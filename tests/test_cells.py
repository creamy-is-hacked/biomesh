"""P1-WP03 deterministic capsule-cell tests using synthetic SI inputs."""

from __future__ import annotations

import math

import numpy as np
import pytest

from biomesh.cells import (
    Cell,
    CellIdGenerator,
    CellModelParameters,
    CellValidationError,
    divide_if_ready,
)


def _parameters() -> CellModelParameters:
    """Return synthetic, caller-provided SI values for cell-model tests."""
    return CellModelParameters(
        dry_biomass_per_unit_length_kg_m=2.0,
        division_length_m=1.0,
        maximum_daughter_asymmetry_fraction=0.1,
    )


def _cell() -> Cell:
    """Return one valid synthetic parent cell."""
    return Cell(
        cell_id="parent-0001",
        x_m=4.0,
        y_m=3.0,
        orientation_rad=0.0,
        length_m=2.0,
        radius_m=0.25,
        dry_biomass_kg=4.0,
        age_s=12.0,
        state="active",
        strain="reference",
    )


def test_growth_derives_length_from_explicit_biomass_mapping() -> None:
    """Length changes solely according to the caller-provided SI mapping."""
    parent = _cell()

    grown = parent.with_dry_biomass(6.0, dry_biomass_per_unit_length_kg_m=2.0)

    assert grown.dry_biomass_kg == 6.0
    assert grown.length_m == 3.0
    assert parent.length_m == 2.0


def test_division_conserves_biomass_and_persists_lineage() -> None:
    """Daughters retain parent lineage and conserve its dry biomass."""
    parent = _cell()
    result = divide_if_ready(
        parent,
        _parameters(),
        np.random.default_rng(8),
        CellIdGenerator(),
    )

    assert result is not None
    daughters = (result.first_daughter, result.second_daughter)
    assert sum(daughter.dry_biomass_kg for daughter in daughters) == pytest.approx(
        parent.dry_biomass_kg
    )
    assert [daughter.cell_id for daughter in daughters] == [
        "cell-000000000000",
        "cell-000000000001",
    ]
    assert all(daughter.parent_id == parent.cell_id for daughter in daughters)
    assert all(daughter.age_s == 0.0 for daughter in daughters)
    assert all(daughter.state == parent.state for daughter in daughters)
    assert all(daughter.strain == parent.strain for daughter in daughters)


def test_fixed_seed_reproduces_identical_division_lineage() -> None:
    """The same seed and ID sequence replay identical daughter cell records."""
    first = divide_if_ready(
        _cell(), _parameters(), np.random.default_rng(42), CellIdGenerator(20)
    )
    second = divide_if_ready(
        _cell(), _parameters(), np.random.default_rng(42), CellIdGenerator(20)
    )

    assert first == second


def test_division_preserves_valid_tangent_capsule_geometry() -> None:
    """Daughter capsules have valid axes and tangent, non-overlapping extents."""
    result = divide_if_ready(
        _cell(),
        _parameters(),
        np.random.default_rng(3),
        CellIdGenerator(),
    )

    assert result is not None
    first, second = result.first_daughter, result.second_daughter
    assert first.length_m > 0.0
    assert second.length_m > 0.0
    assert first.radius_m == second.radius_m
    assert all(
        math.isfinite(value)
        for point in first.centreline_endpoints_m
        for value in point
    )
    assert all(
        math.isfinite(value)
        for point in second.centreline_endpoints_m
        for value in point
    )
    centre_distance_m = math.dist((first.x_m, first.y_m), (second.x_m, second.y_m))
    required_distance_m = (
        (first.length_m + second.length_m) / 2.0 + first.radius_m + second.radius_m
    )
    assert centre_distance_m == pytest.approx(required_distance_m)


def test_threshold_cell_does_not_divide() -> None:
    """The threshold is strict: a cell must be longer than it to divide."""
    threshold_cell = _cell().with_dry_biomass(
        2.0, dry_biomass_per_unit_length_kg_m=2.0
    )

    result = divide_if_ready(
        threshold_cell,
        _parameters(),
        np.random.default_rng(1),
        CellIdGenerator(),
    )

    assert result is None


@pytest.mark.parametrize(
    ("keyword", "cell_kwargs"),
    [
        ("orientation_rad", {"orientation_rad": 2.0 * math.pi}),
        ("length_m", {"length_m": 0.0}),
        ("state", {"state": "  "}),
    ],
)
def test_invalid_cell_state_fails_explicitly(
    keyword: str, cell_kwargs: dict[str, float | str]
) -> None:
    """Invalid geometry and labels are rejected instead of corrected."""
    values: dict[str, float | str | None] = {
        "cell_id": "parent-0001",
        "x_m": 4.0,
        "y_m": 3.0,
        "orientation_rad": 0.0,
        "length_m": 2.0,
        "radius_m": 0.25,
        "dry_biomass_kg": 4.0,
        "age_s": 12.0,
        "state": "active",
        "strain": "reference",
        "parent_id": None,
    }
    values.update(cell_kwargs)

    with pytest.raises(CellValidationError, match=keyword):
        Cell(**values)  # type: ignore[arg-type]
