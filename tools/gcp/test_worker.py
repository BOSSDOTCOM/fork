# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the Google Cloud worker's queue logic (tools/gcp/worker.py) with stub jobs, on Linux (WSL or the VM):

    python3 -I tools/gcp/test_worker.py
"""
import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


@unittest.skipIf(os.name == 'nt', 'the worker runs on Linux')
class WorkerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ['FORK_WORKER_ROOT'] = str(self.root)
        os.environ['FORK_JOBS'] = str(self.root / 'jobs')
        sys.path.insert(0, str(HERE))
        import worker
        self.w = importlib.reload(worker)
        self.w.jobctl.root = lambda: self.root / 'jobs'
        (self.root / 'queue').mkdir()
        (self.root / 'state' / 'items').mkdir(parents=True)

    def tearDown(self):
        for name in self.w.jobctl.root().joinpath('jobs').glob('*.json') if (self.root / 'jobs').exists() else []:
            self.w.jobctl_cmd('stop', name.stem, '--grace', '1')
        self.tmp.cleanup()

    def item(self, name, cls, script, outputs=(), **kw):
        it = {'name': name, 'class': cls, 'type': f't{cls}', 'argv': ['bash', '-c', script],
              'outputs': list(outputs), **kw}
        (self.root / 'queue' / f'{name}.json').write_text(json.dumps(it))
        return it

    def wait_end(self, name, limit=20):
        for _ in range(limit * 10):
            if not self.w.job_live(name):
                return
            time.sleep(0.1)
        self.fail(f'{name} still runs')

    def status(self):
        return json.loads((self.root / 'state' / 'worker.json').read_text())

    def test_most_urgent_first_then_done_with_outputs(self):
        out = self.root / 'out.json'
        self.item('c-fill', 'c', 'sleep 30', preemptible=True)
        self.item('a-slice', 'a', f'echo {{}} > {out}', outputs=[f'json:{out}'])
        self.w.pass_once()
        self.assertEqual(self.status()['running'], 'a-slice')
        self.wait_end('a-slice')
        self.w.pass_once()
        self.assertTrue((self.root / 'state' / 'items' / 'a-slice.done').exists())
        self.assertEqual(self.status()['running'], 'c-fill')

    def test_missing_output_fails(self):
        self.item('b-label', 'b', 'true', outputs=[f'json:{self.root}/never.json'])
        self.w.pass_once()
        self.wait_end('b-label')
        self.w.pass_once()
        failed = json.loads((self.root / 'state' / 'items' / 'b-label.failed').read_text())
        self.assertIn('missing', failed['why'])

    def test_nonzero_exit_fails_and_is_not_retried(self):
        self.item('b-bad', 'b', 'exit 3', outputs=[f'any:{self.root}/x'])
        self.w.pass_once()
        self.wait_end('b-bad')
        self.w.pass_once()
        self.assertIn('exit 3', (self.root / 'state' / 'items' / 'b-bad.failed').read_text())
        self.w.pass_once()
        self.assertIsNone(self.status()['running'])

    def test_filler_yields_to_urgent_item(self):
        self.item('c-fill', 'c', 'sleep 60', preemptible=True)
        self.w.pass_once()
        self.assertEqual(self.status()['running'], 'c-fill')
        self.item('b-pilot', 'b', 'sleep 60', outputs=['x'])
        self.w.pass_once()
        self.assertEqual(self.status()['running'], 'b-pilot')
        self.assertEqual(self.status()['items']['c-fill']['state'], 'pending')

    def test_withdrawn_item_is_stopped(self):
        self.item('b-pilot', 'b', 'sleep 60', outputs=['x'])
        self.w.pass_once()
        (self.root / 'queue' / 'b-pilot.json').unlink()
        self.w.pass_once()
        self.assertIsNone(self.status()['running'])
        self.assertFalse(self.w.job_live('b-pilot'))

    def test_held_item_waits(self):
        self.item('a-slice', 'a', 'sleep 60', outputs=['x'], hold=True)
        self.w.pass_once()
        self.assertIsNone(self.status()['running'])
        self.assertEqual(self.status()['items']['a-slice']['state'], 'held')

    def test_preempted_job_is_resumed(self):
        # A record that says running, started before the last boot, with no process: the VM stopped under it.
        self.item('a-slice', 'a', 'sleep 60', outputs=['x'], max_resumes=1)
        jobs = self.root / 'jobs' / 'jobs'
        jobs.mkdir(parents=True)
        old = time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime(self.w.jobctl.last_boot() - 3600))
        rec = {'name': 'a-slice', 'type': 'ta', 'id': 'feedfeedfeedfeed', 'started': old, 'state': 'running',
               'command': ['true'], 'queue_item': True, 'pid': 999999, 'keeper': 999998}
        (jobs / 'a-slice.json').write_text(json.dumps(rec))
        self.w.pass_once()
        self.assertEqual(json.loads((self.root / 'state' / 'items' / 'a-slice.resumes').read_text())['count'], 1)
        self.assertEqual(self.status()['running'], 'a-slice')
        self.w.jobctl_cmd('stop', 'a-slice', '--grace', '1')


class ScoreDisplayTest(unittest.TestCase):
    """The worker's CalibratedScore guard (owner, 2026-11-13), on any platform: an item running a build whose commit
    has the option starts only from a tools checkout that forces it off. Uses this repository's history (skipped
    without c7a61ea's parent)."""
    ADOPTED = 'c7a61ea987595b7de3b105098b27e7360a73763f'

    def setUp(self):
        self.repo = HERE.parents[1]
        self.pre = subprocess.run(['git', '-C', str(self.repo), 'rev-parse', '--verify', '--quiet', self.ADOPTED + '^'],
                                  capture_output=True, text=True).stdout.strip()
        if not self.pre:
            self.skipTest("c7a61ea's parent is not in this clone")
        self.head = subprocess.run(['git', '-C', str(self.repo), 'rev-parse', 'HEAD'], capture_output=True,
                                   text=True).stdout.strip()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ['FORK_WORKER_ROOT'] = str(self.root)
        os.environ['FORK_JOBS'] = str(self.root / 'jobs')
        sys.path.insert(0, str(HERE))
        import worker
        self.w = importlib.reload(worker)
        self.w.GUARD_REPO = self.repo
        self.old_tools = self.root / 'old-tools'  # a checkout without tools/check_score_display_off.py
        self.old_tools.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def item(self, commit):
        b = self.root / 'builds' / 'b1'
        b.mkdir(parents=True, exist_ok=True)
        if commit:
            (b / 'build.env').write_text(f'commit={commit}\narch=x86-64-v3\n')
        return {'name': 'b-label', 'argv': ['python3', 'label.py', '--engine', str(self.root / 'builds') + '/b1/fork']}

    def test_build_with_the_option_and_an_old_checkout_refused(self):
        self.w.TOOLS_TREE = self.old_tools
        why = self.w.score_display_refusal(self.item(self.head))
        self.assertIsNotNone(why)
        self.assertIn('refused', why)

    def test_build_with_the_option_and_this_checkout_allowed(self):
        self.w.TOOLS_TREE = self.repo
        self.assertIsNone(self.w.score_display_refusal(self.item(self.head)))

    def test_build_without_the_option_allowed_anywhere(self):
        self.w.TOOLS_TREE = self.old_tools
        self.assertIsNone(self.w.score_display_refusal(self.item(self.pre)))

    def test_build_without_build_env_refused(self):
        self.w.TOOLS_TREE = self.repo
        self.assertIn('no build.env commit', self.w.score_display_refusal(self.item(None)))

    def test_item_without_a_build_needs_nothing(self):
        self.w.TOOLS_TREE = self.old_tools
        self.assertIsNone(self.w.score_display_refusal({'name': 'x', 'argv': ['bash', '-c', 'true']}))

    def test_refused_item_is_failed_without_starting(self):
        self.w.TOOLS_TREE = self.old_tools
        (self.root / 'state' / 'items').mkdir(parents=True)
        self.assertFalse(self.w.start(dict(self.item(self.head), type='tb', **{'class': 'b'})))
        failed = json.loads((self.root / 'state' / 'items' / 'b-label.failed').read_text())
        self.assertIn('CalibratedScore', failed['why'])
        self.assertFalse((self.root / 'jobs').exists())


if __name__ == '__main__':
    unittest.main()
