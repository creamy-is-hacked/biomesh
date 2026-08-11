"""Deterministic descriptive statistics for P4-WP02 report data."""

from __future__ import annotations

import math
from collections.abc import Sequence

from scipy.stats import t as student_t  # type: ignore[import-untyped]

CONFIDENCE_LEVEL = 0.95


def sample_uncertainty(
    values: Sequence[float],
) -> tuple[float, float | None, float | None, float | None]:
    """Return mean, sample deviation, and two-sided Student-t interval."""
    mean = math.fsum(values) / len(values)
    if len(values) == 1:
        return mean, None, None, None
    variance = math.fsum((value - mean) ** 2 for value in values) / (len(values) - 1)
    standard_deviation = math.sqrt(max(0.0, variance))
    critical = float(student_t.ppf(0.5 + CONFIDENCE_LEVEL / 2.0, len(values) - 1))
    half_width = critical * standard_deviation / math.sqrt(len(values))
    return mean, standard_deviation, mean - half_width, mean + half_width


def difference_interval(
    left: Sequence[float], right: Sequence[float], difference: float
) -> tuple[float | None, float | None]:
    """Return a two-sided Welch Student-t interval for a mean difference."""
    if len(left) < 2 or len(right) < 2:
        return None, None
    left_mean = math.fsum(left) / len(left)
    right_mean = math.fsum(right) / len(right)
    left_variance = math.fsum((value - left_mean) ** 2 for value in left) / (
        len(left) - 1
    )
    right_variance = math.fsum((value - right_mean) ** 2 for value in right) / (
        len(right) - 1
    )
    left_term = left_variance / len(left)
    right_term = right_variance / len(right)
    standard_error = math.sqrt(left_term + right_term)
    if standard_error == 0.0:
        return difference, difference
    degrees = (left_term + right_term) ** 2 / (
        left_term**2 / (len(left) - 1) + right_term**2 / (len(right) - 1)
    )
    critical = float(student_t.ppf(0.5 + CONFIDENCE_LEVEL / 2.0, degrees))
    half_width = critical * standard_error
    return difference - half_width, difference + half_width


def hedges_g(left: Sequence[float], right: Sequence[float]) -> float | None:
    """Return bias-corrected standardized mean difference when defined."""
    if len(left) < 2 or len(right) < 2:
        return None
    left_mean = math.fsum(left) / len(left)
    right_mean = math.fsum(right) / len(right)
    left_ss = math.fsum((value - left_mean) ** 2 for value in left)
    right_ss = math.fsum((value - right_mean) ** 2 for value in right)
    degrees = len(left) + len(right) - 2
    pooled_variance = (left_ss + right_ss) / degrees
    if pooled_variance == 0.0:
        return None
    correction = 1.0 - 3.0 / (4.0 * degrees - 1.0)
    return correction * (left_mean - right_mean) / math.sqrt(pooled_variance)


def median(values: Sequence[float]) -> float:
    """Return the deterministic median of a nonempty sequence."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0
