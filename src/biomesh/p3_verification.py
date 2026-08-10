"""Deterministic P3 frontend-equivalence and checkpoint verification paths.

These verification adapters exercise the existing P2 fixture engine through
the CLI runner boundary and the public P3 application service.  They add no
biological equations or parameter values.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from biomesh.application import ApplicationService
from biomesh.application_types import ApplicationError, RunRequest, RunStatus
from biomesh.p2_campaign import (
    _run_fixture_replicate,
    resolve_application_run,
)

REFERENCE_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1
REPORT_NAME = "frontend_equivalence.json"
CHECKPOINT_NAME = "checkpoint.json"
CLI_DIRECTORY = "cli"
GUI_DIRECTORY = "gui"


@dataclass(frozen=True, slots=True)
class FrontendReference:
    """Strict non-biological selector for one existing manufactured fixture."""

    configuration_file: Path
    fixture_file: Path
    condition_id: str
    calibration_status: str
    purpose: str


def load_frontend_reference(path: Path) -> FrontendReference:
    """Load one strict JSON-compatible YAML frontend reference selector."""
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ApplicationError(f"invalid frontend reference {path}: {error}") from error
    expected = {
        "calibration_status",
        "condition_id",
        "fixture_file",
        "purpose",
        "schema_version",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ApplicationError("frontend reference has an invalid field set")
    if payload.get("schema_version") != REFERENCE_SCHEMA_VERSION:
        raise ApplicationError("frontend reference schema_version is unsupported")
    if payload.get("calibration_status") != "CALIBRATION_REQUIRED":
        raise ApplicationError(
            "frontend reference must preserve CALIBRATION_REQUIRED status"
        )
    condition_id = _nonblank_string(payload, "condition_id")
    fixture_label = _nonblank_string(payload, "fixture_file")
    purpose = _nonblank_string(payload, "purpose")
    fixture_candidate = path.parent / fixture_label
    if fixture_candidate.is_symlink():
        raise ApplicationError(
            f"frontend reference fixture must not be a symlink: {fixture_candidate}"
        )
    fixture_file = fixture_candidate.resolve()
    if not fixture_file.is_file():
        raise ApplicationError(
            f"frontend reference fixture is not a regular file: {fixture_file}"
        )
    return FrontendReference(
        configuration_file=path.resolve(),
        fixture_file=fixture_file,
        condition_id=condition_id,
        calibration_status="CALIBRATION_REQUIRED",
        purpose=purpose,
    )


def compare_frontends(
    *, reference_file: Path, seed: int, output_directory: Path
) -> dict[str, object]:
    """Atomically compare canonical CLI and application-service artifact bytes."""
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ApplicationError("comparison seed must be a nonnegative integer")
    if output_directory.exists() or output_directory.is_symlink():
        raise ApplicationError("comparison output directory must not already exist")
    if not output_directory.parent.is_dir():
        raise ApplicationError("comparison output parent directory must exist")

    reference = load_frontend_reference(reference_file)
    resolved = resolve_application_run(
        fixture_file=reference.fixture_file,
        condition_id=reference.condition_id,
        seed=seed,
    )
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{output_directory.name}.", dir=output_directory.parent
        )
    )
    try:
        cli_directory = temporary / CLI_DIRECTORY
        _run_fixture_replicate(resolved.request, cli_directory)

        gui_directory = temporary / GUI_DIRECTORY
        with ApplicationService() as service:
            snapshot = service.run(
                RunRequest(reference.fixture_file, reference.condition_id, seed)
            )
            while snapshot.status is not RunStatus.COMPLETED:
                snapshot = service.step()
            service.export(gui_directory)

        checkpoint_file = temporary / CHECKPOINT_NAME
        with ApplicationService() as service:
            service.run(
                RunRequest(reference.fixture_file, reference.condition_id, seed)
            )
            service.step()
            service.pause()
            checkpoint = service.checkpoint(checkpoint_file)

        cli_files = _file_records(cli_directory)
        gui_files = _file_records(gui_directory)
        mismatches = _record_mismatches(cli_files, gui_files)
        report: dict[str, object] = {
            "calibration_status": reference.calibration_status,
            "checkpoint": {
                "path": CHECKPOINT_NAME,
                "sha256": checkpoint.sha256,
                "step_index": checkpoint.step_index,
            },
            "cli_directory": CLI_DIRECTORY,
            "condition_id": reference.condition_id,
            "configuration_file": str(reference.configuration_file),
            "configuration_sha256": _sha256(reference.configuration_file),
            "fixture_file": str(reference.fixture_file),
            "fixture_sha256": resolved.fixture_sha256,
            "gui_directory": GUI_DIRECTORY,
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
            "parameter_files": [
                {"label": item.label, "sha256": item.sha256}
                for item in resolved.request.parameter_files
            ],
            "passed": not mismatches,
            "purpose": reference.purpose,
            "schema_version": REPORT_SCHEMA_VERSION,
            "seed": seed,
        }
        (temporary / REPORT_NAME).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, output_directory)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    if mismatches:
        raise ApplicationError(
            f"CLI and GUI artifacts differ in {len(mismatches)} path(s)"
        )
    report["output_directory"] = str(output_directory.resolve())
    return report


def verify_checkpoint(run_directory: Path) -> dict[str, object]:
    """Replay a hash-bound checkpoint and compare with stored GUI artifacts."""
    if not run_directory.is_dir() or run_directory.is_symlink():
        raise ApplicationError("checkpoint run directory must be a regular directory")
    report = _read_report(run_directory / REPORT_NAME)
    checkpoint = _mapping(report, "checkpoint")
    checkpoint_path = _contained_path(
        run_directory, _nonblank_string(checkpoint, "path")
    )
    expected_checkpoint_sha256 = _nonblank_string(checkpoint, "sha256")
    actual_checkpoint_sha256 = _sha256(checkpoint_path)
    if actual_checkpoint_sha256 != expected_checkpoint_sha256:
        raise ApplicationError("checkpoint SHA-256 does not match the run report")
    gui_directory = _contained_path(
        run_directory, _nonblank_string(report, "gui_directory")
    )
    expected = _file_records(gui_directory)

    with tempfile.TemporaryDirectory(
        prefix=".biomesh-checkpoint-verify-", dir=run_directory.parent
    ) as temporary_name:
        replay_directory = Path(temporary_name) / "replay"
        with ApplicationService() as service:
            snapshot = service.resume(checkpoint_path)
            while snapshot.status is not RunStatus.COMPLETED:
                snapshot = service.step()
            service.export(replay_directory)
        actual = _file_records(replay_directory)
    mismatches = _record_mismatches(expected, actual)
    result: dict[str, object] = {
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": actual_checkpoint_sha256,
        "file_count": len(expected),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "passed": not mismatches,
        "run_directory": str(run_directory.resolve()),
        "schema_version": REPORT_SCHEMA_VERSION,
        "seed": report.get("seed"),
    }
    if mismatches:
        raise ApplicationError(
            f"checkpoint replay differs in {len(mismatches)} path(s)"
        )
    return result


def _read_report(path: Path) -> dict[str, Any]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ApplicationError(f"invalid frontend report {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ApplicationError("frontend report must be a JSON object")
    required = {
        "calibration_status",
        "checkpoint",
        "cli_directory",
        "condition_id",
        "configuration_file",
        "configuration_sha256",
        "fixture_file",
        "fixture_sha256",
        "gui_directory",
        "mismatch_count",
        "mismatches",
        "parameter_files",
        "passed",
        "purpose",
        "schema_version",
        "seed",
    }
    if set(payload) != required:
        raise ApplicationError("frontend report has an invalid field set")
    if payload.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise ApplicationError("frontend report schema_version is unsupported")
    if payload.get("passed") is not True or payload.get("mismatch_count") != 0:
        raise ApplicationError("frontend report did not record equivalence")
    if payload.get("calibration_status") != "CALIBRATION_REQUIRED":
        raise ApplicationError("frontend report calibration boundary is invalid")
    return payload


def _file_records(directory: Path) -> dict[str, str]:
    if not directory.is_dir() or directory.is_symlink():
        raise ApplicationError(f"artifact directory is invalid: {directory}")
    records: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ApplicationError(f"artifact tree contains a symlink: {path}")
        if path.is_file():
            records[path.relative_to(directory).as_posix()] = _sha256(path)
    if not records:
        raise ApplicationError(f"artifact directory is empty: {directory}")
    return records


def _record_mismatches(
    expected: dict[str, str], actual: dict[str, str]
) -> list[str]:
    return [
        path
        for path in sorted(set(expected) | set(actual))
        if expected.get(path) != actual.get(path)
    ]


def _contained_path(root: Path, label: str) -> Path:
    unresolved = root / label
    if unresolved.is_symlink():
        raise ApplicationError("frontend report path must not be a symlink")
    candidate = unresolved.resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ApplicationError(
            "frontend report path escapes its run directory"
        ) from error
    return candidate


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise ApplicationError(f"unable to hash {path}: {error}") from error


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ApplicationError(f"frontend report {key} must be an object")
    return value


def _nonblank_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ApplicationError(f"frontend record {key} must be a nonblank string")
    return value
