// SPDX-License-Identifier: GPL-3.0-or-later

// revisit: the table of reversible piece moves by their key change, for
// finding a move back to an earlier position (think tank R12, the engine
// survey's F7; KB search-techniques.md §3.29 T51 describes the published
// method this follows in idea; Fork's table and lookup are its own).
//
// Purpose: a knight, bishop, rook, queen or king of either colour moving
// between two squares it connects on an empty board changes the position's
// key by piece_square[p][a] ^ piece_square[p][b] ^ side, whichever way it
// moves. The table maps each such change to its piece and squares, so a
// position can ask, for each earlier position of its repetition window that
// has the other side to move, whether one move of a piece would turn this
// position into that one (Position::revisit_available).
// Invariants:
// - Built once by init() from Fork's own Zobrist keys (core/zobrist.hpp), at
//   startup after them (core::init), never typed in: a change of the keys
//   rebuilds it.
// - Every reversible piece move is stored exactly once (both directions share
//   one entry), and find() returns it for its key change; for any other key
//   find() returns -1 (tests/test_draws.cpp checks Position::revisit_available
//   against making every legal move).
// - Open addressing with linear probing over a power-of-two table at most
//   half full, indexed by the key change's low bits: a miss ends at the first
//   empty slot.
#pragma once

#include <cstdint>

#include "core/types.hpp"

namespace forkeng::revisit {

constexpr int SlotBits = 13;
constexpr int Slots = 1 << SlotBits;

// One reversible move: its piece and its two squares (a < b).
struct Shuttle {
  Piece piece;
  Square a, b;
};

extern Key keys[Slots];       // 0: an empty slot (no key change of a real move is 0)
extern Shuttle moves[Slots];  // the move at each filled slot

void init();  // after zobrist::init(); called by forkeng::init()

// The slot holding this key change, or -1 if no reversible move makes it.
inline int find(Key change) {
  for (int i = static_cast<int>(change & (Slots - 1));; i = (i + 1) & (Slots - 1)) {
    if (keys[i] == 0) return -1;  // first, so a change of 0 never matches an empty slot
    if (keys[i] == change) return i;
  }
}

// Filled slots (tests).
int stored();

}  // namespace forkeng::revisit
