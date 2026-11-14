# SPDX-License-Identifier: GPL-3.0-or-later

"""S512+X's warm start (owner, 2026-11-02: XGR's exposure plane as an add-on
to S512r2): S-512's float weights (bullet's optimiser_state/weights.bin,
records sorted by name) with the 650 exposure inputs (640 rows and their
10-input factoriser, tools/train --arch s512x) appended to the first layer
as zero columns. bullet stores the first layer input by input (hidden values
per input), so the new inputs are hidden x 650 zeros at the end of l0w;
every other tensor is copied. With zero exposure weights the network
computes exactly S-512's output, so the warm start begins at S512r2's
validation loss.

S512cl's warm start (ideas.md 41) is the same with its contact and link
inputs (tools/nnue/contacts.py; no factoriser) appended instead, done on the
file's bytes (its first layer has about 27 M values); S512+PP's (ideas.md
40) with its links of rank limit 1 only.

H512+PP's warm start (bake-off round 3's option a, architecture 9; owner,
2026-11-14), from an S512+PP net (r8brft1 first; the next default's when
one is promoted): S512+PP's piece inputs copied per own-king region of the
map M4 (models.XGR_REGIONS), the links shared after the region rows. Two
forms, whose evaluations are the source's exactly:
- from S512+PP's float weights (weights.bin), the trainer's warm start
  (tools/train --arch h512pp --init-weights): every region's rows zero, the
  factoriser rows S512+PP's piece rows, the links copied; that is, S512+PP's
  first layer with 768 x 4 zero inputs put before it. The trainer saves a
  region's rows as region + factoriser (an f32 addition of zero), so the
  quantised file is S512+PP's piece rows in every region.
- from S512+PP's net file (Fork's integer file), the engine's net: every
  region's rows S512+PP's piece rows, the links, biases, output layer, phase
  table and scale copied; the map block names the regions. A build with it
  gives the source's bench. With --perturb SEED the regions after the first
  move each weight a small, seeded step toward zero (never away, so the
  reader's bounds still hold), so every region differs: a test net for the
  incremental and snapshot checks.
The source's kind is read from its first bytes (a Fork net file starts with
FORKNET).

S512+PPXL's warm start (bake-off round 3's x_lower arm, architecture 10;
owner, 2026-11-14), from an S512+PP net the same way (r8brft1 first; 8c's
winner when promoted), with the exposure plane's inputs at zero, so its
evaluations are the source's exactly:
- from S512+PP's float weights (weights.bin), the trainer's warm start
  (tools/train --arch s512ppxl --init-weights): the 640 exposure inputs and
  their 10-input factoriser put between the 768 piece inputs and the 608
  links, as zeros (the trainer's order: pieces, exposure, its factoriser,
  links);
- from S512+PP's net file, the engine's net: the 640 exposure rows put
  between the piece rows and the links as zeros, everything else copied. A
  build with it gives the source's bench. With --perturb SEED the exposure
  rows take small seeded weights instead (a test net whose evaluations
  depend on the exposed set; the reader does not bound the exposure rows,
  which Fork sums in 32 bits).

    extend_weights.py S512_WEIGHTS.bin OUT.bin [--arch s512x|s512cl|s512pp|h512pp|s512ppxl]
    extend_weights.py S512PP.fnet OUT.fnet --arch h512pp|s512ppxl [--perturb SEED]
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contacts  # noqa: E402
import models  # noqa: E402
import netformat  # noqa: E402

EXPOSURE_INPUTS = models.EXPOSURE_ROWS + 10  # the rows and their factoriser


def add_exposure_inputs(weights, hidden=512):
    """S-512's weights {name: floats} as S512+X's initial weights."""
    if len(weights['l0w']) != models.PIECE_SQUARES * hidden or len(weights['l0b']) != hidden:
        raise ValueError("not S-512's first layer")
    out = dict(weights)
    out['l0w'] = list(weights['l0w']) + [0.0] * (EXPOSURE_INPUTS * hidden)
    return out


def contact_inputs():
    return contacts.contact_count() + contacts.link_count()


def append_l0w_inputs(data, count, hidden=512):
    """weights.bin bytes with `count` zero inputs (hidden zeros each)
    appended to l0w, every other record copied byte for byte."""
    out, at, done = bytearray(), 0, False
    while at < len(data):
        nl = data.index(b'\n', at)
        name = data[at:nl].decode('ascii')
        (n,) = struct.unpack_from('<Q', data, nl + 1)
        body = data[nl + 9:nl + 9 + 4 * n]
        if name == 'l0w':
            if n != models.PIECE_SQUARES * hidden:
                raise ValueError("not S-512's first layer")
            out += b'l0w\n' + struct.pack('<Q', n + count * hidden) + body + bytes(4 * count * hidden)
            done = True
        else:
            out += data[at:nl + 9 + 4 * n]
        at = nl + 9 + 4 * n
    if not done:
        raise ValueError('no l0w record')
    return bytes(out)


def pp_links():
    return contacts.link_count(contacts.S512PP_RANKS)


def regioned_weights(data, regions=models.XGR_REGIONS, hidden=512):
    """S512+PP's weights.bin bytes as H512+PP's warm start: 768 zero inputs per
    region put before l0w's inputs (S512+PP's piece rows become the
    factoriser, its links stay last), every other record copied byte for
    byte."""
    count = models.PIECE_SQUARES * (max(regions) + 1)
    out, at, done = bytearray(), 0, False
    while at < len(data):
        nl = data.index(b'\n', at)
        name = data[at:nl].decode('ascii')
        (n,) = struct.unpack_from('<Q', data, nl + 1)
        body = data[nl + 9:nl + 9 + 4 * n]
        if name == 'l0w':
            if n != (models.PIECE_SQUARES + pp_links()) * hidden:
                raise ValueError("not S512+PP's first layer")
            out += b'l0w\n' + struct.pack('<Q', n + count * hidden) + bytes(4 * count * hidden) + body
            done = True
        else:
            out += data[at:nl + 9 + 4 * n]
        at = nl + 9 + 4 * n
    if not done:
        raise ValueError('no l0w record')
    return bytes(out)


def toward_zero(rows, seed):
    """i16 rows (bytes) with each weight moved a seeded step of 0 to 8 toward
    zero, never past it: no magnitude grows, so no bound of the reader breaks."""
    import array
    import random
    rng = random.Random(seed)
    w = array.array('h', rows)
    if sys.byteorder != 'little':
        w.byteswap()
    for i, x in enumerate(w):
        step = min(abs(x), rng.randint(0, 8))
        w[i] = x - step if x > 0 else x + step
    if sys.byteorder != 'little':
        w.byteswap()
    return w.tobytes()


def regioned_net(data, regions=models.XGR_REGIONS, perturb=None, hidden=512):
    """An S512+PP net file (architecture 8) as H512+PP's (architecture 9):
    every region's piece rows the source's (with `perturb`, the regions after
    the first moved toward zero, each by its own seed), then the source's
    links, biases and output layer; its phase table and scale kept."""
    h = netformat.header_fields(data)
    links = pp_links()
    if (h['version'], h['architecture'], h['inputs'], h['hidden']) != (2, 8, models.PIECE_SQUARES + links, hidden):
        raise ValueError(f'not an S512+PP net file: {h}')
    payload = data[netformat.HEADER_BYTES:]
    block, rest = payload[:models.MAP_BLOCK], payload[models.MAP_BLOCK:]
    if any(block[:32]) or any(block[57:]):
        raise ValueError("an S512+PP net's map block holds no regions and no other bytes")
    arch = models.Arch('h512pp', regions, list(block[32:57]))
    row = 2 * hidden
    pieces = rest[:models.PIECE_SQUARES * row]
    copies = [pieces if perturb is None or r == 0 else toward_zero(pieces, perturb * 1000 + r)
              for r in range(arch.region_count)]
    out = models.map_block(arch) + b''.join(copies) + rest[models.PIECE_SQUARES * row:]
    assert len(out) - models.MAP_BLOCK == len(rest) + (arch.region_count - 1) * len(pieces)
    return netformat.write_net2(arch.id, arch.saved_inputs, hidden, h['buckets'], h['scale'], out)


def exposure_weights(data, hidden=512):
    """S512+PP's weights.bin bytes as S512+PPXL's warm start: the 650
    exposure inputs (640 rows and their factoriser) put between l0w's 768
    piece inputs and its links as zeros, every other record copied byte for
    byte."""
    out, at, done = bytearray(), 0, False
    while at < len(data):
        nl = data.index(b'\n', at)
        name = data[at:nl].decode('ascii')
        (n,) = struct.unpack_from('<Q', data, nl + 1)
        body = data[nl + 9:nl + 9 + 4 * n]
        if name == 'l0w':
            if n != (models.PIECE_SQUARES + pp_links()) * hidden:
                raise ValueError("not S512+PP's first layer")
            pieces = 4 * models.PIECE_SQUARES * hidden
            out += (b'l0w\n' + struct.pack('<Q', n + EXPOSURE_INPUTS * hidden) + body[:pieces] +
                    bytes(4 * EXPOSURE_INPUTS * hidden) + body[pieces:])
            done = True
        else:
            out += data[at:nl + 9 + 4 * n]
        at = nl + 9 + 4 * n
    if not done:
        raise ValueError('no l0w record')
    return bytes(out)


# --perturb's exposure weights: seeded integers in [-PERTURB_RANGE, PERTURB_RANGE], small beside the piece rows
# (a test net's evaluations stay near its source's, so its search stays ordinary) yet enough to move the
# evaluation of a position with an exposed piece (tools/nnue/test_bakeoff.py checks that some parity positions
# change).
PERTURB_RANGE = 16


def exposure_net(data, perturb=None, hidden=512):
    """An S512+PP net file (architecture 8) as S512+PPXL's (architecture 10):
    the source's piece rows, 640 exposure rows (zero, or with `perturb` small
    seeded weights), then the source's links, biases and output layer; its map
    block, phase table and scale kept."""
    import array
    import random
    h = netformat.header_fields(data)
    links = pp_links()
    if (h['version'], h['architecture'], h['inputs'], h['hidden']) != (2, 8, models.PIECE_SQUARES + links, hidden):
        raise ValueError(f'not an S512+PP net file: {h}')
    payload = data[netformat.HEADER_BYTES:]
    block, rest = payload[:models.MAP_BLOCK], payload[models.MAP_BLOCK:]
    if any(block[:32]) or any(block[57:]):
        raise ValueError("an S512+PP net's map block holds no regions and no other bytes")
    arch = models.Arch('s512ppxl', table=list(block[32:57]))
    pieces = models.PIECE_SQUARES * 2 * hidden
    rows = array.array('h', bytes(2 * models.EXPOSURE_ROWS * hidden))
    if perturb is not None:
        rng = random.Random(perturb)
        for i in range(len(rows)):
            rows[i] = rng.randint(-PERTURB_RANGE, PERTURB_RANGE)
    if sys.byteorder != 'little':
        rows.byteswap()
    out = block + rest[:pieces] + rows.tobytes() + rest[pieces:]
    assert len(out) == len(payload) + 2 * models.EXPOSURE_ROWS * hidden
    return netformat.write_net2(arch.id, arch.saved_inputs, hidden, h['buckets'], h['scale'], out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('weights')
    ap.add_argument('out')
    ap.add_argument('--arch', default='s512x', choices=('s512x', 's512cl', 's512pp', 'h512pp', 's512ppxl'))
    ap.add_argument('--perturb', type=int, metavar='SEED',
                    help='h512pp from a net file: the regions after the first moved toward zero; s512ppxl from a '
                         'net file: small seeded exposure weights (test nets)')
    a = ap.parse_args(argv)
    if a.arch == 's512ppxl':
        source = Path(a.weights).read_bytes()
        if source[:8] == netformat.MAGIC:
            data = exposure_net(source, perturb=a.perturb)
            kind = 'net file, ' + (f'exposure rows seeded (seed {a.perturb})' if a.perturb is not None
                                   else 'exposure rows zero')
        else:
            if a.perturb is not None:
                ap.error('--perturb applies to a net file only')
            data = exposure_weights(source)
            kind = 'float weights, the exposure inputs and their factoriser zero'
        Path(a.out).write_bytes(data)
        print(f'{a.out}: {len(data)} bytes, S512+PPXL ({kind})')
        return 0
    if a.arch == 'h512pp':
        source = Path(a.weights).read_bytes()
        if source[:8] == netformat.MAGIC:
            data = regioned_net(source, perturb=a.perturb)
            kind = 'net file, every region the source\'s piece rows' + (
                f' (regions 1-3 perturbed, seed {a.perturb})' if a.perturb is not None else '')
        else:
            if a.perturb is not None:
                ap.error('--perturb applies to a net file only')
            data = regioned_weights(source)
            kind = 'float weights, regions zero, the factoriser the source\'s piece rows'
        Path(a.out).write_bytes(data)
        print(f'{a.out}: {len(data)} bytes, H512+PP ({kind})')
        return 0
    if a.perturb is not None:
        ap.error('--perturb applies to --arch h512pp and s512ppxl only')
    if a.arch == 's512cl':
        data = append_l0w_inputs(Path(a.weights).read_bytes(), contact_inputs())
        Path(a.out).write_bytes(data)
        print(f'{a.out}: {len(data)} bytes, {contact_inputs()} contact and link inputs appended to l0w')
        return 0
    if a.arch == 's512pp':
        links = contacts.link_count(contacts.S512PP_RANKS)
        data = append_l0w_inputs(Path(a.weights).read_bytes(), links)
        Path(a.out).write_bytes(data)
        print(f'{a.out}: {len(data)} bytes, {links} link inputs appended to l0w')
        return 0
    w = netformat.read_weights_bin(Path(a.weights).read_bytes())
    data = netformat.write_weights_bin(add_exposure_inputs(w))
    Path(a.out).write_bytes(data)
    print(f'{a.out}: {len(data)} bytes, l0w {len(w["l0w"])} -> {len(w["l0w"]) + EXPOSURE_INPUTS * 512} values')
    return 0


if __name__ == '__main__':
    sys.exit(main())
