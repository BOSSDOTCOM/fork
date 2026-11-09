# SPDX-License-Identifier: GPL-3.0-or-later
"""X6 of Phase 4 step 1 (DESIGN.md §5.7): the node-share fit.

Does the best move's share of the root nodes, with best-move stability and
the score's change, predict that the best move changes within the next two
iterations? Fork's own curve for node-share time management (think tank
R8, specialist S1), measured before any game.

Input: game_replay.py runs with `--report iterations` (a stats build's
`iteration_trace` rows, one per finished iteration). Rows: each finished
iteration k whose search also finished k+1 and k+2 (the last two are
censored). Label: the best move at k+1 or at k+2 differs from the best at
k; S1's variant (the best at k+2 differs) is reported beside it. Searches
whose score at k is a mate or tablebase score (|score| >= TbWinScore -
MaxPly = 29,250, src/search/score_bounds.hpp) are left out of those rows.

Features: the logit of the share (per mille / 1000, clipped to [0.005,
0.995]), stability (finished iterations in a row ending at k with the same
best move, capped at 10), log(1 + |score change from k-1|) (cp, clipped at
500), and the depth. Logistic regression by IRLS (Newton steps with a
ridge of 1e-6), pure Python (the repository's venv has no numpy).

Reported, for both share definitions (the last aspiration pass's, `share`,
the one the engine already computes, and every pass's, `share_all`): rows,
base rate, coefficients, AUC (rank form), out-of-sample AUC (two folds by
game), McFadden's pseudo-R², the partial R² of the share (1 - LL_full /
LL_without_share), Spearman's rho² of the share against the label, and
P(change) by share decile. 95% intervals: a bootstrap over games, 300
rounds, seed 20261108 (each round refits twice per definition; 300 keeps
the pure-Python refits to minutes).

Declared readings (specialist S1, verdict B14; DESIGN.md §5.7), fixed
before the data were seen: the primary fit uses rows at depth >= 8 (where
an STC soft-limit decision is taken) and the definition with the higher
AUC; rho² < 0.03 (a time-equivalent under 1.5%, under +2.3 Elo by M5's
table) skips R8's share SPRT and tries the stability signal instead;
otherwise the decile curve and the predicted Elo from M5 go into R8's spec.
M5's rho² is the share's explained share of per-move difficulty; Spearman's
rho² against a two-iteration change is its proxy (UNVERIFIED that the two
coincide).

    node_share_fit.py REPLAY_DIR... [--min-depth 8] [--rounds 300] [--json OUT] [--csv OUT]
"""
import argparse
import csv
import json
import math
import random
import sys
import zlib
from pathlib import Path


def change_label(bests, k):
    """(changes within the next two iterations, S1's: the best at k+2 differs)."""
    return int(bests[k + 1] != bests[k] or bests[k + 2] != bests[k]), int(bests[k + 2] != bests[k])


def iteration_rows(records, min_depth=1):
    """One row per finished iteration with two finished iterations after it."""
    rows = []
    for record in records:
        its = record.get('iterations') or []
        bests = [it['best'] for it in its]
        for k in range(len(its) - 2):
            it = its[k]
            if abs(it['score']) >= 29250 or it['depth'] < min_depth:
                continue
            stability = 1
            while stability <= k and bests[k - stability] == bests[k]:
                stability += 1
            y, y_s1 = change_label(bests, k)
            rows.append({'game': record['game'], 'ply': record['ply'], 'depth': it['depth'], 'share': it['share'],
                         'share_all': it['share_all'], 'runner_up': it['runner_up'], 'stability': stability,
                         'dscore': abs(it['score'] - its[k - 1]['score']) if k > 0 else 0, 'y': y, 'y_s1': y_s1})
    return rows


def share_logit(share_permille):
    p = min(max(share_permille / 1000, 0.005), 0.995)
    return math.log(p / (1 - p))


def feature_vector(row, share_key='share', drop=None):
    """[1, logit share, stability (cap 10), log1p |score change| (cap 500), depth], less `drop`."""
    features = {'share': share_logit(row[share_key]), 'stability': min(row['stability'], 10),
                'dscore': math.log1p(min(row['dscore'], 500)), 'depth': row['depth']}
    return [1.0] + [v for k, v in features.items() if k != drop]


def sigmoid(z):
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def solve_linear(a, b):
    """Solves a x = b (Gaussian elimination with partial pivoting)."""
    n = len(b)
    m = [list(a[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[pivot] = m[pivot], m[col]
        if abs(m[col][col]) < 1e-300:
            raise ValueError('singular system')
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def predict(beta, xs):
    return [sigmoid(sum(b * v for b, v in zip(beta, x))) for x in xs]


def log_likelihood(beta, xs, ys):
    total = 0.0
    for p, y in zip(predict(beta, xs), ys):
        p = min(max(p, 1e-12), 1 - 1e-12)
        total += math.log(p) if y else math.log(1 - p)
    return total


def fit_logistic_irls(xs, ys, ridge=1e-6, iterations=50, start=None, tolerance=1e-9):
    """Maximum-likelihood logistic coefficients by Newton steps (IRLS)."""
    k = len(xs[0])
    beta = list(start) if start else [0.0] * k
    for _ in range(iterations):
        grad = [-ridge * b for b in beta]
        hess = [[ridge if i == j else 0.0 for j in range(k)] for i in range(k)]
        for x, y, p in zip(xs, ys, predict(beta, xs)):
            w = p * (1 - p)
            for i in range(k):
                grad[i] += (y - p) * x[i]
                xi = w * x[i]
                for j in range(i + 1):
                    hess[i][j] += xi * x[j]
        for i in range(k):
            for j in range(i):
                hess[j][i] = hess[i][j]
        step = solve_linear(hess, grad)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < tolerance:
            break
    return beta


def rank_values(xs):
    """Ranks from 1, ties sharing their average rank."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for t in range(i, j + 1):
            ranks[order[t]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def rank_auc(scores, labels):
    """The area under the ROC curve, as the Mann-Whitney statistic."""
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return float('nan')
    ranks = rank_values(scores)
    return (sum(r for r, y in zip(ranks, labels) if y) - positives * (positives + 1) / 2) / (positives * negatives)


def spearman_rho(xs, ys):
    rx, ry = rank_values(xs), rank_values(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else 0.0


def partial_r2(rows, feature, share_key='share', label='y', start=None):
    """1 - LL_full / LL_without(feature): McFadden's partial R² of one feature."""
    ys = [r[label] for r in rows]
    full_x = [feature_vector(r, share_key) for r in rows]
    less_x = [feature_vector(r, share_key, drop=feature) for r in rows]
    full = fit_logistic_irls(full_x, ys, start=start)
    less = fit_logistic_irls(less_x, ys)
    return 1 - log_likelihood(full, full_x, ys) / log_likelihood(less, less_x, ys)


def game_bootstrap(rows, statistic, rounds, seed):
    """The 2.5% and 97.5% points of `statistic(rows)` over games resampled with replacement."""
    by_game = {}
    for r in rows:
        by_game.setdefault(r['game'], []).append(r)
    games = sorted(by_game)
    rng = random.Random(seed)
    values = []
    for _ in range(rounds):
        sample = []
        for _ in games:
            sample.extend(by_game[games[rng.randrange(len(games))]])
        values.append(statistic(sample))
    values.sort()
    return values[int(0.025 * rounds)], values[max(int(0.975 * rounds) - 1, 0)]


def binned_curve(rows, key='share', bins=10, label='y'):
    """P(change) by quantile bin of `key`: [(low, high, rows, rate)]."""
    ordered = sorted(rows, key=lambda r: r[key])
    out = []
    for b in range(bins):
        part = ordered[b * len(ordered) // bins:(b + 1) * len(ordered) // bins]
        if part:
            out.append((part[0][key], part[-1][key], len(part), sum(r[label] for r in part) / len(part)))
    return out


def write_rows(rows, path):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('replay', nargs='+', type=Path)
    parser.add_argument('--min-depth', type=int, default=8)
    parser.add_argument('--rounds', type=int, default=300)
    parser.add_argument('--seed', type=int, default=20261108)
    parser.add_argument('--json', type=Path, default=None)
    parser.add_argument('--csv', type=Path, default=None)
    a = parser.parse_args(argv)

    records = []
    for d in a.replay:
        for f in sorted(d.glob('game-*.jsonl')):
            records.extend(json.loads(line) for line in f.read_text(encoding='utf-8').splitlines())
    result = {'searches': len(records)}
    for scope, min_depth in (('primary', a.min_depth), ('all_depths', 1)):
        rows = iteration_rows(records, min_depth)
        if a.csv and scope == 'primary':
            write_rows(rows, a.csv)
        ys = [r['y'] for r in rows]
        block = {'rows': len(rows), 'games': len({r['game'] for r in rows}), 'base_rate': sum(ys) / len(ys)}
        for share_key in ('share', 'share_all'):
            xs = [feature_vector(r, share_key) for r in rows]
            beta = fit_logistic_irls(xs, ys)
            null = math.log(block['base_rate']) * sum(ys) + math.log(1 - block['base_rate']) * (len(ys) - sum(ys))
            ll = log_likelihood(beta, xs, ys)
            # Two folds by game (a stable hash of the game id).
            fold_scores, fold_labels = [], []
            for fold in (0, 1):
                train = [r for r in rows if zlib.crc32(r['game'].encode()) % 2 != fold]
                test = [r for r in rows if zlib.crc32(r['game'].encode()) % 2 == fold]
                b = fit_logistic_irls([feature_vector(r, share_key) for r in train], [r['y'] for r in train])
                fold_scores += predict(b, [feature_vector(r, share_key) for r in test])
                fold_labels += [r['y'] for r in test]

            def auc_of(sample, key=share_key, start=beta):
                bb = fit_logistic_irls([feature_vector(r, key) for r in sample], [r['y'] for r in sample],
                                       start=start, iterations=8)
                return rank_auc(predict(bb, [feature_vector(r, key) for r in sample]), [r['y'] for r in sample])

            def rho2_of(sample, key=share_key):
                return spearman_rho([r[key] for r in sample], [r['y'] for r in sample]) ** 2

            def partial_of(sample, key=share_key, start=beta):
                return partial_r2(sample, 'share', key, start=start)

            entry = {
                'coefficients': dict(zip(['intercept', 'logit_share', 'stability', 'log1p_dscore', 'depth'], beta)),
                'auc': rank_auc(predict(beta, xs), ys),
                'auc_ci95': game_bootstrap(rows, auc_of, a.rounds, a.seed),
                'auc_out_of_sample': rank_auc(fold_scores, fold_labels),
                'mcfadden_r2': 1 - ll / null,
                'partial_r2_share': partial_r2(rows, 'share', share_key),
                'partial_r2_share_ci95': game_bootstrap(rows, partial_of, a.rounds, a.seed),
                'partial_r2_stability': partial_r2(rows, 'stability', share_key),
                'partial_r2_dscore': partial_r2(rows, 'dscore', share_key),
                'spearman_rho2_share': rho2_of(rows),
                'spearman_rho2_share_ci95': game_bootstrap(rows, rho2_of, a.rounds, a.seed),
                'auc_share_alone': rank_auc([-r[share_key] for r in rows], ys),
                'auc_s1_label': rank_auc(predict(fit_logistic_irls(xs, [r['y_s1'] for r in rows]), xs),
                                         [r['y_s1'] for r in rows]),
                'curve_by_share_decile': binned_curve(rows, share_key),
            }
            block[share_key] = entry
            print(f'{scope} {share_key}: AUC {entry["auc"]:.3f} {entry["auc_ci95"]}, out of sample '
                  f'{entry["auc_out_of_sample"]:.3f}, partial R2(share) {entry["partial_r2_share"]:.4f}, '
                  f'rho2 {entry["spearman_rho2_share"]:.4f}', flush=True)
        block['stability_curve'] = binned_curve(rows, 'stability', bins=5)
        result[scope] = block
    out = json.dumps(result, indent=1)
    if a.json:
        a.json.write_text(out + '\n', encoding='utf-8')
    print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
