"""Isolated P4-WP07 benchmark and experimental acceleration boundary.

This module is not imported by the accepted simulation, campaign, plugin,
registry, queue, archive, or desktop execution paths.  Its NumPy candidate is
an explicitly enabled CPU-only software feasibility probe, not a model backend.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform as platform_module
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from biomesh import __version__
from biomesh.acceleration_benchmark_types import (
    BENCHMARK_API_VERSION,
    AccelerationBenchmarkReport,
    BackendDescriptor,
    BackendObservation,
    BenchmarkBackend,
    BenchmarkCase,
    BenchmarkEnvironment,
    BenchmarkError,
    DivergenceMeasurement,
)

BENCHMARK_REPORT_FILE = "acceleration_benchmark.json"

_REPORT_LIMITATIONS = (
    "The workload is a synthetic dimensionless 2D software stencil; it is not "
    "a BioMesh scientific model, 3D implementation, or biological result.",
    "The optional candidate uses NumPy on the CPU only; no GPU is detected, "
    "selected, exercised, validated, or claimed.",
    "Equivalence applies only to this declared case and engineering tolerance; "
    "it does not validate accuracy for any scientific simulation.",
    "Elapsed times, when requested, are raw local observations without warm-up, "
    "environment control, statistical inference, comparison ratio, or "
    "performance claim.",
)


class CpuReferenceBackend:
    """Scalar-loop CPU reference for the synthetic fixed-edge stencil."""

    descriptor = BackendDescriptor(
        backend_id="cpu-reference",
        implementation="Python scalar loop over a NumPy float64 array",
        experimental=False,
    )

    def execute(
        self, case: BenchmarkCase, initial: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        state = initial.copy()
        for _ in range(case.steps):
            updated = state.copy()
            for row in range(1, case.rows - 1):
                for column in range(1, case.columns - 1):
                    updated[row, column] = 0.5 * state[row, column] + 0.125 * (
                        state[row - 1, column]
                        + state[row + 1, column]
                        + state[row, column - 1]
                        + state[row, column + 1]
                    )
            state = updated
        return state


class NumpyExperimentalBackend:
    """Opt-in CPU vectorization feasibility candidate; never a model backend."""

    descriptor = BackendDescriptor(
        backend_id="numpy-cpu-experimental",
        implementation="NumPy float64 slice operations on the CPU",
        experimental=True,
    )

    def execute(
        self, case: BenchmarkCase, initial: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        state = initial.copy()
        for _ in range(case.steps):
            updated = state.copy()
            updated[1:-1, 1:-1] = 0.5 * state[1:-1, 1:-1] + 0.125 * (
                state[:-2, 1:-1]
                + state[2:, 1:-1]
                + state[1:-1, :-2]
                + state[1:-1, 2:]
            )
            state = updated
        return state


def run_acceleration_benchmark(
    *,
    enable_experimental: bool = False,
    timing_samples: int = 0,
    case: BenchmarkCase | None = None,
    experimental_backend: BenchmarkBackend | None = None,
    clock_ns: Callable[[], int] = time.perf_counter_ns,
) -> AccelerationBenchmarkReport:
    """Run the CPU reference and, only when explicit, the isolated candidate."""
    if isinstance(timing_samples, bool) or not isinstance(timing_samples, int):
        raise BenchmarkError("timing_samples must be an integer")
    if timing_samples < 0 or timing_samples > 100:
        raise BenchmarkError("timing_samples must be between 0 and 100")
    selected_case = BenchmarkCase() if case is None else case
    initial = _initial_field(selected_case)
    input_sha256 = _array_sha256(initial)
    environment = _benchmark_environment()
    reference_array, reference = _observe_backend(
        CpuReferenceBackend(), selected_case, initial, timing_samples, clock_ns
    )
    if not enable_experimental:
        return AccelerationBenchmarkReport(
            experimental_requested=False,
            experimental_status="DISABLED",
            case=selected_case,
            input_sha256=input_sha256,
            environment=environment,
            cpu_reference=reference,
            experimental_candidate=None,
            divergence=None,
            passed=True,
            limitations=list(_REPORT_LIMITATIONS),
        )

    candidate_backend = experimental_backend or NumpyExperimentalBackend()
    if not candidate_backend.descriptor.experimental:
        raise BenchmarkError("experimental backend must declare experimental=true")
    if candidate_backend.descriptor.dimensionality != "2D":
        raise BenchmarkError("the P4-WP07 fixed case requires a 2D backend")
    candidate_array, candidate = _observe_backend(
        candidate_backend, selected_case, initial, timing_samples, clock_ns
    )
    divergence = _measure_divergence(
        reference_array, candidate_array, selected_case
    )
    return AccelerationBenchmarkReport(
        experimental_requested=True,
        experimental_status="MEASURED",
        case=selected_case,
        input_sha256=input_sha256,
        environment=environment,
        cpu_reference=reference,
        experimental_candidate=candidate,
        divergence=divergence,
        passed=divergence.equivalent,
        limitations=list(_REPORT_LIMITATIONS),
    )


def publish_acceleration_benchmark(
    output: Path,
    *,
    enable_experimental: bool = False,
    timing_samples: int = 0,
) -> AccelerationBenchmarkReport:
    """Atomically publish one new benchmark artifact directory."""
    if output.exists() or output.is_symlink():
        raise BenchmarkError(f"benchmark output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise BenchmarkError("benchmark output parent must be a real directory")
    report = run_acceleration_benchmark(
        enable_experimental=enable_experimental,
        timing_samples=timing_samples,
    )
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        report_bytes = (
            json.dumps(
                report.model_dump(mode="json"),
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode()
        (staging / BENCHMARK_REPORT_FILE).write_bytes(report_bytes)
        os.replace(staging, output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return report


def _initial_field(case: BenchmarkCase) -> NDArray[np.float64]:
    indices = np.arange(case.rows * case.columns, dtype=np.float64)
    return ((indices % 97.0) / 97.0).reshape(case.rows, case.columns)


def _observe_backend(
    backend: BenchmarkBackend,
    case: BenchmarkCase,
    initial: NDArray[np.float64],
    timing_samples: int,
    clock_ns: Callable[[], int],
) -> tuple[NDArray[np.float64], BackendObservation]:
    result = _validated_result(backend.execute(case, initial), case, backend)
    elapsed: list[int] = []
    for _ in range(timing_samples):
        started = clock_ns()
        repeated = _validated_result(backend.execute(case, initial), case, backend)
        finished = clock_ns()
        if not np.array_equal(repeated, result):
            raise BenchmarkError(
                f"backend {backend.descriptor.backend_id} is not deterministic"
            )
        duration = finished - started
        if duration < 0:
            raise BenchmarkError("benchmark clock moved backwards")
        elapsed.append(duration)
    return result, BackendObservation(
        backend=backend.descriptor,
        result_sha256=_array_sha256(result),
        value_count=result.size,
        elapsed_ns=elapsed,
        performance_status=(
            "RAW_OBSERVATIONS_ONLY" if elapsed else "NOT_MEASURED"
        ),
    )


def _validated_result(
    result: NDArray[np.float64],
    case: BenchmarkCase,
    backend: BenchmarkBackend,
) -> NDArray[np.float64]:
    if not isinstance(result, np.ndarray):
        raise BenchmarkError(
            f"backend {backend.descriptor.backend_id} did not return an ndarray"
        )
    if result.shape != (case.rows, case.columns):
        raise BenchmarkError(
            f"backend {backend.descriptor.backend_id} returned shape {result.shape}; "
            f"expected {(case.rows, case.columns)}"
        )
    if result.dtype != np.dtype(np.float64):
        raise BenchmarkError(
            f"backend {backend.descriptor.backend_id} must return float64"
        )
    if not np.isfinite(result).all():
        raise BenchmarkError(
            f"backend {backend.descriptor.backend_id} returned non-finite values"
        )
    return result.copy()


def _measure_divergence(
    reference: NDArray[np.float64],
    candidate: NDArray[np.float64],
    case: BenchmarkCase,
) -> DivergenceMeasurement:
    absolute = np.abs(candidate - reference)
    nonzero_reference = np.abs(reference) > 0.0
    relative = np.zeros_like(absolute)
    np.divide(
        absolute,
        np.abs(reference),
        out=relative,
        where=nonzero_reference,
    )
    undefined_relative = bool(
        np.any((~nonzero_reference) & (absolute > 0.0))
    )
    matches = np.isclose(
        candidate,
        reference,
        rtol=case.relative_tolerance,
        atol=case.absolute_tolerance,
        equal_nan=False,
    )
    return DivergenceMeasurement(
        absolute_tolerance=case.absolute_tolerance,
        relative_tolerance=case.relative_tolerance,
        maximum_absolute_divergence=float(np.max(absolute)),
        maximum_relative_divergence=(
            None if undefined_relative else float(np.max(relative))
        ),
        mean_absolute_divergence=float(np.mean(absolute)),
        mismatched_value_count=int(matches.size - np.count_nonzero(matches)),
        value_count=matches.size,
        equivalent=bool(np.all(matches)),
    )


def _array_sha256(array: NDArray[np.float64]) -> str:
    portable = np.ascontiguousarray(array, dtype=np.dtype("<f8"))
    return hashlib.sha256(portable.tobytes(order="C")).hexdigest()


def _benchmark_environment() -> BenchmarkEnvironment:
    return BenchmarkEnvironment(
        biomesh_version=__version__,
        python_version=platform_module.python_version(),
        numpy_version=np.__version__,
        platform=platform_module.platform(),
        machine=platform_module.machine(),
    )


__all__ = [
    "BENCHMARK_API_VERSION",
    "BENCHMARK_REPORT_FILE",
    "AccelerationBenchmarkReport",
    "BackendDescriptor",
    "BackendObservation",
    "BenchmarkBackend",
    "BenchmarkCase",
    "BenchmarkEnvironment",
    "BenchmarkError",
    "CpuReferenceBackend",
    "DivergenceMeasurement",
    "NumpyExperimentalBackend",
    "publish_acceleration_benchmark",
    "run_acceleration_benchmark",
]
