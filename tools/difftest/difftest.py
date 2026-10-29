# SPDX-License-Identifier: GPL-3.0-or-later

"""Differential test: Fork's move generator against python-chess.

python-chess (GPL-3.0) is an independent move generator used here only as a
test oracle; it is not part of Fork. Random games are played with
python-chess; Fork replays each game through `fork difftest` and must print,
at every ply, exactly what python-chess computes:

    fen | sorted legal moves ('+' = gives check) | in check |
    insufficient material | fifty-move clock reached | repetitions (max 3)

Games start from the CPW suite and special-rule positions, or from random
legal placements, and choose moves with biases toward captures,
promotions (all four pieces) and move reversals (to provoke repetitions).

usage: python -I tools/difftest/difftest.py --fork build/clang-release/fork.exe
           [--positions 2000000] [--workers N] [--seed 1]
Exit status 1 on any mismatch.
"""

import argparse
import multiprocessing as mp
import os
import random
import subprocess
import sys
import time

import chess

# Start positions: the CPW "Perft Results" positions (start, Kiwipete,
# positions 3-6), positions constructed for Fork's special-rule tests
# (tests/suite.hpp), the 218-move position from CPW "Encoding Moves"
# (checked byte for byte on 2026-10-24), and a constructed fifty-move case.
STARTS = [
    chess.STARTING_FEN,
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
    "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
    "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",
    "8/8/8/2k5/3Pp3/8/8/4K3 b - d3 0 1",
    "8/8/8/KPp4r/8/8/8/7k w - c6 0 1",
    "r3k2r/8/8/8/8/8/5q2/R3K2R w KQkq - 0 1",
    "n1n5/PPPk4/8/8/8/8/4Kppp/5N1N b - - 0 1",
    "R6R/3Q4/1Q4Q1/4Q3/2Q4Q/Q4Q2/pp1Q4/kBNN1KB1 w - - 0 1",
    "4k3/8/8/2KPp2q/8/8/8/8 w - e6 0 1",
    "8/1p6/8/8/8/8/6P1/K6k w - - 90 120",
]


def expected(board: chess.Board) -> str:
    moves = sorted(m.uci() + ("+" if board.gives_check(m) else "") for m in board.legal_moves)
    rep = 3 if board.is_repetition(3) else 2 if board.is_repetition(2) else 1
    return "|".join([
        board.fen(),
        " ".join(moves),
        str(int(board.is_check())),
        str(int(board.is_insufficient_material())),
        str(int(board.halfmove_clock >= 100)),
        str(rep),
    ])


def random_position(rng: random.Random) -> str:
    """A random legal placement: two kings plus 0-14 other pieces."""
    kinds = "PNBRQpnbrq"
    while True:
        board = chess.Board(None)
        squares = rng.sample(range(64), 2 + rng.randint(0, 14))
        board.set_piece_at(squares[0], chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(squares[1], chess.Piece(chess.KING, chess.BLACK))
        for sq in squares[2:]:
            piece = chess.Piece.from_symbol(rng.choice(kinds))
            if piece.piece_type == chess.PAWN and chess.square_rank(sq) in (0, 7):
                continue
            board.set_piece_at(sq, piece)
        board.turn = rng.random() < 0.5
        board.halfmove_clock = rng.choice([0, 0, 0, 50, 95, 99])
        if board.is_valid():
            return board.fen()


def choose(board: chess.Board, legal, rng: random.Random):
    r = rng.random()
    if r < 0.25:
        forcing = [m for m in legal if board.is_capture(m) or m.promotion]
        if forcing:
            return rng.choice(forcing)
    elif r < 0.40 and len(board.move_stack) >= 2:
        prev = board.move_stack[-2]
        back = chess.Move(prev.to_square, prev.from_square)
        if back in legal:
            return back
    return rng.choice(legal)


def worker(args):
    fork_path, seed, quota = args
    rng = random.Random(seed)
    proc = subprocess.Popen([fork_path, "difftest"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, bufsize=1)
    positions = games = 0
    mismatches = []
    try:
        while positions < quota and len(mismatches) < 5:
            start = random_position(rng) if rng.random() < 0.3 else rng.choice(STARTS)
            board = chess.Board(start)
            want = [expected(board)]
            moves = []
            for _ in range(rng.randint(10, 400)):
                legal = list(board.legal_moves)
                if not legal:
                    break
                m = choose(board, legal, rng)
                board.push(m)
                moves.append(m.uci())
                want.append(expected(board))
            proc.stdin.write(start + "|" + " ".join(moves) + "\n")
            got = []
            while True:
                line = proc.stdout.readline()
                if not line:
                    raise RuntimeError("fork exited unexpectedly")
                line = line.rstrip("\r\n")
                if line == "end":
                    break
                got.append(line)
            games += 1
            positions += len(want)
            if got != want:
                for ply in range(max(len(got), len(want))):
                    g = got[ply] if ply < len(got) else "<missing>"
                    w = want[ply] if ply < len(want) else "<missing>"
                    if g != w:
                        mismatches.append({"start": start, "moves": moves[:ply], "ply": ply,
                                           "fork": g, "python-chess": w})
                        break
    finally:
        proc.stdin.close()
        proc.wait(timeout=30)
    return positions, games, mismatches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fork", required=True)
    ap.add_argument("--positions", type=int, default=2_000_000)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 2))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--chunks", type=int, default=0, help="work units (default 8 per worker)")
    a = ap.parse_args()
    a.fork = os.path.abspath(a.fork)

    chunks = a.chunks or a.workers * 8
    jobs = [(a.fork, a.seed * 1_000_003 + i, a.positions // chunks + 1) for i in range(chunks)]
    start = time.time()
    total_pos = total_games = 0
    mismatches = []
    with mp.Pool(a.workers) as pool:
        for i, (p, g, mm) in enumerate(pool.imap_unordered(worker, jobs), 1):
            total_pos += p
            total_games += g
            mismatches += mm
            print(f"  chunk {i}/{chunks}: {total_pos:,} positions, {total_games:,} games, "
                  f"{len(mismatches)} mismatches, {time.time() - start:.0f} s", flush=True)
    print(f"python-chess {chess.__version__}: {total_pos:,} positions in {total_games:,} games, "
          f"{len(mismatches)} mismatches, {time.time() - start:.0f} s")
    for m in mismatches[:10]:
        print("MISMATCH", m)
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
