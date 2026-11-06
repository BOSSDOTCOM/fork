# SPDX-License-Identifier: GPL-3.0-or-later

"""Measures what a fixed node count buys Fork's search, to set fork_datagen's
--nodes and --hash-mb (DESIGN.md §5.3, constants table).

For each node count, searches every position of an EPD (default: the
datagen test openings, which are the search bench positions) with
`go nodes N` from a cleared table, and reports the median and range of the
last finished depth and the table fill (hashfull, per mille) at the end.

    .venv/Scripts/python.exe -I tools/datagen/measure_nodes.py FORK_EXE [--nodes 1000,2000,...] [--hash-mb 1]
"""
import argparse
import statistics
import subprocess
from pathlib import Path


def search(proc, fen, nodes):
    proc.stdin.write(f'ucinewgame\nposition fen {fen}\ngo nodes {nodes}\n')
    proc.stdin.flush()
    depth = full = 0
    for line in proc.stdout:
        parts = line.split()
        if parts and parts[0] == 'info' and 'depth' in parts and 'score' in parts:
            if 'lowerbound' not in parts and 'upperbound' not in parts:
                depth = int(parts[parts.index('depth') + 1])
            if 'hashfull' in parts:
                full = int(parts[parts.index('hashfull') + 1])
        if parts and parts[0] == 'bestmove':
            return depth, full


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('fork')
    ap.add_argument('--epd', default=str(Path(__file__).resolve().parents[2] / 'tests' / 'datagen_openings.epd'))
    ap.add_argument('--nodes', default='1000,2000,5000,10000,20000,50000')
    ap.add_argument('--hash-mb', type=int, default=1)
    a = ap.parse_args()
    fens = [l.strip() for l in open(a.epd) if l.strip() and not l.startswith('#')]
    proc = subprocess.Popen([str(Path(a.fork).resolve())], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    proc.stdin.write(f'uci\nsetoption name Hash value {a.hash_mb}\nisready\n')
    proc.stdin.flush()
    for line in proc.stdout:
        if line.strip() == 'readyok':
            break
    print(f'{len(fens)} positions, Hash {a.hash_mb} MB')
    print('nodes   depth median [min-max]   hashfull median [max]')
    for n in [int(x) for x in a.nodes.split(',')]:
        results = [search(proc, f, n) for f in fens]
        d = [r[0] for r in results]
        h = [r[1] for r in results]
        print(f'{n:>6}   {statistics.median(d):>5} [{min(d)}-{max(d)}]'
              f'            {statistics.median(h):>5} [{max(h)}]')
    proc.stdin.write('quit\n')
    proc.stdin.flush()
    proc.wait()


if __name__ == '__main__':
    main()
