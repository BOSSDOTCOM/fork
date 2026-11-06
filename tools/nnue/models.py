# SPDX-License-Identifier: GPL-3.0-or-later

"""The bake-off architectures in Fork's independent NNUE reference (DESIGN.md
§5.4; KB phase4-designs/judgement.md and the three design files), written
from the designs, not from Fork's training program or C++:

- features: each perspective's active inputs from python-chess (the board
  seen from that side: flipped vertically for Black, "ours" first; mirrored
  left-right when that side's own king is on files a-d; one 768 block per
  king region; the factoriser and XGR's exposure inputs) and the bucket;
- R-float: the float forward pass on bullet's weights.bin (factorisers
  still separate, as bullet trains them);
- R-quant: bullet's save list redone from weights.bin (merge each
  factoriser into its rows by an f32 addition, transpose, then f64 product
  rounded half away from zero), and the scales of the tensors Fork's
  converter quantizes itself;
- R-int: Fork's integer arithmetic on Fork's net file (the payload layout
  below), exactly as the designs specify it.

Architecture ids: 2 S-512, 3 H-512, 4 AF-S, 5 XGR-512 (1 is B0, in
reference.py). Fork's net file, version 2: the 64-byte header (magic,
version 2, id, saved inputs, hidden, QA, QB, S, bucket count, checksum),
then a 128-byte map block (32 region bytes, 25 phase-table bytes, zeros),
then the tensors, little-endian:
- 2, 3: feature weights i16 [inputs][H], feature biases i16 [H], output
  weights i16 [8][2H] (side to move's half first), output biases i32 [8];
- 4: feature weights and biases as above, then per stack k: L1 i8 [8][16][H],
  L1 biases i32 [8][16], L2 i16 [8][32][16], L2 biases i32 [8][32], L3 i16
  [8][32], L3 biases i32 [8], and the output multiplier M (i64);
- 5: feature weights i16 [inputs][H], biases i16 [H], side weights i16
  [inputs][3] (lane 0 the gate, 1 and 2 the linear lanes; three, the lanes used), side
  biases i16 [3], expert A weights i16 [2H], bias i32, expert B likewise.
"""
import math
import struct
from fractions import Fraction

import chess

EVAL_LIMIT = 20000  # src/eval/eval_scale.hpp
QA, QB = 255, 64
PIECE_SQUARES = 768
EXPOSURE_ROWS = 640
XGR_REGIONS = [0, 1, 1, 1, 2, 2, 2, 2] + [3] * 24  # e1; f1-h1; rank 2; ranks 3-8 (design-novelty.md §2.1)
PHASE_WEIGHT = {chess.KNIGHT: 1, chess.BISHOP: 1, chess.ROOK: 2, chess.QUEEN: 4}
CLASS = {chess.PAWN: 1, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5}
ARCH = {'s512': 2, 'h512': 3, 'afs': 4, 'xgr512': 5}
MAP_BLOCK = 128

# AF-S's integer scales (design-accuracy.md §5.3-5.4), as exact rationals.
AF_PAIR_SCALE = Fraction(255 * 255, 512)          # one pairwise unit per 1.0
AF_S1 = 64 * AF_PAIR_SCALE                         # L1 sums
AF_SQ1 = (AF_S1 / 4) ** 2 / 2048                   # q1 = (c1 * c1) >> 11
AF_S2 = AF_SQ1 * 8192                              # L2 sums
AF_SQ2 = AF_SQ1 ** 2 / 2048                        # c2 = clamp(y2 >> 13), q2 = (c2 * c2) >> 11
AF_S3 = AF_SQ2 * 8192                              # L3 sums


class Arch:
    def __init__(self, name, regions=None, table=None):
        self.name, self.id = name, ARCH[name]
        self.hidden = 512
        if name == 'xgr512':
            regions = XGR_REGIONS
        self.regions = list(regions) if regions is not None else [0] * 32
        self.region_count = max(self.regions) + 1
        self.factoriser = name in ('h512', 'afs', 'xgr512')
        self.exposure = name == 'xgr512'
        self.picker = 'phase' if name != 'xgr512' else None
        self.table = list(table) if table is not None else []
        if self.picker:
            assert len(self.table) == 25 and max(self.table) <= 7
        if name in ('h512', 'afs'):
            assert len(self.regions) == 32

    @property
    def factor_start(self):
        return PIECE_SQUARES * self.region_count

    @property
    def exposure_start(self):
        return self.factor_start + (PIECE_SQUARES if self.factoriser else 0)

    @property
    def saved_inputs(self):
        return self.factor_start + (EXPOSURE_ROWS if self.exposure else 0)


def exposed_squares(board):
    """XGR's exposure rule on python-chess's attack sets (pseudo-attacks:
    sliders stop at the first piece, pins ignored, no en passant; kings
    attack and defend and rank above the queen)."""
    out = set()
    for sq, piece in board.piece_map().items():
        if piece.piece_type == chess.KING:
            continue
        enemy = board.attackers(not piece.color, sq)
        if not enemy:
            continue
        lowest = min(CLASS[board.piece_at(a).piece_type] for a in enemy)
        if lowest < CLASS[piece.piece_type] or not board.attackers(piece.color, sq):
            out.add(sq)
    return out


def features(arch, board, persp, exposed=None):
    """Active inputs of perspective `persp` (a colour), as training sees
    them (factoriser and exposure inputs included)."""
    orient = (lambda s: s) if persp == chess.WHITE else (lambda s: s ^ 56)
    king = orient(board.king(persp))
    flip = 7 if king % 8 < 4 else 0
    k = king ^ flip
    region = arch.regions[(k // 8) * 4 + k % 8 - 4]
    out = []
    for sq, piece in board.piece_map().items():
        own = int(piece.color != persp)
        kind = piece.piece_type - 1
        s = orient(sq) ^ flip
        base = 384 * own + 64 * kind + s
        out.append(PIECE_SQUARES * region + base)
        if arch.factoriser:
            out.append(arch.factor_start + base)
        if arch.exposure and sq in exposed:
            out.append(arch.exposure_start + 320 * own + 64 * kind + s)
            out.append(arch.exposure_start + EXPOSURE_ROWS + 5 * own + kind)
    return sorted(out)


def bucket(arch, board):
    if arch.picker == 'phase':
        phase = sum(PHASE_WEIGHT.get(p.piece_type, 0) for p in board.piece_map().values())
        return arch.table[min(phase, 24)]
    return 0


def both_perspectives(arch, board):
    exposed = exposed_squares(board) if arch.exposure else None
    return (features(arch, board, board.turn, exposed), features(arch, board, not board.turn, exposed),
            bucket(arch, board))


def merged_index(arch, f):
    """The saved row an active training input lands on after the merge, or
    None for a factoriser input."""
    if f < arch.factor_start:
        return f
    if arch.exposure and arch.exposure_start <= f < arch.exposure_start + EXPOSURE_ROWS:
        return arch.factor_start + (f - arch.exposure_start)
    return None


# ---- float forward pass (R-float) on weights.bin ----

def column_sum(w, rows, active, bias):
    """bias + the sum of the active inputs' columns of a column-major
    rows x inputs weight."""
    acc = list(bias)
    for f in active:
        col = w[f * rows:(f + 1) * rows]
        for i in range(rows):
            acc[i] += col[i]
    return acc


def clip(x):
    return min(max(x, 0.0), 1.0)


def dense(w, b, x, rows, block=0):
    """Rows block*rows .. of a column-major (all rows) x len(x) weight
    times x, plus the bias (bullet's select keeps one block of rows)."""
    total_rows = len(b)
    out = []
    for r in range(block * rows, (block + 1) * rows):
        out.append(b[r] + sum(w[i * total_rows + r] * x[i] for i in range(len(x))))
    return out


def r_float(arch, w, board):
    stm, ntm, k = both_perspectives(arch, board)
    h = arch.hidden
    a_s, a_n = (column_sum(w['l0w'], h, f, w['l0b']) for f in (stm, ntm))
    if arch.name in ('s512', 'h512'):
        x = [clip(v) ** 2 for v in a_s + a_n]
        return dense(w['l1w'], w['l1b'], x, 1, k)[0]
    if arch.name == 'afs':
        half = h // 2
        x = [clip(a[j]) * clip(a[j + half]) for a in (a_s, a_n) for j in range(half)]
        y1 = [clip(v) ** 2 for v in dense(w['l1w'], w['l1b'], x, 16, k)]
        y2 = [clip(v) ** 2 for v in dense(w['l2w'], w['l2b'], y1, 32, k)]
        return dense(w['l3w'], w['l3b'], y2, 1, k)[0]
    # xgr512
    x = [clip(v) ** 2 for v in a_s + a_n]
    s_s, s_n = (column_sum(w['s0w'], 3, f, w['s0b']) for f in (stm, ntm))
    gate = clip(s_s[0] + s_n[0])
    out_a = dense(w['oaw'], w['oab'], x, 1)[0] + 2.0 * (s_s[1] - s_n[1])
    out_b = dense(w['obw'], w['obb'], x, 1)[0] + 2.0 * (s_s[2] - s_n[2])
    return out_b + gate * (out_a - out_b)


# ---- bullet's quantization, redone (R-quant) ----

def to_f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


def round_half_away(x):
    """Exact round half away from zero of a float64 or a Fraction."""
    if isinstance(x, Fraction):
        n = abs(x.numerator) * 2 + x.denominator
        r = n // (2 * x.denominator)
        return r if x >= 0 else -r
    t = math.trunc(x)
    if abs(x - t) >= 0.5:
        t += 1 if x > 0 else -1
    return int(t)


RANGES = {'i8': (-128, 127), 'i16': (-32768, 32767), 'i32': (-2**31, 2**31 - 1), 'i64': (-2**63, 2**63 - 1)}


def quantise(values, factor, kind):
    lo, hi = RANGES[kind]
    out = []
    for v in values:
        x = round_half_away(Fraction(factor) * Fraction(v)) if isinstance(factor, Fraction) \
            else round_half_away(float(factor) * float(v))
        if not lo <= x <= hi:
            raise ValueError(f'{v} x {factor} = {x} leaves the {kind} range')
        out.append(x)
    return out


def merge(arch, w, rows):
    """A first-layer weight with each factoriser column added to the
    columns it serves (f32 sums), the factoriser columns dropped."""
    def col(c):
        return w[c * rows:(c + 1) * rows]
    out = []
    for r in range(arch.region_count):
        for f in range(PIECE_SQUARES):
            a, b = col(PIECE_SQUARES * r + f), col(arch.factor_start + f) if arch.factoriser else None
            out.extend(a if b is None else [to_f32(x + y) for x, y in zip(a, b)])
    if arch.exposure:
        x0 = arch.exposure_start
        for e in range(EXPOSURE_ROWS):
            own, kind = e // 320, (e % 320) // 64
            a, b = col(x0 + e), col(x0 + EXPOSURE_ROWS + 5 * own + kind)
            out.extend(to_f32(x + y) for x, y in zip(a, b))
    return out


def transpose(w, rows, cols):
    """A column-major rows x cols weight in row-major order."""
    return [w[c * rows + r] for r in range(rows) for c in range(cols)]


def saved_tensors(arch, w):
    """bullet's quantised.bin tensors (save order) from weights.bin, plus
    the further tensors Fork's file holds: {name: (kind, values)}."""
    h, nb = arch.hidden, 8
    t = {}
    l0 = merge(arch, w['l0w'], h) if arch.factoriser else w['l0w']
    t['l0w'] = ('i16', quantise(l0, 255, 'i16'))
    t['l0b'] = ('i16', quantise(w['l0b'], 255, 'i16'))
    if arch.name in ('s512', 'h512'):
        t['l1w'] = ('i16', quantise(transpose(w['l1w'], nb, 2 * h), 64, 'i16'))
        t['l1b'] = ('i32', quantise(w['l1b'], 255 * 64, 'i32'))
    elif arch.name == 'afs':
        t['l1w'] = ('i8', quantise(transpose(w['l1w'], 16 * nb, h), 64, 'i8'))
        t['l1b'] = ('f32', list(w['l1b']))
        t['l2w'] = ('i16', quantise(transpose(w['l2w'], 32 * nb, 16), 8192, 'i16'))
        t['l2b'] = ('f32', list(w['l2b']))
        t['l3w'] = ('i16', quantise(transpose(w['l3w'], nb, 32), 8192, 'i16'))
        t['l3b'] = ('f32', list(w['l3b']))
    else:
        t['s0w'] = ('i16', quantise(merge(arch, w['s0w'], 3), 255, 'i16'))
        t['s0b'] = ('i16', quantise(w['s0b'], 255, 'i16'))
        for e in ('oa', 'ob'):
            t[e + 'w'] = ('i16', quantise(w[e + 'w'], 64, 'i16'))
            t[e + 'b'] = ('i32', quantise(w[e + 'b'], 255 * 64, 'i32'))
    return t


def af_multiplier(scale):
    """AF-S's output multiplier M = round(S * 2^32 / s_y3)."""
    return round_half_away(Fraction(scale) * 2**32 / AF_S3)


def fork_tensors(arch, t, scale):
    """Fork's payload tensors (after the map block) from the saved tensors,
    in file order: [(kind, values)]."""
    h = arch.hidden
    if arch.name in ('s512', 'h512'):
        return [t['l0w'], t['l0b'], t['l1w'], t['l1b']]
    if arch.name == 'afs':
        return [t['l0w'], t['l0b'], t['l1w'], ('i32', quantise(t['l1b'][1], AF_S1, 'i32')),
                t['l2w'], ('i32', quantise(t['l2b'][1], AF_S2, 'i32')),
                t['l3w'], ('i32', quantise(t['l3b'][1], AF_S3, 'i32')), ('i64', [af_multiplier(scale)])]
    assert len(t['l0w'][1]) == arch.saved_inputs * h and len(t['s0w'][1]) == arch.saved_inputs * 3
    return [t['l0w'], t['l0b'], t['s0w'], t['s0b'], t['oaw'], t['oab'], t['obw'], t['obb']]


CODES = {'i8': 'b', 'i16': 'h', 'i32': 'i', 'i64': 'q', 'f32': 'f'}


def pack(tensors):
    return b''.join(struct.pack(f'<{len(v)}{CODES[k]}', *v) for k, v in tensors)


def map_block(arch):
    block = bytes(arch.regions) + bytes(arch.table)
    return block + bytes(MAP_BLOCK - len(block))


def arch_from_net(name, payload):
    """The architecture with the maps a net file's map block stores (an
    evaluation must use the net's own maps, not a description's)."""
    regions = list(payload[:32]) if name in ('h512', 'afs') else None
    table = list(payload[32:57]) if name != 'xgr512' else None
    return Arch(name, regions, table)


def unpack(arch, payload):
    """Fork's payload as {name: values}, in the layout above."""
    h, n = arch.hidden, arch.saved_inputs
    at = MAP_BLOCK
    shapes = {'s512': [('ftw', 'i16', n * h), ('ftb', 'i16', h), ('outw', 'i16', 8 * 2 * h), ('outb', 'i32', 8)],
              'afs': [('ftw', 'i16', n * h), ('ftb', 'i16', h), ('l1w', 'i8', 8 * 16 * h), ('l1b', 'i32', 128),
                      ('l2w', 'i16', 8 * 32 * 16), ('l2b', 'i32', 256), ('l3w', 'i16', 256), ('l3b', 'i32', 8),
                      ('mult', 'i64', 1)],
              'xgr512': [('ftw', 'i16', n * h), ('ftb', 'i16', h), ('sidew', 'i16', n * 3), ('sideb', 'i16', 3),
                         ('aw', 'i16', 2 * h), ('ab', 'i32', 1), ('bw', 'i16', 2 * h), ('bb', 'i32', 1)]}
    shapes['h512'] = shapes['s512']
    out = {'regions': list(payload[:32]), 'table': list(payload[32:65])}
    for name, kind, count in shapes[arch.name]:
        size = struct.calcsize('<' + CODES[kind])
        out[name] = list(struct.unpack_from(f'<{count}{CODES[kind]}', payload, at))
        at += size * count
    if at != len(payload):
        raise ValueError(f'payload of {len(payload)} bytes, the layout needs {at}')
    return out


# ---- Fork's integer arithmetic (R-int) ----

def saved_features(arch, active):
    return [m for m in (merged_index(arch, f) for f in active) if m is not None]


def accumulate(net, arch, active, weights='ftw', bias='ftb', width=None):
    width = width or arch.hidden
    acc = list(net[bias][:width])
    stride = len(net[bias]) if weights == 'sidew' else arch.hidden
    for f in saved_features(arch, active):
        row = net[weights][f * stride:f * stride + width]
        for i in range(width):
            acc[i] += row[i]
    for a in acc:
        assert -32768 <= a <= 32767, 'accumulator left int16: the net file breaks its bounds'
    return acc


def trunc_div(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def limit_eval(cp):
    return max(-(EVAL_LIMIT - 1), min(EVAL_LIMIT - 1, cp))


def r_int(arch, net, scale, board):
    stm, ntm, k = both_perspectives(arch, board)
    h = arch.hidden
    a_s, a_n = accumulate(net, arch, stm), accumulate(net, arch, ntm)
    v = [min(max(x, 0), QA) for x in a_s + a_n]
    if arch.name in ('s512', 'h512'):
        w = net['outw'][k * 2 * h:(k + 1) * 2 * h]
        total = sum(vi * (vi * wi) for vi, wi in zip(v, w))
        y = trunc_div(total, QA) + net['outb'][k]
        return limit_eval(trunc_div(y * scale, QA * QB))
    if arch.name == 'afs':
        half = h // 2
        x = [(v[p * h + j] * v[p * h + j + half] + 256) >> 9 for p in (0, 1) for j in range(half)]
        q1 = []
        for o in range(16):
            row = net['l1w'][(k * 16 + o) * h:(k * 16 + o + 1) * h]
            y1 = net['l1b'][k * 16 + o] + sum(xi * wi for xi, wi in zip(x, row))
            c1 = min(max(y1 >> 2, 0), 2032)
            q1.append((c1 * c1) >> 11)
        q2 = []
        for o in range(32):
            row = net['l2w'][(k * 32 + o) * 16:(k * 32 + o + 1) * 16]
            y2 = net['l2b'][k * 32 + o] + sum(qi * wi for qi, wi in zip(q1, row))
            c2 = min(max(y2 >> 13, 0), 2016)
            q2.append((c2 * c2) >> 11)
        y3 = net['l3b'][k] + sum(qi * wi for qi, wi in zip(q2, net['l3w'][k * 32:(k + 1) * 32]))
        return limit_eval((y3 * net['mult'][0]) >> 32)
    # xgr512
    s_s = accumulate(net, arch, stm, 'sidew', 'sideb', 3)
    s_n = accumulate(net, arch, ntm, 'sidew', 'sideb', 3)
    outs = []
    for e, lane in (('a', 1), ('b', 2)):
        total = sum(vi * (vi * wi) for vi, wi in zip(v, net[e + 'w']))
        outs.append(trunc_div(total, QA) + net[e + 'b'][0] + 128 * (s_s[lane] - s_n[lane]))
    out_a, out_b = outs
    g = min(max(s_s[0] + s_n[0], 0), QA)
    out = trunc_div(out_b * QA + g * (out_a - out_b), QA)
    return limit_eval(trunc_div(out * scale, QA * QB))
