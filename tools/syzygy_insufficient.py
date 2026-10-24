"""Checks Fork's insufficient-material rule against Syzygy WDL tables.

Fork's insufficient_material() mirrors python-chess's per-side rule (so
difftest cannot catch a flaw in the rule itself; review suspicion 6). This
tool samples random legal positions for every pawnless material split with at
most five men and checks, with the Syzygy WDL tables as an independent oracle:
  - a side the rule calls insufficient never has a winning WDL score;
  - a position where both sides are insufficient is a WDL draw;
  - Fork (through `fork difftest`) gives the same overall verdict as
    python-chess.
WDL shows what can be forced, not what a helpmate could reach, so this checks
that scoring such positions as "this side cannot win" is safe for search; it
does not prove the FIDE dead-position definition.

  python -I tools/syzygy_insufficient.py --fork build/clang-release/fork \
      --syzygy <dir with 3-4-5 tables> [--samples 2000] [--seed 1]
"""
import argparse
import itertools
import random
import subprocess
import sys

import chess
import chess.syzygy

PIECES = [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]


def material_splits(max_men):
    extra = max_men - 2
    for n_white in range(extra + 1):
        for n_black in range(extra + 1 - n_white):
            for white in itertools.combinations_with_replacement(PIECES, n_white):
                for black in itertools.combinations_with_replacement(PIECES, n_black):
                    if white or black:
                        yield white, black


def random_position(rng, white, black):
    while True:
        board = chess.Board(None)
        squares = rng.sample(chess.SQUARES, 2 + len(white) + len(black))
        board.set_piece_at(squares[0], chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(squares[1], chess.Piece(chess.KING, chess.BLACK))
        rest = squares[2:]
        for sq, t in zip(rest, white):
            board.set_piece_at(sq, chess.Piece(t, chess.WHITE))
        for sq, t in zip(rest[len(white):], black):
            board.set_piece_at(sq, chess.Piece(t, chess.BLACK))
        board.turn = rng.choice([chess.WHITE, chess.BLACK])
        if board.is_valid():
            return board


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fork", required=True)
    ap.add_argument("--syzygy", required=True)
    ap.add_argument("--samples", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    positions = []  # (board, white_insufficient, black_insufficient)
    for white, black in material_splits(5):
        for _ in range(args.samples):
            b = random_position(rng, white, black)
            wi, bi = b.has_insufficient_material(chess.WHITE), b.has_insufficient_material(chess.BLACK)
            if wi or bi:
                positions.append((b, wi, bi))

    failures = 0
    checked_side = checked_both = 0
    with chess.syzygy.open_tablebase(args.syzygy) as tb:
        for b, wi, bi in positions:
            wdl = tb.probe_wdl(b)  # from the side to move
            for color, insufficient in ((chess.WHITE, wi), (chess.BLACK, bi)):
                if not insufficient:
                    continue
                checked_side += 1
                side_wdl = wdl if b.turn == color else -wdl
                if side_wdl > 0:
                    failures += 1
                    print(f"FAIL: {chess.COLOR_NAMES[color]} called insufficient but wins: {b.fen()} wdl {wdl}")
            if wi and bi:
                checked_both += 1
                if wdl != 0:
                    failures += 1
                    print(f"FAIL: both insufficient but not a draw: {b.fen()} wdl {wdl}")

    # Fork's verdict: field 4 of each difftest line is insufficient_material().
    proc = subprocess.run([args.fork, "difftest"], input="".join(f"{b.fen()}|\n" for b, _, _ in positions),
                          capture_output=True, text=True, check=True)
    lines = [l for l in proc.stdout.splitlines() if l != "end"]
    if len(lines) != len(positions):
        print(f"FAIL: fork printed {len(lines)} lines for {len(positions)} positions")
        return 1
    mismatches = 0
    for (b, wi, bi), line in zip(positions, lines):
        if line.split("|")[3] != str(int(wi and bi)):
            mismatches += 1
            print(f"FAIL: fork disagrees with python-chess: {b.fen()} -> {line}")
    failures += mismatches

    print(f"{len(positions)} positions with an insufficient side; {checked_side} side checks, "
          f"{checked_both} both-insufficient draws checked against WDL; fork agreed on "
          f"{len(positions) - mismatches}; failures {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
