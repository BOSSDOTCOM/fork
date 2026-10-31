# SPDX-License-Identifier: GPL-3.0-or-later

"""Spot pools for a data-generation launch, ranked by expected cost per
million positions (owner, 2026-10-30).

A pool is one instance type in one availability zone. Its expected cost per
million positions is its current spot price over the type's measured rate:
positions per second from tools/cloud/datagen-rates.tsv, for the same
network, nodes and score adjudication (the rate is measured on the type's
own chunks; a type without one cannot be judged and is left out). Pools
whose price is above --max-price or whose cost is above --max-cost-per-m
are left out too; the rest are ranked cheapest first, ties in --types
order. Each pool's maximum price is the price at which it reaches the cost
limit (at most --max-price), so the fleet never launches above the limit
and an instance whose price later climbs past it is interrupted.

    python3 tools/cloud/spot_pools.py --rates FILE --net s512 --nodes 20000 --adjudicate 700/8 \\
        --types c8a.2xlarge,c7a.2xlarge --max-price 0.25 --max-cost-per-m 0.03 \\
        --prices PRICES.json --subnets SUBNETS.json

PRICES.json holds `aws ec2 describe-spot-price-history` rows as
[[zone, type, price, timestamp], ...] (the latest row of a pool counts) and
SUBNETS.json [[subnet, zone], ...]. Prints the fleet's overrides as JSON on
stdout and the ranking on stderr; exits 3 when no pool qualifies.
"""
import argparse
import json
import math
import sys
from pathlib import Path


def load_rates(path, net, nodes, adjudicate):
    """{type: positions per second} for the rows measured with these settings.
    Columns: type, net, nodes, adjudicate (CP/PLIES or off), positions/s,
    then free text (chunks, CPU, source)."""
    rates = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        f = line.split('\t')
        if f[1:4] == [net, str(nodes), adjudicate]:
            rates[f[0]] = float(f[4])
    return rates


def latest_prices(rows):
    """{(type, zone): dollars an hour} from the latest row of each pool."""
    latest = {}
    for zone, itype, price, stamp in rows:
        if (itype, zone) not in latest or stamp > latest[itype, zone][1]:
            latest[itype, zone] = (float(price), stamp)
    return {k: p for k, (p, _) in latest.items()}


def millions_an_hour(rate):
    return rate * 3600 / 1e6


def rank(types, subnets, prices, rates, max_price, limit):
    """(pools ranked cheapest first, [(pool, reason)] left out)."""
    pools, refused = [], []
    for order, t in enumerate(types):
        if t not in rates:
            refused.append((t, 'no measured rate for these settings'))
            continue
        per_hour = millions_an_hour(rates[t])
        for subnet, zone in subnets:
            price = prices.get((t, zone))
            if price is None:
                refused.append((f'{t} {zone}', 'no spot price'))
            elif price > max_price:
                refused.append((f'{t} {zone}', f'${price:.4f}/h is over the price cap ${max_price}'))
            elif price / per_hour > limit:
                refused.append((f'{t} {zone}', f'${price / per_hour:.4f} per M is over the limit ${limit}'))
            else:
                # Rounded down to 0.0001 (past float error), so the cap stays within the limit.
                cap = math.floor(min(max_price, limit * per_hour) * 1e4 + 1e-6) / 1e4
                pools.append({'type': t, 'zone': zone, 'subnet': subnet, 'price': price, 'rate': rates[t],
                              'per_m': price / per_hour, 'max_price': cap, 'order': order})
    pools.sort(key=lambda p: (p['per_m'], p['order'], p['zone']))
    return pools, refused


def overrides(pools):
    return [{'InstanceType': p['type'], 'SubnetId': p['subnet'], 'Priority': i + 1,
             'MaxPrice': f"{p['max_price']:.4f}"} for i, p in enumerate(pools)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--rates', required=True)
    ap.add_argument('--net', required=True)
    ap.add_argument('--nodes', type=int, required=True)
    ap.add_argument('--adjudicate', required=True, help='CP/PLIES, or off')
    ap.add_argument('--types', required=True, help='comma-separated, in preference order for ties')
    ap.add_argument('--max-price', type=float, required=True)
    ap.add_argument('--max-cost-per-m', type=float, required=True)
    ap.add_argument('--prices', required=True)
    ap.add_argument('--subnets', required=True)
    a = ap.parse_args(argv)
    rates = load_rates(a.rates, a.net, a.nodes, a.adjudicate)
    prices = latest_prices(json.loads(Path(a.prices).read_text()))
    subnets = json.loads(Path(a.subnets).read_text())
    pools, refused = rank(a.types.split(','), subnets, prices, rates, a.max_price, a.max_cost_per_m)
    for i, p in enumerate(pools):
        print(f"  {i + 1}. {p['type']} {p['zone']}: ${p['price']:.4f}/h, {p['rate']:.0f} positions/s, "
              f"${p['per_m']:.4f} per M (max price ${p['max_price']:.4f})", file=sys.stderr)
    for what, why in refused:
        print(f'  left out: {what}: {why}', file=sys.stderr)
    if not pools:
        print(f'no pool within ${a.max_cost_per_m} per million positions', file=sys.stderr)
        return 3
    print(json.dumps(overrides(pools)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
