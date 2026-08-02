"""Finite-volume solute transport for P1 – Phase 1 – Core Model.

Concentrations are stored in ``mol m^-3`` on cell-centred 2D grids.  The
domain represents a vertical cross-section with a caller-supplied depth used
only when converting whole-cell exchange rates (``mol s^-1``) to volumetric
source terms (``mol m^-3 s^-1``).  No biological or transport values are
embedded in this module; diffusivities and bulk concentrations are required
at construction time.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
NUMERICAL_TOLERANCE = 1.0e-12


class SoluteValidationError(ValueError):
    """Raised when a solute-field input is invalid or numerically unsafe."""


class DiffusionStabilityError(SoluteValidationError):
    """Raised when an explicit diffusion step exceeds its stability limit."""


class NegativeConcentrationError(SoluteValidationError):
    """Raised when a proposed step produces a nonphysical concentration."""


@dataclass(frozen=True, slots=True)
class CellSoluteExchange:
    """Whole-cell solute exchange located in the 2D simulation plane.

    A positive rate is a source to the field and a negative rate is uptake.
    Carbon and oxygen rates are intentionally supplied independently because
    their kinetic coupling belongs to P1-WP04, not this transport package.
    """

    x_m: float
    y_m: float
    carbon_rate_mol_s: float
    oxygen_rate_mol_s: float


@dataclass(slots=True)
class SoluteField:
    """One explicitly stepped solute concentration field.

    ``shape`` is ``(vertical_cells, horizontal_cells)``.  The top boundary is
    held at ``top_bulk_concentration_mol_m3``; the bottom has zero normal
    diffusive flux; the left and right sides are periodic.
    """

    name: str
    shape: tuple[int, int]
    width_m: float
    height_m: float
    diffusivity_m2_s: float
    top_bulk_concentration_mol_m3: float
    concentration_mol_m3: FloatArray

    def __post_init__(self) -> None:
        rows, columns = self.shape
        if not self.name.strip():
            raise SoluteValidationError("field name must not be blank")
        if rows < 2 or columns < 2:
            raise SoluteValidationError("grid shape must contain at least 2 by 2 cells")
        self._validate_positive("width_m", self.width_m)
        self._validate_positive("height_m", self.height_m)
        self._validate_nonnegative("diffusivity_m2_s", self.diffusivity_m2_s)
        self._validate_nonnegative(
            "top_bulk_concentration_mol_m3", self.top_bulk_concentration_mol_m3
        )
        concentration = np.asarray(self.concentration_mol_m3, dtype=np.float64)
        if concentration.shape != self.shape:
            raise SoluteValidationError(
                "concentration_mol_m3 shape must match the configured grid shape"
            )
        if not np.all(np.isfinite(concentration)):
            raise SoluteValidationError(
                "concentration_mol_m3 must contain finite values"
            )
        if float(np.min(concentration)) < -NUMERICAL_TOLERANCE:
            raise NegativeConcentrationError(
                "concentration_mol_m3 cannot start below the numerical tolerance"
            )
        self.concentration_mol_m3 = concentration.copy()

    @property
    def cell_width_m(self) -> float:
        """Horizontal control-volume width in metres."""
        return self.width_m / self.shape[1]

    @property
    def cell_height_m(self) -> float:
        """Vertical control-volume height in metres."""
        return self.height_m / self.shape[0]

    @property
    def maximum_stable_timestep_s(self) -> float:
        """Return the explicit stability limit for the configured boundaries."""
        if self.diffusivity_m2_s == 0.0:
            return float("inf")
        boundary_weight = (
            2.0 / self.cell_width_m**2 + 3.0 / self.cell_height_m**2
        )
        return 1.0 / (self.diffusivity_m2_s * boundary_weight)

    def advance(
        self,
        time_step_s: float,
        source_rate_mol_m3_s: FloatArray | None = None,
    ) -> None:
        """Advance diffusion and a volumetric source term by one stable step.

        The method rejects an unstable step and leaves the field unchanged when
        the candidate update would become negative beyond numerical tolerance.
        """
        self._validate_positive("time_step_s", time_step_s)
        if time_step_s > self.maximum_stable_timestep_s:
            raise DiffusionStabilityError(
                "time_step_s exceeds the explicit diffusion stability limit "
                f"of {self.maximum_stable_timestep_s:.17g} s"
            )
        source_rate = self._validated_source_rate(source_rate_mol_m3_s)
        candidate = self.concentration_mol_m3 + time_step_s * (
            self.diffusivity_m2_s * self._laplacian_mol_m5() + source_rate
        )
        if float(np.min(candidate)) < -NUMERICAL_TOLERANCE:
            raise NegativeConcentrationError(
                "solute update would produce a concentration below the numerical "
                "tolerance"
            )
        self.concentration_mol_m3 = candidate

    def cell_index(self, x_m: float, y_m: float) -> tuple[int, int]:
        """Return the control-volume index for an in-domain cell position."""
        if not isfinite(x_m) or not isfinite(y_m):
            raise SoluteValidationError("cell coordinates must be finite")
        if not 0.0 <= x_m < self.width_m:
            raise SoluteValidationError("cell x_m must be within [0, width_m)")
        if not 0.0 <= y_m < self.height_m:
            raise SoluteValidationError("cell y_m must be within [0, height_m)")
        return int(y_m / self.cell_height_m), int(x_m / self.cell_width_m)

    def _laplacian_mol_m5(self) -> FloatArray:
        concentration = self.concentration_mol_m3
        dx_squared = self.cell_width_m**2
        dy_squared = self.cell_height_m**2
        horizontal = (
            np.roll(concentration, -1, axis=1)
            - 2.0 * concentration
            + np.roll(concentration, 1, axis=1)
        ) / dx_squared
        vertical = np.empty_like(concentration)
        vertical[1:-1, :] = (
            concentration[2:, :]
            - 2.0 * concentration[1:-1, :]
            + concentration[:-2, :]
        ) / dy_squared
        vertical[0, :] = (
            concentration[1, :]
            - 3.0 * concentration[0, :]
            + 2.0 * self.top_bulk_concentration_mol_m3
        ) / dy_squared
        vertical[-1, :] = (concentration[-2, :] - concentration[-1, :]) / dy_squared
        return horizontal + vertical

    def _validated_source_rate(self, source_rate: FloatArray | None) -> FloatArray:
        if source_rate is None:
            return np.zeros(self.shape, dtype=np.float64)
        source = np.asarray(source_rate, dtype=np.float64)
        if source.shape != self.shape:
            raise SoluteValidationError("source rate shape must match the field grid")
        if not np.all(np.isfinite(source)):
            raise SoluteValidationError("source rate must contain finite values")
        return source

    @staticmethod
    def _validate_positive(name: str, value: float) -> None:
        if not isfinite(value) or value <= 0.0:
            raise SoluteValidationError(
                f"{name} must be a finite value greater than zero"
            )

    @staticmethod
    def _validate_nonnegative(name: str, value: float) -> None:
        if not isfinite(value) or value < 0.0:
            raise SoluteValidationError(
                f"{name} must be a finite value greater than or equal to zero"
            )


@dataclass(slots=True)
class SoluteFields:
    """The carbon and oxygen fields required by P1-WP02.

    Both fields must share a grid because their cell-local exchange terms are
    mapped to the same control volumes.  Distinct diffusivities and bulk
    concentrations remain caller-configured scientific inputs.
    """

    carbon: SoluteField
    oxygen: SoluteField

    def __post_init__(self) -> None:
        if self.carbon.shape != self.oxygen.shape:
            raise SoluteValidationError(
                "carbon and oxygen grids must have the same shape"
            )
        if self.carbon.width_m != self.oxygen.width_m:
            raise SoluteValidationError(
                "carbon and oxygen grids must have the same width_m"
            )
        if self.carbon.height_m != self.oxygen.height_m:
            raise SoluteValidationError(
                "carbon and oxygen grids must have the same height_m"
            )

    def source_rates_from_cell_exchanges(
        self,
        exchanges: Sequence[CellSoluteExchange],
        depth_m: float,
    ) -> tuple[FloatArray, FloatArray]:
        """Map whole-cell rates into conservative volumetric source arrays.

        ``depth_m`` represents the out-of-plane depth of the 2D cross-section.
        For each solute, the sum of source density times control-volume size is
        exactly the sum of supplied cell rates.
        """
        SoluteField._validate_positive("depth_m", depth_m)
        carbon_source = np.zeros(self.carbon.shape, dtype=np.float64)
        oxygen_source = np.zeros(self.oxygen.shape, dtype=np.float64)
        volume_m3 = (
            self.carbon.cell_width_m * self.carbon.cell_height_m * depth_m
        )
        for exchange in exchanges:
            self._validate_exchange(exchange)
            row, column = self.carbon.cell_index(exchange.x_m, exchange.y_m)
            carbon_source[row, column] += exchange.carbon_rate_mol_s / volume_m3
            oxygen_source[row, column] += exchange.oxygen_rate_mol_s / volume_m3
        return carbon_source, oxygen_source

    def advance_with_cell_exchanges(
        self,
        time_step_s: float,
        exchanges: Sequence[CellSoluteExchange],
        depth_m: float,
    ) -> None:
        """Advance both fields using the supplied cell-local source/sink rates."""
        carbon_source, oxygen_source = self.source_rates_from_cell_exchanges(
            exchanges, depth_m
        )
        self.carbon.advance(time_step_s, carbon_source)
        self.oxygen.advance(time_step_s, oxygen_source)

    @staticmethod
    def _validate_exchange(exchange: CellSoluteExchange) -> None:
        for name, value in (
            ("carbon_rate_mol_s", exchange.carbon_rate_mol_s),
            ("oxygen_rate_mol_s", exchange.oxygen_rate_mol_s),
        ):
            if not isfinite(value):
                raise SoluteValidationError(f"{name} must be finite")
