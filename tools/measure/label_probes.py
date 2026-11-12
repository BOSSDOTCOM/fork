# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline probes on the existing gold labels (ideas.md 83 and 85; docs/research/novel-ideas-2026-11-11.md ideas 5
and 7). Pure Python, CPU minutes. Needs tools/datagen/td_labels.py (branch research/labels-teacher), given by --td.

`superres` (idea 83, label super-resolution): can a small regression from what a record already has (its stored
search score s, the labeller's static evaluation e, their difference s - e, the |s| band and the material class)
predict the deep label better than s itself? Sets:
- H: idea 51's held-out sites (5,000 saved records of g3j-w05-val, one per game; 3,131 kept by the trainer's
  filter), gold S512ppr3 at 1M nodes; independent golds scratch-s1 and scratch-s2 at 1M (ensemble-teacher step 0);
  static e: S512ppr3's evaluation (teacher step 0's H-ppr3-static). Kept records only.
- C: idea 52's 2,000 controls (uniform kept g3j records), gold S512ppr3 at 200,000 nodes, e = S512ppr3's static.
Model (in cp, side to move's view): f = b1 s + b2 (s - e) [model A], plus a slope on s per |s| band and per class
[model B]; label p = sigmoid(f / K), K = 92 (the scale of idea 51's comparisons). Fitted by Gauss-Newton on the
squared error in win probability against the gold (mates as 0 or 1), 10-fold cross-validation (seeded), so every
record is scored by a fit that never saw it. Reported: raw MSE (sigmoid(s / K)), corrected MSE, the reduction, its
95% bootstrap interval (records resampled; H has one record per game, C nearly so), b2 with a 95% bootstrap
interval (refits); the H fit scored against the independent golds too. Kill (owner, ideas.md 83): reduction under
10%, or b2 not positive with its interval clear of zero.

`tdclass` (idea 85, class-matched TD horizon): on H's kept records, the TD(lambda) label (td_labels.py's
td_targets, the recipe's chain, S = K) against each gold, per material class, over a lambda grid; the best lambda
per class with its bootstrap distribution (records resampled within class). Also the result-residual variogram per
class over the first G games of g3j-w05-val: for each chain record t with class c, r_t = z - sigmoid(s_t / K)
(White's view), gamma_c(h) = mean (r_{t+h} - r_t)^2 / 2 over chain pairs h plies apart. Kill (owner, ideas.md 85):
the best lambda for queens-on middlegames and for endgames differ by less than 0.05.

Material classes (phase units N = B = 1, R = 2, Q = 4, as the engine's phase; my reading of the conversion-defense
taxonomy, whose "P" is UNVERIFIED as phase units): Q-MG (a queen on, phase >= 13), Q-EG (a queen on, phase <= 12),
noQ-MG (no queen, phase >= 10), EG (no queen, phase <= 9).

    label_probes.py superres --td DIR --h-sites DIR --h-static DIR --golds NAME=DIR... --c-sites FILE --c-labels FILE
                             --data DIR [--json OUT]
    label_probes.py tdclass --td DIR --h-sites DIR --golds NAME=DIR... --data DIR --shard FILE [--games G] [--json OUT]
"""
import argparse
import json
import math
import os
import random
import sys
from pathlib import Path

K = 92.0
SEED = 20261111
PHASE = {'n': 1, 'b': 1, 'r': 2, 'q': 4}
CLASSES = ('Q-MG', 'Q-EG', 'noQ-MG', 'EG')
BANDS = (100, 300, 700)  # |s| bands: < 100, 100-299, 300-699, >= 700 cp


def material_class(board_field):
    pieces = [c.lower() for c in board_field if c.isalpha()]
    phase = sum(PHASE.get(c, 0) for c in pieces)
    queen = 'q' in pieces
    if queen:
        return 'Q-MG' if phase >= 13 else 'Q-EG'
    return 'noQ-MG' if phase >= 10 else 'EG'


def sig(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def read_tsv(path):
    out = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            f = line.split('\t')
            out[int(f[0])] = (int(f[1]), int(f[2]))
    return out


def gold_p(cp, mate):
    if mate:
        return 1.0 if cp > 0 else 0.0
    return sig(cp / K)


# ---- the regression ----

def features(r, model):
    s, e = r['s'], r['e']
    x = [s, s - e]
    if model == 'B':
        band = sum(abs(s) >= b for b in BANDS)
        x += [s if band == k else 0.0 for k in range(1, len(BANDS) + 1)]
        x += [s if r['cls'] == c else 0.0 for c in CLASSES[1:]]
    return x


def fit(rows, model, iters=30):
    """Gauss-Newton (Levenberg-damped) on mean (sigmoid(f / K) - gold)^2, f = beta . x."""
    xs = [features(r, model) for r in rows]
    ys = [r['g'] for r in rows]
    k = len(xs[0])
    beta = [1.0] + [0.0] * (k - 1)
    damp = 1e-3

    def loss(b):
        return sum((sig(sum(c * v for c, v in zip(b, x)) / K) - y) ** 2 for x, y in zip(xs, ys))

    cur = loss(beta)
    for _ in range(iters):
        jtj = [[0.0] * k for _ in range(k)]
        jtr = [0.0] * k
        for x, y in zip(xs, ys):
            p = sig(sum(c * v for c, v in zip(beta, x)) / K)
            d = p * (1 - p) / K
            res = p - y
            for i in range(k):
                gi = d * x[i]
                jtr[i] += gi * res
                for j in range(i + 1):
                    jtj[i][j] += gi * d * x[j]
        for i in range(k):
            for j in range(i):
                jtj[j][i] = jtj[i][j]
        while True:
            a = [[jtj[i][j] + (damp * (jtj[i][i] + 1e-12) if i == j else 0.0) for j in range(k)] for i in range(k)]
            step = solve(a, [-v for v in jtr])
            trial = [b + s for b, s in zip(beta, step)]
            new = loss(trial)
            if new <= cur:
                beta, cur, damp = trial, new, max(damp / 10, 1e-9)
                break
            damp *= 10
            if damp > 1e6:
                return beta
        if max(abs(s) for s in step) < 1e-7:
            break
    return beta


def solve(a, b):
    n = len(b)
    m = [list(a[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        if abs(m[col][col]) < 1e-300:
            raise ValueError('singular')
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def predict(beta, r, model):
    return sig(sum(c * v for c, v in zip(beta, features(r, model))) / K)


def crossval(rows, model, folds=10):
    rng = random.Random(SEED)
    order = list(range(len(rows)))
    rng.shuffle(order)
    pred = [None] * len(rows)
    for f in range(folds):
        test = set(order[f::folds])
        beta = fit([rows[i] for i in range(len(rows)) if i not in test], model)
        for i in test:
            pred[i] = predict(beta, rows[i], model)
    return pred


def pct_interval(vals):
    vals = sorted(vals)
    return [vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]]


def superres_block(rows, model, golds_extra=(), rounds=1000, refits=None):
    refits = refits or (200 if model == 'A' else 50)
    pred = crossval(rows, model)
    raw = [sig(r['s'] / K) for r in rows]
    out = {'records': len(rows), 'model': model}
    gold_sets = [('gold', [r['g'] for r in rows])] + [(n, [r['extra'][n] for r in rows]) for n in golds_extra]
    rng = random.Random(SEED)
    idx_rounds = [[rng.randrange(len(rows)) for _ in rows] for _ in range(rounds)]
    for name, gold in gold_sets:
        e_raw = [(p - g) ** 2 for p, g in zip(raw, gold)]
        e_cor = [(p - g) ** 2 for p, g in zip(pred, gold)]
        m_raw, m_cor = sum(e_raw) / len(rows), sum(e_cor) / len(rows)
        reds = []
        for idx in idx_rounds:
            a = sum(e_raw[i] for i in idx)
            b = sum(e_cor[i] for i in idx)
            reds.append(1 - b / a)
        out[name] = {'mse_raw': m_raw, 'mse_corrected': m_cor, 'reduction': 1 - m_cor / m_raw,
                     'reduction_ci95': pct_interval(reds)}
    beta = fit(rows, model)
    out['beta_full'] = beta
    rng = random.Random(SEED + 1)
    b2 = []
    for _ in range(refits):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        b2.append(fit(sample, model)[1])
    out['b2'] = beta[1]
    out['b2_ci95'] = pct_interval(b2)
    by = {}
    for r, p, q in zip(rows, raw, pred):
        d = by.setdefault(r['cls'], [0, 0.0, 0.0])
        d[0] += 1
        d[1] += (p - r['g']) ** 2
        d[2] += (q - r['g']) ** 2
    out['by_class'] = {c: {'n': n, 'mse_raw': a / n, 'mse_corrected': b / n, 'reduction': 1 - b / a if a else None}
                       for c, (n, a, b) in sorted(by.items())}
    return out


def load_h(a, td):
    golds = dict(g.split('=', 1) for g in a.golds)
    first = next(iter(golds))
    rows, stats = td.matched_records([Path(golds[first])], [a.data])
    sites = {}
    for line in (Path(a.h_sites) / 'sites.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            s = json.loads(line)
            sites[(s['game'], s['record'])] = s
    tables = {n: read_tsv(Path(d) / 'deep.tsv') for n, d in golds.items()}
    static = read_tsv(Path(a.h_static) / 'deep.tsv') if getattr(a, 'h_static', None) else None
    out = []
    for r in rows:
        if not r['kept']:
            continue
        site = sites[(r['game'], r['record'])]
        sid = site['id']
        s_white = r['scores'][r['record']]
        s = s_white if r['white'] else -s_white
        row = {'id': sid, 'game': r['game'], 's': float(s), 'cls': material_class(site['fen'].split()[0]),
               'g': gold_p(*tables[first][sid]), 'extra': {n: gold_p(*t[sid]) for n, t in tables.items()},
               'td': r}
        if static is not None:
            row['e'] = float(static[sid][0])
        out.append(row)
    return out, stats, first


def cmd_superres(a, td):
    h, stats, first = load_h(a, td)
    extra = [n for n in dict(g.split('=', 1) for g in a.golds) if n != first]
    labels = read_tsv(a.c_labels)
    c = []
    for line in Path(a.c_sites).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        s = json.loads(line)
        if s.get('set') != 'control' or s['id'] not in labels:
            continue
        white = s['fen'].split()[1] == 'w'
        stored = s['score_white'] if white else -s['score_white']
        c.append({'id': s['id'], 'game': f"{s['shard']}#{s['game']}", 's': float(stored), 'e': float(s['eval_a']),
                  'cls': material_class(s['fen'].split()[0]), 'g': gold_p(*labels[s['id']]), 'extra': {}})
    out = {'K': K, 'seed': SEED, 'match': stats, 'H': {}, 'C': {}}
    for model in ('A', 'B'):
        out['H'][model] = superres_block(h, model, extra)
        out['C'][model] = superres_block(c, model)
    a_red, a_ci = out['H']['A']['gold']['reduction'], out['H']['A']['b2_ci95']
    out['verdict'] = {
        'H_model_A_reduction': a_red, 'H_model_A_b2_ci95': a_ci,
        'kill': a_red < 0.10 or a_ci[0] <= 0,
        'rule': 'kill if the reduction against the gold is under 10% or b2 (the slope on s - e) is not positive with '
                'its 95% interval clear of zero; primary: H, model A, the S512ppr3 1M gold'}
    return out


def cmd_tdclass(a, td):
    h, stats, first = load_h(a, td)
    names = list(dict(g.split('=', 1) for g in a.golds))
    grid = [float(x) for x in a.grid.split(',')]
    labels = {}
    for r in h:
        t = r['td']
        for lam in grid:
            key = (t['game'], lam)
            if key not in labels:
                labels[key] = td.td_targets(t['scores'], t['result'], lam, K, skip=t['check'])
    out = {'K': K, 'grid': grid, 'match': stats, 'golds': names, 'classes': {}}
    rng = random.Random(SEED)
    targets = names + ['independent_mean']
    for cls in CLASSES + ('all',):
        rows = [r for r in h if cls == 'all' or r['cls'] == cls]
        rows = [r for r in rows if labels[(r['td']['game'], 0.9)][r['td']['record']] is not None]
        if not rows:
            continue
        err = {}
        for name in targets:
            for lam in grid:
                e = []
                for r in rows:
                    lab = labels[(r['td']['game'], lam)][r['td']['record']]
                    p = lab if r['td']['white'] else 1 - lab
                    g = (sum(r['extra'][n] for n in names[1:]) / len(names[1:]) if name == 'independent_mean'
                         else r['extra'][name])
                    e.append((p - g) ** 2)
                err[(name, lam)] = e
        block = {'n': len(rows)}
        for name in targets:
            mse = {lam: sum(err[(name, lam)]) / len(rows) for lam in grid}
            best = min(grid, key=lambda lam: mse[lam])
            boots = []
            for _ in range(300):
                idx = [rng.randrange(len(rows)) for _ in rows]
                boots.append(min(grid, key=lambda lam: sum(err[(name, lam)][i] for i in idx)))
            block[name] = {'mse': {str(k): v for k, v in mse.items()}, 'best': best,
                           'best_boot': {str(lam): boots.count(lam) / len(boots) for lam in grid if boots.count(lam)}}
        out['classes'][cls] = block
    # The variogram.
    data = Path(a.shard).read_bytes()
    lags = (1, 2, 4, 8, 16, 32)
    acc = {c: {h_: [0.0, 0] for h_ in lags} for c in CLASSES}
    games = 0
    for _start, head, recs, _end in td.split_games(data, a.games):
        rows, _kind = td.replay(head, recs, 0)
        z = td.WHITE_RESULT[head[30]]
        res = [None if (sc == td.UNSAVED or rows[t][3]) else z - sig(sc / K) for t, (_c, sc) in enumerate(recs)]
        cls = [material_class(r[0].split()[0]) for r in rows]
        for t, rt in enumerate(res):
            if rt is None:
                continue
            for h_ in lags:
                if t + h_ < len(res) and res[t + h_] is not None:
                    d = acc[cls[t]][h_]
                    d[0] += (res[t + h_] - rt) ** 2 / 2
                    d[1] += 1
        games += 1
    out['variogram'] = {'games': games, 'lags': list(lags),
                        'gamma': {c: {str(h_): (v[0] / v[1] if v[1] else None) for h_, v in acc[c].items()}
                                  for c in CLASSES},
                        'pairs': {c: {str(h_): v[1] for h_, v in acc[c].items()} for c in CLASSES}}
    qmg = out['classes']['Q-MG']
    eg = out['classes']['EG']
    out['verdict'] = {
        'best_lambda_QMG': {n: qmg[n]['best'] for n in targets}, 'best_lambda_EG': {n: eg[n]['best'] for n in targets},
        'kill_by_gold': {n: abs(qmg[n]['best'] - eg[n]['best']) < 0.05 for n in targets},
        'rule': 'kill if the best lambda for Q-MG and for EG differ by less than 0.05 (primary: the independent gold '
                'mean, which shares no network with the stored scores; S512ppr3 gold reported beside it)'}
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('superres', 'tdclass'):
        s = sub.add_parser(name)
        s.add_argument('--td', required=True, type=Path)
        s.add_argument('--h-sites', required=True)
        s.add_argument('--golds', nargs='+', required=True, help='NAME=DIR, the first is the primary gold')
        s.add_argument('--data', required=True)
        s.add_argument('--json', type=Path)
    s = sub.choices['superres']
    s.add_argument('--h-static', required=True)
    s.add_argument('--c-sites', required=True)
    s.add_argument('--c-labels', required=True)
    s = sub.choices['tdclass']
    s.add_argument('--shard', required=True)
    s.add_argument('--games', type=int, default=3000)
    s.add_argument('--grid', default='0,0.5,0.6,0.7,0.8,0.85,0.9,0.93,0.95,0.97,0.99')
    a = p.parse_args(argv)
    if sys.platform == 'win32':  # below-normal priority: production jobs share the machine
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    elif hasattr(os, 'nice'):
        os.nice(10)
    sys.path.insert(0, str(a.td.resolve()))
    import td_labels as td
    out = cmd_superres(a, td) if a.cmd == 'superres' else cmd_tdclass(a, td)
    text = json.dumps(out, indent=1)
    if a.json:
        a.json.write_text(text + '\n', encoding='utf-8')
    print(json.dumps(out.get('verdict'), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
