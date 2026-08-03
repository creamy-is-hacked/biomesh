"""Deterministic P1-WP07 simulation orchestration.

The orchestrator owns the explicit Phase 1 update order:

1. sample metabolism and advance both solute fields atomically;
2. divide eligible cells using the run's seeded generator;
3. relax capsule mechanics and enforce attachment/boundaries;
4. account for global mass and serialize the accepted snapshot.

It composes existing component interfaces and introduces no new scientific
equations or Phase 2 behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from biomesh.cells import Cell, CellIdGenerator, CellModelParameters, divide_if_ready
from biomesh.mass_balance import GlobalMassAccountant
from biomesh.mechanics import (
    MechanicsParameters,
    attach_initial_cells,
    relax_cells,
)
from biomesh.metabolism import MetabolismParameters, advance_metabolism
from biomesh.outputs import (
    DivisionEvent,
    MassBalanceEntry,
    OutputPaths,
    SimulationOutputWriter,
)
from biomesh.solutes import SoluteField, SoluteFields


class SimulationValidationError(ValueError):
    """Raised when orchestration controls or state are incomplete."""


@dataclass(frozen=True, slots=True)
class SimulationParameters:
    """Explicit numerical and resolved biological inputs for one P1 run."""

    time_step_s: float
    step_count: int
    depth_m: float
    cell_model: CellModelParameters
    metabolism: MetabolismParameters
    mechanics: MechanicsParameters
    mass_balance_absolute_tolerance: float
    mass_balance_relative_tolerance: float
    next_cell_sequence: int

    def __post_init__(self) -> None:
        _require_positive("time_step_s", self.time_step_s)
        if (
            not isinstance(self.step_count, int)
            or isinstance(self.step_count, bool)
            or self.step_count <= 0
        ):
            raise SimulationValidationError("step_count must be a positive integer")
        _require_positive("depth_m", self.depth_m)
        _require_nonnegative(
            "mass_balance_absolute_tolerance",
            self.mass_balance_absolute_tolerance,
        )
        _require_nonnegative(
            "mass_balance_relative_tolerance",
            self.mass_balance_relative_tolerance,
        )
        if (
            not isinstance(self.next_cell_sequence, int)
            or isinstance(self.next_cell_sequence, bool)
            or self.next_cell_sequence < 0
        ):
            raise SimulationValidationError(
                "next_cell_sequence must be a nonnegative integer"
            )


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Final accepted state, metrics, and output paths for a complete run."""

    cells: tuple[Cell, ...]
    solute_fields: SoluteFields
    maximum_overlap_m: float
    mass_balance_entries: tuple[MassBalanceEntry, ...]
    output_paths: OutputPaths


def run_simulation(
    *,
    initial_cells: tuple[Cell, ...],
    initial_solute_fields: SoluteFields,
    parameters: SimulationParameters,
    seed: int,
    output_writer: SimulationOutputWriter,
) -> SimulationResult:
    """Execute the deterministic P1 component pipeline and write snapshots."""
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise SimulationValidationError("seed must be a nonnegative integer")
    if not isinstance(output_writer, SimulationOutputWriter):
        raise SimulationValidationError(
            "output_writer must be a SimulationOutputWriter instance"
        )
    if output_writer.metadata.seed != seed:
        raise SimulationValidationError(
            "simulation seed must match the seed recorded by output_writer"
        )
    cells = tuple(sorted(initial_cells, key=lambda cell: cell.cell_id))
    fields = _copy_solute_fields(initial_solute_fields)
    attachment = attach_initial_cells(cells, parameters.mechanics)
    initial_mechanics = relax_cells(
        attachment.cells,
        parameters.mechanics,
        attached_cell_ids=attachment.attached_cell_ids,
    )
    cells = initial_mechanics.cells
    attached_cell_ids = attachment.attached_cell_ids
    accountant = GlobalMassAccountant.from_state(
        cells=cells,
        solute_fields=fields,
        depth_m=parameters.depth_m,
        biomass_yield_on_carbon_kg_mol=(
            parameters.metabolism.biomass_yield_on_carbon_kg_mol
        ),
        biomass_yield_on_oxygen_kg_mol=(
            parameters.metabolism.biomass_yield_on_oxygen_kg_mol
        ),
    )
    random_generator = np.random.default_rng(seed)
    id_generator = CellIdGenerator(parameters.next_cell_sequence)
    balance_entries = accountant.entries(
        cells=cells,
        solute_fields=fields,
        absolute_tolerance=parameters.mass_balance_absolute_tolerance,
        relative_tolerance=parameters.mass_balance_relative_tolerance,
    )
    output_writer.write_snapshot(
        time_s=0.0,
        cells=cells,
        solute_fields=fields,
        division_events=(),
        mass_balance_entries=balance_entries,
    )
    maximum_overlap_m = initial_mechanics.maximum_overlap_m

    for step_index in range(1, parameters.step_count + 1):
        fields_before_step = _copy_solute_fields(fields)
        metabolism_result = advance_metabolism(
            cells,
            fields,
            parameters.time_step_s,
            parameters.depth_m,
            parameters.cell_model.dry_biomass_per_unit_length_kg_m,
            parameters.metabolism,
        )
        accountant.record_step(
            fields_before_step=fields_before_step,
            time_step_s=parameters.time_step_s,
            metabolism_result=metabolism_result,
        )
        cells, division_events, attached_cell_ids = _divide_cells(
            metabolism_result.cells,
            parameters.cell_model,
            random_generator,
            id_generator,
            attached_cell_ids,
        )
        mechanics_result = relax_cells(
            cells,
            parameters.mechanics,
            attached_cell_ids=attached_cell_ids,
        )
        cells = mechanics_result.cells
        maximum_overlap_m = max(
            maximum_overlap_m,
            mechanics_result.maximum_overlap_m,
        )
        balance_entries = accountant.entries(
            cells=cells,
            solute_fields=fields,
            absolute_tolerance=parameters.mass_balance_absolute_tolerance,
            relative_tolerance=parameters.mass_balance_relative_tolerance,
        )
        output_writer.write_snapshot(
            time_s=step_index * parameters.time_step_s,
            cells=cells,
            solute_fields=fields,
            division_events=division_events,
            mass_balance_entries=balance_entries,
        )

    return SimulationResult(
        cells=cells,
        solute_fields=fields,
        maximum_overlap_m=maximum_overlap_m,
        mass_balance_entries=balance_entries,
        output_paths=output_writer.finalize(),
    )


def _divide_cells(
    cells: tuple[Cell, ...],
    parameters: CellModelParameters,
    random_generator: np.random.Generator,
    id_generator: CellIdGenerator,
    attached_cell_ids: frozenset[str],
) -> tuple[tuple[Cell, ...], tuple[DivisionEvent, ...], frozenset[str]]:
    next_cells: list[Cell] = []
    events: list[DivisionEvent] = []
    next_attached_ids = set(attached_cell_ids)
    for cell in sorted(cells, key=lambda candidate: candidate.cell_id):
        division = divide_if_ready(
            cell,
            parameters,
            random_generator,
            id_generator,
        )
        if division is None:
            next_cells.append(cell)
            continue
        first = division.first_daughter
        second = division.second_daughter
        next_cells.extend((first, second))
        events.append(DivisionEvent(cell.cell_id, first.cell_id, second.cell_id))
        if cell.cell_id in next_attached_ids:
            next_attached_ids.remove(cell.cell_id)
            next_attached_ids.update((first.cell_id, second.cell_id))
    return (
        tuple(sorted(next_cells, key=lambda candidate: candidate.cell_id)),
        tuple(events),
        frozenset(next_attached_ids),
    )


def _copy_solute_fields(fields: SoluteFields) -> SoluteFields:
    return SoluteFields(
        carbon=_copy_solute_field(fields.carbon),
        oxygen=_copy_solute_field(fields.oxygen),
    )


def _copy_solute_field(field: SoluteField) -> SoluteField:
    return SoluteField(
        name=field.name,
        shape=field.shape,
        width_m=field.width_m,
        height_m=field.height_m,
        diffusivity_m2_s=field.diffusivity_m2_s,
        top_bulk_concentration_mol_m3=field.top_bulk_concentration_mol_m3,
        concentration_mol_m3=field.concentration_mol_m3,
    )


def _require_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise SimulationValidationError(
            f"{name} must be finite and greater than zero"
        )


def _require_nonnegative(name: str, value: float) -> None:
    if not isfinite(value) or value < 0.0:
        raise SimulationValidationError(
            f"{name} must be finite and greater than or equal to zero"
        )
