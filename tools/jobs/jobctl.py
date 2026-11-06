# SPDX-License-Identifier: GPL-3.0-or-later
"""Fork's job supervisor (owner, 2026-11-05): long-running local jobs (the GitHub SPRT drivers, data
generation, measurements) start and stop only through it.

- One lock per job type: `start TYPE NAME` creates $FORK_JOBS/locks/TYPE.json exclusively; a second job of
  the same type is refused while the first lives. A lock whose job has no process left is reclaimed (and
  logged); a lock whose job still has processes is never taken over.
- The whole process tree is contained: a keeper process starts the command and waits for it. On Windows the
  command starts suspended, joins a Job Object of its own and only then runs, so every descendant (Git Bash
  children, gh, engines) is in the job, whatever happens to its parents. On POSIX the command leads a new
  session, and every process carries FORK_JOB_ID in its environment, which finds descendants that started a
  session of their own.
- `stop NAME` stops the whole tree, gently first (SIGTERM on POSIX: fork_datagen ends at a game boundary;
  on Windows the job is terminated), then verifies that no process of the job remains before it releases
  the lock; it exits 1, keeping the lock, if any process survived.
- Each job's record ($FORK_JOBS/jobs/NAME.json) and events (start, end, stop, reclaim) in
  $FORK_JOBS/events.jsonl; the command's output goes to $FORK_JOBS/jobs/NAME.log unless --log names a file.

    jobctl.py start TYPE NAME [--log FILE] [--cwd DIR] -- COMMAND [ARG...]
    jobctl.py stop NAME [--grace SECONDS]
    jobctl.py status [NAME]          (every job, or one; exit 0 if NAME is running)
    jobctl.py processes NAME         (the job's live process ids, one per line)

Job types in use: github (anything that dispatches GitHub runs: SPRT, fixed-node and gauntlet drivers; one
at a time), datagen, measure, test. $FORK_JOBS defaults to ~/fork-jobs.
"""
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

WINDOWS = os.name == 'nt'
NAME_OK = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.')


def root():
    return Path(os.environ.get('FORK_JOBS') or Path.home() / 'fork-jobs')


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%S%z')


def event(kind, **fields):
    root().mkdir(parents=True, exist_ok=True)
    line = json.dumps({'at': now(), 'event': kind, **fields}, sort_keys=True)
    with open(root() / 'events.jsonl', 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def job_path(name):
    return root() / 'jobs' / f'{name}.json'


def lock_path(kind):
    return root() / 'locks' / f'{kind}.json'


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def write_json(path, data):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding='utf-8')
    os.replace(tmp, path)


# ---------------------------------------------------------------- the platform's process control

if WINDOWS:
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    ntdll = ctypes.WinDLL('ntdll')
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    k32.OpenJobObjectW.restype = wintypes.HANDLE
    k32.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    k32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
                                              wintypes.LPVOID]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    JOB_ALL_ACCESS = 0x1F001F
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    CREATE_SUSPENDED = 0x4
    CREATE_NEW_PROCESS_GROUP = 0x200
    DETACHED_PROCESS = 0x8
    CREATE_NO_WINDOW = 0x08000000

    def job_object_name(job_id):
        return f'fork-job-{job_id}'

    def job_pids(record):
        """The live processes of the job's Job Object (none if the object is gone)."""
        h = k32.OpenJobObjectW(JOB_ALL_ACCESS, False, job_object_name(record['id']))
        if not h:
            return []
        try:
            class IdList(ctypes.Structure):  # JOBOBJECT_BASIC_PROCESS_ID_LIST with room for 4,096 ids
                _fields_ = [('assigned', wintypes.DWORD), ('listed', wintypes.DWORD),
                            ('ids', ctypes.c_size_t * 4096)]
            buf = IdList()
            if not k32.QueryInformationJobObject(h, 3, ctypes.byref(buf), ctypes.sizeof(buf), None):
                raise OSError(ctypes.get_last_error(), 'QueryInformationJobObject')
            return [int(buf.ids[i]) for i in range(buf.listed)]
        finally:
            k32.CloseHandle(h)

    def pid_alive(pid):
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        try:
            code = wintypes.DWORD()
            return bool(k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == STILL_ACTIVE
        finally:
            k32.CloseHandle(h)

    def launch(record, cmd, log, cwd):
        """Starts cmd suspended, puts it in a new Job Object, then lets it run. Returns (Popen, job handle)."""
        job = k32.CreateJobObjectW(None, job_object_name(record['id']))
        if not job:
            raise OSError(ctypes.get_last_error(), 'CreateJobObject')
        env = dict(os.environ, FORK_JOB_ID=record['id'], FORK_JOB=record['name'])
        p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, cwd=cwd, env=env,
                             creationflags=CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW)
        if not k32.AssignProcessToJobObject(job, int(p._handle)):
            err = ctypes.get_last_error()
            p.kill()
            raise OSError(err, 'AssignProcessToJobObject')
        ntdll.NtResumeProcess(int(p._handle))
        return p, job

    def terminate(record, grace):
        h = k32.OpenJobObjectW(JOB_ALL_ACCESS, False, job_object_name(record['id']))
        if h:
            try:
                k32.TerminateJobObject(h, 1)
            finally:
                k32.CloseHandle(h)

    def spawn_keeper(args):
        return subprocess.Popen([sys.executable, '-I', os.path.abspath(__file__), '_keep', *args],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
                                close_fds=True)
else:
    def job_pids(record):
        """Processes in the job's session, or carrying its FORK_JOB_ID (descendants that left the session)."""
        marker = f"FORK_JOB_ID={record['id']}".encode()
        sid = record.get('session')
        out = []
        for d in Path('/proc').iterdir():
            if not d.name.isdigit():
                continue
            pid = int(d.name)
            try:
                stat = (d / 'stat').read_text()
                fields = stat[stat.rindex(')') + 2:].split()
                if fields[0] == 'Z':
                    continue
                if sid is not None and int(fields[3]) == sid:
                    out.append(pid)
                    continue
                if marker in (d / 'environ').read_bytes().split(b'\0'):
                    out.append(pid)
            except (OSError, ValueError):
                continue
        return out

    def pid_alive(pid):
        try:
            stat = Path(f'/proc/{pid}/stat').read_text()
        except OSError:
            return False
        return stat[stat.rindex(')') + 2:].split()[0] != 'Z'

    def launch(record, cmd, log, cwd):
        env = dict(os.environ, FORK_JOB_ID=record['id'], FORK_JOB=record['name'])
        p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, cwd=cwd, env=env,
                             start_new_session=True)
        return p, None

    def terminate(record, grace):
        def send(sig):
            for pid in job_pids(record):
                try:
                    os.kill(pid, sig)
                except OSError:
                    pass
        send(signal.SIGTERM)
        deadline = time.time() + grace
        while time.time() < deadline and job_pids(record):
            time.sleep(0.2)
        send(signal.SIGKILL)

    def spawn_keeper(args):
        return subprocess.Popen([sys.executable, '-I', os.path.abspath(__file__), '_keep', *args],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True, close_fds=True)


def live(record):
    """The job's live processes, the keeper included."""
    pids = set(job_pids(record))
    for k in ('keeper', 'pid'):
        if record.get(k) and pid_alive(record[k]):
            pids.add(record[k])
    return sorted(pids)


# ---------------------------------------------------------------- locks

def take_lock(kind, record):
    """Creates the type's lock for record; reclaims a lock whose job has no process left. Raises
    RuntimeError naming the holder otherwise."""
    path = lock_path(kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            held = read_json(path)
            holder = read_json(job_path(held['name'])) if held else None
            if held and holder and holder.get('id') == held.get('id') and live(holder):
                raise RuntimeError(f"type {kind} is held by job {held['name']} (started {held.get('started')}, "
                                   f"processes {live(holder)})")
            event('reclaim', type=kind, lock=held)
            os.remove(path)
            continue
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'name': record['name'], 'id': record['id'], 'started': record['started']}, f)
        return
    raise RuntimeError(f'type {kind}: the lock could not be taken')


def release_lock(kind, job_id):
    """Removes the type's lock if it still names this job."""
    path = lock_path(kind)
    held = read_json(path)
    if held and held.get('id') == job_id:
        os.remove(path)


# ---------------------------------------------------------------- commands

def cmd_start(argv):
    if '--' not in argv or argv.index('--') < 2:
        sys.exit('usage: jobctl.py start TYPE NAME [--log FILE] [--cwd DIR] -- COMMAND [ARG...]')
    k = argv.index('--')
    head, cmd = argv[:k], argv[k + 1:]
    kind, name, opts = head[0], head[1], head[2:]
    log = cwd = None
    while opts:
        if opts[0] == '--log' and len(opts) > 1:
            log, opts = opts[1], opts[2:]
        elif opts[0] == '--cwd' and len(opts) > 1:
            cwd, opts = opts[1], opts[2:]
        else:
            sys.exit(f'jobctl: unknown option {opts[0]}')
    for word in (kind, name):
        if not word or set(word) - NAME_OK:
            sys.exit(f'jobctl: {word!r}: names and types use letters, digits, - _ . only')
    if not cmd:
        sys.exit('jobctl: no command')
    old = read_json(job_path(name))
    if old and live(old):
        sys.exit(f'jobctl: job {name} is running (processes {live(old)})')
    (root() / 'jobs').mkdir(parents=True, exist_ok=True)
    record = {'name': name, 'type': kind, 'id': uuid.uuid4().hex[:16], 'started': now(), 'command': cmd,
              'cwd': os.path.abspath(cwd or os.getcwd()), 'log': os.path.abspath(log or root() / 'jobs' / f'{name}.log'),
              'state': 'starting'}
    try:
        take_lock(kind, record)
    except RuntimeError as e:
        sys.exit(f'jobctl: {e}')
    write_json(job_path(name), record)
    spawn_keeper([name])
    for _ in range(200):  # the keeper records the command's pid once it runs
        r = read_json(job_path(name))
        if r and r.get('state') != 'starting':
            break
        time.sleep(0.05)
    r = read_json(job_path(name)) or record
    if r.get('state') == 'failed':
        release_lock(kind, record['id'])
        sys.exit(f"jobctl: job {name} did not start: {r.get('error')}")
    event('start', name=name, type=kind, id=record['id'], pid=r.get('pid'), command=cmd)
    print(f"started {name} (type {kind}, id {record['id']}, pid {r.get('pid')}); log {r['log']}")


def cmd_keep(argv):
    """The keeper: runs the job's command inside its container and records how it ended."""
    name = argv[0]
    record = read_json(job_path(name))
    record['keeper'] = os.getpid()
    try:
        log = open(record['log'], 'ab')
        p, handle = launch(record, record['command'], log, record['cwd'])
    except Exception as e:  # noqa: BLE001  (recorded for start to report)
        record.update(state='failed', error=f'{type(e).__name__}: {e}')
        write_json(job_path(name), record)
        return
    record.update(state='running', pid=p.pid)
    if not WINDOWS:
        record['session'] = p.pid  # the command leads its own session
    write_json(job_path(name), record)
    rc = p.wait()
    # The job ends when its whole tree has: a descendant may outlive the command. The keeper waits for it,
    # and on Windows its handle keeps the Job Object (and its name, which `stop` opens) alive until then:
    # a Job Object's name goes when its last handle closes, even with processes still in it.
    while job_pids(record):
        time.sleep(1)
    current = read_json(job_path(name)) or record
    if current.get('id') == record['id'] and current.get('state') == 'running':
        current.update(state='ended', exit_code=rc, ended=now())
        write_json(job_path(name), current)
        event('end', name=name, id=record['id'], exit_code=rc)
        release_lock(current['type'], current['id'])
    if handle is not None:
        k32.CloseHandle(handle)


def cmd_stop(argv):
    if not argv:
        sys.exit('usage: jobctl.py stop NAME [--grace SECONDS]')
    name = argv[0]
    grace = float(argv[argv.index('--grace') + 1]) if '--grace' in argv else 20.0
    record = read_json(job_path(name))
    if not record:
        sys.exit(f'jobctl: no job {name}')
    before = live(record)
    if record.get('state') == 'running':
        record.update(state='stopping')
        write_json(job_path(name), record)
    terminate(record, grace)
    deadline = time.time() + max(5.0, grace)
    left = live(record)
    while left and time.time() < deadline:
        time.sleep(0.2)
        left = live(record)
    if left:
        event('stop-failed', name=name, id=record['id'], left=left)
        print(f'jobctl: job {name}: processes still alive after the stop: {left}; the lock is kept')
        sys.exit(1)
    record.update(state='stopped', stopped=now())
    write_json(job_path(name), record)
    release_lock(record['type'], record['id'])
    event('stop', name=name, id=record['id'], stopped=before)
    print(f'stopped {name}: {len(before)} process(es) ended, none left; lock {record["type"]} released')


def cmd_status(argv):
    names = [argv[0]] if argv else sorted(p.stem for p in (root() / 'jobs').glob('*.json'))
    running = False
    for name in names:
        r = read_json(job_path(name))
        if not r:
            print(f'{name}: no such job')
            continue
        pids = live(r)
        running = running or bool(pids)
        state = r.get('state')
        print(f"{name}: type {r['type']}, {state}{' (exit ' + str(r['exit_code']) + ')' if 'exit_code' in r else ''}, "
              f"started {r['started']}, processes {pids if pids else 'none'}")
    for lk in sorted((root() / 'locks').glob('*.json')):
        held = read_json(lk) or {}
        print(f"lock {lk.stem}: {held.get('name')} ({held.get('id')})")
    if argv:
        sys.exit(0 if running else 3)


def cmd_processes(argv):
    r = read_json(job_path(argv[0])) if argv else None
    if not r:
        sys.exit('jobctl: no such job')
    for pid in live(r):
        print(pid)


def main(argv):
    if not argv:
        sys.exit(__doc__)
    commands = {'start': cmd_start, 'stop': cmd_stop, 'status': cmd_status, 'processes': cmd_processes,
                '_keep': cmd_keep}
    if argv[0] not in commands:
        sys.exit(f'jobctl: unknown command {argv[0]}')
    commands[argv[0]](argv[1:])


if __name__ == '__main__':
    main(sys.argv[1:])
