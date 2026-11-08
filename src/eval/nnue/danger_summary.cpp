// SPDX-License-Identifier: GPL-3.0-or-later

#include "eval/nnue/danger_summary.hpp"

#include "core/bitboard.hpp"

namespace forkeng {

DangerSummary danger_summary(const Position& pos, Bitboard& exposed) {
  const Bitboard occ = pos.pieces();
  // Per side: the squares its knights, bishops, rooks and queens attack, kept
  // apart for the check squares, and the attack sets by class as
  // exposed_pieces builds them (upto[c][k]: attacked by c's pieces of class
  // k + 1 or lower, pawn < minor < rook < queen < king).
  Bitboard knights[2], bishops[2], rooks[2], queens[2], upto[2][5];
  for (const Color c : {White, Black}) {
    Bitboard pawns = 0;
    knights[c] = bishops[c] = rooks[c] = queens[c] = 0;
    for (Bitboard b = pos.pieces(c, Pawn); b;) pawns |= pawn_attacks(c, pop_lsb(b));
    for (Bitboard b = pos.pieces(c, Knight); b;) knights[c] |= knight_attacks(pop_lsb(b));
    for (Bitboard b = pos.pieces(c, Bishop); b;) bishops[c] |= bishop_attacks(pop_lsb(b), occ);
    for (Bitboard b = pos.pieces(c, Rook); b;) rooks[c] |= rook_attacks(pop_lsb(b), occ);
    for (Bitboard b = pos.pieces(c, Queen); b;) queens[c] |= queen_attacks(pop_lsb(b), occ);
    upto[c][0] = pawns;
    upto[c][1] = pawns | knights[c] | bishops[c];
    upto[c][2] = upto[c][1] | rooks[c];
    upto[c][3] = upto[c][2] | queens[c];
    upto[c][4] = upto[c][3] | king_attacks(pos.king_square(c));
  }

  exposed = 0;
  for (const Color c : {White, Black}) {
    const Bitboard* enemy = upto[~c];
    exposed |= pos.pieces(c, Knight, Bishop) & enemy[0];
    exposed |= pos.pieces(c, Rook) & enemy[1];
    exposed |= pos.pieces(c, Queen) & enemy[2];
    exposed |= (pos.pieces(c) & ~pos.pieces(King)) & enemy[4] & ~upto[c][4];
  }

  DangerSummary d;
  for (const Color x : {White, Black}) {
    const Color them = ~x;
    const Square king = pos.king_square(x);
    const Bitboard hit = (king_attacks(king) | bb(king)) & upto[them][4];
    d.zone_attacked[x] = popcount(hit);
    d.zone_weak[x] = popcount(hit & ~upto[x][3]);  // defended by none of x's pieces but the king
    const Bitboard diagonal = bishop_attacks(king, occ), straight = rook_attacks(king, occ);
    const Bitboard checks = (knight_attacks(king) & knights[them]) | (diagonal & bishops[them]) |
                            (straight & rooks[them]) | ((diagonal | straight) & queens[them]);
    d.safe_checks[x] = popcount(checks & ~pos.pieces(them) & ~upto[x][4]);
    d.pinned_count[x] = popcount(x == pos.side_to_move()
                                     ? pos.pinned()
                                     : pos.lone_shields(king, pos.pieces(x), pos.pieces(them, Rook, Queen),
                                                        pos.pieces(them, Bishop, Queen)));
    d.exposed_count[x] = popcount(exposed & pos.pieces(x));
  }
  return d;
}

}  // namespace forkeng
