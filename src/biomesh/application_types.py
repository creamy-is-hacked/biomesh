"""Immutable public value types for the P3-WP01 application boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


class ApplicationError(ValueError):
    """Raised for invalid application operations or state transitions."""


class RunStatus(StrEnum):
    """Lifecycle states visible at the application boundary."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class RunRequest:
    """Exact existing P2 fixture condition and deterministic seed to run."""

    fixture_file: Path
    condition_id: str
    seed: int

    def __post_init__(self) -> None:
        if not isinstance(self.fixture_file, Path):
            raise ApplicationError("fixture_file must be a Path")
        if not isinstance(self.condition_id, str) or not self.condition_id.strip():
            raise ApplicationError("condition_id must be a nonblank string")
        if (
            not isinstance(self.seed, int)
            or isinstance(self.seed, bool)
            or self.seed < 0
        ):
            raise ApplicationError("seed must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class ParameterProvenance:
    """Immutable identity for one existing biological-parameter record."""

    label: str
    sha256: str


@dataclass(frozen=True, slots=True)
class CellSnapshot:
    """Immutable GUI-safe copy of one cell record in SI units."""

    cell_id: str
    parent_id: str | None
    x_m: float
    y_m: float
    orientation_rad: float
    length_m: float
    radius_m: float
    dry_biomass_kg: float
    age_s: float
    state: str
    strain: str


@dataclass(frozen=True, slots=True)
class FieldSnapshot:
    """Immutable little-endian float64 field payload with explicit SI unit."""

    name: str
    unit: str
    shape: tuple[int, int]
    data: bytes

    @classmethod
    def from_array(
        cls, *, name: str, unit: str, values: NDArray[np.float64]
    ) -> FieldSnapshot:
        array = np.ascontiguousarray(values, dtype="<f8")
        if array.ndim != 2 or not np.all(np.isfinite(array)):
            raise ApplicationError("snapshot fields must be finite 2D arrays")
        return cls(name=name, unit=unit, shape=array.shape, data=array.tobytes())

    def as_array(self) -> NDArray[np.float64]:
        """Return a zero-copy read-only view backed by immutable bytes."""
        return np.frombuffer(self.data, dtype="<f8").reshape(self.shape)


@dataclass(frozen=True, slots=True)
class MetricSnapshot:
    """One immutable scalar observation at the current solver boundary."""

    name: str
    unit: str
    value: float


@dataclass(frozen=True, slots=True)
class AccountingSnapshot:
    """One immutable current-interval accounting record."""

    quantity: str
    unit: str
    initial_amount: float
    final_amount: float
    net_input_amount: float
    residual_amount: float
    relative_error: float


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    """Complete immutable application view at one accepted solver boundary."""

    status: RunStatus
    condition_id: str
    seed: int
    step_index: int
    step_count: int
    time_s: float
    configuration_sha256: str
    calibration_status: str
    parameter_provenance: tuple[ParameterProvenance, ...]
    cells: tuple[CellSnapshot, ...]
    fields: tuple[FieldSnapshot, ...]
    metrics: tuple[MetricSnapshot, ...]
    accounting: tuple[AccountingSnapshot, ...]

    def field(self, name: str) -> FieldSnapshot:
        """Return one named immutable field or fail explicitly."""
        for field in self.fields:
            if field.name == name:
                return field
        raise ApplicationError(f"snapshot has no field {name!r}")


@dataclass(frozen=True, slots=True)
class LocalValue:
    """One cell-local immutable SI value returned by inspection."""

    name: str
    unit: str
    value: float


@dataclass(frozen=True, slots=True)
class CellInspection:
    """Immutable cell and local-field view derived from the current boundary."""

    cell: CellSnapshot
    local_values: tuple[LocalValue, ...]
    quorum_activation_fraction: float


@dataclass(frozen=True, slots=True)
class CheckpointResult:
    """Identity of one replay-verifiable application checkpoint."""

    checkpoint_file: Path
    sha256: str
    step_index: int


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Existing canonical P2 raw artifacts exported by the application API."""

    output_directory: Path
    files: tuple[Path, ...]
