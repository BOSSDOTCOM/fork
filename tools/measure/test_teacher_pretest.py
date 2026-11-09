# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/measure/teacher_pretest.py on synthetic fixtures: the
win-probability mean, the mate rule, the Brier score, the bootstrap (seeded,
and the same draw as label_pretest.boot_difference), and a whole run on a
small shard, Y1 and Y2 checked by hand and the TD comparisons checked
against label_pretest's own report; with a fault (a mate rule that ignores
the side) that the tests must catch.

    python -I -B -m unittest discover -s tools/measure -p 'test_*.py'
"""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'datagen'))
import label_pretest as lp  # noqa: E402
import teacher_pretest as tp  # noqa: E402
import td_labels as td  # noqa: E402
from test_label_pretest import shard  # noqa: E402


def sig(x):
    return 1.0 / (1.0 + math.exp(-x))


class MeanTests(unittest.TestCase):
    def test_plain_mean_in_probability(self):
        p, state = tp._mean_p([(92, 0), (-92, 0), (0, 0)], 92.0, True)
        self.assertAlmostEqual(p, (sig(1) + sig(-1) + 0.5) / 3)
        self.assertEqual(state, 0)
        # Not the mean in cp: one confident member does not dominate.
        p, _ = tp._mean_p([(800, 0), (0, 0)], 92.0, False)
        self.assertAlmostEqual(p, (sig(800 / 92) + 0.5) / 2)
        self.assertNotAlmostEqual(p, sig(400 / 92))

    def test_mate_majority(self):
        self.assertEqual(tp._mean_p([(20000, 1), (20000, 1), (-50, 0)], 92.0, True), (1.0, 1))
        self.assertEqual(tp._mean_p([(-20000, 1), (-20000, 1), (300, 0)], 92.0, True), (0.0, 1))
        # One mate of three is no majority: the mate member is left out.
        p, state = tp._mean_p([(20000, 1), (92, 0), (-92, 0)], 92.0, True)
        self.assertAlmostEqual(p, (sig(1) + sig(-1)) / 2)
        self.assertEqual(state, 2)
        # Two mates for opposite sides: neither side has a majority.
        p, state = tp._mean_p([(20000, 1), (-20000, 1), (92, 0)], 92.0, True)
        self.assertAlmostEqual(p, sig(1))
        self.assertEqual(state, 2)
        # Two of two members, split: every member left out, the plain mean.
        p, state = tp._mean_p([(20000, 1), (-20000, 1)], 92.0, True)
        self.assertAlmostEqual(p, 0.5)
        self.assertEqual(state, 3)
        # Two of two is a strict majority; one of two is not.
        self.assertEqual(tp._mean_p([(20000, 1), (20000, 1)], 92.0, True), (1.0, 1))
        p, state = tp._mean_p([(-20000, 1), (46, 0)], 92.0, True)
        self.assertAlmostEqual(p, sig(0.5))
        self.assertEqual(state, 2)
        # Without the rule, mates enter the plain mean.
        p, state = tp._mean_p([(20000, 1), (92, 0), (-92, 0)], 92.0, False)
        self.assertAlmostEqual(p, (1.0 + sig(1) + sig(-1)) / 3)
        self.assertEqual(state, 0)

    def test_fault_a_rule_ignoring_the_side_is_caught(self):
        # Injected fault: counting mates of either side as one majority would
        # call this split position a win.
        def faulty(values):
            mates = [cp for cp, m in values if m]
            return 1.0 if 2 * len(mates) > len(values) else None

        values = [(20000, 1), (-20000, 1), (0, 0)]
        self.assertEqual(faulty(values), 1.0)
        self.assertNotEqual(tp._mean_p(values, 92.0, True)[0], 1.0)

    def test_brier(self):
        self.assertAlmostEqual(tp._brier(0.8, 1.0), 0.04)
        self.assertAlmostEqual(tp._brier(0.8, 0.5), 0.09)
        self.assertAlmostEqual(tp._brier(0.3, 0.0), 0.09)


class BootTests(unittest.TestCase):
    def test_same_draw_as_label_pretest(self):
        a = [0.10, 0.30, 0.05, 0.20, 0.15, 0.40, 0.00]
        b = [0.12, 0.25, 0.10, 0.20, 0.30, 0.35, 0.05]
        n = [1, 1, 0, 1, 1, 1, 1]
        sa, sb, sn = tp._resample_sums([a, b, n], 500, 11)
        reps = [x / m - y / m for x, y, m in zip(sa, sb, sn) if m]
        groups = list(zip(a, n, b, n))
        d, (lo, hi) = lp.boot_difference(groups, 500, 11)
        self.assertEqual(tp._summary(sum(a) / sum(n) - sum(b) / sum(n), reps)['interval'], [lo, hi])

    def test_seeded_and_reproducible(self):
        cols = [[float(k % 5) for k in range(30)], [1] * 30]
        self.assertEqual(tp._resample_sums(cols, 200, 3), tp._resample_sums(cols, 200, 3))
        self.assertNotEqual(tp._resample_sums(cols, 200, 3), tp._resample_sums(cols, 200, 4))
        # Each resample draws k games with replacement.
        self.assertTrue(all(s == 30 for s in tp._resample_sums(cols, 200, 3)[1]))


class RunTests(unittest.TestCase):
    """A whole run: three games of label_pretest's test shard, one site per
    game, labels written by hand."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.data = root / 'data'
        self.data.mkdir()
        (self.data / 'x.vf').write_bytes(shard())
        sites, _ = lp.sample_sites(shard(), 'x.vf', 10, 7)
        self.sites = sites
        text = ''.join(json.dumps(s) + '\n' for s in sites)
        self.labels = {  # per site id: (cp, mate)
            'a': {s['id']: v for s, v in zip(sites, [(92, 0), (20000, 1), (-46, 0)])},
            'b': {s['id']: v for s, v in zip(sites, [(0, 0), (20000, 1), (46, 0)])},
            'c': {s['id']: v for s, v in zip(sites, [(-92, 0), (30, 0), (-20000, 1)])},
            'g': {s['id']: v for s, v in zip(sites, [(184, 0), (-184, 0), (0, 0)])},
        }
        self.dirs = {}
        for name, lab in self.labels.items():
            d = root / name
            d.mkdir()
            (d / 'sites.jsonl').write_text(text, encoding='utf-8')
            (d / 'deep.tsv').write_text(''.join(f'{i}\t{cp}\t{m}\t5\n' for i, (cp, m) in lab.items()),
                                        encoding='utf-8')
            self.dirs[name] = d

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, extra):
        out = Path(self.tmp.name) / 'out.json'
        args = [f'g={self.dirs["g"]}'] + [f'{n}={self.dirs[n]}' for n in 'abc']
        tp.main(args + ['--data', str(self.data), '--scale', '92', '--boot', '300', '--seed', '5', '--json', str(out)]
                + extra)
        return json.loads(out.read_text(encoding='utf-8'))

    def records(self):
        rows, _ = td.matched_records([self.dirs['g']], [self.data])
        ids = {s['game']: s['id'] for s in self.sites}
        return rows, ids

    def test_y1_and_y2_by_hand(self):
        rep = self.run_main(['--mate-majority', 'E=a,b,c', '--reference', 'g'])
        rows, ids = self.records()
        kept = [r for r in rows if r['kept']]
        self.assertGreater(len(kept), 0)
        self.assertEqual(rep['kept_records'], len(kept))
        e_vals, y1_e, y2_e = [], 0.0, 0.0
        for r in kept:
            sid = ids[r['game']]
            vals = [self.labels[n][sid] for n in 'abc']
            if sum(1 for cp, m in vals if m and cp > 0) >= 2:
                e = 1.0
            elif sum(1 for cp, m in vals if m and cp < 0) >= 2:
                e = 0.0
            else:
                rest = [sig(cp / 92) for cp, m in vals if not m]
                e = sum(rest) / len(rest)
            e_vals.append(e)
            z = td.WHITE_RESULT[r['result']]
            z = z if r['white'] else 1 - z
            y1_e += (e - z) ** 2
            y2_e += (e - sig(self.labels['g'][sid][0] / 92)) ** 2
        self.assertAlmostEqual(rep['y1']['mean']['E']['value'], y1_e / len(kept))
        self.assertAlmostEqual(rep['y2']['g']['mean']['E']['value'], y2_e / len(kept))
        d = rep['y1']['differences']['a - E']['value']
        self.assertAlmostEqual(d, rep['y1']['mean']['a']['value'] - rep['y1']['mean']['E']['value'])
        lo, hi = rep['y1']['mean']['E']['interval']
        self.assertLessEqual(lo, hi)

    def test_td_comparisons_match_label_pretest(self):
        rep = self.run_main(['--reference', 'g', '--reference', 'a', '--blend', '0.5', '--lams', '0.5,0.9'])
        rows, _ = td.matched_records([self.dirs['g']], [self.data])
        want = lp.label_report(lp.label_errors(rows, 92.0, 0.5, [0.5, 0.9]), [0.5, 0.9], 300, 5)
        got = rep['golds']['g']
        for name in ('td=0.5', 'td=0.9'):
            self.assertAlmostEqual(got['differences'][name]['value'], want['td'][name]['difference'])
            self.assertEqual(got['differences'][name]['interval'], want['td'][name]['interval'])
        self.assertAlmostEqual(got['differences']['unfiltered']['value'], want['unfiltered']['difference'])
        self.assertEqual(got['differences']['unfiltered']['interval'], want['unfiltered']['interval'])
        # The bias is the first gold's difference minus the other's.
        b = rep['bias']['g minus a']['td=0.5']['value']
        self.assertAlmostEqual(b, got['differences']['td=0.5']['value']
                               - rep['golds']['a']['differences']['td=0.5']['value'])
        # The bias of a gold against itself is zero.
        same = self.run_main(['--reference', 'g', '--combine', 'g2=g', '--reference', 'g2', '--blend', '0.5',
                              '--lams', '0.5'])
        self.assertEqual(same['bias']['g minus g2']['td=0.5']['value'], 0.0)

    def test_a_missing_label_stops_the_run(self):
        lines = (self.dirs['c'] / 'deep.tsv').read_text(encoding='utf-8').splitlines()
        (self.dirs['c'] / 'deep.tsv').write_text('\n'.join(lines[1:]) + '\n', encoding='utf-8')
        with self.assertRaises(SystemExit):
            self.run_main([])


if __name__ == '__main__':
    unittest.main()
