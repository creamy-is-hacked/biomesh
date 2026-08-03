"""Package metadata and command-help tests."""

from __future__ import annotations

import subprocess
import sys

import biomesh


def test_package_exposes_version() -> None:
    """The package exposes its current version identifier."""
    assert biomesh.__version__ == "0.0.0"


def test_module_help_succeeds() -> None:
    """The module command exposes its current help."""
    result = subprocess.run(
        [sys.executable, "-m", "biomesh", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "BioMesh Phase 1 core-model runner" in result.stdout
    assert "--version" in result.stdout
    assert "validate" in result.stdout
    assert "reproduce" in result.stdout
