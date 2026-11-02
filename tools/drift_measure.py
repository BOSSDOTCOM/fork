# SPDX-License-Identifier: GPL-3.0-or-later
"""The pawn drift measurement (tier 2, T32; DESIGN.md, "Search constants":
DriftLimit, DriftWeightTotal, DriftWeightCap, DriftSlotBits).

The table learns over a game, so the measurement replays games: Fork's own
STC SPRT games (fastchess PGNs), one engine process per game in turn, which
searches every position where the game's first mover is to move, in order,
at a fixed node budget (`position fen START moves ...`, `go nodes N`), after
one `ucinewgame` at the game's start, as a game player would. The engine is
a tuning and stats build (FORK_TUNE, FORK_SEARCH_STATS): the drift switch
and parameters are UCI options, and with FORK_DRIFT_REPORT set it prints its
drift counters after each search (src/search/searcher.cpp): at every node
where the table learns, the error of the raw and of the drifted static
estimate against the node's result (for a bound, only the part the bound
proves), the exact results' raw errors in 10 cp bins, and how often a learn
finds its slot last written by another structure, for 2^10 to 2^16 slots.

Every setting runs with the drift not applied (UsePawnDrift false): under
FORK_DRIFT_REPORT the table still learns with the setting's parameters and
its estimate is judged, but the search uses the raw eval. So every setting
searches the same tree, and the drifted estimate is judged against results
it did not shape. With the drift applied, the quiescence stand-pats carry
it into the results, which moves them toward the drifted estimate: in a
3-game pipeline test the applied 64/16 run's drifted error over its own raw
error was 0.68, while its drifted error (36.44 cp) was no lower than the
undrifted run's raw error (36.42 cp). That circularity, not which setting
did better, is why the measurement changed to this form before its runs
(the 3 test games are among the 120). Whether applying the drift gains is
the SPRT's question.

Rules, fixed before the measurement's data were seen (2026-11-02):
1. DriftLimit: from the run "off" (the default parameters), the 99th percentile of the
   exact results' raw error |result - raw eval|, rounded up to a multiple of
   25 cp (a larger error is clamped when learned: it is more likely a
   tactic the search found than the structure's drift).
2. The weights: every pair of DriftWeightTotal in {32, 64, 128} and
   DriftWeightCap in {8, 16, 32}, with that limit and 2^14 slots. A setting's
   fitness is its summed drifted error over its summed raw error, over all
   its games' learning nodes (lower is better; 1 is no better than the raw
   eval). The pair with the lowest fitness is chosen; settings within
   0.005 of it count as tied, and a tie goes to the smallest largest step
   (cap / total), then to the smaller total. The chosen pair goes to the
   SPRT whatever its margin (the SPRT decides adoption); its fitness is
   reported with a bootstrap 95% interval over games.
3. DriftSlotBits: in the chosen setting's run, the smallest slot count from
   2^10 to 2^16 whose learns find another structure's entry in under 2% of
   learns (2^16 if none does).
Reported but not part of the rules: each setting's samples and mean errors,
and the nodes searched.

    drift_measure.py games PGN... OUT.jsonl [--count 120]
    drift_measure.py sweep FORK GAMES.jsonl OUTDIR SETTING [--limit L] [--nodes 200000] [--jobs 2]
        SETTING: off, or TOTAL/CAP (e.g. 64/16)
    drift_measure.py report OUTDIR
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

import chess
import chess.pgn

Totals = [32, 64, 128]
Caps = [8, 16, 32]
TieMargin = 0.005
LimitPercentile = 0.99
LimitStep = 25
ForeignShare = 0.02
CheckLow = 10
BootstrapSeed = 20261102
BootstrapRounds = 2000


def games(a):
    """The first COUNT games of the PGNs, in the order given: start FEN and UCI moves."""
    out = []
    for path in a.pgn:
        with open(path, encoding='utf-8') as f:
            while len(out) < a.count:
                game = chess.pgn.read_game(f)
                if game is None:
                    break
                board = game.board()
                out.append({'fen': board.fen(), 'moves': [m.uci() for m in game.mainline_moves()]})
        if len(out) >= a.count:
            break
    with open(a.out, 'w', encoding='utf-8') as f:
        for g in out:
            f.write(json.dumps(g) + '\n')
    print(f'{len(out)} games, {sum((len(g["moves"]) + 1) // 2 for g in out)} positions to search')


class Engine:
    """One engine process; its drift counters go to a file read after each search."""

    def __init__(self, path, options):
        self.err = tempfile.NamedTemporaryFile('w+', encoding='utf-8', delete=False, suffix='.drift')
        env = dict(os.environ, FORK_DRIFT_REPORT='1')
        # Below normal priority on Windows: the machine's data generation comes first.
        self.p = subprocess.Popen([os.path.abspath(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err,
                                  text=True, encoding='utf-8', bufsize=1, env=env,
                                  creationflags=getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0))
        self.send('uci')
        self.until('uciok')
        for name, value in options:
            self.send(f'setoption name {name} value {value}')
        self.send('setoption name Hash value 16')

    def send(self, line):
        self.p.stdin.write(line + '\n')
        self.p.stdin.flush()

    def until(self, prefix):
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError(f'engine ended waiting for {prefix!r}')
            if line.startswith(prefix):
                return line

    def counters(self):
        with open(self.err.name, encoding='utf-8') as f:
            last = [line for line in f if line.startswith('drift_report ')][-1]
        head, bins, foreign = last[len('drift_report '):].split('|')
        return {'head': [int(x) for x in head.split()], 'bins': [int(x) for x in bins.split()],
                'foreign': [int(x) for x in foreign.split()]}

    def play(self, game, nodes):
        self.send('ucinewgame')
        self.send('isready')
        self.until('readyok')
        searched = 0
        for ply in range(0, len(game['moves']), 2):
            moves = ' '.join(game['moves'][:ply])
            self.send(f'position fen {game["fen"]}' + (f' moves {moves}' if moves else ''))
            self.send(f'go nodes {nodes}')
            self.until('bestmove')
            searched += 1
        return searched

    def close(self):
        self.send('quit')
        self.p.wait(timeout=30)
        self.err.close()
        os.unlink(self.err.name)


def delta(after, before):
    return {k: [x - y for x, y in zip(after[k], before[k])] for k in after}


def options_for(setting, limit):
    if setting == 'off':
        return [('UsePawnDrift', 'false')]
    total, cap = setting.split('/')
    return [('UsePawnDrift', 'false'), ('DriftWeightTotal', total), ('DriftWeightCap', cap),
            ('DriftLimit', str(limit))]


def sweep(a):
    rows = [json.loads(line) for line in open(a.games, encoding='utf-8') if line.strip()]
    os.makedirs(a.outdir, exist_ok=True)
    path = os.path.join(a.outdir, a.setting.replace('/', '-') + '.jsonl')
    if os.path.exists(path):
        print(f'{path} exists')
        return
    if a.setting != 'off' and a.limit is None:
        sys.exit('a drift setting needs --limit')

    def part(chunk):
        engine = Engine(a.fork, options_for(a.setting, a.limit))
        out = []
        try:
            before = {'head': [0, 0, 0], 'bins': [0] * 101, 'foreign': [0] * 7}
            for k, game in chunk:
                searched = engine.play(game, a.nodes)
                now = engine.counters()
                out.append((k, {'game': k, 'searched': searched, **delta(now, before)}))
                before = now
        finally:
            engine.close()
        return out

    jobs = max(1, min(a.jobs, len(rows)))
    chunks = [list(enumerate(rows))[j::jobs] for j in range(jobs)]
    with ThreadPoolExecutor(jobs) as pool:
        results = sorted((r for part_rows in pool.map(part, chunks) for r in part_rows), key=lambda r: r[0])
    with open(path + '.part', 'w', encoding='utf-8') as f:
        for _, r in results:
            f.write(json.dumps({'setting': a.setting, 'limit': a.limit, 'nodes': a.nodes, **r}) + '\n')
    os.replace(path + '.part', path)
    print(f'{a.setting}: {len(results)} games done', flush=True)


def load(path):
    return [json.loads(line) for line in open(path, encoding='utf-8') if line.strip()]


def fitness(rows):
    raw = sum(r['head'][1] for r in rows)
    drifted = sum(r['head'][2] for r in rows)
    return drifted / raw if raw else float('nan')


def interval(rows):
    rng = random.Random(BootstrapSeed)
    values = sorted(fitness([rows[rng.randrange(len(rows))] for _ in rows]) for _ in range(BootstrapRounds))
    return values[int(0.025 * BootstrapRounds)], values[int(0.975 * BootstrapRounds) - 1]


def report(a):
    runs = {}
    for name in sorted(os.listdir(a.outdir)):
        if name.endswith('.jsonl'):
            rows = load(os.path.join(a.outdir, name))
            runs[rows[0]['setting']] = rows
    if 'off' in runs:
        bins = [sum(r['bins'][i] for r in runs['off']) for i in range(101)]
        total, seen, p99 = sum(bins), 0, None
        for i, n in enumerate(bins):
            seen += n
            if p99 is None and seen >= LimitPercentile * total:
                p99 = (i + 1) * 10  # the bin's upper edge
        limit = math.ceil(p99 / LimitStep) * LimitStep
        print(f'off: {total} exact results; 99th percentile of the raw error below {p99} cp: DriftLimit {limit}')
    for s, rows in runs.items():
        samples = sum(r['head'][0] for r in rows)
        raw = sum(r['head'][1] for r in rows) / max(samples, 1)
        drifted = sum(r['head'][2] for r in rows) / max(samples, 1)
        judged = '' if s == 'off' else f' drifted {drifted:.2f}, fitness {fitness(rows):.4f}'
        print(f'{s:>6}: {len(rows)} games, {sum(r["searched"] for r in rows)} searches, {samples} samples, '
              f'mean error raw {raw:.2f}{judged}')
    grid = [f'{t}/{c}' for t in Totals for c in Caps if f'{t}/{c}' in runs]
    if not grid:
        return
    if len(grid) < len(Totals) * len(Caps):
        print(f'partial grid: {len(grid)} of {len(Totals) * len(Caps)} settings')
    fit = {s: fitness(runs[s]) for s in grid}
    best = min(fit.values())
    tied = [s for s in grid if fit[s] <= best + TieMargin]
    chosen = min(tied, key=lambda s: (int(s.split('/')[1]) / int(s.split('/')[0]), int(s.split('/')[0])))
    low, high = interval(runs[chosen])
    print(f'chosen: total/cap {chosen} (fitness {fit[chosen]:.4f} [{low:.4f}, {high:.4f}]; best {best:.4f}; '
          f'tied: {", ".join(tied)})')
    samples = sum(r['head'][0] for r in runs[chosen])
    foreign = [sum(r['foreign'][i] for r in runs[chosen]) for i in range(7)]
    for i, n in enumerate(foreign):
        print(f'  2^{CheckLow + i} slots: another structure in {n / max(samples, 1):.2%} of learns')
    bits = next((CheckLow + i for i, n in enumerate(foreign) if n < ForeignShare * samples), CheckLow + 6)
    print(f'chosen DriftSlotBits: {bits}')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('games')
    p.add_argument('pgn', nargs='+')
    p.add_argument('out')
    p.add_argument('--count', type=int, default=120)
    p = sub.add_parser('sweep')
    p.add_argument('fork')
    p.add_argument('games')
    p.add_argument('outdir')
    p.add_argument('setting')
    p.add_argument('--limit', type=int)
    p.add_argument('--nodes', type=int, default=200000)
    p.add_argument('--jobs', type=int, default=2)
    p = sub.add_parser('report')
    p.add_argument('outdir')
    a = ap.parse_args()
    {'games': games, 'sweep': sweep, 'report': report}[a.cmd](a)


if __name__ == '__main__':
    main()
