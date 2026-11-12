# SPDX-License-Identifier: GPL-3.0-or-later
"""The held-out 8-12-piece check (owner, 2026-11-11, after the bug review's T1): positions beyond the tablebases,
from a source that is not Fork's training data, scored against labels from a deep search, to see whether the
held-out endgame drift (tools/nnue/endgame_heldout.py: S512ppr2 454, S512ppr3 514, r8btd90 526, r8brft1 612 of
3,800) reaches positions the tables do not cover.

**Positions** (`positions`): human games from the Lichess open database (lichess_db_standard_rated_2016-09.pgn.zst,
CC0, the file tools/datagen/datagen_openings.py read for Fork's 2016-09 opening book; its SHA-256 is checked). Why
this source: Fork's training positions are its own self-play from 8-16-ply openings, so a human game's
8-12-piece positions come from a different process (a human middle game and ending), while the gauntlet's anchor
games would bring positions shaped by Fork's own play and by engines'. Games: rated, no BOT title, both ratings
at least MIN_RATING (the opening book's filter), each accepted with probability ACCEPT (seeded) so the set spreads
over the month. From each accepted game at most one position: the positions with 8 to 12 pieces that are quiet
(not in check, no capture available, game not over: endgame_check.py's rule) are grouped by piece count, a
count still short of PER_COUNT is drawn at random among those the game has, then a ply at random. No (board,
side to move) twice. Only the game moves are read (comments and any [%eval] never), and only the game's URL is
kept.

**Overlap** (`overlap`): an exact board-and-side match (endgame_heldout.key) against Fork's game files (the
viriformat .vf shards: the g4 and label-depth data on this machine), each game replayed from its header with the
format's move codes (tools/datagen/verify_games.py: code_of), so every recorded position is compared. The
endgame slice cannot hold any of these (it has at most 5 pieces).

**Labels** (`label`, declared 2026-11-11 before any label was computed): Fork's own search on each position, the
current default's engine (the network r8brft1, bench 10,166,167 / d874b380155a2e8c), `go nodes 10,000,000` (NODES),
Threads 1, Hash 64 MB, the Syzygy 3-4-5 tables, a fresh game (ucinewgame) per position, below-normal priority;
the label is the final score from the side to move (centipawns, or a mate). **The circularity**: the label is
Fork's search over r8brft1's own evaluation, so the check scores every net against what r8brft1 searches to;
r8brft1 is favoured, and a net that agrees with r8brft1's search is not thereby right.

**Scoring** (`check`, declared with the labels): each net's static evaluation (R-int, tools/nnue/models.py, at the
net's own scale) against the label, the label classed as winning (at least +200 cp, or a mate for the side to
move), losing (at most -200 cp, or a mate against it) or level (within +-50 cp), other labels unclassed; misjudged
as in endgame_check.py: a winning position below +100 cp, a losing one above -100 cp, a level one beyond +-200 cp.
Also the mean absolute difference with both values clamped to +-1000 cp, over every position.

    heldout_deep.py positions PGN.zst --sha256 HEX --out FILE.tsv [--per-count 300] [--seed 20261111]
    heldout_deep.py overlap FILE.tsv SHARD.vf... [--json OUT]
    heldout_deep.py label FILE.tsv --engine FORK --syzygy DIR --out PART.tsv [--part K --parts N] [--nodes N]
    heldout_deep.py merge FILE.tsv PART.tsv... --out LABELLED.tsv
    heldout_deep.py check LABELLED.tsv NET[=LAYOUT]... [--json OUT]   (LAYOUT defaults to tools/nnue/s512pp.json)
"""
import argparse
import hashlib
import io
import json
import random
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chess  # noqa: E402
import chess.pgn  # noqa: E402

import endgame_check  # noqa: E402
import endgame_heldout as eh  # noqa: E402

SEED = 20261111
PIECES = range(8, 13)
PER_COUNT = 300
MIN_RATING = 2000
ACCEPT = 0.2
NODES = 10_000_000
HASH_MB = 64
WIN, LEVEL, CLAMP = 200, 50, 1000
HEADER = '# pieces\tgame\tply\tfen\tlabel\tdepth\tnodes  -- tools/nnue/heldout_deep.py'


# ---------------------------------------------------------------------------------------------------- positions
def games(stream):
    """(headers dict, PGN text) of each game in a PGN text stream, split at blank-line-separated header blocks."""
    head, body, lines = {}, [], []
    state = 'head'
    for line in stream:
        if line.startswith('['):
            if state == 'body' and lines:
                yield head, ''.join(lines)
                head, lines = {}, []
            state = 'head'
            m = re.match(r'\[(\w+) "(.*)"\]', line)
            if m:
                head[m.group(1)] = m.group(2)
            lines.append(line)
        else:
            if line.strip():
                state = 'body'
            lines.append(line)
    if lines:
        yield head, ''.join(lines)


def eligible(h, min_rating=MIN_RATING):
    try:
        ratings = int(h.get('WhiteElo', 0)), int(h.get('BlackElo', 0))
    except ValueError:
        return False
    return ('Rated' in h.get('Event', '') and 'BOT' not in (h.get('WhiteTitle'), h.get('BlackTitle'))
            and min(ratings) >= min_rating and h.get('Variant', 'Standard') == 'Standard')


def quiet(b):
    return not b.is_check() and not any(b.is_capture(m) for m in b.legal_moves) and not b.is_game_over()


def pick(game_text, rng, need, seen):
    """(pieces, ply, board) of one quiet 8-12-piece position of the game, from a piece count still in `need`."""
    game = chess.pgn.read_game(io.StringIO(game_text))
    if game is None or game.errors:
        return None
    b = game.board()
    by = {}
    for ply, move in enumerate(game.mainline_moves(), 1):
        b.push(move)
        n = chess.popcount(b.occupied)
        if n < min(PIECES):
            break
        if n in need and quiet(b):
            by.setdefault(n, []).append((ply, b.copy(stack=False)))
    counts = sorted(by)
    if not counts:
        return None
    n = rng.choice(counts)
    ply, board = rng.choice(by[n])
    if eh.key(board) in seen:
        return None
    return n, ply, board


def collect(text_stream, per_count=PER_COUNT, seed=SEED, min_rating=MIN_RATING, accept=ACCEPT):
    rng = random.Random(seed)
    have, rows, seen, stats = Counter(), [], set(), Counter()
    for h, text in games(text_stream):
        stats['games'] += 1
        if not eligible(h, min_rating):
            continue
        stats['eligible'] += 1
        if rng.random() >= accept:
            continue
        stats['accepted'] += 1
        need = {n for n in PIECES if have[n] < per_count}
        if not need:
            break
        got = pick(text, rng, need, seen)
        if got is None:
            continue
        n, ply, board = got
        seen.add(eh.key(board))
        have[n] += 1
        rows.append({'pieces': n, 'game': h.get('Site', '?'), 'ply': ply, 'fen': board.fen(), 'label': '',
                     'depth': '', 'nodes': ''})
    stats['positions'] = len(rows)
    return rows, dict(stats)


def write(rows, path):
    lines = [HEADER] + ['\t'.join(str(r[k]) for k in ('pieces', 'game', 'ply', 'fen', 'label', 'depth', 'nodes'))
                        for r in rows]
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


def read(path):
    rows = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#'):
            p, g, ply, fen, label, depth, nodes = line.split('\t')
            rows.append({'pieces': int(p), 'game': g, 'ply': int(ply), 'fen': fen, 'label': label, 'depth': depth,
                         'nodes': nodes})
    return rows


# ------------------------------------------------------------------------------------------------------ overlap
def scan(path, occs, keys):
    """Every position of a viriformat game file (each game replayed from its header by its move codes) with 8-12
    pieces matched against `keys` (endgame_heldout.key); `occs` is their set of occupancies, a fast pre-filter.
    Returns (keys found, games, positions). A truncated last game (a file still being written) is ignored."""
    data = Path(path).read_bytes()
    found, ngames, npos, i, end = set(), 0, 0, 0, len(data)
    lo, hi = min(PIECES), max(PIECES)
    while i + 32 <= end:
        h = data[i:i + 32]
        occ = int.from_bytes(h[0:8], 'little')
        arr = [-1] * 64
        k, o = 0, occ
        while o:
            sq = (o & -o).bit_length() - 1
            o &= o - 1
            code = h[8 + k // 2] >> (4 * (k % 2)) & 15
            k += 1
            if code & 7 == 6:
                code = (code & 8) | 3  # a rook with its castling right is a rook
            arr[sq] = code
        black = bool(h[24] & 128)
        j = i + 32
        moves = []
        while j + 4 <= end:
            code = data[j] | data[j + 1] << 8
            j += 4
            if code == 0:
                break
            moves.append(code)
        else:
            break  # no terminator: a truncated game
        ngames += 1
        npos += len(moves) + 1
        for step in range(len(moves) + 1):
            n = bin(occ).count('1')
            if lo <= n <= hi and occ in occs:
                nib = [arr[sq] for sq in range(64) if occ >> sq & 1]
                packed = bytearray(16)
                for t, v in enumerate(nib):
                    packed[t // 2] |= v << (4 * (t % 2))
                key = (occ.to_bytes(8, 'little') + bytes(packed), black)
                if key in keys:
                    found.add(key)
            if step == len(moves):
                break
            code = moves[step]
            frm, to, promo, kind = code & 63, code >> 6 & 63, code >> 12 & 3, code >> 14
            piece = arr[frm]
            arr[frm] = -1
            occ &= ~(1 << frm)
            if kind == 2:  # castling: the king's move to its own rook's square
                rook = arr[to]
                arr[to] = -1
                occ &= ~(1 << to)
                base = frm & 56
                kd, rd = (base + 6, base + 5) if (to & 7) > (frm & 7) else (base + 2, base + 3)
                arr[kd], arr[rd] = piece, rook
                occ |= 1 << kd | 1 << rd
            else:
                if kind == 1:
                    cap = (frm & 56) | (to & 7)
                    arr[cap] = -1
                    occ &= ~(1 << cap)
                elif kind == 3:
                    piece = (piece & 8) | (promo + 1)
                arr[to] = piece
                occ |= 1 << to
            black = not black
        i = j
    return found, ngames, npos


def overlap(rows, paths):
    boards = [chess.Board(r['fen']) for r in rows]
    keys = {eh.key(b) for b in boards}
    occs = {int(b.occupied) for b in boards}
    found, report = set(), {'files': []}
    for path in paths:
        f, ng, npos = scan(path, occs, keys)
        found |= f
        report['files'].append({'file': str(path), 'games': ng, 'positions': npos, 'matches': len(f)})
        print(f'{path}: {ng} games, {npos} positions, {len(f)} matches', flush=True)
    report['positions'] = len(keys)
    report['found'] = len(found)
    report['games'] = sum(x['games'] for x in report['files'])
    report['positions_scanned'] = sum(x['positions'] for x in report['files'])
    return report, found


# -------------------------------------------------------------------------------------------------------- labels
def label(rows, engine, syzygy, out, part=0, parts=1, nodes=NODES, hash_mb=HASH_MB):
    """Fork's search on each of this part's positions (every parts-th row from part), appended to OUT as it goes;
    rows already in OUT are skipped (a restart resumes)."""
    import chess.engine
    done = {r['fen'] for r in read(out)} if Path(out).exists() else set()
    mine = [r for i, r in enumerate(rows) if i % parts == part and r['fen'] not in done]
    if not Path(out).exists():
        Path(out).write_text(HEADER + '\n', encoding='utf-8', newline='\n')
    flags = getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
    eng = chess.engine.SimpleEngine.popen_uci(engine, creationflags=flags) if flags else \
        chess.engine.SimpleEngine.popen_uci(['nice', '-n', '10', engine])
    try:
        eng.configure({'Threads': 1, 'Hash': hash_mb, 'SyzygyPath': syzygy})
        for r in mine:
            b = chess.Board(r['fen'])
            info = eng.analyse(b, chess.engine.Limit(nodes=nodes), game=object())
            s = info['score'].pov(b.turn)
            lab = f'M{s.mate()}' if s.is_mate() else str(s.score())
            with open(out, 'a', encoding='utf-8', newline='\n') as f:
                f.write('\t'.join(str(x) for x in (r['pieces'], r['game'], r['ply'], r['fen'], lab, info.get('depth', ''),
                                                    info.get('nodes', ''))) + '\n')
    finally:
        eng.quit()


def merge(rows, parts):
    got = {}
    for p in parts:
        for r in read(p):
            got[r['fen']] = r
    missing = [r['fen'] for r in rows if r['fen'] not in got]
    return [got[r['fen']] for r in rows if r['fen'] in got], missing


# --------------------------------------------------------------------------------------------------------- check
def label_cp(lab):
    """A label as centipawns from the side to move: a mate as +-(CLAMP + 1000)."""
    if lab.startswith('M'):
        m = int(lab[1:])
        return CLAMP + 1000 if m > 0 else -(CLAMP + 1000)
    return int(lab)


def label_class(lab):
    cp = label_cp(lab)
    return 'winning' if cp >= WIN else 'losing' if cp <= -WIN else 'level' if abs(cp) <= LEVEL else None


def misjudged(kind, cp):
    return endgame_check.misjudged({'winning': 'won', 'losing': 'lost', 'level': 'drawn'}[kind], cp)


def check(rows, nets):
    import models
    import netformat
    out = {}
    for arg in nets:
        path, _, lay = arg.partition('=')
        desc = netformat.layout(lay or str(HERE / 's512pp.json'))
        data = Path(path).read_bytes()
        arch = models.arch_from_net(desc['name'], data[netformat.HEADER_BYTES:])
        net = models.unpack(arch, data[netformat.HEADER_BYTES:])
        scale = netformat.header_fields(data)['scale']
        t, err = {}, []
        for r in rows:
            cp = models.r_int(arch, net, scale, chess.Board(r['fen']))
            lab = label_cp(r['label'])
            err.append(abs(max(-CLAMP, min(CLAMP, cp)) - max(-CLAMP, min(CLAMP, lab))))
            kind = label_class(r['label'])
            if kind:
                cell = t.setdefault((r['pieces'], kind), [0, 0])
                cell[0] += 1
                cell[1] += misjudged(kind, cp)
        out[Path(path).stem] = {'table': t, 'mae': sum(err) / len(err)}
    return out


def print_check(res):
    names = list(res)
    first = res[names[0]]['table']
    print(f'{"pieces":6} {"label":8} {"positions":>9}  ' + '  '.join(f'{n:>14}' for n in names))
    for n in PIECES:
        for kind in ('winning', 'level', 'losing'):
            if (n, kind) in first:
                print(f'{n:<6} {kind:8} {first[(n, kind)][0]:>9}  '
                      + '  '.join(f'{res[m]["table"][(n, kind)][1]:>14}' for m in names))
    for m in names:
        bad = sum(v[1] for v in res[m]['table'].values())
        alln = sum(v[0] for v in res[m]['table'].values())
        print(f'{m}: {bad} of {alln} classed positions misjudged ({100 * bad / alln:.1f}%); mean |static - label| '
              f'(both within +-{CLAMP}) {res[m]["mae"]:.1f} cp')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('positions')
    p.add_argument('pgn')
    p.add_argument('--sha256', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--per-count', type=int, default=PER_COUNT)
    p.add_argument('--seed', type=int, default=SEED)
    o = sub.add_parser('overlap')
    o.add_argument('positions')
    o.add_argument('shards', nargs='+')
    o.add_argument('--json')
    lb = sub.add_parser('label')
    lb.add_argument('positions')
    lb.add_argument('--engine', required=True)
    lb.add_argument('--syzygy', required=True)
    lb.add_argument('--out', required=True)
    lb.add_argument('--part', type=int, default=0)
    lb.add_argument('--parts', type=int, default=1)
    lb.add_argument('--nodes', type=int, default=NODES)
    mg = sub.add_parser('merge')
    mg.add_argument('positions')
    mg.add_argument('parts', nargs='+')
    mg.add_argument('--out', required=True)
    c = sub.add_parser('check')
    c.add_argument('labelled')
    c.add_argument('nets', nargs='+')
    c.add_argument('--json')
    a = ap.parse_args(argv)
    if a.cmd == 'positions':
        import zstandard
        digest = hashlib.sha256()
        with open(a.pgn, 'rb') as f:
            for block in iter(lambda: f.read(1 << 20), b''):
                digest.update(block)
        if digest.hexdigest() != a.sha256:
            sys.exit(f'{a.pgn}: SHA-256 {digest.hexdigest()}, expected {a.sha256}')
        t0 = time.time()
        with open(a.pgn, 'rb') as f:
            text = io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True),
                                    encoding='utf-8', errors='replace')
            rows, stats = collect(text, a.per_count, a.seed)
        write(rows, a.out)
        print(json.dumps({'source': Path(a.pgn).name, 'source_sha256': a.sha256, 'seed': a.seed,
                          'per_count': a.per_count, 'min_rating': MIN_RATING, 'accept': ACCEPT, 'stats': stats,
                          'by_pieces': dict(sorted(Counter(r['pieces'] for r in rows).items())),
                          'seconds': round(time.time() - t0)}))
        return 0
    rows = read(a.positions if a.cmd != 'check' else a.labelled)
    if a.cmd == 'overlap':
        rep, _ = overlap(rows, a.shards)
        print(json.dumps({k: v for k, v in rep.items() if k != 'files'}))
        if a.json:
            Path(a.json).write_text(json.dumps(rep, indent=1) + '\n', encoding='utf-8')
        return 1 if rep['found'] else 0
    if a.cmd == 'label':
        label(rows, a.engine, a.syzygy, a.out, a.part, a.parts, a.nodes)
        return 0
    if a.cmd == 'merge':
        got, missing = merge(rows, a.parts)
        write(got, a.out)
        print(f'{len(got)} labelled, {len(missing)} missing')
        return 1 if missing else 0
    res = check(rows, a.nets)
    print_check(res)
    if a.json:
        Path(a.json).write_text(json.dumps({m: {'mae': v['mae'], 'table': {f'{n} {k}': c for (n, k), c in
                                                                           v['table'].items()}}
                                            for m, v in res.items()}, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
