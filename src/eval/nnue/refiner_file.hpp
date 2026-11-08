// SPDX-License-Identifier: GPL-3.0-or-later

// refiner_file: the Boundary Refiner's file and the weights it holds
// (ideas.md 59, step 3; docs/research/boundary-refiner/step3-plan.md §2.2-2.5,
// §2.8).
//
// Purpose: a small network read beside the base network, on the base's own
// accumulator, and its validating reader. The refiner's shape is fixed at
// build time like the base's: CMake reads the architecture and the entry
// layer's width from the embedded file's header (FORK_REFINER_ARCH,
// FORK_REFINER_L1; 1 and 16 when no refiner is embedded, so every build
// compiles and tests the inference).
// Invariants:
// - Little-endian. A 64-byte header: "FORKRFN" and a zero byte, the format
//   version (u32, 1), the refiner architecture (u32: 1 the exposure rows, 2
//   the exposure rows and the danger summary), the entry layer's width (u32),
//   the middle layer's width (u32), the head count (u32), the output scale S
//   (i32), the cap C in cp (i32), 4 zero bytes, the payload checksum (u64,
//   net_checksum, at a net file's offset 40), the base network's payload
//   checksum (u64: the refiner reads that network's accumulator), 8 zero
//   bytes.
// - Payload, in order: entry weights i8 [width][input bytes] (output-major),
//   entry biases i32 [width], row weights i16 [rows][width], middle weights i8
//   [32][width], middle biases i32 [32], head weights i16 [2][32], head biases
//   i32 [2]. Inputs: the clipped accumulator as bytes (1.0 = QA = 255) and the
//   active rows (each an input fixed at 1.0); weights at QB = 64 per 1.0;
//   sums in units of QA x QB (bullet's convention, ORIGINALITY.md); rows are
//   multiplied by QA when read, so they add into the same sums.
// - The reader accepts a file only if every field matches what this build
//   computes with, the checksum matches, every dense (i8) weight lies in
//   [-QB, QB] (two products of a byte and such a weight sum exactly in int16,
//   so the 8-bit multiply-add path equals the scalar one), and no layer's
//   worst-case sum (its bias, its dense part at the inputs' maximum, the
//   largest RefinerMaxActive row values) leaves int32. The cap lies in
//   [0, EvalLimit]. The scale S lies in [1, 100000], the range the net reader
//   accepts for a base network's S (net_file.cpp), so a refiner can carry any
//   scale its base can.
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

#include "eval/nnue/net_shape.hpp"

#ifndef FORK_REFINER_ARCH
#define FORK_REFINER_ARCH 1
#endif
#ifndef FORK_REFINER_L1
#define FORK_REFINER_L1 16
#endif

namespace forkeng {

inline constexpr int RefinerArchitecture = FORK_REFINER_ARCH;
static_assert(RefinerArchitecture == 1 || RefinerArchitecture == 2, "unknown refiner architecture");
inline constexpr std::uint32_t RefinerFormatVersion = 1;
inline constexpr int RefinerL1Width = FORK_REFINER_L1;
static_assert(RefinerL1Width == 8 || RefinerL1Width == 16, "the refiner's entry layer is 8 or 16 wide");
inline constexpr int RefinerL2Width = 32;
inline constexpr int RefinerHeads = 2;  // the correction and the confidence
// Both perspectives' clipped accumulator values, side to move first.
inline constexpr int RefinerInputBytes = 2 * NetHidden;
// The rows (step3-plan.md §2.2): the exposed pieces from the side to move's
// view (own/enemy x pawn..queen x square: NetExposureRows); in architecture 2
// the danger summary (per side, the side to move first: king-zone pressure
// 0-4+, weak king-zone squares 0-2+, safe checks 0-2+, pinned pieces 0-2+,
// exposed pieces 0-3+, one-hot: 18 rows); then the context, the base's phase
// bucket (NetBuckets rows) and the base evaluation in RefinerEvalBins bins of
// RefinerEvalBinCp over [-RefinerEvalBins / 2 * RefinerEvalBinCp, ... - 1].
inline constexpr int RefinerDangerRows = 36;
inline constexpr int RefinerEvalBins = 16;
inline constexpr int RefinerEvalBinCp = 125;
inline constexpr int RefinerRows =
    NetExposureRows + (RefinerArchitecture == 2 ? RefinerDangerRows : 0) + NetBuckets + RefinerEvalBins;
// At most 30 exposed pieces (all but the kings), 10 danger rows, 2 context rows.
inline constexpr int RefinerMaxActive = 30 + (RefinerArchitecture == 2 ? 10 : 0) + 2;

struct RefinerFile {
  alignas(64) std::int8_t entry_weights[RefinerL1Width][RefinerInputBytes];
  alignas(64) std::int32_t entry_bias[RefinerL1Width];
  alignas(64) std::int32_t row_weights[RefinerRows][RefinerL1Width];  // the file's i16 times QA
  alignas(64) std::int8_t middle_weights[RefinerL2Width][RefinerL1Width];
  alignas(64) std::int32_t middle_bias[RefinerL2Width];
  alignas(64) std::int16_t head_weights[RefinerHeads][RefinerL2Width];
  std::int32_t head_bias[RefinerHeads] = {};
  std::int32_t scale = 0;  // S: centipawns per unit of the correction head
  std::int32_t cap = 0;    // C: the correction is held to [-C, C] cp
  std::uint64_t base_checksum = 0;
};

// Reads a whole refiner file into `out`. Returns false, with the reason in
// `error`, unless every check above passes.
bool read_refiner_file(std::span<const std::uint8_t> bytes, RefinerFile& out, std::string& error);

// The file for `r` (tests; trained refiners will come from the converter).
// Row weights must be multiples of QA within the i16 range times QA.
std::vector<std::uint8_t> write_refiner_file(const RefinerFile& r);

#ifdef FORK_REFINER
// The refiner compiled into this build (CMake FORK_REFINER_NET), read and
// validated once, on first use; the engine stops if it is invalid or was
// trained on another base network than the embedded one.
const RefinerFile& embedded_refiner();
#endif

}  // namespace forkeng
