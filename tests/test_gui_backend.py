"""P5 GUI binding selection regression tests."""

from __future__ import annotations

import os
import subprocess
import sys


def test_gui_overrides_competing_pyqtgraph_binding_preference() -> None:
    environment = os.environ.copy()
    environment["PYQTGRAPH_QT_LIB"] = "PyQt6"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import biomesh.gui, os, pyqtgraph; "
                "assert os.environ['PYQTGRAPH_QT_LIB'] == 'PySide6'; "
                "assert pyqtgraph.Qt.QT_LIB == 'PySide6'"
            ),
        ],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
