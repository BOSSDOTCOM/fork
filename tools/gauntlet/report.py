# SPDX-License-Identifier: GPL-3.0-or-later

"""The gauntlet's result (.github/workflows/gauntlet.yml, job "ordo"): merges
the game shards and rates Fork with Ordo, the anchors fixed at their CCRL
Blitz ratings. A reference opponent (role "reference" in
tools/gauntlet/anchors.tsv: Stockfish) is kept out of the fit and reported
apart as the gap to it: Fork's score, the Elo difference it implies, and a
95% interval from the game pairs (pentanomial, as tools/cloud/sprt_merge.py;
with -repeat, the two games of a shard's round share an opening, so a pair
is keyed by its shard, round and starting FEN). Its CCRL Blitz rating is
shown for context only. Near a zero score the interval is wide and
lopsided, and its lower end can be -inf.

    python3 tools/gauntlet/report.py [--previous GAUNTLET] [--baseline GAUNTLET --adopted JSON]
        SHARDS TABLE OUT ORDO [ORDO ARGS...]
    python3 tools/gauntlet/report.py --check SHARDS TABLE OUT CLAIM

SHARDS holds one folder per shard (games.pgn, anchor.csv, shard.txt, as the
games job writes them); TABLE is tools/gauntlet/anchors.tsv; ORDO is the
command that runs Ordo. OUT receives gauntlet.pgn and anchors.csv (Ordo's
input: the anchors' games and ratings), ordo.txt, ordo.log, reference.pgn
(the reference opponents' games) and summary.md, which is also printed.
Without the options the output is exactly the gauntlet's report as before.

The anchor check (docs/research/transfer-testing/report.md §5; owner,
2026-11-09). Both levels measure a gain the same way: openings are
identified by the game's FEN header, and a cell is one anchor and one
opening; only cells both sides played count (paired by opening). The gain
is the difference of two plain logistic fits of Fork's rating, each solving
sum over anchors of n_a E(R - R_a) = Fork's points, with the anchors fixed
at their CCRL Blitz ratings from TABLE (a draw counts half; no white or draw
parameter, as every opening is played with both colours). This is the same
logistic Elo scale as the SPRTs' "Elo" figure. Its uncertainty is a
bootstrap over openings: RESAMPLES resamples with replacement (seeded with
SEED, so a report is reproducible), the same openings for both sides and
every anchor, which keeps the pairing; the report gives the SD and the
2.5% and 97.5% percentiles.

Level 0 (no extra games), options of the gauntlet report:
- --previous GAUNTLET: the previous gauntlet's result folder (its
  gauntlet.pgn is read) or a merged PGN: the gain of this run over it on the
  anchors both runs played, overall and per anchor.
- --baseline GAUNTLET --adopted JSON: the running transfer ratio, the anchor
  gain since the baseline gauntlet over the summed self-play Elo of the
  changes adopted since (tools/gauntlet/transfer.json: "adopted", a list of
  {"change", "elo", "ci95", "test"}, ci95 the half-width of the 95%
  interval; its "baseline" and "previous" name the runs the workflow
  downloads). The ratio's interval divides each bootstrap draw of the gain
  by a normal draw of the sum (SE = the root of the summed (ci95 / 1.96)^2).

Level 1 (--check): the two-engine mode's report. SHARDS holds one folder per
shard, each with old.pgn and new.pgn (OLD and NEW Fork against one anchor on
the same openings), anchor.csv and shard.txt; OUT receives old.pgn, new.pgn
(merged) and summary.md. CLAIM is NEW's claimed self-play gain over OLD
(Elo). The report gives NEW - OLD per anchor and pooled, and the outcome:
- confirmed: the pooled gain's lower 95% bound is above 0;
- consistent: not confirmed, but the pooled gain is at least CLAIM minus 2
  bootstrap SDs of the gain;
- flagged for the owner's review: otherwise.
It never reverts anything.
"""
import json
import math
import random
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'cloud'))

import sprt_merge as sm  # noqa: E402

SEED = 20261109     # the date of the owner's decision; any fixed value would do
RESAMPLES = 4000    # the transfer-testing report's count: its SDs move by about 1% between seeds
POINTS = {'1-0': 1.0, '0-1': 0.0, '1/2-1/2': 0.5}


def headers(pgn):
    """Each game's tag pairs, in order."""
    return [dict(re.findall(r'^\[(\w+) "(.*)"\]', g, re.M)) for g in re.split(r'^\[Event ', pgn, flags=re.M)[1:]]


def gap(name, ccrl, pgns):
    """The summary line for a reference opponent, from its shards' PGNs."""
    points, pairs = [], []
    for pgn in pgns:
        rounds = {}
        for tag in headers(pgn):
            p = POINTS.get(tag.get('Result'))
            if p is None:  # unfinished ("*"): Ordo leaves it out too
                continue
            p = p if tag['White'] == 'Fork' else 1.0 - p
            points.append(p)
            rounds.setdefault((tag.get('Round'), tag.get('FEN')), []).append(p)
        pairs += [r for r in rounds.values() if len(r) == 2]
    ptnml = [0] * 5
    for r in pairs:
        ptnml[round(2 * sum(r))] += 1
    n, mean, var = sm.moments(ptnml)
    half = 1.96 * math.sqrt(var / n) if n else 0.0
    low = sm.elo(mean - half) if mean - half > 0 else -math.inf
    high = sm.elo(mean + half) if mean + half < 1 else math.inf
    return (f'- {name} (CCRL Blitz {ccrl}, for context only): Fork {sum(points):g}/{len(points)} '
            f'({100 * sum(points) / len(points):.1f}%), +{points.count(1.0)} ={points.count(0.5)} '
            f'-{points.count(0.0)}; Elo {sm.elo(mean):.1f}, 95% interval {low:.1f} to {high:.1f} '
            f'(pentanomial, {n} pairs, Ptnml(0-2) {ptnml})')


def cells(pgn):
    """Fork's finished games by anchor and opening: {anchor: {FEN: [points, games]}}."""
    out = {}
    for tag in headers(pgn):
        p = POINTS.get(tag.get('Result'))
        if p is None or 'Fork' not in (tag.get('White'), tag.get('Black')):
            continue
        white = tag['White'] == 'Fork'
        c = out.setdefault(tag['Black'] if white else tag['White'], {}).setdefault(tag.get('FEN', ''), [0.0, 0])
        c[0] += p if white else 1.0 - p
        c[1] += 1
    return out


def fit(totals, ratings):
    """Fork's rating from {anchor: (points, games)}: the root of sum n_a E(R - R_a) = points (bisection;
    +-inf at a zero or full score)."""
    points = sum(t[0] for t in totals.values())
    games = sum(t[1] for t in totals.values())
    if points <= 0 or points >= games:
        return math.copysign(math.inf, points - 0.5 * games) if games else math.nan
    if len(totals) == 1:
        (a, _), = totals.items()
        return ratings[a] - 400 * math.log10(games / points - 1)
    lo, hi = min(ratings[a] for a in totals) - 3000.0, max(ratings[a] for a in totals) + 3000.0
    for _ in range(60):
        r = (lo + hi) / 2
        e = sum(t[1] / (1 + 10 ** ((ratings[a] - r) / 400)) for a, t in totals.items())
        lo, hi = (r, hi) if e < points else (lo, r)
    return (lo + hi) / 2


def spread(draws):
    """(SD, 2.5% and 97.5% percentiles) of bootstrap draws."""
    v = sorted(draws)
    n = len(v)
    if not all(math.isfinite(x) for x in v):
        sd = math.inf
    else:
        m = sum(v) / n
        sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))
    return sd, v[round(0.025 * (n - 1))], v[round(0.975 * (n - 1))]


def compare(old, new, ratings, sides=('OLD', 'NEW'), seed=SEED, resamples=RESAMPLES):
    """The paired gain of NEW over OLD (each a cells() result) on the anchors both played on a common
    opening and TABLE rates. SIDES names the two in the list of anchors left out. Returns a dict:
    anchors, left (anchor -> why it was left out), openings, games (OLD's, NEW's), gain, per_anchor
    {anchor: gain}, scores {anchor: ((points, games) OLD, (points, games) NEW)}, draws (the pooled gain
    per resample) and per_draws {anchor: [its gain per resample]}."""
    both = set(old) & set(new)
    left = {a: 'not in the anchor table' for a in both if a not in ratings}
    left.update({a: f'{sides[0]} only' for a in set(old) - both})
    left.update({a: f'{sides[1]} only' for a in set(new) - both})
    paired = {a: sorted(set(old[a]) & set(new[a])) for a in both if a in ratings}
    left.update({a: 'no opening in common' for a, fs in paired.items() if not fs})
    anchors = sorted(a for a, fs in paired.items() if fs)
    openings = sorted({f for fs in paired.values() for f in fs})
    index = {f: i for i, f in enumerate(openings)}
    # Per anchor: (opening index, old points, old games, new points, new games) for each paired opening.
    rows = {a: [(index[f], *old[a][f], *new[a][f]) for f in paired[a]] for a in anchors}

    def totals(weights):
        o, n = {}, {}
        for a, rs in rows.items():
            t = [0.0, 0, 0.0, 0]
            for i, *v in rs:
                if weights[i]:
                    for k in range(4):
                        t[k] += weights[i] * v[k]
            o[a], n[a] = (t[0], t[1]), (t[2], t[3])
        return o, n

    def gains(weights):
        o, n = totals(weights)
        pooled = fit(n, ratings) - fit(o, ratings)
        return pooled, {a: fit({a: n[a]}, ratings) - fit({a: o[a]}, ratings) for a in anchors}, o, n

    result = {'anchors': anchors, 'left': left, 'openings': len(openings)}
    if not anchors:
        return result
    gain, per_anchor, o, n = gains([1] * len(openings))
    result.update(gain=gain, per_anchor=per_anchor, scores={a: (o[a], n[a]) for a in anchors},
                  games=(sum(t[1] for t in o.values()), sum(t[1] for t in n.values())))
    rng = random.Random(seed)
    draws, per_draws = [], {a: [] for a in anchors}
    for _ in range(resamples):
        weights = [0] * len(openings)
        for _ in openings:
            weights[rng.randrange(len(openings))] += 1
        g, per, _, _ = gains(weights)
        draws.append(g)
        for a in anchors:
            per_draws[a].append(per[a])
    result.update(draws=draws, per_draws=per_draws)
    return result


def signed(x, digits=1):
    return f'{x:+.{digits}f}' if math.isfinite(x) else ('+inf' if x > 0 else '-inf' if x < 0 else 'n/a')


def interval(draws):
    sd, low, high = spread(draws)
    return f'bootstrap SD {sd:.1f}, 95% interval {signed(low)} to {signed(high)}'


def method_note(c):
    return (f'paired by opening: {c["openings"]} openings, {c["games"][0]} and {c["games"][1]} games; plain '
            f'logistic fit, the anchors at their CCRL Blitz ratings; bootstrap of {RESAMPLES} resamples of the '
            f'openings, seed {SEED}')


def left_note(c):
    return ['- Not compared: ' + ', '.join(f'{a} ({why})' for a, why in sorted(c['left'].items()))] if c['left'] else []


def read_gauntlet(path):
    p = Path(path)
    return (p / 'gauntlet.pgn' if p.is_dir() else p).read_text(encoding='utf-8', errors='replace')


def level0(pgn, ratings, previous=None, baseline=None, adopted=None):
    """The anchor check's level 0 section of the gauntlet report (a list of lines)."""
    now = cells(pgn)
    lines = []
    if previous is not None:
        c = compare(cells(read_gauntlet(previous)), now, ratings, ('the previous run', 'this run'))
        lines.append('### Anchor check: gain over the previous gauntlet')
        if 'gain' not in c:
            lines += ['- No anchor and opening played in both runs.'] + left_note(c)
        else:
            lines += [f'- On {", ".join(c["anchors"])}: {signed(c["gain"])} Elo, {interval(c["draws"])} '
                      f'({method_note(c)})',
                      '- Per anchor: ' + '; '.join(f'{a} {signed(c["per_anchor"][a])} (SD {spread(c["per_draws"][a])[0]:.1f})'
                                                   for a in c['anchors'])] + left_note(c)
    if baseline is not None:
        data = json.loads(Path(adopted).read_text(encoding='utf-8'))
        changes = data['adopted']
        total = sum(float(x['elo']) for x in changes)
        se = math.sqrt(sum((float(x['ci95']) / 1.96) ** 2 for x in changes))
        c = compare(cells(read_gauntlet(baseline)), now, ratings, ('the baseline run', 'this run'))
        base = data.get('baseline', {})
        lines.append('### Anchor check: running transfer ratio since the baseline gauntlet'
                     + (f' (run {base["run"]}, commit {base.get("commit", "?")})' if 'run' in base else ''))
        lines.append(f'- Self-play: {len(changes)} adopted changes sum to {signed(total)} +/- {1.96 * se:.1f} Elo (95%): '
                     + '; '.join(f'{x["change"]} {signed(float(x["elo"]), 2)}' for x in changes))
        if 'gain' not in c:
            lines += ['- No anchor and opening played in both runs.'] + left_note(c)
        else:
            lines.append(f'- Against the anchors ({", ".join(c["anchors"])}): {signed(c["gain"])} Elo, '
                         f'{interval(c["draws"])} ({method_note(c)})')
            if total > 0:
                rng = random.Random(SEED)
                _, low, high = spread([g / rng.gauss(total, se) for g in c['draws']])
                lines.append(f'- Transfer ratio {c["gain"] / total:.2f}, 95% interval {low:.2f} to {high:.2f} (each '
                             f'bootstrap draw of the anchor gain over a normal draw of the sum); gap '
                             f'{signed(c["gain"] - total)} +/- {math.hypot(spread(c["draws"])[0], se):.1f} Elo (1 SE)')
            else:
                lines.append('- Transfer ratio: not defined (the self-play sum is not above 0)')
            lines += left_note(c)
    return lines


def outcome(gain, sd, low, claim):
    """The level 1 outcome (see the module's docstring)."""
    if low > 0:
        return 'confirmed'
    if gain >= claim - 2 * sd:
        return 'consistent'
    return "flagged for the owner's review"


def score(t):
    return f'{t[0]:g}/{t[1]} ({100 * t[0] / t[1]:.1f}%)' if t[1] else '0/0'


def check(argv):
    """Level 1: report.py --check SHARDS TABLE OUT CLAIM."""
    if len(argv) != 4:
        sys.exit(__doc__)
    shards, table, out, claim = Path(argv[0]), argv[1], Path(argv[2]), float(argv[3])
    ratings = read_ratings(table)
    folders = sorted(p for p in shards.iterdir() if p.is_dir())
    old = ''.join((f / 'old.pgn').read_text(encoding='utf-8', errors='replace') for f in folders)
    new = ''.join((f / 'new.pgn').read_text(encoding='utf-8', errors='replace') for f in folders)
    (out / 'old.pgn').write_text(old, encoding='utf-8')
    (out / 'new.pgn').write_text(new, encoding='utf-8')
    c = compare(cells(old), cells(new), ratings)
    lines = ['### Anchor check: NEW against OLD, paired by opening']
    if 'gain' not in c:
        lines += ['No anchor and opening played by both sides: no result.'] + left_note(c)
    else:
        sd, low, high = spread(c['draws'])
        verdict = outcome(c['gain'], sd, low, claim)
        lines += [f'{c["games"][0] + c["games"][1]} games; claimed self-play gain {signed(claim)} Elo; '
                  f'{method_note(c)}.', '',
                  '| Anchor | OLD | NEW | NEW - OLD (Elo) | Bootstrap SD | 95% interval |', '|---|---|---|---|---|---|']
        for a in c['anchors']:
            s, (o, n) = spread(c['per_draws'][a]), c['scores'][a]
            lines.append(f'| {a} | {score(o)} | {score(n)} | {signed(c["per_anchor"][a])} | {s[0]:.1f} | '
                         f'{signed(s[1])} to {signed(s[2])} |')
        o = tuple(sum(c['scores'][a][0][i] for a in c['anchors']) for i in (0, 1))
        n = tuple(sum(c['scores'][a][1][i] for a in c['anchors']) for i in (0, 1))
        lines += [f'| Pooled | {score(o)} | {score(n)} | {signed(c["gain"])} | {sd:.1f} | {signed(low)} to {signed(high)} |',
                  '', f'**Outcome: {verdict}.** Confirmed: the lower 95% bound is above 0. Consistent: not confirmed, '
                  f'but the gain is at least the claim minus 2 SD ({signed(claim - 2 * sd)}). Otherwise flagged for '
                  "the owner's review. The check never reverts anything."]
        if claim > 0:
            lines.append(f'- Gain over the claim: {c["gain"] / claim:.2f}')
        lines += left_note(c)
    lines += ['Shards:'] + ['- ' + (f / 'shard.txt').read_text(encoding='utf-8').replace('\n', ' ') for f in folders]
    summary = '\n'.join(lines) + '\n'
    (out / 'summary.md').write_text(summary, encoding='utf-8')
    sys.stdout.write(summary)
    return 0


def read_rows(table):
    return [r.split('\t') for r in Path(table).read_text(encoding='utf-8').splitlines() if r.strip() and r[0] != '#']


def read_ratings(table):
    return {r[0]: float(r[2]) for r in read_rows(table)}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['--check']:
        return check(argv[1:])
    opts = {}
    while argv[:1] and argv[0] in ('--previous', '--baseline', '--adopted'):
        if len(argv) < 2:
            sys.exit(__doc__)
        opts[argv[0][2:]], argv = argv[1], argv[2:]
    if ('baseline' in opts) != ('adopted' in opts):
        sys.exit('report.py: --baseline and --adopted go together')
    if len(argv) < 4:
        sys.exit(__doc__)
    shards, table, out, ordo = argv[0], argv[1], Path(argv[2]), argv[3:]
    rows = read_rows(table)
    reference = {r[0] for r in rows if r[3] == 'reference'}
    folders = sorted(p for p in Path(shards).iterdir() if p.is_dir())
    games = {}  # (anchor name, CCRL Blitz) -> [each shard's PGN]
    for f in folders:
        name, ccrl = (f / 'anchor.csv').read_text(encoding='utf-8').strip().rsplit(',', 1)
        games.setdefault((name.strip('"'), ccrl), []).append((f / 'games.pgn').read_text(encoding='utf-8',
                                                                                          errors='replace'))
    fit_set = sorted(k for k in games if k[0] not in reference)
    pgn = ''.join(p for k in fit_set for p in games[k])
    (out / 'gauntlet.pgn').write_text(pgn, encoding='utf-8')
    (out / 'anchors.csv').write_text(''.join(f'"{k[0]}",{k[1]}\n' for k in fit_set), encoding='utf-8')
    (out / 'reference.pgn').write_text(''.join(p for k in sorted(games) if k[0] in reference for p in games[k]),
                                       encoding='utf-8')
    with open(out / 'ordo.log', 'w', encoding='utf-8') as log:
        subprocess.run(ordo + ['-p', str(out / 'gauntlet.pgn'), '-m', str(out / 'anchors.csv'), '-W', '-D',
                               '-s', '1000', '-o', str(out / 'ordo.txt')], stdout=log, stderr=subprocess.STDOUT,
                       check=True)
    lines = ['### Gauntlet: %d games' % len(re.findall(r'^\[Event ', pgn, re.M)), '```',
             (out / 'ordo.txt').read_text(encoding='utf-8').rstrip('\n'), '```']
    gaps = [gap(k[0], k[1], games[k]) for k in sorted(games) if k[0] in reference]
    if gaps:
        lines += ['### Gap to the reference opponents (outside the Ordo fit)'] + gaps
    if opts:
        lines += level0(pgn, read_ratings(table), opts.get('previous'), opts.get('baseline'), opts.get('adopted'))
    lines += ['Shards:'] + ['- ' + (f / 'shard.txt').read_text(encoding='utf-8').replace('\n', ' ') for f in folders]
    summary = '\n'.join(lines) + '\n'
    (out / 'summary.md').write_text(summary, encoding='utf-8')
    sys.stdout.write(summary)
    return 0


if __name__ == '__main__':
    sys.exit(main())
