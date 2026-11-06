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
import random
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import convert  # noqa: E402
import netformat  # noqa: E402
import reference  # noqa: E402

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
