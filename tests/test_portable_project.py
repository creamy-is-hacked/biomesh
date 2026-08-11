"""Focused P4-WP06 portable-project archive tests."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from biomesh.__main__ import main
from biomesh.portable_project import (
    export_project_archive,
    import_project_archive,
    verify_project_archive,
)
from biomesh.portable_project_types import PortableArchiveError
from biomesh.project_campaign import (
    CampaignRecord,
    CampaignService,
    ExperimentRecord,
    ProjectDefinition,
    ProjectRecord,
    RunExecutionRequest,
    SeedPolicy,
    SweepPoint,
    create_project,
)

FIXTURE = Path("experiments/producer.yaml")


def _definition() -> ProjectDefinition:
    return ProjectDefinition(
        schema_version=1,
        project=ProjectRecord(
            schema_version=1,
            project_id="portable-project",
            title="Portable manufactured validation project",
            description="Software validation only; no biological conclusion.",
        ),
        experiments=[
            ExperimentRecord(
                schema_version=1,
                experiment_id="accepted-producer",
                title="Accepted producer fixture",
                fixture_file=str(FIXTURE.resolve()),
                fixture_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
                calibration_status="CALIBRATION_REQUIRED",
                notes="Preserves the accepted zero-plugin fixture path.",
            )
        ],
        campaigns=[
            CampaignRecord(
                schema_version=1,
                campaign_id="completed-campaign",
                experiment_id="accepted-producer",
                title="Completed compact result",
                replicate_count=1,
                seed_policy=SeedPolicy(kind="explicit", seeds=[101]),
                sweep_matrix=[
                    SweepPoint(point_id="producer-point", condition_id="producer")
                ],
            ),
            CampaignRecord(
                schema_version=1,
                campaign_id="pending-campaign",
                experiment_id="accepted-producer",
                title="Pending clean-install reproduction",
                replicate_count=1,
                seed_policy=SeedPolicy(kind="explicit", seeds=[202]),
                sweep_matrix=[
                    SweepPoint(point_id="producer-point", condition_id="producer")
                ],
            ),
        ],
    )


def _project(tmp_path: Path) -> Path:
    definition_file = tmp_path / "definition.json"
    definition_file.write_text(
        _definition().model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    project = create_project(definition_file, tmp_path / "project")

    def executor(request: RunExecutionRequest, output: Path) -> None:
        (output / "compact.json").write_text(
            json.dumps(
                {
                    "calibration_status": "CALIBRATION_REQUIRED",
                    "run_id": request.run.run_id,
                    "seed": request.run.seed,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    status = CampaignService(project, executor=executor).resume("completed-campaign")
    assert status.completed == 1
    return project


def test_archive_is_deterministic_self_describing_and_importable(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    source_manifest = (project / "project.json").read_bytes()
    source_state = (project / "campaign_state.json").read_bytes()
    first = tmp_path / "first.biomesh"
    second = tmp_path / "second.biomesh"

    first_result = export_project_archive(project, first)
    second_result = export_project_archive(project, second)
    assert first.read_bytes() == second.read_bytes()
    assert first_result.archive_sha256 == second_result.archive_sha256
    assert first_result.completed_run_count == 1
    assert (project / "project.json").read_bytes() == source_manifest
    assert (project / "campaign_state.json").read_bytes() == source_state

    with zipfile.ZipFile(first) as archive:
        archive_manifest = json.loads(archive.read("archive.json"))
        portable_definition = json.loads(archive.read("project/project.json"))
        names = set(archive.namelist())
    assert archive_manifest["plugin_policy"] == "no_plugins_embedded_or_trusted"
    assert archive_manifest["registry_policy"] == (
        "no_registry_embedded_or_reidentified"
    )
    assert archive_manifest["queue_policy"] == (
        "queue_state_not_embedded_reenqueue_after_import"
    )
    fixture_label = portable_definition["experiments"][0]["fixture_file"]
    assert fixture_label.startswith("fixtures/accepted-producer-")
    assert f"project/{fixture_label}" in names
    assert not any("queue_state.json" in name for name in names)

    verified = verify_project_archive(first)
    assert verified.archive_sha256 == first_result.archive_sha256
    imported = tmp_path / "imported"
    import_result = import_project_archive(first, imported)
    assert import_result.completed_run_count == 1
    assert CampaignService(imported).status("completed-campaign").completed == 1
    assert CampaignService(imported).status("pending-campaign").pending == 1
    original_result = next((project / "artifacts").glob("*/compact.json"))
    imported_result = next((imported / "artifacts").glob("*/compact.json"))
    assert imported_result.read_bytes() == original_result.read_bytes()


def test_checksums_detect_repacked_member_corruption(tmp_path: Path) -> None:
    project = _project(tmp_path)
    archive_path = tmp_path / "project.biomesh"
    export_project_archive(project, archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    target = next(name for name in members if name.endswith("compact.json"))
    members[target] = members[target] + b"corruption"
    corrupt = tmp_path / "corrupt.biomesh"
    with zipfile.ZipFile(corrupt, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)

    with pytest.raises(PortableArchiveError, match="size mismatch|checksum mismatch"):
        verify_project_archive(corrupt)


def test_archive_cross_checks_results_against_campaign_state(tmp_path: Path) -> None:
    project = _project(tmp_path)
    archive_path = tmp_path / "project.biomesh"
    export_project_archive(project, archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}

    target = next(name for name in members if name.endswith("compact.json"))
    members[target] = members[target] + b"replaced"
    manifest = json.loads(members["archive.json"])
    record = next(item for item in manifest["files"] if item["path"] == target)
    record["size_bytes"] = len(members[target])
    record["sha256"] = hashlib.sha256(members[target]).hexdigest()
    members["archive.json"] = (
        json.dumps(manifest, indent=2, separators=(",", ":")) + "\n"
    ).encode()

    altered = tmp_path / "altered.biomesh"
    with zipfile.ZipFile(altered, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)
    with pytest.raises(PortableArchiveError, match="artifact identity mismatch"):
        verify_project_archive(altered)


def test_archive_rejects_unsafe_members_and_existing_import_target(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    archive_path = tmp_path / "project.biomesh"
    export_project_archive(project, archive_path)
    unsafe = tmp_path / "unsafe.biomesh"
    with zipfile.ZipFile(archive_path) as source, zipfile.ZipFile(
        unsafe, mode="w", compression=zipfile.ZIP_STORED
    ) as target:
        for name in source.namelist():
            target.writestr(name, source.read(name))
        target.writestr("../escaped", b"unsafe")
    with pytest.raises(PortableArchiveError, match="contained under project"):
        verify_project_archive(unsafe)

    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(PortableArchiveError, match="already exists"):
        import_project_archive(archive_path, existing)


def test_project_archive_cli_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _project(tmp_path)
    archive_path = tmp_path / "cli.biomesh"
    assert main(
        ["project", "export", str(project), "--output", str(archive_path)]
    ) == 0
    assert json.loads(capsys.readouterr().out)["completed_run_count"] == 1
    assert main(["project", "verify-archive", str(archive_path)]) == 0
    assert json.loads(capsys.readouterr().out)["file_count"] >= 5
    imported = tmp_path / "cli-imported"
    assert main(["project", "import", str(archive_path), str(imported)]) == 0
    assert json.loads(capsys.readouterr().out)["project_id"] == "portable-project"
