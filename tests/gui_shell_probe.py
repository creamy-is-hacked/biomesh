"""Subprocess probe for real P3-WP02 widgets on the offscreen Qt backend."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDockWidget, QMenu, QPlainTextEdit

from biomesh.gui.main_window import MainWindow
from biomesh.gui.preferences import UiPreferences, UiPreferencesStore
from biomesh.gui.viewer import SimulationViewer


def main(root: Path) -> int:
    """Verify shell chrome, visible errors, and scientific-state isolation."""
    application = QApplication(["biomesh-gui-probe"])
    preferences_file = root / "ui" / "preferences.json"
    project_file = root / "example.biomesh"
    project_file.write_text("opaque shell reference\n", encoding="utf-8")
    parameter_files = sorted(Path("parameters").glob("*.toml"))
    hashes_before = {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in parameter_files
    }

    window = MainWindow(UiPreferencesStore(preferences_file))
    window.show()
    application.processEvents()
    assert isinstance(window.centralWidget(), SimulationViewer)
    assert window.menuBar().findChild(QMenu, "fileMenu") is not None
    assert window.menuBar().findChild(QMenu, "viewMenu") is not None
    assert window.menuBar().findChild(QMenu, "helpMenu") is not None
    assert window.findChild(QDockWidget, "projectDock") is not None
    assert window.findChild(QDockWidget, "errorConsoleDock") is not None
    console = window.findChild(QPlainTextEdit, "errorConsole")
    assert console is not None and console.isReadOnly()
    assert window.statusBar().currentMessage() == "Ready"

    assert window.open_project_reference(project_file)
    assert window.current_project == project_file.resolve()
    missing = root / "missing.biomesh"
    assert not window.open_project_reference(missing)
    assert not window.open_project_reference(root)
    error_text = console.toPlainText()
    assert str(missing) in error_text
    assert "does not exist" in error_text
    assert "not a regular file" in error_text
    assert window.statusBar().currentMessage() == "Error - see Error Console"
    assert window.save_ui_preferences()
    window.close()
    application.processEvents()

    hashes_after = {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in parameter_files
    }
    assert hashes_after == hashes_before
    restored = UiPreferencesStore(preferences_file).load()
    assert restored.recent_projects == (str(project_file.resolve()),)

    preferences_file.write_text("invalid", encoding="utf-8")
    invalid_window = MainWindow(UiPreferencesStore(preferences_file))
    invalid_console = invalid_window.findChild(QPlainTextEdit, "errorConsole")
    assert invalid_console is not None
    assert "unable to read UI preferences" in invalid_console.toPlainText()
    assert invalid_window.preferences == UiPreferences()
    invalid_window.close()
    application.processEvents()
    assert preferences_file.read_text(encoding="utf-8") == "invalid"
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
