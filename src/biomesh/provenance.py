"""Run-level provenance collection for P1-WP07.

Provenance describes the execution environment and exact parameter document;
it does not supply or alter scientific inputs.
"""

from __future__ import annotations

import hashlib
import platform as platform_module
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from biomesh import __version__
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
        commit_hash=_git_commit(repository_root),
        dependency_versions=dependency_versions,
        parameter_file=parameter_file_label,
        parameter_file_sha256=hashlib.sha256(parameter_bytes).hexdigest(),
        platform=platform_module.platform(),
        python_version=platform_module.python_version(),
    )


def _git_commit(repository_root: Path | None) -> str:
    if repository_root is None:
        return "UNAVAILABLE"
    try:
        result = subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "UNAVAILABLE"
    commit = result.stdout.strip()
    if result.returncode != 0 or not commit:
        return "UNAVAILABLE"
    return commit
