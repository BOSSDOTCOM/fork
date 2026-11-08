# SPDX-License-Identifier: GPL-3.0-or-later
"""Near-window evaluation sites for the Boundary Refiner (ideas.md 59, step 3;
docs/research/boundary-refiner/step3-plan.md 3.1-3.3).

1. `games`: games of sealed data-generation shards (viriformat; Fork's own
   games, the only allowed source of training positions, DESIGN.md §5.3)
   written as game_replay.py's games.jsonl: id (shard#index), start FEN, UCI
   moves, the replayed colour (alternating by the pick's order) and depths
   (none). COUNT games picked by a seeded shuffle of every game of the
   shards, in the order given; decoded with tools/datagen/verify_games.py's
   independent decoder.
2. (game_replay.py `run` through the stats build with `--report
   counters,iterations,sites --sites N,M`, then crucial_points.py `sites`.)
3. `select`: the sites whose nearest finite bound lies within GAP cp of the
   logged static evaluation, COUNT of them by a seeded shuffle, written as
   sites.jsonl into each output folder (crucial_points.py `deep` labels every
   site of its folder; one folder per label budget). A site's position key
   is its FEN without the move counters. --dedup keeps the first site (in id
   order) of each position; --exclude drops the sites whose position appears
   in the given sites.jsonl files (the training split never shares a
   position with validation or test). Also printed: the picked sites'
   effective number under the training's decision weights,
   exp(-gap^2 / (2 h^2)) with h = 25 cp at main-search sites and 10 cp at
   quiescence sites (setting (a)'s margins).

    near_window_sites.py games SHARD.vf... OUT.jsonl --count N --seed S
    near_window_sites.py select ALL/sites.jsonl OUT... --gap 80 --count 3000 --seed S [--dedup]
                         [--exclude OTHER/sites.jsonl ...]

The labelling pilot of 2026-11-08 ran: games g3i-w05-val.vf --count 150
--seed 20261108; replay at 200,000 nodes, --sites 45000,90000; select
--gap 80 --count 3000 --seed 20261108 into n100k, n300k and n1m.
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'datagen'))

import crucial_points  # noqa: E402
import verify_games  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    g = sub.add_parser('games', help='games of a viriformat shard as games.jsonl')
    g.add_argument('shards', type=Path, nargs='+')
    g.add_argument('out', type=Path)
    g.add_argument('--count', type=int, required=True)
    g.add_argument('--seed', type=int, required=True)
    s = sub.add_parser('select', help='near-window sites into label folders')
    s.add_argument('sites', type=Path)
    s.add_argument('outs', type=Path, nargs='+')
    s.add_argument('--gap', type=int, required=True)
    s.add_argument('--count', type=int, required=True)
    s.add_argument('--seed', type=int, required=True)
    s.add_argument('--dedup', action='store_true', help='keep the first site of each position')
    s.add_argument('--exclude', type=Path, nargs='+', default=[], help='sites.jsonl files whose positions are left out')
    a = ap.parse_args(argv)

    if a.command == 'games':
        shards = [(shard, shard.read_bytes()) for shard in a.shards]
        offsets = []  # (shard, data, index in the shard, start) of every game, found without decoding
        for shard, data in shards:
            i, index = 0, 0
            while i < len(data):
                offsets.append((shard, data, index, i))
                index += 1
                i += 32
                while verify_games.u16(data, i) != 0:
                    i += 4
                i += 4
        order = list(range(len(offsets)))
        random.Random(a.seed).shuffle(order)
        plies = 0
        with open(a.out, 'w', encoding='utf-8') as f:
            for k, pick in enumerate(order[:a.count]):
                shard, data, index, i = offsets[pick]
                board, _result = verify_games.decode_board(data[i:i + 32])
                start = board.fen()
                i += 32
                moves = []
                while (code := verify_games.u16(data, i)) != 0:
                    i += 4
                    match = [m for m in board.legal_moves if verify_games.code_of(board, m) == code]
                    if len(match) != 1:
                        raise SystemExit(f'move code {code} matches {len(match)} moves in {board.fen()}')
                    moves.append(match[0].uci())
                    board.push(match[0])
                plies += len(moves)
                f.write(json.dumps({'id': f'{shard.name}#{index}', 'fen': start, 'moves': moves,
                                    'colour': 'w' if k % 2 == 0 else 'b', 'depths': [None] * len(moves)}) + '\n')
        print(f'{len(offsets)} games in {", ".join(shard.name for shard, _ in shards)}; '
              f'{min(a.count, len(offsets))} picked (seed {a.seed}) into {a.out}; {plies} plies')
        return 0

    # Only the sites within GAP are kept in memory (a training replay has millions).
    total, gap_of, near = 0, {}, []
    with open(a.sites, encoding='utf-8') as f:
        for line in f:
            site = json.loads(line)
            total += 1
            bound = crucial_points.nearest_bound(site['eval'], site['alpha'], site['beta'])
            if bound is not None and abs(site['eval'] - bound[1]) <= a.gap:
                gap_of[site['id']] = abs(site['eval'] - bound[1])
                near.append(site)
    key = lambda site: ' '.join(site['fen'].split()[:4])  # noqa: E731
    dropped = {}
    if a.exclude:
        excluded = {key(json.loads(line)) for f in a.exclude for line in f.read_text(encoding='utf-8').splitlines()}
        kept = [site for site in near if key(site) not in excluded]
        dropped['excluded'] = len(near) - len(kept)
        near = kept
    if a.dedup:
        seen, kept = set(), []
        for site in sorted(near, key=lambda site: site['id']):
            if key(site) not in seen:
                seen.add(key(site))
                kept.append(site)
        dropped['duplicates'] = len(near) - len(kept)
        near = kept
    random.Random(a.seed).shuffle(near)
    picked = sorted(near[:a.count], key=lambda site: site['id'])
    for out in a.outs:
        out.mkdir(parents=True, exist_ok=True)
        with open(out / 'sites.jsonl', 'w', encoding='utf-8') as f:
            for site in picked:
                f.write(json.dumps(site, separators=(',', ':')) + '\n')
    if dropped:
        print('dropped: ' + ', '.join(f'{v} {k}' for k, v in dropped.items()))
    print(f'{total} sites, {len(near)} within {a.gap} cp; {len(picked)} picked (seed {a.seed}), '
          f'{sum(gap_of[site["id"]] <= 25 for site in picked)} of them within 25 cp; '
          f'main {sum(site["kind"] == 0 for site in picked)}, quiescence {sum(site["kind"] == 1 for site in picked)}, '
          f'reused {sum(site["reused"] for site in picked)}')
    weights = [math.exp(-gap_of[site['id']] ** 2 / (2 * (25 if site['kind'] == 0 else 10) ** 2)) for site in picked]
    if weights:
        n_eff = sum(weights) ** 2 / sum(w * w for w in weights)
        print(f'decision weights (h = 25 cp main search, 10 cp quiescence): n_eff {n_eff:.0f} of {len(weights)} '
              f'({n_eff / len(weights):.2f})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
