# SPDX-License-Identifier: GPL-3.0-or-later
"""The factorial removal round's design, row permutation and fit (DESIGN.md §5.6 step 18; the design:
docs/research/phase4-designs/factorial-removal-round.md, cited below as "the design" with its section).

A factorial stage plays one binary (a FORK_TUNE build, so the switches are UCI options; design §3.2) against
itself: the base side is the full engine, and each shard's test side plays one row of the design, a set of
m switches turned off (design §3.1, §3.4). The design file holds the rows; every stage plays the same rows,
permuted over the shards by a permutation derived from the run's name and stage with SHA-256 (design §3.3,
fix 2: runner CPUs differ), which the driver sends with each dispatch and the merge recomputes.

    factorial_fit.py search --factors A,B,... --m M --rows N --seed TEXT --starts S --out FILE
        an A-optimal block (the trace of (X'X)^-1 minimised by coordinate exchange from S seeded random
        starts; design §3.4), written as a design file
    factorial_fit.py rows --design FILE --name NAME --stage S
        the stage's rows in shard order, one line of JSON (sprt.yml's rows input)
    factorial_fit.py fit --design FILE --name NAME [--json OUT] [control options] RESULT.json ...
        the weighted least-squares fit of design §3.5 over the shards' pentanomials, the decision rows of
        §5.2 (rule A), the lack-of-fit statistic and the one look (§4.4)

The model (design §3.5): for shard s playing row r, y_s = (mean pair score) - 1/2 and its variance
var_s = v_s / n_s from the shard's own pentanomial (sprt_merge.moments); y_s = sum_j x_rj b_j with
x_rj = 1 when row r turns switch j off, no intercept (the base is the full engine); weights 1 / var_s.
b = (X'WX)^-1 X'Wy, Cov(b) = (X'WX)^-1. Each b_j is converted to nElo as sprt_merge.nelo converts a mean,
on the pooled pentanomial's variance v: nElo = b_j / sqrt(v) * NELO_SCALE. A switch's value is
v_j = -b_j in nElo (what switching it off loses), with its SE. Lack of fit: the row means against the
additive model, sum_r W_r (ybar_r - x_r b)^2 with W_r the row's summed weights and ybar_r its weighted
mean, chi-square with rows - k degrees of freedom (16 - 8 = 8 for the main screen, design §3.5), rejected
at the 1% level (design §5.1). Beside each estimate, a diagnostic only (design §5.2): the empirical-Bayes
posterior mean across the k switches under a normal prior N(mu, tau^2) fitted by maximum marginal
likelihood, prod N(v_j; mu, tau^2 + se_j^2) (think tank ST2's form, phase-b-specialists.md "ST2"; the
estimates' correlations are ignored there).
"""
import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'cloud'))
import sprt_merge  # noqa: E402

FORMAT = 'fork-factorial-design/1'
# Rule A (owner, 2026-11-09; design §5.2): a switch whose estimate is at or below 0 nElo is removed, subject
# to the combined guard.
REMOVAL_THRESHOLD = 0.0
# The one look (design §4.4): after the look's stages, stop if every estimate is more than 1 SE from the
# removal threshold; otherwise play on to the cap.
LOOK_SE = 1.0
# Lack of fit rejects additivity at 1% (design §5.1).
LACK_OF_FIT_LEVEL = 0.01
# The control (design §5.1): check relief's estimate within 2.5 SE of its dedicated estimate.
CONTROL_SE = 2.5
_OPTION = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')


class Refused(Exception):
    """A design, a stage's rows or a set of results that must not be used."""


# ------------------------------------------------------------------ linear algebra (small, dense)

def _inverse_spd(a):
    """The inverse of a symmetric positive definite matrix (Cholesky); Refused if it is singular."""
    k = len(a)
    scale = max(abs(a[i][i]) for i in range(k)) or 1.0
    low = [[0.0] * k for _ in range(k)]
    for i in range(k):
        for j in range(i + 1):
            s = a[i][j] - sum(low[i][t] * low[j][t] for t in range(j))
            if i == j:
                if s <= 1e-12 * scale:
                    raise Refused('the design matrix is singular (a switch cannot be estimated)')
                low[i][i] = math.sqrt(s)
            else:
                low[i][j] = s / low[j][j]
    inv_low = [[0.0] * k for _ in range(k)]  # low^-1, lower triangular
    for i in range(k):
        inv_low[i][i] = 1.0 / low[i][i]
        for j in range(i):
            inv_low[i][j] = -sum(low[i][t] * inv_low[t][j] for t in range(j, i)) / low[i][i]
    return [[sum(inv_low[t][i] * inv_low[t][j] for t in range(max(i, j), k)) for j in range(k)] for i in range(k)]


def _gram(rows, weights=None):
    k = len(rows[0])
    g = [[0.0] * k for _ in range(k)]
    for n, x in enumerate(rows):
        w = 1.0 if weights is None else weights[n]
        on = [j for j in range(k) if x[j]]
        for i in on:
            for j in on:
                g[i][j] += w * x[i] * x[j]
    return g


def a_value(rows):
    """trace((X'X)^-1) of a 0/1 design, or inf when a switch cannot be estimated."""
    try:
        return sum(_inverse_spd(_gram(rows))[j][j] for j in range(len(rows[0])))
    except Refused:
        return math.inf


# ------------------------------------------------------------------ seeded draws (SHA-256, as spsa.py's)

class _Draws:
    """Uniform integers from a SHA-256 counter stream of one seed."""

    def __init__(self, seed):
        self.seed, self.counter, self.pool = seed, 0, b''

    def _u64(self):
        if len(self.pool) < 8:
            self.pool += hashlib.sha256(self.seed + b'|' + self.counter.to_bytes(8, 'big')).digest()
            self.counter += 1
        value, self.pool = int.from_bytes(self.pool[:8], 'big'), self.pool[8:]
        return value

    def below(self, n):
        """Uniform in [0, n), by rejection (no modulo bias)."""
        limit = (2 ** 64 // n) * n
        while True:
            value = self._u64()
            if value < limit:
                return value % n


def permutation(name, stage, count):
    """The row each shard plays in this stage: shard s plays row permutation(...)[s] (design §3.3: a seed
    derived from the run's name and stage with SHA-256; Fisher-Yates)."""
    draws = _Draws(hashlib.sha256(f'factorial|{name}|{int(stage)}'.encode()).digest())
    p = list(range(count))
    for i in range(count - 1, 0, -1):
        j = draws.below(i + 1)
        p[i], p[j] = p[j], p[i]
    return p


# ------------------------------------------------------------------ the design file

def check_design(design):
    """Refused unless the design is well formed: its factors distinct option names, every row a 0/1 vector
    over them with exactly m switches off, and every switch estimable."""
    if design.get('format') != FORMAT:
        raise Refused(f'design format {design.get("format")!r} is not {FORMAT!r}')
    factors, m, rows = design.get('factors'), design.get('m'), design.get('rows')
    if not isinstance(factors, list) or not factors or len(set(factors)) != len(factors) or \
            not all(isinstance(f, str) and _OPTION.match(f) for f in factors):
        raise Refused('design factors must be distinct option names')
    k = len(factors)
    if not isinstance(m, int) or not 1 <= m <= k:
        raise Refused(f'design m {m!r} must be a whole number from 1 to {k}')
    if not isinstance(rows, list) or len(rows) < k:
        raise Refused(f'a design needs at least k = {k} rows')
    for r, x in enumerate(rows):
        if not isinstance(x, list) or len(x) != k or any(v not in (0, 1) or isinstance(v, bool) for v in x):
            raise Refused(f'design row {r} is not a 0/1 vector over the {k} factors')
        if sum(x) != m:
            raise Refused(f'design row {r} turns {sum(x)} switches off, not m = {m}')
    if a_value(rows) == math.inf:
        raise Refused('the design matrix is singular (a switch cannot be estimated)')
    return design


def load_design(path):
    with open(path, encoding='utf-8') as f:
        return check_design(json.load(f))


def design_digest(design):
    """SHA-256 of what the games depend on: the factors, m and the rows."""
    core = {'factors': design['factors'], 'm': design['m'], 'rows': design['rows']}
    return hashlib.sha256(json.dumps(core, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def row_opts(design, row):
    """The fastchess options of a row's test engine: each switch the row turns off, in the factors' order."""
    return ' '.join(f'option.{f}=false' for f, x in zip(design['factors'], design['rows'][row]) if x)


def stage_rows(design, name, stage):
    """A stage's rows in shard order (sprt.yml's rows input and the stage's dispatch record)."""
    perm = permutation(name, stage, len(design['rows']))
    return {'design': design_digest(design), 'name': name, 'stage': int(stage),
            'shard_rows': [{'row': r, 'opts': row_opts(design, r)} for r in perm]}


def expected_rows(design, name, stages):
    """{(stage, shard): (row, opts, design digest)} as strings, as the shards' meta records them."""
    digest, out = design_digest(design), {}
    for stage in stages:
        for shard, entry in enumerate(stage_rows(design, name, stage)['shard_rows']):
            out[(str(int(stage)), str(shard))] = (str(entry['row']), entry['opts'], digest)
    return out


# ------------------------------------------------------------------ the A-optimal search (design §3.4)

def _random_row(draws, k, m):
    chosen = set()
    while len(chosen) < m:
        chosen.add(draws.below(k))
    return [1 if j in chosen else 0 for j in range(k)]


def exchange(rows):
    """Coordinate exchange: swap one off switch of a row for one on switch while the trace falls; returns a
    design no single swap improves, and its trace."""
    rows = [list(x) for x in rows]
    best = a_value(rows)
    improved = True
    while improved:
        improved = False
        for x in rows:
            for off in [j for j in range(len(x)) if x[j]]:
                for on in [j for j in range(len(x)) if not x[j]]:
                    x[off], x[on] = 0, 1
                    value = a_value(rows)
                    if value < best - 1e-12:
                        best, improved = value, True
                        break
                    x[off], x[on] = 1, 0
                if improved:
                    break
            if improved:
                break
    return rows, best


def search(factors, m, n_rows, seed, starts):
    """The best design over `starts` seeded random starts, each improved by coordinate exchange."""
    k = len(factors)
    draws = _Draws(hashlib.sha256(f'factorial-search|{seed}'.encode()).digest())
    best_rows, best = None, math.inf
    for _ in range(starts):
        rows, value = exchange([_random_row(draws, k, m) for _ in range(n_rows)])
        if value < best - 1e-12:
            best_rows, best = rows, value
    if best_rows is None:
        raise Refused(f'no estimable design found for k = {k}, m = {m}, {n_rows} rows')
    inv = _inverse_spd(_gram(best_rows))
    return {'format': FORMAT, 'factors': list(factors), 'm': m, 'rows': best_rows,
            'search': {'criterion': 'A (trace of (X\'X)^-1)', 'seed': seed, 'starts': starts,
                       'trace': round(best, 6),
                       'relative_se': [round(math.sqrt(inv[j][j]), 6) for j in range(k)]}}


# ------------------------------------------------------------------ the fit (design §3.5, §5)

def chi2_sf(x, df):
    """P(chi-square with df degrees of freedom > x): Q(df/2, x/2), from Q(1/2, z) = erfc(sqrt z) or
    Q(1, z) = exp(-z) and the recurrence Q(a + 1, z) = Q(a, z) + z^a exp(-z) / Gamma(a + 1)."""
    if df <= 0:
        return math.nan
    if x <= 0:
        return 1.0
    z = x / 2
    a, q = (0.5, math.erfc(math.sqrt(z))) if df % 2 else (1.0, math.exp(-z))
    while a < df / 2 - 1e-9:
        q += math.exp(a * math.log(z) - z - math.lgamma(a + 1))
        a += 1
    return min(max(q, 0.0), 1.0)


def eb_posterior(values, ses):
    """(mu, tau, posterior means): the normal prior N(mu, tau^2) by maximum marginal likelihood of
    v_j ~ N(mu, tau^2 + se_j^2), then each v_j shrunk towards mu."""
    def profile(tau):
        w = [1 / (tau * tau + s * s) for s in ses]
        mu = sum(wi * v for wi, v in zip(w, values)) / sum(w)
        ll = -0.5 * sum(math.log(1 / wi) + wi * (v - mu) ** 2 for wi, v in zip(w, values))
        return ll, mu

    spread = max(values) - min(values)
    top = 2 * spread + max(ses)
    grid = [top * i / 2000 for i in range(2001)]
    i = max(range(len(grid)), key=lambda t: profile(grid[t])[0])
    lo, hi = grid[max(i - 1, 0)], grid[min(i + 1, len(grid) - 1)]
    for _ in range(100):  # golden section on the bracketing interval
        a = hi - (hi - lo) * 0.6180339887498949
        b = lo + (hi - lo) * 0.6180339887498949
        if profile(a)[0] < profile(b)[0]:
            lo = a
        else:
            hi = b
    tau = (lo + hi) / 2
    if profile(0.0)[0] >= profile(tau)[0]:
        tau = 0.0
    mu = profile(tau)[1]
    if tau == 0.0:
        return mu, 0.0, [mu] * len(values)
    post = [(v / (s * s) + mu / (tau * tau)) / (1 / (s * s) + 1 / (tau * tau)) for v, s in zip(values, ses)]
    return mu, tau, post


def read_results(paths):
    shards = []
    for p in paths:
        with open(p, encoding='utf-8') as f:
            shards.append(json.load(f))
    return shards


def fit(design, name, shards, control=None):
    """The fit of design §3.5 over complete shards whose rows match the recomputed permutation (the merge's
    checks, sprt_merge.merge with the rows); control: (switch, nElo, 95% half-width, basis) or None."""
    check_design(design)
    stages = sorted({int(s.get('meta', {}).get('stage', -1)) for s in shards})
    merged = sprt_merge.merge(shards, require_complete=True, rows=expected_rows(design, name, stages))
    factors, X = design['factors'], design['rows']
    k = len(factors)
    rows_of, ys, ws = [], [], []
    for s in shards:
        n, mean, var = sprt_merge.moments(s['ptnml'])
        if n == 0 or var == 0:
            meta = s.get('meta', {})
            raise Refused(f'stage {meta.get("stage")} shard {meta.get("shard")} has no pair-score variance '
                          f'({s["ptnml"]}): its weight is undefined')
        rows_of.append(int(s['meta']['row']))
        ys.append(mean - 0.5)
        ws.append(n / var)
    xs = [X[r] for r in rows_of]
    cov = _inverse_spd(_gram(xs, ws))
    xty = [sum(w * x[j] * y for x, y, w in zip(xs, ys, ws)) for j in range(k)]
    b = [sum(cov[i][j] * xty[j] for j in range(k)) for i in range(k)]
    _, _, pooled_var = sprt_merge.moments(merged['ptnml'])
    scale = sprt_merge.NELO_SCALE / math.sqrt(pooled_var)
    values = [-bj * scale for bj in b]
    ses = [math.sqrt(cov[j][j]) * scale for j in range(k)]
    # Row means against the additive model (lack of fit).
    played = sorted(set(rows_of))
    chi2, row_lines = 0.0, []
    for r in played:
        idx = [t for t, rr in enumerate(rows_of) if rr == r]
        w_r = sum(ws[t] for t in idx)
        ybar = sum(ws[t] * ys[t] for t in idx) / w_r
        pred = sum(X[r][j] * b[j] for j in range(k))
        chi2 += w_r * (ybar - pred) ** 2
        row_ptnml = [sum(shards[t]['ptnml'][i] for t in idx) for i in range(5)]
        row_lines.append({'row': r, 'off': [f for f, x in zip(factors, X[r]) if x], 'shards': len(idx),
                          'ptnml': row_ptnml, 'mean_nelo': ybar * scale, 'model_nelo': pred * scale,
                          'z': (ybar - pred) * math.sqrt(w_r)})
    df = len(played) - k
    p_value = chi2_sf(chi2, df) if df > 0 else None
    mu, tau, post = eb_posterior(values, ses)
    switches = []
    for j, f in enumerate(factors):
        switches.append({'switch': f, 'value_nelo': values[j], 'se_nelo': ses[j], 'z': values[j] / ses[j],
                         'eb_posterior_nelo': post[j],
                         'rule_a': 'remove (subject to the guard)' if values[j] <= REMOVAL_THRESHOLD else 'keep',
                         'look_clear': abs(values[j] - REMOVAL_THRESHOLD) > LOOK_SE * ses[j]})
    result = {'design': design_digest(design), 'name': name, 'stages': stages, 'shards': len(shards),
              'pooled_ptnml': merged['ptnml'], 'pooled_nelo': sprt_merge.nelo(merged['ptnml']),
              'switches': switches, 'rows': row_lines,
              'lack_of_fit': {'chi2': chi2, 'df': df, 'p': p_value,
                              'rejects_additivity': p_value is not None and p_value < LACK_OF_FIT_LEVEL},
              'eb_prior': {'mu_nelo': mu, 'tau_nelo': tau},
              'look': 'stop' if all(s['look_clear'] for s in switches) else 'extend'}
    if control is not None:
        switch, ref, half95, basis = control
        if switch not in factors:
            raise Refused(f'the control {switch} is not a factor of the design')
        j = factors.index(switch)
        ref_se = half95 / 1.96  # sprt_merge's "nElo: x +/- e" is 1.96 SE
        se = ses[j] if basis == 'screen' else math.sqrt(ses[j] ** 2 + ref_se ** 2)
        off_effect = -values[j]  # the dedicated test's sign: test = the switch off
        dist = abs(off_effect - ref)
        result['control'] = {'switch': switch, 'off_effect_nelo': off_effect, 'reference_nelo': ref,
                             'reference_half95': half95, 'basis': basis, 'se_nelo': se,
                             'distance_se': dist / se, 'within': dist <= CONTROL_SE * se}
    return result


def report(result):
    out = [f'Factorial fit: {result["name"]}, stages {result["stages"][0]}-{result["stages"][-1]} '
           f'({len(result["stages"])}), {result["shards"]} shards, design {result["design"][:12]}',
           f'Pooled: Ptnml(0-2) {result["pooled_ptnml"]}, nElo {result["pooled_nelo"]:.2f} '
           f'(every row against the full engine)',
           'switch                      value nElo     SE      z   EB posterior  rule A']
    for s in result['switches']:
        out.append(f'{s["switch"]:<26} {s["value_nelo"]:>10.2f} {s["se_nelo"]:>7.2f} {s["z"]:>6.2f} '
                   f'{s["eb_posterior_nelo"]:>13.2f}  {s["rule_a"]}')
    prior = result['eb_prior']
    out.append(f'EB prior (diagnostic): mu {prior["mu_nelo"]:.2f}, tau {prior["tau_nelo"]:.2f} nElo')
    lof = result['lack_of_fit']
    if lof['p'] is None:
        out.append(f'Lack of fit: no degrees of freedom ({len(result["rows"])} rows played, k = '
                   f'{len(result["switches"])})')
    else:
        out.append(f'Lack of fit: chi2 {lof["chi2"]:.2f} on {lof["df"]} df, p {lof["p"]:.4f}: '
                   + ('REJECTS additivity at 1%: the owner sees the row means before any removal'
                      if lof['rejects_additivity'] else 'additivity not rejected at 1%'))
    out.append('Rows (each against the full engine, nElo; negative: the row loses; z: its mean against the model):')
    out.append('row  off                                              shards  mean nElo  model nElo      z')
    for r in result['rows']:
        out.append(f'{r["row"]:>3}  {",".join(r["off"]):<48} {r["shards"]:>6} {r["mean_nelo"]:>10.2f} '
                   f'{r["model_nelo"]:>11.2f} {r["z"]:>6.2f}')
    if 'control' in result:
        c = result['control']
        out.append(f'Control {c["switch"]}: off effect {c["off_effect_nelo"]:.2f} nElo against the dedicated '
                   f'{c["reference_nelo"]:.2f} +/- {c["reference_half95"]:.2f}: {c["distance_se"]:.2f} SE '
                   f'({c["basis"]}) apart: '
                   + ('within 2.5 SE' if c['within'] else 'NOT within 2.5 SE: the method is refuted (design section 5.1)'))
    clear = sum(s['look_clear'] for s in result['switches'])
    out.append(f'Look: {result["look"]} ({clear} of {len(result["switches"])} estimates more than 1 SE from 0)')
    return '\n'.join(out)


# ------------------------------------------------------------------ the command line

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('search')
    s.add_argument('--factors', required=True)
    s.add_argument('--m', type=int, required=True)
    s.add_argument('--rows', type=int, required=True)
    s.add_argument('--seed', required=True)
    s.add_argument('--starts', type=int, required=True)
    s.add_argument('--out', required=True)
    r = sub.add_parser('rows')
    r.add_argument('--design', required=True)
    r.add_argument('--name', required=True)
    r.add_argument('--stage', type=int, required=True)
    f = sub.add_parser('fit')
    f.add_argument('files', nargs='+')
    f.add_argument('--design', required=True)
    f.add_argument('--name', required=True)
    f.add_argument('--json')
    f.add_argument('--control', help='the control switch (design §5.1: UseLmrCheckRelief)')
    f.add_argument('--control-nelo', type=float, help="its dedicated removal test's nElo (test = switch off)")
    f.add_argument('--control-half95', type=float, help="that test's 95%% half-width (sprt_merge's +/-)")
    f.add_argument('--control-basis', choices=('screen', 'difference'),
                   help="the SE of the 2.5 SE rule: the screen estimate's, or the difference's")
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'search':
            factors = [x for x in a.factors.split(',') if x]
            if a.starts < 1:
                raise Refused('--starts must be at least 1')
            design = check_design(search(factors, a.m, a.rows, a.seed, a.starts))
            with open(a.out, 'w', encoding='utf-8') as fh:
                json.dump(design, fh, indent=1)
                fh.write('\n')
            print(f'{a.out}: trace {design["search"]["trace"]}, relative SE {design["search"]["relative_se"]}, '
                  f'design {design_digest(design)}')
        elif a.cmd == 'rows':
            print(json.dumps(stage_rows(load_design(a.design), a.name, a.stage), separators=(',', ':')))
        else:
            control = None
            given = [a.control, a.control_nelo, a.control_half95, a.control_basis]
            if any(v is not None for v in given):
                if any(v is None for v in given):
                    raise Refused('--control needs --control-nelo, --control-half95 and --control-basis')
                control = (a.control, a.control_nelo, a.control_half95, a.control_basis)
            result = fit(load_design(a.design), a.name, read_results(a.files), control)
            print(report(result))
            if a.json:
                with open(a.json, 'w', encoding='utf-8') as fh:
                    json.dump(result, fh, indent=1)
    except (Refused, ValueError, KeyError, OSError) as e:
        print(f'factorial_fit.py: refused: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
