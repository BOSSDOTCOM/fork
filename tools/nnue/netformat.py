# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared readers and writers for the NNUE tools (DESIGN.md §5.3,
deliverables 4-6): Fork's net file (src/eval/nnue/net_file.hpp), bullet's
quantised.bin and optimiser_state/weights.bin (KB bullet-internals.md §1-2),
and B0's tensor description (tools/nnue/b0.json). Written from those
specifications, not from Fork's C++.
"""
import json
import struct
from pathlib import Path

MASK64 = (1 << 64) - 1
MAGIC = b'FORKNET\0'
HEADER_BYTES = 64
TYPES = {'i16': ('h', 2, -32768, 32767), 'i32': ('i', 4, -2**31, 2**31 - 1)}  # struct codes


def splitmix_finalize(z):
    """src/core/splitmix.hpp's output function (Vigna's splitmix64
    reference, https://prng.di.unimi.it/splitmix64.c, as cited there)."""
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return z ^ (z >> 31)


def net_checksum(payload):
    h = len(payload)
    for i in range(0, len(payload), 8):
        word = int.from_bytes(payload[i:i + 8].ljust(8, b'\0'), 'little')
        h = splitmix_finalize(h ^ word)
    return h


def layout(path=None):
    return json.loads(Path(path or Path(__file__).with_name('b0.json')).read_text())


def read_quantised(data, desc):
    """bullet's quantised.bin as {name: list of ints}, checking its size and
    the cyclic "bullet" padding to a multiple of 64 bytes."""
    tensors, at = {}, 0
    for t in desc['quantised']:
        fmt, size, _, _ = TYPES[t['type']]
        n = t['rows'] * t['cols']
        if at + n * size > len(data):
            raise ValueError(f"quantised file too short for {t['name']}")
        tensors[t['name']] = list(struct.unpack_from(f'<{n}{fmt}', data, at))
        at += n * size
    pad = data[at:]
    if len(data) % 64 != 0 or len(pad) >= 64:
        raise ValueError(f'quantised file of {len(data)} bytes: wrong size for {at} bytes of tensors')
    # The cycle starts at the first padding byte (seen in a file bullet wrote,
    # 2026-10-28: four tensor bytes, then "bulletbullet...").
    expected = bytes(b'bullet'[i % 6] for i in range(len(pad)))
    if pad != expected:
        raise ValueError('quantised file padding is not the cyclic "bullet" pattern')
    return tensors


def read_weights_bin(data):
    """bullet's optimiser_state/weights.bin as {name: list of floats}
    (records: ASCII name, 0x0A, u64 count, that many f32)."""
    out, at = {}, 0
    while at < len(data):
        nl = data.index(b'\n', at)
        name = data[at:nl].decode('ascii')
        (count,) = struct.unpack_from('<Q', data, nl + 1)
        start = nl + 9
        out[name] = list(struct.unpack_from(f'<{count}f', data, start))
        at = start + 4 * count
    return out


def write_weights_bin(weights):
    """weights.bin bytes in bullet's layout (records sorted by name), for
    synthetic tests."""
    out = b''
    for name in sorted(weights):
        v = weights[name]
        out += name.encode('ascii') + b'\n' + struct.pack('<Q', len(v)) + struct.pack(f'<{len(v)}f', *v)
    return out


def write_quantised(tensors, desc):
    """quantised.bin bytes in bullet's layout (tensors in save order, padded
    to 64 bytes with the cyclic "bullet" bytes), for synthetic tests."""
    out = b''
    for t in desc['quantised']:
        fmt = TYPES[t['type']][0]
        out += struct.pack(f'<{len(tensors[t["name"]])}{fmt}', *tensors[t['name']])
    pad = (-len(out)) % 64
    return out + bytes(b'bullet'[i % 6] for i in range(pad))


def fork_payload(tensors, desc):
    """Fork's payload (net_file.hpp) from B0's quantized tensors: feature
    weights feature-major, feature biases, output weights (side to move's
    half first), output bias."""
    h, n_in = desc['hidden'], desc['inputs']
    l0w, l0b, l1w, l1b = (tensors[k] for k in ('l0w', 'l0b', 'l1w', 'l1b'))
    assert len(l0w) == h * n_in and len(l0b) == h and len(l1w) == 2 * h and len(l1b) == 1
    # Column-major h x n_in: input f's h weights are l0w[f*h : (f+1)*h],
    # exactly Fork's feature-major order.
    return struct.pack(f'<{h * n_in}h', *l0w) + struct.pack(f'<{h}h', *l0b) + \
        struct.pack(f'<{2 * h}h', *l1w) + struct.pack('<i', l1b[0])


def write_net(payload, desc, scale):
    header = MAGIC + struct.pack('<IIIIiiiI', 1, desc['architecture'], desc['inputs'], desc['hidden'],
                                 desc['qa'], desc['qb'], scale, 0)
    header += struct.pack('<Q', net_checksum(payload))
    header = header.ljust(HEADER_BYTES, b'\0')
    return header + payload


def read_net(data, desc):
    """Fork's net file as (scale, l0w feature-major, l0b, l1w, l1b),
    checking the header against the description and the checksum."""
    if data[:8] != MAGIC:
        raise ValueError('not a Fork net file')
    version, arch, n_in, h, qa, qb, scale, zero = struct.unpack_from('<IIIIiiiI', data, 8)
    (checksum,) = struct.unpack_from('<Q', data, 40)
    if (version, arch, n_in, h, qa, qb, zero) != (1, desc['architecture'], desc['inputs'], desc['hidden'],
                                                desc['qa'], desc['qb'], 0):
        raise ValueError('net file header does not match the description')
    payload = data[HEADER_BYTES:]
    if net_checksum(payload) != checksum:
        raise ValueError('net file checksum mismatch')
    l0w = struct.unpack_from(f'<{h * n_in}h', payload, 0)
    at = 2 * h * n_in
    l0b = struct.unpack_from(f'<{h}h', payload, at)
    l1w = struct.unpack_from(f'<{2 * h}h', payload, at + 2 * h)
    (l1b,) = struct.unpack_from('<i', payload, at + 6 * h)
    if len(payload) != at + 6 * h + 4:
        raise ValueError('net file size does not match the description')
    return scale, l0w, l0b, l1w, l1b
