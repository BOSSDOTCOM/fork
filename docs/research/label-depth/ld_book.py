# SPDX-License-Identifier: GPL-3.0-or-later
"""Writes the label-depth arms' openings file: the openings that a full book gives fork_datagen's first K games
for one seed, in an order that gives game g < K the same opening from the K-line file.

fork_datagen (src/datagen/datagen_main.cpp) starts game g from book[perm[g mod N]], perm being a Fisher-Yates
shuffle of the N openings driven by splitmix_next from state = --seed (for i = N-1 down to 1: swap perm[i] and
perm[next % (i + 1)]). With a K-line file the shuffle runs over K instead, as perm_K. This file is S with
S[perm_K[g]] = book[perm_N[g]] for g < K, so games 0 .. K-1 open exactly as with the full book (checked by
comparing fork_datagen's shards byte for byte, docs/research/label-depth/probe.md). The reason: every
fork_datagen process keeps its whole book in memory (about 1.4 GB for the 13.9 M-line lichess-2026-09.epd), and
the three arms run as three processes in a 5.9 GB WSL machine.

    python3 -I ld_book.py BOOK SEED K OUT
"""
import sys

MASK = (1 << 64) - 1


def finalize(z):
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return z ^ (z >> 31)


def shuffle(n, seed):
    """fork_datagen's opening order for an n-line book (src/core/splitmix.hpp splitmix_next)."""
    from array import array
    order = array('I', range(n))
    state = seed
    for i in range(n - 1, 0, -1):
        state = (state + 0x9E3779B97F4A7C15) & MASK
        j = finalize(state) % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


def openings(path):
    """The book's openings as fork_datagen reads them: '\\r' stripped, blank lines and '#' comments skipped."""
    with open(path, 'rb') as f:
        for raw in f:
            line = raw.rstrip(b'\n')
            if line.endswith(b'\r'):
                line = line[:-1]
            if not line or line.startswith(b'#'):
                continue
            yield line


def main(argv):
    book, seed, k, out = argv[0], int(argv[1]), int(argv[2]), argv[3]
    n = sum(1 for _ in openings(book))
    if k > n:
        sys.exit(f'K {k} is larger than the book ({n})')
    full = shuffle(n, seed)
    sub = shuffle(k, seed)
    want = {}  # book index -> the game indices g < K that open from it (a book index is used once in a perm)
    for g in range(k):
        want[full[g]] = g
    lines = [None] * k
    for idx, line in enumerate(openings(book)):
        g = want.get(idx)
        if g is not None:
            lines[sub[g]] = line
    assert all(x is not None for x in lines)
    with open(out, 'wb') as f:
        for line in lines:
            f.write(line + b'\n')
    print(f'{book}: {n} openings; wrote {k} to {out} for seed {seed}')


if __name__ == '__main__':
    main(sys.argv[1:])
