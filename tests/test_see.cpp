// Static exchange evaluation (DESIGN.md §5.2, deliverable 4). Positions are
// constructed for Fork (legality checked by tools/check_search_positions.py);
// each expected value is derived by hand in its comment.
#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "eval/bootstrap_eval.hpp"
#include "harness.hpp"
#include "search/see.hpp"
#include "suite.hpp"

namespace forkeng::test {

namespace {

int see_of(std::string_view fen, std::string_view uci) {
  Position pos;
  CHECK_MSG(pos.set_fen(fen), fen);
  const Move m = pos.parse_uci(uci);
  CHECK_MSG(!m.is_none(), fen << " " << uci);
  return m.is_none() ? -99999 : see_value(pos, m);
}

// The oracle: the same exchange rules written another way. Recursive, and it
// finds each side's attackers by asking every piece on the board whether it
// attacks the square, instead of Position::attackers_to.
Bitboard attackers_of(const Position& pos, Color side, Square to, Bitboard occ) {
  Bitboard out = 0;
  for (Bitboard b = pos.pieces(side) & occ; b;) {
    const Square s = pop_lsb(b);
    const PieceType t = kind_of(pos.piece_at(s));
    const Bitboard reach = t == Pawn ? pawn_attacks(side, s) : attacks(t, s, occ);
    if (reach & bb(to)) out |= bb(s);
  }
  return out;
}

// What `side`, to move, gains on `to` where a piece worth `standing` stands:
// stop (0), or capture with its least valuable attacker and let the other side
// choose in turn.
int swap_from(const Position& pos, Square to, Bitboard occ, Color side, int standing) {
  const Bitboard mine = attackers_of(pos, side, to, occ);
  if (!mine) return 0;
  for (PieceType t : {Pawn, Knight, Bishop, Rook, Queen, King}) {
    const Bitboard of_type = mine & pos.pieces(t);
    if (!of_type) continue;
    const Square s = lsb(of_type);
    if (t == King && attackers_of(pos, ~side, to, occ ^ bb(s))) return 0;
    return std::max(0, standing - swap_from(pos, to, occ ^ bb(s), ~side, piece_value(t)));
  }
  return 0;
}

int reference_see(const Position& pos, Move m) {
  if (m.is_castle()) return 0;
  Bitboard occ = pos.pieces() ^ bb(m.from());
  int captured_value = 0;
  if (m.is_en_passant()) {
    captured_value = piece_value(Pawn);
    occ ^= bb(pos.capture_square(m));
  } else if (m.is_capture()) {
    captured_value = piece_value(kind_of(pos.piece_at(m.to())));
  }
  int standing = piece_value(kind_of(pos.piece_at(m.from())));
  if (m.is_promotion()) {
    captured_value += piece_value(m.promo_type()) - piece_value(Pawn);
    standing = piece_value(m.promo_type());
  }
  return captured_value - swap_from(pos, m.to(), occ, ~pos.side_to_move(), standing);
}

void compare_tree(Position& pos, int depth, int& compared) {
  MoveList list;
  generate<GenMode::Legal>(pos, list);
  for (Move m : list) {
    const int got = see_value(pos, m), want = reference_see(pos, m);
    CHECK_MSG(got == want, pos.fen() << " " << pos.move_to_uci(m) << ": " << got << " vs " << want);
    ++compared;
    // see_at_least decides early (review 2, claim (a)): it must agree with
    // the full value at the value itself, either side of it, and a spread.
    for (const int t : {got - 1, got, got + 1, -1000, -500, -300, -100, -1, 0, 1, 100, 300, 500, 1000})
      CHECK_MSG(see_at_least(pos, m, t) == (got >= t),
                pos.fen() << " " << pos.move_to_uci(m) << ": see " << got << ", threshold " << t);
  }
  if (depth == 0) return;
  for (Move m : list) {
    pos.make(m);
    compare_tree(pos, depth - 1, compared);
    pos.unmake(m);
  }
}

}  // namespace

TEST_CASE("see", "hand-derived exchanges") {
  // exd5, nothing recaptures: +100.
  CHECK_EQ(see_of("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1", "e4d5"), 100);
  // exd5 cxd5: pawn for pawn, 0.
  CHECK_EQ(see_of("4k3/8/2p5/3p4/4P3/8/8/4K3 w - - 0 1", "e4d5"), 0);
  // Nxd5 cxd5: a knight for a pawn, 100 - 300 = -200.
  CHECK_EQ(see_of("4k3/8/2p5/3p4/8/4N3/8/4K3 w - - 0 1", "e3d5"), -200);
  // Rxd5 Rxd5 Rxd5 (the second white rook x-rays through d2): Black does best
  // not to recapture, so White wins the pawn, +100.
  CHECK_EQ(see_of("3rk3/8/8/3p4/8/8/3R4/3RK3 w - - 0 1", "d2d5"), 100);
  // Qxd4 Kxd4: the queen for a pawn, 100 - 900 = -800.
  CHECK_EQ(see_of("8/8/8/3k4/3p4/8/8/3QK3 w - - 0 1", "d1d4"), -800);
  // Rxd4: the king may not recapture, because the queen behind the rook now
  // defends d4: +100.
  CHECK_EQ(see_of("8/8/8/3k4/3p4/8/3R4/3QK3 w - - 0 1", "d2d4"), 100);
  // En passant exd6: +100.
  CHECK_EQ(see_of("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", "e5d6"), 100);
  // b8=Q, nothing attacks b8: the promotion gain, 900 - 100 = +800.
  CHECK_EQ(see_of("4k3/1P6/8/8/8/8/8/4K3 w - - 0 1", "b7b8q"), 800);
  // b8=Q Rxb8: the pawn is lost, -100 (the rook on a8 guards b8).
  CHECK_EQ(see_of("r3k3/1P6/8/8/8/8/8/4K3 w - - 0 1", "b7b8q"), -100);
  // A quiet move to an attacked square: the knight is lost, -300.
  CHECK_EQ(see_of("4k3/8/2p5/8/8/4N3/8/4K3 w - - 0 1", "e3d5"), -300);
  // Castling exchanges nothing.
  CHECK_EQ(see_of("4k3/8/8/8/8/8/8/4K2R w K - 0 1", "e1g1"), 0);
}

TEST_CASE("see",
          "agrees with the recursive oracle on every move of the perft suites to depth 2 and random games") {
  int compared = 0;
  for (const PerftPosition& p : perft_suite()) {
    Position pos;
    CHECK(pos.set_fen(p.fen));
    compare_tree(pos, Optimized ? 2 : 1, compared);
  }
  std::uint64_t seed = 20261024;
  for (int game = 0; game < (Optimized ? 400 : 40); ++game) {
    Position pos;
    for (int ply = 0; ply < 80; ++ply) {
      MoveList list;
      generate<GenMode::Legal>(pos, list);
      if (list.size() == 0 || pos.fifty_move_reached()) break;
      compare_tree(pos, 0, compared);
      pos.make(list[splitmix_next(seed) % list.size()]);
    }
  }
  CHECK(compared > (Optimized ? 500000 : 5000));
  // see_at_least is see_value compared with the threshold.
  Position pos;
  CHECK(pos.set_fen("4k3/8/2p5/3p4/8/4N3/8/4K3 w - - 0 1"));
  const Move m = pos.parse_uci("e3d5");
  CHECK(see_at_least(pos, m, -200) && !see_at_least(pos, m, -199));
}

}  // namespace forkeng::test
