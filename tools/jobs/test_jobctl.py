# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the job supervisor and the run-ID ledger (tools/jobs), each in a fresh $FORK_JOBS:
- a stop ends the whole process tree: the command, its child, a grandchild whose parent has already exited
  (an orphan, what a killed wrapper leaves), and on POSIX a descendant that started a session of its own;
  the stop verifies none is left and releases the lock;
- a job started inside another (the 8b chain's `jobctl start ... -- bash script` path) stops with its whole
  tree, its orphans included once its bash is killed, and the outer job lives on; the job it was started from
  is never counted as started inside it, old records (no 'parent') by their start times;
- on Windows with WSL, a `wsl.exe -d DISTRO -- ...` job's Linux processes stop with it in every running
  distribution, one that ignores SIGHUP and SIGTERM included (a throwaway sleep with a unique marker); a sweep
  that cannot look counts as a process left, and a stop of a record from before the marker says so;
- one lock per type: a second job of a type is refused while the first runs, another type is not;
- a job that ends by itself releases its lock;
- a lock whose job has no process left is reclaimed (and logged); one whose job lives is never taken;
- a stop that leaves a process alive exits 1 and keeps the lock (the termination stubbed out);
- the ledger: records, the last record per stage, exact checks of a stage's run and inputs, a run id
  refused for a second stage;
- the two-try limit (tries.jsonl): two tries per idea and time control class, a third only with an owner
  override recorded verbatim, a resume not counted, the run records untouched.

    python -I -m unittest discover -s tools/jobs -p 'test_*.py'
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
import uuid
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


def running_distros():
    """The WSL distributions running now (none off Windows or without WSL); the WSL test starts none."""
    if os.name != 'nt' or not shutil.which('wsl.exe'):
        return []
    try:
        out = subprocess.run(['wsl.exe', '-l', '--running', '-q'], capture_output=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [d.strip() for d in out.decode('utf-16-le', 'replace').replace('\0', '').splitlines() if d.strip()]


def linux_pids(distro, marker):
    """The distro's processes whose command line holds `sleep MARKER` (the [s] keeps pgrep's own shell out)."""
    r = subprocess.run(['wsl.exe', '-d', distro, '-u', 'root', '-e', 'pgrep', '-f', f'[s]leep {marker}'],
                       capture_output=True, text=True, timeout=60)
    return [int(x) for x in r.stdout.split()]


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

    def start_nested_upload(self):
        """The 8b chain's launch path: an outer job runs a bash script that starts an inner job with
        `jobctl start ... -- bash inner.sh`, and inner.sh runs Python as its last command but one (bash waits in
        a child of its own for it, as upload-run.sh does). Returns the inner job's Python process id."""
        bash = shutil.which('bash')
        if not bash or 'system32' in bash.lower():
            self.skipTest('no Git Bash or POSIX bash')
        fwd = lambda p: str(p).replace('\\', '/')  # noqa: E731
        child = self.root / 'child.py'
        child.write_text('import os, sys, time\nopen(sys.argv[1], "w").write(str(os.getpid()))\ntime.sleep(600)\n',
                         encoding='utf-8')
        inner = self.root / 'inner.sh'
        inner.write_text('"$1" -I "$2" "$3"\nrc=$?\necho "child exit $rc"\nexit $rc\n', encoding='utf-8', newline='\n')
        outer = self.root / 'outer.sh'
        outer.write_text('"$1" -I "$2" start upload inner -- "$3" "$4" "$1" "$5" "$6"\nsleep 600\n',
                         encoding='utf-8', newline='\n')
        self.pidfile = self.root / 'child-pid'
        r = self.start('kaggle', 'outer', bash, fwd(outer), fwd(sys.executable), fwd(JOBCTL), fwd(bash), fwd(inner),
                       fwd(child), fwd(self.pidfile))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.started.append('inner')
        path = self.root / 'jobs' / 'jobs' / 'inner.json'
        self.assertTrue(self.wait_for(lambda: path.exists() and self.record('inner').get('state') == 'running'
                                      and self.pidfile.exists() and self.pidfile.read_text().strip()))
        return int(self.pidfile.read_text())

    def test_a_job_started_inside_another_stops_with_its_whole_tree(self):
        # 2026-11-10: `stop r8b-upload-pre2-r3` (an upload job the r8b-chain3 job had started) ended nothing: on
        # Windows the inner Job Object nests in the outer one, so every inner process was also "another job's".
        child = self.start_nested_upload()
        outer = jobctl.live(self.record('outer'))
        self.assertIn(child, jobctl.live(self.record('inner')))
        self.assertNotIn(child, outer)
        r = self.ctl('stop', 'inner', '--grace', '2')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(alive(child), f'pid {child} survived the stop')
        self.assertEqual(self.record('inner')['state'], 'stopped')
        self.assertEqual([p for p in outer if not alive(p)], [])  # the outer job is untouched
        self.assertEqual(self.ctl('status', 'outer').returncode, 0)

    def test_a_nested_jobs_orphans_are_found_after_its_command_dies(self):
        # The same incident's second half: the job's bash was killed by hand, the next stop reported "processes
        # none", and the bash child running the upload lived on (its parent gone, its Job Object's name gone).
        child = self.start_nested_upload()
        time.sleep(2.5)  # the keeper hands out the Job Object's handles once a second
        rec = self.record('inner')
        kill(rec['pid'])
        self.assertTrue(self.wait_for(lambda: not alive(rec['pid'])))
        time.sleep(1.5)
        self.assertTrue(alive(child))
        self.assertIn(child, jobctl.live(self.record('inner')))
        self.assertEqual(self.ctl('status', 'inner').returncode, 0)
        r = self.ctl('stop', 'inner', '--grace', '2')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.wait_for(lambda: not alive(child), 10), f'pid {child} survived the stop')

    def test_a_wsl_jobs_linux_processes_stop_with_it(self):
        # 2026-11-10: a Windows stop of `jobctl start ... -- wsl.exe -d Ubuntu -- bash script.sh` ended wsl.exe
        # only; the Linux side, outside every Windows Job Object, ran on. A plain sleep, and a shell that ignores
        # SIGHUP and SIGTERM (so its sleep does too, and only SIGKILL ends it), each with a unique marker.
        distros = running_distros()
        if not distros:
            self.skipTest('no running WSL distribution')
        for distro in distros:
            for linux in (['sleep', '{m}'], ['sh', '-c', "trap '' HUP TERM; sleep {m}; :"]):
                with self.subTest(distro=distro, linux=linux[0]):
                    marker = f'600.{uuid.uuid4().int % 10**9:09d}'
                    name = f'wsl-{len(self.started)}'
                    try:
                        r = self.ctl('start', 'test', name, '--', 'wsl.exe', '-d', distro, '--',
                                     *(a.format(m=marker) for a in linux))
                        self.assertEqual(r.returncode, 0, r.stderr)
                        self.started.append(name)
                        self.assertTrue(self.wait_for(lambda: linux_pids(distro, marker), 60))
                        r = self.ctl('stop', name, '--grace', '2')
                        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                        self.assertTrue(self.wait_for(lambda: not linux_pids(distro, marker), 10),
                                        f'{distro}: {linux_pids(distro, marker)} survived the stop')
                    finally:
                        subprocess.run(['wsl.exe', '-d', distro, '-u', 'root', '-e', 'pkill', '-KILL', '-f',
                                        f'[s]leep {marker}'], capture_output=True, timeout=60)

    @unittest.skipUnless(os.name == 'nt' and shutil.which('wsl.exe'), 'Windows with WSL')
    def test_a_wsl_sweep_that_cannot_look_is_not_none_left(self):
        saved = jobctl.wsl_running
        jobctl.wsl_running = lambda: ['NoSuchDistro-forkjobtest']
        try:
            self.assertEqual(jobctl.wsl_pids({'id': 'feedfacefeedface', 'wslenv': True}),
                             ['NoSuchDistro-forkjobtest:unknown'])
            self.assertEqual(jobctl.wsl_pids({'id': 'feedfacefeedface'}), [])  # a record from before the marker
        finally:
            jobctl.wsl_running = saved
        # A stop of such an old record says its Linux side was not checked.
        jobs = self.root / 'jobs' / 'jobs'
        jobs.mkdir(parents=True)
        dead = subprocess.Popen([sys.executable, '-I', '-c', 'pass'])
        dead.wait()
        (jobs / 'old.json').write_text(json.dumps({'name': 'old', 'type': 'test', 'id': 'feedfacefeedface',
                                                   'started': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                                                   'keeper': dead.pid, 'pid': dead.pid, 'state': 'running',
                                                   'command': ['wsl.exe', '-d', 'Ubuntu', '--', 'true']}))
        r = self.ctl('stop', 'old', '--grace', '0')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('any it left in WSL were not checked', r.stdout)

    def test_which_jobs_count_as_started_inside(self):
        # Records from before 'parent' was kept (jobs running across the fix) fall back to the start times.
        outer = {'id': 'a', 'started': '2026-11-10T00:09:40-0500'}
        old_inner = {'id': 'b', 'started': '2026-11-10T05:50:14-0500'}
        same_second = {'id': 'c', 'started': outer['started']}
        self.assertTrue(jobctl.started_inside(old_inner, outer, {}))
        self.assertFalse(jobctl.started_inside(outer, old_inner, {}))  # the job it was started from
        self.assertFalse(jobctl.started_inside(same_second, outer, {}))
        child = dict(same_second, parent='a')  # a recorded parent settles a tie
        grandchild = {'id': 'd', 'started': outer['started'], 'parent': 'c'}
        self.assertTrue(jobctl.started_inside(child, outer, {}))
        self.assertTrue(jobctl.started_inside(grandchild, outer, {'c': child}))
        self.assertFalse(jobctl.started_inside(outer, child, {'c': child}))
        self.assertFalse(jobctl.started_inside({'id': 'e', 'parent': 'e'}, outer, {'e': {'parent': 'e'}}))

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
            # 2026-11-07: the machine went down while g3h ran, so its record still said "running"; after the
            # reboot its recorded ids (463, 464) were reused and the next part's start was refused. A job that
            # started before the last boot has no process left, whatever its record says.
            rec['started'] = '2000-01-01T00:00:00+0000'
            self.assertEqual(jobctl.live(rec), [])
            rec['started'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
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


class Tries(unittest.TestCase):
    """The two-try limit (owner, DESIGN.md §6 2026-11-07 decision 2): at most two SPRTs per idea and time
    control class; a third only with an owner override, recorded verbatim; tries.jsonl, apart from the run
    ledger."""
    A, B = '1' * 40, '2' * 40

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, FORK_JOBS=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_ledger(self, *args):
        return subprocess.run([sys.executable, '-I', str(LEDGER), *args], env=self.env, capture_output=True,
                              text=True)

    def try_(self, sprt, *extra, idea='razoring', tc='stc'):
        return self.run_ledger('try', idea, sprt, '--kind', 'search', '--tc-class', tc, '--base', self.A,
                               '--test', self.B, *extra)

    def records(self):
        p = Path(self.tmp.name) / 'tries.jsonl'
        return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()] if p.exists() else []

    def test_tries_limit(self):
        r = self.try_('raz-a')
        self.assertEqual((r.returncode, r.stdout.strip()), (0, 'try 1 of 2'))
        self.assertEqual(self.try_('raz-b').returncode, 0)
        r = self.try_('raz-c', '--check')
        self.assertEqual(r.returncode, 3)
        self.assertIn('already has 2 stc tries (raz-a, raz-b)', r.stderr)
        self.assertEqual(self.try_('raz-c').returncode, 3)
        self.assertEqual(len(self.records()), 2)  # refused: nothing written
        r = self.try_('raz-c', '--owner-override', 'owner, 2026-11-09: third try', '--check')
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(self.records()), 2)  # --check writes nothing
        self.assertEqual(self.try_('raz-c', '--owner-override', 'owner, 2026-11-09: third try').returncode, 0)
        self.assertEqual(self.records()[-1]['override'], 'owner, 2026-11-09: third try')
        self.assertEqual(self.records()[-1]['try'], 3)
        self.assertEqual(self.try_('raz-d', '--owner-override', '').returncode, 2)
        listed = self.run_ledger('tries', 'razoring').stdout.splitlines()
        self.assertEqual(listed[0], f'1 raz-a search stc {self.A} {self.B}')
        self.assertEqual(listed[2], f'3 raz-c search stc {self.A} {self.B} override: owner, 2026-11-09: third try')

    def test_try_resume_not_counted(self):
        self.assertEqual(self.try_('raz-a').returncode, 0)
        r = self.try_('raz-a')
        self.assertEqual((r.returncode, r.stdout.strip()), (0, 'resume of try 1'))
        self.assertEqual(len(self.records()), 1)
        r = self.try_('raz-a', idea='other')  # one SPRT name belongs to one idea
        self.assertEqual(r.returncode, 1)
        self.assertIn('raz-a is a try of idea razoring', r.stderr)

    def test_tries_by_tc_class(self):
        self.assertEqual(self.try_('raz-a').returncode, 0)
        self.assertEqual(self.try_('raz-b').returncode, 0)
        r = self.try_('raz-ltc', tc='ltc')
        self.assertEqual((r.returncode, r.stdout.strip()), (0, 'try 1 of 2'))

    def test_run_ledger_untouched(self):
        self.assertEqual(self.run_ledger('add', 'x', '0', '100', '--base', self.A, '--test', self.B).returncode, 0)
        before = [self.run_ledger(*a).stdout for a in (('runs', 'x'),)]
        self.assertEqual(self.try_('x').returncode, 0)
        self.assertEqual([self.run_ledger(*a).stdout for a in (('runs', 'x'),)], before)
        self.assertEqual(self.run_ledger('check', 'x', '0', '100', self.A, self.B).returncode, 0)
        self.assertEqual(self.run_ledger('known', '100').returncode, 0)
        self.assertEqual(len((Path(self.tmp.name) / 'ledger.jsonl').read_text().splitlines()), 1)

    def test_bad_arguments_refused(self):
        self.assertEqual(self.try_('raz-a', idea='Bad Idea').returncode, 2)
        self.assertEqual(self.try_('raz-a', tc='vltc').returncode, 2)
        r = self.run_ledger('try', 'razoring', 'raz-a', '--kind', 'custom', '--tc-class', 'stc', '--base', self.A,
                            '--test', self.B)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.records(), [])


if __name__ == '__main__':
    unittest.main()
