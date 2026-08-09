"""Focused headless acceptance tests for the P3-WP03 simulation viewer."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_snapshot_viewer_headless_acceptance(tmp_path: Path) -> None:
    """Exercise rendering, layers, navigation, and rate limiting offscreen."""
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "tests/gui_viewer_probe.py", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
