# SPDX-License-Identifier: GPL-3.0-or-later

"""The offline pre-test of XGR's exposure plane (KB phase4-designs/
design-novelty.md §2.2, falsifying experiment step 1; judgement.md: XGR-512
enters the bake-off only if X passes it).

For positions from Fork's shards (the training filter applied: not in
check, no capture or promotion played, |score| <= 20000), it counts k, the
pieces that are "exposed" by XGR's rule, and compares the static
evaluation's residual |static - search score| for k = 0 against k >= 1. If
positions with k >= 1 carry no larger residual, X has nothing to fix.

XGR's rule: a non-king piece on s is exposed if an enemy piece of a
strictly lower value class attacks s (pawn < knight = bishop < rook <
queen), or if s is attacked by at least one enemy piece and defended by
none of its own. Pseudo-attacks on the real occupancy (sliders stop at the
first piece, pins ignored, no x-rays, no en passant). Kings count as
attackers and defenders. The rule gives the king no value class, which the
judge flagged; Fork's reading: as an attacker the king ranks above the
queen, so it is never a "lower" attacker, but it still attacks an
undefended piece and defends its own.

The static evaluation comes from a Fork binary (`fork evalfens`): the
bootstrap evaluation for a provisional run on generation 0, a network
build for the run the judge specified (B0 on generation-1 data).

    exposure_pretest.py FORK SHARD... [--positions N]
"""
import argparse
import statistics
import subprocess
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'datagen'))
import verify_games as vg  # noqa: E402

CLASS = {chess.PAWN: 1, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5}
MAX_SCORE = 20000


def exposed_count(board):
    k = 0
    for sq, piece in board.piece_map().items():
        if piece.piece_type == chess.KING:
            continue
        attackers = board.attackers(not piece.color, sq)
        if not attackers:
            continue
        lower = any(CLASS[board.piece_type_at(a)] < CLASS[piece.piece_type] for a in attackers)
        defended = bool(board.attackers(piece.color, sq))
        if lower or not defended:
            k += 1
    return k


def samples(paths, limit):
    """Yields (FEN, search score from White's view, k) for the kept
    positions, at most `limit`, reading one shard at a time."""
    n = 0
    for path in paths:
        data = Path(path).read_bytes()
        i = 0
        while i + 32 <= len(data) and n < limit:
            board, _ = vg.decode_board(data[i:i + 32])
            i += 32
            while i + 4 <= len(data):
                code, score = vg.u16(data, i), vg.i16(data, i + 2)
                i += 4
                if code == 0:
                    break
                move = next(m for m in board.legal_moves if vg.code_of(board, m) == code)
                if n < limit and not board.is_check() and not board.is_capture(move) and move.promotion is None \
                        and abs(score) <= MAX_SCORE:
                    yield board.fen(), score if board.turn == chess.WHITE else -score, exposed_count(board)
                    n += 1
                board.push(move)
        if n >= limit:
            return


def chunks(items, size):
    chunk = []
    for item in items:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('fork')
    ap.add_argument('shards', nargs='+')
    ap.add_argument('--positions', type=int, default=300000)
    ap.add_argument('--chunk', type=int, default=100000, help='positions per evalfens call (memory)')
    a = ap.parse_args(argv)
    from array import array
    fork = str(Path(a.fork).resolve())
    groups = {'k=0': array('i'), 'k>=1': array('i')}
    ks = array('b')
    for chunk in chunks(samples(a.shards, a.positions), a.chunk):
        fens = ''.join(f + '\n' for f, _, _ in chunk)
        out = subprocess.run([fork, 'evalfens'], input=fens, capture_output=True, text=True, check=True).stdout.split()
        assert len(out) == len(chunk), 'evalfens gave a different number of scores'
        for (_, search, k), static in zip(chunk, out):
            groups['k=0' if k == 0 else 'k>=1'].append(abs(int(static) - search))
            ks.append(min(k, 127))
    evaluator = subprocess.run([fork, 'version'], capture_output=True, text=True).stdout
    evaluator = next((l for l in evaluator.splitlines() if l.startswith(('evaluator', 'net'))), 'unknown')
    print(f'{len(ks)} positions, {evaluator}; mean k {statistics.mean(ks):.2f}, '
          f'k=0 in {100 * ks.count(0) / len(ks):.1f}%, k>=3 in {100 * sum(k >= 3 for k in ks) / len(ks):.1f}%')
    for name, rs in groups.items():
        print(f'  {name:5} n {len(rs):>7}  residual mean {statistics.mean(rs):7.1f} cp  median '
              f'{statistics.median(rs):6.1f} cp')
    m0, m1 = statistics.mean(groups['k=0']), statistics.mean(groups['k>=1'])
    print('verdict:', 'X has something to fix (k>=1 residual larger)' if m1 > m0 else 'X has nothing to fix: stop')
    return 0


if __name__ == '__main__':
    sys.exit(main())
