# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/measure/prune_ledger_fit.py (X10): the wrong flag, the
rate tables and the probit-with-floor fit on synthetic rows.

    python -I -B -m unittest discover -s tools/measure -p 'test_*.py'
"""
import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prune_ledger_fit as plf  # noqa: E402


def synthetic_ledger(n, theta, seed, depth=3, margin=240):
    """RFP rows whose wrong flag follows I1's model with parameters `theta`."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        gap = rng.randint(0, 600)
        wrong = rng.random() < plf.probit_floor_probability(gap, theta)
        rows.append({'technique': 'rfp', 'game': f'g{i % 100}', 'depth': depth, 'margin': margin, 'gap': gap,
                     'fired': int(gap >= margin), 'wrong': int(wrong)})
    return rows


class PruneLedgerFitTests(unittest.TestCase):
    def test_wrong_flag(self):
        self.assertEqual(plf.wrong_flag({'technique': 'rfp', 'arm_minus_beta': -1}), 1)
        self.assertEqual(plf.wrong_flag({'technique': 'rfp', 'arm_minus_beta': 0}), 0)  # fails high: the prune held
        fut = {'technique': 'futility'}
        self.assertEqual(plf.wrong_flag(dict(fut, on_minus_beta=-5, off_minus_beta=0)), 1)
        self.assertEqual(plf.wrong_flag(dict(fut, on_minus_beta=-5, off_minus_beta=-1)), 0)  # both fail low
        self.assertEqual(plf.wrong_flag(dict(fut, on_minus_beta=3, off_minus_beta=7)), 0)  # both fail high
        rows = plf.ledger_rows([{'game': 'a', 'ledger': [
            {'technique': 'rfp', 'excess': 90, 'arm_minus_beta': -3, 'depth': 1},
            {'technique': 'futility', 'deficit': 200, 'on_minus_beta': -1, 'off_minus_beta': 4, 'depth': 2}]}])
        self.assertEqual([(r['gap'], r['wrong'], r['game']) for r in rows], [(90, 1, 'a'), (200, 1, 'a')])

    def test_weighted_rates(self):
        rows = [{'technique': 'rfp', 'depth': 2, 'margin': 160, 'gap': g, 'fired': int(g >= 160), 'wrong': w}
                for g, w in ((5, 1), (15, 1), (25, 0), (165, 0), (170, 1), (175, 0), (300, 0))]
        rows.append({'technique': 'futility', 'depth': 2, 'margin': 240, 'gap': 10, 'fired': 0, 'wrong': 1})
        table = plf.weighted_rate_table(rows, 'rfp', every=32)
        e = table[2]
        self.assertEqual((e['rows'], e['fired'], e['wrong'], e['weight']), (7, 4, 3, 224))
        self.assertEqual(e['bins'][0], [2, 2])
        self.assertEqual(e['bins'][160], [3, 1])
        rate, n, k = plf.marginal_rate_at_margin(e)
        self.assertAlmostEqual(rate, 1 / 3)
        self.assertEqual((n, k), (3, 1))

    def test_probit_floor_recovery(self):
        theta = (-60.0, math.log(70.0), -3.5, math.log(150.0))
        rows = synthetic_ledger(40000, theta, 5)
        fit, _ = plf.fit_probit_floor(rows)
        self.assertAlmostEqual(math.exp(fit[1]), 70.0, delta=20.0)  # sigma
        self.assertAlmostEqual(fit[0], -60.0, delta=25.0)  # mu
        # The fitted probability tracks the true one across the gaps.
        for g in (0, 100, 240, 400):
            self.assertAlmostEqual(plf.probit_floor_probability(g, fit), plf.probit_floor_probability(g, theta),
                                   delta=0.02)
        # Nelder-Mead on a known quadratic.
        best, value = plf.nelder_mead_min(lambda p: (p[0] - 3) ** 2 + (p[1] + 1) ** 2, [0.0, 0.0])
        self.assertAlmostEqual(best[0], 3.0, delta=1e-3)
        self.assertAlmostEqual(best[1], -1.0, delta=1e-3)
        self.assertAlmostEqual(plf.normal_cdf(0.0), 0.5)
        # Extreme parameters (the simplex can wander there) neither overflow nor break the bounds:
        # the first real fit hit an overflow at logit pi below -709.
        for logit_pi in (-1000.0, 1000.0):
            p = plf.probit_floor_probability(50, (-60.0, math.log(70.0), logit_pi, math.log(150.0)))
            self.assertTrue(0 < p < 1)
        self.assertEqual(plf.negative_log_likelihood((0.0, 0.0, -1000.0, 0.0), [(5.0, 10, 1)]), float('inf'))
        lo, hi = plf.bootstrap_fit(rows, 50, 1, lambda s: sum(r['wrong'] for r in s) / len(s))
        rate = sum(r['wrong'] for r in rows) / len(rows)
        self.assertLessEqual(lo, rate)
        self.assertGreaterEqual(hi, rate)


if __name__ == '__main__':
    unittest.main()
