#include "search/see.hpp"

#include <algorithm>

#include "core/material.hpp"

namespace forkeng {

// The swap-list method (CPW "SEE - The Swap Algorithm"): record what each
// capture in the sequence would swing if the exchange stopped right after it,
// then walk back from the end, letting each side choose between stopping and
// continuing.
int see_value(const Position& pos, Move m) {
  if (m.is_castle()) return 0;
  const Square from = m.from(), to = m.to();
  Bitboard occ = pos.pieces() ^ bb(from);
  int swing[32];
  if (m.is_en_passant()) {
    swing[0] = piece_value(Pawn);
    occ ^= bb(pos.capture_square(m));
  } else {
    swing[0] = m.is_capture() ? piece_value(kind_of(pos.piece_at(to))) : 0;
  }
  // The value now standing on the square, which the next capture wins.
  int standing = piece_value(kind_of(pos.piece_at(from)));
  if (m.is_promotion()) {
    swing[0] += piece_value(m.promo_type()) - piece_value(Pawn);
    standing = piece_value(m.promo_type());
  }

  Color side = ~pos.side_to_move();
  int d = 0;
  for (;;) {
    const Bitboard attackers = pos.attackers_to(to, occ) & occ & pos.pieces(side);
    if (!attackers) break;
    PieceType pt = Pawn;
    while (!(attackers & pos.pieces(pt))) pt = PieceType(pt + 1);
    const Square sq = lsb(attackers & pos.pieces(pt));
    if (pt == King && (pos.attackers_to(to, occ ^ bb(sq)) & occ & pos.pieces(~side))) break;
    ++d;
    swing[d] = standing - swing[d - 1];
    standing = piece_value(pt);  // the king (value 0) is never captured: the check above
    occ ^= bb(sq);
    side = ~side;
  }
  while (d > 0) {
    swing[d - 1] = -std::max(-swing[d - 1], swing[d]);
    --d;
  }
  return swing[0];
}

bool see_at_least(const Position& pos, Move m, int threshold) {
  if (m.is_castle()) return 0 >= threshold;
  const Square from = m.from(), to = m.to();
  Bitboard occ = pos.pieces() ^ bb(from);
  // The mover's net gain if the exchange stopped now, and the value of the
  // piece standing on the square (what the next capture would win).
  int net_gain;
  if (m.is_en_passant()) {
    net_gain = piece_value(Pawn);
    occ ^= bb(pos.capture_square(m));
  } else {
    net_gain = m.is_capture() ? piece_value(kind_of(pos.piece_at(to))) : 0;
  }
  int standing = piece_value(kind_of(pos.piece_at(from)));
  if (m.is_promotion()) {
    net_gain += piece_value(m.promo_type()) - piece_value(Pawn);
    standing = piece_value(m.promo_type());
  }
  Color decider = ~pos.side_to_move();  // the opponent chooses first
  bool our_turn = false;
  for (;;) {
    if (our_turn ? net_gain >= threshold : net_gain < threshold) return net_gain >= threshold;
    // One capture more changes the gain by at most the piece standing on the
    // square, after which the other side may stop: when even that cannot
    // cross the threshold, the answer is settled without a lookup (audit-1,
    // P-3; before the first lookup in 30.3% of calls).
    if (our_turn ? net_gain + standing < threshold : net_gain - standing >= threshold) return !our_turn;
    const Bitboard attackers = pos.attackers_to(to, occ) & occ & pos.pieces(decider);
    if (!attackers) return net_gain >= threshold;
    PieceType pt = Pawn;
    while (!(attackers & pos.pieces(pt))) pt = PieceType(pt + 1);
    const Square sq = lsb(attackers & pos.pieces(pt));
    // The king may only capture onto a square the other side no longer attacks.
    if (pt == King && (pos.attackers_to(to, occ ^ bb(sq)) & occ & pos.pieces(~decider)))
      return net_gain >= threshold;
    net_gain += our_turn ? standing : -standing;
    standing = piece_value(pt);
    occ ^= bb(sq);
    decider = ~decider;
    our_turn = !our_turn;
  }
}

}  // namespace forkeng
