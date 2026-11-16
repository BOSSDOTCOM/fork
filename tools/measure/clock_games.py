# SPDX-License-Identifier: GPL-3.0-or-later
"""Clock games between two settings of one Fork binary: the time-loss check of L1 (the time-management audit of
2026-11-16, switch UseTimeGuards; DESIGN.md §5.2 "Search constants", TimeGuardPermille).

Each game is played over UCI with a real clock: before each move the side to move is sent its clock (`go wtime
btime winc binc`), the time from `go` to `bestmove` is measured here (monotonic clock), taken off, and the
increment is added after the move. That is the stricter of the two GUI rules (fastchess sends the move's
increment with the clock: tools/measure/clock_share.py), so a time loss here is a time loss there too. A clock
below zero after a move is a time loss: the game ends, lost on time. Otherwise a game ends by the rules
(python-chess: mate, stalemate, insufficient material, threefold repetition, the 50-move rule) or as a draw at
--max-plies. Openings: --games / 2 starts from an EPD file (a seeded shuffle), each played with both colours.
Arm A gets --option-a, arm B --option-b (NAME=VALUE, repeatable); both get Hash, Threads 1, the Move Overhead and
CalibratedScore false. Engines run at niceness --nice (POSIX; 0 shares the CPU equally with a running data
generation).

Reported per arm: moves, time losses, the smallest clock left after a move, the largest share of the clock less
the Move Overhead one move took, and the moves over 0.5 and 0.9 of it; per game: result, plies, how it ended.
The game files (one JSON line per game, the moves and times) go to OUT.jsonl, so a stopped run resumes.

    clock_games.py FORK OPENINGS.epd OUT --games 80 --base-ms 60000 --inc-ms 100 [--overhead-ms 100]
                   [--concurrency 2] [--nice 0] [--seed 20261116] [--hash 64] [--syzygy DIR] [--max-plies 400]
                   [--option-a UseTimeGuards=true] [--option-b UseTimeGuards=false]
"""
import argparse
import json
import os
import random
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import chess


class Engine:
    def __init__(self, path, options, nice):
        self.process = subprocess.Popen([os.path.abspath(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, encoding='utf-8', bufsize=1)
        if hasattr(os, 'setpriority'):
            try:
                os.setpriority(os.PRIO_PROCESS, self.process.pid, nice)
            except OSError:
                pass
        self.send('uci')
        self.wait_for('uciok')
        for name, value in options:
            self.send(f'setoption name {name} value {value}')
        self.send('ucinewgame')
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

    def close(self):
        try:
            self.send('quit')
            self.process.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            self.process.kill()


def play(fork, fen, a_white, settings):
    """One game; returns its record (arms 'a' and 'b')."""
    common = [('CalibratedScore', 'false'), ('Threads', 1), ('Hash', settings['hash']),
              ('Move Overhead', settings['overhead_ms'])]
    if settings['syzygy']:
        common.append(('SyzygyPath', settings['syzygy']))
    arms = {'a': common + settings['option_a'], 'b': common + settings['option_b']}
    colour_arm = {chess.WHITE: 'a' if a_white else 'b', chess.BLACK: 'b' if a_white else 'a'}
    engines = {arm: Engine(fork, opts, settings['nice']) for arm, opts in arms.items()}
    board = chess.Board(fen)
    clock = {chess.WHITE: settings['base_ms'], chess.BLACK: settings['base_ms']}
    inc = settings['inc_ms']
    moves, end, loser = [], None, None
    try:
        while True:
            if board.is_game_over(claim_draw=True):
                end = board.outcome(claim_draw=True).termination.name.lower()
                break
            if len(moves) >= settings['max_plies']:
                end = 'max_plies'
                break
            side = board.turn
            arm = colour_arm[side]
            e = engines[arm]
            e.send(f'position fen {fen}' + (' moves ' + ' '.join(m['uci'] for m in moves) if moves else ''))
            before = clock[side]
            t0 = time.monotonic()
            e.send(f'go wtime {max(0, clock[chess.WHITE])} btime {max(0, clock[chess.BLACK])} winc {inc} binc {inc}')
            best = e.wait_for('bestmove').split()[1]
            used = round((time.monotonic() - t0) * 1000)
            clock[side] = before - used
            moves.append({'uci': best, 'arm': arm, 'before_ms': before, 'used_ms': used, 'after_ms': clock[side]})
            if clock[side] < 0:
                end, loser = 'time_loss', arm
                break
            try:
                move = chess.Move.from_uci(best)
            except ValueError:
                move = None
            if move is None or move not in board.legal_moves:
                end, loser = 'illegal_move', arm
                break
            board.push(move)
            clock[side] += inc
    finally:
        for e in engines.values():
            e.close()
    if loser:
        result = {'a': 0.0, 'b': 1.0} if loser == 'a' else {'a': 1.0, 'b': 0.0}
    elif board.is_checkmate():
        winner = colour_arm[not board.turn]
        result = {winner: 1.0, ('b' if winner == 'a' else 'a'): 0.0}
    else:
        result = {'a': 0.5, 'b': 0.5}
    return {'fen': fen, 'a_white': a_white, 'end': end, 'loser': loser, 'score_a': result['a'],
            'plies': len(moves), 'moves': moves}


def summarise(records, overhead_ms):
    out = {}
    for arm in ('a', 'b'):
        rows = [m for r in records for m in r['moves'] if m['arm'] == arm]
        shares = [m['used_ms'] / max(1, m['before_ms'] - overhead_ms) for m in rows]
        out[arm] = {'moves': len(rows),
                    'time_losses': sum(r['end'] == 'time_loss' and r['loser'] == arm for r in records),
                    'illegal_moves': sum(r['end'] == 'illegal_move' and r['loser'] == arm for r in records),
                    'min_clock_after_ms': min((m['after_ms'] for m in rows), default=None),
                    'max_share_available': max(shares, default=None),
                    'moves_over_0.5': sum(s > 0.5 for s in shares), 'moves_over_0.9': sum(s > 0.9 for s in shares)}
    n = len(records)
    out['games'] = n
    out['score_a'] = sum(r['score_a'] for r in records) / n if n else None
    out['ends'] = {k: sum(r['end'] == k for r in records) for k in sorted({r['end'] for r in records})}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('fork')
    parser.add_argument('openings', type=Path)
    parser.add_argument('out', type=Path, help='OUT.jsonl (games) and OUT.summary.json')
    parser.add_argument('--games', type=int, required=True)
    parser.add_argument('--base-ms', type=int, required=True)
    parser.add_argument('--inc-ms', type=int, required=True)
    parser.add_argument('--overhead-ms', type=int, default=100)
    parser.add_argument('--concurrency', type=int, default=2)
    parser.add_argument('--nice', type=int, default=0)
    parser.add_argument('--seed', type=int, default=20261116)
    parser.add_argument('--hash', type=int, default=64)
    parser.add_argument('--syzygy', default=None)
    parser.add_argument('--max-plies', type=int, default=400)
    parser.add_argument('--option-a', action='append', default=[])
    parser.add_argument('--option-b', action='append', default=[])
    a = parser.parse_args(argv)
    if a.games < 2 or a.games % 2:
        raise SystemExit('--games: an even number, at least 2 (each opening with both colours)')
    fens = [' '.join(line.split()[:6]) for line in a.openings.read_text(encoding='utf-8').splitlines() if line.strip()]
    random.Random(a.seed).shuffle(fens)
    starts = [(fen, white) for fen in fens[:a.games // 2] for white in (True, False)]
    settings = {'hash': a.hash, 'overhead_ms': a.overhead_ms, 'syzygy': a.syzygy, 'nice': a.nice,
                'base_ms': a.base_ms, 'inc_ms': a.inc_ms, 'max_plies': a.max_plies,
                'option_a': [tuple(o.split('=', 1)) for o in a.option_a],
                'option_b': [tuple(o.split('=', 1)) for o in a.option_b]}
    out = Path(str(a.out) + '.jsonl')
    done = {}
    if out.exists():  # resume: games already played are kept
        for line in out.read_text(encoding='utf-8').splitlines():
            if line.strip():
                r = json.loads(line)
                done[(r['fen'], r['a_white'])] = r
    lock = threading.Lock()

    def one(start):
        if start in done:
            return done[start]
        r = play(a.fork, start[0], start[1], settings)
        with lock, open(out, 'a', encoding='utf-8') as f:
            f.write(json.dumps(r, separators=(',', ':')) + '\n')
        return r

    with ThreadPoolExecutor(max_workers=a.concurrency) as pool:
        records = list(pool.map(one, starts))
    summary = summarise(records, a.overhead_ms)
    summary['settings'] = {k: v for k, v in settings.items()}
    Path(str(a.out) + '.summary.json').write_text(json.dumps(summary, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
