# SPDX-License-Identifier: GPL-3.0-or-later
"""The singular-extension measurement (tier 2; DESIGN.md, "Search constants").

Fork's own data for the singular test's constants. Step 1 collects nodes
where a singular test could run: a stats build (FORK_SEARCH_STATS) prints
them when FORK_SINGULAR_PROBE is set (src/search/searcher.cpp), here while it
searches sample positions to a fixed depth. Step 2 takes an equal random
sample per remaining depth and, in a normal build, searches each node again
from scratch (ucinewgame, one thread, Hash 16) with `go depth K searchmoves`:
the TT move alone and every other legal move, at half depth (K = d // 2)
and at the node's depth (K = d). Step 3 reports, per depth and per entry
depth deficit (d minus the TT entry's depth), how often a test with margin
M cp per ply (alternatives' half-depth score below S - M * d, S the TT
score) flags the TT move, and how often a flagged move is still strictly
the best move at full depth (the TT move's full-depth score above every
alternative's).

Selection rules, fixed before the data were seen (amended once, before the
second run: the first run's 60 samples per depth left most cells with fewer
than 20 flagged samples, which the first rules skipped, so a margin passed
without evidence; a cell now needs 20 flagged samples to count at all):
- a cell (a depth, or a deficit group) passes when it has at least 20
  flagged samples and at least 90% of them are still best at full depth;
- the margin per ply is the smallest M (whole cp) at which every depth from
  6 to 12 passes (depths below 6 are left out of this choice: their
  half-depth search is 2 plies or fewer);
- the minimum depth is the smallest depth from which every depth up to 12
  passes at that margin;
- the entry slack is the largest deficit K such that every deficit group up
  to K passes (pooled over depths from the minimum depth up).

    singular_measure.py collect STATS_FORK POSITIONS.jsonl OUT.txt [--count 60] [--depth 12]
    singular_measure.py search FORK PROBES.txt OUT.jsonl [--per-depth 60] [--seed 20261031]
                               [--pv-strata] [--min-depth D] [--max-depth D]
    singular_measure.py report OUT.jsonl [--c6]

The engine survey's C6 (2026-11-12): the probe lines gained two fields, the
TT entry's PV flag (was_pv) and the TT move's history (Searcher::
entry_move_history); --pv-strata samples --per-depth nodes per depth for
each value of was_pv. `report --c6` adds two analyses, with rules declared
before the data were seen (coordinator's brief of 2026-11-12, recorded in
DESIGN.md's rows):
- C6a, the TT-PV singular margin: rule 1 above applied to the was_pv = 1
  samples alone (and, for the record, to was_pv = 0) gives the natural
  value; the retry value is the smallest M at which every was_pv = 1 depth
  cell from 6 to 12 has at least 20 flagged samples and at least 95% of them
  still best, or the natural value plus 2 if that is the same or none.
  If the natural value equals the current margin (6), C6a has no candidate.
- C6b, the history-shifted bar: at the current margin (6 cp per ply), the
  bar S - 6 d - h / k (h the TT move's history) for k in
  {-400, -200, -100, -50, 50, 100, 200, 400}; a k passes when every depth
  cell from 6 to 12 (all samples) has at least 20 flagged samples and at
  least 90% of them still best; the natural value is the passing k that
  flags the most samples at depths 6-12, ties to the larger |k|, and only if
  it flags more than the unshifted bar does; the retry value is the passing
  k with the next most flagged samples.
"""
import argparse
import json
import os
import random
import subprocess
import sys
from collections import defaultdict

import chess


class Engine:
    def __init__(self, path, env=None, err=subprocess.DEVNULL):
        self.p = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
                                  text=True, bufsize=1, env=env)
        self.send('uci')
        self.wait('uciok')
        self.send('setoption name Threads value 1')
        self.send('setoption name Hash value 16')

    def send(self, line):
        self.p.stdin.write(line + '\n')
        self.p.stdin.flush()

    def wait(self, token):
        lines = []
        while True:
            line = self.p.stdout.readline()
            if not line:
                sys.exit('engine exited')
            lines.append(line.rstrip('\n'))
            if line.startswith(token):
                return lines

    def search(self, fen, depth, moves):
        """The last exact score (cp) at `depth`, or None for a mate score."""
        self.send('ucinewgame')
        self.send(f'position fen {fen}')
        self.send(f'go depth {depth} searchmoves {" ".join(moves)}')
        score = 'missing'
        for line in self.wait('bestmove'):
            t = line.split()
            if not t or t[0] != 'info' or 'score' not in t or 'depth' not in t:
                continue
            if int(t[t.index('depth') + 1]) != depth or 'lowerbound' in t or 'upperbound' in t:
                continue
            i = t.index('score')
            score = int(t[i + 2]) if t[i + 1] == 'cp' else None
        if score == 'missing':
            sys.exit(f'no exact score at depth {depth}: {fen} {moves}')
        return score

    def close(self):
        self.send('quit')
        self.p.wait()


def collect(a):
    rows = [json.loads(line) for line in open(a.positions)]
    step = max(1, len(rows) // a.count)
    env = dict(os.environ, FORK_SINGULAR_PROBE='1')
    with open(a.out, 'w', newline='\n') as out:
        for row in rows[::step][:a.count]:
            with open(a.out + '.err', 'w') as err:
                e = Engine(a.fork, env, err)
                e.send(f'position fen {row["fen"]}')
                e.send(f'go depth {a.depth}')
                e.wait('bestmove')
                e.close()
            n = 0
            for line in open(a.out + '.err'):
                if line.startswith('singular_probe '):
                    out.write(line[len('singular_probe '):])
                    n += 1
            print(f'{row["id"]}: {n} candidates', flush=True)


def search(a):
    by_depth = defaultdict(list)
    for line in open(a.probes):
        f = line.rstrip('\n').split('|')
        fen, depth, move, score, bound, entry_depth, on_pv = f[:7]
        row = {'fen': fen, 'depth': int(depth), 'move': move, 'score': int(score), 'bound': int(bound),
               'entry_depth': int(entry_depth), 'on_pv': int(on_pv)}
        if len(f) >= 9:  # C6's fields
            row['was_pv'], row['hist'] = int(f[7]), int(f[8])
        if a.min_depth <= row['depth'] <= a.max_depth:
            key = (row['depth'], row.get('was_pv', 0)) if a.pv_strata else (row['depth'], 0)
            by_depth[key].append(row)
    rng = random.Random(a.seed)
    e = Engine(a.fork)
    done = 0
    with open(a.out, 'w', newline='\n') as out:
        for key in sorted(by_depth):
            depth = key[0]
            pool = by_depth[key]
            rng.shuffle(pool)
            taken = 0
            for s in pool:
                if taken == a.per_depth:
                    break
                board = chess.Board(s['fen'])
                legal = [m.uci() for m in board.legal_moves]
                if s['move'] not in legal or len(legal) < 2:
                    continue
                others = [m for m in legal if m != s['move']]
                half = depth // 2
                s['tt_half'] = e.search(s['fen'], half, [s['move']])
                s['alt_half'] = e.search(s['fen'], half, others)
                s['tt_full'] = e.search(s['fen'], depth, [s['move']])
                s['alt_full'] = e.search(s['fen'], depth, others)
                if None in (s['tt_half'], s['alt_half'], s['tt_full'], s['alt_full']):
                    continue  # a mate score: the test skips mate scores anyway
                out.write(json.dumps(s) + '\n')
                out.flush()
                taken += 1
                done += 1
            print(f'depth {depth} stratum {key[1]}: {taken} samples of {len(pool)} candidates', flush=True)
    e.close()


def report(a):
    rows = [json.loads(line) for line in open(a.results)]
    print(f'{len(rows)} samples')
    print('half-depth error of the TT move, S - its half-depth score (cp): median |e| and p90 |e| per depth')
    by_depth = defaultdict(list)
    for r in rows:
        by_depth[r['depth']].append(r)
    if a.c6:
        c6_report(rows)
    for d in sorted(by_depth):
        e = sorted(abs(r['score'] - r['tt_half']) for r in by_depth[d])
        print(f'  depth {d:2d}: n {len(e):3d}, median {e[len(e) // 2]:4d}, p90 {e[int(0.9 * (len(e) - 1))]:4d}')

    def flagged(r, m):
        return r['alt_half'] < r['score'] - m * r['depth']

    def best(r):
        return r['tt_full'] > r['alt_full']

    print('per margin M: flagged share and share of flagged still best at full depth, per depth (n flagged)')
    margins = list(range(0, 41, 2))
    table = {}
    for m in margins:
        cells = []
        for d in sorted(by_depth):
            f = [r for r in by_depth[d] if flagged(r, m)]
            ok = sum(best(r) for r in f)
            table[m, d] = (len(f), ok)
            cells.append(f'{d}:{len(f) / len(by_depth[d]):.2f}/{(ok / len(f) if f else 0):.2f}({len(f)})')
        print(f'  M {m:2d}: ' + ' '.join(cells))
    unflagged_best = sum(best(r) for r in rows) / len(rows)
    print(f'all samples: TT move strictly best at full depth in {unflagged_best:.2f}')

    def holds(m, d):
        n, ok = table[m, d]
        return n >= 20 and ok >= 0.9 * n

    depths = [d for d in sorted(by_depth) if d <= 12]
    margin = next((m for m in margins if all(holds(m, d) for d in depths if d >= 6)), None)
    print(f'rule 1, margin: {margin} cp per ply')
    if margin is None:
        return
    min_depth = next((d for d in depths if all(holds(margin, x) for x in depths if x >= d)), None)
    print(f'rule 2, minimum depth: {min_depth}')
    if min_depth is None:
        return
    slack = -1
    for k in range(0, 5):
        f = [r for r in rows if r['depth'] >= min_depth and r['depth'] - r['entry_depth'] == k and flagged(r, margin)]
        ok = sum(best(r) for r in f)
        print(f'  deficit {k}: {len(f)} flagged, {ok / len(f) if f else 0:.2f} still best')
        if len(f) < 20 or ok < 0.9 * len(f):
            break
        slack = k
    print(f'rule 3, entry slack: {slack}')


def c6_report(rows):
    """The engine survey's C6 analyses (the rules in the module docstring)."""
    current = 6
    margins = list(range(0, 41, 2))

    def best(r):
        return r['tt_full'] > r['alt_full']

    def cells(subset, flag):
        out = {}
        for d in range(6, 13):
            f = [r for r in subset if r['depth'] == d and flag(r)]
            out[d] = (len(f), sum(best(r) for r in f))
        return out

    def passes(c, share):
        return all(n >= 20 and ok >= share * n for n, ok in c.values())

    print('C6a, the TT-PV singular margin: per was_pv stratum, the smallest M passing at 90% (and at 95%)')
    picks = {}
    for pv in (1, 0):
        subset = [r for r in rows if r.get('was_pv') == pv]
        found = {}
        for share in (0.90, 0.95):
            found[share] = next((m for m in margins if passes(
                cells(subset, lambda r, m=m: r['alt_half'] < r['score'] - m * r['depth']), share)), None)
        picks[pv] = found
        c = cells(subset, lambda r: r['alt_half'] < r['score'] - current * r['depth'])
        print(f'  was_pv {pv}: {len(subset)} samples; at M {current}: ' +
              ' '.join(f'{d}:{ok}/{n}' for d, (n, ok) in c.items()) +
              f'; M at 90%: {found[0.90]}, at 95%: {found[0.95]}')
    nat = picks[1][0.90]
    if nat is None or nat == current:
        print(f'  C6a: no candidate (the was_pv = 1 pick is {nat}, the current margin {current})')
    else:
        retry = picks[1][0.95]
        if retry is None or retry == nat:
            retry = nat + 2
        print(f'  C6a: natural value {nat} cp per ply, retry {retry}')

    print(f'C6b, the history-shifted bar at M {current}: flagged at depths 6-12 and whether every cell passes at 90%')
    base_cells = cells(rows, lambda r: r['alt_half'] < r['score'] - current * r['depth'])
    base_flagged = sum(n for n, _ in base_cells.values())
    print(f'  unshifted: {base_flagged} flagged, passes {passes(base_cells, 0.90)}')
    results = []
    for k in (-400, -200, -100, -50, 50, 100, 200, 400):
        c = cells(rows, lambda r, k=k: r['alt_half'] < r['score'] - current * r['depth'] - int(r['hist'] / k))
        flagged = sum(n for n, _ in c.values())
        ok = passes(c, 0.90)
        results.append((k, flagged, ok))
        print(f'  k {k:5d}: {flagged} flagged, passes {ok}; ' + ' '.join(f'{d}:{o}/{n}' for d, (n, o) in c.items()))
    passing = sorted((r for r in results if r[2]), key=lambda r: (-r[1], -abs(r[0])))
    if not passing or passing[0][1] <= base_flagged:
        print('  C6b: no candidate (no passing k flags more than the unshifted bar)')
    else:
        retry = passing[1][0] if len(passing) > 1 else None
        print(f'  C6b: natural value k {passing[0][0]}, retry {retry}')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('collect')
    c.add_argument('fork')
    c.add_argument('positions')
    c.add_argument('out')
    c.add_argument('--count', type=int, default=60)
    c.add_argument('--depth', type=int, default=12)
    s = sub.add_parser('search')
    s.add_argument('fork')
    s.add_argument('probes')
    s.add_argument('out')
    s.add_argument('--per-depth', type=int, default=60)
    s.add_argument('--seed', type=int, default=20261031)
    s.add_argument('--pv-strata', action='store_true')
    s.add_argument('--min-depth', type=int, default=0)
    s.add_argument('--max-depth', type=int, default=99)
    r = sub.add_parser('report')
    r.add_argument('results')
    r.add_argument('--c6', action='store_true')
    a = ap.parse_args()
    {'collect': collect, 'search': search, 'report': report}[a.cmd](a)


if __name__ == '__main__':
    main()
