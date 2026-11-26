# SPDX-License-Identifier: GPL-3.0-or-later
"""The freeze watch starts no process per tick (owner, 2026-11-24, the token leak's option d), and its log lines
stay in the form the Operations Display parses (tools/ops_display/readers.py freezewatch())."""
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / 'freezewatch.sh'
sys.path.insert(0, str(HERE.parent / 'ops_display'))
import readers  # noqa: E402


def git_bash():
    """Git Bash on Windows (never the WSL launcher bash.exe in System32); /bin/bash elsewhere."""
    if os.name == 'nt':
        p = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Git' / 'bin' / 'bash.exe'
        return str(p) if p.exists() else None
    return '/bin/bash' if Path('/bin/bash').exists() else None


class Script(unittest.TestCase):
    def loop_body(self):
        text = SCRIPT.read_text(encoding='utf-8')
        start = text.index('while :; do')
        return text[start:text.index('\ndone', start)]

    def test_no_external_command_in_the_tick(self):
        body = self.loop_body()
        for word in ('sleep', 'date', 'powershell'):
            self.assertNotRegex(body, r'\b%s\b' % word, word)
        # every command substitution in the loop is a stall's or a heartbeat's memory reading
        for line in body.splitlines():
            if re.search(r'\$\((?!\()', line):   # a command substitution, not $(( arithmetic ))
                self.assertIn('$(mem)', line, line)
                self.assertTrue(re.search(r'say "(STALL|heartbeat)', line), line)

    def test_builtin_sleep_and_clock(self):
        text = SCRIPT.read_text(encoding='utf-8')
        self.assertIn('read -r -t "$TICK" -u "$SLEEPER"', text)
        self.assertIn("printf -v now '%(%s)T' -1", text)


@unittest.skipIf(git_bash() is None, 'no bash')
class Run(unittest.TestCase):
    def run_watch(self, **env):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / 'freezewatch.log'
            e = dict(os.environ, FREEZEWATCH_LOG=str(log).replace('\\', '/'), FREEZEWATCH_MEM='avail 1234 MB, commit 56.7%',
                     TMPDIR=d.replace('\\', '/'), **env)
            t0 = time.monotonic()
            subprocess.run([git_bash(), str(SCRIPT)], env=e, check=True, timeout=60)
            return log.read_text(encoding='utf-8'), time.monotonic() - t0

    def test_ticks_wait_and_heartbeats_parse(self):
        text, took = self.run_watch(FREEZEWATCH_TICK='1', FREEZEWATCH_TICKS='3', FREEZEWATCH_HEARTBEAT='1')
        self.assertGreaterEqual(took, 2.5)   # the builtin sleep really waits
        self.assertRegex(text, r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [AP]M EST freezewatch started')
        parsed = readers.freezewatch(text)
        self.assertGreaterEqual(len(parsed['samples']), 2)
        self.assertEqual(parsed['samples'][0]['avail_mb'], 1234)
        self.assertEqual(parsed['stall_count'], 0)

    def test_a_late_tick_is_a_stall(self):
        text, _ = self.run_watch(FREEZEWATCH_TICK='1', FREEZEWATCH_TICKS='2', FREEZEWATCH_STALL='0')
        parsed = readers.freezewatch(text)
        self.assertEqual(len(parsed['stalls']), 2)
        self.assertIn('STALL: 1 s between ticks (expected 1); avail 1234 MB, commit 56.7%', text)


if __name__ == '__main__':
    unittest.main()
