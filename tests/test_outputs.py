"""P1-WP06 deterministic scientific-output verification."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from biomesh.cells import Cell
from biomesh.outputs import (
    DivisionEvent,
    MassBalanceEntry,
    OutputValidationError,
    RunMetadata,
    SimulationOutputWriter,
)
from biomesh.solutes import SoluteField, SoluteFields


def _cells() -> tuple[Cell, Cell]:
    """Return deliberately unsorted synthetic capsule state in SI units."""
    return (
        Cell(
            cell_id="cell-b",
            x_m=0.75,
            y_m=0.7,
            orientation_rad=0.0,
            length_m=0.4,
            radius_m=0.1,
            dry_biomass_kg=2.0,
            age_s=3.0,
            state="active",
            strain="synthetic",
        ),
        Cell(
            cell_id="cell-a",
            x_m=0.25,
            y_m=0.4,
            orientation_rad=0.0,
            length_m=0.2,
            radius_m=0.1,
            dry_biomass_kg=1.0,
            age_s=2.0,
            state="active",
            strain="synthetic",
            parent_id="founder",
        ),
    )


def _fields() -> SoluteFields:
    """Return synthetic, caller-provided solute state in SI units."""
    return SoluteFields(
        carbon=SoluteField(
            "carbon",
            (2, 2),
            1.0,
            2.0,
            0.1,
            3.0,
            np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64),
        ),
        oxygen=SoluteField(
            "oxygen",
            (2, 2),
            1.0,
            2.0,
            0.2,
            5.0,
            np.array([[6.0, 7.0], [8.0, 9.0]], dtype=np.float64),
        ),
    )


def _metadata() -> RunMetadata:
    """Return complete, serializable provenance without scientific values."""
    return RunMetadata(
        seed=42,
        parameters={"nested": {"beta": 2, "alpha": 1}, "schema_version": 1},
        package_version="0.0.0",
        commit_hash="abc123",
        dependency_versions={"numpy": "test", "pyarrow": "test"},
        parameter_file="parameters/test.toml",
        parameter_file_sha256="123456",
        platform="synthetic-platform",
        python_version="3.14.test",
    )


def _mass_balance() -> tuple[MassBalanceEntry, MassBalanceEntry]:
    """Return mass-balance inputs with explicit units and tolerances."""
    return (
        MassBalanceEntry(
            quantity="carbon",
            unit="mol",
            initial_amount=5.0,
            final_amount=4.0,
            net_input_amount=-1.0,
            absolute_tolerance=1.0e-9,
            relative_tolerance=1.0e-12,
        ),
        MassBalanceEntry(
            quantity="biomass",
            unit="kg",
            initial_amount=1.0,
            final_amount=3.0,
            net_input_amount=2.0,
            absolute_tolerance=1.0e-12,
            relative_tolerance=1.0e-12,
        ),
    )


def _write_one_snapshot(path: Path) -> Path:
    """Write a fixed output fixture and return its run directory."""
    writer = SimulationOutputWriter(path, _metadata())
    writer.write_snapshot(
        time_s=4.0,
        cells=_cells(),
        solute_fields=_fields(),
        division_events=(
            DivisionEvent(
                parent_cell_id="founder",
                first_daughter_cell_id="cell-a",
                second_daughter_cell_id="cell-b",
            ),
        ),
        mass_balance_entries=_mass_balance(),
    )
    return writer.finalize().run_directory


def test_writer_exports_complete_si_state_and_provenance(tmp_path: Path) -> None:
    """A snapshot produces all P1 tables, fields, metrics, and run metadata."""
    cells = _cells()
    fields = _fields()
    carbon_before = fields.carbon.concentration_mol_m3.copy()
    oxygen_before = fields.oxygen.concentration_mol_m3.copy()
    writer = SimulationOutputWriter(tmp_path / "run", _metadata())

    writer.write_snapshot(
        time_s=4.0,
        cells=cells,
        solute_fields=fields,
        division_events=(
            DivisionEvent("founder", "cell-a", "cell-b"),
        ),
        mass_balance_entries=_mass_balance(),
    )
    paths = writer.finalize()

    assert np.array_equal(fields.carbon.concentration_mol_m3, carbon_before)
    assert np.array_equal(fields.oxygen.concentration_mol_m3, oxygen_before)
    assert paths.run_directory == tmp_path / "run"
    assert paths.cells_table.is_file()
    assert paths.summary_table.is_file()
    assert paths.division_events_table.is_file()
    assert paths.mass_balance_table.is_file()
    assert paths.metadata_file.is_file()
    assert paths.quorum_history_table is None
    assert paths.field_files == (tmp_path / "run" / "fields" / "000000.npz",)

    cells_table = pq.read_table(paths.cells_table).to_pydict()
    assert cells_table["cell_id"] == ["cell-a", "cell-b"]
    assert cells_table["parent_id"] == ["founder", None]
    assert cells_table["x_m"] == [0.25, 0.75]
    assert cells_table["dry_biomass_kg"] == [1.0, 2.0]

    summary = pq.read_table(paths.summary_table).to_pydict()
    assert summary["time_s"] == [4.0]
    assert summary["total_dry_biomass_kg"] == [3.0]
    assert summary["cell_count"] == [2]
    assert summary["division_event_count"] == [1]
    assert summary["biofilm_height_m"] == [pytest.approx(0.8)]
    assert summary["biofilm_roughness_m"] == [pytest.approx(0.15)]

    events = pq.read_table(paths.division_events_table).to_pydict()
    assert events == {
        "time_s": [4.0],
        "parent_cell_id": ["founder"],
        "first_daughter_cell_id": ["cell-a"],
        "second_daughter_cell_id": ["cell-b"],
    }
    mass_balance = pq.read_table(paths.mass_balance_table).to_pydict()
    assert mass_balance["quantity"] == ["biomass", "carbon"]
    assert mass_balance["residual_amount"] == [0.0, 0.0]
    assert mass_balance["unit"] == ["kg", "mol"]

    with np.load(paths.field_files[0], allow_pickle=False) as field_data:
        assert np.array_equal(field_data["carbon_concentration_mol_m3"], carbon_before)
        assert np.array_equal(field_data["oxygen_concentration_mol_m3"], oxygen_before)
        assert field_data["width_m"].item() == 1.0
        assert field_data["height_m"].item() == 2.0

    metadata = json.loads(paths.metadata_file.read_text(encoding="utf-8"))
    assert metadata == {
        "commit_hash": "abc123",
        "dependency_versions": {"numpy": "test", "pyarrow": "test"},
        "package_version": "0.0.0",
        "parameter_file": "parameters/test.toml",
        "parameter_file_sha256": "123456",
        "parameters": {"nested": {"alpha": 1, "beta": 2}, "schema_version": 1},
        "platform": "synthetic-platform",
        "python_version": "3.14.test",
        "seed": 42,
    }


def test_identical_state_produces_byte_identical_exports(tmp_path: Path) -> None:
    """Canonical ordering and fixed archive metadata make exports reproducible."""
    first = _write_one_snapshot(tmp_path / "first")
    second = _write_one_snapshot(tmp_path / "second")

    first_files = sorted(
        path.relative_to(first) for path in first.rglob("*") if path.is_file()
    )
    second_files = sorted(
        path.relative_to(second) for path in second.rglob("*") if path.is_file()
    )
    assert first_files == second_files
    for relative_path in first_files:
        assert (first / relative_path).read_bytes() == (
            second / relative_path
        ).read_bytes()


def test_snapshot_input_and_lifecycle_failures_are_explicit(tmp_path: Path) -> None:
    """The writer rejects ambiguous records and unsafe output lifecycle changes."""
    writer = SimulationOutputWriter(tmp_path / "run", _metadata())

    with pytest.raises(OutputValidationError, match="unique"):
        writer.write_snapshot(
            time_s=0.0,
            cells=(_cells()[0], _cells()[0]),
            solute_fields=_fields(),
            division_events=(),
            mass_balance_entries=_mass_balance(),
        )

    writer.write_snapshot(
        time_s=0.0,
        cells=(),
        solute_fields=_fields(),
        division_events=(),
        mass_balance_entries=_mass_balance(),
    )
    writer.finalize()

    with pytest.raises(OutputValidationError, match="finalized"):
        writer.write_snapshot(
            time_s=1.0,
            cells=(),
            solute_fields=_fields(),
            division_events=(),
            mass_balance_entries=_mass_balance(),
        )
    with pytest.raises(
        OutputValidationError, match="output run directory already exists"
    ):
        SimulationOutputWriter(tmp_path / "run", _metadata())


def test_writer_rejects_mass_balance_outside_declared_tolerance(
    tmp_path: Path,
) -> None:
    """A failed conservation gate cannot be serialized as an accepted snapshot."""
    writer = SimulationOutputWriter(tmp_path / "run", _metadata())
    failed_balance = MassBalanceEntry(
        quantity="carbon",
        unit="mol",
        initial_amount=1.0,
        final_amount=0.5,
        net_input_amount=0.0,
        absolute_tolerance=1.0e-12,
        relative_tolerance=0.0,
    )

    with pytest.raises(OutputValidationError, match="carbon"):
        writer.write_snapshot(
            time_s=0.0,
            cells=_cells(),
            solute_fields=_fields(),
            division_events=(),
            mass_balance_entries=(failed_balance,),
        )
