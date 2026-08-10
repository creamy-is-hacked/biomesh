"""Snapshot-only live analytics for P3-WP06."""

from __future__ import annotations

from dataclasses import dataclass

import pyqtgraph as pg  # type: ignore[import-untyped]
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from biomesh.application_types import ApplicationError, RunSnapshot


@dataclass(frozen=True, slots=True)
class AnalyticsSeries:
    """One approved display series backed by an existing stored metric."""

    name: str
    title: str
    unit: str
    source_metric: str


@dataclass(frozen=True, slots=True)
class AnalyticsPlot:
    """One live plot containing one or more approved series."""

    name: str
    title: str
    series: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnalyticsRecord:
    """One exact scalar value taken from an immutable application snapshot."""

    step_index: int
    time_s: float
    series: str
    label: str
    unit: str
    value: float
    source_metric: str


ANALYTICS_SERIES: tuple[AnalyticsSeries, ...] = (
    AnalyticsSeries("population_cell_count", "Population", "1", "cell_count"),
    AnalyticsSeries(
        "total_dry_biomass_kg",
        "Total dry biomass",
        "kg",
        "total_dry_biomass_kg",
    ),
    AnalyticsSeries(
        "producer_cell_frequency",
        "Strain ratio (producer cell fraction)",
        "1",
        "producer_cell_frequency",
    ),
    AnalyticsSeries("total_eps_kg", "Total EPS", "kg", "total_eps_kg"),
    AnalyticsSeries(
        "quorum_active_fraction",
        "Quorum-active fraction",
        "1",
        "quorum_active_fraction",
    ),
    AnalyticsSeries(
        "biofilm_thickness_m",
        "Biofilm thickness",
        "m",
        "biofilm_thickness_m",
    ),
    AnalyticsSeries(
        "biofilm_roughness_m",
        "Biofilm roughness",
        "m",
        "biofilm_roughness_m",
    ),
    AnalyticsSeries(
        "carbon_penetration_depth_m",
        "Carbon penetration depth",
        "m",
        "carbon_penetration_depth_m",
    ),
    AnalyticsSeries(
        "oxygen_penetration_depth_m",
        "Oxygen penetration depth",
        "m",
        "oxygen_penetration_depth_m",
    ),
)

ANALYTICS_PLOTS: tuple[AnalyticsPlot, ...] = (
    AnalyticsPlot("population", "Population", ("population_cell_count",)),
    AnalyticsPlot("biomass", "Biomass", ("total_dry_biomass_kg",)),
    AnalyticsPlot(
        "strain_ratio", "Strain ratio", ("producer_cell_frequency",)
    ),
    AnalyticsPlot("eps", "EPS", ("total_eps_kg",)),
    AnalyticsPlot(
        "quorum_active_fraction",
        "Quorum-active fraction",
        ("quorum_active_fraction",),
    ),
    AnalyticsPlot("thickness", "Thickness", ("biofilm_thickness_m",)),
    AnalyticsPlot("roughness", "Roughness", ("biofilm_roughness_m",)),
    AnalyticsPlot(
        "penetration_depth",
        "Penetration depth",
        ("carbon_penetration_depth_m", "oxygen_penetration_depth_m"),
    ),
)

_SERIES_BY_NAME = {series.name: series for series in ANALYTICS_SERIES}
_METRIC_UNITS = {
    series.source_metric: series.unit
    for series in ANALYTICS_SERIES
    if series.source_metric != "cell_count"
}
_PENS = ("#4cc9f0", "#f72585")


class AnalyticsHistory:
    """Retain only immutable public snapshots for one current run."""

    def __init__(self) -> None:
        self._identity: tuple[str, int, str] | None = None
        self._snapshots: dict[int, RunSnapshot] = {}

    @property
    def snapshots(self) -> tuple[RunSnapshot, ...]:
        """Return accepted snapshots in deterministic solver order."""
        return tuple(self._snapshots[index] for index in sorted(self._snapshots))

    @property
    def records(self) -> tuple[AnalyticsRecord, ...]:
        """Return exact plot records in solver and declared-series order."""
        return analytics_records(self.snapshots)

    def clear(self) -> None:
        """Discard presentation history without touching application state."""
        self._identity = None
        self._snapshots.clear()

    def accept_snapshot(self, snapshot: RunSnapshot) -> None:
        """Accept or replace one immutable solver-boundary snapshot."""
        if not isinstance(snapshot, RunSnapshot):
            raise ApplicationError("analytics requires a RunSnapshot")
        identity = (
            snapshot.condition_id,
            snapshot.seed,
            snapshot.configuration_sha256,
        )
        if snapshot.step_index == 0 or self._identity != identity:
            self.clear()
            self._identity = identity
        self._snapshots[snapshot.step_index] = snapshot


def analytics_records(
    snapshots: tuple[RunSnapshot, ...],
) -> tuple[AnalyticsRecord, ...]:
    """Extract approved values without conversion, inference, or fallback."""
    if not snapshots:
        return ()
    ordered = tuple(sorted(snapshots, key=lambda item: item.step_index))
    identity = (
        ordered[0].condition_id,
        ordered[0].seed,
        ordered[0].configuration_sha256,
    )
    if len({item.step_index for item in ordered}) != len(ordered):
        raise ApplicationError("analytics snapshots contain duplicate step indices")
    records: list[AnalyticsRecord] = []
    for snapshot in ordered:
        if (
            snapshot.condition_id,
            snapshot.seed,
            snapshot.configuration_sha256,
        ) != identity:
            raise ApplicationError("analytics snapshots must belong to one run")
        if not snapshot.metrics:
            continue
        metrics = {metric.name: metric for metric in snapshot.metrics}
        if len(metrics) != len(snapshot.metrics):
            raise ApplicationError("snapshot metrics contain duplicate names")
        for name, expected_unit in _METRIC_UNITS.items():
            metric = metrics.get(name)
            if metric is None:
                raise ApplicationError(
                    f"snapshot is missing required stored metric {name!r}"
                )
            if metric.unit != expected_unit:
                raise ApplicationError(
                    f"stored metric {name!r} must use unit {expected_unit!r}"
                )
        for series in ANALYTICS_SERIES:
            value = (
                float(len(snapshot.cells))
                if series.source_metric == "cell_count"
                else metrics[series.source_metric].value
            )
            records.append(
                AnalyticsRecord(
                    step_index=snapshot.step_index,
                    time_s=snapshot.time_s,
                    series=series.name,
                    label=series.title,
                    unit=series.unit,
                    value=value,
                    source_metric=series.source_metric,
                )
            )
    return tuple(records)


def series_records(
    records: tuple[AnalyticsRecord, ...], series_name: str
) -> tuple[AnalyticsRecord, ...]:
    """Select one known series while retaining deterministic time order."""
    if series_name not in _SERIES_BY_NAME:
        raise ApplicationError(f"unknown analytics series {series_name!r}")
    return tuple(record for record in records if record.series == series_name)


class AnalyticsPanel(QWidget):
    """PyQtGraph live plots populated only from immutable snapshot history."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("analyticsPanel")
        self._history = AnalyticsHistory()
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._value_labels: dict[str, QLabel] = {}
        self._build_ui()

    @property
    def history(self) -> AnalyticsHistory:
        """Expose snapshot-only presentation history for export integration."""
        return self._history

    def accept_snapshot(self, snapshot: RunSnapshot) -> None:
        """Refresh every plot from the current immutable history."""
        self._history.accept_snapshot(snapshot)
        records = self._history.records
        for series in ANALYTICS_SERIES:
            selected = series_records(records, series.name)
            self._curves[series.name].setData(
                [item.time_s for item in selected],
                [item.value for item in selected],
            )
            label = self._value_labels[series.name]
            label.setText(
                "No stored value"
                if not selected
                else f"{selected[-1].value:.17g} {series.unit}"
            )

    def series_values(self, series_name: str) -> tuple[tuple[float, float], ...]:
        """Return exact displayed coordinates for focused headless tests."""
        return tuple(
            (record.time_s, record.value)
            for record in series_records(self._history.records, series_name)
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        boundary = QLabel(
            "Plots use immutable public snapshots and existing stored SI metrics. "
            "Strain ratio is the stored producer cell frequency; no missing "
            "scientific quantity is inferred.",
            self,
        )
        boundary.setObjectName("analyticsBoundary")
        boundary.setWordWrap(True)
        root.addWidget(boundary)
        grid = QGridLayout()
        for index, plot in enumerate(ANALYTICS_PLOTS):
            group = QGroupBox(plot.title, self)
            group.setObjectName(f"{plot.name}AnalyticsPlot")
            layout = QVBoxLayout(group)
            chart = pg.PlotWidget(group)
            chart.setLabel("bottom", "time", units="s")
            chart.setLabel("left", "value", units=_SERIES_BY_NAME[plot.series[0]].unit)
            chart.showGrid(x=True, y=True, alpha=0.2)
            if len(plot.series) > 1:
                chart.addLegend()
            for series_index, series_name in enumerate(plot.series):
                series = _SERIES_BY_NAME[series_name]
                curve = chart.plot(
                    [],
                    [],
                    pen=pg.mkPen(_PENS[series_index], width=2),
                    name=series.title,
                )
                self._curves[series_name] = curve
                value_label = QLabel("No stored value", group)
                value_label.setObjectName(f"{series_name}AnalyticsValue")
                layout.addWidget(value_label)
                self._value_labels[series_name] = value_label
            layout.insertWidget(0, chart)
            grid.addWidget(group, index // 2, index % 2)
        root.addLayout(grid)
