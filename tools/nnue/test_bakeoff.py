# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of the bake-off architectures in tools/nnue (DESIGN.md §5.4):
models.py, convert.py, reference.py's legs and fit_maps.py, on synthetic
float weights in bullet's documented layouts (KB bullet-internals.md §1-2).
The cross-check against bullet's own files (fork-train check, and the
trained nets) runs outside these tests; here each mutation is shown to fail
the leg meant to catch it.

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
from fractions import Fraction
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))

import convert  # noqa: E402
import fit_maps  # noqa: E402
import models  # noqa: E402
import netformat  # noqa: E402
import reference  # noqa: E402

HERE = Path(__file__).resolve().parent
REGIONS = [0, 1, 2, 2, 1, 1, 2, 2] + [3] * 24
PHASE = [p * 8 // 25 for p in range(25)]
FENS = ['rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1',
        '8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1',
        'r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1']  # CPW perft suite, as tests/suite.hpp


def description(name):
    desc = json.loads((HERE / f'{name}.json').read_text(encoding='utf-8'))
    if name in ('h512', 'afs'):
        desc['regions'] = REGIONS
    if name != 'xgr512':
        desc['table'] = PHASE
    return desc


def training_inputs(arch):
    return arch.exposure_start + (models.EXPOSURE_ROWS + 10 if arch.exposure else 0)


def synthetic_weights(arch, seed):
    """f32 weights with bullet's names and shapes (as trained, factorisers
    separate), within the designs' clips, with two exact rounding ties."""
    rng = random.Random(seed)
    n, h = training_inputs(arch), arch.hidden

    def r(count, lim):
        return [models.to_f32(rng.uniform(-lim, lim)) for _ in range(count)]
    w = {'l0w': r(n * h, 0.06), 'l0b': r(h, 0.3)}
    if arch.name in ('s512', 'h512'):
        w.update(l1w=r(8 * 2 * h, 0.5), l1b=r(8, 0.2))
    elif arch.name == 'afs':
        w.update(l1w=r(128 * h, 0.5), l1b=r(128, 0.3), l2w=r(256 * 16, 0.6), l2b=r(256, 0.3),
                 l3w=r(8 * 32, 0.6), l3b=r(8, 0.2))
    else:
        w.update(s0w=r(3 * n, 0.05), s0b=r(3, 0.2), oaw=r(2 * h, 0.5), oab=r(1, 0.2), obw=r(2 * h, 0.5),
                 obb=r(1, 0.2))
    w['l0b'][0] = 0.5   # 0.5 x 255 = 127.5: a tie at QA
    w['l0b'][1] = -1.5  # -382.5: a negative tie
    return w


def bullet_files(arch, desc, w):
    """quantised.bin as bullet writes it for these weights (its documented
    rule: f64 product, half away from zero), and weights.bin."""
    saved = models.saved_tensors(arch, w)
    q = {t['name']: saved[t['name']][1] for t in desc['quantised']}
    return netformat.write_weights_bin(w), netformat.write_quantised(q, desc)


class Bakeoff(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def legs(self, name, w=None, mutate=None, convert_with=None):
        """Writes the files, converts, runs the legs; returns (rc, stats)."""
        desc = description(name)
        arch = reference.arch_of(desc)
        w = w or synthetic_weights(arch, 5)
        wbin, qbin = bullet_files(arch, desc, w)
        layout = self.tmp / f'{name}.json'
        layout.write_text(json.dumps(desc), encoding='utf-8')
        net = (convert_with or convert.convert)(qbin, desc, 107)
        if mutate:
            wbin, qbin, net = mutate(wbin, qbin, net)
        paths = {}
        for key, data in (('weights', wbin), ('quantised', qbin), ('net', net)):
            paths[key] = self.tmp / key
            paths[key].write_bytes(data)
        epd = self.tmp / 'p.epd'
        epd.write_text('\n'.join(FENS) + '\n')
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = reference.main(['legs', '--net', str(paths['net']), '--weights', str(paths['weights']),
                                 '--quantised', str(paths['quantised']), '--epd', str(epd), '--layout', str(layout)])
        return rc, json.loads(out.getvalue().splitlines()[0])

    def test_every_architecture_passes_its_legs(self):
        for name in ('s512', 'h512', 'afs', 'xgr512'):
            with self.subTest(name):
                rc, stats = self.legs(name)
                self.assertEqual(rc, 0)
                self.assertEqual(stats['positions'], len(FENS))

    def test_a_corrupted_weight_fails_the_quantization_leg(self):
        def corrupt(wbin, qbin, net):
            b = bytearray(qbin)
            b[100] ^= 1
            return wbin, bytes(b), net
        self.assertEqual(self.legs('h512', mutate=corrupt)[0], 1)

    def test_a_missing_factoriser_merge_fails(self):
        def unmerged(data, desc, scale):  # a converter that forgot the factoriser
            arch = reference.arch_of(desc)
            w = netformat.read_weights_bin((self.tmp / 'w-ref').read_bytes())
            w = {k: [models.to_f32(x) for x in v] for k, v in w.items()}
            no = models.Arch(arch.name, arch.regions, arch.table)
            no.factoriser = False
            t = models.saved_tensors(arch, w)
            l0 = w['l0w'][:arch.factor_start * arch.hidden]
            t['l0w'] = ('i16', models.quantise(l0, 255, 'i16'))
            payload = models.map_block(arch) + models.pack(models.fork_tensors(arch, t, scale))
            return netformat.write_net2(arch.id, arch.saved_inputs, arch.hidden, 8, scale, payload)
        desc = description('afs')
        arch = reference.arch_of(desc)
        w = synthetic_weights(arch, 5)
        (self.tmp / 'w-ref').write_bytes(netformat.write_weights_bin(w))
        self.assertEqual(self.legs('afs', w=w, convert_with=unmerged)[0], 1)

    def test_a_transposed_output_layer_fails(self):
        def transposed(data, desc, scale):
            tensors = netformat.read_quantised(data, desc)
            l1 = tensors['l1w']  # [8][1024] read as [1024][8]
            tensors['l1w'] = [l1[c * 8 + r] for r in range(8) for c in range(1024)]
            data = netformat.write_quantised(tensors, desc)
            return convert.convert(data, desc, scale)
        self.assertEqual(self.legs('s512', convert_with=transposed)[0], 1)

    def test_truncation_instead_of_rounding_fails(self):
        def truncated(data, desc, scale):
            arch = reference.arch_of(desc)
            w = netformat.read_weights_bin((self.tmp / 'w-ref').read_bytes())
            t = models.saved_tensors(arch, w)
            t['l0b'] = ('i16', [int(255.0 * x) for x in w['l0b']])  # trunc, not round: the ties differ
            payload = models.map_block(arch) + models.pack(models.fork_tensors(arch, t, scale))
            return netformat.write_net2(arch.id, arch.saved_inputs, arch.hidden, 8, scale, payload)
        desc = description('s512')
        w = synthetic_weights(reference.arch_of(desc), 5)
        (self.tmp / 'w-ref').write_bytes(netformat.write_weights_bin(w))
        self.assertEqual(self.legs('s512', w=w, convert_with=truncated)[0], 1)

    def test_integer_and_float_passes_agree(self):
        # With moderate weights the quantization loss stays small for every
        # design (a wrong scale or shift would put it in the hundreds).
        for name in ('s512', 'h512', 'afs', 'xgr512'):
            with self.subTest(name):
                rc, stats = self.legs(name)
                self.assertLess(stats['loss_max'], 30, stats)


class Rounding(unittest.TestCase):
    def test_fractions_round_half_away_from_zero(self):
        self.assertEqual(models.round_half_away(Fraction(5, 2)), 3)
        self.assertEqual(models.round_half_away(Fraction(-5, 2)), -3)
        self.assertEqual(models.round_half_away(Fraction(7, 3)), 2)
        self.assertEqual(models.round_half_away(-1.5), -2)
        self.assertEqual(models.quantise([0.0390625], 64, 'i16'), [3])

    def test_af_scales(self):
        self.assertEqual(models.AF_S1, Fraction(8128125, 1000))
        self.assertEqual(models.AF_SQ1, Fraction(65025, 32) ** 2 / 2048)


class Features(unittest.TestCase):
    def test_mirror_and_colour_flip_give_equal_features(self):
        arch = models.Arch('xgr512')
        for fen in FENS[1:]:
            board = chess.Board(fen)
            for twin in (board.transform(chess.flip_horizontal), board.mirror()):
                twin.clear_stack()
                self.assertEqual(models.both_perspectives(arch, board), models.both_perspectives(arch, twin), fen)

    def test_exposure_rule(self):
        # A white knight attacked by a pawn (lower class) is exposed though
        # defended; a defended rook attacked by a rook is not; an undefended
        # bishop attacked by a queen is.
        board = chess.Board('4k3/8/3p4/4N3/8/1q6/2B5/4K2R w - - 0 1')
        exposed = models.exposed_squares(board)
        self.assertIn(chess.E5, exposed)
        self.assertIn(chess.C2, exposed)
        self.assertNotIn(chess.H1, exposed)


class FitMaps(unittest.TestCase):
    def test_regions_merge_to_the_threshold(self):
        kings = [0] * 32
        kings[0], kings[2], kings[3] = 40, 30, 20  # e1, g1, h1
        for c in range(4, 32):
            kings[c] = 10 if c < 8 else 0
        out = fit_maps.fit_regions(kings)
        self.assertLessEqual(max(out) + 1, 4)
        shares = [sum(k for k, r in zip(kings, out) if r == i) / sum(kings) for i in range(max(out) + 1)]
        self.assertTrue(all(s >= 0.10 for s in shares), shares)
        self.assertEqual(out[0], 0)

    def test_phase_octiles_are_monotone(self):
        hist = [1000] * 25
        table = fit_maps.fit_phase(hist)
        self.assertEqual(table, sorted(table))
        self.assertEqual((table[0], table[-1]), (0, 7))


if __name__ == '__main__':
    unittest.main()
