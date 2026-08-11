"""Traceable P4-WP02 comparison and presentation-neutral report data.

The report layer reads only hash-verified P4-WP01 completed-run artifacts. It
does not mutate raw runs, infer scientific conclusions, or introduce model,
plugin, registry, queue, archive, packaging, or acceleration behavior.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from biomesh.project_campaign import (
    ArtifactRecord,
    CampaignRecord,
    CampaignRunStatus,
    CampaignService,
    ProjectCampaignError,
    ProjectDefinition,
    ProjectState,
    RunRecord,
)
from biomesh.project_report_metrics import REPORT_METRICS, ReportMetric
from biomesh.project_report_output import REPORT_SCHEMA_VERSION, publish_report
from biomesh.project_report_statistics import (
    CONFIDENCE_LEVEL,
    difference_interval,
    hedges_g,
    median,
    sample_uncertainty,
)


@dataclass(frozen=True, slots=True)
class ReportGenerationResult:
    """Identity and compact counts for one atomically published report."""

    output_directory: Path
    campaign_id: str
    completed_runs: int
    missing_runs: int
    summary_rows: int
    comparison_rows: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "campaign_id": self.campaign_id,
            "comparison_rows": self.comparison_rows,
            "completed_runs": self.completed_runs,
            "missing_runs": self.missing_runs,
            "output_directory": str(self.output_directory),
            "summary_rows": self.summary_rows,
        }


@dataclass(frozen=True, slots=True)
class _Observation:
    point_id: str
    condition_id: str
    metric: str
    unit: str
    time_s: float
    value: float
    run_id: str
    seed: int
    replicate_index: int
    artifact_path: str
    artifact_sha256: str
    artifact_size_bytes: int
    row_index: int
    source_column: str

    def trace_dict(self) -> dict[str, object]:
        return {
            "artifact_path": self.artifact_path,
            "artifact_sha256": self.artifact_sha256,
            "artifact_size_bytes": self.artifact_size_bytes,
            "replicate_index": self.replicate_index,
            "row_index": self.row_index,
            "run_id": self.run_id,
            "seed": self.seed,
            "source_column": self.source_column,
            "value": self.value,
        }

    def row_dict(self) -> dict[str, object]:
        """Return the complete flat observation used by the CSV output."""
        return {
            "condition_id": self.condition_id,
            "metric": self.metric,
            "point_id": self.point_id,
            "time_s": self.time_s,
            "unit": self.unit,
            **self.trace_dict(),
        }


def generate_campaign_report(
    project_directory: Path, campaign_id: str, output_directory: Path
) -> ReportGenerationResult:
    """Publish deterministic comparisons traced to immutable raw run bytes."""
    project = project_directory.resolve()
    output = output_directory.resolve()
    artifact_root = project / "artifacts"
    if output == artifact_root or output.is_relative_to(artifact_root):
        raise ProjectCampaignError("report output must not be inside raw run artifacts")
    if output.exists() or output.is_symlink():
        raise ProjectCampaignError(f"report output already exists: {output}")

    definition, state = CampaignService(project).verified_records()
    campaign = _campaign(definition, campaign_id)
    runs = tuple(run for run in state.runs if run.campaign_id == campaign_id)
    if not runs:
        raise ProjectCampaignError(f"campaign has no planned runs: {campaign_id}")

    completed = tuple(run for run in runs if run.status is CampaignRunStatus.COMPLETED)
    missing = tuple(
        run for run in runs if run.status is not CampaignRunStatus.COMPLETED
    )
    observations = _read_observations(project, completed)
    summaries = _condition_summaries(campaign, runs, observations)
    comparisons = _pairwise_comparisons(campaign, summaries)
    data = _report_data(
        definition,
        state,
        campaign,
        runs,
        observations,
        summaries,
        comparisons,
    )
    publish_report(
        output,
        definition,
        state,
        campaign,
        data,
        [item.row_dict() for item in observations],
    )
    return ReportGenerationResult(
        output_directory=output,
        campaign_id=campaign_id,
        completed_runs=len(completed),
        missing_runs=len(missing),
        summary_rows=len(summaries),
        comparison_rows=len(comparisons),
    )


def _campaign(definition: ProjectDefinition, campaign_id: str) -> CampaignRecord:
    for campaign in definition.campaigns:
        if campaign.campaign_id == campaign_id:
            return campaign
    raise ProjectCampaignError(f"unknown campaign: {campaign_id}")


def _read_observations(
    project: Path, completed_runs: Sequence[RunRecord]
) -> tuple[_Observation, ...]:
    observations: list[_Observation] = []
    for run in completed_runs:
        records = {record.path: record for record in run.artifacts}
        for metric in REPORT_METRICS:
            record = records.get(metric.artifact_path)
            if record is None:
                raise ProjectCampaignError(
                    f"completed run {run.run_id} lacks report source "
                    f"{metric.artifact_path}"
                )
            path = project / "artifacts" / run.run_id / metric.artifact_path
            observations.extend(_metric_observations(run, metric, record, path))
    return tuple(
        sorted(
            observations,
            key=lambda item: (
                item.point_id,
                item.metric,
                item.time_s,
                item.replicate_index,
                item.seed,
                item.run_id,
            ),
        )
    )


def _metric_observations(
    run: RunRecord,
    metric: ReportMetric,
    record: ArtifactRecord,
    path: Path,
) -> list[_Observation]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ProjectCampaignError(f"report source is missing or unsafe: {path}")
        contents = path.read_bytes()
        if (
            len(contents) != record.size_bytes
            or hashlib.sha256(contents).hexdigest() != record.sha256
        ):
            raise ProjectCampaignError(f"report source artifact changed: {path}")
        table = pq.read_table(
            pa.BufferReader(contents), columns=["time_s", metric.column]
        )
    except ProjectCampaignError:
        raise
    except Exception as error:
        raise ProjectCampaignError(
            f"unable to read report source {path}: {error}"
        ) from error
    times = table.column("time_s").to_pylist()
    values = table.column(metric.column).to_pylist()
    if not times or len(times) != len(values):
        raise ProjectCampaignError(f"report source is empty or malformed: {path}")
    result: list[_Observation] = []
    seen_times: set[float] = set()
    for row_index, (raw_time, raw_value) in enumerate(zip(times, values, strict=True)):
        if (
            isinstance(raw_time, bool)
            or not isinstance(raw_time, (int, float))
            or isinstance(raw_value, bool)
            or not isinstance(raw_value, (int, float))
        ):
            raise ProjectCampaignError(f"report source has non-numeric values: {path}")
        time_s = float(raw_time)
        value = float(raw_value)
        if not math.isfinite(time_s) or time_s < 0.0 or not math.isfinite(value):
            raise ProjectCampaignError(f"report source has non-finite values: {path}")
        if time_s in seen_times:
            raise ProjectCampaignError(
                f"report source has duplicate metric times: {path}"
            )
        seen_times.add(time_s)
        result.append(
            _Observation(
                point_id=run.point_id,
                condition_id=run.condition_id,
                metric=metric.name,
                unit=metric.unit,
                time_s=time_s,
                value=value,
                run_id=run.run_id,
                seed=run.seed,
                replicate_index=run.replicate_index,
                artifact_path=(
                    Path("artifacts") / run.run_id / metric.artifact_path
                ).as_posix(),
                artifact_sha256=record.sha256,
                artifact_size_bytes=record.size_bytes,
                row_index=row_index,
                source_column=metric.column,
            )
        )
    return result


def _condition_summaries(
    campaign: CampaignRecord,
    runs: Sequence[RunRecord],
    observations: Sequence[_Observation],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, float], list[_Observation]] = defaultdict(list)
    for observation in observations:
        grouped[(observation.point_id, observation.metric, observation.time_s)].append(
            observation
        )
    point_conditions = {
        point.point_id: point.condition_id for point in campaign.sweep_matrix
    }
    expected = {
        point.point_id: tuple(run for run in runs if run.point_id == point.point_id)
        for point in campaign.sweep_matrix
    }
    rows: list[dict[str, Any]] = []
    for (point_id, metric, time_s), values in sorted(grouped.items()):
        ordered = sorted(values, key=lambda item: (item.replicate_index, item.seed))
        numeric = [item.value for item in ordered]
        present = {item.run_id for item in ordered}
        missing_ids = [
            run.run_id for run in expected[point_id] if run.run_id not in present
        ]
        uncertainty = sample_uncertainty(numeric)
        rows.append(
            {
                "claim_status": (
                    "SINGLE_SEED_ONLY" if len(numeric) == 1 else "REPLICATED"
                ),
                "condition_id": point_conditions[point_id],
                "confidence_interval_high": uncertainty[3],
                "confidence_interval_low": uncertainty[2],
                "distribution": [item.trace_dict() for item in ordered],
                "expected_replicate_count": len(expected[point_id]),
                "maximum": max(numeric),
                "mean": uncertainty[0],
                "median": median(numeric),
                "metric": metric,
                "minimum": min(numeric),
                "missing_run_ids": missing_ids,
                "observed_replicate_count": len(numeric),
                "point_id": point_id,
                "sample_standard_deviation": uncertainty[1],
                "sample_variance": (
                    None if uncertainty[1] is None else uncertainty[1] ** 2
                ),
                "single_seed_warning": len(numeric) == 1,
                "time_s": time_s,
                "uncertainty_status": (
                    "not_estimated_single_seed"
                    if len(numeric) == 1
                    else "student_t_95_percent"
                ),
                "unit": ordered[0].unit,
            }
        )
    return rows


def _pairwise_comparisons(
    campaign: CampaignRecord,
    summaries: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_point_metric_time = {
        (row["point_id"], row["metric"], row["time_s"]): row for row in summaries
    }
    rows: list[dict[str, Any]] = []
    points = list(campaign.sweep_matrix)
    metric_times = sorted({(row["metric"], row["time_s"]) for row in summaries})
    for left_index, left in enumerate(points):
        for right in points[left_index + 1 :]:
            for metric, time_s in metric_times:
                left_row = by_point_metric_time.get((left.point_id, metric, time_s))
                right_row = by_point_metric_time.get((right.point_id, metric, time_s))
                if left_row is None or right_row is None:
                    continue
                left_values = [item["value"] for item in left_row["distribution"]]
                right_values = [item["value"] for item in right_row["distribution"]]
                difference = float(left_row["mean"]) - float(right_row["mean"])
                low, high = difference_interval(left_values, right_values, difference)
                single = len(left_values) == 1 or len(right_values) == 1
                rows.append(
                    {
                        "claim_status": (
                            "SINGLE_SEED_ONLY" if single else "REPLICATED"
                        ),
                        "confidence_interval_high": high,
                        "confidence_interval_low": low,
                        "effect_size": {
                            "mean_difference": difference,
                            "standardized_method": "Hedges_g",
                            "standardized_value": hedges_g(left_values, right_values),
                            "unit": left_row["unit"],
                        },
                        "left_condition_id": left.condition_id,
                        "left_missing_run_ids": left_row["missing_run_ids"],
                        "left_observed_replicates": len(left_values),
                        "left_point_id": left.point_id,
                        "metric": metric,
                        "right_condition_id": right.condition_id,
                        "right_missing_run_ids": right_row["missing_run_ids"],
                        "right_observed_replicates": len(right_values),
                        "right_point_id": right.point_id,
                        "single_seed_warning": single,
                        "time_s": time_s,
                        "uncertainty_status": (
                            "not_estimated_single_seed"
                            if single
                            else "welch_student_t_95_percent"
                        ),
                        "unit": left_row["unit"],
                    }
                )
    return rows


def _report_data(
    definition: ProjectDefinition,
    state: ProjectState,
    campaign: CampaignRecord,
    runs: Sequence[RunRecord],
    observations: Sequence[_Observation],
    summaries: Sequence[dict[str, Any]],
    comparisons: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    completed = [run for run in runs if run.status is CampaignRunStatus.COMPLETED]
    missing = [run for run in runs if run.status is not CampaignRunStatus.COMPLETED]
    single_seed = campaign.replicate_count == 1
    warnings: list[dict[str, str]] = []
    if single_seed:
        warnings.append(
            {
                "code": "SINGLE_SEED_CAMPAIGN",
                "message": (
                    "Campaign has one planned seed per condition; uncertainty and "
                    "replicated claims are unavailable."
                ),
            }
        )
    if missing:
        warnings.append(
            {
                "code": "MISSING_RUNS",
                "message": (
                    f"{len(missing)} of {len(runs)} planned runs are not completed; "
                    "they remain visible in run_coverage and in each available "
                    "summary's missing_run_ids."
                ),
            }
        )
    if len(campaign.sweep_matrix) < 2:
        warnings.append(
            {
                "code": "NO_PAIRWISE_CONDITION",
                "message": "Campaign has fewer than two conditions to compare.",
            }
        )
    return {
        "campaign": {
            "calibration_status": "CALIBRATION_REQUIRED",
            "campaign_id": campaign.campaign_id,
            "completed_run_count": len(completed),
            "confidence_level": CONFIDENCE_LEVEL,
            "expected_run_count": len(runs),
            "missing_run_count": len(missing),
            "replicate_count": campaign.replicate_count,
            "single_seed_warning": single_seed,
            "title": campaign.title,
        },
        "condition_summaries": list(summaries),
        "metric_definitions": [
            {
                "name": metric.name,
                "source_artifact": metric.artifact_path,
                "source_column": metric.column,
                "title": metric.title,
                "unit": metric.unit,
            }
            for metric in REPORT_METRICS
        ],
        "methods": {
            "condition_uncertainty": (
                "Two-sided Student t confidence interval for replicate means; "
                "unavailable for one observation."
            ),
            "effect_size": (
                "Left-minus-right mean difference in the recorded SI unit and "
                "bias-corrected Hedges g when pooled variance is defined."
            ),
            "pairwise_uncertainty": (
                "Two-sided Welch Student t confidence interval for the difference "
                "in means; unavailable if either side has one observation."
            ),
            "scope": (
                "Descriptive comparison data only; no biological conclusion, "
                "calibration claim, or significance decision is generated."
            ),
        },
        "observation_count": len(observations),
        "pairwise_comparisons": list(comparisons),
        "project": {
            "definition_sha256": state.definition_sha256,
            "project_id": definition.project.project_id,
            "state_generation": state.generation,
        },
        "report_kind": "P4-WP02 comparison and report data",
        "run_coverage": [_coverage(run) for run in runs],
        "schema_version": REPORT_SCHEMA_VERSION,
        "warnings": warnings,
    }


def _coverage(run: RunRecord) -> dict[str, Any]:
    return {
        "condition_id": run.condition_id,
        "failure": (
            None if run.failure is None else run.failure.model_dump(mode="json")
        ),
        "point_id": run.point_id,
        "replicate_index": run.replicate_index,
        "run_id": run.run_id,
        "seed": run.seed,
        "status": run.status.value,
    }
