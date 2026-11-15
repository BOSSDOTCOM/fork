# SPDX-License-Identifier: GPL-3.0-or-later

"""Checks the trainer decoder's halfmove clock and castling rights against an independent replay.

The trainer (tools/train, fork-train) decodes each viriformat game into one packed board per position and
carries the position's halfmove clock and castling rights in the board's spare bytes (packed_state in
tools/train/src/main.rs; owner, 2026-11-14). `fork-train dump --state` prints them. This script replays the
same games with its own decoder and python-chess (verify_games.py's decode_board and move codes, written
from the format's README, not from the trainer) and compares, position by position:
- the packed board as the trainer prints it (side to move relative pieces, score and result), so the two
  sides are aligned on the same position;
- the halfmove clock (python-chess's, from the start board's field and each move);
- the castling rights, side to move first (bit 0 its O-O, bit 1 its O-O-O, bit 2 the other side's O-O,
  bit 3 the other side's O-O-O), with the carried flag 0x80.

Give the dump of every position (`fork-train dump --data SHARD --keep-all --state --count N`) as --all and,
optionally, the dump of the training filter's kept positions (the same without --keep-all) as --kept: the
kept set is replayed with the training filter as measured for deliverable 4 (DESIGN.md §5.3: not in check,
the move played neither a capture, en passant included, nor a promotion, |score| below 20,000). The first
--games games of SHARD are checked; each dump must hold at least their positions.

    .venv/Scripts/python.exe -I tools/datagen/check_trainer_state.py SHARD --all ALL.txt [--kept KEPT.txt]
        [--games N]

Exit status 0 when every compared position matches; prints one summary line per dump.
"""
import argparse
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_games import UNSAVED_SCORE, Bad, code_of, decode_board, i16, u16  # noqa: E402

CARRIED = 0x80
MAX_SCORE = 20000  # tools/train/src/main.rs MAX_SCORE (Fork's EvalLimit)


def packed_text(board):
    """The trainer's pieces_text of the position: 'piece:square' by ascending square, side to move relative
    (ranks flipped when Black is to move; piece = 8 for the other side's + type index pawn 0 .. king 5)."""
    flip = board.turn == chess.BLACK
    items = sorted(((sq ^ 56 if flip else sq), (0 if p.color == board.turn else 8) | (p.piece_type - 1))
                   for sq, p in board.piece_map().items())
    return ' '.join(f'{code}:{sq}' for sq, code in items)


def rights_byte(board):
    def side(color):
        return int(board.has_kingside_castling_rights(color)) | int(board.has_queenside_castling_rights(color)) << 1
    return CARRIED | side(board.turn) | side(not board.turn) << 2


def replay(path, games):
    """(line, kept) per position of the first `games` games: line as `dump --state` prints it."""
    data = Path(path).read_bytes()
    out = []
    i = g = 0
    while i < len(data) and g < games:
        board, result = decode_board(data[i:i + 32])
        i += 32
        while True:
            code, score = u16(data, i), i16(data, i + 2)
            i += 4
            if code == 0:
                break
            matches = [m for m in board.legal_moves if code_of(board, m) == code]
            if len(matches) != 1:
                raise Bad(f'{path}: move code {code} matches {len(matches)} legal moves in {board.fen()}')
            move = matches[0]
            white = board.turn == chess.WHITE
            res = result / 2 if white else 1 - result / 2
            line = (f'{packed_text(board)} | {score if white else -score} | {res:g} | '
                    f'{board.halfmove_clock} | {rights_byte(board)}')
            kept = not (board.is_check() or board.is_capture(move) or move.promotion or abs(score) >= MAX_SCORE)
            out.append((line, kept))
            board.push(move)
        g += 1
    return out, g


def compare(name, want, dump_path):
    got = Path(dump_path).read_text().splitlines()
    if len(got) < len(want):
        print(f'{name}: the dump holds {len(got)} lines, fewer than the {len(want)} positions checked')
        return False
    bad = 0
    for k, w in enumerate(want):
        if got[k] != w:
            bad += 1
            if bad <= 5:
                print(f'{name}: position {k} differs\n  replay  {w}\n  trainer {got[k]}')
    clocks = sum(1 for w in want if int(w.split(' | ')[3]) > 0)
    rights = sum(1 for w in want if int(w.split(' | ')[4]) != CARRIED)
    print(f'{name}: {len(want) - bad} of {len(want)} positions match ({bad} differ); '
          f'{clocks} with a nonzero halfmove clock, {rights} with a castling right')
    return bad == 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('shard')
    ap.add_argument('--all', required=True, help='fork-train dump --keep-all --state of SHARD')
    ap.add_argument('--kept', help='fork-train dump --state of SHARD (the training filter)')
    ap.add_argument('--games', type=int, default=500)
    args = ap.parse_args(argv)
    rows, games = replay(args.shard, args.games)
    unsaved = sum(1 for line, _ in rows if abs(int(line.split(' | ')[1])) == UNSAVED_SCORE)
    print(f'{args.shard}: {games} games, {len(rows)} positions ({unsaved} unsaved records)')
    ok = compare('all', [line for line, _ in rows], args.all)
    if args.kept:
        ok = compare('kept', [line for line, kept in rows if kept], args.kept) and ok
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
