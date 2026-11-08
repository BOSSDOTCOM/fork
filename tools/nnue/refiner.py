# SPDX-License-Identifier: GPL-3.0-or-later

"""The Boundary Refiner's file (ideas.md 59, step 3; the format is specified
in src/eval/nnue/refiner_file.hpp's header comment, and this writer follows
that text, not the C++ code).

For now one command: `zero` writes a refiner whose every weight and bias is
zero, for the speed gate's identical-tree measurement (the plan's M1,
docs/research/boundary-refiner/step3-plan.md §4.5) and as the refiner
build's test file. Its output scale S is the base network's own, its cap C is
given (the committed test file uses 20,000, EvalLimit: no cap, so a zero
correction comes from the zero weights alone), and its header binds it to
the base network's payload checksum. The trained refiner's converter and
references (R-float, R-quant, R-int) come later, here.

usage: python -I tools/nnue/refiner.py zero --base nets/s512ppr3.fnet --arch 1 --l1 16
           --cap 20000 --out tests/nnue/refiner-zero.frnet
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import netformat  # noqa: E402

REFINER_MAGIC = b'FORKRFN\0'
REFINER_VERSION = 1


def payload_sizes(arch, l1, hidden, buckets):
    """The payload's tensors in file order: (name, values, bytes per value).
    Rows: 640 exposure rows, 36 danger rows in architecture 2, the base's
    phase buckets and 16 evaluation bins."""
    rows = 640 + (36 if arch == 2 else 0) + buckets + 16
    return [('entry weights', l1 * 2 * hidden, 1), ('entry biases', l1, 4), ('row weights', rows * l1, 2),
            ('middle weights', 32 * l1, 1), ('middle biases', 32, 4), ('head weights', 2 * 32, 2),
            ('head biases', 2, 4)]


def zero_payload(arch, l1, hidden, buckets):
    return bytes(sum(n * size for _, n, size in payload_sizes(arch, l1, hidden, buckets)))


def refiner_file(arch, l1, scale, cap, base_checksum, payload):
    """The header (64 bytes) and the payload."""
    header = REFINER_MAGIC + struct.pack('<IIIIIiiI', REFINER_VERSION, arch, l1, 32, 2, scale, cap, 0)
    header += struct.pack('<QQ', netformat.net_checksum(payload), base_checksum)
    return header.ljust(netformat.HEADER_BYTES, b'\0') + payload


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    zero = sub.add_parser('zero', help='a refiner with every weight zero')
    zero.add_argument('--base', required=True, help='the base network (.fnet) the refiner reads')
    zero.add_argument('--arch', type=int, choices=(1, 2), required=True)
    zero.add_argument('--l1', type=int, choices=(8, 16), required=True)
    zero.add_argument('--cap', type=int, required=True)
    zero.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    if not 0 <= args.cap <= 20000:
        ap.error('--cap must lie in [0, 20000]')
    base = Path(args.base).read_bytes()
    fields = netformat.header_fields(base)  # checks the magic and the checksum
    (base_checksum,) = struct.unpack_from('<Q', base, 40)
    data = refiner_file(args.arch, args.l1, fields['scale'], args.cap, base_checksum,
                        zero_payload(args.arch, args.l1, fields['hidden'], max(fields['buckets'], 1)))
    Path(args.out).write_bytes(data)
    print(f'{args.out}: {len(data)} bytes, architecture {args.arch}, entry width {args.l1}, '
          f'S {fields["scale"]}, cap {args.cap}, base {base_checksum:016x}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
