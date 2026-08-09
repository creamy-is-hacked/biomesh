"""P2-WP01 quorum production, transport, sensing, and replay verification."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest
from numpy.typing import NDArray

from biomesh.cells import Cell
from biomesh.outputs import MassBalanceEntry, RunMetadata, SimulationOutputWriter
from biomesh.quorum import (
    QuorumSignalParameters,
    QuorumValidationError,
    advance_quorum_signal,
    hill_activation,
    initialize_quorum_states,
    maximum_stable_timestep_s,
)
from biomesh.solutes import DiffusionStabilityError, SoluteField, SoluteFields


def _cell(cell_id: str, x_m: float, y_m: float) -> Cell:
    return Cell(
        cell_id=cell_id,
        x_m=x_m,
        y_m=y_m,
        orientation_rad=0.0,
        length_m=0.1,
        radius_m=0.01,
        dry_biomass_kg=1.0,
        age_s=0.0,
        state="active",
        strain="synthetic-validation",
    )


def _signal_field(
    concentration_mol_m3: NDArray[np.float64],
    *,
    width_m: float = 1.0,
    height_m: float = 1.0,
    diffusivity_m2_s: float = 0.0,
    top_bulk_concentration_mol_m3: float = 0.0,
) -> SoluteField:
    return SoluteField(
        name="quorum_signal",
        shape=concentration_mol_m3.shape,
        width_m=width_m,
        height_m=height_m,
        diffusivity_m2_s=diffusivity_m2_s,
        top_bulk_concentration_mol_m3=top_bulk_concentration_mol_m3,
        concentration_mol_m3=concentration_mol_m3,
    )


def _parameters(
    *,
    degradation_rate_s: float = 0.0,
    basal_production_rate_mol_s: float = 0.0,
    induced_production_rate_mol_s: float = 0.0,
    activation_half_saturation_mol_m3: float = 1.0,
    hill_coefficient: float = 2.0,
) -> QuorumSignalParameters:
    return QuorumSignalParameters(
        degradation_rate_s=degradation_rate_s,
        basal_production_rate_mol_s=basal_production_rate_mol_s,
        induced_production_rate_mol_s=induced_production_rate_mol_s,
        activation_half_saturation_mol_m3=(
            activation_half_saturation_mol_m3
        ),
        hill_coefficient=hill_coefficient,
    )


def test_basal_and_induced_production_use_cell_local_activation() -> None:
    """Each cell emits basal plus Hill-scaled induced whole-cell production."""
    field = _signal_field(np.full((2, 2), 2.0, dtype=np.float64))
    cells = (_cell("cell-b", 0.75, 0.25), _cell("cell-a", 0.25, 0.25))
    parameters = _parameters(
        basal_production_rate_mol_s=0.1,
        induced_production_rate_mol_s=0.3,
        activation_half_saturation_mol_m3=2.0,
    )

    result = advance_quorum_signal(
        cells=cells,
        signal_field=field,
        parameters=parameters,
        time_step_s=0.1,
        depth_m=1.0,
        start_time_s=0.0,
    )

    assert [record.cell_id for record in result.cell_production] == [
        "cell-a",
        "cell-b",
    ]
    assert [record.production_rate_mol_s for record in result.cell_production] == [
        pytest.approx(0.25),
        pytest.approx(0.25),
    ]
    assert field.concentration_mol_m3[-1, :].tolist() == pytest.approx([2.1, 2.1])
    assert result.mass_balance.produced_signal_mol == pytest.approx(0.05)
    assert abs(result.mass_balance.residual_signal_mol) < 1.0e-15
    assert all(len(state.history) == 2 for state in result.cell_states)
    assert all(state.current.time_s == 0.1 for state in result.cell_states)


def test_diffusion_decay_matches_manufactured_analytical_mode() -> None:
    """The reused finite-volume field resolves a diffusion-decay eigenmode."""
    rows, columns = 48, 8
    height_m = 1.0
    diffusivity_m2_s = 0.05
    degradation_rate_s = 0.2
    y_from_top_m = (np.arange(rows) + 0.5) * height_m / rows
    initial_profile = np.sin(np.pi * y_from_top_m / (2.0 * height_m))
    initial = np.repeat(initial_profile[:, None], columns, axis=1)
    field = _signal_field(
        initial,
        diffusivity_m2_s=diffusivity_m2_s,
    )
    parameters = _parameters(degradation_rate_s=degradation_rate_s)
    final_time_s = 0.01
    time_step_s = min(
        1.0e-5,
        maximum_stable_timestep_s(field, degradation_rate_s) / 4.0,
    )
    step_count = round(final_time_s / time_step_s)
    time_step_s = final_time_s / step_count

    for step_index in range(step_count):
        advance_quorum_signal(
            cells=(),
            signal_field=field,
            parameters=parameters,
            time_step_s=time_step_s,
            depth_m=1.0,
            start_time_s=step_index * time_step_s,
        )

    decay = np.exp(
        -(
            diffusivity_m2_s * (np.pi / (2.0 * height_m)) ** 2
            + degradation_rate_s
        )
        * final_time_s
    )
    expected = np.repeat((initial_profile * decay)[:, None], columns, axis=1)
    assert np.max(np.abs(field.concentration_mol_m3 - expected)) < 2.0e-5


@pytest.mark.parametrize("multiple", [0.0, 0.5, 1.0, 2.0, 10.0])
def test_uniform_concentration_reproduces_hill_curve(multiple: float) -> None:
    """Cell-local activation equals the analytical Hill response everywhere."""
    half_saturation = 3.0
    concentration = multiple * half_saturation
    parameters = _parameters(
        activation_half_saturation_mol_m3=half_saturation,
        hill_coefficient=2.5,
    )
    field = _signal_field(
        np.full((2, 2), concentration, dtype=np.float64),
    )
    cells = (_cell("cell-a", 0.25, 0.25), _cell("cell-b", 0.75, 0.75))

    states = initialize_quorum_states(
        cells=cells,
        signal_field=field,
        parameters=parameters,
        time_s=0.0,
    )

    expected = 0.0 if multiple == 0.0 else multiple**2.5 / (1.0 + multiple**2.5)
    assert all(
        state.current.activation_fraction == pytest.approx(expected)
        for state in states
    )


def test_geometry_changes_activation_with_equal_cell_counts() -> None:
    """Local placement changes activation when population count is unchanged."""
    parameters = _parameters(
        basal_production_rate_mol_s=1.0,
        activation_half_saturation_mol_m3=4.0,
        hill_coefficient=1.0,
    )

    def two_steps(cells: tuple[Cell, Cell]) -> float:
        field = _signal_field(
            np.zeros((2, 4), dtype=np.float64),
            width_m=2.0,
            diffusivity_m2_s=0.01,
        )
        states = None
        for step_index in range(2):
            result = advance_quorum_signal(
                cells=cells,
                signal_field=field,
                parameters=parameters,
                time_step_s=1.0,
                depth_m=1.0,
                start_time_s=float(step_index),
                cell_states=states,
            )
            states = result.cell_states
        return sum(state.current.activation_fraction for state in states) / len(states)

    clustered_activation = two_steps(
        (_cell("cell-a", 0.10, 0.25), _cell("cell-b", 0.20, 0.25))
    )
    separated_activation = two_steps(
        (_cell("cell-a", 0.10, 0.25), _cell("cell-b", 1.10, 0.25))
    )

    assert clustered_activation > separated_activation


def test_degradation_and_discrete_signal_balance() -> None:
    """First-order loss is explicit and the closed-field ledger reconciles."""
    field = _signal_field(np.full((2, 2), 5.0, dtype=np.float64))
    result = advance_quorum_signal(
        cells=(),
        signal_field=field,
        parameters=_parameters(degradation_rate_s=0.2),
        time_step_s=1.0,
        depth_m=2.0,
        start_time_s=0.0,
    )

    assert np.array_equal(field.concentration_mol_m3, np.full((2, 2), 4.0))
    assert result.mass_balance.degraded_signal_mol == pytest.approx(2.0)
    assert result.mass_balance.boundary_input_signal_mol == 0.0
    assert abs(result.mass_balance.residual_signal_mol) < 1.0e-15


def test_transport_boundary_is_included_in_signal_balance() -> None:
    """Open-top transfer reconciles while periodic and bottom fluxes cancel."""
    field = _signal_field(
        np.ones((2, 2), dtype=np.float64),
        diffusivity_m2_s=0.1,
        top_bulk_concentration_mol_m3=2.0,
    )
    time_step_s = maximum_stable_timestep_s(field, 0.0) / 2.0

    result = advance_quorum_signal(
        cells=(),
        signal_field=field,
        parameters=_parameters(),
        time_step_s=time_step_s,
        depth_m=3.0,
        start_time_s=0.0,
    )

    assert result.mass_balance.boundary_input_signal_mol > 0.0
    assert abs(result.mass_balance.residual_signal_mol) < 1.0e-15


def _metadata() -> RunMetadata:
    return RunMetadata(
        seed=7,
        parameters={"purpose": "synthetic P2-WP01 replay"},
        package_version="0.0.0",
        commit_hash="test",
        dependency_versions={"numpy": "test"},
        parameter_file="synthetic.toml",
        parameter_file_sha256="0" * 64,
        platform="test",
        python_version="3.14.test",
    )


def _base_fields() -> SoluteFields:
    return SoluteFields(
        carbon=SoluteField("carbon", (2, 2), 1.0, 1.0, 0.0, 0.0, np.zeros((2, 2))),
        oxygen=SoluteField("oxygen", (2, 2), 1.0, 1.0, 0.0, 0.0, np.zeros((2, 2))),
    )


def _write_quorum_replay(run_directory: Path) -> Path:
    cells = (_cell("cell-a", 0.25, 0.25),)
    field = _signal_field(np.zeros((2, 2), dtype=np.float64))
    parameters = _parameters(
        degradation_rate_s=0.1,
        basal_production_rate_mol_s=0.2,
        induced_production_rate_mol_s=0.3,
    )
    states = initialize_quorum_states(
        cells=cells,
        signal_field=field,
        parameters=parameters,
        time_s=0.0,
    )
    writer = SimulationOutputWriter(run_directory, _metadata())
    writer.write_snapshot(
        time_s=0.0,
        cells=cells,
        solute_fields=_base_fields(),
        division_events=(),
        mass_balance_entries=(
            MassBalanceEntry(
                quantity="quorum_signal",
                unit="mol",
                initial_amount=0.0,
                final_amount=0.0,
                net_input_amount=0.0,
                absolute_tolerance=0.0,
                relative_tolerance=0.0,
            ),
        ),
        quorum_signal_field=field,
        quorum_states=states,
    )
    result = None
    for step_index in range(10):
        result = advance_quorum_signal(
            cells=cells,
            signal_field=field,
            parameters=parameters,
            time_step_s=0.1,
            depth_m=1.0,
            start_time_s=step_index * 0.1,
            cell_states=states,
        )
        states = result.cell_states
        balance = result.mass_balance
        writer.write_snapshot(
            time_s=states[0].current.time_s,
            cells=cells,
            solute_fields=_base_fields(),
            division_events=(),
            mass_balance_entries=(
                MassBalanceEntry(
                    quantity="quorum_signal",
                    unit="mol",
                    initial_amount=balance.initial_signal_mol,
                    final_amount=balance.final_signal_mol,
                    net_input_amount=(
                        balance.produced_signal_mol
                        - balance.degraded_signal_mol
                        + balance.boundary_input_signal_mol
                    ),
                    absolute_tolerance=1.0e-12,
                    relative_tolerance=1.0e-12,
                ),
            ),
            quorum_signal_field=field,
            quorum_states=states,
        )
    assert result is not None
    paths = writer.finalize()
    assert paths.quorum_history_table is not None
    history = pq.read_table(paths.quorum_history_table).to_pydict()
    assert history["cell_id"] == ["cell-a"] * 11
    assert history["time_s"] == pytest.approx(
        [step_index * 0.1 for step_index in range(11)]
    )
    with np.load(paths.field_files[-1], allow_pickle=False) as archive:
        assert np.array_equal(
            archive["quorum_signal_concentration_mol_m3"],
            field.concentration_mol_m3,
        )
    return paths.run_directory


def test_deterministic_replay_includes_signal_and_activation_outputs(
    tmp_path: Path,
) -> None:
    """Identical inputs reproduce histories, fields, and bytes exactly."""
    first = _write_quorum_replay(tmp_path / "first")
    second = _write_quorum_replay(tmp_path / "second")
    relative_files = sorted(
        path.relative_to(first) for path in first.rglob("*") if path.is_file()
    )

    assert relative_files == sorted(
        path.relative_to(second) for path in second.rglob("*") if path.is_file()
    )
    assert all(
        (first / path).read_bytes() == (second / path).read_bytes()
        for path in relative_files
    )


def test_parameter_and_step_validation_fail_explicitly() -> None:
    """Nonphysical values and unstable updates are rejected before mutation."""
    with pytest.raises(QuorumValidationError, match="degradation_rate_s"):
        _parameters(degradation_rate_s=-1.0)
    with pytest.raises(QuorumValidationError, match="half_saturation"):
        _parameters(activation_half_saturation_mol_m3=0.0)
    with pytest.raises(QuorumValidationError, match="hill_coefficient"):
        _parameters(hill_coefficient=float("nan"))
    with pytest.raises(QuorumValidationError, match="greater than or equal"):
        hill_activation(-1.0, 1.0, 1.0)

    field = _signal_field(
        np.ones((2, 2), dtype=np.float64),
        diffusivity_m2_s=1.0,
    )
    before = field.concentration_mol_m3.copy()
    limit = maximum_stable_timestep_s(field, 1.0)
    with pytest.raises(DiffusionStabilityError, match="stability limit"):
        advance_quorum_signal(
            cells=(),
            signal_field=field,
            parameters=_parameters(degradation_rate_s=1.0),
            time_step_s=limit * 1.01,
            depth_m=1.0,
            start_time_s=0.0,
        )
    assert np.array_equal(field.concentration_mol_m3, before)


def test_stale_cell_state_is_rejected_instead_of_silently_corrected() -> None:
    """History must match current geometry, field, parameters, and time."""
    cell = _cell("cell-a", 0.25, 0.25)
    field = _signal_field(np.ones((2, 2), dtype=np.float64))
    parameters = _parameters()
    states = initialize_quorum_states(
        cells=(cell,), signal_field=field, parameters=parameters, time_s=0.0
    )
    field.concentration_mol_m3[-1, 0] = 2.0

    with pytest.raises(QuorumValidationError, match="does not match"):
        advance_quorum_signal(
            cells=(cell,),
            signal_field=field,
            parameters=parameters,
            time_step_s=0.1,
            depth_m=1.0,
            start_time_s=0.0,
            cell_states=states,
        )
