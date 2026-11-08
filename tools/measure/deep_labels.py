# SPDX-License-Identifier: GPL-3.0-or-later
"""Deep labels of near-window sites for the Boundary Refiner (ideas.md 59,
step 3; docs/research/boundary-refiner/step3-plan.md 3.3 and section 5's P0).

The labels come from crucial_points.py `deep` (the site's FEN searched to N
nodes, one thread, Hash 16, `ucinewgame` before each; side to move's view;
mates flagged), by a pinned engine copied outside build/ and checked here
before the first label and after the last; a mismatch voids the labels.

1. `check`: the pinned engine's SHA-256 against the expected one, and its
   bench against the repository's reference for its network.
2. `budget`: the label budget N of a pilot folder holding n100k, n300k and
   n1m (each sites.jsonl and deep.tsv) and the replay's rep folder: the
   smallest of 100k and 300k whose label lies on the 1M label's side of the
   site's nearest bound at no less than 90% of the gated sites (window gap
   <= 25 cp) and whose win-probability residual correlates with the 1M one
   at 0.8 or more; 1M if neither. Also P0's residual checks on the pilot's
   own sites (with each search's root score movement from the replay's
   iteration rows) and the decision-weighted centring mean.
3. `p0`: on a crucial-point folder (sites.jsonl, deep.tsv, seed-<name>.tsv):
   the residual deep - static near the window (perspective, mates and
   tables, selection by window gap and by kind of site) and, given the
   seeds s512ppr3, s512r2 and s512x, the net flips of S512+X over each base
   at the sites within 25 cp of that base's own evaluation.
4. `weights`: the folders of one split (validation: the pilot's n1m and
   val/n1m together) get each labelled site's training and acceptance
   weights, written to weights.tsv in its folder as id<TAB>training<TAB>
   acceptance (the plan's labelling section, "The training mix" and "A8 and
   the acceptance weighting"; owner, 2026-11-08). Mate-flagged labels and
   the table band (|label| >= 29,250) weigh 0 in both. Training: the
   closeness kernel exp(-gap^2 / (2 h^2)), h = 25 cp at main-search sites
   and 17 cp at quiescence sites, times one factor per kind that makes the
   kinds' totals 1.68 : 2.13 (the oracle's call rates at gate (a), in % of
   nodes), the weights averaging 1 over the sites used. Acceptance
   (deployment weighting): 1 inside gate (a)'s margins (main search 25 cp,
   quiescence 10 cp, inclusive), 0 outside, times one factor per kind for
   the same 1.68 : 2.13 totals, averaging 1 over the sites inside. Prints
   the counts, the factors and the n_eff: A8's (the kernel alone), with the
   factors, and the acceptance weights'.

    deep_labels.py check ENGINE --sha256 HEX
    deep_labels.py budget PILOT_DIR
    deep_labels.py p0 DIR
    deep_labels.py weights DIR...

Win probability: sigmoid(cp / 89), S512ppr3's output scale (the plan's 3.7).
"""
import argparse
import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))

import crucial_points  # noqa: E402

TB_FLOOR = 29250  # score_bounds.hpp: TbWinScore - MaxPly


def material(board):
    """The side to move's material balance in centipawns (pawn 100, minor 300, rook 500, queen 900)."""
    values = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300, chess.ROOK: 500, chess.QUEEN: 900}
    return sum(values.get(p.piece_type, 0) * (1 if p.color == board.turn else -1) for p in board.piece_map().values())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    c = sub.add_parser('check', help="the pinned engine's hash and bench")
    c.add_argument('engine', type=Path)
    c.add_argument('--sha256', required=True)
    b = sub.add_parser('budget', help='the label budget and P0 on a pilot folder')
    b.add_argument('pilot', type=Path)
    p = sub.add_parser('p0', help="P0's checks on a crucial-point folder")
    p.add_argument('dir', type=Path)
    w = sub.add_parser('weights', help="a split's training and acceptance weights (weights.tsv in each folder)")
    w.add_argument('dir', type=Path, nargs='+')
    a = ap.parse_args(argv)

    wp = lambda cp: 1 / (1 + math.exp(-max(-4000, min(4000, cp)) / 89))  # noqa: E731

    def describe(values):
        if not values:
            return 'n 0'
        trimmed = [v for v in values if abs(v) <= 1000]
        return (f'n {len(values)}, mean {statistics.fmean(values):+.1f}, median {statistics.median(values):+.1f}, '
                f'mean of |r| <= 1000 {statistics.fmean(trimmed) if trimmed else float("nan"):+.1f}, '
                f'share r > 0 {sum(v > 0 for v in values) / len(values):.2f}')

    def above(value, near):
        side, bound = near
        return value >= bound if side == 'beta' else value > bound

    def read_labels(path):
        out = {}
        for line in path.read_text(encoding='utf-8').splitlines():
            i, v, m, d = line.split('\t')
            out[int(i)] = (int(v), int(m), int(d))
        return out

    if a.command == 'check':
        digest = hashlib.sha256(a.engine.read_bytes()).hexdigest()
        if digest != a.sha256.lower():
            raise SystemExit(f'{a.engine}: SHA-256 {digest}, expected {a.sha256}: labels void')
        version = subprocess.run([str(a.engine), 'version'], capture_output=True, text=True, check=True).stdout
        net = re.search(r'^net (\S+)', version, re.M).group(1)
        bench = subprocess.run([str(a.engine), 'bench'], capture_output=True, text=True, check=True).stdout
        ref = (Path(__file__).resolve().parents[2] / 'tests' / f'bench-{net}.ref').read_text(encoding='utf-8')
        got = (re.search(r'nodes (\d+)', bench).group(1), re.search(r'signature ([0-9a-f]+)', bench).group(1))
        want = (re.search(r'nodes (\d+)', ref).group(1), re.search(r'signature ([0-9a-f]+)', ref).group(1))
        if got != want:
            raise SystemExit(f'{a.engine}: bench {got[0]} / {got[1]}, reference {want[0]} / {want[1]}: labels void')
        print(f'{a.engine.name}: SHA-256 {digest[:16]}..., bench {got[0]} / {got[1]} ({net}) as referenced')
        return 0

    if a.command == 'weights':
        mix = {0: 1.68, 1: 2.13}  # gate (a)'s calls in % of nodes: main search, quiescence (plan 1.1)
        bandwidth = {0: 25, 1: 17}  # cp (plan 3.7, amended)
        margin = {0: 25, 1: 10}  # gate (a), cp
        rows = []  # (folder, id, kind, gap, used)
        for folder in a.dir:
            labels = read_labels(folder / 'deep.tsv')
            for line in (folder / 'sites.jsonl').read_text(encoding='utf-8').splitlines():
                s = json.loads(line)
                if s['id'] not in labels:
                    continue
                value, mate, _depth = labels[s['id']]
                near = crucial_points.nearest_bound(s['eval'], s['alpha'], s['beta'])
                used = near is not None and not mate and abs(value) < TB_FLOOR
                rows.append((folder, s['id'], 1 if s['kind'] else 0, abs(s['eval'] - near[1]) if near else None, used))

        def scaled(base):
            # One factor per kind: the kinds' totals in mix's ratio, the weights averaging 1 where base > 0.
            counted = sum(1 for b in base if b > 0)
            totals = {k: sum(b for b, r in zip(base, rows) if r[2] == k) for k in (0, 1)}
            if not all(totals.values()):
                raise SystemExit(f'weights: a kind has no weight ({totals}); the call mix cannot be met')
            factor = {k: mix[k] / sum(mix.values()) * counted / totals[k] for k in (0, 1)}
            return [b * factor[r[2]] for b, r in zip(base, rows)], factor

        n_eff = lambda ws: sum(x for x in ws if x > 0) ** 2 / sum(x * x for x in ws if x > 0)  # noqa: E731
        kernel = [math.exp(-r[3] ** 2 / (2 * bandwidth[r[2]] ** 2)) if r[4] else 0.0 for r in rows]
        inside = [1.0 if r[4] and r[3] <= margin[r[2]] else 0.0 for r in rows]
        training, train_factor = scaled(kernel)
        acceptance, accept_factor = scaled(inside)
        for folder in a.dir:
            with open(folder / 'weights.tsv', 'w', encoding='utf-8') as f:
                for r, t, u in zip(rows, training, acceptance):
                    if r[0] == folder:
                        f.write(f'{r[1]}\t{t:.6f}\t{u:.6f}\n')
        n_used = sum(1 for r in rows if r[4])
        n_in = {k: sum(1 for r, u in zip(rows, inside) if u and r[2] == k) for k in (0, 1)}
        print(f'{len(rows)} labelled sites in {len(a.dir)} folder(s); {n_used} used (mates and the table band out: '
              f'{len(rows) - n_used}); main search {sum(1 for r in rows if r[4] and r[2] == 0)}, '
              f'quiescence {sum(1 for r in rows if r[4] and r[2] == 1)}')
        print(f'training (h = 25 / 17 cp, call mix 1.68 : 2.13): factors main {train_factor[0]:.3f}, quiescence '
              f'{train_factor[1]:.3f}; n_eff of the kernel alone (A8) {n_eff(kernel) / n_used:.3f} n, with the '
              f'factors {n_eff(training) / n_used:.3f} n')
        print(f'acceptance (inside gate (a), 25 / 10 cp): main {n_in[0]}, quiescence {n_in[1]}; factors main '
              f'{accept_factor[0]:.3f}, quiescence {accept_factor[1]:.3f}; n_eff {n_eff(acceptance):.0f} of '
              f'{sum(n_in.values())} ({n_eff(acceptance) / sum(n_in.values()):.3f} n)')
        return 0

    if a.command == 'budget':
        sites = [json.loads(line) for line in (a.pilot / 'n1m' / 'sites.jsonl').read_text(encoding='utf-8').splitlines()]
        labels = {n: read_labels(a.pilot / n / 'deep.tsv') for n in ('n100k', 'n300k', 'n1m')}
        rows = [s for s in sites if all(s['id'] in labels[n] for n in labels)]
        for s in rows:
            s['near'] = crucial_points.nearest_bound(s['eval'], s['alpha'], s['beta'])
            s['gap'] = abs(s['eval'] - s['near'][1])
        gated = [s for s in rows if s['gap'] <= 25]
        print(f'pilot: {len(sites)} sites selected, {len(rows)} labelled at all three budgets; {len(gated)} within 25 cp')
        print('median label depth: ' + ', '.join(
            f'{n} {statistics.median(labels[n][s["id"]][2] for s in rows):.0f}' for n in labels))
        print('\nside agreement with the 1M label, and the correlation of the win-probability residuals with the')
        print('1M residual (mates out of the correlation)')
        choice = None
        for name in ('n100k', 'n300k'):
            for title, group in (('gated (<= 25 cp)', gated), ('all near-window', rows)):
                agree = sum(above(labels[name][s['id']][0], s['near']) == above(labels['n1m'][s['id']][0], s['near'])
                            for s in group) / len(group)
                clean = [s for s in group if not labels[name][s['id']][1] and not labels['n1m'][s['id']][1]]
                r = statistics.correlation([wp(labels[name][s['id']][0]) - wp(s['eval']) for s in clean],
                                           [wp(labels['n1m'][s['id']][0]) - wp(s['eval']) for s in clean])
                flips = [s for s in group if above(s['eval'], s['near']) != above(labels['n1m'][s['id']][0], s['near'])]
                flip_agree = sum(above(labels[name][s['id']][0], s['near']) == above(labels['n1m'][s['id']][0], s['near'])
                                 for s in flips) / max(1, len(flips))
                print(f'  {name} {title:<17}: side agreement {agree:.3f}; residual correlation {r:.3f} (n {len(clean)}); '
                      f'agreement at the 1M-crucial sites {flip_agree:.3f} (n {len(flips)})')
                if title.startswith('gated') and choice is None and agree >= 0.90 and r >= 0.80:
                    choice = name
        print(f'  => label budget N = {choice or "n1m"} (the smallest passing both lines; 1M if none)')
        trace = {}
        for f in sorted((a.pilot / 'rep').glob('game-*.jsonl')):
            for line in f.read_text(encoding='utf-8').splitlines():
                rec = json.loads(line)
                its = rec.get('iterations') or []
                if len(its) >= 3:
                    trace[(rec['game'], rec['ply'])] = its[-1]['score'] - its[-3]['score']
        clean = [s for s in rows if not labels['n1m'][s['id']][1] and abs(labels['n1m'][s['id']][0]) < TB_FLOOR]
        res = {s['id']: labels['n1m'][s['id']][0] - s['eval'] for s in clean}
        g25 = [s for s in clean if s['gap'] <= 25]
        print(f'\nP0 on the pilot (1M labels; mates {sum(labels["n1m"][s["id"]][1] for s in rows)} of {len(rows)} out):')
        print('  within 25 cp :', describe([res[s['id']] for s in g25]))
        print('  near-window  :', describe([res[s['id']] for s in clean]))
        for name, test in [('main search', lambda s: s['kind'] == 0), ('quiescence', lambda s: s['kind'] == 1),
                           ('computed', lambda s: not s['reused']), ('reused', lambda s: s['reused']),
                           ('zero window', lambda s: s['beta'] - s['alpha'] == 1),
                           ('open window (PV)', lambda s: s['beta'] - s['alpha'] > 1),
                           ('root score moved > 30 cp over the last two iterations',
                            lambda s: abs(trace.get((s['game'], s['search_ply']), 0)) > 30),
                           ('root score stable (<= 10 cp)',
                            lambda s: abs(trace.get((s['game'], s['search_ply']), 99)) <= 10)]:
            print(f'    within 25 cp, {name:<52}', describe([res[s['id']] for s in g25 if test(s)]))
        w = [math.exp(-s['gap'] ** 2 / (2 * 25 ** 2)) for s in clean]
        mean_cp = sum(wi * res[s['id']] for wi, s in zip(w, clean)) / sum(w)
        mean_wp = sum(wi * (wp(labels['n1m'][s['id']][0]) - wp(s['eval'])) for wi, s in zip(w, clean)) / sum(w)
        neff = sum(w) ** 2 / sum(wi * wi for wi in w)
        print(f'  the centring mean (decision-weighted, h = 25 cp): {mean_cp:+.1f} cp, {mean_wp:+.4f} in win '
              f'probability; n_eff {neff:.0f} of {len(clean)} ({neff / len(clean):.2f})')
        return 0

    sites = {s['id']: s for s in (json.loads(line) for line in
                                  (a.dir / 'sites.jsonl').read_text(encoding='utf-8').splitlines())}
    labels = read_labels(a.dir / 'deep.tsv')
    seeds = {f.stem[5:]: {int(i): int(v) for i, v in (line.split('\t') for line in f.read_text().splitlines())}
             for f in sorted(a.dir.glob('seed-*.tsv'))}
    rows = [s for s in sites.values() if s['id'] in labels]
    deep = {i: v for i, (v, _m, _d) in labels.items()}
    mate = {i: m for i, (_v, m, _d) in labels.items()}
    print(f'sites {len(sites)}, deep-labelled {len(rows)}')
    pieces = lambda s: len(chess.Board(s['fen']).piece_map())  # noqa: E731
    print(f'deep values: mate-flagged {sum(mate[s["id"]] for s in rows)}; tablebase band (|v| >= {TB_FLOOR}) '
          f'{sum(not mate[s["id"]] and abs(deep[s["id"]]) >= TB_FLOOR for s in rows)}; 2,000 <= |v| < {TB_FLOOR} '
          f'{sum(not mate[s["id"]] and 2000 <= abs(deep[s["id"]]) < TB_FLOOR for s in rows)}; positions of at most '
          f'5 pieces {sum(pieces(s) <= 5 for s in rows)}')
    gap = lambda s, v: (lambda n: (abs(v - n[1]), n) if n else (None, None))(  # noqa: E731
        crucial_points.nearest_bound(v, s['alpha'], s['beta']))
    clean = [s for s in rows if not mate[s['id']] and abs(deep[s['id']]) < TB_FLOOR]
    near25 = [s for s in clean if gap(s, s['eval'])[0] is not None and gap(s, s['eval'])[0] <= 25]
    r = lambda group: [deep[s['id']] - s['eval'] for s in group]  # noqa: E731
    print('\nresidual r = deep - static (both from the side to move at the node)')
    print('  all sites, mates and tablebase-band values out:', describe(r(clean)))
    print('  within 25 cp of the nearest finite bound    :', describe(r(near25)))
    print('  the same, positions of at most 5 pieces out   :', describe(r([s for s in near25 if pieces(s) > 5])))
    print('  the same, |deep| < 2,000                      :', describe(r([s for s in near25 if abs(deep[s['id']]) < 2000])))
    mats = [material(chess.Board(s['fen'])) for s in clean]
    print(f'  perspective: corr(static, side to move\'s material) '
          f'{statistics.correlation([s["eval"] for s in clean], mats):+.2f}; corr(deep, same) '
          f'{statistics.correlation([deep[s["id"]] for s in clean], mats):+.2f}; corr(static, deep) '
          f'{statistics.correlation([s["eval"] for s in clean], [deep[s["id"]] for s in clean]):+.2f}; sign '
          f'disagreements beyond +-300 cp '
          f'{sum((s["eval"] > 300 and deep[s["id"]] < -300) or (s["eval"] < -300 and deep[s["id"]] > 300) for s in clean)}'
          f' of {len(clean)}')
    for name, test in [('main search', lambda s: s['kind'] == 0), ('quiescence', lambda s: s['kind'] == 1),
                       ('computed', lambda s: not s['reused']), ('reused', lambda s: s['reused']),
                       ('last move a capture', lambda s: s['captured']),
                       ('static below the bound', lambda s: s['eval'] < gap(s, s['eval'])[1][1]),
                       ('zero window', lambda s: s['beta'] - s['alpha'] == 1),
                       ('open window (PV)', lambda s: s['beta'] - s['alpha'] > 1)]:
        print(f'    within 25 cp, {name:<24}', describe(r([s for s in near25 if test(s)])))
    for lo, hi in [(0, 25), (26, 80), (81, 200), (201, 500), (501, 100000)]:
        print(f'    gap {lo}-{hi:<7}', describe(r([s for s in clean if gap(s, s['eval'])[0] is not None
                                                  and lo <= gap(s, s['eval'])[0] <= hi])))
    if {'s512ppr3', 's512r2', 's512x'} <= seeds.keys():
        print('\nnet flips of S512+X over each base, at sites within 25 cp of the base\'s own evaluation')
        nf = {}
        for base in ('s512ppr3', 's512r2'):
            fixed = broken = gated = 0
            for s in rows:
                g, near = gap(s, seeds[base][s['id']])
                if g is None or g > 25:
                    continue
                gated += 1
                b_up, x_up, d_up = (above(v, near) for v in (seeds[base][s['id']], seeds['s512x'][s['id']], deep[s['id']]))
                fixed += b_up != d_up and x_up == d_up
                broken += b_up == d_up and x_up != d_up
            nf[base] = (fixed - broken) / gated
            z = (fixed - broken) / math.sqrt(fixed + broken) if fixed + broken else 0
            print(f'  over {base}: gated {gated}, fixed {fixed}, broken {broken}, NF {nf[base]:+.4f} (McNemar z {z:+.2f})')
        print(f'  ratio NF(over S512ppr3) / NF(over S512r2) = {nf["s512ppr3"] / nf["s512r2"]:.2f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
