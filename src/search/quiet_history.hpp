// SPDX-License-Identifier: GPL-3.0-or-later

// quiet_history: the butterfly history of quiet moves (DESIGN.md §5.2,
// deliverable 5; KB search-techniques.md T9).
//
// Purpose: score quiet moves by how often they refuted positions elsewhere in
// the tree, indexed by side to move, from-square and to-square.
// Invariants:
// - Every value stays within [-HistoryMax, HistoryMax] for any sequence of
//   updates (tests/test_ordering.cpp). The update is the standard published
//   self-limiting ("gravity") form, cited in docs/ORIGINALITY.md: with the
//   amount b clamped to [-HistoryMax, HistoryMax], v becomes
//   v + b - v * |b| / HistoryMax, so it moves by less the closer it already
//   is to the limit on b's side, and by more when b goes against it.
// - A cutoff by a quiet move gives it a bonus that grows with depth, capped;
//   the quiet moves tried before it at that node get the same amount as a
//   malus.
// - Integer arithmetic only (bench determinism); 16-bit entries, so summing
//   several tables (the pair history below) cannot overflow an int.
// - The pair history (tier 2, T10; KB search-techniques.md §3.10) scores a
//   quiet move by a move that led to its node, paired with it: the
//   opponent's last move (the reply table) or the side's own previous move,
//   two plies back (the follow table). A move is a slot: its piece
//   (colour and type) and its destination square; a node reached by a null
//   move, or the root, has no arrival and reads and updates nothing. Same
//   scale, bounds and update as the butterfly history.
// - Every index is in range: side 0-1; from- and to-squares 0-63 (Move masks
//   them); a pair or take slot built from a real piece (colour and type), a
//   square 0-63 and a victim type Pawn to King; an arrival a pair slot; a
//   threat bucket 0-3.
//   Debug builds assert it at each read and update (<cassert>, compiled out
//   by NDEBUG in release builds, so bench and speed are unchanged).
#pragma once

#include <cassert>
#include <cstdint>
#include <cstdlib>

#include "core/types.hpp"
#include "tune/params.hpp"

namespace forkeng {

// Fork's scale and bonus (justified in DESIGN.md §5.2, "Search constants").
// The scale stays a constant (the int16 headroom depends on it); the bonus's
// factor and cap are in the parameter table: HistoryBonusFactor = 25 (half
// the factor of depth^2) and HistoryBonusCap = HistoryMax / 8, reached at
// depth 10.
constexpr int HistoryMax = 10000;
#ifndef FORK_TUNE
static_assert(HistoryBonusCap <= HistoryMax);  // tuning builds: its range's top (tests/test_params.cpp)
#endif

// The bonus for a cutoff at `depth`: HistoryBonusFactor / 2 * depth^2 (12.5),
// capped.
FORK_TUNABLE_CONSTEXPR int bonus_for_depth(int depth) {
  const int quadratic = depth * depth * HistoryBonusFactor / 2;
  return quadratic > HistoryBonusCap ? HistoryBonusCap : quadratic;
}

// A move's slot in the pair history: its piece (colour and type) and its
// destination square (for castling the encoded square, the rook's).
constexpr int PairSlots = 2 * 6 * 64;
constexpr int NoArrival = -1;
inline int pair_slot(Piece moved, Square to) {
  assert(side_of(moved) <= Black && kind_of(moved) <= King && "pair slot: not a piece");
  assert(to >= 0 && to < 64 && "pair slot: square out of range");
  return (side_of(moved) * 6 + kind_of(moved)) * 64 + to;
}

// The take history (tier 2, T11; KB search-techniques.md §3.11): captures
// scored by how often they cut in this tree, indexed by the moving piece
// (colour and type), its destination and the captured piece's type (a pawn
// for en passant). Same scale, bounds and update as the other histories.
constexpr int TakeSlots = PairSlots * 6;
inline int take_slot(Piece moved, Square to, PieceType victim) {
  assert(victim <= King && "take slot: victim is not a piece type");
  return pair_slot(moved, to) * 6 + victim;
}

class TakeHistory {
 public:
  int value(int slot) const {
    assert(slot >= 0 && slot < TakeSlots && "take history: slot out of range");
    return table_[slot];
  }

  // As QuietHistory::apply.
  void apply(int slot, int amount) {
    assert(slot >= 0 && slot < TakeSlots && "take history: slot out of range");
    std::int16_t& v = table_[slot];
    const int clamped = amount > HistoryMax ? HistoryMax : amount < -HistoryMax ? -HistoryMax : amount;
    v = static_cast<std::int16_t>(v + clamped - v * std::abs(clamped) / HistoryMax);
  }

  void clear() {
    for (std::int16_t& v : table_) v = 0;
  }

 private:
  std::int16_t table_[TakeSlots] = {};
};

// The searcher keeps both pair tables in one array, so the move selector
// holds a single pointer (the search stack's frame stays within its size
// guard, tests/test_search.cpp).
constexpr int ReplyTable = 0;
constexpr int FollowTable = 1;

class PairHistory {
 public:
  int value(int arrival, int slot) const {
    assert(arrival >= 0 && arrival < PairSlots && "pair history: arrival out of range");
    assert(slot >= 0 && slot < PairSlots && "pair history: slot out of range");
    return table_[arrival][slot];
  }

  // As QuietHistory::apply.
  void apply(int arrival, int slot, int amount) {
    assert(arrival >= 0 && arrival < PairSlots && "pair history: arrival out of range");
    assert(slot >= 0 && slot < PairSlots && "pair history: slot out of range");
    std::int16_t& v = table_[arrival][slot];
    const int clamped = amount > HistoryMax ? HistoryMax : amount < -HistoryMax ? -HistoryMax : amount;
    v = static_cast<std::int16_t>(v + clamped - v * std::abs(clamped) / HistoryMax);
  }

  void clear() {
    for (auto& row : table_)
      for (std::int16_t& v : row) v = 0;
  }

 private:
  std::int16_t table_[PairSlots][PairSlots] = {};
};

// Threat buckets (tier 2, T56; KB search-techniques.md §3.34, its first
// family): the butterfly history is split by whether the opponent attacks
// the move's from-square and its to-square in the position before the move,
// so "move an attacked piece to a safe square" learns apart from the same
// squares when nothing is attacked. Bucket 2 * (from attacked) + (to
// attacked); with the switch off every move reads and updates bucket 0, the
// table as it was. A castling move's to-square is its encoded rook square.
constexpr int ThreatBuckets = 4;
inline int threat_bucket(Bitboard attacked, Move m) {
  return static_cast<int>(((attacked >> m.from()) & 1) * 2 + ((attacked >> m.to()) & 1));
}

class QuietHistory {
 public:
  int value(Color side, Move m, int bucket = 0) const {
    assert(side <= Black && "quiet history: side out of range");
    assert(bucket >= 0 && bucket < ThreatBuckets && "quiet history: bucket out of range");
    return table_[side][bucket][m.from()][m.to()];
  }

  // Moves the entry by `amount` (positive: bonus, negative: malus), self-limiting.
  void apply(Color side, Move m, int amount, int bucket = 0) {
    assert(side <= Black && "quiet history: side out of range");
    assert(bucket >= 0 && bucket < ThreatBuckets && "quiet history: bucket out of range");
    std::int16_t& v = table_[side][bucket][m.from()][m.to()];
    const int clamped = amount > HistoryMax ? HistoryMax : amount < -HistoryMax ? -HistoryMax : amount;
    v = static_cast<std::int16_t>(v + clamped - v * std::abs(clamped) / HistoryMax);
  }

  void clear() {
    for (auto& side : table_)
      for (auto& bucket : side)
        for (auto& from : bucket)
          for (std::int16_t& v : from) v = 0;
  }

 private:
  // 64 KB: four buckets of the 16 KB butterfly table (T56's cost note).
  std::int16_t table_[2][ThreatBuckets][64][64] = {};
};

}  // namespace forkeng
