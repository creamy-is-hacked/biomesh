"""P5-WP05 manifest-bound Linux installer lifecycle operations."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, cast

from biomesh.build_identity import canonical_json_bytes, strict_json_loads
from biomesh.linux_packaging import verify_installer_supply

OWNED_MANIFEST = ".biomesh-owned.json"
LIFECYCLE_SCHEMA_VERSION = 1
JOURNAL_SCHEMA_VERSION = 2
_VERSION_PATTERN = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]*")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_ROLES = frozenset({"application", "dependency", "launcher", "metadata"})
_LAUNCHERS = ("biomesh", "biomesh-gui")


class InstallerLifecycleError(ValueError):
    """Raised when a lifecycle operation cannot proceed safely."""


class LifecycleInterruption(RuntimeError):
    """Testable interruption that deliberately preserves the transaction journal."""


@dataclass(frozen=True, slots=True, order=True)
class OwnedFile:
    """One regular file owned by one installed BioMesh version."""

    path: str
    role: Literal["application", "dependency", "launcher", "metadata"]
    sha256: str
    size_bytes: int
    owner_version: str

    def __post_init__(self) -> None:
        _safe_relative_path(self.path, "owned file")
        if self.role not in _ROLES:
            raise InstallerLifecycleError("owned file role is unsupported")
        _sha256("owned file SHA-256", self.sha256)
        if self.size_bytes < 0:
            raise InstallerLifecycleError("owned file size must not be negative")
        _version(self.owner_version)

    def as_dict(self) -> dict[str, int | str]:
        return {
            "owner_version": self.owner_version,
            "path": self.path,
            "role": self.role,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, value: object) -> OwnedFile:
        item = _exact_object(
            value,
            {"owner_version", "path", "role", "sha256", "size_bytes"},
            "owned file",
        )
        role = _string(item["role"], "owned file role")
        if role not in _ROLES:
            raise InstallerLifecycleError("owned file role is unsupported")
        return cls(
            path=_string(item["path"], "owned file path"),
            role=cast(
                Literal["application", "dependency", "launcher", "metadata"],
                role,
            ),
            sha256=_string(item["sha256"], "owned file SHA-256"),
            size_bytes=_integer(item["size_bytes"], "owned file size"),
            owner_version=_string(item["owner_version"], "owned file owner"),
        )


@dataclass(frozen=True, slots=True)
class OwnedFileManifest:
    """Canonical ownership and supply-chain identity for one version tree."""

    version: str
    files: tuple[OwnedFile, ...]
    wheel_sha256: str
    provenance_sha256: str
    schema_version: int = LIFECYCLE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _version(self.version)
        if self.schema_version != LIFECYCLE_SCHEMA_VERSION:
            raise InstallerLifecycleError("owned-file manifest schema is unsupported")
        if not self.files:
            raise InstallerLifecycleError("owned-file manifest is empty")
        paths = [record.path for record in self.files]
        if len(paths) != len(set(paths)):
            raise InstallerLifecycleError("owned-file manifest has duplicate paths")
        if tuple(sorted(self.files)) != self.files:
            raise InstallerLifecycleError("owned-file manifest paths are not canonical")
        if any(record.owner_version != self.version for record in self.files):
            raise InstallerLifecycleError("owned-file ownership version is mismatched")
        if not {f"bin/{name}" for name in _LAUNCHERS}.issubset(paths):
            raise InstallerLifecycleError(
                "owned-file manifest omits required launchers"
            )
        _sha256("wheel SHA-256", self.wheel_sha256)
        _sha256("provenance SHA-256", self.provenance_sha256)

    def as_dict(self) -> dict[str, object]:
        return {
            "files": [record.as_dict() for record in self.files],
            "provenance_sha256": self.provenance_sha256,
            "schema_version": self.schema_version,
            "version": self.version,
            "wheel_sha256": self.wheel_sha256,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.as_dict())

    @classmethod
    def from_bytes(cls, contents: bytes) -> OwnedFileManifest:
        value = _exact_object(
            strict_json_loads(contents),
            {"files", "provenance_sha256", "schema_version", "version", "wheel_sha256"},
            "owned-file manifest",
        )
        files = value["files"]
        if not isinstance(files, list):
            raise InstallerLifecycleError("owned-file manifest files must be a list")
        result = cls(
            version=_string(value["version"], "owned-file manifest version"),
            files=tuple(OwnedFile.from_dict(item) for item in files),
            wheel_sha256=_string(value["wheel_sha256"], "wheel SHA-256"),
            provenance_sha256=_string(value["provenance_sha256"], "provenance SHA-256"),
            schema_version=_integer(value["schema_version"], "schema version"),
        )
        if result.to_bytes() != contents:
            raise InstallerLifecycleError("owned-file manifest JSON is not canonical")
        return result


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Explicit verification result without silent file correction."""

    version: str
    manifest_sha256: str
    mismatches: tuple[str, ...]
    wheel_sha256: str = "0" * 64
    provenance_sha256: str = "0" * 64

    @property
    def verified(self) -> bool:
        return not self.mismatches


SmokeRunner = Callable[[Path], None]
FaultHook = Callable[[str], None]


def build_owned_file_manifest(
    candidate: Path,
    *,
    version: str,
    wheel_sha256: str,
    provenance_sha256: str,
) -> OwnedFileManifest:
    """Inventory a prebuilt candidate without following links or mutating a prefix."""
    _version(version)
    _sha256("wheel SHA-256", wheel_sha256)
    _sha256("provenance SHA-256", provenance_sha256)
    files = tuple(
        OwnedFile(
            path=relative,
            role=_file_role(relative),
            sha256=_digest(path.read_bytes()),
            size_bytes=path.stat().st_size,
            owner_version=version,
        )
        for relative, path in _regular_tree(candidate)
    )
    return OwnedFileManifest(
        version=version,
        files=files,
        wheel_sha256=wheel_sha256,
        provenance_sha256=provenance_sha256,
    )


class InstallerLifecycle:
    """Side-by-side installer with one atomic current-version pointer."""

    def __init__(
        self,
        prefix: Path,
        *,
        smoke_runner: SmokeRunner | None = None,
        fault_hook: FaultHook | None = None,
    ) -> None:
        if not prefix.is_absolute():
            raise InstallerLifecycleError("install prefix must be absolute")
        self.prefix = prefix
        self.root = prefix / "lib" / "biomesh"
        self.versions = self.root / "versions"
        self.current = self.root / "current"
        self.journal = self.root / ".lifecycle-transaction.json"
        self.logs = self.root / "lifecycle-logs"
        self.recovery = self.root / "recovery"
        self._smoke_runner = smoke_runner or _installed_smoke
        self._fault_hook = fault_hook

    def install(
        self,
        candidate: Path,
        manifest_bytes: bytes,
        *,
        upgrade: bool = False,
        acknowledge_paths: Sequence[str] = (),
    ) -> VerificationResult:
        """Publish and activate a verified fresh or upgrade candidate."""
        operation = "upgrade" if upgrade else "install"
        manifest = OwnedFileManifest.from_bytes(manifest_bytes)
        manifest_sha256 = _digest(manifest_bytes)
        self._preflight_target()
        candidate_result = _verify_tree(candidate, manifest, manifest_sha256)
        _require_verified(operation, candidate_result)
        current_result = self.verify_current(require=upgrade)
        if upgrade:
            if current_result is None:
                raise InstallerLifecycleError("upgrade requires a current installation")
            self._acknowledge(operation, current_result, acknowledge_paths)
            if current_result.version == manifest.version:
                raise InstallerLifecycleError(
                    "upgrade candidate version is already current"
                )
        elif current_result is not None:
            raise InstallerLifecycleError(
                "fresh install requires no current installation"
            )
        existing = self._find_version(manifest.version)
        if existing is not None:
            raise InstallerLifecycleError(
                f"{operation} target version already exists: {manifest.version}"
            )
        self._preflight_launchers(expect_existing=upgrade)

        version_name = _version_directory_name(manifest.version, manifest_sha256)
        stage_name = f".stage-{version_name}"
        previous = None if current_result is None else current_result.version
        journal = self._journal_value(
            operation=operation,
            phase="prepared",
            from_version=previous,
            from_identity=current_result,
            target_version=manifest.version,
            version_name=version_name,
            stage_name=stage_name,
            manifest_sha256=manifest_sha256,
            wheel_sha256=manifest.wheel_sha256,
            provenance_sha256=manifest.provenance_sha256,
            affected_paths=tuple(acknowledge_paths),
            quarantine=False,
        )
        self._begin(journal)
        try:
            self._preflight_target(allow_journal=True)
            stage = _safe_child_path(self.versions, stage_name, "staging directory")
            stage.mkdir(mode=0o700)
            for record in manifest.files:
                source = candidate / record.path
                target = stage / record.path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target, follow_symlinks=False)
                target.chmod(source.stat().st_mode & 0o777)
            (stage / OWNED_MANIFEST).write_bytes(manifest_bytes)
            self._update_phase(journal, "staged")
            self._fault("staged")

            self._preflight_target(allow_journal=True)
            published = _safe_child_path(
                self.versions, version_name, "published version directory"
            )
            if published.exists() or published.is_symlink():
                raise InstallerLifecycleError(
                    "published version directory already exists"
                )
            os.replace(stage, published)
            self._update_phase(journal, "published")
            self._fault("published")
            _require_verified(operation, self._verify_path(published))
            self._smoke_runner(published)
            self._ensure_launchers()
            self._update_phase(journal, "verified")
            self._fault("verified")
            self._switch_current(version_name)
            self._update_phase(journal, "activated")
            self._fault("activated")
            result = self._verify_path(published, activation=True)
            _require_verified(operation, result)
            self._log(
                operation,
                previous,
                manifest.version,
                manifest_sha256,
                manifest.wheel_sha256,
                manifest.provenance_sha256,
                "activated",
                tuple(acknowledge_paths),
                "not_required",
            )
            self.journal.unlink()
            return result
        except LifecycleInterruption:
            raise
        except Exception as error:
            self._abort_candidate(version_name, stage_name)
            self._log(
                operation,
                previous,
                manifest.version,
                manifest_sha256,
                manifest.wheel_sha256,
                manifest.provenance_sha256,
                "rejected",
                tuple(acknowledge_paths),
                "prior_current_retained",
            )
            if self.journal.exists():
                self.journal.unlink()
            if isinstance(error, InstallerLifecycleError):
                raise
            raise InstallerLifecycleError(f"{operation} failed: {error}") from error

    def rollback(self, version: str) -> VerificationResult:
        """Atomically reactivate one exact, already installed verified version."""
        _version(version)
        current_result = self.verify_current(require=True)
        assert current_result is not None
        _require_verified("rollback current", current_result)
        if current_result.version == version:
            raise InstallerLifecycleError("rollback target is already current")
        target = self._find_version(version)
        if target is None:
            raise InstallerLifecycleError(f"rollback target is absent: {version}")
        result = self._verify_path(target)
        _require_verified("rollback target", result)
        self._preflight_launchers(expect_existing=True)
        self._smoke_runner(target)
        journal = self._journal_value(
            operation="rollback",
            phase="prepared",
            from_version=current_result.version,
            from_identity=current_result,
            target_version=version,
            version_name=target.name,
            stage_name="",
            manifest_sha256=result.manifest_sha256,
            wheel_sha256=result.wheel_sha256,
            provenance_sha256=result.provenance_sha256,
            affected_paths=(),
            quarantine=False,
        )
        self._begin(journal)
        self._fault("rollback-prepared")
        self._switch_current(target.name)
        self._update_phase(journal, "activated")
        self._fault("rollback-activated")
        activated = self._verify_path(target, activation=True)
        _require_verified("rollback", activated)
        self._log(
            "rollback",
            current_result.version,
            version,
            result.manifest_sha256,
            result.wheel_sha256,
            result.provenance_sha256,
            "activated",
            (),
            "not_required",
        )
        self.journal.unlink()
        return activated

    def uninstall(
        self,
        version: str,
        *,
        acknowledge_paths: Sequence[str] = (),
        quarantine_modified: bool = False,
    ) -> None:
        """Remove only a proven version tree or quarantine explicitly named changes."""
        _version(version)
        self._preflight_target()
        target = self._find_version(version)
        if target is None:
            raise InstallerLifecycleError(f"uninstall target is absent: {version}")
        result = self._verify_path(target)
        if result.mismatches:
            self._acknowledge("uninstall", result, acknowledge_paths)
            if not quarantine_modified:
                raise InstallerLifecycleError(
                    "uninstall recovery must quarantine acknowledged modified paths"
                )
        elif acknowledge_paths:
            raise InstallerLifecycleError("uninstall acknowledgement names no mismatch")
        current_name = self._current_name()
        is_current = current_name == target.name
        if is_current and any(path != target for path in self._installed_paths()):
            raise InstallerLifecycleError(
                "uninstall current version requires rollback or removal of "
                "other versions"
            )
        if is_current:
            self._preflight_launchers(expect_existing=True)
        manifest_sha256 = result.manifest_sha256
        retired_name = f".retired-{target.name}"
        journal = self._journal_value(
            operation="uninstall",
            phase="prepared",
            from_version=version if is_current else None,
            from_identity=result if is_current else None,
            target_version=version,
            version_name=target.name,
            stage_name=retired_name,
            manifest_sha256=manifest_sha256,
            wheel_sha256=result.wheel_sha256,
            provenance_sha256=result.provenance_sha256,
            affected_paths=tuple(acknowledge_paths),
            quarantine=quarantine_modified,
        )
        self._begin(journal)
        self._fault("uninstall-prepared")
        if is_current:
            self.current.unlink()
            self._fault("uninstall-current-unlinked")
            self._update_phase(journal, "deactivated")
            self._fault("uninstall-deactivated")
            self._remove_launchers()
            self._update_phase(journal, "launchers-removed")
            self._fault("uninstall-launchers-removed")
        self._preflight_target(allow_journal=True)
        retired = _safe_child_path(self.versions, retired_name, "retired directory")
        if retired.exists() or retired.is_symlink():
            raise InstallerLifecycleError("retired directory already exists")
        os.replace(target, retired)
        self._fault("uninstall-target-retired")
        self._update_phase(journal, "retired")
        self._fault("uninstall-retired")
        recovery_result = "not_required"
        if quarantine_modified:
            self._preflight_target(allow_journal=True)
            self.recovery.mkdir(parents=True, exist_ok=True)
            quarantine = _safe_child_path(
                self.recovery, target.name, "recovery quarantine directory"
            )
            if quarantine.exists() or quarantine.is_symlink():
                raise InstallerLifecycleError(
                    "uninstall recovery target already exists"
                )
            os.replace(retired, quarantine)
            self._fault("uninstall-quarantined")
            recovery_result = "modified_tree_quarantined"
        else:
            shutil.rmtree(retired)
            self._fault("uninstall-removed")
        self._log(
            "uninstall",
            version if is_current else self.current_version(),
            None,
            manifest_sha256,
            result.wheel_sha256,
            result.provenance_sha256,
            "removed" if not quarantine_modified else "quarantined",
            tuple(acknowledge_paths),
            recovery_result,
        )
        self.journal.unlink()

    def recover(self) -> str:
        """Deterministically resolve the one recorded interrupted transaction."""
        self._preflight_target(allow_journal=True)
        if not self.journal.is_file() or self.journal.is_symlink():
            raise InstallerLifecycleError("no recoverable lifecycle transaction exists")
        data = self._load_journal()
        operation = _string(data["operation"], "journal operation")
        phase = _string(data["phase"], "journal phase")
        version_name = _string(data["version_name"], "journal version directory")
        stage_name = _string(data["stage_name"], "journal staging directory")
        from_version = _optional_string(
            data["from_version"], "journal source version"
        )
        from_manifest_sha256 = _optional_string(
            data["from_manifest_sha256"], "journal source manifest SHA-256"
        )
        from_wheel_sha256 = _optional_string(
            data["from_wheel_sha256"], "journal source wheel SHA-256"
        )
        from_provenance_sha256 = _optional_string(
            data["from_provenance_sha256"],
            "journal source provenance SHA-256",
        )
        target_version = _string(data["target_version"], "journal target version")
        manifest_sha256 = _string(data["manifest_sha256"], "journal manifest SHA-256")
        wheel_sha256 = _string(data["wheel_sha256"], "journal wheel SHA-256")
        provenance_sha256 = _string(
            data["provenance_sha256"], "journal provenance SHA-256"
        )
        _sha256("journal manifest SHA-256", manifest_sha256)
        _sha256("journal wheel SHA-256", wheel_sha256)
        _sha256("journal provenance SHA-256", provenance_sha256)
        affected = _string_list(data["affected_paths"], "journal affected paths")
        self._validate_journal_paths(
            operation=operation,
            phase=phase,
            from_version=from_version,
            from_manifest_sha256=from_manifest_sha256,
            from_wheel_sha256=from_wheel_sha256,
            from_provenance_sha256=from_provenance_sha256,
            target_version=target_version,
            version_name=version_name,
            stage_name=stage_name,
            manifest_sha256=manifest_sha256,
            wheel_sha256=wheel_sha256,
            provenance_sha256=provenance_sha256,
            quarantine=_boolean(data["quarantine"], "journal quarantine"),
        )
        if operation in {"install", "upgrade"}:
            current = self.verify_current()
            self._require_recovery_current_state(
                operation,
                current,
                from_version=from_version,
                from_manifest_sha256=from_manifest_sha256,
                from_wheel_sha256=from_wheel_sha256,
                from_provenance_sha256=from_provenance_sha256,
                target_version=target_version,
                manifest_sha256=manifest_sha256,
                wheel_sha256=wheel_sha256,
                provenance_sha256=provenance_sha256,
                source_mismatches=affected if operation == "upgrade" else (),
            )
            if operation == "upgrade":
                assert from_version is not None
                assert from_manifest_sha256 is not None
                assert from_wheel_sha256 is not None
                assert from_provenance_sha256 is not None
                self._require_recorded_version_tree(
                    "upgrade recovery source",
                    version_name=_version_directory_name(
                        from_version, from_manifest_sha256
                    ),
                    version=from_version,
                    manifest_sha256=from_manifest_sha256,
                    wheel_sha256=from_wheel_sha256,
                    provenance_sha256=from_provenance_sha256,
                    allowed_mismatches=affected,
                )
            target = _safe_child_path(
                self.versions, version_name, "recovery version directory"
            )
            if target.is_dir() and not target.is_symlink():
                result = self._verify_path(target)
                self._require_journal_identity(
                    "recovery candidate",
                    result,
                    target_version=target_version,
                    manifest_sha256=manifest_sha256,
                    wheel_sha256=wheel_sha256,
                    provenance_sha256=provenance_sha256,
                )
                _require_verified("recovery candidate", result)
                self._smoke_runner(target)
                self._ensure_launchers()
                self._switch_current(version_name)
                outcome = "verified_candidate_activated"
            else:
                if phase not in {"prepared", "staged"}:
                    raise InstallerLifecycleError(
                        "recorded recovery candidate is missing"
                    )
                stage = _safe_child_path(
                    self.versions, stage_name, "recovery staging directory"
                )
                if phase == "staged":
                    if not stage.is_dir() or stage.is_symlink():
                        raise InstallerLifecycleError(
                            "recorded recovery staging tree is missing"
                        )
                    staged = self._verify_path(stage, expected_name=version_name)
                    self._require_journal_identity(
                        "recovery staging candidate",
                        staged,
                        target_version=target_version,
                        manifest_sha256=manifest_sha256,
                        wheel_sha256=wheel_sha256,
                        provenance_sha256=provenance_sha256,
                    )
                    _require_verified("recovery staging candidate", staged)
                if stage.exists() and not stage.is_symlink():
                    shutil.rmtree(stage)
                outcome = "staging_removed_prior_current_retained"
            self._log(
                operation,
                from_version,
                target_version,
                manifest_sha256,
                wheel_sha256,
                provenance_sha256,
                "recovered",
                affected,
                outcome,
            )
        elif operation == "rollback":
            current = self.verify_current(require=True)
            assert current is not None
            assert from_version is not None
            assert from_manifest_sha256 is not None
            assert from_wheel_sha256 is not None
            assert from_provenance_sha256 is not None
            self._require_recorded_version_tree(
                "rollback recovery source",
                version_name=_version_directory_name(
                    from_version, from_manifest_sha256
                ),
                version=from_version,
                manifest_sha256=from_manifest_sha256,
                wheel_sha256=from_wheel_sha256,
                provenance_sha256=from_provenance_sha256,
            )
            self._require_recorded_version_tree(
                "rollback recovery target",
                version_name=version_name,
                version=target_version,
                manifest_sha256=manifest_sha256,
                wheel_sha256=wheel_sha256,
                provenance_sha256=provenance_sha256,
            )
            self._require_recovery_current_state(
                operation,
                current,
                from_version=from_version,
                from_manifest_sha256=from_manifest_sha256,
                from_wheel_sha256=from_wheel_sha256,
                from_provenance_sha256=from_provenance_sha256,
                target_version=target_version,
                manifest_sha256=manifest_sha256,
                wheel_sha256=wheel_sha256,
                provenance_sha256=provenance_sha256,
                source_mismatches=(),
            )
            outcome = f"verified_current_retained:{current.version}"
            self._log(
                operation,
                from_version,
                current.version,
                current.manifest_sha256,
                current.wheel_sha256,
                current.provenance_sha256,
                "recovered",
                (),
                outcome,
            )
        elif operation == "uninstall":
            retired = _safe_child_path(
                self.versions, stage_name, "recovery retired directory"
            )
            target = _safe_child_path(
                self.versions, version_name, "recovery version directory"
            )
            if phase == "retired":
                if target.exists():
                    raise InstallerLifecycleError(
                        "uninstall recovery target conflicts with retired phase"
                    )
                if retired.exists() and not retired.is_dir():
                    raise InstallerLifecycleError(
                        "uninstall recovery retired tree is not a directory"
                    )
                if retired.is_dir() and not retired.is_symlink():
                    quarantine_requested = _boolean(
                        data["quarantine"], "journal quarantine"
                    )
                    allowed_mismatches = affected if quarantine_requested else ()
                    self._verify_journal_tree(
                        retired,
                        version_name=version_name,
                        target_version=target_version,
                        manifest_sha256=manifest_sha256,
                        wheel_sha256=wheel_sha256,
                        provenance_sha256=provenance_sha256,
                        allowed_mismatches=allowed_mismatches,
                    )
                    if quarantine_requested:
                        self._preflight_target(allow_journal=True)
                        self.recovery.mkdir(parents=True, exist_ok=True)
                        quarantine = _safe_child_path(
                            self.recovery,
                            version_name,
                            "recovery quarantine directory",
                        )
                        if quarantine.exists() or quarantine.is_symlink():
                            raise InstallerLifecycleError(
                                "recovery quarantine target already exists"
                            )
                        os.replace(retired, quarantine)
                        outcome = "retired_tree_quarantined"
                    else:
                        shutil.rmtree(retired)
                        outcome = "retired_tree_removed"
                else:
                    if _boolean(data["quarantine"], "journal quarantine"):
                        quarantine = _safe_child_path(
                            self.recovery,
                            version_name,
                            "recovery quarantine directory",
                        )
                        if not quarantine.is_dir() or quarantine.is_symlink():
                            raise InstallerLifecycleError(
                                "recorded uninstall quarantine is missing"
                            )
                        self._verify_journal_tree(
                            quarantine,
                            version_name=version_name,
                            target_version=target_version,
                            manifest_sha256=manifest_sha256,
                            wheel_sha256=wheel_sha256,
                            provenance_sha256=provenance_sha256,
                            allowed_mismatches=affected,
                        )
                        outcome = "retired_tree_already_quarantined"
                    else:
                        raise InstallerLifecycleError(
                            "recorded uninstall retired tree is missing"
                        )
            else:
                target_present = target.is_dir() and not target.is_symlink()
                retired_present = retired.is_dir() and not retired.is_symlink()
                if target.exists() and not target_present:
                    raise InstallerLifecycleError(
                        "uninstall recovery target tree is not a directory"
                    )
                if retired.exists() and not retired_present:
                    raise InstallerLifecycleError(
                        "uninstall recovery retired tree is not a directory"
                    )
                if target_present == retired_present:
                    raise InstallerLifecycleError(
                        "uninstall recovery requires exactly one recorded version tree"
                    )
                recovery_tree = target if target_present else retired
                self._verify_journal_tree(
                    recovery_tree,
                    version_name=version_name,
                    target_version=target_version,
                    manifest_sha256=manifest_sha256,
                    wheel_sha256=wheel_sha256,
                    provenance_sha256=provenance_sha256,
                )
                restore_current = _optional_string(
                    data["from_version"], "journal source version"
                )
                if restore_current is not None:
                    self._preflight_recovery_activation(version_name)
                    self._smoke_runner(recovery_tree)
                if retired_present:
                    os.replace(retired, target)
                    self._verify_journal_tree(
                        target,
                        version_name=version_name,
                        target_version=target_version,
                        manifest_sha256=manifest_sha256,
                        wheel_sha256=wheel_sha256,
                        provenance_sha256=provenance_sha256,
                    )
                if restore_current is not None:
                    self._ensure_launchers()
                    self._switch_current(version_name)
                    activated = self._verify_path(target, activation=True)
                    self._require_journal_identity(
                        "uninstall recovery activation",
                        activated,
                        target_version=target_version,
                        manifest_sha256=manifest_sha256,
                        wheel_sha256=wheel_sha256,
                        provenance_sha256=provenance_sha256,
                    )
                    _require_verified("uninstall recovery activation", activated)
                outcome = "verified_installation_restored"
            self._log(
                operation,
                target_version,
                None,
                manifest_sha256,
                wheel_sha256,
                provenance_sha256,
                "recovered",
                affected,
                outcome,
            )
        else:
            raise InstallerLifecycleError("journal operation is unsupported")
        self.journal.unlink()
        return outcome

    def verify_current(self, *, require: bool = False) -> VerificationResult | None:
        """Verify the active pointer, manifest, files, and both stable launchers."""
        current_name = self._current_name()
        if current_name is None:
            if require:
                raise InstallerLifecycleError("no current BioMesh installation exists")
            return None
        target = _safe_child_path(
            self.versions, current_name, "current version directory"
        )
        if not target.is_dir() or target.is_symlink():
            raise InstallerLifecycleError(
                "current launcher target is missing or unsafe"
            )
        return self._verify_path(target, activation=True)

    def current_version(self) -> str | None:
        """Return the recorded active version without inferring missing identity."""
        result = self.verify_current()
        return None if result is None else result.version

    def _verify_path(
        self,
        target: Path,
        *,
        activation: bool = False,
        expected_name: str | None = None,
    ) -> VerificationResult:
        manifest_path = target / OWNED_MANIFEST
        if not manifest_path.is_file() or manifest_path.is_symlink():
            return VerificationResult(
                "UNKNOWN", "0" * 64, (f"missing:{OWNED_MANIFEST}",)
            )
        contents = manifest_path.read_bytes()
        try:
            manifest = OwnedFileManifest.from_bytes(contents)
        except (InstallerLifecycleError, ValueError) as error:
            return VerificationResult(
                "UNKNOWN", _digest(contents), (f"manifest:{error}",)
            )
        result = _verify_tree(target, manifest, _digest(contents), installed=True)
        manifest_name = _version_directory_name(
            manifest.version, result.manifest_sha256
        )
        mismatches = list(result.mismatches)
        owned_name = target.name if expected_name is None else expected_name
        if owned_name != manifest_name:
            mismatches.append(f"ownership-directory:{target.name}")
        if activation:
            if self._current_name() != target.name:
                mismatches.append("launcher-target:current")
            for name in _LAUNCHERS:
                launcher = self.prefix / "bin" / name
                expected = f"../lib/biomesh/current/bin/{name}"
                if not launcher.is_symlink() or os.readlink(launcher) != expected:
                    mismatches.append(f"launcher-target:bin/{name}")
        return VerificationResult(
            manifest.version,
            result.manifest_sha256,
            tuple(sorted(mismatches)),
            manifest.wheel_sha256,
            manifest.provenance_sha256,
        )

    def _verify_journal_tree(
        self,
        target: Path,
        *,
        version_name: str,
        target_version: str,
        manifest_sha256: str,
        wheel_sha256: str,
        provenance_sha256: str,
        allowed_mismatches: tuple[str, ...] = (),
    ) -> VerificationResult:
        result = self._verify_path(target, expected_name=version_name)
        self._require_journal_identity(
            "uninstall recovery",
            result,
            target_version=target_version,
            manifest_sha256=manifest_sha256,
            wheel_sha256=wheel_sha256,
            provenance_sha256=provenance_sha256,
        )
        expected_mismatches = tuple(sorted(set(allowed_mismatches)))
        if result.mismatches != expected_mismatches:
            detail = ", ".join(result.mismatches) or "none"
            expected = ", ".join(expected_mismatches) or "none"
            raise InstallerLifecycleError(
                "uninstall recovery verification failed: "
                f"observed mismatches {detail}; recorded mismatches {expected}"
            )
        return result

    @staticmethod
    def _require_journal_identity(
        operation: str,
        result: VerificationResult,
        *,
        target_version: str,
        manifest_sha256: str,
        wheel_sha256: str,
        provenance_sha256: str,
    ) -> None:
        mismatches: list[str] = []
        if result.version != target_version:
            mismatches.append("version")
        if result.manifest_sha256 != manifest_sha256:
            mismatches.append("manifest")
        if result.wheel_sha256 != wheel_sha256:
            mismatches.append("wheel")
        if result.provenance_sha256 != provenance_sha256:
            mismatches.append("provenance")
        if mismatches:
            raise InstallerLifecycleError(
                f"{operation} journal identity mismatch: {', '.join(mismatches)}"
            )

    def _require_recovery_current_state(
        self,
        operation: str,
        result: VerificationResult | None,
        *,
        from_version: str | None,
        from_manifest_sha256: str | None,
        from_wheel_sha256: str | None,
        from_provenance_sha256: str | None,
        target_version: str,
        manifest_sha256: str,
        wheel_sha256: str,
        provenance_sha256: str,
        source_mismatches: tuple[str, ...],
    ) -> None:
        """Accept only an exact source/target state recorded by the journal."""
        if result is None:
            if operation == "install" and from_version is None:
                return
            raise InstallerLifecycleError(
                f"{operation} recovery current state is missing"
            )
        expected_mismatches: tuple[str, ...]
        if result.version == target_version:
            expected_manifest = manifest_sha256
            expected_wheel = wheel_sha256
            expected_provenance = provenance_sha256
            expected_mismatches = ()
        elif result.version == from_version:
            if (
                from_version is None
                or from_manifest_sha256 is None
                or from_wheel_sha256 is None
                or from_provenance_sha256 is None
            ):
                raise InstallerLifecycleError(
                    f"{operation} recovery source identity is incomplete"
                )
            expected_manifest = from_manifest_sha256
            expected_wheel = from_wheel_sha256
            expected_provenance = from_provenance_sha256
            expected_mismatches = tuple(sorted(set(source_mismatches)))
        else:
            raise InstallerLifecycleError(
                f"{operation} recovery current version is not a recorded state: "
                f"{result.version}"
            )
        self._require_journal_identity(
            f"{operation} recovery current state",
            result,
            target_version=result.version,
            manifest_sha256=expected_manifest,
            wheel_sha256=expected_wheel,
            provenance_sha256=expected_provenance,
        )
        if result.mismatches != expected_mismatches:
            detail = ", ".join(result.mismatches) or "none"
            expected = ", ".join(expected_mismatches) or "none"
            raise InstallerLifecycleError(
                f"{operation} recovery current state mismatch: observed {detail}; "
                f"recorded {expected}"
            )

    def _require_recorded_version_tree(
        self,
        operation: str,
        *,
        version_name: str,
        version: str,
        manifest_sha256: str,
        wheel_sha256: str,
        provenance_sha256: str,
        allowed_mismatches: tuple[str, ...] = (),
    ) -> None:
        """Bind one retained side of a transaction to its complete journal identity."""
        target = _safe_child_path(
            self.versions, version_name, f"{operation} version directory"
        )
        if not target.is_dir() or target.is_symlink():
            raise InstallerLifecycleError(f"{operation} tree is missing or unsafe")
        result = self._verify_path(target)
        self._require_journal_identity(
            operation,
            result,
            target_version=version,
            manifest_sha256=manifest_sha256,
            wheel_sha256=wheel_sha256,
            provenance_sha256=provenance_sha256,
        )
        expected_mismatches = tuple(sorted(set(allowed_mismatches)))
        if result.mismatches != expected_mismatches:
            detail = ", ".join(result.mismatches) or "none"
            expected = ", ".join(expected_mismatches) or "none"
            raise InstallerLifecycleError(
                f"{operation} mismatch: observed {detail}; recorded {expected}"
            )

    def _find_version(self, version: str) -> Path | None:
        matches: list[Path] = []
        if self.versions.is_dir() and not self.versions.is_symlink():
            for path in self.versions.iterdir():
                if (
                    path.name.startswith(f"{version}-")
                    and path.is_dir()
                    and not path.is_symlink()
                ):
                    matches.append(path)
        if len(matches) > 1:
            raise InstallerLifecycleError(f"installed version is ambiguous: {version}")
        return None if not matches else matches[0]

    def _installed_paths(self) -> tuple[Path, ...]:
        if not self.versions.is_dir() or self.versions.is_symlink():
            return ()
        return tuple(
            sorted(
                path
                for path in self.versions.iterdir()
                if path.is_dir()
                and not path.is_symlink()
                and not path.name.startswith(".")
            )
        )

    def _acknowledge(
        self,
        operation: str,
        result: VerificationResult,
        acknowledge_paths: Sequence[str],
    ) -> None:
        if not result.mismatches:
            if acknowledge_paths:
                raise InstallerLifecycleError(
                    f"{operation} acknowledgement names no affected path"
                )
            return
        supplied = tuple(sorted(set(acknowledge_paths)))
        if supplied != result.mismatches:
            detail = ", ".join(result.mismatches)
            raise InstallerLifecycleError(
                f"{operation} blocked by owned-path changes: {detail}; "
                "explicit acknowledgement must match every affected path"
            )

    def _preflight_target(self, *, allow_journal: bool = False) -> None:
        for path, label in (
            (self.prefix, "installer prefix"),
            (self.prefix / "lib", "installer lib directory"),
            (self.prefix / "bin", "installer bin directory"),
            (self.root, "installer target root"),
            (self.versions, "installer versions root"),
            (self.logs, "installer lifecycle log directory"),
            (self.recovery, "installer recovery directory"),
        ):
            _reject_symlink_chain(path)
            if path.exists() and (not path.is_dir() or path.is_symlink()):
                raise InstallerLifecycleError(f"{label} is not a safe directory")
        if not allow_journal and (self.journal.exists() or self.journal.is_symlink()):
            raise InstallerLifecycleError(
                "an interrupted lifecycle transaction requires explicit recovery"
            )

    def _preflight_launchers(self, *, expect_existing: bool) -> None:
        _reject_symlink_chain(self.prefix / "bin")
        if (self.prefix / "bin").exists() and not (self.prefix / "bin").is_dir():
            raise InstallerLifecycleError("installer bin directory is not safe")
        for name in _LAUNCHERS:
            path = self.prefix / "bin" / name
            expected = f"../lib/biomesh/current/bin/{name}"
            if expect_existing:
                if not path.is_symlink() or os.readlink(path) != expected:
                    raise InstallerLifecycleError(
                        f"launcher ownership mismatch: bin/{name}"
                    )
            elif path.exists() or path.is_symlink():
                raise InstallerLifecycleError(f"unowned launcher exists: bin/{name}")

    def _ensure_launchers(self) -> None:
        bin_directory = self.prefix / "bin"
        self._preflight_target(allow_journal=True)
        bin_directory.mkdir(parents=True, exist_ok=True)
        self._preflight_target(allow_journal=True)
        for name in _LAUNCHERS:
            path = bin_directory / name
            expected = f"../lib/biomesh/current/bin/{name}"
            if path.is_symlink():
                if os.readlink(path) != expected:
                    raise InstallerLifecycleError(
                        f"launcher ownership mismatch: bin/{name}"
                    )
                continue
            if path.exists():
                raise InstallerLifecycleError(f"unowned launcher exists: bin/{name}")
            temporary = bin_directory / f".{name}.biomesh-new"
            if temporary.exists() or temporary.is_symlink():
                raise InstallerLifecycleError(
                    f"launcher staging path exists: {temporary}"
                )
            temporary.symlink_to(expected)
            os.replace(temporary, path)

    def _preflight_recovery_activation(self, version_name: str) -> None:
        current_name = self._current_name()
        if current_name not in {None, version_name}:
            raise InstallerLifecycleError(
                "uninstall recovery current pointer names a different version"
            )
        current_stage = _safe_child_path(
            self.root, ".current-new", "current pointer staging path"
        )
        if current_stage.exists() or current_stage.is_symlink():
            raise InstallerLifecycleError("current pointer staging path exists")
        bin_directory = self.prefix / "bin"
        _reject_symlink_chain(bin_directory)
        if bin_directory.exists() and (
            not bin_directory.is_dir() or bin_directory.is_symlink()
        ):
            raise InstallerLifecycleError("installer bin directory is not safe")
        for name in _LAUNCHERS:
            path = bin_directory / name
            expected = f"../lib/biomesh/current/bin/{name}"
            if path.is_symlink():
                if os.readlink(path) != expected:
                    raise InstallerLifecycleError(
                        f"launcher ownership mismatch: bin/{name}"
                    )
            elif path.exists():
                raise InstallerLifecycleError(f"unowned launcher exists: bin/{name}")
            temporary = bin_directory / f".{name}.biomesh-new"
            if temporary.exists() or temporary.is_symlink():
                raise InstallerLifecycleError(
                    f"launcher staging path exists: {temporary}"
                )

    def _remove_launchers(self) -> None:
        self._preflight_target(allow_journal=True)
        self._preflight_launchers(expect_existing=True)
        for name in _LAUNCHERS:
            (self.prefix / "bin" / name).unlink()
            self._fault(f"uninstall-launcher-{name}-removed")

    def _switch_current(self, version_name: str) -> None:
        self._preflight_target(allow_journal=True)
        target = _safe_child_path(
            self.versions, version_name, "version directory"
        )
        if not target.is_dir() or target.is_symlink():
            raise InstallerLifecycleError("activation target is missing or unsafe")
        temporary = _safe_child_path(
            self.root, ".current-new", "current pointer staging path"
        )
        if temporary.exists() or temporary.is_symlink():
            raise InstallerLifecycleError("current pointer staging path exists")
        temporary.symlink_to(f"versions/{version_name}")
        os.replace(temporary, self.current)

    def _current_name(self) -> str | None:
        if not self.current.exists() and not self.current.is_symlink():
            return None
        if not self.current.is_symlink():
            raise InstallerLifecycleError(
                "current installation pointer is not a symlink"
            )
        target = os.readlink(self.current)
        path = PurePosixPath(target)
        if len(path.parts) != 2 or path.parts[0] != "versions":
            raise InstallerLifecycleError(
                "current installation pointer escapes versions"
            )
        _safe_basename(path.parts[1], "current version directory")
        return path.parts[1]

    def _begin(self, journal: dict[str, object]) -> None:
        self._preflight_target(allow_journal=True)
        self.versions.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        self._preflight_target(allow_journal=True)
        _atomic_write(self.journal, canonical_json_bytes(journal))

    def _update_phase(self, journal: dict[str, object], phase: str) -> None:
        self._preflight_target(allow_journal=True)
        journal["phase"] = phase
        _atomic_write(self.journal, canonical_json_bytes(journal))

    def _journal_value(
        self,
        *,
        operation: str,
        phase: str,
        from_version: str | None,
        from_identity: VerificationResult | None,
        target_version: str,
        version_name: str,
        stage_name: str,
        manifest_sha256: str,
        wheel_sha256: str,
        provenance_sha256: str,
        affected_paths: tuple[str, ...],
        quarantine: bool,
    ) -> dict[str, object]:
        if (from_version is None) != (from_identity is None):
            raise InstallerLifecycleError(
                "journal source version and artifact identity must be recorded together"
            )
        if from_identity is not None and from_identity.version != from_version:
            raise InstallerLifecycleError(
                "journal source artifact version is inconsistent"
            )
        return {
            "affected_paths": list(affected_paths),
            "from_manifest_sha256": (
                None if from_identity is None else from_identity.manifest_sha256
            ),
            "from_provenance_sha256": (
                None if from_identity is None else from_identity.provenance_sha256
            ),
            "from_version": from_version,
            "from_wheel_sha256": (
                None if from_identity is None else from_identity.wheel_sha256
            ),
            "manifest_sha256": manifest_sha256,
            "operation": operation,
            "phase": phase,
            "provenance_sha256": provenance_sha256,
            "quarantine": quarantine,
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "stage_name": stage_name,
            "target_version": target_version,
            "version_name": version_name,
            "wheel_sha256": wheel_sha256,
        }

    def _load_journal(self) -> dict[str, object]:
        contents = self.journal.read_bytes()
        value = _exact_object(
            strict_json_loads(contents),
            {
                "affected_paths",
                "from_manifest_sha256",
                "from_provenance_sha256",
                "from_version",
                "from_wheel_sha256",
                "manifest_sha256",
                "operation",
                "phase",
                "provenance_sha256",
                "quarantine",
                "schema_version",
                "stage_name",
                "target_version",
                "version_name",
                "wheel_sha256",
            },
            "lifecycle journal",
        )
        if (
            _integer(value["schema_version"], "journal schema")
            != JOURNAL_SCHEMA_VERSION
        ):
            raise InstallerLifecycleError("lifecycle journal schema is unsupported")
        if canonical_json_bytes(value) != contents:
            raise InstallerLifecycleError("lifecycle journal JSON is not canonical")
        return value

    def _validate_journal_paths(
        self,
        *,
        operation: str,
        phase: str,
        from_version: str | None,
        from_manifest_sha256: str | None,
        from_wheel_sha256: str | None,
        from_provenance_sha256: str | None,
        target_version: str,
        version_name: str,
        stage_name: str,
        manifest_sha256: str,
        wheel_sha256: str,
        provenance_sha256: str,
        quarantine: bool,
    ) -> None:
        if operation not in {"install", "upgrade", "rollback", "uninstall"}:
            raise InstallerLifecycleError("journal operation is unsupported")
        phases = {
            "install": {"prepared", "staged", "published", "verified", "activated"},
            "upgrade": {"prepared", "staged", "published", "verified", "activated"},
            "rollback": {"prepared", "activated"},
            "uninstall": {
                "prepared",
                "deactivated",
                "launchers-removed",
                "retired",
            },
        }
        if phase not in phases[operation]:
            raise InstallerLifecycleError("journal phase is unsupported")
        _version(target_version)
        if from_version is not None:
            _version(from_version)
        source_hashes = (
            from_manifest_sha256,
            from_wheel_sha256,
            from_provenance_sha256,
        )
        if from_version is None:
            if any(value is not None for value in source_hashes):
                raise InstallerLifecycleError(
                    "journal source identity exists without a source version"
                )
        elif any(value is None for value in source_hashes):
            raise InstallerLifecycleError(
                "journal source artifact identity is incomplete"
            )
        else:
            assert from_manifest_sha256 is not None
            assert from_wheel_sha256 is not None
            assert from_provenance_sha256 is not None
            _sha256("journal source manifest SHA-256", from_manifest_sha256)
            _sha256("journal source wheel SHA-256", from_wheel_sha256)
            _sha256("journal source provenance SHA-256", from_provenance_sha256)
        _safe_basename(version_name, "journal version directory")
        expected_version_name = _version_directory_name(
            target_version, manifest_sha256
        )
        if version_name != expected_version_name:
            raise InstallerLifecycleError("journal version identity is inconsistent")
        expected_stage = {
            "install": f".stage-{version_name}",
            "upgrade": f".stage-{version_name}",
            "rollback": "",
            "uninstall": f".retired-{version_name}",
        }[operation]
        if stage_name != expected_stage:
            raise InstallerLifecycleError("journal staging identity is inconsistent")
        if stage_name:
            _safe_basename(stage_name, "journal staging directory")
        if operation == "install" and from_version is not None:
            raise InstallerLifecycleError(
                "install journal source version is unexpected"
            )
        if operation in {"upgrade", "rollback"}:
            if from_version is None:
                raise InstallerLifecycleError(
                    f"{operation} journal source version is missing"
                )
            if from_version == target_version:
                raise InstallerLifecycleError(
                    f"{operation} journal source and target versions are identical"
                )
        if (
            operation == "uninstall"
            and from_version is not None
            and from_version != target_version
        ):
            raise InstallerLifecycleError(
                "uninstall journal source version is inconsistent"
            )
        if operation == "uninstall" and from_version is not None:
            assert from_manifest_sha256 is not None
            assert from_wheel_sha256 is not None
            assert from_provenance_sha256 is not None
            if (
                from_manifest_sha256 != manifest_sha256
                or from_wheel_sha256 != wheel_sha256
                or from_provenance_sha256 != provenance_sha256
            ):
                raise InstallerLifecycleError(
                    "uninstall journal source artifact identity is inconsistent"
                )
        if operation != "uninstall" and quarantine:
            raise InstallerLifecycleError(
                "journal quarantine is unsupported for this operation"
            )

    def _abort_candidate(self, version_name: str, stage_name: str) -> None:
        try:
            self._preflight_target(allow_journal=True)
        except InstallerLifecycleError:
            return
        current_name = self._current_name()
        for name in (stage_name, version_name):
            try:
                path = _safe_child_path(self.versions, name, "abandoned candidate")
            except InstallerLifecycleError:
                continue
            if path.is_dir() and not path.is_symlink() and current_name != name:
                shutil.rmtree(path)
        if current_name is None:
            for name in _LAUNCHERS:
                launcher = self.prefix / "bin" / name
                expected = f"../lib/biomesh/current/bin/{name}"
                if launcher.is_symlink() and os.readlink(launcher) == expected:
                    launcher.unlink()

    def _fault(self, boundary: str) -> None:
        if self._fault_hook is not None:
            self._fault_hook(boundary)

    def _log(
        self,
        operation: str,
        from_version: str | None,
        target_version: str | None,
        manifest_sha256: str,
        wheel_sha256: str,
        provenance_sha256: str,
        result: str,
        affected_paths: tuple[str, ...],
        recovery_result: str,
    ) -> None:
        self._preflight_target(allow_journal=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        existing = sorted(self.logs.glob("*.json"))
        path = self.logs / f"{len(existing) + 1:06d}.json"
        record = {
            "affected_owned_paths": list(affected_paths),
            "from_version": from_version,
            "manifest_sha256": manifest_sha256,
            "operation": operation,
            "provenance_sha256": provenance_sha256,
            "recovery_result": recovery_result,
            "result": result,
            "schema_version": LIFECYCLE_SCHEMA_VERSION,
            "target_version": target_version,
            "wheel_sha256": wheel_sha256,
        }
        path.write_bytes(canonical_json_bytes(record))


def _verify_tree(
    root: Path,
    manifest: OwnedFileManifest,
    manifest_sha256: str,
    *,
    installed: bool = False,
) -> VerificationResult:
    try:
        actual = dict(_regular_tree(root, omit_manifest=installed))
    except InstallerLifecycleError as error:
        return VerificationResult(
            manifest.version,
            manifest_sha256,
            (f"tree:{error}",),
            manifest.wheel_sha256,
            manifest.provenance_sha256,
        )
    expected = {record.path: record for record in manifest.files}
    mismatches: list[str] = []
    for path in sorted(expected.keys() - actual.keys()):
        mismatches.append(f"missing:{path}")
    for path in sorted(actual.keys() - expected.keys()):
        mismatches.append(f"extra:{path}")
    for path in sorted(expected.keys() & actual.keys()):
        contents = actual[path].read_bytes()
        record = expected[path]
        if len(contents) != record.size_bytes or _digest(contents) != record.sha256:
            mismatches.append(f"modified:{path}")
    return VerificationResult(
        manifest.version,
        manifest_sha256,
        tuple(mismatches),
        manifest.wheel_sha256,
        manifest.provenance_sha256,
    )


def _regular_tree(
    root: Path, *, omit_manifest: bool = False
) -> tuple[tuple[str, Path], ...]:
    if not root.is_dir() or root.is_symlink():
        raise InstallerLifecycleError("candidate must be one regular directory")
    result: list[tuple[str, Path]] = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        for name in names:
            child = directory_path / name
            if child.is_symlink():
                raise InstallerLifecycleError(
                    f"candidate contains symlinked directory: {child.relative_to(root)}"
                )
        for name in filenames:
            path = directory_path / name
            relative = path.relative_to(root).as_posix()
            if omit_manifest and relative == OWNED_MANIFEST:
                continue
            if path.is_symlink() or not path.is_file():
                raise InstallerLifecycleError(
                    f"candidate contains non-regular payload: {relative}"
                )
            _safe_relative_path(relative, "candidate file")
            result.append((relative, path))
    result.sort(key=lambda item: item[0])
    if not result:
        raise InstallerLifecycleError("candidate tree is empty")
    return tuple(result)


def _installed_smoke(version_root: Path) -> None:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="biomesh-installer-smoke-") as config:
        environment["XDG_CONFIG_HOME"] = config
        commands = (
            (version_root / "bin" / "biomesh", "--help"),
            (version_root / "bin" / "biomesh-gui", "--smoke-test"),
        )
        for executable, argument in commands:
            completed = subprocess.run(
                [str(executable), argument],
                check=False,
                capture_output=True,
                env=environment,
                text=True,
                timeout=60,
            )
            if completed.returncode != 0:
                raise InstallerLifecycleError(
                    f"installed smoke failed for {executable.name}: "
                    f"{completed.stderr.strip()}"
                )


def _file_role(
    path: str,
) -> Literal["application", "dependency", "launcher", "metadata"]:
    if path.startswith("bin/"):
        return "launcher"
    if path == "python-path" or ".dist-info/" in path:
        return "metadata"
    if path.startswith("app/biomesh/"):
        return "application"
    return "dependency"


def _version_directory_name(version: str, manifest_sha256: str) -> str:
    return f"{version}-{manifest_sha256}"


def _require_verified(operation: str, result: VerificationResult) -> None:
    if result.mismatches:
        raise InstallerLifecycleError(
            f"{operation} verification failed for version {result.version}, "
            f"manifest {result.manifest_sha256}, wheel {result.wheel_sha256}, "
            f"provenance {result.provenance_sha256}: "
            f"{', '.join(result.mismatches)}"
        )


def _reject_symlink_chain(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise InstallerLifecycleError(f"installer target uses symlink: {current}")
        if not current.exists():
            break


def _atomic_write(path: Path, contents: bytes) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _safe_relative_path(value: str, label: str) -> None:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != value
        or value == OWNED_MANIFEST
    ):
        raise InstallerLifecycleError(f"{label} path is unsafe: {value}")


def _safe_child_path(parent: Path, name: str, label: str) -> Path:
    """Return one existing-parent child proven not to redirect outside it."""
    _safe_basename(name, label)
    _reject_symlink_chain(parent)
    if not parent.is_dir() or parent.is_symlink():
        raise InstallerLifecycleError(f"{label} parent is unsafe")
    child = parent / name
    if child.is_symlink():
        raise InstallerLifecycleError(f"{label} is a symlink")
    resolved_parent = parent.resolve()
    resolved_child = child.resolve(strict=False)
    if not resolved_child.is_relative_to(resolved_parent):
        raise InstallerLifecycleError(f"{label} escapes its parent")
    return child


def _safe_basename(value: str, label: str) -> None:
    path = PurePosixPath(value)
    if not value or path.name != value or value in {".", ".."}:
        raise InstallerLifecycleError(f"{label} is unsafe")


def _version(value: str) -> None:
    if not _VERSION_PATTERN.fullmatch(value) or value in {".", ".."}:
        raise InstallerLifecycleError("BioMesh version is malformed")


def _sha256(label: str, value: str) -> None:
    if not _SHA256_PATTERN.fullmatch(value):
        raise InstallerLifecycleError(f"{label} is malformed")


def _digest(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _exact_object(value: object, fields: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise InstallerLifecycleError(f"{label} fields are missing or unexpected")
    if any(not isinstance(key, str) for key in value):
        raise InstallerLifecycleError(f"{label} field names must be strings")
    return cast(dict[str, object], value)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise InstallerLifecycleError(f"{label} must be a string")
    return value


def _optional_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _string(value, label)


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise InstallerLifecycleError(f"{label} must be an integer")
    return value


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise InstallerLifecycleError(f"{label} must be a boolean")
    return value


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise InstallerLifecycleError(f"{label} must be a string list")
    return tuple(cast(list[str], value))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="biomesh-installer-lifecycle")
    commands = parser.add_subparsers(dest="command", required=True)
    apply = commands.add_parser("apply")
    apply.add_argument("operation", choices=("install", "upgrade"))
    apply.add_argument("--prefix", required=True, type=Path)
    apply.add_argument("--candidate", required=True, type=Path)
    apply.add_argument("--version", required=True)
    apply.add_argument("--wheel", required=True, type=Path)
    apply.add_argument("--build-provenance", required=True, type=Path)
    apply.add_argument("--artifact-binding", required=True, type=Path)
    apply.add_argument("--acknowledge-path", action="append", default=[])
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--prefix", required=True, type=Path)
    rollback.add_argument("--version", required=True)
    _add_supply_arguments(rollback)
    uninstall = commands.add_parser("uninstall")
    uninstall.add_argument("--prefix", required=True, type=Path)
    uninstall.add_argument("--version", required=True)
    uninstall.add_argument("--acknowledge-path", action="append", default=[])
    uninstall.add_argument("--quarantine-modified", action="store_true")
    _add_supply_arguments(uninstall)
    recover = commands.add_parser("recover")
    recover.add_argument("--prefix", required=True, type=Path)
    return parser


def _add_supply_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--build-provenance", required=True, type=Path)
    parser.add_argument("--artifact-binding", required=True, type=Path)


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the bundle-facing lifecycle command surface."""
    arguments = _parser().parse_args(argv)
    try:
        lifecycle = InstallerLifecycle(arguments.prefix)
        if arguments.command == "apply":
            supply = verify_installer_supply(
                arguments.wheel,
                build_provenance=arguments.build_provenance.read_bytes(),
                artifact_binding=arguments.artifact_binding.read_bytes(),
            )
            if supply.package_version != arguments.version:
                raise InstallerLifecycleError(
                    "candidate version does not match verified supply identity"
                )
            manifest = build_owned_file_manifest(
                arguments.candidate,
                version=arguments.version,
                wheel_sha256=supply.wheel_sha256,
                provenance_sha256=supply.provenance_sha256,
            )
            lifecycle.install(
                arguments.candidate,
                manifest.to_bytes(),
                upgrade=arguments.operation == "upgrade",
                acknowledge_paths=arguments.acknowledge_path,
            )
        elif arguments.command == "rollback":
            verify_installer_supply(
                arguments.wheel,
                build_provenance=arguments.build_provenance.read_bytes(),
                artifact_binding=arguments.artifact_binding.read_bytes(),
            )
            lifecycle.rollback(arguments.version)
        elif arguments.command == "uninstall":
            verify_installer_supply(
                arguments.wheel,
                build_provenance=arguments.build_provenance.read_bytes(),
                artifact_binding=arguments.artifact_binding.read_bytes(),
            )
            lifecycle.uninstall(
                arguments.version,
                acknowledge_paths=arguments.acknowledge_path,
                quarantine_modified=arguments.quarantine_modified,
            )
        elif arguments.command == "recover":
            lifecycle.recover()
        else:
            raise AssertionError("unhandled lifecycle command")
    except (InstallerLifecycleError, OSError, subprocess.SubprocessError) as error:
        print(f"installer lifecycle error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
