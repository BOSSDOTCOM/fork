# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/gauntlet/stopbias.py: its stage limits are sprt_merge's verdicts, its exact outcome
distribution agrees with an independent Monte Carlo of the staged test and with the bug review's simulated power
table, the lattice is fine enough, and the median-unbiased estimate has its defining properties.

    python3 -m unittest discover -s tools/gauntlet -p 'test_*.py'
"""
import math
import random
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'cloud'))

import sprt_merge as sm  # noqa: E402
import stopbias as sb  # noqa: E402

R = sb.DESIGNS['search-stc']
NET = sb.DESIGNS['network-stc']


def monte_carlo(d, theta, trials, seed):
    """The staged test played out directly: Gaussian stage estimates, sprt_merge.stage_decision's order."""
    rng = random.Random(seed)
    s = sb.C / math.sqrt(d['pairs'])
    counts = {'H1': 0, 'H0': 0, 'futility': 0, 'capped': 0}
    passed = 0.0
    for _ in range(trials):
        w = 0.0
        for k in range(1, d['cap'] + 1):
            w += rng.gauss(theta, s)
            x = w / k
            lo, up = sb.limits(d, k)
            if x >= up:
                counts['H1'] += 1
                passed += x
                break
            if x <= lo:
                counts['H0'] += 1
                break
            if d['futility'] == k and x < 0:
                counts['futility'] += 1
                break
            if k == d['cap']:
                counts['capped'] += 1
    return {k: v / trials for k, v in counts.items()}, passed / counts['H1'] - theta


class Limits(unittest.TestCase):
    def test_limits_are_sprt_merges_verdicts(self):
        # Pentanomial counts of 800 k pairs around each limit: sprt_merge's verdict flips where the limit says.
        rng = random.Random(3)
        for d, alpha, beta in ((R, 0.05, 0.20), (NET, 0.05, 0.05)):
            for k in (1, 2, 5):
                lo, up = sb.limits(d, k)
                for _ in range(200):
                    n = 800 * k
                    p = [rng.random() for _ in range(5)]
                    ptnml = [int(n * v / sum(p)) for v in p]
                    ptnml[2] += n - sum(ptnml)
                    x = sm.nelo(ptnml)
                    _, verdict = sm.verdict(ptnml, d['e0'], d['e1'], alpha, beta)
                    if abs(x - up) > 1e-6 and abs(x - lo) > 1e-6:
                        want = 'H1 accepted' if x > up else 'H0 accepted' if x < lo else 'continue'
                        self.assertEqual(verdict, want, (k, ptnml, x, lo, up))

    def test_design_r_futility_error(self):
        # sprt_merge's docstring: the estimate's error after 2 stages of 1,600 games is 6.14 nElo.
        self.assertAlmostEqual(sb.C / math.sqrt(2 * R['pairs']), 6.14, places=2)


class Distribution(unittest.TestCase):
    def test_exact_agrees_with_monte_carlo(self):
        for d, theta in ((R, 6.0), (NET, 3.0)):
            exact = sb.outcome_probabilities(d, theta)
            mc, mc_bias = monte_carlo(d, theta, 20000, 11)
            for k in exact:
                self.assertAlmostEqual(exact[k], mc[k], delta=0.012, msg=(theta, k))
            self.assertAlmostEqual(sb.pass_bias(d, theta), mc_bias, delta=0.35)
            self.assertAlmostEqual(sum(exact.values()), 1.0, delta=1e-6)

    def test_bug_reviews_power_table(self):
        # docs/research/bug-review-2026-11-11.md, "Design R power (simulation, 40,000 trials per point)":
        # search STC at 0: passes 1.6%, H0 38%, futility 36%, capped 24%; at 9: 72%, 1%, 7%, 20%;
        # network STC at 6: 58%, 0.5%, none, 41%; pass bias +7.6, +5.1, +3.2 nElo at 3, 6, 9 (its section 4, T4).
        for d, theta, want in ((R, 0.0, (0.016, 0.38, 0.36, 0.24)), (R, 9.0, (0.72, 0.01, 0.07, 0.20)),
                               (NET, 6.0, (0.58, 0.005, 0.0, 0.41))):
            got = sb.outcome_probabilities(d, theta)
            for k, v in zip(('H1', 'H0', 'futility', 'capped'), want):
                self.assertAlmostEqual(got[k], v, delta=0.01, msg=(theta, k))
        for theta, bias in ((3.0, 7.6), (6.0, 5.1), (9.0, 3.2)):
            self.assertAlmostEqual(sb.pass_bias(R, theta), bias, delta=0.15)

    def test_lattice_spacing(self):
        coarse = sb.walk(R, 6.0, 4)[0]
        fine = sb.walk(R, 6.0, 4, h=0.125)[0]
        for a, b in zip(coarse, fine):
            self.assertAlmostEqual(a[0], b[0], delta=1e-3)
            self.assertAlmostEqual(a[1], b[1], delta=0.05)


class MedianUnbiased(unittest.TestCase):
    def test_stage_one_is_the_estimate(self):
        # At the first stage every H1 with a larger estimate is more extreme: the tail is P(x_1 >= x).
        self.assertAlmostEqual(sb.median_unbiased(R, 1, 64.91), 64.91, delta=0.02)
        self.assertAlmostEqual(sb.median_unbiased(NET, 1, 53.37), 53.37, delta=0.02)

    def test_tail_is_one_half_and_monotone(self):
        m = sb.median_unbiased(R, 4, 13.04)
        self.assertAlmostEqual(sb._upper_tail(R, 4, 13.04, m), 0.5, delta=2e-3)
        self.assertLess(m, 13.04)
        self.assertLess(sb.median_unbiased(R, 4, 12.5), m)
        self.assertLess(sb.median_unbiased(R, 5, 13.04), m)

    def test_not_a_pass_is_refused(self):
        with self.assertRaises(ValueError):
            sb.median_unbiased(R, 4, 10.0)  # below stage 4's H1 limit (11.71)
        with self.assertRaises(ValueError):
            sb.median_unbiased(R, 9, 30.0)  # beyond design R's cap

    def test_adjust(self):
        self.assertIsNone(sb.adjust({'change': 'speed', 'elo': 6.0, 'ci95': 1.1}))
        m, s = sb.adjust({'change': 'x', 'elo': 7.49, 'sprt': {'design': 'search-stc', 'stages': 4, 'nelo': 13.04}})
        self.assertLess(s, m)
        self.assertLess(m, 7.49)


if __name__ == '__main__':
    unittest.main()
