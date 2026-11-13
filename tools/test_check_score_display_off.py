# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/check_score_display_off.py's workflow rule (owner, 2026-11-13: every harness forces CalibratedScore
off, branch workflows included): a workflow that plays games with Fork must run .github/ci/score-display-check.sh;
one that plays none needs nothing; the step named only in a comment does not count. And this repository's own
workflows pass. Run by scripts/check.sh:

    python -I -m unittest discover -s tools -p 'test_check_score_display_off.py'
"""
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('check_score_display_off', HERE / 'check_score_display_off.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

BUILD = 'jobs:\n  build:\n    steps:\n      - run: bash tools/cloud/build_pair.sh . A B engines\n'
GAMES = '      - run: bash tools/cloud/run_shard.sh --base engines/base/fork --test engines/test/fork\n'
INLINE = '      - run: "$T/fastchess" -engine cmd=fork option.CalibratedScore=false -engine cmd=anchor\n'
BELT = '      - name: CalibratedScore\n        run: bash .github/ci/score-display-check.sh engines/base/fork\n'
COMMENT = '      # bash .github/ci/score-display-check.sh engines/base/fork (not run)\n'


class WorkflowRuleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        env = {k: v for k, v in os.environ.items() if k not in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE')}
        subprocess.run(['git', '-C', str(self.repo), 'init', '-q'], check=True, env=env)
        self.env = env

    def tearDown(self):
        self.tmp.cleanup()

    def unbelted(self, **workflows):
        d = self.repo / '.github' / 'workflows'
        d.mkdir(parents=True, exist_ok=True)
        for name, text in workflows.items():
            (d / f'{name}.yml').write_text(text, encoding='utf-8')
        subprocess.run(['git', '-C', str(self.repo), 'add', '-A'], check=True, env=self.env)
        return check.workflows_without_belt(self.repo)

    def test_games_without_the_step_fail(self):
        self.assertEqual(self.unbelted(sprt=BUILD + GAMES), ['.github/workflows/sprt.yml'])

    def test_inline_off_flag_alone_is_not_enough(self):
        self.assertEqual(self.unbelted(gauntlet=BUILD + INLINE), ['.github/workflows/gauntlet.yml'])

    def test_the_step_in_a_comment_does_not_count(self):
        self.assertEqual(self.unbelted(sprt=BUILD + COMMENT + GAMES), ['.github/workflows/sprt.yml'])

    def test_games_with_the_step_pass(self):
        self.assertEqual(self.unbelted(sprt=BUILD + BELT + GAMES, gauntlet=BUILD + BELT + INLINE), [])

    def test_a_workflow_without_games_needs_nothing(self):
        self.assertEqual(self.unbelted(ci=BUILD + '      - run: ctest --test-dir build\n'), [])

    def test_a_setoption_loop_pair_counts_as_off(self):
        d = self.repo / 'tools'
        d.mkdir()
        head = "p.send('uci'); p.wait('uciok')\nfor name, value in (('Hash', 16), "
        (d / 'loop_off.py').write_text(head + "('CalibratedScore', 'false')):\n    p.send(name)\n", encoding='utf-8')
        (d / 'loop_on.py').write_text(head + "('Threads', 1)):\n    p.send(name)\n", encoding='utf-8')
        subprocess.run(['git', '-C', str(self.repo), 'add', '-A'], check=True, env=self.env)
        self.assertEqual(sorted(check.launchers(self.repo)), [('tools/loop_off.py', True), ('tools/loop_on.py', False)])

    def test_this_repository(self):
        repo = HERE.parent
        self.assertEqual(check.workflows_without_belt(repo), [])
        for f in ('.github/workflows/sprt.yml', '.github/workflows/gauntlet.yml'):
            text = (repo / f).read_text(encoding='utf-8')
            self.assertTrue(any(r.search(text) for r in check.PLAYS), f'{f} is no longer seen as playing games')


if __name__ == '__main__':
    unittest.main()
