"""P1-WP05 deterministic capsule mechanics and attachment tests."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from biomesh.cells import Cell
from biomesh.mechanics import (
    MechanicsConvergenceError,
    MechanicsParameters,
    MechanicsValidationError,
    attach_initial_cells,
    maximum_overlap,
    minimum_capsule_y_m,
    relax_cells,
)


def _parameters(**changes: object) -> MechanicsParameters:
    values: dict[str, object] = {
        "domain_width_m": 20.0,
        "maximum_overlap_m": 1.0e-10,
        "maximum_iterations": 100,
        "displacement_fraction": 1.0,
        "attachment_mode": "bottom",
    }
    values.update(changes)
    return MechanicsParameters(**values)  # type: ignore[arg-type]


def _cell(
    cell_id: str,
    x_m: float,
    y_m: float,
    *,
    orientation_rad: float = 0.0,
    length_m: float = 2.0,
    radius_m: float = 0.5,
) -> Cell:
    return Cell(
        cell_id=cell_id,
        x_m=x_m,
        y_m=y_m,
        orientation_rad=orientation_rad,
        length_m=length_m,
        radius_m=radius_m,
        dry_biomass_kg=1.0,
        age_s=0.0,
        state="active",
        strain="reference",
    )


def test_collision_relaxation_resolves_overlapping_capsules() -> None:
    cells = (_cell("a", 5.0, 1.0), _cell("b", 5.5, 1.0))
    parameters = _parameters()

    result = relax_cells(cells, parameters)

    assert result.iterations > 0
    assert result.maximum_overlap_m <= parameters.maximum_overlap_m
    assert maximum_overlap(result.cells, parameters.domain_width_m) == pytest.approx(
        result.maximum_overlap_m
    )


def test_mechanics_preserves_valid_existing_cell_records() -> None:
    cells = (
        _cell("a", 5.0, 0.4, orientation_rad=math.pi / 4.0),
        _cell("b", 5.2, 0.5, orientation_rad=3.0 * math.pi / 4.0),
    )

    result = relax_cells(cells, _parameters())

    assert all(cell.length_m > 0.0 and cell.radius_m > 0.0 for cell in result.cells)
    assert all(
        math.isfinite(cell.x_m) and math.isfinite(cell.y_m)
        for cell in result.cells
    )
    assert [cell.cell_id for cell in result.cells] == ["a", "b"]
    assert [cell.orientation_rad for cell in result.cells] == [
        cells[0].orientation_rad,
        cells[1].orientation_rad,
    ]


def test_identical_inputs_replay_identical_mechanics() -> None:
    cells = (
        _cell("a", 5.0, 1.0),
        _cell("b", 5.1, 1.1, orientation_rad=math.pi / 2.0),
        _cell("c", 5.3, 1.0),
    )
    parameters = _parameters(maximum_iterations=300, displacement_fraction=0.75)

    first = relax_cells(cells, parameters)
    second = relax_cells(cells, parameters)

    assert first == second


def test_bottom_attachment_is_configurable() -> None:
    initial = (_cell("a", 3.0, 5.0, orientation_rad=math.pi / 2.0),)

    attached = attach_initial_cells(initial, _parameters(attachment_mode="bottom"))
    unattached = attach_initial_cells(initial, _parameters(attachment_mode="none"))

    assert minimum_capsule_y_m(attached.cells[0]) == pytest.approx(0.0)
    assert attached.attached_cell_ids == frozenset({"a"})
    assert unattached.cells == initial
    assert unattached.attached_cell_ids == frozenset()


def test_attached_cell_remains_on_surface_during_relaxation() -> None:
    parameters = _parameters()
    attachment = attach_initial_cells(
        (_cell("attached", 5.0, 3.0),), parameters
    )
    cells = attachment.cells + (_cell("other", 5.0, 0.8),)

    result = relax_cells(
        cells,
        parameters,
        attached_cell_ids=attachment.attached_cell_ids,
    )

    attached_cell = next(cell for cell in result.cells if cell.cell_id == "attached")
    assert minimum_capsule_y_m(attached_cell) == pytest.approx(0.0)
    assert result.maximum_overlap_m <= parameters.maximum_overlap_m


def test_periodic_side_overlap_is_detected_and_prevented() -> None:
    parameters = _parameters(domain_width_m=10.0)
    cells = (_cell("left", 0.2, 2.0), _cell("right", 9.8, 2.0))

    assert maximum_overlap(cells, parameters.domain_width_m) > 0.0
    result = relax_cells(cells, parameters)

    assert result.maximum_overlap_m <= parameters.maximum_overlap_m
    assert all(0.0 <= cell.x_m < parameters.domain_width_m for cell in result.cells)


def test_solid_boundary_is_enforced_after_mechanics_update() -> None:
    cells = (
        _cell("low", 4.0, 0.1, orientation_rad=math.pi / 2.0),
        _cell("upper", 4.0, 1.0, orientation_rad=math.pi / 2.0),
    )

    result = relax_cells(cells, _parameters())

    assert all(minimum_capsule_y_m(cell) >= 0.0 for cell in result.cells)


def test_unattached_initial_cell_below_solid_boundary_fails_explicitly() -> None:
    cell = _cell("crossing", 2.0, 0.1, orientation_rad=math.pi / 2.0)

    with pytest.raises(MechanicsValidationError, match="solid boundary"):
        attach_initial_cells((cell,), _parameters(attachment_mode="none"))


def test_iteration_limit_reports_unresolved_overlap_metric() -> None:
    cells = (_cell("a", 5.0, 1.0), _cell("b", 5.5, 1.0))
    parameters = _parameters(maximum_iterations=1, displacement_fraction=0.1)

    with pytest.raises(MechanicsConvergenceError) as error:
        relax_cells(cells, parameters)

    assert error.value.iterations == 1
    assert error.value.maximum_overlap_m > parameters.maximum_overlap_m


@pytest.mark.parametrize(
    ("changes", "keyword"),
    [
        ({"domain_width_m": 0.0}, "domain_width_m"),
        ({"maximum_overlap_m": -1.0}, "maximum_overlap_m"),
        ({"maximum_iterations": 0}, "maximum_iterations"),
        ({"displacement_fraction": 0.0}, "displacement_fraction"),
        ({"displacement_fraction": 1.1}, "displacement_fraction"),
        ({"attachment_mode": "adhesive"}, "attachment_mode"),
    ],
)
def test_invalid_mechanics_parameters_fail_explicitly(
    changes: dict[str, object], keyword: str
) -> None:
    with pytest.raises(MechanicsValidationError, match=keyword):
        _parameters(**changes)


def test_duplicate_or_unknown_attached_cell_ids_fail_explicitly() -> None:
    parameters = _parameters()
    duplicate = _cell("same", 2.0, 2.0)
    with pytest.raises(MechanicsValidationError, match="unique"):
        relax_cells((duplicate, replace(duplicate, x_m=4.0)), parameters)

    with pytest.raises(MechanicsValidationError, match="not present"):
        relax_cells((duplicate,), parameters, attached_cell_ids=frozenset({"missing"}))


def test_micrometre_scale_relaxation_is_numerically_stable() -> None:
    parameters = _parameters(
        domain_width_m=20.0e-6,
        maximum_overlap_m=1.0e-15,
        maximum_iterations=200,
        displacement_fraction=0.8,
    )
    cells = (
        _cell("a", 5.0e-6, 1.0e-6, length_m=2.0e-6, radius_m=0.5e-6),
        _cell("b", 5.4e-6, 1.0e-6, length_m=2.0e-6, radius_m=0.5e-6),
    )

    result = relax_cells(cells, parameters)

    assert math.isfinite(result.maximum_overlap_m)
    assert result.maximum_overlap_m <= parameters.maximum_overlap_m
    assert all(minimum_capsule_y_m(cell) >= 0.0 for cell in result.cells)
