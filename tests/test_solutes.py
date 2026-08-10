"""P1-WP02 solute transport verification tests using synthetic inputs."""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from biomesh.solutes import (
    CellSoluteExchange,
    DiffusionStabilityError,
    NegativeConcentrationError,
    SoluteField,
    SoluteFields,
)


def _analytical_mode(shape: tuple[int, int]) -> tuple[SoluteField, NDArray[np.float64]]:
    """Create a manufactured diffusion mode for the specified grid resolution."""
    rows, columns = shape
    width_m = 1.0
    height_m = 1.0
    diffusivity_m2_s = 0.1
    bulk_mol_m3 = 1.0
    amplitude_mol_m3 = 0.25
    x = (np.arange(columns) + 0.5) * width_m / columns
    y = (np.arange(rows) + 0.5) * height_m / rows
    x_mesh, y_mesh = np.meshgrid(x, y)
    mode = np.cos(2.0 * np.pi * x_mesh / width_m) * np.sin(
        np.pi * y_mesh / (2.0 * height_m)
    )
    field = SoluteField(
        name="synthetic",
        shape=shape,
        width_m=width_m,
        height_m=height_m,
        diffusivity_m2_s=diffusivity_m2_s,
        top_bulk_concentration_mol_m3=bulk_mol_m3,
        concentration_mol_m3=bulk_mol_m3 + amplitude_mol_m3 * mode,
    )
    return field, mode


def _mode_error(shape: tuple[int, int]) -> float:
    """Advance a manufactured mode and return its maximum analytical error."""
    field, mode = _analytical_mode(shape)
    final_time_s = 0.002
    time_step_s = min(0.00001, field.maximum_stable_timestep_s / 2.0)
    steps = round(final_time_s / time_step_s)
    time_step_s = final_time_s / steps
    for _ in range(steps):
        field.advance(time_step_s)
    decay = np.exp(-0.1 * ((2.0 * np.pi) ** 2 + (np.pi / 2.0) ** 2) * final_time_s)
    expected = 1.0 + 0.25 * mode * decay
    return float(np.max(np.abs(field.concentration_mol_m3 - expected)))


def test_pure_diffusion_matches_analytical_mode() -> None:
    """A manufactured periodic/Dirichlet/no-flux mode decays analytically."""
    assert _mode_error((48, 96)) < 0.002


def test_grid_refinement_reduces_pure_diffusion_error() -> None:
    """The manufactured diffusion benchmark converges under grid refinement."""
    assert _mode_error((48, 96)) < _mode_error((24, 48))


def test_stable_diffusion_preserves_nonnegative_concentrations() -> None:
    """A stable no-source step does not create negative concentrations."""
    field = SoluteField(
        name="carbon",
        shape=(8, 8),
        width_m=2.0,
        height_m=1.0,
        diffusivity_m2_s=0.2,
        top_bulk_concentration_mol_m3=0.0,
        concentration_mol_m3=np.zeros((8, 8), dtype=np.float64),
    )
    field.concentration_mol_m3[4, 4] = 1.0

    field.advance(field.maximum_stable_timestep_s)

    assert float(np.min(field.concentration_mol_m3)) >= -1.0e-12


def test_solute_field_rejects_any_negative_initial_state() -> None:
    """The stored field state is strictly finite and nonnegative."""
    with pytest.raises(NegativeConcentrationError, match="below zero"):
        SoluteField(
            name="carbon",
            shape=(2, 2),
            width_m=1.0,
            height_m=1.0,
            diffusivity_m2_s=0.0,
            top_bulk_concentration_mol_m3=0.0,
            concentration_mol_m3=np.array(
                [[0.0, -1.0e-15], [0.0, 0.0]], dtype=np.float64
            ),
        )


def test_solute_field_rejects_tiny_negative_candidate_state() -> None:
    """Numerical tolerance never stores a negative concentration."""
    field = SoluteField(
        name="carbon",
        shape=(2, 2),
        width_m=1.0,
        height_m=1.0,
        diffusivity_m2_s=0.0,
        top_bulk_concentration_mol_m3=0.0,
        concentration_mol_m3=np.zeros((2, 2), dtype=np.float64),
    )

    with pytest.raises(NegativeConcentrationError, match="below zero"):
        field.advance(
            1.0,
            np.full((2, 2), -1.0e-15, dtype=np.float64),
        )


def test_bottom_boundary_uses_no_flux_stencil() -> None:
    """The bottom cell has one interior diffusive face and no exterior flux."""
    concentration = np.zeros((4, 4), dtype=np.float64)
    concentration[-1, :] = 1.0
    field = SoluteField(
        name="oxygen",
        shape=(4, 4),
        width_m=1.0,
        height_m=1.0,
        diffusivity_m2_s=0.1,
        top_bulk_concentration_mol_m3=0.0,
        concentration_mol_m3=concentration,
    )
    time_step_s = field.maximum_stable_timestep_s / 2.0

    field.advance(time_step_s)

    expected_bottom = 1.0 - time_step_s * 0.1 / field.cell_height_m**2
    assert np.allclose(field.concentration_mol_m3[-1, :], expected_bottom)


def test_unstable_timestep_fails_explicitly() -> None:
    """The solver refuses an FTCS step outside the calculated stability limit."""
    field, _ = _analytical_mode((8, 8))

    with pytest.raises(DiffusionStabilityError, match="stability limit"):
        field.advance(field.maximum_stable_timestep_s * 1.01)


def test_cell_exchange_mapping_conserves_each_solute_rate() -> None:
    """Point-cell source/sink mapping preserves total carbon and oxygen rates."""
    carbon = SoluteField(
        "carbon", (4, 8), 2.0, 1.0, 0.1, 1.0, np.ones((4, 8))
    )
    oxygen = SoluteField(
        "oxygen", (4, 8), 2.0, 1.0, 0.2, 2.0, np.ones((4, 8))
    )
    fields = SoluteFields(carbon, oxygen)
    exchanges = [
        CellSoluteExchange(0.1, 0.1, -3.0e-9, -5.0e-9),
        CellSoluteExchange(1.8, 0.8, 1.0e-9, 2.0e-9),
    ]
    depth_m = 0.5

    carbon_source, oxygen_source = fields.source_rates_from_cell_exchanges(
        exchanges, depth_m
    )

    volume_m3 = carbon.cell_width_m * carbon.cell_height_m * depth_m
    assert np.sum(carbon_source) * volume_m3 == pytest.approx(-2.0e-9)
    assert np.sum(oxygen_source) * volume_m3 == pytest.approx(-3.0e-9)


def test_cell_exchange_rejects_out_of_domain_position() -> None:
    """Invalid cell locations are rejected rather than being silently clamped."""
    field, _ = _analytical_mode((4, 4))
    fields = SoluteFields(field, _analytical_mode((4, 4))[0])

    with pytest.raises(ValueError, match="within"):
        fields.source_rates_from_cell_exchanges(
            [CellSoluteExchange(1.0, 0.1, 0.0, 0.0)], depth_m=1.0
        )


def test_cell_coordinates_map_bottom_to_last_array_row() -> None:
    """Physical y coordinates agree with top-first diffusion array ordering."""
    field, _ = _analytical_mode((4, 4))

    assert field.cell_index(0.1, 0.1)[0] == 3
    assert field.cell_index(0.1, 0.9)[0] == 0


def test_coupled_field_advance_rolls_back_if_second_solute_fails() -> None:
    """The public two-field update cannot leave a partial carbon mutation."""
    carbon = SoluteField(
        "carbon", (2, 2), 1.0, 1.0, 0.0, 0.0, np.ones((2, 2))
    )
    oxygen = SoluteField(
        "oxygen", (2, 2), 1.0, 1.0, 0.0, 0.0, np.ones((2, 2))
    )
    fields = SoluteFields(carbon, oxygen)
    carbon_before = carbon.concentration_mol_m3.copy()
    oxygen_before = oxygen.concentration_mol_m3.copy()

    with pytest.raises(NegativeConcentrationError):
        fields.advance_with_cell_exchanges(
            1.0,
            [CellSoluteExchange(0.25, 0.25, -0.1, -10.0)],
            depth_m=1.0,
        )

    assert np.array_equal(carbon.concentration_mol_m3, carbon_before)
    assert np.array_equal(oxygen.concentration_mol_m3, oxygen_before)
