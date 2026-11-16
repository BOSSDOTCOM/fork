# SPDX-License-Identifier: GPL-3.0-or-later

"""Candidate positions for the TT halfmove guard's test (search suite, "the
TT halfmove guard: fifty-move draws the unguarded TT cutoff misses",
tests/test_search.cpp; written for its narrowed variant, the recorded
fallback on branch tier2/tt-halfmove-guard-high).

Fork's own games only (fastchess PGNs of an SPRT run; never another
engine's data). Each game is replayed with python-chess; a position is a
candidate when it has at most 5 pieces, no pawns (so only captures and mates
can end the fifty-move count), and the Syzygy tables (DTZ, the 3-4-5 set)
say the side to move wins or loses at clock 0 (WDL +-2) with |DTZ| at least
`--min-dtz` plies: with the clock at 100 - depth no zeroing move or mate can
be forced before the rule, so the fifty-move rule makes the game a draw
there (the DTZ oracle), though the same position at clock 0 is a real win.
The first such position of each game is kept (distinct EPDs), in the order
of the PGN paths (sorted, with / separators) and the games within them.

Output, one line per candidate: the FEN at clock 0, WDL, DTZ, and its source
(PGN path relative to the given root, game number from 1, ply from 0).

usage: python -I tools/fifty_guard_positions.py --tables DIR --root DIR \
         --pgn GLOB [--pgn GLOB ...] [--min-dtz 7] [--count 40]
"""
import argparse
import glob
import os
import sys

import chess
import chess.pgn
import chess.syzygy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", required=True)
    ap.add_argument("--root", required=True, help="folder the PGN paths are reported relative to")
    ap.add_argument("--pgn", action="append", required=True)
    ap.add_argument("--min-dtz", type=int, default=7)
    ap.add_argument("--count", type=int, default=40)
    args = ap.parse_args()

    paths = sorted({p.replace(os.sep, "/") for g in args.pgn for p in glob.glob(g)})
    seen = set()
    found = 0
    with chess.syzygy.open_tablebase(args.tables) as tb:
        for path in paths:
            with open(path, encoding="utf-8") as f:
                game_no = 0
                while found < args.count:
                    game = chess.pgn.read_game(f)
                    if game is None:
                        break
                    game_no += 1
                    board = game.board()
                    ply = 0
                    for move in [None, *game.mainline_moves()]:
                        if move is not None:
                            board.push(move)
                            ply += 1
                        if chess.popcount(board.occupied) > 5 or board.pawns or board.is_game_over():
                            continue
                        epd = board.epd()
                        if epd in seen:
                            continue
                        probe = board.copy(stack=False)
                        probe.halfmove_clock = 0
                        wdl = tb.probe_wdl(probe)
                        if abs(wdl) != 2:
                            continue
                        dtz = tb.probe_dtz(probe)
                        if abs(dtz) < args.min_dtz:
                            continue
                        seen.add(epd)
                        found += 1
                        rel = os.path.relpath(path, args.root).replace(os.sep, "/")
                        print(f"{probe.fen()}\twdl {wdl}\tdtz {dtz}\t{rel} game {game_no} ply {ply}")
                        break
            if found >= args.count:
                break
    print(f"{found} candidates", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
