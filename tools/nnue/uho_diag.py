# SPDX-License-Identifier: GPL-3.0-or-later
"""The UHO/SF19 diagnostic benchmark (owner, 2026-11-13 ~4:20 PM EST): how a network judges the positions where
Fork failed to convert its UHO edges against Stockfish 19, measured per candidate net.

**Test data only.** The position sets come from the gauntlet games Fork 117d26a played against Stockfish 19 (GitHub
runs 43492072142, UHO book, and 43492038248, balanced book; the analysis of 2026-11-13). They and Stockfish's
scores in them are another engine's output: a diagnostic reference, never training data, never committed to this
repository (docs/ORIGINALITY.md, "Training data provenance"). This tool reads the sets by path.

The leading explanation it measures (docs/DESIGN.md decisions log, 2026-11-13): a two-sided misjudgment, queens-on
edges underrated and level queenless positions overrated.

The sets (`sets`, deterministic: the seed and the PGNs fix them; manifest.json records counts and SHA-256s). Scores in
the PGN comments are pawns from the mover's view; SF's comment at its move is its search score of the position before
that move. Material counts pawn 1, knight 3, bishop 3, rook 5, queen 9.

- **adv** (UHO games): each opening's book position, once. Every book FEN is played twice, colours reversed; the
  advantaged side is the sign of SF19's first score (White's view) averaged over the two games, and both games must
  agree on that sign. Reference: SF19's first score for the advantaged side in the game where Fork had it (`sf_cp`),
  the two games' mean (`sf_mean_cp`) and Fork 117d26a's own first in-game score there (`game_cp`, raw cp).
- **levelql** (UHO and balanced games): positions before an SF move with |SF score| <= 10 cp, no queen on the board,
  equal material, at least one pawn, the side to move not in check, neither the move before nor SF's move a capture.
  At most 2 per game (seeded), FENs unique, then a seeded sample of at most 300. Values from Fork's side (the colour
  Fork played): SF's score (`sf_cp`) and Fork's in-game score at its next move (`game_cp`).
- **qtrade** (UHO and balanced games): positions with exactly one queen per side where the side to move is ahead by
  +30 to +100 cp on SF's score and a queen trade is available (`avail`): the mover's queen can capture the other
  queen with a legal recapture on that square (`qxq`), or else the mover can offer one, a queen move to a square
  where the other queen can take it and a recapture is legal (`offer`), or else the game's own line from there
  traded queens (`line`). Subset
  `S`: SF to move, SF's own score; subset `F`: Fork to move, minus SF's score at the move before. At most 2 per game
  and subset (seeded), FENs unique, at most 300 per subset. `game_trade`: whether the game's line traded queens.
  A line trades queens when both queens are off the board within its first 3 plies (the mover's move and two
  more); a line of one move that captures the queen with the queen counts when a recapture is legal.

`run` measures one net: the static evaluation on adv and levelql (from the tool's sign convention: adv from the
advantaged side, levelql from Fork's side), from a Fork binary (`fork evalfens`) or, for a net file alone,
tools/nnue/reference.py's integer evaluation (R-int, the engine's static evaluation exactly: tests/nnue parity); with
a binary, a fixed-node search (Threads 1, Hash 16, CalibratedScore off, ucinewgame before each position) on all three
sets, whose score is reported like the static one and whose principal variation decides the trade on qtrade. With
both a net and a binary, the binary's static evaluation must equal the net's R-int on every position (the binary
carries that net). Values are raw cp (pawn units = cp / 100) next to SF19's.

    uho_diag.py sets --uho DIR --bal DIR --out SETDIR [--seed N]
    uho_diag.py run --sets SETDIR [--net NET.fnet] [--bin FORK] [--nodes 100000] [--name NAME] --out OUT.json
    uho_diag.py table OUT.json...          (one line per net; markdown with --md)
"""
import argparse
import hashlib
import json
import random
import re
import statistics as st
import subprocess
import sys
import tempfile
from pathlib import Path

import chess
import chess.pgn

HERE = Path(__file__).resolve().parent
VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
MATE_CP = 10000
SEED = 20261113
LEVEL_WINDOW = 10          # |SF| <= 10 cp: "SF reported 0.00 +- small"
LEVEL_PER_GAME, LEVEL_CAP = 2, 300
TRADE_LO, TRADE_HI = 30, 100   # "slightly ahead" by SF, side to move's view
TRADE_PER_GAME, TRADE_CAP = 2, 300
TRADE_PLIES = 3
SCORE_RE = re.compile(r'^\s*([+-]?)(M?)(\d+(?:\.\d+)?)/(\d+)')
FIELDS = {
    'adv': ['fen', 'side', 'sf_cp', 'sf_mean_cp', 'game_cp', 'source', 'game'],
    'levelql': ['fen', 'side', 'sf_cp', 'game_cp', 'source', 'game', 'ply'],
    'qtrade': ['fen', 'subset', 'sf_cp', 'avail', 'game_trade', 'source', 'game', 'ply'],
}


# ---------- position rules ----------

def comment_cp(comment):
    """A fastchess comment's score in cp, mover's view; None when absent or a mate score."""
    m = SCORE_RE.match(comment or '')
    if not m or m.group(2):
        return None
    return round((-1 if m.group(1) == '-' else 1) * float(m.group(3)) * 100)


def material(board, color):
    return sum(VAL[p.piece_type] for p in board.piece_map().values() if p.color == color and p.piece_type in VAL)


def queens(board, color):
    return len(board.pieces(chess.QUEEN, color))


def line_trades(board, moves, plies=TRADE_PLIES):
    """Whether the line (moves from `board`, one queen per side there) trades queens: both queens off within its first
    `plies` plies, or a one-move line in which the mover's queen takes the other queen and a recapture is legal."""
    if queens(board, chess.WHITE) != 1 or queens(board, chess.BLACK) != 1 or not moves:
        return False
    b = board.copy(stack=False)
    for m in moves[:plies]:
        if m not in b.legal_moves:
            break
        b.push(m)
        if queens(b, chess.WHITE) == 0 and queens(b, chess.BLACK) == 0:
            return True
    if len(moves) == 1:
        return queen_takes_queen(board, moves[0])
    return False


def queen_takes_queen(board, move):
    """The mover's queen captures the other queen with `move`, and the other side can recapture on that square."""
    piece, target = board.piece_at(move.from_square), board.piece_at(move.to_square)
    if not (piece and target and piece.piece_type == chess.QUEEN and target.piece_type == chess.QUEEN
            and piece.color == board.turn and target.color != board.turn and move in board.legal_moves):
        return False
    b = board.copy(stack=False)
    b.push(move)
    return any(r.to_square == move.to_square for r in b.legal_moves)


def queen_offer(board, move):
    """`move` puts the mover's queen where the other queen can take it, and the mover can then recapture."""
    piece = board.piece_at(move.from_square)
    if not piece or piece.piece_type != chess.QUEEN or move not in board.legal_moves:
        return False
    b = board.copy(stack=False)
    b.push(move)
    for r in b.legal_moves:
        if r.to_square == move.to_square and b.piece_at(r.from_square).piece_type == chess.QUEEN:
            b2 = b.copy(stack=False)
            b2.push(r)
            if any(x.to_square == move.to_square for x in b2.legal_moves):
                return True
    return False


def trade_available(board):
    """'qxq', 'offer' or None (one queen per side required)."""
    if queens(board, chess.WHITE) != 1 or queens(board, chess.BLACK) != 1:
        return None
    moves = list(board.legal_moves)
    if any(queen_takes_queen(board, m) for m in moves):
        return 'qxq'
    if any(queen_offer(board, m) for m in moves):
        return 'offer'
    return None


def level_queenless(board, prev_move, move, sf_cp):
    """The levelql rule for the position `board` (SF to move, SF's score sf_cp, its move `move`, the move before
    `prev_move` played from the position before `board`, given as (board_before, move) or None)."""
    if sf_cp is None or abs(sf_cp) > LEVEL_WINDOW:
        return False
    if queens(board, chess.WHITE) or queens(board, chess.BLACK):
        return False
    if material(board, chess.WHITE) != material(board, chess.BLACK) or not board.pieces(chess.PAWN, chess.WHITE) | \
            board.pieces(chess.PAWN, chess.BLACK):
        return False
    if board.is_check() or board.is_capture(move):
        return False
    if prev_move is not None and prev_move[0].is_capture(prev_move[1]):
        return False
    return True


def to_side(stm_cp, board, side):
    """A side-to-move score from `side`'s view (the sign normalisation)."""
    return stm_cp if board.turn == side else -stm_cp


# ---------- sets ----------

def read_games(folder, tag):
    """Every game of every games.pgn under folder, as dicts: the per-ply boards, moves and comment scores."""
    out = []
    for pgn in sorted(Path(folder).glob('*/games.pgn')):
        with open(pgn, encoding='utf-8') as f:
            while True:
                g = chess.pgn.read_game(f)
                if g is None:
                    break
                h = g.headers
                if 'Fork' not in (h['White'], h['Black']):
                    continue
                fork = chess.WHITE if h['White'] == 'Fork' else chess.BLACK
                b = g.board()
                plies = []
                for nd in g.mainline():
                    plies.append({'board': b.copy(stack=False), 'move': nd.move, 'cp': comment_cp(nd.comment),
                                  'fork_moves': b.turn == fork})
                    b.push(nd.move)
                out.append({'source': tag, 'game': f'{tag}/{pgn.parent.name}/{h["Round"]}',
                            'fen': h.get('FEN') or g.board().fen(),
                            'fork': fork, 'plies': plies})
    return out


def first_sf(game):
    for p in game['plies']:
        if not p['fork_moves'] and p['cp'] is not None:
            return p
    return None


def first_fork(game):
    for p in game['plies']:
        if p['fork_moves'] and p['cp'] is not None:
            return p
    return None


def build_adv(uho_games):
    by_fen = {}
    for g in uho_games:
        by_fen.setdefault(g['fen'], []).append(g)
    rows, skipped = [], []
    for fen, gs in by_fen.items():
        if len(gs) != 2:
            skipped.append((fen, f'{len(gs)} games'))
            continue
        whites = []
        for g in gs:
            p = first_sf(g)
            if p is None:
                break
            whites.append(p['cp'] if p['board'].turn == chess.WHITE else -p['cp'])
        if len(whites) != 2 or whites[0] == 0 or whites[1] == 0 or (whites[0] > 0) != (whites[1] > 0):
            skipped.append((fen, 'no sign agreement'))
            continue
        side = chess.WHITE if whites[0] > 0 else chess.BLACK
        game = next(g for g in gs if g['fork'] == side)
        sf = first_sf(game)
        fk = first_fork(game)
        rows.append({'fen': fen, 'side': 'w' if side == chess.WHITE else 'b',
                     'sf_cp': to_side(sf['cp'], sf['board'], side),
                     'sf_mean_cp': round(sum(w if side == chess.WHITE else -w for w in whites) / 2, 1),
                     'game_cp': to_side(fk['cp'], fk['board'], side) if fk else '',
                     'source': 'uho', 'game': game['game']})
    rows.sort(key=lambda r: r['game'])
    return rows, skipped


def game_rng(seed, kind, game):
    return random.Random(f'{seed}:{kind}:{game}')


def cap(rows, n, seed, kind):
    rows = sorted(rows, key=lambda r: (r['game'], int(r['ply'])))
    if len(rows) > n:
        rows = sorted(random.Random(f'{seed}:{kind}:cap').sample(rows, n), key=lambda r: (r['game'], int(r['ply'])))
    return rows


def build_levelql(games, seed):
    pool, seen = [], set()
    for g in games:
        cands = []
        pl = g['plies']
        for i, p in enumerate(pl):
            if p['fork_moves']:
                continue
            prev = (pl[i - 1]['board'], pl[i - 1]['move']) if i > 0 else None
            if not level_queenless(p['board'], prev, p['move'], p['cp']):
                continue
            nxt = pl[i + 1] if i + 1 < len(pl) else None
            cands.append({'fen': p['board'].fen(), 'side': 'w' if g['fork'] == chess.WHITE else 'b',
                          'sf_cp': to_side(p['cp'], p['board'], g['fork']),
                          'game_cp': to_side(nxt['cp'], nxt['board'], g['fork']) if nxt and nxt['cp'] is not None
                          else '', 'source': g['source'], 'game': g['game'], 'ply': i})
        rng = game_rng(seed, 'levelql', g['game'])
        rng.shuffle(cands)
        taken = 0
        for c in cands:
            if taken == LEVEL_PER_GAME:
                break
            if c['fen'] in seen:
                continue
            seen.add(c['fen'])
            pool.append(c)
            taken += 1
    return cap(pool, LEVEL_CAP, seed, 'levelql')


def build_qtrade(games, seed):
    pools = {'S': [], 'F': []}
    seen = set()
    for g in games:
        pl = g['plies']
        cands = {'S': [], 'F': []}
        for i, p in enumerate(pl):
            b = p['board']
            if queens(b, chess.WHITE) != 1 or queens(b, chess.BLACK) != 1:
                continue
            if p['fork_moves']:
                if i == 0 or pl[i - 1]['cp'] is None:
                    continue
                sub, sf = 'F', -pl[i - 1]['cp']
            else:
                if p['cp'] is None:
                    continue
                sub, sf = 'S', p['cp']
            if not TRADE_LO <= sf <= TRADE_HI:
                continue
            line = [q['move'] for q in pl[i:i + TRADE_PLIES]]
            traded = line_trades(b, line)
            avail = trade_available(b) or ('line' if traded else None)
            if avail is None:
                continue
            cands[sub].append({'fen': b.fen(), 'subset': sub, 'sf_cp': sf, 'avail': avail,
                               'game_trade': int(traded), 'source': g['source'], 'game': g['game'], 'ply': i})
        for sub in ('S', 'F'):
            rng = game_rng(seed, 'qtrade' + sub, g['game'])
            rng.shuffle(cands[sub])
            taken = 0
            for c in cands[sub]:
                if taken == TRADE_PER_GAME:
                    break
                if c['fen'] in seen:
                    continue
                seen.add(c['fen'])
                pools[sub].append(c)
                taken += 1
    return cap(pools['S'], TRADE_CAP, seed, 'qtradeS') + cap(pools['F'], TRADE_CAP, seed, 'qtradeF')


def write_tsv(path, kind, rows):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(FIELDS[kind]) + '\n')
        for r in rows:
            f.write('\t'.join(str(r[k]) for k in FIELDS[kind]) + '\n')


def read_tsv(path):
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    head = lines[0].split('\t')
    return [dict(zip(head, l.split('\t'))) for l in lines[1:] if l]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cmd_sets(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    uho, bal = read_games(a.uho, 'uho'), read_games(a.bal, 'bal')
    adv, skipped = build_adv(uho)
    sets = {'adv': adv, 'levelql': build_levelql(uho + bal, a.seed), 'qtrade': build_qtrade(uho + bal, a.seed)}
    man = {'seed': a.seed, 'games': {'uho': len(uho), 'bal': len(bal)}, 'adv_skipped': len(skipped),
           'rules': {'level_window_cp': LEVEL_WINDOW, 'level_per_game': LEVEL_PER_GAME, 'level_cap': LEVEL_CAP,
                     'trade_band_cp': [TRADE_LO, TRADE_HI], 'trade_per_game': TRADE_PER_GAME,
                     'trade_cap_per_subset': TRADE_CAP, 'trade_plies': TRADE_PLIES},
           'sources': {str(p.relative_to(Path(d).parent)).replace('\\', '/'): sha256(p)
                       for d in (a.uho, a.bal) for p in sorted(Path(d).glob('*/games.pgn'))},
           'sets': {}}
    for kind, rows in sets.items():
        p = out / f'{kind}.tsv'
        write_tsv(p, kind, rows)
        info = {'count': len(rows), 'sha256': sha256(p)}
        if kind == 'qtrade':
            info['subsets'] = {s: sum(r['subset'] == s for r in rows) for s in ('S', 'F')}
            info['avail'] = {s: {k: sum(r['subset'] == s and r['avail'] == k for r in rows)
                                 for k in ('qxq', 'offer', 'line')} for s in ('S', 'F')}
            info['game_trade'] = {s: sum(r['subset'] == s and r['game_trade'] for r in rows) for s in ('S', 'F')}
        if kind == 'levelql':
            info['by_source'] = {s: sum(r['source'] == s for r in rows) for s in ('uho', 'bal')}
        man['sets'][kind] = info
    (out / 'manifest.json').write_text(json.dumps(man, indent=1) + '\n', encoding='utf-8')
    for kind, info in man['sets'].items():
        print(f'{kind}: {info["count"]} positions, sha256 {info["sha256"]}')
    return 0


# ---------- evaluation ----------

def layout_for(net):
    """The tools/nnue/*.json layout whose architecture id is the net header's."""
    sys.path.insert(0, str(HERE))
    import netformat
    arch = netformat.header_fields(Path(net).read_bytes())['architecture']
    for j in sorted(HERE.glob('*.json')):
        try:
            if json.loads(j.read_text()).get('architecture') == arch:
                return j, netformat.header_fields(Path(net).read_bytes())['scale']
        except (ValueError, AttributeError):
            continue
    raise SystemExit(f'uho_diag: no layout in {HERE} for architecture {arch}')


def reference_evals(net, fens):
    lay, _ = layout_for(net)
    with tempfile.TemporaryDirectory() as d:
        epd = Path(d) / 'fens.txt'
        epd.write_text('\n'.join(fens) + '\n', encoding='utf-8')
        out = subprocess.run([sys.executable, '-I', str(HERE / 'reference.py'), 'eval', '--net', str(net), '--epd',
                              str(epd), '--layout', str(lay)], capture_output=True, text=True, check=True).stdout
    vals = [int(l.rsplit('|', 1)[1]) for l in out.splitlines() if '|' in l]
    if len(vals) != len(fens):
        raise SystemExit('uho_diag: reference.py gave a different number of scores')
    return vals


def binary_evals(binary, fens):
    out = subprocess.run([binary, 'evalfens'], input='\n'.join(fens) + '\n', capture_output=True, text=True,
                         check=True).stdout.split()
    if len(out) != len(fens) or 'invalid' in out:
        raise SystemExit('uho_diag: evalfens gave a different number of scores or an invalid FEN')
    return [int(v) for v in out]


class Engine:
    """A Fork UCI process for fixed-node searches."""

    def __init__(self, binary):
        self.p = subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.send('uci')
        self.wait('uciok')
        for name, value in (('Threads', 1), ('Hash', 16), ('CalibratedScore', 'false')):
            self.send(f'setoption name {name} value {value}')
        self.send('isready')
        self.wait('readyok')

    def send(self, line):
        self.p.stdin.write(line + '\n')
        self.p.stdin.flush()

    def wait(self, token):
        lines = []
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise SystemExit('uho_diag: the engine exited')
            lines.append(line.strip())
            if line.split() and line.split()[0] == token:
                return lines

    def search(self, fen, nodes):
        """(score cp from the side to move's view, mate scores as +-MATE_CP, the PV as moves)."""
        self.send('ucinewgame')
        self.send('isready')
        self.wait('readyok')
        self.send(f'position fen {fen}')
        self.send(f'go nodes {nodes}')
        lines = self.wait('bestmove')
        best = lines[-1].split()[1]
        score, pv = None, []
        for line in lines:
            t = line.split()
            if t[:1] != ['info'] or 'score' not in t:
                continue
            i = t.index('score')
            score = int(t[i + 2]) if t[i + 1] == 'cp' else (MATE_CP if int(t[i + 2]) > 0 else -MATE_CP)
            pv = t[t.index('pv') + 1:] if 'pv' in t else []
        if not pv or pv[0] != best:
            pv = [best]
        board = chess.Board(fen)
        moves = []
        for u in pv:
            m = chess.Move.from_uci(u)
            if m not in board.legal_moves:
                break
            moves.append(m)
            board.push(m)
        return score, moves

    def close(self):
        try:
            self.send('quit')
            self.p.wait(timeout=10)
        except Exception:  # noqa: BLE001
            self.p.kill()


def summary(vals):
    v = sorted(vals)
    if not v:
        return {}
    q = st.quantiles(v, n=4) if len(v) > 1 else [v[0]] * 3
    return {'n': len(v), 'median': st.median(v), 'mean': round(st.fmean(v), 1), 'p25': q[0], 'p75': q[2]}


def side_of(row):
    return chess.WHITE if row['side'] == 'w' else chess.BLACK


def oriented(rows, stm_vals):
    """Side-to-move values from each row's own side (adv: the advantaged side; levelql: Fork's)."""
    return [to_side(v, chess.Board(r['fen']), side_of(r)) for r, v in zip(rows, stm_vals)]


def compare(fork_vals, sf_vals):
    d = [f - s for f, s in zip(fork_vals, sf_vals)]
    ratios = [f / s for f, s in zip(fork_vals, sf_vals) if s]
    return {'fork': summary(fork_vals), 'sf': summary(sf_vals), 'fork_minus_sf': summary(d),
            'median_ratio': round(st.median(ratios), 3) if ratios else None,
            'fork_pawns_median': round(st.median(fork_vals) / 100, 2), 'sf_pawns_median': round(st.median(sf_vals) / 100, 2),
            'share_fork_above_25': round(sum(v > 25 for v in fork_vals) / len(fork_vals), 3),
            'share_fork_below_minus25': round(sum(v < -25 for v in fork_vals) / len(fork_vals), 3)}


def cmd_run(a):
    sets = Path(a.sets)
    adv, lev, qt = (read_tsv(sets / f'{k}.tsv') for k in ('adv', 'levelql', 'qtrade'))
    man = json.loads((sets / 'manifest.json').read_text(encoding='utf-8'))
    for k, rows in (('adv', adv), ('levelql', lev), ('qtrade', qt)):
        if sha256(sets / f'{k}.tsv') != man['sets'][k]['sha256']:
            raise SystemExit(f'uho_diag: {k}.tsv does not match manifest.json')
    if not a.net and not a.bin:
        raise SystemExit('uho_diag: give --net, --bin or both')
    fens = [r['fen'] for r in adv + lev]
    res = {'name': a.name or Path(a.net or a.bin).stem, 'net': str(a.net) if a.net else None,
           'net_sha256': sha256(a.net) if a.net else None, 'bin': str(a.bin) if a.bin else None,
           'sets_sha256': {k: man['sets'][k]['sha256'] for k in man['sets']}, 'nodes': a.nodes if a.bin else None}
    if a.net:
        res['net_scale'] = layout_for(a.net)[1]
        ref = reference_evals(a.net, fens)
    if a.bin:
        ver = subprocess.run([a.bin, 'version'], capture_output=True, text=True).stdout
        res['bin_version'] = ' | '.join(l for l in ver.splitlines() if l.split()[:1] in (['Fork'], ['net'], ['arch']))
        stat = binary_evals(a.bin, fens)
        if a.net:
            bad = sum(x != y for x, y in zip(stat, ref))
            if bad:
                raise SystemExit(f'uho_diag: the binary\'s static evaluation differs from {a.net} on {bad} of '
                                 f'{len(fens)} positions: it does not carry that net')
            res['identity'] = f'binary static eval == reference R-int on all {len(fens)} positions'
    else:
        stat = ref
    sa, sl = stat[:len(adv)], stat[len(adv):]
    res['static'] = {'adv': compare(oriented(adv, sa), [int(r['sf_cp']) for r in adv]),
                     'levelql': compare(oriented(lev, sl), [int(r['sf_cp']) for r in lev])}
    if a.bin:
        eng = Engine(a.bin)
        try:
            srch = {}
            for kind, rows in (('adv', adv), ('levelql', lev)):
                vals = [eng.search(r['fen'], a.nodes)[0] for r in rows]
                srch[kind] = compare(oriented(rows, vals), [int(r['sf_cp']) for r in rows])
            per = []
            for r in qt:
                score, pv = eng.search(r['fen'], a.nodes)
                per.append((r, int(line_trades(chess.Board(r['fen']), pv)), score))
        finally:
            eng.close()
        qres = {}
        for sub, ref_name in (('S', 'sf_trade'), ('F', 'fork_game_trade')):
            for scope in ('all', 'qxq'):
                rows = [(r, t, s) for r, t, s in per if r['subset'] == sub and (scope == 'all' or r['avail'] == 'qxq')]
                if not rows:
                    continue
                n = len(rows)
                qres[f'{sub}_{scope}'] = {
                    'n': n, 'net_trade': round(sum(t for _, t, _ in rows) / n, 3),
                    ref_name: round(sum(int(r['game_trade']) for r, _, _ in rows) / n, 3),
                    'agree': round(sum(t == int(r['game_trade']) for r, t, _ in rows) / n, 3),
                    'search_cp_median': st.median(s for _, _, s in rows)}
        srch['qtrade'] = qres
        res['search'] = srch
    Path(a.out).write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    print(line(res))
    return 0


def line(res):
    s = res['static']
    out = (f"{res['name']}: static adv {s['adv']['fork']['median']:+} (SF {s['adv']['sf']['median']:+}, ratio "
           f"{s['adv']['median_ratio']}), levelql {s['levelql']['fork']['median']:+} (SF {s['levelql']['sf']['median']:+})")
    if 'search' in res:
        r = res['search']
        q = r['qtrade']
        out += (f"; search adv {r['adv']['fork']['median']:+} (ratio {r['adv']['median_ratio']}), levelql "
                f"{r['levelql']['fork']['median']:+}; qtrade S {q['S_all']['net_trade']:.2f} vs SF "
                f"{q['S_all']['sf_trade']:.2f} (qxq {q['S_qxq']['net_trade']:.2f} vs {q['S_qxq']['sf_trade']:.2f}), "
                f"F {q['F_all']['net_trade']:.2f} vs Fork-game {q['F_all']['fork_game_trade']:.2f}")
    return out + ' (cp, raw)'


def cmd_table(a):
    rows = [json.loads(Path(p).read_text(encoding='utf-8')) for p in a.files]
    head = ['net', 'adv static', 'ratio', 'adv search', 'ratio', 'levelql static', '>+25', 'levelql search',
            'S trade (SF)', 'S qxq (SF)', 'F trade (game)']
    print('| ' + ' | '.join(head) + ' |')
    print('|' + '---|' * len(head))
    for r in rows:
        s, se = r['static'], r.get('search')
        cells = [r['name'], f"{s['adv']['fork']['median']:+}", f"{s['adv']['median_ratio']}",
                 f"{se['adv']['fork']['median']:+}" if se else '-', f"{se['adv']['median_ratio']}" if se else '-',
                 f"{s['levelql']['fork']['median']:+}", f"{s['levelql']['share_fork_above_25']:.2f}",
                 f"{se['levelql']['fork']['median']:+}" if se else '-']
        if se:
            q = se['qtrade']
            cells += [f"{q['S_all']['net_trade']:.2f} ({q['S_all']['sf_trade']:.2f})",
                      f"{q['S_qxq']['net_trade']:.2f} ({q['S_qxq']['sf_trade']:.2f})",
                      f"{q['F_all']['net_trade']:.2f} ({q['F_all']['fork_game_trade']:.2f})"]
        else:
            cells += ['-'] * 3
        print('| ' + ' | '.join(cells) + ' |')
    if rows:
        s = rows[0]['static']
        print(f"\nSF19 medians: adv {s['adv']['sf']['median']:+} cp ({s['adv']['sf_pawns_median']:+} pawns), "
              f"levelql {s['levelql']['sf']['median']:+} cp. Values are raw cp, from the advantaged side (adv) and "
              f"Fork's side (levelql); trade = share of qtrade positions whose line trades queens.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('sets')
    s.add_argument('--uho', required=True)
    s.add_argument('--bal', required=True)
    s.add_argument('--out', required=True)
    s.add_argument('--seed', type=int, default=SEED)
    r = sub.add_parser('run')
    r.add_argument('--sets', required=True)
    r.add_argument('--net')
    r.add_argument('--bin')
    r.add_argument('--nodes', type=int, default=100000)
    r.add_argument('--name')
    r.add_argument('--out', required=True)
    t = sub.add_parser('table')
    t.add_argument('files', nargs='+')
    a = ap.parse_args(argv)
    return {'sets': cmd_sets, 'run': cmd_run, 'table': cmd_table}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
