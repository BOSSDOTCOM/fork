# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the job supervisor and the run-ID ledger (tools/jobs), each in a fresh $FORK_JOBS:
- a stop ends the whole process tree: the command, its child, a grandchild whose parent has already exited
  (an orphan, what a killed wrapper leaves), and on POSIX a descendant that started a session of its own;
  the stop verifies none is left and releases the lock;
- one lock per type: a second job of a type is refused while the first runs, another type is not;
- a job that ends by itself releases its lock;
- a lock whose job has no process left is reclaimed (and logged); one whose job lives is never taken;
- a stop that leaves a process alive exits 1 and keeps the lock (the termination stubbed out);
- the ledger: records, the last record per stage, exact checks of a stage's run and inputs, a run id
  refused for a second stage.

    python -I -m unittest discover -s tools/jobs -p 'test_*.py'
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
JOBCTL = HERE / 'jobctl.py'
LEDGER = HERE / 'ledger.py'
sys.path.insert(0, str(HERE))
import jobctl  # noqa: E402

TREE = textwrap.dedent('''
    import os, subprocess, sys, time
    out, mode = sys.argv[1], sys.argv[2]
    if mode == 'root':
        kids = [subprocess.Popen([sys.executable, __file__, out, 'sleeper']),
                subprocess.Popen([sys.executable, __file__, out, 'orphaner'])]
        if os.name != 'nt':
            kids.append(subprocess.Popen([sys.executable, __file__, out, 'sleeper'], start_new_session=True))
        kids[1].wait()  # the orphaner's parent exits; its own child lives on
        time.sleep(600)
    elif mode == 'orphaner':
        subprocess.Popen([sys.executable, __file__, out, 'sleeper'])
        time.sleep(0.5)
    else:
        time.sleep(600)
    ''')


ORPHAN = textwrap.dedent('''
    import subprocess, sys, time
    out, mode = sys.argv[1], sys.argv[2]
    if mode == 'root':
        subprocess.Popen([sys.executable, __file__, out, 'orphaner']).wait()
        time.sleep(600)
    elif mode == 'orphaner':
        p = subprocess.Popen([sys.executable, __file__, out, 'sleeper'])
        open(out, 'w').write(str(p.pid))
    else:
        time.sleep(600)
    ''')


def alive(pid):
    return jobctl.pid_alive(pid)


def kill(pid):
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


class Supervisor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, FORK_JOBS=str(self.root / 'jobs'))
        os.environ['FORK_JOBS'] = self.env['FORK_JOBS']
        self.started = []

    def tearDown(self):
        for name in self.started:
            subprocess.run([sys.executable, '-I', str(JOBCTL), 'stop', name, '--grace', '1'], env=self.env,
                           capture_output=True)
        self.tmp.cleanup()

    def ctl(self, *args):
        return subprocess.run([sys.executable, '-I', str(JOBCTL), *args], env=self.env, capture_output=True,
                              text=True, timeout=120)

    def start(self, kind, name, *cmd):
        r = self.ctl('start', kind, name, '--', *cmd)
        if r.returncode == 0:
            self.started.append(name)
        return r

    def record(self, name):
        return json.loads((self.root / 'jobs' / 'jobs' / f'{name}.json').read_text(encoding='utf-8'))

    def lock(self, kind):
        p = self.root / 'jobs' / 'locks' / f'{kind}.json'
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None

    def wait_for(self, cond, seconds=30):
        deadline = time.time() + seconds
        while time.time() < deadline:
            if cond():
                return True
            time.sleep(0.1)
        return False

    def test_stop_ends_the_whole_tree(self):
        script = self.root / 'tree.py'
        script.write_text(TREE, encoding='utf-8')
        r = self.start('test', 'tree', sys.executable, '-I', str(script), str(self.root / 'pids'), 'root')
        self.assertEqual(r.returncode, 0, r.stderr)
        want = 4 if os.name == 'nt' else 5  # root, sleeper, orphaner's child, (session leader), and the keeper
        self.assertTrue(self.wait_for(lambda: len(jobctl.live(self.record('tree'))) >= want),
                        jobctl.live(self.record('tree')))
        pids = jobctl.live(self.record('tree'))
        self.assertTrue(all(alive(p) for p in pids))
        r = self.ctl('stop', 'tree', '--grace', '2')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('none left', r.stdout)
        self.assertEqual([p for p in pids if alive(p)], [])
        self.assertIsNone(self.lock('test'))
        self.assertEqual(self.record('tree')['state'], 'stopped')

    def test_a_descendant_outliving_the_command_keeps_the_job(self):
        spawn = ('import subprocess, sys; '
                 'subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(600)"])')
        r = self.start('test', 'leaver', sys.executable, '-I', '-c', spawn)
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.record('leaver')
        self.assertTrue(self.wait_for(lambda: not alive(self.record('leaver')['pid'])))  # the command is gone
        time.sleep(1.5)
        self.assertEqual(self.record('leaver')['state'], 'running')  # its descendant is not
        self.assertTrue([p for p in jobctl.live(self.record('leaver')) if p not in (rec.get('keeper'),)])
        self.assertEqual(self.lock('test')['name'], 'leaver')
        self.assertEqual(self.ctl('status', 'leaver').returncode, 0)
        r = self.ctl('stop', 'leaver', '--grace', '1')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(jobctl.live(self.record('leaver')), [])
        self.assertIsNone(self.lock('test'))

    def test_one_job_per_type(self):
        sleep = [sys.executable, '-I', '-c', 'import time; time.sleep(600)']
        self.assertEqual(self.start('github', 'first', *sleep).returncode, 0)
        r = self.start('github', 'second', *sleep)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('held by job first', r.stderr)
        self.assertEqual(self.start('measure', 'other', *sleep).returncode, 0)
        self.assertEqual(self.lock('github')['name'], 'first')
        self.assertEqual(self.ctl('stop', 'first', '--grace', '1').returncode, 0)
        self.assertEqual(self.start('github', 'second', *sleep).returncode, 0)

    def test_an_ended_job_releases_its_lock(self):
        r = self.start('test', 'short', sys.executable, '-I', '-c', 'print("hello")')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.wait_for(lambda: self.record('short').get('state') == 'ended'))
        self.assertTrue(self.wait_for(lambda: self.lock('test') is None))
        self.assertEqual(self.record('short')['exit_code'], 0)
        self.assertIn('hello', Path(self.record('short')['log']).read_text())

    def test_a_dead_jobs_lock_is_reclaimed_a_live_ones_is_not(self):
        locks, jobs = self.root / 'jobs' / 'locks', self.root / 'jobs' / 'jobs'
        locks.mkdir(parents=True)
        jobs.mkdir(parents=True)
        dead = subprocess.Popen([sys.executable, '-I', '-c', 'pass'])
        dead.wait()
        (jobs / 'gone.json').write_text(json.dumps({'name': 'gone', 'type': 'test', 'id': 'feedfacefeedface',
                                                    'started': 'x', 'keeper': dead.pid, 'pid': dead.pid,
                                                    'state': 'running'}))
        (locks / 'test.json').write_text(json.dumps({'name': 'gone', 'id': 'feedfacefeedface', 'started': 'x'}))
        sleep = [sys.executable, '-I', '-c', 'import time; time.sleep(600)']
        self.assertEqual(self.start('test', 'next', *sleep).returncode, 0)
        events = (self.root / 'jobs' / 'events.jsonl').read_text().splitlines()
        self.assertTrue(any(json.loads(e)['event'] == 'reclaim' for e in events))
        r = self.start('test', 'third', *sleep)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('held by job next', r.stderr)

    def test_stop_ends_the_tree_after_its_keeper_and_command_died(self):
        # 2026-11-06: a job whose keeper had died lost its Job Object's name, so `stop` saw no process and
        # reported none left while an SPRT driver lived on.
        script = self.root / 'orphan.py'
        script.write_text(ORPHAN, encoding='utf-8')
        pids = self.root / 'orphan-pid'
        r = self.start('test', 'bereaved', sys.executable, '-I', str(script), str(pids), 'root')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.wait_for(lambda: pids.exists() and pids.read_text().strip()))
        orphan = int(pids.read_text())
        time.sleep(2.5)  # the keeper hands out the Job Object's handles once a second
        rec = self.record('bereaved')
        for pid in (rec['keeper'], rec['pid']):
            kill(pid)
        self.assertTrue(self.wait_for(lambda: not alive(rec['keeper']) and not alive(rec['pid'])))
        self.assertTrue(alive(orphan))
        r = self.ctl('stop', 'bereaved', '--grace', '2')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.wait_for(lambda: not alive(orphan), 10), f'pid {orphan} survived the stop')

    def test_a_job_started_inside_another_outlives_its_stop(self):
        # 2026-11-06: stopping a chain job killed the SPRT job it had started.
        inner = [sys.executable, '-I', '-c', 'import time; time.sleep(600)']
        outer = ('import subprocess, sys, time; '
                 f'subprocess.run([sys.executable, "-I", {str(JOBCTL)!r}, "start", "test", "inner", "--", *{inner!r}]); '
                 'time.sleep(600)')
        r = self.start('queue', 'outer', sys.executable, '-I', '-c', outer)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.started.append('inner')
        path = self.root / 'jobs' / 'jobs' / 'inner.json'
        self.assertTrue(self.wait_for(lambda: path.exists() and self.record('inner').get('state') == 'running'))
        own = jobctl.live(self.record('outer'))
        r = self.ctl('stop', 'outer', '--grace', '2')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([p for p in own if alive(p)], [])
        time.sleep(1)
        rec = self.record('inner')
        self.assertTrue(alive(rec['keeper']) and alive(rec['pid']), rec)
        self.assertEqual(self.ctl('status', 'inner').returncode, 0)
        self.assertEqual(self.lock('test')['name'], 'inner')
        self.assertEqual(self.ctl('stop', 'inner', '--grace', '1').returncode, 0)
        self.assertFalse(alive(rec['pid']))

    def test_a_finished_jobs_recorded_ids_are_not_its_processes(self):
        # 2026-11-06: a stopped WSL job's keeper and command ids (461, 462) were reused by short-lived
        # processes, and the Control Center refused to start the next part while "g3e was running".
        other = subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(60)'])
        try:
            for state in ('stopped', 'ended'):
                rec = {'name': 'done', 'type': 'test', 'id': 'feedfacefeedface', 'state': state,
                       'keeper': other.pid, 'pid': other.pid}
                self.assertEqual(jobctl.live(rec), [], state)
            rec['state'] = 'running'
            self.assertEqual(jobctl.live(rec), [other.pid])
        finally:
            other.kill()
            other.wait()

    def test_a_failed_stop_keeps_the_lock(self):
        sleep = [sys.executable, '-I', '-c', 'import time; time.sleep(600)']
        self.assertEqual(self.start('test', 'stubborn', *sleep).returncode, 0)
        self.assertTrue(self.wait_for(lambda: self.record('stubborn').get('state') == 'running'))
        saved = jobctl.terminate
        jobctl.terminate = lambda record, grace: None  # the fault: nothing is killed
        try:
            with self.assertRaises(SystemExit) as e:
                jobctl.cmd_stop(['stubborn', '--grace', '0'])
            self.assertEqual(e.exception.code, 1)
        finally:
            jobctl.terminate = saved
        self.assertEqual(self.lock('test')['name'], 'stubborn')
        self.assertTrue(jobctl.live(self.record('stubborn')))


class Ledger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, FORK_JOBS=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_ledger(self, *args):
        return subprocess.run([sys.executable, '-I', str(LEDGER), *args], env=self.env, capture_output=True,
                              text=True)

    def test_records_and_checks(self):
        a, b, c = '1' * 40, '2' * 40, '3' * 40
        self.assertEqual(self.run_ledger('add', 'x', '0', '100', '--base', a, '--test', b).returncode, 0)
        self.assertEqual(self.run_ledger('add', 'x', '1', '101', '--base', a, '--test', b).returncode, 0)
        self.assertEqual(self.run_ledger('add', 'x', '1', '105', '--base', a, '--test', b).returncode, 0)  # a rerun
        self.assertEqual(self.run_ledger('runs', 'x').stdout.split('\n')[:2],
                         [f'0 100 {a} {b}', f'1 105 {a} {b}'])
        self.assertEqual(self.run_ledger('check', 'x', '1', '105', a, b).returncode, 0)
        self.assertEqual(self.run_ledger('check', 'x', '1', '101', a, b).returncode, 1)  # superseded
        self.assertEqual(self.run_ledger('check', 'x', '0', '100', a, c).returncode, 1)  # other inputs
        self.assertEqual(self.run_ledger('check', 'y', '0', '100', a, b).returncode, 1)  # other SPRT
        r = self.run_ledger('add', 'y', '0', '100', '--base', a, '--test', b)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('already recorded as x stage 0', r.stderr)
        self.assertEqual(self.run_ledger('known', '101').returncode, 0)
        self.assertEqual(self.run_ledger('known', '999').returncode, 1)
        self.assertNotEqual(self.run_ledger('add', 'x', '2', '106', '--base', 'abc', '--test', b).returncode, 0)


if __name__ == '__main__':
    unittest.main()
