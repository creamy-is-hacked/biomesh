"""M0 – Repository Bootstrap package-shell tests."""

from __future__ import annotations

import subprocess
import sys

import biomesh


def test_package_exposes_version() -> None:
    """The package exposes the M0 – Repository Bootstrap version identifier."""
    assert biomesh.__version__ == "0.0.0"


def test_module_help_succeeds() -> None:
    """The module command exposes its help without simulation behavior."""
    result = subprocess.run(
        [sys.executable, "-m", "biomesh", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "BioMesh biofilm simulator" in result.stdout
    assert "--version" in result.stdout
