# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/datagen/snapshot_parts.py: the game split against
python-chess-built games, the exclusions, the stream merge and the record.
(Checked once on real data too: rebuilding g3s3's rest of g3f-w09-val.vf and
g3s3-val.vf gives the SHA-256 values data/manifests/g3s3.json holds;
docs/research/retrain-8b/plan.md.)

    python -I -B -m unittest discover -s tools/datagen -p 'test_snapshot_parts.py'
"""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import snapshot_parts as sp  # noqa: E402
import test_td_labels as tt  # noqa: E402 (its python-chess game encoder)


def games(n, seed=0):
    """n short games, each distinct (its first move and its result vary), some with an unsaved record."""
    out = []
    firsts = ['e2e4', 'd2d4', 'g1f3', 'c2c4', 'b1c3', 'f2f4', 'b2b3', 'g2g3']
    for k in range(n):
        moves = [firsts[(k + seed) % 8], 'e7e6' if k % 2 else 'd7d6']
        scores = [k, tt.U if k % 3 == 0 else -k]
        out.append(tt.encode_game(chess.STARTING_FEN, moves, scores, k % 3)[0])
    return out


class SnapshotPartsTests(unittest.TestCase):
    def test_spans_and_stats(self):
        g = games(7)
        data = b''.join(g)
        spans = sp.game_spans(data)
        self.assertEqual([(s, e) for s, e, _, _ in spans],
                         [(sum(map(len, g[:k])), sum(map(len, g[:k + 1]))) for k in range(7)])
        st = sp.stats_of('x.vf', data)
        self.assertEqual((st['games'], st['positions'], st['positions_unsaved'], st['positions_saved']), (7, 14, 3, 11))
        with self.assertRaises(ValueError):
            sp.game_spans(data[:-1])

    def test_hold_and_exclude(self):
        g = games(10)
        held, rest, dropped = sp.hold(b''.join(g), 3, {1, 4, 9, 12})
        self.assertEqual(held, b''.join(g[:3]))
        self.assertEqual(rest, b''.join(g[k] for k in range(3, 10) if k not in (4, 9)))
        self.assertEqual(dropped, 2)  # 1 is held (validation, never training), 12 is past the end
        with self.assertRaises(ValueError):
            sp.hold(b''.join(g), 11, set())

    def test_excluded_games_reads_only_this_shard(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / 'sites.jsonl'
            f.write_text('{"game": "a.vf#3"}\n{"game": "b.vf#4"}\n\n{"game": "a.vf#7"}\n{"fen": "x"}\n',
                         encoding='utf-8')
            self.assertEqual(sp.excluded_games([f], 'a.vf'), {3, 7})

    def test_val_merges_streams_one_game_at_a_time(self):
        base = games(6)          # 2 streams: games 0, 2, 4 and 1, 3, 5
        held = games(2, seed=5)  # one more stream
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / 'base.vf').write_bytes(b''.join(base))
            (t / 'h.vf').write_bytes(b''.join(held))
            with mock.patch('sys.stdout', io.StringIO()):
                self.assertEqual(sp.main(['val', '--base', str(t / 'base.vf'), '--streams', '2', '--held',
                                          str(t / 'h.vf'), '--out', str(t / 'v.vf')]), 0)
            want = [base[0], base[1], held[0], base[2], base[3], held[1], base[4], base[5]]
            self.assertEqual((t / 'v.vf').read_bytes(), b''.join(want))
            with mock.patch('sys.stdout', io.StringIO()), mock.patch('sys.stderr', io.StringIO()):
                self.assertEqual(sp.main(['val', '--base', str(t / 'base.vf'), '--streams', '4', '--held',
                                          str(t / 'h.vf'), '--out', str(t / 'w.vf')]), 1)

    def test_hold_and_record_commands(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            g = games(8)
            (t / 'p-w05-val.vf').write_bytes(b''.join(g))
            (t / 's.jsonl').write_text(json.dumps({'game': 'p-w05-val.vf#6'}) + '\n', encoding='utf-8')
            out = io.StringIO()
            with mock.patch('sys.stdout', out):
                self.assertEqual(sp.main(['hold', str(t / 'p-w05-val.vf'), '--games', '2', '--prefix', 'g4s1',
                                          '--out', str(t / 'o'), '--exclude', str(t / 's.jsonl')]), 0)
            info = json.loads(out.getvalue())
            self.assertEqual(info['excluded_games'], 1)
            self.assertEqual((t / 'o' / 'g4s1-p-w05-val-held.vf').read_bytes(), b''.join(g[:2]))
            self.assertEqual((t / 'o' / 'g4s1-p-w05-val-rest.vf').read_bytes(), b''.join(g[2:6] + g[7:]))
            with mock.patch('sys.stdout', io.StringIO()):
                sp.main(['record', 'r', str(t / 'o' / 'g4s1-p-w05-val-rest.vf'), '--out', str(t / 'r.json')])
            rec = json.loads((t / 'r.json').read_text(encoding='utf-8'))
            self.assertEqual(rec['batches'][0][0]['games'], 5)
            self.assertEqual(rec['totals']['games'], 5)


if __name__ == '__main__':
    unittest.main()
