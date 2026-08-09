"""Subprocess probe for real P3-WP04 editor widgets on offscreen Qt."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDockWidget, QLabel, QPlainTextEdit

from biomesh.gui.experiment_document import PARAMETER_SCHEMAS, load_parameter_document
from biomesh.gui.experiment_editor import ExperimentEditor
from biomesh.gui.main_window import MainWindow
from biomesh.gui.preferences import UiPreferencesStore


def main(root: Path) -> int:
    """Verify generated controls, validation, round-trip, and preset protection."""
    application = QApplication(["biomesh-editor-probe"])
    repository_root = Path.cwd()
    preferences_file = root / "ui-preferences.json"
    parameter_files = sorted((repository_root / "parameters").glob("*.toml"))
    hashes_before = {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in parameter_files
    }

    window = MainWindow(
        UiPreferencesStore(preferences_file), repository_root=repository_root
    )
    window.show()
    application.processEvents()
    dock = window.findChild(QDockWidget, "experimentEditorDock")
    assert dock is not None
    editor = dock.findChild(ExperimentEditor, "experimentEditor")
    assert editor is not None
    for schema in PARAMETER_SCHEMAS:
        assert editor.load_template(schema.schema_id)
        parameters = editor.session.document.configuration.biological_parameters
        assert parameters
        for index, _parameter in enumerate(parameters):
            for field_name in (
                "name",
                "value",
                "unit",
                "source",
                "uncertainty",
                "notes",
                "calibration_status",
            ):
                assert editor.field_editor(index, field_name) is not None
    assert editor.load_template("p1_core")
    assert len(editor.session.document.configuration.biological_parameters) == 15
    first = editor.session.document.configuration.biological_parameters[0]
    assert editor.field_editor(0, "unit").text() == first.unit
    assert editor.field_editor(0, "source").text() == first.source
    assert editor.field_editor(0, "uncertainty").text() == first.uncertainty
    assert editor.field_editor(0, "notes").text() == first.notes
    assert editor.field_editor(0, "calibration_status").text() == (
        first.calibration_status
    )
    assert editor.field_editor(0, "name").isReadOnly()
    assert editor.field_editor(0, "unit").isReadOnly()

    editor.set_field_text(0, "value", "invalid")
    application.processEvents()
    assert editor.session.validated_document is None
    assert not editor.session.run_eligible
    validation_summary = editor.findChild(QLabel, "parameterValidationSummary")
    assert validation_summary is not None
    assert "Invalid configuration" in validation_summary.text()
    invalid_target = root / "invalid.toml"
    assert not editor.save_configuration(invalid_target)
    assert not invalid_target.exists()
    console = window.findChild(QPlainTextEdit, "errorConsole")
    assert console is not None
    assert "invalid configuration cannot be saved" in console.toPlainText()

    assert editor.load_audited_preset("p2_eps")
    application.processEvents()
    assert editor.session.is_read_only
    for index, _parameter in enumerate(
        editor.session.document.configuration.biological_parameters
    ):
        for field_name in (
            "name",
            "value",
            "unit",
            "source",
            "uncertainty",
            "notes",
            "calibration_status",
        ):
            assert editor.field_editor(index, field_name).isReadOnly()
    source_label = editor.findChild(QLabel, "parameterDocumentSource")
    assert source_label is not None
    assert "Read-only audited preset" in source_label.text()
    editor.clone_as_editable()
    application.processEvents()
    assert not editor.session.is_read_only
    assert not editor.field_editor(0, "value").isReadOnly()
    assert editor.field_editor(0, "unit").isReadOnly()

    saved_path = root / "eps-copy.toml"
    original = editor.session.validated_document
    assert editor.save_configuration(saved_path)
    assert original is not None
    assert load_parameter_document(saved_path, "p2_eps").configuration == (
        original.configuration
    )
    assert editor.open_saved_configuration(saved_path)
    assert editor.session.validated_document is not None
    assert editor.session.validated_document.configuration == original.configuration
    preset_path = repository_root / "parameters" / "p2_eps_model.toml"
    assert not editor.save_configuration(preset_path, overwrite=True)

    window.close()
    application.processEvents()
    hashes_after = {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in parameter_files
    }
    assert hashes_after == hashes_before
    assert preferences_file.is_file()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
