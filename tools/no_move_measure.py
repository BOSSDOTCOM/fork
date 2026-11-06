# SPDX-License-Identifier: GPL-3.0-or-later
"""The internal-iterative-reduction measurement (tier 2, T26; DESIGN.md,
"Search constants": NoMoveReduceMinDepth).

Quality per node: on a fixed position set, each setting searches every
position at the same node budget from a fresh state, and is scored against
a much deeper label with the evolve loop's proxies (tools/evolve/proxies.py:
1 for the label's move less the capped score error / 1000, per position).
The settings are the reduction off and its minimum depth at 2, 3, 4, 5, 6,
7 and 8, all in one tuning build (FORK_TUNE: UseNoMoveReduction and
NoMoveReduceMinDepth are UCI options there).

Step 1 labels the evolve split of tools/evolve/positions.jsonl again with
the current engine (its committed labels came from an older evaluation, on
another score scale): `go nodes LABEL` from a fresh state (ucinewgame, Hash
64), the reduction off as in the default build; labels with a mate score or
|score| > 1500 cp are dropped. Step 2 searches every labeled position with
every setting at two budgets, 250,000 and 2,500,000 nodes (about one STC
move at 8+0.08 on this machine, and ten times that), Hash 16. Step 3 reports.

Selection rule, fixed before the data were seen (owner, 2026-11-01,
option B):
- a setting's fitness is its per-position score averaged over the
  positions and both budgets;
- the minimum depth is the one of 2-8 with the highest fitness; settings
  within 0.001 of the best count as tied, and a tie goes to the largest
  depth (fewer nodes reduced);
- the chosen depth goes to the SPRT whatever its margin over "off" (the
  SPRT decides adoption); each depth's gain over "off" is reported with a
  paired bootstrap 95% interval over positions (both budgets summed per
  position), and the report says when no interval lies above zero.
Reported but not part of the rule: agreement and score error per budget,
the mean depth reached, and time to depth (the geometric mean of the nodes
at which depth D finished, at the 2,500,000 budget, over the positions
where every setting finished D; D the deepest such depth reached in at
least 90% of the positions). The labels come from the setting "off", so a
small bias toward it is possible; it cannot favour one depth over another.

    no_move_measure.py label FORK OUT.jsonl [--nodes 25000000] [--jobs 10]
    no_move_measure.py sweep FORK LABELS.jsonl OUTDIR [--jobs 10]
    no_move_measure.py report LABELS.jsonl OUTDIR
"""
import argparse
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'evolve'))
import proxies  # noqa: E402

Settings = ['off', 2, 3, 4, 5, 6, 7, 8]
Budgets = [250000, 2500000]
TieMargin = 0.001
LabelCap = 1500
BootstrapSeed = 20261101


class Engine(proxies.Engine):
    """proxies.Engine, keeping the nodes at which each depth finished."""

    def configure(self, setting):
        on = setting != 'off'
        self.send(f'setoption name UseNoMoveReduction value {"true" if on else "false"}')
        if on:
            self.send(f'setoption name NoMoveReduceMinDepth value {setting}')

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


def run(fork, rows, nodes, setting, jobs, hash_mb):
    def part(chunk):
        engine = Engine(fork, hash_mb)
        try:
            engine.configure(setting)
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


def label(a):
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rows = proxies.load_positions(os.path.join(repo, 'tools', 'evolve', 'positions.jsonl'), 'evolve')
    answers = run(a.fork, rows, a.nodes, 'off', a.jobs, 64)
    kept = 0
    with open(a.out, 'w', encoding='utf-8') as f:
        for r, s in zip(rows, answers):
            if s['mate'] or s['score'] is None or abs(s['score']) > LabelCap:
                continue
            f.write(json.dumps({'id': r['id'], 'fen': r['fen'], 'bm': s['move'], 'ce': s['score'],
                                'depth': s['depth'], 'nodes': a.nodes}) + '\n')
            kept += 1
    print(f'{kept} of {len(rows)} positions labeled at {a.nodes} nodes')


def sweep(a):
    labels = proxies.load_positions(a.labels, None)
    os.makedirs(a.outdir, exist_ok=True)
    for budget in Budgets:
        for setting in Settings:
            path = os.path.join(a.outdir, f'{setting}-{budget}.jsonl')
            if os.path.exists(path):
                continue
            answers = run(a.fork, labels, budget, setting, a.jobs, 16)
            with open(path + '.part', 'w', encoding='utf-8') as f:
                for r, s in zip(labels, answers):
                    f.write(json.dumps({'id': r['id'], **s}) + '\n')
            os.replace(path + '.part', path)
            print(f'{setting} at {budget} nodes done', flush=True)


def load_answers(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def report(a):
    labels = proxies.load_positions(a.labels, None)
    data = {}
    for budget in Budgets:
        for setting in Settings:
            rows = load_answers(os.path.join(a.outdir, f'{setting}-{budget}.jsonl'))
            assert [r['id'] for r in rows] == [r['id'] for r in labels]
            answers = [proxies.Answer(r['move'], r['score'], r['depth']) for r in rows]
            data[setting, budget] = (proxies.measure(answers, labels), rows)
    n = len(labels)
    per_position = {s: [sum(data[s, b][0].per_position[i] for b in Budgets) for i in range(n)]
                    for s in Settings}
    fitness = {s: sum(per_position[s]) / (n * len(Budgets)) for s in Settings}
    print(f'{n} positions; fitness is the mean per-position score over both budgets')
    for s in Settings:
        cells = '  '.join(f'{b}: agree {data[s, b][0].agreement:.4f} err {data[s, b][0].score_error:.1f} '
                          f'depth {data[s, b][0].depth:.2f}' for b in Budgets)
        gain = '' if s == 'off' else ' gain {:+.4f} [{:+.4f}, {:+.4f}]'.format(
            *(x / len(Budgets) for x in proxies.paired_interval(per_position[s], per_position['off'],
                                                                 BootstrapSeed)))
        print(f'{s!s:>4}: fitness {fitness[s]:.4f}{gain}  {cells}')
    # Time to depth at the larger budget.
    big = Budgets[-1]
    finished = {s: [r['finished'] for r in data[s, big][1]] for s in Settings}
    depth = None
    for d in range(1, 64):
        common = [i for i in range(n) if all(str(d) in finished[s][i] for s in Settings)]
        if len(common) >= 0.9 * n:
            depth = d
    if depth is not None:
        common = [i for i in range(n) if all(str(depth) in finished[s][i] for s in Settings)]
        print(f'time to depth {depth} ({len(common)} positions), geometric mean of nodes:')
        for s in Settings:
            g = math.exp(sum(math.log(finished[s][i][str(depth)]) for i in common) / len(common))
            print(f'{s!s:>4}: {g:,.0f}')
    depths = [s for s in Settings if s != 'off']
    best = max(fitness[s] for s in depths)
    chosen = max(s for s in depths if fitness[s] >= best - TieMargin)
    print(f'chosen minimum depth: {chosen} (fitness {fitness[chosen]:.4f}; best {best:.4f})')
    lows = [proxies.paired_interval(per_position[s], per_position['off'], BootstrapSeed)[1] for s in depths]
    if all(low <= 0 for low in lows):
        print('no depth\'s gain interval lies above zero')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('label')
    p.add_argument('fork')
    p.add_argument('out')
    p.add_argument('--nodes', type=int, default=25000000)
    p.add_argument('--jobs', type=int, default=10)
    p = sub.add_parser('sweep')
    p.add_argument('fork')
    p.add_argument('labels')
    p.add_argument('outdir')
    p.add_argument('--jobs', type=int, default=10)
    p = sub.add_parser('report')
    p.add_argument('labels')
    p.add_argument('outdir')
    a = ap.parse_args()
    {'label': label, 'sweep': sweep, 'report': report}[a.cmd](a)


if __name__ == '__main__':
    main()
