# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/datagen/verify_games.py's end-of-game judgement
(DESIGN.md §5.3, deliverable 2).

A record starts after the opening's random plies, but fork_datagen plays
those plies on the game's own position, so its threefold repetition count
includes them. The case below is generation 0's worker 0, game 121414
(data/manifests/g0.json, shard g0-w00.vf): a perpetual check whose final
position occurs twice in the 9-ply record and once more in the plies just
before it (the record's start is that position after Kd7-e8, halfmove clock
2), stored as a draw.

    python -I -B -m unittest discover -s tools/datagen -p 'test_*.py'
"""
import sys
import unittest
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_games as vg  # noqa: E402

PERPETUAL = '1rbqkbnr/2p3pp/ppp5/5Q2/3PPP2/8/PPP3PP/RNB1K2R w KQ - 2 12'
PERPETUAL_MOVES = 'f5h5 e8e7 h5g5 e7d7 g5f5 d7e7 f5g5 e7d7 g5f5'.split()


def played(fen, moves):
    board = chess.Board(fen)
    for m in moves:
        board.push_uci(m)
    return board


class ExpectedEndTests(unittest.TestCase):
    def test_repetition_reaching_before_the_record_is_a_draw(self):
        board = played(PERPETUAL, PERPETUAL_MOVES)
        self.assertFalse(board.is_repetition(3))  # only twice within the record
        self.assertEqual(vg.expected_end(board, 0, 5), ('1/2-1/2', 'repetition before the record'))

    def test_no_repetition_explained_when_the_clock_stays_inside_the_record(self):
        # The same moves from a start with halfmove clock 0: no earlier ply
        # can hold the third occurrence, so the end stays unexplained.
        board = played(PERPETUAL.replace(' 2 12', ' 0 12'), PERPETUAL_MOVES)
        self.assertEqual(vg.expected_end(board, 0, 5), (None, 'unexplained'))

    def test_threefold_within_the_record_is_a_rules_draw(self):
        board = played(PERPETUAL, PERPETUAL_MOVES + 'd7e7 f5g5 e7d7 g5f5'.split())
        self.assertTrue(board.is_repetition(3))
        self.assertEqual(vg.expected_end(board, 0, 5), ('1/2-1/2', 'rules draw'))

    def test_a_mate_score_is_judged_before_a_repetition(self):
        board = played(PERPETUAL, PERPETUAL_MOVES)
        self.assertEqual(vg.expected_end(board, 29990, 5), ('1-0', 'mate score'))

    def test_a_completed_score_adjudication_is_judged_before_the_board(self):
        board = played(PERPETUAL, PERPETUAL_MOVES)
        self.assertEqual(vg.expected_end(board, -900, 5, -1), ('0-1', 'score adjudication'))
        self.assertEqual(vg.expected_end(board, 900, 5, 1), ('1-0', 'score adjudication'))


class ScoreStreakTests(unittest.TestCase):
    """The same sequences as tests/test_datagen.cpp's ScoreStreak case."""

    def run_streak(self, cp, scores):
        count = sign = 0
        out = []
        for v in scores:
            count, sign = vg.streak_step(count, sign, v, cp)
            out.append(count * sign)
        return out

    def test_inclusive_bound(self):
        self.assertEqual(self.run_streak(300, [300, 400, 500]), [1, 2, 3])

    def test_band_restarts(self):
        self.assertEqual(self.run_streak(300, [300, 400, 299, 300]), [1, 2, 0, 1])

    def test_other_side_restarts(self):
        self.assertEqual(self.run_streak(300, [300, 400, -500, -300]), [1, 2, -1, -2])


if __name__ == '__main__':
    unittest.main()
