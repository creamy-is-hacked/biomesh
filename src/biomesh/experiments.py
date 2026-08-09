"""Reproducible replicated-experiment harness for P2-WP06.

The harness owns campaign expansion, provenance, artifact validation, and
replicate statistics.  A caller-supplied runner owns the already-approved P2
component update order; this module does not introduce a new biological
mechanism or silently choose a coupling sequence.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite, sqrt
from pathlib import Path
from typing import Annotated, Literal, Self

import numpy as np
from pydantic import (
    AllowInfNan,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)
from scipy.stats import t as student_t  # type: ignore[import-untyped]

from biomesh.config import BiologicalParameter

NonBlankText = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
FiniteFloat = Annotated[float, AllowInfNan(allow_inf_nan=False)]
ExperimentFamily = Literal[
    "producer_monoculture",
    "nonproducer_monoculture",
    "competition_50_50",
    "inoculation_pattern",
    "eps_control",
    "quorum_threshold_sweep",
    "nutrient_oxygen_sweep",
    "eps_cost_sweep",
    "shear_sweep",
]
EPSControl = Literal["constitutive", "quorum_controlled"]

REQUIRED_FAMILIES: frozenset[str] = frozenset(
    {
        "producer_monoculture",
        "nonproducer_monoculture",
        "competition_50_50",
        "inoculation_pattern",
        "eps_control",
        "quorum_threshold_sweep",
        "nutrient_oxygen_sweep",
        "eps_cost_sweep",
        "shear_sweep",
    }
)
SWEEP_PARAMETERS: Mapping[str, frozenset[str]] = {
    "quorum_threshold_sweep": frozenset(
        {"quorum_activation_half_saturation_constant"}
    ),
    "nutrient_oxygen_sweep": frozenset(
        {"carbon_bulk_concentration", "oxygen_bulk_concentration"}
    ),
    "eps_cost_sweep": frozenset({"maximum_eps_allocation_fraction"}),
    "shear_sweep": frozenset({"surface_parallel_shear_stress"}),
}
REQUIRED_METRIC_UNITS: Mapping[str, str] = {
    "producer_cell_frequency": "1",
    "total_dry_biomass_kg": "kg",
    "total_eps_kg": "kg",
    # P2-WP01 defines a continuous response, not an unapproved binary threshold.
    "quorum_active_fraction": "1",
    "active_biomass_kg": "kg",
    "dormant_biomass_kg": "kg",
    "dead_biomass_kg": "kg",
    "detached_biomass_kg": "kg",
    "biofilm_thickness_m": "m",
    "biofilm_roughness_m": "m",
    "biofilm_footprint_m": "m",
    "carbon_penetration_depth_m": "m",
    "oxygen_penetration_depth_m": "m",
    "detachment_rate_s": "s^-1",
}
REQUIRED_RUN_FILES: frozenset[str] = frozenset(
    {
        "run_metadata.json",
        "cell_snapshots.parquet",
        "summary.parquet",
        "division_events.parquet",
        "mass_balance.parquet",
        "quorum_history.parquet",
        "eps_summary.parquet",
        "competition_summary.parquet",
        "competition_strains.parquet",
        "competition_cells.parquet",
        "physiology_summary.parquet",
        "shear_summary.parquet",
    }
)
REQUIRED_FIELD_ARRAYS: frozenset[str] = frozenset(
    {
        "carbon_concentration_mol_m3",
        "oxygen_concentration_mol_m3",
        "quorum_signal_concentration_mol_m3",
        "eps_density_kg_m3",
        "waste_concentration_mol_m3",
    }
)


class ExperimentValidationError(ValueError):
    """Raised when a campaign, run, or artifact set is incomplete."""


class SweepParameter(BiologicalParameter):
    """One SI/provenance-complete condition override with a named level."""

    level_id: NonBlankText


class ExperimentCondition(BaseModel):
    """One condition in the required P2-WP06 experiment matrix."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    condition_id: NonBlankText
    family: ExperimentFamily
    producer_fraction: FiniteFloat = Field(ge=0.0, le=1.0)
    inoculation_pattern: NonBlankText
    eps_control: EPSControl
    parameter_overrides: list[SweepParameter] = Field(default_factory=list)
    notes: NonBlankText

    @model_validator(mode="after")
    def validate_family_contract(self) -> Self:
        """Keep fixed-composition controls and sweep inputs explicit."""
        expected_fraction = {
            "producer_monoculture": 1.0,
            "nonproducer_monoculture": 0.0,
            "competition_50_50": 0.5,
        }.get(self.family)
        if (
            expected_fraction is not None
            and self.producer_fraction != expected_fraction
        ):
            raise ValueError(
                f"{self.family} requires producer_fraction={expected_fraction}"
            )
        names = [parameter.name for parameter in self.parameter_overrides]
        if len(names) != len(set(names)):
            raise ValueError("condition parameter override names must be unique")
        required = SWEEP_PARAMETERS.get(self.family, frozenset())
        missing = sorted(required - set(names))
        if missing:
            raise ValueError(
                f"{self.family} is missing parameter overrides: " + ", ".join(missing)
            )
        return self


class ExperimentCampaign(BaseModel):
    """Complete, calibration-labelled P2-WP06 campaign definition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    campaign_id: NonBlankText
    purpose: NonBlankText
    calibration_status: Literal["CALIBRATION_REQUIRED"]
    confidence_level: FiniteFloat = Field(gt=0.0, lt=1.0)
    seeds: list[int] = Field(min_length=2)
    biological_parameter_files: list[NonBlankText] = Field(min_length=1)
    conditions: list[ExperimentCondition] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_campaign_matrix(self) -> Self:
        """Require all experiments, multiple patterns, sweep levels, and seeds."""
        if any(isinstance(seed, bool) or seed < 0 for seed in self.seeds):
            raise ValueError("seeds must be nonnegative integers")
        if len(self.seeds) != len(set(self.seeds)):
            raise ValueError("seeds must be unique")
        if len(self.biological_parameter_files) != len(
            set(self.biological_parameter_files)
        ):
            raise ValueError("biological_parameter_files must be unique")
        condition_ids = [condition.condition_id for condition in self.conditions]
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("condition IDs must be unique")
        families = {condition.family for condition in self.conditions}
        missing_families = sorted(REQUIRED_FAMILIES - families)
        if missing_families:
            raise ValueError(
                "campaign is missing required experiment families: "
                + ", ".join(missing_families)
            )
        patterns = {
            condition.inoculation_pattern
            for condition in self.conditions
            if condition.family == "inoculation_pattern"
        }
        if len(patterns) < 2:
            raise ValueError("inoculation_pattern requires at least two patterns")
        controls = {
            condition.eps_control
            for condition in self.conditions
            if condition.family == "eps_control"
        }
        if controls != {"constitutive", "quorum_controlled"}:
            raise ValueError(
                "eps_control requires constitutive and quorum_controlled conditions"
            )
        for family, parameter_names in SWEEP_PARAMETERS.items():
            family_conditions = [
                condition for condition in self.conditions if condition.family == family
            ]
            if len(family_conditions) < 2:
                raise ValueError(f"{family} requires at least two conditions")
            for parameter_name in parameter_names:
                levels = {
                    parameter.level_id
                    for condition in family_conditions
                    for parameter in condition.parameter_overrides
                    if parameter.name == parameter_name
                }
                if len(levels) < 2:
                    raise ValueError(
                        f"{family} requires at least two {parameter_name} levels"
                    )
        return self


@dataclass(frozen=True, slots=True)
class ParameterFileRecord:
    """One immutable campaign-level biological-parameter file record."""

    label: str
    path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class ExperimentRunRequest:
    """Complete condition and provenance passed to one run executor."""

    campaign_id: str
    condition: ExperimentCondition
    seed: int
    parameter_files: tuple[ParameterFileRecord, ...]


@dataclass(frozen=True, slots=True)
class ExperimentObservation:
    """One scalar result at one time, ready for replicate aggregation."""

    metric: str
    unit: str
    time_s: float
    value: float

    def __post_init__(self) -> None:
        if not self.metric.strip() or not self.unit.strip():
            raise ExperimentValidationError(
                "observation metric and unit must not be blank"
            )
        if not isfinite(self.time_s) or self.time_s < 0.0:
            raise ExperimentValidationError(
                "observation time_s must be finite and nonnegative"
            )
        if not isfinite(self.value):
            raise ExperimentValidationError("observation value must be finite")


ExperimentRunner = Callable[
    [ExperimentRunRequest, Path], Sequence[ExperimentObservation]
]


@dataclass(frozen=True, slots=True)
class ExperimentCampaignResult:
    """Final deterministic campaign artifacts."""

    output_directory: Path
    campaign_manifest: Path
    summary_statistics: Path
    sensitivity_ranking: Path
    run_manifests: tuple[Path, ...]


def load_experiment_campaign(path: Path) -> ExperimentCampaign:
    """Load one strict TOML campaign definition."""
    try:
        with path.open("rb") as campaign_file:
            contents = tomllib.load(campaign_file)
    except OSError as error:
        raise ExperimentValidationError(
            f"unable to read experiment campaign {path}: {error.strerror or error}"
        ) from error
    except tomllib.TOMLDecodeError as error:
        raise ExperimentValidationError(
            f"invalid TOML in experiment campaign {path}: {error}"
        ) from error
    try:
        return ExperimentCampaign.model_validate(contents)
    except ValidationError as error:
        raise ExperimentValidationError(
            f"invalid experiment campaign {path}: {error}"
        ) from error


def run_experiment_campaign(
    *,
    configuration: ExperimentCampaign,
    configuration_file: Path,
    output_directory: Path,
    runner: ExperimentRunner,
) -> ExperimentCampaignResult:
    """Execute every fixed condition/seed pair and aggregate its observations."""
    if not isinstance(configuration, ExperimentCampaign):
        raise ExperimentValidationError(
            "configuration must be an ExperimentCampaign instance"
        )
    if not callable(runner):
        raise ExperimentValidationError("runner must be callable")
    if output_directory.exists():
        raise ExperimentValidationError("output_directory must not already exist")
    try:
        configuration_bytes = configuration_file.read_bytes()
    except OSError as error:
        raise ExperimentValidationError(
            f"unable to read campaign provenance file {configuration_file}: "
            f"{error.strerror or error}"
        ) from error
    parameter_files = _parameter_file_records(
        configuration, configuration_file.parent
    )
    output_directory.mkdir(parents=True)
    runs_directory = output_directory / "runs"
    runs_directory.mkdir()
    run_records: list[dict[str, object]] = []
    run_manifests: list[Path] = []
    observations_by_condition: dict[
        str, list[tuple[int, tuple[ExperimentObservation, ...]]]
    ] = defaultdict(list)

    for condition in sorted(
        configuration.conditions, key=lambda candidate: candidate.condition_id
    ):
        for seed in sorted(configuration.seeds):
            run_directory = runs_directory / condition.condition_id / f"seed-{seed}"
            request = ExperimentRunRequest(
                campaign_id=configuration.campaign_id,
                condition=condition,
                seed=seed,
                parameter_files=parameter_files,
            )
            observations = _validated_observations(runner(request, run_directory))
            _validate_required_metrics(observations)
            artifact_records = _validated_artifacts(run_directory)
            raw_manifest = {
                "campaign_id": configuration.campaign_id,
                "condition": condition.model_dump(mode="json"),
                "observations": [_observation_dict(item) for item in observations],
                "parameter_files": [
                    _parameter_file_dict(item) for item in parameter_files
                ],
                "raw_artifacts": artifact_records,
                "seed": seed,
            }
            manifest_path = run_directory / "run_manifest.json"
            _write_json(manifest_path, raw_manifest)
            run_manifests.append(manifest_path)
            relative_manifest = manifest_path.relative_to(output_directory).as_posix()
            run_records.append(
                {
                    "condition_id": condition.condition_id,
                    "run_manifest": relative_manifest,
                    "seed": seed,
                }
            )
            observations_by_condition[condition.condition_id].append(
                (seed, observations)
            )

    statistics = _replicate_statistics(
        observations_by_condition, configuration.confidence_level
    )
    summary_path = output_directory / "summary_statistics.json"
    _write_json(
        summary_path,
        {
            "campaign_id": configuration.campaign_id,
            "confidence_level": configuration.confidence_level,
            "statistics": statistics,
        },
    )
    sensitivity_path = output_directory / "sensitivity_ranking.json"
    _write_json(
        sensitivity_path,
        {
            "campaign_id": configuration.campaign_id,
            "method": "absolute range of condition replicate means per metric and time",
            "rankings": _sensitivity_rankings(configuration, statistics),
        },
    )
    campaign_manifest_path = output_directory / "campaign_manifest.json"
    _write_json(
        campaign_manifest_path,
        {
            "campaign_configuration": configuration.model_dump(mode="json"),
            "campaign_configuration_sha256": hashlib.sha256(
                configuration_bytes
            ).hexdigest(),
            "parameter_files": [_parameter_file_dict(item) for item in parameter_files],
            "runs": run_records,
            "sensitivity_ranking": sensitivity_path.name,
            "summary_statistics": summary_path.name,
        },
    )
    return ExperimentCampaignResult(
        output_directory=output_directory,
        campaign_manifest=campaign_manifest_path,
        summary_statistics=summary_path,
        sensitivity_ranking=sensitivity_path,
        run_manifests=tuple(run_manifests),
    )


def _parameter_file_records(
    configuration: ExperimentCampaign, base_directory: Path
) -> tuple[ParameterFileRecord, ...]:
    records: list[ParameterFileRecord] = []
    for label in sorted(configuration.biological_parameter_files):
        path = Path(label)
        resolved = path if path.is_absolute() else base_directory / path
        try:
            contents = resolved.read_bytes()
        except OSError as error:
            raise ExperimentValidationError(
                f"unable to read biological parameter file {label}: "
                f"{error.strerror or error}"
            ) from error
        records.append(
            ParameterFileRecord(
                label=label,
                path=resolved,
                sha256=hashlib.sha256(contents).hexdigest(),
            )
        )
    return tuple(records)


def _validated_observations(
    observations: Sequence[ExperimentObservation],
) -> tuple[ExperimentObservation, ...]:
    if isinstance(observations, (str, bytes)):
        raise ExperimentValidationError(
            "runner observations must be a sequence of ExperimentObservation"
        )
    validated = tuple(observations)
    if not validated or any(
        not isinstance(observation, ExperimentObservation)
        for observation in validated
    ):
        raise ExperimentValidationError(
            "runner must return at least one ExperimentObservation"
        )
    keys = [(item.metric, item.unit, item.time_s) for item in validated]
    if len(keys) != len(set(keys)):
        raise ExperimentValidationError(
            "runner observations must have unique metric, unit, and time_s keys"
        )
    return tuple(
        sorted(validated, key=lambda item: (item.metric, item.unit, item.time_s))
    )


def _validate_required_metrics(
    observations: tuple[ExperimentObservation, ...],
) -> None:
    metrics = {item.metric for item in observations}
    missing = sorted(set(REQUIRED_METRIC_UNITS) - metrics)
    if missing:
        raise ExperimentValidationError(
            "run is missing required experiment metrics: " + ", ".join(missing)
        )
    wrong_units = sorted(
        {
            item.metric
            for item in observations
            if item.metric in REQUIRED_METRIC_UNITS
            and item.unit != REQUIRED_METRIC_UNITS[item.metric]
        }
    )
    if wrong_units:
        raise ExperimentValidationError(
            "run has incorrect SI units for metrics: " + ", ".join(wrong_units)
        )
    producer_frequency_times = {
        item.time_s
        for item in observations
        if item.metric == "producer_cell_frequency"
    }
    if len(producer_frequency_times) < 2:
        raise ExperimentValidationError(
            "producer_cell_frequency must contain at least two time points"
        )


def _validated_artifacts(run_directory: Path) -> list[dict[str, object]]:
    if not run_directory.is_dir():
        raise ExperimentValidationError(
            f"runner did not create run directory {run_directory}"
        )
    manifest_path = run_directory / "run_manifest.json"
    if manifest_path.exists():
        raise ExperimentValidationError("runner must not create run_manifest.json")
    missing_files = sorted(
        name for name in REQUIRED_RUN_FILES if not (run_directory / name).is_file()
    )
    if missing_files:
        raise ExperimentValidationError(
            "run is missing required raw outputs: " + ", ".join(missing_files)
        )
    field_files = sorted((run_directory / "fields").glob("*.npz"))
    if not field_files:
        raise ExperimentValidationError("run must contain at least one field archive")
    for field_file in field_files:
        try:
            with np.load(field_file, allow_pickle=False) as archive:
                missing_arrays = sorted(REQUIRED_FIELD_ARRAYS - set(archive.files))
        except (OSError, ValueError) as error:
            raise ExperimentValidationError(
                f"invalid field archive {field_file}: {error}"
            ) from error
        if missing_arrays:
            raise ExperimentValidationError(
                f"field archive {field_file.name} is missing arrays: "
                + ", ".join(missing_arrays)
            )
    files = sorted(path for path in run_directory.rglob("*") if path.is_file())
    return [
        {
            "path": path.relative_to(run_directory).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
        for path in files
    ]


def _replicate_statistics(
    observations_by_condition: Mapping[
        str, Sequence[tuple[int, tuple[ExperimentObservation, ...]]]
    ],
    confidence_level: float,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for condition_id in sorted(observations_by_condition):
        replicates = observations_by_condition[condition_id]
        schemas = [
            tuple((item.metric, item.unit, item.time_s) for item in observations)
            for _, observations in replicates
        ]
        if any(schema != schemas[0] for schema in schemas[1:]):
            raise ExperimentValidationError(
                f"replicate observation schema differs for condition {condition_id}"
            )
        for observation_index, (metric, unit, time_s) in enumerate(schemas[0]):
            values = [
                observations[observation_index].value
                for _, observations in replicates
            ]
            count = len(values)
            mean = sum(values) / count
            variance = sum((value - mean) ** 2 for value in values) / (count - 1)
            critical = float(
                student_t.ppf((1.0 + confidence_level) / 2.0, count - 1)
            )
            half_width = critical * sqrt(variance / count)
            rows.append(
                {
                    "condition_id": condition_id,
                    "confidence_interval_high": mean + half_width,
                    "confidence_interval_low": mean - half_width,
                    "mean": mean,
                    "metric": metric,
                    "replicate_count": count,
                    "time_s": time_s,
                    "unit": unit,
                    "variance": variance,
                }
            )
    return rows


def _sensitivity_rankings(
    configuration: ExperimentCampaign,
    statistics: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Rank only observed sweep effects without fitting a sensitivity model."""
    family_by_condition = {
        condition.condition_id: condition.family
        for condition in configuration.conditions
    }
    grouped: dict[
        tuple[str, str, float], dict[str, list[tuple[str, float]]]
    ] = defaultdict(lambda: defaultdict(list))
    for row in statistics:
        condition_id = str(row["condition_id"])
        family = family_by_condition[condition_id]
        if family not in SWEEP_PARAMETERS:
            continue
        key = (
            str(row["metric"]),
            str(row["unit"]),
            _result_float(row["time_s"], "time_s"),
        )
        grouped[key][family].append(
            (condition_id, _result_float(row["mean"], "mean"))
        )

    rankings: list[dict[str, object]] = []
    for (metric, unit, time_s), family_values in sorted(grouped.items()):
        effects: list[dict[str, object]] = []
        for sweep_family, values in sorted(family_values.items()):
            if len(values) < 2:
                raise ExperimentValidationError(
                    f"sensitivity family {sweep_family} has fewer than two result "
                    "conditions"
                )
            ordered = sorted(values, key=lambda item: (item[1], item[0]))
            low_condition, low_mean = ordered[0]
            high_condition, high_mean = ordered[-1]
            effects.append(
                {
                    "absolute_mean_range": high_mean - low_mean,
                    "family": sweep_family,
                    "high_condition_id": high_condition,
                    "high_mean": high_mean,
                    "low_condition_id": low_condition,
                    "low_mean": low_mean,
                    "parameters": sorted(SWEEP_PARAMETERS[sweep_family]),
                }
            )
        effects.sort(
            key=lambda item: (
                -_result_float(item["absolute_mean_range"], "absolute_mean_range"),
                str(item["family"]),
            )
        )
        for rank, effect in enumerate(effects, start=1):
            effect["rank"] = rank
        rankings.append(
            {
                "metric": metric,
                "ranking": effects,
                "time_s": time_s,
                "unit": unit,
            }
        )
    return rankings


def _result_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExperimentValidationError(f"result {name} must be numeric")
    converted = float(value)
    if not isfinite(converted):
        raise ExperimentValidationError(f"result {name} must be finite")
    return converted


def _observation_dict(observation: ExperimentObservation) -> dict[str, object]:
    return {
        "metric": observation.metric,
        "time_s": observation.time_s,
        "unit": observation.unit,
        "value": observation.value,
    }


def _parameter_file_dict(record: ParameterFileRecord) -> dict[str, object]:
    return {"label": record.label, "sha256": record.sha256}


def _write_json(path: Path, contents: object) -> None:
    serialized = json.dumps(contents, indent=2, sort_keys=True, allow_nan=False)
    path.write_text(f"{serialized}\n", encoding="utf-8")
