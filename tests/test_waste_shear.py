"""P2-WP05 waste transport and deterministic shear-detachment verification."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from biomesh.cells import Cell
from biomesh.eps import EPSField, EPSParameters
from biomesh.outputs import MassBalanceEntry, RunMetadata, SimulationOutputWriter
from biomesh.physiology import (
    DeadBiomassRule,
    PhysiologyParameters,
    advance_physiological_states,
    initialize_physiological_states,
)
from biomesh.shear import (
    ShearParameters,
    ShearValidationError,
    advance_shear_detachment,
    initialize_shear_states,
)
from biomesh.solutes import DiffusionStabilityError, SoluteField, SoluteFields
from biomesh.waste import (
    WasteParameters,
    WasteValidationError,
    advance_waste,
    maximum_stable_timestep_s,
)


def _cell(cell_id: str = "cell-a", *, state: str = "active") -> Cell:
    return Cell(
        cell_id=cell_id,
        x_m=0.25,
        y_m=0.25,
        orientation_rad=0.0,
        length_m=0.5,
        radius_m=0.02,
        dry_biomass_kg=1.0,
        age_s=0.0,
        state=state,
        strain="synthetic-validation",
    )


def _solute_fields() -> SoluteFields:
    concentration = np.full((2, 2), 10.0, dtype=np.float64)
    return SoluteFields(
        carbon=SoluteField("carbon", (2, 2), 1.0, 1.0, 0.0, 10.0, concentration),
        oxygen=SoluteField("oxygen", (2, 2), 1.0, 1.0, 0.0, 10.0, concentration),
    )


def _waste_field(
    concentration_mol_m3: float = 0.0,
    *,
    diffusivity_m2_s: float = 0.0,
) -> SoluteField:
    return SoluteField(
        "waste",
        (2, 2),
        1.0,
        1.0,
        diffusivity_m2_s,
        0.0,
        np.full((2, 2), concentration_mol_m3, dtype=np.float64),
    )


def _eps_field(density_kg_m3: float = 0.0) -> EPSField:
    return EPSField(
        shape=(2, 2),
        width_m=1.0,
        height_m=1.0,
        depth_m=1.0,
        density_kg_m3=np.full((2, 2), density_kg_m3, dtype=np.float64),
    )


def _eps_parameters(sensitivity_m3_kg: float = 0.0) -> EPSParameters:
    return EPSParameters(
        maximum_allocation_fraction=0.0,
        cohesion_sensitivity_m3_kg=0.0,
        attachment_strength_sensitivity_m3_kg=sensitivity_m3_kg,
    )


def _shear_parameters(stress_pa: float) -> ShearParameters:
    return ShearParameters(
        surface_parallel_shear_stress_pa=stress_pa,
        detachment_exposure_threshold_pa_s=1.0,
        attached_resistance_multiplier=1.0,
    )


def _physiology_parameters() -> PhysiologyParameters:
    return PhysiologyParameters(
        carbon_slow_threshold_mol_m3=1.0,
        oxygen_slow_threshold_mol_m3=1.0,
        carbon_dormancy_threshold_mol_m3=0.5,
        oxygen_dormancy_threshold_mol_m3=0.5,
        carbon_death_threshold_mol_m3=0.1,
        oxygen_death_threshold_mol_m3=0.1,
        slow_transition_delay_s=1.0,
        dormancy_transition_delay_s=1.0,
        death_transition_delay_s=1.0,
        recovery_transition_delay_s=1.0,
        slow_metabolic_activity_fraction=0.5,
        dormant_metabolic_activity_fraction=0.1,
        dead_biomass_rule=DeadBiomassRule.PERSIST,
        dead_biomass_recycling_rate_s=None,
    )


def test_waste_production_removal_and_activity_accounting_reconcile() -> None:
    """Waste sources, first-order removal, and activity scaling close in mol."""
    field = _waste_field(2.0)
    result = advance_waste(
        cells=(_cell(),),
        waste_field=field,
        parameters=WasteParameters(2.0, 0.25),
        time_step_s=0.5,
        depth_m=1.0,
        metabolic_activity_fractions={"cell-a": 0.5},
    )

    balance = result.mass_balance
    assert result.cell_production[0].production_rate_mol_s == 1.0
    assert balance.initial_waste_mol == pytest.approx(2.0)
    assert balance.produced_waste_mol == pytest.approx(0.5)
    assert balance.removed_waste_mol == pytest.approx(0.25)
    assert abs(balance.residual_waste_mol) < 1.0e-15
    assert field.concentration_mol_m3[-1, 0] == pytest.approx(3.75)


def test_waste_diffusion_removal_stability_is_explicit_and_atomic() -> None:
    """The reused transport stability gate rejects an unsafe update unchanged."""
    field = _waste_field(1.0, diffusivity_m2_s=1.0)
    before = field.concentration_mol_m3.copy()
    limit = maximum_stable_timestep_s(field, 1.0)

    with pytest.raises(DiffusionStabilityError, match="stability"):
        advance_waste(
            cells=(),
            waste_field=field,
            parameters=WasteParameters(0.0, 1.0),
            time_step_s=limit * 1.01,
            depth_m=1.0,
        )

    assert np.array_equal(field.concentration_mol_m3, before)


def test_zero_shear_causes_no_shear_driven_detachment() -> None:
    """A zero stress never selects a detachment transition."""
    cell = _cell()
    result = advance_shear_detachment(
        cells=(cell,),
        eps_field=_eps_field(),
        eps_parameters=_eps_parameters(),
        parameters=_shear_parameters(0.0),
        time_step_s=10.0,
        start_time_s=0.0,
        attached_cell_ids=frozenset({cell.cell_id}),
    )

    assert result.detached_cell_ids == frozenset()
    assert result.snapshot.detached_cell_count == 0
    assert result.snapshot.detachment_rate_s == 0.0


def test_increasing_shear_increases_controlled_detachment() -> None:
    """Higher uniform stress crosses the same configured exposure threshold."""
    cell = _cell()
    shared = dict(
        cells=(cell,),
        eps_field=_eps_field(),
        eps_parameters=_eps_parameters(),
        time_step_s=1.0,
        start_time_s=0.0,
    )
    lower = advance_shear_detachment(
        parameters=_shear_parameters(0.5), **shared
    )
    higher = advance_shear_detachment(
        parameters=_shear_parameters(1.0), **shared
    )

    assert lower.detached_cell_ids == frozenset()
    assert higher.detached_cell_ids == frozenset({cell.cell_id})
    assert higher.snapshot.detachment_rate_s > lower.snapshot.detachment_rate_s


def test_stronger_eps_reduces_detachment_under_identical_shear() -> None:
    """Existing local EPS attachment strength raises shear resistance."""
    cell = _cell()
    shared = dict(
        cells=(cell,),
        eps_parameters=_eps_parameters(1.0),
        parameters=_shear_parameters(1.0),
        time_step_s=1.0,
        start_time_s=0.0,
    )
    weaker = advance_shear_detachment(eps_field=_eps_field(0.0), **shared)
    stronger = advance_shear_detachment(eps_field=_eps_field(1.0), **shared)

    assert weaker.detached_cell_ids == frozenset({cell.cell_id})
    assert stronger.detached_cell_ids == frozenset()
    assert (
        stronger.cell_states[0].current.effective_detachment_threshold_pa_s
        > weaker.cell_states[0].current.effective_detachment_threshold_pa_s
    )


def test_surface_attachment_increases_configured_detachment_resistance() -> None:
    """Caller-designated attachment enters the same exposure threshold law."""
    cell = _cell()
    parameters = ShearParameters(
        surface_parallel_shear_stress_pa=1.0,
        detachment_exposure_threshold_pa_s=1.0,
        attached_resistance_multiplier=2.0,
    )
    shared = dict(
        cells=(cell,),
        eps_field=_eps_field(),
        eps_parameters=_eps_parameters(),
        parameters=parameters,
        time_step_s=1.0,
        start_time_s=0.0,
    )
    unattached = advance_shear_detachment(**shared)
    attached = advance_shear_detachment(
        attached_cell_ids=frozenset({cell.cell_id}), **shared
    )

    assert unattached.detached_cell_ids == frozenset({cell.cell_id})
    assert attached.detached_cell_ids == frozenset()


def test_shear_detachment_reconciles_with_terminal_physiology_ledger() -> None:
    """Selected IDs drive the existing terminal detached state and its ledger."""
    cell = _cell()
    fields = _solute_fields()
    shear = advance_shear_detachment(
        cells=(cell,),
        eps_field=_eps_field(),
        eps_parameters=_eps_parameters(),
        parameters=_shear_parameters(1.0),
        time_step_s=1.0,
        start_time_s=0.0,
    )
    physiology = advance_physiological_states(
        cells=(cell,),
        solute_fields=fields,
        cell_states=initialize_physiological_states(
            cells=(cell,), solute_fields=fields, time_s=0.0
        ),
        parameters=_physiology_parameters(),
        time_step_s=1.0,
        start_time_s=0.0,
        dry_biomass_per_unit_length_kg_m=2.0,
        detached_cell_ids=shear.detached_cell_ids,
    )

    assert physiology.cells[0].state == "detached"
    assert physiology.snapshot.totals.detached_cell_count == 1
    assert physiology.snapshot.totals.detached_biomass_kg == pytest.approx(1.0)
    assert physiology.snapshot.totals.partitioned_biomass_kg == pytest.approx(1.0)


def _metadata() -> RunMetadata:
    return RunMetadata(
        seed=5,
        parameters={"purpose": "synthetic P2-WP05 replay"},
        package_version="0.0.0",
        commit_hash="test",
        dependency_versions={"numpy": "test"},
        parameter_file="synthetic.toml",
        parameter_file_sha256="test",
        platform="test",
        python_version="3.14.test",
    )


def _write_replay(run_directory: Path) -> Path:
    cell = _cell()
    waste = _waste_field()
    shear = advance_shear_detachment(
        cells=(cell,),
        eps_field=_eps_field(),
        eps_parameters=_eps_parameters(),
        parameters=_shear_parameters(0.5),
        time_step_s=1.0,
        start_time_s=0.0,
    )
    waste_result = advance_waste(
        cells=(cell,),
        waste_field=waste,
        parameters=WasteParameters(1.0, 0.0),
        time_step_s=1.0,
        depth_m=1.0,
    )
    balance = waste_result.mass_balance
    writer = SimulationOutputWriter(run_directory, _metadata())
    writer.write_snapshot(
        time_s=1.0,
        cells=(cell,),
        solute_fields=_solute_fields(),
        division_events=(),
        mass_balance_entries=(
            MassBalanceEntry(
                quantity="waste",
                unit="mol",
                initial_amount=balance.initial_waste_mol,
                final_amount=balance.final_waste_mol,
                net_input_amount=(
                    balance.produced_waste_mol
                    - balance.removed_waste_mol
                    + balance.boundary_input_waste_mol
                ),
                absolute_tolerance=1.0e-12,
                relative_tolerance=1.0e-12,
            ),
        ),
        waste_field=waste,
        shear_snapshot=shear.snapshot,
    )
    paths = writer.finalize()
    assert paths.shear_summary_table is not None
    summary = pq.read_table(paths.shear_summary_table).to_pydict()
    assert summary["detachment_rate_s"] == [0.0]
    with np.load(paths.field_files[0], allow_pickle=False) as archive:
        assert np.array_equal(
            archive["waste_concentration_mol_m3"], waste.concentration_mol_m3
        )
    return paths.run_directory


def test_waste_and_shear_outputs_are_deterministic_replay_artifacts(
    tmp_path: Path,
) -> None:
    """Waste maps and detachment-rate output reproduce byte for byte."""
    first = _write_replay(tmp_path / "first")
    second = _write_replay(tmp_path / "second")
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


def test_waste_shear_and_history_validation_fail_explicitly() -> None:
    """Nonphysical controls and stale/unknown state interfaces fail closed."""
    with pytest.raises(WasteValidationError, match="production_rate_mol_s"):
        WasteParameters(-1.0, 0.0)
    with pytest.raises(ShearValidationError, match="threshold"):
        ShearParameters(1.0, 0.0, 1.0)
    cell = _cell()
    with pytest.raises(ShearValidationError, match="unknown"):
        initialize_shear_states(
            cells=(cell,),
            eps_field=_eps_field(),
            eps_parameters=_eps_parameters(),
            parameters=_shear_parameters(1.0),
            attached_cell_ids=frozenset({"missing"}),
            time_s=0.0,
        )
    states = initialize_shear_states(
        cells=(cell,),
        eps_field=_eps_field(),
        eps_parameters=_eps_parameters(),
        parameters=_shear_parameters(1.0),
        time_s=0.0,
    )
    with pytest.raises(ShearValidationError, match="start_time_s"):
        advance_shear_detachment(
            cells=(cell,),
            eps_field=_eps_field(),
            eps_parameters=_eps_parameters(),
            parameters=_shear_parameters(1.0),
            time_step_s=1.0,
            start_time_s=2.0,
            cell_states=states,
        )
