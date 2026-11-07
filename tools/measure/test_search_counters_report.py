# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/measure/search_counters_report.py (X1 and X2).

    python -I -B -m unittest discover -s tools/measure -p 'test_*.py'
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import search_counters_report as scr  # noqa: E402


class SearchCountersReportTests(unittest.TestCase):
    def test_x1_ratios(self):
        # Hand-computed: 10 root + 290 main + 700 quiescence = 1,000 nodes;
        # 150 + 500 + 0 evaluations; TT hits 50 of 200 main lookups.
        c = {'root_nodes': 10, 'main_nodes': 290, 'quiesce_nodes_pv': 100, 'quiesce_nodes_non_pv': 600,
             'evals_main': 150, 'evals_quiesce': 500, 'evals_horizon': 0, 'tt_eval_hits_main': 50,
             'tt_eval_hits_quiesce': 0, 'makes': 800, 'pawn_makes': 200, 'pawn_makes_quiesce': 50,
             'perspective_updates': 1000, 'update_rows': 3000, 'frame_refreshes': 9, 'root_refreshes': 1,
             'walked_plies': 1300, 'evaluations': 650, 'link_updates': 250, 'move_pushes': 900, 'null_pushes': 100}
        r = scr.x1_ratios(c)
        self.assertEqual(r['nodes'], 1000)
        self.assertAlmostEqual(r['evaluations_per_node'], 0.65)
        self.assertAlmostEqual(r['quiescence_share_of_nodes'], 0.7)
        self.assertAlmostEqual(r['quiescence_share_of_evaluations'], 500 / 650)
        self.assertAlmostEqual(r['tt_eval_hit_rate_main'], 0.25)
        self.assertAlmostEqual(r['pawn_share_of_makes'], 0.25)
        self.assertAlmostEqual(r['rows_per_update'], 3.0)
        self.assertAlmostEqual(r['refreshes_per_1000_updates'], 10.0)
        self.assertAlmostEqual(r['plies_walked_per_evaluation'], 2.0)
        self.assertAlmostEqual(r['link_update_share'], 0.25)
        self.assertAlmostEqual(r['evaluated_share_of_pushes'], 0.65)
        # Without a network there is no tally, and no tally numbers.
        for name in ('perspective_updates', 'update_rows', 'frame_refreshes', 'root_refreshes', 'walked_plies',
                     'evaluations', 'link_updates', 'move_pushes', 'null_pushes'):
            del c[name]
        self.assertNotIn('rows_per_update', scr.x1_ratios(c))


if __name__ == '__main__':
    unittest.main()
