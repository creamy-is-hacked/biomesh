"""Snapshot-only P3-WP03 simulation viewer.

Cells retain their SI coordinates in a dedicated canvas. Scalar fields retain
their exact array values in a grid-indexed canvas because the immutable
P3-WP01 snapshot contract deliberately contains no domain extent. Keeping the
canvases separate avoids inventing a spatial transform between those records.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
import pyqtgraph as pg  # type: ignore[import-untyped]
from numpy.typing import NDArray
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import (
    QCheckBox,
    QGraphicsPathItem,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from biomesh.application_types import CellSnapshot, FieldSnapshot, RunSnapshot

FIELD_NAMES = ("carbon", "oxygen", "quorum_signal", "eps", "waste")


class ViewerError(ValueError):
    """Raised when a snapshot or viewer operation is invalid."""


@dataclass(frozen=True, slots=True)
class RenderStatistics:
    """Small immutable counter set used to verify bounded rendering work."""

    presented_frames: int
    cell_rebuilds: int
    field_uploads: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class _FieldStyle:
    title: str
    color_map: str
    color: str


_FIELD_STYLES = {
    "carbon": _FieldStyle("Carbon", "viridis", "#2a9d8f"),
    "oxygen": _FieldStyle("Oxygen", "magma", "#457b9d"),
    "quorum_signal": _FieldStyle("Quorum signal", "plasma", "#e76f51"),
    "eps": _FieldStyle("EPS", "cividis", "#e9c46a"),
    "waste": _FieldStyle("Waste", "inferno", "#9b5de5"),
}


class SimulationViewer(QWidget):
    """Render immutable cells and scalar fields without owning solver state."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        maximum_frames_per_second: float = 30.0,
    ) -> None:
        super().__init__(parent)
        if (
            isinstance(maximum_frames_per_second, bool)
            or not isinstance(maximum_frames_per_second, (int, float))
            or not math.isfinite(maximum_frames_per_second)
            or maximum_frames_per_second <= 0.0
        ):
            raise ViewerError("maximum_frames_per_second must be finite and positive")
        self.setObjectName("simulationViewer")
        self._minimum_frame_interval_ns = math.ceil(
            1_000_000_000 / float(maximum_frames_per_second)
        )
        self._last_render_ns: int | None = None
        self._latest_snapshot: RunSnapshot | None = None
        self._pending_snapshot: RunSnapshot | None = None
        self._presented_frames = 0
        self._cell_rebuilds = 0
        self._field_uploads = dict.fromkeys(FIELD_NAMES, 0)

        self._layer_visibility = {"cells": True, **dict.fromkeys(FIELD_NAMES, False)}
        self._layer_visibility["carbon"] = True
        self._layer_opacity = {name: 1.0 for name in self._layer_visibility}
        self._layer_checks: dict[str, QCheckBox] = {}
        self._layer_sliders: dict[str, QSlider] = {}
        self._legend_values: dict[str, QLabel] = {}
        self._field_items: dict[str, pg.ImageItem] = {}

        self._frame_timer = QTimer(self)
        self._frame_timer.setSingleShot(True)
        self._frame_timer.timeout.connect(self._present_pending_snapshot)

        self._build_ui()

    @property
    def latest_snapshot(self) -> RunSnapshot | None:
        """Return the last snapshot accepted for display."""
        return self._latest_snapshot

    @property
    def maximum_frames_per_second(self) -> float:
        """Return the configured hard presentation-rate ceiling."""
        return 1_000_000_000 / self._minimum_frame_interval_ns

    def present_snapshot(self, snapshot: RunSnapshot) -> bool:
        """Present now or retain only the newest snapshot until the next frame.

        The Boolean result is true when this call rendered immediately and
        false when rate limiting queued or replaced a pending frame.
        """
        self._validate_snapshot(snapshot)
        now_ns = time.monotonic_ns()
        if (
            self._last_render_ns is None
            or now_ns - self._last_render_ns >= self._minimum_frame_interval_ns
        ):
            self._frame_timer.stop()
            self._pending_snapshot = None
            self._render_snapshot(snapshot, now_ns=now_ns)
            return True

        self._pending_snapshot = snapshot
        remaining_ns = self._minimum_frame_interval_ns - (
            now_ns - self._last_render_ns
        )
        if not self._frame_timer.isActive():
            self._frame_timer.start(max(1, math.ceil(remaining_ns / 1_000_000)))
        return False

    def set_layer_visible(self, name: str, visible: bool) -> None:
        """Set layer visibility, uploading its current snapshot only on show."""
        self._require_layer(name)
        if not isinstance(visible, bool):
            raise ViewerError("visible must be a bool")
        if self._layer_visibility[name] is visible:
            return
        self._layer_visibility[name] = visible
        check = self._layer_checks[name]
        if check.isChecked() is not visible:
            check.setChecked(visible)
        if name == "cells":
            self._cell_item.setVisible(visible)
            if visible and self._latest_snapshot is not None:
                self._render_cells(self._latest_snapshot.cells)
            return
        item = self._field_items[name]
        item.setVisible(visible)
        if visible and self._latest_snapshot is not None:
            self._render_field(self._latest_snapshot.field(name))

    def layer_is_visible(self, name: str) -> bool:
        """Return whether a named layer participates in rendering."""
        self._require_layer(name)
        return self._layer_visibility[name]

    def set_layer_opacity(self, name: str, opacity: float) -> None:
        """Set one layer opacity in the explicit closed interval [0, 1]."""
        self._require_layer(name)
        if (
            isinstance(opacity, bool)
            or not isinstance(opacity, (int, float))
            or not math.isfinite(opacity)
            or not 0.0 <= opacity <= 1.0
        ):
            raise ViewerError("opacity must be finite and between 0 and 1")
        value = float(opacity)
        self._layer_opacity[name] = value
        slider = self._layer_sliders[name]
        slider_value = round(value * 100)
        if slider.value() != slider_value:
            slider.setValue(slider_value)
        if name == "cells":
            self._cell_item.setOpacity(value)
        else:
            self._field_items[name].setOpacity(value)

    def layer_opacity(self, name: str) -> float:
        """Return a named layer's current opacity."""
        self._require_layer(name)
        return self._layer_opacity[name]

    def rendered_field_values(
        self, name: str
    ) -> NDArray[np.float64] | None:
        """Return a read-only copy of the values held by a visible image item."""
        self._require_field(name)
        item = self._field_items[name]
        if not self._layer_visibility[name] or item.image is None:
            return None
        values = np.array(item.image, dtype=np.float64, copy=True)
        values.setflags(write=False)
        return values

    def render_statistics(self) -> RenderStatistics:
        """Return immutable work counters for performance acceptance tests."""
        return RenderStatistics(
            presented_frames=self._presented_frames,
            cell_rebuilds=self._cell_rebuilds,
            field_uploads=tuple(
                (name, self._field_uploads[name]) for name in FIELD_NAMES
            ),
        )

    def fit_view(self) -> None:
        """Fit both coordinate-faithful canvases to their visible content."""
        self._cells_plot.enableAutoRange()
        self._fields_plot.enableAutoRange()
        self._cells_plot.autoRange()
        self._fields_plot.autoRange()

    def zoom_by(self, factor: float) -> None:
        """Zoom both canvases by a positive relative scale factor."""
        if (
            isinstance(factor, bool)
            or not isinstance(factor, (int, float))
            or not math.isfinite(factor)
            or factor <= 0.0
        ):
            raise ViewerError("zoom factor must be finite and positive")
        scale = float(factor)
        self._cells_plot.getViewBox().scaleBy((scale, scale))
        self._fields_plot.getViewBox().scaleBy((scale, scale))

    def pan_cells(self, x_m: float, y_m: float) -> None:
        """Pan the cell canvas by explicit SI distances."""
        self._pan(self._cells_plot, x_m, y_m)

    def pan_fields(self, columns: float, rows: float) -> None:
        """Pan the field canvas by explicit array-index distances."""
        self._pan(self._fields_plot, columns, rows)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        fit_button = QPushButton("Fit", self)
        fit_button.setObjectName("fitViewButton")
        fit_button.clicked.connect(self.fit_view)
        zoom_in = QPushButton("Zoom in", self)
        zoom_in.setObjectName("zoomInButton")
        zoom_in.clicked.connect(lambda: self.zoom_by(0.8))
        zoom_out = QPushButton("Zoom out", self)
        zoom_out.setObjectName("zoomOutButton")
        zoom_out.clicked.connect(lambda: self.zoom_by(1.25))
        self._frame_label = QLabel("No snapshot", self)
        self._frame_label.setObjectName("viewerFrameLabel")
        toolbar.addWidget(fit_button)
        toolbar.addWidget(zoom_in)
        toolbar.addWidget(zoom_out)
        toolbar.addStretch()
        toolbar.addWidget(self._frame_label)
        root.addLayout(toolbar)

        content = QHBoxLayout()
        controls = self._build_layer_controls()
        controls.setMaximumWidth(340)
        content.addWidget(controls)

        graphics = pg.GraphicsLayoutWidget(self)
        graphics.setObjectName("viewerGraphics")
        self._cells_plot = graphics.addPlot(row=0, col=0, title="Cells")
        self._cells_plot.setLabel("bottom", "x", units="m")
        self._cells_plot.setLabel("left", "y", units="m")
        self._cells_plot.setAspectLocked(True)
        self._cells_plot.setMouseEnabled(x=True, y=True)
        self._cell_item = QGraphicsPathItem()
        cell_pen = QPen(QColor("#d9f0ff"))
        cell_pen.setCosmetic(True)
        self._cell_item.setPen(cell_pen)
        self._cell_item.setBrush(QColor("#3a86ff"))
        self._cells_plot.addItem(self._cell_item)

        self._fields_plot = graphics.addPlot(row=0, col=1, title="Scalar fields")
        self._fields_plot.setLabel("bottom", "column index")
        self._fields_plot.setLabel("left", "row index")
        self._fields_plot.setAspectLocked(True)
        self._fields_plot.setMouseEnabled(x=True, y=True)
        for z_index, name in enumerate(FIELD_NAMES):
            style = _FIELD_STYLES[name]
            item = pg.ImageItem(axisOrder="row-major")
            color_map = pg.colormap.get(style.color_map)
            item.setLookupTable(color_map.getLookupTable(nPts=256, alpha=True))
            item.setZValue(z_index)
            item.setVisible(self._layer_visibility[name])
            self._fields_plot.addItem(item)
            self._field_items[name] = item
        content.addWidget(graphics, stretch=1)
        root.addLayout(content, stretch=1)

    def _build_layer_controls(self) -> QGroupBox:
        group = QGroupBox("Layers and legends", self)
        group.setObjectName("viewerLayerControls")
        layout = QVBoxLayout(group)
        layers = (
            ("cells", "Cells", "#3a86ff", "No cells"),
            *(
                (name, style.title, style.color, "No field")
                for name, style in _FIELD_STYLES.items()
            ),
        )
        for name, title, color, empty_text in layers:
            row = QHBoxLayout()
            swatch = QLabel(group)
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(f"background-color: {color}; border: 1px solid #555;")
            check = QCheckBox(title, group)
            check.setObjectName(f"{name}LayerCheck")
            check.setChecked(self._layer_visibility[name])
            check.toggled.connect(
                lambda checked, layer=name: self.set_layer_visible(layer, checked)
            )
            slider = QSlider(Qt.Orientation.Horizontal, group)
            slider.setObjectName(f"{name}OpacitySlider")
            slider.setRange(0, 100)
            slider.setValue(100)
            slider.setToolTip("Layer opacity")
            slider.valueChanged.connect(
                lambda value, layer=name: self.set_layer_opacity(layer, value / 100)
            )
            row.addWidget(swatch)
            row.addWidget(check)
            row.addWidget(slider)
            layout.addLayout(row)
            value_label = QLabel(empty_text, group)
            value_label.setObjectName(f"{name}LegendValue")
            value_label.setWordWrap(True)
            layout.addWidget(value_label)
            self._layer_checks[name] = check
            self._layer_sliders[name] = slider
            self._legend_values[name] = value_label
        layout.addStretch()
        return group

    def _render_snapshot(self, snapshot: RunSnapshot, *, now_ns: int) -> None:
        self._latest_snapshot = snapshot
        if self._layer_visibility["cells"]:
            self._render_cells(snapshot.cells)
        for field in snapshot.fields:
            if self._layer_visibility[field.name]:
                self._render_field(field)
        self._presented_frames += 1
        self._last_render_ns = now_ns
        self._frame_label.setText(
            f"Step {snapshot.step_index}/{snapshot.step_count} · "
            f"{snapshot.time_s:.6g} s"
        )

    def _render_cells(self, cells: tuple[CellSnapshot, ...]) -> None:
        path = QPainterPath()
        for cell in cells:
            capsule = QPainterPath()
            radius = cell.radius_m
            capsule.addRoundedRect(
                QRectF(
                    -cell.length_m / 2.0 - radius,
                    -radius,
                    cell.length_m + 2.0 * radius,
                    2.0 * radius,
                ),
                radius,
                radius,
            )
            transform = QTransform()
            transform.translate(cell.x_m, cell.y_m)
            transform.rotateRadians(cell.orientation_rad)
            path.addPath(transform.map(capsule))
        self._cell_item.setPath(path)
        self._cell_item.setOpacity(self._layer_opacity["cells"])
        self._legend_values["cells"].setText(f"{len(cells)} cells · SI geometry")
        self._cell_rebuilds += 1

    def _render_field(self, field: FieldSnapshot) -> None:
        item = self._field_items[field.name]
        values = field.as_array()
        minimum = float(np.min(values))
        maximum = float(np.max(values))
        item.setImage(values, autoLevels=False, levels=_color_levels(minimum, maximum))
        item.setRect(QRectF(0.0, 0.0, float(field.shape[1]), float(field.shape[0])))
        item.setOpacity(self._layer_opacity[field.name])
        self._legend_values[field.name].setText(
            f"{minimum:.6g} – {maximum:.6g} {field.unit}"
        )
        self._field_uploads[field.name] += 1

    def _present_pending_snapshot(self) -> None:
        snapshot = self._pending_snapshot
        if snapshot is None:
            return
        self._pending_snapshot = None
        self._render_snapshot(snapshot, now_ns=time.monotonic_ns())

    def _validate_snapshot(self, snapshot: RunSnapshot) -> None:
        if not isinstance(snapshot, RunSnapshot):
            raise ViewerError("snapshot must be a RunSnapshot")
        names = tuple(field.name for field in snapshot.fields)
        if len(set(names)) != len(names):
            raise ViewerError("snapshot scalar-field names must be unique")
        missing = tuple(name for name in FIELD_NAMES if name not in names)
        unsupported = tuple(name for name in names if name not in FIELD_NAMES)
        if missing or unsupported:
            raise ViewerError(
                "snapshot scalar fields must be exactly " + ", ".join(FIELD_NAMES)
            )

    def _require_layer(self, name: str) -> None:
        if name not in self._layer_visibility:
            raise ViewerError(f"unknown viewer layer {name!r}")

    def _require_field(self, name: str) -> None:
        if name not in self._field_items:
            raise ViewerError(f"unknown scalar-field layer {name!r}")

    @staticmethod
    def _pan(plot: pg.PlotItem, x: float, y: float) -> None:
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in (x, y)
        ):
            raise ViewerError("pan distances must be finite numbers")
        plot.getViewBox().translateBy(x=float(x), y=float(y))


def _color_levels(minimum: float, maximum: float) -> tuple[float, float]:
    if minimum != maximum:
        return minimum, maximum
    margin = max(abs(minimum), 1.0) * 1.0e-12
    return minimum - margin, maximum + margin
