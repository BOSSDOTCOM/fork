// movegen: implementation (see movegen.hpp).
#include "core/movegen.hpp"

namespace forkeng {

namespace {

// One loop per piece type, so each slider lookup is resolved at compile time
// (measured: legal generation 8-9% faster on clang and gcc, DESIGN.md 6).
template <PieceType Pt, bool Captures, bool Quiets>
void add_piece_moves(const Position& pos, MoveList& list, Color us, Square ksq, Bitboard occ, Bitboard pinned,
                     Bitboard capture_target, Bitboard quiet_target) {
  for (Bitboard pcs = pos.pieces(us, Pt); pcs;) {
    Square from = pop_lsb(pcs);
    Bitboard a;
    if constexpr (Pt == Knight)
      a = knight_attacks(from);
    else if constexpr (Pt == Bishop)
      a = bishop_attacks(from, occ);
    else if constexpr (Pt == Rook)
      a = rook_attacks(from, occ);
    else
      a = queen_attacks(from, occ);
    if (pinned & bb(from)) {
      if constexpr (Pt == Knight) continue;
      a &= line(ksq, from);
    }
    if constexpr (Captures)
      for (Bitboard b = a & capture_target; b;) list.add(Move(from, pop_lsb(b), Capture));
    if constexpr (Quiets)
      for (Bitboard b = a & quiet_target; b;) list.add(Move(from, pop_lsb(b), Quiet));
  }
}

void add_promotions(MoveList& list, Square from, Square to, bool capture) {
  int base = capture ? PromoCaptureKnight : PromoKnight;
  for (int i = 3; i >= 0; --i) list.add(Move(from, to, base + i));  // queen first
}

// Fully legal generation (see DESIGN.md 4.6): check and pin masks instead of
// make-and-test.
template <bool Captures, bool Quiets>
void generate_moves(const Position& pos, MoveList& list) {
  const Color us = pos.side_to_move(), them = ~us;
  const Square ksq = pos.king_square(us);
  const Bitboard occ = pos.pieces(), ours = pos.pieces(us), theirs = pos.pieces(them);
  const Bitboard checkers = pos.checkers();

  // King moves, tested with the king lifted off the board so it cannot hide
  // behind itself on a checking ray.
  const Bitboard occ_no_king = occ ^ bb(ksq);
  for (Bitboard b = king_attacks(ksq) & ~ours; b;) {
    Square to = pop_lsb(b);
    bool capture = theirs & bb(to);
    if ((capture ? Captures : Quiets) && !pos.attacked_by(them, to, occ_no_king))
      list.add(Move(ksq, to, capture ? Capture : Quiet));
  }
  if (has_multiple(checkers)) return;

  const Bitboard target = checkers ? between(ksq, lsb(checkers)) | checkers : ~Bitboard{0};
  const Bitboard capture_target = theirs & target;
  const Bitboard quiet_target = ~occ & target;
  const Bitboard pinned = pos.pinned();

  add_piece_moves<Knight, Captures, Quiets>(pos, list, us, ksq, occ, pinned, capture_target, quiet_target);
  add_piece_moves<Bishop, Captures, Quiets>(pos, list, us, ksq, occ, pinned, capture_target, quiet_target);
  add_piece_moves<Rook, Captures, Quiets>(pos, list, us, ksq, occ, pinned, capture_target, quiet_target);
  add_piece_moves<Queen, Captures, Quiets>(pos, list, us, ksq, occ, pinned, capture_target, quiet_target);

  const int up = forward(us);
  const Square ep = pos.ep_square();
  for (Bitboard pawns = pos.pieces(us, Pawn); pawns;) {
    Square from = pop_lsb(pawns);
    Bitboard allowed = (pinned & bb(from)) ? line(ksq, from) : ~Bitboard{0};
    bool promotes = relative_rank(us, from) == 6;

    Square one = from + up;
    if (!(occ & bb(one))) {
      if (allowed & target & bb(one)) {
        if (promotes) {
          if constexpr (Captures) add_promotions(list, from, one, false);
        } else if constexpr (Quiets) {
          list.add(Move(from, one, Quiet));
        }
      }
      if constexpr (Quiets) {
        Square two = one + up;
        if (relative_rank(us, from) == 1 && !(occ & bb(two)) && (allowed & target & bb(two)))
          list.add(Move(from, two, DoublePush));
      }
    }

    if constexpr (Captures) {
      for (Bitboard b = pawn_attacks(us, from) & capture_target & allowed; b;) {
        Square to = pop_lsb(b);
        if (promotes)
          add_promotions(list, from, to, true);
        else
          list.add(Move(from, to, Capture));
      }
      // En passant: simulate the occupancy change and look for any attacker
      // other than the captured pawn. Covers checks, pins and rank discovery.
      if (ep != NoSquare && (pawn_attacks(us, from) & bb(ep))) {
        Square capsq = ep - up;
        Bitboard after = (occ ^ bb(from) ^ bb(capsq)) | bb(ep);
        if (!(pos.attackers_to(ksq, after) & theirs & ~bb(capsq))) list.add(Move(from, ep, EnPassant));
      }
    }
  }

  if constexpr (Quiets) {
    if (checkers) return;
    const int rights = pos.castling_rights() & (us == White ? WhiteOO | WhiteOOO : BlackOO | BlackOOO);
    for (int side = 0; side < 2; ++side) {
      int right = (us == White ? WhiteOO : BlackOO) << side;
      if (!(rights & right)) continue;
      Square rook = relative(us, side == 0 ? 7 : 0);
      if (between(ksq, rook) & occ) continue;
      Square kto = Position::castle_king_to(ksq, rook);
      bool safe = true;
      for (Bitboard path = between(ksq, kto) | bb(kto); path && safe;)
        safe = !pos.attacked_by(them, pop_lsb(path), occ);
      if (safe) list.add(Move(ksq, rook, Castle));
    }
  }
}

}  // namespace

template <>
void generate<GenMode::Legal>(const Position& pos, MoveList& list) {
  generate_moves<true, true>(pos, list);
}
template <>
void generate<GenMode::Captures>(const Position& pos, MoveList& list) {
  generate_moves<true, false>(pos, list);
}
template <>
void generate<GenMode::Quiets>(const Position& pos, MoveList& list) {
  generate_moves<false, true>(pos, list);
}

}  // namespace forkeng
