# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of tools/measure/deep_labels.py: the pinned engine's hash check and
the label budget rule (docs/research/boundary-refiner/step3-plan.md 3.3).

    python -I -B -m unittest discover -s tools/measure -p 'test_*.py'
"""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deep_labels  # noqa: E402


class DeepLabelsTests(unittest.TestCase):
    def test_check_voids_a_wrong_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = Path(tmp) / 'engine.exe'
            engine.write_bytes(b'not an engine')
            with self.assertRaises(SystemExit) as stop:
                deep_labels.main(['check', str(engine), '--sha256', '0' * 64])
            self.assertIn('labels void', str(stop.exception))
            # The right hash (in either case) passes the hash check; running the file then fails.
            digest = hashlib.sha256(b'not an engine').hexdigest().upper()
            with self.assertRaises(OSError):
                deep_labels.main(['check', str(engine), '--sha256', digest])

    def test_budget_rule(self):
        def run(deep_1m, deep_100k, deep_300k):
            # The budget command on twenty gated sites: static 10 against the zero window [0, 1]
            # (nearest bound beta, gap 9).
            with tempfile.TemporaryDirectory() as tmp:
                pilot = Path(tmp)
                (pilot / 'rep').mkdir()
                for name, labels in (('n100k', deep_100k), ('n300k', deep_300k), ('n1m', deep_1m)):
                    (pilot / name).mkdir()
                    (pilot / name / 'deep.tsv').write_text(
                        ''.join(f'{i}\t{v}\t0\t{12 + i % 3}\n' for i, v in enumerate(labels)), encoding='utf-8')
                sites = [{'id': i, 'fen': '4k3/8/8/8/8/8/4P3/4K3 w - - 0 1', 'eval': 10, 'alpha': 0, 'beta': 1,
                          'kind': i % 2, 'reused': False, 'game': 'g#0', 'search_ply': i} for i in range(20)]
                (pilot / 'n1m' / 'sites.jsonl').write_text(''.join(json.dumps(s) + '\n' for s in sites),
                                                            encoding='utf-8')
                with contextlib.redirect_stdout(io.StringIO()) as said:
                    deep_labels.main(['budget', str(pilot)])
            return said.getvalue()

        # The 1M labels alternate sides of the bound; a cheaper label is the 1M one plus 3, or on the
        # other side at the `flipped` sites.
        deep_1m = [(60 + 10 * i) * (1 if i % 2 == 0 else -1) for i in range(20)]
        near = lambda flipped: [-v if i in flipped else v + 3 for i, v in enumerate(deep_1m)]  # noqa: E731
        # 100k agrees in side at 17 of 20 (0.85 < 0.90); 300k at 19 of 20.
        self.assertIn('label budget N = n300k', run(deep_1m, near({1, 4, 7}), near({2})))
        # 100k agrees at 18 of 20 (0.90, the bound included).
        self.assertIn('label budget N = n100k', run(deep_1m, near({1, 4}), near({2})))
        self.assertIn('label budget N = n1m', run(deep_1m, near({1, 4, 7}), near({2, 5, 8})))
        # Side agreement alone is not enough: all labels above the bound, the cheaper ones in reverse
        # order (residual correlation -1), fail the 0.8 line.
        one_side = [20 + 10 * i for i in range(20)]
        self.assertIn('label budget N = n1m', run(one_side, one_side[::-1], one_side[::-1]))


if __name__ == '__main__':
    unittest.main()
