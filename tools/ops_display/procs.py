# SPDX-License-Identifier: GPL-3.0-or-later
"""The only place the display starts a process, and only these read-only commands:

  git -C REPO log ...                      (adoption commits; GIT_OPTIONAL_LOCKS=0, so git takes no lock)
  gh api repos/OWNER/NAME/actions/...      (GET only: a run's jobs, its artifact list, one artifact's zip)
  kaggle kernels status OWNER/KERNEL       (a session's state)

Anything else raises PermissionError before a process exists. No shell, no stdin, a timeout on every call,
no window. The tools read their own credentials (the existing gh login, the Kaggle CLI's file); the display
never opens a credentials file, and error text is cut to its last line and scrubbed before it is shown."""
import os
import re
import shutil
import subprocess

import fsread

CREATE_NO_WINDOW = 0x08000000
_GH_PATH = re.compile(r'^repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/(runs/\d+/(jobs|artifacts)(\?per_page=\d+)?|artifacts/\d+/zip)$')
_KERNEL = re.compile(r'^[A-Za-z0-9_-]+/[A-Za-z0-9_-]+$')
_WRITE_FLAGS = ('-X', '--method', '-f', '-F', '--field', '--raw-field', '--input', '--output', '-o', '--exec', '--upload-pack')


def allowed(argv):
    """Whether argv is one of the read-only commands above (the program is argv[0]'s base name)."""
    if not isinstance(argv, (list, tuple)) or len(argv) < 3 or not all(isinstance(a, str) for a in argv):
        return False
    prog = os.path.basename(argv[0]).lower()
    prog = prog[:-4] if prog.endswith('.exe') else prog
    args = list(argv[1:])
    if any(a.split('=')[0] in _WRITE_FLAGS for a in args):
        return False
    if prog == 'git':
        return len(args) >= 3 and args[0] == '-C' and args[2] == 'log' and all(
            a.startswith(('-', 'refs/')) or re.match(r'^[\w./-]+$', a) for a in args[3:])
    if prog == 'gh':
        return len(args) == 2 and args[0] == 'api' and bool(_GH_PATH.match(args[1]))
    if prog == 'kaggle':
        return len(args) == 3 and args[:2] == ['kernels', 'status'] and bool(_KERNEL.match(args[2]))
    return False


def find(tool, repo=None):
    """The tool's path, or None: git and gh from PATH (gh also from the WinGet links folder), kaggle from the
    repository's own virtual environment."""
    if tool == 'kaggle':
        for cand in (os.path.join(repo or '', '.venv', 'Scripts', 'kaggle.exe'), os.path.join(repo or '', '.venv', 'bin', 'kaggle')):
            if os.path.isfile(cand):
                return cand
        return shutil.which('kaggle')
    found = shutil.which(tool)
    if not found and tool == 'gh' and os.environ.get('LOCALAPPDATA'):
        cand = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'WinGet', 'Links', 'gh.exe')
        found = cand if os.path.isfile(cand) else None
    return found


def run(argv, timeout=30, binary=False, runner=subprocess.run):
    """(return code, stdout, last line of stderr). Raises PermissionError for a command not on the list."""
    if not allowed(argv):
        raise PermissionError('not a read-only command of the display: ' + ' '.join(map(str, argv))[:120])
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GH_PROMPT_DISABLED='1', GH_NO_UPDATE_NOTIFIER='1', NO_COLOR='1')
    try:
        r = runner(list(argv), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                   env=env, creationflags=CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except subprocess.TimeoutExpired:
        return 124, b'' if binary else '', 'timed out'
    except OSError as e:
        return 127, b'' if binary else '', type(e).__name__
    err = (r.stderr or b'').decode('utf-8', 'replace').strip().splitlines()
    out = r.stdout or b''
    return r.returncode, out if binary else out.decode('utf-8', 'replace'), fsread.scrub(err[-1])[:160] if err else ''
