// SPDX-License-Identifier: GPL-3.0-or-later

// return_moves: the reversible-move table (see return_moves.hpp).
#include "core/return_moves.hpp"

#include <cstdio>
#include <cstdlib>
#include <utility>

#include "core/bitboard.hpp"
#include "core/zobrist.hpp"

namespace forkeng::return_moves {

namespace {

Entry table[TableSize];
int count = 0;

// The two candidate slots: two disjoint bit fields of the key.
int first_slot(Key k) { return static_cast<int>(k & (TableSize - 1)); }
int second_slot(Key k) { return static_cast<int>((k >> 32) & (TableSize - 1)); }

// Cuckoo insertion: the entry takes one of its slots; an entry it displaces
// moves to its other slot, and so on. A bounded number of moves, then a hard
// stop: the Zobrist keys are fixed, so a failure would fail on every build
// and the table test would show it.
void insert(Entry e) {
  int slot = first_slot(e.key);
  for (int moves = 0; moves < 4 * TableSize; ++moves) {
    std::swap(e, table[slot]);
    if (e.key == 0) return;
    slot = slot == first_slot(e.key) ? second_slot(e.key) : first_slot(e.key);
  }
  std::fprintf(stderr, "return_moves: the cuckoo table could not place every key\n");
  std::abort();
}

// The squares `kind` reaches from `s` on an empty board.
Bitboard reach(PieceType kind, Square s) {
  switch (kind) {
    case Knight:
      return knight_attacks(s);
    case Bishop:
      return bishop_attacks(s, 0);
    case Rook:
      return rook_attacks(s, 0);
    case Queen:
      return bishop_attacks(s, 0) | rook_attacks(s, 0);
    default:
      return king_attacks(s);
  }
}

}  // namespace

Key return_move_key(Piece p, Square a, Square b) {
  return zobrist::piece_square[p][a] ^ zobrist::piece_square[p][b] ^ zobrist::side;
}

void init() {
  for (Color c : {White, Black})
    for (PieceType kind : {Knight, Bishop, Rook, Queen, King}) {
      const Piece p = piece_of(c, kind);
      for (Square a = 0; a < 64; ++a)
        for (Bitboard targets = reach(kind, a); targets;) {
          const Square b = pop_lsb(targets);
          if (b < a) continue;  // each pair once
          insert({return_move_key(p, a, b), p, a, b});
          ++count;
        }
    }
}

const Entry* find(Key k) {
  if (table[first_slot(k)].key == k) return &table[first_slot(k)];
  if (table[second_slot(k)].key == k) return &table[second_slot(k)];
  return nullptr;
}

int stored() { return count; }

}  // namespace forkeng::return_moves
