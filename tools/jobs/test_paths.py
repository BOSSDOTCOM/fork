# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the path helper (tools/jobs/paths.sh and paths.py; DESIGN.md section 1, "Paths across Git Bash,
PowerShell, Windows Python and WSL" and "No silent done"):
- both implementations convert the same table of paths, in each simulated environment (Git Bash, WSL, Linux),
  between the forms: Git Bash /c/..., Windows C:\\... and C:/..., WSL /mnt/c/..., WSL-native /home/... and
  the UNC \\\\wsl.localhost\\DISTRO\\... form; a UNC path of another distribution has no WSL form;
- in Git Bash, another POSIX path (/tmp, /usr) is the MSYS root's and goes through cygpath;
- fork_path_for picks the Windows form for a Windows program and the shell's own form otherwise;
- the outputs check: a missing file, an empty one and an unparseable JSON file each fail and are named, valid
  outputs pass, and fork_chain_done reports "done" only when every output is there; on Windows, the 2026-11-10
  incident's shape (a Git Bash /c/... path checked by a Windows Python) passes.

    python -I -m unittest discover -s tools/jobs -p 'test_*.py'
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATHS_SH = HERE / 'paths.sh'
sys.path.insert(0, str(HERE))
import paths  # noqa: E402

DISTRO = 'Ubuntu'
ENV = {'FORK_WSL_DISTRO': DISTRO, 'FORK_WSL_HOME': '/home/tester'}
HOMES = {'gitbash': '/c/Users/tester', 'wsl': '/home/tester', 'linux': '/home/tester'}

# (environment, path, target, expected); None: no form in that target (an error).
TABLE = [
    ('gitbash', '/c/Users/t/x', 'win', 'C:/Users/t/x'),
    ('gitbash', '/c/Users/t/x', 'winbs', 'C:\\Users\\t\\x'),
    ('gitbash', '/c/Users/t/x', 'wsl', '/mnt/c/Users/t/x'),
    ('gitbash', '/c/Users/t/x', 'gitbash', '/c/Users/t/x'),
    ('gitbash', '/c/Users/t/x', 'here', '/c/Users/t/x'),
    ('gitbash', 'C:\\Users\\t\\x', 'gitbash', '/c/Users/t/x'),
    ('gitbash', 'c:/Users/t/x', 'win', 'C:/Users/t/x'),
    ('gitbash', 'C:/Users/t/x', 'winbs', 'C:\\Users\\t\\x'),
    ('gitbash', '/mnt/d/data', 'win', 'D:/data'),
    ('gitbash', '/c', 'win', 'C:/'),
    ('gitbash', 'C:', 'gitbash', '/c/'),
    ('gitbash', '/mnt/c', 'wsl', '/mnt/c/'),
    ('gitbash', '/c/a b/c d', 'win', 'C:/a b/c d'),
    ('gitbash', '\\\\wsl.localhost\\Ubuntu\\home\\t\\fork', 'wsl', '/home/t/fork'),
    ('gitbash', '//wsl.localhost/Ubuntu/home/t/fork', 'wsl', '/home/t/fork'),
    ('gitbash', '//wsl$/Ubuntu/home/t', 'win', '//wsl.localhost/Ubuntu/home/t'),
    ('gitbash', '\\\\wsl$\\ubuntu\\home\\t', 'winbs', '\\\\wsl.localhost\\ubuntu\\home\\t'),
    ('gitbash', '\\\\wsl.localhost\\Ubuntu-22.04\\root', 'wsl', None),
    ('gitbash', '\\\\wsl.localhost\\Ubuntu-22.04\\root', 'win', '//wsl.localhost/Ubuntu-22.04/root'),
    ('gitbash', 'wsl:/home/t/fork', 'win', '//wsl.localhost/Ubuntu/home/t/fork'),
    ('gitbash', 'wsl:/home/t/fork', 'winbs', '\\\\wsl.localhost\\Ubuntu\\home\\t\\fork'),
    ('gitbash', 'wsl:/home/t/fork', 'gitbash', '//wsl.localhost/Ubuntu/home/t/fork'),
    ('gitbash', 'wsl:~/fork', 'wsl', '/home/tester/fork'),
    ('gitbash', 'wsl:/mnt/c/x', 'win', 'C:/x'),
    ('gitbash', 'rel/dir\\f', 'win', 'rel/dir/f'),
    ('gitbash', 'rel/dir/f', 'winbs', 'rel\\dir\\f'),
    ('gitbash', '~/x', 'win', 'C:/Users/tester/x'),
    ('gitbash', '~', 'wsl', '/mnt/c/Users/tester'),
    ('wsl', '/home/t/x', 'win', '//wsl.localhost/Ubuntu/home/t/x'),
    ('wsl', '/home/t/x', 'here', '/home/t/x'),
    ('wsl', '/home/t/x', 'gitbash', '//wsl.localhost/Ubuntu/home/t/x'),
    ('wsl', 'C:/x', 'here', '/mnt/c/x'),
    ('wsl', '/c/x', 'here', '/mnt/c/x'),
    ('wsl', '/mnt/c/x', 'win', 'C:/x'),
    ('wsl', '~/x', 'win', '//wsl.localhost/Ubuntu/home/tester/x'),
    ('wsl', '\\\\wsl.localhost\\Ubuntu\\home\\t', 'here', '/home/t'),
    ('linux', '/home/t/x', 'here', '/home/t/x'),
    ('linux', '/c/x', 'wsl', '/mnt/c/x'),
    ('linux', 'C:\\x\\y', 'here', '/mnt/c/x/y'),
    ('gitbash', '', 'win', None),
    ('gitbash', '/c/x', 'nowhere', None),
]


def find_bash():
    bash = os.environ.get('FORK_BASH') or shutil.which('bash')
    if not bash or 'system32' in bash.lower():  # C:\Windows\System32\bash.exe is WSL's, not Git Bash
        return None
    return bash


BASH = find_bash()


def run_bash(script, *args, env_name=None, extra=None):
    env = dict(os.environ, **ENV, **(extra or {}))
    if env_name:
        env['FORK_PATH_ENV'] = env_name
        env['HOME'] = HOMES[env_name]
    cmd = [BASH, '-c', f'. "{PATHS_SH.as_posix()}" || exit 9\n{script}', 'test', *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)


class PythonConversions(unittest.TestCase):
    def test_table(self):
        for env, path, target, want in TABLE:
            with self.subTest(env=env, path=path, target=target):
                kw = dict(env=env, distro=DISTRO, home=HOMES[env], wsl_home='/home/tester')
                if want is None:
                    with self.assertRaises(ValueError):
                        paths.convert(path, target, **kw)
                else:
                    self.assertEqual(paths.convert(path, target, **kw), want)

    def test_msys_root_paths_use_cygpath(self):
        kw = dict(env='gitbash', distro=DISTRO, home=HOMES['gitbash'])
        if shutil.which('cygpath'):
            want = subprocess.run(['cygpath', '-m', '/tmp/x'], capture_output=True, text=True).stdout.strip()
            self.assertEqual(paths.convert('/tmp/x', 'win', **kw), want)
        else:
            with self.assertRaises(ValueError):
                paths.convert('/tmp/x', 'win', **kw)

    def test_windows_program(self):
        self.assertTrue(paths.windows_program('C:/tools/venv/Scripts/python.exe', env='gitbash'))
        self.assertTrue(paths.windows_program('/mnt/c/tools/python.exe', env='wsl'))
        self.assertFalse(paths.windows_program('/usr/bin/cat', env='gitbash'))
        self.assertFalse(paths.windows_program('/usr/bin/python3', env='wsl'))
        self.assertFalse(paths.windows_program('python.exe', env='linux'))


@unittest.skipUnless(BASH, 'no Git Bash or POSIX bash')
class BashConversions(unittest.TestCase):
    def test_table(self):
        # One bash per environment: each row prints "OK value" or "ERR status".
        for env in ('gitbash', 'wsl', 'linux'):
            rows = [r for r in TABLE if r[0] == env]
            script = 'while IFS= read -r t && IFS= read -r p; do\n' \
                     '  if v=$(fork_path "$t" "$p" 2>/dev/null); then printf "OK %s\\n" "$v"; ' \
                     'else printf "ERR %s\\n" "$?"; fi\ndone'
            feed = ''.join(f'{t}\n{p}\n' for _, p, t, _ in rows)
            env_vars = dict(os.environ, **ENV, FORK_PATH_ENV=env, HOME=HOMES[env])
            # Bytes, not text: a Windows text-mode pipe would end each line with \r.
            r = subprocess.run([BASH, '-c', f'. "{PATHS_SH.as_posix()}" || exit 9\n{script}'],
                               input=feed.encode(), capture_output=True, env=env_vars, timeout=120)
            out, err = r.stdout.decode(), r.stderr.decode()
            self.assertEqual(r.returncode, 0, err)
            got = out.splitlines()
            self.assertEqual(len(got), len(rows), out + err)
            for (_, path, target, want), line in zip(rows, got):
                with self.subTest(env=env, path=path, target=target):
                    if want is None:
                        self.assertTrue(line.startswith('ERR '), line)
                    else:
                        self.assertEqual(line, f'OK {want}')

    def test_msys_root_paths_use_cygpath(self):
        r = run_bash('fork_path win /tmp/x', env_name='gitbash')
        if shutil.which('cygpath'):
            want = subprocess.run(['cygpath', '-m', '/tmp/x'], capture_output=True, text=True).stdout.strip()
            self.assertEqual((r.returncode, r.stdout.strip()), (0, want), r.stderr)
        else:
            self.assertNotEqual(r.returncode, 0)

    def test_path_for(self):
        r = run_bash('fork_path_for C:/tools/venv/Scripts/python.exe /c/y; fork_path_for /usr/bin/cat /c/y',
                     env_name='gitbash')
        self.assertEqual(r.stdout.split(), ['C:/y', '/c/y'], r.stderr)
        r = run_bash('fork_path_for /mnt/c/tools/python.exe /home/t; fork_path_for /usr/bin/python3 /home/t',
                     env_name='wsl')
        self.assertEqual(r.stdout.split(), ['//wsl.localhost/Ubuntu/home/t', '/home/t'], r.stderr)

    def test_env_detection(self):
        r = run_bash('fork_path_env')
        want = {'nt': 'gitbash'}.get(os.name)
        if want:
            self.assertEqual(r.stdout.strip(), want, r.stderr)
        else:
            self.assertIn(r.stdout.strip(), ('wsl', 'linux'), r.stderr)


class Outputs:
    """Fixtures shared by the bash and Python outputs checks."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / 'good.json').write_text('{"base": "abc", "cands": {}}\n')
        (self.tmp / 'bad.json').write_text('{"base": \n')
        (self.tmp / 'empty.txt').write_text('')
        (self.tmp / 'log.txt').write_text('done\n')

    def p(self, name):
        return (self.tmp / name).as_posix()


class PythonOutputs(Outputs, unittest.TestCase):
    def test_valid(self):
        self.assertEqual(paths.require_outputs(['json:' + self.p('good.json'), self.p('log.txt'),
                                                'any:' + self.p('empty.txt')]), [])

    def test_missing_empty_invalid(self):
        problems = paths.require_outputs([self.p('nope.json'), self.p('empty.txt'), 'json:' + self.p('bad.json'),
                                          'json:' + self.p('good.json')])
        self.assertEqual(len(problems), 3, problems)
        self.assertTrue(problems[0].startswith('missing: ') and problems[0].endswith('nope.json'), problems)
        self.assertTrue(problems[1].startswith('empty: ') and problems[1].endswith('empty.txt'), problems)
        self.assertTrue(problems[2].startswith('invalid JSON: ') and 'bad.json' in problems[2], problems)

    def test_cli(self):
        r = subprocess.run([sys.executable, '-I', str(HERE / 'paths.py'), 'require', 'json:' + self.p('bad.json')],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn('invalid JSON: ', r.stderr)
        r = subprocess.run([sys.executable, '-I', str(HERE / 'paths.py'), 'require', 'json:' + self.p('good.json')],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)


@unittest.skipUnless(BASH, 'no Git Bash or POSIX bash')
class BashOutputs(Outputs, unittest.TestCase):
    def run_check(self, script, *args):
        return run_bash(script, *args, extra={'FORK_PYTHON': Path(sys.executable).as_posix()})

    def test_valid_outputs_pass(self):
        r = self.run_check('fork_require_outputs "$@"', 'json:' + self.p('good.json'), self.p('log.txt'),
                           'any:' + self.p('empty.txt'))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_missing_file_fails(self):
        r = self.run_check('fork_require_outputs "$@"', self.p('log.txt'), self.p('nope.json'))
        self.assertEqual(r.returncode, 1)
        self.assertIn('missing: ' + self.p('nope.json'), r.stderr)

    def test_empty_file_fails(self):
        r = self.run_check('fork_require_outputs "$@"', self.p('empty.txt'))
        self.assertEqual(r.returncode, 1)
        self.assertIn('empty: ' + self.p('empty.txt'), r.stderr)

    def test_unparseable_json_fails(self):
        r = self.run_check('fork_require_outputs "$@"', 'json:' + self.p('bad.json'), 'json:' + self.p('good.json'))
        self.assertEqual(r.returncode, 1)
        self.assertIn('invalid JSON: ' + self.p('bad.json'), r.stderr)
        self.assertNotIn('good.json', r.stderr)

    def test_chain_done(self):
        r = self.run_check('fork_chain_done "retrain 8b chain" "$@"', 'json:' + self.p('good.json'))
        self.assertEqual((r.returncode, r.stdout.strip()), (0, 'retrain 8b chain done (1 output verified)'),
                         r.stderr)
        r = self.run_check('fork_chain_done "retrain 8b chain" "$@"', 'json:' + self.p('good.json'),
                           'json:' + self.p('r8b-ready.json'))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn('chain done', r.stdout)
        self.assertIn('retrain 8b chain failed: missing: ' + self.p('r8b-ready.json'), r.stdout)

    @unittest.skipUnless(os.name == 'nt', 'the Git Bash form exists only on Windows')
    def test_git_bash_path_to_windows_python(self):
        # The incident's shape: the chain's own (Git Bash) path, checked by a Windows Python.
        gb = paths.convert(self.p('good.json'), 'gitbash')
        self.assertTrue(gb.startswith('/') and gb[2] == '/', gb)
        r = self.run_check('fork_require_outputs "$@"', 'json:' + gb)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_check('fork_require_outputs "$@"', 'json:' + paths.convert(self.p('bad.json'), 'gitbash'))
        self.assertEqual(r.returncode, 1, r.stderr)


if __name__ == '__main__':
    unittest.main()
