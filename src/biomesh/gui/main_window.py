"""P3-WP05 desktop shell with viewer, editor, controls, and inspection."""

from __future__ import annotations

import base64
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, Slot
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from biomesh.application_types import CellInspection, RunSnapshot
from biomesh.gui.cell_inspector import CellInspector
from biomesh.gui.experiment_editor import ExperimentEditor
from biomesh.gui.preferences import (
    UiPreferences,
    UiPreferencesError,
    UiPreferencesStore,
)
from biomesh.gui.run_controls import SimulationControls
from biomesh.gui.simulation_worker import SimulationWorker
from biomesh.gui.viewer import SimulationViewer
from biomesh.runtime_resources import RuntimeResourceError, runtime_root


class MainWindow(QMainWindow):
    """Desktop chrome around snapshot viewing and validated parameter editing."""

    def __init__(
        self,
        preferences_store: UiPreferencesStore | None = None,
        repository_root: Path | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("biomeshMainWindow")
        self.setWindowTitle("BioMesh")
        self.resize(1100, 720)
        self._preferences_store = preferences_store or UiPreferencesStore()
        self._repository_root = (
            repository_root or _default_repository_root()
        ).resolve()
        self._preferences = UiPreferences()
        self._preferences_load_failed = False
        self._current_project: Path | None = None
        preference_error: str | None = None
        try:
            self._preferences = self._preferences_store.load()
        except UiPreferencesError as error:
            self._preferences_load_failed = True
            preference_error = str(error)

        self._build_central_viewer()
        self._build_docks()
        self._build_worker()
        self._build_menus()
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready")
        self._restore_window_layout()
        self._rebuild_recent_projects_menu()
        if preference_error is not None:
            self.report_error(preference_error)

    @property
    def preferences(self) -> UiPreferences:
        """Expose immutable UI-only preferences for shell integration tests."""
        return self._preferences

    @property
    def current_project(self) -> Path | None:
        """Return the current opaque UI project reference, if any."""
        return self._current_project

    def open_project_reference(self, project_file: Path) -> bool:
        """Record an existing readable file without interpreting its contents."""
        try:
            resolved = project_file.expanduser().resolve(strict=True)
            if not resolved.is_file():
                raise OSError("path is not a regular file")
            with resolved.open("rb") as stream:
                stream.read(1)
        except FileNotFoundError:
            self.report_error(
                f"Unable to open project reference {project_file}: file does not exist"
            )
            return False
        except OSError as error:
            self.report_error(
                f"Unable to open project reference {project_file}: {error}"
            )
            return False

        self._current_project = resolved
        self._preferences = self._preferences.with_recent_project(resolved)
        self._project_path.setText(str(resolved))
        self.statusBar().showMessage(f"Project reference: {resolved}")
        self._rebuild_recent_projects_menu()
        return True

    def report_error(self, message: str) -> None:
        """Display a clear shell error without hiding it in a transient dialog."""
        self._error_console.appendPlainText(f"ERROR: {message}")
        self._error_dock.show()
        self.statusBar().showMessage("Error - see Error Console")

    def save_ui_preferences(self) -> bool:
        """Persist window chrome separately from scientific configuration."""
        if self._preferences_load_failed:
            self.report_error(
                "Invalid UI preferences were not overwritten; remove or repair "
                f"{self._preferences_store.path}"
            )
            return False
        geometry = bytes(self.saveGeometry().toBase64().data()).decode("ascii")
        state = bytes(self.saveState().toBase64().data()).decode("ascii")
        self._preferences = self._preferences.with_window_state(
            geometry=geometry,
            state=state,
        )
        try:
            self._preferences_store.save(self._preferences)
        except UiPreferencesError as error:
            self.report_error(str(error))
            return False
        return True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Cancel worker activity, then save only UI state."""
        self._worker.request_shutdown()
        if self._worker.isRunning() and not self._worker.wait(10_000):
            self.report_error(
                "Simulation worker did not stop at an accepted solver boundary"
            )
            event.ignore()
            return
        self.save_ui_preferences()
        event.accept()

    def _build_central_viewer(self) -> None:
        self._viewer = SimulationViewer(self)
        self.setCentralWidget(self._viewer)

    def _build_docks(self) -> None:
        self._project_dock = QDockWidget("Project", self)
        self._project_dock.setObjectName("projectDock")
        project_widget = QWidget(self._project_dock)
        project_layout = QVBoxLayout(project_widget)
        project_layout.addWidget(QLabel("Current project reference", project_widget))
        self._project_path = QLabel("No project reference selected", project_widget)
        self._project_path.setObjectName("currentProjectPath")
        self._project_path.setWordWrap(True)
        project_layout.addWidget(self._project_path)
        project_layout.addStretch()
        self._project_dock.setWidget(project_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._project_dock)

        self._experiment_dock = QDockWidget("Experiment Editor", self)
        self._experiment_dock.setObjectName("experimentEditorDock")
        self._experiment_editor = ExperimentEditor(
            self._repository_root, self._experiment_dock
        )
        self._experiment_editor.error_reported.connect(self.report_error)
        self._experiment_dock.setWidget(self._experiment_editor)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._experiment_dock
        )

        self._controls_dock = QDockWidget("Simulation Controls", self)
        self._controls_dock.setObjectName("simulationControlsDock")
        self._controls = SimulationControls(
            self._repository_root, self._controls_dock
        )
        self._controls_dock.setWidget(self._controls)
        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self._controls_dock
        )

        self._inspector_dock = QDockWidget("Cell Inspector", self)
        self._inspector_dock.setObjectName("cellInspectorDock")
        self._inspector = CellInspector(self._inspector_dock)
        self._inspector_dock.setWidget(self._inspector)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._inspector_dock
        )

        self._error_dock = QDockWidget("Error Console", self)
        self._error_dock.setObjectName("errorConsoleDock")
        self._error_console = QPlainTextEdit(self._error_dock)
        self._error_console.setObjectName("errorConsole")
        self._error_console.setReadOnly(True)
        self._error_console.setPlaceholderText("Desktop shell errors appear here.")
        self._error_dock.setWidget(self._error_console)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._error_dock)

    def _build_worker(self) -> None:
        self._worker = SimulationWorker(self)
        self._controls.run_requested.connect(self._worker.start_run)
        self._controls.pause_requested.connect(self._worker.request_pause)
        self._controls.step_requested.connect(self._worker.request_step)
        self._controls.resume_requested.connect(self._worker.request_resume)
        self._controls.stop_requested.connect(self._worker.request_stop)
        self._controls.speed_target_requested.connect(
            self._worker.set_speed_target
        )
        self._controls.checkpoint_requested.connect(
            self._worker.create_checkpoint
        )
        self._controls.checkpoint_resume_requested.connect(
            self._worker.resume_checkpoint
        )
        self._worker.snapshot_ready.connect(self._accept_snapshot)
        self._worker.inspection_ready.connect(self._accept_inspection)
        self._worker.checkpoint_created.connect(self._controls.accept_checkpoint)
        self._worker.state_changed.connect(self._controls.accept_state)
        self._worker.error_reported.connect(self.report_error)
        self._worker.stopped.connect(
            lambda: self.statusBar().showMessage("Simulation stopped")
        )
        self._viewer.cell_clicked.connect(self._inspect_cell)
        self._experiment_editor.run_eligibility_changed.connect(
            self._controls.set_editor_run_eligible
        )
        self._controls.set_editor_run_eligible(
            self._experiment_editor.session.run_eligible
        )

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.setObjectName("fileMenu")
        open_action = QAction("&Open Project Reference...", self)
        open_action.setObjectName("openProjectAction")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._choose_project_reference)
        file_menu.addAction(open_action)

        self._recent_menu = file_menu.addMenu("Recent Projects")
        self._recent_menu.setObjectName("recentProjectsMenu")
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.setObjectName("exitAction")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.setObjectName("viewMenu")
        view_menu.addAction(self._project_dock.toggleViewAction())
        view_menu.addAction(self._experiment_dock.toggleViewAction())
        view_menu.addAction(self._controls_dock.toggleViewAction())
        view_menu.addAction(self._inspector_dock.toggleViewAction())
        view_menu.addAction(self._error_dock.toggleViewAction())

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.setObjectName("helpMenu")
        about_action = QAction("&About BioMesh", self)
        about_action.setObjectName("aboutAction")
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _restore_window_layout(self) -> None:
        geometry = self._preferences.window_geometry
        if geometry is not None:
            restored = self.restoreGeometry(
                QByteArray(base64.b64decode(geometry, validate=True))
            )
            if not restored:
                self.report_error("Stored UI window geometry is invalid")
        state = self._preferences.window_state
        if state is not None:
            restored = self.restoreState(
                QByteArray(base64.b64decode(state, validate=True))
            )
            if not restored:
                self.report_error("Stored UI dock state is invalid")

    def _rebuild_recent_projects_menu(self) -> None:
        self._recent_menu.clear()
        if not self._preferences.recent_projects:
            empty = self._recent_menu.addAction("No Recent Projects")
            empty.setEnabled(False)
            return
        for path in self._preferences.recent_projects:
            action = self._recent_menu.addAction(path)
            action.setData(path)
            action.triggered.connect(
                lambda _checked=False, project=path: self.open_project_reference(
                    Path(project)
                )
            )
        self._recent_menu.addSeparator()
        clear_action = self._recent_menu.addAction("Clear Recent Projects")
        clear_action.triggered.connect(self._clear_recent_projects)

    @Slot()
    def _choose_project_reference(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "Open Project Reference",
            "",
            "All files (*)",
        )
        if selected:
            self.open_project_reference(Path(selected))

    @Slot()
    def _clear_recent_projects(self) -> None:
        self._preferences = UiPreferences(
            window_geometry=self._preferences.window_geometry,
            window_state=self._preferences.window_state,
        )
        self._rebuild_recent_projects_menu()
        self.statusBar().showMessage("Recent projects cleared")

    @Slot()
    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About BioMesh",
            "BioMesh P3-WP05 desktop viewer, experiment editor, deterministic "
            "controls, checkpoints, and immutable cell inspection. Scientific "
            "behavior remains owned by the frozen application API.",
        )

    @Slot(object)
    def _accept_snapshot(self, snapshot: RunSnapshot) -> None:
        if not isinstance(snapshot, RunSnapshot):
            self.report_error("Worker returned an invalid simulation snapshot")
            return
        self._viewer.present_snapshot(snapshot)
        self.statusBar().showMessage(
            f"{snapshot.status.value.title()} · step "
            f"{snapshot.step_index}/{snapshot.step_count} · {snapshot.time_s:.6g} s"
        )

    @Slot(object)
    def _accept_inspection(self, inspection: CellInspection) -> None:
        if not isinstance(inspection, CellInspection):
            self.report_error("Worker returned an invalid cell inspection")
            return
        self._inspector.present_inspection(inspection)
        self._inspector_dock.show()

    @Slot(str)
    def _inspect_cell(self, cell_id: str) -> None:
        snapshot = self._viewer.latest_snapshot
        if snapshot is None:
            self.report_error("Cell inspection requires an immutable snapshot")
            return
        self._worker.inspect_cell(
            cell_id, expected_step_index=snapshot.step_index
        )


def _default_repository_root() -> Path:
    """Find source-repository templates without depending on launch directory."""
    source_root = Path(__file__).resolve().parents[3]
    for candidate in (Path.cwd(), source_root):
        if (candidate / "parameters" / "p1_core_model.toml").is_file():
            return candidate
    try:
        return runtime_root()
    except RuntimeResourceError:
        pass
    return Path.cwd()
