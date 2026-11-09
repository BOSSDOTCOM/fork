// SPDX-License-Identifier: GPL-3.0-or-later

// return_moves: the table of reversible moves for upcoming-repetition
// detection (tier 2, T51; KB search-techniques.md §3.29, after van Kervinck's
// cycle detection, 2013).
//
// Purpose: a position differs from an earlier one by a single reversible move
// of one piece exactly when the XOR of their keys is that move's return move
// key: piece_square[p][a] ^ piece_square[p][b] ^ side, for a knight, bishop,
// rook, queen or king p of either colour and two squares a and b it could move
// between on an empty board. XOR is symmetric, so a move and its reverse share
// one key. The keys are kept in a cuckoo hash table (Pagh and Rodler, 2001):
// each key has two candidate slots, so a lookup reads at most two.
// Invariants:
// - Built once by init() (core init(), after the Zobrist keys), the same on
//   every build: the insertion order and both slot functions are fixed, and
//   the build stops the program if it ever fails to place a key.
// - Every return move key is in the table, exactly once, with its piece and
//   its squares (a < b); a slot without an entry has key 0
//   (tests/test_draws.cpp counts them against an enumeration of its
//   own).
#pragma once

#include "core/types.hpp"

namespace forkeng::return_moves {

constexpr int TableBits = 13;  // 8,192 slots, room for about twice the keys
constexpr int TableSize = 1 << TableBits;

struct Entry {
  Key key = 0;
  Piece piece = NoPiece;
  Square a = 0, b = 0;  // a < b
};

// piece_square[p][a] ^ piece_square[p][b] ^ side.
Key return_move_key(Piece p, Square a, Square b);

void init();

// The entry whose key is `k`, or nullptr.
const Entry* find(Key k);

// Entries stored (tests).
int stored();

}  // namespace forkeng::return_moves
