// SPDX-License-Identifier: GPL-3.0-or-later

// net_file: Fork's network file and the weights it holds (DESIGN.md §5.3,
// deliverable 5), for the baseline network B0: 768 inputs per perspective,
// one hidden layer of NetHidden, clipped ReLU, one output.
//
// Purpose: the one format Fork's inference reads, independent of the
// trainer's layout (tools/nnue/convert.py writes it from bullet's quantized
// file), and its validating reader.
// Invariants:
// - Little-endian. A 64-byte header: "FORKNET" and a zero byte, the format
//   version (u32), the architecture id (u32, 1 = B0), inputs and hidden size
//   (u32 each), QA, QB and the output scale S (i32 each), 4 zero bytes, the
//   payload checksum (u64), 16 zero bytes. Then the payload: the feature
//   weights (i16, feature-major: NetHidden values per input), the feature
//   biases (i16), the output weights (i16, the side to move's half first),
//   the output bias (i32).
// - QA and QB are bullet's quantization convention (owner, 2026-10-28;
//   ORIGINALITY.md): activations clipped to [0, QA], output weights scaled by
//   QB, the output bias by QA * QB.
// - The reader accepts a file only if every field matches what this build
//   computes with, the checksum matches, and the weights keep every sum in
//   range: no hidden unit's |bias| + 32 * its largest |feature weight|
//   exceeds the int16 range (at most 32 features are active), and QA times
//   the output weights' absolute sum plus |output bias| stays within int32.
//   So the integer arithmetic of every path (scalar and SIMD) never
//   overflows, and all paths give identical results.
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

namespace forkeng {

constexpr int NetInputs = 768;  // 2 colours x 6 piece types x 64 squares
constexpr int NetHidden = 256;
constexpr int NetQa = 255;
constexpr int NetQb = 64;
constexpr std::uint32_t NetFormatVersion = 1;
constexpr std::uint32_t NetArchitectureB0 = 1;
constexpr std::size_t NetHeaderBytes = 64;
constexpr std::size_t NetPayloadBytes =
    2 * (std::size_t{NetInputs} * NetHidden + NetHidden + 2 * NetHidden) + 4;

struct NetFile {
  alignas(64) std::int16_t ft_weights[NetInputs * NetHidden];
  alignas(64) std::int16_t ft_bias[NetHidden];
  alignas(64) std::int16_t out_weights[2 * NetHidden];
  std::int32_t out_bias = 0;
  std::int32_t scale = 0;  // S: centipawns per unit of the network's output
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
