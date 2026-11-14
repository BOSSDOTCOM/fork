# SPDX-License-Identifier: GPL-3.0-or-later
"""Pentanomial statistics for the display, the same model as Fork's SPRT driver (tools/cloud/sprt_merge.py:
pair scores 0, 1/4, 1/2, 3/4, 1 over game pairs; logistic Elo; normalized Elo; 95% intervals). Kept here so
the display has no import from the tools it watches. tests check these against the driver's printed lines."""
import math

PAIR_SCORES = (0.0, 0.25, 0.5, 0.75, 1.0)
NELO_SCALE = 800 / (math.log(10) * math.sqrt(2))


def moments(ptnml):
    n = sum(ptnml)
    if n == 0:
        return 0, 0.5, 0.0
    mean = sum(c * s for c, s in zip(ptnml, PAIR_SCORES)) / n
    var = sum(c * (s - mean) ** 2 for c, s in zip(ptnml, PAIR_SCORES)) / n
    return n, mean, var


def elo(mean):
    if mean <= 0 or mean >= 1:
        return math.copysign(float('inf'), mean - 0.5)
    return -400 * math.log10(1 / mean - 1)


def summary(ptnml):
    """{pairs, games, elo, elo_err, nelo, nelo_err} for a pentanomial count; errors are 95% half-widths.
    None when there are no pairs. Infinite values (a one-sided score) come back as None."""
    n, mean, var = moments(ptnml)
    if n == 0:
        return None
    se = math.sqrt(var / n)
    half = (elo(mean + 1.96 * se) - elo(mean - 1.96 * se)) / 2
    nelo = (mean - 0.5) / math.sqrt(var) * NELO_SCALE if var > 0 else 0.0
    fin = lambda v: round(v, 2) if math.isfinite(v) else None  # noqa: E731
    return {'pairs': n, 'games': 2 * n, 'elo': fin(elo(mean)), 'elo_err': fin(half),
            'nelo': fin(nelo), 'nelo_err': fin(1.96 * NELO_SCALE / math.sqrt(n))}


def llr(ptnml, nelo0, nelo1):
    n, mean, var = moments(ptnml)
    if n == 0 or var == 0:
        return 0.0
    sd = math.sqrt(var)
    m0 = 0.5 + nelo0 / NELO_SCALE * sd
    m1 = 0.5 + nelo1 / NELO_SCALE * sd
    return n / (2 * var) * ((mean - m0) ** 2 - (mean - m1) ** 2)


def add(ptnmls):
    """The element-wise sum of pentanomial counts (shards of a stage, stages of a test)."""
    total = [0, 0, 0, 0, 0]
    for p in ptnmls:
        if isinstance(p, (list, tuple)) and len(p) == 5 and all(isinstance(c, int) and c >= 0 for c in p):
            total = [a + b for a, b in zip(total, p)]
    return total
