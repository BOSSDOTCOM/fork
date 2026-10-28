"""Checks the facts that the tests' constructed positions rely on
(tests/test_search.cpp, test_eval.cpp, test_see.cpp, test_ordering.cpp,
test_pruning.cpp, test_draws.cpp, test_uci.cpp, test_endgame_tables.cpp),
with python-chess as the independent oracle: legal FENs, forced mates in N
(and none sooner), checkmate and stalemate, repetitions, halfmove clocks and
the LMR move facts; and restates the danger-zone time budgets. Exits non-zero
if any fact is wrong.

    .venv/Scripts/python.exe -I tools/check_search_positions.py
"""
import sys

import chess


def forced_mate_within(board, n):
    """True if the side to move can force mate within n moves."""
    for move in board.legal_moves:
        board.push(move)
        if board.is_checkmate():
            board.pop()
            return True
        if n > 1 and not board.is_game_over() and all_replies_lose(board, n - 1):
            board.pop()
            return True
        board.pop()
    return False


def all_replies_lose(board, n):
    for reply in board.legal_moves:
        board.push(reply)
        ok = forced_mate_within(board, n)
        board.pop()
        if not ok:
            return False
    return True


def mating_moves(board):
    out = []
    for move in board.legal_moves:
        board.push(move)
        if board.is_checkmate():
            out.append(move.uci())
        board.pop()
    return out


failures = 0


def check(cond, what):
    global failures
    print(('ok   ' if cond else 'FAIL ') + what)
    failures += not cond


def board_of(fen):
    b = chess.Board(fen)
    check(b.is_valid(), f'valid: {fen}')
    return b


b = board_of('6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1')
check(mating_moves(b) == ['a1a8'], 'back rank: a1a8 is the only mate in 1')
b = board_of('6k1/5ppp/8/8/8/8/8/R5K1 w - - 99 80')
check(mating_moves(b) == ['a1a8'], 'back rank, halfmove 99: a1a8 mates')
b = board_of('k7/8/2K5/8/8/8/8/7R w - - 0 1')
check(not forced_mate_within(b, 1) and forced_mate_within(b, 2), 'K+R v K: mate in 2, not in 1')
b = board_of('7k/8/8/8/8/8/8/R5K1 w - - 99 80')
check(not forced_mate_within(b, 1), 'K+R v K, halfmove 99: no mate in 1')
b = board_of('rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3')
check(b.is_checkmate(), "fool's mate: White is checkmated")
b = board_of('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1')
check(b.is_stalemate(), 'Black is stalemated')
b = chess.Board()
for uci in ['e2e4', 'g8f6', 'g1f3', 'f6g8', 'f3g1', 'g8f6']:
    b.push_uci(uci)
check(b.is_repetition(2), 'e4 Nf6 Nf3 Ng8 Ng1 Nf6 repeats the position after 1...Nf6')

for fen in ['8/8/8/4k3/8/8/8/4K3 w - - 0 1', '8/8/8/4k3/8/8/8/2B1K3 b - - 0 1', '8/8/8/4k3/8/8/8/2N1K3 w - - 0 1']:
    check(board_of(fen).is_insufficient_material(), f'insufficient material: {fen}')
for fen in ['4k3/pppppppp/8/8/8/8/PPPPPPPP/R3K3 w - - 0 1', '4k3/pppppppp/8/8/8/8/PPPPPPPP/R3K3 b - - 0 1',
            'k7/8/8/8/8/8/8/1R2K3 w - - 0 1', '8/8/8/3k4/8/8/8/1R2K3 w - - 0 1',
            'k7/8/1K6/8/8/8/8/7R w - - 0 1', 'k7/8/8/8/8/8/8/6KR w - - 0 1']:
    board_of(fen)

# tests/test_see.cpp: legal positions, and the move each one judges is legal.
for fen, uci in [('4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1', 'e4d5'), ('4k3/8/2p5/3p4/4P3/8/8/4K3 w - - 0 1', 'e4d5'),
                 ('4k3/8/2p5/3p4/8/4N3/8/4K3 w - - 0 1', 'e3d5'), ('3rk3/8/8/3p4/8/8/3R4/3RK3 w - - 0 1', 'd2d5'),
                 ('8/8/8/3k4/3p4/8/8/3QK3 w - - 0 1', 'd1d4'), ('8/8/8/3k4/3p4/8/3R4/3QK3 w - - 0 1', 'd2d4'),
                 ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1', 'e5d6'), ('4k3/1P6/8/8/8/8/8/4K3 w - - 0 1', 'b7b8q'),
                 ('r3k3/1P6/8/8/8/8/8/4K3 w - - 0 1', 'b7b8q'), ('4k3/8/2p5/8/8/4N3/8/4K3 w - - 0 1', 'e3d5'),
                 ('4k3/8/8/8/8/8/8/4K2R w K - 0 1', 'e1g1')]:
    b = board_of(fen)
    check(chess.Move.from_uci(uci) in b.legal_moves, f'legal: {uci} in {fen}')
# tests/test_ordering.cpp: the ordering position and its two moves.
b = board_of('4k3/8/2p5/3p3p/8/4N1Q1/8/4K3 w - - 0 1')
check(chess.Move.from_uci('e3d5') in b.legal_moves and chess.Move.from_uci('e1f1') in b.legal_moves
      and [m.uci() for m in b.legal_moves if b.is_capture(m)] == ['e3d5'], 'ordering position: Nxd5 the only capture, Kf1 legal')
# tests/test_pruning.cpp, the max-ply stress test: a locked pawn ending.
b = board_of('4k3/8/8/1p1p1p2/1P1P1P2/8/8/4K3 w - - 0 1')
check(all(b.piece_type_at(m.from_square) == chess.KING for m in b.legal_moves), 'locked pawn ending: only king moves')
# tests/test_pruning.cpp: Black has only king moves, is far behind, and is
# neither mated nor stalemated; White to move is legal too.
b = board_of('7k/8/8/8/8/1Q6/8/1R4K1 b - - 0 1')
check(all(b.piece_type_at(m.from_square) == chess.KING for m in b.legal_moves) and b.legal_moves.count() > 0
      and not b.is_check(), 'pruning position: Black has only (quiet) king moves')
board_of('7k/8/8/8/8/1Q6/8/1R4K1 w - - 0 1')
# tests/test_search.cpp, the TT endgames.
for fen in ['8/2k5/8/1p6/1P6/8/5K2/8 w - - 0 1', '4k3/8/8/8/8/8/4P3/4K3 w - - 0 1',
            '8/8/3k4/8/8/3K4/8/R7 w - - 0 1', '8/5pk1/8/8/8/8/5PK1/8 b - - 0 1']:
    board_of(fen)

# tests/test_search.cpp, "quiescence values on constructed exchanges": the
# material-only value (pawn 100, knight and bishop 300, rook 500, queen 900)
# of a depth-1 search ending in a capture search (captures and queen
# promotions, stand pat; every evasion in check), and the moves reaching it.
# python-chess generates the moves; nothing here uses Fork's SEE or search.
VALUE = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300, chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}


def material(b):
    s = sum(VALUE[p.piece_type] * (1 if p.color == b.turn else -1) for p in b.piece_map().values())
    return s


def capture_search(b, alpha, beta):
    if b.is_checkmate():
        return -100000
    in_check = b.is_check()
    if not in_check:
        stand = material(b)
        if stand >= beta:
            return beta
        alpha = max(alpha, stand)
    for m in b.legal_moves:
        if not in_check and not (b.is_capture(m) or m.promotion == chess.QUEEN):
            continue
        if m.promotion and m.promotion != chess.QUEEN:
            continue
        b.push(m)
        score = -capture_search(b, -beta, -alpha)
        b.pop()
        if score >= beta:
            return beta
        alpha = max(alpha, score)
    return alpha


def depth_one(fen):
    b = chess.Board(fen)
    results = {}
    for m in b.legal_moves:
        b.push(m)
        results[m.uci()] = -capture_search(b, -10**6, 10**6)
        b.pop()
    best = max(results.values())
    return best, sorted(u for u, v in results.items() if v == best)


for fen, value, moves in [
    ('4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1', 100, ['e4d5']),
    ('4k3/8/3p4/4r3/8/5N2/8/4K3 w - - 0 1', -100, ['f3e5']),
    ('4k3/8/2p5/3p4/8/8/3Q4/4K3 w - - 0 1', 700, None),  # every quiet move; never d2d5
    ('4k3/1P6/8/8/8/8/8/4K3 w - - 0 1', 900, ['b7b8q']),
    ('3rk3/8/8/3p4/8/8/3R4/3RK3 w - - 0 1', 500, ['d2d5']),
]:
    board_of(fen)
    got_value, got_moves = depth_one(fen)
    ok = got_value == value and (moves is None or got_moves == moves) and (moves is not None or 'd2d5' not in got_moves)
    check(ok, f'capture search {fen}: value {got_value}, best {got_moves[:6]}')

# tests/test_endgame_tables.cpp (deliverable 7). The two KPPPPPvK positions
# and their results are from the KB (tools.md §6.9, Fathom and the lichess API
# agreeing); here only their legality and the claims the test relies on: no
# capture is possible (so no smaller table is needed), and Black has 3 legal
# moves. The other two are constructed: a running halfmove clock, and eight
# pieces (more than any table covers).
for fen in ('k7/8/8/8/8/8/PPPPP3/7K w - - 0 1', 'k7/8/8/8/8/8/PPPPP3/7K b - - 0 1'):
    b = board_of(fen)
    check(not any(b.is_capture(m) for m in b.legal_moves), f'tables: no capture in {fen}')
check(board_of('k7/8/8/8/8/8/PPPPP3/7K b - - 0 1').legal_moves.count() == 3, 'tables: Black has 3 legal moves')
board_of('k7/8/8/8/8/8/PPPPP3/7K w - - 3 1')
check(len(board_of('k7/p7/8/8/8/8/PPPPP3/7K w - - 0 1').piece_map()) == 8, 'tables: eight pieces')

# tests/test_uci.cpp, the search-line check (audit-1 Q-2): the castling
# position's two castling moves, Rxa8 legal there, Black's queenside castling
# legal after O-O; the K+R v K mate in 2 line c6b6 a8b8 h1h8 (and c6b6 a8b8
# h1h7 not mate).
b = board_of('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
check(sorted(m.uci() for m in b.legal_moves if b.is_castling(m)) == ['e1c1', 'e1g1'],
      'castling position: e1g1 and e1c1 are its castling moves')
check(chess.Move.from_uci('a1a8') in b.legal_moves, 'castling position: a1a8 is legal')
b.push_uci('e1g1')
check(b.is_castling(chess.Move.from_uci('e8c8')) and chess.Move.from_uci('e8c8') in b.legal_moves,
      'castling position: e8c8 castles after e1g1')
b = board_of('k7/8/2K5/8/8/8/8/7R w - - 0 1')
for uci in ['c6b6', 'a8b8']:
    b.push_uci(uci)
check(chess.Move.from_uci('h1h8') in b.legal_moves and chess.Move.from_uci('h1h7') in b.legal_moves,
      'K+R v K: h1h8 and h1h7 legal after c6b6 a8b8')
b.push_uci('h1h8')
check(b.is_checkmate(), 'K+R v K: c6b6 a8b8 h1h8 is mate')
b.pop()
b.push_uci('h1h7')
check(not b.is_checkmate(), 'K+R v K: c6b6 a8b8 h1h7 is not mate')

# tests/test_draws.cpp, the fifty-move clock (audit-1 Q-3): the halfmove
# clock after each move, and the rule reached at exactly 100 half-moves.
for fen, moves, clocks in [
    (chess.STARTING_FEN, ['g1f3', 'b8c6', 'f3e5', 'c6e5', 'g2g3', 'e5f3', 'e2f3'], [1, 2, 3, 0, 0, 1, 0]),
    ('4k3/8/8/8/8/8/8/R3K2R w K - 37 50', ['e1g1', 'e8d7', 'f1f7', 'd7e6'], [38, 39, 40, 41]),
    ('4k3/8/8/8/8/8/r7/R3K3 w - - 37 50', ['a1a2'], [0]),
    ('4k3/1p6/8/2P5/8/8/8/4K3 b - - 37 50', ['b7b5'], [0]),
    ('4k3/8/8/1pP5/8/8/8/4K3 w - b6 12 50', ['c5b6'], [0]),
    ('4k3/1P6/8/8/8/8/8/4K3 w - - 37 50', ['b7b8q'], [0]),
    ('4k3/8/8/8/8/8/8/R3K3 w - - 99 80', ['a1a2'], [100]),
]:
    b = board_of(fen)
    got = []
    for uci in moves:
        b.push_uci(uci)
        got.append(b.halfmove_clock)
    check(got == clocks, f'halfmove clocks from {fen}: {got}')
b = board_of('4k3/8/8/8/8/8/8/R3K3 w - - 99 80')
check(not b.is_fifty_moves(), 'fifty-move rule not reached at 99 half-moves')
b.push_uci('a1a2')
check(b.is_fifty_moves(), 'fifty-move rule reached at 100 half-moves')

# tests/test_pruning.cpp, the LMR context's history (audit-1 V-4): legal
# positions and moves.
for fen, uci in [('4k3/8/8/8/8/8/8/R3K3 w - - 0 1', 'a1a2'), ('r3k3/8/8/8/8/8/8/4K3 b - - 0 1', 'a8a7')]:
    b = board_of(fen)
    check(chess.Move.from_uci(uci) in b.legal_moves and not b.is_capture(chess.Move.from_uci(uci)),
          f'quiet and legal: {uci} in {fen}')

# tests/test_search.cpp, the zero-window and null-move cases (audit-1 Q-7):
# the back-rank position with Black to move is legal and not over; the two
# pawn endings (results from the lichess tablebase API, cited in the test)
# are legal and the moves named there legal.
b = board_of('6k1/5ppp/8/8/8/8/8/R5K1 b - - 0 1')
check(not b.is_game_over() and not b.is_check(), 'back rank, Black to move: not over, not in check')
for fen, moves in [('8/1p6/8/6k1/8/8/4P3/7K b - - 0 1', ['b7b5', 'b7b6']),
                   ('8/3p4/8/6P1/3k3p/5K2/8/8 b - - 0 1', ['d4d5', 'd4e5', 'd7d5'])]:
    b = board_of(fen)
    check(all(chess.Move.from_uci(u) in b.legal_moves for u in moves), f'legal in {fen}: {moves}')

# tests/test_endgame_tables.cpp, the 3-4-5 cases (audit-1 Q-6; the table
# results are the lichess API's, cited there): legal positions and moves;
# KQvKP: Black's only moves are c7c6 and c7c5, each answered by a mate in 1;
# the KQvK king shuffle is legal and repeats the position.
for fen, moves in [('8/8/8/pK6/5k1N/8/2N5/8 b - - 0 1', ['a5a4']),
                   ('8/8/8/1K6/p4k1N/8/2N5/8 w - - 0 1', ['c2a3']),
                   ('k7/8/8/8/2P5/8/8/6K1 w - - 0 1', ['c4c5', 'g1f1', 'g1f2', 'g1g2', 'g1h1', 'g1h2']),
                   ('8/1P6/8/2k2K2/8/8/8/8 w - - 0 1', ['b7b8q', 'b7b8r', 'b7b8b', 'b7b8n']),
                   ('8/8/8/5k2/8/7K/6P1/8 w - - 0 1', ['h3h4', 'g2g3', 'g2g4', 'h3h2', 'h3g3']),
                   ('8/8/8/8/6K1/3k4/8/6Q1 w - - 0 1', ['g1c5'])]:
    b = board_of(fen)
    check(all(chess.Move.from_uci(u) in b.legal_moves for u in moves), f'legal in {fen}: {moves}')
check(board_of('k7/8/8/8/2P5/8/8/6K1 w - - 0 1').legal_moves.count() == 6, 'KPvK draw: six legal moves')
b = board_of('8/2p5/8/8/2Q5/k7/2K5/8 b - - 0 1')
check(sorted(m.uci() for m in b.legal_moves) == ['c7c5', 'c7c6'], 'KQvKP: c7c6 and c7c5 are the only moves')
for uci in ['c7c6', 'c7c5']:
    b.push_uci(uci)
    check(forced_mate_within(b, 1), f'KQvKP: mate in 1 after {uci}')
    b.pop()
b = board_of('8/8/8/8/6K1/3k4/8/6Q1 w - - 0 1')
for uci in ['g4h5', 'd3e4', 'h5g4', 'e4d3']:
    b.push_uci(uci)
check(b.is_repetition(2) and b.halfmove_clock == 4, 'KQvK: the king shuffle repeats the position (clock 4)')

# tests/test_pruning.cpp, "LMR move facts" (audit-1 Q-11: the derivation was
# not committed): the moved piece's type (0 pawn ... 5 king), whether the
# opponent attacked its square before the move, and whether from its new
# square (a castling king's landing square) it attacks an enemy piece other
# than a pawn or the king.
PIECE_INDEX = {chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5}
for fen, uci, piece, threatened, attacks in [
    ('4k3/8/8/3p4/4N3/8/8/4K3 w - - 0 1', 'e4c3', 1, True, False),
    ('4k3/8/8/8/1r6/8/8/N3K3 w - - 0 1', 'a1c2', 1, False, True),
    ('r3k3/8/8/8/8/8/8/R3K3 w - - 0 1', 'a1a2', 3, True, True),
    ('4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'e1d1', 5, False, False),
    ('4k3/8/8/2n5/8/3P4/8/4K3 w - - 0 1', 'd3d4', 0, True, True),
    ('4k3/8/8/8/3n4/4P3/8/4K3 b - - 0 1', 'd4b5', 1, True, False),
    ('4k3/8/8/8/8/8/7r/4K2R w K - 0 1', 'e1g1', 5, False, True),
]:
    b = board_of(fen)
    m = chess.Move.from_uci(uci)
    mover, them = b.turn, not b.turn
    got_piece = PIECE_INDEX[b.piece_type_at(m.from_square)]
    got_threatened = b.is_attacked_by(them, m.from_square)
    landing = m.to_square
    b.push(m)
    targets = [s for s in b.attacks(landing)
               if b.color_at(s) == them and b.piece_type_at(s) not in (chess.PAWN, chess.KING)]
    got = (got_piece, got_threatened, bool(targets))
    check(got == (piece, threatened, attacks), f'LMR facts {fen} {uci}: {got}')

# tests/test_search.cpp, "an extra overhead of reserve only in the danger
# zone" (audit-1 Q-11): its literal budgets, restated here from the rule in
# src/search/time_budget.cpp's comments (Move Overhead 100, 30 moves left, a
# tenth of the clock in reserve, or max(a tenth, one overhead) when less
# than two overheads plus the increment are left; the soft limit one share,
# the hard limit four shares, capped at the clock less the reserve).
def budget(remaining, inc, overhead=100):
    available = max(1, remaining - overhead)
    zone = available < 2 * overhead + inc
    reserve = max(available // 10, overhead) if zone else available // 10
    cap = max(1, available - reserve)
    share = available // 30 + min(inc, cap) * 3 // 4
    hard = min(max(min(share, cap // 4) * 4, 1), cap)
    return min(max(share, 1), hard), hard


DANGER = {150: [(1, 1), (1, 1), (1, 1)], 250: [(5, 20), (20, 48), (42, 48)], 300: [(6, 24), (21, 84), (66, 100)],
          319: [(7, 28), (22, 88), (67, 116)], 320: [(7, 28), (22, 88), (67, 120)],
          379: [(9, 36), (24, 96), (69, 176)], 380: [(9, 36), (24, 96), (69, 252)],
          500: [(13, 52), (28, 112), (73, 292)], 1000: [(30, 120), (45, 180), (90, 360)],
          2000: [(63, 252), (78, 312), (123, 492)]}
for remaining, rows in DANGER.items():
    got = [budget(remaining, inc) for inc in (0, 20, 80)]
    check(got == rows, f'danger-zone budgets at {remaining} ms: {got}')

# tests/test_search.cpp, the forced-move stop (audit-1, B-1): White's only
# legal move is g2g3 (in check from the queen on h4), and a quiet position
# with more than one.
check([m.uci() for m in board_of('rnb1kbnr/pppp1ppp/8/4p3/7q/5P2/PPPPP1PP/RNBQKBNR w KQkq - 1 3').legal_moves] == ['g2g3'],
      'forced move: g2g3 only')

print(f'{failures} failures')
sys.exit(1 if failures else 0)
