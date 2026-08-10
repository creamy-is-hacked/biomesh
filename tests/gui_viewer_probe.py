"""Subprocess probe for the real P3-WP03 widgets and application snapshots."""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from biomesh.application import ApplicationService, RunRequest, RunStatus
from biomesh.application_types import (
    CellSnapshot,
    FieldSnapshot,
    RunSnapshot,
)
from biomesh.gui.main_window import MainWindow
from biomesh.gui.preferences import UiPreferencesStore
from biomesh.gui.viewer import FIELD_NAMES, SimulationViewer, ViewerError

_EXPORT_KEYS = {
    "carbon": "carbon_concentration_mol_m3",
    "oxygen": "oxygen_concentration_mol_m3",
    "quorum_signal": "quorum_signal_concentration_mol_m3",
    "eps": "eps_density_kg_m3",
    "waste": "waste_concentration_mol_m3",
}


def _snapshot(step: int) -> RunSnapshot:
    fields = tuple(
        FieldSnapshot.from_array(
            name=name,
            unit="kg m^-3" if name == "eps" else "mol m^-3",
            values=np.arange(6, dtype=np.float64).reshape(2, 3) + step + index,
        )
        for index, name in enumerate(FIELD_NAMES)
    )
    cells = (
        CellSnapshot(
            cell_id="cell-000",
            parent_id=None,
            x_m=1.0e-6 + step * 1.0e-8,
            y_m=0.5e-6,
            orientation_rad=math.pi / 6.0,
            length_m=1.0e-6,
            radius_m=0.25e-6,
            dry_biomass_kg=1.0e-15,
            age_s=float(step),
            state="active",
            strain="producer",
        ),
    )
    return RunSnapshot(
        status=RunStatus.RUNNING,
        condition_id="viewer-probe",
        seed=101,
        step_index=step,
        step_count=10,
        time_s=step * 0.1,
        configuration_sha256="0" * 64,
        calibration_status="CALIBRATION_REQUIRED",
        parameter_provenance=(),
        cells=cells,
        fields=fields,
        metrics=(),
        accounting=(),
    )


def _expect_viewer_error(function: object, *arguments: object) -> None:
    try:
        function(*arguments)  # type: ignore[operator]
    except ViewerError:
        return
    raise AssertionError("ViewerError was not raised")


def _exercise_layers_and_navigation() -> None:
    viewer = SimulationViewer(maximum_frames_per_second=30.0)
    first = _snapshot(0)
    assert viewer.present_snapshot(first)
    statistics = viewer.render_statistics()
    assert statistics.presented_frames == 1
    assert statistics.cell_rebuilds == 1
    assert dict(statistics.field_uploads) == {
        "carbon": 1,
        "oxygen": 0,
        "quorum_signal": 0,
        "eps": 0,
        "waste": 0,
    }
    np.testing.assert_allclose(
        viewer.rendered_field_values("carbon"),
        first.field("carbon").as_array(),
        rtol=0.0,
        atol=0.0,
    )
    viewer.set_layer_opacity("carbon", 0.35)
    assert viewer.layer_opacity("carbon") == 0.35
    viewer.set_layer_visible("carbon", False)
    viewer.set_layer_visible("cells", False)
    before = viewer.render_statistics()
    QTest.qWait(40)
    second = _snapshot(1)
    assert viewer.present_snapshot(second)
    after = viewer.render_statistics()
    assert after.cell_rebuilds == before.cell_rebuilds
    assert after.field_uploads == before.field_uploads
    assert viewer.rendered_field_values("carbon") is None

    viewer.set_layer_visible("oxygen", True)
    values = viewer.rendered_field_values("oxygen")
    assert values is not None and not values.flags.writeable
    np.testing.assert_allclose(
        values, second.field("oxygen").as_array(), rtol=0.0, atol=0.0
    )
    assert dict(viewer.render_statistics().field_uploads)["oxygen"] == 1

    viewer.fit_view()
    viewer.zoom_by(0.8)
    viewer.pan_cells(1.0e-7, -1.0e-7)
    viewer.pan_fields(0.25, -0.25)
    _expect_viewer_error(viewer.zoom_by, 0.0)
    _expect_viewer_error(viewer.pan_fields, float("nan"), 0.0)
    _expect_viewer_error(viewer.set_layer_opacity, "oxygen", 1.1)
    _expect_viewer_error(viewer.set_layer_visible, "unknown", True)
    viewer.close()


def _exercise_frame_rate_limit() -> None:
    viewer = SimulationViewer(maximum_frames_per_second=5.0)
    first = _snapshot(0)
    newest = _snapshot(2)
    assert viewer.present_snapshot(first)
    assert not viewer.present_snapshot(_snapshot(1))
    assert not viewer.present_snapshot(newest)
    assert viewer.render_statistics().presented_frames == 1
    QTest.qWait(230)
    assert viewer.render_statistics().presented_frames == 2
    np.testing.assert_allclose(
        viewer.rendered_field_values("carbon"),
        newest.field("carbon").as_array(),
        rtol=0.0,
        atol=0.0,
    )
    viewer.close()


def _exercise_application_export(root: Path) -> None:
    with ApplicationService() as service:
        snapshot = service.run(
            RunRequest(Path("experiments/producer.yaml"), "producer", 101)
        )
        while snapshot.status is not RunStatus.COMPLETED:
            snapshot = service.step()
        export = service.export(root / "viewer-export")

    viewer = SimulationViewer(maximum_frames_per_second=30.0)
    started = time.perf_counter()
    assert viewer.present_snapshot(snapshot)
    assert time.perf_counter() - started < 1.0
    archive_path = export.output_directory / "fields" / "000002.npz"
    with np.load(archive_path, allow_pickle=False) as archive:
        for name in FIELD_NAMES:
            viewer.set_layer_visible(name, True)
            displayed = viewer.rendered_field_values(name)
            assert displayed is not None
            np.testing.assert_allclose(
                displayed,
                archive[_EXPORT_KEYS[name]],
                rtol=1.0e-12,
                atol=1.0e-15,
            )
    viewer.close()


def main(root: Path) -> int:
    """Run focused acceptance checks with one real offscreen application."""
    application = QApplication(["biomesh-viewer-probe"])
    window = MainWindow(UiPreferencesStore(root / "ui-preferences.json"))
    assert isinstance(window.centralWidget(), SimulationViewer)
    window.show()
    application.processEvents()
    _exercise_layers_and_navigation()
    _exercise_frame_rate_limit()
    _exercise_application_export(root)
    window.close()
    application.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
