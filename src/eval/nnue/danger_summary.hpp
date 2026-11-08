// SPDX-License-Identifier: GPL-3.0-or-later

// danger_summary: a few counts of king danger and loose pieces, read off the
// board's attack sets (the Boundary Refiner's architecture 2, ideas.md 59;
// docs/research/boundary-refiner/step3-plan.md §2.2 (iii)).
//
// Purpose: for each side X, how much of X's king zone the other side attacks,
// how many of those squares only X's king defends, from how many squares the
// other side could check X's king safely, how many of X's pieces are pinned
// to X's king, and how many of X's pieces are exposed (XGR's rule,
// exposed_pieces in accumulator.hpp). One pass over both sides' attack sets,
// which also yields the exposed set itself, so the refiner's exposure rows
// need no second pass.
// Invariants:
// - X's king zone is its king's square and the squares next to it.
// - "Attacked" is on the board's occupancy, every piece of a side counted
//   (pins ignored), as exposed_pieces counts.
// - A safe check against X is an empty or X-occupied square from which some
//   knight, bishop, rook or queen of the other side would give check, which
//   such a piece of the other side attacks, and which X does not attack.
//   Each square counts once.
// - The exposed set equals exposed_pieces(pos) (tests/test_refiner.cpp).
// - No allocation, no floating point.
#pragma once

#include "core/position.hpp"

namespace forkeng {

// Each count indexed by the side X it describes.
struct DangerSummary {
  int zone_attacked[2] = {};
  int zone_weak[2] = {};
  int safe_checks[2] = {};
  int pinned_count[2] = {};
  int exposed_count[2] = {};
};

// The counts for `pos`; `exposed` receives the exposed pieces of both sides.
DangerSummary danger_summary(const Position& pos, Bitboard& exposed);

}  // namespace forkeng
