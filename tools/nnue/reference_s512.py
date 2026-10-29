# SPDX-License-Identifier: GPL-3.0-or-later

"""Independent integer reference for the bake-off candidate S-512 (EXPERIMENT
BRANCH; KB phase4-designs/design-speed.md), written from the design, not
from Fork's C++ (src/eval/nnue/single_layer.hpp).

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
"""
import argparse
import random
import struct
import sys
from pathlib import Path

import chess

H, INPUTS, BUCKETS, QA, QB = 512, 768, 8, 255, 64
REPO = Path(__file__).resolve().parents[2]


def trunc_div(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def features(board, persp):
    king = board.king(persp)
    seen_king = king if persp == chess.WHITE else king ^ 56
    mirror = chess.square_file(seen_king) < 4
    out = []
    for sq, p in board.piece_map().items():
        seen = sq if persp == chess.WHITE else sq ^ 56
        if mirror:
            seen ^= 7
        out.append(384 * (p.color != persp) + 64 * (p.piece_type - 1) + seen)
    return out


def r_int(net, board):
    ftw, ftb, outw, outb, scale = net
    bucket = min(BUCKETS - 1, (chess.popcount(board.occupied) - 1) // 4)
    total = 0
    for half, persp in enumerate((board.turn, not board.turn)):
        acc = list(ftb)
        for f in features(board, persp):
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
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    ftw = [rng.randint(-900, 900) for _ in range(INPUTS * H)]
    ftb = [rng.randint(-2000, 2000) for _ in range(H)]
    outw = [rng.randint(-128, 128) for _ in range(BUCKETS * 2 * H)]
    outb = [rng.randint(-100000, 100000) for _ in range(BUCKETS)]
    scale = 400
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 's512.bin').write_bytes(struct.pack(f'<{len(ftw)}h', *ftw) + struct.pack(f'<{H}h', *ftb) +
                                   struct.pack(f'<{len(outw)}h', *outw) + struct.pack(f'<{BUCKETS}i', *outb) +
                                   struct.pack('<i', scale))
    net = (ftw, ftb, outw, outb, scale)
    fens = [l.strip() for l in open(REPO / 'tests' / 'nnue' / 'parity.epd', encoding='utf-8')
            if l.strip() and not l.startswith('#')]
    with open(out / 's512.expect', 'w', newline='\n') as f:
        for fen in fens:
            f.write(f'{fen} | {r_int(net, chess.Board(fen))}\n')
    print(f'{len(fens)} positions written to {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
