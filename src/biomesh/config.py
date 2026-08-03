"""Validated loading for completed biological-parameter work packages."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    AllowInfNan,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

CalibrationStatus = Literal[
    "MEASURED", "DERIVED", "CALIBRATED", "CALIBRATION_REQUIRED"
]
CalibrationRequired = Literal["CALIBRATION_REQUIRED"]
NonBlankText = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
FiniteValue = Annotated[float, AllowInfNan(allow_inf_nan=False)]
ParameterValue = FiniteValue | CalibrationRequired

_P1_PARAMETER_UNITS: dict[str, str] = {
    "maximum_specific_growth_rate": "s^-1",
    "carbon_half_saturation_constant": "mol m^-3",
    "oxygen_half_saturation_constant": "mol m^-3",
    "death_rate": "s^-1",
    "biomass_yield_on_carbon": "kg mol^-1",
    "biomass_yield_on_oxygen": "kg mol^-1",
    "effective_carbon_diffusivity": "m^2 s^-1",
    "effective_oxygen_diffusivity": "m^2 s^-1",
    "carbon_bulk_concentration": "mol m^-3",
    "oxygen_bulk_concentration": "mol m^-3",
    "dry_biomass_per_unit_length": "kg m^-1",
    "cell_radius": "m",
    "division_length": "m",
    "maximum_daughter_asymmetry_fraction": "1",
    "maximum_permitted_cell_overlap": "m",
}
_P2_WP01_PARAMETER_UNITS: dict[str, str] = {
    "effective_quorum_signal_diffusivity": "m^2 s^-1",
    "quorum_signal_top_bulk_concentration": "mol m^-3",
    "quorum_signal_degradation_rate": "s^-1",
    "basal_quorum_signal_production_rate": "mol s^-1",
    "induced_quorum_signal_production_rate": "mol s^-1",
    "quorum_activation_half_saturation_constant": "mol m^-3",
    "quorum_hill_coefficient": "1",
}
_P2_WP02_PARAMETER_UNITS: dict[str, str] = {
    "maximum_eps_allocation_fraction": "1",
    "eps_cohesion_sensitivity": "m^3 kg^-1",
    "eps_attachment_strength_sensitivity": "m^3 kg^-1",
}
_P2_WP04_PARAMETER_UNITS: dict[str, str] = {
    "carbon_slow_threshold": "mol m^-3",
    "oxygen_slow_threshold": "mol m^-3",
    "carbon_dormancy_threshold": "mol m^-3",
    "oxygen_dormancy_threshold": "mol m^-3",
    "carbon_death_threshold": "mol m^-3",
    "oxygen_death_threshold": "mol m^-3",
    "slow_transition_delay": "s",
    "dormancy_transition_delay": "s",
    "death_transition_delay": "s",
    "recovery_transition_delay": "s",
    "slow_metabolic_activity_fraction": "1",
    "dormant_metabolic_activity_fraction": "1",
    "dead_biomass_recycling_rate": "s^-1",
}
_KNOWN_PARAMETER_UNITS = (
    _P1_PARAMETER_UNITS
    | _P2_WP01_PARAMETER_UNITS
    | _P2_WP02_PARAMETER_UNITS
    | _P2_WP04_PARAMETER_UNITS
)
_NONNEGATIVE_PARAMETERS = {
    "death_rate",
    "carbon_bulk_concentration",
    "oxygen_bulk_concentration",
    "maximum_permitted_cell_overlap",
    "quorum_signal_top_bulk_concentration",
    "quorum_signal_degradation_rate",
    "basal_quorum_signal_production_rate",
    "induced_quorum_signal_production_rate",
    "eps_cohesion_sensitivity",
    "eps_attachment_strength_sensitivity",
    *_P2_WP04_PARAMETER_UNITS,
}


class ParameterValidationError(ValueError):
    """Raised when a parameter file does not meet the provenance contract."""


class BiologicalParameter(BaseModel):
    """One biological parameter and the provenance needed to use it."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: NonBlankText
    value: ParameterValue
    unit: NonBlankText
    source: NonBlankText
    uncertainty: NonBlankText
    notes: NonBlankText
    calibration_status: CalibrationStatus

    @model_validator(mode="after")
    def validate_calibration_record(self) -> Self:
        """Keep unknown values explicit and prevent unsupported numeric values."""
        expected_unit = _KNOWN_PARAMETER_UNITS.get(self.name)
        if expected_unit is not None and self.unit != expected_unit:
            raise ValueError(
                f"unit for {self.name} must be the required SI unit {expected_unit!r}"
            )
        if self.value == "CALIBRATION_REQUIRED":
            if self.source != "CALIBRATION_REQUIRED":
                raise ValueError(
                    "source must be CALIBRATION_REQUIRED when value is unknown"
                )
            if self.uncertainty != "CALIBRATION_REQUIRED":
                raise ValueError(
                    "uncertainty must be CALIBRATION_REQUIRED when value is unknown"
                )
            if self.calibration_status != "CALIBRATION_REQUIRED":
                raise ValueError(
                    "calibration_status must be CALIBRATION_REQUIRED when value is "
                    "unknown"
                )
        elif self.source == "CALIBRATION_REQUIRED":
            raise ValueError("numeric values require a non-placeholder source")
        elif self.name == "maximum_daughter_asymmetry_fraction":
            if not 0.0 <= self.value < 0.5:
                raise ValueError(
                    "maximum_daughter_asymmetry_fraction must be within [0, 0.5)"
                )
        elif self.name == "maximum_eps_allocation_fraction":
            if not 0.0 <= self.value <= 1.0:
                raise ValueError(
                    "maximum_eps_allocation_fraction must be within [0, 1]"
                )
        elif self.name in {
            "slow_metabolic_activity_fraction",
            "dormant_metabolic_activity_fraction",
        }:
            if not 0.0 <= self.value <= 1.0:
                raise ValueError(f"{self.name} must be within [0, 1]")
        elif self.name in _NONNEGATIVE_PARAMETERS:
            if self.value < 0.0:
                raise ValueError(f"{self.name} must be greater than or equal to zero")
        elif expected_unit is not None and self.value <= 0.0:
            raise ValueError(f"{self.name} must be greater than zero")

        return self


class ParameterSet(BaseModel):
    """The versioned, structured parameter document used by P1 components."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    biological_parameters: list[BiologicalParameter] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_parameter_names(self) -> Self:
        """Reject duplicate or incomplete P1 parameter manifests."""
        names = [parameter.name for parameter in self.biological_parameters]
        if len(names) != len(set(names)):
            raise ValueError("biological parameter names must be unique")
        missing = sorted(set(_P1_PARAMETER_UNITS) - set(names))
        if missing:
            raise ValueError(
                "missing required P1 biological parameters: " + ", ".join(missing)
            )
        return self


class QuorumParameterSet(BaseModel):
    """The versioned P2-WP01 quorum biological-parameter document."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    biological_parameters: list[BiologicalParameter] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_quorum_parameter_names(self) -> Self:
        """Reject duplicate or incomplete P2-WP01 parameter manifests."""
        names = [parameter.name for parameter in self.biological_parameters]
        if len(names) != len(set(names)):
            raise ValueError("biological parameter names must be unique")
        unexpected = sorted(set(names) - set(_P2_WP01_PARAMETER_UNITS))
        if unexpected:
            raise ValueError(
                "unexpected P2-WP01 biological parameters: "
                + ", ".join(unexpected)
            )
        missing = sorted(set(_P2_WP01_PARAMETER_UNITS) - set(names))
        if missing:
            raise ValueError(
                "missing required P2-WP01 biological parameters: "
                + ", ".join(missing)
            )
        return self


class EPSParameterSet(BaseModel):
    """The versioned P2-WP02 EPS biological-parameter document."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    biological_parameters: list[BiologicalParameter] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_eps_parameter_names(self) -> Self:
        """Reject duplicate or incomplete P2-WP02 parameter manifests."""
        names = [parameter.name for parameter in self.biological_parameters]
        if len(names) != len(set(names)):
            raise ValueError("biological parameter names must be unique")
        unexpected = sorted(set(names) - set(_P2_WP02_PARAMETER_UNITS))
        if unexpected:
            raise ValueError(
                "unexpected P2-WP02 biological parameters: "
                + ", ".join(unexpected)
            )
        missing = sorted(set(_P2_WP02_PARAMETER_UNITS) - set(names))
        if missing:
            raise ValueError(
                "missing required P2-WP02 biological parameters: "
                + ", ".join(missing)
            )
        return self


class PhysiologyParameterSet(BaseModel):
    """The versioned P2-WP04 physiological biological-parameter document."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    biological_parameters: list[BiologicalParameter] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_physiology_parameter_names(self) -> Self:
        """Reject duplicate or incomplete P2-WP04 parameter manifests."""
        names = [parameter.name for parameter in self.biological_parameters]
        if len(names) != len(set(names)):
            raise ValueError("biological parameter names must be unique")
        unexpected = sorted(set(names) - set(_P2_WP04_PARAMETER_UNITS))
        if unexpected:
            raise ValueError(
                "unexpected P2-WP04 biological parameters: "
                + ", ".join(unexpected)
            )
        missing = sorted(set(_P2_WP04_PARAMETER_UNITS) - set(names))
        if missing:
            raise ValueError(
                "missing required P2-WP04 biological parameters: "
                + ", ".join(missing)
            )
        return self


def load_parameter_file(path: Path) -> ParameterSet:
    """Load and validate a TOML parameter file with an explicit error boundary."""
    try:
        with path.open("rb") as parameter_file:
            contents = tomllib.load(parameter_file)
    except OSError as error:
        message = f"unable to read parameter file {path}: {error.strerror or error}"
        raise ParameterValidationError(message) from error
    except tomllib.TOMLDecodeError as error:
        message = f"invalid TOML in parameter file {path}: {error}"
        raise ParameterValidationError(message) from error

    try:
        return ParameterSet.model_validate(contents)
    except ValidationError as error:
        message = f"invalid parameter file {path}: {error}"
        raise ParameterValidationError(message) from error


def load_quorum_parameter_file(path: Path) -> QuorumParameterSet:
    """Load and validate the isolated P2-WP01 quorum parameter document."""
    try:
        with path.open("rb") as parameter_file:
            contents = tomllib.load(parameter_file)
    except OSError as error:
        message = f"unable to read parameter file {path}: {error.strerror or error}"
        raise ParameterValidationError(message) from error
    except tomllib.TOMLDecodeError as error:
        message = f"invalid TOML in parameter file {path}: {error}"
        raise ParameterValidationError(message) from error

    try:
        return QuorumParameterSet.model_validate(contents)
    except ValidationError as error:
        message = f"invalid parameter file {path}: {error}"
        raise ParameterValidationError(message) from error


def load_eps_parameter_file(path: Path) -> EPSParameterSet:
    """Load and validate the isolated P2-WP02 EPS parameter document."""
    try:
        with path.open("rb") as parameter_file:
            contents = tomllib.load(parameter_file)
    except OSError as error:
        message = f"unable to read parameter file {path}: {error.strerror or error}"
        raise ParameterValidationError(message) from error
    except tomllib.TOMLDecodeError as error:
        message = f"invalid TOML in parameter file {path}: {error}"
        raise ParameterValidationError(message) from error

    try:
        return EPSParameterSet.model_validate(contents)
    except ValidationError as error:
        message = f"invalid parameter file {path}: {error}"
        raise ParameterValidationError(message) from error


def load_physiology_parameter_file(path: Path) -> PhysiologyParameterSet:
    """Load and validate the isolated P2-WP04 physiological parameter file."""
    try:
        with path.open("rb") as parameter_file:
            contents = tomllib.load(parameter_file)
    except OSError as error:
        message = f"unable to read parameter file {path}: {error.strerror or error}"
        raise ParameterValidationError(message) from error
    except tomllib.TOMLDecodeError as error:
        message = f"invalid TOML in parameter file {path}: {error}"
        raise ParameterValidationError(message) from error

    try:
        return PhysiologyParameterSet.model_validate(contents)
    except ValidationError as error:
        message = f"invalid parameter file {path}: {error}"
        raise ParameterValidationError(message) from error
