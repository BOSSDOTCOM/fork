// SPDX-License-Identifier: GPL-3.0-or-later

// Tier 1 pruning and reductions (DESIGN.md §5.2, deliverable 6).
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <memory>
#include <vector>

#include "core/material.hpp"
#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "eval/eval.hpp"
#include "harness.hpp"
#include "search/lmr_table.hpp"
#include "search/quiet_history.hpp"
#include "search/search_bench.hpp"
#include "search/searcher.hpp"

namespace forkeng::test {

namespace {

constexpr int FutilityTestMaxDepth = 6;  // the futility depth limit in searcher.cpp

struct PruningFixture {
  std::vector<TtBucket> buckets = std::vector<TtBucket>(16384);
  TransTable table;
  std::unique_ptr<Searcher> searcher;
  std::atomic<bool> stop{false};
  PruningFixture() {
    table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
    searcher = std::make_unique<Searcher>(table);
  }
  SearchResult search(std::string_view fen, int depth) {
    std::fill(buckets.begin(), buckets.end(), TtBucket{});
    searcher->clear_history();
    Position pos;
    CHECK_MSG(pos.set_fen(fen), fen);
    SearchQuota limits;
    limits.depth = depth;
    return searcher->deliberate(pos, limits, stop, nullptr, nullptr);
  }
  // Node counts of three searches with the given switches (tests/suite.hpp's
  // perft positions 2 and 5, and the start position), for the fault checks
  // that a technique changes the search: one position alone can give the
  // same tree with and without a technique at a debug build's shallow
  // depth (S512r2 did at kiwipete, 2026-11-01), three together did not.
  std::vector<std::uint64_t> tree_sizes(const SearchSwitches& switches, int depth) {
    static constexpr std::string_view Fens[] = {
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"};
    searcher->switches = switches;
    std::vector<std::uint64_t> nodes;
    for (std::string_view fen : Fens) nodes.push_back(search(fen, depth).nodes);
    return nodes;
  }
};

}  // namespace

TEST_CASE("pruning", "LMR table: integer log shape, monotone, zero at depth or move 1, checksum pinned") {
  // fixed_log2 is floor(256 * log2(x)) or one unit below it (the repeated
  // fixed-point squaring truncates; review, deliverable 6). Compared with the
  // floating-point value in this test only (the engine uses no floating point).
  for (std::uint32_t x = 1; x < 4096; ++x) {
    const int floor_value = static_cast<int>(std::floor(256.0 * std::log2(static_cast<double>(x)) + 1e-9));
    CHECK_MSG(fixed_log2(x) == floor_value || fixed_log2(x) == floor_value - 1,
              "x " << x << ": " << fixed_log2(x) << " vs floor " << floor_value);
  }
  std::uint64_t checksum = 0;
  for (int d = 1; d < LmrMaxDepth; ++d) {
    for (int m = 1; m < LmrMaxMove; ++m) {
      const int r = reduction_for(d, m);
      if (d > 1) CHECK(r >= reduction_for(d - 1, m));
      if (m > 1) CHECK(r >= reduction_for(d, m - 1));
      // The intended shape: log2(d) * log2(m) / 4.5 rounded, or one ply less
      // where the integer logarithms land below the true value.
      const int rounded = static_cast<int>(std::lround(std::log2(d) * std::log2(m) / 4.5));
      CHECK_MSG(r == rounded || r == rounded - 1, "d " << d << " m " << m << ": " << r << " vs " << rounded);
      checksum = checksum * 31 + static_cast<std::uint64_t>(r);
    }
  }
  CHECK_EQ(reduction_for(1, 40), 0);
  CHECK_EQ(reduction_for(40, 1), 0);
  // Pinned: the table must be identical on every build (DESIGN.md §5.2,
  // determinism rule). A deliberate change updates this value.
  CHECK_EQ(checksum, std::uint64_t{12482488978459601924ULL});
}

TEST_CASE("pruning", "a side with only quiet moves is never pruned into a stalemate score") {
  // Constructed (checked with python-chess, tools/check_search_positions.py):
  // Black has only king moves and is far behind, and is neither mated nor
  // stalemated; every pruning technique is on (the defaults).
  PruningFixture fx;
  for (int depth = 1; depth <= 8; ++depth) {
    const SearchResult r = fx.search("7k/8/8/8/8/1Q6/8/1R4K1 b - - 0 1", depth);
    CHECK_MSG(!r.best.is_none(), "depth " << depth);
    CHECK_MSG(r.score < -500, "depth " << depth << ": score " << r.score);
  }
  // White to move, many quiet moves, winning: never a draw score either.
  for (int depth = 1; depth <= 8; ++depth)
    CHECK(fx.search("7k/8/8/8/8/1Q6/8/1R4K1 w - - 0 1", depth).score > 500);
}

TEST_CASE("pruning", "each technique off and all on: legal moves, mates still found") {
  PruningFixture fx;
  for (int off = -1; off < 6; ++off) {
    SearchSwitches s;
    bool* flags[] = {&s.use_rfp, &s.use_nmp, &s.use_lmr, &s.use_lmp, &s.use_futility, &s.use_see_prune};
    if (off >= 0) *flags[off] = false;
    fx.searcher->switches = s;
    // Back-rank mate in 1 and K+R v K mate in 2 (tests/test_search.cpp).
    CHECK_MSG(fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", 6).score == mate_score(1), "off " << off);
    CHECK_MSG(fx.search("k7/8/2K5/8/8/8/8/7R w - - 0 1", 6).score == mate_score(3), "off " << off);
    Position pos;
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    const SearchResult r = fx.search(Position::StartFen, 8);
    CHECK_MSG(legal.contains(r.best), "off " << off);
  }
}

// A node whose every move is prunable: Black, far behind, has only quiet
// king moves (none gives check), so at a zero window well above its eval
// futility pruning applies to all of them. The node must fail low with an
// honest score, not report a stalemate (0, a false fail high) or a score
// below any mate. Fault-injected: letting the first move be pruned and
// treating "nothing searched" as no legal move fails this.
TEST_CASE("pruning", "a node whose moves are all prunable fails low honestly, never as a stalemate") {
  PruningFixture fx;
  for (int depth = 1; depth <= FutilityTestMaxDepth; ++depth) {
    std::fill(fx.buckets.begin(), fx.buckets.end(), TtBucket{});
    Position pos;
    CHECK(pos.set_fen("7k/8/8/8/8/1Q6/8/1R4K1 b - - 0 1"));
    const int beta = -100;
    const int score = fx.searcher->probe_zero_window(pos, beta, depth, fx.stop);
    CHECK_MSG(score < beta && score > -(MateScore - MaxPly), "depth " << depth << ": score " << score);
  }
}

// Pruning must never turn a decisive position into a draw (a node whose moves
// were all pruned reported as a stalemate would). Random endgame positions
// (few pieces, many quiet moves), pruned against exact searches.
TEST_CASE("pruning", "pruned and exact searches agree in sign wherever the exact score is decisive") {
  PruningFixture fx;
  std::uint64_t seed = 20261025;
  int compared = 0;
  for (int game = 0; game < (Optimized ? 300 : 30); ++game) {
    // Random games from a fixed endgame set, a few random plies in.
    static constexpr std::string_view Starts[] = {
        "4k3/8/8/8/8/8/8/R3K2Q w - - 0 1", "4k3/pp6/8/8/8/8/6PP/R3K3 w - - 0 1",
        "1r2k3/8/8/8/8/8/8/R3K1Q1 b - - 0 1", "4k3/8/8/3q4/8/8/8/4K2R w - - 0 1"};
    Position pos;
    CHECK(pos.set_fen(Starts[game % 4]));
    for (int ply = 0; ply < 6; ++ply) {
      MoveList list;
      generate<GenMode::Legal>(pos, list);
      if (list.size() == 0) break;
      pos.make(list[splitmix_next(seed) % list.size()]);
    }
    MoveList list;
    generate<GenMode::Legal>(pos, list);
    if (list.size() == 0) continue;
    const std::string fen = pos.fen();
    fx.searcher->switches = SearchSwitches{};
    fx.searcher->switches.use_rfp = fx.searcher->switches.use_nmp = fx.searcher->switches.use_lmr = false;
    fx.searcher->switches.use_lmp = fx.searcher->switches.use_futility = fx.searcher->switches.use_see_prune =
        false;
    const int exact = fx.search(fen, 5).score;
    fx.searcher->switches = SearchSwitches{};
    const int pruned = fx.search(fen, 5).score;
    if (exact > 400) CHECK_MSG(pruned > 0, fen << ": exact " << exact << ", pruned " << pruned);
    if (exact < -400) CHECK_MSG(pruned < 0, fen << ": exact " << exact << ", pruned " << pruned);
    ++compared;
  }
  CHECK(compared > (Optimized ? 200 : 20));
}

// Searches with no depth limit, to a node budget or to the maximum depth
// (the mates iterate to MaxPly - 1), stay inside the frame arrays (the
// clang-debug preset runs this under ASan and UBSan) and return a legal
// move. Selective depth stays far below MaxPly here (about 45 plies at most,
// review); frames near MaxPly are safe by construction, since a node at
// ply >= MaxPly returns before touching frames_[ply + 1].
TEST_CASE("pruning", "searches to the maximum depth and to a node budget stay in bounds") {
  PruningFixture fx;
  // Mates (found at every depth, so iterations run to MaxPly - 1 quickly),
  // a locked pawn ending (tiny tree, deep iterations) and Kiwipete.
  static constexpr std::string_view Fens[] = {
      "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "k7/8/2K5/8/8/8/8/7R w - - 0 1",
      "4k3/8/8/1p1p1p2/1P1P1P2/8/8/4K3 w - - 0 1",
      "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"};
  for (std::string_view fen : Fens) {
    std::fill(fx.buckets.begin(), fx.buckets.end(), TtBucket{});
    fx.searcher->clear_history();
    Position pos;
    CHECK_MSG(pos.set_fen(fen), fen);
    SearchQuota limits;  // depth MaxPly - 1
    limits.nodes = Optimized ? 3'000'000 : 200'000;
    const SearchResult r = fx.searcher->deliberate(pos, limits, fx.stop, nullptr, nullptr);
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    CHECK_MSG(legal.contains(r.best), fen);
    CHECK_MSG(pos.fen() == fen, fen);
  }
}

// Review 2, claim (d) (KB T50): with the TT-refined pruning eval on (the
// default since 2026-10-26, provisionally), the search stays correct (mates
// found, a legal move) and actually changes (fault check: a refinement that
// never applies leaves the tree identical).
TEST_CASE("pruning", "TT-refined pruning eval: still correct, and it changes the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_tt_eval_refine);
  fx.searcher->switches = SearchSwitches{};
  CHECK(fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", 6).score == mate_score(1));
  CHECK(fx.search("k7/8/2K5/8/8/8/8/7R w - - 0 1", 6).score == mate_score(3));
  const std::string_view kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";
  const SearchResult refined = fx.search(kiwipete, Optimized ? 10 : 7);
  SearchSwitches off;
  off.use_tt_eval_refine = false;
  fx.searcher->switches = off;
  const SearchResult plain = fx.search(kiwipete, Optimized ? 10 : 7);
  Position pos;
  CHECK(pos.set_fen(kiwipete));  // tests/suite.hpp's perft position 2
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  CHECK(legal.contains(refined.best));
  CHECK_MSG(refined.nodes != plain.nodes, "nodes " << refined.nodes << " with and without refinement");
}

// The switches are independent (audit-1, A9-2): with PVS off, late moves were
// searched only as full-window PV children, so LMR never ran and switching it
// made no difference; a removal test of PVS would have measured LMR too.
TEST_CASE("pruning", "with PVS off, LMR still reduces: the two switches are independent") {
  PruningFixture fx;
  const std::string_view kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";
  Position pos;
  CHECK(pos.set_fen(kiwipete));  // tests/suite.hpp's perft position 2
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  const int depth = Optimized ? 7 : 5;
  SearchSwitches no_pvs;
  no_pvs.use_pvs = false;
  fx.searcher->switches = no_pvs;
  const SearchResult with_lmr = fx.search(kiwipete, depth);
  no_pvs.use_lmr = false;
  fx.searcher->switches = no_pvs;
  const SearchResult without_lmr = fx.search(kiwipete, depth);
  CHECK(legal.contains(with_lmr.best));
  CHECK(legal.contains(without_lmr.best));
  CHECK_MSG(with_lmr.nodes < without_lmr.nodes,
            "PVS off: nodes " << with_lmr.nodes << " with LMR, " << without_lmr.nodes << " without");
}

// Singular extension (tier 2, T27), then multi-cut (T28) and negative
// extensions (T30) on top: with each on, mates are still found and the best
// move is legal; searches to the maximum depth and to a node budget stay in
// bounds (KB §3.21's stress test against an extension explosion: forcing
// positions, where singular moves are common); and each switch really
// changes the tree (fault check: an outcome that never applies leaves the
// tree as it was without that switch).
TEST_CASE("pruning",
          "singular extension, multi-cut, negative extension: correct, bounded, each changes the search") {
  PruningFixture fx;
  // Singular extension and multi-cut on since their SPRTs (2026-10-31); the
  // negative extension off (its SPRT rejected it).
  CHECK(SearchSwitches{}.use_singular_extension);
  CHECK(SearchSwitches{}.use_multi_cut);
  CHECK(!SearchSwitches{}.use_negative_extension);
  static constexpr std::string_view Forcing[] = {
      "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "4k3/8/8/1p1p1p2/1P1P1P2/8/8/4K3 w - - 0 1",
      // Kiwipete (tests/suite.hpp's perft position 2) and perft position 5.
      "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
      "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8"};
  const std::string_view kiwipete = Forcing[2];
  const int depth = Optimized ? 10 : 7;
  SearchSwitches s;
  s.use_singular_extension = false;
  s.use_multi_cut = false;
  fx.searcher->switches = s;
  std::uint64_t previous = fx.search(kiwipete, depth).nodes;
  bool* added[] = {&s.use_singular_extension, &s.use_multi_cut, &s.use_negative_extension};
  for (int step = 0; step < 3; ++step) {
    *added[step] = true;
    fx.searcher->switches = s;
    CHECK_MSG(fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", 8).score == mate_score(1), "step " << step);
    CHECK_MSG(fx.search("k7/8/2K5/8/8/8/8/7R w - - 0 1", 8).score == mate_score(3), "step " << step);
    for (std::string_view fen : Forcing) {
      std::fill(fx.buckets.begin(), fx.buckets.end(), TtBucket{});
      fx.searcher->clear_history();
      Position pos;
      CHECK_MSG(pos.set_fen(fen), fen);
      SearchQuota limits;  // depth MaxPly - 1
      limits.nodes = Optimized ? 3'000'000 : 200'000;
      const SearchResult r = fx.searcher->deliberate(pos, limits, fx.stop, nullptr, nullptr);
      MoveList legal;
      generate<GenMode::Legal>(pos, legal);
      CHECK_MSG(legal.contains(r.best), fen << " step " << step);
      CHECK_MSG(pos.fen() == fen, fen);
    }
    const std::uint64_t nodes = fx.search(kiwipete, depth).nodes;
    CHECK_MSG(nodes != previous,
              "step " << step << ": nodes " << nodes << " with the switch, " << previous << " without");
    previous = nodes;
  }
}

// The reply table (tier 2, T10): with it on, mates are still found and the
// best move is legal, and it changes the tree (fault check: a table never
// read or never updated leaves the tree as it is with the switch off).
TEST_CASE("pruning", "reply and follow tables: still correct, and each changes the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_reply_history);  // on since its SPRT (2026-11-01)
  SearchSwitches on;
  on.use_reply_history = true;
  on.use_follow_history = false;
  fx.searcher->switches = on;
  CHECK(fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", 6).score == mate_score(1));
  CHECK(fx.search("k7/8/2K5/8/8/8/8/7R w - - 0 1", 6).score == mate_score(3));
  const std::string_view kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";
  const int depth = Optimized ? 10 : 7;
  Position pos;
  CHECK(pos.set_fen(kiwipete));  // tests/suite.hpp's perft position 2
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  CHECK(legal.contains(fx.search(kiwipete, depth).best));
  SearchSwitches off;
  off.use_reply_history = false;
  off.use_follow_history = false;
  const std::vector<std::uint64_t> with = fx.tree_sizes(on, depth);
  const std::vector<std::uint64_t> without = fx.tree_sizes(off, depth);
  CHECK_MSG(with != without, "the reply table left all three trees unchanged");
  // The follow table (T10's 2-ply table), on its own and with the reply table.
  CHECK(SearchSwitches{}.use_follow_history);  // on since its SPRT (2026-11-01)
  for (bool reply : {false, true}) {
    SearchSwitches follow;
    follow.use_follow_history = true;
    follow.use_reply_history = reply;
    fx.searcher->switches = follow;
    CHECK(fx.search("k7/8/2K5/8/8/8/8/7R w - - 0 1", 6).score == mate_score(3));
    CHECK(legal.contains(fx.search(kiwipete, depth).best));
    CHECK_MSG(
        fx.tree_sizes(follow, depth) != (reply ? with : without),
        "the follow table left all three trees unchanged (reply table " << (reply ? "on" : "off") << ")");
  }
}

// The take history (tier 2, T11): with it on, mates are still found and the
// best move is legal, and it changes the tree (fault check: a table never
// read or never updated leaves the tree as it is with the switch off).
TEST_CASE("pruning", "take history: still correct, and it changes the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_take_history);  // on since its SPRT (2026-11-01)
  SearchSwitches on;
  on.use_take_history = true;
  fx.searcher->switches = on;
  CHECK(fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", 6).score == mate_score(1));
  CHECK(fx.search("k7/8/2K5/8/8/8/8/7R w - - 0 1", 6).score == mate_score(3));
  const std::string_view kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";
  const int depth = Optimized ? 10 : 7;
  Position pos;
  CHECK(pos.set_fen(kiwipete));  // tests/suite.hpp's perft position 2
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  CHECK(legal.contains(fx.search(kiwipete, depth).best));
  SearchSwitches off;
  off.use_take_history = false;
  CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
            "the take history left all three trees unchanged");
}

// Internal iterative reduction (tier 2, T26): with it on, mates are still
// found and the best move is legal, and it changes the tree (fault check: a
// reduction that never fires leaves the tree as it is with the switch off).
TEST_CASE("pruning", "no-move reduction: still correct, and it changes the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_no_move_reduction);  // on since its SPRT (2026-11-02)
  SearchSwitches on;
  on.use_no_move_reduction = true;
  fx.searcher->switches = on;
  CHECK(fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", 6).score == mate_score(1));
  CHECK(fx.search("k7/8/2K5/8/8/8/8/7R w - - 0 1", 6).score == mate_score(3));
  const std::string_view kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";
  const int depth = Optimized ? 12 : 9;
  Position pos;
  CHECK(pos.set_fen(kiwipete));  // tests/suite.hpp's perft position 2
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  CHECK(legal.contains(fx.search(kiwipete, depth).best));
  SearchSwitches off;
  off.use_no_move_reduction = false;
  CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
            "the no-move reduction left all three trees unchanged");
}

// The LMR context's move facts (lmr_move_facts, the heuristic-discovery
// region's inputs, 2026-10-27): constructed positions, the expected values
// computed independently by python-chess (board.is_attacked_by before the
// move, board.attacks after it; the positions checked legal there; committed
// in tools/check_search_positions.py since audit-1 Q-11). Case 3's
// rook was attacked along the file through the square it moves to, so the
// board before the move must be rebuilt, not read after it.
TEST_CASE("pruning", "LMR move facts: piece, threatened before the move, attacks after it") {
  struct FactsCase {
    const char* fen;
    const char* move;
    int piece;
    bool threatened;
    bool attacks;
  };
  for (const FactsCase& c : {FactsCase{"4k3/8/8/3p4/4N3/8/8/4K3 w - - 0 1", "e4c3", 1, true, false},
                             FactsCase{"4k3/8/8/8/1r6/8/8/N3K3 w - - 0 1", "a1c2", 1, false, true},
                             FactsCase{"r3k3/8/8/8/8/8/8/R3K3 w - - 0 1", "a1a2", 3, true, true},
                             FactsCase{"4k3/8/8/8/8/8/8/4K3 w - - 0 1", "e1d1", 5, false, false},
                             FactsCase{"4k3/8/8/2n5/8/3P4/8/4K3 w - - 0 1", "d3d4", 0, true, true},
                             FactsCase{"4k3/8/8/8/3n4/4P3/8/4K3 b - - 0 1", "d4b5", 1, true, false},
                             FactsCase{"4k3/8/8/8/8/8/7r/4K2R w K - 0 1", "e1g1", 5, false, true}}) {
    Position pos;
    CHECK(pos.set_fen(c.fen));
    const Move m = pos.parse_uci(c.move);
    CHECK_MSG(!m.is_none(), c.fen);
    pos.make(m);
    const LmrMoveFacts f = lmr_move_facts(pos, m);
    CHECK_MSG(f.piece == c.piece, c.fen << " " << c.move << ": piece " << f.piece);
    CHECK_MSG(f.threatened == c.threatened, c.fen << " " << c.move << ": threatened " << f.threatened);
    CHECK_MSG(f.attacks == c.attacks, c.fen << " " << c.move << ": attacks " << f.attacks);
  }
}

// Audit-1 V-4 (b89185f): the LMR context's history is the mover's. The
// search builds the context after making the move, so the side to move is
// the opponent; reading its table instead passed every test (the committed
// correction is 0). One entry is set for the mover only, another for the
// opponent only, both for the same from and to squares.
TEST_CASE("pruning", "LMR context: the history read is the mover's, after the move is made") {
  for (const char* fen : {"4k3/8/8/8/8/8/8/R3K3 w - - 0 1", "r3k3/8/8/8/8/8/8/4K3 b - - 0 1"}) {
    Position pos;
    CHECK(pos.set_fen(fen));
    const Color mover = pos.side_to_move();
    const Move m = pos.parse_uci(mover == White ? "a1a2" : "a8a7");
    CHECK_MSG(!m.is_none(), fen);
    QuietHistory history;
    history.apply(mover, m, 300);
    history.apply(~mover, m, -700);
    const int mine = history.value(mover, m);
    CHECK(mine > 0 && history.value(~mover, m) < 0);
    pos.make(m);
    CHECK_MSG(mover_history(history, pos, m) == mine, fen << ": " << mover_history(history, pos, m));
  }
}

// The game phase the LMR context reads (Fork's evaluation's own, now in
// core/material.hpp unchanged): python-chess counts 24, 0 and 6 here.
TEST_CASE("pruning", "game phase: all pieces 24, a pawn ending 0, rook and queen 6") {
  Position pos;
  CHECK(pos.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"));
  CHECK_EQ(game_phase(pos), 24);
  CHECK(pos.set_fen("4k3/4p3/8/8/8/8/4P3/4K3 w - - 0 1"));
  CHECK_EQ(game_phase(pos), 0);
  CHECK(pos.set_fen("4k3/8/8/8/8/8/8/R3K2Q w - - 0 1"));
  CHECK_EQ(game_phase(pos), 6);
}

}  // namespace forkeng::test

namespace forkeng::test {

// Window-aware LMR (ideas.md idea 61 part 5): a reduced late move whose
// child's static evaluation lies within LmrWindowBand of alpha (the child's
// window_gap on its zero window) is reduced LmrWindowRelief ply less, never
// below no reduction; a mate or tablebase alpha (gap -1) never relieves.
// Fault checks (2026-11-08): with the band test widened by one centipawn,
// the gap band + 1 relieves; without both the "already unreduced" test and
// the cap at new_depth (with a one-ply relief either alone suffices), an
// unreduced move is extended; with gap -1 counted, a mate alpha relieves.
TEST_CASE("pruning", "window-aware LMR: one ply less, within the band only") {
  CHECK(!SearchSwitches{}.use_window_aware_lmr);  // off: untested (idea 61 part 5)
  CHECK_EQ(LmrWindowRelief, 1);
  const int b = LmrWindowBand;
  CHECK_EQ(window_relieved_depth(3, 6, 0), 4);
  CHECK_EQ(window_relieved_depth(3, 6, b), 4);
  CHECK_EQ(window_relieved_depth(3, 6, b + 1), 3);
  CHECK_EQ(window_relieved_depth(3, 6, -1), 3);
  CHECK_EQ(window_relieved_depth(1, 6, b), 2);
  CHECK_EQ(window_relieved_depth(5, 6, 0), 6);  // to no reduction, never beyond
  CHECK_EQ(window_relieved_depth(6, 6, 0), 6);  // nothing to relieve
  // The child's gap on its zero window [-alpha - 1, -alpha]: the distance of
  // the move's evaluation from alpha, and -1 for a mate or tablebase alpha.
  const int alpha = 40;
  CHECK_EQ(window_gap(-alpha - b, -alpha - 1, -alpha), b - 1);
  CHECK_EQ(window_gap(-alpha + b, -alpha - 1, -alpha), b);
  CHECK_EQ(window_gap(0, -mate_score(5) - 1, -mate_score(5)), -1);
  CHECK_EQ(window_gap(0, -(TbWinScore - 9) - 1, -(TbWinScore - 9)), -1);
}

// With window-aware LMR on, mates are still found, the best move is legal,
// and the tree changes (fault check: a relief that never fires leaves all
// three trees as they are with the switch off). Debug builds also check that
// every evaluation the parent lends equals the child's own (searcher.cpp;
// fault checks: a lent value one centipawn off, or a lent value not cleared
// after its move's searches, traps in the debug suites).
TEST_CASE("pruning", "window-aware LMR: still correct, and it changes the search") {
  PruningFixture fx;
  SearchSwitches on;
  on.use_window_aware_lmr = true;
  fx.searcher->switches = on;
  CHECK(fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", 6).score == mate_score(1));
  CHECK(fx.search("k7/8/2K5/8/8/8/8/7R w - - 0 1", 6).score == mate_score(3));
  const std::string_view kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";
  const int depth = Optimized ? 12 : 8;
  Position pos;
  CHECK(pos.set_fen(kiwipete));  // tests/suite.hpp's perft position 2
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  CHECK(legal.contains(fx.search(kiwipete, depth).best));
  SearchSwitches off;
  off.use_window_aware_lmr = false;
  CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
            "window-aware LMR left all three trees unchanged");
}

#ifdef FORK_TUNE
// Tuning builds: the band is a parameter, so both head-to-head candidates
// (25 and 50 cp) are testable in one binary, and it reaches the search
// (fault check: a band the gate does not read leaves the trees equal).
TEST_CASE("pruning", "window-aware LMR: the band is a tuning parameter") {
  PruningFixture fx;
  SearchSwitches on;
  on.use_window_aware_lmr = true;
  const int depth = Optimized ? 10 : 7;
  CHECK(set_param("LmrWindowBand", 25));
  const std::vector<std::uint64_t> narrow = fx.tree_sizes(on, depth);
  CHECK(set_param("LmrWindowBand", 50));
  const std::vector<std::uint64_t> wide = fx.tree_sizes(on, depth);
  CHECK(narrow != wide);
  CHECK(set_param("LmrWindowBand", find_param("LmrWindowBand")->default_value));
}
#endif

#ifdef FORK_SEARCH_STATS
// Stats builds: the window-aware LMR counters. The gate is evaluated in
// shadow with the switch off, which counts sites, gaps and gated moves and
// relieves nothing (the stats build's bench parity shows that the shadow
// leaves the tree as it is: the lent value is the child's own).
// With the switch on, every gated move is relieved (each site is a reduced
// move), and the gated count is the bins up to the band (25 or 50 cp, the
// head-to-head candidates, are both bin edges).
// The gap is measured from alpha on the right side: in positions where one
// side leads (bench positions, search_bench_fens, whose static evaluation is
// at least 300 cp either way, so alpha lies far from zero), reduced searches
// of moves near alpha beat it more often than those of moves far from it
// (fault checks: a gate whose gated count reads a wider band fails the
// counts; a gap taken against -alpha instead of alpha fails the lopsided
// positions' rates).
TEST_CASE("pruning", "window-aware LMR: the stats counters") {
  PruningFixture fx;
  const int depth = Optimized ? 10 : 7;
  int band_bin = -1;  // the bin whose upper edge is the band
  for (int i = 0; i < 4; ++i)
    if (SearchCounters::LmrWindowBinEdges[i] == LmrWindowBand) band_bin = i;
  CHECK_MSG(band_bin >= 0, LmrWindowBand);
  for (const bool on : {false, true}) {
    SearchSwitches s;
    s.use_window_aware_lmr = on;
    fx.searcher->counters = SearchCounters{};
    fx.tree_sizes(s, depth);
    const SearchCounters c = fx.searcher->counters;
    std::uint64_t binned = 0;
    for (const std::uint64_t n : c.lmr_window_gap_bins) binned += n;
    CHECK_EQ(binned, c.lmr_window_sites);
    CHECK(c.lmr_window_sites > 0 && c.lmr_window_reused > 0 && c.lmr_window_reused < c.lmr_window_sites);
    CHECK(c.lmr_window_gated > 0);
    std::uint64_t within = 0;
    for (int i = 0; i <= band_bin; ++i) within += c.lmr_window_gap_bins[i];
    CHECK_EQ(c.lmr_window_gated, within);
    CHECK_EQ(c.lmr_window_relieved, on ? c.lmr_window_gated : 0u);
    for (int i = 0; i < SearchCounters::LmrWindowBins; ++i)
      CHECK(c.lmr_window_research_bins[i] <= c.lmr_window_gap_bins[i]);
    const auto rate = [&](int i) {
      return static_cast<double>(c.lmr_window_research_bins[i]) / static_cast<double>(c.lmr_window_gap_bins[i]);
    };
    CHECK(c.lmr_window_gap_bins[0] > 0 && c.lmr_window_gap_bins[4] > 0);
    CHECK_MSG(rate(0) > 2 * rate(4), "near alpha " << rate(0) << ", beyond 100 cp " << rate(4));
  }
  fx.searcher->switches = SearchSwitches{};
  fx.searcher->counters = SearchCounters{};
  int lopsided = 0;
  for (std::string_view fen : search_bench_fens()) {
    Position pos;
    CHECK_MSG(pos.set_fen(fen), fen);
    if (pos.in_check() || std::abs(static_eval(pos)) < 300) continue;
    ++lopsided;
    fx.search(fen, depth);
  }
  CHECK_MSG(lopsided >= 5, lopsided);
  const SearchCounters u = fx.searcher->counters;
  CHECK(u.lmr_window_gap_bins[0] > 0 && u.lmr_window_gap_bins[4] > 0);
  const double near = static_cast<double>(u.lmr_window_research_bins[0]) / static_cast<double>(u.lmr_window_gap_bins[0]);
  const double far = static_cast<double>(u.lmr_window_research_bins[4]) / static_cast<double>(u.lmr_window_gap_bins[4]);
  CHECK_MSG(near > 2 * far, lopsided << " lopsided positions: near alpha " << near << ", beyond 100 cp " << far);
}
#endif

// Every tier-2 switch on (from the tier-2 review of 2026-10-31): a search
// from the same state twice is identical, and the best move is legal.
TEST_CASE("pruning", "tier 2, all switches on: deterministic and legal") {
  PruningFixture fx;
  SearchSwitches s;
  s.use_singular_extension = s.use_multi_cut = s.use_negative_extension = true;
  s.use_reply_history = s.use_follow_history = s.use_take_history = s.use_no_move_reduction = true;
  s.use_window_aware_lmr = true;
  fx.searcher->switches = s;
  static constexpr std::string_view Fens[] = {
      "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
      "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"};
  const int depth = Optimized ? 12 : 7;
  for (std::string_view fen : Fens) {
    const SearchResult a = fx.search(fen, depth);
    const SearchResult b = fx.search(fen, depth);
    CHECK_MSG(a.nodes == b.nodes && a.best == b.best && a.score == b.score,
              fen << ": nodes " << a.nodes << " vs " << b.nodes);
    Position pos;
    CHECK(pos.set_fen(fen));
    MoveList legal;
    generate<GenMode::Legal>(pos, legal);
    CHECK_MSG(legal.contains(a.best), fen);
  }
}

}  // namespace forkeng::test
