"""Immutable P3-WP05 cell-inspection presentation."""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from biomesh.application_types import CellInspection, LocalValue


class CellInspector(QWidget):
    """Display only values returned by ``ApplicationService.inspect``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("cellInspector")
        self._inspection: CellInspection | None = None
        layout = QVBoxLayout(self)
        self._summary = QLabel("Click a cell in the snapshot viewer.", self)
        self._summary.setObjectName("inspectionSummary")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)
        form = QFormLayout()
        self._values: dict[str, QLabel] = {}
        for key, title in (
            ("lineage", "Lineage"),
            ("strain", "Strain"),
            ("biomass", "Dry biomass"),
            ("state", "Physiological state"),
            ("solutes", "Local solutes"),
            ("quorum", "Quorum activity"),
            ("eps", "EPS rate/value"),
        ):
            label = QLabel("—", self)
            label.setObjectName(f"inspection_{key}")
            label.setWordWrap(True)
            form.addRow(title, label)
            self._values[key] = label
        layout.addLayout(form)
        layout.addStretch()

    @property
    def inspection(self) -> CellInspection | None:
        """Return the exact immutable record currently displayed."""
        return self._inspection

    def present_inspection(self, inspection: CellInspection) -> None:
        """Render one public record without querying or retaining solver state."""
        if not isinstance(inspection, CellInspection):
            raise ValueError("inspection must be a CellInspection")
        self._inspection = inspection
        cell = inspection.cell
        self._summary.setText(f"Cell {cell.cell_id} at immutable solver boundary")
        self._values["lineage"].setText(
            f"cell {cell.cell_id}; parent {cell.parent_id or 'none (root)'}"
        )
        self._values["strain"].setText(cell.strain)
        self._values["biomass"].setText(f"{cell.dry_biomass_kg:.17g} kg")
        self._values["state"].setText(cell.state)
        local = {item.name: item for item in inspection.local_values}
        solutes = tuple(
            local[name]
            for name in ("carbon", "oxygen", "quorum_signal", "waste")
            if name in local
        )
        self._values["solutes"].setText(
            "; ".join(_local_text(item) for item in solutes)
        )
        self._values["quorum"].setText(
            f"activation fraction {inspection.quorum_activation_fraction:.17g} 1"
        )
        eps = local.get("eps")
        eps_text = _local_text(eps) if eps is not None else "not present"
        self._values["eps"].setText(
            f"local value {eps_text}; per-cell EPS rate is not exposed by the "
            "immutable P3-WP01 inspection record"
        )


def _local_text(value: LocalValue) -> str:
    return f"{value.name} {value.value:.17g} {value.unit}"
