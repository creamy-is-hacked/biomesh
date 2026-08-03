"""Deterministic capsule mechanics and bottom attachment for P1-WP05.

The solver translates the existing :class:`biomesh.cells.Cell` capsules; it
does not define a second cell representation or change cell orientation.
Capsule contact is computed from centreline-segment distance with periodic
horizontal images.  The bottom at ``y = 0 m`` is the sole solid boundary in
P1.  All distances are metres, and every solver control is caller supplied.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from math import isfinite, sqrt
from typing import Literal

from biomesh.cells import Cell

AttachmentMode = Literal["bottom", "none"]
Point = tuple[float, float]


class MechanicsValidationError(ValueError):
    """Raised when mechanics inputs or capsule/domain geometry are invalid."""


class MechanicsConvergenceError(RuntimeError):
    """Raised when the configured iteration limit leaves excessive overlap."""

    def __init__(self, maximum_overlap_m: float, iterations: int) -> None:
        self.maximum_overlap_m = maximum_overlap_m
        self.iterations = iterations
        super().__init__(
            "mechanical solver did not converge after "
            f"{iterations} iterations; maximum unresolved overlap is "
            f"{maximum_overlap_m:.17g} m"
        )


@dataclass(frozen=True, slots=True)
class MechanicsParameters:
    """Caller-provided P1 capsule-contact and attachment controls.

    ``domain_width_m`` and ``maximum_overlap_m`` are SI lengths.  The overlap
    threshold has no approved scientific value and remains
    ``CALIBRATION_REQUIRED`` for scientific runs.
    ``displacement_fraction`` is the fraction of each detected penetration
    corrected per iteration.  No values are defaulted because the domain,
    acceptance threshold, and numerical controls must be selected explicitly.
    """

    domain_width_m: float
    maximum_overlap_m: float
    maximum_iterations: int
    displacement_fraction: float
    attachment_mode: AttachmentMode

    def __post_init__(self) -> None:
        _require_positive("domain_width_m", self.domain_width_m)
        _require_nonnegative("maximum_overlap_m", self.maximum_overlap_m)
        if (
            not isinstance(self.maximum_iterations, int)
            or isinstance(self.maximum_iterations, bool)
            or self.maximum_iterations <= 0
        ):
            raise MechanicsValidationError(
                "maximum_iterations must be a positive integer"
            )
        if (
            not isfinite(self.displacement_fraction)
            or not 0.0 < self.displacement_fraction <= 1.0
        ):
            raise MechanicsValidationError(
                "displacement_fraction must be finite and within (0, 1]"
            )
        if self.attachment_mode not in ("bottom", "none"):
            raise MechanicsValidationError(
                "attachment_mode must be either 'bottom' or 'none'"
            )


@dataclass(frozen=True, slots=True)
class AttachmentResult:
    """Initial cells after configured attachment and their anchored IDs."""

    cells: tuple[Cell, ...]
    attached_cell_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class MechanicsResult:
    """Converged cells and the residual maximum-overlap error metric."""

    cells: tuple[Cell, ...]
    iterations: int
    maximum_overlap_m: float


def attach_initial_cells(
    cells: Sequence[Cell], parameters: MechanicsParameters
) -> AttachmentResult:
    """Apply the configured initial bottom-surface attachment behavior.

    ``bottom`` translates every supplied initial capsule vertically until its
    lowest point is exactly at the solid boundary and records it as attached.
    ``none`` retains vertical positions and records no attachments.  In both
    modes, horizontal centres are mapped into the periodic domain.
    """
    validated = _validate_cells(cells, parameters)
    wrapped = tuple(_wrap_cell(cell, parameters.domain_width_m) for cell in validated)
    if parameters.attachment_mode == "none":
        _validate_solid_boundary(wrapped)
        return AttachmentResult(wrapped, frozenset())

    attached = tuple(_place_on_bottom(cell) for cell in wrapped)
    return AttachmentResult(
        attached,
        frozenset(cell.cell_id for cell in attached),
    )


def relax_cells(
    cells: Sequence[Cell],
    parameters: MechanicsParameters,
    *,
    attached_cell_ids: frozenset[str] = frozenset(),
) -> MechanicsResult:
    """Resolve capsule overlap and the bottom boundary deterministically.

    Attached cells remain tangent to the bottom but may translate
    horizontally.  Other cells are moved upward only when contact resolution
    would place them through the solid boundary.  A result is returned only
    after its maximum overlap is at or below the configured threshold;
    otherwise :class:`MechanicsConvergenceError` reports the residual metric.
    """
    current = list(_validate_cells(cells, parameters))
    known_ids = {cell.cell_id for cell in current}
    unknown_ids = attached_cell_ids - known_ids
    if unknown_ids:
        names = ", ".join(sorted(unknown_ids))
        raise MechanicsValidationError(f"attached cell IDs are not present: {names}")

    current = [
        _enforce_bottom(
            _wrap_cell(cell, parameters.domain_width_m),
            attached=cell.cell_id in attached_cell_ids,
        )
        for cell in current
    ]
    initial_overlap_m = maximum_overlap(current, parameters.domain_width_m)
    if initial_overlap_m <= parameters.maximum_overlap_m:
        return MechanicsResult(tuple(current), 0, initial_overlap_m)

    for iteration in range(1, parameters.maximum_iterations + 1):
        for first_index in range(len(current) - 1):
            for second_index in range(first_index + 1, len(current)):
                first = current[first_index]
                second = current[second_index]
                overlap_m, normal = _pair_overlap_and_normal(
                    first, second, parameters.domain_width_m
                )
                if overlap_m <= parameters.maximum_overlap_m:
                    continue
                correction_m = overlap_m * parameters.displacement_fraction / 2.0
                current[first_index] = _translate(
                    first,
                    -normal[0] * correction_m,
                    -normal[1] * correction_m,
                )
                current[second_index] = _translate(
                    second,
                    normal[0] * correction_m,
                    normal[1] * correction_m,
                )

        current = [
            _enforce_bottom(
                _wrap_cell(cell, parameters.domain_width_m),
                attached=cell.cell_id in attached_cell_ids,
            )
            for cell in current
        ]
        unresolved_overlap_m = maximum_overlap(
            current, parameters.domain_width_m
        )
        if unresolved_overlap_m <= parameters.maximum_overlap_m:
            return MechanicsResult(
                tuple(current), iteration, unresolved_overlap_m
            )

    raise MechanicsConvergenceError(
        maximum_overlap(current, parameters.domain_width_m),
        parameters.maximum_iterations,
    )


def maximum_overlap(cells: Sequence[Cell], domain_width_m: float) -> float:
    """Return the largest capsule penetration depth in metres."""
    _require_positive("domain_width_m", domain_width_m)
    maximum_overlap_m = 0.0
    for first_index in range(len(cells) - 1):
        for second_index in range(first_index + 1, len(cells)):
            overlap_m, _ = _pair_overlap_and_normal(
                cells[first_index], cells[second_index], domain_width_m
            )
            maximum_overlap_m = max(maximum_overlap_m, overlap_m)
    return maximum_overlap_m


def minimum_capsule_y_m(cell: Cell) -> float:
    """Return the capsule's lowest vertical coordinate in metres."""
    endpoints = cell.centreline_endpoints_m
    return min(endpoints[0][1], endpoints[1][1]) - cell.radius_m


def _validate_cells(
    cells: Sequence[Cell], parameters: MechanicsParameters
) -> tuple[Cell, ...]:
    validated = tuple(cells)
    if any(not isinstance(cell, Cell) for cell in validated):
        raise MechanicsValidationError("cells must contain only Cell instances")
    identifiers = [cell.cell_id for cell in validated]
    if len(identifiers) != len(set(identifiers)):
        raise MechanicsValidationError("cell IDs must be unique")
    for cell in validated:
        if cell.capsule_length_m >= parameters.domain_width_m:
            raise MechanicsValidationError(
                f"cell {cell.cell_id} capsule length must be less than "
                "domain_width_m for periodic contact geometry"
            )
    return validated


def _validate_solid_boundary(cells: Sequence[Cell]) -> None:
    crossing = [cell.cell_id for cell in cells if minimum_capsule_y_m(cell) < 0.0]
    if crossing:
        names = ", ".join(crossing)
        raise MechanicsValidationError(
            f"unattached initial cells cross the solid boundary: {names}"
        )


def _place_on_bottom(cell: Cell) -> Cell:
    return _translate(cell, 0.0, -minimum_capsule_y_m(cell))


def _enforce_bottom(cell: Cell, *, attached: bool) -> Cell:
    minimum_y_m = minimum_capsule_y_m(cell)
    if attached or minimum_y_m < 0.0:
        return _translate(cell, 0.0, -minimum_y_m)
    return cell


def _wrap_cell(cell: Cell, domain_width_m: float) -> Cell:
    wrapped_x_m = cell.x_m % domain_width_m
    if wrapped_x_m == cell.x_m:
        return cell
    return replace(cell, x_m=wrapped_x_m)


def _translate(cell: Cell, x_m: float, y_m: float) -> Cell:
    return replace(cell, x_m=cell.x_m + x_m, y_m=cell.y_m + y_m)


def _pair_overlap_and_normal(
    first: Cell, second: Cell, domain_width_m: float
) -> tuple[float, Point]:
    horizontal_delta_m = second.x_m - first.x_m
    nearest_image_delta_m = (
        (horizontal_delta_m + domain_width_m / 2.0) % domain_width_m
        - domain_width_m / 2.0
    )
    nearest_image_shift_m = nearest_image_delta_m - horizontal_delta_m
    first_start, first_end = first.centreline_endpoints_m
    second_start, second_end = second.centreline_endpoints_m
    closest_contact: tuple[float, Point, Point, float] | None = None
    for periodic_offset_m in (0.0, -domain_width_m, domain_width_m):
        second_image_shift_m = nearest_image_shift_m + periodic_offset_m
        shifted_second_start = (
            second_start[0] + second_image_shift_m,
            second_start[1],
        )
        shifted_second_end = (
            second_end[0] + second_image_shift_m,
            second_end[1],
        )
        first_point, second_point = _closest_segment_points(
            first_start,
            first_end,
            shifted_second_start,
            shifted_second_end,
        )
        distance_m = sqrt(
            (second_point[0] - first_point[0]) ** 2
            + (second_point[1] - first_point[1]) ** 2
        )
        if closest_contact is None or distance_m < closest_contact[0]:
            closest_contact = (
                distance_m,
                first_point,
                second_point,
                nearest_image_delta_m + periodic_offset_m,
            )

    if closest_contact is None:  # pragma: no cover - the candidate set is fixed.
        raise AssertionError("periodic contact search produced no candidates")
    distance_m, first_point, second_point, image_delta_m = closest_contact
    difference = (
        second_point[0] - first_point[0],
        second_point[1] - first_point[1],
    )
    overlap_m = max(0.0, first.radius_m + second.radius_m - distance_m)
    if distance_m > 0.0:
        return overlap_m, (difference[0] / distance_m, difference[1] / distance_m)

    centre_difference = (image_delta_m, second.y_m - first.y_m)
    centre_distance_m = sqrt(
        centre_difference[0] ** 2 + centre_difference[1] ** 2
    )
    if centre_distance_m > 0.0:
        return overlap_m, (
            centre_difference[0] / centre_distance_m,
            centre_difference[1] / centre_distance_m,
        )

    # Coincident capsules have no geometric separation normal.  Cell IDs are
    # unique, so their lexical order supplies a stable direction without RNG.
    direction = 1.0 if first.cell_id < second.cell_id else -1.0
    return overlap_m, (direction, 0.0)


def _closest_segment_points(
    first_start: Point,
    first_end: Point,
    second_start: Point,
    second_end: Point,
) -> tuple[Point, Point]:
    """Return closest points on two non-degenerate 2D line segments."""
    first_vector = _subtract(first_end, first_start)
    second_vector = _subtract(second_end, second_start)
    start_difference = _subtract(first_start, second_start)
    first_length_squared = _dot(first_vector, first_vector)
    cross_projection = _dot(first_vector, second_vector)
    second_length_squared = _dot(second_vector, second_vector)
    first_start_projection = _dot(first_vector, start_difference)
    second_start_projection = _dot(second_vector, start_difference)
    denominator = (
        first_length_squared * second_length_squared
        - cross_projection * cross_projection
    )

    first_numerator = 0.0
    first_denominator = denominator
    second_numerator = 0.0
    second_denominator = denominator

    if denominator > 0.0:
        first_numerator = (
            cross_projection * second_start_projection
            - second_length_squared * first_start_projection
        )
        second_numerator = (
            first_length_squared * second_start_projection
            - cross_projection * first_start_projection
        )
        if first_numerator < 0.0:
            first_numerator = 0.0
            second_numerator = second_start_projection
            second_denominator = second_length_squared
        elif first_numerator > first_denominator:
            first_numerator = first_denominator
            second_numerator = second_start_projection + cross_projection
            second_denominator = second_length_squared
    else:
        first_numerator = 0.0
        first_denominator = 1.0
        second_numerator = second_start_projection
        second_denominator = second_length_squared

    if second_numerator < 0.0:
        second_numerator = 0.0
        if -first_start_projection < 0.0:
            first_numerator = 0.0
        elif -first_start_projection > first_length_squared:
            first_numerator = first_denominator
        else:
            first_numerator = -first_start_projection
            first_denominator = first_length_squared
    elif second_numerator > second_denominator:
        second_numerator = second_denominator
        endpoint_projection = -first_start_projection + cross_projection
        if endpoint_projection < 0.0:
            first_numerator = 0.0
        elif endpoint_projection > first_length_squared:
            first_numerator = first_denominator
        else:
            first_numerator = endpoint_projection
            first_denominator = first_length_squared

    first_fraction = first_numerator / first_denominator
    second_fraction = second_numerator / second_denominator
    return (
        _add_scaled(first_start, first_vector, first_fraction),
        _add_scaled(second_start, second_vector, second_fraction),
    )


def _subtract(first: Point, second: Point) -> Point:
    return first[0] - second[0], first[1] - second[1]


def _dot(first: Point, second: Point) -> float:
    return first[0] * second[0] + first[1] * second[1]


def _add_scaled(point: Point, vector: Point, scale: float) -> Point:
    return point[0] + vector[0] * scale, point[1] + vector[1] * scale


def _require_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise MechanicsValidationError(f"{name} must be finite and greater than zero")


def _require_nonnegative(name: str, value: float) -> None:
    if not isfinite(value) or value < 0.0:
        raise MechanicsValidationError(
            f"{name} must be finite and greater than or equal to zero"
        )
