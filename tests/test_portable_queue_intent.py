"""Focused P6-WP01 portable queue-intent and application-path tests."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from biomesh.__main__ import main
from biomesh.local_queue import LocalQueueService
from biomesh.local_queue_runtime import process_start_ticks
from biomesh.local_queue_storage import create_local_queue
from biomesh.local_queue_types import (
    AppliedResourceLimits,
    LocalQueueState,
    QueueItemStatus,
)
from biomesh.portable_project import export_project_archive, import_project_archive
from biomesh.portable_queue_intent import export_portable_queue_intent
from biomesh.portable_queue_intent_types import (
    PortableQueueIntentError,
    PortableQueueIntentManifest,
)
from biomesh.project_campaign import (
    CampaignRecord,
    CampaignService,
    ExperimentRecord,
    ProjectDefinition,
    ProjectRecord,
    SeedPolicy,
    SweepPoint,
    accepted_core_execution_identity,
    create_project,
    execution_identity_sha256,
)

FIXTURE = Path("experiments/producer.yaml")
MEMORY_LIMIT_BYTES = 8 * 1024**3


def _definition(
    campaign_ids: tuple[str, ...] = ("campaign-a",),
    *,
    fixture: Path = FIXTURE,
) -> ProjectDefinition:
    fixture_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
    return ProjectDefinition(
        schema_version=2,
        project=ProjectRecord(
            schema_version=1,
            project_id="portable-queue-project",
            title="Portable queue intent software-validation project",
            description="Manufactured execution only; no biological conclusion.",
        ),
        experiments=[
            ExperimentRecord(
                schema_version=1,
                experiment_id="accepted-producer",
                title="Accepted producer fixture",
                fixture_file=str(fixture),
                fixture_sha256=fixture_hash,
                calibration_status="CALIBRATION_REQUIRED",
                notes="Preserves the accepted fixture and calibration boundary.",
            )
        ],
        campaigns=[
            CampaignRecord(
                schema_version=1,
                campaign_id=campaign_id,
                experiment_id="accepted-producer",
                title=f"Portable campaign {campaign_id}",
                replicate_count=1,
                seed_policy=SeedPolicy(kind="explicit", seeds=[41]),
                sweep_matrix=[
                    SweepPoint(point_id="producer-point", condition_id="producer")
                ],
            )
            for campaign_id in campaign_ids
        ],
        execution_identity=accepted_core_execution_identity(Path.cwd()),
    )


def _project(tmp_path: Path, definition: ProjectDefinition) -> Path:
    definition_file = tmp_path / "definition.json"
    definition_file.write_text(
        definition.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return create_project(definition_file, tmp_path / "project")


def _queue(tmp_path: Path, name: str, *, memory: int = MEMORY_LIMIT_BYTES) -> Path:
    return create_local_queue(
        tmp_path / name,
        cpu_cores=1,
        memory_limit_bytes=memory,
    )


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _write_queue_state(queue: Path, state: LocalQueueState) -> None:
    (queue / "queue_state.json").write_text(
        state.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )


def test_cli_exports_ordered_path_free_complete_intent_without_mutation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _project(tmp_path, _definition(("low", "high")))
    queue = _queue(tmp_path, "queue")
    service = LocalQueueService(queue)
    service.enqueue(project, "low", priority=1)
    service.enqueue(project, "high", priority=9)
    before_queue = _tree_bytes(queue)
    before_project = _tree_bytes(project)
    output = tmp_path / "intent.json"
    dry_output = tmp_path / "dry-intent.json"

    assert (
        main(
            [
                "queue",
                "export-intent",
                str(queue),
                "--output",
                str(dry_output),
                "--dry-run",
            ]
        )
        == 0
    )
    dry_receipt = json.loads(capsys.readouterr().out)
    assert dry_receipt["dry_run"] is True
    assert dry_receipt["manifest"] == str(dry_output)
    assert dry_receipt["item_count"] == 2
    assert not dry_output.exists()
    assert _tree_bytes(queue) == before_queue
    assert _tree_bytes(project) == before_project

    assert (
        main(["queue", "export-intent", str(queue), "--output", str(output)])
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    contents = output.read_bytes()
    assert receipt == {
        "item_count": 2,
        "manifest": str(output),
        "manifest_sha256": hashlib.sha256(contents).hexdigest(),
    }
    manifest = PortableQueueIntentManifest.model_validate_json(contents)
    assert main(["queue", "migration-status", str(output)]) == 0
    migration_status = json.loads(capsys.readouterr().out)
    assert migration_status["record_type"] == "PORTABLE_INTENT"
    assert migration_status["record_sha256"] == hashlib.sha256(contents).hexdigest()
    assert migration_status["item_count"] == 2
    assert migration_status["project_count"] == 1
    incompatible = tmp_path / "incompatible-intent.json"
    incompatible_payload = json.loads(contents)
    incompatible_payload["biomesh_version"] = "0.5.0"
    incompatible.write_text(
        json.dumps(incompatible_payload, separators=(",", ":"), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    assert main(["queue", "migration-status", str(incompatible)]) == 2
    assert "BioMesh version is incompatible" in capsys.readouterr().err
    assert [item.campaign.campaign_id for item in manifest.items] == ["high", "low"]
    assert [item.intent_sequence for item in manifest.items] == [0, 1]
    assert [item.priority for item in manifest.items] == [9, 1]
    assert manifest.items[0].campaign.sweep_matrix[0].condition_id == "producer"
    assert manifest.items[0].experiment.fixture_sha256 == hashlib.sha256(
        FIXTURE.read_bytes()
    ).hexdigest()
    identity = accepted_core_execution_identity(Path.cwd())
    assert manifest.items[0].execution_identity == identity
    assert manifest.items[0].execution_identity_sha256 == execution_identity_sha256(
        identity
    )
    assert manifest.items[0].source.project_definition_sha256 == hashlib.sha256(
        (project / "project.json").read_bytes()
    ).hexdigest()
    assert manifest.items[0].source.archive is None
    assert str(tmp_path).encode() not in contents
    payload = json.loads(contents)
    forbidden = {
        "applied_resources",
        "cancel_requested",
        "memory_limit_bytes",
        "project_directory",
        "queue_id",
        "resource_limits",
        "status",
        "worker_pid",
        "worker_start_ticks",
    }

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value))
        return set()

    assert keys(payload).isdisjoint(forbidden)
    assert _tree_bytes(queue) == before_queue
    assert _tree_bytes(project) == before_project


def test_equal_intent_is_byte_identical_despite_local_policy_and_history(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path, _definition(("ignored", "campaign-a")))
    first_queue = _queue(tmp_path, "first", memory=MEMORY_LIMIT_BYTES)
    second_queue = _queue(tmp_path, "second", memory=MEMORY_LIMIT_BYTES + 4096)
    first = LocalQueueService(first_queue)
    ignored = first.enqueue(project, "ignored", priority=100)
    first.cancel(ignored.queue_id)
    first.enqueue(project, "campaign-a", priority=3)
    LocalQueueService(second_queue).enqueue(project, "campaign-a", priority=3)

    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"
    export_portable_queue_intent(first_queue, first_output)
    export_portable_queue_intent(second_queue, second_output)
    assert first_output.read_bytes() == second_output.read_bytes()


def test_imported_archive_hash_and_status_are_provenance_without_trust(
    tmp_path: Path,
) -> None:
    source = _project(tmp_path, _definition())
    archive = tmp_path / "source.biomesh"
    exported = export_project_archive(source, archive)
    imported = tmp_path / "imported"
    import_project_archive(archive, imported, allow_unauthenticated=True)
    queue = _queue(tmp_path, "queue")
    LocalQueueService(queue).enqueue(imported, "campaign-a", priority=0)
    output = tmp_path / "intent.json"

    export_portable_queue_intent(queue, output)
    manifest = PortableQueueIntentManifest.model_validate_json(output.read_bytes())
    archive_source = manifest.items[0].source.archive
    assert archive_source is not None
    assert archive_source.payload_sha256 == exported.archive_sha256
    assert archive_source.envelope_sha256 == exported.archive_sha256
    assert archive_source.authenticity_status == "UNAUTHENTICATED"
    assert manifest.trust_policy == "source_archive_status_is_provenance_not_trust"


@pytest.mark.parametrize("live", [True, False], ids=["active", "stale"])
def test_active_or_stale_queue_item_fails_before_publication(
    tmp_path: Path, live: bool
) -> None:
    project = _project(tmp_path, _definition())
    queue = _queue(tmp_path, "queue")
    service = LocalQueueService(queue)
    item = service.enqueue(project, "campaign-a", priority=0)
    state_path = queue / "queue_state.json"
    state = LocalQueueState.model_validate_json(state_path.read_bytes())
    running = item.model_copy(
        update={
            "status": QueueItemStatus.RUNNING,
            "worker_pid": os.getpid() if live else 999_999_999,
            "worker_start_ticks": process_start_ticks(os.getpid()) if live else 1,
            "applied_resources": AppliedResourceLimits(
                cpu_ids=[min(os.sched_getaffinity(0))],
                memory_limit_bytes=MEMORY_LIMIT_BYTES,
            ),
        }
    )
    _write_queue_state(state_path.parent, state.model_copy(update={"items": [running]}))
    queue_before = _tree_bytes(queue)
    project_before = _tree_bytes(project)
    output = tmp_path / "intent.json"

    message = "active item" if live else "stale running item"
    with pytest.raises(PortableQueueIntentError, match=message):
        export_portable_queue_intent(queue, output)
    assert not output.exists()
    assert _tree_bytes(queue) == queue_before
    assert _tree_bytes(project) == project_before


def test_missing_symlinked_drifted_and_ambiguous_references_fail_closed(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    source = _project(source_root, _definition())
    archive = tmp_path / "source.biomesh"
    export_project_archive(source, archive)
    project = tmp_path / "project"
    import_project_archive(archive, project, allow_unauthenticated=True)
    imported_definition = ProjectDefinition.model_validate_json(
        (project / "project.json").read_bytes()
    )
    local_fixture = project / imported_definition.experiments[0].fixture_file
    queue = _queue(tmp_path, "queue")
    item = LocalQueueService(queue).enqueue(project, "campaign-a", priority=0)
    original = LocalQueueState.model_validate_json(
        (queue / "queue_state.json").read_bytes()
    )

    missing = item.model_copy(
        update={"project_directory": str(tmp_path / "missing-project")}
    )
    _write_queue_state(queue, original.model_copy(update={"items": [missing]}))
    with pytest.raises(PortableQueueIntentError, match="unavailable|missing"):
        export_portable_queue_intent(queue, tmp_path / "missing.json")

    symlink = tmp_path / "project-link"
    symlink.symlink_to(project, target_is_directory=True)
    linked = item.model_copy(update={"project_directory": str(symlink)})
    _write_queue_state(queue, original.model_copy(update={"items": [linked]}))
    with pytest.raises(PortableQueueIntentError, match="symlinked"):
        export_portable_queue_intent(queue, tmp_path / "symlink.json")

    queue_link = tmp_path / "queue-link"
    queue_link.symlink_to(queue, target_is_directory=True)
    with pytest.raises(PortableQueueIntentError, match="symlinked"):
        LocalQueueService(queue_link).export_intent(tmp_path / "queue-link.json")

    _write_queue_state(queue, original)
    local_fixture.write_bytes(local_fixture.read_bytes() + b"\n# drift\n")
    with pytest.raises(PortableQueueIntentError, match="fixture drifted"):
        export_portable_queue_intent(queue, tmp_path / "drift.json")
    local_fixture.write_bytes(FIXTURE.read_bytes())

    duplicate = item.model_copy(
        update={"queue_id": "queue-00000001-campaign-a", "enqueue_sequence": 1}
    )
    ambiguous = original.model_copy(
        update={"items": [item, duplicate], "next_sequence": 2}
    )
    _write_queue_state(queue, ambiguous)
    with pytest.raises(PortableQueueIntentError, match="ambiguous campaign"):
        export_portable_queue_intent(queue, tmp_path / "ambiguous.json")
    assert not (tmp_path / "missing.json").exists()
    assert not (tmp_path / "symlink.json").exists()
    assert not (tmp_path / "drift.json").exists()
    assert not (tmp_path / "ambiguous.json").exists()
    assert not (tmp_path / "queue-link.json").exists()


def test_project_activity_stale_campaign_and_publication_failure_are_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path, _definition())
    queue = _queue(tmp_path, "queue")
    LocalQueueService(queue).enqueue(project, "campaign-a", priority=0)
    output = tmp_path / "intent.json"

    with (project / ".campaign.lock").open("r+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(PortableQueueIntentError, match="active"):
            export_portable_queue_intent(queue, output)
    assert not output.exists()

    queue_before = _tree_bytes(queue)
    project_before = _tree_bytes(project)

    def fail_publication(_path: Path, _contents: bytes) -> None:
        raise OSError("synthetic publication failure")

    monkeypatch.setattr(
        "biomesh.portable_queue_intent._publish_manifest", fail_publication
    )
    with pytest.raises(PortableQueueIntentError, match="synthetic publication failure"):
        export_portable_queue_intent(queue, output)
    assert not output.exists()
    assert _tree_bytes(queue) == queue_before
    assert _tree_bytes(project) == project_before
    monkeypatch.undo()

    CampaignService(project).resume("campaign-a")
    stale_queue_before = _tree_bytes(queue)
    completed_before = _tree_bytes(project)
    with pytest.raises(PortableQueueIntentError, match="stale with no pending"):
        export_portable_queue_intent(queue, output)
    assert not output.exists()
    assert _tree_bytes(queue) == stale_queue_before
    assert _tree_bytes(project) == completed_before


def test_strict_schema_rejects_live_state_fields_and_existing_output(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path, _definition())
    queue = _queue(tmp_path, "queue")
    LocalQueueService(queue).enqueue(project, "campaign-a", priority=0)
    output = tmp_path / "intent.json"
    export_portable_queue_intent(queue, output)
    payload = json.loads(output.read_bytes())
    payload["items"][0]["worker_pid"] = 123
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PortableQueueIntentManifest.model_validate(payload)
    original = output.read_bytes()
    with pytest.raises(PortableQueueIntentError, match="already exists"):
        export_portable_queue_intent(queue, output)
    assert output.read_bytes() == original
