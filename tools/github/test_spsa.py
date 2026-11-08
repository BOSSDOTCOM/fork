# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the SPSA arithmetic, spec and state (tools/github/spsa.py).

The oracles are independent of the code under test: the closed form of the expected update on a quadratic
Elo loss (derived by hand in the design: a balanced set of sign patterns cancels every cross term, so one
update moves x - x* by -2 a k gamma^2 2^p (x - x*)), Spall's published gain formula, hand-computed clamps,
and a simulated noisy landscape whose optimum is known.

    python -m unittest discover -s tools/github -p 'test_*.py'
"""
import contextlib
import io
import itertools
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import fake_spsa_shard as fake  # noqa: E402
import spsa  # noqa: E402
import spsa_calibrate  # noqa: E402

K = math.log(10) / 1600


def spec_for(params, **over):
    """A resolved-looking spec without a commit: params as (name, start, c, lowest, highest)."""
    spec = {'params': [{'name': n, 'start': s, 'c': c, 'lowest': lo, 'highest': hi} for n, s, c, lo, hi in params],
            'loss_budget': 0.5, 'pair_sd': 0.21, 'gain_exponent': 0.602, 'clamp_c': 0.5, 'c_decay': 0.0,
            'average_tail': 0.3, 'total_pairs': 10400, 'stability_offset': 1040}
    spec.update(over)
    spec['gain_end'] = spsa.gain_end(spec)
    spec.update({k: v for k, v in over.items() if k == 'gain_end'})
    return spec


def expected_record(signs, r):
    """One pair whose pentanomial (fractional counts) has mean score 1/2 + r, |r| <= 1/4."""
    q = abs(r) * 4
    ptnml = [0.0, 0.0, 1 - q, q, 0.0] if r >= 0 else [0.0, q, 1 - q, 0.0, 0.0]
    return {'signs': ''.join('+' if s > 0 else '-' for s in signs), 'ptnml': ptnml}


class SpsaMathTest(unittest.TestCase):
    def test_gain_end_formula(self):
        # B7's form: a / c^2 = eps / (1.917 p) in pair-score units (eps 0.5, sd 0.21).
        spec = spec_for([('A', 50, 2, 0, 100)] * 8)
        self.assertAlmostEqual(spec['gain_end'], 0.5 / (1.917 * 8), delta=2e-4)
        # Spall 1998, Sec. III-A Step 1: a_k = a / (A + k + 1)^alpha, k from 0; here a = gain_end (A + N)^alpha.
        a = spec['gain_end'] * (1040 + 10400) ** 0.602
        for n in (0, 1, 500, 10399):
            self.assertAlmostEqual(spsa.gain_at(spec, n), a / (1040 + n + 1) ** 0.602, places=12)
        self.assertAlmostEqual(spsa.gain_at(spec, 10399), spec['gain_end'], places=12)
        # c_k = c / (k + 1)^gamma with k from 0.
        decayed = spec_for([('A', 50, 2, 0, 100)], c_decay=0.101)
        self.assertAlmostEqual(spsa.c_at(decayed, 4)['A'], 2 / 5 ** 0.101, places=12)

    def test_update_matches_closed_form_quadratic(self):
        for p in (3, 8):
            gain = 0.03
            names = [f'P{i}' for i in range(p)]
            c = [2.0 + i for i in range(p)]
            w = [c[i] * (0.8 + 0.1 * i) for i in range(p)]  # gamma = c / w, different per parameter
            opt = [40.0 + i for i in range(p)]
            theta = {n: opt[i] + (1.5 - 0.4 * i) * c[i] for i, n in enumerate(names)}
            spec = spec_for([(n, theta[n], c[i], 0, 1000) for i, n in enumerate(names)], gain_exponent=0.0,
                            clamp_c=100.0, gain_end=gain)
            for it in range(10):
                x = {n: theta[n] / c[i] for i, n in enumerate(names)}
                xs = {n: opt[i] / c[i] for i, n in enumerate(names)}
                g2 = {n: (c[i] / w[i]) ** 2 for i, n in enumerate(names)}
                records = []
                for signs in itertools.product((1, -1), repeat=p):
                    d_elo = sum(-4 * g2[n] * (x[n] - xs[n]) * s for n, s in zip(names, signs))
                    records.append(expected_record(signs, K * d_elo))
                out = spsa.iteration_step(spec, theta, it, records, 0)
                for i, n in enumerate(names):
                    want = -2 * gain * K * g2[n] * 2 ** p * (x[n] - xs[n]) * c[i]
                    self.assertAlmostEqual(out['step'][n], want, places=12)
                theta = out['theta_after']
            # Ten updates: x - x* shrinks by (1 - 2^(p+1) a k gamma^2) each time (theta is kept to 1e-3).
            for i, n in enumerate(names):
                g2 = (c[i] / w[i]) ** 2
                want = opt[i] + (1.5 - 0.4 * i) * c[i] * (1 - 2 ** (p + 1) * gain * K * g2) ** 10
                self.assertAlmostEqual(theta[n], want, delta=0.01)

    def test_update_clamps_half_c(self):
        spec = spec_for([('A', 50, 4, 0, 100), ('B', 50, 2, 0, 100)], gain_end=0.5, gain_exponent=0.0)
        records = [expected_record((1, 1), 0.25) for _ in range(40)]
        out = spsa.iteration_step(spec, {'A': 50, 'B': 50}, 0, records, 0)
        # raw step: 40 pairs * 0.5 * 0.25 * c / 2 = 2.5 c, clamped to 0.5 c.
        self.assertAlmostEqual(out['step_raw']['A'], 2.5 * 4)
        self.assertEqual(out['step'], {'A': 2.0, 'B': 1.0})
        self.assertEqual(out['clamped'], ['A', 'B'])
        small = spsa.iteration_step(spec, {'A': 50, 'B': 50}, 0, records[:4], 0)
        self.assertAlmostEqual(small['step']['A'], 4 * 0.5 * 0.25 * 4 / 2)
        self.assertEqual(small['clamped'], [])

    def test_range_keeps_perturbation_inside(self):
        spec = spec_for([('A', 95, 4, 0, 100), ('B', 5, 4, 0, 100)], gain_end=0.5, gain_exponent=0.0)
        records = [expected_record((1, -1), 0.25) for _ in range(40)]
        out = spsa.iteration_step(spec, {'A': 95.0, 'B': 5.0}, 0, records, 0)
        self.assertEqual(out['theta_after'], {'A': 96.0, 'B': 4.0})  # 100 - c and 0 + c
        tuned = [('A', 96.0, 4.0), ('B', 4.0, 4.0)]
        for j in range(200):
            _, plus, minus = spsa.perturbed_values(spsa.pair_seed('spsa-t', 'c', 0, 0, j), tuned)
            self.assertTrue(all(0 <= v <= 100 for v in plus + minus))

    def test_stochastic_rounding_mean(self):
        rng = random.Random(7)
        draws = [spsa.stochastic_round(6.3, rng.random()) for _ in range(100000)]
        self.assertEqual(set(draws), {6, 7})
        self.assertAlmostEqual(sum(draws) / len(draws), 6.3, delta=3 * math.sqrt(0.21 / 100000))
        self.assertEqual(spsa.stochastic_round(6.0, 0.999), 6)
        # theta + c and theta - c share the uniform: their difference is exactly 2c when 2c is whole.
        for j in range(500):
            signs, plus, minus = spsa.perturbed_values(spsa.pair_seed('spsa-t', 'c', 1, 2, j), [('A', 10.5, 2.0)])
            self.assertEqual(plus[0] - minus[0], 4 * signs[0])

    def test_signs_reproducible(self):
        tuned = [(f'P{i}', 50.0, 3.0) for i in range(24)]
        base = spsa.perturbed_values(spsa.pair_seed('spsa-a', 'abc', 3, 1, 9), tuned)
        self.assertEqual(base, spsa.perturbed_values(spsa.pair_seed('spsa-a', 'abc', 3, 1, 9), tuned))
        for args in (('spsa-b', 'abc', 3, 1, 9), ('spsa-a', 'abd', 3, 1, 9), ('spsa-a', 'abc', 4, 1, 9),
                     ('spsa-a', 'abc', 3, 2, 9), ('spsa-a', 'abc', 3, 1, 10)):
            self.assertNotEqual(base[0], spsa.perturbed_values(spsa.pair_seed(*args), tuned)[0], args)
        plus_share = sum(s > 0 for j in range(400) for s in spsa.draw_signs(spsa.pair_seed('x', 'y', 0, 0, j), 24))
        self.assertAlmostEqual(plus_share / 9600, 0.5, delta=0.03)

    def test_noisy_quadratic_recovers(self):
        # 8 parameters, c = w (gamma 1), starts 2-3 c from the optimum, one side 3x steeper on two of them;
        # 13 updates of 800 pairs (R14's run) through the real draws, rounding and update.
        names = [f'P{i}' for i in range(8)]
        c = 5.0
        land = {n: [100.0, c, 3.0 if i < 2 else 1.0] for i, n in enumerate(names)}
        start = {n: 100.0 + (2 + (i % 2)) * c * (1 if i % 3 else -1) for i, n in enumerate(names)}
        spec = spec_for([(n, start[n], c, 0, 200) for n in names])
        theta, hist, n0 = dict(start), [], 0
        for it in range(13):
            disp = {'label': 'spsa-sim', 'commit': 'f' * 40, 'stage': it, 'games': 1600, 'shards': 16,
                    'draw_pairs': 1, 'openings': 1, 'tc': '8+0.08', 'hash': 16,
                    'params': spsa.format_params([(n, theta[n], c) for n in names], {})}
            records = [r for s in range(16) for r in fake.shard_result(disp, s, land)['records']]
            out = spsa.iteration_step(spec, theta, it, records, n0)
            n0 += out['pairs']
            theta = out['theta_after']
            hist.append(theta)
        final = spsa.final_theta(hist, 0.3)
        before = sum(abs(start[n] - 100) for n in names) / 8 / c
        after = sum(abs(final[n] - 100) for n in names) / 8 / c
        self.assertLess(after, before / 2, (before, after))

    def test_final_theta_tail_mean(self):
        hist = [{'A': float(i)} for i in range(10)]
        self.assertEqual(spsa.final_theta(hist, 0.3), {'A': 8.0})  # mean of 7, 8, 9
        self.assertEqual(spsa.final_theta(hist[:1], 0.3), {'A': 0.0})

    def test_step_limited_flag(self):
        self.assertEqual(spsa.step_limited({'A': 8, 'B': 7, 'C': 12}, 12), ['A', 'C'])
        self.assertEqual(spsa.step_limited({'A': 9, 'B': 8}, 13), ['A'])

R14_LIKE = {'params': [{'name': 'RfpMargin', 'c': 6}, {'name': 'FutilityOffset', 'c': 8}],
            'fixed': {}, 'iterations': 3, 'games': 64, 'shards': 2, 'draw_pairs': 1, 'tc': '8+0.08', 'hash': 16,
            'loss_budget': 0.5, 'pair_sd': 0.21, 'gain_exponent': 0.602, 'stability_offset': 9, 'clamp_c': 0.5,
            'c_decay': 0.0, 'average_tail': 0.3, 'opening_reserve': 2000001}


class SpsaStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = os.environ.get('SPSA_DATA')
        os.environ['SPSA_DATA'] = self.tmp
        self.commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                                     text=True).stdout.strip()
        self.table = spsa.table_from_header((ROOT / 'src' / 'tune' / 'params.hpp').read_text(encoding='utf-8'))

    def tearDown(self):
        if self.old is None:
            os.environ.pop('SPSA_DATA', None)
        else:
            os.environ['SPSA_DATA'] = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = spsa.main(list(args))
        return rc, out.getvalue()

    def start(self, name, raw=R14_LIKE):
        path = Path(self.tmp) / f'{name}-spec.json'
        path.write_text(json.dumps(raw), encoding='utf-8')
        self.assertEqual(self.run_cli('init', name, '--spec', str(path), '--commit', self.commit)[0], 0)

    def iterate(self, name, land=None, crash_after_log=False):
        rc, text = self.run_cli('dispatch', name)
        self.assertEqual(rc, 0, text)
        stage = int(dict(line.split('=', 1) for line in text.splitlines())['stage'])
        folder = spsa.data_dir(name) / f'i{stage}'
        disp = spsa.read_json(folder / 'dispatch.json')
        fake.write_run(disp, folder, land or {'RfpMargin': [70, 6, 1], 'FutilityOffset': [110, 8, 1]})
        if crash_after_log:
            saved = (spsa.data_dir(name) / 'state.json').read_bytes()
        self.assertEqual(self.run_cli('step', name, '--stage', str(stage))[0], 0)
        if crash_after_log:  # the log line is written, the state write is lost
            (spsa.data_dir(name) / 'state.json').write_bytes(saved)
        return stage

    def use(self, folder):
        """Two data folders, so one SPSA (same name, same seeds) can run twice."""
        os.environ['SPSA_DATA'] = str(Path(self.tmp) / folder)

    def test_step_idempotent_after_crash(self):
        self.use('a')
        self.start('spsa-a')
        self.iterate('spsa-a')
        a = spsa.load_state('spsa-a')
        self.use('b')
        self.start('spsa-a')
        stage = self.iterate('spsa-a', crash_after_log=True)
        self.assertEqual(spsa.load_state('spsa-a')['iteration'], 0)
        self.assertEqual(self.run_cli('step', 'spsa-a', '--stage', str(stage))[0], 0)
        self.assertEqual(len(spsa.history('spsa-a')), 1)
        b = spsa.load_state('spsa-a')
        self.assertEqual(a, b)
        self.assertEqual(b['iteration'], 1)
        # A third call changes nothing.
        self.assertEqual(self.run_cli('step', 'spsa-a', '--stage', str(stage))[0], 0)
        self.assertEqual(spsa.load_state('spsa-a'), b)
        self.assertEqual(len(spsa.log_lines('spsa-a')), 1)

    def test_resume_equals_uninterrupted(self):
        self.use('one')
        self.start('spsa-s')
        for _ in range(3):
            self.iterate('spsa-s')
        one = spsa.load_state('spsa-s')
        self.assertTrue(one['done'])
        self.assertEqual(self.run_cli('dispatch', 'spsa-s')[0], 1)  # finished
        self.assertEqual(self.run_cli('report', 'spsa-s')[0], 0)
        self.assertEqual(spsa.read_json(spsa.data_dir('spsa-s') / 'final.json')['iterations'], 3)
        self.use('two')
        self.start('spsa-s')
        self.iterate('spsa-s')
        # Interrupted after a dispatch: the next dispatch hands out the same pending stage.
        rc, first = self.run_cli('dispatch', 'spsa-s')
        rc, again = self.run_cli('dispatch', 'spsa-s')
        self.assertEqual(first, again)
        folder = spsa.data_dir('spsa-s') / 'i1'
        fake.write_run(spsa.read_json(folder / 'dispatch.json'), folder,
                       {'RfpMargin': [70, 6, 1], 'FutilityOffset': [110, 8, 1]})
        self.assertEqual(self.run_cli('step', 'spsa-s', '--stage', '1')[0], 0)
        self.iterate('spsa-s')
        self.assertEqual(spsa.load_state('spsa-s'), one)

        # A rewind abandons the pending stage; stage indices and openings never rewind.
        self.use('three')
        self.start('spsa-r')
        self.iterate('spsa-r')
        theta1 = spsa.load_state('spsa-r')['theta']
        self.iterate('spsa-r')
        self.run_cli('dispatch', 'spsa-r')  # stage 2 pending
        self.assertEqual(self.run_cli('rewind', 'spsa-r', '--to', '0')[0], 0)
        state = spsa.load_state('spsa-r')
        self.assertEqual((state['iteration'], state['theta'], state['burned']), (1, theta1, [2]))
        self.assertEqual(self.run_cli('step', 'spsa-r', '--stage', '2')[0], 1)  # abandoned
        stage = self.iterate('spsa-r')
        self.assertEqual(stage, 3)  # never reused
        self.assertEqual([h['stage'] for h in spsa.history('spsa-r')], [0, 3])
        cursor = spsa.read_json(spsa.data_dir('spsa-r') / 'i3' / 'dispatch.json')['openings']
        self.assertEqual(cursor, 2000001 + 3 * 32)  # the openings never rewind either

    def results(self):
        self.start('spsa-v')
        self.run_cli('dispatch', 'spsa-v')
        disp = spsa.read_json(spsa.data_dir('spsa-v') / 'i0' / 'dispatch.json')
        return disp, [fake.shard_result(disp, s, {}) for s in range(2)]

    def test_merge_refuses_foreign_meta(self):
        disp, res = self.results()
        self.assertEqual(len(spsa.verify_shards(disp, res)), 32)
        for key, value in (('commit', '0' * 40), ('params', 'RfpMargin=81.000:6.000'), ('stage', '7'),
                           ('label', 'spsa-x'), ('tc', '40+0.4')):
            bad = json.loads(json.dumps(res))
            bad[1]['meta'][key] = value
            with self.assertRaises(spsa.Refused, msg=key):
                spsa.verify_shards(disp, bad)

    def test_merge_refuses_overlapping_openings(self):
        disp, res = self.results()
        res[1]['meta']['opening_start'] = res[0]['meta']['opening_end']
        with self.assertRaisesRegex(spsa.Refused, 'played openings'):
            spsa.verify_shards(disp, res)

    def test_merge_refuses_tampered_signs(self):
        disp, res = self.results()
        res[0]['records'][3]['plus'][0] += 1
        with self.assertRaisesRegex(spsa.Refused, 'differ from its seed'):
            spsa.verify_shards(disp, res)
        disp, res = self.results()
        sign = res[1]['records'][0]['signs']
        res[1]['records'][0]['signs'] = ('-' if sign[0] == '+' else '+') + sign[1:]
        with self.assertRaisesRegex(spsa.Refused, 'differ from its seed'):
            spsa.verify_shards(disp, res)

    def test_merge_refuses_short_shard(self):
        disp, res = self.results()
        res[1]['status'] = 'short'
        with self.assertRaisesRegex(spsa.Refused, 'not done'):
            spsa.verify_shards(disp, res)
        disp, res = self.results()
        del res[1]['records'][-1]
        with self.assertRaisesRegex(spsa.Refused, 'has draws'):
            spsa.verify_shards(disp, res)
        disp, res = self.results()
        with self.assertRaisesRegex(spsa.Refused, 'shard results'):
            spsa.verify_shards(disp, res[:1])

    def test_build_flags_match_update_sh(self):
        # The tuning build configures exactly as update.sh (TCEC's build) plus -DFORK_TUNE=ON.
        def flags(path):
            text = path.read_text(encoding='utf-8')
            block = text[text.index('cmake -S'):]
            block = block[:block.index('cmake --build')]
            return {k: ('<var>' if v.lstrip('"').startswith('$') else v)
                    for k, v in re.findall(r'-D(\w+)=("?[^\s\\]+)', block)}
        update, tune = flags(ROOT / 'update.sh'), flags(HERE / 'spsa_build.sh')
        self.assertEqual(update, {'CMAKE_CXX_COMPILER': '<var>', 'CMAKE_BUILD_TYPE': 'Release', 'FORK_ARCH': '<var>',
                                  'FORK_BUILD_TESTS': 'OFF'})
        self.assertEqual(tune, dict(update, FORK_TUNE='ON'))

    def test_spec_refuses_excluded_params(self):
        resolve = lambda raw: spsa.resolve_spec(raw, self.table, 'spsa-t', 'a' * 40)  # noqa: E731
        self.assertEqual(len(resolve(R14_LIKE)['params']), 2)
        for name in sorted(spsa.EXCLUDED_PARAMS):
            self.assertIn(name, self.table)  # the list names real parameters
            with self.assertRaisesRegex(spsa.Refused, 'time management', msg=name):
                resolve(dict(R14_LIKE, params=[{'name': name, 'c': 1}]))
        for params, why in (([{'name': 'NoSuchParam', 'c': 2}], 'not in'),
                            ([{'name': 'RfpMargin', 'c': 6, 'lowest': 30}], 'not inside'),
                            ([{'name': 'RfpMargin', 'c': 0.5}], 'below 1'),
                            ([{'name': 'RfpMargin', 'c': 6, 'start': 44}], 'inside its bounds'),
                            ([{'name': 'RfpMargin', 'c': 6}, {'name': 'RfpMargin', 'c': 6}], 'twice')):
            with self.assertRaisesRegex(spsa.Refused, why):
                resolve(dict(R14_LIKE, params=params))
        with self.assertRaisesRegex(spsa.Refused, '10%'):
            resolve(dict(R14_LIKE, stability_offset=10))
        with self.assertRaisesRegex(spsa.Refused, 'reserve'):
            resolve(dict(R14_LIKE, opening_reserve=1))
        with self.assertRaisesRegex(spsa.Refused, 'spsa-'):
            spsa.resolve_spec(R14_LIKE, self.table, 'r14', 'a' * 40)
        # The params strings: tuned entries with ':c', fixed ones without.
        tuned, fixed = [('RfpMargin', 80.0, 6.0), ('LmpQuietAllowance', 12.25, 1.0)], {'UseRazoring': 'true'}
        text = spsa.format_params(tuned, fixed)
        self.assertEqual(text, 'RfpMargin=80.000:6.000,LmpQuietAllowance=12.250:1.000,UseRazoring=true')
        self.assertEqual(spsa.parse_params(text), (tuned, fixed))
        for bad in ('RfpMargin=80', 'R fp=1:1', 'A=1:1,A=2:1', 'A=1:0', 'A=x:1', 'A=1:1,B=a b'):
            with self.assertRaises(spsa.Refused, msg=bad):
                spsa.parse_params(bad)

        # R14's committed spec resolves against this tree's table.
        raw = json.loads((HERE / 'spsa-r14.json').read_text(encoding='utf-8'))
        spec = spsa.resolve_spec(raw, self.table, 'spsa-r14', 'a' * 40)
        self.assertEqual([p['name'] for p in spec['params']],
                         ['RfpMargin', 'FutilityOffset', 'FutilityGrowth', 'NullSurplusPerPly', 'AspirationHalfWidth',
                          'QuietSeeFloor', 'CaptureSeeFloor', 'LmpQuietAllowance'])
        self.assertEqual((spec['total_pairs'], spec['iterations'] * spec['games']), (10400, 20800))
        self.assertAlmostEqual(spec['gain_end'], 0.0326, delta=1e-4)



class SpsaCalibrationTest(unittest.TestCase):
    def test_calibration_interpolates_target(self):
        # The stats lines as src/search/search_bench.cpp prints them.
        text = ('stats: cuts rfp 10 null 20; prunes lmp 30 futility 40 see 50\n'
                'stats: aspiration re-searches 6, null-move surplus plies 7, quiet SEE prunes 8\n')
        self.assertEqual(spsa_calibrate.parse_stats(text),
                         {'rfp_cuts': 10, 'null_cuts': 20, 'lmp_prunes': 30, 'futility_prunes': 40, 'see_prunes': 50,
                          'aspiration_researches': 6, 'null_surplus_plies': 7, 'quiet_see_prunes': 8})
        with self.assertRaises(ValueError):
            spsa_calibrate.parse_stats(text.splitlines()[0])
        table = spsa.table_from_header((ROOT / 'src' / 'tune' / 'params.hpp').read_text(encoding='utf-8'))
        self.assertEqual(set(spsa_calibrate.COUNTER_FOR_PARAM) - set(table), set())

        # Counts linear in each value: rho(h) = slope * h, so log-linear interpolation is exact: c = target / slope.
        def bench(settings):
            v = {n: settings.get(n, table[n][0]) for n in table}
            quiet = 3000
            return {'rfp_cuts': 10000 * (1 - 0.1 / 9 * (v['RfpMargin'] - 80)),
                    'futility_prunes': 5000 * (1 + 1e-5 * (v['FutilityGrowth'] - 70)),
                    'lmp_prunes': 800 * (1 - 0.5 * (v['LmpQuietAllowance'] - 12)),
                    'quiet_see_prunes': quiet,
                    'see_prunes': quiet + 2000 * (1 + 0.1 / 12 * (v['CaptureSeeFloor'] - 100)),
                    'null_cuts': 0, 'aspiration_researches': 100, 'null_surplus_plies': 400}
        out = {e['name']: e for e in spsa_calibrate.calibrate(
            ['RfpMargin', 'FutilityGrowth', 'LmpQuietAllowance', 'CaptureSeeFloor'], table, bench, 0.10)}
        self.assertEqual((out['RfpMargin']['c'], out['RfpMargin']['insensitive']), (9.0, False))
        self.assertEqual([row[0] for row in out['RfpMargin']['points']][:2], [6, 12])
        self.assertEqual((out['CaptureSeeFloor']['c'], out['CaptureSeeFloor']['counter']),
                         (12.0, 'see_prunes - quiet_see_prunes'))
        self.assertEqual(out['LmpQuietAllowance']['c'], 1.0)  # 0.2 by the rule, raised to integer resolution
        # FutilityGrowth barely moves its count: 8 steps cut to the range (35), flagged, capped at a quarter
        # of the range.
        self.assertEqual([row[0] for row in out['FutilityGrowth']['points']], [5, 10, 20, 35])
        self.assertTrue(out['FutilityGrowth']['insensitive'])
        self.assertEqual(out['FutilityGrowth']['c'], round((140 - 35) / 4, 1))
        # Between bracketing points: log-linear interpolation.
        c, flag = spsa_calibrate.calibrated_c([(1, 0.05), (2, 0.2)], 0.1)
        self.assertAlmostEqual(c, math.sqrt(2), places=12)
        self.assertFalse(flag)

        # The engine is started by its absolute path: Windows does not start a relative path written with
        # forward slashes from the working folder (the first calibration job failed so, 2026-11-08).
        tmp = tempfile.mkdtemp()
        old_cwd, old_run = os.getcwd(), spsa_calibrate.subprocess.run
        started = []

        def fake_run(cmd, **kwargs):
            started.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='')
        try:
            os.chdir(tmp)
            os.makedirs('eng')
            Path('eng/fork.exe').write_bytes(b'')
            Path('spec.json').write_text(json.dumps({'params': [{'name': 'RfpMargin', 'c': 6}]}), encoding='utf-8')
            spsa_calibrate.subprocess.run = fake_run
            with contextlib.redirect_stderr(io.StringIO()):
                rc = spsa_calibrate.main(['--engine', 'eng/fork.exe', '--spec', 'spec.json', '--out', 'out.json'])
            self.assertEqual(rc, 1)  # the fake has no options, so it stops after the first start
            self.assertTrue(os.path.isabs(started[0][0]), started[0])
            self.assertEqual(Path(started[0][0]), (Path(tmp) / 'eng' / 'fork.exe').resolve())
        finally:
            spsa_calibrate.subprocess.run = old_run
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)

if __name__ == '__main__':
    unittest.main()
