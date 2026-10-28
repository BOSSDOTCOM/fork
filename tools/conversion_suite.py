# SPDX-License-Identifier: GPL-3.0-or-later

"""Deliverable 7's won-ending conversion suite (DESIGN.md §5.2): TB-won
positions near the fifty-move limit, played out by Fork (with the tables)
against a TB-perfect defender; the share Fork converts before the
fifty-move rule draws the game.

Positions: random legal 4-5 piece positions in the installed tables, with
the side to move winning (WDL 2) and its halfmove clock set so that the
distance to zeroing plus the clock is within 100 by a small margin (seeded,
reproducible). With a running halfmove clock Fork's in-search probes do not
apply (they need a zero clock), so this exercises the root ranking by
distance to zero under the fifty-move rule.

The defender (python-chess's Syzygy prober): among its legal moves it plays
one that keeps the best result for it (a draw if any, else the longest
distance to zeroing for the winner), ties broken by the move's UCI text.
Fork plays each of its moves with `go nodes N` (deterministic, unaffected by
machine load). A game is converted when Fork mates before the fifty-move
rule (or any other draw) ends it.

    .venv/Scripts/python.exe -I tools/conversion_suite.py ENGINE SYZYGY_PATH [--positions 100] [--nodes 50000]
"""
import argparse
import random
import subprocess
import sys

import chess
import chess.syzygy

PIECES = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]


class Engine:
    def __init__(self, path, syzygy):
        self.p = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.send('uci')
        self.until('uciok')
        self.send(f'setoption name SyzygyPath value {syzygy}')
        self.send('isready')
        self.until('readyok')

    def send(self, line):
        self.p.stdin.write(line + '\n')
        self.p.stdin.flush()

    def until(self, prefix):
        while True:
            line = self.p.stdout.readline()
            if not line:
                sys.exit(f'engine closed its output waiting for {prefix!r}')
            if line.startswith(prefix):
                return line.split()

    def move(self, board, nodes):
        # The start position and every move since, as a GUI sends them, so
        # Fork sees the game's repetitions (a bare FEN hides them).
        start = board.root().fen()
        moves = ' '.join(m.uci() for m in board.move_stack)
        self.send(f'position fen {start}' + (f' moves {moves}' if moves else ''))
        self.send(f'go nodes {nodes}')
        return chess.Move.from_uci(self.until('bestmove')[1])

    def close(self):
        self.send('quit')
        self.p.wait(timeout=10)


def won_position(rng, tb, max_pieces, margin):
    """A random winning position for the side to move, its clock near the limit."""
    while True:
        board = chess.Board(None)
        squares = rng.sample(chess.SQUARES, max_pieces)
        board.set_piece_at(squares[0], chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(squares[1], chess.Piece(chess.KING, chess.BLACK))
        for sq in squares[2:2 + rng.randint(2, max_pieces - 2)]:
            kind = rng.choice(PIECES)
            if kind == chess.PAWN and chess.square_rank(sq) in (0, 7):
                continue
            board.set_piece_at(sq, chess.Piece(kind, rng.choice([chess.WHITE, chess.BLACK])))
        board.turn = rng.choice([chess.WHITE, chess.BLACK])
        board.castling_rights = chess.BB_EMPTY
        board.halfmove_clock = 0
        if not board.is_valid() or board.is_game_over():
            continue
        try:
            if tb.probe_wdl(board) != 2:
                continue
            dtz = tb.probe_dtz(board)
        except KeyError:
            continue
        if not 0 < dtz < 100 - margin:
            continue
        board.halfmove_clock = 100 - margin - dtz  # a real win, but only just
        if tb.probe_wdl(board) == 2:  # still a win with that clock (python-chess counts the clock)
            return board


def defender_move(board, tb):
    """The move that keeps the defender's best result, longest from zeroing."""
    best, best_key = None, None
    for move in sorted(board.legal_moves, key=lambda m: m.uci()):
        board.push(move)
        try:
            wdl = -tb.probe_wdl(board)  # from the defender's side
            dtz = tb.probe_dtz(board) if not board.is_game_over() else 0
        except KeyError:
            wdl, dtz = -2, 0
        board.pop()
        key = (wdl, abs(dtz))
        if best_key is None or key > best_key:
            best, best_key = move, key
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('engine')
    ap.add_argument('path')
    ap.add_argument('--positions', type=int, default=100)
    ap.add_argument('--nodes', type=int, default=50000)
    ap.add_argument('--max-pieces', type=int, default=5)
    ap.add_argument('--margin', type=int, default=4)
    ap.add_argument('--seed', type=int, default=20261026)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    tb = chess.syzygy.open_tablebase(a.path)
    fork = Engine(a.engine, a.path)
    converted, failed = 0, []
    for _ in range(a.positions):
        board = won_position(rng, tb, a.max_pieces, a.margin)
        start = board.fen()
        winner = board.turn
        fork.send('ucinewgame')  # each game from a fresh search state: reproducible per position
        fork.send('isready')
        fork.until('readyok')
        while not board.is_game_over(claim_draw=True) and board.halfmove_clock < 100:
            board.push(fork.move(board, a.nodes) if board.turn == winner else defender_move(board, tb))
        if board.is_checkmate() and board.turn != winner:
            converted += 1
        else:
            failed.append(f'{start} -> {board.result(claim_draw=True)} (halfmove {board.halfmove_clock})')
    fork.close()
    tb.close()
    print(f'conversion: {converted} / {a.positions} converted (seed {a.seed}, margin {a.margin}, '
          f'{a.nodes} nodes per move)')
    for line in failed[:10]:
        print('  not converted:', line)
    sys.exit(0 if converted == a.positions else 1)


if __name__ == '__main__':
    main()
