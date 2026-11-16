# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the factorial removal round's design, permutation and fit (tools/github/factorial_fit.py; design
docs/research/phase4-designs/factorial-removal-round.md). Oracles: exact rational arithmetic (fractions) for
the matrix inverse and the least-squares solution, numerical integration of the chi-square density for its
tail, the normal equations and the marginal likelihood's own maximum for the empirical-Bayes fit, and
synthetic pentanomials built to be exactly additive. In tools/cloud beside sprt_merge.py's tests, so the quick
check's tool tests (scripts/check.sh, unittest discovery of tools/cloud) run it.

    python3 -m unittest discover -s tools/cloud -p 'test_factorial_fit.py'
"""
import io
import json
import math
import os
import random
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
GITHUB = HERE.parent / 'github'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GITHUB))

import factorial_fit as ff  # noqa: E402
import sprt_merge as sm  # noqa: E402

# Design §2's factor set (k = 8) and §4.1 step 2's pilot (k = 4), in the design's order.
SCREEN = ['UseAspiration', 'UseMateDistance', 'UseSeeQuiesce', 'UseHistoryMalus', 'UseLmp', 'UseTtEvalRefine',
          'UseLmrInCheck', 'UseLmrCheckRelief']
PILOT = ['UseLmrCheckRelief', 'UseLmrInCheck', 'UseAspiration', 'UseMateDistance']
BASE = [5, 10, 20, 10, 5]  # 50 pairs, mean pair score exactly 1/2


def exact_inverse(a):
    """Gauss-Jordan on Fractions (the oracle)."""
    k = len(a)
    m = [[Fraction(x) for x in row] + [Fraction(int(i == j)) for j in range(k)] for i, row in enumerate(a)]
    for c in range(k):
        p = next(r for r in range(c, k) if m[r][c] != 0)
        m[c], m[p] = m[p], m[c]
        piv = m[c][c]
        m[c] = [x / piv for x in m[c]]
        for r in range(k):
            if r != c and m[r][c] != 0:
                f = m[r][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [row[k:] for row in m]


def design_of(factors, m, rows):
    return {'format': ff.FORMAT, 'factors': factors, 'm': m, 'rows': rows}


def shard(name, design, stage, shard_index, ptnml, row=None, opts=None, digest=None, status='done'):
    """A complete shard result as run_shard.sh writes it, playing the permutation's row unless told otherwise."""
    perm = ff.permutation(name, stage, len(design['rows']))
    r = perm[shard_index] if row is None else row
    n = len(design['rows'])
    start = 1 + (stage * n + shard_index) * 50
    return {'ptnml': list(ptnml), 'pairs': sum(ptnml), 'finished_games': 2 * sum(ptnml), 'time_losses': 0,
            'abnormal': 0, 'status': status,
            'meta': {'base': 'a' * 40, 'test': 'a' * 40, 'tc': '8+0.08', 'hash': '16', 'base_opts': '',
                     'test_opts': ff.row_opts(design, r) if opts is None else opts, 'tables': '3-4-5',
                     'book_sha': 'x', 'stage': str(stage), 'shard': str(shard_index), 'shards': str(n),
                     'rounds': str(sum(ptnml)), 'opening_start': str(start), 'opening_end': str(start + 49),
                     'row': str(r), 'design': ff.design_digest(design) if digest is None else digest}}


def shifted(shift, base=BASE):
    """BASE with `shift` pairs moved from the 1/2 bucket to 3/4 (positive) or 1/4 (negative): the mean pair
    score moves by exactly shift * 0.25 / 50."""
    p = list(base)
    if shift >= 0:
        p[2] -= shift
        p[3] += shift
    else:
        p[2] += shift
        p[1] -= shift
    return p


def additive_stages(name, design, effects, stages, wobble=None):
    """Shards whose pentanomials follow an additive model exactly: each switch off moves effects[j] pairs.
    wobble(stage, row) adds a further shift (non-additivity)."""
    out = []
    for stage in range(stages):
        perm = ff.permutation(name, stage, len(design['rows']))
        for s, r in enumerate(perm):
            shift = sum(e for e, x in zip(effects, design['rows'][r]) if x)
            if wobble:
                shift += wobble(stage, r)
            out.append(shard(name, design, stage, s, shifted(shift)))
    return out


class PermutationTests(unittest.TestCase):
    def test_a_permutation_fixed_by_name_and_stage(self):
        p = ff.permutation('r30-main', 3, 16)
        self.assertEqual(sorted(p), list(range(16)))
        self.assertEqual(p, ff.permutation('r30-main', 3, 16))
        self.assertNotEqual(p, ff.permutation('r30-main', 4, 16))
        self.assertNotEqual(p, ff.permutation('r30-other', 3, 16))

    def test_every_row_reaches_every_shard_about_equally(self):
        # 3,200 stages: each (shard, row) count is binomial(3200, 1/16), mean 200, sd 13.7; 5 sd either way.
        counts = [[0] * 16 for _ in range(16)]
        for stage in range(3200):
            for s, r in enumerate(ff.permutation('uniformity', stage, 16)):
                counts[s][r] += 1
        flat = [c for row in counts for c in row]
        self.assertTrue(all(131 <= c <= 269 for c in flat), (min(flat), max(flat)))

    def test_stage_rows_follow_the_permutation(self):
        d = design_of(PILOT, 2, [[1, 1, 0, 0], [0, 1, 1, 0], [0, 0, 1, 1], [1, 0, 0, 1]])
        t = ff.stage_rows(d, 'p', 5)
        perm = ff.permutation('p', 5, 4)
        self.assertEqual([e['row'] for e in t['shard_rows']], perm)
        self.assertEqual(t['shard_rows'][0]['opts'], ff.row_opts(d, perm[0]))
        self.assertEqual(ff.row_opts(d, 1), 'option.UseLmrInCheck=false option.UseAspiration=false')
        self.assertEqual(t['design'], ff.design_digest(d))


class LinearAlgebraTests(unittest.TestCase):
    def test_inverse_matches_exact_arithmetic(self):
        rnd = random.Random(7)
        for _ in range(20):
            rows = [[int(rnd.random() < 0.4) for _ in range(6)] for _ in range(14)]
            g = ff._gram(rows)
            if ff.a_value(rows) == math.inf:
                continue
            inv, exact = ff._inverse_spd(g), exact_inverse(g)
            for i in range(6):
                for j in range(6):
                    self.assertAlmostEqual(inv[i][j], float(exact[i][j]), places=9)

    def test_singular_designs(self):
        self.assertEqual(ff.a_value([[1, 1, 0], [1, 1, 0], [0, 0, 1]]), math.inf)
        with self.assertRaises(ff.Refused):
            ff.check_design(design_of(['A', 'B', 'C'], 2, [[1, 1, 0], [1, 1, 0], [1, 1, 0]]))


class DesignTests(unittest.TestCase):
    def test_check_design_refusals(self):
        good = design_of(['A', 'B'], 1, [[1, 0], [0, 1]])
        ff.check_design(good)
        for bad in (dict(good, format='other'), dict(good, factors=['A', 'A']), dict(good, factors=['A', 'b c']),
                    dict(good, m=0), dict(good, rows=[[1, 0]]), dict(good, rows=[[1, 0], [1, 1]]),
                    dict(good, rows=[[1, 0], [0, 2]]), dict(good, rows=[[True, False], [False, True]])):
            with self.assertRaises(ff.Refused):
                ff.check_design(bad)

    def test_digest_ignores_the_search_record(self):
        d = design_of(['A', 'B'], 1, [[1, 0], [0, 1]])
        self.assertEqual(ff.design_digest(d), ff.design_digest(dict(d, search={'seed': 'x'})))
        self.assertNotEqual(ff.design_digest(d), ff.design_digest(dict(d, rows=[[0, 1], [1, 0]])))

    def test_search_finds_a_local_optimum_at_least_as_good_as_random(self):
        d = ff.search(PILOT, 2, 16, 'unit-test', 3)
        ff.check_design(d)
        self.assertTrue(all(sum(x) == 2 for x in d['rows']))
        self.assertEqual(d, ff.search(PILOT, 2, 16, 'unit-test', 3))  # seeded
        _, after = ff.exchange(d['rows'])
        self.assertAlmostEqual(after, ff.a_value(d['rows']), places=12)  # no single swap improves it
        draws = ff._Draws(b'independent random designs')
        best_random = min(ff.a_value([ff._random_row(draws, 4, 2) for _ in range(16)]) for _ in range(300))
        self.assertLessEqual(ff.a_value(d['rows']), best_random + 1e-12)
        self.assertAlmostEqual(d['search']['trace'], ff.a_value(d['rows']), places=5)

    def test_committed_designs(self):
        """The committed blocks (tools/github/factorial/): design §2's factors and §4.1's shapes, the recorded
        search reproducible from its record, and the screen at least as good as design §4.2's best random
        block (per-switch SE 4.28 nElo at 16 stages of SE 8.68 each, 16 rows: 8.68 * sqrt(16) = 34.7 per row
        and stage, so the mean SE is 34.7 / sqrt(16) * the mean relative SE)."""
        folder = GITHUB / 'factorial'
        for name, factors, m in (('screen-k8-m3.json', SCREEN, 3), ('pilot-k4-m2.json', PILOT, 2)):
            d = ff.load_design(folder / name)
            self.assertEqual((d['factors'], d['m'], len(d['rows'])), (factors, m, 16))
            rec = d['search']
            self.assertAlmostEqual(rec['trace'], ff.a_value(d['rows']), places=5)
            inv = ff._inverse_spd(ff._gram(d['rows']))
            self.assertEqual(rec['relative_se'], [round(math.sqrt(inv[j][j]), 6) for j in range(len(factors))])
        screen = ff.load_design(folder / 'screen-k8-m3.json')
        mean_rel = sum(screen['search']['relative_se']) / 8
        self.assertLessEqual(8.68 * mean_rel, 4.28)


class StatisticsTests(unittest.TestCase):
    def test_chi2_tail_against_numerical_integration(self):
        def density(x, df):
            return math.exp((df / 2 - 1) * math.log(x) - x / 2 - (df / 2) * math.log(2) - math.lgamma(df / 2))

        for df in range(1, 11):
            for x in (0.5, 2.0, 8.0, 20.09):
                hi, n = x + 200.0, 20000
                h = (hi - x) / n
                total = density(x, df) + density(hi, df)
                total += sum((4 if i % 2 else 2) * density(x + i * h, df) for i in range(1, n))
                self.assertAlmostEqual(ff.chi2_sf(x, df), total * h / 3, places=7, msg=(df, x))
        self.assertEqual(ff.chi2_sf(0, 8), 1.0)

    def test_eb_posterior_maximises_the_marginal_likelihood(self):
        values, ses = [5.0, -2.0, 9.0, 1.0, 14.0, -6.0, 3.0, 0.5], [4.0, 4.2, 3.9, 4.1, 4.0, 4.3, 3.8, 4.0]

        def ll(mu, tau):
            return -0.5 * sum(math.log(tau ** 2 + s ** 2) + (v - mu) ** 2 / (tau ** 2 + s ** 2)
                              for v, s in zip(values, ses))

        mu, tau, post = ff.eb_posterior(values, ses)
        best = ll(mu, tau)
        for dm in (-0.05, 0.05):
            self.assertGreaterEqual(best, ll(mu + dm, tau) - 1e-9)
        for dt in (-0.05, 0.05):
            self.assertGreaterEqual(best, ll(mu, max(tau + dt, 0.0)) - 1e-9)
        self.assertGreater(tau, 0)
        for v, s, p in zip(values, ses, post):
            self.assertAlmostEqual(p, (v / s ** 2 + mu / tau ** 2) / (1 / s ** 2 + 1 / tau ** 2), places=9)
            self.assertLessEqual(abs(p - mu), abs(v - mu) + 1e-12)  # shrunk towards mu

    def test_eb_posterior_without_spread_pools_everything(self):
        mu, tau, post = ff.eb_posterior([2.0, 2.0, 2.0], [4.0, 4.0, 4.0])
        self.assertEqual(tau, 0.0)
        self.assertEqual(post, [mu] * 3)
        self.assertAlmostEqual(mu, 2.0)


class FitTests(unittest.TestCase):
    design = design_of(PILOT, 2, [[1, 1, 0, 0], [0, 1, 1, 0], [0, 0, 1, 1], [1, 0, 0, 1], [1, 0, 1, 0],
                                  [0, 1, 0, 1], [1, 1, 0, 0], [0, 0, 1, 1]])

    def test_exactly_additive_data_is_recovered(self):
        effects = [-3, 2, 1, -1]  # pairs moved per switch off
        shards = additive_stages('fit', self.design, effects, 3)
        r = ff.fit(self.design, 'fit', shards)
        _, _, pooled_var = sm.moments([sum(s['ptnml'][i] for s in shards) for i in range(5)])
        scale = sm.NELO_SCALE / math.sqrt(pooled_var)
        for j, e in enumerate(effects):
            self.assertAlmostEqual(r['switches'][j]['value_nelo'], -(e * 0.25 / 50) * scale, places=9)
        self.assertLess(r['lack_of_fit']['chi2'], 1e-12)
        self.assertEqual(r['lack_of_fit']['df'], 8 - 4)
        self.assertFalse(r['lack_of_fit']['rejects_additivity'])
        decisions = [s['rule_a'] for s in r['switches']]
        self.assertEqual(decisions, ['keep', 'remove (subject to the guard)', 'remove (subject to the guard)', 'keep'])

    def test_least_squares_against_exact_arithmetic(self):
        """Non-additive data: b and Cov(b) from Fractions (the weights computed independently here)."""
        shards = additive_stages('fit2', self.design, [-2, 1, 0, 3], 2, wobble=lambda stage, r: (r * 3 + stage) % 4 - 1)
        r = ff.fit(self.design, 'fit2', shards)
        xs, ys, ws = [], [], []
        for s in shards:
            p = [Fraction(c) for c in s['ptnml']]
            n = sum(p)
            mean = sum(c * Fraction(i, 4) for i, c in enumerate(p)) / n
            var = sum(c * (Fraction(i, 4) - mean) ** 2 for i, c in enumerate(p)) / n
            xs.append(self.design['rows'][int(s['meta']['row'])])
            ys.append(mean - Fraction(1, 2))
            ws.append(n / var)
        k = 4
        g = [[sum(w * x[i] * x[j] for x, w in zip(xs, ws)) for j in range(k)] for i in range(k)]
        cov = exact_inverse(g)
        xty = [sum(w * x[j] * y for x, y, w in zip(xs, ys, ws)) for j in range(k)]
        b = [sum(cov[i][j] * xty[j] for j in range(k)) for i in range(k)]
        _, _, pooled_var = sm.moments([sum(s['ptnml'][i] for s in shards) for i in range(5)])
        scale = sm.NELO_SCALE / math.sqrt(pooled_var)
        for j in range(k):
            self.assertAlmostEqual(r['switches'][j]['value_nelo'], -float(b[j]) * scale, places=9)
            self.assertAlmostEqual(r['switches'][j]['se_nelo'], math.sqrt(float(cov[j][j])) * scale, places=9)
        # Lack of fit: the row means against the model, independently.
        chi2 = Fraction(0)
        for row in range(len(self.design['rows'])):
            idx = [t for t, s in enumerate(shards) if int(s['meta']['row']) == row]
            w_r = sum(ws[t] for t in idx)
            ybar = sum(ws[t] * ys[t] for t in idx) / w_r
            pred = sum(self.design['rows'][row][j] * b[j] for j in range(k))
            chi2 += w_r * (ybar - pred) ** 2
        self.assertAlmostEqual(r['lack_of_fit']['chi2'], float(chi2), places=9)
        self.assertGreater(r['lack_of_fit']['chi2'], 0.1)
        self.assertAlmostEqual(r['lack_of_fit']['p'], ff.chi2_sf(float(chi2), 4), places=12)

    def test_gross_non_additivity_is_flagged(self):
        # Rows 0 and 6 turn the same switches off, as do rows 2 and 7: opposite shifts no additive model absorbs.
        shards = additive_stages('lof', self.design, [0, 0, 0, 0], 6,
                                 wobble=lambda stage, r: 7 if r in (0, 2) else -7 if r in (6, 7) else 0)
        r = ff.fit(self.design, 'lof', shards)
        self.assertTrue(r['lack_of_fit']['rejects_additivity'], r['lack_of_fit'])
        self.assertIn('REJECTS additivity at 1%', ff.report(r))

    def test_the_look(self):
        strong = ff.fit(self.design, 'look', additive_stages('look', self.design, [-6, -6, 6, -6], 4))
        self.assertEqual(strong['look'], 'stop')
        weak = ff.fit(self.design, 'look', additive_stages('look', self.design, [-6, 0, 6, -6], 4))
        self.assertEqual(weak['look'], 'extend')
        self.assertEqual([s['look_clear'] for s in weak['switches']], [True, False, True, True])
        self.assertIn('Look: extend (3 of 4 estimates more than 1 SE from 0)', ff.report(weak))

    def test_refusals(self):
        good = additive_stages('ref', self.design, [-1, 0, 1, 0], 2)
        wrong_row = [dict(s) for s in good]
        m = dict(wrong_row[3]['meta'])
        m['row'] = str((int(m['row']) + 1) % 8)
        wrong_row[3] = dict(wrong_row[3], meta=m)
        other_opts = [dict(s) for s in good]
        m = dict(other_opts[2]['meta'], test_opts='option.UseLmp=false')
        other_opts[2] = dict(other_opts[2], meta=m)
        other_design = [dict(s, meta=dict(s['meta'], design='0' * 64)) for s in good]
        partial = list(good)
        partial[0] = dict(partial[0], status='interrupted')
        flat = list(good)
        flat[1] = dict(flat[1], ptnml=[0, 0, 50, 0, 0])
        for bad, why in ((wrong_row, "not the permutation's row"), (other_opts, "not the permutation's row"),
                         (other_design, "not the permutation's row"), (partial, 'incomplete'),
                         (flat, 'no pair-score variance')):
            with self.assertRaises((ValueError, ff.Refused)) as ctx:
                ff.fit(self.design, 'ref', bad)
            self.assertIn(why, str(ctx.exception))
        with self.assertRaises(ValueError):
            ff.fit(self.design, 'another-name', good)  # the permutation of another run

    def test_control(self):
        shards = additive_stages('ctl', self.design, [-3, 0, 0, 0], 4)
        base = ff.fit(self.design, 'ctl', shards)
        v, se = base['switches'][0]['value_nelo'], base['switches'][0]['se_nelo']
        ref, half = -v + 2.0 * se, 4.72  # the off effect is -v; the reference 2 screen SEs away
        r = ff.fit(self.design, 'ctl', shards, control=('UseLmrCheckRelief', ref, half, 'screen'))
        self.assertAlmostEqual(r['control']['distance_se'], 2.0, places=9)
        self.assertTrue(r['control']['within'])
        r = ff.fit(self.design, 'ctl', shards, control=('UseLmrCheckRelief', -v + 3.0 * se, half, 'screen'))
        self.assertFalse(r['control']['within'])
        self.assertIn('NOT within 2.5 SE', ff.report(r))
        r = ff.fit(self.design, 'ctl', shards, control=('UseLmrCheckRelief', -v + 3.0 * se, half, 'difference'))
        both = math.sqrt(se ** 2 + (half / 1.96) ** 2)
        self.assertAlmostEqual(r['control']['distance_se'], 3.0 * se / both, places=9)
        with self.assertRaises(ff.Refused):
            ff.fit(self.design, 'ctl', shards, control=('UseLmp', 0.0, 1.0, 'screen'))


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = ff.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_search_rows_and_fit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'd.json')
            code, out, _ = self.run_cli('search', '--factors', ','.join(PILOT), '--m', '2', '--rows', '8',
                                        '--seed', 'cli', '--starts', '2', '--out', path)
            self.assertEqual(code, 0, out)
            design = ff.load_design(path)
            code, out, _ = self.run_cli('rows', '--design', path, '--name', 'cli', '--stage', '2')
            self.assertEqual((code, json.loads(out)), (0, ff.stage_rows(design, 'cli', 2)))
            files = []
            for i, s in enumerate(additive_stages('cli', design, [-4, 4, -4, 4], 2)):
                files.append(os.path.join(tmp, f'r{i}.json'))
                with open(files[-1], 'w', encoding='utf-8') as f:
                    json.dump(s, f)
            out_json = os.path.join(tmp, 'fit.json')
            code, out, err = self.run_cli('fit', '--design', path, '--name', 'cli', '--json', out_json, *files)
            self.assertEqual(code, 0, err)
            self.assertIn('Look: ', out)
            with open(out_json, encoding='utf-8') as f:
                self.assertEqual(len(json.load(f)['switches']), 4)
            code, _, err = self.run_cli('fit', '--design', path, '--name', 'cli', '--control', 'UseLmp', *files)
            self.assertEqual(code, 1)
            self.assertIn('--control needs', err)
            code, _, err = self.run_cli('fit', '--design', path, '--name', 'wrong', *files)
            self.assertEqual(code, 1)
            self.assertIn("not the permutation's row", err)


if __name__ == '__main__':
    unittest.main()
