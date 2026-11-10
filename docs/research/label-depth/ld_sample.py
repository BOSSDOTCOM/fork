# SPDX-License-Identifier: GPL-3.0-or-later
"""Samples N saved, not-in-check positions (the ones whose label depth the experiment varies) uniformly from an
arm's shards, with a fixed seed, and writes them as FENs for tools/datagen/measure_nodes.py (the median completed
depth of `go nodes`, design section 1.6).

    python -I ld_sample.py ARM_DIR N SEED OUT.epd
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools' / 'datagen'))
import verify_games as V  # noqa: E402


def saved_fens(d):
    for s in sorted(Path(d).glob('*.vf')):
        data = s.read_bytes()
        i = 0
        while i + 32 <= len(data) and int.from_bytes(data[i:i + 8], 'little'):
            board, _ = V.decode_board(data[i:i + 32])
            j = i + 32
            fens = []
            closed = False
            while j + 4 <= len(data):
                code, score = V.u16(data, j), V.i16(data, j + 2)
                j += 4
                if code == 0:
                    closed = True
                    break
                if score != 32767 and not board.is_check():
                    fens.append(board.fen())
                board.push(next(m for m in board.legal_moves if V.code_of(board, m) == code))
            if not closed:
                break
            yield from fens
            i = j


def main(argv):
    d, n, seed, out = argv[0], int(argv[1]), int(argv[2]), argv[3]
    rng = random.Random(seed)
    pick = []
    for k, fen in enumerate(saved_fens(d)):  # reservoir sampling
        if k < n:
            pick.append(fen)
        else:
            r = rng.randrange(k + 1)
            if r < n:
                pick[r] = fen
    Path(out).write_text(''.join(f + '\n' for f in pick), newline='\n')
    print(f'{d}: {k + 1} saved non-check positions, {len(pick)} sampled to {out}')


if __name__ == '__main__':
    main(sys.argv[1:])
