"""Immutable, versioned P4-WP04 model and parameter registry records."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal, Self

from pydantic import (
    AllowInfNan,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from biomesh.config import CalibrationStatus

Identifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]
NonBlankText = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
FiniteValue = Annotated[float, AllowInfNan(allow_inf_nan=False)]
RegistryValue = FiniteValue | Literal["CALIBRATION_REQUIRED"]
ParameterProvenanceKind = Literal[
    "MEASURED",
    "LITERATURE_DERIVED",
    "FITTED",
    "ASSUMED",
    "CALIBRATION_REQUIRED",
]


class RegistryCitation(BaseModel):
    """One stable citation, dataset, or internal evidence locator."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    citation_id: Identifier
    title: NonBlankText
    source: NonBlankText
    locator: NonBlankText
    notes: NonBlankText


class RegistryParameter(BaseModel):
    """One SI-explicit value with complete provenance classification."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: Identifier
    value: RegistryValue
    unit: NonBlankText
    provenance_kind: ParameterProvenanceKind
    source: NonBlankText
    citations: list[RegistryCitation] = Field(default_factory=list)
    uncertainty: NonBlankText
    notes: NonBlankText
    calibration_status: CalibrationStatus

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        citation_ids = [citation.citation_id for citation in self.citations]
        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError("parameter citation IDs must be unique")
        if citation_ids != sorted(citation_ids):
            raise ValueError("parameter citations must be sorted by citation ID")
        if self.value == "CALIBRATION_REQUIRED":
            if self.provenance_kind != "CALIBRATION_REQUIRED":
                raise ValueError(
                    "unknown values require CALIBRATION_REQUIRED provenance_kind"
                )
            if self.source != "CALIBRATION_REQUIRED":
                raise ValueError("unknown values require CALIBRATION_REQUIRED source")
            if self.uncertainty != "CALIBRATION_REQUIRED":
                raise ValueError(
                    "unknown values require CALIBRATION_REQUIRED uncertainty"
                )
            if self.calibration_status != "CALIBRATION_REQUIRED":
                raise ValueError(
                    "unknown values require CALIBRATION_REQUIRED calibration_status"
                )
            if self.citations:
                raise ValueError("unknown values cannot claim supporting citations")
        else:
            if self.provenance_kind == "CALIBRATION_REQUIRED":
                raise ValueError(
                    "numeric values require an explicit non-placeholder provenance_kind"
                )
            if self.source == "CALIBRATION_REQUIRED":
                raise ValueError("numeric values require a non-placeholder source")
            if not self.citations:
                raise ValueError("numeric values require at least one citation")
        return self


class RequiredParameter(BaseModel):
    """One exact name/unit requirement declared by a model version."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: Identifier
    unit: NonBlankText


class RequiredPlugin(BaseModel):
    """One exact reviewed plugin identity required by a model version."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    plugin_id: Identifier
    plugin_version: NonBlankText
    metadata_sha256: Sha256
    selection_sha256: Sha256
    components: list[
        Literal["species", "kinetics", "field", "metric", "exporter"]
    ] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_components(self) -> Self:
        if len(self.components) != len(set(self.components)):
            raise ValueError("required plugin components must be unique")
        if self.components != sorted(self.components):
            raise ValueError("required plugin components must be sorted")
        return self


class ModelRecord(BaseModel):
    """One named, versioned model compatibility contract."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    model_id: Identifier
    model_version: NonBlankText
    display_name: NonBlankText
    parameter_schema_id: Identifier
    required_parameters: list[RequiredParameter] = Field(min_length=1)
    plugin_api_version: Literal[1]
    required_plugins: list[RequiredPlugin] = Field(default_factory=list)
    source: NonBlankText
    compatibility_reference: NonBlankText
    calibration_status: CalibrationStatus
    limitations: list[NonBlankText] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ordering(self) -> Self:
        names = [parameter.name for parameter in self.required_parameters]
        if len(names) != len(set(names)):
            raise ValueError("model required parameter names must be unique")
        if names != sorted(names):
            raise ValueError("model required parameters must be sorted by name")
        plugin_ids = [plugin.plugin_id for plugin in self.required_plugins]
        if len(plugin_ids) != len(set(plugin_ids)):
            raise ValueError("model required plugin IDs must be unique")
        if plugin_ids != sorted(plugin_ids):
            raise ValueError("model required plugins must be sorted by plugin ID")
        if len(self.limitations) != len(set(self.limitations)):
            raise ValueError("model limitations must be unique")
        return self


class ParameterSetRecord(BaseModel):
    """One named, versioned parameter set bound to an exact model version."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    parameter_set_id: Identifier
    parameter_set_version: NonBlankText
    display_name: NonBlankText
    model_id: Identifier
    model_version: NonBlankText
    parameter_schema_id: Identifier
    audited: bool
    immutable: bool
    source: NonBlankText
    source_sha256: Sha256
    parameters: list[RegistryParameter] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("parameter set names must be unique")
        if names != sorted(names):
            raise ValueError("parameter set parameters must be sorted by name")
        if self.audited and not self.immutable:
            raise ValueError("audited parameter sets must be immutable")
        return self


class ModelEntry(BaseModel):
    """Hash-bound model record stored in a registry."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    record: ModelRecord
    record_sha256: Sha256

    @model_validator(mode="after")
    def validate_hash(self) -> Self:
        if self.record_sha256 != canonical_model_sha256(self.record):
            raise ValueError("model record_sha256 does not match record")
        return self


class ParameterSetEntry(BaseModel):
    """Hash-bound parameter-set record stored in a registry."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    record: ParameterSetRecord
    record_sha256: Sha256

    @model_validator(mode="after")
    def validate_hash(self) -> Self:
        if self.record_sha256 != canonical_parameter_set_sha256(self.record):
            raise ValueError("parameter-set record_sha256 does not match record")
        return self


class RegistryBundle(BaseModel):
    """Complete deterministic export/import document for one registry."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    source: NonBlankText
    models: list[ModelEntry] = Field(min_length=1)
    parameter_sets: list[ParameterSetEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identity_and_order(self) -> Self:
        model_keys = [
            (entry.record.model_id, entry.record.model_version)
            for entry in self.models
        ]
        set_keys = [
            (entry.record.parameter_set_id, entry.record.parameter_set_version)
            for entry in self.parameter_sets
        ]
        if len(model_keys) != len(set(model_keys)):
            raise ValueError("registry model identities must be unique")
        if len(set_keys) != len(set(set_keys)):
            raise ValueError("registry parameter-set identities must be unique")
        if model_keys != sorted(model_keys):
            raise ValueError("registry models must be sorted by identity")
        if set_keys != sorted(set_keys):
            raise ValueError("registry parameter sets must be sorted by identity")
        available_models = set(model_keys)
        for entry in self.parameter_sets:
            model_key = (entry.record.model_id, entry.record.model_version)
            if model_key not in available_models:
                raise ValueError(
                    "parameter set references a model version absent from registry: "
                    f"{model_key[0]}@{model_key[1]}"
                )
        return self


class RegistryVerificationReport(BaseModel):
    """Deterministic application-path evidence for a verified registry."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    registry_sha256: Sha256
    model_count: int
    parameter_set_count: int
    audited_parameter_set_count: int
    compatibility_checks: int
    unresolved_parameter_count: int
    audited_presets_immutable: Literal[True]
    citations_and_uncertainty_preserved: Literal[True]


class LaunchPreflightReport(BaseModel):
    """Traceable identities proven compatible before a caller may launch."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    registry_sha256: Sha256
    model_id: Identifier
    model_version: NonBlankText
    model_record_sha256: Sha256
    parameter_set_id: Identifier
    parameter_set_version: NonBlankText
    parameter_set_record_sha256: Sha256
    plugin_selection_sha256: list[Sha256]
    parameter_count: int
    passed: Literal[True]


def canonical_model_sha256(record: ModelRecord) -> str:
    """Return the canonical content identity of one model record."""
    return hashlib.sha256(canonical_bytes(record)).hexdigest()


def canonical_parameter_set_sha256(record: ParameterSetRecord) -> str:
    """Return the canonical content identity of one parameter-set record."""
    return hashlib.sha256(canonical_bytes(record)).hexdigest()


def canonical_registry_sha256(bundle: RegistryBundle) -> str:
    """Return the canonical content identity of a complete registry."""
    return hashlib.sha256(canonical_bytes(bundle)).hexdigest()


def canonical_bytes(model: BaseModel) -> bytes:
    """Serialize one strict registry model deterministically."""
    return (
        json.dumps(
            model.model_dump(mode="json"),
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
