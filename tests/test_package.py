"""Package metadata and command-help tests."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version as installed_version
from pathlib import Path

import biomesh


def test_package_exposes_version() -> None:
    """The package exposes its current version identifier."""
    assert biomesh.__version__ == installed_version("biomesh") == "0.5.0"


def test_module_version_reports_installed_version() -> None:
    """The module CLI reports the installed distribution version."""
    result = subprocess.run(
        [sys.executable, "-m", "biomesh", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == f"biomesh {installed_version('biomesh')}"
    assert result.stderr == ""


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


def test_help_alias_matches_top_level_help() -> None:
    """The ergonomic help alias has the same output as the help flag."""
    flag_result = subprocess.run(
        [sys.executable, "-m", "biomesh", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    alias_result = subprocess.run(
        [sys.executable, "-m", "biomesh", "help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert alias_result.returncode == 0
    assert alias_result.stdout == flag_result.stdout
    assert alias_result.stderr == flag_result.stderr == ""


def test_run_rejects_existing_output_with_actionable_error(tmp_path: Path) -> None:
    """A reference run never overwrites an existing directory."""
    output = tmp_path / "existing-run"
    output.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "biomesh",
            "run",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "output run directory already exists" in result.stderr
    assert str(output) in result.stderr
    assert "choose a new path with --output" in result.stderr


def test_run_succeeds_with_new_explicit_output_directory(tmp_path: Path) -> None:
    """A new explicit output directory remains a successful P1 CLI path."""
    output = tmp_path / "new-run"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "biomesh",
            "run",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == str(output)
    assert output.is_dir()
    assert (output / "run_metadata.json").is_file()
