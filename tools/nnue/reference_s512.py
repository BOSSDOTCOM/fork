# SPDX-License-Identifier: GPL-3.0-or-later

"""Independent integer reference for the bake-off candidates S-512 and H-512
(EXPERIMENT BRANCH; KB phase4-designs/design-speed.md, judgement.md's
H-512), written from the designs, not from Fork's C++
(src/eval/nnue/single_layer.hpp).

`write OUTDIR [--seed N]` writes a random S-512 network within the
kernels' bounds as raw little-endian arrays (s512.bin: feature weights
768 x 512 i16 feature-major, feature biases 512 i16, output weights 8 x
1024 i16, output biases 8 i32, scale i32) and s512.expect: "FEN | R-int" for
tests/nnue/parity.epd. The C++ test bakeoff/S-512 parity reads both.

S-512 by the design: per perspective, the square seen from it (ranks flipped
for Black), files mirrored when that perspective's own king stands on files
a-d; index 384 * [colour != perspective] + 64 * type + square; accumulator
sums; SCReLU a = clamp(x, 0, 255), term = int16(a * w) * a; bucket =
min(7, (pieces - 1) // 4); out = trunc(sum / 255) + bias; cp = trunc(out * S /
(255 * 64)), clamped inside +-20000.

H-512 (--arch h512): the same, with 768 inputs per king region (the region
of the perspective's own king, from its mirrored square through
REGION_MAP, fitted by tools/nnue/fit_regions.py), so index + 768 * region,
and the bucket from game_phase (knights and bishops 1, rooks 2, queens 4,
capped at 24) through PHASE_BUCKETS.
"""
import argparse
import random
import struct
import sys
from pathlib import Path

import chess

H, BUCKETS, QA, QB = 512, 8, 255, 64
REGION_MAP = [0, 2, 1, 1, 2, 2, 1, 1, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]
PHASE_BUCKETS = [0, 0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 3, 4, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 7, 7]
PHASE = {chess.KNIGHT: 1, chess.BISHOP: 1, chess.ROOK: 2, chess.QUEEN: 4}
REPO = Path(__file__).resolve().parents[2]


def trunc_div(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def features(board, persp, regions=False):
    king = board.king(persp)
    seen_king = king if persp == chess.WHITE else king ^ 56
    mirror = chess.square_file(seen_king) < 4
    base = 0
    if regions:
        f, r = chess.square_file(seen_king), chess.square_rank(seen_king)
        base = 768 * REGION_MAP[4 * r + ((7 - f) if f < 4 else f) - 4]
    out = []
    for sq, p in board.piece_map().items():
        seen = sq if persp == chess.WHITE else sq ^ 56
        if mirror:
            seen ^= 7
        out.append(base + 384 * (p.color != persp) + 64 * (p.piece_type - 1) + seen)
    return out


def r_int(net, board, arch='s512'):
    ftw, ftb, outw, outb, scale = net
    if arch == 'h512':
        bucket = PHASE_BUCKETS[min(24, sum(PHASE.get(p.piece_type, 0) for p in board.piece_map().values()))]
    else:
        bucket = min(BUCKETS - 1, (chess.popcount(board.occupied) - 1) // 4)
    total = 0
    for half, persp in enumerate((board.turn, not board.turn)):
        acc = list(ftb)
        for f in features(board, persp, arch == 'h512'):
            row = ftw[f * H:(f + 1) * H]
            for i in range(H):
                acc[i] += row[i]
        w = outw[bucket * 2 * H + half * H: bucket * 2 * H + (half + 1) * H]
        for x, wi in zip(acc, w):
            a = min(max(x, 0), QA)
            term = a * wi
            assert -32768 <= term <= 32767
            total += term * a
    out = trunc_div(total, QA) + outb[bucket]
    cp = trunc_div(out * scale, QA * QB)
    return max(-19999, min(19999, cp))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    w = sub.add_parser('write')
    w.add_argument('outdir')
    w.add_argument('--seed', type=int, default=11)
    w.add_argument('--arch', choices=['s512', 'h512'], default='s512')
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    inputs = 768 * (4 if a.arch == 'h512' else 1)
    ftw = [rng.randint(-900, 900) for _ in range(inputs * H)]
    ftb = [rng.randint(-2000, 2000) for _ in range(H)]
    outw = [rng.randint(-128, 128) for _ in range(BUCKETS * 2 * H)]
    outb = [rng.randint(-100000, 100000) for _ in range(BUCKETS)]
    scale = 400
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f'{a.arch}.bin').write_bytes(struct.pack(f'<{len(ftw)}h', *ftw) + struct.pack(f'<{H}h', *ftb) +
                                   struct.pack(f'<{len(outw)}h', *outw) + struct.pack(f'<{BUCKETS}i', *outb) +
                                   struct.pack('<i', scale))
    net = (ftw, ftb, outw, outb, scale)
    fens = [l.strip() for l in open(REPO / 'tests' / 'nnue' / 'parity.epd', encoding='utf-8')
            if l.strip() and not l.startswith('#')]
    with open(out / f'{a.arch}.expect', 'w', newline='\n') as f:
        for fen in fens:
            f.write(f'{fen} | {r_int(net, chess.Board(fen), a.arch)}\n')
    print(f'{len(fens)} positions written to {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
