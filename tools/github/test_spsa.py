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

    def test_pinned_at_bound_flag(self):
        # Synthetic trajectories over 9 updates (a third: 3), c fixed: the reachable floor is lowest + c and
        # the ceiling highest - c. F sits on its floor 3 times (flagged), G twice (not), H only at the last
        # update (flagged, "at the end"), I at its ceiling 3 times, J near its floor but 0.05 c above it
        # (not: it is free to move), K on its floor in 3 updates under a decaying c (the floor moves).
        spec = {'c_decay': 0.0, 'params': [
            {'name': 'F', 'lowest': 40, 'highest': 160, 'c': 15}, {'name': 'G', 'lowest': 6, 'highest': 24, 'c': 1.7},
            {'name': 'H', 'lowest': 0, 'highest': 10, 'c': 2}, {'name': 'I', 'lowest': 0, 'highest': 8, 'c': 1},
            {'name': 'J', 'lowest': 50, 'highest': 200, 'c': 18.2}]}
        traj = {'F': [70, 60, 55, 55, 55, 60, 62, 63, 64], 'G': [9, 7.7, 7.7, 9, 9, 9, 9, 9, 9],
                'H': [5, 5, 5, 5, 5, 5, 5, 3, 2], 'I': [5, 6, 7, 7, 7, 6, 5, 5, 5],
                'J': [70, 69, 69.1, 69.1, 69.1, 69.1, 69.1, 69.1, 69.1]}
        hist = [{'iteration': i, 'theta_after': {k: v[i] for k, v in traj.items()}} for i in range(9)]
        self.assertEqual(spsa.pinned_at_bound(spec, hist),
                         [('F', 'floor', 55, 3, False), ('H', 'floor', 2, 1, True), ('I', 'ceiling', 7, 3, False)])
        self.assertEqual(spsa.pinned_at_bound(spec, []), [])
        # A decaying c: the floor of update i is lowest + c / (i + 2)^gamma, theta clamped there as
        # iteration_step does (rounded to 3 decimals, as the log keeps it).
        decay = {'c_decay': 0.101, 'params': [{'name': 'K', 'lowest': 10, 'highest': 100, 'c': 8}]}
        floors = [round(10 + 8 / (i + 2) ** 0.101, 3) for i in range(6)]
        hist = [{'iteration': i, 'theta_after': {'K': floors[i] if i in (1, 2) else 30.0}} for i in range(6)]
        self.assertEqual(spsa.pinned_at_bound(decay, hist), [('K', 'floor', floors[-1], 2, False)])
        hist[2]['theta_after']['K'] = floors[2] + 0.5  # off the floor by 0.5 / 8 c: no longer at it
        self.assertEqual(spsa.pinned_at_bound(decay, hist), [])

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

    def init_with(self, name, raw, *carry):
        path = Path(self.tmp) / f'{name}-spec.json'
        path.write_text(json.dumps(raw), encoding='utf-8')
        args = ['init', name, '--spec', str(path), '--commit', self.commit]
        for c in carry:
            args += ['--carry', c]
        return self.run_cli(*args)

    def finish(self, name, land, iterations=3):
        """Every iteration of an initialised SPSA on the fake shards, then its report."""
        folder = spsa.data_dir(name)
        for _ in range(iterations):
            rc, text = self.run_cli('dispatch', name)
            self.assertEqual(rc, 0, text)
            stage = int(dict(line.split('=', 1) for line in text.splitlines())['stage'])
            fake.write_run(spsa.read_json(folder / f'i{stage}' / 'dispatch.json'), folder / f'i{stage}', land)
            self.assertEqual(self.run_cli('step', name, '--stage', str(stage))[0], 0)
        self.assertEqual(self.run_cli('report', name)[0], 0)
        return spsa.read_json(folder / 'final.json')['params']

    def test_opening_limit(self):
        # A run's share of the reserve: 2 iterations of 32 pairs, a limit of exactly those 64 lines.
        raw = dict(R14_LIKE, iterations=2, stability_offset=6, opening_limit=2000001 + 64 - 1)
        for bad in (2000001 + 64 - 2, 2632037, '2000100'):
            with self.assertRaisesRegex(spsa.Refused, 'opening_limit'):
                spsa.resolve_spec(dict(raw, opening_limit=bad), self.table, 'spsa-t', 'a' * 40)
        self.assertNotIn('opening_limit', spsa.resolve_spec(R14_LIKE, self.table, 'spsa-t', 'a' * 40))
        self.assertEqual(self.init_with('spsa-l', raw)[0], 0)
        self.iterate('spsa-l')
        self.run_cli('dispatch', 'spsa-l')  # stage 1 pending, the share's last 32 lines
        self.assertEqual(self.run_cli('rewind', 'spsa-l', '--to', '0')[0], 0)  # abandoned: its lines are spent
        rc, _ = self.run_cli('dispatch', 'spsa-l')
        self.assertEqual(rc, 1)  # the next 32 lines would pass the limit
        self.assertFalse((spsa.data_dir('spsa-l') / 'i2').exists())
        self.assertEqual(spsa.load_state('spsa-l')['opening_cursor'], 2000001 + 64)

    def test_carry(self):
        land = {'RfpMargin': [70, 6, 1], 'FutilityOffset': [110, 8, 1], 'LmpQuietAllowance': [14, 1, 1]}
        # Wave 1: the two margins, finished and reported.
        self.assertEqual(self.init_with('spsa-w1', R14_LIKE)[0], 0)
        later = dict(R14_LIKE, params=[{'name': 'LmpQuietAllowance', 'c': 1}], fixed={'UseRazoring': 'true'})
        self.assertEqual(self.init_with('spsa-w2', later, 'spsa-w1')[0], 1)  # wave 1 not finished yet
        self.iterate('spsa-w1', land)
        self.assertEqual(self.run_cli('report', 'spsa-w1')[0], 0)  # a report part-way: final.json of 1 update
        self.assertEqual(self.init_with('spsa-w2', later, 'spsa-w1')[0], 1)  # still not finished
        for _ in range(2):
            self.iterate('spsa-w1', land)
        self.assertEqual(self.init_with('spsa-w2', later, 'spsa-w1')[0], 1)  # finished; final.json is stale
        self.assertEqual(self.run_cli('report', 'spsa-w1')[0], 0)
        final1 = spsa.read_json(spsa.data_dir('spsa-w1') / 'final.json')['params']
        hist = spsa.history('spsa-w1')
        want = {k: round(v) for k, v in spsa.final_theta([h['theta_after'] for h in hist], 0.3).items()}
        self.assertEqual(final1, want)
        # Wave 2 tunes another parameter on wave 1's values: they become fixed options, played by both sides.
        self.assertEqual(self.init_with('spsa-w2', dict(R14_LIKE), 'spsa-w1')[0], 1)  # tunes what it carries
        clash = dict(later, fixed={'RfpMargin': str(final1['RfpMargin'] + 1)})
        self.assertEqual(self.init_with('spsa-w2', clash, 'spsa-w1')[0], 1)  # its own fixed option differs
        self.assertEqual(self.init_with('spsa-w2', later, 'spsa-none')[0], 1)  # no such run
        self.assertFalse((spsa.data_dir('spsa-w2') / 'spec.json').exists())  # nothing written by a refusal
        rc, text = self.init_with('spsa-w2', later, 'spsa-w1')
        self.assertEqual(rc, 0, text)
        spec2 = spsa.load_spec('spsa-w2')
        self.assertEqual(spec2['fixed'], {'UseRazoring': 'true', 'RfpMargin': str(final1['RfpMargin']),
                                          'FutilityOffset': str(final1['FutilityOffset'])})
        digest = spsa.hashlib.sha256((spsa.data_dir('spsa-w1') / 'final.json').read_bytes()).hexdigest()
        self.assertEqual(spec2['carried'], [{'name': 'spsa-w1', 'final_sha256': digest}])
        self.assertEqual(self.init_with('spsa-w2', later, 'spsa-w1')[0], 0)  # the same init again: unchanged
        rc, text = self.run_cli('dispatch', 'spsa-w2')
        params = dict(line.split('=', 1) for line in text.splitlines())['params']
        self.assertEqual(spsa.parse_params(params)[1], spec2['fixed'])  # what both sides play
        folder = spsa.data_dir('spsa-w2')
        fake.write_run(spsa.read_json(folder / 'i0' / 'dispatch.json'), folder / 'i0', land)
        self.assertEqual(self.run_cli('step', 'spsa-w2', '--stage', '0')[0], 0)
        final2 = self.finish('spsa-w2', land, iterations=2)
        # Wave 3 names only wave 2: wave 1's values come along through wave 2's fixed options; naming both
        # cross-checks them.
        third = dict(R14_LIKE, params=[{'name': 'CaptureSeeFloor', 'c': 16}])
        rc, text = self.init_with('spsa-w3', third, 'spsa-w2')
        self.assertEqual(rc, 0, text)
        self.assertEqual(spsa.load_spec('spsa-w3')['fixed'],
                         dict(spec2['fixed'], LmpQuietAllowance=str(final2['LmpQuietAllowance'])))
        self.assertEqual(self.init_with('spsa-w3b', third, 'spsa-w1', 'spsa-w2')[0], 0)
        self.assertEqual(spsa.load_spec('spsa-w3b')['fixed'], spsa.load_spec('spsa-w3')['fixed'])
        # Sources that disagree: a run whose own fixed RfpMargin is not wave 1's value.
        self.assertEqual(self.init_with('spsa-odd', dict(later, fixed={'RfpMargin': str(final1['RfpMargin'] + 2)}))[0], 0)
        self.finish('spsa-odd', land)
        with self.assertRaisesRegex(spsa.Refused, 'another source'):
            spsa.carried_values(['spsa-w1', 'spsa-odd'], self.table, self.commit)
        # Another commit, a final.json that is not its log's result, a value outside the table, a screen.
        with self.assertRaisesRegex(spsa.Refused, 'tuned on'):
            spsa.carried_values(['spsa-w1'], self.table, 'b' * 40)
        path = spsa.data_dir('spsa-w1') / 'final.json'
        good = path.read_bytes()
        stale = spsa.read_json(path)
        stale['params']['RfpMargin'] += 1
        spsa.write_json(path, stale)
        with self.assertRaisesRegex(spsa.Refused, 'not its log'):
            spsa.carried_values(['spsa-w1'], self.table, self.commit)
        path.write_bytes(good)
        self.assertEqual(spsa.carried_values(['spsa-w1'], self.table, self.commit)[0],
                         {k: str(v) for k, v in final1.items()})
        narrow = dict(self.table, RfpMargin=(self.table['RfpMargin'][0], final1['RfpMargin'] + 1, 160, 6))
        with self.assertRaisesRegex(spsa.Refused, 'outside'):
            spsa.carried_values(['spsa-w1'], narrow, self.commit)
        screen = {'mode': 'screen', 'fixed': {}, 'iterations': 1, 'games': 64, 'shards': 2, 'draw_pairs': 1,
                  'tc': '8+0.08', 'hash': 16, 'pair_sd': 0.204, 'opening_reserve': 2010401,
                  'params': [{'name': 'RfpMargin', 'c': 6, 'group': 'G1a', 'placeholder': False, 'switch': 'UseRfp'}]}
        self.assertEqual(self.init_with('spsa-scr', screen)[0], 0)
        with self.assertRaisesRegex(spsa.Refused, 'screen'):
            spsa.carried_values(['spsa-scr'], self.table, self.commit)

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
        lowest = self.table['RfpMargin'][1]  # from params.hpp, whose bounds the final retune widened (2026-11-09)
        for params, why in (([{'name': 'NoSuchParam', 'c': 2}], 'not in'),
                            ([{'name': 'RfpMargin', 'c': 6, 'lowest': lowest - 10}], 'not inside'),
                            ([{'name': 'RfpMargin', 'c': 0.5}], 'below 1'),
                            ([{'name': 'RfpMargin', 'c': 6, 'start': lowest + 4}], 'inside its bounds'),
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

        # R14's committed spec resolves against this tree's table: seven of the eight margins (owner,
        # 2026-11-08: QuietSeeFloor, insensitive in the calibration, keeps its value).
        raw = json.loads((HERE / 'spsa-r14.json').read_text(encoding='utf-8'))
        spec = spsa.resolve_spec(raw, self.table, 'spsa-r14', 'a' * 40)
        self.assertEqual([p['name'] for p in spec['params']],
                         ['RfpMargin', 'FutilityOffset', 'FutilityGrowth', 'NullSurplusPerPly', 'AspirationHalfWidth',
                          'CaptureSeeFloor', 'LmpQuietAllowance'])
        self.assertEqual((spec['total_pairs'], spec['iterations'] * spec['games']), (10400, 20800))
        self.assertAlmostEqual(spec['gain_end'], 0.5 / (1.917 * 7), delta=1e-4)


def screen_spec(params, **over):
    """A resolved-looking screen spec: params as (name, start, c, c_screen, lowest, highest, group, placeholder)."""
    spec = {'mode': 'screen', 'pair_sd': 0.204, 'total_pairs': 6400, 'iterations': 8,
            'params': [{'name': n, 'start': s, 'c': c, 'c_screen': cs, 'lowest': lo, 'highest': hi, 'group': g,
                        'placeholder': ph, 'switch': 'UseX'} for n, s, c, cs, lo, hi, g, ph in params]}
    spec.update(over)
    return spec


# Design S1's candidates: the 32 class (a) STC parameters of docs/research/final-retune-expansion-2026-11-15.md
# §1.1, in its order, with its §3.1 groups; the owner's decisions of 2026-11-22 (HistoryBonusFactor and
# LmrCorrectionStrength out as inert, the two 64ths LMR terms in).
S1_CANDIDATES = [
    ('RfpMaxDepth', 'G1a'), ('RfpMargin', 'G1a'), ('NullMinDepth', 'G1a'), ('NullSurplusPerPly', 'G1a'),
    ('NullSurplusPliesMax', 'G1a'), ('FutilityMaxDepth', 'G1a'), ('FutilityOffset', 'G1a'), ('FutilityGrowth', 'G1a'),
    ('LmpMaxDepth', 'G1b'), ('LmpQuietAllowance', 'G1b'), ('LmpImprovingEighths', 'G1b'), ('SeePruneMaxDepth', 'G1b'),
    ('QuietSeeFloor', 'G1b'), ('CaptureSeeFloor', 'G1b'), ('QuiesceMoveCap', 'G1b'), ('LmrMinDepth', 'G2'),
    ('LmrMinMove', 'G2'), ('CutNodeLmrSixtyFourths', 'G2'), ('LmrNotImprovingSixtyFourths', 'G2'),
    ('HistoryBonusCap', 'G3'), ('LinearBonusPerPly', 'G3'), ('HistoryKeepQuarters', 'G3'), ('ReplyWeight', 'G3'),
    ('FollowWeight', 'G3'), ('TakeWeight', 'G3'), ('DirectCheckBonus', 'G3'), ('HistorySkipPerPly', 'G3'),
    ('HistorySkipMaxDepth', 'G3'), ('MinorDriftShare', 'G4'), ('DriftLimit', 'G4'), ('AspirationMinDepth', 'G4'),
    ('AspirationHalfWidth', 'G4')]
# §1.1's provenance column marks these nine "placeholder" (never measured).
S1_PLACEHOLDERS = {'RfpMaxDepth', 'NullMinDepth', 'NullSurplusPliesMax', 'FutilityMaxDepth', 'LmpMaxDepth',
                   'SeePruneMaxDepth', 'LmrMinDepth', 'HistoryBonusCap', 'HistorySkipMaxDepth'}
# QuietSeeFloor's calibrated c (not in spsa-r14.json, which left it out): DESIGN.md §5.2 "Perturbation sizes".
QUIET_SEE_FLOOR_C = 22.5


class SpsaScreenTest(unittest.TestCase):
    """Design S1, the zero-gain screen. Oracles: the hand-derived secant of a quadratic, -4 c (theta - x*) / w^2;
    a balanced set of sign patterns (every cross term cancels, so the estimate is exact); the hand-applied
    decision map; the design doc's candidate list."""

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

    def raw(self, **over):
        raw = {'mode': 'screen', 'fixed': {}, 'iterations': 2, 'games': 64, 'shards': 2, 'draw_pairs': 1,
               'tc': '8+0.08', 'hash': 16, 'pair_sd': 0.204, 'opening_reserve': 2010401,
               'params': [{'name': 'RfpMargin', 'c': 15, 'group': 'G1a', 'placeholder': False, 'switch': 'UseRfp'},
                          {'name': 'LmpImprovingEighths', 'c': 1, 'group': 'G1b', 'placeholder': False,
                           'switch': 'UseImprovingLmp'}]}
        raw.update(over)
        return raw

    def test_c_screen_respects_bounds(self):
        # The rule: twice c, or the room to the nearer bound if less.
        self.assertEqual(spsa.screen_c(1, 6, 3, 12), 2)
        self.assertEqual(spsa.screen_c(15, 55, 30, 160), 25)    # 25 to the floor, not 2c = 30
        self.assertEqual(spsa.screen_c(1, 1, 0, 4), 1)          # one step above the floor
        self.assertEqual(spsa.screen_c(366, 700, 350, 4000), 350)
        self.assertEqual(spsa.screen_c(5, 95, 0, 100), 5)       # the ceiling's room
        resolve = lambda raw: spsa.resolve_spec(raw, self.table, 'spsa-t', 'a' * 40)  # noqa: E731
        spec = resolve(self.raw())
        default, lowest, highest, _ = self.table['RfpMargin']
        rfp, lmp = spec['params']
        self.assertEqual(rfp['c_screen'], min(30, default - lowest, highest - default))
        self.assertEqual(lmp['c_screen'], min(2, self.table['LmpImprovingEighths'][0] - self.table['LmpImprovingEighths'][1]))
        self.assertEqual(spsa.c_at(spec, 0), {'RfpMargin': rfp['c_screen'], 'LmpImprovingEighths': lmp['c_screen']})
        self.assertNotIn('gain_end', spec)
        room = min(default - lowest, highest - default)
        ok = self.raw()
        ok['params'][0]['c_screen'] = room  # exactly the room is allowed
        self.assertEqual(resolve(ok)['params'][0]['c_screen'], room)
        for change, why in (({'c_screen': room + 0.5}, 'at most the room'), ({'c_screen': 0.5}, 'at least 1'),
                            ({'start': default}, 'default'), ({'lowest': lowest + 1}, 'default'),
                            ({'group': None}, 'group'), ({'placeholder': 'no'}, 'placeholder'),
                            ({'switch': ''}, 'switch'), ({'c': 0.5}, 'below 1')):
            bad = self.raw()
            bad['params'][0].update(change)
            bad['params'][0] = {k: v for k, v in bad['params'][0].items() if v is not None}
            with self.assertRaisesRegex(spsa.Refused, why, msg=change):
                resolve(bad)
        for key in spsa.GAIN_KEYS:
            with self.assertRaisesRegex(spsa.Refused, 'no gain', msg=key):
                resolve(self.raw(**{key: 0.5}))
        with self.assertRaisesRegex(spsa.Refused, 'mode'):
            resolve(self.raw(mode='other'))
        # Every perturbed value of every draw stays inside the range, at c_screen = the room on both sides.
        tuned = [(p['name'], p['start'], p['c_screen']) for p in spec['params']]
        for j in range(300):
            _, plus, minus = spsa.perturbed_values(spsa.pair_seed('spsa-t', 'c', 0, 0, j), tuned)
            for p, a, b in zip(spec['params'], plus, minus):
                self.assertTrue(p['lowest'] <= min(a, b) and max(a, b) <= p['highest'], (p['name'], a, b))

    def test_screen_never_moves_theta(self):
        # A steep, one-sided slope that a tuning update would follow (and clamp): the screen keeps theta.
        spec = screen_spec([('A', 50, 4, 8, 0, 100, 'G', False), ('B', 5, 2, 4, 0, 100, 'G', False)])
        records = [expected_record((1, -1), 0.25) for _ in range(40)]
        theta = {'A': 50.0, 'B': 5.0}
        out = spsa.iteration_step(spec, theta, 0, records, 0)
        self.assertEqual(out['theta_after'], theta)
        self.assertEqual((out['step'], out['clamped']), ({'A': 0.0, 'B': 0.0}, []))
        self.assertEqual(out['grad_sum'], {'A': 10.0, 'B': -10.0})
        self.assertEqual(out['pairs'], 40)
        # Through the commands: every iteration is dispatched at the defaults with c_screen, and the state's
        # theta never leaves them, on a landscape whose optimum is far away.
        path = Path(self.tmp) / 'spec.json'
        path.write_text(json.dumps(self.raw(iterations=3)), encoding='utf-8')
        self.assertEqual(self.run_cli('init', 'spsa-scr', '--spec', str(path), '--commit', self.commit)[0], 0)
        start = spsa.load_state('spsa-scr')['theta']
        self.assertEqual(start, {'RfpMargin': float(self.table['RfpMargin'][0]),
                                 'LmpImprovingEighths': float(self.table['LmpImprovingEighths'][0])})
        sent = set()
        for _ in range(3):
            rc, text = self.run_cli('dispatch', 'spsa-scr')
            self.assertEqual(rc, 0, text)
            stage = int(dict(line.split('=', 1) for line in text.splitlines())['stage'])
            folder = spsa.data_dir('spsa-scr') / f'i{stage}'
            disp = spsa.read_json(folder / 'dispatch.json')
            sent.add(disp['params'])
            fake.write_run(disp, folder, {'RfpMargin': [30, 10, 1], 'LmpImprovingEighths': [4, 1, 1]})
            self.assertEqual(self.run_cli('step', 'spsa-scr', '--stage', str(stage))[0], 0)
            self.assertEqual(spsa.load_state('spsa-scr')['theta'], start)
        spec = spsa.load_spec('spsa-scr')
        self.assertEqual(sent, {spsa.format_params([(p['name'], p['start'], p['c_screen']) for p in spec['params']], {})})
        self.assertTrue(spsa.load_state('spsa-scr')['done'])
        rc, text = self.run_cli('report', 'spsa-scr')
        self.assertEqual(rc, 0)
        self.assertIn('a screen, 3 of 3 iterations', text)
        final = spsa.read_json(spsa.data_dir('spsa-scr') / 'final.json')
        self.assertEqual(final['mode'], 'screen')
        self.assertLess(final['params']['RfpMargin']['z'], 0)  # its optimum lies below the default
        # A screened parameter's switch must be on at the commit: UseMateDistance (off since 2026-11-17) is refused.
        off = self.raw()
        off['params'][0]['switch'] = 'UseMateDistance'
        path.write_text(json.dumps(off), encoding='utf-8')
        rc = self.run_cli('init', 'spsa-off', '--spec', str(path), '--commit', self.commit)[0]
        self.assertEqual(rc, 1)
        self.assertFalse((spsa.data_dir('spsa-off') / 'spec.json').exists())

    def test_screen_recovers_known_slope_exactly(self):
        # Every sign pattern once, each pair's expected score 1/2 + k * sum_i D_i s_i: the estimate is D exactly.
        d_true = {'A': 6.0, 'B': -3.5, 'C': 0.0, 'D': 1.25}
        spec = screen_spec([(n, 50, 2, 4, 0, 100, 'G', False) for n in d_true])
        records = [expected_record(signs, K * sum(d * s for d, s in zip(d_true.values(), signs)))
                   for signs in itertools.product((1, -1), repeat=4)]
        out = spsa.iteration_step(spec, {n: 50.0 for n in d_true}, 0, records, 0)
        hist = [dict(out, ptnml=[sum(r['ptnml'][i] for r in records) for i in range(5)])]
        est = spsa.screen_estimates(spec, hist)
        for n, d in d_true.items():
            self.assertAlmostEqual(est[n]['d'], d, places=9)
            self.assertAlmostEqual(est[n]['d_c'], d * 2 / 4, places=9)  # c-units: times c / c_screen

    def test_screen_recovers_known_slope_fake_shard(self):
        # The fake shard's quadratic Elo -((v - x*) / w)^2 has the secant D = -4 c_screen (theta - x*) / w^2 at
        # c_screen. 8 iterations of 16 shards x 50 pairs (the S1 size), integer theta and c_screen (no rounding).
        land = {'A': [60, 4, 1], 'B': [97, 2, 1], 'E': [0, 30, 1]}
        rows = [('A', 50, 4, 8, 0, 100), ('B', 100, 2, 4, 0, 200), ('C', 20, 1, 2, 0, 40), ('D', 10, 1, 1, 9, 20),
                ('E', 30, 2, 3, 0, 60)]
        spec = screen_spec([r + ('G', False) for r in rows])
        theta = {r[0]: float(r[1]) for r in rows}
        d_true = {n: (-4 * cs * (theta[n] - land[n][0]) / land[n][1] ** 2 if n in land else 0.0)
                  for n, _, _, cs, _, _ in rows}
        self.assertEqual(d_true, {'A': 20.0, 'B': -12.0, 'C': 0.0, 'D': 0.0, 'E': -0.4})
        hist = []
        for it in range(8):
            disp = {'label': 'spsa-scr', 'commit': 'e' * 40, 'stage': it, 'games': 1600, 'shards': 16,
                    'draw_pairs': 1, 'openings': 2010401, 'tc': '8+0.08', 'hash': 16,
                    'params': spsa.format_params([(n, theta[n], cs) for n, _, _, cs, _, _ in rows], {})}
            records = [r for s in range(16) for r in fake.shard_result(disp, s, land)['records']]
            out = spsa.iteration_step(spec, theta, it, records, 0)
            self.assertEqual(out['theta_after'], theta)
            hist.append(dict(out, ptnml=[sum(r['ptnml'][i] for r in records) for i in range(5)]))
        est = spsa.screen_estimates(spec, hist)
        # The fake's pair-score variance: a game draws with probability 0.6, so each game's score has variance
        # 0.1 near equality, a pair's mean 0.05: SE = sqrt(0.05) / (k sqrt(6400)).
        se_fake = math.sqrt(0.05) / (K * math.sqrt(6400))
        for n, d in d_true.items():
            e = est[n]
            self.assertLess(abs(e['d'] - d), 3.5 * e['se'], (n, e, d))
            self.assertAlmostEqual(e['se'] / se_fake, 1.0, delta=0.1)
            self.assertAlmostEqual(e['z'], e['d'] / e['se'], places=12)
        c = {r[0]: r[2] / r[3] for r in rows}  # c / c_screen
        for n, e in est.items():
            self.assertAlmostEqual(e['d_c'], e['d'] * c[n], places=9)
            self.assertAlmostEqual(e['se_c'], e['se'] * c[n], places=9)
            self.assertAlmostEqual(e['planned_se_c'], 0.204 / (K * 80) * c[n], places=9)
        self.assertGreater(est['A']['z'], 2)
        self.assertLess(est['B']['z'], -2)
        # The planned SE of the design (§2.1): 0.2037 / (k sqrt 6400) = 1.77 Elo at c_screen, 0.885 in c-units at 2c.
        one = [{'pairs': 6400, 'grad_sum': {'P': 0.0}, 'ptnml': [0, 0, 6400, 0, 0]}]
        plan = spsa.screen_estimates(screen_spec([('P', 50, 2, 4, 0, 100, 'G', False)], pair_sd=0.2037), one)['P']
        self.assertAlmostEqual(plan['planned_se_c'] * 2, 1.77, delta=0.005)
        self.assertAlmostEqual(plan['planned_se_c'], 0.885, delta=0.002)

    def test_decision_map(self):
        # Hand-applied map: |z| >= 2 important, 1 <= |z| < 2 ambiguous, below 1 flat. G (big): 6 importants, so
        # its ambiguous non-placeholder is frozen and its ambiguous placeholder joins. H (small): one important,
        # so its ambiguous member joins (1 < 6). Z: one flat member, nothing joins.
        rows = [('G1', 2.0, False), ('G2', -2.5, False), ('G3', 3.0, False), ('G4', -7.0, False), ('G5', 2.2, False),
                ('G6', 2.01, False), ('G7', 1.99, False), ('G8', -1.0, True), ('G9', 0.99, True), ('G10', -0.2, False),
                ('H1', -4.0, False), ('H2', 1.5, False), ('H3', -0.5, True), ('Z1', 0.0, False)]
        spec = screen_spec([(n, 50, 1, 2, 0, 100, n[0], ph) for n, _, ph in rows])
        verdicts, groups = spsa.screen_verdicts(spec, {n: z for n, z, _ in rows})
        klass = {n: v[0] for n, v in verdicts.items()}
        self.assertEqual(klass, {'G1': 'important', 'G2': 'important', 'G3': 'important', 'G4': 'important',
                                 'G5': 'important', 'G6': 'important', 'G7': 'ambiguous', 'G8': 'ambiguous',
                                 'G9': 'flat', 'G10': 'flat', 'H1': 'important', 'H2': 'ambiguous', 'H3': 'flat',
                                 'Z1': 'flat'})
        self.assertEqual(groups, {'G': ['G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G8'], 'H': ['H1', 'H2'], 'Z': []})
        self.assertIn('placeholder', verdicts['G8'][2])
        self.assertIn('not under 6', verdicts['G7'][2])
        self.assertEqual(verdicts['G9'][1:], (False, 'frozen: screened flat'))  # a flat placeholder stays frozen
        # Five that join on their own: under 6, so the ambiguous non-placeholder joins.
        z5 = {n: z for n, z, _ in rows}
        z5['G6'] = z5['G8'] = 0.0  # G8, an ambiguous placeholder, would count too
        verdicts, groups = spsa.screen_verdicts(spec, z5)
        self.assertTrue(verdicts['G7'][1])
        self.assertIn('G7', groups['G'])

    def test_committed_s1_spec(self):
        raw = json.loads((HERE / 'spsa-s1-screen.json').read_text(encoding='utf-8'))
        spec = spsa.resolve_spec(raw, self.table, 'spsa-s1-screen', 'a' * 40)
        self.assertEqual([(p['name'], p['group']) for p in spec['params']], S1_CANDIDATES)
        self.assertEqual({p['name'] for p in spec['params'] if p['placeholder']}, S1_PLACEHOLDERS)
        names = {p['name'] for p in spec['params']}
        self.assertEqual(names & (spsa.EXCLUDED_PARAMS | {'HistoryBonusFactor', 'LmrCorrectionStrength'}), set())
        self.assertEqual((spec['iterations'], spec['games'], spec['shards'], spec['tc'], spec['total_pairs']),
                         (8, 1600, 16, '8+0.08', 6400))
        self.assertGreaterEqual(spec['opening_reserve'], 2010401)  # past R14's last line, 2,010,400
        r14 = {p['name']: p['c'] for p in json.loads((HERE / 'spsa-r14.json').read_text(encoding='utf-8'))['params']}
        r14['QuietSeeFloor'] = QUIET_SEE_FLOOR_C
        switches = spsa.switches_from_header((ROOT / 'src' / 'search' / 'searcher.hpp').read_text(encoding='utf-8'))
        self.assertFalse(switches['UseMateDistance'])  # the removal round's one removal (2026-11-17)
        for p in spec['params']:
            default, lowest, highest, step = self.table[p['name']]
            self.assertEqual(p['start'], default)
            # c: the calibration where a firing counter exists, else the fallback (owner, 2026-11-22).
            if p['name'] in spsa_calibrate.COUNTER_FOR_PARAM:
                self.assertEqual(p['c'], r14[p['name']], p['name'])
            else:
                self.assertEqual(p['c'], 1 if step == 1 else 2 * step, p['name'])
            self.assertEqual(p['c_screen'], spsa.screen_c(p['c'], default, lowest, highest), p['name'])
            self.assertTrue(switches[p['switch']], p['name'])  # its feature is on in this tree


# The final retune's groups after screen S1 (owner, 2026-11-22 and 2026-11-23, DESIGN.md decisions log): the
# members, in wave order, with NullSurplusPerPly added to G1a by the owner.
RETUNE_GROUPS = [
    ('g3', ['LinearBonusPerPly', 'HistoryKeepQuarters', 'ReplyWeight', 'FollowWeight', 'TakeWeight',
            'HistorySkipMaxDepth']),
    ('g1b', ['LmpMaxDepth', 'LmpQuietAllowance', 'LmpImprovingEighths', 'SeePruneMaxDepth', 'QuiesceMoveCap']),
    ('g2g4', ['LmrMinDepth', 'LmrMinMove', 'MinorDriftShare', 'DriftLimit', 'AspirationHalfWidth']),
    ('g1a', ['RfpMaxDepth', 'RfpMargin', 'NullMinDepth', 'FutilityMaxDepth', 'FutilityOffset', 'FutilityGrowth',
             'NullSurplusPerPly'])]
# The screen's last opening line + 1 (spsa-s1-screen's state.json opening_cursor after its 8 iterations).
S1_OPENING_END = 2010401 + 6400


class RetuneSpecTest(unittest.TestCase):
    """The four committed group specs (tools/github/spsa-<group>.json) against the owner's decisions and §3.2 of
    docs/research/final-retune-expansion-2026-11-15.md: members, c as the screen's, the settings, the
    iteration rule, A, and consecutive, non-overlapping shares of the tuning reserve after the screen."""

    def test_committed_retune_specs(self):
        table = spsa.table_from_header((ROOT / 'src' / 'tune' / 'params.hpp').read_text(encoding='utf-8'))
        s1 = {p['name']: p['c'] for p in json.loads((HERE / 'spsa-s1-screen.json').read_text(encoding='utf-8'))['params']}
        cursor = S1_OPENING_END
        seen = set()
        for key, members in RETUNE_GROUPS:
            raw = json.loads((HERE / f'spsa-{key}.json').read_text(encoding='utf-8'))
            spec = spsa.resolve_spec(raw, table, f'spsa-{key}', 'a' * 40)
            self.assertNotIn('mode', spec)  # tune mode
            self.assertEqual([p['name'] for p in spec['params']], members, key)
            self.assertEqual(seen & set(members), set())
            seen |= set(members)
            self.assertEqual(spec['fixed'], {}, key)  # later waves get theirs at init (--carry)
            p = len(members)
            iterations = max(8, math.ceil(1.9 * p))
            self.assertEqual((spec['iterations'], spec['games'], spec['shards'], spec['draw_pairs'], spec['tc'],
                              spec['hash']), (iterations, 1600, 16, 1, '8+0.08', 16), key)
            self.assertEqual(spec['total_pairs'], 800 * iterations)
            self.assertEqual(spec['stability_offset'], spec['total_pairs'] // 10)
            self.assertEqual((spec['loss_budget'], spec['pair_sd'], spec['gain_exponent'], spec['clamp_c'],
                              spec['c_decay'], spec['average_tail']), (0.5, 0.204, 0.602, 0.5, 0.0, 0.3), key)
            self.assertAlmostEqual(spec['gain_end'], 16 * 0.5 * K / (p * 0.204 ** 2), places=12)
            for q in spec['params']:
                default, lowest, highest, _ = table[q['name']]
                self.assertEqual((q['start'], q['lowest'], q['highest'], q['c']),
                                 (default, lowest, highest, s1[q['name']]), q['name'])
            # Openings: consecutive shares, each the planned pairs plus 4 iterations' spare lines.
            self.assertEqual(spec['opening_reserve'], cursor, key)
            self.assertEqual(spec['opening_limit'], cursor + spec['total_pairs'] + 3200 - 1, key)
            cursor = spec['opening_limit'] + 1
        self.assertLessEqual(cursor - 1, 2632036)
        self.assertEqual(table['HistoryKeepQuarters'][1:3], (0, 4))  # tuned within its whole range (owner 2026-11-23)


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
        # The arithmetic below on these four rows as they were when it was written (2026-11-08), so a later
        # change of a default or a bound in params.hpp (the final retune's, 2026-11-09 on) does not move it.
        table = dict(table, RfpMargin=(80, 40, 160, 6), FutilityGrowth=(70, 35, 140, 5),
                     LmpQuietAllowance=(12, 6, 24, 1), CaptureSeeFloor=(100, 50, 200, 8))

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
