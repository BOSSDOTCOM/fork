// Walks perft trees and checks internal invariants at every node.
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

void check_node(const Position& pos, const MoveList& legal, const MoveList* parent) {
  const std::string fen = pos.fen();
  CHECK_MSG(pos.key() == pos.compute_key(), "incremental key, " << fen);
  Color us = pos.side_to_move();
  CHECK_MSG(pos.checkers() == (pos.attackers_to(pos.king_square(us), pos.pieces()) & pos.pieces(~us)),
            "checkers, " << fen);

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
    CHECK(pos.key() == pos.compute_key());
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
  // Ep evasion of a pawn check, ep discovered-check pins, promotions with
  // capture, castling through attacked squares, double check.
  const char* fens[] = {
      "8/8/8/2k5/3Pp3/8/8/4K3 b - d3 0 1",
      "8/8/8/KPp4r/8/8/8/7k w - c6 0 1",
      "1b5k/8/8/3pP3/8/8/7K/8 w - d6 0 1",
      "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
      "r3k2r/8/8/8/8/8/5q2/R3K2R w KQkq - 0 1",
      "1r2k2r/8/8/8/8/8/8/R3K1R1 b Qk - 0 1",
      "4k3/8/8/8/8/8/1p4p1/R3K2R b KQ - 0 1",
      "4k3/8/8/8/1b6/8/8/r3K2R w K - 0 1",
      "4k3/8/5n2/8/8/8/4r3/4K3 w - - 0 1",
      "n1n5/PPPk4/8/8/8/8/4Kppp/5N1N b - - 0 1",
  };
  for (const char* fen : fens) {
    Position pos;
    std::string error;
    CHECK_MSG(pos.set_fen(fen, &error), fen << ": " << error);
    walk(pos, Optimized ? 3 : 2, nullptr);
  }
}
