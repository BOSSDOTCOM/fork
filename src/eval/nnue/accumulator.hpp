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
//   king square (a Frame). XGR's, S512+X's and S512+PPXL's exposure inputs
//   follow the piece rows (added at each evaluation, never kept in the
//   sums). S512+PP's link inputs follow the piece rows in the same sums
//   (H512+PP's follow every region's piece rows, S512+PPXL's its exposure
//   rows): a move changes them only when a pawn moves, is captured or
//   promotes.
// - A perspective's frame changes only when its own king moves across the
//   d/e line or into another region; then that perspective is recomputed
//   from the board (H512+PP: lazily, from that frame's snapshot, by the
//   difference of the boards; FeatureStack), every other update is
//   incremental.
// - Every SIMD path has a scalar reference here, always compiled, with the
//   same results bit for bit (tests/test_nnue.cpp); the net file's bounds
//   (net_file.hpp) guarantee no overflow on any path.
// - The evaluation is from the side to move's view, in centipawns, clamped
//   inside +-EvalLimit. A position and its colour mirror evaluate the same;
//   with mirroring, so do a position and its left-right mirror.
// - An incrementally updated accumulator equals one computed from scratch.
// - No allocation, no floating point.
// - Stats builds (FORK_SEARCH_STATS) also count the stack's work in a
//   FeatureStackTally (DESIGN.md §5.7, X1); the counts only read the state,
//   and normal builds have none.
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
#if FORK_NET_LINKS
  // S512+PP's (and H512+PP's) links change only when a pawn moves, is captured or promotes:
  // then pawn_change is set and these hold each side's pawns before and
  // after the move (left unset otherwise).
  bool pawn_change = false;
  Bitboard pawns_before[2] = {0, 0}, pawns_after[2] = {0, 0};
#endif
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

// The added-rows kernel (S512cl's contact and link rows; compiled in every
// build, for its equivalence test): out = base plus the `count` rows (each NetHidden
// values), summed in 32 bits and held to the int16 range. The scalar
// reference and the build's vector path (AVX-512 or AVX2 where compiled; the
// scalar one otherwise) give the same values bit for bit.
void sum_rows_saturated(const std::int16_t* base, const std::int16_t* const* rows, int count,
                        std::int16_t* out);
void sum_rows_saturated_scalar(const std::int16_t* base, const std::int16_t* const* rows, int count,
                               std::int16_t* out);

#if FORK_NET_ARCH == 5 || FORK_NET_ARCH == 6
// XGR's exposed pieces (S512+X's too): non-king pieces attacked by an enemy piece of a
// lower class (pawn < knight = bishop < rook < queen < king), or attacked
// and not defended (pseudo-attacks on the occupancy).
Bitboard exposed_pieces(const Position& pos);
#endif

#if FORK_NET_ARCH == 10
// S512+PPXL's exposed pieces: the rule's lower-class half only, non-king
// pieces attacked by an enemy piece of a lower class (pawn < knight = bishop
// < rook < queen < king; pseudo-attacks on the occupancy), so never a pawn.
// Set-wise, from the enemy's pawn, minor and rook attacks, each computed only
// when a piece it could expose stands on the board.
Bitboard exposed_lower(const Position& pos);
// The same rule square by square, from each piece's attackers: the check of
// exposed_lower (its test, and every evaluation in FORK_DEBUG builds).
Bitboard exposed_lower_reference(const Position& pos);
#endif

// The feature stack's work, counted in stats builds (DESIGN.md §5.7, X1):
// evaluations; moves and null moves pushed (lazily: most are never
// evaluated); perspective updates in the evaluation walk (B0's
// both-at-once kernel counts two), the rows they subtract and add, and those
// whose delta changed pawns (S512+PP's link rows); perspectives recomputed
// from the board at a frame change (H512+PP: refreshed from a snapshot at an
// evaluation, once per evaluation that needs it) and at a search's root; the
// plies an evaluation walks, the longer perspective's walk; and the king
// moves pushed.
struct FeatureStackTally {
  std::uint64_t evaluations = 0;
  std::uint64_t move_pushes = 0;
  std::uint64_t null_pushes = 0;
  std::uint64_t perspective_updates = 0;
  std::uint64_t update_rows = 0;
  std::uint64_t link_updates = 0;
  std::uint64_t frame_refreshes = 0;
  std::uint64_t root_refreshes = 0;
  std::uint64_t walked_plies = 0;
  std::uint64_t king_pushes = 0;
};

#ifdef FORK_SEARCH_STATS
// The rows a delta subtracts and adds for one perspective in frame `f`
// (stats builds: the same columns advance_perspective uses).
int delta_row_count(const NetFile& net, const FeatureDelta& d, Color perspective, Frame f);
#endif

// One accumulator per ply of a search: ply 0 is the root, computed from
// scratch; the others are computed from their parent when first needed,
// except a perspective whose frame the move changes. That one is recomputed
// from the board at once, or in H512+PP, whose king regions make frame
// changes several times as frequent, lazily: when an evaluation needs that
// perspective at that ply or below, the evaluated ply's sums for it come
// from the frame's snapshot (the sums last computed in that frame, with the
// board they belong to), brought to the current board by the pieces and
// links that differ, and the snapshot takes the new sums. Children never
// evaluated cost nothing.
class FeatureStack {
 public:
  void reset(const NetFile& net, const Position& root);
  // Before `m` is made at `ply` (so the child is ply + 1).
  void push_move(const NetFile& net, int ply, const Position& before, Move m);
  // Before a null move at `ply`: the child's accumulator is the parent's.
  void push_null(int ply) {
#ifdef FORK_SEARCH_STATS
    ++tally_.null_pushes;
#endif
    Entry& e = entries_[ply + 1];
    e.delta = FeatureDelta{};
    e.frame[White] = entries_[ply].frame[White];
    e.frame[Black] = entries_[ply].frame[Black];
    e.computed[White] = e.computed[Black] = false;
  }
  // The evaluation at `ply` of `pos` (the position the stack has reached).
  int evaluate(const NetFile& net, int ply, const Position& pos);
#ifdef FORK_SEARCH_STATS
  const FeatureStackTally& tally() const { return tally_; }
  void set_tally(const FeatureStackTally& t) { tally_ = t; }  // X10: undo a side search's counts
#endif

 private:
  struct Entry {
    Accumulator acc;
    FeatureDelta delta;
    Frame frame[2];
    bool computed[2] = {false, false};
  };
#if FORK_NET_ARCH == 9
  // One perspective's sums in one frame, with the board they belong to (each
  // colour's pieces by kind). reset() starts every snapshot as the empty
  // board (the biases), so its first use adds every piece and link.
  struct FrameSnapshot {
    alignas(64) std::int16_t values[NetHidden];
    Bitboard pieces[2][6];
  };
  // A slot per file flip and region of one perspective.
  static constexpr int SnapshotSlots = 2 * NetMaxRegions;
  static int snapshot_slot(Frame f) { return (f.flip != 0) + 2 * (f.offset / NetPieceSquares); }
  // Sets `perspective`'s sums at `ply` from its frame's snapshot and `pos`
  // (the position at `ply`), and the snapshot to them.
  void refresh_from_snapshot(const NetFile& net, int ply, Color perspective, const Position& pos);

  FrameSnapshot snapshots_[2][SnapshotSlots];
#endif
  Entry entries_[MaxPly + 1];
#ifdef FORK_SEARCH_STATS
  FeatureStackTally tally_;
#endif
};

}  // namespace forkeng
