# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/datagen/defense_starts.py (ideas.md 66; docs/research/defense-slices/pilot.md):
the slices' selection rules on hand-made shards, the score and result conversion to the side to move,
the matching of played games back to their starts, and the offline gate's arithmetic.

    python -I -B -m unittest discover -s tools/datagen -p 'test_*.py'
"""
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import defense_starts as ds  # noqa: E402
import verify_games as vg  # noqa: E402

NIBBLE = {chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5}

# Both queens on, equal pieces, pawns level (the position after 1.e4 e5 2.Nf3 Nc6, then 3.Bc4 Bc5).
ITALIAN = 'r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4'
# The same with Black's d-pawn and e-pawn gone: two pawns apart.
TWO_DOWN = 'r1bqk1nr/ppp2ppp/2n5/2b5/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4'
# No queens.
NO_QUEENS = 'r1b1k1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNB1K2R w KQkq - 4 4'


def encode_board(board, result_white):
    """The 32-byte start board (verify_games.decode_board's layout; castling rooks as type 6)."""
    occ = 0
    nibbles = []
    rooks = {chess.H1: chess.BB_H1, chess.A1: chess.BB_A1, chess.H8: chess.BB_H8, chess.A8: chess.BB_A8}
    for sq in range(64):
        p = board.piece_at(sq)
        if p is None:
            continue
        occ |= 1 << sq
        kind = NIBBLE[p.piece_type]
        if p.piece_type == chess.ROOK and sq in rooks and board.castling_rights & rooks[sq]:
            kind = 6
        nibbles.append(kind | (8 if p.color == chess.BLACK else 0))
    packed = bytearray(16)
    for k, n in enumerate(nibbles):
        packed[k // 2] |= n << (4 * (k % 2))
    ep = board.ep_square if board.ep_square is not None and board.has_legal_en_passant() else 64
    head = struct.pack('<Q', occ) + bytes(packed)
    head += bytes([(0 if board.turn == chess.WHITE else 128) | ep, board.halfmove_clock])
    return head + struct.pack('<H', board.fullmove_number) + struct.pack('<h', 0) + bytes([result_white, 0])


def encode_game(fen, moves, white_scores, result_white):
    """One viriformat game from `fen`: each UCI move with its White-view score, then the terminator."""
    board = chess.Board(fen)
    out = bytearray(encode_board(board, result_white))
    for uci, score in zip(moves, white_scores, strict=True):
        move = chess.Move.from_uci(uci)
        out += struct.pack('<Hh', vg.code_of(board, move), score)
        board.push(move)
    return bytes(out + struct.pack('<Hh', 0, 0))


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def shard(self, name, games):
        path = self.dir / name
        path.write_bytes(b''.join(games))
        return str(path)


class ClassifyTests(Fixture):
    def rows(self, fen, moves, scores, result=1):
        path = self.shard('t.vf', [encode_game(fen, moves, scores, result)])
        return list(ds.positions(path))

    def test_a_quiet_level_position_in_the_band_is_positional(self):
        (p,) = self.rows(ITALIAN, ['c2c3'], [150])
        self.assertEqual(ds.slices_of(p), {'positional'})
        self.assertEqual(p.score, 150)

    def test_the_band_is_on_the_absolute_score_and_inclusive(self):
        for score, want in ((79, set()), (80, {'positional'}), (400, {'positional'}), (401, set()),
                            (-80, {'positional'}), (-99, {'positional'}), (-100, {'positional', 'defense'}),
                            (-300, {'positional', 'defense'}), (-301, {'positional'}), (-401, set())):
            (p,) = self.rows(ITALIAN, ['c2c3'], [score])
            self.assertEqual(ds.slices_of(p), want, score)

    def test_scores_and_results_are_read_from_the_side_to_move(self):
        # Black to move after 4.c3: a White-view +150 is -150 for Black (a defense start); the stored
        # result 2 (White won) is a loss for Black.
        _, p = self.rows(ITALIAN, ['c2c3', 'g8f6'], [0, 150], result=2)
        self.assertEqual(p.board.turn, chess.BLACK)
        self.assertEqual(p.score, -150)
        self.assertEqual(p.result, 0.0)
        self.assertEqual(ds.slices_of(p), {'positional', 'defense'})

    def test_two_pawns_apart_is_defense_only(self):
        (p,) = self.rows(TWO_DOWN, ['c2c3'], [200])
        self.assertEqual(ds.slices_of(p), set())  # +200 for the side to move: not a defense start
        _, q = self.rows(TWO_DOWN, ['c2c3', 'g8f6'], [0, 200])
        self.assertEqual(ds.slices_of(q), {'defense'})

    def test_queens_off_is_neither(self):
        _, p = self.rows(NO_QUEENS, ['c2c3', 'g8f6'], [0, 150])
        self.assertEqual(ds.slices_of(p), set())

    def test_unequal_pieces_are_not_positional(self):
        # Bishop against knight (equal counts, different pieces) is the taxonomy's B-vs-N, not equal pieces.
        fen = 'r1bqk2r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4'
        _, p = self.rows(fen, ['c2c3', 'f6g4'], [0, 150])
        self.assertEqual(ds.slices_of(p), {'defense'})

    def test_check_capture_promotion_and_unsaved_records_are_excluded(self):
        (p,) = self.rows(ITALIAN, ['c4f7'], [150])  # a capture (and check)
        self.assertEqual(ds.slices_of(p), set())
        (p,) = self.rows(ITALIAN, ['c2c3'], [vg.UNSAVED_SCORE])
        self.assertEqual(ds.slices_of(p), set())
        (p,) = self.rows(ITALIAN, ['c2c3'], [20001])
        self.assertEqual(ds.slices_of(p), set())
        checked = 'r1bqk1nr/pppp1Bpp/2n5/2b1p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 0 4'
        (p,) = self.rows(checked, ['e8f7'], [-150])
        self.assertEqual(ds.slices_of(p), set())

    def test_castling_and_promotion_codes_replay(self):
        # Castling is coded king-to-rook; the replay must reach the castled position.
        _, p = self.rows(ITALIAN, ['e1h1', 'g8f6'], [0, 0])
        self.assertEqual(p.board.piece_at(chess.G1), chess.Piece(chess.KING, chess.WHITE))
        self.assertEqual(p.board.piece_at(chess.F1), chess.Piece(chess.ROOK, chess.WHITE))
        promo = '8/P6k/8/8/8/8/6K1/8 w - - 0 1'
        p, q = self.rows(promo, ['a7a8q', 'h7h6'], [500, 600])
        self.assertTrue(p.tactical)
        self.assertEqual(q.board.piece_at(chess.A8), chess.Piece(chess.QUEEN, chess.WHITE))


class SelectTests(Fixture):
    def make(self):
        games = []
        for k in range(12):
            moves = ['c2c3', 'g8f6', 'd2d3', 'd7d6', 'h2h3']
            games.append(encode_game(ITALIAN, moves, [150, 150 + k, -120, 200, 150], 1))
        return self.shard('s-w00.vf', games)

    def test_at_most_one_start_per_game_and_slice_and_never_the_same_position_twice(self):
        path = self.make()
        out = ds.select([path], seed=7)
        for name in ('positional', 'defense'):
            games = [(r['shard'], r['game']) for r in out['rows'][name]]
            self.assertEqual(len(games), len(set(games)), name)
        keys = [r['key'] for name in ('positional', 'defense') for r in out['rows'][name]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(out['pool']['positional']['games'], 12)
        self.assertEqual(out['pool']['positional']['positions'], 12 * 5)  # every |score| is in 80-400
        # Defense: plies 1 (+150+k for White = -(150+k) for Black), 2 (-120, White to move) and 3 (+200:
        # -200 for Black).
        self.assertEqual(out['pool']['defense']['positions'], 12 * 3)
        # The twelve games repeat one move sequence: each position is kept once over both slices.
        self.assertLessEqual(len(keys), 5)

    def test_the_draw_is_reproducible_and_seeded(self):
        path = self.make()
        a = ds.select([path], seed=7)
        b = ds.select([path], seed=7)
        c = ds.select([path], seed=8)
        self.assertEqual(a['rows'], b['rows'])
        self.assertNotEqual([r['id'] for r in a['rows']['positional']], [r['id'] for r in c['rows']['positional']])

    def test_excluded_keys_are_dropped(self):
        path = self.make()
        first = ds.select([path], seed=7)
        keys = {r['key'] for r in first['rows']['positional']}
        again = ds.select([path], seed=7, exclude=keys)
        self.assertTrue(all(r['key'] not in keys for r in again['rows']['positional']))

    def test_rows_round_trip_through_the_tsv_and_the_openings_file(self):
        path = self.make()
        out = ds.select([path], seed=7)
        tsv = self.dir / 'p.tsv'
        ds.write_rows(tsv, out['rows']['positional'])
        back = ds.read_rows(tsv)
        self.assertEqual(back, out['rows']['positional'])
        fens = self.dir / 'p.epd'
        ds.write_openings(fens, back, 3, 'test')
        lines = [l for l in fens.read_text().splitlines() if l and not l.startswith('#')]
        self.assertEqual(lines, [r['fen'] for r in back[:3]])
        for line in lines:
            self.assertTrue(chess.Board(line).is_valid())


class PlayedAndGateTests(Fixture):
    def test_played_games_are_matched_to_their_starts(self):
        rows = [{'id': 'a:0:1', 'key': ds.key_of(chess.Board(ITALIAN)), 'fen': ITALIAN},
                {'id': 'a:3:2', 'key': ds.key_of(chess.Board(TWO_DOWN)), 'fen': TWO_DOWN}]
        # Played from TWO_DOWN (White to move): first score +40 for White, Black won.
        path = self.shard('pilot.vf', [encode_game(TWO_DOWN, ['c2c3', 'g8f6'], [40, 60], 0)])
        got = ds.played(rows, [path])
        self.assertEqual(got, [{'id': 'a:3:2', 'score': 40, 'result': 0.0, 'positions': 2}])

    def test_gate_arithmetic(self):
        s = 92.0
        sig = lambda v: 1 / (1 + math.exp(-v / s))  # noqa: E731
        rows = {'x': {'score': 100, 'result': 0.5}, 'y': {'score': -150, 'result': 0.0},
                'z': {'score': 10, 'result': 0.5}}
        pilot = {'x': {'score': 200, 'result': 1.0}, 'y': {'score': -300, 'result': 0.0},
                 'z': {'score': 0, 'result': 0.5}}
        gold = {'x': 250, 'y': -400, 'z': 20}  # z: |gold| < 50, left out
        r = ds.gate(rows, pilot, gold, scale=s, result_weight=0.5, boot=200, seed=1)
        self.assertEqual(r['n'], 2)
        std = [(0.5 * sig(100) + 0.25) - 0.5, -((0.5 * sig(-150) + 0.0) - 0.5)]
        pil = [(0.5 * sig(200) + 0.5) - 0.5, -((0.5 * sig(-300) + 0.0) - 0.5)]
        self.assertAlmostEqual(r['standard'], sum(std) / 2, places=9)
        self.assertAlmostEqual(r['pilot'], sum(pil) / 2, places=9)
        self.assertAlmostEqual(r['difference'], r['pilot'] - r['standard'], places=12)
        self.assertTrue(r['pass'])
        lo, hi = r['difference_ci']
        self.assertLessEqual(lo, r['difference'])
        self.assertGreaterEqual(hi, r['difference'])


if __name__ == '__main__':
    unittest.main()
