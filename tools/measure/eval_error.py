# SPDX-License-Identifier: GPL-3.0-or-later
"""B1, the offline eval-error check of the three eval-margin pruning sites
(owner-approved 2026-11-22; input for the final retune's group G1a:
RfpMargin, FutilityOffset, FutilityGrowth, NullSurplusPerPly and their
depth limits).

Question: at reverse futility pruning (RFP), futility pruning and null-move
pruning, how far is the pruning eval (the static eval after the drift
tables and the TT refinement: exactly the value each site compares with its
margin) from the search result at that node, by the result's bound and by
depth, and how often does today's margin make the wrong call?

Method. A pruned node has no search result, so the result comes from the
decision ledger's side searches (DESIGN.md §5.7, X10; null rows added by B1
behind FORK_NULL_LEDGER): a stats build samples 1 in N of each site's
candidates by the position's key and searches the sampled node again with
that one site switched off there (futility also forced on), in a side search
the real search never sees (node count, limits, TT writes, histories,
counters and the tally restored; tests/test_search_stats.cpp). The real
search, and so the population of candidate nodes, is the play build's.

- RFP rows: every RFP condition but the margin, and pruning eval >= beta.
  Result: the node searched with RFP off there. Wrong prune: today's margin
  prunes (excess >= RfpMargin * depth) and the result fails low; missed
  prune: it does not prune and the result fails high.
- Futility rows: every condition but the margin, and pruning eval <= alpha.
  Result: the node searched with futility off there. Wrong prune: today's
  margin makes the node futile and the forced-on arm fails low while the off
  arm fails high (X10's rule); missed prune: not futile, and both arms fail
  low (pruning the quiets would have kept the result).
- Null rows: every null-move condition holds (the null search is tried).
  Result: the node searched with the null move off there. Wrong cut: the
  null search reached beta and the result fails low; missed cut: it did not
  and the result fails high.

The error is pruning eval minus the result, in cp. Every site runs only at
non-PV nodes, which Fork searches on a zero window, so a result is a lower
bound (fail high) or an upper bound (fail low), never exact (the counter
ledger_wide_windows checks it: 0). A fail-soft lower bound v means the true
value is at least v, so for "lower" rows the error is an upper bound on the
true error; for "upper" rows a lower bound. Rows whose arm (or null score)
is a mate or tablebase score are counted apart and left out of the error
statistics; arms are clamped to +-2,000 cp around beta by the engine.

Declared reading (fixed before the data were seen; the owner's rule,
DESIGN.md §5.2 Testing setup, 2026-11-12): an offline measurement only
informs the retune's RANGES. It never picks a value and never gates a test;
games (SPSA, SPRT) decide. The sweep tables show, per depth, the wrong-prune
rate among the prunes and the prune share at margins around today's; a
range is suggested to cover every margin whose rates stay near today's and
to extend wherever today's value sits at the edge of the measured trade.

    eval_error.py select POSITIONS.jsonl OUT.txt [--count 300] [--seed 20261122]
    eval_error.py run FORK OUTDIR [--fens FILE --depth 12] [--bench] [--every 16] [--hash 16]
    eval_error.py report OUTDIR [--every 16] [--json OUT]

`select` draws COUNT positions of the "evolve" split by
random.Random(SEED).sample, written as FENs in file order. `run` drives the
stats build (clang-stats) at below-normal priority with FORK_PRUNE_LEDGER and
FORK_NULL_LEDGER: `--bench` runs `fork bench` (stderr to OUTDIR/bench.err);
`--fens` searches each FEN from a cleared state (`ucinewgame`, Hash 16, one
thread, no tablebases) to `--depth` (stderr to OUTDIR/fens.err). `report`
reads every *.err file in OUTDIR.
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_lines  # noqa: E402

# Today's margins (src/tune/params.hpp at phase-4 3875ca9f).
CURRENT_RFP_MARGIN = 55
FUTILITY_OFFSET = 86
FUTILITY_GROWTH = 50
NULL_SURPLUS_PER_PLY = 301

QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)


def depth_bin(site, depth):
    """Depth bins: each depth for RFP and futility (1-6), wider bins for the null move (3 and up)."""
    if site != 'null':
        return str(depth)
    for low, high in ((3, 3), (4, 4), (5, 5), (6, 6), (7, 8), (9, 11)):
        if low <= depth <= high:
            return str(low) if low == high else f'{low}-{high}'
    return '12+'


def depth_bin_order(site):
    return [str(d) for d in range(1, 7)] if site != 'null' else ['3', '4', '5', '6', '7-8', '9-11', '12+']


def classify(row):
    """One ledger row -> (site, depth, error, bound, fired, wrong, missed, mate).

    error: pruning eval minus the result (cp); bound: 'lower' or 'upper' (the
    result's side of the zero window)."""
    site = row['technique']
    if site == 'rfp':
        result = row['arm_minus_beta']
        error = row['excess'] - result
        fired = row['fired'] == 1
        wrong = fired and result < 0
        missed = not fired and result >= 0
    elif site == 'futility':
        # alpha = beta - 1 on the zero window: pruning eval = beta - 1 - deficit.
        result = row['off_minus_beta']
        error = -1 - row['deficit'] - result
        fired = row['fired'] == 1
        on_low, off_low = row['on_minus_beta'] < 0, result < 0
        wrong = fired and on_low and not off_low
        missed = not fired and on_low and off_low
    elif site == 'null':
        result = row['arm_minus_beta']
        error = row['excess'] - result
        fired = row['fired'] == 1
        wrong = fired and result < 0
        missed = not fired and result >= 0
    else:
        raise ValueError(f'unknown site {site!r}')
    bound = 'lower' if result >= 0 else 'upper'
    return site, row['depth'], error, bound, fired, wrong, missed, row['arm_mate'] == 1


def read_rows(paths):
    rows = []
    for path in paths:
        with open(path, encoding='utf-8', errors='replace') as f:
            for number, line in enumerate(f, 1):
                if not line.startswith('prune_ledger '):
                    continue
                try:
                    rows.append(engine_lines.parse_ledger_line(line))
                except ValueError as e:
                    raise ValueError(f'{path}:{number}: {e}') from None
    return rows


def quantile(sorted_values, q):
    """Linear-interpolation quantile of a sorted list."""
    if not sorted_values:
        return float('nan')
    pos = q * (len(sorted_values) - 1)
    low = math.floor(pos)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


def summary(values):
    n = len(values)
    if n == 0:
        return {'count': 0}
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n > 1 else 0.0
    s = sorted(values)
    return {'count': n, 'mean': mean, 'sd': sd, 'quantiles': {str(q): quantile(s, q) for q in QUANTILES}}


def error_tables(rows):
    """{site: {bound: {depth_bin: summary}}} over rows without mate arms, plus 'all' bounds."""
    cells = {}
    for row in rows:
        site, depth, error, bound, _, _, _, mate = classify(row)
        if mate:
            continue
        b = depth_bin(site, depth)
        for key in (bound, 'all'):
            cells.setdefault(site, {}).setdefault(key, {}).setdefault(b, []).append(error)
    return {site: {bound: {b: summary(v) for b, v in by_bin.items()} for bound, by_bin in by_bound.items()}
            for site, by_bound in cells.items()}


def call_tables(rows):
    """{site: {depth_bin: counts}}: rows, mate rows, exact results (always 0), fired, wrong, missed."""
    out = {}
    for row in rows:
        site, depth, _, _, fired, wrong, missed, mate = classify(row)
        for b in (depth_bin(site, depth), 'all'):
            c = out.setdefault(site, {}).setdefault(b, {'rows': 0, 'mate': 0, 'fired': 0, 'wrong': 0, 'missed': 0})
            c['rows'] += 1
            c['mate'] += mate
            c['fired'] += fired
            c['wrong'] += wrong
            c['missed'] += missed
    return out


def rfp_sweep(rows, margins):
    """{depth: {M: (prune share of candidates, wrong rate among prunes, prunes)}} for margin M per ply."""
    by_depth = {}
    for row in rows:
        if row['technique'] == 'rfp':
            by_depth.setdefault(row['depth'], []).append((row['excess'], row['arm_minus_beta'] < 0))
    out = {}
    for depth, pairs in sorted(by_depth.items()):
        out[depth] = {}
        for m in margins:
            pruned = [low for excess, low in pairs if excess >= m * depth]
            out[depth][m] = (len(pruned) / len(pairs), sum(pruned) / len(pruned) if pruned else float('nan'),
                             len(pruned))
    return out


def futility_sweep(rows, points):
    """{depth: {(offset, growth): (futile share, wrong rate among futile rows, futile rows)}}."""
    by_depth = {}
    for row in rows:
        if row['technique'] == 'futility':
            wrong = row['on_minus_beta'] < 0 <= row['off_minus_beta']
            by_depth.setdefault(row['depth'], []).append((row['deficit'], wrong))
    out = {}
    for depth, pairs in sorted(by_depth.items()):
        out[depth] = {}
        for offset, growth in points:
            futile = [w for deficit, w in pairs if deficit >= offset + growth * depth]
            out[depth][(offset, growth)] = (len(futile) / len(pairs),
                                            sum(futile) / len(futile) if futile else float('nan'), len(futile))
    return out


def null_surplus_table(rows):
    """{depth_bin: {surplus band: [rows, fired, wrong]}}: the null move by its pruning-eval surplus over beta."""
    bands = ((0, 99), (100, 300), (301, 601), (602, 10 ** 9))
    names = ('0-99', '100-300', '301-601', '602+')
    out = {}
    for row in rows:
        if row['technique'] != 'null':
            continue
        band = next(n for (low, high), n in zip(bands, names) if low <= row['excess'] <= high)
        _, _, _, _, fired, wrong, _, _ = classify(row)
        c = out.setdefault(depth_bin('null', row['depth']), {}).setdefault(band, [0, 0, 0])
        c[0] += 1
        c[1] += fired
        c[2] += wrong
    return out


class Engine:
    def __init__(self, path, env, stderr):
        flags = getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
        self.process = subprocess.Popen([os.path.abspath(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=stderr, env=env, text=True, bufsize=1, creationflags=flags)
        if not flags and hasattr(os, 'setpriority'):
            os.setpriority(os.PRIO_PROCESS, self.process.pid, 10)

    def send(self, text):
        self.process.stdin.write(text + '\n')
        self.process.stdin.flush()

    def wait_for(self, prefix):
        lines = []
        for line in self.process.stdout:
            lines.append(line.rstrip('\n'))
            if line.startswith(prefix):
                return lines
        raise RuntimeError(f'engine ended before {prefix!r}')

    def close(self):
        self.send('quit')
        self.process.wait(timeout=60)


def run(a):
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['FORK_PRUNE_LEDGER'] = str(a.every)
    env['FORK_NULL_LEDGER'] = '1'
    env['FORK_STATS_REPORT'] = '1'
    started = time.time()
    if a.bench:
        flags = getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
        with open(out / 'bench.err', 'w', encoding='utf-8') as err:
            result = subprocess.run([os.path.abspath(a.fork), 'bench'], stdout=subprocess.PIPE, stderr=err, env=env,
                                    text=True, creationflags=flags, check=True)
        (out / 'bench.out').write_text(result.stdout, encoding='utf-8')
        print(result.stdout.strip())
    if a.fens:
        fens = [line.strip() for line in open(a.fens, encoding='utf-8') if line.strip()]
        with open(out / 'fens.err', 'w', encoding='utf-8') as err, open(out / 'fens.out', 'w',
                                                                          encoding='utf-8') as log:
            engine = Engine(a.fork, env, err)
            engine.send('uci')
            engine.wait_for('uciok')
            engine.send(f'setoption name Hash value {a.hash}')
            engine.send('setoption name Threads value 1')
            engine.send('setoption name CalibratedScore value false')  # raw scores (the display calibration off)
            for i, fen in enumerate(fens, 1):
                engine.send('ucinewgame')
                engine.send('isready')
                engine.wait_for('readyok')
                engine.send(f'position fen {fen}')
                engine.send(f'go depth {a.depth}')
                lines = engine.wait_for('bestmove')
                log.write(f'{i}\t{fen}\t{lines[-2] if len(lines) > 1 else ""}\t{lines[-1]}\n')
                log.flush()
                if i % 25 == 0:
                    print(f'{i}/{len(fens)} positions, {time.time() - started:.0f} s', flush=True)
            engine.close()
    print(f'wall {time.time() - started:.1f} s')


def select(a):
    rows = [json.loads(line) for line in open(a.positions, encoding='utf-8') if line.strip()]
    evolve = [i for i, r in enumerate(rows) if r['split'] == 'evolve']
    chosen = sorted(random.Random(a.seed).sample(evolve, a.count))
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        for i in chosen:
            f.write(rows[i]['fen'] + '\n')
    print(f'{len(chosen)} of {len(evolve)} evolve positions, seed {a.seed}: {a.out}')


def fmt(v, digits=1):
    return '-' if v is None or (isinstance(v, float) and math.isnan(v)) else f'{v:.{digits}f}'


def report(a):
    paths = sorted(Path(a.outdir).glob('*.err'))
    sources = {p.stem: read_rows([p]) for p in paths}
    result = {'every': a.every, 'sources': {}}
    for name, rows in list(sources.items()) + [('pooled', [r for rows in sources.values() for r in rows])]:
        if not rows:
            continue
        entry = {'rows': len(rows), 'errors': error_tables(rows), 'calls': call_tables(rows),
                 'null_surplus': null_surplus_table(rows)}
        rfp_margins = (30, 40, 45, 50, 55, 60, 65, 70, 80, 100)
        entry['rfp_sweep'] = {d: {m: v for m, v in t.items()} for d, t in rfp_sweep(rows, rfp_margins).items()}
        fut_points = ((86, 50), (60, 40), (70, 45), (100, 50), (86, 35), (86, 65), (100, 70), (50, 30), (120, 60))
        entry['futility_sweep'] = {d: {f'{o}+{g}d': v for (o, g), v in t.items()}
                                   for d, t in futility_sweep(rows, fut_points).items()}
        result['sources'][name] = entry
        print(f'\n## {name}: {len(rows)} ledger rows (1 in {a.every} candidates)\n')
        print('### Error (pruning eval - search result, cp), mate/TB arms excluded\n')
        print('| site | bound | depth | count | mean | SD | p5 | p25 | p50 | p75 | p95 |')
        print('|---|---|---|---|---|---|---|---|---|---|---|')
        for site in ('rfp', 'futility', 'null'):
            for bound in ('lower', 'upper', 'all'):
                for b in depth_bin_order(site):
                    s = entry['errors'].get(site, {}).get(bound, {}).get(b)
                    if not s or not s['count']:
                        continue
                    q = s['quantiles']
                    print(f'| {site} | {bound} | {b} | {s["count"]} | {fmt(s["mean"])} | {fmt(s["sd"])} | '
                          + ' | '.join(fmt(q[str(x)], 0) for x in QUANTILES) + ' |')
        print('\n### Calls at today\'s margins\n')
        print('| site | depth | rows | mate | fired | wrong | wrong/fired | missed | missed/unfired |')
        print('|---|---|---|---|---|---|---|---|---|')
        for site in ('rfp', 'futility', 'null'):
            for b in depth_bin_order(site) + ['all']:
                c = entry['calls'].get(site, {}).get(b)
                if not c:
                    continue
                unfired = c['rows'] - c['fired']
                print(f'| {site} | {b} | {c["rows"]} | {c["mate"]} | {c["fired"]} | {c["wrong"]} | '
                      f'{fmt(100 * c["wrong"] / c["fired"] if c["fired"] else float("nan"), 2)}% | {c["missed"]} | '
                      f'{fmt(100 * c["missed"] / unfired if unfired else float("nan"), 2)}% |')
        print('\n### RFP sweep: prune share of candidates / wrong rate among prunes, margin M per ply\n')
        print('| depth | ' + ' | '.join(f'M={m}' for m in rfp_margins) + ' |')
        print('|---|' + '---|' * len(rfp_margins))
        for d, t in entry['rfp_sweep'].items():
            print(f'| {d} | ' + ' | '.join(f'{fmt(100 * t[m][0])}% / {fmt(100 * t[m][1], 2)}%' for m in rfp_margins)
                  + ' |')
        print('\n### Futility sweep: futile share of candidates / wrong rate among futile rows, offset + growth*d\n')
        print('| depth | ' + ' | '.join(f'{o}+{g}d' for o, g in fut_points) + ' |')
        print('|---|' + '---|' * len(fut_points))
        for d, t in entry['futility_sweep'].items():
            print(f'| {d} | ' + ' | '.join(f'{fmt(100 * t[f"{o}+{g}d"][0])}% / {fmt(100 * t[f"{o}+{g}d"][1], 2)}%'
                                           for o, g in fut_points) + ' |')
        print('\n### Null move by surplus (pruning eval - beta): rows / cut share / wrong among cuts\n')
        print('| depth | 0-99 | 100-300 | 301-601 | 602+ |')
        print('|---|---|---|---|---|')
        for b in depth_bin_order('null'):
            t = entry['null_surplus'].get(b)
            if not t:
                continue
            cells = []
            for band in ('0-99', '100-300', '301-601', '602+'):
                n, fired, wrong = t.get(band, [0, 0, 0])
                cells.append(f'{n} / {fmt(100 * fired / n if n else float("nan"))}% / '
                             f'{fmt(100 * wrong / fired if fired else float("nan"), 2)}%')
            print(f'| {b} | ' + ' | '.join(cells) + ' |')
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=1, default=str)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    s = sub.add_parser('select')
    s.add_argument('positions')
    s.add_argument('out')
    s.add_argument('--count', type=int, default=300)
    s.add_argument('--seed', type=int, default=20261122)
    r = sub.add_parser('run')
    r.add_argument('fork')
    r.add_argument('outdir')
    r.add_argument('--fens')
    r.add_argument('--depth', type=int, default=12)
    r.add_argument('--bench', action='store_true')
    r.add_argument('--every', type=int, default=16)
    r.add_argument('--hash', type=int, default=16)
    p = sub.add_parser('report')
    p.add_argument('outdir')
    p.add_argument('--every', type=int, default=16)
    p.add_argument('--json')
    a = ap.parse_args()
    {'select': select, 'run': run, 'report': report}[a.command](a)


if __name__ == '__main__':
    main()
