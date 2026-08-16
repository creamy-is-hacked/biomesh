"""Strict P6-WP02 records for explicit import and local rebinding."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from biomesh.local_queue_types import AbsolutePathText, QueueResourceLimits
from biomesh.portable_queue_intent_types import (
    ArchiveSourceIdentity,
    PortableQueueIntentItem,
    PortableQueueIntentManifest,
    portable_queue_intent_sha256,
)
from biomesh.project_campaign import Identifier, Sha256

PORTABLE_QUEUE_IMPORT_SCHEMA_VERSION = 1


class PortableQueueImportError(ValueError):
    """Raised when portable intent cannot be imported or rebound safely."""


class UnboundPortableQueueItem(BaseModel):
    """One validated imported intent that cannot enter the local queue."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: Literal["UNBOUND"]
    intent: PortableQueueIntentItem


class PortableQueueImportRecord(BaseModel):
    """Complete non-runnable import of one canonical P6-WP01 manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    import_format: Literal["biomesh-portable-queue-import"]
    source_manifest_sha256: Sha256
    source_manifest: PortableQueueIntentManifest
    lifecycle_policy: Literal["unbound_non_runnable"]
    binding_policy: Literal["explicit_complete_local_project_binding_required"]
    resource_policy: Literal["explicit_new_local_resource_policy_required"]
    trust_policy: Literal["no_destination_trust_granted"]
    calibration_policy: Literal["no_calibration_status_promotion"]
    items: list[UnboundPortableQueueItem] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_import_identity(self) -> Self:
        if self.source_manifest_sha256 != portable_queue_intent_sha256(
            self.source_manifest
        ):
            raise ValueError("import source manifest hash mismatch")
        if [item.intent for item in self.items] != self.source_manifest.items:
            raise ValueError("unbound items do not equal the source manifest")
        project_sources: dict[str, object] = {}
        for item in self.source_manifest.items:
            prior = project_sources.setdefault(item.project_id, item.source)
            if prior != item.source:
                raise ValueError(
                    "portable intent contains an ambiguous source project identity"
                )
        return self


class ProjectPathBinding(BaseModel):
    """Caller-supplied binding from one source project ID to one local path."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    project_id: Identifier
    local_project_directory: AbsolutePathText


class LocalProjectBinding(BaseModel):
    """Verified local project binding that grants no destination trust."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    project_id: Identifier
    source_project_definition_sha256: Sha256
    local_project_directory: AbsolutePathText
    source_archive: ArchiveSourceIdentity | None
    destination_archive_trust: Literal["NOT_GRANTED"]
    destination_plugin_trust: Literal["NOT_GRANTED"]
    destination_registry_trust: Literal["NOT_GRANTED"]
    destination_authorization: Literal["NOT_GRANTED"]
    destination_calibration_status: Literal["CALIBRATION_REQUIRED"]


class BoundPortableQueueItem(BaseModel):
    """One fully rebound intent that remains outside the runnable P4 queue."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: Literal["BOUND_NONRUNNABLE"]
    intent: PortableQueueIntentItem
    local_project_directory: AbsolutePathText


class PortableQueueBindingRecord(BaseModel):
    """Atomic complete-set local binding without P6-WP03 activation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    binding_format: Literal["biomesh-portable-queue-local-binding"]
    source_import_sha256: Sha256
    source_manifest_sha256: Sha256
    source_manifest: PortableQueueIntentManifest
    lifecycle_policy: Literal["bound_non_runnable_p6_wp03_activation_required"]
    ordering_policy: Literal["source_manifest_order_preserved"]
    resource_policy: Literal["explicit_new_local_policy_not_source_receipt"]
    trust_policy: Literal["no_destination_trust_granted"]
    calibration_policy: Literal["no_calibration_status_promotion"]
    local_resource_limits: QueueResourceLimits
    projects: list[LocalProjectBinding] = Field(min_length=1)
    items: list[BoundPortableQueueItem] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_complete_binding(self) -> Self:
        if self.source_manifest_sha256 != portable_queue_intent_sha256(
            self.source_manifest
        ):
            raise ValueError("binding source manifest hash mismatch")
        if [item.intent for item in self.items] != self.source_manifest.items:
            raise ValueError("bound items do not equal the source manifest")
        project_ids = [binding.project_id for binding in self.projects]
        project_paths = [binding.local_project_directory for binding in self.projects]
        if len(project_ids) != len(set(project_ids)):
            raise ValueError("local project binding IDs must be unique")
        if len(project_paths) != len(set(project_paths)):
            raise ValueError("local project binding paths must be unique")
        bindings = {binding.project_id: binding for binding in self.projects}
        expected_ids = {item.project_id for item in self.source_manifest.items}
        if set(bindings) != expected_ids:
            raise ValueError("local project bindings are not a complete set")
        for item in self.items:
            binding = bindings[item.intent.project_id]
            if item.local_project_directory != binding.local_project_directory:
                raise ValueError("bound item local project path mismatch")
            if (
                item.intent.source.project_definition_sha256
                != binding.source_project_definition_sha256
                or item.intent.source.archive != binding.source_archive
            ):
                raise ValueError("bound item source provenance mismatch")
        return self


@dataclass(frozen=True, slots=True)
class PortableQueueImportResult:
    """Receipt for one atomically published UNBOUND import record."""

    import_record: str
    import_sha256: str
    manifest_sha256: str
    item_count: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "import_record": self.import_record,
            "import_sha256": self.import_sha256,
            "item_count": self.item_count,
            "manifest_sha256": self.manifest_sha256,
        }


@dataclass(frozen=True, slots=True)
class PortableQueueBindingResult:
    """Receipt for one atomically published complete non-runnable binding."""

    binding_record: str
    binding_sha256: str
    item_count: int
    project_count: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "binding_record": self.binding_record,
            "binding_sha256": self.binding_sha256,
            "item_count": self.item_count,
            "project_count": self.project_count,
        }


def portable_queue_import_bytes(record: PortableQueueImportRecord) -> bytes:
    """Return deterministic strict JSON for one UNBOUND import record."""
    return _canonical_model_bytes(record, PortableQueueImportRecord)


def portable_queue_binding_bytes(record: PortableQueueBindingRecord) -> bytes:
    """Return deterministic strict JSON for one complete local binding."""
    return _canonical_model_bytes(record, PortableQueueBindingRecord)


def portable_queue_import_sha256(record: PortableQueueImportRecord) -> str:
    """Return the canonical imported-record SHA-256."""
    return hashlib.sha256(portable_queue_import_bytes(record)).hexdigest()


def _canonical_model_bytes(
    record: PortableQueueImportRecord | PortableQueueBindingRecord,
    record_type: type[PortableQueueImportRecord] | type[PortableQueueBindingRecord],
) -> bytes:
    validated = record_type.model_validate_json(
        record.model_dump_json(exclude_none=False, serialize_as_any=False)
    )
    return (
        json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
