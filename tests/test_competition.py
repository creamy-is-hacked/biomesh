"""P2-WP03 producer/nonproducer competition verification."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from biomesh.cells import (
    Cell,
    CellIdGenerator,
    CellModelParameters,
    divide_if_ready,
)
from biomesh.competition import (
    CompetitionStrains,
    CompetitionValidationError,
    advance_competition,
)
from biomesh.eps import (
    EPSField,
    EPSParameters,
    EPSValidationError,
    advance_eps_metabolism,
)
from biomesh.metabolism import MetabolismParameters
from biomesh.outputs import MassBalanceEntry, RunMetadata, SimulationOutputWriter
from biomesh.quorum import CellQuorumState, QuorumObservation
from biomesh.solutes import SoluteField, SoluteFields


def _cell(
    cell_id: str,
    strain: str,
    *,
    x_m: float,
    y_m: float = 0.25,
    parent_id: str | None = None,
) -> Cell:
    return Cell(
        cell_id=cell_id,
        x_m=x_m,
        y_m=y_m,
        orientation_rad=0.0,
        length_m=0.5,
        radius_m=0.02,
        dry_biomass_kg=1.0,
        age_s=0.0,
        state="active",
        strain=strain,
        parent_id=parent_id,
    )


def _fields(*, shape: tuple[int, int] = (2, 2)) -> SoluteFields:
    concentration = np.full(shape, 20.0, dtype=np.float64)
    return SoluteFields(
        carbon=SoluteField(
            "carbon", shape, 1.0, 1.0, 0.0, 0.0, concentration
        ),
        oxygen=SoluteField(
            "oxygen", shape, 1.0, 1.0, 0.0, 0.0, concentration
        ),
    )


def _eps_field(
    *,
    shape: tuple[int, int] = (2, 2),
    density_kg_m3: np.ndarray[tuple[int, int], np.dtype[np.float64]] | None = None,
) -> EPSField:
    return EPSField(
        shape=shape,
        width_m=1.0,
        height_m=1.0,
        depth_m=1.0,
        density_kg_m3=(
            np.zeros(shape, dtype=np.float64)
            if density_kg_m3 is None
            else density_kg_m3
        ),
    )


def _eps_parameters(*, allocation_fraction: float = 0.5) -> EPSParameters:
    return EPSParameters(
        maximum_allocation_fraction=allocation_fraction,
        cohesion_sensitivity_m3_kg=2.0,
        attachment_strength_sensitivity_m3_kg=3.0,
    )


def _metabolism_parameters() -> MetabolismParameters:
    return MetabolismParameters(
        maximum_specific_growth_rate_s=0.4,
        carbon_half_saturation_mol_m3=2.0,
        oxygen_half_saturation_mol_m3=4.0,
        death_rate_s=0.0,
        biomass_yield_on_carbon_kg_mol=2.0,
        biomass_yield_on_oxygen_kg_mol=4.0,
    )


def _roles() -> CompetitionStrains:
    return CompetitionStrains(
        producer_strains=frozenset({"producer"}),
        nonproducer_strains=frozenset({"nonproducer"}),
    )


def _quorum_states(
    cells: tuple[Cell, ...], *, time_s: float = 0.0, activation: float = 1.0
) -> tuple[CellQuorumState, ...]:
    return tuple(
        CellQuorumState(
            cell_id=cell.cell_id,
            history=(
                QuorumObservation(
                    time_s=time_s,
                    signal_concentration_mol_m3=1.0,
                    activation_fraction=activation,
                ),
            ),
        )
        for cell in cells
    )


def _advance(
    cells: tuple[Cell, ...],
    *,
    fields: SoluteFields | None = None,
    eps_field: EPSField | None = None,
    allocation_fraction: float = 0.5,
    time_s: float = 0.0,
):
    selected_fields = _fields() if fields is None else fields
    selected_eps = _eps_field() if eps_field is None else eps_field
    result = advance_competition(
        cells=cells,
        strain_roles=_roles(),
        solute_fields=selected_fields,
        eps_field=selected_eps,
        quorum_states=_quorum_states(cells, time_s=time_s),
        eps_parameters=_eps_parameters(allocation_fraction=allocation_fraction),
        metabolism_parameters=_metabolism_parameters(),
        time_step_s=0.5,
        start_time_s=time_s,
        dry_biomass_per_unit_length_kg_m=2.0,
    )
    return result, selected_fields, selected_eps


def test_neutral_strains_have_identical_fitness_without_production_cost() -> None:
    """Role labels alone create no systematic advantage in a neutral control."""
    cells = (
        _cell("cell-p", "producer", x_m=0.25),
        _cell("cell-n", "nonproducer", x_m=0.25),
    )
    result, _, _ = _advance(cells, allocation_fraction=0.0)
    metrics = {metric.role: metric for metric in result.snapshot.cell_metrics}

    assert metrics["producer"].final_dry_biomass_kg == pytest.approx(
        metrics["nonproducer"].final_dry_biomass_kg
    )
    assert metrics["producer"].realized_local_fitness_s == pytest.approx(
        metrics["nonproducer"].realized_local_fitness_s
    )
    assert result.snapshot.producer_cell_frequency == 0.5
    assert result.snapshot.producer_biomass_frequency == pytest.approx(0.5)


def test_production_cost_is_measurable_in_well_mixed_control() -> None:
    """Co-located producers retain less biomass when EPS allocation is enabled."""
    cells = (
        _cell("cell-p", "producer", x_m=0.25),
        _cell("cell-n", "nonproducer", x_m=0.25),
    )
    result, _, _ = _advance(cells, allocation_fraction=0.6)
    metrics = {metric.role: metric for metric in result.snapshot.cell_metrics}

    assert metrics["producer"].eps_allocation_fraction == 0.6
    assert metrics["nonproducer"].eps_allocation_fraction == 0.0
    assert (
        metrics["producer"].realized_local_fitness_s
        < metrics["nonproducer"].realized_local_fitness_s
    )
    assert (
        metrics["producer"].final_dry_biomass_kg
        < metrics["nonproducer"].final_dry_biomass_kg
    )
    assert result.snapshot.producer_biomass_frequency < 0.5


def test_nonproducer_shares_local_eps_benefit_without_paying_cost() -> None:
    """Nearby cells receive equal matrix modifiers regardless of strain role."""
    cells = (
        _cell("cell-p", "producer", x_m=0.25),
        _cell("cell-n", "nonproducer", x_m=0.25),
    )
    result, _, eps_field = _advance(cells)
    metrics = {metric.role: metric for metric in result.snapshot.cell_metrics}

    assert result.eps.mass_balance.produced_eps_kg > 0.0
    assert eps_field.total_mass_kg == pytest.approx(
        result.eps.mass_balance.produced_eps_kg
    )
    assert metrics["nonproducer"].eps_allocation_fraction == 0.0
    assert metrics["nonproducer"].local_eps_density_kg_m3 > 0.0
    assert metrics["nonproducer"].cohesion_multiplier == pytest.approx(
        metrics["producer"].cohesion_multiplier
    )
    assert metrics["nonproducer"].attachment_strength_multiplier == pytest.approx(
        metrics["producer"].attachment_strength_multiplier
    )


def test_shared_resource_uptake_and_biomass_equivalent_conserve() -> None:
    """Mixed cells share one resource update and retain explicit balances."""
    cells = (
        _cell("cell-p", "producer", x_m=0.25),
        _cell("cell-n", "nonproducer", x_m=0.25),
    )
    fields = _fields()
    initial_carbon_mol = float(np.sum(fields.carbon.concentration_mol_m3)) * 0.25
    initial_oxygen_mol = float(np.sum(fields.oxygen.concentration_mol_m3)) * 0.25
    result, fields, _ = _advance(cells, fields=fields)
    final_carbon_mol = float(np.sum(fields.carbon.concentration_mol_m3)) * 0.25
    final_oxygen_mol = float(np.sum(fields.oxygen.concentration_mol_m3)) * 0.25
    gross_kg = sum(
        metric.gross_biomass_production_kg
        for metric in result.eps.metabolism.cell_results
    )

    assert initial_carbon_mol - final_carbon_mol == pytest.approx(gross_kg / 2.0)
    assert initial_oxygen_mol - final_oxygen_mol == pytest.approx(gross_kg / 4.0)
    assert abs(result.eps.mass_balance.eps_residual_kg) < 1.0e-15
    assert abs(result.eps.mass_balance.biomass_equivalent_residual_kg) < 1.0e-15


def test_frequency_segregation_lineage_and_local_fitness_are_tracked() -> None:
    """Competition records expose every metric required by P2-WP03."""
    cells = (
        _cell("p-a", "producer", x_m=0.5, y_m=0.10, parent_id="p-founder"),
        _cell("p-b", "producer", x_m=0.5, y_m=0.20, parent_id="p-founder"),
        _cell("n-a", "nonproducer", x_m=0.5, y_m=0.80, parent_id="n-founder"),
        _cell("n-b", "nonproducer", x_m=0.5, y_m=0.90, parent_id="n-founder"),
    )
    result, _, _ = _advance(cells, allocation_fraction=0.0)

    assert result.snapshot.nearest_neighbor_segregation_fraction == 1.0
    assert {metric.parent_id for metric in result.snapshot.cell_metrics} == {
        "p-founder",
        "n-founder",
    }
    assert {metric.strain for metric in result.snapshot.strain_metrics} == {
        "producer",
        "nonproducer",
    }
    assert sum(
        metric.cell_frequency for metric in result.snapshot.strain_metrics
    ) == pytest.approx(1.0)
    assert all(
        np.isfinite(metric.realized_local_fitness_s)
        for metric in result.snapshot.cell_metrics
    )


def _seeded_mixed_outcome(seed: int):
    cells = (
        _cell("founder-p", "producer", x_m=0.25),
        _cell("founder-n", "nonproducer", x_m=0.75),
    )
    fields = _fields()
    eps_field = _eps_field()
    first, _, _ = _advance(cells, fields=fields, eps_field=eps_field)
    random_generator = np.random.default_rng(seed)
    id_generator = CellIdGenerator(next_sequence=100)
    division_parameters = CellModelParameters(
        dry_biomass_per_unit_length_kg_m=2.0,
        division_length_m=0.4,
        maximum_daughter_asymmetry_fraction=0.1,
    )
    daughters: list[Cell] = []
    for cell in first.cells:
        division = divide_if_ready(
            cell, division_parameters, random_generator, id_generator
        )
        assert division is not None
        daughters.extend((division.first_daughter, division.second_daughter))
    daughter_cells = tuple(daughters)
    second, _, _ = _advance(
        daughter_cells,
        fields=fields,
        eps_field=eps_field,
        time_s=0.5,
    )
    return (
        second.cells,
        second.snapshot,
        fields.carbon.concentration_mol_m3.copy(),
        fields.oxygen.concentration_mol_m3.copy(),
        eps_field.density_kg_m3.copy(),
    )


def test_mixed_outcomes_reproduce_from_fixed_seed() -> None:
    """Seeded division plus mixed competition replays exactly."""
    first = _seeded_mixed_outcome(17)
    second = _seeded_mixed_outcome(17)

    assert first[:2] == second[:2]
    assert all(
        np.array_equal(left, right)
        for left, right in zip(first[2:], second[2:])
    )


def test_cell_input_order_does_not_change_mixed_outcome() -> None:
    """Canonical competition evaluation is independent of input ordering."""
    cells = (
        _cell("cell-p", "producer", x_m=0.25),
        _cell("cell-n", "nonproducer", x_m=0.25),
    )
    first, first_fields, first_eps = _advance(cells)
    second, second_fields, second_eps = _advance(tuple(reversed(cells)))

    assert first == second
    assert np.array_equal(
        first_fields.carbon.concentration_mol_m3,
        second_fields.carbon.concentration_mol_m3,
    )
    assert np.array_equal(first_eps.density_kg_m3, second_eps.density_kg_m3)


def _write_competition_replay(run_directory: Path) -> Path:
    cells = (
        _cell("cell-p", "producer", x_m=0.25),
        _cell("cell-n", "nonproducer", x_m=0.25),
    )
    fields = _fields()
    eps_field = _eps_field()
    writer = SimulationOutputWriter(
        run_directory,
        RunMetadata(
            seed=17,
            parameters={"purpose": "synthetic P2-WP03 replay"},
            package_version="0.0.0",
            commit_hash="test",
            dependency_versions={"numpy": "test"},
            parameter_file="synthetic.toml",
            parameter_file_sha256="0" * 64,
            platform="test",
            python_version="3.14.test",
        ),
    )
    for step_index in range(2):
        initial_eps_kg = eps_field.total_mass_kg
        result, _, _ = _advance(
            cells,
            fields=fields,
            eps_field=eps_field,
            time_s=step_index * 0.5,
        )
        cells = result.cells
        writer.write_snapshot(
            time_s=(step_index + 1) * 0.5,
            cells=cells,
            solute_fields=fields,
            division_events=(),
            mass_balance_entries=(
                MassBalanceEntry(
                    quantity="eps",
                    unit="kg",
                    initial_amount=initial_eps_kg,
                    final_amount=eps_field.total_mass_kg,
                    net_input_amount=eps_field.total_mass_kg - initial_eps_kg,
                    absolute_tolerance=1.0e-12,
                    relative_tolerance=1.0e-12,
                ),
            ),
            eps_field=eps_field,
            competition_snapshot=result.snapshot,
        )
    paths = writer.finalize()
    assert paths.competition_summary_table is not None
    assert paths.competition_strain_table is not None
    assert paths.competition_cell_table is not None
    summary = pq.read_table(paths.competition_summary_table).to_pydict()
    assert summary["producer_cell_frequency"] == [0.5, 0.5]
    assert summary["producer_biomass_frequency"][-1] < 0.5
    cells_table = pq.read_table(paths.competition_cell_table).to_pydict()
    assert set(cells_table["role"]) == {"producer", "nonproducer"}
    return paths.run_directory


def test_competition_history_outputs_replay_byte_for_byte(tmp_path: Path) -> None:
    """Frequencies, fitness, lineage, and matrix benefits serialize exactly."""
    first = _write_competition_replay(tmp_path / "first")
    second = _write_competition_replay(tmp_path / "second")
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


def test_unclassified_cell_strain_is_rejected_atomically() -> None:
    """Unknown strain roles cannot partially consume resources or produce EPS."""
    strain_roles = _roles()
    cell = replace(_cell("cell-x", "producer", x_m=0.25), strain="unknown")
    fields = _fields()
    eps_field = _eps_field()
    carbon_before = fields.carbon.concentration_mol_m3.copy()

    with pytest.raises(CompetitionValidationError, match="no configured"):
        advance_competition(
            cells=(cell,),
            strain_roles=strain_roles,
            solute_fields=fields,
            eps_field=eps_field,
            quorum_states=_quorum_states((cell,)),
            eps_parameters=_eps_parameters(),
            metabolism_parameters=_metabolism_parameters(),
            time_step_s=0.5,
            start_time_s=0.0,
            dry_biomass_per_unit_length_kg_m=2.0,
        )
    assert np.array_equal(fields.carbon.concentration_mol_m3, carbon_before)
    assert eps_field.total_mass_kg == 0.0


def test_competition_role_and_producer_selection_validation() -> None:
    """Ambiguous roles and unknown producer cell IDs fail explicitly."""
    with pytest.raises(CompetitionValidationError, match="disjoint"):
        CompetitionStrains(
            producer_strains=frozenset({"shared"}),
            nonproducer_strains=frozenset({"shared"}),
        )
    with pytest.raises(CompetitionValidationError, match="non-empty"):
        CompetitionStrains(
            producer_strains=frozenset(),
            nonproducer_strains=frozenset({"nonproducer"}),
        )

    cell = _cell("cell-p", "producer", x_m=0.25)
    with pytest.raises(EPSValidationError, match="unknown cell IDs"):
        advance_eps_metabolism(
            cells=(cell,),
            solute_fields=_fields(),
            eps_field=_eps_field(),
            quorum_states=_quorum_states((cell,)),
            eps_parameters=_eps_parameters(),
            metabolism_parameters=_metabolism_parameters(),
            time_step_s=0.5,
            start_time_s=0.0,
            dry_biomass_per_unit_length_kg_m=2.0,
            producing_cell_ids=frozenset({"missing"}),
        )
