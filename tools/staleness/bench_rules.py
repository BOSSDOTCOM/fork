# SPDX-License-Identifier: GPL-3.0-or-later
"""The staleness audit's bench-based re-runs (coordinator's order of
2026-11-12): the constants DESIGN.md's "Search constants" table says were
measured on the bench, measured again on the current default net and search
by the rule that table records.

- aspiration: the 46 bench positions (src/search/search_bench.cpp) searched
  to depth 14 from a cleared state with UseAspiration off; per depth, the
  p90 of |score(d) - score(d - 1)| (the last exact score of each iteration).
  AspirationHalfWidth's rule: the p90 of the changes from depth 5 on (the
  bound that nine iterations in ten stay inside); AspirationMinDepth's: the
  depth from which the per-depth p90 has settled (reported per depth, read
  as recorded: "p90 16 cp at depths 2-4 and settles at 9-13 cp from depth 5").
- growth: the same positions to depth 14 with the default engine; the
  cumulative nodes at each finished iteration, the factor n(d) / n(d - 1) at
  depths 8-14: median, p75, p90 (IterationGrowthThirds: the median in
  thirds; ForcedMoveFraction: the median to the 4th power, rounded).
- weights: `bench` (FORK_SEARCH_STATS and FORK_TUNE build) with one weight
  set and the others at their defaults. ReplyWeight and FollowWeight: the
  mean index of the cutting quiet over the quiet cutoffs at depths 1-6
  (non-PV, out of check; the stats' histogram), lowest wins, ties to the
  smaller tree; TakeWeight: the mean cutoff index over all cutoffs. Grids as
  recorded: 0 (the table's term off), 1, 2, 4, 6, 8 for the two pair tables,
  0, 1, 2, 4, 8, 16 for the take history. Also prints the default bench's
  first-move cutoff share (LmrMinMove's recorded 87.8%).

    bench_rules.py aspiration FORK OUT.json [--jobs 2]
    bench_rules.py growth FORK OUT.json [--jobs 2]
    bench_rules.py weights STATS_FORK OUT.json
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
RuleDepthRow = 14


def bench_fens():
    text = open(os.path.join(REPO, 'src', 'search', 'search_bench.cpp'), encoding='utf-8').read()
    body = text[text.index('BenchFens'):]
    body = body[:body.index('};')]
    fens = re.findall(r'^\s*"([^"]+)",', body, re.M)
    assert len(fens) == 46, len(fens)
    return fens


def below_normal(p):
    if os.name == 'nt':
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(int(p._handle), 0x4000)


def search(fork, fen, options):
    p = subprocess.Popen([fork], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True)
    below_normal(p)
    cmds = ['uci', 'setoption name Hash value 16'] + [f'setoption name {k} value {v}' for k, v in options.items()]
    cmds += ['ucinewgame', 'isready', f'position fen {fen}', f'go depth {RuleDepthRow}']
    p.stdin.write('\n'.join(cmds) + '\n')
    p.stdin.flush()
    per = {}
    for line in p.stdout:
        t = line.split()
        if t[:1] == ['bestmove']:
            break
        if t[:1] != ['info'] or 'depth' not in t or 'score' not in t:
            continue
        if 'lowerbound' in t or 'upperbound' in t:
            continue
        d = int(t[t.index('depth') + 1])
        i = t.index('score')
        score = int(t[i + 2]) if t[i + 1] == 'cp' else None
        nodes = int(t[t.index('nodes') + 1]) if 'nodes' in t else None
        per[d] = {'score': score, 'nodes': nodes}
    p.stdin.write('quit\n')
    p.stdin.flush()
    p.wait()
    return per


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = max(0, min(len(xs) - 1, int(-(-q * len(xs) // 1)) - 1))  # nearest-rank
    return xs[k]


def run_all(fork, options, jobs):
    fens = bench_fens()
    with ThreadPoolExecutor(jobs) as pool:
        return list(pool.map(lambda f: search(fork, f, options), fens))


def aspiration(a):
    res = run_all(a.fork, {'UseAspiration': 'false'}, a.jobs)
    by_depth = {}
    for per in res:
        for d in range(2, RuleDepthRow + 1):
            if d in per and d - 1 in per and per[d]['score'] is not None and per[d - 1]['score'] is not None:
                by_depth.setdefault(d, []).append(abs(per[d]['score'] - per[d - 1]['score']))
    rows = {d: {'n': len(v), 'p90': pct(v, 0.9), 'median': statistics.median(v)} for d, v in sorted(by_depth.items())}
    from5 = [x for d, v in by_depth.items() if d >= 5 for x in v]
    out = {'per_depth': rows, 'p90_from_depth5': pct(from5, 0.9), 'n_from_depth5': len(from5),
           'share_within_12_from_depth5': sum(x <= 12 for x in from5) / len(from5),
           'p90_depths2_4': pct([x for d, v in by_depth.items() if d < 5 for x in v], 0.9)}
    for d, r in rows.items():
        print(f'depth {d:2}: n {r["n"]:2}  p90 {r["p90"]:4}  median {r["median"]}')
    print(f'p90 from depth 5: {out["p90_from_depth5"]} cp ({out["n_from_depth5"]} changes); '
          f'share within 12 cp {out["share_within_12_from_depth5"]:.3f}; p90 at depths 2-4 {out["p90_depths2_4"]}')
    json.dump(out, open(a.out, 'w'), indent=1)


def growth(a):
    res = run_all(a.fork, {}, a.jobs)
    f = []
    for per in res:
        for d in range(8, RuleDepthRow + 1):
            if d in per and d - 1 in per and per[d]['nodes'] and per[d - 1]['nodes']:
                f.append(per[d]['nodes'] / per[d - 1]['nodes'])
    med = statistics.median(f)
    out = {'n': len(f), 'median': med, 'p75': pct(f, 0.75), 'p90': pct(f, 0.9), 'thirds': round(med * 3),
           'forced_fraction': round(med ** 4)}
    print(json.dumps(out))
    json.dump(out, open(a.out, 'w'), indent=1)


def bench_stats(fork, options):
    p = subprocess.Popen([fork], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    below_normal(p)
    cmds = ['uci'] + [f'setoption name {k} value {v}' for k, v in options.items()] + ['isready', 'bench', 'quit']
    out, err = p.communicate('\n'.join(cmds) + '\n')
    nodes = int(re.search(r'info string nodes (\d+)', out)[1])
    m = re.search(r'stats: (\d+) beta cutoffs, ([\d.]+)% on the first move, mean cutoff index ([\d.]+)', err)
    hist = {int(d): list(map(int, h.split())) for d, h in
            re.findall(r'stats: quiet cutoffs at depth (\d+) by quiet index:([\d ]+)', err)}
    qn = sum(c for d in range(1, 7) for c in hist[d])
    qs = sum(i * c for d in range(1, 7) for i, c in enumerate(hist[d]))
    return {'nodes': nodes, 'cutoffs': int(m[1]), 'first_move_pct': float(m[2]), 'mean_cutoff_index': float(m[3]),
            'quiet_cutoffs': qn, 'mean_quiet_index': qs / qn}


def weights(a):
    out = {'default': bench_stats(a.fork, {})}
    print('default', out['default'], flush=True)
    for name, grid, key in (('ReplyWeight', [0, 1, 2, 4, 6, 8], 'mean_quiet_index'),
                            ('FollowWeight', [0, 1, 2, 4, 6, 8], 'mean_quiet_index'),
                            ('TakeWeight', [0, 1, 2, 4, 8, 16], 'mean_cutoff_index')):
        rows = {}
        for v in grid:
            rows[v] = bench_stats(a.fork, {name: v})
            print(name, v, rows[v], flush=True)
        best = min(grid, key=lambda v: (round(rows[v][key], 4), rows[v]['nodes']))
        out[name] = {'metric': key, 'rows': rows, 'chosen': best}
        print(f'{name}: chosen {best} by {key}', flush=True)
    json.dump(out, open(a.out, 'w'), indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['aspiration', 'growth', 'weights'])
    ap.add_argument('fork')
    ap.add_argument('out')
    ap.add_argument('--jobs', type=int, default=2)
    a = ap.parse_args()
    {'aspiration': aspiration, 'growth': growth, 'weights': weights}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
