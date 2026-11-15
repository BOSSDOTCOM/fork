# SPDX-License-Identifier: GPL-3.0-or-later

"""The elementary-mate suite's starting positions (tests/test_elementary_mates.cpp;
docs/ideas.md 203).

Constructed, never typed: for each ending, random legal positions are drawn
with a fixed seed (Python's random.Random, which is reproducible across
platforms for the same seed and calls), the attacker (White) to move, and
each is probed with python-chess's own Syzygy prober on the lichess mirror's
tables (CMakeLists.txt pins their SHA-256s). Only wins for the side to move
(WDL 2, so a win under the fifty-move rule) are kept. From those, per ending:

  far:     the largest distance to zero (DTZ), the hardest win the draw found;
  centre:  the largest DTZ with the defending king on d4, e4, d5 or e5;
  typical: the median win by DTZ, colour-flipped (Black attacks), so both
           colours are covered.

Ties go to the smallest FEN. Against a lone king every winning line ends in
mate (the only zeroing moves there are the lone king's captures, which
draw), so the DTZ is the length of the fastest mate in plies, as far as the
tables' DTZ rounding goes (python-chess: it can be one more). With a
defending pawn or rook it is the distance to the next pawn move or capture
instead.

    .venv/Scripts/python.exe -I tools/make_mate_positions.py SYZYGY_DIR [--seed 203] [--draws 20000]

Prints the C++ rows for the test's table: ending, label, FEN, DTZ.
"""
import argparse
import random
import sys

import chess
import chess.syzygy

# (name, the attacker's pieces besides the king, the defender's pieces besides the king)
ENDINGS = [
    ("KQvK", [chess.QUEEN], []),
    ("KRvK", [chess.ROOK], []),
    ("KBBvK", [chess.BISHOP, chess.BISHOP], []),
    ("KBNvK", [chess.BISHOP, chess.KNIGHT], []),
    ("KQvKP", [chess.QUEEN], [chess.PAWN]),
    ("KQvKR", [chess.QUEEN], [chess.ROOK]),
]
CENTRE = {chess.D4, chess.E4, chess.D5, chess.E5}


def draw_position(rng, attack, defend):
    """A random placement with White to move, or None if it is not a legal position."""
    board = chess.Board(None)
    squares = rng.sample(range(64), 2 + len(attack) + len(defend))
    board.set_piece_at(squares[0], chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(squares[1], chess.Piece(chess.KING, chess.BLACK))
    for sq, kind in zip(squares[2:], attack + defend):
        colour = chess.WHITE if len(board.pieces(kind, chess.WHITE)) < attack.count(kind) else chess.BLACK
        if kind == chess.PAWN and chess.square_rank(sq) in (0, 7):
            return None
        board.set_piece_at(sq, chess.Piece(kind, colour))
    board.turn = chess.WHITE
    if not board.is_valid() or board.is_game_over():
        return None
    return board


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("syzygy")
    ap.add_argument("--seed", type=int, default=203)
    ap.add_argument("--draws", type=int, default=20000)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    with chess.syzygy.open_tablebase(args.syzygy) as tb:
        for name, attack, defend in ENDINGS:
            wins = []  # (dtz, fen, board)
            for _ in range(args.draws):
                board = draw_position(rng, attack, defend)
                if board is None:
                    continue
                if tb.probe_wdl(board) != 2:
                    continue
                dtz = tb.probe_dtz(board)
                if dtz <= 0:
                    sys.exit(f"{name}: WDL 2 but DTZ {dtz} for {board.fen()}")
                wins.append((dtz, board.fen(), board))
            if not wins:
                sys.exit(f"{name}: no win drawn")
            typical = sorted(wins, key=lambda w: (w[0], w[1]))[len(wins) // 2]
            hardest = min(wins, key=lambda w: (-w[0], w[1]))
            centred = [w for w in wins if w[2].king(chess.BLACK) in CENTRE]
            centre = min(centred, key=lambda w: (-w[0], w[1]))
            flipped = typical[2].mirror()
            flip_dtz = tb.probe_dtz(flipped)
            if tb.probe_wdl(flipped) != 2 or flip_dtz != typical[0]:
                sys.exit(f"{name}: the colour flip of {typical[1]} does not keep its result")
            print(f"// {name}: {len(wins)} wins in {args.draws} draws")
            for label, dtz, fen in (("far", hardest[0], hardest[1]), ("centre", centre[0], centre[1]),
                                    ("typical", flip_dtz, flipped.fen())):
                print(f'{{"{name}", "{label}", "{fen}", {dtz}}},', flush=True)


if __name__ == "__main__":
    main()
