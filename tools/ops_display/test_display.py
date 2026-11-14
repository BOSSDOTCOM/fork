# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the display above its readers: discovery, the lane view, alerts, health on missing and corrupt
files, the read-only guarantee (an audit hook that fails on any write or process start), the allow-listed
commands, the network polls with a fake tool, and the local server.
Run: python -I -B -m unittest discover -s tools/ops_display -p "test_*.py"
"""
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import collect  # noqa: E402
import fsread  # noqa: E402
import machine  # noqa: E402
import net  # noqa: E402
import procs  # noqa: E402
import readers as R  # noqa: E402
import rules  # noqa: E402
import serve  # noqa: E402

FIX = os.path.join(HERE, 'fixtures')
NOW = R.est_stamp('2026-11-14 01:30 PM EST')

# ---------------------------------------------------------------- the read-only guard
# One process-wide audit hook (it cannot be removed once installed). While armed it raises on any event
# that writes, deletes, renames, creates a folder or starts a process.
_ARMED = threading.local()
_WRITE_EVENTS = {'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'os.truncate', 'os.link', 'os.symlink', 'os.chmod',
                 'shutil.rmtree', 'shutil.move', 'shutil.copyfile', 'subprocess.Popen', 'os.system', 'os.startfile',
                 'os.exec', 'os.spawn', 'os.posix_spawn', 'tempfile.mkstemp', 'tempfile.mkdtemp'}


def _audit(event, args):
    if not getattr(_ARMED, 'on', False):
        return
    if event == 'open':
        mode, flags = args[1], args[2] if len(args) > 2 else 0
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or \
                  (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if writing:
            raise AssertionError(f'the display opened a file for writing: {args[0]!r} mode {mode!r}')
    elif event in _WRITE_EVENTS:
        raise AssertionError(f'the display did something that is not reading: {event} {args[:1]!r}')


sys.addaudithook(_audit)


class guarded:
    def __enter__(self):
        _ARMED.on = True

    def __exit__(self, *a):
        _ARMED.on = False


def tree(root):
    out = {}
    for d, _, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            s = os.stat(p)
            out[p] = (s.st_size, s.st_mtime_ns)
    return out


def fx(name):
    with open(os.path.join(FIX, name), encoding='utf-8') as f:
        return f.read()


class Probes:
    """Machine probes with fixed answers; `dead` names the jobs whose processes are gone."""

    def __init__(self):
        self.dead, self.t = set(), [1000, 1000]

    def cpu_times(self):
        self.t = [self.t[0] + 700, self.t[1] + 300]
        return tuple(self.t)

    def memory(self):
        return {'total': 16 * 2 ** 30, 'avail': 3 * 2 ** 30, 'commit': 71.5}

    def processors(self):
        return 12

    def job_live(self, rec):
        return rec['name'] not in self.dead


class World:
    """A temporary home with the pipeline's files, built from the fixtures."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix='ops-display-test-')
        self.paths = collect.Paths(self.root, cc_state=os.path.join(self.root, 'cc'), wsl_home=os.path.join(self.root, 'wsl'))
        self.probes = Probes()
        p = self.paths
        for d in (os.path.join(p.jobs, 'jobs'), os.path.join(p.jobs, 'locks'), os.path.join(p.jobs, 'gcp'), p.state, p.sprt,
                  os.path.join(p.repo, 'data', 'manifests'), os.path.join(p.repo, 'docs'), os.path.join(p.repo, '.git', 'refs', 'heads'),
                  os.path.join(p.repo, 'tools', 'gauntlet'), os.path.join(p.cc, 'parts', 'g4c'), os.path.join(p.gauntlet, 'run-1')):
            os.makedirs(d)
        self.lane('github', 'night-queue', 'items', 'chain.sh')
        self.lane('github2', 'night-queue-b', 'items-b', 'chain-b.sh')
        for kind, name in (('gcpwatch', 'gcp-watch2'), ('watch', 'memwatch3'), ('freezewatch', 'freezewatch'), ('wslcache', 'wsl-cache-drop2')):
            self.job(name, kind)
            self.put(os.path.join(p.jobs, 'locks', kind + '.json'), json.dumps({'name': name, 'id': 'i-' + name, 'started': '2026-11-11T14:12:35-0500'}))
        # lane A: a capped test done, an SPRT in flight after 5 merged stages, one more waiting
        self.item('items', '10-f12-pin-see-stc', done=True)
        self.item('items', '20-d15-shallow-skip-stc', log='2026-11-14 01:00 PM EST x\n' + self.running_log())
        self.item('items', '30-b6-null-verify-nonreg')
        self.sprt('f12-pin-see-stc', fx('driver-capped.log'), 'capped', fx('design.json'))
        self.sprt('d15-shallow-skip-stc', self.running_log(), None, fx('design.json'))
        # lane B: a screen in flight, a gated item, an item waiting on its retry timer
        self.item('items-b', '15-r8c-cc1-vs-r8brft1', log=self.screen_log())
        self.sprt('r8c-fn-r8cc1-vs-r8brft1', self.screen_log(), None, None)
        self.item('items-b', '88a-i59-ds-stc', log='gated: waits for state/gate-e1.done\n')
        self.item('items-b', '89a-i42-cont-inputs-stc')
        self.put(os.path.join(p.state, '89a-i42-cont-inputs-stc.retry_at'), str(int(NOW + 900)))
        self.put(os.path.join(p.state, '89a-i42-cont-inputs-stc.failures'), '1\n')
        self.put(os.path.join(p.jobs, 'ledger.jsonl'),
                 json.dumps({'at': '2026-11-14T13:12:30-0500', 'sprt': 'd15-shallow-skip-stc', 'stage': 5, 'run_id': 777}) + '\n')
        self.put(os.path.join(p.jobs, 'events.jsonl'), fx('events.jsonl'))
        self.put(os.path.join(p.jobs, 'tries.jsonl'), fx('tries.jsonl'))
        self.put(os.path.join(p.jobs, 'gcp', 'status.json'), fx('gcp-status.json'))
        self.put(os.path.join(p.jobs, 'gcp', 'wanted.json'), '{"wanted": "running"}')
        self.put(os.path.join(p.jobs, 'gcp.json'), json.dumps({'project': 'project-secret-1', 'billing_account': '000000-AAAAAA-BBBBBB',
                 'ssh_key': 'C:/Users/someone/.ssh/secret-key', 'usd_per_hour_running': 0.119, 'usd_per_hour_stopped': 0.0045, 'egress_usd_per_gib': 0.12}))
        self.put(os.path.join(p.jobs, 'gcp', 'egress.jsonl'), fx('egress.jsonl'))
        self.put(os.path.join(p.cc, 'watchdog.json'), fx('watchdog.json'))
        self.put(os.path.join(p.cc, 'parts', 'g4c', 'part.json'), fx('part.json'))
        self.put(os.path.join(p.cc, 'parts', 'g4c', 'seal-result.json'), fx('seal-result.json'))
        for src, dst in (('manifest-part.json', 'g4c.json'), ('manifest-cut.json', 'ld-d20c50.json'), ('manifest-snapshot.json', 'g3s3.json')):
            self.put(os.path.join(p.repo, 'data', 'manifests', dst), fx(src))
        self.put(os.path.join(p.repo, 'CMakeLists.txt'), 'set(FORK_NET "${CMAKE_SOURCE_DIR}/nets/r8brft1.fnet" CACHE FILEPATH "x")\n')
        self.put(os.path.join(p.repo, 'docs', 'nets.md'), fx('nets.md'))
        self.put(os.path.join(p.repo, 'docs', 'ideas.md'), fx('ideas.md'))
        self.put(os.path.join(p.repo, 'tools', 'gauntlet', 'transfer.json'), fx('transfer.json'))
        self.put(os.path.join(p.repo, '.git', 'HEAD'), 'ref: refs/heads/phase-4\n')
        self.put(os.path.join(p.repo, '.git', 'refs', 'heads', 'phase-4'), '5dc29ea0000000000000000000000000000000ab\n')
        self.put(os.path.join(p.gauntlet, 'run-1', 'ordo.txt'), fx('ordo.txt'))
        self.put(os.path.join(p.gauntlet, 'run-1', 'meta.txt'), fx('gauntlet-meta.txt'))
        self.put(os.path.join(p.gauntlet, 'run-1', 'summary.md'), fx('gauntlet-summary.md'))
        gates = os.path.join(p.data, '8c', 'a1-gates')
        for netname in ('r8cc1', 'r8cc2', 'r8ceplo1'):
            self.put(os.path.join(gates, netname, 'gates.json'), fx('gates.json'))
        self.put(os.path.join(p.data, '8c', 'a1-state', 'bakes.txt'), fx('bakes.txt'))
        self.put(os.path.join(p.data, '8c', 'a1-state', 'fetch-main.log'), fx('fetch-main.log'))
        self.put(os.path.join(p.night, 'freezewatch.log'), fx('freezewatch.log'))
        self.put(os.path.join(p.jobs, 'jobs', 'wsl-cache-drop2.log'), fx('wslcache.log'))
        self.put(os.path.join(p.jobs, 'jobs', 'memwatch3.log'), fx('memwatch.log'))

    def running_log(self):
        """The capped fixture's first five stages, then stage 5 dispatched: an SPRT in flight."""
        lines = fx('driver-capped.log').replace('f12-pin-see-stc', 'd15-shallow-skip-stc').splitlines()
        cut = next(i for i, l in enumerate(lines) if 'stage 5:' in l and 'dispatched' in l)
        return '\n'.join(lines[:cut]) + '\n2026-11-14 18:12 UTC d15-shallow-skip-stc: stage 5: run 777 dispatched (ledger)\n'

    def screen_log(self):
        return ('2026-11-14 17:16 UTC r8c-fn-r8cc1-vs-r8brft1: base b49d6f5dece2c8c434b24aef03c1208fa678b316, test a71dd2daf4aa854346ab9f7e73c42cc7a321c4ca, '
                'bounds [0, 5], stages 0 to 0, ref phase-4\n2026-11-14 18:19 UTC r8c-fn-r8cc1-vs-r8brft1: stage 0: run 888 dispatched (ledger)\n')

    def put(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)

    def job(self, name, kind, script=None, state='running'):
        rec = {'name': name, 'type': kind, 'state': state, 'id': 'i-' + name, 'pid': 4242, 'keeper': 4243,
               'started': '2026-11-10T21:29:35-0500', 'command': ['bash', script or 'C:/Users/someone/fork-jobs/x.sh'],
               'log': 'C:\\Users\\someone\\fork-jobs\\jobs\\' + name + '.log'}
        if state == 'ended':
            rec.update(ended='2026-11-14T13:20:00-0500', exit_code=1)
        self.put(os.path.join(self.paths.jobs, 'jobs', name + '.json'), json.dumps(rec))

    def lane(self, lock, job, folder, script):
        path = os.path.join(self.paths.night, script)
        self.put(path, f'#!/usr/bin/env bash\nN=/c/Users/someone/fork-jobs/night\nI=$N/{folder}\n')
        os.makedirs(os.path.join(self.paths.night, folder), exist_ok=True)
        self.job(job, lock, path)
        self.put(os.path.join(self.paths.jobs, 'locks', lock + '.json'), json.dumps({'name': job, 'id': 'i-' + job, 'started': '2026-11-10T21:29:35-0500'}))

    def item(self, folder, key, done=False, log=None):
        self.put(os.path.join(self.paths.night, folder, key + '.sh'), '#!/usr/bin/env bash\n# A test item for the display.\nexit 0\n')
        if done:
            self.put(os.path.join(self.paths.state, key + '.done'), '')
        if log is not None:
            self.put(os.path.join(self.paths.night, key + '.log'), log)

    def sprt(self, name, driver, verdict, design):
        d = os.path.join(self.paths.sprt, name)
        self.put(os.path.join(d, 'driver.log'), driver)
        if verdict:
            self.put(os.path.join(d, 'verdict'), verdict + '\n')
        if design:
            self.put(os.path.join(d, 'design.json'), design)
        for f in os.listdir(d):
            os.utime(os.path.join(d, f), (NOW - 600, NOW - 600))

    def collector(self, now=NOW):
        self.clock = [now]
        c = collect.Collector(self.paths, clock=lambda: self.clock[0], probes=self.probes,
                              git_log=lambda repo, branch: 'a86ddcc 2026-11-13 Search: root reductions adopted on their STC and LTC passes\n')
        c.settle = 0            # the test's files are written just before they are read
        return c

    def snap(self, c):
        s = c.tick()
        s['alerts'] = rules.alerts(s)
        s['situation'] = rules.situation(s)
        return s

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class WithWorld(unittest.TestCase):
    def setUp(self):
        self.w = World()
        self.addCleanup(self.w.close)


class Discovery(WithWorld):
    def test_lanes_items_and_states_are_found_from_the_files(self):
        s = self.w.snap(self.w.collector())
        self.assertEqual([(l['id'], l['lock'], l['folder'], l['state']) for l in s['lanes']],
                         [('A', 'github', 'items', 'testing'), ('B', 'github2', 'items-b', 'testing')])
        a, b = s['lanes']
        self.assertEqual((a['item']['key'], a['sprt']['name'], a['pending']), ('20-d15-shallow-skip-stc', 'd15-shallow-skip-stc', 1))
        self.assertEqual(b['item']['key'], '15-r8c-cc1-vs-r8brft1')
        q = {i['key']: i for i in s['queue']}
        self.assertEqual(sorted(q), ['30-b6-null-verify-nonreg', '88a-i59-ds-stc', '89a-i42-cont-inputs-stc'])   # the done item is gone
        self.assertEqual((q['88a-i59-ds-stc']['state'], q['89a-i42-cont-inputs-stc']['state'], q['89a-i42-cont-inputs-stc']['failures']),
                         ('gated', 'retry', 1))
        self.assertEqual(q['89a-i42-cont-inputs-stc']['title'], 'Idea 42 cont inputs')

    def test_a_new_lane_and_a_new_item_appear_without_a_code_change(self):
        c = self.w.collector()
        self.w.snap(c)
        self.w.lane('github3', 'night-queue-c', 'items-c', 'chain-c.sh')
        self.w.item('items-c', '05-brand-new-kind-ltc')
        self.w.item('items', '25-another-idea-stc')
        self.w.clock[0] += 10
        s = self.w.snap(c)
        self.assertEqual([l['id'] for l in s['lanes']], ['A', 'B', 'C'])
        self.assertEqual(s['lanes'][2]['item']['key'], '05-brand-new-kind-ltc')
        self.assertIn('25-another-idea-stc', [i['key'] for i in s['queue']])
        self.assertIn('lane-C', [n['id'] for n in s['situation']['nodes']])

    def test_retrains_parts_and_labellers_are_discovered(self):
        s = self.w.snap(self.w.collector())
        r = s['training']['retrains'][0]
        self.assertEqual((r['title'], r['nets']), ('8c a1', 3))
        self.assertEqual(sorted(a['arm'] for a in r['arms']), ['c', 'eplo'])
        c = next(a for a in r['arms'] if a['arm'] == 'c')
        self.assertEqual((c['cells']['gates'], c['cells']['bake'], c['cells']['default']), ('done', 'done', 'run'))   # its screen against the default is in flight
        self.assertEqual(s['training']['quota']['left'], 22.86)
        self.assertEqual(s['data']['labellers'], [{'name': 'r8brft1', 'positions': 229475885}])   # the cut and the snapshot are not counted
        self.assertEqual((s['data']['pc']['state'], s['data']['pc']['part'], s['data']['pc']['seal']), ('idle', 'g4c', 'sealed'))
        self.assertEqual(s['data']['vm']['running'], 'filler-g4')
        self.assertEqual((s['overview']['net'], s['overview']['commit'], s['overview']['latest']['rating']), ('r8brft1', '5dc29ea', 3553.7))
        self.assertEqual(s['overview']['adoptions']['week'], 1)

    def test_a_running_part_is_read_through_the_gated_share(self):
        w = self.w
        w.put(os.path.join(w.paths.cc, 'watchdog.json'), json.dumps({'pid': 1, 'part': 'g4c', 'started': NOW - 5000, 'heartbeat': NOW - 20,
                                                                    'running': True, 'sleep_blocked': True}))
        w.put(os.path.join(w.paths.wsl_home, 'fork-data', 'gen4c', 'g4c.log'), fx('datagen.log'))
        s = w.snap(w.collector())
        self.assertEqual((s['data']['pc']['state'], s['data']['pc']['positions']), ('active', 29852407))
        self.assertGreater(s['data']['pc']['rate'], 8_000_000)
        night = R.est_stamp('2026-11-14 01:45 AM EST')                 # the window in which WSL is restarted
        w.put(os.path.join(w.paths.cc, 'watchdog.json'), json.dumps({'pid': 1, 'part': 'g4c', 'heartbeat': night - 20, 'running': True}))
        s = w.snap(w.collector(night))
        self.assertEqual((s['data']['pc']['state'], s['data']['pc']['positions']), ('active', None))
        self.assertIn('1:20', s['data']['pc']['note'])


class LaneMarker(WithWorld):
    def marker(self, lane, state, item='', drivers='', source='watcher', age=5):
        self.w.put(os.path.join(self.w.paths.state, f'current-{lane}.txt'),
                   f'lane={lane}\nstate={state}\nitem={item}\ndrivers={drivers}\nsource={source}\nupdated_epoch={int(NOW - age)}\n')

    def test_the_lanes_marker_decides_the_current_item(self):
        w = self.w
        self.marker('A', 'running', '30-b6-null-verify-nonreg')          # not the first item in name order
        s = w.snap(w.collector())
        a = s['lanes'][0]
        self.assertEqual((a['item']['key'], a['marker']), ('30-b6-null-verify-nonreg', 'watcher'))
        self.assertIn('20-d15-shallow-skip-stc', [q['key'] for q in s['queue']])
        self.assertEqual(s['lanes'][1]['marker'], None)                 # lane B has no marker: inferred as before
        self.assertEqual(s['lanes'][1]['item']['key'], '15-r8c-cc1-vs-r8brft1')

    def test_an_idle_lane_with_a_driver_still_running_shows_that_test(self):
        w = self.w
        self.marker('A', 'idle', '', 'd15-shallow-skip-stc')
        a = w.snap(w.collector())['lanes'][0]
        self.assertEqual((a['item']['key'], a['sprt']['name'], a['state']), ('20-d15-shallow-skip-stc', 'd15-shallow-skip-stc', 'testing'))
        self.marker('A', 'idle', '', '')
        s = w.snap(w.collector())
        self.assertEqual((s['lanes'][0]['item'], s['lanes'][0]['state']), (None, 'idle'))
        self.assertIn('lane-idle:A', [x['id'] for x in s['alerts']])

    def test_a_stale_watcher_marker_or_a_corrupt_one_falls_back_to_inference(self):
        w = self.w
        self.marker('A', 'running', '30-b6-null-verify-nonreg', age=600)   # the watcher stopped writing 10 minutes ago
        self.assertEqual(w.snap(w.collector())['lanes'][0]['item']['key'], '20-d15-shallow-skip-stc')
        w.put(os.path.join(w.paths.state, 'current-A.txt'), '\x00 half a mark')
        a = w.snap(w.collector())['lanes'][0]
        self.assertEqual((a['item']['key'], a['marker']), ('20-d15-shallow-skip-stc', None))
        self.marker('A', 'running', '30-b6-null-verify-nonreg', source='chain', age=7200)   # the chain writes once, at the item's start
        self.assertEqual(w.snap(w.collector())['lanes'][0]['item']['key'], '30-b6-null-verify-nonreg')


class LaneView(WithWorld):
    def test_live_figures_countdown_and_latest_end(self):
        s = self.w.snap(self.w.collector())
        v = s['lanes'][0]['sprt']
        self.assertEqual((v['klass'], v['is_sprt'], v['stage_no'], v['stage_count'], v['cap_games']), ('stc', True, 6, 8, 12800))
        self.assertEqual((v['last']['elo'], v['last']['elo_err'], v['last']['games'], v['last']['llr'], v['lo'], v['hi']),
                         (1.30, 4.37, 8000, -0.29, -1.56, 2.77))
        self.assertEqual(len(v['stages']), 5)
        self.assertEqual(v['typical_min'], 18.0)                       # the median of the finished stages of the same kind
        self.assertEqual(v['flight']['dispatched'], R.iso('2026-11-14T13:12:30-0500'))   # the ledger's time, to the second
        self.assertEqual(v['flight']['eta'], v['flight']['dispatched'] + 18 * 60)
        self.assertEqual(v['flight']['latest'], v['flight']['eta'] + 2 * 18 * 60)
        screen = s['lanes'][1]['sprt']
        self.assertEqual((screen['klass'], screen['is_sprt'], screen['last'], screen['flight']['eta']), ('screen', False, None, None))   # no history of screens: no guess

    def test_preliminary_result_combines_shard_progress_with_finished_stages(self):
        c = self.w.collector()
        self.w.snap(c)
        c.net['runs'] = {777: {'shards': {'total': 16, 'done': 4, 'running': 12, 'queued': 0, 'failed': 0},
                               'progress': {'ptnml': [3, 40, 80, 45, 4], 'games': 344, 'shards': 9, 'at': NOW - 30}}}
        self.w.clock[0] += 6
        v = self.w.snap(c)['lanes'][0]['sprt']
        self.assertEqual(v['shards']['done'], 4)
        self.assertEqual(v['prelim']['games'], 8000 + 344)
        self.assertEqual((v['prelim']['stage_games'], v['prelim']['shards']), (344, 9))
        self.assertIsNotNone(v['prelim']['elo_err'])
        self.assertEqual(v['last']['games'], 8000)                     # the stage-end figure is untouched
        c.net['runs'] = {777: {'shards': None, 'progress': None}}      # no progress artifacts: stage-end results only
        self.w.clock[0] += 6
        self.assertIsNone(self.w.snap(c)['lanes'][0]['sprt']['prelim'])

    def test_wanted_runs_are_the_lanes_live_runs(self):
        c = self.w.collector()
        self.w.snap(c)
        self.assertEqual(sorted(c.wanted['runs']), [777, 888])


class Alerts(WithWorld):
    def ids(self, s, tier=None):
        return [a['id'] for a in s['alerts'] if tier is None or a['tier'] == tier]

    def test_a_healthy_world_has_no_critical_alert(self):
        s = self.w.snap(self.w.collector())
        self.assertEqual(self.ids(s, 'critical'), [])
        self.assertIn('pc-idle:g4c', self.ids(s, 'attention'))
        self.assertIn('item-failures:89a-i42-cont-inputs-stc', self.ids(s, 'attention'))
        self.assertEqual(s['health']['failing'], {})

    def test_a_dead_lane_a_stopped_run_and_a_missing_watcher_are_critical(self):
        w = self.w
        w.probes.dead.add('night-queue')
        w.probes.dead.add('freezewatch')
        w.sprt('r8c-fn-r8cc1-vs-r8brft1', w.screen_log() + "2026-11-14 18:25 UTC r8c-fn-r8cc1-vs-r8brft1: stage 0: run 888 ended 'failure'; stopping\n", None, None)
        s = w.snap(w.collector())
        crit = self.ids(s, 'critical')
        self.assertIn('lane-down:A', crit)
        self.assertIn('lane-stopped:B:r8c-fn-r8cc1-vs-r8brft1', crit)
        self.assertIn('watcher:freezewatch', crit)
        self.assertEqual([l['state'] for l in s['lanes']], ['down', 'stopped'])
        self.assertEqual(s['alerts'][0]['tier'], 'critical')            # critical first

    def test_a_failed_job_is_critical_until_a_later_run_passes(self):
        w = self.w
        w.job('r8c-upload', 'upload', state='ended')
        s = w.snap(w.collector())
        self.assertTrue(any(i.startswith('job-failed:r8c-upload') for i in self.ids(s, 'critical')))
        w.put(os.path.join(w.paths.jobs, 'jobs', 'r8c-upload2.json'), json.dumps({'name': 'r8c-upload2', 'type': 'upload', 'state': 'ended',
              'id': 'x', 'started': '2026-11-14T13:21:00-0500', 'ended': '2026-11-14T13:25:00-0500', 'exit_code': 0}))
        s = w.snap(w.collector())
        self.assertTrue(any(i.startswith('job-failed:r8c-upload') for i in self.ids(s, 'info')))
        self.assertEqual(self.ids(s, 'critical'), [])

    def test_vm_and_memory_alerts(self):
        w = self.w
        st = json.loads(fx('gcp-status.json'))
        st['vm']['status'] = 'TERMINATED'
        w.put(os.path.join(w.paths.jobs, 'gcp', 'status.json'), json.dumps(st))
        os.utime(os.path.join(w.paths.jobs, 'gcp', 'status.json'), (NOW - 1500, NOW - 1500))
        w.probes.memory = lambda: {'total': 16 * 2 ** 30, 'avail': 0.8 * 2 ** 30, 'commit': 93.0}
        s = w.snap(w.collector())
        self.assertIn('vm-state', self.ids(s, 'critical'))
        self.assertIn('vm-stale', self.ids(s, 'critical'))
        self.assertIn('commit', self.ids(s, 'attention'))

    def test_rules_file(self):
        self.assertEqual(rules.load('')['commit_percent'], 90)
        self.assertEqual(rules.load('{"commit_percent": 95, "my_new_rule": 1}')['commit_percent'], 95)
        with self.assertRaises(ValueError):
            rules.load('[1, 2]')
        with self.assertRaises(ValueError):
            rules.load('{half')


class MissingAndCorrupt(WithWorld):
    def test_an_empty_home_gives_a_snapshot_not_an_error(self):
        empty = tempfile.mkdtemp(prefix='ops-display-empty-')
        self.addCleanup(shutil.rmtree, empty, True)
        c = collect.Collector(collect.Paths(empty, cc_state=os.path.join(empty, 'cc'), wsl_home=os.path.join(empty, 'wsl')),
                              clock=lambda: NOW, probes=Probes())
        c.settle = 0
        s = c.tick()
        s['alerts'] = rules.alerts(s)
        s['situation'] = rules.situation(s)
        self.assertEqual(c.errors, {})
        self.assertEqual((s['lanes'], s['queue'], s['verdicts']), ([], [], []))
        self.assertIn('watcher:gcpwatch', [a['id'] for a in s['alerts']])
        self.assertTrue(s['situation']['text'])
        json.dumps(s, allow_nan=False)

    def test_a_half_written_file_keeps_the_last_good_value_and_raises_an_alert(self):
        w = self.w
        c = w.collector()
        good = w.snap(c)
        path = os.path.join(w.paths.jobs, 'gcp', 'status.json')
        w.put(path, fx('gcp-status.json')[:300])                       # cut mid-write
        w.clock[0] += 11
        s = w.snap(c)
        self.assertEqual(s['data']['vm']['running'], good['data']['vm']['running'])
        failing = [k for k in s['health']['failing'] if k.endswith('gcp/status.json')]
        self.assertEqual(len(failing), 1)
        self.assertTrue(any(a['id'] == 'source:' + failing[0] for a in s['alerts']))
        w.put(path, fx('gcp-status.json'))                             # written whole again: the alert clears
        w.clock[0] += 11
        s = w.snap(c)
        self.assertEqual(s['health']['failing'], {})

    def test_a_changed_format_is_reported_by_name(self):
        w = self.w
        w.put(os.path.join(w.paths.data, '8c', 'a1-gates', 'r8cc1', 'gates.json'), '{"scale": 89, "renamed_field": false}')
        w.put(os.path.join(w.paths.repo, 'tools', 'gauntlet', 'transfer.json'), '{"adopted": "moved elsewhere"}')
        s = w.snap(w.collector())
        keys = ' '.join(s['health']['failing'])
        self.assertIn('a1-gates/r8cc1/gates.json', keys)
        self.assertIn('gauntlet/transfer.json', keys)
        self.assertEqual(sum(1 for a in s['alerts'] if a['id'].startswith('source:')), 2)

    def test_binary_garbage_and_truncation_everywhere(self):
        w = self.w
        before = [p for p in tree(w.root)]
        for i, p in enumerate(before):
            data = fsread.read_bytes(p)
            with open(p, 'wb') as f:
                f.write(b'\x00\xff\xfe garbage \x01' * 20 if i % 3 == 0 else data[:len(data) // 2] if i % 3 == 1 else b'')
        c = w.collector()
        s = w.snap(c)
        self.assertEqual(c.errors, {})                                 # no section fell over
        json.dumps(s, allow_nan=False)

    def test_a_file_that_vanishes_between_listing_and_reading(self):
        w = self.w
        c = w.collector()
        w.snap(c)
        shutil.rmtree(os.path.join(w.paths.sprt, 'd15-shallow-skip-stc'))
        os.remove(os.path.join(w.paths.jobs, 'jobs', 'night-queue-b.json'))
        w.clock[0] += 40
        s = w.snap(c)
        self.assertEqual(c.errors, {})
        self.assertEqual(len(s['lanes']), 2)


class ReadOnly(WithWorld):
    def test_the_guard_itself_fails_on_a_write(self):
        with self.assertRaises(AssertionError), guarded():
            open(os.path.join(self.w.root, 'x.txt'), 'w')
        _ARMED.on = False
        with self.assertRaises(AssertionError), guarded():
            os.mkdir(os.path.join(self.w.root, 'newdir'))
        _ARMED.on = False

    def test_collecting_and_judging_write_nothing_and_start_nothing(self):
        w = self.w
        c = w.collector()
        before = tree(w.root)
        with guarded():
            for _ in range(4):
                s = c.tick()
                s['alerts'] = rules.alerts(s)
                s['situation'] = rules.situation(s)
                fsread.scrub(json.dumps(s, default=str))
                w.clock[0] += 61
        self.assertEqual(tree(w.root), before)

    def test_the_display_refresh_writes_nothing(self):
        d = serve.Display(self.w.paths, clock=lambda: NOW)
        d.collector.probes = self.w.probes
        d.collector.git_log = None
        d.collector.settle = 0
        before = tree(self.w.root), tree(HERE)
        with guarded():
            d.refresh()
            d.refresh()
        self.assertEqual((tree(self.w.root), tree(HERE)), before)
        self.assertIn(b'"lanes"', d.body)

    @unittest.skipUnless(os.name == 'nt', 'Windows file sharing')
    def test_what_an_open_handle_of_the_display_allows_and_what_it_does_not(self):
        p = os.path.join(self.w.root, 'lock.json')
        self.w.put(p, '{"name": "x"}')
        with fsread.open_shared(p) as f:
            os.remove(p)                                                # what jobctl does to a lock: allowed while open
            self.assertEqual(f.read(), b'{"name": "x"}')
        self.assertFalse(os.path.exists(p))
        p = os.path.join(self.w.root, 'job.json')
        self.w.put(p, '{"state": "running"}')
        with fsread.open_shared(p):
            os.rename(p, p + '.moved')                                  # renamed away: allowed while open
        os.rename(p + '.moved', p)
        self.w.put(p + '.new', '{"state": "ended"}')
        with fsread.open_shared(p):
            with self.assertRaises(PermissionError):                    # replaced by rename: Windows refuses while open,
                os.replace(p + '.new', p)                               # whatever the sharing. Hence the short opens.
        os.replace(p + '.new', p)
        self.assertEqual(fsread.read_json(p), {'state': 'ended'})

    def test_a_writer_that_replaces_like_jobctl_is_never_blocked_for_long_by_the_display_reading(self):
        """The display reads a record 500 times a second (it really reads one once per change, after it has
        settled) while a writer replaces it 300 times the way jobctl does, retrying a refusal every 10 ms. Every
        replace must go through far inside jobctl's 10 second limit. Measured on the owner's machine under load,
        2026-11-14 (300 replaces each): no reader, worst 264 ms and no retry; a read each second, 2 retries, worst
        74 ms; 500 reads a second, 195 retries, worst 262 ms; a reader spinning on the file, 294 retries, worst
        1.5 s. A read can cost the writer a retry, never a failure, and the display reads a record once per
        change, so it adds less of this than any tool that polls the records."""
        p = os.path.join(self.w.root, 'job.json')
        self.w.put(p, '{"n": 0}')
        stop, reads, bad = threading.Event(), [0], []

        def reader():
            while not stop.is_set():
                try:
                    json.loads(fsread.read_text(p))
                    reads[0] += 1
                except (OSError, ValueError) as e:                      # the file is mid-replace: the collector keeps its last value
                    bad.append(type(e).__name__)
                time.sleep(0.002)
        th = threading.Thread(target=reader, daemon=True)
        th.start()
        worst = 0.0
        try:
            for n in range(1, 301):
                with open(p + '.tmp', 'w', encoding='utf-8') as f:
                    f.write(json.dumps({'n': n}))
                t0 = time.perf_counter()
                while True:
                    try:
                        os.replace(p + '.tmp', p)
                        break
                    except PermissionError:
                        if time.perf_counter() - t0 > 10:               # jobctl's own limit
                            self.fail('a replace was blocked for 10 seconds')
                        time.sleep(0.01)                                # jobctl's own retry pause
                worst = max(worst, time.perf_counter() - t0)
        finally:
            stop.set()
            th.join(5)
        self.assertEqual(fsread.read_json(p), {'n': 300})
        self.assertGreater(reads[0], 50)
        self.assertLess(worst, 5.0, f'the slowest replace took {worst:.3f} s against a 10 s limit')

    def test_a_record_being_rewritten_is_not_read_until_it_is_still(self):
        c = self.w.collector()
        self.w.snap(c)
        c.settle = 3600                                                 # everything on disk is "just written"
        self.w.job('night-queue', 'github', os.path.join(self.w.paths.night, 'chain.sh'), state='ended')
        self.w.clock[0] += 6
        s = self.w.snap(c)
        self.assertEqual(s['lanes'][0]['state'], 'testing')             # the last record stands until the file settles
        c.settle = 0
        self.w.clock[0] += 6
        self.assertEqual(self.w.snap(c)['lanes'][0]['up'], False)

    def test_no_module_imports_a_control_module_or_calls_anything_that_writes(self):
        import ast
        banned_calls = {'os.remove', 'os.unlink', 'os.rename', 'os.replace', 'os.mkdir', 'os.makedirs', 'os.rmdir', 'os.truncate',
                        'shutil.rmtree', 'shutil.copy', 'shutil.copy2', 'shutil.copyfile', 'shutil.move', 'subprocess.Popen',
                        'subprocess.call', 'subprocess.check_call', 'subprocess.check_output', 'os.system', 'os.kill', 'os.startfile',
                        'os.popen', 'os.execv', 'os.spawnv', 'exec', 'eval', '__import__', 'importlib.import_module'}
        banned_tails = ('.write', '.write_text', '.write_bytes', '.writelines', '.kill', '.terminate', '.unlink', '.mkdir', '.rename',
                        '.replace_file', '.touch', '.spec_from_file_location')
        control = ('control_center', 'jobctl', 'generation_control', 'seal_part', 'watchdog')
        subprocess_run = {}
        for name in ('fsread.py', 'readers.py', 'stats.py', 'machine.py', 'collect.py', 'rules.py', 'net.py', 'procs.py', 'serve.py'):
            src = fsread.read_text(os.path.join(HERE, name))
            mod = ast.parse(src)
            for node in ast.walk(mod):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [a.name for a in node.names] + [getattr(node, 'module', None) or '']
                    for n in names:
                        self.assertFalse(any(c in n for c in control), f'{name} imports {n}')
                if isinstance(node, ast.Attribute) and ast.unparse(node) == 'subprocess.run':
                    subprocess_run[name] = subprocess_run.get(name, 0) + 1
                if not isinstance(node, ast.Call):
                    continue
                fn = ast.unparse(node.func)
                self.assertNotIn(fn, banned_calls, f'{name} calls {fn}')
                if fn == 'self.wfile.write' and name == 'serve.py':
                    continue                                            # the HTTP response
                self.assertFalse(fn.endswith(banned_tails), f'{name} calls {fn}')
                if fn == 'open':
                    self.assertEqual(name, 'fsread.py', f'{name} opens a file itself')
                    self.assertEqual(ast.literal_eval(node.args[1]), 'rb')
                if fn == 'os.fdopen':
                    self.assertEqual(ast.literal_eval(node.args[1]), 'rb')
                if fn == 'webbrowser.open':
                    self.assertEqual(name, 'serve.py')
        self.assertEqual(subprocess_run, {'procs.py': 1})               # the one door to a process, behind the allow-list


class KaggleWatch(WithWorld):
    def test_only_a_kernel_that_was_really_pushed_is_ever_polled(self):
        w = self.w
        w.job('r8c-gpu-queue', 'kagglequeue')
        log = os.path.join(w.paths.jobs, 'jobs', 'r8c-gpu-queue.log')
        w.put(log, 'reading C:/Users/someone/fork-data/8c/gpu-queue.txt\nwaiting for someone/fork-data and owner/fork-unknown\n')
        c = w.collector()
        w.snap(c)
        self.assertEqual(c.wanted['kaggle'], [])                        # a path piece and an unknown name: nothing is polled
        w.put(os.path.join(w.paths.data, 'kaggle', 'k-a2', 'kernel-metadata.json'), json.dumps({'id': 'owner/fork-retrain-8c-a2', 'enable_gpu': True}))
        w.put(log, 'pushed owner/fork-retrain-8c-a2; polling every 300 s\n')
        w.clock[0] += 31
        w.snap(c)
        self.assertEqual(c.wanted['kaggle'], ['owner/fork-retrain-8c-a2'])


class Privacy(WithWorld):
    def test_paths_addresses_and_secrets_never_reach_the_snapshot(self):
        d = serve.Display(self.w.paths, clock=lambda: NOW)
        d.collector.probes = self.w.probes
        d.collector.git_log = None
        d.collector.settle = 0
        d.refresh()
        text = d.body.decode('utf-8')
        for secret in ('someone', 'project-secret-1', '000000-AAAAAA-BBBBBB', 'secret-key', '203.0.113.7', os.path.basename(self.w.root)):
            self.assertNotIn(secret, text)
        self.assertNotIn('"command"', text)
        self.assertNotIn('"ip"', text)

    def test_scrub(self):
        s = fsread.scrub
        self.assertEqual(s('C:\\Users\\someone\\fork-jobs\\x.log'), '~\\fork-jobs\\x.log')
        self.assertEqual(s('C:\\\\Users\\\\someone\\\\fork'), '~\\\\fork')                # as it appears inside JSON
        self.assertEqual(s('see /c/Users/someone/fork-jobs/night/x.log'), 'see ~/fork-jobs/night/x.log')
        self.assertEqual(s('into /mnt/c/Users/someone/fork-data/8c'), 'into ~/fork-data/8c')
        self.assertEqual(s('//wsl.localhost/Ubuntu/home/someone/fork-data'), '~/fork-data')
        self.assertEqual(s('/home/someone/fork'), '~/fork')
        self.assertEqual(s('vm at 203.0.113.7 answered'), 'vm at [address] answered')
        self.assertEqual(s('http://127.0.0.1:8719/'), 'http://127.0.0.1:8719/')
        self.assertEqual(s('Elo 1.30 +/- 4.37 after 3.11.14'), 'Elo 1.30 +/- 4.37 after 3.11.14')
        fsread.private('someone')
        self.addCleanup(fsread.PRIVATE.discard, 'someone')
        self.assertEqual(s("Cannot access kernel 'someone/fork-data' (denied)"), "Cannot access kernel '[user]/fork-data' (denied)")
        self.assertEqual(s('someone-else and awesomeone stay'), 'someone-else and awesomeone stay')
        me = os.path.basename(os.path.expanduser('~'))
        if len(me) >= 3:
            self.assertNotIn(me, s(f'error from a tool about {me}/fork-data'))


class Commands(unittest.TestCase):
    def test_only_the_read_only_commands_are_allowed(self):
        ok = [['git', '-C', 'C:/repo', 'log', '-400', '--format=%h %ad %s', '--date=short', 'phase-4'],
              ['C:/x/gh.exe', 'api', 'repos/OWNER/fork/actions/runs/43620446592/jobs?per_page=100'],
              ['gh', 'api', 'repos/OWNER/fork/actions/runs/43620446592/artifacts?per_page=100'],
              ['gh', 'api', 'repos/OWNER/fork/actions/artifacts/123/zip'],
              ['C:/repo/.venv/Scripts/kaggle.exe', 'kernels', 'status', 'owner/fork-retrain-8c-a1']]
        bad = [['git', '-C', 'C:/repo', 'push'], ['git', '-C', 'C:/repo', 'log', '--output=x'], ['git', 'log'], ['git', '-C', 'r', 'reset', '--hard'],
               ['gh', 'api', '-X', 'POST', 'repos/OWNER/fork/actions/runs/1/cancel'], ['gh', 'api', 'repos/OWNER/fork/actions/runs/1/cancel'],
               ['gh', 'api', 'repos/OWNER/fork/actions/runs/1/rerun'], ['gh', 'run', 'cancel', '1'], ['gh', 'workflow', 'run', 'sprt.yml'],
               ['gh', 'api', 'repos/OWNER/fork/actions/runs/1/jobs', '--method', 'DELETE'], ['gh', 'api', 'repos/OWNER/fork/dispatches'],
               ['kaggle', 'kernels', 'push', '-p', 'x'], ['kaggle', 'kernels', 'status', 'owner/k', '--extra'], ['kaggle', 'datasets', 'list'],
               ['wsl.exe', '-e', 'true'], ['powershell.exe', '-Command', 'x'], ['bash', 'x.sh'], ['python', 'jobctl.py', 'stop', 'x'], [], 'gh api x',
               ['gcloud', 'compute', 'instances', 'list']]
        for a in ok:
            self.assertTrue(procs.allowed(a), a)
        for a in bad:
            self.assertFalse(procs.allowed(a), a)
            with self.assertRaises(PermissionError):
                procs.run(a, runner=lambda *x, **k: self.fail('a refused command reached the runner'))

    def test_run_passes_no_stdin_and_reports_failures(self):
        seen = {}

        def runner(argv, **kw):
            seen.update(kw, argv=argv)
            return type('P', (), {'returncode': 1, 'stdout': b'', 'stderr': b'x\nHTTP 404: C:\\Users\\someone\\gh\n'})()
        rc, out, err = procs.run(['gh', 'api', 'repos/OWNER/fork/actions/runs/1/jobs?per_page=100'], runner=runner)
        self.assertEqual((rc, out), (1, ''))
        self.assertEqual(err, 'HTTP 404: ~\\gh')
        self.assertEqual(seen['env']['GIT_OPTIONAL_LOCKS'], '0')
        self.assertIsNotNone(seen['timeout'])
        import subprocess
        self.assertEqual(seen['stdin'], subprocess.DEVNULL)


def _zip(record, name='progress.json'):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr(name, record if isinstance(record, (str, bytes)) else json.dumps(record))
    return buf.getvalue()


class Network(unittest.TestCase):
    def test_repo_slug(self):
        self.assertEqual(net.repo_slug('[remote "origin"]\n\turl = https://github.com/OWNER/fork.git\n'), 'OWNER/fork')
        self.assertEqual(net.repo_slug('[remote "origin"]\n\turl = git@github.com:OWNER/fork\n'), 'OWNER/fork')
        self.assertIsNone(net.repo_slug('[core]\n'))

    def test_shard_counts_and_progress_artifacts(self):
        jobs = {'jobs': [{'name': 'engines', 'status': 'completed', 'conclusion': 'success'}] +
                [{'name': f'shard ({i})', 'status': 'completed', 'conclusion': 'success'} for i in range(9)] +
                [{'name': 'shard (9)', 'status': 'completed', 'conclusion': 'failure'}] +
                [{'name': f'shard ({i})', 'status': 'in_progress', 'conclusion': None} for i in range(10, 14)] +
                [{'name': f'shard ({i})', 'status': 'queued', 'conclusion': None} for i in range(14, 16)]}
        self.assertEqual(net.shard_counts(json.dumps(jobs)), {'total': 16, 'done': 10, 'running': 4, 'queued': 2, 'failed': 1})
        for bad in ('', 'not json', '{}', '{"jobs": []}', '[1]'):
            self.assertIsNone(net.shard_counts(bad))
        arts = {'artifacts': [{'id': 1, 'name': 'progress-5-0', 'updated_at': '2026-11-14T18:00:00Z'},
                              {'id': 2, 'name': 'progress-5-0', 'updated_at': '2026-11-14T18:05:00Z'},
                              {'id': 3, 'name': 'progress-5-1', 'updated_at': '2026-11-14T18:05:00Z', 'expired': True},
                              {'id': 4, 'name': 'shard-5-2'}, {'id': 'x', 'name': 'progress-5-3'}, 'junk']}
        self.assertEqual(net.progress_artifacts(json.dumps(arts)), [{'id': 2, 'stage': 5, 'shard': 0}])
        self.assertEqual(net.progress_artifacts('half {'), [])

    def test_progress_zip(self):
        rec = {'sprt': 'x-stc', 'stage': 5, 'shard': 0, 'ptnml': [1, 10, 20, 12, 2], 'finished_games': 90, 'at': '2026-11-14T18:05:00Z'}
        self.assertEqual(net.read_progress_zip(_zip(rec))['games'], 90)
        for bad in (b'', b'not a zip', _zip(rec, 'other.json'), _zip('{half'), _zip({'stage': 5, 'shard': 0, 'ptnml': [1, 2]}), _zip('x' * 70000)):
            with self.assertRaises(ValueError):
                net.read_progress_zip(bad)
        both = net.combine([{'stage': 5, 'shard': 0, 'ptnml': [1, 10, 20, 12, 2], 'games': 90, 'at': 100},
                            {'stage': 5, 'shard': 1, 'ptnml': [0, 9, 22, 11, 1], 'games': 86, 'at': 160},
                            {'stage': 4, 'shard': 0, 'ptnml': [9, 9, 9, 9, 9], 'games': 90, 'at': 50}], 5)
        self.assertEqual(both, {'ptnml': [1, 19, 42, 23, 3], 'games': 176, 'shards': 2, 'at': 160})
        self.assertIsNone(net.combine([], 5))

    def test_the_poller_uses_only_allowed_commands_and_survives_bad_answers(self):
        calls = []
        rec = {'sprt': 'x-stc', 'stage': 5, 'shard': 0, 'ptnml': [1, 10, 20, 12, 2], 'finished_games': 90, 'at': '2026-11-14T18:05:00Z'}

        def execute(argv, timeout=30, binary=False):
            self.assertTrue(procs.allowed(argv), argv)
            calls.append(argv[-1])
            if argv[1] == 'kernels':
                return 0, 'owner/fork-retrain has status "KernelWorkerStatus.RUNNING"', ''
            if argv[-1].endswith('/jobs?per_page=100'):
                return 0, json.dumps({'jobs': [{'name': 'shard (0)', 'status': 'in_progress'}]}), ''
            if argv[-1].endswith('/artifacts?per_page=100'):
                return 0, json.dumps({'artifacts': [{'id': 7, 'name': 'progress-5-0', 'updated_at': 'b'}, {'id': 8, 'name': 'progress-5-1', 'updated_at': 'b'}]}), ''
            return 0, _zip(rec) if argv[-1].endswith('/7/zip') else b'broken', ''
        c = type('C', (), {'wanted': {'runs': [777], 'kaggle': ['owner/fork-retrain']}, 'net': {'runs': {}, 'kaggle': {}}})()
        t = [1000.0]
        p = net.Poller(c, 'repo', 'OWNER/fork', execute=execute, clock=lambda: t[0], gh='gh', kaggle='kaggle')
        p.step()
        self.assertEqual(c.net['runs'][777]['shards'], {'total': 1, 'done': 0, 'running': 1, 'queued': 0, 'failed': 0})
        self.assertEqual(c.net['runs'][777]['progress']['games'], 90)          # the broken artifact is skipped, the good one used
        self.assertIn('unreadable', c.net['runs'][777]['error'])
        self.assertEqual(c.net['kaggle']['owner/fork-retrain']['state'], 'RUNNING')
        n = len(calls)
        p.step()                                                                # nothing is due yet
        self.assertEqual(len(calls), n)
        t[0] += 121
        p.step()
        self.assertEqual(sum(1 for x in calls if x.endswith('/zip')), 2)        # an artifact is downloaded once
        c.wanted = {'runs': [], 'kaggle': []}
        t[0] += 400
        p.step()
        self.assertEqual((p.status['gh'], p.status['kaggle']), ('idle: no live run', 'idle: no session job is running'))
        p.execute = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom'))
        c.wanted = {'runs': [1], 'kaggle': ['a/fork-b']}
        t[0] += 400
        p.step()                                                                # a failing tool never ends the poller
        self.assertTrue(p.status['gh'].startswith('failed'))


class Server(WithWorld):
    def setUp(self):
        super().setUp()
        self.display = serve.Display(self.w.paths, clock=lambda: NOW)
        self.display.collector.probes = self.w.probes
        self.display.collector.git_log = None
        self.display.collector.settle = 0
        self.display.refresh()
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), None)
        self.port = self.httpd.server_address[1]
        self.httpd.RequestHandlerClass = serve.make_handler(self.display, self.port)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def get(self, path, method='GET', host=None):
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', method=method, data=b'{}' if method != 'GET' else None)
        if host:
            req.add_header('Host', host)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def test_it_serves_the_page_and_the_snapshot(self):
        code, body, headers = self.get('/snapshot')
        self.assertEqual(code, 200)
        snap = json.loads(body)
        self.assertEqual([l['id'] for l in snap['lanes']], ['A', 'B'])
        self.assertIn('alerts', snap)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        for path in ('/', '/app.js', '/style.css'):
            code, body, _ = self.get(path)
            self.assertEqual(code, 200, path)
            self.assertGreater(len(body), 500)

    def test_it_refuses_everything_but_local_reads(self):
        for method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            self.assertEqual(self.get('/snapshot', method)[0], 405, method)
        self.assertEqual(self.get('/snapshot', host='evil.example')[0], 403)
        self.assertEqual(self.get('/snapshot', host=f'evil.example:{self.port}')[0], 403)
        for path in ('/jobs/stop', '/../serve.py', '/fixtures/gcp-status.json', '/web/../rules.py', '/snapshot/../../x'):
            self.assertEqual(self.get(path)[0], 404, path)

    def test_the_page_makes_no_outside_request_and_has_no_form(self):
        for name in ('index.html', 'app.js', 'style.css'):
            src = fsread.read_text(os.path.join(HERE, 'web', name))
            for banned in ('http://', 'https://', '<form', 'method:', 'XMLHttpRequest', 'localStorage', 'sessionStorage', 'document.cookie', 'indexedDB'):
                if banned == 'http://' and name == 'app.js':
                    self.assertEqual(src.count('http://'), 1)          # the SVG namespace, not a request
                    self.assertIn('"http://www.w3.org/2000/svg"', src)
                    continue
                self.assertNotIn(banned, src, f'{name} contains {banned}')
        js = fsread.read_text(os.path.join(HERE, 'web', 'app.js'))
        self.assertEqual(js.count('fetch('), 1)
        self.assertIn('fetch("/snapshot"', js)


class Machine(unittest.TestCase):
    def test_job_liveness_follows_the_recorded_process(self):
        rec = {'state': 'running', 'started': 5000.0, 'keeper': 11, 'pid': 12, 'keeper_started': 5001.0, 'pid_started': 5002.0}
        probe = lambda alive: (lambda pid: alive.get(pid, (False, None)))  # noqa: E731
        self.assertTrue(machine.job_live(rec, probe({11: (True, 5001.5)}), boot=100.0))
        self.assertFalse(machine.job_live(rec, probe({11: (True, 9000.0), 12: (True, 9000.0)}), boot=100.0))   # the ids were reused
        self.assertFalse(machine.job_live(rec, probe({}), boot=100.0))
        self.assertFalse(machine.job_live(rec, probe({11: (True, 5001.0)}), boot=6000.0))                      # started before the last boot
        self.assertFalse(machine.job_live(dict(rec, state='ended'), probe({11: (True, 5001.0)}), boot=100.0))
        old = {'state': 'running', 'started': 5000.0, 'keeper': 11}
        self.assertTrue(machine.job_live(old, probe({11: (True, 5060.0)}), boot=100.0))                       # an older record: within its start window
        self.assertFalse(machine.job_live(old, probe({11: (True, 5500.0)}), boot=100.0))
        self.assertIsNone(machine.job_live({'state': 'running', 'started': 5000.0}, probe({}), boot=100.0))

    @unittest.skipUnless(os.name == 'nt', 'Windows probes')
    def test_real_probes_answer(self):
        a = machine.cpu_times()
        m = machine.memory()
        self.assertTrue(a and a[0] > 0)
        self.assertTrue(0 < m['avail'] < m['total'])
        self.assertTrue(0 < m['commit'] < 200)
        alive, started = machine.pid_started(os.getpid())
        self.assertTrue(alive)
        self.assertLess(abs(time.time() - started), 3600)
        self.assertEqual(machine.pid_started(0), (False, None))


if __name__ == '__main__':
    unittest.main()
