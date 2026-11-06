# SPDX-License-Identifier: GPL-3.0-or-later

"""What an ended spot instance cost (owner, 2026-10-31): its hours run times
the price paid, the spot price in effect over each part of its run.

A spot instance pays the pool's current spot price, which can change while
it runs, so the run is split at every price change: each part costs its
length in hours times the price in effect at its start (the latest price
row at or before it; before the first row, the first row's price). Run by
tools/cloud/cost_guard.sh when it replaces a launch's worst-case booking
with the actual cost.

    python3 tools/cloud/spot_cost.py PRICES.json START END

PRICES.json holds the pool's `aws ec2 describe-spot-price-history` rows as
[[price, timestamp], ...], covering START (from before it) to END; START
and END are ISO 8601 times. Prints the cost in dollars to the cent.
"""
import json
import sys
from datetime import datetime
from pathlib import Path


def when(stamp):
    return datetime.fromisoformat(stamp.replace('Z', '+00:00')).timestamp()


def cost_between(rows, start, end):
    """Dollars for running from start to end (seconds) at the prices in rows."""
    changes = sorted((when(t), float(p)) for p, t in rows)
    if not changes:
        raise ValueError('no spot price rows')
    price = changes[0][1]
    for t, p in changes:
        if t <= start:
            price = p
    total, at = 0.0, start
    for t, p in changes:
        if start < t < end:
            total += (t - at) / 3600 * price
            at, price = t, p
    return total + max(0.0, end - at) / 3600 * price


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print(__doc__.strip().split('\n\n')[2], file=sys.stderr)
        return 2
    rows = json.loads(Path(argv[0]).read_text())
    print(f'{cost_between(rows, when(argv[1]), when(argv[2])):.2f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
