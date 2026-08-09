"""Deterministic surface-parallel shear detachment for P2-WP05.

The simplified model accumulates uniform surface-parallel shear exposure in
``Pa s``.  A non-detached cell is selected for detachment when its cumulative
exposure reaches the caller-provided base threshold scaled by its attachment
state and the existing local EPS attachment-strength multiplier.  This is a
deterministic force/exposure abstraction, not a stochastic probability law or
a resolved fluid model.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from math import isfinite

from biomesh.cells import Cell
from biomesh.eps import EPSField, EPSParameters, local_mechanical_modifiers
from biomesh.physiology import PhysiologicalState


class ShearValidationError(ValueError):
    """Raised when shear-detachment inputs or histories are invalid."""


@dataclass(frozen=True, slots=True)
class ShearParameters:
    """Caller-provided mechanical controls for simplified shear detachment.

    ``attached_resistance_multiplier`` applies only to IDs explicitly supplied
    as surface-attached.  EPS resistance remains local and is computed from
    the already-configured P2-WP02 attachment-strength multiplier.
    """

    surface_parallel_shear_stress_pa: float
    detachment_exposure_threshold_pa_s: float
    attached_resistance_multiplier: float

    def __post_init__(self) -> None:
        _require_nonnegative(
            "surface_parallel_shear_stress_pa", self.surface_parallel_shear_stress_pa
        )
        _require_positive(
            "detachment_exposure_threshold_pa_s",
            self.detachment_exposure_threshold_pa_s,
        )
        _require_positive(
            "attached_resistance_multiplier", self.attached_resistance_multiplier
        )


@dataclass(frozen=True, slots=True)
class ShearObservation:
    """One chronological cumulative shear exposure record for a cell."""

    time_s: float
    cumulative_exposure_pa_s: float
    effective_detachment_threshold_pa_s: float
    attached: bool
    eps_attachment_strength_multiplier: float
    detached_by_shear: bool

    def __post_init__(self) -> None:
        _require_nonnegative("time_s", self.time_s)
        _require_nonnegative("cumulative_exposure_pa_s", self.cumulative_exposure_pa_s)
        _require_positive(
            "effective_detachment_threshold_pa_s",
            self.effective_detachment_threshold_pa_s,
        )
        _require_positive(
            "eps_attachment_strength_multiplier",
            self.eps_attachment_strength_multiplier,
        )
        if not isinstance(self.attached, bool) or not isinstance(
            self.detached_by_shear, bool
        ):
            raise ShearValidationError("shear flags must be bool values")


@dataclass(frozen=True, slots=True)
class CellShearState:
    """Immutable chronological exposure history for one cell."""

    cell_id: str
    history: tuple[ShearObservation, ...]

    def __post_init__(self) -> None:
        if not self.cell_id.strip():
            raise ShearValidationError("cell_id must not be blank")
        if not self.history or any(
            not isinstance(observation, ShearObservation)
            for observation in self.history
        ):
            raise ShearValidationError("shear history must contain observations")
        if any(
            current.time_s <= previous.time_s
            for previous, current in zip(self.history, self.history[1:], strict=False)
        ):
            raise ShearValidationError("shear observation times must increase strictly")

    @property
    def current(self) -> ShearObservation:
        """Return the latest accepted exposure record."""
        return self.history[-1]


@dataclass(frozen=True, slots=True)
class ShearSnapshot:
    """Output-ready deterministic shear exposure and detachment summary."""

    time_s: float
    surface_parallel_shear_stress_pa: float
    eligible_cell_count: int
    detached_cell_count: int
    detachment_rate_s: float
    cell_states: tuple[CellShearState, ...]

    def __post_init__(self) -> None:
        _require_nonnegative("time_s", self.time_s)
        _require_nonnegative(
            "surface_parallel_shear_stress_pa", self.surface_parallel_shear_stress_pa
        )
        if self.eligible_cell_count < 0 or self.detached_cell_count < 0:
            raise ShearValidationError("shear cell counts must be nonnegative")
        if self.detached_cell_count > self.eligible_cell_count:
            raise ShearValidationError("detached cells cannot exceed eligible cells")
        _require_nonnegative("detachment_rate_s", self.detachment_rate_s)


@dataclass(frozen=True, slots=True)
class ShearStepResult:
    """Selected detachment IDs, state histories, and output summary."""

    detached_cell_ids: frozenset[str]
    cell_states: tuple[CellShearState, ...]
    snapshot: ShearSnapshot


def initialize_shear_states(
    *,
    cells: Sequence[Cell],
    eps_field: EPSField,
    eps_parameters: EPSParameters,
    parameters: ShearParameters,
    attached_cell_ids: frozenset[str] = frozenset(),
    time_s: float,
) -> tuple[CellShearState, ...]:
    """Initialize zero-exposure histories using current attachment and EPS."""
    _require_nonnegative("time_s", time_s)
    ordered_cells = _validated_cells(cells)
    attached = _validated_attached_ids(ordered_cells, attached_cell_ids)
    _validate_eps_inputs(eps_field, eps_parameters)
    return tuple(
        CellShearState(
            cell_id=cell.cell_id,
            history=(
                _observation(
                    cell,
                    eps_field,
                    eps_parameters,
                    parameters,
                    cell.cell_id in attached,
                    0.0,
                    False,
                    time_s,
                ),
            ),
        )
        for cell in ordered_cells
    )


def advance_shear_detachment(
    *,
    cells: Sequence[Cell],
    eps_field: EPSField,
    eps_parameters: EPSParameters,
    parameters: ShearParameters,
    time_step_s: float,
    start_time_s: float,
    attached_cell_ids: frozenset[str] = frozenset(),
    cell_states: Sequence[CellShearState] | None = None,
) -> ShearStepResult:
    """Accumulate exposure and select terminal physiology transitions.

    The returned IDs are passed directly to
    :func:`biomesh.physiology.advance_physiological_states`; this component
    intentionally does not mutate cells or duplicate the population ledger.
    A zero configured stress never selects a shear-driven detachment, even if
    a prior history contains exposure near a threshold.
    """
    _require_positive("time_step_s", time_step_s)
    _require_nonnegative("start_time_s", start_time_s)
    ordered_cells = _validated_cells(cells)
    attached = _validated_attached_ids(ordered_cells, attached_cell_ids)
    _validate_eps_inputs(eps_field, eps_parameters)
    previous = (
        initialize_shear_states(
            cells=ordered_cells,
            eps_field=eps_field,
            eps_parameters=eps_parameters,
            parameters=parameters,
            attached_cell_ids=attached,
            time_s=start_time_s,
        )
        if cell_states is None
        else _validated_previous_states(ordered_cells, cell_states, start_time_s)
    )
    state_by_id = {state.cell_id: state for state in previous}
    exposure_increment_pa_s = parameters.surface_parallel_shear_stress_pa * time_step_s
    detached_ids: set[str] = set()
    next_states: list[CellShearState] = []
    eligible_count = 0
    for cell in ordered_cells:
        prior = state_by_id[cell.cell_id].current
        already_detached = cell.state == PhysiologicalState.DETACHED.value
        eligible = not already_detached
        if eligible:
            eligible_count += 1
        exposure_pa_s = prior.cumulative_exposure_pa_s + exposure_increment_pa_s
        observation = _observation(
            cell,
            eps_field,
            eps_parameters,
            parameters,
            cell.cell_id in attached,
            exposure_pa_s,
            False,
            start_time_s + time_step_s,
        )
        selected = (
            eligible
            and parameters.surface_parallel_shear_stress_pa > 0.0
            and exposure_pa_s >= observation.effective_detachment_threshold_pa_s
        )
        if selected:
            detached_ids.add(cell.cell_id)
            observation = _observation(
                cell,
                eps_field,
                eps_parameters,
                parameters,
                cell.cell_id in attached,
                exposure_pa_s,
                True,
                start_time_s + time_step_s,
            )
        next_states.append(
            CellShearState(
                cell.cell_id,
                (*state_by_id[cell.cell_id].history, observation),
            )
        )
    ordered_next_states = tuple(next_states)
    rate_s = len(detached_ids) / eligible_count / time_step_s if eligible_count else 0.0
    snapshot = ShearSnapshot(
        time_s=start_time_s + time_step_s,
        surface_parallel_shear_stress_pa=parameters.surface_parallel_shear_stress_pa,
        eligible_cell_count=eligible_count,
        detached_cell_count=len(detached_ids),
        detachment_rate_s=rate_s,
        cell_states=ordered_next_states,
    )
    return ShearStepResult(frozenset(detached_ids), ordered_next_states, snapshot)


def _observation(
    cell: Cell,
    eps_field: EPSField,
    eps_parameters: EPSParameters,
    parameters: ShearParameters,
    attached: bool,
    exposure_pa_s: float,
    detached_by_shear: bool,
    time_s: float,
) -> ShearObservation:
    eps_multiplier = local_mechanical_modifiers(
        eps_field=eps_field,
        x_m=cell.x_m,
        y_m=cell.y_m,
        parameters=eps_parameters,
    ).attachment_strength_multiplier
    attachment_multiplier = (
        parameters.attached_resistance_multiplier if attached else 1.0
    )
    return ShearObservation(
        time_s=time_s,
        cumulative_exposure_pa_s=exposure_pa_s,
        effective_detachment_threshold_pa_s=(
            parameters.detachment_exposure_threshold_pa_s
            * attachment_multiplier
            * eps_multiplier
        ),
        attached=attached,
        eps_attachment_strength_multiplier=eps_multiplier,
        detached_by_shear=detached_by_shear,
    )


def _validate_eps_inputs(eps_field: EPSField, eps_parameters: EPSParameters) -> None:
    if not isinstance(eps_field, EPSField):
        raise ShearValidationError("eps_field must be an EPSField instance")
    if not isinstance(eps_parameters, EPSParameters):
        raise ShearValidationError("eps_parameters must be an EPSParameters instance")


def _validated_cells(cells: Sequence[Cell]) -> tuple[Cell, ...]:
    validated = tuple(cells)
    if any(not isinstance(cell, Cell) for cell in validated):
        raise ShearValidationError("cells must contain only Cell instances")
    identifiers = [cell.cell_id for cell in validated]
    if len(identifiers) != len(set(identifiers)):
        raise ShearValidationError("cell IDs must be unique")
    return tuple(sorted(validated, key=lambda cell: cell.cell_id))


def _validated_attached_ids(
    cells: tuple[Cell, ...], attached_cell_ids: Collection[str]
) -> frozenset[str]:
    if not isinstance(attached_cell_ids, frozenset):
        raise ShearValidationError("attached_cell_ids must be a frozenset")
    unknown = attached_cell_ids - {cell.cell_id for cell in cells}
    if unknown:
        raise ShearValidationError(
            "attached_cell_ids contains unknown cell IDs: " + ", ".join(sorted(unknown))
        )
    return attached_cell_ids


def _validated_previous_states(
    cells: tuple[Cell, ...], states: Sequence[CellShearState], start_time_s: float
) -> tuple[CellShearState, ...]:
    validated = tuple(states)
    if any(not isinstance(state, CellShearState) for state in validated):
        raise ShearValidationError(
            "cell_states must contain only CellShearState instances"
        )
    by_id = {state.cell_id: state for state in validated}
    if len(by_id) != len(validated) or set(by_id) != {cell.cell_id for cell in cells}:
        raise ShearValidationError(
            "cell_states must contain exactly one state for every cell"
        )
    if any(state.current.time_s != start_time_s for state in validated):
        raise ShearValidationError(
            "current shear observation time must match start_time_s"
        )
    return tuple(by_id[cell.cell_id] for cell in cells)


def _require_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise ShearValidationError(f"{name} must be finite and greater than zero")


def _require_nonnegative(name: str, value: float) -> None:
    if not isfinite(value) or value < 0.0:
        raise ShearValidationError(
            f"{name} must be finite and greater than or equal to zero"
        )
