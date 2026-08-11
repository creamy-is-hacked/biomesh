"""P4-WP04 registry integrity, compatibility, import/export, and preflight."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from biomesh.plugin_api import (
    PluginSelection,
    PluginSetManifest,
    PluginTrustPolicy,
    load_plugins,
    plugin_selection_sha256,
)
from biomesh.registry_catalog import builtin_registry
from biomesh.registry_types import (
    LaunchPreflightReport,
    ModelEntry,
    ModelRecord,
    ParameterSetEntry,
    ParameterSetRecord,
    RegistryBundle,
    RegistryVerificationReport,
    RequiredPlugin,
    canonical_bytes,
    canonical_registry_sha256,
)

REGISTRY_FILE = "registry.json"


class _EntryPointLike(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def value(self) -> str: ...

    @property
    def distribution_name(self) -> str: ...

    @property
    def distribution_version(self) -> str: ...

    def load(self) -> object: ...


class RegistryError(ValueError):
    """Raised when registry data cannot be trusted or used safely."""


def load_registry(path: Path, repository_root: Path) -> RegistryBundle:
    """Load one strict registry file/directory and enforce audited identities."""
    source = path / REGISTRY_FILE if path.is_dir() else path
    try:
        payload = source.read_bytes()
    except OSError as error:
        raise RegistryError(f"unable to read registry {source}: {error}") from error
    try:
        bundle = RegistryBundle.model_validate_json(payload)
    except ValidationError as error:
        raise RegistryError(f"invalid registry {source}: {error}") from error
    _verify_audited_identities(bundle, repository_root)
    return bundle


def verify_registry(
    bundle: RegistryBundle, repository_root: Path
) -> RegistryVerificationReport:
    """Verify hashes, audited immutability, units, compatibility, and round-trip."""
    _verify_audited_identities(bundle, repository_root)
    compatibility_checks = 0
    unresolved = 0
    for entry in bundle.parameter_sets:
        model_entry = _find_model(
            bundle, entry.record.model_id, entry.record.model_version
        )
        compatibility_checks += _check_parameter_compatibility(
            model_entry.record, entry.record
        )
        unresolved += sum(
            parameter.value == "CALIBRATION_REQUIRED"
            for parameter in entry.record.parameters
        )
    serialized = canonical_bytes(bundle)
    if RegistryBundle.model_validate_json(serialized) != bundle:
        raise RegistryError("registry failed citation/uncertainty semantic round-trip")
    return RegistryVerificationReport(
        schema_version=1,
        registry_sha256=canonical_registry_sha256(bundle),
        model_count=len(bundle.models),
        parameter_set_count=len(bundle.parameter_sets),
        audited_parameter_set_count=sum(
            entry.record.audited for entry in bundle.parameter_sets
        ),
        compatibility_checks=compatibility_checks,
        unresolved_parameter_count=unresolved,
        audited_presets_immutable=True,
        citations_and_uncertainty_preserved=True,
    )


def publish_builtin_registry(
    output_directory: Path, repository_root: Path
) -> RegistryVerificationReport:
    """Atomically export the verified built-in registry to a new directory."""
    bundle = builtin_registry(repository_root)
    report = verify_registry(bundle, repository_root)
    _publish_registry(bundle, output_directory)
    return report


def import_registry(
    source: Path, output_directory: Path, repository_root: Path
) -> RegistryVerificationReport:
    """Validate and atomically import a registry without changing its semantics."""
    bundle = load_registry(source, repository_root)
    report = verify_registry(bundle, repository_root)
    _publish_registry(bundle, output_directory)
    return report


def preflight_launch(
    bundle: RegistryBundle,
    *,
    repository_root: Path,
    model_id: str,
    model_version: str,
    parameter_set_id: str,
    parameter_set_version: str,
    plugin_manifest: PluginSetManifest,
    trust_policy: PluginTrustPolicy,
    available_entry_points: Sequence[_EntryPointLike] | None = None,
) -> LaunchPreflightReport:
    """Fail closed on parameters and plugins before returning launch identities."""
    registry_report = verify_registry(bundle, repository_root)
    model_entry = _find_model(bundle, model_id, model_version)
    parameter_entry = _find_parameter_set(
        bundle, parameter_set_id, parameter_set_version
    )
    _check_parameter_compatibility(model_entry.record, parameter_entry.record)
    unresolved = [
        parameter.name
        for parameter in parameter_entry.record.parameters
        if parameter.value == "CALIBRATION_REQUIRED"
    ]
    if unresolved:
        raise RegistryError(
            "launch blocked by CALIBRATION_REQUIRED parameters: "
            + ", ".join(unresolved)
        )

    declared_plugins = {
        selection.metadata.plugin_id: (
            selection.metadata.plugin_version,
            selection.metadata_sha256,
            plugin_selection_sha256(selection),
            tuple(selection.metadata.components),
        )
        for selection in plugin_manifest.plugins
    }
    required_plugins = {
        item.plugin_id: (
            item.plugin_version,
            item.metadata_sha256,
            item.selection_sha256,
            tuple(item.components),
        )
        for item in model_entry.record.required_plugins
    }
    if declared_plugins != required_plugins:
        raise RegistryError(
            "plugin selection does not exactly match model requirements"
        )
    try:
        loaded_plugins = load_plugins(
            plugin_manifest,
            trust_policy,
            available_entry_points=available_entry_points,
        )
    except ValueError as error:
        raise RegistryError(f"plugin preflight failed: {error}") from error
    actual_plugins = {
        item.selection.metadata.plugin_id: (
            item.selection.metadata.plugin_version,
            item.selection.metadata_sha256,
            plugin_selection_sha256(item.selection),
            tuple(item.selection.metadata.components),
        )
        for item in loaded_plugins
    }
    if actual_plugins != required_plugins:
        raise RegistryError(
            "plugin selection does not exactly match model requirements"
        )
    return LaunchPreflightReport(
        schema_version=1,
        registry_sha256=registry_report.registry_sha256,
        model_id=model_entry.record.model_id,
        model_version=model_entry.record.model_version,
        model_record_sha256=model_entry.record_sha256,
        parameter_set_id=parameter_entry.record.parameter_set_id,
        parameter_set_version=parameter_entry.record.parameter_set_version,
        parameter_set_record_sha256=parameter_entry.record_sha256,
        plugin_selection_sha256=sorted(
            plugin_selection_sha256(selection)
            for selection in plugin_manifest.plugins
        ),
        parameter_count=len(parameter_entry.record.parameters),
        passed=True,
    )


def required_plugin_from_selection(
    selection: PluginSelection,
) -> RequiredPlugin:
    """Convert one validated plugin selection without widening its trust policy."""
    metadata = selection.metadata
    return RequiredPlugin(
        plugin_id=metadata.plugin_id,
        plugin_version=metadata.plugin_version,
        metadata_sha256=selection.metadata_sha256,
        selection_sha256=plugin_selection_sha256(selection),
        components=sorted(metadata.components),
    )


def _verify_audited_identities(
    bundle: RegistryBundle, repository_root: Path
) -> None:
    builtins = builtin_registry(repository_root)
    expected = {
        (entry.record.parameter_set_id, entry.record.parameter_set_version): entry
        for entry in builtins.parameter_sets
    }
    for entry in bundle.parameter_sets:
        if not entry.record.audited:
            continue
        key = (entry.record.parameter_set_id, entry.record.parameter_set_version)
        accepted = expected.get(key)
        if accepted is None or entry != accepted:
            raise RegistryError(
                "audited parameter set is not an immutable built-in identity: "
                f"{key[0]}@{key[1]}"
            )


def _check_parameter_compatibility(
    model: ModelRecord, parameter_set: ParameterSetRecord
) -> int:
    if (parameter_set.model_id, parameter_set.model_version) != (
        model.model_id,
        model.model_version,
    ):
        raise RegistryError("parameter set targets a different model version")
    if parameter_set.parameter_schema_id != model.parameter_schema_id:
        raise RegistryError("parameter schema is incompatible with model")
    required = {
        parameter.name: parameter.unit for parameter in model.required_parameters
    }
    supplied = {
        parameter.name: parameter.unit for parameter in parameter_set.parameters
    }
    missing = sorted(required.keys() - supplied.keys())
    unexpected = sorted(supplied.keys() - required.keys())
    if missing or unexpected:
        raise RegistryError(
            "parameter names are incompatible with model; "
            f"missing={missing}, unexpected={unexpected}"
        )
    mismatches = sorted(
        name for name in required if required[name] != supplied[name]
    )
    if mismatches:
        details = ", ".join(
            f"{name}: expected {required[name]!r}, found {supplied[name]!r}"
            for name in mismatches
        )
        raise RegistryError(f"parameter unit mismatch: {details}")
    return len(required)


def _find_model(
    bundle: RegistryBundle, model_id: str, model_version: str
) -> ModelEntry:
    matches = [
        entry
        for entry in bundle.models
        if (entry.record.model_id, entry.record.model_version)
        == (model_id, model_version)
    ]
    if len(matches) != 1:
        raise RegistryError(f"unknown model version {model_id}@{model_version}")
    return matches[0]


def _find_parameter_set(
    bundle: RegistryBundle, parameter_set_id: str, parameter_set_version: str
) -> ParameterSetEntry:
    matches = [
        entry
        for entry in bundle.parameter_sets
        if (entry.record.parameter_set_id, entry.record.parameter_set_version)
        == (parameter_set_id, parameter_set_version)
    ]
    if len(matches) != 1:
        raise RegistryError(
            f"unknown parameter-set version "
            f"{parameter_set_id}@{parameter_set_version}"
        )
    return matches[0]


def _publish_registry(bundle: RegistryBundle, output_directory: Path) -> None:
    output = Path(output_directory)
    if output.exists() or output.is_symlink():
        raise RegistryError(f"registry output already exists: {output}")
    target = output.resolve()
    if not target.parent.is_dir():
        raise RegistryError(f"registry output parent does not exist: {target.parent}")
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent)
    )
    try:
        registry_file = temporary / REGISTRY_FILE
        registry_file.write_bytes(canonical_bytes(bundle))
        with registry_file.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as error:
        raise RegistryError(f"unable to publish registry {target}: {error}") from error
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
