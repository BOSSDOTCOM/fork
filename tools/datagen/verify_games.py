# SPDX-License-Identifier: GPL-3.0-or-later

"""Independent check of fork_datagen's shards (DESIGN.md §5.3, deliverable 2).

Decodes each viriformat game with its own decoder, written from the
format's README (cosmobobak/viriformat, pinned in KB phase4-pipeline.md §3),
not from Fork's C++, and replays it with python-chess's move generator:
- every move code must match exactly one legal move of its position
  (castling as king to own rook, en passant type 1, promotions type 3);
- the start board's fields (castling from the rook codes, en passant, side
  to move) must give a valid position;
- the stored result must follow from how the game ended: a mate or a rules
  draw on the board, or an adjudication Fork makes (a mate score in the
  last record, or a position within --table-pieces pieces, whose table
  result is not rechecked here);
- with --manifest (fork_datagen's <run>.json), each shard's game and
  position counts must match.

    .venv/Scripts/python.exe -I tools/datagen/verify_games.py SHARD... [--manifest RUN.json]

Exit status 0 when every game passes; prints a summary line.
"""
import argparse
import json
import sys
from pathlib import Path

import chess

MATE_BAND_FLOOR = 30000 - 250  # src/search/score_bounds.hpp: MateScore - MaxPly
PIECE_TYPES = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]
CASTLING_CORNERS = {(chess.H1, chess.WHITE): 'K', (chess.A1, chess.WHITE): 'Q',
                    (chess.H8, chess.BLACK): 'k', (chess.A8, chess.BLACK): 'q'}


class Bad(Exception):
    pass


def u16(b, i):
    return b[i] | (b[i + 1] << 8)


def i16(b, i):
    v = u16(b, i)
    return v - 65536 if v >= 32768 else v


def decode_board(h):
    occupancy = int.from_bytes(h[0:8], 'little')
    if occupancy == 0:
        raise Bad('zero occupancy')
    board = chess.Board(None)
    rights = []
    k = 0
    for sq in range(64):
        if not occupancy >> sq & 1:
            continue
        code = (h[8 + k // 2] >> (4 * (k % 2))) & 15
        k += 1
        kind, color = code & 7, chess.BLACK if code & 8 else chess.WHITE
        if kind == 7:
            raise Bad('piece code 7')
        if kind == 6:
            if (sq, color) not in CASTLING_CORNERS:
                raise Bad('castling rook off its corner')
            rights.append(CASTLING_CORNERS[(sq, color)])
            kind = 3
        board.set_piece_at(sq, chess.Piece(PIECE_TYPES[kind], color))
    if k > 32:
        raise Bad('more than 32 pieces')
    board.turn = chess.BLACK if h[24] & 128 else chess.WHITE
    board.set_castling_fen(''.join(c for c in 'KQkq' if c in rights) or '-')
    ep = h[24] & 127
    if ep > 64:
        raise Bad('bad ep square')
    board.ep_square = None if ep == 64 else ep
    board.halfmove_clock = h[25]
    board.fullmove_number = max(1, u16(h, 26))
    if h[30] > 2 or h[31] != 0:
        raise Bad('bad result or reserved byte')
    if not board.is_valid():
        raise Bad(f'invalid start position {board.fen()} ({board.status()!r})')
    if board.castling_rights != board.clean_castling_rights():
        raise Bad('castling rights without king and rook at home')
    return board, h[30]


def code_of(board, move):
    """The format's 16-bit code for a python-chess move."""
    frm, to, kind, promo = move.from_square, move.to_square, 0, 0
    if board.is_castling(move):
        kind = 2
        # python-chess gives standard castling as the king's two-square move;
        # the format writes the king to its own rook's square.
        to = chess.square(7 if chess.square_file(to) > chess.square_file(frm) else 0, chess.square_rank(frm))
    elif board.is_en_passant(move):
        kind = 1
    elif move.promotion:
        kind = 3
        promo = move.promotion - chess.KNIGHT
    return frm | to << 6 | promo << 12 | kind << 14


def expected_end(board, last_score, table_pieces):
    """'1-0', '0-1' or '1/2-1/2' if the end can be judged here, else None,
    and what ended the game."""
    if board.is_checkmate():
        return ('0-1' if board.turn == chess.WHITE else '1-0'), 'checkmate'
    if board.is_stalemate() or board.is_insufficient_material():
        return '1/2-1/2', 'rules draw'
    if board.halfmove_clock >= 100 or board.is_repetition(3):
        return '1/2-1/2', 'rules draw'
    if last_score is not None and abs(last_score) >= MATE_BAND_FLOOR:
        return ('1-0' if last_score > 0 else '0-1'), 'mate score'
    if chess.popcount(board.occupied) <= table_pieces:
        return None, 'table'
    return None, 'unexplained'


def verify_file(path, table_pieces, totals):
    data = Path(path).read_bytes()
    games = positions = 0
    i = 0
    while i < len(data):
        if len(data) - i < 32:
            raise Bad(f'{path}: truncated board at byte {i}')
        board, result = decode_board(data[i:i + 32])
        i += 32
        last_score = None
        while True:
            if len(data) - i < 4:
                raise Bad(f'{path}: truncated moves at byte {i}')
            code, score = u16(data, i), i16(data, i + 2)
            i += 4
            if code == 0:
                if score != 0:
                    raise Bad(f'{path}: bad terminator at byte {i - 4}')
                break
            matches = [m for m in board.legal_moves if code_of(board, m) == code]
            if len(matches) != 1:
                raise Bad(f'{path}: move code {code} matches {len(matches)} legal moves in {board.fen()}')
            board.push(matches[0])
            last_score = score
            positions += 1
        want, why = expected_end(board, last_score, table_pieces)
        stored = ['0-1', '1/2-1/2', '1-0'][result]
        if why == 'unexplained':
            raise Bad(f'{path}: game {games} ended without a reason at {board.fen()}')
        if want is not None and want != stored:
            raise Bad(f'{path}: game {games} stored {stored} but ended by {why} as {want} at {board.fen()}')
        totals[why] = totals.get(why, 0) + 1
        games += 1
    return games, positions


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('shards', nargs='+')
    ap.add_argument('--manifest', help="fork_datagen's <run>.json, to compare counts")
    ap.add_argument('--table-pieces', type=int, default=5,
                    help='largest piece count the run adjudicated by tables (0: none)')
    a = ap.parse_args(argv)
    totals = {}
    counts = {}
    try:
        for s in a.shards:
            counts[Path(s).name] = verify_file(s, a.table_pieces, totals)
        if a.manifest:
            man = json.loads(Path(a.manifest).read_text())
            listed = {e['file']: (e['games'], e['positions']) for e in man['shards']}
            for name, got in counts.items():
                if listed.get(name) != got:
                    raise Bad(f'{name}: {got} games/positions, manifest says {listed.get(name)}')
            missing = set(listed) - set(counts)
            if missing:
                raise Bad(f'shards in the manifest but not checked: {sorted(missing)}')
    except Bad as e:
        print(f'FAIL {e}', file=sys.stderr)
        return 1
    g = sum(c[0] for c in counts.values())
    p = sum(c[1] for c in counts.values())
    print(f'ok: {len(counts)} shards, {g} games, {p} positions; ends {json.dumps(totals, sort_keys=True)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
