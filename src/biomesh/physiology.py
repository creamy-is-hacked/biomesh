"""Deterministic physiological state transitions for P2-WP04.

Cells occupy one centralized state: active, slow, dormant, dead, or detached.
Living-state transitions use caller-provided carbon and oxygen thresholds and
continuous exposure delays.  Concentrations are sampled from the containing
control volume at the start of each interval and retained in immutable history.

The module contains no biological defaults.  Active metabolic activity is the
reference fraction one; dead and detached activity are zero by definition.
Slow and dormant activity fractions, all thresholds, all delays, and the
optional first-order dead-biomass recycling rate are explicit inputs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from math import exp, isclose, isfinite

from biomesh.cells import Cell
from biomesh.solutes import SoluteFields


class PhysiologyValidationError(ValueError):
    """Raised when physiological parameters or state are inconsistent."""


class PhysiologicalState(StrEnum):
    """The complete P2-WP04 physiological state inventory."""

    ACTIVE = "active"
    SLOW = "slow"
    DORMANT = "dormant"
    DEAD = "dead"
    DETACHED = "detached"


class DeadBiomassRule(StrEnum):
    """Explicit disposition of biomass after a cell enters the dead state."""

    PERSIST = "persist"
    RECYCLE = "recycle"


@dataclass(frozen=True, slots=True)
class PhysiologyParameters:
    """Caller-provided SI thresholds, delays, and activity controls.

    Thresholds are concentrations in ``mol m^-3`` and delays are seconds.
    For each solute, ``death <= dormancy <= slow`` is required.  A living cell
    is limited when either solute is at or below the applicable threshold and
    recovers only when both solutes are strictly above their slow thresholds.
    """

    carbon_slow_threshold_mol_m3: float
    oxygen_slow_threshold_mol_m3: float
    carbon_dormancy_threshold_mol_m3: float
    oxygen_dormancy_threshold_mol_m3: float
    carbon_death_threshold_mol_m3: float
    oxygen_death_threshold_mol_m3: float
    slow_transition_delay_s: float
    dormancy_transition_delay_s: float
    death_transition_delay_s: float
    recovery_transition_delay_s: float
    slow_metabolic_activity_fraction: float
    dormant_metabolic_activity_fraction: float
    dead_biomass_rule: DeadBiomassRule
    dead_biomass_recycling_rate_s: float | None

    def __post_init__(self) -> None:
        for name in (
            "carbon_slow_threshold_mol_m3",
            "oxygen_slow_threshold_mol_m3",
            "carbon_dormancy_threshold_mol_m3",
            "oxygen_dormancy_threshold_mol_m3",
            "carbon_death_threshold_mol_m3",
            "oxygen_death_threshold_mol_m3",
            "slow_transition_delay_s",
            "dormancy_transition_delay_s",
            "death_transition_delay_s",
            "recovery_transition_delay_s",
        ):
            _require_nonnegative(name, getattr(self, name))
        if not (
            self.carbon_death_threshold_mol_m3
            <= self.carbon_dormancy_threshold_mol_m3
            <= self.carbon_slow_threshold_mol_m3
        ):
            raise PhysiologyValidationError(
                "carbon thresholds must satisfy death <= dormancy <= slow"
            )
        if not (
            self.oxygen_death_threshold_mol_m3
            <= self.oxygen_dormancy_threshold_mol_m3
            <= self.oxygen_slow_threshold_mol_m3
        ):
            raise PhysiologyValidationError(
                "oxygen thresholds must satisfy death <= dormancy <= slow"
            )
        _require_fraction(
            "slow_metabolic_activity_fraction",
            self.slow_metabolic_activity_fraction,
        )
        _require_fraction(
            "dormant_metabolic_activity_fraction",
            self.dormant_metabolic_activity_fraction,
        )
        if not (
            self.dormant_metabolic_activity_fraction
            < self.slow_metabolic_activity_fraction
            < 1.0
        ):
            raise PhysiologyValidationError(
                "activity fractions must satisfy dormant < slow < active (1)"
            )
        if not isinstance(self.dead_biomass_rule, DeadBiomassRule):
            raise PhysiologyValidationError(
                "dead_biomass_rule must be a DeadBiomassRule"
            )
        if self.dead_biomass_rule is DeadBiomassRule.PERSIST:
            if self.dead_biomass_recycling_rate_s is not None:
                raise PhysiologyValidationError(
                    "persisting dead biomass requires no recycling rate"
                )
        elif self.dead_biomass_recycling_rate_s is None:
            raise PhysiologyValidationError(
                "recycling dead biomass requires dead_biomass_recycling_rate_s"
            )
        else:
            _require_positive(
                "dead_biomass_recycling_rate_s",
                self.dead_biomass_recycling_rate_s,
            )


@dataclass(frozen=True, slots=True)
class PhysiologyObservation:
    """One end-of-interval state and its sampled SI exposure history."""

    time_s: float
    carbon_concentration_mol_m3: float
    oxygen_concentration_mol_m3: float
    state: PhysiologicalState
    limited_duration_s: float
    dormant_duration_s: float
    lethal_duration_s: float
    recovery_duration_s: float

    def __post_init__(self) -> None:
        for name in (
            "time_s",
            "carbon_concentration_mol_m3",
            "oxygen_concentration_mol_m3",
            "limited_duration_s",
            "dormant_duration_s",
            "lethal_duration_s",
            "recovery_duration_s",
        ):
            _require_nonnegative(name, getattr(self, name))
        if not isinstance(self.state, PhysiologicalState):
            raise PhysiologyValidationError("state must be a PhysiologicalState")


@dataclass(frozen=True, slots=True)
class CellPhysiologyState:
    """Chronological physiological history and recycled mass for one cell."""

    cell_id: str
    history: tuple[PhysiologyObservation, ...]
    recycled_dead_biomass_kg: float = 0.0

    def __post_init__(self) -> None:
        if not self.cell_id.strip():
            raise PhysiologyValidationError("cell_id must not be blank")
        if not self.history:
            raise PhysiologyValidationError("physiology history must not be empty")
        if any(
            not isinstance(observation, PhysiologyObservation)
            for observation in self.history
        ):
            raise PhysiologyValidationError(
                "history must contain only PhysiologyObservation instances"
            )
        if any(
            current.time_s <= previous.time_s
            for previous, current in zip(self.history, self.history[1:])
        ):
            raise PhysiologyValidationError(
                "physiology observation times must increase strictly"
            )
        _require_nonnegative(
            "recycled_dead_biomass_kg", self.recycled_dead_biomass_kg
        )

    @property
    def current(self) -> PhysiologyObservation:
        """Return the latest accepted observation."""
        return self.history[-1]


@dataclass(frozen=True, slots=True)
class PhysiologicalStateTotals:
    """Population counts and retained dry biomass partitioned by state."""

    active_cell_count: int
    slow_cell_count: int
    dormant_cell_count: int
    dead_cell_count: int
    detached_cell_count: int
    active_biomass_kg: float
    slow_biomass_kg: float
    dormant_biomass_kg: float
    dead_biomass_kg: float
    detached_biomass_kg: float
    retained_biomass_kg: float
    recycled_dead_biomass_kg: float

    @property
    def cell_count(self) -> int:
        """Return the complete population-ledger count."""
        return (
            self.active_cell_count
            + self.slow_cell_count
            + self.dormant_cell_count
            + self.dead_cell_count
            + self.detached_cell_count
        )

    @property
    def partitioned_biomass_kg(self) -> float:
        """Return retained biomass summed across all five states."""
        return (
            self.active_biomass_kg
            + self.slow_biomass_kg
            + self.dormant_biomass_kg
            + self.dead_biomass_kg
            + self.detached_biomass_kg
        )


@dataclass(frozen=True, slots=True)
class PhysiologySnapshot:
    """Output-ready physiological state and reconciled population ledger."""

    time_s: float
    cell_states: tuple[CellPhysiologyState, ...]
    totals: PhysiologicalStateTotals


@dataclass(frozen=True, slots=True)
class PhysiologyStepResult:
    """Updated cell records, histories, and ledger after one state interval."""

    cells: tuple[Cell, ...]
    cell_states: tuple[CellPhysiologyState, ...]
    snapshot: PhysiologySnapshot
    recycled_dead_biomass_this_step_kg: float


def initialize_physiological_states(
    *,
    cells: Sequence[Cell],
    solute_fields: SoluteFields,
    time_s: float,
) -> tuple[CellPhysiologyState, ...]:
    """Initialize strict state histories from existing cell records."""
    _require_nonnegative("time_s", time_s)
    ordered_cells = _validated_cells(cells)
    states: list[CellPhysiologyState] = []
    for cell in ordered_cells:
        state = _parse_state(cell.state)
        carbon, oxygen = _sample_exposure(cell, solute_fields)
        states.append(
            CellPhysiologyState(
                cell_id=cell.cell_id,
                history=(
                    PhysiologyObservation(
                        time_s=time_s,
                        carbon_concentration_mol_m3=carbon,
                        oxygen_concentration_mol_m3=oxygen,
                        state=state,
                        limited_duration_s=0.0,
                        dormant_duration_s=0.0,
                        lethal_duration_s=0.0,
                        recovery_duration_s=0.0,
                    ),
                ),
            )
        )
    return tuple(states)


def metabolic_activity_fractions(
    *,
    cells: Sequence[Cell],
    cell_states: Sequence[CellPhysiologyState],
    parameters: PhysiologyParameters,
) -> dict[str, float]:
    """Return per-cell activity fractions for metabolism/EPS/competition."""
    ordered_cells = _validated_cells(cells)
    ordered_states = _validated_states(ordered_cells, cell_states, None)
    activity_by_state = {
        PhysiologicalState.ACTIVE: 1.0,
        PhysiologicalState.SLOW: parameters.slow_metabolic_activity_fraction,
        PhysiologicalState.DORMANT: (
            parameters.dormant_metabolic_activity_fraction
        ),
        PhysiologicalState.DEAD: 0.0,
        PhysiologicalState.DETACHED: 0.0,
    }
    return {
        cell.cell_id: activity_by_state[state.current.state]
        for cell, state in zip(ordered_cells, ordered_states, strict=True)
    }


def cells_retained_for_mechanics(cells: Sequence[Cell]) -> tuple[Cell, ...]:
    """Return non-detached cells; WP04 defines no detachment force or chance."""
    return tuple(
        cell
        for cell in _validated_cells(cells)
        if _parse_state(cell.state) is not PhysiologicalState.DETACHED
    )


def advance_physiological_states(
    *,
    cells: Sequence[Cell],
    solute_fields: SoluteFields,
    cell_states: Sequence[CellPhysiologyState],
    parameters: PhysiologyParameters,
    time_step_s: float,
    start_time_s: float,
    dry_biomass_per_unit_length_kg_m: float,
    detached_cell_ids: frozenset[str] = frozenset(),
) -> PhysiologyStepResult:
    """Advance explicit threshold/delay state and dead-biomass accounting.

    ``detached_cell_ids`` is an externally selected categorical transition. It
    introduces no WP05 shear, force, or probability law. Detached is terminal.
    Dead biomass either persists exactly or follows the configured first-order
    transfer into the cumulative recycled-biomass ledger. Recycled material is
    not silently returned to a solute field because no composition or yield is
    specified by P2-WP04.
    """
    _require_positive("time_step_s", time_step_s)
    _require_nonnegative("start_time_s", start_time_s)
    _require_positive(
        "dry_biomass_per_unit_length_kg_m",
        dry_biomass_per_unit_length_kg_m,
    )
    ordered_cells = _validated_cells(cells)
    ordered_states = _validated_states(ordered_cells, cell_states, start_time_s)
    if not isinstance(detached_cell_ids, frozenset):
        raise PhysiologyValidationError("detached_cell_ids must be a frozenset")
    unknown_detached = detached_cell_ids - {
        cell.cell_id for cell in ordered_cells
    }
    if unknown_detached:
        raise PhysiologyValidationError(
            "detached_cell_ids contains unknown cell IDs: "
            + ", ".join(sorted(unknown_detached))
        )

    end_time_s = start_time_s + time_step_s
    next_cells: list[Cell] = []
    next_states: list[CellPhysiologyState] = []
    recycled_this_step_kg = 0.0
    for cell, state_record in zip(ordered_cells, ordered_states, strict=True):
        current = state_record.current
        carbon, oxygen = _sample_exposure(cell, solute_fields)
        limited = (
            carbon <= parameters.carbon_slow_threshold_mol_m3
            or oxygen <= parameters.oxygen_slow_threshold_mol_m3
        )
        dormant = (
            carbon <= parameters.carbon_dormancy_threshold_mol_m3
            or oxygen <= parameters.oxygen_dormancy_threshold_mol_m3
        )
        lethal = (
            carbon <= parameters.carbon_death_threshold_mol_m3
            or oxygen <= parameters.oxygen_death_threshold_mol_m3
        )
        recovered = (
            carbon > parameters.carbon_slow_threshold_mol_m3
            and oxygen > parameters.oxygen_slow_threshold_mol_m3
        )
        limited_duration_s = _updated_duration(
            current.limited_duration_s, limited, time_step_s
        )
        dormant_duration_s = _updated_duration(
            current.dormant_duration_s, dormant, time_step_s
        )
        lethal_duration_s = _updated_duration(
            current.lethal_duration_s, lethal, time_step_s
        )
        recovery_duration_s = _updated_duration(
            current.recovery_duration_s, recovered, time_step_s
        )

        next_state = _transition_state(
            current=current.state,
            detach=cell.cell_id in detached_cell_ids,
            limited=limited,
            dormant=dormant,
            lethal=lethal,
            recovered=recovered,
            limited_duration_s=limited_duration_s,
            dormant_duration_s=dormant_duration_s,
            lethal_duration_s=lethal_duration_s,
            recovery_duration_s=recovery_duration_s,
            parameters=parameters,
        )
        updated_cell = cell
        recycled_total_kg = state_record.recycled_dead_biomass_kg
        if (
            current.state is PhysiologicalState.DEAD
            and next_state is PhysiologicalState.DEAD
            and parameters.dead_biomass_rule is DeadBiomassRule.RECYCLE
        ):
            recycling_rate_s = parameters.dead_biomass_recycling_rate_s
            if recycling_rate_s is None:  # Defensive against invalid construction.
                raise PhysiologyValidationError(
                    "recycling dead biomass requires a configured rate"
                )
            remaining_biomass_kg = cell.dry_biomass_kg * exp(
                -recycling_rate_s * time_step_s
            )
            recycled_kg = cell.dry_biomass_kg - remaining_biomass_kg
            updated_cell = cell.with_dry_biomass(
                remaining_biomass_kg,
                dry_biomass_per_unit_length_kg_m,
            )
            recycled_total_kg += recycled_kg
            recycled_this_step_kg += recycled_kg
        updated_cell = replace(updated_cell, state=next_state.value)
        observation = PhysiologyObservation(
            time_s=end_time_s,
            carbon_concentration_mol_m3=carbon,
            oxygen_concentration_mol_m3=oxygen,
            state=next_state,
            limited_duration_s=limited_duration_s,
            dormant_duration_s=dormant_duration_s,
            lethal_duration_s=lethal_duration_s,
            recovery_duration_s=recovery_duration_s,
        )
        next_cells.append(updated_cell)
        next_states.append(
            CellPhysiologyState(
                cell_id=cell.cell_id,
                history=(*state_record.history, observation),
                recycled_dead_biomass_kg=recycled_total_kg,
            )
        )

    accepted_cells = tuple(next_cells)
    accepted_states = tuple(next_states)
    snapshot = build_physiology_snapshot(
        time_s=end_time_s,
        cells=accepted_cells,
        cell_states=accepted_states,
    )
    return PhysiologyStepResult(
        cells=accepted_cells,
        cell_states=accepted_states,
        snapshot=snapshot,
        recycled_dead_biomass_this_step_kg=recycled_this_step_kg,
    )


def build_physiology_snapshot(
    *,
    time_s: float,
    cells: Sequence[Cell],
    cell_states: Sequence[CellPhysiologyState],
) -> PhysiologySnapshot:
    """Build and verify the state-partitioned population ledger."""
    _require_nonnegative("time_s", time_s)
    ordered_cells = _validated_cells(cells)
    ordered_states = _validated_states(ordered_cells, cell_states, time_s)
    cells_by_state = {
        state: tuple(
            cell
            for cell, state_record in zip(
                ordered_cells, ordered_states, strict=True
            )
            if state_record.current.state is state
        )
        for state in PhysiologicalState
    }
    biomasses = {
        state: sum(cell.dry_biomass_kg for cell in selected)
        for state, selected in cells_by_state.items()
    }
    retained_biomass_kg = sum(cell.dry_biomass_kg for cell in ordered_cells)
    totals = PhysiologicalStateTotals(
        active_cell_count=len(cells_by_state[PhysiologicalState.ACTIVE]),
        slow_cell_count=len(cells_by_state[PhysiologicalState.SLOW]),
        dormant_cell_count=len(cells_by_state[PhysiologicalState.DORMANT]),
        dead_cell_count=len(cells_by_state[PhysiologicalState.DEAD]),
        detached_cell_count=len(cells_by_state[PhysiologicalState.DETACHED]),
        active_biomass_kg=biomasses[PhysiologicalState.ACTIVE],
        slow_biomass_kg=biomasses[PhysiologicalState.SLOW],
        dormant_biomass_kg=biomasses[PhysiologicalState.DORMANT],
        dead_biomass_kg=biomasses[PhysiologicalState.DEAD],
        detached_biomass_kg=biomasses[PhysiologicalState.DETACHED],
        retained_biomass_kg=retained_biomass_kg,
        recycled_dead_biomass_kg=sum(
            state.recycled_dead_biomass_kg for state in ordered_states
        ),
    )
    if totals.cell_count != len(ordered_cells) or not isclose(
        totals.partitioned_biomass_kg,
        totals.retained_biomass_kg,
        rel_tol=1.0e-15,
        abs_tol=0.0,
    ):
        raise PhysiologyValidationError(
            "physiological state totals do not reconcile with population ledger"
        )
    return PhysiologySnapshot(
        time_s=time_s,
        cell_states=ordered_states,
        totals=totals,
    )


def _transition_state(
    *,
    current: PhysiologicalState,
    detach: bool,
    limited: bool,
    dormant: bool,
    lethal: bool,
    recovered: bool,
    limited_duration_s: float,
    dormant_duration_s: float,
    lethal_duration_s: float,
    recovery_duration_s: float,
    parameters: PhysiologyParameters,
) -> PhysiologicalState:
    if current is PhysiologicalState.DETACHED or detach:
        return PhysiologicalState.DETACHED
    if current is PhysiologicalState.DEAD:
        return PhysiologicalState.DEAD
    if lethal and lethal_duration_s >= parameters.death_transition_delay_s:
        return PhysiologicalState.DEAD
    if (
        current in {PhysiologicalState.SLOW, PhysiologicalState.DORMANT}
        and recovered
        and recovery_duration_s >= parameters.recovery_transition_delay_s
    ):
        return PhysiologicalState.ACTIVE
    if (
        current is PhysiologicalState.SLOW
        and dormant
        and dormant_duration_s >= parameters.dormancy_transition_delay_s
    ):
        return PhysiologicalState.DORMANT
    if (
        current is PhysiologicalState.ACTIVE
        and limited
        and limited_duration_s >= parameters.slow_transition_delay_s
    ):
        return PhysiologicalState.SLOW
    return current


def _validated_cells(cells: Sequence[Cell]) -> tuple[Cell, ...]:
    validated = tuple(cells)
    if any(not isinstance(cell, Cell) for cell in validated):
        raise PhysiologyValidationError("cells must contain only Cell instances")
    identifiers = [cell.cell_id for cell in validated]
    if len(identifiers) != len(set(identifiers)):
        raise PhysiologyValidationError("cell IDs must be unique")
    return tuple(sorted(validated, key=lambda cell: cell.cell_id))


def _validated_states(
    cells: tuple[Cell, ...],
    states: Sequence[CellPhysiologyState],
    expected_time_s: float | None,
) -> tuple[CellPhysiologyState, ...]:
    validated = tuple(states)
    if any(not isinstance(state, CellPhysiologyState) for state in validated):
        raise PhysiologyValidationError(
            "cell_states must contain only CellPhysiologyState instances"
        )
    state_by_id = {state.cell_id: state for state in validated}
    cell_ids = {cell.cell_id for cell in cells}
    if len(state_by_id) != len(validated) or set(state_by_id) != cell_ids:
        raise PhysiologyValidationError(
            "cell_states must contain exactly one state for every cell"
        )
    ordered = tuple(state_by_id[cell.cell_id] for cell in cells)
    for cell, state in zip(cells, ordered, strict=True):
        if _parse_state(cell.state) is not state.current.state:
            raise PhysiologyValidationError(
                f"physiology state for {cell.cell_id} must match cell.state"
            )
        if expected_time_s is not None and not isclose(
            state.current.time_s,
            expected_time_s,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise PhysiologyValidationError(
                f"current physiology time for {cell.cell_id} must match start_time_s"
            )
    return ordered


def _sample_exposure(cell: Cell, fields: SoluteFields) -> tuple[float, float]:
    if not isinstance(fields, SoluteFields):
        raise PhysiologyValidationError(
            "solute_fields must be a SoluteFields instance"
        )
    carbon_row, carbon_column = fields.carbon.cell_index(cell.x_m, cell.y_m)
    oxygen_row, oxygen_column = fields.oxygen.cell_index(cell.x_m, cell.y_m)
    return (
        float(fields.carbon.concentration_mol_m3[carbon_row, carbon_column]),
        float(fields.oxygen.concentration_mol_m3[oxygen_row, oxygen_column]),
    )


def _parse_state(value: str) -> PhysiologicalState:
    try:
        return PhysiologicalState(value)
    except ValueError as error:
        allowed = ", ".join(state.value for state in PhysiologicalState)
        raise PhysiologyValidationError(
            f"physiological state must be one of: {allowed}"
        ) from error


def _updated_duration(previous_s: float, condition: bool, time_step_s: float) -> float:
    return previous_s + time_step_s if condition else 0.0


def _require_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise PhysiologyValidationError(
            f"{name} must be finite and greater than zero"
        )


def _require_nonnegative(name: str, value: float) -> None:
    if not isfinite(value) or value < 0.0:
        raise PhysiologyValidationError(
            f"{name} must be finite and greater than or equal to zero"
        )


def _require_fraction(name: str, value: float) -> None:
    if not isfinite(value) or not 0.0 <= value <= 1.0:
        raise PhysiologyValidationError(f"{name} must be finite and within [0, 1]")
