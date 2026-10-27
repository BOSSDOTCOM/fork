#include "search/time_budget.hpp"

#include <algorithm>

namespace forkeng {

namespace {

// Conservative fixed values (Phase 5 tunes time management); the formula
// they feed is credited at plan_time below.
constexpr std::int64_t AssumedMovesLeft = 30;     // sudden death: plan as if this many moves remain
constexpr std::int64_t MaxMovesToGo = 40;         // a larger movestogo is treated as this
constexpr std::int64_t HardOverSoft = 4;          // the hard limit allows this many soft budgets
constexpr std::int64_t ReserveDivisor = 10;       // never plan into the last 1/10 of the clock,
constexpr std::int64_t ReserveOverheads = 2;      // nor into the last two Move Overheads (deliverable 8)
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
  // The reserve: a tenth of the clock, but never less than two Move
  // Overheads (deliverable 8, DESIGN.md §5.2 "Search constants"): the
  // overhead is the per-move latency allowance, and Milestone A's time loss
  // came from a clock planned down to about one overhead, where one slow
  // move flagged. Below the reserve Fork moves at once and the increment
  // rebuilds the clock.
  const std::int64_t reserve = std::max(available / ReserveDivisor, ReserveOverheads * overhead);
  const std::int64_t cap = std::max<std::int64_t>(1, available - reserve);
  // The budget. Each move gets an even part of the clock, as if
  // AssumedMovesLeft moves remained (or movestogo), plus three quarters of
  // the increment, which comes back every move; the soft limit is that
  // share, and the hard limit allows HardOverSoft shares for a search that
  // needs more (a fail low, an unstable best move), never into the reserve.
  // Credit (owner's decision, 2026-10-26): this shape, the clock less the
  // overhead over 30 moves plus an increment term with a hard limit of four
  // shares capped short of the clock, is the same as Berserk 4.5.0-8's time
  // allocation (jhonnold/berserk, src/uci.c, GPL-3.0), found by the
  // originality-checker's constant screen. Fork's deliverable 2 wrote it
  // without opening Berserk's source, but model memory may have reproduced
  // the known form, so it is credited and kept (docs/ORIGINALITY.md). Fork's
  // own parts: three quarters of the increment (multiplied before dividing:
  // the first external review's claim (b)), the soft limit at one share, and
  // the reserve's floor of two Move Overheads.
  const std::int64_t share = available / moves + std::min(increment, cap) * 3 / 4;
  t.hard_ms = std::clamp<std::int64_t>(std::min(share, cap / HardOverSoft) * HardOverSoft, 1, cap);
  t.soft_ms = std::clamp<std::int64_t>(share, 1, t.hard_ms);
  return t;
}

}  // namespace forkeng
