# SPDX-License-Identifier: GPL-3.0-or-later
"""What the read-only tabs show, gathered without changing anything: files are only opened for reading,
and commands go through runner.ReadOnly (git show/rev-parse, gh run list, the Kaggle CLI's list and status,
the WSL probe). The data-generation tab's numbers come from generation_control.py; everything else is here.

collect() returns one snapshot dict per poll; GitHub and Kaggle are asked at most every github_seconds and
kaggle_seconds, and the large docs are parsed again only when their file changes.
"""
import calendar
import glob
import importlib.util
import json
import os
import re
import shutil
import time
from pathlib import Path

import config
import parsers as P
import winutil

SECRET = re.compile(r'("?(?:key|token|password)"?\s*[:=]\s*)"?[^"\s,}]+', re.I)
HEX32 = re.compile(r'\b[0-9a-f]{32,}\b')


def redact(text):
    """Error text from a CLI, with anything shaped like a credential removed (the Kaggle token is never
    shown)."""
    return HEX32.sub('[redacted]', SECRET.sub(r'\1[redacted]', text or ''))


def read_text(path, limit=None):
    try:
        with open(path, 'rb') as f:
            if limit:
                f.seek(0, 2)
                n = f.tell()
                f.seek(max(0, n - limit))
            return f.read().decode('utf-8', 'replace')
    except OSError:
        return None


def read_json(path):
    t = read_text(path)
    try:
        return json.loads(t) if t is not None else None
    except ValueError:
        return None


def find_gh():
    exe = shutil.which('gh')
    if exe:
        return exe
    base = os.environ.get('LOCALAPPDATA', '')
    hits = glob.glob(os.path.join(base, 'Microsoft', 'WinGet', 'Packages', 'GitHub.cli_*', 'bin', 'gh.exe'))
    return hits[0] if hits else 'gh'


class Collector:
    def __init__(self, cfg, ro, state=None, now=time.time, jobctl=None, cpu_times=winutil.cpu_times,
                 memory=winutil.memory, disk=winutil.disk, gh=None):
        self.cfg, self.ro, self.now = cfg, ro, now
        self.state = Path(state or config.state_dir())
        self.repo = config.expand(cfg['repo'])
        self.jobctl = jobctl if jobctl is not None else self._load_jobctl()
        self.cpu_times, self.memory, self.disk = cpu_times, memory, disk
        self.gh = gh or find_gh()
        self._docs = {}
        self._cpu_prev = None
        self._github = (0, None)
        self._kaggle = (0, None)
        self._datasets = (0, None)

    def _load_jobctl(self):
        path = self.repo / 'tools' / 'jobs' / 'jobctl.py'
        try:
            spec = importlib.util.spec_from_file_location('fork_jobctl_ro', path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        except Exception:  # noqa: BLE001
            return None

    def doc(self, rel, parse):
        """A repo file parsed once per change of its mtime."""
        path = self.repo / rel
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None
        key = (rel, parse.__name__)
        hit = self._docs.get(key)
        if hit and hit[0] == mtime:
            return hit[1]
        value = parse(read_text(path) or '')
        self._docs[key] = (mtime, value)
        return value

    # ------------------------------------------------------------ jobs

    def windows_jobs(self):
        root = config.expand(self.cfg['windows_jobs'])
        out = []
        for f in sorted((root / 'jobs').glob('*.json')) if (root / 'jobs').is_dir() else []:
            rec = read_json(f)
            if not isinstance(rec, dict) or 'name' not in rec:
                continue
            live = []
            if self.jobctl is not None:
                try:
                    live = self.jobctl.live(rec)
                except Exception:  # noqa: BLE001
                    live = []
            out.append({'record': rec, 'live': live})
        return out

    def windows_locks(self):
        root = config.expand(self.cfg['windows_jobs']) / 'locks'
        return [{'type': f.stem, **(read_json(f) or {})} for f in sorted(root.glob('*.json'))] if root.is_dir() else []

    def jobs(self, probe, wjobs, now):
        rows = []
        for where, jobs in (('Windows', wjobs), ('WSL', (probe or {}).get('jobs', []))):
            for j in jobs:
                r = P.job_row(j['record'], j['live'], now)
                r['supervisor'] = where
                if r['type'] == 'measure' and r['log']:
                    text = read_text(r['log'], 16384) if where == 'Windows' else None
                    r['progress'] = P.measure_progress(text or '') if text is not None else None
                rows.append(r)
        rows.sort(key=lambda r: (not r['processes'], -(r['started'] or 0)))
        locks = [dict(lk, supervisor='Windows') for lk in self.windows_locks()]
        locks += [dict(lk, supervisor='WSL') for lk in (probe or {}).get('locks', [])]
        return rows, locks

    # ------------------------------------------------------------ testing

    def sprts(self, wjobs):
        """Every SPRT in the driver logs of the github and queue jobs, newest last; the current one is the
        running github job's latest."""
        found, current = [], None
        for j in sorted(wjobs, key=lambda j: P.iso_epoch(j['record'].get('started')) or 0):
            rec = j['record']
            if rec.get('type') not in ('github', 'queue') or not rec.get('log'):
                continue
            text = read_text(rec['log'], 256 * 1024)
            if not text:
                continue
            states = [P.sprt_state(s) for s in P.driver_log(text).values()]
            for s in states:
                s['job'], s['job_live'] = rec['name'], bool(j['live'])
            found.extend(states)
            if j['live'] and rec.get('type') == 'github' and states:
                current = states[-1]
        if current is None and found:
            current = found[-1]
        return found, current

    def github(self, force=False):
        at, cached = self._github
        if cached is not None and not force and self.now() - at < self.cfg['github_seconds']:
            return cached
        fields = 'databaseId,displayTitle,status,conclusion,workflowName,headBranch,createdAt,url'
        r = self.ro.read([self.gh, 'run', 'list', '--limit', '15', '--json', fields], timeout=40)
        c = self.ro.read([self.gh, 'run', 'list', '--workflow', 'ci.yml', '--limit', '6', '--json', fields],
                         timeout=40)
        value = {'runs': P.gh_runs(r.out) if r.rc == 0 else [], 'ci': P.gh_runs(c.out) if c.rc == 0 else [],
                 'error': None if r.rc == 0 else redact(r.err.strip())[:300], 'at': self.now()}
        self._github = (self.now(), value)
        return value

    # ------------------------------------------------------------ training

    def kaggle(self, force=False):
        at, cached = self._kaggle
        if cached is not None and not force and self.now() - at < self.cfg['kaggle_seconds']:
            return cached
        exe = str(config.expand(self.cfg['kaggle']))
        r = self.ro.read([exe, 'kernels', 'list', '--mine', '--sort-by', 'dateRun', '--page-size',
                          str(self.cfg['kaggle_kernels']), '--csv'], timeout=60)
        kernels, error = [], None
        if r.rc == 0:
            kernels = P.kaggle_list(r.out)
            for k in kernels:
                s = self.ro.read([exe, 'kernels', 'status', k['ref']], timeout=60)
                k['status'] = P.kaggle_status(s.out) if s.rc == 0 else None
        else:
            error = redact((r.err or r.out).strip())[:300]
        value = {'kernels': kernels, 'error': error, 'at': self.now()}
        self._kaggle = (self.now(), value)
        return value

    def training_runs(self, limit=20):
        root = config.expand(self.cfg['training_out'])
        out = []
        for f in glob.glob(str(root / '*' / 'result' / '*' / 'run.json')):
            rec = read_json(f)
            if not isinstance(rec, dict):
                continue
            t = P.training_run(rec)
            t['folder'] = f'{Path(f).parent.parent.parent.name}/{Path(f).parent.name}'
            t['mtime'] = os.path.getmtime(f)
            out.append(t)
        out.sort(key=lambda t: -t['mtime'])
        return out[:limit]

    # ------------------------------------------------------------ networks and strength

    def networks(self):
        nets = self.doc('docs/nets.md', P.nets_md) or {'nets': [], 'default': None, 'entries': []}
        gauntlets = list(self.doc('docs/DESIGN.md', P.decision_gauntlets) or [])
        root = config.expand(self.cfg['gauntlets'])
        known = {g['run'] for g in gauntlets if g.get('run')}
        for d in sorted(root.glob('run-*')) if root.is_dir() else []:
            row = P.ordo(read_text(d / 'ordo.txt') or '')
            run = int(d.name.split('-')[1]) if d.name.split('-')[1].isdigit() else None
            if row and run not in known:
                # The run's own time from tools/gauntlet/archive.sh's meta.txt, else the folder's.
                created = re.search(r'^created_at\t(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\r?$', read_text(d / 'meta.txt') or '', re.M)
                when = calendar.timegm(time.strptime(created[1], '%Y-%m-%dT%H:%M:%SZ')) if created else d.stat().st_mtime
                gauntlets.append({'date': time.strftime('%Y-%m-%d', time.localtime(when)),
                                  'rating': row['rating'], 'error': row['error'] or 0,
                                  'title': f'{d.name} (local Ordo table)', 'run': run})
        gauntlets.sort(key=lambda g: g['date'])
        log = self.doc('docs/history/phase-4/sprt-log.md', P.sprt_log) or []
        return {'nets': nets, 'gauntlets': gauntlets, 'gains': P.sprt_gains(log), 'sprt_log': log}

    # ------------------------------------------------------------ data

    def datasets(self):
        at, cached = self._datasets
        if cached is not None and self.now() - at < 600:
            return cached
        exe = str(config.expand(self.cfg['kaggle']))
        r = self.ro.read([exe, 'datasets', 'list', '--mine', '--csv', '--page-size', '100'], timeout=60)
        value = P.kaggle_datasets(r.out) if r.rc == 0 else None
        self._datasets = (self.now(), value)
        return value

    def data(self, probe, with_kaggle=True):
        parts = {}
        dirs = [self.repo / 'data' / 'manifests']
        if self.cfg.get('manifests_out'):
            dirs.append(config.expand(self.cfg['manifests_out']))
        for d in dirs:
            for f in sorted(Path(d).glob('g*.json')):
                m = read_json(f)
                if P.is_part_manifest(m):
                    s = P.manifest_summary(m)
                    s['sealed'] = True
                    s['committed_in'] = str(f.parent)
                    parts[m['run']] = s
        copies = config.expand(self.cfg['copies'])
        for f in sorted(copies.glob('g*/g*.json')) if copies.is_dir() else []:
            if f.stem != f.parent.name or f.stem in parts or not P.part_key(f.stem):
                continue
            m = read_json(f) or {}
            parts[f.stem] = {'run': f.stem, 'generation': P.part_key(f.stem)[0], 'games': m.get('games'),
                             'positions': m.get('positions'), 'sealed': False, 'net': P.net_of(m.get('evaluator')),
                             'seed': (m.get('settings') or {}).get('seed'), 'files': [s['file'] for s in
                                                                                     m.get('shards', [])]}
        wsl_root = (probe or {}).get('folders', {}).get(self.cfg['wsl_data']) or {}
        wsl_dirs = {f['name'] for f in wsl_root.get('files', []) if f.get('dir')}
        ds = self.datasets() if with_kaggle else None
        for name, s in parts.items():
            where = []
            if P.part_dir(name) in wsl_dirs:
                where.append(f"WSL {self.cfg['wsl_data']}/{P.part_dir(name)}")
            c = copies / name
            if c.is_dir():
                n = len(list(c.glob('*.vf')))
                where.append(f'C: copies ({n} shards)')
            if ds:
                hits = [r for r in ds if r.split('/')[-1] == f'fork-{name}']
                where += [f'Kaggle {h}' for h in hits]
            s['where'] = where
        return sorted(parts.values(), key=lambda s: P.part_key(s['run']))

    # ------------------------------------------------------------ machine

    def machine(self, probe):
        out = {'warnings': []}
        t = self.cpu_times()
        if t and self._cpu_prev:
            di, db = t[0] - self._cpu_prev[0], t[1] - self._cpu_prev[1]
            out['cpu'] = 100.0 * db / (di + db) if di + db > 0 else None
        self._cpu_prev = t
        out['memory'] = self.memory()
        out['c_disk'] = self.disk(str(Path.home().anchor or Path.home()))
        mi = P.meminfo((probe or {}).get('meminfo') or '')
        out['wsl_memory'] = ({'total': mi['MemTotal'], 'available': mi.get('MemAvailable', 0)}
                             if 'MemTotal' in mi else None)
        out['wsl_disk'] = (probe or {}).get('disk')
        out['wsl_load'] = (probe or {}).get('loadavg')
        warn_gb = self.cfg['disk_warn_gb']
        if out['c_disk'] and out['c_disk']['free'] < warn_gb * 1e9:
            out['warnings'].append(f'Low disk: C: has less than {warn_gb} GB free')
        if out['wsl_disk'] and out['wsl_disk']['free'] < warn_gb * 1e9:
            out['warnings'].append(f"Low disk: WSL's disk has less than {warn_gb} GB free")
        if out['memory'] and out['memory']['load'] >= self.cfg['memory_warn_percent']:
            out['warnings'].append(f"Memory pressure: Windows memory load at or above "
                                   f"{self.cfg['memory_warn_percent']}%")
        wm = out['wsl_memory']
        if wm and wm['total'] and wm['available'] / wm['total'] < 0.10:
            out['warnings'].append('Memory pressure: WSL has less than 10% of its memory available')
        return out

    # ------------------------------------------------------------ roadmap

    def roadmap(self):
        return self.doc('docs/DESIGN.md', P.checklist) or {'title': '', 'groups': [], 'order': []}

    # ------------------------------------------------------------ all of it

    def state_files(self):
        seals, messages, stops = {}, {}, []
        root = self.state / 'parts'
        for d in sorted(root.iterdir()) if root.is_dir() else []:
            r = read_json(d / 'seal-result.json')
            if r:
                seals[d.name], messages[d.name] = r.get('state'), r.get('message', '')
            if (d / 'stop.json').exists():
                stops.append(d.name)
        return seals, messages, stops

    def collect(self, probe, probe_error=None, with_network=True):
        now = self.now()
        wjobs = self.windows_jobs()
        rows, locks = self.jobs(probe, wjobs, now)
        sprts, current = self.sprts(wjobs)
        snap = {'at': now, 'probe_error': probe_error, 'jobs': rows, 'locks': locks, 'sprts': sprts,
                'current_sprt': current, 'machine': self.machine(probe), 'roadmap': self.roadmap(),
                'networks': self.networks(), 'training_runs': self.training_runs(),
                'queue': [j for j in rows if j['type'] == 'queue' and j['processes']]}
        snap['warnings'] = snap['machine']['warnings']
        if with_network:
            snap['github'] = self.github()
            snap['kaggle_info'] = self.kaggle()
        snap['kaggle'] = {k['ref']: k.get('status') for k in (snap.get('kaggle_info') or {}).get('kernels', [])}
        snap['data'] = self.data(probe, with_kaggle=with_network)
        snap['seals'], snap['seal_messages'], snap['expected_stops'] = self.state_files()
        return snap
