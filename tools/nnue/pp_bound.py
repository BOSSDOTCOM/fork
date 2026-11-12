# SPDX-License-Identifier: GPL-3.0-or-later
"""S512+PP's reader bound on a converted net (src/eval/nnue/net_file.cpp: per first-layer unit, |bias| + 32 x its
largest |piece weight| + 64 x its largest |link weight| <= 32,767): reports the units over it and the link
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
WEIGHTS_AT = 64 + 128  # the header, then S512+PP's map block


def bound(data):
    """(weights clamped to their units' allowances, units over the bound, clamped count, allowances)."""
    inputs, hidden = struct.unpack_from('<II', data, 16)
    if (inputs, hidden) != (PIECES + LINKS, H):
        raise ValueError(f'not an S512+PP net: {inputs} inputs, {hidden} hidden')
    w = list(struct.unpack_from(f'<{inputs * H}h', data, WEIGHTS_AT))
    b = struct.unpack_from(f'<{H}h', data, WEIGHTS_AT + 2 * inputs * H)
    over, clamped, allowances = 0, 0, []
    for j in range(H):
        piece = max(abs(w[r * H + j]) for r in range(PIECES))
        link = max(abs(w[r * H + j]) for r in range(PIECES, inputs))
        allow = (32767 - abs(b[j]) - 32 * piece) // MAX_LINKS
        allowances.append(allow)
        if link > allow:
            over += 1
        for r in range(PIECES, inputs):
            v = w[r * H + j]
            if abs(v) > allow:
                clamped += 1
                w[r * H + j] = allow if v > 0 else -allow
    return w, over, clamped, allowances


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
    print(json.dumps({'units_over': over, 'clamped': clamped, 'link_weights': LINKS * H,
                      'max_clamped': a.max_clamped}))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
