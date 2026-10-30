// SPDX-License-Identifier: GPL-3.0-or-later

// net_file: Fork's network file and the weights it holds (DESIGN.md §5.3,
// deliverable 5; §5.4 for the bake-off architectures), for the architecture
// this build is compiled for (net_shape.hpp).
//
// Purpose: the one format Fork's inference reads, independent of the
// trainer's layout (tools/nnue/convert.py writes it from bullet's quantized
// file), and its validating reader.
// Invariants:
// - Little-endian. A 64-byte header: "FORKNET" and a zero byte, the format
//   version (u32: 1 for B0, 2 for the others), the architecture id (u32),
//   the inputs (u32: the saved first-layer rows) and hidden size (u32), QA,
//   QB and the output scale S (i32 each), 4 bytes (zero in version 1, the
//   bucket count in version 2), the payload checksum (u64), 16 zero bytes.
// - Version 1 payload (B0): the feature weights (i16, feature-major:
//   NetHidden values per input), the feature biases (i16), the output
//   weights (i16, the side to move's half first), the output bias (i32).
// - Version 2 payload (tools/nnue/models.py): a 128-byte map block (32
//   region bytes for the mirrored own-king cell rank * 4 + file - 4, 25
//   phase-table bytes, zeros), the feature weights and biases as above, then
//   per architecture: 2, 3: output weights i16 [8][2H], biases i32 [8];
//   4: L1 i8 [8][16][H], biases i32 [8][16], L2 i16 [8][32][16], biases i32
//   [8][32], L3 i16 [8][32], biases i32 [8], the output output_multiplier i64;
//   5: side weights i16 [inputs][3], side biases i16 [3], two experts' i16
//   [2H] weights and i32 biases.
// - QA and QB are bullet's quantization convention (owner, 2026-10-28;
//   ORIGINALITY.md).
// - The reader accepts a file only if every field matches what this build
//   computes with, the checksum matches, and the weights keep every sum in
//   range: no first-layer unit's (or side lane's) |bias| + 32 * its largest
//   |piece weight| (+ 30 * its largest |exposure weight|) exceeds the int16
//   range, and the output layers' worst cases stay within int32 (int64 for
//   the squared outputs' sums). So the integer arithmetic of every path
//   (scalar and SIMD) never overflows, and all paths give identical results.
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

#include "eval/nnue/net_shape.hpp"

namespace forkeng {

inline constexpr int NetInputs = NetMaxInputs;  // the most first-layer rows this build reads
inline constexpr std::uint32_t NetFormatVersion = NetArchitecture == 1 ? 1 : 2;
inline constexpr std::size_t NetHeaderBytes = 64;
inline constexpr std::size_t NetMapBytes = 128;
#if FORK_NET_ARCH == 1
inline constexpr std::size_t NetPayloadBytes =
    2 * (std::size_t{NetInputs} * NetHidden + NetHidden + 2 * NetHidden) + 4;
#endif

struct NetFile {
  alignas(64) std::int16_t ft_weights[NetInputs * NetHidden];
  alignas(64) std::int16_t ft_bias[NetHidden];
#if FORK_NET_ARCH == 1
  alignas(64) std::int16_t out_weights[2 * NetHidden];
  std::int32_t out_bias = 0;
#elif FORK_NET_ARCH == 2 || FORK_NET_ARCH == 3
  alignas(64) std::int16_t out_weights[NetBuckets][2 * NetHidden];
  std::int32_t out_bias[NetBuckets] = {};
#elif FORK_NET_ARCH == 4
  alignas(64) std::int8_t af1_weights[NetBuckets][NetL1][NetHidden];
  std::int32_t af1_bias[NetBuckets][NetL1] = {};
  alignas(64) std::int16_t af2_weights[NetBuckets][NetL2][NetL1];
  std::int32_t af2_bias[NetBuckets][NetL2] = {};
  alignas(64) std::int16_t af3_weights[NetBuckets][NetL2];
  std::int32_t af3_bias[NetBuckets] = {};
  std::int64_t output_multiplier = 0;
#elif FORK_NET_ARCH == 5
  alignas(64) std::int16_t side_weights[NetInputs][4];  // lanes 0-2 used, 3 zero
  std::int16_t side_bias[4] = {};
  alignas(64) std::int16_t expert_weights[2][2 * NetHidden];
  std::int32_t expert_bias[2] = {};
#endif
  std::uint8_t regions[32] = {};  // region of the mirrored own-king cell
  std::uint8_t phase_table[25] = {};
  int region_count = 1;
  int inputs = NetPieceSquares;  // first-layer rows in this file
  std::int32_t scale = 0;        // S: centipawns per unit of the network's output
};

// Fork's checksum of a payload: its bytes in 8-byte little-endian words (the
// last zero-padded), each mixed in with splitmix's output function.
std::uint64_t net_checksum(std::span<const std::uint8_t> payload);

// Reads a whole net file into `out`. Returns false, with the reason in
// `error`, unless every check above passes.
bool read_net_file(std::span<const std::uint8_t> bytes, NetFile& out, std::string& error);

// The file for `net` (tests; the trainer's files come from convert.py).
std::vector<std::uint8_t> write_net_file(const NetFile& net);

}  // namespace forkeng
