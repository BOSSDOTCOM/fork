# SPDX-License-Identifier: GPL-3.0-or-later
"""S512+PP's reader bound on a converted net (src/eval/nnue/net_file.cpp: per first-layer unit, |bias| + 32 x its
largest |piece weight| + 64 x its largest |link weight| <= 32,767; H512+PP's the same, the piece weights over every
region's rows, bake-off round 3's option a, architecture 9): reports the units over it and the link
weights beyond their unit's allowance; with --clamp OUT.fnet writes a copy whose link weights are clamped to
each unit's allowance (the owner's fallback, 2026-11-05: clamp at conversion, report the clamped share and the
quantization loss), its checksum rewritten.

Moved into the repository from a session scratchpad (bug review 2026-11-11, T2; owner, the same day), with
--max-clamped: exit 1 when more link weights need clamping than that (the clamp-count gate of
tools/nnue/gates.sh). The last line is the counts as JSON.

    pp_bound.py NET.fnet [--clamp OUT.fnet] [--max-clamped N]
"""
import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import netformat  # noqa: E402

PIECES, LINKS, H, MAX_LINKS = 768, 608, 512, 64
WEIGHTS_AT = 64 + 128  # the header, then the map block (S512+PP's, H512+PP's)
MAX_REGIONS = 4  # H512+PP (src/eval/nnue/net_shape.hpp, NetMaxRegions)


def bound(data):
    """(weights clamped to their units' allowances, units over the bound, clamped count, allowances)."""
    arch, inputs, hidden = struct.unpack_from('<III', data, 12)
    regions = (inputs - LINKS) // PIECES
    if hidden != H or (arch, inputs) not in ((8, PIECES + LINKS),) + tuple(
            (9, PIECES * r + LINKS) for r in range(1, MAX_REGIONS + 1)):
        raise ValueError(f'not an S512+PP or H512+PP net: architecture {arch}, {inputs} inputs, {hidden} hidden')
    pieces = PIECES * regions
    w = list(struct.unpack_from(f'<{inputs * H}h', data, WEIGHTS_AT))
    b = struct.unpack_from(f'<{H}h', data, WEIGHTS_AT + 2 * inputs * H)
    over, clamped, allowances = 0, 0, []
    for j in range(H):
        piece = max(abs(w[r * H + j]) for r in range(pieces))
        link = max(abs(w[r * H + j]) for r in range(pieces, inputs))
        allow = (32767 - abs(b[j]) - 32 * piece) // MAX_LINKS
        allowances.append(allow)
        if link > allow:
            over += 1
        if allow < 0:
            # The piece rows alone break the bound (H512+PP's region rows can grow in training): no clamp of
            # the links mends that, so the unit is left as it is and counted (piece_bound_units).
            continue
        for r in range(pieces, inputs):
            v = w[r * H + j]
            if abs(v) > allow:
                clamped += 1
                w[r * H + j] = allow if v > 0 else -allow
    return w, over, clamped, allowances


def piece_bound_units(allowances):
    """The units whose piece rows alone break the reader's bound (a negative allowance)."""
    return sum(1 for a in allowances if a < 0)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('net')
    ap.add_argument('--clamp', metavar='OUT.fnet')
    ap.add_argument('--max-clamped', type=int, metavar='N')
    a = ap.parse_args(argv)
    data = bytearray(Path(a.net).read_bytes())
    w, over, clamped, allowances = bound(data)
    print(f'units over the bound: {over} of {H}; smallest allowance {min(allowances)}, median '
          f'{sorted(allowances)[H // 2]}; link weights to clamp: {clamped} of {LINKS * H} '
          f'({100 * clamped / (LINKS * H):.4f}%)')
    if a.clamp:
        struct.pack_into(f'<{len(w)}h', data, WEIGHTS_AT, *w)
        struct.pack_into('<Q', data, 40, netformat.net_checksum(bytes(data[64:])))
        Path(a.clamp).write_bytes(bytes(data))
        print('clamped copy written')
    failed = a.max_clamped is not None and clamped > a.max_clamped
    if failed:
        print(f'FAIL {clamped} link weights to clamp, above the limit of {a.max_clamped}', file=sys.stderr)
    piece_over = piece_bound_units(allowances)
    if piece_over:
        failed = True
        print(f'FAIL {piece_over} units over the bound by their piece weights alone: no link clamp mends them',
              file=sys.stderr)
    print(json.dumps({'units_over': over, 'clamped': clamped, 'link_weights': LINKS * H,
                      'max_clamped': a.max_clamped, 'piece_bound_units': piece_over}))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
