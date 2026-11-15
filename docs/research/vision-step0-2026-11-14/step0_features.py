# SPDX-License-Identifier: GPL-3.0-or-later
"""Vision step 0 (ideas.md 185): one pass over a `fork-train dump` that finds every family's cells
(step0_common.position_cells) and the base table's cells, and saves them as one compressed .npz (per family a
flat int32 array of cells and per-position offsets), with the phase, the kings' squares and each side's material.

Checks, on every --check-every-th position, against oracles written apart from the finders:
- xl and xx against tools/nnue/models.py's exposed_lower_squares and exposed_squares (square by square, from
  python-chess's attackers; the rules the S512+X / S512+PPXL nets were trained and checked with);
- pin against python-chess's Board.is_pinned for every non-king piece of both sides;
- disc and pinq against a removal oracle: lift the piece and see whether an own slider now attacks the enemy king
  (disc) or an enemy bishop or rook now attacks the own queen (pinq);
- the defender counts behind loose, overprotected and under against python-chess's Board.attackers.
Fork's own Position::pinned()/discoverers() are checked by step0_pins_cpp.py.

    step0_features.py DUMP --out OUT.npz [--limit N] [--workers 3] [--check-every 50]
"""
import argparse
import ctypes
import json
import os
import sys
import time
from multiprocessing import Pool

for var in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[var] = '1'

import chess  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import step0_common as sc  # noqa: E402

sys.path.insert(0, str(sc.REPO / 'tools' / 'nnue'))
import models  # noqa: E402


def below_normal():
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def squares_of(cells, width=64):
    return {c % width for c in cells}


def oracle_check(board, cells, stats):
    stats['checked'] += 1
    xl = {c % 64 for c in cells['xl']}
    xx = {c % 64 for c in cells['xx']}
    stats['xl_mismatch'] += xl != models.exposed_lower_squares(board)
    stats['xx_mismatch'] += xx != models.exposed_squares(board)
    pins = set()
    for c in (chess.WHITE, chess.BLACK):
        for sq in board.pieces(chess.PAWN, c) | board.pieces(chess.KNIGHT, c) | board.pieces(chess.BISHOP, c) | \
                board.pieces(chess.ROOK, c) | board.pieces(chess.QUEEN, c):
            if board.is_pinned(c, sq):
                pins.add(sq)
    stats['pin_mismatch'] += pins != {c % 64 for c in cells['pin']}
    stats['pins_seen'] += len(pins)
    disc, pinq = set(), set()
    for sq, piece in board.piece_map().items():
        c = piece.color
        ek = board.king(not c)
        before = board.attackers(c, ek)
        lifted = board.copy(stack=False)
        lifted.remove_piece_at(sq)
        after = lifted.attackers(c, ek)
        if any(lifted.piece_type_at(a) in (chess.BISHOP, chess.ROOK, chess.QUEEN) for a in after - before):
            disc.add(sq)
        if piece.piece_type != chess.KING:
            for q in board.pieces(chess.QUEEN, c):
                if q == sq:
                    continue
                new = lifted.attackers(not c, q) - board.attackers(not c, q)
                if any(lifted.piece_type_at(a) in (chess.BISHOP, chess.ROOK) for a in new):
                    pinq.add(sq)
    stats['disc_mismatch'] += disc != {c % 64 for c in cells['disc']}
    stats['pinq_mismatch'] += pinq != {c % 64 for c in cells['pinq']}
    stats['disc_seen'] += len(disc)
    stats['pinq_seen'] += len(pinq)
    loose = set()
    under = set()
    for sq, piece in board.piece_map().items():
        if piece.piece_type == chess.KING:
            continue
        d = len(board.attackers(piece.color, sq))
        a = len(board.attackers(not piece.color, sq))
        if piece.piece_type != chess.PAWN:
            if d == 0:
                loose.add((sq, 0))
            elif d - a >= 2:
                loose.add((sq, 1))
        if a >= 2 and d <= 1 and sq not in models.exposed_squares(board):
            under.add(sq)
    got_loose = {(c % 64, (c // 64) % 2) for c in cells['loose']}
    stats['loose_mismatch'] += loose != got_loose
    stats['under_mismatch'] += under != {c % 64 for c in cells['under']}


def work(job):
    below_normal()
    start, packed_list, check_every = job
    fam = {name: [] for name in sc.FAMILY_NAMES}
    counts = {name: [] for name in sc.FAMILY_NAMES}
    base, nbase = [], []
    phase = np.zeros(len(packed_list), dtype=np.int16)
    kings = np.zeros((len(packed_list), 2), dtype=np.int8)
    material = np.zeros((len(packed_list), 2, 5), dtype=np.int8)
    stats = {k: 0 for k in ('checked', 'xl_mismatch', 'xx_mismatch', 'pin_mismatch', 'disc_mismatch',
                            'pinq_mismatch', 'loose_mismatch', 'under_mismatch', 'pins_seen', 'disc_seen',
                            'pinq_seen')}
    for i, packed in enumerate(packed_list):
        board = sc.board_of(packed)
        cells = sc.position_cells(board)
        for name in sc.FAMILY_NAMES:
            fam[name].extend(cells[name])
            counts[name].append(len(cells[name]))
        b = sc.base_cells(packed)
        base.extend(b)
        nbase.append(len(b))
        phase[i] = sc.phase_of(packed)
        kings[i] = (board.king(chess.WHITE), board.king(chess.BLACK))
        for s, c in enumerate((chess.WHITE, chess.BLACK)):
            material[i, s] = [len(board.pieces(t, c)) for t in range(1, 6)]
        if check_every and (start + i) % check_every == 0:
            oracle_check(board, cells, stats)
    return (start, {n: np.array(fam[n], dtype=np.int32) for n in fam},
            {n: np.array(counts[n], dtype=np.int32) for n in counts},
            np.array(base, dtype=np.int16), np.array(nbase, dtype=np.int8), phase, kings, material, stats)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('dump')
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--check-every', type=int, default=50)
    ap.add_argument('--chunk', type=int, default=4000)
    a = ap.parse_args(argv)
    below_normal()
    t0 = time.time()
    positions, scores = sc.read_dump(a.dump, a.limit)
    n = len(positions)
    jobs = [(c0, positions[c0:c0 + a.chunk], a.check_every) for c0 in range(0, n, a.chunk)]
    results = [None] * len(jobs)
    with Pool(a.workers, initializer=below_normal) as pool:
        for k, res in enumerate(pool.imap(work, jobs)):
            results[k] = res
            if k % 20 == 0:
                print(f'{res[0] + len(jobs[k][1])} / {n} positions, {time.time() - t0:.0f} s', flush=True)
    out = {'scores': scores, 'n': np.array([n])}
    stats = {}
    for name in sc.FAMILY_NAMES:
        out[f'{name}_flat'] = np.concatenate([r[1][name] for r in results])
        cnt = np.concatenate([r[2][name] for r in results])
        out[f'{name}_off'] = np.concatenate([[0], np.cumsum(cnt)]).astype(np.int64)
    out['base_flat'] = np.concatenate([r[3] for r in results])
    out['base_off'] = np.concatenate([[0], np.cumsum(np.concatenate([r[4] for r in results]).astype(np.int64))])
    out['phase'] = np.concatenate([r[5] for r in results])
    out['kings'] = np.concatenate([r[6] for r in results])
    out['material'] = np.concatenate([r[7] for r in results])
    for r in results:
        for k, v in r[8].items():
            stats[k] = stats.get(k, 0) + v
    np.savez_compressed(a.out, **out)
    report = {'dump': os.path.basename(a.dump), 'positions': n, 'checks': stats, 'seconds': round(time.time() - t0)}
    report_path = a.out.rsplit('.', 1)[0] + '.json'
    with open(report_path, 'w') as fh:
        json.dump(report, fh, indent=1)
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
