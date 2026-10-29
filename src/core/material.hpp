// SPDX-License-Identifier: GPL-3.0-or-later

// material: piece values and the game phase, shared by the search and the
// evaluation.
//
// Purpose: one material scale for SEE, move ordering (MVV-LVA) and the LMR
// context, owned outside the evaluator, so a Phase 4 evaluator or an eval
// retune does not move SEE thresholds or the move order (audit-1 A9 F-12).
// The bootstrap evaluation uses the same table.
// Invariants:
// - MaterialCp: the conventional 1/3/3/5/9 pawn-unit scale in centipawns
//   (source in docs/ORIGINALITY.md, "Bootstrap evaluation"); the king has
//   none. Compile-time constants.
// - game_phase is in [0, FullPhase]: knights and bishops 1, rooks 2, queens
//   4, so the starting position is FullPhase = 24 (capped there: promotions
//   can add more); 0 is a pawn ending.
#pragma once

#include "core/position.hpp"

namespace forkeng {

inline constexpr int MaterialCp[6] = {100, 300, 300, 500, 900, 0};

// Material value of a piece type in centipawns.
constexpr int piece_value(PieceType t) { return MaterialCp[t]; }

inline constexpr int FullPhase = 24;
inline constexpr int PhaseWeight[6] = {0, 1, 1, 2, 4, 0};
// Inline: the search reads it too (the LMR context), and must be able to
// drop it when unused.
inline int game_phase(const Position& pos) {
  int phase = 0;
  for (PieceType t : {Knight, Bishop, Rook, Queen}) phase += PhaseWeight[t] * popcount(pos.pieces(t));
  return phase < FullPhase ? phase : FullPhase;
}

}  // namespace forkeng
