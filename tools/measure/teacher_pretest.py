# SPDX-License-Identifier: GPL-3.0-or-later

"""Ensemble-teacher step 0's yardsticks (docs/research/labels-teacher/
step0-declaration.md, committed before any label; report.md §2.5 beside it).

Inputs are label folders in label_pretest.py's format (sites.jsonl with id,
fen, game "SHARD#INDEX" and the record index; deep.tsv with id, cp from the
side to move, mate flag, depth), one per label and per site set. A static
evaluation is written in the same format (mate 0, depth 0). Every label of a
run must cover every matched site; the record of each site (its game's
stored scores, result, side and the trainer's kept flag) comes from the
first label's folders through td_labels.matched_records.

Each label becomes a win probability p = sigmoid(cp / S) from the side to
move (a mate, +-20,000, saturates to 1 or 0). Two more kinds of label:
- `--combine NAME=A,B,...`: the plain mean of the members' p (the gold mean);
- `--mate-majority NAME=A,B,...`: the mean with the declared mate rule: when
  a strict majority of the members report a mate for the same side, the
  label is that side's p (1 or 0); otherwise the members reporting a mate
  are left out of the mean. Should every member be left out (possible only
  with an even split of mates), the plain mean is used and counted.
The label "stored" is always present: the record's stored game score.

Without --lams (step 0's tables), on the kept records:
- Y1: the Brier score (p - z)^2 against the game result z (1, 1/2, 0 from
  the side to move);
- Y2: for each `--reference R`, the squared error (p - p_R)^2;
- every label's mean and every pair's paired difference A - B, each with a
  95% percentile interval from `--boot` resamples of the games that have a
  kept record (label_pretest.py's draw: random.Random(seed), randrange per
  game, one resample of the games shared by every quantity).
With --lams (the TD pre-test's comparisons re-scored with other golds;
declaration-8b's settings), every `--reference` serves as the gold in turn:
the control (1 - w) sigmoid(s / S) + w z and TD(lambda) labels against it
on the kept records, the control on all saved records against the kept
ones, all as label_pretest.py `labels` computes them (the same games, draw
and arithmetic, so the first reference reproduces its numbers); and the bias
of each comparison, its difference under the first reference minus its
difference under each other one, with the same paired interval.

    teacher_pretest.py NAME=DIR[,DIR...]... --data DIR... --scale S --boot B --seed S
        [--combine NAME=A,B,...]... [--mate-majority NAME=A,B,...]... [--reference NAME]...
        [--blend W --lams L,...] [--json OUT]

A label's folders are given in the same set order for every label (for
example H's folder, then H2's); each set's sites.jsonl must be identical
across labels.
"""
import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'datagen'))
import label_pretest as lp  # noqa: E402
import td_labels as td  # noqa: E402

STORED = 'stored'


def _p(cp, scale):
    return td.win_pair(cp, scale)[0]


def _mean_p(values, scale, majority):
    """values: the members' (cp, mate flag). Returns (p, state): state 0 when
    no member reports a mate, 1 a majority mate, 2 mate members left out,
    3 every member left out (the plain mean)."""
    plain = sum(_p(cp, scale) for cp, _m in values) / len(values)
    if not majority or not any(m for _cp, m in values):
        return plain, 0
    wins = sum(1 for cp, m in values if m and cp > 0)
    losses = sum(1 for cp, m in values if m and cp < 0)
    if 2 * wins > len(values):
        return 1.0, 1
    if 2 * losses > len(values):
        return 0.0, 1
    rest = [_p(cp, scale) for cp, m in values if not m]
    if not rest:
        return plain, 3
    return sum(rest) / len(rest), 2


def _brier(p, z):
    return (p - z) ** 2


def _resample_sums(columns, boots, seed):
    """columns: equal-length per-game value lists. For each of `boots`
    resamples of the games (label_pretest.boot_difference's draw), each
    column's resampled sum: [[sum per resample] per column]."""
    k = len(columns[0])
    rng = random.Random(seed)
    out = [[] for _ in columns]
    getters = [c.__getitem__ for c in columns]
    for _ in range(boots):
        idx = [rng.randrange(k) for _ in range(k)]
        for j, g in enumerate(getters):
            out[j].append(sum(map(g, idx)))
    return out


def _summary(point, reps):
    reps = [r for r in reps if r == r]
    lo, hi = lp.interval(reps)
    return {'value': point, 'interval': [lo, hi]}


def _read_deep(folder):
    out = {}
    for line in (folder / 'deep.tsv').read_text(encoding='utf-8').splitlines():
        if line.strip():
            f = line.split('\t')
            out[int(f[0])] = (int(f[1]), int(f[2]))
    return out


def _site_ids(folder):
    out = {}
    for line in (folder / 'sites.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            s = json.loads(line)
            out[s['game']] = s['id']
    return out


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _records(entries, data):
    """The matched records of every set (first label's folders), with each
    search label's (cp, mate) attached as rec['labels'][name]."""
    names = list(entries)
    sets = len(entries[names[0]])
    rows, info = [], []
    for i in range(sets):
        first = entries[names[0]][i]
        digest = _sha(first / 'sites.jsonl')
        for n in names[1:]:
            if _sha(entries[n][i] / 'sites.jsonl') != digest:
                raise SystemExit(f'{n}: set {i} sites.jsonl differs from {names[0]}\'s')
        matched, stats = td.matched_records([first], data)
        ids = _site_ids(first)
        deep = {n: _read_deep(entries[n][i]) for n in names}
        missing = {n: sum(1 for r in matched if ids[r['game']] not in deep[n]) for n in names}
        if any(missing.values()):
            raise SystemExit(f'set {i}: labels missing for matched sites: {missing}')
        for r in matched:
            sid = ids[r['game']]
            r['labels'] = {n: deep[n][sid] for n in names}
            r['set'] = i
            rows.append(r)
        info.append({'folder': first.name, 'sites_sha256': digest, 'match': stats, 'records': len(matched),
                     'kept': sum(r['kept'] for r in matched)})
    return rows, info


def _side(r, p):
    return p if r['white'] else 1.0 - p


def _label_ps(rows, names, combos, scale):
    """Each record's p of every label (search, stored, combined), and the
    combined labels' mate-rule counts."""
    counts = {c: [0, 0, 0, 0] for c in combos}
    for r in rows:
        ps = {n: _p(r['labels'][n][0], scale) for n in names}
        ps[STORED] = _side(r, _p(r['scores'][r['record']], scale))
        for c, (members, majority) in combos.items():
            p, state = _mean_p([r['labels'][m] for m in members], scale, majority)
            counts[c][state] += 1
            ps[c] = p
        r['p'] = ps
    return {c: dict(zip(('no_mate', 'majority_mate', 'mates_left_out', 'all_left_out'), v))
            for c, v in counts.items()}


def _tables(rows, labels, references, boots, seed):
    """Y1 and Y2 means and paired differences on the kept records; the games
    resampled are those with a kept record."""
    kept = [r for r in rows if r['kept']]
    games = {}
    for r in kept:
        games.setdefault(r['game'], []).append(r)
    glist = list(games.values())
    metrics = [('y1', None)] + [('y2', ref) for ref in references]
    cols, keys = [], []
    for metric, ref in metrics:
        for lab in labels:
            if lab == ref:
                continue
            col = []
            for g in glist:
                z = [_side(r, td.WHITE_RESULT[r['result']]) for r in g]
                col.append(sum(_brier(r['p'][lab], zz if ref is None else r['p'][ref]) for r, zz in zip(g, z)))
            cols.append(col)
            keys.append((metric, ref, lab))
    cols.append([len(g) for g in glist])
    sums = _resample_sums(cols, boots, seed)
    n_reps = sums[-1]
    n = len(kept)
    by_key = {key: (sum(cols[j]) / n, [s / m for s, m in zip(sums[j], n_reps)]) for j, key in enumerate(keys)}
    out = {'kept_records': n, 'games': len(glist), 'y1': {}, 'y2': {}}
    for (metric, ref, lab), (point, reps) in by_key.items():
        table = out['y1'] if metric == 'y1' else out['y2'].setdefault(ref, {})
        table.setdefault('mean', {})[lab] = _summary(point, reps)
    for metric, ref in metrics:
        table = out['y1'] if metric == 'y1' else out['y2'][ref]
        names = [lab for lab in labels if lab != ref]
        diffs = {}
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                pa, ra = by_key[(metric, ref, a)]
                pb, rb = by_key[(metric, ref, b)]
                diffs[f'{a} - {b}'] = _summary(pa - pb, [x - y for x, y in zip(ra, rb)])
        table['differences'] = diffs
    return out


def _bias(rows, references, scale, blend, lams, boots, seed):
    """The TD pre-test's comparisons under each reference as the gold, and
    the bias of each comparison: first reference minus each other one."""
    games = {}
    for r in rows:
        games.setdefault(r['game'], []).append(r)
    glist = list(games.values())
    cands = ['control'] + [f'td={lam:g}' for lam in lams]
    cache = {}
    for r in rows:
        v = td.win_pair(r['scores'][r['record']], scale)[0]
        z = td.WHITE_RESULT[r['result']]
        r['cand'] = {'control': _side(r, (1.0 - blend) * v + blend * z)}
        for lam in lams:
            key = (r['game'], lam)
            if key not in cache:
                cache[key] = td.td_targets(r['scores'], r['result'], lam, scale, skip=r['check'])
            label = cache[key][r['record']]
            if label is not None:
                r['cand'][f'td={lam:g}'] = _side(r, label)
    cols, keys = [], []
    for ref in references:
        for c in cands:
            cols.append([sum((x['cand'][c] - x['p'][ref]) ** 2 for x in g if x['kept']) for g in glist])
            keys.append((ref, c, 'kept'))
        cols.append([sum((x['cand']['control'] - x['p'][ref]) ** 2 for x in g) for g in glist])
        keys.append((ref, 'control', 'all'))
    cols.append([sum(x['kept'] for x in g) for g in glist])
    cols.append([len(g) for g in glist])
    sums = _resample_sums(cols, boots, seed)
    nk_reps, na_reps = sums[-2], sums[-1]
    nk, na = sum(cols[-2]), sum(cols[-1])
    point, reps = {}, {}
    for j, key in enumerate(keys):
        d, d_reps = (nk, nk_reps) if key[2] == 'kept' else (na, na_reps)
        point[key] = sum(cols[j]) / d
        reps[key] = [s / m if m else float('nan') for s, m in zip(sums[j], d_reps)]

    def comparisons(ref):
        out = {}
        for c in cands[1:]:
            out[c] = (point[(ref, c, 'kept')] - point[(ref, 'control', 'kept')],
                      [a - b for a, b in zip(reps[(ref, c, 'kept')], reps[(ref, 'control', 'kept')])])
        out['unfiltered'] = (point[(ref, 'control', 'all')] - point[(ref, 'control', 'kept')],
                             [a - b for a, b in zip(reps[(ref, 'control', 'all')], reps[(ref, 'control', 'kept')])])
        return out

    report = {'records': na, 'kept': nk, 'games': len(glist), 'golds': {}, 'bias': {}}
    comp = {ref: comparisons(ref) for ref in references}
    for ref in references:
        report['golds'][ref] = {
            'mse_kept': {c: point[(ref, c, 'kept')] for c in cands},
            'mse_all_saved_control': point[(ref, 'control', 'all')],
            'differences': {k: _summary(*v) for k, v in comp[ref].items()}}
    first = references[0]
    for ref in references[1:]:
        report['bias'][f'{first} minus {ref}'] = {
            k: _summary(comp[first][k][0] - comp[ref][k][0], [a - b for a, b in zip(comp[first][k][1], comp[ref][k][1])])
            for k in comp[first]}
    return report


def _mean_abs_cp(rows, names):
    out = {}
    for n in names:
        vals = [abs(r['labels'][n][0]) for r in rows if r['kept'] and not r['labels'][n][1]]
        out[n] = sum(vals) / len(vals) if vals else float('nan')
    return out


def _pairs(items, what):
    out = {}
    for item in items:
        name, _, rest = item.partition('=')
        if not name or not rest:
            raise SystemExit(f'{what}: expected NAME=..., got {item!r}')
        out[name] = rest.split(',')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('entries', nargs='+')
    ap.add_argument('--data', type=Path, nargs='+', required=True)
    ap.add_argument('--scale', type=float, required=True)
    ap.add_argument('--boot', type=int, required=True)
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--combine', action='append', default=[])
    ap.add_argument('--mate-majority', action='append', default=[])
    ap.add_argument('--reference', action='append', default=[])
    ap.add_argument('--blend', type=float)
    ap.add_argument('--lams')
    ap.add_argument('--json', type=Path)
    a = ap.parse_args(argv)
    began = time.monotonic()
    entries = {n: [Path(x) for x in dirs] for n, dirs in _pairs(a.entries, 'label').items()}
    if len({len(v) for v in entries.values()}) != 1:
        raise SystemExit('every label needs the same number of folders (one per set)')
    combos = {n: (m, False) for n, m in _pairs(a.combine, '--combine').items()}
    combos.update({n: (m, True) for n, m in _pairs(a.mate_majority, '--mate-majority').items()})
    for c, (members, _maj) in combos.items():
        bad = [m for m in members if m not in entries]
        if bad or c in entries or c == STORED:
            raise SystemExit(f'{c}: members must be search labels, the name new ({bad})')
    labels = list(entries) + [STORED] + list(combos)
    for ref in a.reference:
        if ref not in labels:
            raise SystemExit(f'--reference {ref}: no such label')
    rows, info = _records(entries, a.data)
    mate_counts = _label_ps(rows, list(entries), combos, a.scale)
    report = {'sets': info, 'scale': a.scale, 'boot': a.boot, 'seed': a.seed,
              'labels': {n: {'folders': [str(p) for p in entries[n]],
                             'mate_flags': sum(r['labels'][n][1] for r in rows),
                             'mate_flags_kept': sum(r['labels'][n][1] for r in rows if r['kept'])} for n in entries},
              'combined': {c: {'members': m, 'mate_majority': maj, 'states': mate_counts[c]}
                           for c, (m, maj) in combos.items()},
              'mean_abs_cp_kept_no_mate': _mean_abs_cp(rows, list(entries))}
    if a.lams:
        if a.blend is None or len(a.reference) < 1:
            raise SystemExit('--lams needs --blend and at least one --reference')
        lams = [float(x) for x in a.lams.split(',')]
        report['blend'] = a.blend
        report['lams'] = lams
        report.update(_bias(rows, a.reference, a.scale, a.blend, lams, a.boot, a.seed))
    else:
        report.update(_tables(rows, labels, a.reference, a.boot, a.seed))
    report['seconds'] = round(time.monotonic() - began, 1)
    text = json.dumps(report, indent=1)
    print(text)
    if a.json:
        a.json.write_text(text + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
