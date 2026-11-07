# SPDX-License-Identifier: GPL-3.0-or-later
"""Crucial-point ground truth (owner's request, 2026-11-07; DESIGN.md §5.7):
which detector finds the evaluation sites where a better evaluation would
change a decision, per percent of nodes, as the gate for ideas 59 and 60.

1. `sites`: the evaluation sites a stats build sampled during a
   game_replay.py run (`--report counters,sites --sites N,M`: every Nth
   main-search and every Mth quiescence site, computed or reused from the
   TT), each with its FEN, window, static evaluation, depth, ply, the
   parent's evaluation, TT entry and the last move's capture flag; plus each
   stratum's sites per node from the run's counters.
2. `deep`: every site with a finite window bound searched by the default
   engine (a normal build, its bench checked against the reference first),
   one thread, Hash 16, `ucinewgame` before each, to N nodes (1,000,000);
   its last reported score is the site's deep value (side to move's view;
   a mate is written as +-20,000 and flagged). Resumable; engines run at
   below-normal priority.
3. `seeds`: each site's evaluation by other networks, through the
   repository's integer reference (tools/nnue/reference.py, R-int, which
   gives the engine's own values; the warm seed fails the engine's int16
   load check, so every seed goes through R-int alike).
4. `score`: the labels and the detectors.

A site is **crucial** when its static evaluation and its deep value fall on
opposite sides of the nearest finite bound of its window, both from the
side to move at that node: at beta, one is >= beta and the other is not;
at alpha, one is > alpha and the other is not. A site whose bounds are both
in the mate or tablebase band (|bound| >= 29,250) is never crucial.

Detectors (higher score = called first): (a) the window gap (smaller is
higher); (b) seed disagreement, |scratch seed 1 - scratch seed 2| and
|default - warm seed 2|; (c) simple features: the side to move's and the
opponent's hanging pieces (attacked and undefended, or attacked by a
cheaper piece), checking moves available, the last move a capture, the
evaluation's swing from the parent (|eval + parent eval|), the TT
refinement (|refined - static|); (d) a logistic model on the gap, the
disagreements and the features, fitted on the games of one half (a stable
hash of the game id) and scored on the other, both ways. Each detector's
ROC: recall of crucial sites against the call rate per node (the share of
the stratum's sampled sites it calls, times the stratum's sites per node),
separately for main search and quiescence, read at 2, 4, 7 and 10% of
nodes. Measurement settings: DESIGN.md §5.7.

    crucial_points.py sites REPLAY_DIR OUT_DIR
    crucial_points.py deep ENGINE OUT_DIR [--nodes 1000000] [--workers 2]
    crucial_points.py seeds OUT_DIR NAME NET.fnet [--layout tools/nnue/s512pp.json]
    crucial_points.py score OUT_DIR [--json OUT]
"""
import argparse
import json
import math
import queue
import re
import subprocess
import sys
import threading
import zlib
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))

import node_share_fit  # noqa: E402


def read_sites(replay_dir):
    """The sampled sites of a replay (with ids and games) and each stratum's sites per node."""
    sites, counters = [], {}
    for f in sorted(Path(replay_dir).glob('game-*.jsonl')):
        for line in f.read_text(encoding='utf-8').splitlines():
            record = json.loads(line)
            for k, v in record.get('counters', {}).items():
                counters[k] = counters.get(k, 0) + v
            for site in record.get('sites') or []:
                site = dict(site, game=record['game'], search_ply=record['ply'], id=len(sites))
                sites.append(site)
    nodes = counters['root_nodes'] + counters['main_nodes'] + counters['quiesce_nodes_pv'] + \
        counters['quiesce_nodes_non_pv']
    per_node = {'main': (counters['evals_main'] + counters['tt_eval_hits_main']) / nodes,
                'quiescence': (counters['evals_quiesce'] + counters['tt_eval_hits_quiesce']) / nodes}
    return sites, per_node


def nearest_bound(value, alpha, beta):
    """('alpha' or 'beta', bound) of the nearer finite bound, or None."""
    low, high = abs(alpha) < 29250, abs(beta) < 29250
    if not low and not high:
        return None
    if not low:
        return 'beta', beta
    if not high:
        return 'alpha', alpha
    return ('alpha', alpha) if abs(value - alpha) <= abs(value - beta) else ('beta', beta)


def crucial_label(static, deep, alpha, beta):
    """1 if the static and the deep value fall on opposite sides of the nearest
    finite bound (chosen from the static evaluation), 0 if not, None without one."""
    near = nearest_bound(static, alpha, beta)
    if near is None:
        return None
    side, bound = near
    if side == 'beta':
        return int((static >= bound) != (deep >= bound))
    return int((static > bound) != (deep > bound))


def site_features(site):
    """The simple features of one site, from its record and its FEN."""
    board = chess.Board(site['fen'])
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}
    hanging = {chess.WHITE: 0, chess.BLACK: 0}
    for square, piece in board.piece_map().items():
        if piece.piece_type == chess.KING:
            continue
        attackers = board.attackers(not piece.color, square)
        if not attackers:
            continue
        defended = bool(board.attackers(piece.color, square))
        cheapest = min(values[board.piece_type_at(a)] for a in attackers)
        if not defended or cheapest < values[piece.piece_type]:
            hanging[piece.color] += 1
    us = board.turn
    checks = sum(1 for m in board.legal_moves if board.gives_check(m))
    near = nearest_bound(site['eval'], site['alpha'], site['beta'])
    parent = site['parent_eval']
    return {
        'gap': abs(site['eval'] - near[1]) if near else None,
        'hanging_own': hanging[us],
        'hanging_their': hanging[not us],
        'checks_available': checks,
        'last_capture': site['captured'],
        'parent_swing': abs(site['eval'] + parent) if abs(parent) < 30000 else 0,
        'refine_diff': abs(site['prune_eval'] - site['eval']),
        'reused': site['reused'],
        'on_pv': site['on_pv'],
        'depth': site['depth'],
    }


def detector_scores(rows):
    """Each detector's score per row (higher: called first)."""
    out = {
        'window_gap': [-r['gap'] if r['gap'] is not None else -1e9 for r in rows],
        'seed_scratch': [abs(r['seed_scratch_s1'] - r['seed_scratch_s2']) for r in rows],
        'seed_warm': [abs(r['eval'] - r['seed_warm_s2']) for r in rows],
        'hanging': [r['hanging_own'] + r['hanging_their'] for r in rows],
        'checks_available': [r['checks_available'] for r in rows],
        'last_capture': [r['last_capture'] for r in rows],
        'parent_swing': [r['parent_swing'] for r in rows],
        'refine_diff': [r['refine_diff'] for r in rows],
    }
    # Gap against disagreement: how far the seeds disagree beyond the distance to the bound.
    out['seed_minus_gap'] = [(abs(r['seed_scratch_s1'] - r['seed_scratch_s2']) - r['gap']) if r['gap'] is not None
                             else -1e9 for r in rows]
    return out


def roc_points(scores, labels, per_node):
    """[(call rate per node, recall)] calling sites in descending score order
    (ties called together)."""
    total = sum(labels)
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    points, called, caught, i = [(0.0, 0.0)], 0, 0, 0
    while i < len(order):
        j = i
        while j < len(order) and scores[order[j]] == scores[order[i]]:
            called += 1
            caught += labels[order[j]]
            j += 1
        points.append((called / len(scores) * per_node, caught / total if total else 0.0))
        i = j
    return points


def recall_at_rates(points, rates):
    """The recall at each call rate per node, interpolated linearly between ROC points."""
    out = {}
    for rate in rates:
        value = points[-1][1]
        for (r0, c0), (r1, c1) in zip(points, points[1:]):
            if r1 >= rate:
                value = c0 + (c1 - c0) * ((rate - r0) / (r1 - r0)) if r1 > r0 else c1
                break
        out[rate] = value
    return out


def fit_detector(train, names):
    """A logistic model of the label on standardised features: (coefficients, means, scales)."""
    means = [sum(r[n] for r in train) / len(train) for n in names]
    scales = [math.sqrt(sum((r[n] - m) ** 2 for r in train) / len(train)) or 1.0 for n, m in zip(names, means)]
    xs = [[1.0] + [(r[n] - m) / s for n, m, s in zip(names, means, scales)] for r in train]
    beta = node_share_fit.fit_logistic_irls(xs, [r['label'] for r in train], ridge=1e-3)
    return beta, means, scales


def deep_search_sites(engine, todo, out_path, nodes, workers):
    """Searches each (id, fen) to `nodes` nodes; appends 'id<TAB>cp<TAB>mate<TAB>depth' lines."""
    jobs = queue.Queue()
    for item in todo:
        jobs.put(item)
    lock = threading.Lock()
    flags = getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)

    def work():
        p = subprocess.Popen([engine], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
                             creationflags=flags)

        def send(line):
            p.stdin.write(line + '\n')
            p.stdin.flush()

        def read_until(token):
            last = None
            while True:
                line = p.stdout.readline()
                if not line:
                    raise RuntimeError('engine exited')
                if ' score ' in line:
                    last = line
                if line.startswith(token):
                    return last

        send('uci')
        read_until('uciok')
        send('setoption name Hash value 16')
        send('setoption name Threads value 1')
        while True:
            try:
                site_id, fen = jobs.get_nowait()
            except queue.Empty:
                break
            send('ucinewgame')
            send('isready')
            read_until('readyok')
            send(f'position fen {fen}')
            send(f'go nodes {nodes}')
            info = read_until('bestmove')
            cp = re.search(r' score cp (-?\d+)', info or '')
            mate = re.search(r' score mate (-?\d+)', info or '')
            depth = re.search(r' depth (\d+)', info or '')
            value, is_mate = (int(cp.group(1)), 0) if cp else ((20000 if int(mate.group(1)) > 0 else -20000), 1)
            with lock, open(out_path, 'a', encoding='utf-8') as f:
                f.write(f'{site_id}\t{value}\t{is_mate}\t{depth.group(1) if depth else 0}\n')
        send('quit')
        p.wait(timeout=30)

    threads = [threading.Thread(target=work) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def seed_evals(fens, net, layout):
    """Each FEN's R-int evaluation by `net` (tools/nnue/reference.py eval)."""
    reference = Path(__file__).resolve().parents[1] / 'nnue' / 'reference.py'
    with open(Path(net).with_suffix('.fens.tmp'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(fens) + '\n')
    done = subprocess.run([sys.executable, '-I', str(reference), 'eval', '--net', str(net), '--epd',
                           str(Path(net).with_suffix('.fens.tmp')), '--layout', str(layout)],
                          capture_output=True, text=True, check=True)
    Path(net).with_suffix('.fens.tmp').unlink()
    values = [int(line.rsplit('|', 1)[1]) for line in done.stdout.splitlines() if '|' in line]
    if len(values) != len(fens):
        raise RuntimeError(f'{len(values)} evaluations for {len(fens)} positions')
    return values


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('sites')
    p.add_argument('replay', type=Path)
    p.add_argument('out', type=Path)
    p = sub.add_parser('deep')
    p.add_argument('engine')
    p.add_argument('out', type=Path)
    p.add_argument('--nodes', type=int, default=1000000)
    p.add_argument('--workers', type=int, default=2)
    p = sub.add_parser('seeds')
    p.add_argument('out', type=Path)
    p.add_argument('name')
    p.add_argument('net', type=Path)
    p.add_argument('--layout', type=Path, default=Path(__file__).resolve().parents[1] / 'nnue' / 's512pp.json')
    p = sub.add_parser('score')
    p.add_argument('out', type=Path)
    p.add_argument('--json', type=Path, default=None)
    a = parser.parse_args(argv)

    if a.command == 'sites':
        sites, per_node = read_sites(a.replay)
        a.out.mkdir(parents=True, exist_ok=True)
        with open(a.out / 'sites.jsonl', 'w', encoding='utf-8') as f:
            for s in sites:
                f.write(json.dumps(s, separators=(',', ':')) + '\n')
        (a.out / 'per_node.json').write_text(json.dumps(per_node) + '\n', encoding='utf-8')
        finite = sum(1 for s in sites if nearest_bound(s['eval'], s['alpha'], s['beta']))
        kinds = [sum(1 for s in sites if s['kind'] == k) for k in (0, 1)]
        print(f'{len(sites)} sites (main {kinds[0]}, quiescence {kinds[1]}), {finite} with a finite bound; '
              f'sites per node {per_node}')
        return 0

    sites = [json.loads(line) for line in (a.out / 'sites.jsonl').read_text(encoding='utf-8').splitlines()]
    if a.command == 'deep':
        engine = str(Path(a.engine).resolve())
        version = subprocess.run([engine, 'version'], capture_output=True, text=True, check=True).stdout
        bench = subprocess.run([engine, 'bench'], capture_output=True, text=True, check=True).stdout
        net = re.search(r'^net (\S+)', version, re.M)
        ref = (Path(__file__).resolve().parents[2] / 'tests' / f'bench-{net.group(1)}.ref').read_text(encoding='utf-8')
        nodes = re.search(r'nodes (\d+)', bench).group(1)
        signature = re.search(r'signature ([0-9a-f]+)', bench).group(1)
        if f'nodes {nodes}' not in ref or f'signature {signature}' not in ref:
            raise SystemExit(f'bench {nodes} / {signature} does not match the reference')
        path = a.out / 'deep.tsv'
        done = set()
        if path.exists():
            done = {int(line.split('\t')[0]) for line in path.read_text(encoding='utf-8').splitlines() if line}
        todo = [(s['id'], s['fen']) for s in sites
                if s['id'] not in done and nearest_bound(s['eval'], s['alpha'], s['beta'])]
        print(f'{len(todo)} sites to search ({len(done)} done)', flush=True)
        deep_search_sites(engine, todo, path, a.nodes, a.workers)
        return 0

    if a.command == 'seeds':
        values = seed_evals([s['fen'] for s in sites], a.net, a.layout)
        with open(a.out / f'seed-{a.name}.tsv', 'w', encoding='utf-8') as f:
            for s, v in zip(sites, values):
                f.write(f'{s["id"]}\t{v}\n')
        print(f'{len(values)} evaluations by {a.name}')
        return 0

    # score
    per_node = json.loads((a.out / 'per_node.json').read_text(encoding='utf-8'))
    deep = {}
    for line in (a.out / 'deep.tsv').read_text(encoding='utf-8').splitlines():
        site_id, value, mate, _ = line.split('\t')
        deep[int(site_id)] = int(value)
    seeds = {}
    for name in ('scratch_s1', 'scratch_s2', 'warm_s2'):
        seeds[name] = {int(i): int(v) for i, v in (line.split('\t') for line in
                                                   (a.out / f'seed-{name}.tsv').read_text(encoding='utf-8').splitlines())}
    rows = []
    for s in sites:
        label = crucial_label(s['eval'], deep[s['id']], s['alpha'], s['beta']) if s['id'] in deep else None
        if label is None and nearest_bound(s['eval'], s['alpha'], s['beta']):
            continue  # a finite-bound site not yet searched
        row = dict(s, **site_features(s), label=label or 0, deep=deep.get(s['id']),
                   seed_scratch_s1=seeds['scratch_s1'][s['id']], seed_scratch_s2=seeds['scratch_s2'][s['id']],
                   seed_warm_s2=seeds['warm_s2'][s['id']])
        rows.append(row)
    names = ['gap_capped', 'seed_scratch', 'seed_warm', 'hanging_own', 'hanging_their', 'checks_available',
             'last_capture', 'parent_swing', 'refine_diff', 'reused', 'on_pv', 'depth']
    for r in rows:
        r['gap_capped'] = math.log1p(min(r['gap'], 2000)) if r['gap'] is not None else math.log1p(2000)
        r['seed_scratch'] = math.log1p(abs(r['seed_scratch_s1'] - r['seed_scratch_s2']))
        r['seed_warm'] = math.log1p(abs(r['eval'] - r['seed_warm_s2']))
        r['parent_swing'] = math.log1p(min(r['parent_swing'], 2000))
    result = {'per_node': per_node, 'strata': {}}
    rates = (0.02, 0.04, 0.07, 0.10)
    for stratum, kind in (('main', 0), ('quiescence', 1)):
        part = [r for r in rows if r['kind'] == kind]
        labels = [r['label'] for r in part]
        scores = detector_scores(part)
        # (d) logistic models, two folds by game: each half scored by the model fitted on the other.
        for model, used in (('logistic_gap_features', [n for n in names if not n.startswith('seed')]),
                            ('logistic_all', names)):
            fold_scores = [0.0] * len(part)
            for fold in (0, 1):
                train = [r for r in part if zlib.crc32(r['game'].encode()) % 2 != fold]
                if not train or not any(r['label'] for r in train):
                    continue  # nothing to fit on (a tiny run): that half keeps score 0
                beta, means, scales = fit_detector(train, used)
                for i, r in enumerate(part):
                    if zlib.crc32(r['game'].encode()) % 2 == fold:
                        fold_scores[i] = sum(b * v for b, v in zip(beta, [1.0] + [(r[n] - m) / sc for n, m, sc in
                                                                                  zip(used, means, scales)]))
            scores[model] = fold_scores
        block = {'sites': len(part), 'crucial': sum(labels),
                 'crucial_rate': sum(labels) / len(part) if part else 0.0,
                 'sites_per_node': per_node[stratum], 'detectors': {}}
        for name, sc in scores.items():
            points = roc_points(sc, labels, per_node[stratum])
            block['detectors'][name] = {
                'recall_at': {f'{int(r * 100)}%': v for r, v in recall_at_rates(points, rates).items()},
                'auc': node_share_fit.rank_auc(sc, labels)}
        result['strata'][stratum] = block
        print(f'{stratum}: {len(part)} sites, {sum(labels)} crucial ({block["crucial_rate"]:.3%})', flush=True)
        for name, d in sorted(block['detectors'].items(), key=lambda kv: -kv[1]['recall_at']['4%']):
            print(f'  {name:24s} AUC {d["auc"]:.3f} recall at 2/4/7/10% of nodes: ' +
                  ' '.join(f'{v:.3f}' for v in d['recall_at'].values()), flush=True)
    text = json.dumps(result, indent=1)
    if a.json:
        a.json.write_text(text + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
