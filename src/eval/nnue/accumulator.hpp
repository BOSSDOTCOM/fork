// SPDX-License-Identifier: GPL-3.0-or-later

// accumulator: B0's first layer, kept incrementally, and its output layer
// (DESIGN.md §5.3, deliverable 5).
//
// Purpose: the per-perspective sums of the active features' weights (the
// accumulator), updated from the parent's by the few features a move
// changes; the output layer (clipped ReLU, then the dot product with the
// output weights); and FeatureStack, one accumulator per search ply,
// computed only when a node's evaluation is needed.
// Invariants:
// - Feature index, as bullet's 768-input set (KB bullet-internals.md §4.2):
//   for perspective P, 384 * [piece colour != P] + 64 * piece type (pawn 0 ...
//   king 5) + the square seen from P (a1 = 0 ... h8 = 63, ranks flipped for
//   Black).
// - Every SIMD path has a scalar reference here, always compiled, with the
//   same results bit for bit (tests/test_nnue.cpp); the net file's bounds
//   (net_file.hpp) guarantee no overflow on any path.
// - The evaluation is from the side to move's view, in centipawns: the
//   output sum times S, divided by QA * QB (truncated toward zero), clamped
//   inside +-EvalLimit. A position and its colour mirror evaluate the same.
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
};

constexpr int feature_index(Color perspective, Piece piece, Square sq) {
  const Square seen = perspective == White ? sq : sq ^ 56;
  return 384 * (side_of(piece) != perspective) + 64 * kind_of(piece) + seen;
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

void accumulate_board(const NetFile& net, const Position& pos, Accumulator& out);
void advance_accumulator(const NetFile& net, const Accumulator& from, const FeatureDelta& d, Accumulator& to);
// The evaluation of an accumulator for side to move `stm`.
int output_layer(const NetFile& net, const Accumulator& acc, Color stm);

// Scalar references of the two kernels, for the equivalence tests.
void advance_accumulator_scalar(const NetFile& net, const Accumulator& from, const FeatureDelta& d, Accumulator& to);
int output_layer_scalar(const NetFile& net, const Accumulator& acc, Color stm);

// One accumulator per ply of a search: ply 0 is the root, computed from
// scratch; the others are computed from their parent when first needed.
class FeatureStack {
 public:
  void reset(const NetFile& net, const Position& root);
  // Before `m` is made at `ply` (so the child is ply + 1).
  void push_move(int ply, const Position& before, Move m) {
    Entry& e = entries_[ply + 1];
    e.delta = delta_for_move(before, m);
    e.computed = false;
  }
  // Before a null move at `ply`: the child's accumulator is the parent's.
  void push_null(int ply) {
    Entry& e = entries_[ply + 1];
    e.delta = FeatureDelta{};
    e.computed = false;
  }
  // The evaluation at `ply` of `pos` (the position the stack has reached).
  int evaluate(const NetFile& net, int ply, const Position& pos);

 private:
  struct Entry {
    Accumulator acc;
    FeatureDelta delta;
    bool computed = false;
  };
  Entry entries_[MaxPly + 1];
};

}  // namespace forkeng
