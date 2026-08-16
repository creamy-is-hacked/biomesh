"""Strict P6-WP03 activation and destination provenance records."""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from biomesh.local_queue_types import AbsolutePathText, QueueResourceLimits
from biomesh.portable_queue_import_types import (
    PortableQueueBindingRecord,
    portable_queue_binding_bytes,
)
from biomesh.project_campaign import Identifier, Sha256

PORTABLE_QUEUE_ACTIVATION_SCHEMA_VERSION = 1
PORTABLE_QUEUE_ACTIVATION_FILE = "portable_activation.json"


class PortableQueueActivationError(ValueError):
    """Raised when a bound portable item cannot be activated safely."""


class ActivatedPortableQueueItem(BaseModel):
    """One bound intent mapped to a newly allocated local queue identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: Literal["ACTIVATED"]
    intent_sequence: int = Field(ge=0)
    portable_intent_item_sha256: Sha256
    project_id: Identifier
    campaign_id: Identifier
    local_project_directory: AbsolutePathText
    local_queue_id: Identifier

    @model_validator(mode="after")
    def validate_integers(self) -> Self:
        if isinstance(self.intent_sequence, bool):
            raise ValueError("activation intent sequence must be an integer")
        return self


class PortableQueueActivationRecord(BaseModel):
    """Immutable activation provenance stored beside a fresh local queue."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    activation_format: Literal["biomesh-portable-queue-activation"]
    source_binding_sha256: Sha256
    source_import_sha256: Sha256
    source_manifest_sha256: Sha256
    source_binding: PortableQueueBindingRecord
    lifecycle_policy: Literal["activated_local_p4_queue_only"]
    scheduler_policy: Literal["new_destination_queue_identity_only"]
    resource_policy: Literal["binding_local_policy_verified_at_activation"]
    trust_policy: Literal["no_destination_trust_granted"]
    calibration_policy: Literal["no_calibration_status_promotion"]
    destination_queue_schema_version: Literal[1]
    destination_resource_limits: QueueResourceLimits
    items: list[ActivatedPortableQueueItem] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_activation(self) -> Self:
        if self.source_binding_sha256 != hashlib.sha256(
            portable_queue_binding_bytes(self.source_binding)
        ).hexdigest():
            raise ValueError("activation source binding hash mismatch")
        if self.source_import_sha256 != self.source_binding.source_import_sha256:
            raise ValueError("activation source import hash mismatch")
        if self.source_manifest_sha256 != self.source_binding.source_manifest_sha256:
            raise ValueError("activation source manifest hash mismatch")
        if (
            self.destination_resource_limits
            != self.source_binding.local_resource_limits
        ):
            raise ValueError("activation resource policy does not equal the binding")
        if [item.intent_sequence for item in self.items] != list(
            range(len(self.items))
        ):
            raise ValueError("activation intent sequences must be contiguous")
        expected = self.source_binding.items
        if len(self.items) != len(expected):
            raise ValueError("activation item count does not equal the binding")
        queue_ids = [item.local_queue_id for item in self.items]
        if len(queue_ids) != len(set(queue_ids)):
            raise ValueError("activated local queue IDs must be unique")
        for activated, bound in zip(self.items, expected, strict=True):
            if activated.project_id != bound.intent.project_id:
                raise ValueError("activation project identity mismatch")
            if activated.campaign_id != bound.intent.campaign.campaign_id:
                raise ValueError("activation campaign identity mismatch")
            if activated.local_project_directory != bound.local_project_directory:
                raise ValueError("activation local project path mismatch")
        return self


def portable_queue_activation_bytes(
    record: PortableQueueActivationRecord,
) -> bytes:
    """Return deterministic strict JSON for one activation record."""
    try:
        validated = PortableQueueActivationRecord.model_validate_json(
            record.model_dump_json(exclude_none=False, serialize_as_any=False)
        )
    except ValidationError as error:
        raise PortableQueueActivationError(
            f"invalid portable queue activation: {error}"
        ) from error
    return (
        json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def portable_queue_activation_sha256(record: PortableQueueActivationRecord) -> str:
    """Return the canonical activation-record SHA-256."""
    return hashlib.sha256(portable_queue_activation_bytes(record)).hexdigest()
