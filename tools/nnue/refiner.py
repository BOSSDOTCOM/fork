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

`convert` writes a trained refiner's file from the trainer's float weights
(fork-train --arch refiner's optimiser_state/weights.bin): the refiner
tensors quantised by models.refiner_quantise (R-quant: the factoriser
merged, weights x 64, biases x 255 x 64, rounded half away from zero), the
dense weights checked against the bound, the header bound to the base
network's payload checksum, its output scale the base's.

`parity` runs the parity chain on a .sites file (step3-plan.md 3.6, "the
parity chain"): R-int (models.refiner_int on REFINER's tensors and the base
net) against ENGINE's `fork refine` output (a refiner build embedding
REFINER), exactly, at every line; with --weights, R-quant: REFINER's payload
equal to models.refiner_quantise of the trainer's float weights; with
--weights and --trainer (fork-train --arch refiner eval's output on the same
file), the trainer against R-float (the base: the net's integers / 255)
within 0.0002 in each head's raw output (0.018 cp of correction at S = 89).
Exit 1 on any failure.

usage: python -I tools/nnue/refiner.py zero --base nets/s512ppr3.fnet --arch 1 --l1 16
           --bound 64 --cap 20000 --out tests/nnue/refiner-zero.frnet
       python -I tools/nnue/refiner.py export --base nets/s512ppr3.fnet --out train.sites DIR...
       python -I tools/nnue/refiner.py convert --weights weights.bin --base nets/s512ppr3.fnet --arch 1 --l1 8
           --bound 64 --cap C --out refiner.frnet
       python -I tools/nnue/refiner.py parity ENGINE REFINER --base nets/s512ppr3.fnet --sites FILE.sites
           [--weights weights.bin [--trainer eval.txt]]
"""
import argparse
import json
import struct
import subprocess
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
    convert = sub.add_parser('convert', help="a trained refiner's file from the trainer's float weights")
    convert.add_argument('--weights', required=True, help="fork-train --arch refiner's optimiser_state/weights.bin")
    convert.add_argument('--base', required=True, help='the base network (.fnet) the refiner reads')
    convert.add_argument('--arch', type=int, choices=(1,), required=True)
    convert.add_argument('--l1', type=int, choices=(8, 16), required=True)
    convert.add_argument('--bound', type=int, choices=(64, 32), required=True, help='the dense weights\' bound')
    convert.add_argument('--cap', type=int, required=True)
    convert.add_argument('--out', required=True)
    parity = sub.add_parser('parity', help='the parity chain on a .sites file')
    parity.add_argument('engine', help='a refiner build of fork embedding REFINER')
    parity.add_argument('refiner', type=Path, help='the refiner file (.frnet)')
    parity.add_argument('--base', required=True, help='the base network (.fnet)')
    parity.add_argument('--sites', required=True, type=Path)
    parity.add_argument('--weights', help="the trainer's float weights (optimiser_state/weights.bin)")
    parity.add_argument('--trainer', type=Path, help="fork-train --arch refiner eval's output on --sites")
    args = ap.parse_args(argv)
    if args.command == 'parity':
        base = Path(args.base).read_bytes()
        fields = netformat.header_fields(base)
        name = {v: k for k, v in models.ARCH.items()}[fields['architecture']]
        arch = models.arch_from_net(name, base[netformat.HEADER_BYTES:])
        net = models.unpack(arch, base[netformat.HEADER_BYTES:])
        data = args.refiner.read_bytes()
        version, rarch, l1, _l2, _heads, scale, cap, bound = struct.unpack_from('<IIIIIiiI', data, 8)
        (base_checksum,) = struct.unpack_from('<QQ', data, 40)[1:]
        fails = []
        if (version, rarch) != (REFINER_VERSION, 1) or base_checksum != struct.unpack_from('<Q', base, 40)[0]:
            fails.append(f'{args.refiner}: version {version}, architecture {rarch}, base {base_checksum:016x}')
        q, at = [], netformat.HEADER_BYTES
        for (_, count, size), kind in zip(payload_sizes(rarch, l1, fields['hidden'], max(fields['buckets'], 1)),
                                          ('i8', 'i32', 'i16', 'i8', 'i32', 'i16', 'i32')):
            q.append((kind, list(struct.unpack_from(f'<{count}{models.CODES[kind]}', data, at))))
            at += count * size
        lines = args.sites.read_text(encoding='utf-8').splitlines()
        if args.weights:
            floats = netformat.read_weights_bin(Path(args.weights).read_bytes())
            r = {k: [models.to_f32(x) for x in floats[k]] for k in ('entry_weights', 'entry_bias', 'row_weights',
                                                                     'middle_weights', 'middle_bias', 'head_weights',
                                                                     'head_bias')}
            if models.pack(models.refiner_quantise(r)) != data[netformat.HEADER_BYTES:]:
                fails.append('R-quant: the refiner file is not the quantised weights')
        engine = subprocess.run([args.engine, 'refine'], input='\n'.join(lines) + '\n', capture_output=True, text=True,
                                check=True).stdout.split('\n')
        mismatched = 0
        for line, out in zip(lines, engine):
            fen, base_eval = line.split(' | ')[:2]
            want = models.refiner_int(arch, net, scale, q, cap, chess.Board(fen), int(base_eval), max(fields['buckets'], 1))
            if out.split() != [str(want[0]), str(want[1])]:
                mismatched += 1
                if mismatched <= 3:
                    fails.append(f'R-int {want} against the engine {out!r} at {fen}')
        if len([o for o in engine if o]) != len(lines) or mismatched:
            fails.append(f'engine leg: {mismatched} of {len(lines)} lines differ')
        worst = 0.0
        if args.weights and args.trainer:
            w = {'l0w': [models.to_f32(x / models.QA) for x in net['ftw']], 'l0b': [models.to_f32(x / models.QA) for x in net['ftb']]}
            trainer = [list(map(float, t.split())) for t in args.trainer.read_text(encoding='utf-8').splitlines()]
            for line, t in zip(lines, trainer):
                fen, base_eval = line.split(' | ')[:2]
                y = models.refiner_float(arch, w, r, chess.Board(fen), int(base_eval), max(fields['buckets'], 1))
                worst = max(worst, abs(y[0] - t[0]), abs(y[1] - t[1]))
            if len(trainer) != len(lines) or worst > 0.0002:
                fails.append(f'trainer leg: {len(trainer)} lines for {len(lines)}, worst difference {worst:.6f}')
        print(f'parity on {len(lines)} sites: engine leg {len(lines) - mismatched} exact'
              + (', R-quant checked' if args.weights else '')
              + (f', trainer leg worst {worst:.6f}' if args.weights and args.trainer else ''))
        for msg in fails:
            print('FAIL', msg, file=sys.stderr)
        return 1 if fails else 0
    if args.command == 'convert':
        if not 0 <= args.cap <= 20000:
            ap.error('--cap must lie in [0, 20000]')
        base = Path(args.base).read_bytes()
        fields = netformat.header_fields(base)
        (base_checksum,) = struct.unpack_from('<Q', base, 40)
        floats = netformat.read_weights_bin(Path(args.weights).read_bytes())
        names = ('entry_weights', 'entry_bias', 'row_weights', 'middle_weights', 'middle_bias', 'head_weights', 'head_bias')
        r = {name: [models.to_f32(x) for x in floats[name]] for name in names}
        rows = 640 + models.REFINER_FACTORS + max(fields['buckets'], 1) + 16
        expected = {'entry_weights': args.l1 * 2 * fields['hidden'], 'entry_bias': args.l1, 'row_weights': rows * args.l1,
                    'middle_weights': 32 * args.l1, 'middle_bias': 32, 'head_weights': 64, 'head_bias': 2}
        for name, count in expected.items():
            if len(r[name]) != count:
                raise SystemExit(f'{name}: {len(r[name])} values, the shape needs {count}')
        q = models.refiner_quantise(r)
        for i in (0, 3):  # the dense (i8) layers
            worst = max(abs(x) for x in q[i][1])
            if worst > args.bound:
                raise SystemExit(f'{names[i]}: a weight of {worst} outside the bound {args.bound}')
        data = refiner_file(args.arch, args.l1, args.bound, fields['scale'], args.cap, base_checksum, models.pack(q))
        Path(args.out).write_bytes(data)
        print(f'{args.out}: {len(data)} bytes, architecture {args.arch}, entry width {args.l1}, bound {args.bound}, '
              f'S {fields["scale"]}, cap {args.cap}, base {base_checksum:016x}')
        return 0
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
