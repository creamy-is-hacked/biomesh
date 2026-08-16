"""Fail-closed P6-WP03 activation into the existing local P4 queue."""

from __future__ import annotations

import hashlib
import os
import tempfile
from contextlib import ExitStack
from pathlib import Path

from pydantic import ValidationError

from biomesh import __version__
from biomesh.local_queue_storage import state_bytes
from biomesh.local_queue_types import (
    QUEUE_LOCK,
    QUEUE_WORKER_LOCK,
    LocalQueueError,
    LocalQueueState,
    QueueAuditRecord,
    QueueItem,
    QueueItemStatus,
)
from biomesh.portable_queue_activation_types import (
    PORTABLE_QUEUE_ACTIVATION_FILE,
    ActivatedPortableQueueItem,
    PortableQueueActivationError,
    PortableQueueActivationRecord,
    portable_queue_activation_bytes,
)
from biomesh.portable_queue_import import (
    _revalidate_bound_project,
    _safe_bound_project_path,
    _safe_input_file,
    _validate_bound_project,
)
from biomesh.portable_queue_import_types import (
    PortableQueueBindingRecord,
    PortableQueueImportError,
    portable_queue_binding_bytes,
)
from biomesh.portable_queue_intent import (
    _assert_no_symlink_components,
    _read_stable_regular_file,
    _safe_directory,
)
from biomesh.portable_queue_intent_types import (
    PortableQueueIntentError,
    portable_queue_intent_item_sha256,
)
from biomesh.project_campaign import CampaignService, ProjectDefinition, ProjectState


def activate_portable_queue_binding(
    binding_record_path: Path, queue_directory: Path, *, dry_run: bool = False
) -> PortableQueueActivationRecord:
    """Validate a complete binding and optionally publish a fresh local queue."""
    try:
        source = _safe_input_file(
            binding_record_path, label="portable queue local binding"
        )
    except PortableQueueImportError as error:
        raise PortableQueueActivationError(str(error)) from error
    source_bytes, binding = _load_binding(source)
    queue_path = _new_queue_path(queue_directory)
    try:
        project_roots = {
            project.project_id: _safe_bound_project_path(
                Path(project.local_project_directory)
            )
            for project in binding.projects
        }
    except PortableQueueImportError as error:
        raise PortableQueueActivationError(str(error)) from error
    if queue_path in project_roots.values() or any(
        queue_path.is_relative_to(project) or project.is_relative_to(queue_path)
        for project in project_roots.values()
    ):
        raise PortableQueueActivationError(
            "activation queue directory must be separate from every bound project"
        )

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
                        item.intent
                        for item in binding.items
                        if item.intent.project_id == project_id
                    ],
                )
                for project_id, project_path in project_roots.items()
            }
            state, activation = _activation_records(
                binding, source_bytes, project_roots
            )
            state_contents = state_bytes(state)
            activation_contents = portable_queue_activation_bytes(activation)
            if (
                _read_stable_regular_file(source, label="portable queue binding")
                != source_bytes
            ):
                raise PortableQueueActivationError(
                    "portable queue binding changed during activation validation"
                )
            for project_id, project_path in project_roots.items():
                _revalidate_bound_project(
                    project_path,
                    stamp=stamps[project_id],
                    intents=[
                        item.intent
                        for item in binding.items
                        if item.intent.project_id == project_id
                    ],
                )
            if not dry_run:
                _publish_queue(
                    queue_path,
                    state_contents=state_contents,
                    activation_contents=activation_contents,
                )
    except (LocalQueueError, PortableQueueActivationError, OSError) as error:
        if isinstance(error, PortableQueueActivationError):
            raise
        raise PortableQueueActivationError(str(error)) from error
    return activation


def load_portable_queue_activation(
    queue_directory: Path,
) -> PortableQueueActivationRecord | None:
    """Load and canonical-verify activation provenance, if this is a P6 queue."""
    path = queue_directory / PORTABLE_QUEUE_ACTIVATION_FILE
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise LocalQueueError("portable queue activation record is unsafe")
    try:
        contents = _read_stable_regular_file(
            path, label="portable queue activation record"
        )
        record = PortableQueueActivationRecord.model_validate_json(contents)
        if portable_queue_activation_bytes(record) != contents:
            raise PortableQueueActivationError(
                "portable queue activation record is not canonical strict JSON"
            )
        return record
    except (
        PortableQueueActivationError,
        PortableQueueIntentError,
        ValidationError,
        OSError,
    ) as error:
        raise LocalQueueError(
            f"invalid portable queue activation record: {error}"
        ) from error


def load_portable_queue_binding(path: Path) -> PortableQueueBindingRecord:
    """Read one canonical complete binding for report traceability."""
    try:
        source = _safe_input_file(path, label="portable queue local binding")
    except PortableQueueImportError as error:
        raise PortableQueueActivationError(str(error)) from error
    contents = _read_stable_regular_file(source, label="portable queue binding")
    try:
        record = PortableQueueBindingRecord.model_validate_json(contents)
    except ValidationError as error:
        raise PortableQueueActivationError(
            f"invalid portable queue binding: {error}"
        ) from error
    if portable_queue_binding_bytes(record) != contents:
        raise PortableQueueActivationError(
            "portable queue binding is not canonical strict JSON"
        )
    return record


def validate_portable_queue_state(
    state: LocalQueueState, activation: PortableQueueActivationRecord | None
) -> None:
    """Ensure an activated queue cannot mix or duplicate its bound items."""
    if activation is None:
        return
    if state.resource_limits != activation.destination_resource_limits:
        raise LocalQueueError("activated queue resource policy changed")
    if len(state.items) != len(activation.items):
        raise LocalQueueError("activated queue item count changed")
    for queue_item, activated in zip(state.items, activation.items, strict=True):
        if (
            queue_item.queue_id != activated.local_queue_id
            or queue_item.project_directory != activated.local_project_directory
            or queue_item.campaign_id != activated.campaign_id
        ):
            raise LocalQueueError(
                "activated queue item identity or project path changed"
            )


def portable_trace_for_queue_item(
    activation: PortableQueueActivationRecord,
    queue_id: str,
    run_id: str | None,
) -> dict[str, object]:
    """Return portable identity plus explicit destination run identity."""
    try:
        item = next(
            item for item in activation.items if item.local_queue_id == queue_id
        )
    except StopIteration as error:
        raise LocalQueueError(f"activated queue item is missing: {queue_id}") from error
    # The manifest and activation items are both canonical and ordered. Resolve
    # by the activation sequence rather than a mutable queue field.
    intent = activation.source_binding.source_manifest.items[item.intent_sequence]
    archive = intent.source.archive
    trace = {
        "schema_version": 1,
        "portable_manifest_sha256": activation.source_manifest_sha256,
        "portable_intent_item_sha256": portable_queue_intent_item_sha256(intent),
        "source_import_sha256": activation.source_import_sha256,
        "source_project_definition_sha256": intent.source.project_definition_sha256,
        "project_id": intent.project_id,
        "campaign_id": intent.campaign.campaign_id,
        "experiment_id": intent.experiment.experiment_id,
        "fixture_sha256": intent.experiment.fixture_sha256,
        "execution_identity_sha256": intent.execution_identity_sha256,
        "plugin_set_sha256": intent.execution_identity.plugin_set_sha256,
        "source_archive": (
            None
            if archive is None
            else archive.model_dump(mode="json")
        ),
    }
    if run_id is not None:
        trace["run_id"] = run_id
    return trace


def _load_binding(
    path: Path,
) -> tuple[bytes, PortableQueueBindingRecord]:
    try:
        contents = _read_stable_regular_file(path, label="portable queue binding")
        record = PortableQueueBindingRecord.model_validate_json(contents)
        if portable_queue_binding_bytes(record) != contents:
            raise PortableQueueActivationError(
                "portable queue binding is not canonical strict JSON"
            )
        if record.source_manifest.biomesh_version != __version__:
            raise PortableQueueActivationError(
                "portable queue binding BioMesh version is incompatible with "
                "this runtime"
            )
        return contents, record
    except (PortableQueueIntentError, ValidationError, OSError) as error:
        raise PortableQueueActivationError(
            f"invalid portable queue binding: {error}"
        ) from error


def _new_queue_path(path: Path) -> Path:
    if ".." in path.parts:
        raise PortableQueueActivationError("activation queue path contains traversal")
    absolute = path.absolute()
    if os.path.lexists(absolute):
        raise PortableQueueActivationError(f"activation queue already exists: {path}")
    try:
        _assert_no_symlink_components(absolute.parent, label="activation queue parent")
        _safe_directory(absolute.parent, label="activation queue parent")
    except Exception as error:
        raise PortableQueueActivationError(str(error)) from error
    return absolute


def _activation_records(
    binding: PortableQueueBindingRecord,
    source_bytes: bytes,
    project_roots: dict[str, Path],
) -> tuple[LocalQueueState, PortableQueueActivationRecord]:
    queue_items: list[QueueItem] = []
    activation_items: list[ActivatedPortableQueueItem] = []
    audit = [
        QueueAuditRecord(
            sequence=0,
            action="queue_created",
            detail="created fresh local queue by explicit P6-WP03 activation",
        )
    ]
    for sequence, bound in enumerate(binding.items):
        queue_id = f"queue-{sequence:08d}-{bound.intent.campaign.campaign_id}"
        queue_items.append(
            QueueItem(
                queue_id=queue_id,
                enqueue_sequence=sequence,
                project_directory=bound.local_project_directory,
                campaign_id=bound.intent.campaign.campaign_id,
                priority=bound.intent.priority,
                status=QueueItemStatus.QUEUED,
            )
        )
        audit.append(
            QueueAuditRecord(
                sequence=sequence + 1,
                action="campaign_enqueued",
                queue_id=queue_id,
                detail=f"activated portable intent sequence {sequence}",
            )
        )
        activation_items.append(
            ActivatedPortableQueueItem(
                status="ACTIVATED",
                intent_sequence=sequence,
                portable_intent_item_sha256=portable_queue_intent_item_sha256(
                    bound.intent
                ),
                project_id=bound.intent.project_id,
                campaign_id=bound.intent.campaign.campaign_id,
                local_project_directory=project_roots[bound.intent.project_id].as_posix(),
                local_queue_id=queue_id,
            )
        )
    state = LocalQueueState(
        schema_version=1,
        generation=0,
        next_sequence=len(queue_items),
        resource_limits=binding.local_resource_limits,
        items=queue_items,
        audit=audit,
    )
    try:
        activation = PortableQueueActivationRecord(
            schema_version=1,
            activation_format="biomesh-portable-queue-activation",
            source_binding_sha256=hashlib.sha256(source_bytes).hexdigest(),
            source_import_sha256=binding.source_import_sha256,
            source_manifest_sha256=binding.source_manifest_sha256,
            source_binding=binding,
            lifecycle_policy="activated_local_p4_queue_only",
            scheduler_policy="new_destination_queue_identity_only",
            resource_policy="binding_local_policy_verified_at_activation",
            trust_policy="no_destination_trust_granted",
            calibration_policy="no_calibration_status_promotion",
            destination_queue_schema_version=1,
            destination_resource_limits=binding.local_resource_limits,
            items=activation_items,
        )
    except ValidationError as error:
        raise PortableQueueActivationError(
            f"invalid portable queue activation: {error}"
        ) from error
    return state, activation


def _publish_queue(
    path: Path, *, state_contents: bytes, activation_contents: bytes
) -> None:
    staging = Path(tempfile.mkdtemp(prefix=f".{path.name}.", dir=path.parent))
    published = False
    try:
        (staging / QUEUE_LOCK).touch()
        (staging / QUEUE_WORKER_LOCK).touch()
        _write_new(staging / "queue_state.json", state_contents)
        _write_new(staging / PORTABLE_QUEUE_ACTIVATION_FILE, activation_contents)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(staging, directory_flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if os.path.lexists(path):
            raise PortableQueueActivationError(
                f"activation queue already exists: {path}"
            )
        os.replace(staging, path)
        published = True
        parent_descriptor = os.open(path.parent, directory_flags)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    except Exception:
        if not published and staging.exists():
            import shutil

            shutil.rmtree(staging, ignore_errors=True)
        raise


def _write_new(path: Path, contents: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(contents)
        stream.flush()
        os.fsync(stream.fileno())
