// SPDX-License-Identifier: GPL-3.0-or-later

// eval_drift: the drift tables (tier 2; think tank R34 and engine survey E4;
// KB search-techniques.md §3.23, static evaluation correction history).
//
// Purpose: learn how far search results land from the raw static eval in
// positions that share a key, per side to move, so the search can add that
// drift to the eval it estimates with (pruning and the quiescence
// stand-pat). The TT and anything that could feed training keep the raw
// eval. The table is the pawn drift table's (T32, branch tier2/drift, its
// constants measured there); here it is keyed by four other keys:
// - pieces: one table per colour, keyed by that colour's pieces other than
//   pawns, its king included (R34's non-pawn key per side);
// - minor: the knights and bishops of both colours;
// - major: the rooks and queens of both colours;
// - threat: Fork's threat configuration (threat_drift_key below).
// Invariants:
// - Each entry is the drift in 1/DriftGrain centipawns. An update moves it
//   toward the observed error, clamped to [-DriftLimit, DriftLimit] cp, by
//   the fraction min(depth, DriftWeightCap) / DriftWeightTotal of the gap: a
//   weighted running mean, so no entry ever leaves [-DriftLimit, DriftLimit]
//   cp for any sequence of updates (tests/test_eval_drift.cpp).
// - The drift read is whole centipawns, rounded toward zero.
// - Integer arithmetic only (bench determinism). One set of tables per
//   Searcher (per thread); sharing between threads is Phase 6.
// - The slot is the key's top DriftSlotBits bits; keys that share them share
//   an entry (no key check: a collision only blurs the mean).
// - The material keys (DriftKeys) are XORs of the Zobrist piece-square keys
//   of the pieces they cover, so a move changes them by the pieces it moves,
//   captures or promotes: advance_drift_keys gives exactly drift_keys of the
//   position after the move (tests/test_eval_drift.cpp, every move of
//   random games against the recomputation).
#pragma once

#include <cstdint>

#include "core/position.hpp"
#include "core/splitmix.hpp"
#include "core/types.hpp"
#include "core/zobrist.hpp"
#include "tune/params.hpp"

namespace forkeng {

// Fork's sizes (justified in DESIGN.md §5.2, "Search constants"); the
// weights, the limit and the shares are in the parameter table.
constexpr int DriftSlotBits = 15;
constexpr int DriftSlots = 1 << DriftSlotBits;
constexpr int DriftGrain = 128;
// The shares (PieceDriftShare, ...) are in 1/DriftShareUnit of the learned
// drift: the term a table adds is its drift * share / DriftShareUnit.
constexpr int DriftShareUnit = 64;
// The depth scale (switch use_drift_depth_scale): from this depth on the
// switched-on terms apply whole; below it, at depth d (the quiescence search
// at 0), (d + 1) / (DriftFullDepth + 1) of them.
constexpr int DriftFullDepth = 3;
// The window gate (switch use_drift_window_gate; idea 59's gate margin):
// the (depth-scaled) sum applies whole while the estimate it gives lies
// within DriftWindowMargin cp of the window's nearer finite bound, and
// fades linearly to nothing over the next DriftWindowFade cp.
constexpr int DriftWindowMargin = 25;
constexpr int DriftWindowFade = 25;

class EvalDrift {
 public:
  static int slot(Key key) { return static_cast<int>(key >> (64 - DriftSlotBits)); }

  // The drift for `side` to move at `key`, in centipawns.
  int offset(Color side, Key key) const { return table_[side][slot(key)] / DriftGrain; }

  // A search of a node with this key scored `error` cp away from its raw
  // static eval (score minus eval), at `depth`.
  void learn(Color side, Key key, int error, int depth) {
    const int limit = DriftLimit * DriftGrain;
    const int target = error * DriftGrain > limit    ? limit
                       : error * DriftGrain < -limit ? -limit
                                                     : error * DriftGrain;
    // At most the whole gap: a weight above the total would overshoot.
    const int cap = DriftWeightCap < DriftWeightTotal ? DriftWeightCap : DriftWeightTotal;
    const int weight = depth < cap ? depth : cap;
    std::int32_t& v = table_[side][slot(key)];
    v += (target - v) * weight / DriftWeightTotal;
  }

  void clear() {
    for (auto& side : table_)
      for (std::int32_t& v : side) v = 0;
  }

 private:
  std::int32_t table_[2][DriftSlots] = {};
};

// The material keys of a position: XORs of the Zobrist piece-square keys
// (zobrist.hpp) of the pieces each covers.
struct DriftKeys {
  Key pieces[2] = {0, 0};  // per colour: its pieces other than pawns, the king included
  Key minors = 0;          // knights and bishops, both colours
  Key majors = 0;          // rooks and queens, both colours

  // `p` placed on or lifted from `sq`.
  void toggle(Piece p, Square sq) {
    const PieceType t = kind_of(p);
    if (t == Pawn) return;
    const Key z = zobrist::piece_square[p][sq];
    pieces[side_of(p)] ^= z;
    if (t == Knight || t == Bishop) minors ^= z;
    if (t == Rook || t == Queen) majors ^= z;
  }

  bool operator==(const DriftKeys&) const = default;
};

// The material keys from scratch.
inline DriftKeys drift_keys(const Position& pos) {
  DriftKeys k;
  for (Bitboard b = pos.pieces() & ~pos.pieces(Pawn); b;) {
    const Square sq = pop_lsb(b);
    k.toggle(pos.piece_at(sq), sq);
  }
  return k;
}

// `k`, the keys of `before`, becomes the keys after `m` (a legal move of
// `before`, not yet made): the pieces the move lifts, captures and places.
inline void advance_drift_keys(DriftKeys& k, const Position& before, Move m) {
  const Square from = m.from(), to = m.to();
  const Piece p = before.piece_at(from);
  if (m.is_castle()) {  // encoded king to rook square
    const Position::CastleLanding land = Position::castle_landing(from, to);
    const Piece rook = before.piece_at(to);
    k.toggle(p, from);
    k.toggle(p, land.king);
    k.toggle(rook, to);
    k.toggle(rook, land.rook);
    return;
  }
  if (m.is_capture()) {
    const Square cap = before.capture_square(m);
    k.toggle(before.piece_at(cap), cap);
  }
  k.toggle(p, from);
  k.toggle(m.is_promotion() ? piece_of(side_of(p), m.promo_type()) : p, to);
}

// The squares `c`'s pawns attack (set-wise; the masks drop the shifts that
// would wrap from one edge file to the other).
inline Bitboard pawn_cover(Color c, Bitboard pawns) {
  return c == White ? ((pawns << 7) & ~FileH) | ((pawns << 9) & ~FileA)
                    : ((pawns >> 9) & ~FileH) | ((pawns >> 7) & ~FileA);
}

// Fork's threat configuration (tier 2, E4's threat table): which pieces
// other than pawns and kings stand attacked, and by whom. Three sets: the
// side to move's pieces the opponent attacks, the opponent's pieces the side
// to move attacks, and the pieces of either colour an enemy pawn attacks
// (the cheapest attacker, the threat that most often costs the piece),
// hashed together with the splitmix output function. The side to move is
// part of the tables' index, so the sets are taken relative to it.
inline Key threat_drift_key(const Position& pos) {
  const Color us = pos.side_to_move(), them = ~us;
  const Bitboard targets = pos.pieces() & ~pos.pieces(Pawn) & ~pos.pieces(King);
  const Bitboard ours = targets & pos.pieces(us), theirs = targets & pos.pieces(them);
  const Bitboard hit_ours = ours & pos.attacked_squares(them);
  const Bitboard hit_theirs = theirs & pos.attacked_squares(us);
  const Bitboard by_pawns =
      (ours & pawn_cover(them, pos.pieces(them, Pawn))) | (theirs & pawn_cover(us, pos.pieces(us, Pawn)));
  return splitmix_finalize(splitmix_finalize(splitmix_finalize(hit_ours) ^ hit_theirs) ^ by_pawns);
}

}  // namespace forkeng
