// quiet_history: the butterfly history of quiet moves (DESIGN.md §5.2,
// deliverable 5; KB search-techniques.md T9).
//
// Purpose: score quiet moves by how often they refuted positions elsewhere in
// the tree, indexed by side to move, from-square and to-square.
// Invariants:
// - Every value stays within [-HistoryMax, HistoryMax] for any sequence of
//   updates (tests/test_ordering.cpp): the update is self-limiting ("gravity"),
//   moving a value by bonus * (1 - |value| / HistoryMax) towards the bonus's
//   sign, so a result against a large stored value moves it more than one
//   that confirms it.
// - A cutoff by a quiet move gives it a bonus that grows with depth, capped;
//   the quiet moves tried before it at that node get the same amount as a
//   malus.
// - Integer arithmetic only (bench determinism); 16-bit entries, so summing
//   several tables later (continuation history, tier 2) cannot overflow an
//   int.
#pragma once

#include <cstdint>
#include <cstdlib>

#include "core/types.hpp"

namespace forkeng {

constexpr int HistoryMax = 16384;
constexpr int HistoryBonusCap = 1600;

// The bonus for a cutoff at `depth` (Fork's own shape: quadratic, capped).
constexpr int bonus_for_depth(int depth) {
  return depth * depth * 16 > HistoryBonusCap ? HistoryBonusCap : depth * depth * 16;
}

class QuietHistory {
 public:
  int value(Color side, Move m) const { return table_[side][m.from()][m.to()]; }

  // Moves the entry by `amount` (positive: bonus, negative: malus), self-limiting.
  void apply(Color side, Move m, int amount) {
    std::int16_t& v = table_[side][m.from()][m.to()];
    const int clamped = amount > HistoryMax ? HistoryMax : amount < -HistoryMax ? -HistoryMax : amount;
    v = static_cast<std::int16_t>(v + clamped - v * std::abs(clamped) / HistoryMax);
  }

  void clear() {
    for (auto& side : table_)
      for (auto& from : side)
        for (std::int16_t& v : from) v = 0;
  }

 private:
  std::int16_t table_[2][64][64] = {};
};

}  // namespace forkeng
