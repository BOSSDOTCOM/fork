# SPDX-License-Identifier: GPL-3.0-or-later

"""Fits the output scale S for a training run (DESIGN.md §5.3, B0 table):
the S that makes sigmoid(score / S) best predict the game result (mean
squared error, side to move's view), over the positions training keeps
(not in check, no capture or promotion played, |score| <= 20000), read from
Fork's shards with tools/datagen/verify_games.py's decoder and python-chess.

    fit_scale.py SHARD... [--positions N]
"""
import argparse
import math
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'datagen'))
import verify_games as vg  # noqa: E402

MAX_SCORE = 20000  # EvalLimit (src/eval/eval_scale.hpp), as tools/train filters


def samples(paths, limit):
    out = []
    for path in paths:
        data = Path(path).read_bytes()
        i = 0
        while i + 32 <= len(data) and len(out) < limit:
            board, res = vg.decode_board(data[i:i + 32])
            i += 32
            white = [0.0, 0.5, 1.0][res]
            while i + 4 <= len(data):
                code, score = vg.u16(data, i), vg.i16(data, i + 2)
                i += 4
                if code == 0:
                    break
                move = next(m for m in board.legal_moves if vg.code_of(board, m) == code)
                if not board.is_check() and not board.is_capture(move) and move.promotion is None \
                        and abs(score) <= MAX_SCORE:
                    stm_white = board.turn == chess.WHITE
                    out.append((score if stm_white else -score, white if stm_white else 1.0 - white))
                board.push(move)
        if len(out) >= limit:
            break
    return out[:limit]


def error(data, s):
    return sum((1.0 / (1.0 + math.exp(-sc / s)) - r) ** 2 for sc, r in data) / len(data)


def fit(data, lo=20.0, hi=3000.0):
    """Golden-section search for the S minimizing the error (unimodal in
    practice for this one-parameter logistic)."""
    g = (math.sqrt(5) - 1) / 2
    a, b = lo, hi
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = error(data, c), error(data, d)
    while b - a > 0.5:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = error(data, c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = error(data, d)
    return (a + b) / 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('shards', nargs='+')
    ap.add_argument('--positions', type=int, default=300000)
    a = ap.parse_args(argv)
    data = samples(a.shards, a.positions)
    s = fit(data)
    print(f'S = {round(s)} (fitted on {len(data)} positions; error {error(data, s):.6f}, '
          f'at S/2 {error(data, s / 2):.6f}, at 2S {error(data, 2 * s):.6f})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
