# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of endgame_heldout.py: its position key is the slice's own board bytes (endgame_slice.encode, decoded by
verify_games.py's decoder), the overlap scan finds a planted position and counts material classes, the committed
position file holds what its docstring says (classes outside the slice's generator, quiet, legal, no repeats,
per-class counts), and the misjudged rule is endgame_check.py's."""
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import chess

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'datagen'))
import endgame_check  # noqa: E402
import endgame_heldout as eh  # noqa: E402
import endgame_slice as es  # noqa: E402
import verify_games as vg  # noqa: E402

FILE = HERE / 'endgame_heldout.tsv'


def record(board):
    move = next(m for m in board.legal_moves if not board.is_capture(m))
    return es.encode(board, move, 1, 0)


class Key(unittest.TestCase):
    def test_key_is_the_slice_records_board_and_side(self):
        for fen in ('8/8/8/4k3/8/8/3QK3/8 b - - 0 1', '8/2p5/8/4k3/1R6/8/3PK3/8 w - - 0 1',
                    '8/8/1n6/4k3/8/2B5/3NK3/8 b - - 0 1'):
            board = chess.Board(fen)
            data = record(board)
            occ_packed, black = eh.key(board)
            self.assertEqual(occ_packed, data[:24])
            self.assertEqual(black, bool(data[24] & 128))
            back, _ = vg.decode_board(data[:32])
            self.assertEqual(eh.key(back), eh.key(board))

    def test_side_to_move_separates_keys(self):
        w = chess.Board('8/8/8/4k3/8/8/3QK3/8 w - - 0 1')
        b = chess.Board('8/8/8/4k3/8/8/3QK3/8 b - - 0 1')
        self.assertNotEqual(eh.key(w), eh.key(b))

    def test_material_class_names(self):
        self.assertEqual(eh.material_class(['KR', 'KQ']), 'KQvKR')
        self.assertEqual(eh.material_class(['KQ', 'KNB']), 'KBNvKQ')
        self.assertEqual(eh.board_class(chess.Board('8/8/8/4k3/1r6/8/3PK3/8 w - - 0 1')), 'KRvKP')
        self.assertEqual(eh.material_class(['K', 'KRP']), eh.material_class(['KPR', 'K']))


class Scan(unittest.TestCase):
    def test_a_planted_position_is_found_and_classes_counted(self):
        rows = eh.read(FILE)
        planted = rows[17][2]
        other = chess.Board('8/8/8/4k3/8/8/3QK3/8 b - - 0 1')  # KQvK, not in the check
        flipped = planted.copy()
        flipped.turn = not flipped.turn  # same board, other side to move: must not match
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'slice.vf'
            data = record(other) + record(planted)
            if flipped.is_valid() and any(not flipped.is_capture(m) for m in flipped.legal_moves):
                data += record(flipped)
            path.write_bytes(data)
            rep = eh.overlap(rows, [str(path)])
        self.assertEqual(rep['matches']['held-out']['found_in_any_file'], 1)
        self.assertEqual(rep['matches']['held-out']['by_class'], {eh.board_class(planted): 1})
        self.assertEqual(rep['classes'].get('KQvK'), 1)
        self.assertIn(eh.board_class(planted), rep['held_out_classes_in_slice'])

    def test_a_record_that_is_not_a_one_move_game_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.vf'
            data = bytearray(record(chess.Board('8/8/8/4k3/8/8/3QK3/8 b - - 0 1')))
            data[38] = 1
            path.write_bytes(bytes(data))
            with self.assertRaises(ValueError):
                eh.scan(path, set())


class CommittedFile(unittest.TestCase):
    def test_positions(self):
        rows = eh.read(FILE)
        self.assertEqual(len(rows), eh.PER_CLASS * len(eh.CLASSES))
        self.assertEqual(Counter(c for c, _, _ in rows), {c: eh.PER_CLASS for c in eh.CLASSES})
        seen = set()
        for cls, wdl, b in rows:
            self.assertEqual(eh.board_class(b), eh.material_class(cls.split('v')))
            self.assertTrue(b.is_valid())
            self.assertFalse(b.is_check())
            self.assertFalse(any(b.is_capture(m) for m in b.legal_moves))
            self.assertFalse(b.is_game_over())
            self.assertIn(wdl, (-2, -1, 0, 1, 2))
            self.assertNotIn(eh.key(b), seen)
            seen.add(eh.key(b))

    def test_classes_are_outside_the_slice_generator(self):
        # The slice draws BASIC (3 pieces) and table-entry signatures, which have 5 pieces: no 4-piece class,
        # and the 5-piece classes here are absent from its signature list (checked on the files by `overlap`).
        basic = {eh.material_class(s.split('v')) for s in es.BASIC}
        for cls in eh.CLASSES:
            self.assertNotIn(eh.material_class(cls.split('v')), basic)
        self.assertTrue(all(len(c) - 1 == 4 for c in eh.CLASSES_4))
        self.assertTrue(all(len(c) - 1 == 5 for c in eh.CLASSES_5))


class Rule(unittest.TestCase):
    def test_misjudged_rule_is_endgame_checks(self):
        self.assertTrue(endgame_check.misjudged('won', 99))
        self.assertFalse(endgame_check.misjudged('won', 100))
        self.assertTrue(endgame_check.misjudged('lost', -99))
        self.assertFalse(endgame_check.misjudged('lost', -100))
        self.assertTrue(endgame_check.misjudged('drawn', 201))
        self.assertFalse(endgame_check.misjudged('drawn', -200))
        self.assertEqual([endgame_check.verdict(w) for w in (-2, -1, 0, 1, 2)],
                         ['lost', 'lost', 'drawn', 'won', 'won'])


if __name__ == '__main__':
    unittest.main()
