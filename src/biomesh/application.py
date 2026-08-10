"""Typed P3-WP01 application boundary over the accepted P2 engine path.

The service owns private mutable engine state.  Callers receive only frozen
records and immutable byte-backed field arrays.  Solver advancement occurs one
accepted P2 interval at a time and retains the recorded P2 update order.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Self

from biomesh.application_types import (
    AccountingSnapshot,
    ApplicationError,
    CellInspection,
    CellSnapshot,
    CheckpointResult,
    ExportResult,
    FieldSnapshot,
    LocalValue,
    MetricSnapshot,
    ParameterProvenance,
    RunRequest,
    RunSnapshot,
    RunStatus,
)
from biomesh.cells import Cell
from biomesh.p2_campaign import (
    FIXTURE_STEP_COUNT,
    FIXTURE_TIME_STEP_S,
    ResolvedFixtureRun,
    _advance_fixture_replicate,
    _finalize_fixture_replicate,
    _FixtureRunState,
    _initialize_fixture_replicate,
    resolve_application_run,
)

CHECKPOINT_SCHEMA_VERSION = 1


class ApplicationService:
    """Small synchronous service boundary for one deterministic P2 run.

    ``run`` creates a session at time zero.  ``step`` advances exactly one
    accepted solver interval.  ``pause`` and ``resume`` only change lifecycle
    state at those boundaries; no worker or GUI behavior is included.
    """

    def __init__(self) -> None:
        self._status = RunStatus.IDLE
        self._resolved: ResolvedFixtureRun | None = None
        self._engine: _FixtureRunState | None = None
        self._temporary: TemporaryDirectory[str] | None = None

    @property
    def status(self) -> RunStatus:
        """Return the current lifecycle state without exposing engine state."""
        return self._status

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_error: object) -> None:
        self.close()

    def close(self) -> None:
        """Release private temporary artifacts owned by this service."""
        if self._temporary is not None:
            self._temporary.cleanup()
        self._temporary = None
        self._engine = None
        self._resolved = None
        self._status = RunStatus.IDLE

    def run(self, request: RunRequest) -> RunSnapshot:
        """Start one exact existing P2 fixture run at its initial boundary."""
        if self._status is not RunStatus.IDLE:
            raise ApplicationError("run requires an idle application service")
        if not isinstance(request, RunRequest):
            raise ApplicationError("request must be a RunRequest")
        try:
            resolved = resolve_application_run(
                fixture_file=request.fixture_file,
                condition_id=request.condition_id,
                seed=request.seed,
            )
            temporary = TemporaryDirectory(prefix="biomesh-application-")
            engine = _initialize_fixture_replicate(
                resolved.request, Path(temporary.name) / "run"
            )
        except (OSError, ValueError, RuntimeError) as error:
            raise ApplicationError(f"unable to start run: {error}") from error
        self._resolved = resolved
        self._temporary = temporary
        self._engine = engine
        self._status = RunStatus.RUNNING
        return self._snapshot()

    def pause(self) -> RunSnapshot:
        """Pause a running session at its current accepted boundary."""
        self._require_status(RunStatus.RUNNING, operation="pause")
        self._status = RunStatus.PAUSED
        return self._snapshot()

    def step(self) -> RunSnapshot:
        """Advance exactly one solver boundary while running or paused."""
        if self._status not in {RunStatus.RUNNING, RunStatus.PAUSED}:
            raise ApplicationError("step requires a running or paused session")
        engine = self._require_engine()
        try:
            _advance_fixture_replicate(engine)
            if engine.step_index == FIXTURE_STEP_COUNT:
                _finalize_fixture_replicate(engine)
                self._status = RunStatus.COMPLETED
        except (OSError, ValueError, RuntimeError) as error:
            raise ApplicationError(f"solver step failed: {error}") from error
        return self._snapshot()

    def resume(self, checkpoint_file: Path | None = None) -> RunSnapshot:
        """Resume a paused session or reconstruct one verified checkpoint."""
        if checkpoint_file is None:
            self._require_status(RunStatus.PAUSED, operation="resume")
            self._status = RunStatus.RUNNING
            return self._snapshot()
        if self._status is not RunStatus.IDLE:
            raise ApplicationError("checkpoint resume requires an idle service")
        checkpoint = _read_checkpoint(checkpoint_file)
        fixture_sha256 = _string(checkpoint, "fixture_sha256")
        checkpoint_parameters = _checkpoint_parameter_hashes(checkpoint)
        step_index = _integer(checkpoint, "step_index")
        request = RunRequest(
            fixture_file=Path(_string(checkpoint, "fixture_file")),
            condition_id=_string(checkpoint, "condition_id"),
            seed=_integer(checkpoint, "seed"),
        )
        snapshot = self.run(request)
        resolved = self._require_resolved()
        if resolved.fixture_sha256 != fixture_sha256:
            self.close()
            raise ApplicationError(
                "checkpoint fixture hash does not match current file"
            )
        expected_parameters = tuple(
            (record.label, record.sha256) for record in resolved.request.parameter_files
        )
        if expected_parameters != checkpoint_parameters:
            self.close()
            raise ApplicationError(
                "checkpoint biological-parameter hashes do not match current files"
            )
        for _ in range(step_index):
            snapshot = self.step()
        if snapshot.status is not RunStatus.COMPLETED:
            self._status = RunStatus.RUNNING
            snapshot = self._snapshot()
        return snapshot

    def checkpoint(self, checkpoint_file: Path) -> CheckpointResult:
        """Write a new hash-bound replay checkpoint at a stable boundary."""
        if self._status not in {RunStatus.PAUSED, RunStatus.COMPLETED}:
            raise ApplicationError("checkpoint requires a paused or completed session")
        if checkpoint_file.exists() or checkpoint_file.is_symlink():
            raise ApplicationError("checkpoint_file must not already exist")
        if not checkpoint_file.parent.is_dir():
            raise ApplicationError("checkpoint_file parent directory must exist")
        resolved = self._require_resolved()
        engine = self._require_engine()
        payload = {
            "calibration_status": resolved.calibration_status,
            "condition_id": resolved.request.condition.condition_id,
            "fixture_file": str(resolved.fixture_file),
            "fixture_sha256": resolved.fixture_sha256,
            "parameter_files": [
                {"label": item.label, "sha256": item.sha256}
                for item in resolved.request.parameter_files
            ],
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "seed": resolved.request.seed,
            "status": self._status.value,
            "step_index": engine.step_index,
            "step_count": FIXTURE_STEP_COUNT,
        }
        contents = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
        try:
            _atomic_write_bytes(checkpoint_file, contents)
        except OSError as error:
            raise ApplicationError(f"unable to write checkpoint: {error}") from error
        return CheckpointResult(
            checkpoint_file=checkpoint_file,
            sha256=hashlib.sha256(contents).hexdigest(),
            step_index=engine.step_index,
        )

    def inspect(self, cell_id: str | None = None) -> RunSnapshot | CellInspection:
        """Inspect the full immutable snapshot or one cell-local view."""
        snapshot = self._snapshot()
        if cell_id is None:
            return snapshot
        if not isinstance(cell_id, str) or not cell_id.strip():
            raise ApplicationError("cell_id must be a nonblank string")
        engine = self._require_engine()
        cell = next((item for item in engine.cells if item.cell_id == cell_id), None)
        if cell is None:
            raise ApplicationError(f"current snapshot has no cell {cell_id!r}")
        quorum_by_id = {item.cell_id: item for item in engine.quorum_states}
        quorum_state = quorum_by_id[cell.cell_id]
        return CellInspection(
            cell=_cell_snapshot(cell),
            local_values=_local_values(engine, cell),
            quorum_activation_fraction=quorum_state.current.activation_fraction,
        )

    def export(self, output_directory: Path) -> ExportResult:
        """Export the complete existing P2 raw artifact set without conversion."""
        self._require_status(RunStatus.COMPLETED, operation="export")
        if output_directory.exists() or output_directory.is_symlink():
            raise ApplicationError("output_directory must not already exist")
        if not output_directory.parent.is_dir():
            raise ApplicationError("output_directory parent directory must exist")
        engine = self._require_engine()
        if engine.finalized_paths is None:
            raise ApplicationError("completed run has no finalized output paths")
        source_directory = engine.finalized_paths.run_directory
        try:
            output_directory.resolve().relative_to(source_directory.resolve())
        except ValueError:
            pass
        else:
            raise ApplicationError("output_directory must be outside the source run")
        temporary_directory: Path | None = None
        try:
            temporary_directory = Path(
                tempfile.mkdtemp(
                    prefix=f".{output_directory.name}.",
                    dir=output_directory.parent,
                )
            )
            shutil.copytree(source_directory, temporary_directory, dirs_exist_ok=True)
            os.replace(temporary_directory, output_directory)
        except OSError as error:
            if temporary_directory is not None:
                shutil.rmtree(temporary_directory, ignore_errors=True)
            raise ApplicationError(f"unable to export run: {error}") from error
        files = tuple(
            sorted(
                path.relative_to(output_directory)
                for path in output_directory.rglob("*")
                if path.is_file()
            )
        )
        return ExportResult(output_directory=output_directory, files=files)

    def _snapshot(self) -> RunSnapshot:
        resolved = self._require_resolved()
        engine = self._require_engine()
        current_time_s = engine.step_index * FIXTURE_TIME_STEP_S
        current_metrics = tuple(
            MetricSnapshot(item.metric, item.unit, item.value)
            for item in engine.observations
            if item.time_s == current_time_s
        )
        return RunSnapshot(
            status=self._status,
            condition_id=resolved.request.condition.condition_id,
            seed=resolved.request.seed,
            step_index=engine.step_index,
            step_count=FIXTURE_STEP_COUNT,
            time_s=current_time_s,
            configuration_sha256=resolved.fixture_sha256,
            calibration_status=resolved.calibration_status,
            parameter_provenance=tuple(
                ParameterProvenance(item.label, item.sha256)
                for item in resolved.request.parameter_files
            ),
            cells=tuple(_cell_snapshot(cell) for cell in engine.cells),
            fields=(
                FieldSnapshot.from_array(
                    name="carbon",
                    unit="mol m^-3",
                    values=engine.fields.carbon.concentration_mol_m3,
                ),
                FieldSnapshot.from_array(
                    name="oxygen",
                    unit="mol m^-3",
                    values=engine.fields.oxygen.concentration_mol_m3,
                ),
                FieldSnapshot.from_array(
                    name="quorum_signal",
                    unit="mol m^-3",
                    values=engine.signal.concentration_mol_m3,
                ),
                FieldSnapshot.from_array(
                    name="eps", unit="kg m^-3", values=engine.eps.density_kg_m3
                ),
                FieldSnapshot.from_array(
                    name="waste",
                    unit="mol m^-3",
                    values=engine.waste.concentration_mol_m3,
                ),
            ),
            metrics=current_metrics,
            accounting=tuple(
                AccountingSnapshot(
                    item.quantity,
                    item.unit,
                    item.initial_amount,
                    item.final_amount,
                    item.net_input_amount,
                    item.residual_amount,
                    item.relative_error,
                )
                for item in engine.mass_balance_entries
            ),
        )

    def _require_status(self, status: RunStatus, *, operation: str) -> None:
        if self._status is not status:
            raise ApplicationError(f"{operation} requires a {status.value} session")

    def _require_engine(self) -> _FixtureRunState:
        if self._engine is None:
            raise ApplicationError("application service has no active run")
        return self._engine

    def _require_resolved(self) -> ResolvedFixtureRun:
        if self._resolved is None:
            raise ApplicationError("application service has no active run")
        return self._resolved


def _cell_snapshot(cell: Cell) -> CellSnapshot:
    return CellSnapshot(
        cell_id=cell.cell_id,
        parent_id=cell.parent_id,
        x_m=cell.x_m,
        y_m=cell.y_m,
        orientation_rad=cell.orientation_rad,
        length_m=cell.length_m,
        radius_m=cell.radius_m,
        dry_biomass_kg=cell.dry_biomass_kg,
        age_s=cell.age_s,
        state=cell.state,
        strain=cell.strain,
    )


def _local_values(engine: _FixtureRunState, cell: Cell) -> tuple[LocalValue, ...]:
    row, column = engine.fields.carbon.cell_index(cell.x_m, cell.y_m)
    return (
        LocalValue(
            "carbon",
            "mol m^-3",
            float(engine.fields.carbon.concentration_mol_m3[row, column]),
        ),
        LocalValue(
            "oxygen",
            "mol m^-3",
            float(engine.fields.oxygen.concentration_mol_m3[row, column]),
        ),
        LocalValue(
            "quorum_signal",
            "mol m^-3",
            float(engine.signal.concentration_mol_m3[row, column]),
        ),
        LocalValue("eps", "kg m^-3", float(engine.eps.density_kg_m3[row, column])),
        LocalValue(
            "waste",
            "mol m^-3",
            float(engine.waste.concentration_mol_m3[row, column]),
        ),
    )


def _read_checkpoint(path: Path) -> dict[str, Any]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ApplicationError(f"invalid checkpoint {path}: {error}") from error
    expected = {
        "calibration_status",
        "condition_id",
        "fixture_file",
        "fixture_sha256",
        "parameter_files",
        "schema_version",
        "seed",
        "status",
        "step_index",
        "step_count",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ApplicationError("checkpoint has an invalid field set")
    if payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise ApplicationError("checkpoint schema_version is unsupported")
    if payload.get("step_count") != FIXTURE_STEP_COUNT:
        raise ApplicationError("checkpoint step_count does not match the engine")
    if payload.get("calibration_status") != "CALIBRATION_REQUIRED":
        raise ApplicationError("checkpoint calibration boundary is invalid")
    if payload.get("status") not in {
        RunStatus.PAUSED.value,
        RunStatus.COMPLETED.value,
    }:
        raise ApplicationError("checkpoint status must be paused or completed")
    step_index = payload.get("step_index")
    if (
        not isinstance(step_index, int)
        or isinstance(step_index, bool)
        or not 0 <= step_index <= FIXTURE_STEP_COUNT
    ):
        raise ApplicationError("checkpoint step_index is out of range")
    if (payload.get("status") == RunStatus.COMPLETED.value) != (
        step_index == FIXTURE_STEP_COUNT
    ):
        raise ApplicationError("checkpoint status and step_index are inconsistent")
    return payload


def _checkpoint_parameter_hashes(
    checkpoint: dict[str, Any],
) -> tuple[tuple[str, str], ...]:
    value = checkpoint.get("parameter_files")
    if not isinstance(value, list):
        raise ApplicationError("checkpoint parameter_files must be a list")
    records: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"label", "sha256"}:
            raise ApplicationError("checkpoint parameter file record is invalid")
        label = item.get("label")
        sha256 = item.get("sha256")
        if not isinstance(label, str) or not isinstance(sha256, str):
            raise ApplicationError("checkpoint parameter file identity is invalid")
        records.append((label, sha256))
    return tuple(records)


def _string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ApplicationError(f"checkpoint {key} must be a nonblank string")
    return value


def _integer(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ApplicationError(f"checkpoint {key} must be an integer")
    return value


def _atomic_write_bytes(path: Path, contents: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    os.close(descriptor)
    try:
        with temporary_path.open("wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
