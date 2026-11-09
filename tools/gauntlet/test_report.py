# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/gauntlet/report.py on a fake result set: a reference
opponent's games (Stockfish) stay out of Ordo's fit and are reported apart,
with the pentanomial interval. Ordo is replaced by a fake that records the
players of the games it was given. The anchor check (both levels) on
synthetic PGNs: pairing by opening, the shared anchors, a known gain
recovered, the bootstrap's reproducibility, the outcome classes, and the
default report unchanged.

    python3 -m unittest discover -s tools/gauntlet -p 'test_*.py'
"""
import contextlib
import io
import json
import math
import random
import subprocess
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
            # Without the anchor check's options the summary is exactly the one
            # report.py wrote before them (origin/phase-4 8bf1280, on this fixture).
            self.assertEqual(summary, DEFAULT_SUMMARY)


DEFAULT_SUMMARY = (
    '### Gauntlet: 4 games\n```\nfake ordo: 4 games; players: Fork, Weiss 1.0\n```\n'
    '### Gap to the reference opponents (outside the Ordo fit)\n'
    '- Stockfish 19 (CCRL Blitz 3792, for context only): Fork 1.5/8 (18.8%), +0 =3 -5; Elo -254.7, 95% interval '
    '-inf to -77.2 (pentanomial, 4 pairs, Ptnml(0-2) [2, 1, 1, 0, 0])\n'
    'Shards:\n'
    '- cpu=test anchor=Stockfish 19 ccrl=3792 start=1 played=4 of 4 \n'
    '- cpu=test anchor=Stockfish 19 ccrl=3792 start=51 played=4 of 4 \n'
    '- cpu=test anchor=Weiss 1.0 ccrl=2896 start=1 played=4 of 4 \n')

RATINGS = {'Weiss 1.0': 2896.0, 'Altair 7.0.0': 3579.0, 'Clover 6.1': 3639.0}


def pgn(games):
    """Games (anchor, opening number, Fork's colour 'w' or 'b', Fork's points) as a PGN with FEN headers."""
    out = []
    for anchor, opening, colour, p in games:
        white, black = ('Fork', anchor) if colour == 'w' else (anchor, 'Fork')
        result = {1.0: '1-0', 0.0: '0-1', 0.5: '1/2-1/2'}[p if colour == 'w' else 1.0 - p]
        out.append(f'[Event "Fastchess Tournament"]\n[White "{white}"]\n[Black "{black}"]\n[Result "{result}"]\n'
                   f'[SetUp "1"]\n[FEN "fen {opening} w - - 0 1"]\n\n1. e4 e5 {result}\n\n')
    return ''.join(out)


def pairs(anchor, scores, first=1):
    """Both colours of each opening from FIRST on: scores[i] = Fork's points (with White, with Black)."""
    return [(anchor, first + i, c, p) for i, (w, b) in enumerate(scores) for c, p in (('w', w), ('b', b))]


def logistic(r):
    return 1 / (1 + 10 ** (-r / 400))


class AnchorCheckTests(unittest.TestCase):
    def test_pairing_by_opening(self):
        # OLD played openings 1-3 against Weiss, NEW 2-4: only 2 and 3 count,
        # so opening 1's loss and opening 4's win are both left out.
        old = report.cells(pgn(pairs('Weiss 1.0', [(0.0, 0.0), (0.5, 0.5), (1.0, 0.0)])))
        new = report.cells(pgn(pairs('Weiss 1.0', [(1.0, 0.5), (0.5, 0.5), (1.0, 1.0)], first=2)))
        self.assertEqual(old['Weiss 1.0']['fen 2 w - - 0 1'], [1.0, 2])
        c = report.compare(old, new, RATINGS, resamples=50)
        self.assertEqual(c['openings'], 2)
        self.assertEqual(c['games'], (4, 4))
        self.assertEqual(c['scores']['Weiss 1.0'], ((2.0, 4), (2.5, 4)))
        # 2/4 to 2.5/4: -400 log10(1/0.625 - 1) = +88.7 Elo, against one anchor.
        self.assertAlmostEqual(c['gain'], -400 * math.log10(1 / 0.625 - 1), places=6)
        self.assertAlmostEqual(c['per_anchor']['Weiss 1.0'], c['gain'], places=6)

    def test_shared_anchors(self):
        old = report.cells(pgn(pairs('Weiss 1.0', [(1.0, 0.5)]) + pairs('Altair 7.0.0', [(0.0, 0.5)])
                               + pairs('Mystery 1', [(0.5, 0.5)])))
        new = report.cells(pgn(pairs('Weiss 1.0', [(1.0, 1.0)]) + pairs('Clover 6.1', [(0.0, 0.0)])
                               + pairs('Mystery 1', [(0.5, 1.0)]) + pairs('Altair 7.0.0', [(0.5, 0.5)], first=9)))
        c = report.compare(old, new, RATINGS, sides=('the previous run', 'this run'), resamples=10)
        self.assertEqual(c['anchors'], ['Weiss 1.0'])
        self.assertEqual(c['left'], {'Altair 7.0.0': 'no opening in common', 'Clover 6.1': 'this run only',
                                     'Mystery 1': 'not in the anchor table'})

    def test_identical_games_give_zero_in_every_resample(self):
        # Paired resampling: the same games on both sides give a gain of
        # exactly 0 in every draw (resampling the sides apart would not).
        rng = random.Random(7)
        games = [(a, i, c, rng.choice((0.0, 0.5, 1.0))) for a in ('Weiss 1.0', 'Altair 7.0.0')
                 for i in range(1, 41) for c in 'wb']
        c = report.compare(report.cells(pgn(games)), report.cells(pgn(games)), RATINGS, resamples=200)
        self.assertEqual(c['gain'], 0.0)
        self.assertEqual(set(c['draws']), {0.0})
        self.assertEqual(report.spread(c['draws']), (0.0, 0.0, 0.0))

    def test_known_gain_recovered(self):
        # Simulated games, no draws: OLD 3550 and NEW 3600 (+50) against
        # Altair (3579) and Clover (3639), 1,500 openings each with both colours.
        rng = random.Random(20261109)
        games = {}
        for side, r in (('old', 3550.0), ('new', 3600.0)):
            games[side] = [(a, i, c, float(rng.random() < logistic(r - RATINGS[a])))
                           for a in ('Altair 7.0.0', 'Clover 6.1') for i in range(1, 1501) for c in 'wb']
        c = report.compare(report.cells(pgn(games['old'])), report.cells(pgn(games['new'])), RATINGS, resamples=200)
        sd, low, high = report.spread(c['draws'])
        self.assertLess(abs(c['gain'] - 50.0), 3 * sd)
        self.assertLess(low, 50.0)
        self.assertGreater(high, 50.0)
        # The pooled fit solves sum n_a E(R - R_a) = points on each side (checked
        # here by substitution, not with the fit itself).
        for i in (0, 1):
            totals = {a: c['scores'][a][i] for a in c['anchors']}
            r = report.fit(totals, RATINGS)
            expected = sum(t[1] * logistic(r - RATINGS[a]) for a, t in totals.items())
            self.assertAlmostEqual(expected, sum(t[0] for t in totals.values()), places=6)

    def test_bootstrap_reproducible(self):
        rng = random.Random(3)
        old = report.cells(pgn([('Altair 7.0.0', i, c, rng.choice((0.0, 0.5, 1.0))) for i in range(1, 31) for c in 'wb']))
        new = report.cells(pgn([('Altair 7.0.0', i, c, rng.choice((0.0, 0.5, 1.0))) for i in range(1, 31) for c in 'wb']))
        a = report.compare(old, new, RATINGS, resamples=300)
        b = report.compare(old, new, RATINGS, resamples=300)
        self.assertEqual(a['draws'], b['draws'])
        self.assertNotEqual(a['draws'], report.compare(old, new, RATINGS, seed=report.SEED + 1, resamples=300)['draws'])
        self.assertEqual((report.SEED, report.RESAMPLES), (20261109, 4000))

    def test_outcomes(self):
        self.assertEqual(report.outcome(25.0, 10.0, 5.0, 30.0), 'confirmed')
        self.assertEqual(report.outcome(10.0, 10.0, -9.0, 30.0), 'consistent')      # 10 = 30 - 2 * 10
        self.assertEqual(report.outcome(9.9, 10.0, -9.1, 30.0), "flagged for the owner's review")
        self.assertEqual(report.outcome(-5.0, 10.0, -25.0, 10.0), 'consistent')    # -5 >= 10 - 20

    def test_level0_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            for d in ('shards', 'out', 'previous', 'baseline'):
                (t / d).mkdir()
            (t / 'anchors.tsv').write_text(TABLE, encoding='utf-8')
            (t / 'ordo.py').write_text(ORDO, encoding='utf-8')
            now = pairs('Weiss 1.0', [(1.0, 1.0), (1.0, 0.5), (0.5, 0.5), (1.0, 0.0)])
            d = t / 'shards' / 'games-weiss-1.0-1'
            d.mkdir()
            (d / 'games.pgn').write_text(pgn(now), encoding='utf-8')
            (d / 'anchor.csv').write_text('"Weiss 1.0",2896\n', encoding='utf-8')
            (d / 'shard.txt').write_text('cpu=test\n', encoding='utf-8')
            (t / 'previous' / 'gauntlet.pgn').write_text(pgn(pairs('Weiss 1.0', [(1.0, 0.0), (0.5, 0.5), (0.5, 0.5),
                                                                                 (1.0, 0.0)])), encoding='utf-8')
            (t / 'baseline.pgn').write_text(pgn(pairs('Weiss 1.0', [(0.5, 0.0), (0.5, 0.5), (0.5, 0.0), (0.0, 0.5)])),
                                            encoding='utf-8')
            (t / 'transfer.json').write_text(json.dumps({'baseline': {'run': 1, 'commit': 'abc'}, 'adopted': [
                {'change': 'X', 'elo': 100.0, 'ci95': 19.6, 'test': 't'},
                {'change': 'Y', 'elo': 50.0, 'ci95': 0.0, 'test': 't'}]}), encoding='utf-8')
            args = [str(t / 'shards'), str(t / 'anchors.tsv'), str(t / 'out'), sys.executable, '-I', str(t / 'ordo.py')]
            with contextlib.redirect_stdout(io.StringIO()):
                report.main(['--previous', str(t / 'previous'), '--baseline', str(t / 'baseline.pgn'),
                             '--adopted', str(t / 'transfer.json')] + args)
            summary = (t / 'out' / 'summary.md').read_text(encoding='utf-8')
            # Previous 4/8 to now 5.5/8; baseline 2.5/8 to 5.5/8.
            prev = -400 * math.log10(8 / 5.5 - 1) + 400 * math.log10(8 / 4 - 1)
            base = -400 * math.log10(8 / 5.5 - 1) + 400 * math.log10(8 / 2.5 - 1)
            self.assertIn(f'- On Weiss 1.0: {prev:+.1f} Elo, bootstrap SD', summary)
            self.assertIn('adopted changes sum to +150.0 +/- 19.6 Elo (95%): X +100.00; Y +50.00', summary)
            self.assertIn(f'- Transfer ratio {base / 150:.2f}, 95% interval', summary)
            self.assertIn('since the baseline gauntlet (run 1, commit abc)', summary)
            # Before the shard list; after it nothing else.
            self.assertLess(summary.index('### Anchor check: gain over'), summary.index('### Anchor check: running'))
            self.assertLess(summary.index('### Anchor check: running'), summary.index('Shards:'))
            with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
                report.main(['--baseline', str(t / 'baseline.pgn')] + args)

    def test_level1_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / 'shards').mkdir()
            (t / 'out').mkdir()
            (t / 'anchors.tsv').write_text(TABLE + 'Altair 7.0.0\taltair-7.0.0\t3579\tcontinuity\tu\t0\t.\tmake\t-\t-\n',
                                           encoding='utf-8')
            # NEW wins every game OLD drew: a large, certain gain.
            for anchor, start in (('Weiss 1.0', 1), ('Altair 7.0.0', 1), ('Altair 7.0.0', 26)):
                d = t / 'shards' / f'check-{anchor[:5]}-{start}'
                d.mkdir()
                (d / 'old.pgn').write_text(pgn(pairs(anchor, [(0.5, 0.5)] * 25, start)), encoding='utf-8')
                (d / 'new.pgn').write_text(pgn(pairs(anchor, [(1.0, 0.5)] * 25, start)), encoding='utf-8')
                (d / 'shard.txt').write_text(f'cpu=test anchor={anchor} start={start}\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(report.main(['--check', str(t / 'shards'), str(t / 'anchors.tsv'), str(t / 'out'), '30']), 0)
            summary = (t / 'out' / 'summary.md').read_text(encoding='utf-8')
            self.assertEqual((t / 'out' / 'new.pgn').read_text(encoding='utf-8').count('[Event '), 150)
            self.assertIn('300 games; claimed self-play gain +30.0 Elo', summary)
            self.assertIn('| Altair 7.0.0 | 50/100 (50.0%) | 75/100 (75.0%) | +190.8 | 0.0 | +190.8 to +190.8 |', summary)
            self.assertIn('| Pooled | 75/150 (50.0%) | 112.5/150 (75.0%) |', summary)
            self.assertIn('**Outcome: confirmed.**', summary)
            self.assertEqual(summary.count('cpu=test'), 3)

    def test_uci_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            uci = Path(tmp) / 'uci.txt'
            uci.write_text('id name X\noption name Threads type spin default 4 min 1 max 64\n'
                           'option name OwnBook type check default true\noption name Hash type spin default 16\n'
                           'option name Style type string default x\nuciok\n', encoding='utf-8')
            run = [sys.executable, '-I', str(Path(report.__file__).with_name('uci_options.py'))]
            out = subprocess.run(run + ['option.Hash=64 option.Missing=1', str(uci)], capture_output=True, text=True,
                                 check=True).stdout
            self.assertEqual(out, 'option.Hash=64 option.Threads=1 option.OwnBook=false\n')
            out = subprocess.run(run + ['-', str(uci)], capture_output=True, text=True, check=True).stdout
            self.assertEqual(out, 'option.Threads=1 option.OwnBook=false\n')


if __name__ == '__main__':
    unittest.main()
