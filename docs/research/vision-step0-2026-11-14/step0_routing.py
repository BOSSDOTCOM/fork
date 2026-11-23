# SPDX-License-Identifier: GPL-3.0-or-later
"""Vision step 0 (ideas.md 185), part (d): r3kr1's output heads refit on its frozen body under other routings.

**The body** is r3kr1's first layer, frozen: each position's 1,024 clipped hidden values v (step0_eval.py
--hidden; the side to move's 512 then the other side's), so a head sees x = (v / QA)^2 and outputs
z = x . u + c, Fork's integer formula in floats (u = w / QB, c = b / (QA * QB); its truncations left out).
**The loss** is the trainer's (tools/train/src/main.rs: output.sigmoid().squared_error(target)), squared error
between sigmoid(z) and the target sigmoid(score / 92) (result weight 0, as retrain 8c trained r3kr1's recipe and as
idea 175's study used), summed over the training positions, plus a ridge term lam * |theta_c - theta0_c|^2 per head
toward a start (r3kr1's own head for the cell's phase bucket; for the progress routing, r3kr1's heads averaged by the
cell's bucket mix). lam is chosen per routing from LAMBDAS by the pooled held-out loss.
**The fit** minimises that objective exactly, by Newton steps with a Gauss-Newton matrix (sum of
sigmoid'(z)^2 x x^T per head, pooled over the folds, times 7/8; first at the start heads, then recomputed at the
current fit at iterations 3, 8, 16, 32 and 64) and step halving per
head when a step raises the objective; it stops when the total objective falls by less than 1e-9 of itself in a pass (each head's held-out loss is
taken at its last accepted fit).
(Idea 82's probe, tools/measure/head_probes.py heads on tools/probes-1111, minimised the same squared error by
full-batch Adam with early stopping on a 10% hold-out; this is the same objective with an exact optimum and ridge
instead of early stopping.)
**Folds**: blocks of 2,000 consecutive positions, block b in fold b mod 8 (idea 175's); each fold's loss is that of
the heads fitted on the other seven. The interval of a routing's difference to the phase control is +- the standard
error of the 8 per-fold differences of mean loss (and 2 x that is lens 1's kill rule).

Routings (a cell per position; one head per cell):
- phase: the output bucket (r3kr1's 8 phase octiles): the control, which must reproduce r3kr1's held-out loss;
- progress: octiles of a learned linear progress score (ridge least squares of ply / final ply on the 768
  mover-relative piece-square cells), fitted, with its octile boundaries, on the other position set (`fit-progress`);
- phaseprog (an extra, not in the order): phase x the progress score above or below its bucket's median (the
  medians fitted on the other set): progress within material phase, 16;
- wings: phase x the kings' wings (files a-d against e-h; same or opposite): 16;
- column: phase x one hidden value's activity (v_j > 0; j of the 1,024), the column chosen on the other set
  (`rank-columns`: every column pre-ranked by the residual SSE a per-(bucket, bit) linear correction a + b z0
  removes; then `select-column`: the top 8 refit on that set, the best held-out loss kept): 16.

    step0_routing.py fit-progress FEAT PLIES --eval EVAL --out PROG.npz
    step0_routing.py rank-columns FEAT EVAL HIDDEN --out RANK.json
    step0_routing.py select-column FEAT EVAL HIDDEN --net NET --rank RANK.json --out SEL.json [--top 8]
    step0_routing.py refit FEAT EVAL HIDDEN --net NET --progress PROG.npz --column J --out OUT.json
"""
import argparse
import ctypes
import json
import math
import os
import sys
import time
from pathlib import Path

for var in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(var, '3')

import numpy as np  # noqa: E402
import scipy.linalg as sla  # noqa: E402
import scipy.sparse as sp  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import step0_common as sc  # noqa: E402

sys.path.insert(0, str(sc.REPO / 'tools' / 'nnue'))
import netformat  # noqa: E402

LAMBDAS = (0.1, 1.0, 10.0, 100.0, 1000.0)
CHUNK = 8192
MAX_ITER = 80
REFRESH = (3, 8, 16, 32, 64)  # iterations at which the Gauss-Newton matrix is recomputed at the current fit


def below_normal():
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def heads_of(net_path):
    """r3kr1's 8 heads in the float form: theta[k] = (w / QB for the 1,024 inputs, b / (QA * QB))."""
    data = Path(net_path).read_bytes()
    head = netformat.header_fields(data)
    assert head['architecture'] == 9
    payload = data[netformat.HEADER_BYTES:]
    sys.path.insert(0, str(sc.REPO / 'tools' / 'nnue'))
    import models
    arch = models.arch_from_net('h512pp', payload)
    net = models.unpack(arch, payload)
    w = np.array(net['outw'], dtype=np.float64).reshape(8, 1024) / sc.QB
    b = np.array(net['outb'], dtype=np.float64) / (sc.QA * sc.QB)
    return np.concatenate([w, b[:, None]], axis=1)


def chunks(hidden, n):
    for c0 in range(0, n, CHUNK):
        c1 = min(n, c0 + CHUNK)
        x = hidden[c0:c1].astype(np.float32) * (1.0 / sc.QA)
        x *= x
        yield c0, c1, np.concatenate([x, np.ones((c1 - c0, 1), dtype=np.float32)], axis=1)


def load(feat_path, eval_path, hidden_path):
    feat = np.load(feat_path)
    n = int(feat['n'][0])
    ev = np.load(eval_path)
    hidden = np.memmap(hidden_path, dtype=np.uint8, mode='r', shape=(n, 1024))
    return feat, ev, hidden, n


def fit(hidden, n, target, cell, K, theta0, fold, lambdas=LAMBDAS, log=None):
    """The CV refit: per (fold t, lam) heads for every cell. Returns per lam the held-out SSE and count per fold."""
    M = sc.FOLDS * len(lambdas)
    t0 = time.time()
    def gauss_newton(lin):
        """Per cell: the eigendecomposition of sum sigmoid'(z)^2 x x^T at heads `lin` (K x 1025), times 7/8."""
        H = np.zeros((K, 1025, 1025))
        for c0, c1, X in chunks(hidden, n):
            cc = cell[c0:c1]
            z = np.einsum('ij,ij->i', X.astype(np.float64), lin[cc])
            s = sigmoid(z)
            w = (s * (1 - s)) ** 2
            for c in np.unique(cc):
                sel = cc == c
                Xc = X[sel]
                H[c] += (Xc.T @ (Xc * w[sel, None].astype(np.float32))).astype(np.float64)
        ev = np.zeros((K, 1025))
        for c in range(K):  # one eigendecomposition per head serves every lam: (7/8 H + lam I)^-1 = Q diag Q^T
            ev[c], H[c] = sla.eigh(H[c], overwrite_a=True, check_finite=False)
        return ev.clip(min=0.0) * (7.0 / 8.0), H

    evals, Q = gauss_newton(theta0)
    if log:
        log(f'  Gauss-Newton matrices {time.time() - t0:.0f} s')
    lam_of = np.repeat(np.array(lambdas), sc.FOLDS)          # model m = li * FOLDS + t
    fold_of = np.tile(np.arange(sc.FOLDS), len(lambdas))
    theta = np.repeat(theta0[None], M, axis=0)               # M x K x 1025
    prev = theta.copy()
    step = np.zeros_like(theta)
    alpha = np.ones((M, K))
    prev_obj = np.full((M, K), np.inf)
    best_held = np.zeros((M, K))   # held-out SSE of model m's fold in head c, at the head's last accepted fit
    for it in range(MAX_ITER):
        obj = np.zeros((M, K))
        grad = np.zeros((M, K, 1025))
        held = np.zeros((M, K))
        for c0, c1, X in chunks(hidden, n):
            cc, ff, yy = cell[c0:c1], fold[c0:c1], target[c0:c1]
            for c in np.unique(cc):
                sel = np.nonzero(cc == c)[0]
                Xc = X[sel]
                Z = (Xc @ theta[:, c, :].T.astype(np.float32)).astype(np.float64)   # m_c x M
                S = sigmoid(Z)
                E = S - yy[sel, None]
                train = ff[sel, None] != fold_of[None, :]
                obj[:, c] += (E * E * train).sum(axis=0)
                held[:, c] += (E * E * ~train).sum(axis=0)
                D = (2 * E * S * (1 - S) * train).astype(np.float32)
                grad[:, c, :] += (Xc.T @ D).T.astype(np.float64)
        reg = (lam_of[:, None] * ((theta - theta0[None]) ** 2).sum(axis=2))
        obj += reg
        grad += 2 * lam_of[:, None, None] * (theta - theta0[None])
        worse = obj > prev_obj * (1 + 1e-10)  # a rise beyond rounding
        best_held = np.where(worse, best_held, held)
        total_prev = np.where(np.isfinite(prev_obj), prev_obj, obj).sum()
        gain = (np.where(np.isfinite(prev_obj), prev_obj, obj) - obj).clip(min=0).sum()
        if log:
            log(f'  iter {it}: objective {obj.sum():.6f}, rejected heads {int(worse.sum())}, '
                f'{time.time() - t0:.0f} s')
        if it > 0 and gain < 1e-9 * total_prev:
            break
        if it in REFRESH:  # re-linearize at the current fit of fold 0, middle lam
            del Q
            evals, Q = gauss_newton(theta[(len(lambdas) // 2) * sc.FOLDS].copy())
            if log:
                log(f'  Gauss-Newton matrices refreshed, {time.time() - t0:.0f} s')
        for c in range(K):
            coeff = (grad[:, c, :] @ Q[c]) / (evals[c][None, :] + lam_of[:, None])
            newstep = -(coeff @ Q[c].T) / 2
            for m in range(M):
                if worse[m, c]:
                    alpha[m, c] *= 0.5
                    theta[m, c] = prev[m, c] + alpha[m, c] * step[m, c]
                else:
                    prev_obj[m, c] = obj[m, c]
                    prev[m, c] = theta[m, c]
                    step[m, c] = newstep[m]
                    alpha[m, c] = 1.0
                    theta[m, c] = prev[m, c] + step[m, c]
    else:
        if log:
            log('  stopped at MAX_ITER')
    counts = np.array([(fold == t).sum() for t in range(sc.FOLDS)])
    out = {}
    for li, lam in enumerate(lambdas):
        rows = [li * sc.FOLDS + t for t in range(sc.FOLDS)]
        out[lam] = np.array([best_held[rows[t]].sum() for t in range(sc.FOLDS)])
    return out, counts, {'iterations': it + 1, 'seconds': round(time.time() - t0)}


def summarize(sse_by_lam, counts):
    lam = min(sse_by_lam, key=lambda k: sse_by_lam[k].sum())
    sse = sse_by_lam[lam]
    return {'lambda': lam, 'loss': float(sse.sum() / counts.sum()), 'fold_loss': (sse / counts).tolist(),
            'by_lambda': {str(k): float(v.sum() / counts.sum()) for k, v in sse_by_lam.items()}}


def progress_score(feat, model):
    n = int(feat['n'][0])
    rows = np.repeat(np.arange(n), np.diff(feat['base_off']))
    X = sp.csr_matrix((np.ones(len(rows)), (rows, feat['base_flat'].astype(np.int64))), shape=(n, 768))
    return X @ model['w'] + model['b'][0]


def cmd_fit_progress(a):
    feat = np.load(a.feat)
    pl = np.load(a.plies)
    n = int(feat['n'][0])
    f = pl['ply'] / pl['final']
    rows = np.repeat(np.arange(n), np.diff(feat['base_off']))
    X = sp.csr_matrix((np.ones(len(rows)), (rows, feat['base_flat'].astype(np.int64))), shape=(n, 768))
    X1 = sp.hstack([X, np.ones((n, 1))]).tocsr()
    G = (X1.T @ X1).toarray() + 1.0 * np.diag(np.r_[np.ones(768), 0.0])
    beta = np.linalg.solve(G, X1.T @ f)
    score = X1 @ beta
    bounds = np.quantile(score, np.arange(1, 8) / 8)
    r2 = 1 - ((f - score) ** 2).sum() / ((f - f.mean()) ** 2).sum()
    k = np.load(a.eval)['buckets'].astype(np.int64)
    medians = np.array([np.median(score[k == b]) for b in range(8)])
    np.savez(a.out, w=beta[:768], b=beta[768:], bounds=bounds, medians=medians)
    print(json.dumps({'positions': n, 'r2_in_sample': float(r2), 'bounds': bounds.tolist(),
                      'bucket_medians': medians.tolist()}))


def cmd_rank_columns(a):
    feat, ev, hidden, n = load(a.feat, a.eval, a.hidden)
    target = sc.label_of(feat['scores'])
    z0 = ev['ys'].astype(np.float64) / (sc.QA * sc.QB)
    e = target - sigmoid(z0)
    k = ev['buckets'].astype(np.int64)
    stats1 = np.zeros((8, 1024, 6))
    tot = np.zeros((8, 6))
    for c0 in range(0, n, CHUNK):
        c1 = min(n, c0 + CHUNK)
        bit = (hidden[c0:c1] > 0).astype(np.float64)
        q = np.stack([np.ones(c1 - c0), e[c0:c1], z0[c0:c1], z0[c0:c1] ** 2, z0[c0:c1] * e[c0:c1],
                      e[c0:c1] ** 2], axis=1)
        for b in range(8):
            sel = k[c0:c1] == b
            stats1[b] += bit[sel].T @ q[sel]
            tot[b] += q[sel].sum(axis=0)

    def sse(s):
        nn, se, sz, szz, sze, see = (s[..., i] for i in range(6))
        det = nn * szz - sz * sz
        ok = det > 1e-9
        det = np.where(ok, det, 1.0)
        a0 = (szz * se - sz * sze) / det
        a1 = (nn * sze - sz * se) / det
        fitted = np.where(ok, a0 * se + a1 * sze, np.where(nn > 0, se * se / np.maximum(nn, 1), 0.0))
        return see - fitted
    pooled = sse(tot)[:, None]
    gain = (pooled - sse(stats1) - sse(tot[:, None, :] - stats1)).sum(axis=0)
    order = np.argsort(-gain)
    active = np.array([(stats1[:, j, 0].sum()) / n for j in range(1024)])
    out = {'positions': n, 'ranked': [{'column': int(j), 'gain': float(gain[j]), 'active_share': float(active[j])}
                                      for j in order[:64]]}
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out['ranked'][:10]))


def cells_for(routing, feat, ev, hidden, n, progress=None, column=None):
    k = ev['buckets'].astype(np.int64)
    if routing == 'phase':
        return k, 8
    if routing == 'wings':
        kings = feat['kings'].astype(np.int64)
        opp = ((kings[:, 0] % 8) >= 4) != ((kings[:, 1] % 8) >= 4)
        return k * 2 + opp.astype(np.int64), 16
    if routing == 'column':
        bit = np.zeros(n, dtype=np.int64)
        for c0 in range(0, n, CHUNK):
            c1 = min(n, c0 + CHUNK)
            bit[c0:c1] = hidden[c0:c1, column] > 0
        return k * 2 + bit, 16
    if routing == 'progress':
        s = progress_score(feat, progress)
        return np.searchsorted(progress['bounds'], s), 8
    if routing == 'phaseprog':
        s = progress_score(feat, progress)
        return k * 2 + (s > progress['medians'][k]).astype(np.int64), 16
    raise ValueError(routing)


def start_heads(routing, cell, K, k, heads):
    if routing == 'phase':
        return heads.copy()
    if routing in ('wings', 'column', 'phaseprog'):
        return heads[np.arange(K) // 2]
    mix = np.zeros((K, 8))
    np.add.at(mix, (cell, k), 1.0)
    mix /= np.maximum(mix.sum(axis=1, keepdims=True), 1)
    return mix @ heads


def logger(path):
    def log(msg):
        print(msg, flush=True)
        with open(path, 'a') as fh:
            fh.write(msg + '\n')
    return log


def cmd_select_column(a):
    feat, ev, hidden, n = load(a.feat, a.eval, a.hidden)
    heads = heads_of(a.net)
    target = sc.label_of(feat['scores'])
    fold = sc.folds_of(n)
    k = ev['buckets'].astype(np.int64)
    rank = json.loads(Path(a.rank).read_text())['ranked'][:a.top]
    log = logger(a.out + '.log')
    cell, K = cells_for('phase', feat, ev, hidden, n)
    res, counts, info = fit(hidden, n, target, cell, K, heads, fold, lambdas=(a.lam,), log=log)
    control = summarize(res, counts)
    out = {'positions': n, 'lambda': a.lam, 'phase': control, 'candidates': []}
    log(f"phase control loss {control['loss']:.8f}")
    for r in rank:
        j = r['column']
        cell, K = cells_for('column', feat, ev, hidden, n, column=j)
        res, counts, info = fit(hidden, n, target, cell, K, start_heads('column', cell, K, k, heads), fold,
                                lambdas=(a.lam,), log=log)
        s = summarize(res, counts)
        d = np.array(s['fold_loss']) - np.array(control['fold_loss'])
        out['candidates'].append({'column': j, 'loss': s['loss'], 'diff': float(d.mean()),
                                  'diff_se': float(d.std(ddof=1) / math.sqrt(sc.FOLDS)), **info})
        log(f"column {j}: loss {s['loss']:.8f}, diff {d.mean():+.3e} +- {d.std(ddof=1) / math.sqrt(8):.1e}")
        Path(a.out).write_text(json.dumps(out, indent=1))
    best = min(out['candidates'], key=lambda c: c['loss'])
    out['chosen'] = best['column']
    Path(a.out).write_text(json.dumps(out, indent=1))


def cmd_refit(a):
    feat, ev, hidden, n = load(a.feat, a.eval, a.hidden)
    heads = heads_of(a.net)
    target = sc.label_of(feat['scores'])
    fold = sc.folds_of(n)
    k = ev['buckets'].astype(np.int64)
    log = logger(a.out + '.log')
    counts = np.array([(fold == t).sum() for t in range(sc.FOLDS)])
    z_int = ev['ys'].astype(np.float64) / (sc.QA * sc.QB)
    shipped = np.array([((sigmoid(z_int) - target)[fold == t] ** 2).sum() for t in range(sc.FOLDS)])
    out = {'positions': n, 'loss': 'mean (sigmoid(z) - sigmoid(score / 92))^2',
           'shipped_integer': {'loss': float(shipped.sum() / counts.sum()), 'fold_loss': (shipped / counts).tolist()},
           'routings': {}}
    # the float form of r3kr1's own heads (no refit), as a check of the float formula
    zf = np.zeros(n)
    for c0, c1, X in chunks(hidden, n):
        zf[c0:c1] = np.einsum('ij,ij->i', X.astype(np.float64), heads[k[c0:c1]])
    flt = np.array([((sigmoid(zf) - target)[fold == t] ** 2).sum() for t in range(sc.FOLDS)])
    out['shipped_float'] = {'loss': float(flt.sum() / counts.sum()), 'fold_loss': (flt / counts).tolist(),
                            'max_abs_z_diff_vs_integer': float(np.abs(zf - z_int).max())}
    log(f"shipped integer {out['shipped_integer']['loss']:.8f}, float {out['shipped_float']['loss']:.8f}")
    prog = dict(np.load(a.progress)) if a.progress else None
    lambdas = tuple(sorted(float(x) for x in a.lambdas.split(','))) if a.lambdas else LAMBDAS
    out['lambdas'] = list(lambdas)
    for routing in a.routings.split(','):
        cell, K = cells_for(routing, feat, ev, hidden, n, progress=prog, column=a.column)
        occupancy = np.bincount(cell, minlength=K).tolist()
        log(f'{routing}: {K} heads, positions per head {occupancy}')
        res, cnt, info = fit(hidden, n, target, cell, K, start_heads(routing, cell, K, k, heads), fold,
                             lambdas=lambdas, log=log)
        s = summarize(res, cnt)
        s.update(info, heads=K, positions_per_head=occupancy)
        out['routings'][routing] = s
        log(f"{routing}: loss {s['loss']:.8f} (lambda {s['lambda']})")
        Path(a.out).write_text(json.dumps(out, indent=1))
    ctrl = out['routings'].get('phase')
    if ctrl:
        for name, s in out['routings'].items():
            d = np.array(s['fold_loss']) - np.array(ctrl['fold_loss'])
            s['diff_vs_phase'] = float(d.mean())
            s['diff_vs_phase_se'] = float(d.std(ddof=1) / math.sqrt(sc.FOLDS))
        d = np.array(ctrl['fold_loss']) - np.array(out['shipped_integer']['fold_loss'])
        ctrl['diff_vs_shipped'] = float(d.mean())
        ctrl['diff_vs_shipped_se'] = float(d.std(ddof=1) / math.sqrt(sc.FOLDS))
    if a.column is not None:
        out['column'] = a.column
    Path(a.out).write_text(json.dumps(out, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('fit-progress')
    p.add_argument('feat')
    p.add_argument('plies')
    p.add_argument('--eval', required=True, help='the output buckets of this set (step0_eval.py output)')
    p.add_argument('--out', required=True)
    p = sub.add_parser('rank-columns')
    for x in ('feat', 'eval', 'hidden'):
        p.add_argument(x)
    p.add_argument('--out', required=True)
    p = sub.add_parser('select-column')
    for x in ('feat', 'eval', 'hidden'):
        p.add_argument(x)
    p.add_argument('--net', required=True)
    p.add_argument('--rank', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--top', type=int, default=8)
    p.add_argument('--lam', type=float, default=10.0)
    p = sub.add_parser('refit')
    for x in ('feat', 'eval', 'hidden'):
        p.add_argument(x)
    p.add_argument('--net', required=True)
    p.add_argument('--progress')
    p.add_argument('--column', type=int)
    p.add_argument('--routings', default='phase,progress,wings,column')
    p.add_argument('--lambdas', help='the ridge grid, comma-separated (default LAMBDAS)')
    p.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    below_normal()
    {'fit-progress': cmd_fit_progress, 'rank-columns': cmd_rank_columns, 'select-column': cmd_select_column,
     'refit': cmd_refit}[a.cmd](a)


if __name__ == '__main__':
    main()
