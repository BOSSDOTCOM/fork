# SPDX-License-Identifier: GPL-3.0-or-later
"""The near-window extension's node cost (ideas.md idea 60, its first
measurement; DESIGN.md "Search constants": NearWindowMargin).

The cost of an extension is more nodes at equal depth (nps is unchanged:
the work per node is the same). On a fixed set of game positions, each
setting searches every position to the same depth from a fresh state
(`ucinewgame`): the extension off, and on at each margin, all in one
tuning build (FORK_TUNE: UseNearWindowExtension and NearWindowMargin are
UCI options there). A position's cost is its node ratio on / off at the
same depth.

Positions: the games of idea 59 step 1's X2 replay (DESIGN.md §5.7 on
branch measure/step1: 100 games of ~/fork-data/sprt/s512ppr2-stc, seed
20261107, the games.jsonl its game_replay.py wrote), the positions where
the games' "test" engine was to move, at most PER_GAME per game, evenly
spaced over its positions. Engine settings: Hash 16 MB, one thread, the
Syzygy 3-4-5 tables, as in the replayed SPRT games.

Rule, fixed before the runs (2026-11-07): a margin's node cost at a depth
is the geometric mean over positions of nodes(on) / nodes(off), less 1,
with a 95% interval from a bootstrap over games (200 rounds, seed
20261107); the ratio of total nodes is reported beside it. Idea 60's kill
line: a cost above about 15% at the margin chosen later. Two depths: the
first, where "off" takes about 200,000 nodes at the median (the STC
proxy), and two plies deeper (toward LTC).

    near_window_cost.py run FORK GAMES.jsonl OUT.jsonl --depths 9,11 [--margins 10,25] [--per-game 20]
                        [--jobs 2] [--hash 16] [--syzygy DIR] [--max-games N]
    near_window_cost.py report OUT.jsonl

`run` writes one line per position (game, ply, nodes per setting and
depth); a game's lines are appended when it is finished, and games already
in OUT are skipped, so a stopped run resumes. Engines run at below-normal
priority.
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import chess

BootstrapSeed = 20261107
BootstrapRounds = 200
KillLine = 0.15


class Engine:
    """One engine process over UCI."""

    def __init__(self, path, hash_mb, syzygy):
        flags = getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
        self.proc = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1, creationflags=flags)
        self.send('uci')
        self.wait_for('uciok')
        self.send(f'setoption name Hash value {hash_mb}')
        self.send('setoption name Threads value 1')
        if syzygy:
            self.send(f'setoption name SyzygyPath value {syzygy}')
        self.send('isready')
        self.wait_for('readyok')

    def send(self, line):
        self.proc.stdin.write(line + '\n')
        self.proc.stdin.flush()

    def wait_for(self, token):
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError('engine exited')
            if line.split()[:1] == [token]:
                return line

    def nodes_to_depth(self, fen, moves, depth, margin):
        """Nodes of a fresh search to `depth`; margin None is the extension off."""
        self.send('ucinewgame')
        self.send(f'setoption name UseNearWindowExtension value {"false" if margin is None else "true"}')
        if margin is not None:
            self.send(f'setoption name NearWindowMargin value {margin}')
        self.send('isready')
        self.wait_for('readyok')
        self.send(f'position fen {fen}' + (' moves ' + ' '.join(moves) if moves else ''))
        self.send(f'go depth {depth}')
        nodes = None
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError('engine exited')
            words = line.split()
            if words[:1] == ['bestmove']:
                return nodes
            if words[:1] == ['info'] and 'nodes' in words:
                nodes = int(words[words.index('nodes') + 1])

    def close(self):
        try:
            self.send('quit')
            self.proc.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()


def own_positions(game, per_game):
    """Up to `per_game` positions where the game's engine was to move, evenly
    spaced: (ply, moves before it)."""
    board = chess.Board(game['fen'])
    own = []
    for ply, uci in enumerate(game['moves']):
        if ('w' if board.turn == chess.WHITE else 'b') == game['colour']:
            own.append((ply, game['moves'][:ply]))
        board.push_uci(uci)
    if len(own) <= per_game:
        return own
    return [own[i * len(own) // per_game] for i in range(per_game)]


def setting_names(margins):
    return ['off'] + [f'm{m}' for m in margins]


def run(args):
    games = [json.loads(line) for line in open(args.games, encoding='utf-8') if line.strip()]
    if args.max_games:
        games = games[:args.max_games]
    depths = [int(d) for d in args.depths.split(',')]
    margins = [int(m) for m in args.margins.split(',') if m]  # empty: "off" only (a depth pilot)
    done = set()
    if os.path.exists(args.out):
        done = {json.loads(line)['game'] for line in open(args.out, encoding='utf-8') if line.strip()}
    todo = [g for g in games if g['id'] not in done]
    lock = threading.Lock()
    finished = [len(done)]

    def work(chunk):
        engine = Engine(args.fork, args.hash, args.syzygy)
        try:
            for game in chunk:
                rows = []
                for ply, moves in own_positions(game, args.per_game):
                    nodes = {}
                    for depth in depths:
                        for name, margin in zip(setting_names(margins), [None] + margins):
                            nodes[f'{name}@{depth}'] = engine.nodes_to_depth(game['fen'], moves, depth, margin)
                    rows.append({'game': game['id'], 'ply': ply, 'nodes': nodes})
                with lock:
                    with open(args.out, 'a', encoding='utf-8') as out:
                        for row in rows:
                            out.write(json.dumps(row) + '\n')
                    finished[0] += 1
                    print(f'{finished[0]}/{len(games)} games', flush=True)
        finally:
            engine.close()

    chunks = [todo[i::args.jobs] for i in range(args.jobs)]
    with ThreadPoolExecutor(args.jobs) as pool:
        for f in [pool.submit(work, c) for c in chunks if c]:
            f.result()


def geometric_mean_ratio(rows, a, b):
    logs = [math.log(r['nodes'][a] / r['nodes'][b]) for r in rows]
    return math.exp(sum(logs) / len(logs))


def report(args):
    rows = [json.loads(line) for line in open(args.out, encoding='utf-8') if line.strip()]
    keys = sorted({k for r in rows for k in r['nodes']})
    depths = sorted({int(k.split('@')[1]) for k in keys})
    names = sorted({k.split('@')[0] for k in keys} - {'off'}, key=lambda n: int(n[1:]))
    by_game = {}
    for r in rows:
        by_game.setdefault(r['game'], []).append(r)
    game_ids = sorted(by_game)
    rng = random.Random(BootstrapSeed)
    samples = [[rng.choice(game_ids) for _ in game_ids] for _ in range(BootstrapRounds)]
    print(f'{len(rows)} positions from {len(game_ids)} games; kill line: cost above {KillLine:.0%}')
    for depth in depths:
        off = f'off@{depth}'
        median = sorted(r['nodes'][off] for r in rows)[len(rows) // 2]
        print(f'depth {depth}: "off" median {median:,} nodes, total {sum(r["nodes"][off] for r in rows):,}')
        for name in names:
            on = f'{name}@{depth}'
            cost = geometric_mean_ratio(rows, on, off) - 1
            boot = sorted(geometric_mean_ratio([r for g in s for r in by_game[g]], on, off) - 1 for s in samples)
            low, high = boot[int(0.025 * len(boot))], boot[int(0.975 * len(boot)) - 1]
            total = sum(r['nodes'][on] for r in rows) / sum(r['nodes'][off] for r in rows) - 1
            verdict = 'above the kill line' if cost > KillLine else 'within the kill line'
            print(f'  {name}: cost {cost:+.1%} [{low:+.1%}, {high:+.1%}] (geometric mean), '
                  f'total nodes {total:+.1%}: {verdict}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    r = sub.add_parser('run')
    r.add_argument('fork')
    r.add_argument('games')
    r.add_argument('out')
    r.add_argument('--depths', required=True)
    r.add_argument('--margins', default='10,25')
    r.add_argument('--per-game', type=int, default=20)
    r.add_argument('--jobs', type=int, default=2)
    r.add_argument('--hash', type=int, default=16)
    r.add_argument('--syzygy', default='')
    r.add_argument('--max-games', type=int, default=0)
    p = sub.add_parser('report')
    p.add_argument('out')
    args = parser.parse_args()
    run(args) if args.command == 'run' else report(args)


if __name__ == '__main__':
    sys.exit(main())
