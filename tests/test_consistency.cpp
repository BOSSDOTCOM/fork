// SPDX-License-Identifier: GPL-3.0-or-later

// Walks perft trees and checks internal invariants at every node against
// independent (slow, obvious) oracles.
#include <algorithm>

#include "core/movegen.hpp"
#include "harness.hpp"
#include "suite.hpp"

using namespace forkeng;
using namespace forkeng::test;

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

// Oracle for pinned pieces and discovered-check candidates: lift each piece
// of `shield_side` in turn and see whether a slider of the side opposite the
// king starts attacking the king of `king_side`.
Bitboard shields_by_removal(const Position& pos, Color king_side, Color shield_side) {
  const Square own_king = pos.king_square(king_side);
  const Bitboard occ = pos.pieces();
  const Bitboard before = slider_attackers(pos, ~king_side, own_king, occ);
  Bitboard shields = 0;
  for (Bitboard b = pos.pieces(shield_side) & ~bb(own_king); b;) {
    Square sq = pop_lsb(b);
    if (slider_attackers(pos, ~king_side, own_king, occ ^ bb(sq)) & ~before & ~bb(sq)) shields |= bb(sq);
  }
  return shields;
}

void check_state(const Position& pos, const std::string& fen) {
  // pinned and discoverers are computed on first read (audit-1, P-2): until
  // then each holds all ones; every other field is always current.
  const State& s = pos.state();
  const State fresh = pos.compute_state();
  CHECK_MSG(s.key == fresh.key, "key, " << fen);
  CHECK_MSG(s.pinned == fresh.pinned || s.pinned == ~Bitboard{0}, "pinned before reading, " << fen);
  CHECK_MSG(s.discoverers == fresh.discoverers || s.discoverers == ~Bitboard{0},
            "discoverers before reading, " << fen);
  pos.pinned();
  pos.discoverers();
  CHECK_MSG(s == fresh, "full state, " << fen);

  const Color us = pos.side_to_move(), them = ~us;
  CHECK_MSG(pos.checkers() == (pos.attackers_to(pos.king_square(us), pos.pieces()) & pos.pieces(them)),
            "checkers, " << fen);
  CHECK_MSG(pos.pinned() == shields_by_removal(pos, us, us), "pinned, " << fen);
  CHECK_MSG(pos.discoverers() == shields_by_removal(pos, them, us), "discoverers, " << fen);
}

void check_node(Position& pos, const MoveList& legal, const MoveList* parent) {
  const std::string fen = pos.fen();
  check_state(pos, fen);

  Position copy;
  std::string error;
  CHECK_MSG(copy.set_fen(fen, &error), "fen reparse, " << fen << ": " << error);
  CHECK_MSG(copy.fen() == fen && copy.key() == pos.key(), "fen round trip, " << fen);

  MoveList captures, quiets;
  generate<GenMode::Captures>(pos, captures);
  generate<GenMode::Quiets>(pos, quiets);
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
    const Key predicted_key = pos.predicted_key(m);
    pos.make(m);
    CHECK_MSG(predicted_check == pos.in_check(), "gives_check, " << fen << " " << m.raw());
    CHECK_MSG(predicted_key == pos.key(), "predicted_key, " << fen << " " << m.raw());
    pos.unmake(m);
  }
  if (!pos.in_check()) {  // the null move's key, for its TT prefetch
    const Key predicted_null = pos.predicted_null_key();
    pos.make_null();
    CHECK_MSG(predicted_null == pos.key(), "predicted_null_key, " << fen);
    pos.unmake_null();
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
  generate<GenMode::Legal>(pos, legal);
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
  generate<GenMode::Legal>(pos, legal);
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
  generate<GenMode::Legal>(pos, legal);
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
