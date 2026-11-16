# SPDX-License-Identifier: GPL-3.0-or-later
"""The share of the remaining clock each move of a game takes (the per-move guard's measurement; DESIGN.md
§5.2 "Search constants", TimeGuardPermille).

Input: fastchess PGNs of sudden-death games with an increment (TimeControl "B+I", seconds) whose move comments
end in the move's time ("{+0.34/20 3.799s}"). The PGNs carry no clock comments, so each side's clock is
rebuilt: before each of the side's moves it gains I, and the move's time comes off (the clock the engine is sent
holds that move's increment). The data decide the rule: credited this way, no move of 1,008 SPRT shards of
2026-11-14 to 16 takes more than 0.903 of the clock less the 100 ms overhead, which is Fork's own cap (the hard
limit stops 1/10 short of that clock) plus latency; credited after the move instead, moves would take up to 6
times the clock they had, impossible in games without time losses. For every move: the time over the clock before it
(`share`), and over the clock less the Move Overhead the engine plans with (`share_available`, overhead in
--overhead-ms, Fork's default 100).

Reported per time control: moves, games, the largest shares, percentiles, and for each guard fraction F the
moves that took more than F of the available clock (where a guard at F would have stopped them sooner), and
the rebuilt clock's lowest value (a negative one would mean the rebuild is wrong: those games had no time
losses).

    clock_share.py [PGN...] [--list FILE] [--overhead-ms 100] [--json OUT]   (--list: one PGN path per line)
"""
import argparse
import json
import re
import sys
from pathlib import Path

TC = re.compile(r'\[TimeControl "(\d+(?:\.\d+)?)\+(\d+(?:\.\d+)?)"\]')
TIME = re.compile(r'\{[^}]*?(\d+(?:\.\d+)?)s[,}]')
FRACTIONS = (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60)


def games(text):
    """(time control, move times in order) per game."""
    for chunk in re.split(r'\n(?=\[Event )', text):
        tc = TC.search(chunk)
        body = chunk.split('\n\n', 1)
        if not tc or len(body) < 2:
            continue
        times = [float(t) for t in TIME.findall(body[1])]
        if times:
            yield (float(tc.group(1)), float(tc.group(2))), times


def shares(base_s, inc_s, times, overhead_ms):
    """Per move: (share of the clock, share of the clock less the overhead, clock before the move in ms)."""
    clocks = [base_s * 1000.0, base_s * 1000.0]
    out = []
    for i, t in enumerate(times):
        side = i % 2
        before = clocks[side] + inc_s * 1000.0
        used = t * 1000.0
        available = max(1.0, before - overhead_ms)
        out.append((used / before, used / available, before))
        clocks[side] = before - used
    return out


def summarise(rows, n_games):
    rows.sort(key=lambda r: r[1])
    n = len(rows)

    def pct(p):
        return rows[min(n - 1, int(p * n))][1]

    return {'moves': n, 'games': n_games, 'max_share': max(r[0] for r in rows), 'max_share_available': rows[-1][1],
            'p50': pct(0.5), 'p99': pct(0.99), 'p999': pct(0.999), 'p9999': pct(0.9999),
            'lowest_clock_ms': min(r[2] for r in rows),
            'over_fraction': {f'{f:.2f}': sum(r[1] > f for r in rows) for f in FRACTIONS},
            'top10_share_available': [round(r[1], 4) for r in rows[-10:]]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('pgn', nargs='*', type=Path)
    parser.add_argument('--list', type=Path)
    parser.add_argument('--overhead-ms', type=float, default=100.0)
    parser.add_argument('--json', type=Path)
    a = parser.parse_args(argv)
    by_tc, n_games = {}, {}
    paths = list(a.pgn)
    if a.list:
        paths += [Path(x) for x in a.list.read_text(encoding='utf-8').splitlines() if x.strip()]
    for path in paths:
        for (base, inc), times in games(path.read_text(encoding='utf-8', errors='replace')):
            key = f'{base:g}+{inc:g}'
            by_tc.setdefault(key, []).extend(shares(base, inc, times, a.overhead_ms))
            n_games[key] = n_games.get(key, 0) + 1
    out = {key: summarise(rows, n_games[key]) for key, rows in sorted(by_tc.items())}
    text = json.dumps(out, indent=1)
    if a.json:
        a.json.write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
