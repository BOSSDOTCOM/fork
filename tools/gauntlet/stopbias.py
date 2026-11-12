# SPDX-License-Identifier: GPL-3.0-or-later

"""The stopping and selection bias of an adopted change's SPRT estimate (bug review 2026-11-11, T4; owner,
2026-11-11), for the transfer ratio's denominator (tools/gauntlet/report.py).

An adopted change enters the ratio with the Elo its SPRT reported when it stopped for H1. That estimate is
biased upward twice over: the test stops when its estimate is high (the stopping rule), and only passed tests
are adopted (selection on passing). This module computes both under each design's own rules, exactly (no
simulation noise) under the normal model the SPRT itself uses.

**The model** (tools/cloud/sprt_merge.py): after n game pairs the nElo estimate x is normal around the true
nElo theta with SD C / sqrt(n), C = 800 / (ln 10 sqrt 2), and LLR = n / (2 C^2) (e1 - e0) (2 x - e0 - e1)
(sprt_merge's LLR written in terms of its nElo estimate; the sample variance cancels). So each stage boundary
is a pair of limits on x, and the test is a Gaussian random walk in the sum W_k = k x_k (k stages played),
checked at stage boundaries in sprt_merge.stage_decision's order: H1 or H0 by the LLR, then the futility look
(design R: stop if x < 0 after exactly 2 stages), then the cap. The walk's sub-density over the continuation
region is carried on a lattice of spacing H (each cell's mass integrated exactly over the stage's normal step),
and the stopping probabilities and partial means are integrated exactly from each lattice point.

**The designs** (tools/github/sprt_run.sh, --kind; DESIGN.md §6, 2026-11-07 decision 2): search = design R,
[0, 6] nElo, alpha 0.05, beta 0.20, cap 8 at STC (6 at LTC by default), futility after 2 stages; network =
[0, 5], alpha = beta = 0.05, cap 13 at STC (6 at LTC), no futility. A stage is 1,600 games (800 pairs) at STC
and 1,664 (832 pairs) at LTC.

**What is computed for an adopted entry** (its design, stages played k, nElo estimate x at the stop):
- `median_unbiased(design, k, x)`: the median-unbiased estimate under the stage-wise ordering of outcomes (an
  H1 at an earlier stage is more extreme than any H1 later; at the same stage a larger x is more extreme): the
  theta at which P(H1 before stage k) + P(H1 at stage k with x_k >= x) = 1/2. It removes the stopping rule's
  share of the bias (at stage 1 it equals x); it does not remove the selection on passing.
- `pass_bias(design, theta)`: E[x at the stop | H1] - theta, the selection-and-stopping bias of a passed test
  at a fixed true effect (the bug review's simulated +7.6, +5.1, +3.2 nElo at theta 3, 6, 9 for design R).
  A per-entry correction for it needs the entry's true effect, which the test does not pin down: report.py
  gives it as a plug-in sensitivity (the bias at the entry's median-unbiased estimate), not as an unbiased
  estimate. Removing the selection bias properly needs a prior over the true effects of tested ideas
  (empirical Bayes over every SPRT, passed or not): not done here.

    stopbias.py DESIGN K NELO      (the median-unbiased estimate and the pass bias there)
"""
import math
import sys

C = 800 / (math.log(10) * math.sqrt(2))
H = 0.25  # lattice spacing of the walk's sum, nElo; tests compare it with 0.125 and with a Monte Carlo
DESIGNS = {
    'search-stc': {'e0': 0.0, 'e1': 6.0, 'alpha': 0.05, 'beta': 0.20, 'cap': 8, 'futility': 2, 'pairs': 800},
    'search-ltc': {'e0': 0.0, 'e1': 6.0, 'alpha': 0.05, 'beta': 0.20, 'cap': 6, 'futility': 2, 'pairs': 832},
    'network-stc': {'e0': 0.0, 'e1': 5.0, 'alpha': 0.05, 'beta': 0.05, 'cap': 13, 'futility': 0, 'pairs': 800},
    'network-ltc': {'e0': 0.0, 'e1': 5.0, 'alpha': 0.05, 'beta': 0.05, 'cap': 6, 'futility': 0, 'pairs': 832},
}


def _Phi(z):
    return 0.5 * math.erfc(-z / math.sqrt(2))


def _phi(z):
    return math.exp(-z * z / 2) / math.sqrt(2 * math.pi)


def limits(d, k):
    """(H0 limit, H1 limit) on the nElo estimate after k stages (sprt_merge's bounds and LLR)."""
    n = k * d['pairs']
    upper = math.log((1 - d['beta']) / d['alpha'])
    lower = math.log(d['beta'] / (1 - d['alpha']))
    mid, delta = (d['e0'] + d['e1']) / 2, d['e1'] - d['e0']
    return mid + lower * C * C / (n * delta), mid + upper * C * C / (n * delta)


def walk(d, theta, stages=None, h=H):
    """Stage by stage, for k = 1..stages (default the cap): (P(H1 at k), E[x_k; H1 at k], P(H0 at k),
    P(futility at k), the continuation lattice before stage k as (indices, masses)); and P(capped)."""
    s = C / math.sqrt(d['pairs'])
    stages = stages or d['cap']
    # Cell probabilities of one stage's step on the lattice, by index difference.
    span = int(math.ceil((abs(theta) + 9 * s) / h))
    kernel = {j: _Phi(((j + 0.5) * h - theta) / s) - _Phi(((j - 0.5) * h - theta) / s) for j in range(-span, span + 1)}
    idx, mass = [0], [1.0]
    out = []
    for k in range(1, stages + 1):
        lo, up = limits(d, k)
        lo_w, up_w = k * lo, k * up
        p1 = e1 = p0 = pf = 0.0
        for i, m in zip(idx, mass):
            w = i * h
            a = (up_w - w - theta) / s
            q = 1 - _Phi(a)
            p1 += m * q
            e1 += m * ((w + theta) * q + s * _phi(a))
            p0 += m * _Phi((lo_w - w - theta) / s)
            if d['futility'] == k and lo_w < 0:
                pf += m * (_Phi((0 - w - theta) / s) - _Phi((lo_w - w - theta) / s))
        out.append((p1, e1 / k, p0, pf, (idx, mass)))
        left = max(lo_w, 0.0) if d['futility'] == k else lo_w
        # Every cell [(j - 1/2) h, (j + 1/2) h) that overlaps the continuation region (left, up_w); the two
        # cells cut by its ends get only their inside part, so no mass is lost or counted twice.
        first, last = int(math.ceil(left / h - 0.5)), int(math.floor(up_w / h + 0.5))
        new = []
        for j in range(first, last + 1):
            a, b = max((j - 0.5) * h, left), min((j + 0.5) * h, up_w)
            t = 0.0
            if a > (j - 0.5) * h or b < (j + 0.5) * h:
                for i, m in zip(idx, mass):
                    t += m * (_Phi((b - i * h - theta) / s) - _Phi((a - i * h - theta) / s))
            else:
                for i, m in zip(idx, mass):
                    kv = kernel.get(j - i)
                    if kv:
                        t += m * kv
            new.append(t)
        idx, mass = list(range(first, last + 1)), new
    return out, sum(mass)


def outcome_probabilities(d, theta):
    """{'H1', 'H0', 'futility', 'capped'} probabilities of the whole design at a true nElo theta."""
    out, capped = walk(d, theta)
    return {'H1': sum(r[0] for r in out), 'H0': sum(r[2] for r in out), 'futility': sum(r[3] for r in out),
            'capped': capped}


def pass_bias(d, theta):
    """E[nElo estimate at the stop | H1] - theta."""
    out, _ = walk(d, theta)
    p = sum(r[0] for r in out)
    return sum(r[1] for r in out) / p - theta


def _upper_tail(d, k, x, theta, h=H):
    """P(H1 before stage k) + P(H1 at stage k with x_k >= x), the stage-wise ordering's upper tail."""
    s = C / math.sqrt(d['pairs'])
    out, _ = walk(d, theta, k, h)
    before = sum(r[0] for r in out[:-1])
    idx, mass = out[-1][4]
    c = max(k * limits(d, k)[1], k * x)
    return before + sum(m * (1 - _Phi((c - i * h - theta) / s)) for i, m in zip(idx, mass))


def median_unbiased(d, k, x, h=H, tol=0.005):
    """The theta at which the stage-wise upper tail of the observed outcome (H1 after k stages, estimate x) is
    1/2. The tail grows with theta, so a bisection finds it."""
    if not 1 <= k <= d['cap']:
        raise ValueError(f'{k} stages played: outside the design (cap {d["cap"]})')
    if x < limits(d, k)[1] - 1e-9:
        raise ValueError(f'nElo {x} after {k} stages is below the H1 limit {limits(d, k)[1]:.2f}: not a pass')
    s_k = C / math.sqrt(k * d['pairs'])
    lo, hi = x - 10 * s_k - 10, x + 10 * s_k
    while _upper_tail(d, k, x, lo, h) > 0.5:
        lo -= 10 * s_k
    while _upper_tail(d, k, x, hi, h) < 0.5:
        hi += 10 * s_k
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if _upper_tail(d, k, x, mid, h) < 0.5:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def adjust(entry):
    """For a transfer.json entry with an "sprt" record ({"design", "stages", "nelo"}): (Elo at the median-unbiased
    estimate, Elo with the pass bias at that estimate removed), each the entry's Elo scaled by the nElo ratio
    (the test's own Elo / nElo). None for an entry without one (e.g. a speed pricing)."""
    sprt = entry.get('sprt')
    if not sprt:
        return None
    d = DESIGNS[sprt['design']]
    x, elo = float(sprt['nelo']), float(entry['elo'])
    m = median_unbiased(d, int(sprt['stages']), x)
    return elo * m / x, elo * (m - pass_bias(d, m)) / x


def main(argv):
    d = DESIGNS[argv[1]]
    k, x = int(argv[2]), float(argv[3])
    m = median_unbiased(d, k, x)
    print(f'{argv[1]}, H1 after {k} stages at nElo {x}: median-unbiased {m:.2f}; '
          f'pass bias there {pass_bias(d, m):+.2f}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
