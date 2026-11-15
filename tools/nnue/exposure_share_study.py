# SPDX-License-Identifier: GPL-3.0-or-later
"""Idea 178's first falsifier (docs/ideas.md 178; docs/research/network-novelty-2026-11-14.md, idea 4): how much
of the network's residual the counts of the side to move's exposed pieces explain, against the opponent's.

**Positions and label** as idea 175's study (tools/nnue/state_rows_study.py on proto/i175-state-rows;
docs/research/idea175-screens.md): `fork-train dump` output, the training filter and the side-to-move-relative
view ("code:square ... | score | result", codes 0-5 own pawn ... king, 8-13 the opponent's), the label the
trainer's target at result weight 0, sigmoid(score / 92) of the file's copy score.

**The network's value.** An H512+PP net (architecture 9; r3kr1) evaluated with Fork's integer arithmetic:
models.py's features (regions, links; the factoriser merged away) and bucket, the sums, clipped squares and output
in numpy. The prediction is sigmoid(y / (QA * QB)), y the output before the scale; the evaluation in centipawns
trunc(y * S / (QA * QB)), clamped as the engine clamps. `--fork BIN` checks it against `BIN evalfens` on every
`--check-every`-th position (the board seen from the side to move, White to move).

**Exposure** (White is the side to move in the dump's view), two rules, each for each side:
- lower (x_lower's rule, L-lower): a non-king piece attacked by an enemy piece of a lower class (pawn < knight =
  bishop < rook < queen < king; pseudo-attacks on the occupancy), so never a pawn;
- exact (XGR's full rule, L-exact): lower, or attacked by any enemy piece and defended by none of its own.
Found set-wise from python-chess's attack masks and checked against models.py's square-by-square rules
(exposed_lower_squares, exposed_squares) on every `--check-every`-th position.

**Shares.** r = label - prediction. Count features per side and rule: (total) one-hot of the side's exposed count
(1, 2, 3 or more); (type) per piece type, the count at least 1 and at least 2; (type x bucket) per type, at least 1,
by output bucket. Ridge least squares with an unpenalised intercept, the ridge strength of LAMBDAS chosen by the
pooled held-out error; FOLDS folds of BLOCK consecutive positions (whole games but at the block edges), each fold
predicted from the others. A share = (held-out SSE without the features - with them) / held-out sum of squares of
r about the training folds' mean. For each design: S_mover and S_opp (each side's features alone), S_both, and
the mover's part S_mover / (S_mover + S_opp) (the kill line: under one half), with a jackknife over the folds; also
the increments (S_both - S_opp and S_both - S_mover), and the same over a control base (each side's piece counts
by type and the output bucket one-hot), which takes out what the counts say only through material and phase.
`--inject SIDE SIZE` adds SIZE (a share of r's variance) worth of a known effect, a times the side's total exposed
count under the lower rule, to r first: the check that the method finds a known effect on the right side (a
negative SHARE injects -a: the two signs' shares average the base share plus SHARE when the effect is linear).

    exposure_share_study.py DUMP --net NET.fnet --out OUT.json [--fork BIN] [--check-every N] [--limit N]
                            [--cache CACHE.npz] [--inject mover|opp SHARE]

Needs numpy (and python-chess).
"""
import argparse
import ctypes
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

for var in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(var, '3')

import chess  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import models  # noqa: E402
import netformat  # noqa: E402

QA, QB = 255, 64
EVAL_LIMIT = 20000
TRAIN_SCALE = 92.0
BLOCK = 2000
FOLDS = 8
LAMBDAS = (1e-3, 1.0, 10.0, 100.0, 1e3, 1e4, 1e5)
RULES = ('lower', 'exact')
SIDES = ('mover', 'opp')
TYPES = ('P', 'N', 'B', 'R', 'Q')


def read_dump(path, limit):
    out, scores = [], []
    with open(path, encoding='ascii') as fh:
        for line in fh:
            left, score, _ = line.split('|')
            out.append(bytes(int(x) for t in left.split() for x in t.split(':')))
            scores.append(int(score))
            if limit and len(out) >= limit:
                break
    return out, np.array(scores, dtype=np.float64)


def board_of(packed):
    b = chess.Board(None)
    b.set_piece_map({sq: chess.Piece((code & 7) + 1, chess.WHITE if code < 8 else chess.BLACK)
                     for code, sq in zip(packed[0::2], packed[1::2])})
    b.turn = chess.WHITE
    return b


def bits(mask):
    return chess.scan_forward(mask)


def exposure(board):
    """Per rule and side (White the mover), the exposed set (a bitboard)."""
    upto = {}
    for c in (chess.WHITE, chess.BLACK):
        pawns = minors = rooks = queens = 0
        for sq in bits(board.pieces_mask(chess.PAWN, c)):
            pawns |= chess.BB_PAWN_ATTACKS[c][sq]
        for sq in bits(board.pieces_mask(chess.KNIGHT, c) | board.pieces_mask(chess.BISHOP, c)):
            minors |= board.attacks_mask(sq)
        for sq in bits(board.pieces_mask(chess.ROOK, c)):
            rooks |= board.attacks_mask(sq)
        for sq in bits(board.pieces_mask(chess.QUEEN, c)):
            queens |= board.attacks_mask(sq)
        u1 = pawns | minors
        u2 = u1 | rooks
        u3 = u2 | queens
        u4 = u3 | chess.BB_KING_ATTACKS[board.king(c)]
        upto[c] = (pawns, u1, u2, u3, u4)
    out = {}
    for c in (chess.WHITE, chess.BLACK):
        e = upto[not c]
        lower = ((board.pieces_mask(chess.KNIGHT, c) | board.pieces_mask(chess.BISHOP, c)) & e[0]) | \
                (board.pieces_mask(chess.ROOK, c) & e[1]) | (board.pieces_mask(chess.QUEEN, c) & e[2])
        nonking = board.occupied_co[c] & ~board.kings
        exact = lower | (nonking & e[4] & ~upto[c][4])
        out[('lower', c)] = lower
        out[('exact', c)] = exact
    return out


def type_counts(board, mask, c):
    return [chess.popcount(mask & board.pieces_mask(t, c)) for t in range(chess.PAWN, chess.KING)]


def load_net(path):
    data = Path(path).read_bytes()
    head = netformat.header_fields(data)
    if head['architecture'] != 9:
        sys.exit('an architecture 9 (H512+PP) net is expected')
    payload = data[netformat.HEADER_BYTES:]
    arch = models.arch_from_net('h512pp', payload)
    net = models.unpack(arch, payload)
    ftw = np.frombuffer(bytes(net['ftw']), dtype='<i2').reshape(-1, 512)
    ftb = np.array(net['ftb'], dtype=np.int32)
    outw = np.array(net['outw'], dtype=np.int64).reshape(8, 2, 512)
    outb = np.array(net['outb'], dtype=np.int64)
    return arch, ftw, ftb, outw, outb, head['scale']


def trunc_div(a, b):
    return np.sign(a) * (np.abs(a) // b)


def first_pass(positions, netinfo, check_every, chunk=2048):
    """y, bucket, per (rule, side, type) exposed counts, per (side, type) piece counts, and the oracle check."""
    arch, ftw, ftb, outw, outb, scale = netinfo
    n = len(positions)
    ys = np.zeros(n, dtype=np.int64)
    buckets = np.zeros(n, dtype=np.int64)
    exposed = np.zeros((n, 2, 2, 5), dtype=np.int8)
    material = np.zeros((n, 2, 5), dtype=np.int8)
    oracle = {'checked': 0, 'lower_mismatch': 0, 'exact_mismatch': 0}
    for c0 in range(0, n, chunk):
        part = positions[c0:c0 + chunk]
        rows, starts = [], []
        for i, packed in enumerate(part):
            g = c0 + i
            b = board_of(packed)
            stm, ntm, k = models.both_perspectives(arch, b)
            starts.append(len(rows))
            rows.extend(models.saved_features(arch, stm))
            starts.append(len(rows))
            rows.extend(models.saved_features(arch, ntm))
            buckets[g] = k
            ex = exposure(b)
            for ri, rule in enumerate(RULES):
                for si, c in enumerate((chess.WHITE, chess.BLACK)):
                    exposed[g, ri, si] = type_counts(b, ex[(rule, c)], c)
            for si, c in enumerate((chess.WHITE, chess.BLACK)):
                material[g, si] = [chess.popcount(b.pieces_mask(t, c)) for t in range(chess.PAWN, chess.KING)]
            if check_every and g % check_every == 0:
                oracle['checked'] += 1
                lo = chess.SquareSet(ex[('lower', chess.WHITE)] | ex[('lower', chess.BLACK)])
                fu = chess.SquareSet(ex[('exact', chess.WHITE)] | ex[('exact', chess.BLACK)])
                oracle['lower_mismatch'] += set(lo) != models.exposed_lower_squares(b)
                oracle['exact_mismatch'] += set(fu) != models.exposed_squares(b)
        sums = np.add.reduceat(ftw[np.array(rows)].astype(np.int32), np.array(starts), axis=0) + ftb
        assert sums.min() >= -32768 and sums.max() <= 32767
        v = np.clip(sums, 0, QA).astype(np.int64).reshape(len(part), 2, 512)
        k = buckets[c0:c0 + len(part)]
        total = np.einsum('mhj,mhj->m', v, v * outw[k])
        ys[c0:c0 + len(part)] = trunc_div(total, QA) + outb[k]
    cp = np.clip(trunc_div(ys * scale, QA * QB), -(EVAL_LIMIT - 1), EVAL_LIMIT - 1)
    return ys, cp, buckets, exposed, material, oracle


def check_evalfens(fork, positions, cp, every):
    idx = list(range(0, len(positions), every))
    fens = ''.join(board_of(positions[i]).fen() + '\n' for i in idx)
    out = subprocess.run([fork, 'evalfens'], input=fens, capture_output=True, text=True, check=True).stdout.split()
    got = np.array([int(x) for x in out])
    return len(idx), int((got != cp[idx]).sum())


# ---- designs ----

def side_block(exposed, buckets, rule, side, kind):
    """The count features of one side under one rule (float32 columns)."""
    e = exposed[:, RULES.index(rule), SIDES.index(side)].astype(np.int32)  # (n, 5)
    types = range(5) if rule == 'exact' else range(1, 5)                  # the lower rule never exposes a pawn
    if kind == 'total':
        t = e.sum(axis=1)
        return np.stack([t == 1, t == 2, t >= 3], axis=1).astype(np.float32)
    if kind == 'type':
        return np.stack([e[:, t] >= m for t in types for m in (1, 2)], axis=1).astype(np.float32)
    if kind == 'type_bucket':
        return np.stack([(e[:, t] >= 1) & (buckets == k) for t in types for k in range(8)],
                        axis=1).astype(np.float32)
    raise ValueError(kind)


def base_block(material, buckets):
    m = material.reshape(len(material), 10).astype(np.float32)
    oh = np.stack([buckets == k for k in range(8)], axis=1).astype(np.float32)
    return np.concatenate([m, oh], axis=1)


def grams(X, r, fold):
    """Per fold: X^T X and X^T r with an intercept column first, and r's count, sum and sum of squares."""
    X1 = np.concatenate([np.ones((len(X), 1), dtype=np.float64), X.astype(np.float64)], axis=1)
    p = X1.shape[1]
    G = np.zeros((FOLDS, p, p))
    B = np.zeros((FOLDS, p))
    S = np.zeros((FOLDS, 3))
    for f in range(FOLDS):
        sel = fold == f
        Xf, rf = X1[sel], r[sel]
        G[f] = Xf.T @ Xf
        B[f] = Xf.T @ rf
        S[f] = (sel.sum(), rf.sum(), (rf ** 2).sum())
    return G, B, S


def heldout(G, B, S, cols, lam):
    """Per fold: held-out SSE of the ridge fit on columns `cols` (intercept 0 always in, unpenalised)."""
    idx = np.array([0] + [c + 1 for c in cols], dtype=np.int64)
    pen = np.full(len(idx), lam)
    pen[0] = 0.0
    out = np.zeros(FOLDS)
    for t in range(FOLDS):
        train = [f for f in range(FOLDS) if f != t]
        Gt, Bt = G[train].sum(axis=0)[np.ix_(idx, idx)], B[train].sum(axis=0)[idx]
        beta = np.linalg.solve(Gt + np.diag(pen), Bt)
        out[t] = S[t, 2] - 2 * beta @ B[t, idx] + beta @ G[t][np.ix_(idx, idx)] @ beta
    return out


def sst_folds(S):
    out = np.zeros(FOLDS)
    for t in range(FOLDS):
        train = [f for f in range(FOLDS) if f != t]
        mu = S[train, 1].sum() / S[train, 0].sum()
        out[t] = S[t, 2] - 2 * mu * S[t, 1] + mu * mu * S[t, 0]
    return out


def best_sse(G, B, S, cols):
    if not cols:
        return heldout(G, B, S, [], 0.0), 0.0
    best = None
    for lam in LAMBDAS:
        sse = heldout(G, B, S, cols, lam)
        if best is None or sse.sum() < best[0].sum():
            best = (sse, lam)
    return best


def jackknife_ratio(num_f, den_f):
    """The ratio of pooled sums and its jackknife standard error over the folds."""
    full = num_f.sum() / den_f.sum() if den_f.sum() != 0 else float('nan')
    loo = np.array([(num_f.sum() - num_f[f]) / (den_f.sum() - den_f[f]) for f in range(FOLDS)])
    se = math.sqrt((FOLDS - 1) / FOLDS * ((loo - loo.mean()) ** 2).sum())
    return float(full), float(se)


def share_table(r, fold, exposed, material, buckets, rule, kind, controls):
    mv = side_block(exposed, buckets, rule, 'mover', kind)
    op = side_block(exposed, buckets, rule, 'opp', kind)
    base = base_block(material, buckets) if controls else np.zeros((len(r), 0), dtype=np.float32)
    X = np.concatenate([base, mv, op], axis=1)
    G, B, S = grams(X, r, fold)
    sst = sst_folds(S)
    nb, nm, no = base.shape[1], mv.shape[1], op.shape[1]
    cb = list(range(nb))
    cm = list(range(nb, nb + nm))
    co = list(range(nb + nm, nb + nm + no))
    sse0, lam0 = best_sse(G, B, S, cb)
    sse_m, lam_m = best_sse(G, B, S, cb + cm)
    sse_o, lam_o = best_sse(G, B, S, cb + co)
    sse_b, lam_b = best_sse(G, B, S, cb + cm + co)
    d_m, d_o, d_b = sse0 - sse_m, sse0 - sse_o, sse0 - sse_b
    inc_m, inc_o = sse_o - sse_b, sse_m - sse_b

    def pct(d):
        return {'share_pct': float(100 * d.sum() / sst.sum()),
                'se_pct': float(100 * (d / sst).std(ddof=1) / math.sqrt(FOLDS))}

    part, part_se = jackknife_ratio(d_m, d_m + d_o)
    ipart, ipart_se = jackknife_ratio(inc_m, inc_m + inc_o)
    return {
        'rule': rule, 'design': kind, 'controls': controls, 'columns': {'mover': nm, 'opp': no, 'base': nb},
        'lambda': {'base': lam0, 'mover': lam_m, 'opp': lam_o, 'both': lam_b},
        'base_r2_heldout_pct': float(100 * (1 - sse0.sum() / sst.sum())),
        'mover': pct(d_m), 'opp': pct(d_o), 'both': pct(d_b),
        'mover_given_opp': pct(inc_m), 'opp_given_mover': pct(inc_o),
        'mover_part': part, 'mover_part_se': part_se,
        'mover_part_incremental': ipart, 'mover_part_incremental_se': ipart_se,
    }


def describe(r, exposed, rule):
    """Frequencies and the mean residual by each side's total exposed count (0, 1, 2, 3+)."""
    out = {}
    for si, side in enumerate(SIDES):
        e = exposed[:, RULES.index(rule), si].astype(np.int32)
        t = np.minimum(e.sum(axis=1), 3)
        out[side] = {
            'mean_count': float(e.sum(axis=1).mean()),
            'share_with_any': float((t > 0).mean()),
            'by_type_mean': {TYPES[k]: float(e[:, k].mean()) for k in range(5)},
            'mean_residual_x1000_by_total': {str(g): (float(1000 * r[t == g].mean()) if (t == g).any() else None)
                                             for g in range(4)},
            'positions_by_total': {str(g): int((t == g).sum()) for g in range(4)},
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('dump')
    ap.add_argument('--net', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--fork')
    ap.add_argument('--check-every', type=int, default=50)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--cache')
    ap.add_argument('--inject', nargs=2, metavar=('SIDE', 'SHARE'))
    args = ap.parse_args(argv)
    if sys.platform == 'win32':  # below normal: the machine is shared with data generation
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    t0 = time.time()
    positions, scores = read_dump(args.dump, args.limit)
    timing = {}
    info = {'dump': os.path.basename(args.dump), 'net': os.path.basename(args.net), 'positions': len(positions)}
    if args.cache and os.path.exists(args.cache):
        z = np.load(args.cache)
        ys, cp, buckets, exposed, material = z['ys'], z['cp'], z['buckets'], z['exposed'], z['material']
        assert len(ys) == len(positions)
        info['oracle'] = 'cached pass (see the first run)'
    else:
        netinfo = load_net(args.net)
        ys, cp, buckets, exposed, material, oracle = first_pass(positions, netinfo, args.check_every)
        info['oracle'] = oracle
        timing['first_pass'] = round(time.time() - t0, 1)
        if args.cache:
            np.savez(args.cache, ys=ys, cp=cp, buckets=buckets, exposed=exposed, material=material)
        if args.fork:
            checked, bad = check_evalfens(args.fork, positions, cp, args.check_every)
            info['evalfens'] = {'checked': checked, 'mismatches': bad}
            print(f'evalfens check: {checked} positions, {bad} mismatches', flush=True)
    label = 1.0 / (1.0 + np.exp(-scores / TRAIN_SCALE))
    pred = 1.0 / (1.0 + np.exp(-ys.astype(np.float64) / (QA * QB)))
    r = label - pred
    info['residual'] = {'mean': float(r.mean()), 'var': float(r.var()), 'label_var': float(label.var())}
    if args.inject:
        side, share = args.inject[0], float(args.inject[1])
        cnt = exposed[:, RULES.index('lower'), SIDES.index(side)].astype(np.float64).sum(axis=1)
        a = math.copysign(math.sqrt(abs(share) * r.var() / cnt.var()), share)  # a negative SHARE: a negative a
        r = r + a * cnt
        info['inject'] = {'side': side, 'rule': 'lower', 'share_of_var': share, 'coefficient': a,
                          'injected_var_over_new_var_pct': float(100 * (a * a * cnt.var()) / r.var())}
    fold = (np.arange(len(r)) // BLOCK) % FOLDS
    t1 = time.time()
    tables = []
    for rule in RULES:
        for kind in ('total', 'type', 'type_bucket'):
            for controls in (False, True):
                row = share_table(r, fold, exposed, material, buckets, rule, kind, controls)
                tables.append(row)
                print(f"{rule:5s} {kind:11s} {'ctrl' if controls else 'none'}  mover {row['mover']['share_pct']:7.4f}% "
                      f"+- {row['mover']['se_pct']:.4f}  opp {row['opp']['share_pct']:7.4f}% +- {row['opp']['se_pct']:.4f}  "
                      f"both {row['both']['share_pct']:7.4f}%  mover part {row['mover_part']:.3f} +- "
                      f"{row['mover_part_se']:.3f}  (incremental {row['mover_part_incremental']:.3f} +- "
                      f"{row['mover_part_incremental_se']:.3f})", flush=True)
    timing['shares'] = round(time.time() - t1, 1)
    timing['total'] = round(time.time() - t0, 1)
    out = {**info, 'describe': {rule: describe(r, exposed, rule) for rule in RULES}, 'tables': tables,
           'seconds': timing}
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ('positions', 'residual', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
