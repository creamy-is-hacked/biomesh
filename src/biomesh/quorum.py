"""Deterministic quorum-signal transport and cell-local sensing for P2-WP01.

The signal concentration ``A`` is stored in ``mol m^-3`` by the validated
Phase 1 :class:`~biomesh.solutes.SoluteField` finite-volume operator.  Each
cell contributes a caller-configured whole-cell production rate in ``mol s^-1``:

``q_A = q_basal + q_induced * A^n / (K_A^n + A^n)``.

First-order degradation is applied explicitly with diffusion and production.
The combined diffusion-degradation stability limit is checked before mutation.
No biological value has a module default.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import exp, isclose, isfinite, log

import numpy as np

from biomesh.cells import Cell
from biomesh.solutes import DiffusionStabilityError, SoluteField

TIME_MATCH_RELATIVE_TOLERANCE = 1.0e-12
TIME_MATCH_ABSOLUTE_TOLERANCE_S = 1.0e-15


class QuorumValidationError(ValueError):
    """Raised when quorum parameters, state, or update inputs are invalid."""


@dataclass(frozen=True, slots=True)
class QuorumSignalParameters:
    """Caller-provided biological parameters for the P2-WP01 equations."""

    degradation_rate_s: float
    basal_production_rate_mol_s: float
    induced_production_rate_mol_s: float
    activation_half_saturation_mol_m3: float
    hill_coefficient: float

    def __post_init__(self) -> None:
        _require_nonnegative("degradation_rate_s", self.degradation_rate_s)
        _require_nonnegative(
            "basal_production_rate_mol_s", self.basal_production_rate_mol_s
        )
        _require_nonnegative(
            "induced_production_rate_mol_s", self.induced_production_rate_mol_s
        )
        _require_positive(
            "activation_half_saturation_mol_m3",
            self.activation_half_saturation_mol_m3,
        )
        _require_positive("hill_coefficient", self.hill_coefficient)


@dataclass(frozen=True, slots=True)
class QuorumObservation:
    """One cell-local signal exposure and Hill activation observation."""

    time_s: float
    signal_concentration_mol_m3: float
    activation_fraction: float

    def __post_init__(self) -> None:
        _require_nonnegative("time_s", self.time_s)
        _require_nonnegative(
            "signal_concentration_mol_m3", self.signal_concentration_mol_m3
        )
        if (
            not isfinite(self.activation_fraction)
            or not 0.0 <= self.activation_fraction <= 1.0
        ):
            raise QuorumValidationError(
                "activation_fraction must be finite and within [0, 1]"
            )


@dataclass(frozen=True, slots=True)
class CellQuorumState:
    """Chronological signal-exposure and activation history for one cell."""

    cell_id: str
    history: tuple[QuorumObservation, ...]

    def __post_init__(self) -> None:
        if not self.cell_id.strip():
            raise QuorumValidationError("cell_id must not be blank")
        if not self.history:
            raise QuorumValidationError("quorum history must not be empty")
        if any(
            not isinstance(observation, QuorumObservation)
            for observation in self.history
        ):
            raise QuorumValidationError(
                "quorum history must contain only QuorumObservation instances"
            )
        if any(
            current.time_s <= previous.time_s
            for previous, current in zip(self.history, self.history[1:], strict=False)
        ):
            raise QuorumValidationError(
                "quorum observation times must increase strictly"
            )

    @property
    def current(self) -> QuorumObservation:
        """Return the most recent cell-local observation."""
        return self.history[-1]


@dataclass(frozen=True, slots=True)
class CellSignalProduction:
    """Whole-cell signal production used for one explicit update."""

    cell_id: str
    production_rate_mol_s: float

    def __post_init__(self) -> None:
        if not self.cell_id.strip():
            raise QuorumValidationError("cell_id must not be blank")
        _require_nonnegative("production_rate_mol_s", self.production_rate_mol_s)


@dataclass(frozen=True, slots=True)
class QuorumMassBalance:
    """Discrete signal accounting for production, degradation, and boundaries."""

    initial_signal_mol: float
    final_signal_mol: float
    produced_signal_mol: float
    degraded_signal_mol: float
    boundary_input_signal_mol: float

    @property
    def residual_signal_mol(self) -> float:
        """Return ``final - initial - production + degradation - boundary``."""
        return (
            self.final_signal_mol
            - self.initial_signal_mol
            - self.produced_signal_mol
            + self.degraded_signal_mol
            - self.boundary_input_signal_mol
        )


@dataclass(frozen=True, slots=True)
class QuorumStepResult:
    """Accepted cell-local state and accounting for one signal update."""

    cell_states: tuple[CellQuorumState, ...]
    cell_production: tuple[CellSignalProduction, ...]
    mass_balance: QuorumMassBalance


def hill_activation(
    signal_concentration_mol_m3: float,
    activation_half_saturation_mol_m3: float,
    hill_coefficient: float,
) -> float:
    """Evaluate ``A^n / (K_A^n + A^n)`` without overflow."""
    _require_nonnegative(
        "signal_concentration_mol_m3", signal_concentration_mol_m3
    )
    _require_positive(
        "activation_half_saturation_mol_m3",
        activation_half_saturation_mol_m3,
    )
    _require_positive("hill_coefficient", hill_coefficient)
    if signal_concentration_mol_m3 == 0.0:
        return 0.0
    log_ratio = hill_coefficient * (
        log(activation_half_saturation_mol_m3)
        - log(signal_concentration_mol_m3)
    )
    if log_ratio >= 0.0:
        inverse_ratio = exp(-log_ratio)
        return inverse_ratio / (1.0 + inverse_ratio)
    ratio = exp(log_ratio)
    return 1.0 / (1.0 + ratio)


def initialize_quorum_states(
    *,
    cells: Sequence[Cell],
    signal_field: SoluteField,
    parameters: QuorumSignalParameters,
    time_s: float,
) -> tuple[CellQuorumState, ...]:
    """Sample one deterministic initial observation for every cell."""
    _require_nonnegative("time_s", time_s)
    ordered_cells = _validated_cells(cells)
    return tuple(
        CellQuorumState(
            cell_id=cell.cell_id,
            history=(_observation(cell, signal_field, parameters, time_s),),
        )
        for cell in ordered_cells
    )


def maximum_stable_timestep_s(
    signal_field: SoluteField,
    degradation_rate_s: float,
) -> float:
    """Return the positivity-preserving explicit diffusion-decay limit."""
    _require_nonnegative("degradation_rate_s", degradation_rate_s)
    diffusion_rate_s = signal_field.diffusivity_m2_s * (
        2.0 / signal_field.cell_width_m**2
        + 3.0 / signal_field.cell_height_m**2
    )
    combined_rate_s = diffusion_rate_s + degradation_rate_s
    if combined_rate_s == 0.0:
        return float("inf")
    return 1.0 / combined_rate_s


def advance_quorum_signal(
    *,
    cells: Sequence[Cell],
    signal_field: SoluteField,
    parameters: QuorumSignalParameters,
    time_step_s: float,
    depth_m: float,
    start_time_s: float,
    cell_states: Sequence[CellQuorumState] | None = None,
) -> QuorumStepResult:
    """Advance production, diffusion, degradation, and cell-local state once.

    Feedback production samples the signal at each cell centre at the start of
    the explicit step.  The accepted field is sampled again at the end of the
    step and appended to each cell's immutable exposure/activation history.
    """
    _require_positive("time_step_s", time_step_s)
    _require_positive("depth_m", depth_m)
    _require_nonnegative("start_time_s", start_time_s)
    stable_timestep_s = maximum_stable_timestep_s(
        signal_field, parameters.degradation_rate_s
    )
    if time_step_s > stable_timestep_s:
        raise DiffusionStabilityError(
            "time_step_s exceeds the explicit quorum diffusion-degradation "
            f"stability limit of {stable_timestep_s:.17g} s"
        )

    ordered_cells = _validated_cells(cells)
    previous_states = (
        initialize_quorum_states(
            cells=ordered_cells,
            signal_field=signal_field,
            parameters=parameters,
            time_s=start_time_s,
        )
        if cell_states is None
        else _validated_previous_states(
            ordered_cells,
            signal_field,
            parameters,
            start_time_s,
            cell_states,
        )
    )
    state_by_id = {state.cell_id: state for state in previous_states}
    control_volume_m3 = (
        signal_field.cell_width_m * signal_field.cell_height_m * depth_m
    )
    source_rate_mol_m3_s = np.zeros(signal_field.shape, dtype=np.float64)
    cell_production: list[CellSignalProduction] = []
    for cell in ordered_cells:
        activation = state_by_id[cell.cell_id].current.activation_fraction
        production_rate_mol_s = (
            parameters.basal_production_rate_mol_s
            + parameters.induced_production_rate_mol_s * activation
        )
        row, column = signal_field.cell_index(cell.x_m, cell.y_m)
        source_rate_mol_m3_s[row, column] += (
            production_rate_mol_s / control_volume_m3
        )
        cell_production.append(
            CellSignalProduction(cell.cell_id, production_rate_mol_s)
        )

    initial_signal_mol = signal_amount_mol(signal_field, depth_m)
    produced_signal_mol = (
        sum(record.production_rate_mol_s for record in cell_production) * time_step_s
    )
    degraded_signal_mol = (
        parameters.degradation_rate_s * initial_signal_mol * time_step_s
    )
    boundary_input_signal_mol = (
        top_boundary_input_rate_mol_s(signal_field, depth_m) * time_step_s
    )
    degradation_rate_mol_m3_s = (
        parameters.degradation_rate_s * signal_field.concentration_mol_m3
    )
    signal_field.advance(
        time_step_s,
        source_rate_mol_m3_s - degradation_rate_mol_m3_s,
    )

    end_time_s = start_time_s + time_step_s
    next_states = tuple(
        CellQuorumState(
            cell_id=cell.cell_id,
            history=(
                *state_by_id[cell.cell_id].history,
                _observation(cell, signal_field, parameters, end_time_s),
            ),
        )
        for cell in ordered_cells
    )
    return QuorumStepResult(
        cell_states=next_states,
        cell_production=tuple(cell_production),
        mass_balance=QuorumMassBalance(
            initial_signal_mol=initial_signal_mol,
            final_signal_mol=signal_amount_mol(signal_field, depth_m),
            produced_signal_mol=produced_signal_mol,
            degraded_signal_mol=degraded_signal_mol,
            boundary_input_signal_mol=boundary_input_signal_mol,
        ),
    )


def signal_amount_mol(signal_field: SoluteField, depth_m: float) -> float:
    """Return the total signal amount represented by the 2D field."""
    _require_positive("depth_m", depth_m)
    control_volume_m3 = (
        signal_field.cell_width_m * signal_field.cell_height_m * depth_m
    )
    return float(np.sum(signal_field.concentration_mol_m3)) * control_volume_m3


def top_boundary_input_rate_mol_s(
    signal_field: SoluteField,
    depth_m: float,
) -> float:
    """Return signed signal input through the prescribed top boundary."""
    _require_positive("depth_m", depth_m)
    difference_mol_m3 = (
        signal_field.top_bulk_concentration_mol_m3
        - signal_field.concentration_mol_m3[0, :]
    )
    top_face_area_m2 = signal_field.cell_width_m * depth_m
    rate_mol_s = (
        2.0
        * signal_field.diffusivity_m2_s
        * difference_mol_m3
        / signal_field.cell_height_m
        * top_face_area_m2
    )
    return float(np.sum(rate_mol_s))


def _observation(
    cell: Cell,
    signal_field: SoluteField,
    parameters: QuorumSignalParameters,
    time_s: float,
) -> QuorumObservation:
    row, column = signal_field.cell_index(cell.x_m, cell.y_m)
    concentration_mol_m3 = float(signal_field.concentration_mol_m3[row, column])
    return QuorumObservation(
        time_s=time_s,
        signal_concentration_mol_m3=concentration_mol_m3,
        activation_fraction=hill_activation(
            concentration_mol_m3,
            parameters.activation_half_saturation_mol_m3,
            parameters.hill_coefficient,
        ),
    )


def _validated_cells(cells: Sequence[Cell]) -> tuple[Cell, ...]:
    validated = tuple(cells)
    if any(not isinstance(cell, Cell) for cell in validated):
        raise QuorumValidationError("cells must contain only Cell instances")
    identifiers = [cell.cell_id for cell in validated]
    if len(identifiers) != len(set(identifiers)):
        raise QuorumValidationError("cell IDs must be unique")
    return tuple(sorted(validated, key=lambda cell: cell.cell_id))


def _validated_previous_states(
    cells: tuple[Cell, ...],
    signal_field: SoluteField,
    parameters: QuorumSignalParameters,
    start_time_s: float,
    states: Sequence[CellQuorumState],
) -> tuple[CellQuorumState, ...]:
    validated = tuple(states)
    if any(not isinstance(state, CellQuorumState) for state in validated):
        raise QuorumValidationError(
            "cell_states must contain only CellQuorumState instances"
        )
    state_by_id = {state.cell_id: state for state in validated}
    cell_ids = {cell.cell_id for cell in cells}
    if len(state_by_id) != len(validated) or set(state_by_id) != cell_ids:
        raise QuorumValidationError(
            "cell_states must contain exactly one state for every current cell"
        )
    for cell in cells:
        expected = _observation(cell, signal_field, parameters, start_time_s)
        current = state_by_id[cell.cell_id].current
        if not isclose(
            current.time_s,
            start_time_s,
            rel_tol=TIME_MATCH_RELATIVE_TOLERANCE,
            abs_tol=TIME_MATCH_ABSOLUTE_TOLERANCE_S,
        ) or (
            current.signal_concentration_mol_m3
            != expected.signal_concentration_mol_m3
            or current.activation_fraction != expected.activation_fraction
        ):
            raise QuorumValidationError(
                f"current quorum state for {cell.cell_id} does not match the "
                "field, geometry, parameters, and start_time_s"
            )
    return tuple(state_by_id[cell.cell_id] for cell in cells)


def _require_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise QuorumValidationError(f"{name} must be finite and greater than zero")


def _require_nonnegative(name: str, value: float) -> None:
    if not isfinite(value) or value < 0.0:
        raise QuorumValidationError(
            f"{name} must be finite and greater than or equal to zero"
        )
