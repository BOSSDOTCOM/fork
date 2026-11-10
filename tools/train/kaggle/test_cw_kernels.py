# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of idea 69's two Kaggle kernels (docs/research/class-sampler/design.md section 14), runnable anywhere:

- cw_preflight.py: the progress-line rate, the table of ones, and the declared verdict on synthetic weights files
  (equal byte for byte; a difference within CUDA's own run-to-run noise; a difference beyond it; a slow table run;
  a table run equal to the control, so the weights would not act);
- retrain_8b_cw.py: everything but the arm is retrain 8b's own kernel (the settings, the manifests, the warm start,
  the queue of one arm with c's exact recipe and file list), and its idea 69 options and checks (the table's SHA-256,
  the exempt list = the arm's slice files).

    python -I tools/train/kaggle/test_cw_kernels.py
"""
import hashlib
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cw_preflight as pf  # noqa: E402
import retrain_8b as k8b  # noqa: E402
import retrain_8b_cw as kcw  # noqa: E402


def weights_file(path, values):
    """bullet's weights.bin layout: per record the ASCII name, 0x0A, a u64 count and that many f32s."""
    with open(path, 'wb') as f:
        for name, xs in values.items():
            f.write(name.encode() + b'\n' + struct.pack('<Q', len(xs)) + struct.pack(f'<{len(xs)}f', *xs))
    return path


class PreflightTest(unittest.TestCase):
    def test_the_rate_counts_batches_across_superbatches(self):
        # From superbatch 1 batch 128 to superbatch 2 batch 256: 305 - 128 + 256 = 433 batches in 10 s.
        self.assertEqual(pf.rate([(5.0, 1, 128), (7.0, 1, 256), (15.0, 2, 256)]), round(433 * 16384 / 10))
        self.assertIsNone(pf.rate([(5.0, 1, 128)]))

    def test_the_table_of_ones_lists_every_entry(self):
        lines = pf.ones_table().splitlines()
        self.assertEqual(len(lines), 112)
        self.assertEqual(len(set(l.rsplit(' ', 1)[0] for l in lines)), 112)
        self.assertTrue(all(l.endswith(' 1') for l in lines))

    def runs(self, d, w, speeds):
        rec = {}
        for r in pf.RUNS:
            p = weights_file(os.path.join(d, f'{r}.bin'), w[r])
            rec[r] = {'weights': p, 'sha256': hashlib.sha256(open(p, 'rb').read()).hexdigest(),
                      'positions_per_second': speeds[r]}
        return rec

    def test_the_verdict(self):
        base = {'l0w': [0.5, -0.25, 0.125], 'l1w': [1.0]}
        moved = {'l0w': [0.5, -0.25, 0.126], 'l1w': [1.0]}
        fast = dict.fromkeys(pf.RUNS, 232400)
        with tempfile.TemporaryDirectory() as d:
            ok = self.runs(d, {**dict.fromkeys(pf.RUNS, base), 'table': moved}, fast)
            v = pf.verdict(ok)
            self.assertTrue(v['pass'] and v['equal'] and v['deterministic'] and v['speed'] and v['table_acts'], v)
            # The table of ones changes the weights on a deterministic device: fail.
            v = pf.verdict(self.runs(d, {**dict.fromkeys(pf.RUNS, base), 'ones': moved, 'table': moved}, fast))
            self.assertFalse(v['pass'] or v['equal'])
            # Not deterministic: old2 differs by 1e-3; none and ones within that: pass; beyond it: fail.
            near = {'l0w': [0.5, -0.25, 0.1255], 'l1w': [1.0]}
            far = {'l0w': [0.5, -0.25, 0.13], 'l1w': [1.0]}
            w = {'old1': base, 'old2': moved, 'none': near, 'ones': near, 'table': far}
            v = pf.verdict(self.runs(d, w, fast))
            self.assertTrue(v['equal'] and not v['deterministic'] and v['pass'], v)
            v = pf.verdict(self.runs(d, {**w, 'ones': far}, fast))
            self.assertFalse(v['equal'] or v['pass'])
            # The table run 1.1% slower than the old runs' mean: fail.
            v = pf.verdict(self.runs(d, {**dict.fromkeys(pf.RUNS, base), 'table': moved}, {**fast, 'table': 229800}))
            self.assertFalse(v['speed'] or v['pass'])
            v = pf.verdict(self.runs(d, {**dict.fromkeys(pf.RUNS, base), 'table': moved}, {**fast, 'table': 230200}))
            self.assertTrue(v['speed'] and v['pass'])
            # The table run equal to old1: the weights did not act: fail.
            v = pf.verdict(self.runs(d, dict.fromkeys(pf.RUNS, base), fast))
            self.assertFalse(v['table_acts'] or v['pass'])


class ArmKernelTest(unittest.TestCase):
    def test_everything_but_the_arm_is_8bs(self):
        for name in ('ARCH', 'SCALE', 'BATCH', 'BATCHES', 'SUPERBATCHES', 'VAL_POSITIONS', 'MANIFESTS', 'VAL', 'INIT',
                     'TOLERANCE', 'WINDOW', 'KEEP', 'SEED', 'EVAL_ONLY', 'I52_POOL'):
            self.assertEqual(getattr(kcw, name), getattr(k8b, name), name)
        self.assertEqual(list(kcw.ARMS), ['cw', 'c2'])
        recipe = {k: v for k, v in kcw.ARMS['cw'].items() if k != 'cell_weights'}
        self.assertEqual(recipe, k8b.ARMS['c'])
        self.assertTrue(kcw.ARMS['cw']['cell_weights'])
        # c2: arm c with seed 2, nothing else; no loss weights; not a candidate.
        self.assertEqual({k: v for k, v in kcw.ARMS['c2'].items() if k != 'seed'}, k8b.ARMS['c'])
        self.assertEqual(kcw.ARMS['c2']['seed'], k8b.SEED + 1)
        self.assertEqual(kcw.stage_args('c2', '<val>'), k8b.stage_args('c', '<val>').replace('--seed 1 ', '--seed 2 '))
        self.assertEqual(kcw.weight_args('c2', '<repo>'), '')
        self.assertEqual(kcw.QUEUES, [['cw'], ['c2']])
        self.assertEqual(kcw.CANDIDATES, ['cw'])
        # The same file list as arm c for any set of mounted files.
        base = ['g2s1-a.vf', 'g3j-w00.vf', 'g4-w01.vf', 'slice1-01.vf', 'g3s2-slice1-00-rest.vf']
        self.assertEqual(kcw.arm_files('control', base), k8b.arm_files('control', base))
        # c's command line, plus the table and the exempt files.
        c, cw = k8b.stage_args('c', '<val>'), kcw.stage_args('cw', '<val>')
        self.assertEqual(c, cw)
        extra = kcw.weight_args('cw', '<repo>')
        self.assertTrue(extra.startswith(f'--cell-weights <repo>/{kcw.TABLE} --exempt '))
        self.assertEqual(extra.split('--exempt ')[1].split(), kcw.EXEMPT)

    def test_the_cell_checks(self):
        slices = ['g3s2-slice1-00-rest.vf'] + [f'slice1-0{i}.vf' for i in range(1, 10)]
        names = ['g2s1-a.vf', 'g3j-w00.vf'] + slices
        with tempfile.TemporaryDirectory() as repo:
            table = Path(repo) / kcw.TABLE
            table.parent.mkdir(parents=True)
            table.write_text('Q-MG|level two-wing 1\n', encoding='utf-8')
            digest = hashlib.sha256(table.read_bytes()).hexdigest()
            saved = kcw.TABLE_SHA256
            try:
                kcw.TABLE_SHA256 = digest
                self.assertTrue(kcw.cell_checks(repo, names)['ok'])
                self.assertFalse(kcw.cell_checks(repo, names[:-1])['ok'])           # a slice file not trained
                self.assertFalse(kcw.cell_checks(repo, names + ['slice2-01.vf'])['ok'])  # an unexempt slice file
                kcw.TABLE_SHA256 = '0' * 64
                self.assertFalse(kcw.cell_checks(repo, names)['ok'])                # another table
            finally:
                kcw.TABLE_SHA256 = saved
            self.assertFalse(kcw.cell_checks(os.path.join(repo, 'none'), names)['ok'])  # no table


if __name__ == '__main__':
    unittest.main()
