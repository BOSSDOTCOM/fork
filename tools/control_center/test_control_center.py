# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the Control Center (tools/control_center), with every external command stubbed:
- parsing of the real formats: fork_datagen's log, a part's launch log, fork_datagen's command line and
  `fork version` (fixtures/ copied from the live runs, user paths replaced), the sealed manifests, the
  bench reference and CMakeLists.txt, the SPRT driver logs, the SPRT log, nets.md, DESIGN.md's section 5.6
  and decisions log (the committed files themselves), Ordo, run.json, the Kaggle CLI, gh, /proc/meminfo, df;
- the data-generation controls against a simulated WSL supervisor: the next part's plan (name, seed,
  target, engine build or reuse), start refused while a datagen job lives or holds the lock, on low disk,
  or when jobctl itself refuses; a start's launch files and command; attaching to a running part (g3e's
  real command line and log); stop & seal (the stop, then the seal job), a failed stop sealing nothing;
  the auto-stop and the sleep block's release (the watchdog loop on a fake clock); one watchdog at a time;
- the seal: complete games only (a synthetic shard with an unfinished game; the real g3d copies when present
  on this machine), a failed verification keeping every file and sealing nothing, an occupied folder never
  overwritten, a passing one sealed with its reason;
- that no read-only tab can change anything: the command guard, the read-only view without control(),
  every collector and every read-only tab's render() run under an audit hook that fails on any write,
  delete, rename, folder creation, process start or file launch, with the fixture tree's files hashed
  before and after; and the read-only tabs are built without the controller;
- notifications: an SPRT decision, a finished Kaggle session, failed and unexpectedly stopped jobs, a seal,
  disk and memory warnings, nothing on the first snapshot.

    python -I -m unittest discover -s tools/control_center -p "test_*.py"
"""
import hashlib
import inspect
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIX = HERE / 'fixtures'
sys.path.insert(0, str(HERE))
import collectors  # noqa: E402
import config  # noqa: E402
import generation_control  # noqa: E402
import notify  # noqa: E402
import parsers as P  # noqa: E402
import runner as R  # noqa: E402
import seal_part  # noqa: E402
import watchdog  # noqa: E402


def fixture(name):
    return (FIX / name).read_text(encoding='utf-8')


G3E_CMDLINE = ['./fork_datagen', '--openings', '/home/user/fork-data/openings/lichess-2016-09.epd', '--out',
               '/home/user/fork-data/gen3e', '--run', 'g3e', '--positions', '477173594', '--nodes', '20000',
               '--threads', '10', '--seed', '20261110', '--hash-mb', '1', '--shard-mb', '1024', '--tables',
               '/home/user/fork-tools/syzygy/3-4-5', '--adjudicate-cp', '700', '--adjudicate-plies', '8',
               '--save-percent', '50', '--unsaved-nodes', '4000', '--check-nodes', '2000']  # /proc/462/cmdline

# ================================================================ the audit guard

WRITE_EVENTS = {'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'os.chmod', 'os.truncate', 'os.utime',
                'os.link', 'os.symlink', 'shutil.copyfile', 'shutil.copymode', 'shutil.copystat', 'shutil.move',
                'shutil.rmtree', 'shutil.copytree', 'subprocess.Popen', 'os.system', 'os.startfile', 'os.spawn',
                'os.posix_spawn', 'os.exec', 'os.fork', 'os.kill', 'winreg.SetValue', 'winreg.CreateKey'}
GUARD = {'on': False, 'violations': []}
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC


def _audit(event, args):
    """While the guard is on, records and blocks (raises) every write, delete, rename, folder creation,
    process start and file launch."""
    if not GUARD['on']:
        return
    bad = None
    if event == 'open':
        path, mode, flags = (list(args) + [None, None, None])[:3]
        if isinstance(mode, str) and any(c in mode for c in 'wax+'):
            bad = (event, str(path), mode)
        elif mode is None and isinstance(flags, int) and flags & WRITE_FLAGS:
            bad = (event, str(path), flags)
    elif event in WRITE_EVENTS:
        bad = (event, str(args)[:200])
    if bad:
        GUARD['violations'].append(bad)
        raise PermissionError(f'blocked by the read-only guard: {bad}')


sys.addaudithook(_audit)


class guarded:
    def __enter__(self):
        GUARD['violations'] = []
        GUARD['on'] = True
        return GUARD

    def __exit__(self, *exc):
        GUARD['on'] = False
        return False


def tree_hashes(root):
    out = {}
    for dirpath, dirs, files in os.walk(root):
        for f in files:
            p = os.path.join(dirpath, f)
            st = os.stat(p)
            out[p] = (hashlib.sha256(Path(p).read_bytes()).hexdigest(), st.st_mtime_ns, st.st_size)
        for d in dirs:
            out[os.path.join(dirpath, d)] = 'dir'
    return out


# ================================================================ parsing the real formats

class Parsing(unittest.TestCase):
    def test_datagen_log(self):
        d = P.datagen_log(fixture('g3e.log'))
        self.assertEqual(d['last'], {'seconds': 12240, 'games': 318299, 'positions': 29852407, 'rate': 2439})
        self.assertAlmostEqual(d['recent_rate'], (29852407 - 29784295) / 30)
        self.assertIsNone(d['done'])
        done = P.datagen_log(fixture('g3-done.log'))['done']
        self.assertEqual(done, {'games': 5334231, 'positions': 500000697, 'seconds': 182879.5, 'rate': 2734})

    def test_launch_log_command_line_and_version(self):
        self.assertEqual(P.job_log_start(fixture('g3e-job.log')), 1793979916)
        s, paths = P.datagen_args(G3E_CMDLINE)
        self.assertEqual(s, {'positions_target': 477173594, 'nodes': 20000, 'threads': 10, 'seed': 20261110,
                             'hash_mb': 1, 'shard_mb': 1024, 'adjudicate_cp': 700, 'adjudicate_plies': 8,
                             'save_percent': 50, 'unsaved_nodes': 4000, 'check_nodes': 2000})
        self.assertEqual(paths['out'], '/home/user/fork-data/gen3e')
        v = P.fork_version(fixture('fork-version.txt'))
        self.assertEqual((v['version'], v['commit'], v['net'], v['arch']),
                         ('0.3.0-dev+684bac6', '684bac6', 's512r2', 'native'))
        self.assertTrue(v['compiler'].startswith('clang '))

    def test_bench_expected_and_default_net(self):
        ref = P.bench_expected((REPO / 'tests' / 'bench-s512r2.ref').read_text())
        self.assertEqual(set(ref), {'nodes', 'signature'})
        self.assertTrue(ref['nodes'].isdigit())
        self.assertEqual(P.default_net((REPO / 'CMakeLists.txt').read_text()), 's512r2')

    def test_manifests(self):
        m = json.loads((REPO / 'data' / 'manifests' / 'g3d.json').read_text())
        s = P.manifest_summary(m)
        self.assertEqual((s['run'], s['generation'], s['games'], s['positions']), ('g3d', 3, 194026, 18242788))
        self.assertEqual(s['saved'], 18242788 - 8314854)
        self.assertEqual((s['net'], s['commit'], s['seed'], s['threads']), ('s512r2', '684bac6', 20261109, 6))
        self.assertEqual(s['split'], '50% / 4000 / 2000')
        self.assertEqual(len(s['files']), 6)
        g2bc = json.loads((REPO / 'data' / 'manifests' / 'g2bc.json').read_text())
        self.assertFalse(P.is_part_manifest(g2bc))  # "not a part of its own"
        self.assertFalse(P.is_part_manifest(json.loads((REPO / 'data' / 'manifests' / 'g2s1.json').read_text())))
        self.assertEqual([P.next_part(x) for x in ('g3', 'g3e', 'g2b')], ['g3b', 'g3f', 'g2c'])
        self.assertEqual(P.part_dir('g3e'), 'gen3e')
        self.assertIsNone(P.part_key('g3s1'))

    def test_driver_logs(self):
        d = P.driver_log(fixture('driver-queue.log'))
        rfp = P.sprt_state(d['rising-rfp-25-vs-base'])
        self.assertEqual((rfp['stage'], rfp['games'], rfp['elo'], rfp['elo_err'], rfp['llr']),
                         (11, 19200, -3.78, 2.92, -3.76))
        self.assertEqual(rfp['verdict'], 'H0 accepted')
        self.assertEqual(rfp['finished'], 'decided after stage 11')
        rv = P.sprt_state(d['reval-no-check-relief'])
        self.assertEqual((rv['elo0'], rv['elo1'], rv['games'], rv['elo'], rv['llr'], rv['verdict']),
                         (-3.0, 0.0, 20800, -3.16, -1.92, 'continue'))
        self.assertEqual(rv['finished'], 'undecided after stage 12')
        t = P.sprt_state(P.driver_log(fixture('driver-threat.log'))['threat-set-cheaper-vs-base'])
        self.assertEqual((t['stage'], t['stage_state'], t['merged_stage'], t['games'], t['elo'], t['llr']),
                         (3, 'dispatched', 2, 4800, -5.57, -1.28))
        self.assertEqual((t['elo0'], t['elo1'], t['last_stage'], t['finished']), (0.0, 3.0, 12, None))

    def test_sprt_log(self):
        e = {x['name']: x for x in P.sprt_log((REPO / 'docs/history/phase-4/sprt-log.md').read_text('utf-8'))}
        self.assertTrue(e['reval-no-check-relief']['verdict'].startswith('undecided'))
        self.assertEqual(e['reval-no-check-relief']['elo'], -3.16)
        self.assertEqual(e['rising-rfp-25-vs-base']['verdict'], 'H0 accepted')
        self.assertEqual((e['r2s512-vs-s512']['verdict'], e['r2s512-vs-s512']['elo']), ('H1 accepted', 151.35))
        self.assertEqual(e['b0-vs-bootstrap']['date'], '2026-10-29')
        gains = P.sprt_gains(list(e.values()))
        names = [g[1] for g in gains]
        self.assertIn('r2s512-vs-s512', names)
        self.assertNotIn('ltc-iir-on-vs-off', names)  # a non-regression [-3, 0] test is not a gain

    def test_nets_md(self):
        n = P.nets_md((REPO / 'docs' / 'nets.md').read_text('utf-8'))
        self.assertEqual(n['default']['name'], 'S512r2')
        self.assertIn('B0r2', [x['name'] for x in n['nets']])
        self.assertIn('nets/s512.fnet', [x['net'] for x in n['entries']])

    def test_checklist_and_gauntlets(self):
        md = (REPO / 'docs' / 'DESIGN.md').read_text('utf-8')
        c = P.checklist(md)
        self.assertTrue(c['title'].startswith('5.6 '))
        groups = [g['group'] for g in c['groups']]
        for g in ('Network', 'Search', 'Speed', 'Final steps'):
            self.assertIn(g, groups)
        self.assertGreaterEqual(len(c['order']), 10)
        self.assertEqual([o['n'] for o in c['order']], list(range(1, len(c['order']) + 1)))
        g = {x['run']: x for x in P.decision_gauntlets(md)}
        self.assertEqual((g[41465146207]['rating'], g[41465146207]['error'], g[41465146207]['date']),
                         (3445.8, 21.6, '2026-11-02'))
        self.assertEqual(P.ordo(fixture('ordo.txt')),
                         {'rating': 3445.8, 'error': 21.6, 'points': 823.0, 'games': 1200, 'percent': 69})

    def test_training_kaggle_gh_machine(self):
        t = P.training_run(json.loads(fixture('run.json')))
        rec = json.loads(fixture('run.json'))
        best = min(rec['val_curve'], key=lambda x: x[1])
        self.assertEqual((t['arch'], t['seed'], t['best_loss'], t['best_at']), ('s512pp', 1, best[1], best[0]))
        self.assertEqual(P.kaggle_list(fixture('kaggle-list.csv'))[0]['ref'], 'owner/fork-s512pp')
        self.assertEqual(P.kaggle_status(fixture('kaggle-status.txt')), 'complete')
        runs = P.gh_runs(fixture('gh-runs.json'))
        self.assertEqual([r['workflow'] for r in runs], ['sprt', 'sprt', 'sprt', 'ci'])
        self.assertEqual(runs[0]['status'], 'in_progress')
        self.assertTrue(runs[1]['url'].startswith('https://github.com/'))
        mi = P.meminfo(fixture('meminfo.txt'))
        self.assertIn('MemTotal', mi)
        self.assertGreater(mi['MemTotal'], mi['MemAvailable'])
        self.assertEqual(P.df(fixture('df.txt')), {'total': 1081101176832, 'free': 1007235383296})
        m = P.measure_progress(fixture('measure.log'))
        self.assertEqual((m['done'], m['total']), (0, 2000))

    def test_times(self):
        self.assertEqual(P.est(1793979916), '2026-11-06 10:45:16 AM EST')  # g3e-job.log prints both
        self.assertEqual(P.iso_epoch('2026-11-06T10:45:12-0500'), 1793979912)
        self.assertEqual(P.duration(3 * 3600 + 61), '3:01:01')


# ================================================================ a simulated WSL supervisor

class World:
    """What the stubbed commands see: WSL's jobs, locks and folders, git's answers, the disks."""

    def __init__(self):
        self.jobs = {}
        self.datagen = {}
        self.folders = {}
        self.wsl_disk = {'total': 10 ** 12, 'free': 900 * 10 ** 9}
        self.diff_rc = 0
        self.stop_rc = 0
        self.stop_leaves = []
        self.external_lock = None
        self.seal_starts = []
        self.commit = 'c' * 40

    def add_running_g3e(self):
        self.jobs['g3e'] = {'record': json.loads(fixture('wsl-job-g3e.json')), 'live': [461, 462, 486]}
        self.datagen['g3e'] = {'name': 'g3e', 'pid': 462, 'cmdline': G3E_CMDLINE, 'dir': '/home/user/fork-data/gen3e',
                               'log_tail': fixture('g3e.log'), 'job_log_head': fixture('g3e-job.log'),
                               'job_log_tail': fixture('g3e-job.log'), 'run_json': False}

    def probe(self, folders):
        locks = [{'type': j['record']['type'], 'name': n, 'id': j['record']['id'], 'started': j['record']['started']}
                 for n, j in self.jobs.items() if j['live']]
        if self.external_lock:
            locks.append(self.external_lock)
        return {'home': '/home/user', 'jobs': list(self.jobs.values()), 'locks': locks, 'events': [],
                'datagen': list(self.datagen.values()), 'errors': [], 'disk': self.wsl_disk,
                'folders': {f: self.folders.get(f, {'path': f, 'exists': False}) for f in folders},
                'meminfo': fixture('meminfo.txt'), 'loadavg': ['10.0', '10.0', '10.0']}

    def backend(self, argv, timeout, input, cwd):
        a = [str(x) for x in argv]
        ok = lambda out='': R.Result(0, out, '')  # noqa: E731
        if os.path.basename(a[0]) == 'wsl.exe':
            cmd = a[a.index('--exec') + 1:]
            if cmd[:3] == ['python3', '-I', '-']:
                return ok(json.dumps(self.probe(cmd[6:])))
            if cmd[0] == 'python3' and cmd[3] == 'start':
                kind, name = cmd[4], cmd[5]
                held = [j for j in self.jobs.values() if j['record']['type'] == kind and j['live']]
                if held or self.external_lock:
                    return R.Result(1, '', f'jobctl: type {kind} is held by job {(held or [{}])[0].get("record", {}).get("name", "x")}')
                rec = {'name': name, 'type': kind, 'id': 'id-' + name, 'started': '2026-11-07T09:00:00-0500',
                       'state': 'running', 'log': cmd[cmd.index('--log') + 1]}
                self.jobs[name] = {'record': rec, 'live': [2000]}
                self.started_cmd = cmd
                return ok(f'started {name} (type {kind}, id id-{name}, pid 2000)')
            if cmd[0] == 'python3' and cmd[3] == 'stop':
                if self.stop_rc:
                    return R.Result(1, 'jobctl: job g3e: processes still alive after the stop: [462]; the lock is kept', '')
                j = self.jobs[cmd[4]]
                j['live'] = list(self.stop_leaves)
                j['record'] = dict(j['record'], state='stopped', stopped='2026-11-06T20:00:00-0500')
                self.datagen.get(cmd[4], {})['pid'] = None
                return ok(f'stopped {cmd[4]}')
            raise AssertionError(f'unexpected WSL command {cmd}')
        if os.path.basename(a[0]) == 'git':
            sub = a[3:]
            if sub[0] == 'rev-parse':
                return ok(self.commit + '\n')
            if sub[0] == 'show' and sub[1].endswith(':CMakeLists.txt'):
                return ok((REPO / 'CMakeLists.txt').read_text())
            if sub[0] == 'show' and sub[1].endswith('.ref'):
                return ok('nodes 14180299\nsignature 4cf778ff753861f7\n')
            if sub[0] == 'diff':
                return R.Result(self.diff_rc, '', '')
        if a[0].endswith('python.exe') and 'start' in a and 'seal' in a:
            self.seal_starts.append(a)
            return ok('started seal-g3e (type seal, id x, pid 9)')
        raise AssertionError(f'unexpected command {a[:5]}')


class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.repo = t / 'repo'
        (self.repo / 'data' / 'manifests').mkdir(parents=True)
        for f in ('g3.json', 'g3b.json', 'g3c.json', 'g3d.json', 'g2e.json', 'openings-lichess-2016-09.json'):
            shutil.copy(REPO / 'data' / 'manifests' / f, self.repo / 'data' / 'manifests' / f)
        self.copies = t / 'copies'
        self.copies.mkdir()
        self.state = t / 'state'
        self.cfg = config.load({'repo': str(self.repo), 'copies': str(self.copies), 'python': 'C:/py/python.exe'})
        self.world = World()
        self.runner = R.Runner(self.world.backend)
        self.clock = [1794000000.0]
        self.spawned = []
        self.cdisk = {'total': 5 * 10 ** 11, 'free': 200 * 10 ** 9}
        self.ctl = generation_control.GenerationControl(self.cfg, self.runner, state=self.state, disk=lambda p: self.cdisk,
                                   now=lambda: self.clock[0], spawn=self.spawned.append,
                                   pid_alive=lambda pid: pid == 4242)

    def tearDown(self):
        self.tmp.cleanup()

    def copy_g3e(self, positions=30000000):
        d = self.copies / 'g3e'
        d.mkdir()
        run = {'version': '0.3.0-dev+684bac6 (WSL clang PGO, clang 21.1.8)', 'evaluator': 'nnue (s512r2)',
               'settings': {'positions_target': 477173594, 'seed': 20261110, 'threads': 10},
               'games': 300000, 'positions': positions, 'shards': []}
        (d / 'g3e.json').write_text(json.dumps(run))

    def controls(self):
        return [c for c in self.runner.calls if c[0] == 'control']

    def test_plan_refuses_while_the_last_part_is_not_sealed(self):
        self.world.add_running_g3e()
        with self.assertRaises(generation_control.Refused) as e:
            self.ctl.plan()
        self.assertIn('g3e', str(e.exception))
        self.assertEqual(self.controls(), [])

    def test_plan_next_part(self):
        self.world.add_running_g3e()
        self.world.jobs['g3e']['live'] = []
        self.world.datagen['g3e']['pid'] = None
        self.copy_g3e()
        self.world.folders['~/fork-data/gen3e'] = {'exists': True, 'files': [{'name': 'fork'}, {'name': 'fork_datagen'}]}
        plan, probe = self.ctl.plan()
        self.assertEqual((plan['name'], plan['previous'], plan['generation']), ('g3f', 'g3e', 3))
        self.assertEqual(plan['settings']['seed'], 20261111)  # every local seed so far is at most 20261110
        self.assertEqual(plan['settings']['positions_target'], 477173594 - 30000000)
        self.assertEqual((plan['mode'], plan['engine_commit'], plan['reuse_dir']),
                         ('reuse', '684bac6', '~/fork-data/gen3e'))
        self.assertEqual((plan['net'], plan['bench_nodes'], plan['bench_signature']),
                         ('s512r2', '14180299', '4cf778ff753861f7'))
        self.assertEqual(plan['openings_sha256'],
                         '0ae298e1c7c635606fcddb056ee08073aeed8f4db4de3f19b8ef721d4a72831b')
        for k, v in {'nodes': 20000, 'adjudicate_cp': 700, 'adjudicate_plies': 8, 'save_percent': 50,
                     'unsaved_nodes': 4000, 'check_nodes': 2000, 'threads': 10}.items():
            self.assertEqual(plan['settings'][k], v)
        self.assertEqual(self.ctl.preflight(plan, probe), [])
        self.world.diff_rc = 1  # an engine file changed since 684bac6: a PGO build of the branch tip
        plan, _ = self.ctl.plan()
        self.assertEqual((plan['mode'], plan['engine_commit']), ('build', self.world.commit))
        self.assertEqual(self.controls(), [])

    def test_plan_refuses_after_a_failed_seal(self):
        self.copy_g3e()
        self.ctl.write_state('g3e', 'seal-result.json', {'state': 'verify-failed', 'message': 'FAIL game 12'})
        with self.assertRaises(generation_control.Refused) as e:
            self.ctl.plan()
        self.assertIn('verify-failed', str(e.exception))

    def test_start_refused_while_datagen_runs(self):
        self.world.add_running_g3e()
        self.copy_g3e()  # even with a copy, the live job refuses the start
        plan, probe = self.ctl.plan()
        why = ' '.join(self.ctl.preflight(plan, probe))
        self.assertIn('a data-generation job is running: g3e', why)
        self.assertIn('lock is held by g3e', why)
        with self.assertRaises(generation_control.Refused):
            self.ctl.start(plan, probe)
        self.assertEqual(self.controls(), [])
        self.assertEqual(self.spawned, [])

    def test_start_refused_on_windows_datagen_and_low_disk(self):
        self.copy_g3e()
        win = [{'record': {'name': 'other', 'type': 'datagen'}, 'live': [77]}]
        self.ctl.windows_jobs = lambda: win
        plan, probe = self.ctl.plan()
        self.assertIn('other (Windows', ' '.join(self.ctl.preflight(plan, probe)))
        win.clear()
        self.world.wsl_disk = {'total': 10 ** 12, 'free': 5 * 10 ** 9}
        self.cdisk = {'total': 10 ** 12, 'free': 21 * 10 ** 9}
        plan, probe = self.ctl.plan()
        why = self.ctl.preflight(plan, probe)
        self.assertTrue(any(w.startswith('WSL has') for w in why), why)
        self.assertTrue(any(w.startswith('C: has') for w in why), why)
        with self.assertRaises(generation_control.Refused):
            self.ctl.start(plan, probe)
        self.assertEqual(self.controls(), [])

    def test_start_refused_by_jobctl(self):
        self.copy_g3e()
        plan, probe = self.ctl.plan()
        self.world.external_lock = {'type': 'datagen', 'name': 'race', 'id': 'zz'}
        probe['locks'] = []  # the lock appeared after the preflight's probe
        with self.assertRaises(generation_control.Refused) as e:
            self.ctl.start(plan, probe)
        self.assertIn('held by', str(e.exception))
        self.assertIsNone(self.ctl.read_state('g3f', 'part.json'))  # renamed, so a retry is possible
        self.assertEqual(self.spawned, [])

    def test_start(self):
        self.copy_g3e()
        self.world.folders['~/fork-data/gen3e'] = {'exists': True, 'files': [{'name': 'fork'}, {'name': 'fork_datagen'}]}
        plan, probe = self.ctl.plan(threads=6)
        out = self.ctl.start(plan, probe, auto_stop_hours='5')
        self.assertIn('started g3f', out)
        cmd = self.world.started_cmd
        self.assertEqual(cmd[3:6], ['start', 'datagen', 'g3f'])
        self.assertEqual(cmd[cmd.index('--log') + 1], '/home/user/fork-data/g3f-job.log')
        self.assertTrue(cmd[-1].endswith('/parts/g3f/start_part.sh') and cmd[-2] == 'bash')
        params = (self.state / 'parts' / 'g3f' / 'params.sh').read_text()
        for line in ('NAME=g3f', 'SEED=20261111', 'THREADS=6', f'POSITIONS={477173594 - 30000000}', 'MODE=reuse',
                     'REUSE_DIR=/home/user/fork-data/gen3e', 'DIR=/home/user/fork-data/gen3f', 'NODES=20000',
                     'SAVE_PERCENT=50', 'UNSAVED_NODES=4000', 'CHECK_NODES=2000', 'ADJ_CP=700', 'ADJ_PLIES=8',
                     'WANT_NODES=14180299', 'WANT_SIGNATURE=4cf778ff753861f7', 'NET=s512r2'):
            self.assertIn(line + '\n', params)
        self.assertTrue((self.state / 'parts' / 'g3f' / 'start_part.sh').is_file())
        auto = self.ctl.read_state('g3f', 'autostop.json')
        self.assertEqual(auto['deadline'], self.clock[0] + 5 * 3600)
        self.assertEqual(self.spawned, ['g3f'])
        with self.assertRaises(generation_control.Refused):  # a second start of the same part
            self.ctl.start(plan, self.ctl.probe())

    def test_attach_to_a_running_part(self):
        self.world.add_running_g3e()
        run = self.ctl.running(self.ctl.probe())
        self.assertEqual((run['name'], run['phase'], run['games'], run['positions'], run['rate']),
                         ('g3e', 'generating', 318299, 29852407, 2439))
        self.assertEqual((run['seed'], run['threads'], run['target']), (20261110, 10, 477173594))
        self.assertAlmostEqual(run['progress'], 29852407 / 477173594)
        self.assertEqual(run['started'], P.iso_epoch('2026-11-06T10:45:12-0500'))
        part = self.ctl.read_state('g3e', 'part.json')
        self.assertTrue(part['attached'])
        self.assertEqual(part['cmdline'], G3E_CMDLINE)
        self.assertEqual(self.controls(), [])

    def test_stop_and_seal(self):
        self.world.add_running_g3e()
        self.ctl.running(self.ctl.probe())  # attached first, as the app does
        msg = self.ctl.stop_and_seal('g3e', 'the owner stops it')
        self.assertIn('sealing', msg)
        ctl_calls = [c[1] for c in self.controls()]
        stop = next(c for c in ctl_calls if 'stop' in c)
        self.assertEqual(stop[stop.index('--exec') + 1:], ['python3', '-I', self.ctl.jobctl_wsl, 'stop', 'g3e',
                                                           '--grace', '20'])
        self.assertLess(ctl_calls.index(stop), ctl_calls.index(self.world.seal_starts[0]))
        seal = self.world.seal_starts[0]
        self.assertEqual(seal[seal.index('start') + 1:seal.index('start') + 3], ['seal', 'seal-g3e'])
        req = self.ctl.read_state('g3e', 'seal-request.json')
        self.assertEqual(req['started'], 1793979916)
        self.assertEqual(req['seconds'], self.clock[0] - 1793979916)
        self.assertEqual(req['cmdline'], G3E_CMDLINE)
        self.assertEqual(req['reason'], 'the owner stops it')
        self.assertTrue(self.ctl.read_state('g3e', 'stop.json'))

    def test_failed_stop_seals_nothing(self):
        self.world.add_running_g3e()
        self.world.stop_rc = 1
        with self.assertRaises(generation_control.Refused) as e:
            self.ctl.stop_and_seal('g3e', 'x')
        self.assertIn('nothing was sealed', str(e.exception))
        self.world.stop_rc = 0
        self.world.stop_leaves = [462]  # jobctl said stopped, yet a process is left
        with self.assertRaises(generation_control.Refused):
            self.ctl.stop_and_seal('g3e', 'x')
        self.assertEqual(self.world.seal_starts, [])

    def test_watchdog_once(self):
        self.assertTrue(self.ctl.ensure_watchdog('g3e'))
        self.assertEqual(self.spawned, ['g3e'])
        self.state.mkdir(parents=True, exist_ok=True)
        (self.state / 'watchdog.json').write_text(json.dumps({'pid': 4242, 'part': 'g3e',
                                                              'heartbeat': self.clock[0] - 10}))
        self.assertFalse(self.ctl.ensure_watchdog('g3e'))
        (self.state / 'watchdog.json').write_text(json.dumps({'pid': 4242, 'part': 'g3e',
                                                              'heartbeat': self.clock[0] - 3600}))
        self.assertTrue(self.ctl.ensure_watchdog('g3e'))  # a stale heartbeat: a new watchdog
        self.assertEqual(self.spawned, ['g3e', 'g3e'])


class Watchdog(unittest.TestCase):
    def run_watch(self, states, deadline=None, fail_stop=False):
        clock = [1000.0]
        log = []

        def is_running(_):
            return states.pop(0) if states else True

        def stop(name, reason):
            log.append(('stop', name, reason))
            if fail_stop:
                raise generation_control.Refused('the stop failed')

        def sleep(s):
            clock[0] += s
        how = watchdog.watch('g3e', is_running, lambda n: deadline, stop, lambda on: log.append(('sleep', on)),
                             lambda r: None, now=lambda: clock[0], sleep=sleep, poll=30, unknown_limit=3)
        return how, log, clock[0]

    def test_ends_with_the_job_and_releases_sleep(self):
        how, log, _ = self.run_watch([True, True, False])
        self.assertEqual(how, 'ended')
        self.assertEqual(log, [('sleep', True), ('sleep', False)])

    def test_auto_stop_at_the_deadline(self):
        how, log, t = self.run_watch([], deadline={'deadline': 1100.0, 'hours': 0.5})
        self.assertEqual(how, 'auto-stopped')
        self.assertEqual(log[0], ('sleep', True))
        self.assertEqual(log[1][:2], ('stop', 'g3e'))
        self.assertIn('auto-stop after 0.5 hours', log[1][2])
        self.assertEqual(log[-1], ('sleep', False))
        self.assertGreaterEqual(t, 1100.0)
        self.assertLess(t, 1100.0 + 30)

    def test_failed_auto_stop_still_releases(self):
        how, log, _ = self.run_watch([], deadline={'deadline': 1000.0, 'hours': 1}, fail_stop=True)
        self.assertTrue(how.startswith('auto-stop failed'))
        self.assertEqual(log[-1], ('sleep', False))

    def test_unknown_state_keeps_blocking_then_gives_up(self):
        how, log, t = self.run_watch([None, None, None])
        self.assertEqual(how, 'unknown')
        self.assertEqual(log, [('sleep', True), ('sleep', False)])

    def test_release_on_error(self):
        log = []

        def boom(_):
            raise RuntimeError('x')
        with self.assertRaises(RuntimeError):
            watchdog.watch('g3e', boom, lambda n: None, None, lambda on: log.append(on), lambda r: None)
        self.assertEqual(log, [True, False])


# ================================================================ the seal

def game(result, moves, unsaved=0, close=True):
    head = bytes([1] + [0] * 29 + [result, 0])  # a 32-byte board record; byte 30 is the result
    recs = b''.join(struct.pack('<I', (5 << 16) | (0x100 + i)) for i in range(moves - unsaved))
    recs += b''.join(struct.pack('<I', (seal_part.UNSAVED << 16) | 0x200) for _ in range(unsaved))
    return head + recs + (struct.pack('<I', 0) if close else b'')


class Seal(unittest.TestCase):
    def test_complete_games(self):
        data = game(2, 3, unsaved=1) + game(0, 2) + game(1, 4, close=False)[:-2]
        end, games, positions, unsaved, res = seal_part.complete_games(data)
        self.assertEqual((end, games, positions, unsaved, res), (len(game(2, 3)) + len(game(0, 2)), 2, 5, 1,
                                                                  [1, 0, 1]))

    def test_real_g3d_copies(self):
        """Each shard of the sealed g3d copy holds exactly the games and positions its manifest lists (counts
        that verify_games.py confirmed). Runs only where the copies exist (this machine)."""
        d = config.expand('~/fork-data/kaggle/g3d')
        if not (d / 'g3d-w00.vf').exists():
            self.skipTest('g3d copies not on this machine')
        m = json.loads((REPO / 'data' / 'manifests' / 'g3d.json').read_text())
        for s in m['batches'][0][:2]:
            data = (d / s['file']).read_bytes()
            end, games, positions, unsaved, res = seal_part.complete_games(data)
            self.assertEqual((end, games, positions), (s['bytes'], s['games'], s['positions']), s['file'])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.src = t / 'wsl' / 'gen9b'
        self.src.mkdir(parents=True)
        (self.src / 'g9b-w00-0000.vf').write_bytes(game(2, 3) + game(1, 2) + game(0, 5, close=False))
        (self.src / 'g9b-w01-0000.vf').write_bytes(game(0, 4, unsaved=2))
        self.repo = t / 'repo'
        (self.repo / 'data' / 'manifests').mkdir(parents=True)
        shutil.copy(REPO / 'data' / 'manifests' / 'openings-lichess-2016-09.json', self.repo / 'data' / 'manifests')
        self.here = t / 'state'
        self.here.mkdir()
        self.req = {'name': 'g9b', 'reason': 'test reason', 'distro': 'Ubuntu', 'home': '/home/user',
                    'dir': '/home/user/fork-data/gen9b', 'src': str(self.src), 'cmdline': G3E_CMDLINE[:5] + [
                        '--threads', '2', '--seed', '7', '--positions', '1000'], 'settings': {}, 'seconds': 60.0,
                    'started': 1793979916, 'stopped': 1793979976, 'finished': False, 'copies': str(t / 'copies'),
                    'repo': str(self.repo), 'python': 'python', 'val_worker': 'last',
                    'manifests_out': str(self.repo / 'data' / 'manifests')}

    def tearDown(self):
        self.tmp.cleanup()

    def test_failed_verification_keeps_everything(self):
        uploads = []
        rc = seal_part.seal(self.req, self.here, wsl_version=fixture('fork-version.txt'), verify=lambda a: 1,
                            upload=uploads.append)
        self.assertEqual(rc, 1)
        res = json.loads((self.here / 'seal-result.json').read_text())
        self.assertEqual(res['state'], 'verify-failed')
        self.assertIn('nothing sealed', res['message'])
        self.assertEqual(uploads, [])
        out = Path(self.req['copies']) / 'g9b'
        self.assertEqual(sorted(f.name for f in out.iterdir()), ['g9b-w00.vf', 'g9b-w01-val.vf', 'g9b.json'])
        self.assertEqual(len(list(self.src.iterdir())), 2)  # the originals untouched
        # a second seal never overwrites the kept copy
        rc = seal_part.seal(self.req, self.here, wsl_version=fixture('fork-version.txt'), verify=lambda a: 0,
                            upload=uploads.append)
        self.assertEqual((rc, uploads), (1, []))
        self.assertEqual(json.loads((self.here / 'seal-result.json').read_text())['state'], 'failed')

    def test_real_steps_run(self):
        """The default verify and seal steps start their scripts (fakes here that record their arguments)."""
        tools = self.repo / 'tools' / 'datagen'
        tools.mkdir(parents=True)
        for script in ('verify_games.py', 'upload_batch.py'):
            (tools / script).write_text(
                'import sys, pathlib\n'
                f'pathlib.Path(r"{self.here}", "{script}.args").write_text("\\n".join(sys.argv[1:]))\n'
                f'print("ok: fake {script}")\n')
        self.req['python'] = sys.executable
        rc = seal_part.seal(self.req, self.here, wsl_version=fixture('fork-version.txt'))
        self.assertEqual(rc, 0, (self.here / 'seal-result.json').read_text())
        self.assertIn('--manifest', (self.here / 'verify_games.py.args').read_text().splitlines())
        self.assertEqual((self.here / 'upload_batch.py.args').read_text().splitlines()[0], 'seal')
        self.assertIn('ok: fake verify_games.py', (self.here / 'seal-steps.log').read_text())

    def test_sealed(self):
        seen = {}

        def verify(argv):
            seen['verify'] = [str(a) for a in argv]
            return 0

        def upload(argv):
            seen['upload'] = [str(a) for a in argv]
            return 0
        rc = seal_part.seal(self.req, self.here, wsl_version=fixture('fork-version.txt'), verify=verify,
                            upload=upload)
        self.assertEqual(rc, 0)
        out = Path(self.req['copies']) / 'g9b'
        run = json.loads((out / 'g9b.json').read_text())
        self.assertEqual((run['games'], run['positions'], run['positions_unsaved']), (3, 9, 2))
        self.assertEqual(run['results'], {'white': 1, 'draw': 1, 'black': 1})
        self.assertEqual(run['evaluator'], 'nnue (s512r2)')
        self.assertEqual((run['settings']['seed'], run['settings']['threads'], run['settings']['positions_target']),
                         (7, 2, 1000))
        self.assertEqual(run['settings']['openings_count'], 591871)
        self.assertEqual([s['file'] for s in run['shards']], ['g9b-w00.vf', 'g9b-w01-val.vf'])
        self.assertEqual((out / 'g9b-w00.vf').stat().st_size, len(game(2, 3)) + len(game(1, 2)))
        self.assertIn('--manifest', seen['verify'])
        u = seen['upload']
        self.assertEqual(u[3:5], ['seal', str(out / 'g9b.json')])
        part_end = u[u.index('--part-end') + 1]
        self.assertTrue(part_end.startswith('test reason; '))
        self.assertIn('every game verified', part_end)
        self.assertEqual(json.loads((self.here / 'seal-result.json').read_text())['state'], 'sealed')


# ================================================================ the read-only tabs change nothing

class FakeJobctl:
    @staticmethod
    def live(rec):
        return [1234] if rec.get('state') == 'running' else []


class ReadOnlyTabs(unittest.TestCase):
    def test_command_guard(self):
        ro = [['git', '-C', 'r', 'rev-parse', 'phase-4'], ['git', '-C', 'r', 'show', 'phase-4:CMakeLists.txt'],
              ['git', '-C', 'r', 'diff', '--quiet', 'a', 'b', '--', 'src'],
              ['gh', 'run', 'list', '--json', 'x'], ['C:/x/gh.exe', 'run', 'view', '1'],
              ['C:/v/kaggle.exe', 'kernels', 'status', 'o/k'], ['kaggle', 'kernels', 'list', '--mine'],
              ['kaggle', 'datasets', 'list', '--mine'],
              ['wsl.exe', '-d', 'Ubuntu', '--exec', '/home/user/fork-data/gen3e/fork', 'version']]
        for a in ro:
            self.assertTrue(R.is_read_only(a), a)
        self.assertTrue(R.is_read_only(['wsl.exe', '-d', 'U', '--exec', 'python3', '-I', '-', 'x'],
                                       R.PROBE.read_text(encoding='utf-8')))
        changing = [['git', '-C', 'r', 'push'], ['git', 'checkout', 'x'], ['git', 'diff', 'a', 'b'],
                    ['git', 'diff', '--quiet', '--output=f'], ['gh', 'run', 'rerun', '1'], ['gh', 'run', 'cancel', '1'],
                    ['gh', 'workflow', 'run', 'sprt'], ['gh', 'api', '-X', 'POST', 'x'], ['gh', 'run', 'view', '--web'],
                    ['kaggle', 'kernels', 'push'], ['kaggle', 'datasets', 'create'],
                    ['wsl.exe', '-d', 'U', '--exec', 'python3', '-I', 'jobctl.py', 'stop', 'g3e'],
                    ['wsl.exe', '-d', 'U', '--', 'python3', '-I', '-'],
                    ['wsl.exe', '-d', 'U', '--exec', '/x/../fork', 'version'],
                    ['python', '-I', 'jobctl.py', 'start', 'seal', 'x'], ['powershell.exe', '-c', 'x'], []]
        for a in changing:
            self.assertFalse(R.is_read_only(a), a)
        self.assertFalse(R.is_read_only(['wsl.exe', '-d', 'U', '--exec', 'python3', '-I', '-'], 'import os'))
        calls = []
        r = R.Runner(lambda *a: calls.append(a) or R.Result(0, '', ''))
        with self.assertRaises(PermissionError):
            r.read(['gh', 'run', 'cancel', '1'])
        self.assertEqual(calls, [])  # refused before any process
        self.assertFalse(hasattr(R.ReadOnly(r), 'control'))

    def test_guard_can_fail(self):
        """Fault injection: each kind of change the guard must catch is caught."""
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'x.txt'
            f.write_text('a')
            for change in (lambda: f.write_text('b'), lambda: open(f, 'a').close(), lambda: os.remove(f),
                           lambda: os.replace(f, f), lambda: (Path(tmp) / 'd').mkdir(),
                           lambda: os.open(f, os.O_WRONLY),
                           lambda: __import__('subprocess').Popen([sys.executable, '-c', 'pass'])):
                with guarded() as g:
                    with self.assertRaises(PermissionError):
                        change()
                self.assertTrue(g['violations'], change)
                self.assertEqual(f.read_text(), 'a')  # blocked, not just noticed
            with guarded() as g:
                f.read_text()
            self.assertEqual(g['violations'], [])
            before = tree_hashes(tmp)
            os.utime(f, (1, 1))
            self.assertNotEqual(tree_hashes(tmp), before)

    def world(self, t):
        repo = t / 'repo'
        for rel in ('docs/nets.md', 'docs/DESIGN.md', 'docs/history/phase-4/sprt-log.md'):
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REPO / rel, repo / rel)
        shutil.copytree(REPO / 'data' / 'manifests', repo / 'data' / 'manifests')
        jobs = t / 'jobs'
        (jobs / 'jobs').mkdir(parents=True)
        (jobs / 'locks').mkdir()
        shutil.copy(FIX / 'driver-threat.log', jobs / 'jobs' / 'sprt-threat.log')
        (jobs / 'jobs' / 'sprt-threat.json').write_text(json.dumps({
            'name': 'sprt-threat', 'type': 'github', 'id': 'a1', 'state': 'running', 'started':
            '2026-11-06T09:47:00-0500', 'log': str(jobs / 'jobs' / 'sprt-threat.log')}))
        meas = json.loads(fixture('win-job-measure.json'))
        shutil.copy(FIX / 'measure.log', jobs / 'jobs' / 'measure.log')
        meas['log'] = str(jobs / 'jobs' / 'measure.log')
        (jobs / 'jobs' / 'clock-damping.json').write_text(json.dumps(meas))
        (jobs / 'locks' / 'github.json').write_text(json.dumps({'name': 'sprt-threat', 'id': 'a1'}))
        copies = t / 'copies'
        (copies / 'g3d').mkdir(parents=True)
        (copies / 'g3d' / 'g3d-w00.vf').write_bytes(b'')
        gaunt = t / 'gauntlet' / 'run-41465146207'
        gaunt.mkdir(parents=True)
        shutil.copy(FIX / 'ordo.txt', gaunt / 'ordo.txt')
        train = t / 'train' / 'pp-out' / 'result' / 's512pp-s1'
        train.mkdir(parents=True)
        shutil.copy(FIX / 'run.json', train / 'run.json')
        state = t / 'state'
        (state / 'parts' / 'g3e').mkdir(parents=True)
        (state / 'parts' / 'g3e' / 'seal-result.json').write_text(json.dumps({'state': 'verifying', 'message': 'm'}))
        cfg = config.load({'repo': str(repo), 'windows_jobs': str(jobs), 'copies': str(copies),
                           'gauntlets': str(t / 'gauntlet'), 'training_out': str(t / 'train'), 'kaggle': 'kaggle'})
        return cfg, state

    def fake_cli(self, argv, timeout, input, cwd):
        a = [str(x) for x in argv]
        if 'run' in a and 'list' in a:
            return R.Result(0, fixture('gh-runs.json'), '')
        if a[1:3] == ['kernels', 'list']:
            return R.Result(0, fixture('kaggle-list.csv'), '')
        if a[1:3] == ['kernels', 'status']:
            return R.Result(0, fixture('kaggle-status.txt'), '')
        if a[1:3] == ['datasets', 'list']:
            return R.Result(0, 'ref,title\nowner/fork-g3d,fork-g3d\n', '')
        raise AssertionError(a)

    def test_collectors_and_tabs_write_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            cfg, state = self.world(t)
            w = World()
            w.add_running_g3e()
            probe = w.probe([cfg['wsl_data']])
            probe['folders'][cfg['wsl_data']] = {'exists': True, 'files': [{'name': 'gen3d', 'dir': True}]}
            runner = R.Runner(self.fake_cli)
            col = collectors.Collector(cfg, R.ReadOnly(runner), state=state, jobctl=FakeJobctl,
                                       cpu_times=iter([(100, 100), (150, 250)]).__next__,
                                       memory=lambda: {'load': 95, 'total': 16e9, 'free': 1e9},
                                       disk=lambda p: {'total': 5e11, 'free': 10e9}, gh='gh')
            before = tree_hashes(t)
            with guarded() as g:
                col.collect(probe)
                snap = col.collect(probe)
            self.assertEqual(g['violations'], [])
            self.assertEqual(tree_hashes(t), before)
            self.assertTrue(all(c[0] == 'read' for c in runner.calls))
            s = snap['current_sprt']
            self.assertEqual((s['name'], s['games'], s['elo'], s['llr'], s['job_live']),
                             ('threat-set-cheaper-vs-base', 4800, -5.57, -1.28, True))
            jobs = {j['name']: j for j in snap['jobs']}
            self.assertEqual(jobs['g3e']['supervisor'], 'WSL')
            self.assertEqual((jobs['clock-damping']['progress']['done'], jobs['clock-damping']['progress']['total']),
                             (0, 2000))
            self.assertEqual(snap['kaggle'], {k['ref']: 'complete' for k in P.kaggle_list(fixture('kaggle-list.csv'))})
            self.assertEqual(snap['training_runs'][0]['arch'], 's512pp')
            self.assertIn(3445.8, [x['rating'] for x in snap['networks']['gauntlets']])
            data = {d['run']: d for d in snap['data']}
            self.assertEqual(data['g3d']['saved'], 18242788 - 8314854)
            self.assertIn('WSL ~/fork-data/gen3d', data['g3d']['where'])
            self.assertIn('Kaggle owner/fork-g3d', data['g3d']['where'])
            self.assertIn('Low disk: C: has less than 20 GB free', snap['warnings'])
            self.assertTrue(any(w.startswith('Memory pressure: Windows') for w in snap['warnings']))
            self.assertEqual(snap['machine']['cpu'], 100.0 * 150 / 200)
            self.assertEqual(snap['seals'], {'g3e': 'verifying'})
            self.render_tabs(snap)

    def render_tabs(self, snap):
        try:
            import tkinter as tk
            import app
            root = tk.Tk()
        except Exception as e:  # noqa: BLE001
            self.skipTest(f'no Tk display: {e}')
        try:
            root.withdraw()
            opened = []
            for title, cls in app.READ_ONLY_TABS:
                params = list(inspect.signature(cls.__init__).parameters)
                self.assertEqual(params, ['self', 'parent', 'open_url'], title)
                src = inspect.getsource(cls)
                for word in ('ctl', 'runner', '.control(', 'GenerationControl', 'generation_control'):
                    self.assertNotIn(word, src, f'{title} mentions {word}')
                tab = cls(root, opened.append)
                root.update_idletasks()
                with guarded() as g:
                    tab.render(snap)
                    root.update()
                self.assertEqual(g['violations'], [], title)
            self.assertEqual(opened, [])
        finally:
            root.destroy()


# ================================================================ notifications

class Notifications(unittest.TestCase):
    def base(self):
        return {'sprts': [{'name': 's', 'finished': None}], 'kaggle': {'o/k': 'running'},
                'jobs': [{'supervisor': 'WSL', 'name': 'g3e', 'id': '1', 'type': 'datagen', 'raw_state': 'running',
                          'processes': [1]},
                         {'supervisor': 'Windows', 'name': 'm', 'id': '2', 'type': 'measure',
                          'raw_state': 'running', 'processes': [2]},
                         {'supervisor': 'Windows', 'name': 'q', 'id': '3', 'type': 'github',
                          'raw_state': 'running', 'processes': [3]}],
                'seals': {}, 'warnings': [], 'expected_stops': []}

    def test_events(self):
        prev = self.base()
        self.assertEqual(notify.events(None, prev), [])
        self.assertEqual(notify.events(prev, self.base()), [])
        cur = self.base()
        cur['sprts'] = [{'name': 's', 'finished': 'decided after stage 3', 'elo': 5.1, 'elo_err': 3.0, 'llr': 2.95,
                         'llr_lo': -2.94, 'llr_hi': 2.94, 'elo0': 0.0, 'elo1': 3.0, 'verdict': 'H1 accepted'}]
        cur['kaggle'] = {'o/k': 'complete'}
        cur['jobs'][0].update(raw_state='stopped', processes=[])
        cur['jobs'][1].update(raw_state='ended', exit_code=1, processes=[])
        cur['jobs'][2].update(processes=[])
        cur['seals'] = {'g3e': 'verify-failed'}
        cur['warnings'] = ['Low disk: C: has less than 20 GB free']
        titles = [t for t, _ in notify.events(prev, cur)]
        self.assertEqual(titles, ['SPRT s', 'Kaggle session finished', 'Data generation stopped', 'Job failed',
                                  'Job stopped unexpectedly', 'Seal of g3e: verify-failed', 'Fork machine warning'])
        cur['expected_stops'] = ['g3e']  # stopped from the app: no alarm
        self.assertNotIn('Data generation stopped', [t for t, _ in notify.events(prev, cur)])
        again = notify.events(cur, cur)
        self.assertEqual(again, [])  # each warning and decision once

    def test_toast_command(self):
        seen = {}

        def popen(argv, **kw):
            seen['argv'], seen['env'] = argv, kw['env']
        if os.name != 'nt':
            self.skipTest('Windows only')
        self.assertTrue(notify.toast('T', 'text', popen=popen))
        self.assertEqual(seen['argv'][0], 'powershell.exe')
        self.assertEqual((seen['env']['FORK_CC_TITLE'], seen['env']['FORK_CC_TEXT']), ('T', 'text'))


if __name__ == '__main__':
    unittest.main()
