// Tier 1 pruning and reductions (DESIGN.md §5.2, deliverable 6).
#include <atomic>
#include <cmath>
#include <memory>
#include <vector>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "eval/bootstrap_eval.hpp"
#include "harness.hpp"
#include "search/lmr_table.hpp"
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

// The LMR context's move facts (lmr_move_facts, the heuristic-discovery
// region's inputs, 2026-10-27): constructed positions, the expected values
// computed independently by python-chess (board.is_attacked_by before the
// move, board.attacks after it; the positions checked legal there). Case 3's
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
                             FactsCase{"4k3/8/8/8/3n4/4P3/8/4K3 b - - 0 1", "d4b5", 1, true, false}}) {
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

// The game phase the LMR context reads (Fork's evaluation's own, moved inline
// into bootstrap_eval.hpp unchanged): python-chess counts 24, 0 and 6 here.
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
