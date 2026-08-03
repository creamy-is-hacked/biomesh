"""Application-path regressions for the executable P2-WP06 remediation."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from biomesh.__main__ import main


def test_required_p2_command_surface_writes_real_artifacts(tmp_path: Path) -> None:
    assert main(["validate", "all"]) == 0
    commands = (
        ("experiment", "producer.yaml"),
        ("experiment", "nonproducer.yaml"),
        ("experiment", "competition_50_50.yaml"),
        ("sweep", "qs_threshold_sweep.yaml"),
        ("sweep", "eps_cost_sweep.yaml"),
        ("sweep", "shear_sweep.yaml"),
    )
    for command, fixture_name in commands:
        output = tmp_path / fixture_name.removesuffix(".yaml")
        fixture = Path("experiments") / fixture_name
        assert main([command, str(fixture), "--output", str(output)]) == 0
        manifest = json.loads((output / "campaign_manifest.json").read_text())
        assert manifest["runs"]
        run_directory = output / manifest["runs"][0]["run_manifest"]
        metadata = json.loads((run_directory.parent / "run_metadata.json").read_text())
        assert {
            "commit_hash",
            "seed",
            "parameters",
            "platform",
            "python_version",
        } <= set(metadata)
        assert pq.read_table(run_directory.parent / "summary.parquet").num_rows == 3
        accounting = pq.read_table(run_directory.parent / "mass_balance.parquet")
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
        assert (run_directory.parent / "fields" / "000000.npz").is_file()
    assert main(["report", str(tmp_path / "producer")]) == 0
    assert (tmp_path / "producer" / "report.png").is_file()


def test_malformed_fixture_and_artifact_are_rejected(tmp_path: Path) -> None:
    fixture = tmp_path / "broken.yaml"
    fixture.write_text("not JSON-compatible YAML", encoding="utf-8")
    assert main(["experiment", str(fixture), "--output", str(tmp_path / "out")]) == 2
