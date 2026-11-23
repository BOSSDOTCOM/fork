# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the path check (tools/jobs/check_paths.py; DESIGN.md section 1, "Paths across Git Bash, PowerShell,
Windows Python and WSL"):
- fixtures/paths/flag.sh: every line marked "want: RULE" is flagged with exactly those rules, no other line;
  its cases include both shapes of the 2026-11-10 incident (a /c/ path inside -c code and in NAME=PATH);
- fixtures/paths/pass.sh: converted paths, Git Bash's own programs, redirections, MSYS_NO_PATHCONV for wsl.exe
  and marked exceptions are not flagged;
- an exception needs a reason, a whole-file exception too;
- the command line exits 1 on a finding and 0 on none, naming each finding's file and line;
- every job and chain script in the repository (tools/jobs, tools/github, tools/control_center, scripts) passes,
  so the check runs on every commit (scripts/check.sh's tool tests).

    python -I -m unittest discover -s tools/jobs -p 'test_*.py'
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / 'fixtures' / 'paths'
sys.path.insert(0, str(HERE))
import check_paths  # noqa: E402


def wanted(path):
    out = set()
    for n, line in enumerate(path.read_text().splitlines(), 1):
        m = re.search(r'# want: ([\w, -]+)$', line)
        if m:
            out |= {(n, r.strip()) for r in m.group(1).split(',')}
    return out


class Fixtures(unittest.TestCase):
    def test_flagged(self):
        path = FIXTURES / 'flag.sh'
        got = {(f.line, f.rule) for f in check_paths.scan_file(path)}
        self.assertEqual(sorted(got), sorted(wanted(path)))

    def test_passing(self):
        found = check_paths.scan_file(FIXTURES / 'pass.sh')
        self.assertEqual([str(f) for f in found], [])

    def test_file_exception(self):
        body = 'PY=C:/t/python.exe\n"$PY" x.py /c/work/x\n'
        self.assertEqual(len(check_paths.scan_text(body, 'x.sh')), 1)
        self.assertEqual(check_paths.scan_text('# fork-paths: ok-file runs only in WSL\n' + body, 'x.sh'), [])
        rules = [f.rule for f in check_paths.scan_text('# fork-paths: ok-file\n' + body, 'x.sh')]
        self.assertEqual(sorted(rules), ['bad-marker', 'msys-path'])

    def test_marker_on_line_above_a_continued_command(self):
        body = 'PY=C:/t/python.exe\n# fork-paths: ok converted by the tool\n"$PY" x.py \\\n  /c/work/x\n'
        self.assertEqual(check_paths.scan_text(body, 'x.sh'), [])

    def test_cli(self):
        r = subprocess.run([sys.executable, '-I', str(HERE / 'check_paths.py'), str(FIXTURES / 'flag.sh')],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertRegex(r.stdout, r'flag\.sh:9: msys-path: ')
        r = subprocess.run([sys.executable, '-I', str(HERE / 'check_paths.py'), str(FIXTURES / 'pass.sh')],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual((r.returncode, r.stdout), (0, ''), r.stderr)


class Repository(unittest.TestCase):
    def test_job_and_chain_scripts_pass(self):
        files = check_paths.repository_scripts()
        self.assertTrue(any(f.name == 'sprt_run.sh' for f in files), files)
        self.assertFalse(any('fixtures' in f.parts for f in files), files)
        found = [str(f) for p in files for f in check_paths.scan_file(p)]
        self.assertEqual(found, [])


if __name__ == '__main__':
    unittest.main()
