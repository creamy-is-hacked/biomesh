"""P1-WP07 calibration-placeholder reference and reproduction tests."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from biomesh.reference import reproduce_reference, run_reference

REFERENCE_FILE = Path("parameters/phase1_reference.toml")


def test_reference_preserves_calibration_gate_and_records_full_provenance(
    tmp_path: Path,
) -> None:
    paths = run_reference(
        parameter_file=REFERENCE_FILE,
        output_directory=tmp_path / "run",
        repository_root=Path.cwd(),
    )

    metadata = json.loads(paths.metadata_file.read_text(encoding="utf-8"))
    assert metadata["seed"] == 42
    assert metadata["parameter_file"] == "parameters/phase1_reference.toml"
    assert metadata["dependency_versions"]
    assert metadata["platform"]
    assert metadata["python_version"]
    assert metadata["parameters"]["run_classification"] == (
        "CALIBRATION_REQUIRED_NON_SCIENTIFIC_REFERENCE"
    )
    assert {
        parameter["value"]
        for parameter in metadata["parameters"]["biological_manifest"][
            "biological_parameters"
        ]
    } == {"CALIBRATION_REQUIRED"}
    assert pq.read_table(paths.cells_table).num_rows == 0
    assert (paths.run_directory / "reference_parameters.toml").is_file()
    assert (paths.run_directory / "biological_parameters.toml").is_file()


def test_metadata_driven_reference_reproduction_has_no_mismatches(
    tmp_path: Path,
) -> None:
    paths = run_reference(
        parameter_file=REFERENCE_FILE,
        output_directory=tmp_path / "run",
        repository_root=Path.cwd(),
    )

    assert reproduce_reference(
        run_directory=paths.run_directory,
        repository_root=Path.cwd(),
    ) == ()
