// see: static exchange evaluation (DESIGN.md §5.2, deliverable 4; KB
// search-techniques.md T7).
//
// Purpose: estimate the material result of a move's capture sequence on its
// destination square without searching it, for move ordering and pruning.
// Invariants:
// - The sides alternately recapture on the square with their least valuable
//   attacker; sliders behind a piece that leaves the line join the exchange
//   (attackers are recomputed from the occupancy after each capture); either
//   side may stop instead of recapturing; the move judged is forced.
// - A king captures only onto a square the other side no longer attacks.
// - Promotions (Fork's rule): the move judged counts its promotion gain and
//   puts the promoted piece on the square; later recaptures do not promote.
// - Pins are ignored (a pinned piece may recapture); an experiment may change
//   that (DESIGN.md §5.2).
// - Values: piece_value() of the evaluation (100/300/300/500/900).
// - No allocation, no floating point; the move must be legal.
#pragma once

#include "core/position.hpp"

namespace forkeng {

// The exchange's material result for the side making `m`, in centipawns.
int see_value(const Position& pos, Move m);

// Whether see_value(pos, m) >= threshold, decided as soon as the answer is
// settled (second external review, claim (a), 2026-10-26): the side about to
// choose between stopping and capturing again can always stop, so when the
// mover is to choose and the gain so far reaches the threshold the answer is
// yes, and when the opponent is to choose and it falls short the answer is
// no. Nor can one more capture move the gain by more than the piece now on
// the square, after which the other side may stop: when that cannot cross
// the threshold either, the answer is settled too (audit-1, P-3). Otherwise
// the exchange goes on, and with no capture left the gain so far decides.
// Equal to see_value(pos, m) >= threshold for every move and
// threshold (tests/test_see.cpp).
bool see_at_least(const Position& pos, Move m, int threshold);

}  // namespace forkeng
