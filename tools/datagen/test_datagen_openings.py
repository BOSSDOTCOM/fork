# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests of tools/datagen/datagen_openings.py (DESIGN.md §5.3, deliverable 1).

The fixture games are random legal games played by python-chess with a
fixed seed, so no move list is typed by hand. Needs python-chess and
zstandard (the repository's .venv):

    .venv/Scripts/python.exe -I -B -m unittest discover -s tools/datagen -p 'test_*.py'
"""
import hashlib
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))

import datagen_openings as dg  # noqa: E402


def random_movetext(rng, plies, comments=True):
    """SAN movetext of a random legal game, with Lichess-style comments and
    annotations mixed in (which the tool must skip)."""
    board = chess.Board()
    parts = []
    for i in range(plies):
        moves = list(board.legal_moves)
        if not moves or board.is_game_over(claim_draw=True):
            break
        move = rng.choice(moves)
        san = board.san(move)
        board.push(move)
        if i % 2 == 0:
            parts.append(f'{i // 2 + 1}.')
        parts.append(san + ('?!' if comments and i == 3 else ''))
        if comments and i % 3 == 0:
            parts.append('{ [%eval 0.31] [%clk 0:02:59] Nf3 was better }')
    return ' '.join(parts) + ' 1-0'


def pgn_game(movetext, event='Rated Blitz game', white=2100, black=2200, extra=''):
    return (f'[Event "{event}"]\n[White "a"]\n[Black "b"]\n[Result "1-0"]\n'
            f'[WhiteElo "{white}"]\n[BlackElo "{black}"]\n{extra}\n{movetext}\n\n')


def fixture(n_good=40, seed=7):
    rng = random.Random(seed)
    games = [pgn_game(random_movetext(rng, 40)) for _ in range(n_good)]
    games += [
        pgn_game(random_movetext(rng, 40), extra='[WhiteTitle "BOT"]\n'),
        pgn_game(random_movetext(rng, 40), extra='[BlackTitle "BOT"]\n'),
        pgn_game(random_movetext(rng, 40), white=1999),
        pgn_game(random_movetext(rng, 40), black='?'),
        pgn_game(random_movetext(rng, 40), event='Casual Blitz game'),
        pgn_game(random_movetext(rng, 40), extra='[Variant "Chess960"]\n'),
        pgn_game(random_movetext(rng, 6)),
    ]
    return ''.join(games)


class TokenTests(unittest.TestCase):
    def test_comments_numbers_nags_and_annotations_are_skipped(self):
        text = '1. e4 { [%eval 0.2] Nf3 } e5?! 2. Nf3 $1 Nc6 3... Bb5 1-0'
        self.assertEqual(dg.san_moves(text, 10), ['e4', 'e5', 'Nf3', 'Nc6', 'Bb5'])
        self.assertEqual(dg.san_moves(text, 2), ['e4', 'e5'])


class RunTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def write_source(self, text, name='src.pgn.zst'):
        import zstandard
        path = self.tmp / name
        path.write_bytes(zstandard.ZstdCompressor().compress(text.encode()))
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def run_tool(self, src, digest, out_name='out.epd', *extra):
        out = self.tmp / out_name
        rc = dg.main([str(src), str(out), '--sha256', digest, *extra])
        return rc, out

    def test_filters_and_counts(self):
        src, digest = self.write_source(fixture())
        rc, out = self.run_tool(src, digest)
        self.assertEqual(rc, 0)
        stats = json.loads(Path(str(out) + '.manifest.json').read_text())['stats']
        self.assertEqual(stats['games'], 47)
        self.assertEqual(stats['bot'], 2)
        self.assertEqual(stats['below_rating'], 2)
        self.assertEqual(stats['not_rated'], 1)
        self.assertEqual(stats['not_standard'], 1)
        self.assertEqual(stats['rating_pass'], 41)
        self.assertEqual(stats['too_short'] + stats['game_over'] + stats['duplicate'] + stats['written'], 41)
        self.assertGreaterEqual(stats['too_short'], 1)
        self.assertGreater(stats['written'], 30)

    def test_positions_are_legal_live_and_at_the_right_depth(self):
        src, digest = self.write_source(fixture())
        rc, out = self.run_tool(src, digest)
        self.assertEqual(rc, 0)
        fens = out.read_text().splitlines()
        self.assertEqual(len(fens), len(set(chess.Board(f).epd() for f in fens)))
        for fen in fens:
            board = chess.Board(fen)
            self.assertTrue(board.is_valid(), fen)
            self.assertFalse(board.is_game_over(claim_draw=True), fen)
            plies = 2 * (board.fullmove_number - 1) + (board.turn == chess.BLACK)
            self.assertGreaterEqual(plies, 8 + 2, fen)
            self.assertLessEqual(plies, 16 + 4, fen)

    def test_same_settings_give_identical_output_and_seed_matters(self):
        src, digest = self.write_source(fixture())
        _, a = self.run_tool(src, digest, 'a.epd')
        _, b = self.run_tool(src, digest, 'b.epd')
        _, c = self.run_tool(src, digest, 'c.epd', '--seed', '5')
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertNotEqual(a.read_bytes(), c.read_bytes())
        man = json.loads(Path(str(a) + '.manifest.json').read_text())
        self.assertEqual(man['output_sha256'], hashlib.sha256(a.read_bytes()).hexdigest())
        self.assertEqual(man['source_sha256'], digest)
        self.assertEqual(man['source'], 'src.pgn.zst')

    def test_wrong_checksum_writes_nothing(self):
        src, digest = self.write_source(fixture())
        bad = ('0' if digest[0] != '0' else '1') + digest[1:]
        rc, out = self.run_tool(src, bad)
        self.assertEqual(rc, 1)
        self.assertFalse(out.exists())

    def test_bot_filter_can_fail(self):
        # Checker check: with the BOT test removed from the filter, the
        # counts test above would see the BOT games pass.
        original = dg.game_filter

        def no_bot_filter(headers, min_rating):
            h = dict(headers)
            h.pop('WhiteTitle', None)
            h.pop('BlackTitle', None)
            return original(h, min_rating)

        dg.game_filter = no_bot_filter
        try:
            src, digest = self.write_source(fixture())
            _, out = self.run_tool(src, digest)
            stats = json.loads(Path(str(out) + '.manifest.json').read_text())['stats']
            self.assertEqual(stats['bot'], 0)
            self.assertEqual(stats['rating_pass'], 43)
        finally:
            dg.game_filter = original


if __name__ == '__main__':
    unittest.main()
