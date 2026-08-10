"""P3-WP05 controls restricted to exact accepted P2 fixture requests."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from biomesh.application_types import CheckpointResult, RunRequest, RunStatus

EXACT_P2_FIXTURE_RUNS = (
    ("Producer monoculture", "producer.yaml", "producer"),
    ("Nonproducer monoculture", "nonproducer.yaml", "nonproducer"),
    ("50:50 competition", "competition_50_50.yaml", "competition-50-50"),
    (
        "Intermixed inoculation",
        "inoculation_intermixed.yaml",
        "inoculation-intermixed",
    ),
    (
        "Segregated inoculation",
        "inoculation_segregated.yaml",
        "inoculation-segregated",
    ),
    ("Constitutive EPS", "eps_constitutive.yaml", "eps-constitutive"),
    (
        "Quorum-controlled EPS",
        "eps_quorum_controlled.yaml",
        "eps-quorum-controlled",
    ),
    ("Low QS threshold", "qs_threshold_sweep.yaml", "qs-low"),
    ("High QS threshold", "qs_threshold_sweep.yaml", "qs-high"),
    ("Low nutrients/oxygen", "nutrient_oxygen_sweep.yaml", "resources-low"),
    ("High nutrients/oxygen", "nutrient_oxygen_sweep.yaml", "resources-high"),
    ("Low EPS cost", "eps_cost_sweep.yaml", "eps-cost-low"),
    ("High EPS cost", "eps_cost_sweep.yaml", "eps-cost-high"),
    ("Low shear", "shear_sweep.yaml", "shear-low"),
    ("High shear", "shear_sweep.yaml", "shear-high"),
)
EXACT_P2_SEEDS = (101, 202, 303)


class SimulationControls(QWidget):
    """Emit lifecycle commands without treating editor documents as inputs."""

    run_requested = Signal(object)
    pause_requested = Signal()
    step_requested = Signal()
    resume_requested = Signal()
    stop_requested = Signal()
    speed_target_requested = Signal(float)
    checkpoint_requested = Signal(object)
    checkpoint_resume_requested = Signal(object)

    def __init__(self, runtime_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("simulationControls")
        self._runtime_root = runtime_root.resolve()
        self._status = RunStatus.IDLE
        self._editor_run_eligible = False
        self._build_ui()
        self._refresh_enabled_state()

    @property
    def editor_run_eligible(self) -> bool:
        """Return the current P3-WP04 editor eligibility gate."""
        return self._editor_run_eligible

    @property
    def status(self) -> RunStatus:
        """Return the latest worker lifecycle state."""
        return self._status

    def selected_request(self) -> RunRequest:
        """Build exactly one existing P2 fixture/condition/seed request."""
        selection = self._fixture.currentData()
        seed = self._seed.currentData()
        if (
            not isinstance(selection, tuple)
            or len(selection) != 2
            or not all(isinstance(item, str) for item in selection)
            or not isinstance(seed, int)
            or isinstance(seed, bool)
        ):
            raise ValueError("invalid exact P2 fixture selection")
        fixture_name, condition_id = selection
        return RunRequest(
            self._runtime_root / "experiments" / fixture_name,
            condition_id,
            seed,
        )

    @Slot(bool)
    def set_editor_run_eligible(self, eligible: bool) -> None:
        """Apply the editor gate without passing its document to the engine."""
        if not isinstance(eligible, bool):
            raise ValueError("editor run eligibility must be a bool")
        self._editor_run_eligible = eligible
        self._eligibility.setText(
            "Editor gate: eligible" if eligible else "Editor gate: ineligible"
        )
        self._refresh_enabled_state()

    @Slot(object)
    def accept_state(self, status: RunStatus) -> None:
        """Update buttons from one worker-published application state."""
        if not isinstance(status, RunStatus):
            raise ValueError("status must be a RunStatus")
        self._status = status
        self._state.setText(f"Application state: {status.value}")
        self._refresh_enabled_state()

    @Slot(object)
    def accept_checkpoint(self, result: CheckpointResult) -> None:
        """Display immutable checkpoint identity returned by the service."""
        if not isinstance(result, CheckpointResult):
            raise ValueError("result must be a CheckpointResult")
        self._checkpoint_status.setText(
            f"Checkpoint: {result.checkpoint_file} · step {result.step_index} · "
            f"SHA-256 {result.sha256}"
        )

    def request_checkpoint(self, path: Path) -> None:
        """Emit a checkpoint request for a caller-selected new file."""
        self.checkpoint_requested.emit(path)

    def request_checkpoint_resume(self, path: Path) -> None:
        """Emit a resume request for a caller-selected checkpoint."""
        self.checkpoint_resume_requested.emit(path)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        boundary = QLabel(
            "Runs use only the exact accepted P2 software fixtures below. "
            "The editor document is a validation gate and is never passed to "
            "the frozen application API.",
            self,
        )
        boundary.setObjectName("runInputBoundary")
        boundary.setWordWrap(True)
        layout.addWidget(boundary)

        inputs = QGroupBox("Exact P2 RunRequest", self)
        grid = QGridLayout(inputs)
        self._fixture = QComboBox(inputs)
        self._fixture.setObjectName("runFixtureCondition")
        for title, fixture_name, condition_id in EXACT_P2_FIXTURE_RUNS:
            self._fixture.addItem(title, (fixture_name, condition_id))
        self._seed = QComboBox(inputs)
        self._seed.setObjectName("runSeed")
        for seed in EXACT_P2_SEEDS:
            self._seed.addItem(str(seed), seed)
        grid.addWidget(QLabel("Fixture condition", inputs), 0, 0)
        grid.addWidget(self._fixture, 0, 1)
        grid.addWidget(QLabel("Fixed seed", inputs), 1, 0)
        grid.addWidget(self._seed, 1, 1)
        layout.addWidget(inputs)

        self._state = QLabel("Application state: idle", self)
        self._state.setObjectName("controlApplicationState")
        self._eligibility = QLabel("Editor gate: ineligible", self)
        self._eligibility.setObjectName("controlEditorEligibility")
        layout.addWidget(self._state)
        layout.addWidget(self._eligibility)

        lifecycle = QHBoxLayout()
        self._run = _button("Run", "runButton", self)
        self._pause = _button("Pause", "pauseButton", self)
        self._step = _button("Step one boundary", "stepButton", self)
        self._resume = _button("Resume", "resumeButton", self)
        self._stop = _button("Stop", "stopButton", self)
        self._run.clicked.connect(self._emit_run)
        self._pause.clicked.connect(self.pause_requested)
        self._step.clicked.connect(self.step_requested)
        self._resume.clicked.connect(self.resume_requested)
        self._stop.clicked.connect(self.stop_requested)
        for button in (
            self._run,
            self._pause,
            self._step,
            self._resume,
            self._stop,
        ):
            lifecycle.addWidget(button)
        layout.addLayout(lifecycle)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed target", self))
        self._speed = QDoubleSpinBox(self)
        self._speed.setObjectName("speedTarget")
        self._speed.setRange(0.1, 1000.0)
        self._speed.setDecimals(1)
        self._speed.setValue(10.0)
        self._speed.setSuffix(" boundaries/s")
        self._speed.valueChanged.connect(self.speed_target_requested)
        speed_row.addWidget(self._speed)
        layout.addLayout(speed_row)

        checkpoint_row = QHBoxLayout()
        self._checkpoint = _button("Save Checkpoint…", "checkpointButton", self)
        self._load_checkpoint = _button(
            "Resume Checkpoint…", "resumeCheckpointButton", self
        )
        self._checkpoint.clicked.connect(self._choose_checkpoint)
        self._load_checkpoint.clicked.connect(self._choose_checkpoint_resume)
        checkpoint_row.addWidget(self._checkpoint)
        checkpoint_row.addWidget(self._load_checkpoint)
        layout.addLayout(checkpoint_row)
        self._checkpoint_status = QLabel("No checkpoint operation", self)
        self._checkpoint_status.setObjectName("checkpointStatus")
        self._checkpoint_status.setWordWrap(True)
        layout.addWidget(self._checkpoint_status)
        layout.addStretch()

        focus_order = (
            self._fixture,
            self._seed,
            self._run,
            self._pause,
            self._step,
            self._resume,
            self._stop,
            self._speed,
            self._checkpoint,
            self._load_checkpoint,
        )
        for current, following in zip(
            focus_order[:-1], focus_order[1:], strict=True
        ):
            QWidget.setTabOrder(current, following)

    @Slot()
    def _emit_run(self) -> None:
        self.run_requested.emit(self.selected_request())

    @Slot()
    def _choose_checkpoint(self) -> None:
        selected, _filter = QFileDialog.getSaveFileName(
            self,
            "Create replay checkpoint",
            "",
            "BioMesh checkpoint (*.json)",
        )
        if selected:
            self.request_checkpoint(Path(selected))

    @Slot()
    def _choose_checkpoint_resume(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "Resume replay checkpoint",
            "",
            "BioMesh checkpoint (*.json)",
        )
        if selected:
            self.request_checkpoint_resume(Path(selected))

    def _refresh_enabled_state(self) -> None:
        idle = self._status is RunStatus.IDLE
        running = self._status is RunStatus.RUNNING
        paused = self._status is RunStatus.PAUSED
        completed = self._status is RunStatus.COMPLETED
        self._run.setEnabled(idle and self._editor_run_eligible)
        self._pause.setEnabled(running)
        self._step.setEnabled(paused)
        self._resume.setEnabled(paused and self._editor_run_eligible)
        self._stop.setEnabled(running or paused)
        self._checkpoint.setEnabled(paused or completed)
        self._load_checkpoint.setEnabled(idle and self._editor_run_eligible)


def _button(text: str, object_name: str, parent: QWidget) -> QPushButton:
    button = QPushButton(text, parent)
    button.setObjectName(object_name)
    return button
