# SPDX-License-Identifier: GPL-3.0-or-later

"""Converts bullet's quantised.bin for B0 into Fork's net file (DESIGN.md
§5.3, deliverable 5), using B0's tensor description (tools/nnue/b0.json).
Fork's format never depends on the trainer's layout; the parity test
(tools/nnue/reference.py) checks this conversion end to end.

    convert.py quantised.bin OUT.fnet --scale S [--layout b0.json]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import netformat  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('quantised')
    ap.add_argument('out')
    ap.add_argument('--scale', type=int, required=True, help='S, the output scale fitted for the training run')
    ap.add_argument('--layout')
    a = ap.parse_args(argv)
    desc = netformat.layout(a.layout)
    tensors = netformat.read_quantised(Path(a.quantised).read_bytes(), desc)
    data = netformat.write_net(netformat.fork_payload(tensors, desc), desc, a.scale)
    Path(a.out).write_bytes(data)
    print(f'{a.out}: {len(data)} bytes, checksum {netformat.net_checksum(data[netformat.HEADER_BYTES:]):016x}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
