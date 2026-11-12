# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of heldout_deep.py: the fast game-file scan replays every move kind exactly as python-chess does (the key
of every position matches), finds a planted position and ignores a truncated game; the PGN splitter and filters;
the label classes and the misjudged rule."""
import io
import sys
import tempfile
import unittest
from pathlib import Path

import chess

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'datagen'))
import endgame_heldout as eh  # noqa: E402
import endgame_slice as es  # noqa: E402
import heldout_deep as hd  # noqa: E402
import verify_games as vg  # noqa: E402

# En passant, castling both ways, a capture-promotion and an under-promotion.
START = 'r3k2r/1P6/8/3pP3/8/8/6p1/R3K2R w KQkq d6 0 1'
MOVES = ['e5d6', 'e8g8', 'b7a8q', 'g2g1n', 'e1c1', 'g8g7', 'a8a7', 'g7g6']


def game_bytes(fen, moves):
    board = chess.Board(fen)
    first = chess.Move.from_uci(moves[0])
    head = es.encode(board, first, 1, 0)[:32]
    out = bytearray(head)
    keys = [eh.key(board)]
    for uci in moves:
        m = chess.Move.from_uci(uci)
        assert m in board.legal_moves, uci
        out += vg.code_of(board, m).to_bytes(2, 'little') + (0).to_bytes(2, 'little')
        board.push(m)
        keys.append(eh.key(board))
    return bytes(out + bytes(4)), keys


class Scan(unittest.TestCase):
    def setUp(self):
        self.saved = hd.PIECES
        hd.PIECES = range(2, 33)

    def tearDown(self):
        hd.PIECES = self.saved

    def test_every_move_kind_replays_like_python_chess(self):
        data, keys = game_bytes(START, MOVES)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'g.vf'
            path.write_bytes(data + data[:40])  # a second, truncated game is ignored
            found, ngames, npos = hd.scan(path, {int.from_bytes(k[0][:8], 'little') for k in keys}, set(keys))
        self.assertEqual((ngames, npos), (1, len(MOVES) + 1))
        self.assertEqual(found, set(keys))

    def test_a_different_side_to_move_is_not_found(self):
        data, keys = game_bytes(START, MOVES)
        other = {(k[0], not k[1]) for k in keys}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'g.vf'
            path.write_bytes(data)
            found, _, _ = hd.scan(path, {int.from_bytes(k[0][:8], 'little') for k in other}, other)
        # Positions that recur with the other side to move would match legitimately; this game has none.
        self.assertEqual(found, set())


class Positions(unittest.TestCase):
    PGN = ('[Event "Rated Blitz game"]\n[Site "https://lichess.org/x1"]\n[WhiteElo "2100"]\n[BlackElo "2050"]\n\n'
           '1. e4 e5 1-0\n\n'
           '[Event "Rated Blitz game"]\n[Site "https://lichess.org/x2"]\n[WhiteElo "2100"]\n[BlackElo "1900"]\n\n'
           '1. d4 d5 0-1\n\n'
           '[Event "Casual Blitz game"]\n[Site "https://lichess.org/x3"]\n[WhiteElo "2500"]\n[BlackElo "2500"]\n\n'
           '1. c4 c5 1/2-1/2\n\n'
           '[Event "Rated Blitz game"]\n[Site "https://lichess.org/x4"]\n[WhiteElo "2500"]\n[BlackElo "2500"]\n'
           '[BlackTitle "BOT"]\n\n1. c4 c5 1/2-1/2\n')

    def test_split_and_filter(self):
        got = list(hd.games(io.StringIO(self.PGN)))
        self.assertEqual([h['Site'] for h, _ in got], ['https://lichess.org/x1', 'https://lichess.org/x2',
                                                        'https://lichess.org/x3', 'https://lichess.org/x4'])
        self.assertEqual([hd.eligible(h) for h, _ in got], [True, False, False, False])
        self.assertIn('1. e4 e5', got[0][1])


class Labels(unittest.TestCase):
    def test_classes_and_rule(self):
        self.assertEqual([hd.label_class(x) for x in ('200', '199', '50', '-50', '-51', '-200', 'M3', 'M-2')],
                         ['winning', None, 'level', 'level', None, 'losing', 'winning', 'losing'])
        self.assertTrue(hd.misjudged('winning', 99))
        self.assertFalse(hd.misjudged('winning', 100))
        self.assertTrue(hd.misjudged('losing', -99))
        self.assertTrue(hd.misjudged('level', 201))
        self.assertFalse(hd.misjudged('level', -200))


if __name__ == '__main__':
    unittest.main()
