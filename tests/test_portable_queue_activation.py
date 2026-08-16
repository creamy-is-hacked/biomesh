"""Focused P6-WP03 activation, recovery, retry, and traceability tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from threading import Barrier, Thread

import pytest

from biomesh.__main__ import main
from biomesh.local_queue import LocalQueueError, LocalQueueService
from biomesh.local_queue_storage import create_local_queue
from biomesh.portable_queue_activation import (
    activate_portable_queue_binding,
    load_portable_queue_activation,
)
from biomesh.portable_queue_activation_types import (
    PortableQueueActivationError,
)
from biomesh.portable_queue_import import (
    bind_portable_queue_intent,
    import_portable_queue_intent,
    parse_project_path_binding,
)
from biomesh.portable_queue_import_types import PortableQueueBindingRecord
from biomesh.portable_queue_intent import export_portable_queue_intent
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
from biomesh.project_reports import generate_campaign_report

FIXTURE = Path("experiments/producer.yaml")
MEMORY_LIMIT_BYTES = 8 * 1024**3


def _definition(project_id: str = "activation-project") -> ProjectDefinition:
    return ProjectDefinition(
        schema_version=2,
        project=ProjectRecord(
            schema_version=1,
            project_id=project_id,
            title="Activation project",
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
                campaign_id="campaign-a",
                experiment_id="accepted-producer",
                title="Activation campaign",
                replicate_count=1,
                seed_policy=SeedPolicy(kind="explicit", seeds=[41]),
                sweep_matrix=[
                    SweepPoint(point_id="producer-point", condition_id="producer")
                ],
            )
        ],
        execution_identity=accepted_core_execution_identity(Path.cwd()),
    )


def _project(tmp_path: Path) -> Path:
    definition = _definition()
    definition_file = tmp_path / "definition.json"
    definition_file.write_text(
        definition.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return create_project(definition_file, tmp_path / "project")


def _binding(tmp_path: Path, project: Path) -> Path:
    source_queue = create_local_queue(
        tmp_path / "source-queue",
        cpu_cores=1,
        memory_limit_bytes=MEMORY_LIMIT_BYTES,
    )
    LocalQueueService(source_queue).enqueue(project, "campaign-a", priority=7)
    manifest = tmp_path / "intent.json"
    export_portable_queue_intent(source_queue, manifest)
    imported = tmp_path / "imported.json"
    import_portable_queue_intent(manifest, imported)
    binding = tmp_path / "binding.json"
    bind_portable_queue_intent(
        imported,
        binding,
        project_bindings=[
            parse_project_path_binding(f"activation-project={project.resolve()}")
        ],
        cpu_cores=1,
        memory_limit_bytes=MEMORY_LIMIT_BYTES,
    )
    return binding


def test_activation_is_atomic_runnable_and_report_traceable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _project(tmp_path)
    binding_path = _binding(tmp_path, project)
    binding_bytes = binding_path.read_bytes()
    queue = tmp_path / "destination-queue"

    assert main(["queue", "activate-intent", str(binding_path), str(queue)]) == 0
    activation_receipt = json.loads(capsys.readouterr().out)
    assert binding_path.read_bytes() == binding_bytes
    assert (queue / "portable_activation.json").is_file()
    loaded = load_portable_queue_activation(queue)
    assert loaded is not None
    assert activation_receipt["activation_sha256"] == hashlib.sha256(
        (queue / "portable_activation.json").read_bytes()
    ).hexdigest()
    assert [
        item.item.status.value for item in LocalQueueService(queue).status().items
    ] == [
        "queued"
    ]

    result = LocalQueueService(queue).run()
    assert (result.executed, result.completed, result.failed) == (1, 1, 0)
    state = json.loads((queue / "queue_state.json").read_text(encoding="utf-8"))
    assert state["items"][0]["status"] == "completed"
    assert state["items"][0]["worker_pid"] is None
    run_request = next(
        path / "run_request.json"
        for path in (project / "artifacts").iterdir()
        if path.is_dir()
    )
    trace = json.loads(run_request.read_text(encoding="utf-8"))["portable_trace"]
    bound = PortableQueueBindingRecord.model_validate_json(binding_bytes)
    assert trace["portable_manifest_sha256"] == bound.source_manifest_sha256
    report = tmp_path / "destination-report"
    generate_campaign_report(
        project,
        "campaign-a",
        report,
        portable_binding=bound,
    )
    report_data = json.loads((report / "report_data.json").read_text(encoding="utf-8"))
    assert report_data["portable_traceability"]["campaign_id"] == "campaign-a"
    assert report_data["environment"]["python_version"]


def test_activation_target_conflict_and_concurrent_claim_are_explicit(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    binding = _binding(tmp_path, project)
    target = tmp_path / "destination"
    activate_portable_queue_binding(binding, target)
    with pytest.raises(PortableQueueActivationError, match="already exists"):
        activate_portable_queue_binding(binding, target)

    second_target = tmp_path / "second-destination"
    barrier = Barrier(2)
    errors: list[Exception] = []

    def activate() -> None:
        barrier.wait()
        try:
            activate_portable_queue_binding(binding, second_target)
        except Exception as error:  # noqa: BLE001 - assertion captures exact race result
            errors.append(error)

    threads = [Thread(target=activate), Thread(target=activate)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(errors) == 1
    assert second_target.is_dir()
    assert load_portable_queue_activation(second_target) is not None


def test_activated_queue_cannot_mix_enqueue_and_completed_item_cannot_retry(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    binding = _binding(tmp_path, project)
    queue = tmp_path / "destination"
    activation = activate_portable_queue_binding(binding, queue)
    service = LocalQueueService(queue)
    with pytest.raises(LocalQueueError, match="cannot accept"):
        service.enqueue(project, "campaign-a", priority=1)
    assert service.run().completed == 1
    queue_id = activation.items[0].local_queue_id
    with pytest.raises(LocalQueueError, match="not retryable"):
        service.retry(queue_id)


def test_activation_rejects_tampered_binding_without_partial_queue(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    binding = _binding(tmp_path, project)
    payload = json.loads(binding.read_bytes())
    payload["items"][0]["intent"]["priority"] = 999
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    target = tmp_path / "destination"
    with pytest.raises(PortableQueueActivationError):
        activate_portable_queue_binding(tampered, target)
    assert not target.exists()
