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

    python3 tools/gauntlet/report.py SHARDS TABLE OUT ORDO [ORDO ARGS...]

SHARDS holds one folder per shard (games.pgn, anchor.csv, shard.txt, as the
games job writes them); TABLE is tools/gauntlet/anchors.tsv; ORDO is the
command that runs Ordo. OUT receives gauntlet.pgn and anchors.csv (Ordo's
input: the anchors' games and ratings), ordo.txt, ordo.log, reference.pgn
(the reference opponents' games) and summary.md, which is also printed.
"""
import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'cloud'))

import sprt_merge as sm  # noqa: E402


def gap(name, ccrl, pgns):
    """The summary line for a reference opponent, from its shards' PGNs."""
    points, pairs = [], []
    for pgn in pgns:
        rounds = {}
        for g in re.split(r'^\[Event ', pgn, flags=re.M)[1:]:
            tag = dict(re.findall(r'^\[(\w+) "(.*)"\]', g, re.M))
            p = {'1-0': 1.0, '0-1': 0.0, '1/2-1/2': 0.5}.get(tag.get('Result'))
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


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 4:
        sys.exit(__doc__)
    shards, table, out, ordo = argv[0], argv[1], Path(argv[2]), argv[3:]
    rows = [r.split('\t') for r in Path(table).read_text(encoding='utf-8').splitlines() if r.strip() and r[0] != '#']
    reference = {r[0] for r in rows if r[3] == 'reference'}
    folders = sorted(p for p in Path(shards).iterdir() if p.is_dir())
    games = {}  # (anchor name, CCRL Blitz) -> [each shard's PGN]
    for f in folders:
        name, ccrl = (f / 'anchor.csv').read_text(encoding='utf-8').strip().rsplit(',', 1)
        games.setdefault((name.strip('"'), ccrl), []).append((f / 'games.pgn').read_text(encoding='utf-8',
                                                                                          errors='replace'))
    fit = sorted(k for k in games if k[0] not in reference)
    pgn = ''.join(p for k in fit for p in games[k])
    (out / 'gauntlet.pgn').write_text(pgn, encoding='utf-8')
    (out / 'anchors.csv').write_text(''.join(f'"{k[0]}",{k[1]}\n' for k in fit), encoding='utf-8')
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
    lines += ['Shards:'] + ['- ' + (f / 'shard.txt').read_text(encoding='utf-8').replace('\n', ' ') for f in folders]
    summary = '\n'.join(lines) + '\n'
    (out / 'summary.md').write_text(summary, encoding='utf-8')
    sys.stdout.write(summary)
    return 0


if __name__ == '__main__':
    sys.exit(main())
