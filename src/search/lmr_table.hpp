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

#ifdef FORK_TUNE
// Tuning builds: rebuilt by set_param (src/tune/params.cpp) when a value changes.
inline LmrTable LmrPlies = make_lmr_table(LmrDivisorTenths);
inline void rebuild_lmr_table() { LmrPlies = make_lmr_table(LmrDivisorTenths); }
#else
inline constexpr LmrTable LmrPlies = make_lmr_table(LmrDivisorTenths);
#endif

// Reduction in plies for the move numbered `move` (1 = first) at `depth`.
FORK_TUNABLE_CONSTEXPR int reduction_for(int depth, int move) {
  const int d = depth < 1 ? 1 : depth >= LmrMaxDepth ? LmrMaxDepth - 1 : depth;
  const int m = move < 1 ? 1 : move >= LmrMaxMove ? LmrMaxMove - 1 : move;
  return LmrPlies.plies[d][m];
}

// The heuristic-discovery loop's first evolvable region (ideas.md idea 23,
// deliverable 8c; tools/evolve/): a correction in plies added to the table's
// reduction, scaled by LmrCorrectionStrength / 64 (the parameter table). Only
// the body between the markers may change, and tools/evolve/regions.py
// rejects anything else. The committed body returns 0, which keeps the search
// exactly as the table alone makes it (bench unchanged).
struct LmrContext {
  int depth;        // remaining depth at the node
  int move_number;  // the move's number in the order, 1 = first
  int base;         // the table's reduction, reduction_for(depth, move_number)
  int history;      // the move's butterfly history score, [-HistoryMax, HistoryMax]
  bool on_pv;       // a PV node
};

constexpr int lmr_correction(const LmrContext& c) {
  // FORK-EVOLVE-BEGIN lmr
  static_cast<void>(c);
  return 0;
  // FORK-EVOLVE-END lmr
}

}  // namespace forkeng
