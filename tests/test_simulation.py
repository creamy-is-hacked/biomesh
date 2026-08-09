"""P1-WP07 orchestration, global accounting, and deterministic replay tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from biomesh.cells import Cell, CellModelParameters
from biomesh.mass_balance import (
    solute_amount_mol,
    top_boundary_input_rate_mol_s,
)
from biomesh.mechanics import MechanicsParameters
from biomesh.metabolism import MetabolismParameters
from biomesh.outputs import RunMetadata, SimulationOutputWriter
from biomesh.simulation import (
    SimulationParameters,
    SimulationValidationError,
    run_simulation,
)
from biomesh.solutes import SoluteField, SoluteFields


def _fields() -> SoluteFields:
    return SoluteFields(
        carbon=SoluteField(
            "carbon",
            (2, 2),
            1.0,
            1.0,
            0.01,
            4.0,
            np.full((2, 2), 3.0, dtype=np.float64),
        ),
        oxygen=SoluteField(
            "oxygen",
            (2, 2),
            1.0,
            1.0,
            0.01,
            6.0,
            np.full((2, 2), 5.0, dtype=np.float64),
        ),
    )


def _cell() -> Cell:
    return Cell(
        cell_id="cell-000000000000",
        x_m=0.5,
        y_m=0.25,
        orientation_rad=0.0,
        length_m=0.2,
        radius_m=0.02,
        dry_biomass_kg=0.2,
        age_s=0.0,
        state="active",
        strain="synthetic-validation",
    )


def _parameters() -> SimulationParameters:
    return SimulationParameters(
        time_step_s=0.1,
        step_count=1,
        depth_m=1.0,
        cell_model=CellModelParameters(1.0, 0.2, 0.01),
        metabolism=MetabolismParameters(0.4, 2.0, 4.0, 0.1, 2.0, 4.0),
        mechanics=MechanicsParameters(1.0, 1.0e-12, 100, 1.0, "bottom"),
        mass_balance_absolute_tolerance=1.0e-12,
        mass_balance_relative_tolerance=1.0e-12,
        next_cell_sequence=1,
    )


def _metadata() -> RunMetadata:
    return RunMetadata(
        seed=42,
        parameters={"purpose": "synthetic orchestration test"},
        package_version="0.0.0",
        commit_hash="test",
        dependency_versions={"numpy": "test"},
        parameter_file="synthetic.toml",
        parameter_file_sha256="0" * 64,
        platform="test",
        python_version="3.14.test",
    )


def _run(path: Path) -> Path:
    result = run_simulation(
        initial_cells=(_cell(),),
        initial_solute_fields=_fields(),
        parameters=_parameters(),
        seed=42,
        output_writer=SimulationOutputWriter(path, _metadata()),
    )
    assert len(result.cells) == 2
    assert result.maximum_overlap_m <= 1.0e-12
    assert all(
        abs(entry.residual_amount) <= entry.allowed_residual_amount
        for entry in result.mass_balance_entries
    )
    return result.output_paths.run_directory


def test_top_boundary_flux_matches_discrete_global_amount_change() -> None:
    field = SoluteField(
        "synthetic",
        (2, 2),
        2.0,
        2.0,
        0.5,
        3.0,
        np.ones((2, 2), dtype=np.float64),
    )
    depth_m = 4.0
    time_step_s = field.maximum_stable_timestep_s / 2.0
    initial_mol = solute_amount_mol(field, depth_m)
    expected_input_mol = (
        top_boundary_input_rate_mol_s(field, depth_m) * time_step_s
    )

    field.advance(time_step_s)

    assert solute_amount_mol(field, depth_m) - initial_mol == pytest.approx(
        expected_input_mol
    )


def test_orchestrator_integrates_components_and_replays_byte_identically(
    tmp_path: Path,
) -> None:
    first = _run(tmp_path / "first")
    second = _run(tmp_path / "second")

    first_files = sorted(
        path.relative_to(first) for path in first.rglob("*") if path.is_file()
    )
    second_files = sorted(
        path.relative_to(second) for path in second.rglob("*") if path.is_file()
    )
    assert first_files == second_files
    assert all(
        (first / path).read_bytes() == (second / path).read_bytes()
        for path in first_files
    )
    events = pq.read_table(first / "division_events.parquet").to_pydict()
    assert events["parent_cell_id"] == ["cell-000000000000"]
    balances = pq.read_table(first / "mass_balance.parquet").to_pydict()
    assert set(balances["quantity"]) == {
        "carbon_equivalent",
        "dry_biomass",
        "oxygen_equivalent",
    }
    assert max(abs(value) for value in balances["residual_amount"]) <= 1.0e-12


def test_orchestrator_rejects_a_seed_not_recorded_in_provenance(
    tmp_path: Path,
) -> None:
    writer = SimulationOutputWriter(tmp_path / "run", _metadata())

    with pytest.raises(SimulationValidationError, match="recorded"):
        run_simulation(
            initial_cells=(_cell(),),
            initial_solute_fields=_fields(),
            parameters=_parameters(),
            seed=43,
            output_writer=writer,
        )
