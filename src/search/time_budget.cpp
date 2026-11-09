// SPDX-License-Identifier: GPL-3.0-or-later

#include "search/time_budget.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <limits>

#include "search/score_bounds.hpp"
#include "tune/params.hpp"

namespace forkeng {

namespace {

// Conservative fixed values (Phase 5 tunes time management), in the
// parameter table (src/tune/params.hpp): AssumedMovesLeft (sudden death: plan
// as if this many moves remain), MaxMovesToGo (a larger movestogo is treated
// as this), HardOverSoft (the hard limit allows this many soft budgets),
// ReserveDivisor (never plan into the last 1/10 of the clock). The formula
// they feed is credited at plan_time below. Not tuned (an owner's rule):
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
  const std::int64_t moves = in.movestogo ? std::clamp<std::int64_t>(*in.movestogo, 1, MaxMovesToGo)
                                          : std::int64_t{AssumedMovesLeft};
  const std::int64_t increment = std::clamp<std::int64_t>(in.increment_ms.value_or(0), 0, ClockCap);
  // The reserve (deliverable 8, variant B2, "danger zone"): a tenth of the
  // clock, and one more Move Overhead only when the time left is within
  // DangerZoneOverheads overheads plus one increment of running out. The
  // overhead, already taken off, covers each move's normal latency; only so
  // close to the end can one slow move flag, so only there is more kept.
  const bool danger_zone = available < DangerZoneOverheads * overhead + increment;
  const std::int64_t reserve =
      danger_zone ? std::max(available / ReserveDivisor, overhead) : available / ReserveDivisor;
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
  // the danger-zone reserve above.
  const std::int64_t share = available / moves + std::min(increment, cap) * 3 / 4;
  t.hard_ms = std::clamp<std::int64_t>(std::min(share, cap / HardOverSoft) * HardOverSoft, 1, cap);
  t.soft_ms = std::clamp<std::int64_t>(share, 1, t.hard_ms);
  return t;
}

namespace {

// The soft limit's scaling (time_budget.hpp; DESIGN.md §5.6 step 10). Every
// value below is a placeholder from Fork's own fit, X6 (18,782 iterations at
// depth >= 8 of 2,086 searches at 2M nodes in 60 of Fork's STC games; §5.7 on
// measure/step1, derived by tools/measure/tm_curve.py there), justified in
// DESIGN.md §5.2 "Search constants", and awaits the originality-checker's
// constant screen before its SPRT.
// The fit's domain: X6 has no rows below depth 8 (its primary depth); 19 is
// the last depth with at least 1% of the rows; the share is clipped to
// [5, 995] per mille, as X6 declared. The stability cap is the 99th
// percentile of the stability count over X6's rows at depth >= 8, the
// smallest integer whose cumulative share reaches 99% (the owner's rule,
// declared before it was computed, 2026-11-07).
constexpr int TimeScaleMinDepth = 8;
constexpr int TimeScaleMaxDepth = 19;
constexpr int TimeScaleStabilityCap = 72;
constexpr int TimeScaleShareMin = 5;
constexpr int TimeScaleShareMax = 995;
// Never below 36% of the soft limit: at most two iterations short of it at
// Fork's iteration growth of 5/3 ((3/5)^2 = 0.36). It binds at about a
// quarter of X6's rows (the long-stable ones), which the balance includes.
constexpr int TimeScaleFloor = 360;
// The mean-spend balance per variant, per mille: the factor that keeps the
// mean spend equal to the plain soft limit's when X6's searches are replayed
// with nodes as the clock, averaged over 100k, 250k and 500k-node budgets.
constexpr int TimeScaleBalanceStability = 1030;
constexpr int TimeScaleBalanceShare = 996;

// Logistic fits of "the best move changes within the next two iterations",
// coefficients in Q16 (x 65,536). StabilityFit and ShareFit give the chance
// for the iteration at hand; DepthFit gives the typical chance at its depth,
// which divides it: depth normalises the scale, keeping the balance near 1 at
// every time control, and is no signal of its own (owner, 2026-11-07).
struct ChangeFit {
  std::int64_t intercept;
  std::int64_t per_iteration;  // per iteration of stability
  std::int64_t per_logit;      // per unit of the share's logit
  std::int64_t per_ply;        // per ply of depth
};
constexpr ChangeFit StabilityFit{35056, -13610, 0, -6328};   // 0.534912, -0.207666, -, -0.096556
constexpr ChangeFit ShareFit{31102, -11639, -12129, -6772};  // 0.474586, -0.177596, -0.185073, -0.103338
constexpr ChangeFit DepthFit{37191, 0, 0, -13876};           // 0.567490, -, -, -0.211730

// log2(x) in Q16 for x >= 1: the integer part from the highest set bit, then
// 16 fraction bits by squaring the mantissa (Q30, in [1, 2)).
std::int64_t fixed_log2(std::uint64_t x) {
  constexpr std::uint64_t One = std::uint64_t{1} << 30;
  const int top = std::bit_width(x) - 1;
  std::uint64_t m = top <= 30 ? x << (30 - top) : x >> (top - 30);
  std::int64_t fraction = 0;
  for (int bit = 15; bit >= 0; --bit) {
    m = m * m >> 30;
    if (m >= 2 * One) {
      m >>= 1;
      fraction |= std::int64_t{1} << bit;
    }
  }
  return std::int64_t{top} * 65536 + fraction;
}

// 2^(-w / 65,536) in Q30, for |w| / 65,536 up to 30: 2^n times 2^f with n
// whole and f in [0, 1), 2^f the product over f's bits j of 2^(2^-j); those
// roots are computed here, each the square root of the one before.
std::uint64_t fixed_exp2_neg(std::int64_t w) {
  constexpr std::uint64_t One = std::uint64_t{1} << 30;
  static constexpr std::array<std::uint64_t, 17> roots = [] {
    std::array<std::uint64_t, 17> r{};
    r[0] = 2 * One;
    for (std::size_t j = 1; j < r.size(); ++j) {
      const std::uint64_t v = r[j - 1] << 30;  // Newton's integer square root of v
      std::uint64_t x = v;
      for (std::uint64_t next = (x + v / x) / 2; next < x; next = (x + v / x) / 2) x = next;
      r[j] = x;
    }
    return r;
  }();
  const std::int64_t v = -w;
  const std::int64_t whole = v >= 0 ? v / 65536 : -((-v + 65535) / 65536);  // floor
  const std::int64_t fraction = v - whole * 65536;                          // [0, 65,536)
  std::uint64_t result = One;
  for (int j = 1; j <= 16; ++j)
    if (fraction & (std::int64_t{1} << (16 - j))) result = result * roots[static_cast<std::size_t>(j)] >> 30;
  return whole >= 0 ? result << whole : result >> -whole;
}

}  // namespace

int soft_scale_permille(TimeScaleVariant variant, const IterationSignals& signals) {
  constexpr int Unchanged = 1000;
  constexpr std::uint64_t One = std::uint64_t{1} << 30;
  constexpr std::int64_t Log2E = 94548;  // log2(e) in Q16 (math)
  constexpr std::int64_t Ln2 = 45426;    // ln(2) in Q16 (math)
  if (variant == TimeScaleVariant::Off || signals.depth < TimeScaleMinDepth || is_tb_or_mate(signals.score))
    return Unchanged;
  const bool with_share = variant == TimeScaleVariant::StabilityAndShare;
  if (with_share && signals.share_all <= 0) return Unchanged;
  const std::int64_t s = std::clamp(signals.stability, 1, TimeScaleStabilityCap);
  const std::int64_t d = std::min(signals.depth, TimeScaleMaxDepth);
  const ChangeFit& fit = with_share ? ShareFit : StabilityFit;
  std::int64_t z1 = fit.intercept + fit.per_iteration * s + fit.per_ply * d;
  if (with_share) {
    const auto p =
        static_cast<std::uint64_t>(std::clamp(signals.share_all, TimeScaleShareMin, TimeScaleShareMax));
    const std::int64_t logit = (fixed_log2(p) - fixed_log2(1000 - p)) * Ln2 / 65536;
    z1 += fit.per_logit * logit / 65536;
  }
  const std::int64_t z0 = DepthFit.intercept + DepthFit.per_ply * d;
  // sigma(z1) / sigma(z0) = (1 + e^-z0) / (1 + e^-z1), with e^-z = 2^(-z log2 e).
  const std::uint64_t balance = with_share ? TimeScaleBalanceShare : TimeScaleBalanceStability;
  const std::uint64_t num = (One + fixed_exp2_neg(z0 * Log2E / 65536)) * balance;
  const std::uint64_t den = One + fixed_exp2_neg(z1 * Log2E / 65536);
  return std::max(TimeScaleFloor, static_cast<int>((num + den / 2) / den));
}

int root_gap_permille(int depth, int score, int runner_up, bool reached) {
  constexpr int Unchanged = 1000;
  // The same depth gate as the stability scaling: shallower iterations take
  // a negligible part of any soft limit. A mate or tablebase score's gap is
  // a distance in plies, not a closeness of evaluation.
  if (depth < TimeScaleMinDepth || runner_up <= -ScoreInfinite || is_tb_or_mate(score)) return Unchanged;
  if (score - runner_up >= RootGapBand) return Unchanged;
  return reached ? Unchanged + RootGapExtra : Unchanged;
}

std::int64_t scaled_soft_ms(std::int64_t soft_ms, std::int64_t hard_ms, int permille) {
  if (soft_ms < 0 || hard_ms < 0 || soft_ms >= hard_ms) return soft_ms;
  const std::int64_t p = std::max(permille, 0);
  if (p == 0) return 1;
  // soft_ms * p / 1000 without overflow: past INT64_MAX it is past any hard limit.
  const std::int64_t whole = soft_ms / 1000, rest = soft_ms % 1000;
  if (whole > std::numeric_limits<std::int64_t>::max() / p - 1) return hard_ms;
  return std::clamp<std::int64_t>(whole * p + rest * p / 1000, 1, hard_ms);
}

}  // namespace forkeng
