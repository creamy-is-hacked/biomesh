"""Focused headless P3-WP04 experiment-editor acceptance test."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_schema_generated_editor_headless(tmp_path: Path) -> None:
    """Exercise the real editor dock without loading Qt into this process."""
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "tests/gui_editor_probe.py", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
