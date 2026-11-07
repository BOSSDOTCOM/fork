# SPDX-License-Identifier: GPL-3.0-or-later
"""Runs the Control Center's external commands (wsl.exe, git, gh, the Kaggle CLI, jobctl.py) without a
console window and with a timeout.

Two doors, so the read-only tabs cannot change anything:
- `read(argv)` runs only commands that is_read_only() accepts: git rev-parse/show/diff/log/cat-file, gh run
  list/view, the Kaggle CLI's kernels list/status and datasets list, `wsl --exec python3 -I -` fed the
  read-only probe (wsl_probe.py), `wsl --exec <part folder>/fork version` and `wsl --exec sha256sum
  </absolute path>.epd` (an openings book's hash, for the preflight) (--exec: no shell between).
  Anything else raises PermissionError before a process starts.
- `control(argv)` runs anything; only the data-generation controller (generation_control.py) holds it. The tabs get
  a ReadOnly view, which has no control().
"""
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000      # process creation flags (Microsoft Learn, "Process Creation Flags")
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000  # (Microsoft Learn, GetPriorityClass)
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

PROBE = Path(__file__).with_name('wsl_probe.py')


@dataclass
class Result:
    rc: int
    out: str
    err: str


def _base(name):
    return os.path.basename(str(name)).lower()


def is_read_only(argv, probe_source=None):
    """True for the commands the read-only tabs may run (see the module docstring)."""
    if not argv:
        return False
    exe = _base(argv[0])
    args = [str(a) for a in argv[1:]]
    if exe in ('git', 'git.exe'):
        if len(args) >= 3 and args[0] == '-C':
            sub = args[2:]
        else:
            sub = args
        if not sub:
            return False
        if sub[0] in ('rev-parse', 'show', 'log', 'cat-file'):
            return not any(a.startswith('--output') for a in sub)
        if sub[0] == 'diff':
            return '--quiet' in sub and not any(a.startswith('--output') for a in sub)
        return False
    if exe in ('gh', 'gh.exe'):
        return len(args) >= 2 and args[0] == 'run' and args[1] in ('list', 'view') and '--web' not in args
    if exe in ('kaggle', 'kaggle.exe'):
        return (len(args) >= 2 and ((args[0] == 'kernels' and args[1] in ('list', 'status'))
                                    or (args[0] == 'datasets' and args[1] == 'list')))
    if exe in ('wsl', 'wsl.exe'):
        if '--exec' not in args:
            return False
        cmd = args[args.index('--exec') + 1:]
        if cmd[:3] == ['python3', '-I', '-']:
            return probe_source is not None and probe_source == PROBE.read_text(encoding='utf-8')
        if len(cmd) == 2 and cmd[0] == 'sha256sum':
            return cmd[1].startswith('/') and cmd[1].endswith('.epd') and '..' not in cmd[1]
        return len(cmd) == 2 and cmd[1] == 'version' and cmd[0].endswith('/fork') and '..' not in cmd[0]
    return False


def run_process(argv, timeout=60, input=None, cwd=None, below_normal=False):
    flags = CREATE_NO_WINDOW if os.name == 'nt' else 0
    if below_normal and os.name == 'nt':
        flags |= BELOW_NORMAL_PRIORITY_CLASS
    try:
        p = subprocess.run([str(a) for a in argv], input=input, capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=timeout, cwd=cwd, creationflags=flags,
                           stdin=None if input is not None else subprocess.DEVNULL)
        return Result(p.returncode, p.stdout, p.stderr)
    except FileNotFoundError as e:
        return Result(127, '', str(e))
    except subprocess.TimeoutExpired:
        return Result(124, '', f'timed out after {timeout} s')


class Runner:
    """The real runner. `backend` (argv, timeout, input, cwd) -> Result replaces the processes in tests."""

    def __init__(self, backend=None):
        self.backend = backend or (lambda argv, timeout, input, cwd: run_process(argv, timeout, input, cwd))
        self.calls = []

    def read(self, argv, timeout=60, input=None, cwd=None):
        if not is_read_only(argv, input):
            raise PermissionError(f'not a read-only command: {argv[:4]}')
        self.calls.append(('read', list(map(str, argv))))
        return self.backend(argv, timeout, input, cwd)

    def control(self, argv, timeout=120, input=None, cwd=None):
        self.calls.append(('control', list(map(str, argv))))
        return self.backend(argv, timeout, input, cwd)


class ReadOnly:
    """What the tabs hold: the runner's read() and nothing else."""

    def __init__(self, runner):
        self._read = runner.read

    def read(self, argv, timeout=60, input=None, cwd=None):
        return self._read(argv, timeout=timeout, input=input, cwd=cwd)
