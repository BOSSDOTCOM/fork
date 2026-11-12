# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of overlap_audit.py's input preparation and summary (the streaming tool is checked by its own run)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import overlap_audit  # noqa: E402


class FensTest(unittest.TestCase):
    def test_tsv_and_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            tsv = Path(d, 'a.tsv')
            tsv.write_text('# class\twdl (Syzygy)\tfen  -- comment\nKQvKR\t2\t8/8/8/8/8/8/8/K1k5 w - - 0 1\n')
            out = Path(d, 'a.fens')
            overlap_audit.main(['fens', str(tsv), '--out', str(out)])
            self.assertEqual(out.read_text(), '8/8/8/8/8/8/8/K1k5 w - - 0 1\n')
            jl = Path(d, 'b.jsonl')
            jl.write_text(json.dumps({'id': 0, 'fen': 'x w - - 0 1'}) + '\n')
            overlap_audit.main(['fens', str(jl), '--out', str(out)])
            self.assertEqual(out.read_text(), 'x w - - 0 1\n')


class SummaryTest(unittest.TestCase):
    def test_masks_select_groups(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'r')
            Path(p + '-groups.tsv').write_text('bit\tgroup\n0\ts2\n1\tg4b\n')
            Path(p + '-files.tsv').write_text(
                'group\tpath\tskip\tgames\tpositions\tsaved\tkept\thits_k1\thits_k0\thits_k1_kept\t'
                'identical_games\tsame_start_games\ttruncated\terror\n'
                's2\tx/a.vf\t0\t1\t3\t2\t1\t1\t1\t0\t0\t0\t0\t\n')
            head = 'set\titem\tply\tpieces\tkept\tk1_count\tk1_kept_count\tk1_mask\tk1_kept_mask\tk0_count\tk0_mask\tfen4\n'
            rows = ['v\t0\t0\t32\t1\t5\t0\t1\t0\t5\t1\tA', 'v\t0\t1\t32\t1\t0\t0\t2\t0\t0\t2\tB',
                    'v\t0\t2\t31\t0\t0\t0\t0\t0\t0\t0\tC']
            Path(p + '-queries.tsv').write_text(head + '\n'.join(rows) + '\n')
            Path(p + '-games.tsv').write_text(
                'set\titem\tplies\tidentical_count\tidentical_mask\tstart_count\tstart_mask\tstart_fen4\nv\t0\t3\t0\t0\t5\t1\tA\n')
            Path(d, 'pairs.json').write_text(json.dumps([{'name': 'n', 'queries': ['v'], 'groups': ['s2']}]))
            out = Path(d, 's.json')
            overlap_audit.main(['summary', p, '--pairs', str(Path(d, 'pairs.json')), '--json', str(out)])
            r = json.loads(out.read_text())['pairs'][0]
            self.assertEqual((r['all']['positions'], r['all']['k1_in_train']), (3, 1))   # B's hit is in g4b only
            self.assertEqual((r['kept']['positions'], r['kept']['k1_in_train']), (2, 1))
            self.assertEqual(r['kept']['k1_in_train_as_kept'], 0)
            self.assertEqual((r['games']['identical_in_train'], r['games']['start_position_in_train']), (0, 1))


if __name__ == '__main__':
    unittest.main()
