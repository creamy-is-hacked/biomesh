"""Strict persistent records for the P4-WP05 local campaign queue."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from biomesh.project_campaign import (
    CampaignStatus,
    Identifier,
    NonBlankText,
)

QUEUE_SCHEMA_VERSION = 1
QUEUE_STATE = "queue_state.json"
QUEUE_LOCK = ".queue.lock"
QUEUE_WORKER_LOCK = ".worker.lock"

AbsolutePathText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=4096, pattern=r"^/"),
]

QueueAuditAction = Literal[
    "queue_created",
    "campaign_enqueued",
    "campaign_started",
    "cancellation_requested",
    "campaign_cancelled",
    "campaign_completed",
    "campaign_failed",
    "worker_recovered",
]


class LocalQueueError(ValueError):
    """Raised when a local queue operation cannot be completed safely."""


class QueueItemStatus(StrEnum):
    """Persistent lifecycle for one queued campaign execution."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueueResourceLimits(BaseModel):
    """Explicit OS-enforced limits shared by every worker invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    cpu_cores: int = Field(ge=1)
    memory_limit_bytes: int = Field(ge=1)

    @model_validator(mode="after")
    def reject_boolean_limits(self) -> Self:
        if isinstance(self.cpu_cores, bool) or isinstance(
            self.memory_limit_bytes, bool
        ):
            raise ValueError("queue resource limits must be integers")
        return self


class AppliedResourceLimits(BaseModel):
    """Exact limit receipt recorded by the local worker process."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    cpu_ids: list[int] = Field(min_length=1)
    memory_limit_bytes: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if (
            isinstance(self.memory_limit_bytes, bool)
            or any(isinstance(cpu_id, bool) or cpu_id < 0 for cpu_id in self.cpu_ids)
            or self.cpu_ids != sorted(set(self.cpu_ids))
        ):
            raise ValueError("applied resource limits are not canonical")
        return self


class QueueItem(BaseModel):
    """One persistent local campaign request and its worker identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    queue_id: Identifier
    enqueue_sequence: int = Field(ge=0)
    project_directory: AbsolutePathText
    campaign_id: Identifier
    priority: int
    status: QueueItemStatus
    cancel_requested: bool = False
    worker_pid: int | None = Field(default=None, ge=1)
    worker_start_ticks: int | None = Field(default=None, ge=0)
    applied_resources: AppliedResourceLimits | None = None
    failure: NonBlankText | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if isinstance(self.enqueue_sequence, bool) or isinstance(self.priority, bool):
            raise ValueError("queue sequence and priority must be integers")
        if isinstance(self.worker_pid, bool) or isinstance(
            self.worker_start_ticks, bool
        ):
            raise ValueError("worker identity values must be integers")
        if self.status is QueueItemStatus.RUNNING:
            if (
                self.worker_pid is None
                or self.worker_start_ticks is None
                or self.applied_resources is None
                or self.failure is not None
            ):
                raise ValueError(
                    "running queue items require worker identity and resource receipt"
                )
        elif self.worker_pid is not None or self.worker_start_ticks is not None:
            raise ValueError("only running queue items may retain worker identity")
        if self.status is QueueItemStatus.FAILED and self.failure is None:
            raise ValueError("failed queue items require a failure message")
        if self.status is not QueueItemStatus.FAILED and self.failure is not None:
            raise ValueError("only failed queue items may retain a failure message")
        if self.cancel_requested and self.status not in {
            QueueItemStatus.RUNNING,
            QueueItemStatus.CANCELLED,
        }:
            raise ValueError("cancellation may only be requested for active work")
        return self


class QueueAuditRecord(BaseModel):
    """Deterministically ordered queue transition evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    sequence: int = Field(ge=0)
    action: QueueAuditAction
    queue_id: Identifier | None = None
    detail: NonBlankText


class LocalQueueState(BaseModel):
    """Atomically replaced persistent local queue state."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    generation: int = Field(ge=0)
    next_sequence: int = Field(ge=0)
    resource_limits: QueueResourceLimits
    items: list[QueueItem]
    audit: list[QueueAuditRecord]

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if isinstance(self.generation, bool) or isinstance(self.next_sequence, bool):
            raise ValueError("queue generation and sequence must be integers")
        queue_ids = [item.queue_id for item in self.items]
        item_sequences = [item.enqueue_sequence for item in self.items]
        if len(queue_ids) != len(set(queue_ids)):
            raise ValueError("queue item IDs must be unique")
        if len(item_sequences) != len(set(item_sequences)):
            raise ValueError("queue item sequences must be unique")
        if any(sequence >= self.next_sequence for sequence in item_sequences):
            raise ValueError("queue item sequence exceeds next_sequence")
        if [record.sequence for record in self.audit] != list(range(len(self.audit))):
            raise ValueError("queue audit sequences must be contiguous from zero")
        for item in self.items:
            applied = item.applied_resources
            if applied is not None and (
                len(applied.cpu_ids) != self.resource_limits.cpu_cores
                or applied.memory_limit_bytes
                != self.resource_limits.memory_limit_bytes
            ):
                raise ValueError("worker resource receipt does not match queue limits")
        return self


@dataclass(frozen=True, slots=True)
class QueueItemSnapshot:
    """One queue item joined to an atomic campaign progress snapshot."""

    item: QueueItem
    campaign: CampaignStatus

    def as_dict(self) -> dict[str, object]:
        return {
            "campaign": self.campaign.as_dict(),
            "campaign_id": self.item.campaign_id,
            "cancel_requested": self.item.cancel_requested,
            "enqueue_sequence": self.item.enqueue_sequence,
            "failure": self.item.failure,
            "priority": self.item.priority,
            "progress_denominator": self.campaign.total,
            "progress_numerator": self.campaign.completed,
            "project_directory": self.item.project_directory,
            "queue_id": self.item.queue_id,
            "resources": (
                None
                if self.item.applied_resources is None
                else self.item.applied_resources.model_dump(mode="json")
            ),
            "status": self.item.status.value,
        }


@dataclass(frozen=True, slots=True)
class LocalQueueSnapshot:
    """Deterministically ordered public queue status."""

    queue_directory: Path
    resource_limits: QueueResourceLimits
    items: tuple[QueueItemSnapshot, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "items": [item.as_dict() for item in self.items],
            "queue_directory": str(self.queue_directory),
            "resource_limits": self.resource_limits.model_dump(mode="json"),
        }


@dataclass(frozen=True, slots=True)
class QueueRunResult:
    """Summary from one local worker drain invocation."""

    executed: int
    completed: int
    failed: int
    cancelled: int

    def as_dict(self) -> dict[str, int]:
        return {
            "cancelled": self.cancelled,
            "completed": self.completed,
            "executed": self.executed,
            "failed": self.failed,
        }
