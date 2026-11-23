# SPDX-License-Identifier: GPL-3.0-or-later
"""Vision step 0 (ideas.md 185), parts (a)-(c): each family's held-out share of a network's residual variance,
with idea 175's design (tools/nnue/state_rows_study.py on proto/i175-state-rows; docs/research/idea175-screens.md).

r = label - sigmoid(y / (QA * QB)), the label the trainer's target at result weight 0 (sigmoid(score / 92) of the
dump's copy score), y from step0_eval.py. A family's table (one column per cell) is fitted beside the base table
(one column per mover-relative colour, kind and square: 768) by ridge least squares on r minus the training folds'
mean, no intercept. Positions are cut into blocks of 2,000 consecutive positions, block b in fold b mod 8, each fold
predicted from the other seven. The base table's ridge strength is chosen alone (of BASE_LAMBDAS), then the
family's (of LAMBDAS) with the base's kept, each by the pooled held-out SSE (both grids 1 to 1e7; idea 175's family grid stopped at 1e5). Share = (held-out SSE of the base
table - of base + family) / held-out sum of squares of r about the training mean, pooled over the folds; +- the
standard error of the 8 per-fold shares. Each family in three designs:
- square: one column per cell (side x kind x state x square, the family's layout in step0_common);
- pooled: one column per block (the cell's side, kind and state, its square pooled; a column holds the count);
- bucket: one column per (block, the net's output bucket), the state-by-phase table that pooled tables average away.
and, for families with both sides' cells, for the mover's cells only, the opponent's only and both.
(Unlike idea 175's script, the centring uses each column's sum, which is right for count columns too.)

`--inject FAMILY SIDE SHARE` adds a known effect first: a fixed random value (normal, seed 20261114) per by-square
cell of the family's chosen side, summed over a position's set cells and scaled so the effect is SHARE of r's
variance; the run then reports what the study recovers for that family (the checker check).

    step0_study.py FEAT.npz --net NAME=EVAL.npz [--net ...] --out OUT.json [--families a,b] [--calibration-only NAME]
                   [--inject FAMILY SIDE SHARE]
"""
import argparse
import ctypes
import json
import math
import os
import sys
import time

for var in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(var, '3')

import numpy as np  # noqa: E402
import scipy.sparse as sp  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import step0_common as sc  # noqa: E402

BASE_LAMBDAS = (1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0, 3000.0, 10000.0, 30000.0, 100000.0, 1e6, 1e7)
# idea 175's family grid ended at 1e5; it is extended to the base's 1e7 here, so a family the base table already
# covers can shrink to nothing instead of reading slightly negative.
LAMBDAS = BASE_LAMBDAS
CALIBRATION = ('xl', 'xpn', 'xsl', 'xx', 'links')


def below_normal():
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def csr(flat, off, cols, n, mapping=None):
    """The n x cols count matrix of a family (cells mapped through `mapping`, -1 dropped)."""
    rows = np.repeat(np.arange(n), np.diff(off))
    c = flat.astype(np.int64)
    if mapping is not None:
        c = mapping[c]
        keep = c >= 0
        rows, c = rows[keep], c[keep]
    data = np.ones(len(c), dtype=np.float64)
    return sp.csr_matrix((data, (rows, c)), shape=(n, cols))


class Folds:
    def __init__(self, n, R):
        self.fold = sc.folds_of(n)
        self.rows = [np.nonzero(self.fold == f)[0] for f in range(sc.FOLDS)]
        self.R = R  # n x nets
        self.S = np.array([[(len(r), R[r, j].sum(), (R[r, j] ** 2).sum()) for r in self.rows]
                           for j in range(R.shape[1])])  # nets x folds x 3

    def parts(self, j, t):
        train = [f for f in range(sc.FOLDS) if f != t]
        S = self.S[j]
        mu = S[train, 1].sum() / S[train, 0].sum()
        sst = S[t, 2] - 2 * mu * S[t, 1] + mu * mu * S[t, 0]
        return mu, sst


def fold_stats(X, folds):
    """Per fold: X_f^T X_f (dense float32: counts, exact below 2^24), X_f^T R and the column sums."""
    c = X.shape[1]
    G = np.zeros((sc.FOLDS, c, c), dtype=np.float32)
    Bv = np.zeros((sc.FOLDS, c, folds.R.shape[1]))
    C = np.zeros((sc.FOLDS, c))
    for f, r in enumerate(folds.rows):
        Xf = X[r]
        G[f] = (Xf.T @ Xf).toarray()
        Bv[f] = Xf.T @ folds.R[r]
        C[f] = np.asarray(Xf.sum(axis=0)).ravel()
    return G, Bv, C


def fold_sse(G, Bv, C, folds, nets, pens):
    """sse[j][p][t]: held-out fold t's SSE for net j under penalty vector pens[j][p] (the fit on the other folds)."""
    Gtot = G.sum(axis=0, dtype=np.float64)
    Btot, Ctot = Bv.sum(axis=0), C.sum(axis=0)
    out = {j: np.zeros((len(pens[j]), sc.FOLDS)) for j in nets}
    sst = {j: np.zeros(sc.FOLDS) for j in nets}
    for t in range(sc.FOLDS):
        Gh = G[t].astype(np.float64)
        Gt = Gtot - Gh
        for j in nets:
            mu, sst[j][t] = folds.parts(j, t)
            bt = (Btot[:, j] - Bv[t, :, j]) - mu * (Ctot - C[t])
            bh = Bv[t, :, j] - mu * C[t]
            for p, pen in enumerate(pens[j]):
                beta = np.linalg.solve(Gt + np.diag(pen), bt)
                out[j][p, t] = sst[j][t] - 2 * beta @ bh + beta @ Gh @ beta
    return out, sst


class Base:
    """The base table's fold statistics and, per net, its ridge strength and held-out SSE."""

    def __init__(self, feat, folds, n):
        self.X = csr(feat['base_flat'], feat['base_off'], 768, n)
        nets = list(range(folds.R.shape[1]))
        G, Bv, C = fold_stats(self.X, folds)
        pens = {j: [np.full(768, lam) for lam in BASE_LAMBDAS] for j in nets}
        sse, sst = fold_sse(G, Bv, C, folds, nets, pens)
        self.lam, self.sse, self.sst = {}, {}, {}
        for j in nets:
            p = int(np.argmin(sse[j].sum(axis=1)))
            self.lam[j], self.sse[j], self.sst[j] = BASE_LAMBDAS[p], sse[j][p], sst[j]


def share(base, F, folds, nets):
    """Each net's held-out share of the family columns F (an n x c sparse matrix) over the base table."""
    X = sp.hstack([base.X, F]).tocsr()
    c = F.shape[1]
    G, Bv, C = fold_stats(X, folds)
    pens = {j: [np.concatenate([np.full(768, base.lam[j]), np.full(c, lam)]) for lam in LAMBDAS] for j in nets}
    sse, _ = fold_sse(G, Bv, C, folds, nets, pens)
    del G
    out = {}
    for j in nets:
        p = int(np.argmin(sse[j].sum(axis=1)))
        lam, sse1 = LAMBDAS[p], sse[j][p]
        sse0, sst = base.sse[j], base.sst[j]
        per = (sse0 - sse1) / sst
        out[j] = {'share_pct': float(100 * (sse0.sum() - sse1.sum()) / sst.sum()),
                  'se_pct': float(100 * per.std(ddof=1) / math.sqrt(sc.FOLDS)),
                  'folds_pct': [round(float(100 * x), 5) for x in per], 'lambda': lam, 'lambda_base': base.lam[j],
                  'columns': int(c)}
    return out


def variants(name, layout):
    cells, side, group = layout
    sides = sorted(set(int(s) for s in side))
    sel = {'both': np.ones(cells, dtype=bool)}
    if 0 in sides and 1 in sides:
        sel['mover'] = side == 0
        sel['opp'] = side == 1
    return sel


def mapping_for(design, keep, group, cells, bucket_count=8):
    """cell -> column (-1 dropped) for a design; for 'bucket' the column is group * 8 + bucket, added later."""
    m = np.full(cells, -1, dtype=np.int64)
    if design == 'square':
        m[keep] = np.arange(keep.sum())
        return m, int(keep.sum())
    g = group[keep]
    uniq, inv = np.unique(g, return_inverse=True)
    m[keep] = inv
    return m, len(uniq)


def family_matrix(feat, name, layout, keep, design, n, buckets):
    cells, side, group = layout
    flat, off = feat[f'{name}_flat'], feat[f'{name}_off']
    m, cols = mapping_for(design, keep, group, cells)
    if design != 'bucket':
        return csr(flat, off, cols, n, m), cols
    rows = np.repeat(np.arange(n), np.diff(off))
    c = m[flat.astype(np.int64)]
    ok = c >= 0
    rows, c = rows[ok], c[ok] * 8 + buckets[rows[ok]]
    return sp.csr_matrix((np.ones(len(c)), (rows, c)), shape=(n, cols * 8)), cols * 8


def prevalence(feat, name, keep, n):
    flat, off = feat[f'{name}_flat'], feat[f'{name}_off']
    rows = np.repeat(np.arange(n), np.diff(off))
    per = np.bincount(rows[keep[flat.astype(np.int64)]], minlength=n)
    return {'positions_with_any_pct': float(100 * (per > 0).mean()), 'cells_per_position': float(per.mean())}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('feat')
    ap.add_argument('--net', action='append', required=True, help='NAME=EVAL.npz')
    ap.add_argument('--out', required=True)
    ap.add_argument('--families', default=','.join(sc.FAMILY_NAMES))
    ap.add_argument('--calibration-only', action='append', default=[],
                    help='a net measured on the calibration families only')
    ap.add_argument('--designs', default='square,pooled,bucket')
    ap.add_argument('--inject', nargs=3, metavar=('FAMILY', 'SIDE', 'SHARE'))
    ap.add_argument('--bucket-net', help='the net whose output buckets the bucket design uses (default: the first)')
    a = ap.parse_args(argv)
    below_normal()
    t0 = time.time()
    feat = dict(np.load(a.feat))
    n = int(feat['n'][0])
    label = sc.label_of(feat['scores'])
    names, R, buckets = [], [], {}
    for spec in a.net:
        name, path = spec.split('=', 1)
        e = np.load(path)
        assert len(e['ys']) == n
        names.append(name)
        R.append(label - 1.0 / (1.0 + np.exp(-e['ys'].astype(np.float64) / (sc.QA * sc.QB))))
        buckets[name] = e['buckets'].astype(np.int64)
    R = np.stack(R, axis=1)
    lay = sc.layouts()
    report = {'feat': os.path.basename(a.feat), 'positions': n, 'nets': names, 'families': {}}
    if a.inject:
        fam, sd, sh = a.inject[0], a.inject[1], float(a.inject[2])
        cells, side, _ = lay[fam]
        keep = variants(fam, lay[fam])[sd]
        rng = np.random.default_rng(20261114)
        val = np.where(keep, rng.standard_normal(cells), 0.0)
        flat, off = feat[f'{fam}_flat'], feat[f'{fam}_off']
        eff = np.bincount(np.repeat(np.arange(n), np.diff(off)), weights=val[flat.astype(np.int64)], minlength=n)
        eff -= eff.mean()
        for j in range(R.shape[1]):
            scale = math.sqrt(sh * R[:, j].var() / eff.var())
            R[:, j] = R[:, j] + scale * eff
        report['inject'] = {'family': fam, 'side': sd, 'share_of_old_var': sh,
                            'share_of_new_var_pct': 100 * sh / (1 + sh)}
    report['residual'] = {nm: {'mean': float(R[:, j].mean()), 'var': float(R[:, j].var())}
                          for j, nm in enumerate(names)}
    folds = Folds(n, R)
    base = Base(feat, folds, n)
    report['base'] = {nm: {'lambda': base.lam[j],
                           'r2_heldout_pct': float(100 * (1 - base.sse[j].sum() / base.sst[j].sum()))}
                      for j, nm in enumerate(names)}
    print(f'base done {time.time() - t0:.0f} s', report['base'], flush=True)
    bnet = a.bucket_net or names[0]
    report['bucket_net'] = bnet
    fams = [f for f in a.families.split(',') if f]
    if a.inject:
        fams = [a.inject[0]]
    for fam in fams:
        nets = [j for j, nm in enumerate(names) if nm not in a.calibration_only or fam in CALIBRATION]
        if not nets:
            continue
        sels = variants(fam, lay[fam])
        if a.inject:
            sels = {a.inject[1]: sels[a.inject[1]]}
        res = {}
        for sd, keep in sels.items():
            row = {'prevalence': prevalence(feat, fam, keep, n)}
            for design in a.designs.split(','):
                F, cols = family_matrix(feat, fam, lay[fam], keep, design, n, buckets[bnet])
                r = share(base, F, folds, nets)
                row[design] = {names[j]: v for j, v in r.items()}
                line = '  '.join(f"{names[j]} {v['share_pct']:.4f} +- {v['se_pct']:.4f}" for j, v in r.items())
                print(f'{fam:6s} {sd:5s} {design:6s} cols {cols:5d}  {line}   ({time.time() - t0:.0f} s)', flush=True)
            res[sd] = row
        report['families'][fam] = res
        with open(a.out, 'w') as fh:
            json.dump(report, fh, indent=1)
    report['seconds'] = round(time.time() - t0)
    with open(a.out, 'w') as fh:
        json.dump(report, fh, indent=1)


if __name__ == '__main__':
    main()
