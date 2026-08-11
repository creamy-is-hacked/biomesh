"""Focused P4-WP05 persistent local-queue and application-path tests."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from biomesh.__main__ import main
from biomesh.local_queue import LocalQueueError, LocalQueueService
from biomesh.local_queue_types import (
    AppliedResourceLimits,
    LocalQueueState,
    QueueItemStatus,
)
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
WORKER_MEMORY_BYTES = 8 * 1024**3


def _definition(
    campaign_ids: tuple[str, ...] = ("campaign-a",),
    *,
    points: int = 1,
    replicates: int = 1,
) -> ProjectDefinition:
    fixture_hash = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    return ProjectDefinition(
        schema_version=1,
        project=ProjectRecord(
            schema_version=1,
            project_id="queue-research-project",
            title="Local queue software-validation project",
            description="Manufactured execution only; no biological conclusion.",
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
                campaign_id=campaign_id,
                experiment_id="accepted-producer",
                title=f"Queued campaign {campaign_id}",
                replicate_count=replicates,
                seed_policy=SeedPolicy(kind="sequence", start=21, step=1),
                sweep_matrix=[
                    SweepPoint(
                        point_id=f"point-{point_index}", condition_id="producer"
                    )
                    for point_index in range(points)
                ],
            )
            for campaign_id in campaign_ids
        ],
    )


def _create_project(tmp_path: Path, definition: ProjectDefinition) -> Path:
    definition_file = tmp_path / "definition.json"
    definition_file.write_text(
        definition.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return create_project(definition_file, tmp_path / "project")


def _create_queue(tmp_path: Path, *, name: str = "queue") -> Path:
    queue = tmp_path / name
    assert (
        main(
            [
                "queue",
                "create",
                str(queue),
                "--cpu-cores",
                "1",
                "--memory-limit-bytes",
                str(WORKER_MEMORY_BYTES),
            ]
        )
        == 0
    )
    return queue


def _run_queue_subprocess(queue: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "biomesh", "queue", "run", str(queue), *extra],
        check=False,
        capture_output=True,
        cwd=Path.cwd(),
        text=True,
        timeout=60,
    )


def test_cli_priority_progress_restart_and_exact_os_resource_receipt(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _create_project(tmp_path, _definition(("low", "high")))
    queue = _create_queue(tmp_path)
    capsys.readouterr()

    assert (
        main(
            [
                "queue",
                "enqueue",
                str(queue),
                str(project),
                "low",
                "--priority",
                "1",
            ]
        )
        == 0
    )
    low_id = json.loads(capsys.readouterr().out)["queue_id"]
    assert (
        main(
            [
                "queue",
                "enqueue",
                str(queue),
                str(project),
                "high",
                "--priority",
                "9",
            ]
        )
        == 0
    )
    high_id = json.loads(capsys.readouterr().out)["queue_id"]

    assert main(["queue", "status", str(queue)]) == 0
    before = json.loads(capsys.readouterr().out)
    assert [item["status"] for item in before["items"]] == ["queued", "queued"]
    assert all(item["progress_numerator"] == 0 for item in before["items"])

    first = _run_queue_subprocess(queue, "--once")
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout) == {
        "cancelled": 0,
        "completed": 1,
        "executed": 1,
        "failed": 0,
    }
    first_status = LocalQueueService(queue).status().as_dict()
    by_id = {item["queue_id"]: item for item in first_status["items"]}
    assert by_id[high_id]["status"] == "completed"
    assert by_id[low_id]["status"] == "queued"
    assert by_id[high_id]["progress_numerator"] == 1
    assert by_id[high_id]["progress_denominator"] == 1
    assert by_id[high_id]["resources"] == {
        "cpu_ids": [min(os.sched_getaffinity(0))],
        "memory_limit_bytes": WORKER_MEMORY_BYTES,
    }

    second = _run_queue_subprocess(queue)
    assert second.returncode == 0, second.stderr
    restarted = LocalQueueService(queue).status()
    assert [item.item.status for item in restarted.items] == [
        QueueItemStatus.COMPLETED,
        QueueItemStatus.COMPLETED,
    ]
    state = LocalQueueState.model_validate_json(
        (queue / "queue_state.json").read_text(encoding="utf-8")
    )
    starts = [
        record.queue_id for record in state.audit if record.action == "campaign_started"
    ]
    assert starts == [high_id, low_id]


def test_stale_worker_recovery_preserves_completed_run_bytes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _create_project(tmp_path, _definition(replicates=2))
    queue = _create_queue(tmp_path)
    capsys.readouterr()
    item = LocalQueueService(queue).enqueue(project, "campaign-a", priority=0)

    call_count = 0

    def crash_second(request: RunExecutionRequest, output: Path) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise KeyboardInterrupt
        (output / "immutable.txt").write_text(
            f"completed-{request.run.run_id}", encoding="utf-8"
        )

    service = CampaignService(project, executor=crash_second)
    with pytest.raises(KeyboardInterrupt):
        service.resume("campaign-a")
    campaign_state = json.loads((project / "campaign_state.json").read_text())
    completed_run = next(
        run for run in campaign_state["runs"] if run["status"] == "completed"
    )
    completed_path = (
        project / "artifacts" / completed_run["run_id"] / "immutable.txt"
    )
    completed_bytes = completed_path.read_bytes()

    queue_state_path = queue / "queue_state.json"
    queue_state = LocalQueueState.model_validate_json(
        queue_state_path.read_text(encoding="utf-8")
    )
    stale = queue_state.items[0].model_copy(
        update={
            "status": QueueItemStatus.RUNNING,
            "worker_pid": 999_999_999,
            "worker_start_ticks": 1,
            "applied_resources": AppliedResourceLimits(
                cpu_ids=[min(os.sched_getaffinity(0))],
                memory_limit_bytes=WORKER_MEMORY_BYTES,
            ),
        }
    )
    queue_state = queue_state.model_copy(update={"items": [stale]})
    queue_state_path.write_text(
        queue_state.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )

    recovered = LocalQueueService(queue).status()
    assert recovered.items[0].item.queue_id == item.queue_id
    assert recovered.items[0].item.status is QueueItemStatus.FAILED
    assert completed_path.read_bytes() == completed_bytes
    final_campaign = json.loads((project / "campaign_state.json").read_text())
    failed_run = next(
        run for run in final_campaign["runs"] if run["status"] == "failed"
    )
    assert failed_run["failure"]["kind"] == "interrupted"
    assert completed_run == next(
        run for run in final_campaign["runs"] if run["status"] == "completed"
    )


def test_cli_cancels_queued_campaign_without_changing_project(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _create_project(tmp_path, _definition())
    queue = _create_queue(tmp_path)
    capsys.readouterr()
    state_before = (project / "campaign_state.json").read_bytes()
    assert (
        main(
            ["queue", "enqueue", str(queue), str(project), "campaign-a"]
        )
        == 0
    )
    queue_id = json.loads(capsys.readouterr().out)["queue_id"]
    assert main(["queue", "cancel", str(queue), queue_id]) == 0
    cancelled = json.loads(capsys.readouterr().out)
    assert cancelled["status"] == "cancelled"
    assert (project / "campaign_state.json").read_bytes() == state_before
    assert _run_queue_subprocess(queue).returncode == 0

    with pytest.raises(LocalQueueError, match="already cancelled"):
        LocalQueueService(queue).cancel(queue_id)


def test_running_cli_cancellation_is_persistent_and_retryable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _create_project(tmp_path, _definition(points=40))
    queue = _create_queue(tmp_path)
    capsys.readouterr()
    item = LocalQueueService(queue).enqueue(project, "campaign-a", priority=4)
    worker = subprocess.Popen(
        [sys.executable, "-m", "biomesh", "queue", "run", str(queue)],
        cwd=Path.cwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 15
    observed_running = False
    while time.monotonic() < deadline:
        snapshot = LocalQueueService(queue).status()
        if snapshot.items[0].item.status is QueueItemStatus.RUNNING:
            observed_running = True
            break
        if worker.poll() is not None:
            break
        time.sleep(0.01)
    assert observed_running, "queue worker completed before cancellation probe"

    competing_worker = _run_queue_subprocess(queue, "--once")
    assert competing_worker.returncode == 2
    assert "already has an active worker" in competing_worker.stderr

    assert main(["queue", "cancel", str(queue), item.queue_id]) == 0
    capsys.readouterr()
    stdout, stderr = worker.communicate(timeout=30)
    assert worker.returncode == 0, stderr
    assert json.loads(stdout)["cancelled"] == 1
    final = LocalQueueService(queue).status().items[0]
    assert final.item.status is QueueItemStatus.CANCELLED
    assert final.campaign.running == 0
    assert final.campaign.pending > 0
    campaign_state = json.loads((project / "campaign_state.json").read_text())
    cancelled_runs = [
        run
        for run in campaign_state["runs"]
        if run["status"] == "failed" and run["failure"]["kind"] == "cancelled"
    ]
    assert len(cancelled_runs) == 1
    assert all(
        run["status"] != "completed" or run["artifacts"]
        for run in campaign_state["runs"]
    )
