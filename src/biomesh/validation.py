"""Executable manufactured and analytical validation cases for P1-WP07."""

from __future__ import annotations

from dataclasses import asdict
from math import exp, pi
from pathlib import Path

import numpy as np

from biomesh.cells import Cell, CellModelParameters
from biomesh.mechanics import MechanicsParameters
from biomesh.metabolism import (
    MetabolismParameters,
    evaluate_cell_metabolism,
)
from biomesh.outputs import SimulationOutputWriter
from biomesh.provenance import collect_run_metadata
from biomesh.simulation import SimulationParameters, run_simulation
from biomesh.solutes import SoluteField, SoluteFields


def validate_diffusion() -> dict[str, float | bool]:
    """Run the P1 manufactured diffusion solution and refinement check."""
    coarse_error = _diffusion_mode_error((24, 48))
    fine_error = _diffusion_mode_error((48, 96))
    threshold = 2.0e-3
    return {
        "fine_error": fine_error,
        "passed": fine_error < threshold and fine_error < coarse_error,
        "refinement_ratio": fine_error / coarse_error,
        "threshold": threshold,
    }


def validate_growth() -> dict[str, float | bool]:
    """Run a declared synthetic ODE case against its analytical solution."""
    parameters = _synthetic_metabolism_parameters()
    initial_biomass_kg = 1.7
    time_step_s = 3.5
    carbon_mol_m3 = 6.0
    oxygen_mol_m3 = 12.0
    result = evaluate_cell_metabolism(
        initial_biomass_kg,
        carbon_mol_m3,
        oxygen_mol_m3,
        time_step_s,
        parameters,
    )
    expected_rate_s = 0.4 * (6.0 / 8.0) * (12.0 / 16.0)
    expected_biomass_kg = initial_biomass_kg * exp(
        (expected_rate_s - parameters.death_rate_s) * time_step_s
    )
    absolute_error_kg = abs(result.final_dry_biomass_kg - expected_biomass_kg)
    threshold_kg = 1.0e-12
    return {
        "absolute_error_kg": absolute_error_kg,
        "passed": absolute_error_kg <= threshold_kg,
        "threshold_kg": threshold_kg,
    }


def validate_mass_balance(
    *,
    output_directory: Path,
    parameter_file: Path,
    repository_root: Path | None,
) -> dict[str, float | bool]:
    """Run one full synthetic P1 step including nonzero top-boundary input."""
    fields = SoluteFields(
        carbon=SoluteField(
            "carbon",
            (2, 2),
            1.0,
            1.0,
            0.01,
            4.0,
            np.full((2, 2), 3.0, dtype=np.float64),
        ),
        oxygen=SoluteField(
            "oxygen",
            (2, 2),
            1.0,
            1.0,
            0.01,
            6.0,
            np.full((2, 2), 5.0, dtype=np.float64),
        ),
    )
    cell = Cell(
        cell_id="cell-000000000000",
        x_m=0.5,
        y_m=0.25,
        orientation_rad=0.0,
        length_m=0.2,
        radius_m=0.02,
        dry_biomass_kg=0.2,
        age_s=0.0,
        state="active",
        strain="synthetic-validation",
    )
    simulation_parameters = SimulationParameters(
        time_step_s=0.1,
        step_count=1,
        depth_m=1.0,
        cell_model=CellModelParameters(
            dry_biomass_per_unit_length_kg_m=1.0,
            division_length_m=0.2,
            maximum_daughter_asymmetry_fraction=0.01,
        ),
        metabolism=_synthetic_metabolism_parameters(),
        mechanics=MechanicsParameters(
            domain_width_m=1.0,
            maximum_overlap_m=1.0e-12,
            maximum_iterations=100,
            displacement_fraction=1.0,
            attachment_mode="bottom",
        ),
        mass_balance_absolute_tolerance=1.0e-12,
        mass_balance_relative_tolerance=1.0e-12,
        next_cell_sequence=1,
    )
    metadata = collect_run_metadata(
        parameter_file=parameter_file,
        parameter_file_label=str(parameter_file),
        parameters={
            "purpose": "synthetic manufactured P1 integration validation",
            "scientific_use": False,
            "simulation_parameters": asdict(simulation_parameters),
        },
        seed=42,
        repository_root=repository_root,
    )
    result = run_simulation(
        initial_cells=(cell,),
        initial_solute_fields=fields,
        parameters=simulation_parameters,
        seed=42,
        output_writer=SimulationOutputWriter(output_directory, metadata),
    )
    maximum_absolute_residual = max(
        abs(entry.residual_amount) for entry in result.mass_balance_entries
    )
    maximum_relative_error = max(
        entry.relative_error for entry in result.mass_balance_entries
    )
    passed = all(
        abs(entry.residual_amount) <= entry.allowed_residual_amount
        for entry in result.mass_balance_entries
    )
    return {
        "carbon_equivalent_net_input_mol": next(
            entry.net_input_amount
            for entry in result.mass_balance_entries
            if entry.quantity == "carbon_equivalent"
        ),
        "maximum_absolute_residual": maximum_absolute_residual,
        "maximum_overlap_m": result.maximum_overlap_m,
        "maximum_relative_error": maximum_relative_error,
        "passed": passed,
    }


def _synthetic_metabolism_parameters() -> MetabolismParameters:
    """Return dimensionally valid manufactured values, not biological constants."""
    return MetabolismParameters(
        maximum_specific_growth_rate_s=0.4,
        carbon_half_saturation_mol_m3=2.0,
        oxygen_half_saturation_mol_m3=4.0,
        death_rate_s=0.1,
        biomass_yield_on_carbon_kg_mol=2.0,
        biomass_yield_on_oxygen_kg_mol=4.0,
    )


def _diffusion_mode_error(shape: tuple[int, int]) -> float:
    rows, columns = shape
    width_m = 1.0
    height_m = 1.0
    diffusivity_m2_s = 0.1
    bulk_mol_m3 = 1.0
    amplitude_mol_m3 = 0.25
    x = (np.arange(columns) + 0.5) * width_m / columns
    y = (np.arange(rows) + 0.5) * height_m / rows
    x_mesh, y_mesh = np.meshgrid(x, y)
    mode = np.cos(2.0 * pi * x_mesh / width_m) * np.sin(
        pi * y_mesh / (2.0 * height_m)
    )
    field = SoluteField(
        "synthetic",
        shape,
        width_m,
        height_m,
        diffusivity_m2_s,
        bulk_mol_m3,
        bulk_mol_m3 + amplitude_mol_m3 * mode,
    )
    final_time_s = 0.002
    time_step_s = min(0.00001, field.maximum_stable_timestep_s / 2.0)
    steps = round(final_time_s / time_step_s)
    time_step_s = final_time_s / steps
    for _ in range(steps):
        field.advance(time_step_s)
    decay = exp(
        -diffusivity_m2_s
        * ((2.0 * pi) ** 2 + (pi / 2.0) ** 2)
        * final_time_s
    )
    expected = bulk_mol_m3 + amplitude_mol_m3 * mode * decay
    return float(np.max(np.abs(field.concentration_mol_m3 - expected)))
