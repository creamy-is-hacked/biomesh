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

        return self


class ParameterSet(BaseModel):
    """The versioned, structured parameter document used by P1 components."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    biological_parameters: list[BiologicalParameter] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_parameter_names(self) -> Self:
        """Reject duplicate records rather than choosing one implicitly."""
        names = [parameter.name for parameter in self.biological_parameters]
        if len(names) != len(set(names)):
            raise ValueError("biological parameter names must be unique")
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
