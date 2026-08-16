"""Focused P6-WP02 import, rebinding, and application-path tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from biomesh.__main__ import main
from biomesh.local_queue import LocalQueueService
from biomesh.local_queue_storage import create_local_queue
from biomesh.local_queue_types import LocalQueueError
from biomesh.portable_project import export_project_archive, import_project_archive
from biomesh.portable_queue_import import (
    bind_portable_queue_intent,
    import_portable_queue_intent,
    parse_project_path_binding,
)
from biomesh.portable_queue_import_types import (
    PortableQueueBindingRecord,
    PortableQueueImportError,
    PortableQueueImportRecord,
)
from biomesh.portable_queue_intent import export_portable_queue_intent
from biomesh.portable_queue_intent_types import (
    PortableQueueIntentManifest,
    portable_queue_intent_bytes,
)
from biomesh.project_campaign import (
    CampaignRecord,
    ExperimentRecord,
    ProjectDefinition,
    ProjectRecord,
    SeedPolicy,
    SweepPoint,
    accepted_core_execution_identity,
    create_project,
)

FIXTURE = Path("experiments/producer.yaml")
MEMORY_LIMIT_BYTES = 8 * 1024**3


def _definition(
    project_id: str = "portable-import-project",
    campaign_ids: tuple[str, ...] = ("campaign-a",),
) -> ProjectDefinition:
    return ProjectDefinition(
        schema_version=2,
        project=ProjectRecord(
            schema_version=1,
            project_id=project_id,
            title=f"Portable import project {project_id}",
            description="Manufactured software validation only.",
        ),
        experiments=[
            ExperimentRecord(
                schema_version=1,
                experiment_id="accepted-producer",
                title="Accepted producer fixture",
                fixture_file=str(FIXTURE),
                fixture_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
                calibration_status="CALIBRATION_REQUIRED",
                notes="No calibration or scientific conclusion.",
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


def _project(tmp_path: Path, definition: ProjectDefinition, name: str) -> Path:
    definition_file = tmp_path / f"{name}-definition.json"
    definition_file.write_text(
        definition.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return create_project(definition_file, tmp_path / name)


def _manifest(
    tmp_path: Path,
    projects: tuple[tuple[Path, str, int], ...],
) -> tuple[Path, Path]:
    queue = create_local_queue(
        tmp_path / "source-queue",
        cpu_cores=1,
        memory_limit_bytes=MEMORY_LIMIT_BYTES,
    )
    service = LocalQueueService(queue)
    for project, campaign_id, priority in projects:
        service.enqueue(project, campaign_id, priority=priority)
    manifest = tmp_path / "portable-intent.json"
    export_portable_queue_intent(queue, manifest)
    return queue, manifest


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_all_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_all_keys(item) for item in value))
    return set()


def test_cli_import_and_complete_binding_preserve_intent_without_runnable_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _project(
        tmp_path,
        _definition(campaign_ids=("low", "high")),
        "project",
    )
    queue, manifest = _manifest(
        tmp_path,
        ((project, "low", 1), (project, "high", 9)),
    )
    queue_before = _tree_bytes(queue)
    project_before = _tree_bytes(project)
    manifest_before = manifest.read_bytes()
    imported_path = tmp_path / "imported-intent.json"
    dry_imported_path = tmp_path / "dry-imported-intent.json"

    assert (
        main(
            [
                "queue",
                "import-intent",
                str(manifest),
                "--output",
                str(dry_imported_path),
                "--dry-run",
            ]
        )
        == 0
    )
    dry_import_receipt = json.loads(capsys.readouterr().out)
    assert dry_import_receipt["dry_run"] is True
    assert dry_import_receipt["import_record"] == str(dry_imported_path.resolve())
    assert not dry_imported_path.exists()
    assert manifest.read_bytes() == manifest_before
    assert _tree_bytes(queue) == queue_before
    assert _tree_bytes(project) == project_before

    assert (
        main(
            [
                "queue",
                "import-intent",
                str(manifest),
                "--output",
                str(imported_path),
            ]
        )
        == 0
    )
    import_receipt = json.loads(capsys.readouterr().out)
    imported_bytes = imported_path.read_bytes()
    imported = PortableQueueImportRecord.model_validate_json(imported_bytes)
    assert import_receipt == {
        "import_record": str(imported_path.resolve()),
        "import_sha256": hashlib.sha256(imported_bytes).hexdigest(),
        "item_count": 2,
        "manifest_sha256": hashlib.sha256(manifest_before).hexdigest(),
    }
    assert [item.status for item in imported.items] == ["UNBOUND", "UNBOUND"]
    assert [item.intent.campaign.campaign_id for item in imported.items] == [
        "high",
        "low",
    ]
    assert [item.intent.priority for item in imported.items] == [9, 1]
    assert imported.source_manifest_sha256 == hashlib.sha256(
        manifest_before
    ).hexdigest()
    assert main(["queue", "migration-status", str(imported_path)]) == 0
    import_status = json.loads(capsys.readouterr().out)
    assert import_status == {
        "biomesh_version": imported.source_manifest.biomesh_version,
        "item_count": 2,
        "project_count": 1,
        "record_sha256": hashlib.sha256(imported_bytes).hexdigest(),
        "record_type": "UNBOUND_IMPORT",
        "schema_version": 1,
    }

    bound_path = tmp_path / "bound-intent.json"
    dry_bound_path = tmp_path / "dry-bound-intent.json"
    binding_arguments = [
        "--project-binding",
        f"portable-import-project={project.resolve()}",
        "--cpu-cores",
        "1",
        "--memory-limit-bytes",
        str(MEMORY_LIMIT_BYTES + 4096),
    ]
    assert (
        main(
            [
                "queue",
                "bind-intent",
                str(imported_path),
                "--output",
                str(dry_bound_path),
                *binding_arguments,
                "--dry-run",
            ]
        )
        == 0
    )
    dry_binding_receipt = json.loads(capsys.readouterr().out)
    assert dry_binding_receipt["dry_run"] is True
    assert dry_binding_receipt["binding_record"] == str(dry_bound_path.resolve())
    assert not dry_bound_path.exists()
    assert imported_path.read_bytes() == imported_bytes
    assert _tree_bytes(queue) == queue_before
    assert _tree_bytes(project) == project_before

    assert (
        main(
            [
                "queue",
                "bind-intent",
                str(imported_path),
                "--output",
                str(bound_path),
                *binding_arguments,
            ]
        )
        == 0
    )
    binding_receipt = json.loads(capsys.readouterr().out)
    bound_bytes = bound_path.read_bytes()
    bound = PortableQueueBindingRecord.model_validate_json(bound_bytes)
    assert binding_receipt == {
        "binding_record": str(bound_path.resolve()),
        "binding_sha256": hashlib.sha256(bound_bytes).hexdigest(),
        "item_count": 2,
        "project_count": 1,
    }
    assert [item.status for item in bound.items] == [
        "BOUND_NONRUNNABLE",
        "BOUND_NONRUNNABLE",
    ]
    assert [item.intent for item in bound.items] == imported.source_manifest.items
    assert bound.local_resource_limits.memory_limit_bytes == MEMORY_LIMIT_BYTES + 4096
    assert bound.projects[0].destination_archive_trust == "NOT_GRANTED"
    assert bound.projects[0].destination_plugin_trust == "NOT_GRANTED"
    assert bound.projects[0].destination_registry_trust == "NOT_GRANTED"
    assert bound.projects[0].destination_authorization == "NOT_GRANTED"
    assert bound.projects[0].destination_calibration_status == "CALIBRATION_REQUIRED"
    assert main(["queue", "migration-status", str(bound_path)]) == 0
    binding_status = json.loads(capsys.readouterr().out)
    assert binding_status["record_type"] == "BOUND_NONRUNNABLE"
    assert binding_status["record_sha256"] == hashlib.sha256(bound_bytes).hexdigest()
    assert binding_status["item_count"] == 2
    assert binding_status["project_count"] == 1
    forbidden = {
        "applied_resources",
        "cancel_requested",
        "enqueue_sequence",
        "failure",
        "queue_id",
        "worker_pid",
        "worker_start_ticks",
    }
    assert _all_keys(json.loads(bound_bytes)).isdisjoint(forbidden)
    with pytest.raises(LocalQueueError, match="not a BioMesh local queue"):
        LocalQueueService(bound_path).status()
    assert manifest.read_bytes() == manifest_before
    assert imported_path.read_bytes() == imported_bytes
    assert _tree_bytes(queue) == queue_before
    assert _tree_bytes(project) == project_before


def test_import_rejects_noncanonical_incompatible_and_live_state_fields_atomically(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path, _definition(), "project")
    _, manifest = _manifest(tmp_path, ((project, "campaign-a", 0),))
    payload = json.loads(manifest.read_bytes())

    incompatible = tmp_path / "incompatible.json"
    payload["schema_version"] = 2
    incompatible.write_text(
        json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
    )
    with pytest.raises(
        PortableQueueImportError, match="schema_version|Input should be 1"
    ):
        import_portable_queue_intent(
            incompatible, tmp_path / "incompatible-import.json"
        )
    assert not (tmp_path / "incompatible-import.json").exists()

    forbidden = tmp_path / "forbidden.json"
    payload["schema_version"] = 1
    payload["items"][0]["queue_id"] = "transported-old-id"
    forbidden.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(PortableQueueImportError, match="Extra inputs"):
        import_portable_queue_intent(forbidden, tmp_path / "forbidden-import.json")
    assert not (tmp_path / "forbidden-import.json").exists()

    noncanonical = tmp_path / "noncanonical.json"
    clean_payload = json.loads(manifest.read_bytes())
    noncanonical.write_text(
        json.dumps(clean_payload, indent=2) + "\n", encoding="utf-8"
    )
    with pytest.raises(PortableQueueImportError, match="canonical P6-WP01"):
        import_portable_queue_intent(
            noncanonical, tmp_path / "noncanonical-import.json"
        )
    assert not (tmp_path / "noncanonical-import.json").exists()

    existing = tmp_path / "existing.json"
    existing.write_bytes(b"preserve-me")
    with pytest.raises(PortableQueueImportError, match="already exists"):
        import_portable_queue_intent(manifest, existing)
    assert existing.read_bytes() == b"preserve-me"

    ambiguous_root = tmp_path / "ambiguous-source"
    ambiguous_root.mkdir()
    first = _project(
        ambiguous_root, _definition("ambiguous-one"), "ambiguous-one"
    )
    second = _project(
        ambiguous_root, _definition("ambiguous-two"), "ambiguous-two"
    )
    _, two_project_manifest = _manifest(
        ambiguous_root,
        ((first, "campaign-a", 2), (second, "campaign-a", 1)),
    )
    ambiguous_payload = json.loads(two_project_manifest.read_bytes())
    ambiguous_payload["items"][1]["project_id"] = "ambiguous-one"
    ambiguous_manifest = PortableQueueIntentManifest.model_validate(
        ambiguous_payload
    )
    ambiguous_path = ambiguous_root / "ambiguous-intent.json"
    ambiguous_path.write_bytes(portable_queue_intent_bytes(ambiguous_manifest))
    ambiguous_output = ambiguous_root / "ambiguous-import.json"
    with pytest.raises(PortableQueueImportError, match="ambiguous source project"):
        import_portable_queue_intent(ambiguous_path, ambiguous_output)
    assert not ambiguous_output.exists()


def test_binding_requires_one_complete_unambiguous_safe_project_set(
    tmp_path: Path,
) -> None:
    first = _project(tmp_path, _definition("project-one"), "project-one")
    second = _project(tmp_path, _definition("project-two"), "project-two")
    _, manifest = _manifest(
        tmp_path,
        ((first, "campaign-a", 2), (second, "campaign-a", 1)),
    )
    imported = tmp_path / "imported.json"
    import_portable_queue_intent(manifest, imported)

    with pytest.raises(PortableQueueImportError, match="complete exact set"):
        bind_portable_queue_intent(
            imported,
            tmp_path / "partial.json",
            project_bindings=[
                parse_project_path_binding(f"project-one={first.resolve()}")
            ],
            cpu_cores=1,
            memory_limit_bytes=MEMORY_LIMIT_BYTES,
        )
    assert not (tmp_path / "partial.json").exists()

    duplicate = parse_project_path_binding(f"project-one={first.resolve()}")
    with pytest.raises(PortableQueueImportError, match="duplicate"):
        bind_portable_queue_intent(
            imported,
            tmp_path / "duplicate.json",
            project_bindings=[duplicate, duplicate],
            cpu_cores=1,
            memory_limit_bytes=MEMORY_LIMIT_BYTES,
        )
    assert not (tmp_path / "duplicate.json").exists()

    with pytest.raises(PortableQueueImportError, match="traversal-free"):
        parse_project_path_binding("project-one=/tmp/source/../project")
    with pytest.raises(PortableQueueImportError, match="unsafe path components"):
        parse_project_path_binding("project-one=/tmp/source/./project")

    link = tmp_path / "project-link"
    link.symlink_to(first, target_is_directory=True)
    with pytest.raises(PortableQueueImportError, match="symlinked"):
        bind_portable_queue_intent(
            imported,
            tmp_path / "symlink.json",
            project_bindings=[
                parse_project_path_binding(f"project-one={link.absolute()}"),
                parse_project_path_binding(f"project-two={second.resolve()}"),
            ],
            cpu_cores=1,
            memory_limit_bytes=MEMORY_LIMIT_BYTES,
        )
    assert not (tmp_path / "symlink.json").exists()

    with pytest.raises(PortableQueueImportError, match="outside bound projects"):
        bind_portable_queue_intent(
            imported,
            first / "binding.json",
            project_bindings=[
                parse_project_path_binding(f"project-one={first.resolve()}"),
                parse_project_path_binding(f"project-two={second.resolve()}"),
            ],
            cpu_cores=1,
            memory_limit_bytes=MEMORY_LIMIT_BYTES,
        )
    assert not (first / "binding.json").exists()


def test_missing_drifted_and_conflicting_binding_targets_fail_without_publication(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path, _definition(), "project")
    _, manifest = _manifest(tmp_path, ((project, "campaign-a", 0),))
    imported = tmp_path / "imported.json"
    import_portable_queue_intent(manifest, imported)

    missing = tmp_path / "missing-project"
    with pytest.raises(PortableQueueImportError, match="unavailable|missing"):
        bind_portable_queue_intent(
            imported,
            tmp_path / "missing.json",
            project_bindings=[
                parse_project_path_binding(
                    f"portable-import-project={missing.resolve()}"
                )
            ],
            cpu_cores=1,
            memory_limit_bytes=MEMORY_LIMIT_BYTES,
        )
    assert not (tmp_path / "missing.json").exists()

    definition_path = project / "project.json"
    definition_path.write_bytes(definition_path.read_bytes() + b" ")
    with pytest.raises(PortableQueueImportError, match="definition|state"):
        bind_portable_queue_intent(
            imported,
            tmp_path / "drifted.json",
            project_bindings=[
                parse_project_path_binding(
                    f"portable-import-project={project.resolve()}"
                )
            ],
            cpu_cores=1,
            memory_limit_bytes=MEMORY_LIMIT_BYTES,
        )
    assert not (tmp_path / "drifted.json").exists()

    existing = tmp_path / "bound-existing.json"
    existing.write_bytes(b"preserve-bound-target")
    with pytest.raises(PortableQueueImportError, match="already exists"):
        bind_portable_queue_intent(
            imported,
            existing,
            project_bindings=[
                parse_project_path_binding(
                    f"portable-import-project={project.resolve()}"
                )
            ],
            cpu_cores=1,
            memory_limit_bytes=MEMORY_LIMIT_BYTES,
        )
    assert existing.read_bytes() == b"preserve-bound-target"


def test_archive_provenance_is_retained_but_never_promoted_to_local_trust(
    tmp_path: Path,
) -> None:
    source = _project(tmp_path, _definition(), "source")
    archive = tmp_path / "source.biomesh"
    exported = export_project_archive(source, archive)
    project = tmp_path / "imported-project"
    import_project_archive(archive, project, allow_unauthenticated=True)
    _, manifest = _manifest(tmp_path, ((project, "campaign-a", 0),))
    imported = tmp_path / "imported.json"
    import_portable_queue_intent(manifest, imported)
    bound_path = tmp_path / "bound.json"

    bind_portable_queue_intent(
        imported,
        bound_path,
        project_bindings=[
            parse_project_path_binding(f"portable-import-project={project.resolve()}")
        ],
        cpu_cores=1,
        memory_limit_bytes=MEMORY_LIMIT_BYTES,
    )
    bound = PortableQueueBindingRecord.model_validate_json(bound_path.read_bytes())
    source_archive = bound.projects[0].source_archive
    assert source_archive is not None
    assert source_archive.payload_sha256 == exported.archive_sha256
    assert source_archive.authenticity_status == "UNAUTHENTICATED"
    assert bound.projects[0].destination_archive_trust == "NOT_GRANTED"
    assert bound.trust_policy == "no_destination_trust_granted"


def test_equal_import_and_binding_are_byte_deterministic(tmp_path: Path) -> None:
    project = _project(tmp_path, _definition(), "project")
    _, manifest = _manifest(tmp_path, ((project, "campaign-a", 3),))
    first_import = tmp_path / "first-import.json"
    second_import = tmp_path / "second-import.json"
    import_portable_queue_intent(manifest, first_import)
    import_portable_queue_intent(manifest, second_import)
    assert first_import.read_bytes() == second_import.read_bytes()
    binding = parse_project_path_binding(
        f"portable-import-project={project.resolve()}"
    )
    first_bound = tmp_path / "first-bound.json"
    second_bound = tmp_path / "second-bound.json"
    bind_portable_queue_intent(
        first_import,
        first_bound,
        project_bindings=[binding],
        cpu_cores=1,
        memory_limit_bytes=MEMORY_LIMIT_BYTES,
    )
    bind_portable_queue_intent(
        second_import,
        second_bound,
        project_bindings=[binding],
        cpu_cores=1,
        memory_limit_bytes=MEMORY_LIMIT_BYTES,
    )
    assert first_bound.read_bytes() == second_bound.read_bytes()


def test_changed_during_validation_inputs_fail_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path, _definition(), "project")
    _, manifest = _manifest(tmp_path, ((project, "campaign-a", 0),))
    real_read = __import__(
        "biomesh.portable_queue_import", fromlist=["_read_stable_regular_file"]
    )._read_stable_regular_file
    manifest_reads = 0

    def changed_manifest(path: Path, *, label: str) -> bytes:
        nonlocal manifest_reads
        contents = real_read(path, label=label)
        if path == manifest.resolve():
            manifest_reads += 1
            if manifest_reads == 3:
                return contents + b" "
        return contents

    monkeypatch.setattr(
        "biomesh.portable_queue_import._read_stable_regular_file",
        changed_manifest,
    )
    with pytest.raises(PortableQueueImportError, match="changed during"):
        import_portable_queue_intent(manifest, tmp_path / "changed-import.json")
    assert not (tmp_path / "changed-import.json").exists()
    monkeypatch.undo()

    imported = tmp_path / "imported.json"
    import_portable_queue_intent(manifest, imported)
    state_path = (project / "campaign_state.json").resolve()
    state_reads = 0

    def changed_project(path: Path, *, label: str) -> bytes:
        nonlocal state_reads
        contents = real_read(path, label=label)
        if path == state_path:
            state_reads += 1
            if state_reads == 2:
                return contents + b" "
        return contents

    monkeypatch.setattr(
        "biomesh.portable_queue_import._read_stable_regular_file",
        changed_project,
    )
    with pytest.raises(PortableQueueImportError, match="changed during"):
        bind_portable_queue_intent(
            imported,
            tmp_path / "changed-bound.json",
            project_bindings=[
                parse_project_path_binding(
                    f"portable-import-project={project.resolve()}"
                )
            ],
            cpu_cores=1,
            memory_limit_bytes=MEMORY_LIMIT_BYTES,
        )
    assert not (tmp_path / "changed-bound.json").exists()


def test_publication_failure_preserves_sources_and_leaves_no_partial_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path, _definition(), "project")
    queue, manifest = _manifest(tmp_path, ((project, "campaign-a", 0),))
    queue_before = _tree_bytes(queue)
    project_before = _tree_bytes(project)
    manifest_before = manifest.read_bytes()

    def fail_publication(_path: Path, _contents: bytes, *, label: str) -> None:
        raise OSError(f"synthetic {label} publication failure")

    monkeypatch.setattr(
        "biomesh.portable_queue_import._publish_new_file", fail_publication
    )
    output = tmp_path / "failed-import.json"
    with pytest.raises(OSError, match="synthetic portable queue import"):
        import_portable_queue_intent(manifest, output)
    assert not output.exists()
    assert manifest.read_bytes() == manifest_before
    assert _tree_bytes(queue) == queue_before
    assert _tree_bytes(project) == project_before
