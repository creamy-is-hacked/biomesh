"""Validated loading for Phase 1 biological parameter records."""

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
_P1_NONNEGATIVE_PARAMETERS = {
    "death_rate",
    "carbon_bulk_concentration",
    "oxygen_bulk_concentration",
    "maximum_permitted_cell_overlap",
}


class ParameterValidationError(ValueError):
    """Raised when a parameter file does not meet the P1 provenance contract."""


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
        expected_unit = _P1_PARAMETER_UNITS.get(self.name)
        if expected_unit is not None and self.unit != expected_unit:
            raise ValueError(
                f"unit for {self.name} must be the P1 SI unit {expected_unit!r}"
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
        elif self.name in _P1_NONNEGATIVE_PARAMETERS:
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
