// SPDX-License-Identifier: GPL-3.0-or-later

// time_budget: how long one search may run (DESIGN.md §5.2, deliverable 8;
// a first version is in place from deliverable 2 so games can be played).
//
// Purpose: turn the clock arguments of `go` and the Move Overhead option into
// a soft limit (checked between iterations: no new iteration starts after it)
// and a hard limit (polled during the search). Phase 5 replaces the formulas.
// Also, behind the search's switches use_stability_time and use_share_time
// (off), the soft limit's scaling after each finished iteration (below).
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
// and use_share_time, off by default). After each finished iteration of a
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
// - deep_depth (switch use_deep_time_depth, on since 2026-11-14; the
//   parameter's own default stays false): the depth is clamped at 60 instead
//   of 19, so the scale keeps following depth in deep searches (E2 of the
//   bug review of 2026-11-11); identical up to depth 19.
enum class TimeScaleVariant : std::uint8_t { Off, StabilityOnly, StabilityAndShare };

struct IterationSignals {
  int depth = 0;
  int stability = 0;  // finished iterations in a row, ending at this one, with the same best move
  int share_all = 0;  // the best move's per mille of the iteration's nodes over every aspiration pass
  int score = 0;
};

int soft_scale_permille(TimeScaleVariant variant, const IterationSignals& signals, bool deep_depth = false);
std::int64_t scaled_soft_ms(std::int64_t soft_ms, std::int64_t hard_ms, int permille);

}  // namespace forkeng
