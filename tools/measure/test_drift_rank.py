# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/measure/drift_rank.py: flips, fitness and the declared order.

    python -I -B -m unittest discover -s tools/measure -p 'test_*.py'
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import drift_rank as dr  # noqa: E402


def rfp_row(excess, margin, arm, drift):
    return {'technique': 'rfp', 'excess': excess, 'margin': margin, 'arm_minus_beta': arm, 'drift': drift}


def fut_row(deficit, margin, on, off, drift):
    return {'technique': 'futility', 'deficit': deficit, 'margin': margin, 'on_minus_beta': on,
            'off_minus_beta': off, 'drift': drift}


def flat(v, **over):
    d = {t: v for t in ('pieces', 'minor', 'major', 'threat')}
    d.update(over)
    return d


class DriftRankTests(unittest.TestCase):
    def test_flips(self):
        records = [{'ledger': [
            # Raw does not prune (90 < 100); pieces would (110): a new prune, right (the arm held beta).
            rfp_row(90, 100, 5, flat(90, pieces=110)),
            # Raw prunes; minor would not: a removed prune that was wrong (the arm failed low): right.
            rfp_row(120, 100, -5, flat(120, minor=80)),
            # Raw prunes; major would not, and the prune was right: a wrong flip.
            rfp_row(120, 100, 5, flat(120, major=80)),
            # Futility: threat makes it fire, and futility is wrong here (on fails low, off fails high).
            fut_row(50, 100, -1, 3, flat(50, threat=130)),
            # No drift values: not counted.
            {'technique': 'rfp', 'excess': 0, 'margin': 1, 'arm_minus_beta': 0},
        ]}]
        g = dr.game_tallies(records)
        self.assertEqual(g['rows'], {'rfp': 3, 'futility': 1})
        self.assertEqual(g['flips']['pieces']['rfp'], [1, 0])
        self.assertEqual(g['flips']['minor']['rfp'], [1, 0])
        self.assertEqual(g['flips']['major']['rfp'], [0, 1])
        self.assertEqual(g['flips']['threat']['futility'], [0, 1])
        s = dr.summarize([g])
        self.assertAlmostEqual(s['tables']['pieces']['gain_per_1000'], 250.0)
        self.assertAlmostEqual(s['tables']['major']['gain_per_1000'], -250.0)

    def test_fitness_and_order(self):
        counters = {'drift_samples': 10, 'drift_error_raw': 1000, 'drift_tail_samples': 2, 'drift_tail_raw': 400,
                    'drift_error_pieces': 900, 'drift_tail_pieces': 300, 'drift_half_pieces': 950,
                    'drift_error_minor': 1000, 'drift_tail_minor': 200, 'drift_half_minor': 1000,
                    'drift_error_major': 1000, 'drift_tail_major': 400, 'drift_half_major': 1000,
                    'drift_error_threat': 1000, 'drift_tail_threat': 400, 'drift_half_threat': 1000}
        ledger = [rfp_row(90, 100, 5, flat(90, pieces=110, minor=110))] * 10
        games = [dr.game_tallies([{'counters': counters, 'ledger': ledger}]) for _ in range(5)]
        r = dr.rank(games, rounds=50)
        self.assertAlmostEqual(r['tables']['pieces']['fitness'], 0.9)
        self.assertAlmostEqual(r['tables']['minor']['tail_fitness'], 0.5)
        # pieces and minor tie on G in every resample; minor's better tail fitness puts it first.
        self.assertEqual(r['order'][:2], ['minor', 'pieces'])
        self.assertTrue(r['pairs'][0]['swapped'])


if __name__ == '__main__':
    unittest.main()
