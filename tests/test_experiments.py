"""P2-WP06 experiment-matrix, replay, provenance, and statistics tests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import numpy as np
import pytest
from pydantic import ValidationError

from biomesh.experiments import (
    REQUIRED_FIELD_ARRAYS,
    REQUIRED_METRIC_UNITS,
    REQUIRED_RUN_FILES,
    ExperimentCampaign,
    ExperimentCondition,
    ExperimentObservation,
    ExperimentRunRequest,
    ExperimentValidationError,
    SweepParameter,
    load_experiment_campaign,
    run_experiment_campaign,
)


def _override(
    name: str,
    unit: str,
    level_id: str,
    value: float = 1.0,
) -> SweepParameter:
    return SweepParameter(
        name=name,
        value=value,
        unit=unit,
        source="synthetic P2-WP06 software verification",
        uncertainty="synthetic exact input",
        notes="Configurable test value; not a biological calibration.",
        calibration_status="DERIVED",
        level_id=level_id,
    )


def _condition(
    condition_id: str,
    family: str,
    *,
    producer_fraction: float = 0.5,
    pattern: str = "intermixed",
    eps_control: str = "quorum_controlled",
    overrides: Sequence[SweepParameter] = (),
) -> ExperimentCondition:
    return ExperimentCondition.model_validate(
        {
            "condition_id": condition_id,
            "family": family,
            "producer_fraction": producer_fraction,
            "inoculation_pattern": pattern,
            "eps_control": eps_control,
            "parameter_overrides": [
                override.model_dump(mode="python") for override in overrides
            ],
            "notes": "Synthetic harness condition; not a biological result.",
        }
    )


def _conditions() -> list[ExperimentCondition]:
    quorum_name = "quorum_activation_half_saturation_constant"
    carbon_name = "carbon_bulk_concentration"
    oxygen_name = "oxygen_bulk_concentration"
    eps_name = "maximum_eps_allocation_fraction"
    shear_name = "surface_parallel_shear_stress"
    return [
        _condition("producer", "producer_monoculture", producer_fraction=1.0),
        _condition("nonproducer", "nonproducer_monoculture", producer_fraction=0.0),
        _condition("competition", "competition_50_50"),
        _condition("pattern-intermixed", "inoculation_pattern", pattern="intermixed"),
        _condition("pattern-segregated", "inoculation_pattern", pattern="segregated"),
        _condition("eps-constitutive", "eps_control", eps_control="constitutive"),
        _condition("eps-quorum", "eps_control", eps_control="quorum_controlled"),
        _condition(
            "quorum-low",
            "quorum_threshold_sweep",
            overrides=(_override(quorum_name, "mol m^-3", "low", 1.0),),
        ),
        _condition(
            "quorum-high",
            "quorum_threshold_sweep",
            overrides=(_override(quorum_name, "mol m^-3", "high", 2.0),),
        ),
        _condition(
            "resources-low",
            "nutrient_oxygen_sweep",
            overrides=(
                _override(carbon_name, "mol m^-3", "low", 1.0),
                _override(oxygen_name, "mol m^-3", "low", 1.0),
            ),
        ),
        _condition(
            "resources-high",
            "nutrient_oxygen_sweep",
            overrides=(
                _override(carbon_name, "mol m^-3", "high", 2.0),
                _override(oxygen_name, "mol m^-3", "high", 2.0),
            ),
        ),
        _condition(
            "eps-cost-low",
            "eps_cost_sweep",
            overrides=(_override(eps_name, "1", "low", 0.1),),
        ),
        _condition(
            "eps-cost-high",
            "eps_cost_sweep",
            overrides=(_override(eps_name, "1", "high", 0.2),),
        ),
        _condition(
            "shear-low",
            "shear_sweep",
            overrides=(_override(shear_name, "Pa", "low", 1.0),),
        ),
        _condition(
            "shear-high",
            "shear_sweep",
            overrides=(_override(shear_name, "Pa", "high", 2.0),),
        ),
    ]


def _campaign(parameter_file: str = "parameters.toml") -> ExperimentCampaign:
    return ExperimentCampaign(
        schema_version=1,
        campaign_id="synthetic-p2-wp06",
        purpose="Deterministic P2-WP06 harness verification only",
        calibration_status="CALIBRATION_REQUIRED",
        confidence_level=0.95,
        seeds=[1, 3],
        biological_parameter_files=[parameter_file],
        conditions=_conditions(),
    )


def _write_deterministic_field_archive(path: Path) -> None:
    path.parent.mkdir(parents=True)
    with ZipFile(path, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(REQUIRED_FIELD_ARRAYS):
            buffer = BytesIO()
            np.lib.format.write_array(
                buffer, np.zeros((2, 2), dtype=np.float64), allow_pickle=False
            )
            entry = ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o600 << 16
            archive.writestr(entry, buffer.getvalue(), compress_type=ZIP_DEFLATED)


def _observations(seed: int) -> tuple[ExperimentObservation, ...]:
    return tuple(
        ExperimentObservation(
            metric=metric,
            unit=unit,
            time_s=time_s,
            value=float(index + seed + time_s),
        )
        for index, (metric, unit) in enumerate(sorted(REQUIRED_METRIC_UNITS.items()))
        for time_s in (0.0, 1.0)
    )


def _runner_with_hashes(
    hashes: dict[tuple[str, int], dict[str, str]],
):
    def runner(
        request: ExperimentRunRequest, run_directory: Path
    ) -> tuple[ExperimentObservation, ...]:
        run_directory.mkdir(parents=True)
        for name in sorted(REQUIRED_RUN_FILES):
            (run_directory / name).write_bytes(
                f"{request.condition.condition_id}:{request.seed}:{name}\n".encode()
            )
        _write_deterministic_field_archive(run_directory / "fields" / "000000.npz")
        hashes[(request.condition.condition_id, request.seed)] = {
            path.relative_to(run_directory).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(run_directory.rglob("*"))
            if path.is_file()
        }
        return _observations(request.seed)

    return runner


def _campaign_inputs(tmp_path: Path) -> tuple[Path, Path]:
    parameter_file = tmp_path / "parameters.toml"
    parameter_file.write_text("schema_version = 1\n", encoding="utf-8")
    configuration_file = tmp_path / "campaign.toml"
    configuration_file.write_text(
        "schema_version = 1\n# synthetic provenance fixture\n", encoding="utf-8"
    )
    return parameter_file, configuration_file


def test_repository_campaign_template_covers_required_matrix() -> None:
    campaign = load_experiment_campaign(Path("experiments/p2_wp06_campaign.toml"))

    assert len(campaign.seeds) >= 2
    assert {condition.family for condition in campaign.conditions} == {
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
    assert all(
        parameter.value == "CALIBRATION_REQUIRED"
        for condition in campaign.conditions
        for parameter in condition.parameter_overrides
    )


def test_campaign_replays_byte_identically_and_preserves_raw_outputs(
    tmp_path: Path,
) -> None:
    _, configuration_file = _campaign_inputs(tmp_path)
    campaign = _campaign()
    first_hashes: dict[tuple[str, int], dict[str, str]] = {}
    second_hashes: dict[tuple[str, int], dict[str, str]] = {}
    first = run_experiment_campaign(
        configuration=campaign,
        configuration_file=configuration_file,
        output_directory=tmp_path / "first",
        runner=_runner_with_hashes(first_hashes),
    )
    second = run_experiment_campaign(
        configuration=campaign,
        configuration_file=configuration_file,
        output_directory=tmp_path / "second",
        runner=_runner_with_hashes(second_hashes),
    )

    assert len(first.run_manifests) == len(campaign.conditions) * len(campaign.seeds)
    assert first_hashes == second_hashes
    for (condition_id, seed), expected_hashes in first_hashes.items():
        run_directory = first.output_directory / "runs" / condition_id / f"seed-{seed}"
        actual_hashes = {
            relative: hashlib.sha256(
                (run_directory / relative).read_bytes()
            ).hexdigest()
            for relative in expected_hashes
        }
        assert actual_hashes == expected_hashes
    first_files = sorted(
        path.relative_to(first.output_directory)
        for path in first.output_directory.rglob("*")
        if path.is_file()
    )
    assert first_files == sorted(
        path.relative_to(second.output_directory)
        for path in second.output_directory.rglob("*")
        if path.is_file()
    )
    assert all(
        (first.output_directory / path).read_bytes()
        == (second.output_directory / path).read_bytes()
        for path in first_files
    )


def test_campaign_records_complete_manifests_and_replicate_statistics(
    tmp_path: Path,
) -> None:
    _, configuration_file = _campaign_inputs(tmp_path)
    hashes: dict[tuple[str, int], dict[str, str]] = {}
    result = run_experiment_campaign(
        configuration=_campaign(),
        configuration_file=configuration_file,
        output_directory=tmp_path / "campaign-output",
        runner=_runner_with_hashes(hashes),
    )

    manifest = json.loads(result.campaign_manifest.read_text(encoding="utf-8"))
    assert len(manifest["runs"]) == 30
    assert {run["seed"] for run in manifest["runs"]} == {1, 3}
    raw_manifest = json.loads(result.run_manifests[0].read_text(encoding="utf-8"))
    assert raw_manifest["condition"]["condition_id"]
    assert raw_manifest["parameter_files"][0]["sha256"]
    assert len(raw_manifest["raw_artifacts"]) == len(REQUIRED_RUN_FILES) + 1
    statistics = json.loads(result.summary_statistics.read_text(encoding="utf-8"))
    row = next(
        item
        for item in statistics["statistics"]
        if item["condition_id"] == "competition"
        and item["metric"] == "active_biomass_kg"
        and item["time_s"] == 0.0
    )
    assert row["replicate_count"] == 2
    assert row["mean"] == pytest.approx(2.0)
    assert row["variance"] == pytest.approx(2.0)
    assert row["confidence_interval_low"] < row["mean"]
    assert row["confidence_interval_high"] > row["mean"]


def test_campaign_validation_fails_explicitly_for_incomplete_inputs_and_outputs(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError, match="missing required experiment families"):
        ExperimentCampaign(
            schema_version=1,
            campaign_id="incomplete",
            purpose="invalid synthetic campaign",
            calibration_status="CALIBRATION_REQUIRED",
            confidence_level=0.95,
            seeds=[1, 2],
            biological_parameter_files=["parameters.toml"],
            conditions=[
                _condition(
                    "producer", "producer_monoculture", producer_fraction=1.0
                )
            ],
        )
    _, configuration_file = _campaign_inputs(tmp_path)

    def incomplete_runner(
        request: ExperimentRunRequest, run_directory: Path
    ) -> tuple[ExperimentObservation, ...]:
        run_directory.mkdir(parents=True)
        return _observations(request.seed)[:-1]

    with pytest.raises(ExperimentValidationError, match="missing required"):
        run_experiment_campaign(
            configuration=_campaign(),
            configuration_file=configuration_file,
            output_directory=tmp_path / "incomplete-output",
            runner=incomplete_runner,
        )
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(ExperimentValidationError, match="must not already exist"):
        run_experiment_campaign(
            configuration=_campaign(),
            configuration_file=configuration_file,
            output_directory=existing,
            runner=incomplete_runner,
        )
