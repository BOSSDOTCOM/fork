# SPDX-License-Identifier: GPL-3.0-or-later

"""The Boundary Refiner's file (ideas.md 59, step 3; the format is specified
in src/eval/nnue/refiner_file.hpp's header comment, and this writer follows
that text, not the C++ code).

`zero` writes a refiner whose every weight and bias is zero, for the speed gate's identical-tree measurement (the plan's M1,
docs/research/boundary-refiner/step3-plan.md §4.5) and as the refiner
build's test file. Its output scale S is the base network's own, its cap C is
given (the committed test file uses 20,000, EvalLimit: no cap, so a zero
correction comes from the zero weights alone), and its header binds it to
the base network's payload checksum.

`export` writes one split's labelled sites (each folder's sites.jsonl,
deep.tsv and weights.tsv: tools/measure/crucial_points.py `deep`,
deep_labels.py `weights`) as the trainer's .sites file, one line per site:

    FEN | base | label | weight | rows

base the site's logged static evaluation (the refiner's base, side to move's
view, cp), label the deep label (cp), weight the training weight (0 for the
mate-flagged labels and the table band, which the loss leaves out), rows the
refiner's active rows in architecture 1 (models.refiner_rows, from the base
network's phase table). The trainer centres the target itself (step3-plan.md
3.7).

usage: python -I tools/nnue/refiner.py zero --base nets/s512ppr3.fnet --arch 1 --l1 16
           --bound 64 --cap 20000 --out tests/nnue/refiner-zero.frnet
       python -I tools/nnue/refiner.py export --base nets/s512ppr3.fnet --out train.sites DIR...
"""
import argparse
import json
import struct
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import models  # noqa: E402
import netformat  # noqa: E402

REFINER_MAGIC = b'FORKRFN\0'
REFINER_VERSION = 2  # 2 adds the dense-weight bound at header byte 36


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


def refiner_file(arch, l1, bound, scale, cap, base_checksum, payload):
    """The header (64 bytes) and the payload."""
    header = REFINER_MAGIC + struct.pack('<IIIIIiiI', REFINER_VERSION, arch, l1, 32, 2, scale, cap, bound)
    header += struct.pack('<QQ', netformat.net_checksum(payload), base_checksum)
    return header.ljust(netformat.HEADER_BYTES, b'\0') + payload


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    zero = sub.add_parser('zero', help='a refiner with every weight zero')
    zero.add_argument('--base', required=True, help='the base network (.fnet) the refiner reads')
    zero.add_argument('--arch', type=int, choices=(1, 2), required=True)
    zero.add_argument('--l1', type=int, choices=(8, 16), required=True)
    zero.add_argument('--bound', type=int, choices=(64, 32), required=True, help='the dense weights\' bound')
    zero.add_argument('--cap', type=int, required=True)
    zero.add_argument('--out', required=True)
    export = sub.add_parser('export', help="a split's labelled sites as the trainer's .sites file")
    export.add_argument('--base', required=True, help='the base network (.fnet): its phase table and bucket count')
    export.add_argument('--out', required=True)
    export.add_argument('dir', type=Path, nargs='+', help='folders with sites.jsonl, deep.tsv and weights.tsv')
    args = ap.parse_args(argv)
    if args.command == 'export':
        base = Path(args.base).read_bytes()
        fields = netformat.header_fields(base)
        name = {v: k for k, v in models.ARCH.items()}[fields['architecture']]
        arch = models.arch_from_net(name, base[netformat.HEADER_BYTES:])
        lines = weighted = active = 0
        with open(args.out, 'w', encoding='utf-8', newline='\n') as f:
            for folder in args.dir:
                labels = {}
                for line in (folder / 'deep.tsv').read_text(encoding='utf-8').splitlines():
                    i, value, _mate, _depth = line.split('\t')
                    labels[int(i)] = int(value)
                weights = {}
                for line in (folder / 'weights.tsv').read_text(encoding='utf-8').splitlines():
                    i, training, _acceptance = line.split('\t')
                    weights[int(i)] = training
                for line in (folder / 'sites.jsonl').read_text(encoding='utf-8').splitlines():
                    s = json.loads(line)
                    if s['id'] not in labels:
                        continue
                    rows = models.refiner_rows(arch, chess.Board(s['fen']), s['eval'], fields['buckets'])
                    f.write(f"{s['fen']} | {s['eval']} | {labels[s['id']]} | {weights[s['id']]} | "
                            f"{' '.join(map(str, rows))}\n")
                    lines += 1
                    weighted += float(weights[s['id']]) > 0
                    active += len(rows)
        print(f'{args.out}: {lines} sites ({weighted} weighted), {active / max(lines, 1):.2f} active rows per site')
        return 0
    if not 0 <= args.cap <= 20000:
        ap.error('--cap must lie in [0, 20000]')
    base = Path(args.base).read_bytes()
    fields = netformat.header_fields(base)  # checks the magic and the checksum
    (base_checksum,) = struct.unpack_from('<Q', base, 40)
    data = refiner_file(args.arch, args.l1, args.bound, fields['scale'], args.cap, base_checksum,
                        zero_payload(args.arch, args.l1, fields['hidden'], max(fields['buckets'], 1)))
    Path(args.out).write_bytes(data)
    print(f'{args.out}: {len(data)} bytes, architecture {args.arch}, entry width {args.l1}, '
          f'bound {args.bound}, S {fields["scale"]}, cap {args.cap}, base {base_checksum:016x}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
