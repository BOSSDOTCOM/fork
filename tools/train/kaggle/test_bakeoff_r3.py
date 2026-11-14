# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of bake-off round 3's option (a) kernel (tools/train/kaggle/bakeoff_r3.py): the two arms' settings (the
owner's decisions of 2026-11-14: H512+PP beside a same-recipe S512+PP control, one warm-start source, retrain 8c's
control recipe and files), the file lists and the input check's verdicts, and the warm start's quantised identity
probe on synthetic weights (true for a correct layout, false for a changed one).

    python -I -B -m unittest discover -s tools/train/kaggle -p 'test_bakeoff_r3.py'
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
NNUE = HERE.parent.parent / 'nnue'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(NNUE))
import bakeoff_r3 as k  # noqa: E402
import extend_weights  # noqa: E402
import models  # noqa: E402
import netformat  # noqa: E402

# Retrain 8c's test originals (test_retrain_8c.py on retrain/8c-prep), and files mounted but never trained.
ORIGINALS = ['g2s1-w00.vf', 'g3h-w00.vf', 'g3j-w00.vf', 'g4-w00.vf', 'g4s1-g3j-w05-val-rest.vf', 'g4b-w00.vf',
             'ld-d20-s2-w00.vf', 'ld-d50-w00.vf', 'ld-d100-w01.vf', 'g4c-w03.vf', 'g4s2-g4c-w09-val-rest.vf',
             'slice1b-00.vf', 'slice1b-09.vf', 'g4-gcp-20261111T191107Z-w00.vf',
             'g4s2-g4-gcp-20261111T191107Z-w03-val-rest.vf', 'g4-gcp-20261112T213623Z-w00.vf']
NOT_TRAINED = ['g4s2-val.vf', 'bl-g4s2-val.vf', 'g4s1-val.vf', 'pos1-w00.vf', 'ld-d20c50-w00.vf',
               'i52-held.vf', 'i52-controls.vf', 'ld-d20-w02-val.vf', 'slice1-01.vf', 'g3s2-slice1-00-rest.vf',
               'g4-gcp-20261111T191107Z-w03-val.vf', 'i80-g4c-w03.vf', 'lam-td90-g4c-w03.vf']


class ArmTests(unittest.TestCase):
    def test_the_two_arms_differ_only_in_architecture_and_warm_start(self):
        self.assertEqual(sorted(k.ARMS), ['kr1', 'pp1'])
        kr, pp = k.ARMS['kr1'], k.ARMS['pp1']
        self.assertEqual((kr['arch'], kr['init']), ('h512pp', 'regioned'))
        self.assertEqual((pp['arch'], pp['init']), ('s512pp', 'source'))
        rest = lambda a: {x: y for x, y in a.items() if x not in ('arch', 'init')}  # noqa: E731
        self.assertEqual(rest(kr), rest(pp))
        # 8c's control recipe (its arm c): 360 superbatches, LR 1e-4 dropped after 180, the window 331-360, result
        # weight 0 on the label copies, validated on the blend copy; the same seed, so the same data order.
        self.assertEqual((kr['superbatches'], kr['lr'], kr['lr_step'], kr['window'], kr['result_weight'], kr['val'],
                          kr['seed']), (360, 1e-4, 180, (331, 360), 0.0, 'bl-g4s2-val.vf', 1))
        self.assertEqual(k.QUEUES, [['kr1'], ['pp1']])
        self.assertEqual((k.SCALE, k.BATCH, k.BATCHES, k.SMOKE, k.ARM_SET), (92, 16384, 305, False, 'A'))

    def test_session_x_runs_xl1_alone_with_the_same_recipe(self):
        # x_lower (owner, 2026-11-14): one seed, alone in its session, compared against session A's pp1, so the same
        # recipe, data and warm-start source. The kernel copy's one replacement, as make_kernel.py makes it.
        src = (HERE / 'bakeoff_r3.py').read_text(encoding='utf-8')
        old = "\nARM_SET = 'A' "
        self.assertEqual(src.count(old), 1)
        x = {'__name__': 'bakeoff_r3_x'}
        exec(compile(src.replace(old, "\nARM_SET = 'X' ", 1), 'bakeoff_r3_x.py', 'exec'), x)
        self.assertEqual(x['QUEUES'], [['xl1']])
        self.assertEqual(sorted(x['ARMS']), ['xl1'])
        xl, pp = x['ARMS']['xl1'], k.ARMS['pp1']
        self.assertEqual((xl['arch'], xl['init']), ('s512ppxl', 'exposure'))
        rest = lambda a: {f: v for f, v in a.items() if f not in ('arch', 'init')}  # noqa: E731
        self.assertEqual(rest(xl), rest(pp))
        self.assertEqual(x['WARM_STARTS']['exposure'], ('s512ppxl', 'exposure_net'))
        self.assertEqual(x['SOURCE'], k.SOURCE)

    def test_the_source_is_r8brft1s_float_weights(self):
        # r8brft1's window average (fork-retrain-8b-rft v1, avg-rft1/weights.bin), SHA-256 checked on this machine
        # 2026-11-14 (its quantised layers are nets/r8brft1.fnet's but its one clamped link weight).
        self.assertEqual(k.SOURCE['name'], 'r8brft1')
        self.assertEqual(k.SOURCE['sha256'], '2d70ebccb6e6eb7d192faea0e16bee5c1aa2169c0346f3791e5d6bb27ae1dba1')

    def test_command(self):
        args = k.stage_args('kr1', 'V')
        for part in ('--superbatches 360', '--lr 0.0001', '--lr-step 180', '--seed 1', '--scale 92',
                     '--result-weight 0.0', '--batch 16384', '--batches 305', '--interleave', '--val V'):
            self.assertIn(part, args)


class FileTests(unittest.TestCase):
    def test_the_control_names_are_8cs(self):
        got = dict(zip(ORIGINALS, [k.control_name(n) for n in ORIGINALS]))
        for n in ('g3j-w00.vf', 'g4-w00.vf', 'g4s1-g3j-w05-val-rest.vf', 'g4b-w00.vf', 'ld-d20-s2-w00.vf',
                  'ld-d50-w00.vf', 'ld-d100-w01.vf', 'g4c-w03.vf', 'g4s2-g4c-w09-val-rest.vf',
                  'g4-gcp-20261111T191107Z-w00.vf', 'g4s2-g4-gcp-20261111T191107Z-w03-val-rest.vf',
                  'g4-gcp-20261112T213623Z-w00.vf'):
            self.assertEqual(got[n], f'td90-{n}')
        for n in ('g2s1-w00.vf', 'g3h-w00.vf'):
            self.assertEqual(got[n], f'bl-{n}')
        for n in ('slice1b-00.vf', 'slice1b-09.vf'):
            self.assertEqual(got[n], n)

    def test_resolve(self):
        with tempfile.TemporaryDirectory() as d:
            names = set(ORIGINALS + NOT_TRAINED) | {k.control_name(n) for n in ORIGINALS}
            for n in names:
                Path(d, n).write_bytes(b'x')
            sealed = {n: 'h' for n in names}
            paths = [os.path.join(d, n) for n in names]
            record, lists, _ = k.resolve(paths, sealed, hashes=False)
            self.assertTrue(record['ok'], record)
            self.assertTrue(record['same_lists'])
            self.assertEqual(lists['kr1'], [k.control_name(n) for n in sorted(ORIGINALS)])
            self.assertEqual(lists['kr1'], lists['pp1'])
            for bad in NOT_TRAINED:
                self.assertNotIn(bad, lists['kr1'])
            # The check can fail: a missing control copy, an unsealed file, a file mounted twice.
            gone = [p for p in paths if not p.endswith('td90-g4c-w03.vf')]
            record, _, _ = k.resolve(gone, sealed, hashes=False)
            self.assertFalse(record['ok'])
            self.assertEqual(record['unresolved']['kr1'], ['td90-g4c-w03.vf'])
            record, _, _ = k.resolve(paths, {n: h for n, h in sealed.items() if n != 'g4b-w00.vf'}, hashes=False)
            self.assertFalse(record['ok'])
            os.makedirs(os.path.join(d, 'twin'))
            Path(d, 'twin', 'g4b-w00.vf').write_bytes(b'x')
            record, _, _ = k.resolve(paths + [os.path.join(d, 'twin', 'g4b-w00.vf')], sealed, hashes=False)
            self.assertFalse(record['ok'])


class IdentityProbeTests(unittest.TestCase):
    """The session's quantised identity check, run here on synthetic S512+PP weights quantised by the reference
    (tools/nnue/models.py: bullet's save list redone), in place of the trainer's files."""

    def quantised(self, arch, w, path):
        desc = netformat.layout(NNUE / f'{arch.name}.json')
        saved = models.saved_tensors(arch, w)
        Path(path).write_bytes(netformat.write_quantised({t['name']: saved[t['name']][1] for t in desc['quantised']},
                                                         desc))

    def probe(self, d, source_q, warm_q, arch='h512pp', lay_out='regioned_net'):
        script = Path(d, 'identity.py')
        script.write_text(k.identity_probe(str(NNUE), str(source_q), str(warm_q), arch, lay_out))
        out = subprocess.run([sys.executable, '-I', str(script)], capture_output=True, text=True)
        return out.stdout.strip()

    def test_true_for_the_warm_start_false_for_a_changed_one(self):
        table = netformat.layout(NNUE / 's512pp.json')['table']
        pp, kr = models.Arch('s512pp', table=table), models.Arch('h512pp', table=table)
        rng = random.Random(4)
        n = 768 + 608
        w = {'l0w': [models.to_f32(rng.uniform(-0.06, 0.06)) for _ in range(n * 512)],
             'l0b': [models.to_f32(rng.uniform(-0.3, 0.3)) for _ in range(512)],
             'l1w': [models.to_f32(rng.uniform(-0.5, 0.5)) for _ in range(8 * 1024)],
             'l1b': [models.to_f32(rng.uniform(-0.2, 0.2)) for _ in range(8)]}
        warm = netformat.read_weights_bin(extend_weights.regioned_weights(netformat.write_weights_bin(w)))
        with tempfile.TemporaryDirectory() as d:
            sq, wq = Path(d, 'source.bin'), Path(d, 'warm.bin')
            self.quantised(pp, w, sq)
            self.quantised(kr, warm, wq)
            self.assertEqual(self.probe(d, sq, wq), 'True')
            warm['l0w'][2 * 768 * 512 + 7] = 0.05  # one region-2 weight off zero
            self.quantised(kr, warm, wq)
            self.assertEqual(self.probe(d, sq, wq), 'False')
            # x_lower's warm start: the exposure inputs zero (S512+PPXL, extend_weights.exposure_net).
            xl = models.Arch('s512ppxl', table=table)
            xwarm = netformat.read_weights_bin(extend_weights.exposure_weights(netformat.write_weights_bin(w)))
            xq = Path(d, 'xl.bin')
            self.quantised(xl, xwarm, xq)
            self.assertEqual(self.probe(d, sq, xq, 's512ppxl', 'exposure_net'), 'True')
            xwarm['l0w'][768 * 512 + 3] = 0.05  # one exposure weight off zero
            self.quantised(xl, xwarm, xq)
            self.assertEqual(self.probe(d, sq, xq, 's512ppxl', 'exposure_net'), 'False')


if __name__ == '__main__':
    unittest.main()
