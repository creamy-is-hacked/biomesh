"""Focused P4-WP07 benchmark-boundary and application-path tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from biomesh.__main__ import main
from biomesh.acceleration_benchmark import (
    BENCHMARK_REPORT_FILE,
    BackendDescriptor,
    BenchmarkCase,
    BenchmarkError,
    publish_acceleration_benchmark,
    run_acceleration_benchmark,
)


@dataclass
class _ProbeBackend:
    descriptor: BackendDescriptor
    calls: int = 0
    offset: float = 0.0

    def execute(
        self, case: BenchmarkCase, initial: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        self.calls += 1
        result = initial.copy()
        result[1:-1, 1:-1] += self.offset
        return result


def _probe_backend(*, offset: float = 0.0) -> _ProbeBackend:
    return _ProbeBackend(
        descriptor=BackendDescriptor(
            backend_id="test-experimental",
            implementation="focused test probe",
            experimental=True,
        ),
        offset=offset,
    )


def test_experimental_candidate_is_disabled_by_default_and_not_called() -> None:
    candidate = _probe_backend()

    report = run_acceleration_benchmark(experimental_backend=candidate)

    assert candidate.calls == 0
    assert report.experimental_default_enabled is False
    assert report.experimental_requested is False
    assert report.experimental_status == "DISABLED"
    assert report.experimental_candidate is None
    assert report.divergence is None
    assert report.passed is True
    assert len(report.input_sha256) == 64
    assert report.environment.biomesh_version
    assert report.environment.python_version.startswith("3.14.")
    assert report.environment.numpy_version
    assert report.cpu_reference.backend.experimental is False
    assert report.cpu_reference.backend.gpu_used is False


def test_opt_in_numpy_cpu_candidate_measures_equivalence_and_divergence() -> None:
    report = run_acceleration_benchmark(enable_experimental=True)

    assert report.experimental_status == "MEASURED"
    assert report.experimental_candidate is not None
    assert report.experimental_candidate.backend.backend_id == (
        "numpy-cpu-experimental"
    )
    assert report.experimental_candidate.backend.processor_kind == "CPU"
    assert report.experimental_candidate.backend.dimensionality == "2D"
    assert report.experimental_candidate.backend.gpu_used is False
    assert report.divergence is not None
    assert report.divergence.value_count == 48 * 48
    assert report.divergence.mismatched_value_count == 0
    assert report.divergence.equivalent is True
    assert report.passed is True
    assert any("no GPU" in limitation for limitation in report.limitations)
    assert any("performance claim" in limitation for limitation in report.limitations)


def test_non_equivalent_candidate_fails_without_hiding_divergence() -> None:
    candidate = _probe_backend(offset=1.0e-4)

    report = run_acceleration_benchmark(
        enable_experimental=True,
        case=BenchmarkCase(rows=3, columns=3, steps=1),
        experimental_backend=candidate,
    )

    assert candidate.calls == 1
    assert report.divergence is not None
    assert report.divergence.equivalent is False
    assert report.divergence.mismatched_value_count > 0
    assert report.divergence.maximum_absolute_divergence > 0.0
    assert report.passed is False


def test_timing_is_opt_in_raw_observation_without_ratio_or_claim() -> None:
    clock_values = iter((10, 14, 20, 29))
    report = run_acceleration_benchmark(
        timing_samples=2,
        case=BenchmarkCase(rows=3, columns=3, steps=1),
        clock_ns=lambda: next(clock_values),
    )

    assert report.cpu_reference.elapsed_ns == [4, 9]
    assert report.cpu_reference.performance_status == "RAW_OBSERVATIONS_ONLY"
    dumped = report.model_dump(mode="json")
    assert "speedup" not in json.dumps(dumped).lower()
    assert any("without warm-up" in item for item in report.limitations)


def test_invalid_backend_output_and_timing_request_fail_explicitly() -> None:
    candidate = _probe_backend()

    with pytest.raises(BenchmarkError, match="between 0 and 100"):
        run_acceleration_benchmark(timing_samples=101)
    with pytest.raises(BenchmarkError, match="experimental=true"):
        candidate.descriptor = candidate.descriptor.model_copy(
            update={"experimental": False}
        )
        run_acceleration_benchmark(
            enable_experimental=True,
            experimental_backend=candidate,
        )
    candidate.descriptor = candidate.descriptor.model_copy(
        update={"experimental": True, "dimensionality": "3D"}
    )
    with pytest.raises(BenchmarkError, match="requires a 2D backend"):
        run_acceleration_benchmark(
            enable_experimental=True,
            experimental_backend=candidate,
        )


def test_benchmark_artifact_publication_is_atomic_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    output = tmp_path / "benchmark"

    report = publish_acceleration_benchmark(output, enable_experimental=True)

    artifact = output / BENCHMARK_REPORT_FILE
    assert json.loads(artifact.read_text()) == report.model_dump(mode="json")
    with pytest.raises(BenchmarkError, match="already exists"):
        publish_acceleration_benchmark(output)


def test_benchmark_cli_default_experimental_and_artifact_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["benchmark", "acceleration"]) == 0
    disabled = json.loads(capsys.readouterr().out)
    assert disabled["experimental_status"] == "DISABLED"
    assert disabled["experimental_candidate"] is None

    assert main(["benchmark", "acceleration", "--experimental"]) == 0
    measured = json.loads(capsys.readouterr().out)
    assert measured["experimental_status"] == "MEASURED"
    assert measured["divergence"]["equivalent"] is True

    output = tmp_path / "cli-artifact"
    assert (
        main(
            [
                "benchmark",
                "acceleration",
                "--experimental",
                "--timing-samples",
                "1",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    published = json.loads(capsys.readouterr().out)
    assert published == json.loads((output / BENCHMARK_REPORT_FILE).read_text())
    assert published["cpu_reference"]["elapsed_ns"]
    assert published["experimental_candidate"]["elapsed_ns"]

    assert main(["benchmark", "acceleration", "--timing-samples", "-1"]) == 2
    assert "timing_samples" in capsys.readouterr().err
