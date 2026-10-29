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

AF-S (--arch afs; design-accuracy.md §5): H-512's inputs and accumulator;
v = clamp(acc, 0, 255); per perspective (side to move first) a[j] =
(v[j] * v[j + 256] + 256) >> 9 for j < 256; for the phase stack k: y1 = b1 +
sum x * W1 (16 outputs), q1 = (clamp(y1 >> 2, 0, 2032))^2 >> 11; y2 = b2 + sum q1
* W2 (32), q2 = (clamp(y2 >> 13, 0, 2016))^2 >> 11; y3 = b3 + sum q2 * W3; eval =
(y3 * M) >> 32 (floor), clamped inside +-20000.

XGR-512 (--arch xgr; design-novelty.md §1, §2.1-2.3, §5.1): 768 mirrored
inputs per XGR region of the own king's mirrored square (e1; f1-h1; rank 2;
ranks 3-8), plus the exposure plane: own/enemy x 5 non-king types x 64
squares, same orientation, active for a non-king piece that an enemy piece of
a lower value class attacks (pawn 1, knight and bishop 2, rook 3, queen 4,
king 5), or that is attacked and undefended (python-chess attacker sets).
Each row has H hidden values and 8 side lanes. Per expert k (A, B): S_k =
trunc(sum v * (v * w) / 255), v = clamp(y, 0, 255), o_k = S_k + c_k + 128 *
(lane[1+k]_stm - lane[1+k]_ntm); g = clamp(lane0_stm + lane0_ntm, 0, 255);
out = trunc((o_B * 255 + g * (o_A - o_B)) / 255); eval = trunc(out * S /
16320), clamped inside +-20000.
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


def r_int_afs(net, board):
    ftw, ftb, l1w, l1b, l2w, l2b, l3w, l3b, mult = net
    k = PHASE_BUCKETS[min(24, sum(PHASE.get(p.piece_type, 0) for p in board.piece_map().values()))]
    x = []
    for persp in (board.turn, not board.turn):
        acc = list(ftb)
        for f in features(board, persp, True):
            row = ftw[f * H:(f + 1) * H]
            for i in range(H):
                acc[i] += row[i]
        v = [min(max(t, 0), 255) for t in acc]
        x += [(v[j] * v[j + H // 2] + 256) >> 9 for j in range(H // 2)]
    q1 = []
    for o in range(16):
        w = l1w[(k * 16 + o) * H:(k * 16 + o + 1) * H]
        y = l1b[k * 16 + o] + sum(a * b for a, b in zip(x, w))
        c = min(max(y >> 2, 0), 2032)
        q1.append((c * c) >> 11)
    q2 = []
    for o in range(32):
        w = l2w[(k * 32 + o) * 16:(k * 32 + o + 1) * 16]
        y = l2b[k * 32 + o] + sum(a * b for a, b in zip(q1, w))
        c = min(max(y >> 13, 0), 2016)
        q2.append((c * c) >> 11)
    y3 = l3b[k] + sum(a * b for a, b in zip(q2, l3w[k * 32:(k + 1) * 32]))
    return max(-19999, min(19999, (y3 * mult) >> 32))


def write_afs(rng, out, fens):
    ftw = [rng.randint(-900, 900) for _ in range(4 * 768 * H)]
    ftb = [rng.randint(-2000, 2000) for _ in range(H)]
    l1w = [rng.randint(-127, 127) for _ in range(8 * 16 * H)]
    l1b = [rng.randint(-20000, 20000) for _ in range(8 * 16)]
    l2w = [rng.randint(-2000, 2000) for _ in range(8 * 32 * 16)]
    l2b = [rng.randint(-1000000, 1000000) for _ in range(8 * 32)]
    l3w = [rng.randint(-20000, 20000) for _ in range(8 * 32)]
    l3b = [rng.randint(-1000000, 1000000) for _ in range(8)]
    mult = 105000
    (out / 'afs.bin').write_bytes(
        struct.pack(f'<{len(ftw)}h', *ftw) + struct.pack(f'<{H}h', *ftb) + struct.pack(f'<{len(l1w)}b', *l1w) +
        struct.pack(f'<{len(l1b)}i', *l1b) + struct.pack(f'<{len(l2w)}h', *l2w) + struct.pack(f'<{len(l2b)}i', *l2b) +
        struct.pack(f'<{len(l3w)}h', *l3w) + struct.pack(f'<{len(l3b)}i', *l3b) + struct.pack('<q', mult))
    net = (ftw, ftb, l1w, l1b, l2w, l2b, l3w, l3b, mult)
    with open(out / 'afs.expect', 'w', newline='\n') as f:
        for fen in fens:
            f.write(f'{fen} | {r_int_afs(net, chess.Board(fen))}\n')


XGR_CLASS = {chess.PAWN: 1, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5}
SIDE = 8


def xgr_exposed(board):
    out = []
    for sq, p in board.piece_map().items():
        if p.piece_type == chess.KING:
            continue
        enemy = board.attackers(not p.color, sq)
        if not enemy:
            continue
        lower = any(XGR_CLASS[board.piece_type_at(a)] < XGR_CLASS[p.piece_type] for a in enemy)
        if lower or not board.attackers(p.color, sq):
            out.append((sq, p))
    return out


def xgr_rows(board, persp):
    king = board.king(persp)
    seen_king = king if persp == chess.WHITE else king ^ 56
    f, r = chess.square_file(seen_king), chess.square_rank(seen_king)
    mirror = f < 4
    fm = 7 - f if mirror else f
    region = (0 if fm == 4 else 1) if r == 0 else (2 if r == 1 else 3)

    def oriented(sq):
        seen = sq if persp == chess.WHITE else sq ^ 56
        return seen ^ 7 if mirror else seen

    base = [768 * region + 384 * (p.color != persp) + 64 * (p.piece_type - 1) + oriented(sq)
            for sq, p in board.piece_map().items()]
    expo = [320 * (p.color != persp) + 64 * (p.piece_type - 1) + oriented(sq) for sq, p in xgr_exposed(board)]
    return base, expo


def r_int_xgr(net, board):
    ftw, fts, xw, xs, ftb, sb, ew, eb, scale = net
    ys, sides = [], []
    for persp in (board.turn, not board.turn):
        y, side = list(ftb), list(sb)
        base, expo = xgr_rows(board, persp)
        for rows, w, s in ((base, ftw, fts), (expo, xw, xs)):
            for f in rows:
                for i in range(H):
                    y[i] += w[f * H + i]
                for i in range(SIDE):
                    side[i] += s[f * SIDE + i]
        assert all(-32768 <= t <= 32767 for t in y + side)
        ys.append(y)
        sides.append(side)
    o = []
    for k in range(2):
        total = 0
        for half in range(2):
            for i in range(H):
                v = min(max(ys[half][i], 0), 255)
                vw = v * ew[k * 2 * H + half * H + i]
                assert -32768 <= vw <= 32767
                total += vw * v
        o.append(trunc_div(total, 255) + eb[k] + 128 * (sides[0][1 + k] - sides[1][1 + k]))
    g = min(max(sides[0][0] + sides[1][0], 0), 255)
    out = trunc_div(o[1] * 255 + g * (o[0] - o[1]), 255)
    return max(-19999, min(19999, trunc_div(out * scale, 16320)))


def write_xgr(rng, out, fens):
    ftw = [rng.randint(-500, 500) for _ in range(4 * 768 * H)]
    fts = [rng.randint(-8, 8) for _ in range(4 * 768 * SIDE)]
    xw = [rng.randint(-500, 500) for _ in range(640 * H)]
    xs = [rng.randint(-8, 8) for _ in range(640 * SIDE)]
    ftb = [rng.randint(-1500, 1500) for _ in range(H)]
    sb = [rng.randint(-50, 50) for _ in range(SIDE)]
    ew = [rng.randint(-127, 127) for _ in range(2 * 2 * H)]
    eb = [rng.randint(-100000, 100000) for _ in range(2)]
    scale = 40
    (out / 'xgr.bin').write_bytes(
        struct.pack(f'<{len(ftw)}h', *ftw) + struct.pack(f'<{len(fts)}h', *fts) + struct.pack(f'<{len(xw)}h', *xw) +
        struct.pack(f'<{len(xs)}h', *xs) + struct.pack(f'<{H}h', *ftb) + struct.pack(f'<{SIDE}h', *sb) +
        struct.pack(f'<{len(ew)}h', *ew) + struct.pack('<2i', *eb) + struct.pack('<i', scale))
    net = (ftw, fts, xw, xs, ftb, sb, ew, eb, scale)
    with open(out / 'xgr.expect', 'w', newline='\n') as f:
        for fen in fens:
            board = chess.Board(fen)
            f.write(f'{fen} | {r_int_xgr(net, board)} | {len(xgr_exposed(board))}\n')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    w = sub.add_parser('write')
    w.add_argument('outdir')
    w.add_argument('--seed', type=int, default=11)
    w.add_argument('--arch', choices=['s512', 'h512', 'afs', 'xgr'], default='s512')
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    fens_all = [l.strip() for l in open(REPO / 'tests' / 'nnue' / 'parity.epd', encoding='utf-8')
                if l.strip() and not l.startswith('#')]
    if a.arch in ('afs', 'xgr'):
        out = Path(a.outdir)
        out.mkdir(parents=True, exist_ok=True)
        (write_afs if a.arch == 'afs' else write_xgr)(rng, out, fens_all)
        print(f'{len(fens_all)} positions written to {out}')
        return 0
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
