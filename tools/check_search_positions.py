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

print(f'{failures} failures')
sys.exit(1 if failures else 0)
