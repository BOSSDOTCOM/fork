// SPDX-License-Identifier: GPL-3.0-or-later

// lmr_table: the late move reduction table (DESIGN.md §5.2, deliverable 6;
// KB search-techniques.md T15).
//
// Purpose: how many plies a late quiet move is reduced, from the remaining
// depth and the move's number in the order, shaped as the product of two
// logarithms (the shape CPW describes).
// Invariants:
// - Integer arithmetic only (DESIGN.md §5.2, determinism rule): logarithms
//   are fixed-point base-2 values computed by repeated squaring, so the table
//   is identical on every compiler, libm and architecture; its checksum is
//   pinned by tests/test_pruning.cpp.
// - reduction_for(d, m) is round(log2(d) * log2(m) / 4.5) for d, m >= 1
//   (Fork's own divisor, LmrDivisorTenths = 45 in the parameter table), or
//   one ply less where the integer logarithms fall
//   below the true value (18 of the 63 x 63 entries; review); non-decreasing
//   in both arguments, 0 at d or m = 1.
#pragma once

#include <cstdint>

#include "tune/params.hpp"

namespace forkeng {

constexpr int LmrMaxDepth = 64;
constexpr int LmrMaxMove = 64;

// 256 * log2(x) for 1 <= x < 2^16 in integer arithmetic: the floor, or one
// unit below it (each squaring truncates).
constexpr int fixed_log2(std::uint32_t x) {
  int whole = 0;
  while ((x >> whole) > 1) ++whole;
  // The fraction: square the mantissa (16-bit fixed point) eight times.
  std::uint64_t mantissa = (static_cast<std::uint64_t>(x) << 16) >> whole;  // in [1, 2) as Q16
  int fraction = 0;
  for (int bit = 7; bit >= 0; --bit) {
    mantissa = (mantissa * mantissa) >> 16;
    if (mantissa >= (std::uint64_t{2} << 16)) {
      mantissa >>= 1;
      fraction |= 1 << bit;
    }
  }
  return whole * 256 + fraction;
}

// The table: log2(d) * log2(m) / (divisor_tenths / 10), rounded. With the
// fixed-point logs L = 256 log2(d) * 256 log2(m), that is
// (10 L + 32768 t) / (65536 t) for t tenths; for t = 45 exactly the earlier
// (L + 147456) / 294912 (both terms times ten), so bench is unchanged.
struct LmrTable {
  std::uint8_t plies[LmrMaxDepth][LmrMaxMove];
};

constexpr LmrTable make_lmr_table(int divisor_tenths) {
  LmrTable t{};
  for (int d = 1; d < LmrMaxDepth; ++d)
    for (int m = 1; m < LmrMaxMove; ++m)
      t.plies[d][m] = static_cast<std::uint8_t>(
          (10 * fixed_log2(static_cast<std::uint32_t>(d)) * fixed_log2(static_cast<std::uint32_t>(m)) +
           32768 * divisor_tenths) /
          (65536 * divisor_tenths));
  return t;
}

// Round-once LMR (think tank R20; switch use_centred_lmr_history): the same
// reduction in 64ths of a ply, so sub-ply terms can be added before one
// rounding to whole plies. Each entry is the whole-ply entry times 64 plus
// the fixed-point value's own fraction, round(64 x) - 64 * plies, kept
// within [-32, 31]: rounding once, (sixty_fourths + 64 k + 32) >> 6, gives
// back plies + k exactly for every whole k, so with no sub-ply term the
// reduction is the whole-ply table's (tests/test_pruning.cpp, every entry).
// The 18 entries that sit one ply low (above) keep 31, their nearest fraction
// within that bound.
constexpr int LmrFineUnit = 64;
struct LmrSixtyFourths {
  std::int16_t fine[LmrMaxDepth][LmrMaxMove];
};

constexpr LmrSixtyFourths make_lmr_sixty_fourths(int divisor_tenths, const LmrTable& whole) {
  LmrSixtyFourths t{};
  for (int d = 1; d < LmrMaxDepth; ++d)
    for (int m = 1; m < LmrMaxMove; ++m) {
      const std::int64_t product = std::int64_t{10} * fixed_log2(static_cast<std::uint32_t>(d)) *
                                   fixed_log2(static_cast<std::uint32_t>(m));
      const std::int64_t rounded = (product * LmrFineUnit + std::int64_t{32768} * divisor_tenths) /
                                   (std::int64_t{65536} * divisor_tenths);
      const std::int64_t centre = std::int64_t{whole.plies[d][m]} * LmrFineUnit;
      const std::int64_t fraction = rounded - centre < -32  ? -32
                                    : rounded - centre > 31 ? 31
                                                            : rounded - centre;
      t.fine[d][m] = static_cast<std::int16_t>(centre + fraction);
    }
  return t;
}

#ifdef FORK_TUNE
// Tuning builds: rebuilt by set_param (src/tune/params.cpp) when a value changes.
inline LmrTable LmrPlies = make_lmr_table(LmrDivisorTenths);
inline LmrSixtyFourths LmrFine = make_lmr_sixty_fourths(LmrDivisorTenths, LmrPlies);
inline void rebuild_lmr_table() {
  LmrPlies = make_lmr_table(LmrDivisorTenths);
  LmrFine = make_lmr_sixty_fourths(LmrDivisorTenths, LmrPlies);
}
#else
inline constexpr LmrTable LmrPlies = make_lmr_table(LmrDivisorTenths);
inline constexpr LmrSixtyFourths LmrFine = make_lmr_sixty_fourths(LmrDivisorTenths, LmrPlies);
#endif

// Reduction in plies for the move numbered `move` (1 = first) at `depth`.
FORK_TUNABLE_CONSTEXPR int reduction_for(int depth, int move) {
  const int d = depth < 1 ? 1 : depth >= LmrMaxDepth ? LmrMaxDepth - 1 : depth;
  const int m = move < 1 ? 1 : move >= LmrMaxMove ? LmrMaxMove - 1 : move;
  return LmrPlies.plies[d][m];
}

// The same reduction in 64ths of a ply (R20), and the one rounding back to
// whole plies (to nearest, halves up; floor division, so negative sums round
// the same way).
FORK_TUNABLE_CONSTEXPR int reduction_sixty_fourths(int depth, int move) {
  const int d = depth < 1 ? 1 : depth >= LmrMaxDepth ? LmrMaxDepth - 1 : depth;
  const int m = move < 1 ? 1 : move >= LmrMaxMove ? LmrMaxMove - 1 : move;
  return LmrFine.fine[d][m];
}
constexpr int round_sixty_fourths(int fine) { return (fine + LmrFineUnit / 2) >> 6; }

// R20's history term in 64ths of a ply: a move whose centred history is
// `centred` (its tables' values less their running centres, weighted as the
// move ordering weights them) is reduced centred / per_ply plies less (more
// when negative), truncated toward zero.
constexpr int history_sixty_fourths(int centred, int per_ply) {
  return static_cast<int>(-std::int64_t{centred} * LmrFineUnit / per_ply);
}

// A running centre for one history table's values at LMR sites (R20): an
// exponential moving average over about 2^Shift sites, kept as the sum
// 2^Shift * centre, so centring the term on it keeps the term's mean near
// zero as the tables grow through a game. Starts at 0 (cleared with the
// histories).
struct HistoryCentre {
  static constexpr int Shift = 10;  // DESIGN.md, "Search constants": HistoryCentre::Shift
  int sum = 0;
  constexpr int centre() const { return sum >> Shift; }
  constexpr void add(int v) { sum += v - (sum >> Shift); }
};

// The heuristic-discovery loop's first evolvable region (ideas.md idea 23,
// deliverable 8c; tools/evolve/): a correction in plies added to the table's
// reduction, scaled by LmrCorrectionStrength / LmrCorrectionUnit (the
// parameter table; 64 of 64 applies the rule as written). Only
// the body between the markers may change, and tools/evolve/regions.py
// rejects anything else. The committed body returns 0, which keeps the search
// exactly as the table alone makes it (bench unchanged).
constexpr int LmrCorrectionUnit = 64;

struct LmrContext {
  int depth;        // remaining depth at the node
  int move_number;  // the move's number in the order, 1 = first
  int base;         // the table's reduction, reduction_for(depth, move_number)
  int history;      // the move's butterfly history score (the mover's), [-HistoryMax, HistoryMax]
  bool on_pv;       // a PV node
  // Added 2026-10-27 (the owner: new information for the loop to use). Each
  // is built from inline, side-effect-free code, so a rule that does not
  // read it costs nothing.
  int piece;         // the moved piece: 0 pawn, 1 knight, 2 bishop, 3 rook, 4 queen, 5 king
  bool threatened;   // the opponent attacked the moved piece's square before the move
  bool attacks;      // from its new square it attacks an enemy piece other than a pawn or the king
  int quiet_moves;   // quiet moves generated at this node
  int phase;         // game phase, 0 (no pieces) to 24 (all of them), from non-pawn material
  int entry_bound;   // this node's TT entry: 0 none, 1 upper bound, 2 lower bound, 3 exact
  int entry_depth;   // its depth in plies, -1 without an entry
  int score_trend;   // the root score's change between the last two finished iterations, cp, in [-1000, 1000]
  int branch_share;  // per mille of the last finished iteration's nodes spent under this line's root move
};

constexpr int lmr_correction(const LmrContext& c) {
  // FORK-EVOLVE-BEGIN lmr
  static_cast<void>(c);
  return 0;
  // FORK-EVOLVE-END lmr
}

}  // namespace forkeng
