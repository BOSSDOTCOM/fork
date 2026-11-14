# SPDX-License-Identifier: GPL-3.0-or-later
"""The display's two network polls, on their own thread so a slow answer never delays the file readers:

  GitHub, every 2 minutes, only for the runs a lane is waiting on: the run's jobs (how many shards have
  finished), and, when the run carries per-shard progress artifacts, their pentanomial counts, from which
  the collector shows a combined result labelled "preliminary";
  Kaggle, every 5 minutes, only while a session may be running (a running job is a Kaggle job or its log
  names a kernel): the account's recent kernels from Kaggle's own list, then the state of those run in the
  last 12 hours. A kernel seen finished is not asked about again until it runs again.

Both go through procs.run (read-only commands only). Results are kept in memory; nothing is written.

Progress artifacts (the production session's, docs/research/shard-progress.md, format
fork-shard-progress/1): per shard an artifact progress-<stage>-<shard> holding progress.json, replaced while
the games run (each replacement is a new artifact id). The newest per shard is used; an id is downloaded
once, and a shard is refreshed at most every 4 minutes, which keeps the display near 250 calls an hour per
run against the login's shared 5,000. A run without them has `progress` None and the display shows
stage-end results only."""
import io
import json
import re
import threading
import time
import zipfile

import fsread
import procs
import readers as R

_PROGRESS_NAME = re.compile(r'^progress-(\d+)-(\d+)')


def repo_slug(git_config):
    """'OWNER/NAME' from a .git/config text's origin URL on github.com, or None."""
    m = re.search(r'url\s*=\s*\S*github\.com[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?\s*$', git_config or '', re.M)
    return f'{m.group(1)}/{m.group(2)}' if m else None


def shard_counts(jobs_json):
    """A run's jobs API answer -> {total, done, running, queued, failed} over its shard jobs (every job when
    none is named like a shard)."""
    try:
        jobs = json.loads(jobs_json).get('jobs')
    except (ValueError, AttributeError):
        return None
    if not isinstance(jobs, list) or not jobs:
        return None
    shard = [j for j in jobs if isinstance(j, dict) and re.search(r'shard|play|games', str(j.get('name', '')), re.I)] or \
            [j for j in jobs if isinstance(j, dict)]
    out = {'total': len(shard), 'done': 0, 'running': 0, 'queued': 0, 'failed': 0}
    for j in shard:
        if j.get('status') == 'completed':
            out['done'] += 1
            if j.get('conclusion') not in ('success', 'skipped', None):
                out['failed'] += 1
        elif j.get('status') == 'in_progress':
            out['running'] += 1
        else:
            out['queued'] += 1
    return out


def progress_artifacts(artifacts_json):
    """The newest progress artifact per (stage, shard): [{id, stage, shard}]."""
    try:
        arts = json.loads(artifacts_json).get('artifacts')
    except (ValueError, AttributeError):
        return []
    best = {}
    for a in arts if isinstance(arts, list) else []:
        m = _PROGRESS_NAME.match(str(a.get('name', ''))) if isinstance(a, dict) else None
        if not m or a.get('expired') or not isinstance(a.get('id'), int):
            continue
        key = (int(m.group(1)), int(m.group(2)))
        stamp = str(a.get('updated_at') or a.get('created_at') or '')
        if key not in best or stamp >= best[key][0]:
            best[key] = (stamp, a['id'])
    return [{'id': v[1], 'stage': k[0], 'shard': k[1]} for k, v in sorted(best.items())]


def read_progress_zip(data):
    """A progress artifact's zip (bytes, read in memory) -> readers.shard_progress of its progress.json.
    Raises ValueError when the zip or its record is not as proposed."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = next((n for n in z.namelist() if n.endswith('progress.json')), None)
            if name is None or z.getinfo(name).file_size > 65536:
                raise ValueError('no small progress.json in the artifact')
            return R.shard_progress(json.loads(z.read(name).decode('utf-8', 'replace')))
    except (zipfile.BadZipFile, KeyError, UnicodeError) as e:
        raise ValueError(f'unreadable progress artifact: {type(e).__name__}') from e


def combine(records, stage):
    """Shard records of one stage, the newest per shard -> {stage, ptnml, games, planned, shards, final, at},
    or None when there is none. planned counts the shards that have reported; `final` is how many are done."""
    newest = {}
    for r in records:
        if r['stage'] == stage and (r['shard'] not in newest or (r['seq'], r['at'] or 0) > (newest[r['shard']]['seq'], newest[r['shard']]['at'] or 0)):
            newest[r['shard']] = r
    recs = list(newest.values())
    if not recs:
        return None
    import stats
    total = max((r['shards'] or 0) for r in recs) or len(recs)
    planned = sum(r['planned'] for r in recs)
    return {'stage': stage, 'ptnml': stats.add([r['ptnml'] for r in recs]), 'games': sum(r['games'] for r in recs),
            'planned': round(planned * total / len(recs)), 'shards': len(recs), 'of': total,
            'final': sum(1 for r in recs if r['state'] == 'final'), 'at': max((r['at'] or 0) for r in recs) or None}


class Poller:
    """Fills collector.net from collector.wanted, on its own daemon thread (start()); stop() ends it."""

    def __init__(self, collector, repo, slug, gh_every=120, kaggle_every=300, execute=procs.run, clock=time.time,
                 gh=None, kaggle=None):
        self.c, self.repo, self.slug = collector, repo, slug
        self.gh_every, self.kaggle_every, self.execute, self.clock = gh_every, kaggle_every, execute, clock
        self.stopping = threading.Event()
        self.gh = gh or procs.find('gh')
        self.kaggle = kaggle or procs.find('kaggle', repo)
        self.status = {'gh': 'not polled yet' if self.gh and slug else 'off: gh or the repository name was not found',
                       'kaggle': 'not polled yet' if self.kaggle else 'off: the Kaggle tool was not found'}
        self._seen = {}            # artifact id -> parsed record (an artifact never changes once uploaded)
        self._fresh = {}           # (run, stage, shard) -> when its record was last downloaded
        self.shard_every = 240     # seconds between two downloads for one shard
        self._last = {'gh': -1e9, 'kaggle': -1e9}
        self._held = {}            # run id -> {(stage, shard): record}
        self._ended = {}           # (kernel, its last run time) -> the state it ended in
        self.thread = None

    def poll_github(self, now):
        runs = {}
        for run_id in list(self.c.wanted.get('runs') or [])[:4]:
            rc, out, err = self.execute([self.gh, 'api', f'repos/{self.slug}/actions/runs/{int(run_id)}/jobs?per_page=100'], timeout=40)
            if rc != 0:
                self.status['gh'] = f'failed: {err or rc}'
                continue
            entry = {'shards': shard_counts(out), 'progress': None, 'at': now, 'error': None}
            rc, out, err = self.execute([self.gh, 'api', f'repos/{self.slug}/actions/runs/{int(run_id)}/artifacts?per_page=100'], timeout=40)
            held = self._held.setdefault(run_id, {})         # (stage, shard) -> the newest record downloaded
            for a in progress_artifacts(out) if rc == 0 else []:
                key = (run_id, a['stage'], a['shard'])
                if a['id'] in self._seen or now - self._fresh.get(key, -1e9) < self.shard_every:
                    continue
                self._fresh[key] = now
                rc2, data, _ = self.execute([self.gh, 'api', f'repos/{self.slug}/actions/artifacts/{a["id"]}/zip'], timeout=40, binary=True)
                try:
                    rec = read_progress_zip(data) if rc2 == 0 else None
                except ValueError as e:
                    rec = None
                    entry['error'] = str(e)[:120]
                self._seen[a['id']] = rec is not None
                if rec and rec['run_id'] in (None, run_id):
                    held[(a['stage'], a['shard'])] = rec
            if held:
                entry['progress'] = combine(list(held.values()), max(r['stage'] for r in held.values()))
            runs[run_id] = entry
            self.status['gh'] = f'ok, {len(runs)} run(s)'
        if not self.c.wanted.get('runs'):
            self.status['gh'] = 'idle: no live run'
        self.c.net['runs'] = runs
        for gone in set(self._held) - set(self.c.wanted.get('runs') or []):
            del self._held[gone]                              # the run ended: its records are no longer needed
        if len(self._seen) > 4000:
            self._seen.clear()

    def poll_kaggle(self, now):
        w = self.c.wanted.get('kaggle') or {}
        if not w.get('watch'):
            self.status['kaggle'] = 'idle: no Kaggle job is running'
            self.c.net['kaggle'] = {'sessions': [], 'at': now, 'error': None}
            return
        rc, text, err = self.execute([self.kaggle] + procs.KAGGLE_LIST, timeout=60)
        rows = R.kaggle_list(text) if rc == 0 else []
        if not rows:
            self.status['kaggle'] = 'failed: ' + (fsread.scrub(err)[:120] if err else 'the kernel list could not be read')
            self.c.net['kaggle'] = dict(self.c.net.get('kaggle') or {'sessions': []}, error=self.status['kaggle'], at=now)
            return
        named = set(w.get('named') or [])
        recent = [r for r in rows if r['ref'] in named or (r['last_run'] and now - r['last_run'] < 12 * 3600)][:4]
        sessions = []
        for r in recent:
            key = (r['ref'], r['last_run'])
            state = self._ended.get(key)
            error = None
            if state is None:
                rc, text, err = self.execute([self.kaggle, 'kernels', 'status', r['ref']], timeout=60)
                state = R.kaggle_status(text) if rc == 0 else None
                if state is None:
                    error = fsread.scrub(err or 'no state in the answer')[:120]
                elif state not in ('RUNNING', 'QUEUED'):
                    self._ended[key] = state                   # finished: not asked again until it runs again
            sessions.append({'ref': r['ref'], 'state': state, 'last_run': r['last_run'], 'at': now, 'error': error})
        if len(self._ended) > 200:
            self._ended.clear()
        live = sum(1 for s in sessions if s['state'] in ('RUNNING', 'QUEUED'))
        self.status['kaggle'] = f'ok, {live} running of {len(sessions)} recent'
        self.c.net['kaggle'] = {'sessions': sessions, 'at': now, 'error': None}

    def step(self):
        now = self.clock()
        if self.gh and self.slug and now - self._last['gh'] >= self.gh_every:
            self._last['gh'] = now
            try:
                self.poll_github(now)
            except Exception as e:  # noqa: BLE001  a poll must never end the thread
                self.status['gh'] = f'failed: {type(e).__name__}'
        if self.kaggle and now - self._last['kaggle'] >= self.kaggle_every:
            self._last['kaggle'] = now
            try:
                self.poll_kaggle(now)
            except Exception as e:  # noqa: BLE001
                self.status['kaggle'] = f'failed: {type(e).__name__}'

    def _loop(self):
        while not self.stopping.wait(5):
            self.step()

    def start(self):
        self.thread = threading.Thread(target=self._loop, daemon=True, name='ops-display-net')
        self.thread.start()

    def stop(self):
        self.stopping.set()
