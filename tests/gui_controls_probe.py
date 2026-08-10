"""Offscreen application-path probe for P3-WP05 controls and inspection."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from biomesh.application import ApplicationService
from biomesh.application_types import (
    ApplicationError,
    CellInspection,
    CheckpointResult,
    RunRequest,
    RunSnapshot,
    RunStatus,
)
from biomesh.gui.cell_inspector import CellInspector
from biomesh.gui.experiment_editor import ExperimentEditor
from biomesh.gui.main_window import MainWindow
from biomesh.gui.preferences import UiPreferencesStore
from biomesh.gui.run_controls import SimulationControls
from biomesh.gui.simulation_worker import SimulationWorker
from biomesh.gui.viewer import SimulationViewer


def _wait_for[T](
    application: QApplication,
    values: list[T],
    predicate: Callable[[T], bool],
    *,
    timeout_s: float = 5.0,
) -> T:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        application.processEvents()
        for value in reversed(values):
            if predicate(value):
                return value
        time.sleep(0.005)
    raise AssertionError(f"timed out waiting for signal values: {values!r}")


def _scientific(snapshot: RunSnapshot) -> RunSnapshot:
    return replace(snapshot, status=RunStatus.PAUSED)


class _FailingStepService(ApplicationService):
    def step(self) -> RunSnapshot:
        raise ApplicationError("synthetic worker solver failure")


def main(root: Path) -> int:
    application = QApplication(["biomesh-controls-probe"])
    repository_root = Path.cwd()
    request = RunRequest(
        repository_root / "experiments" / "producer.yaml", "producer", 101
    )

    controls = SimulationControls(repository_root)
    run_button = controls.findChild(QPushButton, "runButton")
    load_checkpoint = controls.findChild(QPushButton, "resumeCheckpointButton")
    assert run_button is not None and not run_button.isEnabled()
    assert load_checkpoint is not None and not load_checkpoint.isEnabled()
    controls.set_editor_run_eligible(True)
    assert run_button.isEnabled()
    assert load_checkpoint.isEnabled()
    assert controls.selected_request() == request
    pause_button = controls.findChild(QPushButton, "pauseButton")
    step_button = controls.findChild(QPushButton, "stepButton")
    resume_button = controls.findChild(QPushButton, "resumeButton")
    stop_button = controls.findChild(QPushButton, "stopButton")
    checkpoint_button = controls.findChild(QPushButton, "checkpointButton")
    assert all(
        button is not None
        for button in (
            pause_button,
            step_button,
            resume_button,
            stop_button,
            checkpoint_button,
        )
    )
    controls.accept_state(RunStatus.RUNNING)
    assert pause_button is not None and pause_button.isEnabled()
    assert stop_button is not None and stop_button.isEnabled()
    assert not run_button.isEnabled()
    controls.accept_state(RunStatus.PAUSED)
    assert step_button is not None and step_button.isEnabled()
    assert resume_button is not None and resume_button.isEnabled()
    assert checkpoint_button is not None and checkpoint_button.isEnabled()
    controls.accept_state(RunStatus.COMPLETED)
    assert checkpoint_button.isEnabled()
    assert not stop_button.isEnabled()
    controls.accept_state(RunStatus.IDLE)
    controls.set_editor_run_eligible(False)
    assert not run_button.isEnabled()
    assert not load_checkpoint.isEnabled()

    snapshots: list[RunSnapshot] = []
    inspections: list[CellInspection] = []
    checkpoints: list[CheckpointResult] = []
    errors: list[str] = []
    stopped: list[bool] = []
    speeds: list[float] = []
    worker = SimulationWorker(speed_target_hz=0.1)
    worker.snapshot_ready.connect(snapshots.append)
    worker.inspection_ready.connect(inspections.append)
    worker.checkpoint_created.connect(checkpoints.append)
    worker.error_reported.connect(errors.append)
    worker.stopped.connect(lambda: stopped.append(True))
    worker.speed_target_changed.connect(speeds.append)
    try:
        worker.set_speed_target(20.0)
        _wait_for(application, speeds, lambda item: item == 20.0)
        assert worker.speed_target_hz == 20.0
        worker.set_speed_target(0.1)
        _wait_for(application, speeds, lambda item: item == 0.1)
        worker.start_run(request)
        _wait_for(
            application,
            snapshots,
            lambda item: item.status is RunStatus.RUNNING and item.step_index == 0,
        )
        worker.request_pause()
        paused_zero = _wait_for(
            application,
            snapshots,
            lambda item: item.status is RunStatus.PAUSED and item.step_index == 0,
        )
        worker.request_step()
        paused_one = _wait_for(
            application,
            snapshots,
            lambda item: item.status is RunStatus.PAUSED and item.step_index == 1,
        )

        with ApplicationService() as expected_service:
            expected_service.run(request)
            expected_service.pause()
            expected_one = expected_service.step()
            expected_inspection = expected_service.inspect("cell-000")
        assert _scientific(paused_zero).step_index == 0
        assert _scientific(paused_one) == _scientific(expected_one)
        assert isinstance(expected_inspection, CellInspection)

        viewer = SimulationViewer(maximum_frames_per_second=1000.0)
        viewer.present_snapshot(paused_one)
        viewer.cell_clicked.connect(
            lambda cell_id: worker.inspect_cell(
                cell_id, expected_step_index=paused_one.step_index
            )
        )
        cell = paused_one.cells[0]
        assert viewer.select_cell_at(cell.x_m, cell.y_m) == cell.cell_id
        actual_inspection = _wait_for(
            application, inspections, lambda item: item.cell.cell_id == cell.cell_id
        )
        assert actual_inspection == expected_inspection
        inspector = CellInspector()
        inspector.present_inspection(actual_inspection)
        assert inspector.inspection == expected_inspection
        biomass = inspector.findChild(QLabel, "inspection_biomass")
        eps = inspector.findChild(QLabel, "inspection_eps")
        assert biomass is not None
        assert biomass.text() == f"{expected_inspection.cell.dry_biomass_kg:.17g} kg"
        expected_eps = next(
            value for value in expected_inspection.local_values if value.name == "eps"
        )
        assert eps is not None
        assert f"{expected_eps.value:.17g} {expected_eps.unit}" in eps.text()
        assert "not exposed" in eps.text()

        worker.inspect_cell("cell-000", expected_step_index=0)
        _wait_for(application, errors, lambda item: "snapshot is stale" in item)

        checkpoint_file = root / "paused.checkpoint.json"
        worker.create_checkpoint(checkpoint_file)
        checkpoint = _wait_for(
            application, checkpoints, lambda item: item.step_index == 1
        )
        assert checkpoint.checkpoint_file == checkpoint_file
        assert checkpoint_file.is_file()

        worker.request_stop()
        _wait_for(application, stopped, lambda item: item)
        count_after_stop = len(snapshots)
        deadline = time.monotonic() + 0.2
        while time.monotonic() < deadline:
            application.processEvents()
            time.sleep(0.005)
        assert len(snapshots) == count_after_stop
        assert worker.status is RunStatus.IDLE

        worker.resume_checkpoint(checkpoint_file)
        resumed_one = _wait_for(
            application,
            snapshots,
            lambda item: item.status is RunStatus.RUNNING and item.step_index == 1,
        )
        assert _scientific(resumed_one) == _scientific(paused_one)
        worker.request_pause()
        _wait_for(
            application,
            snapshots,
            lambda item: item.status is RunStatus.PAUSED and item.step_index == 1,
        )
        worker.request_step()
        resumed_two = _wait_for(
            application,
            snapshots,
            lambda item: item.status is RunStatus.PAUSED and item.step_index == 2,
        )
        with ApplicationService() as uninterrupted:
            uninterrupted.run(request)
            uninterrupted.pause()
            uninterrupted.step()
            expected_two = uninterrupted.step()
            expected_complete = uninterrupted.step()
        assert _scientific(resumed_two) == _scientific(expected_two)
        worker.set_speed_target(100.0)
        _wait_for(application, speeds, lambda item: item == 100.0)
        worker.request_resume()
        completed = _wait_for(
            application,
            snapshots,
            lambda item: item.status is RunStatus.COMPLETED,
        )
        assert replace(completed, status=RunStatus.COMPLETED) == expected_complete
    finally:
        worker.request_shutdown()
        assert worker.wait(10_000)

    failure_errors: list[str] = []
    failing = SimulationWorker(
        service_factory=_FailingStepService, speed_target_hz=1000.0
    )
    failing.error_reported.connect(failure_errors.append)
    try:
        failing.start_run(request)
        _wait_for(
            application,
            failure_errors,
            lambda item: item == "synthetic worker solver failure",
        )
        assert failing.status is RunStatus.PAUSED
    finally:
        failing.request_shutdown()
        assert failing.wait(10_000)

    window = MainWindow(
        UiPreferencesStore(root / "ui-preferences.json"),
        repository_root=repository_root,
    )
    window.show()
    application.processEvents()
    integrated_run = window.findChild(QPushButton, "runButton")
    assert integrated_run is not None and not integrated_run.isEnabled()
    integrated_editor = window.findChild(ExperimentEditor, "experimentEditor")
    assert integrated_editor is not None
    assert integrated_editor.load_template("p2_eps")
    for index, _parameter in enumerate(
        integrated_editor.session.document.configuration.biological_parameters
    ):
        integrated_editor.set_field_text(index, "value", "0.1")
        integrated_editor.set_field_text(
            index, "source", "manufactured software test input"
        )
        integrated_editor.set_field_text(
            index, "uncertainty", "synthetic exact test input"
        )
        integrated_editor.set_field_text(index, "calibration_status", "DERIVED")
    application.processEvents()
    assert integrated_editor.session.run_eligible
    assert integrated_run.isEnabled()
    integrated_editor.set_field_text(0, "value", "invalid")
    application.processEvents()
    assert not integrated_editor.session.run_eligible
    assert not integrated_run.isEnabled()
    window.close()
    application.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
