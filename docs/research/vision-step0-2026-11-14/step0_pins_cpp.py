# SPDX-License-Identifier: GPL-3.0-or-later
"""Vision step 0 (ideas.md 185): the pin and discoverer finders (step0_common) against Fork's own
Position::pinned() and Position::discoverers() (src/core/position.hpp, lone_shields), on every --every-th position
of a dump. Each position is given to Fork twice: with the mover (White) to move, so pinned() and discoverers() are
the mover's, and with the opponent to move, so they are the opponent's (the dump holds no position with the mover in
check, so the second FEN is legal too). CHECKER is a scratch program (pins.cpp, beside this script: it
reads FENs and prints both bitboards in hex) built against build/clang-release/libforkcore.a.

    step0_pins_cpp.py DUMP CHECKER [--every 50] [--limit N]
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import step0_common as sc  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('dump')
    ap.add_argument('checker')
    ap.add_argument('--every', type=int, default=50)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args(argv)
    positions, _ = sc.read_dump(a.dump, a.limit)
    idx = list(range(0, len(positions), a.every))
    fens, want = [], []
    for i in idx:
        b = sc.board_of(positions[i])
        cells = sc.position_cells(b)
        place = b.board_fen()
        fens += [f'{place} w - - 0 1', f'{place} b - - 0 1']
        for side in (0, 1):
            pin = sum(1 << (c % 64) for c in cells['pin'] if c // 64 // 5 == side)
            disc = sum(1 << (c % 64) for c in cells['disc'] if c // 64 // 6 == side)
            want.append((pin, disc))
    out = subprocess.run([a.checker], input='\n'.join(fens) + '\n', capture_output=True, text=True,
                         check=True).stdout.split('\n')
    got = []
    for line in out[:len(fens)]:
        p, d = line.split()
        got.append((int(p, 16), int(d, 16)))
    pin_bad = sum(g[0] != w[0] for g, w in zip(got, want))
    disc_bad = sum(g[1] != w[1] for g, w in zip(got, want))
    report = {'positions': len(idx), 'fens': len(fens), 'pinned_mismatch': pin_bad, 'discoverers_mismatch': disc_bad,
              'pinned_nonzero': sum(1 for g in got if g[0]), 'discoverers_nonzero': sum(1 for g in got if g[1])}
    print(json.dumps(report))


if __name__ == '__main__':
    main()
