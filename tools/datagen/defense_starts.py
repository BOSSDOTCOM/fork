# SPDX-License-Identifier: GPL-3.0-or-later

"""Start positions for the positional-advantage and defense-start slices (ideas.md 66; owner,
2026-11-10; docs/research/defense-slices/pilot.md), drawn from Fork's own sealed fork_datagen shards
only, never from gauntlet, SPRT or other engines' games.

Each game of a shard (viriformat, decoded by verify_games.py's reader) is replayed; every recorded
position is classified from its stored score (the search score of the position the move was played in,
White's view, turned to the side to move) and its board:
- both slices: the score is saved (not UNSAVED_SCORE) and |score| <= 20000, the side to move is not in
  check and the recorded move is neither a capture nor a promotion (the trainer's max_eval,
  filter_check and filter_tactical: the score is a label the trainer would read); each side has a queen;
- positional: knights, bishops, rooks and queens equal in number for both sides, pawns level or one
  apart, 80 <= |score| <= 400;
- defense: -300 <= score <= -100 for the side to move.
From each game at most one start per slice is drawn, uniformly among its eligible positions (seeded by
the seed, the shard and the game); the defense draw skips the position the positional draw took. The
per-game starts are then shuffled (seeded), and a position (board, side to move, castling) is kept only
at its first appearance over both slices, and never if it is in `--exclude` (a held-out gold set).

    defense_starts.py select SHARD... --out PREFIX [--seed S] [--exclude TSV...]
        writes PREFIX-positional.tsv, PREFIX-defense.tsv (every drawn start, in draw order) and
        PREFIX-pool.json (eligible positions and games per slice)
    defense_starts.py openings TSV --count N --out FILE       the first N starts as fork_datagen openings
    defense_starts.py played TSV SHARD... --out FILE          each played game's start, first score,
                                                              result (side to move's view) and length
    defense_starts.py gate TSV PLAYED LABELS [--scale 92 --result-weight 0.5]   the offline gate

The gate (pilot.md, check 5): on starts whose gold label (LABELS: label.py's id, cp, ...) is at least
50 cp from 0, the trainer's target t = (1 - w) sigmoid(score / S) + w result, for the standard data
(the shard's own score and result) and for the pilot (its first score and result), is measured as
(t - 0.5) * sign(gold): larger means less compressed toward 0. Pass when the paired bootstrap 95%
interval of pilot minus standard lies above 0.
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_games as vg  # noqa: E402

MAX_SCORE = 20000  # tools/train/src/main.rs MAX_SCORE: the trainer's max_eval
POSITIONAL_BAND = (80, 400)  # |score| for the side to move (owner, 2026-11-10)
DEFENSE_BAND = (-300, -100)  # score for the side to move (owner, 2026-11-10)
GOLD_FLOOR = 50  # cp: gold labels nearer 0 carry no sign (report.md item 4's signed-error floor)
SLICES = ('positional', 'defense')
PIECES = (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
COLUMNS = ('id', 'shard', 'game', 'ply', 'key', 'fen', 'score', 'result', 'phase', 'pawn_diff', 'men')


class Position:
    __slots__ = ('shard', 'game', 'ply', 'board', 'score', 'result', 'tactical', 'saved')

    def __init__(self, shard, game, ply, board, score, result, tactical, saved):
        self.shard, self.game, self.ply, self.board = shard, game, ply, board
        self.score, self.result, self.tactical, self.saved = score, result, tactical, saved


def move_of(code):
    """python-chess move for a format code; castling stays king-to-rook, which push() reads as castling."""
    frm, to, promo, kind = code & 63, (code >> 6) & 63, (code >> 12) & 3, code >> 14
    return chess.Move(frm, to, promotion=promo + chess.KNIGHT if kind == 3 else None)


def games(path):
    """Yields (index, start board, stored result 0/1/2, [(code, white score)]) for each game of a shard."""
    data = Path(path).read_bytes()
    i = index = 0
    while i < len(data):
        board, result = vg.decode_board(data[i:i + 32])
        i += 32
        records = []
        while True:
            code, score = vg.u16(data, i), vg.i16(data, i + 2)
            i += 4
            if code == 0:
                break
            records.append((code, score))
        yield index, board, result, records
        index += 1


def positions(path, keep_boards=True):
    """Every recorded position of a shard as a Position (score and result from the side to move's view)."""
    shard = Path(path).name
    for index, board, result, records in games(path):
        for ply, (code, white) in enumerate(records):
            move = move_of(code)
            stm_white = board.turn == chess.WHITE
            saved = white != vg.UNSAVED_SCORE
            score = (white if stm_white else -white) if saved else None
            res = (result / 2) if stm_white else (1 - result / 2)
            tactical = board.is_capture(move) or move.promotion is not None or board.is_check()
            yield Position(shard, index, ply, board.copy(stack=False) if keep_boards else board, score, res,
                           tactical, saved)
            board.push(move)


def material(board):
    return {(c, pt): chess.popcount(board.pieces_mask(pt, c)) for c in (chess.WHITE, chess.BLACK)
            for pt in (chess.PAWN,) + PIECES}


def slices_of(p):
    """The slices whose rules position p meets."""
    if not p.saved or p.tactical or abs(p.score) > MAX_SCORE:
        return set()
    m = material(p.board)
    if not (m[(chess.WHITE, chess.QUEEN)] and m[(chess.BLACK, chess.QUEEN)]):
        return set()
    out = set()
    equal = all(m[(chess.WHITE, pt)] == m[(chess.BLACK, pt)] for pt in PIECES)
    if equal and abs(m[(chess.WHITE, chess.PAWN)] - m[(chess.BLACK, chess.PAWN)]) <= 1 \
            and POSITIONAL_BAND[0] <= abs(p.score) <= POSITIONAL_BAND[1]:
        out.add('positional')
    if DEFENSE_BAND[0] <= p.score <= DEFENSE_BAND[1]:
        out.add('defense')
    return out


def key_of(board):
    return f'{board.board_fen()} {"w" if board.turn == chess.WHITE else "b"} {board.castling_xfen()}'


def row_of(p):
    m = material(p.board)
    us, them = p.board.turn, not p.board.turn
    phase = sum(w * (m[(chess.WHITE, pt)] + m[(chess.BLACK, pt)])
                for pt, w in ((chess.KNIGHT, 1), (chess.BISHOP, 1), (chess.ROOK, 2), (chess.QUEEN, 4)))
    return {'id': f'{p.shard}:{p.game}:{p.ply}', 'shard': p.shard, 'game': p.game, 'ply': p.ply,
            'key': key_of(p.board), 'fen': p.board.fen(en_passant='legal'), 'score': p.score, 'result': p.result,
            'phase': phase, 'pawn_diff': m[(us, chess.PAWN)] - m[(them, chess.PAWN)],
            'men': chess.popcount(p.board.occupied)}


def select(paths, seed, exclude=()):
    """Draws the starts; returns {'rows': {slice: [row]}, 'pool': {slice: {'positions', 'games'}}}."""
    exclude = set(exclude)
    pool = {s: {'positions': 0, 'games': 0} for s in SLICES}
    drawn = {s: [] for s in SLICES}
    for path in paths:
        shard = Path(path).name
        current, eligible = None, {s: [] for s in SLICES}

        def close():
            if current is None:
                return
            rng = random.Random(f'{seed}:{shard}:{current}')
            taken = None
            for s in SLICES:
                cands = [p for p in eligible[s] if p.ply != taken]
                if eligible[s]:
                    pool[s]['games'] += 1
                if cands:
                    p = cands[rng.randrange(len(cands))]
                    drawn[s].append(row_of(p))
                    if s == 'positional':
                        taken = p.ply

        for p in positions(path, keep_boards=False):
            if p.game != current:
                close()
                current, eligible = p.game, {s: [] for s in SLICES}
            got = slices_of(p)
            for s in got:
                pool[s]['positions'] += 1
                eligible[s].append(Position(p.shard, p.game, p.ply, p.board.copy(stack=False), p.score, p.result,
                                            p.tactical, p.saved))
        close()
    rng = random.Random(seed)
    seen = set(exclude)
    rows = {}
    for s in SLICES:
        order = sorted(drawn[s], key=lambda r: (r['shard'], r['game']))
        rng.shuffle(order)
        rows[s] = []
        for r in order:
            if r['key'] in seen:
                continue
            seen.add(r['key'])
            rows[s].append(r)
    return {'rows': rows, 'pool': pool}


def write_rows(path, rows):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(COLUMNS) + '\n')
        for r in rows:
            f.write('\t'.join(str(r[c]) for c in COLUMNS) + '\n')


def read_rows(path):
    with open(path, encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        out = []
        for line in f:
            r = dict(zip(head, line.rstrip('\n').split('\t')))
            for c in ('game', 'ply', 'score', 'phase', 'pawn_diff', 'men'):
                r[c] = int(r[c])
            r['result'] = float(r['result'])
            out.append(r)
    return out


def write_openings(path, rows, count, note):
    if count > len(rows):
        raise SystemExit(f'{count} starts asked, {len(rows)} drawn')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(f'# {note}\n')
        for r in rows[:count]:
            f.write(r['fen'] + '\n')


def played(rows, paths):
    """For each game of the pilot shards, its start's row id, first score and result (side to move's
    view) and its positions. A start played twice, or a game whose start is not in rows, is an error."""
    by_key = {r['key']: r['id'] for r in rows}
    out, seen = [], set()
    for path in paths:
        for _, board, result, records in games(path):
            k = key_of(board)
            if k not in by_key:
                raise SystemExit(f'{path}: a game from a start not in the list: {board.fen()}')
            if k in seen:
                raise SystemExit(f'{path}: start played twice: {board.fen()}')
            seen.add(k)
            stm_white = board.turn == chess.WHITE
            first = records[0][1]
            score = None if first == vg.UNSAVED_SCORE else (first if stm_white else -first)
            out.append({'id': by_key[k], 'score': score, 'result': (result / 2) if stm_white else 1 - result / 2,
                        'positions': len(records)})
    return out


def _target(score, result, scale, w):
    return (1 - w) / (1 + math.exp(-score / scale)) + w * result


def gate(standard, pilot, gold, scale=92.0, result_weight=0.5, boot=2000, seed=20261110):
    """The declared offline gate. standard, pilot: id -> {'score', 'result'}; gold: id -> cp."""
    ids = sorted(i for i in standard if i in pilot and i in gold and pilot[i]['score'] is not None
                 and abs(gold[i]) >= GOLD_FLOOR)
    std, pil, parts = [], [], {'score': [], 'result': []}
    for i in ids:
        sgn = 1 if gold[i] > 0 else -1
        a, b = standard[i], pilot[i]
        std.append((_target(a['score'], a['result'], scale, result_weight) - 0.5) * sgn)
        pil.append((_target(b['score'], b['result'], scale, result_weight) - 0.5) * sgn)
        parts['score'].append((_target(b['score'], 0, scale, 0) - _target(a['score'], 0, scale, 0)) * sgn)
        parts['result'].append((b['result'] - a['result']) * sgn)
    n = len(ids)
    if n == 0:
        return {'n': 0, 'pass': False}
    diff = [p - s for p, s in zip(pil, std)]
    rng = random.Random(seed)
    means = sorted(sum(diff[rng.randrange(n)] for _ in range(n)) / n for _ in range(boot))
    lo, hi = means[int(0.025 * boot)], means[min(boot - 1, int(0.975 * boot))]
    gold_t = sum((1 / (1 + math.exp(-gold[i] / scale)) - 0.5) * (1 if gold[i] > 0 else -1) for i in ids) / n
    return {'n': n, 'standard': sum(std) / n, 'pilot': sum(pil) / n, 'difference': sum(diff) / n,
            'difference_ci': [lo, hi], 'score_part': sum(parts['score']) / n, 'result_part': sum(parts['result']) / n,
            'gold_sigmoid': gold_t, 'pass': lo > 0}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('select')
    s.add_argument('shards', nargs='+')
    s.add_argument('--out', required=True)
    s.add_argument('--seed', type=int, default=20261110)
    s.add_argument('--exclude', nargs='*', default=[])
    o = sub.add_parser('openings')
    o.add_argument('tsv')
    o.add_argument('--count', type=int, required=True)
    o.add_argument('--out', required=True)
    p = sub.add_parser('played')
    p.add_argument('tsv')
    p.add_argument('shards', nargs='+')
    p.add_argument('--out', required=True)
    g = sub.add_parser('gate')
    g.add_argument('tsv')
    g.add_argument('played')
    g.add_argument('labels')
    g.add_argument('--scale', type=float, default=92.0)
    g.add_argument('--result-weight', type=float, default=0.5)
    a = ap.parse_args(argv)
    if a.cmd == 'select':
        exclude = {r['key'] for t in a.exclude for r in read_rows(t)}
        out = select(a.shards, a.seed, exclude)
        for name in SLICES:
            write_rows(f'{a.out}-{name}.tsv', out['rows'][name])
        pool = {'seed': a.seed, 'shards': [Path(x).name for x in a.shards], 'excluded': len(exclude),
                'pool': out['pool'], 'drawn': {k: len(v) for k, v in out['rows'].items()}}
        Path(f'{a.out}-pool.json').write_text(json.dumps(pool, indent=1) + '\n', encoding='utf-8')
        print(json.dumps(pool))
    elif a.cmd == 'openings':
        rows = read_rows(a.tsv)
        write_openings(a.out, rows, a.count, f'{a.count} starts from {Path(a.tsv).name} (defense_starts.py)')
        print(f'{a.count} of {len(rows)} starts written')
    elif a.cmd == 'played':
        got = played(read_rows(a.tsv), a.shards)
        with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
            f.write('id\tscore\tresult\tpositions\n')
            for r in got:
                f.write(f"{r['id']}\t{r['score']}\t{r['result']}\t{r['positions']}\n")
        print(f'{len(got)} games matched to their starts')
    else:
        rows = {r['id']: r for r in read_rows(a.tsv)}
        pil = {}
        with open(a.played, encoding='utf-8') as f:
            f.readline()
            for line in f:
                i, sc, res, _ = line.rstrip('\n').split('\t')
                pil[i] = {'score': None if sc == 'None' else int(sc), 'result': float(res)}
        gold = {}
        with open(a.labels, encoding='utf-8') as f:
            for line in f:
                parts = line.rstrip('\n').split('\t')
                if len(parts) >= 2:
                    gold[parts[0]] = int(parts[1])
        print(json.dumps(gate(rows, pil, gold, a.scale, a.result_weight), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
