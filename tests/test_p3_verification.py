"""Focused regressions for the mandatory P3A CLI verification paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from biomesh.__main__ import main
from biomesh.application import ApplicationService, RunRequest
from biomesh.p2_campaign import resolve_fixture_run

REFERENCE = Path("parameters/phase2_reference.yaml")
FIXTURE = Path("experiments/producer.yaml")


def test_compare_frontends_and_verify_checkpoint_commands(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "comparison"
    assert (
        main(
            [
                "compare-frontends",
                str(REFERENCE),
                "--seed",
                "42",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    comparison = json.loads(capsys.readouterr().out)
    assert comparison["passed"] is True
    assert comparison["mismatch_count"] == 0
    assert comparison["seed"] == 42
    assert comparison["calibration_status"] == "CALIBRATION_REQUIRED"

    assert main(["verify-checkpoint", str(output)]) == 0
    replay = json.loads(capsys.readouterr().out)
    assert replay["passed"] is True
    assert replay["mismatch_count"] == 0
    assert replay["seed"] == 42


def test_application_audit_seed_does_not_expand_p2_campaign_seeds() -> None:
    with pytest.raises(ValueError, match="fixture seed must be one of"):
        resolve_fixture_run(
            fixture_file=FIXTURE,
            condition_id="producer",
            seed=42,
        )
    with ApplicationService() as service:
        snapshot = service.run(RunRequest(FIXTURE, "producer", 42))
        assert snapshot.seed == 42
        assert snapshot.calibration_status == "CALIBRATION_REQUIRED"


def test_verify_checkpoint_rejects_tampering(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "comparison"
    assert (
        main(
            [
                "compare-frontends",
                str(REFERENCE),
                "--seed",
                "42",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    capsys.readouterr()
    checkpoint = output / "checkpoint.json"
    checkpoint.write_bytes(checkpoint.read_bytes() + b" ")

    assert main(["verify-checkpoint", str(output)]) == 2
    error = capsys.readouterr().err
    assert "checkpoint SHA-256 does not match" in error
