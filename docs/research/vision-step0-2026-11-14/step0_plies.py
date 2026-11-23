# SPDX-License-Identifier: GPL-3.0-or-later
"""Vision step 0 (ideas.md 185): each dump position's ply in its game and the game's final ply, for the learned
progress score's target (the fraction of the game elapsed, ply / final ply; lens 1's L1-1).

`fork-train dump` keeps no ply, so the games of the .vf file the dump was made from are replayed (the viriformat
decoder of tools/datagen/verify_games.py, decode_board; moves applied from their codes) and each record's position
(the board before its move) is matched to the next dump line: side-to-move relative, the same (code, square) list.
A record that does not match is one the trainer's filter dropped (in check, a capture or promotion played, an
unsaved record, |score| > 20,000), and the dump pointer only moves on an exact match, so the alignment cannot drift
silently: the script fails unless every dump position is matched.

    step0_plies.py FILE.vf DUMP --out OUT.npz [--limit N]
"""
import argparse
import json
import os
import sys
from pathlib import Path

import chess
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import step0_common as sc  # noqa: E402

sys.path.insert(0, str(sc.REPO / 'tools' / 'datagen'))
import verify_games as vg  # noqa: E402


def relative(board):
    """The dump's encoding of a board: sorted (code, square) pairs from the side to move."""
    stm = board.turn
    out = []
    for sq, p in board.piece_map().items():
        s = sq if stm == chess.WHITE else sq ^ 56
        code = (p.piece_type - 1) + (0 if p.color == stm else 8)
        out.append((s, code))
    out.sort()
    return bytes(x for s, c in out for x in (c, s))


def canon(packed):
    pairs = sorted((s, c) for c, s in zip(packed[0::2], packed[1::2]))
    return bytes(x for s, c in pairs for x in (c, s))


def move_of(board, code):
    frm, to, promo, kind = code & 63, (code >> 6) & 63, (code >> 12) & 3, code >> 14
    if kind == 2:  # castling: king to its own rook's square in the format
        to = chess.square(6 if chess.square_file(to) > chess.square_file(frm) else 2, chess.square_rank(frm))
    return chess.Move(frm, to, promotion=(promo + chess.KNIGHT) if kind == 3 else None)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('vf')
    ap.add_argument('dump')
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args(argv)
    positions, _ = sc.read_dump(a.dump, a.limit)
    want = [canon(p) for p in positions]
    n = len(want)
    ply = np.zeros(n, dtype=np.int32)
    final = np.zeros(n, dtype=np.int32)
    game_of = np.zeros(n, dtype=np.int32)
    data = Path(a.vf).read_bytes()
    i = k = games = records = 0
    while i < len(data) and k < n:
        board, _ = vg.decode_board(data[i:i + 32])
        i += 32
        start = 2 * (board.fullmove_number - 1) + (1 if board.turn == chess.BLACK else 0)
        first_k = k
        moves = 0
        while True:
            code, score = vg.u16(data, i), vg.i16(data, i + 2)
            i += 4
            if code == 0:
                break
            records += 1
            if k < n and relative(board) == want[k]:
                ply[k] = start + moves
                game_of[k] = games
                k += 1
            board.push(move_of(board, code))
            moves += 1
        final[first_k:k] = start + moves
        games += 1
    if k != n:
        sys.exit(f'only {k} of {n} dump positions matched')
    np.savez(a.out, ply=ply, final=final, game=game_of)
    report = {'vf': os.path.basename(a.vf), 'positions': n, 'matched': k, 'games': games, 'records_read': records,
              'progress_mean': float((ply / final).mean())}
    Path(a.out.rsplit('.', 1)[0] + '.json').write_text(json.dumps(report, indent=1))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
