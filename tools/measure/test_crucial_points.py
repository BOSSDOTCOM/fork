# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/measure/crucial_points.py: bounds, labels and their sign
conventions, features, ROC arithmetic and site reading.

    python -I -B -m unittest discover -s tools/measure -p 'test_*.py'
"""
import collections.abc
import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))

import crucial_points as cp  # noqa: E402
import engine_lines  # noqa: E402


class CrucialPointsTests(unittest.TestCase):
    def test_nearest_bound(self):
        self.assertEqual(cp.nearest_bound(100, 50, 51), ('beta', 51))
        self.assertEqual(cp.nearest_bound(10, 50, 200), ('alpha', 50))
        self.assertEqual(cp.nearest_bound(10, -31000, 31000), None)
        self.assertEqual(cp.nearest_bound(10, -29999, 29998), None)  # mate-distance bounds
        self.assertEqual(cp.nearest_bound(10, -31000, 60), ('beta', 60))
        self.assertEqual(cp.nearest_bound(10, 0, 31000), ('alpha', 0))

    def test_crucial_label(self):
        # Zero window [50, 51]: the nearest bound is beta (51) above 50.5, alpha (50) at or below 50.
        self.assertEqual(cp.crucial_label(80, 30, 50, 51), 1)   # static fails high, deep fails low
        self.assertEqual(cp.crucial_label(80, 51, 50, 51), 0)   # deep exactly at beta still fails high
        self.assertEqual(cp.crucial_label(80, 60, 50, 51), 0)
        self.assertEqual(cp.crucial_label(20, 90, 50, 51), 1)   # static fails low, deep fails high
        self.assertEqual(cp.crucial_label(20, 50, 50, 51), 0)   # deep exactly at alpha still fails low
        self.assertEqual(cp.crucial_label(20, 40, 50, 51), 0)
        self.assertEqual(cp.crucial_label(20, 90, -31000, 31000), None)  # no finite bound: never crucial
        # A wide window: only the nearer bound counts.
        self.assertEqual(cp.crucial_label(190, 210, 0, 200), 1)
        self.assertEqual(cp.crucial_label(190, -10, 0, 200), 0)  # crosses alpha, but beta is nearer

    def test_site_features(self):
        board = chess.Board()
        for uci in ('e2e4', 'd7d5'):
            board.push_uci(uci)
        site = {'fen': board.fen(), 'eval': 30, 'alpha': 20, 'beta': 21, 'parent_eval': -10, 'prune_eval': 45,
                'captured': 0, 'reused': 1, 'on_pv': 0, 'depth': 3}
        f = cp.site_features(site)
        self.assertEqual(f['gap'], 9)
        self.assertEqual(f['hanging_own'], 1)    # e4: attacked by the d5 pawn, undefended
        self.assertEqual(f['hanging_their'], 0)  # d5: attacked by a pawn, defended by the queen, a pawn itself
        self.assertGreaterEqual(f['checks_available'], 1)  # Bb5+ (the d7 pawn has moved)
        self.assertEqual(f['parent_swing'], 20)
        self.assertEqual(f['refine_diff'], 15)

    def test_roc_points(self):
        points = cp.roc_points([5, 4, 4, 1], [1, 0, 1, 0], per_node=0.4)
        self.assertEqual(points, [(0.0, 0.0), (0.1, 0.5), (0.30000000000000004, 1.0), (0.4, 1.0)])

    def test_recall_at_rates(self):
        points = [(0.0, 0.0), (0.1, 0.5), (0.3, 1.0)]
        r = cp.recall_at_rates(points, (0.05, 0.1, 0.2, 0.5))
        self.assertAlmostEqual(r[0.05], 0.25)
        self.assertAlmostEqual(r[0.1], 0.5)
        self.assertAlmostEqual(r[0.2], 0.75)
        self.assertAlmostEqual(r[0.5], 1.0)

    def test_read_sites(self):
        with tempfile.TemporaryDirectory() as d:
            site = {'kind': 0, 'reused': 0, 'alpha': 1, 'beta': 2, 'eval': 5, 'prune_eval': 5, 'depth': 2, 'ply': 4,
                    'parent_eval': 0, 'tt_bound': 0, 'tt_depth': -1, 'captured': 0, 'on_pv': 0, 'fen': '8/8/8/8 w'}
            counters = {'root_nodes': 1, 'main_nodes': 49, 'quiesce_nodes_pv': 0, 'quiesce_nodes_non_pv': 50,
                        'evals_main': 20, 'tt_eval_hits_main': 10, 'evals_quiesce': 35, 'tt_eval_hits_quiesce': 5}
            records = [{'game': 'g', 'ply': 0, 'counters': counters, 'sites': [site, dict(site, kind=1)]},
                       {'game': 'g', 'ply': 2, 'counters': counters, 'sites': []}]
            (Path(d) / 'game-0000.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records), encoding='utf-8')
            sites, per_node = cp.read_sites(d)
            self.assertIsInstance(sites, collections.abc.Iterator)  # one at a time, never all held at once
            self.assertEqual([(s['id'], s['kind'], s['game']) for s in sites], [(0, 0, 'g'), (1, 1, 'g')])
            self.assertAlmostEqual(per_node['main'], 60 / 200)
            self.assertAlmostEqual(per_node['quiescence'], 80 / 200)

    def test_parse_eval_site_line(self):
        row = engine_lines.parse_eval_site_line(
            'eval_site 1|0|-11|-10|13|13|0|9|9|0|-1|0|0|r1bqkbnr/1p1p1ppp/p1n1p3/2p5/P3P3/2N2N2/1PPPBPPP/R1BQK2R b KQkq - 0 5\n')
        self.assertEqual((row['kind'], row['alpha'], row['beta'], row['eval'], row['tt_depth']), (1, -11, -10, 13, -1))
        self.assertEqual(row['fen'], 'r1bqkbnr/1p1p1ppp/p1n1p3/2p5/P3P3/2N2N2/1PPPBPPP/R1BQK2R b KQkq - 0 5')
        with self.assertRaises(ValueError):
            engine_lines.parse_eval_site_line('eval_site 1|0|2')

    def test_deep_resume_ignores_a_partial_line(self):
        # A stop can cut deep.tsv's last line short; the rerun must drop it
        # (else the next label is appended to it) and keep every whole line,
        # written with Windows line ends or not.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            site = {'id': 9, 'fen': chess.STARTING_FEN, 'eval': 10, 'alpha': 0, 'beta': 1}
            (out / 'sites.jsonl').write_text(json.dumps(site) + '\n', encoding='utf-8')
            (out / 'deep.tsv').write_bytes(b'3\t-41\t0\t14\r\n5\t20000\t1\t9\n7\t12')
            with contextlib.redirect_stdout(io.StringIO()) as said:
                # The engine is missing, so the run stops at its first engine call, after the resume.
                with self.assertRaises(OSError):
                    cp.main(['deep', str(out / 'missing-engine'), str(out)])
            self.assertEqual((out / 'deep.tsv').read_text(encoding='utf-8'), '3\t-41\t0\t14\n5\t20000\t1\t9\n')
            self.assertIn('1 incomplete line(s) dropped', said.getvalue())
            # Whole lines only: nothing is rewritten.
            before = (out / 'deep.tsv').read_bytes()
            with contextlib.redirect_stdout(io.StringIO()) as said:
                with self.assertRaises(OSError):
                    cp.main(['deep', str(out / 'missing-engine'), str(out)])
            self.assertEqual((out / 'deep.tsv').read_bytes(), before)
            self.assertNotIn('dropped', said.getvalue())

    def test_deep_sends_the_tables_path(self):
        # The labels search with the Syzygy tables of --syzygy (plan 3.3): the engine receives SyzygyPath
        # before its first search, and nothing without the option. The engine is a stand-in.
        ref = (Path(__file__).resolve().parents[2] / 'tests' / 'bench-s512ppr3.ref').read_text(encoding='utf-8')
        nodes = re.search(r'nodes (\d+)', ref).group(1)
        signature = re.search(r'signature ([0-9a-f]+)', ref).group(1)
        bench = f'nodes {nodes}\nsignature {signature}\n'
        for extra, expected in ((['--syzygy', 'tables/3-4-5'], True), ([], False)):
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)
                site = {'id': 7, 'fen': chess.STARTING_FEN, 'eval': 10, 'alpha': 0, 'beta': 1}
                (out / 'sites.jsonl').write_text(json.dumps(site) + '\n', encoding='utf-8')
                engine = mock.MagicMock()
                engine.stdout.readline.side_effect = ['uciok\n', 'readyok\n', 'info depth 3 score cp 25 nodes 9\n',
                                                      'bestmove e2e4\n']
                ran = lambda args, **_: mock.Mock(stdout='net s512ppr3\n' if args[1] == 'version' else bench)  # noqa: E731
                with mock.patch.object(cp.subprocess, 'run', side_effect=ran), \
                        mock.patch.object(cp.subprocess, 'Popen', return_value=engine), \
                        contextlib.redirect_stdout(io.StringIO()):
                    cp.main(['deep', 'engine', str(out), '--nodes', '9', '--workers', '1', *extra])
                sent = ''.join(call.args[0] for call in engine.stdin.write.call_args_list)
                self.assertEqual((out / 'deep.tsv').read_text(encoding='utf-8'), '7\t25\t0\t3\n')
            self.assertEqual('setoption name SyzygyPath value tables/3-4-5\n' in sent, expected)
            self.assertEqual('SyzygyPath' in sent, expected)
            if expected:
                self.assertLess(sent.index('SyzygyPath'), sent.index('go nodes 9'))


if __name__ == '__main__':
    unittest.main()
