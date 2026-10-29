# SPDX-License-Identifier: GPL-3.0-or-later

"""Fits the hybrid H-512's two data-derived tables (EXPERIMENT BRANCH; KB
phase4-designs/design-accuracy.md §2.1 and §2.4, judgement.md's H-512):

1. The king-region map: from positions passing the training filter, the
   own king's square for both perspectives (ranks flipped for Black, files
   mirrored to e-h: 32 cells). Every cell starts as its own region; the
   region with the smallest share is merged into its edge-adjacent
   neighbour region with the smallest share (ties: same rank first, then
   the lower cell index) until every region holds at least --theta of the
   samples and there are at most --max-regions regions.
2. The output buckets: the 25-entry table from Fork's game_phase (knights
   and bishops 1, rooks 2, queens 4, capped at 24; src/core/material.hpp)
   to 8 buckets cut at the octiles of the phase histogram.

Prints both tables as JSON (cell = 4 * rank + (file - 4), rank 0 = the
perspective's own first rank).

    fit_regions.py SHARD... [--positions N] [--theta 0.10] [--max-regions 4]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'datagen'))
import verify_games as vg  # noqa: E402

PHASE = {chess.KNIGHT: 1, chess.BISHOP: 1, chess.ROOK: 2, chess.QUEEN: 4}


def cell(king, persp):
    seen = king if persp == chess.WHITE else king ^ 56
    f, r = chess.square_file(seen), chess.square_rank(seen)
    if f < 4:
        f = 7 - f
    return 4 * r + (f - 4)


def phase(board):
    return min(24, sum(PHASE.get(p.piece_type, 0) for p in board.piece_map().values()))


def collect(paths, limit):
    cells, phases, n = Counter(), Counter(), 0
    for path in paths:
        data = Path(path).read_bytes()
        i = 0
        while i + 32 <= len(data) and n < limit:
            board, _ = vg.decode_board(data[i:i + 32])
            i += 32
            while i + 4 <= len(data):
                code, score = vg.u16(data, i), vg.i16(data, i + 2)
                i += 4
                if code == 0:
                    break
                move = next(m for m in board.legal_moves if vg.code_of(board, m) == code)
                if not board.is_check() and not board.is_capture(move) and move.promotion is None \
                        and abs(score) <= 20000:
                    for persp in (chess.WHITE, chess.BLACK):
                        cells[cell(board.king(persp), persp)] += 1
                    phases[phase(board)] += 1
                    n += 1
                board.push(move)
        if n >= limit:
            break
    return cells, phases, n


def neighbours(c):
    r, f = divmod(c, 4)
    for dr, df in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        if 0 <= r + dr < 8 and 0 <= f + df < 4:
            yield 4 * (r + dr) + f + df, dr == 0


def fit_map(cells, theta, max_regions):
    total = sum(cells.values())
    region = {c: c for c in range(32)}

    def share(rg):
        return sum(cells[c] for c in range(32) if region[c] == rg) / total

    while True:
        regions = sorted(set(region.values()))
        shares = {rg: share(rg) for rg in regions}
        if min(shares.values()) >= theta and len(regions) <= max_regions:
            break
        small = min(regions, key=lambda rg: (shares[rg], rg))
        cand = {}
        for c in range(32):
            if region[c] != small:
                continue
            for nb, same_rank in neighbours(c):
                if region[nb] != small:
                    key = (shares[region[nb]], not same_rank, region[nb])
                    cand[region[nb]] = min(cand.get(region[nb], key), key)
        target = min(cand, key=lambda rg: cand[rg])
        for c in range(32):
            if region[c] == small:
                region[c] = target
    # Renumber regions 0..B-1 in order of their lowest cell.
    order = {rg: k for k, rg in enumerate(sorted(set(region.values())))}
    return [order[region[c]] for c in range(32)]


def octile_table(phases):
    total = sum(phases.values())
    table, acc = [], 0
    for p in range(25):
        table.append(min(7, int(8 * acc / total)))
        acc += phases[p]
    return table


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('shards', nargs='+')
    ap.add_argument('--positions', type=int, default=400000)
    ap.add_argument('--theta', type=float, default=0.10)
    ap.add_argument('--max-regions', type=int, default=4)
    a = ap.parse_args(argv)
    cells, phases, n = collect(a.shards, a.positions)
    rmap = fit_map(cells, a.theta, a.max_regions)
    total = sum(cells.values())
    shares = [round(sum(cells[c] for c in range(32) if rmap[c] == r) / total, 4) for r in range(max(rmap) + 1)]
    print(json.dumps({'positions': n, 'region_map': rmap, 'region_shares': shares,
                      'phase_buckets': octile_table(phases),
                      'phase_histogram': [phases[p] for p in range(25)]}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
