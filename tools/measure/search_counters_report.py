# SPDX-License-Identifier: GPL-3.0-or-later
"""X1 and X2 of Phase 4 step 1 (DESIGN.md §5.7): reports from a stats
build's counters.

X1 (search and accumulator counters): evaluations per node, the
quiescence share of nodes and of evaluations, TT-eval hits, network
refreshes per 1,000 updates, rows per update, plies walked per evaluation,
the link-update share and the pawn-move share of moves. Input: a stats
build's stderr with FORK_STATS_REPORT set (the last, cumulative
`search_counters` line counts: e.g. `fork bench`), or a game_replay.py
output folder (the per-search deltas are summed).

Declared readings (phase-c-synthesis.md §2.4; phase-a-evidence.md M4),
fixed before the data were seen: 0.75-0.85 evaluations per node was
predicted (refuted under 0.6), and only a high value leaves room for
evaluation skipping; quiescence evaluations under 30% of all evaluations
would drop the quiescence eval-avoidance ideas.

X2 (in-game history magnitudes): from a game_replay.py run with counter
dumps, per game-move band (1-15, 16-29, 30-60, 61+) and for bench (a stats
build's `FORK_STATS_REPORT=1 fork bench` stderr): the share of LMR sites
where the LMR history term of branch sprt/lmr-history (the base reduction
less the ordering score / 24,000) would act (|score| >= 24,000), on which
side, where it would change the reduction, and the quantiles of the
ordering score and of the butterfly, reply, follow and late-capture take
entries (bin midpoints, so within half a bin: 125 for the tables, 250 for
the score). 95% intervals: a bootstrap over games (2,000 rounds, seed
20261107).

Declared readings (phase-c-synthesis.md §2.4, B14 §3.7, phase-a-evidence.md
M1), fixed before the data were seen: an in-game share at moves 30-60 at
least 5x the bench's confirms history persistence (then R16's per-go
scaling comes before R20 and R29); within 2x of the bench's attributes the
term's -10.8 Elo to its cost or asymmetry (then its nps is measured); B14
predicted that at least 85% of the term's firings were on the reduce-more
side.

Idea 59 step 1 (the Boundary Refiner's gate): at evaluation sites, the gap
between the static evaluation and the nearest finite bound of the node's
alpha-beta window (a bound in the mate or tablebase band does not count;
a site with none is "infinite"), separately for main-search and quiescence
evaluations, computed ones (the network runs) and ones reused from the TT
entry. For margins of 10, 25, 50 and 100 cp: the share of evaluations
within the margin, and the call rate per node (those evaluations over all
nodes; X1's evaluations per node times the share). Main-search evaluations
are also split by remaining depth (1, 2, 3-4, 5-7, 8+). A measurement only:
no decision rule was declared (the owner's request, 2026-11-07, sets the
two gate margins from it later).

    search_counters_report.py x1 LOG_OR_REPLAY_DIR...
    search_counters_report.py x2 REPLAY_DIR --bench BENCH_STDERR [--json OUT]
    search_counters_report.py gap LOG_OR_REPLAY_DIR... [--json OUT]
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine_lines  # noqa: E402


def x1_ratios(c):
    """X1's numbers from summed counters (a dict of counter name -> count)."""
    def ratio(a, b):
        return a / b if b else 0.0

    quiesce = c['quiesce_nodes_pv'] + c['quiesce_nodes_non_pv']
    nodes = c['root_nodes'] + c['main_nodes'] + quiesce
    evals = c['evals_main'] + c['evals_quiesce'] + c['evals_horizon']
    out = {
        'nodes': nodes,
        'evaluations_per_node': ratio(evals, nodes),
        'main_evaluations_per_node': ratio(c['evals_main'], nodes),
        'quiescence_evaluations_per_node': ratio(c['evals_quiesce'], nodes),
        'tt_eval_hit_rate_main': ratio(c['tt_eval_hits_main'], c['tt_eval_hits_main'] + c['evals_main']),
        'tt_eval_hit_rate_quiescence': ratio(c['tt_eval_hits_quiesce'], c['tt_eval_hits_quiesce'] + c['evals_quiesce']),
        'quiescence_share_of_nodes': ratio(quiesce, nodes),
        'quiescence_share_of_evaluations': ratio(c['evals_quiesce'], evals),
        'pawn_share_of_makes': ratio(c['pawn_makes'], c['makes']),
        'pawn_share_of_quiescence_makes_total': ratio(c['pawn_makes_quiesce'], c['pawn_makes']),
    }
    if 'perspective_updates' in c:
        updates = c['perspective_updates']
        out.update({
            'rows_per_update': ratio(c['update_rows'], updates),
            'refreshes_per_1000_updates': 1000 * ratio(c['frame_refreshes'] + c['root_refreshes'], updates),
            'frame_refreshes_per_1000_updates': 1000 * ratio(c['frame_refreshes'], updates),
            'plies_walked_per_evaluation': ratio(c['walked_plies'], c['evaluations']),
            'link_update_share': ratio(c['link_updates'], updates),
            'evaluated_share_of_pushes': ratio(c['evaluations'], c['move_pushes'] + c['null_pushes']),
        })
    return out


def history_share_above(bins, threshold, width):
    """Sign-magnitude bins (searcher.hpp's table_value_bin / order_score_bin):
    the counts at score >= threshold and at score <= -threshold, and the
    total. `threshold` must be a multiple of `width` (the bins split there)."""
    if threshold % width:
        raise ValueError('the threshold must be a multiple of the bin width')
    half = len(bins) // 2
    above = sum(bins[half + threshold // width:])
    below = sum(bins[:half - threshold // width])
    return above, below, sum(bins)


def move_band(move_number):
    """The game-move band of X2's report."""
    return '1-15' if move_number <= 15 else '16-29' if move_number <= 29 else '30-60' if move_number <= 60 else '61+'


def x2_report(records, bench, threshold=24000, rounds=2000, seed=20261107):
    """X2's numbers: per band (and 'all') and for bench (summed counters with
    'hist' bins, or None). Returns a dict."""
    tables = {'lmr_order': 500, 'lmr_quiet': 250, 'lmr_reply': 250, 'lmr_follow': 250, 'late_take': 250}

    def quantiles(bins, width):
        total = sum(bins)
        half = len(bins) // 2
        out = {}
        for q in (0.05, 0.25, 0.5, 0.75, 0.95):
            seen = 0
            for i, n in enumerate(bins):
                seen += n
                if total and seen >= q * total:
                    lo = (i - half) * width if i >= half else -((half - i) * width - 1)
                    out[f'p{int(q * 100)}'] = lo + (width - 1) / 2  # the bin's midpoint
                    break
        return out

    def summarise(counters, hist, per_game=None):
        sites = counters.get('lmr_rule_sites', 0)
        fires = counters.get('lmr_history_fire_less', 0) + counters.get('lmr_history_fire_more', 0)
        row = {
            'lmr_sites': sites,
            'term_acts_share': fires / sites if sites else 0.0,
            'reduce_less_share': counters.get('lmr_history_fire_less', 0) / sites if sites else 0.0,
            'reduce_more_share': counters.get('lmr_history_fire_more', 0) / sites if sites else 0.0,
            'reduce_more_share_of_firings': counters.get('lmr_history_fire_more', 0) / fires if fires else None,
            'changes_share': counters.get('lmr_history_changes', 0) / sites if sites else 0.0,
            'late_capture_sites': counters.get('late_capture_sites', 0),
        }
        if 'lmr_order' in hist:
            above, below, total = history_share_above(hist['lmr_order'], threshold, 500)
            row['order_share_above_threshold'] = (above + below) / total if total else 0.0
        for name, width in tables.items():
            if name in hist:
                row[name + '_quantiles'] = quantiles(hist[name], width)
        if per_game:
            games = list(per_game.values())
            rng = random.Random(seed)
            shares = []
            for _ in range(rounds):
                pick = [games[rng.randrange(len(games))] for _ in games]
                s_sites = sum(g[0] for g in pick)
                shares.append(sum(g[1] for g in pick) / s_sites if s_sites else 0.0)
            shares.sort()
            row['term_acts_share_ci95'] = (shares[int(0.025 * rounds)], shares[int(0.975 * rounds) - 1])
            row['games'] = len(games)
        return row

    groups = {}
    for record in records:
        if 'counters' not in record:
            continue
        for band in (move_band(record['move_number']), 'all'):
            g = groups.setdefault(band, {'counters': {}, 'hist': {}, 'per_game': {}, 'searches': 0})
            g['searches'] += 1
            for k, v in record['counters'].items():
                g['counters'][k] = g['counters'].get(k, 0) + v
            for k, v in record.get('hist', {}).items():
                acc = g['hist'].setdefault(k, [0] * len(v))
                for i, n in enumerate(v):
                    acc[i] += n
            c = record['counters']
            pg = g['per_game'].setdefault(record['game'], [0, 0])
            pg[0] += c.get('lmr_rule_sites', 0)
            pg[1] += c.get('lmr_history_fire_less', 0) + c.get('lmr_history_fire_more', 0)
    out = {'bands': {}}
    for band in ('1-15', '16-29', '30-60', '61+', 'all'):
        if band in groups:
            row = summarise(groups[band]['counters'], groups[band]['hist'], groups[band]['per_game'])
            row['searches'] = groups[band]['searches']
            out['bands'][band] = row
    if bench:
        out['bench'] = summarise(bench['counters'], bench['hist'])
        b = out['bench']['term_acts_share']
        if '30-60' in out['bands']:
            game = out['bands']['30-60']['term_acts_share']
            out['ratio_30_60_to_bench'] = game / b if b else float('inf')
    return out


def gap_bin_edges(count=317):
    """The window-gap bins (searcher.hpp's window_gap_bin): [(low, high)], 1 cp
    each up to 255, 64 cp up to 4,095, then one open bin (high None)."""
    edges = [(g, g) for g in range(256)]
    edges += [(256 + 64 * i, 256 + 64 * i + 63) for i in range(count - 257)]
    edges.append((256 + 64 * (count - 257), None))
    return edges


def gap_share_within(bins, infinite, margin):
    """(evaluations with a gap of at most `margin` cp, all evaluations of the
    histogram, infinite windows included). `margin` must be at most 255."""
    if margin > 255:
        raise ValueError('margins above 255 cp fall in the coarse bins')
    return sum(bins[:margin + 1]), sum(bins) + infinite


def window_gap_report(counters, hist, margins=(10, 25, 50, 100)):
    """Idea 59 step 1's numbers from summed counters and histograms."""
    nodes = counters['root_nodes'] + counters['main_nodes'] + counters['quiesce_nodes_pv'] + \
        counters['quiesce_nodes_non_pv']
    edges = gap_bin_edges(len(hist['eval_gap_main']))

    def describe(bins, infinite, one_sided=None):
        total = sum(bins) + infinite
        row = {'evaluations': total, 'per_node': total / nodes if nodes else 0.0,
               'infinite_share': infinite / total if total else 0.0}
        if one_sided is not None:
            row['one_sided_share'] = one_sided / total if total else 0.0
        finite = sum(bins)
        seen = 0
        for q in (0.25, 0.5, 0.75):
            for (low, high), n in zip(edges, bins):
                if finite and seen + n >= q * finite:
                    row[f'gap_p{int(q * 100)}'] = low if high is None else (low + high) / 2
                    break
                seen += n
            seen = 0
        for m in margins:
            within, all_evals = gap_share_within(bins, infinite, m)
            row[f'within_{m}'] = {'share': within / all_evals if all_evals else 0.0,
                                  'call_rate_per_node': within / nodes if nodes else 0.0}
        return row

    out = {'nodes': nodes,
           'main': describe(hist['eval_gap_main'], counters['eval_gap_main_infinite'],
                            counters['eval_gap_main_one_sided']),
           'quiescence': describe(hist['eval_gap_quiesce'], counters['eval_gap_quiesce_infinite'],
                                  counters['eval_gap_quiesce_one_sided']),
           'main_reused': describe(hist['eval_gap_main_reuse'], counters['eval_gap_main_reuse_infinite']),
           'quiescence_reused': describe(hist['eval_gap_quiesce_reuse'], counters['eval_gap_quiesce_reuse_infinite']),
           'main_by_depth': {}}
    infinite_bands = hist.get('eval_gap_band_infinite', [0] * 5)
    for i, band in enumerate(('1', '2', '3-4', '5-7', '8+')):
        name = 'eval_gap_band_' + band.replace('-', '_').replace('+', '_plus')
        if name in hist:
            out['main_by_depth'][band] = describe(hist[name], infinite_bands[i])
    out['combined_call_rate_per_node'] = {
        m: out['main'][f'within_{m}']['call_rate_per_node'] + out['quiescence'][f'within_{m}']['call_rate_per_node']
        for m in margins}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    p1 = sub.add_parser('x1', help='search and accumulator counters')
    p1.add_argument('inputs', nargs='+', type=Path)
    p2 = sub.add_parser('x2', help='in-game history magnitudes and the LMR history term')
    p2.add_argument('replay', type=Path)
    p2.add_argument('--bench', type=Path, required=True, help='stderr of FORK_STATS_REPORT=1 fork bench')
    p2.add_argument('--json', type=Path, default=None)
    p3 = sub.add_parser('gap', help="idea 59 step 1: evaluations' gaps to the window")
    p3.add_argument('inputs', nargs='+', type=Path)
    p3.add_argument('--json', type=Path, default=None)
    a = parser.parse_args(argv)

    if a.command == 'gap':
        results = {}
        for path in a.inputs:
            counters, hist = {}, {}
            if path.is_dir():
                for f in sorted(path.glob('game-*.jsonl')):
                    for line in f.read_text(encoding='utf-8').splitlines():
                        record = json.loads(line)
                        for k, v in record['counters'].items():
                            counters[k] = counters.get(k, 0) + v
                        for k, v in record.get('hist', {}).items():
                            acc = hist.setdefault(k, [0] * len(v))
                            for i, n in enumerate(v):
                                acc[i] += n
            else:
                for number, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
                    try:
                        if line.startswith('search_counters '):
                            counters = engine_lines.parse_counter_line(line)
                        elif line.startswith('search_hist '):
                            name, bins = engine_lines.parse_hist_line(line)
                            hist[name] = bins
                    except ValueError as e:
                        raise SystemExit(f'{path}:{number}: {e}')
            results[str(path.name)] = window_gap_report(counters, hist)
        text = json.dumps(results, indent=1)
        if a.json:
            a.json.write_text(text + '\n', encoding='utf-8')
        print(text)
        return 0

    if a.command == 'x2':
        records = []
        for f in sorted(a.replay.glob('game-*.jsonl')):
            records.extend(json.loads(line) for line in f.read_text(encoding='utf-8').splitlines())
        bench = {'counters': {}, 'hist': {}}
        for number, line in enumerate(a.bench.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            try:
                if line.startswith('search_counters '):
                    bench['counters'] = engine_lines.parse_counter_line(line)
                elif line.startswith('search_hist '):
                    name, bins = engine_lines.parse_hist_line(line)
                    bench['hist'][name] = bins
            except ValueError as e:
                raise SystemExit(f'{a.bench}:{number}: {e}')
        result = x2_report(records, bench if bench['counters'] else None)
        if a.json:
            a.json.write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
        print(json.dumps(result, indent=1))
        return 0

    if a.command == 'x1':
        for path in a.inputs:
            totals = {}
            if path.is_dir():
                records = 0
                for f in sorted(path.glob('*.jsonl')):
                    for line in f.read_text(encoding='utf-8').splitlines():
                        record = json.loads(line)
                        for name, value in record['counters'].items():
                            totals[name] = totals.get(name, 0) + value
                        records += 1
                label = f'{path} ({records} searches)'
            else:
                for number, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
                    if line.startswith('search_counters '):
                        try:
                            totals = engine_lines.parse_counter_line(line)
                        except ValueError as e:
                            raise SystemExit(f'{path}:{number}: {e}')
                label = str(path)
            if not totals:
                raise SystemExit(f'{path}: no search_counters data')
            print(f'X1: {label}')
            for name, value in x1_ratios(totals).items():
                print(f'  {name:40s} {value:.4f}' if isinstance(value, float) else f'  {name:40s} {value}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
