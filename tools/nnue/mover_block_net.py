# SPDX-License-Identifier: GPL-3.0-or-later
"""An H512+PP+M net file (architecture 11, idea 178's prototype; src/eval/nnue/net_shape.hpp) from an H512+PP one
(architecture 9): the same header and payload, the architecture id 11, and the block's 640 x 64 int16 weights
appended after the output layer (zero by default, so the evaluation equals the source net's), the checksum
recomputed.

    mover_block_net.py SOURCE.fnet OUT.fnet [--perturb MAX --seed N]

--perturb MAX fills the block with seeded uniform integers in [-MAX, MAX] (the equivalence and Debug checks: the
evaluation then changes wherever the side to move has an exposed piece).
"""
import argparse
import random
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import netformat  # noqa: E402

BLOCK_ROWS, BLOCK_COLUMNS = 640, 64


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('source')
    ap.add_argument('out')
    ap.add_argument('--perturb', type=int, default=0)
    ap.add_argument('--seed', type=int, default=20261114)
    args = ap.parse_args(argv)
    data = Path(args.source).read_bytes()
    head = netformat.header_fields(data)
    if head['architecture'] != 9:
        sys.exit('an architecture 9 (H512+PP) source is expected')
    rng = random.Random(args.seed)
    n = BLOCK_ROWS * BLOCK_COLUMNS
    values = [rng.randint(-args.perturb, args.perturb) for _ in range(n)] if args.perturb else [0] * n
    payload = data[netformat.HEADER_BYTES:] + struct.pack(f'<{n}h', *values)
    header = bytearray(data[:netformat.HEADER_BYTES])
    struct.pack_into('<I', header, 12, 11)
    struct.pack_into('<Q', header, 40, netformat.net_checksum(payload))
    Path(args.out).write_bytes(bytes(header) + payload)
    print(f'{args.out}: {len(header) + len(payload)} bytes, block weights in [-{args.perturb}, {args.perturb}]')


if __name__ == '__main__':
    main()
