"""Run-level provenance collection for P1-WP07.

Provenance describes the execution environment and exact parameter document;
it does not supply or alter scientific inputs.
"""

from __future__ import annotations

import hashlib
import platform as platform_module
import re
import stat
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Protocol

from biomesh import __version__
from biomesh.build_identity import BuildProvenanceError, load_embedded_build_identity
from biomesh.outputs import RunMetadata

_SOURCE_TREE_DOMAIN = b"biomesh-source-tree-v1\0"
_WORKING_TREE_DOMAIN = b"biomesh-working-tree-v2\0"

RUNTIME_DISTRIBUTIONS = (
    "cryptography",
    "matplotlib",
    "numba",
    "numpy",
    "pyarrow",
    "pydantic",
    "pyqtgraph",
    "PySide6",
    "scipy",
)


class ProvenanceError(ValueError):
    """Raised when required run provenance cannot be collected safely."""


class _HashWriter(Protocol):
    def update(self, value: bytes, /) -> None: ...


def collect_run_metadata(
    *,
    parameter_file: Path,
    parameter_file_label: str,
    parameters: dict[str, object],
    seed: int,
    repository_root: Path | None,
) -> RunMetadata:
    """Collect deterministic run provenance without changing model inputs."""
    try:
        parameter_bytes = parameter_file.read_bytes()
    except OSError as error:
        raise ProvenanceError(
            f"unable to read provenance parameter file {parameter_file}: "
            f"{error.strerror or error}"
        ) from error

    commit_hash, source_tree_sha256, source_state = runtime_source_identity(
        repository_root
    )
    return RunMetadata(
        seed=seed,
        parameters=parameters,
        package_version=__version__,
        commit_hash=commit_hash,
        dependency_versions=runtime_dependency_versions(),
        parameter_file=parameter_file_label,
        parameter_file_sha256=hashlib.sha256(parameter_bytes).hexdigest(),
        platform=platform_module.platform(),
        python_version=platform_module.python_version(),
        source_tree_sha256=source_tree_sha256,
        source_state=source_state,
    )


def exact_runtime_source_commit(repository_root: Path | None) -> str:
    """Resolve a Git or immutable installed commit without an unknown fallback."""
    source_root = _owned_source_root(repository_root)
    if source_root is not None:
        return runtime_source_identity(repository_root)[0]
    try:
        return load_embedded_build_identity().source_commit
    except BuildProvenanceError as error:
        raise ProvenanceError(
            "exact source commit is unavailable; this execution is not from a "
            "publishable P5 build"
        ) from error


def runtime_dependency_versions() -> dict[str, str]:
    """Return the complete declared runtime dependency inventory."""
    dependency_versions: dict[str, str] = {}
    for distribution in RUNTIME_DISTRIBUTIONS:
        try:
            dependency_versions[distribution] = version(distribution)
        except PackageNotFoundError as error:
            raise ProvenanceError(
                f"required runtime dependency is not installed: {distribution}"
            ) from error
    return dependency_versions


def runtime_source_identity(
    repository_root: Path | None,
) -> tuple[str, str, str]:
    """Return Git commit, complete source-state hash, and state label."""
    source_root = _owned_source_root(repository_root)
    if source_root is None:
        try:
            identity = load_embedded_build_identity()
        except BuildProvenanceError as error:
            raise ProvenanceError(
                "exact source identity is unavailable; this execution is not from a "
                "publishable P5 build"
            ) from error
        return identity.source_commit, identity.source_tree_sha256, "clean"
    return _source_identity(source_root)


def _source_identity(source_root: Path) -> tuple[str, str, str]:
    try:
        status = subprocess.run(
            [
                "git",
                "-C",
                str(source_root),
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
            ],
            check=False,
            capture_output=True,
        )
        if status.returncode != 0:
            raise ProvenanceError("source state cannot be verified")
        listing = _git_bytes(
            source_root, "ls-tree", "-r", "-z", "--full-tree", "HEAD"
        )
        if not listing:
            raise ProvenanceError("source tree identity cannot be resolved")
        commit = _git_text(source_root, "rev-parse", "--verify", "HEAD")
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
            raise ProvenanceError("exact source commit cannot be resolved")
        if not status.stdout:
            return (
                commit,
                hashlib.sha256(_SOURCE_TREE_DOMAIN + listing).hexdigest(),
                "clean",
            )
        diff = _git_bytes(source_root, "diff", "--binary", "HEAD", "--")
        untracked = _git_bytes(
            source_root,
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
        )
        digest = hashlib.sha256()
        digest.update(_WORKING_TREE_DOMAIN)
        _update_identity_field(digest, b"commit", commit.encode("ascii"))
        _update_identity_field(digest, b"tracked-tree", listing)
        _update_identity_field(digest, b"status", status.stdout)
        _update_identity_field(digest, b"diff", diff)
        for relative_bytes in sorted(
            item for item in untracked.split(b"\0") if item
        ):
            relative = relative_bytes.decode("utf-8")
            path = source_root / relative
            metadata = path.lstat()
            if not stat.S_ISREG(metadata.st_mode):
                raise ProvenanceError(
                    "source working state contains an unsafe untracked path"
                )
            _update_identity_field(digest, b"untracked-path", relative_bytes)
            _update_identity_field(
                digest,
                b"untracked-mode",
                stat.S_IMODE(metadata.st_mode).to_bytes(4, "big"),
            )
            _update_identity_field(digest, b"untracked-content", path.read_bytes())
        return commit, digest.hexdigest(), "modified"
    except OSError as error:
        raise ProvenanceError("source state cannot be verified") from error


def _git_bytes(source_root: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(source_root), *arguments],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ProvenanceError("source Git identity cannot be resolved")
    return result.stdout


def _update_identity_field(
    digest: _HashWriter, label: bytes, value: bytes
) -> None:
    """Add one unambiguous typed field to a working-tree identity."""
    digest.update(len(label).to_bytes(2, "big"))
    digest.update(label)
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def _git_text(source_root: Path, *arguments: str) -> str:
    return _git_bytes(source_root, *arguments).decode("utf-8").strip()


def _owned_source_root(candidate: Path | None) -> Path | None:
    module = Path(__file__).resolve()
    candidates = (() if candidate is None else (candidate.resolve(),)) + tuple(
        module.parents
    )
    for root in candidates:
        source = root / "src" / "biomesh" / "provenance.py"
        if not (root / ".git").exists() or not source.is_file():
            continue
        try:
            if source.samefile(module):
                return root
        except OSError:
            continue
    return None
