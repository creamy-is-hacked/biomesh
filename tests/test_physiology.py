"""P2-WP04 physiological state and population-ledger verification."""

from __future__ import annotations

from dataclasses import replace
from math import exp
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from biomesh.cells import Cell
from biomesh.competition import CompetitionStrains, advance_competition
from biomesh.eps import EPSField, EPSParameters
from biomesh.metabolism import MetabolismParameters, advance_metabolism
from biomesh.outputs import (
    MassBalanceEntry,
    OutputValidationError,
    RunMetadata,
    SimulationOutputWriter,
)
from biomesh.physiology import (
    DeadBiomassRule,
    PhysiologicalState,
    PhysiologyParameters,
    PhysiologyValidationError,
    advance_physiological_states,
    build_physiology_snapshot,
    cells_retained_for_mechanics,
    initialize_physiological_states,
    metabolic_activity_fractions,
)
from biomesh.quorum import CellQuorumState, QuorumObservation
from biomesh.solutes import SoluteField, SoluteFields


def _cell(
    cell_id: str = "cell-a",
    *,
    state: PhysiologicalState = PhysiologicalState.ACTIVE,
    strain: str = "producer",
    x_m: float = 0.25,
    biomass_kg: float = 1.0,
) -> Cell:
    return Cell(
        cell_id=cell_id,
        x_m=x_m,
        y_m=0.25,
        orientation_rad=0.0,
        length_m=biomass_kg / 2.0,
        radius_m=0.02,
        dry_biomass_kg=biomass_kg,
        age_s=0.0,
        state=state.value,
        strain=strain,
    )


def _fields(carbon: float, oxygen: float) -> SoluteFields:
    return SoluteFields(
        carbon=SoluteField(
            "carbon",
            (2, 2),
            1.0,
            1.0,
            0.0,
            carbon,
            np.full((2, 2), carbon, dtype=np.float64),
        ),
        oxygen=SoluteField(
            "oxygen",
            (2, 2),
            1.0,
            1.0,
            0.0,
            oxygen,
            np.full((2, 2), oxygen, dtype=np.float64),
        ),
    )


def _parameters(
    *,
    rule: DeadBiomassRule = DeadBiomassRule.PERSIST,
    recycling_rate_s: float | None = None,
) -> PhysiologyParameters:
    return PhysiologyParameters(
        carbon_slow_threshold_mol_m3=5.0,
        oxygen_slow_threshold_mol_m3=5.0,
        carbon_dormancy_threshold_mol_m3=2.0,
        oxygen_dormancy_threshold_mol_m3=2.0,
        carbon_death_threshold_mol_m3=0.5,
        oxygen_death_threshold_mol_m3=0.5,
        slow_transition_delay_s=2.0,
        dormancy_transition_delay_s=2.0,
        death_transition_delay_s=2.0,
        recovery_transition_delay_s=2.0,
        slow_metabolic_activity_fraction=0.5,
        dormant_metabolic_activity_fraction=0.1,
        dead_biomass_rule=rule,
        dead_biomass_recycling_rate_s=recycling_rate_s,
    )


def _advance(
    cell: Cell,
    states,
    fields: SoluteFields,
    *,
    start_time_s: float,
    parameters: PhysiologyParameters | None = None,
    detached_cell_ids: frozenset[str] = frozenset(),
):
    return advance_physiological_states(
        cells=(cell,),
        solute_fields=fields,
        cell_states=states,
        parameters=_parameters() if parameters is None else parameters,
        time_step_s=1.0,
        start_time_s=start_time_s,
        dry_biomass_per_unit_length_kg_m=2.0,
        detached_cell_ids=detached_cell_ids,
    )


def test_thresholds_delays_and_recent_history_drive_reversible_states() -> None:
    """Active, slow, dormant, and recovered transitions honor exact delays."""
    cell = _cell()
    fields = _fields(4.0, 10.0)
    states = initialize_physiological_states(
        cells=(cell,), solute_fields=fields, time_s=0.0
    )

    first = _advance(cell, states, fields, start_time_s=0.0)
    assert first.cells[0].state == "active"
    second = _advance(first.cells[0], first.cell_states, fields, start_time_s=1.0)
    assert second.cells[0].state == "slow"

    fields = _fields(1.0, 10.0)
    third = _advance(second.cells[0], second.cell_states, fields, start_time_s=2.0)
    assert third.cells[0].state == "slow"
    fourth = _advance(third.cells[0], third.cell_states, fields, start_time_s=3.0)
    assert fourth.cells[0].state == "dormant"

    fields = _fields(10.0, 10.0)
    fifth = _advance(fourth.cells[0], fourth.cell_states, fields, start_time_s=4.0)
    assert fifth.cells[0].state == "dormant"
    sixth = _advance(fifth.cells[0], fifth.cell_states, fields, start_time_s=5.0)
    assert sixth.cells[0].state == "active"
    assert [observation.time_s for observation in sixth.cell_states[0].history] == [
        0.0,
        1.0,
        2.0,
        3.0,
        4.0,
        5.0,
        6.0,
    ]


def test_lethal_threshold_and_delay_are_inclusive_and_terminal() -> None:
    """Either solute at its lethal threshold can cause delayed death."""
    cell = _cell()
    fields = _fields(0.5, 10.0)
    states = initialize_physiological_states(
        cells=(cell,), solute_fields=fields, time_s=0.0
    )

    first = _advance(cell, states, fields, start_time_s=0.0)
    second = _advance(first.cells[0], first.cell_states, fields, start_time_s=1.0)
    recovered_fields = _fields(10.0, 10.0)
    third = _advance(
        second.cells[0], second.cell_states, recovered_fields, start_time_s=2.0
    )

    assert second.cells[0].state == "dead"
    assert third.cells[0].state == "dead"
    assert third.snapshot.totals.dead_cell_count == 1


def test_zero_delays_mean_immediate_only_when_threshold_condition_is_met() -> None:
    """A zero delay does not trigger a transition without its exposure condition."""
    parameters = replace(
        _parameters(),
        slow_transition_delay_s=0.0,
        dormancy_transition_delay_s=0.0,
        death_transition_delay_s=0.0,
        recovery_transition_delay_s=0.0,
    )
    active = _cell()
    high_fields = _fields(10.0, 10.0)
    states = initialize_physiological_states(
        cells=(active,), solute_fields=high_fields, time_s=0.0
    )
    unchanged = _advance(
        active,
        states,
        high_fields,
        start_time_s=0.0,
        parameters=parameters,
    )
    lethal_fields = _fields(0.5, 10.0)
    dead = _advance(
        unchanged.cells[0],
        unchanged.cell_states,
        lethal_fields,
        start_time_s=1.0,
        parameters=parameters,
    )

    assert unchanged.cells[0].state == "active"
    assert dead.cells[0].state == "dead"


def test_interrupted_exposure_resets_the_continuous_delay() -> None:
    """Separated threshold encounters do not accumulate into one transition."""
    cell = _cell()
    limited_fields = _fields(4.0, 10.0)
    recovered_fields = _fields(10.0, 10.0)
    states = initialize_physiological_states(
        cells=(cell,), solute_fields=limited_fields, time_s=0.0
    )
    first = _advance(cell, states, limited_fields, start_time_s=0.0)
    second = _advance(
        first.cells[0],
        first.cell_states,
        recovered_fields,
        start_time_s=1.0,
    )
    third = _advance(
        second.cells[0],
        second.cell_states,
        limited_fields,
        start_time_s=2.0,
    )

    assert first.cell_states[0].current.limited_duration_s == 1.0
    assert second.cell_states[0].current.limited_duration_s == 0.0
    assert third.cells[0].state == "active"
    assert third.cell_states[0].current.limited_duration_s == 1.0


def _metabolism_parameters() -> MetabolismParameters:
    return MetabolismParameters(
        maximum_specific_growth_rate_s=0.4,
        carbon_half_saturation_mol_m3=2.0,
        oxygen_half_saturation_mol_m3=2.0,
        death_rate_s=0.05,
        biomass_yield_on_carbon_kg_mol=2.0,
        biomass_yield_on_oxygen_kg_mol=4.0,
    )


def test_dormant_cells_consume_less_than_active_cells() -> None:
    """The configured activity fraction scales growth, uptake, and maintenance."""
    cells = (
        _cell("active", state=PhysiologicalState.ACTIVE, x_m=0.25),
        _cell("dormant", state=PhysiologicalState.DORMANT, x_m=0.25),
    )
    fields = _fields(20.0, 20.0)
    states = initialize_physiological_states(
        cells=cells, solute_fields=fields, time_s=0.0
    )
    activities = metabolic_activity_fractions(
        cells=cells, cell_states=states, parameters=_parameters()
    )
    result = advance_metabolism(
        cells,
        fields,
        0.5,
        1.0,
        2.0,
        _metabolism_parameters(),
        metabolic_activity_fractions=activities,
    )
    by_id = dict(
        zip((cell.cell_id for cell in result.cells), result.cell_results, strict=True)
    )

    assert activities == {"active": 1.0, "dormant": 0.1}
    assert by_id["dormant"].carbon_uptake_mol < by_id["active"].carbon_uptake_mol
    assert by_id["dormant"].oxygen_uptake_mol < by_id["active"].oxygen_uptake_mol
    assert by_id["dormant"].specific_growth_rate_s == pytest.approx(
        0.1 * by_id["active"].specific_growth_rate_s
    )


def test_competition_and_eps_use_the_same_physiological_activity_mapping() -> None:
    """Competition retains its roles while physiology scales shared metabolism."""
    cells = (
        _cell("active", strain="producer", state=PhysiologicalState.ACTIVE),
        _cell(
            "dormant",
            strain="nonproducer",
            state=PhysiologicalState.DORMANT,
        ),
    )
    fields = _fields(20.0, 20.0)
    states = initialize_physiological_states(
        cells=cells, solute_fields=fields, time_s=0.0
    )
    activities = metabolic_activity_fractions(
        cells=cells, cell_states=states, parameters=_parameters()
    )
    quorum_states = tuple(
        CellQuorumState(
            cell_id=cell.cell_id,
            history=(QuorumObservation(0.0, 1.0, 1.0),),
        )
        for cell in cells
    )
    result = advance_competition(
        cells=cells,
        strain_roles=CompetitionStrains(
            producer_strains=frozenset({"producer"}),
            nonproducer_strains=frozenset({"nonproducer"}),
        ),
        solute_fields=fields,
        eps_field=EPSField(
            shape=(2, 2),
            width_m=1.0,
            height_m=1.0,
            depth_m=1.0,
            density_kg_m3=np.zeros((2, 2), dtype=np.float64),
        ),
        quorum_states=quorum_states,
        eps_parameters=EPSParameters(0.0, 0.0, 0.0),
        metabolism_parameters=_metabolism_parameters(),
        time_step_s=0.5,
        start_time_s=0.0,
        dry_biomass_per_unit_length_kg_m=2.0,
        metabolic_activity_fractions=activities,
    )
    metrics = {metric.cell_id: metric for metric in result.snapshot.cell_metrics}

    assert metrics["dormant"].realized_local_fitness_s < (
        metrics["active"].realized_local_fitness_s
    )
    assert result.eps.cell_production[0].produced_eps_kg == 0.0
    assert result.eps.cell_production[1].produced_eps_kg == 0.0


def test_dead_biomass_persists_or_recycles_by_explicit_rule() -> None:
    """Both accepted dead-biomass dispositions conserve their explicit ledger."""
    dead = _cell(state=PhysiologicalState.DEAD)
    fields = _fields(10.0, 10.0)
    states = initialize_physiological_states(
        cells=(dead,), solute_fields=fields, time_s=0.0
    )
    persisted = _advance(dead, states, fields, start_time_s=0.0)
    recycling = _parameters(
        rule=DeadBiomassRule.RECYCLE,
        recycling_rate_s=0.5,
    )
    recycled = _advance(
        dead,
        states,
        fields,
        start_time_s=0.0,
        parameters=recycling,
    )

    assert persisted.cells[0].dry_biomass_kg == 1.0
    assert persisted.snapshot.totals.recycled_dead_biomass_kg == 0.0
    assert recycled.cells[0].dry_biomass_kg == pytest.approx(exp(-0.5))
    assert recycled.recycled_dead_biomass_this_step_kg == pytest.approx(
        1.0 - exp(-0.5)
    )
    assert (
        recycled.snapshot.totals.dead_biomass_kg
        + recycled.snapshot.totals.recycled_dead_biomass_kg
    ) == pytest.approx(1.0)


def test_detached_state_is_explicit_terminal_and_excluded_from_mechanics() -> None:
    """WP04 records external detachment without implementing a WP05 shear law."""
    cell = _cell()
    fields = _fields(10.0, 10.0)
    states = initialize_physiological_states(
        cells=(cell,), solute_fields=fields, time_s=0.0
    )
    detached = _advance(
        cell,
        states,
        fields,
        start_time_s=0.0,
        detached_cell_ids=frozenset({cell.cell_id}),
    )
    activity = metabolic_activity_fractions(
        cells=detached.cells,
        cell_states=detached.cell_states,
        parameters=_parameters(),
    )

    assert detached.cells[0].state == "detached"
    assert detached.snapshot.totals.detached_biomass_kg == 1.0
    assert cells_retained_for_mechanics(detached.cells) == ()
    assert activity == {cell.cell_id: 0.0}


def test_all_state_totals_reconcile_with_population_ledger() -> None:
    """Counts and retained biomass partition exactly over all five states."""
    cells = tuple(
        _cell(
            state.value,
            state=state,
            biomass_kg=float(index),
            x_m=0.1 * index,
        )
        for index, state in enumerate(PhysiologicalState, start=1)
    )
    fields = _fields(10.0, 10.0)
    states = initialize_physiological_states(
        cells=cells, solute_fields=fields, time_s=0.0
    )
    snapshot = build_physiology_snapshot(
        time_s=0.0, cells=cells, cell_states=states
    )

    assert snapshot.totals.cell_count == 5
    assert snapshot.totals.retained_biomass_kg == 15.0
    assert snapshot.totals.partitioned_biomass_kg == 15.0
    assert snapshot.totals.active_biomass_kg == 1.0
    assert snapshot.totals.slow_biomass_kg == 2.0
    assert snapshot.totals.dormant_biomass_kg == 3.0
    assert snapshot.totals.dead_biomass_kg == 4.0
    assert snapshot.totals.detached_biomass_kg == 5.0


def _metadata() -> RunMetadata:
    return RunMetadata(
        seed=19,
        parameters={"purpose": "synthetic P2-WP04 replay"},
        package_version="0.0.0",
        commit_hash="test",
        dependency_versions={"numpy": "test"},
        parameter_file="synthetic.toml",
        parameter_file_sha256="0" * 64,
        platform="test",
        python_version="3.14.test",
    )


def _write_physiology_replay(run_directory: Path) -> Path:
    cells = (
        _cell("active", state=PhysiologicalState.ACTIVE, biomass_kg=1.0),
        _cell("dead", state=PhysiologicalState.DEAD, biomass_kg=2.0),
    )
    fields = _fields(10.0, 10.0)
    states = initialize_physiological_states(
        cells=cells, solute_fields=fields, time_s=0.0
    )
    snapshot = build_physiology_snapshot(
        time_s=0.0, cells=cells, cell_states=states
    )
    writer = SimulationOutputWriter(run_directory, _metadata())
    writer.write_snapshot(
        time_s=0.0,
        cells=cells,
        solute_fields=fields,
        division_events=(),
        mass_balance_entries=(
            MassBalanceEntry("biomass", "kg", 3.0, 3.0, 0.0, 0.0, 0.0),
        ),
        physiology_snapshot=snapshot,
    )
    paths = writer.finalize()
    assert paths.physiology_summary_table is not None
    table = pq.read_table(paths.physiology_summary_table).to_pydict()
    assert table["active_biomass_kg"] == [1.0]
    assert table["dead_biomass_kg"] == [2.0]
    assert table["retained_biomass_kg"] == [3.0]
    return paths.run_directory


def test_physiology_outputs_replay_byte_for_byte(tmp_path: Path) -> None:
    """State totals and existing cell-state output serialize deterministically."""
    first = _write_physiology_replay(tmp_path / "first")
    second = _write_physiology_replay(tmp_path / "second")
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


def test_output_rejects_a_nonreconciling_physiology_ledger(tmp_path: Path) -> None:
    """Caller-supplied state totals cannot contradict the serialized cells."""
    cells = (_cell(),)
    fields = _fields(10.0, 10.0)
    states = initialize_physiological_states(
        cells=cells, solute_fields=fields, time_s=0.0
    )
    snapshot = build_physiology_snapshot(
        time_s=0.0, cells=cells, cell_states=states
    )
    invalid = replace(
        snapshot,
        totals=replace(snapshot.totals, active_biomass_kg=2.0),
    )
    writer = SimulationOutputWriter(tmp_path / "invalid", _metadata())

    with pytest.raises(OutputValidationError, match="totals"):
        writer.write_snapshot(
            time_s=0.0,
            cells=cells,
            solute_fields=fields,
            division_events=(),
            mass_balance_entries=(
                MassBalanceEntry("biomass", "kg", 1.0, 1.0, 0.0, 0.0, 0.0),
            ),
            physiology_snapshot=invalid,
        )


def test_invalid_parameters_and_state_mismatch_fail_explicitly() -> None:
    """Invalid thresholds, rules, and stale centralized state are rejected."""
    with pytest.raises(PhysiologyValidationError, match="carbon thresholds"):
        replace(_parameters(), carbon_death_threshold_mol_m3=6.0)
    with pytest.raises(PhysiologyValidationError, match="persisting"):
        _parameters(recycling_rate_s=1.0)

    cell = _cell()
    fields = _fields(10.0, 10.0)
    states = initialize_physiological_states(
        cells=(cell,), solute_fields=fields, time_s=0.0
    )
    stale_cell = replace(cell, state="slow")
    with pytest.raises(PhysiologyValidationError, match="match cell.state"):
        _advance(stale_cell, states, fields, start_time_s=0.0)
    with pytest.raises(PhysiologyValidationError, match="one of"):
        initialize_physiological_states(
            cells=(replace(cell, state="unknown"),),
            solute_fields=fields,
            time_s=0.0,
        )


def test_state_updates_are_independent_of_input_order() -> None:
    """Canonical cell ordering makes physiological replay deterministic."""
    cells = (_cell("b", x_m=0.75), _cell("a", x_m=0.25))
    fields = _fields(4.0, 10.0)
    states = initialize_physiological_states(
        cells=cells, solute_fields=fields, time_s=0.0
    )
    first = advance_physiological_states(
        cells=cells,
        solute_fields=fields,
        cell_states=states,
        parameters=_parameters(),
        time_step_s=1.0,
        start_time_s=0.0,
        dry_biomass_per_unit_length_kg_m=2.0,
    )
    second = advance_physiological_states(
        cells=tuple(reversed(cells)),
        solute_fields=fields,
        cell_states=tuple(reversed(states)),
        parameters=_parameters(),
        time_step_s=1.0,
        start_time_s=0.0,
        dry_biomass_per_unit_length_kg_m=2.0,
    )

    assert first == second
