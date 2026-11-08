// SPDX-License-Identifier: GPL-3.0-or-later

// refiner_gate: where the Boundary Refiner is consulted (ideas.md 59).
//
// Purpose: window_gap, the distance from a static evaluation to the nearest
// finite bound of its node's window (idea 59 step 1's measurement, DESIGN.md
// §5.7; every build), and, in oracle builds (FORK_REFINER), the gate that
// decides at a computed evaluation whether the refiner network is consulted,
// with the tally of what it did. The gate is a predicate over a GateSite, the
// facts already in hand at the evaluation, selected by GateKind: the window
// distance (one margin for the main search, one for quiescence) is the first
// kind; a feature-based or combined detector is another kind and another case
// of gate_fires, with no change at the sites. Two control kinds (owner,
// 2026-11-07, after setting (a)'s screen): Shift, the window gate with a
// constant added to the base evaluation instead of the refiner's (the
// refiner never consulted), and Hashed, the refiner consulted at computed
// evaluations sampled by the position's key at fixed rates, whatever the
// window.
// Invariants:
// - window_gap is -1 when neither bound is finite (both in the mate or
//   tablebase band), else the distance in cp to the nearer finite bound.
// - The window and shift gates fire exactly when that gap is known and at
//   most the site's margin (inclusive, as step 1 counted); a margin of -1
//   never fires. The hashed gate fires when the key's hash, splitmix's output
//   function modulo a million, is below the site's rate in parts per million:
//   the same position always gets the same answer.
// - No allocation, no floating point, no virtual dispatch: one switch per
//   evaluation.
#pragma once

#include <cstdint>

#include "core/position.hpp"
#include "core/splitmix.hpp"
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

#ifdef FORK_REFINER
enum class GateKind : std::uint8_t { Window, Shift, Hashed };

// The gate's settings (the UCI options RefinerGateKind, RefinerMarginMain,
// RefinerMarginQuiesce, RefinerShift, RefinerSampleMain, RefinerSampleQuiesce
// and RefinerLazy; `fork bench MAIN QUIESCE [lazy]`). Defaults: the window
// gate at the build's FORK_REFINER_MARGIN_MAIN and FORK_REFINER_MARGIN_QUIESCE.
// lazy does not change the gate: it keeps the refiner's accumulators updated
// only where the gate fires, instead of beside the base's at every computed
// evaluation (the same evaluations, so the same tree).
struct RefinerGate {
  GateKind kind = GateKind::Window;
  int margin_main = FORK_REFINER_MARGIN_MAIN;  // cp; -1: never
  int margin_quiesce = FORK_REFINER_MARGIN_QUIESCE;
  // Shift: added to the base evaluation where the gate fires, in thousandths
  // of a cp; the whole cp always, one more at that many sites per thousand,
  // picked by the key's hash, so the shifts average exactly this.
  int shift_millicp = 0;
  // Hashed: the share of computed evaluations sampled, parts per million.
  int sample_main_ppm = 0;
  int sample_quiesce_ppm = 0;
  bool lazy = false;
};

// What a gate may read at an evaluation site: all of it already computed.
struct GateSite {
  const Position& pos;
  int base_eval;  // the base network's evaluation (or the TT's stored one)
  int alpha, beta;
  int depth;  // 0 in quiescence
  int ply;
  bool quiesce;
};

inline bool gate_fires(const RefinerGate& g, const GateSite& s) {
  switch (g.kind) {
    case GateKind::Window:
    case GateKind::Shift: {
      const int margin = s.quiesce ? g.margin_quiesce : g.margin_main;
      const int gap = window_gap(s.base_eval, s.alpha, s.beta);
      return margin >= 0 && gap >= 0 && gap <= margin;
    }
    case GateKind::Hashed: {
      const int rate = s.quiesce ? g.sample_quiesce_ppm : g.sample_main_ppm;
      return splitmix_finalize(s.pos.key()) % 1000000 < static_cast<std::uint64_t>(rate < 0 ? 0 : rate);
    }
  }
  return false;
}

// What the gate did in one search (reset at each), for the `info string
// refiner` line: computed evaluations and gate calls in the main search and
// in quiescence, reused TT evaluations the gate would have fired on, the sum
// of (refined - base) and of its absolute value over the calls, and the
// refiner evaluations made (consults: the calls, except under Shift, none).
struct RefinerTally {
  std::uint64_t main_evals = 0;
  std::uint64_t main_calls = 0;
  std::uint64_t quiesce_evals = 0;
  std::uint64_t quiesce_calls = 0;
  std::uint64_t reused_near = 0;
  std::int64_t shift_sum = 0;
  std::int64_t abs_shift_sum = 0;
  std::uint64_t consults = 0;
};
#endif

}  // namespace forkeng
