# SPDX-License-Identifier: GPL-3.0-or-later
"""near_window_cost.py's option names: the switch and the parameter a run
sets are idea 60's by default and any tuning build's with --switch and
--param (idea 61 part 5). Needs python-chess (imported by the tool)."""
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import near_window_cost  # noqa: E402


class OptionNamesTest(unittest.TestCase):
    def test_options_sent(self):
        # An engine without a process: its input is captured, and its output
        # answers readyok, one info line and bestmove for each search.
        def searched(switch_and_param):
            engine = object.__new__(near_window_cost.Engine)
            if switch_and_param:
                engine.switch, engine.param = switch_and_param
            else:  # the constructor's defaults
                engine.switch, engine.param = near_window_cost.Engine.__init__.__defaults__
            sent = io.StringIO()
            replies = io.StringIO('readyok\ninfo depth 3 nodes 1234\nbestmove e2e4\n' * 2)
            engine.proc = mock.Mock(stdin=sent, stdout=replies)
            nodes = [engine.nodes_to_depth('8/8/8/8/8/8/8/K6k w - - 0 1', [], 3, m) for m in (None, 25)]
            self.assertEqual(nodes, [1234, 1234])
            return [line for line in sent.getvalue().splitlines() if line.startswith('setoption')]

        self.assertEqual(searched(None), ['setoption name UseNearWindowExtension value false',
                                          'setoption name UseNearWindowExtension value true',
                                          'setoption name NearWindowMargin value 25'])
        self.assertEqual(searched(('UseWindowAwareLmr', 'LmrWindowBand')),
                         ['setoption name UseWindowAwareLmr value false',
                          'setoption name UseWindowAwareLmr value true',
                          'setoption name LmrWindowBand value 25'])
        # The command line: idea 60's names by default, and the run passes
        # whatever --switch and --param name.
        for extra, want in (([], ('UseNearWindowExtension', 'NearWindowMargin')),
                            (['--switch', 'UseWindowAwareLmr', '--param', 'LmrWindowBand'],
                             ('UseWindowAwareLmr', 'LmrWindowBand'))):
            with mock.patch.object(near_window_cost, 'run') as run, \
                    mock.patch.object(sys, 'argv', ['near_window_cost.py', 'run', 'fork', 'g', 'o',
                                                    '--depths', '3'] + extra):
                near_window_cost.main()
            args = run.call_args.args[0]
            self.assertEqual((args.switch, args.param), want)


if __name__ == '__main__':
    unittest.main()
