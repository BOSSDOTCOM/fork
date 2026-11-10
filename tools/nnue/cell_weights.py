# SPDX-License-Identifier: GPL-3.0-or-later
"""Idea 69's loss weights per material cell and wing (docs/research/class-sampler/design.md §3.3
and its "Owner decision 2026-11-10" section), and the realised-share check of §5.2.

For a material cell c with training share t_c (from the trainer's `cells` count) and deciding
share d_c (the conversion-and-defense report's item5-data-gaps.json, `matcls`, "all deciding
positions"), the ratio is r_c = d_c / t_c, and each (cell, wing) gets

    w = 1                                  if c has fewer than --min-n deciding positions,
                                           or no training positions;
    w = clip(k * r_c, low, 2)              otherwise, low = 1.0 for the owner's floored
                                           positions (below), else 0.5,

with the scale k solved (bisection; the mean is non-decreasing in k) so that the mean weight over
the training positions is exactly 1. The owner's floors (2026-11-10; narrowed at about 9:50 AM EST
to the material classes): the classes the report flagged for conversion failures, rook against
minor pieces (every R-vs-minors cell), queen imbalances (every Q-imbalance cell) and a piece
against pawns (minor-EG|minor-up, the report's own name for it in items 3 and 4), are floored at
1.0 instead of 0.5. One-wing structures are no longer floored, so both wing entries of a cell
carry the same weight (the table keeps them apart for any later rule). The weight depends only
on the board.

    python -I tools/nnue/cell_weights.py solve --deciding item5-data-gaps.json --counts COUNTS
        [--no-floors] [--min-n 50] [--out TABLE] [--summary JSON] [--markdown FILE]
    python -I tools/nnue/cell_weights.py check --table TABLE --counts COUNTS --stream STREAM
        [--exempt-counts COUNTS]

COUNTS is `fork-train cells` output, STREAM `fork-train cells --stream` output, TABLE the
trainer's --cell-weights file (one "cell wing weight" line for each of the 112 entries).
"""
import argparse
import json
import math
import sys

SIGNATURES = ['Q-MG', 'Q-EG', 'noQ-MG', 'R+minor-EG', 'R-EG', 'minor-EG', 'pawn-EG']
BALANCES = ['Q-imbalance', 'R-vs-minors', 'minor-up', 'other-imbalance', 'B-vs-N', 'level', 'pawn+-1', 'pawn+-2+']
WINGS = ['two-wing', 'one-wing']
CELLS = [f'{s}|{b}' for s in SIGNATURES for b in BALANCES]
FLAGGED_BALANCES = {'R-vs-minors', 'Q-imbalance'}
FLAGGED_CELLS = {'minor-EG|minor-up'}
LOW, HIGH, FLOOR, MIN_N = 0.5, 2.0, 1.0, 50
DECIDING = 'all deciding positions'


def floored(cell, wing):
    """The owner's floor (2026-11-10, narrowed at about 9:50 AM EST): the conversion-failure
    material classes, in both wing classes."""
    del wing
    return cell.split('|')[1] in FLAGGED_BALANCES or cell in FLAGGED_CELLS


def read_counts(text):
    """{(cell, wing): count} from `fork-train cells` output."""
    out = {}
    for line in text.splitlines():
        f = line.split()
        if len(f) == 4 and f[0] == 'cell' and f[1] in CELLS:
            out[(f[1], 'two-wing')] = int(f[2])
            out[(f[1], 'one-wing')] = int(f[3])
    if set(c for c, _ in out) != set(CELLS):
        raise ValueError('a counts file lists every one of the 56 cells')
    return out


def read_deciding(path):
    """{cell: (deciding share, deciding count)} from item5-data-gaps.json."""
    d = json.load(open(path, encoding='utf-8'))
    return {r['cat']: (r[DECIDING]['share'], r[DECIDING]['n']) for r in d['dims']['matcls']}


def solve(counts, deciding, floors=True, low=LOW, high=HIGH, floor=FLOOR, min_n=MIN_N):
    total = sum(counts.values())
    if total <= 0:
        raise ValueError('no training positions')
    t = {k: n / total for k, n in counts.items()}
    tc = {c: t.get((c, 'two-wing'), 0.0) + t.get((c, 'one-wing'), 0.0) for c in CELLS}
    small = {c for c in CELLS if c not in deciding or deciding[c][1] < min_n or tc[c] == 0.0}
    ratio = {c: deciding[c][0] / tc[c] for c in CELLS if c not in small}

    def lowest(c, w):
        return floor if floors and floored(c, w) else low

    def table(k):
        return {(c, w): 1.0 if c in small else min(high, max(lowest(c, w), k * ratio[c])) for c in CELLS for w in WINGS}

    free = [(c, w) for c in CELLS for w in WINGS if c not in small]
    mass = sum(t.get(e, 0.0) for e in free)

    def mean_free(k):
        tab = table(k)
        return sum(t.get(e, 0.0) * tab[e] for e in free) / mass

    lo_k, hi_k = 1e-9, 1e9
    if not (mean_free(lo_k) <= 1.0 <= mean_free(hi_k)):
        raise ValueError(f'no scale gives a mean weight of 1 (range {mean_free(lo_k):.4f} to {mean_free(hi_k):.4f})')
    for _ in range(300):
        mid = math.sqrt(lo_k * hi_k)
        if mean_free(mid) < 1.0:
            lo_k = mid
        else:
            hi_k = mid
    k = math.sqrt(lo_k * hi_k)
    tab = table(k)
    mean = sum(t.get(e, 0.0) * tab[e] for e in tab)
    e_w2 = sum(t.get(e, 0.0) * tab[e] ** 2 for e in tab)
    dsum = sum(deciding[c][0] for c in CELLS if c in deciding)
    d = {c: (deciding[c][0] / dsum if c in deciding else 0.0) for c in CELLS}
    weighted = {c: sum(t.get((c, w), 0.0) * tab[(c, w)] for w in WINGS) / mean for c in CELLS}
    tv_before = 0.5 * sum(abs(tc[c] - d[c]) for c in CELLS)
    tv_after = 0.5 * sum(abs(weighted[c] - d[c]) for c in CELLS)
    return {'table': tab, 'k': k, 'mean': mean, 'e_w2': e_w2, 'tv_before': tv_before, 'tv_after': tv_after,
            'train_share': tc, 'deciding_share': d, 'weighted_share': weighted, 'ratio': ratio,
            'small': sorted(small), 'one_wing_share': sum(t.get((c, 'one-wing'), 0.0) for c in CELLS),
            'positions': total}


def table_text(table):
    lines = ['# Idea 69 loss weights: cell wing weight (tools/nnue/cell_weights.py)']
    lines += [f'{c} {w} {table[(c, w)]:.6f}' for c in CELLS for w in WINGS]
    return '\n'.join(lines) + '\n'


def read_table(text):
    out = {}
    for line in text.splitlines():
        if line.strip() and not line.startswith('#'):
            c, w, x = line.split()
            out[(c, w)] = float(x)
    return out


def read_stream(text):
    """`fork-train cells --stream` output."""
    s = {'cells': {}}
    for line in text.splitlines():
        f = line.split()
        if not f:
            continue
        if f[0] == 'positions':
            s['positions'] = int(f[1])
        elif f[0] == 'exempt':
            s['exempt'], s['exempt_min'], s['exempt_max'] = int(f[1]), float(f[4]), float(f[6])
        elif f[0] == 'weighted':
            s['weighted'], s['mean'] = int(f[1]), float(f[3])
        elif len(f) == 6 and f[0] == 'cell' and f[1] in CELLS:
            s['cells'][(f[1], 'two-wing')] = (int(f[2]), float(f[4]))
            s['cells'][(f[1], 'one-wing')] = (int(f[3]), float(f[5]))
    return s


def check_stream(table, counts, stream, tol_pp=0.3, tol_mean=0.005):
    """§5.2: each material cell's share of the stream's weight within tol_pp percentage points of
    its target t_c w_c (normalised), the mean weight within 1 +- tol_mean, every exempt position
    at weight exactly 1."""
    total = sum(counts.values())
    target = {}
    tsum = sum(n / total * table[k] for k, n in counts.items())
    for c in CELLS:
        target[c] = sum(counts[(c, w)] / total * table[(c, w)] for w in WINGS) / tsum
    wsum = sum(x[1] for x in stream['cells'].values())
    real = {c: sum(stream['cells'].get((c, w), (0, 0.0))[1] for w in WINGS) / wsum for c in CELLS}
    diffs = {c: 100 * (real[c] - target[c]) for c in CELLS}
    worst = max(diffs, key=lambda c: abs(diffs[c]))
    mean_ok = abs(stream['mean'] - 1.0) <= tol_mean
    exempt_ok = stream.get('exempt', 0) == 0 or (stream['exempt_min'] == 1.0 and stream['exempt_max'] == 1.0)
    ok = abs(diffs[worst]) <= tol_pp and mean_ok and exempt_ok
    report = {'ok': ok, 'max_diff_pp': diffs[worst], 'worst_cell': worst, 'mean': stream['mean'],
              'mean_ok': mean_ok, 'exempt': stream.get('exempt', 0), 'exempt_ok': exempt_ok,
              'tolerance_pp': tol_pp, 'tolerance_mean': tol_mean}
    return ok, report


def markdown(r, base=None):
    """The per-cell table of a solution (and, with `base`, which weights moved against it)."""
    tab, rows = r['table'], []
    head = '| Cell | Training | Deciding | Ratio | Weight, two-wing | Weight, one-wing | Weighted share |'
    if base:
        head += ' Without the floors (two / one) |'
    rows.append(head)
    rows.append('|' + '---|' * (head.count('|') - 1))
    for c in sorted(CELLS, key=lambda c: -r['deciding_share'][c]):
        if r['train_share'][c] == 0 and r['deciding_share'][c] == 0:
            continue
        ratio = f"{r['ratio'][c]:.2f}" if c in r['ratio'] else 'small'
        line = (f"| {c} | {100 * r['train_share'][c]:.2f}% | {100 * r['deciding_share'][c]:.2f}% | {ratio} | "
                f"{tab[(c, 'two-wing')]:.3f} | {tab[(c, 'one-wing')]:.3f} | {100 * r['weighted_share'][c]:.2f}% |")
        if base:
            line += f" {base['table'][(c, 'two-wing')]:.3f} / {base['table'][(c, 'one-wing')]:.3f} |"
        rows.append(line)
    return '\n'.join(rows) + '\n'


def summary_of(r):
    return {k: v for k, v in r.items() if k in ('k', 'mean', 'e_w2', 'tv_before', 'tv_after', 'small',
                                                'one_wing_share', 'positions')}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('solve')
    s.add_argument('--deciding', required=True)
    s.add_argument('--counts', required=True)
    s.add_argument('--no-floors', action='store_true')
    s.add_argument('--min-n', type=int, default=MIN_N)
    s.add_argument('--out')
    s.add_argument('--summary')
    s.add_argument('--markdown')
    c = sub.add_parser('check')
    c.add_argument('--table', required=True)
    c.add_argument('--counts', required=True)
    c.add_argument('--stream', required=True)
    a = ap.parse_args(argv)
    if a.cmd == 'solve':
        counts = read_counts(open(a.counts, encoding='utf-8').read())
        deciding = read_deciding(a.deciding)
        r = solve(counts, deciding, floors=not a.no_floors, min_n=a.min_n)
        base = solve(counts, deciding, floors=False, min_n=a.min_n) if not a.no_floors else None
        out = summary_of(r)
        if base:
            out['without_floors'] = summary_of(base)
            out['moved'] = sorted(f'{c} {w}' for (c, w), x in r['table'].items() if abs(x - base['table'][(c, w)]) > 5e-4)
        print(json.dumps(out, indent=1))
        if a.out:
            open(a.out, 'w', encoding='utf-8', newline='\n').write(table_text(r['table']))
        if a.summary:
            json.dump(out, open(a.summary, 'w', encoding='utf-8'), indent=1)
        if a.markdown:
            open(a.markdown, 'w', encoding='utf-8', newline='\n').write(markdown(r, base))
        return 0
    table = read_table(open(a.table, encoding='utf-8').read())
    counts = read_counts(open(a.counts, encoding='utf-8').read())
    ok, report = check_stream(table, counts, read_stream(open(a.stream, encoding='utf-8').read()))
    print(json.dumps(report, indent=1))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
