# SPDX-License-Identifier: GPL-3.0-or-later
"""Near-window evaluation sites for the Boundary Refiner (ideas.md 59, step 3;
docs/research/boundary-refiner/step3-plan.md 3.1-3.3).

1. `games`: games of a sealed data-generation shard (viriformat; Fork's own
   games, the only allowed source of training positions, DESIGN.md §5.3)
   written as game_replay.py's games.jsonl: id (shard#index), start FEN, UCI
   moves, the replayed colour (alternating by the pick's order) and depths
   (none). COUNT games picked by a seeded shuffle; decoded with
   tools/datagen/verify_games.py's independent decoder.
2. (game_replay.py `run` through the stats build with `--report
   counters,iterations,sites --sites N,M`, then crucial_points.py `sites`.)
3. `select`: the sites whose nearest finite bound lies within GAP cp of the
   logged static evaluation, COUNT of them by a seeded shuffle, written as
   sites.jsonl into each output folder (crucial_points.py `deep` labels every
   site of its folder; one folder per label budget).

    near_window_sites.py games SHARD.vf OUT.jsonl --count N --seed S
    near_window_sites.py select ALL/sites.jsonl OUT... --gap 80 --count 3000 --seed S

The labelling pilot of 2026-11-08 ran: games g3i-w05-val.vf --count 150
--seed 20261108; replay at 200,000 nodes, --sites 45000,90000; select
--gap 80 --count 3000 --seed 20261108 into n100k, n300k and n1m.
"""
import argparse
import json
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
    g.add_argument('shard', type=Path)
    g.add_argument('out', type=Path)
    g.add_argument('--count', type=int, required=True)
    g.add_argument('--seed', type=int, required=True)
    s = sub.add_parser('select', help='near-window sites into label folders')
    s.add_argument('sites', type=Path)
    s.add_argument('outs', type=Path, nargs='+')
    s.add_argument('--gap', type=int, required=True)
    s.add_argument('--count', type=int, required=True)
    s.add_argument('--seed', type=int, required=True)
    a = ap.parse_args(argv)

    if a.command == 'games':
        data = a.shard.read_bytes()
        offsets, i = [], 0  # each game's start, found without decoding
        while i < len(data):
            offsets.append(i)
            i += 32
            while verify_games.u16(data, i) != 0:
                i += 4
            i += 4
        order = list(range(len(offsets)))
        random.Random(a.seed).shuffle(order)
        plies = 0
        with open(a.out, 'w', encoding='utf-8') as f:
            for k, index in enumerate(order[:a.count]):
                i = offsets[index]
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
                f.write(json.dumps({'id': f'{a.shard.name}#{index}', 'fen': start, 'moves': moves,
                                    'colour': 'w' if k % 2 == 0 else 'b', 'depths': [None] * len(moves)}) + '\n')
        print(f'{len(offsets)} games in {a.shard.name}; {min(a.count, len(offsets))} picked (seed {a.seed}) '
              f'into {a.out}; {plies} plies')
        return 0

    sites = [json.loads(line) for line in a.sites.read_text(encoding='utf-8').splitlines()]
    gap_of = {}
    for site in sites:
        near = crucial_points.nearest_bound(site['eval'], site['alpha'], site['beta'])
        if near is not None:
            gap_of[site['id']] = abs(site['eval'] - near[1])
    near = [site for site in sites if site['id'] in gap_of and gap_of[site['id']] <= a.gap]
    random.Random(a.seed).shuffle(near)
    picked = sorted(near[:a.count], key=lambda site: site['id'])
    for out in a.outs:
        out.mkdir(parents=True, exist_ok=True)
        with open(out / 'sites.jsonl', 'w', encoding='utf-8') as f:
            for site in picked:
                f.write(json.dumps(site, separators=(',', ':')) + '\n')
    print(f'{len(sites)} sites, {len(near)} within {a.gap} cp; {len(picked)} picked (seed {a.seed}), '
          f'{sum(gap_of[site["id"]] <= 25 for site in picked)} of them within 25 cp; '
          f'main {sum(site["kind"] == 0 for site in picked)}, quiescence {sum(site["kind"] == 1 for site in picked)}, '
          f'reused {sum(site["reused"] for site in picked)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
