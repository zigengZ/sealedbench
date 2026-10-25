"""Wilson score interval and a Wald interval for a difference of proportions."""

from __future__ import annotations

import math

Z95 = 1.959963984540054


def wilson(correct: int, n: int, z: float = Z95) -> tuple[float, float] | tuple[None, None]:
    if n <= 0:
        return (None, None)
    p = correct / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def wald_diff(correct_a: int, n_a: int, correct_b: int, n_b: int, z: float = Z95):
    """Wald 95% interval for p_a - p_b. Returns (gap, lo, hi)."""
    if n_a <= 0 or n_b <= 0:
        return (None, None, None)
    pa = correct_a / n_a
    pb = correct_b / n_b
    gap = pa - pb
    se = math.sqrt(pa * (1.0 - pa) / n_a + pb * (1.0 - pb) / n_b)
    return (gap, gap - z * se, gap + z * se)
