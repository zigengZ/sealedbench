"""Wilson and Newcombe intervals used by the v2 pre-registration."""

from __future__ import annotations

import math

Z95 = 1.959963984540054


def wilson(correct: int, n: int, z: float = Z95) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p = correct / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / denom
    return centre - margin, centre + margin


def newcombe(correct_a: int, n_a: int, correct_b: int, n_b: int, z: float = Z95) -> tuple[float | None, float | None, float | None]:
    """Newcombe hybrid score interval for p_a - p_b."""
    if n_a <= 0 or n_b <= 0:
        return None, None, None
    p_a = correct_a / n_a
    p_b = correct_b / n_b
    lo_a, hi_a = wilson(correct_a, n_a, z)
    lo_b, hi_b = wilson(correct_b, n_b, z)
    if None in (lo_a, hi_a, lo_b, hi_b):
        return None, None, None
    diff = p_a - p_b
    low = diff - math.sqrt((p_a - lo_a) ** 2 + (hi_b - p_b) ** 2)
    high = diff + math.sqrt((hi_a - p_a) ** 2 + (p_b - lo_b) ** 2)
    return diff, low, high
