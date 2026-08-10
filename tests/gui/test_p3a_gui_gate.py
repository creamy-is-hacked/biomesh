"""P3A GUI application-path gate collected by the documented audit command."""

from __future__ import annotations

import os
import subprocess
import sys


def test_offscreen_desktop_smoke_path() -> None:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "-m", "biomesh.gui", "--smoke-test"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
