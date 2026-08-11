"""Strict records for P4-WP06 portable project archives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ArchivePath = Annotated[str, StringConstraints(min_length=1, pattern=r"^[^\\]+$")]


class PortableArchiveError(ValueError):
    """Raised when portable project exchange cannot be completed safely."""


class PortableFileRecord(BaseModel):
    """One byte-exact regular file carried by a portable archive."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: ArchivePath
    role: Literal["configuration", "manifest", "fixture", "compact_result"]
    sha256: Sha256
    size_bytes: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_size(self) -> Self:
        if isinstance(self.size_bytes, bool):
            raise ValueError("portable file size_bytes must be an integer")
        return self


class PortableProjectManifest(BaseModel):
    """Self-describing, deterministic archive inventory and scope boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    archive_format: Literal["biomesh-portable-project"]
    biomesh_version: str
    project_id: str
    project_schema_version: Literal[1]
    source_definition_sha256: Sha256
    portable_definition_sha256: Sha256
    state_sha256: Sha256
    calibration_status: Literal["CALIBRATION_REQUIRED"]
    result_policy: Literal["all_hash_verified_completed_run_artifacts"]
    plugin_policy: Literal["no_plugins_embedded_or_trusted"]
    registry_policy: Literal["no_registry_embedded_or_reidentified"]
    queue_policy: Literal["queue_state_not_embedded_reenqueue_after_import"]
    files: list[PortableFileRecord] = Field(min_length=3)

    @model_validator(mode="after")
    def validate_inventory(self) -> Self:
        paths = [record.path for record in self.files]
        if paths != sorted(paths):
            raise ValueError("portable archive file inventory must be path-sorted")
        if len(paths) != len(set(paths)):
            raise ValueError("portable archive file paths must be unique")
        required = {
            "project/project.json",
            "project/campaign_state.json",
        }
        if not required.issubset(paths):
            raise ValueError("portable archive omits required project manifests")
        if not any(record.role == "fixture" for record in self.files):
            raise ValueError("portable archive requires at least one fixture")
        return self


@dataclass(frozen=True, slots=True)
class PortableArchiveResult:
    """Public result for archive export or verification."""

    archive: str
    archive_sha256: str
    file_count: int
    completed_run_count: int
    project_id: str

    def as_dict(self) -> dict[str, int | str]:
        return {
            "archive": self.archive,
            "archive_sha256": self.archive_sha256,
            "completed_run_count": self.completed_run_count,
            "file_count": self.file_count,
            "project_id": self.project_id,
        }


@dataclass(frozen=True, slots=True)
class PortableImportResult:
    """Public result for an atomic project import."""

    project_directory: str
    project_id: str
    completed_run_count: int
    file_count: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "completed_run_count": self.completed_run_count,
            "file_count": self.file_count,
            "project_directory": self.project_directory,
            "project_id": self.project_id,
        }
