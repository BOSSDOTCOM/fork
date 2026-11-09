# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/measure/label_pretest.py: the sample, the deep labeller
against a scripted fake engine, the bootstrap and the pass rule, the label
report and the closeness-weighted ranking, with a fault that the pass rule
must catch.

    python -I -B -m unittest discover -s tools/measure -p 'test_*.py'
"""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import chess

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'datagen'))
import label_pretest as lp  # noqa: E402
import td_labels as td  # noqa: E402
from test_td_labels import FOOL, U, encode_game  # noqa: E402

FAKE_ENGINE = r'''
import sys
fen = ''
for line in sys.stdin:
    line = line.strip()
    if line == 'uci':
        print('uciok', flush=True)
    elif line == 'isready':
        print('readyok', flush=True)
    elif line.startswith('position fen '):
        fen = line[len('position fen '):]
    elif line.startswith('go'):
        if fen.split()[1] == 'b':
            print('info depth 3 score mate -2 nodes 10', flush=True)
        else:
            print('info depth 1 score cp 5 nodes 1', flush=True)
            print('info depth 2 score cp 42 nodes 9', flush=True)
        print('bestmove 0000', flush=True)
    elif line == 'quit':
        break
'''


def shard():
    games = [FOOL, (chess.STARTING_FEN, ['e2e4', 'e7e5', 'g1f3'], [20, U, 30], 1),
             (chess.STARTING_FEN, ['d2d4'], [U], 1), (chess.STARTING_FEN, ['c2c4', 'e7e5'], [5, -5], 2)]
    return b''.join(encode_game(*g)[0] for g in games)


class SampleTests(unittest.TestCase):
    def test_one_saved_record_per_game(self):
        data = shard()
        sites, total = lp.sample_sites(data, 'x.vf', 10, 7)
        self.assertEqual(total, 4)
        self.assertEqual(sorted(int(s['game'].split('#')[1]) for s in sites), [0, 1, 3])  # game 2 has none saved
        games = list(td.split_games(data))
        for s in sites:
            index = int(s['game'].split('#')[1])
            _, head, recs, _ = games[index]
            self.assertNotEqual(recs[s['record']][1], U)
            rows, _ = td.replay(head, recs, table_pieces=0)
            self.assertEqual(td.fen_key(chess.Board(s['fen'])), rows[s['record']][0])
            self.assertEqual(s['kept'], rows[s['record']][2])
        self.assertEqual(sites, lp.sample_sites(data, 'x.vf', 10, 7)[0])  # seeded


class DeepTests(unittest.TestCase):
    def test_labels_mates_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'engine.py').write_text(FAKE_ENGINE, encoding='utf-8')
            engine = [sys.executable, '-I', str(tmp / 'engine.py')]
            out = tmp / 'deep.tsv'
            out.write_text('5\t1\t0\t1\n', encoding='utf-8')
            lp.deep_search(engine, [(0, chess.STARTING_FEN), (1, 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b '
                                                              'KQkq - 0 1')], out, 100, 2)
            lines = sorted(out.read_text(encoding='utf-8').splitlines())
            self.assertEqual(lines, ['0\t42\t0\t2', '1\t-20000\t1\t3', '5\t1\t0\t1'])


class BootTests(unittest.TestCase):
    def test_difference_and_interval(self):
        groups = [(1.0, 1, 2.0, 1), (2.0, 1, 3.5, 1), (0.5, 1, 1.0, 1), (1.5, 1, 2.0, 1)]
        d, (lo, hi) = lp.boot_difference(groups, 2000, 3)
        self.assertAlmostEqual(d, 5.0 / 4 - 8.5 / 4)
        self.assertLess(hi, 0)  # every game's difference is negative
        self.assertLessEqual(lo, d)
        self.assertEqual((d, (lo, hi)), lp.boot_difference(groups, 2000, 3))

    def test_straddling_interval_does_not_pass(self):
        errs = [{'game': f'g{k}', 'kept': True, 'end': 'table',
                 'err': {'control': 0.10, 'td=0.9': 0.10 + (0.02 if k % 2 else -0.02)}} for k in range(40)]
        rep = lp.label_report(errs, [0.9], 1000, 1)
        self.assertAlmostEqual(rep['td']['td=0.9']['difference'], 0.0, places=12)
        self.assertFalse(rep['td']['td=0.9']['passes'])

    def test_a_clearly_better_candidate_passes(self):
        errs = [{'game': f'g{k}', 'kept': k % 3 != 0, 'end': 'table',
                 'err': {'control': 0.10 + 0.001 * k, 'td=0.9': 0.05 + 0.001 * k}} for k in range(40)]
        rep = lp.label_report(errs, [0.9], 1000, 1)
        self.assertTrue(rep['td']['td=0.9']['passes'])
        self.assertEqual(rep['kept'], 26)
        # The unfiltered comparison: every saved record against the kept ones.
        all_mse = sum(0.10 + 0.001 * k for k in range(40)) / 40
        kept_mse = sum(0.10 + 0.001 * k for k in range(40) if k % 3) / 26
        self.assertAlmostEqual(rep['unfiltered']['difference'], all_mse - kept_mse, places=12)

    def test_fault_a_reversed_rule_is_caught(self):
        # Injected fault: a rule reading the interval's lower end would pass
        # the straddling candidate; the real rule must not.
        errs = [{'game': f'g{k}', 'kept': True, 'end': 'x',
                 'err': {'control': 0.1, 'td=0.5': 0.1 + (0.03 if k % 2 else -0.03)}} for k in range(40)]
        rep = lp.label_report(errs, [0.5], 1000, 2)
        lo, hi = rep['td']['td=0.5']['interval']
        self.assertTrue(lo < 0)       # the faulty rule would pass it
        self.assertFalse(rep['td']['td=0.5']['passes'])


class RankTests(unittest.TestCase):
    def test_weights_errors_and_n_eff(self):
        sites = [  # gap 0 (weight 1) and gap 25 at h 25 (weight exp(-1/2)); a mate label and an open window dropped
            {'game': 'a', 'kind': 0, 'eval': 10, 'alpha': 9, 'beta': 10, 'deep': 0, 'mate': 0,
             'evals': {'r': 0, 'x': 89}},
            {'game': 'b', 'kind': 0, 'eval': 35, 'alpha': 9, 'beta': 10, 'deep': 0, 'mate': 0,
             'evals': {'r': 89, 'x': 0}},
            {'game': 'c', 'kind': 1, 'eval': 0, 'alpha': -1, 'beta': 0, 'deep': 20000, 'mate': 1,
             'evals': {'r': 0, 'x': 0}},
            {'game': 'd', 'kind': 1, 'eval': 0, 'alpha': -30000, 'beta': 30000, 'deep': 0, 'mate': 0,
             'evals': {'r': 0, 'x': 0}},
        ]
        rep = lp.rank_report(sites, ['r', 'x'], 'r', 89.0, {0: 25.0, 1: 17.0}, 200, 1)
        self.assertEqual(rep['used'], 2)
        w = math.exp(-0.5)
        e = (1 / (1 + math.exp(-1)) - 0.5) ** 2
        self.assertAlmostEqual(rep['plain']['r'], e / 2)
        self.assertAlmostEqual(rep['plain']['x'], e / 2)
        self.assertAlmostEqual(rep['weighted']['r'], w * e / (1 + w))
        self.assertAlmostEqual(rep['weighted']['x'], e / (1 + w))
        self.assertAlmostEqual(rep['n_eff'], (1 + w) ** 2 / (1 + w * w))
        self.assertAlmostEqual(rep['against_reference']['x']['weighted']['difference'], (1 - w) * e / (1 + w))

    def test_read_rank_sites(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / 'sites.jsonl').write_text(json.dumps({'id': 3, 'kind': 1, 'eval': 4, 'alpha': 1, 'beta': 2,
                                                       'game': 'g#1'}) + '\n', encoding='utf-8')
            (d / 'deep.tsv').write_text('3\t-7\t0\t12\n', encoding='utf-8')
            (d / 'seed-a.tsv').write_text('3\t11\n', encoding='utf-8')
            got = lp.read_rank_sites(d, ['a'])
            self.assertEqual(len(got), 1)
            self.assertEqual((got[0]['deep'], got[0]['evals'], got[0]['kind']), (-7, {'a': 11}, 1))


if __name__ == '__main__':
    unittest.main()
