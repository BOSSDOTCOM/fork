# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/datagen/upload_batch.py's seal step (DESIGN.md §5.3,
deliverable 3), on a fake run with made-up shard contents.

    .venv/Scripts/python.exe -I -B -m unittest discover -s tools/datagen -p 'test_*.py'
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import upload_batch as ub  # noqa: E402


class SealTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.dir.name)
        self.shards = []
        for i in range(53):
            name = f'r-w{i % 10:02d}-{i // 10:04d}.vf'
            data = bytes([i]) * (100 + i)
            (self.tmp / name).write_bytes(data)
            self.shards.append({'file': name, 'worker': i % 10, 'games': 2, 'positions': 7, 'bytes': len(data)})
        run = {'tool': 'fork_datagen', 'version': 'v', 'evaluator': 'bootstrap', 'arch': 'x86-64-v3',
               'settings': {'nodes': 1}, 'games': 106, 'positions': 371, 'seconds': 1.0,
               'results': {}, 'ends': {}, 'shards': self.shards}
        (self.tmp / 'r.json').write_text(json.dumps(run))
        om = {'output': 'o.epd', 'output_sha256': 'aa', 'positions': 3, 'source': 's.pgn.zst', 'source_sha256': 'bb'}
        (self.tmp / 'o.json').write_text(json.dumps(om))

    def tearDown(self):
        self.dir.cleanup()

    def seal(self, part_end='target reached'):
        return ub.seal(self.tmp / 'r.json', self.tmp / 'o.json', self.tmp / 'm', part_end)

    def set_evaluator(self, evaluator):
        run = json.loads((self.tmp / 'r.json').read_text())
        run['evaluator'] = evaluator
        (self.tmp / 'r.json').write_text(json.dumps(run))

    def test_hashes_batches_and_no_paths(self):
        out = self.seal()
        sealed = json.loads(out.read_text())
        self.assertEqual([len(b) for b in sealed['batches']], [50, 3])
        flat = [s for b in sealed['batches'] for s in b]
        self.assertEqual(len(flat), 53)
        for s in flat:
            self.assertEqual(s['sha256'], hashlib.sha256((self.tmp / s['file']).read_bytes()).hexdigest())
        self.assertNotIn(str(self.tmp), out.read_text())

    def test_size_mismatch_stops(self):
        (self.tmp / self.shards[0]['file']).write_bytes(b'x')
        with self.assertRaises(SystemExit):
            self.seal()

    def test_counts_must_add_up(self):
        run = json.loads((self.tmp / 'r.json').read_text())
        run['positions'] += 1
        (self.tmp / 'r.json').write_text(json.dumps(run))
        with self.assertRaises(SystemExit):
            self.seal()

    # The labeller policy (DESIGN.md §5.3, deliverable 2): every part
    # records its labelling network, its openings and why it ended.
    def test_records_why_the_part_ended(self):
        sealed = json.loads(self.seal('a new labelling net: B0r3 promoted').read_text())
        self.assertEqual(sealed['part_end'], 'a new labelling net: B0r3 promoted')
        self.assertEqual(sealed['openings']['file'], 'o.epd')

    def test_a_reason_is_required(self):
        for reason in ('', '   '):
            with self.assertRaises(SystemExit):
                self.seal(reason)

    def test_a_network_run_must_name_its_net(self):
        self.set_evaluator('nnue')
        with self.assertRaises(SystemExit):
            self.seal()
        self.set_evaluator('nnue (b0r2)')
        sealed = json.loads(self.seal().read_text())
        self.assertEqual(sealed['generator']['evaluator'], 'nnue (b0r2)')

    def test_cli_requires_the_reason(self):
        with self.assertRaises(SystemExit):
            ub.main(['seal', str(self.tmp / 'r.json'), '--openings-manifest', str(self.tmp / 'o.json'),
                     '--out', str(self.tmp / 'm')])
        ub.main(['seal', str(self.tmp / 'r.json'), '--openings-manifest', str(self.tmp / 'o.json'),
                 '--out', str(self.tmp / 'm'), '--part-end', 'stopped by the owner'])
        self.assertEqual(json.loads((self.tmp / 'm' / 'r.json').read_text())['part_end'], 'stopped by the owner')


if __name__ == '__main__':
    unittest.main()
