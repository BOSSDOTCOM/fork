# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of the head-to-head picker (tools/cloud/h2h_pick.py; owner, DESIGN.md §6 2026-11-07 decision 3):
each pairing's delta and error from its merged pentanomial, the least-squares strengths of three and of
four values against the closed form, the declared tie rule (0.5 e, owner 2026-11-07), the refusals
(pairings on different openings, results of another commit) and the constants-table row.

    python3 -m unittest discover -s tools/cloud -p 'test_*.py'
"""
import contextlib
import io
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import h2h_pick as hp  # noqa: E402
import sprt_merge as sm  # noqa: E402

SHA = {'20': '2' * 40, '40': '4' * 40, '60': '6' * 40, '80': '8' * 40}
BETTER = [2, 6, 20, 14, 8]  # per shard: the test side clearly stronger
EDGE = [4, 10, 20, 11, 5]   # per shard: a small edge (+13.83 nElo over 200 pairs, below 0.5 e)
EVEN = [5, 10, 20, 10, 5]


def load_tests(loader, tests, pattern):
    t = unittest.TestCase()
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)

    def write(name, base, test, ptnml, stages=2, shards=2, origin=0, shift=0, run=500, foreign=False):
        """A pairing's stage folders as sprt_run.sh leaves them (50 pairs per shard)."""
        d = root / name
        for s in range(origin, origin + stages):
            for k in range(shards):
                f = d / f's{s}' / f'shard-{s}-{k}' / 'result.json'
                f.parent.mkdir(parents=True, exist_ok=True)
                meta = {'base': base, 'test': 'f' * 40 if foreign else test, 'stage': str(s), 'shard': str(k),
                        'shards': str(shards), 'tc': '8+0.08', 'hash': '16', 'base_opts': '', 'test_opts': '',
                        'tables': '3-4-5', 'book_sha': 'x', 'opening_start': str((s * shards + k) * 50 + 1 + shift),
                        'rounds': '50'}
                f.write_text(json.dumps({'ptnml': ptnml, 'meta': meta}), encoding='utf-8')
            (d / f's{s}' / 'run_id').write_text(f'{run + s}\n', encoding='utf-8')
        return d

    def declare(name, values, prefer='40', stages=2, margin=0.5):
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / 'declaration.json').write_text(json.dumps({
            'const': 'RfpMarginTest', 'values': {v: SHA[v] for v in values}, 'stages': str(stages), 'origin': '0',
            'prefer': prefer, 'prefer_reason': 'the current value', 'tie_margin': str(margin), 'idea': 'rfp'}),
            encoding='utf-8')
        return d

    def run_main(name):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = hp.main([str(root / name), str(root)])
        return rc, out.getvalue()

    def test_two_values():
        write('two.40-60', SHA['40'], SHA['60'], BETTER)
        r = hp.pairing_result(root / 'two.40-60', SHA['40'], SHA['60'], 0, 2)
        total = [4 * x for x in BETTER]
        t.assertEqual(r['ptnml'], total)
        t.assertAlmostEqual(r['d'], sm.nelo(total), places=9)
        t.assertAlmostEqual(r['e'], 1.96 * sm.NELO_SCALE / math.sqrt(200), places=9)
        declare('two', ['40', '60'])
        rc, out = run_main('two')
        t.assertEqual(rc, 0, out)
        pick = json.loads((root / 'two' / 'pick.json').read_text(encoding='utf-8'))
        t.assertEqual((pick['winner'], pick['tie_rule_applied']), ('60', False))
        line = (root / 'two' / 'constants-line.md').read_text(encoding='utf-8')
        t.assertIn('60 - 40 +96.36 +/- 34.05 nElo', line)
        t.assertIn('(400 games)', line)
        t.assertTrue(line.startswith('| `RfpMarginTest` | 60 | **Head-to-head** ('))

    def test_three_values_closed_form():
        d_ab, d_ac, d_bc, e = 7.3, -2.1, 4.4, 17.0
        s = hp.fit_strengths([('A', 'B', d_ab, e), ('A', 'C', d_ac, e), ('B', 'C', d_bc, e)], ['A', 'B', 'C'], 'A')
        t.assertAlmostEqual(s['B'][0], (2 * d_ab + d_ac - d_bc) / 3, places=9)
        t.assertAlmostEqual(s['C'][0], (d_ab + 2 * d_ac + d_bc) / 3, places=9)
        t.assertAlmostEqual(s['B'][1], e * math.sqrt(2 / 3), places=9)
        t.assertAlmostEqual(s['C'][1], e * math.sqrt(2 / 3), places=9)
        t.assertEqual(s['A'], (0.0, 0.0))
        two = hp.fit_strengths([('A', 'B', d_ab, e)], ['A', 'B'], 'A')  # two values: the pairing itself
        t.assertAlmostEqual(two['B'][0], d_ab, places=9)
        t.assertAlmostEqual(two['B'][1], e, places=9)
        # Through main: B beats A and C on the same openings.
        write('three.40-60', SHA['40'], SHA['60'], BETTER, run=600)
        write('three.40-80', SHA['40'], SHA['80'], EVEN, run=700)
        write('three.60-80', SHA['60'], SHA['80'], list(reversed(BETTER)), run=800)
        declare('three', ['40', '60', '80'])
        rc, out = run_main('three')
        t.assertEqual(rc, 0, out)
        pick = json.loads((root / 'three' / 'pick.json').read_text(encoding='utf-8'))
        t.assertEqual(pick['winner'], '60')
        t.assertAlmostEqual(pick['strengths']['60'][0], sm.nelo([4 * x for x in BETTER]), places=6)
        t.assertAlmostEqual(pick['strengths']['60'][1], 34.0505 * math.sqrt(2 / 3), places=2)

    def test_four_values_closed_form():
        # A full round robin of n values, equal-length pairings: s_X = (sum_Y d_XY - sum_Y d_PY) / n with
        # d_XY = s_X - s_Y as measured (antisymmetric) and P the preferred value; each +/- e sqrt(2/n).
        meas = {('A', 'B'): 7.3, ('A', 'C'): -2.1, ('A', 'D'): 11.8, ('B', 'C'): 4.4, ('B', 'D'): -6.5,
                ('C', 'D'): 3.2}  # s_hi - s_lo, deliberately inconsistent
        e, labels = 17.0, ['A', 'B', 'C', 'D']
        d = {}
        for (lo, hi), v in meas.items():
            d[(hi, lo)], d[(lo, hi)] = v, -v
        row = {x: sum(d[(x, y)] for y in labels if y != x) for x in labels}
        for ref in ('A', 'C'):
            s = hp.fit_strengths([(lo, hi, v, e) for (lo, hi), v in meas.items()], labels, ref)
            for x in labels:
                t.assertAlmostEqual(s[x][0], (row[x] - row[ref]) / 4, places=9)
                t.assertAlmostEqual(s[x][1], 0.0 if x == ref else e * math.sqrt(2 / 4), places=9)
        # Through main: four values, six pairings on the same openings; 60 beats the rest.
        write('four.20-40', SHA['20'], SHA['40'], EVEN, run=1000)
        write('four.20-60', SHA['20'], SHA['60'], BETTER, run=1010)
        write('four.20-80', SHA['20'], SHA['80'], EVEN, run=1020)
        write('four.40-60', SHA['40'], SHA['60'], BETTER, run=1030)
        write('four.40-80', SHA['40'], SHA['80'], EVEN, run=1040)
        write('four.60-80', SHA['60'], SHA['80'], list(reversed(BETTER)), run=1050)
        declare('four', ['20', '40', '60', '80'], prefer='20')
        rc, out = run_main('four')
        t.assertEqual(rc, 0, out)
        pick = json.loads((root / 'four' / 'pick.json').read_text(encoding='utf-8'))
        t.assertEqual((pick['winner'], pick['tie_rule_applied']), ('60', False))
        t.assertEqual(len(pick['pairings']), 6)
        t.assertAlmostEqual(pick['strengths']['60'][0], sm.nelo([4 * x for x in BETTER]), places=6)
        t.assertAlmostEqual(pick['strengths']['60'][1], 34.0505 * math.sqrt(2 / 4), places=2)
        line = (root / 'four' / 'constants-line.md').read_text(encoding='utf-8')
        t.assertIn('values 20, 40, 60, 80 in a round robin', line)
        t.assertIn('(least squares over the 6 pairings)', line)
        # The tie rule among four: the preferred value is kept against a leader within 0.5 e of it.
        order = ['A', 'B', 'C', 'D']
        t.assertEqual(hp.pick_winner({'A': (0.0, 0.0), 'B': (2.0, 10.0), 'C': (4.9, 10.0), 'D': (-1.0, 10.0)},
                                     'A', 0.5, order), ('A', True))
        t.assertEqual(hp.pick_winner({'A': (0.0, 0.0), 'B': (2.0, 10.0), 'C': (5.1, 10.0), 'D': (-1.0, 10.0)},
                                     'A', 0.5, order), ('C', False))

    def test_tie_rule():
        order = ['A', 'B', 'C']
        t.assertEqual(hp.pick_winner({'A': (0.0, 0.0), 'B': (4.9, 10.0)}, 'A', 0.5, order), ('A', True))
        t.assertEqual(hp.pick_winner({'A': (0.0, 0.0), 'B': (5.1, 10.0)}, 'A', 0.5, order), ('B', False))
        t.assertEqual(hp.pick_winner({'A': (0.0, 0.0), 'B': (4.9, 10.0)}, 'A', 0.25, order), ('B', False))
        t.assertEqual(hp.pick_winner({'A': (0.0, 0.0), 'B': (-3.0, 10.0)}, 'A', 0.5, order), ('A', False))
        # Between two values that are not the preferred one: the larger strength.
        t.assertEqual(hp.pick_winner({'A': (0.0, 0.0), 'B': (30.0, 10.0), 'C': (29.0, 10.0)}, 'A', 0.5, order),
                      ('B', False))
        write('edge.40-60', SHA['40'], SHA['60'], EDGE, run=900)
        declare('edge', ['40', '60'])
        rc, out = run_main('edge')
        t.assertEqual(rc, 0, out)
        pick = json.loads((root / 'edge' / 'pick.json').read_text(encoding='utf-8'))
        t.assertEqual((pick['winner'], pick['tie_rule_applied']), ('40', True))

    def test_unequal_openings_refused():
        write('shifted.40-60', SHA['40'], SHA['60'], BETTER, run=1000)
        write('shifted.40-80', SHA['40'], SHA['80'], EVEN, run=1100, shift=400)
        write('shifted.60-80', SHA['60'], SHA['80'], EVEN, run=1200)
        declare('shifted', ['40', '60', '80'])
        rc, out = run_main('shifted')
        t.assertEqual(rc, 1)
        t.assertIn('shifted.40-80', out)
        t.assertIn('not on the same openings', out)
        t.assertFalse((root / 'shifted' / 'pick.json').exists())

    def test_wrong_commit_refused():
        write('foreign.40-60', SHA['40'], SHA['60'], BETTER, run=1300, foreign=True)
        with t.assertRaises(ValueError):
            hp.pairing_result(root / 'foreign.40-60', SHA['40'], SHA['60'], 0, 2)
        declare('foreign', ['40', '60'])
        t.assertEqual(run_main('foreign')[0], 1)

    def test_constants_line():
        decl = {'const': 'RfpMarginTest', 'values': {'40': SHA['40'], '60': SHA['60']}, 'stages': '2',
                'origin': '0', 'prefer': '40', 'prefer_reason': 'the current value', 'tie_margin': '0.5'}
        results = {('40', '60'): {'ptnml': [8, 24, 80, 56, 32], 'pairs': 200, 'd': 96.3567, 'e': 34.0505,
                                  'runs': [501, 502]}}
        strengths = {'40': (0.0, 0.0), '60': (96.3567, 34.0505)}
        line = hp.constants_line(decl, 'rfp-h2h', results, strengths, '60', False, '2026-11-08')
        t.assertEqual(line, '| `RfpMarginTest` | 60 | **Head-to-head** (2026-11-08, h2h rfp-h2h, runs 501, 502): '
                            'values 40, 60, 2 stages of 200 games on the same openings (400 games); '
                            '60 - 40 +96.36 +/- 34.05 nElo; declared tie rule: 40 (the current value) unless beaten '
                            'by more than 0.5 e. Fork\'s own measurement (DESIGN.md §6, 2026-11-07 decision 3). |')
        kept = hp.constants_line(decl, 'rfp-h2h', results, {'40': (0.0, 0.0), '60': (13.83, 34.05)}, '40', True,
                                 '2026-11-08')
        t.assertIn('| 40 |', kept)
        t.assertIn('60 - 40 +13.83 +/- 34.05 nElo, within 0.5 e: the tie rule keeps 40', kept)

    suite = unittest.TestSuite()
    for f in (test_two_values, test_three_values_closed_form, test_tie_rule, test_unequal_openings_refused,
              test_wrong_commit_refused, test_constants_line):
        suite.addTest(unittest.FunctionTestCase(f))
    suite.addTest(unittest.FunctionTestCase(tmp.cleanup))
    return suite


if __name__ == '__main__':
    unittest.main()
