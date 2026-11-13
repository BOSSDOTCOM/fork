# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of uho_diag.py (Fork's .venv, python-chess as the oracle): the queen-trade detector (capture with recapture,
offers, lines, a won queen is not a trade), the levelql filter (window, queens, material, checks and captures), and
the sign normalisation of the sets and of the measured values (from synthetic games written here; every position is
reached by legal moves from python-chess's own starting position, none is typed in)."""
import sys
import tempfile
import unittest
from pathlib import Path

import chess
import chess.pgn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uho_diag as u  # noqa: E402


def play(*sans):
    b = chess.Board()
    for s in sans:
        b.push_san(s)
    return b


def moves(board, *sans):
    b, out = board.copy(), []
    for s in sans:
        m = b.parse_san(s)
        out.append(m)
        b.push(m)
    return out


# 1.e4 d5 2.exd5 Qxd5: White to move, queens d1 and d5, the d-file blocked by d2.
CENTRE = ('e4', 'd5', 'exd5', 'Qxd5')


class TradeDetector(unittest.TestCase):
    def test_capture_with_recapture(self):
        b = play(*CENTRE, 'Qf3')  # Black's queen can take on f3, and g2 or the g1 knight recaptures
        self.assertEqual(u.trade_available(b), 'qxq')
        qxq = b.parse_san('Qxf3')
        self.assertTrue(u.queen_takes_queen(b, qxq))
        self.assertTrue(u.line_trades(b, moves(b, 'Qxf3', 'gxf3')))
        self.assertTrue(u.line_trades(b, moves(b, 'Qxf3', 'Nxf3', 'Nc6')))
        self.assertTrue(u.line_trades(b, [qxq]))  # a one-move PV: the recapture is legal

    def test_won_queen_is_not_a_trade(self):
        b = play(*CENTRE, 'Qf3')
        self.assertFalse(u.line_trades(b, moves(b, 'Qxf3', 'Nc3', 'Nc6')))
        self.assertFalse(u.line_trades(b, moves(b, 'Qxf3', 'Nc3')))

    def test_no_trade_line(self):
        b = play(*CENTRE, 'Qf3')
        self.assertFalse(u.line_trades(b, moves(b, 'Qd8', 'Qxb7', 'Bxb7')))  # only White's queen is lost
        self.assertFalse(u.line_trades(b, moves(b, 'Qe6')))
        self.assertFalse(u.line_trades(b, []))

    def test_offer(self):
        b = play(*CENTRE)
        self.assertFalse(any(u.queen_takes_queen(b, m) for m in b.legal_moves))
        self.assertEqual(u.trade_available(b), 'offer')
        self.assertTrue(u.queen_offer(b, b.parse_san('Qf3')))
        self.assertFalse(u.queen_offer(b, b.parse_san('Qe2')))
        # an offer that is accepted and recaptured is a trade within 3 plies
        self.assertTrue(u.line_trades(b, moves(b, 'Qf3', 'Qxf3', 'Nxf3')))
        self.assertFalse(u.line_trades(b, moves(b, 'Qf3', 'Nc6', 'Nc3')))

    def test_needs_one_queen_each(self):
        b = play(*CENTRE, 'Qf3', 'Qxf3', 'Nxf3')
        self.assertIsNone(u.trade_available(b))
        self.assertFalse(u.line_trades(b, moves(b, 'Nc6')))


# 1.e4 d5 2.exd5 Qxd5 3.Qf3 Qxf3 4.Nxf3: queenless, a pawn each gone, Black to move.
QUEENLESS = CENTRE + ('Qf3', 'Qxf3', 'Nxf3')


class LevelFilter(unittest.TestCase):
    def setUp(self):
        self.before = play(*QUEENLESS, 'Nc6')       # White to move
        self.board = play(*QUEENLESS, 'Nc6', 'Bc4')  # Black to move after a quiet move
        self.prev = (self.before, self.before.parse_san('Bc4'))
        self.quiet = self.board.parse_san('Nf6')

    def test_accepts_level_quiet(self):
        self.assertEqual(u.material(self.board, chess.WHITE), u.material(self.board, chess.BLACK))
        for cp in (0, 10, -10):
            self.assertTrue(u.level_queenless(self.board, self.prev, self.quiet, cp))

    def test_window(self):
        self.assertFalse(u.level_queenless(self.board, self.prev, self.quiet, 11))
        self.assertFalse(u.level_queenless(self.board, self.prev, self.quiet, -11))
        self.assertFalse(u.level_queenless(self.board, self.prev, self.quiet, None))

    def test_captures_and_queens(self):
        after_capture = play(*QUEENLESS)
        prev = (play(*QUEENLESS[:-1]), play(*QUEENLESS[:-1]).parse_san('Nxf3'))
        self.assertFalse(u.level_queenless(after_capture, prev, after_capture.parse_san('Nc6'), 0))
        queens_on = play(*CENTRE, 'Nc3')
        self.assertFalse(u.level_queenless(queens_on, None, queens_on.parse_san('Qa5'), 0))

    def test_material(self):
        # 4...Nc6 5.Bc4 Nd4 6.Nxd4 e6 7.Nf3: Black a knight down, Black to move after a quiet move
        line = QUEENLESS + ('Nc6', 'Bc4', 'Nd4', 'Nxd4', 'e6', 'Nf3')
        b = play(*line)
        before = play(*line[:-1])
        self.assertNotEqual(u.material(b, chess.WHITE), u.material(b, chess.BLACK))
        self.assertFalse(u.level_queenless(b, (before, before.parse_san('Nf3')), b.parse_san('Nf6'), 0))


def write_game(path, fork_white, sans_with_comments, rnd=1):
    g = chess.pgn.Game()
    g.headers['White'], g.headers['Black'] = ('Fork', 'Stockfish 19') if fork_white else ('Stockfish 19', 'Fork')
    g.headers['Round'] = str(rnd)
    g.setup(chess.Board())
    node = g
    for san, comment in sans_with_comments:
        node = node.add_variation(node.board().parse_san(san))
        node.comment = comment
    with open(path, 'a', encoding='utf-8') as f:
        print(g, file=f, end='\n\n')


class SignNormalisation(unittest.TestCase):
    """SF's comments are from the mover's view; the sets store values from the advantaged side (adv) or Fork's
    side (levelql), and the measured side-to-move values are turned the same way."""

    def test_adv_side_and_sign(self):
        with tempfile.TemporaryDirectory() as d:
            shard = Path(d) / 'shard-1'
            shard.mkdir()
            pgn = shard / 'games.pgn'
            # game 1: Fork White; SF (Black) says -0.80 = White +80. Game 2: SF White says +0.90.
            write_game(pgn, True, [('e4', '+0.30/10 0.1s'), ('e5', '-0.80/10 0.1s'), ('Nf3', '+0.31/10 0.1s')])
            write_game(pgn, False, [('e4', '+0.90/10 0.1s'), ('e5', '-0.40/10 0.1s')], 2)
            games = u.read_games(d, 'uho')
            rows, skipped = u.build_adv(games)
        self.assertEqual(skipped, [])
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r['side'], r['sf_cp'], r['sf_mean_cp'], r['game_cp']), ('w', 80, 85.0, 30))

    def test_adv_black_advantaged(self):
        with tempfile.TemporaryDirectory() as d:
            shard = Path(d) / 'shard-1'
            shard.mkdir()
            pgn = shard / 'games.pgn'
            write_game(pgn, True, [('e4', '+0.10/10 0.1s'), ('e5', '+0.70/10 0.1s')])   # SF Black: Black +70
            write_game(pgn, False, [('e4', '-0.60/10 0.1s'), ('e5', '+0.20/10 0.1s')], 2)  # SF White: Black +60
            rows, _ = u.build_adv(u.read_games(d, 'uho'))
        r = rows[0]
        # Fork had Black in game 2: SF (White) said -0.60 there, Black's +60; Fork's own first score +0.20 (Black's)
        self.assertEqual((r['side'], r['sf_cp'], r['sf_mean_cp'], r['game_cp']), ('b', 60, 65.0, 20))
        self.assertEqual(r['game'], 'uho/shard-1/2')

    def test_levelql_from_forks_side(self):
        line = list(QUEENLESS) + ['Nc6', 'Bc4', 'Nf6', 'Nc3']
        with tempfile.TemporaryDirectory() as d:
            shard = Path(d) / 'shard-1'
            shard.mkdir()
            # Fork White, so SF moves Black's plies (odd indices); its 0.05 at ...Nf6 is Black's +5 = Fork's -5
            comments = ['+0.20/10 0.1s'] * len(line)
            comments[9] = '+0.05/10 0.1s'   # Black's 5...Nf6, SF to move
            comments[10] = '+0.25/10 0.1s'  # Fork's next score, 6.Nc3
            write_game(shard / 'games.pgn', True, list(zip(line, comments)))
            rows = u.build_levelql(u.read_games(d, 'bal'), u.SEED)
        self.assertEqual([(r['ply'], r['sf_cp'], r['game_cp']) for r in rows], [(9, -5, 25)])

    def test_oriented_values(self):
        black_to_move = play('e4').fen()
        rows = [{'fen': black_to_move, 'side': 'w'}, {'fen': black_to_move, 'side': 'b'},
                {'fen': chess.Board().fen(), 'side': 'w'}]
        self.assertEqual(u.oriented(rows, [30, 30, 30]), [-30, 30, 30])

    def test_comment_scores(self):
        self.assertEqual(u.comment_cp('+0.38/14 0.231s'), 38)
        self.assertEqual(u.comment_cp('-1.20/19 0.717s'), -120)
        self.assertEqual(u.comment_cp('0.00/26 0.115s, Draw by 3-fold repetition'), 0)
        self.assertIsNone(u.comment_cp('+M5/30 0.1s'))
        self.assertIsNone(u.comment_cp(''))


# Lines for the piece-trade detector, each reached by legal moves (the knight and bishop ones were found by a random
# search over legal lines with python-chess, 2026-11-13).
ROOKS = ('a4', 'a5', 'Ra3', 'Ra6', 'Rb3', 'Rb6')           # White to move: Rxb6, recaptured by c7xb6
SPANISH = ('e4', 'e5', 'Nf3', 'Nc6', 'Bb5', 'a6')         # White to move: Bxc6, recaptured by a pawn
KNIGHTS = ('g3', 'Nf6', 'e4', 'Nxe4', 'Bh3', 'd6', 'Nc3')  # Black to move: Nxc3, recaptured by a pawn
BISHOPS = ('d4', 'h6', 'b3', 'a5', 'Ba3', 'e5')           # White to move: Bxf8, recaptured by the king
KNIGHT_OFFER = ('b4', 'Nc6', 'g3', 'Ne5')                  # White to move: Nf3 offers the knights
LOOSE_BISHOP = ('g3', 'b6', 'Bg2', 'Bb7')                  # White to move: Bxb7 cannot be recaptured


class PieceTrades(unittest.TestCase):
    def test_pair_classes(self):
        self.assertEqual(u.pair_class(chess.ROOK, chess.ROOK), 'R')
        self.assertEqual(u.pair_class(chess.KNIGHT, chess.BISHOP), 'BN')
        self.assertEqual(u.pair_class(chess.BISHOP, chess.KNIGHT), 'BN')
        self.assertIsNone(u.pair_class(chess.ROOK, chess.KNIGHT))
        self.assertIsNone(u.pair_class(chess.QUEEN, chess.QUEEN))

    def test_captures_with_recapture(self):
        for line, san, cls in ((ROOKS, 'Rxb6', 'R'), (SPANISH, 'Bxc6', 'BN'), (KNIGHTS, 'Nxc3', 'N'),
                               (BISHOPS, 'Bxf8', 'B')):
            b = play(*line)
            self.assertEqual(u.capture_class(b, b.parse_san(san)), cls, san)
            self.assertEqual(u.piece_trades_available(b).get(cls), 'cap', san)
            self.assertEqual(u.line_piece_trade(b, [b.parse_san(san)]), cls, san)  # one-move line

    def test_capture_without_recapture(self):
        b = play(*LOOSE_BISHOP)
        m = b.parse_san('Bxb7')
        self.assertIsNone(u.capture_class(b, m))
        self.assertNotEqual(u.piece_trades_available(b).get('B'), 'cap')
        self.assertIsNone(u.line_piece_trade(b, [m]))

    def test_lines(self):
        b = play(*ROOKS)
        self.assertEqual(u.line_piece_trade(b, moves(b, 'Rxb6', 'cxb6')), 'R')
        self.assertEqual(u.line_piece_trade(b, moves(b, 'Rxb6', 'cxb6', 'Nc3')), 'R')
        self.assertIsNone(u.line_piece_trade(b, moves(b, 'Rxb6', 'Nc6', 'Nc3')))  # a rook won, not traded
        self.assertIsNone(u.line_piece_trade(b, moves(b, 'Nc3', 'Nc6', 'e3')))
        b = play(*SPANISH)
        self.assertEqual(u.line_piece_trade(b, moves(b, 'Bxc6', 'dxc6')), 'BN')
        b = play(*BISHOPS)
        self.assertEqual(u.line_piece_trade(b, moves(b, 'Bxf8', 'Kxf8')), 'B')
        b = play(*CENTRE, 'Qf3')  # a queen trade is not a piece-class trade
        self.assertIsNone(u.line_piece_trade(b, moves(b, 'Qxf3', 'Nxf3')))

    def test_offer(self):
        b = play(*KNIGHT_OFFER)
        m = b.parse_san('Nf3')
        self.assertIsNone(u.capture_class(b, m))
        self.assertEqual(u.offer_classes(b, m), {'N'})
        self.assertEqual(u.piece_trades_available(b).get('N'), 'offer')
        self.assertEqual(u.line_piece_trade(b, moves(b, 'Nf3', 'Nxf3+', 'exf3')), 'N')

    def test_queen_state(self):
        self.assertEqual(u.queen_state(chess.Board()), 'qon')
        self.assertEqual(u.queen_state(play(*QUEENLESS)), 'ql')
        self.assertIsNone(u.queen_state(play(*CENTRE, 'Qf3', 'Qxf3')))

    def test_set_row_and_sign(self):
        # Fork White; SF's -0.50 at ...Rb6 (Black's view) is White's +50 when Fork is to play Rxb6 (subset F)
        line = list(ROOKS) + ['Rxb6', 'cxb6', 'Nc3']
        comments = ['0.00/10 0.1s'] * len(line)
        comments[5] = '-0.50/10 0.1s'
        with tempfile.TemporaryDirectory() as d:
            shard = Path(d) / 'shard-1'
            shard.mkdir()
            write_game(shard / 'games.pgn', True, list(zip(line, comments)))
            rows = u.build_ptrade(u.read_games(d, 'uho'), u.SEED)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r['subset'], r['qstate'], r['sf_cp'], r['game_trade'], r['ply']), ('F', 'qon', 50, 'R', 6))
        self.assertEqual(u.parse_avail(r['avail'])['R'], 'cap')

    def test_rates(self):
        rows = [{'subset': 'S', 'qstate': 'ql', 'avail': 'R:cap,BN:offer', 'game_trade': 'R'},
                {'subset': 'S', 'qstate': 'ql', 'avail': 'R:offer', 'game_trade': '-'},
                {'subset': 'S', 'qstate': 'qon', 'avail': 'BN:cap', 'game_trade': '-'},
                {'subset': 'F', 'qstate': 'ql', 'avail': 'N:line', 'game_trade': 'N'}]
        out = u.ptrade_rates(list(zip(rows, ['R', 'R', 'BN', None])))
        sq = out['S_ql']
        self.assertEqual(sq['any'], {'n': 2, 'net': 1.0, 'ref': 0.5})
        self.assertEqual(sq['R'], {'n': 2, 'n_cap': 1, 'net': 1.0, 'ref': 0.5, 'net_cap': 1.0, 'ref_cap': 1.0})
        self.assertEqual(sq['BN'], {'n': 1, 'n_cap': 0, 'net': 0.0, 'ref': 0.0})
        self.assertEqual(out['S_all']['BN']['n'], 2)
        self.assertEqual(out['S_qon']['BN'], {'n': 1, 'n_cap': 1, 'net': 1.0, 'ref': 0.0, 'net_cap': 1.0,
                                             'ref_cap': 0.0})
        self.assertEqual(out['F_ql']['N'], {'n': 1, 'n_cap': 0, 'net': 0.0, 'ref': 1.0})


if __name__ == '__main__':
    unittest.main()
