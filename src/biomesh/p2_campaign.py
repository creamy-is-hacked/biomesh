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

import json
import platform
import subprocess
import sys
from dataclasses import dataclass, replace
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from biomesh import __version__
from biomesh.cells import Cell
from biomesh.competition import CompetitionStrains, advance_competition
from biomesh.eps import EPSField, EPSParameters
from biomesh.experiments import (
    ExperimentCampaign,
    ExperimentCondition,
    ExperimentObservation,
    ExperimentRunRequest,
    ExperimentValidationError,
    SweepParameter,
    load_experiment_campaign,
    run_experiment_campaign,
)
from biomesh.mass_balance import solute_amount_mol, top_boundary_input_rate_mol_s
from biomesh.mechanics import MechanicsParameters, attach_initial_cells, relax_cells
from biomesh.metabolism import MetabolismParameters
from biomesh.outputs import MassBalanceEntry, RunMetadata, SimulationOutputWriter
from biomesh.physiology import (
    DeadBiomassRule,
    PhysiologyParameters,
    advance_physiological_states,
    initialize_physiological_states,
    metabolic_activity_fractions,
)
from biomesh.quorum import (
    CellQuorumState,
    QuorumObservation,
    QuorumSignalParameters,
    advance_quorum_signal,
    initialize_quorum_states,
)
from biomesh.shear import ShearParameters, advance_shear_detachment
from biomesh.solutes import SoluteField, SoluteFields
from biomesh.waste import WasteParameters, advance_waste

FIXTURE_SCHEMA_VERSION = 1
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

    campaign_id: str
    condition_ids: tuple[str, ...]


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
    if payload["fixture_kind"] not in {"experiment", "sweep"}:
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
    return FixtureCommand(campaign_id, tuple(condition_ids))


def run_fixture_command(*, fixture_file: Path, output_directory: Path) -> Path:
    """Run selected P2 conditions with three deterministic seeds and real artifacts."""
    command = load_fixture_command(fixture_file)
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
    fixtures = sorted(
        fixture_directory / name
        for name in (
            "producer.yaml",
            "nonproducer.yaml",
            "competition_50_50.yaml",
            "qs_threshold_sweep.yaml",
            "eps_cost_sweep.yaml",
            "shear_sweep.yaml",
        )
    )
    if len(fixtures) != 6:
        raise ExperimentValidationError(
            "expected exactly six P2 software-validation fixtures"
        )
    commands = [load_fixture_command(path) for path in fixtures]
    return {
        "fixture_count": len(commands),
        "passed": True,
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
    figure.savefig(report, dpi=120)
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
        condition("eps-quorum", "eps_control", 0.5),
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
        seeds=[101, 202, 303],
        biological_parameter_files=[str(fixture_file.resolve())],
        conditions=conditions,
    )


def _run_fixture_replicate(
    request: ExperimentRunRequest, directory: Path
) -> tuple[ExperimentObservation, ...]:
    """Compose all approved P2 interfaces for one fixture condition/seed."""
    values = {
        item.name: float(item.value) for item in request.condition.parameter_overrides
    }
    dt, depth = 0.1, 1e-6
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
            "fixture": "manufactured SI software validation",
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
    shear_states = None
    observations: list[ExperimentObservation] = []
    for index in range(1, 4):
        start = (index - 1) * dt
        quorum = advance_quorum_signal(
            cells=cells,
            signal_field=signal,
            parameters=quorum_parameters,
            time_step_s=dt,
            depth_m=depth,
            start_time_s=start,
            cell_states=quorum_states,
        )
        eps_quorum_states = (
            _constitutive_states(quorum_states)
            if request.condition.eps_control == "constitutive"
            else quorum_states
        )
        activities = metabolic_activity_fractions(
            cells=cells, cell_states=physiology_states, parameters=physiology_parameters
        )
        carbon_before_mol = solute_amount_mol(fields.carbon, depth)
        oxygen_before_mol = solute_amount_mol(fields.oxygen, depth)
        carbon_boundary_mol = top_boundary_input_rate_mol_s(fields.carbon, depth) * dt
        oxygen_boundary_mol = top_boundary_input_rate_mol_s(fields.oxygen, depth) * dt
        competition = advance_competition(
            cells=cells,
            strain_roles=strains,
            solute_fields=fields,
            eps_field=eps,
            quorum_states=eps_quorum_states,
            eps_parameters=eps_parameters,
            metabolism_parameters=metabolism,
            time_step_s=dt,
            start_time_s=start,
            dry_biomass_per_unit_length_kg_m=1e-18,
            metabolic_activity_fractions=activities,
        )
        waste_result = advance_waste(
            cells=competition.cells,
            waste_field=waste,
            parameters=WasteParameters(1e-23, 0.0),
            time_step_s=dt,
            depth_m=depth,
            metabolic_activity_fractions=activities,
        )
        shear = advance_shear_detachment(
            cells=competition.cells,
            eps_field=eps,
            eps_parameters=eps_parameters,
            parameters=shear_parameters,
            time_step_s=dt,
            start_time_s=start,
            attached_cell_ids=attached.attached_cell_ids,
            cell_states=shear_states,
        )
        shear_states = shear.cell_states
        physiology = advance_physiological_states(
            cells=competition.cells,
            solute_fields=fields,
            cell_states=physiology_states,
            parameters=physiology_parameters,
            time_step_s=dt,
            start_time_s=start,
            dry_biomass_per_unit_length_kg_m=1e-18,
            detached_cell_ids=shear.detached_cell_ids,
        )
        retained = tuple(cell for cell in physiology.cells if cell.state != "detached")
        retained_ids = frozenset(cell.cell_id for cell in retained)
        relaxed = relax_cells(
            retained,
            mechanics,
            attached_cell_ids=attached.attached_cell_ids & retained_ids,
        )
        changed = {cell.cell_id: cell for cell in relaxed.cells}
        cells = tuple(changed.get(cell.cell_id, cell) for cell in physiology.cells)
        physiology_states = physiology.cell_states
        entries = _accounting_entries(
            competition=competition,
            quorum=quorum,
            waste=waste_result,
            carbon_before_mol=carbon_before_mol,
            carbon_boundary_mol=carbon_boundary_mol,
            carbon_after_mol=solute_amount_mol(fields.carbon, depth),
            oxygen_before_mol=oxygen_before_mol,
            oxygen_boundary_mol=oxygen_boundary_mol,
            oxygen_after_mol=solute_amount_mol(fields.oxygen, depth),
        )
        writer.write_snapshot(
            time_s=index * dt,
            cells=cells,
            solute_fields=fields,
            division_events=(),
            mass_balance_entries=entries,
            quorum_signal_field=signal,
            quorum_states=quorum.cell_states,
            eps_field=eps,
            competition_snapshot=competition.snapshot,
            physiology_snapshot=physiology.snapshot,
            waste_field=waste,
            shear_snapshot=shear.snapshot,
        )
        observations.extend(
            _observations(
                cells,
                eps,
                quorum.cell_states,
                physiology.snapshot,
                shear.snapshot,
                index * dt,
            )
        )
        quorum_states = quorum.cell_states
    writer.finalize()
    return tuple(observations)


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
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return (
        result.stdout.strip()
        if result.returncode == 0 and result.stdout.strip()
        else "UNKNOWN"
    )


def _validate_campaign_artifacts(output_directory: Path) -> None:
    manifest = output_directory / "campaign_manifest.json"
    summary = output_directory / "summary_statistics.json"
    ranking = output_directory / "sensitivity_ranking.json"
    if not all(path.is_file() for path in (manifest, summary, ranking)):
        raise ExperimentValidationError("campaign artifacts are incomplete")
    campaign = json.loads(manifest.read_text())
    if not campaign.get("runs"):
        raise ExperimentValidationError("campaign manifest has no runs")
    for record in campaign["runs"]:
        run = output_directory / record["run_manifest"]
        if not run.is_file():
            raise ExperimentValidationError("campaign references missing run manifest")
        payload = json.loads(run.read_text())
        raw = payload.get("raw_artifacts", [])
        if not raw:
            raise ExperimentValidationError("run manifest has no raw artifact hashes")
        run_directory = run.parent
        metadata = run_directory / "run_metadata.json"
        if not metadata.is_file():
            raise ExperimentValidationError("run is missing environment metadata")
        metadata_payload = json.loads(metadata.read_text())
        if not {
            "commit_hash",
            "seed",
            "parameters",
            "platform",
            "python_version",
        } <= set(metadata_payload):
            raise ExperimentValidationError(
                "run metadata lacks commit, seed, parameters, or environment"
            )
        for table in (
            "summary.parquet",
            "mass_balance.parquet",
            "competition_summary.parquet",
        ):
            try:
                pq.read_table(run_directory / table)
            except Exception as error:
                raise ExperimentValidationError(
                    f"malformed Parquet artifact {table}: {error}"
                ) from error
