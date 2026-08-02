"""P1-WP04 dual-substrate metabolism verification with synthetic SI inputs."""

from __future__ import annotations

import math

import numpy as np
import pytest

from biomesh.cells import Cell
from biomesh.metabolism import (
    MetabolismParameters,
    MetabolismValidationError,
    advance_metabolism,
    dual_substrate_monod_rate,
    evaluate_cell_metabolism,
)
from biomesh.solutes import NegativeConcentrationError, SoluteField, SoluteFields


def _parameters() -> MetabolismParameters:
    """Return dimensionally valid synthetic values, not biological constants."""
    return MetabolismParameters(
        maximum_specific_growth_rate_s=0.4,
        carbon_half_saturation_mol_m3=2.0,
        oxygen_half_saturation_mol_m3=4.0,
        death_rate_s=0.1,
        biomass_yield_on_carbon_kg_mol=2.0,
        biomass_yield_on_oxygen_kg_mol=4.0,
    )


def _cell(
    *,
    cell_id: str = "cell-a",
    x_m: float = 0.25,
    y_m: float = 0.25,
    dry_biomass_kg: float = 1.0,
) -> Cell:
    return Cell(
        cell_id=cell_id,
        x_m=x_m,
        y_m=y_m,
        orientation_rad=0.0,
        length_m=dry_biomass_kg / 2.0,
        radius_m=0.05,
        dry_biomass_kg=dry_biomass_kg,
        age_s=3.0,
        state="active",
        strain="synthetic",
    )


def _fields(
    carbon: np.ndarray[tuple[int, int], np.dtype[np.float64]],
    oxygen: np.ndarray[tuple[int, int], np.dtype[np.float64]],
) -> SoluteFields:
    shape = carbon.shape
    return SoluteFields(
        carbon=SoluteField("carbon", shape, 1.0, 1.0, 0.0, 0.0, carbon),
        oxygen=SoluteField("oxygen", shape, 1.0, 1.0, 0.0, 0.0, oxygen),
    )


def test_dual_monod_applies_both_limitation_factors() -> None:
    """Concentrations equal to their half-saturation values give mu_max/4."""
    parameters = _parameters()

    rate = dual_substrate_monod_rate(2.0, 4.0, parameters)

    assert rate == pytest.approx(parameters.maximum_specific_growth_rate_s / 4.0)


@pytest.mark.parametrize(
    ("carbon_mol_m3", "oxygen_mol_m3"),
    [(0.0, 8.0), (8.0, 0.0), (0.0, 0.0)],
)
def test_growth_halts_when_either_required_substrate_is_absent(
    carbon_mol_m3: float,
    oxygen_mol_m3: float,
) -> None:
    """An absent required substrate prevents growth and associated uptake."""
    parameters = _parameters()

    result = evaluate_cell_metabolism(
        1.0, carbon_mol_m3, oxygen_mol_m3, 2.0, parameters
    )

    assert result.specific_growth_rate_s == 0.0
    assert result.gross_biomass_production_kg == 0.0
    assert result.carbon_uptake_mol == 0.0
    assert result.oxygen_uptake_mol == 0.0
    assert result.final_dry_biomass_kg == pytest.approx(
        math.exp(-parameters.death_rate_s * 2.0)
    )


def test_well_mixed_growth_matches_expected_ode_solution() -> None:
    """Fixed well-mixed concentrations match the analytical biomass ODE."""
    parameters = _parameters()
    initial_biomass_kg = 1.7
    time_step_s = 3.5
    expected_mu_s = 0.4 * (6.0 / 8.0) * (12.0 / 16.0)

    result = evaluate_cell_metabolism(
        initial_biomass_kg,
        carbon_concentration_mol_m3=6.0,
        oxygen_concentration_mol_m3=12.0,
        time_step_s=time_step_s,
        parameters=parameters,
    )

    expected_biomass_kg = initial_biomass_kg * math.exp(
        (expected_mu_s - parameters.death_rate_s) * time_step_s
    )
    assert result.specific_growth_rate_s == pytest.approx(expected_mu_s)
    assert result.final_dry_biomass_kg == pytest.approx(expected_biomass_kg)


def test_integrated_yields_and_death_close_biomass_balance() -> None:
    """Each yield accounts for gross production and k_d for biomass loss."""
    parameters = _parameters()

    result = evaluate_cell_metabolism(2.0, 3.0, 5.0, 0.75, parameters)

    biomass_change_kg = (
        result.final_dry_biomass_kg - result.initial_dry_biomass_kg
    )
    assert biomass_change_kg + result.maintenance_death_loss_kg == pytest.approx(
        result.gross_biomass_production_kg
    )
    assert (
        result.carbon_uptake_mol
        * parameters.biomass_yield_on_carbon_kg_mol
        == pytest.approx(result.gross_biomass_production_kg)
    )
    assert (
        result.oxygen_uptake_mol
        * parameters.biomass_yield_on_oxygen_kg_mol
        == pytest.approx(result.gross_biomass_production_kg)
    )


def test_closed_system_field_and_biomass_mass_balance() -> None:
    """Coupled uptake equals field loss and yield-equivalent biomass gain."""
    fields = _fields(
        np.full((2, 2), 20.0, dtype=np.float64),
        np.full((2, 2), 20.0, dtype=np.float64),
    )
    initial_carbon_mol = float(np.sum(fields.carbon.concentration_mol_m3)) * 0.25
    initial_oxygen_mol = float(np.sum(fields.oxygen.concentration_mol_m3)) * 0.25

    step = advance_metabolism(
        [_cell()], fields, 0.5, 1.0, 2.0, _parameters()
    )

    result = step.cell_results[0]
    final_carbon_mol = float(np.sum(fields.carbon.concentration_mol_m3)) * 0.25
    final_oxygen_mol = float(np.sum(fields.oxygen.concentration_mol_m3)) * 0.25
    assert initial_carbon_mol - final_carbon_mol == pytest.approx(
        result.carbon_uptake_mol
    )
    assert initial_oxygen_mol - final_oxygen_mol == pytest.approx(
        result.oxygen_uptake_mol
    )
    assert (
        step.cells[0].dry_biomass_kg
        - result.initial_dry_biomass_kg
        + result.maintenance_death_loss_kg
        == pytest.approx(result.gross_biomass_production_kg)
    )


def _closed_system_state(time_step_s: float) -> np.ndarray:
    """Return a synthetic closed-system state after one simulated second."""
    fields = _fields(
        np.full((2, 2), 2.0, dtype=np.float64),
        np.full((2, 2), 4.0, dtype=np.float64),
    )
    cell = _cell()
    step_count = round(1.0 / time_step_s)
    for _ in range(step_count):
        cell = advance_metabolism(
            [cell], fields, time_step_s, 1.0, 2.0, _parameters()
        ).cells[0]
    return np.array(
        [
            cell.dry_biomass_kg,
            fields.carbon.concentration_mol_m3[0, 0],
            fields.oxygen.concentration_mol_m3[0, 0],
        ]
    )


def test_closed_system_time_step_refinement_converges() -> None:
    """Operator-split metabolism approaches a refined closed-system result."""
    reference = _closed_system_state(0.0125)
    coarse_error = float(np.max(np.abs(_closed_system_state(0.2) - reference)))
    fine_error = float(np.max(np.abs(_closed_system_state(0.1) - reference)))

    assert fine_error < coarse_error


def test_coupling_uses_each_cells_local_control_volume() -> None:
    """Local limitations produce distinct growth and localized field uptake."""
    carbon = np.array([[2.0, 8.0], [2.0, 8.0]], dtype=np.float64)
    oxygen = np.array([[4.0, 16.0], [4.0, 16.0]], dtype=np.float64)
    fields = _fields(carbon, oxygen)

    step = advance_metabolism(
        [_cell(), _cell(cell_id="cell-b", x_m=0.75)],
        fields,
        time_step_s=0.2,
        depth_m=1.0,
        dry_biomass_per_unit_length_kg_m=2.0,
        parameters=_parameters(),
    )

    assert step.cell_results[1].specific_growth_rate_s > (
        step.cell_results[0].specific_growth_rate_s
    )
    assert fields.carbon.concentration_mol_m3[0, 0] < carbon[0, 0]
    assert fields.carbon.concentration_mol_m3[0, 1] < carbon[0, 1]
    assert np.array_equal(fields.carbon.concentration_mol_m3[1], carbon[1])
    assert step.cells[0].age_s == pytest.approx(3.2)
    assert step.cells[0].length_m == pytest.approx(
        step.cells[0].dry_biomass_kg / 2.0
    )


def test_coupled_step_is_deterministic_for_identical_inputs() -> None:
    """Metabolism introduces no hidden stochasticity or ordering state."""
    carbon = np.full((2, 2), 10.0, dtype=np.float64)
    oxygen = np.full((2, 2), 10.0, dtype=np.float64)
    first_fields = _fields(carbon, oxygen)
    second_fields = _fields(carbon, oxygen)

    first = advance_metabolism(
        [_cell()], first_fields, 0.25, 1.0, 2.0, _parameters()
    )
    second = advance_metabolism(
        [_cell()], second_fields, 0.25, 1.0, 2.0, _parameters()
    )

    assert first == second
    assert np.array_equal(
        first_fields.carbon.concentration_mol_m3,
        second_fields.carbon.concentration_mol_m3,
    )
    assert np.array_equal(
        first_fields.oxygen.concentration_mol_m3,
        second_fields.oxygen.concentration_mol_m3,
    )


def test_insufficient_solute_fails_without_partial_field_update() -> None:
    """A rejected uptake step leaves both coupled fields unchanged."""
    fields = _fields(
        np.full((2, 2), 10.0, dtype=np.float64),
        np.full((2, 2), 10.0, dtype=np.float64),
    )
    parameters = MetabolismParameters(
        maximum_specific_growth_rate_s=0.4,
        carbon_half_saturation_mol_m3=2.0,
        oxygen_half_saturation_mol_m3=4.0,
        death_rate_s=0.1,
        biomass_yield_on_carbon_kg_mol=1.0e12,
        biomass_yield_on_oxygen_kg_mol=1.0e-6,
    )
    carbon_before = fields.carbon.concentration_mol_m3.copy()
    oxygen_before = fields.oxygen.concentration_mol_m3.copy()

    with pytest.raises(NegativeConcentrationError):
        advance_metabolism([_cell()], fields, 1.0, 1.0, 2.0, parameters)

    assert np.array_equal(fields.carbon.concentration_mol_m3, carbon_before)
    assert np.array_equal(fields.oxygen.concentration_mol_m3, oxygen_before)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("maximum_specific_growth_rate_s", 0.0),
        ("carbon_half_saturation_mol_m3", -1.0),
        ("oxygen_half_saturation_mol_m3", math.inf),
        ("death_rate_s", -0.1),
        ("biomass_yield_on_carbon_kg_mol", 0.0),
        ("biomass_yield_on_oxygen_kg_mol", math.nan),
    ],
)
def test_invalid_metabolic_parameters_fail_explicitly(
    field: str, value: float
) -> None:
    """Invalid parameters are rejected instead of corrected or defaulted."""
    values = {
        "maximum_specific_growth_rate_s": 0.4,
        "carbon_half_saturation_mol_m3": 2.0,
        "oxygen_half_saturation_mol_m3": 4.0,
        "death_rate_s": 0.1,
        "biomass_yield_on_carbon_kg_mol": 2.0,
        "biomass_yield_on_oxygen_kg_mol": 4.0,
    }
    values[field] = value

    with pytest.raises(MetabolismValidationError, match=field):
        MetabolismParameters(**values)


def test_negative_local_concentration_fails_explicitly() -> None:
    """The kinetics boundary rejects a nonphysical local concentration."""
    with pytest.raises(
        MetabolismValidationError, match="carbon_concentration_mol_m3"
    ):
        dual_substrate_monod_rate(-1.0e-6, 1.0, _parameters())
