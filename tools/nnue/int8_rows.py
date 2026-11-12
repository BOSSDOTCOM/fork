# SPDX-License-Identifier: GPL-3.0-or-later
"""Int8 feature-transformer rows (speed sprint 3, I4): a converted net's first layer re-quantized from bullet's
float weights so that every unit's weights (piece and link rows alike) are multiples of one per-unit multiplier m
with |w / m| <= 127. The int8 build (FORK_FT_INT8, src/eval/nnue/net_file.cpp) stores the rows as int8 and
widens them times m when it accumulates; every other build reads the file as an ordinary net and evaluates it
the same (the format is unchanged).

Per unit j: m_j = max(1, ceil(max_f |w_fj| / 127)) over the converted net's saved rows (its int16 weights, bullet's
round(f * 255) but for any weight the converter clamped), then w_fj = m_j * round_half_away(f_fj * 255 / m_j) from
the float weight f (one rounding: re-rounding the int16 weights instead rounds every exact half away from zero and
roughly doubles the quantization loss, measured on r8brft1, 2026-11-12), held to +-127 m_j (counted). For S512+PP,
a link weight over its unit's reader allowance (tools/nnue/pp_bound.py) then steps one multiple toward zero
(counted). Biases, the map block and the output layer are the converted net's. The last line is the counts as JSON.

    int8_rows.py NET.fnet weights.bin OUT.fnet --layout tools/nnue/s512pp.json
"""
import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import models  # noqa: E402
import netformat  # noqa: E402

MAP_BYTES = 128  # a version-2 file's map block, between the header and the weights
PIECES, MAX_LINKS = 768, 64  # S512+PP: the piece rows, then the links, at most 64 active (pp_bound.py)


def int8_rows(data, float_l0w, links):
    """(the rewritten file, counts) from a converted net and its float first-layer weights (saved order)."""
    fields = netformat.header_fields(data)
    inputs, h = fields['inputs'], fields['hidden']
    if fields['version'] != 2 or len(float_l0w) != inputs * h:
        raise ValueError('a version-2 net and its own float weights are needed')
    at = netformat.HEADER_BYTES + MAP_BYTES
    w16 = struct.unpack_from(f'<{inputs * h}h', data, at)
    bias = struct.unpack_from(f'<{h}h', data, at + 2 * inputs * h)
    w = list(w16)
    mults, held, stepped, changed = [], 0, 0, 0
    for j in range(h):
        m = max(1, -(-max(abs(w16[r * h + j]) for r in range(inputs)) // 127))
        mults.append(m)
        for r in range(inputs):
            q = models.round_half_away(float_l0w[r * h + j] * 255 / m)
            if abs(q) > 127:
                q, held = (127 if q > 0 else -127), held + 1
            w[r * h + j] = m * q
        if links:
            piece = max(abs(w[r * h + j]) for r in range(PIECES))
            allow = (32767 - abs(bias[j]) - 32 * piece) // MAX_LINKS
            for r in range(PIECES, inputs):
                while abs(w[r * h + j]) > allow:
                    w[r * h + j] -= m if w[r * h + j] > 0 else -m
                    stepped += 1
        changed += sum(1 for r in range(inputs) if w[r * h + j] != w16[r * h + j])
    payload = bytearray(data[netformat.HEADER_BYTES:])
    struct.pack_into(f'<{inputs * h}h', payload, MAP_BYTES, *w)
    header = bytearray(data[:netformat.HEADER_BYTES])
    struct.pack_into('<Q', header, 40, netformat.net_checksum(bytes(payload)))
    counts = {'units_per_multiplier': {str(m): mults.count(m) for m in sorted(set(mults))},
              'weights_changed': changed, 'weights': inputs * h, 'held_to_127': held, 'stepped_for_the_bound': stepped}
    return bytes(header) + bytes(payload), counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('net')
    ap.add_argument('weights')
    ap.add_argument('out')
    ap.add_argument('--layout', required=True)
    a = ap.parse_args(argv)
    desc = netformat.layout(a.layout)
    arch = models.Arch(desc['name'], desc.get('regions'), desc.get('table'))
    if arch.factoriser or arch.exposure:
        raise SystemExit('int8_rows.py: layouts with a factoriser or exposure inputs are not supported')
    l0w = [models.to_f32(x) for x in netformat.read_weights_bin(Path(a.weights).read_bytes())['l0w']]
    data, counts = int8_rows(Path(a.net).read_bytes(), l0w, desc['architecture'] == 8)
    Path(a.out).write_bytes(data)
    netformat.header_fields(data)  # the checksum, re-read
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
