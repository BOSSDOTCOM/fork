// SPDX-License-Identifier: GPL-3.0-or-later

// refiner: the Boundary Refiner's inference (ideas.md 59, step 3;
// docs/research/boundary-refiner/step3-plan.md §2.1-2.5).
//
// Purpose: a correction to the base network's evaluation, computed on demand
// where the search's gate fires (search/refiner_gate.hpp), from the base's
// own accumulator (no second accumulator) and a few sparse rows found from
// the board: the exposed pieces (XGR's rule) from the side to move's view, in
// architecture 2 the danger summary, and the context (the base's phase bucket
// and the base evaluation's bin). Layers: the clipped accumulator bytes and
// the rows -> RefinerL1Width -> RefinerL2Width -> 2 heads (the correction in
// cp and the confidence in thousandths of win probability), clipped ReLU,
// integer arithmetic only.
// Invariants:
// - The output depends on the position and the base evaluation only, never on
//   the window, the depth or the TT (the plan's §2.2: a stored refined value
//   means the same thing whatever window finds it).
// - Every SIMD path has its scalar reference here, always compiled, with the
//   same results bit for bit (tests/test_refiner.cpp); refiner_file.hpp's
//   bounds guarantee no overflow or saturation on any path. With AVX-512 VNNI
//   the entry layer uses dpbusd; other AVX-512 builds use the AVX2 paths.
// - A refiner whose weights are all zero outputs a zero correction and a zero
//   confidence for every input.
// - No allocation, no floating point.
#pragma once

#include <cstdint>

#include "core/position.hpp"
#include "eval/nnue/accumulator.hpp"
#include "eval/nnue/refiner_file.hpp"

namespace forkeng {

struct RefinerInputs {
  alignas(64) std::uint8_t bytes[RefinerInputBytes];  // pack_clipped's output
  int rows[RefinerMaxActive];                         // refiner_rows' output
  int row_count = 0;
};

struct RefinerOutput {
  int correction = 0;  // cp, within [-cap, cap]
  int confidence = 0;  // the predicted error, thousandths of win probability, [0, 1000]
};

// Both perspectives' accumulator values clipped to [0, QA] as bytes, the side
// to move's first (the base output's own clip).
void pack_clipped(const Accumulator& acc, Color stm, std::uint8_t* out);
void pack_clipped_scalar(const Accumulator& acc, Color stm, std::uint8_t* out);

// The active rows of `pos` (refiner_file.hpp's row layout); `base` is the
// base network (its frames and phase table) and `base_eval` its evaluation
// of `pos`. Returns how many were written (at most RefinerMaxActive).
int refiner_rows(const NetFile& base, const Position& pos, int base_eval, int* rows);

// The refiner's output for `in`.
RefinerOutput run_refiner(const RefinerFile& r, const RefinerInputs& in);
RefinerOutput run_refiner_scalar(const RefinerFile& r, const RefinerInputs& in);

// run_refiner's two parts, public for fork_micro's per-part timing and the
// equivalence tests: the entry layer's sums (units of QA x QB: bias, dense
// part, active rows; the build's vector path, and its scalar reference), then
// the entry layer's clipped ReLU, the middle layer, the heads and the
// output's scaling (the build's vector path, or with Scalar its scalar
// reference; explicitly instantiated for both).
// refiner_l1's vector path depends on the weights' bound (refiner_file.hpp),
// so both bounds are instantiated and tested in every build; run_refiner
// uses this build's.
template <int Bound = RefinerDenseBound>
void refiner_l1(const RefinerFile& r, const RefinerInputs& in, std::int32_t* sums);
void refiner_l1_scalar(const RefinerFile& r, const RefinerInputs& in, std::int32_t* sums);
template <bool Scalar = false>
RefinerOutput refiner_l2_heads(const RefinerFile& r, const std::int32_t* sums);

}  // namespace forkeng
