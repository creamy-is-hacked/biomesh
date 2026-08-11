"""Deterministic atomic JSON and CSV publication for P4-WP02."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from io import StringIO
from pathlib import Path
from typing import Any

from biomesh.project_campaign import (
    CampaignRecord,
    ProjectCampaignError,
    ProjectDefinition,
    ProjectState,
)

REPORT_SCHEMA_VERSION = 1


def publish_report(
    output: Path,
    definition: ProjectDefinition,
    state: ProjectState,
    campaign: CampaignRecord,
    data: Mapping[str, Any],
    observations: Sequence[Mapping[str, object]],
) -> None:
    """Publish a new report directory or remove all staged data on failure."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ProjectCampaignError("report output parent must be a real directory")
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        files: dict[str, bytes] = {
            "report_data.json": _json_bytes(data),
            "run_coverage.csv": _coverage_csv(data["run_coverage"]),
            "observations.csv": _observations_csv(observations),
            "condition_summaries.csv": _summary_csv(data["condition_summaries"]),
            "pairwise_comparisons.csv": _comparison_csv(data["pairwise_comparisons"]),
        }
        for name, contents in files.items():
            (staging / name).write_bytes(contents)
        manifest = {
            "campaign_id": campaign.campaign_id,
            "files": [
                {
                    "path": name,
                    "sha256": hashlib.sha256(contents).hexdigest(),
                    "size_bytes": len(contents),
                }
                for name, contents in sorted(files.items())
            ],
            "project_definition_sha256": state.definition_sha256,
            "project_id": definition.project.project_id,
            "report_kind": "P4-WP02 comparison and report data",
            "schema_version": REPORT_SCHEMA_VERSION,
            "source_state_generation": state.generation,
        }
        (staging / "report_manifest.json").write_bytes(_json_bytes(manifest))
        os.replace(staging, output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _csv_bytes(
    fieldnames: Sequence[str], rows: Sequence[Mapping[str, object]]
) -> bytes:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _coverage_csv(rows: Sequence[Mapping[str, Any]]) -> bytes:
    flattened = [
        {
            **{
                key: row[key]
                for key in (
                    "run_id",
                    "point_id",
                    "condition_id",
                    "replicate_index",
                    "seed",
                    "status",
                )
            },
            "failure_kind": None if row["failure"] is None else row["failure"]["kind"],
            "failure_message": None
            if row["failure"] is None
            else row["failure"]["message"],
        }
        for row in rows
    ]
    return _csv_bytes(
        (
            "run_id",
            "point_id",
            "condition_id",
            "replicate_index",
            "seed",
            "status",
            "failure_kind",
            "failure_message",
        ),
        flattened,
    )


def _observations_csv(observations: Sequence[Mapping[str, object]]) -> bytes:
    return _csv_bytes(
        (
            "point_id",
            "condition_id",
            "metric",
            "unit",
            "time_s",
            "value",
            "run_id",
            "replicate_index",
            "seed",
            "artifact_path",
            "artifact_sha256",
            "artifact_size_bytes",
            "row_index",
            "source_column",
        ),
        observations,
    )


def _summary_csv(rows: Sequence[Mapping[str, Any]]) -> bytes:
    flattened = [
        {
            key: row[key]
            for key in (
                "point_id",
                "condition_id",
                "metric",
                "unit",
                "time_s",
                "expected_replicate_count",
                "observed_replicate_count",
                "mean",
                "median",
                "minimum",
                "maximum",
                "sample_variance",
                "sample_standard_deviation",
                "confidence_interval_low",
                "confidence_interval_high",
                "single_seed_warning",
                "claim_status",
                "uncertainty_status",
            )
        }
        | {"missing_run_ids": ";".join(row["missing_run_ids"])}
        for row in rows
    ]
    return _csv_bytes(
        (
            "point_id",
            "condition_id",
            "metric",
            "unit",
            "time_s",
            "expected_replicate_count",
            "observed_replicate_count",
            "missing_run_ids",
            "mean",
            "median",
            "minimum",
            "maximum",
            "sample_variance",
            "sample_standard_deviation",
            "confidence_interval_low",
            "confidence_interval_high",
            "single_seed_warning",
            "claim_status",
            "uncertainty_status",
        ),
        flattened,
    )


def _comparison_csv(rows: Sequence[Mapping[str, Any]]) -> bytes:
    flattened = [
        {
            "left_point_id": row["left_point_id"],
            "left_condition_id": row["left_condition_id"],
            "right_point_id": row["right_point_id"],
            "right_condition_id": row["right_condition_id"],
            "metric": row["metric"],
            "unit": row["unit"],
            "time_s": row["time_s"],
            "left_observed_replicates": row["left_observed_replicates"],
            "right_observed_replicates": row["right_observed_replicates"],
            "left_missing_run_ids": ";".join(row["left_missing_run_ids"]),
            "right_missing_run_ids": ";".join(row["right_missing_run_ids"]),
            "mean_difference": row["effect_size"]["mean_difference"],
            "hedges_g": row["effect_size"]["standardized_value"],
            "confidence_interval_low": row["confidence_interval_low"],
            "confidence_interval_high": row["confidence_interval_high"],
            "single_seed_warning": row["single_seed_warning"],
            "claim_status": row["claim_status"],
            "uncertainty_status": row["uncertainty_status"],
        }
        for row in rows
    ]
    return _csv_bytes(
        (
            "left_point_id",
            "left_condition_id",
            "right_point_id",
            "right_condition_id",
            "metric",
            "unit",
            "time_s",
            "left_observed_replicates",
            "right_observed_replicates",
            "left_missing_run_ids",
            "right_missing_run_ids",
            "mean_difference",
            "hedges_g",
            "confidence_interval_low",
            "confidence_interval_high",
            "single_seed_warning",
            "claim_status",
            "uncertainty_status",
        ),
        flattened,
    )
