# SPDX-License-Identifier: GPL-3.0-or-later

"""Converts bullet's quantised.bin into Fork's net file (DESIGN.md §5.3,
deliverable 5; §5.4 for the bake-off architectures), using the network's
tensor description (tools/nnue/b0.json, or s512/h512/afs/xgr512.json with
their fitted maps). Fork's format never depends on the trainer's layout;
the parity test (tools/nnue/reference.py) checks this conversion end to end.

    convert.py quantised.bin OUT.fnet --scale S [--layout b0.json]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import models  # noqa: E402
import netformat  # noqa: E402


def arch_of(desc):
    return models.Arch(desc['name'], desc.get('regions'), desc.get('table'))


def convert(data, desc, scale):
    tensors = netformat.read_quantised(data, desc)
    if desc['architecture'] == 1:
        return netformat.write_net(netformat.fork_payload(tensors, desc), desc, scale)
    arch = arch_of(desc)
    kinds = {t['name']: t['type'] for t in desc['quantised']}
    saved = {name: (kinds[name], values) for name, values in tensors.items()}
    payload = models.map_block(arch) + models.pack(models.fork_tensors(arch, saved, scale))
    return netformat.write_net2(arch.id, arch.saved_inputs, arch.hidden, 8 if arch.picker else 1, scale, payload)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('quantised')
    ap.add_argument('out')
    ap.add_argument('--scale', type=int, required=True, help='S, the output scale fitted for the training run')
    ap.add_argument('--layout')
    a = ap.parse_args(argv)
    desc = netformat.layout(a.layout)
    data = convert(Path(a.quantised).read_bytes(), desc, a.scale)
    Path(a.out).write_bytes(data)
    print(f'{a.out}: {len(data)} bytes, checksum {netformat.net_checksum(data[netformat.HEADER_BYTES:]):016x}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
