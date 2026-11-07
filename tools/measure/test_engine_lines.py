# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/measure/engine_lines.py: the stats build's line formats.

    python -I -B -m unittest discover -s tools/measure -p 'test_*.py'
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine_lines as el  # noqa: E402


class EngineLinesTests(unittest.TestCase):
    def test_counter_line(self):
        self.assertEqual(el.parse_counter_line('search_counters main_nodes=5 evals_main=3\n'),
                         {'main_nodes': 5, 'evals_main': 3})

    def test_hist_line(self):
        self.assertEqual(el.parse_hist_line('search_hist lmr_order 0 1 2'), ('lmr_order', [0, 1, 2]))

    def test_iteration_line(self):
        row = el.parse_iteration_line('iteration_trace 7|796|812|790|101|5000|5600|-31|2|30|14')
        self.assertEqual(row['depth'], 7)
        self.assertEqual(row['score'], -31)
        self.assertEqual(row['seldepth'], 14)
        self.assertEqual(len(row), 11)

    def test_ledger_line(self):
        rfp = el.parse_ledger_line('prune_ledger rfp|3|9|250|240|240|2|5|-12|20|1|-40|1234|0')
        self.assertEqual((rfp['technique'], rfp['depth'], rfp['fired'], rfp['arm_minus_beta']), ('rfp', 3, 1, -40))
        fut = el.parse_ledger_line('prune_ledger futility|2|11|300|310|240|0|-1|7|14|1|-1|5|100|180|0')
        self.assertEqual((fut['technique'], fut['on_minus_beta'], fut['off_minus_beta'], fut['off_nodes']),
                         ('futility', -1, 5, 180))

    def test_counter_delta(self):
        before = {'a': 1, 'h': [0, 2]}
        after = {'a': 4, 'h': [1, 2]}
        self.assertEqual(el.counter_delta(after, before), {'a': 3, 'h': [1, 0]})
        self.assertEqual(el.counter_delta(after, None), after)
        with self.assertRaises(ValueError):
            el.counter_delta(before, after)  # counters never go down
        with self.assertRaises(ValueError):
            el.counter_delta({'a': 1}, {'b': 1})

    def test_malformed_lines(self):
        for bad in ('search_counters', 'search_counters a', 'search_counters a=1 a=2', 'other a=1'):
            with self.assertRaises(ValueError, msg=bad):
                el.parse_counter_line(bad)
        with self.assertRaises(ValueError):
            el.parse_iteration_line('iteration_trace 1|2|3')
        with self.assertRaises(ValueError):
            el.parse_ledger_line('prune_ledger nmp|1|2')
        with self.assertRaises(ValueError):
            el.parse_ledger_line('prune_ledger rfp|1|2')
        with self.assertRaises(ValueError):
            el.parse_hist_line('search_hist name')


if __name__ == '__main__':
    unittest.main()
