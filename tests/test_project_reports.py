"""Focused P4-WP02 comparison, traceability, and report-path tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from biomesh.__main__ import main
from biomesh.p2_campaign import resolve_application_run
from biomesh.project_campaign import (
    CampaignRecord,
    CampaignService,
    ExperimentRecord,
    ProjectCampaignError,
    ProjectDefinition,
    ProjectRecord,
    RunExecutionRequest,
    SeedPolicy,
    SweepPoint,
    create_project,
)
from biomesh.project_reports import generate_campaign_report

FIXTURE = Path("experiments/qs_threshold_sweep.yaml")


def _definition(*, replicate_count: int = 2) -> ProjectDefinition:
    points = []
    for condition_id in ("qs-low", "qs-high"):
        resolved = resolve_application_run(
            fixture_file=FIXTURE, condition_id=condition_id, seed=1
        )
        points.append(
            SweepPoint(
                point_id=f"point-{condition_id}",
                condition_id=condition_id,
                parameters=list(resolved.request.condition.parameter_overrides),
            )
        )
    return ProjectDefinition(
        schema_version=1,
        project=ProjectRecord(
            schema_version=1,
            project_id="comparison-project",
            title="Manufactured comparison project",
            description="Software validation only; no biological conclusion.",
        ),
        experiments=[
            ExperimentRecord(
                schema_version=1,
                experiment_id="accepted-qs",
                title="Accepted quorum-threshold fixture",
                fixture_file=str(FIXTURE),
                fixture_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
                calibration_status="CALIBRATION_REQUIRED",
                notes="Preserves the accepted P2/P3 fixture path.",
            )
        ],
        campaigns=[
            CampaignRecord(
                schema_version=1,
                campaign_id="comparison-campaign",
                experiment_id="accepted-qs",
                title="Two-condition comparison",
                replicate_count=replicate_count,
                seed_policy=SeedPolicy(kind="sequence", start=10, step=5),
                sweep_matrix=points,
            )
        ],
    )


def _create(tmp_path: Path, *, replicate_count: int = 2) -> Path:
    definition = _definition(replicate_count=replicate_count)
    definition_file = tmp_path / "definition.json"
    definition_file.write_text(
        definition.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return create_project(definition_file, tmp_path / "project")


def _write_table(path: Path, rows: dict[str, list[float | int]]) -> None:
    pq.write_table(pa.table(rows), path)


def _report_executor(request: RunExecutionRequest, output: Path) -> None:
    raw = output / "raw"
    raw.mkdir()
    condition_offset = 10.0 if request.run.condition_id == "qs-high" else 0.0
    seed_offset = request.run.seed / 100.0
    values = [condition_offset + seed_offset, condition_offset + seed_offset + 1.0]
    times = [0.0, 1.0]
    _write_table(
        raw / "summary.parquet",
        {
            "time_s": times,
            "total_dry_biomass_kg": values,
            "cell_count": [1, 2],
            "division_event_count": [0, 1],
            "biofilm_height_m": values,
            "biofilm_roughness_m": [0.0, 0.1],
        },
    )
    _write_table(
        raw / "eps_summary.parquet",
        {"time_s": times, "total_eps_kg": values},
    )
    _write_table(
        raw / "competition_summary.parquet",
        {
            "time_s": times,
            "producer_cell_frequency": [0.5, 0.5],
            "producer_biomass_frequency": [0.5, 0.5],
            "nearest_neighbor_segregation_fraction": [0.0, 0.0],
        },
    )
    _write_table(
        raw / "physiology_summary.parquet",
        {
            "time_s": times,
            "active_biomass_kg": values,
            "slow_biomass_kg": [0.0, 0.0],
            "dormant_biomass_kg": [0.0, 0.0],
            "dead_biomass_kg": [0.0, 0.0],
            "detached_biomass_kg": [0.0, 0.0],
        },
    )
    _write_table(
        raw / "shear_summary.parquet",
        {
            "time_s": times,
            "surface_parallel_shear_stress_pa": [0.0, 0.0],
            "detachment_rate_s": [0.0, 0.0],
        },
    )


def test_report_compares_replicates_with_raw_hash_and_row_traceability(
    tmp_path: Path,
) -> None:
    project = _create(tmp_path)
    status = CampaignService(project, executor=_report_executor).resume(
        "comparison-campaign"
    )
    assert (status.completed, status.failed) == (4, 0)
    state_before = (project / "campaign_state.json").read_bytes()

    result = generate_campaign_report(
        project, "comparison-campaign", tmp_path / "report"
    )
    assert result.completed_runs == 4
    assert result.missing_runs == 0
    assert result.comparison_rows > 0
    data = json.loads((result.output_directory / "report_data.json").read_text())
    summary = next(
        row
        for row in data["condition_summaries"]
        if row["point_id"] == "point-qs-low"
        and row["metric"] == "total_dry_biomass_kg"
        and row["time_s"] == 1.0
    )
    assert summary["observed_replicate_count"] == 2
    assert summary["missing_run_ids"] == []
    assert summary["claim_status"] == "REPLICATED"
    assert summary["confidence_interval_low"] is not None
    assert len(summary["distribution"]) == 2
    assert all(len(item["artifact_sha256"]) == 64 for item in summary["distribution"])
    assert all(item["row_index"] == 1 for item in summary["distribution"])

    comparison = next(
        row
        for row in data["pairwise_comparisons"]
        if row["metric"] == "total_dry_biomass_kg" and row["time_s"] == 1.0
    )
    assert comparison["effect_size"]["mean_difference"] == pytest.approx(-10.0)
    assert comparison["effect_size"]["standardized_value"] is not None
    assert comparison["uncertainty_status"] == "welch_student_t_95_percent"

    manifest = json.loads(
        (result.output_directory / "report_manifest.json").read_text()
    )
    for record in manifest["files"]:
        contents = (result.output_directory / record["path"]).read_bytes()
        assert len(contents) == record["size_bytes"]
        assert hashlib.sha256(contents).hexdigest() == record["sha256"]
    assert (project / "campaign_state.json").read_bytes() == state_before

    replay_root = tmp_path / "replay"
    replay_root.mkdir()
    replay_project = _create(replay_root)
    CampaignService(replay_project, executor=_report_executor).resume(
        "comparison-campaign"
    )
    replay_report = replay_root / "report"
    generate_campaign_report(replay_project, "comparison-campaign", replay_report)
    assert {
        path.relative_to(result.output_directory): path.read_bytes()
        for path in result.output_directory.iterdir()
    } == {
        path.relative_to(replay_report): path.read_bytes()
        for path in replay_report.iterdir()
    }


def test_missing_runs_and_single_seed_claims_remain_explicit(tmp_path: Path) -> None:
    project = _create(tmp_path, replicate_count=1)

    def fail_high(request: RunExecutionRequest, output: Path) -> None:
        if request.run.condition_id == "qs-high":
            raise RuntimeError("visible synthetic failure")
        _report_executor(request, output)

    status = CampaignService(project, executor=fail_high).resume("comparison-campaign")
    assert (status.completed, status.failed) == (1, 1)
    output = tmp_path / "partial-report"
    generate_campaign_report(project, "comparison-campaign", output)
    data = json.loads((output / "report_data.json").read_text())

    assert data["campaign"]["single_seed_warning"] is True
    assert data["campaign"]["missing_run_count"] == 1
    assert {item["code"] for item in data["warnings"]} == {
        "MISSING_RUNS",
        "SINGLE_SEED_CAMPAIGN",
    }
    assert [row["status"] for row in data["run_coverage"]] == [
        "completed",
        "failed",
    ]
    assert data["run_coverage"][1]["failure"]["message"] == (
        "visible synthetic failure"
    )
    assert data["condition_summaries"][0]["single_seed_warning"] is True
    assert data["condition_summaries"][0]["claim_status"] == "SINGLE_SEED_ONLY"
    assert data["condition_summaries"][0]["confidence_interval_low"] is None
    assert data["pairwise_comparisons"] == []


def test_report_fails_closed_on_raw_drift_and_atomic_generation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _create(tmp_path)
    CampaignService(project, executor=_report_executor).resume("comparison-campaign")
    state = json.loads((project / "campaign_state.json").read_text())
    run_id = state["runs"][0]["run_id"]
    raw_summary = project / "artifacts" / run_id / "raw" / "summary.parquet"
    raw_summary.write_bytes(raw_summary.read_bytes() + b"drift")
    with pytest.raises(ProjectCampaignError, match="artifact changed"):
        generate_campaign_report(project, "comparison-campaign", tmp_path / "drift")

    clean_root = tmp_path / "clean"
    clean_root.mkdir()
    clean_project = _create(clean_root)
    CampaignService(clean_project, executor=_report_executor).resume(
        "comparison-campaign"
    )
    monkeypatch.setattr(
        "biomesh.project_report_output._comparison_csv",
        lambda _rows: (_ for _ in ()).throw(RuntimeError("synthetic report failure")),
    )
    target = clean_root / "failed-report"
    with pytest.raises(RuntimeError, match="synthetic report failure"):
        generate_campaign_report(clean_project, "comparison-campaign", target)
    assert not target.exists()
    assert not list(clean_root.glob(".failed-report.*"))


def test_campaign_report_cli_path_publishes_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _create(tmp_path)
    CampaignService(project, executor=_report_executor).resume("comparison-campaign")
    output = tmp_path / "cli-report"
    assert (
        main(
            [
                "campaign",
                "report",
                str(project),
                "comparison-campaign",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    response = json.loads(capsys.readouterr().out)
    assert response["completed_runs"] == 4
    assert response["comparison_rows"] > 0
    assert (output / "report_data.json").is_file()

    assert (
        main(
            [
                "campaign",
                "report",
                str(project),
                "comparison-campaign",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert "report output already exists" in capsys.readouterr().err
