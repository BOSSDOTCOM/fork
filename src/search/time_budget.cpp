#include "search/time_budget.hpp"

#include <algorithm>

namespace forkeng {

namespace {

// Fork's own conservative choices (Phase 5 tunes time management).
constexpr std::int64_t AssumedMovesLeft = 30;     // sudden death: plan as if this many moves remain
constexpr std::int64_t MaxMovesToGo = 40;         // a larger movestogo is treated as this
constexpr std::int64_t HardOverSoft = 4;          // the hard limit allows this many soft budgets
constexpr std::int64_t ReserveDivisor = 10;       // never plan into the last 1/10 of the clock
constexpr std::int64_t MovetimeFloorDivisor = 2;  // go movetime keeps at least 1/2 of its time

// Every input is clamped to [-2^40, 2^40] ms (about 35 years either way)
// first, so no difference or sum below can overflow, even for the INT64_MIN
// and INT64_MAX that go_limits.hpp clamps out-of-range numbers to.
constexpr std::int64_t ClockCap = std::int64_t{1} << 40;
std::int64_t bounded(std::int64_t v) { return std::clamp(v, -ClockCap, ClockCap); }

}  // namespace

TimeBudget plan_time(const ClockInput& in) {
  TimeBudget t;
  const std::int64_t overhead = std::clamp<std::int64_t>(in.overhead_ms, 0, ClockCap);
  if (in.movetime) {
    // The Move Overhead comes off, but never more than half of the time
    // asked for (owner, 2026-10-25): with the full 100 ms default taken off,
    // every movetime of 100 ms or less played at 1 ms, silently weakening
    // short-movetime tests. A clock game keeps its full overhead below.
    const std::int64_t asked = bounded(*in.movetime);
    t.soft_ms = t.hard_ms = std::max<std::int64_t>({1, asked - overhead, asked / MovetimeFloorDivisor});
    return t;
  }
  if (!in.remaining_ms) return t;  // no clock: depth, nodes, mate or infinite decide
  const std::int64_t available = std::max<std::int64_t>(1, bounded(*in.remaining_ms) - overhead);
  const std::int64_t moves =
      in.movestogo ? std::clamp<std::int64_t>(*in.movestogo, 1, MaxMovesToGo) : AssumedMovesLeft;
  const std::int64_t increment = std::clamp<std::int64_t>(in.increment_ms.value_or(0), 0, ClockCap);
  const std::int64_t cap = std::max<std::int64_t>(1, available - available / ReserveDivisor);
  const std::int64_t share = available / moves + std::min(increment, cap) / 4 * 3;
  t.hard_ms = std::clamp<std::int64_t>(std::min(share, cap / HardOverSoft) * HardOverSoft, 1, cap);
  t.soft_ms = std::clamp<std::int64_t>(share, 1, t.hard_ms);
  return t;
}

}  // namespace forkeng
