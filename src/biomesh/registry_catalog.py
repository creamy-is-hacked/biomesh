"""Code-owned P4-WP04 catalog of accepted biological parameter presets."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from biomesh.config import (
    EPSParameterSet,
    ParameterSet,
    PhysiologyParameterSet,
    QuorumParameterSet,
    WasteShearParameterSet,
    load_eps_parameter_file,
    load_parameter_file,
    load_physiology_parameter_file,
    load_quorum_parameter_file,
    load_waste_shear_parameter_file,
)
from biomesh.registry_types import (
    ModelEntry,
    ModelRecord,
    ParameterSetEntry,
    ParameterSetRecord,
    RegistryBundle,
    RegistryParameter,
    RequiredParameter,
    canonical_model_sha256,
    canonical_parameter_set_sha256,
)

BUILTIN_REGISTRY_SOURCE = "BioMesh P4-WP04 built-in audited preset catalog"

ParameterDocument = (
    ParameterSet
    | QuorumParameterSet
    | EPSParameterSet
    | PhysiologyParameterSet
    | WasteShearParameterSet
)
ParameterLoader = Callable[[Path], ParameterDocument]


class RegistryCatalogError(ValueError):
    """Raised when an accepted preset does not match its code-owned identity."""


@dataclass(frozen=True, slots=True)
class _AuditedPreset:
    schema_id: str
    model_id: str
    parameter_set_id: str
    display_name: str
    filename: str
    sha256: str
    compatibility_reference: str
    loader: ParameterLoader


_AUDITED_PRESETS = (
    _AuditedPreset(
        "p1_core",
        "org.biomesh.p1-core",
        "org.biomesh.audited.p1-core",
        "P1 core model",
        "p1_core_model.toml",
        "b732b8547b8a36951a30ced085a14782538901790444dd1fb3d7e44b4145ebef",
        "P1A accepted parameter contract",
        load_parameter_file,
    ),
    _AuditedPreset(
        "p2_eps",
        "org.biomesh.p2-eps",
        "org.biomesh.audited.p2-eps",
        "P2 EPS model",
        "p2_eps_model.toml",
        "58d1181c95095e6edf7b91197998d759d8ba2f2130059e4b18420b04ef73d253",
        "P2A accepted P2-WP02 parameter contract",
        load_eps_parameter_file,
    ),
    _AuditedPreset(
        "p2_physiology",
        "org.biomesh.p2-physiology",
        "org.biomesh.audited.p2-physiology",
        "P2 physiological states",
        "p2_physiological_states.toml",
        "2344c5a84a15edb29a8a22cb8a2daaf9facd00aefc88737f3f2bb927cff8a2ad",
        "P2A accepted P2-WP04 parameter contract",
        load_physiology_parameter_file,
    ),
    _AuditedPreset(
        "p2_quorum",
        "org.biomesh.p2-quorum",
        "org.biomesh.audited.p2-quorum",
        "P2 quorum signal",
        "p2_quorum_signal.toml",
        "48e4dabfe0e5c54f3923762229f8c4465da41549b4a7c2b641ceb6f1296c4119",
        "P2A accepted P2-WP01 parameter contract",
        load_quorum_parameter_file,
    ),
    _AuditedPreset(
        "p2_waste_shear",
        "org.biomesh.p2-waste-shear",
        "org.biomesh.audited.p2-waste-shear",
        "P2 waste and shear",
        "p2_waste_shear.toml",
        "bba3923da9894ddf2d2493ea0dd38cfdbbf801ed1cf87814d8f546280c5da799",
        "P2A accepted P2-WP05 parameter contract",
        load_waste_shear_parameter_file,
    ),
)


def builtin_registry(repository_root: Path) -> RegistryBundle:
    """Build the registry only after verifying every accepted preset byte."""
    models: list[ModelEntry] = []
    parameter_sets: list[ParameterSetEntry] = []
    for preset in _AUDITED_PRESETS:
        source = repository_root / "parameters" / preset.filename
        try:
            source_bytes = source.read_bytes()
        except OSError as error:
            raise RegistryCatalogError(
                f"unable to read audited preset {source}: {error}"
            ) from error
        actual_sha256 = hashlib.sha256(source_bytes).hexdigest()
        if actual_sha256 != preset.sha256:
            raise RegistryCatalogError(
                f"audited preset hash mismatch for {source}: expected "
                f"{preset.sha256}, found {actual_sha256}"
            )
        try:
            document = preset.loader(source)
        except ValueError as error:
            raise RegistryCatalogError(
                f"invalid audited preset {source}: {error}"
            ) from error
        parameters = sorted(
            (
                RegistryParameter(
                    name=parameter.name,
                    value=parameter.value,
                    unit=parameter.unit,
                    provenance_kind="CALIBRATION_REQUIRED",
                    source=parameter.source,
                    citations=[],
                    uncertainty=parameter.uncertainty,
                    notes=parameter.notes,
                    calibration_status=parameter.calibration_status,
                )
                for parameter in document.biological_parameters
            ),
            key=lambda parameter: parameter.name,
        )
        model = _model_record(preset, parameters)
        parameter_set = _parameter_set_record(preset, parameters)
        models.append(
            ModelEntry(record=model, record_sha256=canonical_model_sha256(model))
        )
        parameter_sets.append(
            ParameterSetEntry(
                record=parameter_set,
                record_sha256=canonical_parameter_set_sha256(parameter_set),
            )
        )
    return RegistryBundle(
        schema_version=1,
        source=BUILTIN_REGISTRY_SOURCE,
        models=sorted(
            models,
            key=lambda entry: (entry.record.model_id, entry.record.model_version),
        ),
        parameter_sets=sorted(
            parameter_sets,
            key=lambda entry: (
                entry.record.parameter_set_id,
                entry.record.parameter_set_version,
            ),
        ),
    )


def _model_record(
    preset: _AuditedPreset, parameters: list[RegistryParameter]
) -> ModelRecord:
    return ModelRecord(
        schema_version=1,
        model_id=preset.model_id,
        model_version="1.0.0",
        display_name=preset.display_name,
        parameter_schema_id=preset.schema_id,
        required_parameters=[
            RequiredParameter(name=parameter.name, unit=parameter.unit)
            for parameter in parameters
        ],
        plugin_api_version=1,
        required_plugins=[],
        source="Accepted BioMesh P1/P2 component contract",
        compatibility_reference=preset.compatibility_reference,
        calibration_status="CALIBRATION_REQUIRED",
        limitations=[
            "Accepted software model; biological applicability is uncalibrated",
            "Registry declaration does not alter the accepted execution path",
        ],
    )


def _parameter_set_record(
    preset: _AuditedPreset, parameters: list[RegistryParameter]
) -> ParameterSetRecord:
    return ParameterSetRecord(
        schema_version=1,
        parameter_set_id=preset.parameter_set_id,
        parameter_set_version="1.0.0",
        display_name=f"{preset.display_name} audited preset",
        model_id=preset.model_id,
        model_version="1.0.0",
        parameter_schema_id=preset.schema_id,
        audited=True,
        immutable=True,
        source=f"parameters/{preset.filename}",
        source_sha256=preset.sha256,
        parameters=parameters,
    )
