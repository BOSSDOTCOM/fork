# SPDX-License-Identifier: GPL-3.0-or-later
"""The Google Cloud CPU worker's queue runner (docs/gcp-worker.md). Runs on the VM under systemd
(fork-worker.service, Restart=always), so it starts at every boot, including after a spot preemption.

The queue is a folder of item files, $W/queue/NAME.json, a mirror of the PC's queue (the PC is authoritative:
tools/gcp/gcp.py push replaces the folder's contents). An item:

    {"name": "slice-pos-td90", "class": "a", "type": "slice", "argv": ["python3", "-I", "..."],
     "outputs": ["json:/opt/fork/out/slice-pos-td90/done.json"], "max_resumes": 50,
     "preemptible": false, "hold": false}

- class: a (the positional slice), b (labelling and measurement jobs), c (standard data generation, the filler);
  the most urgent available item runs: class first, then the name. "hold": true keeps an item queued but unrun.
- one job at a time, through the job supervisor (tools/jobs/jobctl.py, FORK_JOBS=$W/jobs), type = the item's
  type, name = the item's name, so a job survives the worker's own restart (KillMode=process) and an SSH
  disconnect; every job's processes carry FORK_JOB_ID.
- an item's command must be resumable: after a preemption (the VM stopped: the job's record says running, it
  started before the last boot and no process is left) it is started again with the same argv and resumes from
  its own state at a game or chunk boundary. At most max_resumes restarts (default 50), then it fails.
- a job that ends with exit 0 and whose outputs all pass the outputs check (tools/jobs/paths.py require) is
  done ($W/state/items/NAME.done, JSON); any other end is failed (NAME.failed). Neither is retried: the PC
  sees it, alerts, and decides (delete the state file to run it again).
- a running item that is "preemptible" (the filler) is stopped (jobctl stop: SIGTERM, then the whole tree)
  when a more urgent item is available; it resumes later. An item removed from the queue while it runs is
  stopped the same way ("withdrawn").
- CalibratedScore (owner, 2026-11-13): an item whose argv names a build under $W/builds/ starts only if the build's
  commit (its build.env) lacks the option or this tools checkout forces it off (tools/jobs/score_display_guard.py);
  otherwise it is failed with the reason, before any process starts.
- $W/state/worker.json (rewritten every pass) and $W/state/events.jsonl (appended) are what the PC reads.

    python3 -I worker.py run [--interval 30]     the service's loop
    python3 -I worker.py once                    one pass (tests, or by hand)
    python3 -I worker.py status                  worker.json, pretty
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
W = Path(os.environ.get('FORK_WORKER_ROOT', '/opt/fork'))
os.environ.setdefault('FORK_JOBS', str(W / 'jobs'))
sys.path.insert(0, str(HERE.parent / 'jobs'))
import jobctl  # noqa: E402
import paths  # noqa: E402

QUEUE, STATE = W / 'queue', W / 'state'
ITEMS = STATE / 'items'
JOBCTL = HERE.parent / 'jobs' / 'jobctl.py'
GUARD = HERE.parent / 'jobs' / 'score_display_guard.py'
TOOLS_TREE = HERE.parents[1]  # the worker's tools checkout ($W/tools, a worktree of $W/src)
GUARD_REPO = TOOLS_TREE  # resolves the builds' commits (the same objects as $W/src)
CLASSES = ('a', 'b', 'c')


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%S%z')


def event(kind, **fields):
    STATE.mkdir(parents=True, exist_ok=True)
    with open(STATE / 'events.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'at': now(), 'event': kind, **fields}, sort_keys=True) + '\n')


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def load_queue():
    """The valid items by name; an invalid file is reported once per pass and skipped."""
    items, bad = {}, []
    for p in sorted(QUEUE.glob('*.json')):
        it = read_json(p)
        ok = (isinstance(it, dict) and it.get('name') == p.stem and it.get('class') in CLASSES
              and isinstance(it.get('argv'), list) and it['argv'] and it.get('type'))
        if ok and not set(it['name'] + it['type']) - jobctl.NAME_OK:
            items[it['name']] = it
        else:
            bad.append(p.name)
    return items, bad


def item_state(name):
    """done, failed or None (pending)."""
    for s in ('done', 'failed'):
        if (ITEMS / f'{name}.{s}').exists():
            return s
    return None


def resumes(name):
    r = read_json(ITEMS / f'{name}.resumes') or {}
    return int(r.get('count', 0))


def job_record(name):
    return jobctl.read_json(jobctl.job_path(name))


def job_live(name):
    r = job_record(name)
    return bool(r) and bool(jobctl.live(r))


def running_job():
    """The name of the queue job that has processes now (at most one: one lock per type, one start at a time)."""
    jobs = jobctl.root() / 'jobs'
    for p in sorted(jobs.glob('*.json')) if jobs.exists() else []:
        r = jobctl.read_json(p)
        if r and r.get('queue_item') and jobctl.live(r):
            return r['name']
    return None


def jobctl_cmd(*args):
    r = subprocess.run([sys.executable, '-I', str(JOBCTL), *args], capture_output=True, text=True,
                       env=dict(os.environ, FORK_JOBS=str(jobctl.root())))
    return r.returncode, (r.stdout + r.stderr).strip()


def finish(name, item):
    """Records how a job that has no process left ended: done, failed, or preempted (started again later)."""
    r = job_record(name)
    if not r or r.get('state') in ('starting',):
        return
    st = r.get('state')
    if st in ('running', 'stopping'):
        # No process and the record never closed: the machine stopped under it (a preemption or a crash).
        boot = jobctl.last_boot()
        started = jobctl.started_at(r)
        why = 'preempted' if boot and started and started < boot else 'lost'
        n = resumes(name) + 1
        write_json(ITEMS / f'{name}.resumes', {'count': n, 'last': now(), 'why': why})
        r.update(state='interrupted', interrupted=now(), why=why)
        jobctl.write_json(jobctl.job_path(name), r)
        jobctl.release_lock(r['type'], r['id'])
        event('interrupted', name=name, why=why, resumes=n)
        if n > int(item.get('max_resumes', 50)):
            write_json(ITEMS / f'{name}.failed', {'at': now(), 'why': f'{n - 1} resumes used up ({why})'})
            event('failed', name=name, why='resumes used up')
        return
    if st == 'stopped':
        return  # stopped by the worker (withdrawn or yielded): pending again
    if st == 'ended':
        code = r.get('exit_code')
        problems = []
        if code == 0:
            problems = paths.require_outputs(item.get('outputs', []))
            if not item.get('outputs'):
                problems = ['the item names no outputs to check']
        if code == 0 and not problems:
            write_json(ITEMS / f'{name}.done', {'at': now(), 'job_id': r['id'], 'outputs': item.get('outputs', [])})
            event('done', name=name, outputs=item.get('outputs', []))
        else:
            why = f'exit {code}' if code != 0 else 'outputs: ' + '; '.join(problems)
            write_json(ITEMS / f'{name}.failed', {'at': now(), 'job_id': r['id'], 'why': why,
                                                  'log': r.get('log')})
            event('failed', name=name, why=why)
        r['state'] = 'closed'
        jobctl.write_json(jobctl.job_path(name), r)


def score_display_refusal(item):
    """None if the item may start, else why not (owner, 2026-11-13: CalibratedScore off in every harness). An item
    whose argv names a build under $W/builds/ runs that build with this worker's tools checkout; if the build's commit
    (its build.env) has the option, the checkout must force it off (tools/jobs/score_display_guard.py --tree)."""
    prefix = str(W / 'builds') + '/'
    commits = []
    for a in map(str, item['argv']):
        if not a.startswith(prefix):
            continue
        build = W / 'builds' / a[len(prefix):].split('/')[0]
        env = read_text(build / 'build.env')
        commit = next((ln[7:].strip() for ln in env.splitlines() if ln.startswith('commit=')), '')
        if not commit:
            return f'{build} has no build.env commit: cannot tell whether it has CalibratedScore'
        commits.append(commit)
    if not commits:
        return None
    r = subprocess.run([sys.executable, '-I', '-B', str(GUARD), '--repo', str(GUARD_REPO), '--tree', str(TOOLS_TREE),
                        *sorted(set(commits))], capture_output=True, text=True)
    return None if r.returncode == 0 else (r.stdout + r.stderr).strip()[-400:] or f'the guard exited {r.returncode}'


def read_text(path):
    try:
        return Path(path).read_text(encoding='utf-8')
    except OSError:
        return ''


def start(item):
    name = item['name']
    why = score_display_refusal(item)
    if why:
        write_json(ITEMS / f'{name}.failed', {'at': now(), 'why': f'CalibratedScore: {why}'})
        event('failed', name=name, why=f'CalibratedScore: {why}')
        return False
    log = W / 'logs' / f'{name}.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    rc, out = jobctl_cmd('start', item['type'], name, '--log', str(log), '--cwd', str(W), '--', *item['argv'])
    if rc != 0:
        event('start-refused', name=name, out=out[-300:])
        return False
    r = job_record(name)
    if r:
        r['queue_item'] = True
        jobctl.write_json(jobctl.job_path(name), r)
    event('start', name=name, cls=item['class'], resumes=resumes(name))
    return True


def stop(name, why):
    rc, out = jobctl_cmd('stop', name, '--grace', '60')
    event('stop', name=name, why=why, ok=rc == 0, out=out[-300:])
    return rc == 0


def pass_once():
    items, bad = load_queue()
    # Close the records of queue jobs that have no process left.
    jobs = jobctl.root() / 'jobs'
    for p in sorted(jobs.glob('*.json')) if jobs.exists() else []:
        r = jobctl.read_json(p)
        if r and r.get('queue_item') and r.get('state') not in ('closed', 'interrupted', 'stopped') \
                and not jobctl.live(r):
            finish(r['name'], items.get(r['name'], {'max_resumes': 50}))
    pending = sorted((it for it in items.values() if not it.get('hold') and item_state(it['name']) is None),
                     key=lambda it: (CLASSES.index(it['class']), it['name']))
    best = pending[0] if pending else None
    cur = running_job()
    if cur and cur not in items:
        stop(cur, 'withdrawn from the queue')
        cur = running_job()
    elif cur and best and best['name'] != cur and items[cur].get('preemptible') \
            and CLASSES.index(best['class']) < CLASSES.index(items[cur]['class']):
        stop(cur, f"yields to {best['name']} (class {best['class']})")
        cur = running_job()
    if not cur and best:
        start(best)
        cur = running_job()
    write_json(STATE / 'worker.json', {
        'at': now(), 'boot': jobctl.last_boot(), 'running': cur, 'bad_items': bad,
        'items': {n: {'class': it['class'], 'state': item_state(n) or ('running' if n == cur else
                      ('held' if it.get('hold') else 'pending')), 'resumes': resumes(n)}
                  for n, it in items.items()}})


def main(argv):
    cmd = argv[0] if argv else 'run'
    for d in (QUEUE, ITEMS):
        d.mkdir(parents=True, exist_ok=True)
    if cmd == 'once':
        pass_once()
    elif cmd == 'run':
        interval = float(argv[argv.index('--interval') + 1]) if '--interval' in argv else 30.0
        event('worker-start', pid=os.getpid(), boot=jobctl.last_boot())
        while True:
            try:
                pass_once()
            except Exception as e:  # noqa: BLE001  (logged; the loop goes on)
                event('worker-error', error=f'{type(e).__name__}: {e}')
            time.sleep(interval)
    elif cmd == 'status':
        print(json.dumps(read_json(STATE / 'worker.json'), indent=1))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
