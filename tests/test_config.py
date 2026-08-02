"""P1-WP01 parameter-file validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from biomesh.config import ParameterValidationError, load_parameter_file

PARAMETER_FILE = Path("parameters/p1_core_model.toml")


def test_parameter_file_loads_required_provenance_records() -> None:
    """The shipped P1 parameter file keeps all unknown values explicit."""
    parameters = load_parameter_file(PARAMETER_FILE)

    assert parameters.schema_version == 1
    assert len(parameters.biological_parameters) == 13
    assert {
        parameter.name for parameter in parameters.biological_parameters
    }.issuperset(
        {
            "maximum_specific_growth_rate",
            "carbon_half_saturation_constant",
            "oxygen_half_saturation_constant",
            "death_rate",
            "biomass_yield_on_carbon",
            "biomass_yield_on_oxygen",
        }
    )
    assert {
        parameter.value for parameter in parameters.biological_parameters
    } == {"CALIBRATION_REQUIRED"}
    assert all(parameter.unit for parameter in parameters.biological_parameters)
    assert all(parameter.source for parameter in parameters.biological_parameters)
    assert all(parameter.uncertainty for parameter in parameters.biological_parameters)
    assert all(parameter.notes for parameter in parameters.biological_parameters)


def test_missing_provenance_field_fails_with_clear_error(tmp_path: Path) -> None:
    """Every biological parameter must include the required source metadata."""
    parameter_file = tmp_path / "missing-source.toml"
    parameter_file.write_text(
        """\
schema_version = 1
[[biological_parameters]]
name = "example"
value = "CALIBRATION_REQUIRED"
unit = "s^-1"
uncertainty = "CALIBRATION_REQUIRED"
notes = "example record"
calibration_status = "CALIBRATION_REQUIRED"
"""
    )

    with pytest.raises(ParameterValidationError, match="source"):
        load_parameter_file(parameter_file)


def test_unknown_value_rejects_non_placeholder_provenance(tmp_path: Path) -> None:
    """Unknown values cannot be paired with invented provenance."""
    parameter_file = tmp_path / "invalid-unknown.toml"
    parameter_file.write_text(
        """\
schema_version = 1
[[biological_parameters]]
name = "example"
value = "CALIBRATION_REQUIRED"
unit = "s^-1"
source = "Example citation"
uncertainty = "CALIBRATION_REQUIRED"
notes = "example record"
calibration_status = "CALIBRATION_REQUIRED"
"""
    )

    with pytest.raises(
        ParameterValidationError,
        match="source must be CALIBRATION_REQUIRED",
    ):
        load_parameter_file(parameter_file)


def test_malformed_toml_fails_with_clear_error(tmp_path: Path) -> None:
    """Syntax failures are reported at the file-validation boundary."""
    parameter_file = tmp_path / "malformed.toml"
    parameter_file.write_text("schema_version = [")

    with pytest.raises(ParameterValidationError, match="invalid TOML"):
        load_parameter_file(parameter_file)
