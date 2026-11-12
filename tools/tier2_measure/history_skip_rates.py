# SPDX-License-Identifier: GPL-3.0-or-later
"""The history skip's firing-rate measurement (tier 2, T24; the rule in
tools/tier2_measure/history_skip.json, declared before the run).

Reads the site histograms of a stats build (FORK_SEARCH_STATS:
history_skip_site_bins, the ordering score of every quiet move at a site
where the skip could act, by remaining depth, in sign-magnitude bins of 100,
searcher.hpp's skip_score_bin) and prints, for each HistorySkipPerPly P on
the spec's grid, the share of the sites at depths 1 to max_depth whose score
is at or below -P x depth; then the spec's candidates by its rule. SOURCE is
either the stderr of a stats build's `fork bench` (its "stats: history skip
sites at depth D bins:" lines) or a tools/measure/game_replay.py output
folder (the per-search `history_skip_site_dD` histogram deltas of every
game-*.jsonl, summed). With --skips N (the same source with the switch on)
it also prints the actual share N / sites.

    history_skip_rates.py SPEC SOURCE [--skips N]
"""
import argparse
import glob
import json
import os
import re
import sys

BinWidth = 100


def read_bench(path):
    sites = {}
    pattern = re.compile(r'^stats: history skip sites at depth (\d+) bins:((?: \d+)+)\s*$')
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            m = pattern.match(line)
            if m:
                sites[int(m.group(1))] = [int(v) for v in m.group(2).split()]
    return sites


def read_replay(folder):
    sites, skips, searches = {}, 0, 0
    for path in sorted(glob.glob(os.path.join(folder, 'game-*.jsonl'))):
        with open(path, encoding='utf-8') as f:
            for line in f:
                record = json.loads(line)
                searches += 1
                skips += record.get('counters', {}).get('history_skips', 0)
                for name, bins in record.get('hist', {}).items():
                    m = re.fullmatch(r'history_skip_site_d(\d+)', name)
                    if m:
                        d = int(m.group(1))
                        acc = sites.setdefault(d, [0] * len(bins))
                        for i, v in enumerate(bins):
                            acc[i] += v
    return sites, skips, searches


def at_or_below(bins, threshold):
    """The count of values at or below `threshold` (-j x BinWidth, j >= 1).

    Bin layout (skip_score_bin): index n/2 + k holds s in [100k, 100k + 99]
    and index n/2 - 1 - k holds -s in [100k, 100k + 99] (s < 0). So
    s <= -100j <=> -s >= 100j <=> the negative bin k >= j: exact.
    """
    n = len(bins)
    assert threshold < 0 and threshold % BinWidth == 0
    j = -threshold // BinWidth
    return sum(bins[n // 2 - 1 - k] for k in range(j, n // 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('spec')
    ap.add_argument('source')
    ap.add_argument('--skips', type=int)
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding='utf-8'))
    d_max, grid = spec['max_depth'], spec['grid_values']
    if os.path.isdir(a.source):
        sites, skips, searches = read_replay(a.source)
        print(f'{searches} searches; history_skips in their counters: {skips}')
    else:
        sites = read_bench(a.source)
    if not sites:
        sys.exit(f'{a.source}: no history skip site histograms (not a stats build?)')
    total = sum(sum(sites[d]) for d in range(1, d_max + 1))
    print(f'sites at depths 1-{d_max}: {total} (' +
          ', '.join(f'd{d} {sum(sites[d])}' for d in range(1, d_max + 1)) + ')')
    for d in range(1, d_max + 1):
        n = len(sites[d])
        neg = sum(sites[d][:n // 2])
        zero = sites[d][n // 2]  # [0, 99]
        print(f'  d{d}: negative {neg / sum(sites[d]):.4f}, in [0, 99] {zero / sum(sites[d]):.4f}, '
              f'<= -1000 {at_or_below(sites[d], -1000) / sum(sites[d]):.4f}, '
              f'<= -5000 {at_or_below(sites[d], -5000) / sum(sites[d]):.4f}')
    rates = {}
    for p in grid:
        rates[p] = sum(at_or_below(sites[d], -p * d) for d in range(1, d_max + 1)) / total
    for p in grid:
        if p % 500 == 0 or 0.02 < rates[p] < 0.3:
            print(f'P {p:6d}: predicted share {rates[p]:.4f}')
    picks = []
    for t in spec['targets']:
        best = min(grid, key=lambda p: (abs(rates[p] - t), -p))
        if abs(rates[best] - t) > t / 2:
            print(f'target {t}: dropped (nearest P {best}, share {rates[best]:.4f})')
        else:
            print(f'target {t}: P {best}, predicted share {rates[best]:.4f}')
            if best not in picks:
                picks.append(best)
    print('candidates:', picks)
    if a.skips is not None:
        print(f'actual share: {a.skips} / {total} = {a.skips / total:.4f}')


if __name__ == '__main__':
    main()
