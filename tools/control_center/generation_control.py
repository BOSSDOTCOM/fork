# SPDX-License-Identifier: GPL-3.0-or-later
"""The Control Center's only controls: data generation (DESIGN.md section 5.3, deliverable 2, and its
labeller policy).

- plan(): the next part of the current generation: its name (the next letter), the current default engine
  (the default network and every adopted change: the tip of `branch`; a PGO build of it, or the previous
  part's own binary when no engine file changed since that binary's commit), the standing settings, the
  next unused local seed, and the rest of the generation's target (the previous part's target minus what it
  generated). The openings are the previous part's, or the book chosen for the next parts with
  set_next_openings() (next-openings.json in the state folder, its SHA-256 checked against its manifest in
  the repo). preflight() refuses while any data-generation job lives (either supervisor), when the disk
  margin (config.py) is not met, or when the openings' WSL copy is missing or hashes differently.
- start(): writes the part's launch files into the state folder and starts `start_part.sh` through the WSL
  supervisor (jobctl.py start datagen NAME), then the watchdog (watchdog.py: keeps Windows awake and runs
  the auto-stop).
- stop_and_seal(): `jobctl.py stop NAME` (the whole tree, verified), then a seal job under the Windows
  supervisor (seal_part.py: each worker's complete games copied, every game verified, sealed with its
  manifest; a failed verification is reported and every file kept).
- A part that is already running (started by hand, like g3e) is attached: its settings are read from
  fork_datagen's command line and recorded in the state folder for the seal.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import config
import parsers as P
import winutil
from runner import PROBE

HERE = Path(__file__).resolve().parent
LOCAL_SEED_LIMIT = 10 ** 12  # cloud seeds start 10^12 apart from every local run (DESIGN.md, 2026-10-30)
NEXT_OPENINGS = 'next-openings.json'  # in the state folder: the openings book the next parts start from


class Refused(Exception):
    """A control that will not run, with the reason the app shows."""


def gb(n):
    return f'{n / 1e9:,.1f} GB'


class GenerationControl:
    def __init__(self, cfg, runner, state=None, windows_jobs=None, disk=winutil.disk, now=time.time,
                 spawn=None, pid_alive=winutil.pid_alive):
        self.cfg, self.runner = cfg, runner
        self.state = Path(state or config.state_dir())
        self.repo = config.expand(cfg['repo'])
        self.jobctl_win = self.repo / 'tools' / 'jobs' / 'jobctl.py'
        self.jobctl_wsl = config.to_wsl(self.jobctl_win)
        self.python = config.expand(cfg['python'])
        self.windows_jobs = windows_jobs or (lambda: [])
        self.disk, self.now, self.pid_alive = disk, now, pid_alive
        self.spawn = spawn or self._spawn
        self.manifest_dirs = [self.repo / 'data' / 'manifests']
        if cfg.get('manifests_out'):
            self.manifest_dirs.append(config.expand(cfg['manifests_out']))

    # ------------------------------------------------------------ reading

    def wsl(self, *cmd):
        return ['wsl.exe', '-d', self.cfg['wsl_distro'], '--exec', *cmd]

    def probe(self, folders=()):
        r = self.runner.read(self.wsl('python3', '-I', '-', self.jobctl_wsl, self.cfg['wsl_jobs'],
                                      self.cfg['wsl_data'], *folders),
                             timeout=45, input=PROBE.read_text(encoding='utf-8'))
        if r.rc != 0:
            raise RuntimeError(f'WSL probe failed ({r.rc}): {(r.err or r.out).strip()[:300]}')
        return json.loads(r.out)

    def git(self, *args):
        return self.runner.read(['git', '-C', str(self.repo), *args], timeout=30)

    def part_state(self, name):
        return self.state / 'parts' / name

    def read_state(self, name, file):
        try:
            return json.loads((self.part_state(name) / file).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None

    def write_state(self, name, file, data):
        d = self.part_state(name)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / (file + '.tmp')
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding='utf-8')
        os.replace(tmp, d / file)

    def sealed(self):
        """{part: manifest} of every sealed local part."""
        out = {}
        for d in self.manifest_dirs:
            for f in sorted(Path(d).glob('g*.json')):
                try:
                    m = json.loads(f.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    continue
                if P.is_part_manifest(m):
                    out[m['run']] = m
        return out

    def snapshots(self):
        """{part: run json} of each part copied (complete games) but maybe not sealed yet."""
        out = {}
        root = config.expand(self.cfg['copies'])
        for f in sorted(Path(root).glob('g*/g*.json')) if root and root.is_dir() else []:
            if f.stem == f.parent.name and P.part_key(f.stem):
                try:
                    out[f.stem] = json.loads(f.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    pass
        return out

    @staticmethod
    def live_datagen(probe, windows_jobs):
        """Every data-generation job with a live process, from both supervisors, and every lock of type
        datagen whose job still lives."""
        live = []
        for where, jobs in (('WSL', probe.get('jobs', [])), ('Windows', windows_jobs)):
            for j in jobs:
                rec = j['record']
                if rec.get('type') == 'datagen' and j['live']:
                    live.append(f"{rec.get('name')} ({where}, processes {j['live']})")
        return live

    def running(self, probe):
        """The running part (attached if needed) with its live numbers, or the most recent datagen job."""
        jobs = [j for j in probe.get('jobs', []) if j['record'].get('type') == 'datagen']
        if not jobs:
            return None
        live = [j for j in jobs if j['live']]
        best = max(live or jobs, key=lambda j: P.iso_epoch(j['record'].get('started')) or 0)
        rec = best['record']
        name = rec['name']
        dg = next((d for d in probe.get('datagen', []) if d.get('name') == name), {})
        log = P.datagen_log(dg.get('log_tail') or '')
        settings, paths = P.datagen_args(dg.get('cmdline') or [])
        part = self.read_state(name, 'part.json')
        if dg.get('cmdline') and (part is None or not part.get('cmdline')):
            part = dict(part or {}, name=name, cmdline=dg['cmdline'], settings=settings, paths=paths,
                        attached=part is None, dir=dg.get('dir'), recorded=self.now())
            self.write_state(name, 'part.json', part)
        if part and not settings:
            settings = part.get('settings', {})
        now = self.now()
        start = P.iso_epoch(rec.get('started'))
        end = P.iso_epoch(rec.get('ended') or rec.get('stopped'))
        last = log['last'] or {}
        target = settings.get('positions_target')
        if best['live'] and dg.get('pid'):
            phase = 'generating'
        elif best['live']:
            phase = 'preparing (build, bench check)'
        else:
            phase = rec.get('state', '?')
        return {
            'name': name, 'live': best['live'], 'phase': phase, 'record': rec, 'dir': dg.get('dir'),
            'started': start, 'elapsed': ((end or now) - start) if start else None,
            'games': last.get('games'), 'positions': last.get('positions'), 'rate': last.get('rate'),
            'recent_rate': log['recent_rate'], 'log_seconds': last.get('seconds'), 'done': log['done'],
            'target': target, 'seed': settings.get('seed'), 'threads': settings.get('threads'),
            'progress': (last.get('positions') or 0) / target if target else None,
            'engine': (dg.get('job_log_head') or '').splitlines()[0] if dg.get('job_log_head') else None,
            'job_log_tail': dg.get('job_log_tail'), 'autostop': self.read_state(name, 'autostop.json'),
            'seal': self.seal_status(name), 'finished_run_json': dg.get('run_json'),
        }

    def seal_status(self, name):
        res = self.read_state(name, 'seal-result.json')
        job = next((j for j in self.windows_jobs() if j['record'].get('name') == f'seal-{name}'), None)
        if job is None and res is None:
            return None
        return {'result': res, 'job_state': job['record'].get('state') if job else None,
                'job_live': bool(job and job['live'])}

    # ------------------------------------------------------------ the next part

    def plan(self, probe=None, threads=None, new_generation=None):
        """(plan, probe): the next part, and a probe that also looked at the previous part's folder (its
        binaries, for reuse) and the new part's (which must be empty). new_generation (a positions target,
        the owner's decision) plans instead the first part of the next generation, once the current one has
        reached its target and its last part is sealed: always a fresh PGO build of the branch tip, and the
        previous part's openings unless the next openings are set."""
        probe = probe or self.probe()
        plan = self._plan(probe, threads, new_generation)
        folders = [plan['dir'], f"{self.cfg['wsl_data']}/{P.part_dir(plan['previous'])}"]
        if not all(f in (probe.get('folders') or {}) for f in folders):
            probe = self.probe(folders)
            plan = self._plan(probe, threads, new_generation)
        return plan, probe

    def _plan(self, probe, threads=None, new_generation=None):
        sealed, snaps = self.sealed(), self.snapshots()
        names = set(sealed) | set(snaps)
        names |= {j['record']['name'] for j in probe.get('jobs', []) if j['record'].get('type') == 'datagen'
                  and P.part_key(j['record'].get('name', ''))}
        if not names:
            raise Refused('no earlier local part found')
        gen = max(P.part_key(n)[0] for n in names)
        last = max((n for n in names if P.part_key(n)[0] == gen), key=P.part_key)
        seal = self.read_state(last, 'seal-result.json') or {}
        if last not in sealed and seal.get('state') in ('verify-failed', 'failed'):
            raise Refused(f"the seal of {last} ended '{seal['state']}': {seal.get('message', '')[:300]}; resolve it "
                          'before the next part starts')
        if last in sealed:
            info, source = sealed[last], 'sealed manifest'
        elif last in snaps:
            info, source = snaps[last], 'copy (not sealed yet)'
        else:
            raise Refused(f'the last part, {last}, is neither sealed nor copied yet: stop and seal it first')
        st = info.get('settings', {})
        target = st.get('positions_target', 0) - info.get('positions', 0)
        if new_generation is not None:
            if target > 0:
                raise Refused(f'generation {gen} has {target:,} positions to go after {last}: its next part comes '
                              'before a new generation')
            if last not in sealed:
                raise Refused(f'{last} is not sealed yet: seal it before a new generation starts')
            if not isinstance(new_generation, int) or new_generation <= 0:
                raise Refused(f'a new generation needs a positive positions target, not {new_generation!r}')
            target = new_generation
        elif target <= 0:
            raise Refused(f'generation {gen} reached its target with {last}; a new generation is the owner\'s '
                          'decision')
        seeds = [m.get('settings', {}).get('seed') for m in list(sealed.values()) + list(snaps.values())]
        for j in probe.get('jobs', []):
            s, _ = P.datagen_args((next((d for d in probe.get('datagen', []) if d['name'] == j['record'].get(
                'name')), {}) or {}).get('cmdline') or [])
            seeds.append(s.get('seed'))
        for f in (self.state / 'parts').glob('*/part.json') if (self.state / 'parts').is_dir() else []:
            try:
                seeds.append(json.loads(f.read_text(encoding='utf-8')).get('settings', {}).get('seed'))
            except (OSError, ValueError):
                pass
        seeds = [s for s in seeds if isinstance(s, int) and s < LOCAL_SEED_LIMIT]
        if not seeds:
            raise Refused('no earlier local seed found')
        seed = max(seeds) + 1

        branch = self.cfg['branch']
        r = self.git('rev-parse', branch)
        if r.rc != 0:
            raise Refused(f'git rev-parse {branch} failed: {r.err.strip()}')
        commit = r.out.strip()
        r = self.git('show', f'{branch}:CMakeLists.txt')
        net = P.default_net(r.out) if r.rc == 0 else None
        if not net:
            raise Refused(f'the default network of {branch} could not be read from CMakeLists.txt')
        r = self.git('show', f'{branch}:tests/bench-{net}.ref')
        ref = P.bench_expected(r.out) if r.rc == 0 else {}
        if 'nodes' not in ref or 'signature' not in ref:
            raise Refused(f'tests/bench-{net}.ref on {branch} has no nodes and signature')
        version = (info.get('generator') or {}).get('version') or info.get('version') or ''
        prev_commit = (re.search(r'\+([0-9a-f]{7,40})', version) or [None, None])[1]
        prev_net = P.net_of((info.get('generator') or {}).get('evaluator') or info.get('evaluator'))
        changed = True
        if prev_commit and prev_net == net and new_generation is None:  # a new generation always builds
            d = self.git('diff', '--quiet', prev_commit, commit, '--', *self.cfg['engine_paths'])
            changed = d.rc != 0  # 0: no engine file differs; 1: differs; anything else: unknown, so build
        prev_dir = f"{self.cfg['wsl_data']}/{P.part_dir(last)}"
        reuse_ok = False
        if not changed:
            f = (probe.get('folders') or {}).get(prev_dir) or {}
            have = {x['name'] for x in f.get('files', [])}
            reuse_ok = {'fork', 'fork_datagen'} <= have
        openings = info.get('openings') or {}
        prev_ofile = openings.get('file') or st.get('openings')
        prev_osha = openings.get('sha256')
        if not prev_ofile:  # a copy's run json may not name them: the generation's last sealed part's openings
            same = [m for k, m in sealed.items() if P.part_key(k)[0] == gen]
            if not same:
                raise Refused(f'no openings known for {last}')
            m = max(same, key=lambda m: P.part_key(m['run']))
            prev_ofile, prev_osha = m['openings']['file'], m['openings']['sha256']
        openings = self.next_openings()  # the owner's choice for the next parts, if any
        if openings:
            om = self._openings_manifest(openings['file'])
            if om['output_sha256'] != openings['sha256']:
                raise Refused(f"{NEXT_OPENINGS} gives the SHA-256 {openings['sha256']} for {openings['file']}, its "
                              f"manifest {om['output_sha256']}")
            ofile, osha = openings['file'], openings['sha256']
            osource = f"{NEXT_OPENINGS} (set {P.est(openings.get('set_at'))})"
        else:  # the previous part's; its manifest must be in the repo (the seal reads it)
            om = self._openings_manifest(prev_ofile)
            if prev_osha and prev_osha != om['output_sha256']:
                raise Refused(f"{last} used {prev_ofile} with the SHA-256 {prev_osha}, its manifest gives "
                              f"{om['output_sha256']}")
            ofile, osha, osource = prev_ofile, om['output_sha256'], f'previous part ({last})'
        standing = dict(self.cfg['standing'])
        settings = {**standing, 'threads': int(threads or self.cfg['threads']), 'seed': seed,
                    'positions_target': target, 'openings': ofile}
        differs = {k: (st.get(k), v) for k, v in standing.items() if st.get(k) != v}
        name = f'g{gen + 1}' if new_generation is not None else P.next_part(last)
        if new_generation is not None:
            gen += 1
        if ofile != prev_ofile:
            differs['openings'] = (prev_ofile, ofile)
        return {
            'name': name, 'generation': gen, 'previous': last, 'previous_source': source,
            'previous_positions': info.get('positions'), 'previous_target': st.get('positions_target'),
            'branch': branch, 'commit': commit, 'net': net, 'bench_nodes': ref['nodes'],
            'bench_signature': ref['signature'],
            'mode': 'reuse' if reuse_ok else 'build', 'engine_commit': prev_commit if reuse_ok else commit,
            'engine_changed': changed, 'reuse_dir': prev_dir if reuse_ok else None,
            'dir': f"{self.cfg['wsl_data']}/{P.part_dir(name)}", 'openings': ofile, 'openings_sha256': osha,
            'openings_source': osource,
            'settings': settings, 'differs_from_previous': differs,
            'need_bytes': int(target * self.cfg['bytes_per_position']),
        }

    def next_openings(self):
        """The openings book chosen for the next parts ({file, sha256, set_at, reason}), or None: the previous
        part's. A file that is there but unreadable refuses, never falling back to the old book."""
        f = self.state / NEXT_OPENINGS
        if not f.exists():
            return None
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError) as e:
            raise Refused(f'{f} is unreadable ({e}); fix or clear it') from None
        if not isinstance(data, dict) or not data.get('file') or not data.get('sha256'):
            raise Refused(f'{f} does not name a file and its sha256; fix or clear it')
        return data

    def set_next_openings(self, file, sha256=None, reason=''):
        """Chooses the openings book of the next parts (None: the previous part's again). The book needs its
        manifest in the repo (data/manifests/openings-<name>.json) with this SHA-256; its WSL copy is checked
        by the preflight."""
        f = self.state / NEXT_OPENINGS
        if file is None:
            try:
                f.unlink()
            except FileNotFoundError:
                pass
            return None
        if not file or any(c in file for c in '/\\') or '..' in file:
            raise Refused(f'give the openings file by its name, not a path: {file!r}')
        om = self._openings_manifest(file)
        if not re.fullmatch(r'[0-9a-f]{64}', str(sha256 or '')):
            raise Refused("give the openings' SHA-256 (64 hex digits) to check against their manifest")
        if sha256 != om['output_sha256']:
            raise Refused(f"the SHA-256 {sha256} is not the manifest's {om['output_sha256']} for {file}")
        data = {'file': file, 'sha256': sha256, 'set_at': self.now(), 'reason': reason}
        self.state.mkdir(parents=True, exist_ok=True)
        tmp = self.state / (NEXT_OPENINGS + '.tmp')
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding='utf-8')
        os.replace(tmp, f)
        return data

    def _openings_manifest(self, file):
        """The repo's manifest of an openings book, which the seal needs too."""
        f = self.repo / 'data' / 'manifests' / f'openings-{Path(file).stem}.json'
        try:
            om = json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError) as e:
            raise Refused(f'the openings {file} have no readable manifest {f.name} in the repo ({type(e).__name__}); '
                          'commit it first (the seal needs it)') from None
        if om.get('output') != file or not om.get('output_sha256') or not om.get('positions'):
            raise Refused(f'{f.name} is not the manifest of {file} (output, output_sha256, positions)')
        return om

    def _wsl_openings_path(self, plan, home):
        return f"{self.cfg['openings_wsl'].replace('~', home, 1)}/{plan['openings']}"

    def preflight(self, plan, probe):
        """The reasons a start is refused (none: it may start)."""
        why = []
        live = self.live_datagen(probe, self.windows_jobs())
        if live:
            why.append('a data-generation job is running: ' + '; '.join(live))
        for lk in probe.get('locks', []):
            if lk.get('type') == 'datagen':
                holder = next((j for j in probe.get('jobs', []) if j['record'].get('id') == lk.get('id')), None)
                if holder is None or holder['live']:
                    why.append(f"the WSL datagen lock is held by {lk.get('name')}")
        f = (probe.get('folders') or {}).get(plan['dir']) or {}
        if f.get('exists') and f.get('files'):
            why.append(f"{plan['dir']} already holds files")
        reserve = self.cfg['disk_reserve_gb'] * 1e9
        need = plan['need_bytes']
        wsl_disk = probe.get('disk')
        if not wsl_disk:
            why.append("WSL's free space could not be read")
        elif wsl_disk['free'] < need + reserve:
            why.append(f"WSL has {gb(wsl_disk['free'])} free; the part needs {gb(need)} plus the "
                       f"{gb(reserve)} margin")
        cdisk = self.disk(str(Path.home().anchor or Path.home()))
        if not cdisk:
            why.append('the free space of C: could not be read')
        elif cdisk['free'] < 2 * need + reserve:
            why.append(f"C: has {gb(cdisk['free'])} free; the part needs {gb(2 * need)} (WSL's disk and the "
                       f"sealed copy) plus the {gb(reserve)} margin")
        if self.read_state(plan['name'], 'part.json'):
            why.append(f"{plan['name']} was started before (state folder {self.part_state(plan['name'])})")
        p = self._wsl_openings_path(plan, probe['home'])  # the file start_part.sh checks and fork_datagen reads
        r = self.runner.read(self.wsl('sha256sum', p), timeout=300)
        x = r.out.split()[0] if r.rc == 0 and r.out.split() else None
        if x is None:
            why.append(f"the openings {p} could not be hashed in WSL ({r.rc}): {(r.err or r.out).strip()[:200]}")
        elif x != plan['openings_sha256']:
            why.append(f"the openings {p} in WSL hash to {x}, the plan wants {plan['openings_sha256']}")
        return why

    # ------------------------------------------------------------ controls

    def start(self, plan, probe, auto_stop_hours=None):
        why = self.preflight(plan, probe)
        if why:
            raise Refused('; '.join(why))
        name = plan['name']
        home = probe['home']
        d = self.part_state(name)
        d.mkdir(parents=True, exist_ok=True)
        st = plan['settings']
        params = {
            'NAME': name, 'DIR': plan['dir'].replace('~', home, 1), 'MODE': plan['mode'],
            'REUSE_DIR': (plan['reuse_dir'] or '').replace('~', home, 1), 'REPO': config.to_wsl(self.repo),
            'BRANCH': plan['branch'], 'COMMIT': plan['commit'], 'ENGINE_COMMIT': plan['engine_commit'],
            'NET': plan['net'], 'WANT_NODES': plan['bench_nodes'], 'WANT_SIGNATURE': plan['bench_signature'],
            'CLONE': self.cfg['wsl_build_clone'].replace('~', home, 1),
            'BUILDS': f"{self.cfg['wsl_data'].replace('~', home, 1)}/{name}-builds/pgo",
            'OPENINGS': self._wsl_openings_path(plan, home),
            'OPENINGS_SHA256': plan['openings_sha256'], 'TABLES': self.cfg['tables_wsl'].replace('~', home, 1),
            'POSITIONS': st['positions_target'], 'NODES': st['nodes'], 'THREADS': st['threads'],
            'SEED': st['seed'], 'HASH_MB': st['hash_mb'], 'SHARD_MB': st['shard_mb'],
            'ADJ_CP': st['adjudicate_cp'], 'ADJ_PLIES': st['adjudicate_plies'], 'SAVE_PERCENT': st['save_percent'],
            'UNSAVED_NODES': st['unsaved_nodes'], 'CHECK_NODES': st['check_nodes'],
        }
        (d / 'params.sh').write_text(''.join(f'{k}={shlex.quote(str(v))}\n' for k, v in params.items()),
                                     encoding='utf-8', newline='\n')
        shutil.copyfile(HERE / 'start_part.sh', d / 'start_part.sh')
        self.write_state(name, 'part.json', {**plan, 'name': name, 'started_by_app': self.now(), 'cmdline': None,
                                              'paths': {'out': params['DIR']}})
        log = f"{self.cfg['wsl_data'].replace('~', home, 1)}/{name}-job.log"
        r = self.runner.control(self.wsl('python3', '-I', self.jobctl_wsl, 'start', 'datagen', name, '--log', log,
                                         '--cwd', self.cfg['wsl_data'].replace('~', home, 1), '--', 'bash',
                                         config.to_wsl(d / 'start_part.sh')), timeout=60)
        if r.rc != 0:
            (d / 'part.json').rename(d / f'part-refused-{int(self.now())}.json')
            raise Refused(f'jobctl refused the start: {(r.out + r.err).strip()}')
        if auto_stop_hours:
            self.set_auto_stop(name, auto_stop_hours)
        self.ensure_watchdog(name)
        return r.out.strip()

    def set_auto_stop(self, name, hours):
        if hours is None:
            try:
                (self.part_state(name) / 'autostop.json').unlink()
            except FileNotFoundError:
                pass
            return None
        hours = float(hours)
        if not 0 < hours <= 24 * 30:
            raise Refused('auto-stop: give a number of hours between 0 and 720')
        data = {'hours': hours, 'set_at': self.now(), 'deadline': self.now() + hours * 3600}
        self.write_state(name, 'autostop.json', data)
        return data

    def stop_and_seal(self, name, reason, probe=None):
        """Stops the part (verified by jobctl) and starts its seal job. Returns a message; raises Refused if
        the stop did not happen."""
        probe = probe or self.probe()
        job = next((j for j in probe.get('jobs', []) if j['record'].get('name') == name), None)
        if job is None:
            raise Refused(f'no supervisor job named {name}')
        if job['record'].get('type') != 'datagen':
            raise Refused(f'{name} is not a data-generation job')
        if not reason.strip():
            raise Refused('say why the part ends (it goes into the manifest as part_end)')
        dg = next((d for d in probe.get('datagen', []) if d.get('name') == name), {})
        self.write_state(name, 'stop.json', {'requested': self.now(), 'reason': reason})
        stopped_at = None
        if job['live']:
            r = self.runner.control(self.wsl('python3', '-I', self.jobctl_wsl, 'stop', name, '--grace',
                                             str(self.cfg['stop_grace_seconds'])),
                                    timeout=self.cfg['stop_grace_seconds'] + 90)
            if r.rc != 0:
                raise Refused(f'the stop failed, nothing was sealed: {(r.out + r.err).strip()}')
            stopped_at = self.now()
            after = self.probe()
            again = next((j for j in after.get('jobs', []) if j['record'].get('name') == name), None)
            if again and again['live']:
                raise Refused(f'{name} still has processes {again["live"]} after the stop; nothing was sealed')
        rec = job['record']
        start = P.job_log_start((dg.get('job_log_head') or '') + (dg.get('job_log_tail') or ''))
        end = stopped_at or P.iso_epoch(rec.get('stopped') or rec.get('ended'))
        log = P.datagen_log(dg.get('log_tail') or '')
        part = self.read_state(name, 'part.json') or {}
        request = {
            'name': name, 'reason': reason, 'distro': self.cfg['wsl_distro'], 'home': probe['home'],
            'dir': dg.get('dir') or f"{probe['home']}/{self.cfg['wsl_data'][2:]}/{P.part_dir(name)}",
            'cmdline': part.get('cmdline') or dg.get('cmdline'),
            'settings': part.get('settings') or P.datagen_args(dg.get('cmdline') or [])[0],
            'seconds': (end - start) if (start and end) else ((log['last'] or {}).get('seconds')),
            'started': start, 'stopped': end, 'finished': bool(dg.get('run_json')),
            'copies': str(config.expand(self.cfg['copies'])), 'repo': str(self.repo),
            'python': str(self.python), 'val_worker': self.cfg['val_worker'],
            'manifests_out': str(self.manifest_dirs[-1]),
        }
        self.write_state(name, 'seal-request.json', request)
        argv = [str(self.python), '-I', str(self.jobctl_win), 'start', 'seal', f'seal-{name}', '--log',
                str(self.part_state(name) / 'seal.log'), '--cwd', str(self.repo), '--', str(self.python), '-I',
                str(HERE / 'seal_part.py'), str(self.part_state(name) / 'seal-request.json')]
        r = self.runner.control(argv, timeout=60)
        if r.rc != 0:
            raise Refused(f'{name} stopped, but the seal job did not start: {(r.out + r.err).strip()}')
        return f'{name} stopped; sealing (job seal-{name}): {r.out.strip()}'

    # ------------------------------------------------------------ the watchdog

    def watchdog_state(self):
        try:
            w = json.loads((self.state / 'watchdog.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        fresh = self.now() - w.get('heartbeat', 0) < 3 * self.cfg['poll_seconds'] + 30
        w['alive'] = bool(self.pid_alive(w.get('pid')) and fresh and not w.get('exited'))
        return w

    def ensure_watchdog(self, name):
        w = self.watchdog_state()
        if w and w['alive'] and w.get('part') == name:
            return False
        self.spawn(name)
        return True

    def _spawn(self, name):
        pyw = self.python.with_name('pythonw.exe')
        exe = pyw if pyw.exists() else self.python
        flags = 0x00000008 | 0x00000200 if os.name == 'nt' else 0  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen([str(exe), '-I', str(HERE / 'watchdog.py'), '--part', name], creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         close_fds=True, env=dict(os.environ, FORK_CC_STATE=str(self.state)))


def is_running(ctl, name):
    """True / False / None (unknown: the probe failed) for the watchdog."""
    try:
        probe = ctl.probe()
    except Exception:  # noqa: BLE001
        return None
    job = next((j for j in probe.get('jobs', []) if j['record'].get('name') == name), None)
    return bool(job and job['live'])


if __name__ == '__main__':
    sys.exit('generation_control.py is a module of the Control Center (app.py)')
