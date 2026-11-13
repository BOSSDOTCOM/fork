# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/datagen/td_labels.py (ideas.md 51): the lambda limits, a
hand-worked game, every kind of game end, the shard copy, the comparison
mode, and two injected faults that the limit check must catch.

The games are built here with python-chess and written in the shard format
by this file's own encoder (from verify_games.py's decoder layout); every
end position is checked by python-chess (checkmate, stalemate and so on)
before it is used.

    python -I -B -m unittest discover -s tools/datagen -p 'test_*.py'
"""
import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import td_labels as td  # noqa: E402
import verify_games as vg  # noqa: E402

U = vg.UNSAVED_SCORE
KIND = {chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5}
CORNER_RIGHT = {chess.H1: chess.BB_H1, chess.A1: chess.BB_A1, chess.H8: chess.BB_H8, chess.A8: chess.BB_A8}


def encode_game(fen, moves, scores, result):
    """One game in the shard format: the 32-byte board, (move code, White-view
    score) per record, the terminator. `result` is the stored byte (0 Black
    wins, 1 draw, 2 White wins)."""
    board = chess.Board(fen)
    occ, nibbles = 0, []
    for sq in range(64):
        p = board.piece_at(sq)
        if p is None:
            continue
        occ |= 1 << sq
        kind = KIND[p.piece_type]
        if p.piece_type == chess.ROOK and board.castling_rights & CORNER_RIGHT.get(sq, 0):
            kind = 6
        nibbles.append(kind | (8 if p.color == chess.BLACK else 0))
    packed = bytearray(16)
    for k, n in enumerate(nibbles):
        packed[k // 2] |= n << (4 * (k % 2))
    ep = board.ep_square if board.ep_square is not None else 64
    head = struct.pack('<Q', occ) + bytes(packed)
    head += bytes([(128 if board.turn == chess.BLACK else 0) | ep, board.halfmove_clock])
    head += struct.pack('<Hh', board.fullmove_number, 0) + bytes([result, 0])
    body = b''
    for uci, s in zip(moves, scores, strict=True):
        move = chess.Move.from_uci(uci)
        assert move in board.legal_moves, (uci, board.fen())
        body += struct.pack('<Hh', vg.code_of(board, move), s)
        board.push(move)
    return head + body + struct.pack('<Hh', 0, 0), board


# Fool's mate: 1. f3 e5 2. g4 Qh4#. Record 1 unsaved, record 3 a mate score
# for Black (White's view), stored result 0-1.
FOOL = (chess.STARTING_FEN, ['f2f3', 'e7e5', 'g2g4', 'd8h4'], [0, U, -100, -29990], 0)


def sig(x):
    return 1.0 / (1.0 + math.exp(-x))


def check_limits(targets, scale=100.0):
    """lambda = 0 gives each saved record's own sigmoid(s / S) and lambda = 1
    the stored result, on a fixed set of score chains; raises AssertionError
    otherwise. `targets` has td_targets' signature."""
    chains = [([0, U, -100, -29990], 0), ([35, -20, U, U, 80, 900], 2), ([10, -10, 0, 5], 1),
              ([U, 400, U], 2), ([-250], 0)]
    for scores, result in chains:
        for unsaved in ('next', 'drop'):
            got0 = targets(scores, result, 0.0, scale, unsaved=unsaved)
            got1 = targets(scores, result, 1.0, scale, unsaved=unsaved)
            for s, a, b in zip(scores, got0, got1):
                if s == U:
                    assert a is None and b is None, (scores, a, b)
                    continue
                assert math.isclose(a, sig(s / scale), rel_tol=0, abs_tol=1e-12), (scores, s, a)
                assert math.isclose(b, (0.0, 0.5, 1.0)[result], rel_tol=0, abs_tol=1e-12), (scores, s, b)


class LimitTests(unittest.TestCase):
    def test_lambda_zero_is_the_score_and_one_the_result(self):
        check_limits(td.td_targets)

    def test_lambda_zero_copies_a_shard_byte_for_byte(self):
        # Decided scores too: the (T, 1 - T) chain keeps sigmoid(5000 / 92)'s
        # complement, so the score comes back exactly.
        data, _ = encode_game(chess.STARTING_FEN, ['e2e4', 'e7e5', 'g1f3'], [5000, -20000, 19999], 2)
        data += encode_game(*FOOL)[0]
        out, counts = td.relabel_shard(data, 0.0, 92.0)
        self.assertEqual(out, data)
        self.assertEqual(counts, {'games': 2, 'records': 7, 'relabelled': 5, 'unsaved': 1, 'in_check': 0,
                                  'beyond_limit': 1, 'clamped': 1, 'one_move': 0, 'unsaved_labelled': 0,
                                  'unsaved_decided': 0})

    def test_weights_sum_to_one(self):
        # A constant chain with the same terminal value is a fixed point of any lambda.
        for lam in (0.0, 0.3, 0.9, 1.0):
            got = td.td_targets([0, U, 0, 0], 1, lam, 92.0)
            for g in got:
                self.assertTrue(g is None or math.isclose(g, 0.5, abs_tol=1e-15))

    def test_lambda_outside_the_interval_is_refused(self):
        with self.assertRaises(ValueError):
            td.td_targets([0], 1, 1.5, 92.0)


class InCheckTests(unittest.TestCase):
    """1. e4 f6 2. Qh5+ g6: record 3's position is in check (python-chess
    confirms), searched with fewer nodes, so its score stays out of the
    chain by default. At S = 100, lambda = 0.5, z = 1/2:
    U4 = 0.5; U3 (outside the chain: the next value is z) = 0.5;
    U2 = 0.5 sigmoid(3) + 0.5 U3 = 0.5 * 0.952574127 + 0.25 = 0.726287063.
    With --check-scores keep: T3 = 0.5 sigmoid(-4) + 0.25 = 0.5 * 0.017986210 + 0.25 = 0.258993105."""

    MOVES = ['e2e4', 'f7f6', 'd1h5', 'g7g6']
    SCORES = [10, -20, 300, -400]

    def test_check_flags_and_labels(self):
        data, board = encode_game(chess.STARTING_FEN, self.MOVES, self.SCORES, 1)
        _, head, recs, _ = list(td.split_games(data))[0]
        flags = td.check_flags(head, recs)
        self.assertEqual(flags, [False, False, False, True])
        self.assertEqual(flags, [r[3] for r in td.replay(head, recs, table_pieces=0)[0]])
        got = td.td_targets(self.SCORES, 1, 0.5, 100.0, skip=flags)
        self.assertIsNone(got[3])
        self.assertAlmostEqual(got[2], 0.7262870634, places=9)
        self.assertAlmostEqual(td.td_targets(self.SCORES, 1, 0.5, 100.0)[3], 0.2589931050, places=9)
        out, counts = td.relabel_shard(data, 0.5, 100.0)
        self.assertEqual(counts['in_check'], 1)
        self.assertEqual(list(td.split_games(out))[0][2][3], recs[3])  # unchanged
        out_keep, counts_keep = td.relabel_shard(data, 0.5, 100.0, check_scores='keep')
        self.assertEqual(counts_keep['in_check'], 0)
        self.assertNotEqual(out_keep, out)

    def test_unchecked_replay_reads_castling_ep_and_promotion(self):
        # The fast replay against the legal one on special moves.
        fen = 'r3k2r/1P6/8/3pP3/8/8/8/R3K2R w KQkq d6 0 1'
        board = chess.Board(fen)
        for uci in ('e1g1', 'e1c1', 'e5d6', 'b7b8q', 'b7a8n'):
            move = chess.Move.from_uci(uci)
            self.assertIn(move, board.legal_moves)
            self.assertEqual(td.move_of(board, vg.code_of(board, move)), move)


class HandWorkedGameTests(unittest.TestCase):
    """Fool's mate at S = 100, lambda = 0.5 (worked by hand):
    v0 = sigmoid(0) = 0.5, v2 = sigmoid(-1) = 0.2689414214, v3 =
    sigmoid(-299.9) ~ 5e-131 (taken as 0), z = 0 (Black won).
    Plies (default, an unsaved ply takes the next saved value):
      U4 = z = 0
      U3 = 0.5 v3 + 0.5 U4 = 0
      U2 = 0.5 v2 + 0.5 U3 = 0.1344707107
      U1 = 0.5 v2 + 0.5 U2 = 0.2017060660  (record 1 unsaved: no label)
      U0 = 0.5 v0 + 0.5 U1 = 0.3508530330
    --unsaved drop (chain over records 0, 2, 3): U0 = 0.25 + 0.5 U2 = 0.3172353553.
    --from-next: T0 = U1 = 0.2017060660, T2 = U3 = 0, T3 = U4 = 0.
    Side to move: records 0 and 2 White (labels as above), record 3 Black (1 - T).
    Copy scores: round(100 ln(0.350853 / 0.649147)) = round(-61.53) = -62;
    round(100 ln(0.134471 / 0.865529)) = round(-186.19) = -186; the unsaved
    record and the mate score (|s| > 20,000) unchanged."""

    def test_labels(self):
        scores, result = FOOL[2], FOOL[3]
        got = td.td_targets(scores, result, 0.5, 100.0)
        self.assertIsNone(got[1])
        for g, want in zip((got[0], got[2], got[3]), (0.3508530330, 0.1344707107, 0.0)):
            self.assertAlmostEqual(g, want, places=10)
        self.assertAlmostEqual(td.td_targets(scores, result, 0.5, 100.0, unsaved='drop')[0], 0.3172353553, places=10)
        nxt = td.td_targets(scores, result, 0.5, 100.0, from_next=True)
        self.assertAlmostEqual(nxt[0], 0.2017060660, places=10)
        self.assertAlmostEqual(nxt[2], 0.0, places=9)

    def test_shard_copy(self):
        data, _ = encode_game(*FOOL)
        out, counts = td.relabel_shard(data, 0.5, 100.0)
        recs = list(td.split_games(out))[0][2]
        self.assertEqual([s for _, s in recs], [-62, U, -186, -29990])
        self.assertEqual(out[:32], data[:32])
        self.assertEqual([c for c, _ in recs], [c for c, _ in list(td.split_games(data))[0][2]])
        self.assertEqual(counts['relabelled'], 2)

    def test_replay_rows(self):
        data, _ = encode_game(*FOOL)
        _, head, recs, _ = list(td.split_games(data))[0]
        rows, kind = td.replay(head, recs)
        self.assertEqual(kind, 'mate score')
        self.assertEqual([r[1] for r in rows], [True, False, True, False])
        # Kept: record 0 and 2 (quiet, saved, |s| <= 20,000); 1 unsaved; 3 a mate score.
        self.assertEqual([r[2] for r in rows], [True, False, True, False])
        self.assertEqual(rows[0][0], ' '.join(chess.STARTING_FEN.split()[:4]))


def game(fen, moves, scores, result, **kw):
    data, board = encode_game(fen, moves, scores, result)
    _, head, recs, _ = list(td.split_games(data))[0]
    rows, kind = td.replay(head, recs, **kw)
    return data, board, rows, kind


class EndKindTests(unittest.TestCase):
    """One game per kind of end; each time lambda = 1 gives the stored result
    from the side to move's view and lambda = 0 the record's own score."""

    def check(self, fen, moves, scores, result, want_kind, board_check=None, **kw):
        data, board, rows, kind = game(fen, moves, scores, result, **kw)
        if board_check:
            self.assertTrue(board_check(board), board.fen())
        self.assertEqual(kind, want_kind)
        z = (0.0, 0.5, 1.0)[result]
        for lam in (0.0, 1.0):
            got = td.td_targets(scores, result, lam, 92.0)
            for s, t, row in zip(scores, got, rows):
                if s == U:
                    continue
                want = z if lam == 1.0 else sig(s / 92.0)
                stm = t if row[1] else 1.0 - t
                self.assertAlmostEqual(stm, want if row[1] else 1.0 - want, places=12)
        return rows

    def test_checkmate_on_the_board(self):
        # The mating move's search was unsaved, so no mate score ends it.
        self.check(FOOL[0], FOOL[1], [0, U, -100, U], 0, 'checkmate', lambda b: b.is_checkmate())

    def test_mate_score(self):
        self.check(*FOOL, 'mate score')

    def test_stalemate(self):
        self.check('7k/8/6K1/8/8/8/8/5Q2 w - - 0 1', ['f1f7'], [0], 1, 'stalemate', lambda b: b.is_stalemate(),
                   table_pieces=0)

    def test_insufficient_material(self):
        rows = self.check('4k3/8/8/8/8/8/3r4/4K3 w - - 0 1', ['e1d2'], [0], 1, 'insufficient material',
                          lambda b: b.is_insufficient_material(), table_pieces=0)
        self.assertFalse(rows[0][2])  # a capture: not kept

    def test_fifty_moves(self):
        self.check('4k3/8/8/8/8/8/8/R3K3 w - - 99 80', ['a1a2'], [300], 1, 'fifty moves',
                   lambda b: b.halfmove_clock == 100, table_pieces=0)

    def test_repetition(self):
        moves = 'g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1 f6g8'.split()
        self.check(chess.STARTING_FEN, moves, [10, -5, U, 0, 12, U, 3, -1], 1, 'repetition',
                   lambda b: b.is_repetition(3))

    def test_repetition_before_the_record(self):
        # tools/datagen/test_verify_games.py's g0 perpetual (Fork's own data).
        fen = '1rbqkbnr/2p3pp/ppp5/5Q2/3PPP2/8/PPP3PP/RNB1K2R w KQ - 2 12'
        moves = 'f5h5 e8e7 h5g5 e7d7 g5f5 d7e7 f5g5 e7d7 g5f5'.split()
        self.check(fen, moves, [400, 380, U, 390, 0, 0, U, 0, 0], 1, 'repetition before the record')

    def test_table_entry(self):
        self.check('4k3/8/8/8/8/8/8/R3K3 w - - 0 1', ['a1a7'], [1500], 2, 'table')

    def test_score_adjudication(self):
        self.check(chess.STARTING_FEN, ['e2e4', 'e7e5'], [800, 900], 2, 'score adjudication',
                   adjudicate=[700, 2])

    def test_unexplained_end_is_reported(self):
        self.check(chess.STARTING_FEN, ['e2e4', 'e7e5'], [800, 900], 2, 'unexplained', table_pieces=0)


class CompareTests(unittest.TestCase):
    def test_matched_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'data').mkdir()
            data = encode_game(chess.STARTING_FEN, ['e2e4'], [20], 1)[0] + encode_game(*FOOL)[0]
            (tmp / 'data' / 'x.vf').write_bytes(data)
            folder = tmp / 'sites'
            folder.mkdir()
            after_f3 = chess.Board()
            after_f3.push_uci('f2f3')
            after_g4 = chess.Board()
            for m in ('f2f3', 'e7e5', 'g2g4'):
                after_g4.push_uci(m)
            sites = [  # record 0 (White), record 1 (unsaved: no match), record 3 (Black), and a stranger
                {'id': 0, 'fen': chess.STARTING_FEN, 'game': 'x.vf#1'},
                {'id': 1, 'fen': after_f3.fen(), 'game': 'x.vf#1'},
                {'id': 2, 'fen': after_g4.fen(), 'game': 'x.vf#1'},
                {'id': 3, 'fen': '4k3/8/8/8/8/8/8/R3K3 w - - 0 1', 'game': 'x.vf#1'},
                {'id': 4, 'fen': chess.STARTING_FEN, 'game': 'x.vf#1'},  # the same record again
            ]
            (folder / 'sites.jsonl').write_text(''.join(json.dumps(s) + '\n' for s in sites), encoding='utf-8')
            (folder / 'deep.tsv').write_text('0\t0\t0\t20\n1\t50\t0\t20\n2\t100\t0\t20\n3\t0\t0\t9\n4\t7\t0\t20\n',
                                             encoding='utf-8')
            rows, stats = td.matched_records([folder], [tmp / 'data'])
            self.assertEqual(stats, {'sites': 5, 'no_shard': 0, 'no_match': 2, 'duplicate': 1})
            self.assertEqual([(r['record'], r['white'], r['kept'], r['end']) for r in rows],
                             [(0, True, True, 'mate score'), (3, False, False, 'mate score')])
            table = td.error_table(rows, 100.0, [0.0, 0.5, 1.0], [0.5])
            # Record 0 at lambda 0.5: 0.350853034 against gold sigmoid(0) = 0.5.
            n, mse, bias = table['kept']['lambda=0.5']
            self.assertEqual(n, 1)
            self.assertAlmostEqual(bias, 0.3508530330 - 0.5, places=9)
            self.assertAlmostEqual(mse, (0.3508530330 - 0.5) ** 2, places=9)
            # Record 3, Black to move: its label 1 - T3 = 1 against gold sigmoid(1) = 0.731058579.
            n, mse, bias = table['all saved']['lambda=1']
            self.assertEqual(n, 2)
            self.assertAlmostEqual(bias, ((0.0 - 0.5) + (1.0 - 0.731058579)) / 2, places=9)
            # The blend at w = 0.5 on record 0: 0.5 * 0.5 + 0.5 * 0 = 0.25.
            self.assertAlmostEqual(table['kept']['blend w=0.5'][2], 0.25 - 0.5, places=12)
            self.assertIn('kept, end: mate score', table)


def slice_game(fen, uci, wdl_white):
    """A one-move game as tools/datagen/endgame_slice.py writes it: the move's
    score +-SLICE_SCORE or 0 from White's view, the result the table's WDL."""
    import endgame_slice  # noqa: E402 (python-chess and the slice's own encoder)
    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    assert move in board.legal_moves
    return endgame_slice.encode(board, move, wdl_white + 1, endgame_slice.SLICE_SCORE * wdl_white)


class OneMoveGameTests(unittest.TestCase):
    """Retrain 8b (owner, 2026-11-09): every arm reads the Syzygy endgame slice
    unchanged; a one-move game (the slice's, idea 52's sites) is never relabelled.
    Without the rule TD(0.8) would move a slice win's 2,000 to about 2,148
    (sigmoid(2000 / 92) mixed with z = 1), and a blend copy would rewrite it."""

    KRK = slice_game('4k3/8/8/8/8/8/8/R3K3 w - - 0 1', 'a1a7', 1)
    KPK_DRAW = slice_game('8/8/8/8/8/4k3/4P3/4K3 b - - 0 1', 'e3e4', 0)

    def test_labels_copy_one_move_games_unchanged(self):
        data = self.KRK + self.KPK_DRAW + encode_game(*FOOL)[0]
        out, counts = td.relabel_shard(data, 0.8, 92.0)
        self.assertEqual(out[:len(self.KRK) + len(self.KPK_DRAW)], self.KRK + self.KPK_DRAW)
        self.assertEqual(counts['one_move'], 2)
        self.assertEqual(counts['relabelled'], 2)  # Fool's mate's records 0 and 2 only

    def test_blend_copies_one_move_games_unchanged(self):
        data = self.KRK + self.KPK_DRAW
        out, counts = td.blend_shard(data, 0.5, 92.0)
        self.assertEqual(out, data)
        self.assertEqual(counts['one_move'], 2)
        self.assertEqual(counts['relabelled'], 0)

    def test_a_one_move_game_whose_score_is_not_its_result_is_relabelled(self):
        # A search score with a game result (idea 52's sites, a short self-play game) is not the slice's.
        board = chess.Board('4k3/8/8/8/8/8/8/R3K3 w - - 0 1')
        import endgame_slice  # noqa: E402
        game = endgame_slice.encode(board, chess.Move.from_uci('a1a7'), 2, 300)
        self.assertNotEqual(td.relabel_shard(game, 0.8, 92.0)[0], game)
        self.assertNotEqual(td.blend_shard(game, 0.5, 92.0)[0], game)
        out, _ = td.relabel_shard(game, 0.8, 92.0)
        self.assertEqual(td.check_copy(game, out, 'td', 0.8, 92.0, sample=1)['bad'], [])

    def test_the_slice_target_is_the_same_at_either_result_weight(self):
        # Why the slice needs no copy: sigmoid(+-2000 / 92) is the WDL to within 1e-9.
        for s, z in ((2000, 1.0), (-2000, 0.0), (0, 0.5)):
            p = sig(s / 92.0)
            self.assertLess(abs(p - (0.5 * p + 0.5 * z)), 1e-9)


class BlendTests(unittest.TestCase):
    """`blend`: a copy whose keepable scores carry the score/result blend, so
    --result-weight 0 on the copy trains the target --result-weight W gives the
    original. Fool's mate at S = 100, W = 0.5, z = 0: record 0, sigmoid(0) = 0.5,
    T = 0.25, score round(100 ln(0.25 / 0.75)) = round(-109.86) = -110; record 2,
    sigmoid(-1) = 0.268941421, T = 0.134470711, round(100 ln(0.134470711 /
    0.865529289)) = round(-186.19) = -186; the unsaved record and the mate score
    (|s| > 20,000) unchanged."""

    def test_hand_worked(self):
        data, _ = encode_game(*FOOL)
        out, counts = td.blend_shard(data, 0.5, 100.0)
        self.assertEqual([s for _, s in list(td.split_games(out))[0][2]], [-110, U, -186, -29990])
        self.assertEqual((counts['relabelled'], counts['unsaved'], counts['beyond_limit']), (2, 1, 1))

    def test_target_at_weight_zero_equals_the_original_at_w(self):
        data, _ = encode_game(chess.STARTING_FEN, ['e2e4', 'e7e5', 'g1f3', 'b8c6'], [35, -20, 900, -19999], 2)
        out, _ = td.blend_shard(data, 0.5, 92.0)
        for (_, s0), (_, s1) in zip(list(td.split_games(data))[0][2], list(td.split_games(out))[0][2]):
            want = 0.5 * sig(s0 / 92.0) + 0.5 * 1.0
            # The integer rounding moves the target by at most 0.5 / S / 4.
            self.assertLessEqual(abs(sig(s1 / 92.0) - want), 0.5 / 92.0 / 4 + 1e-12)

    def test_weight_zero_copies_byte_for_byte(self):
        data, _ = encode_game(chess.STARTING_FEN, ['e2e4', 'e7e5', 'g1f3'], [5000, -20000, 19999], 2)
        self.assertEqual(td.blend_shard(data, 0.0, 92.0)[0], data)


class CopyCheckTests(unittest.TestCase):
    """`check`: a copy against its original, its labels recomputed on a sample
    of games by the forward view (an independent formula)."""

    def data(self):
        return (encode_game(*FOOL)[0] + self_play_like() + OneMoveGameTests.KRK
                + encode_game(chess.STARTING_FEN, ['e2e4', 'f7f6', 'd1h5', 'g7g6'], [10, -20, 300, -400], 1)[0])

    def test_good_copies_pass(self):
        data = self.data()
        for lam in (0.0, 0.8, 0.9, 1.0):
            out, _ = td.relabel_shard(data, lam, 92.0)
            report = td.check_copy(data, out, 'td', lam, 92.0, sample=1)
            self.assertEqual(report['bad'], [], lam)
            self.assertEqual(report['games_recomputed'], 3)  # the one-move game is compared whole instead
        out, _ = td.blend_shard(data, 0.5, 92.0)
        self.assertEqual(td.check_copy(data, out, 'blend', 0.5, 92.0, sample=1)['bad'], [])

    def test_a_wrong_lambda_fails(self):
        data = self.data()
        out, _ = td.relabel_shard(data, 0.8, 92.0)
        self.assertNotEqual(td.check_copy(data, out, 'td', 0.9, 92.0, sample=1)['bad'], [])

    def test_a_changed_move_or_unsaved_score_fails(self):
        data = self.data()
        out = bytearray(td.relabel_shard(data, 0.8, 92.0)[0])
        moved = bytearray(out)
        moved[32] ^= 1  # the first move code
        self.assertNotEqual(td.check_copy(data, bytes(moved), 'td', 0.8, 92.0, sample=1)['bad'], [])
        unsaved = bytearray(out)
        unsaved[32 + 4 + 2:32 + 4 + 4] = struct.pack('<h', 5)  # Fool's mate's unsaved record 1
        self.assertNotEqual(td.check_copy(data, bytes(unsaved), 'td', 0.8, 92.0, sample=1)['bad'], [])

    def test_a_relabelled_one_move_game_fails(self):
        data = OneMoveGameTests.KRK
        bad = bytearray(data)
        bad[34:36] = struct.pack('<h', 2148)
        self.assertNotEqual(td.check_copy(data, bytes(bad), 'td', 0.8, 92.0, sample=1)['bad'], [])


def self_play_like():
    """A longer game with an unsaved ply, a score past the trainer's limit
    and a quiet ending, for the copy checks."""
    moves = 'e2e4 e7e5 g1f3 b8c6 f1c4 g8f6 d2d3 f8c5 c2c3 d7d6'.split()
    scores = [30, -25, U, -40, 45, 21000, 50, U, 38, -36]
    return encode_game(chess.STARTING_FEN, moves, scores, 1)[0]


class UnsavedLabelTests(unittest.TestCase):
    """Idea 80, variant A (--label-unsaved; retrain 8c's i80 arm). Worked by
    hand at S = 100, lambda = 0.5, z = 1/2 (a draw), scores [10, U, 300, U]
    on 1. e4 e5 2. Nf3 Nc6 (no position in check, python-chess confirms):
      U4 = z = 0.5
      U3 (unsaved; the next chain value is z) = 0.5 * 0.5 + 0.5 * 0.5 = 0.5
      U2 = 0.5 sigmoid(3) + 0.5 U3 = 0.5 * 0.952574127 + 0.25 = 0.726287063
      U1 (unsaved; the next chain value is sigmoid(3)) = 0.5 * 0.952574127 + 0.5 * 0.726287063 = 0.839430595
      U0 = 0.5 sigmoid(0.1) + 0.5 U1 = 0.5 * 0.524979187 + 0.5 * 0.839430595 = 0.682204891
    Without the option records 1 and 3 have no label; the saved records'
    labels are the same either way."""

    MOVES = ['e2e4', 'e7e5', 'g1f3', 'b8c6']
    SCORES = [10, U, 300, U]

    def test_hand_worked(self):
        base = td.td_targets(self.SCORES, 1, 0.5, 100.0)
        got = [None if q is None else q[0] for q in td.td_pairs(self.SCORES, 1, 0.5, 100.0, label_unsaved=True)]
        self.assertIsNone(base[1])
        self.assertIsNone(base[3])
        for g, want in zip(got, (0.682204891, 0.839430595, 0.726287063, 0.5)):
            self.assertAlmostEqual(g, want, places=8)
        self.assertEqual((got[0], got[2]), (base[0], base[2]))

    def test_the_limits(self):
        # lambda = 0: an unsaved record takes the next chain value; lambda = 1: the result.
        zero = td.td_pairs(self.SCORES, 1, 0.0, 100.0, label_unsaved=True)
        self.assertAlmostEqual(zero[1][0], sig(3.0), places=12)
        self.assertAlmostEqual(zero[3][0], 0.5, places=12)
        one = td.td_pairs([35, U, -20, U], 2, 1.0, 100.0, label_unsaved=True)
        self.assertTrue(all(abs(q[0] - 1.0) < 1e-12 for q in one))

    def test_shard_copy_and_its_check(self):
        data = encode_game(chess.STARTING_FEN, self.MOVES, self.SCORES, 1)[0] + self_play_like()
        out, counts = td.relabel_shard(data, 0.5, 100.0, label_unsaved=True)
        self.assertEqual((counts['unsaved_labelled'], counts['unsaved']), (4, 0))
        recs = list(td.split_games(out))[0][2]
        # round(100 ln(0.839430595 / 0.160569405)) = round(165.40) = 165; record 3: 0.
        self.assertEqual([sc for _, sc in recs][1::2], [165, 0])
        self.assertEqual(td.check_copy(data, out, 'td', 0.5, 100.0, sample=1, label_unsaved=True)['bad'], [])
        # The checker can fail: the same copy read without the option, a plain copy read with it, a wrong label.
        self.assertNotEqual(td.check_copy(data, out, 'td', 0.5, 100.0, sample=1)['bad'], [])
        plain, _ = td.relabel_shard(data, 0.5, 100.0)
        self.assertNotEqual(td.check_copy(data, plain, 'td', 0.5, 100.0, sample=1, label_unsaved=True)['bad'], [])
        wrong = bytearray(out)
        wrong[32 + 4 + 2:32 + 4 + 4] = struct.pack('<h', 170)
        self.assertNotEqual(td.check_copy(data, bytes(wrong), 'td', 0.5, 100.0, sample=1,
                                          label_unsaved=True)['bad'], [])

    def test_an_unsaved_position_in_check_stays_unsaved(self):
        # 1. e4 f6 2. Qh5+ g6: record 3 (Black to move, in check) unsaved; record 1 unsaved, quiet.
        data = encode_game(chess.STARTING_FEN, ['e2e4', 'f7f6', 'd1h5', 'g7g6'], [10, U, 300, U], 1)[0]
        out, counts = td.relabel_shard(data, 0.5, 100.0, label_unsaved=True)
        recs = list(td.split_games(out))[0][2]
        self.assertEqual(recs[3][1], U)
        self.assertNotEqual(recs[1][1], U)
        self.assertEqual((counts['unsaved_labelled'], counts['unsaved']), (1, 1))
        self.assertEqual(td.check_copy(data, out, 'td', 0.5, 100.0, sample=1, label_unsaved=True)['bad'], [])
        bad = bytearray(out)
        bad[32 + 3 * 4 + 2:32 + 3 * 4 + 4] = struct.pack('<h', 7)
        self.assertNotEqual(td.check_copy(data, bytes(bad), 'td', 0.5, 100.0, sample=1,
                                          label_unsaved=True)['bad'], [])

    def test_a_label_saturated_by_a_mate_score_stays_unsaved(self):
        # Fool's mate with record 2 (1. f3 e5 2. ?, White to move, not in check) unsaved before Black's mate score:
        # its label is (0.1 sigmoid(-29990 / 92) + 0.9 * 0), about e^-326, which reaches -20,000: the trainer drops
        # the saved mate score after it, so the record stays unsaved; record 1's label is not saturated.
        data = encode_game(chess.STARTING_FEN, ['f2f3', 'e7e5', 'g2g4', 'd8h4'], [0, -100, U, -29990], 0)[0]
        out, counts = td.relabel_shard(data, 0.9, 92.0, label_unsaved=True)
        recs = list(td.split_games(out))[0][2]
        self.assertEqual(recs[2][1], U)
        self.assertEqual((counts['unsaved_decided'], counts['unsaved_labelled'], counts['clamped']), (1, 0, 0))
        self.assertLess(abs(recs[0][1]), td.KEEP_LIMIT)
        self.assertEqual(td.check_copy(data, out, 'td', 0.9, 92.0, sample=1, label_unsaved=True)['bad'], [])
        clamped = bytearray(out)
        clamped[32 + 2 * 4 + 2:32 + 2 * 4 + 4] = struct.pack('<h', -20000)
        self.assertNotEqual(td.check_copy(data, bytes(clamped), 'td', 0.9, 92.0, sample=1,
                                          label_unsaved=True)['bad'], [])

    def test_one_move_games_and_refusals(self):
        out, counts = td.relabel_shard(OneMoveGameTests.KRK, 0.9, 92.0, label_unsaved=True)
        self.assertEqual(out, OneMoveGameTests.KRK)
        with self.assertRaises(ValueError):
            td.td_pairs(self.SCORES, 1, 0.5, 100.0, unsaved='drop', label_unsaved=True)
        with self.assertRaises(ValueError):
            td.relabel_shard(OneMoveGameTests.KRK, 0.9, 92.0, check_scores='keep', label_unsaved=True)


class SplitTests(unittest.TestCase):
    """`split` (retrain 8c's rft-ep): above 7 pieces a keepable score becomes the
    result's code (+-2,000 / 0, White's view), at or below it is kept."""

    def test_piece_counts_against_python_chess(self):
        # Castling both ways, en passant, captures and promotions with capture.
        games = [
            ('r3k2r/1P6/8/3pP3/8/8/8/R3K2R w KQkq d6 0 1', ['e5d6', 'e8g8', 'b7a8q', 'g8g7', 'e1c1']),
            ('r3k2r/1P6/8/3pP3/8/8/8/R3K2R w KQkq d6 0 1', ['b7a8n', 'e8g8', 'e1c1']),
            (chess.STARTING_FEN, 'e2e4 d7d5 e4d5 d8d5 b1c3 d5a5 d2d4 c7c6 g1f3 c8g4 f1e2 e7e6 e1g1'.split()),
        ]
        for fen, moves in games:
            data, _ = encode_game(fen, moves, [0] * len(moves), 1)
            _, head, recs, _ = list(td.split_games(data))[0]
            board = chess.Board(fen)
            want = []
            for m in moves:
                want.append(len(board.piece_map()))
                board.push_uci(m)
            self.assertEqual(td.piece_counts(head, recs), want, fen)

    def test_hand_worked(self):
        # 8 pieces, then a capture to 7: record 0 (8 pieces, saved) to the result's code, record 1 (unsaved)
        # unchanged, record 2 (7 pieces) kept, record 3 beyond the limit kept.
        fen = '4k3/8/3p4/4P3/8/8/8/R2QK1NR w - - 0 1'
        data, _ = encode_game(fen, ['e5d6', 'e8f8', 'a1a2', 'f8g8'], [40, U, 55, 25000], 0)
        _, head, recs, _ = list(td.split_games(data))[0]
        self.assertEqual(td.piece_counts(head, recs), [8, 7, 7, 7])
        out, counts = td.split_shard(data)
        self.assertEqual([sc for _, sc in list(td.split_games(out))[0][2]], [-2000, U, 55, 25000])
        self.assertEqual((counts['to_result'], counts['kept_target'], counts['unsaved'], counts['beyond_limit']),
                         (1, 1, 1, 1))
        self.assertEqual(td.check_split(data, out, sample=1)['bad'], [])

    def test_slice_games_unchanged_and_the_check_can_fail(self):
        data = OneMoveGameTests.KRK + OneMoveGameTests.KPK_DRAW + self_play_like()
        out, counts = td.split_shard(data)
        self.assertEqual(out[:len(OneMoveGameTests.KRK) + len(OneMoveGameTests.KPK_DRAW)],
                         OneMoveGameTests.KRK + OneMoveGameTests.KPK_DRAW)
        self.assertEqual(counts['one_move'], 2)
        recs = list(td.split_games(out))[2][2]
        self.assertEqual([sc for _, sc in recs], [0, 0, U, 0, 0, 21000, 0, U, 0, 0])  # a draw, 32 pieces
        self.assertEqual(td.check_split(data, out, sample=1)['bad'], [])
        self.assertNotEqual(td.check_split(data, data, sample=1)['bad'], [])     # nothing split
        self.assertNotEqual(td.check_split(data, out, max_pieces=32, sample=1)['bad'], [])  # another rule


class ClassLambdaTests(unittest.TestCase):
    """Idea 85 (retrain 8c's lam arm): lambda by the record's material class."""
    GAMES = [
        # Castling both ways, en passant, a promotion to a queen with capture, a rook promotion, piece captures.
        ('r3k2r/1P6/8/3pP3/8/8/8/R3K2R w KQkq d6 0 1', ['e5d6', 'e8g8', 'b7a8q', 'g8g7', 'e1c1']),
        ('r3k2r/1P6/8/3pP3/8/8/8/R3K2R w KQkq d6 0 1', ['b7a8n', 'e8g8', 'e1c1']),
        ('8/1P5k/8/8/8/8/8/4K3 w - - 0 1', ['b7b8r', 'h7g6', 'b8b6']),
        (chess.STARTING_FEN, 'e2e4 d7d5 e4d5 d8d5 b1c3 d5a5 d2d4 c7c6 g1f3 c8g4 f1e2 e7e6 e1g1 a5h5'.split()),
        # A queen trade into an ending: Q-MG, then noQ-MG, then EG.
        ('3qk3/8/8/8/8/8/8/R2QK2R w - - 0 1', ['d1d8', 'e8d8', 'a1a8', 'd8e7', 'a8a7']),
    ]

    def test_classes_against_python_chess(self):
        # Fails on any replay slip (a capture, castling or promotion mis-tracked): the classes come from boards.
        for fen, moves in self.GAMES:
            data, _ = encode_game(fen, moves, [0] * len(moves), 1)
            _, head, recs, _ = list(td.split_games(data))[0]
            board = chess.Board(fen)
            want = []
            for m in moves:
                want.append(td.board_class(board))
                board.push_uci(m)
            self.assertEqual(td.material_classes(head, recs), want, fen)

    def test_the_class_rule(self):
        self.assertEqual(td.board_class(chess.Board()), 'Q-MG')                               # phase 24
        self.assertEqual(td.board_class(chess.Board('4k3/8/8/8/8/8/3Q4/R3K3 w - - 0 1')), 'Q-EG')   # 6
        self.assertEqual(td.board_class(chess.Board('r3k2r/8/8/8/8/8/8/RN2K1NR w - - 0 1')), 'noQ-MG')  # 10
        self.assertEqual(td.board_class(chess.Board('r3k2r/8/8/8/8/8/8/R3K1NR w - - 0 1')), 'EG')  # 9
        self.assertEqual(td.board_class(chess.Board('rn2k1nr/8/8/8/8/8/8/RB1QK3 w - - 0 1')), 'Q-MG')  # 13
        self.assertEqual(td.board_class(chess.Board('rn2k1nr/8/8/8/8/8/8/R2QK3 w - - 0 1')), 'Q-EG')  # 12

    def test_per_record_lambda_recursion_equals_the_forward_view(self):
        scores = [35, U, -20, U, 80, 300, U, -50]
        lams = [0.35, 0.9, 0.65, 0.35, 0.9, 0.65, 0.9, 0.35]
        chain = [s != U for s in scores]
        for result in (0, 1, 2):
            got = td.td_pairs(scores, result, lams, 92.0, label_unsaved=True)
            for t in range(len(scores)):
                want = td.forward_td_pair(scores, chain, result, lams, 92.0, t)
                self.assertAlmostEqual(got[t][0], want[0], places=12)
        # A constant list is the scalar.
        self.assertEqual(td.td_pairs(scores, 2, [0.9] * 8, 92.0), td.td_pairs(scores, 2, 0.9, 92.0))

    def test_copy_and_its_check(self):
        data = b''.join(encode_game(f, m, [(-1) ** i * 37 * i for i in range(len(m))], 2)[0] for f, m in self.GAMES)
        plain, _ = td.relabel_shard(data, 0.9, 92.0)
        same, _ = td.relabel_shard(data, 0.9, 92.0, lam_by_class={'Q-MG': 0.9, 'EG': 0.9})
        self.assertEqual(plain, same)                                    # a table of 0.9 is TD(0.9)
        lam, _ = td.relabel_shard(data, 0.9, 92.0, lam_by_class=td.LAM_BY_CLASS)
        self.assertNotEqual(lam, plain)
        self.assertEqual(td.check_copy(data, lam, 'td', 0.9, 92.0, sample=1, lam_by_class=td.LAM_BY_CLASS)['bad'], [])
        # The check fails on the wrong copy either way round.
        self.assertNotEqual(td.check_copy(data, plain, 'td', 0.9, 92.0, sample=1,
                                          lam_by_class=td.LAM_BY_CLASS)['bad'], [])
        self.assertNotEqual(td.check_copy(data, lam, 'td', 0.9, 92.0, sample=1)['bad'], [])


class InjectedFaultTests(unittest.TestCase):
    """The limit check must fail on a broken label function."""

    def test_off_by_one_is_caught(self):
        # The ideas.md form (the record's own score left out) is not the
        # default definition: at lambda = 0 it gives the next score.
        def shifted(scores, result, lam, scale, unsaved='next'):
            return td.td_targets(scores, result, lam, scale, from_next=True, unsaved=unsaved)
        with self.assertRaises(AssertionError):
            check_limits(shifted)

    def test_missing_terminal_value_is_caught(self):
        def no_result(scores, result, lam, scale, unsaved='next'):
            return td.td_targets(scores, 1, lam, scale, unsaved=unsaved)  # every game a draw
        with self.assertRaises(AssertionError):
            check_limits(no_result)


if __name__ == '__main__':
    unittest.main()
