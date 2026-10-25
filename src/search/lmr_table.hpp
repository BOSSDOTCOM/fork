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
//   (Fork's own divisor), or one ply less where the integer logarithms fall
//   below the true value (18 of the 63 x 63 entries; review); non-decreasing
//   in both arguments, 0 at d or m = 1.
#pragma once

#include <cstdint>

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

// The table, built at compile time: log2(d) * log2(m) / 4.5, rounded
// (256 * 256 * 4.5 = 294912).
struct LmrTable {
  std::uint8_t plies[LmrMaxDepth][LmrMaxMove];
};

constexpr LmrTable make_lmr_table() {
  LmrTable t{};
  for (int d = 1; d < LmrMaxDepth; ++d)
    for (int m = 1; m < LmrMaxMove; ++m)
      t.plies[d][m] = static_cast<std::uint8_t>(
          (fixed_log2(static_cast<std::uint32_t>(d)) * fixed_log2(static_cast<std::uint32_t>(m)) + 147456) /
          294912);
  return t;
}

inline constexpr LmrTable LmrPlies = make_lmr_table();

// Reduction in plies for the move numbered `move` (1 = first) at `depth`.
constexpr int reduction_for(int depth, int move) {
  const int d = depth < 1 ? 1 : depth >= LmrMaxDepth ? LmrMaxDepth - 1 : depth;
  const int m = move < 1 ? 1 : move >= LmrMaxMove ? LmrMaxMove - 1 : move;
  return LmrPlies.plies[d][m];
}

}  // namespace forkeng
