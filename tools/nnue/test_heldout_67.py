# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of heldout_67.py (run in Fork's .venv, upstream python-chess; ChessTB itself is not needed): the committed
file holds what the docstring declares (materials, counts, quiet legal positions, no repeats) and its positions are
reproduced from the seed; the WDL reading (cursed and blessed are draws); the table-file and hash checks refuse a
wrong file; the overlap scans find a planted position; the sign test and the report's flag."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import chess

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'datagen'))
import endgame_heldout as eh  # noqa: E402
import endgame_slice as es  # noqa: E402
import heldout_67 as h  # noqa: E402
import heldout_deep as hd  # noqa: E402
import verify_games as vg  # noqa: E402

FILE = HERE / 'heldout_67.tsv'


class CommittedFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = h.read(FILE)

    def test_materials(self):
        self.assertEqual(len(h.MATERIALS), 28)
        self.assertEqual(len(set(h.MATERIALS)), 28)
        self.assertEqual(Counter(h.pieces(m) for m in h.MATERIALS), {6: 23, 7: 5})

    def test_counts_and_rules(self):
        self.assertEqual(len(self.rows), h.PER_MATERIAL * len(h.MATERIALS))
        self.assertEqual(Counter(m for _, m, _, _ in self.rows), {m: h.PER_MATERIAL for m in h.MATERIALS})
        seen = set()
        for cls, material, wdl, b in self.rows:
            self.assertEqual(cls, h.CLASS_OF[material])
            self.assertEqual(eh.board_class(b), eh.material_class(material.split('v')))
            self.assertTrue(b.is_valid())
            self.assertTrue(h.quiet(b))
            self.assertFalse(any(m.promotion for m in b.legal_moves))
            self.assertEqual((b.castling_rights, b.ep_square, b.halfmove_clock), (0, None, 0))
            self.assertIn(wdl, (-2, -1, 0, 1, 2))
            self.assertNotIn(eh.key(b), seen)
            seen.add(eh.key(b))

    def test_positions_come_from_the_seed(self):
        by = {}
        for _, material, _, b in self.rows:
            by.setdefault(material, []).append(b.fen())
        for material in h.MATERIALS:
            self.assertEqual([b.fen() for b in h.positions(material, 3)], by[material][:3], material)


class Rules(unittest.TestCase):
    def test_cursed_and_blessed_are_draws(self):
        self.assertEqual([h.verdict(w) for w in (-2, -1, 0, 1, 2)], ['lost', 'drawn', 'drawn', 'drawn', 'won'])
        self.assertEqual({k: h.verdict(v) for k, v in h.LICHESS_WDL.items()},
                         {'win': 'won', 'cursed-win': 'drawn', 'draw': 'drawn', 'blessed-loss': 'drawn',
                          'loss': 'lost'})

    def test_promotion_is_not_quiet(self):
        self.assertFalse(h.quiet(chess.Board('8/1P6/8/8/8/k7/8/K7 w - - 0 1')))
        self.assertTrue(h.quiet(chess.Board('8/1P6/8/8/8/k7/8/K7 b - - 0 1')))

    def test_table_names(self):
        files = ['KBPPKR.lzw', 'KRPKRP.lzw', 'KQPPPKQ.lzw']
        self.assertEqual(h.table_name('KRvKBPP', files), 'KBPPKR.lzw')
        self.assertEqual(h.table_name('KRPvKRP', files), 'KRPKRP.lzw')
        self.assertEqual(h.table_name('KQPPPvKQ', files), 'KQPPPKQ.lzw')
        with self.assertRaises(FileNotFoundError):
            h.table_name('KRvKNPP', files)

    def test_sign_test(self):
        self.assertEqual(h.sign_test(0, 0), 1.0)
        self.assertAlmostEqual(h.sign_test(12, 5), 0.1435, places=4)  # the T1 extension's r8brft1 vs S512ppr2
        self.assertAlmostEqual(h.sign_test(5, 1), 0.21875)
        self.assertEqual(h.sign_test(3, 9), h.sign_test(9, 3))

    def test_flag(self):
        self.assertTrue(h.flag_line('c', 116, 'r', 100)[1])
        self.assertFalse(h.flag_line('c', 115, 'r', 100)[1])

    def test_spot_sample_is_stratified(self):
        rows = h.read(FILE)
        idx = h.spot_sample(rows)
        self.assertEqual(len(set(idx)), h.SPOT)
        self.assertEqual(Counter(rows[i][0] for i in idx), {c: h.SPOT // 4 for c in h.CLASSES})
        self.assertEqual(idx, h.spot_sample(rows))


class Tables(unittest.TestCase):
    def test_size_and_hash_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / 'full/wdl').mkdir(parents=True)
            data = b'not a table'
            (t / 'full/wdl/KRKP.lzw').write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            plan, manifest = t / 'plan.tsv', t / 'manifest.jsonl'
            for size, good in ((len(data), sha), (len(data) + 1, sha), (len(data), '0' * 64)):
                plan.write_text(f'order\tgroup\tform\tpath\tbytes\txet_hash\n1\tR6\tfull/wdl\tfull/wdl/KRKP.lzw\t'
                                f'{size}\tx\n', encoding='utf-8')
                manifest.write_text(json.dumps({'path': 'full/wdl/KRKP.lzw', 'sha256': good}) + '\n',
                                    encoding='utf-8')
                rec = h.load_records(plan, manifest)
                if size == len(data) and good == sha:
                    self.assertEqual(h.checked(t, 'full/wdl/KRKP.lzw', rec, t / 'work'), t / 'full/wdl/KRKP.lzw')
                    cached = json.loads((t / 'work/verified.json').read_text(encoding='utf-8'))
                    self.assertEqual(cached['full/wdl/KRKP.lzw']['sha256'], sha)
                else:
                    (t / 'work/verified.json').unlink(missing_ok=True)
                    with self.assertRaises(RuntimeError):
                        h.checked(t, 'full/wdl/KRKP.lzw', rec, t / 'work')

    def test_probe_directory_holds_only_its_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            src = t / 'KRPKRP.lzw'
            src.write_bytes(b'x')
            try:
                d = h.link_dir(t / 'work', 'KRPvKRP', [src])
            except OSError as e:  # Windows without the symbolic-link privilege
                self.skipTest(f'no symbolic links here: {e}')
            self.assertEqual(sorted(p.name for p in (d / 'wdl').iterdir()), ['KRPKRP.lzw'])
            (d / 'wdl' / 'extra.lzw').write_bytes(b'y')
            with self.assertRaises(RuntimeError):
                h.link_dir(t / 'work', 'KRPvKRP', [src])


class Overlap(unittest.TestCase):
    def test_a_planted_position_is_found_in_a_slice_and_a_shard(self):
        rows = h.read(FILE)
        planted = rows[1234][3]
        move = next(m for m in planted.legal_moves)
        with tempfile.TemporaryDirectory() as tmp:
            sl = Path(tmp) / 'slice.vf'
            other = chess.Board('8/8/8/4k3/8/8/3QK3/8 b - - 0 1')
            sl.write_bytes(es.encode(other, next(iter(other.legal_moves)), 1, 0)
                           + es.encode(planted, move, 1, 0))
            # A two-move game through the planted position, as a self-play shard holds it.
            before = planted.copy()
            back = next(m for m in planted.legal_moves if not planted.is_capture(m))
            before.push(back)
            reply = next(m for m in before.legal_moves if not before.is_capture(m))
            start = before.copy()
            game = bytearray(es.encode(start, reply, 1, 0)[:32])
            for b0, m in ((start, reply),):
                game += vg.code_of(b0, m).to_bytes(2, 'little') + bytes(2)
            game += bytes(4)
            sh = Path(tmp) / 'shard.vf'
            sh.write_bytes(bytes(game))
            after = start.copy()
            after.push(reply)
            rows2 = rows + [('C1', 'KRPvKRP', 0, after)] if eh.key(after) not in {eh.key(r[3]) for r in rows} \
                else rows
            rep, found = h.overlap(rows2, [str(sl)], [str(sh)])
        self.assertEqual(rep['slices']['found'], 1)
        self.assertIn(eh.board_class(planted), rep['slices']['held_out_classes_in_slice'])
        self.assertEqual(rep['shards']['found'], 1 if len(rows2) > len(rows) else 0)
        self.assertEqual(hd.PIECES, range(8, 13))  # restored
        self.assertGreaterEqual(found, 2)


if __name__ == '__main__':
    unittest.main()
