# SPDX-License-Identifier: GPL-3.0-or-later
"""The PC's side of the Google Cloud CPU worker (docs/gcp-worker.md). Windows Python; gcloud runs through its
bundled Python, SSH and rsync run in WSL (the worker's key lives there). The PC is authoritative: the queue
lives here and is pushed to the VM; results come back here, are checked here, and only then count.

Settings (never committed: project, zone, key and paths): ~/fork-jobs/gcp.json, or $FORK_GCP_CONFIG:
    {"project": "...", "zone": "...", "instance": "...", "gcloud_python": ".../bundledpython/python.exe",
     "gcloud_py": ".../google-cloud-sdk/lib/gcloud.py", "distro": "Ubuntu", "ssh_user": "fork",
     "ssh_key": "~/.ssh/fork-gcp", "known_hosts": "~/.ssh/fork-gcp-known",
     "staging": "wsl:~/fork-data/gcp", "state": "C:/Users/<user>/fork-jobs/gcp",
     "egress_usd_per_gib": 0.12, "usd_per_hour_running": 0.0, "usd_per_hour_stopped": 0.0,
     "finish": {"JOB": {"kind": "slice", "slice_tools": "C:/...", "python": "C:/.../python.exe",
                        "starts": "C:/.../slice-positional.tsv", "copy_to": "C:/...",
                        "done_file": "C:/.../JOB-done.json"}}}
The queue: STATE/queue/NAME.json (tools/gcp/worker.py's item format).

    gcp.py status [--json]            the VM (gcloud describe: cheap, no SSH) and, when it runs, the worker's
                                      state and last events (one SSH); STATE/status.json
    gcp.py start | stop               start or stop the VM; the wanted state goes to STATE/wanted.json, which
                                      watch --restart follows
    gcp.py push                       mirror STATE/queue/ to the VM's queue (rsync --delete)
    gcp.py pull JOB                   rsync the VM's /opt/fork/out/JOB/ into the staging folder; the bytes and
                                      their egress price go to STATE/egress.jsonl
    gcp.py finish JOB                 pull, then the PC's own checks (per the job's "finish" settings); writes
                                      the done file only if every check passes
    gcp.py watch [--interval 300] [--restart] [--finish]
                                      the status loop (run it under jobctl as type gcpwatch): a Windows toast
                                      and a line in STATE/alerts.jsonl on a preemption, a stop nobody asked for,
                                      a worker job that failed or used up its resumes, or a VM that cannot be
                                      reached; --restart starts a preempted VM again while wanted.json says
                                      running; --finish runs finish for each job the worker reports done
Exit status: 0 ok, 1 a failed check or command, 2 usage.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'jobs'))
sys.path.insert(0, str(HERE.parent / 'control_center'))
import paths  # noqa: E402

NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
OUT = '/opt/fork/out'


def est(t=None):
    return time.strftime('%Y-%m-%d %I:%M:%S %p EST', time.gmtime((t or time.time()) - 5 * 3600))


def load_config():
    p = Path(os.environ.get('FORK_GCP_CONFIG') or Path.home() / 'fork-jobs' / 'gcp.json')
    c = json.loads(p.read_text(encoding='utf-8'))
    c.setdefault('distro', 'Ubuntu')
    c.setdefault('ssh_user', 'fork')
    c.setdefault('state', str(Path.home() / 'fork-jobs' / 'gcp'))
    return c


def state_dir(c):
    d = Path(paths.convert(c['state'], 'win'))
    d.mkdir(parents=True, exist_ok=True)
    return d


def run(argv, timeout=600, check=False):
    r = subprocess.run([str(a) for a in argv], capture_output=True, text=True, timeout=timeout,
                       stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
    if check and r.returncode != 0:
        raise SystemExit(f'failed ({r.returncode}): {" ".join(map(str, argv))[:200]}\n{r.stderr.strip()[-800:]}')
    return r


def gcloud(c, *args, check=True, timeout=300):
    r = run([c['gcloud_python'], c['gcloud_py'], *args, f"--project={c['project']}"], timeout=timeout, check=check)
    return r


def describe(c):
    r = gcloud(c, 'compute', 'instances', 'describe', c['instance'], f"--zone={c['zone']}", '--format=json',
               check=False)
    if r.returncode != 0:
        return {'status': 'UNKNOWN', 'error': r.stderr.strip()[-300:]}
    d = json.loads(r.stdout)
    ip = None
    for nic in d.get('networkInterfaces', []):
        for ac in nic.get('accessConfigs', []):
            ip = ac.get('natIP') or ip
    return {'status': d.get('status'), 'ip': ip, 'machine_type': d.get('machineType', '').rsplit('/', 1)[-1],
            'last_start': d.get('lastStartTimestamp'), 'last_stop': d.get('lastStopTimestamp'),
            'provisioning': d.get('scheduling', {}).get('provisioningModel'),
            'termination_action': d.get('scheduling', {}).get('instanceTerminationAction')}


def preemptions(c, since=None):
    """The instance's preemption operations (newest last), optionally after an RFC 3339 time."""
    flt = f"operationType=compute.instances.preempted AND targetLink~/{c['instance']}$"
    if since:
        flt += f' AND insertTime>"{since}"'
    r = gcloud(c, 'compute', 'operations', 'list', f'--filter={flt}', '--format=json(insertTime,name)', check=False)
    try:
        return sorted((o['insertTime'] for o in json.loads(r.stdout or '[]')))
    except ValueError:
        return []


def wsl(c, *argv, timeout=600, check=False):
    return run(['wsl.exe', '-d', c['distro'], '--exec', *argv], timeout=timeout, check=check)


def ssh_opts(c):
    return ['-i', c['ssh_key'], '-o', f"UserKnownHostsFile={c['known_hosts']}", '-o',
            f"HostKeyAlias={c['instance']}", '-o', 'StrictHostKeyChecking=accept-new', '-o', 'BatchMode=yes',
            '-o', 'ConnectTimeout=20']


def ssh(c, ip, command, timeout=120, check=False):
    return wsl(c, 'ssh', *ssh_opts(c), f"{c['ssh_user']}@{ip}", command, timeout=timeout, check=check)


def rsync(c, src, dst, *extra, timeout=7200):
    rsh = 'ssh ' + ' '.join(ssh_opts(c))
    return wsl(c, 'rsync', '-a', '--partial', '--stats', '-e', rsh, *extra, src, dst, timeout=timeout)


def need_ip(c):
    d = describe(c)
    if d['status'] != 'RUNNING' or not d.get('ip'):
        raise SystemExit(f"the VM is {d['status']}, not running")
    return d['ip']


# ---------------------------------------------------------------- commands

def cmd_status(c, as_json=False):
    d = describe(c)
    out = {'at': est(), 'vm': d, 'worker': None, 'events': []}
    if d['status'] == 'RUNNING' and d.get('ip'):
        r = ssh(c, d['ip'], 'cat /opt/fork/state/worker.json; echo ---; tail -n 20 /opt/fork/state/events.jsonl')
        if r.returncode == 0:
            w, _, ev = r.stdout.partition('---\n')
            try:
                out['worker'] = json.loads(w)
            except ValueError:
                out['worker'] = {'error': 'unreadable worker.json'}
            out['events'] = [json.loads(x) for x in ev.splitlines() if x.strip().startswith('{')]
        else:
            out['worker'] = {'error': f'ssh failed: {r.stderr.strip()[-200:]}'}
    (state_dir(c) / 'status.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    if as_json:
        print(json.dumps(out, indent=1))
    else:
        print(f"{c['instance']} ({d.get('machine_type')}, {d.get('provisioning')}): {d['status']}"
              f"{', ip ' + d['ip'] if d.get('ip') else ''}; last start {d.get('last_start')}, last stop "
              f"{d.get('last_stop')}")
        w = out['worker'] or {}
        if 'items' in w:
            print(f"worker at {w['at']}: running {w.get('running')}")
            for n, it in sorted(w['items'].items()):
                print(f"  {n}: class {it['class']}, {it['state']}, resumes {it['resumes']}")
        elif w:
            print(f"worker: {w}")
    return out


def cmd_start_stop(c, what):
    (state_dir(c) / 'wanted.json').write_text(json.dumps({'wanted': 'running' if what == 'start' else 'stopped',
                                                         'at': est()}), encoding='utf-8')
    gcloud(c, 'compute', 'instances', what, c['instance'], f"--zone={c['zone']}", timeout=600)
    print(f"{c['instance']}: {describe(c)['status']}")


def cmd_push(c):
    q = state_dir(c) / 'queue'
    q.mkdir(exist_ok=True)
    for p in q.glob('*.json'):
        it = json.loads(p.read_text(encoding='utf-8'))
        if it.get('name') != p.stem:
            raise SystemExit(f'{p}: its name is not {p.stem}')
    ip = need_ip(c)
    r = rsync(c, paths.convert(str(q), 'wsl') + '/', f"{c['ssh_user']}@{ip}:/opt/fork/queue/", '--delete',
              '--include=*.json', '--exclude=*', timeout=300)
    if r.returncode != 0:
        raise SystemExit(f'push failed: {r.stderr.strip()[-500:]}')
    print(f'queue pushed: {sorted(p.stem for p in q.glob("*.json"))}')


def received_bytes(stats):
    for line in stats.splitlines():
        if line.startswith('Total bytes received:'):
            return int(line.split(':')[1].strip().replace(',', ''))
    return None


def cmd_pull(c, job):
    ip = need_ip(c)
    dst = paths.convert(c['staging'], 'wsl').rstrip('/') + f'/{job}/'
    wsl(c, 'mkdir', '-p', dst, check=True)
    r = rsync(c, f"{c['ssh_user']}@{ip}:{OUT}/{job}/", dst)
    if r.returncode != 0:
        raise SystemExit(f'pull of {job} failed: {r.stderr.strip()[-500:]}')
    got = received_bytes(r.stdout) or 0
    usd = got / 2 ** 30 * float(c.get('egress_usd_per_gib', 0.12))
    with open(state_dir(c) / 'egress.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'at': est(), 'job': job, 'bytes': got, 'usd': round(usd, 6)}) + '\n')
    print(f'{job}: {got:,} bytes received into {dst} (egress about ${usd:.4f})')
    return paths.convert('wsl:' + dst, 'win')  # the form Windows Python opens


def finish_slice(c, job, f, staging):
    """The PC's checks of a slice run (slice.sh's, on a copy on C:): every shard's SHA-256 against the VM's
    done.json, verify_games.py per segment with its manifest, defense_starts.py played over all segments."""
    import shutil
    src = Path(staging)
    done = json.loads((src / 'done.json').read_text(encoding='utf-8'))
    dst = Path(f['copy_to']) / job
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    from hashlib import sha256
    for rel, want in done['sha256'].items():
        seg, name = rel.split('/')
        (dst / seg).mkdir(exist_ok=True)
        shutil.copyfile(src / seg / name, dst / seg / name)
        got = sha256((dst / seg / name).read_bytes()).hexdigest()
        if got != want:
            raise SystemExit(f'{rel}: SHA-256 {got} on the PC, {want} on the VM')
    verify = []
    for i, s in enumerate(done['segments']):
        man = src / s['dir'] / f"{s['run']}.json"
        shutil.copyfile(man, dst / s['dir'] / man.name)
        shards = [str(dst / rel) for rel in done['sha256'] if rel.startswith(s['dir'] + '/')]
        r = run([f['python'], '-I', Path(f['slice_tools']) / 'verify_games.py', *shards, '--manifest',
                 dst / s['dir'] / man.name, '--table-pieces', '5'], timeout=7200)
        if r.returncode != 0:
            raise SystemExit(f"verify_games.py failed on {s['dir']}: {(r.stdout + r.stderr).strip()[-500:]}")
        verify.append(f"{s['dir']}: {r.stdout.strip().splitlines()[-1]}")
    shards = [str(dst / rel) for rel in done['sha256']]
    r = run([f['python'], '-I', Path(f['slice_tools']) / 'defense_starts.py', 'played', f['starts'], *shards,
             '--out', dst / 'played.tsv'], timeout=7200)
    if r.returncode != 0:
        raise SystemExit(f'defense_starts.py played failed: {(r.stdout + r.stderr).strip()[-500:]}')
    played = r.stdout.strip().splitlines()[-1]
    out = {'run': job, 'positions': done['positions'], 'games': done['games'], 'finished': done['finished'],
           'checked_on_pc': est(), 'dir': str(dst), 'segments': done['segments'], 'verify': verify,
           'played': played, 'builds': done['builds'], 'sha256': done['sha256']}
    return out


def cmd_finish(c, job):
    f = (c.get('finish') or {}).get(job)
    if not f:
        raise SystemExit(f'no "finish" settings for {job} in the config')
    staging = cmd_pull(c, job)
    if f['kind'] == 'slice':
        out = finish_slice(c, job, f, staging)
    else:
        raise SystemExit(f"unknown finish kind {f['kind']}")
    done_file = Path(f['done_file'])
    tmp = done_file.with_suffix('.tmp')
    tmp.write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
    os.replace(tmp, done_file)
    problems = paths.require_outputs([f"json:{paths.convert(str(done_file), 'win')}"])
    if problems:
        raise SystemExit(f'{job} finish failed: {"; ".join(problems)}')
    print(f'{job} finished and checked on the PC: {done_file}')


def alert(c, title, text):
    with open(state_dir(c) / 'alerts.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'at': est(), 'title': title, 'text': text}) + '\n')
    print(f'{est()} ALERT {title}: {text}', flush=True)
    try:
        import notify
        notify.toast(title, text)
    except Exception:  # noqa: BLE001  (the alert is in the log either way)
        pass


def cmd_watch(c, interval, restart, finish):
    seen_pre = set(preemptions(c))
    seen_events, prev, unreachable = set(), None, 0
    finished = set()
    print(f'{est()} watching {c["instance"]} every {interval:.0f} s (restart {restart}, finish {finish})', flush=True)
    while True:
        try:
            st = cmd_status(c, as_json=False)
            vm, w = st['vm'], st['worker'] or {}
            wanted = (json.loads((state_dir(c) / 'wanted.json').read_text(encoding='utf-8'))
                      if (state_dir(c) / 'wanted.json').exists() else {}).get('wanted')
            pre = set(preemptions(c))
            new_pre = pre - seen_pre
            for t in sorted(new_pre):
                alert(c, 'GCP worker preempted', f"{c['instance']} was preempted at {t}")
            seen_pre |= pre
            if prev == 'RUNNING' and vm['status'] in ('TERMINATED', 'STOPPED') and wanted == 'running' \
                    and not new_pre:
                alert(c, 'GCP worker stopped', f"{c['instance']} is {vm['status']} though wanted running")
            if restart and wanted == 'running' and vm['status'] == 'TERMINATED':
                r = gcloud(c, 'compute', 'instances', 'start', c['instance'], f"--zone={c['zone']}", check=False)
                print(f"{est()} restart: {'ok' if r.returncode == 0 else r.stderr.strip()[-200:]}", flush=True)
            if vm['status'] == 'RUNNING' and 'error' in w:
                unreachable += 1
                if unreachable == 3:
                    alert(c, 'GCP worker unreachable', str(w['error'])[:300])
            else:
                unreachable = 0
            for e in st['events']:
                key = (e.get('at'), e.get('event'), e.get('name'))
                if key in seen_events:
                    continue
                seen_events.add(key)
                if prev is None:
                    continue  # the first pass only sets the baseline
                if e.get('event') in ('failed', 'start-refused', 'worker-error'):
                    alert(c, f"GCP job {e.get('event')}", f"{e.get('name')}: {e.get('why') or e.get('out') or e.get('error')}")
            for n, it in (w.get('items') or {}).items():
                if finish and it['state'] == 'done' and n not in finished and n in (c.get('finish') or {}):
                    f = c['finish'][n]
                    if not Path(f['done_file']).exists():
                        try:
                            cmd_finish(c, n)
                            alert(c, 'GCP job finished', f'{n}: pulled and checked on the PC ({f["done_file"]})')
                        except SystemExit as e:
                            alert(c, 'GCP finish failed', f'{n}: {e}')
                    finished.add(n)
            prev = vm['status']
        except Exception as e:  # noqa: BLE001  (logged; the loop goes on)
            print(f'{est()} watch error: {type(e).__name__}: {e}', flush=True)
        time.sleep(interval)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    c = load_config()
    cmd, rest = argv[0], argv[1:]
    if cmd == 'status':
        cmd_status(c, '--json' in rest)
    elif cmd in ('start', 'stop'):
        cmd_start_stop(c, cmd)
    elif cmd == 'push':
        cmd_push(c)
    elif cmd == 'pull' and rest:
        cmd_pull(c, rest[0])
    elif cmd == 'finish' and rest:
        cmd_finish(c, rest[0])
    elif cmd == 'watch':
        interval = float(rest[rest.index('--interval') + 1]) if '--interval' in rest else 300.0
        cmd_watch(c, interval, '--restart' in rest, '--finish' in rest)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
