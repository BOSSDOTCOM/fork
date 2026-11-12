# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline probes on the default network's frozen first layer (ideas.md 82 and 79; docs/research/
novel-ideas-2026-11-11.md ideas 4 and 1). Needs numpy (not in the repository's venv: run it in a venv of its own),
python-chess, tools/nnue (models.py, contacts.py, netformat.py) and td_labels.py with verify_games.py
(branch research/labels-teacher), given by --nnue and --td.

The net (S512+PP layout, architecture 8: 768 piece rows + pawn links -> 512 per perspective, SCReLU, 8 phase heads)
is read from its file. Each position's hidden values v (the side to move's 512 then the other side's 512, clipped
to [0, QA]) are computed with numpy from tools/nnue/models.py's features, and the head output is
out = sum_i (v_i / QA)^2 u_i + c per bucket, u = w S / QB, c = b S / (QA QB) (Fork's integer formula in floats; its
truncations are left out). `extract` checks the float output against models.r_int, the integer reference, on the
first positions it writes.

`extract`: kept records (the trainer's filter: saved, not in check, the move played no capture or promotion,
|score| <= 20,000) sampled from shards of complete games (a cut-off last game is dropped), with the TD(lambda)
label (td_labels.td_targets, side to move's view) and the game's id; or deep-labelled sites (sites.jsonl with
deep.tsv folders as golds, kept records only, or idea 52's controls). Writes an .npz.

`heads` (idea 82, multi-fidelity heads): refits the 8 heads (the first layer frozen) on one sample at a time by
full-batch Adam on mean (sigmoid(out / S) - label)^2, from the shipped heads, early-stopped on a 10% hold-out;
scores the shipped and every refit head on the gold sets: mean squared error in win probability against each gold
(K = 92, mates as 0 or 1), overall and by material class, with 95% bootstrap intervals of each refit's difference
to the shipped heads (positions resampled).

`narrow` (idea 79, nested-width oracle, accuracy half): a narrow readout on the first 256 columns of each
perspective, fitted per bucket by ridge least squares to the full output (cp) on one sample, scored on a held-out
part and on the gold sets: the distribution of |narrow - full| (the band any "narrow far, full near" gate needs),
the share above 25, 50, 100 and 150 cp, and the narrow readout's own gold error beside the full one's.

    head_probes.py extract records --nnue DIR --td DIR --net NET --shards SHARD... --count N --seed S --lam L
                   --scale S --out OUT.npz [--skip-games FILE] [--workers W]
    head_probes.py extract sites --nnue DIR --td DIR --net NET --sites FILE --golds NAME=DIR... --data DIR --out OUT.npz
    head_probes.py extract controls --nnue DIR --td DIR --net NET --sites FILE --labels FILE --out OUT.npz
    head_probes.py heads --net NET --train NAME=FILE.npz... --gold NAME=FILE.npz... --json OUT
    head_probes.py narrow --net NET --train FILE.npz --gold NAME=FILE.npz... --json OUT
"""
import argparse
import json
import random
import sys
import zlib
from multiprocessing import Pool
from pathlib import Path

import numpy as np

K_GOLD = 92.0
QA, QB = 255, 64
PHASE = {'n': 1, 'b': 1, 'r': 2, 'q': 4}
CLASSES = ('Q-MG', 'Q-EG', 'noQ-MG', 'EG')
G = {}  # per-process state: modules and the net


def material_class(board_field):
    pieces = [c.lower() for c in board_field if c.isalpha()]
    phase = sum(PHASE.get(c, 0) for c in pieces)
    if 'q' in pieces:
        return 'Q-MG' if phase >= 13 else 'Q-EG'
    return 'noQ-MG' if phase >= 10 else 'EG'


def setup(nnue, td, net_path):
    sys.path.insert(0, str(nnue))
    sys.path.insert(0, str(td))
    import chess
    import models
    import netformat
    import td_labels
    import verify_games
    data = Path(net_path).read_bytes()
    head = netformat.header_fields(data)
    name = {v: k for k, v in models.ARCH.items()}[head['architecture']]
    arch = models.arch_from_net(name, data[netformat.HEADER_BYTES:])
    net = models.unpack(arch, data[netformat.HEADER_BYTES:])
    h = arch.hidden
    G.update(chess=chess, models=models, td=td_labels, vg=verify_games, arch=arch, net=net, scale=head['scale'],
             ftw=np.frombuffer(net['ftw'], dtype=np.int16).reshape(-1, h),
             ftb=np.array(net['ftb'][:h], dtype=np.int32))
    return G


def hidden(board):
    """(v as uint8[2H], bucket) for the side to move first."""
    m, arch = G['models'], G['arch']
    stm, ntm, k = m.both_perspectives(arch, board)
    out = []
    for active in (stm, ntm):
        saved = m.saved_features(arch, active)
        pieces = [f for f in saved if f < arch.factor_start]
        extra = [f for f in saved if f >= arch.factor_start]
        acc = G['ftb'] + G['ftw'][pieces].astype(np.int32).sum(0)
        assert acc.min() >= -32768 and acc.max() <= 32767
        if extra:
            acc = acc + G['ftw'][extra].astype(np.int32).sum(0)
        acc = np.clip(acc, -32768, 32767)
        out.append(np.clip(acc, 0, QA).astype(np.uint8))
    return np.concatenate(out), k


def head_params(_net_path=None):
    """Shipped heads as floats: u [8, 2H], c [8], and the net's S."""
    nn = G['net']
    h = G['arch'].hidden
    w = np.array(nn['outw'], dtype=np.float64).reshape(8, 2 * h)
    b = np.array(nn['outb'], dtype=np.float64)
    s = G['scale']
    return w * s / QB, b * s / (QA * QB), s


def outputs(v, k, u, c):
    x = (v.astype(np.float32) / QA) ** 2
    return (x * u[k].astype(np.float32)).sum(1) + c[k]


# ---- extract: records ----

def read_games(path):
    """Complete games of one shard: (head, recs) pairs; a truncated last game is dropped."""
    td = G['td']
    data = Path(path).read_bytes()
    out = []
    try:
        for _s, head, recs, _e in td.split_games(data):
            out.append((head, recs))
    except G['vg'].Bad:
        pass
    return out


def game_records(job):
    """The kept records of one game (by the sampled indices) with their features and TD label."""
    gid, head, recs, wanted, lam, scale = job
    chess, vg, td = G['chess'], G['vg'], G['td']
    board, _ = vg.decode_board(head)
    checks, rows = [], []
    for t, (code, score) in enumerate(recs):
        moves = [m for m in board.legal_moves if vg.code_of(board, m) == code]
        if len(moves) != 1:
            return []
        move = moves[0]
        check = board.is_check()
        checks.append(check)
        kept = (score != td.UNSAVED and abs(score) <= td.KEEP_LIMIT and not check and not board.is_capture(move)
                and move.promotion is None)
        if kept and (wanted is None or t in wanted):
            v, k = hidden(board)
            rows.append((t, v, k, board.turn == chess.WHITE, material_class(board.board_fen())))
        board.push(move)
    labels = td.td_targets([s for _c, s in recs], head[30], lam, scale, skip=checks)
    out = []
    for t, v, k, white, cls in rows:
        lab = labels[t]
        if lab is None:
            continue
        out.append((gid, t, v, k, lab if white else 1 - lab, cls))
    return out


def init_worker(nnue, td, net):
    setup(nnue, td, net)


def extract_records(a):
    setup(a.nnue, a.td, a.net)
    games = []
    for path in a.shards:
        for i, (head, recs) in enumerate(read_games(path)):
            games.append((f'{Path(path).name}#{i}', head, recs))
    skip = set()
    if a.skip_games:
        skip = set(json.loads(Path(a.skip_games).read_text()))
    games = [g for g in games if g[0] not in skip]
    rng = random.Random(a.seed)
    rng.shuffle(games)
    # One kept record per game at most every `stride` plies keeps games from dominating: sample up to `per_game`.
    jobs = []
    for gid, head, recs in games:
        saved = [t for t, (_c, s) in enumerate(recs) if s != G['td'].UNSAVED]
        pick = set(rng.sample(saved, min(len(saved), a.per_game)))
        jobs.append((gid, head, recs, pick, a.lam, a.scale))
    vs, ks, ys, gids, classes = [], [], [], [], []
    with Pool(a.workers, initializer=init_worker, initargs=(a.nnue, a.td, a.net)) as pool:
        for rows in pool.imap(game_records, jobs, chunksize=16):
            for gid, _t, v, k, y, cls in rows:
                vs.append(v)
                ks.append(k)
                ys.append(y)
                gids.append(gid)
                classes.append(cls)
            if len(ys) >= a.count:
                pool.terminate()
                break
    n = min(len(ys), a.count)
    np.savez_compressed(a.out, v=np.stack(vs[:n]), k=np.array(ks[:n], dtype=np.uint8),
                        y=np.array(ys[:n], dtype=np.float32), game=np.array(gids[:n]),
                        cls=np.array(classes[:n]), games_used=len(set(gids[:n])))
    print(json.dumps({'out': str(a.out), 'records': n, 'games': len(set(gids[:n])), 'games_in_shards': len(games)}))
    return 0


# ---- extract: deep-labelled sites ----

def read_tsv(path):
    out = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            f = line.split('\t')
            out[int(f[0])] = (int(f[1]), int(f[2]))
    return out


def gold_p(cp, mate):
    if mate:
        return 1.0 if cp > 0 else 0.0
    return float(1 / (1 + np.exp(-cp / K_GOLD)))


def parity_check(boards, vs, ks, n=40):
    """The float head output against models.r_int on the first n positions: |difference| <= 2 cp."""
    u, c, s = head_params(None)
    worst = 0.0
    for board, v, k in list(zip(boards, vs, ks))[:n]:
        exact = G['models'].r_int(G['arch'], G['net'], s, board)
        approx = float(outputs(v[None, :], np.array([k]), u, c)[0])
        worst = max(worst, abs(exact - approx))
    if worst > 2.5:
        raise SystemExit(f'parity: float head output differs from r_int by {worst:.2f} cp')
    return worst


def extract_sites(a):
    setup(a.nnue, a.td, a.net)
    chess = G['chess']
    golds = dict(g.split('=', 1) for g in a.golds)
    tables = {n: read_tsv(Path(d) / 'deep.tsv') for n, d in golds.items()}
    vs, ks, cls, ids, gp, boards = [], [], [], [], {n: [] for n in golds}, []
    for line in Path(a.sites).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        s = json.loads(line)
        if not s.get('kept') or any(s['id'] not in t for t in tables.values()):
            continue
        board = chess.Board(s['fen'])
        v, k = hidden(board)
        vs.append(v)
        ks.append(k)
        boards.append(board)
        cls.append(material_class(s['fen'].split()[0]))
        ids.append(s['id'])
        for n, t in tables.items():
            gp[n].append(gold_p(*t[s['id']]))
    worst = parity_check(boards, vs, ks)
    np.savez_compressed(a.out, v=np.stack(vs), k=np.array(ks, dtype=np.uint8), cls=np.array(cls),
                        id=np.array(ids), golds=np.array(list(golds)), **{f'gold_{n}': np.array(p) for n, p in gp.items()})
    print(json.dumps({'out': str(a.out), 'positions': len(vs), 'parity_worst_cp': worst}))
    return 0


def extract_controls(a):
    setup(a.nnue, a.td, a.net)
    chess = G['chess']
    labels = read_tsv(a.labels)
    vs, ks, cls, ids, gp, boards = [], [], [], [], [], []
    for line in Path(a.sites).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        s = json.loads(line)
        if s.get('set') != 'control' or s['id'] not in labels:
            continue
        board = chess.Board(s['fen'])
        v, k = hidden(board)
        vs.append(v)
        ks.append(k)
        boards.append(board)
        cls.append(material_class(s['fen'].split()[0]))
        ids.append(s['id'])
        gp.append(gold_p(*labels[s['id']]))
    worst = parity_check(boards, vs, ks)
    np.savez_compressed(a.out, v=np.stack(vs), k=np.array(ks, dtype=np.uint8), cls=np.array(cls), id=np.array(ids),
                        golds=np.array(['ppr3_200k']), gold_ppr3_200k=np.array(gp))
    print(json.dumps({'out': str(a.out), 'positions': len(vs), 'parity_worst_cp': worst}))
    return 0


# ---- heads ----

def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def refit(v, k, y, u0, c0, s, seed, epochs=600, lr=1e-3):
    """Full-batch Adam per bucket on mean (sigmoid(out / s) - y)^2, from (u0, c0); early stop on a 10% hold-out."""
    rng = np.random.default_rng(seed)
    u, c = u0.copy(), c0.copy()
    report = {}
    for b in range(8):
        idx = np.nonzero(k == b)[0]
        if len(idx) < 200:
            report[b] = {'n': int(len(idx)), 'kept_shipped': True}
            continue
        rng.shuffle(idx)
        cut = len(idx) // 10
        hold, train = idx[:cut], idx[cut:]
        xt = (v[train].astype(np.float32) / QA) ** 2
        xh = (v[hold].astype(np.float32) / QA) ** 2
        yt, yh = y[train], y[hold]
        # Adam on (u_b, c_b), in units scaled by s so steps are comparable.
        theta = np.concatenate([u[b], [c[b]]]).astype(np.float64) / s
        m = np.zeros_like(theta)
        q = np.zeros_like(theta)

        def loss(th, x, yy):
            return float(np.mean((sigmoid(x @ th[:-1] + th[-1]) - yy) ** 2))

        best, best_theta, bad = loss(theta, xh, yh), theta.copy(), 0
        start_hold = best
        for e in range(1, epochs + 1):
            p = sigmoid(xt @ theta[:-1] + theta[-1])
            g = 2 * (p - yt) * p * (1 - p) / len(yt)
            grad = np.concatenate([xt.T @ g, [g.sum()]])
            m = 0.9 * m + 0.1 * grad
            q = 0.999 * q + 0.001 * grad ** 2
            theta -= lr * (m / (1 - 0.9 ** e)) / (np.sqrt(q / (1 - 0.999 ** e)) + 1e-12)
            if e % 10 == 0:
                h = loss(theta, xh, yh)
                if h < best - 1e-9:
                    best, best_theta, bad = h, theta.copy(), 0
                else:
                    bad += 1
                    if bad >= 5:
                        break
        u[b], c[b] = best_theta[:-1] * s, best_theta[-1] * s
        report[b] = {'n': int(len(idx)), 'hold_loss_start': start_hold, 'hold_loss_end': best, 'epochs': e}
    return u, c, report


def score_gold(gold, u, c):
    out = outputs(gold['v'], gold['k'].astype(np.int64), u, c)
    return 1 / (1 + np.exp(-out / K_GOLD))


def gold_sets(specs):
    sets = {}
    for spec in specs:
        name, path = spec.split('=', 1)
        z = np.load(path, allow_pickle=False)
        for g in z['golds']:
            sets[f'{name}:{g}'] = {'v': z['v'], 'k': z['k'], 'cls': z['cls'], 'gold': z[f'gold_{g}']}
    return sets


def boot_diff(err_a, err_b, rounds=2000, seed=20261111):
    rng = np.random.default_rng(seed)
    n = len(err_a)
    d = err_a - err_b
    reps = np.array([d[rng.integers(0, n, n)].mean() for _ in range(rounds)])
    return [float(np.percentile(reps, 2.5)), float(np.percentile(reps, 97.5))]


def cmd_heads(a):
    setup(a.nnue, a.td, a.net)
    u0, c0, s = head_params(a.net)
    golds = gold_sets(a.gold)
    heads = {'shipped': (u0, c0)}
    out = {'scale': s, 'train': {}, 'gold': {}}
    for spec in a.train:
        name, path = spec.split('=', 1)
        half = None
        if path[-2:] in (':0', ':1'):  # one half of the file's games (crc32 of the game id), a disjoint seed
            path, half = path[:-2], int(path[-1])
        z = np.load(path, allow_pickle=False)
        sel = np.arange(len(z['y']))
        if half is not None:
            sel = np.array([i for i, g in enumerate(z['game']) if zlib.crc32(str(g).encode()) % 2 == half])
        u, c, rep = refit(z['v'][sel], z['k'][sel].astype(np.int64), z['y'][sel].astype(np.float32), u0, c0, s,
                          seed=len(heads))
        heads[name] = (u, c)
        out['train'][name] = {'records': int(len(sel)), 'file': Path(path).name, 'half': half, 'buckets': rep}
    for gname, g in golds.items():
        block = {'n': int(len(g['gold']))}
        errs = {h: (score_gold(g, *uc) - g['gold']) ** 2 for h, uc in heads.items()}
        for h, e in errs.items():
            block[h] = {'mse': float(e.mean())}
            if h != 'shipped':
                block[h]['minus_shipped'] = float(e.mean() - errs['shipped'].mean())
                block[h]['minus_shipped_ci95'] = boot_diff(e, errs['shipped'])
            block[h]['by_class'] = {c: float(e[g['cls'] == c].mean()) for c in CLASSES if (g['cls'] == c).any()}
        block['class_n'] = {c: int((g['cls'] == c).sum()) for c in CLASSES}
        out['gold'][gname] = block
    Path(a.json).write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({g: {h: round(v[h]['mse'], 6) for h in heads} for g, v in out['gold'].items()}, indent=1))
    return 0


def cmd_narrow(a):
    setup(a.nnue, a.td, a.net)
    u0, c0, s = head_params(a.net)
    h = G['arch'].hidden
    cols = np.r_[0:h // 2, h:h + h // 2]
    z = np.load(a.train, allow_pickle=False)
    v, k = z['v'], z['k'].astype(np.int64)
    full = outputs(v, k, u0, c0)
    rng = np.random.default_rng(20261111)
    order = rng.permutation(len(full))
    cut = len(order) // 5
    test, train = order[:cut], order[cut:]
    un = np.zeros((8, len(cols)))
    cn = np.zeros(8)
    for b in range(8):
        idx = train[k[train] == b]
        if len(idx) < 50:
            continue
        x = (v[idx][:, cols].astype(np.float64) / QA) ** 2
        x1 = np.hstack([x, np.ones((len(idx), 1))])
        reg = 1e-3 * np.eye(x1.shape[1])
        sol = np.linalg.solve(x1.T @ x1 + reg * len(idx), x1.T @ full[idx].astype(np.float64))
        un[b], cn[b] = sol[:-1], sol[-1]

    def narrow_out(vv, kk):
        x = (vv[:, cols].astype(np.float32) / QA) ** 2
        return (x * un[kk].astype(np.float32)).sum(1) + cn[kk]

    def dist(diff):
        ad = np.abs(diff)
        return {'mean': float(ad.mean()), 'p50': float(np.percentile(ad, 50)), 'p90': float(np.percentile(ad, 90)),
                'p95': float(np.percentile(ad, 95)), 'p99': float(np.percentile(ad, 99)),
                'share_over': {str(t): float((ad > t).mean()) for t in (25, 50, 100, 150)}}

    out = {'columns': '0-255 of each perspective', 'train_positions': int(len(train)),
           'test_positions': int(len(test))}
    nt = narrow_out(v[test], k[test])
    out['test'] = dist(nt - full[test])
    out['test_by_bucket'] = {str(b): dist(nt[k[test] == b] - full[test][k[test] == b])
                             for b in range(8) if (k[test] == b).sum() > 50}
    # Near the decision: the full output within 100 cp of zero (a stand-in for a window around an even score).
    near = np.abs(full[test]) < 100
    out['test_full_within_100cp_of_0'] = dist((nt - full[test])[near]) if near.any() else None
    out['gold'] = {}
    for gname, g in gold_sets(a.gold).items():
        f = outputs(g['v'], g['k'].astype(np.int64), u0, c0)
        n = narrow_out(g['v'], g['k'].astype(np.int64))
        pf = 1 / (1 + np.exp(-f / K_GOLD))
        pn = 1 / (1 + np.exp(-n / K_GOLD))
        out['gold'][gname] = {'n': int(len(f)), 'narrow_minus_full': dist(n - f),
                              'mse_full': float(((pf - g['gold']) ** 2).mean()),
                              'mse_narrow': float(((pn - g['gold']) ** 2).mean())}
    if a.export_inc:
        # The readout in the net file's integer form (as the output layer: y = sum v^2 w / QA + b, cp = y S / (QA QB)),
        # side to move's 256 columns first, then the other side's.
        wn = np.rint(un * QB / s).astype(np.int64)
        bn = np.rint(cn * QA * QB / s).astype(np.int64)
        assert wn.min() >= -32768 and wn.max() <= 32767 and abs(bn).max() < 2 ** 31
        rows = ',\n'.join('  {' + ', '.join(str(int(x)) for x in wn[b]) + '}' for b in range(8))
        Path(a.export_inc).write_text(
            '// SPDX-License-Identifier: GPL-3.0-or-later\n'
            "// Generated by tools/measure/head_probes.py narrow (idea 79's fixed-node oracle; not hand-edited): a\n"
            '// readout on the first 256 hidden columns of each perspective of nets/r8brft1.fnet, fitted per\n'
            '// bucket by ridge least squares to the full output (cp) on 320,000 positions of the label-depth arm\n'
            '// D20. Valid with r8brft1 only (scale 88).\n'
            f'inline constexpr std::int16_t NarrowReadoutWeights[8][{len(cols)}] = {{\n' + rows + '};\n'
            'inline constexpr std::int32_t NarrowReadoutBias[8] = {' + ', '.join(str(int(x)) for x in bn) + '};\n',
            encoding='utf-8')
        out['export'] = {'file': Path(a.export_inc).name, 'w_min': int(wn.min()), 'w_max': int(wn.max()),
                         'bias': [int(x) for x in bn]}
        # The integer readout as the engine computes it, on the first parity positions (for the engine's test).
        if a.parity_from:
            chess = G['chess']
            lines = [x for x in Path(a.parity_from).read_text(encoding='utf-8').splitlines()[1:] if '|' in x]
            vals = []
            for line in lines[:a.parity_count]:
                fen = line.rsplit('|', 1)[0].strip()
                v, k = hidden(chess.Board(fen))
                vv = v[cols].astype(np.int64)
                y = int((vv * vv * wn[k]).sum())
                y = (abs(y) // QA) * (1 if y >= 0 else -1) + int(bn[k])
                cp = (abs(y * s) // (QA * QB)) * (1 if y * s >= 0 else -1)
                vals.append({'fen': fen, 'narrow': int(max(-19999, min(19999, cp)))})
            out['export']['parity'] = vals
    Path(a.json).write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(out['test'], indent=1))
    return 0


def cmd_writenet(a):
    """Refits the heads on one training spec (as `heads` does, same seed rule) and writes a net file: the base net's
    payload with the quantized heads (w = round(u QB / S), b = round(c QA QB / S)), a parity file (R-int, models.r_int)
    on the base net's parity positions, and the gold errors of the written net's heads."""
    setup(a.nnue, a.td, a.net)
    import netformat
    u0, c0, s = head_params()
    name, path = a.train.split('=', 1)
    half = None
    if path[-2:] in (':0', ':1'):
        path, half = path[:-2], int(path[-1])
    z = np.load(path, allow_pickle=False)
    sel = np.arange(len(z['y']))
    if half is not None:
        sel = np.array([i for i, g in enumerate(z['game']) if zlib.crc32(str(g).encode()) % 2 == half])
    u, c, rep = refit(z['v'][sel], z['k'][sel].astype(np.int64), z['y'][sel].astype(np.float32), u0, c0, s,
                      seed=a.seed)
    w_int = np.rint(u * QB / s).astype(np.int64)
    b_int = np.rint(c * QA * QB / s).astype(np.int64)
    # The loader's bounds (src/eval/nnue/net_file.cpp): each output weight within 32767 / QA = 128 (the squared
    # output's int16 product), and QA^2 sum |w| per bucket within int32.
    limit = 32767 // QA
    clipped = int((np.abs(w_int) > limit).sum())
    w_int = np.clip(w_int, -limit, limit)
    assert (QA * QA * np.abs(w_int).sum(1)).max() < 2 ** 31 and abs(b_int).max() < 2 ** 31
    data = Path(a.net).read_bytes()
    head = netformat.header_fields(data)
    payload = bytearray(data[netformat.HEADER_BYTES:])
    h, n = G['arch'].hidden, G['arch'].saved_inputs
    at = 128 + 2 * n * h + 2 * h  # the map block, feature weights, feature biases (models.unpack's layout)
    old_w = np.frombuffer(bytes(payload[at:at + 2 * 16 * h]), dtype='<i2')
    assert np.array_equal(old_w, np.array(G['net']['outw'], dtype=np.int16)), 'output weights not where expected'
    payload[at:at + 2 * 16 * h] = w_int.astype('<i2').tobytes()
    payload[at + 2 * 16 * h:at + 2 * 16 * h + 4 * 8] = b_int.astype('<i4').tobytes()
    out = netformat.write_net2(head['architecture'], head['inputs'], head['hidden'], head['buckets'], head['scale'],
                               bytes(payload))
    Path(a.out).write_bytes(out)
    # Re-read the written net and evaluate it exactly.
    setup(a.nnue, a.td, a.out)
    uq, cq, _ = head_params()
    chess = G['chess']
    lines = [x for x in Path(a.parity_from).read_text(encoding='utf-8').splitlines()[1:] if '|' in x]
    worst = 0.0
    rows = []
    for line in lines:
        fen = line.rsplit('|', 1)[0].strip()
        board = chess.Board(fen)
        exact = G['models'].r_int(G['arch'], G['net'], s, board)
        v, k = hidden(board)
        worst = max(worst, abs(exact - float(outputs(v[None, :], np.array([k]), uq, cq)[0])))
        rows.append(f'{fen} | {exact}')
    meta = {'net_checksum': f"{netformat.net_checksum(bytes(payload)):016x}", 'scale': s, 'positions': len(rows),
            'source': 'R-int only (tools/nnue/models.py r_int); heads refitted by tools/measure/head_probes.py'}
    Path(a.parity_out).write_text(json.dumps(meta) + '\n' + '\n'.join(rows) + '\n', encoding='utf-8')
    report = {'net': a.out, 'train': a.train, 'seed': a.seed, 'records': int(len(sel)), 'buckets': rep,
              'weights_clipped_to_128': clipped,
              'float_vs_rint_worst_cp': worst, 'gold': {}}
    for gname, g in gold_sets(a.gold).items():
        e_ship = (score_gold(g, u0, c0) - g['gold']) ** 2
        e_new = (score_gold(g, uq, cq) - g['gold']) ** 2
        report['gold'][gname] = {'shipped': float(e_ship.mean()), 'written': float(e_new.mean()),
                                 'minus_shipped_ci95': boot_diff(e_new, e_ship)}
    Path(a.json).write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'buckets'}, indent=1))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    ex = sub.add_parser('extract')
    exs = ex.add_subparsers(dest='what', required=True)
    for name in ('records', 'sites', 'controls'):
        s = exs.add_parser(name)
        s.add_argument('--nnue', required=True, type=Path)
        s.add_argument('--td', required=True, type=Path)
        s.add_argument('--net', required=True)
        s.add_argument('--out', required=True)
    r = exs.choices['records']
    r.add_argument('--shards', nargs='+', required=True)
    r.add_argument('--count', type=int, required=True)
    r.add_argument('--seed', type=int, required=True)
    r.add_argument('--lam', type=float, default=0.9)
    r.add_argument('--scale', type=float, required=True)
    r.add_argument('--per-game', type=int, default=8)
    r.add_argument('--skip-games')
    r.add_argument('--workers', type=int, default=8)
    s = exs.choices['sites']
    s.add_argument('--sites', required=True)
    s.add_argument('--golds', nargs='+', required=True)
    s = exs.choices['controls']
    s.add_argument('--sites', required=True)
    s.add_argument('--labels', required=True)
    for name in ('heads', 'narrow'):
        s = sub.add_parser(name)
        s.add_argument('--nnue', required=True, type=Path)
        s.add_argument('--td', required=True, type=Path)
        s.add_argument('--net', required=True)
        s.add_argument('--gold', nargs='+', required=True)
        s.add_argument('--json', required=True)
    sub.choices['heads'].add_argument('--train', nargs='+', required=True)
    s = sub.add_parser('writenet')
    s.add_argument('--nnue', required=True, type=Path)
    s.add_argument('--td', required=True, type=Path)
    s.add_argument('--net', required=True)
    s.add_argument('--gold', nargs='+', required=True)
    s.add_argument('--json', required=True)
    s.add_argument('--train', required=True)
    s.add_argument('--seed', type=int, required=True)
    s.add_argument('--out', required=True)
    s.add_argument('--parity-from', required=True)
    s.add_argument('--parity-out', required=True)
    sub.choices['narrow'].add_argument('--train', required=True)
    sub.choices['narrow'].add_argument('--export-inc')
    sub.choices['narrow'].add_argument('--parity-from')
    sub.choices['narrow'].add_argument('--parity-count', type=int, default=12)
    a = p.parse_args(argv)
    if a.cmd == 'extract':
        return {'records': extract_records, 'sites': extract_sites, 'controls': extract_controls}[a.what](a)
    return {'heads': cmd_heads, 'narrow': cmd_narrow, 'writenet': cmd_writenet}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
