# SPDX-License-Identifier: GPL-3.0-or-later

"""Fork's independent NNUE reference (DESIGN.md §5.3, deliverable 6),
written from the spec, not from Fork's C++ or convert.py.

- R-float: B0's float forward pass on bullet's optimiser_state/weights.bin.
- R-quant: bullet's quantization of those weights, redone here (each f32
  widened to f64, multiplied by the factor in f64, rounded half away from
  zero, range-checked; KB bullet-internals.md §1.2-1.4).
- R-int: Fork's integer arithmetic on Fork's net file (accumulate in int16
  range, clip to [0, QA], dot with the output weights in int32, add the
  bias, times S, divided by QA * QB truncating toward zero, clamped inside
  +-EvalLimit).
Features come from python-chess (bullet's 768-input convention:
384 * [piece colour != perspective] + 64 * type + square seen from the
perspective).

    reference.py legs --net NET --weights weights.bin --quantised quantised.bin
        --epd POSITIONS [--trainer parity-trainer.txt] [--out NET.parity]
    reference.py eval --net NET --epd POSITIONS     (R-int only, one line per position)
    reference.py features --rust FEATURES.txt         (the feature leg against fork-train features)
With --layout s512/h512/afs/xgr512.json (fitted maps included), every
command handles that bake-off architecture through models.py (DESIGN.md
§5.4); without it, B0.
    reference.py synthetic --out DIR [--seed N]      (random bullet-layout files, for tests)
"""
import argparse
import json
import math
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import models  # noqa: E402
import netformat  # noqa: E402

EVAL_LIMIT = 20000  # src/eval/eval_scale.hpp


def round_half_away(x):
    """Exact round half away from zero for a float64 (not numpy's half-to-even)."""
    t = math.trunc(x)
    frac = x - t  # exact in float64 for |x| < 2^52
    if abs(frac) >= 0.5:
        t += 1 if x > 0 else -1
    return int(t)


def to_f32(x):
    import struct
    return struct.unpack('<f', struct.pack('<f', x))[0]


def quantise_like_bullet(values, factor, kind):
    """bullet's .round().quantise::<T>(factor): f64 product, half away from
    zero, the full range of T or an error."""
    _, _, lo, hi = netformat.TYPES[kind]
    out = []
    for w in values:
        x = round_half_away(float(factor) * float(w))  # values are already f32-exact
        if not lo <= x <= hi:
            raise ValueError(f'{w} x {factor} = {x} leaves the {kind} range: bullet writes no file')
        out.append(x)
    return out


def features(board, perspective):
    out = []
    for sq, piece in board.piece_map().items():
        seen = sq if perspective == chess.WHITE else sq ^ 56
        out.append(384 * (piece.color != perspective) + 64 * (piece.piece_type - 1) + seen)
    return out


def r_float(weights, board, h=256):
    """The raw float output (side to move's view, before the sigmoid)."""
    l0w, l0b, l1w, l1b = (weights[k] for k in ('l0w', 'l0b', 'l1w', 'l1b'))
    out = l1b[0]
    for half, persp in enumerate((board.turn, not board.turn)):
        acc = list(l0b)
        for f in features(board, persp):
            col = l0w[f * h:(f + 1) * h]
            for i in range(h):
                acc[i] += col[i]
        w = l1w[half * h:(half + 1) * h]
        out += sum(min(max(a, 0.0), 1.0) * wi for a, wi in zip(acc, w))
    return out


def r_int(net, board, qa=255, qb=64, h=256):
    scale, l0w, l0b, l1w, l1b = net
    total = 0
    for half, persp in enumerate((board.turn, not board.turn)):
        acc = list(l0b)
        for f in features(board, persp):
            col = l0w[f * h:(f + 1) * h]
            for i in range(h):
                acc[i] += col[i]
        for i, a in enumerate(acc):
            assert -32768 <= a <= 32767, 'accumulator left int16: the net file breaks its bounds'
            total += min(max(a, 0), qa) * l1w[half * h + i]
    assert -2**31 <= total <= 2**31 - 1
    num = (total + l1b) * scale
    cp = abs(num) // (qa * qb) * (1 if num >= 0 else -1)  # truncation toward zero
    return max(-(EVAL_LIMIT - 1), min(EVAL_LIMIT - 1, cp))


def read_fens(path):
    return [l.strip() for l in open(path) if l.strip() and not l.startswith('#')]


def read_trainer(path):
    """parity-trainer.txt: 'FEN | raw output' per line (written by tools/train)."""
    out = {}
    for line in open(path):
        if '|' in line:
            fen, raw = line.rsplit('|', 1)
            out[fen.strip()] = float(raw)
    return out


def arch_of(desc):
    """The bake-off architecture a description names (tools/nnue/models.py)."""
    return models.Arch(desc['name'], desc.get('regions'), desc.get('table'))


def quantization_leg(desc, weights, quantised, net_bytes, scale, fails):
    """R-quant == bullet's quantised.bin == Fork's net file; returns the
    evaluators (R-int, R-float) of the network."""
    bq = netformat.read_quantised(quantised, desc)
    if desc['architecture'] == 1:
        net = netformat.read_net(net_bytes, desc)
        rq = {t['name']: quantise_like_bullet(weights[t['name']], t['factor'], t['type']) for t in desc['quantised']}
        expected = netformat.fork_payload(rq, desc)
        evaluators = (lambda board: r_int(net, board)), (lambda board: r_float(weights, board))
    else:
        arch = arch_of(desc)
        header = netformat.header_fields(net_bytes)
        if (header['version'], header['architecture'], header['inputs'], header['hidden']) != \
                (2, arch.id, arch.saved_inputs, arch.hidden):
            fails.append(f'net file header {header} does not match {arch.name}')
        net = models.unpack(arch, net_bytes[netformat.HEADER_BYTES:])
        saved = models.saved_tensors(arch, weights)
        rq = {name: values for name, (_, values) in saved.items()}
        expected = models.map_block(arch) + models.pack(models.fork_tensors(arch, saved, scale))
        evaluators = (lambda board: models.r_int(arch, net, scale, board)), \
            (lambda board: models.r_float(arch, weights, board))
    for name in bq:
        if rq[name] != bq[name]:
            diff = sum(1 for x, y in zip(rq[name], bq[name]) if x != y)
            fails.append(f'quantization leg: {name} differs from bullet in {diff} values')
    if expected != net_bytes[netformat.HEADER_BYTES:]:
        fails.append("quantization leg: Fork's net file differs from R-quant")
    return evaluators


def legs(a):
    desc = netformat.layout(a.layout)
    fails = []
    net_bytes = Path(a.net).read_bytes()
    scale = netformat.header_fields(net_bytes)['scale']
    weights = netformat.read_weights_bin(Path(a.weights).read_bytes())
    weights = {k: [to_f32(x) for x in v] for k, v in weights.items()}
    eval_int, eval_float = quantization_leg(desc, weights, Path(a.quantised).read_bytes(), net_bytes, scale, fails)

    trainer = read_trainer(a.trainer) if a.trainer else {}
    rows, losses = [], []
    trainer_diff = 0.0
    for fen in read_fens(a.epd):
        board = chess.Board(fen)
        ri = eval_int(board)
        rf = eval_float(board) * scale
        row = {'fen': fen, 'r_int': ri, 'r_float': round(rf, 4)}
        if fen in trainer:
            t = trainer[fen] * scale
            row['trainer'] = round(t, 4)
            trainer_diff = max(trainer_diff, abs(rf - t))
            if abs(rf - t) > 0.01:
                fails.append(f'R-float {rf:.4f} vs trainer {t:.4f} cp at {fen}')
        losses.append(abs(ri - rf))
        rows.append(row)
    losses.sort()
    stats = {'positions': len(rows), 'loss_max': round(losses[-1], 3),
             'loss_p99': round(losses[min(len(losses) - 1, int(0.99 * len(losses)))], 3),
             'loss_mean': round(sum(losses) / len(losses), 3), 'trainer_positions': len(trainer),
             'trainer_max_diff_cp': round(trainer_diff, 5)}
    if a.max_loss is not None and stats['loss_max'] > a.max_loss:
        fails.append(f"quantization loss {stats['loss_max']} cp above the threshold {a.max_loss}")
    if a.p99_loss is not None and stats['loss_p99'] > a.p99_loss:
        fails.append(f"quantization loss p99 {stats['loss_p99']} cp above the threshold {a.p99_loss}")
    if a.out:
        with open(a.out, 'w', newline='\n') as f:
            f.write(json.dumps({'net_checksum': f'{netformat.net_checksum(net_bytes[64:]):016x}', 'scale': scale,
                                **stats}) + '\n')
            for r in rows:
                f.write(f"{r['fen']} | {r['r_int']}\n")
    print(json.dumps(stats))
    for msg in fails:
        print('FAIL', msg, file=sys.stderr)
    return 1 if fails else 0


def synthetic_weights(seed):
    """Random f32 weights for B0 within bullet's clip, plus two exact
    rounding ties (KB bullet-internals.md §1.4)."""
    import random
    rng = random.Random(seed)
    w = {'l0w': [to_f32(rng.uniform(-0.12, 0.12)) for _ in range(256 * 768)],
         'l0b': [to_f32(rng.uniform(-0.5, 0.5)) for _ in range(256)],
         'l1w': [to_f32(rng.uniform(-1.0, 1.0)) for _ in range(512)],
         'l1b': [to_f32(rng.uniform(-0.2, 0.2))]}
    w['l0b'][0] = 0.5  # 0.5 x 255 = 127.5: an exact tie at QA
    w['l1w'][3] = 0.0390625  # 5/128 x 64 = 2.5: an exact tie at QB
    return w


def synthetic(a):
    desc = netformat.layout(a.layout)
    w = synthetic_weights(a.seed)
    q = {t['name']: quantise_like_bullet(w[t['name']], t['factor'], t['type']) for t in desc['quantised']}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'weights.bin').write_bytes(netformat.write_weights_bin(w))
    (out / 'quantised.bin').write_bytes(netformat.write_quantised(q, desc))
    return 0


def evaluate(a):
    desc = netformat.layout(a.layout)
    data = Path(a.net).read_bytes()
    if desc['architecture'] == 1:
        net = netformat.read_net(data, desc)
        fn = lambda board: r_int(net, board)  # noqa: E731
    else:
        arch = models.arch_from_net(desc['name'], data[netformat.HEADER_BYTES:])
        scale = netformat.header_fields(data)['scale']
        net = models.unpack(arch, data[netformat.HEADER_BYTES:])
        fn = lambda board: models.r_int(arch, net, scale, board)  # noqa: E731
    for fen in read_fens(a.epd):
        print(f'{fen} | {fn(chess.Board(fen))}')
    return 0


def board_from_pieces(text):
    """A board from the trainer's "piece:square ..." text (bulletformat's
    side-to-move frame: White to move, bit 3 marks the opponent's pieces,
    types 0-5 pawn to king)."""
    board = chess.Board(None)
    for item in text.split():
        code, sq = (int(x) for x in item.split(':'))
        board.set_piece_at(sq, chess.Piece((code & 7) + 1, chess.BLACK if code & 8 else chess.WHITE))
    board.turn = chess.WHITE
    return board


def feature_leg(a):
    """The feature leg: every line of `fork-train features` (FEN or pieces |
    stm inputs | ntm inputs | bucket) against this reference's features."""
    desc = netformat.layout(a.layout)
    arch = arch_of(desc) if desc['architecture'] != 1 else None
    n, bad = 0, []
    for line in open(a.rust, encoding='utf-8'):
        if '|' not in line:
            continue
        text, stm, ntm, k = (x.strip() for x in line.split('|'))
        board = chess.Board(text) if '/' in text else board_from_pieces(text)
        if arch is None:
            ours = (sorted(features(board, board.turn)), sorted(features(board, not board.turn)), 0)
        else:
            ours = models.both_perspectives(arch, board)
        theirs = ([int(x) for x in stm.split()], [int(x) for x in ntm.split()], int(k))
        n += 1
        if (list(ours[0]), list(ours[1]), ours[2]) != theirs:
            bad.append(text)
    print(f'feature leg: {n} positions, {len(bad)} differ')
    for text in bad[:10]:
        print('  differs:', text, file=sys.stderr)
    return 1 if bad or n == 0 else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    g = sub.add_parser('legs')
    g.add_argument('--net', required=True)
    g.add_argument('--weights', required=True)
    g.add_argument('--quantised', required=True)
    g.add_argument('--epd', required=True)
    g.add_argument('--trainer')
    g.add_argument('--out')
    g.add_argument('--max-loss', type=float)
    g.add_argument('--p99-loss', type=float)
    g.add_argument('--layout')
    y = sub.add_parser('synthetic')
    y.add_argument('--out', required=True)
    y.add_argument('--seed', type=int, default=1)
    y.add_argument('--layout')
    e = sub.add_parser('eval')
    e.add_argument('--net', required=True)
    e.add_argument('--epd', required=True)
    e.add_argument('--layout')
    f = sub.add_parser('features')
    f.add_argument('--rust', required=True, help='output of fork-train features')
    f.add_argument('--layout')
    a = ap.parse_args(argv)
    return {'legs': legs, 'eval': evaluate, 'synthetic': synthetic, 'features': feature_leg}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
