"""Executable, deterministic P2 software-validation campaigns.

This adapter is deliberately separate from ``experiments/p2_wp06_campaign.toml``:
that file remains the unresolved biological campaign definition.  The values
below are manufactured SI-labelled software fixtures and are never presented
as biological calibration or scientific results.

Update order for each accepted interval is fixed and recorded in run metadata:
1. quorum production/transport and local sensing; 2. physiology-derived
activity; 3. shared-resource competition and EPS allocation; 4. waste
transport; 5. shear selection; 6. physiology state/ledger update; 7. mechanics
for retained cells; 8. accounting and serialization.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
import tempfile
from dataclasses import dataclass, replace
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from biomesh import __version__
from biomesh.cells import Cell
from biomesh.competition import (
    CompetitionSnapshot,
    CompetitionStrains,
    advance_competition,
)
from biomesh.eps import EPSField, EPSParameters
from biomesh.experiments import (
    REQUIRED_FIELD_ARRAYS,
    REQUIRED_METRIC_UNITS,
    REQUIRED_RUN_FILES,
    SWEEP_PARAMETERS,
    ExperimentCampaign,
    ExperimentCondition,
    ExperimentObservation,
    ExperimentRunRequest,
    ExperimentValidationError,
    ParameterFileRecord,
    SweepParameter,
    load_experiment_campaign,
    run_experiment_campaign,
)
from biomesh.mass_balance import solute_amount_mol, top_boundary_input_rate_mol_s
from biomesh.mechanics import MechanicsParameters, attach_initial_cells, relax_cells
from biomesh.metabolism import MetabolismParameters
from biomesh.outputs import (
    MassBalanceEntry,
    OutputPaths,
    RunMetadata,
    SimulationOutputWriter,
)
from biomesh.physiology import (
    CellPhysiologyState,
    DeadBiomassRule,
    PhysiologyParameters,
    PhysiologySnapshot,
    advance_physiological_states,
    initialize_physiological_states,
    metabolic_activity_fractions,
)
from biomesh.provenance import exact_runtime_source_commit
from biomesh.quorum import (
    CellQuorumState,
    QuorumObservation,
    QuorumSignalParameters,
    advance_quorum_signal,
    initialize_quorum_states,
)
from biomesh.shear import (
    CellShearState,
    ShearParameters,
    ShearSnapshot,
    advance_shear_detachment,
)
from biomesh.solutes import SoluteField, SoluteFields
from biomesh.waste import WasteParameters, advance_waste

FIXTURE_SCHEMA_VERSION = 1
FIXTURE_SEEDS = (101, 202, 303)
FIXTURE_STEP_COUNT = 3
FIXTURE_TIME_STEP_S = 0.1
FixtureKind = Literal["experiment", "sweep"]
PUBLISHED_FIXTURES: dict[str, tuple[FixtureKind, tuple[str, ...]]] = {
    "producer.yaml": ("experiment", ("producer",)),
    "nonproducer.yaml": ("experiment", ("nonproducer",)),
    "competition_50_50.yaml": ("experiment", ("competition-50-50",)),
    "inoculation_intermixed.yaml": ("experiment", ("inoculation-intermixed",)),
    "inoculation_segregated.yaml": ("experiment", ("inoculation-segregated",)),
    "eps_constitutive.yaml": ("experiment", ("eps-constitutive",)),
    "eps_quorum_controlled.yaml": ("experiment", ("eps-quorum-controlled",)),
    "qs_threshold_sweep.yaml": ("sweep", ("qs-low", "qs-high")),
    "nutrient_oxygen_sweep.yaml": (
        "sweep",
        ("resources-low", "resources-high"),
    ),
    "eps_cost_sweep.yaml": ("sweep", ("eps-cost-low", "eps-cost-high")),
    "shear_sweep.yaml": ("sweep", ("shear-low", "shear-high")),
}
BIOLOGICAL_PARAMETER_FILES = (
    "../parameters/p1_core_model.toml",
    "../parameters/p2_quorum_signal.toml",
    "../parameters/p2_eps_model.toml",
    "../parameters/p2_physiological_states.toml",
    "../parameters/p2_waste_shear.toml",
)
UPDATE_ORDER = [
    "quorum_transport_and_local_sensing",
    "physiology_activity",
    "competition_and_eps_allocation",
    "waste_transport",
    "shear_detachment_selection",
    "physiology_state_and_ledger",
    "retained_cell_mechanics",
    "accounting_and_output",
]


@dataclass(frozen=True, slots=True)
class FixtureCommand:
    """Parsed JSON-compatible YAML command fixture."""

    fixture_kind: FixtureKind
    campaign_id: str
    condition_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResolvedFixtureRun:
    """One exact P2 fixture condition and its immutable input identity."""

    fixture_file: Path
    fixture_sha256: str
    request: ExperimentRunRequest
    calibration_status: str


@dataclass(slots=True)
class _FixtureRunState:
    """Private mutable state advanced only at accepted P2 solver boundaries."""

    request: ExperimentRunRequest
    fields: SoluteFields
    signal: SoluteField
    waste: SoluteField
    eps: EPSField
    cells: tuple[Cell, ...]
    depth_m: float
    mechanics: MechanicsParameters
    attached_cell_ids: frozenset[str]
    quorum_parameters: QuorumSignalParameters
    eps_parameters: EPSParameters
    metabolism_parameters: MetabolismParameters
    physiology_parameters: PhysiologyParameters
    shear_parameters: ShearParameters
    strains: CompetitionStrains
    writer: SimulationOutputWriter
    quorum_states: tuple[CellQuorumState, ...]
    physiology_states: tuple[CellPhysiologyState, ...]
    shear_states: tuple[CellShearState, ...] | None = None
    step_index: int = 0
    observations: tuple[ExperimentObservation, ...] = ()
    mass_balance_entries: tuple[MassBalanceEntry, ...] = ()
    competition_snapshot: CompetitionSnapshot | None = None
    physiology_snapshot: PhysiologySnapshot | None = None
    shear_snapshot: ShearSnapshot | None = None
    finalized_paths: OutputPaths | None = None


def load_fixture_command(path: Path) -> FixtureCommand:
    """Load one strict JSON-compatible YAML fixture without a YAML dependency."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExperimentValidationError(
            f"invalid software-validation fixture {path}: {error}"
        ) from error
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "fixture_kind",
        "campaign_id",
        "condition_ids",
    }:
        raise ExperimentValidationError(
            "fixture must contain only schema_version, fixture_kind, campaign_id, "
            "and condition_ids"
        )
    if payload["schema_version"] != FIXTURE_SCHEMA_VERSION:
        raise ExperimentValidationError("unsupported fixture schema_version")
    fixture_kind = payload["fixture_kind"]
    if fixture_kind not in {"experiment", "sweep"}:
        raise ExperimentValidationError("fixture_kind must be experiment or sweep")
    campaign_id = payload["campaign_id"]
    condition_ids = payload["condition_ids"]
    if not isinstance(campaign_id, str) or not campaign_id.strip():
        raise ExperimentValidationError("fixture campaign_id must be nonblank")
    if (
        not isinstance(condition_ids, list)
        or not condition_ids
        or any(
            not isinstance(value, str) or not value.strip() for value in condition_ids
        )
        or len(condition_ids) != len(set(condition_ids))
    ):
        raise ExperimentValidationError(
            "fixture condition_ids must be unique nonblank strings"
        )
    return FixtureCommand(fixture_kind, campaign_id, tuple(condition_ids))


def resolve_fixture_run(
    *, fixture_file: Path, condition_id: str, seed: int
) -> ResolvedFixtureRun:
    """Resolve one CLI fixture condition/seed without changing its science."""
    command = load_fixture_command(fixture_file)
    if condition_id not in command.condition_ids:
        raise ExperimentValidationError(
            f"fixture does not select condition {condition_id!r}"
        )
    if not isinstance(seed, int) or isinstance(seed, bool) or seed not in FIXTURE_SEEDS:
        raise ExperimentValidationError(
            "fixture seed must be one of " + ", ".join(map(str, FIXTURE_SEEDS))
        )
    return _resolve_fixture_run(
        fixture_file=fixture_file,
        command=command,
        condition_id=condition_id,
        seed=seed,
    )


def resolve_application_run(
    *, fixture_file: Path, condition_id: str, seed: int
) -> ResolvedFixtureRun:
    """Resolve one deterministic P3 application run over an existing fixture.

    The published P2 campaign remains restricted to ``FIXTURE_SEEDS``.  The P3
    application boundary accepts any nonnegative deterministic seed so its
    documented frontend-equivalence check can use an independent audit seed.
    """
    command = load_fixture_command(fixture_file)
    if condition_id not in command.condition_ids:
        raise ExperimentValidationError(
            f"fixture does not select condition {condition_id!r}"
        )
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ExperimentValidationError("application seed must be nonnegative")
    return _resolve_fixture_run(
        fixture_file=fixture_file,
        command=command,
        condition_id=condition_id,
        seed=seed,
    )


def _resolve_fixture_run(
    *,
    fixture_file: Path,
    command: FixtureCommand,
    condition_id: str,
    seed: int,
) -> ResolvedFixtureRun:
    """Resolve common immutable fixture inputs after caller seed validation."""
    campaign = _software_campaign(fixture_file)
    condition_by_id = {
        condition.condition_id: condition for condition in campaign.conditions
    }
    try:
        condition = condition_by_id[condition_id]
    except KeyError as error:
        raise ExperimentValidationError(
            f"fixture selects unknown condition {condition_id!r}"
        ) from error
    try:
        fixture_contents = fixture_file.read_bytes()
    except OSError as error:
        raise ExperimentValidationError(
            f"unable to read fixture provenance file {fixture_file}: "
            f"{error.strerror or error}"
        ) from error
    parameter_files = tuple(
        _parameter_file_record(label, fixture_file.parent)
        for label in sorted(campaign.biological_parameter_files)
    )
    return ResolvedFixtureRun(
        fixture_file=fixture_file.resolve(),
        fixture_sha256=hashlib.sha256(fixture_contents).hexdigest(),
        request=ExperimentRunRequest(
            campaign_id=command.campaign_id,
            condition=condition,
            seed=seed,
            parameter_files=parameter_files,
        ),
        calibration_status=campaign.calibration_status,
    )


def _parameter_file_record(label: str, base_directory: Path) -> ParameterFileRecord:
    path = Path(label)
    resolved = path if path.is_absolute() else base_directory / path
    try:
        contents = resolved.read_bytes()
    except OSError as error:
        raise ExperimentValidationError(
            f"unable to read biological parameter file {label}: "
            f"{error.strerror or error}"
        ) from error
    return ParameterFileRecord(
        label=label,
        path=resolved.resolve(),
        sha256=hashlib.sha256(contents).hexdigest(),
    )


def run_fixture_command(
    *,
    fixture_file: Path,
    output_directory: Path,
    expected_kind: FixtureKind,
) -> Path:
    """Run selected P2 conditions with three deterministic seeds and real artifacts."""
    command = load_fixture_command(fixture_file)
    if command.fixture_kind != expected_kind:
        raise ExperimentValidationError(
            f"{expected_kind} command requires fixture_kind={expected_kind}"
        )
    full = _software_campaign(fixture_file)
    by_id = {condition.condition_id: condition for condition in full.conditions}
    missing = sorted(set(command.condition_ids) - set(by_id))
    if missing:
        raise ExperimentValidationError(
            "fixture selects unknown conditions: " + ", ".join(missing)
        )
    # The matrix is validated in full above.  This projection is only the CLI
    # execution subset requested by one fixture, never a biological campaign.
    selected = full.model_copy(
        update={
            "campaign_id": command.campaign_id,
            "conditions": [by_id[key] for key in command.condition_ids],
        }
    )
    result = run_experiment_campaign(
        configuration=selected,
        configuration_file=fixture_file,
        output_directory=output_directory,
        runner=_run_fixture_replicate,
    )
    _validate_campaign_artifacts(result.output_directory)
    return result.output_directory


def validate_all(repository_root: Path) -> dict[str, object]:
    """Validate unresolved biological records and all executable fixture files."""
    load_experiment_campaign(repository_root / "experiments/p2_wp06_campaign.toml")
    fixture_directory = repository_root / "experiments"
    actual_names = {
        path.name
        for path in fixture_directory.glob("*.yaml")
        if path.name != "platform_reference.yaml"
    }
    expected_names = set(PUBLISHED_FIXTURES)
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        unexpected = sorted(actual_names - expected_names)
        raise ExperimentValidationError(
            "published fixture set mismatch; "
            f"missing={missing}, unexpected={unexpected}"
        )
    commands: list[FixtureCommand] = []
    for name, (fixture_kind, condition_ids) in PUBLISHED_FIXTURES.items():
        command = load_fixture_command(fixture_directory / name)
        if (
            command.fixture_kind != fixture_kind
            or command.condition_ids != condition_ids
        ):
            raise ExperimentValidationError(
                f"published fixture {name} does not match its required command contract"
            )
        commands.append(command)
    full_campaign = _software_campaign(fixture_directory / "producer.yaml")
    published_conditions = [
        condition_id for command in commands for condition_id in command.condition_ids
    ]
    expected_conditions = {
        condition.condition_id for condition in full_campaign.conditions
    }
    if (
        len(published_conditions) != len(set(published_conditions))
        or set(published_conditions) != expected_conditions
    ):
        raise ExperimentValidationError(
            "published fixtures must cover every executable condition exactly once"
        )
    if tuple(full_campaign.seeds) != FIXTURE_SEEDS:
        raise ExperimentValidationError("software fixtures require three fixed seeds")
    return {
        "fixture_count": len(commands),
        "condition_count": len(published_conditions),
        "passed": True,
        "seeds": list(FIXTURE_SEEDS),
        "scientific_calibration": "not claimed; manufactured software fixtures only",
    }


def report_campaign(output_directory: Path) -> Path:
    """Reject malformed campaign artifacts and render a deterministic PNG report."""
    _validate_campaign_artifacts(output_directory)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    summary = json.loads((output_directory / "summary_statistics.json").read_text())
    rows = summary["statistics"]
    selected = [row for row in rows if row["metric"] == "total_dry_biomass_kg"]
    if not selected:
        raise ExperimentValidationError("summary has no total_dry_biomass_kg rows")
    figure, axis = plt.subplots(figsize=(6, 4))
    for condition in sorted({str(row["condition_id"]) for row in selected}):
        series = sorted(
            (row for row in selected if row["condition_id"] == condition),
            key=lambda row: float(row["time_s"]),
        )
        axis.plot(
            [row["time_s"] for row in series],
            [row["mean"] for row in series],
            label=condition,
        )
    axis.set(
        xlabel="time (s)",
        ylabel="mean dry biomass (kg)",
        title="P2 manufactured software-validation fixture",
    )
    axis.legend(fontsize="x-small")
    figure.tight_layout()
    report = output_directory / "report.png"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{report.name}.", suffix=".png", dir=output_directory
    )
    temporary_report = Path(temporary_name)
    os.close(descriptor)
    try:
        figure.savefig(temporary_report, dpi=120, format="png")
        os.replace(temporary_report, report)
    except Exception:
        temporary_report.unlink(missing_ok=True)
        raise
    plt.close(figure)
    return report


def _software_campaign(fixture_file: Path) -> ExperimentCampaign:
    """Return a full strict matrix with manufactured, non-biological controls."""

    def condition(
        condition_id: str,
        family: str,
        fraction: float,
        pattern: str = "intermixed",
        eps: str = "quorum_controlled",
        overrides: list[SweepParameter] | None = None,
    ) -> ExperimentCondition:
        return ExperimentCondition.model_validate(
            {
                "condition_id": condition_id,
                "family": family,
                "producer_fraction": fraction,
                "inoculation_pattern": pattern,
                "eps_control": eps,
                "parameter_overrides": [item.model_dump() for item in overrides or []],
                "notes": (
                    "Manufactured SI software-validation fixture; "
                    "not biological calibration."
                ),
            }
        )

    def override(name: str, unit: str, level: str, value: float) -> SweepParameter:
        return SweepParameter(
            name=name,
            value=value,
            unit=unit,
            level_id=level,
            source="manufactured software-validation fixture",
            uncertainty="not a biological uncertainty",
            notes="SI-labelled executable fixture; not calibration.",
            calibration_status="DERIVED",
        )

    conditions = [
        condition("producer", "producer_monoculture", 1.0),
        condition("nonproducer", "nonproducer_monoculture", 0.0),
        condition("competition-50-50", "competition_50_50", 0.5),
        condition("inoculation-intermixed", "inoculation_pattern", 0.5),
        condition("inoculation-segregated", "inoculation_pattern", 0.5, "segregated"),
        condition("eps-constitutive", "eps_control", 0.5, eps="constitutive"),
        condition("eps-quorum-controlled", "eps_control", 0.5),
        condition(
            "qs-low",
            "quorum_threshold_sweep",
            0.5,
            overrides=[
                override(
                    "quorum_activation_half_saturation_constant",
                    "mol m^-3",
                    "low",
                    5e-7,
                )
            ],
        ),
        condition(
            "qs-high",
            "quorum_threshold_sweep",
            0.5,
            overrides=[
                override(
                    "quorum_activation_half_saturation_constant",
                    "mol m^-3",
                    "high",
                    5e-6,
                )
            ],
        ),
        condition(
            "resources-low",
            "nutrient_oxygen_sweep",
            0.5,
            overrides=[
                override("carbon_bulk_concentration", "mol m^-3", "low", 1e3),
                override("oxygen_bulk_concentration", "mol m^-3", "low", 1e3),
            ],
        ),
        condition(
            "resources-high",
            "nutrient_oxygen_sweep",
            0.5,
            overrides=[
                override("carbon_bulk_concentration", "mol m^-3", "high", 2e3),
                override("oxygen_bulk_concentration", "mol m^-3", "high", 2e3),
            ],
        ),
        condition(
            "eps-cost-low",
            "eps_cost_sweep",
            0.5,
            overrides=[override("maximum_eps_allocation_fraction", "1", "low", 0.1)],
        ),
        condition(
            "eps-cost-high",
            "eps_cost_sweep",
            0.5,
            overrides=[override("maximum_eps_allocation_fraction", "1", "high", 0.4)],
        ),
        condition(
            "shear-low",
            "shear_sweep",
            0.5,
            overrides=[override("surface_parallel_shear_stress", "Pa", "low", 0.0)],
        ),
        condition(
            "shear-high",
            "shear_sweep",
            0.5,
            overrides=[override("surface_parallel_shear_stress", "Pa", "high", 2.0)],
        ),
    ]
    return ExperimentCampaign(
        schema_version=1,
        campaign_id="p2-software-validation",
        purpose=(
            "Manufactured deterministic software validation; no biological conclusion."
        ),
        calibration_status="CALIBRATION_REQUIRED",
        confidence_level=0.95,
        seeds=list(FIXTURE_SEEDS),
        biological_parameter_files=list(BIOLOGICAL_PARAMETER_FILES),
        conditions=conditions,
    )


def _run_fixture_replicate(
    request: ExperimentRunRequest, directory: Path
) -> tuple[ExperimentObservation, ...]:
    """Compose all approved P2 interfaces for one fixture condition/seed."""
    state = _initialize_fixture_replicate(request, directory)
    while state.step_index < FIXTURE_STEP_COUNT:
        _advance_fixture_replicate(state)
    _finalize_fixture_replicate(state)
    return state.observations


def _initialize_fixture_replicate(
    request: ExperimentRunRequest, directory: Path
) -> _FixtureRunState:
    """Create private P2 state without advancing an accepted interval."""
    values = {
        item.name: float(item.value) for item in request.condition.parameter_overrides
    }
    depth = 1e-6
    carbon_bulk = values.get("carbon_bulk_concentration", 1e3)
    oxygen_bulk = values.get("oxygen_bulk_concentration", 1e3)
    shape, width, height = (4, 4), 4e-6, 4e-6
    fields = SoluteFields(
        SoluteField(
            "carbon",
            shape,
            width,
            height,
            1e-12,
            carbon_bulk,
            np.full(shape, carbon_bulk),
        ),
        SoluteField(
            "oxygen",
            shape,
            width,
            height,
            1e-12,
            oxygen_bulk,
            np.full(shape, oxygen_bulk),
        ),
    )
    signal = SoluteField(
        "quorum_signal", shape, width, height, 1e-12, 0.0, np.zeros(shape)
    )
    waste = SoluteField("waste", shape, width, height, 1e-12, 0.0, np.zeros(shape))
    eps = EPSField(
        shape=shape,
        width_m=width,
        height_m=height,
        depth_m=depth,
        density_kg_m3=np.zeros(shape),
    )
    cells = _initial_cells(request, width)
    mechanics = MechanicsParameters(width, 1e-6, 20, 1.0, "bottom")
    attached = attach_initial_cells(cells, mechanics)
    cells = attached.cells
    quorum_parameters = QuorumSignalParameters(
        0.0,
        1e-23,
        0.0,
        values.get("quorum_activation_half_saturation_constant", 1e-6),
        2.0,
    )
    eps_parameters = EPSParameters(
        values.get("maximum_eps_allocation_fraction", 0.25), 1e18, 1e18
    )
    metabolism = MetabolismParameters(1e-3, 1.0, 1.0, 0.0, 1e-6, 1e-6)
    physiology_parameters = PhysiologyParameters(
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        10.0,
        10.0,
        10.0,
        10.0,
        0.5,
        0.1,
        DeadBiomassRule.PERSIST,
        None,
    )
    shear_parameters = ShearParameters(
        values.get("surface_parallel_shear_stress", 0.0), 0.1, 1.0
    )
    strains = CompetitionStrains(frozenset({"producer"}), frozenset({"nonproducer"}))
    metadata = RunMetadata(
        seed=request.seed,
        parameters={
            "software_fixture": "manufactured SI software validation",
            "condition": request.condition.model_dump(mode="json"),
            "update_order": UPDATE_ORDER,
        },
        package_version=__version__,
        commit_hash=_commit_hash(),
        dependency_versions={
            "numpy": version("numpy"),
            "pyarrow": version("pyarrow"),
            "scipy": version("scipy"),
        },
        parameter_file=request.parameter_files[0].label,
        parameter_file_sha256=request.parameter_files[0].sha256,
        platform=platform.platform(),
        python_version=sys.version.split()[0],
    )
    writer = SimulationOutputWriter(directory, metadata)
    quorum_states = initialize_quorum_states(
        cells=cells, signal_field=signal, parameters=quorum_parameters, time_s=0.0
    )
    physiology_states = initialize_physiological_states(
        cells=cells, solute_fields=fields, time_s=0.0
    )
    return _FixtureRunState(
        request=request,
        fields=fields,
        signal=signal,
        waste=waste,
        eps=eps,
        cells=cells,
        depth_m=depth,
        mechanics=mechanics,
        attached_cell_ids=attached.attached_cell_ids,
        quorum_parameters=quorum_parameters,
        eps_parameters=eps_parameters,
        metabolism_parameters=metabolism,
        physiology_parameters=physiology_parameters,
        shear_parameters=shear_parameters,
        strains=strains,
        writer=writer,
        quorum_states=quorum_states,
        physiology_states=physiology_states,
    )


def _advance_fixture_replicate(state: _FixtureRunState) -> None:
    """Advance exactly one accepted interval in the recorded P2 update order."""
    if state.finalized_paths is not None:
        raise ExperimentValidationError("fixture run has already been finalized")
    if state.step_index >= FIXTURE_STEP_COUNT:
        raise ExperimentValidationError("fixture run has no remaining solver step")
    dt = FIXTURE_TIME_STEP_S
    start = state.step_index * dt
    quorum = advance_quorum_signal(
        cells=state.cells,
        signal_field=state.signal,
        parameters=state.quorum_parameters,
        time_step_s=dt,
        depth_m=state.depth_m,
        start_time_s=start,
        cell_states=state.quorum_states,
    )
    eps_quorum_states = (
        _constitutive_states(state.quorum_states)
        if state.request.condition.eps_control == "constitutive"
        else state.quorum_states
    )
    activities = metabolic_activity_fractions(
        cells=state.cells,
        cell_states=state.physiology_states,
        parameters=state.physiology_parameters,
    )
    carbon_before_mol = solute_amount_mol(state.fields.carbon, state.depth_m)
    oxygen_before_mol = solute_amount_mol(state.fields.oxygen, state.depth_m)
    carbon_boundary_mol = (
        top_boundary_input_rate_mol_s(state.fields.carbon, state.depth_m) * dt
    )
    oxygen_boundary_mol = (
        top_boundary_input_rate_mol_s(state.fields.oxygen, state.depth_m) * dt
    )
    competition = advance_competition(
        cells=state.cells,
        strain_roles=state.strains,
        solute_fields=state.fields,
        eps_field=state.eps,
        quorum_states=eps_quorum_states,
        eps_parameters=state.eps_parameters,
        metabolism_parameters=state.metabolism_parameters,
        time_step_s=dt,
        start_time_s=start,
        dry_biomass_per_unit_length_kg_m=1e-18,
        metabolic_activity_fractions=activities,
    )
    waste_result = advance_waste(
        cells=competition.cells,
        waste_field=state.waste,
        parameters=WasteParameters(1e-23, 0.0),
        time_step_s=dt,
        depth_m=state.depth_m,
        metabolic_activity_fractions=activities,
    )
    shear = advance_shear_detachment(
        cells=competition.cells,
        eps_field=state.eps,
        eps_parameters=state.eps_parameters,
        parameters=state.shear_parameters,
        time_step_s=dt,
        start_time_s=start,
        attached_cell_ids=state.attached_cell_ids,
        cell_states=state.shear_states,
    )
    physiology = advance_physiological_states(
        cells=competition.cells,
        solute_fields=state.fields,
        cell_states=state.physiology_states,
        parameters=state.physiology_parameters,
        time_step_s=dt,
        start_time_s=start,
        dry_biomass_per_unit_length_kg_m=1e-18,
        detached_cell_ids=shear.detached_cell_ids,
    )
    retained = tuple(cell for cell in physiology.cells if cell.state != "detached")
    retained_ids = frozenset(cell.cell_id for cell in retained)
    relaxed = relax_cells(
        retained,
        state.mechanics,
        attached_cell_ids=state.attached_cell_ids & retained_ids,
    )
    changed = {cell.cell_id: cell for cell in relaxed.cells}
    cells = tuple(changed.get(cell.cell_id, cell) for cell in physiology.cells)
    entries = _accounting_entries(
        competition=competition,
        quorum=quorum,
        waste=waste_result,
        carbon_before_mol=carbon_before_mol,
        carbon_boundary_mol=carbon_boundary_mol,
        carbon_after_mol=solute_amount_mol(state.fields.carbon, state.depth_m),
        oxygen_before_mol=oxygen_before_mol,
        oxygen_boundary_mol=oxygen_boundary_mol,
        oxygen_after_mol=solute_amount_mol(state.fields.oxygen, state.depth_m),
    )
    end_time_s = (state.step_index + 1) * dt
    state.writer.write_snapshot(
        time_s=end_time_s,
        cells=cells,
        solute_fields=state.fields,
        division_events=(),
        mass_balance_entries=entries,
        quorum_signal_field=state.signal,
        quorum_states=quorum.cell_states,
        eps_field=state.eps,
        competition_snapshot=competition.snapshot,
        physiology_snapshot=physiology.snapshot,
        waste_field=state.waste,
        shear_snapshot=shear.snapshot,
    )
    state.observations = (
        *state.observations,
        *_observations(
            cells,
            state.eps,
            quorum.cell_states,
            physiology.snapshot,
            shear.snapshot,
            end_time_s,
        ),
    )
    state.cells = cells
    state.quorum_states = quorum.cell_states
    state.physiology_states = physiology.cell_states
    state.shear_states = shear.cell_states
    state.mass_balance_entries = entries
    state.competition_snapshot = competition.snapshot
    state.physiology_snapshot = physiology.snapshot
    state.shear_snapshot = shear.snapshot
    state.step_index += 1


def _finalize_fixture_replicate(state: _FixtureRunState) -> OutputPaths:
    """Finalize a complete fixture run without changing scientific state."""
    if state.step_index != FIXTURE_STEP_COUNT:
        raise ExperimentValidationError("only a complete fixture run can be finalized")
    if state.finalized_paths is not None:
        raise ExperimentValidationError("fixture run has already been finalized")
    state.finalized_paths = state.writer.finalize()
    return state.finalized_paths


def _initial_cells(request: ExperimentRunRequest, width: float) -> tuple[Cell, ...]:
    generator = np.random.default_rng(request.seed)
    cells: list[Cell] = []
    for index in range(4):
        producer = index < round(4 * request.condition.producer_fraction)
        x = (
            (index + 0.5) * width / 4
            if request.condition.inoculation_pattern == "segregated"
            else float(generator.uniform(0.2e-6, width - 0.2e-6))
        )
        cells.append(
            Cell(
                f"cell-{index:03d}",
                x,
                0.2e-6,
                0.0,
                1e-6,
                1e-7,
                1e-24,
                0.0,
                "active",
                "producer" if producer else "nonproducer",
            )
        )
    return tuple(cells)


def _constitutive_states(
    states: tuple[CellQuorumState, ...],
) -> tuple[CellQuorumState, ...]:
    return tuple(
        replace(
            state,
            history=(
                *state.history[:-1],
                QuorumObservation(
                    state.current.time_s, state.current.signal_concentration_mol_m3, 1.0
                ),
            ),
        )
        for state in states
    )


def _accounting_entries(
    *,
    competition: Any,
    quorum: Any,
    waste: Any,
    carbon_before_mol: float,
    carbon_boundary_mol: float,
    carbon_after_mol: float,
    oxygen_before_mol: float,
    oxygen_boundary_mol: float,
    oxygen_after_mol: float,
) -> tuple[MassBalanceEntry, ...]:
    """Serialize the explicit resource ledgers returned by each interface."""
    eps_balance = competition.eps.mass_balance
    quorum_balance = quorum.mass_balance
    waste_balance = waste.mass_balance
    metabolism = competition.eps.metabolism.cell_results
    carbon_uptake_mol = sum(item.carbon_uptake_mol for item in metabolism)
    oxygen_uptake_mol = sum(item.oxygen_uptake_mol for item in metabolism)
    return (
        MassBalanceEntry(
            "dry_biomass",
            "kg",
            eps_balance.initial_living_biomass_kg,
            eps_balance.final_living_biomass_kg,
            eps_balance.gross_biomass_equivalent_production_kg
            - eps_balance.produced_eps_kg
            - eps_balance.maintenance_death_loss_kg,
            1e-30,
            1e-12,
        ),
        MassBalanceEntry(
            "eps",
            "kg",
            eps_balance.initial_eps_kg,
            eps_balance.final_eps_kg,
            eps_balance.produced_eps_kg,
            1e-30,
            1e-12,
        ),
        MassBalanceEntry(
            "quorum_signal",
            "mol",
            quorum_balance.initial_signal_mol,
            quorum_balance.final_signal_mol,
            quorum_balance.produced_signal_mol
            - quorum_balance.degraded_signal_mol
            + quorum_balance.boundary_input_signal_mol,
            1e-30,
            1e-12,
        ),
        MassBalanceEntry(
            "waste",
            "mol",
            waste_balance.initial_waste_mol,
            waste_balance.final_waste_mol,
            waste_balance.produced_waste_mol
            - waste_balance.removed_waste_mol
            + waste_balance.boundary_input_waste_mol,
            1e-30,
            1e-12,
        ),
        MassBalanceEntry(
            "carbon",
            "mol",
            carbon_before_mol,
            carbon_after_mol,
            carbon_boundary_mol - carbon_uptake_mol,
            1e-30,
            1e-12,
        ),
        MassBalanceEntry(
            "oxygen",
            "mol",
            oxygen_before_mol,
            oxygen_after_mol,
            oxygen_boundary_mol - oxygen_uptake_mol,
            1e-30,
            1e-12,
        ),
    )


def _observations(
    cells: tuple[Cell, ...],
    eps: EPSField,
    quorum_states: tuple[CellQuorumState, ...],
    physiology: Any,
    shear: Any,
    time_s: float,
) -> tuple[ExperimentObservation, ...]:
    total = sum(cell.dry_biomass_kg for cell in cells)
    producers = [cell for cell in cells if cell.strain == "producer"]
    activation = sum(
        state.current.activation_fraction for state in quorum_states
    ) / len(quorum_states)
    totals = physiology.totals
    values = {
        "producer_cell_frequency": len(producers) / len(cells),
        "total_dry_biomass_kg": total,
        "total_eps_kg": eps.total_mass_kg,
        "quorum_active_fraction": activation,
        "active_biomass_kg": totals.active_biomass_kg,
        "dormant_biomass_kg": totals.dormant_biomass_kg,
        "dead_biomass_kg": totals.dead_biomass_kg,
        "detached_biomass_kg": totals.detached_biomass_kg,
        "biofilm_thickness_m": max(
            (cell.y_m + cell.radius_m for cell in cells), default=0.0
        ),
        "biofilm_roughness_m": 0.0,
        "biofilm_footprint_m": max((cell.x_m for cell in cells), default=0.0)
        - min((cell.x_m for cell in cells), default=0.0),
        "carbon_penetration_depth_m": 4e-6,
        "oxygen_penetration_depth_m": 4e-6,
        "detachment_rate_s": shear.detachment_rate_s,
    }
    units = {
        "producer_cell_frequency": "1",
        "total_dry_biomass_kg": "kg",
        "total_eps_kg": "kg",
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
    return tuple(
        ExperimentObservation(metric, units[metric], time_s, value)
        for metric, value in values.items()
    )


def _commit_hash() -> str:
    return exact_runtime_source_commit(None)


def _validate_campaign_artifacts(output_directory: Path) -> None:
    """Validate the complete immutable campaign and raw-artifact contract."""
    _assert_output_tree_contained(output_directory)
    manifest = output_directory / "campaign_manifest.json"
    summary = output_directory / "summary_statistics.json"
    ranking = output_directory / "sensitivity_ranking.json"
    if not all(path.is_file() for path in (manifest, summary, ranking)):
        raise ExperimentValidationError("campaign artifacts are incomplete")
    campaign = _read_json_object(manifest, "campaign manifest")
    if set(campaign) != {
        "campaign_configuration",
        "campaign_configuration_sha256",
        "parameter_files",
        "runs",
        "sensitivity_ranking",
        "summary_statistics",
    }:
        raise ExperimentValidationError("campaign manifest schema is malformed")
    if campaign["summary_statistics"] != summary.name:
        raise ExperimentValidationError("campaign manifest summary path is malformed")
    if campaign["sensitivity_ranking"] != ranking.name:
        raise ExperimentValidationError("campaign manifest ranking path is malformed")
    if not _is_sha256(campaign["campaign_configuration_sha256"]):
        raise ExperimentValidationError("campaign configuration hash is malformed")

    configuration = campaign["campaign_configuration"]
    if not isinstance(configuration, dict):
        raise ExperimentValidationError("campaign configuration is malformed")
    campaign_id = configuration.get("campaign_id")
    if not isinstance(campaign_id, str) or not campaign_id.strip():
        raise ExperimentValidationError("campaign_id is malformed")
    if configuration.get("seeds") != list(FIXTURE_SEEDS):
        raise ExperimentValidationError("campaign must contain three fixed seeds")
    if configuration.get("calibration_status") != "CALIBRATION_REQUIRED":
        raise ExperimentValidationError(
            "campaign must preserve CALIBRATION_REQUIRED status"
        )
    if configuration.get("biological_parameter_files") != list(
        BIOLOGICAL_PARAMETER_FILES
    ):
        raise ExperimentValidationError(
            "campaign biological provenance is missing or mixed with fixture inputs"
        )
    condition_payloads = configuration.get("conditions")
    if not isinstance(condition_payloads, list) or not condition_payloads:
        raise ExperimentValidationError("campaign conditions are malformed")
    conditions: dict[str, ExperimentCondition] = {}
    try:
        for payload in condition_payloads:
            condition = ExperimentCondition.model_validate(payload)
            if condition.condition_id in conditions:
                raise ExperimentValidationError("campaign condition IDs are duplicated")
            conditions[condition.condition_id] = condition
    except (ValueError, TypeError) as error:
        raise ExperimentValidationError(
            f"campaign condition is malformed: {error}"
        ) from error

    parameter_files = _validate_parameter_file_records(campaign["parameter_files"])
    runs = campaign["runs"]
    if not isinstance(runs, list) or not runs:
        raise ExperimentValidationError("campaign manifest has no runs")
    expected_runs = {
        (condition_id, seed)
        for condition_id in conditions
        for seed in FIXTURE_SEEDS
    }
    observed_runs: set[tuple[str, int]] = set()
    for record in runs:
        if not isinstance(record, dict) or set(record) != {
            "condition_id",
            "run_manifest",
            "seed",
        }:
            raise ExperimentValidationError("campaign run record is malformed")
        condition_id = record["condition_id"]
        seed = record["seed"]
        relative_manifest = record["run_manifest"]
        if (
            not isinstance(condition_id, str)
            or isinstance(seed, bool)
            or not isinstance(seed, int)
            or not isinstance(relative_manifest, str)
        ):
            raise ExperimentValidationError("campaign run identity is malformed")
        identity = (condition_id, seed)
        if identity not in expected_runs or identity in observed_runs:
            raise ExperimentValidationError("campaign run matrix is malformed")
        observed_runs.add(identity)
        run = _safe_artifact_path(output_directory, relative_manifest)
        if not run.is_file():
            raise ExperimentValidationError("campaign references missing run manifest")
        _validate_run_artifacts(
            run,
            campaign_id=campaign_id,
            condition=conditions[condition_id],
            seed=seed,
            parameter_files=parameter_files,
        )
    if observed_runs != expected_runs:
        raise ExperimentValidationError("campaign run matrix is incomplete")
    _validate_summary_statistics(summary, campaign_id, set(conditions))
    _validate_sensitivity_ranking(ranking, campaign_id, conditions)


def _validate_parameter_file_records(value: object) -> dict[str, str]:
    if not isinstance(value, list) or not value:
        raise ExperimentValidationError("biological parameter records are malformed")
    records: dict[str, str] = {}
    for item in value:
        if not isinstance(item, dict) or set(item) != {"label", "sha256"}:
            raise ExperimentValidationError(
                "biological parameter record is malformed"
            )
        label, sha256 = item["label"], item["sha256"]
        if (
            not isinstance(label, str)
            or label not in BIOLOGICAL_PARAMETER_FILES
            or label in records
            or not _is_sha256(sha256)
        ):
            raise ExperimentValidationError(
                "biological parameter record is malformed"
            )
        records[label] = sha256
    if set(records) != set(BIOLOGICAL_PARAMETER_FILES):
        raise ExperimentValidationError("biological parameter records are incomplete")
    return records


def _validate_run_artifacts(
    manifest_path: Path,
    *,
    campaign_id: str,
    condition: ExperimentCondition,
    seed: int,
    parameter_files: dict[str, str],
) -> None:
    payload = _read_json_object(manifest_path, "run manifest")
    if set(payload) != {
        "campaign_id",
        "condition",
        "observations",
        "parameter_files",
        "raw_artifacts",
        "seed",
    }:
        raise ExperimentValidationError("run manifest schema is malformed")
    if (
        payload["campaign_id"] != campaign_id
        or payload["seed"] != seed
        or payload["condition"] != condition.model_dump(mode="json")
    ):
        raise ExperimentValidationError("run manifest identity is malformed")
    if _validate_parameter_file_records(payload["parameter_files"]) != parameter_files:
        raise ExperimentValidationError("run biological provenance is inconsistent")
    _validate_observations(payload["observations"])

    run_directory = manifest_path.parent
    raw = payload["raw_artifacts"]
    if not isinstance(raw, list) or not raw:
        raise ExperimentValidationError("run manifest has no raw artifact hashes")
    recorded_paths: set[str] = set()
    for record in raw:
        if not isinstance(record, dict) or set(record) != {
            "path",
            "sha256",
            "size_bytes",
        }:
            raise ExperimentValidationError("raw artifact record is malformed")
        relative_path = record["path"]
        size_bytes = record["size_bytes"]
        if (
            not isinstance(relative_path, str)
            or relative_path in recorded_paths
            or isinstance(size_bytes, bool)
            or not isinstance(size_bytes, int)
            or size_bytes < 0
            or not _is_sha256(record["sha256"])
        ):
            raise ExperimentValidationError("raw artifact record is malformed")
        recorded_paths.add(relative_path)
        artifact = _safe_artifact_path(run_directory, relative_path)
        if not artifact.is_file():
            raise ExperimentValidationError(
                f"run references missing raw artifact {relative_path}"
            )
        contents = artifact.read_bytes()
        digest = hashlib.sha256(contents).hexdigest()
        if len(contents) != size_bytes or digest != record["sha256"]:
            raise ExperimentValidationError(
                f"raw artifact hash or size mismatch: {relative_path}"
            )
    actual_paths = {
        path.relative_to(run_directory).as_posix()
        for path in run_directory.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual_paths != recorded_paths:
        raise ExperimentValidationError("raw artifact manifest is incomplete")
    if not REQUIRED_RUN_FILES <= recorded_paths:
        raise ExperimentValidationError("run is missing required raw outputs")

    metadata = _read_json_object(run_directory / "run_metadata.json", "run metadata")
    required_metadata = {
        "commit_hash",
        "seed",
        "parameters",
        "platform",
        "python_version",
        "parameter_file",
        "parameter_file_sha256",
    }
    if not required_metadata <= set(metadata):
        raise ExperimentValidationError(
            "run metadata lacks commit, seed, parameters, or environment"
        )
    parameter_label = metadata["parameter_file"]
    parameters = metadata["parameters"]
    if (
        metadata["seed"] != seed
        or not isinstance(metadata["commit_hash"], str)
        or not metadata["commit_hash"].strip()
        or not isinstance(metadata["platform"], str)
        or not metadata["platform"].strip()
        or not isinstance(metadata["python_version"], str)
        or not metadata["python_version"].strip()
        or not isinstance(parameter_label, str)
        or parameter_label not in parameter_files
        or metadata["parameter_file_sha256"] != parameter_files[parameter_label]
        or not isinstance(parameters, dict)
        or parameters.get("condition") != condition.model_dump(mode="json")
        or parameters.get("software_fixture")
        != "manufactured SI software validation"
        or parameters.get("update_order") != UPDATE_ORDER
    ):
        raise ExperimentValidationError("run metadata provenance is malformed")

    for table_name in sorted(REQUIRED_RUN_FILES - {"run_metadata.json"}):
        try:
            pq.read_table(run_directory / table_name)
        except Exception as error:
            raise ExperimentValidationError(
                f"malformed Parquet artifact {table_name}: {error}"
            ) from error
    accounting = pq.read_table(run_directory / "mass_balance.parquet")
    accounting_pairs = set(
        zip(
            accounting.column("quantity").to_pylist(),
            accounting.column("unit").to_pylist(),
            strict=True,
        )
    )
    if not {
        ("carbon", "mol"),
        ("oxygen", "mol"),
        ("dry_biomass", "kg"),
        ("eps", "kg"),
        ("quorum_signal", "mol"),
        ("waste", "mol"),
    } <= accounting_pairs:
        raise ExperimentValidationError("mass-balance SI accounting is incomplete")

    field_paths = sorted(
        path for path in recorded_paths if path.startswith("fields/")
    )
    if not field_paths:
        raise ExperimentValidationError("run has no NumPy field artifacts")
    for relative_path in field_paths:
        try:
            with np.load(run_directory / relative_path, allow_pickle=False) as archive:
                if not REQUIRED_FIELD_ARRAYS <= set(archive.files):
                    raise ExperimentValidationError(
                        f"NumPy field artifact is incomplete: {relative_path}"
                    )
                if any(
                    not np.issubdtype(archive[name].dtype, np.number)
                    or not np.all(np.isfinite(archive[name]))
                    for name in REQUIRED_FIELD_ARRAYS
                ):
                    raise ExperimentValidationError(
                        f"NumPy field artifact is malformed: {relative_path}"
                    )
        except (OSError, ValueError) as error:
            raise ExperimentValidationError(
                f"malformed NumPy artifact {relative_path}: {error}"
            ) from error


def _validate_observations(value: object) -> None:
    if not isinstance(value, list) or not value:
        raise ExperimentValidationError("run observations are malformed")
    metric_times: dict[str, set[float]] = {
        metric: set() for metric in REQUIRED_METRIC_UNITS
    }
    for row in value:
        if not isinstance(row, dict) or set(row) != {
            "metric",
            "time_s",
            "unit",
            "value",
        }:
            raise ExperimentValidationError("run observation is malformed")
        metric = row["metric"]
        if (
            not isinstance(metric, str)
            or metric not in REQUIRED_METRIC_UNITS
            or row["unit"] != REQUIRED_METRIC_UNITS[metric]
            or not _is_finite_number(row["time_s"], minimum=0.0)
            or not _is_finite_number(row["value"])
        ):
            raise ExperimentValidationError("run observation is malformed")
        time_s = float(row["time_s"])
        if time_s in metric_times[metric]:
            raise ExperimentValidationError("run observations are duplicated")
        metric_times[metric].add(time_s)
    if any(len(times) < 2 for times in metric_times.values()):
        raise ExperimentValidationError("run observations are incomplete")


def _validate_summary_statistics(
    path: Path, campaign_id: str, condition_ids: set[str]
) -> None:
    payload = _read_json_object(path, "summary statistics")
    if set(payload) != {"campaign_id", "confidence_level", "statistics"}:
        raise ExperimentValidationError("summary statistics schema is malformed")
    rows = payload["statistics"]
    if payload["campaign_id"] != campaign_id or not isinstance(rows, list) or not rows:
        raise ExperimentValidationError("summary statistics are malformed")
    coverage: dict[tuple[str, str], set[float]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "condition_id",
            "confidence_interval_high",
            "confidence_interval_low",
            "mean",
            "metric",
            "replicate_count",
            "time_s",
            "unit",
            "variance",
        }:
            raise ExperimentValidationError("summary statistic row is malformed")
        condition_id, metric = row["condition_id"], row["metric"]
        if (
            not isinstance(condition_id, str)
            or condition_id not in condition_ids
            or not isinstance(metric, str)
            or metric not in REQUIRED_METRIC_UNITS
            or row["unit"] != REQUIRED_METRIC_UNITS[metric]
            or row["replicate_count"] != len(FIXTURE_SEEDS)
            or not _is_finite_number(row["time_s"], minimum=0.0)
            or not _is_finite_number(row["mean"])
            or not _is_finite_number(row["variance"], minimum=0.0)
            or not _is_finite_number(row["confidence_interval_low"])
            or not _is_finite_number(row["confidence_interval_high"])
            or float(row["confidence_interval_low"])
            > float(row["mean"])
            or float(row["confidence_interval_high"])
            < float(row["mean"])
        ):
            raise ExperimentValidationError("summary statistic row is malformed")
        key = (condition_id, metric)
        times = coverage.setdefault(key, set())
        time_s = float(row["time_s"])
        if time_s in times:
            raise ExperimentValidationError("summary statistic rows are duplicated")
        times.add(time_s)
    expected_keys = {
        (condition_id, metric)
        for condition_id in condition_ids
        for metric in REQUIRED_METRIC_UNITS
    }
    if set(coverage) != expected_keys or any(
        len(times) < 2 for times in coverage.values()
    ):
        raise ExperimentValidationError("summary statistic coverage is incomplete")


def _validate_sensitivity_ranking(
    path: Path,
    campaign_id: str,
    conditions: dict[str, ExperimentCondition],
) -> None:
    payload = _read_json_object(path, "sensitivity ranking")
    if set(payload) != {"campaign_id", "method", "rankings"}:
        raise ExperimentValidationError("sensitivity ranking schema is malformed")
    rankings = payload["rankings"]
    if payload["campaign_id"] != campaign_id or not isinstance(rankings, list):
        raise ExperimentValidationError("sensitivity ranking is malformed")
    family_counts: dict[str, int] = {}
    for condition in conditions.values():
        family_counts[condition.family] = family_counts.get(condition.family, 0) + 1
    expected_families = {
        family
        for family, count in family_counts.items()
        if family in SWEEP_PARAMETERS and count >= 2
    }
    if bool(rankings) != bool(expected_families):
        raise ExperimentValidationError("sensitivity ranking coverage is incomplete")
    for row in rankings:
        if not isinstance(row, dict) or set(row) != {
            "metric",
            "ranking",
            "time_s",
            "unit",
        }:
            raise ExperimentValidationError("sensitivity ranking row is malformed")
        metric, entries = row["metric"], row["ranking"]
        if (
            not isinstance(metric, str)
            or metric not in REQUIRED_METRIC_UNITS
            or row["unit"] != REQUIRED_METRIC_UNITS[metric]
            or not _is_finite_number(row["time_s"], minimum=0.0)
            or not isinstance(entries, list)
            or {entry.get("family") for entry in entries if isinstance(entry, dict)}
            != expected_families
        ):
            raise ExperimentValidationError("sensitivity ranking row is malformed")
        for expected_rank, entry in enumerate(entries, start=1):
            if (
                not isinstance(entry, dict)
                or entry.get("rank") != expected_rank
                or not _is_finite_number(entry.get("absolute_mean_range"), minimum=0.0)
            ):
                raise ExperimentValidationError(
                    "sensitivity ranking entry is malformed"
                )


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExperimentValidationError(f"malformed {label}: {error}") from error
    if not isinstance(payload, dict):
        raise ExperimentValidationError(f"malformed {label}: expected an object")
    return payload


def _safe_artifact_path(root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ExperimentValidationError("artifact path must be relative and contained")
    resolved_root = root.resolve()
    resolved_path = (root / path).resolve()
    if not resolved_path.is_relative_to(resolved_root):
        raise ExperimentValidationError("artifact path escapes campaign output")
    return resolved_path


def _assert_output_tree_contained(root: Path) -> None:
    """Reject symlinks and paths resolving outside a campaign output root."""
    resolved_root = root.resolve()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ExperimentValidationError(
                f"campaign output must not contain symlinks: {path}"
            )
        try:
            path.resolve(strict=False).relative_to(resolved_root)
        except ValueError as error:
            raise ExperimentValidationError(
                f"campaign output escapes requested output root: {path}"
            ) from error


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_finite_number(value: object, *, minimum: float | None = None) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    converted = float(value)
    return math.isfinite(converted) and (minimum is None or converted >= minimum)
