"""Strict P4-WP07 benchmark interface and report records."""

from __future__ import annotations

from typing import Literal, Protocol, Self

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, model_validator

BENCHMARK_API_VERSION = 1


class BenchmarkError(ValueError):
    """Raised when a benchmark request or backend result is invalid."""


class BenchmarkCase(BaseModel):
    """One immutable, unit-explicit synthetic software benchmark case."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1] = 1
    case_id: Literal["synthetic-2d-five-point-stencil"] = (
        "synthetic-2d-five-point-stencil"
    )
    value_unit: Literal["dimensionless"] = "dimensionless"
    boundary_condition: Literal["fixed-edge"] = "fixed-edge"
    rows: int = Field(default=48, ge=3, le=4096)
    columns: int = Field(default=48, ge=3, le=4096)
    steps: int = Field(default=4, ge=1, le=10_000)
    absolute_tolerance: float = Field(default=1.0e-12, ge=0.0)
    relative_tolerance: float = Field(default=1.0e-12, ge=0.0)


class BackendDescriptor(BaseModel):
    """Declarative identity and explicit scope of one benchmark backend."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    benchmark_api_version: Literal[1] = 1
    backend_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    implementation: str = Field(min_length=1)
    experimental: bool
    processor_kind: Literal["CPU", "GPU"] = "CPU"
    dimensionality: Literal["2D", "3D"] = "2D"
    gpu_used: bool = False

    @model_validator(mode="after")
    def validate_processor_identity(self) -> Self:
        if self.gpu_used != (self.processor_kind == "GPU"):
            raise ValueError("gpu_used must match processor_kind")
        return self


class BackendObservation(BaseModel):
    """Output identity plus optional raw timing observations for one backend."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    backend: BackendDescriptor
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    value_count: int = Field(gt=0)
    elapsed_ns: list[int]
    performance_status: Literal["NOT_MEASURED", "RAW_OBSERVATIONS_ONLY"]

    @model_validator(mode="after")
    def validate_performance_status(self) -> Self:
        expected = "RAW_OBSERVATIONS_ONLY" if self.elapsed_ns else "NOT_MEASURED"
        if self.performance_status != expected:
            raise ValueError("performance_status does not match elapsed_ns")
        if any(value < 0 for value in self.elapsed_ns):
            raise ValueError("elapsed_ns values must be non-negative")
        return self


class DivergenceMeasurement(BaseModel):
    """Pointwise candidate divergence from the CPU reference."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    comparison: Literal["numpy.isclose(equal_nan=False)"] = (
        "numpy.isclose(equal_nan=False)"
    )
    absolute_tolerance: float = Field(ge=0.0)
    relative_tolerance: float = Field(ge=0.0)
    maximum_absolute_divergence: float = Field(ge=0.0)
    maximum_relative_divergence: float | None = Field(default=None, ge=0.0)
    mean_absolute_divergence: float = Field(ge=0.0)
    mismatched_value_count: int = Field(ge=0)
    value_count: int = Field(gt=0)
    equivalent: bool


class BenchmarkEnvironment(BaseModel):
    """Software and host identity needed to interpret local observations."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    biomesh_version: str = Field(min_length=1)
    python_version: str = Field(min_length=1)
    numpy_version: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    machine: str


class AccelerationBenchmarkReport(BaseModel):
    """Self-limiting report for the isolated P4-WP07 feasibility path."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1] = 1
    benchmark_api_version: Literal[1] = 1
    benchmark_kind: Literal["P4-WP07 experimental acceleration feasibility"] = (
        "P4-WP07 experimental acceleration feasibility"
    )
    experimental_default_enabled: Literal[False] = False
    experimental_requested: bool
    experimental_status: Literal["DISABLED", "MEASURED"]
    case: BenchmarkCase
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    environment: BenchmarkEnvironment
    cpu_reference: BackendObservation
    experimental_candidate: BackendObservation | None
    divergence: DivergenceMeasurement | None
    passed: bool
    limitations: list[str]

    @model_validator(mode="after")
    def validate_experimental_state(self) -> Self:
        measured = self.experimental_status == "MEASURED"
        if self.experimental_requested != measured:
            raise ValueError("experimental status does not match explicit request")
        if measured != (self.experimental_candidate is not None):
            raise ValueError("experimental candidate presence does not match status")
        if measured != (self.divergence is not None):
            raise ValueError("divergence presence does not match status")
        expected_passed = self.divergence is None or self.divergence.equivalent
        if self.passed != expected_passed:
            raise ValueError("passed does not match measured equivalence")
        if not self.limitations:
            raise ValueError("benchmark limitations must remain explicit")
        return self


class BenchmarkBackend(Protocol):
    """Narrow execution interface reserved for later reviewed backends."""

    @property
    def descriptor(self) -> BackendDescriptor: ...

    def execute(
        self, case: BenchmarkCase, initial: NDArray[np.float64]
    ) -> NDArray[np.float64]: ...


__all__ = [
    "BENCHMARK_API_VERSION",
    "AccelerationBenchmarkReport",
    "BackendDescriptor",
    "BackendObservation",
    "BenchmarkBackend",
    "BenchmarkCase",
    "BenchmarkEnvironment",
    "BenchmarkError",
    "DivergenceMeasurement",
]
