# SPDX-License-Identifier: GPL-3.0-or-later

"""TD(lambda) labels from Fork's stored self-play games (ideas.md 51; label
tooling only, no training: lambda is chosen later against deep labels).

The label. A game's records r_0 .. r_{N-1} (one per ply, the position before
each move) carry White-view search scores s_t, or UNSAVED_SCORE for an
unsaved position of the split search; z is the stored result from White's
view (1, 1/2, 0). Only full-search scores enter the chain (ideas.md 51's
caveat B13): a record is in the chain when it is saved and its position is
not in check (fork_datagen searches a position in check with check_nodes,
2,000 in generation 3, against 20,000 for the others; --check-scores keep
lets them in). Each chain score gives v_t = sigmoid(s_t / S), the trainer's
own conversion (tools/train src/main.rs `mapper`: 1 / (1 + exp(-score / S)),
S its --scale), mate and tablebase scores included (they saturate to 0 or
1). For ply t and step n >= 0, the n-step value G_t(n) is v_j of the first
chain record j >= t + n, or z when none is left. The label of a chain
record t is the lambda-return (Sutton and Barto's forward view of
TD(lambda))

    T_t = (1 - lambda) * sum_{n=0}^{N-t-1} lambda^n G_t(n) + lambda^(N-t) z,

computed backwards as U_N = z, U_t = (1 - lambda) G_t(0) + lambda U_{t+1},
T_t = U_t. So lambda = 0 gives the record's own stored score and
lambda = 1 the game result; the weights sum to 1. lambda is per ply.
Options:
- --from-next: T_t = U_{t+1}, the formula as ideas.md 51 writes it
  (sum over k >= 1, the record's own score left out; lambda = 0 gives the
  next saved score);
- --unsaved drop: records outside the chain are removed before it is built
  (the steps count chain records only); the default `next` counts plies, a
  ply outside the chain taking the next chain value.
Ends: z is the stored result for every kind of end (checkmate, the rules
draws, the Syzygy table result at table entry, a mate score, the score
adjudication; generation 3 adjudicates at 700 cp for 8 plies). The kind is
inferred by replay (verify_games.py's judgement) and only reported, in the
comparison's breakdown.

`labels` writes a copy of a shard with every chain score of |s| <= 20,000
(the scores the trainer's filter can keep) replaced by the White-view score
whose trainer target is the label, round(S * logit(T_t)) clamped to
+-20,000; every other record (unsaved, in check, mate and tablebase scores)
and every move, board and result is copied unchanged (finding the positions
in check replays the moves, unchecked: the shards were verified at their
seal). So fork-train, run on the copy
with the same --scale and --result-weight 0, trains on the TD labels with
no change to the trainer, and keeps exactly the positions it keeps from the
original (the filter reads the move, the board and |score| <= 20,000). The
integer rounding moves a target by at most 0.25 / S / 2 in probability
(about 0.0014 at S = 92). The chain runs on (T, 1 - T) pairs, so a decided
score survives the round trip: lambda = 0 copies the shard byte for byte.
A sidecar OUT.json records the settings and counts. A one-move game whose
score already says its result (the Syzygy endgame slice's: +-2,000 or 0 with
the table's WDL) is copied unchanged: its label is the tablebase's, and
retrain 8b reads the slice unchanged in every arm (owner, 2026-11-09).

`blend` (retrain 8b's TD arms): a copy whose keepable scores carry the
current target, the blend (1 - W) sigmoid(s / S) + W z, as a score, so a
run at --result-weight 0 trains the TD copies of the newest parts and the
blend copies of every other part together, each file at its own target,
with no change to the trainer. No replay (every keepable score is rewritten;
the trainer still drops the same records); the slice's one-move games are
copied unchanged, as above.

`check` compares a copy with its original: the same boards, moves and
terminators; scores changed only where a relabelling may change them; and
on every --sample-th game each score recomputed by an independent formula
(the forward view of TD(lambda), the defining sum, or the blend) and equal
within 1. Exit 1 on any difference.

`compare` reads deep-labelled sites (crucial_points.py's folders:
sites.jsonl with id, fen and game "SHARD#INDEX", the index 0-based in the
shard; deep.tsv with id, cp from the side to move, mate flag, depth),
finds each site's game in the shards under --data, replays it, and matches
the site's position (board, side, castling, en passant) to a saved record of
that game (the first such record, or the site's own "record" index when
it names one, as tools/measure/label_pretest.py's sample does; one site
per record, the first). For each
lambda of --grid it reports the mean squared error of the record's label
(side to move's view) against sigmoid(deep / S), and the mean signed error,
over the records the trainer keeps (not in check, no capture or promotion
played, |score| <= 20,000) and over all matched saved records, per end
kind; with the score/result blend's error (1 - w) sigmoid(s_t / S) + w z at
--blend w for reference. It chooses nothing.

    td_labels.py labels SHARD --out OUT.vf --lam L --scale S [--games N] [--from-next] [--unsaved next|drop]
                        [--check-scores skip|keep]
    td_labels.py blend SHARD --out OUT.vf --scale S [--weight W]
    td_labels.py check ORIGINAL COPY --mode td|blend --scale S [--lam L] [--weight W] [--sample N]
    td_labels.py compare --sites DIR... --data DIR... --scale S [--grid L,L,...] [--blend W,...]
                         [--from-next] [--unsaved next|drop] [--check-scores skip|keep] [--json OUT.json]
"""
import argparse
import hashlib
import json
import math
import struct
import sys
import time
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_games as vg  # noqa: E402

KEEP_LIMIT = 20000  # the trainer's max_eval (tools/train MAX_SCORE, EvalLimit)
UNSAVED = vg.UNSAVED_SCORE
WHITE_RESULT = (0.0, 0.5, 1.0)  # the stored result byte: 0 Black wins, 1 draw, 2 White wins
DEFAULT_GRID = (0.0, 0.5, 0.7, 0.8, 0.85, 0.9, 0.93, 0.95, 0.97, 0.98, 0.99, 1.0)


def win_pair(score, scale):
    """(sigmoid(score / S), sigmoid(-score / S)), each computed without
    cancellation, so the smaller one keeps its precision."""
    x = score / scale
    if x >= 0:
        e = math.exp(-x)
        return 1.0 / (1.0 + e), e / (1.0 + e)
    e = math.exp(x)
    return e / (1.0 + e), 1.0 / (1.0 + e)


def td_pairs(scores, result, lam, scale, from_next=False, unsaved='next', skip=None):
    """The White-view label of each record as a pair (T, 1 - T); None for a
    record outside the chain (unsaved, or flagged in `skip`: the positions in
    check). `scores` are the records' White-view scores, `result` the stored
    result byte (0, 1, 2)."""
    if not 0.0 <= lam <= 1.0:
        raise ValueError(f'lambda {lam} outside [0, 1]')
    if unsaved not in ('next', 'drop'):
        raise ValueError(f'unsaved mode {unsaved!r}')
    z = WHITE_RESULT[result]
    chain = [s != UNSAVED and not (skip and skip[t]) for t, s in enumerate(scores)]
    order = list(range(len(scores)))
    if unsaved == 'drop':
        order = [t for t in order if chain[t]]
    out = [None] * len(scores)
    u = (z, 1.0 - z)  # U after the last step
    nv = u            # the next saved value (z past the end)
    for t in reversed(order):
        after = u
        if chain[t]:
            nv = win_pair(scores[t], scale)
        u = ((1.0 - lam) * nv[0] + lam * after[0], (1.0 - lam) * nv[1] + lam * after[1])
        if chain[t]:
            out[t] = after if from_next else u
    return out


def td_targets(scores, result, lam, scale, from_next=False, unsaved='next', skip=None):
    """td_pairs' labels as plain White-view probabilities."""
    return [None if p is None else p[0] for p in td_pairs(scores, result, lam, scale, from_next, unsaved, skip)]


def pair_to_score(pair, scale):
    """The White-view integer score whose sigmoid(score / S) is the label,
    clamped to the trainer's +-20,000."""
    t, q = pair
    if q <= 0.0:
        return KEEP_LIMIT
    if t <= 0.0:
        return -KEEP_LIMIT
    return max(-KEEP_LIMIT, min(KEEP_LIMIT, round(scale * (math.log(t) - math.log(q)))))


def split_games(data, limit=None):
    """(start byte, header, [(code, score)...], end byte) of each game, read
    without a replay; at most `limit` games."""
    i, n = 0, 0
    while i < len(data) and (limit is None or n < limit):
        if len(data) - i < 32:
            raise vg.Bad(f'truncated board at byte {i}')
        start, head = i, data[i:i + 32]
        i += 32
        recs = []
        while True:
            if len(data) - i < 4:
                raise vg.Bad(f'truncated moves at byte {i}')
            code, score = struct.unpack_from('<Hh', data, i)
            i += 4
            if code == 0:
                break
            recs.append((code, score))
        yield start, head, recs, i
        n += 1


def move_of(board, code):
    """The move a record's code stands for, without a legality check
    (castling written as the king to its own rook, python-chess's as the
    king's two-square move)."""
    frm, to, promo, kind = code & 63, code >> 6 & 63, code >> 12 & 3, code >> 14
    if kind == 2:
        to = chess.square(6 if chess.square_file(to) > chess.square_file(frm) else 2, chess.square_rank(frm))
    return chess.Move(frm, to, promo + chess.KNIGHT if kind == 3 else None)


def check_flags(head, recs):
    """Whether each record's position is in check, by an unchecked replay."""
    board, _ = vg.decode_board(head)
    flags = []
    for code, _s in recs:
        flags.append(board.is_check())
        board.push(move_of(board, code))
    return flags


def settled_one_move(recs, result, scale):
    """Whether a game is one record whose keepable score already says its
    result: sigmoid(s / S) within 1e-6 of z. That is the endgame slice's
    one-move game (tools/datagen/endgame_slice.py: +-2,000 or 0 with the
    table's WDL as the result), whose label is the tablebase's, not a
    search's: retrain 8b reads the slice unchanged in every arm (owner,
    2026-11-09), and its target is the same at any result weight. A
    one-record self-play game (a mate score, beyond the trainer's limit, in
    the shards seen) or any other one-move game is relabelled like the rest."""
    if len(recs) != 1 or recs[0][1] == UNSAVED or abs(recs[0][1]) > KEEP_LIMIT:
        return False
    return abs(win_pair(recs[0][1], scale)[0] - WHITE_RESULT[result]) <= 1e-6


def relabel_shard(data, lam, scale, games=None, from_next=False, unsaved='next', check_scores='skip'):
    """The shard (its first `games` games) with TD labels in place of the
    keepable chain scores, and the counts. A table-labelled one-move game
    (settled_one_move: the endgame slice's) is copied unchanged."""
    out = bytearray()
    counts = {'games': 0, 'records': 0, 'relabelled': 0, 'unsaved': 0, 'in_check': 0, 'beyond_limit': 0,
              'clamped': 0, 'one_move': 0}
    for start, head, recs, end in split_games(data, games):
        if head[30] > 2:
            raise vg.Bad(f'bad result byte at {start}')
        if settled_one_move(recs, head[30], scale):
            out += data[start:end]
            counts['one_move'] += 1
            counts['games'] += 1
            counts['records'] += 1
            continue
        scores = [s for _, s in recs]
        skip = check_flags(head, recs) if check_scores == 'skip' else None
        pairs = td_pairs(scores, head[30], lam, scale, from_next, unsaved, skip)
        out += head
        for (code, s), p in zip(recs, pairs):
            if s == UNSAVED:
                counts['unsaved'] += 1
            elif p is None:
                counts['in_check'] += 1
            elif abs(s) > KEEP_LIMIT:
                counts['beyond_limit'] += 1
            else:
                s = pair_to_score(p, scale)
                counts['relabelled'] += 1
                counts['clamped'] += abs(s) == KEEP_LIMIT
            out += struct.pack('<Hh', code, s)
        out += struct.pack('<Hh', 0, 0)
        counts['games'] += 1
        counts['records'] += len(recs)
    return bytes(out), counts


def blend_pair(score, result, weight, scale):
    """The trainer's target (1 - W) sigmoid(s / S) + W z (White's view) as a pair (T, 1 - T)."""
    v, q = win_pair(score, scale)
    z = WHITE_RESULT[result]
    return (1.0 - weight) * v + weight * z, (1.0 - weight) * q + weight * (1.0 - z)


def blend_shard(data, weight, scale):
    """The shard with every keepable score (|s| <= 20,000, saved) replaced by
    the score whose sigmoid is the score/result blend at result weight W, so
    --result-weight 0 on the copy trains what --result-weight W trains on the
    original (to the integer rounding). No replay: the records the trainer
    drops (in check, captures, promotions) are rewritten too and still
    dropped. Table-labelled one-move games are copied unchanged
    (settled_one_move)."""
    out = bytearray()
    counts = {'games': 0, 'records': 0, 'relabelled': 0, 'unsaved': 0, 'beyond_limit': 0, 'clamped': 0,
              'one_move': 0}
    for start, head, recs, end in split_games(data):
        result = head[30]
        if result > 2:
            raise vg.Bad(f'bad result byte at {start}')
        counts['games'] += 1
        counts['records'] += len(recs)
        if settled_one_move(recs, result, scale):
            out += data[start:end]
            counts['one_move'] += 1
            continue
        out += head
        for code, s in recs:
            if s == UNSAVED:
                counts['unsaved'] += 1
            elif abs(s) > KEEP_LIMIT:
                counts['beyond_limit'] += 1
            else:
                s = pair_to_score(blend_pair(s, result, weight, scale), scale)
                counts['relabelled'] += 1
                counts['clamped'] += abs(s) == KEEP_LIMIT
            out += struct.pack('<Hh', code, s)
        out += struct.pack('<Hh', 0, 0)
    return bytes(out), counts


def forward_td_pair(scores, chain, result, lam, scale, t):
    """Record t's label by the forward view (the defining sum, not the
    backward recursion relabel_shard uses), for the copy check:
    (1 - lambda) sum_n lambda^n G_t(n) + lambda^(N - t) z, G_t(n) the pair of
    the first chain record j >= t + n, or z past the last."""
    n_rec = len(scores)
    z = (WHITE_RESULT[result], 1.0 - WHITE_RESULT[result])
    nxt = [None] * (n_rec + 1)
    nxt[n_rec] = z
    for j in range(n_rec - 1, -1, -1):
        nxt[j] = win_pair(scores[j], scale) if chain[j] else nxt[j + 1]
    a = b = 0.0
    for n in range(n_rec - t):
        w = (1.0 - lam) * lam ** n
        a += w * nxt[t + n][0]
        b += w * nxt[t + n][1]
    w = lam ** (n_rec - t)
    return a + w * z[0], b + w * z[1]


def check_copy(original, copy, mode, param, scale, sample=100, check_scores='skip'):
    """A relabelled copy against its original. Every game: the same boards,
    moves and terminators; scores changed only on keepable records of games
    of two or more records, and within +-20,000 there. Every `sample`-th game
    (and its in-check records, by replay): each score equal, within 1, to the
    label recomputed independently (mode 'td': forward_td_pair at lambda =
    param, the default definition; 'blend': blend_pair at W = param).
    Returns the counts and the first problems found."""
    report = {'games': 0, 'records': 0, 'changed': 0, 'games_recomputed': 0, 'records_recomputed': 0,
              'max_difference': 0, 'bad': []}

    def bad(text):
        if len(report['bad']) < 20:
            report['bad'].append(text)

    if len(original) != len(copy):
        bad(f'length {len(copy)} against {len(original)}')
        return report
    try:
        pairs = zip(split_games(original), split_games(copy), strict=True)
        for k, ((s0, h0, r0, e0), (s1, h1, r1, e1)) in enumerate(pairs):
            report['games'] += 1
            report['records'] += len(r0)
            if (s0, e0) != (s1, e1) or h0 != h1 or [c for c, _ in r0] != [c for c, _ in r1]:
                bad(f'game {k}: board, moves or length differ')
                continue
            if settled_one_move(r0, h0[30], scale):
                if r0 != r1:
                    bad(f'game {k}: a table-labelled one-move game was changed')
                continue
            for t, ((_, a), (_, b)) in enumerate(zip(r0, r1)):
                if a != b:
                    report['changed'] += 1
                    if a == UNSAVED or abs(a) > KEEP_LIMIT or abs(b) > KEEP_LIMIT:
                        bad(f'game {k} record {t}: {a} changed to {b}')
            if sample <= 0 or k % sample:
                continue
            report['games_recomputed'] += 1
            scores = [a for _, a in r0]
            skip = check_flags(h0, r0) if mode == 'td' and check_scores == 'skip' else [False] * len(r0)
            chain = [a != UNSAVED and not skip[t] for t, a in enumerate(scores)]
            for t, ((_, a), (_, b)) in enumerate(zip(r0, r1)):
                if a == UNSAVED or abs(a) > KEEP_LIMIT:
                    continue
                if mode == 'td':
                    if not chain[t]:
                        if a != b:
                            bad(f'game {k} record {t}: in check, changed {a} to {b}')
                        continue
                    want = pair_to_score(forward_td_pair(scores, chain, h0[30], param, scale, t), scale)
                else:
                    want = pair_to_score(blend_pair(a, h0[30], param, scale), scale)
                report['records_recomputed'] += 1
                report['max_difference'] = max(report['max_difference'], abs(b - want))
                if abs(b - want) > 1:
                    bad(f'game {k} record {t}: {b}, recomputed {want}')
    except (ValueError, vg.Bad) as e:
        bad(f'unreadable: {e}')
    return report


def fen_key(board):
    """Board, side to move, castling and a legal en passant square (the clocks left out)."""
    return ' '.join(board.fen(en_passant='legal').split()[:4])


def end_kind(board, last_score, table_pieces, streak_sign):
    """verify_games.py's judgement of how the game ended, its rules draws
    told apart."""
    _want, why = vg.expected_end(board, last_score, table_pieces, streak_sign)
    if why != 'rules draw':
        return why
    if board.is_stalemate():
        return 'stalemate'
    if board.is_insufficient_material():
        return 'insufficient material'
    if board.halfmove_clock >= 100:
        return 'fifty moves'
    return 'repetition'


def replay(head, recs, table_pieces=5, adjudicate=None):
    """Each record's (fen key, side to move is White, kept by the trainer,
    in check) and the game's end kind."""
    board, _result = vg.decode_board(head)
    rows = []
    last = None
    count = sign = done = 0
    for code, score in recs:
        moves = [m for m in board.legal_moves if vg.code_of(board, m) == code]
        if len(moves) != 1:
            raise vg.Bad(f'move code {code} matches {len(moves)} legal moves in {board.fen()}')
        move = moves[0]
        kept = (score != UNSAVED and abs(score) <= KEEP_LIMIT and not board.is_check()
                and not board.is_capture(move) and move.promotion is None)
        rows.append((fen_key(board), board.turn == chess.WHITE, kept, board.is_check()))
        board.push(move)
        if score == UNSAVED:
            last = None
            continue
        last = score
        if adjudicate and abs(score) < vg.MATE_BAND_FLOOR and not done:
            count, sign = vg.streak_step(count, sign, score, adjudicate[0])
            if count >= adjudicate[1]:
                done = sign
    return rows, end_kind(board, last, table_pieces, done)


def read_sites(folder):
    """[(id, fen, shard name, game index, deep cp, mate flag, record)] of a
    deep-labelled folder; record is the site's own record index when the
    site file names one (a sampled game record), else None."""
    deep = {}
    for line in (folder / 'deep.tsv').read_text(encoding='utf-8').splitlines():
        if line.strip():
            f = line.split('\t')
            deep[int(f[0])] = (int(f[1]), int(f[2]))
    out = []
    for line in (folder / 'sites.jsonl').read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        s = json.loads(line)
        if s['id'] not in deep or '#' not in s.get('game', ''):
            continue
        name, index = s['game'].rsplit('#', 1)
        out.append((s['id'], s['fen'], name, int(index)) + deep[s['id']] + (s.get('record'),))
    return out


def find_shard(name, data_dirs):
    for d in data_dirs:
        hits = sorted(Path(d).rglob(name))
        if hits:
            return hits[0]
    return None


def shard_settings(path):
    """The score adjudication of the run whose manifest sits beside the shard."""
    for man in path.parent.glob('*.json'):
        try:
            m = json.loads(man.read_text())
        except (OSError, ValueError):
            continue
        st = m.get('settings', {})
        files = [e.get('file') for b in m.get('batches', []) for e in b] + [e.get('file') for e in m.get('shards', [])]
        if path.name in files:
            return [st['adjudicate_cp'], st['adjudicate_plies']] if st.get('adjudicate_plies', 0) > 0 else None
    return None


def matched_records(folders, data_dirs, table_pieces=5):
    """For each folder, the matched (game, record) pairs: dicts with the
    game's scores and result, the record index, its side, kept flag, end
    kind and the deep label. Also the counts of unmatched sites."""
    out = []
    stats = {'sites': 0, 'no_shard': 0, 'no_match': 0, 'duplicate': 0}
    for folder in map(Path, folders):
        sites = read_sites(folder)
        stats['sites'] += len(sites)
        by_shard = {}
        for s in sites:
            by_shard.setdefault(s[2], []).append(s)
        for name, group in sorted(by_shard.items()):
            path = find_shard(name, data_dirs)
            if path is None:
                stats['no_shard'] += len(group)
                continue
            adjudicate = shard_settings(path)
            wanted = {s[3] for s in group}
            games = {}
            data = path.read_bytes()
            for index, (_start, head, recs, _end) in enumerate(split_games(data, max(wanted) + 1)):
                if index in wanted:
                    games[index] = (head, recs)
            del data
            replays = {}
            seen = set()
            for sid, fen, _name, index, cp, mate, own in sorted(group, key=lambda s: s[0]):
                if index not in games:
                    stats['no_match'] += 1
                    continue
                head, recs = games[index]
                if index not in replays:
                    replays[index] = replay(head, recs, table_pieces, adjudicate)
                rows, kind = replays[index]
                key = fen_key(chess.Board(fen))
                if own is not None:  # the site names its record: it must be that position, saved
                    t = own if 0 <= own < len(rows) and rows[own][0] == key and recs[own][1] != UNSAVED else None
                else:
                    t = next((k for k, r in enumerate(rows) if r[0] == key and recs[k][1] != UNSAVED), None)
                if t is None:
                    stats['no_match'] += 1
                    continue
                if (folder, name, index, t) in seen:
                    stats['duplicate'] += 1
                    continue
                seen.add((folder, name, index, t))
                out.append({'folder': folder.name if folder.name not in ('n1m', 'n1m2', 'n100k', 'n300k') else
                            f'{folder.parent.name}/{folder.name}', 'game': f'{name}#{index}', 'record': t,
                            'scores': [r[1] for r in recs], 'check': [r[3] for r in rows],
                            'result': head[30], 'white': rows[t][1],
                            'kept': rows[t][2], 'end': kind, 'deep': cp, 'mate': mate})
    return out, stats


def error_table(rows, scale, grid, blends, from_next=False, unsaved='next', check_scores='skip'):
    """{subset: {label name: (n, mse, mean signed error)}} over kept and all
    matched records, and per end kind (kept records)."""
    acc = {}

    def add(subset, name, err):
        n, sq, sg = acc.setdefault(subset, {}).get(name, (0, 0.0, 0.0))
        acc[subset][name] = (n + 1, sq + err * err, sg + err)

    cache = {}
    for r in rows:
        gold = win_pair(r['deep'], scale)[0]
        key = (r['game'], tuple(r['scores']))
        for lam in grid:
            if (key, lam) not in cache:
                cache[(key, lam)] = td_targets(r['scores'], r['result'], lam, scale, from_next, unsaved,
                                               r['check'] if check_scores == 'skip' else None)
            t = cache[(key, lam)][r['record']]
            if t is None:  # a record in check, outside the chain: no label
                continue
            label = t if r['white'] else 1.0 - t
            name = f'lambda={lam:g}'
            subsets = ['all saved'] + (['kept', f'kept, end: {r["end"]}'] if r['kept'] else [])
            for sub in subsets:
                add(sub, name, label - gold)
        v = win_pair(r['scores'][r['record']], scale)[0]
        z = WHITE_RESULT[r['result']]
        for w in blends:
            b = (1.0 - w) * v + w * z
            label = b if r['white'] else 1.0 - b
            for sub in ['all saved'] + (['kept', f'kept, end: {r["end"]}'] if r['kept'] else []):
                add(sub, f'blend w={w:g}', label - gold)
    return {sub: {name: (n, sq / n, sg / n) for name, (n, sq, sg) in names.items()} for sub, names in acc.items()}


def write_atomic(path, data):
    """Writes through a .part file, so an interrupted run leaves no complete-looking output."""
    tmp = path.with_name(path.name + '.part')
    tmp.write_bytes(data)
    tmp.replace(path)


def parse_floats(text):
    return [float(x) for x in text.split(',') if x.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    for p in (sub.add_parser('labels', help='a copy of a shard with TD labels as its scores'),
              sub.add_parser('compare', help="each lambda's error against deep labels")):
        p.add_argument('--scale', type=float, required=True, help="the trainer's --scale S")
        p.add_argument('--from-next', action='store_true', help="ideas.md 51's sum over k >= 1")
        p.add_argument('--unsaved', choices=('next', 'drop'), default='next')
        p.add_argument('--check-scores', choices=('skip', 'keep'), default='skip',
                       help='whether the scores of positions in check (a cheaper search) enter the chain')
    lp = sub.choices['labels']
    lp.add_argument('shard', type=Path)
    lp.add_argument('--out', type=Path, required=True)
    lp.add_argument('--lam', type=float, required=True)
    lp.add_argument('--games', type=int, help='only the first N games')
    cp_ = sub.choices['compare']
    cp_.add_argument('--sites', type=Path, nargs='+', required=True)
    cp_.add_argument('--data', type=Path, nargs='+', required=True)
    cp_.add_argument('--grid', default=','.join(f'{x:g}' for x in DEFAULT_GRID))
    cp_.add_argument('--blend', default='0.5', help='result weights of the reference blend')
    cp_.add_argument('--table-pieces', type=int, default=5)
    cp_.add_argument('--json', type=Path)
    bp = sub.add_parser('blend', help='a copy whose scores carry the score/result blend, for --result-weight 0')
    bp.add_argument('shard', type=Path)
    bp.add_argument('--out', type=Path, required=True)
    bp.add_argument('--weight', type=float, default=0.5, help="the blend's result weight W")
    bp.add_argument('--scale', type=float, required=True, help="the trainer's --scale S")
    kp = sub.add_parser('check', help='a copy against its original, labels recomputed on a sample of games')
    kp.add_argument('original', type=Path)
    kp.add_argument('copy', type=Path)
    kp.add_argument('--mode', choices=('td', 'blend'), required=True)
    kp.add_argument('--lam', type=float, help='mode td: lambda')
    kp.add_argument('--weight', type=float, default=0.5, help='mode blend: W')
    kp.add_argument('--scale', type=float, required=True)
    kp.add_argument('--sample', type=int, default=100, help='recompute every N-th game (0: none)')
    kp.add_argument('--check-scores', choices=('skip', 'keep'), default='skip')
    a = ap.parse_args(argv)
    if a.scale <= 0:
        ap.error('--scale must be positive')
    began = time.monotonic()
    try:
        if a.command == 'labels':
            data = a.shard.read_bytes()
            out, counts = relabel_shard(data, a.lam, a.scale, a.games, a.from_next, a.unsaved, a.check_scores)
            write_atomic(a.out, out)
            info = {'source': a.shard.name, 'lambda': a.lam, 'scale': a.scale,
                    'from_next': a.from_next, 'unsaved_mode': a.unsaved, 'check_scores': a.check_scores,
                    'games_limit': a.games,
                    'sha256': hashlib.sha256(out).hexdigest(), 'bytes': len(out), **counts,
                    'seconds': round(time.monotonic() - began, 1)}
            a.out.with_name(a.out.name + '.json').write_text(json.dumps(info, indent=1) + '\n')
            print(json.dumps(info))
            return 0
        if a.command == 'blend':
            out, counts = blend_shard(a.shard.read_bytes(), a.weight, a.scale)
            write_atomic(a.out, out)
            info = {'source': a.shard.name, 'blend_weight': a.weight, 'scale': a.scale,
                    'sha256': hashlib.sha256(out).hexdigest(), 'bytes': len(out), **counts,
                    'seconds': round(time.monotonic() - began, 1)}
            a.out.with_name(a.out.name + '.json').write_text(json.dumps(info, indent=1) + '\n')
            print(json.dumps(info))
            return 0
        if a.command == 'check':
            if a.mode == 'td' and a.lam is None:
                ap.error('--mode td needs --lam')
            param = a.lam if a.mode == 'td' else a.weight
            report = check_copy(a.original.read_bytes(), a.copy.read_bytes(), a.mode, param, a.scale, a.sample,
                                a.check_scores)
            print(json.dumps({'original': a.original.name, 'copy': a.copy.name, 'mode': a.mode, 'param': param,
                              **report, 'seconds': round(time.monotonic() - began, 1)}))
            return 1 if report['bad'] else 0
        grid, blends = parse_floats(a.grid), parse_floats(a.blend)
        rows, stats = matched_records(a.sites, a.data, a.table_pieces)
        table = error_table(rows, a.scale, grid, blends, a.from_next, a.unsaved, a.check_scores)
    except vg.Bad as e:
        print(f'FAIL {e}', file=sys.stderr)
        return 1
    stats.update(matched=len(rows), kept=sum(r['kept'] for r in rows), mate_labels=sum(r['mate'] for r in rows),
                 seconds=round(time.monotonic() - began, 1))
    print(json.dumps(stats))
    for sub_name in ['kept', 'all saved'] + sorted(s for s in table if s.startswith('kept, end')):
        if sub_name not in table:
            continue
        print(f'== {sub_name}')
        for name, (n, mse, bias) in table[sub_name].items():
            print(f'{name:>14}  n {n:6d}  mse {mse:.6f}  mean error {bias:+.6f}')
    if a.json:
        a.json.write_text(json.dumps({'settings': {'scale': a.scale, 'grid': grid, 'blend': blends,
                                                   'from_next': a.from_next, 'unsaved': a.unsaved,
                                                   'check_scores': a.check_scores,
                                                   'sites': [str(s) for s in a.sites]},
                                      'stats': stats, 'errors': table}, indent=1) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
