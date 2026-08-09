from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

import biomesh.application as application_module
from biomesh.__main__ import main
from biomesh.application import (
    ApplicationError,
    ApplicationService,
    CellInspection,
    RunRequest,
    RunSnapshot,
    RunStatus,
)

FIXTURE = Path("experiments/producer.yaml")


def _request() -> RunRequest:
    return RunRequest(FIXTURE, "producer", 101)


def _complete(service: ApplicationService) -> RunSnapshot:
    snapshot = service.run(_request())
    while snapshot.status is not RunStatus.COMPLETED:
        snapshot = service.step()
    return snapshot


def _scientific_snapshot(snapshot: RunSnapshot) -> RunSnapshot:
    return replace(snapshot, status=RunStatus.COMPLETED)


def test_state_transitions_and_explicit_errors(tmp_path: Path) -> None:
    service = ApplicationService()
    with pytest.raises(ApplicationError, match="pause requires a running"):
        service.pause()
    with pytest.raises(ApplicationError, match="active run"):
        service.inspect()
    with pytest.raises(ApplicationError, match="completed session"):
        service.export(tmp_path / "early-export")

    initial = service.run(_request())
    assert initial.status is RunStatus.RUNNING
    assert initial.step_index == 0
    assert initial.time_s == 0.0
    with pytest.raises(ApplicationError, match="idle application service"):
        service.run(_request())
    with pytest.raises(ApplicationError, match="paused or completed"):
        service.checkpoint(tmp_path / "running.json")

    paused = service.pause()
    assert paused.status is RunStatus.PAUSED
    stepped = service.step()
    assert stepped.status is RunStatus.PAUSED
    assert stepped.step_index == 1
    resumed = service.resume()
    assert resumed.status is RunStatus.RUNNING
    service.step()
    completed = service.step()
    assert completed.status is RunStatus.COMPLETED
    with pytest.raises(ApplicationError, match="running or paused"):
        service.step()
    with pytest.raises(ApplicationError, match="no cell"):
        service.inspect("missing-cell")


def test_snapshots_and_inspection_are_immutable() -> None:
    with ApplicationService() as service:
        snapshot = service.run(_request())
        with pytest.raises(FrozenInstanceError):
            snapshot.time_s = 1.0  # type: ignore[misc]
        field = snapshot.field("carbon")
        array = field.as_array()
        assert not array.flags.writeable
        with pytest.raises(ValueError, match="read-only"):
            array[0, 0] = 0.0
        with pytest.raises(ValueError, match="cannot set WRITEABLE"):
            array.setflags(write=True)

        inspection = service.inspect("cell-000")
        assert isinstance(inspection, CellInspection)
        assert inspection.cell == snapshot.cells[0]
        assert {value.name for value in inspection.local_values} == {
            "carbon",
            "eps",
            "oxygen",
            "quorum_signal",
            "waste",
        }


def test_checkpoint_round_trip_matches_pause_step_resume(tmp_path: Path) -> None:
    expected_output = tmp_path / "expected"
    with ApplicationService() as uninterrupted:
        uninterrupted.run(_request())
        uninterrupted.step()
        uninterrupted.pause()
        uninterrupted.step()
        uninterrupted.resume()
        expected = uninterrupted.step()
        expected_export = uninterrupted.export(expected_output)

    checkpoint_file = tmp_path / "run.checkpoint.json"
    with ApplicationService() as source:
        source.run(_request())
        source.step()
        paused = source.pause()
        checkpoint = source.checkpoint(checkpoint_file)
        assert checkpoint.step_index == 1
        assert checkpoint.sha256

    with ApplicationService() as restored:
        resumed = restored.resume(checkpoint_file)
        assert resumed.status is RunStatus.RUNNING
        assert resumed.step_index == paused.step_index
        assert _scientific_snapshot(resumed) == _scientific_snapshot(paused)
        restored.step()
        actual = restored.step()
        actual_output = tmp_path / "actual"
        actual_export = restored.export(actual_output)

    assert actual == expected
    assert actual_export.files == expected_export.files
    for relative_path in actual_export.files:
        assert (actual_output / relative_path).read_bytes() == (
            expected_output / relative_path
        ).read_bytes()


def test_checkpoint_rejects_configuration_drift(tmp_path: Path) -> None:
    checkpoint_file = tmp_path / "run.checkpoint.json"
    with ApplicationService() as service:
        service.run(_request())
        service.pause()
        service.checkpoint(checkpoint_file)
    payload = json.loads(checkpoint_file.read_text(encoding="utf-8"))
    payload["fixture_sha256"] = "0" * 64
    checkpoint_file.write_text(json.dumps(payload), encoding="utf-8")

    with ApplicationService() as restored:
        with pytest.raises(ApplicationError, match="fixture hash"):
            restored.resume(checkpoint_file)


def test_checkpoint_failure_is_atomic_and_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed checkpoint leaves no partial target and permits a retry."""
    checkpoint_file = tmp_path / "run.checkpoint.json"
    with ApplicationService() as service:
        service.run(_request())
        service.pause()
        original = application_module._atomic_write_bytes

        def fail(_path: Path, _contents: bytes) -> None:
            raise OSError("synthetic checkpoint failure")

        monkeypatch.setattr(application_module, "_atomic_write_bytes", fail)
        with pytest.raises(ApplicationError, match="synthetic checkpoint failure"):
            service.checkpoint(checkpoint_file)
        assert not checkpoint_file.exists()
        monkeypatch.setattr(application_module, "_atomic_write_bytes", original)
        service.checkpoint(checkpoint_file)
        assert checkpoint_file.is_file()


def test_cli_and_application_export_are_byte_equivalent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli_output = tmp_path / "cli"
    assert (
        main(
            [
                "experiment",
                str(FIXTURE),
                "--output",
                str(cli_output),
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.strip() == str(cli_output)

    api_output = tmp_path / "api"
    with ApplicationService() as service:
        _complete(service)
        exported = service.export(api_output)

    cli_run = cli_output / "runs" / "producer" / "seed-101"
    cli_files = tuple(
        sorted(
            path.relative_to(cli_run)
            for path in cli_run.rglob("*")
            if path.is_file() and path.name != "run_manifest.json"
        )
    )
    assert exported.files == cli_files
    for relative_path in exported.files:
        assert (api_output / relative_path).read_bytes() == (
            cli_run / relative_path
        ).read_bytes()


def test_invalid_request_and_export_targets_fail_explicitly(tmp_path: Path) -> None:
    with pytest.raises(ApplicationError, match="nonnegative integer"):
        RunRequest(FIXTURE, "producer", True)  # type: ignore[arg-type]
    with ApplicationService() as service:
        with pytest.raises(ApplicationError, match="fixture seed must be one of"):
            service.run(RunRequest(FIXTURE, "producer", 999))
        _complete(service)
        existing = tmp_path / "existing"
        existing.mkdir()
        with pytest.raises(ApplicationError, match="must not already exist"):
            service.export(existing)


def test_export_failure_is_atomic_and_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed directory export leaves no partial target and permits a retry."""
    output = tmp_path / "export"
    with ApplicationService() as service:
        _complete(service)
        original = application_module.shutil.copytree

        def fail(*_args: object, **_kwargs: object) -> None:
            raise OSError("synthetic export failure")

        monkeypatch.setattr(application_module.shutil, "copytree", fail)
        with pytest.raises(ApplicationError, match="synthetic export failure"):
            service.export(output)
        assert not output.exists()
        monkeypatch.setattr(application_module.shutil, "copytree", original)
        service.export(output)
        assert output.is_dir()
