# SPDX-License-Identifier: GPL-3.0-or-later

"""Samples the Lichess positions of Fork's search bench (DESIGN.md §5.2).

Reads the Lichess CC0 game export for January 2013 (moves only: comments,
including any [%eval] annotations, are never read into the output; games
with a BOT player are skipped; KB data-policy.md), picks positions with a
fixed seed, and prints them as C++ initializer lines with their category.

Categories, each filled to a fixed count so the set covers them all (owner,
2026-10-24): opening (move 4-12, phase >= 20), middlegame (phase 8-19),
endgame (phase <= 7, at least 4 pieces), check (side to move in check, any
phase). Phase counts knights and bishops 1, rooks 2, queens 4 (24 at the
start), as the bootstrap evaluation does.

    .venv/Scripts/python.exe -I tools/make_bench_positions.py \
        .cache/lichess/lichess_db_standard_rated_2013-01.pgn.zst [--seed 20261024]

The input file: https://database.lichess.org/standard/lichess_db_standard_rated_2013-01.pgn.zst
(17,761,302 bytes, SHA-256 aa40b3671fa3cf1072eb182892cd90b0e1e003a4a5943492f64b77e7f3fd1635,
as published in https://database.lichess.org/standard/sha256sums.txt; checked below).
"""
import argparse
import hashlib
import io
import random
import sys

import chess
import chess.pgn
import zstandard

EXPECTED_SHA256 = 'aa40b3671fa3cf1072eb182892cd90b0e1e003a4a5943492f64b77e7f3fd1635'
TARGET = {'opening': 8, 'middlegame': 16, 'endgame': 10, 'check': 6}
WEIGHT = {chess.KNIGHT: 1, chess.BISHOP: 1, chess.ROOK: 2, chess.QUEEN: 4}


def phase(board):
    return min(24, sum(w * len(board.pieces(t, c)) for t, w in WEIGHT.items() for c in chess.COLORS))


def category(board, fullmove):
    if board.is_check():
        return 'check'
    p = phase(board)
    if 4 <= fullmove <= 12 and p >= 20:
        return 'opening'
    if 8 <= p <= 19:
        return 'middlegame'
    if p <= 7 and len(board.piece_map()) >= 4:
        return 'endgame'
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pgn_zst')
    ap.add_argument('--seed', type=int, default=20261024)
    a = ap.parse_args()
    with open(a.pgn_zst, 'rb') as f:
        data = f.read()
    if hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
        sys.exit('input does not match the published SHA-256')
    text = io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data)), encoding='utf-8')

    rng = random.Random(a.seed)
    chosen = {k: [] for k in TARGET}
    seen = set()
    games = 0
    while any(len(chosen[k]) < n for k, n in TARGET.items()):
        game = chess.pgn.read_game(text)
        if game is None:
            sys.exit('ran out of games before every category was filled')
        games += 1
        if 'BOT' in (game.headers.get('WhiteTitle'), game.headers.get('BlackTitle')):
            continue
        if rng.random() >= 0.02:  # look at about one game in fifty
            continue
        moves = list(game.mainline_moves())
        if len(moves) < 8:
            continue
        ply = rng.randrange(6, len(moves))
        board = game.board()
        for m in moves[:ply]:
            board.push(m)
        if board.is_game_over(claim_draw=True):
            continue
        cat = category(board, board.fullmove_number)
        if cat is None or len(chosen[cat]) >= TARGET[cat]:
            continue
        fen = board.fen()
        if fen in seen:
            continue
        seen.add(fen)
        chosen[cat].append((fen, game.headers.get('Site', '?')))

    print(f'// {sum(TARGET.values())} positions from {games} games read; seed {a.seed}')
    for cat in TARGET:
        for fen, site in chosen[cat]:
            print(f'    {{"{fen}"}},  // {cat}, {site}')
    print('// coverage: ' + ', '.join(f'{k} {len(v)}' for k, v in chosen.items()), file=sys.stderr)


if __name__ == '__main__':
    main()
