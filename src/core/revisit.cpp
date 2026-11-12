// SPDX-License-Identifier: GPL-3.0-or-later

// revisit: the reversible-move table (see revisit.hpp).
#include "core/revisit.hpp"

#include <cassert>

#include "core/bitboard.hpp"
#include "core/zobrist.hpp"

namespace forkeng::revisit {

Key keys[Slots];
Shuttle moves[Slots];

namespace {
int filled = 0;
}  // namespace

void init() {
  for (Key& k : keys) k = 0;
  filled = 0;
  for (Color c : {White, Black})
    for (PieceType t : {Knight, Bishop, Rook, Queen, King}) {
      const Piece p = piece_of(c, t);
      for (Square a = 0; a < 64; ++a) {
        // Each pair once: the squares above a that the piece reaches from a
        // on an empty board.
        Bitboard reach = attacks(t, a, 0) & ~((bb(a) << 1) - 1);
        while (reach) {
          const Square b = pop_lsb(reach);
          const Key change = zobrist::piece_square[p][a] ^ zobrist::piece_square[p][b] ^ zobrist::side;
          assert(change != 0 && "revisit: a key change of 0 cannot be stored");
          int i = static_cast<int>(change & (Slots - 1));
          while (keys[i] != 0) {
            assert(keys[i] != change && "revisit: two moves with one key change");
            i = (i + 1) & (Slots - 1);
          }
          keys[i] = change;
          moves[i] = Shuttle{p, a, b};
          ++filled;
        }
      }
    }
  assert(2 * filled <= Slots && "revisit: the table is more than half full");
}

int stored() { return filled; }

}  // namespace forkeng::revisit
