"""Deterministic producer/nonproducer resource competition for P2-WP03.

Producer and nonproducer cells are evaluated together by the existing
metabolism integrator, so they sample the same start-of-step carbon and oxygen
fields and their uptake is accumulated before either field advances. Only
producer cells allocate quorum-controlled growth to EPS. Every cell samples
the resulting local EPS field and therefore receives the same matrix-derived
mechanical modifiers at the same position, irrespective of strain role.

Competition metrics are derived without additional biological parameters.
Realized local fitness is the per-capita dry-biomass change rate in ``s^-1``.
Spatial segregation is the mean fraction of each cell's nearest neighbours
that have the same strain; all exactly equidistant nearest neighbours are
included, and horizontal distance follows the existing periodic domain.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Literal

from biomesh.cells import Cell
from biomesh.eps import (
    EPSField,
    EPSParameters,
    EPSStepResult,
    advance_eps_metabolism,
    local_mechanical_modifiers,
)
from biomesh.metabolism import MetabolismParameters
from biomesh.quorum import CellQuorumState
from biomesh.solutes import SoluteFields

StrainRole = Literal["producer", "nonproducer"]


class CompetitionValidationError(ValueError):
    """Raised when strain roles or competition state are invalid."""


@dataclass(frozen=True, slots=True)
class CompetitionStrains:
    """Explicit categorical producer and nonproducer strain identities.

    Strain identities are experiment configuration, not numeric biological
    constants. Both role inventories are required even when a particular
    controlled run is a monoculture.
    """

    producer_strains: frozenset[str]
    nonproducer_strains: frozenset[str]

    def __post_init__(self) -> None:
        _validate_strain_names("producer_strains", self.producer_strains)
        _validate_strain_names("nonproducer_strains", self.nonproducer_strains)
        overlap = self.producer_strains & self.nonproducer_strains
        if overlap:
            raise CompetitionValidationError(
                "producer and nonproducer strain identities must be disjoint: "
                + ", ".join(sorted(overlap))
            )

    def role_for(self, strain: str) -> StrainRole:
        """Return the configured role for one strain or fail explicitly."""
        if strain in self.producer_strains:
            return "producer"
        if strain in self.nonproducer_strains:
            return "nonproducer"
        raise CompetitionValidationError(
            f"cell strain {strain!r} has no configured competition role"
        )


@dataclass(frozen=True, slots=True)
class CellCompetitionMetric:
    """Lineage, local fitness, cost, and shared-matrix state for one cell."""

    cell_id: str
    parent_id: str | None
    strain: str
    role: StrainRole
    initial_dry_biomass_kg: float
    final_dry_biomass_kg: float
    realized_local_fitness_s: float
    eps_allocation_fraction: float
    local_eps_density_kg_m3: float
    cohesion_multiplier: float
    attachment_strength_multiplier: float


@dataclass(frozen=True, slots=True)
class StrainCompetitionMetric:
    """Population frequency, biomass frequency, and mean fitness by strain."""

    strain: str
    role: StrainRole
    cell_count: int
    cell_frequency: float
    dry_biomass_kg: float
    biomass_frequency: float
    mean_realized_local_fitness_s: float


@dataclass(frozen=True, slots=True)
class CompetitionSnapshot:
    """End-of-step competition state suitable for chronological output."""

    time_s: float
    producer_cell_frequency: float
    producer_biomass_frequency: float
    nearest_neighbor_segregation_fraction: float | None
    strain_metrics: tuple[StrainCompetitionMetric, ...]
    cell_metrics: tuple[CellCompetitionMetric, ...]


@dataclass(frozen=True, slots=True)
class CompetitionStepResult:
    """Coupled EPS/metabolism result and derived competition snapshot."""

    eps: EPSStepResult
    snapshot: CompetitionSnapshot

    @property
    def cells(self) -> tuple[Cell, ...]:
        """Return cells after shared-resource growth and producer EPS cost."""
        return self.eps.cells


def advance_competition(
    *,
    cells: Sequence[Cell],
    strain_roles: CompetitionStrains,
    solute_fields: SoluteFields,
    eps_field: EPSField,
    quorum_states: Sequence[CellQuorumState],
    eps_parameters: EPSParameters,
    metabolism_parameters: MetabolismParameters,
    time_step_s: float,
    start_time_s: float,
    dry_biomass_per_unit_length_kg_m: float,
    metabolic_activity_fractions: Mapping[str, float] | None = None,
) -> CompetitionStepResult:
    """Advance one mixed competition step and report deterministic metrics."""
    if not isinstance(strain_roles, CompetitionStrains):
        raise CompetitionValidationError(
            "strain_roles must be a CompetitionStrains instance"
        )
    if not cells:
        raise CompetitionValidationError("competition requires at least one cell")
    if any(not isinstance(cell, Cell) for cell in cells):
        raise CompetitionValidationError("cells must contain only Cell instances")
    cell_ids = [cell.cell_id for cell in cells]
    if len(cell_ids) != len(set(cell_ids)):
        raise CompetitionValidationError("cell IDs must be unique")
    roles_by_id = {
        cell.cell_id: strain_roles.role_for(cell.strain) for cell in cells
    }
    producing_cell_ids = frozenset(
        cell_id for cell_id, role in roles_by_id.items() if role == "producer"
    )
    initial_by_id = {cell.cell_id: cell for cell in cells}

    eps_result = advance_eps_metabolism(
        cells=cells,
        solute_fields=solute_fields,
        eps_field=eps_field,
        quorum_states=quorum_states,
        eps_parameters=eps_parameters,
        metabolism_parameters=metabolism_parameters,
        time_step_s=time_step_s,
        start_time_s=start_time_s,
        dry_biomass_per_unit_length_kg_m=dry_biomass_per_unit_length_kg_m,
        producing_cell_ids=producing_cell_ids,
        metabolic_activity_fractions=metabolic_activity_fractions,
    )
    production_by_id = {
        production.cell_id: production for production in eps_result.cell_production
    }
    metabolism_by_id = dict(
        zip(
            (cell.cell_id for cell in eps_result.cells),
            eps_result.metabolism.cell_results,
            strict=True,
        )
    )
    cell_metrics: list[CellCompetitionMetric] = []
    for cell in eps_result.cells:
        initial_cell = initial_by_id[cell.cell_id]
        metabolism = metabolism_by_id[cell.cell_id]
        production = production_by_id[cell.cell_id]
        modifiers = local_mechanical_modifiers(
            eps_field=eps_field,
            x_m=cell.x_m,
            y_m=cell.y_m,
            parameters=eps_parameters,
        )
        local_fitness_s = (
            (cell.dry_biomass_kg - initial_cell.dry_biomass_kg)
            / initial_cell.dry_biomass_kg
            / time_step_s
        )
        if not isfinite(local_fitness_s):
            raise CompetitionValidationError("realized local fitness is non-finite")
        if metabolism.final_dry_biomass_kg != cell.dry_biomass_kg:
            raise CompetitionValidationError(
                "metabolism and competition cell biomass are inconsistent"
            )
        cell_metrics.append(
            CellCompetitionMetric(
                cell_id=cell.cell_id,
                parent_id=cell.parent_id,
                strain=cell.strain,
                role=roles_by_id[cell.cell_id],
                initial_dry_biomass_kg=initial_cell.dry_biomass_kg,
                final_dry_biomass_kg=cell.dry_biomass_kg,
                realized_local_fitness_s=local_fitness_s,
                eps_allocation_fraction=production.allocation_fraction,
                local_eps_density_kg_m3=modifiers.eps_density_kg_m3,
                cohesion_multiplier=modifiers.cohesion_multiplier,
                attachment_strength_multiplier=(
                    modifiers.attachment_strength_multiplier
                ),
            )
        )

    ordered_metrics = tuple(sorted(cell_metrics, key=lambda metric: metric.cell_id))
    total_biomass_kg = sum(metric.final_dry_biomass_kg for metric in ordered_metrics)
    strain_metrics = _strain_metrics(ordered_metrics, total_biomass_kg)
    producer_count = sum(metric.role == "producer" for metric in ordered_metrics)
    producer_biomass_kg = sum(
        metric.final_dry_biomass_kg
        for metric in ordered_metrics
        if metric.role == "producer"
    )
    snapshot = CompetitionSnapshot(
        time_s=start_time_s + time_step_s,
        producer_cell_frequency=producer_count / len(ordered_metrics),
        producer_biomass_frequency=producer_biomass_kg / total_biomass_kg,
        nearest_neighbor_segregation_fraction=_nearest_neighbor_segregation(
            eps_result.cells, eps_field.width_m
        ),
        strain_metrics=strain_metrics,
        cell_metrics=ordered_metrics,
    )
    return CompetitionStepResult(eps=eps_result, snapshot=snapshot)


def _strain_metrics(
    cell_metrics: tuple[CellCompetitionMetric, ...],
    total_biomass_kg: float,
) -> tuple[StrainCompetitionMetric, ...]:
    metrics: list[StrainCompetitionMetric] = []
    strains = sorted({metric.strain for metric in cell_metrics})
    for strain in strains:
        selected = tuple(metric for metric in cell_metrics if metric.strain == strain)
        biomass_kg = sum(metric.final_dry_biomass_kg for metric in selected)
        metrics.append(
            StrainCompetitionMetric(
                strain=strain,
                role=selected[0].role,
                cell_count=len(selected),
                cell_frequency=len(selected) / len(cell_metrics),
                dry_biomass_kg=biomass_kg,
                biomass_frequency=biomass_kg / total_biomass_kg,
                mean_realized_local_fitness_s=(
                    sum(metric.realized_local_fitness_s for metric in selected)
                    / len(selected)
                ),
            )
        )
    return tuple(metrics)


def _nearest_neighbor_segregation(
    cells: tuple[Cell, ...], width_m: float
) -> float | None:
    if len(cells) < 2:
        return None
    same_strain_fractions: list[float] = []
    for cell in cells:
        distances: list[tuple[float, Cell]] = []
        for other in cells:
            if other.cell_id == cell.cell_id:
                continue
            x_distance_m = abs(cell.x_m - other.x_m)
            periodic_x_distance_m = min(x_distance_m, width_m - x_distance_m)
            y_distance_m = cell.y_m - other.y_m
            distances.append(
                (
                    periodic_x_distance_m * periodic_x_distance_m
                    + y_distance_m * y_distance_m,
                    other,
                )
            )
        minimum_distance_squared_m2 = min(distance for distance, _ in distances)
        nearest = tuple(
            other
            for distance, other in distances
            if distance == minimum_distance_squared_m2
        )
        same_strain_fractions.append(
            sum(other.strain == cell.strain for other in nearest) / len(nearest)
        )
    return sum(same_strain_fractions) / len(same_strain_fractions)


def _validate_strain_names(name: str, strains: frozenset[str]) -> None:
    if not isinstance(strains, frozenset) or not strains:
        raise CompetitionValidationError(f"{name} must be a non-empty frozenset")
    if any(not isinstance(strain, str) or not strain.strip() for strain in strains):
        raise CompetitionValidationError(
            f"{name} must contain only non-blank strain names"
        )
