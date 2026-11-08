# SPDX-License-Identifier: GPL-3.0-or-later
"""The time-management curve of §5.6 step 10 (think tank R8), derived from X6's data.

Input: the same game_replay.py runs X6 used (`--report iterations` of a stats
build, one `iteration_trace` row per finished iteration; DESIGN.md §5.7).
Everything is Fork's own: X6's label (the best move changes within the next
two iterations), its feature definitions (stability capped at 10, the
every-pass share's logit clipped to [5, 995] per mille, rows at depth >= 8,
mate and tablebase scores left out) and node_share_fit.py's IRLS fit.

Printed (and written with --json):
- the logistic fits: stability alone and stability + share (the literal
  variants), the same with depth (the engine's numerators: variant (a)
  stability, variant (b) stability + share) and depth alone (the
  normaliser), with AUC in sample and out of sample (two folds by game), and
  each coefficient in Q16 (x 65,536) as the engine stores it;
- the depth cap: the last depth holding at least 1% of the rows;
- the mean-spend balance of each variant: X6's searches replayed with nodes
  as the clock (soft budget B, hard 4B; the engine's rules: a hard stop
  inside an iteration, the soft check after it, the forced-move stop at 1/8,
  no iteration started once 5/3 of the elapsed passes the hard limit), the
  scale applied as the engine does (depth >= 8, depth capped, the floor),
  and the balance found by bisection so the mean spend equals the plain soft
  limit's, at B = 100k, 250k and 500k nodes; the engine uses their mean;
- at that balance, how often the move at the stop equals the search's final
  move (in sample; not Elo), and the scale's Spearman rho² against the label;
- the literal fits' balance at each B (the fallback, which drifts with B).

    tm_curve.py REPLAY_DIR... [--floor 360] [--json OUT]
"""
import argparse
import json
import math
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import node_share_fit as nsf  # noqa: E402

MIN_DEPTH = 8          # X6's primary depth
STABILITY_CAP = 10     # X6's cap
MATE_FLOOR = 29250     # TbWinScore - MaxPly (src/search/score_bounds.hpp), as X6
HARD_OVER_SOFT = 4     # src/tune/params.hpp HardOverSoft
GROWTH_THIRDS = 5      # src/tune/params.hpp IterationGrowthThirds
FORCED_FRACTION = 8    # src/tune/params.hpp ForcedMoveFraction
BUDGETS = (100_000, 250_000, 500_000)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('replay', nargs='+', type=Path)
    parser.add_argument('--floor', type=int, default=360)
    parser.add_argument('--json', type=Path, default=None)
    a = parser.parse_args(argv)
    records = []
    for d in a.replay:
        for f in sorted(d.glob('game-*.jsonl')):
            records.extend(json.loads(line) for line in f.read_text(encoding='utf-8').splitlines())
    rows = nsf.iteration_rows(records, MIN_DEPTH)
    ys = [r['y'] for r in rows]
    out = {'searches': len(records), 'rows': len(rows), 'base_rate': sum(ys) / len(ys)}

    # The depth cap: the last depth with at least 1% of the rows.
    per_depth = {}
    for r in rows:
        per_depth[r['depth']] = per_depth.get(r['depth'], 0) + 1
    depth_cap = max(d for d, n in per_depth.items() if n >= 0.01 * len(rows))
    out['depth_cap'] = depth_cap

    def features(r, model):
        f = [1.0]
        if 'stability' in model:
            f.append(min(r['stability'], STABILITY_CAP))
        if 'share' in model:
            f.append(nsf.share_logit(r['share_all']))
        if 'depth' in model:
            f.append(r['depth'])
        return f

    models = {'stability': ('stability',), 'stability_share': ('stability', 'share'),
              'a': ('stability', 'depth'), 'b': ('stability', 'share', 'depth'), 'depth': ('depth',)}
    folds = [zlib.crc32(r['game'].encode()) % 2 for r in rows]
    fits = {}
    for name, model in models.items():
        xs = [features(r, model) for r in rows]
        beta = nsf.fit_logistic_irls(xs, ys)
        oos = [0.0] * len(rows)
        for fold in (0, 1):
            train = [i for i in range(len(rows)) if folds[i] != fold]
            b = nsf.fit_logistic_irls([xs[i] for i in train], [ys[i] for i in train])
            for i in range(len(rows)):
                if folds[i] == fold:
                    oos[i] = nsf.sigmoid(sum(c * v for c, v in zip(b, xs[i])))
        fits[name] = beta
        out.setdefault('fits', {})[name] = {
            'terms': ['intercept', *model], 'coefficients': beta, 'q16': [round(c * 65536) for c in beta],
            'auc': nsf.rank_auc(nsf.predict(beta, xs), ys), 'auc_out_of_sample': nsf.rank_auc(oos, ys)}

    def raw_ratio(variant, stability, share_all, depth):
        """The engine's scale before balance and floor."""
        s, d = min(stability, STABILITY_CAP), min(depth, depth_cap)
        if variant in ('a', 'b'):
            z0 = fits['depth'][0] + fits['depth'][1] * d
            c = fits[variant]
            z1 = c[0] + c[1] * s + (c[2] * nsf.share_logit(share_all) + c[3] * d if variant == 'b' else c[2] * d)
            return nsf.sigmoid(z1) / nsf.sigmoid(z0)
        c = fits[variant]  # the literal fits, over the base rate
        z1 = c[0] + c[1] * s + (c[2] * nsf.share_logit(share_all) if variant == 'stability_share' else 0)
        return nsf.sigmoid(z1) / out['base_rate']

    def replay(its, budget, variant=None, balance=1.0):
        """(nodes spent, move at the stop) under the engine's rules, nodes as the clock."""
        hard = HARD_OVER_SOFT * budget
        spent, stability, best = 0, 0, None
        for it in its:
            if spent + it['nodes_iteration'] > hard:
                return hard, best
            spent += it['nodes_iteration']
            stability = stability + 1 if it['best'] == best else 1
            best = it['best']
            soft = budget
            if variant and it['depth'] >= MIN_DEPTH and abs(it['score']) < MATE_FLOOR:
                scale = max(a.floor / 1000, balance * raw_ratio(variant, stability, it['share_all'], it['depth']))
                soft = min(budget * scale, hard)
            if spent >= soft:
                return spent, best
            if it['root_moves'] == 1 and spent * FORCED_FRACTION >= budget:
                return spent, best
            if spent * GROWTH_THIRDS / 3 > hard:
                return spent, best
        return spent, best

    searches = [r['iterations'] for r in records if r.get('iterations')]

    def mean_spend(budget, variant=None, balance=1.0):
        return sum(replay(its, budget, variant, balance)[0] for its in searches) / len(searches)

    def agreement(budget, variant=None, balance=1.0):
        return sum(replay(its, budget, variant, balance)[1] == its[-1]['best'] for its in searches) / len(searches)

    for variant in ('a', 'b', 'stability', 'stability_share'):
        block = {}
        for budget in BUDGETS:
            target = mean_spend(budget)
            low, high = 0.2, 5.0
            for _ in range(40):
                mid = (low + high) / 2
                if mean_spend(budget, variant, mid) < target:
                    low = mid
                else:
                    high = mid
            block[budget] = {'balance': mid, 'agree': agreement(budget, variant, mid),
                             'agree_plain': agreement(budget)}
        block['mean_balance'] = sum(block[b]['balance'] for b in BUDGETS) / len(BUDGETS)
        scales = [max(a.floor / 1000, block['mean_balance'] * raw_ratio(variant, r['stability'], r['share_all'],
                                                                        r['depth'])) for r in rows]
        block['spearman_rho2'] = nsf.spearman_rho(scales, ys) ** 2
        out.setdefault('variants', {})[variant] = block

    text = json.dumps(out, indent=1)
    if a.json:
        a.json.write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
