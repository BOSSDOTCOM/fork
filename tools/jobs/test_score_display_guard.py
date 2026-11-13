# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/jobs/score_display_guard.py (owner, 2026-11-13: every harness forces CalibratedScore off, branch
workflows included). A toy repository stands in for Fork's history:

    P  before the option: src without it, a launcher without the off flag, no checker
    A  the option adopted: src names it, the launcher sets it off, the harness's checker (a toy one)
    B  after A: the launcher loses its off flag (the checker is there and fails)
    C  after A: src no longer names the option (it still descends from A)
    X  a side branch from P that carries the option without A (src names it)

and one case runs on this repository itself when c7a61ea's parent is present (a pre-c7a61ea ref refused with HEAD's
engine; c7a61ea itself accepted; both pre-c7a61ea allowed). Run by scripts/check.sh (tools/jobs):

    python -I -m unittest discover -s tools/jobs -p 'test_*.py'
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD = HERE / 'score_display_guard.py'
REPO = HERE.parents[1]
REAL_ADOPTED = 'c7a61ea987595b7de3b105098b27e7360a73763f'

# The toy harness's checker: every file under tools/ that starts an engine with fastchess sets the option off.
TOY_CHECKER = '''import sys
from pathlib import Path
ROOTS = ('tools/',)
bad = [p for p in Path(sys.argv[1], 'tools').rglob('*.sh')
       if '-engine cmd=' in p.read_text() and 'option.CalibratedScore=false' not in p.read_text()]
for p in bad:
    print(f'{p.name} launches an engine without setting CalibratedScore off', file=sys.stderr)
print('toy checker: ok' if not bad else 'toy checker: failed')
sys.exit(1 if bad else 0)
'''
LAUNCH_OFF = 'fastchess -engine cmd=fork option.CalibratedScore=false -engine cmd=other\n'
LAUNCH_ON = 'fastchess -engine cmd=fork -engine cmd=other\n'


def git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME='toy', GIT_AUTHOR_EMAIL='toy@example.invalid', GIT_COMMITTER_NAME='toy',
               GIT_COMMITTER_EMAIL='toy@example.invalid')
    for k in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):  # never the repository a hook or rebase runs in
        env.pop(k, None)
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, check=True,
                          env=env).stdout.strip()


class GuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        r = cls.repo = Path(cls.tmp.name) / 'toy'
        r.mkdir()
        git(r, '-c', 'init.defaultBranch=main', 'init', '-q')
        git(r, 'config', 'core.autocrlf', 'false')

        def commit(files, msg):
            for name, text in files.items():
                p = r / name
                if text is None:
                    p.unlink()
                    continue
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(text.encode())
            git(r, 'add', '-A')
            git(r, 'commit', '-q', '-m', msg)
            return git(r, 'rev-parse', 'HEAD')
        cls.P = commit({'src/session.cpp': 'options.add("Hash");\n', 'tools/sprt.sh': LAUNCH_ON}, 'P')
        cls.A = commit({'src/session.cpp': 'options.add("Hash");\noptions.add_check("CalibratedScore", true);\n',
                        'tools/sprt.sh': LAUNCH_OFF, 'tools/check_score_display_off.py': TOY_CHECKER}, 'A')
        cls.B = commit({'tools/sprt.sh': LAUNCH_ON}, 'B')
        git(r, 'checkout', '-q', cls.A)
        cls.C = commit({'src/session.cpp': 'options.add("Hash");\n'}, 'C')
        git(r, 'checkout', '-q', cls.P)
        cls.X = commit({'src/session.cpp': 'options.add_check("CalibratedScore", false);\n'}, 'X')
        cls.scratch = Path(cls.tmp.name) / 'scratch'
        cls.scratch.mkdir()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def guard(self, *args, repo=None, adopted=None):
        argv = [sys.executable, '-I', '-B', str(GUARD), '--repo', str(repo or self.repo)]
        if adopted is not False:
            argv += ['--adopted', adopted or self.A]
        # Its own temporary folder, so a guard running beside these tests cannot look like a leftover.
        tmp = str(self.scratch)
        r = subprocess.run(argv + list(args), capture_output=True, text=True,
                           env=dict(os.environ, TMP=tmp, TEMP=tmp, TMPDIR=tmp))
        return r.returncode, r.stdout + r.stderr

    def test_old_ref_with_new_engine_refused(self):
        rc, out = self.guard('--ref', self.P, self.P, self.A)
        self.assertEqual(rc, 1, out)
        self.assertIn('refused', out)
        self.assertIn('tools/check_score_display_off.py is not in it', out)

    def test_new_ref_with_new_engine_allowed(self):
        rc, out = self.guard('--ref', self.A, self.A, self.A)
        self.assertEqual(rc, 0, out)
        self.assertIn('toy checker: ok', out)

    def test_old_engines_allowed_with_any_ref(self):
        rc, out = self.guard('--ref', self.P, self.P, self.P)
        self.assertEqual(rc, 0, out)
        self.assertIn('no engine has CalibratedScore', out)

    def test_ref_whose_checker_fails_refused(self):
        rc, out = self.guard('--ref', self.B, self.A)
        self.assertEqual(rc, 1, out)
        self.assertIn('sprt.sh launches an engine without setting CalibratedScore off', out)

    def test_descendant_of_the_adopting_commit_counts_without_the_name(self):
        rc, out = self.guard('--ref', self.P, self.C)
        self.assertEqual(rc, 1, out)

    def test_the_option_without_the_adopting_commit_counts(self):
        rc, out = self.guard('--ref', self.P, self.X)
        self.assertEqual(rc, 1, out)

    def test_tree_mode(self):
        wt = Path(self.tmp.name) / 'wt'
        git(self.repo, 'worktree', 'add', '-q', '--detach', str(wt), self.P)
        try:
            rc, out = self.guard('--tree', str(wt), self.A)
            self.assertEqual(rc, 1, out)
            git(wt, 'checkout', '-q', self.A)
            rc, out = self.guard('--tree', str(wt), self.A)
            self.assertEqual(rc, 0, out)
        finally:
            git(self.repo, 'worktree', 'remove', '--force', str(wt))

    def test_unknown_commits_are_errors(self):
        self.assertEqual(self.guard('--ref', self.A, 'f' * 40)[0], 2)
        self.assertEqual(self.guard('--ref', 'f' * 40, self.A)[0], 2)

    def test_leaves_no_temporary_repository(self):
        rc, out = self.guard('--ref', self.A, self.A)
        self.assertEqual(rc, 0, out)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_this_repository(self):
        pre = subprocess.run(['git', '-C', str(REPO), 'rev-parse', '--verify', '--quiet', REAL_ADOPTED + '^'],
                             capture_output=True, text=True).stdout.strip()
        if not pre:
            self.skipTest("c7a61ea's parent is not in this clone")
        # The adopting commit as the accepting harness: its own checker passes on its tree (HEAD's may be mid-fix).
        head = git(REPO, 'rev-parse', 'HEAD')
        rc, out = self.guard('--ref', pre, head, repo=REPO, adopted=False)
        self.assertEqual(rc, 1, out)
        rc, out = self.guard('--ref', REAL_ADOPTED, head, repo=REPO, adopted=False)
        self.assertEqual(rc, 0, out)
        self.assertIn('check_score_display_off: ok', out)
        rc, out = self.guard('--ref', pre, pre, repo=REPO, adopted=False)
        self.assertEqual(rc, 0, out)


if __name__ == '__main__':
    unittest.main()
