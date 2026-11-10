# SPDX-License-Identifier: GPL-3.0-or-later

"""The ordering pilot's fitness: nodes to a fixed depth (ideas.md idea 23,
owner, 2026-11-09; the declaration is docs/research/idea23-pilot/declaration.md).

Each position is searched from a fresh state (`ucinewgame`: the hash table
and every history table cleared) to a fixed depth with one thread and a fixed
Hash, so the node count, best move and score are a function of the engine
and the position alone: the same whatever the order of the positions, the
number of engine processes or the machine's load. A candidate's fitness is
its node reduction against the baseline on the same positions,

    reduction = 1 - (sum of the candidate's nodes) / (sum of the baseline's),

higher is better (0 for the baseline itself). Its uncertainty over the choice
of positions is a paired percentile bootstrap of that ratio (positions drawn
with replacement, both engines' counts together; seeded).

The equivalence guard compares each position's answer with the baseline's:
a position is equivalent if the best move is the same and the scores agree
within a tolerance (both centipawn scores within `tolerance` cp, or both mate
scores for the same side). The guard passes if the equivalent share of the
check set reaches the declared threshold.
"""
import hashlib
import json
import math
import random
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import proxies


@dataclass
class DepthAnswer:
    nodes: int
    move: str
    score: str  # 'cp N' or 'mate N', from the side to move's view; '' if none was reported

    def row(self):
        return [self.nodes, self.move, self.score]


def answer_from_row(row):
    return DepthAnswer(int(row[0]), row[1], row[2])


def parse_search(lines, depth):
    """The DepthAnswer from one `go depth` search's output: the last exact
    score line's nodes and score (it is the last iteration's: the search ends
    when that iteration completes) and the bestmove."""
    nodes, score, reached = 0, '', 0
    for line in lines:
        t = line.split()
        if t[:1] != ['info']:
            continue
        if 'nodes' in t:
            nodes = int(t[t.index('nodes') + 1])
        if 'score' in t and 'lowerbound' not in t and 'upperbound' not in t:
            i = t.index('score')
            score = f'{t[i + 1]} {t[i + 2]}'
            if 'depth' in t:
                reached = int(t[t.index('depth') + 1])
    move = lines[-1].split()[1] if lines and lines[-1].startswith('bestmove') else ''
    if reached and reached != depth:
        raise RuntimeError(f'the search reported depth {reached}, not {depth}')
    return DepthAnswer(nodes, move, score)


class DepthEngine(proxies.Engine):
    """One engine process: one thread, a fixed Hash, a fresh state per position."""

    def __init__(self, path, hash_mb=16):
        super().__init__(path, hash_mb)
        self.send('setoption name Threads value 1')

    def search(self, fen, depth):
        self.send('ucinewgame')
        self.send('isready')
        self.until('readyok')
        self.send(f'position fen {fen}')
        self.send(f'go depth {depth}')
        return parse_search(self.until('bestmove'), depth)


def run_fixed_depth(engine_path, rows, depth, jobs=1, hash_mb=16):
    """Every position of `rows` searched to `depth`, split across `jobs`
    engine processes (interleaved), answers in the rows' order."""
    def part(chunk):
        engine = DepthEngine(engine_path, hash_mb)
        try:
            return [engine.search(r['fen'], depth) for r in chunk]
        finally:
            engine.close()
    jobs = max(1, min(jobs, len(rows)))
    chunks = [rows[k::jobs] for k in range(jobs)]
    with ThreadPoolExecutor(jobs) as pool:
        results = list(pool.map(part, chunks))
    answers = [None] * len(rows)
    for k, chunk in enumerate(results):
        answers[k::jobs] = chunk
    return answers


def node_reduction(candidate, baseline):
    """1 - sum(candidate) / sum(baseline): the share of the baseline's nodes saved (negative: more nodes)."""
    return 1.0 - sum(candidate) / sum(baseline)


def reduction_interval(candidate, baseline, seed, rounds=2000, level=0.95):
    """(reduction, low, high): the reduction and a paired percentile bootstrap
    interval over positions (each round draws positions with replacement and
    recomputes the ratio of the sums). Seeded; None without counts."""
    if not candidate or len(candidate) != len(baseline):
        return None
    n = len(candidate)
    rng = random.Random(seed)
    values = []
    for _ in range(rounds):
        c = b = 0
        for _ in range(n):
            i = rng.randrange(n)
            c += candidate[i]
            b += baseline[i]
        values.append(1.0 - c / b)
    values.sort()
    tail = (1 - level) / 2
    return node_reduction(candidate, baseline), values[int(tail * rounds)], values[min(rounds - 1,
                                                                                         int((1 - tail) * rounds))]


def paired_summary(candidate, baseline):
    """Per-position comparison: positions with fewer, equal and more nodes, the
    median and geometric mean of the candidate / baseline ratio, and the
    totals."""
    ratios = sorted(c / b for c, b in zip(candidate, baseline) if b > 0)
    fewer = sum(c < b for c, b in zip(candidate, baseline))
    more = sum(c > b for c, b in zip(candidate, baseline))
    n = len(ratios)
    median = (ratios[n // 2] if n % 2 else (ratios[n // 2 - 1] + ratios[n // 2]) / 2) if n else None
    geo = math.exp(sum(math.log(r) for r in ratios if r > 0) / n) if n else None
    return {'positions': len(candidate), 'fewer': fewer, 'equal': len(candidate) - fewer - more, 'more': more,
            'median_ratio': median, 'geomean_ratio': geo, 'total': sum(candidate), 'baseline_total': sum(baseline)}


def equivalent(a, b, tolerance):
    """True if answers a and b give the same best move and scores within `tolerance` cp (mates: the same side)."""
    if a.move != b.move or not a.score or not b.score:
        return False
    ka, va = a.score.split()
    kb, vb = b.score.split()
    if ka == 'cp' and kb == 'cp':
        return abs(int(va) - int(vb)) <= tolerance
    if ka == 'mate' and kb == 'mate':
        return (int(va) > 0) == (int(vb) > 0)
    return False


def equivalence_share(candidate, baseline, tolerance):
    """The share of positions whose answers are equivalent (a list of DepthAnswer each)."""
    if not candidate:
        return 0.0
    return sum(equivalent(a, b, tolerance) for a, b in zip(candidate, baseline)) / len(candidate)


def digest(answers):
    """SHA-256 of the answers in order (nodes, move, score): one value to compare two runs exactly."""
    text = json.dumps([a.row() for a in answers], separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


_CUTOFFS = re.compile(r'stats: (\d+) beta cutoffs, ([0-9.]+)% on the first move, mean cutoff index ([0-9.]+)')


def ordering_descriptors(stats_output):
    """(share of beta cutoffs by the first move, mean index of the cutting move)
    from a FORK_SEARCH_STATS build's bench: how well the order puts the
    refutation first, the ordering pilot's two grid axes."""
    m = _CUTOFFS.search(stats_output)
    if not m:
        raise ValueError('no cutoff statistics in the bench output (not a FORK_SEARCH_STATS build?)')
    return float(m.group(2)) / 100.0, float(m.group(3))


def sample_rows(rows, count, seed):
    """`count` rows drawn without replacement with `seed`, kept in file order (all of them for 0 or None)."""
    if not count or count >= len(rows):
        return list(rows)
    keep = set(random.Random(seed).sample(range(len(rows)), count))
    return [r for i, r in enumerate(rows) if i in keep]
