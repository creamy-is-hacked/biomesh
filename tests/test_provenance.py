"""P5 runtime source and dependency provenance regression tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

from biomesh.provenance import (
    RUNTIME_DISTRIBUTIONS,
    runtime_dependency_versions,
    runtime_source_identity,
)


def test_runtime_source_identity_distinguishes_modified_working_tree(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    source = root / "src" / "biomesh"
    source.mkdir(parents=True)
    module = Path(__file__).parents[1] / "src" / "biomesh" / "provenance.py"
    (source / "provenance.py").symlink_to(module)
    tracked = source / "tracked.py"
    tracked.write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "BioMesh Test"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "--quiet", "-m", "fixture"],
        check=True,
    )

    commit, clean_hash, clean_state = runtime_source_identity(root)
    assert len(commit) == 40
    assert len(clean_hash) == 64
    assert clean_state == "clean"

    tracked.write_text("VALUE = 2\n", encoding="utf-8")
    (root / "untracked.txt").write_text("new source\n", encoding="utf-8")
    dirty_commit, dirty_hash, dirty_state = runtime_source_identity(root)
    assert dirty_commit == commit
    assert dirty_hash != clean_hash
    assert dirty_state == "modified"


def test_modified_identity_distinguishes_untracked_execute_mode_deterministically(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    source = root / "src" / "biomesh"
    source.mkdir(parents=True)
    module = Path(__file__).parents[1] / "src" / "biomesh" / "provenance.py"
    (source / "provenance.py").symlink_to(module)
    (source / "tracked.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "BioMesh Test"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "--quiet", "-m", "fixture"],
        check=True,
    )
    untracked = root / "tool.sh"
    untracked.write_bytes(b"#!/bin/sh\nexit 0\n")
    untracked.chmod(0o644)
    first = runtime_source_identity(root)
    assert runtime_source_identity(root) == first

    untracked.chmod(0o755)
    second = runtime_source_identity(root)
    assert second[0] == first[0]
    assert second[1] != first[1]
    assert second[2] == first[2] == "modified"
    assert runtime_source_identity(root) == second


def test_runtime_dependency_inventory_is_complete_and_versioned() -> None:
    versions = runtime_dependency_versions()
    assert set(versions) == set(RUNTIME_DISTRIBUTIONS)
    assert all(value for value in versions.values())
