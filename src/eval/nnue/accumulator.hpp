// SPDX-License-Identifier: GPL-3.0-or-later

// accumulator: the network's first layer, kept incrementally, and its
// output layers (DESIGN.md §5.3, deliverable 5; §5.4 for the bake-off
// architectures), for the architecture this build is compiled for.
//
// Purpose: the per-perspective sums of the active features' weights (the
// accumulator), updated from the parent's by the few features a move
// changes; the output (B0: clipped ReLU and one dot product; the bake-off
// entries as tools/nnue/models.py specifies them); and FeatureStack, one
// accumulator per search ply, computed only when a node's evaluation is
// needed.
// Invariants:
// - Feature index, as bullet's 768-input set (KB bullet-internals.md §4.2):
//   for perspective P, 384 * [piece colour != P] + 64 * piece type (pawn 0 ...
//   king 5) + the square seen from P (a1 = 0 ... h8 = 63, ranks flipped for
//   Black). Mirrored architectures also flip the files (XOR 7) when P's own
//   king stands on files a-d, and add 768 times the region of P's mirrored
//   king square (a Frame). XGR's exposure inputs follow the piece rows.
// - A perspective's frame changes only when its own king moves across the
//   d/e line or into another region; then that perspective is recomputed
//   from the board, every other update is incremental.
// - Every SIMD path has a scalar reference here, always compiled, with the
//   same results bit for bit (tests/test_nnue.cpp); the net file's bounds
//   (net_file.hpp) guarantee no overflow on any path.
// - The evaluation is from the side to move's view, in centipawns, clamped
//   inside +-EvalLimit. A position and its colour mirror evaluate the same;
//   with mirroring, so do a position and its left-right mirror.
// - An incrementally updated accumulator equals one computed from scratch.
// - No allocation, no floating point.
#pragma once

#include <cstdint>

#include "core/position.hpp"
#include "eval/nnue/net_file.hpp"
#include "search/score_bounds.hpp"

namespace forkeng {

struct alignas(64) Accumulator {
  std::int16_t values[2][NetHidden];  // indexed by perspective colour
#if FORK_NET_ARCH == 5
  std::int16_t side[2][4];  // XGR's gate and linear lanes (lane 3 unused)
#endif
};

// How one perspective sees the board: the file flip (7 when its own king
// stands on files a-d of its view, mirrored architectures only) and the
// first input of its king's region.
struct Frame {
  int flip = 0;
  int offset = 0;
  friend bool operator==(Frame, Frame) = default;
};

Frame frame_of(const NetFile& net, Color perspective, Square own_king);

constexpr int feature_index(Color perspective, Piece piece, Square sq, Frame f = {}) {
  const Square seen = perspective == White ? sq : sq ^ 56;
  return f.offset + 384 * (side_of(piece) != perspective) + 64 * kind_of(piece) + (seen ^ f.flip);
}

// The pieces a move takes off and puts on the board (at most two each:
// castling moves king and rook, a capture-promotion removes two).
struct FeatureDelta {
  int removed_count = 0, added_count = 0;
  Piece removed_piece[2], added_piece[2];
  Square removed_square[2], added_square[2];
};

// The delta of `m`, legal in `before`.
FeatureDelta delta_for_move(const Position& before, Move m);

// Both perspectives from scratch, each in its own frame.
void accumulate_board(const NetFile& net, const Position& pos, Accumulator& out);
// One perspective from its parent's, by a delta (the frame unchanged).
void advance_perspective(const NetFile& net, const Accumulator& from, const FeatureDelta& d,
                         Color perspective, Frame frame, Accumulator& to);
// The evaluation of `pos` from its accumulator, side to move's view.
int evaluate_position(const NetFile& net, const Accumulator& acc, const Position& pos);
// The same with the scalar kernels only (the equivalence tests).
int evaluate_position_scalar(const NetFile& net, const Accumulator& acc, const Position& pos);

#if FORK_NET_ARCH == 1
// B0's kernels, both perspectives at once, and their scalar references.
void advance_accumulator(const NetFile& net, const Accumulator& from, const FeatureDelta& d, Accumulator& to);
int output_layer(const NetFile& net, const Accumulator& acc, Color stm);
void advance_accumulator_scalar(const NetFile& net, const Accumulator& from, const FeatureDelta& d,
                                Accumulator& to);
int output_layer_scalar(const NetFile& net, const Accumulator& acc, Color stm);
#endif

#if FORK_NET_ARCH == 5
// XGR's exposed pieces: non-king pieces attacked by an enemy piece of a
// lower class (pawn < knight = bishop < rook < queen < king), or attacked
// and not defended (pseudo-attacks on the occupancy).
Bitboard exposed_pieces(const Position& pos);
#endif

// One accumulator per ply of a search: ply 0 is the root, computed from
// scratch; the others are computed from their parent when first needed,
// except a perspective whose frame the move changes, which is recomputed
// from the board at once.
class FeatureStack {
 public:
  void reset(const NetFile& net, const Position& root);
  // Before `m` is made at `ply` (so the child is ply + 1).
  void push_move(const NetFile& net, int ply, const Position& before, Move m);
  // Before a null move at `ply`: the child's accumulator is the parent's.
  void push_null(int ply) {
    Entry& e = entries_[ply + 1];
    e.delta = FeatureDelta{};
    e.frame[White] = entries_[ply].frame[White];
    e.frame[Black] = entries_[ply].frame[Black];
    e.computed[White] = e.computed[Black] = false;
  }
  // The evaluation at `ply` of `pos` (the position the stack has reached).
  int evaluate(const NetFile& net, int ply, const Position& pos);

 private:
  struct Entry {
    Accumulator acc;
    FeatureDelta delta;
    Frame frame[2];
    bool computed[2] = {false, false};
  };
  Entry entries_[MaxPly + 1];
};

}  // namespace forkeng
