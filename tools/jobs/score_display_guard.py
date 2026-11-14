# SPDX-License-Identifier: GPL-3.0-or-later
"""The dispatch-side guard of the CalibratedScore rule (owner, 2026-11-13: "make every harness force the option off by
default, including branch workflows, with a test").

Fork's CalibratedScore option (c7a61ea, default on) changed the centipawn number in its info lines, so every harness
sets it off (tools/check_score_display_off.py). The owner removed the option on 2026-11-13 (about 7:10 PM EST); engines
built from c7a61ea up to the removal commit still carry it and stay in play, so this guard stays until none of them
is played any more (DESIGN.md decisions log, 2026-11-13). A harness from a branch or checkout older than c7a61ea does not, yet it
can still be pointed at a newer engine: a workflow dispatched with --ref OLD_BRANCH builds the engines from its inputs
but runs OLD_BRANCH's tools. Every dispatcher calls this guard first:

    score_display_guard.py [--repo DIR] (--ref REV | --tree DIR) ENGINE...

ENGINE: the engine commits to be played. One "has the option" if its src/ names CalibratedScore (git grep): the
option's declaration is the only place src/ ever named it, so this holds from c7a61ea up to the removal and on any
branch that carries it, and not after the removal (descent from c7a61ea alone no longer means the option; until the
removal it was a second test). If none has it, the run is allowed whatever the harness. Otherwise the harness must force it off: its tree holds
tools/check_score_display_off.py (none before c7a61ea) and that checker, the harness's own, passes on the harness's
tree. --ref REV: the commit the harness runs from (a workflow's ref, a cloud instance's tools commit); its tracked
files under the checker's ROOTS are exported to a temporary repository (git archive) and the checker runs there.
--tree DIR: a checkout that runs as it is (tools/sprt.sh, the cloud worker's tools checkout); the checker runs on it.

Exit 0 allowed (one line saying why), 1 refused (the reason), 2 an engine or REV this repository cannot resolve.
"""
import argparse
import ast
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

CHECKER = 'tools/check_score_display_off.py'
DEFAULT_ROOTS = ('tools/', 'scripts/', 'bench/', '.github/')
# Every git call names its repository with -C: a GIT_DIR, GIT_WORK_TREE or GIT_INDEX_FILE exported by a hook or a
# rebase must not redirect it (2026-11-07: a test run by `git rebase --exec` wrote to the real repository).
ENV = {k: v for k, v in os.environ.items() if k not in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE',
                                                        'GIT_OBJECT_DIRECTORY', 'GIT_COMMON_DIR')}


def git(repo, *args, check=True):
    r = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, env=ENV)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)[:120]}: {r.stderr.strip()}")
    return r


def remove_tree(path):
    """Deletes the temporary repository this guard made (git leaves read-only files, which Windows will not delete)."""
    def writable(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=writable)
    else:
        shutil.rmtree(path, onerror=writable)


def commit_of(repo, rev):
    r = git(repo, 'rev-parse', '--verify', '--quiet', f'{rev}^{{commit}}', check=False)
    return r.stdout.strip() if r.returncode == 0 else None


def has_option(repo, commit):
    """True if the engine at COMMIT has the CalibratedScore option: its src/ names it (removed 2026-11-13)."""
    r = git(repo, 'grep', '-q', '-F', 'CalibratedScore', commit, '--', 'src', check=False)
    if r.returncode not in (0, 1):
        raise RuntimeError(f'git grep in {commit[:12]}: {r.stderr.strip()}')
    return r.returncode == 0


def checker_roots(text):
    """The ROOTS the harness's own checker walks (a literal tuple), else the defaults."""
    try:
        for node in ast.parse(text).body:
            if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == 'ROOTS' for t in node.targets):
                roots = ast.literal_eval(node.value)
                if isinstance(roots, (tuple, list)) and all(isinstance(r, str) for r in roots):
                    return tuple(roots)
    except (SyntaxError, ValueError):
        pass
    return DEFAULT_ROOTS


def run_checker(tree):
    """(ok, why): the harness's own checker on TREE; why is its ok line, or its first complaints."""
    r = subprocess.run([sys.executable, '-I', '-B', str(Path(tree) / CHECKER), str(tree)], capture_output=True,
                       text=True, env=ENV)
    if r.returncode == 0:
        lines = r.stdout.strip().splitlines()
        return True, lines[-1] if lines else f'{CHECKER} passed'
    lines = r.stderr.strip().splitlines() + r.stdout.strip().splitlines()
    more = f' (and {len(lines) - 3} more)' if len(lines) > 3 else ''
    return False, '; '.join(lines[:3]) + more if lines else f'{CHECKER} exited {r.returncode}'


def check_ref(repo, rev):
    """(ok, why) for the harness at commit REV."""
    shown = git(repo, 'show', f'{rev}:{CHECKER}', check=False)
    if shown.returncode != 0:
        return False, f'{CHECKER} is not in it (it predates c7a61ea), so it does not force CalibratedScore off'
    names = git(repo, 'ls-tree', '-r', '--name-only', rev).stdout.splitlines()
    roots = checker_roots(shown.stdout)
    wanted = [n for n in names if n.startswith(roots)]
    objects = git(repo, 'rev-parse', '--path-format=absolute', '--git-path', 'objects').stdout.strip()
    tmp = Path(tempfile.mkdtemp(prefix='score-display-guard-'))
    try:
        # A throwaway repository that borrows this one's objects: its index is REV's whole tree (what the checker's
        # git ls-files lists), and the files under the checker's ROOTS are written out for it to read.
        git(tmp, 'init', '-q')
        (tmp / '.git' / 'objects' / 'info').mkdir(parents=True, exist_ok=True)
        (tmp / '.git' / 'objects' / 'info' / 'alternates').write_bytes((objects + '\n').encode())
        git(tmp, 'read-tree', rev)
        r = subprocess.run(['git', '-C', str(tmp), '-c', 'core.autocrlf=false', 'checkout-index', '-f', '-z', '--stdin'],
                           input=b'\0'.join(n.encode() for n in wanted) + b'\0', capture_output=True, env=ENV)
        if r.returncode != 0:
            raise RuntimeError(f"git checkout-index of {rev[:12]}: {r.stderr.decode(errors='replace').strip()[-300:]}")
        return run_checker(tmp)
    finally:
        remove_tree(tmp)


def check_tree(tree):
    if not (Path(tree) / CHECKER).is_file():
        return False, f'{CHECKER} is not in it (it predates c7a61ea), so it does not force CalibratedScore off'
    return run_checker(tree)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--repo', default='.', help='the repository that resolves the commits (default .)')
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument('--ref', help='the commit (or ref) the harness runs from')
    where.add_argument('--tree', help='a checkout the harness runs from as it is')
    ap.add_argument('engines', nargs='+', metavar='ENGINE')
    a = ap.parse_args(argv)
    say = lambda msg: print(f'score_display_guard: {msg}')  # noqa: E731
    try:
        with_option = []
        for e in a.engines:
            c = commit_of(a.repo, e)
            if not c:
                print(f'score_display_guard: engine {e} is not a commit in {a.repo}', file=sys.stderr)
                return 2
            if has_option(a.repo, c):
                with_option.append(c)
        if not with_option:
            say('allowed: no engine has CalibratedScore (no src/ names it)')
            return 0
        engines = ', '.join(c[:12] for c in with_option)
        if a.ref is not None:
            rev = commit_of(a.repo, a.ref)
            if not rev:
                print(f'score_display_guard: harness ref {a.ref} is not a commit in {a.repo} (fetch it)',
                      file=sys.stderr)
                return 2
            ok, why = check_ref(a.repo, rev)
            harness = f'harness {a.ref} ({rev[:12]})'
        else:
            ok, why = check_tree(a.tree)
            harness = f'harness checkout {a.tree}'
    except RuntimeError as err:
        print(f'score_display_guard: {err}', file=sys.stderr)
        return 2
    if ok:
        say(f'allowed: {harness} forces CalibratedScore off for {engines} ({why})')
        return 0
    print(f'score_display_guard: refused: {engines} has CalibratedScore (default on), but {harness} does not force it '
          f'off: {why}. Dispatch from a ref that contains c7a61ea (e.g. phase-4) or merge it into this one.',
          file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
