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
//   per architecture: 2, 3, 6, 7, 8, 9: output weights i16 [8][2H], biases i32 [8];
//   4: L1 i8 [8][16][H], biases i32 [8][16], L2 i16 [8][32][16], biases i32
//   [8][32], L3 i16 [8][32], biases i32 [8], the output output_multiplier i64;
//   5: side weights i16 [inputs][3], side biases i16 [3], two experts' i16
//   [2H] weights and i32 biases.
// - QA and QB are bullet's quantization convention (owner, 2026-10-28;
//   ORIGINALITY.md).
// - The reader accepts a file only if every field matches what this build
//   computes with, the checksum matches, and the weights keep every sum in
//   range: no first-layer unit's (or side lane's) |bias| + 32 * its largest
//   |piece weight| (over every region's piece rows; + 30 * its largest
//   |exposure weight|, XGR; + 64 * its largest |link weight|, S512+PP and
//   H512+PP: the most links at their rank limit) exceeds the
//   int16 range, and the output layers' worst cases stay within int32 (the
//   squared outputs: QA^2 times each bucket's sum of |w|, which bounds the
//   AVX2 path's 32-bit lane sums; the scalar path sums in int64). S512+X's
//   exposure rows and S512cl's
//   contact and link rows need no bound: they are summed in 32 bits
//   (accumulator.cpp) and held to int16 only when added to the piece sums. So the
//   integer arithmetic of every path (scalar and SIMD) never overflows, and
//   all paths give identical results.
// - Move-delta builds (FORK_MOVE_DELTA, ideas.md 182) also hold the step rows,
//   made from the feature weights by fill_step_rows: read_net_file calls it
//   on every file it accepts, and code that sets the weights itself (the
//   tests' random networks) calls it after.
#pragma once

#include <bit>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

#include "core/types.hpp"
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

#if FORK_MOVE_DELTA
// Move-delta rows (ideas.md 182): one row per step a non-pawn piece can make
// on an empty board, in a perspective's frame (squares as feature_index sees
// them). Both flips of a frame (ranks for Black, files when mirrored) keep a
// step a step of the same piece, so a move's step row in any frame is the
// row of its origin and destination as that frame sees them. Rows run by
// colour block (own, enemy), then by kind (knight .. king), origin and
// destination (ascending).
struct StepLayout {
  Bitboard reach[5][64] = {};       // [kind - Knight][origin]: the destinations
  std::uint16_t first[5][64] = {};  // the origin's first row within a colour block
  int per_colour = 0;               // rows per colour block
};

constexpr StepLayout make_step_layout() {
  StepLayout s;
  for (int from = 0; from < 64; ++from)
    for (int to = 0; to < 64; ++to) {
      const int df = (to & 7) - (from & 7), dr = (to >> 3) - (from >> 3);
      const int af = df < 0 ? -df : df, ar = dr < 0 ? -dr : dr;
      const bool diagonal = af == ar && af > 0, straight = (af == 0) != (ar == 0);
      const Bitboard b = Bitboard{1} << to;
      if ((af == 1 && ar == 2) || (af == 2 && ar == 1)) s.reach[0][from] |= b;  // knight
      if (diagonal) s.reach[1][from] |= b;                                      // bishop
      if (straight) s.reach[2][from] |= b;                                      // rook
      if (diagonal || straight) s.reach[3][from] |= b;                          // queen
      if (af <= 1 && ar <= 1 && af + ar > 0) s.reach[4][from] |= b;             // king
    }
  int next = 0;
  for (int k = 0; k < 5; ++k)
    for (int from = 0; from < 64; ++from) {
      s.first[k][from] = static_cast<std::uint16_t>(next);
      next += std::popcount(s.reach[k][from]);
    }
  s.per_colour = next;
  return s;
}

inline constexpr StepLayout StepGeometry = make_step_layout();
inline constexpr int StepRows = 2 * StepGeometry.per_colour;

// The step row of a `kind` piece (Knight .. King; `enemy` when it is not the
// perspective's colour) from `from` to `to`, both as the frame sees them; the
// step must be one of reach's.
constexpr int step_row(bool enemy, int kind, int from, int to) {
  const int k = kind - Knight;
  return (enemy ? StepGeometry.per_colour : 0) + StepGeometry.first[k][from] +
         std::popcount(StepGeometry.reach[k][from] & ((Bitboard{1} << to) - 1));
}
#endif

struct NetFile {
  alignas(64) std::int16_t ft_weights[NetInputs * NetHidden];
  alignas(64) std::int16_t ft_bias[NetHidden];
#if FORK_MOVE_DELTA
  // Each step row: the piece's feature row on the destination minus its row
  // on the origin (fill_step_rows, from ft_weights). Every piece weight is
  // within +-1,023 (the reader's bound above: 32 x 1,024 > 32,767), so each
  // difference fits int16; and int16 sums wrap, so applying the difference equals
  // subtracting one row and adding the other bit for bit in any case.
  alignas(64) std::int16_t step_rows[StepRows * NetHidden];
#endif
#if FORK_NET_ARCH == 1
  alignas(64) std::int16_t out_weights[2 * NetHidden];
  std::int32_t out_bias = 0;
#elif FORK_NET_ARCH == 2 || FORK_NET_ARCH == 3 || FORK_NET_ARCH == 6 || FORK_NET_ARCH == 7 || \
    FORK_NET_ARCH == 8 || FORK_NET_ARCH == 9
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

#if FORK_MOVE_DELTA
// Sets net.step_rows from net.ft_weights (the piece rows).
void fill_step_rows(NetFile& net);
#endif

}  // namespace forkeng
