"""Validated P3-WP04 biological-parameter editing documents.

This module contains no Qt state.  Mutable editor text lives in
``ExperimentEditorSession`` while the accepted scientific configuration is one
of the existing frozen Pydantic parameter schemas from :mod:`biomesh.config`.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from biomesh.config import (
    EPSParameterSet,
    ParameterSet,
    PhysiologyParameterSet,
    QuorumParameterSet,
    WasteShearParameterSet,
)

ParameterDocumentModel = (
    ParameterSet
    | QuorumParameterSet
    | EPSParameterSet
    | PhysiologyParameterSet
    | WasteShearParameterSet
)
AUDITED_PRESET_REVISION = "6adb5def6f094762cb79ba3a2eddeede6007a2f5"


class ExperimentDocumentError(ValueError):
    """Raised when an editor document cannot be loaded, validated, or saved."""


class DocumentAccess(StrEnum):
    """Whether a session is an editable draft or an immutable audited view."""

    EDITABLE = "editable"
    AUDITED_READ_ONLY = "audited_read_only"


class BiologicalParameterFields(StrEnum):
    """Fields exposed by the existing BiologicalParameter schema."""

    NAME = "name"
    VALUE = "value"
    UNIT = "unit"
    SOURCE = "source"
    UNCERTAINTY = "uncertainty"
    NOTES = "notes"
    CALIBRATION_STATUS = "calibration_status"


_BIOLOGICAL_PARAMETER_FIELD_NAMES = frozenset(
    field.value for field in BiologicalParameterFields
)


@dataclass(frozen=True, slots=True)
class ParameterSchema:
    """One existing validated parameter schema and its repository template."""

    schema_id: str
    title: str
    template_name: str
    model_type: type[BaseModel]
    audited_sha256: str

    def validate(self, payload: object) -> ParameterDocumentModel:
        """Validate payload through the existing frozen scientific schema."""
        return cast(ParameterDocumentModel, self.model_type.model_validate(payload))


PARAMETER_SCHEMAS = (
    ParameterSchema(
        "p1_core",
        "P1 core model",
        "p1_core_model.toml",
        ParameterSet,
        "b732b8547b8a36951a30ced085a14782538901790444dd1fb3d7e44b4145ebef",
    ),
    ParameterSchema(
        "p2_quorum",
        "P2 quorum signal",
        "p2_quorum_signal.toml",
        QuorumParameterSet,
        "48e4dabfe0e5c54f3923762229f8c4465da41549b4a7c2b641ceb6f1296c4119",
    ),
    ParameterSchema(
        "p2_eps",
        "P2 EPS model",
        "p2_eps_model.toml",
        EPSParameterSet,
        "58d1181c95095e6edf7b91197998d759d8ba2f2130059e4b18420b04ef73d253",
    ),
    ParameterSchema(
        "p2_physiology",
        "P2 physiological states",
        "p2_physiological_states.toml",
        PhysiologyParameterSet,
        "2344c5a84a15edb29a8a22cb8a2daaf9facd00aefc88737f3f2bb927cff8a2ad",
    ),
    ParameterSchema(
        "p2_waste_shear",
        "P2 waste and shear",
        "p2_waste_shear.toml",
        WasteShearParameterSet,
        "bba3923da9894ddf2d2493ea0dd38cfdbbf801ed1cf87814d8f546280c5da799",
    ),
)
_SCHEMA_BY_ID = {schema.schema_id: schema for schema in PARAMETER_SCHEMAS}


@dataclass(frozen=True, slots=True)
class ParameterDocument:
    """Immutable validated scientific configuration, separate from UI state."""

    schema: ParameterSchema
    configuration: ParameterDocumentModel


def schema_by_id(schema_id: str) -> ParameterSchema:
    """Return a registered existing schema or fail explicitly."""
    try:
        return _SCHEMA_BY_ID[schema_id]
    except KeyError as error:
        raise ExperimentDocumentError(
            f"unknown parameter schema {schema_id!r}"
        ) from error


def repository_parameter_path(repository_root: Path, schema_id: str) -> Path:
    """Resolve one versioned repository parameter record for templates/presets."""
    schema = schema_by_id(schema_id)
    return (repository_root / "parameters" / schema.template_name).resolve()


def audited_preset_paths(repository_root: Path) -> frozenset[Path]:
    """Return paths protected as P2A-accepted read-only presets."""
    return frozenset(
        repository_parameter_path(repository_root, schema.schema_id)
        for schema in PARAMETER_SCHEMAS
    )


def load_parameter_document(path: Path, schema_id: str) -> ParameterDocument:
    """Load TOML and validate it through the selected existing schema."""
    schema = schema_by_id(schema_id)
    try:
        with path.open("rb") as stream:
            payload = tomllib.load(stream)
    except OSError as error:
        raise ExperimentDocumentError(
            f"unable to read parameter configuration {path}: {error.strerror or error}"
        ) from error
    except tomllib.TOMLDecodeError as error:
        raise ExperimentDocumentError(
            f"invalid TOML in parameter configuration {path}: {error}"
        ) from error
    try:
        configuration = schema.validate(payload)
    except ValidationError as error:
        raise ExperimentDocumentError(
            f"invalid {schema.title} configuration {path}: {error}"
        ) from error
    return ParameterDocument(schema, configuration)


def detect_parameter_document(path: Path) -> ParameterDocument:
    """Load a saved configuration only when exactly one existing schema accepts it."""
    accepted: list[ParameterDocument] = []
    failures: list[str] = []
    for schema in PARAMETER_SCHEMAS:
        try:
            accepted.append(load_parameter_document(path, schema.schema_id))
        except ExperimentDocumentError as error:
            failures.append(str(error))
    if len(accepted) == 1:
        return accepted[0]
    if not accepted:
        raise ExperimentDocumentError(
            f"saved configuration {path} matches no existing parameter schema: "
            + " | ".join(failures)
        )
    schema_ids = ", ".join(item.schema.schema_id for item in accepted)
    raise ExperimentDocumentError(
        f"saved configuration {path} ambiguously matches schemas: {schema_ids}"
    )


class ExperimentEditorSession:
    """Mutable draft text whose only scientific output is a validated document."""

    def __init__(
        self,
        document: ParameterDocument,
        *,
        access: DocumentAccess,
        source_path: Path,
        protected_paths: frozenset[Path],
    ) -> None:
        self.document = document
        self.access = access
        self.source_path = source_path.resolve()
        self.protected_paths = protected_paths
        self.target_path: Path | None = None
        self._draft_fields = [
            {
                name.value: _field_text(parameter, name.value)
                for name in BiologicalParameterFields
            }
            for parameter in document.configuration.biological_parameters
        ]
        self._validation_errors: dict[tuple[int, str], str] = {}
        self._validated_document: ParameterDocument | None = document

    @classmethod
    def from_template(
        cls, repository_root: Path, schema_id: str
    ) -> ExperimentEditorSession:
        """Create an unsaved editable draft from a provenance-complete template."""
        source = repository_parameter_path(repository_root, schema_id)
        return cls(
            load_parameter_document(source, schema_id),
            access=DocumentAccess.EDITABLE,
            source_path=source,
            protected_paths=audited_preset_paths(repository_root),
        )

    @classmethod
    def from_audited_preset(
        cls, repository_root: Path, schema_id: str
    ) -> ExperimentEditorSession:
        """Open a P2A-accepted repository parameter record read-only."""
        source = repository_parameter_path(repository_root, schema_id)
        schema = schema_by_id(schema_id)
        try:
            actual_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
        except OSError as error:
            raise ExperimentDocumentError(
                f"unable to verify audited preset {source}: {error}"
            ) from error
        if actual_sha256 != schema.audited_sha256:
            raise ExperimentDocumentError(
                f"audited preset {source} does not match P2A revision "
                f"{AUDITED_PRESET_REVISION}"
            )
        return cls(
            load_parameter_document(source, schema_id),
            access=DocumentAccess.AUDITED_READ_ONLY,
            source_path=source,
            protected_paths=audited_preset_paths(repository_root),
        )

    @classmethod
    def from_saved_configuration(
        cls, repository_root: Path, path: Path
    ) -> ExperimentEditorSession:
        """Open a saved configuration as editable without treating it as UI state."""
        resolved = path.expanduser().resolve()
        protected = audited_preset_paths(repository_root)
        if resolved in protected:
            raise ExperimentDocumentError(
                "repository audited presets must be opened through the read-only "
                "preset catalog"
            )
        return cls(
            detect_parameter_document(resolved),
            access=DocumentAccess.EDITABLE,
            source_path=resolved,
            protected_paths=protected,
        )

    @property
    def is_read_only(self) -> bool:
        """Return whether edits and saves are prohibited for this session."""
        return self.access is DocumentAccess.AUDITED_READ_ONLY

    @property
    def validation_errors(self) -> dict[tuple[int, str], str]:
        """Return a copy of explicit row/field validation errors."""
        return dict(self._validation_errors)

    @property
    def validated_document(self) -> ParameterDocument | None:
        """Return immutable validated science, or ``None`` for an invalid draft."""
        return self._validated_document

    @property
    def run_eligible(self) -> bool:
        """Require valid, fully resolved provenance before future run controls."""
        if self._validated_document is None:
            return False
        return all(
            parameter.value != "CALIBRATION_REQUIRED"
            and parameter.source != "CALIBRATION_REQUIRED"
            and parameter.uncertainty != "CALIBRATION_REQUIRED"
            and parameter.calibration_status != "CALIBRATION_REQUIRED"
            for parameter in (
                self._validated_document.configuration.biological_parameters
            )
        )

    def field_text(self, parameter_index: int, field_name: str) -> str:
        """Return the exact editor text for one schema field."""
        self._require_field(parameter_index, field_name)
        return self._draft_fields[parameter_index][field_name]

    def set_field(self, parameter_index: int, field_name: str, text: str) -> None:
        """Update one draft field and revalidate without coercion or fallback."""
        if self.is_read_only:
            raise ExperimentDocumentError(
                "audited presets are read-only; create an editable copy first"
            )
        self._require_field(parameter_index, field_name)
        if not isinstance(text, str):
            raise ExperimentDocumentError("editor field value must be text")
        self._draft_fields[parameter_index][field_name] = text
        self._revalidate()

    def clone_as_editable(self) -> ExperimentEditorSession:
        """Copy current valid semantics into a new unsaved editable draft."""
        if self._validated_document is None:
            raise ExperimentDocumentError(
                "invalid configuration cannot be cloned as an editable document"
            )
        return ExperimentEditorSession(
            self._validated_document,
            access=DocumentAccess.EDITABLE,
            source_path=self.source_path,
            protected_paths=self.protected_paths,
        )

    def save(self, path: Path, *, overwrite: bool = False) -> ParameterDocument:
        """Atomically save a valid draft after semantic round-trip verification."""
        if self.is_read_only:
            raise ExperimentDocumentError(
                "audited presets are read-only and cannot be saved or overwritten"
            )
        if self._validated_document is None:
            raise ExperimentDocumentError(
                "invalid configuration cannot be saved or become run-eligible"
            )
        target = path.expanduser().resolve()
        if target in self.protected_paths:
            raise ExperimentDocumentError(
                f"audited preset cannot be overwritten: {target}"
            )
        if not target.parent.is_dir():
            raise ExperimentDocumentError(
                f"configuration parent directory does not exist: {target.parent}"
            )
        if target.exists() and not overwrite:
            raise ExperimentDocumentError(
                f"configuration already exists; explicit overwrite required: {target}"
            )
        contents = _serialize_document(self._validated_document)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.name}.",
                delete=False,
            ) as temporary:
                temporary.write(contents)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            reloaded = load_parameter_document(
                temporary_path, self._validated_document.schema.schema_id
            )
            if reloaded.configuration != self._validated_document.configuration:
                raise ExperimentDocumentError(
                    "saved configuration failed semantic round-trip verification"
                )
            os.replace(temporary_path, target)
            temporary_path = None
        except OSError as error:
            raise ExperimentDocumentError(
                f"unable to save parameter configuration {target}: {error}"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        self.target_path = target
        return load_parameter_document(target, self.document.schema.schema_id)

    def _require_field(self, parameter_index: int, field_name: str) -> None:
        if not 0 <= parameter_index < len(self._draft_fields):
            raise ExperimentDocumentError(
                f"parameter index is out of range: {parameter_index}"
            )
        if field_name not in _BIOLOGICAL_PARAMETER_FIELD_NAMES:
            raise ExperimentDocumentError(f"unknown parameter field {field_name!r}")

    def _revalidate(self) -> None:
        payload = self.document.configuration.model_dump(mode="python")
        parameters = cast(list[dict[str, Any]], payload["biological_parameters"])
        parse_errors: dict[tuple[int, str], str] = {}
        for index, draft in enumerate(self._draft_fields):
            parameters[index] = dict(draft)
            value_text = draft[BiologicalParameterFields.VALUE.value]
            if value_text == "CALIBRATION_REQUIRED":
                parameters[index][BiologicalParameterFields.VALUE.value] = value_text
            else:
                try:
                    parameters[index][BiologicalParameterFields.VALUE.value] = float(
                        value_text
                    )
                except ValueError:
                    parse_errors[(index, BiologicalParameterFields.VALUE.value)] = (
                        "value must be a finite number or CALIBRATION_REQUIRED"
                    )
        if parse_errors:
            self._validation_errors = parse_errors
            self._validated_document = None
            return
        try:
            configuration = self.document.schema.validate(payload)
        except ValidationError as error:
            self._validation_errors = _validation_error_map(error)
            self._validated_document = None
            return
        self._validation_errors = {}
        self._validated_document = ParameterDocument(
            self.document.schema, configuration
        )


def _validation_error_map(error: ValidationError) -> dict[tuple[int, str], str]:
    mapped: dict[tuple[int, str], str] = {}
    for item in error.errors(include_url=False):
        location = item["loc"]
        index = -1
        field = "__document__"
        if len(location) >= 2 and location[0] == "biological_parameters":
            if isinstance(location[1], int):
                index = location[1]
            if len(location) >= 3 and isinstance(location[2], str):
                field = location[2]
            else:
                field = "__parameter__"
        mapped[(index, field)] = str(item["msg"])
    return mapped


def _field_text(parameter: BaseModel, field_name: str) -> str:
    value = getattr(parameter, field_name)
    return str(value)


def _serialize_document(document: ParameterDocument) -> str:
    lines = [f"schema_version = {document.configuration.schema_version}", ""]
    for parameter in document.configuration.biological_parameters:
        lines.append("[[biological_parameters]]")
        for field in BiologicalParameterFields:
            value = getattr(parameter, field.value)
            lines.append(f"{field.value} = {_toml_scalar(value)}")
        lines.append("")
    return "\n".join(lines)


def _toml_scalar(value: object) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    raise ExperimentDocumentError(f"unsupported TOML scalar {value!r}")
