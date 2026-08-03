"""Deterministic dual-substrate metabolism for P1-WP04.

The specific growth rate follows the P1 multiplicative Monod law::

    mu = mu_max * S / (K_S + S) * O / (K_O + O)

For one metabolism step, the local carbon and oxygen concentrations are
sampled from the cell's control volume and held constant.  Biomass is then
integrated exactly under ``dX/dt = (mu - k_d) X``.  Growth-associated carbon
and oxygen uptake are calculated independently from explicit yields in
``kg biomass mol^-1``.  The configured ``k_d`` is the P1 maintenance/death
biomass-loss term; no unsupported maintenance-uptake equation is introduced.

All values use SI units.  This module contains no biological defaults.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from math import exp, expm1, isfinite

from biomesh.cells import Cell
from biomesh.solutes import CellSoluteExchange, SoluteFields


class MetabolismValidationError(ValueError):
    """Raised when metabolic inputs are invalid or an update is non-finite."""


@dataclass(frozen=True, slots=True)
class MetabolismParameters:
    """Caller-provided SI parameters for dual-substrate metabolism.

    Every field is a biological parameter requiring a validated provenance
    record before scientific use.  No value is inferred or defaulted here.
    """

    maximum_specific_growth_rate_s: float
    carbon_half_saturation_mol_m3: float
    oxygen_half_saturation_mol_m3: float
    death_rate_s: float
    biomass_yield_on_carbon_kg_mol: float
    biomass_yield_on_oxygen_kg_mol: float

    def __post_init__(self) -> None:
        _require_positive(
            "maximum_specific_growth_rate_s",
            self.maximum_specific_growth_rate_s,
        )
        _require_positive(
            "carbon_half_saturation_mol_m3",
            self.carbon_half_saturation_mol_m3,
        )
        _require_positive(
            "oxygen_half_saturation_mol_m3",
            self.oxygen_half_saturation_mol_m3,
        )
        _require_nonnegative("death_rate_s", self.death_rate_s)
        _require_positive(
            "biomass_yield_on_carbon_kg_mol",
            self.biomass_yield_on_carbon_kg_mol,
        )
        _require_positive(
            "biomass_yield_on_oxygen_kg_mol",
            self.biomass_yield_on_oxygen_kg_mol,
        )


@dataclass(frozen=True, slots=True)
class CellMetabolismResult:
    """Integrated biomass and uptake accounting for one cell and one step."""

    initial_dry_biomass_kg: float
    final_dry_biomass_kg: float
    specific_growth_rate_s: float
    gross_biomass_production_kg: float
    maintenance_death_loss_kg: float
    carbon_uptake_mol: float
    oxygen_uptake_mol: float


@dataclass(frozen=True, slots=True)
class MetabolismStepResult:
    """Updated cells and per-cell accounting from a coupled metabolism step."""

    cells: tuple[Cell, ...]
    cell_results: tuple[CellMetabolismResult, ...]


def dual_substrate_monod_rate(
    carbon_concentration_mol_m3: float,
    oxygen_concentration_mol_m3: float,
    parameters: MetabolismParameters,
) -> float:
    """Return the dual-substrate specific growth rate in ``s^-1``."""
    _require_nonnegative(
        "carbon_concentration_mol_m3", carbon_concentration_mol_m3
    )
    _require_nonnegative(
        "oxygen_concentration_mol_m3", oxygen_concentration_mol_m3
    )
    carbon_limitation = carbon_concentration_mol_m3 / (
        parameters.carbon_half_saturation_mol_m3
        + carbon_concentration_mol_m3
    )
    oxygen_limitation = oxygen_concentration_mol_m3 / (
        parameters.oxygen_half_saturation_mol_m3
        + oxygen_concentration_mol_m3
    )
    return (
        parameters.maximum_specific_growth_rate_s
        * carbon_limitation
        * oxygen_limitation
    )


def evaluate_cell_metabolism(
    initial_dry_biomass_kg: float,
    carbon_concentration_mol_m3: float,
    oxygen_concentration_mol_m3: float,
    time_step_s: float,
    parameters: MetabolismParameters,
) -> CellMetabolismResult:
    """Integrate one cell at fixed local concentrations for ``time_step_s``.

    Uptake is integrated over the same exact biomass trajectory as growth and
    death, which provides an explicit closed-system accounting identity for
    each substrate.
    """
    _require_positive("initial_dry_biomass_kg", initial_dry_biomass_kg)
    _require_positive("time_step_s", time_step_s)
    specific_growth_rate_s = dual_substrate_monod_rate(
        carbon_concentration_mol_m3,
        oxygen_concentration_mol_m3,
        parameters,
    )
    net_specific_rate_s = specific_growth_rate_s - parameters.death_rate_s
    exponent = net_specific_rate_s * time_step_s
    try:
        final_dry_biomass_kg = initial_dry_biomass_kg * exp(exponent)
        if net_specific_rate_s == 0.0:
            integrated_biomass_kg_s = initial_dry_biomass_kg * time_step_s
        else:
            integrated_biomass_kg_s = (
                initial_dry_biomass_kg * expm1(exponent) / net_specific_rate_s
            )
    except OverflowError as error:
        raise MetabolismValidationError(
            "metabolism step produces non-finite biomass; reduce time_step_s"
        ) from error
    if (
        not isfinite(final_dry_biomass_kg)
        or final_dry_biomass_kg <= 0.0
        or not isfinite(integrated_biomass_kg_s)
    ):
        raise MetabolismValidationError(
            "metabolism step produces non-positive or non-finite biomass; "
            "reduce time_step_s"
        )

    gross_biomass_production_kg = (
        specific_growth_rate_s * integrated_biomass_kg_s
    )
    maintenance_death_loss_kg = (
        parameters.death_rate_s * integrated_biomass_kg_s
    )
    carbon_uptake_mol = (
        gross_biomass_production_kg
        / parameters.biomass_yield_on_carbon_kg_mol
    )
    oxygen_uptake_mol = (
        gross_biomass_production_kg
        / parameters.biomass_yield_on_oxygen_kg_mol
    )
    return CellMetabolismResult(
        initial_dry_biomass_kg=initial_dry_biomass_kg,
        final_dry_biomass_kg=final_dry_biomass_kg,
        specific_growth_rate_s=specific_growth_rate_s,
        gross_biomass_production_kg=gross_biomass_production_kg,
        maintenance_death_loss_kg=maintenance_death_loss_kg,
        carbon_uptake_mol=carbon_uptake_mol,
        oxygen_uptake_mol=oxygen_uptake_mol,
    )


def advance_metabolism(
    cells: Sequence[Cell],
    solute_fields: SoluteFields,
    time_step_s: float,
    depth_m: float,
    dry_biomass_per_unit_length_kg_m: float,
    parameters: MetabolismParameters,
) -> MetabolismStepResult:
    """Couple cell-local metabolism to carbon and oxygen solute fields.

    All cells sample the fields at the beginning of the step.  Their exchange
    rates are accumulated before either field is advanced, making the result
    independent of cell evaluation order except for the returned tuple order.
    Field mutations are rolled back if either solute update fails, and cells
    are returned only after both field updates succeed.
    """
    _require_positive("time_step_s", time_step_s)
    _require_positive("depth_m", depth_m)
    _require_positive(
        "dry_biomass_per_unit_length_kg_m",
        dry_biomass_per_unit_length_kg_m,
    )
    results: list[CellMetabolismResult] = []
    exchanges: list[CellSoluteExchange] = []
    updated_cells: list[Cell] = []
    for cell in cells:
        carbon_row, carbon_column = solute_fields.carbon.cell_index(
            cell.x_m, cell.y_m
        )
        oxygen_row, oxygen_column = solute_fields.oxygen.cell_index(
            cell.x_m, cell.y_m
        )
        result = evaluate_cell_metabolism(
            initial_dry_biomass_kg=cell.dry_biomass_kg,
            carbon_concentration_mol_m3=float(
                solute_fields.carbon.concentration_mol_m3[
                    carbon_row, carbon_column
                ]
            ),
            oxygen_concentration_mol_m3=float(
                solute_fields.oxygen.concentration_mol_m3[
                    oxygen_row, oxygen_column
                ]
            ),
            time_step_s=time_step_s,
            parameters=parameters,
        )
        results.append(result)
        exchanges.append(
            CellSoluteExchange(
                x_m=cell.x_m,
                y_m=cell.y_m,
                carbon_rate_mol_s=-result.carbon_uptake_mol / time_step_s,
                oxygen_rate_mol_s=-result.oxygen_uptake_mol / time_step_s,
            )
        )
        resized_cell = cell.with_dry_biomass(
            result.final_dry_biomass_kg,
            dry_biomass_per_unit_length_kg_m,
        )
        updated_cells.append(replace(resized_cell, age_s=cell.age_s + time_step_s))

    carbon_before = solute_fields.carbon.concentration_mol_m3.copy()
    oxygen_before = solute_fields.oxygen.concentration_mol_m3.copy()
    try:
        solute_fields.advance_with_cell_exchanges(
            time_step_s=time_step_s,
            exchanges=exchanges,
            depth_m=depth_m,
        )
    except Exception:
        solute_fields.carbon.concentration_mol_m3[...] = carbon_before
        solute_fields.oxygen.concentration_mol_m3[...] = oxygen_before
        raise

    return MetabolismStepResult(tuple(updated_cells), tuple(results))


def _require_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise MetabolismValidationError(
            f"{name} must be finite and greater than zero"
        )


def _require_nonnegative(name: str, value: float) -> None:
    if not isfinite(value) or value < 0.0:
        raise MetabolismValidationError(
            f"{name} must be finite and greater than or equal to zero"
        )
