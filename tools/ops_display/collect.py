# SPDX-License-Identifier: GPL-3.0-or-later
"""The collector: turns the pipeline's files into one snapshot for the display.

It discovers what exists instead of knowing names: lanes from the lock files, queue items from each lane's
folder (found through the lane's own runner script), tests from the item logs, jobs from their records,
retrains from the folders that hold gate results, data parts and labellers from the manifests. Each source
is read through fsread (read-only, shared, only when its size or modified time changed). A source that
fails to parse keeps its last good value and is reported in `health`, which the rules turn into an alert.
Nothing here writes a file or starts a process; the two network polls live in net.py."""
import os
import re
import statistics
import time
from collections import deque

import fsread
import readers as R
import stats

RUNNING = ('starting', 'running', 'stopping')
WEEK = 7 * 86400


class Paths:
    """Every folder the display reads; all can be pointed elsewhere (the tests use temporary folders)."""

    def __init__(self, home=None, repo=None, cc_state=None, wsl_home=None):
        home = home or os.path.expanduser('~')
        j = os.path.join
        self.home = home
        self.jobs = j(home, 'fork-jobs')
        self.night = j(self.jobs, 'night')
        self.state = j(self.night, 'state')
        self.data = j(home, 'fork-data')
        self.sprt = j(self.data, 'sprt')
        self.gauntlet = j(self.data, 'gauntlet')
        self.repo = repo or j(home, 'fork')
        self.cc = cc_state or j(os.environ.get('LOCALAPPDATA') or j(home, 'AppData', 'Local'), 'ForkControlCenter')
        self.wsl_home = wsl_home            # the WSL home as a Windows path; found on first use when None
        self.wsl_homes = r'\\wsl.localhost\Ubuntu\home'


def _median(xs):
    return statistics.median(xs) if xs else None


class Collector:
    SECTIONS = (('machine', 2), ('jobs', 5), ('sprts', 30), ('lanes', 5), ('data', 10), ('training', 30),
                ('overview', 60))

    def __init__(self, paths=None, clock=time.time, probes=None, git_log=None):
        self.p = paths or Paths()
        self.clock = clock
        if probes is None:
            import machine as probes
        self.probes = probes
        self.git_log = git_log              # callable(repo, branch) -> text of `git log`, or None (no adoptions)
        self.cache = fsread.Cache(clock)
        self.last, self.state, self.errors = {}, {}, {}
        self.net = {'runs': {}, 'kaggle': {'sessions': []}}            # filled by net.Poller; read here
        self.wanted = {'runs': [], 'kaggle': {'watch': False, 'named': []}}   # what the poller should look at
        self._jobcache = {}
        self._cpu_prev = None
        self.hist = {'cpu': deque(maxlen=120), 'avail': deque(maxlen=120), 'commit': deque(maxlen=120)}
        self._hist_at = 0
        self._adopt = (None, [])
        self._vm_rate = None
        self.settle = 0.5       # seconds a job record must have been still before it is read (see fsread.py)

    # ------------------------------------------------------------ small loaders

    def _key(self, path):
        return fsread.scrub(os.path.normpath(path)).replace('\\', '/')

    def _text(self, path, limit=fsread.MAX_WHOLE, optional=True):
        return self.cache.load(self._key(path), path, lambda p: fsread.read_text(p, limit), default='', optional=optional) or ''

    def _tail(self, path, nbytes):
        return self.cache.load(self._key(path), path, lambda p: fsread.tail_text(p, nbytes), default='', optional=True) or ''

    def _json(self, path, parse, optional=True, default=None):
        return self.cache.load(self._key(path), path, lambda p: parse(fsread.read_json(p)), default=default, optional=optional)

    def _parsed(self, path, parse, limit=fsread.MAX_WHOLE):
        return self.cache.load(self._key(path), path, lambda p: parse(fsread.read_text(p, limit)), optional=True)

    # ------------------------------------------------------------ tick

    def tick(self):
        now = self.clock()
        for name, every in self.SECTIONS:
            if now - self.last.get(name, -1e9) < every:
                continue
            try:
                self.state[name] = getattr(self, '_' + name)(now)
                self.errors.pop(name, None)
            except Exception as e:  # noqa: BLE001  one section failing must not blank the others
                self.errors[name] = f'{type(e).__name__}: {e}'[:200]
            self.last[name] = now
        return self.snapshot(now)

    def snapshot(self, now):
        s = self.state
        snap = {'now': now, 'machine': s.get('machine'), 'jobs': self._jobs_view(s.get('jobs')),
                'lanes': (s.get('lanes') or {}).get('lanes', []), 'queue': (s.get('lanes') or {}).get('queue', []),
                'verdicts': (s.get('sprts') or {}).get('verdicts', []),
                'interrupted': self._interrupted(now),
                'data': s.get('data'), 'training': s.get('training'), 'overview': s.get('overview'),
                'events': self._events(now), 'health': self._health()}
        return snap

    def _interrupted(self, now):
        """Tests dispatched and never merged that no lane is running: stopped without a verdict."""
        sp = self.state.get('sprts') or {}
        live = {(l['sprt'] or {}).get('name') for l in (self.state.get('lanes') or {}).get('lanes', [])}
        out = []
        for c in sp.get('interrupted', []):
            typical = sp.get('typical', {}).get(c['klass'])
            quiet = max(3600, 2.5 * 60 * typical) if typical else 3 * 3600
            if c['name'] not in live and now - c['log_at'] > quiet:
                t = R.item_title(c['name'], c['name'], *self._names())
                out.append({'name': c['name'], 'title': t['title'], 'since': c['since'], 'klass': c['klass']})
        return out

    def _health(self):
        h = {k: v for k, v in self.cache.health().items() if not v['ok']}
        for name, err in self.errors.items():
            h['section: ' + name] = {'ok': False, 'error': err, 'missing': False, 'age': None}
        return {'failing': h, 'sources': len(self.cache.sources)}

    # ------------------------------------------------------------ jobs and locks

    def _jobs(self, now):
        folder = os.path.join(self.p.jobs, 'jobs')
        recs, seen = {}, set()
        for name, is_dir, mt, size in fsread.listdir(folder):
            if is_dir or not name.endswith('.json'):
                continue
            key = name[:-5]
            seen.add(key)
            old = self._jobcache.get(key)
            if (not old or old[0] != (mt, size)) and time.time() - mt < self.settle:
                if old and old[1]:
                    recs[key] = old[1]      # being rewritten right now: keep the last record, read it next time
                continue
            if not old or old[0] != (mt, size):
                try:
                    raw = fsread.read_json(os.path.join(folder, name))
                    old = ((mt, size), R.job_record(raw), R.job_script(raw))
                except (OSError, ValueError):
                    old = (None, old[1] if old else None, old[2] if old else None)   # replaced mid-read: next time
                self._jobcache[key] = old
            if old[1]:
                recs[key] = old[1]
        for gone in set(self._jobcache) - seen:
            del self._jobcache[gone]
        running = []
        for key, rec in recs.items():
            if rec['state'] in RUNNING:
                running.append({**rec, 'live': self.probes.job_live(rec), 'script': self._jobcache[key][2]})
        locks = {}
        for name, is_dir, _, _ in fsread.listdir(os.path.join(self.p.jobs, 'locks')):
            if name.endswith('.json') and not is_dir:
                d = self._json(os.path.join(self.p.jobs, 'locks', name), lambda x: x if isinstance(x, dict) else None)
                if d and d.get('name'):
                    locks[name[:-5]] = {'name': d['name'], 'id': d.get('id'), 'started': R.iso(d.get('started'))}
        ended = [r for r in recs.values() if r['state'] not in RUNNING and r['ended'] and now - r['ended'] < 86400]
        ev_text = self._tail(os.path.join(self.p.jobs, 'events.jsonl'), 24000)
        events, _ = R.events(ev_text)
        return {'recs': recs, 'running': running, 'locks': locks, 'ended': ended, 'events': events}

    def _jobs_view(self, j):
        if not j:
            return None
        lock_of = {v['name']: k for k, v in j['locks'].items()}
        run = [{'name': r['name'], 'type': r['type'], 'started': r['started'], 'live': r['live'],
                'lock': lock_of.get(r['name'])} for r in sorted(j['running'], key=lambda r: r['started'] or 0)]
        failed = []
        ended = sorted(j['ended'], key=lambda r: r['ended'])
        for i, r in enumerate(ended):
            if r['exit_code'] in (0, None) and r['state'] != 'failed':
                continue
            stem = re.sub(r'\d+$', '', r['name'])
            later_ok = any(re.sub(r'\d+$', '', x['name']) == stem and x['exit_code'] == 0 for x in ended[i + 1:])
            failed.append({'name': r['name'], 'type': r['type'], 'at': r['ended'], 'exit_code': r['exit_code'],
                           'recovered': later_ok})
        return {'running': run, 'failed': failed[-12:], 'records': len(j['recs'])}

    # ------------------------------------------------------------ tests (the SPRT folders)

    def _klass(self, e):
        des, hdr = e.get('design'), (e['drv'].get('header') or {})
        if des:
            return des.get('tc_class') or 'stc'
        if hdr.get('kind'):
            return hdr.get('tc_class') or 'stc'
        return 'screen'

    def _load_sprt(self, name):
        d = os.path.join(self.p.sprt, name)
        drv = self._parsed(os.path.join(d, 'driver.log'), R.driver_log, 512 * 1024)
        if not drv:
            return None
        verdict = self._text(os.path.join(d, 'verdict'), 4096).strip()
        des = self._json(os.path.join(d, 'design.json'), R.design)
        return {'name': name, 'drv': drv, 'verdict': verdict, 'design': des,
                'verdict_at': fsread.mtime(os.path.join(d, 'verdict')), 'log_at': fsread.mtime(os.path.join(d, 'driver.log'))}

    def _sprts(self, now):
        idx = {}
        for name, is_dir, _, _ in fsread.listdir(self.p.sprt):
            if not is_dir:
                continue
            mt = fsread.mtime(os.path.join(self.p.sprt, name, 'driver.log'))
            if mt is None or now - mt > 10 * 86400:
                continue
            e = self._load_sprt(name)
            if e:
                idx[name] = e
        mins = {}
        for e in idx.values():
            for s in e['drv']['stages']:
                if s.get('merged') and s.get('dispatched') and s['merged'] > s['dispatched']:
                    mins.setdefault(self._klass(e), []).append((s['merged'], (s['merged'] - s['dispatched']) / 60))
        typical = {k: _median([m for _, m in sorted(v)[-30:]]) for k, v in mins.items()}
        adopted = self._adopted_tests()
        tries, _ = R.tries(self._text(os.path.join(self.p.jobs, 'tries.jsonl')))
        codes, ideas = self._names()
        verdicts, interrupted = [], []
        for name, e in idx.items():
            drv, last = e['drv'], (e['drv']['stages'][-1] if e['drv']['stages'] else None)
            out = R.outcome(e['verdict'], drv, e['design'] is not None)
            at = e['verdict_at'] or (drv['end'] or {}).get('at') or (drv['stopped'] or {}).get('at')
            if out['kind'] == 'running':
                if drv['flight'] and e['log_at'] and now - e['log_at'] < 2 * 86400:
                    interrupted.append({'name': name, 'since': drv['flight']['dispatched'], 'log_at': e['log_at'],
                                        'stage': drv['flight']['stage'], 'klass': self._klass(e)})
                if not drv['end']:
                    continue
                at = drv['end']['at']
            if not at or now - at > 3 * 86400:
                continue
            t = R.item_title(name, name, codes, ideas)
            verdicts.append({'at': at, 'name': name, 'title': t['title'], 'about': t['about'], 'klass': self._klass(e).upper()
                             if self._klass(e) != 'screen' else 'screen', 'outcome': out,
                             'elo': last['elo'] if last else None, 'err': last['elo_err'] if last else None,
                             'games': last['games'] if last else None, 'adopted': name in adopted,
                             'try': (tries.get(name) or {}).get('try')})
        verdicts.sort(key=lambda v: -v['at'])
        return {'index': idx, 'typical': typical, 'verdicts': verdicts[:40], 'interrupted': interrupted}

    def _adopted_tests(self):
        t = self._json(os.path.join(self.p.repo, 'tools', 'gauntlet', 'transfer.json'), R.transfer, default=[]) or []
        return {name for a in t for name in a.get('tests', [])}

    def _names(self):
        codes, ideas = {}, {}
        research = os.path.join(self.p.repo, 'docs', 'research')
        for name, is_dir, _, _ in fsread.listdir(research):
            if is_dir:
                c = self._parsed(os.path.join(research, name, 'comparison.md'), R.survey_codes)
                if c:
                    codes.update(c)
        ideas = self._parsed(os.path.join(self.p.repo, 'docs', 'ideas.md'), R.ideas_md) or {}
        return codes, ideas

    # ------------------------------------------------------------ lanes and queue

    def _lanes(self, now):
        jobs = self.state.get('jobs') or {'locks': {}, 'recs': {}, 'running': []}
        sprts = self.state.get('sprts') or {'index': {}, 'typical': {}}
        state_names = {n for n, _, _, _ in fsread.listdir(self.p.state)}
        ledger, _ = R.ledger(self._tail(os.path.join(self.p.jobs, 'ledger.jsonl'), 16000))
        dispatch = {(r['sprt'], r['stage']): r for r in ledger}
        codes, ideas = self._names()
        lanes, queue, runs = [], [], []
        lane_locks = sorted((k for k in jobs['locks'] if k.startswith('github')), key=lambda k: (len(k), k))
        for n, lock in enumerate(lane_locks):
            lid = chr(ord('A') + n) if n < 26 else str(n)
            holder = jobs['locks'][lock]['name']
            rec = next((r for r in jobs['running'] if r['name'] == holder), None)
            lane = {'id': lid, 'lock': lock, 'job': holder, 'up': bool(rec) and rec['live'] is not False,
                    'state': 'down', 'item': None, 'sprt': None, 'pending': 0, 'folder': None, 'since': (rec or {}).get('started')}
            folder = None
            if rec and rec.get('script'):
                folder = R.chain_items_folder(self._text(rec['script'], 256 * 1024))
            lane['folder'] = folder
            pending = []
            if folder:
                for name, is_dir, _, _ in fsread.listdir(os.path.join(self.p.night, folder)):
                    if is_dir or not name.endswith('.sh'):
                        continue
                    key = name[:-3]
                    if key + '.done' in state_names or key + '.skipped' in state_names:
                        continue
                    pending.append(key)
            pending.sort()
            # the lane's own marker says what it runs; without a fresh one, the first runnable item is taken
            mark = self._parsed(os.path.join(self.p.state, f'current-{lid}.txt'), R.lane_marker, 16 * 1024)
            if mark and (mark['lane'] != lid or (mark['source'] == 'watcher' and (not mark['updated'] or now - mark['updated'] > 180))):
                mark = None
            alive = getattr(self.probes, 'pid_alive', None)
            if mark and mark['source'] != 'watcher' and mark['chain_pid'] and alive and not alive(mark['chain_pid']):
                mark = None                                 # a chain writes on transitions only: its process must still live
            lane['marker'] = (mark or {}).get('source')
            marked = mark['item'] if mark and mark['state'] == 'running' else None
            if marked and marked not in pending:
                pending.insert(0, marked)                   # it finished its last step a moment ago: still the lane's item
            current = None
            for key in pending:
                log = R.item_log(self._tail(os.path.join(self.p.night, key + '.log'), 6000))
                retry_at = None
                if key + '.retry_at' in state_names:
                    retry_at = R.num(self._text(os.path.join(self.p.state, key + '.retry_at'), 64).strip())
                failures = int(R.num(self._text(os.path.join(self.p.state, key + '.failures'), 64).strip()) or 0) \
                    if key + '.failures' in state_names else 0
                waiting_retry = bool(retry_at and retry_at > now)
                t = R.item_title(key, log['sprt'], codes, ideas)
                item = {'lane': lid, 'key': key, 'title': t['title'], 'about': t['about'], 'kind': R.item_kind(key),
                        'comment': R.item_comment(self._text(os.path.join(self.p.night, folder, key + '.sh'), 64 * 1024)),
                        'state': 'retry' if waiting_retry else 'gated' if log['waiting'] else 'pending',
                        'retry_at': retry_at if waiting_retry else None, 'failures': failures, 'sprt': log['sprt']}
                if mark:
                    if key == marked and lane['up']:
                        item['sprt'] = item['sprt'] or (mark['drivers'][0] if mark['drivers'] else None)
                        current = item
                        continue
                    if not marked and current is None and lane['up'] and item['sprt'] and item['sprt'] in mark['drivers']:
                        current = item                      # idle between steps, its test's driver still running
                        continue
                elif current is None and lane['up'] and not waiting_retry and not log['waiting']:
                    current = item
                    continue
                queue.append(item)
            if mark and current is None and lane['up'] and mark['drivers']:
                name = mark['drivers'][0]                   # a driver with no item of its own left in the folder
                t = R.item_title(name, name, codes, ideas)
                current = {'lane': lid, 'key': name, 'title': t['title'], 'about': t['about'], 'kind': R.item_kind(name),
                           'comment': None, 'state': 'pending', 'retry_at': None, 'failures': 0, 'sprt': name}
            lane['pending'] = sum(1 for q in queue if q['lane'] == lid)
            if current:
                lane['item'] = current
                view = self._sprt_view(current['sprt'], now, sprts, dispatch) if current['sprt'] else None
                lane['sprt'] = view
                if view and view.get('flight'):
                    runs.append(view['flight']['run'])
                    lane['state'] = 'testing'
                elif view and view.get('stopped'):
                    lane['state'] = 'stopped'
                else:
                    lane['state'] = 'starting'
            elif lane['up']:
                lane['state'] = 'idle'
            lanes.append(lane)
        self.wanted['runs'] = runs
        return {'lanes': lanes, 'queue': queue}

    def _sprt_view(self, name, now, sprts, dispatch):
        e = sprts['index'].get(name) or self._load_sprt(name)
        if not e:
            return {'name': name, 'new': True, 'stages': [], 'flight': None, 'klass': None}
        drv, des, hdr = e['drv'], e['design'], e['drv'].get('header') or {}
        klass = self._klass(e)
        first = hdr.get('first_stage') or 0
        stages = drv['stages']
        last = stages[-1] if stages else None
        cap = (des or {}).get('cap') or (hdr.get('last_stage', first) - first + 1 if hdr else None)
        per = (des or {}).get('games') or (stages[0]['games'] if stages else None)
        lo, hi = (last['lo'], last['hi']) if last else (None, None)
        if lo is None and des and des.get('alpha') and des.get('beta'):
            import math
            lo, hi = round(math.log(des['beta'] / (1 - des['alpha'])), 2), round(math.log((1 - des['beta']) / des['alpha']), 2)
        typical = sprts['typical'].get(klass)
        flight = drv['flight']
        view = {'name': name, 'klass': klass, 'is_sprt': klass != 'screen',
                'design': {'kind': (des or {}).get('kind') or hdr.get('kind'),
                           'elo0': hdr.get('elo0'), 'elo1': hdr.get('elo1'), 'tc': (des or {}).get('tc'), 'cap': cap,
                           'games_per_stage': per, 'futility_after': hdr.get('futility_after'), 'idea': hdr.get('idea'),
                           'try': hdr.get('try'), 'base': (hdr.get('base') or '')[:7], 'test': (hdr.get('test') or '')[:7],
                           'alpha': hdr.get('alpha'), 'beta': hdr.get('beta')},
                'stages': [{k: s.get(k) for k in ('stage', 'run', 'dispatched', 'merged', 'games', 'elo', 'elo_err',
                                                    'nelo', 'nelo_err', 'llr', 'ptnml')} for s in stages],
                'last': last and {k: last.get(k) for k in ('games', 'elo', 'elo_err', 'nelo', 'nelo_err', 'llr', 'ptnml')},
                'lo': lo, 'hi': hi, 'stage_no': None, 'stage_count': cap, 'cap_games': cap * per if cap and per else None,
                'flight': None, 'typical_min': round(typical, 1) if typical else None,
                'stopped': drv['stopped'] and drv['stopped']['text'][:160], 'end': drv['end'] and drv['end']['text'],
                'prelim': None, 'shards': None}
        if flight:
            led = dispatch.get((name, flight['stage']))
            at = led['at'] if led and led.get('run_id') == flight['run'] and led['at'] else flight['dispatched']
            view['stage_no'] = flight['stage'] - first + 1
            eta = at + typical * 60 if typical and at else None
            latest = eta + (cap - view['stage_no']) * typical * 60 if eta and cap and klass != 'screen' else None
            view['flight'] = {'stage': flight['stage'], 'run': flight['run'], 'dispatched': at, 'eta': eta, 'latest': latest}
            net = self.net['runs'].get(flight['run'])
            if net:
                view['shards'] = net.get('shards')
                p = net.get('progress')
                if p and p.get('ptnml') and p.get('stage') == flight['stage'] and sum(p['ptnml']) > 0:
                    total = stats.add([p['ptnml']] + ([last['ptnml']] if last and last.get('ptnml') else []))
                    summ = stats.summary(total)
                    if summ:
                        est = None
                        if klass != 'screen' and hdr.get('elo0') is not None and hdr.get('elo1') is not None:
                            est = round(stats.llr(total, hdr['elo0'], hdr['elo1']), 2)
                        view['prelim'] = {**summ, 'llr': est, 'stage_games': p['games'], 'stage_planned': p['planned'],
                                          'shards': p['shards'], 'of': p['of'], 'final': p['final'], 'at': p['at']}
        elif last:
            view['stage_no'] = last['stage'] - first + 1
        return view

    # ------------------------------------------------------------ data

    def _wsl_window(self, now):
        t = time.gmtime(now - 5 * 3600)        # EST
        m = t.tm_hour * 60 + t.tm_min
        return 80 <= m < 150                   # 1:20 to 2:30 AM EST: a chain restarts WSL then

    def _wsl_home(self):
        if self.p.wsl_home:
            return self.p.wsl_home
        homes = [n for n, is_dir, _, _ in fsread.listdir(self.p.wsl_homes) if is_dir]
        if len(homes) == 1:
            self.p.wsl_home = os.path.join(self.p.wsl_homes, homes[0])
            fsread.private(homes[0])
        return self.p.wsl_home

    def _data(self, now):
        j = os.path.join
        # the PC's generator
        wd = self._json(j(self.p.cc, 'watchdog.json'), R.watchdog)
        pc = {'state': 'idle', 'part': None, 'positions': None, 'rate': None, 'target': None, 'seal': None,
              'since': None, 'note': None}
        parts_dir = j(self.p.cc, 'parts')
        part_names = [n for n, d, _, _ in fsread.listdir(parts_dir) if d]
        if wd and wd['part']:
            pc['part'] = wd['part']
            fresh = wd['heartbeat'] and now - wd['heartbeat'] < 120
            part = self._json(j(parts_dir, wd['part'], 'part.json'), R.part_json) or {}
            pc['target'] = part.get('target')
            if wd['running'] and fresh and not wd['exited']:
                pc['state'] = 'active'
                if self._wsl_window(now):
                    pc['note'] = 'rate not read between 1:20 and 2:30 AM EST'
                elif part.get('dir') and self._wsl_home():
                    rel = part['dir'].replace('~/', '').replace('/', os.sep)
                    log = self._tail(j(self._wsl_home(), rel, wd['part'] + '.log'), 12000)
                    g = R.datagen_log(log)
                    if g:
                        pc.update(positions=g['positions'], rate=g['rate'])
                    else:
                        pc['note'] = 'running; its log could not be read'
                else:
                    pc['note'] = 'running; rate not read'
            else:
                pc['since'] = wd['exited'] or wd['heartbeat']
        seals = {}
        for name in part_names:
            s = self._json(j(parts_dir, name, 'seal-result.json'), R.seal_result)
            if s:
                seals[name] = s
        # manifests: totals, labellers, parts
        by_lab, parts, total = {}, [], 0
        mdir = j(self.p.repo, 'data', 'manifests')
        sources = [j(mdir, n) for n, d, _, _ in fsread.listdir(mdir) if n.endswith('.json') and not d]
        cloud_verified, cloud_chunks, cloud_runs = 0, 0, 0
        for name, is_dir, _, _ in fsread.listdir(self.p.data):
            filler = j(self.p.data, name, 'filler')
            if not is_dir or fsread.stat(filler) is None:
                continue
            have = set()
            for n, d, _, _ in fsread.listdir(j(filler, 'parts')):
                if n.endswith('.json') and not d:
                    sources.append(j(filler, 'parts', n))
                    have.add(n[:-5])
            for n, d, _, _ in fsread.listdir(filler):
                if n.endswith('.ok') and not d:
                    ok = self._parsed(j(filler, n), R.filler_ok, 4096)
                    if ok:
                        cloud_verified += ok['positions']
                        cloud_chunks += ok['chunks']
                        cloud_runs += 1
                        if n[:-3] not in have:
                            by_lab['cloud, labeller not recorded'] = by_lab.get('cloud, labeller not recorded', 0) + ok['positions']
                            total += ok['positions']
        for path in sources:
            m = self._json(path, R.manifest)
            if not m or not m['is_part'] or not isinstance(m['positions'], int):
                continue
            lab = m['labeller'] or 'unknown'
            by_lab[lab] = by_lab.get(lab, 0) + m['positions']
            total += m['positions']
            parts.append({'run': m['run'], 'labeller': lab, 'positions': m['positions'], 'at': fsread.mtime(path)})
        parts.sort(key=lambda x: x['at'] or 0)
        order = []
        for x in parts:                                   # labellers in the order their first data appeared
            if x['labeller'] not in order:
                order.append(x['labeller'])
        labellers = [{'name': n, 'positions': by_lab[n]} for n in order + [k for k in by_lab if k not in order]]
        last_part = None
        if pc['part']:
            lm = next((x for x in parts if x['run'] == pc['part']), None)
            seal = seals.get(pc['part'])
            pc['seal'] = 'sealed' if lm else (seal['state'] if seal else None)
            pc['seal_at'] = (seal or {}).get('at') if seal else (lm or {}).get('at')
            if lm and pc['state'] == 'idle':
                last_part = lm['positions']
        pc['last_positions'] = last_part
        # the cloud VM
        g = self._json(j(self.p.jobs, 'gcp', 'status.json'), R.gcp_status, optional=False)
        vm = None
        if g:
            sig = fsread.mtime(j(self.p.jobs, 'gcp', 'status.json'))
            wanted = self._json(j(self.p.jobs, 'gcp', 'wanted.json'), lambda d: d.get('wanted') if isinstance(d, dict) else None)
            rates = self._json(j(self.p.jobs, 'gcp.json'), R.gcp_rates) or {}
            eg = self._parsed(j(self.p.jobs, 'gcp', 'egress.jsonl'), lambda t: R.egress(t)[0]) or {'usd': 0, 'pulls': 0}
            run_since = None
            for e in g['events']:
                if e['name'] == g['running'] and e['event'] == 'start':
                    run_since = e['at']
            self._learn_vm_rate(g, j)
            est = None
            if g['running'] and run_since and self._vm_rate and 'filler' in (g['running'] or ''):
                est = round((now - run_since) * self._vm_rate)
            cost = None
            if g['vm']['last_start'] and g['vm']['status'] == 'RUNNING' and rates.get('usd_per_hour_running'):
                cost = round((now - g['vm']['last_start']) / 3600 * rates['usd_per_hour_running'] + eg['usd'], 2)
            vm = {'status': g['vm']['status'], 'machine_type': g['vm']['machine_type'], 'provisioning': g['vm']['provisioning'],
                  'running': g['running'], 'since': run_since, 'items': g['items'], 'wanted': wanted,
                  'status_at': sig, 'worker_error': g['worker_error'], 'last_start': g['vm']['last_start'],
                  'rate_est': round(self._vm_rate * 3600) if self._vm_rate else None, 'unpulled_est': est,
                  'verified': cloud_verified, 'chunks': cloud_chunks, 'runs': cloud_runs, 'cost_est': cost,
                  'events': g['events'][-8:]}
        # arms or any other generator job with a heartbeat log
        arms = None
        for r in (self.state.get('jobs') or {}).get('running', []):
            if r['type'] == 'datagen':
                a = R.arms_log(self._tail(j(self.p.jobs, 'jobs', r['name'] + '.log'), 1500))
                if a:
                    arms = {**a, 'job': r['name']}
        decision = self._json(j(self.p.state, 'ld-decision.json'), R.ld_decision)
        return {'pc': pc, 'vm': vm, 'labellers': labellers, 'total': total, 'parts': len(parts), 'arms': arms,
                'arms_decision': decision, 'seals': {k: v['state'] for k, v in seals.items()}}

    def _learn_vm_rate(self, g, j):
        """Positions per second of the last complete filler run: its verified positions over the time from its
        start (the UTC stamp in its name) to its stop event. Kept once learnt; None until a run qualifies."""
        stops = [e for e in g['events'] if e['event'] in ('stop', 'done', 'preempted') and e['at']]
        for name, is_dir, _, _ in fsread.listdir(self.p.data):
            filler = j(self.p.data, name, 'filler')
            for n, d, _, _ in (fsread.listdir(filler) if is_dir else []):
                m = re.search(r'(\d{8}T\d{6})Z\.ok$', n)
                if not m:
                    continue
                start = R.utc_minute(f'{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]} {m.group(1)[9:11]}:{m.group(1)[11:13]}')
                ok = self._parsed(j(filler, n), R.filler_ok, 4096)
                stop = min((e['at'] for e in stops if start and e['at'] > start), default=None)
                later = [x for x, _, _, _ in fsread.listdir(filler) if x.endswith('.ok') and x > n]
                if ok and start and stop and not later and stop - start > 3600:
                    self._vm_rate = ok['positions'] / (stop - start)

    # ------------------------------------------------------------ training

    def _training(self, now):
        j = os.path.join
        idx = (self.state.get('sprts') or {}).get('index', {})
        default = R.default_net(self._text(j(self.p.repo, 'CMakeLists.txt')))
        retrains, quota = [], None
        for top, is_dir, _, _ in fsread.listdir(self.p.data):
            if not is_dir:
                continue
            for sub, sub_dir, _, _ in fsread.listdir(j(self.p.data, top)):
                if not sub_dir or 'gate' not in sub:
                    continue
                gdir = j(self.p.data, top, sub)
                nets = {}
                for net, nd, _, _ in fsread.listdir(gdir):
                    if nd and fsread.stat(j(gdir, net, 'gates.json')):
                        g = self._json(j(gdir, net, 'gates.json'), R.gates_json, optional=False)
                        nets[net] = {'gates': g, 'at': fsread.mtime(j(gdir, net, 'gates.json'))}
                if not nets:
                    continue
                stem = sub[:-len('-gates')] if sub.endswith('-gates') else None
                sdir = j(self.p.data, top, stem + '-state') if stem and fsread.stat(j(self.p.data, top, stem + '-state')) else j(self.p.data, top)
                r = self._retrain(top, stem, sdir, nets, idx, default, now)
                if not stem and sub != 'gates':
                    r['title'] = r['id'] = top + ' ' + sub.replace('gates', '').strip('-')
                retrains.append(r)
                for n, d, mt, _ in fsread.listdir(sdir):
                    if not d and n.startswith('fetch') and n.endswith('.log'):
                        f = self._parsed(j(sdir, n), R.fetch_log, 64 * 1024)
                        if f and f['quota'] and (quota is None or mt > quota['at']):
                            quota = {**f['quota'], 'at': mt}
        retrains.sort(key=lambda r: -(r['updated'] or 0))
        others = []
        for n, d, mt, _ in fsread.listdir(self.p.state):
            if not d and n.endswith('-decision.json'):
                dec = self._json(j(self.p.state, n), R.ld_decision)
                if dec:
                    others.append({'state': 'nominal', 'name': n[:-len('-decision.json')] + ' decision', 'text': dec['verdict'], 'at': mt})
        # A Kaggle session may be running when a running job is a Kaggle job or its log names a kernel. That
        # only switches the poll on; which kernels are asked about comes from Kaggle's own list (net.py).
        prep, named, watch = [], [], False
        for r in (self.state.get('jobs') or {}).get('running', []):
            kind = (r['type'] or '') + ' ' + r['name']
            if (r.get('lock') or '').startswith('github') or (r['type'] or '').startswith('github'):
                continue
            refs = R.kernel_refs(self._tail(j(self.p.jobs, 'jobs', r['name'] + '.log'), 6000))
            if refs or re.search(r'kaggle|train|chain|upload|copies|smoke|fetch', kind):
                prep.append({'name': r['name'], 'type': r['type'], 'started': r['started'], 'live': r['live']})
            if refs or 'kaggle' in kind:
                watch = True
                named += refs
        self.wanted['kaggle'] = {'watch': watch, 'named': list(dict.fromkeys(named))}
        k = self.net.get('kaggle') or {}
        sessions = [{'ref': s['ref'].split('/', 1)[-1], 'state': s['state'], 'last_run': s['last_run'], 'at': s['at'], 'error': s['error']}
                    for s in k.get('sessions') or []]
        return {'default': default, 'retrains': retrains[:6], 'quota': quota, 'others': others, 'prep': prep,
                'sessions': sessions, 'watching': watch, 'kaggle_error': k.get('error')}

    def _retrain(self, top, stem, sdir, nets, idx, default, now):
        j = os.path.join
        has_bakes = fsread.stat(j(sdir, 'bakes.txt')) is not None
        bakes = self._parsed(j(sdir, 'bakes.txt'), R.bakes_txt, 256 * 1024) or {}
        names = sorted(nets)
        split = {}                                          # an arm is its nets' name without the seed digit
        for net in names:
            m = re.match(r'^(.*?)(\d)$', net)
            split[net] = (m.group(1), int(m.group(2))) if m else (net, None)
        stems = sorted({a for a, _ in split.values()})
        prefix = os.path.commonprefix(stems) if len(stems) > 1 else ''
        if any(len(a) <= len(prefix) for a in stems):
            prefix = ''                                     # the prefix would swallow an arm's whole name
        arms = {}
        for net in names:
            arms.setdefault(split[net][0][len(prefix):].strip('-'), []).append((split[net][1], net))
        uho_dir = j(self.p.data, 'uho-diag', 'runs')
        has_uho = any(fsread.stat(j(uho_dir, n + '.json')) for n in names)
        rows, updated = [], 0
        for arm, members in arms.items():
            cells = {k: [] for k in ('gates', 'heldout', 'bake', 'uho', 'screen', 'default', 'sprt')}
            texts, tips = [], []
            for seed, net in sorted(members, key=lambda m: (m[0] or 0, m[1])):
                g = nets[net]['gates']
                updated = max(updated, nets[net]['at'] or 0)
                cells['gates'].append('fail' if (g and g['failed']) else 'done' if g else 'wait')
                cells['heldout'].append('flag' if (g and g['flags']) else 'done' if (g and g['heldout']) else 'none')
                cells['bake'].append('done' if net in bakes else 'wait' if has_bakes else 'none')
                cells['uho'].append('done' if fsread.stat(j(uho_dir, net + '.json')) else 'wait' if has_uho else 'none')
                scr, dfl, spr = 'none', 'none', 'none'
                for name, e in idx.items():
                    if f'-{net}-vs-' not in name and not name.startswith(net + '-') and f'-{net}-' not in name + '-':
                        continue
                    drv = e['drv']
                    st = 'done' if drv['stages'] and (drv['end'] or e['verdict']) else 'run' if drv['flight'] else 'wait'
                    last = drv['stages'][-1] if drv['stages'] else None
                    if e['design'] and e['design'].get('kind') == 'network':
                        spr = 'fail' if e['verdict'].startswith(('H0', 'futility')) else st
                    elif f'-{net}-vs-' in name:
                        if default and name.endswith('-vs-' + default):
                            dfl = st
                        else:
                            scr = st if scr != 'run' else scr
                        if last and last['elo'] is not None and st == 'done':
                            texts.append((seed or 0, name.split('-vs-')[-1], last['elo'], last['elo_err']))
                    updated = max(updated, e['log_at'] or 0)
                cells['screen'].append(scr)
                cells['default'].append(dfl)
                cells['sprt'].append(spr)
                tips.append(net + (f': held-out {", ".join(str(h["ratio"]) for h in g["heldout"])} of the default' if g and g['heldout'] else ''))
            rows.append({'arm': arm, 'nets': [m[1] for m in members], 'cells': {k: self._merge(v) for k, v in cells.items()},
                         'screens': [{'seed': s, 'against': a, 'elo': e, 'err': r} for s, a, e, r in sorted(texts)],
                         'promoted': default in [m[1] for m in members], 'tip': '; '.join(tips)})
        title = top + (' ' + stem if stem else '')
        return {'id': title, 'title': title, 'updated': updated or None, 'arms': rows, 'nets': len(names),
                'gates_at': max((nets[n]['at'] or 0) for n in names) or None,
                'stages': ['Gates', 'Held-out', 'Bake', 'UHO check', 'Screens', 'Against default', 'SPRT']}

    @staticmethod
    def _merge(states):
        for s in ('fail', 'run', 'flag'):
            if s in states:
                return s
        if states and all(s == 'done' for s in states):
            return 'done'
        if 'done' in states or 'wait' in states:
            return 'wait' if 'wait' in states else 'done'
        return 'none'

    # ------------------------------------------------------------ overview

    def _overview(self, now):
        j = os.path.join
        nets = self._parsed(j(self.p.repo, 'docs', 'nets.md'), R.nets_md) or {}
        default = R.default_net(self._text(j(self.p.repo, 'CMakeLists.txt')))
        head = self._text(j(self.p.repo, '.git', 'HEAD'), 4096).strip()
        branch, commit = None, None
        m = re.match(r'^ref: refs/heads/(.+)$', head)
        if m:
            branch = m.group(1)
            commit = self._text(j(self.p.repo, '.git', 'refs', 'heads', *branch.split('/')), 4096).strip()[:7] or None
            if not commit:
                pk = re.search(r'^([0-9a-f]{40}) refs/heads/' + re.escape(branch) + r'$', self._text(j(self.p.repo, '.git', 'packed-refs')), re.M)
                commit = pk.group(1)[:7] if pk else None
        elif re.match(r'^[0-9a-f]{40}$', head):
            commit = head[:7]
        series, checks = [], []
        for name, is_dir, _, _ in fsread.listdir(self.p.gauntlet):
            if not is_dir:
                continue
            d = j(self.p.gauntlet, name)
            meta = self._parsed(j(d, 'meta.txt'), R.gauntlet_meta, 256 * 1024)
            if not meta or not meta['at']:
                continue
            if meta['kind'] == 'check':
                c = self._parsed(j(d, 'summary.md'), R.anchor_check, 512 * 1024)
                if c:
                    checks.append({'at': meta['at'], 'run': meta['run'], **c})
                continue
            o = self._parsed(j(d, 'ordo.txt'), R.ordo, 64 * 1024)
            if not o:
                continue
            s = self._parsed(j(d, 'summary.md'), R.gauntlet_summary, 512 * 1024) or {}
            series.append({'at': meta['at'], 'run': meta['run'], 'commit': meta['commit'], 'book': meta['book'],
                           'rating': o['rating'], 'err': o['error'], 'played': o['played'], 'anchors': sorted(o['anchors']),
                           'reference': s.get('reference'), 'transfer': s.get('transfer'), 'gain': s.get('gain')})
        series.sort(key=lambda x: x['at'])
        prev = None
        for g in series:
            if g['book'] != 'balanced':
                continue
            g['anchors_changed'] = prev is not None and prev != g['anchors']
            prev = g['anchors']
        for g in series:
            g['anchor_count'] = len(g.pop('anchors'))
        balanced = [g for g in series if g['book'] == 'balanced']
        latest = balanced[-1] if balanced else None
        adopt = self._adoptions(branch, commit)
        week = [a for a in adopt if a['at'] and now - a['at'] < WEEK]
        stack = []
        idx = (self.state.get('sprts') or {}).get('index', {})
        logs = {n for n, d, _, _ in fsread.listdir(self.p.night) if not d and 'stack-check' in n and n.endswith('.log')}
        for name, e in sorted(idx.items()):
            if 'stack-check' not in name or not e['drv']['stages']:
                continue
            last = e['drv']['stages'][-1]
            log = next((l for l in logs if name in l or name.replace('-stc', '') in l), None)
            total = R.stack_sum(self._text(j(self.p.night, log), 64 * 1024).split('\n', 1)[0]) if log else None
            stack.append({'name': name, 'at': last['merged'], 'sum': total, 'elo': last['elo'], 'err': last['elo_err'],
                          'games': last['games']})
        perf = self._parsed(j(self.p.repo, 'docs', 'history', 'phase-4', 'perf-log.md'), R.perf_log) or []
        decisions = self._parsed(j(self.p.repo, 'MORNING.md'), R.decisions) or []
        return {'net': default, 'net_since': nets.get('since') if nets.get('default') == default else None,
                'branch': branch, 'commit': commit, 'latest': latest, 'series': series,
                'adoptions': {'week': len(week), 'list': adopt[:40]}, 'stack': stack, 'perf': perf[-8:],
                'checks': sorted(checks, key=lambda c: c['at']),
                'decisions': decisions}

    def _adoptions(self, branch, commit):
        if not self.git_log or not branch:
            return []
        if self._adopt[0] != commit:
            try:
                text = self.git_log(self.p.repo, branch)
            except Exception:  # noqa: BLE001
                return self._adopt[1]
            out = []
            for a in R.adoptions(text):
                at = R.iso(a['date'] + 'T12:00:00-0500')
                out.append({**a, 'at': at})
            self._adopt = (commit, out)
        return self._adopt[1]

    # ------------------------------------------------------------ machine

    def _machine(self, now):
        j = os.path.join
        cpu = None
        t = self.probes.cpu_times()
        if t and self._cpu_prev:
            di, db = t[0] - self._cpu_prev[0], t[1] - self._cpu_prev[1]
            cpu = round(100.0 * db / (di + db), 1) if di + db > 0 else None
        self._cpu_prev = t
        mem = self.probes.memory() or {}
        if now - self._hist_at >= 30:
            self._hist_at = now
            if cpu is not None:
                self.hist['cpu'].append(cpu)
            if mem.get('avail') is not None:
                self.hist['avail'].append(round(mem['avail'] / 2 ** 30, 2))
            if mem.get('commit') is not None:
                self.hist['commit'].append(mem['commit'])
        out = {'cpu': cpu, 'threads': self.probes.processors(), 'mem_avail': mem.get('avail'), 'mem_total': mem.get('total'),
               'commit': mem.get('commit'), 'hist': {k: list(v) for k, v in self.hist.items()}}
        if now - self.last.get('machine_files', -1e9) >= 10:
            self.last['machine_files'] = now
            fz = self._tail(j(self.p.night, 'freezewatch.log'), 6000)
            f = R.freezewatch(fz)
            wsl = R.wslcache(self._tail(j(self.p.jobs, 'jobs', 'wsl-cache-drop2.log'), 6000)) if fsread.stat(j(self.p.jobs, 'jobs', 'wsl-cache-drop2.log')) else None
            for n, d, _, _ in fsread.listdir(j(self.p.jobs, 'jobs')) if wsl is None else []:
                if not d and n.endswith('.log') and 'cache' in n:
                    wsl = R.wslcache(self._tail(j(self.p.jobs, 'jobs', n), 6000)) or wsl
            mw = None
            for n, d, _, _ in fsread.listdir(j(self.p.jobs, 'jobs')):
                if not d and n.startswith('memwatch') and n.endswith('.log'):
                    cand = R.memwatch(self._tail(j(self.p.jobs, 'jobs', n), 8000))
                    if cand['started'] and (mw is None or (cand['started'] or 0) > (mw['started'] or 0)):
                        mw = cand
            lifted = self._text(j(self.p.jobs, 'compile.lock.lifted'), 4096).strip()
            owner = self._text(j(self.p.jobs, 'compile.lock.d', 'owner'), 4096).strip()
            day = time.strftime('%Y-%m-%d', time.gmtime(now - 5 * 3600))
            waits = R.compile_waits(self._text(j(self.p.jobs, 'compile-lock-waits.log'), 256 * 1024), day)
            queue = [n.split('-', 2)[1] if n.count('-') >= 2 else n for n, d, _, _ in fsread.listdir(j(self.p.jobs, 'compile.queue.d')) if d]
            comp = {'state': 'lifted' if lifted else 'held' if owner else 'free', 'text': (lifted or owner)[:160],
                    'at': fsread.mtime(j(self.p.jobs, 'compile.lock.lifted' if lifted else 'compile.lock.d')),
                    'queue': queue, 'waited_today': waits['seconds']}
            nps = []
            for n, d, mt, _ in fsread.listdir(j(self.p.jobs, 'nps-measure.lock')):
                if not d:
                    first = self._text(j(self.p.jobs, 'nps-measure.lock', n), 4096).split('\n', 1)[0]
                    nps.append({'who': re.split(r', started', first)[0][:80] or n, 'at': mt})
            self._machine_files = {'freeze': {'stalls': f['stall_count'], 'last_stall': f['stalls'][-1] if f['stalls'] else None,
                                              'since': f['samples'][0]['at'] if f['samples'] else None,
                                              'last': f['samples'][-1] if f['samples'] else None},
                                   'wsl': wsl, 'memwatch': mw, 'compile': comp, 'nps_lock': nps}
        out.update(getattr(self, '_machine_files', {}))
        return out

    # ------------------------------------------------------------ the ticker

    def _events(self, now):
        ev = []
        add = lambda at, state, text: ev.append({'at': at, 'state': state, 'text': text}) if at and now - at < 2 * 86400 else None  # noqa: E731
        jobs = self.state.get('jobs') or {}
        lanes = {l['job'] for l in (self.state.get('lanes') or {}).get('lanes', [])}
        for e in jobs.get('events', []):
            if e['name'] in lanes:
                continue
            if e['event'] == 'end':
                bad = e['exit_code'] not in (0, None)
                add(e['at'], 'attention' if bad else 'nominal', f"Job ended: {e['name']} (exit {e['exit_code']})")
            elif e['event'] in ('stop', 'stop-failed', 'reclaim'):
                add(e['at'], 'attention' if e['event'] == 'stop-failed' else 'idle', f"Job {e['event']}: {e['name']}")
            elif e['event'] == 'start':
                add(e['at'], 'active', f"Job started: {e['name']}" + (f" ({e['type']})" if e['type'] else ''))
        for v in (self.state.get('sprts') or {}).get('verdicts', []):
            o = v['outcome']
            res = f"{v['elo']:+.1f} \u00b1 {v['err']:.1f} Elo over {v['games']:,} games" if v['elo'] is not None and v['err'] is not None else 'no result'
            add(v['at'], 'nominal' if o['kind'] in ('passed', 'screen', 'complete') else 'idle',
                f"{o['label']}: {v['title']} ({v['klass']}), {res}".replace('+-', '\u2212').replace('-', '\u2212', 0))
        d = self.state.get('data') or {}
        for e in ((d.get('vm') or {}).get('events') or []):
            add(e['at'], 'active' if e['event'] == 'start' else 'idle', f"Cloud VM: {e['name']} {e['event']}" + (f" ({e['why']})" if e['why'] else ''))
        m = self.state.get('machine') or {}
        for dr in ((m.get('wsl') or {}).get('drops') or [])[-6:]:
            add(dr['at'], 'idle', f"WSL cache dropped: {dr['before']:,} to {dr['after'] if dr['after'] is not None else '?'} MB")
        for a in ((m.get('memwatch') or {}).get('actions') or []):
            add(a['at'], 'failure' if a['kind'] == 'alert' else 'attention', 'Memory watch' + a['text'])
        ev.sort(key=lambda e: -e['at'])
        return ev[:40]
