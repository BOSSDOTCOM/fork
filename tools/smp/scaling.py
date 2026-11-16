# SPDX-License-Identifier: GPL-3.0-or-later

"""Lazy SMP scaling diagnostics (DESIGN.md §5.6 step 17a; owner, 2026-11-15).

Searches each bench position (src/search/search_bench.cpp's BenchFens: the
CPW perft suite and 40 positions from the Lichess CC0 database) to a fixed
depth at several thread counts and reports, per thread count, the time to
that depth, the nodes searched and the nodes per second, against one
thread. A diagnostic only: time to depth understates Lazy SMP's gain (its
trees widen), so games decide (docs/kb/lazy-smp.md §2.3, §4.3).

Each round runs every thread count once, in an order rotated per round (so
load drift favours none), each in a fresh engine process: Threads and Hash
set, then per position `ucinewgame`, `isready`, `position fen`, `go depth D`.
The time to depth is the engine's own `time` on its last info line at depth
D (the main thread's clock); wall time from `go` to `bestmove` is recorded
too. A thread count the engine reports it cannot run (an `info string
Threads ...` reply: fewer hardware threads) is skipped and named.

  python3 -I tools/smp/scaling.py ENGINE [--threads auto|1,2,4] [--depth 15] [--rounds 3]
      [--hash 64] [--positions N] [--label TEXT] [--json OUT]
  python3 -I tools/smp/scaling.py --merge RESULT.json ... [--json OUT]

--threads auto: 1, 2, 4, 8, ... up to this machine's CPUs (os.cpu_count()).
--merge: one table over several runners' results (each runner's ratios to
its own one-thread run; the median over runners).
"""

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH_SOURCE = HERE.parent.parent / 'src' / 'search' / 'search_bench.cpp'


def bench_fens(source=BENCH_SOURCE):
    """The FENs of BenchFens in search_bench.cpp, in order."""
    text = source.read_text(encoding='utf-8')
    block = text[text.index('BenchFens[] = {'):]
    block = block[:block.index('};')]
    return re.findall(r'^\s*"([^"]+)",', block, re.M)


def thread_counts(spec, cpus):
    if spec == 'auto':
        counts, n = [], 1
        while n <= max(cpus, 1):
            counts.append(n)
            n *= 2
        return counts
    counts = sorted({int(x) for x in spec.split(',')})
    if not counts or counts[0] < 1:
        raise SystemExit('scaling.py: --threads needs positive counts')
    return counts


INFO = re.compile(r'^info .*\bdepth (\d+) .*\bnodes (\d+) .*\btime (\d+)')


class Engine:
    def __init__(self, path):
        cmd = [str(Path(path).resolve())]
        if cmd[0].endswith('.py'):  # a fake engine (tools/smp/test_scaling.py)
            cmd.insert(0, sys.executable)
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def send(self, line):
        self.p.stdin.write(line + '\n')
        self.p.stdin.flush()

    def until(self, prefix):
        """Lines up to and including the first starting with `prefix`."""
        lines = []
        for line in self.p.stdout:
            line = line.rstrip('\r\n')
            lines.append(line)
            if line.startswith(prefix):
                return lines
        raise SystemExit(f'scaling.py: the engine exited before "{prefix}"')

    def quit(self):
        try:
            self.send('quit')
            self.p.wait(timeout=30)
        except Exception:  # noqa: BLE001 - a hung engine is killed
            self.p.kill()


def search(engine, fen, depth):
    engine.send('ucinewgame')
    engine.send('isready')
    engine.until('readyok')
    engine.send(f'position fen {fen}')
    t0 = time.perf_counter()
    engine.send(f'go depth {depth}')
    lines = engine.until('bestmove')
    wall_ms = (time.perf_counter() - t0) * 1000
    last = None
    for line in lines:
        m = INFO.match(line)
        if m and int(m.group(1)) == depth and ' pv ' in line:
            last = m
    if last is None:
        raise SystemExit(f'scaling.py: no info line at depth {depth} for {fen}')
    return {'nodes': int(last.group(2)), 'time_ms': int(last.group(3)), 'wall_ms': round(wall_ms, 1)}


def one_run(path, threads, depth, hash_mb, fens):
    """One fresh engine at `threads`: every position; None if it cannot run them."""
    e = Engine(path)
    try:
        e.send('uci')
        e.until('uciok')
        e.send('setoption name CalibratedScore value false')  # engines that still have it (score display only)
        e.send(f'setoption name Threads value {threads}')
        e.send(f'setoption name Hash value {hash_mb}')
        e.send('isready')
        replies = e.until('readyok')
        refused = [r for r in replies if r.startswith('info string Threads')]
        if refused:
            return {'threads': threads, 'skipped': refused[0]}
        rows = [search(e, fen, depth) for fen in fens]
    finally:
        e.quit()
    return {
        'threads': threads,
        'nodes': sum(r['nodes'] for r in rows),
        'time_ms': sum(r['time_ms'] for r in rows),
        'wall_ms': round(sum(r['wall_ms'] for r in rows), 1),
        'positions': rows,
    }


def summarise(runs, counts):
    """Per thread count: medians over rounds of the summed time and nodes, nps, and ratios to one thread."""
    table = {}
    for n in counts:
        done = [r for r in runs if r['threads'] == n and 'skipped' not in r]
        if not done:
            continue
        t = statistics.median(r['time_ms'] for r in done)
        nodes = statistics.median(r['nodes'] for r in done)
        table[n] = {'rounds': len(done), 'time_ms': t, 'nodes': nodes, 'nps': nodes * 1000 / max(t, 1)}
    if 1 in table:
        base = table[1]
        for row in table.values():
            row['ttd_speedup'] = base['time_ms'] / max(row['time_ms'], 1)
            row['nps_ratio'] = row['nps'] / max(base['nps'], 1)
            row['node_ratio'] = row['nodes'] / max(base['nodes'], 1)
    return table


def format_table(table, title):
    out = [title, '| threads | rounds | time to depth (ms, sum) | nodes (sum) | nps | '
           'time-to-depth speedup | nps ratio | node ratio |', '|---|---|---|---|---|---|---|---|']
    for n, r in sorted(table.items()):
        out.append(f"| {n} | {r['rounds']} | {r['time_ms']:.0f} | {r['nodes']:.0f} | {r['nps']:.0f} | "
                   f"{r.get('ttd_speedup', float('nan')):.2f} | {r.get('nps_ratio', float('nan')):.2f} | "
                   f"{r.get('node_ratio', float('nan')):.2f} |")
    return '\n'.join(out)


def merge(files):
    per_runner = [json.loads(Path(f).read_text(encoding='utf-8')) for f in files]
    counts = sorted({int(n) for r in per_runner for n in r['summary']})
    rows = []
    for n in counts:
        vals = [r['summary'][str(n)] for r in per_runner if str(n) in r['summary']]
        rows.append((n, len(vals), *(statistics.median(v[k] for v in vals if k in v) if any(k in v for v in vals)
                                     else float('nan') for k in ('ttd_speedup', 'nps_ratio', 'node_ratio'))))
    out = [f'Merged over {len(per_runner)} runner(s) (each against its own one-thread run; median over runners):',
           '| threads | runners | time-to-depth speedup | nps ratio | node ratio |', '|---|---|---|---|---|']
    out += [f'| {n} | {k} | {a:.2f} | {b:.2f} | {c:.2f} |' for n, k, a, b, c in rows]
    return '\n'.join(out), {str(n): {'runners': k, 'ttd_speedup': a, 'nps_ratio': b, 'node_ratio': c}
                            for n, k, a, b, c in rows}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('engine', nargs='?')
    ap.add_argument('--threads', default='auto')
    ap.add_argument('--depth', type=int, default=15)
    ap.add_argument('--rounds', type=int, default=3)
    ap.add_argument('--hash', type=int, default=64)
    ap.add_argument('--positions', type=int, default=0, help='the first N bench positions (0: all)')
    ap.add_argument('--label', default='')
    ap.add_argument('--json')
    ap.add_argument('--merge', nargs='+', metavar='RESULT')
    a = ap.parse_args(argv)
    if a.merge:
        text, data = merge(a.merge)
        print(text)
        if a.json:
            Path(a.json).write_text(json.dumps({'merged': data}, indent=1), encoding='utf-8')
        return 0
    if not a.engine:
        ap.error('ENGINE is required (or --merge)')
    if a.depth < 1 or a.rounds < 1:
        ap.error('--depth and --rounds must be at least 1')
    fens = bench_fens()
    if a.positions:
        fens = fens[:a.positions]
    cpus = os.cpu_count() or 1
    counts = thread_counts(a.threads, cpus)
    runs = []
    for k in range(a.rounds):
        order = counts[k % len(counts):] + counts[:k % len(counts)]  # rotated per round
        for n in order:
            r = one_run(a.engine, n, a.depth, a.hash, fens)
            r['round'] = k
            runs.append(r)
            note = r.get('skipped') or f"{r['time_ms']} ms, {r['nodes']} nodes"
            print(f'round {k + 1}, {n} thread(s): {note}', flush=True)
    table = summarise(runs, counts)
    skipped = sorted({r['skipped'] for r in runs if 'skipped' in r})
    title = (f"{a.label + ': ' if a.label else ''}{len(fens)} bench positions to depth {a.depth}, Hash {a.hash} MB, "
             f'{a.rounds} round(s), {cpus} CPUs')
    print(format_table(table, title))
    for s in skipped:
        print(f'skipped: {s}')
    if a.json:
        Path(a.json).write_text(json.dumps({'label': a.label, 'cpus': cpus, 'depth': a.depth, 'hash': a.hash,
                                            'positions': len(fens), 'rounds': a.rounds, 'skipped': skipped,
                                            'summary': {str(n): r for n, r in table.items()}, 'runs': runs},
                                           indent=1), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
