# SPDX-License-Identifier: GPL-3.0-or-later

"""End-to-end test of tools/datagen/retrain_8b_inputs.py's `pre` and `post`
stages on a tiny synthetic tree (every manifest, part and folder the real
run reads, a few games each): which files are blended, TD-relabelled or left
alone, the splits, idea 52's arm, the manifests and the upload folders; a
source that does not match its manifest stops the run.

    python -I -B -m unittest discover -s tools/datagen -p 'test_retrain_8b_inputs.py'
"""
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import chess

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'measure'))
import committee_sites as cs  # noqa: E402
import retrain_8b_inputs as r8  # noqa: E402
import td_labels as td  # noqa: E402
import test_td_labels as tt  # noqa: E402

sys.path.insert(0, str(HERE.parent / 'train' / 'kaggle'))
import retrain_8b as kernel  # noqa: E402 (the training kernel's input checks)

U = tt.U
LINES = ['e2e4 e7e5 g1f3 b8c6 f1c4 g8f6', 'd2d4 d7d5 c2c4 e7e6 b1c3 g8f6', 'g1f3 d7d5 g2g3 c8g4 f1g2 e7e6',
         'c2c4 e7e5 b1c3 g8f6 g2g3 d7d5']


def shard(seed, games=12):
    """`games` short games with saved, unsaved and decided scores."""
    out = b''
    for k in range(games):
        moves = LINES[(k + seed) % 4].split()
        scores = [30 + k, U, -20 - seed, 45, U if k % 2 else 15, -60 + k]
        out += tt.encode_game(chess.STARTING_FEN, moves, scores, (k + seed) % 3)[0]
    return out


def entry(name, data):
    return {'file': name, 'games': len(list(td.split_games(data))), 'positions': 0, 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


class PipelineTests(unittest.TestCase):
    def build(self, tmp):
        kaggle, manifests = tmp / 'kaggle', tmp / 'manifests'
        manifests.mkdir()
        seed = 0
        folders = {'g2s1': 'g2s1', 'g3s1': 'g3s1', 'g3b': 'g3bcd', 'g3c': 'g3bcd', 'g3d': 'g3bcd', 'g3e': 'g3e',
                   'g3s2': 'g3s2', 'g3f': 'g3f', 'g3g': 'g3g', 'g3s3': 'g3s3', 'g3h': 'g3h', 'g3i': 'g3i',
                   'g3j': 'g3j'}
        for m, folder in folders.items():
            d = kaggle / folder
            d.mkdir(parents=True, exist_ok=True)
            names = [f'{m}-w00.vf', f'{m}-w01.vf', f'{m}-w02-val.vf']
            if m == 'g3s2':
                names += ['slice1-01.vf']
            if m == 'g3s3':
                names = ['g3s3-x-rest.vf', 'g3s3-val.vf']
            if m == 'g3j':
                names = [f'g3j-w0{k}.vf' for k in range(5)] + ['g3j-w05-val.vf']
            rows = []
            for n in names:
                seed += 1
                if n.startswith('slice'):
                    data = tt.OneMoveGameTests.KRK * 3 + tt.OneMoveGameTests.KPK_DRAW * 2
                elif n == 'g3s3-val.vf':
                    data = shard(seed, 32 * 2)  # 32 streams of 2 games
                else:
                    data = shard(seed, 70 if n.endswith('-val.vf') else 12)
                (d / n).write_bytes(data)
                rows.append(entry(n, data))
            (manifests / f'{m}.json').write_text(json.dumps({'run': m, 'batches': [rows]}), encoding='utf-8')
        # S512ppr3's float weights (any bytes: the run checks the hash it is given).
        w = kaggle / r8.INIT[0]
        w.parent.mkdir(parents=True)
        w.write_bytes(b'weights')
        # Idea 52's sites: kept positions of the g3j pool, 6 trained + 2 held + 2 controls.
        i52 = tmp / 'i52'
        i52.mkdir()
        pool = {n: list(cs.replay_records((kaggle / 'g3j' / f'{n}.vf').read_bytes())) for n in r8.I52_POOL}
        picks = [('g3j-w00', 0), ('g3j-w01', 3), ('g3j-w02', 5), ('g3j-w03', 2), ('g3j-w04', 7), ('g3j-w00', 9),
                 ('g3j-w01', 11), ('g3j-w02', 1), ('g3j-w03', 13), ('g3j-w04', 4)]
        sites = []
        for k, (n, line) in enumerate(picks):
            g, ply, uci, score, result, fen = pool[n][line]
            sites.append({'id': k, 'set': 'control' if k < 2 else 'top', 'shard': n, 'line': line, 'game': g,
                          'ply': ply, 'move': uci, 'score_white': score, 'result': result, 'fen': fen})
        (i52 / 'sites.jsonl').write_text(''.join(json.dumps(s) + '\n' for s in sites), encoding='utf-8')
        (i52 / 'labels.tsv').write_text(''.join(f'{k}\t{40 * k - 100}\t0\t9\n' for k in range(10)), encoding='utf-8')
        (i52 / 'stats.json').write_text(json.dumps({'positions_by_shard': {n: len(v) for n, v in pool.items()}}),
                                        encoding='utf-8')
        h = tmp / 'H.jsonl'
        h.write_text('{"game": "g3j-w05-val.vf#65"}\n{"game": "g3j-w05-val.vf#3"}\n', encoding='utf-8')
        return kaggle, manifests, i52, h

    def setUp(self):
        saved = (r8.INIT, r8.HOLD, r8.I52_FACTOR, r8.I52_HOLD)

        def restore():
            r8.INIT, r8.HOLD, r8.I52_FACTOR, r8.I52_HOLD = saved
        self.addCleanup(restore)

    def test_pre_and_post(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            kaggle, manifests, i52, h = self.build(tmp)
            r8.INIT = (r8.INIT[0], r8.INIT[1], hashlib.sha256(b'weights').hexdigest())
            out = tmp / 'out'
            r8.HOLD, r8.I52_FACTOR, r8.I52_HOLD = 2, 3, 2
            argv = ['pre', '--kaggle', str(kaggle), '--out', str(out), '--manifests', str(manifests), '--i52',
                    str(i52), '--exclude', str(h)]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(r8.main(argv), 0)
                self.assertEqual(r8.main(argv), 0)  # a second run finds everything done
            blend = sorted(p.name for p in (out / 'blend').glob('bl-*.vf'))
            # Every training file older than g3j, its rests too; no slice, no validation shard, no g3j.
            self.assertIn('bl-g2s1-w00.vf', blend)
            self.assertIn('bl-g3s3-x-rest.vf', blend)
            self.assertIn('bl-g4s1-g3h-w02-val-rest.vf', blend)
            self.assertFalse([n for n in blend if 'slice' in n or n.endswith('-val.vf') or n.startswith('bl-g3j')])
            self.assertEqual(len(blend), 2 * 11 + 1 + 2)
            arms = sorted(p.name for p in (out / 'arms').glob('td*.vf'))
            self.assertEqual(arms, sorted(f'td{l}-{n}' for l in ('80', '90') for n in
                                          [f'g3j-w0{k}.vf' for k in range(5)] + ['g4s1-g3j-w05-val-rest.vf']))
            # H's games 3 and 65 (past the 2 held ones) are out of g3j's rest.
            rest = (out / 'g3hij' / 'g4s1-g3j-w05-val-rest.vf').read_bytes()
            self.assertEqual(len(list(td.split_games(rest))), 70 - 2 - 2)
            # The manifests list what the upload folders hold.
            rec = json.loads((manifests / 'r8b-arms.json').read_text(encoding='utf-8'))
            listed = {s['file'] for b in rec['batches'] for s in b}
            self.assertTrue({'i52-sites.vf', 'i52-held.vf', 'i52-controls.vf', 'i52-g3j-w00.vf'} <= listed)
            self.assertTrue(rec['arm']['check']['equal_data'])
            up = out / 'up-pre'
            self.assertEqual({p.name for p in up.iterdir()},
                             {'fork-g3hij', 'fork-r8b-blend-1', 'fork-r8b-arms'})
            self.assertEqual({p.name for p in (up / 'fork-r8b-arms').iterdir()}, listed)
            self.assertIn('s512ppr3-weights.bin', {p.name for p in (up / 'fork-g3hij').iterdir()})
            # post: g4 as a sealed part.
            g4 = kaggle / 'g4'
            g4.mkdir()
            rows = []
            for k, n in enumerate(['g4-w00.vf', 'g4-w01-val.vf']):
                data = shard(50 + k, 12 if k == 0 else 8)
                (g4 / n).write_bytes(data)
                rows.append(entry(n, data))
            (tmp / 'g4.json').write_text(json.dumps({'run': 'g4', 'batches': [rows]}), encoding='utf-8')
            with redirect_stdout(io.StringIO()):
                self.assertEqual(r8.main(['post', '--kaggle', str(kaggle), '--out', str(out), '--manifests',
                                          str(manifests), '--g4-manifest', str(tmp / 'g4.json')]), 0)
            val = (out / 'g4' / 'g4s1-val.vf').read_bytes()
            self.assertEqual(len(list(td.split_games(val))), 32 * 2 + 4 * 2)
            rec = json.loads((manifests / 'r8b-g4.json').read_text(encoding='utf-8'))
            self.assertEqual({s['file'] for b in rec['batches'] for s in b},
                             {'g4s1-g4-w01-val-rest.vf', 'g4s1-val.vf', 'bl-g4s1-val.vf', 'td80-g4-w00.vf',
                              'td90-g4-w00.vf', 'td80-g4s1-g4-w01-val-rest.vf', 'td90-g4s1-g4-w01-val-rest.vf'})
            self.assertEqual({p.name for p in (out / 'up-post').iterdir()}, {'fork-g4', 'fork-r8b-g4'})
            # The kernel's input checks on what Kaggle would mount: 8a's datasets and the uploaded folders.
            shutil.copy(tmp / 'g4.json', manifests / 'g4.json')
            mounted = [str(p) for f in r8.OLD_FOLDERS for p in (kaggle / f).glob('*.vf')]
            mounted += [str(p) for stage in ('up-pre', 'up-post') for p in (out / stage).glob('*/*.vf')]
            sealed = {}
            for m in kernel.MANIFESTS:
                for b in json.loads((manifests / f'{m}.json').read_text(encoding='utf-8'))['batches']:
                    for s in b:
                        sealed[s['file']] = s['sha256']
            record, lists, _ = kernel.resolve(mounted, sealed)
            self.assertTrue(record['ok'], record)
            n = len(lists['c'])
            self.assertEqual(lists['scr'], lists['c'])
            self.assertEqual((len(lists['td80']), len(lists['td90']), len(lists['i52'])), (n, n, n + 1))
            self.assertEqual(record['slice_files'], ['slice1-01.vf'])
            self.assertIn('slice1-01.vf', lists['td80'])
            self.assertIn('td80-g4-w00.vf', lists['td80'])
            self.assertIn('bl-g3h-w00.vf', lists['td90'])
            self.assertIn('i52-g3j-w03.vf', lists['i52'])
            self.assertNotIn('g3j-w03.vf', lists['i52'])
            self.assertFalse([x for x in lists['c'] if x.endswith('-val.vf') or x.startswith(('bl-', 'td', 'i52'))])
            # A file that is not what its manifest says fails the check.
            sealed['g3e-w00.vf'] = '0' * 64
            self.assertFalse(kernel.resolve(mounted, sealed)[0]['ok'])

    def test_a_wrong_source_stops_the_run(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            kaggle, manifests, i52, h = self.build(tmp)
            (kaggle / 'g3e' / 'g3e-w00.vf').write_bytes(shard(99))
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                r8.main(['pre', '--kaggle', str(kaggle), '--out', str(tmp / 'out'), '--manifests', str(manifests),
                         '--i52', str(i52), '--exclude', str(h)])
            self.assertFalse((tmp / 'out' / 'blend').exists())


if __name__ == '__main__':
    unittest.main()
