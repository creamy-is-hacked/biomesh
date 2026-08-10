"""Small P3-WP05 worker boundary around the public application service."""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from biomesh.application import ApplicationService
from biomesh.application_types import (
    ApplicationError,
    CellInspection,
    RunRequest,
    RunSnapshot,
    RunStatus,
)


class WorkerError(ValueError):
    """Raised when a worker command is invalid before it is queued."""


class _CommandKind(StrEnum):
    RUN = "run"
    PAUSE = "pause"
    STEP = "step"
    RESUME = "resume"
    STOP = "stop"
    SPEED = "speed"
    CHECKPOINT = "checkpoint"
    RESUME_CHECKPOINT = "resume_checkpoint"
    INSPECT = "inspect"


@dataclass(frozen=True, slots=True)
class _Command:
    kind: _CommandKind
    value: object | None = None
    expected_step_index: int | None = None


class SimulationWorker(QThread):
    """Serialize application operations and continuous boundary advancement.

    The worker is the only owner of its ``ApplicationService``. Stop and pause
    requests synchronously prevent scheduling another boundary; an interval
    already executing is allowed to finish before the request is accepted.
    """

    snapshot_ready = Signal(object)
    inspection_ready = Signal(object)
    checkpoint_created = Signal(object)
    state_changed = Signal(object)
    stopped = Signal()
    error_reported = Signal(str)
    speed_target_changed = Signal(float)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        service_factory: Callable[[], ApplicationService] = ApplicationService,
        speed_target_hz: float = 10.0,
    ) -> None:
        super().__init__(parent)
        self._service_factory = service_factory
        self._condition = threading.Condition()
        self._commands: deque[_Command] = deque()
        self._pause_requested = threading.Event()
        self._stop_requested = threading.Event()
        self._shutdown_requested = threading.Event()
        self._continuous = False
        self._status = RunStatus.IDLE
        self._speed_target_hz = _validated_speed_target(speed_target_hz)

    @property
    def status(self) -> RunStatus:
        """Return the last application status published by the worker."""
        with self._condition:
            return self._status

    @property
    def speed_target_hz(self) -> float:
        """Return the requested maximum solver-boundary rate."""
        with self._condition:
            return self._speed_target_hz

    def start_run(self, request: RunRequest) -> None:
        """Queue one exact application ``RunRequest`` for continuous execution."""
        if not isinstance(request, RunRequest):
            raise WorkerError("request must be a RunRequest")
        self._pause_requested.clear()
        self._stop_requested.clear()
        self._submit(_Command(_CommandKind.RUN, request))

    def request_pause(self) -> None:
        """Prevent another automatic boundary, then pause through the service."""
        self._pause_requested.set()
        self._submit(_Command(_CommandKind.PAUSE))

    def request_step(self) -> None:
        """Queue exactly one service step while the session is paused."""
        self._submit(_Command(_CommandKind.STEP))

    def request_resume(self) -> None:
        """Resume a paused in-memory session through the service."""
        self._submit(_Command(_CommandKind.RESUME))

    def request_stop(self) -> None:
        """Prevent another automatic boundary, then close the service session."""
        self._stop_requested.set()
        if self._shutdown_requested.is_set():
            raise WorkerError("worker is shutting down")
        with self._condition:
            self._commands.clear()
            self._commands.appendleft(_Command(_CommandKind.STOP))
            self._condition.notify_all()
        if not self.isRunning():
            self.start()

    def set_speed_target(self, boundaries_per_second: float) -> None:
        """Queue a finite positive target rate without changing solver time."""
        value = _validated_speed_target(boundaries_per_second)
        self._submit(_Command(_CommandKind.SPEED, value))

    def create_checkpoint(self, checkpoint_file: Path) -> None:
        """Queue a checkpoint at the current paused or completed boundary."""
        if not isinstance(checkpoint_file, Path):
            raise WorkerError("checkpoint_file must be a Path")
        self._submit(_Command(_CommandKind.CHECKPOINT, checkpoint_file))

    def resume_checkpoint(self, checkpoint_file: Path) -> None:
        """Queue reconstruction of a hash-verified application checkpoint."""
        if not isinstance(checkpoint_file, Path):
            raise WorkerError("checkpoint_file must be a Path")
        self._pause_requested.clear()
        self._stop_requested.clear()
        self._submit(_Command(_CommandKind.RESUME_CHECKPOINT, checkpoint_file))

    def inspect_cell(self, cell_id: str, *, expected_step_index: int) -> None:
        """Inspect a cell only if the selected immutable frame is still current."""
        if not isinstance(cell_id, str) or not cell_id.strip():
            raise WorkerError("cell_id must be a nonblank string")
        if (
            not isinstance(expected_step_index, int)
            or isinstance(expected_step_index, bool)
            or expected_step_index < 0
        ):
            raise WorkerError("expected_step_index must be a nonnegative integer")
        self._submit(
            _Command(_CommandKind.INSPECT, cell_id, expected_step_index)
        )

    def request_shutdown(self) -> None:
        """Request orderly cancellation and release of worker-owned resources."""
        self._stop_requested.set()
        self._shutdown_requested.set()
        with self._condition:
            self._condition.notify_all()

    def run(self) -> None:
        """Own and operate the synchronous service on this background thread."""
        service = self._service_factory()
        next_step_at = time.monotonic()
        try:
            while not self._shutdown_requested.is_set():
                command: _Command | None = None
                automatic_step = False
                with self._condition:
                    while not self._shutdown_requested.is_set():
                        if self._commands:
                            command = self._commands.popleft()
                            break
                        if (
                            self._continuous
                            and not self._pause_requested.is_set()
                            and not self._stop_requested.is_set()
                        ):
                            delay = next_step_at - time.monotonic()
                            if delay <= 0.0:
                                automatic_step = True
                                break
                            self._condition.wait(delay)
                            continue
                        self._condition.wait()
                if self._shutdown_requested.is_set():
                    break
                if command is not None:
                    self._execute(service, command)
                    next_step_at = time.monotonic() + 1.0 / self.speed_target_hz
                elif automatic_step:
                    if self._pause_requested.is_set() or self._stop_requested.is_set():
                        continue
                    self._advance(service)
                    next_step_at = time.monotonic() + 1.0 / self.speed_target_hz
        finally:
            service.close()
            self._set_state(RunStatus.IDLE)

    def _submit(self, command: _Command) -> None:
        if self._shutdown_requested.is_set():
            raise WorkerError("worker is shutting down")
        with self._condition:
            self._commands.append(command)
            self._condition.notify_all()
        if not self.isRunning():
            self.start()

    def _execute(self, service: ApplicationService, command: _Command) -> None:
        try:
            if command.kind is _CommandKind.RUN:
                assert isinstance(command.value, RunRequest)
                snapshot = service.run(command.value)
                self._continuous = True
                self._publish_snapshot(snapshot)
            elif command.kind is _CommandKind.PAUSE:
                snapshot = service.pause()
                self._continuous = False
                self._publish_snapshot(snapshot)
            elif command.kind is _CommandKind.STEP:
                if service.status is not RunStatus.PAUSED:
                    raise ApplicationError(
                        "single-boundary step requires a paused session"
                    )
                self._advance(service)
            elif command.kind is _CommandKind.RESUME:
                snapshot = service.resume()
                self._pause_requested.clear()
                self._continuous = True
                self._publish_snapshot(snapshot)
            elif command.kind is _CommandKind.STOP:
                service.close()
                self._continuous = False
                self._stop_requested.clear()
                self._pause_requested.clear()
                self._set_state(RunStatus.IDLE)
                self.stopped.emit()
            elif command.kind is _CommandKind.SPEED:
                assert isinstance(command.value, float)
                with self._condition:
                    self._speed_target_hz = command.value
                self.speed_target_changed.emit(command.value)
            elif command.kind is _CommandKind.CHECKPOINT:
                assert isinstance(command.value, Path)
                result = service.checkpoint(command.value)
                self.checkpoint_created.emit(result)
            elif command.kind is _CommandKind.RESUME_CHECKPOINT:
                assert isinstance(command.value, Path)
                snapshot = service.resume(command.value)
                self._continuous = snapshot.status is RunStatus.RUNNING
                self._publish_snapshot(snapshot)
            elif command.kind is _CommandKind.INSPECT:
                assert isinstance(command.value, str)
                current = service.inspect()
                assert isinstance(current, RunSnapshot)
                if current.step_index != command.expected_step_index:
                    raise ApplicationError(
                        "selected cell snapshot is stale; select the cell again "
                        "from the newest frame"
                    )
                inspection = service.inspect(command.value)
                assert isinstance(inspection, CellInspection)
                self.inspection_ready.emit(inspection)
        except Exception as error:
            self._handle_error(service, error)

    def _advance(self, service: ApplicationService) -> None:
        try:
            snapshot = service.step()
        except Exception as error:
            self._handle_error(service, error)
            return
        if snapshot.status is RunStatus.COMPLETED:
            self._continuous = False
        self._publish_snapshot(snapshot)

    def _handle_error(self, service: ApplicationService, error: Exception) -> None:
        self._continuous = False
        if service.status is RunStatus.RUNNING:
            try:
                snapshot = service.pause()
            except ApplicationError:
                pass
            else:
                self._pause_requested.set()
                self._publish_snapshot(snapshot)
        else:
            self._set_state(service.status)
        self.error_reported.emit(str(error))

    def _publish_snapshot(self, snapshot: RunSnapshot) -> None:
        self._set_state(snapshot.status)
        self.snapshot_ready.emit(snapshot)

    def _set_state(self, status: RunStatus) -> None:
        with self._condition:
            self._status = status
        self.state_changed.emit(status)


def _validated_speed_target(value: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0.0
    ):
        raise WorkerError("speed target must be finite and positive")
    return float(value)
