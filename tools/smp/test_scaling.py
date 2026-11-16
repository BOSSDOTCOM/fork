# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/smp/scaling.py with a fake UCI engine (no real search).

  python3 -I -B -m unittest discover -s tools/smp -p 'test_*.py'
"""

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scaling  # noqa: E402

# Answers uci, isready, setoption, position and go depth D: at Threads N it
# reports 1000 * N nodes in 400 / N ms per position (so nps grows N^2), and
# above MAX threads it says, as Fork does, that fewer threads run.
FAKE = textwrap.dedent('''
    import sys
    MAX = 4
    threads = 1
    for line in sys.stdin:
        w = line.split()
        if not w:
            continue
        if w[0] == 'uci':
            print('uciok', flush=True)
        elif w[0] == 'isready':
            if threads > MAX:
                print(f'info string Threads {threads}: {MAX} search threads (one per hardware thread)')
            print('readyok', flush=True)
        elif w[0] == 'setoption' and w[2] == 'Threads':
            threads = int(w[4])
        elif w[0] == 'go':
            d = int(w[2])
            print(f'info depth {d - 1} seldepth 3 score cp 0 nodes 10 nps 1 time 1 pv a2a3')
            print(f'info depth {d} seldepth 9 score cp 5 nodes {1000 * threads} nps 1 hashfull 0 tbhits 0 '
                  f'time {400 // threads} pv e2e4 e7e5')
            print('bestmove e2e4', flush=True)
        elif w[0] == 'quit':
            break
''')


class Scaling(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = Path(self.tmp.name) / 'fake_engine.py'
        self.engine.write_text(FAKE, encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_bench_fens_are_the_46_bench_positions(self):
        fens = scaling.bench_fens()
        self.assertEqual(len(fens), 46)
        self.assertTrue(all(len(f.split()) == 6 for f in fens))

    def test_thread_counts(self):
        self.assertEqual(scaling.thread_counts('auto', 4), [1, 2, 4])
        self.assertEqual(scaling.thread_counts('auto', 3), [1, 2])
        self.assertEqual(scaling.thread_counts('auto', 1), [1])
        self.assertEqual(scaling.thread_counts('4,1,2,2', 64), [1, 2, 4])

    def test_runs_summary_and_skips(self):
        out = Path(self.tmp.name) / 'r.json'
        rc = scaling.main([str(self.engine), '--threads', '1,2,8', '--depth', '6', '--rounds', '2',
                           '--positions', '3', '--json', str(out)])
        self.assertEqual(rc, 0)
        data = json.loads(out.read_text(encoding='utf-8'))
        s = data['summary']
        self.assertEqual(sorted(s), ['1', '2'])  # 8 threads skipped: the fake runs at most 4
        self.assertEqual(len(data['skipped']), 1)
        self.assertEqual(s['1']['time_ms'], 3 * 400)
        self.assertEqual(s['2']['nodes'], 3 * 2000)
        self.assertAlmostEqual(s['2']['ttd_speedup'], 2.0)
        self.assertAlmostEqual(s['2']['nps_ratio'], 4.0)
        self.assertAlmostEqual(s['2']['node_ratio'], 2.0)
        self.assertEqual(s['2']['rounds'], 2)
        # Every round ran each thread count once, in a rotated order.
        orders = [[r['threads'] for r in data['runs'] if r['round'] == k] for k in (0, 1)]
        self.assertEqual(orders, [[1, 2, 8], [2, 8, 1]])

    def test_merge_takes_the_median_over_runners(self):
        files = []
        for k, speedup in enumerate((1.5, 1.7, 1.9)):
            f = Path(self.tmp.name) / f'm{k}.json'
            f.write_text(json.dumps({'summary': {'1': {'ttd_speedup': 1.0, 'nps_ratio': 1.0, 'node_ratio': 1.0},
                                                 '2': {'ttd_speedup': speedup, 'nps_ratio': 2.0,
                                                       'node_ratio': 1.2}}}), encoding='utf-8')
            files.append(str(f))
        text, data = scaling.merge(files)
        self.assertAlmostEqual(data['2']['ttd_speedup'], 1.7)
        self.assertEqual(data['2']['runners'], 3)
        self.assertIn('| 2 | 3 | 1.70 | 2.00 | 1.20 |', text)


if __name__ == '__main__':
    unittest.main()
