// SPDX-License-Identifier: GPL-3.0-or-later

// Tier 1 pruning and reductions (DESIGN.md §5.2, deliverable 6).
#include <atomic>
#include <cmath>
#include <cstdint>
#include <memory>
#include <vector>

#include "core/material.hpp"
#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "eval/eval.hpp"
#include "harness.hpp"
#include "search/lmr_table.hpp"
#include "search/quiet_history.hpp"
#include "search/searcher.hpp"
#include "suite.hpp"

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

// The tables the search reads at startup, before any setoption, are the ones
// the parameters give. In a tuning build they are dynamically initialised
// variables; the LLVM-MinGW clang tuning build once filled the 64ths table
// from a whole-ply table that was still all zeros (every fine entry 31, so
// round-once LMR never reduced; bench 14,927,773 for 6,064,962) until a
// setoption rebuilt them. This suite runs in its own process and sets no
// parameter, so it sees the startup state.
TEST_CASE("pruning", "LMR tables at startup equal freshly built ones (static initialisation order)") {
  const LmrTable whole = make_lmr_table(LmrDivisorTenths);
  const LmrSixtyFourths fine = make_lmr_sixty_fourths(LmrDivisorTenths, whole);
  int whole_differ = 0, fine_differ = 0;
  for (int d = 0; d < LmrMaxDepth; ++d)
    for (int m = 0; m < LmrMaxMove; ++m) {
      whole_differ += LmrPlies.plies[d][m] != whole.plies[d][m];
      fine_differ += LmrFine.fine[d][m] != fine.fine[d][m];
    }
  CHECK_MSG(whole_differ == 0, whole_differ << " whole-ply entries differ");
  CHECK_MSG(fine_differ == 0, fine_differ << " 64ths entries differ, e.g. (20, 20): " << LmrFine.fine[20][20]
                                          << " for " << fine.fine[20][20]);
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
  // The tree check below was set on trees without root reductions (they did
  // not exist yet); with them on, the debug build's three depth-9 trees come
  // out the same with the reduction on and off (2026-11-13; the release
  // build's depth-12 trees still differ), so the case pins them off: it tests
  // the reduction on the trees it was built for.
  SearchSwitches on;
  on.use_no_move_reduction = true;
  on.use_root_lmr = false;
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
  off.use_root_lmr = false;
  CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
            "the no-move reduction left all three trees unchanged");
}

// Node types and their LMR use, the cut-node reduction (tier 2, T17): with
// it on, mates are still found and the best move is legal, and it changes
// the tree (fault check: an expected type never set, or a reduction never
// applied, leaves the tree as it is with the switch off).
TEST_CASE("pruning", "cut-node reduction: still correct, and it changes the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_cut_node_lmr);  // on since its SPRTs (2026-11-11)
  SearchSwitches on;
  on.use_cut_node_lmr = true;
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
  off.use_cut_node_lmr = false;
  CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
            "the cut-node reduction left all three trees unchanged");
}

// The threat buckets of the butterfly history (tier 2, T56): with them on,
// mates are still found and the best move is legal, and they change the
// tree (fault check: a threat set never built, or buckets never read,
// leaves the tree as it is with the switch off).
TEST_CASE("pruning", "threat buckets: still correct, and they change the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_threat_buckets);  // on since its SPRTs (2026-11-11)
  SearchSwitches on;
  on.use_threat_buckets = true;
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
  off.use_threat_buckets = false;
  CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
            "the threat buckets left all three trees unchanged");
  // The search updates the bucket it reads: with the switch on its cutoffs
  // write every bucket (an update left in bucket 0 would leave buckets 1-3
  // empty while the selector and LMR read them); off, only bucket 0.
  const auto written = [&](int bucket) {
    int n = 0;
    for (Color side : {White, Black})
      for (Square from = 0; from < 64; ++from)
        for (Square to = 0; to < 64; ++to)
          n += fx.searcher->butterfly_view().value(side, Move(from, to, 0), bucket) != 0;
    return n;
  };
  fx.searcher->switches = on;
  fx.search(kiwipete, depth);
  for (int b = 0; b < ThreatBuckets; ++b) CHECK_MSG(written(b) > 0, "bucket " << b);
  fx.searcher->switches = off;
  fx.search(kiwipete, depth);
  CHECK(written(0) > 0);
  for (int b = 1; b < ThreatBuckets; ++b) CHECK_MSG(written(b) == 0, "bucket " << b);
}

// ProbCut, the capture probe (tier 2, T31): with it on, mates are still
// found and the best move is legal, and it changes the tree (fault check: a
// probe that never cuts leaves the tree as it is with the switch off). Deep
// enough that non-PV nodes reach its minimum depth in a debug build too: the
// root's children are searched one ply shallower than the root, so the
// depth is tied to CaptureProbeMinDepth and stays above it. A fixed debug
// depth of 9, written when the minimum depth was 6, ran no probe at all once
// the measured minimum depth 9 replaced it (5c9e755), so the trees were equal.
TEST_CASE("pruning", "capture probe: still correct, and it changes the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_capture_probe);  // on since its LTC SPRT passed
  SearchSwitches on;
  on.use_capture_probe = true;
  fx.searcher->switches = on;
  CHECK(fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", 8).score == mate_score(1));
  CHECK(fx.search("k7/8/2K5/8/8/8/8/7R w - - 0 1", 8).score == mate_score(3));
  const std::string_view kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";
  const int depth = CaptureProbeMinDepth + (Optimized ? 3 : 1);  // 12 and 10 at the default 9
  Position pos;
  CHECK(pos.set_fen(kiwipete));  // tests/suite.hpp's perft position 2
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  CHECK(legal.contains(fx.search(kiwipete, depth).best));
  SearchSwitches off;
  off.use_capture_probe = false;
  CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
            "the capture probe left all three trees unchanged");
}

// The capture probe's cut itself, which the tree test above cannot see (the
// probe's own searches change the tree even if it never cuts). White's rook
// can take the undefended queen, with two pawns each left on the board
// (constructed; checked by tools/check_search_positions.py). A zero-window
// search at the probe's minimum depth (above RFP's depth limit; the no-move
// reduction switched off in both arms, so the node keeps that depth) with
// beta one above White's static eval, so the null move does not apply and
// the queen's capture (SEE 900) passes the probe's SEE filter, stores the
// node at the probe's depth, the depth less CaptureProbeReduction, as a lower
// bound with the capture as its move; without the probe, at the node's own
// depth.
// Without the pawns S512r2 scored the bare rook ending after the capture at
// about 0 cp, below the bar, and the probe rightly let the node be searched.
TEST_CASE("pruning", "capture probe: a winning capture cuts the node at the probe's depth") {
  for (bool probe : {false, true}) {
    PruningFixture fx;
    SearchSwitches s;
    s.use_capture_probe = probe;
    s.use_no_move_reduction = false;
    fx.searcher->switches = s;
    Position pos;
    CHECK(pos.set_fen("4k3/pp6/8/3q4/8/8/PP1R4/4K3 w - - 0 1"));
    const int beta = static_eval(pos) + 1;
    const int depth = CaptureProbeMinDepth;
    const int score = fx.searcher->probe_zero_window(pos, beta, depth, fx.stop);
    CHECK_MSG(score >= beta, "probe " << probe << ": beta " << beta << ", score " << score);
    TtHit hit{};
    CHECK(fx.table.fetch(pos.key(), hit));
    CHECK_MSG(hit.depth == (probe ? depth - CaptureProbeReduction : depth),
              "probe " << probe << ": depth " << hit.depth);
    if (probe) CHECK(hit.move == pos.parse_uci("d2d5") && hit.bound == TtBound::Lower);
  }
}

// Quiet history pruning, the history skip (tier 2, T24): with it on, mates
// are still found and the best move is legal, and it changes the search
// (fault check: a skip never taken leaves the nodes as with the switch off).
// The skip needs history that has grown over a game (a cleared searcher's
// scores at the skip's sites stay within a few hundred of zero: the
// measurement, tools/tier2_measure/history_skip.json), so the change is
// checked on a 24-ply game from perft position 3 at depth 10, history
// carried, in optimized builds only (too slow under the sanitizers).
TEST_CASE("pruning", "history skip: still correct, and it changes the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_history_skip);  // on since its STC SPRT passed
  SearchSwitches on;
  on.use_history_skip = true;
  fx.searcher->switches = on;
  CHECK(fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", 6).score == mate_score(1));
  CHECK(fx.search("k7/8/2K5/8/8/8/8/7R w - - 0 1", 6).score == mate_score(3));
  const std::string_view kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";
  Position pos;
  CHECK(pos.set_fen(kiwipete));  // tests/suite.hpp's perft position 2
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  CHECK(legal.contains(fx.search(kiwipete, Optimized ? 10 : 7).best));
  if (!Optimized) return;
  // Total nodes of the game's searches, each move legal.
  const auto game_nodes = [&fx](bool skip) {
    std::fill(fx.buckets.begin(), fx.buckets.end(), TtBucket{});
    fx.searcher->clear_history();
    fx.searcher->switches.use_history_skip = skip;
    Position game;
    CHECK(game.set_fen(perft_suite()[2].fen));  // perft position 3
    SearchQuota limits;
    limits.depth = 10;
    std::uint64_t nodes = 0;
    for (int ply = 0; ply < 24; ++ply) {
      MoveList moves;
      generate<GenMode::Legal>(game, moves);
      if (moves.size() == 0) break;
      const SearchResult r = fx.searcher->deliberate(game, limits, fx.stop, nullptr, nullptr);
      CHECK(moves.contains(r.best));
      nodes += r.nodes;
      game.make(r.best);
    }
    return nodes;
  };
  CHECK_MSG(game_nodes(true) != game_nodes(false), "the history skip left the game's searches unchanged");
}

// The summed-base pair-table update (the engine survey's D8): with it on,
// mates are still found and the best move is legal, and it changes the tree
// (fault check: an update that still read each entry alone leaves the tree
// as it is with the switch off). With the reply table off only the follow
// table is updated, by its own entry, so the tree equals the switch off.
TEST_CASE("pruning", "summed pair update: still correct, and it changes the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_pair_sum_update);  // on since its STC SPRT passed
  SearchSwitches on;
  on.use_pair_sum_update = true;
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
  off.use_pair_sum_update = false;
  CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
            "the summed pair update left all three trees unchanged");
  SearchSwitches follow_only_on = on, follow_only_off = off;
  follow_only_on.use_reply_history = follow_only_off.use_reply_history = false;
  CHECK(fx.tree_sizes(follow_only_on, depth) == fx.tree_sizes(follow_only_off, depth));
}

// The direct-check ordering bonus (the engine survey's D13): with it on,
// mates are still found and the best move is legal, and it changes the tree
// (fault check: a bonus never passed to the selector leaves the tree as it is
// with the switch off).
TEST_CASE("pruning", "direct-check bonus: still correct, and it changes the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_check_order_bonus);  // on since its STC SPRT passed
  SearchSwitches on;
  on.use_check_order_bonus = true;
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
  off.use_check_order_bonus = false;
  CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
            "the direct-check bonus left all three trees unchanged");
}

// The history skip's exemption for checking quiets (use_skip_check_exempt):
// the only mate, Ra1-a8 (a quiet direct check), is given the worst butterfly
// history in every threat bucket (-HistoryMax, far below the skip's
// threshold at depths 1 to HistorySkipMaxDepth), so it is ordered after the
// other quiets and the skip drops it unless the exemption is on. A
// zero-window probe of the root (a non-PV node) at beta = mate in 1 finds
// the mate at each of those depths with the exemption and fails low without
// it (fault check: an exemption that never applies fails the first case).
// Late move pruning and futility pruning are off so that only the skip can
// drop the move. The position is the mate-in-1 case above.
TEST_CASE("pruning", "history skip: a quiet direct check with bad history is exempt only with the switch") {
  CHECK(SearchSwitches{}.use_skip_check_exempt);  // on since its SPRT
  PruningFixture fx;
  const std::string_view fen = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1";
  const auto probe = [&](bool exempt, int depth) {
    std::fill(fx.buckets.begin(), fx.buckets.end(), TtBucket{});
    fx.searcher->clear_history();
    SearchSwitches s;
    s.use_lmp = s.use_futility = false;
    s.use_history_skip = true;
    s.use_skip_check_exempt = exempt;
    fx.searcher->switches = s;
    Position pos;
    CHECK(pos.set_fen(fen));
    const Move mate = pos.parse_uci("a1a8");
    CHECK(!mate.is_none() && !mate.is_capture() && gives_direct_check(pos, mate));
    for (int b = 0; b < ThreatBuckets; ++b) fx.searcher->butterfly_edit().apply(White, mate, -HistoryMax, b);
    CHECK(fx.searcher->butterfly_view().value(White, mate, 0) <= -HistorySkipPerPly * HistorySkipMaxDepth);
    return fx.searcher->probe_zero_window(pos, mate_score(1), depth, fx.stop);
  };
  for (int depth = 1; depth <= HistorySkipMaxDepth; ++depth) {
    CHECK_MSG(probe(true, depth) >= mate_score(1), "depth " << depth << ": the exempt check was skipped");
    CHECK_MSG(probe(false, depth) < mate_score(1), "depth " << depth << ": the check was not skipped");
  }
}

// History ageing between searches (the engine survey's D17): with the switch
// on, a second search after a first one, the histories not cleared between
// them, still finds mates and plays a legal move, and differs from the same
// pair of searches with the switch off (fault check: ageing never called
// leaves it the same). A search after clear_history() is unchanged: ageing an
// empty table changes nothing.
TEST_CASE("pruning", "history ageing: still correct, and it changes a second search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_history_ageing);  // on since its SPRT
  const std::string_view kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";
  const int depth = Optimized ? 10 : 7;
  // Two searches in a row on one history (the TT cleared before each, so
  // only the history carries over); returns the second's result.
  const auto second = [&](const SearchSwitches& s) {
    fx.searcher->switches = s;
    std::fill(fx.buckets.begin(), fx.buckets.end(), TtBucket{});
    fx.searcher->clear_history();
    Position pos;
    CHECK(pos.set_fen(kiwipete));
    SearchQuota limits;
    limits.depth = depth;
    fx.searcher->deliberate(pos, limits, fx.stop, nullptr, nullptr);
    std::fill(fx.buckets.begin(), fx.buckets.end(), TtBucket{});
    const Move next = pos.parse_uci("d5e6");  // the same game's next position
    CHECK(!next.is_none());
    pos.make(next);
    return fx.searcher->deliberate(pos, limits, fx.stop, nullptr, nullptr);
  };
  SearchSwitches on, off;
  on.use_history_ageing = true;
  off.use_history_ageing = false;  // explicitly off: it is on by default
  const SearchResult a = second(on), b = second(off);
  Position pos;
  CHECK(pos.set_fen(kiwipete));  // tests/suite.hpp's perft position 2
  pos.make(pos.parse_uci("d5e6"));
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  CHECK(legal.contains(a.best));
  CHECK_MSG(a.nodes != b.nodes, "history ageing left the second search unchanged: " << a.nodes);
  fx.searcher->switches = on;
  CHECK(fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", 6).score == mate_score(1));
  CHECK(fx.search("k7/8/2K5/8/8/8/8/7R w - - 0 1", 6).score == mate_score(3));
  // After clear_history() the first search is the same as with the switch off.
  CHECK(fx.tree_sizes(on, depth) == fx.tree_sizes(off, depth));
}

// The improving flag in late move pruning and LMR (the engine survey's B9,
// think tank R17): each switch on alone still finds mates and plays a legal
// move, and changes the search (fault check: the flag never set, or its
// term never applied, leaves the tree as it is with the switch off). Each
// does nothing with the technique it adjusts switched off.
TEST_CASE("pruning", "improving flag in LMP and LMR: still correct, and each changes the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_improving_lmp);  // on since its SPRT
  CHECK(SearchSwitches{}.use_improving_lmr);  // on since its SPRT
  const std::string_view kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";
  const int depth = Optimized ? 10 : 7;
  Position pos;
  CHECK(pos.set_fen(kiwipete));  // tests/suite.hpp's perft position 2
  MoveList legal;
  generate<GenMode::Legal>(pos, legal);
  SearchSwitches off;  // explicitly off: both uses are on by default
  off.use_improving_lmp = off.use_improving_lmr = false;
  for (int which = 0; which < 2; ++which) {
    SearchSwitches on = off;
    bool* flags[] = {&on.use_improving_lmp, &on.use_improving_lmr};
    *flags[which] = true;
    fx.searcher->switches = on;
    CHECK_MSG(fx.search("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", 6).score == mate_score(1), "switch " << which);
    CHECK_MSG(fx.search("k7/8/2K5/8/8/8/8/7R w - - 0 1", 6).score == mate_score(3), "switch " << which);
    CHECK_MSG(legal.contains(fx.search(kiwipete, depth).best), "switch " << which);
    CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
              "improving switch " << which << " left all three trees unchanged");
  }
  SearchSwitches lmp_on = off, lmp_off = off;
  lmp_on.use_improving_lmp = true;
  lmp_on.use_lmp = lmp_off.use_lmp = false;
  CHECK(fx.tree_sizes(lmp_on, depth) == fx.tree_sizes(lmp_off, depth));
  SearchSwitches lmr_on = off, lmr_off = off;
  lmr_on.use_improving_lmr = true;
  lmr_on.use_lmr = lmr_off.use_lmr = false;
  CHECK(fx.tree_sizes(lmr_on, depth) == fx.tree_sizes(lmr_off, depth));
}

// Round-once LMR (think tank R20): the table in 64ths of a ply rounds back
// to the whole-ply table at every entry, with any whole number of plies
// added (so with no sub-ply term the search is unchanged); each entry lies
// within half a ply of the whole one and within a ply of the real-valued
// shape; the history term and the running centre by hand.
TEST_CASE("pruning", "round-once LMR: 64ths round back to the whole-ply table, the term and centre by hand") {
  for (int d = 1; d < LmrMaxDepth; ++d)
    for (int m = 1; m < LmrMaxMove; ++m) {
      const int fine = reduction_sixty_fourths(d, m), whole = reduction_for(d, m);
      CHECK_MSG(fine >= 64 * whole - 32 && fine <= 64 * whole + 31, "d " << d << " m " << m << ": " << fine);
      const double shape = std::log2(d) * std::log2(m) / 4.5;
      CHECK_MSG(std::fabs(fine / 64.0 - shape) < 1.0, "d " << d << " m " << m << ": " << fine);
      for (int k = -4; k <= 4; ++k)
        CHECK_MSG(round_sixty_fourths(fine + 64 * k) == whole + k, "d " << d << " m " << m << " k " << k);
    }
  // Out-of-range arguments are clamped as reduction_for clamps them.
  CHECK_EQ(reduction_sixty_fourths(200, 200), reduction_sixty_fourths(LmrMaxDepth - 1, LmrMaxMove - 1));
  CHECK_EQ(reduction_sixty_fourths(0, 0), 0);
  // The term: -centred * 64 / per_ply, truncated toward zero.
  CHECK_EQ(history_sixty_fourths(0, 10000), 0);
  CHECK_EQ(history_sixty_fourths(10000, 10000), -64);
  CHECK_EQ(history_sixty_fourths(-5000, 10000), 32);
  CHECK_EQ(history_sixty_fourths(156, 10000), 0);   // -0.998: under a 64th
  CHECK_EQ(history_sixty_fourths(-157, 10000), 1);  // +1.005
  CHECK_EQ(history_sixty_fourths(30000, 5000), -384);
  // The centre: 0 at the start, then it follows a steady input (an
  // exponential average: within 1% after 5 x 1024 values from 0), both signs.
  HistoryCentre c;
  CHECK_EQ(c.centre(), 0);
  for (int i = 0; i < 5 * 1024; ++i) c.add(4000);
  CHECK_MSG(c.centre() >= 3960 && c.centre() <= 4000, c.centre());
  for (int i = 0; i < 8 * 1024; ++i) c.add(-2500);  // from about 4,000: within 0.1 cp per cp of the step
  CHECK_MSG(c.centre() >= -2505 && c.centre() <= -2495, c.centre());
  for (int i = 0; i < 20 * 1024; ++i) c.add(i % 2 ? HistoryMax : -HistoryMax);
  CHECK_MSG(c.centre() >= -HistoryMax && c.centre() <= HistoryMax, c.centre());
}

// The centred LMR history term (R20): with it on, mates are still found and
// the best move is legal, and it changes the tree (fault check: a term that
// is always 0 leaves the tree as it is with the switch off). With every
// history table left at zero (use_history off: no cutoff updates them) the
// term is 0 and the round-once arithmetic gives the switch-off tree exactly
// (B9's not-improving plies on in both: a whole-ply term in the 64ths sum).
TEST_CASE("pruning", "centred LMR history: still correct, changes the search, round-once alone does not") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_centred_lmr_history);  // on since its SPRTs
  // The tree check below was set on trees without root reductions (adopted
  // after R20); with them on, the debug build's three depth-7 trees come out
  // the same with the term on and off (2026-11-13; the release build's
  // depth-10 trees still differ), so the case pins them off: it tests the
  // term on the trees it was built for.
  SearchSwitches on;
  on.use_centred_lmr_history = true;
  on.use_root_lmr = false;
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
  off.use_centred_lmr_history = false;
  off.use_root_lmr = false;
  CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
            "the centred LMR history term left all three trees unchanged");
  SearchSwitches no_history_on = on, no_history_off = off;
  no_history_on.use_history = no_history_off.use_history = false;
  CHECK(fx.tree_sizes(no_history_on, depth) == fx.tree_sizes(no_history_off, depth));
}

// The linear history bonus (R15, D11): with it on, mates are still found
// and the best move is legal, and it changes the tree (fault check: the
// quadratic bonus kept leaves the tree as it is with the switch off); with
// use_history off it does nothing (only the take history reads the bonus
// then, so that is off too).
TEST_CASE("pruning", "linear history bonus: still correct, and it changes the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_linear_bonus);  // on since its SPRT
  SearchSwitches on;
  on.use_linear_bonus = true;
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
  off.use_linear_bonus = false;  // explicitly off: it is on by default
  CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
            "the linear bonus left all three trees unchanged");
  SearchSwitches no_history_on = on, no_history_off = off;
  no_history_on.use_history = no_history_off.use_history = false;
  no_history_on.use_take_history = no_history_off.use_take_history = false;
  CHECK(fx.tree_sizes(no_history_on, depth) == fx.tree_sizes(no_history_off, depth));
}

// The quiescence move cap (the engine survey's B16): with it on, mates are
// still found and the best move is legal, and it changes the tree (fault
// check: a cap that never fires leaves the trees as with the switch off);
// with the quiescence search off it does nothing.
TEST_CASE("pruning", "quiescence move cap: still correct, and it changes the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_quiesce_move_cap);  // on since its SPRT
  SearchSwitches on;
  on.use_quiesce_move_cap = true;
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
  off.use_quiesce_move_cap = false;  // explicitly off: it is on by default
  CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
            "the quiescence move cap left all three trees unchanged");
  SearchSwitches no_quiesce_on = on, no_quiesce_off = off;
  no_quiesce_on.use_quiesce = no_quiesce_off.use_quiesce = false;
  CHECK(fx.tree_sizes(no_quiesce_on, depth) == fx.tree_sizes(no_quiesce_off, depth));
}

// Root reductions (bug review 2026-11-11 §3): with them on, mates are still
// found and the best move is legal, and they change the tree (fault check: a
// root reduction that never fires leaves the trees as with the switch off);
// with LMR off they do nothing.
TEST_CASE("pruning", "root reductions: still correct, and they change the search") {
  PruningFixture fx;
  CHECK(SearchSwitches{}.use_root_lmr);  // on since its SPRTs
  SearchSwitches on;
  on.use_root_lmr = true;
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
  off.use_root_lmr = false;  // explicitly off: it is on by default
  CHECK_MSG(fx.tree_sizes(on, depth) != fx.tree_sizes(off, depth),
            "root reductions left all three trees unchanged");
  SearchSwitches no_lmr_on = on, no_lmr_off = off;
  no_lmr_on.use_lmr = no_lmr_off.use_lmr = false;
  CHECK(fx.tree_sizes(no_lmr_on, depth) == fx.tree_sizes(no_lmr_off, depth));
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

// Every tier-2 switch on (from the tier-2 review of 2026-10-31): a search
// from the same state twice is identical, and the best move is legal.
TEST_CASE("pruning", "tier 2, all switches on: deterministic and legal") {
  PruningFixture fx;
  SearchSwitches s;
  s.use_singular_extension = s.use_multi_cut = s.use_negative_extension = true;
  s.use_reply_history = s.use_follow_history = s.use_take_history = s.use_no_move_reduction = true;
  s.use_threat_buckets = s.use_capture_probe = true;
  s.use_piece_drift = s.use_minor_drift = s.use_major_drift = s.use_threat_drift = true;
  s.use_pair_sum_update = s.use_check_order_bonus = s.use_skip_check_exempt = true;
  s.use_history_ageing = s.use_improving_lmp = s.use_improving_lmr = true;
  s.use_centred_lmr_history = s.use_linear_bonus = s.use_quiesce_move_cap = true;
  s.use_root_lmr = true;
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

// X2's histogram bins and the LMR history probe (DESIGN.md §5.7): the bins
// cover their ranges, never go down, and split exactly at multiples of the
// width in |v|, so the bins at or beyond 24,000 count exactly the values
// with |s| >= 24,000 (the oracle: a direct count over every int16 value).
TEST_CASE("pruning", "X2 histogram bins and the LMR history probe shift") {
  int previous = -1;
  for (int v = -HistoryMax; v <= HistoryMax; ++v) {
    const int b = table_value_bin(v);
    CHECK(b >= 0 && b < TableBins && b >= previous);
    previous = b;
  }
  CHECK_EQ(table_value_bin(-HistoryMax), 0);
  CHECK_EQ(table_value_bin(HistoryMax), TableBins - 1);
  CHECK_EQ(table_value_bin(0), TableBins / 2);
  CHECK_EQ(table_value_bin(-1), TableBins / 2 - 1);
  CHECK_EQ(table_value_bin(249), TableBins / 2);
  CHECK_EQ(table_value_bin(250), TableBins / 2 + 1);
  CHECK_EQ(table_value_bin(-250), TableBins / 2 - 2);
  std::vector<std::uint64_t> bins(OrderBins);
  std::uint64_t direct = 0;
  previous = -1;
  for (int s = -INT16_MAX; s <= INT16_MAX; ++s) {
    const int b = order_score_bin(s);
    CHECK(b >= 0 && b < OrderBins && b >= previous);
    previous = b;
    ++bins[b];
    direct += s >= 24000 || s <= -24000;
  }
  std::uint64_t from_bins = 0;
  for (int b = 0; b < OrderBins; ++b)
    if (b >= order_score_bin(24000) || b <= order_score_bin(-24000)) from_bins += bins[b];
  CHECK_EQ(from_bins, direct);
  CHECK_EQ(order_score_bin(0), OrderBins / 2);
  CHECK_EQ(order_score_bin(499), OrderBins / 2);
  CHECK_EQ(order_score_bin(500), OrderBins / 2 + 1);
  CHECK_EQ(order_score_bin(-499), OrderBins / 2 - 1);
  CHECK_EQ(order_score_bin(-500), OrderBins / 2 - 2);
  CHECK(order_score_bin(23999) != order_score_bin(24000));
  CHECK(order_score_bin(-23999) != order_score_bin(-24000));
  CHECK_EQ(order_score_bin(-INT16_MAX), 0);
  CHECK_EQ(order_score_bin(INT16_MAX), OrderBins - 1);
  CHECK_EQ(lmr_history_probe_shift(23999), 0);
  CHECK_EQ(lmr_history_probe_shift(24000), 1);
  CHECK_EQ(lmr_history_probe_shift(-23999), 0);
  CHECK_EQ(lmr_history_probe_shift(-24000), -1);
  CHECK_EQ(lmr_history_probe_shift(INT16_MAX), 1);
}

// The history skip's measurement bins (T24): monotone over every int16
// value, and for every threshold -100j the bins at or below
// skip_score_bin(-100j) count exactly the values at or below it (the
// oracle: a direct count), as tools/tier2_measure/history_skip_rates.py
// reads them.
TEST_CASE("pruning", "history skip measurement bins split exactly at multiples of 100") {
  std::vector<std::uint64_t> bins(SkipBins, 0);
  int previous = -1;
  for (int s = -INT16_MAX; s <= INT16_MAX; ++s) {
    const int b = skip_score_bin(s);
    CHECK(b >= 0 && b < SkipBins && b >= previous);
    previous = b;
    ++bins[b];
  }
  for (int threshold : {-100, -200, -1200, -9900, -32700}) {
    std::uint64_t direct = 0, from_bins = 0;
    for (int s = -INT16_MAX; s <= threshold; ++s) ++direct;
    for (int b = 0; b <= skip_score_bin(threshold); ++b) from_bins += bins[b];
    CHECK_MSG(from_bins == direct, "threshold " << threshold << ": " << from_bins << " vs " << direct);
  }
  CHECK_EQ(skip_score_bin(0), SkipBins / 2);
  CHECK_EQ(skip_score_bin(99), SkipBins / 2);
  CHECK_EQ(skip_score_bin(100), SkipBins / 2 + 1);
  CHECK_EQ(skip_score_bin(-1), SkipBins / 2 - 1);
  CHECK_EQ(skip_score_bin(-99), SkipBins / 2 - 1);
  CHECK_EQ(skip_score_bin(-100), SkipBins / 2 - 2);
  CHECK_EQ(skip_score_bin(INT16_MAX), SkipBins - 1);
}

// Idea 59 step 1's window gap (DESIGN.md §5.7): the distance to the nearer
// finite bound, a bound in the mate or tablebase band not counting, -1 with
// none; 1 cp bins to 255, 64 cp bins to 4,095, one overflow bin; depth bands.
TEST_CASE("pruning", "idea 59 window gap, its bins and depth bands") {
  CHECK_EQ(window_gap(100, 50, 51), 49);
  CHECK_EQ(window_gap(40, 50, 51), 10);
  CHECK_EQ(window_gap(51, 50, 51), 0);
  CHECK_EQ(window_gap(100, -ScoreInfinite, ScoreInfinite), -1);
  CHECK_EQ(window_gap(100, mated_score(3), mate_score(4)), -1);  // mate distance bounds are not finite
  CHECK_EQ(window_gap(100, -ScoreInfinite, 150), 50);            // one finite bound
  CHECK_EQ(window_gap(100, 20, ScoreInfinite), 80);
  CHECK_EQ(window_gap(100, TbWinScore - 10, ScoreInfinite), -1);
  int previous = -1;
  for (int g = 0; g < 6000; ++g) {
    const int b = window_gap_bin(g);
    CHECK(b >= 0 && b < GapBins && b >= previous);
    previous = b;
  }
  CHECK_EQ(window_gap_bin(255), 255);
  CHECK_EQ(window_gap_bin(256), 256);
  CHECK_EQ(window_gap_bin(319), 256);
  CHECK_EQ(window_gap_bin(320), 257);
  CHECK_EQ(window_gap_bin(4095), GapBins - 2);
  CHECK_EQ(window_gap_bin(4096), GapBins - 1);
  CHECK_EQ(GapBins, 317);
  CHECK_EQ(gap_depth_band(1), 0);
  CHECK_EQ(gap_depth_band(2), 1);
  CHECK_EQ(gap_depth_band(3), 2);
  CHECK_EQ(gap_depth_band(4), 2);
  CHECK_EQ(gap_depth_band(5), 3);
  CHECK_EQ(gap_depth_band(7), 3);
  CHECK_EQ(gap_depth_band(8), 4);
  CHECK_EQ(gap_depth_band(40), GapBands - 1);
}

}  // namespace forkeng::test
