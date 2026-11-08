# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/nnue (DESIGN.md §5.3, deliverables 5-6) on synthetic
bullet files written in bullet's documented layouts (KB
bullet-internals.md §1-2). The real cross-check, against bullet's own
files, runs with the first trained net; these tests pin the rounding rule
and show that each mutation fails the leg meant to catch it.

    .venv/Scripts/python.exe -I -B -m unittest discover -s tools/nnue -p 'test_*.py'
"""
import contextlib
import io
import json
import random
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))

import convert  # noqa: E402
import models  # noqa: E402
import netformat  # noqa: E402
import reference  # noqa: E402
import refiner  # noqa: E402

FENS = ['rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1',
        '8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1',
        'r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1']  # CPW perft suite, as tests/suite.hpp


def synthetic_weights(seed):
    return reference.synthetic_weights(seed)


def weights_bin(w):
    return netformat.write_weights_bin(w)


def quantised_bin(q, desc):
    return netformat.write_quantised(q, desc)


class RoundingTests(unittest.TestCase):
    def test_bullet_tie_vectors(self):
        # KB bullet-internals.md §1.4: bullet's .round() is half away from zero.
        q = reference.quantise_like_bullet
        self.assertEqual(q([1.5], 255, 'i16'), [383])
        self.assertEqual(q([-1.5], 255, 'i16'), [-383])
        self.assertEqual(q([0.5], 255, 'i16'), [128])
        self.assertEqual(q([0.0390625], 64, 'i16'), [3])
        self.assertEqual(q([-0.0390625], 64, 'i16'), [-3])
        self.assertEqual(q([0.0234375], 16320, 'i32'), [383])

    def test_out_of_range_is_an_error(self):
        with self.assertRaises(ValueError):
            reference.quantise_like_bullet([200.0], 255, 'i16')


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.dir.name)
        self.desc = netformat.layout()
        self.w = synthetic_weights(1)
        self.q = {t['name']: reference.quantise_like_bullet(self.w[t['name']], t['factor'], t['type'])
                  for t in self.desc['quantised']}
        (self.tmp / 'weights.bin').write_bytes(weights_bin(self.w))
        (self.tmp / 'quantised.bin').write_bytes(quantised_bin(self.q, self.desc))
        (self.tmp / 'p.epd').write_text('\n'.join(FENS) + '\n')

    def tearDown(self):
        self.dir.cleanup()

    def convert(self, src='quantised.bin', out='net.fnet'):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(convert.main([str(self.tmp / src), str(self.tmp / out), '--scale', '400']), 0)
        return self.tmp / out

    def legs(self, net, *extra):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = reference.main(['legs', '--net', str(net), '--weights', str(self.tmp / 'weights.bin'),
                                 '--quantised', str(self.tmp / 'quantised.bin'), '--epd', str(self.tmp / 'p.epd'),
                                 *extra])
        return rc, err.getvalue()

    def test_padding_and_size(self):
        data = (self.tmp / 'quantised.bin').read_bytes()
        self.assertEqual(len(data), 394816)  # 394,756 bytes of tensors, padded to 64 (KB §5.8)
        with self.assertRaises(ValueError):
            netformat.read_quantised(data[:-1], self.desc)
        with self.assertRaises(ValueError):
            netformat.read_quantised(data[:-1] + b'x', self.desc)

    def test_all_legs_pass_and_parity_file(self):
        net = self.convert()
        rc, err = self.legs(net, '--out', str(self.tmp / 'net.parity'))
        self.assertEqual(rc, 0, err)
        lines = (self.tmp / 'net.parity').read_text().splitlines()
        self.assertEqual(len(lines), 1 + len(FENS))

    def test_float_trainer_leg(self):
        net = self.convert()
        good = ''.join(f'{f} | {reference.r_float(self.w, reference.chess.Board(f))}\n' for f in FENS)
        (self.tmp / 't.txt').write_text(good)
        self.assertEqual(self.legs(net, '--trainer', str(self.tmp / 't.txt'))[0], 0)
        lines = good.splitlines()
        f0, v0 = lines[0].rsplit(' | ', 1)
        lines[0] = f'{f0} | {float(v0) + 0.001}'  # 0.4 cp at S = 400: beyond 0.01 cp
        (self.tmp / 't.txt').write_text('\n'.join(lines) + '\n')
        rc, err = self.legs(net, '--trainer', str(self.tmp / 't.txt'))
        self.assertEqual(rc, 1)
        self.assertIn('R-float', err)

    def test_mutations_fail_the_quantization_leg(self):
        # A corrupted weight in bullet's file.
        q = {k: list(v) for k, v in self.q.items()}
        q['l0w'][1000] += 1
        (self.tmp / 'quantised.bin').write_bytes(quantised_bin(q, self.desc))
        rc, err = self.legs(self.convert())
        self.assertEqual(rc, 1)
        self.assertIn('l0w differs', err)

    def test_transposed_tensor_fails(self):
        q = {k: list(v) for k, v in self.q.items()}
        col = q['l0w']
        q['l0w'] = [col[c * 256 + r] for r in range(256) for c in range(768)]  # row-major instead
        (self.tmp / 'quantised.bin').write_bytes(quantised_bin(q, self.desc))
        rc, err = self.legs(self.convert())
        self.assertEqual(rc, 1)
        self.assertIn('l0w differs', err)

    def test_missing_rounding_fails(self):
        q = {t['name']: [int(t['factor'] * x) for x in self.w[t['name']]] for t in self.desc['quantised']}
        (self.tmp / 'quantised.bin').write_bytes(quantised_bin(q, self.desc))
        rc, err = self.legs(self.convert())
        self.assertEqual(rc, 1)
        self.assertIn('differs', err)

    def test_loss_threshold(self):
        net = self.convert()
        self.assertEqual(self.legs(net, '--max-loss', '1000')[0], 0)
        rc, err = self.legs(net, '--max-loss', '0')
        self.assertEqual(rc, 1)
        self.assertIn('quantization loss', err)

    def test_net_checksum_and_header(self):
        net = self.convert().read_bytes()
        self.assertEqual(len(net), 64 + 394756)
        bad = bytearray(net)
        bad[100] ^= 1
        with self.assertRaises(ValueError):
            netformat.read_net(bytes(bad), self.desc)

    def test_refiner_zero_file(self):
        # The Boundary Refiner's committed zero file (ideas.md 59) is what
        # refiner.py zero writes from the default network, byte for byte, and
        # its header holds the fields refiner_file.hpp specifies.
        repo = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'zero.frnet'
            with contextlib.redirect_stdout(io.StringIO()):
                refiner.main(['zero', '--base', str(repo / 'nets/s512ppr3.fnet'), '--arch', '1', '--l1', '16',
                              '--bound', '64', '--cap', '20000', '--out', str(out)])
            data = out.read_bytes()
        self.assertEqual(data, (repo / 'tests/nnue/refiner-zero.frnet').read_bytes())
        self.assertEqual(data[:8], b'FORKRFN\0')
        version, arch, l1, l2, heads, scale, cap, bound = struct.unpack_from('<IIIIIiiI', data, 8)
        self.assertEqual((version, arch, l1, l2, heads, scale, cap, bound), (2, 1, 16, 32, 2, 89, 20000, 64))
        checksum, base = struct.unpack_from('<QQ', data, 40)
        self.assertEqual(checksum, netformat.net_checksum(data[64:]))
        self.assertEqual(base, 0x5861c1a319ca267b)  # S512ppr3's payload checksum (docs/nets.md)
        self.assertEqual(len(data) - 64, 16 * 1024 + 16 * 4 + 664 * 16 * 2 + 32 * 16 + 32 * 4 + 64 * 2 + 2 * 4)
        self.assertFalse(any(data[64:]))

    def test_refiner_rows(self):
        # Rows written out by hand from step3-plan.md 2.2. A black knight on d5 attacked by a white pawn
        # (a lower class) is exposed; nothing else is.
        repo = Path(__file__).resolve().parents[2]
        net = (repo / 'nets/s512ppr3.fnet').read_bytes()
        arch = models.arch_from_net('s512pp', net[netformat.HEADER_BYTES:])
        phase_row = 640 + arch.table[1]  # one knight: phase 1
        rows = lambda fen, base: models.refiner_rows(arch, chess.Board(fen), base, 8)  # noqa: E731
        # White to move, king on e1 (no file flip): enemy (320) + knight (64) + d5 (35).
        self.assertEqual(rows('4k3/8/8/3n4/4P3/8/8/4K3 w - - 0 1', 37), [320 + 64 + 35, phase_row, 648 + 8])
        # Black to move, king on e8: own knight, d5 seen from Black is d4 (27).
        self.assertEqual(rows('4k3/8/8/3n4/4P3/8/8/4K3 b - - 0 1', 37), [64 + 27, phase_row, 648 + 8])
        # White's king on d1: files flipped, d5 becomes e5 (36).
        self.assertEqual(rows('3k4/8/8/3n4/4P3/8/8/3K4 w - - 0 1', 37), [320 + 64 + 36, phase_row, 648 + 8])
        # The evaluation's bins: clamped to [-1,000, 999], 125 cp each.
        for base, b in ((-1500, 0), (-1000, 0), (-876, 0), (-875, 1), (0, 8), (999, 15), (2000, 15)):
            self.assertEqual(rows('4k3/8/8/3n4/4P3/8/8/4K3 w - - 0 1', base)[-1], 648 + b)

    def test_refiner_int_matches_float(self):
        # R-int against R-float on the same inputs (random bytes v and their floats v / 255) and a random
        # refiner whose weights lie on the file's grid (multiples of 1/64; biases of 1/(255 x 64)), so the
        # quantization is exact and the two differ only by the activations' rounding down (sum >> 6): each
        # byte of L1 by less than 1, so L2's by less than 1 + sum |W2| / 64 units, and the correction by
        # less than S x sum |H0| x that / (255 x 64) + 1 cp. A zero refiner gives (0, 0); the cap holds;
        # the factoriser rows are merged into the rows they share.
        repo = Path(__file__).resolve().parents[2]
        data = (repo / 'nets/s512ppr3.fnet').read_bytes()
        scale = netformat.header_fields(data)['scale']
        arch = models.arch_from_net('s512pp', data[netformat.HEADER_BYTES:])
        rng = random.Random(59)
        l1 = 8
        grid = lambda n, lo, hi, unit: [rng.randint(lo, hi) / unit for _ in range(n)]  # noqa: E731
        # Sizes that keep L1 mostly unclipped and let the rows and the factoriser matter; the confidence head
        # centred near 0.3 (300 thousandths).
        r = {'entry_weights': grid(1024 * l1, -2, 2, 64), 'entry_bias': grid(l1, 4000, 12000, 255 * 64),
             'row_weights': grid(674 * l1, -40, 40, 64), 'middle_weights': grid(l1 * 32, -16, 16, 64),
             'middle_bias': grid(32, -3000, 3000, 255 * 64), 'head_weights': grid(64, -40, 40, 64),
             'head_bias': grid(1, -1000, 1000, 255 * 64) + [4896 / (255 * 64)]}
        q = models.refiner_quantise(r)
        middle = [[r['middle_weights'][j * 32 + k] for j in range(l1)] for k in range(32)]
        head = [r['head_weights'][k * 2] for k in range(32)]
        self.assertLess(scale * sum(abs(hk) * (1 + sum(abs(x) for x in middle[k])) for k, hk in enumerate(head)) / 255 + 1,
                        15)  # the correction's check below is a tight one
        fens = ['rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1', '4k3/8/8/3n4/4P3/8/8/4K3 b - - 0 1',
                'r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4']
        changed = 0
        for fen, base in zip(fens * 4, (20, -310, 75, 999, -1000, 400, -50, 0, 1500, -600, 125, 30)):
            board = chess.Board(fen)
            v = [rng.randint(0, 255) if rng.random() < 0.7 else 0 for _ in range(1024)]
            y = models.refiner_float(arch, None, r, board, base, 8, acc=[x / 255 for x in v])
            c, conf = models.refiner_int(arch, None, scale, q, 20000, board, base, 8, acc=v)
            for o, (got, want, unit) in enumerate(((c, y[0] * scale, scale), (conf, max(0.0, min(1000.0, y[1] * 1000)), 1000))):
                head = [r['head_weights'][k * 2 + o] for k in range(32)]
                bound = unit * sum(abs(hk) * (1 + sum(abs(x) for x in middle[k])) for k, hk in enumerate(head)) / 255 + 1
                self.assertLessEqual(abs(got - want), bound, (fen, base, o))
            changed += c != 0
            capped, _ = models.refiner_int(arch, None, scale, q, 3, board, base, 8, acc=v)
            self.assertEqual(capped, max(-3, min(3, c)))
        self.assertGreater(changed, 6)
        zero = models.refiner_quantise({k: [0.0] * len(v) for k, v in r.items()})
        self.assertEqual(models.refiner_int(arch, None, scale, zero, 20000, chess.Board(fens[0]), 20, 8, acc=[255] * 1024),
                         (0, 0))
        rows = q[2][1]
        f, j = 421, 3  # an exposure row (enemy, 64 x 1 + ...) and its type row 640 + 421 // 64
        self.assertEqual(rows[f * l1 + j], models.quantise([models.to_f32(r['row_weights'][f * l1 + j]
                                                                           + r['row_weights'][(640 + f // 64) * l1 + j])],
                                                           64, 'i16')[0])
        self.assertEqual(len(rows), 664 * l1)
        # The frozen base (owner, 2026-11-08: (B)): the engine net's own first layer read as floats (int / 255,
        # each an f32), as the trainer loads it. Its clipped accumulator equals the engine's bytes / 255 up to
        # float rounding, so R-float on boards and R-int on the net agree within the same bound.
        net = models.unpack(arch, data[netformat.HEADER_BYTES:])
        base = {'l0w': [models.to_f32(x / 255) for x in net['ftw']], 'l0b': [models.to_f32(x / 255) for x in net['ftb']]}
        boards = [chess.Board(f) for f in ('r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4',
                                           '4k3/8/8/3n4/4P3/8/8/4K3 b - - 0 1',
                                           '8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1',
                                           'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1')]
        head = [r['head_weights'][k * 2] for k in range(32)]
        bound = scale * sum(abs(hk) * (1 + sum(abs(x) for x in middle[k])) for k, hk in enumerate(head)) / 255 + 1
        # The entry layer reads only the side to move's half here, so the perspectives' order shows.
        r = dict(r, entry_weights=[x * 3 if i < 512 * l1 else 0.0 for i, x in enumerate(r['entry_weights'])])
        q = models.refiner_quantise(r)
        for board in boards:
            stm, ntm, _ = models.both_perspectives(arch, board)
            unit = [models.clip(v) for v in models.column_sum(base['l0w'], 512, stm, base['l0b'])
                    + models.column_sum(base['l0w'], 512, ntm, base['l0b'])]
            floats = [v * 255 for v in unit]
            pieces = [f for f in stm if f < arch.factor_start], [f for f in ntm if f < arch.factor_start]
            a_s, a_n = (models.exposure_sum(net, arch, f, models.accumulate(net, arch, p)) for f, p in zip((stm, ntm), pieces))
            ints = [min(max(x, 0), 255) for x in a_s + a_n]
            self.assertLess(max(abs(a - b) for a, b in zip(floats, ints)), 1e-3, board.fen())
            y = models.refiner_float(arch, base, r, board, 40, 8)
            self.assertEqual(y, models.refiner_float(arch, None, r, board, 40, 8, acc=unit))  # the side to move first
            c, _ = models.refiner_int(arch, net, scale, q, 20000, board, 40, 8)
            self.assertLessEqual(abs(c - y[0] * scale), bound, board.fen())

    def test_refiner_convert_round_trip(self):
        # A trainer checkpoint's refiner tensors -> refiner.py convert -> the file: the header refiner_file.hpp
        # specifies (the base's S and payload checksum), the payload R-quant's tensors packed in file order, so
        # R-int on the file's tensors is R-int on R-quant's; a dense weight beyond the bound is refused.
        repo = Path(__file__).resolve().parents[2]
        net = repo / 'nets/s512ppr3.fnet'
        rng = random.Random(7)
        l1 = 8
        shapes = {'entry_weights': 1024 * l1, 'entry_bias': l1, 'row_weights': 674 * l1, 'middle_weights': 32 * l1,
                  'middle_bias': 32, 'head_weights': 64, 'head_bias': 2}
        r = {k: [models.to_f32(rng.uniform(-0.9, 0.9)) for _ in range(n)] for k, n in shapes.items()}
        floats = dict(r, l0w=[0.5] * 3, l0b=[0.25] * 2)  # the frozen base's tensors are in the checkpoint too
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'weights.bin').write_bytes(netformat.write_weights_bin(floats))
            args = ['convert', '--weights', str(tmp / 'weights.bin'), '--base', str(net), '--arch', '1', '--l1', '8',
                    '--bound', '64', '--cap', '300', '--out', str(tmp / 'r.frnet')]
            with contextlib.redirect_stdout(io.StringIO()):
                refiner.main(args)
            data = (tmp / 'r.frnet').read_bytes()
            bad = dict(floats, middle_weights=[1.2] + r['middle_weights'][1:])  # 76.8 at x 64
            (tmp / 'weights.bin').write_bytes(netformat.write_weights_bin(bad))
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stdout(io.StringIO()):
                    refiner.main(args)
        self.assertEqual(data[:8], b'FORKRFN\0')
        self.assertEqual(struct.unpack_from('<IIIIIiiI', data, 8), (2, 1, 8, 32, 2, 89, 300, 64))
        checksum, base = struct.unpack_from('<QQ', data, 40)
        self.assertEqual((checksum, base), (netformat.net_checksum(data[64:]), 0x5861c1a319ca267b))
        q = models.refiner_quantise(r)
        self.assertEqual(data[64:], models.pack(q))
        self.assertEqual(len(data) - 64, 1024 * 8 + 8 * 4 + 664 * 8 * 2 + 32 * 8 + 32 * 4 + 64 * 2 + 2 * 4)
        # The file's tensors read back in order give R-int the same output as R-quant's.
        at, back = 64, []
        for kind, values in q:
            size = struct.calcsize('<' + models.CODES[kind])
            back.append((kind, list(struct.unpack_from(f'<{len(values)}{models.CODES[kind]}', data, at))))
            at += size * len(values)
        arch = models.arch_from_net('s512pp', net.read_bytes()[netformat.HEADER_BYTES:])
        board = chess.Board('4k3/8/8/3n4/4P3/8/8/4K3 b - - 0 1')
        v = [rng.randint(0, 255) for _ in range(1024)]
        self.assertEqual(models.refiner_int(arch, None, 89, back, 300, board, 50, 8, acc=v),
                         models.refiner_int(arch, None, 89, q, 300, board, 50, 8, acc=v))

    def test_refiner_export(self):
        # One line per labelled site: FEN | base | label | training weight | rows, folders in order.
        repo = Path(__file__).resolve().parents[2]
        net = repo / 'nets/s512ppr3.fnet'
        arch = models.arch_from_net('s512pp', net.read_bytes()[netformat.HEADER_BYTES:])
        fens = ['4k3/8/8/3n4/4P3/8/8/4K3 w - - 0 1', '3k4/8/8/3n4/4P3/8/8/3K4 b - - 4 9', chess.STARTING_FEN]
        with tempfile.TemporaryDirectory() as tmp:
            folders = []
            for name, ids in (('a', (3, 5)), ('b', (2,))):
                d = Path(tmp) / name
                d.mkdir()
                (d / 'sites.jsonl').write_text(''.join(json.dumps({'id': i, 'fen': fens[i % 3], 'eval': 10 * i - 25})
                                                       + '\n' for i in (*ids, 8)), encoding='utf-8')
                (d / 'deep.tsv').write_text(''.join(f'{i}\t{100 + i}\t{int(i == 5)}\t17\n' for i in ids),
                                            encoding='utf-8')
                (d / 'weights.tsv').write_text(''.join(f'{i}\t{0.5 * i if i != 5 else 0:.6f}\t{9:.6f}\n' for i in ids),
                                               encoding='utf-8')
                folders.append(str(d))
            out = Path(tmp) / 'split.sites'
            with contextlib.redirect_stdout(io.StringIO()):
                refiner.main(['export', '--base', str(net), '--out', str(out), *folders])
            lines = out.read_text(encoding='utf-8').splitlines()
        expected = []
        for i in (3, 5, 2):  # site 8 has no label: left out
            rows = models.refiner_rows(arch, chess.Board(fens[i % 3]), 10 * i - 25, 8)
            weight = f'{0.5 * i if i != 5 else 0:.6f}'
            expected.append(f"{fens[i % 3]} | {10 * i - 25} | {100 + i} | {weight} | {' '.join(map(str, rows))}")
        self.assertEqual(lines, expected)


class FitScaleTests(unittest.TestCase):
    def test_recovers_a_known_scale(self):
        import math
        import fit_scale
        rng = random.Random(3)
        data = []
        for _ in range(20000):
            sc = rng.uniform(-1500, 1500)
            p = 1 / (1 + math.exp(-sc / 350))
            data.append((sc, 1.0 if rng.random() < p else 0.0))
        self.assertAlmostEqual(fit_scale.fit(data), 350, delta=25)


if __name__ == '__main__':
    unittest.main()
