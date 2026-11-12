# SPDX-License-Identifier: GPL-3.0-or-later
"""The drift tables' passive ranking (tier 2: think tank R34, engine survey
E4; DESIGN.md §5.7 and the constants table). Declared before its run.

A stats build with FORK_DRIFT_REPORT=1 lets all four drift tables (pieces
per colour, minor, major, threat; src/search/eval_drift.hpp) learn at the
nodes where the search's result shows its estimate erred, without applying
any, so the search keeps its tree and each table is judged against results
it did not shape (tools/drift_measure.py's passive method, branch
tier2/drift, rewritten). game_replay.py replays Fork's own STC games with
`--report counters,ledger,drift`; with the decision ledger (X10) every
sampled RFP or futility candidate row also carries each table's pruning
eval (`drift_ledger`), and a node is a candidate when the raw pruning eval
or any table's would make it one.

Readings, per table (the threat table and the three material ones):

1. **Decision accuracy (primary).** At each ledger row the raw decision
   fires when the gap (RFP: pruning eval minus beta; futility: alpha minus
   it) reaches the margin; the table's decision fires when its own gap
   does. Where they differ the table flips the decision. A flip is right
   when the decision it takes is the correct one: a new prune that is not
   wrong (prune_ledger_fit.wrong_flag), or a removed prune that was wrong;
   otherwise it is a wrong flip. The table's gain G is (right flips - wrong
   flips) per 1,000 ledger rows, RFP and futility rows pooled; also
   reported as a share of its flips and per technique.
2. **Tail fitness.** Over the learning nodes whose raw error exceeds 100 cp
   (I5's tail bins), the table's summed error over the raw eval's (lower is
   better; 1 = no change).
3. **Summed fitness** (the pawn drift measurement's, kept for comparison
   with its 0.919), and the same at half the learned term (whether a
   smaller share would have erred less), reported only.

95% intervals: a bootstrap over games, seed 20261111, 1,000 rounds,
percentile intervals; the paired difference of two tables' G uses the same
resamples.

**Declared rule (owner, 2026-11-11: the ranking orders the tests only; no
table is dropped on it).** Order the tables by G, largest first. Then one
pass from the top: where two neighbours' paired G difference has a 95%
interval that contains 0 and the lower one has the better (smaller) tail
fitness, they swap. The result is the order of their head-to-heads and
SPRTs (night items 19-corr-a-*, 19-corr-b-*, ...). Reported, not acted on:
R34's kill reading (a table whose gain is under 2% of its flipped
decisions) and its prediction that the best key passes LTC.

**Declared settings** (before the run): the stats build (clang-stats) of
this commit; 120 games of the current default network's STC SPRT
r8b-rft-stc (the "test" engine, r8brft1), chosen by
`game_replay.py games ~/fork-data/sprt/r8b-rft-stc OUT --count 120 --seed
20261111` (7,943 positions); `game_replay.py run` at 200,000 nodes per
move, `--report counters,ledger,drift --ledger-every 512` (X10's rate),
Hash 16, Syzygy 3-4-5, 2 jobs. The ranking reads this run only. Report
only, if time allows: the first 60 of those games at 1,000,000 nodes (an
LTC proxy, I5's reading iv).

    drift_rank.py REPLAY_DIR [--rounds 1000] [--json OUT]
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine_lines import DRIFT_TABLES  # noqa: E402
from prune_ledger_fit import wrong_flag  # noqa: E402

SEED = 20261111
TAIL_NAME = {t: f'drift_tail_{t}' for t in DRIFT_TABLES}


def game_tallies(records):
    """One game's tallies: counter sums and, per table, rows, right and wrong flips by technique."""
    counters = {}
    flips = {t: {'rfp': [0, 0], 'futility': [0, 0]} for t in DRIFT_TABLES}
    rows = {'rfp': 0, 'futility': 0}
    for record in records:
        for name, value in (record.get('counters') or {}).items():
            if name.startswith('drift_'):
                counters[name] = counters.get(name, 0) + value
        for row in record.get('ledger') or []:
            drift = row.get('drift')
            if drift is None:
                continue
            technique = row['technique']
            rows[technique] += 1
            gap = row['excess'] if technique == 'rfp' else row['deficit']
            raw_fires = gap >= row['margin']
            wrong = wrong_flag(row)
            for t in DRIFT_TABLES:
                fires = drift[t] >= row['margin']
                if fires == raw_fires:
                    continue
                # A new prune is right unless it is wrong; a removed prune is right only if it was wrong.
                right = (not wrong) if fires else bool(wrong)
                flips[t][technique][0 if right else 1] += 1
    return {'counters': counters, 'flips': flips, 'rows': rows}


def summarize(games):
    """The readings over a list of game tallies."""
    counters = {}
    rows = {'rfp': 0, 'futility': 0}
    flips = {t: {'rfp': [0, 0], 'futility': [0, 0]} for t in DRIFT_TABLES}
    for g in games:
        for name, value in g['counters'].items():
            counters[name] = counters.get(name, 0) + value
        for k in rows:
            rows[k] += g['rows'][k]
        for t in DRIFT_TABLES:
            for k in ('rfp', 'futility'):
                flips[t][k][0] += g['flips'][t][k][0]
                flips[t][k][1] += g['flips'][t][k][1]
    total_rows = rows['rfp'] + rows['futility']
    out = {'rows': rows, 'samples': counters.get('drift_samples', 0),
           'tail_samples': counters.get('drift_tail_samples', 0), 'tables': {}}
    raw = counters.get('drift_error_raw', 0)
    raw_tail = counters.get('drift_tail_raw', 0)
    for t in DRIFT_TABLES:
        right = flips[t]['rfp'][0] + flips[t]['futility'][0]
        wrong = flips[t]['rfp'][1] + flips[t]['futility'][1]
        out['tables'][t] = {
            'gain_per_1000': 1000.0 * (right - wrong) / total_rows if total_rows else 0.0,
            'right': right, 'wrong': wrong,
            'gain_share_of_flips': (right - wrong) / (right + wrong) if right + wrong else 0.0,
            'by_technique': {k: {'right': flips[t][k][0], 'wrong': flips[t][k][1],
                                 'gain_per_1000': 1000.0 * (flips[t][k][0] - flips[t][k][1]) / rows[k]
                                 if rows[k] else 0.0} for k in ('rfp', 'futility')},
            'tail_fitness': counters.get(TAIL_NAME[t], 0) / raw_tail if raw_tail else 1.0,
            'fitness': counters.get(f'drift_error_{t}', 0) / raw if raw else 1.0,
            'half_fitness': counters.get(f'drift_half_{t}', 0) / raw if raw else 1.0,
        }
    return out


def percentile(values, q):
    values = sorted(values)
    i = min(len(values) - 1, max(0, int(round(q * (len(values) - 1)))))
    return values[i]


def rank(games, rounds=1000):
    """The readings, their bootstrap intervals and the declared order."""
    point = summarize(games)
    rng = random.Random(SEED)
    draws = []
    for _ in range(rounds):
        sample = [games[rng.randrange(len(games))] for _ in games]
        draws.append(summarize(sample))
    for t in DRIFT_TABLES:
        entry = point['tables'][t]
        for key in ('gain_per_1000', 'tail_fitness', 'fitness'):
            vals = [d['tables'][t][key] for d in draws]
            entry[key + '_ci'] = [percentile(vals, 0.025), percentile(vals, 0.975)]
    order = sorted(DRIFT_TABLES, key=lambda t: -point['tables'][t]['gain_per_1000'])
    pairs = []
    for i in range(len(order) - 1):
        a, b = order[i], order[i + 1]
        diffs = [d['tables'][a]['gain_per_1000'] - d['tables'][b]['gain_per_1000'] for d in draws]
        ci = [percentile(diffs, 0.025), percentile(diffs, 0.975)]
        tied = ci[0] <= 0 <= ci[1]
        swap = tied and point['tables'][b]['tail_fitness'] < point['tables'][a]['tail_fitness']
        pairs.append({'upper': a, 'lower': b, 'diff_ci': ci, 'tied': tied, 'swapped': swap})
        if swap:
            order[i], order[i + 1] = b, a
    point['order'] = order
    point['pairs'] = pairs
    point['rounds'] = rounds
    point['games'] = len(games)
    point['kill_reading'] = {t: point['tables'][t]['gain_share_of_flips'] < 0.02 for t in DRIFT_TABLES}
    return point


def load_games(replay_dir):
    games = []
    for f in sorted(Path(replay_dir).glob('game-*.jsonl')):
        records = [json.loads(line) for line in f.read_text(encoding='utf-8').splitlines() if line.strip()]
        games.append(game_tallies(records))
    return games


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('replay', type=Path)
    parser.add_argument('--rounds', type=int, default=1000)
    parser.add_argument('--json', type=Path)
    a = parser.parse_args(argv)
    games = load_games(a.replay)
    if not games:
        raise SystemExit(f'no game-*.jsonl in {a.replay}')
    result = rank(games, a.rounds)
    print(f"{result['games']} games, {result['rows']['rfp']} RFP and {result['rows']['futility']} futility rows, "
          f"{result['samples']} learning nodes ({result['tail_samples']} in the tail)")
    print('table    G/1000 rows [95%]          right  wrong  share   RFP G  fut. G  tail fit [95%]         '
          'fit    half fit')
    for t in DRIFT_TABLES:
        e = result['tables'][t]
        print(f"{t:8} {e['gain_per_1000']:+7.3f} [{e['gain_per_1000_ci'][0]:+.3f}, {e['gain_per_1000_ci'][1]:+.3f}]"
              f" {e['right']:6} {e['wrong']:6} {e['gain_share_of_flips']:+.3f}"
              f" {e['by_technique']['rfp']['gain_per_1000']:+7.3f} {e['by_technique']['futility']['gain_per_1000']:+7.3f}"
              f"  {e['tail_fitness']:.4f} [{e['tail_fitness_ci'][0]:.4f}, {e['tail_fitness_ci'][1]:.4f}]"
              f" {e['fitness']:.4f} {e['half_fitness']:.4f}")
    for p in result['pairs']:
        print(f"{p['upper']} - {p['lower']}: G difference 95% [{p['diff_ci'][0]:+.3f}, {p['diff_ci'][1]:+.3f}]"
              f"{' tied' if p['tied'] else ''}{', swapped by tail fitness' if p['swapped'] else ''}")
    print('order: ' + ', '.join(result['order']))
    print('R34 kill reading (gain under 2% of flips): ' +
          ', '.join(f"{t} {'yes' if v else 'no'}" for t, v in result['kill_reading'].items()))
    if a.json:
        a.json.write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
