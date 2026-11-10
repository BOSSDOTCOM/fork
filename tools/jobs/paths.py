# SPDX-License-Identifier: GPL-3.0-or-later
"""Path forms across Git Bash, PowerShell, Windows Python and WSL (DESIGN.md section 1, "Paths across Git Bash,
PowerShell, Windows Python and WSL"), and the outputs check behind "No silent done". The Python twin of
tools/jobs/paths.sh: the same rules, tested on the same table (test_paths.py).

Forms a path can come in:
- Git Bash:     /c/Users/x             (a drive letter alone as the first component)
- Windows:      C:\\Users\\x or C:/Users/x
- WSL mount:    /mnt/c/Users/x
- WSL native:   /home/x, /root/x, ~/x as the distribution sees them; written wsl:/home/x or wsl:~/x to say so
                from another environment; the UNC form \\\\wsl.localhost\\DISTRO\\home\\x (or \\\\wsl$\\...)
- relative:     left relative; only its separators change.
Another absolute POSIX path (/tmp, /usr/bin, /home/x without wsl:) belongs to the environment running the
caller: in Git Bash the MSYS root (converted by cygpath), in WSL or Linux the distribution.

Targets: win (C:/x, //wsl.localhost/DISTRO/x: what Windows Python, PowerShell, jobctl and most Windows programs
take), winbs (the same with backslashes), gitbash (/c/x), wsl (/mnt/c/x, /home/x), here (the running
environment's own form). The WSL distribution is $FORK_WSL_DISTRO, else $WSL_DISTRO_NAME inside WSL, else
Ubuntu; the WSL home for wsl:~ is $FORK_WSL_HOME, else asked of the distribution.

    python paths.py convert TARGET PATH...        prints each converted path
    python paths.py require [--label L] SPEC...   the outputs check; SPEC is FILE (present and not empty),
                                                  json:FILE (also parses as JSON) or any:FILE (present)
"""
import json
import os
import re
import shutil
import subprocess
import sys

TARGETS = ('win', 'winbs', 'gitbash', 'wsl', 'here')
_GITBASH = re.compile(r'^/([A-Za-z])(/.*)?$')
_MOUNT = re.compile(r'^/mnt/([A-Za-z])(/.*)?$')
_WINDOWS = re.compile(r'^([A-Za-z]):([\\/].*)?$')
_UNC = re.compile(r'^(?:\\\\|//)wsl(?:\.localhost|\$)[\\/]([^\\/]+)(.*)$', re.IGNORECASE)


def current_env():
    """gitbash, wsl or linux ($FORK_PATH_ENV overrides). Native Windows Python counts as gitbash: the MSYS
    root, when cygpath is on PATH, is the only meaning a bare POSIX path can have there."""
    env = os.environ.get('FORK_PATH_ENV')
    if env:
        return env
    if os.name == 'nt' or sys.platform.startswith(('msys', 'cygwin')):
        return 'gitbash'
    if os.environ.get('WSL_DISTRO_NAME') or os.path.exists('/proc/sys/fs/binfmt_misc/WSLInterop'):
        return 'wsl'
    return 'linux'


def _distro(distro):
    return distro or os.environ.get('FORK_WSL_DISTRO') or os.environ.get('WSL_DISTRO_NAME') or 'Ubuntu'


def _wsl_home(wsl_home, distro, env):
    if wsl_home or os.environ.get('FORK_WSL_HOME'):
        return wsl_home or os.environ['FORK_WSL_HOME']
    if env in ('wsl', 'linux'):
        return os.environ.get('HOME', '/root')
    if not shutil.which('wsl.exe'):
        raise ValueError('wsl:~ needs FORK_WSL_HOME or wsl.exe')
    r = subprocess.run(['wsl.exe', '-d', distro, '-e', 'sh', '-c', 'printf %s "$HOME"'], capture_output=True,
                       text=True, timeout=60)
    if r.returncode or not r.stdout.startswith('/'):
        raise ValueError(f'cannot read the WSL home of {distro}')
    return r.stdout


def _parse(path, env, distro, home, wsl_home):
    """('drive', letter, rest) or ('distro', name, /abs) or ('rel', text); rest is '' or starts with '/'."""
    if not path:
        raise ValueError('empty path')
    in_wsl = path.startswith('wsl:')
    if in_wsl:
        path = path[4:]
        if path == '~' or path.startswith('~/'):
            path = _wsl_home(wsl_home, _distro(distro), env).rstrip('/') + path[1:]
    elif path == '~' or path.startswith('~/'):
        h = home if home is not None else os.environ.get('HOME') or os.path.expanduser('~')
        path = h.rstrip('/\\') + path[1:]
    for rx in (_MOUNT, _GITBASH, _WINDOWS) if not in_wsl else (_MOUNT,):
        m = rx.match(path)
        if m:
            return ('drive', m.group(1).lower(), (m.group(2) or '').replace('\\', '/'))
    m = _UNC.match(path)
    if m:
        return ('distro', m.group(1), m.group(2).replace('\\', '/') or '/')
    if path.startswith('/'):
        if in_wsl or env in ('wsl', 'linux'):
            return ('distro', _distro(distro), path)
        cyg = shutil.which('cygpath')
        if not cyg:
            raise ValueError(f'{path}: a Git Bash (MSYS root) path needs cygpath')
        win = subprocess.run([cyg, '-m', path], capture_output=True, text=True, timeout=60).stdout.strip()
        m = _WINDOWS.match(win)
        if not m:
            m2 = _UNC.match(win)
            if m2:
                return ('distro', m2.group(1), m2.group(2) or '/')
            raise ValueError(f'{path}: cygpath gave {win!r}')
        return ('drive', m.group(1).lower(), (m.group(2) or '').replace('\\', '/'))
    if in_wsl:
        raise ValueError(f'wsl:{path}: not an absolute path')
    return ('rel', path)


def convert(path, target, env=None, distro=None, home=None, wsl_home=None):
    """The form of PATH that TARGET needs; ValueError if it has none (an unknown target, an empty path, a
    UNC path of another distribution for wsl)."""
    env = env or current_env()
    if target not in TARGETS:
        raise ValueError(f'unknown target {target!r} (one of {", ".join(TARGETS)})')
    if target == 'here':
        target = 'gitbash' if env == 'gitbash' else 'wsl'
    p = _parse(path, env, distro, home, wsl_home)
    if p[0] == 'rel':
        return p[1].replace('/', '\\') if target == 'winbs' else p[1].replace('\\', '/')
    if p[0] == 'drive':
        letter, rest = p[1], p[2] or '/'
        if target == 'win':
            return f'{letter.upper()}:{rest}'
        if target == 'winbs':
            return f'{letter.upper()}:{rest}'.replace('/', '\\')
        if target == 'gitbash':
            return f'/{letter}{rest}'
        return f'/mnt/{letter}{rest}'
    name, rest = p[1], p[2]
    if target == 'wsl':
        if name.lower() != _distro(distro).lower():
            raise ValueError(f'{path}: a path of WSL distribution {name}, not {_distro(distro)}')
        return rest
    unc = f'//wsl.localhost/{name}{rest}'
    return unc.replace('/', '\\') if target == 'winbs' else unc


def windows_program(program, env=None):
    """Whether PROGRAM (a name or path) is a Windows program, which takes Windows paths: in Git Bash anything
    outside the MSYS root's /usr and /bin; in WSL a .exe; on plain Linux nothing."""
    env = env or current_env()
    found = shutil.which(program) or program
    found = found.replace('\\', '/')
    if env == 'gitbash':  # a bare name not found (a builtin, a function) is not a program
        if found.startswith(('/usr/', '/bin/')) or '/Git/usr/' in found or '/Git/bin/' in found:
            return False
        return '/' in found or found.lower().endswith('.exe')
    if env == 'wsl':
        return found.lower().endswith('.exe') or bool(_MOUNT.match(found))
    return False


def require_outputs(specs):
    """The problems with a chain's final outputs, one line each naming the file; [] when all are valid.
    SPEC: FILE (present and not empty), json:FILE (present, not empty, parses as JSON), any:FILE (present)."""
    problems = []
    for spec in specs:
        kind, _, name = spec.partition(':') if spec.startswith(('json:', 'any:')) else ('', '', spec)
        try:  # this Python's own form: Windows for a Windows Python, else the distribution's
            path = convert(name, 'win', env='gitbash') if os.name == 'nt' else convert(name, 'here')
        except ValueError:
            path = name
        if not os.path.isfile(path):
            problems.append(f'missing: {name}')
        elif kind != 'any' and os.path.getsize(path) == 0:
            problems.append(f'empty: {name}')
        elif kind == 'json':
            try:
                with open(path, encoding='utf-8') as f:
                    json.load(f)
            except (OSError, ValueError) as e:
                problems.append(f'invalid JSON: {name} ({e})')
    return problems


def main(argv):
    if len(argv) >= 2 and argv[0] == 'convert':
        try:
            for p in argv[2:]:
                print(convert(p, argv[1]))
        except ValueError as e:
            print(f'paths.py: {e}', file=sys.stderr)
            return 2
        return 0
    if argv and argv[0] == 'require':
        args, label = argv[1:], None
        if args[:1] == ['--label'] and len(args) >= 2:
            label, args = args[1], args[2:]
        problems = require_outputs(args)
        for p in problems:
            print(p, file=sys.stderr)
        if label:
            print(f'{label} failed: {"; ".join(problems)}' if problems
                  else f'{label} done ({len(args)} output{"s" * (len(args) != 1)} verified)')
        return 1 if problems else 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
