"""Locate BioMesh's versioned runtime resource records.

Source checkouts use the repository root.  Built distributions carry the same
records beneath the package so installed CLI and GUI entry points do not depend
on the process working directory.
"""

from __future__ import annotations

from pathlib import Path


class RuntimeResourceError(RuntimeError):
    """Raised when the packaged or source runtime records cannot be found."""


def runtime_root(working_directory: Path | None = None) -> Path:
    """Return the source or packaged root containing required runtime records."""
    working = (working_directory or Path.cwd()).resolve()
    if _has_runtime_records(working):
        return working

    packaged = Path(__file__).resolve().parent / "resources"
    if _has_runtime_records(packaged):
        return packaged
    raise RuntimeResourceError(
        "BioMesh runtime resources are unavailable; use a source checkout or "
        "a complete wheel/sdist installation"
    )


def _has_runtime_records(root: Path) -> bool:
    return (
        (root / "experiments" / "p2_wp06_campaign.toml").is_file()
        and (root / "experiments" / "producer.yaml").is_file()
        and (root / "parameters" / "p1_core_model.toml").is_file()
        and (root / "parameters" / "phase1_reference.toml").is_file()
    )
