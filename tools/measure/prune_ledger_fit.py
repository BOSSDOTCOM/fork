# SPDX-License-Identifier: GPL-3.0-or-later
"""X10 of Phase 4 step 1 (DESIGN.md §5.7): the decision ledger's RFP and
futility rows.

A stats build with FORK_PRUNE_LEDGER=N samples 1 in N of the candidates of
reverse futility pruning and futility pruning (every condition but the
margin) by the position's key, and searches each sampled node again with
the technique toggled there only, in side searches the real search never
sees (src/search/searcher.cpp). Each row is one decision:

- RFP (gap g = prune_eval - beta, >= 0): the node searched with RFP off
  there; the prune (taken when g >= RfpMargin * depth, or one a smaller
  margin would take) is wrong when that search fails low (< beta).
- Futility (gap g = alpha - prune_eval, >= 0): the node searched with
  futility forced on and forced off there; futility is wrong when the on
  arm fails low and the off arm fails high.

Every candidate is sampled at the same known rate, so each row stands for N
decisions (a Horvitz-Thompson weight of N, the same for all rows: rates
need no weighting, totals are N times the counts).

Reported per technique and depth: candidates sampled, rows that fired, the
wrong rate by gap bin of 20 cp, the marginal wrong rate at the current
margin (the 20-cp bin holding it), and the think tank's fit (I1),
P(wrong | g) = (1 - pi) Phi((-g - mu) / sigma) + pi * exp(-g / tau) / 2, by
maximum likelihood on rows binned to 10 cp (Nelder-Mead, pure Python), with
the fitted rate at the margin. 95% intervals: a bootstrap over games, seed
20261109: 200 rounds for the margin rate, 50 for the fitted sigma (each of
those rounds refits; 50 keeps the pure-Python fits to minutes). `--csv` writes every row with
its game and weight for later fits (R14's ranges, R17, R35).

Declared readings (think tank I1; phase-c-synthesis.md §2.4), fixed before
the data were seen: the marginal wrong rate at the current margin falls at
least 3x from depth 1 to depth 5 (refuted if flat). It gives P(wrong | g,
d), the shape and ranges of the margins, never their Elo level. A cell with
fewer than 100 wrong events is marked thin (I1 asked about 1,200 per depth
to pin a 2% rate to +-20%).

    prune_ledger_fit.py REPLAY_DIR [--every 512] [--rounds 200] [--json OUT] [--csv OUT]
"""
import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path


def ledger_rows(records):
    """The ledger rows of a replay, each with its game, gap and wrong flag."""
    rows = []
    for record in records:
        for row in record.get('ledger') or []:
            out = dict(row)
            out['game'] = record['game']
            out['gap'] = row['excess'] if row['technique'] == 'rfp' else row['deficit']
            out['wrong'] = wrong_flag(row)
            rows.append(out)
    return rows


def wrong_flag(row):
    """1 if the decision the row describes would be (or was) a wrong prune."""
    if row['technique'] == 'rfp':
        return int(row['arm_minus_beta'] < 0)
    return int(row['on_minus_beta'] < 0 <= row['off_minus_beta'])


def weighted_rate_table(rows, technique, bin_width=20, every=1):
    """{depth: {'rows', 'fired', 'wrong', 'rate', 'weight', 'margin', 'bins': {low: [n, wrong]}}}."""
    table = {}
    for r in rows:
        if r['technique'] != technique:
            continue
        t = table.setdefault(r['depth'], {'rows': 0, 'fired': 0, 'wrong': 0, 'margin': r['margin'], 'bins': {}})
        t['rows'] += 1
        t['fired'] += r['fired']
        t['wrong'] += r['wrong']
        low = r['gap'] // bin_width * bin_width
        b = t['bins'].setdefault(low, [0, 0])
        b[0] += 1
        b[1] += r['wrong']
    for t in table.values():
        t['rate'] = t['wrong'] / t['rows'] if t['rows'] else 0.0
        t['weight'] = every * t['rows']  # the decisions the rows stand for
    return table


def marginal_rate_at_margin(entry, bin_width=20):
    """The wrong rate in the gap bin holding the margin: (rate, rows, wrong events)."""
    low = entry['margin'] // bin_width * bin_width
    n, wrong = entry['bins'].get(low, [0, 0])
    return (wrong / n if n else None), n, wrong


def normal_cdf(z):
    return 0.5 * math.erfc(-z / math.sqrt(2))


def probit_floor_probability(g, theta):
    """I1's P(wrong | g): theta = (mu, log sigma, logit pi, log tau)."""
    mu, log_sigma, logit_pi, log_tau = theta
    # The logistic of logit_pi, without overflow at either extreme.
    pi = 1 / (1 + math.exp(-logit_pi)) if logit_pi >= 0 else math.exp(logit_pi) / (1 + math.exp(logit_pi))
    p = (1 - pi) * normal_cdf((-g - mu) / math.exp(log_sigma)) + pi * 0.5 * math.exp(-g / math.exp(log_tau))
    return min(max(p, 1e-12), 1 - 1e-12)


def negative_log_likelihood(theta, bins):
    """Binned Bernoulli likelihood: bins = [(gap midpoint, rows, wrong)]."""
    if not all(math.isfinite(v) for v in theta) or abs(theta[1]) > 20 or abs(theta[2]) > 50 or abs(theta[3]) > 20:
        return float('inf')
    total = 0.0
    for g, n, k in bins:
        p = probit_floor_probability(g, theta)
        total -= k * math.log(p) + (n - k) * math.log(1 - p)
    return total


def nelder_mead_min(f, start, step=0.5, iterations=600, tolerance=1e-8):
    """Minimises f from `start` by the Nelder-Mead simplex method."""
    n = len(start)
    simplex = [list(start)] + [[v + (step if i == j else 0.0) for j, v in enumerate(start)] for i in range(n)]
    values = [f(p) for p in simplex]
    for _ in range(iterations):
        order = sorted(range(n + 1), key=lambda i: values[i])
        simplex = [simplex[i] for i in order]
        values = [values[i] for i in order]
        if abs(values[-1] - values[0]) <= tolerance * (abs(values[0]) + tolerance):
            break
        centroid = [sum(p[j] for p in simplex[:-1]) / n for j in range(n)]
        worst = simplex[-1]
        reflected = [c + (c - w) for c, w in zip(centroid, worst)]
        fr = f(reflected)
        if fr < values[0]:
            expanded = [c + 2 * (c - w) for c, w in zip(centroid, worst)]
            fe = f(expanded)
            simplex[-1], values[-1] = (expanded, fe) if fe < fr else (reflected, fr)
        elif fr < values[-2]:
            simplex[-1], values[-1] = reflected, fr
        else:
            contracted = [c + 0.5 * (w - c) for c, w in zip(centroid, worst)]
            fc = f(contracted)
            if fc < values[-1]:
                simplex[-1], values[-1] = contracted, fc
            else:
                best = simplex[0]
                simplex = [best] + [[b + 0.5 * (p - b) for b, p in zip(best, q)] for q in simplex[1:]]
                values = [values[0]] + [f(p) for p in simplex[1:]]
    i = min(range(n + 1), key=lambda i: values[i])
    return simplex[i], values[i]


def fit_probit_floor(rows, bin_width=10, start=None):
    """I1's model fitted to rows of one technique and depth: (theta, -log L)."""
    counts = {}
    for r in rows:
        low = r['gap'] // bin_width * bin_width
        c = counts.setdefault(low, [0, 0])
        c[0] += 1
        c[1] += r['wrong']
    bins = [(low + (bin_width - 1) / 2, n, k) for low, (n, k) in sorted(counts.items())]
    if start is None:
        start = (-50.0, math.log(60.0), -4.0, math.log(100.0))
    theta, value = nelder_mead_min(lambda t: negative_log_likelihood(t, bins), start)
    theta, value = nelder_mead_min(lambda t: negative_log_likelihood(t, bins), theta, step=0.1)
    return theta, value


def bootstrap_fit(rows, rounds, seed, statistic):
    """The 2.5% and 97.5% points of statistic(sample) over games resampled with replacement."""
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
        v = statistic(sample)
        if v is not None:
            values.append(v)
    if not values:
        return None
    values.sort()
    return values[int(0.025 * len(values))], values[max(int(0.975 * len(values)) - 1, 0)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('replay', type=Path)
    parser.add_argument('--every', type=int, default=512, help='the run\'s FORK_PRUNE_LEDGER rate (the row weight)')
    parser.add_argument('--rounds', type=int, default=200)
    parser.add_argument('--seed', type=int, default=20261109)
    parser.add_argument('--json', type=Path, default=None)
    parser.add_argument('--csv', type=Path, default=None)
    a = parser.parse_args(argv)

    records = []
    for f in sorted(a.replay.glob('game-*.jsonl')):
        records.extend(json.loads(line) for line in f.read_text(encoding='utf-8').splitlines())
    rows = ledger_rows(records)
    if a.csv and rows:
        names = sorted({k for r in rows for k in r})
        with open(a.csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=names + ['weight'])
            writer.writeheader()
            for r in rows:
                writer.writerow(dict(r, weight=a.every))
    result = {'searches': len(records), 'rows': len(rows), 'every': a.every, 'techniques': {}}
    for technique in ('rfp', 'futility'):
        table = weighted_rate_table(rows, technique, every=a.every)
        out = {}
        for depth in sorted(table):
            entry = table[depth]
            part = [r for r in rows if r['technique'] == technique and r['depth'] == depth]
            rate, n_margin, wrong_margin = marginal_rate_at_margin(entry)
            theta, nll = fit_probit_floor(part)

            def margin_rate(sample, margin=entry['margin']):
                low = margin // 20 * 20
                cell = [r for r in sample if low <= r['gap'] < low + 20]
                return sum(r['wrong'] for r in cell) / len(cell) if cell else None

            def fitted_sigma(sample, start=theta):
                return math.exp(fit_probit_floor(sample, start=start)[0][1])

            out[depth] = {
                'rows': entry['rows'], 'decisions': entry['weight'], 'fired': entry['fired'],
                'wrong': entry['wrong'], 'wrong_rate': entry['rate'], 'margin': entry['margin'],
                'margin_rate': rate, 'margin_rows': n_margin, 'margin_wrong': wrong_margin,
                'margin_rate_ci95': bootstrap_fit(part, a.rounds, a.seed, margin_rate),
                'thin': entry['wrong'] < 100,
                'fit': {'mu': theta[0], 'sigma': math.exp(theta[1]),
                        'pi': math.exp(min(theta[2], 0)) / (math.exp(min(theta[2], 0)) + math.exp(min(-theta[2], 0))),
                        'tau': math.exp(theta[3]), 'neg_log_likelihood': nll,
                        'rate_at_margin': probit_floor_probability(entry['margin'], theta)},
                'sigma_ci95': bootstrap_fit(part, min(a.rounds, 50), a.seed, fitted_sigma),
                'rate_by_gap_bin': {low: [n, k, k / n] for low, (n, k) in sorted(entry['bins'].items()) if n >= 50},
            }
            print(f'{technique} depth {depth}: {entry["rows"]} rows, {entry["fired"]} fired, wrong rate '
                  f'{entry["rate"]:.4f}, at the margin {rate} ({wrong_margin}/{n_margin})', flush=True)
        if 1 in out and 5 in out and out[1]['margin_rate'] and out[5]['margin_rate']:
            out['fall_d1_to_d5'] = out[1]['margin_rate'] / out[5]['margin_rate']
        result['techniques'][technique] = out
    text = json.dumps(result, indent=1)
    if a.json:
        a.json.write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
