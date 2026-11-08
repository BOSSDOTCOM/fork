# SPDX-License-Identifier: GPL-3.0-or-later
"""The SPSA perturbation sizes from firing counts (think tank B7, O3; DESIGN.md §5.2, "SPSA on GitHub").

SPSA's largest avoidable loss is a perturbation c far from each parameter's 1-Elo half-width (B7 §0). Elo
curvature is expensive to measure, but each margin's mechanism is not: c_i is set so that theta_i +- c_i
changes the firing count of its own rule on the search bench by a fixed share (the target, 10%), a proxy
for equal curvature. Rule, fixed before any run: for h in 1, 2, 4 and 8 table steps (h cut so that
default +- h stays inside the range), rho(h) = (K(default + h) - K(default - h)) / (2 K(default)), K the
rule's count on `bench`; c is the h where |rho| reaches the target, log-linearly interpolated between the
bracketing points (linearly from 0 below the first); a rule that does not reach it at 8 steps gets c = 8
steps and is flagged insensitive (the owner decides whether it stays: about 0.17 Elo per parameter with
nothing to gain, B7 rule 7). Then c is at least 1 (integer resolution) and at most a quarter of the range
and the distance from the default to either bound. O3's own refutation is reported: every c within 30% of
its table step means the calibration can be skipped next time.

The engine must be a tuning build with the search counters (CMake FORK_TUNE=ON and FORK_SEARCH_STATS=ON):
each point is one UCI session (setoption, bench, quit), its `stats:` lines read from stderr. The bench is
deterministic and single-threaded; run it under the job supervisor as a measure job.

    spsa_calibrate.py --engine EXE --spec SPEC --out FILE [--target 0.10]
"""
import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spsa  # noqa: E402

# The count each margin's own decisions move (src/search/searcher.hpp, SearchCounters); a pair is a
# difference (the capture share of SEE pruning).
COUNTER_FOR_PARAM = {
    'RfpMargin': 'rfp_cuts',
    'FutilityOffset': 'futility_prunes',
    'FutilityGrowth': 'futility_prunes',
    'NullSurplusPerPly': 'null_surplus_plies',
    'AspirationHalfWidth': 'aspiration_researches',
    'QuietSeeFloor': 'quiet_see_prunes',
    'CaptureSeeFloor': ('see_prunes', 'quiet_see_prunes'),
    'LmpQuietAllowance': 'lmp_prunes',
}
_CUTS = re.compile(r'^stats: cuts rfp (\d+) null (\d+); prunes lmp (\d+) futility (\d+) see (\d+)', re.M)
_SPSA = re.compile(r'^stats: aspiration re-searches (\d+), null-move surplus plies (\d+), quiet SEE prunes (\d+)', re.M)


def parse_stats(text):
    """The counters of a FORK_SEARCH_STATS bench's stderr, by their SearchCounters names."""
    cuts, extra = _CUTS.search(text), _SPSA.search(text)
    if not cuts or not extra:
        raise ValueError('no search counters in the bench output (not a FORK_SEARCH_STATS build?)')
    names = ('rfp_cuts', 'null_cuts', 'lmp_prunes', 'futility_prunes', 'see_prunes', 'aspiration_researches',
             'null_surplus_plies', 'quiet_see_prunes')
    return dict(zip(names, (int(x) for x in cuts.groups() + extra.groups())))


def count_of(stats, counter):
    return stats[counter[0]] - stats[counter[1]] if isinstance(counter, tuple) else stats[counter]


def calibrated_c(points, target):
    """(c, insensitive) from [(h, rho)] in increasing h."""
    prev_h, prev_r = 0.0, 0.0
    for h, rho in points:
        r = abs(rho)
        if r >= target:
            if prev_r <= 0:  # the first point, or no change before it: linear from the point before
                return prev_h + (h - prev_h) * (target - prev_r) / (r - prev_r), False
            t = (math.log(target) - math.log(prev_r)) / (math.log(r) - math.log(prev_r))
            return math.exp(math.log(prev_h) + t * (math.log(h) - math.log(prev_h))), False
        prev_h, prev_r = h, r
    return points[-1][0], True


def calibrate(names, table, bench, target):
    """One entry per parameter. bench(settings) -> the stats dict of one bench with those option values."""
    base = bench({})
    out = []
    for name in names:
        default, lowest, highest, step = table[name]
        counter = COUNTER_FOR_PARAM[name]
        k0 = count_of(base, counter)
        points, rows = [], []
        for mult in (1, 2, 4, 8):
            h = min(mult * step, default - lowest, highest - default)
            if h <= 0 or (points and h == points[-1][0]):
                continue
            minus = count_of(bench({name: default - h}), counter)
            plus = count_of(bench({name: default + h}), counter)
            rho = (plus - minus) / (2 * k0) if k0 else 0.0
            points.append((h, rho))
            rows.append([h, minus, plus, round(rho, 5)])
        c, insensitive = calibrated_c(points, target) if points else (1.0, True)
        c = min(max(c, 1.0), (highest - lowest) / 4, default - lowest, highest - default)
        out.append({'name': name, 'start': default, 'step': step, 'counter': counter if isinstance(counter, str)
                    else f'{counter[0]} - {counter[1]}', 'base': k0, 'points': rows, 'c': round(c, 1),
                    'insensitive': insensitive})
    return out


def run_bench(engine, settings):
    lines = [f'setoption name {k} value {v}' for k, v in settings.items()] + ['bench', 'quit']
    r = subprocess.run([engine], input='\n'.join(lines) + '\n', capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f'{engine} exited {r.returncode}: {r.stderr[-500:]}')
    return parse_stats(r.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--engine', required=True)
    ap.add_argument('--spec', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--target', type=float, default=0.10)
    a = ap.parse_args(argv)
    raw = spsa.read_json(a.spec)
    table = spsa.table_from_header((HERE.parents[1] / 'src' / 'tune' / 'params.hpp').read_text(encoding='utf-8'))
    names = [p['name'] for p in raw['params']]
    missing = [n for n in names if n not in COUNTER_FOR_PARAM or n not in table]
    if missing:
        print(f'spsa_calibrate: no counter or no table row for {", ".join(missing)}', file=sys.stderr)
        return 1
    options = subprocess.run([a.engine], input='uci\nquit\n', capture_output=True, text=True).stdout
    absent = [n for n in names if f'option name {n} type spin' not in options]
    if absent:
        print(f'spsa_calibrate: {a.engine} has no spin option {", ".join(absent)} (not a FORK_TUNE build?)',
              file=sys.stderr)
        return 1
    result = calibrate(names, table, lambda s: run_bench(a.engine, s), a.target)
    print('| parameter | counter | count at default | rho at 1, 2, 4, 8 steps | c | c / step |')
    print('|---|---|---|---|---|---|')
    for e in result:
        rhos = ', '.join(f'{row[3]:+.3f}' for row in e['points'])
        flag = ' (insensitive)' if e['insensitive'] else ''
        print(f'| {e["name"]} | {e["counter"]} | {e["base"]} | {rhos} | {e["c"]}{flag} | {e["c"] / e["step"]:.2f} |')
    near = all(0.7 <= e['c'] / e['step'] <= 1.3 for e in result)
    print('O3 refutation check: every c within 30% of its table step: ' + ('yes (skip O3 next time)' if near else 'no'))
    spsa.write_json(a.out, {'target': a.target, 'engine_build': hashlib.sha256(Path(a.engine).read_bytes()).hexdigest()[:16],
                            'params': result})
    return 0


if __name__ == '__main__':
    sys.exit(main())
