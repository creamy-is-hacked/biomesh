"""Strict P6-WP01 records for portable local-queue intent."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from biomesh.project_campaign import (
    CampaignRecord,
    ExecutionIdentity,
    Identifier,
    Sha256,
    execution_identity_sha256,
)

PORTABLE_QUEUE_INTENT_SCHEMA_VERSION = 1

NonBlankText = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


class PortableQueueIntentError(ValueError):
    """Raised when portable queue intent cannot be exported safely."""


class ArchiveSourceIdentity(BaseModel):
    """Durable imported-archive provenance that grants no destination trust."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    envelope_sha256: Sha256
    payload_sha256: Sha256
    authenticity_status: Literal["AUTHENTICATED", "UNAUTHENTICATED"]
    confidentiality_status: Literal["CONFIDENTIAL", "PLAINTEXT"]
    signer_id: NonBlankText | None
    signing_key_id: NonBlankText | None
    replay_binding: Sha256 | None

    @model_validator(mode="after")
    def validate_authenticity_provenance(self) -> Self:
        authenticated = self.authenticity_status == "AUTHENTICATED"
        values = (self.signer_id, self.signing_key_id, self.replay_binding)
        if authenticated and any(value is None for value in values):
            raise ValueError(
                "authenticated archive provenance requires signer, key, and replay "
                "identities"
            )
        if not authenticated and any(value is not None for value in values):
            raise ValueError(
                "unauthenticated archive provenance cannot claim signer identities"
            )
        return self


class ProjectSourceIdentity(BaseModel):
    """Hash identity of one verified local project and any imported archive."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    project_schema_version: Literal[2]
    project_definition_sha256: Sha256
    archive: ArchiveSourceIdentity | None = None


class ExperimentDependencyIdentity(BaseModel):
    """Path-free identity for the campaign's accepted experiment fixture."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Identifier
    fixture_sha256: Sha256
    calibration_status: Literal["CALIBRATION_REQUIRED"]


class PortableQueueIntentItem(BaseModel):
    """One path-free campaign request in canonical portable execution order."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    intent_sequence: int = Field(ge=0)
    priority: int
    project_id: Identifier
    campaign: CampaignRecord
    experiment: ExperimentDependencyIdentity
    execution_identity: ExecutionIdentity
    execution_identity_sha256: Sha256
    source: ProjectSourceIdentity

    @model_validator(mode="after")
    def validate_intent_identity(self) -> Self:
        if isinstance(self.intent_sequence, bool) or isinstance(self.priority, bool):
            raise ValueError("intent sequence and priority must be integers")
        if self.campaign.experiment_id != self.experiment.experiment_id:
            raise ValueError("campaign experiment dependency identity mismatch")
        if self.execution_identity_sha256 != execution_identity_sha256(
            self.execution_identity
        ):
            raise ValueError("execution dependency identity hash mismatch")
        return self


class PortableQueueIntentManifest(BaseModel):
    """Canonical schema-versioned queue intent with no live scheduler state."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    manifest_format: Literal["biomesh-portable-queue-intent"]
    biomesh_version: NonBlankText
    source_queue_schema_version: Literal[1]
    ordering_policy: Literal["priority_descending_fifo"]
    lifecycle_policy: Literal["queued_intent_only_no_live_or_terminal_state"]
    resource_policy: Literal["local_resource_policy_not_transported"]
    trust_policy: Literal["source_archive_status_is_provenance_not_trust"]
    calibration_policy: Literal["no_calibration_status_promotion"]
    items: list[PortableQueueIntentItem] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_order_and_uniqueness(self) -> Self:
        if [item.intent_sequence for item in self.items] != list(
            range(len(self.items))
        ):
            raise ValueError("portable intent sequences must be contiguous from zero")
        priorities = [item.priority for item in self.items]
        if priorities != sorted(priorities, reverse=True):
            raise ValueError("portable intent items must be priority ordered")
        identities = [
            (
                item.source.project_definition_sha256,
                item.campaign.campaign_id,
            )
            for item in self.items
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("portable intent contains an ambiguous campaign reference")
        return self


@dataclass(frozen=True, slots=True)
class PortableQueueIntentResult:
    """Public receipt for one atomically published portable intent manifest."""

    manifest: str
    manifest_sha256: str
    item_count: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "item_count": self.item_count,
            "manifest": self.manifest,
            "manifest_sha256": self.manifest_sha256,
        }


def portable_queue_intent_bytes(manifest: PortableQueueIntentManifest) -> bytes:
    """Return a byte-canonical JSON representation after strict round-trip."""
    contents = (
        manifest.model_dump_json(
            exclude_none=False,
            serialize_as_any=False,
        )
    )
    validated = PortableQueueIntentManifest.model_validate_json(contents)
    return (
        json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def portable_queue_intent_sha256(manifest: PortableQueueIntentManifest) -> str:
    """Return the SHA-256 of one canonical portable queue-intent manifest."""
    return hashlib.sha256(portable_queue_intent_bytes(manifest)).hexdigest()


def portable_queue_intent_item_sha256(item: PortableQueueIntentItem) -> str:
    """Return the canonical identity of one portable intent item."""
    contents = json.dumps(
        item.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256((contents + "\n").encode("utf-8")).hexdigest()
