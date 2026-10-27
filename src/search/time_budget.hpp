// time_budget: how long one search may run (DESIGN.md §5.2, deliverable 8;
// a first version is in place from deliverable 2 so games can be played).
//
// Purpose: turn the clock arguments of `go` and the Move Overhead option into
// a soft limit (checked between iterations: no new iteration starts after it)
// and a hard limit (polled during the search). Phase 5 replaces the formulas.
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

}  // namespace forkeng
