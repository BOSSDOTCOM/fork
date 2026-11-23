# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/cloud/shard_progress.py (the SPRT shards' progress records, display only).

The fixture is a real shard's output, not typed: fixtures/shard-progress-fastchess.log and
fixtures/shard-progress-result.json are fastchess.log and result.json of the artifact shard-0-0 of sprt run
43620446592 (BOSSDOTCOM/fork, 2026-11-14: Fork a71dd2d against b49d6f5 at 800,000 nodes per move, 100
games; SHA-256 e429ab3c124b789e537602e73f3c6d8b28d2ce0fb1f28d516b27cfd73bffc74b and
8144e0b52f53a447253560539cc5369670a30fa6e530f601a8792f1a7450309f). Oracles: fastchess's own final report in
that log (its Wins/Losses/Draws and Ptnml line), the shard's result.json (the merge's input), and, for every
prefix of the log (a shard part-way), a slow obvious recount written here.

    python3 -I -B -m unittest discover -s tools/cloud -p 'test_shard_progress.py'
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import shard_progress  # noqa: E402
import sprt_merge  # noqa: E402

LOG = HERE / 'fixtures' / 'shard-progress-fastchess.log'
RESULT = HERE / 'fixtures' / 'shard-progress-result.json'


def obvious_counts(text):
    """A plain recount: each 'Finished game N (W vs B): R {...}' line gives the test engine's points of game
    N; games 2k-1 and 2k (one opening, both colours) make pair k once both finished."""
    points = {}
    for line in text.split('\n'):
        if not line.startswith('Finished game '):
            continue
        head, rest = line[len('Finished game '):].split(' (', 1)
        players, rest = rest.split('): ', 1)
        white = players.split(' vs ')[0]
        result = rest.split(' ', 1)[0]
        white_points = 1.0 if result == '1-0' else 0.0 if result == '0-1' else 0.5
        points[int(head)] = white_points if white == 'test' else 1.0 - white_points
    ptnml = [0] * 5
    k = 1
    while 2 * k <= max(points, default=0):
        if 2 * k - 1 in points and 2 * k in points:
            ptnml[int(2 * (points[2 * k - 1] + points[2 * k]))] += 1
        k += 1
    wdl = {'wins': sum(1 for p in points.values() if p == 1.0),
           'draws': sum(1 for p in points.values() if p == 0.5),
           'losses': sum(1 for p in points.values() if p == 0.0)}
    return len(points), ptnml, wdl


class CountsTest(unittest.TestCase):
    def setUp(self):
        self.text = LOG.read_text(encoding='utf-8')

    def test_whole_log_matches_fastchess_report(self):
        c = shard_progress.counts(self.text)
        games = re.search(r'^Games: (\d+), Wins: (\d+), Losses: (\d+), Draws: (\d+)', self.text, re.M)
        self.assertIsNotNone(games, 'the fixture holds fastchess\'s final report')
        self.assertEqual(c['games_finished'], int(games.group(1)))
        self.assertEqual(c['wdl'], {'wins': int(games.group(2)), 'losses': int(games.group(3)),
                                    'draws': int(games.group(4))})
        report = re.search(r'^Ptnml\(0-2\): \[([0-9, ]+)\]', self.text, re.M)
        self.assertEqual(c['ptnml'], [int(x) for x in report.group(1).split(',')])

    def test_whole_log_matches_the_shards_result(self):
        c = shard_progress.counts(self.text)
        result = json.loads(RESULT.read_text(encoding='utf-8'))
        self.assertEqual(c['ptnml'], result['ptnml'])
        self.assertEqual(c['pairs_finished'], result['pairs'])
        self.assertEqual(c['games_finished'], result['finished_games'])
        self.assertEqual(c['time_losses'], result['time_losses'])
        self.assertEqual(c['abnormal'], result['abnormal'])

    def test_every_prefix_matches_a_plain_recount_and_the_merge(self):
        lines = self.text.split('\n')
        checked = 0
        for cut in range(0, len(lines) + 1, 7):
            prefix = '\n'.join(lines[:cut])
            c = shard_progress.counts(prefix)
            games, ptnml, wdl = obvious_counts(prefix)
            self.assertEqual((c['games_finished'], c['ptnml'], c['wdl']), (games, ptnml, wdl), f'cut {cut}')
            self.assertEqual(c['ptnml'], sprt_merge.snapshot(prefix)['ptnml'])  # as the merge counts them
            self.assertEqual(sum(c['ptnml']), c['pairs_finished'])
            checked += 1
        self.assertGreater(checked, 50)
        # Part-way, a game's pair partner may still be playing: a finished game outside every pair (the
        # fixture's line 18 is game 3's end, line 22 game 4's).
        partial = '\n'.join(lines[:18])
        self.assertTrue(lines[17].startswith('Finished game 3 '), lines[17])
        c = shard_progress.counts(partial)
        self.assertEqual((c['games_finished'], c['pairs_finished']), (3, 1))

    def test_record_fields(self):
        a = argparse.Namespace(
            run_id='43620446592', run_attempt='1', sprt_name='r8c-fn', stage='0', shard='3', shards='16',
            games_planned='100', base='b' * 40, test='a' * 40)
        rec = shard_progress.record(self.text, a, 'final', 4, '2026-11-14T17:20:40Z', 'done')
        self.assertEqual(rec['format'], 'fork-shard-progress/1')
        self.assertEqual((rec['run_id'], rec['stage'], rec['shard'], rec['shards']), (43620446592, 0, 3, 16))
        self.assertEqual((rec['games_planned'], rec['pairs_planned']), (100, 50))
        self.assertEqual((rec['state'], rec['shard_status'], rec['upload_seq']), ('final', 'done', 4))
        self.assertRegex(rec['updated_utc'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')


class WatchTest(unittest.TestCase):
    """The watcher against a log that grows as a shard's does, with a fake upload command (copies each
    record it is given): uploads at the start and every N games, never in the shard's folder."""

    def run_watch(self, upload, every_games=20, every_seconds=3600):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        out, prog, sent = tmp / 'out', tmp / 'progress', tmp / 'sent'
        out.mkdir()
        sent.mkdir()
        lines = LOG.read_text(encoding='utf-8').split('\n')
        log = out / 'fastchess.log'
        log.write_text('', encoding='utf-8')
        fake = tmp / 'fake_upload.py'
        fake.write_text(
            'import shutil, sys, pathlib\n'
            'd = pathlib.Path(sys.argv[1]); n = len(list(d.iterdir()))\n'
            'shutil.copy(sys.argv[3], d / f"{n:03d}-{sys.argv[2]}.json")\n', encoding='utf-8')
        cmd = upload.format(py=Path(sys.executable).as_posix(), fake=fake.as_posix(), sent=sent.as_posix())
        meta = ['--stage', '2', '--shard', '5', '--shards', '16', '--games-planned', '100', '--run-id', '7']
        watcher = subprocess.Popen(
            [sys.executable, '-B', str(HERE / 'shard_progress.py'), 'watch', '--log', str(log), '--dir', str(prog),
             '--name', 'progress-2-5', '--upload', cmd, '--every-games', str(every_games),
             '--every-seconds', str(every_seconds), '--poll', '0.05'] + meta,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 20  # the watcher's first record (the shard's start) before any game
        while not (prog / 'progress.json').exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        with open(log, 'a', encoding='utf-8', newline='\n') as f:  # the shard's games, a few lines at a time
            for i in range(0, len(lines), 20):
                f.write('\n'.join(lines[i:i + 20]) + ('\n' if i + 20 < len(lines) else ''))
                f.flush()
                time.sleep(0.1)
        time.sleep(0.5)
        log_bytes = log.read_bytes()
        (out / 'result.json').write_bytes(RESULT.read_bytes())
        before = {p.name: p.read_bytes() for p in out.iterdir()}
        subprocess.run([sys.executable, '-B', str(HERE / 'shard_progress.py'), 'finish', '--log', str(log),
                        '--dir', str(prog), '--result', str(out / 'result.json'), '--wait', '10'] + meta,
                       check=True, stdout=subprocess.DEVNULL)
        watcher.wait(timeout=20)
        output = watcher.stdout.read().decode()
        watcher.stdout.close()
        after = {p.name: p.read_bytes() for p in out.iterdir()}
        self.assertEqual(before, after, 'the shard folder is untouched')
        self.assertEqual(log.read_bytes(), log_bytes)
        records = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(sent.iterdir())]
        final = json.loads((prog / 'progress.json').read_text(encoding='utf-8'))
        return records, final, output, prog

    def test_uploads_every_n_games_and_final(self):
        records, final, output, prog = self.run_watch('{py} {fake} {sent}')
        games = [r['games_finished'] for r in records]
        self.assertEqual(games[0], 0, output)
        # The start, then every 20 games: the count depends on the machine's load, so at least one part-way.
        self.assertTrue(any(0 < g < 100 for g in games), output)
        for a, b in zip(games, games[1:]):
            self.assertGreaterEqual(b - a, 20, games)
        self.assertEqual([r['upload_seq'] for r in records], list(range(1, len(records) + 1)))
        self.assertTrue(all(r['state'] == 'running' for r in records))
        self.assertEqual((final['state'], final['shard_status'], final['games_finished']), ('final', 'done', 100))
        self.assertEqual(final['upload_seq'], len(records) + 1)
        self.assertEqual((final['stage'], final['shard'], final['run_id']), (2, 5, 7))
        self.assertEqual(final['ptnml'], json.loads(RESULT.read_text(encoding='utf-8'))['ptnml'])
        self.assertNotIn('result.json', [p.name for p in prog.iterdir()])

    def test_time_trigger(self):
        records, _, output, _ = self.run_watch('{py} {fake} {sent}', every_games=1000, every_seconds=0.3)
        self.assertGreaterEqual(len(records), 2, output)  # the start, then every 0.3 s with news
        self.assertTrue(any(0 < r['games_finished'] < 100 for r in records), output)

    def test_failed_uploads_never_stop_it(self):
        records, final, output, _ = self.run_watch('{py} -c "import sys; sys.exit(3)"')
        self.assertEqual(records, [])
        self.assertIn('upload exit 3', output)
        self.assertGreaterEqual(output.count('upload exit 3'), 2)  # the start and at least one more
        self.assertEqual(final['state'], 'final')


if __name__ == '__main__':
    unittest.main()
