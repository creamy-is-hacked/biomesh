"""Capsule-cell state and deterministic division for P1-WP03.

Cells are two-dimensional capsules: a centreline segment of ``length_m``
with semicircular end caps of ``radius_m``.  The dry-biomass-to-length mapping
is explicitly configured as ``dry_biomass_per_unit_length_kg_m``; no cell size
or biomass density is embedded in this module.  Position coordinates are in
metres, orientation is in radians, dry biomass is in kilograms, and age is in
seconds.

This module deliberately does not constrain cells to a domain or resolve
inter-cell overlaps.  Those responsibilities belong to P1-WP05.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import cos, isfinite, pi, sin

import numpy as np


class CellValidationError(ValueError):
    """Raised when cell state or a cell-model input is invalid."""


@dataclass(frozen=True, slots=True)
class CellModelParameters:
    """Caller-provided, SI-valued controls for P1-WP03 cell division.

    ``dry_biomass_per_unit_length_kg_m`` is an uncalibrated biological
    parameter.  The accepted value must be supplied by a parameter record
    with provenance before it is used in a scientific simulation.
    """

    dry_biomass_per_unit_length_kg_m: float
    division_length_m: float
    maximum_daughter_asymmetry_fraction: float

    def __post_init__(self) -> None:
        _require_positive(
            "dry_biomass_per_unit_length_kg_m",
            self.dry_biomass_per_unit_length_kg_m,
        )
        _require_positive("division_length_m", self.division_length_m)
        if (
            not isfinite(self.maximum_daughter_asymmetry_fraction)
            or not 0.0 <= self.maximum_daughter_asymmetry_fraction < 0.5
        ):
            raise CellValidationError(
                "maximum_daughter_asymmetry_fraction must be finite and within "
                "[0, 0.5)"
            )


@dataclass(frozen=True, slots=True)
class Cell:
    """One rod-shaped cell represented as a two-dimensional capsule.

    ``length_m`` is the centreline segment length, excluding the two
    semicircular caps.  The capsule's full tip-to-tip length is available as
    ``capsule_length_m``.  ``parent_id`` is retained after division so lineage
    can be reconstructed without an external registry.
    """

    cell_id: str
    x_m: float
    y_m: float
    orientation_rad: float
    length_m: float
    radius_m: float
    dry_biomass_kg: float
    age_s: float
    state: str
    strain: str
    parent_id: str | None = None

    def __post_init__(self) -> None:
        _require_nonblank("cell_id", self.cell_id)
        _require_finite("x_m", self.x_m)
        _require_finite("y_m", self.y_m)
        if not (
            isfinite(self.orientation_rad)
            and 0.0 <= self.orientation_rad < 2.0 * pi
        ):
            raise CellValidationError(
                "orientation_rad must be finite and within [0, 2*pi)"
            )
        _require_positive("length_m", self.length_m)
        _require_positive("radius_m", self.radius_m)
        _require_positive("dry_biomass_kg", self.dry_biomass_kg)
        _require_nonnegative("age_s", self.age_s)
        _require_nonblank("state", self.state)
        _require_nonblank("strain", self.strain)
        if self.parent_id is not None:
            _require_nonblank("parent_id", self.parent_id)

    @property
    def capsule_length_m(self) -> float:
        """Return the tip-to-tip capsule length in metres."""
        return self.length_m + 2.0 * self.radius_m

    @property
    def centreline_endpoints_m(
        self,
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        """Return centreline endpoint coordinates in metres."""
        half_length_m = self.length_m / 2.0
        x_offset_m = half_length_m * cos(self.orientation_rad)
        y_offset_m = half_length_m * sin(self.orientation_rad)
        return (
            (self.x_m - x_offset_m, self.y_m - y_offset_m),
            (self.x_m + x_offset_m, self.y_m + y_offset_m),
        )

    def with_dry_biomass(
        self,
        dry_biomass_kg: float,
        dry_biomass_per_unit_length_kg_m: float,
    ) -> Cell:
        """Return this cell with a length derived from its dry biomass.

        The caller must provide the calibrated dry-biomass-per-length mapping;
        accepting it here prevents an implicit biological constant.
        """
        _require_positive("dry_biomass_kg", dry_biomass_kg)
        _require_positive(
            "dry_biomass_per_unit_length_kg_m",
            dry_biomass_per_unit_length_kg_m,
        )
        return replace(
            self,
            dry_biomass_kg=dry_biomass_kg,
            length_m=dry_biomass_kg / dry_biomass_per_unit_length_kg_m,
        )


@dataclass(slots=True)
class CellIdGenerator:
    """Deterministically allocate unique cell IDs for a simulation lineage."""

    next_sequence: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.next_sequence, int) or self.next_sequence < 0:
            raise CellValidationError("next_sequence must be a nonnegative integer")

    def next_id(self) -> str:
        """Return the next deterministic identifier and advance the sequence."""
        cell_id = f"cell-{self.next_sequence:012d}"
        self.next_sequence += 1
        return cell_id


@dataclass(frozen=True, slots=True)
class DivisionResult:
    """The two daughter cells produced by one parent-cell division."""

    first_daughter: Cell
    second_daughter: Cell


def divide_if_ready(
    cell: Cell,
    parameters: CellModelParameters,
    random_generator: np.random.Generator,
    id_generator: CellIdGenerator,
) -> DivisionResult | None:
    """Divide a cell above its configured threshold, else return ``None``.

    Daughter dry-biomass fractions are ``0.5 ± a`` where ``a`` is sampled
    uniformly from the configured maximum asymmetry interval.  The second
    daughter receives the residual mass so the operation conserves the
    parent biomass up to floating-point precision.  Daughter centres are
    placed along the inherited axis with their capsule boundaries tangent.
    """
    if not isinstance(random_generator, np.random.Generator):
        raise CellValidationError("random_generator must be a numpy Generator")
    if cell.length_m <= parameters.division_length_m:
        return None

    asymmetry_fraction = random_generator.uniform(
        -parameters.maximum_daughter_asymmetry_fraction,
        parameters.maximum_daughter_asymmetry_fraction,
    )
    first_biomass_kg = cell.dry_biomass_kg * (0.5 + asymmetry_fraction)
    second_biomass_kg = cell.dry_biomass_kg - first_biomass_kg
    first_length_m = first_biomass_kg / parameters.dry_biomass_per_unit_length_kg_m
    second_length_m = (
        second_biomass_kg / parameters.dry_biomass_per_unit_length_kg_m
    )
    centre_distance_m = (
        (first_length_m + second_length_m) / 2.0 + 2.0 * cell.radius_m
    )
    x_offset_m = centre_distance_m * cos(cell.orientation_rad) / 2.0
    y_offset_m = centre_distance_m * sin(cell.orientation_rad) / 2.0

    first_daughter = Cell(
        cell_id=id_generator.next_id(),
        x_m=cell.x_m - x_offset_m,
        y_m=cell.y_m - y_offset_m,
        orientation_rad=cell.orientation_rad,
        length_m=first_length_m,
        radius_m=cell.radius_m,
        dry_biomass_kg=first_biomass_kg,
        age_s=0.0,
        state=cell.state,
        strain=cell.strain,
        parent_id=cell.cell_id,
    )
    second_daughter = Cell(
        cell_id=id_generator.next_id(),
        x_m=cell.x_m + x_offset_m,
        y_m=cell.y_m + y_offset_m,
        orientation_rad=cell.orientation_rad,
        length_m=second_length_m,
        radius_m=cell.radius_m,
        dry_biomass_kg=second_biomass_kg,
        age_s=0.0,
        state=cell.state,
        strain=cell.strain,
        parent_id=cell.cell_id,
    )
    return DivisionResult(first_daughter, second_daughter)


def _require_finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise CellValidationError(f"{name} must be finite")


def _require_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise CellValidationError(f"{name} must be finite and greater than zero")


def _require_nonnegative(name: str, value: float) -> None:
    if not isfinite(value) or value < 0.0:
        raise CellValidationError(
            f"{name} must be finite and greater than or equal to zero"
        )


def _require_nonblank(name: str, value: str) -> None:
    if not value.strip():
        raise CellValidationError(f"{name} must not be blank")
