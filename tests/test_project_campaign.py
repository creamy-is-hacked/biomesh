"""Focused P4-WP01 project/campaign model and application-path tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from biomesh.__main__ import main
from biomesh.project_campaign import (
    CampaignRecord,
    CampaignRunStatus,
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

FIXTURE = Path("experiments/producer.yaml")


def _definition(*, replicate_count: int = 2, points: int = 2) -> ProjectDefinition:
    fixture_hash = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    return ProjectDefinition(
        schema_version=1,
        project=ProjectRecord(
            schema_version=1,
            project_id="research-project",
            title="Manufactured validation project",
            description="Software validation only; no biological conclusion.",
        ),
        experiments=[
            ExperimentRecord(
                schema_version=1,
                experiment_id="accepted-producer",
                title="Accepted producer fixture",
                fixture_file=str(FIXTURE),
                fixture_sha256=fixture_hash,
                calibration_status="CALIBRATION_REQUIRED",
                notes="Preserves the accepted P2/P3 fixture path.",
            )
        ],
        campaigns=[
            CampaignRecord(
                schema_version=1,
                campaign_id="campaign-a",
                experiment_id="accepted-producer",
                title="Replicate matrix",
                replicate_count=replicate_count,
                seed_policy=SeedPolicy(kind="sequence", start=10, step=5),
                sweep_matrix=[
                    SweepPoint(
                        point_id=f"point-{index}",
                        condition_id="producer",
                    )
                    for index in range(points)
                ],
            )
        ],
    )


def _write_definition(tmp_path: Path, definition: ProjectDefinition) -> Path:
    path = tmp_path / "definition.json"
    path.write_text(definition.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def _create(tmp_path: Path, definition: ProjectDefinition | None = None) -> Path:
    definition_file = _write_definition(tmp_path, definition or _definition())
    return create_project(definition_file, tmp_path / "project")


def test_seed_policies_are_deterministic_and_strict() -> None:
    assert SeedPolicy(kind="explicit", seeds=[9, 4]).expand(2) == (9, 4)
    assert SeedPolicy(kind="sequence", start=7, step=3).expand(4) == (7, 10, 13, 16)

    with pytest.raises(ProjectCampaignError, match="must equal"):
        SeedPolicy(kind="explicit", seeds=[1]).expand(2)
    with pytest.raises(ValidationError, match="must be unique"):
        SeedPolicy(kind="explicit", seeds=[1, 1])
    with pytest.raises(ValidationError, match="requires start/step"):
        SeedPolicy(kind="sequence", start=1)


def test_project_creation_expands_stable_matrix_and_audit(tmp_path: Path) -> None:
    project = _create(tmp_path)
    state = json.loads((project / "campaign_state.json").read_text())

    assert [run["seed"] for run in state["runs"]] == [10, 15, 10, 15]
    assert len({run["run_id"] for run in state["runs"]}) == 4
    assert all(run["status"] == "pending" for run in state["runs"])
    assert state["audit"] == [
        {
            "action": "campaign_initialized",
            "attempt": 0,
            "campaign_id": "campaign-a",
            "detail": "planned 4 runs",
            "run_id": None,
            "sequence": 0,
        }
    ]
    assert CampaignService(project).status("campaign-a").as_dict() == {
        "campaign_id": "campaign-a",
        "completed": 0,
        "failed": 0,
        "pending": 4,
        "running": 0,
        "total": 4,
    }


def test_project_rejects_fixture_drift_and_sweep_provenance_mismatch(
    tmp_path: Path,
) -> None:
    definition = _definition()
    changed_hash = definition.experiments[0].model_copy(
        update={"fixture_sha256": "0" * 64}
    )
    mismatched = definition.model_copy(update={"experiments": [changed_hash]})
    with pytest.raises(ProjectCampaignError, match="fixture hash mismatch"):
        _create(tmp_path, mismatched)

    parameter_payload = {
        "name": "maximum_eps_allocation_fraction",
        "value": 0.2,
        "unit": "1",
        "level_id": "invented",
        "source": "manufactured software-validation fixture",
        "uncertainty": "not a biological uncertainty",
        "notes": "SI-labelled executable fixture; not calibration.",
        "calibration_status": "DERIVED",
    }
    point = SweepPoint.model_validate(
        {
            "point_id": "bad-point",
            "condition_id": "producer",
            "parameters": [parameter_payload],
        }
    )
    campaign = definition.campaigns[0].model_copy(update={"sweep_matrix": [point]})
    mismatch = definition.model_copy(update={"campaigns": [campaign]})
    second = tmp_path / "second"
    second.mkdir()
    with pytest.raises(ProjectCampaignError, match="parameters do not match"):
        _create(second, mismatch)


def test_partial_failure_is_explicit_and_retryable_without_rerunning_completion(
    tmp_path: Path,
) -> None:
    project = _create(tmp_path, _definition(replicate_count=2, points=1))
    attempts: dict[str, int] = {}

    def executor(request: RunExecutionRequest, output: Path) -> None:
        attempts[request.run.run_id] = attempts.get(request.run.run_id, 0) + 1
        if request.run.replicate_index == 1 and attempts[request.run.run_id] == 1:
            raise RuntimeError("synthetic partial failure")
        (output / "result.json").write_text(
            json.dumps({"seed": request.run.seed}), encoding="utf-8"
        )

    service = CampaignService(project, executor=executor)
    first = service.resume("campaign-a")
    assert (first.completed, first.failed, first.pending) == (1, 1, 0)

    first_state = json.loads((project / "campaign_state.json").read_text())
    failed = next(run for run in first_state["runs"] if run["status"] == "failed")
    completed = next(run for run in first_state["runs"] if run["status"] == "completed")
    assert failed["failure"] == {
        "kind": "runtime",
        "message": "synthetic partial failure",
        "retryable": True,
    }
    completed_bytes = (
        project / "artifacts" / completed["run_id"] / "result.json"
    ).read_bytes()

    final = service.retry("campaign-a", [failed["run_id"]])
    assert (final.completed, final.failed) == (2, 0)
    assert attempts[completed["run_id"]] == 1
    assert (
        project / "artifacts" / completed["run_id"] / "result.json"
    ).read_bytes() == completed_bytes

    state = json.loads((project / "campaign_state.json").read_text())
    retried = next(run for run in state["runs"] if run["run_id"] == failed["run_id"])
    assert retried["attempt_count"] == 2
    assert [record["sequence"] for record in state["audit"]] == list(
        range(len(state["audit"]))
    )


def test_interrupted_run_becomes_explicit_failure_and_other_work_resumes(
    tmp_path: Path,
) -> None:
    project = _create(tmp_path, _definition(replicate_count=2, points=1))
    interrupted = True

    def executor(request: RunExecutionRequest, output: Path) -> None:
        nonlocal interrupted
        if interrupted:
            interrupted = False
            raise KeyboardInterrupt
        (output / "result.txt").write_text(str(request.run.seed), encoding="utf-8")

    service = CampaignService(project, executor=executor)
    with pytest.raises(KeyboardInterrupt):
        service.resume("campaign-a")
    assert service.status("campaign-a").running == 1

    resumed = service.resume("campaign-a")
    assert (resumed.completed, resumed.failed, resumed.running) == (1, 1, 0)
    state = json.loads((project / "campaign_state.json").read_text())
    failure = next(run for run in state["runs"] if run["status"] == "failed")
    assert failure["failure"]["kind"] == "interrupted"
    assert any(record["action"] == "run_failed" for record in state["audit"])


def test_completed_artifact_drift_blocks_resume_and_retry(tmp_path: Path) -> None:
    project = _create(tmp_path, _definition(replicate_count=1, points=1))

    def executor(_request: RunExecutionRequest, output: Path) -> None:
        (output / "immutable.txt").write_text("original", encoding="utf-8")

    service = CampaignService(project, executor=executor)
    assert service.resume("campaign-a").completed == 1
    state = json.loads((project / "campaign_state.json").read_text())
    run_id = state["runs"][0]["run_id"]
    (project / "artifacts" / run_id / "immutable.txt").write_text(
        "changed", encoding="utf-8"
    )

    with pytest.raises(ProjectCampaignError, match="artifact changed"):
        service.status("campaign-a")
    with pytest.raises(ProjectCampaignError, match="artifact changed"):
        service.resume("campaign-a")


def test_published_artifacts_recover_after_state_write_interruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _create(tmp_path, _definition(replicate_count=1, points=1))

    def executor(_request: RunExecutionRequest, output: Path) -> None:
        (output / "complete.txt").write_text("complete", encoding="utf-8")

    service = CampaignService(project, executor=executor)
    original = service._write_state
    writes = 0

    def interrupt_completion(state: object) -> None:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("synthetic post-publication interruption")
        original(state)  # type: ignore[arg-type]

    monkeypatch.setattr(service, "_write_state", interrupt_completion)
    with pytest.raises(ProjectCampaignError, match="post-publication"):
        service.resume("campaign-a")
    monkeypatch.setattr(service, "_write_state", original)

    recovered = service.resume("campaign-a")
    assert (recovered.completed, recovered.failed, recovered.running) == (1, 0, 0)
    state = json.loads((project / "campaign_state.json").read_text())
    assert state["runs"][0]["attempt_count"] == 1
    assert state["audit"][-1]["action"] == "run_recovered"


def test_cli_create_status_resume_and_retry_application_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    definition_file = _write_definition(
        tmp_path, _definition(replicate_count=1, points=1)
    )
    project = tmp_path / "cli-project"
    assert main(["project", "create", str(definition_file), str(project)]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["project_directory"] == str(project)

    assert main(["campaign", "status", str(project), "campaign-a"]) == 0
    assert json.loads(capsys.readouterr().out)["pending"] == 1

    calls = 0

    def fail_once(request: RunExecutionRequest, output: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("retry probe")
        (output / "result.json").write_text(
            json.dumps({"run_id": request.run.run_id}), encoding="utf-8"
        )

    monkeypatch.setattr("biomesh.project_campaign.execute_application_run", fail_once)
    assert main(["campaign", "resume", str(project), "campaign-a"]) == 1
    assert json.loads(capsys.readouterr().out)["failed"] == 1
    assert main(["campaign", "retry", str(project), "campaign-a"]) == 0
    assert json.loads(capsys.readouterr().out)["completed"] == 1


def test_real_application_executor_preserves_raw_artifact_contract(
    tmp_path: Path,
) -> None:
    project = _create(tmp_path, _definition(replicate_count=1, points=1))
    status = CampaignService(project).resume("campaign-a")
    assert (status.completed, status.failed) == (1, 0)
    state = json.loads((project / "campaign_state.json").read_text())
    run = state["runs"][0]
    artifact_root = project / "artifacts" / run["run_id"]
    assert (artifact_root / "run_request.json").is_file()
    assert (artifact_root / "raw" / "run_metadata.json").is_file()
    assert (artifact_root / "raw" / "summary.parquet").is_file()
    assert all(record["sha256"] for record in run["artifacts"])
    assert run["status"] == CampaignRunStatus.COMPLETED.value
