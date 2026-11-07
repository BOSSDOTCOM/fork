# SPDX-License-Identifier: GPL-3.0-or-later
"""The stats build's stderr line formats (DESIGN.md §5.7, Phase 4 step 1).

A stats build (FORK_SEARCH_STATS) prints, when asked by environment
variables read at start-up (src/search/searcher.cpp):

- FORK_STATS_REPORT: after each search, `search_counters name=value ...`
  (every scalar counter and, with a network, the feature stack's tally;
  cumulative per process) and `search_hist NAME v0 v1 ...` lines (cumulative
  histogram bins);
- FORK_ITERATION_TRACE: per finished iteration,
  `iteration_trace depth|best|share|share_all|runner_up|nodes_last_pass|nodes_iteration|score|passes|root_moves|seldepth`;
- FORK_PRUNE_LEDGER: per sampled prune candidate,
  `prune_ledger rfp|depth|ply|excess|static_excess|margin|tt_bound|tt_depth|swing|phase|fired|arm_minus_beta|arm_nodes|arm_mate`
  or
  `prune_ledger futility|depth|ply|deficit|static_deficit|margin|tt_bound|tt_depth|swing|phase|fired|on_minus_beta|off_minus_beta|on_nodes|off_nodes|arm_mate`;
- FORK_EVAL_SITES=N,M: every Nth main-search and every Mth quiescence
  evaluation site,
  `eval_site kind|reused|alpha|beta|eval|prune_eval|depth|ply|parent_eval|tt_bound|tt_depth|captured|on_pv|FEN`
  (kind 0 main search, 1 quiescence; the FEN last, with its spaces).

Each parser raises ValueError on a malformed line; callers add the line's
number to the message.
"""


def parse_counter_line(line):
    """`search_counters a=1 b=2` -> {'a': 1, 'b': 2}."""
    words = line.split()
    if not words or words[0] != 'search_counters':
        raise ValueError(f'not a counter line: {line[:60]!r}')
    out = {}
    for word in words[1:]:
        name, sep, value = word.partition('=')
        if not sep or not name or name in out:
            raise ValueError(f'bad counter field {word!r}')
        out[name] = int(value)
    if not out:
        raise ValueError('a counter line without counters')
    return out


def parse_hist_line(line):
    """`search_hist NAME 1 2 3` -> ('NAME', [1, 2, 3])."""
    words = line.split()
    if len(words) < 3 or words[0] != 'search_hist':
        raise ValueError(f'not a histogram line: {line[:60]!r}')
    return words[1], [int(w) for w in words[2:]]


def parse_iteration_line(line):
    """One `iteration_trace` line -> a dict of its fields (all integers)."""
    names = ('depth', 'best', 'share', 'share_all', 'runner_up', 'nodes_last_pass', 'nodes_iteration', 'score',
             'passes', 'root_moves', 'seldepth')
    words = line.split()
    if len(words) != 2 or words[0] != 'iteration_trace':
        raise ValueError(f'not an iteration_trace line: {line[:60]!r}')
    values = words[1].split('|')
    if len(values) != len(names):
        raise ValueError(f'iteration_trace: {len(values)} fields, expected {len(names)}')
    return dict(zip(names, (int(v) for v in values)))


def parse_ledger_line(line):
    """One `prune_ledger` line -> a dict with 'technique' and that technique's fields."""
    layouts = {
        'rfp': ('depth', 'ply', 'excess', 'static_excess', 'margin', 'tt_bound', 'tt_depth', 'swing', 'phase', 'fired',
                'arm_minus_beta', 'arm_nodes', 'arm_mate'),
        'futility': ('depth', 'ply', 'deficit', 'static_deficit', 'margin', 'tt_bound', 'tt_depth', 'swing', 'phase',
                     'fired', 'on_minus_beta', 'off_minus_beta', 'on_nodes', 'off_nodes', 'arm_mate'),
    }
    words = line.split()
    if len(words) != 2 or words[0] != 'prune_ledger':
        raise ValueError(f'not a prune_ledger line: {line[:60]!r}')
    values = words[1].split('|')
    technique = values[0]
    if technique not in layouts:
        raise ValueError(f'prune_ledger: unknown technique {technique!r}')
    names = layouts[technique]
    if len(values) - 1 != len(names):
        raise ValueError(f'prune_ledger {technique}: {len(values) - 1} fields, expected {len(names)}')
    row = dict(zip(names, (int(v) for v in values[1:])))
    row['technique'] = technique
    return row


def parse_eval_site_line(line):
    """One `eval_site` line -> a dict of its integer fields and 'fen'."""
    names = ('kind', 'reused', 'alpha', 'beta', 'eval', 'prune_eval', 'depth', 'ply', 'parent_eval', 'tt_bound',
             'tt_depth', 'captured', 'on_pv')
    if not line.startswith('eval_site '):
        raise ValueError(f'not an eval_site line: {line[:60]!r}')
    parts = line[len('eval_site '):].rstrip('\r\n').split('|', len(names))
    if len(parts) != len(names) + 1 or not parts[-1].strip():
        raise ValueError(f'eval_site: {len(parts)} fields, expected {len(names) + 1}')
    row = dict(zip(names, (int(v) for v in parts[:-1])))
    row['fen'] = parts[-1].strip()
    return row


def counter_delta(after, before):
    """The difference of two cumulative dumps (dicts of counters or of bin lists)."""
    if before is None:
        return dict(after)
    if set(after) != set(before):
        raise ValueError('the two dumps have different counters')
    out = {}
    for name, value in after.items():
        if isinstance(value, list):
            if len(value) != len(before[name]):
                raise ValueError(f'histogram {name} changed length')
            out[name] = [a - b for a, b in zip(value, before[name])]
            if min(out[name], default=0) < 0:
                raise ValueError(f'histogram {name} went down: not cumulative')
        else:
            out[name] = value - before[name]
            if out[name] < 0:
                raise ValueError(f'counter {name} went down: not cumulative')
    return out
