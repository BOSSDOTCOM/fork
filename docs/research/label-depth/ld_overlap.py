# SPDX-License-Identifier: GPL-3.0-or-later
"""Checks that a resumed label-depth segment replays no game of an earlier one (docs/research/label-depth/probe.md,
"Stop and resume"), from the shards' bytes:
- start position: the viriformat start board's first 28 bytes (pieces, side to move, en passant, halfmove and
  fullmove counters), i.e. the position after the opening line and its random plies;
- identical game: the same start position and the same move list (every recorded move);
- also the games sharing the start position and their first 8 moves.
The opening line itself (before the random plies) is not in the shards. Its overlap is estimated from the two
seeds' shuffles of the full book (fork_datagen: game g opens from book[perm[g]], perm a Fisher-Yates shuffle from
splitmix_next(state = seed)) over the game indices each segment played, taken as the written games times PLAYED
(written games / games played, from the probe's run jsons: decided openings end before any record and are not
written); an estimate.

    python -I ld_overlap.py --seeds S1 S2 [--book-lines N] ARM SEG1_DIR SEG2_DIR [ARM SEG1_DIR SEG2_DIR ...]
    (exit 1 if any identical game exists)
"""
import json
import math
import re
import sys
from array import array
from pathlib import Path

SHARD = re.compile(r'.*-w(?P<worker>\d{2})(-\d{4})?(-val)?\.vf$')
MASK = (1 << 64) - 1
PLAYED = {'d20': 14872 / 12188, 'd50': 6576 / 5410, 'd100': 3560 / 2939}  # probe: ends / written games
FIRST = 8


def games(path):
    """(position key, first-8-moves key, game key) per complete game of a shard."""
    data = Path(path).read_bytes()
    i, n = 0, len(data)
    while i + 32 <= n and int.from_bytes(data[i:i + 8], 'little'):
        pos = data[i:i + 28]
        j, moves = i + 32, []
        closed = False
        while j + 4 <= n:
            code = data[j] | data[j + 1] << 8
            j += 4
            if code == 0:
                closed = True
                break
            moves.append(code)
        if not closed:
            return
        mv = array('H', moves).tobytes()
        yield pos, pos + mv[:2 * FIRST], pos + mv
        i = j


def keys(d):
    out, workers = [], {}
    for f in sorted(Path(d).glob('*.vf')):
        m = SHARD.match(f.name)
        w = int(m['worker']) if m else -1
        for k in games(f):
            out.append(k)
            workers[w] = workers.get(w, 0) + 1
    return out, workers


def finalize(z):
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return z ^ (z >> 31)


def perm_prefix(n, seed, upto):
    """The first `upto` entries of fork_datagen's opening order for an n-line book."""
    order = array('I', range(n))
    state = seed
    for i in range(n - 1, 0, -1):
        state = (state + 0x9E3779B97F4A7C15) & MASK
        j = finalize(state) % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order[:upto]


def main(argv):
    i = argv.index('--seeds')
    s1, s2 = int(argv[i + 1]), int(argv[i + 2])
    argv = argv[:i] + argv[i + 3:]
    nbook = 13943421
    if '--book-lines' in argv:
        i = argv.index('--book-lines')
        nbook = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    arms = [argv[k:k + 3] for k in range(0, len(argv), 3)]
    rows, ranges = [], {}
    for arm, d1, d2 in arms:
        k1, w1 = keys(d1)
        k2, w2 = keys(d2)
        pos1 = {k[0] for k in k1}
        first1 = {k[1] for k in k1}
        game1 = {k[2] for k in k1}
        row = {'arm': arm, 'seg1_games': len(k1), 'seg2_games': len(k2),
               'seg1_games_per_worker': w1, 'seg2_games_per_worker': w2,
               'seg2_same_start_position': sum(k[0] in pos1 for k in k2),
               f'seg2_same_start_and_first_{FIRST}_moves': sum(k[1] in first1 for k in k2),
               'seg2_identical_games': sum(k[2] in game1 for k in k2),
               'seg1_distinct_start_positions': len(pos1)}
        f = PLAYED.get(arm.split('-')[-1], 1.0)
        row['seg1_played_indices_est'] = math.ceil(len(k1) * f)
        row['seg2_played_indices_est'] = math.ceil(len(k2) * f)
        ranges[arm] = (row['seg1_played_indices_est'], row['seg2_played_indices_est'])
        rows.append(row)
    top1 = max(r[0] for r in ranges.values())
    top2 = max(r[1] for r in ranges.values())
    p1 = perm_prefix(nbook, s1, top1)
    p2 = perm_prefix(nbook, s2, top2)
    for row in rows:
        a1, a2 = ranges[row['arm']]
        used1 = set(p1[:a1])
        row['seg2_book_line_also_in_seg1_est'] = sum(1 for x in p2[:a2] if x in used1)
        row['seg2_book_line_also_in_seg1_expected'] = round(a1 * a2 / nbook, 1)
    print(json.dumps(rows, indent=1))
    return 1 if any(r['seg2_identical_games'] for r in rows) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
