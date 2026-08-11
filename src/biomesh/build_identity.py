"""Strict, deterministic installed-build provenance records for P5-WP02."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import PurePosixPath
from typing import Any, Literal, cast

from biomesh import __version__

BUILD_PROVENANCE_RESOURCE = "_build_provenance.json"
SOURCE_IDENTITY_POLICY = "git-head-ls-tree-sha256-v1"
ArtifactKind = Literal["wheel", "sdist", "linux_installer"]

_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_ARTIFACT_KINDS: frozenset[str] = frozenset({"wheel", "sdist", "linux_installer"})
_REQUIRED_BUILD_TOOLS = frozenset(
    {"biomesh-provenance-builder", "git", "hatchling", "python"}
)


class BuildProvenanceError(ValueError):
    """Raised when build provenance is unavailable, ambiguous, or inconsistent."""


@dataclass(frozen=True, slots=True, order=True)
class BuildTool:
    """One exact tool in the declared deterministic build toolchain."""

    name: str
    version: str

    def __post_init__(self) -> None:
        _nonblank("build tool name", self.name)
        _nonblank("build tool version", self.version)

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


@dataclass(frozen=True, slots=True)
class BuildIdentity:
    """Exact clean source and toolchain identity embedded in a distribution."""

    package_name: str
    package_version: str
    source_commit: str
    source_tree_sha256: str
    source_identity_policy: str
    build_tools: tuple[BuildTool, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise BuildProvenanceError("unsupported build provenance schema version")
        if self.package_name != "biomesh":
            raise BuildProvenanceError("build provenance package name is inconsistent")
        _nonblank("package version", self.package_version)
        if not _COMMIT_PATTERN.fullmatch(self.source_commit):
            raise BuildProvenanceError("source commit is malformed")
        _sha256("source tree identity", self.source_tree_sha256)
        if self.source_identity_policy != SOURCE_IDENTITY_POLICY:
            raise BuildProvenanceError("source identity policy is unsupported")
        if not self.build_tools:
            raise BuildProvenanceError("build tool identity is missing")
        names = [tool.name for tool in self.build_tools]
        if len(names) != len(set(names)):
            raise BuildProvenanceError("build tool identity contains duplicates")
        if set(names) != _REQUIRED_BUILD_TOOLS:
            raise BuildProvenanceError(
                "build tool identity is incomplete or unexpected"
            )
        if tuple(sorted(self.build_tools)) != self.build_tools:
            raise BuildProvenanceError("build tool identity is not canonical")

    def as_dict(self) -> dict[str, object]:
        return {
            "build_tools": [tool.as_dict() for tool in self.build_tools],
            "package_name": self.package_name,
            "package_version": self.package_version,
            "schema_version": self.schema_version,
            "source_commit": self.source_commit,
            "source_identity_policy": self.source_identity_policy,
            "source_tree_sha256": self.source_tree_sha256,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.as_dict())

    @classmethod
    def from_dict(cls, value: object) -> BuildIdentity:
        data = _exact_object(
            value,
            {
                "build_tools",
                "package_name",
                "package_version",
                "schema_version",
                "source_commit",
                "source_identity_policy",
                "source_tree_sha256",
            },
            "build provenance",
        )
        tools_value = data["build_tools"]
        if not isinstance(tools_value, list):
            raise BuildProvenanceError("build_tools must be a list")
        tools: list[BuildTool] = []
        for item in tools_value:
            tool = _exact_object(item, {"name", "version"}, "build tool")
            tools.append(
                BuildTool(
                    name=_string(tool["name"], "build tool name"),
                    version=_string(tool["version"], "build tool version"),
                )
            )
        return cls(
            schema_version=_integer(data["schema_version"], "schema_version"),
            package_name=_string(data["package_name"], "package_name"),
            package_version=_string(data["package_version"], "package_version"),
            source_commit=_string(data["source_commit"], "source_commit"),
            source_tree_sha256=_string(
                data["source_tree_sha256"], "source_tree_sha256"
            ),
            source_identity_policy=_string(
                data["source_identity_policy"], "source_identity_policy"
            ),
            build_tools=tuple(tools),
        )

    @classmethod
    def from_bytes(cls, contents: bytes) -> BuildIdentity:
        value = strict_json_loads(contents)
        identity = cls.from_dict(value)
        if identity.to_bytes() != contents:
            raise BuildProvenanceError("build provenance JSON is not canonical")
        return identity


@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    """Raw SHA-256 and size identity of one publishable artifact."""

    kind: ArtifactKind
    filename: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if self.kind not in _ARTIFACT_KINDS:
            raise BuildProvenanceError("artifact kind is unsupported")
        path = PurePosixPath(self.filename)
        if (
            not self.filename
            or path.is_absolute()
            or len(path.parts) != 1
            or path.name != self.filename
            or self.filename in {".", ".."}
        ):
            raise BuildProvenanceError("artifact filename must be one safe basename")
        _sha256("artifact SHA-256", self.sha256)
        if (
            not isinstance(self.size_bytes, int)
            or isinstance(self.size_bytes, bool)
            or self.size_bytes < 1
        ):
            raise BuildProvenanceError("artifact size must be a positive integer")

    def as_dict(self) -> dict[str, int | str]:
        return {
            "filename": self.filename,
            "kind": self.kind,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, value: object) -> ArtifactIdentity:
        data = _exact_object(
            value, {"filename", "kind", "sha256", "size_bytes"}, "artifact"
        )
        kind = _string(data["kind"], "artifact kind")
        if kind not in _ARTIFACT_KINDS:
            raise BuildProvenanceError("artifact kind is unsupported")
        return cls(
            kind=cast(ArtifactKind, kind),
            filename=_string(data["filename"], "artifact filename"),
            sha256=_string(data["sha256"], "artifact SHA-256"),
            size_bytes=_integer(data["size_bytes"], "artifact size"),
        )


@dataclass(frozen=True, slots=True)
class PublicationManifest:
    """Complete cross-artifact binding for one publishable distribution set."""

    build: BuildIdentity
    artifacts: tuple[ArtifactIdentity, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise BuildProvenanceError("unsupported publication schema version")
        if tuple(sorted(self.artifacts, key=lambda item: item.kind)) != self.artifacts:
            raise BuildProvenanceError("artifact records are not canonical")
        kinds = [artifact.kind for artifact in self.artifacts]
        names = [artifact.filename for artifact in self.artifacts]
        if set(kinds) != _ARTIFACT_KINDS or len(kinds) != len(_ARTIFACT_KINDS):
            raise BuildProvenanceError(
                "publication must contain exactly one wheel, sdist, and installer"
            )
        if len(names) != len(set(names)):
            raise BuildProvenanceError("publication contains duplicate artifact names")

    def as_dict(self) -> dict[str, object]:
        return {
            "artifacts": [artifact.as_dict() for artifact in self.artifacts],
            "build": self.build.as_dict(),
            "schema_version": self.schema_version,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.as_dict())

    @classmethod
    def from_bytes(cls, contents: bytes) -> PublicationManifest:
        value = strict_json_loads(contents)
        data = _exact_object(
            value, {"artifacts", "build", "schema_version"}, "publication manifest"
        )
        artifacts_value = data["artifacts"]
        if not isinstance(artifacts_value, list):
            raise BuildProvenanceError("artifacts must be a list")
        manifest = cls(
            schema_version=_integer(data["schema_version"], "schema_version"),
            build=BuildIdentity.from_dict(data["build"]),
            artifacts=tuple(
                ArtifactIdentity.from_dict(item) for item in artifacts_value
            ),
        )
        if manifest.to_bytes() != contents:
            raise BuildProvenanceError("publication manifest JSON is not canonical")
        return manifest


def canonical_json_bytes(value: object) -> bytes:
    """Serialize one manifest deterministically with a final newline."""
    return (
        json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()


def strict_json_loads(contents: bytes) -> object:
    """Load UTF-8 JSON while rejecting duplicate keys at every object depth."""

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise BuildProvenanceError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    try:
        return json.loads(contents.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BuildProvenanceError("provenance JSON is malformed") from error


def load_embedded_build_identity() -> BuildIdentity:
    """Load the package-owned provenance resource without external state."""
    resource = files("biomesh").joinpath(BUILD_PROVENANCE_RESOURCE)
    try:
        contents = resource.read_bytes()
    except (FileNotFoundError, OSError) as error:
        raise BuildProvenanceError(
            "installed build provenance is missing; this is not a publishable "
            "exact build"
        ) from error
    identity = BuildIdentity.from_bytes(contents)
    if identity.package_version != __version__:
        raise BuildProvenanceError(
            "installed build provenance package version is inconsistent"
        )
    return identity


def sha256_bytes(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _exact_object(value: object, expected: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        raise BuildProvenanceError(f"{label} fields are missing or unexpected")
    if any(not isinstance(key, str) for key in value):
        raise BuildProvenanceError(f"{label} field names must be strings")
    return cast(dict[str, object], value)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise BuildProvenanceError(f"{label} must be a string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise BuildProvenanceError(f"{label} must be an integer")
    return value


def _nonblank(label: str, value: str) -> None:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise BuildProvenanceError(f"{label} must be a nonblank canonical string")


def _sha256(label: str, value: str) -> None:
    if not _SHA256_PATTERN.fullmatch(value):
        raise BuildProvenanceError(f"{label} is malformed")
