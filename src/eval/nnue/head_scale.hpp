// SPDX-License-Identifier: GPL-3.0-or-later

// head_scale: a fixed-point multiplier per (output bucket, queen state)
// applied after the phase-picked networks' output head (ideas.md 180, step
// 2: the inference form of the per-class calibration; an experiment, not
// adopted; docs/research/idea180-step2.md).
//
// Purpose: lets one network's eight phase heads be read on a different scale
// with queens on the board than without, from Fork's own calibration fit,
// without touching the net file (which has one head per phase bucket only).
// Invariants:
// - Q12: a multiplier m means m / 4096. The output becomes
//   clamp(y * S * m / (QA * QB * 4096)) for the head's sum y and the net's
//   scale S, all in int64; with m = 4096 that is exactly today's
//   clamp(y * S / (QA * QB)) (the same rational, truncated the same way).
// - The queen state is colour-symmetric (any queen of either colour), and so
//   is the bucket, so a position and its colour mirror still evaluate the
//   same.
// - Default builds use the unit table (every m = 4096): their evaluations,
//   bench and search are unchanged. FORK_EXPERIMENT=HEAD_SCALE selects the
//   fitted table (its bench differs by design).
// - **Candidate commit (branch exp/i180-head-scale only):** the fitted table
//   is switched on below for every build, for the fixed-node screen against
//   r8brft1; tests/bench-r8brft1.ref holds this build's bench.
// - No floating point: the table is integers fixed at build time.
#pragma once

#include <cstdint>

#ifndef FORK_EXP_HEAD_SCALE
#define FORK_EXP_HEAD_SCALE
#endif

namespace forkeng {

inline constexpr int HeadScaleOne = 4096;

// Indexed [output bucket][queens on the board: 0 none, 1 any].
#if defined(FORK_EXP_HEAD_SCALE)
// The fitted factors for r8brft1 (docs/research/idea180-step2.md: the
// pooled k over k(bucket, queen state), logistic scales of search score
// against result in Fork's own STC self-play games; a thin cell takes its
// bucket's factor; clipped to [0.70, 1.40]), times 4096, rounded.
inline constexpr std::int32_t HeadScaleTable[8][2] = {
    {2867, 2867},  // bucket 0 (phase 0-3): 0.609 clipped to 0.700; no queen is possible
    {3465, 3451},  // bucket 1 (4-5): 0.846; queens on thin, the bucket's 0.842
    {3876, 3693},  // bucket 2 (6-7): 0.946; queens on thin, the bucket's 0.902
    {4033, 3813},  // bucket 3 (8-11): 0.985, 0.931
    {4105, 4308},  // bucket 4 (12-15): 1.002, 1.052
    {4440, 4431},  // bucket 5 (16-19): queenless thin, the bucket's 1.084; 1.082
    {4645, 4645},  // bucket 6 (20-22): 1.134; queenless impossible, the bucket's
    {4819, 4819},  // bucket 7 (23-24): 1.176; queenless impossible, the bucket's
};
inline constexpr bool HeadScaleActive = true;
#else
inline constexpr std::int32_t HeadScaleTable[8][2] = {
    {4096, 4096}, {4096, 4096}, {4096, 4096}, {4096, 4096},
    {4096, 4096}, {4096, 4096}, {4096, 4096}, {4096, 4096},
};
inline constexpr bool HeadScaleActive = false;
#endif

// The head's centipawn value before the clamp: y * S * m / (QA * QB * 4096),
// truncated toward zero as the unscaled form is. The loader's bounds keep the
// squared sum within int32, so |y| is below 2^23 plus the int32 bias, under
// 2^32; S is below 10^5 < 2^17 (net_file.cpp) and m at most 1.40 x 4096 <
// 2^13 (the rails), so the product stays below 2^62, inside int64.
constexpr std::int64_t scaled_head_cp(std::int64_t y, std::int32_t scale, std::int32_t multiplier, int qa,
                                      int qb) {
  return y * scale * multiplier / (std::int64_t{qa} * qb * HeadScaleOne);
}

}  // namespace forkeng
