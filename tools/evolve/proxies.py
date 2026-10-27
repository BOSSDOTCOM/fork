"""The evaluator funnel's second stage: cheap proxies (ideas.md idea 23).

On the loop's position set (tools/evolve/positions.py: Fork's own
self-play, labeled by Fork's own much deeper search), a candidate searches
every position at the same node budget as the baseline, from a fresh state,
and is scored by:
- agreement: the share of positions where its best move is the label's;
- score error: the mean absolute difference from the label's score, in cp,
  each capped at ErrorCap so one wild position cannot dominate;
- depth (secondary only, never used alone): the mean depth reached in the
  budget.
Only the "evolve" split is used during evolution; "holdout" is for the final
check of a survivor. WAC and matetrack are never proxies (owner's spec).

The behaviour descriptors for the population's grid come from a
FORK_SEARCH_STATS build's bench: the mean reduction of reduced searches and
the share re-searched at full depth.
"""
import json
import re
import subprocess
from dataclasses import dataclass

ErrorCap = 400


def load_positions(path, split='evolve'):
    with open(path, encoding='utf-8') as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [r for r in rows if split is None or r['split'] == split]


@dataclass
class Answer:
    move: str
    score: int | None  # cp from the side to move; None for a mate or no score
    depth: int


@dataclass
class ProxyResult:
    positions: int
    agreement: float
    score_error: float
    depth: float

    def fitness(self):
        """One number for ranking: agreement, less a pawn of mean error per 0.1 of agreement."""
        return self.agreement - self.score_error / 1000.0


def measure(answers, labels):
    """Proxy metrics from a candidate's answers and the labels (same order)."""
    if not labels:
        return ProxyResult(0, 0.0, 0.0, 0.0)
    agree = sum(a.move == r['bm'] for a, r in zip(answers, labels))
    errors = [min(ErrorCap, abs(a.score - r['ce'])) if a.score is not None else ErrorCap
              for a, r in zip(answers, labels)]
    return ProxyResult(len(labels), agree / len(labels), sum(errors) / len(errors),
                       sum(a.depth for a in answers) / len(answers))


class Engine:
    """One UCI engine process answering `go nodes N` from a fresh state per position."""

    def __init__(self, path, hash_mb=16):
        self.p = subprocess.Popen([str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.send('uci')
        self.until('uciok')
        self.send(f'setoption name Hash value {hash_mb}')

    def send(self, line):
        self.p.stdin.write(line + '\n')
        self.p.stdin.flush()

    def until(self, prefix):
        lines = []
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError(f'engine ended waiting for {prefix!r}')
            lines.append(line.rstrip('\n'))
            if line.startswith(prefix):
                return lines

    def answer(self, fen, nodes):
        self.send('ucinewgame')
        self.send('isready')
        self.until('readyok')
        self.send(f'position fen {fen}')
        self.send(f'go nodes {nodes}')
        lines = self.until('bestmove')
        score, depth = None, 0
        for line in lines:
            t = line.split()
            if t[:1] != ['info'] or 'score' not in t or 'lowerbound' in t or 'upperbound' in t:
                continue
            i = t.index('score')
            score = int(t[i + 2]) if t[i + 1] == 'cp' else None
            depth = int(t[t.index('depth') + 1]) if 'depth' in t else depth
        return Answer(lines[-1].split()[1], score, depth)

    def close(self):
        self.send('quit')
        self.p.wait(timeout=10)


def run_proxies(engine_path, labels, nodes):
    engine = Engine(engine_path)
    try:
        answers = [engine.answer(r['fen'], nodes) for r in labels]
    finally:
        engine.close()
    return measure(answers, labels)


_REDUCED = re.compile(r'stats: (\d+) reduced searches, (\d+) re-searched')
_MEAN = re.compile(r'stats: mean reduction ([0-9.]+) plies')


def descriptors(stats_output):
    """(mean reduction in plies, re-search share) from a stats build's bench output."""
    reduced = _REDUCED.search(stats_output)
    mean = _MEAN.search(stats_output)
    if not reduced or not mean:
        raise ValueError('no LMR statistics in the bench output (not a FORK_SEARCH_STATS build?)')
    searches, researches = int(reduced.group(1)), int(reduced.group(2))
    return float(mean.group(1)), researches / searches if searches else 0.0
