# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/pgn_summary.py: adjudication is a normal ending, and the
abnormal kinds are counted apart.

    python3 -m unittest discover -s tools -p 'test_pgn_summary.py'
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pgn_summary as ps  # noqa: E402


def game(termination, reason, result='1-0'):
    tags = f'[Event "t"]\n[Result "{result}"]\n' + (f'[Termination "{termination}"]\n' if termination else '')
    return f'{tags}\n1. e4 {{+0.20/10 0.10s}} e5 {{-0.10/9 0.10s, {reason}}} {result}\n'


class AbnormalKindTests(unittest.TestCase):
    def test_rules_and_adjudication_are_normal(self):
        self.assertIsNone(ps.abnormal_kind('normal', 'White mates'))
        self.assertIsNone(ps.abnormal_kind('adjudication', 'White wins by adjudication'))
        self.assertIsNone(ps.abnormal_kind('adjudication', 'Draw by adjudication'))

    def test_kinds(self):
        # Reasons and Terminations as worded in the pinned fastchess binary.
        self.assertEqual(ps.abnormal_kind('time forfeit', 'White loses on time (12ms overrun)'), 'time forfeit')
        self.assertEqual(ps.abnormal_kind('illegal move', 'White makes an illegal move'), 'illegal move')
        self.assertEqual(ps.abnormal_kind('abandoned', "Black's connection stalls"), 'stall')
        self.assertEqual(ps.abnormal_kind('abandoned', 'Black disconnects'), 'disconnect')
        self.assertEqual(ps.abnormal_kind('abandoned', '?'), 'abandoned')
        self.assertEqual(ps.abnormal_kind('rules infraction', '?'), 'other termination "rules infraction"')

    def test_main_counts_kinds_and_exit_status(self):
        pgn = '\n'.join([
            game('adjudication', 'White wins by adjudication'),
            game('adjudication', 'Draw by adjudication', '1/2-1/2'),
            game(None, 'White mates'),
            game('time forfeit', 'Black loses on time (3ms overrun)'),
            game('illegal move', 'Black makes an illegal move'),
        ])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'games.pgn')
            path.write_text(pgn, encoding='utf-8')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                status = ps.main([str(path)])
            self.assertEqual(status, 1)
            text = out.getvalue()
            self.assertIn('5 games', text)
            self.assertIn('games not ending by the rules or adjudication: 2\n', text)
            self.assertIn('       1  time forfeit\n', text)
            self.assertIn('       1  illegal move\n', text)
            path.write_text('\n'.join(pgn.split('\n\n[Event')[0:1]) + '\n', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ps.main([str(path)]), 0)


if __name__ == '__main__':
    unittest.main()
