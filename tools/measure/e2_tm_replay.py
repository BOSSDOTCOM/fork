# SPDX-License-Identifier: GPL-3.0-or-later
"""E2's long-search check (bug review 2026-11-11, E2; DESIGN.md decisions log 2026-11-11): does the time
manager's depth clamp (TimeScaleMaxDepth 19) under-spend once searches go deeper than X6's data?

Input: game_replay.py runs of a stats build with `--report iterations` at a large node budget R (one
`iteration_trace` row per finished iteration). Each search is replayed with nodes as the clock, as
tools/measure/tm_curve.py replays X6 (soft budget B, hard 4B; the engine's rules: the hard stop inside an
iteration, the soft check after each finished iteration, the forced-move stop at 1/8 of the soft limit, no
iteration started once 5/3 of the spend passes the hard limit), at budgets B = R/32, R/16, R/8, R/4. The scale
is the engine's own integer arithmetic (soft_scale_permille and scaled_soft_ms of src/search/time_budget.cpp,
ported line by line and checked against the bug review's E2 table by --self-test).

Rules replayed:
- plain: the soft limit unscaled (UseStabilityTime off);
- engine: variant (b) as shipped (stability and every-pass share, depth clamped at 19, floor 360, balance 996);
- unclamped: the same with the depth not clamped (the fits extrapolated).

Reported per budget: the mean spend over the plain rule's mean spend; the mean depth of the last finished
iteration at the stop; the share of stops where the floor bound the scale; agreement of the move at the stop with
the search's final move (the last finished iteration at R nodes; in sample, not Elo); the engine's balance that
restores the plain rule's mean spend (bisection) and its agreement there, minus the plain rule's, with a 95%
bootstrap interval over games. Also the calibration of "the best move changes within the next two iterations"
(X6's label) by depth band: the empirical rate, and its ratio for long-stable rows (stability >= 12) over the
band's rate, against the engine's mean unfloored scale for those rows.

    e2_tm_replay.py REPLAY_DIR [--json OUT] [--rounds 1000] [--seed 20261111]
    e2_tm_replay.py --self-test
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import node_share_fit as nsf  # noqa: E402

# src/search/time_budget.cpp at 26323e1 (the engine whose searches are replayed).
MIN_DEPTH, MAX_DEPTH, STAB_CAP, SHARE_MIN, SHARE_MAX, FLOOR = 8, 19, 72, 5, 995, 360
BALANCE_SHARE = 996
SHARE_FIT = (31102, -11639, -12129, -6772)  # intercept, per iteration, per logit, per ply (Q16)
DEPTH_FIT = (37191, -13876)
ONE = 1 << 30
LOG2E, LN2 = 94548, 45426
TB_WIN, MAX_PLY = 29500, 250  # src/search/score_bounds.hpp: is_tb_or_mate is |score| >= TbWinScore - MaxPly
HARD_OVER_SOFT, GROWTH_THIRDS, FORCED_FRACTION = 4, 5, 8  # src/tune/params.hpp


def cdiv(a, b):
    """C++ integer division (truncates toward zero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def fixed_log2(x):
    top = x.bit_length() - 1
    m = x << (30 - top) if top <= 30 else x >> (top - 30)
    fraction = 0
    for bit in range(15, -1, -1):
        m = (m * m) >> 30
        if m >= 2 * ONE:
            m >>= 1
            fraction |= 1 << bit
    return top * 65536 + fraction


def _roots():
    r = [2 * ONE]
    for _ in range(1, 17):
        v = r[-1] << 30
        x = v
        nxt = (x + v // x) // 2
        while nxt < x:
            x = nxt
            nxt = (x + v // x) // 2
        r.append(x)
    return r


ROOTS = _roots()


def fixed_exp2_neg(w):
    v = -w
    whole = v // 65536 if v >= 0 else -((-v + 65535) // 65536)
    fraction = v - whole * 65536
    result = ONE
    for j in range(1, 17):
        if fraction & (1 << (16 - j)):
            result = (result * ROOTS[j]) >> 30
    return result << whole if whole >= 0 else result >> -whole


def scale_permille(stability, share_all, depth, score, clamp_depth=True, floor=FLOOR, balance=BALANCE_SHARE):
    """soft_scale_permille(StabilityAndShare, ...); clamp_depth: True clamps at 19 (the engine), False not at all,
    an integer clamps there; floor=0 drops the floor."""
    if depth < MIN_DEPTH or abs(score) >= TB_WIN - MAX_PLY:
        return 1000
    if share_all <= 0:
        return 1000
    s = min(max(stability, 1), STAB_CAP)
    cap = MAX_DEPTH if clamp_depth is True else (clamp_depth or None)
    d = min(depth, cap) if cap else depth
    z1 = SHARE_FIT[0] + SHARE_FIT[1] * s + SHARE_FIT[3] * d
    p = min(max(share_all, SHARE_MIN), SHARE_MAX)
    logit = cdiv((fixed_log2(p) - fixed_log2(1000 - p)) * LN2, 65536)
    z1 += cdiv(SHARE_FIT[2] * logit, 65536)
    z0 = DEPTH_FIT[0] + DEPTH_FIT[1] * d
    num = (ONE + fixed_exp2_neg(cdiv(z0 * LOG2E, 65536))) * balance
    den = ONE + fixed_exp2_neg(cdiv(z1 * LOG2E, 65536))
    return max(floor, (num + den // 2) // den)


def scaled_soft(soft, hard, permille):
    if soft < 0 or hard < 0 or soft >= hard:
        return soft
    p = max(permille, 0)
    if p == 0:
        return 1
    whole, rest = soft // 1000, soft % 1000
    return min(max(whole * p + rest * p // 1000, 1), hard)


def replay(its, budget, rule, balance=BALANCE_SHARE):
    """(nodes spent, move at the stop, depth at the stop, floor bound at the stop) under the engine's rules."""
    hard = HARD_OVER_SOFT * budget
    spent, stability, best, depth, floored = 0, 0, None, 0, False
    for it in its:
        if spent + it['nodes_iteration'] > hard:
            return hard, best, depth, floored
        spent += it['nodes_iteration']
        stability = stability + 1 if it['best'] == best else 1
        best, depth = it['best'], it['depth']
        soft = budget
        floored = False
        if rule != 'plain':
            clamp = True if rule == 'engine' else (int(rule[3:]) if rule.startswith('cap') else False)
            p = scale_permille(stability, it['share_all'], it['depth'], it['score'], clamp, FLOOR, balance)
            floored = p == FLOOR and scale_permille(stability, it['share_all'], it['depth'], it['score'],
                                                    clamp, 0, balance) < FLOOR
            soft = scaled_soft(budget, hard, p)
        if spent >= soft:
            return spent, best, depth, floored
        if it['root_moves'] == 1 and spent * FORCED_FRACTION >= budget:
            return spent, best, depth, floored
        if spent * GROWTH_THIRDS / 3 > hard:
            return spent, best, depth, floored
    return spent, best, depth, floored


def load(replay_dir):
    records = []
    for f in sorted(Path(replay_dir).glob('game-*.jsonl')):
        records.extend(json.loads(line) for line in f.read_text(encoding='utf-8').splitlines() if line.strip())
    return [r for r in records if r.get('iterations')]


def summarise(searches, budget, rule, balance=BALANCE_SHARE):
    out = [replay(r['iterations'], budget, rule, balance) for r in searches]
    n = len(out)
    return {'spend': sum(o[0] for o in out) / n, 'agree': [o[1] == r['iterations'][-1]['best'] for o, r in
                                                          zip(out, searches)],
            'depth': sum(o[2] for o in out) / n, 'floored': sum(o[3] for o in out) / n}


def balance_for(searches, budget, target):
    low, high = 100, 20000
    for _ in range(30):
        mid = (low + high) // 2
        if summarise(searches, budget, 'engine', mid)['spend'] < target:
            low = mid + 1
        else:
            high = mid
    return low


def bootstrap_diff(games, a, b, rounds, seed):
    """95% percentile interval of mean(a) - mean(b) (paired per search) resampling games."""
    by_game = {}
    for g, x, y in zip(games, a, b):
        by_game.setdefault(g, []).append(x - y)
    keys = sorted(by_game)
    rng = random.Random(seed)
    stats = []
    for _ in range(rounds):
        tot = cnt = 0
        for _ in keys:
            v = by_game[keys[rng.randrange(len(keys))]]
            tot += sum(v)
            cnt += len(v)
        stats.append(tot / cnt)
    stats.sort()
    return [stats[int(0.025 * rounds)], stats[int(0.975 * rounds) - 1]]


def calibration(records):
    rows = nsf.iteration_rows(records, MIN_DEPTH)
    bands = [(8, 13), (14, 19), (20, 23), (24, 27), (28, 99)]
    out = []
    for lo, hi in bands:
        band = [r for r in rows if lo <= r['depth'] <= hi]
        if not band:
            continue
        rate = sum(r['y'] for r in band) / len(band)
        stable = [r for r in band if r['stability'] >= 12]
        entry = {'depths': f'{lo}-{hi}', 'rows': len(band), 'change_rate': rate,
                 'mean_stability': sum(r['stability'] for r in band) / len(band),
                 'share_stability_ge_12': len(stable) / len(band)}
        if stable and rate > 0:
            s_rate = sum(r['y'] for r in stable) / len(stable)
            entry['stable_rows'] = len(stable)
            entry['stable_change_rate'] = s_rate
            entry['stable_ratio_empirical'] = s_rate / rate
            for name, clamp in (('engine', True), ('unclamped', False)):
                entry[f'stable_scale_{name}_unfloored'] = sum(
                    scale_permille(r['stability'], r['share_all'], r['depth'], 0, clamp, 0) for r in stable) / (
                    1000 * len(stable))
        out.append(entry)
    return out


def self_test():
    # The bug review's E2 table (docs/research/bug-review-2026-11-11.md), depth >= 19: rows share 200/500/800/950,
    # columns s = 1, 3, 5, 8, 12, 16, 20.
    table = {200: [6387, 4756, 3487, 2141, 1089, 544, 360], 500: [5171, 3806, 2765, 1682, 849, 423, 360],
             800: [4150, 3025, 2181, 1317, 661, 360, 360], 950: [3213, 2321, 1663, 997, 498, 360, 360]}
    bad = 0
    for share, row in table.items():
        for s, want in zip((1, 3, 5, 8, 12, 16, 20), row):
            for depth in (19, 25, 40):
                got = scale_permille(s, share, depth, 0)
                if got != want:
                    bad += 1
                    print(f'mismatch share {share} s {s} depth {depth}: got {got}, want {want}')
    print('self-test', 'ok' if not bad else f'{bad} mismatches')
    return 0 if not bad else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('replay', nargs='?', type=Path)
    parser.add_argument('--json', type=Path)
    parser.add_argument('--rounds', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=20261111)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--caps', default='', help='also replay the scale clamped at each of these depths, e.g. 22,25,28')
    a = parser.parse_args(argv)
    if a.self_test:
        return self_test()
    records = load(a.replay)
    if not records:
        raise SystemExit('no searches with iteration rows')
    limit = min(r['nodes_limit'] for r in records)
    games = [r['game'] for r in records]
    out = {'searches': len(records), 'games': len(set(games)), 'nodes_limit': limit,
           'final_depth_mean': sum(r['iterations'][-1]['depth'] for r in records) / len(records),
           'budgets': {}, 'calibration': calibration(records)}
    for div in (32, 16, 8, 4):
        budget = limit // div
        plain = summarise(records, budget, 'plain')
        block = {'plain': {k: (sum(v) / len(v) if k == 'agree' else v) for k, v in plain.items()}}
        for rule in ('engine', 'unclamped') + tuple(f'cap{c}' for c in a.caps.split(',') if c):
            s = summarise(records, budget, rule)
            block[rule] = {k: (sum(v) / len(v) if k == 'agree' else v) for k, v in s.items()}
            block[rule]['spend_over_plain'] = s['spend'] / plain['spend']
        bal = balance_for(records, budget, plain['spend'])
        matched = summarise(records, budget, 'engine', bal)
        block['engine_matched'] = {'balance_permille': bal, 'spend_over_plain': matched['spend'] / plain['spend'],
                                   'agree': sum(matched['agree']) / len(records),
                                   'agree_minus_plain': (sum(matched['agree']) - sum(plain['agree'])) / len(records),
                                   'ci95': bootstrap_diff(games, matched['agree'], plain['agree'], a.rounds, a.seed)}
        shipped = summarise(records, budget, 'engine')
        block['engine']['agree_minus_plain_ci95'] = bootstrap_diff(games, shipped['agree'], plain['agree'], a.rounds,
                                                                   a.seed)
        out['budgets'][str(budget)] = block
    text = json.dumps(out, indent=1)
    if a.json:
        a.json.write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
