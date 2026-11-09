# SPDX-License-Identifier: GPL-3.0-or-later
"""The Control Center's read-only look inside WSL, run as `wsl -d DISTRO -- python3 -I - ARGS` with this
file on stdin (one process per poll). It only reads: the WSL supervisor's job records, locks and events
(with each job's live processes, by jobctl.py's own live()), each datagen job's fork_datagen command line
and log tails, the folders it is asked about, /proc/meminfo, the load average and the free space of ~.
Prints one JSON object.

    ARGS: JOBCTL_PATH WSL_JOBS WSL_DATA [FOLDER...]   (paths may start with ~)
"""
import json
import os
import sys
from pathlib import Path

TAIL = 48 * 1024


def tail(path, size=TAIL):
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            n = f.tell()
            f.seek(max(0, n - size))
            return f.read().decode('utf-8', 'replace')
    except OSError:
        return None


def head(path, size=4096):
    try:
        with open(path, 'rb') as f:
            return f.read(size).decode('utf-8', 'replace')
    except OSError:
        return None


def folder(path):
    p = Path(path)
    if not p.is_dir():
        return {'path': str(p), 'exists': False}
    files = []
    for f in sorted(p.iterdir()):
        try:
            st = f.stat()
            files.append({'name': f.name, 'bytes': st.st_size, 'mtime': st.st_mtime, 'dir': f.is_dir()})
        except OSError:
            pass
    return {'path': str(p), 'exists': True, 'files': files}


def proc_cmdline(pid):
    try:
        raw = Path(f'/proc/{pid}/cmdline').read_bytes()
        return [a.decode('utf-8', 'replace') for a in raw.split(b'\0') if a]
    except OSError:
        return None


def proc_comm(pid):
    try:
        return Path(f'/proc/{pid}/comm').read_text().strip()
    except OSError:
        return None


def main(argv):
    home = str(Path.home())
    ex = lambda p: os.path.expanduser(p)  # noqa: E731
    jobctl_path, jobs_root, data_root = ex(argv[0]), ex(argv[1]), ex(argv[2])
    os.environ['FORK_JOBS'] = jobs_root
    out = {'home': home, 'jobs': [], 'locks': [], 'events': [], 'datagen': [], 'folders': {}, 'errors': []}
    try:
        sys.path.insert(0, os.path.dirname(jobctl_path))
        import jobctl  # noqa: E402  (read-only use: read_json and live)
    except Exception as e:  # noqa: BLE001
        jobctl = None
        out['errors'].append(f'jobctl: {type(e).__name__}: {e}')
    jr = Path(jobs_root)
    for f in sorted((jr / 'jobs').glob('*.json')):
        try:
            rec = json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        live = []
        if jobctl is not None:
            try:
                live = jobctl.live(rec)
            except Exception as e:  # noqa: BLE001
                out['errors'].append(f"live({rec.get('name')}): {e}")
        job = {'record': rec, 'live': live}
        out['jobs'].append(job)
        if rec.get('type') == 'datagen':
            dg = {'name': rec.get('name'), 'cmdline': None, 'pid': None}
            for pid in live:
                if proc_comm(pid) == 'fork_datagen':
                    dg['pid'], dg['cmdline'] = pid, proc_cmdline(pid)
                    break
            d = None
            if dg['cmdline'] and '--out' in dg['cmdline']:
                d = dg['cmdline'][dg['cmdline'].index('--out') + 1]
            if not d:
                d = os.path.join(data_root, 'gen' + str(rec.get('name', ''))[1:])
            dg['dir'] = d
            dg['log_tail'] = tail(os.path.join(d, f"{rec.get('name')}.log"))
            dg['job_log_head'] = head(rec.get('log', ''))
            dg['job_log_tail'] = tail(rec.get('log', ''), 8192)
            dg['run_json'] = (Path(d) / f"{rec.get('name')}.json").is_file()
            dg['folder'] = folder(d)
            out['datagen'].append(dg)
    for f in sorted((jr / 'locks').glob('*.json')):
        try:
            out['locks'].append({'type': f.stem, **json.loads(f.read_text(encoding='utf-8'))})
        except (OSError, ValueError):
            out['locks'].append({'type': f.stem, 'unreadable': True})
    ev = tail(jr / 'events.jsonl', 16384) or ''
    for line in ev.splitlines()[-40:]:
        try:
            out['events'].append(json.loads(line))
        except ValueError:
            pass
    for p in argv[3:]:
        out['folders'][p] = folder(ex(p))
    try:
        out['meminfo'] = Path('/proc/meminfo').read_text()
        out['loadavg'] = Path('/proc/loadavg').read_text().split()[:3]
        st = os.statvfs(home)
        out['disk'] = {'total': st.f_blocks * st.f_frsize, 'free': st.f_bavail * st.f_frsize}
    except OSError as e:
        out['errors'].append(str(e))
    print(json.dumps(out))


if __name__ == '__main__':
    main(sys.argv[1:])
