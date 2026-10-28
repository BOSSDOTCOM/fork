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
//   several tables later (continuation history, tier 2) cannot overflow an
//   int.
#pragma once

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
