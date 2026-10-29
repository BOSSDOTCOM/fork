// SPDX-License-Identifier: GPL-3.0-or-later

// Tests from the adversarial review of deliverable 6 (tier 1 pruning):
// pruned mate scores are real, and stopped searches and probes leave no
// state behind. (The review also showed pruning delaying a mate in 3 in
// KQR v K to depth 11; a strength question, ideas.md, not a test.)
#include <atomic>
#include <cmath>
#include <memory>
#include <vector>

#include "core/movegen.hpp"
#include "core/splitmix.hpp"
#include "harness.hpp"
#include "search/lmr_table.hpp"
#include "search/searcher.hpp"

namespace forkeng::test {

namespace {

struct ReviewFixture {
  std::vector<TtBucket> buckets = std::vector<TtBucket>(16384);
  TransTable table;
  std::unique_ptr<Searcher> searcher;
  std::atomic<bool> stop{false};
  ReviewFixture() {
    table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
    searcher = std::make_unique<Searcher>(table);
  }
  void clear() {
    std::fill(buckets.begin(), buckets.end(), TtBucket{});
    searcher->clear_history();
  }
  SearchResult search(std::string_view fen, int depth, std::uint64_t nodes = 0) {
    clear();
    Position pos;
    CHECK_MSG(pos.set_fen(fen), fen);
    SearchQuota limits;
    limits.depth = depth;
    limits.nodes = nodes;
    return searcher->deliberate(pos, limits, stop, nullptr, nullptr);
  }
};

SearchSwitches no_pruning() {
  SearchSwitches s;
  s.tt_exact_depth = true;
  s.use_rfp = s.use_nmp = s.use_lmr = s.use_lmp = s.use_futility = s.use_see_prune = false;
  return s;
}

}  // namespace

// A mate the pruned search reports must be real: an exact (unpruned) search
// to that many plies confirms it at least as fast (wins) or no slower
// (losses).
TEST_CASE("pruning", "every mate score the pruned search reports is confirmed by an exact search") {
  ReviewFixture fx;
  std::uint64_t seed = 77;
  static constexpr std::string_view Starts[] = {
      "4k3/8/8/8/8/8/8/R3K2Q w - - 0 1",        "4k3/8/8/8/8/8/8/4K2R w - - 0 1",
      "4k3/8/8/3q4/8/8/8/4K2R w - - 0 1",       "1r2k3/8/8/8/8/8/8/R3K1Q1 b - - 0 1",
      "6k1/5ppp/8/8/8/8/5PPP/R2Q2K1 w - - 0 1", "2r3k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1",
      "4k3/8/8/8/8/8/3PPP2/3QKB2 b - - 0 1",    "r5k1/5ppp/8/8/8/2n5/5PPP/3R2K1 w - - 0 1"};
  int mates = 0;
  const int games = Optimized ? 400 : 40;
  for (int game = 0; game < games; ++game) {
    Position pos;
    CHECK(pos.set_fen(Starts[game % 8]));
    const int plies = 2 + static_cast<int>(splitmix_next(seed) % 10);
    for (int ply = 0; ply < plies; ++ply) {
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
    const int pruned = fx.search(fen, Optimized ? 9 : 6).score;
    if (!is_mate_score(pruned)) continue;
    ++mates;
    const int k = pruned > 0 ? MateScore - pruned : MateScore + pruned;
    if (k + 1 > (Optimized ? 9 : 6)) continue;  // keep the exact search affordable
    fx.searcher->switches = no_pruning();
    const int exact = fx.search(fen, k + 1).score;
    if (pruned > 0)
      CHECK_MSG(exact >= pruned,
                fen << ": pruned " << pruned << ", exact at depth " << k + 1 << " " << exact);
    if (pruned < 0)
      CHECK_MSG(exact <= pruned,
                fen << ": pruned " << pruned << ", exact at depth " << k + 1 << " " << exact);
  }
  CHECK(mates > 0);
}

// Search state must not leak between searches: a searcher that was stopped
// mid-search many times (by node limits that end anywhere, including inside
// null-move subtrees) and probed, then reset (TT and history cleared), gives
// exactly the same search as a fresh one.
TEST_CASE("pruning", "stopped searches and probes leave no state behind") {
  static constexpr std::string_view Fens[] = {
      "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"};
  const int depth = Optimized ? 9 : 5;
  for (std::string_view fen : Fens) {
    ReviewFixture fresh;
    const SearchResult want = fresh.search(fen, depth);
    ReviewFixture used;
    for (std::uint64_t n = 37; n < (Optimized ? 200000u : 20000u); n = n * 3 + 11) {
      used.search(fen, MaxPly - 1, n);
      Position pos;
      CHECK(pos.set_fen(fen));
      used.searcher->probe_zero_window(pos, 50, 4, used.stop);
      CHECK_MSG(pos.fen() == fen, fen);
    }
    const SearchResult got = used.search(fen, depth);
    CHECK_MSG(got.nodes == want.nodes && got.score == want.score && got.best == want.best,
              fen << ": nodes " << got.nodes << " vs " << want.nodes << ", score " << got.score << " vs "
                  << want.score);
  }
}

// A probe right after construction and a probe after an deliberate must agree
// (same TT and history state).
TEST_CASE("pruning", "probe_zero_window is reproducible") {
  const std::string_view fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";
  for (int beta : {-200, 0, 30, 400}) {
    ReviewFixture a, b;
    b.search(fen, 6);
    a.clear();
    b.clear();
    Position pa, pb;
    CHECK(pa.set_fen(fen));
    CHECK(pb.set_fen(fen));
    const int sa = a.searcher->probe_zero_window(pa, beta, 5, a.stop);
    const int sb = b.searcher->probe_zero_window(pb, beta, 5, b.stop);
    CHECK_MSG(sa == sb, "beta " << beta << ": " << sa << " vs " << sb);
  }
}

}  // namespace forkeng::test
