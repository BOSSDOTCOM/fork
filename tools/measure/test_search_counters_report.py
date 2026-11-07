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

    def test_share_above_matches_direct_count(self):
        # The engine's sign-magnitude bins (searcher.hpp's order_score_bin),
        # rebuilt here for synthetic scores; the oracle is a direct count.
        width, count = 500, 132
        half = count // 2
        scores = list(range(-32767, 32768, 37)) + [24000, -24000, 23999, -23999, 0, -1]
        bins = [0] * count
        for s in scores:
            b = half + s // width if s >= 0 else half - 1 - (-s) // width
            bins[b] += 1
        above, below, total = scr.history_share_above(bins, 24000, width)
        self.assertEqual(above, sum(1 for s in scores if s >= 24000))
        self.assertEqual(below, sum(1 for s in scores if s <= -24000))
        self.assertEqual(total, len(scores))
        with self.assertRaises(ValueError):
            scr.history_share_above(bins, 24100, width)

    def test_move_band(self):
        self.assertEqual([scr.move_band(n) for n in (1, 15, 16, 29, 30, 60, 61, 200)],
                         ['1-15', '1-15', '16-29', '16-29', '30-60', '30-60', '61+', '61+'])
        # The report groups searches by band and bootstraps over games.
        records = [{'game': g, 'move_number': n,
                    'counters': {'lmr_rule_sites': 100, 'lmr_history_fire_less': 1, 'lmr_history_fire_more': 3,
                                 'lmr_history_changes': 2, 'late_capture_sites': 5}}
                   for g in ('a', 'b') for n in (10, 40)]
        r = scr.x2_report(records, {'counters': {'lmr_rule_sites': 1000, 'lmr_history_fire_less': 0,
                                                 'lmr_history_fire_more': 4}, 'hist': {}}, rounds=50)
        self.assertEqual(r['bands']['30-60']['lmr_sites'], 200)
        self.assertAlmostEqual(r['bands']['30-60']['term_acts_share'], 0.04)
        self.assertAlmostEqual(r['bands']['all']['reduce_more_share_of_firings'], 0.75)
        self.assertAlmostEqual(r['ratio_30_60_to_bench'], 10.0)
        self.assertEqual(r['bands']['1-15']['games'], 2)

    def test_gap_bin_edges(self):
        edges = scr.gap_bin_edges()
        self.assertEqual(len(edges), 317)  # searcher.hpp's GapBins
        self.assertEqual(edges[0], (0, 0))
        self.assertEqual(edges[255], (255, 255))
        self.assertEqual(edges[256], (256, 319))
        self.assertEqual(edges[315], (4032, 4095))
        self.assertEqual(edges[316], (4096, None))

    def test_gap_share_within(self):
        bins = [0] * 317
        bins[0], bins[10], bins[11], bins[100], bins[300] = 2, 3, 4, 5, 6
        self.assertEqual(scr.gap_share_within(bins, 10, 10), (5, 30))  # gaps of 10 count; infinite in the total
        self.assertEqual(scr.gap_share_within(bins, 0, 100), (14, 20))
        with self.assertRaises(ValueError):
            scr.gap_share_within(bins, 0, 300)

    def test_window_gap_report(self):
        empty = [0] * 317
        main, qs = list(empty), list(empty)
        main[5], main[30] = 10, 30  # 40 main evaluations with a finite bound
        qs[20], qs[60] = 50, 50
        hist = {'eval_gap_main': main, 'eval_gap_quiesce': qs, 'eval_gap_main_reuse': list(empty),
                'eval_gap_quiesce_reuse': list(empty), 'eval_gap_band_1': main,
                'eval_gap_band_infinite': [10, 0, 0, 0, 0]}
        counters = {'root_nodes': 0, 'main_nodes': 100, 'quiesce_nodes_pv': 0, 'quiesce_nodes_non_pv': 100,
                    'eval_gap_main_infinite': 10, 'eval_gap_quiesce_infinite': 0, 'eval_gap_main_reuse_infinite': 0,
                    'eval_gap_quiesce_reuse_infinite': 0, 'eval_gap_main_one_sided': 5, 'eval_gap_quiesce_one_sided': 0}
        r = scr.window_gap_report(counters, hist)
        self.assertEqual(r['main']['evaluations'], 50)
        self.assertAlmostEqual(r['main']['infinite_share'], 0.2)
        self.assertAlmostEqual(r['main']['within_10']['share'], 10 / 50)
        self.assertAlmostEqual(r['main']['within_50']['call_rate_per_node'], 40 / 200)
        self.assertAlmostEqual(r['quiescence']['within_25']['share'], 0.5)
        self.assertAlmostEqual(r['combined_call_rate_per_node'][100], (40 + 100) / 200)
        self.assertEqual(r['quiescence']['gap_p25'], 20)
        self.assertEqual(r['main_by_depth']['1']['evaluations'], 50)


if __name__ == '__main__':
    unittest.main()
