# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for tools/zugzwang/zugzwang_set.py.

    .venv/Scripts/python.exe -I tools/zugzwang/test_zugzwang_set.py

- the zugzwang rule on every pair of WDL values, against a separate enumeration written from the definition;
- the solved rule and the UCI info parser on hand-written results;
- the committed set's 3-5-piece rows re-probed with Syzygy (skipped when the tables are absent; FORK_SYZYGY or
  ~/fork-data/syzygy/3-4-5), and the checker shown able to fail: a row with its side to move flipped, its WDL
  changed, or a kept move dropped must be reported.
"""
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chess  # noqa: E402

import zugzwang_set as z  # noqa: E402

SET = HERE / 'zugzwang_set.tsv'
SYZYGY = os.environ.get('FORK_SYZYGY', str(Path.home() / 'fork-data' / 'syzygy' / '3-4-5'))


class Rule(unittest.TestCase):
    def test_every_pair(self):
        values = (-2, -1, 0, 1, 2)
        for a in values:
            for b in values:
                # Independent statement: S to move gets a; if S could pass, O would be to move and S would get -b.
                exact = a in (-2, 0, 2) and b in (-2, 0, 2)
                worse_to_move = exact and a < -b
                got = z.zugzwang_type(a, b)
                self.assertEqual(got is not None, worse_to_move, (a, b))
                if got:
                    self.assertEqual(got, {0: 'D', -2: 'L'}[a] + '/' + {0: 'D', -2: 'L'}[b])

    def test_symmetric(self):
        for a in (-2, 0, 2):
            for b in (-2, 0, 2):
                self.assertEqual(z.zugzwang_type(a, b) is None, z.zugzwang_type(b, a) is None)


class Solved(unittest.TestCase):
    drawn = {'wdl_stm': 0, 'kept_moves': 'a1a2 b1b2'}
    lost = {'wdl_stm': -2, 'kept_moves': '*'}

    def res(self, kind, score, move='a1a2'):
        return {'kind': kind, 'score': score, 'bestmove': move}

    def test_drawn(self):
        self.assertEqual(z.solved(self.drawn, self.res('cp', 200)), (True, True))
        self.assertEqual(z.solved(self.drawn, self.res('cp', -200, 'b1b2')), (True, True))
        self.assertEqual(z.solved(self.drawn, self.res('cp', 201)), (False, True))
        self.assertEqual(z.solved(self.drawn, self.res('cp', 0, 'c1c2')), (True, False))
        self.assertEqual(z.solved(self.drawn, self.res('mate', 3)), (False, True))
        self.assertEqual(z.solved(self.drawn, self.res('mate', -3)), (False, True))
        self.assertEqual(z.solved({'wdl_stm': 0, 'kept_moves': '?'}, self.res('cp', 0)), (True, None))

    def test_lost(self):
        self.assertEqual(z.solved(self.lost, self.res('cp', -100)), (True, None))
        self.assertEqual(z.solved(self.lost, self.res('cp', -99)), (False, None))
        self.assertEqual(z.solved(self.lost, self.res('mate', -5)), (True, None))
        self.assertEqual(z.solved(self.lost, self.res('mate', 5)), (False, None))

    def test_parse_info(self):
        line = 'info depth 17 seldepth 30 score cp -123 nodes 456789 nps 1 hashfull 3 tbhits 0 time 812 pv a2a3'
        self.assertEqual(z.parse_info(line), (17, 'cp', -123, 456789, 812))
        self.assertEqual(z.parse_info('info depth 9 score mate -4 nodes 10 time 2')[:3], (9, 'mate', -4))
        self.assertIsNone(z.parse_info('info depth 9 score cp 10 lowerbound nodes 10 time 2'))
        self.assertIsNone(z.parse_info('info string nodes 10'))


def encode_game(board, moves):
    """A viriformat game (the layout tools/datagen/verify_games.py decode_board reads: occupancy, a 4-bit code
    per piece with 6 for a rook that can castle, side to move and en passant, clocks, score, result, reserved),
    then each move's code (verify_games.code_of) with a zero score, then the terminator."""
    sys.path.insert(0, str(HERE.parent / 'datagen'))
    import verify_games
    occ, nib = 0, []
    corners = {chess.A1: chess.BB_A1, chess.H1: chess.BB_H1, chess.A8: chess.BB_A8, chess.H8: chess.BB_H8}
    for sq in range(64):
        p = board.piece_at(sq)
        if p:
            occ |= 1 << sq
            code = p.piece_type - 1
            if p.piece_type == chess.ROOK and sq in corners and board.castling_rights & corners[sq]:
                code = 6
            nib.append(code | (8 if p.color == chess.BLACK else 0))
    packed = bytearray(16)
    for t, v in enumerate(nib):
        packed[t // 2] |= v << (4 * (t % 2))
    ep = 64 if board.ep_square is None else board.ep_square
    head = occ.to_bytes(8, 'little') + bytes(packed) + bytes([ep | (128 if board.turn == chess.BLACK else 0), 0,
                                                              1, 0, 0, 0, 1, 0])
    body = bytearray()
    b = board.copy()
    for m in moves:
        body += verify_games.code_of(b, m).to_bytes(2, 'little') + b'\0\0'
        b.push(m)
    return head + bytes(body) + b'\0\0\0\0'


class Harvest(unittest.TestCase):
    def test_replay_matches_python_chess(self):
        """game_positions on synthetic random games equals a python-chess replay with the same filters."""
        import random
        import tempfile
        rng = random.Random(7)
        data, want = bytearray(), []
        for g in range(40):
            b = chess.Board()
            moves = []
            while not b.is_game_over() and len(moves) < 400:
                ms = list(b.legal_moves)
                caps = [m for m in ms if b.is_capture(m)]
                m = rng.choice(caps if caps and rng.random() < 0.7 else ms)  # captures, so endings come
                moves.append(m)
                b.push(m)
            data += encode_game(chess.Board(), moves)
            r = chess.Board()
            for step in range(len(moves) + 1):
                last = r.peek() if r.move_stack else None
                double = (last is not None and r.piece_type_at(last.to_square) == chess.PAWN
                          and abs(last.to_square - last.from_square) == 16)
                if (len(r.piece_map()) <= 7 and not r.castling_rights and not double and not r.is_check()
                        and z.has_piece(r, r.turn) and not r.is_checkmate() and not r.is_stalemate()):
                    want.append((g, r.board_fen(), r.turn))
                if step < len(moves):
                    r.push(moves[step])
        self.assertGreater(len(want), 100)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'games.vf'
            path.write_bytes(bytes(data))
            got = [(g, b.board_fen(), b.turn) for g, b in z.game_positions(path, 7)]
            self.assertEqual(got, want)
            # The checker can fail: the first game's side to move flipped in its header changes what is replayed.
            bad = bytearray(data)
            bad[24] ^= 128
            path.write_bytes(bytes(bad))
            self.assertNotEqual([(g, b.board_fen(), b.turn) for g, b in z.game_positions(path, 7)][:len(want)],
                                want)


class Files(unittest.TestCase):
    """What can be checked without tables: every row of both committed files is a legal position whose stated
    moves are legal, and a set row's type is the rule's verdict on its own two WDL columns."""

    def test_rows(self):
        for path in (SET, HERE / 'published_cpw.tsv'):
            for r in z.read_rows(path):
                b = chess.Board(r['fen'])
                self.assertTrue(b.is_valid(), r['id'])
                self.assertEqual(len(b.piece_map()), r['pieces'], r['id'])
                self.assertEqual(r['material'], z.canonical(z.material_of(b), (r['material'],)), r['id'])
                legal = {m.uci() for m in b.legal_moves}
                if r['kept_moves'] not in ('*', '?'):
                    self.assertTrue(set(r['kept_moves'].split()) <= legal, r['id'])
                if r['type'] == 'published':
                    self.assertTrue(r['source'].startswith('cpw:'))
                    continue
                self.assertEqual(z.zugzwang_type(r['wdl_stm'], r['wdl_other_to_move']), r['type'], r['id'])
                self.assertTrue(z.has_piece(b, b.turn), r['id'])
                self.assertFalse(b.is_check() or b.castling_rights or b.ep_square is not None, r['id'])


@unittest.skipUnless(SET.exists() and Path(SYZYGY).is_dir(), 'set or Syzygy 3-4-5 tables absent')
class CommittedSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tb, cls.probe = z.syzygy_prober(SYZYGY)
        cls.rows = z.read_rows(SET)

    @classmethod
    def tearDownClass(cls):
        cls.tb.close()

    def test_rows_hold(self):
        small = [r for r in self.rows if r['pieces'] <= 5]
        self.assertTrue(small)
        for r in small:
            self.assertEqual(z.verify_row(self.probe, r), [], r['id'])

    def test_header_and_ids(self):
        self.assertEqual([r['id'] for r in self.rows], [f'z{i:03d}' for i in range(1, len(self.rows) + 1)])
        self.assertEqual(len({chess.Board(r['fen']).board_fen() for r in self.rows}), len(self.rows))

    def test_checker_can_fail(self):
        r = next(r for r in self.rows if r['pieces'] <= 5 and r['type'] == 'D/L' and r['kept_moves'] not in '*?')
        flipped = dict(r, fen=z.other_to_move(chess.Board(r['fen'])).fen())
        self.assertTrue(z.verify_row(self.probe, flipped))
        self.assertTrue(z.verify_row(self.probe, dict(r, wdl_stm=-2)))
        self.assertTrue(z.verify_row(self.probe, dict(r, kept_moves=' '.join(r['kept_moves'].split()[1:]))))


if __name__ == '__main__':
    unittest.main()
