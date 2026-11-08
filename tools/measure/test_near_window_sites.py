# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/measure/near_window_sites.py: games picked from several
viriformat shards and decoded, and the site selection's deduplication and
exclusion.

    python -I -B -m unittest discover -s tools/measure -p 'test_*.py'
"""
import contextlib
import io
import json
import math
import random
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'datagen'))

import endgame_slice  # noqa: E402
import near_window_sites  # noqa: E402
import verify_games  # noqa: E402


class NearWindowSitesTests(unittest.TestCase):
    def test_games_decodes_and_picks(self):
        def encode(fen, moves):
            # One viriformat game: endgame_slice's 32-byte board, each move with a zero score, the terminator.
            board = chess.Board(fen)
            out = bytearray(endgame_slice.encode(board, chess.Move.from_uci(moves[0]), 1, 0)[:32])
            for m in moves:
                move = chess.Move.from_uci(m)
                out += struct.pack('<Hh', verify_games.code_of(board, move), 0)
                board.push(move)
            return bytes(out + struct.pack('<Hh', 0, 0))

        # Start positions without castling rights (endgame_slice's board writes none).
        start = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1'
        other = '4k3/8/8/8/8/8/4P3/4K3 b - - 3 40'
        games = {('a.vf', 0): (start, ['e2e4', 'e7e5', 'g1f3']),
                 ('a.vf', 1): (start, ['d2d4']),
                 ('b.vf', 0): (other, ['e8d7', 'e2e4']),
                 ('b.vf', 1): (start, ['e2e4', 'c7c5', 'e4e5', 'd7d5', 'e5d6']),  # en passant
                 ('b.vf', 2): (other, ['e8f7'])}
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for name in ('a.vf', 'b.vf'):
                (tmp / name).write_bytes(b''.join(encode(*games[key]) for key in sorted(games) if key[0] == name))
            out = tmp / 'games.jsonl'
            with contextlib.redirect_stdout(io.StringIO()):
                near_window_sites.main(['games', str(tmp / 'a.vf'), str(tmp / 'b.vf'), str(out),
                                        '--count', '4', '--seed', '7'])
            picked = [json.loads(line) for line in out.read_text(encoding='utf-8').splitlines()]
        # The picks: a seeded shuffle of every game of the shards, in the order the shards were given.
        order = list(range(5))
        random.Random(7).shuffle(order)
        keys = sorted(games)
        self.assertEqual([g['id'] for g in picked], [f'{keys[k][0]}#{keys[k][1]}' for k in order[:4]])
        for k, g in enumerate(picked):
            name, index = g['id'].split('#')
            fen, moves = games[(name, int(index))]
            self.assertEqual((g['fen'], g['moves']), (fen, moves))
            self.assertEqual(g['colour'], 'wb'[k % 2])
            self.assertEqual(g['depths'], [None] * len(moves))

    def test_select_dedups_and_excludes(self):
        site = lambda i, fen, value, kind=0: {'id': i, 'fen': fen, 'eval': value, 'alpha': 0, 'beta': 1,  # noqa: E731
                                              'kind': kind, 'reused': False}
        a = '4k3/8/8/8/8/8/4P3/4K3 w - - 0 1'
        b = '4k3/8/8/8/8/8/3P4/4K3 w - - 0 1'
        c = '4k3/8/8/8/8/8/2P5/4K3 w - - 0 1'
        sites = [site(4, a, 10), site(2, a.replace(' 0 1', ' 6 30'), 12),  # one position twice
                 site(3, b, 30, kind=1), site(5, c, 5), site(6, c.replace(' 0 1', ' 2 9'), 500)]  # 6 too far
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'all.jsonl').write_text(''.join(json.dumps(s) + '\n' for s in sites), encoding='utf-8')
            (tmp / 'other.jsonl').write_text(json.dumps(site(1, c.replace(' 0 1', ' 1 2'), 0)) + '\n',
                                             encoding='utf-8')

            def select(*extra):
                with contextlib.redirect_stdout(io.StringIO()) as said:
                    near_window_sites.main(['select', str(tmp / 'all.jsonl'), str(tmp / 'out'), '--gap', '80',
                                            '--count', '10', '--seed', '1', *extra])
                text = (tmp / 'out' / 'sites.jsonl').read_text(encoding='utf-8')
                return [json.loads(line)['id'] for line in text.splitlines()], said.getvalue()

            self.assertEqual(select()[0], [2, 3, 4, 5])
            self.assertEqual(select('--dedup')[0], [2, 3, 5])  # the first of a position by id
            self.assertEqual(select('--exclude', str(tmp / 'other.jsonl'))[0], [2, 3, 4])  # move counters ignored
            ids, said = select('--dedup', '--exclude', str(tmp / 'other.jsonl'))
            self.assertEqual(ids, [2, 3])
            self.assertIn('dropped: 1 excluded, 1 duplicates', said)
            # Decision weights: gap 11 at main-search site 2 (h 25), gap 29 at quiescence site 3 (h 10).
            w = [math.exp(-11 ** 2 / (2 * 25 ** 2)), math.exp(-29 ** 2 / (2 * 10 ** 2))]
            n_eff = sum(w) ** 2 / sum(x * x for x in w)
            self.assertIn(f'n_eff {n_eff:.0f} of 2 ({n_eff / 2:.2f})', said)


if __name__ == '__main__':
    unittest.main()
