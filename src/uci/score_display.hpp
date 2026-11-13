// SPDX-License-Identifier: GPL-3.0-or-later

// score_display: the centipawn score a UCI info line reports when the
// CalibratedScore option is on (display only).
//
// Purpose: Fork's search scores understate how surely an advantage converts.
// Over Fork's own recent games (2026-11-12; the calibration report in
// ~/fork-data/calib-1112, DESIGN.md "Search constants", score display),
// the expected game score at search score s follows
// 1 / (1 + exp(-s / k)) with k about 67 cp, while the network's own scale
// (r8brft1's S = 88, docs/nets.md, which Fork's web eval bar also uses)
// implies k = 88. Multiplying the reported score by 88 / 67 puts it on the
// network's scale: 1 / (1 + exp(-shown / 88)) then matches the measured
// expected score. The search never sees this value.
// Invariants:
// - Display only: no search, evaluation, bench or data-generation code
//   calls this.
// - Mate and tablebase scores (is_tb_or_mate) pass through unchanged.
// - Monotonic and odd (f(-s) = -f(s)); every other score stays strictly
//   below the tablebase band, so the order of all scores is kept.
#pragma once

#include <cstdint>

#include "search/score_bounds.hpp"

namespace forkeng {

// The scale the shown score is put on: r8brft1's output scale S
// (docs/nets.md).
constexpr int DisplayTargetScale = 88;
// The logistic scale fitted to Fork's own games (search scores, the 40+0.4
// UHO self-play of probcut-ltc2, 4,992 games: 67.0 cp, 95% 63.9 to 69.5).
// Refit when the default network changes.
constexpr int DisplayFittedScale = 67;

constexpr int calibrated_display_score(int score) {
  if (is_tb_or_mate(score)) return score;
  const std::int64_t num = static_cast<std::int64_t>(score < 0 ? -score : score) * DisplayTargetScale;
  std::int64_t shown = (num + DisplayFittedScale / 2) / DisplayFittedScale;  // round half up on |score|
  constexpr std::int64_t Ceiling = TbWinScore - MaxPly - 1;                     // below the tablebase band
  if (shown > Ceiling) shown = Ceiling;
  return score < 0 ? -static_cast<int>(shown) : static_cast<int>(shown);
}

}  // namespace forkeng
