# SPDX-License-Identifier: GPL-3.0-or-later
"""Test double of the SPSA shards (tools/github/spsa_shard.py) for the tests of tools/github/spsa.py and
tools/github/spsa_run.sh: writes one run's shard result.json files, each draw with the signs and values its
seed gives (the real functions of spsa.py) and games played on a synthetic Elo landscape instead of by
engines. No engine, no fastchess.

    fake_spsa_shard.py DISPATCH_JSON OUTDIR [LANDSCAPE_JSON]

LANDSCAPE_JSON: {name: [optimum, half_width, steep]}: Elo(theta) = -sum(((theta - optimum) / w)^2), with w
divided by `steep` above the optimum (an asymmetric landscape). Without it every game is a draw-heavy coin.
Each game: a draw with probability 0.6, else a win with the probability that gives the logistic expected
score of the Elo difference. Seeded from the draw's seed, so the same dispatch always gives the same games.
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spsa  # noqa: E402


def elo(values, names, landscape):
    total = 0.0
    for name, v in zip(names, values):
        if name in landscape:
            opt, w, steep = landscape[name]
            total -= ((v - opt) / (w / steep if v > opt else w)) ** 2
    return total


def game(rng, diff):
    """Points for the first side, from the Elo difference."""
    expected = 1 / (1 + 10 ** (-diff / 400))
    draw = 0.6
    u = rng.random()
    if u < draw:
        return 0.5
    return 1.0 if rng.random() < (expected - draw / 2) / (1 - draw) else 0.0


def pair_ptnml(rng, diff, pairs):
    ptnml = [0] * 5
    for _ in range(pairs):
        ptnml[int(round(2 * (game(rng, diff) + game(rng, diff))))] += 1
    return ptnml


def shard_result(disp, shard, landscape):
    tuned, _ = spsa.parse_params(disp['params'])
    names = [n for n, _, _ in tuned]
    k = int(disp['draw_pairs'])
    per = spsa.shard_plan(int(disp['games']), int(disp['shards']), k)
    start = int(disp['openings']) + shard * per
    records = []
    for j in range(per // k):
        seed = spsa.pair_seed(disp['label'], disp['commit'], disp['stage'], shard, j)
        signs, plus, minus = spsa.perturbed_values(seed, tuned)
        rng = random.Random(seed)
        ptnml = pair_ptnml(rng, elo(plus, names, landscape) - elo(minus, names, landscape), k)
        records.append({'index': j, 'line': start + j * k, 'signs': ''.join('+' if s > 0 else '-' for s in signs),
                        'plus': plus, 'minus': minus, 'ptnml': ptnml, 'time_losses': 0, 'abnormal': 0})
    meta = {'label': disp['label'], 'commit': disp['commit'], 'stage': str(disp['stage']), 'params': disp['params'],
            'shard': str(shard), 'shards': str(disp['shards']), 'opening_start': str(start),
            'opening_end': str(start + per - 1), 'draw_pairs': str(k), 'tc': disp['tc'], 'hash': str(disp['hash']),
            'tables': '3-4-5', 'book': 'fake.epd', 'book_seed': 'none', 'book_sha': 'fake', 'runner': 'fake'}
    ptnml = [sum(r['ptnml'][i] for r in records) for i in range(5)]
    return {'status': 'done', 'records': records, 'ptnml': ptnml, 'meta': meta}


def write_run(disp, out, landscape=None):
    for shard in range(int(disp['shards'])):
        folder = Path(out) / f'spsa-{disp["stage"]}-{shard}'
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / 'result.json', 'w', encoding='utf-8') as f:
            json.dump(shard_result(disp, shard, landscape or {}), f)


if __name__ == '__main__':
    with open(sys.argv[1], encoding='utf-8') as f:
        dispatch = json.load(f)
    land = None
    if len(sys.argv) > 3:
        with open(sys.argv[3], encoding='utf-8') as f:
            land = json.load(f)
    write_run(dispatch, sys.argv[2], land)
