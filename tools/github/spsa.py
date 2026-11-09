# SPDX-License-Identifier: GPL-3.0-or-later
"""SPSA on the GitHub shards: the arithmetic, the spec and the state (DESIGN.md §5.2, "SPSA on GitHub").

One SPSA iteration is one run of .github/workflows/spsa.yml: every game pair plays theta + c*signs against
theta - c*signs with its own random signs (tools/github/spsa_shard.py), and the iteration's pairs give one
synchronous update of theta. tools/github/spsa_run.sh dispatches the runs; this module plans each run,
verifies its results and updates the state. Every tuned parameter is a FORK_TUNE spin option
(src/tune/params.hpp).

The method (simultaneous perturbation): Spall, "Multivariate stochastic approximation using a simultaneous
perturbation gradient approximation", IEEE TAC 37(3):332-341, 1992 (DOI 10.1109/9.119632); the gain
sequences: Spall, "Implementation of the simultaneous perturbation algorithm for stochastic optimization",
IEEE TAES 34(3):817-823, 1998 (DOI 10.1109/7.705889), Sec. III-A Step 1 (p. 819): a_k = a / (A + k + 1)^alpha
and c_k = c / (k + 1)^gamma with k counted from 0, alpha = 0.602 and gamma = 0.101 as "practically effective
and theoretically valid"; Sec. III-B (p. 820): A much less than the number of iterations, often 10% of it or
less. Fork's own rules for its noise (think tank B7, O2): the gain is set from a stationary-loss budget,
gain_end = 16 * loss_budget * k / (p * pair_sd^2) with k = ln 10 / 1600 the score per Elo at equality; the
gain index counts game pairs (one perturbation per pair); each update is clamped to clamp_c * c; theta stays
at least c inside each range, so a perturbed value never leaves it; integers by random rounding; the result
is the mean of theta over the last average_tail of the updates.

Per pair j of an iteration (pairs ordered by shard, then draw index), with r_j the pair's score for theta+
minus 1/2 and a_n = gain_end * ((A + N) / (A + n + 1))^alpha (n counted from 0 over all pairs, N of them):
    step_i = clamp(sum_j a_n * r_j * signs_ij * c_i^2 / (2 c_ik), -clamp_c * c_ik, +clamp_c * c_ik)
which is a_n * g_i with g_i = r_j signs_ij / (2 c_ik), the simultaneous-perturbation gradient, and a gain
of a_n c_i^2 (B7: the tuner works in units of c). With c fixed (c_decay 0, as B7 simulated) it is
    x_i += a_n r_j signs_ij / 2,  x_i = theta_i / c_i.

    spsa.py init NAME --spec FILE --commit SHA [--calibration FILE]
    spsa.py dispatch NAME          the inputs of the next run (key=value lines); writes i<stage>/dispatch.json
    spsa.py step NAME --stage D [--meta wall_minutes=M]
                                   verifies stage D's downloaded results and applies its update
    spsa.py report NAME            every trajectory and the final values; writes final.json
    spsa.py rewind NAME --to K     back to theta after iteration K (-1: the start); abandons a pending stage
    spsa.py merge FILE... [--json OUT]   a run's shard results summed (the workflow's summary)

Data: $SPSA_DATA/NAME/ (default ~/fork-spsa/github/NAME): spec.json (fixed at init), state.json (written
atomically, the commit point of each update), iterations.jsonl (one line per update; a rewind adds a line),
i<stage>/ (dispatch.json, run_id, the run's artifacts), final.json.
"""
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

SCORE_PER_ELO = math.log(10) / 1600
# Never tuned in an STC or LTC SPSA (DESIGN.md §6, 2026-11-07 decision 4): the time management (the iteration
# rule and the time budget, src/tune/params.hpp). The eval scale is not a parameter of the table at all, so
# it can never be passed; if it ever becomes one, it belongs here too.
EXCLUDED_PARAMS = frozenset({'IterationGrowthThirds', 'ForcedMoveFraction', 'AssumedMovesLeft', 'MaxMovesToGo',
                             'HardOverSoft', 'ReserveDivisor', 'DangerZoneOverheads'})
_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')
_VALUE = re.compile(r'^[A-Za-z0-9.+-]+$')
_LABEL = re.compile(r'^spsa-[a-z0-9][a-z0-9.-]*$')
_TABLE_ROW = re.compile(r'^\s*X\((\w+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\)')


class Refused(Exception):
    """A spec, a state or a run's results that must not be used."""


# ------------------------------------------------------------------ the parameter strings

def parse_params(text):
    """'Name=theta:c,...,Name=value' -> ([(name, theta, c)], {name: value}): tuned entries carry ':c', fixed
    ones (given to both sides alike, e.g. a switch) do not."""
    tuned, fixed, seen = [], {}, set()
    for item in text.split(','):
        name, sep, rest = item.partition('=')
        if not sep or not _NAME.match(name) or name in seen:
            raise Refused(f'params: bad or repeated entry {item!r}')
        seen.add(name)
        if ':' in rest:
            theta, c = rest.split(':', 1)
            try:
                tuned.append((name, float(theta), float(c)))
            except ValueError:
                raise Refused(f'params: bad numbers in {item!r}') from None
            if not tuned[-1][2] > 0:
                raise Refused(f'params: c must be positive in {item!r}')
        elif _VALUE.match(rest):
            fixed[name] = rest
        else:
            raise Refused(f'params: bad value in {item!r}')
    if not tuned:
        raise Refused('params: nothing to tune')
    return tuned, fixed


def format_params(tuned, fixed):
    return ','.join([f'{n}={t:.3f}:{c:.3f}' for n, t, c in tuned] + [f'{n}={v}' for n, v in fixed.items()])


# ------------------------------------------------------------------ the random draws (shared with the shard)

def pair_seed(label, commit, stage, shard, index):
    """The seed of one draw: the shard and the driver derive the same signs and values from it."""
    return hashlib.sha256(f'{label}|{commit}|{stage}|{shard}|{index}'.encode()).digest()


def draw_signs(seed, count):
    """Rademacher signs (+1 / -1), one per tuned parameter."""
    bits = b''
    block = 0
    while len(bits) * 8 < count:
        bits += hashlib.sha256(seed + b'signs' + block.to_bytes(4, 'big')).digest()
        block += 1
    return [1 if bits[i // 8] >> (i % 8) & 1 else -1 for i in range(count)]


def stochastic_round(value, u):
    """floor(value) or floor(value) + 1, the latter with probability frac(value) for u uniform in [0, 1)."""
    low = math.floor(value)
    return int(low) + (1 if u < value - low else 0)


def perturbed_values(seed, tuned):
    """(signs, plus, minus) of one draw: plus = round(theta + c * sign), minus = round(theta - c * sign), each
    parameter rounded with one uniform shared by both sides (common random numbers)."""
    signs = draw_signs(seed, len(tuned))
    plus, minus = [], []
    for i, ((_, theta, c), s) in enumerate(zip(tuned, signs)):
        u = int.from_bytes(hashlib.sha256(seed + b'round' + i.to_bytes(4, 'big')).digest()[:4], 'big') / 2 ** 32
        plus.append(stochastic_round(theta + c * s, u))
        minus.append(stochastic_round(theta - c * s, u))
    return signs, plus, minus


def shard_plan(games, shards, draw_pairs):
    """Pairs per shard: games / 2 shared out, rounded up to whole draws."""
    per = -(-games // (2 * shards))
    return -(-per // draw_pairs) * draw_pairs


# ------------------------------------------------------------------ the gains and the update

def gain_end(spec):
    """The gain at the last pair, from the stationary-loss budget (B7 §0 and O2 rule 3)."""
    return 16 * spec['loss_budget'] * SCORE_PER_ELO / (len(spec['params']) * spec['pair_sd'] ** 2)


def gain_at(spec, n):
    """a_n for pair n (from 0): Spall 1998's a / (A + n + 1)^alpha, scaled to gain_end at the last pair."""
    big_n, big_a = spec['total_pairs'], spec['stability_offset']
    return spec['gain_end'] * ((big_a + big_n) / (big_a + n + 1)) ** spec['gain_exponent']


def c_at(spec, iteration):
    """c_k = c / (k + 1)^gamma per parameter (Spall 1998; c_decay 0 holds c fixed)."""
    return {p['name']: p['c'] / (iteration + 1) ** spec['c_decay'] for p in spec['params']}


def pair_scores(ptnml):
    """(count, sum of (s - 1/2), sum of (s - 1/2)^2) over pairs, s the pair's score over its two games."""
    count = sum(ptnml)
    total = sum(k * (i / 4 - 0.5) for i, k in enumerate(ptnml))
    squares = sum(k * (i / 4 - 0.5) ** 2 for i, k in enumerate(ptnml))
    return count, total, squares


def iteration_step(spec, theta, iteration, records, first_pair):
    """The update of one iteration from its draws, in order: {'theta_after', 'grad_sum', 'z', 'step_raw',
    'step', 'clamped', 'gain_first', 'gain_last', 'pairs'}. Each record has 'signs' ('+-' string, one per
    tuned parameter in spec order) and 'ptnml' (its pairs, scored for theta+)."""
    names = [p['name'] for p in spec['params']]
    c_now, c_next = c_at(spec, iteration), c_at(spec, iteration + 1)
    base_c = {p['name']: p['c'] for p in spec['params']}
    grad = dict.fromkeys(names, 0.0)
    raw = dict.fromkeys(names, 0.0)
    squares, n = 0.0, first_pair
    gains = []
    for rec in records:
        count, total, sq = pair_scores(rec['ptnml'])
        count = int(round(count))  # the tests give expected scores as fractional counts
        if count == 0:
            continue
        gain = sum(gain_at(spec, n + q) for q in range(count)) / count
        gains += [gain_at(spec, n), gain_at(spec, n + count - 1)]
        n += count
        squares += sq
        for name, s in zip(names, rec['signs']):
            sign = 1 if s == '+' else -1
            grad[name] += total * sign
            raw[name] += gain * total * sign * base_c[name] ** 2 / (2 * c_now[name])
    pairs = n - first_pair
    out = {'pairs': pairs, 'grad_sum': grad, 'step_raw': raw, 'step': {}, 'clamped': [], 'theta_after': {},
           'z': {k: (v / math.sqrt(squares) if squares > 0 else 0.0) for k, v in grad.items()},
           'gain_first': gains[0] if gains else 0.0, 'gain_last': gains[-1] if gains else 0.0}
    for p in spec['params']:
        name, limit = p['name'], spec['clamp_c'] * c_now[p['name']]
        step = min(max(raw[name], -limit), limit)
        if step != raw[name]:
            out['clamped'].append(name)
        out['step'][name] = step
        lo, hi = p['lowest'] + c_next[name], p['highest'] - c_next[name]
        out['theta_after'][name] = round(min(max(theta[name] + step, lo), hi), 3)
    return out


def final_theta(history, tail):
    """The mean of theta over the last ceil(tail * updates) updates (B7 O2 rule 9)."""
    if not history:
        raise Refused('no updates yet')
    last = history[-math.ceil(tail * len(history)):]
    return {k: sum(h[k] for h in last) / len(last) for k in last[0]}


def step_limited(clamp_counts, updates):
    """Parameters clamped in at least two thirds of the updates (B14: 8 of 12): the run was step-limited for
    them, not noise-limited."""
    need = math.ceil(2 * updates / 3)
    return sorted(k for k, v in clamp_counts.items() if updates and v >= need)


# ------------------------------------------------------------------ the spec

def table_from_header(text):
    """{name: (default, lowest, highest, step)} from src/tune/params.hpp's FORK_SEARCH_PARAMS."""
    rows = {}
    for line in text.splitlines():
        m = _TABLE_ROW.match(line)
        if m:
            rows[m.group(1)] = tuple(int(m.group(i)) for i in range(2, 6))
    if not rows:
        raise Refused('no FORK_SEARCH_PARAMS rows in the header')
    return rows


def resolve_spec(raw, table, label, commit):
    """The spec as the run uses it: every parameter with start, c and bounds, the derived gain, checked."""
    if not _LABEL.match(label):
        raise Refused(f'name {label!r} must match spsa-[a-z0-9][a-z0-9.-]*')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise Refused('commit must be a full 40-hex SHA')
    spec = {k: raw[k] for k in ('iterations', 'games', 'shards', 'draw_pairs', 'tc', 'hash', 'loss_budget',
                                'pair_sd', 'gain_exponent', 'stability_offset', 'clamp_c', 'c_decay',
                                'average_tail', 'opening_reserve')}
    spec.update(label=label, commit=commit, fixed=dict(raw.get('fixed', {})), params=[])
    for k in ('iterations', 'games', 'shards', 'draw_pairs', 'hash', 'opening_reserve'):
        if not isinstance(spec[k], int) or spec[k] < 1:
            raise Refused(f'{k} must be a positive integer')
    if not 1 <= spec['shards'] <= 16:
        raise Refused('shards must be 1-16')
    if not re.fullmatch(r'[0-9.]+\+[0-9.]+', spec['tc']):
        raise Refused('tc must be base+increment')
    for name, value in spec['fixed'].items():
        if not _NAME.match(name) or not _VALUE.match(str(value)):
            raise Refused(f'fixed option {name}={value} is not name=value')
        spec['fixed'][name] = str(value)
    for p in raw['params']:
        name = p['name']
        if name in EXCLUDED_PARAMS:
            raise Refused(f'{name} is time management: never in an STC or LTC SPSA (DESIGN.md §6, decision 4)')
        if name not in table:
            raise Refused(f'{name} is not in the commit\'s FORK_SEARCH_PARAMS')
        if any(q['name'] == name for q in spec['params']) or name in spec['fixed']:
            raise Refused(f'{name} is listed twice')
        default, lowest, highest, _ = table[name]
        q = {'name': name, 'start': float(p.get('start', default)), 'c': float(p['c']),
             'lowest': int(p.get('lowest', lowest)), 'highest': int(p.get('highest', highest))}
        if q['lowest'] < lowest or q['highest'] > highest or q['lowest'] >= q['highest']:
            raise Refused(f'{name}: bounds {q["lowest"]}-{q["highest"]} not inside the table\'s {lowest}-{highest}')
        if q['c'] < 1:
            raise Refused(f'{name}: c {q["c"]} is below 1 (integer resolution)')
        if not q['lowest'] + q['c'] <= q['start'] <= q['highest'] - q['c']:
            raise Refused(f'{name}: start {q["start"]} must lie at least c = {q["c"]} inside its bounds')
        spec['params'].append(q)
    if not spec['params']:
        raise Refused('nothing to tune')
    pairs = shard_plan(spec['games'], spec['shards'], spec['draw_pairs']) * spec['shards']
    spec['total_pairs'] = pairs * spec['iterations']
    # Spall 1998, Sec. III-B: A is much less than the number of iterations, often 10% of it or less.
    if not 0 <= spec['stability_offset'] <= 0.1 * spec['total_pairs']:
        raise Refused('stability_offset must be at most 10% of the total pairs (Spall 1998, Sec. III-B)')
    # The tuning reserve: lines 2,000,001 to 2,632,036 (the end) of the shuffled UHO book, which no SPRT
    # reaches (an SPRT stage plays from line 1; tools/cloud/run_shard.sh).
    if spec['opening_reserve'] < 2000001 or spec['opening_reserve'] + spec['total_pairs'] - 1 > 2632036:
        raise Refused('the openings must lie in the tuning reserve, lines 2,000,001-2,632,036')
    spec['gain_end'] = gain_end(spec)
    return spec


# ------------------------------------------------------------------ the data folder

def data_dir(name):
    return Path(os.environ.get('SPSA_DATA') or Path.home() / 'fork-spsa' / 'github') / name


def read_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.write('\n')
    os.replace(tmp, path)


def load_spec(name):
    return read_json(data_dir(name) / 'spec.json')


def load_state(name):
    return read_json(data_dir(name) / 'state.json')


def save_state(name, state):
    write_json(data_dir(name) / 'state.json', state)


def log_lines(name):
    try:
        with open(data_dir(name) / 'iterations.jsonl', encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def history(name):
    """The applied updates in order, a rewind truncating them."""
    out = []
    for line in log_lines(name):
        if 'rewind' in line:
            del out[line['rewind'] + 1:]
        else:
            out.append(line)
    return out


def spec_digest(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


def pending_stage(name, state):
    """The stage dispatched and neither applied nor abandoned, or None."""
    d = state['stage'] - 1
    if d < 0 or d in state['burned'] or not (data_dir(name) / f'i{d}' / 'dispatch.json').exists():
        return None
    return None if any(line.get('stage') == d for line in log_lines(name)) else d


# ------------------------------------------------------------------ the commands

def cmd_init(a):
    folder = data_dir(a.name)
    header = subprocess.run(['git', 'show', f'{a.commit}:src/tune/params.hpp'], capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parents[2])
    if header.returncode:
        raise Refused(f'cannot read src/tune/params.hpp at {a.commit}: {header.stderr.strip()}')
    spec = resolve_spec(read_json(a.spec), table_from_header(header.stdout), a.name, a.commit)
    if a.calibration:
        spec['calibration_sha256'] = hashlib.sha256(Path(a.calibration).read_bytes()).hexdigest()
    if (folder / 'spec.json').exists():
        if read_json(folder / 'spec.json') != spec:
            raise Refused(f'{folder / "spec.json"} exists with another spec (a spec is fixed at init)')
        print(f'{a.name}: already initialised with this spec')
        return 0
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / 'spec.json', spec)
    if a.calibration:
        (folder / 'calibration.json').write_bytes(Path(a.calibration).read_bytes())
    save_state(a.name, {'iteration': 0, 'stage': 0, 'pairs_done': 0, 'opening_cursor': spec['opening_reserve'],
                        'theta': {p['name']: p['start'] for p in spec['params']}, 'burned': [], 'done': False,
                        'spec_sha256': spec_digest(spec)})
    print(f'{a.name}: initialised, {len(spec["params"])} parameters, {spec["iterations"]} iterations, '
          f'{spec["total_pairs"]} pairs, gain_end {spec["gain_end"]:.5f}')
    return 0


def checked_state(name):
    spec, state = load_spec(name), load_state(name)
    if state['spec_sha256'] != spec_digest(spec):
        raise Refused('state.json belongs to another spec')
    return spec, state


def cmd_dispatch(a):
    spec, state = checked_state(a.name)
    if state['done']:
        raise Refused('finished: nothing to dispatch')
    d = pending_stage(a.name, state)
    if d is None:
        d = state['stage']
        per = shard_plan(spec['games'], spec['shards'], spec['draw_pairs'])
        lines = per * spec['shards']
        if state['opening_cursor'] + lines - 1 > 2632036:
            raise Refused('the tuning reserve is used up')
        c = c_at(spec, state['iteration'])
        tuned = [(p['name'], state['theta'][p['name']], round(c[p['name']], 3)) for p in spec['params']]
        disp = {'label': spec['label'], 'commit': spec['commit'], 'stage': d, 'iteration': state['iteration'],
                'params': format_params(tuned, spec['fixed']), 'games': spec['games'], 'shards': spec['shards'],
                'tc': spec['tc'], 'hash': spec['hash'], 'openings': state['opening_cursor'],
                'draw_pairs': spec['draw_pairs']}
        folder = data_dir(a.name) / f'i{d}'
        folder.mkdir(parents=True, exist_ok=True)
        write_json(folder / 'dispatch.json', disp)
        state['stage'], state['opening_cursor'] = d + 1, state['opening_cursor'] + lines
        save_state(a.name, state)
    disp = read_json(data_dir(a.name) / f'i{d}' / 'dispatch.json')
    for k in ('label', 'commit', 'stage', 'iteration', 'params', 'games', 'shards', 'tc', 'hash', 'openings',
              'draw_pairs'):
        print(f'{k}={disp[k]}')
    print(f'params_sha256={hashlib.sha256(disp["params"].encode()).hexdigest()}')
    return 0


def verify_shards(disp, results):
    """The draws of one run, in order, after checking that the results are exactly the dispatched run's:
    every shard present and done, every meta field as dispatched, the opening ranges as planned, and every
    draw's signs and values those its seed gives."""
    shards, k = int(disp['shards']), int(disp['draw_pairs'])
    per = shard_plan(int(disp['games']), shards, k)
    tuned, _ = parse_params(disp['params'])
    want = {'label': disp['label'], 'commit': disp['commit'], 'stage': str(disp['stage']),
            'params': disp['params'], 'tc': disp['tc'], 'hash': str(disp['hash']), 'tables': '3-4-5',
            'draw_pairs': str(k), 'shards': str(shards)}
    by_shard = {}
    for res in results:
        meta = res.get('meta', {})
        for key, value in want.items():
            if str(meta.get(key)) != value:
                raise Refused(f'a shard result has {key}={meta.get(key)!r}, not the dispatched {value!r}')
        shard = int(meta['shard'])
        if shard in by_shard:
            raise Refused(f'shard {shard} appears twice')
        by_shard[shard] = res
    if sorted(by_shard) != list(range(shards)):
        raise Refused(f'shard results {sorted(by_shard)}, not 0-{shards - 1}')
    books = {res['meta'].get('book_sha') for res in results}
    if len(books) != 1:
        raise Refused('the shards played different books')
    records = []
    for shard in range(shards):
        res = by_shard[shard]
        if res.get('status') != 'done':
            raise Refused(f'shard {shard} is {res.get("status")!r}, not done')
        start = int(disp['openings']) + shard * per
        if (int(res['meta']['opening_start']), int(res['meta']['opening_end'])) != (start, start + per - 1):
            raise Refused(f'shard {shard} played openings {res["meta"]["opening_start"]}-'
                          f'{res["meta"]["opening_end"]}, not {start}-{start + per - 1}')
        recs = sorted(res['records'], key=lambda r: r['index'])
        if [r['index'] for r in recs] != list(range(per // k)):
            raise Refused(f'shard {shard} has draws {[r["index"] for r in recs]}, not 0-{per // k - 1}')
        for r in recs:
            signs, plus, minus = perturbed_values(pair_seed(disp['label'], disp['commit'], disp['stage'], shard,
                                                            r['index']), tuned)
            if (r['signs'], r['plus'], r['minus']) != (''.join('+' if s > 0 else '-' for s in signs), plus, minus):
                raise Refused(f'shard {shard} draw {r["index"]}: signs or values differ from its seed')
            if r['line'] != start + r['index'] * k or sum(r['ptnml']) != k:
                raise Refused(f'shard {shard} draw {r["index"]}: opening line or pair count not as planned')
            records.append(r)
    return records


def collect_stage_results(folder):
    files = sorted(Path(folder).rglob('result.json'))
    return [read_json(f) for f in files]


def cmd_step(a):
    spec, state = checked_state(a.name)
    folder = data_dir(a.name) / f'i{a.stage}'
    disp = read_json(folder / 'dispatch.json')
    done = [line for line in log_lines(a.name) if line.get('stage') == a.stage]
    if pending_stage(a.name, state) != a.stage and not done:
        raise Refused(f'stage {a.stage} is not the pending stage')
    records = verify_shards(disp, collect_stage_results(folder))
    tuned, _ = parse_params(disp['params'])
    theta = {n: t for n, t, _ in tuned}
    hist = history(a.name)
    # The first pair's gain index: the pairs of the updates before this one.
    stages = [h.get('stage') for h in hist]
    if done and a.stage not in stages:
        raise Refused(f'stage {a.stage} was rewound away')
    before = hist if not done else hist[:stages.index(a.stage)]
    first = sum(h['pairs'] for h in before)
    out = iteration_step(spec, theta, int(disp['iteration']), records, first)
    ptnml = [sum(r['ptnml'][i] for r in records) for i in range(5)]
    line = {'iteration': int(disp['iteration']), 'stage': a.stage, 'params_sha256':
            hashlib.sha256(disp['params'].encode()).hexdigest(), 'ptnml': ptnml, 'theta_before': theta,
            'time_losses': sum(r.get('time_losses', 0) for r in records),
            'abnormal': sum(r.get('abnormal', 0) for r in records), **out}
    run_id = folder / 'run_id'
    if run_id.exists():
        line['run_id'] = int(run_id.read_text().strip())
    meta = dict(kv.split('=', 1) for kv in a.meta)
    if 'wall_minutes' in meta:
        line['wall_minutes'] = float(meta['wall_minutes'])
        line['games_per_minute'] = 2 * out['pairs'] / line['wall_minutes'] if line['wall_minutes'] > 0 else 0.0
    if done:
        old = {k: v for k, v in done[-1].items() if k not in ('wall_minutes', 'games_per_minute')}
        new = {k: v for k, v in line.items() if k not in ('wall_minutes', 'games_per_minute')}
        if json.loads(json.dumps(old)) != json.loads(json.dumps(new)):
            raise Refused(f'stage {a.stage} is already logged with another result')
    else:
        with open(data_dir(a.name) / 'iterations.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(line, sort_keys=True) + '\n')
    # The commit point: the state follows the log line (a crash before this repeats only this write).
    if state['iteration'] == line['iteration']:
        state['iteration'] += 1
        state['pairs_done'] = first + out['pairs']
        state['theta'] = out['theta_after']
        state['done'] = state['iteration'] >= spec['iterations']
        save_state(a.name, state)
    print(f'iteration {line["iteration"]} (stage {a.stage}): {out["pairs"]} pairs, ptnml {ptnml}, '
          f'clamped {",".join(out["clamped"]) or "none"}')
    for p in spec['params']:
        n = p['name']
        print(f'  {n}: {theta[n]:.3f} -> {out["theta_after"][n]:.3f} (step {out["step"][n]:+.3f}, '
              f'z {out["z"][n]:+.2f})')
    if state['done']:
        print('finished: run spsa.py report')
    return 0


def cmd_report(a):
    spec, state = checked_state(a.name)
    hist = history(a.name)
    theta = final_theta([h['theta_after'] for h in hist], spec['average_tail'])
    clamps = {p['name']: sum(p['name'] in h['clamped'] for h in hist) for p in spec['params']}
    limited = step_limited(clamps, len(hist))
    print(f'{a.name}: {len(hist)} of {spec["iterations"]} updates, {sum(h["pairs"] for h in hist)} pairs')
    print('| parameter | start | final (mean of last updates) | in c | c | clamped | trajectory |')
    print('|---|---|---|---|---|---|---|')
    for p in spec['params']:
        n = p['name']
        traj = ' '.join(f'{h["theta_after"][n]:.1f}' for h in hist)
        print(f'| {n} | {p["start"]:g} | {theta[n]:.2f} ({round(theta[n])}) | {(theta[n] - p["start"]) / p["c"]:+.2f} '
              f'| {p["c"]:g} | {clamps[n]} | {traj} |')
    if limited:
        print(f'step-limited (clamped in at least 2/3 of the updates): {", ".join(limited)}')
    write_json(data_dir(a.name) / 'final.json', {'label': spec['label'], 'commit': spec['commit'],
                                                  'iterations': len(hist), 'theta': theta,
                                                  'params': {k: round(v) for k, v in theta.items()},
                                                  'clamped': clamps})
    return 0


def cmd_rewind(a):
    spec, state = checked_state(a.name)
    hist = history(a.name)
    if not -1 <= a.to < len(hist):
        raise Refused(f'--to must be -1 to {len(hist) - 1}')
    d = pending_stage(a.name, state)
    if d is not None:
        state['burned'].append(d)
    theta = hist[a.to]['theta_after'] if a.to >= 0 else {p['name']: p['start'] for p in spec['params']}
    with open(data_dir(a.name) / 'iterations.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'rewind': a.to, 'stage': None}, sort_keys=True) + '\n')
    state.update(iteration=a.to + 1, theta=theta, done=False,
                 pairs_done=sum(h['pairs'] for h in hist[:a.to + 1]))
    save_state(a.name, state)
    print(f'{a.name}: back to the state after iteration {a.to}' + (f'; stage {d} abandoned' if d is not None else ''))
    return 0


def cmd_merge(a):
    results = [read_json(f) for f in a.files]
    records = [r for res in results for r in res.get('records', [])]
    ptnml = [sum(r['ptnml'][i] for r in records) for i in range(5)]
    tuned, _ = parse_params(results[0]['meta']['params']) if results else ([], {})
    count, _, squares = pair_scores(ptnml)
    print(f'shards {len(results)} ({", ".join(sorted({res.get("status", "?") for res in results}))}); pairs {count}, '
          f'ptnml (theta+ against theta-) {ptnml}, time losses {sum(r.get("time_losses", 0) for r in records)}, '
          f'abnormal {sum(r.get("abnormal", 0) for r in records)}')
    grad = {}
    for i, (name, _, _) in enumerate(tuned):
        grad[name] = sum(pair_scores(r['ptnml'])[1] * (1 if r['signs'][i] == '+' else -1) for r in records)
        z = grad[name] / math.sqrt(squares) if squares > 0 else 0.0
        print(f'  {name}: sum {grad[name]:+.2f}, z {z:+.2f}')
    if a.json:
        write_json(a.json, {'ptnml': ptnml, 'pairs': count, 'grad_sum': grad})
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('init')
    s.add_argument('name')
    s.add_argument('--spec', required=True)
    s.add_argument('--commit', required=True)
    s.add_argument('--calibration')
    s = sub.add_parser('dispatch')
    s.add_argument('name')
    s = sub.add_parser('step')
    s.add_argument('name')
    s.add_argument('--stage', type=int, required=True)
    s.add_argument('--meta', action='append', default=[])
    s = sub.add_parser('report')
    s.add_argument('name')
    s = sub.add_parser('rewind')
    s.add_argument('name')
    s.add_argument('--to', type=int, required=True)
    s = sub.add_parser('merge')
    s.add_argument('files', nargs='+')
    s.add_argument('--json')
    a = ap.parse_args(argv)
    try:
        return {'init': cmd_init, 'dispatch': cmd_dispatch, 'step': cmd_step, 'report': cmd_report,
                'rewind': cmd_rewind, 'merge': cmd_merge}[a.cmd](a)
    except Refused as e:
        print(f'spsa: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
