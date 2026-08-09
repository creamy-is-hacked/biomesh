"""Application-path regressions for the executable P2-WP06 remediation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from biomesh.__main__ import main
from biomesh.experiments import REQUIRED_FIELD_ARRAYS, REQUIRED_RUN_FILES
from biomesh.p2_campaign import (
    BIOLOGICAL_PARAMETER_FILES,
    FIXTURE_SEEDS,
    load_fixture_command,
    report_campaign,
    validate_all,
)

PUBLISHED_COMMANDS = (
    ("experiment", "producer.yaml", ("producer",)),
    ("experiment", "nonproducer.yaml", ("nonproducer",)),
    ("experiment", "competition_50_50.yaml", ("competition-50-50",)),
    (
        "experiment",
        "inoculation_intermixed.yaml",
        ("inoculation-intermixed",),
    ),
    (
        "experiment",
        "inoculation_segregated.yaml",
        ("inoculation-segregated",),
    ),
    ("experiment", "eps_constitutive.yaml", ("eps-constitutive",)),
    (
        "experiment",
        "eps_quorum_controlled.yaml",
        ("eps-quorum-controlled",),
    ),
    ("sweep", "qs_threshold_sweep.yaml", ("qs-low", "qs-high")),
    (
        "sweep",
        "nutrient_oxygen_sweep.yaml",
        ("resources-low", "resources-high"),
    ),
    ("sweep", "eps_cost_sweep.yaml", ("eps-cost-low", "eps-cost-high")),
    ("sweep", "shear_sweep.yaml", ("shear-low", "shear-high")),
)


def test_published_fixture_set_covers_every_executable_condition_once() -> None:
    result = validate_all(Path.cwd())

    assert result["fixture_count"] == 11
    assert result["condition_count"] == 15
    assert result["seeds"] == list(FIXTURE_SEEDS)
    assert {path.name for path in Path("experiments").glob("*.yaml")} == {
        fixture_name for _, fixture_name, _ in PUBLISHED_COMMANDS
    }
    published_conditions: list[str] = []
    for command_name, fixture_name, condition_ids in PUBLISHED_COMMANDS:
        fixture = load_fixture_command(Path("experiments") / fixture_name)
        assert fixture.fixture_kind == command_name
        assert fixture.condition_ids == condition_ids
        published_conditions.extend(condition_ids)
    assert len(published_conditions) == len(set(published_conditions)) == 15


def test_required_p2_command_surface_writes_real_artifacts(tmp_path: Path) -> None:
    assert main(["validate", "all"]) == 0
    for command, fixture_name, condition_ids in PUBLISHED_COMMANDS:
        output = tmp_path / fixture_name.removesuffix(".yaml")
        fixture = Path("experiments") / fixture_name
        assert main([command, str(fixture), "--output", str(output)]) == 0
        manifest = json.loads((output / "campaign_manifest.json").read_text())
        configuration = manifest["campaign_configuration"]
        assert configuration["seeds"] == list(FIXTURE_SEEDS)
        assert configuration["biological_parameter_files"] == list(
            BIOLOGICAL_PARAMETER_FILES
        )
        assert {
            condition["condition_id"] for condition in configuration["conditions"]
        } == set(condition_ids)
        assert len(manifest["runs"]) == len(condition_ids) * len(FIXTURE_SEEDS)
        assert {record["seed"] for record in manifest["runs"]} == set(FIXTURE_SEEDS)
        for record in manifest["runs"]:
            run_manifest = output / record["run_manifest"]
            run_directory = run_manifest.parent
            raw_manifest = json.loads(run_manifest.read_text())
            assert raw_manifest["seed"] == record["seed"]
            assert raw_manifest["condition"]["condition_id"] in condition_ids
            assert {
                parameter["label"] for parameter in raw_manifest["parameter_files"]
            } == set(BIOLOGICAL_PARAMETER_FILES)
            raw_artifacts = raw_manifest["raw_artifacts"]
            raw_paths = {artifact["path"] for artifact in raw_artifacts}
            assert REQUIRED_RUN_FILES <= raw_paths
            for artifact in raw_artifacts:
                artifact_path = run_directory / artifact["path"]
                contents = artifact_path.read_bytes()
                assert len(contents) == artifact["size_bytes"]
                assert hashlib.sha256(contents).hexdigest() == artifact["sha256"]
            metadata = json.loads((run_directory / "run_metadata.json").read_text())
            assert {
                "commit_hash",
                "seed",
                "parameters",
                "platform",
                "python_version",
            } <= set(metadata)
            assert metadata["parameters"]["software_fixture"] == (
                "manufactured SI software validation"
            )
            for table_name in REQUIRED_RUN_FILES - {"run_metadata.json"}:
                pq.read_table(run_directory / table_name)
            assert pq.read_table(run_directory / "summary.parquet").num_rows == 3
            accounting = pq.read_table(run_directory / "mass_balance.parquet")
            assert {
                "carbon",
                "oxygen",
                "dry_biomass",
                "eps",
                "quorum_signal",
                "waste",
            } <= set(accounting.column("quantity").to_pylist())
            residuals = accounting.column("residual_amount").to_pylist()
            assert max(abs(value) for value in residuals) < 1e-24
            for field_path in sorted((run_directory / "fields").glob("*.npz")):
                with np.load(field_path, allow_pickle=False) as field_archive:
                    assert REQUIRED_FIELD_ARRAYS <= set(field_archive.files)
        statistics = json.loads((output / "summary_statistics.json").read_text())
        assert statistics["statistics"]
        assert all(
            row["replicate_count"] == len(FIXTURE_SEEDS)
            and row["variance"] >= 0.0
            and row["confidence_interval_low"] <= row["mean"]
            <= row["confidence_interval_high"]
            for row in statistics["statistics"]
        )
        rankings = json.loads((output / "sensitivity_ranking.json").read_text())
        assert bool(rankings["rankings"]) == (command == "sweep")
        assert main(["report", str(output)]) == 0
        assert (output / "report.png").is_file()


def test_malformed_fixture_and_artifact_are_rejected(tmp_path: Path) -> None:
    fixture = tmp_path / "broken.yaml"
    fixture.write_text("not JSON-compatible YAML", encoding="utf-8")
    assert main(["experiment", str(fixture), "--output", str(tmp_path / "out")]) == 2
    assert (
        main(
            [
                "sweep",
                "experiments/producer.yaml",
                "--output",
                str(tmp_path / "wrong-command"),
            ]
        )
        == 2
    )

    output = tmp_path / "valid"
    assert (
        main(
            [
                "experiment",
                "experiments/producer.yaml",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    campaign = json.loads((output / "campaign_manifest.json").read_text())
    run_manifest_path = output / campaign["runs"][0]["run_manifest"]
    run_directory = run_manifest_path.parent
    summary_path = run_directory / "summary.parquet"
    summary_bytes = summary_path.read_bytes()
    summary_path.unlink()
    assert main(["report", str(output)]) == 2
    summary_path.write_bytes(summary_bytes)

    raw_manifest = json.loads(run_manifest_path.read_text())
    field_record = next(
        record
        for record in raw_manifest["raw_artifacts"]
        if record["path"].endswith(".npz")
    )
    field_path = run_directory / field_record["path"]
    malformed_bytes = b"not a NumPy archive"
    field_path.write_bytes(malformed_bytes)
    field_record["size_bytes"] = len(malformed_bytes)
    field_record["sha256"] = hashlib.sha256(malformed_bytes).hexdigest()
    run_manifest_path.write_text(
        json.dumps(raw_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    assert main(["report", str(output)]) == 2


def test_report_publication_failure_is_atomic_and_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed report render preserves no partial report target."""
    output = tmp_path / "report-output"
    assert (
        main(
            [
                "experiment",
                "experiments/producer.yaml",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    from matplotlib.figure import Figure

    def fail(*_args: object, **_kwargs: object) -> None:
        raise OSError("synthetic report failure")

    monkeypatch.setattr(Figure, "savefig", fail)
    with pytest.raises(OSError, match="synthetic report failure"):
        report_campaign(output)
    assert not (output / "report.png").exists()
    monkeypatch.undo()
    assert report_campaign(output).is_file()
