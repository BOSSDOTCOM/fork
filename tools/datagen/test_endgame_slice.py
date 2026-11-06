# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of endgame_slice.py: its records decode with verify_games.py's own decoder, carry the tables' WDL from
White's view in the result and the score, and pass verify_games.py; the positions are legal and quiet. Uses the
3-4-5 test tables CMake downloads (.cache/syzygy345: KPvK, KQvK, KRvK among them); skipped without them."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import chess
import chess.syzygy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import endgame_slice as es  # noqa: E402
import verify_games as vg  # noqa: E402

TABLES = HERE.parent.parent / '.cache' / 'syzygy345'
HAVE = all((TABLES / f'{s}.rtbw').exists() for s in es.BASIC)


class Encoding(unittest.TestCase):
    def test_a_record_decodes_with_the_verifiers_decoder(self):
        board = chess.Board('8/8/8/4k3/8/8/3QK3/8 b - - 0 1')
        move = chess.Move.from_uci('e5e6')
        data = es.encode(board, move, 2, es.SLICE_SCORE)
        back, result = vg.decode_board(data[:32])
        self.assertEqual(back.board_fen(), board.board_fen())
        self.assertEqual(back.turn, chess.BLACK)
        self.assertEqual(result, 2)
        self.assertEqual(vg.u16(data, 32), vg.code_of(board, move))
        self.assertEqual(vg.i16(data, 34), es.SLICE_SCORE)
        self.assertEqual(data[36:40], bytes(4))  # the terminator

    def test_signature_names(self):
        self.assertEqual(es.signature(chess.Board('8/8/8/4k3/8/8/3QK3/8 w - - 0 1')), 'KQvK')
        self.assertEqual(es.signature(chess.Board('8/8/8/4k3/2r5/8/3PK3/8 w - - 0 1')), 'KPvKR')


@unittest.skipUnless(HAVE, 'the 3-4-5 test tables are not in .cache/syzygy345')
class Generation(unittest.TestCase):
    def test_labels_follow_the_tables_from_whites_view(self):
        data, wdl, made = es.generate(str(TABLES), {'KQvK': 1, 'KRvK': 1, 'KPvK': 1}, 600, seed=7)
        self.assertEqual(len(data), 600 * 40)
        self.assertEqual(sum(wdl.values()), 600)
        with chess.syzygy.open_tablebase(str(TABLES)) as tb:
            for k in range(600):
                rec = data[40 * k:40 * (k + 1)]
                board, result = vg.decode_board(rec[:32])
                self.assertFalse(board.is_check())
                self.assertLessEqual(chess.popcount(board.occupied), es.TABLE_PIECES)
                w = tb.probe_wdl(board)
                stm = 1 if w == 2 else -1 if w == -2 else 0
                white = stm if board.turn == chess.WHITE else -stm
                self.assertEqual(result, white + 1, board.fen())
                self.assertEqual(vg.i16(rec, 34), es.SLICE_SCORE * white, board.fen())
                move = next(m for m in board.legal_moves if vg.code_of(board, m) == vg.u16(rec, 32))
                self.assertFalse(board.is_capture(move) or move.promotion, board.fen())
        self.assertGreater(wdl['win'] + wdl['loss'], 300)  # KQK and KRK are mostly won

    def test_the_verifier_accepts_the_file(self):
        data, _, _ = es.generate(str(TABLES), {'KQvK': 1}, 300, seed=11)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'slice.vf'
            path.write_bytes(data)
            totals = {}
            games, positions = vg.verify_file(str(path), es.TABLE_PIECES, totals)
        self.assertEqual((games, positions), (300, 300))
        self.assertEqual(totals, {'table': 300})

    def test_seeded(self):
        a = es.generate(str(TABLES), {'KRvK': 1}, 50, seed=3)[0]
        b = es.generate(str(TABLES), {'KRvK': 1}, 50, seed=3)[0]
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
