# SPDX-License-Identifier: GPL-3.0-or-later
"""The LMR history term's measurement (tier 2, T16's history term; DESIGN.md,
"Search constants": LmrHistoryDivisor), on the method of the internal
iterative reduction's (tools/no_move_measure.py; owner, 2026-11-01, option B).

The term (owner, 2026-11-02: in the base reduction, not in idea 23's
evolvable slot): a late quiet move's reduction is the table's less its
ordering history score (the butterfly history plus the weighted reply and
follow tables, exactly as the move selector orders quiets) divided by
LmrHistoryDivisor, rounded toward zero, so a move with a good history is
reduced less and one with a bad history more.

Quality per node: on a fixed position set, each setting searches every
position at the same node budget from a fresh state, and is scored against
a much deeper label with the evolve loop's proxies (tools/evolve/proxies.py:
1 for the label's move less the capped score error / 1000, per position).
The settings are the term off and LmrHistoryDivisor at 3000, 4500, 6000,
9000, 12000, 18000 and 24000 (a geometric spread: the summed history lies
within about +/-35,000 at its limits and mostly far inside them), all in
one tuning build (FORK_TUNE: UseLmrHistory and LmrHistoryDivisor are UCI
options there).

Step 1 labels the evolve split of tools/evolve/positions.jsonl with the
current default engine (phase-4 at 33e7883: S512r2, IIR on, the term off),
`go nodes LABEL` from a fresh state (ucinewgame, Hash 64) with no options
set; labels with a mate score or |score| > 1500 cp are dropped. Step 2
searches every labeled position with every setting at two budgets, 250,000
and 2,500,000 nodes, Hash 16. Step 3 reports.

Selection rule, fixed before the data were seen (2026-11-02), the IIR
measurement's:
- a setting's fitness is its per-position score averaged over the
  positions and both budgets;
- the divisor is the one with the highest fitness; settings within 0.001
  of the best count as tied, and a tie goes to the largest divisor (the
  smaller adjustment);
- the chosen divisor goes to the SPRT whatever its margin over "off" (the
  SPRT decides adoption); each divisor's gain over "off" is reported with a
  paired bootstrap 95% interval over positions (both budgets summed per
  position), and the report says when no interval lies above zero.
Reported but not part of the rule: agreement and score error per budget,
the mean depth reached, and time to depth. The labels come from the
setting "off", so a small bias toward it is possible; it cannot favour one
divisor over another.

    lmr_history_measure.py label FORK OUT.jsonl [--nodes 25000000] [--jobs 2]
    lmr_history_measure.py sweep FORK LABELS.jsonl OUTDIR [--jobs 2]
    lmr_history_measure.py report LABELS.jsonl OUTDIR
"""
import argparse
import json
import math
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'evolve'))
import proxies  # noqa: E402

Settings = ['off', 3000, 4500, 6000, 9000, 12000, 18000, 24000]
Budgets = [250000, 2500000]
TieMargin = 0.001
LabelCap = 1500
BootstrapSeed = 20261102


class Engine(proxies.Engine):
    """proxies.Engine, keeping the nodes at which each depth finished."""

    def __init__(self, path, hash_mb=16):
        super().__init__(path, hash_mb)
        if os.name == 'nt':  # Windows children do not inherit the priority class
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(int(self.p._handle), 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS

    def configure(self, setting):
        if setting is None:  # the labels: the default engine, no options
            return
        on = setting != 'off'
        self.send(f'setoption name UseLmrHistory value {"true" if on else "false"}')
        if on:
            self.send(f'setoption name LmrHistoryDivisor value {setting}')

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


def run(fork, rows, nodes, setting, jobs, hash_mb, record=None):
    """Every row's search; `record(row, answer)`, if given, is called as each
    one finishes (from the worker threads)."""
    def part(chunk):
        engine = Engine(fork, hash_mb)
        try:
            engine.configure(setting)
            out = []
            for r in chunk:
                out.append(engine.search(r['fen'], nodes))
                if record:
                    record(r, out[-1])
            return out
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
    rows = proxies.load_positions(a.positions or os.path.join(repo, 'tools', 'evolve', 'positions.jsonl'), a.split)
    # Each answer is saved as it finishes (OUT.answers), so a stopped run
    # resumes where it was: every search starts from a fresh state, so the
    # answers do not depend on which run or job computed them.
    saved_path = a.out + '.answers'
    done = {}
    if os.path.exists(saved_path):
        with open(saved_path, 'rb') as f:
            data = f.read()
        data = data[:data.rfind(b'\n') + 1]  # a line cut off by a stop is dropped
        with open(saved_path, 'wb') as f:
            f.write(data)
        for line in data.decode('utf-8').splitlines():
            d = json.loads(line)
            done[d['id']] = d['answer']
    todo = [r for r in rows if r['id'] not in done]
    print(f'{len(done)} answers saved earlier, {len(todo)} to search', flush=True)
    lock = threading.Lock()
    with open(saved_path, 'a', encoding='utf-8') as saved:
        def record(r, s):
            with lock:
                saved.write(json.dumps({'id': r['id'], 'answer': s}) + '\n')
                saved.flush()
        for r, s in zip(todo, run(a.fork, todo, a.nodes, None, a.jobs, 64, record)):
            done[r['id']] = s
    answers = [done[r['id']] for r in rows]
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
    print(f'chosen divisor: {chosen} (fitness {fitness[chosen]:.4f}; best {best:.4f})')
    lows = [proxies.paired_interval(per_position[s], per_position['off'], BootstrapSeed)[1] for s in depths]
    if all(low <= 0 for low in lows):
        print('no divisor\'s gain interval lies above zero')


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
    p = sub.add_parser('label')
    p.add_argument('fork')
    p.add_argument('out')
    p.add_argument('--nodes', type=int, default=25000000)
    p.add_argument('--jobs', type=int, default=2)
    # Another position set in the same row form (tools/clock_positions.py's).
    p.add_argument('--positions', default=None)
    p.add_argument('--split', default='evolve')
    p = sub.add_parser('sweep')
    p.add_argument('fork')
    p.add_argument('labels')
    p.add_argument('outdir')
    p.add_argument('--jobs', type=int, default=2)
    p = sub.add_parser('report')
    p.add_argument('labels')
    p.add_argument('outdir')
    a = ap.parse_args()
    {'label': label, 'sweep': sweep, 'report': report}[a.cmd](a)


if __name__ == '__main__':
    main()
