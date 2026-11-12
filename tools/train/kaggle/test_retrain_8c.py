# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of retrain 8c's kernel (tools/train/kaggle/retrain_8c.py): each arm's file list from the originals (the
substitutions the module note declares), the input check's verdicts, and the arms' settings (the owner's decisions
of 2026-11-12: warm start r8btd90, the fine-tune trio after the control, LR 5e-6 for eplo, the label-depth parts in
every arm).

    python -I -B -m unittest discover -s tools/train/kaggle -p 'test_retrain_8c.py'
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retrain_8c as k  # noqa: E402

ORIGINALS = ['g2s1-w00.vf', 'g3h-w00.vf', 'g3j-w00.vf', 'g4-w00.vf', 'g4s1-g3j-w05-val-rest.vf', 'g4b-w00.vf',
             'ld-d20-s2-w00.vf', 'ld-d50-w00.vf', 'ld-d100-w01.vf', 'g4c-w03.vf', 'g4s2-g4c-w09-val-rest.vf',
             'slice1-01.vf', 'g3s2-slice1-00-rest.vf']
NOT_TRAINED = ['g4s2-val.vf', 'bl-g4s2-val.vf', 'g4s1-val.vf', 'pos1-w00.vf', 'ld-d20c50-w00.vf',
               'i52-held.vf', 'i52-controls.vf', 'ld-d20-w02-val.vf']


class ArmFileTests(unittest.TestCase):
    def test_control(self):
        got = dict(zip(ORIGINALS, k.arm_files('control', ORIGINALS)))
        for n in ('g3j-w00.vf', 'g4-w00.vf', 'g4s1-g3j-w05-val-rest.vf', 'g4b-w00.vf', 'ld-d20-s2-w00.vf',
                  'ld-d50-w00.vf', 'ld-d100-w01.vf', 'g4c-w03.vf', 'g4s2-g4c-w09-val-rest.vf'):
            self.assertEqual(got[n], f'td90-{n}')
        for n in ('g2s1-w00.vf', 'g3h-w00.vf'):
            self.assertEqual(got[n], f'bl-{n}')
        for n in ('slice1-01.vf', 'g3s2-slice1-00-rest.vf'):
            self.assertEqual(got[n], n)

    def test_i80_differs_from_the_control_on_the_td_parts_only(self):
        c = k.arm_files('control', ORIGINALS)
        i = k.arm_files('i80', ORIGINALS)
        for o, a, b in zip(ORIGINALS, c, i):
            if a.startswith('td90-'):
                self.assertEqual(b, f'i80-{o}')
            else:
                self.assertEqual(a, b)

    def test_ep_splits_the_controls_copies_and_keeps_the_slice(self):
        c = k.arm_files('control', ORIGINALS)
        for a, b in zip(c, k.arm_files('ep', ORIGINALS)):
            self.assertEqual(b, a if k.is_slice(a) else f'ep-{a}')
        self.assertEqual(k.arm_files('originals', ORIGINALS), ORIGINALS)

    def test_resolve_keeps_the_a1_originals_only(self):
        with tempfile.TemporaryDirectory() as d:
            names = set(ORIGINALS + NOT_TRAINED)
            for kind in ('control', 'i80', 'ep'):
                names |= set(k.arm_files(kind, ORIGINALS))
            for n in names:
                Path(d, n).write_bytes(b'x')
            sealed = {n: 'h' for n in names}
            record, lists, _ = k.resolve([os.path.join(d, n) for n in names], sealed, hashes=False)
            self.assertTrue(record['ok'], record)
            self.assertEqual(lists['rft1'], sorted(ORIGINALS))
            self.assertEqual(lists['c1'], [k.control_name(n) for n in sorted(ORIGINALS)])
            for bad in ('pos1-w00.vf', 'ld-d20c50-w00.vf', 'i52-held.vf'):
                self.assertNotIn(bad, lists['rft1'])
            # The check can fail: a missing i80 copy, an unsealed file.
            gone = [os.path.join(d, n) for n in names if n != 'i80-g4c-w03.vf']
            record, _, _ = k.resolve(gone, sealed, hashes=False)
            self.assertFalse(record['ok'])
            self.assertIn('i801', record['unresolved'])
            record, _, _ = k.resolve([os.path.join(d, n) for n in names], dict(list(sealed.items())[1:]), hashes=False)
            self.assertFalse(record['ok'])


class SettingTests(unittest.TestCase):
    def test_the_owners_decisions(self):
        self.assertEqual(k.INIT['weights'], 'r8b-td90-avg.bin')                      # O4: warm from r8btd90
        for s in (1, 2):
            self.assertEqual(k.ARMS[f'eplo{s}']['lr'], 5e-6)                         # O1: the lower-LR variant
            self.assertEqual(k.ARMS[f'ep{s}']['lr'], 1e-5)
            for arm in ('rft', 'ep', 'eplo'):
                self.assertEqual(k.ARMS[f'{arm}{s}']['init'], f'c{s}')               # O4: applied after the control
            q = k.QUEUES[s - 1]
            self.assertEqual(q.index(f'c{s}'), 0)
            self.assertLess(max(q.index(f'{a}{s}') for a in ('rft', 'ep', 'eplo')), q.index(f'i80{s}'))
        for prefix in ('ld-d20-', 'ld-d50-', 'ld-d100-'):                            # O3: label depth in every arm
            self.assertIn(prefix, k.TD_PARTS)
        self.assertEqual(k.ARMS['c1']['superbatches'] * k.BATCHES, k.ARMS['i801']['superbatches'] * k.BATCHES)


if __name__ == '__main__':
    unittest.main()
