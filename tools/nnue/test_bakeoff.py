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

import contacts  # noqa: E402
import convert  # noqa: E402
import extend_weights  # noqa: E402
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
    return arch.link_start + (contacts.link_count(arch.link_ranks) if arch.links else 0)


def synthetic_weights(arch, seed):
    """f32 weights with bullet's names and shapes (as trained, factorisers
    separate), within the designs' clips, with two exact rounding ties."""
    rng = random.Random(seed)
    n, h = training_inputs(arch), arch.hidden

    def r(count, lim):
        return [models.to_f32(rng.uniform(-lim, lim)) for _ in range(count)]
    w = {'l0w': r(n * h, 0.06), 'l0b': r(h, 0.3)}
    if arch.name in ('s512', 'h512', 's512x', 's512pp', 'h512pp'):
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
        for name in ('s512', 'h512', 'afs', 'xgr512', 's512x'):
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
        for name in ('s512', 'h512', 'afs', 'xgr512', 's512x'):
            with self.subTest(name):
                rc, stats = self.legs(name)
                self.assertLess(stats['loss_max'], 30, stats)


class ExposureAddOn(unittest.TestCase):
    """S512+X (architecture 6): S-512 plus XGR's exposure plane."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def net_of(self, name, w):
        desc = description(name)
        arch = reference.arch_of(desc)
        _, qbin = bullet_files(arch, desc, w)
        data = convert.convert(qbin, desc, 107)
        return arch, models.unpack(arch, data[netformat.HEADER_BYTES:])

    def test_zero_exposure_weights_evaluate_as_s512(self):
        # The warm start: S-512's weights with the exposure inputs appended as
        # zeros give S-512's evaluations exactly, float and integer.
        w = synthetic_weights(models.Arch('s512', table=PHASE), 7)
        wx = extend_weights.add_exposure_inputs(w)
        a, net = self.net_of('s512', w)
        ax, netx = self.net_of('s512x', wx)
        self.assertEqual(len(wx['l0w']), (768 + 650) * 512)
        for fen in FENS:
            board = chess.Board(fen)
            self.assertTrue(models.exposed_squares(board) or fen == FENS[0])
            self.assertEqual(models.r_int(ax, netx, 107, board), models.r_int(a, net, 107, board), fen)
            self.assertEqual(models.r_float(ax, wx, board), models.r_float(a, w, board), fen)

    def test_extending_keeps_every_other_tensor(self):
        w = synthetic_weights(models.Arch('s512', table=PHASE), 8)
        data = netformat.write_weights_bin(extend_weights.add_exposure_inputs(w))
        back = netformat.read_weights_bin(data)
        self.assertEqual(back['l0w'][:768 * 512], w['l0w'])
        self.assertTrue(all(x == 0.0 for x in back['l0w'][768 * 512:]))
        for k in ('l0b', 'l1w', 'l1b'):
            self.assertEqual(back[k], w[k])
        with self.assertRaises(ValueError):  # already extended
            extend_weights.add_exposure_inputs(extend_weights.add_exposure_inputs(w))

    def test_exposure_rows_change_the_evaluation(self):
        # An exposed piece's row reaches the output (a converter or reference
        # that dropped the exposure rows would give S-512's value).
        w = extend_weights.add_exposure_inputs(synthetic_weights(models.Arch('s512', table=PHASE), 9))
        a0, net0 = self.net_of('s512x', w)
        rng = random.Random(3)
        start = 768 * 512
        w['l0w'] = w['l0w'][:start] + [models.to_f32(rng.uniform(-0.3, 0.3)) for _ in range(650 * 512)]
        a1, net1 = self.net_of('s512x', w)
        board = chess.Board(FENS[1])
        self.assertTrue(models.exposed_squares(board))
        self.assertNotEqual(models.r_int(a1, net1, 107, board), models.r_int(a0, net0, 107, board))

    def test_exposure_sums_beyond_int16_are_held_to_its_range(self):
        # Exposure rows are summed without a bound (Fork: in 32 bits) and the
        # result held to the int16 range; the piece accumulator keeps its own.
        arch = models.Arch('s512x', table=PHASE)
        h = arch.hidden
        net = {'ftw': [0] * (arch.saved_inputs * h), 'ftb': [0] * h}
        rows = [768 + 0, 768 + 1, 768 + 2]
        for r in rows:
            net['ftw'][r * h] = 20000
            net['ftw'][r * h + 1] = -20000
        out = models.exposure_sum(net, arch, rows, [100] * h)
        self.assertEqual(out[:3], [32767, -32768, 100])
        out = models.exposure_sum(net, arch, rows[:1], [100] * h)
        self.assertEqual(out[:2], [20100, -19900])


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


class CombinedLayout(unittest.TestCase):
    """Links and contacts beside a piece factoriser or the exposure plane
    (bake-off round 3's options (a) and (c)): their inputs start after those
    blocks and survive the merge (they started on top of them before
    2026-11-14). The block sizes are summed here, apart from models.py."""

    COMBINATIONS = ((True, False), (False, True), (True, True))

    def combined(self, name, factoriser, exposure):
        arch = models.Arch(name, regions=REGIONS if factoriser else None, table=PHASE)
        arch.factoriser, arch.exposure = factoriser, exposure
        start = (models.PIECE_SQUARES * arch.region_count + (models.PIECE_SQUARES if factoriser else 0)
                 + (models.EXPOSURE_ROWS + 10 if exposure else 0))
        saved = models.PIECE_SQUARES * arch.region_count + (models.EXPOSURE_ROWS if exposure else 0)
        return arch, start, saved

    def test_links_and_contacts_follow_the_merged_blocks(self):
        for name in ('s512pp', 's512cl'):
            plain = models.Arch(name, table=PHASE)
            for factoriser, exposure in self.COMBINATIONS:
                arch, start, saved = self.combined(name, factoriser, exposure)
                for fen in FENS:
                    board = chess.Board(fen)
                    exposed = models.exposed_squares(board) if exposure else None
                    for persp in chess.COLORS:
                        own = [f - models.PIECE_SQUARES for f in models.features(plain, board, persp)
                               if f >= models.PIECE_SQUARES]
                        got = models.features(arch, board, persp, exposed)
                        label = f'{name} factoriser {factoriser} exposure {exposure}: {fen}'
                        self.assertEqual([f for f in got if f >= start], [start + i for i in own], label)
                        self.assertEqual(len(got), len([f for f in got if f < start]) + len(own), label)
                        # Each lands on its own row of the saved file.
                        self.assertEqual([models.merged_index(arch, start + i) for i in own],
                                         [saved + i for i in own], label)

    def test_the_merge_keeps_the_link_and_contact_columns(self):
        rows = 2
        for name in ('s512pp', 's512cl'):
            for factoriser, exposure in self.COMBINATIONS:
                arch, start, saved = self.combined(name, factoriser, exposure)
                tail = arch.saved_inputs - saved
                w = [float(i) for i in range(rows * (start + tail))]
                merged = models.merge(arch, w, rows)
                label = f'{name} factoriser {factoriser} exposure {exposure}'
                self.assertEqual(len(merged), rows * arch.saved_inputs, label)
                self.assertEqual(merged[rows * saved:], w[rows * start:], label)


class RegionedLinks(unittest.TestCase):
    """H512+PP (architecture 9, bake-off round 3's option a): S512+PP's piece
    inputs per own-king region of the map M4, H-512's factoriser, the links
    shared after the region rows; and its warm start from an S512+PP net
    (extend_weights.py), float and integer."""

    M4 = [0, 1, 1, 1] + [2] * 4 + [3] * 24  # e1 | f1-h1 | rank 2 | ranks 3-8, written out apart from models.py

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.dir.name)
        self.pp = models.Arch('s512pp', table=PHASE)
        self.kr = models.Arch('h512pp', table=PHASE)

    def tearDown(self):
        self.dir.cleanup()

    def net_of(self, arch, w, scale=107):
        """Fork's file for float weights `w` as the trainer saves them (bullet's quantised.bin, converted)."""
        desc = {'name': arch.name, 'architecture': arch.id, 'inputs': arch.saved_inputs, 'hidden': 512,
                'qa': 255, 'qb': 64, 'regions': arch.regions if arch.name == 'h512pp' else None,
                'table': arch.table,
                'quantised': [{'name': 'l0w', 'rows': 512, 'cols': arch.saved_inputs, 'type': 'i16', 'factor': 255},
                              {'name': 'l0b', 'rows': 512, 'cols': 1, 'type': 'i16', 'factor': 255},
                              {'name': 'l1w', 'rows': 8, 'cols': 1024, 'type': 'i16', 'factor': 64},
                              {'name': 'l1b', 'rows': 8, 'cols': 1, 'type': 'i32', 'factor': 16320}]}
        _, qbin = bullet_files(arch, desc, w)
        return convert.convert(qbin, desc, scale)

    def test_the_layout(self):
        self.assertEqual(self.kr.regions, self.M4)
        self.assertEqual((self.kr.id, self.kr.region_count, self.kr.factor_start, self.kr.link_start),
                         (9, 4, 3072, 3840))
        self.assertEqual(self.kr.saved_inputs, 3072 + 608)
        self.assertEqual(training_inputs(self.kr), 3840 + 608)
        desc = json.loads((HERE / 'h512pp.json').read_text(encoding='utf-8'))
        self.assertEqual((desc['architecture'], desc['inputs'], desc['regions']), (9, 3680, self.M4))
        self.assertEqual(desc['table'], json.loads((HERE / 's512pp.json').read_text(encoding='utf-8'))['table'])

    def test_features_take_the_own_kings_region_and_the_factoriser(self):
        # Kiwipete: both kings on e1 / e8 (region 0); after Kf1 White's is in
        # region 1 (f1), Black's still in region 0.
        kf1 = 'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R4K1R b kq - 1 1'
        for fen, white_region in ((FENS[1], 0), (kf1, 1)):
            board = chess.Board(fen)
            for persp in chess.COLORS:
                plain = models.features(self.pp, board, persp)
                pieces = [f for f in plain if f < 768]
                links = [f - 768 for f in plain if f >= 768]
                region = white_region if persp == chess.WHITE else 0
                want = sorted([768 * region + f for f in pieces] + [3072 + f for f in pieces] +
                              [3840 + i for i in links])
                self.assertEqual(models.features(self.kr, board, persp), want, f'{fen} {persp}')
                self.assertTrue(links, fen)

    def test_the_merge_adds_the_factoriser_to_every_region_and_keeps_the_links(self):
        rows = 2
        w = [float(i) for i in range(rows * training_inputs(self.kr))]
        merged = models.merge(self.kr, w, rows)
        self.assertEqual(len(merged), rows * 3680)
        for r in range(4):
            for f in (0, 383, 767):
                got = merged[rows * (768 * r + f):rows * (768 * r + f + 1)]
                want = [w[rows * (768 * r + f) + i] + w[rows * (3072 + f) + i] for i in range(rows)]
                self.assertEqual(got, want, (r, f))
        self.assertEqual(merged[rows * 3072:], w[rows * 3840:])

    def test_legs_pass(self):
        bake = Bakeoff('test_every_architecture_passes_its_legs')
        bake.setUp()
        try:
            self.assertEqual(description('h512pp')['regions'], self.M4)
            rc, stats = bake.legs('h512pp')
        finally:
            bake.tearDown()
        self.assertEqual(rc, 0)
        self.assertEqual(stats['positions'], len(FENS))
        self.assertLess(stats['loss_max'], 30, stats)

    def test_the_float_warm_start_evaluates_as_its_source_and_saves_its_rows_in_every_region(self):
        w = synthetic_weights(self.pp, 11)
        wk = netformat.read_weights_bin(extend_weights.regioned_weights(netformat.write_weights_bin(w)))
        self.assertEqual(len(wk['l0w']), (3840 + 608) * 512)
        self.assertTrue(all(x == 0.0 for x in wk['l0w'][:3072 * 512]))
        self.assertEqual(wk['l0w'][3072 * 512:], w['l0w'])
        for k in ('l0b', 'l1w', 'l1b'):
            self.assertEqual(wk[k], w[k])
        for fen in FENS:
            board = chess.Board(fen)
            self.assertEqual(models.r_float(self.kr, wk, board), models.r_float(self.pp, w, board), fen)
        # Saved by the trainer (each region = region + factoriser) and converted, it is the integer expansion
        # of the source's own file, byte for byte.
        self.assertEqual(self.net_of(self.kr, wk), extend_weights.regioned_net(self.net_of(self.pp, w)))
        with self.assertRaises(ValueError):  # already regioned
            extend_weights.regioned_weights(netformat.write_weights_bin(wk))

    def test_the_integer_expansion_evaluates_as_its_source(self):
        source = self.net_of(self.pp, synthetic_weights(self.pp, 12))
        out = extend_weights.regioned_net(source)
        head, src_head = netformat.header_fields(out), netformat.header_fields(source)
        self.assertEqual((head['architecture'], head['inputs'], head['scale'], head['buckets']),
                         (9, 3680, src_head['scale'], src_head['buckets']))
        self.assertEqual(len(out), 64 + 128 + 3680 * 1024 + 1024 + 8 * 1024 * 2 + 32)
        kr = models.arch_from_net('h512pp', out[64:])
        self.assertEqual((kr.regions, kr.table), (self.M4, PHASE))
        net, src = models.unpack(kr, out[64:]), models.unpack(self.pp, source[64:])
        perturbed = extend_weights.regioned_net(source, perturb=3)
        pnet = models.unpack(kr, perturbed[64:])
        first = list(src['ftw'][:768 * 512])
        self.assertEqual(list(pnet['ftw'][:768 * 512]), first)  # region 0 kept
        for r in (1, 2, 3):
            block = list(pnet['ftw'][768 * 512 * r:768 * 512 * (r + 1)])
            self.assertNotEqual(block, first, r)
            self.assertTrue(all(abs(x) <= abs(y) for x, y in zip(block, first)), r)
        differs = 0
        for fen in FENS + ['r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R4K1R b kq - 1 1']:
            board = chess.Board(fen)
            self.assertEqual(models.r_int(kr, net, 107, board), models.r_int(self.pp, src, 107, board), fen)
            differs += models.r_int(kr, pnet, 107, board) != models.r_int(self.pp, src, 107, board)
        self.assertGreater(differs, 0)  # a king off e1 / e8 reads a perturbed region
        with self.assertRaises(ValueError):
            extend_weights.regioned_net(out)  # not an S512+PP file

    def test_the_link_clamp_reads_every_regions_piece_rows(self):
        import pp_bound
        source = bytearray(self.net_of(self.pp, synthetic_weights(self.pp, 13)))
        out = bytearray(extend_weights.regioned_net(bytes(source)))
        _, over8, clamped8, allow8 = pp_bound.bound(source)
        w, over9, clamped9, allow9 = pp_bound.bound(out)
        self.assertEqual((over9, clamped9, allow9), (over8, clamped8, allow8))  # equal regions, equal bound
        at, h = pp_bound.WEIGHTS_AT, 512

        def put(row, unit, value):
            struct.pack_into('<h', out, at + 2 * (row * h + unit), value)
        # Unit 7: a region-3 piece weight of 900 leaves (32767 - |bias| - 28,800) // 64 for the links; a link
        # weight of 200 is over it and is clamped. Unit 9: a piece weight of 1,100 alone breaks the bound.
        put(768 * 3 + 50, 7, 900)
        put(3072 + 10, 7, 200)
        put(768 * 2 + 5, 9, 1100)
        w, over, clamped, allow = pp_bound.bound(out)
        self.assertEqual(allow[7], (32767 - abs(struct.unpack_from('<h', out, at + 2 * (3680 * h + 7))[0]) - 28800)
                         // 64)
        self.assertEqual(w[(3072 + 10) * h + 7], allow[7])
        self.assertLess(allow[9], 0)
        self.assertEqual(pp_bound.piece_bound_units(allow), 1)
        self.assertEqual([w[r * h + 9] for r in range(3072, 3680)],
                         [struct.unpack_from('<h', out, at + 2 * (r * h + 9))[0] for r in range(3072, 3680)])

    def test_the_committed_test_net_is_r8brft1_expanded(self):
        # nets/r8brft1kr4.fnet (CI's network job builds it; its bench is r8brft1's) is reproducible.
        nets = HERE.parent.parent / 'nets'
        self.assertEqual(extend_weights.regioned_net((nets / 'r8brft1.fnet').read_bytes()),
                         (nets / 'r8brft1kr4.fnet').read_bytes())


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
