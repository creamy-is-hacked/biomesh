"""Offscreen application-path probe for P3-WP06 analytics and export work."""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication

from biomesh.application import ApplicationService
from biomesh.application_types import (
    ApplicationError,
    RunRequest,
    RunSnapshot,
    RunStatus,
)
from biomesh.gui.analytics import ANALYTICS_SERIES, AnalyticsPanel
from biomesh.gui.analytics_export import (
    AnalyticsExportCancelled,
    AnalyticsExportResult,
)
from biomesh.gui.main_window import MainWindow
from biomesh.gui.preferences import UiPreferencesStore
from biomesh.gui.simulation_worker import SimulationWorker


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
        time.sleep(0.002)
    raise AssertionError(f"timed out waiting for signal values: {values!r}")


def _long_cancelled_export(
    _service: ApplicationService,
    output: Path,
    snapshots: tuple[RunSnapshot, ...],
    cancel: threading.Event,
) -> AnalyticsExportResult:
    assert snapshots[-1].status is RunStatus.COMPLETED
    while not cancel.wait(0.002):
        pass
    assert not output.exists()
    raise AnalyticsExportCancelled("synthetic accepted export cancellation")


def _failed_export(
    _service: ApplicationService,
    _output: Path,
    _snapshots: tuple[RunSnapshot, ...],
    _cancel: threading.Event,
) -> AnalyticsExportResult:
    raise ApplicationError("synthetic export failure")


def _complete_snapshots(request: RunRequest) -> tuple[RunSnapshot, ...]:
    with ApplicationService() as service:
        snapshot = service.run(request)
        snapshots = [snapshot]
        while snapshot.status is not RunStatus.COMPLETED:
            snapshot = service.step()
            snapshots.append(snapshot)
    return tuple(snapshots)


def _complete_worker(
    application: QApplication,
    worker: SimulationWorker,
    request: RunRequest,
) -> list[RunSnapshot]:
    snapshots: list[RunSnapshot] = []
    worker.snapshot_ready.connect(snapshots.append)
    worker.start_run(request)
    _wait_for(
        application,
        snapshots,
        lambda item: item.status is RunStatus.COMPLETED,
    )
    return snapshots


def main(root: Path) -> int:
    application = QApplication(["biomesh-analytics-probe"])
    request = RunRequest(
        Path.cwd() / "experiments" / "competition_50_50.yaml",
        "competition-50-50",
        101,
    )
    snapshots = _complete_snapshots(request)
    panel = AnalyticsPanel()
    for snapshot in snapshots:
        panel.accept_snapshot(snapshot)
    metric_snapshots = [snapshot for snapshot in snapshots if snapshot.metrics]
    for series in ANALYTICS_SERIES:
        values = panel.series_values(series.name)
        assert len(values) == len(metric_snapshots)
        for (time_s, value), snapshot in zip(values, metric_snapshots, strict=True):
            assert time_s == snapshot.time_s
            if series.source_metric == "cell_count":
                assert value == float(len(snapshot.cells))
            else:
                metric = next(
                    item
                    for item in snapshot.metrics
                    if item.name == series.source_metric
                )
                assert value == metric.value

    cancelled: list[bool] = []
    started: list[bool] = []
    worker = SimulationWorker(
        export_function=_long_cancelled_export, speed_target_hz=1000.0
    )
    worker.export_started.connect(lambda: started.append(True))
    worker.export_cancelled.connect(lambda: cancelled.append(True))
    try:
        _complete_worker(application, worker, request)
        output = root / "cancelled-export"
        worker.export_run(output)
        _wait_for(application, started, lambda item: item)
        responsive_ticks = 0
        deadline = time.monotonic() + 0.05
        while time.monotonic() < deadline:
            application.processEvents()
            responsive_ticks += 1
            time.sleep(0.001)
        assert responsive_ticks >= 10
        worker.request_export_cancel()
        _wait_for(application, cancelled, lambda item: item)
        assert not output.exists()
    finally:
        worker.request_shutdown()
        assert worker.wait(10_000)

    errors: list[str] = []
    failing = SimulationWorker(export_function=_failed_export, speed_target_hz=1000.0)
    failing.error_reported.connect(errors.append)
    try:
        _complete_worker(application, failing, request)
        failing.export_run(root / "failed-export")
        _wait_for(
            application,
            errors,
            lambda item: item == "synthetic export failure",
        )
        assert failing.status is RunStatus.COMPLETED
        assert not (root / "failed-export").exists()
    finally:
        failing.request_shutdown()
        assert failing.wait(10_000)

    window = MainWindow(
        UiPreferencesStore(root / "integrated-ui-preferences.json"),
        repository_root=Path.cwd(),
    )
    window.show()
    application.processEvents()
    integrated_worker = window.findChild(SimulationWorker)
    export_action = window.findChild(QAction, "exportRunAction")
    cancel_action = window.findChild(QAction, "cancelExportAction")
    integrated_panel = window.findChild(AnalyticsPanel, "analyticsPanel")
    assert integrated_worker is not None
    assert export_action is not None and not export_action.isEnabled()
    assert cancel_action is not None and not cancel_action.isEnabled()
    assert integrated_panel is not None
    integrated_worker.set_speed_target(1000.0)
    integrated_snapshots = _complete_worker(application, integrated_worker, request)
    application.processEvents()
    assert export_action.isEnabled()
    assert integrated_panel.series_values("total_dry_biomass_kg")
    completed_exports: list[AnalyticsExportResult] = []
    integrated_errors: list[str] = []
    integrated_started: list[bool] = []
    integrated_worker.export_completed.connect(completed_exports.append)
    integrated_worker.error_reported.connect(integrated_errors.append)
    integrated_worker.export_started.connect(lambda: integrated_started.append(True))
    integrated_output = root / "integrated-export"
    integrated_worker.export_run(integrated_output)
    deadline = time.monotonic() + 20.0
    while (
        not completed_exports
        and not integrated_errors
        and time.monotonic() < deadline
    ):
        application.processEvents()
        time.sleep(0.002)
    assert integrated_started
    assert not integrated_errors, integrated_errors
    assert completed_exports
    integrated_result = completed_exports[-1]
    assert integrated_result.manifest_file.is_file()
    application.processEvents()
    assert export_action.isEnabled()
    assert not cancel_action.isEnabled()
    assert integrated_snapshots[-1].status is RunStatus.COMPLETED
    window.close()
    window.deleteLater()
    application.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
