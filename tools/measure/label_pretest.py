# SPDX-License-Identifier: GPL-3.0-or-later

"""Offline label-quality pre-tests for retrain 8b (owner, 2026-11-09; ideas.md
51 and 48; the declaration in docs/research/label-pretests/declaration-8b.md
fixes the set, the metric, the control, the candidates and the pass rule
before any comparison runs).

1. `sample`: N games of a held-out shard by a seeded draw, and in each one
   saved record (uniform, the same seed stream): sites.jsonl in the deep
   labellers' folder format (id, fen with the clocks, game "SHARD#INDEX",
   the record index, whether the trainer keeps it).
2. `deep`: each site's FEN searched by a pinned engine to N nodes (one
   thread, Hash 16, `ucinewgame` before each, Syzygy tables when given),
   WORKERS engines at below-normal priority; its last reported score is the
   deep value (side to move's view; a mate is written as +-20,000 and
   flagged), appended to deep.tsv as id, cp, mate, depth (crucial_points.py's
   format). Resumable: a rerun searches only the sites without a label.
3. `labels`: on a labelled sample, the label error of the control (the
   trainer's blend (1 - w) sigmoid(s / S) + w z, tools/train src/main.rs
   `mapper`) and of each candidate: TD(lambda) labels
   (tools/datagen/td_labels.py) at each lambda over the kept records, and
   the control over every saved record against the kept ones. The error is
   the squared difference to sigmoid(deep / S) (side to move's view); each
   comparison's difference of mean errors gets a 95% percentile interval
   from a bootstrap over games (a game resampled whole), paired where both
   sides score the same records.
4. `rank`: idea 48's closeness weighting as a weighting of the evaluation
   error: on deep-labelled search sites with each network's evaluation
   (seed-<net>.tsv), the plain and the closeness-weighted mean squared error
   sigmoid(eval / S) - sigmoid(deep / S) of each network, the weight
   exp(-gap^2 / (2 h^2)) of the site's gap to its nearest finite window bound
   (crucial_points.nearest_bound; h per kind of site), the difference of
   each network's error and the reference network's with a game bootstrap
   interval, and the weights' n_eff = (sum w)^2 / sum w^2. Mate-flagged deep
   labels and sites without a finite bound are left out.

    label_pretest.py sample SHARD --games N --seed S --out DIR
    label_pretest.py deep DIR --engine ENGINE --nodes N --workers W [--syzygy DIR]
    label_pretest.py labels DIR --data DIR... --scale S --blend W --lams L,... --boot B --seed S [--json OUT]
    label_pretest.py rank DIR... --nets A,B,... --reference NET --scale S --boot B --seed S [--json OUT]
"""
import argparse
import json
import math
import queue
import random
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import chess

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'datagen'))
import crucial_points  # noqa: E402
import td_labels as td  # noqa: E402
import verify_games as vg  # noqa: E402

BAND = 29250  # score_bounds.hpp: TbWinScore - MaxPly, the mate and table band


def sample_sites(data, name, games, seed):
    """`games` games of the shard bytes `data` by a seeded draw, one saved
    record each: [site dict]."""
    offsets = [start for start, _h, _r, _e in td.split_games(data)]
    rng = random.Random(seed)
    picks = sorted(rng.sample(range(len(offsets)), min(games, len(offsets))))
    out = []
    for index in picks:
        _start, head, recs, _end = next(td.split_games(data[offsets[index]:], 1))
        saved = [t for t, (_c, s) in enumerate(recs) if s != td.UNSAVED]
        if not saved:
            continue
        t = rng.choice(saved)
        board, _ = vg.decode_board(head)
        rows, _kind = td.replay(head, recs[:t + 1], table_pieces=0)
        for code, _s in recs[:t]:
            board.push(next(m for m in board.legal_moves if vg.code_of(board, m) == code))
        out.append({'id': len(out), 'fen': board.fen(), 'game': f'{name}#{index}', 'record': t,
                    'kept': rows[t][2]})
    return out, len(offsets)


def deep_search(engine, todo, out_path, nodes, workers, syzygy=None):
    """Searches each (id, fen) to `nodes` nodes; appends id, cp, mate, depth
    lines. `engine` is a path or a command list."""
    jobs = queue.Queue()
    for item in todo:
        jobs.put(item)
    lock = threading.Lock()
    flags = getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
    errors = []

    def work():
        p = subprocess.Popen(engine if isinstance(engine, list) else [engine], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
                             creationflags=flags)

        def send(line):
            p.stdin.write(line + '\n')
            p.stdin.flush()

        def until(token):
            last = None
            while True:
                line = p.stdout.readline()
                if not line:
                    raise RuntimeError('engine exited')
                if ' score ' in line:
                    last = line
                if line.startswith(token):
                    return last

        try:
            send('uci')
            until('uciok')
            send('setoption name Hash value 16')
            send('setoption name Threads value 1')
            if syzygy:
                send(f'setoption name SyzygyPath value {syzygy}')
            while True:
                try:
                    site_id, fen = jobs.get_nowait()
                except queue.Empty:
                    break
                send('ucinewgame')
                send('isready')
                until('readyok')
                send(f'position fen {fen}')
                send(f'go nodes {nodes}')
                info = until('bestmove') or ''
                cp = re.search(r' score cp (-?\d+)', info)
                mate = re.search(r' score mate (-?\d+)', info)
                depth = re.search(r' depth (\d+)', info)
                if cp:
                    value, flag = int(cp.group(1)), 0
                elif mate:
                    value, flag = (20000 if int(mate.group(1)) > 0 else -20000), 1
                else:
                    raise RuntimeError(f'no score for site {site_id}')
                with lock, open(out_path, 'a', encoding='utf-8') as f:
                    f.write(f'{site_id}\t{value}\t{flag}\t{depth.group(1) if depth else 0}\n')
            send('quit')
            p.wait(timeout=30)
        except Exception as e:  # noqa: BLE001 - reported after the join
            errors.append(str(e))
            p.kill()
            p.wait()
        finally:
            p.stdin.close()
            p.stdout.close()

    threads = [threading.Thread(target=work) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise RuntimeError('; '.join(errors))


def interval(values, level=0.95):
    v = sorted(values)
    lo = v[int(math.floor((1 - level) / 2 * (len(v) - 1)))]
    hi = v[int(math.ceil((1 + level) / 2 * (len(v) - 1)))]
    return lo, hi


def boot_difference(groups, boots, seed):
    """groups: per game, (sum_a, n_a, sum_b, n_b). The difference of means
    sum_a / n_a - sum_b / n_b, and its 95% percentile interval over `boots`
    resamples of the games."""
    def diff(sel):
        sa = sum(g[0] for g in sel)
        na = sum(g[1] for g in sel)
        sb = sum(g[2] for g in sel)
        nb = sum(g[3] for g in sel)
        return sa / na - sb / nb if na and nb else float('nan')

    rng = random.Random(seed)
    k = len(groups)
    reps = [diff([groups[rng.randrange(k)] for _ in range(k)]) for _ in range(boots)]
    reps = [r for r in reps if r == r]
    return diff(groups), interval(reps)


def label_errors(rows, scale, blend, lams):
    """Each matched record's squared errors: {'control', 'td=L'} plus its
    game, kept flag and end kind."""
    out = []
    cache = {}
    for r in rows:
        gold = td.win_pair(r['deep'], scale)[0]
        side = (lambda p: p) if r['white'] else (lambda p: 1.0 - p)
        v = td.win_pair(r['scores'][r['record']], scale)[0]
        z = td.WHITE_RESULT[r['result']]
        e = {'control': (side((1.0 - blend) * v + blend * z) - gold) ** 2}
        for lam in lams:
            key = (r['game'], lam)
            if key not in cache:
                cache[key] = td.td_targets(r['scores'], r['result'], lam, scale, skip=r['check'])
            label = cache[key][r['record']]
            if label is not None:  # none for a record in check (outside the chain)
                e[f'td={lam:g}'] = (side(label) - gold) ** 2
        out.append({'game': r['game'], 'kept': r['kept'], 'end': r['end'], 'err': e})
    return out


def label_report(errs, lams, boots, seed):
    games = {}
    for x in errs:
        games.setdefault(x['game'], []).append(x)
    report = {'records': len(errs), 'kept': sum(x['kept'] for x in errs), 'games': len(games), 'td': {}}
    kept_mse = {}
    for name in ['control'] + [f'td={lam:g}' for lam in lams]:
        ks = [x['err'][name] for x in errs if x['kept']]
        kept_mse[name] = sum(ks) / len(ks) if ks else float('nan')
    report['mse_kept'] = kept_mse
    for lam in lams:
        name = f'td={lam:g}'
        groups = [(sum(x['err'][name] for x in g if x['kept']), sum(x['kept'] for x in g),
                   sum(x['err']['control'] for x in g if x['kept']), sum(x['kept'] for x in g))
                  for g in games.values()]
        d, (lo, hi) = boot_difference(groups, boots, seed)
        report['td'][name] = {'difference': d, 'interval': [lo, hi], 'passes': hi < 0}
    groups = [(sum(x['err']['control'] for x in g), len(g),
               sum(x['err']['control'] for x in g if x['kept']), sum(x['kept'] for x in g)) for g in games.values()]
    d, (lo, hi) = boot_difference(groups, boots, seed)
    all_mse = sum(x['err']['control'] for x in errs) / len(errs) if errs else float('nan')
    report['unfiltered'] = {'mse_all_saved': all_mse, 'mse_kept': kept_mse['control'], 'difference': d,
                            'interval': [lo, hi], 'passes': hi < 0}
    ends = {}
    for x in errs:
        if x['kept']:
            ends.setdefault(x['end'], []).append(x)
    report['by_end'] = {k: {'n': len(v), **{n: sum(x['err'][n] for x in v) / len(v) for n in kept_mse}}
                        for k, v in sorted(ends.items())}
    return report


def read_rank_sites(folder, nets):
    deep = {}
    for line in (folder / 'deep.tsv').read_text(encoding='utf-8').splitlines():
        if line.strip():
            f = line.split('\t')
            deep[int(f[0])] = (int(f[1]), int(f[2]))
    evals = {}
    for net in nets:
        evals[net] = {int(i): int(v) for i, v in (x.split('\t') for x in
                                                  (folder / f'seed-{net}.tsv').read_text(encoding='utf-8').splitlines()
                                                  if x.strip())}
    out = []
    for line in (folder / 'sites.jsonl').read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        s = json.loads(line)
        sid = s['id']
        if sid not in deep or any(sid not in evals[n] for n in nets):
            continue
        out.append({'game': s['game'], 'kind': 1 if s['kind'] else 0, 'eval': s['eval'],
                    'alpha': s['alpha'], 'beta': s['beta'], 'deep': deep[sid][0], 'mate': deep[sid][1],
                    'evals': {n: evals[n][sid] for n in nets}})
    return out


def rank_report(sites, nets, reference, scale, h, boots, seed):
    used = []
    for s in sites:
        near = crucial_points.nearest_bound(s['eval'], s['alpha'], s['beta'])
        if near is None or s['mate'] or abs(s['deep']) >= BAND:
            continue
        gap = abs(s['eval'] - near[1])
        s['w'] = math.exp(-gap * gap / (2.0 * h[s['kind']] ** 2))
        gold = td.win_pair(s['deep'], scale)[0]
        s['err'] = {n: (td.win_pair(s['evals'][n], scale)[0] - gold) ** 2 for n in nets}
        used.append(s)
    w = [s['w'] for s in used]
    report = {'sites': len(sites), 'used': len(used), 'n_eff': (sum(w) ** 2 / sum(x * x for x in w)) if w else 0.0}
    report['n_eff_share'] = report['n_eff'] / len(used) if used else 0.0
    report['plain'] = {n: sum(s['err'][n] for s in used) / len(used) for n in nets}
    report['weighted'] = {n: sum(s['w'] * s['err'][n] for s in used) / sum(w) for n in nets}
    games = {}
    for s in used:
        games.setdefault(s['game'], []).append(s)
    report['against_reference'] = {}
    for n in nets:
        if n == reference:
            continue
        plain = [(sum(s['err'][n] for s in g), len(g), sum(s['err'][reference] for s in g), len(g))
                 for g in games.values()]
        weighted = [(sum(s['w'] * s['err'][n] for s in g), sum(s['w'] for s in g),
                     sum(s['w'] * s['err'][reference] for s in g), sum(s['w'] for s in g)) for g in games.values()]
        dp, ip = boot_difference(plain, boots, seed)
        dw, iw = boot_difference(weighted, boots, seed)
        report['against_reference'][n] = {'plain': {'difference': dp, 'interval': list(ip)},
                                          'weighted': {'difference': dw, 'interval': list(iw)}}
    report['games'] = len(games)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    p = sub.add_parser('sample')
    p.add_argument('shard', type=Path)
    p.add_argument('--games', type=int, required=True)
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('deep')
    p.add_argument('dir', type=Path)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--nodes', type=int, required=True)
    p.add_argument('--workers', type=int, required=True)
    p.add_argument('--syzygy')
    p = sub.add_parser('labels')
    p.add_argument('dir', type=Path)
    p.add_argument('--data', type=Path, nargs='+', required=True)
    p.add_argument('--scale', type=float, required=True)
    p.add_argument('--blend', type=float, required=True)
    p.add_argument('--lams', required=True)
    p.add_argument('--boot', type=int, required=True)
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--json', type=Path)
    p = sub.add_parser('rank')
    p.add_argument('dirs', type=Path, nargs='+')
    p.add_argument('--nets', required=True)
    p.add_argument('--reference', required=True)
    p.add_argument('--scale', type=float, required=True)
    p.add_argument('--h-main', type=float, required=True)
    p.add_argument('--h-quiet', type=float, required=True)
    p.add_argument('--boot', type=int, required=True)
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--json', type=Path)
    a = ap.parse_args(argv)
    began = time.monotonic()

    if a.command == 'sample':
        sites, total = sample_sites(a.shard.read_bytes(), a.shard.name, a.games, a.seed)
        a.out.mkdir(parents=True, exist_ok=True)
        with open(a.out / 'sites.jsonl', 'w', encoding='utf-8') as f:
            for s in sites:
                f.write(json.dumps(s, separators=(',', ':')) + '\n')
        print(f'{len(sites)} sites from {total} games of {a.shard.name} (seed {a.seed}), '
              f'{sum(s["kept"] for s in sites)} kept; {time.monotonic() - began:.1f} s')
        return 0

    if a.command == 'deep':
        path = a.dir / 'deep.tsv'
        done = set()
        if path.exists():
            lines = path.read_text(encoding='utf-8').split('\n')
            good = [x for x in lines[:-1] if x] if lines[-1] else [x for x in lines if x]
            path.write_text(''.join(x + '\n' for x in good), encoding='utf-8')  # drop a line cut short
            done = {int(x.split('\t')[0]) for x in good}
        sites = [json.loads(x) for x in (a.dir / 'sites.jsonl').read_text(encoding='utf-8').splitlines() if x]
        todo = [(s['id'], s['fen']) for s in sites if s['id'] not in done]
        print(f'{len(todo)} sites to search ({len(done)} done)', flush=True)
        deep_search(str(a.engine.resolve()), todo, path, a.nodes, a.workers, a.syzygy)
        print(f'done in {time.monotonic() - began:.0f} s', flush=True)
        return 0

    if a.command == 'labels':
        lams = [float(x) for x in a.lams.split(',')]
        rows, stats = td.matched_records([a.dir], a.data)
        report = label_report(label_errors(rows, a.scale, a.blend, lams), lams, a.boot, a.seed)
        report.update(match=stats, scale=a.scale, blend=a.blend, boot=a.boot, seed=a.seed,
                      seconds=round(time.monotonic() - began, 1))
        print(json.dumps(report, indent=1))
        if a.json:
            a.json.write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')
        return 0

    nets = a.nets.split(',')
    sites = [s for d in a.dirs for s in read_rank_sites(d, nets)]
    report = rank_report(sites, nets, a.reference, a.scale, {0: a.h_main, 1: a.h_quiet}, a.boot, a.seed)
    report.update(scale=a.scale, h={'main': a.h_main, 'quiescence': a.h_quiet}, boot=a.boot, seed=a.seed,
                  seconds=round(time.monotonic() - began, 1))
    print(json.dumps(report, indent=1))
    if a.json:
        a.json.write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
