"""Sharded SPRT results: one shard's snapshot, and the merge of many.

A sharded SPRT splits one test across machines or jobs (tools/cloud/,
docs/kb/tools.md "Cloud SPRT"): every shard plays the same two builds at the
same time control on its own slice of the openings, for a fixed number of
games, and records fastchess's pentanomial counts (game pairs scoring 0,
1/2, 1, 3/2 or 2 for the test engine). Pairs are independent across
shards, so the counts add up, and the combined test is the SPRT on the sum.

The statistics follow fastchess's normalized model (model=normalized), as
checked against 18 SPRTs in Fork's log (tests below): with x the pair score
over 2 (0, 1/4, 1/2, 3/4, 1), its mean m and variance v over n pairs,
- Elo = -400 log10(1/m - 1);
- nElo = (m - 1/2) / sqrt(v) * C, with C = 800 / (ln 10 * sqrt 2);
- LLR = n / (2 v) * ((m - m0)^2 - (m - m1)^2), with m_i = 1/2 + (nElo_i / C)
  sqrt(v) for the bounds nElo_0 and nElo_1 (the normal approximation of the
  generalized SPRT); accept H1 at log((1 - beta) / alpha), H0 at
  log(beta / (1 - alpha)).
Elo, nElo and their error bars match fastchess's to its two decimals; the
LLR is within 0.01 of fastchess's on every undecided run (fastchess's own
computation differs slightly, probably the full likelihood rather than the
normal approximation), so a verdict within 0.01 of a bound is confirmed with
more games before it is trusted.
Looking at the sum only at stage boundaries, not after every pair, makes the
test slightly conservative, never anti-conservative.

    python3 tools/cloud/sprt_merge.py snapshot LOG OUT.json [--meta KEY=VALUE ...] [--status S]
    python3 tools/cloud/sprt_merge.py merge SHARD.json ... --elo0 -3 --elo1 0 [--json OUT]
"""
import argparse
import json
import math
import re
import sys

PAIR_SCORES = (0.0, 0.25, 0.5, 0.75, 1.0)
NELO_SCALE = 800 / (math.log(10) * math.sqrt(2))
_PTNML = re.compile(r'Ptnml\(0-2\):\s*\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]')
_FINISHED = re.compile(r'^Finished game \d+ .*\{(.*)\}')
_ABNORMAL = re.compile(r'illegal|crash|disconnect|stall|unresponsive', re.I)


def moments(ptnml):
    """(pairs, mean, variance) of the pair score over 2."""
    n = sum(ptnml)
    if n == 0:
        return 0, 0.5, 0.0
    mean = sum(c * s for c, s in zip(ptnml, PAIR_SCORES)) / n
    var = sum(c * (s - mean) ** 2 for c, s in zip(ptnml, PAIR_SCORES)) / n
    return n, mean, var


def elo(mean):
    if mean <= 0 or mean >= 1:
        return math.copysign(float('inf'), mean - 0.5)
    return -400 * math.log10(1 / mean - 1)


def nelo(ptnml):
    n, mean, var = moments(ptnml)
    return (mean - 0.5) / math.sqrt(var) * NELO_SCALE if var > 0 else 0.0


def llr(ptnml, nelo0, nelo1):
    n, mean, var = moments(ptnml)
    if n == 0 or var == 0:
        return 0.0
    sd = math.sqrt(var)
    m0 = 0.5 + nelo0 / NELO_SCALE * sd
    m1 = 0.5 + nelo1 / NELO_SCALE * sd
    return n / (2 * var) * ((mean - m0) ** 2 - (mean - m1) ** 2)


def bounds(alpha=0.05, beta=0.05):
    return math.log(beta / (1 - alpha)), math.log((1 - beta) / alpha)


def verdict(ptnml, nelo0, nelo1, alpha=0.05, beta=0.05):
    lower, upper = bounds(alpha, beta)
    value = llr(ptnml, nelo0, nelo1)
    return value, ('H1 accepted' if value >= upper else 'H0 accepted' if value <= lower else 'continue')


_GAME = re.compile(r'^Finished game (\d+) \((\S+) vs (\S+)\): (1-0|0-1|1/2-1/2) \{(.*)\}')


def pairs_from_games(log_text, test='test'):
    """Pentanomial counts from the finished games themselves: with -repeat,
    games 2k-1 and 2k share an opening, and a pair counts once both are done
    (so a shard stopped between fastchess's periodic reports keeps every
    finished pair)."""
    games = {}
    for line in log_text.splitlines():
        m = _GAME.match(line)
        if m:
            n, white, black, result = int(m.group(1)), m.group(2), m.group(3), m.group(4)
            white_points = {'1-0': 1.0, '0-1': 0.0, '1/2-1/2': 0.5}[result]
            games[n] = white_points if white == test else 1.0 - white_points
    ptnml = [0, 0, 0, 0, 0]
    for k in range(1, max(games, default=0) // 2 + 1):
        if 2 * k - 1 in games and 2 * k in games:
            ptnml[int(round(2 * (games[2 * k - 1] + games[2 * k])))] += 1
    return ptnml


def snapshot(log_text):
    """A shard's counts from its fastchess log: the pairs of finished games,
    games finished, time losses and abnormal endings, and fastchess's own
    last pentanomial report for comparison."""
    reports = _PTNML.findall(log_text)
    finished = time_losses = 0
    for line in log_text.splitlines():
        m = _FINISHED.match(line)
        if m:
            finished += 1
            time_losses += bool(re.search(r'on time|forfeit', m.group(1), re.I))
    abnormal = len(_ABNORMAL.findall(log_text))
    ptnml = pairs_from_games(log_text)
    return {'ptnml': ptnml, 'pairs': sum(ptnml), 'finished_games': finished, 'time_losses': time_losses,
            'abnormal': abnormal, 'fastchess_ptnml': [int(x) for x in reports[-1]] if reports else None}


def merge(shards):
    """The summed counts; refuses shards of different tests (commits,
    conditions, tables on or off), or two shards that played the same
    openings. The test is identified by its commits and
    conditions, not by binary hashes: machines that build for themselves
    produce different bytes (debug info, build paths)."""
    keys = ('base', 'test', 'tc', 'hash', 'base_opts', 'test_opts', 'tables')
    first = shards[0].get('meta', {})
    for s in shards[1:]:
        for k in keys:
            if s.get('meta', {}).get(k) != first.get(k):
                raise ValueError(f'shards differ in {k}: {first.get(k)!r} vs {s.get("meta", {}).get(k)!r}')
    starts = [s.get('meta', {}).get('opening_start') for s in shards]
    dup = sorted({x for x in starts if x is not None and starts.count(x) > 1})
    if dup:
        raise ValueError(f'shards share openings (opening_start {", ".join(map(str, dup))})')
    total = [sum(s['ptnml'][i] for s in shards) for i in range(5)]
    return {'meta': {k: first.get(k) for k in keys + ('book', 'book_seed')}, 'shards': len(shards), 'ptnml': total,
            'pairs': sum(total), 'finished_games': sum(s.get('finished_games', 0) for s in shards),
            'time_losses': sum(s.get('time_losses', 0) for s in shards),
            'abnormal': sum(s.get('abnormal', 0) for s in shards),
            'status': sorted({s.get('status', '?') for s in shards})}


def report(merged, nelo0, nelo1, alpha=0.05, beta=0.05):
    p = merged['ptnml']
    n, mean, var = moments(p)
    value, decision = verdict(p, nelo0, nelo1, alpha, beta)
    lower, upper = bounds(alpha, beta)
    se = math.sqrt(var / n) if n else 0.0
    half = (elo(mean + 1.96 * se) - elo(mean - 1.96 * se)) / 2 if n else 0.0
    return '\n'.join([
        f'Shards: {merged["shards"]} ({", ".join(merged["status"])}); pairs {n}, games {2 * n} '
        f'({merged["finished_games"]} finished, time losses {merged["time_losses"]}, abnormal {merged["abnormal"]})',
        f'Tables: {merged["meta"].get("tables") or "not recorded"} (both engines); book: '
        f'{merged["meta"].get("book") or "not recorded"}, seed {merged["meta"].get("book_seed") or "not recorded"}',
        f'Elo: {elo(mean):.2f} +/- {half:.2f}, nElo: {nelo(p):.2f} +/- {1.96 * NELO_SCALE / math.sqrt(n) if n else 0:.2f}',
        f'Ptnml(0-2): {p}',
        f'LLR: {value:.2f} ({lower:.2f}, {upper:.2f}) [{nelo0:.2f}, {nelo1:.2f}] nElo: {decision}',
    ])


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('snapshot')
    s.add_argument('log')
    s.add_argument('out')
    s.add_argument('--meta', action='append', default=[], help='KEY=VALUE recorded with the counts')
    s.add_argument('--status', default='running')
    m = sub.add_parser('merge')
    m.add_argument('files', nargs='+')
    m.add_argument('--elo0', type=float, required=True)
    m.add_argument('--elo1', type=float, required=True)
    m.add_argument('--alpha', type=float, default=0.05)
    m.add_argument('--beta', type=float, default=0.05)
    m.add_argument('--json')
    a = ap.parse_args(argv)
    if a.cmd == 'snapshot':
        with open(a.log, encoding='utf-8', errors='replace') as f:
            result = snapshot(f.read())
        result['meta'] = dict(kv.split('=', 1) for kv in a.meta)
        result['status'] = a.status
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=1)
        return 0
    shards = []
    for path in a.files:
        with open(path, encoding='utf-8') as f:
            shards.append(json.load(f))
    merged = merge(shards)
    if merged['pairs'] == 0:
        print(f'no finished pairs in {len(shards)} shards: nothing to merge', file=sys.stderr)
        return 1
    print(report(merged, a.elo0, a.elo1, a.alpha, a.beta))
    if a.json:
        value, decision = verdict(merged['ptnml'], a.elo0, a.elo1, a.alpha, a.beta)
        merged.update(elo0=a.elo0, elo1=a.elo1, llr=value, verdict=decision, nelo=nelo(merged['ptnml']),
                      elo=elo(moments(merged['ptnml'])[1]))
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
