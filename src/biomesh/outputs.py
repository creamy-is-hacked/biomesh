"""Deterministic P1-WP06 serialization of existing simulation state.

This module has no simulation update logic.  It writes the caller-owned
``Cell`` and ``SoluteFields`` state after a step, preserving SI quantities in
column and array names.  Biofilm height is the greatest capsule-top elevation
above the solid bottom; roughness is the population standard deviation of
capsule-top elevations.  Both are geometric summaries, not biological
parameters.  Mass-balance entries are supplied by the simulation because this
layer must not infer unrecorded sources, sinks, or boundary fluxes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from math import isfinite, sqrt
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from biomesh.cells import Cell
from biomesh.solutes import SoluteFields


class OutputValidationError(ValueError):
    """Raised when an output record is incomplete, ambiguous, or unsafe."""


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

    def __post_init__(self) -> None:
        if (
            not isinstance(self.seed, int)
            or isinstance(self.seed, bool)
            or self.seed < 0
        ):
            raise OutputValidationError("seed must be a nonnegative integer")
        _require_nonblank("package_version", self.package_version)
        _require_nonblank("commit_hash", self.commit_hash)
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

    def as_dict(self) -> dict[str, object]:
        """Return metadata in the stable structure written to JSON."""
        return {
            "commit_hash": self.commit_hash,
            "package_version": self.package_version,
            "parameters": self.parameters,
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

    def __post_init__(self) -> None:
        _require_nonblank("quantity", self.quantity)
        _require_nonblank("unit", self.unit)
        _require_finite("initial_amount", self.initial_amount)
        _require_finite("final_amount", self.final_amount)
        _require_finite("net_input_amount", self.net_input_amount)
        _require_nonnegative("absolute_tolerance", self.absolute_tolerance)

    @property
    def residual_amount(self) -> float:
        """Return the signed balance residual in the entry's declared unit."""
        return self.final_amount - self.initial_amount - self.net_input_amount


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


class SimulationOutputWriter:
    """Write deterministic P1 output artifacts without retaining model state.

    Each :meth:`write_snapshot` call serializes field arrays immediately and
    retains only table rows needed to make compact Parquet tables at
    :meth:`finalize`.  Cell, field, and event records are canonically ordered
    before serialization.  A writer owns a new run directory and never
    overwrites an existing result.
    """

    def __init__(self, run_directory: Path, metadata: RunMetadata) -> None:
        if not isinstance(metadata, RunMetadata):
            raise OutputValidationError("metadata must be a RunMetadata instance")
        self._run_directory = Path(run_directory)
        if self._run_directory.exists():
            raise OutputValidationError("run_directory must not already exist")
        self._run_directory.mkdir(parents=True)
        self._metadata = metadata
        self._metadata_file = self._run_directory / "run_metadata.json"
        self._write_metadata()
        self._fields_directory = self._run_directory / "fields"
        self._fields_directory.mkdir()
        self._cell_rows: list[dict[str, object]] = []
        self._summary_rows: list[dict[str, object]] = []
        self._division_event_rows: list[dict[str, object]] = []
        self._mass_balance_rows: list[dict[str, object]] = []
        self._field_files: list[Path] = []
        self._last_time_s: float | None = None
        self._finalized = False

    def write_snapshot(
        self,
        *,
        time_s: float,
        cells: Sequence[Cell],
        solute_fields: SoluteFields,
        division_events: Sequence[DivisionEvent],
        mass_balance_entries: Sequence[MassBalanceEntry],
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
        snapshot_index = len(self._field_files)
        field_file = self._fields_directory / f"{snapshot_index:06d}.npz"
        _write_field_archive(field_file, solute_fields)
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
        _write_parquet(cells_table, self._cell_rows, _CELL_SCHEMA)
        _write_parquet(summary_table, self._summary_rows, _SUMMARY_SCHEMA)
        _write_parquet(
            division_events_table, self._division_event_rows, _DIVISION_EVENT_SCHEMA
        )
        _write_parquet(
            mass_balance_table, self._mass_balance_rows, _MASS_BALANCE_SCHEMA
        )
        self._finalized = True
        return OutputPaths(
            run_directory=self._run_directory,
            metadata_file=self._metadata_file,
            cells_table=cells_table,
            summary_table=summary_table,
            division_events_table=division_events_table,
            mass_balance_table=mass_balance_table,
            field_files=tuple(self._field_files),
        )

    def _write_metadata(self) -> None:
        contents = json.dumps(self._metadata.as_dict(), indent=2, sort_keys=True)
        self._metadata_file.write_text(f"{contents}\n", encoding="utf-8")

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
        return tuple(sorted(entries, key=lambda entry: entry.quantity))


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
    ]
)


def _write_parquet(
    path: Path, rows: list[dict[str, object]], schema: pa.Schema
) -> None:
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(
        table,
        path,
        compression="zstd",
        use_dictionary=False,
        write_statistics=False,
        data_page_version="1.0",
    )


def _write_field_archive(path: Path, fields: SoluteFields) -> None:
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
    with ZipFile(path, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, array in arrays:
            buffer = BytesIO()
            np.lib.format.write_array(  # type: ignore[no-untyped-call]
                buffer, array, allow_pickle=False
            )
            entry = ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o600 << 16
            archive.writestr(entry, buffer.getvalue(), compress_type=ZIP_DEFLATED)


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
