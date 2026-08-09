"""Deterministic diffusing waste transport for P2-WP05.

Waste concentration is stored in ``mol m^-3`` using the audited
:class:`biomesh.solutes.SoluteField` finite-volume operator.  Each cell emits
the caller-configured whole-cell rate in ``mol s^-1``; an optional activity
mapping permits the physiological state model to set dead and detached
production to zero without inventing a biomass-to-waste conversion.  Explicit
first-order removal and the prescribed top boundary are included in the
discrete molar ledger.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite

import numpy as np

from biomesh.cells import Cell
from biomesh.solutes import DiffusionStabilityError, SoluteField


class WasteValidationError(ValueError):
    """Raised when waste transport inputs are invalid or inconsistent."""


@dataclass(frozen=True, slots=True)
class WasteParameters:
    """Caller-provided production and removal parameters for P2-WP05."""

    production_rate_mol_s: float
    removal_rate_s: float

    def __post_init__(self) -> None:
        _require_nonnegative("production_rate_mol_s", self.production_rate_mol_s)
        _require_nonnegative("removal_rate_s", self.removal_rate_s)


@dataclass(frozen=True, slots=True)
class CellWasteProduction:
    """One cell's whole-cell waste source used in an accepted update."""

    cell_id: str
    production_rate_mol_s: float

    def __post_init__(self) -> None:
        if not self.cell_id.strip():
            raise WasteValidationError("cell_id must not be blank")
        _require_nonnegative("production_rate_mol_s", self.production_rate_mol_s)


@dataclass(frozen=True, slots=True)
class WasteMassBalance:
    """Discrete accounting for waste production, removal, and top transfer."""

    initial_waste_mol: float
    final_waste_mol: float
    produced_waste_mol: float
    removed_waste_mol: float
    boundary_input_waste_mol: float

    @property
    def residual_waste_mol(self) -> float:
        """Return ``final - initial - production + removal - boundary``."""
        return (
            self.final_waste_mol
            - self.initial_waste_mol
            - self.produced_waste_mol
            + self.removed_waste_mol
            - self.boundary_input_waste_mol
        )


@dataclass(frozen=True, slots=True)
class WasteStepResult:
    """Accepted waste field accounting and deterministic cell sources."""

    cell_production: tuple[CellWasteProduction, ...]
    mass_balance: WasteMassBalance


def maximum_stable_timestep_s(
    waste_field: SoluteField,
    removal_rate_s: float,
) -> float:
    """Return the positivity-preserving explicit diffusion-removal limit."""
    _require_nonnegative("removal_rate_s", removal_rate_s)
    diffusion_rate_s = waste_field.diffusivity_m2_s * (
        2.0 / waste_field.cell_width_m**2 + 3.0 / waste_field.cell_height_m**2
    )
    combined_rate_s = diffusion_rate_s + removal_rate_s
    return float("inf") if combined_rate_s == 0.0 else 1.0 / combined_rate_s


def waste_amount_mol(waste_field: SoluteField, depth_m: float) -> float:
    """Return total waste amount in the 2D domain's represented volume."""
    _require_positive("depth_m", depth_m)
    volume_m3 = waste_field.cell_width_m * waste_field.cell_height_m * depth_m
    return float(np.sum(waste_field.concentration_mol_m3)) * volume_m3


def top_boundary_input_rate_mol_s(waste_field: SoluteField, depth_m: float) -> float:
    """Return signed top-boundary waste transfer into the domain in ``mol s^-1``."""
    _require_positive("depth_m", depth_m)
    difference_mol_m3 = (
        waste_field.top_bulk_concentration_mol_m3
        - waste_field.concentration_mol_m3[0, :]
    )
    return float(
        np.sum(
            2.0
            * waste_field.diffusivity_m2_s
            * difference_mol_m3
            / waste_field.cell_height_m
            * waste_field.cell_width_m
            * depth_m
        )
    )


def advance_waste(
    *,
    cells: Sequence[Cell],
    waste_field: SoluteField,
    parameters: WasteParameters,
    time_step_s: float,
    depth_m: float,
    metabolic_activity_fractions: Mapping[str, float] | None = None,
) -> WasteStepResult:
    """Advance waste production, transport, and removal by one explicit step.

    Cell records are processed by identifier.  The field is mutated only after
    all inputs and the combined stability limit have been validated.
    """
    _require_positive("time_step_s", time_step_s)
    _require_positive("depth_m", depth_m)
    if not isinstance(parameters, WasteParameters):
        raise WasteValidationError("parameters must be a WasteParameters instance")
    stable_timestep_s = maximum_stable_timestep_s(
        waste_field, parameters.removal_rate_s
    )
    if time_step_s > stable_timestep_s:
        raise DiffusionStabilityError(
            "time_step_s exceeds the explicit waste diffusion-removal stability "
            f"limit of {stable_timestep_s:.17g} s"
        )
    ordered_cells = _validated_cells(cells)
    activities = _validated_activity_fractions(
        ordered_cells, metabolic_activity_fractions
    )
    volume_m3 = waste_field.cell_width_m * waste_field.cell_height_m * depth_m
    source_rate_mol_m3_s = np.zeros(waste_field.shape, dtype=np.float64)
    cell_production: list[CellWasteProduction] = []
    for cell in ordered_cells:
        rate_mol_s = parameters.production_rate_mol_s * activities[cell.cell_id]
        row, column = waste_field.cell_index(cell.x_m, cell.y_m)
        source_rate_mol_m3_s[row, column] += rate_mol_s / volume_m3
        cell_production.append(CellWasteProduction(cell.cell_id, rate_mol_s))

    initial_waste_mol = waste_amount_mol(waste_field, depth_m)
    produced_waste_mol = sum(
        record.production_rate_mol_s for record in cell_production
    ) * time_step_s
    removed_waste_mol = parameters.removal_rate_s * initial_waste_mol * time_step_s
    boundary_input_waste_mol = (
        top_boundary_input_rate_mol_s(waste_field, depth_m) * time_step_s
    )
    waste_field.advance(
        time_step_s,
        source_rate_mol_m3_s
        - parameters.removal_rate_s * waste_field.concentration_mol_m3,
    )
    return WasteStepResult(
        cell_production=tuple(cell_production),
        mass_balance=WasteMassBalance(
            initial_waste_mol=initial_waste_mol,
            final_waste_mol=waste_amount_mol(waste_field, depth_m),
            produced_waste_mol=produced_waste_mol,
            removed_waste_mol=removed_waste_mol,
            boundary_input_waste_mol=boundary_input_waste_mol,
        ),
    )


def _validated_cells(cells: Sequence[Cell]) -> tuple[Cell, ...]:
    validated = tuple(cells)
    if any(not isinstance(cell, Cell) for cell in validated):
        raise WasteValidationError("cells must contain only Cell instances")
    identifiers = [cell.cell_id for cell in validated]
    if len(identifiers) != len(set(identifiers)):
        raise WasteValidationError("cell IDs must be unique")
    return tuple(sorted(validated, key=lambda cell: cell.cell_id))


def _validated_activity_fractions(
    cells: tuple[Cell, ...],
    fractions: Mapping[str, float] | None,
) -> dict[str, float]:
    if fractions is None:
        return {cell.cell_id: 1.0 for cell in cells}
    if not isinstance(fractions, Mapping):
        raise WasteValidationError("metabolic_activity_fractions must be a mapping")
    identifiers = {cell.cell_id for cell in cells}
    if set(fractions) != identifiers:
        raise WasteValidationError(
            "metabolic_activity_fractions must contain exactly one value per cell"
        )
    validated: dict[str, float] = {}
    for cell_id, fraction in fractions.items():
        if not isinstance(cell_id, str) or not cell_id:
            raise WasteValidationError("metabolic_activity_fractions keys must be IDs")
        if not isfinite(fraction) or not 0.0 <= fraction <= 1.0:
            raise WasteValidationError(
                "metabolic activity fractions must be finite and within [0, 1]"
            )
        validated[cell_id] = fraction
    return validated


def _require_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise WasteValidationError(f"{name} must be finite and greater than zero")


def _require_nonnegative(name: str, value: float) -> None:
    if not isfinite(value) or value < 0.0:
        raise WasteValidationError(
            f"{name} must be finite and greater than or equal to zero"
        )
