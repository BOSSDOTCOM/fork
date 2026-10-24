"""Checks Fork's Phase 2 placeholder move chooser against python-chess.

The rule (DESIGN.md §5.1): a move that mates in one if there is one, else the
best capture by MVV-LVA (most valuable victim, then least valuable
attacker), else the first legal move. Ties go to Fork's generation order,
which python-chess does not share, so this script checks the class of the
chosen move, not the tie-break:

- if mates in one exist, bestmove is one of them;
- else, if captures exist, bestmove is a capture with the best (victim,
  attacker) pair;
- else bestmove is a legal non-capture;
- with no legal move at all, bestmove is "(none)".

Positions come from seeded random games (python-chess picks the moves), so
a run is reproducible. Fork is driven over UCI through pipes, the way a GUI
drives it, with `position fen ...` and `go depth 1`.

    .venv/Scripts/python.exe -I tools/placeholder_check.py build/clang-release/fork [--games N] [--seed S]
"""
import argparse
import random
import subprocess
import sys

import chess

# PieceType order in Fork: pawn < knight < bishop < rook < queen < king.
VALUE = {chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5}


def expected_class(board):
    legal = list(board.legal_moves)
    if not legal:
        return 'none', set()
    mates = set()
    for m in legal:
        board.push(m)
        if board.is_checkmate():
            mates.add(m.uci())
        board.pop()
    if mates:
        return 'mate', mates
    captures = [m for m in legal if board.is_capture(m)]
    if captures:
        def key(m):
            victim = chess.PAWN if board.is_en_passant(m) else board.piece_type_at(m.to_square)
            return (VALUE[victim], -VALUE[board.piece_type_at(m.from_square)])
        best = max(key(m) for m in captures)
        return 'capture', {m.uci() for m in captures if key(m) == best}
    return 'quiet', {m.uci() for m in legal}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('fork')
    ap.add_argument('--games', type=int, default=200)
    ap.add_argument('--seed', type=int, default=20261024)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    proc = subprocess.Popen([args.fork], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def ask(fen):
        proc.stdin.write(f'position fen {fen}\ngo depth 1\n')
        proc.stdin.flush()
        info = None
        for line in proc.stdout:
            line = line.strip()
            if line.startswith('info ') and not line.startswith('info string'):
                info = line
            if line.startswith('bestmove'):
                return line.split()[1], info
        sys.exit('fork closed its output')

    counts = {'mate': 0, 'capture': 0, 'quiet': 0, 'none': 0}
    failures = 0
    positions = 0
    for _ in range(args.games):
        board = chess.Board()
        while True:
            kind, allowed = expected_class(board)
            best, info = ask(board.fen())
            positions += 1
            counts[kind] += 1
            ok = (best == '(none)') if kind == 'none' else best in allowed
            if ok and kind != 'none':
                ok = info is not None and info.endswith(' pv ' + best) and ' score cp 0 ' in info
            if not ok:
                failures += 1
                if failures <= 20:
                    print(f'FAIL {board.fen()}: {kind}, allowed {sorted(allowed)}, got {best} / {info}')
            if kind == 'none' or board.is_game_over(claim_draw=False) or board.ply() >= 300:
                break
            board.push(rng.choice(list(board.legal_moves)))
    proc.stdin.write('quit\n')
    proc.stdin.flush()
    proc.wait(timeout=30)
    print(f'{positions} positions from {args.games} games (seed {args.seed}): '
          f'{counts["mate"]} mate-in-one, {counts["capture"]} capture, {counts["quiet"]} quiet, '
          f'{counts["none"]} no legal move; {failures} failures; fork exit {proc.returncode}')
    return 1 if failures or proc.returncode != 0 else 0


if __name__ == '__main__':
    sys.exit(main())
