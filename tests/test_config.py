"""P1-WP01 parameter-file validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from biomesh.config import (
    BiologicalParameter,
    ParameterSet,
    ParameterValidationError,
    load_parameter_file,
)

PARAMETER_FILE = Path("parameters/p1_core_model.toml")


def test_parameter_file_loads_required_provenance_records() -> None:
    """The shipped P1 parameter file keeps all unknown values explicit."""
    parameters = load_parameter_file(PARAMETER_FILE)

    assert parameters.schema_version == 1
    assert len(parameters.biological_parameters) == 15
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
            "cell_radius",
            "maximum_permitted_cell_overlap",
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


def test_known_p1_parameter_rejects_non_si_unit() -> None:
    """Known P1 quantities cannot enter the model under an inconsistent unit."""
    with pytest.raises(ValueError, match="P1 SI unit"):
        BiologicalParameter(
            name="death_rate",
            value=1.0,
            unit="hours",
            source="synthetic validation input",
            uncertainty="not applicable to synthetic validation",
            notes="Not a biological value.",
            calibration_status="DERIVED",
        )


def test_known_p1_parameter_rejects_nonphysical_numeric_value() -> None:
    """Config validation rejects invalid values before component construction."""
    with pytest.raises(ValueError, match="greater than zero"):
        BiologicalParameter(
            name="effective_oxygen_diffusivity",
            value=-1.0,
            unit="m^2 s^-1",
            source="synthetic validation input",
            uncertainty="not applicable to synthetic validation",
            notes="Not a biological value.",
            calibration_status="DERIVED",
        )


def test_incomplete_p1_parameter_manifest_fails_explicitly() -> None:
    """A partial manifest cannot silently stand in for a runnable P1 config."""
    parameter = BiologicalParameter(
        name="death_rate",
        value="CALIBRATION_REQUIRED",
        unit="s^-1",
        source="CALIBRATION_REQUIRED",
        uncertainty="CALIBRATION_REQUIRED",
        notes="No value is approved.",
        calibration_status="CALIBRATION_REQUIRED",
    )

    with pytest.raises(ValueError, match="missing required P1"):
        ParameterSet(schema_version=1, biological_parameters=[parameter])
