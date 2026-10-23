// Walks perft trees and checks internal invariants at every node against
// independent (slow, obvious) oracles.
#include <algorithm>

#include "core/movegen.hpp"
#include "harness.hpp"
#include "suite.hpp"

using namespace fork;
using namespace fork::test;

namespace {

std::uint64_t rng_state = 0x0DDB'A11C'0FFE'E123ULL;
std::uint16_t random_raw_move() {
  rng_state ^= rng_state << 13;
  rng_state ^= rng_state >> 7;
  rng_state ^= rng_state << 17;
  return static_cast<std::uint16_t>(rng_state);
}

bool accepts(const Position& pos, Move m) { return pos.is_pseudo_legal(m) && pos.is_legal(m); }

Bitboard slider_attackers(const Position& pos, Color by, Square s, Bitboard occ) {
  return (bishop_attacks(s, occ) & pos.pieces(by, Bishop, Queen)) |
         (rook_attacks(s, occ) & pos.pieces(by, Rook, Queen));
}

// Oracle for blockers/pinners: remove each piece in turn and see which enemy
// sliders start attacking the king.
void check_blockers(const Position& pos, Color c, const std::string& fen) {
  const Square ksq = pos.king_square(c);
  const Bitboard occ = pos.pieces();
  const Bitboard before = slider_attackers(pos, ~c, ksq, occ);
  Bitboard blockers = 0, pinners = 0;
  for (Bitboard b = occ & ~bb(ksq); b;) {
    Square sq = pop_lsb(b);
    Bitboard exposed = slider_attackers(pos, ~c, ksq, occ ^ bb(sq)) & ~before & ~bb(sq);
    if (exposed) {
      blockers |= bb(sq);
      if (pos.pieces(c) & bb(sq)) pinners |= exposed;
    }
  }
  CHECK_MSG(pos.blockers(c) == blockers, "blockers, " << fen << " color " << int(c));
  CHECK_MSG(pos.pinners(c) == pinners, "pinners, " << fen << " color " << int(c));
}

void check_state(const Position& pos, const std::string& fen) {
  const State& s = pos.state();
  const State fresh = pos.compute_state();
  CHECK_MSG(s.key == fresh.key, "key, " << fen);
  CHECK_MSG(s.pawn_key == fresh.pawn_key, "pawn key, " << fen);
  CHECK_MSG(s.material_key == fresh.material_key, "material key, " << fen);
  CHECK_MSG(s.non_pawn_key[White] == fresh.non_pawn_key[White] &&
                s.non_pawn_key[Black] == fresh.non_pawn_key[Black],
            "non-pawn keys, " << fen);
  CHECK_MSG(s == fresh, "full state, " << fen);

  const Color us = pos.side_to_move(), them = ~us;
  CHECK_MSG(pos.checkers() == (pos.attackers_to(pos.king_square(us), pos.pieces()) & pos.pieces(them)),
            "checkers, " << fen);
  check_blockers(pos, White, fen);
  check_blockers(pos, Black, fen);

  // Check squares: a piece of ours of that type on the square would attack
  // the enemy king.
  const Bitboard eking = bb(pos.king_square(them));
  for (Square sq = 0; sq < 64; ++sq) {
    CHECK_MSG(bool(pos.check_squares(Pawn) & bb(sq)) == bool(pawn_attacks(us, sq) & eking), "pawn check squares, " << fen);
    for (PieceType t : {Knight, Bishop, Rook, Queen})
      CHECK_MSG(bool(pos.check_squares(t) & bb(sq)) == bool(attacks(t, sq, pos.pieces()) & eking),
                "check squares, " << fen << " type " << int(t));
  }
  CHECK(pos.check_squares(King) == 0);
}

void check_node(Position& pos, const MoveList& legal, const MoveList* parent) {
  const std::string fen = pos.fen();
  check_state(pos, fen);

  Position copy;
  std::string error;
  CHECK_MSG(copy.set_fen(fen, &error), "fen reparse, " << fen << ": " << error);
  CHECK_MSG(copy.fen() == fen && copy.key() == pos.key(), "fen round trip, " << fen);

  MoveList captures, quiets;
  generate<GenType::Captures>(pos, captures);
  generate<GenType::Quiets>(pos, quiets);
  CHECK_MSG(captures.size() + quiets.size() == legal.size(), "partition size, " << fen);
  for (Move m : captures)
    CHECK_MSG((m.is_capture() || m.is_promotion()) && legal.contains(m) && !quiets.contains(m),
              "capture list, " << fen << " " << pos.move_to_uci(m));
  for (Move m : quiets)
    CHECK_MSG(!m.is_capture() && !m.is_promotion() && legal.contains(m),
              "quiet list, " << fen << " " << pos.move_to_uci(m));

  for (Move m : legal) {
    CHECK_MSG(accepts(pos, m), "generated move rejected, " << fen << " " << pos.move_to_uci(m));
    CHECK_MSG(pos.parse_uci(pos.move_to_uci(m)) == m, "uci round trip, " << fen);
    const bool predicted_check = pos.gives_check(m);
    const Key predicted_key = pos.key_after(m);
    pos.make(m);
    CHECK_MSG(predicted_check == pos.in_check(), "gives_check, " << fen << " " << m.raw());
    CHECK_MSG(predicted_key == pos.key(), "key_after, " << fen << " " << m.raw());
    pos.unmake(m);
  }
  if (parent)
    for (Move m : *parent)
      CHECK_MSG(accepts(pos, m) == legal.contains(m), "parent move, " << fen << " raw " << m.raw());
  for (int i = 0; i < 48; ++i) {
    Move m = Move::from_raw(random_raw_move());
    CHECK_MSG(accepts(pos, m) == legal.contains(m), "random move, " << fen << " raw " << m.raw());
  }
}

void walk(Position& pos, int depth, const MoveList* parent) {
  MoveList legal;
  generate<GenType::Legal>(pos, legal);
  check_node(pos, legal, parent);
  if (depth == 0) return;

  const Position snapshot = pos;
  for (Move m : legal) {
    pos.make(m);
    // The side that moved must not be left in check.
    CHECK(!pos.attacked_by(pos.side_to_move(), pos.king_square(~pos.side_to_move()), pos.pieces()));
    walk(pos, depth - 1, &legal);
    pos.unmake(m);
    CHECK_MSG(pos.same_state(snapshot), "unmake, " << snapshot.fen() << " " << pos.move_to_uci(m));
  }

  if (!pos.in_check()) {
    pos.make_null();
    check_state(pos, pos.fen());
    CHECK(pos.checkers() == 0);
    pos.unmake_null();
    CHECK_MSG(pos.same_state(snapshot), "unmake_null, " << snapshot.fen());
  }
}


}  // namespace

TEST_CASE("consistency", "invariants at every node of the suite trees") {
  for (const PerftPosition& pp : perft_suite()) {
    // Trees of about 10^3-10^4 nodes (sanitizer builds), up to 2*10^5 (optimized).
    int depth = pp.counts[2] < 10000 ? 4 : 3;
    if (Optimized && pp.counts[3] < 1000000) ++depth;
    for (bool mirror : {false, true}) {
      Position pos;
      CHECK(pos.set_fen(pp.fen));
      if (mirror) pos = pos.mirrored();
      walk(pos, depth - 1, nullptr);
    }
  }
}

TEST_CASE("consistency", "special positions") {
  for (const EdgePosition& ep : edge_positions()) {
    for (bool mirror : {false, true}) {
      Position pos;
      std::string error;
      CHECK_MSG(pos.set_fen(ep.fen, &error), ep.fen << ": " << error);
      if (mirror) pos = pos.mirrored();
      walk(pos, Optimized ? 3 : 2, nullptr);
    }
  }
}

namespace {

// Every 16-bit move encoding in one position: never crashes, and
// pseudo-legal + legal agrees exactly with the generator.
void exhaustive(Position& pos) {
  MoveList legal;
  generate<GenType::Legal>(pos, legal);
  int accepted = 0;
  for (std::uint32_t raw = 0; raw < 65536; ++raw) {
    Move m = Move::from_raw(static_cast<std::uint16_t>(raw));
    if (accepts(pos, m)) {
      ++accepted;
      CHECK_MSG(legal.contains(m), "accepted but not generated, " << pos.fen() << " raw " << raw);
    }
  }
  CHECK_MSG(static_cast<std::size_t>(accepted) == legal.size(), "accepted count, " << pos.fen());
}

void exhaustive_tree(Position& pos, int depth) {
  exhaustive(pos);
  if (depth == 0) return;
  MoveList legal;
  generate<GenType::Legal>(pos, legal);
  for (std::size_t i = 0; i < legal.size(); i += Optimized ? 3 : 4) {
    pos.make(legal[i]);
    exhaustive_tree(pos, depth - 1);
    pos.unmake(legal[i]);
  }
}

}  // namespace

TEST_CASE("pseudo_legal", "all 65536 encodings agree with the generator") {
  std::vector<std::string_view> fens;
  for (const PerftPosition& pp : perft_suite()) fens.push_back(pp.fen);
  for (const EdgePosition& ep : edge_positions()) fens.push_back(ep.fen);
  for (std::string_view fen : fens) {
    for (bool mirror : {false, true}) {
      Position pos;
      CHECK(pos.set_fen(fen));
      if (mirror) pos = pos.mirrored();
      exhaustive_tree(pos, Optimized ? 2 : 1);
    }
  }
}
