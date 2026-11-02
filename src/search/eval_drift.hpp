// SPDX-License-Identifier: GPL-3.0-or-later

// eval_drift: the pawn drift table (tier 2, T32; KB search-techniques.md
// §3.23, static evaluation correction history).
//
// Purpose: learn how far search results land from the raw static eval in
// positions with the same pawn structure, per side to move, and add that
// drift to the eval the search estimates with (pruning and the quiescence
// stand-pat). The TT and anything that could feed training keep the raw
// eval (DESIGN.md §5.2, tier 2 step 5).
// Invariants:
// - Each entry is the drift in 1/DriftGrain centipawns. An update moves it
//   toward the observed error, clamped to [-DriftLimit, DriftLimit] cp, by
//   the fraction min(depth, DriftWeightCap) / DriftWeightTotal of the gap: a
//   weighted running mean, so no entry ever leaves [-DriftLimit, DriftLimit]
//   cp for any sequence of updates (tests/test_eval_drift.cpp).
// - The drift read is whole centipawns, rounded toward zero.
// - Integer arithmetic only (bench determinism). One table per Searcher
//   (per thread); sharing between threads is Phase 6 (ideas.md idea 17).
// - The slot is the pawn structure key's top bits; positions whose keys share
//   them share an entry (no key check: a collision only blurs the mean).
#pragma once

#include <cstdint>

#include "core/types.hpp"
#include "tune/params.hpp"

namespace forkeng {

// Fork's sizes (justified in DESIGN.md §5.2, "Search constants"); the
// weights and the limit are in the parameter table.
constexpr int DriftSlotBits = 14;
constexpr int DriftSlots = 1 << DriftSlotBits;
constexpr int DriftGrain = 128;

class EvalDrift {
 public:
  static int slot(std::uint32_t structure) { return static_cast<int>(structure >> (32 - DriftSlotBits)); }

  // The drift for `side` to move in `structure`, in centipawns.
  int offset(Color side, std::uint32_t structure) const { return table_[side][slot(structure)] / DriftGrain; }

  // A search of a node with this structure scored `error` cp away from its
  // raw static eval (score minus eval), at `depth`.
  void learn(Color side, std::uint32_t structure, int error, int depth) {
    const int limit = DriftLimit * DriftGrain;
    const int target = error * DriftGrain > limit ? limit : error * DriftGrain < -limit ? -limit : error * DriftGrain;
    // At most the whole gap: a weight above the total would overshoot.
    const int cap = DriftWeightCap < DriftWeightTotal ? DriftWeightCap : DriftWeightTotal;
    const int weight = depth < cap ? depth : cap;
    std::int32_t& v = table_[side][slot(structure)];
    v += (target - v) * weight / DriftWeightTotal;
  }

  void clear() {
    for (auto& side : table_)
      for (std::int32_t& v : side) v = 0;
  }

 private:
  std::int32_t table_[2][DriftSlots] = {};
};

}  // namespace forkeng
