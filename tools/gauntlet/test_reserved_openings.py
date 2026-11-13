# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for tools/gauntlet/reserved_openings.py: derive() against the
permutation shuffle_book.py builds whole (an independent oracle: a full sort
of every key against a streamed partial selection), and extract()'s checks
(line count, window, SHA-256), each shown to refuse a wrong input.

    python3 -I -m unittest discover -s tools/gauntlet -p 'test_*.py'
"""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'cloud'))
import reserved_openings as ro  # noqa: E402
import shuffle_book  # noqa: E402

SEED = 20261027


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.lines = [f'line {i} w - -\n'.encode() for i in range(600)]
        self.book = self.dir / 'book.epd'
        self.book.write_bytes(b''.join(self.lines))
        self.shuffled = self.dir / 'shuffled.epd'
        shuffle_book.main(['--seed', str(SEED), str(self.book), str(self.shuffled)])

    def tearDown(self):
        self.tmp.cleanup()


class Derive(Base):
    def test_matches_the_whole_permutation(self):
        whole = shuffle_book.permuted(self.lines, SEED)
        for first, count in ((401, 50), (551, 50), (600, 1), (1, 600), (300, 7)):
            with self.subTest(first=first, count=count):
                self.assertEqual(ro.derive(self.book, SEED, first, count), b''.join(whole[first - 1:first - 1 + count]))

    def test_another_seed_differs(self):
        self.assertNotEqual(ro.derive(self.book, SEED, 401, 50), ro.derive(self.book, SEED + 1, 401, 50))

    def test_outside_the_book(self):
        for first, count in ((0, 5), (590, 20), (601, 1)):
            with self.subTest(first=first, count=count), self.assertRaises(ValueError):
                ro.derive(self.book, SEED, first, count)


class Extract(Base):
    def args(self, first=401, count=50, book_lines=600, sha=None):
        want = b''.join(self.shuffled.read_bytes().splitlines(keepends=True)[first - 1:first - 1 + count])
        return dict(first=first, count=count, book_lines=book_lines,
                    sha256=sha or hashlib.sha256(want).hexdigest()), want

    def test_the_window(self):
        kw, want = self.args()
        out = self.dir / 'out.epd'
        ro.extract(self.shuffled, out, **kw)
        self.assertEqual(out.read_bytes(), want)
        self.assertEqual(want, ro.derive(self.book, SEED, 401, 50))

    def test_refusals(self):
        kw, _ = self.args()
        cases = {'wrong SHA-256': dict(kw, sha256='0' * 64),
                 'wrong line count': dict(kw, book_lines=601),
                 'window past the end': dict(self.args(first=590, count=20)[0])}
        for what, k in cases.items():
            out = self.dir / f'{what}.epd'
            with self.subTest(what), self.assertRaises(ValueError):
                ro.extract(self.shuffled, out, **k)
            self.assertFalse(out.exists(), what)

    def test_main_exit_status(self):
        # The real constants against the small book: refused (its line count), no output.
        out = self.dir / 'main.epd'
        self.assertEqual(ro.main([str(self.shuffled), str(out)]), 1)
        self.assertFalse(out.exists())


class Constants(unittest.TestCase):
    def test_the_window_lies_in_the_book_past_every_sprt_stage(self):
        self.assertLessEqual(ro.FIRST + ro.COUNT - 1, ro.BOOK_LINES)
        # Line FIRST is reached by no SPRT stage below 3,000 at 832 lines a stage (LTC, the widest).
        self.assertGreater(ro.FIRST, 3000 * 832)
        self.assertRegex(ro.SHA256, '^[0-9a-f]{64}$')

    def test_the_workflow_uses_it(self):
        yml = (HERE.parent.parent / '.github' / 'workflows' / 'gauntlet.yml').read_text(encoding='utf-8')
        self.assertIn('tools/gauntlet/reserved_openings.py', yml)
        self.assertIn(ro.BOOK, yml)


if __name__ == '__main__':
    unittest.main()
