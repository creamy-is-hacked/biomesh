"""Controlled discovery, compatibility, provenance, and loading for P4-WP03.

The accepted P1--P3 engine does not import this module. Hosts must validate a
complete plugin manifest and an explicit review policy before any entry point
is loaded.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path
from typing import Literal, Protocol, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from biomesh import __version__
from biomesh.plugin_components import (
    PLUGIN_API_VERSION,
    BasePlugin,
    ExporterPlugin,
    ExportRequest,
    ExportResult,
    FieldPlugin,
    FieldStepRequest,
    FieldStepResult,
    Identifier,
    KineticsPlugin,
    KineticsRequest,
    KineticsResult,
    MetricPlugin,
    MetricRequest,
    MetricResult,
    NonBlankText,
    PluginComponentKind,
    PluginError,
    PluginMetadata,
    PluginSelfCheck,
    Sha256,
    SpeciesDefinition,
    SpeciesPlugin,
    VersionText,
)

PLUGIN_ENTRY_POINT_GROUP = "biomesh.plugins"
PLUGIN_MANIFEST_FILE = "plugin_manifest.json"

__all__ = [
    "PLUGIN_API_VERSION",
    "BasePlugin",
    "ExporterPlugin",
    "ExportRequest",
    "ExportResult",
    "FieldPlugin",
    "FieldStepRequest",
    "FieldStepResult",
    "KineticsPlugin",
    "KineticsRequest",
    "KineticsResult",
    "LoadedPlugin",
    "MetricPlugin",
    "MetricRequest",
    "MetricResult",
    "PluginError",
    "PluginMetadata",
    "PluginProvenance",
    "PluginSelection",
    "PluginSelfCheck",
    "PluginSetManifest",
    "PluginTrustPolicy",
    "PluginVerificationReport",
    "SpeciesDefinition",
    "SpeciesPlugin",
    "builtin_plugin_trust_policy",
    "example_plugin_manifest",
    "example_plugin_metadata",
    "load_plugins",
    "plugin_metadata_sha256",
    "plugin_selection_sha256",
    "plugin_set_sha256",
    "publish_plugin_verification",
    "verify_plugins",
]


class PluginSelection(BaseModel):
    """One exact reviewed entry point and its pre-import metadata identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    metadata: PluginMetadata
    metadata_sha256: Sha256
    distribution_name: Identifier
    distribution_version: VersionText
    entry_point_name: Identifier
    entry_point_value: NonBlankText
    review_reference: NonBlankText

    @model_validator(mode="after")
    def validate_metadata_hash(self) -> Self:
        if self.metadata_sha256 != plugin_metadata_sha256(self.metadata):
            raise ValueError("plugin metadata_sha256 does not match metadata")
        return self


class PluginSetManifest(BaseModel):
    """Complete deterministic plugin selection for one controlled load."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    plugins: list[PluginSelection] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_plugins(self) -> Self:
        ids = [item.metadata.plugin_id for item in self.plugins]
        entry_point_ids = [
            (item.distribution_name, item.entry_point_name) for item in self.plugins
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("plugin IDs must be unique")
        if len(entry_point_ids) != len(set(entry_point_ids)):
            raise ValueError("plugin entry points must be unique")
        if ids != sorted(ids):
            raise ValueError("plugins must be sorted by plugin ID")
        return self


@dataclass(frozen=True, slots=True)
class PluginTrustPolicy:
    """Out-of-band review decisions required before executable code is loaded."""

    approved_selection_sha256: frozenset[str]


class PluginProvenance(BaseModel):
    """Exact loaded-code and declarative metadata identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    metadata: PluginMetadata
    metadata_sha256: Sha256
    selection_sha256: Sha256
    distribution_name: Identifier
    distribution_version: VersionText
    entry_point_name: Identifier
    entry_point_value: NonBlankText
    review_reference: NonBlankText
    self_check: PluginSelfCheck


class PluginVerificationReport(BaseModel):
    """Deterministic verification manifest for zero or reviewed plugins."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    plugin_api_version: Literal[1]
    zero_plugins_compatible: Literal[True]
    plugin_set_sha256: Sha256
    plugins: list[PluginProvenance]


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


@dataclass(frozen=True, slots=True)
class _BuiltinEntryPoint:
    name: str
    value: str
    distribution_name: str
    distribution_version: str

    def load(self) -> object:
        module_name, attribute = self.value.split(":", maxsplit=1)
        return getattr(importlib.import_module(module_name), attribute)


@dataclass(frozen=True, slots=True)
class _InstalledEntryPoint:
    entry_point: EntryPoint
    name: str
    value: str
    distribution_name: str
    distribution_version: str

    def load(self) -> object:
        return self.entry_point.load()


@dataclass(frozen=True, slots=True)
class LoadedPlugin:
    """A runtime object retained with the exact reviewed selection."""

    selection: PluginSelection
    instance: BasePlugin


def plugin_metadata_sha256(metadata: PluginMetadata) -> str:
    """Return the canonical SHA-256 identity of declarative plugin metadata."""
    return hashlib.sha256(_model_bytes(metadata)).hexdigest()


def plugin_selection_sha256(selection: PluginSelection) -> str:
    """Bind all reviewed metadata, code identity, and review provenance."""
    return hashlib.sha256(_model_bytes(selection)).hexdigest()


def plugin_set_sha256(manifest: PluginSetManifest) -> str:
    """Identify the complete ordered plugin set, including zero plugins."""
    return hashlib.sha256(_model_bytes(manifest)).hexdigest()


def example_plugin_metadata() -> PluginMetadata:
    """Return metadata for the packaged, reviewed species/kinetics example."""
    return PluginMetadata(
        schema_version=1,
        plugin_api_version=PLUGIN_API_VERSION,
        plugin_id="org.biomesh.example-species-kinetics",
        plugin_version="1.0.0",
        display_name="BioMesh example species and kinetics plugin",
        components=["kinetics", "species"],
        source="BioMesh P4-WP03 packaged software example",
        calibration_status="CALIBRATION_REQUIRED",
        limitations=[
            "Does not alter or qualify the accepted BioMesh engine",
            "Requires caller-supplied SI values and provenance records",
            "Software extension example only; not biological evidence",
        ],
    )


def example_plugin_manifest() -> PluginSetManifest:
    """Return the exact reviewed manifest for the packaged example plugin."""
    metadata = example_plugin_metadata()
    return PluginSetManifest(
        schema_version=1,
        plugins=[
            PluginSelection(
                schema_version=1,
                metadata=metadata,
                metadata_sha256=plugin_metadata_sha256(metadata),
                distribution_name="biomesh",
                distribution_version=__version__,
                entry_point_name="example-species-kinetics",
                entry_point_value=(
                    "biomesh.example_species_kinetics:create_plugin"
                ),
                review_reference="P4-WP03 packaged example",
            )
        ],
    )


def builtin_plugin_trust_policy() -> PluginTrustPolicy:
    """Return the narrow code-owned trust policy for the packaged example."""
    selection = example_plugin_manifest().plugins[0]
    return PluginTrustPolicy(
        approved_selection_sha256=frozenset(
            {plugin_selection_sha256(selection)}
        )
    )


def load_plugins(
    manifest: PluginSetManifest,
    trust_policy: PluginTrustPolicy,
    *,
    available_entry_points: Sequence[_EntryPointLike] | None = None,
) -> tuple[LoadedPlugin, ...]:
    """Preflight the complete set, then load only exact reviewed entry points."""
    _preflight_manifest(manifest, trust_policy)
    candidates = (
        tuple(available_entry_points)
        if available_entry_points is not None
        else _installed_entry_points()
    )
    resolved = tuple(
        _resolve_entry_point(item, candidates) for item in manifest.plugins
    )

    loaded: list[LoadedPlugin] = []
    for selection, entry_point in zip(manifest.plugins, resolved, strict=True):
        loaded_object = entry_point.load()
        if not callable(loaded_object):
            raise PluginError(
                f"plugin entry point is not callable: {selection.entry_point_name}"
            )
        factory = cast(Callable[[], object], loaded_object)
        instance = factory()
        if not isinstance(instance, BasePlugin):
            raise PluginError(
                f"plugin does not implement the base interface: "
                f"{selection.metadata.plugin_id}"
            )
        runtime_metadata = instance.metadata()
        if runtime_metadata != selection.metadata:
            raise PluginError(
                f"runtime metadata differs from reviewed metadata: "
                f"{selection.metadata.plugin_id}"
            )
        _validate_component_interfaces(instance, runtime_metadata)
        loaded.append(LoadedPlugin(selection=selection, instance=instance))
    return tuple(loaded)


def verify_plugins(
    manifest: PluginSetManifest | None = None,
    trust_policy: PluginTrustPolicy | None = None,
) -> PluginVerificationReport:
    """Load and deterministically self-check a reviewed plugin set."""
    selected = manifest or example_plugin_manifest()
    policy = trust_policy or builtin_plugin_trust_policy()
    loaded = load_plugins(selected, policy)
    provenance: list[PluginProvenance] = []
    for item in loaded:
        first = item.instance.self_check()
        second = item.instance.self_check()
        metadata = item.selection.metadata
        if first != second:
            raise PluginError(
                f"plugin self-check is nondeterministic: {metadata.plugin_id}"
            )
        if (
            first.plugin_id != metadata.plugin_id
            or first.plugin_version != metadata.plugin_version
        ):
            raise PluginError(
                f"plugin self-check identity mismatch: {metadata.plugin_id}"
            )
        provenance.append(
            PluginProvenance(
                metadata=metadata,
                metadata_sha256=item.selection.metadata_sha256,
                selection_sha256=plugin_selection_sha256(item.selection),
                distribution_name=item.selection.distribution_name,
                distribution_version=item.selection.distribution_version,
                entry_point_name=item.selection.entry_point_name,
                entry_point_value=item.selection.entry_point_value,
                review_reference=item.selection.review_reference,
                self_check=first,
            )
        )
    return PluginVerificationReport(
        schema_version=1,
        plugin_api_version=1,
        zero_plugins_compatible=True,
        plugin_set_sha256=plugin_set_sha256(selected),
        plugins=provenance,
    )


def publish_plugin_verification(output_directory: Path) -> PluginVerificationReport:
    """Atomically publish the packaged example's deterministic manifest."""
    output = Path(output_directory)
    if output.exists() or output.is_symlink():
        raise PluginError(f"plugin verification output already exists: {output}")
    if not output.parent.is_dir():
        raise PluginError("plugin verification output parent must exist")
    report = verify_plugins()
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        path = temporary / PLUGIN_MANIFEST_FILE
        path.write_bytes(_model_bytes(report))
        os.replace(temporary, output)
    except BaseException:
        if temporary.exists():
            for child in temporary.iterdir():
                child.unlink()
            temporary.rmdir()
        raise
    return report


def _preflight_manifest(
    manifest: PluginSetManifest, trust_policy: PluginTrustPolicy
) -> None:
    for selection in manifest.plugins:
        metadata = selection.metadata
        if metadata.plugin_api_version != PLUGIN_API_VERSION:
            raise PluginError(
                f"incompatible plugin API {metadata.plugin_api_version} for "
                f"{metadata.plugin_id}; core supports {PLUGIN_API_VERSION}"
            )
        if (
            plugin_selection_sha256(selection)
            not in trust_policy.approved_selection_sha256
        ):
            raise PluginError(
                f"plugin is not present in the explicit review policy: "
                f"{metadata.plugin_id}"
            )


def _installed_entry_points() -> tuple[_EntryPointLike, ...]:
    discovered = tuple(entry_points(group=PLUGIN_ENTRY_POINT_GROUP))
    installed: tuple[_EntryPointLike, ...] = tuple(
        _InstalledEntryPoint(
            entry_point=item,
            name=item.name,
            value=item.value,
            distribution_name=(item.dist.name if item.dist is not None else ""),
            distribution_version=(
                item.dist.version if item.dist is not None else ""
            ),
        )
        for item in discovered
    )
    if any(item.name == "example-species-kinetics" for item in installed):
        return installed
    fallback: _EntryPointLike = _BuiltinEntryPoint(
        name="example-species-kinetics",
        value="biomesh.example_species_kinetics:create_plugin",
        distribution_name="biomesh",
        distribution_version=__version__,
    )
    return installed + (fallback,)


def _resolve_entry_point(
    selection: PluginSelection, candidates: Sequence[_EntryPointLike]
) -> _EntryPointLike:
    matching = [
        item
        for item in candidates
        if item.name == selection.entry_point_name
        and item.value == selection.entry_point_value
        and item.distribution_name == selection.distribution_name
        and item.distribution_version == selection.distribution_version
    ]
    if len(matching) != 1:
        raise PluginError(
            f"expected exactly one reviewed entry point for "
            f"{selection.metadata.plugin_id}; found {len(matching)}"
        )
    return matching[0]


def _validate_component_interfaces(
    instance: BasePlugin, metadata: PluginMetadata
) -> None:
    interfaces: Mapping[PluginComponentKind, type[object]] = {
        "exporter": ExporterPlugin,
        "field": FieldPlugin,
        "kinetics": KineticsPlugin,
        "metric": MetricPlugin,
        "species": SpeciesPlugin,
    }
    for component in metadata.components:
        if not isinstance(instance, interfaces[component]):
            raise PluginError(
                f"plugin declares {component} but does not implement its interface: "
                f"{metadata.plugin_id}"
            )


def _model_bytes(model: BaseModel) -> bytes:
    return (
        json.dumps(
            model.model_dump(mode="json"),
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
