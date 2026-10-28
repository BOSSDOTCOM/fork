"""Checks the facts that tests/test_search.cpp and tests/test_eval.cpp rely on
for their constructed positions, with python-chess as the independent oracle:
legal FENs, forced mates in N (and none sooner), checkmate and stalemate, and
the repetition. Exits non-zero if any fact is wrong.

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

print(f'{failures} failures')
sys.exit(1 if failures else 0)
