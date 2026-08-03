"""Boundary-aware global mass accounting for P1-WP07.

The prescribed top concentration is the only open transport boundary.  The
periodic side fluxes cancel globally and the solid bottom has zero normal
flux.  Carbon- and oxygen-equivalent totals combine field moles with living
dry biomass through the caller-provided yields.  Death loss is an explicit
outflow from those tracked totals.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from biomesh.cells import Cell
from biomesh.metabolism import MetabolismStepResult
from biomesh.outputs import MassBalanceEntry
from biomesh.solutes import SoluteField, SoluteFields


class MassAccountingError(ValueError):
    """Raised when global accounting inputs are invalid."""


def solute_amount_mol(field: SoluteField, depth_m: float) -> float:
    """Return total field amount in moles for the 2D cross-section depth."""
    _require_positive("depth_m", depth_m)
    control_volume_m3 = field.cell_width_m * field.cell_height_m * depth_m
    return float(np.sum(field.concentration_mol_m3)) * control_volume_m3


def top_boundary_input_rate_mol_s(field: SoluteField, depth_m: float) -> float:
    """Return signed inward flux through the finite-volume top boundary.

    The top-cell stencil uses a half-cell distance to the prescribed boundary,
    so the inward rate is ``2 D (C_bulk - C_top) / dy`` times top-face area.
    """
    _require_positive("depth_m", depth_m)
    top_difference_mol_m3 = (
        field.top_bulk_concentration_mol_m3
        - field.concentration_mol_m3[0, :]
    )
    top_face_area_m2 = field.cell_width_m * depth_m
    rates = (
        2.0
        * field.diffusivity_m2_s
        * top_difference_mol_m3
        / field.cell_height_m
        * top_face_area_m2
    )
    return float(np.sum(rates))


@dataclass(slots=True)
class GlobalMassAccountant:
    """Accumulate run-level P1 balance terms across deterministic steps."""

    depth_m: float
    biomass_yield_on_carbon_kg_mol: float
    biomass_yield_on_oxygen_kg_mol: float
    initial_carbon_equivalent_mol: float
    initial_oxygen_equivalent_mol: float
    initial_dry_biomass_kg: float
    cumulative_carbon_boundary_input_mol: float = 0.0
    cumulative_oxygen_boundary_input_mol: float = 0.0
    cumulative_gross_biomass_production_kg: float = 0.0
    cumulative_death_loss_kg: float = 0.0

    @classmethod
    def from_state(
        cls,
        *,
        cells: tuple[Cell, ...],
        solute_fields: SoluteFields,
        depth_m: float,
        biomass_yield_on_carbon_kg_mol: float,
        biomass_yield_on_oxygen_kg_mol: float,
    ) -> GlobalMassAccountant:
        """Initialize exact global totals before the first simulation step."""
        _require_positive("depth_m", depth_m)
        _require_positive(
            "biomass_yield_on_carbon_kg_mol",
            biomass_yield_on_carbon_kg_mol,
        )
        _require_positive(
            "biomass_yield_on_oxygen_kg_mol",
            biomass_yield_on_oxygen_kg_mol,
        )
        biomass_kg = sum(cell.dry_biomass_kg for cell in cells)
        return cls(
            depth_m=depth_m,
            biomass_yield_on_carbon_kg_mol=biomass_yield_on_carbon_kg_mol,
            biomass_yield_on_oxygen_kg_mol=biomass_yield_on_oxygen_kg_mol,
            initial_carbon_equivalent_mol=(
                solute_amount_mol(solute_fields.carbon, depth_m)
                + biomass_kg / biomass_yield_on_carbon_kg_mol
            ),
            initial_oxygen_equivalent_mol=(
                solute_amount_mol(solute_fields.oxygen, depth_m)
                + biomass_kg / biomass_yield_on_oxygen_kg_mol
            ),
            initial_dry_biomass_kg=biomass_kg,
        )

    def record_step(
        self,
        *,
        fields_before_step: SoluteFields,
        time_step_s: float,
        metabolism_result: MetabolismStepResult,
    ) -> None:
        """Record top-boundary transfer and explicit metabolic mass terms."""
        _require_positive("time_step_s", time_step_s)
        self.cumulative_carbon_boundary_input_mol += (
            top_boundary_input_rate_mol_s(fields_before_step.carbon, self.depth_m)
            * time_step_s
        )
        self.cumulative_oxygen_boundary_input_mol += (
            top_boundary_input_rate_mol_s(fields_before_step.oxygen, self.depth_m)
            * time_step_s
        )
        self.cumulative_gross_biomass_production_kg += sum(
            result.gross_biomass_production_kg
            for result in metabolism_result.cell_results
        )
        self.cumulative_death_loss_kg += sum(
            result.maintenance_death_loss_kg
            for result in metabolism_result.cell_results
        )

    def entries(
        self,
        *,
        cells: tuple[Cell, ...],
        solute_fields: SoluteFields,
        absolute_tolerance: float,
        relative_tolerance: float,
    ) -> tuple[MassBalanceEntry, ...]:
        """Return output-ready global balances for the current run state."""
        _require_nonnegative("absolute_tolerance", absolute_tolerance)
        _require_nonnegative("relative_tolerance", relative_tolerance)
        final_biomass_kg = sum(cell.dry_biomass_kg for cell in cells)
        final_carbon_equivalent_mol = (
            solute_amount_mol(solute_fields.carbon, self.depth_m)
            + final_biomass_kg / self.biomass_yield_on_carbon_kg_mol
        )
        final_oxygen_equivalent_mol = (
            solute_amount_mol(solute_fields.oxygen, self.depth_m)
            + final_biomass_kg / self.biomass_yield_on_oxygen_kg_mol
        )
        return (
            MassBalanceEntry(
                quantity="carbon_equivalent",
                unit="mol",
                initial_amount=self.initial_carbon_equivalent_mol,
                final_amount=final_carbon_equivalent_mol,
                net_input_amount=(
                    self.cumulative_carbon_boundary_input_mol
                    - self.cumulative_death_loss_kg
                    / self.biomass_yield_on_carbon_kg_mol
                ),
                absolute_tolerance=absolute_tolerance,
                relative_tolerance=relative_tolerance,
            ),
            MassBalanceEntry(
                quantity="dry_biomass",
                unit="kg",
                initial_amount=self.initial_dry_biomass_kg,
                final_amount=final_biomass_kg,
                net_input_amount=(
                    self.cumulative_gross_biomass_production_kg
                    - self.cumulative_death_loss_kg
                ),
                absolute_tolerance=absolute_tolerance,
                relative_tolerance=relative_tolerance,
            ),
            MassBalanceEntry(
                quantity="oxygen_equivalent",
                unit="mol",
                initial_amount=self.initial_oxygen_equivalent_mol,
                final_amount=final_oxygen_equivalent_mol,
                net_input_amount=(
                    self.cumulative_oxygen_boundary_input_mol
                    - self.cumulative_death_loss_kg
                    / self.biomass_yield_on_oxygen_kg_mol
                ),
                absolute_tolerance=absolute_tolerance,
                relative_tolerance=relative_tolerance,
            ),
        )


def _require_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise MassAccountingError(f"{name} must be finite and greater than zero")


def _require_nonnegative(name: str, value: float) -> None:
    if not isfinite(value) or value < 0.0:
        raise MassAccountingError(
            f"{name} must be finite and greater than or equal to zero"
        )
