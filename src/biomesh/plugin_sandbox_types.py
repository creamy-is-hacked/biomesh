"""Versioned messages, policy, and provenance for isolated plugin execution."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from biomesh.plugin_components import Identifier, PluginError, Sha256, VersionText

PLUGIN_SANDBOX_POLICY_VERSION = "1.0.0"
PLUGIN_SANDBOX_MESSAGE_VERSION = 1

PluginOperation = Literal[
    "initialize",
    "self_check",
    "species_definition",
    "evaluate_kinetics",
    "advance_field",
    "evaluate_metric",
    "export",
]
PluginExecutionOutcome = Literal[
    "success",
    "preflight_denied",
    "setup_failure",
    "policy_violation",
    "timeout",
    "crash",
    "resource_limit",
    "malformed_output",
    "communication_failure",
]


class PluginSandboxPolicy(BaseModel):
    """Host-owned engineering limits for one fresh plugin operation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1] = 1
    policy_version: str = PLUGIN_SANDBOX_POLICY_VERSION
    wall_timeout_seconds: float = Field(default=5.0, gt=0.0, le=60.0)
    cpu_time_seconds: int = Field(default=2, ge=1, le=30)
    memory_limit_bytes: int = Field(
        default=536_870_912,
        ge=134_217_728,
        le=2_147_483_648,
    )
    max_message_bytes: int = Field(default=1_048_576, ge=4096, le=8_388_608)
    max_output_bytes: int = Field(default=1_048_576, ge=4096, le=8_388_608)
    max_open_files: int = Field(default=32, ge=16, le=256)
    max_processes: Literal[1] = 1


class PluginSandboxRequest(BaseModel):
    """Canonical immutable request sent to the isolated worker."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    plugin_api_version: Literal[1]
    sandbox_policy_version: str
    plugin_id: Identifier
    plugin_version: VersionText
    selection_sha256: Sha256
    entry_point_value: str = Field(min_length=3, max_length=512, pattern=r"\S+:\S+")
    operation: PluginOperation
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_empty_operations(self) -> Self:
        if self.operation in {
            "initialize",
            "self_check",
            "species_definition",
        } and self.payload:
            raise ValueError(f"{self.operation} payload must be empty")
        return self


class PluginSandboxResponse(BaseModel):
    """Canonical worker response validated before host publication."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    plugin_api_version: Literal[1]
    sandbox_policy_version: str
    plugin_id: Identifier
    plugin_version: VersionText
    selection_sha256: Sha256
    operation: PluginOperation
    request_sha256: Sha256
    payload: dict[str, Any]


class PluginResourceLimits(BaseModel):
    """Exact engineering limits applied to one sandbox operation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    wall_timeout_seconds: float
    cpu_time_seconds: int
    memory_limit_bytes: int
    max_message_bytes: int
    max_output_bytes: int
    max_open_files: int
    max_processes: int


class PluginExecutionReceipt(BaseModel):
    """Secret-free provenance for every attempted isolated operation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    plugin_api_version: Literal[1]
    sandbox_policy_version: str
    plugin_id: Identifier
    plugin_version: VersionText
    selection_sha256: Sha256
    plugin_set_sha256: Sha256
    operation: PluginOperation
    request_sha256: Sha256
    result_sha256: Sha256 | None
    outcome: PluginExecutionOutcome
    resource_limits: PluginResourceLimits
    environment_isolation: Literal["cleared"]
    filesystem_isolation: Literal["declared-runtime-read-only"]
    network_isolation: Literal["network-namespace-and-seccomp"]
    process_isolation: Literal["pid-namespace-and-seccomp"]
    calibration_status: Literal["CALIBRATION_REQUIRED"]
    details: str = Field(min_length=1, max_length=256)


class PluginSandboxError(PluginError):
    """Fail one plugin operation while retaining its explicit receipt."""

    def __init__(self, message: str, receipt: PluginExecutionReceipt) -> None:
        super().__init__(message)
        self.receipt = receipt


def canonical_message_bytes(model: BaseModel) -> bytes:
    """Serialize one versioned message deterministically."""
    return (
        json.dumps(
            model.model_dump(mode="json"),
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def message_sha256(payload: bytes) -> str:
    """Return the exact identity of one canonical message."""
    return hashlib.sha256(payload).hexdigest()


def default_plugin_sandbox_policy() -> PluginSandboxPolicy:
    """Return the code-owned P5-WP04 sandbox policy."""
    return PluginSandboxPolicy()
