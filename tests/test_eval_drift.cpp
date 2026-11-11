// SPDX-License-Identifier: GPL-3.0-or-later

// The drift tables (tier 2; think tank R34 and engine survey E4;
// src/search/eval_drift.hpp): the table is bounded under any updates, a
// weighted running mean, per side and key; the material keys kept by
// advance_drift_keys equal an independent recomputation after every move of
// random games (castling, en passant, promotions and captures included);
// the threat key equals one built from per-square attack queries; and each
// table's switch changes the search's tree when on, while every switch off
// leaves it as it was.
#include <atomic>
#include <memory>
#include <vector>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "core/zobrist.hpp"
#include "harness.hpp"
#include "search/eval_drift.hpp"
#include "search/searcher.hpp"
#include "suite.hpp"

namespace forkeng::test {

namespace {

// The keys from the bitboards, by piece type and colour, not through
// DriftKeys::toggle or drift_keys.
DriftKeys keys_by_type(const Position& pos) {
  DriftKeys k;
  const auto fold = [&](Color c, PieceType t) {
    Key z = 0;
    for (Bitboard b = pos.pieces(c, t); b;) z ^= zobrist::piece_square[piece_of(c, t)][pop_lsb(b)];
    return z;
  };
  for (Color c : {White, Black}) {
    for (PieceType t : {Knight, Bishop, Rook, Queen, King}) k.pieces[c] ^= fold(c, t);
    k.minors ^= fold(c, Knight) ^ fold(c, Bishop);
    k.majors ^= fold(c, Rook) ^ fold(c, Queen);
  }
  return k;
}

// The threat key from per-square queries (attacked_by, the pawn attack
// table), hashed as threat_drift_key does.
Key threat_by_squares(const Position& pos) {
  const Color us = pos.side_to_move();
  Bitboard hit_ours = 0, hit_theirs = 0, by_pawns = 0;
  for (Square sq = 0; sq < 64; ++sq) {
    const Piece p = pos.piece_at(sq);
    if (p == NoPiece || kind_of(p) == Pawn || kind_of(p) == King) continue;
    const Color owner = side_of(p);
    if (pos.attacked_by(~owner, sq, pos.pieces())) (owner == us ? hit_ours : hit_theirs) |= bb(sq);
    if (pawn_attacks(owner, sq) & pos.pieces(~owner, Pawn)) by_pawns |= bb(sq);
  }
  return splitmix_finalize(splitmix_finalize(splitmix_finalize(hit_ours) ^ hit_theirs) ^ by_pawns);
}

// A 1 MB table of plain memory for the searches.
struct DriftHash {
  std::vector<TtBucket> buckets = std::vector<TtBucket>(16384);
  TransTable table;
  DriftHash() {
    table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  }
};

// Positions for the switch tests: the start and the ends of random games
// from it (fixed seed).
std::vector<Position> drift_positions() {
  std::vector<Position> out(1);
  std::uint64_t seed = 20261111;
  while (out.size() < 6) {
    Position pos;
    const int plies = 8 + static_cast<int>(splitmix_next(seed) % 30);
    for (int i = 0; i < plies; ++i) {
      MoveList list;
      generate<GenMode::Legal>(pos, list);
      if (list.size() == 0) break;
      pos.make(list[splitmix_next(seed) % list.size()]);
    }
    MoveList list;
    generate<GenMode::Legal>(pos, list);
    if (list.size() > 0 && !pos.in_check()) out.push_back(Position(pos));
  }
  return out;
}

// The nodes of a depth-`depth` search of every position, each from a clear
// TT and clear history (so the drift tables start empty).
std::uint64_t searched_nodes(const SearchSwitches& switches, int depth) {
  DriftHash hash;
  auto searcher = std::make_unique<Searcher>(hash.table);
  searcher->switches = switches;
  std::atomic<bool> stop{false};
  std::uint64_t nodes = 0;
  for (Position pos : drift_positions()) {
    std::fill(hash.buckets.begin(), hash.buckets.end(), TtBucket{});
    searcher->clear_history();
    SearchQuota limits;
    limits.depth = depth;
    nodes += searcher->deliberate(pos, limits, stop, nullptr, nullptr).nodes;
  }
  return nodes;
}

}  // namespace

TEST_CASE("eval_drift", "bounded by the limit under any updates") {
  auto drift = std::make_unique<EvalDrift>();
  std::uint64_t seed = 17;
  constexpr Key K = 0x9e3779b97f4a7c15ULL;
  for (int i = 0; i < 200000; ++i) {
    // Errors far past the limit, depths past the weight cap.
    const int error = static_cast<int>(splitmix_next(seed) % 60001) - 30000;
    const int depth = 1 + static_cast<int>(splitmix_next(seed) % 64);
    drift->learn(i % 2 ? White : Black, K, error, depth);
    for (Color c : {White, Black}) {
      const int v = drift->offset(c, K);
      CHECK_MSG(v >= -DriftLimit && v <= DriftLimit, "drift " << v << " after error " << error);
    }
  }
}

TEST_CASE("eval_drift", "a running mean of the errors, weighted by depth") {
  auto drift = std::make_unique<EvalDrift>();
  constexpr Key K = 0x123456789abcdef0ULL;
  CHECK_EQ(drift->offset(White, K), 0);
  // One update at depth d moves the entry d / DriftWeightTotal of the way
  // (in 1/DriftGrain cp, read toward zero).
  drift->learn(White, K, 200, 2);
  CHECK_EQ(drift->offset(White, K), 200 * DriftGrain * 2 / DriftWeightTotal / DriftGrain);
  // Repeated updates converge on the error, and from below never pass it.
  for (int i = 0; i < 5000; ++i) drift->learn(White, K, 40, 10);
  CHECK(drift->offset(White, K) >= 39 && drift->offset(White, K) <= 40);
  // Deeper results weigh more, up to the cap.
  auto shallow = std::make_unique<EvalDrift>(), deep = std::make_unique<EvalDrift>();
  shallow->learn(Black, K, 250, 1);
  deep->learn(Black, K, 250, DriftWeightCap);
  CHECK(deep->offset(Black, K) > shallow->offset(Black, K));
  // Read in whole centipawns, toward zero.
  auto small = std::make_unique<EvalDrift>();
  small->learn(White, K, -1, 1);
  CHECK_EQ(small->offset(White, K), 0);
}

TEST_CASE("eval_drift", "per side to move and per slot; clear empties it") {
  auto drift = std::make_unique<EvalDrift>();
  constexpr Key A = 0x0000000000000000ULL, B = 0xffffffffffffffffULL;
  CHECK(EvalDrift::slot(A) != EvalDrift::slot(B));
  CHECK(EvalDrift::slot(B) == DriftSlots - 1);
  for (int i = 0; i < 1000; ++i) drift->learn(White, A, 120, 8);
  CHECK(drift->offset(White, A) > 0);
  CHECK_EQ(drift->offset(Black, A), 0);
  CHECK_EQ(drift->offset(White, B), 0);
  drift->clear();
  CHECK_EQ(drift->offset(White, A), 0);
}

TEST_CASE("eval_drift", "the material keys, advanced move by move, equal a recomputation") {
  std::uint64_t seed = 20261112;
  int castles = 0, en_passants = 0, promotions = 0, captures = 0, moves = 0;
  for (int game = 0; game < 400; ++game) {
    Position pos;
    DriftKeys k = drift_keys(pos);
    CHECK(k == keys_by_type(pos));
    for (int ply = 0; ply < 300; ++ply) {
      MoveList list;
      generate<GenMode::Legal>(pos, list);
      if (list.size() == 0 || pos.fifty_move_reached() || pos.insufficient_material()) break;
      // Prefer the rare kinds when offered, so each is exercised often.
      Move m = list[splitmix_next(seed) % list.size()];
      for (Move c : list)
        if ((c.is_castle() || c.is_en_passant() || c.is_promotion()) && splitmix_next(seed) % 2) m = c;
      castles += m.is_castle();
      en_passants += m.is_en_passant();
      promotions += m.is_promotion();
      captures += m.is_capture();
      ++moves;
      advance_drift_keys(k, pos, m);
      pos.make(m);
      const DriftKeys fresh = keys_by_type(pos);
      CHECK_MSG(k == fresh, "keys after " << pos.fen());
      CHECK(drift_keys(pos) == fresh);
      if (!(k == fresh)) return;
    }
  }
  CHECK_MSG(castles > 50 && en_passants > 50 && promotions > 50 && captures > 1000,
            castles << " castles, " << en_passants << " ep, " << promotions << " promotions, " << captures
                    << " captures in " << moves << " moves");
  // The keys cover what they should: pawns never, kings only in the piece keys.
  Position start;
  const DriftKeys s = drift_keys(start);
  CHECK(s.pieces[White] != 0 && s.pieces[Black] != 0 && s.minors != 0 && s.majors != 0);
  CHECK(s.pieces[White] != s.pieces[Black]);
}

TEST_CASE("eval_drift", "the threat key equals one built from per-square attack queries") {
  std::uint64_t seed = 20261113;
  int distinct_checked = 0;
  for (int game = 0; game < 100; ++game) {
    Position pos;
    for (int ply = 0; ply < 200; ++ply) {
      MoveList list;
      generate<GenMode::Legal>(pos, list);
      if (list.size() == 0 || pos.fifty_move_reached()) break;
      CHECK_EQ(threat_drift_key(pos), threat_by_squares(pos));
      ++distinct_checked;
      pos.make(list[splitmix_next(seed) % list.size()]);
    }
  }
  CHECK(distinct_checked > 5000);
  // The key depends on the threats, not on the position as a whole: the
  // start position and one where only the kings and pawns moved share it
  // (nothing other than pawns and kings is attacked in either).
  Position a, b;
  for (const char* uci : {"e2e4", "e7e5", "e1e2", "e8e7"}) b.make(b.parse_uci(uci));
  CHECK(b.key() != a.key());
  CHECK_EQ(threat_drift_key(a), threat_drift_key(b));
}

TEST_CASE("eval_drift", "each table's switch changes the tree when on, alone") {
  // Every table off (whatever the defaults: an SPRT test build turns one
  // on); bench parity shows the defaults' search is phase-4's.
  SearchSwitches off;
  off.use_piece_drift = off.use_minor_drift = off.use_major_drift = off.use_threat_drift = false;
  constexpr int Depth = 8;
  const std::uint64_t base = searched_nodes(off, Depth);
  CHECK_EQ(searched_nodes(off, Depth), base);  // deterministic from clear tables
  for (int which = 0; which < 4; ++which) {
    SearchSwitches on = off;
    (which == 0   ? on.use_piece_drift
     : which == 1 ? on.use_minor_drift
     : which == 2 ? on.use_major_drift
                  : on.use_threat_drift) = true;
    const std::uint64_t nodes = searched_nodes(on, Depth);
    CHECK_MSG(nodes != base, "table " << which << " on: " << nodes << " nodes, as with every table off");
    CHECK_EQ(searched_nodes(on, Depth), nodes);  // deterministic: the tables start empty after clear_history
  }
}

}  // namespace forkeng::test
