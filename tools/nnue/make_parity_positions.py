# SPDX-License-Identifier: GPL-3.0-or-later

"""Writes the parity test's positions, tests/nnue/parity.epd (DESIGN.md §5.3,
deliverable 6): the search bench positions (tests/datagen_openings.epd,
cited in src/search/search_bench.cpp), then positions sampled with a fixed
seed from Fork's own self-play shards, preferring ones that add input
features not yet covered, until every reachable feature (pawns never stand
on the first or last rank) is active somewhere or the shards run out.
Prints the coverage.

    make_parity_positions.py OUT SHARD... [--count N] [--seed S]
"""
import argparse
import random
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'datagen'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import reference  # noqa: E402
import verify_games as vg  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def reachable():
    out = set()
    for persp in (chess.WHITE, chess.BLACK):
        for color in (chess.WHITE, chess.BLACK):
            for kind in range(1, 7):
                for sq in range(64):
                    if kind == chess.PAWN and chess.square_rank(sq) in (0, 7):
                        continue
                    b = chess.Board(None)
                    b.set_piece_at(sq, chess.Piece(kind, color))
                    out.update(reference.features(b, persp))
    return out


def shard_positions(paths, rng, per_shard):
    for path in paths:
        data = Path(path).read_bytes()
        i, positions = 0, []
        while i + 32 <= len(data):
            board, _ = vg.decode_board(data[i:i + 32])
            i += 32
            while i + 4 <= len(data):
                code = vg.u16(data, i)
                i += 4
                if code == 0:
                    break
                positions.append(board.fen())
                board.push(next(m for m in board.legal_moves if vg.code_of(board, m) == code))
        rng.shuffle(positions)
        yield from positions[:per_shard]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('out')
    ap.add_argument('shards', nargs='+')
    ap.add_argument('--count', type=int, default=400)
    ap.add_argument('--seed', type=int, default=20261029)
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    bench = [l.strip() for l in open(REPO / 'tests' / 'datagen_openings.epd') if l.strip() and not l.startswith('#')]
    want = reachable()
    covered = set()
    chosen = []
    for fen in bench:
        b = chess.Board(fen)
        covered.update(reference.features(b, chess.WHITE) + reference.features(b, chess.BLACK))
    pool = list(shard_positions(a.shards, rng, 20000))
    # First positions that add features, then a plain sample, to --count.
    for fen in pool:
        if len(chosen) >= a.count:
            break
        b = chess.Board(fen)
        f = set(reference.features(b, chess.WHITE) + reference.features(b, chess.BLACK))
        if f - covered:
            covered |= f
            chosen.append(fen)
    rest = [p for p in pool if p not in set(chosen)]
    chosen += rest[:max(0, a.count - len(chosen))]
    with open(a.out, 'w', newline='\n') as f:
        f.write('# The trainer-engine parity positions (DESIGN.md §5.3, deliverable 6), written by\n'
                f'# tools/nnue/make_parity_positions.py --seed {a.seed}: the search bench positions\n'
                '# (cited in src/search/search_bench.cpp), then positions from Fork\'s own\n'
                '# generation-0 self-play shards.\n')
        for fen in bench + chosen:
            f.write(fen + '\n')
    print(f'{len(bench) + len(chosen)} positions; reachable features covered: {len(covered & want)} of {len(want)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
