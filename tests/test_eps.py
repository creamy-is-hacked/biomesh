"""P2-WP02 quorum-controlled EPS allocation and interaction verification."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from biomesh.cells import Cell
from biomesh.eps import (
    EPSField,
    EPSParameters,
    EPSValidationError,
    advance_eps_metabolism,
    local_mechanical_modifiers,
)
from biomesh.metabolism import MetabolismParameters
from biomesh.outputs import MassBalanceEntry, RunMetadata, SimulationOutputWriter
from biomesh.quorum import CellQuorumState, QuorumObservation
from biomesh.solutes import SoluteField, SoluteFields


def _cell(cell_id: str = "cell-a", *, x_m: float = 0.25) -> Cell:
    return Cell(
        cell_id=cell_id,
        x_m=x_m,
        y_m=0.25,
        orientation_rad=0.0,
        length_m=0.5,
        radius_m=0.05,
        dry_biomass_kg=1.0,
        age_s=0.0,
        state="active",
        strain="synthetic-validation",
    )


def _fields() -> SoluteFields:
    concentration = np.full((2, 2), 20.0, dtype=np.float64)
    return SoluteFields(
        carbon=SoluteField(
            "carbon", (2, 2), 1.0, 1.0, 0.0, 0.0, concentration
        ),
        oxygen=SoluteField(
            "oxygen", (2, 2), 1.0, 1.0, 0.0, 0.0, concentration
        ),
    )


def _eps_field(
    density_kg_m3: np.ndarray[tuple[int, int], np.dtype[np.float64]] | None = None,
) -> EPSField:
    return EPSField(
        shape=(2, 2),
        width_m=1.0,
        height_m=1.0,
        depth_m=1.0,
        density_kg_m3=(
            np.zeros((2, 2), dtype=np.float64)
            if density_kg_m3 is None
            else density_kg_m3
        ),
    )


def _eps_parameters(
    *,
    maximum_allocation_fraction: float = 0.4,
    cohesion_sensitivity_m3_kg: float = 2.0,
    attachment_strength_sensitivity_m3_kg: float = 3.0,
) -> EPSParameters:
    return EPSParameters(
        maximum_allocation_fraction=maximum_allocation_fraction,
        cohesion_sensitivity_m3_kg=cohesion_sensitivity_m3_kg,
        attachment_strength_sensitivity_m3_kg=(
            attachment_strength_sensitivity_m3_kg
        ),
    )


def _metabolism_parameters(*, death_rate_s: float = 0.0) -> MetabolismParameters:
    return MetabolismParameters(
        maximum_specific_growth_rate_s=0.4,
        carbon_half_saturation_mol_m3=2.0,
        oxygen_half_saturation_mol_m3=4.0,
        death_rate_s=death_rate_s,
        biomass_yield_on_carbon_kg_mol=2.0,
        biomass_yield_on_oxygen_kg_mol=4.0,
    )


def _quorum_state(
    cell_id: str = "cell-a",
    *,
    activation_fraction: float,
    time_s: float = 0.0,
) -> CellQuorumState:
    return CellQuorumState(
        cell_id=cell_id,
        history=(
            QuorumObservation(
                time_s=time_s,
                signal_concentration_mol_m3=1.0,
                activation_fraction=activation_fraction,
            ),
        ),
    )


def _advance(
    *,
    cell: Cell | None = None,
    fields: SoluteFields | None = None,
    eps_field: EPSField | None = None,
    activation_fraction: float = 0.5,
    allocation_fraction: float = 0.4,
    time_s: float = 0.0,
    death_rate_s: float = 0.0,
):
    selected_cell = _cell() if cell is None else cell
    selected_fields = _fields() if fields is None else fields
    selected_eps = _eps_field() if eps_field is None else eps_field
    result = advance_eps_metabolism(
        cells=(selected_cell,),
        solute_fields=selected_fields,
        eps_field=selected_eps,
        quorum_states=(
            _quorum_state(
                selected_cell.cell_id,
                activation_fraction=activation_fraction,
                time_s=time_s,
            ),
        ),
        eps_parameters=_eps_parameters(
            maximum_allocation_fraction=allocation_fraction
        ),
        metabolism_parameters=_metabolism_parameters(death_rate_s=death_rate_s),
        time_step_s=0.5,
        start_time_s=time_s,
        dry_biomass_per_unit_length_kg_m=2.0,
    )
    return result, selected_fields, selected_eps


def test_eps_production_uses_quorum_scaled_allocation() -> None:
    """EPS receives exactly f_EPS times Q times gross anabolic production."""
    result, _, eps_field = _advance(
        activation_fraction=0.5,
        allocation_fraction=0.4,
    )

    metabolism = result.metabolism.cell_results[0]
    production = result.cell_production[0]
    assert production.allocation_fraction == pytest.approx(0.2)
    assert production.produced_eps_kg == pytest.approx(
        0.2 * metabolism.gross_biomass_production_kg
    )
    assert production.produced_eps_kg == pytest.approx(
        metabolism.allocated_biomass_equivalent_kg
    )
    assert eps_field.density_kg_m3[1, 0] == pytest.approx(
        production.produced_eps_kg / eps_field.control_volume_m3
    )
    assert np.count_nonzero(eps_field.density_kg_m3) == 1


def test_eps_accumulates_without_unapproved_loss_or_transport() -> None:
    """Consecutive production adds locally to existing immobile EPS mass."""
    fields = _fields()
    eps_field = _eps_field(np.full((2, 2), 0.25, dtype=np.float64))
    initial_eps_kg = eps_field.total_mass_kg
    first, _, _ = _advance(fields=fields, eps_field=eps_field)
    after_first_kg = eps_field.total_mass_kg
    second, _, _ = _advance(
        cell=first.cells[0],
        fields=fields,
        eps_field=eps_field,
        time_s=0.5,
    )

    assert after_first_kg == pytest.approx(
        initial_eps_kg + first.mass_balance.produced_eps_kg
    )
    assert eps_field.total_mass_kg == pytest.approx(
        after_first_kg + second.mass_balance.produced_eps_kg
    )
    assert eps_field.density_kg_m3[0, 1] == 0.25


def test_higher_allocation_reduces_isolated_producer_growth() -> None:
    """The configured EPS fraction is charged to retained producer biomass."""
    no_cost, _, _ = _advance(
        activation_fraction=1.0,
        allocation_fraction=0.0,
    )
    with_cost, _, _ = _advance(
        activation_fraction=1.0,
        allocation_fraction=0.6,
    )

    assert with_cost.cells[0].dry_biomass_kg < no_cost.cells[0].dry_biomass_kg
    assert with_cost.mass_balance.produced_eps_kg > 0.0
    assert no_cost.mass_balance.produced_eps_kg == 0.0


def test_zero_quorum_activation_prevents_eps_allocation() -> None:
    """The exact P2 equation gives no EPS allocation when Q is zero."""
    result, _, eps_field = _advance(
        activation_fraction=0.0,
        allocation_fraction=1.0,
    )

    assert result.cell_production[0].allocation_fraction == 0.0
    assert result.mass_balance.produced_eps_kg == 0.0
    assert eps_field.total_mass_kg == 0.0


def test_allocated_biomass_and_substrate_equivalents_are_conserved() -> None:
    """Living biomass, EPS, death, and both substrate yields reconcile."""
    fields = _fields()
    initial_carbon_mol = float(np.sum(fields.carbon.concentration_mol_m3)) * 0.25
    initial_oxygen_mol = float(np.sum(fields.oxygen.concentration_mol_m3)) * 0.25
    result, fields, _ = _advance(
        fields=fields,
        activation_fraction=0.75,
        allocation_fraction=0.6,
        death_rate_s=0.1,
    )
    final_carbon_mol = float(np.sum(fields.carbon.concentration_mol_m3)) * 0.25
    final_oxygen_mol = float(np.sum(fields.oxygen.concentration_mol_m3)) * 0.25
    metabolism = result.metabolism.cell_results[0]

    assert abs(result.mass_balance.eps_residual_kg) < 1.0e-15
    assert abs(result.mass_balance.biomass_equivalent_residual_kg) < 1.0e-15
    assert initial_carbon_mol - final_carbon_mol == pytest.approx(
        metabolism.gross_biomass_production_kg / 2.0
    )
    assert initial_oxygen_mol - final_oxygen_mol == pytest.approx(
        metabolism.gross_biomass_production_kg / 4.0
    )


def test_adhesion_and_cohesion_increase_monotonically_with_local_eps() -> None:
    """Controlled local densities produce monotone mechanical modifiers."""
    eps_field = _eps_field(
        np.array([[0.0, 1.0], [2.0, 4.0]], dtype=np.float64)
    )
    parameters = _eps_parameters()
    low = local_mechanical_modifiers(
        eps_field=eps_field,
        x_m=0.75,
        y_m=0.75,
        parameters=parameters,
    )
    high = local_mechanical_modifiers(
        eps_field=eps_field,
        x_m=0.75,
        y_m=0.25,
        parameters=parameters,
    )

    assert low.eps_density_kg_m3 == 1.0
    assert high.eps_density_kg_m3 == 4.0
    assert high.cohesion_multiplier > low.cohesion_multiplier > 1.0
    assert (
        high.attachment_strength_multiplier
        > low.attachment_strength_multiplier
        > 1.0
    )


def _metadata() -> RunMetadata:
    return RunMetadata(
        seed=11,
        parameters={"purpose": "synthetic P2-WP02 replay"},
        package_version="0.0.0",
        commit_hash="test",
        dependency_versions={"numpy": "test"},
        parameter_file="synthetic.toml",
        parameter_file_sha256="0" * 64,
        platform="test",
        python_version="3.14.test",
    )


def _eps_balance(initial_kg: float, final_kg: float) -> tuple[MassBalanceEntry, ...]:
    return (
        MassBalanceEntry(
            quantity="eps",
            unit="kg",
            initial_amount=initial_kg,
            final_amount=final_kg,
            net_input_amount=final_kg - initial_kg,
            absolute_tolerance=1.0e-12,
            relative_tolerance=1.0e-12,
        ),
    )


def _write_eps_replay(run_directory: Path) -> Path:
    fields = _fields()
    eps_field = _eps_field()
    cell = _cell()
    writer = SimulationOutputWriter(run_directory, _metadata())
    writer.write_snapshot(
        time_s=0.0,
        cells=(cell,),
        solute_fields=fields,
        division_events=(),
        mass_balance_entries=_eps_balance(0.0, 0.0),
        eps_field=eps_field,
    )
    for step_index in range(2):
        initial_eps_kg = eps_field.total_mass_kg
        result, _, _ = _advance(
            cell=cell,
            fields=fields,
            eps_field=eps_field,
            time_s=step_index * 0.5,
        )
        cell = result.cells[0]
        writer.write_snapshot(
            time_s=(step_index + 1) * 0.5,
            cells=(cell,),
            solute_fields=fields,
            division_events=(),
            mass_balance_entries=_eps_balance(
                initial_eps_kg, eps_field.total_mass_kg
            ),
            eps_field=eps_field,
        )
    paths = writer.finalize()
    assert paths.eps_summary_table is not None
    summary = pq.read_table(paths.eps_summary_table).to_pydict()
    assert summary["total_eps_kg"][-1] == pytest.approx(eps_field.total_mass_kg)
    with np.load(paths.field_files[-1], allow_pickle=False) as archive:
        assert np.array_equal(archive["eps_density_kg_m3"], eps_field.density_kg_m3)
        assert archive["eps_depth_m"].item() == eps_field.depth_m
    return paths.run_directory


def test_deterministic_replay_includes_eps_accumulation_outputs(
    tmp_path: Path,
) -> None:
    """Identical inputs reproduce EPS state, summaries, and bytes exactly."""
    first = _write_eps_replay(tmp_path / "first")
    second = _write_eps_replay(tmp_path / "second")
    relative_files = sorted(
        path.relative_to(first) for path in first.rglob("*") if path.is_file()
    )

    assert relative_files == sorted(
        path.relative_to(second) for path in second.rglob("*") if path.is_file()
    )
    assert all(
        (first / path).read_bytes() == (second / path).read_bytes()
        for path in relative_files
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"maximum_allocation_fraction": -0.1}, "within"),
        ({"maximum_allocation_fraction": 1.1}, "within"),
        ({"cohesion_sensitivity_m3_kg": -1.0}, "cohesion"),
        ({"attachment_strength_sensitivity_m3_kg": float("nan")}, "attachment"),
    ],
)
def test_invalid_eps_parameters_fail_explicitly(
    changes: dict[str, float],
    message: str,
) -> None:
    """Nonphysical EPS inputs are rejected rather than corrected."""
    values = {
        "maximum_allocation_fraction": 0.4,
        "cohesion_sensitivity_m3_kg": 2.0,
        "attachment_strength_sensitivity_m3_kg": 3.0,
    }
    values.update(changes)

    with pytest.raises(EPSValidationError, match=message):
        EPSParameters(**values)


def test_eps_state_and_coupling_validation_is_atomic() -> None:
    """Invalid state or geometry cannot partially mutate coupled fields."""
    fields = _fields()
    eps_field = _eps_field()
    carbon_before = fields.carbon.concentration_mol_m3.copy()
    oxygen_before = fields.oxygen.concentration_mol_m3.copy()
    eps_before = eps_field.density_kg_m3.copy()

    with pytest.raises(EPSValidationError, match="every cell"):
        advance_eps_metabolism(
            cells=(_cell(),),
            solute_fields=fields,
            eps_field=eps_field,
            quorum_states=(),
            eps_parameters=_eps_parameters(),
            metabolism_parameters=_metabolism_parameters(),
            time_step_s=0.5,
            start_time_s=0.0,
            dry_biomass_per_unit_length_kg_m=2.0,
        )
    assert np.array_equal(fields.carbon.concentration_mol_m3, carbon_before)
    assert np.array_equal(fields.oxygen.concentration_mol_m3, oxygen_before)
    assert np.array_equal(eps_field.density_kg_m3, eps_before)

    with pytest.raises(EPSValidationError, match="negative"):
        _eps_field(np.full((2, 2), -1.0, dtype=np.float64))
