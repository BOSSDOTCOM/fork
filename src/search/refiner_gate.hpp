// SPDX-License-Identifier: GPL-3.0-or-later

// refiner_gate: where the Boundary Refiner is consulted (ideas.md 59; step 3,
// docs/research/boundary-refiner/step3-plan.md §2.6).
//
// Purpose: window_gap, the distance from a static evaluation to the nearest
// finite bound of its node's window (idea 59 step 1's measurement, DESIGN.md
// §5.7), and the gate that decides at an evaluation site whether the refiner
// is consulted, with the tally of what it did. The gate is a predicate over a
// GateSite, the facts already in hand at the site; another detector (the
// logistic gate, idea 61's decision kinds) is another predicate over the same
// facts, with no change at the sites. The search consults the gate only in
// refiner builds (FORK_REFINER, CMake FORK_REFINER_NET); every build compiles
// it, so its tests run everywhere.
// Invariants:
// - window_gap is -1 when neither bound is finite (both in the mate or
//   tablebase band), else the distance in cp to the nearer finite bound.
// - The gate fires exactly when that gap is known and at most the site's
//   margin (inclusive, as step 1 counted); a margin of -1 never fires. Builds
//   without a refiner default both margins to -1.
// - No allocation, no floating point, no virtual dispatch.
#pragma once

#include <cstdint>

#include "core/position.hpp"
#include "search/score_bounds.hpp"

namespace forkeng {

// The gap, or -1 when neither bound is finite.
constexpr int window_gap(int eval, int alpha, int beta) {
  const bool low = !is_tb_or_mate(alpha), high = !is_tb_or_mate(beta);
  if (!low && !high) return -1;
  const int to_alpha = eval > alpha ? eval - alpha : alpha - eval;
  const int to_beta = eval > beta ? eval - beta : beta - eval;
  return !low ? to_beta : !high ? to_alpha : to_alpha < to_beta ? to_alpha : to_beta;
}

// The gate's settings (UCI RefinerMarginMain, RefinerMarginQuiesce and
// RefineReused; `fork bench MAIN QUIESCE [reused]`). refine_reused is G1 of
// the plan (§2.6): an evaluation reused from the TT and not yet refined is
// refined too where the gate fires; off (G0), a reused evaluation is used as
// stored.
struct RefinerGate {
#ifdef FORK_REFINER
  int margin_main = FORK_REFINER_MARGIN_MAIN;  // cp; -1: never
  int margin_quiesce = FORK_REFINER_MARGIN_QUIESCE;
#else
  int margin_main = -1;
  int margin_quiesce = -1;
#endif
  bool refine_reused = false;
};

// What a gate may read at an evaluation site: all of it already computed.
struct GateSite {
  const Position& pos;
  int base_eval;  // the base network's evaluation (computed, or the TT's stored one)
  int alpha, beta;
  int depth;  // 0 in quiescence
  int ply;
  bool quiesce;
};

constexpr bool gate_fires(const RefinerGate& g, const GateSite& s) {
  const int margin = s.quiesce ? g.margin_quiesce : g.margin_main;
  const int gap = window_gap(s.base_eval, s.alpha, s.beta);
  return margin >= 0 && gap >= 0 && gap <= margin;
}

// What the gate did in one search (reset at each), for the `info string
// refiner` line: computed evaluations and refiner calls in the main search
// and in quiescence; reused TT evaluations the gate fired on, those already
// refined when stored (the plan's M4), and those refined now (G1); the sum
// of (used - base) and of its absolute value over the calls; and, in stats
// builds only, the zero bytes of the clipped accumulator over the calls (M3).
struct RefinerTally {
  std::uint64_t main_evals = 0;
  std::uint64_t main_calls = 0;
  std::uint64_t quiesce_evals = 0;
  std::uint64_t quiesce_calls = 0;
  std::uint64_t reused_near = 0;
  std::uint64_t reused_refined = 0;
  std::uint64_t reused_calls = 0;
  std::int64_t shift_sum = 0;
  std::int64_t abs_shift_sum = 0;
  std::uint64_t zero_bytes = 0;
};

}  // namespace forkeng
