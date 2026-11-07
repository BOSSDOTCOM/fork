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

    search_counters_report.py x1 LOG_OR_REPLAY_DIR...
"""
import argparse
import json
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    p1 = sub.add_parser('x1', help='search and accumulator counters')
    p1.add_argument('inputs', nargs='+', type=Path)
    a = parser.parse_args(argv)

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
