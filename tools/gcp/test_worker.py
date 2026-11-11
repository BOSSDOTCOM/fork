# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the Google Cloud worker's queue logic (tools/gcp/worker.py) with stub jobs, on Linux (WSL or the VM):

    python3 -I tools/gcp/test_worker.py
"""
import importlib
import json
import os
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


if __name__ == '__main__':
    unittest.main()
