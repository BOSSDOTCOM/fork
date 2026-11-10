# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of idea 70's kernel (tools/train/kaggle/retrain_8b_rft.py; docs/research/retrain-8b/rft-plan.md), runnable
anywhere: it is exactly what make_rft_kernel.py makes of retrain 8b's kernel; every function but the ones the plan
changes is 8b's own; the declared settings; each arm trains on arm c's file list; the warm starts' hashes are the
manifest's.

    python -I tools/train/kaggle/test_rft_kernel.py
"""
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import retrain_8b as k8b  # noqa: E402
import retrain_8b_rft as rft  # noqa: E402


class RftKernelTest(unittest.TestCase):
    def test_generated_exactly(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'k.py'
            subprocess.run([sys.executable, '-I', str(HERE / 'make_rft_kernel.py'), str(HERE / 'retrain_8b.py'),
                            str(out)], check=True, capture_output=True)
            self.assertEqual(out.read_bytes(), (HERE / 'retrain_8b_rft.py').read_bytes())

    def test_everything_else_is_8b(self):
        changed = {'stage_args', 'plan', 'session'}
        for name, f in inspect.getmembers(k8b, inspect.isfunction):
            if f.__module__ != 'retrain_8b' or name in changed:
                continue
            self.assertEqual(inspect.getsource(f), inspect.getsource(getattr(rft, name)), name)
        for name in ('ARCH', 'SCALE', 'BATCH', 'BATCHES', 'VAL_POSITIONS', 'ALL_POSITIONS', 'MANIFESTS', 'VAL',
                     'EVAL_ONLY', 'TOLERANCE', 'DATA', 'RESULT'):
            self.assertEqual(getattr(k8b, name), getattr(rft, name), name)

    def test_declared_settings(self):
        self.assertEqual(rft.SUPERBATCHES, 60)
        self.assertEqual(rft.WINDOW, (46, 60))
        self.assertEqual(rft.KEEP, {60})
        self.assertEqual(rft.QUEUES, [['rft1'], ['rft2']])
        self.assertEqual(rft.CANDIDATES, ['rft1', 'rft2'])
        for arm, seed in (('rft1', 1), ('rft2', 2)):
            a = rft.ARMS[arm]
            self.assertEqual((a['files'], a['init'], a['lr'], a['result_weight'], a['seed'], a['val']),
                             ('control', True, 1e-5, 1.0, seed, 'g4s1-val.vf'))
            self.assertGreater(a['lr_step'], rft.SUPERBATCHES)  # a constant LR
            args = rft.stage_args(arm, '<val>')
            for part in (f'--seed {seed} ', '--superbatches 60 ', '--lr 1e-05 ', '--result-weight 1.0 ',
                         '--interleave', '--patience 61 '):
                self.assertIn(part, args)
        self.assertEqual(rft.WINNER, 'td90')
        self.assertIs(rft.INIT, rft.INITS['td90'])

    def test_each_arm_reads_arm_c_files(self):
        sealed = k8b.sealed_files(str(REPO))
        with tempfile.TemporaryDirectory() as d:
            found = []
            for n in sealed:  # empty stand-ins: hashes off, only the names and sizes are read
                (Path(d) / n).write_bytes(b'')
                found.append(str(Path(d) / n))
            _, lists8b, _ = k8b.resolve(found, sealed, hashes=False)
            rec, lists, _ = rft.resolve(found, sealed, hashes=False)
        self.assertTrue(rec['ok'], rec)
        self.assertEqual(lists['rft1'], lists8b['c'])
        self.assertEqual(lists['rft2'], lists8b['c'])
        self.assertEqual(len(lists['rft1']), 129)

    def test_warm_starts_are_the_manifest_files(self):
        m = json.loads((REPO / 'data' / 'manifests' / 'r8b-rft-init.json').read_text(encoding='utf-8'))
        files = {s['file']: s['sha256'] for b in m['batches'] for s in b}
        self.assertEqual({v['weights']: v['sha256'] for v in rft.INITS.values()}, files)
        self.assertEqual(set(rft.INITS), {'c', 'i52', 'td80', 'td90'})


if __name__ == '__main__':
    unittest.main()
