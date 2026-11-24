# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/measure/eval_error.py (B1): each site's error, bound and
call flags, the depth bins, the summaries and the margin sweeps, on
hand-made ledger rows.

    python -I -B -m unittest discover -s tools/measure -p 'test_*.py'
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine_lines as el  # noqa: E402
import eval_error as ee  # noqa: E402


def rfp(depth, excess, arm, fired, mate=0):
    return el.parse_ledger_line(f'prune_ledger rfp|{depth}|5|{excess}|{excess}|{55 * depth}|0|-1|0|10|{fired}|'
                                f'{arm}|100|{mate}')


def futility(depth, deficit, on, off, fired):
    return el.parse_ledger_line(f'prune_ledger futility|{depth}|5|{deficit}|{deficit}|{86 + 50 * depth}|0|-1|0|10|'
                                f'{fired}|{on}|{off}|100|100|0')


def null(depth, excess, null_score, arm):
    return el.parse_ledger_line(f'prune_ledger null|{depth}|5|{excess}|{excess}|1|0|-1|10|{int(null_score >= 0)}|'
                                f'{null_score}|{arm}|100|0')


class ClassifyTest(unittest.TestCase):
    def test_rfp(self):
        # Pruning eval 200 above beta, the search 50 above: error 150, a lower bound, a right prune.
        self.assertEqual(ee.classify(rfp(2, 200, 50, 1)), ('rfp', 2, 150, 'lower', True, False, False, False))
        # Pruned, but the search fails low: a wrong prune, an upper bound.
        self.assertEqual(ee.classify(rfp(2, 200, -30, 1))[3:6], ('upper', True, True))
        # Not pruned, the search fails high: a missed prune.
        self.assertEqual(ee.classify(rfp(3, 40, 10, 0))[4:7], (False, False, True))

    def test_futility(self):
        # alpha = beta - 1; pruning eval = alpha - 300 = beta - 301; off arm 20 below beta: error -281.
        site, depth, error, bound, fired, wrong, missed, _ = ee.classify(futility(1, 300, -20, -20, 1))
        self.assertEqual((site, depth, error, bound, fired, wrong, missed), ('futility', 1, -281, 'upper', True,
                                                                               False, False))
        # On fails low, off fails high: the prune changed the result.
        self.assertTrue(ee.classify(futility(1, 300, -1, 5, 1))[5])
        # Not futile, both arms fail low: a missed prune.
        self.assertTrue(ee.classify(futility(2, 50, -5, -3, 0))[6])
        # Not futile, the off arm fails high: no missed prune.
        self.assertFalse(ee.classify(futility(2, 50, -5, 3, 0))[6])

    def test_null(self):
        self.assertEqual(ee.classify(null(7, 120, 15, -40)), ('null', 7, 160, 'upper', True, True, False, False))
        self.assertEqual(ee.classify(null(4, 10, -60, 25))[4:7], (False, False, True))

    def test_depth_bins(self):
        self.assertEqual([ee.depth_bin('null', d) for d in (3, 7, 8, 9, 11, 12, 30)],
                         ['3', '7-8', '7-8', '9-11', '9-11', '12+', '12+'])
        self.assertEqual(ee.depth_bin('rfp', 4), '4')


class TableTest(unittest.TestCase):
    def test_summary(self):
        s = ee.summary([0, 10, 20, 30, 40])
        self.assertEqual((s['count'], s['mean']), (5, 20))
        self.assertAlmostEqual(s['sd'], 15.811388, places=5)
        self.assertEqual(s['quantiles']['0.5'], 20)
        self.assertEqual(s['quantiles']['0.25'], 10)
        self.assertEqual(ee.summary([])['count'], 0)

    def test_tables(self):
        rows = [rfp(1, 100, 20, 1), rfp(1, 100, -10, 1), rfp(1, 30, 5, 0), rfp(1, 100, 2000, 1, mate=1),
                null(3, 50, 10, 5)]
        errors = ee.error_tables(rows)
        self.assertEqual(errors['rfp']['all']['1']['count'], 3)  # the mate row left out
        self.assertEqual(errors['rfp']['lower']['1']['count'], 2)
        self.assertEqual(errors['rfp']['upper']['1']['mean'], 110)
        calls = ee.call_tables(rows)
        self.assertEqual(calls['rfp']['1'], {'rows': 4, 'mate': 1, 'fired': 3, 'wrong': 1, 'missed': 1})
        self.assertEqual(calls['null']['all']['rows'], 1)

    def test_sweeps(self):
        rows = [rfp(2, 100, -5, 0), rfp(2, 150, 10, 1), rfp(2, 50, 3, 0)]
        sweep = ee.rfp_sweep(rows, (25, 60))
        self.assertEqual(sweep[2][25], (1.0, 1 / 3, 3))  # margin 50: all pruned, one wrong
        self.assertEqual(sweep[2][60], (1 / 3, 0.0, 1))  # margin 120: only the 150 row
        frows = [futility(1, 200, -1, 4, 1), futility(1, 100, -1, -1, 0)]
        fs = ee.futility_sweep(frows, ((86, 50), (40, 10)))
        self.assertEqual(fs[1][(86, 50)], (0.5, 1.0, 1))
        self.assertEqual(fs[1][(40, 10)], (1.0, 0.5, 2))
        table = ee.null_surplus_table([null(3, 50, 10, -5), null(3, 400, -10, 5), null(3, 700, 30, 40)])
        self.assertEqual(table['3'], {'0-99': [1, 1, 1], '301-601': [1, 0, 0], '602+': [1, 1, 0]})


if __name__ == '__main__':
    unittest.main()
