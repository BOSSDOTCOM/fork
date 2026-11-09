# SPDX-License-Identifier: GPL-3.0-or-later
"""Idea 52's data arm for retrain 8b (owner, 2026-11-09; ideas.md 52, DESIGN.md
item 8 and the 2026-11-07 decision "Idea 52: the independent committee"):
the training positions on which two independently trained networks disagree
most, deep-labelled by the default engine.

1. `positions SHARD OUT.tsv`: every kept training position of a sealed
   viriformat shard, replayed by this file's own decoder (no python-chess, so
   it runs in a bare Python): the position before each recorded move, kept
   when its record is saved (not the split search's UNSAVED_SCORE) and it
   passes the trainer's filter (tools/train/src/main.rs `filter()`: not in
   check, the move played not a capture or promotion, |score| at most
   20,000). One line per kept position:
   game<TAB>ply<TAB>move<TAB>score<TAB>result<TAB>fen, the move in UCI
   (castling as the king's two-square move), the score as stored (White's
   view), the result 0 / 1 / 2 (Black win / draw / White win), the FEN's en
   passant square only when a pawn could take there (python-chess's xfen).
2. Each network's evaluation of those positions comes from `fork evalfens`
   of a build with that network embedded (the engine's own integer values,
   side to move's view), one line per position:
   `cut -f6 OUT.tsv | fork evalfens > OUT.a`.
3. `select WORK OUT --shards NAME...`: reads WORK/NAME.tsv, NAME.a and
   NAME.b. The disagreement is D = |a - b| in cp (idea 52's report: the
   detector "D in cp" of the scratch pair, error ratio 1.69 at equal |eval|).
   The top set is every position with D at or above the value at rank
   ceil(top_share * n) from the top (the report's top 5%, ties included);
   the sites are `count` positions drawn from it uniformly (a seeded key per
   position; the smallest keys win), duplicates of a position (its first four
   FEN fields) dropped; the control is `control` positions drawn the same way
   from the rest, for the error-ratio check. Writes OUT/sites.jsonl (the
   controls first, then the sites in key order, so any prefix of the sites is
   a uniform sample of them) and OUT/stats.json.
4. `label ENGINE OUT`: each site of OUT/sites.jsonl searched by the default
   engine (its bench checked against the repository's reference first), one
   thread, Hash 16, `ucinewgame` before each, to --nodes nodes, with the
   Syzygy tables of --syzygy DIR; the last reported score is the label (side
   to move's view; a mate written as +-20,000 and flagged). Appends
   id<TAB>cp<TAB>mate<TAB>depth to OUT/labels.tsv; resumable (a rerun drops
   a last line cut short and searches only the sites without a label).
5. `check OUT`: the labelled controls against the labelled sites: the default
   network's mean |eval - label| on each (decided labels left out: mates and
   table wins, |cp| >= TABLE_BAND), plain and with the
   controls reweighted to the sites' |eval| distribution (the report's
   eval-size matching). With --resamples N, also the matched ratio's 95%
   percentile bootstrap interval (N resamples, --seed; the sites and the
   controls each drawn again with replacement, the matched ratio recomputed
   in full from each draw), the interval of the owner's 2026-11-09 rule.
6. `manifest OUT FILE...`: each file's size and SHA-256, as JSON.

    committee_sites.py positions SHARD OUT.tsv
    committee_sites.py select WORK OUT --shards NAME... [--top-share 0.05] [--count 200000]
                       [--control 2000] [--seed 20261109]
    committee_sites.py label ENGINE OUT [--nodes 200000] [--workers 2] [--syzygy DIR] [--limit N]
    committee_sites.py check OUT [--resamples N] [--seed 20261109]
    committee_sites.py manifest OUT.json FILE...
"""
import argparse
import hashlib
import heapq
import json
import math
import queue
import random
import re
import subprocess
import sys
import threading
from pathlib import Path

UNSAVED_SCORE = 32767  # src/datagen/self_play.hpp: an unsaved position's record
KEPT_MAX_SCORE = 20000  # tools/train/src/main.rs MAX_SCORE, the filter's max_eval
MATE_LABEL = 20000      # a deep search's mate score, as crucial_points.py writes it
TABLE_BAND = 29500 - 250  # src/search/score_bounds.hpp: TbWinScore - MaxPly, a table win's reported cp
PIECE_CHARS = 'PNBRQK'
# Castling rights as bits (K, Q, k, q) and the rights each square keeps when
# a piece leaves or arrives there.
RIGHT_BITS = {'K': 1, 'Q': 2, 'k': 4, 'q': 8}
KEEP_RIGHTS = [15] * 64
KEEP_RIGHTS[4], KEEP_RIGHTS[0], KEEP_RIGHTS[7] = 15 & ~3, 15 & ~2, 15 & ~1
KEEP_RIGHTS[60], KEEP_RIGHTS[56], KEEP_RIGHTS[63] = 15 & ~12, 15 & ~8, 15 & ~4
CASTLING_ROOKS = {(7, 0): 'K', (0, 0): 'Q', (63, 1): 'k', (56, 1): 'q'}


def _steps(sq, deltas):
    f, r = sq % 8, sq // 8
    return [(r + dr) * 8 + f + df for df, dr in deltas if 0 <= f + df < 8 and 0 <= r + dr < 8]


def _rays(sq, deltas):
    out = []
    for df, dr in deltas:
        ray, f, r = [], sq % 8 + df, sq // 8 + dr
        while 0 <= f < 8 and 0 <= r < 8:
            ray.append(r * 8 + f)
            f, r = f + df, r + dr
        out.append(ray)
    return out


KNIGHT_STEPS = [_steps(s, [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)])
                for s in range(64)]
KING_STEPS = [_steps(s, [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]) for s in range(64)]
ORTHOGONAL_LINES = [_rays(s, [(1, 0), (-1, 0), (0, 1), (0, -1)]) for s in range(64)]
DIAGONAL_LINES = [_rays(s, [(1, 1), (1, -1), (-1, 1), (-1, -1)]) for s in range(64)]
# The squares from which a pawn of each colour (0 White, 1 Black) attacks a square.
PAWN_FROM = [[_steps(s, [(-1, -1), (1, -1)]) for s in range(64)], [_steps(s, [(-1, 1), (1, 1)]) for s in range(64)]]


def square_attacked(board, sq, by_white):
    """Whether a piece of the given colour attacks `sq` (board: 64 entries, '' or a FEN letter)."""
    pawn, knight, king = ('P', 'N', 'K') if by_white else ('p', 'n', 'k')
    straight, diagonal = ('RQ', 'BQ') if by_white else ('rq', 'bq')
    for s in PAWN_FROM[0 if by_white else 1][sq]:
        if board[s] == pawn:
            return True
    for s in KNIGHT_STEPS[sq]:
        if board[s] == knight:
            return True
    for s in KING_STEPS[sq]:
        if board[s] == king:
            return True
    for rays, sliders in ((ORTHOGONAL_LINES[sq], straight), (DIAGONAL_LINES[sq], diagonal)):
        for ray in rays:
            for s in ray:
                p = board[s]
                if p:
                    if p in sliders:
                        return True
                    break
    return False


def board_fen(board, white, rights, ep, halfmove, fullmove):
    rows = []
    for r in range(7, -1, -1):
        row, empty = '', 0
        for p in board[r * 8:r * 8 + 8]:
            if p:
                if empty:
                    row += str(empty)
                    empty = 0
                row += p
            else:
                empty += 1
        rows.append(row + (str(empty) if empty else ''))
    castling = ''.join(c for c in 'KQkq' if rights & RIGHT_BITS[c]) or '-'
    ep_text = '-'
    if ep is not None:
        # xfen: only when a pawn of the side to move stands beside the pawn that moved two squares.
        pawn = 'P' if white else 'p'
        if any(board[s] == pawn for s in PAWN_FROM[0 if white else 1][ep]):
            ep_text = 'abcdefgh'[ep % 8] + str(ep // 8 + 1)
    return f'{"/".join(rows)} {"w" if white else "b"} {castling} {ep_text} {halfmove} {fullmove}'


def decode_header(h):
    """The start board of a game record (viriformat's 32-byte header):
    (board, white_to_move, rights, ep, halfmove, fullmove, result)."""
    occupancy = int.from_bytes(h[0:8], 'little')
    board = [''] * 64
    rights = 0
    k = 0
    for sq in range(64):
        if not occupancy >> sq & 1:
            continue
        code = (h[8 + k // 2] >> (4 * (k % 2))) & 15
        k += 1
        kind, black = code & 7, code >> 3
        if kind == 7:
            raise ValueError('piece code 7')
        if kind == 6:  # a rook that can still castle
            right = CASTLING_ROOKS.get((sq, black))
            if right is None:
                raise ValueError('castling rook off its corner')
            rights |= RIGHT_BITS[right]
            kind = 3
        board[sq] = PIECE_CHARS[kind].lower() if black else PIECE_CHARS[kind]
    ep = h[24] & 127
    if h[30] > 2:
        raise ValueError('bad result')
    return (board, not h[24] & 128, rights, None if ep == 64 else ep, h[25],
            max(1, h[26] | h[27] << 8), h[30])


def replay_records(data):
    """Yields (game, ply, uci, score, result, fen) for every kept position of a
    shard's bytes (see the module's note 1)."""
    i, game = 0, 0
    n = len(data)
    while i < n:
        if n - i < 32:
            raise ValueError(f'truncated board at byte {i}')
        board, white, rights, ep, halfmove, fullmove, result = decode_header(data[i:i + 32])
        i += 32
        ply = 0
        while True:
            if n - i < 4:
                raise ValueError(f'truncated moves at byte {i}')
            code = data[i] | data[i + 1] << 8
            score = data[i + 2] | data[i + 3] << 8
            if score >= 32768:
                score -= 65536
            i += 4
            if code == 0:
                break
            frm, to, kind = code & 63, (code >> 6) & 63, code >> 14
            piece = board[frm]
            if not piece or piece.isupper() != white:
                raise ValueError(f'game {game} ply {ply}: no piece of the side to move on {frm}')
            target = board[to]
            capture = kind == 1 or (kind != 2 and target != '')
            if score != UNSAVED_SCORE and abs(score) <= KEPT_MAX_SCORE and not capture and kind != 3:
                king = board.index('K' if white else 'k')
                if not square_attacked(board, king, not white):
                    if kind == 2:
                        uci_to = (to // 8) * 8 + (6 if to % 8 > frm % 8 else 2)
                    else:
                        uci_to = to
                    uci = 'abcdefgh'[frm % 8] + str(frm // 8 + 1) + 'abcdefgh'[uci_to % 8] + str(uci_to // 8 + 1)
                    yield game, ply, uci, score, result, board_fen(board, white, rights, ep, halfmove, fullmove)
            # Play the move.
            new_ep = None
            if kind == 2:  # castling: the king to its rook's square in the code
                rank = (to // 8) * 8
                king_to, rook_to = (rank + 6, rank + 5) if to % 8 > frm % 8 else (rank + 2, rank + 3)
                rook = board[to]
                board[frm] = board[to] = ''
                board[king_to], board[rook_to] = piece, rook
            else:
                board[frm] = ''
                if kind == 1:
                    board[to - 8 if white else to + 8] = ''
                    board[to] = piece
                elif kind == 3:
                    promoted = 'NBRQ'[(code >> 12) & 3]
                    board[to] = promoted if white else promoted.lower()
                else:
                    board[to] = piece
                    if piece in 'Pp' and abs(to - frm) == 16:
                        new_ep = (frm + to) // 2
            rights &= KEEP_RIGHTS[frm] & KEEP_RIGHTS[to]
            halfmove = 0 if capture or piece in 'Pp' else halfmove + 1
            if not white:
                fullmove += 1
            white = not white
            ep = new_ep
            ply += 1
        game += 1


def position_key(fen):
    return ' '.join(fen.split(' ')[:4])


def _rows(work, name):
    """Lockstep (row fields, a, b) over a shard's positions and both evaluation files."""
    with open(work / f'{name}.tsv', encoding='utf-8') as fp, open(work / f'{name}.a', encoding='utf-8') as fa, \
            open(work / f'{name}.b', encoding='utf-8') as fb:
        for line, la, lb in zip(fp, fa, fb, strict=True):
            yield line.rstrip('\n').split('\t'), int(la), int(lb)


def top_threshold(histogram, share):
    """The D at rank ceil(share * n) from the top, n the histogram's total."""
    n = sum(histogram.values())
    rank = max(1, math.ceil(share * n))
    seen = 0
    for d in sorted(histogram, reverse=True):
        seen += histogram[d]
        if seen >= rank:
            return d
    return 0


def _quantile(histogram, q):
    n = sum(histogram.values())
    target, seen = q * n, 0
    for d in sorted(histogram):
        seen += histogram[d]
        if seen >= target:
            return d
    return None


def _draw(heap, size, key, item):
    """Keeps the `size` smallest keys (a max-heap on -key)."""
    if len(heap) < size:
        heapq.heappush(heap, (-key, item))
    elif -heap[0][0] > key:
        heapq.heapreplace(heap, (-key, item))


def _distinct(heap, count):
    out, seen = [], set()
    for neg_key, item in sorted(heap, key=lambda e: -e[0]):
        k = position_key(item['fen'])
        if k not in seen:
            seen.add(k)
            out.append(item)
            if len(out) == count:
                return out
    raise SystemExit(f'only {len(out)} distinct positions drawn, {count} wanted')


PIECE_BANDS = ((2, 6), (7, 12), (13, 18), (19, 24), (25, 32))


def select_sites(work, shards, top_share, count, control, seed):
    histogram, pool = {}, {}
    sums = [0] * 6  # n, a, b, aa, bb, ab
    for name in shards:
        n = 0
        for _, a, b in _rows(work, name):
            d = abs(a - b)
            histogram[d] = histogram.get(d, 0) + 1
            sums[0] += 1
            sums[1] += a
            sums[2] += b
            sums[3] += a * a
            sums[4] += b * b
            sums[5] += a * b
            n += 1
        pool[name] = n
    threshold = top_threshold(histogram, top_share)
    rng = random.Random(seed)
    top_heap, rest_heap = [], []
    margin = lambda k: k + max(100, k // 10)  # noqa: E731 (room for dropped duplicates)
    bands = {f'{lo}-{hi}': [0, 0, 0, 0] for lo, hi in PIECE_BANDS}  # n, D sum, top n, |a| sum
    top_n = 0
    for name in shards:
        for idx, (row, a, b) in enumerate(_rows(work, name)):
            d = abs(a - b)
            key = rng.random()
            fen = row[5]
            pieces = sum(1 for c in fen.split(' ')[0] if c.isalpha())
            band = bands[next(f'{lo}-{hi}' for lo, hi in PIECE_BANDS if pieces <= hi)]
            band[0] += 1
            band[1] += d
            band[3] += abs(a)
            item = None
            if d >= threshold:
                top_n += 1
                band[2] += 1
                if len(top_heap) < margin(count) or -top_heap[0][0] > key:
                    item = 'top'
            elif len(rest_heap) < margin(control) or -rest_heap[0][0] > key:
                item = 'control'
            if item:
                site = {'set': item, 'shard': name, 'line': idx, 'game': int(row[0]), 'ply': int(row[1]),
                        'move': row[2], 'score_white': int(row[3]), 'result': int(row[4]), 'eval_a': a,
                        'eval_b': b, 'd': d, 'fen': fen}
                _draw(top_heap if item == 'top' else rest_heap, margin(count if item == 'top' else control),
                      key, site)
    controls = _distinct(rest_heap, control) if control else []
    sites = _distinct(top_heap, count)
    n = sums[0]
    cov = sums[5] / n - (sums[1] / n) * (sums[2] / n)
    var_a, var_b = sums[3] / n - (sums[1] / n) ** 2, sums[4] / n - (sums[2] / n) ** 2
    total_d = sum(d * c for d, c in histogram.items())
    top_d = sum(d * c for d, c in histogram.items() if d >= threshold)
    stats = {
        'positions': n, 'positions_by_shard': pool, 'top_share': top_share, 'threshold_cp': threshold,
        'top_set': top_n, 'sites': len(sites), 'controls': len(controls), 'seed': seed,
        'pearson_a_b': round(cov / math.sqrt(var_a * var_b), 4),
        'mean_eval_a': round(sums[1] / n, 2), 'mean_eval_b': round(sums[2] / n, 2),
        'd_cp': {'mean': round(total_d / n, 2), 'median': _quantile(histogram, 0.5),
                 'p90': _quantile(histogram, 0.9), 'p95': _quantile(histogram, 0.95),
                 'p99': _quantile(histogram, 0.99), 'p999': _quantile(histogram, 0.999), 'max': max(histogram)},
        'top_set_share_of_total_d': round(top_d / total_d, 4) if total_d else None,
        'sites_mean_d': round(sum(s['d'] for s in sites) / len(sites), 2),
        'sites_mean_abs_eval_a': round(sum(abs(s['eval_a']) for s in sites) / len(sites), 2),
        'controls_mean_abs_eval_a': round(sum(abs(s['eval_a']) for s in controls) / len(controls), 2)
        if controls else None,
        'by_pieces': {k: {'n': v[0], 'd_mean': round(v[1] / v[0], 2) if v[0] else None,
                          'top_share': round(v[2] / v[0], 4) if v[0] else None,
                          'abs_eval_a_mean': round(v[3] / v[0], 2) if v[0] else None}
                      for k, v in bands.items()},
    }
    return controls, sites, stats


def check_bench(engine):
    """The engine's bench against the repository's reference for its network; returns (nodes, signature)."""
    version = subprocess.run([engine, 'version'], capture_output=True, text=True, check=True).stdout
    bench = subprocess.run([engine, 'bench'], capture_output=True, text=True, check=True).stdout
    net = re.search(r'^net (\S+)', version, re.M).group(1)
    ref = (Path(__file__).resolve().parents[2] / 'tests' / f'bench-{net}.ref').read_text(encoding='utf-8')
    nodes = re.search(r'nodes (\d+)', bench).group(1)
    signature = re.search(r'signature ([0-9a-f]+)', bench).group(1)
    if f'nodes {nodes}\n' not in ref + '\n' or f'signature {signature}' not in ref:
        raise SystemExit(f'bench {nodes} / {signature} does not match tests/bench-{net}.ref')
    return nodes, signature


def parse_label(info):
    """(value, mate flag, depth) from the last info line with a score."""
    cp = re.search(r' score cp (-?\d+)', info or '')
    mate = re.search(r' score mate (-?\d+)', info or '')
    depth = re.search(r' depth (\d+)', info or '')
    if cp:
        value, is_mate = int(cp.group(1)), 0
    elif mate:
        value, is_mate = (MATE_LABEL if int(mate.group(1)) > 0 else -MATE_LABEL), 1
    else:
        raise RuntimeError(f'no score in {info!r}')
    return value, is_mate, int(depth.group(1)) if depth else 0


def search_labels(engine, todo, out_path, nodes, workers, syzygy=None, popen=subprocess.Popen):
    """Searches each (id, fen) to `nodes` nodes; appends id, value, mate flag and depth lines."""
    jobs = queue.Queue()
    for item in todo:
        jobs.put(item)
    lock = threading.Lock()
    errors = []

    def work():
        p = popen([engine], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

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

        try:
            send('uci')
            read_until('uciok')
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
                read_until('readyok')
                send(f'position fen {fen}')
                send(f'go nodes {nodes}')
                value, is_mate, depth = parse_label(read_until('bestmove'))
                with lock, open(out_path, 'a', encoding='utf-8') as f:
                    f.write(f'{site_id}\t{value}\t{is_mate}\t{depth}\n')
            send('quit')
            p.wait(timeout=30)
        except Exception as e:  # noqa: BLE001 (reported after the other workers finish)
            errors.append(e)
            p.kill()

    threads = [threading.Thread(target=work) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise errors[0]


def read_labels(path):
    """The complete label lines of a labels file (a last line cut short is dropped from the file)."""
    if not path.exists():
        return {}
    text = path.read_text(encoding='utf-8')
    if text and not text.endswith('\n'):
        text = text[:text.rfind('\n') + 1]
        path.write_text(text, encoding='utf-8')
    labels = {}
    for line in text.splitlines():
        site_id, value, mate, depth = line.split('\t')
        labels[int(site_id)] = (int(value), int(mate), int(depth))
    return labels


ABS_EVAL_BINS = (0, 25, 50, 100, 200, 400, 800)


def _bin(v):
    return sum(1 for edge in ABS_EVAL_BINS[1:] if abs(v) >= edge)


def _errors(group, labels):
    """(|eval| bin, |eval - label|) of each labelled position whose label is not decided (a mate or a table win)."""
    out = []
    for s in group:
        lab = labels.get(s['id'])
        if lab and not lab[1] and abs(lab[0]) < TABLE_BAND:
            out.append((_bin(s['eval_a']), abs(s['eval_a'] - lab[0])))
    return out


def _matched(es, ec):
    """The sites' mean error over the controls' at the sites' |eval| bins (sites in a bin no control holds left
    out), and the number of sites counted; None when no site is in a control's bin."""
    total, count = {}, {}
    for b, e in ec:
        total[b] = total.get(b, 0) + e
        count[b] = count.get(b, 0) + 1
    covered = [(b, e) for b, e in es if b in count]
    if not covered:
        return None, 0
    matched_control = sum(total[b] / count[b] for b, _ in covered) / len(covered)
    return (sum(e for _, e in covered) / len(covered)) / matched_control, len(covered)


def error_ratio(sites, controls, labels):
    """The default network's mean |eval - label| on the sites over the controls',
    plain and matched (the controls reweighted to the sites' |eval| bins); decided labels (mates, table wins) left out."""
    es, ec = _errors(sites, labels), _errors(controls, labels)
    if not es or not ec:
        return None
    plain = (sum(e for _, e in es) / len(es)) / (sum(e for _, e in ec) / len(ec))
    matched, covered = _matched(es, ec)
    return {'sites': len(es), 'controls': len(ec), 'sites_mean_error_cp': round(sum(e for _, e in es) / len(es), 2),
            'controls_mean_error_cp': round(sum(e for _, e in ec) / len(ec), 2), 'ratio': round(plain, 3),
            'ratio_matched': round(matched, 3), 'sites_in_matched_bins': covered}


def matched_interval(sites, controls, labels, resamples, seed):
    """The matched ratio's 95% percentile bootstrap interval: each resample draws the sites and the controls again
    with replacement (separately) and recomputes the matched ratio from the draw; a draw with no site in a control's
    bin is redrawn."""
    es, ec = _errors(sites, labels), _errors(controls, labels)
    rng = random.Random(seed)
    values = []
    while len(values) < resamples:
        value, _ = _matched(rng.choices(es, k=len(es)), rng.choices(ec, k=len(ec)))
        if value is not None:
            values.append(value)
    values.sort()
    low = values[int(0.025 * resamples)]
    high = values[min(resamples - 1, math.ceil(0.975 * resamples) - 1)]
    return {'resamples': resamples, 'seed': seed, 'low': round(low, 3), 'high': round(high, 3)}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('positions')
    p.add_argument('shard', type=Path)
    p.add_argument('out', type=Path)
    p = sub.add_parser('select')
    p.add_argument('work', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--shards', nargs='+', required=True)
    p.add_argument('--top-share', type=float, default=0.05)
    p.add_argument('--count', type=int, default=200000)
    p.add_argument('--control', type=int, default=2000)
    p.add_argument('--seed', type=int, default=20261109)
    p = sub.add_parser('label')
    p.add_argument('engine')
    p.add_argument('out', type=Path)
    p.add_argument('--nodes', type=int, default=200000)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--syzygy', default=None)
    p.add_argument('--limit', type=int, default=None, help='label only the first N sites of the file')
    p = sub.add_parser('check')
    p.add_argument('out', type=Path)
    p.add_argument('--resamples', type=int, default=0)
    p.add_argument('--seed', type=int, default=20261109)
    p = sub.add_parser('manifest')
    p.add_argument('out', type=Path)
    p.add_argument('files', type=Path, nargs='+')
    a = parser.parse_args(argv)

    if a.command == 'positions':
        data = a.shard.read_bytes()
        tmp = a.out.with_name(a.out.name + '.part')
        n = 0
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            for game, ply, uci, score, result, fen in replay_records(data):
                f.write(f'{game}\t{ply}\t{uci}\t{score}\t{result}\t{fen}\n')
                n += 1
        tmp.replace(a.out)
        print(f'{a.shard.name}: {n} kept positions', flush=True)
        return 0

    if a.command == 'select':
        controls, sites, stats = select_sites(a.work, a.shards, a.top_share, a.count, a.control, a.seed)
        a.out.mkdir(parents=True, exist_ok=True)
        with open(a.out / 'sites.jsonl', 'w', encoding='utf-8', newline='\n') as f:
            for k, s in enumerate(controls + sites):
                f.write(json.dumps({'id': k, **s}, separators=(',', ':')) + '\n')
        (a.out / 'stats.json').write_text(json.dumps(stats, indent=1) + '\n', encoding='utf-8')
        print(json.dumps(stats), flush=True)
        return 0

    if a.command == 'manifest':
        files = {f.name: {'bytes': f.stat().st_size, 'sha256': sha256_file(f)} for f in a.files}
        a.out.write_text(json.dumps(files, indent=1) + '\n', encoding='utf-8')
        return 0

    rows = [json.loads(line) for line in (a.out / 'sites.jsonl').read_text(encoding='utf-8').splitlines()]
    if a.command == 'label':
        engine = str(Path(a.engine).resolve())
        nodes, signature = check_bench(engine)
        print(f'bench {nodes} / {signature} matches the reference', flush=True)
        path = a.out / 'labels.tsv'
        done = read_labels(path)
        chosen = rows if a.limit is None else rows[:a.limit]
        todo = [(s['id'], s['fen']) for s in chosen if s['id'] not in done]
        print(f'{len(todo)} sites to search ({len(done)} done), {a.nodes} nodes each', flush=True)
        search_labels(engine, todo, path, a.nodes, a.workers, a.syzygy)
        return 0

    # check
    labels = read_labels(a.out / 'labels.tsv')
    top, control = [s for s in rows if s['set'] == 'top'], [s for s in rows if s['set'] == 'control']
    result = error_ratio(top, control, labels)
    if result and a.resamples > 0:
        result['ratio_matched_95'] = matched_interval(top, control, labels, a.resamples, a.seed)
    print(json.dumps(result))
    return 0 if result else 1


if __name__ == '__main__':
    sys.exit(main())
