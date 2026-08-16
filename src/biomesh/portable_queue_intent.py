"""Read-only, deterministic P6-WP01 export of P4 local queue intent."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from biomesh import __version__
from biomesh.local_queue_runtime import item_worker_is_live
from biomesh.local_queue_storage import LocalQueueStore
from biomesh.local_queue_types import (
    LocalQueueError,
    LocalQueueState,
    QueueItem,
    QueueItemStatus,
)
from biomesh.portable_project import ARCHIVE_SECURITY_STATUS
from biomesh.portable_queue_intent_types import (
    ArchiveSourceIdentity,
    ExperimentDependencyIdentity,
    PortableQueueIntentError,
    PortableQueueIntentItem,
    PortableQueueIntentManifest,
    PortableQueueIntentResult,
    ProjectSourceIdentity,
    portable_queue_intent_bytes,
)
from biomesh.project_campaign import (
    PROJECT_MANIFEST,
    PROJECT_STATE,
    CampaignRecord,
    CampaignRunStatus,
    CampaignService,
    ExecutionIdentity,
    ExperimentRecord,
    ProjectCampaignError,
    ProjectDefinition,
    ProjectState,
    accepted_core_execution_identity,
    execution_identity_sha256,
)
from biomesh.runtime_resources import runtime_root

_ARCHIVE_STATUS_FIELDS = {
    "archive_security_format",
    "authenticity_status",
    "confidentiality_status",
    "envelope_sha256",
    "payload_sha256",
    "replay_binding",
    "schema_version",
    "signer_id",
    "signing_key_id",
}


def export_portable_queue_intent(
    queue_directory: Path, output: Path, *, dry_run: bool = False
) -> PortableQueueIntentResult:
    """Verify queued intent and optionally publish its canonical bytes."""
    queue_root = _safe_directory(queue_directory, label="local queue directory")
    output_path = _new_output_path(output)
    store = LocalQueueStore(queue_root)
    try:
        with store.worker_lock(), store.lock(), ExitStack() as projects:
            state = store.load()
            _reject_active_or_stale_queue_items(state)
            queued = [
                item for item in state.items if item.status is QueueItemStatus.QUEUED
            ]
            if not queued:
                raise PortableQueueIntentError(
                    "local queue has no queued campaign intent to export"
                )
            project_paths = {
                item.project_directory: _safe_directory(
                    Path(item.project_directory), label="queued project directory"
                )
                for item in queued
            }
            _reject_output_inside_sources(
                output_path, queue_root, tuple(project_paths.values())
            )
            records: dict[str, tuple[ProjectDefinition, ProjectState]] = {}
            for label, project_path in sorted(project_paths.items()):
                try:
                    snapshot = projects.enter_context(
                        CampaignService(project_path).verified_snapshot(blocking=False)
                    )
                except ValueError as error:
                    raise PortableQueueIntentError(
                        f"queued project is active or invalid: {label}: {error}"
                    ) from error
                records[label] = snapshot
            manifest = _build_manifest(state, queued, project_paths, records)
            contents = portable_queue_intent_bytes(manifest)
            PortableQueueIntentManifest.model_validate_json(contents)
            if store.load() != state:
                raise PortableQueueIntentError(
                    "local queue state drifted during intent export"
                )
            if not dry_run:
                _publish_manifest(output_path, contents)
    except (LocalQueueError, ProjectCampaignError) as error:
        raise PortableQueueIntentError(str(error)) from error
    return PortableQueueIntentResult(
        manifest=str(output_path),
        manifest_sha256=hashlib.sha256(contents).hexdigest(),
        item_count=len(manifest.items),
    )


def _reject_active_or_stale_queue_items(state: LocalQueueState) -> None:
    for item in state.items:
        if item.status is not QueueItemStatus.RUNNING:
            continue
        if item_worker_is_live(item):
            raise PortableQueueIntentError(
                f"local queue has active item {item.queue_id}; export is refused"
            )
        raise PortableQueueIntentError(
            f"local queue has stale running item {item.queue_id}; reconcile it "
            "explicitly before export"
        )


def _build_manifest(
    state: LocalQueueState,
    queued: list[QueueItem],
    project_paths: dict[str, Path],
    records: dict[str, tuple[ProjectDefinition, ProjectState]],
) -> PortableQueueIntentManifest:
    ordered = sorted(
        queued,
        key=lambda item: (-item.priority, item.enqueue_sequence),
    )
    items = [
        _intent_item(
            intent_sequence=index,
            queue_item=item,
            project_path=project_paths[item.project_directory],
            definition=records[item.project_directory][0],
            project_state=records[item.project_directory][1],
        )
        for index, item in enumerate(ordered)
    ]
    try:
        return PortableQueueIntentManifest(
            schema_version=1,
            manifest_format="biomesh-portable-queue-intent",
            biomesh_version=__version__,
            source_queue_schema_version=state.schema_version,
            ordering_policy="priority_descending_fifo",
            lifecycle_policy="queued_intent_only_no_live_or_terminal_state",
            resource_policy="local_resource_policy_not_transported",
            trust_policy="source_archive_status_is_provenance_not_trust",
            calibration_policy="no_calibration_status_promotion",
            items=items,
        )
    except ValidationError as error:
        raise PortableQueueIntentError(
            f"invalid portable queue intent: {error}"
        ) from error


def _intent_item(
    *,
    intent_sequence: int,
    queue_item: QueueItem,
    project_path: Path,
    definition: ProjectDefinition,
    project_state: ProjectState,
) -> PortableQueueIntentItem:
    campaign = _campaign(definition, queue_item.campaign_id)
    experiment = _experiment(definition, campaign.experiment_id)
    runs = [
        run for run in project_state.runs if run.campaign_id == campaign.campaign_id
    ]
    if any(run.status is CampaignRunStatus.RUNNING for run in runs):
        raise PortableQueueIntentError(
            f"queued campaign is active in its project: {campaign.campaign_id}"
        )
    if not any(run.status is CampaignRunStatus.PENDING for run in runs):
        raise PortableQueueIntentError(
            f"queued campaign reference is stale with no pending work: "
            f"{campaign.campaign_id}"
        )
    identity = definition.execution_identity
    if definition.schema_version != 2 or identity is None:
        raise PortableQueueIntentError(
            "portable queue intent requires a schema-version 2 project with "
            "explicit execution identity"
        )
    expected = accepted_core_execution_identity(runtime_root(Path.cwd()))
    if identity != expected:
        raise PortableQueueIntentError(
            "queued project execution dependency identity is stale or incompatible"
        )
    _verify_fixture_source(project_path, experiment)
    _verify_parameter_sources(project_path, identity)
    manifest_bytes = _read_stable_regular_file(
        project_path / PROJECT_MANIFEST, label="project definition"
    )
    try:
        disk_definition = ProjectDefinition.model_validate_json(manifest_bytes)
    except ValidationError as error:
        raise PortableQueueIntentError(
            f"invalid queued project definition: {error}"
        ) from error
    if disk_definition != definition:
        raise PortableQueueIntentError(
            "queued project definition drifted during export"
        )
    state_bytes = _read_stable_regular_file(
        project_path / PROJECT_STATE, label="project state"
    )
    try:
        disk_state = ProjectState.model_validate_json(state_bytes)
    except ValidationError as error:
        raise PortableQueueIntentError(
            f"invalid queued project state: {error}"
        ) from error
    if disk_state != project_state:
        raise PortableQueueIntentError("queued project state drifted during export")
    source = ProjectSourceIdentity(
        project_schema_version=2,
        project_definition_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        archive=_archive_source_identity(project_path),
    )
    try:
        return PortableQueueIntentItem(
            intent_sequence=intent_sequence,
            priority=queue_item.priority,
            project_id=definition.project.project_id,
            campaign=campaign,
            experiment=ExperimentDependencyIdentity(
                experiment_id=experiment.experiment_id,
                fixture_sha256=experiment.fixture_sha256,
                calibration_status=experiment.calibration_status,
            ),
            execution_identity=identity,
            execution_identity_sha256=execution_identity_sha256(identity),
            source=source,
        )
    except ValidationError as error:
        raise PortableQueueIntentError(
            f"invalid queued campaign intent {campaign.campaign_id}: {error}"
        ) from error


def _campaign(definition: ProjectDefinition, campaign_id: str) -> CampaignRecord:
    matches = [item for item in definition.campaigns if item.campaign_id == campaign_id]
    if len(matches) != 1:
        raise PortableQueueIntentError(
            f"queued campaign reference is missing or ambiguous: {campaign_id}"
        )
    return matches[0]


def _experiment(
    definition: ProjectDefinition, experiment_id: str
) -> ExperimentRecord:
    matches = [
        item for item in definition.experiments if item.experiment_id == experiment_id
    ]
    if len(matches) != 1:
        raise PortableQueueIntentError(
            f"queued experiment dependency is missing or ambiguous: {experiment_id}"
        )
    return matches[0]


def _verify_fixture_source(
    project_path: Path, experiment: ExperimentRecord
) -> None:
    source = _resolve_unique_source(
        project_path,
        experiment.fixture_file,
        label=f"experiment fixture {experiment.experiment_id}",
        allow_absolute=True,
    )
    contents = _read_stable_regular_file(source, label="experiment fixture")
    if hashlib.sha256(contents).hexdigest() != experiment.fixture_sha256:
        raise PortableQueueIntentError(
            f"experiment fixture drifted: {experiment.experiment_id}"
        )


def _verify_parameter_sources(
    project_path: Path, identity: ExecutionIdentity
) -> None:
    for model in identity.models:
        source = _resolve_unique_source(
            project_path,
            model.parameter_source,
            label=f"parameter source {model.parameter_source}",
            allow_absolute=False,
        )
        contents = _read_stable_regular_file(source, label="parameter source")
        if hashlib.sha256(contents).hexdigest() != model.parameter_source_sha256:
            raise PortableQueueIntentError(
                f"execution parameter source drifted: {model.parameter_source}"
            )


def _resolve_unique_source(
    project_path: Path,
    value: str,
    *,
    label: str,
    allow_absolute: bool,
) -> Path:
    path = Path(value)
    if path.is_absolute():
        if not allow_absolute:
            raise PortableQueueIntentError(f"{label} must use a relative identity")
        candidates = [_absolute_lexical(path)]
    else:
        project_candidate = _absolute_lexical(project_path / path)
        if os.path.lexists(project_candidate):
            candidates = [project_candidate]
        else:
            candidates = [_absolute_lexical(Path.cwd() / path)]
            try:
                candidates.append(
                    _absolute_lexical(runtime_root(Path.cwd()) / path)
                )
            except (OSError, RuntimeError):
                pass
    unique = list(dict.fromkeys(candidates))
    available: list[Path] = []
    for candidate in unique:
        if not os.path.lexists(candidate):
            continue
        _assert_no_symlink_components(candidate, label=label)
        try:
            candidate_status = os.lstat(candidate)
        except OSError as error:
            raise PortableQueueIntentError(
                f"unable to inspect {label}: {error}"
            ) from error
        if not stat.S_ISREG(candidate_status.st_mode):
            raise PortableQueueIntentError(f"{label} is not a regular file")
        available.append(candidate)
    if not available:
        raise PortableQueueIntentError(f"{label} is missing")
    if len(available) != 1:
        raise PortableQueueIntentError(f"{label} resolves ambiguously")
    return available[0]


def _archive_source_identity(project_path: Path) -> ArchiveSourceIdentity | None:
    status_path = project_path / ARCHIVE_SECURITY_STATUS
    if not os.path.lexists(status_path):
        return None
    contents = _read_stable_regular_file(status_path, label="archive source status")
    try:
        payload = json.loads(contents, object_pairs_hook=_reject_duplicate_fields)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise PortableQueueIntentError(
            "archive source status is not strict JSON"
        ) from error
    if not isinstance(payload, dict) or set(payload) != _ARCHIVE_STATUS_FIELDS:
        raise PortableQueueIntentError("archive source status fields are invalid")
    if payload["archive_security_format"] != "biomesh-archive-security-status":
        raise PortableQueueIntentError("archive source status format is invalid")
    try:
        return ArchiveSourceIdentity.model_validate(
            {
                key: value
                for key, value in payload.items()
                if key != "archive_security_format"
            }
        )
    except ValidationError as error:
        raise PortableQueueIntentError(
            f"archive source status is invalid: {error}"
        ) from error


def _reject_duplicate_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON field: {key}")
        value[key] = item
    return value


def _safe_directory(path: Path, *, label: str) -> Path:
    absolute = _absolute_lexical(path)
    _assert_no_symlink_components(absolute, label=label)
    try:
        status = os.lstat(absolute)
    except OSError as error:
        raise PortableQueueIntentError(f"{label} is unavailable: {error}") from error
    if not stat.S_ISDIR(status.st_mode):
        raise PortableQueueIntentError(f"{label} is not a directory")
    return absolute


def _new_output_path(path: Path) -> Path:
    absolute = _absolute_lexical(path)
    if os.path.lexists(absolute):
        raise PortableQueueIntentError(f"portable queue intent already exists: {path}")
    parent = absolute.parent
    _assert_no_symlink_components(parent, label="portable intent output parent")
    if not parent.is_dir():
        raise PortableQueueIntentError("portable intent output parent is unavailable")
    return absolute


def _reject_output_inside_sources(
    output: Path, queue_root: Path, project_paths: tuple[Path, ...]
) -> None:
    for root in (queue_root, *project_paths):
        if output.is_relative_to(root):
            raise PortableQueueIntentError(
                "portable intent output must be outside queue and project directories"
            )


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_no_symlink_components(path: Path, *, label: str) -> None:
    absolute = _absolute_lexical(path)
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            status = os.lstat(current)
        except FileNotFoundError as error:
            raise PortableQueueIntentError(f"{label} is missing: {current}") from error
        except OSError as error:
            raise PortableQueueIntentError(
                f"unable to inspect {label}: {error}"
            ) from error
        if stat.S_ISLNK(status.st_mode):
            raise PortableQueueIntentError(
                f"{label} contains a symlinked path component: {current}"
            )


def _read_stable_regular_file(path: Path, *, label: str) -> bytes:
    absolute = _absolute_lexical(path)
    _assert_no_symlink_components(absolute, label=label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags)
    except OSError as error:
        raise PortableQueueIntentError(f"unable to open {label}: {error}") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise PortableQueueIntentError(f"{label} is not a regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        path_status = os.lstat(absolute)
    except OSError as error:
        raise PortableQueueIntentError(f"{label} drifted during export") from error
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
    )
    identity_path = (
        path_status.st_dev,
        path_status.st_ino,
        path_status.st_mode,
        path_status.st_size,
        path_status.st_mtime_ns,
    )
    if identity_before != identity_after or identity_after != identity_path:
        raise PortableQueueIntentError(f"{label} drifted during export")
    return b"".join(chunks)


def _publish_manifest(path: Path, contents: bytes) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        if os.path.lexists(path):
            raise PortableQueueIntentError(
                f"portable queue intent already exists: {path}"
            )
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
