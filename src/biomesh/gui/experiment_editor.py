"""Schema-generated P3-WP04 biological-parameter editor widget."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from biomesh.config import BiologicalParameter
from biomesh.gui.experiment_document import (
    AUDITED_PRESET_REVISION,
    PARAMETER_SCHEMAS,
    BiologicalParameterFields,
    ExperimentDocumentError,
    ExperimentEditorSession,
)


class ExperimentEditor(QWidget):
    """Edit draft text while exposing only validated immutable configurations."""

    error_reported = Signal(str)
    run_eligibility_changed = Signal(bool)

    def __init__(self, repository_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("experimentEditor")
        self._repository_root = repository_root.resolve()
        self._session: ExperimentEditorSession | None = None
        self._field_editors: dict[tuple[int, str], QLineEdit] = {}
        self._field_errors: dict[tuple[int, str], QLabel] = {}
        self._parameter_errors: dict[int, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Validated biological parameter document", self))
        catalog_row = QHBoxLayout()
        self._catalog = QComboBox(self)
        self._catalog.setObjectName("parameterDocumentCatalog")
        for schema in PARAMETER_SCHEMAS:
            self._catalog.addItem(
                f"Template — {schema.title}", ("template", schema.schema_id)
            )
        for schema in PARAMETER_SCHEMAS:
            self._catalog.addItem(
                f"Audited preset — {schema.title}", ("preset", schema.schema_id)
            )
        catalog_row.addWidget(self._catalog, 1)
        load_button = QPushButton("Load", self)
        load_button.setObjectName("loadParameterDocumentButton")
        load_button.clicked.connect(self._load_selected)
        catalog_row.addWidget(load_button)
        layout.addLayout(catalog_row)

        action_row = QHBoxLayout()
        open_button = QPushButton("Open Saved Configuration…", self)
        open_button.setObjectName("openParameterDocumentButton")
        open_button.clicked.connect(self._choose_open_path)
        action_row.addWidget(open_button)
        self._clone_button = QPushButton("Create Editable Copy", self)
        self._clone_button.setObjectName("cloneParameterDocumentButton")
        self._clone_button.clicked.connect(self.clone_as_editable)
        action_row.addWidget(self._clone_button)
        self._save_button = QPushButton("Save Configuration As…", self)
        self._save_button.setObjectName("saveParameterDocumentButton")
        self._save_button.clicked.connect(self._choose_save_path)
        action_row.addWidget(self._save_button)
        layout.addLayout(action_row)

        self._source_label = QLabel("No parameter document loaded", self)
        self._source_label.setObjectName("parameterDocumentSource")
        self._source_label.setWordWrap(True)
        layout.addWidget(self._source_label)
        self._validation_summary = QLabel("Not validated", self)
        self._validation_summary.setObjectName("parameterValidationSummary")
        self._validation_summary.setWordWrap(True)
        layout.addWidget(self._validation_summary)
        self._run_eligibility = QLabel("Run eligibility: unavailable", self)
        self._run_eligibility.setObjectName("parameterRunEligibility")
        self._run_eligibility.setWordWrap(True)
        layout.addWidget(self._run_eligibility)

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("parameterEditorScrollArea")
        self._scroll.setWidgetResizable(True)
        layout.addWidget(self._scroll, 1)

        self.load_template(PARAMETER_SCHEMAS[0].schema_id)

    @property
    def session(self) -> ExperimentEditorSession:
        """Return current editor UI state for shell integration and tests."""
        if self._session is None:
            raise ExperimentDocumentError("no parameter document is loaded")
        return self._session

    def field_editor(self, parameter_index: int, field_name: str) -> QLineEdit:
        """Return one generated field control for focused headless tests."""
        try:
            return self._field_editors[(parameter_index, field_name)]
        except KeyError as error:
            raise ExperimentDocumentError(
                "no generated editor for parameter "
                f"{parameter_index} field {field_name}"
            ) from error

    def set_field_text(self, parameter_index: int, field_name: str, text: str) -> None:
        """Set one generated control exactly as an interactive edit would."""
        self.field_editor(parameter_index, field_name).setText(text)

    def load_template(self, schema_id: str) -> bool:
        """Load a repository schema document as a new unsaved editable draft."""
        try:
            session = ExperimentEditorSession.from_template(
                self._repository_root, schema_id
            )
        except ExperimentDocumentError as error:
            self.error_reported.emit(str(error))
            return False
        self._install_session(session)
        return True

    def load_audited_preset(self, schema_id: str) -> bool:
        """Load a P2A-accepted repository parameter document read-only."""
        try:
            session = ExperimentEditorSession.from_audited_preset(
                self._repository_root, schema_id
            )
        except ExperimentDocumentError as error:
            self.error_reported.emit(str(error))
            return False
        self._install_session(session)
        return True

    def open_saved_configuration(self, path: Path) -> bool:
        """Open one saved TOML document through its uniquely matching schema."""
        try:
            session = ExperimentEditorSession.from_saved_configuration(
                self._repository_root, path
            )
        except ExperimentDocumentError as error:
            self.error_reported.emit(str(error))
            return False
        self._install_session(session)
        self._source_label.setText(
            f"Editable saved configuration loaded from {session.source_path}"
        )
        return True

    @Slot()
    def clone_as_editable(self) -> None:
        """Create an unsaved editable copy without altering the audited source."""
        try:
            cloned = self.session.clone_as_editable()
        except ExperimentDocumentError as error:
            self.error_reported.emit(str(error))
            return
        self._install_session(cloned)

    def save_configuration(self, path: Path, *, overwrite: bool = False) -> bool:
        """Save only valid editable science, preserving protected presets."""
        try:
            self.session.save(path, overwrite=overwrite)
        except ExperimentDocumentError as error:
            self.error_reported.emit(str(error))
            return False
        self._source_label.setText(
            f"Editable configuration saved to {path.expanduser().resolve()}"
        )
        return True

    @Slot()
    def _load_selected(self) -> None:
        selection = self._catalog.currentData()
        if (
            not isinstance(selection, tuple)
            or len(selection) != 2
            or not all(isinstance(item, str) for item in selection)
        ):
            self.error_reported.emit("invalid parameter document catalog selection")
            return
        kind, schema_id = selection
        if kind == "template":
            self.load_template(schema_id)
        else:
            self.load_audited_preset(schema_id)

    @Slot()
    def _choose_open_path(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "Open validated parameter configuration",
            "",
            "TOML parameter files (*.toml)",
        )
        if selected:
            self.open_saved_configuration(Path(selected))

    @Slot()
    def _choose_save_path(self) -> None:
        selected, _filter = QFileDialog.getSaveFileName(
            self,
            "Save validated parameter configuration",
            "",
            "TOML parameter files (*.toml)",
        )
        if not selected:
            return
        target = Path(selected)
        overwrite = False
        if target.exists():
            response = QMessageBox.question(
                self,
                "Confirm configuration overwrite",
                f"Replace existing configuration {target}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            overwrite = response is QMessageBox.StandardButton.Yes
            if not overwrite:
                return
        self.save_configuration(target, overwrite=overwrite)

    def _install_session(self, session: ExperimentEditorSession) -> None:
        self._session = session
        self._rebuild_form()
        if session.is_read_only:
            self._source_label.setText(
                "Read-only audited preset from P2A implementation "
                f"{AUDITED_PRESET_REVISION}: {session.source_path}"
            )
        else:
            self._source_label.setText(
                "Editable template copy; source remains unchanged: "
                f"{session.source_path}"
            )
        self._refresh_validation()

    def _rebuild_form(self) -> None:
        old_widget = self._scroll.takeWidget()
        if old_widget is not None:
            old_widget.deleteLater()
        self._field_editors.clear()
        self._field_errors.clear()
        self._parameter_errors.clear()
        container = QWidget(self._scroll)
        container.setObjectName("parameterFormContainer")
        layout = QVBoxLayout(container)
        session = self.session
        schema_fields = tuple(BiologicalParameter.model_fields)
        for index, parameter in enumerate(
            session.document.configuration.biological_parameters
        ):
            group = QGroupBox(parameter.name, container)
            group.setObjectName(f"biologicalParameterGroup{index}")
            form = QFormLayout(group)
            for field_name in schema_fields:
                editor = QLineEdit(
                    session.field_text(index, field_name),
                    group,
                )
                editor.setObjectName(f"parameter{index}_{field_name}")
                editor.setReadOnly(
                    session.is_read_only
                    or field_name
                    in {
                        BiologicalParameterFields.NAME.value,
                        BiologicalParameterFields.UNIT.value,
                    }
                )
                if not editor.isReadOnly():
                    editor.textChanged.connect(
                        lambda text, row=index, field=field_name: self._field_changed(
                            row, field, text
                        )
                    )
                form.addRow(field_name.replace("_", " ").title(), editor)
                error_label = QLabel("", group)
                error_label.setObjectName(f"parameter{index}_{field_name}Error")
                error_label.setWordWrap(True)
                error_label.setStyleSheet("color: #b00020")
                form.addRow("", error_label)
                self._field_editors[(index, field_name)] = editor
                self._field_errors[(index, field_name)] = error_label
            parameter_error = QLabel("", group)
            parameter_error.setObjectName(f"parameter{index}_validationError")
            parameter_error.setWordWrap(True)
            parameter_error.setStyleSheet("color: #b00020")
            form.addRow("Validation error", parameter_error)
            self._parameter_errors[index] = parameter_error
            layout.addWidget(group)
        layout.addStretch()
        self._scroll.setWidget(container)

    def _field_changed(self, parameter_index: int, field_name: str, text: str) -> None:
        try:
            self.session.set_field(parameter_index, field_name, text)
        except ExperimentDocumentError as error:
            self.error_reported.emit(str(error))
            return
        self._refresh_validation()

    def _refresh_validation(self) -> None:
        session = self.session
        for label in self._field_errors.values():
            label.clear()
        for label in self._parameter_errors.values():
            label.clear()
        document_messages: list[str] = []
        for (index, field), message in session.validation_errors.items():
            if (index, field) in self._field_errors:
                self._field_errors[(index, field)].setText(message)
            elif index in self._parameter_errors:
                self._parameter_errors[index].setText(message)
            else:
                document_messages.append(message)
        if session.validated_document is None:
            summary = (
                "Invalid configuration. Correct the explicit errors before saving."
            )
            if document_messages:
                summary += " " + " ".join(document_messages)
            self._validation_summary.setText(summary)
            self._run_eligibility.setText(
                "Run eligibility: INELIGIBLE — configuration is invalid"
            )
        elif session.run_eligible:
            self._validation_summary.setText(
                "Configuration is valid under the existing parameter schema."
            )
            self._run_eligibility.setText(
                "Run eligibility: ELIGIBLE for future controls "
                "(no run control exists in P3-WP04)"
            )
        else:
            self._validation_summary.setText(
                "Configuration is schema-valid and preserves unresolved provenance."
            )
            self._run_eligibility.setText(
                "Run eligibility: INELIGIBLE — CALIBRATION_REQUIRED values or "
                "provenance remain"
            )
        self._clone_button.setEnabled(
            session.is_read_only and session.validated_document is not None
        )
        self._save_button.setEnabled(
            not session.is_read_only and session.validated_document is not None
        )
        self.run_eligibility_changed.emit(session.run_eligible)
