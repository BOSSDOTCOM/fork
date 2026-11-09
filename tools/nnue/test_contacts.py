# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the contact and pawn-link inputs' reference (tools/nnue/contacts.py;
ideas.md idea 41), each against a count or a transformation of its own:

- the index space's sizes, pinned (a change of the encoding must be seen);
- on seeded random game positions: every attack relation between two
  non-king pieces that are not both pawns is represented exactly once (a
  mutual pair by one input), so the active contacts number the relations
  less the mutual pairs; the links number the pawn pairs on the same or
  adjacent files;
- the colour-flipped board seen from the other side gives the same inputs,
  and so does the board mirrored left-right (the frame mirrors by the king);
- the start position's inputs, counted by hand from the rules.
"""
import random
import sys
import unittest
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contacts  # noqa: E402


def positions(count=200, seed=20261105):
    rng = random.Random(seed)
    out = []
    while len(out) < count:
        b = chess.Board()
        for _ in range(rng.randrange(4, 80)):
            moves = list(b.legal_moves)
            if not moves:
                break
            b.push(rng.choice(moves))
        if not b.is_game_over():
            out.append(b.copy(stack=False))
    return out


def relations(board):
    """(attacker square, victim square) for every attack between two
    non-king pieces that are not both pawns, from python-chess directly."""
    out = set()
    for a, x in board.piece_map().items():
        if x.piece_type == chess.KING:
            continue
        for b in board.attacks(a):
            y = board.piece_at(b)
            if y and y.piece_type != chess.KING and not (x.piece_type == y.piece_type == chess.PAWN):
                out.add((a, b))
    return out


def no_castling(board):
    b = board.copy(stack=False)
    b.castling_rights = chess.BB_EMPTY
    b.ep_square = None
    return b


class Contacts(unittest.TestCase):
    def test_index_space_sizes(self):
        self.assertEqual(contacts.contact_count(), 50416)
        self.assertEqual(contacts.link_count(), 1488)

    def test_each_relation_once(self):
        for board in positions():
            rel = relations(board)
            mutual = sum(1 for a, b in rel if (b, a) in rel) // 2
            for persp in (chess.WHITE, chess.BLACK):
                got = contacts.contact_features(board, persp)
                self.assertEqual(len(got), len(set(got)), board.fen())
                self.assertEqual(len(got), len(rel) - mutual, board.fen())

    def test_links_count_the_pawn_pairs(self):
        for board in positions():
            pawns = list(board.pieces(chess.PAWN, True) | board.pieces(chess.PAWN, False))
            want = sum(1 for i, p in enumerate(pawns) for q in pawns[i + 1:] if abs(p % 8 - q % 8) <= 1)
            for persp in (chess.WHITE, chess.BLACK):
                got = contacts.link_features(board, persp)
                self.assertEqual(len(got), len(set(got)), board.fen())
                self.assertEqual(len(got), want, board.fen())

    def test_colour_flip_and_mirror(self):
        for board in positions(120):
            b = no_castling(board)
            flipped = b.mirror()  # colours swapped and the board flipped vertically
            mirrored = b.transform(chess.flip_horizontal)
            for persp in (chess.WHITE, chess.BLACK):
                want = (contacts.contact_features(b, persp), contacts.link_features(b, persp))
                self.assertEqual((contacts.contact_features(flipped, not persp),
                                  contacts.link_features(flipped, not persp)), want, b.fen())
                self.assertEqual((contacts.contact_features(mirrored, persp),
                                  contacts.link_features(mirrored, persp)), want, b.fen())

    def test_start_position(self):
        # Contacts, counted by hand for White (Black's are the same): the a1
        # rook defends a2 and b1 (2), the b1 knight d2 (1), the c1 bishop b2
        # and d2 (2), the queen c1, c2, d2 and e2 (4; the e1 king is left
        # out), the f1 bishop e2 and g2 (2), the g1 knight e2 (1), the h1
        # rook h2 and g1 (2): 14. No two of them attack each other (the
        # queen touches the c1 bishop along the rank, which a bishop does
        # not return), and the pawns attack only empty squares. 28 in all.
        b = chess.Board()
        self.assertEqual(len(contacts.contact_features(b, chess.WHITE)), 28)
        # Links: 8 pawns per side; pairs on the same or adjacent files: per
        # side 7 adjacent pairs; across sides, same file 8, adjacent 14.
        self.assertEqual(len(contacts.link_features(b, chess.WHITE)), 7 + 7 + 8 + 14)
        # S512+PP's rank limit 1: only the 7 pairs on each side's own rank;
        # the two sides' pawns are five ranks apart.
        self.assertEqual(len(contacts.link_features(b, chess.WHITE, contacts.S512PP_RANKS)), 7 + 7)

    def test_rank_limited_links(self):
        # S512+PP's links (rank limit 1): 608, counted here from the squares
        # directly (a pawn slot pairs with the slots on its own and the
        # neighbouring files and ranks; each pair once).
        squares = [(side, q) for side in (0, 1) for q in range(8, 56)]
        want = sum(1 for i, (_, a) in enumerate(squares) for (_, b) in squares[i + 1:]
                   if a != b and abs(a % 8 - b % 8) <= 1 and abs(a // 8 - b // 8) <= 1)
        self.assertEqual(want, 608)
        self.assertEqual(contacts.link_count(contacts.S512PP_RANKS), want)
        for board in positions():
            pawns = list(board.pieces(chess.PAWN, True) | board.pieces(chess.PAWN, False))
            near = sum(1 for i, p in enumerate(pawns) for q in pawns[i + 1:]
                       if abs(p % 8 - q % 8) <= 1 and abs(p // 8 - q // 8) <= 1)
            for persp in (chess.WHITE, chess.BLACK):
                got = contacts.link_features(board, persp, contacts.S512PP_RANKS)
                self.assertEqual(len(got), len(set(got)), board.fen())
                self.assertEqual(len(got), near, board.fen())
                self.assertTrue(all(0 <= x < 608 for x in got), board.fen())


if __name__ == '__main__':
    unittest.main()
