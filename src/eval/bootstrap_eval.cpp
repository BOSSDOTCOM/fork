#include "eval/bootstrap_eval.hpp"

#include <algorithm>
#include <cstdlib>

#include "eval/eval.hpp"

namespace forkeng {

namespace {

// Rings around the four centre squares: 0 for d4/e4/d5/e5 up to 3 on the edge.
int centre_distance(Square s) {
  const int f = file_of(s), r = rank_of(s);
  return std::max(f < 4 ? 3 - f : f - 4, r < 4 ? 3 - r : r - 4);
}

// Fork's own term weights, in centipawns (Phase 3 settles structure, not
// tuning; Phase 4 replaces this evaluation).
constexpr int KnightCentre = 8;    // per ring closer to the centre
constexpr int BishopCentre = 4;    // per ring closer to the centre
constexpr int PawnAdvanceMg = 2;   // per rank advanced, in the middlegame
constexpr int PawnAdvanceEg = 10;  // per rank advanced, in a pawn ending
constexpr int KingShelterMg = 6;   // per ring away from the centre, middlegame
constexpr int KingCentreEg = 10;   // per ring closer to the centre, endgame
constexpr int MopUpLead = 400;     // material lead (no pawns left) that starts the mop-up term
constexpr int MopUpEdge = 20;      // per ring the losing king is pushed out
constexpr int MopUpApproach = 6;   // per square the kings are closer

// One side's score: material plus placement, all non-negative.
int side_score(const Position& pos, Color c, int phase) {
  int score = 0;
  for (PieceType t : {Pawn, Knight, Bishop, Rook, Queen}) score += MaterialCp[t] * pos.count(c, t);

  for (Bitboard b = pos.pieces(c, Knight); b;) score += KnightCentre * (3 - centre_distance(pop_lsb(b)));
  for (Bitboard b = pos.pieces(c, Bishop); b;) score += BishopCentre * (3 - centre_distance(pop_lsb(b)));

  const int eg = FullPhase - phase;
  const int advance = (PawnAdvanceMg * phase + PawnAdvanceEg * eg) / FullPhase;
  for (Bitboard b = pos.pieces(c, Pawn); b;) score += advance * (rank_from(c, pop_lsb(b)) - 1);

  const int king_ring = centre_distance(pos.king_square(c));
  score += (KingShelterMg * king_ring * phase + KingCentreEg * (3 - king_ring) * eg) / FullPhase;
  return score;
}

// With no pawns left and a clear material lead, the stronger side gains for
// pushing the other king to the edge and bringing its own king closer.
int mop_up(const Position& pos, Color strong) {
  const Square loser = pos.king_square(~strong), winner = pos.king_square(strong);
  const int gap =
      std::max(std::abs(file_of(loser) - file_of(winner)), std::abs(rank_of(loser) - rank_of(winner)));
  return MopUpEdge * centre_distance(loser) + MopUpApproach * (7 - gap);
}

}  // namespace

int bootstrap_eval(const Position& pos) {
  if (pos.insufficient_material()) return 0;
  const int phase = game_phase(pos);
  int score[2] = {side_score(pos, White, phase), side_score(pos, Black, phase)};
  if (!pos.pieces(Pawn)) {
    int material[2] = {0, 0};
    for (Color c : {White, Black})
      for (PieceType t : {Knight, Bishop, Rook, Queen}) material[c] += MaterialCp[t] * pos.count(c, t);
    for (Color c : {White, Black})
      if (material[c] - material[~c] >= MopUpLead) score[c] += mop_up(pos, c);
  }
  const Color us = pos.side_to_move();
  return std::clamp(score[us] - score[~us], -EvalLimit, EvalLimit);
}

}  // namespace forkeng
