# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/measure/node_share_fit.py (X6): labels, the IRLS fit, the
rank AUC and the partial R², on hand-made and synthetic data.

    python -I -B -m unittest discover -s tools/measure -p 'test_*.py'
"""
import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import node_share_fit as nsf  # noqa: E402


def make_trace(bests, scores=None, depth0=1):
    scores = scores or [10] * len(bests)
    return [{'depth': depth0 + i, 'best': b, 'share': 600, 'share_all': 590, 'runner_up': 200,
             'nodes_last_pass': 100, 'nodes_iteration': 120, 'score': s, 'passes': 1, 'root_moves': 20,
             'seldepth': 10} for i, (b, s) in enumerate(zip(bests, scores))]


def synthetic_rows(n, beta, seed):
    """Rows whose label follows a logistic model with coefficients `beta` over the features."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        row = {'game': f'g{i % 200}', 'share': rng.randint(5, 995), 'share_all': 0, 'stability': rng.randint(1, 10),
               'dscore': rng.randint(0, 500), 'depth': rng.randint(8, 20)}
        row['share_all'] = row['share']
        p = nsf.sigmoid(sum(b * v for b, v in zip(beta, nsf.feature_vector(row))))
        row['y'] = int(rng.random() < p)
        rows.append(row)
    return rows


class NodeShareFitTests(unittest.TestCase):
    def test_change_label(self):
        self.assertEqual(nsf.change_label([1, 2, 2], 0), (1, 1))
        self.assertEqual(nsf.change_label([1, 2, 1], 0), (1, 0))  # changes at k+1, back at k+2
        self.assertEqual(nsf.change_label([1, 1, 2], 0), (1, 1))
        self.assertEqual(nsf.change_label([1, 1, 1], 0), (0, 0))
        # The last two iterations are censored; stability counts the run ending at k.
        rows = nsf.iteration_rows([{'game': 'a', 'ply': 0, 'iterations': make_trace([5, 5, 5, 7, 7])}])
        self.assertEqual([r['depth'] for r in rows], [1, 2, 3])
        self.assertEqual([r['y'] for r in rows], [0, 1, 1])
        self.assertEqual([r['stability'] for r in rows], [1, 2, 3])
        # Mate and tablebase scores are left out; so are depths below the floor.
        rows = nsf.iteration_rows([{'game': 'a', 'ply': 0,
                                    'iterations': make_trace([5, 5, 5, 5], [10, 29300, 10, 10])}])
        self.assertEqual([r['depth'] for r in rows], [1])
        rows = nsf.iteration_rows([{'game': 'a', 'ply': 0, 'iterations': make_trace([5] * 12)}], min_depth=8)
        self.assertEqual([r['depth'] for r in rows], [8, 9, 10])

    def test_irls_recovers_coefficients(self):
        beta = [0.5, -0.8, -0.2, 0.3, -0.05]
        rows = synthetic_rows(20000, beta, 7)
        xs, ys = [nsf.feature_vector(r) for r in rows], [r['y'] for r in rows]
        fit = nsf.fit_logistic_irls(xs, ys)
        # The intercept is estimated less tightly (it trades off against depth, 8-20).
        for got, want, delta in zip(fit, beta, (0.35, 0.1, 0.05, 0.1, 0.02)):
            self.assertAlmostEqual(got, want, delta=delta)
        # The maximum-likelihood equations hold at the fit: sum (y - p) x = 0.
        ps = nsf.predict(fit, xs)
        for i in range(len(beta)):
            self.assertAlmostEqual(sum((y - p) * x[i] for x, y, p in zip(xs, ys, ps)), 0.0, delta=1e-3)
        # Gaussian elimination against a hand-solved system.
        x = nsf.solve_linear([[2.0, 1.0], [1.0, 3.0]], [3.0, 5.0])
        self.assertAlmostEqual(x[0], 0.8)
        self.assertAlmostEqual(x[1], 1.4)

    def test_rank_auc(self):
        self.assertEqual(nsf.rank_auc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]), 1.0)
        self.assertEqual(nsf.rank_auc([0.9, 0.8, 0.2, 0.1], [0, 0, 1, 1]), 0.0)
        self.assertEqual(nsf.rank_auc([0.5, 0.5], [0, 1]), 0.5)  # a tie counts half
        rng = random.Random(3)
        scores = [rng.random() for _ in range(4000)]
        labels = [rng.randint(0, 1) for _ in range(4000)]
        self.assertAlmostEqual(nsf.rank_auc(scores, labels), 0.5, delta=0.03)
        self.assertAlmostEqual(nsf.spearman_rho([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertEqual(nsf.rank_values([3, 1, 3]), [2.5, 1.0, 2.5])

    def test_partial_r2_without_signal(self):
        # The label ignores the share: its partial R² is near zero, stability's is not.
        rows = synthetic_rows(8000, [0.2, 0.0, -0.4, 0.0, 0.0], 11)
        self.assertLess(abs(nsf.partial_r2(rows, 'share')), 0.002)
        self.assertGreater(nsf.partial_r2(rows, 'stability'), 0.02)
        lo, hi = nsf.game_bootstrap(rows, lambda s: sum(r['y'] for r in s) / len(s), 50, 1)
        rate = sum(r['y'] for r in rows) / len(rows)
        self.assertLessEqual(lo, rate)
        self.assertGreaterEqual(hi, rate)
        curve = nsf.binned_curve(rows, 'stability', bins=5)
        self.assertEqual(sum(c[2] for c in curve), len(rows))
        self.assertGreater(curve[0][3], curve[-1][3])  # more stability, fewer changes
        self.assertTrue(math.isfinite(nsf.share_logit(0)) and math.isfinite(nsf.share_logit(1000)))


if __name__ == '__main__':
    unittest.main()
