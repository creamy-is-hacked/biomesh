"""Run-level provenance collection for P1-WP07.

Provenance describes the execution environment and exact parameter document;
it does not supply or alter scientific inputs.
"""

from __future__ import annotations

import hashlib
import platform as platform_module
import re
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from biomesh import __version__
from biomesh.build_identity import BuildProvenanceError, load_embedded_build_identity
from biomesh.outputs import RunMetadata

RUNTIME_DISTRIBUTIONS = (
    "matplotlib",
    "numba",
    "numpy",
    "pyarrow",
    "pydantic",
    "scipy",
)


class ProvenanceError(ValueError):
    """Raised when required run provenance cannot be collected safely."""


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

    dependency_versions: dict[str, str] = {}
    for distribution in RUNTIME_DISTRIBUTIONS:
        try:
            dependency_versions[distribution] = version(distribution)
        except PackageNotFoundError as error:
            raise ProvenanceError(
                f"required runtime dependency is not installed: {distribution}"
            ) from error

    return RunMetadata(
        seed=seed,
        parameters=parameters,
        package_version=__version__,
        commit_hash=exact_runtime_source_commit(repository_root),
        dependency_versions=dependency_versions,
        parameter_file=parameter_file_label,
        parameter_file_sha256=hashlib.sha256(parameter_bytes).hexdigest(),
        platform=platform_module.platform(),
        python_version=platform_module.python_version(),
    )


def exact_runtime_source_commit(repository_root: Path | None) -> str:
    """Resolve a Git or immutable installed commit without an unknown fallback."""
    source_root = _owned_source_root(repository_root)
    if source_root is not None:
        try:
            result = subprocess.run(
                ["git", "-C", str(source_root), "rev-parse", "--verify", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            result = None
        if result is not None:
            commit = result.stdout.strip()
            if result.returncode == 0 and re.fullmatch(
                r"[0-9a-f]{40}|[0-9a-f]{64}", commit
            ):
                return commit
    try:
        return load_embedded_build_identity().source_commit
    except BuildProvenanceError as error:
        raise ProvenanceError(
            "exact source commit is unavailable; this execution is not from a "
            "publishable P5 build"
        ) from error


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
