# SPDX-License-Identifier: GPL-3.0-or-later

"""Deliverable 7 (DESIGN.md §5.2): Fork's Syzygy probes against an independent
prober. Random legal positions within the installed tables (no castling
rights, a zero halfmove clock: the conditions under which Fork probes) are
probed by Fork (`fork wdl PATH`, which uses the vendored Fathom) and by
python-chess's own Syzygy implementation (chess.syzygy), and every answer
must agree. Whether python-chess's prober descends from de Man's C code is
UNVERIFIED (KB tools.md §6); the 7-piece answers in tests/test_endgame_tables
are anchored to the lichess tablebase API as well.

    .venv/Scripts/python.exe -I tools/check_syzygy.py ENGINE SYZYGY_PATH [--positions 3000] [--seed 20261026]

ENGINE and SYZYGY_PATH are passed to the engine as they are (on Windows the
WSL tables can be named by their \\\\wsl.localhost\\... path).
"""
import argparse
import random
import subprocess
import sys

import chess
import chess.syzygy

PIECES = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]


def random_position(rng, max_pieces):
    """A random legal position with both kings and 0 to max_pieces-2 others."""
    while True:
        board = chess.Board(None)
        squares = rng.sample(chess.SQUARES, max_pieces)
        board.set_piece_at(squares[0], chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(squares[1], chess.Piece(chess.KING, chess.BLACK))
        for sq in squares[2:2 + rng.randint(1, max_pieces - 2)]:
            kind = rng.choice(PIECES)
            if kind == chess.PAWN and chess.square_rank(sq) in (0, 7):
                continue
            board.set_piece_at(sq, chess.Piece(kind, rng.choice([chess.WHITE, chess.BLACK])))
        board.turn = rng.choice([chess.WHITE, chess.BLACK])
        board.castling_rights = chess.BB_EMPTY
        board.halfmove_clock = 0
        if board.is_valid():
            return board


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('engine')
    ap.add_argument('path')
    ap.add_argument('--positions', type=int, default=3000)
    ap.add_argument('--max-pieces', type=int, default=5)
    ap.add_argument('--seed', type=int, default=20261026)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    tb = chess.syzygy.open_tablebase(a.path)
    boards, want = [], []
    while len(boards) < a.positions:
        board = random_position(rng, a.max_pieces)
        try:
            want.append(tb.probe_wdl(board))
        except KeyError:  # no table for this material
            continue
        boards.append(board)
    tb.close()
    out = subprocess.run([a.engine, 'wdl', a.path], input=''.join(b.fen() + '\n' for b in boards),
                         capture_output=True, text=True, check=True)
    got = out.stdout.split()
    if len(got) != len(boards):
        sys.exit(f'{len(got)} answers for {len(boards)} positions; stderr: {out.stderr.strip()}')
    print(out.stderr.strip())
    bad = [(b.fen(), g, w) for b, g, w in zip(boards, got, want) if g != str(w)]
    counts = {v: want.count(v) for v in (-2, -1, 0, 1, 2)}
    print(f'{len(boards)} positions (seed {a.seed}, up to {a.max_pieces} pieces), results {counts}: '
          f'{len(bad)} disagreements')
    for fen, g, w in bad[:10]:
        print(f'  {fen}: Fork {g}, python-chess {w}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
