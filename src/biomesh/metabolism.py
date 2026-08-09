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

from collections.abc import Mapping, Sequence
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
    retained_biomass_production_kg: float
    allocated_biomass_equivalent_kg: float
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
    return evaluate_allocated_cell_metabolism(
        initial_dry_biomass_kg=initial_dry_biomass_kg,
        carbon_concentration_mol_m3=carbon_concentration_mol_m3,
        oxygen_concentration_mol_m3=oxygen_concentration_mol_m3,
        time_step_s=time_step_s,
        parameters=parameters,
        growth_allocation_fraction=0.0,
    )


def evaluate_allocated_cell_metabolism(
    initial_dry_biomass_kg: float,
    carbon_concentration_mol_m3: float,
    oxygen_concentration_mol_m3: float,
    time_step_s: float,
    parameters: MetabolismParameters,
    *,
    growth_allocation_fraction: float,
    metabolic_activity_fraction: float = 1.0,
) -> CellMetabolismResult:
    """Integrate metabolism with an explicit gross-production allocation.

    ``growth_allocation_fraction`` diverts that fraction of ``mu * X`` away
    from retained cell biomass.  Substrate uptake remains tied to the full
    gross biomass-equivalent production, so callers can account for the
    allocated material in another explicitly modelled pool.  P1 callers use
    :func:`evaluate_cell_metabolism`, which fixes the allocation to zero.
    ``metabolic_activity_fraction`` is the optional P2-WP04 multiplier applied
    to both growth and the existing maintenance/death term; its default one
    preserves the audited P1 equation.
    """
    _require_positive("initial_dry_biomass_kg", initial_dry_biomass_kg)
    _require_positive("time_step_s", time_step_s)
    _require_fraction("growth_allocation_fraction", growth_allocation_fraction)
    _require_fraction("metabolic_activity_fraction", metabolic_activity_fraction)
    specific_growth_rate_s = dual_substrate_monod_rate(
        carbon_concentration_mol_m3,
        oxygen_concentration_mol_m3,
        parameters,
    ) * metabolic_activity_fraction
    effective_death_rate_s = parameters.death_rate_s * metabolic_activity_fraction
    retained_specific_growth_rate_s = (
        (1.0 - growth_allocation_fraction) * specific_growth_rate_s
    )
    net_specific_rate_s = retained_specific_growth_rate_s - effective_death_rate_s
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
    allocated_biomass_equivalent_kg = (
        growth_allocation_fraction * gross_biomass_production_kg
    )
    retained_biomass_production_kg = (
        gross_biomass_production_kg - allocated_biomass_equivalent_kg
    )
    maintenance_death_loss_kg = (
        effective_death_rate_s * integrated_biomass_kg_s
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
        retained_biomass_production_kg=retained_biomass_production_kg,
        allocated_biomass_equivalent_kg=allocated_biomass_equivalent_kg,
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
    *,
    growth_allocation_fractions: Mapping[str, float] | None = None,
    metabolic_activity_fractions: Mapping[str, float] | None = None,
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
    allocations = _validated_allocations(cells, growth_allocation_fractions)
    activities = _validated_activity_fractions(cells, metabolic_activity_fractions)
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
        result = evaluate_allocated_cell_metabolism(
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
            growth_allocation_fraction=allocations[cell.cell_id],
            metabolic_activity_fraction=activities[cell.cell_id],
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


def _validated_allocations(
    cells: Sequence[Cell],
    allocations: Mapping[str, float] | None,
) -> dict[str, float]:
    cell_ids = [cell.cell_id for cell in cells]
    if len(cell_ids) != len(set(cell_ids)):
        raise MetabolismValidationError("cell IDs must be unique")
    if allocations is None:
        return dict.fromkeys(cell_ids, 0.0)
    if not isinstance(allocations, Mapping) or set(allocations) != set(cell_ids):
        raise MetabolismValidationError(
            "growth_allocation_fractions must contain exactly one value for "
            "every cell"
        )
    validated: dict[str, float] = {}
    for cell_id in cell_ids:
        allocation = allocations[cell_id]
        _require_fraction(
            f"growth_allocation_fractions[{cell_id!r}]",
            allocation,
        )
        validated[cell_id] = allocation
    return validated


def _validated_activity_fractions(
    cells: Sequence[Cell],
    activities: Mapping[str, float] | None,
) -> dict[str, float]:
    cell_ids = [cell.cell_id for cell in cells]
    if activities is None:
        return dict.fromkeys(cell_ids, 1.0)
    if not isinstance(activities, Mapping) or set(activities) != set(cell_ids):
        raise MetabolismValidationError(
            "metabolic_activity_fractions must contain exactly one value for "
            "every cell"
        )
    validated: dict[str, float] = {}
    for cell_id in cell_ids:
        activity = activities[cell_id]
        _require_fraction(
            f"metabolic_activity_fractions[{cell_id!r}]",
            activity,
        )
        validated[cell_id] = activity
    return validated


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


def _require_fraction(name: str, value: float) -> None:
    if not isfinite(value) or not 0.0 <= value <= 1.0:
        raise MetabolismValidationError(f"{name} must be finite and within [0, 1]")
