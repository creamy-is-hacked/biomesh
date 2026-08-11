"""Immutable version 1 component contracts for the BioMesh Plugin API."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, Protocol, Self, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from biomesh.config import BiologicalParameter

PLUGIN_API_VERSION = 1

Identifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]
NonBlankText = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
VersionText = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9._-]*)?$"),
]
PluginComponentKind = Literal["exporter", "field", "kinetics", "metric", "species"]


class PluginError(ValueError):
    """Raised when plugin declarations, loading, or verification fail closed."""


class PluginMetadata(BaseModel):
    """Versioned identity and limitations declared without importing a plugin."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    plugin_api_version: int = Field(ge=1)
    plugin_id: Identifier
    plugin_version: VersionText
    display_name: NonBlankText
    components: list[PluginComponentKind] = Field(min_length=1)
    source: NonBlankText
    calibration_status: Literal["CALIBRATION_REQUIRED"]
    limitations: list[NonBlankText] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_canonical_lists(self) -> Self:
        if isinstance(self.plugin_api_version, bool):
            raise ValueError("plugin_api_version must be an integer")
        if self.components != sorted(set(self.components)):
            raise ValueError("plugin components must be unique and sorted")
        if self.limitations != sorted(set(self.limitations)):
            raise ValueError("plugin limitations must be unique and sorted")
        return self


class SpeciesDefinition(BaseModel):
    """Non-numeric species identity returned by a species component."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    interface_version: Literal[1]
    species_id: Identifier
    display_name: NonBlankText
    calibration_status: Literal["CALIBRATION_REQUIRED"]
    notes: NonBlankText


class KineticsRequest(BaseModel):
    """Immutable SI/provenance-complete inputs for a kinetics component."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    interface_version: Literal[1]
    carbon_concentration_mol_m3: float = Field(ge=0.0)
    oxygen_concentration_mol_m3: float = Field(ge=0.0)
    biological_parameters: list[BiologicalParameter] = Field(min_length=3)

    @model_validator(mode="after")
    def validate_inputs(self) -> Self:
        if not isfinite(self.carbon_concentration_mol_m3) or not isfinite(
            self.oxygen_concentration_mol_m3
        ):
            raise ValueError("kinetics concentrations must be finite")
        expected = {
            "maximum_specific_growth_rate",
            "carbon_half_saturation_constant",
            "oxygen_half_saturation_constant",
        }
        names = [item.name for item in self.biological_parameters]
        if set(names) != expected or len(names) != len(expected):
            raise ValueError(
                "kinetics requires one provenance record for each declared parameter"
            )
        if any(
            item.value == "CALIBRATION_REQUIRED"
            for item in self.biological_parameters
        ):
            raise ValueError("unresolved kinetics parameters cannot execute")
        return self


class KineticsResult(BaseModel):
    """One unit-explicit immutable kinetics result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    interface_version: Literal[1]
    specific_growth_rate_s: float = Field(ge=0.0)
    unit: Literal["s^-1"]

    @model_validator(mode="after")
    def validate_finite(self) -> Self:
        if not isfinite(self.specific_growth_rate_s):
            raise ValueError("specific growth rate must be finite")
        return self


@dataclass(frozen=True, slots=True)
class FieldStepRequest:
    """Immutable field input with explicit SI unit and row-major shape."""

    interface_version: Literal[1]
    field_id: str
    unit: str
    shape: tuple[int, int]
    values: tuple[float, ...]
    time_step_s: float

    def __post_init__(self) -> None:
        _validate_interface_version(self.interface_version)
        _validate_field_values(self.field_id, self.unit, self.shape, self.values)
        if (
            isinstance(self.time_step_s, bool)
            or not isfinite(self.time_step_s)
            or self.time_step_s <= 0.0
        ):
            raise PluginError("field time_step_s must be finite and positive")


@dataclass(frozen=True, slots=True)
class FieldStepResult:
    """Immutable field output in the request's declared SI unit."""

    interface_version: Literal[1]
    field_id: str
    unit: str
    shape: tuple[int, int]
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        _validate_interface_version(self.interface_version)
        _validate_field_values(self.field_id, self.unit, self.shape, self.values)


@dataclass(frozen=True, slots=True)
class MetricRequest:
    """Immutable named scalar inputs to a metric component."""

    interface_version: Literal[1]
    values: tuple[tuple[str, float, str], ...]

    def __post_init__(self) -> None:
        _validate_interface_version(self.interface_version)
        if not self.values:
            raise PluginError("metric values must not be empty")
        names = [name for name, _value, _unit in self.values]
        if names != sorted(set(names)):
            raise PluginError("metric input names must be unique and sorted")
        for name, value, unit in self.values:
            _require_nonblank("metric input name", name)
            _require_nonblank("metric input unit", unit)
            if isinstance(value, bool) or not isfinite(value):
                raise PluginError("metric input values must be finite numbers")


@dataclass(frozen=True, slots=True)
class MetricResult:
    """One immutable unit-explicit metric value."""

    interface_version: Literal[1]
    metric_id: str
    value: float
    unit: str

    def __post_init__(self) -> None:
        _validate_interface_version(self.interface_version)
        _require_nonblank("metric_id", self.metric_id)
        _require_nonblank("metric unit", self.unit)
        if isinstance(self.value, bool) or not isfinite(self.value):
            raise PluginError("metric result value must be a finite number")


@dataclass(frozen=True, slots=True)
class ExportRequest:
    """Hash-bound immutable artifacts offered to an exporter component."""

    interface_version: Literal[1]
    artifacts: tuple[tuple[str, str, int], ...]
    output_directory: Path

    def __post_init__(self) -> None:
        _validate_interface_version(self.interface_version)
        _validate_artifact_identities(self.artifacts)
        if self.output_directory.exists() or self.output_directory.is_symlink():
            raise PluginError("export output directory must not already exist")
        if not self.output_directory.parent.is_dir():
            raise PluginError("export output parent must exist")


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Hash-bound files produced by an exporter component."""

    interface_version: Literal[1]
    artifacts: tuple[tuple[str, str, int], ...]

    def __post_init__(self) -> None:
        _validate_interface_version(self.interface_version)
        _validate_artifact_identities(self.artifacts)


class PluginSelfCheck(BaseModel):
    """Deterministic plugin-owned compatibility probe result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    plugin_id: Identifier
    plugin_version: VersionText
    passed: Literal[True]
    details: NonBlankText


@runtime_checkable
class BasePlugin(Protocol):
    """Methods required for every BioMesh plugin."""

    def metadata(self) -> PluginMetadata: ...

    def self_check(self) -> PluginSelfCheck: ...


@runtime_checkable
class SpeciesPlugin(BasePlugin, Protocol):
    """Version 1 species-component interface."""

    def species_definition(self) -> SpeciesDefinition: ...


@runtime_checkable
class KineticsPlugin(BasePlugin, Protocol):
    """Version 1 kinetics-component interface."""

    def evaluate_kinetics(self, request: KineticsRequest) -> KineticsResult: ...


@runtime_checkable
class FieldPlugin(BasePlugin, Protocol):
    """Version 1 field-component interface."""

    def advance_field(self, request: FieldStepRequest) -> FieldStepResult: ...


@runtime_checkable
class MetricPlugin(BasePlugin, Protocol):
    """Version 1 metric-component interface."""

    def evaluate_metric(self, request: MetricRequest) -> MetricResult: ...


@runtime_checkable
class ExporterPlugin(BasePlugin, Protocol):
    """Version 1 exporter-component interface."""

    def export(self, request: ExportRequest) -> ExportResult: ...


def _validate_interface_version(interface_version: int) -> None:
    if interface_version != PLUGIN_API_VERSION or isinstance(interface_version, bool):
        raise PluginError(
            f"incompatible component interface {interface_version}; "
            f"core supports {PLUGIN_API_VERSION}"
        )


def _validate_field_values(
    field_id: str,
    unit: str,
    shape: tuple[int, int],
    values: tuple[float, ...],
) -> None:
    _require_nonblank("field_id", field_id)
    _require_nonblank("field unit", unit)
    if (
        len(shape) != 2
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in shape
        )
    ):
        raise PluginError("field shape must contain two positive integers")
    if len(values) != shape[0] * shape[1]:
        raise PluginError("field values must match the declared row-major shape")
    if any(isinstance(value, bool) or not isfinite(value) for value in values):
        raise PluginError("field values must be finite numbers")


def _validate_artifact_identities(
    artifacts: tuple[tuple[str, str, int], ...],
) -> None:
    if not artifacts:
        raise PluginError("export artifacts must not be empty")
    paths = [path for path, _sha256, _size in artifacts]
    if paths != sorted(set(paths)):
        raise PluginError("export artifact paths must be unique and sorted")
    for path, sha256, size_bytes in artifacts:
        relative = PurePosixPath(path)
        if (
            not path
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() != path
        ):
            raise PluginError("export artifact paths must be safe relative paths")
        if re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            raise PluginError("export artifact SHA-256 must be canonical")
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int):
            raise PluginError("export artifact size must be an integer")
        if size_bytes < 0:
            raise PluginError("export artifact size must be nonnegative")


def _require_nonblank(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PluginError(f"{label} must not be blank")
