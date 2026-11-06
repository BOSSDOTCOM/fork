# SPDX-License-Identifier: GPL-3.0-or-later

"""The Syzygy endgame slice for the next snapshot (ideas.md idea 45; owner,
2026-11-06: random legal positions of at most 5 pieces, labelled by their
WDL, a small fixed share of the data), so the nets learn the simple endings
that Fork's games end at (adjudication at table entry keeps them out of the
self-play data).

Positions: random legal placements of a material signature (pawns on ranks
2-7, either side to move, kings apart, the side not to move not in check),
kept when the side to move is not in check and has a quiet legal move after
which the game is not over on the board (the trainer drops positions whose
recorded move is a capture or promotion, and a mate or stalemate after the
move would contradict the stored result).
Signatures: half of the positions from KPK, KQK and KRK in equal shares
(the standing endgame check's three, with the strong side drawn at random),
half from the signatures Fork's own games reach at table entry (the
`signatures` command counts them from sealed shards: the first position of
at most TABLE_PIECES pieces in each game), in proportion.

Labels: the Syzygy WDL from the side to move (python-chess's prober on the
3-4-5 tables), cursed wins and blessed losses counted as draws (the
fifty-move rule decides them). Each position is written as a one-move game
in Fork's viriformat (the board, one quiet legal move, the terminator): the
result from White's view, and the move's score SLICE_SCORE (or -SLICE_SCORE,
or 0 for a draw) from White's view, so that the trainer's target, a blend of
sigmoid(score / S) and the result, equals the WDL (at S = 92,
sigmoid(2000 / 92) = 1 - 4e-10). No position repeats within one file's
seed stream (seeded; reproducible). tools/datagen/verify_games.py checks
the files like any self-play shard (--table-pieces 5 accepts a game ending
at a table position).

    endgame_slice.py signatures SHARD... --games N --out SIGS.json
    endgame_slice.py generate --tables DIR --signatures SIGS.json --positions N --out FILE.vf [--seed S]
"""
import argparse
import json
import random
import struct
import sys
from collections import Counter
from pathlib import Path

import chess
import chess.syzygy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_games as vg  # noqa: E402

TABLE_PIECES = 5
SLICE_SCORE = 2000  # cp from White's view for a win: within the trainer's |score| <= 20000, sigmoid saturated
BASIC = ['KPvK', 'KQvK', 'KRvK']
KIND = {'P': chess.PAWN, 'N': chess.KNIGHT, 'B': chess.BISHOP, 'R': chess.ROOK, 'Q': chess.QUEEN, 'K': chess.KING}
NIBBLE = {chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5}


def signature(board):
    """'KRPvKR' style: White's pieces, then Black's, each strongest first (python-chess's order)."""
    def side(c):
        return ''.join(chess.piece_symbol(t).upper() * len(board.pieces(t, c)) for t in range(6, 0, -1))
    return f'{side(chess.WHITE)}v{side(chess.BLACK)}'


def count_signatures(paths, max_games):
    """Material signatures at table entry in sealed shards: each game's first position of at most
    TABLE_PIECES pieces (games that never get there are not counted)."""
    seen, games = Counter(), 0
    for path in paths:
        data = Path(path).read_bytes()
        i = 0
        while i < len(data) and games < max_games:
            games += 1
            board, _ = vg.decode_board(data[i:i + 32])
            i += 32
            found = chess.popcount(board.occupied) <= TABLE_PIECES
            if found:
                seen[signature(board)] += 1
            while True:
                code = vg.u16(data, i)
                i += 4
                if code == 0:
                    break
                if not found:
                    board.push(next(m for m in board.legal_moves if vg.code_of(board, m) == code))
                    if chess.popcount(board.occupied) <= TABLE_PIECES:
                        found = True
                        seen[signature(board)] += 1
    return seen, games


def place(rng, sig):
    """A random legal board of signature `sig` ('KRvKP'; either colour may take either side), or None."""
    white, black = sig.split('v')
    if rng.random() < 0.5:
        white, black = black, white
    board = chess.Board(None)
    free = list(range(64))
    rng.shuffle(free)
    for colour, pieces in ((chess.WHITE, white), (chess.BLACK, black)):
        for p in pieces:
            kind = KIND[p]
            for k, sq in enumerate(free):
                if kind != chess.PAWN or 8 <= sq < 56:
                    board.set_piece_at(free.pop(k), chess.Piece(kind, colour))
                    break
            else:
                return None
    board.turn = rng.random() < 0.5
    board.castling_rights = chess.BB_EMPTY
    board.ep_square = None
    return board if board.is_valid() else None


def encode(board, move, result_white, score_white):
    """One-move viriformat game: the 32-byte board (verify_games.decode_board's layout), the move, the terminator."""
    occ = 0
    nibbles = []
    for sq in range(64):
        p = board.piece_at(sq)
        if p is None:
            continue
        occ |= 1 << sq
        nibbles.append(NIBBLE[p.piece_type] | (8 if p.color == chess.BLACK else 0))
    packed = bytearray(16)
    for k, n in enumerate(nibbles):
        packed[k // 2] |= n << (4 * (k % 2))
    head = struct.pack('<Q', occ) + bytes(packed)
    head += bytes([(0 if board.turn == chess.WHITE else 128) | 64, board.halfmove_clock])
    head += struct.pack('<H', board.fullmove_number) + struct.pack('<h', 0) + bytes([result_white, 0])
    return head + struct.pack('<Hh', vg.code_of(board, move), score_white) + struct.pack('<Hh', 0, 0)


def generate(tables, sigs, n, seed):
    """`n` labelled one-move games (bytes), the per-WDL counts and the per-signature counts."""
    rng = random.Random(seed)
    own = sorted(sigs.items())
    total = sum(c for _, c in own)
    names, weights = [s for s, _ in own], [c / total for _, c in own]
    out, wdl, made, seen = bytearray(), Counter(), Counter(), set()
    with chess.syzygy.open_tablebase(tables) as tb:
        while sum(made.values()) < n:
            sig = rng.choice(BASIC) if rng.random() < 0.5 else rng.choices(names, weights)[0]
            board = place(rng, sig)
            if board is None or board.is_check():
                continue
            # The recorded move: quiet, and not ending the game on the board (a stalemate or mate after it
            # would contradict the stored result; verify_games checks it).
            quiet = []
            for m in board.legal_moves:
                if board.is_capture(m) or m.promotion:
                    continue
                board.push(m)
                if not board.is_game_over(claim_draw=False):
                    quiet.append(m)
                board.pop()
            if not quiet:
                continue
            key = board.board_fen() + ('w' if board.turn else 'b')
            if key in seen:
                continue
            w = tb.probe_wdl(board)
            seen.add(key)
            stm = 1 if w == 2 else -1 if w == -2 else 0  # cursed wins and blessed losses are draws
            white = stm if board.turn == chess.WHITE else -stm
            out += encode(board, rng.choice(quiet), white + 1, SLICE_SCORE * white)
            wdl[('loss', 'draw', 'win')[white + 1]] += 1
            made[signature(board)] += 1
    return bytes(out), wdl, made


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('signatures')
    s.add_argument('shards', nargs='+')
    s.add_argument('--games', type=int, default=60000)
    s.add_argument('--out', required=True)
    g = sub.add_parser('generate')
    g.add_argument('--tables', required=True)
    g.add_argument('--signatures', required=True)
    g.add_argument('--positions', type=int, required=True)
    g.add_argument('--out', required=True)
    g.add_argument('--seed', type=int, default=20261106)
    a = ap.parse_args(argv)
    if a.cmd == 'signatures':
        seen, games = count_signatures(a.shards, a.games)
        Path(a.out).write_text(json.dumps({'games': games, 'at_table_entry': dict(seen.most_common())}, indent=1) + '\n',
                               encoding='utf-8')
        print(f'{games} games, {sum(seen.values())} reached table entry, {len(seen)} signatures')
        return 0
    sigs = json.loads(Path(a.signatures).read_text(encoding='utf-8'))['at_table_entry']
    data, wdl, made = generate(a.tables, sigs, a.positions, a.seed)
    Path(a.out).write_bytes(data)
    print(f'{a.positions} positions ({dict(wdl)}), {len(made)} signatures, most common {made.most_common(5)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
