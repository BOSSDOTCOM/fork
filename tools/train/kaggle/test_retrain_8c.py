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
             'slice1b-00.vf', 'slice1b-09.vf', 'g4-gcp-20261111T191107Z-w00.vf',
             'g4s2-g4-gcp-20261111T191107Z-w03-val-rest.vf', 'g4-gcp-20261112T213623Z-w00.vf']
NOT_TRAINED = ['g4s2-val.vf', 'bl-g4s2-val.vf', 'g4s1-val.vf', 'pos1-w00.vf', 'ld-d20c50-w00.vf',
               'i52-held.vf', 'i52-controls.vf', 'ld-d20-w02-val.vf', 'slice1-01.vf', 'g3s2-slice1-00-rest.vf',
               'g4-gcp-20261111T191107Z-w03-val.vf']


class ArmFileTests(unittest.TestCase):
    def test_control(self):
        got = dict(zip(ORIGINALS, k.arm_files('control', ORIGINALS)))
        for n in ('g3j-w00.vf', 'g4-w00.vf', 'g4s1-g3j-w05-val-rest.vf', 'g4b-w00.vf', 'ld-d20-s2-w00.vf',
                  'ld-d50-w00.vf', 'ld-d100-w01.vf', 'g4c-w03.vf', 'g4s2-g4c-w09-val-rest.vf',
                  'g4-gcp-20261111T191107Z-w00.vf', 'g4s2-g4-gcp-20261111T191107Z-w03-val-rest.vf',
                  'g4-gcp-20261112T213623Z-w00.vf'):
            self.assertEqual(got[n], f'td90-{n}')
        for n in ('g2s1-w00.vf', 'g3h-w00.vf'):
            self.assertEqual(got[n], f'bl-{n}')
        for n in ('slice1b-00.vf', 'slice1b-09.vf'):
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
            for kind in ('control', 'i80'):          # ep- copies are made in the session, never mounted
                names |= set(k.arm_files(kind, ORIGINALS))
            for n in names:
                Path(d, n).write_bytes(b'x')
            sealed = {n: 'h' for n in names}
            record, lists, _ = k.resolve([os.path.join(d, n) for n in names], sealed, hashes=False)
            self.assertTrue(record['ok'], record)
            self.assertEqual(lists['rft1'], sorted(ORIGINALS))
            self.assertEqual(lists['c1'], [k.control_name(n) for n in sorted(ORIGINALS)])
            for bad in ('pos1-w00.vf', 'ld-d20c50-w00.vf', 'i52-held.vf', 'slice1-01.vf', 'g3s2-slice1-00-rest.vf',
                        'g4-gcp-20261111T191107Z-w03-val.vf'):
                self.assertNotIn(bad, lists['rft1'])          # v1's slice and a filler -val source: mounted, not trained
                self.assertNotIn(bad, lists['c1'])
            self.assertEqual(record['slice_files'], ['slice1b-00.vf', 'slice1b-09.vf'])
            self.assertEqual(lists['ep1'], [n if k.is_slice(n) else f'ep-{n}' for n in lists['c1']])
            self.assertEqual(record['unresolved'], {})
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

    def test_smoke_mode_is_off_and_changes_nothing(self):
        # The real session's settings (the module as committed: SMOKE off).
        self.assertFalse(k.SMOKE)
        self.assertEqual((k.BATCHES, k.VAL, k.VAL_BLEND), (305, 'g4s2-val.vf', 'bl-g4s2-val.vf'))
        self.assertEqual(k.BASE_SETTINGS, {'superbatches': 360, 'lr_step': 180, 'window': (331, 360),
                                           'keep': (180, 360)})
        self.assertEqual(k.FINE_TUNE_SETTINGS['superbatches'], 60)

    def test_smoke_mode_shrinks_sizes_only(self):
        # The smoke copy (one exact replacement) keeps the arms, queues and file rules; only sizes and the
        # validation files change.
        import importlib.util
        src = Path(k.__file__).read_text(encoding='utf-8')
        self.assertEqual(src.count('\nSMOKE = False '), 1)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'retrain_8c_smoke.py')
            path.write_text(src.replace('\nSMOKE = False ', '\nSMOKE = True ', 1), encoding='utf-8')
            spec = importlib.util.spec_from_file_location('retrain_8c_smoke', path)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
        self.assertTrue(m.SMOKE)
        self.assertEqual(m.QUEUES, k.QUEUES)
        self.assertEqual(set(m.ARMS), set(k.ARMS))
        for arm, a in k.ARMS.items():
            b = m.ARMS[arm]
            self.assertEqual({x: a[x] for x in ('files', 'init', 'lr', 'result_weight', 'seed')},
                             {x: b[x] for x in ('files', 'init', 'lr', 'result_weight', 'seed')})
        self.assertEqual((m.BATCHES, m.ARMS['c1']['superbatches'], m.ARMS['ep1']['superbatches']), (8, 4, 3))
        self.assertEqual((m.VAL, m.VAL_BLEND), ('g4s1-val.vf', 'bl-g4s1-val.vf'))
        names = set(m.SMOKE_ORIGINALS + m.SMOKE_ALSO + ['g4s1-val.vf', 'bl-g4s1-val.vf', 'other.vf'])
        for kind in ('control', 'i80'):
            names |= set(m.arm_files(kind, m.SMOKE_ORIGINALS))
        with tempfile.TemporaryDirectory() as d:
            for n in names:
                Path(d, n).write_bytes(b'x')
            found, sealed = m.smoke_subset([os.path.join(d, n) for n in names], {n: 'h' for n in names})
            self.assertNotIn(os.path.join(d, 'other.vf'), found)
            record, lists, _ = m.resolve(found, sealed, hashes=False)
        self.assertTrue(record['ok'], record)
        self.assertEqual(lists['rft1'], sorted(m.SMOKE_ORIGINALS))                 # v1 slice, -val source out
        self.assertEqual(record['slice_files'], ['slice1b-00.vf'])
        self.assertEqual(lists['c1'], ['bl-g3b-w00.vf', 'td90-g4-gcp-20261112T213623Z-w00.vf',
                                       'td90-g4b-w00.vf', 'td90-g4s2-g4-gcp-20261112T185227Z-w02-val-rest.vf',
                                       'slice1b-00.vf'])

    def test_arm_sets_split_the_arms_only(self):
        # 'all' is the kernel as before; 'main' and 'i80' keep exactly their arms' settings and queue order.
        import importlib.util
        src = Path(k.__file__).read_text(encoding='utf-8')
        self.assertEqual(k.ARM_SET, 'all')
        self.assertEqual(src.count("\nARM_SET = 'all' "), 1)
        mods = {}
        for name in ('main', 'i80'):
            with tempfile.TemporaryDirectory() as d:
                path = Path(d, f'retrain_8c_{name}.py')
                path.write_text(src.replace("\nARM_SET = 'all' ", f"\nARM_SET = '{name}' ", 1), encoding='utf-8')
                spec = importlib.util.spec_from_file_location(f'retrain_8c_{name}', path)
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                mods[name] = m
        main, i80 = mods['main'], mods['i80']
        self.assertEqual(main.QUEUES, [['c1', 'rft1', 'ep1', 'eplo1'], ['c2', 'rft2', 'ep2', 'eplo2']])
        self.assertEqual(i80.QUEUES, [['i801'], ['i802']])
        self.assertEqual(set(main.ARMS) | set(i80.ARMS), set(k.ARMS))
        self.assertFalse(set(main.ARMS) & set(i80.ARMS))
        for m in (main, i80):
            for arm, a in m.ARMS.items():
                self.assertEqual(a, k.ARMS[arm])
            self.assertEqual(m.CANDIDATES, list(m.ARMS))
            self.assertEqual(m.MANIFESTS, k.MANIFESTS)
            self.assertIn(m.QUEUES[0][0], m.ARMS)
        # No arm is named in the session's code outside QUEUES (the i80 smoke of 2026-11-13 failed on a hard-coded
        # lists['c1']): every quoted arm name appears only in the QUEUES line.
        body = [line for line in src.splitlines() if not line.startswith('QUEUES = ')]
        for arm in k.ARMS:
            self.assertFalse(any(f"'{arm}'" in line for line in body), arm)

    def test_arm_set_q_adds_the_slice_copies_to_the_control(self):
        # Arm Q (2026-11-14): qn1 = c1's files + each td90-posx1 copy once, qo1 = + each copy POSX_OVERSAMPLE times;
        # c1's settings otherwise; the raw posx1 files trained by no arm.
        import importlib.util
        src = Path(k.__file__).read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'retrain_8c_q.py')
            path.write_text(src.replace("\nARM_SET = 'all' ", "\nARM_SET = 'q' ", 1), encoding='utf-8')
            spec = importlib.util.spec_from_file_location('retrain_8c_q', path)
            q = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(q)
        self.assertEqual(q.QUEUES, [['qn1'], ['qo1']])
        self.assertEqual(set(q.ARMS), {'qn1', 'qo1'})
        control = k.arm_files('control', ORIGINALS)
        self.assertEqual(q.arm_files('qn', ORIGINALS), control + q.POSX)
        self.assertEqual(q.arm_files('qo', ORIGINALS), control + q.POSX * 4)
        self.assertEqual(len(q.POSX), 8)
        for arm in ('qn1', 'qo1'):
            want = dict(k.ARMS['c1'])
            got = dict(q.ARMS[arm])
            self.assertEqual(got.pop('files'), arm[:2])
            want.pop('files')
            self.assertEqual(got, want)
        self.assertTrue('posx1-w00.vf'.startswith(k.NOT_A1))
        self.assertIn('posx1', k.MANIFESTS)
        self.assertIn('posx1-td', k.MANIFESTS)

    def test_the_split_is_made_in_the_session(self):
        self.assertNotIn('r8c-split', k.MANIFESTS)                                    # no upload of ep- copies
        self.assertIn('slice1b', k.MANIFESTS)
        self.assertEqual(k.split_source('ep-td90-g4c-w03.vf'), 'td90-g4c-w03.vf')
        self.assertEqual(k.split_source('td90-g4c-w03.vf'), 'td90-g4c-w03.vf')
        self.assertEqual(k.SPLIT_MAX_PIECES, 7)                                       # O1


if __name__ == '__main__':
    unittest.main()
