# SPDX-License-Identifier: GPL-3.0-or-later

"""Head-to-head selection of a search constant's value (owner, DESIGN.md §6 2026-11-07 decision 3): two
or three candidate values, each a commit, played against each other on the same openings by
tools/github/h2h_run.sh (one pairing for two values, a round robin for three, every pairing the same
declared stages); this script reads the pairings' shard results and picks the value.

- Each pairing (base = the value listed first): its stages' result.json files, each checked against the
  pairing's commits and stage, merged with sprt_merge.merge; d = nElo of test against base, e = its 95%
  half-width 1.96 * C / sqrt(pairs) (the merge report's own). Every pairing must have played the same
  opening lines.
- Strengths: weighted least squares of s_test - s_base = d over the pairings (weights 1 / (e / 1.96)^2),
  with the preferred value at 0; each value's half-width from the inverse normal matrix. For two values
  that is the pairing itself; for three equal-length pairings s_B = (2 d_AB + d_AC - d_BC) / 3 and
  s_C = (d_AB + 2 d_AC + d_BC) / 3, each +/- e sqrt(2/3). nElo differences are treated as additive across
  pairings, an approximation for the small differences between candidate values.
- The pick: the largest strength; the declared tie rule (owner, 2026-11-07: 0.5 e, the 2026-11-06 ladder
  rule's "within half the error bars") keeps the preferred value (the current or the simpler one, named
  before any game) unless the leader beats it by more than tie_margin times the half-width of their
  difference.

    python3 tools/cloud/h2h_pick.py DECLARATION_DIR SPRT_DATA_ROOT

DECLARATION_DIR is $SPRT_DATA/NAME (its declaration.json, written by h2h_run.sh); the pairings are
SPRT_DATA_ROOT/NAME.A-B. Writes pick.json and constants-line.md (the Search constants table's row) to
DECLARATION_DIR. Exit 1 when a pairing is missing, belongs to other commits or played other openings.
"""
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sprt_merge as sm  # noqa: E402


def pairing_result(dirpath, base, test, origin, stages):
    """One pairing's merged result over stages origin .. origin + stages - 1."""
    dirpath = Path(dirpath)
    shards, runs = [], []
    for s in range(origin, origin + stages):
        files = sorted((dirpath / f's{s}').rglob('result.json'))
        if not files:
            raise ValueError(f'stage {s} has no results in {dirpath}')
        for f in files:
            r = json.loads(f.read_text(encoding='utf-8'))
            meta = r.get('meta', {})
            if (meta.get('base'), meta.get('test'), str(meta.get('stage'))) != (base, test, str(s)):
                raise ValueError(f'{f} is not this pairing\'s ({base[:12]} vs {test[:12]}, stage {s})')
            shards.append(r)
        run = (dirpath / f's{s}' / 'run_id')
        if run.exists():
            runs.append(int(run.read_text(encoding='utf-8').strip()))
    merged = sm.merge(shards)
    p = merged['ptnml']
    n = sum(p)
    if n == 0:
        raise ValueError(f'no finished pairs in {dirpath}')
    ranges = sorted(r for r in (sm.opening_range(x.get('meta', {})) for x in shards) if r is not None)
    return {'ptnml': p, 'pairs': n, 'd': sm.nelo(p), 'e': 1.96 * sm.NELO_SCALE / math.sqrt(n), 'ranges': ranges,
            'runs': runs}


def fit_strengths(pairs, labels, ref):
    """pairs: (a, b, d, e) with s_b - s_a = d +/- e. Returns {label: (s, half-width)}, s[ref] = 0."""
    free = [x for x in labels if x != ref]
    k = len(free)
    at = {x: i for i, x in enumerate(free)}
    a = [[0.0] * k for _ in range(k)]
    b = [0.0] * k
    for lo, hi, d, e in pairs:
        w = (1.96 / e) ** 2
        x = [0.0] * k
        if hi in at:
            x[at[hi]] += 1.0
        if lo in at:
            x[at[lo]] -= 1.0
        for i in range(k):
            b[i] += w * d * x[i]
            for j in range(k):
                a[i][j] += w * x[i] * x[j]
    # The inverse of the normal matrix (Gauss-Jordan; k is 1 or 2).
    inv = [[float(i == j) for j in range(k)] for i in range(k)]
    m = [row[:] for row in a]
    for c in range(k):
        piv = max(range(c, k), key=lambda r: abs(m[r][c]))
        if abs(m[piv][c]) < 1e-15:
            raise ValueError('the pairings do not connect every value')
        m[c], m[piv] = m[piv], m[c]
        inv[c], inv[piv] = inv[piv], inv[c]
        f = m[c][c]
        m[c] = [v / f for v in m[c]]
        inv[c] = [v / f for v in inv[c]]
        for r in range(k):
            if r != c and m[r][c] != 0.0:
                g = m[r][c]
                m[r] = [v - g * u for v, u in zip(m[r], m[c])]
                inv[r] = [v - g * u for v, u in zip(inv[r], inv[c])]
    out = {ref: (0.0, 0.0)}
    for x, i in at.items():
        out[x] = (sum(inv[i][j] * b[j] for j in range(k)), 1.96 * math.sqrt(inv[i][i]))
    return out


def pick_winner(strengths, prefer, tie_margin, labels):
    """(winner, tie_rule_applied): the largest strength (exact ties: the preferred value, then the order
    listed); the preferred value unless the leader beats it by more than tie_margin half-widths
    (strengths measured from the preferred value, so the leader's half-width is their difference's)."""
    cands = [x for x in labels if x in strengths]
    lead = max(cands, key=lambda x: (strengths[x][0], x == prefer, -cands.index(x)))
    if lead != prefer and strengths[lead][0] - strengths[prefer][0] <= tie_margin * strengths[lead][1]:
        return prefer, True
    return lead, False


def constants_line(declaration, name, results, strengths, winner, applied, date):
    """The Search constants table's row (DESIGN.md §5.2): value, then the measurement as Fork's own."""
    labels = list(declaration['values'])
    prefer = declaration['prefer']
    stages = int(declaration['stages'])
    margin = f"{float(declaration['tie_margin']):g}"
    runs = [r for res in results.values() for r in res['runs']]
    per_stage = 2 * next(iter(results.values()))['pairs'] // stages
    total = sum(2 * res['pairs'] for res in results.values())
    many = len(results) > 1
    deltas = ', '.join(f'{x} - {prefer} {strengths[x][0]:+.2f} +/- {strengths[x][1]:.2f} nElo'
                       for x in labels if x != prefer)
    if many:
        deltas += f' (least squares over the {len(results)} pairings)'
    if applied:
        deltas += f', within {margin} e: the tie rule keeps {prefer}'
    return (f"| `{declaration['const']}` | {winner} | **Head-to-head** ({date}, h2h {name}, runs "
            f"{', '.join(str(r) for r in runs)}): values {', '.join(labels)}{' in a round robin' if many else ''}, "
            f"{stages} stage{'s' if stages != 1 else ''} of {per_stage:,} games{' per pairing' if many else ''} on "
            f"the same openings ({total:,} games); {deltas}; declared tie rule: {prefer} "
            f"({declaration['prefer_reason']}) unless beaten by more than {margin} e. Fork's own measurement "
            f"(DESIGN.md §6, 2026-11-07 decision 3). |")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 1
    here, data = Path(argv[0]), Path(argv[1])
    name = here.name
    declaration = json.loads((here / 'declaration.json').read_text(encoding='utf-8'))
    labels = list(declaration['values'])
    sha = declaration['values']
    stages, origin = int(declaration['stages']), int(declaration['origin'])
    prefer, margin = declaration['prefer'], float(declaration['tie_margin'])
    results = {}
    first = None
    for i, lo in enumerate(labels):
        for hi in labels[i + 1:]:
            folder = data / f'{name}.{lo}-{hi}'
            try:
                res = pairing_result(folder, sha[lo], sha[hi], origin, stages)
            except ValueError as err:
                print(f'h2h_pick: {folder.name}: {err}', file=sys.stderr)
                return 1
            if first is None:
                first = (folder.name, res['ranges'])
            elif res['ranges'] != first[1]:
                print(f'h2h_pick: {folder.name}: not on the same openings as {first[0]}', file=sys.stderr)
                return 1
            results[(lo, hi)] = res
    strengths = fit_strengths([(lo, hi, r['d'], r['e']) for (lo, hi), r in results.items()], labels, prefer)
    winner, applied = pick_winner(strengths, prefer, margin, labels)
    line = constants_line(declaration, name, results, strengths, winner, applied, time.strftime('%Y-%m-%d'))
    pick = {'const': declaration['const'], 'values': sha, 'prefer': prefer, 'tie_margin': margin,
            'pairings': [{'base': lo, 'test': hi, 'ptnml': r['ptnml'], 'pairs': r['pairs'], 'd': r['d'], 'e': r['e'],
                          'runs': r['runs']} for (lo, hi), r in results.items()],
            'strengths': {x: list(strengths[x]) for x in labels}, 'winner': winner, 'tie_rule_applied': applied}
    (here / 'pick.json').write_text(json.dumps(pick, indent=1), encoding='utf-8')
    (here / 'constants-line.md').write_text(line + '\n', encoding='utf-8')
    for (lo, hi), r in results.items():
        print(f"{lo} vs {hi}: {hi} - {lo} {r['d']:+.2f} +/- {r['e']:.2f} nElo, {2 * r['pairs']:,} games, "
              f"Ptnml(0-2): {r['ptnml']}")
    for x in labels:
        print(f'{x}: {strengths[x][0]:+.2f} +/- {strengths[x][1]:.2f} nElo against {prefer}')
    print(f"winner: {winner}{' (the declared tie rule keeps ' + prefer + ')' if applied else ''}")
    print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
