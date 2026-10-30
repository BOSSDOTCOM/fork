# SPDX-License-Identifier: GPL-3.0-or-later

"""Fits the bake-off's data-dependent maps (DESIGN.md §5.4) from the
histograms `fork-train stats` prints for the training data (the positions
that pass the training filter), and writes them into the architecture
descriptions with the histograms that produced them:

- the king regions of H-512 and AF-S (KB phase4-designs/design-accuracy.md
  §2.1, the judge's θ = 10%, at most 4): the 32 cells of the mirrored
  own-king square (rank * 4 + file - 4; both perspectives of every
  position), each its own region at first; repeatedly the region with the
  smallest share (ties: the lowest cell) merges into the edge-adjacent
  region with the smallest share (ties: one beside it on the same rank,
  then the lowest cell), until every region holds at least θ and there
  are at most 4; regions numbered by their lowest cell;
- the 8 phase stacks of H-512 and AF-S (design-accuracy.md §2.5), also
  S-512's output buckets (owner, 2026-10-30): game phase 0-24 to a stack by
  the octile its middle falls in, min(7, floor(8 * (share below p + half
  the share of p))).

    fit_maps.py STATS.txt --source NAME [--descriptions tools/nnue]
"""
import argparse
import json
import math
import sys
from pathlib import Path

THETA, MAX_REGIONS = 0.10, 4


def read_stats(path):
    out = {}
    for line in open(path, encoding='utf-8'):
        key, *values = line.split()
        out[key] = [int(v) for v in values]
    return out


def fit_regions(kings, theta=THETA, max_regions=MAX_REGIONS):
    total = sum(kings)
    regions = [{c} for c in range(32)]

    def share(r):
        return sum(kings[c] for c in r) / total

    def neighbours(a, b):
        """(edge-adjacent, along a rank) for two cell sets."""
        along_rank = any(x // 4 == y // 4 and abs(x - y) == 1 for x in a for y in b)
        along_file = any(abs(x - y) == 4 for x in a for y in b)
        return along_rank or along_file, along_rank

    while len(regions) > 1 and (len(regions) > max_regions or min(share(r) for r in regions) < theta):
        small = min(regions, key=lambda r: (share(r), min(r)))
        options = []
        for r in regions:
            if r is small:
                continue
            adjacent, same_rank = neighbours(small, r)
            if adjacent:
                options.append((share(r), not same_rank, min(r), id(r), r))
        target = min(options)[-1]
        target |= small
        regions.remove(small)
    regions.sort(key=min)
    out = [0] * 32
    for i, r in enumerate(regions):
        for c in r:
            out[c] = i
    return out


def fit_phase(phase):
    total = sum(phase)
    out, below = [], 0
    for count in phase:
        out.append(min(7, math.floor(8 * (below + count / 2) / total)))
        below += count
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('stats')
    ap.add_argument('--source', required=True, help='the data the histograms come from (a manifest name)')
    ap.add_argument('--descriptions', default=str(Path(__file__).resolve().parent))
    a = ap.parse_args(argv)
    st = read_stats(a.stats)
    regions, phase = fit_regions(st['kings']), fit_phase(st['phase'])
    fitted = {'source': a.source, 'positions': st['positions'][0], 'kings': st['kings'], 'phase': st['phase'],
              'pieces': st['pieces']}
    for name, maps in (('s512', {'table': phase}), ('h512', {'regions': regions, 'table': phase}),
                       ('afs', {'regions': regions, 'table': phase})):
        path = Path(a.descriptions) / f'{name}.json'
        desc = json.loads(path.read_text(encoding='utf-8'))
        desc.update(maps)
        desc['maps_fitted_on'] = fitted
        path.write_text(json.dumps(desc, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'regions': regions, 'phase_table': phase}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
