"""Deterministic serialization of existing simulation state.

This module has no simulation update logic.  It writes the caller-owned
``Cell`` and ``SoluteFields`` state after a step, preserving SI quantities in
column and array names. P2-WP01 optionally adds a quorum signal field and
cell-local exposure/activation records. P2-WP02 optionally adds EPS density
and total-mass records. P2-WP03 optionally adds competition frequency,
segregation, lineage, and local-fitness records without changing the P1
artifact path. P2-WP04 optionally adds reconciled physiological state counts
and biomass totals. P2-WP05 optionally adds a waste concentration field and a
simplified shear-detachment summary. Biofilm height is the greatest capsule-top
elevation above
the solid bottom; roughness is the population standard deviation of capsule-top
elevations. Both are geometric summaries, not biological parameters.
Mass-balance entries are supplied by the simulation because this layer must not
infer unrecorded sources, sinks, or boundary fluxes.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from math import isfinite, sqrt
from pathlib import Path
from typing import Any, Protocol, cast
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from biomesh.cells import Cell
from biomesh.competition import CompetitionSnapshot
from biomesh.eps import EPSField
from biomesh.physiology import PhysiologySnapshot, build_physiology_snapshot
from biomesh.quorum import CellQuorumState
from biomesh.shear import ShearSnapshot
from biomesh.solutes import SoluteField, SoluteFields


class OutputValidationError(ValueError):
    """Raised when an output record is incomplete, ambiguous, or unsafe."""


class _ArrayWriter(Protocol):
    def __call__(
        self,
        file: BytesIO,
        array: np.ndarray[Any, np.dtype[Any]],
        *,
        allow_pickle: bool,
    ) -> None: ...


_write_array = cast(_ArrayWriter, np.lib.format.write_array)


@dataclass(frozen=True, slots=True)
class RunMetadata:
    """Required, reproducible provenance for one simulation run.

    ``parameters`` must be a JSON-serializable mapping containing the exact
    parameter state used by the caller.  It is canonicalized at construction
    so later mutation of a caller's mapping cannot alter run provenance.
    """

    seed: int
    parameters: Mapping[str, object]
    package_version: str
    commit_hash: str
    dependency_versions: Mapping[str, str]
    parameter_file: str
    parameter_file_sha256: str
    platform: str
    python_version: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.seed, int)
            or isinstance(self.seed, bool)
            or self.seed < 0
        ):
            raise OutputValidationError("seed must be a nonnegative integer")
        _require_nonblank("package_version", self.package_version)
        _require_nonblank("commit_hash", self.commit_hash)
        _require_nonblank("parameter_file", self.parameter_file)
        _require_sha256("parameter_file_sha256", self.parameter_file_sha256)
        _require_nonblank("platform", self.platform)
        _require_nonblank("python_version", self.python_version)
        if (
            not isinstance(self.dependency_versions, Mapping)
            or not self.dependency_versions
        ):
            raise OutputValidationError(
                "dependency_versions must be a non-empty mapping"
            )
        if any(
            not isinstance(name, str)
            or not name
            or not isinstance(version, str)
            or not version
            for name, version in self.dependency_versions.items()
        ):
            raise OutputValidationError(
                "dependency names and versions must be non-empty strings"
            )
        if not isinstance(self.parameters, Mapping) or not self.parameters:
            raise OutputValidationError("parameters must be a non-empty mapping")
        if any(not isinstance(key, str) or not key for key in self.parameters):
            raise OutputValidationError("parameter names must be non-empty strings")
        try:
            serialized = json.dumps(
                self.parameters,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        except (TypeError, ValueError) as error:
            raise OutputValidationError(
                "parameters must be JSON serializable finite values"
            ) from error
        canonical = json.loads(serialized)
        if not isinstance(canonical, dict):  # Defensive; a mapping encodes as object.
            raise OutputValidationError("parameters must serialize as a JSON object")
        object.__setattr__(self, "parameters", canonical)
        object.__setattr__(
            self,
            "dependency_versions",
            dict(sorted(self.dependency_versions.items())),
        )

    def as_dict(self) -> dict[str, object]:
        """Return metadata in the stable structure written to JSON."""
        return {
            "commit_hash": self.commit_hash,
            "dependency_versions": self.dependency_versions,
            "package_version": self.package_version,
            "parameter_file": self.parameter_file,
            "parameter_file_sha256": self.parameter_file_sha256,
            "parameters": self.parameters,
            "platform": self.platform,
            "python_version": self.python_version,
            "seed": self.seed,
        }


@dataclass(frozen=True, slots=True)
class DivisionEvent:
    """One division event identified by its parent and two daughter IDs."""

    parent_cell_id: str
    first_daughter_cell_id: str
    second_daughter_cell_id: str

    def __post_init__(self) -> None:
        _require_nonblank("parent_cell_id", self.parent_cell_id)
        _require_nonblank("first_daughter_cell_id", self.first_daughter_cell_id)
        _require_nonblank("second_daughter_cell_id", self.second_daughter_cell_id)
        if self.first_daughter_cell_id == self.second_daughter_cell_id:
            raise OutputValidationError("division daughter cell IDs must differ")


@dataclass(frozen=True, slots=True)
class MassBalanceEntry:
    """One unit-aware balance term supplied by the simulation layer.

    ``net_input_amount`` is the signed total of every source, sink, and
    boundary transfer that the caller includes for the named quantity.  The
    residual is calculated as ``final - initial - net_input`` in ``unit``.
    """

    quantity: str
    unit: str
    initial_amount: float
    final_amount: float
    net_input_amount: float
    absolute_tolerance: float
    relative_tolerance: float

    def __post_init__(self) -> None:
        _require_nonblank("quantity", self.quantity)
        _require_nonblank("unit", self.unit)
        _require_finite("initial_amount", self.initial_amount)
        _require_finite("final_amount", self.final_amount)
        _require_finite("net_input_amount", self.net_input_amount)
        _require_nonnegative("absolute_tolerance", self.absolute_tolerance)
        _require_nonnegative("relative_tolerance", self.relative_tolerance)

    @property
    def residual_amount(self) -> float:
        """Return the signed balance residual in the entry's declared unit."""
        return self.final_amount - self.initial_amount - self.net_input_amount

    @property
    def scale_amount(self) -> float:
        """Return the magnitude used by the configured relative-error gate."""
        return max(
            abs(self.initial_amount),
            abs(self.final_amount),
            abs(self.net_input_amount),
        )

    @property
    def relative_error(self) -> float:
        """Return residual magnitude relative to the largest balance term."""
        if self.scale_amount == 0.0:
            return 0.0 if self.residual_amount == 0.0 else float("inf")
        return abs(self.residual_amount) / self.scale_amount

    @property
    def allowed_residual_amount(self) -> float:
        """Return the combined absolute-plus-relative residual allowance."""
        return self.absolute_tolerance + self.relative_tolerance * self.scale_amount


@dataclass(frozen=True, slots=True)
class OutputPaths:
    """The complete, finalized artifact set for one run."""

    run_directory: Path
    metadata_file: Path
    cells_table: Path
    summary_table: Path
    division_events_table: Path
    mass_balance_table: Path
    field_files: tuple[Path, ...]
    quorum_history_table: Path | None = None
    eps_summary_table: Path | None = None
    competition_summary_table: Path | None = None
    competition_strain_table: Path | None = None
    competition_cell_table: Path | None = None
    physiology_summary_table: Path | None = None
    shear_summary_table: Path | None = None


class SimulationOutputWriter:
    """Write deterministic model artifacts without retaining model state.

    Each :meth:`write_snapshot` call serializes field arrays immediately and
    retains only table rows needed to make compact Parquet tables at
    :meth:`finalize`.  Cell, field, and event records are canonically ordered
    before serialization.  A writer owns a new run directory and never
    overwrites an existing result.
    """

    def __init__(self, run_directory: Path, metadata: RunMetadata) -> None:
        if not isinstance(metadata, RunMetadata):
            raise OutputValidationError("metadata must be a RunMetadata instance")
        self._published_run_directory = Path(run_directory)
        if (
            self._published_run_directory.exists()
            or self._published_run_directory.is_symlink()
        ):
            raise OutputValidationError(
                "output run directory already exists: "
                f"{self._published_run_directory}; "
                "choose a new path with --output"
            )
        self._published_run_directory.parent.mkdir(parents=True, exist_ok=True)
        self._run_directory = Path(
            tempfile.mkdtemp(
                prefix=f".{self._published_run_directory.name}.",
                dir=self._published_run_directory.parent,
            )
        )
        self._metadata = metadata
        try:
            self._metadata_file = self._run_directory / "run_metadata.json"
            self._write_metadata()
            self._fields_directory = self._run_directory / "fields"
            self._fields_directory.mkdir()
        except Exception:
            shutil.rmtree(self._run_directory, ignore_errors=True)
            raise
        self._cell_rows: list[dict[str, object]] = []
        self._summary_rows: list[dict[str, object]] = []
        self._division_event_rows: list[dict[str, object]] = []
        self._mass_balance_rows: list[dict[str, object]] = []
        self._quorum_history_rows: list[dict[str, object]] = []
        self._eps_summary_rows: list[dict[str, object]] = []
        self._competition_summary_rows: list[dict[str, object]] = []
        self._competition_strain_rows: list[dict[str, object]] = []
        self._competition_cell_rows: list[dict[str, object]] = []
        self._physiology_summary_rows: list[dict[str, object]] = []
        self._shear_summary_rows: list[dict[str, object]] = []
        self._quorum_output_enabled: bool | None = None
        self._eps_output_enabled: bool | None = None
        self._competition_output_enabled: bool | None = None
        self._physiology_output_enabled: bool | None = None
        self._waste_output_enabled: bool | None = None
        self._shear_output_enabled: bool | None = None
        self._field_files: list[Path] = []
        self._last_time_s: float | None = None
        self._finalized = False

    @property
    def metadata(self) -> RunMetadata:
        """Return the immutable run-level provenance owned by this writer."""
        return self._metadata

    def write_auxiliary_file(self, name: str, contents: bytes) -> Path:
        """Stage one caller-owned immutable file for atomic run publication."""
        if self._finalized:
            raise OutputValidationError("writer has already been finalized")
        if (
            not isinstance(name, str)
            or not name
            or Path(name).name != name
            or name in {".", ".."}
        ):
            raise OutputValidationError(
                "auxiliary file name must be one path component"
            )
        if not isinstance(contents, bytes):
            raise OutputValidationError("auxiliary file contents must be bytes")
        target = self._run_directory / name

        def write(path: Path) -> None:
            path.write_bytes(contents)

        _atomic_file(target, write)
        return target

    def write_snapshot(
        self,
        *,
        time_s: float,
        cells: Sequence[Cell],
        solute_fields: SoluteFields,
        division_events: Sequence[DivisionEvent],
        mass_balance_entries: Sequence[MassBalanceEntry],
        quorum_signal_field: SoluteField | None = None,
        quorum_states: Sequence[CellQuorumState] | None = None,
        eps_field: EPSField | None = None,
        competition_snapshot: CompetitionSnapshot | None = None,
        physiology_snapshot: PhysiologySnapshot | None = None,
        waste_field: SoluteField | None = None,
        shear_snapshot: ShearSnapshot | None = None,
    ) -> None:
        """Serialize a complete state snapshot and caller-reported balance.

        ``time_s`` is in seconds.  Empty cell populations are valid and report
        zero biomass, height, and roughness.  Snapshot times must increase
        strictly, which makes row order and field names independent of caller
        collection ordering.
        """
        if self._finalized:
            raise OutputValidationError("writer has already been finalized")
        _require_nonnegative("time_s", time_s)
        if self._last_time_s is not None and time_s <= self._last_time_s:
            raise OutputValidationError("snapshot time_s must increase strictly")
        if not isinstance(solute_fields, SoluteFields):
            raise OutputValidationError("solute_fields must be a SoluteFields instance")

        ordered_cells = self._validated_cells(cells)
        ordered_events = self._validated_events(division_events)
        ordered_balance = self._validated_mass_balance_entries(mass_balance_entries)
        ordered_quorum_states = self._validated_quorum_state(
            time_s=time_s,
            cells=ordered_cells,
            solute_fields=solute_fields,
            signal_field=quorum_signal_field,
            states=quorum_states,
        )
        validated_eps_field = self._validated_eps_field(solute_fields, eps_field)
        validated_competition = self._validated_competition_snapshot(
            time_s=time_s,
            cells=ordered_cells,
            snapshot=competition_snapshot,
        )
        validated_physiology = self._validated_physiology_snapshot(
            time_s=time_s,
            cells=ordered_cells,
            snapshot=physiology_snapshot,
        )
        validated_waste_field = self._validated_waste_field(solute_fields, waste_field)
        validated_shear = self._validated_shear_snapshot(
            time_s=time_s,
            cells=ordered_cells,
            snapshot=shear_snapshot,
        )
        snapshot_index = len(self._field_files)
        field_file = self._fields_directory / f"{snapshot_index:06d}.npz"
        _write_field_archive(
            field_file,
            solute_fields,
            quorum_signal_field,
            validated_eps_field,
            validated_waste_field,
        )
        self._field_files.append(field_file)

        for cell in ordered_cells:
            self._cell_rows.append(
                {
                    "snapshot_index": snapshot_index,
                    "time_s": time_s,
                    "cell_id": cell.cell_id,
                    "parent_id": cell.parent_id,
                    "x_m": cell.x_m,
                    "y_m": cell.y_m,
                    "orientation_rad": cell.orientation_rad,
                    "length_m": cell.length_m,
                    "radius_m": cell.radius_m,
                    "dry_biomass_kg": cell.dry_biomass_kg,
                    "age_s": cell.age_s,
                    "state": cell.state,
                    "strain": cell.strain,
                }
            )

        height_m, roughness_m = _biofilm_geometry(ordered_cells)
        self._summary_rows.append(
            {
                "snapshot_index": snapshot_index,
                "time_s": time_s,
                "total_dry_biomass_kg": sum(
                    cell.dry_biomass_kg for cell in ordered_cells
                ),
                "cell_count": len(ordered_cells),
                "division_event_count": len(ordered_events),
                "biofilm_height_m": height_m,
                "biofilm_roughness_m": roughness_m,
            }
        )
        for event in ordered_events:
            self._division_event_rows.append(
                {
                    "time_s": time_s,
                    "parent_cell_id": event.parent_cell_id,
                    "first_daughter_cell_id": event.first_daughter_cell_id,
                    "second_daughter_cell_id": event.second_daughter_cell_id,
                }
            )
        for entry in ordered_balance:
            self._mass_balance_rows.append(
                {
                    "snapshot_index": snapshot_index,
                    "time_s": time_s,
                    "quantity": entry.quantity,
                    "unit": entry.unit,
                    "initial_amount": entry.initial_amount,
                    "final_amount": entry.final_amount,
                    "net_input_amount": entry.net_input_amount,
                    "residual_amount": entry.residual_amount,
                    "absolute_tolerance": entry.absolute_tolerance,
                    "relative_error": entry.relative_error,
                    "relative_tolerance": entry.relative_tolerance,
                }
            )
        for state in ordered_quorum_states:
            observation = state.current
            self._quorum_history_rows.append(
                {
                    "snapshot_index": snapshot_index,
                    "time_s": time_s,
                    "cell_id": state.cell_id,
                    "signal_concentration_mol_m3": (
                        observation.signal_concentration_mol_m3
                    ),
                    "activation_fraction": observation.activation_fraction,
                }
            )
        if validated_eps_field is not None:
            self._eps_summary_rows.append(
                {
                    "snapshot_index": snapshot_index,
                    "time_s": time_s,
                    "total_eps_kg": validated_eps_field.total_mass_kg,
                }
            )
        if validated_competition is not None:
            self._competition_summary_rows.append(
                {
                    "snapshot_index": snapshot_index,
                    "time_s": time_s,
                    "producer_cell_frequency": (
                        validated_competition.producer_cell_frequency
                    ),
                    "producer_biomass_frequency": (
                        validated_competition.producer_biomass_frequency
                    ),
                    "nearest_neighbor_segregation_fraction": (
                        validated_competition.nearest_neighbor_segregation_fraction
                    ),
                }
            )
            for strain_metric in validated_competition.strain_metrics:
                self._competition_strain_rows.append(
                    {
                        "snapshot_index": snapshot_index,
                        "time_s": time_s,
                        "strain": strain_metric.strain,
                        "role": strain_metric.role,
                        "cell_count": strain_metric.cell_count,
                        "cell_frequency": strain_metric.cell_frequency,
                        "dry_biomass_kg": strain_metric.dry_biomass_kg,
                        "biomass_frequency": strain_metric.biomass_frequency,
                        "mean_realized_local_fitness_s": (
                            strain_metric.mean_realized_local_fitness_s
                        ),
                    }
                )
            for cell_metric in validated_competition.cell_metrics:
                self._competition_cell_rows.append(
                    {
                        "snapshot_index": snapshot_index,
                        "time_s": time_s,
                        "cell_id": cell_metric.cell_id,
                        "parent_id": cell_metric.parent_id,
                        "strain": cell_metric.strain,
                        "role": cell_metric.role,
                        "initial_dry_biomass_kg": (
                            cell_metric.initial_dry_biomass_kg
                        ),
                        "final_dry_biomass_kg": cell_metric.final_dry_biomass_kg,
                        "realized_local_fitness_s": (
                            cell_metric.realized_local_fitness_s
                        ),
                        "eps_allocation_fraction": (
                            cell_metric.eps_allocation_fraction
                        ),
                        "local_eps_density_kg_m3": (
                            cell_metric.local_eps_density_kg_m3
                        ),
                        "cohesion_multiplier": cell_metric.cohesion_multiplier,
                        "attachment_strength_multiplier": (
                            cell_metric.attachment_strength_multiplier
                        ),
                    }
                )
        if validated_physiology is not None:
            totals = validated_physiology.totals
            self._physiology_summary_rows.append(
                {
                    "snapshot_index": snapshot_index,
                    "time_s": time_s,
                    "active_cell_count": totals.active_cell_count,
                    "slow_cell_count": totals.slow_cell_count,
                    "dormant_cell_count": totals.dormant_cell_count,
                    "dead_cell_count": totals.dead_cell_count,
                    "detached_cell_count": totals.detached_cell_count,
                    "active_biomass_kg": totals.active_biomass_kg,
                    "slow_biomass_kg": totals.slow_biomass_kg,
                    "dormant_biomass_kg": totals.dormant_biomass_kg,
                    "dead_biomass_kg": totals.dead_biomass_kg,
                    "detached_biomass_kg": totals.detached_biomass_kg,
                    "retained_biomass_kg": totals.retained_biomass_kg,
                    "recycled_dead_biomass_kg": (
                        totals.recycled_dead_biomass_kg
                    ),
                }
            )
        if validated_shear is not None:
            self._shear_summary_rows.append(
                {
                    "snapshot_index": snapshot_index,
                    "time_s": time_s,
                    "surface_parallel_shear_stress_pa": (
                        validated_shear.surface_parallel_shear_stress_pa
                    ),
                    "eligible_cell_count": validated_shear.eligible_cell_count,
                    "detached_cell_count": validated_shear.detached_cell_count,
                    "detachment_rate_s": validated_shear.detachment_rate_s,
                }
            )
        self._last_time_s = time_s

    def finalize(self) -> OutputPaths:
        """Write Parquet tables and return all finalized result paths."""
        if self._finalized:
            raise OutputValidationError("writer has already been finalized")
        if not self._summary_rows:
            raise OutputValidationError("at least one snapshot is required to finalize")
        cells_table = self._run_directory / "cell_snapshots.parquet"
        summary_table = self._run_directory / "summary.parquet"
        division_events_table = self._run_directory / "division_events.parquet"
        mass_balance_table = self._run_directory / "mass_balance.parquet"
        quorum_history_table = (
            self._run_directory / "quorum_history.parquet"
            if self._quorum_output_enabled is True
            else None
        )
        eps_summary_table = (
            self._run_directory / "eps_summary.parquet"
            if self._eps_output_enabled is True
            else None
        )
        competition_summary_table = (
            self._run_directory / "competition_summary.parquet"
            if self._competition_output_enabled is True
            else None
        )
        competition_strain_table = (
            self._run_directory / "competition_strains.parquet"
            if self._competition_output_enabled is True
            else None
        )
        competition_cell_table = (
            self._run_directory / "competition_cells.parquet"
            if self._competition_output_enabled is True
            else None
        )
        physiology_summary_table = (
            self._run_directory / "physiology_summary.parquet"
            if self._physiology_output_enabled is True
            else None
        )
        shear_summary_table = (
            self._run_directory / "shear_summary.parquet"
            if self._shear_output_enabled is True
            else None
        )
        staging_directory = self._run_directory
        try:
            _write_parquet(cells_table, self._cell_rows, _CELL_SCHEMA)
            _write_parquet(summary_table, self._summary_rows, _SUMMARY_SCHEMA)
            _write_parquet(
                division_events_table,
                self._division_event_rows,
                _DIVISION_EVENT_SCHEMA,
            )
            _write_parquet(
                mass_balance_table,
                self._mass_balance_rows,
                _MASS_BALANCE_SCHEMA,
            )
            if quorum_history_table is not None:
                _write_parquet(
                    quorum_history_table,
                    self._quorum_history_rows,
                    _QUORUM_HISTORY_SCHEMA,
                )
            if eps_summary_table is not None:
                _write_parquet(
                    eps_summary_table,
                    self._eps_summary_rows,
                    _EPS_SUMMARY_SCHEMA,
                )
            if competition_summary_table is not None:
                _write_parquet(
                    competition_summary_table,
                    self._competition_summary_rows,
                    _COMPETITION_SUMMARY_SCHEMA,
                )
            if competition_strain_table is not None:
                _write_parquet(
                    competition_strain_table,
                    self._competition_strain_rows,
                    _COMPETITION_STRAIN_SCHEMA,
                )
            if competition_cell_table is not None:
                _write_parquet(
                    competition_cell_table,
                    self._competition_cell_rows,
                    _COMPETITION_CELL_SCHEMA,
                )
            if physiology_summary_table is not None:
                _write_parquet(
                    physiology_summary_table,
                    self._physiology_summary_rows,
                    _PHYSIOLOGY_SUMMARY_SCHEMA,
                )
            if shear_summary_table is not None:
                _write_parquet(
                    shear_summary_table,
                    self._shear_summary_rows,
                    _SHEAR_SUMMARY_SCHEMA,
                )
            os.replace(staging_directory, self._published_run_directory)
        except Exception:
            shutil.rmtree(staging_directory, ignore_errors=True)
            raise

        def published_path(path: Path) -> Path:
            return self._published_run_directory / path.relative_to(staging_directory)

        self._run_directory = self._published_run_directory
        self._metadata_file = published_path(self._metadata_file)
        self._fields_directory = published_path(self._fields_directory)
        self._field_files = [published_path(path) for path in self._field_files]
        self._finalized = True
        return OutputPaths(
            run_directory=self._published_run_directory,
            metadata_file=self._metadata_file,
            cells_table=published_path(cells_table),
            summary_table=published_path(summary_table),
            division_events_table=published_path(division_events_table),
            mass_balance_table=published_path(mass_balance_table),
            field_files=tuple(self._field_files),
            quorum_history_table=(
                published_path(quorum_history_table)
                if quorum_history_table is not None
                else None
            ),
            eps_summary_table=(
                published_path(eps_summary_table)
                if eps_summary_table is not None
                else None
            ),
            competition_summary_table=(
                published_path(competition_summary_table)
                if competition_summary_table is not None
                else None
            ),
            competition_strain_table=(
                published_path(competition_strain_table)
                if competition_strain_table is not None
                else None
            ),
            competition_cell_table=(
                published_path(competition_cell_table)
                if competition_cell_table is not None
                else None
            ),
            physiology_summary_table=(
                published_path(physiology_summary_table)
                if physiology_summary_table is not None
                else None
            ),
            shear_summary_table=(
                published_path(shear_summary_table)
                if shear_summary_table is not None
                else None
            ),
        )

    def _write_metadata(self) -> None:
        contents = json.dumps(self._metadata.as_dict(), indent=2, sort_keys=True)
        _atomic_write_text(self._metadata_file, f"{contents}\n")

    @staticmethod
    def _validated_cells(cells: Sequence[Cell]) -> tuple[Cell, ...]:
        validated = tuple(cells)
        if any(not isinstance(cell, Cell) for cell in validated):
            raise OutputValidationError("cells must contain only Cell instances")
        identifiers = [cell.cell_id for cell in validated]
        if len(identifiers) != len(set(identifiers)):
            raise OutputValidationError("cell IDs in a snapshot must be unique")
        return tuple(sorted(validated, key=lambda cell: cell.cell_id))

    @staticmethod
    def _validated_events(
        division_events: Sequence[DivisionEvent],
    ) -> tuple[DivisionEvent, ...]:
        events = tuple(division_events)
        if any(not isinstance(event, DivisionEvent) for event in events):
            raise OutputValidationError(
                "division_events must contain only DivisionEvent instances"
            )
        return tuple(
            sorted(
                events,
                key=lambda event: (
                    event.parent_cell_id,
                    event.first_daughter_cell_id,
                    event.second_daughter_cell_id,
                ),
            )
        )

    @staticmethod
    def _validated_mass_balance_entries(
        mass_balance_entries: Sequence[MassBalanceEntry],
    ) -> tuple[MassBalanceEntry, ...]:
        entries = tuple(mass_balance_entries)
        if not entries:
            raise OutputValidationError("mass_balance_entries must not be empty")
        if any(not isinstance(entry, MassBalanceEntry) for entry in entries):
            raise OutputValidationError(
                "mass_balance_entries must contain only MassBalanceEntry instances"
            )
        quantities = [entry.quantity for entry in entries]
        if len(quantities) != len(set(quantities)):
            raise OutputValidationError("mass-balance quantities must be unique")
        failed = [
            entry.quantity
            for entry in entries
            if abs(entry.residual_amount) > entry.allowed_residual_amount
        ]
        if failed:
            names = ", ".join(sorted(failed))
            raise OutputValidationError(
                "mass-balance residual exceeds its combined tolerance for: " + names
            )
        return tuple(sorted(entries, key=lambda entry: entry.quantity))

    def _validated_quorum_state(
        self,
        *,
        time_s: float,
        cells: tuple[Cell, ...],
        solute_fields: SoluteFields,
        signal_field: SoluteField | None,
        states: Sequence[CellQuorumState] | None,
    ) -> tuple[CellQuorumState, ...]:
        if (signal_field is None) != (states is None):
            raise OutputValidationError(
                "quorum_signal_field and quorum_states must be supplied together"
            )
        quorum_supplied = signal_field is not None
        if self._quorum_output_enabled is None:
            self._quorum_output_enabled = quorum_supplied
        elif self._quorum_output_enabled != quorum_supplied:
            raise OutputValidationError(
                "quorum output mode must remain consistent across snapshots"
            )
        if signal_field is None or states is None:
            return ()
        if signal_field.shape != solute_fields.carbon.shape or (
            signal_field.width_m != solute_fields.carbon.width_m
            or signal_field.height_m != solute_fields.carbon.height_m
        ):
            raise OutputValidationError(
                "quorum signal field must share the solute grid geometry"
            )
        validated = tuple(states)
        if any(not isinstance(state, CellQuorumState) for state in validated):
            raise OutputValidationError(
                "quorum_states must contain only CellQuorumState instances"
            )
        state_by_id = {state.cell_id: state for state in validated}
        cell_ids = {cell.cell_id for cell in cells}
        if len(state_by_id) != len(validated) or set(state_by_id) != cell_ids:
            raise OutputValidationError(
                "quorum_states must contain exactly one state for every cell"
            )
        if any(state.current.time_s != time_s for state in validated):
            raise OutputValidationError(
                "current quorum observation time must equal snapshot time_s"
            )
        for cell in cells:
            row, column = signal_field.cell_index(cell.x_m, cell.y_m)
            recorded_concentration = state_by_id[
                cell.cell_id
            ].current.signal_concentration_mol_m3
            field_concentration = float(
                signal_field.concentration_mol_m3[row, column]
            )
            if recorded_concentration != field_concentration:
                raise OutputValidationError(
                    f"current quorum exposure for {cell.cell_id} must match the "
                    "signal field at the cell centre"
                )
        return tuple(state_by_id[cell.cell_id] for cell in cells)

    def _validated_eps_field(
        self,
        solute_fields: SoluteFields,
        eps_field: EPSField | None,
    ) -> EPSField | None:
        eps_supplied = eps_field is not None
        if self._eps_output_enabled is None:
            self._eps_output_enabled = eps_supplied
        elif self._eps_output_enabled != eps_supplied:
            raise OutputValidationError(
                "EPS output mode must remain consistent across snapshots"
            )
        if eps_field is None:
            return None
        carbon = solute_fields.carbon
        if (
            eps_field.shape != carbon.shape
            or eps_field.width_m != carbon.width_m
            or eps_field.height_m != carbon.height_m
        ):
            raise OutputValidationError(
                "EPS field must share the solute grid geometry"
            )
        return eps_field

    def _validated_competition_snapshot(
        self,
        *,
        time_s: float,
        cells: tuple[Cell, ...],
        snapshot: CompetitionSnapshot | None,
    ) -> CompetitionSnapshot | None:
        supplied = snapshot is not None
        if self._competition_output_enabled is None:
            self._competition_output_enabled = supplied
        elif self._competition_output_enabled != supplied:
            raise OutputValidationError(
                "competition output mode must remain consistent across snapshots"
            )
        if snapshot is None:
            return None
        if not isinstance(snapshot, CompetitionSnapshot):
            raise OutputValidationError(
                "competition_snapshot must be a CompetitionSnapshot instance"
            )
        if snapshot.time_s != time_s:
            raise OutputValidationError(
                "competition snapshot time_s must equal output snapshot time_s"
            )
        metric_by_id = {metric.cell_id: metric for metric in snapshot.cell_metrics}
        cell_ids = {cell.cell_id for cell in cells}
        if (
            len(metric_by_id) != len(snapshot.cell_metrics)
            or set(metric_by_id) != cell_ids
        ):
            raise OutputValidationError(
                "competition cell metrics must contain exactly one record for "
                "every cell"
            )
        for cell in cells:
            metric = metric_by_id[cell.cell_id]
            if (
                metric.strain != cell.strain
                or metric.parent_id != cell.parent_id
                or metric.final_dry_biomass_kg != cell.dry_biomass_kg
            ):
                raise OutputValidationError(
                    f"competition metric for {cell.cell_id} must match cell state"
                )
        return snapshot

    def _validated_physiology_snapshot(
        self,
        *,
        time_s: float,
        cells: tuple[Cell, ...],
        snapshot: PhysiologySnapshot | None,
    ) -> PhysiologySnapshot | None:
        supplied = snapshot is not None
        if self._physiology_output_enabled is None:
            self._physiology_output_enabled = supplied
        elif self._physiology_output_enabled != supplied:
            raise OutputValidationError(
                "physiology output mode must remain consistent across snapshots"
            )
        if snapshot is None:
            return None
        if not isinstance(snapshot, PhysiologySnapshot):
            raise OutputValidationError(
                "physiology_snapshot must be a PhysiologySnapshot instance"
            )
        if snapshot.time_s != time_s:
            raise OutputValidationError(
                "physiology snapshot time_s must equal output snapshot time_s"
            )
        try:
            expected = build_physiology_snapshot(
                time_s=time_s,
                cells=cells,
                cell_states=snapshot.cell_states,
            )
        except ValueError as error:
            raise OutputValidationError(
                f"invalid physiology snapshot: {error}"
            ) from error
        if snapshot != expected:
            raise OutputValidationError(
                "physiology snapshot totals must match the output cell population"
            )
        return snapshot

    def _validated_waste_field(
        self,
        solute_fields: SoluteFields,
        waste_field: SoluteField | None,
    ) -> SoluteField | None:
        supplied = waste_field is not None
        if self._waste_output_enabled is None:
            self._waste_output_enabled = supplied
        elif self._waste_output_enabled != supplied:
            raise OutputValidationError(
                "waste output mode must remain consistent across snapshots"
            )
        if waste_field is None:
            return None
        carbon = solute_fields.carbon
        if (
            waste_field.shape != carbon.shape
            or waste_field.width_m != carbon.width_m
            or waste_field.height_m != carbon.height_m
        ):
            raise OutputValidationError(
                "waste field must share the solute grid geometry"
            )
        return waste_field

    def _validated_shear_snapshot(
        self,
        *,
        time_s: float,
        cells: tuple[Cell, ...],
        snapshot: ShearSnapshot | None,
    ) -> ShearSnapshot | None:
        supplied = snapshot is not None
        if self._shear_output_enabled is None:
            self._shear_output_enabled = supplied
        elif self._shear_output_enabled != supplied:
            raise OutputValidationError(
                "shear output mode must remain consistent across snapshots"
            )
        if snapshot is None:
            return None
        if not isinstance(snapshot, ShearSnapshot):
            raise OutputValidationError(
                "shear_snapshot must be a ShearSnapshot instance"
            )
        if snapshot.time_s != time_s:
            raise OutputValidationError(
                "shear snapshot time_s must equal output snapshot time_s"
            )
        state_by_id = {state.cell_id: state for state in snapshot.cell_states}
        cell_ids = {cell.cell_id for cell in cells}
        if (
            len(state_by_id) != len(snapshot.cell_states)
            or set(state_by_id) != cell_ids
        ):
            raise OutputValidationError(
                "shear states must contain exactly one record for every cell"
            )
        if any(state.current.time_s != time_s for state in snapshot.cell_states):
            raise OutputValidationError(
                "current shear observation time must equal snapshot time_s"
            )
        observed_detachments = sum(
            state.current.detached_by_shear for state in snapshot.cell_states
        )
        if observed_detachments != snapshot.detached_cell_count:
            raise OutputValidationError(
                "shear detached count must match cell shear observations"
            )
        return snapshot


_CELL_SCHEMA = pa.schema(
    [
        pa.field("snapshot_index", pa.int64()),
        pa.field("time_s", pa.float64()),
        pa.field("cell_id", pa.string()),
        pa.field("parent_id", pa.string(), nullable=True),
        pa.field("x_m", pa.float64()),
        pa.field("y_m", pa.float64()),
        pa.field("orientation_rad", pa.float64()),
        pa.field("length_m", pa.float64()),
        pa.field("radius_m", pa.float64()),
        pa.field("dry_biomass_kg", pa.float64()),
        pa.field("age_s", pa.float64()),
        pa.field("state", pa.string()),
        pa.field("strain", pa.string()),
    ]
)
_SUMMARY_SCHEMA = pa.schema(
    [
        pa.field("snapshot_index", pa.int64()),
        pa.field("time_s", pa.float64()),
        pa.field("total_dry_biomass_kg", pa.float64()),
        pa.field("cell_count", pa.int64()),
        pa.field("division_event_count", pa.int64()),
        pa.field("biofilm_height_m", pa.float64()),
        pa.field("biofilm_roughness_m", pa.float64()),
    ]
)
_DIVISION_EVENT_SCHEMA = pa.schema(
    [
        pa.field("time_s", pa.float64()),
        pa.field("parent_cell_id", pa.string()),
        pa.field("first_daughter_cell_id", pa.string()),
        pa.field("second_daughter_cell_id", pa.string()),
    ]
)
_MASS_BALANCE_SCHEMA = pa.schema(
    [
        pa.field("snapshot_index", pa.int64()),
        pa.field("time_s", pa.float64()),
        pa.field("quantity", pa.string()),
        pa.field("unit", pa.string()),
        pa.field("initial_amount", pa.float64()),
        pa.field("final_amount", pa.float64()),
        pa.field("net_input_amount", pa.float64()),
        pa.field("residual_amount", pa.float64()),
        pa.field("absolute_tolerance", pa.float64()),
        pa.field("relative_error", pa.float64()),
        pa.field("relative_tolerance", pa.float64()),
    ]
)
_QUORUM_HISTORY_SCHEMA = pa.schema(
    [
        pa.field("snapshot_index", pa.int64()),
        pa.field("time_s", pa.float64()),
        pa.field("cell_id", pa.string()),
        pa.field("signal_concentration_mol_m3", pa.float64()),
        pa.field("activation_fraction", pa.float64()),
    ]
)
_EPS_SUMMARY_SCHEMA = pa.schema(
    [
        pa.field("snapshot_index", pa.int64()),
        pa.field("time_s", pa.float64()),
        pa.field("total_eps_kg", pa.float64()),
    ]
)
_COMPETITION_SUMMARY_SCHEMA = pa.schema(
    [
        pa.field("snapshot_index", pa.int64()),
        pa.field("time_s", pa.float64()),
        pa.field("producer_cell_frequency", pa.float64()),
        pa.field("producer_biomass_frequency", pa.float64()),
        pa.field("nearest_neighbor_segregation_fraction", pa.float64()),
    ]
)
_COMPETITION_STRAIN_SCHEMA = pa.schema(
    [
        pa.field("snapshot_index", pa.int64()),
        pa.field("time_s", pa.float64()),
        pa.field("strain", pa.string()),
        pa.field("role", pa.string()),
        pa.field("cell_count", pa.int64()),
        pa.field("cell_frequency", pa.float64()),
        pa.field("dry_biomass_kg", pa.float64()),
        pa.field("biomass_frequency", pa.float64()),
        pa.field("mean_realized_local_fitness_s", pa.float64()),
    ]
)
_COMPETITION_CELL_SCHEMA = pa.schema(
    [
        pa.field("snapshot_index", pa.int64()),
        pa.field("time_s", pa.float64()),
        pa.field("cell_id", pa.string()),
        pa.field("parent_id", pa.string(), nullable=True),
        pa.field("strain", pa.string()),
        pa.field("role", pa.string()),
        pa.field("initial_dry_biomass_kg", pa.float64()),
        pa.field("final_dry_biomass_kg", pa.float64()),
        pa.field("realized_local_fitness_s", pa.float64()),
        pa.field("eps_allocation_fraction", pa.float64()),
        pa.field("local_eps_density_kg_m3", pa.float64()),
        pa.field("cohesion_multiplier", pa.float64()),
        pa.field("attachment_strength_multiplier", pa.float64()),
    ]
)
_PHYSIOLOGY_SUMMARY_SCHEMA = pa.schema(
    [
        pa.field("snapshot_index", pa.int64()),
        pa.field("time_s", pa.float64()),
        pa.field("active_cell_count", pa.int64()),
        pa.field("slow_cell_count", pa.int64()),
        pa.field("dormant_cell_count", pa.int64()),
        pa.field("dead_cell_count", pa.int64()),
        pa.field("detached_cell_count", pa.int64()),
        pa.field("active_biomass_kg", pa.float64()),
        pa.field("slow_biomass_kg", pa.float64()),
        pa.field("dormant_biomass_kg", pa.float64()),
        pa.field("dead_biomass_kg", pa.float64()),
        pa.field("detached_biomass_kg", pa.float64()),
        pa.field("retained_biomass_kg", pa.float64()),
        pa.field("recycled_dead_biomass_kg", pa.float64()),
    ]
)
_SHEAR_SUMMARY_SCHEMA = pa.schema(
    [
        pa.field("snapshot_index", pa.int64()),
        pa.field("time_s", pa.float64()),
        pa.field("surface_parallel_shear_stress_pa", pa.float64()),
        pa.field("eligible_cell_count", pa.int64()),
        pa.field("detached_cell_count", pa.int64()),
        pa.field("detachment_rate_s", pa.float64()),
    ]
)


def _write_parquet(
    path: Path, rows: list[dict[str, object]], schema: pa.Schema
) -> None:
    table = pa.Table.from_pylist(rows, schema=schema)

    def write(temporary_path: Path) -> None:
        pq.write_table(
            table,
            temporary_path,
            compression="zstd",
            use_dictionary=False,
            write_statistics=False,
            data_page_version="1.0",
        )

    _atomic_file(path, write)


def _write_field_archive(
    path: Path,
    fields: SoluteFields,
    quorum_signal_field: SoluteField | None = None,
    eps_field: EPSField | None = None,
    waste_field: SoluteField | None = None,
) -> None:
    arrays: tuple[tuple[str, np.ndarray[Any, np.dtype[Any]]], ...] = (
        (
            "carbon_concentration_mol_m3",
            np.asarray(fields.carbon.concentration_mol_m3, dtype=np.float64),
        ),
        (
            "oxygen_concentration_mol_m3",
            np.asarray(fields.oxygen.concentration_mol_m3, dtype=np.float64),
        ),
        ("carbon_name", np.asarray(fields.carbon.name)),
        ("oxygen_name", np.asarray(fields.oxygen.name)),
        ("shape", np.asarray(fields.carbon.shape, dtype=np.int64)),
        ("width_m", np.asarray(fields.carbon.width_m, dtype=np.float64)),
        ("height_m", np.asarray(fields.carbon.height_m, dtype=np.float64)),
        (
            "carbon_diffusivity_m2_s",
            np.asarray(fields.carbon.diffusivity_m2_s, dtype=np.float64),
        ),
        (
            "oxygen_diffusivity_m2_s",
            np.asarray(fields.oxygen.diffusivity_m2_s, dtype=np.float64),
        ),
        (
            "carbon_top_bulk_concentration_mol_m3",
            np.asarray(fields.carbon.top_bulk_concentration_mol_m3, dtype=np.float64),
        ),
        (
            "oxygen_top_bulk_concentration_mol_m3",
            np.asarray(fields.oxygen.top_bulk_concentration_mol_m3, dtype=np.float64),
        ),
    )
    if quorum_signal_field is not None:
        arrays += (
            (
                "quorum_signal_concentration_mol_m3",
                np.asarray(
                    quorum_signal_field.concentration_mol_m3,
                    dtype=np.float64,
                ),
            ),
            ("quorum_signal_name", np.asarray(quorum_signal_field.name)),
            (
                "quorum_signal_diffusivity_m2_s",
                np.asarray(quorum_signal_field.diffusivity_m2_s, dtype=np.float64),
            ),
            (
                "quorum_signal_top_bulk_concentration_mol_m3",
                np.asarray(
                    quorum_signal_field.top_bulk_concentration_mol_m3,
                    dtype=np.float64,
                ),
            ),
        )
    if eps_field is not None:
        arrays += (
            (
                "eps_density_kg_m3",
                np.asarray(eps_field.density_kg_m3, dtype=np.float64),
            ),
            ("eps_depth_m", np.asarray(eps_field.depth_m, dtype=np.float64)),
        )
    if waste_field is not None:
        arrays += (
            (
                "waste_concentration_mol_m3",
                np.asarray(waste_field.concentration_mol_m3, dtype=np.float64),
            ),
            ("waste_name", np.asarray(waste_field.name)),
            (
                "waste_diffusivity_m2_s",
                np.asarray(waste_field.diffusivity_m2_s, dtype=np.float64),
            ),
            (
                "waste_top_bulk_concentration_mol_m3",
                np.asarray(
                    waste_field.top_bulk_concentration_mol_m3,
                    dtype=np.float64,
                ),
            ),
        )
    def write(temporary_path: Path) -> None:
        with ZipFile(
            temporary_path, "w", compression=ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for name, array in arrays:
                buffer = BytesIO()
                _write_array(buffer, array, allow_pickle=False)
                entry = ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = ZIP_DEFLATED
                entry.create_system = 3
                entry.external_attr = 0o600 << 16
                archive.writestr(entry, buffer.getvalue(), compress_type=ZIP_DEFLATED)

    _atomic_file(path, write)


def _biofilm_geometry(cells: Sequence[Cell]) -> tuple[float, float]:
    if not cells:
        return 0.0, 0.0
    top_elevations_m = [
        max(endpoint[1] for endpoint in cell.centreline_endpoints_m) + cell.radius_m
        for cell in cells
    ]
    if any(top_elevation_m < 0.0 for top_elevation_m in top_elevations_m):
        raise OutputValidationError("cell capsule tops must not be below the bottom")
    mean_elevation_m = sum(top_elevations_m) / len(top_elevations_m)
    roughness_m = sqrt(
        sum((elevation_m - mean_elevation_m) ** 2 for elevation_m in top_elevations_m)
        / len(top_elevations_m)
    )
    return max(top_elevations_m), roughness_m


def _require_nonblank(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise OutputValidationError(f"{name} must be a non-blank string")


def _require_sha256(name: str, value: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OutputValidationError(
            f"{name} must be exactly 64 lowercase hexadecimal characters"
        )


def _atomic_file(path: Path, writer: Callable[[Path], None]) -> None:
    """Write one unpublished sibling file, then publish it with replacement."""
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    os.close(descriptor)
    try:
        writer(temporary_path)
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _atomic_write_text(path: Path, contents: str) -> None:
    def write(temporary_path: Path) -> None:
        with temporary_path.open("w", encoding="utf-8") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())

    _atomic_file(path, write)


def _require_finite(name: str, value: float) -> None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise OutputValidationError(f"{name} must be finite")


def _require_nonnegative(name: str, value: float) -> None:
    _require_finite(name, value)
    if value < 0.0:
        raise OutputValidationError(f"{name} must be greater than or equal to zero")
