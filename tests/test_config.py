"""P1-WP01 parameter-file validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from biomesh.config import (
    BiologicalParameter,
    EPSParameterSet,
    ParameterSet,
    ParameterValidationError,
    QuorumParameterSet,
    load_eps_parameter_file,
    load_parameter_file,
    load_quorum_parameter_file,
)

PARAMETER_FILE = Path("parameters/p1_core_model.toml")
QUORUM_PARAMETER_FILE = Path("parameters/p2_quorum_signal.toml")
EPS_PARAMETER_FILE = Path("parameters/p2_eps_model.toml")


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
    with pytest.raises(ValueError, match="required SI unit"):
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


def test_quorum_parameter_file_loads_complete_unknown_inventory() -> None:
    """P2-WP01 inputs remain isolated, complete, and explicitly uncalibrated."""
    parameters = load_quorum_parameter_file(QUORUM_PARAMETER_FILE)

    assert parameters.schema_version == 1
    assert len(parameters.biological_parameters) == 7
    assert {parameter.name for parameter in parameters.biological_parameters} == {
        "effective_quorum_signal_diffusivity",
        "quorum_signal_top_bulk_concentration",
        "quorum_signal_degradation_rate",
        "basal_quorum_signal_production_rate",
        "induced_quorum_signal_production_rate",
        "quorum_activation_half_saturation_constant",
        "quorum_hill_coefficient",
    }
    assert {
        parameter.value for parameter in parameters.biological_parameters
    } == {"CALIBRATION_REQUIRED"}


def test_incomplete_quorum_parameter_manifest_fails_explicitly() -> None:
    """A partial P2-WP01 manifest cannot silently configure the mechanism."""
    parameter = BiologicalParameter(
        name="quorum_signal_degradation_rate",
        value="CALIBRATION_REQUIRED",
        unit="s^-1",
        source="CALIBRATION_REQUIRED",
        uncertainty="CALIBRATION_REQUIRED",
        notes="No value is approved.",
        calibration_status="CALIBRATION_REQUIRED",
    )

    with pytest.raises(ValueError, match="missing required P2-WP01"):
        QuorumParameterSet(schema_version=1, biological_parameters=[parameter])


def test_quorum_parameter_rejects_non_si_unit_and_negative_rate() -> None:
    """P2-WP01 parameters use their canonical SI units and physical domains."""
    with pytest.raises(ValueError, match="required SI unit"):
        BiologicalParameter(
            name="quorum_signal_degradation_rate",
            value=1.0,
            unit="h^-1",
            source="synthetic validation input",
            uncertainty="not applicable to synthetic validation",
            notes="Not a biological value.",
            calibration_status="DERIVED",
        )
    with pytest.raises(ValueError, match="greater than or equal to zero"):
        BiologicalParameter(
            name="basal_quorum_signal_production_rate",
            value=-1.0,
            unit="mol s^-1",
            source="synthetic validation input",
            uncertainty="not applicable to synthetic validation",
            notes="Not a biological value.",
            calibration_status="DERIVED",
        )


def test_eps_parameter_file_loads_complete_unknown_inventory() -> None:
    """P2-WP02 inputs remain isolated, complete, and uncalibrated."""
    parameters = load_eps_parameter_file(EPS_PARAMETER_FILE)

    assert parameters.schema_version == 1
    assert len(parameters.biological_parameters) == 3
    assert {parameter.name for parameter in parameters.biological_parameters} == {
        "maximum_eps_allocation_fraction",
        "eps_cohesion_sensitivity",
        "eps_attachment_strength_sensitivity",
    }
    assert {
        parameter.value for parameter in parameters.biological_parameters
    } == {"CALIBRATION_REQUIRED"}


def test_incomplete_eps_parameter_manifest_fails_explicitly() -> None:
    """A partial P2-WP02 manifest cannot silently configure the mechanism."""
    parameter = BiologicalParameter(
        name="maximum_eps_allocation_fraction",
        value="CALIBRATION_REQUIRED",
        unit="1",
        source="CALIBRATION_REQUIRED",
        uncertainty="CALIBRATION_REQUIRED",
        notes="No value is approved.",
        calibration_status="CALIBRATION_REQUIRED",
    )

    with pytest.raises(ValueError, match="missing required P2-WP02"):
        EPSParameterSet(schema_version=1, biological_parameters=[parameter])


def test_eps_parameter_rejects_non_si_unit_and_invalid_fraction() -> None:
    """P2-WP02 parameters enforce canonical SI units and physical domains."""
    with pytest.raises(ValueError, match="required SI unit"):
        BiologicalParameter(
            name="eps_cohesion_sensitivity",
            value=1.0,
            unit="kg m^-3",
            source="synthetic validation input",
            uncertainty="not applicable to synthetic validation",
            notes="Not a biological value.",
            calibration_status="DERIVED",
        )
    with pytest.raises(ValueError, match=r"within \[0, 1\]"):
        BiologicalParameter(
            name="maximum_eps_allocation_fraction",
            value=1.1,
            unit="1",
            source="synthetic validation input",
            uncertainty="not applicable to synthetic validation",
            notes="Not a biological value.",
            calibration_status="DERIVED",
        )
