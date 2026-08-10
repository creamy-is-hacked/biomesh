"""Focused P3-WP06 analytics and export acceptance tests."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

import biomesh.gui.analytics_export as export_module
from biomesh.application import ApplicationService
from biomesh.application_types import RunRequest, RunSnapshot, RunStatus
from biomesh.gui.analytics import ANALYTICS_PLOTS, analytics_records
from biomesh.gui.analytics_export import (
    AnalyticsExportCancelled,
    export_analytics_bundle,
)

FIXTURE = Path("experiments/competition_50_50.yaml")


def _complete(service: ApplicationService) -> tuple[RunSnapshot, ...]:
    snapshot = service.run(RunRequest(FIXTURE, "competition-50-50", 101))
    snapshots = [snapshot]
    while snapshot.status is not RunStatus.COMPLETED:
        snapshot = service.step()
        snapshots.append(snapshot)
    return tuple(snapshots)


def test_plot_records_match_snapshots_and_canonical_stored_metrics_exactly(
    tmp_path: Path,
) -> None:
    with ApplicationService() as service:
        snapshots = _complete(service)
        service.export(tmp_path / "canonical")

    records = analytics_records(snapshots)
    by_series = {
        name: [record for record in records if record.series == name]
        for name in {record.series for record in records}
    }
    metric_snapshots = [snapshot for snapshot in snapshots if snapshot.metrics]
    combined = zip(
        metric_snapshots,
        by_series["total_dry_biomass_kg"],
        by_series["producer_cell_frequency"],
        by_series["total_eps_kg"],
        by_series["quorum_active_fraction"],
        by_series["biofilm_thickness_m"],
        by_series["biofilm_roughness_m"],
        by_series["carbon_penetration_depth_m"],
        by_series["oxygen_penetration_depth_m"],
        strict=True,
    )
    for (
        snapshot,
        biomass,
        ratio,
        eps,
        quorum,
        thickness,
        roughness,
        carbon,
        oxygen,
    ) in combined:
        metrics = {item.name: item.value for item in snapshot.metrics}
        assert biomass.value == metrics[biomass.source_metric]
        assert ratio.value == metrics[ratio.source_metric]
        assert eps.value == metrics[eps.source_metric]
        assert quorum.value == metrics[quorum.source_metric]
        assert thickness.value == metrics[thickness.source_metric]
        assert roughness.value == metrics[roughness.source_metric]
        assert carbon.value == metrics[carbon.source_metric]
        assert oxygen.value == metrics[oxygen.source_metric]

    summary = pq.read_table(tmp_path / "canonical" / "summary.parquet").to_pylist()
    competition = pq.read_table(
        tmp_path / "canonical" / "competition_summary.parquet"
    ).to_pylist()
    eps_rows = pq.read_table(
        tmp_path / "canonical" / "eps_summary.parquet"
    ).to_pylist()
    assert [item.value for item in by_series["population_cell_count"]] == [
        float(row["cell_count"]) for row in summary
    ]
    assert [item.value for item in by_series["total_dry_biomass_kg"]] == [
        row["total_dry_biomass_kg"] for row in summary
    ]
    assert [item.value for item in by_series["biofilm_thickness_m"]] == [
        row["biofilm_height_m"] for row in summary
    ]
    assert [item.value for item in by_series["biofilm_roughness_m"]] == [
        row["biofilm_roughness_m"] for row in summary
    ]
    assert [item.value for item in by_series["producer_cell_frequency"]] == [
        row["producer_cell_frequency"] for row in competition
    ]
    assert [item.value for item in by_series["total_eps_kg"]] == [
        row["total_eps_kg"] for row in eps_rows
    ]


def test_export_schema_provenance_and_canonical_artifacts(
    tmp_path: Path,
) -> None:
    with ApplicationService() as expected_service:
        _complete(expected_service)
        expected_service.export(tmp_path / "expected")
    with ApplicationService() as service:
        snapshots = _complete(service)
        result = export_analytics_bundle(
            service, tmp_path / "bundle", snapshots, threading.Event()
        )

    assert result.manifest_file == tmp_path / "bundle" / "run_manifest.json"
    manifest = json.loads(result.manifest_file.read_text(encoding="utf-8"))
    final = snapshots[-1]
    assert manifest["schema_version"] == 1
    assert manifest["seed"] == final.seed
    assert manifest["condition_id"] == final.condition_id
    assert manifest["configuration_sha256"] == final.configuration_sha256
    assert manifest["calibration_status"] == "CALIBRATION_REQUIRED"
    assert manifest["biological_parameter_files"] == [
        {"label": item.label, "sha256": item.sha256}
        for item in final.parameter_provenance
    ]
    assert len(manifest["commit_hash"]) == 40
    software = manifest["software_versions"]
    assert software["python_version"] == sys.version.split()[0]
    assert {"numpy", "pyarrow", "scipy", "PySide6", "pyqtgraph"} <= set(
        software["dependency_versions"]
    )

    expected = tmp_path / "expected"
    bundle = tmp_path / "bundle"
    for source in sorted(expected.glob("*.parquet")):
        assert (bundle / "tables" / source.name).read_bytes() == source.read_bytes()
    for source in sorted((expected / "fields").glob("*.npz")):
        assert (bundle / "fields" / source.name).read_bytes() == source.read_bytes()
    assert (bundle / "run_metadata.json").read_bytes() == (
        expected / "run_metadata.json"
    ).read_bytes()

    expected_records = analytics_records(snapshots)
    parquet_rows = pq.read_table(bundle / "analytics" / "metrics.parquet").to_pylist()
    assert [row["value"] for row in parquet_rows] == [
        item.value for item in expected_records
    ]
    with (bundle / "analytics" / "metrics.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        csv_rows = list(csv.DictReader(stream))
    assert [float(row["value"]) for row in csv_rows] == [
        item.value for item in expected_records
    ]
    for plot in ANALYTICS_PLOTS:
        assert (bundle / "plots" / f"{plot.name}.png").read_bytes().startswith(
            b"\x89PNG\r\n\x1a\n"
        )
    artifact_paths = [item["path"] for item in manifest["artifacts"]]
    assert artifact_paths == sorted(artifact_paths)
    assert "run_manifest.json" not in artifact_paths


def test_export_failure_is_atomic_and_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with ApplicationService() as service:
        snapshots = _complete(service)
        original = export_module._write_parquet

        def fail(_path: Path, _records: object) -> None:
            raise OSError("synthetic analytics table failure")

        monkeypatch.setattr(export_module, "_write_parquet", fail)
        with pytest.raises(OSError, match="synthetic analytics table failure"):
            export_analytics_bundle(
                service, tmp_path / "bundle", snapshots, threading.Event()
            )
        assert not (tmp_path / "bundle").exists()
        assert not list(tmp_path.glob(".bundle.*"))
        monkeypatch.setattr(export_module, "_write_parquet", original)
        export_analytics_bundle(
            service, tmp_path / "bundle", snapshots, threading.Event()
        )
    assert (tmp_path / "bundle" / "run_manifest.json").is_file()


def test_export_cancellation_leaves_no_partial_target(tmp_path: Path) -> None:
    cancel = threading.Event()
    cancel.set()
    with ApplicationService() as service:
        snapshots = _complete(service)
        with pytest.raises(AnalyticsExportCancelled, match="cancelled"):
            export_analytics_bundle(service, tmp_path / "bundle", snapshots, cancel)
    assert not (tmp_path / "bundle").exists()
    assert not list(tmp_path.glob(".bundle.*"))


def test_live_panel_worker_responsiveness_cancellation_and_errors(
    tmp_path: Path,
) -> None:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["MPLCONFIGDIR"] = str(tmp_path / "matplotlib-config")
    result = subprocess.run(
        [sys.executable, "tests/gui_analytics_probe.py", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
