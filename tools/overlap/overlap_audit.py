# SPDX-License-Identifier: GPL-3.0-or-later
"""The training-data audit's validation/training overlap check (owner, 2026-11-11; before retrain 8c's network
decision). The streaming is done by fork_overlap_audit (tools/overlap/overlap_audit.cpp, built by build.sh); this
script prepares its inputs and summarises its outputs. Definitions are in overlap_audit.cpp's header.

    overlap_audit.py train-list --files-json FILES.json --manifests DIR --roots DIR... --out TRAIN.lst
                                [--extra GROUP=PATH[:SKIP]]... [--sha256]
    overlap_audit.py fens SET.tsv|SET.jsonl --out FENS.txt      (a 'fen' column or key; one FEN per line)
    overlap_audit.py summary PREFIX --pairs PAIRS.json [--manifests DIR] [--json OUT]

train-list: the training files of a retrain (the kernel's files.json for an arm), each found under --roots by name
(and by size when its manifest gives one), grouped by the snapshot that added it (SNAPSHOT_GROUPS); --sha256 checks
every file against its manifest. --extra adds files outside the list (SKIP = leading games left out, e.g. the 60
games a validation shard gives to the validation file).

summary: PAIRS.json is a list of {"name", "queries": [sets], "groups": [training groups]}; for each pair it reports
the query positions whose key occurs in those groups (all positions and the kept ones, K1 and K0, by ply and piece
count), the query games found whole in them, and the games whose start position they hold.
"""
import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

# The snapshot that first added each manifest's files (DESIGN.md decisions log; retrain-8b plan §1).
SNAPSHOT_GROUPS = {
    's2': ['g2s1', 'g3s1', 'g3b', 'g3c', 'g3d', 'g3e', 'g3s2'],   # item 7's g3s2
    's3': ['g3f', 'g3g', 'g3s3'],                                  # 8a's g3s3 adds these
    's4': ['g3h', 'g3i', 'g3j', 'g4', 'g4s1-pre', 'r8b-g4'],      # 8b's g4s1 adds these
}
PLY_BUCKETS = [(0, 0), (1, 9), (10, 19), (20, 39), (40, 79), (80, 10 ** 6)]
PIECE_BUCKETS = [(2, 5), (6, 7), (8, 12), (13, 20), (21, 26), (27, 32)]


def manifest_records(mdir):
    """{file name: (manifest, sha256, bytes or None)} over every manifest in mdir."""
    out = {}
    for p in sorted(Path(mdir).glob('*.json')):
        d = json.load(open(p))
        for key in ('batches',):
            for b in d.get(key, []):
                for s in b:
                    out.setdefault(s['file'], (p.stem, s.get('sha256'), s.get('bytes')))
        for s in d.get('held', []):
            out.setdefault(s['file'], (p.stem, s.get('sha256'), s.get('bytes')))
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def default_exe():
    root = Path(__file__).resolve().parents[2]
    exe = root / 'build' / 'overlap' / 'fork_overlap_audit'
    return str(exe.with_suffix('.exe')) if os.name == 'nt' else str(exe)


def positions_in_training(fens, train_list, exe=None):
    """The held-out sets' overlap step (owner, 2026-11-11: zero overlap with every training file). Returns
    (hits, totals): hits = [(index, fen, groups)] of the FENs whose placement and side to move (K0, the coarser key,
    so the check is the stricter one) occur anywhere in TRAIN.lst's files, every record of every game compared by
    fork_overlap_audit; totals = the files, games and positions scanned. Raises if the tool fails or a training file
    is malformed or truncated."""
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        Path(d, 'set.fens').write_text('\n'.join(fens) + '\n', encoding='utf-8')
        Path(d, 'q.lst').write_text(f'fen\theld\t{Path(d, "set.fens")}\n', encoding='utf-8')
        prefix = str(Path(d, 'r'))
        subprocess.run([exe or default_exe(), str(Path(d, 'q.lst')), train_list, prefix], check=True)
        files = [l.rstrip('\n').split('\t') for l in open(prefix + '-files.tsv', encoding='utf-8')][1:]
        bad = [f[1] for f in files if f[-1] or f[-2] != '0']
        if bad:
            raise RuntimeError(f'malformed or truncated training files: {bad}')
        names = {int(b): g for b, g in (l.rstrip('\n').split('\t') for l in
                                        list(open(prefix + '-groups.tsv', encoding='utf-8'))[1:])}
        rows = [l.rstrip('\n').split('\t') for l in open(prefix + '-queries.tsv', encoding='utf-8')][1:]
    hits = []
    for i, (fen, r) in enumerate(zip(fens, rows)):
        mask = int(r[10], 16)
        if mask:
            hits.append((i, fen, [names[b] for b in sorted(names) if mask >> b & 1]))
    return hits, {'files': len(files), 'games': sum(int(f[3]) for f in files),
                  'positions': sum(int(f[4]) for f in files)}


def cmd_train_list(a):
    names = json.load(open(a.files_json))['files']
    records = manifest_records(a.manifests)
    group_of = {m: g for g, ms in SNAPSHOT_GROUPS.items() for m in ms}
    found = defaultdict(list)
    for root in a.roots:
        for dirpath, _, files in os.walk(root):
            for f in files:
                if f.endswith('.vf'):
                    found[f].append(os.path.join(dirpath, f))
    lines, problems = [], []
    for n in names:
        if n not in records:
            problems.append(f'{n}: in no manifest')
            continue
        manifest, digest, size = records[n]
        group = group_of.get(manifest)
        if group is None:
            problems.append(f'{n}: manifest {manifest} has no snapshot group')
            continue
        cands = [p for p in sorted(found.get(n, [])) if size is None or os.path.getsize(p) == size]
        if not cands:
            problems.append(f'{n}: not found under the roots (size {size})')
            continue
        path = cands[0]
        if a.sha256 and digest and sha256(path) != digest:
            problems.append(f'{n}: SHA-256 differs from {manifest}.json at {path}')
            continue
        lines.append(f'{group}\t{path}\t0')
    for e in a.extra:
        group, rest = e.split('=', 1)
        path, _, skip = rest.rpartition(':') if rest.rsplit(':', 1)[-1].isdigit() else (rest, '', '0')
        name = os.path.basename(path)
        if a.sha256 and name in records and records[name][1] and sha256(path) != records[name][1]:
            problems.append(f'{name}: SHA-256 differs from {records[name][0]}.json at {path}')
        lines.append(f'{group}\t{path}\t{skip or 0}')
    if problems:
        print('\n'.join(problems), file=sys.stderr)
        return 1
    Path(a.out).write_text('\n'.join(lines) + '\n')
    print(f'{len(lines)} training files written to {a.out}')
    return 0


def cmd_fens(a):
    out = []
    path = Path(a.input)
    if path.suffix == '.jsonl':
        for line in open(path):
            if line.strip():
                out.append(json.loads(line)['fen'])
    else:
        header = None
        for line in open(path):
            cols = line.rstrip('\n').split('\t')
            if header is None:
                header = [c.strip('# ').split(' ')[0] for c in cols]
                if 'fen' not in header:
                    raise SystemExit(f'{path}: no fen column in {header}')
                continue
            if cols and cols[0].strip():
                out.append(cols[header.index('fen')])
    Path(a.out).write_text('\n'.join(out) + '\n')
    print(f'{len(out)} FENs written to {a.out}')
    return 0


def bucket(v, buckets):
    for lo, hi in buckets:
        if lo <= v <= hi:
            return f'{lo}-{hi}' if hi < 10 ** 6 else f'{lo}+'
    return 'other'


def rate(n, d):
    return round(n / d, 6) if d else None


def cmd_summary(a):
    groups_tsv = [l.rstrip('\n').split('\t') for l in open(f'{a.prefix}-groups.tsv')][1:]
    bit = {g[1]: int(g[0]) for g in groups_tsv}
    files = [l.rstrip('\n').split('\t') for l in open(f'{a.prefix}-files.tsv')]
    fh, files = files[0], files[1:]
    queries = [l.rstrip('\n').split('\t') for l in open(f'{a.prefix}-queries.tsv')]
    qh, queries = queries[0], queries[1:]
    games = [l.rstrip('\n').split('\t') for l in open(f'{a.prefix}-games.tsv')]
    gh, games = games[0], games[1:]
    qi, gi, fi = ({k: i for i, k in enumerate(h)} for h in (qh, gh, fh))
    pairs = json.load(open(a.pairs))
    report = {'files': [], 'pairs': []}

    errors = [f for f in files if f[fi['error']] or f[fi['truncated']] != '0']
    report['file_errors'] = [{'path': f[fi['path']], 'error': f[fi['error']], 'truncated': f[fi['truncated']]}
                             for f in errors]
    totals = Counter()
    for f in files:
        for k in ('games', 'positions', 'saved', 'kept'):
            totals[(f[fi['group']], k)] += int(f[fi[k]])
    report['groups'] = {g: {k: totals[(g, k)] for k in ('games', 'positions', 'saved', 'kept')} for g in bit}
    if a.manifests:
        records = manifest_records(a.manifests)
        checks = []
        for f in files:
            name = os.path.basename(f[fi['path']])
            m = None
            for mp in Path(a.manifests).glob('*.json'):
                d = json.load(open(mp))
                for b in d.get('batches', []) + [d.get('held', [])]:
                    for s in b:
                        if s.get('file') == name and 'positions' in s:
                            m = s
                if m:
                    break
            if m and f[fi['skip']] == '0':
                checks.append({'file': name, 'positions': [int(f[fi['positions']]), m['positions']],
                               'saved': [int(f[fi['saved']]), m.get('positions_saved')],
                               'games': [int(f[fi['games']]), m.get('games')]})
        report['manifest_checks'] = {
            'files_compared': len(checks),
            'mismatches': [c for c in checks if c['positions'][0] != c['positions'][1]
                           or (c['saved'][1] is not None and c['saved'][0] != c['saved'][1])
                           or (c['games'][1] is not None and c['games'][0] != c['games'][1])]}
        del records
    g3j = sum(int(f[fi['kept']]) for f in files if os.path.basename(f[fi['path']]) in
              {f'g3j-w0{k}.vf' for k in range(5)})
    report['kept_rule_check'] = {'g3j_w00_w04_kept': g3j, 'idea52_8b_sites_json': 62144106,
                                 'equal': g3j == 62144106}

    for p in pairs:
        mask = 0
        for g in p['groups']:
            mask |= 1 << bit[g]
        sets = set(p['queries'])
        rows = [q for q in queries if q[qi['set']] in sets]
        res = {'name': p['name'], 'queries': p['queries'], 'groups': p['groups']}
        for kind in ('all', 'kept'):
            sel = rows if kind == 'all' else [q for q in rows if q[qi['kept']] == '1']
            if kind == 'kept' and not sel:
                continue
            hit1 = [q for q in sel if int(q[qi['k1_mask']], 16) & mask]
            hit1k = [q for q in sel if int(q[qi['k1_kept_mask']], 16) & mask]
            hit0 = [q for q in sel if int(q[qi['k0_mask']], 16) & mask]
            uniq = {q[qi['fen4']] for q in sel}
            uniq_hit = {q[qi['fen4']] for q in hit1}
            r = {'positions': len(sel), 'k1_in_train': len(hit1), 'k1_rate': rate(len(hit1), len(sel)),
                 'k1_in_train_as_kept': len(hit1k), 'k1_kept_rate': rate(len(hit1k), len(sel)),
                 'k0_in_train': len(hit0), 'k0_rate': rate(len(hit0), len(sel)),
                 'unique_k1': len(uniq), 'unique_k1_in_train': len(uniq_hit),
                 'unique_k1_rate': rate(len(uniq_hit), len(uniq))}
            by_ply, by_pieces = Counter(), Counter()
            n_ply, n_pieces = Counter(), Counter()
            for q in sel:
                ply, pieces = int(q[qi['ply']]), int(q[qi['pieces']])
                b1, b2 = bucket(ply, PLY_BUCKETS) if ply >= 0 else 'n/a', bucket(pieces, PIECE_BUCKETS)
                n_ply[b1] += 1
                n_pieces[b2] += 1
            for q in hit1:
                ply, pieces = int(q[qi['ply']]), int(q[qi['pieces']])
                by_ply[bucket(ply, PLY_BUCKETS) if ply >= 0 else 'n/a'] += 1
                by_pieces[bucket(pieces, PIECE_BUCKETS)] += 1
            r['k1_by_ply'] = {k: [by_ply[k], n_ply[k]] for k in n_ply}
            r['k1_by_pieces'] = {k: [by_pieces[k], n_pieces[k]] for k in n_pieces}
            if kind == 'kept' and p.get('prefix'):
                # The per-superbatch monitoring prefix: the first N kept positions of the first query set's file.
                first = [q for q in sel if q[qi['set']] == p['queries'][0]][:p['prefix']]
                ph = [q for q in first if int(q[qi['k1_mask']], 16) & mask]
                r['prefix'] = {'positions': len(first), 'k1_in_train': len(ph), 'k1_rate': rate(len(ph), len(first))}
            res[kind] = r
        grows = [g for g in games if g[gi['set']] in sets]
        if grows:
            ident = [g for g in grows if int(g[gi['identical_mask']], 16) & mask]
            start = [g for g in grows if int(g[gi['start_mask']], 16) & mask]
            res['games'] = {'games': len(grows), 'identical_in_train': len(ident),
                            'identical_rate': rate(len(ident), len(grows)),
                            'start_position_in_train': len(start), 'start_rate': rate(len(start), len(grows))}
        report['pairs'].append(res)
    text = json.dumps(report, indent=1)
    if a.json:
        Path(a.json).write_text(text + '\n')
    print(text)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    t = sub.add_parser('train-list')
    t.add_argument('--files-json', required=True)
    t.add_argument('--manifests', required=True)
    t.add_argument('--roots', nargs='+', required=True)
    t.add_argument('--extra', action='append', default=[])
    t.add_argument('--sha256', action='store_true')
    t.add_argument('--out', required=True)
    f = sub.add_parser('fens')
    f.add_argument('input')
    f.add_argument('--out', required=True)
    s = sub.add_parser('summary')
    s.add_argument('prefix')
    s.add_argument('--pairs', required=True)
    s.add_argument('--manifests')
    s.add_argument('--json')
    a = ap.parse_args(argv)
    return {'train-list': cmd_train_list, 'fens': cmd_fens, 'summary': cmd_summary}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
