# SPDX-License-Identifier: GPL-3.0-or-later

"""The gauntlet's reserved UHO openings (owner, 2026-11-13: a gauntlet on
UHO lines that no SPRT uses): 200 consecutive lines near the end of the
SPRTs' shuffled book, UHO_Lichess_4852_v1.shuffled-20261027.epd
(tools/cloud/fetch_tools.sh fetches it and checks its SHA-256).

    python3 -I tools/gauntlet/reserved_openings.py SHUFFLED OUT

writes lines FIRST to FIRST + COUNT - 1 of SHUFFLED to OUT and checks the
book's line count and the extract's SHA-256; any difference is an error
(exit 1) and OUT is not left behind.

Why these lines. The SPRT shards play the shuffled book from its start:
shard I of stage S plays lines 1 + (S * N + I) * R onwards
(tools/cloud/run_shard.sh; N shards, R rounds per shard), 800 lines a stage
at STC (16 x 50) and 832 at LTC (16 x 52); the anchor check's book uho and
its match play lines 1-200. On 2026-11-13 the 7,456 shard results under
~/fork-data (sprt, cloud) recorded no line past 17,600 (stage 21), and the
job ledger's highest stage is 20; reaching line FIRST would take stage
3,163 or later. The local SPRTs of tools/sprt.sh (Phases 2-3) drew from the
unshuffled book in random order: every position (first four FEN fields) in
FIRST..LAST was checked against the FEN tags of all 25 of their PGNs
(43,594 games) and against the shuffled book's first 30,000 lines (a
position can occur on more than one line of the book), with no match; the
window is the last block of 200 near the end of the book with none (the
1,000 last lines held 8 such positions). The 200 lines were derived from
the unshuffled book by streaming shuffle_book.py's keys (as derive() below
does; tools/gauntlet/test_reserved_openings.py checks it against the whole
permutation), the method checked by the same derivation reproducing, opening for
opening, the lines 1-200 that the anchor check of run 43109946231 played.
The SHA-256 below is of that derivation's output; the runner's extract from
the real shuffled book must equal it, a second, independent check.
"""
import hashlib
import heapq
import sys
from pathlib import Path

BOOK = 'UHO_Lichess_4852_v1.shuffled-20261027.epd'
BOOK_LINES = 2632036  # tools/cloud/fetch_tools.sh: 2,632,036 positions
FIRST = 2631816
COUNT = 200
SHA256 = '1bd6a0360e066f5c87a53748cffbcbb509f6090a8cef3ed6e67f3cfa8d407df8'


def extract(shuffled, out, first=FIRST, count=COUNT, book_lines=BOOK_LINES, sha256=SHA256):
    """Lines first..first+count-1 (counted from 1) of shuffled into out, checked; raises ValueError."""
    picked, n = [], 0
    with open(shuffled, 'rb') as f:
        for n, line in enumerate(f, 1):
            if first <= n < first + count:
                picked.append(line)
    if n != book_lines:
        raise ValueError(f'{shuffled} has {n} lines, not {book_lines}')
    if len(picked) != count:
        raise ValueError(f'{shuffled}: lines {first}-{first + count - 1} are not all there')
    data = b''.join(picked)
    got = hashlib.sha256(data).hexdigest()
    if got != sha256:
        raise ValueError(f'lines {first}-{first + count - 1} of {shuffled}: SHA-256 {got}, not {sha256}')
    Path(out).write_bytes(data)


def derive(book, seed, first, count):
    """The lines first..first+count-1 (from 1) of shuffle_book.py's permutation of book, computed by
    streaming its keys SHA-256("<seed>:<i>") (ties by i) and keeping only the n - first + 1 largest, never
    the whole permutation: the independent derivation of the reserved lines (cheap when first is near the end)."""
    with open(book, 'rb') as f:
        n = sum(1 for _ in f)
    keep = n - first + 1  # the positions first..n hold the keep largest keys, in ascending order
    if first < 1 or count < 1 or count > keep:
        raise ValueError('first and count must lie inside the book')
    largest = heapq.nlargest(keep, ((hashlib.sha256(f'{seed}:{i}'.encode()).digest(), i) for i in range(n)))
    window = [i for _, i in sorted(largest)[:count]]
    want, lines = set(window), {}
    with open(book, 'rb') as f:
        for i, line in enumerate(f):
            if i in want:
                lines[i] = line if line.endswith(b'\n') else line + b'\n'
    return b''.join(lines[i] for i in window)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        sys.exit(__doc__)
    try:
        extract(argv[0], argv[1])
    except (OSError, ValueError) as e:
        print(f'reserved_openings.py: {e}', file=sys.stderr)
        return 1
    print(f'reserved_openings.py: lines {FIRST}-{FIRST + COUNT - 1} of {BOOK} in {argv[1]} (SHA-256 checked)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
