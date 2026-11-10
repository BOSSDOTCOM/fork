# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of idea 69's Python tools (docs/research/class-sampler/design.md §5):

- cell_oracle.py, the independent implementation of the material cells, against the
  constructed positions of cell_cases.txt (the same file the trainer's cell_tests read), in
  both of the dump format's frames;
- cell_weights.py, the weight solver: the mean weight is 1, the caps and the owner's floors
  hold, small cells stay at exactly 1, an impossible target is refused, and the realised-share
  check passes a stream that matches the table and fails one that does not.

    python -I tools/nnue/test_cells.py
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cell_oracle  # noqa: E402
import cell_weights  # noqa: E402

CELLS = [f'{s}|{b}' for s in cell_weights.SIGNATURES for b in cell_weights.BALANCES]


def cases():
    out = []
    for line in (HERE / 'cell_cases.txt').read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            fen, cell, wing = [x.strip() for x in line.split(' ; ')]
            out.append((fen, cell, wing))
    return out


def dump_text(fen):
    """The trainer's dump format of a FEN, in the side to move's frame (kind | 8 for the side
    not to move; Black to move flips the ranks)."""
    board, stm = fen.split()[:2]
    kinds = 'pnbrqk'
    tokens = []
    for r, row in enumerate(board.split('/')):
        rank, file = 7 - r, 0
        for ch in row:
            if ch.isdigit():
                file += int(ch)
                continue
            white = ch.isupper()
            ours = white == (stm == 'w')
            sq = (rank if stm == 'w' else 7 - rank) * 8 + file
            tokens.append(f'{kinds.index(ch.lower()) | (0 if ours else 8)}:{sq}')
            file += 1
    return ' '.join(tokens)


class OracleTest(unittest.TestCase):
    def test_the_constructed_positions(self):
        cs = cases()
        self.assertEqual(len(cs), 17)
        for fen, cell, wing in cs:
            self.assertEqual(cell_oracle.classify_fen(fen), (cell, wing), fen)
            self.assertEqual(cell_oracle.classify_pieces(dump_text(fen)), (cell, wing), fen)


def counts_of(shares, total=1_000_000):
    """{(cell, wing): count} from {(cell, wing): share}; every other entry 0."""
    out = {(c, w): 0 for c in CELLS for w in cell_weights.WINGS}
    for k, s in shares.items():
        out[k] = round(s * total)
    return out


class SolverTest(unittest.TestCase):
    def setUp(self):
        # Training: four cells; deciding: one cell twice as common, one rare, one small.
        self.counts = counts_of({('Q-MG|B-vs-N', 'two-wing'): 0.2, ('Q-MG|minor-up', 'two-wing'): 0.4,
                                 ('Q-MG|minor-up', 'one-wing'): 0.1, ('R-EG|level', 'two-wing'): 0.2,
                                 ('pawn-EG|level', 'one-wing'): 0.1})
        self.deciding = {'Q-MG|B-vs-N': (0.6, 600), 'Q-MG|minor-up': (0.2, 200), 'R-EG|level': (0.18, 180),
                         'pawn-EG|level': (0.02, 20)}

    def mean(self, table):
        total = sum(self.counts.values())
        return sum(n * table[k] for k, n in self.counts.items()) / total

    def test_mean_one_caps_and_small_cells(self):
        r = cell_weights.solve(self.counts, self.deciding, floors=False)
        t = r['table']
        self.assertAlmostEqual(self.mean(t), 1.0, places=9)
        self.assertTrue(all(0.5 - 1e-12 <= w <= 2.0 + 1e-12 for w in t.values()))
        self.assertEqual(t[('pawn-EG|level', 'one-wing')], 1.0)     # 20 deciding positions: small
        self.assertEqual(t[('Q-EG|level', 'two-wing')], 1.0)        # no training positions
        self.assertGreater(t[('Q-MG|B-vs-N', 'two-wing')], 1.0)
        self.assertLess(t[('Q-MG|minor-up', 'two-wing')], 1.0)
        # One material cell, one weight, without floors.
        self.assertEqual(t[('Q-MG|minor-up', 'two-wing')], t[('Q-MG|minor-up', 'one-wing')])

    def test_the_owners_floors(self):
        r = cell_weights.solve(self.counts, self.deciding, floors=True)
        t = r['table']
        self.assertAlmostEqual(self.mean(t), 1.0, places=9)
        # The owner's floors (2026-11-10, narrowed at 9:50 AM EST): the conversion-failure material
        # cells only, every R-vs-minors and Q-imbalance cell and minor-EG|minor-up, in both wing
        # classes; one-wing positions are not floored, so a cell has one weight.
        self.assertTrue(cell_weights.floored('R+minor-EG|R-vs-minors', 'two-wing'))
        self.assertTrue(cell_weights.floored('Q-MG|R-vs-minors', 'one-wing'))
        self.assertTrue(cell_weights.floored('Q-EG|Q-imbalance', 'two-wing'))
        self.assertTrue(cell_weights.floored('minor-EG|minor-up', 'two-wing'))
        self.assertFalse(cell_weights.floored('Q-MG|level', 'one-wing'))
        self.assertFalse(cell_weights.floored('Q-MG|minor-up', 'one-wing'))
        self.assertFalse(cell_weights.floored('R+minor-EG|minor-up', 'two-wing'))
        self.assertEqual(t[('Q-MG|minor-up', 'one-wing')], t[('Q-MG|minor-up', 'two-wing')])
        self.assertLess(t[('Q-MG|minor-up', 'two-wing')], 1.0)
        for c in CELLS:
            for w in cell_weights.WINGS:
                if cell_weights.floored(c, w):
                    self.assertGreaterEqual(t[(c, w)], 1.0, (c, w))
        # A floored cell whose ratio would weigh it below 1 is held at 1, and the floor costs the
        # other cells weight: the scale falls.
        counts = counts_of({('Q-MG|B-vs-N', 'two-wing'): 0.3, ('Q-MG|minor-up', 'two-wing'): 0.3,
                            ('R+minor-EG|R-vs-minors', 'two-wing'): 0.4})
        deciding = {'Q-MG|B-vs-N': (0.6, 600), 'Q-MG|minor-up': (0.2, 200), 'R+minor-EG|R-vs-minors': (0.2, 200)}
        f, b = cell_weights.solve(counts, deciding, floors=True), cell_weights.solve(counts, deciding, floors=False)
        self.assertLess(b['table'][('R+minor-EG|R-vs-minors', 'two-wing')], 1.0)
        self.assertEqual(f['table'][('R+minor-EG|R-vs-minors', 'two-wing')], 1.0)
        self.assertLess(f['k'], b['k'])

    def test_an_impossible_mean_is_refused(self):
        counts = counts_of({('Q-MG|B-vs-N', 'one-wing'): 1.0})
        with self.assertRaises(ValueError):
            # Every position in a floored cell; a floor of 1.5 leaves no mean of 1.
            counts = counts_of({('Q-MG|R-vs-minors', 'two-wing'): 1.0})
            cell_weights.solve(counts, {'Q-MG|R-vs-minors': (1.0, 1000)}, floors=True, floor=1.5)

    def test_the_stream_check(self):
        r = cell_weights.solve(self.counts, self.deciding, floors=True)
        t = r['table']
        stream = {'positions': 100_000, 'exempt': 0, 'exempt_min': float('inf'), 'exempt_max': float('-inf'),
                  'weighted': 100_000, 'mean': None, 'cells': {}}
        total = sum(self.counts.values())
        wsum = 0.0
        for k, n in self.counts.items():
            m = round(n / total * 100_000)
            stream['cells'][k] = (m, m * t[k])
            wsum += m * t[k]
        stream['mean'] = wsum / 100_000
        ok, report = cell_weights.check_stream(t, self.counts, stream)
        self.assertTrue(ok, report)
        # Move 1% of the positions from one cell to another: the check must fail.
        a, b = ('Q-MG|B-vs-N', 'two-wing'), ('Q-MG|minor-up', 'two-wing')
        m_a, m_b = stream['cells'][a][0] - 1000, stream['cells'][b][0] + 1000
        stream['cells'][a] = (m_a, m_a * t[a])
        stream['cells'][b] = (m_b, m_b * t[b])
        ok, _ = cell_weights.check_stream(t, self.counts, stream)
        self.assertFalse(ok)

    def test_table_text_round_trip(self):
        t = cell_weights.solve(self.counts, self.deciding, floors=True)['table']
        text = cell_weights.table_text(t)
        self.assertEqual(len([l for l in text.splitlines() if l and not l.startswith('#')]), 112)
        back = cell_weights.read_table(text)
        for k, w in t.items():
            self.assertAlmostEqual(back[k], w, places=6)


class CellLossTest(unittest.TestCase):
    """The per-cell validation comparison (fork-train train --val-cells files, design.md section 7)."""

    def report(self, rows, loss):
        lines = [f'positions {sum(r[2] for r in rows)}', f'loss {loss:.8f}', 'weighted_loss 0.01000000']
        lines += [f'cell {c} {w} {n} {s:.8f} {s2:.8f}' for c, w, n, s, s2 in rows]
        return '\n'.join(lines) + '\n'

    def test_compare(self):
        a = cell_weights.read_cell_losses(self.report([('Q-MG|level', 'two-wing', 4, 0.08, 0.002),
                                                       ('Q-MG|level', 'one-wing', 0, 0.0, 0.0),
                                                       ('R-EG|level', 'two-wing', 2, 0.02, 0.0002)], 0.0166))
        b = cell_weights.read_cell_losses(self.report([('Q-MG|level', 'two-wing', 4, 0.04, 0.0005),
                                                       ('Q-MG|level', 'one-wing', 0, 0.0, 0.0),
                                                       ('R-EG|level', 'two-wing', 2, 0.03, 0.0005)], 0.0116))
        self.assertEqual(a['positions'], 6)
        self.assertAlmostEqual(a['weighted_loss'], 0.01)
        rows = {r['cell']: r for r in cell_weights.compare_cell_losses(a, b)}
        q = rows['Q-MG|level']
        self.assertEqual(q['n'], 4)
        self.assertAlmostEqual(q['a'], 0.02)
        self.assertAlmostEqual(q['b'], 0.01)
        self.assertAlmostEqual(q['diff'], -0.01)
        # Standard error of each mean: sqrt((sum_e4 / n - mean^2) / n), combined in quadrature.
        se_a = ((0.002 / 4 - 0.02 ** 2) / 4) ** 0.5
        se_b = ((0.0005 / 4 - 0.01 ** 2) / 4) ** 0.5
        self.assertAlmostEqual(q['se'], (se_a ** 2 + se_b ** 2) ** 0.5)
        self.assertNotIn('Q-EG|level', rows)       # no positions: left out
        self.assertAlmostEqual(rows['R-EG|level']['diff'], 0.005)


if __name__ == '__main__':
    unittest.main()
