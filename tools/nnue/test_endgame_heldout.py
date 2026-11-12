# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of endgame_heldout.py: its position key is the slice's own board bytes (endgame_slice.encode, decoded by
verify_games.py's decoder), the overlap scan finds a planted position and counts material classes, the committed
position file holds what its docstring says (classes outside the slice's generator, quiet, legal, no repeats,
per-class counts), and the misjudged rule is endgame_check.py's."""
import json
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


class Flag(unittest.TestCase):
    def test_flag_limit(self):
        # Owner, 2026-11-11: flagged when the candidate's count rises more than 15% over the default's.
        self.assertEqual(eh.FLAG_RATIO, 1.15)
        line, flagged = eh.flag_line('cand', (704, 3800), 'r8brft1', (612, 3800))  # 704 / 612 = 1.1503
        self.assertTrue(flagged)
        self.assertIn('cand 704 of 3800', line)
        self.assertIn('r8brft1 612 of 3800', line)
        self.assertIn('ratio 1.150', line)
        self.assertIn("FLAG for the owner's review", line)
        line, flagged = eh.flag_line('cand', (703, 3800), 'r8brft1', (612, 3800))  # 1.1487
        self.assertFalse(flagged)
        self.assertIn('within the flag limit', line)
        self.assertTrue(eh.flag_line('cand', (1, 10), 'ref', (0, 10))[1])
        self.assertFalse(eh.flag_line('cand', (0, 10), 'ref', (0, 10))[1])

    def test_report_flags_a_worse_net_and_exits_zero(self):
        # The fault case on real nets: S512+PP (945) against r8brft1 (612) is flagged; r8brft1 against itself not.
        nets = HERE.parent.parent / 'nets'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'r.json'
            self.assertEqual(eh.main(['report', str(FILE), str(nets / 's512pp.fnet'), '--reference',
                                      str(nets / 'r8brft1.fnet'), '--json', str(out)]), 0)
            got = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual((got['candidate_misjudged'], got['reference_misjudged'], got['flagged']), (945, 612, True))
            self.assertEqual(eh.main(['report', str(FILE), str(nets / 'r8brft1.fnet'), '--reference',
                                      str(nets / 'r8brft1.fnet'), '--json', str(out)]), 0)
            got = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual((got['candidate_misjudged'], got['ratio'], got['flagged']), (612, 1.0, False))


class B0(unittest.TestCase):
    def test_a_b0_net_is_evaluated_as_its_parity_file_says(self):
        # The label-depth experiment's B0 candidates go through the same checks (2026-11-12): models.evaluator
        # reads a version-1 net through reference.py; its values equal the R-int column of b0r2's parity file,
        # which the engine's netcheck matches exactly.
        import models
        root = HERE.parent.parent
        evaluate, scale = models.evaluator(str(root / 'nets' / 'b0r2.fnet'), str(HERE / 'b0.json'))
        lines = [l for l in (root / 'tests' / 'nnue' / 'b0r2.parity').read_text(encoding='utf-8').splitlines()
                 if '|' in l and not l.startswith(('#', '{'))][:12]
        self.assertEqual(len(lines), 12)
        for line in lines:
            fen, _, value = line.rpartition('|')
            self.assertEqual(evaluate(chess.Board(fen.strip())), int(value.split()[0]), fen)
        self.assertEqual(scale, json.loads((root / 'tests' / 'nnue' / 'b0r2.parity').read_text(
            encoding='utf-8').splitlines()[0])['scale'])

    def test_report_runs_on_a_b0_candidate(self):
        nets = HERE.parent.parent / 'nets'
        rows = eh.read(FILE)[:40]
        res = eh.check(rows, [f"{nets / 'b0r2.fnet'}={HERE / 'b0.json'}"])
        self.assertEqual(sum(v[0] for v in res['b0r2'].values()), 40)


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
