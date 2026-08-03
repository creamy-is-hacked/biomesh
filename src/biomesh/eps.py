"""Deterministic quorum-controlled EPS allocation and accumulation for P2-WP02.

EPS is an immobile local density field in ``kg m^-3``.  For each cell, the
existing quorum activation fraction ``Q`` determines the anabolic allocation
``a = f_EPS * Q``.  Metabolism then integrates

``dX/dt = ((1 - a) * mu - k_d) * X``

and deposits ``a * mu * X`` as biomass-equivalent EPS mass in the control
volume containing the cell centre.  Substrate uptake is charged against the
full gross anabolic production, so retained biomass, EPS, death, and substrate
accounting reconcile explicitly.  No EPS loss, transport, or detachment law is
introduced in this work package.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isclose, isfinite

import numpy as np
from numpy.typing import NDArray

from biomesh.cells import Cell
from biomesh.metabolism import (
    MetabolismParameters,
    MetabolismStepResult,
    advance_metabolism,
)
from biomesh.quorum import CellQuorumState
from biomesh.solutes import SoluteFields

FloatArray = NDArray[np.float64]
TIME_MATCH_RELATIVE_TOLERANCE = 1.0e-12
TIME_MATCH_ABSOLUTE_TOLERANCE_S = 1.0e-15


class EPSValidationError(ValueError):
    """Raised when EPS parameters, state, or coupling inputs are invalid."""


@dataclass(frozen=True, slots=True)
class EPSParameters:
    """Caller-provided biological parameters for the P2-WP02 abstraction.

    The two sensitivities convert local EPS density to dimensionless
    multipliers.  A multiplier of one is the no-EPS reference; no absolute
    adhesion force law or unapproved mechanical constant is implied.
    """

    maximum_allocation_fraction: float
    cohesion_sensitivity_m3_kg: float
    attachment_strength_sensitivity_m3_kg: float

    def __post_init__(self) -> None:
        _require_fraction(
            "maximum_allocation_fraction", self.maximum_allocation_fraction
        )
        _require_nonnegative(
            "cohesion_sensitivity_m3_kg", self.cohesion_sensitivity_m3_kg
        )
        _require_nonnegative(
            "attachment_strength_sensitivity_m3_kg",
            self.attachment_strength_sensitivity_m3_kg,
        )


@dataclass(slots=True)
class EPSField:
    """Immobile local EPS density on the audited finite-volume geometry."""

    shape: tuple[int, int]
    width_m: float
    height_m: float
    depth_m: float
    density_kg_m3: FloatArray

    def __post_init__(self) -> None:
        rows, columns = self.shape
        if rows < 2 or columns < 2:
            raise EPSValidationError(
                "EPS grid shape must contain at least 2 by 2 cells"
            )
        _require_positive("width_m", self.width_m)
        _require_positive("height_m", self.height_m)
        _require_positive("depth_m", self.depth_m)
        density = np.asarray(self.density_kg_m3, dtype=np.float64)
        if density.shape != self.shape:
            raise EPSValidationError(
                "density_kg_m3 shape must match the configured EPS grid shape"
            )
        if not np.all(np.isfinite(density)):
            raise EPSValidationError("density_kg_m3 must contain finite values")
        if float(np.min(density)) < 0.0:
            raise EPSValidationError("density_kg_m3 cannot contain negative values")
        self.density_kg_m3 = density.copy()

    @property
    def cell_width_m(self) -> float:
        """Horizontal control-volume width in metres."""
        return self.width_m / self.shape[1]

    @property
    def cell_height_m(self) -> float:
        """Vertical control-volume height in metres."""
        return self.height_m / self.shape[0]

    @property
    def control_volume_m3(self) -> float:
        """Volume represented by one EPS grid cell in cubic metres."""
        return self.cell_width_m * self.cell_height_m * self.depth_m

    @property
    def total_mass_kg(self) -> float:
        """Total EPS mass represented by the density field."""
        return float(np.sum(self.density_kg_m3)) * self.control_volume_m3

    def cell_index(self, x_m: float, y_m: float) -> tuple[int, int]:
        """Return the audited top-first grid index for a physical position."""
        if not isfinite(x_m) or not isfinite(y_m):
            raise EPSValidationError("cell coordinates must be finite")
        if not 0.0 <= x_m < self.width_m:
            raise EPSValidationError("cell x_m must be within [0, width_m)")
        if not 0.0 <= y_m < self.height_m:
            raise EPSValidationError("cell y_m must be within [0, height_m)")
        row_from_bottom = int(y_m / self.cell_height_m)
        row = self.shape[0] - 1 - row_from_bottom
        return row, int(x_m / self.cell_width_m)

    def density_at(self, x_m: float, y_m: float) -> float:
        """Return local EPS density at one physical position."""
        row, column = self.cell_index(x_m, y_m)
        return float(self.density_kg_m3[row, column])


@dataclass(frozen=True, slots=True)
class CellEPSProduction:
    """One cell's quorum-controlled EPS allocation for an accepted step."""

    cell_id: str
    activation_fraction: float
    allocation_fraction: float
    produced_eps_kg: float


@dataclass(frozen=True, slots=True)
class EPSMassBalance:
    """Living-biomass and EPS accounting for one coupled step."""

    initial_living_biomass_kg: float
    final_living_biomass_kg: float
    gross_biomass_equivalent_production_kg: float
    maintenance_death_loss_kg: float
    initial_eps_kg: float
    final_eps_kg: float
    produced_eps_kg: float

    @property
    def eps_residual_kg(self) -> float:
        """Return ``final EPS - initial EPS - produced EPS``."""
        return self.final_eps_kg - self.initial_eps_kg - self.produced_eps_kg

    @property
    def biomass_equivalent_residual_kg(self) -> float:
        """Return the coupled living-biomass plus EPS allocation residual."""
        return (
            self.final_living_biomass_kg
            + self.final_eps_kg
            - self.initial_living_biomass_kg
            - self.initial_eps_kg
            - self.gross_biomass_equivalent_production_kg
            + self.maintenance_death_loss_kg
        )


@dataclass(frozen=True, slots=True)
class EPSStepResult:
    """Accepted coupled metabolism, cell-local production, and accounting."""

    metabolism: MetabolismStepResult
    cell_production: tuple[CellEPSProduction, ...]
    mass_balance: EPSMassBalance

    @property
    def cells(self) -> tuple[Cell, ...]:
        """Return cells after growth cost has been charged."""
        return self.metabolism.cells


@dataclass(frozen=True, slots=True)
class EPSMechanicalModifiers:
    """Local relative cohesion and attachment strength due to EPS."""

    eps_density_kg_m3: float
    cohesion_multiplier: float
    attachment_strength_multiplier: float


def advance_eps_metabolism(
    *,
    cells: Sequence[Cell],
    solute_fields: SoluteFields,
    eps_field: EPSField,
    quorum_states: Sequence[CellQuorumState],
    eps_parameters: EPSParameters,
    metabolism_parameters: MetabolismParameters,
    time_step_s: float,
    start_time_s: float,
    dry_biomass_per_unit_length_kg_m: float,
) -> EPSStepResult:
    """Advance quorum-controlled EPS allocation and coupled metabolism once.

    Quorum activation is sampled from each cell's current immutable state.
    Cells are processed in identifier order.  Carbon, oxygen, and EPS fields
    are restored in place if any part of the coupled update fails.
    """
    _require_positive("time_step_s", time_step_s)
    _require_nonnegative("start_time_s", start_time_s)
    _validate_shared_geometry(solute_fields, eps_field)
    ordered_cells = _validated_cells(cells)
    states = _validated_quorum_states(ordered_cells, quorum_states, start_time_s)
    state_by_id = {state.cell_id: state for state in states}
    allocations = {
        cell.cell_id: (
            eps_parameters.maximum_allocation_fraction
            * state_by_id[cell.cell_id].current.activation_fraction
        )
        for cell in ordered_cells
    }
    initial_living_biomass_kg = sum(
        cell.dry_biomass_kg for cell in ordered_cells
    )
    initial_eps_kg = eps_field.total_mass_kg
    carbon_before = solute_fields.carbon.concentration_mol_m3.copy()
    oxygen_before = solute_fields.oxygen.concentration_mol_m3.copy()
    eps_before = eps_field.density_kg_m3.copy()
    try:
        metabolism = advance_metabolism(
            ordered_cells,
            solute_fields,
            time_step_s,
            eps_field.depth_m,
            dry_biomass_per_unit_length_kg_m,
            metabolism_parameters,
            growth_allocation_fractions=allocations,
        )
        density_increase_kg_m3 = np.zeros(eps_field.shape, dtype=np.float64)
        production: list[CellEPSProduction] = []
        for cell, result in zip(
            ordered_cells, metabolism.cell_results, strict=True
        ):
            produced_eps_kg = result.allocated_biomass_equivalent_kg
            row, column = eps_field.cell_index(cell.x_m, cell.y_m)
            density_increase_kg_m3[row, column] += (
                produced_eps_kg / eps_field.control_volume_m3
            )
            production.append(
                CellEPSProduction(
                    cell_id=cell.cell_id,
                    activation_fraction=(
                        state_by_id[cell.cell_id].current.activation_fraction
                    ),
                    allocation_fraction=allocations[cell.cell_id],
                    produced_eps_kg=produced_eps_kg,
                )
            )
        candidate_density = eps_field.density_kg_m3 + density_increase_kg_m3
        if not np.all(np.isfinite(candidate_density)):
            raise EPSValidationError("EPS accumulation would be non-finite")
        eps_field.density_kg_m3 = candidate_density
    except Exception:
        solute_fields.carbon.concentration_mol_m3[...] = carbon_before
        solute_fields.oxygen.concentration_mol_m3[...] = oxygen_before
        eps_field.density_kg_m3[...] = eps_before
        raise

    gross_production_kg = sum(
        result.gross_biomass_production_kg
        for result in metabolism.cell_results
    )
    death_loss_kg = sum(
        result.maintenance_death_loss_kg for result in metabolism.cell_results
    )
    produced_eps_kg = sum(record.produced_eps_kg for record in production)
    return EPSStepResult(
        metabolism=metabolism,
        cell_production=tuple(production),
        mass_balance=EPSMassBalance(
            initial_living_biomass_kg=initial_living_biomass_kg,
            final_living_biomass_kg=sum(
                cell.dry_biomass_kg for cell in metabolism.cells
            ),
            gross_biomass_equivalent_production_kg=gross_production_kg,
            maintenance_death_loss_kg=death_loss_kg,
            initial_eps_kg=initial_eps_kg,
            final_eps_kg=eps_field.total_mass_kg,
            produced_eps_kg=produced_eps_kg,
        ),
    )


def local_mechanical_modifiers(
    *,
    eps_field: EPSField,
    x_m: float,
    y_m: float,
    parameters: EPSParameters,
) -> EPSMechanicalModifiers:
    """Return monotone local EPS cohesion and attachment multipliers."""
    density_kg_m3 = eps_field.density_at(x_m, y_m)
    return EPSMechanicalModifiers(
        eps_density_kg_m3=density_kg_m3,
        cohesion_multiplier=(
            1.0 + parameters.cohesion_sensitivity_m3_kg * density_kg_m3
        ),
        attachment_strength_multiplier=(
            1.0
            + parameters.attachment_strength_sensitivity_m3_kg * density_kg_m3
        ),
    )


def _validate_shared_geometry(
    solute_fields: SoluteFields,
    eps_field: EPSField,
) -> None:
    carbon = solute_fields.carbon
    if (
        eps_field.shape != carbon.shape
        or eps_field.width_m != carbon.width_m
        or eps_field.height_m != carbon.height_m
    ):
        raise EPSValidationError("EPS field must share the solute grid geometry")


def _validated_cells(cells: Sequence[Cell]) -> tuple[Cell, ...]:
    validated = tuple(cells)
    if any(not isinstance(cell, Cell) for cell in validated):
        raise EPSValidationError("cells must contain only Cell instances")
    identifiers = [cell.cell_id for cell in validated]
    if len(identifiers) != len(set(identifiers)):
        raise EPSValidationError("cell IDs must be unique")
    return tuple(sorted(validated, key=lambda cell: cell.cell_id))


def _validated_quorum_states(
    cells: tuple[Cell, ...],
    states: Sequence[CellQuorumState],
    start_time_s: float,
) -> tuple[CellQuorumState, ...]:
    validated = tuple(states)
    if any(not isinstance(state, CellQuorumState) for state in validated):
        raise EPSValidationError(
            "quorum_states must contain only CellQuorumState instances"
        )
    state_by_id = {state.cell_id: state for state in validated}
    cell_ids = {cell.cell_id for cell in cells}
    if len(state_by_id) != len(validated) or set(state_by_id) != cell_ids:
        raise EPSValidationError(
            "quorum_states must contain exactly one state for every cell"
        )
    if any(
        not isclose(
            state.current.time_s,
            start_time_s,
            rel_tol=TIME_MATCH_RELATIVE_TOLERANCE,
            abs_tol=TIME_MATCH_ABSOLUTE_TOLERANCE_S,
        )
        for state in validated
    ):
        raise EPSValidationError(
            "current quorum observation time must equal start_time_s"
        )
    return tuple(state_by_id[cell.cell_id] for cell in cells)


def _require_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise EPSValidationError(f"{name} must be finite and greater than zero")


def _require_nonnegative(name: str, value: float) -> None:
    if not isfinite(value) or value < 0.0:
        raise EPSValidationError(
            f"{name} must be finite and greater than or equal to zero"
        )


def _require_fraction(name: str, value: float) -> None:
    if not isfinite(value) or not 0.0 <= value <= 1.0:
        raise EPSValidationError(f"{name} must be finite and within [0, 1]")
