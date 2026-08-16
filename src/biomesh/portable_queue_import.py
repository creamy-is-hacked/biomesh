"""Fail-closed P6-WP02 import and explicit local rebinding."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from biomesh import __version__
from biomesh.local_queue_runtime import available_cpu_ids
from biomesh.local_queue_types import LocalQueueError, QueueResourceLimits
from biomesh.portable_queue_import_types import (
    BoundPortableQueueItem,
    LocalProjectBinding,
    PortableQueueBindingRecord,
    PortableQueueBindingResult,
    PortableQueueImportError,
    PortableQueueImportRecord,
    PortableQueueImportResult,
    ProjectPathBinding,
    UnboundPortableQueueItem,
    portable_queue_binding_bytes,
    portable_queue_import_bytes,
)
from biomesh.portable_queue_intent import (
    _absolute_lexical,
    _archive_source_identity,
    _assert_no_symlink_components,
    _read_stable_regular_file,
    _safe_directory,
    _verify_fixture_source,
    _verify_parameter_sources,
)
from biomesh.portable_queue_intent_types import (
    PortableQueueIntentError,
    PortableQueueIntentItem,
    PortableQueueIntentManifest,
    portable_queue_intent_bytes,
    portable_queue_intent_sha256,
)
from biomesh.project_campaign import (
    PROJECT_MANIFEST,
    PROJECT_STATE,
    CampaignRunStatus,
    CampaignService,
    ExecutionIdentity,
    ProjectCampaignError,
    ProjectDefinition,
    ProjectState,
    accepted_core_execution_identity,
    execution_identity_sha256,
)
from biomesh.runtime_resources import runtime_root


@dataclass(frozen=True, slots=True)
class _ProjectValidationStamp:
    """Bytes that must remain stable until bound-record publication."""

    project_definition: bytes
    project_state: bytes
    execution_identity: ExecutionIdentity


def import_portable_queue_intent(
    manifest_path: Path, output: Path
) -> PortableQueueImportResult:
    """Validate a complete canonical manifest and publish only UNBOUND state."""
    source = _safe_input_file(manifest_path, label="portable queue intent")
    output_path = _new_output_file(output, label="portable queue import output")
    source_bytes, manifest = _load_manifest(source)
    try:
        record = PortableQueueImportRecord(
            schema_version=1,
            import_format="biomesh-portable-queue-import",
            source_manifest_sha256=portable_queue_intent_sha256(manifest),
            source_manifest=manifest,
            lifecycle_policy="unbound_non_runnable",
            binding_policy="explicit_complete_local_project_binding_required",
            resource_policy="explicit_new_local_resource_policy_required",
            trust_policy="no_destination_trust_granted",
            calibration_policy="no_calibration_status_promotion",
            items=[
                UnboundPortableQueueItem(status="UNBOUND", intent=item)
                for item in manifest.items
            ],
        )
    except ValidationError as error:
        raise PortableQueueImportError(
            f"invalid portable queue import: {error}"
        ) from error
    contents = portable_queue_import_bytes(record)
    try:
        unchanged_source = _read_stable_regular_file(
            source, label="portable queue intent"
        )
    except PortableQueueIntentError as error:
        raise PortableQueueImportError(str(error)) from error
    if unchanged_source != source_bytes:
        raise PortableQueueImportError(
            "portable queue intent changed during import validation"
        )
    _publish_new_file(output_path, contents, label="portable queue import")
    return PortableQueueImportResult(
        import_record=str(output_path),
        import_sha256=hashlib.sha256(contents).hexdigest(),
        manifest_sha256=record.source_manifest_sha256,
        item_count=len(record.items),
    )


def bind_portable_queue_intent(
    import_record_path: Path,
    output: Path,
    *,
    project_bindings: Sequence[ProjectPathBinding],
    cpu_cores: int,
    memory_limit_bytes: int,
) -> PortableQueueBindingResult:
    """Publish one complete local binding without creating runnable queue state."""
    source = _safe_input_file(import_record_path, label="portable queue import")
    output_path = _new_output_file(output, label="portable queue binding output")
    source_bytes, imported = _load_import_record(source)
    limits = _local_resource_limits(
        cpu_cores=cpu_cores, memory_limit_bytes=memory_limit_bytes
    )
    binding_paths = _complete_binding_paths(imported, project_bindings)
    project_roots = {
        project_id: _safe_bound_project_path(path)
        for project_id, path in binding_paths.items()
    }
    if len(set(project_roots.values())) != len(project_roots):
        raise PortableQueueImportError(
            "each source project requires a distinct local project path"
        )
    _reject_output_inside_projects(output_path, tuple(project_roots.values()))

    try:
        with ExitStack() as stack:
            snapshots: dict[str, tuple[ProjectDefinition, ProjectState]] = {}
            for project_id, project_path in sorted(
                project_roots.items(), key=lambda item: str(item[1])
            ):
                snapshots[project_id] = stack.enter_context(
                    CampaignService(project_path).verified_snapshot(blocking=False)
                )
            stamps = {
                project_id: _validate_bound_project(
                    project_path,
                    definition=snapshots[project_id][0],
                    state=snapshots[project_id][1],
                    intents=[
                        item
                        for item in imported.source_manifest.items
                        if item.project_id == project_id
                    ],
                )
                for project_id, project_path in project_roots.items()
            }
            record = _binding_record(imported, source_bytes, limits, project_roots)
            contents = portable_queue_binding_bytes(record)
            if (
                _read_stable_regular_file(source, label="portable queue import")
                != source_bytes
            ):
                raise PortableQueueImportError(
                    "portable queue import changed during binding validation"
                )
            for project_id, project_path in project_roots.items():
                _revalidate_bound_project(
                    project_path,
                    stamp=stamps[project_id],
                    intents=[
                        item
                        for item in imported.source_manifest.items
                        if item.project_id == project_id
                    ],
                )
            _publish_new_file(output_path, contents, label="portable queue binding")
    except (LocalQueueError, PortableQueueIntentError, ProjectCampaignError) as error:
        raise PortableQueueImportError(str(error)) from error

    return PortableQueueBindingResult(
        binding_record=str(output_path),
        binding_sha256=hashlib.sha256(contents).hexdigest(),
        item_count=len(record.items),
        project_count=len(record.projects),
    )


def parse_project_path_binding(value: str) -> ProjectPathBinding:
    """Parse one explicit CLI PROJECT_ID=/absolute/path binding."""
    if value.count("=") != 1:
        raise PortableQueueImportError(
            "project binding must use PROJECT_ID=/absolute/project/path"
        )
    project_id, path_text = value.split("=", 1)
    if not project_id or not path_text:
        raise PortableQueueImportError(
            "project binding must use PROJECT_ID=/absolute/project/path"
        )
    path_components = path_text.split("/")
    if ".." in path_components[1:]:
        raise PortableQueueImportError(
            "bound local project paths must be absolute and traversal-free"
        )
    if any(component in {"", "."} for component in path_components[1:]):
        raise PortableQueueImportError(
            "bound local project paths contain unsafe path components"
        )
    path = Path(path_text)
    if not path.is_absolute() or ".." in path.parts:
        raise PortableQueueImportError(
            "bound local project paths must be absolute and traversal-free"
        )
    try:
        return ProjectPathBinding(
            project_id=project_id,
            local_project_directory=str(path),
        )
    except ValidationError as error:
        raise PortableQueueImportError(f"invalid project binding: {error}") from error


def _load_manifest(path: Path) -> tuple[bytes, PortableQueueIntentManifest]:
    try:
        contents = _read_stable_regular_file(path, label="portable queue intent")
    except PortableQueueIntentError as error:
        raise PortableQueueImportError(str(error)) from error
    try:
        manifest = PortableQueueIntentManifest.model_validate_json(contents)
    except ValidationError as error:
        raise PortableQueueImportError(
            f"invalid portable queue intent manifest: {error}"
        ) from error
    if portable_queue_intent_bytes(manifest) != contents:
        raise PortableQueueImportError(
            "portable queue intent is not the canonical P6-WP01 byte encoding"
        )
    if manifest.biomesh_version != __version__:
        raise PortableQueueImportError(
            "portable queue intent BioMesh version is incompatible with this runtime"
        )
    return contents, manifest


def _load_import_record(path: Path) -> tuple[bytes, PortableQueueImportRecord]:
    try:
        contents = _read_stable_regular_file(path, label="portable queue import")
    except PortableQueueIntentError as error:
        raise PortableQueueImportError(str(error)) from error
    try:
        record = PortableQueueImportRecord.model_validate_json(contents)
    except ValidationError as error:
        raise PortableQueueImportError(
            f"invalid portable queue import record: {error}"
        ) from error
    if portable_queue_import_bytes(record) != contents:
        raise PortableQueueImportError(
            "portable queue import record is not canonical strict JSON"
        )
    if record.source_manifest.biomesh_version != __version__:
        raise PortableQueueImportError(
            "portable queue import BioMesh version is incompatible with this runtime"
        )
    return contents, record


def _local_resource_limits(
    *, cpu_cores: int, memory_limit_bytes: int
) -> QueueResourceLimits:
    try:
        limits = QueueResourceLimits(
            cpu_cores=cpu_cores,
            memory_limit_bytes=memory_limit_bytes,
        )
    except ValidationError as error:
        raise PortableQueueImportError(
            f"invalid new local resource policy: {error}"
        ) from error
    available = available_cpu_ids()
    if limits.cpu_cores > len(available):
        raise PortableQueueImportError(
            f"cpu_cores exceeds the {len(available)} CPUs available to this process"
        )
    return limits


def _complete_binding_paths(
    imported: PortableQueueImportRecord,
    bindings: Sequence[ProjectPathBinding],
) -> dict[str, Path]:
    project_ids = [binding.project_id for binding in bindings]
    if len(project_ids) != len(set(project_ids)):
        raise PortableQueueImportError("duplicate local project binding identity")
    expected = {item.intent.project_id for item in imported.items}
    supplied = set(project_ids)
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise PortableQueueImportError(
            "project bindings must be one complete exact set: " + "; ".join(details)
        )
    return {
        binding.project_id: Path(binding.local_project_directory)
        for binding in bindings
    }


def _safe_bound_project_path(path: Path) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise PortableQueueImportError(
            "bound local project paths must be absolute and traversal-free"
        )
    try:
        return _safe_directory(path, label="bound local project directory")
    except PortableQueueIntentError as error:
        raise PortableQueueImportError(str(error)) from error


def _validate_bound_project(
    project_path: Path,
    *,
    definition: ProjectDefinition,
    state: ProjectState,
    intents: list[PortableQueueIntentItem],
) -> _ProjectValidationStamp:
    if not intents:
        raise PortableQueueImportError("bound project has no imported intent")
    project_id = intents[0].project_id
    if any(item.project_id != project_id for item in intents):
        raise PortableQueueImportError("bound project intent identity is ambiguous")
    if definition.project.project_id != project_id:
        raise PortableQueueImportError(
            f"bound project ID does not match imported source: {project_id}"
        )
    definition_bytes = _read_stable_regular_file(
        project_path / PROJECT_MANIFEST, label="bound project definition"
    )
    try:
        disk_definition = ProjectDefinition.model_validate_json(definition_bytes)
    except ValidationError as error:
        raise PortableQueueImportError(
            f"invalid bound project definition: {error}"
        ) from error
    if disk_definition != definition:
        raise PortableQueueImportError(
            f"bound project definition changed during validation: {project_id}"
        )
    definition_hash = hashlib.sha256(definition_bytes).hexdigest()
    if any(
        item.source.project_definition_sha256 != definition_hash for item in intents
    ):
        raise PortableQueueImportError(
            f"bound project definition source drifted: {project_id}"
        )
    if state.definition_sha256 != definition_hash:
        raise PortableQueueImportError(
            f"bound project state does not match its definition: {project_id}"
        )
    state_bytes = _read_stable_regular_file(
        project_path / PROJECT_STATE, label="bound project state"
    )
    try:
        disk_state = ProjectState.model_validate_json(state_bytes)
    except ValidationError as error:
        raise PortableQueueImportError(
            f"invalid bound project state: {error}"
        ) from error
    if disk_state != state:
        raise PortableQueueImportError(
            f"bound project state changed during validation: {project_id}"
        )
    expected_identity = accepted_core_execution_identity(runtime_root(Path.cwd()))
    identity = definition.execution_identity
    if identity is None or identity != expected_identity:
        raise PortableQueueImportError(
            f"bound project execution dependency identity is incompatible: {project_id}"
        )
    _verify_parameter_sources(project_path, identity)
    archive_source = _archive_source_identity(project_path)
    for intent in intents:
        campaigns = [
            campaign
            for campaign in definition.campaigns
            if campaign.campaign_id == intent.campaign.campaign_id
        ]
        if len(campaigns) != 1 or campaigns[0] != intent.campaign:
            raise PortableQueueImportError(
                f"bound campaign identity is missing, ambiguous, or drifted: "
                f"{intent.campaign.campaign_id}"
            )
        experiments = [
            experiment
            for experiment in definition.experiments
            if experiment.experiment_id == intent.experiment.experiment_id
        ]
        if len(experiments) != 1:
            raise PortableQueueImportError(
                f"bound experiment identity is missing or ambiguous: "
                f"{intent.experiment.experiment_id}"
            )
        experiment = experiments[0]
        if (
            experiment.fixture_sha256 != intent.experiment.fixture_sha256
            or experiment.calibration_status != intent.experiment.calibration_status
        ):
            raise PortableQueueImportError(
                f"bound experiment dependency drifted: {experiment.experiment_id}"
            )
        _verify_fixture_source(project_path, experiment)
        if (
            intent.execution_identity != identity
            or intent.execution_identity_sha256 != execution_identity_sha256(identity)
        ):
            raise PortableQueueImportError(
                f"bound execution dependency identity drifted: "
                f"{intent.campaign.campaign_id}"
            )
        runs = [
            run
            for run in state.runs
            if run.campaign_id == intent.campaign.campaign_id
        ]
        if any(run.status is CampaignRunStatus.RUNNING for run in runs):
            raise PortableQueueImportError(
                f"bound campaign is currently running: {intent.campaign.campaign_id}"
            )
        if not any(run.status is CampaignRunStatus.PENDING for run in runs):
            raise PortableQueueImportError(
                f"bound campaign has no pending work: {intent.campaign.campaign_id}"
            )
        if archive_source != intent.source.archive:
            raise PortableQueueImportError(
                f"bound archive source provenance drifted: {project_id}"
            )
    return _ProjectValidationStamp(
        project_definition=definition_bytes,
        project_state=state_bytes,
        execution_identity=identity,
    )


def _revalidate_bound_project(
    project_path: Path,
    *,
    stamp: _ProjectValidationStamp,
    intents: list[PortableQueueIntentItem],
) -> None:
    if (
        _read_stable_regular_file(
            project_path / PROJECT_MANIFEST, label="bound project definition"
        )
        != stamp.project_definition
        or _read_stable_regular_file(
            project_path / PROJECT_STATE, label="bound project state"
        )
        != stamp.project_state
    ):
        raise PortableQueueImportError(
            "bound project changed during complete-set validation"
        )
    _verify_parameter_sources(project_path, stamp.execution_identity)
    for intent in intents:
        matching = [
            experiment
            for experiment in ProjectDefinition.model_validate_json(
                stamp.project_definition
            ).experiments
            if experiment.experiment_id == intent.experiment.experiment_id
        ]
        if len(matching) != 1:
            raise PortableQueueImportError("bound experiment identity drifted")
        _verify_fixture_source(project_path, matching[0])
    if _archive_source_identity(project_path) != intents[0].source.archive:
        raise PortableQueueImportError(
            "bound archive source changed during complete-set validation"
        )


def _binding_record(
    imported: PortableQueueImportRecord,
    source_bytes: bytes,
    limits: QueueResourceLimits,
    project_roots: dict[str, Path],
) -> PortableQueueBindingRecord:
    source_by_project = {
        item.project_id: item.source for item in imported.source_manifest.items
    }
    projects = [
        LocalProjectBinding(
            project_id=project_id,
            source_project_definition_sha256=(
                source_by_project[project_id].project_definition_sha256
            ),
            local_project_directory=str(project_roots[project_id]),
            source_archive=source_by_project[project_id].archive,
            destination_archive_trust="NOT_GRANTED",
            destination_plugin_trust="NOT_GRANTED",
            destination_registry_trust="NOT_GRANTED",
            destination_authorization="NOT_GRANTED",
            destination_calibration_status="CALIBRATION_REQUIRED",
        )
        for project_id in sorted(project_roots)
    ]
    try:
        return PortableQueueBindingRecord(
            schema_version=1,
            binding_format="biomesh-portable-queue-local-binding",
            source_import_sha256=hashlib.sha256(source_bytes).hexdigest(),
            source_manifest_sha256=imported.source_manifest_sha256,
            source_manifest=imported.source_manifest,
            lifecycle_policy="bound_non_runnable_p6_wp03_activation_required",
            ordering_policy="source_manifest_order_preserved",
            resource_policy="explicit_new_local_policy_not_source_receipt",
            trust_policy="no_destination_trust_granted",
            calibration_policy="no_calibration_status_promotion",
            local_resource_limits=limits,
            projects=projects,
            items=[
                BoundPortableQueueItem(
                    status="BOUND_NONRUNNABLE",
                    intent=item.intent,
                    local_project_directory=str(
                        project_roots[item.intent.project_id]
                    ),
                )
                for item in imported.items
            ],
        )
    except ValidationError as error:
        raise PortableQueueImportError(
            f"invalid complete portable queue binding: {error}"
        ) from error


def _safe_input_file(path: Path, *, label: str) -> Path:
    if ".." in path.parts:
        raise PortableQueueImportError(f"{label} path contains traversal")
    absolute = _absolute_lexical(path)
    try:
        _assert_no_symlink_components(absolute, label=label)
        _read_stable_regular_file(absolute, label=label)
    except PortableQueueIntentError as error:
        raise PortableQueueImportError(str(error)) from error
    return absolute


def _new_output_file(path: Path, *, label: str) -> Path:
    if ".." in path.parts:
        raise PortableQueueImportError(f"{label} path contains traversal")
    absolute = _absolute_lexical(path)
    if os.path.lexists(absolute):
        raise PortableQueueImportError(f"{label} already exists: {path}")
    try:
        _safe_directory(absolute.parent, label=f"{label} parent")
    except PortableQueueIntentError as error:
        raise PortableQueueImportError(str(error)) from error
    return absolute


def _reject_output_inside_projects(output: Path, projects: tuple[Path, ...]) -> None:
    for project in projects:
        if output.is_relative_to(project):
            raise PortableQueueImportError(
                "portable queue binding output must be outside bound projects"
            )


def _publish_new_file(path: Path, contents: bytes, *, label: str) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    published = False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as error:
            raise PortableQueueImportError(f"{label} already exists: {path}") from error
        published = True
        temporary.unlink()
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_descriptor = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except Exception:
        temporary.unlink(missing_ok=True)
        if published:
            path.unlink(missing_ok=True)
        raise
