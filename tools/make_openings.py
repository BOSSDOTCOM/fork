"""Writes an EPD file of opening positions for Fork's self-play test runs.

Each position comes from a random game of --plies plies played by
python-chess (uniformly random legal moves, seeded, so the file is
reproducible). Positions that are already over, or repeat an earlier one,
are skipped. These are test fixtures only: Fork's Phase 2 placeholder is
deterministic, so self-play from one start position would repeat a single
game. No engine chose any move.

    .venv/Scripts/python.exe -I tools/make_openings.py OUT.epd [--count 200] [--plies 8] [--seed 20261024]
"""
import argparse
import random

import chess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--count', type=int, default=200)
    ap.add_argument('--plies', type=int, default=8)
    ap.add_argument('--seed', type=int, default=20261024)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    seen = set()
    with open(a.out, 'w', newline='\n') as f:
        while len(seen) < a.count:
            board = chess.Board()
            for _ in range(a.plies):
                board.push(rng.choice(list(board.legal_moves)))
                if board.is_game_over():
                    break
            epd = board.epd()
            if board.is_game_over() or epd in seen:
                continue
            seen.add(epd)
            f.write(epd + '\n')
    print(f'{len(seen)} positions ({a.plies} random plies, seed {a.seed}) -> {a.out}')


if __name__ == '__main__':
    main()
