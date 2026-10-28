"""Tests of the cloud book permutation (tools/cloud/shuffle_book.py).

    python3 -m unittest discover -s tools/cloud -p 'test_*.py'
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shuffle_book as sb  # noqa: E402

LINES = [b'a\n', b'b\n', b'c\n', b'd\n', b'e\n']


class ShuffleTests(unittest.TestCase):
    def test_order_follows_the_hash_keys(self):
        # SHA-256 of "1:0" .. "1:4" begins a6685f3b, d6b5915c, 673aeeb0,
        # 85f2ef98, 492ab00b (sha256sum, checked by hand): sorted, lines
        # 4, 2, 3, 0, 1.
        self.assertEqual(sb.permuted(LINES, 1), [b'e\n', b'c\n', b'd\n', b'a\n', b'b\n'])

    def test_same_seed_same_order_other_seed_other_order(self):
        self.assertEqual(sb.permuted(LINES, 7), sb.permuted(list(LINES), 7))
        self.assertNotEqual(sb.permuted(LINES, 1), sb.permuted(LINES, 2))

    def test_file_is_a_permutation_with_a_final_newline(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d, 'in.epd'), Path(d, 'out.epd')
            src.write_bytes(b'a\r\nb\nc')  # bytes kept as they are; the last line gets a newline
            self.assertEqual(sb.main(['--seed', '3', str(src), str(out)]), 0)
            self.assertEqual(sorted(out.read_bytes().splitlines(keepends=True)), [b'a\r\n', b'b\n', b'c\n'])


if __name__ == '__main__':
    unittest.main()
