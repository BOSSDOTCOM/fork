// bootstrap_eval: Phase 3's deliberately simple evaluation (DESIGN.md §5.2,
// deliverable 1), replaced in Phase 4.
//
// Purpose: give the search meaningful scores while it is built: material,
// a little piece centralization, pawn advancement and king placement that
// shift from middlegame to endgame, and a term that drives a bare king to
// the edge so mates such as KRK can be played without tablebases.
// Invariants:
// - Centipawns from the side to move's view; 0 when neither side can mate on
//   material (Position::insufficient_material).
// - Colour-symmetric: a position and its mirror (ranks flipped, colours and
//   side to move swapped) score the same (tests/test_eval.cpp).
// - Integer arithmetic only, every term non-negative before the final
//   difference, so results are identical on every build.
#pragma once

#include "core/position.hpp"

namespace forkeng {

// Material value of a piece type in centipawns (the king has none here).
int piece_value(PieceType t);

// Game phase from the non-pawn material left: knights and bishops 1, rooks 2,
// queens 4, so the starting position is 24 (capped there: promotions can add
// more). 24 is the middlegame, 0 a pawn ending. Inline: the search reads it
// too (the LMR context), and must be able to drop it when unused.
inline constexpr int FullPhase = 24;
inline constexpr int PhaseWeight[6] = {0, 1, 1, 2, 4, 0};
inline int game_phase(const Position& pos) {
  int phase = 0;
  for (PieceType t : {Knight, Bishop, Rook, Queen}) phase += PhaseWeight[t] * popcount(pos.pieces(t));
  return phase < FullPhase ? phase : FullPhase;
}

int bootstrap_eval(const Position& pos);

}  // namespace forkeng
