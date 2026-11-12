# SPDX-License-Identifier: GPL-3.0-or-later
"""Replays Fork's own games through a stats build (DESIGN.md §5.7, Phase 4
step 1: X2, X6, X10 and X1's in-game numbers).

History and the transposition table persist across the moves of a game,
while bench clears them per position. So a game is replayed as a game
player plays it: one engine process per game, `ucinewgame` once, then every
position where the named engine (by default "test", the candidate side of
Fork's SPRT PGNs) was to move, in order, searched with
`position fen START moves ...` and `go nodes N`. The method is
tools/drift_measure.py's (branch tier2/drift), rewritten here. The engine is
a stats build (the clang-stats preset); environment variables ask it for
its reports (engine_lines.py): FORK_STATS_REPORT (counter dumps),
FORK_ITERATION_TRACE (per-iteration rows), FORK_PRUNE_LEDGER (the decision
ledger's sampling rate). Its stderr goes to a temporary file, read after
each `bestmove` (the engine writes its report lines before it).

    game_replay.py games PGN_OR_DIR... OUT.jsonl --count N --seed S [--engine-name test] [--skip GAMES.jsonl ...]
    game_replay.py run FORK GAMES.jsonl OUTDIR --nodes N [--jobs 2] [--max-positions K] [--syzygy DIR]
                   [--report counters,iterations,ledger,sites,drift] [--ledger-every 32] [--sites N,M] [--hash 16]

`games` picks N games by a seeded shuffle of every game in the PGNs (games
listed in a --skip file are left out, so measurements use disjoint games)
and writes them with the named engine's colour and the depths of its PGN
comments. `run` writes OUTDIR/manifest.json (the engine's version and bench
line, checked against tests/bench-<net>.ref: a mismatch aborts) and one
OUTDIR/game-NNNN.jsonl per game, one record per search: the game, ply, game
move number, side, legal-move count, the PGN's depth for that move, the
bestmove, the counter and histogram deltas, the iteration rows and the
ledger rows (with --report drift, each row's `drift` values: the drift
tables' passive measurement, FORK_DRIFT_REPORT). A game's file appears only when the game is finished (written
to a temporary name, then renamed), so a stopped run resumes where it
stopped. Engines run at below-normal priority: data generation comes first.
Measurement settings (DESIGN.md §5.7): Hash 16 MB and the Syzygy 3-4-5
tables, as in the SPRT games replayed; one search thread.
"""
import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import chess
import chess.pgn

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine_lines  # noqa: E402


def read_games(paths, engine_name='test'):
    """Every game in the PGN files (or the *.pgn files under folders), in a
    stable order: id, start FEN, UCI moves, the named engine's colour, and
    each move's PGN comment depth (None where absent)."""
    files = []
    for p in map(Path, paths):
        files.extend(sorted(p.rglob('*.pgn')) if p.is_dir() else [p])
    out = []
    for f in files:
        base = Path(paths[0])
        try:
            label = f.relative_to(base if base.is_dir() else base.parent).as_posix()
        except ValueError:
            label = f.name
        with open(f, encoding='utf-8', errors='replace') as stream:
            index = 0
            while True:
                game = chess.pgn.read_game(stream)
                if game is None:
                    break
                index += 1
                white, black = game.headers.get('White', ''), game.headers.get('Black', '')
                if engine_name not in (white, black):
                    continue
                board = game.board()
                moves, depths = [], []
                for node in game.mainline():
                    moves.append(node.move.uci())
                    found = re.search(r'/(\d+)\s', node.comment + ' ')
                    depths.append(int(found.group(1)) if found else None)
                out.append({'id': f'{label}#{index}', 'fen': board.fen(), 'moves': moves,
                            'colour': 'w' if white == engine_name else 'b', 'depths': depths})
    return out


def select_games(games, count, seed, skip_ids=()):
    """`count` games by a seeded shuffle, leaving out the ids in `skip_ids`."""
    skip = set(skip_ids)
    pool = [g for g in games if g['id'] not in skip]
    random.Random(seed).shuffle(pool)
    return pool[:count]


def own_positions(game, max_positions=None):
    """The positions where the game's engine was to move, in order: ply (moves
    played before it), game move number, side, legal-move count, the moves
    before it and the PGN depth of the move played there."""
    board = chess.Board(game['fen'])
    out = []
    for ply, uci in enumerate(game['moves']):
        side = 'w' if board.turn == chess.WHITE else 'b'
        if side == game['colour']:
            out.append({'ply': ply, 'move_number': board.fullmove_number, 'side': side,
                        'legal': board.legal_moves.count(), 'moves': game['moves'][:ply],
                        'pgn_depth': game['depths'][ply] if ply < len(game['depths']) else None})
            if max_positions and len(out) >= max_positions:
                break
        board.push_uci(uci)
    return out


class ReplayEngine:
    """One engine process over UCI; its stderr is read back after each search."""

    def __init__(self, path, env_extra, options):
        self.path = path
        self.env_extra = env_extra
        self.options = options
        self.process = None
        self.err = None
        self.err_offset = 0

    def start(self):
        self.err = tempfile.NamedTemporaryFile('w+b', delete=False, suffix='.stderr')
        env = dict(os.environ, **self.env_extra)
        flags = getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
        self.process = subprocess.Popen([os.path.abspath(self.path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.err, text=True, encoding='utf-8', bufsize=1, env=env,
                                        creationflags=flags)
        if not flags and hasattr(os, 'nice'):
            try:
                os.setpriority(os.PRIO_PROCESS, self.process.pid, 10)
            except OSError:
                pass
        self.send('uci')
        self.wait_for('uciok')
        for name, value in self.options:
            self.send(f'setoption name {name} value {value}')
        self.send('isready')
        self.wait_for('readyok')

    def send(self, line):
        self.process.stdin.write(line + '\n')
        self.process.stdin.flush()

    def wait_for(self, token):
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(f'engine exited while waiting for {token!r}')
            if line.startswith(token):
                return line.strip()

    def new_game(self):
        self.send('ucinewgame')
        self.send('isready')
        self.wait_for('readyok')

    def search(self, fen, moves, nodes):
        """Searches one position; returns the bestmove and the stderr written meanwhile."""
        self.send(f'position fen {fen}' + (' moves ' + ' '.join(moves) if moves else ''))
        self.send(f'go nodes {nodes}')
        best = self.wait_for('bestmove').split()[1]
        self.err.flush()
        with open(self.err.name, 'rb') as f:
            f.seek(self.err_offset)
            text = f.read().decode('utf-8', errors='replace')
        self.err_offset += len(text.encode('utf-8'))
        return best, text

    def close(self):
        if self.process and self.process.poll() is None:
            try:
                self.send('quit')
                self.process.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
        if self.process:
            for stream in (self.process.stdin, self.process.stdout):
                try:
                    stream.close()
                except OSError:
                    pass
        if self.err:
            self.err.close()
            try:
                os.unlink(self.err.name)
            except OSError:
                pass


def replay_one_game(fork, game, index, outdir, settings):
    """Replays one game into OUTDIR/game-NNNN.jsonl (skipped if it exists)."""
    target = Path(outdir) / f'game-{index:04d}.jsonl'
    if target.exists():
        return 'skipped'
    env = {}
    if 'counters' in settings['report']:
        env['FORK_STATS_REPORT'] = '1'
    if 'iterations' in settings['report']:
        env['FORK_ITERATION_TRACE'] = '1'
    if 'ledger' in settings['report']:
        env['FORK_PRUNE_LEDGER'] = str(settings['ledger_every'])
    if 'sites' in settings['report']:
        env['FORK_EVAL_SITES'] = settings['sites']
    if 'drift' in settings['report']:
        env['FORK_DRIFT_REPORT'] = '1'
    options = [('Hash', settings['hash']), ('Threads', 1)]
    if settings.get('syzygy'):
        options.append(('SyzygyPath', settings['syzygy']))
    engine = ReplayEngine(fork, env, options)
    records = []
    try:
        engine.start()
        engine.new_game()
        previous = None
        for pos in own_positions(game, settings.get('max_positions')):
            best, text = engine.search(game['fen'], pos['moves'], settings['nodes'])
            record = {'game': game['id'], 'index': index, 'ply': pos['ply'], 'move_number': pos['move_number'],
                      'side': pos['side'], 'legal': pos['legal'], 'pgn_depth': pos['pgn_depth'],
                      'nodes_limit': settings['nodes'], 'bestmove': best, 'iterations': [], 'ledger': [],
                      'sites': []}
            dump = {}
            for number, line in enumerate(text.splitlines(), 1):
                try:
                    if line.startswith('search_counters '):
                        dump.update(engine_lines.parse_counter_line(line))
                    elif line.startswith('search_hist '):
                        name, bins = engine_lines.parse_hist_line(line)
                        dump['hist:' + name] = bins
                    elif line.startswith('iteration_trace '):
                        record['iterations'].append(engine_lines.parse_iteration_line(line))
                    elif line.startswith('prune_ledger '):
                        record['ledger'].append(engine_lines.parse_ledger_line(line))
                    elif line.startswith('drift_ledger '):
                        # The drift tables' values for the row just read (same technique).
                        drift = engine_lines.parse_drift_ledger_line(line)
                        if not record['ledger'] or 'drift' in record['ledger'][-1] or                                 record['ledger'][-1]['technique'] != drift['technique']:
                            raise ValueError('a drift_ledger line without its prune_ledger row')
                        record['ledger'][-1]['drift'] = {k: v for k, v in drift.items() if k != 'technique'}
                    elif line.startswith('eval_site '):
                        record['sites'].append(engine_lines.parse_eval_site_line(line))
                except ValueError as e:
                    raise RuntimeError(f'game {game["id"]} ply {pos["ply"]} stderr line {number}: {e}')
            if dump:
                delta = engine_lines.counter_delta(dump, previous)
                previous = dump
                record['counters'] = {k: v for k, v in delta.items() if not k.startswith('hist:')}
                record['hist'] = {k[5:]: v for k, v in delta.items() if k.startswith('hist:')}
            records.append(record)
    finally:
        engine.close()
    partial = target.with_suffix('.partial')
    with open(partial, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, separators=(',', ':')) + '\n')
    os.replace(partial, target)
    return 'done'


def run_replay(fork, games, outdir, settings, jobs):
    """Replays the games (in parallel, `jobs` engines at once); returns (done, skipped)."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    done = skipped = 0
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(replay_one_game, fork, g, i, outdir, settings) for i, g in enumerate(games)]
        for future in futures:
            if future.result() == 'done':
                done += 1
                print(f'{done + skipped}/{len(games)} games', flush=True)
            else:
                skipped += 1
    return done, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    g = sub.add_parser('games', help='select games from PGNs')
    g.add_argument('pgn', nargs='+')
    g.add_argument('out', type=Path)
    g.add_argument('--count', type=int, required=True)
    g.add_argument('--seed', type=int, required=True)
    g.add_argument('--engine-name', default='test')
    g.add_argument('--skip', action='append', default=[], type=Path)
    r = sub.add_parser('run', help='replay the selected games through a stats build')
    r.add_argument('fork')
    r.add_argument('games', type=Path)
    r.add_argument('outdir', type=Path)
    r.add_argument('--nodes', type=int, required=True)
    r.add_argument('--jobs', type=int, default=2)
    r.add_argument('--max-positions', type=int, default=None)
    r.add_argument('--syzygy', default=None)
    r.add_argument('--report', default='counters')
    r.add_argument('--ledger-every', type=int, default=32)
    r.add_argument('--hash', type=int, default=16)
    r.add_argument('--sites', default='0,0', help='with --report sites: FORK_EVAL_SITES (every Nth main, Mth quiescence)')
    r.add_argument('--no-bench-check', action='store_true', help='tests only: skip the bench reference check')
    a = parser.parse_args(argv)

    if a.command == 'games':
        skip_ids = []
        for path in a.skip:
            skip_ids.extend(json.loads(line)['id'] for line in path.read_text(encoding='utf-8').splitlines())
        chosen = select_games(read_games(a.pgn, a.engine_name), a.count, a.seed, skip_ids)
        if len(chosen) < a.count:
            raise SystemExit(f'only {len(chosen)} games available, {a.count} asked')
        with open(a.out, 'w', encoding='utf-8') as f:
            for game in chosen:
                f.write(json.dumps(game, separators=(',', ':')) + '\n')
        positions = sum(len(own_positions(game)) for game in chosen)
        print(f'{len(chosen)} games, {positions} positions of the named engine')
        return 0

    a.fork = os.path.abspath(a.fork)
    games = [json.loads(line) for line in a.games.read_text(encoding='utf-8').splitlines()]
    report = set(a.report.split(','))
    known = {'counters', 'iterations', 'ledger', 'sites', 'drift'}
    if not report <= known:
        raise SystemExit(f'unknown --report entries: {sorted(report - known)}')
    settings = {'nodes': a.nodes, 'max_positions': a.max_positions, 'syzygy': a.syzygy, 'report': sorted(report),
                'ledger_every': a.ledger_every, 'hash': a.hash, 'sites': a.sites}
    a.outdir.mkdir(parents=True, exist_ok=True)
    version = subprocess.run([a.fork, 'version'], capture_output=True, text=True, check=True).stdout
    manifest = {'settings': settings, 'games': str(a.games.name), 'count': len(games), 'version': version}
    if not a.no_bench_check:
        bench = subprocess.run([a.fork, 'bench'], capture_output=True, text=True, check=True).stdout
        nodes = re.search(r'nodes (\d+)', bench).group(1)
        signature = re.search(r'signature ([0-9a-f]+)', bench).group(1)
        net = re.search(r'^net (\S+)', version, re.M)
        ref_path = Path(__file__).resolve().parents[2] / 'tests' / (f'bench-{net.group(1)}.ref' if net else 'bench.ref')
        ref = ref_path.read_text(encoding='utf-8')
        if f'nodes {nodes}' not in ref or f'signature {signature}' not in ref:
            raise SystemExit(f'bench {nodes} / {signature} does not match {ref_path.name}: not this commit\'s search')
        manifest['bench'] = {'nodes': int(nodes), 'signature': signature, 'reference': ref_path.name}
    (a.outdir / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8')
    done, skipped = run_replay(a.fork, games, a.outdir, settings, a.jobs)
    print(f'replayed {done} games ({skipped} already done)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
