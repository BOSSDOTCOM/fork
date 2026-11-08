# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/gauntlet/report.py on a fake result set: a reference
opponent's games (Stockfish) stay out of Ordo's fit and are reported apart,
with the pentanomial interval. Ordo is replaced by a fake that records the
players of the games it was given.

    python3 -m unittest discover -s tools/gauntlet -p 'test_*.py'
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import report  # noqa: E402

TABLE = (
    '# comment\n'
    'Weiss 1.0\tweiss-1.0\t2896\tcontinuity\thttps://example.invalid/w.git\t0\tsrc\tmake\t-\t-\n'
    'Stockfish 19\tstockfish-19\t3792\treference\thttps://example.invalid/s.git\t0\tsrc\t'
    'make net; make build ARCH=x86-64-avx2\t-\toption.Threads=1 option.Hash=16\n'
)

# Ordo's stand-in: the players and game count of the PGN it is given.
ORDO = '''
import sys
a = sys.argv[1:]
pgn = open(a[a.index('-p') + 1], encoding='utf-8').read()
names = sorted({l.split('"')[1] for l in pgn.splitlines() if l.startswith(('[White ', '[Black '))})
games = pgn.count('[Event ')
open(a[a.index('-o') + 1], 'w', encoding='utf-8').write(f'fake ordo: {games} games; players: {", ".join(names)}\\n')
'''


def game(rnd, white, black, result):
    return (f'[Event "Fastchess Tournament"]\n[Round "{rnd}"]\n[White "{white}"]\n[Black "{black}"]\n'
            f'[Result "{result}"]\n\n1. e4 e5 {result}\n\n')


def shard(root, folder, name, ccrl, start, games):
    d = Path(root) / folder
    d.mkdir()
    (d / 'games.pgn').write_text(''.join(game(*g) for g in games), encoding='utf-8')
    (d / 'anchor.csv').write_text(f'"{name}",{ccrl}\n', encoding='utf-8')
    (d / 'shard.txt').write_text(f'cpu=test anchor={name} ccrl={ccrl} start={start}\nplayed={len(games)} of 4\n',
                                 encoding='utf-8')


class ReportTests(unittest.TestCase):
    def test_reference_kept_out_of_fit(self):
        sf = 'Stockfish 19'
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / 'shards').mkdir()
            (t / 'out').mkdir()
            (t / 'anchors.tsv').write_text(TABLE, encoding='utf-8')
            (t / 'ordo.py').write_text(ORDO, encoding='utf-8')
            shard(t / 'shards', 'games-weiss-1.0-1', 'Weiss 1.0', 2896, 1, [
                (1, 'Fork', 'Weiss 1.0', '1-0'), (1, 'Weiss 1.0', 'Fork', '0-1'),
                (2, 'Fork', 'Weiss 1.0', '1/2-1/2'), (2, 'Weiss 1.0', 'Fork', '0-1')])
            # Fork's game pairs: 0 + 1/2 (pair score 1/2), 0 + 0 (0); then in
            # the second shard, whose rounds count from 1 again: 1/2 + 1/2
            # (1), 0 + 0 (0). 1.5 points of 8, Ptnml(0-2) [2, 1, 1, 0, 0].
            shard(t / 'shards', 'games-stockfish-19-1', sf, 3792, 1, [
                (1, 'Fork', sf, '0-1'), (1, sf, 'Fork', '1/2-1/2'),
                (2, sf, 'Fork', '1-0'), (2, 'Fork', sf, '0-1')])
            shard(t / 'shards', 'games-stockfish-19-51', sf, 3792, 51, [
                (1, sf, 'Fork', '1/2-1/2'), (1, 'Fork', sf, '1/2-1/2'),
                (2, 'Fork', sf, '0-1'), (2, sf, 'Fork', '1-0')])
            with contextlib.redirect_stdout(io.StringIO()):
                status = report.main([str(t / 'shards'), str(t / 'anchors.tsv'), str(t / 'out'),
                                      sys.executable, '-I', str(t / 'ordo.py')])
            self.assertEqual(status, 0)
            out = t / 'out'
            # The fit: Weiss's games and rating only.
            self.assertEqual((out / 'anchors.csv').read_text(encoding='utf-8'), '"Weiss 1.0",2896\n')
            self.assertEqual((out / 'ordo.txt').read_text(encoding='utf-8'),
                             'fake ordo: 4 games; players: Fork, Weiss 1.0\n')
            self.assertNotIn(sf, (out / 'gauntlet.pgn').read_text(encoding='utf-8'))
            # Stockfish's games kept apart, all 8.
            self.assertEqual((out / 'reference.pgn').read_text(encoding='utf-8').count('[Event '), 8)
            summary = (out / 'summary.md').read_text(encoding='utf-8')
            self.assertIn('### Gauntlet: 4 games', summary)
            # Score 1.5/8 = 0.1875: Elo -400 log10(1/0.1875 - 1) = -254.7; pair
            # scores over 2 have variance 0.04296875 over 4 pairs, so the 95%
            # interval of the mean is 0.1875 -/+ 1.96 sqrt(0.04296875 / 4):
            # below 0 (-inf) to 0.3906 (Elo -77.2).
            line = next(x for x in summary.splitlines() if x.startswith(f'- {sf}'))
            for part in ('CCRL Blitz 3792', '1.5/8', '+0 =3 -5', 'Elo -254.7', '-inf to -77.2', '[2, 1, 1, 0, 0]'):
                self.assertIn(part, line)
            self.assertLess(summary.index('### Gauntlet'), summary.index(f'- {sf}'))
            self.assertEqual(summary.count('cpu=test'), 3)


if __name__ == '__main__':
    unittest.main()
