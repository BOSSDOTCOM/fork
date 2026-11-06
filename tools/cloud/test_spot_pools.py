# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of the launch rule's pool ranking (tools/cloud/spot_pools.py).

The expected costs are worked by hand: a rate of 2000 positions/s is 7.2 M
positions an hour, so $0.144/h is $0.02 per million and the $0.03 limit is
reached at $0.216/h.

    python3 -m unittest discover -s tools/cloud -p 'test_*.py'
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spot_pools as sp  # noqa: E402

SUBNETS = [['subnet-a', 'z-a'], ['subnet-b', 'z-b']]


class Rank(unittest.TestCase):
    def test_cheapest_per_million_first(self):
        # c7a is cheaper per hour in z-a but slower: $0.10 / 3.6 M = 0.0278 per M,
        # c8a $0.144 / 7.2 M = 0.02.
        rates = {'c8a.2xlarge': 2000, 'c7a.2xlarge': 1000}
        prices = {('c8a.2xlarge', 'z-a'): 0.144, ('c7a.2xlarge', 'z-a'): 0.10}
        pools, refused = sp.rank(['c7a.2xlarge', 'c8a.2xlarge'], SUBNETS[:1], prices, rates, 0.25, 0.03)
        self.assertEqual([p['type'] for p in pools], ['c8a.2xlarge', 'c7a.2xlarge'])
        self.assertAlmostEqual(pools[0]['per_m'], 0.02)
        self.assertEqual(refused, [])

    def test_over_the_limit_or_the_cap_is_left_out(self):
        rates = {'c8a.2xlarge': 2000}
        prices = {('c8a.2xlarge', 'z-a'): 0.2161, ('c8a.2xlarge', 'z-b'): 0.216}
        pools, refused = sp.rank(['c8a.2xlarge'], SUBNETS, prices, rates, 0.25, 0.03)
        self.assertEqual([p['zone'] for p in pools], ['z-b'])  # exactly at the limit qualifies
        self.assertIn('over the limit', refused[0][1])
        pools, refused = sp.rank(['c8a.2xlarge'], SUBNETS, prices, rates, 0.20, 0.03)
        self.assertEqual(pools, [])
        self.assertTrue(all('price cap' in why for _, why in refused))

    def test_unmeasured_types_and_missing_prices_are_left_out(self):
        rates = {'c8a.2xlarge': 2000}
        prices = {('c8a.2xlarge', 'z-a'): 0.10, ('m7a.2xlarge', 'z-a'): 0.01}
        pools, refused = sp.rank(['m7a.2xlarge', 'c8a.2xlarge'], SUBNETS, prices, rates, 0.25, 0.03)
        self.assertEqual([(p['type'], p['zone']) for p in pools], [('c8a.2xlarge', 'z-a')])
        self.assertEqual(refused, [('m7a.2xlarge', 'no measured rate for these settings'),
                                   ('c8a.2xlarge z-b', 'no spot price')])

    def test_ties_keep_the_types_order(self):
        rates = {'c8a.2xlarge': 2000, 'c7a.2xlarge': 2000}
        prices = {('c8a.2xlarge', 'z-a'): 0.1, ('c7a.2xlarge', 'z-a'): 0.1}
        for order in (['c8a.2xlarge', 'c7a.2xlarge'], ['c7a.2xlarge', 'c8a.2xlarge']):
            pools, _ = sp.rank(order, SUBNETS[:1], prices, rates, 0.25, 0.03)
            self.assertEqual([p['type'] for p in pools], order)

    def test_max_price_is_the_limit_rounded_down_within_the_cap(self):
        # 1640 positions/s: 5.904 M an hour, the limit at $0.17712/h.
        pools, _ = sp.rank(['c7a.2xlarge'], SUBNETS[:1], {('c7a.2xlarge', 'z-a'): 0.1},
                           {'c7a.2xlarge': 1640}, 0.25, 0.03)
        self.assertEqual(sp.overrides(pools), [{'InstanceType': 'c7a.2xlarge', 'SubnetId': 'subnet-a',
                                                'Priority': 1, 'MaxPrice': '0.1771'}])
        pools, _ = sp.rank(['c7a.2xlarge'], SUBNETS[:1], {('c7a.2xlarge', 'z-a'): 0.1},
                           {'c7a.2xlarge': 1640}, 0.15, 0.03)
        self.assertEqual(sp.overrides(pools)[0]['MaxPrice'], '0.1500')
        # 2075 positions/s: 0.03 x 7.47 = 0.2241, just below it in floating point.
        pools, _ = sp.rank(['c8a.2xlarge'], SUBNETS[:1], {('c8a.2xlarge', 'z-a'): 0.1},
                           {'c8a.2xlarge': 2075}, 0.25, 0.03)
        self.assertEqual(sp.overrides(pools)[0]['MaxPrice'], '0.2241')


class Inputs(unittest.TestCase):
    def test_the_latest_price_of_a_pool_counts(self):
        rows = [['z-a', 'c8a.2xlarge', '0.30', '2026-10-30T20:00:00+00:00'],
                ['z-a', 'c8a.2xlarge', '0.12', '2026-10-30T22:00:00+00:00'],
                ['z-a', 'c8a.2xlarge', '0.20', '2026-10-30T21:00:00+00:00']]
        self.assertEqual(sp.latest_prices(rows), {('c8a.2xlarge', 'z-a'): 0.12})

    def test_rates_match_net_nodes_and_adjudication(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'rates.tsv'
            f.write_text('# comment\tline\n'
                         'c8a.2xlarge\ts512\t20000\t700/8\t2075\t18\tcpu\tsource\n'
                         'c8a.2xlarge\tb0r2\t20000\t700/8\t2500\t1\tcpu\tsource\n'
                         'c7a.2xlarge\ts512\t20000\toff\t1500\t1\tcpu\tsource\n'
                         'm7a.2xlarge\ts512\t10000\t700/8\t3000\t1\tcpu\tsource\n', encoding='utf-8')
            self.assertEqual(sp.load_rates(f, 's512', 20000, '700/8'), {'c8a.2xlarge': 2075.0})
            self.assertEqual(sp.load_rates(f, 's512', 20000, 'off'), {'c7a.2xlarge': 1500.0})

    def test_the_committed_rates_parse(self):
        rates = sp.load_rates(Path(__file__).with_name('datagen-rates.tsv'), 's512', 20000, '700/8')
        self.assertIn('c8a.2xlarge', rates)
        self.assertTrue(all(r > 0 for r in rates.values()))

    def test_no_pool_exits_3(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / 'r.tsv').write_text('c8a.2xlarge\ts512\t20000\t700/8\t2000\n', encoding='utf-8')
            (d / 'p.json').write_text(json.dumps([['z-a', 'c8a.2xlarge', '0.24', 't']]))
            (d / 's.json').write_text(json.dumps(SUBNETS))
            args = ['--rates', str(d / 'r.tsv'), '--net', 's512', '--nodes', '20000', '--adjudicate', '700/8',
                    '--types', 'c8a.2xlarge', '--max-price', '0.25', '--max-cost-per-m', '0.03',
                    '--prices', str(d / 'p.json'), '--subnets', str(d / 's.json')]
            self.assertEqual(sp.main(args), 3)


if __name__ == '__main__':
    unittest.main()
