# SPDX-License-Identifier: GPL-3.0-or-later

"""A fixed-seed permutation of an opening book, for cloud SPRT shards.

The cloud shards index the book by line number (tools/cloud/run_shard.sh),
and the UHO book's first lines are much shorter openings than the rest
(audit-1 finding U-3), so they play a permutation of it instead: line i of
the input goes to the position of its key SHA-256("<seed>:<i>") in sorted
order (i from 0; ties are impossible in practice and broken by i). The
order depends only on the seed and the line count, uses no random-number
generator whose algorithm could change between Python versions, and is
easy to reproduce in any language. Lines are copied byte for byte; a last
line without a newline gets one.

    python3 tools/cloud/shuffle_book.py --seed SEED IN.epd OUT.epd
"""
import argparse
import hashlib
import sys


def permuted(lines, seed):
    keys = sorted((hashlib.sha256(f'{seed}:{i}'.encode()).digest(), i) for i in range(len(lines)))
    return [lines[i] for _, i in keys]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('book')
    ap.add_argument('out')
    a = ap.parse_args(argv)
    with open(a.book, 'rb') as f:
        lines = f.read().splitlines(keepends=True)
    if lines and not lines[-1].endswith(b'\n'):
        lines[-1] += b'\n'
    with open(a.out, 'wb') as f:
        f.writelines(permuted(lines, a.seed))
    return 0


if __name__ == '__main__':
    sys.exit(main())
