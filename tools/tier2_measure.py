# SPDX-License-Identifier: GPL-3.0-or-later
"""Quality-per-node measurements for tier 2's placeholder constants (owner,
2026-11-02: each is chosen by a measurement with a rule declared before its
runs, on a grid spanning a wide range not centered on the placeholder; owner,
2026-11-05: the queue of the improving flag's RFP use, ProbCut and the threat
set). The method is the LMR history term's and the internal iterative
reduction's (tools/lmr_history_measure.py on tier2/lmr-history,
tools/no_move_measure.py): node-limited searches from a fresh state, scored
against much deeper labels with the evolve loop's proxies
(tools/evolve/proxies.py: per position, 1 for the label's move less the
capped score error / 1000).

Each measurement is a spec, tools/tier2_measure/<name>.json, written and
committed before its runs: its settings (each a set of UCI options for one
tuning build, FORK_TUNE, where switches and constants are options), its
budgets, an optional screening stage and its tie order. The labels are a
file of the LMR measurement's form (the 25 M-node labels of the evolve
positions by the default engine; no mate, |score| <= 1500 cp), reused.

The rule, the same for every spec (fixed 2026-11-05, before any data):
- a setting's fitness is its per-position score averaged over the labeled
  positions and the budgets it was searched at;
- with a screening stage: every setting is searched at the screening budget
  only, and the SCREEN_KEEP settings with the highest screening fitness
  (ties broken by the tie order) go on to every budget with "off";
- the chosen setting is the one with the highest fitness over every budget;
  settings within TIE_MARGIN of the best count as tied, and a tie goes to
  the setting earliest in the spec's tie order;
- the chosen setting goes to the SPRT whatever its margin over "off" (the
  SPRT decides adoption); each setting's gain over "off" is reported with a
  paired bootstrap 95% interval over positions, and the report says when no
  interval lies above zero, or when the chosen setting is at an edge of its
  grid (the owner decides then whether the grid is extended, as for the
  pawn drift table).
Reported but not part of the rule: agreement, score error and mean depth per
budget, and time to depth at the largest budget.

    tier2_measure.py sweep SPEC FORK LABELS OUTDIR [--jobs 2]
    tier2_measure.py report SPEC LABELS OUTDIR
"""
import argparse
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'evolve'))
import proxies  # noqa: E402

TieMargin = 0.001
BootstrapSeed = 20261105


def load_spec(path):
    with open(path, encoding='utf-8') as f:
        spec = json.load(f)
    ids = [s['id'] for s in spec['settings']]
    assert ids[0] == 'off' and len(set(ids)) == len(ids), 'settings: "off" first, ids unique'
    assert sorted(spec['tie_order']) == sorted(ids[1:]), 'the tie order ranks every setting but "off"'
    return spec


class Engine(proxies.Engine):
    """proxies.Engine with options per setting, keeping the nodes at which each depth finished."""

    def __init__(self, path, hash_mb=16):
        super().__init__(path, hash_mb)
        if os.name == 'nt':  # Windows children do not inherit the priority class
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(int(self.p._handle), 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS

    def configure(self, options):
        for name, value in options.items():
            self.send(f'setoption name {name} value {str(value).lower() if isinstance(value, bool) else value}')
        self.send('isready')
        self.until('readyok')

    def search(self, fen, nodes):
        self.send('ucinewgame')
        self.send('isready')
        self.until('readyok')
        self.send(f'position fen {fen}')
        self.send(f'go nodes {nodes}')
        lines = self.until('bestmove')
        move, score, mate, depth, finished = lines[-1].split()[1], None, False, 0, {}
        for line in lines:
            t = line.split()
            if t[:1] != ['info'] or 'score' not in t or 'lowerbound' in t or 'upperbound' in t:
                continue
            i = t.index('score')
            score, mate = (int(t[i + 2]), False) if t[i + 1] == 'cp' else (None, True)
            if 'depth' in t:
                depth = int(t[t.index('depth') + 1])
                if 'nodes' in t:
                    finished[depth] = int(t[t.index('nodes') + 1])
        return {'move': move, 'score': score, 'mate': mate, 'depth': depth, 'finished': finished}


def run(fork, rows, nodes, options, jobs, hash_mb=16):
    def part(chunk):
        engine = Engine(fork, hash_mb)
        try:
            engine.configure(options)
            return [engine.search(r['fen'], nodes) for r in chunk]
        finally:
            engine.close()
    jobs = max(1, min(jobs, len(rows)))
    chunks = [rows[k::jobs] for k in range(jobs)]
    with ThreadPoolExecutor(jobs) as pool:
        results = list(pool.map(part, chunks))
    out = [None] * len(rows)
    for k, chunk in enumerate(results):
        out[k::jobs] = chunk
    return out


def cell_path(outdir, sid, budget):
    return os.path.join(outdir, f'{sid}-{budget}.jsonl')


def ensure(spec, a, labels, sid, budget):
    """Searches one setting at one budget unless its file exists (a stopped sweep resumes per cell)."""
    path = cell_path(a.outdir, sid, budget)
    if os.path.exists(path):
        return
    options = next(s['options'] for s in spec['settings'] if s['id'] == sid)
    answers = run(a.fork, labels, budget, options, a.jobs)
    with open(path + '.part', 'w', encoding='utf-8') as f:
        for r, s in zip(labels, answers):
            f.write(json.dumps({'id': r['id'], **s}) + '\n')
    os.replace(path + '.part', path)
    print(f'{sid} at {budget} nodes done', flush=True)


def load_cell(outdir, sid, budget, labels):
    with open(cell_path(outdir, sid, budget), encoding='utf-8') as f:
        rows = [json.loads(line) for line in f if line.strip()]
    assert [r['id'] for r in rows] == [r['id'] for r in labels]
    return proxies.measure([proxies.Answer(r['move'], r['score'], r['depth']) for r in rows], labels), rows


def finalists(spec, labels, outdir):
    """The settings searched at every budget: all of them, or after screening the best SCREEN_KEEP."""
    ids = [s['id'] for s in spec['settings']]
    screen = spec.get('screen')
    if not screen:
        return ids
    fit = {sid: load_cell(outdir, sid, screen['budget'], labels)[0] for sid in ids}
    rank = {sid: k for k, sid in enumerate(spec['tie_order'])}
    ordered = sorted(ids[1:], key=lambda s: (-sum(fit[s].per_position) / len(labels), rank[s]))
    return ['off'] + ordered[:screen['keep']]


def sweep(a):
    spec = load_spec(a.spec)
    labels = proxies.load_positions(a.labels, None)
    os.makedirs(a.outdir, exist_ok=True)
    screen = spec.get('screen')
    if screen:
        for s in spec['settings']:
            ensure(spec, a, labels, s['id'], screen['budget'])
    for sid in finalists(spec, labels, a.outdir):
        for budget in spec['budgets']:
            ensure(spec, a, labels, sid, budget)


def report(a):
    spec = load_spec(a.spec)
    labels = proxies.load_positions(a.labels, None)
    n, budgets = len(labels), spec['budgets']
    screen = spec.get('screen')
    if screen:
        print(f'screening at {screen["budget"]} nodes, fitness (the best {screen["keep"]} go on):')
        for s in spec['settings']:
            m, _ = load_cell(a.outdir, s['id'], screen['budget'], labels)
            print(f'  {s["id"]:>16}: {sum(m.per_position) / n:.4f}')
    final = finalists(spec, labels, a.outdir)
    data = {(sid, b): load_cell(a.outdir, sid, b, labels) for sid in final for b in budgets}
    per = {sid: [sum(data[sid, b][0].per_position[i] for b in budgets) for i in range(n)] for sid in final}
    fitness = {sid: sum(per[sid]) / (n * len(budgets)) for sid in final}
    print(f'{n} positions; fitness is the mean per-position score over the budgets {budgets}')
    for sid in final:
        cells = '  '.join(f'{b}: agree {data[sid, b][0].agreement:.4f} err {data[sid, b][0].score_error:.1f} '
                          f'depth {data[sid, b][0].depth:.2f}' for b in budgets)
        gain = '' if sid == 'off' else ' gain {:+.4f} [{:+.4f}, {:+.4f}]'.format(
            *(x / len(budgets) for x in proxies.paired_interval(per[sid], per['off'], BootstrapSeed)))
        print(f'{sid:>16}: fitness {fitness[sid]:.4f}{gain}  {cells}')
    big = budgets[-1]
    finished = {sid: [r['finished'] for r in data[sid, big][1]] for sid in final}
    depth = None
    for d in range(1, 64):
        if sum(all(str(d) in finished[s][i] for s in final) for i in range(n)) >= 0.9 * n:
            depth = d
    if depth is not None:
        common = [i for i in range(n) if all(str(depth) in finished[s][i] for s in final)]
        print(f'time to depth {depth} ({len(common)} positions), geometric mean of nodes:')
        for sid in final:
            g = math.exp(sum(math.log(finished[sid][i][str(depth)]) for i in common) / len(common))
            print(f'{sid:>16}: {g:,.0f}')
    candidates = [s for s in final if s != 'off']
    best = max(fitness[s] for s in candidates)
    tied = [s for s in candidates if fitness[s] >= best - TieMargin]
    chosen = min(tied, key=spec['tie_order'].index)
    print(f'chosen: {chosen} (fitness {fitness[chosen]:.4f}; best {best:.4f}; tied: {", ".join(tied)})')
    if all(proxies.paired_interval(per[s], per['off'], BootstrapSeed)[1] <= 0 for s in candidates):
        print('no setting\'s gain interval lies above zero')
    for name, values in spec.get('grid', {}).items():
        v = next(s for s in spec['settings'] if s['id'] == chosen)['options'].get(name)
        if v is not None and v in (min(values), max(values)):
            print(f'{name} {v} is at an edge of its grid {values}')


def lower_priority():
    """Below normal priority on Windows (the engines inherit it): data generation comes first."""
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.windll.kernel32
        kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS


def main():
    lower_priority()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sweep')
    for arg in ('spec', 'fork', 'labels', 'outdir'):
        p.add_argument(arg)
    p.add_argument('--jobs', type=int, default=2)
    p = sub.add_parser('report')
    for arg in ('spec', 'labels', 'outdir'):
        p.add_argument(arg)
    a = ap.parse_args()
    {'sweep': sweep, 'report': report}[a.cmd](a)


if __name__ == '__main__':
    main()
