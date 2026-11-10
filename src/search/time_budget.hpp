// SPDX-License-Identifier: GPL-3.0-or-later

// time_budget: how long one search may run (DESIGN.md §5.2, deliverable 8;
// a first version is in place from deliverable 2 so games can be played).
//
// Purpose: turn the clock arguments of `go` and the Move Overhead option into
// a soft limit (checked between iterations: no new iteration starts after it)
// and a hard limit (polled during the search). Phase 5 replaces the formulas.
// Also, behind the search's switches use_stability_time and use_share_time
// (on since 2026-11-08) and use_root_gap_time (off), the soft limit's
// scaling after each finished iteration (below).
// Invariants:
// - Limits are milliseconds from the moment `go` was received; -1 means none.
// - When both are set, 1 <= soft_ms <= hard_ms. With a clock, hard_ms leaves
//   the Move Overhead and a further reserve unused: a tenth of the remaining
//   time.
// - go movetime N plans max(N - Move Overhead, N / 2), and at least 1 ms
//   (owner, 2026-10-25): a short movetime is not eaten by the overhead.
// - Plain integer arithmetic on 64-bit values; never negative.
#pragma once

#include <cstdint>
#include <optional>

namespace forkeng {

struct TimeBudget {
  std::int64_t soft_ms = -1;
  std::int64_t hard_ms = -1;
};

struct ClockInput {
  std::optional<std::int64_t> remaining_ms;  // the side to move's clock
  std::optional<std::int64_t> increment_ms;
  std::optional<std::int64_t> movestogo;
  std::optional<std::int64_t> movetime;
  std::int64_t overhead_ms = 0;
};

TimeBudget plan_time(const ClockInput& in);

// The soft limit's scaling by best-move stability and the every-pass node
// share (DESIGN.md §5.6 step 10, think tank R8; switches use_stability_time
// and use_share_time, on since 2026-11-08). After each finished iteration of a
// timed search, the soft check may use soft_ms scaled by
// soft_scale_permille: Fork's fitted chance that the best move changes
// within the next two iterations (X6, §5.7 on measure/step1), relative to
// the typical chance at that depth, times a balance that keeps the mean
// spend unchanged, never below a floor. Invariants:
// - 1000 (unchanged) for Off, below depth TimeScaleMinDepth, for mate and
//   tablebase scores, and for a share of 0 in StabilityAndShare.
// - Integer fixed point only (deterministic on every compiler and libm);
//   non-increasing in stability, and in the share for StabilityAndShare.
// - scaled_soft_ms never scales a soft limit equal to its hard limit (go
//   movetime), never returns more than hard_ms nor less than 1, and leaves a
//   missing limit (-1) as it is.
enum class TimeScaleVariant : std::uint8_t { Off, StabilityOnly, StabilityAndShare };

struct IterationSignals {
  int depth = 0;
  int stability = 0;  // finished iterations in a row, ending at this one, with the same best move
  int share_all = 0;  // the best move's per mille of the iteration's nodes over every aspiration pass
  int score = 0;
};

int soft_scale_permille(TimeScaleVariant variant, const IterationSignals& signals);
std::int64_t scaled_soft_ms(std::int64_t soft_ms, std::int64_t hard_ms, int permille);

// Root-gap time (ideas.md idea 61 part 6; switch use_root_gap_time, off by
// default): extra soft-limit time when another root move comes within
// RootGapBand of the best one. `score` is the finished iteration's score;
// `runner_up` is the largest score any other root move returned in that
// iteration's last aspiration pass (fail-soft: exact for a move that was best
// earlier in the pass, an upper bound for one that failed low;
// -ScoreInfinite with one root move), so score - runner_up never exceeds the
// true gap; `reached` is the search's probe (Searcher::probe_root_gap): some
// other root move reaches score - RootGapBand on a zero window at the
// iteration's depth.
// The fail-soft gap alone cannot decide closeness: on the bench positions it
// is 0 at the median iteration (fail-soft upper bounds sit at the window), so
// it only rules a pair out, and the probe decides. Invariants:
// - 1000 + RootGapExtra when the rule applies and `reached`; 1000
//   (unchanged) otherwise. The rule applies from depth TimeScaleMinDepth, for
//   a score that is not a mate or tablebase score, with a runner-up, and
//   with score - runner_up below RootGapBand (otherwise every other move is
//   already known to be at least RootGapBand worse, and no probe is needed).
// - Never below 1000 (it only extends); integer arithmetic only.
int root_gap_permille(int depth, int score, int runner_up, bool reached);

}  // namespace forkeng
