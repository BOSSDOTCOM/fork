# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/measure/game_replay.py: game selection, the named engine's
positions, and a replay end to end against a fake UCI engine (a short
Python script written by the test) that prints cumulative counter dumps.

    python -I -B -m unittest discover -s tools/measure -p 'test_*.py'
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

import chess
import chess.pgn

sys.path.insert(0, str(Path(__file__).resolve().parent))

import game_replay as gr  # noqa: E402

# Synthetic games: legal move sequences (python-chess checks each move).
LINES = [
    ['e2e4', 'e7e5', 'g1f3', 'b8c6', 'f1b5', 'a7a6'],
    ['d2d4', 'd7d5', 'c2c4', 'e7e6', 'b1c3'],
    ['c2c4', 'g8f6', 'b1c3', 'e7e5'],
    ['g1f3', 'd7d5', 'g2g3'],
]

FAKE_ENGINE = r'''
import sys
searches = 0
for line in sys.stdin:
    words = line.split()
    if not words:
        continue
    if words[0] == 'uci':
        print('id name fake'); print('uciok', flush=True)
    elif words[0] == 'isready':
        print('readyok', flush=True)
    elif words[0] == 'go':
        searches += 1
        nodes = int(words[2])
        sys.stderr.write(f'search_counters lmr_rule_sites={10 * searches} main_nodes={nodes * searches}\n')
        sys.stderr.write(f'search_hist lmr_order {searches} 0 {2 * searches}\n')
        sys.stderr.write(f'iteration_trace 1|{searches}|1000|1000|0|5|5|0|1|20|1\n')
        sys.stderr.flush()
        print('bestmove e2e4', flush=True)
    elif words[0] == 'quit':
        break
'''


def write_pgn(path, lines, white='test', black='base'):
    with open(path, 'w', encoding='utf-8') as f:
        for i, moves in enumerate(lines):
            game = chess.pgn.Game()
            game.headers['White'], game.headers['Black'] = (white, black) if i % 2 == 0 else (black, white)
            node = game
            for uci in moves:
                node = node.add_variation(chess.Move.from_uci(uci))
                node.comment = f'+0.10/{10 + len(node.board().move_stack)} 0.1s'
            print(game, file=f, end='\n\n')


class GameReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        write_pgn(self.dir / 'games.pgn', LINES)

    def tearDown(self):
        self.tmp.cleanup()

    def test_selection_is_seeded(self):
        games = gr.read_games([str(self.dir)])
        self.assertEqual(len(games), 4)
        self.assertEqual([g['colour'] for g in games], ['w', 'b', 'w', 'b'])
        first = [g['id'] for g in gr.select_games(games, 3, 7)]
        self.assertEqual(first, [g['id'] for g in gr.select_games(games, 3, 7)])
        self.assertEqual(len(set(first)), 3)

    def test_skip_keeps_subsets_disjoint(self):
        games = gr.read_games([str(self.dir)])
        a = {g['id'] for g in gr.select_games(games, 2, 1)}
        b = {g['id'] for g in gr.select_games(games, 2, 2, skip_ids=a)}
        self.assertFalse(a & b)
        self.assertEqual(len(b), 2)

    def test_own_positions(self):
        games = gr.read_games([str(self.dir)])
        white_game, black_game = games[0], games[1]
        pos = gr.own_positions(white_game)
        self.assertEqual([p['ply'] for p in pos], [0, 2, 4])
        self.assertEqual([p['move_number'] for p in pos], [1, 2, 3])
        self.assertEqual(pos[1]['moves'], LINES[0][:2])
        self.assertEqual(pos[0]['legal'], 20)
        self.assertEqual(pos[1]['pgn_depth'], 13)  # the comment of the move played there (ply 3)
        pos = gr.own_positions(black_game)
        self.assertEqual([p['ply'] for p in pos], [1, 3])
        self.assertTrue(all(p['side'] == 'b' for p in pos))
        self.assertEqual(len(gr.own_positions(white_game, max_positions=2)), 2)

    def fake_engine(self):
        script = self.dir / 'fake_engine.py'
        script.write_text(FAKE_ENGINE, encoding='utf-8')
        if os.name == 'nt':
            launcher = self.dir / 'fake_engine.bat'
            launcher.write_text(f'@"{sys.executable}" -I "{script}"\n', encoding='utf-8')
        else:
            launcher = self.dir / 'fake_engine.sh'
            launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" -I "{script}"\n', encoding='utf-8')
            launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)
        return str(launcher)

    def test_fake_engine_run(self):
        games = gr.read_games([str(self.dir)])[:2]
        out = self.dir / 'out'
        settings = {'nodes': 100, 'max_positions': None, 'syzygy': None, 'report': ['counters', 'iterations'],
                    'ledger_every': 32, 'hash': 16}
        self.assertEqual(gr.run_replay(self.fake_engine(), games, out, settings, 2), (2, 0))
        records = [json.loads(line) for line in (out / 'game-0000.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([r['ply'] for r in records], [0, 2, 4])
        # Deltas of the cumulative dumps: every search adds 10 sites and 100 nodes.
        self.assertEqual([r['counters']['lmr_rule_sites'] for r in records], [10, 10, 10])
        self.assertEqual([r['counters']['main_nodes'] for r in records], [100, 100, 100])
        self.assertEqual([r['hist']['lmr_order'] for r in records], [[1, 0, 2]] * 3)
        self.assertEqual([r['iterations'][0]['best'] for r in records], [1, 2, 3])
        self.assertEqual(records[1]['pgn_depth'], 13)
        black = [json.loads(line) for line in (out / 'game-0001.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([r['ply'] for r in black], [1, 3])

    def test_resume(self):
        games = gr.read_games([str(self.dir)])[:2]
        out = self.dir / 'out'
        settings = {'nodes': 50, 'max_positions': 1, 'syzygy': None, 'report': ['counters'], 'ledger_every': 32,
                    'hash': 16}
        engine = self.fake_engine()
        self.assertEqual(gr.run_replay(engine, games, out, settings, 1), (2, 0))
        self.assertEqual(gr.run_replay(engine, games, out, settings, 1), (0, 2))
        (out / 'game-0001.jsonl').unlink()
        self.assertEqual(gr.run_replay(engine, games, out, settings, 1), (1, 1))
        self.assertFalse(list(out.glob('*.partial')))


if __name__ == '__main__':
    unittest.main()
