# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of an ended spot instance's cost (tools/cloud/spot_cost.py).

Costs worked by hand: 2 hours at $0.10 then 1 hour at $0.20 is $0.40.

    python3 -m unittest discover -s tools/cloud -p 'test_*.py'
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spot_cost as sc  # noqa: E402

T0 = sc.when('2026-10-30T20:00:00+00:00')


def at(hours):
    return T0 + hours * 3600


class CostBetween(unittest.TestCase):
    def test_one_price(self):
        rows = [['0.10', '2026-10-30T19:00:00+00:00']]
        self.assertAlmostEqual(sc.cost_between(rows, at(0), at(3)), 0.30)

    def test_price_changes_during_the_run(self):
        rows = [['0.20', '2026-10-30T22:00:00+00:00'], ['0.10', '2026-10-30T18:00:00Z']]
        self.assertAlmostEqual(sc.cost_between(rows, at(0), at(3)), 0.40)

    def test_rows_outside_the_run_do_not_count(self):
        # A change before the start sets the starting price; one after the end is ignored.
        rows = [['0.30', '2026-10-30T10:00:00+00:00'], ['0.10', '2026-10-30T19:30:00+00:00'],
                ['0.90', '2026-10-30T23:30:00+00:00']]
        self.assertAlmostEqual(sc.cost_between(rows, at(0), at(3)), 0.30)

    def test_first_row_after_the_start(self):
        # No row at or before the start: the first row's price covers the gap.
        rows = [['0.10', '2026-10-30T21:00:00+00:00']]
        self.assertAlmostEqual(sc.cost_between(rows, at(0), at(2)), 0.20)

    def test_no_rows(self):
        with self.assertRaises(ValueError):
            sc.cost_between([], at(0), at(1))


if __name__ == '__main__':
    unittest.main()
