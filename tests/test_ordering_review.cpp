// Reviewer tests for deliverable 5 (move ordering). Each case pins a claim
// made in a module header comment of the change under review.
#include <algorithm>
#include <atomic>
#include <memory>
#include <vector>

#include "core/movegen.hpp"
#include "harness.hpp"
#include "search/move_selector.hpp"
#include "search/quiet_history.hpp"
#include "search/searcher.hpp"
#include "suite.hpp"

namespace forkeng::test {

namespace {

struct ReviewHash {
  std::vector<TtBucket> buckets = std::vector<TtBucket>(16384);
  TransTable table;
  ReviewHash() {
    table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  }
  void clear() { std::fill(buckets.begin(), buckets.end(), TtBucket{}); }
};

}  // namespace

// Review of deliverable 5: the butterfly history is state that survives
// between deliberate() calls, so the invariant now names it: a search is a
// function of position, limits, switches, TT contents and history.
TEST_CASE("ordering", "review: deliberate() is a function of position, limits, switches, TT and history") {
  ReviewHash store;
  auto searcher = std::make_unique<Searcher>(store.table);
  const std::atomic<bool> stop{false};
  SearchQuota limits;
  limits.depth = 7;
  Position pos;
  CHECK(pos.set_fen(perft_suite()[1].fen));  // the perft suite's second position (sourced there)
  store.clear();
  searcher->clear_history();
  const SearchResult a = searcher->deliberate(pos, limits, stop, nullptr, nullptr);
  store.clear();
  searcher->clear_history();  // same TT and history as the first search
  const SearchResult b = searcher->deliberate(pos, limits, stop, nullptr, nullptr);
  CHECK_MSG(a.nodes == b.nodes,
            "nodes " << a.nodes << " then " << b.nodes << " with the same empty TT and history");
}

// Review of deliverable 5: ties are not kept in generation order (the
// partial selection sort swaps); the order is deterministic, and the
// comment now says so. The best-history quiet comes first.
TEST_CASE("ordering",
          "review: equal-score quiets come in a deterministic order after the best-history quiet") {
  Position pos;
  CHECK(pos.set_fen("4k3/8/8/8/8/8/8/R3K3 w - - 0 1"));
  MoveList quiets;
  generate<GenMode::Quiets>(pos, quiets);
  CHECK(quiets.size() >= 3);
  QuietHistory history;
  const Move last = quiets[quiets.size() - 1];
  history.apply(White, last, 1600);
  std::vector<Move> runs[2];
  for (auto& got : runs) {
    MoveSelector s;
    s.start_main(pos, NoMove, &history);
    for (Move m; !(m = s.take_next()).is_none();) got.push_back(m);
  }
  CHECK(!runs[0].empty() && runs[0].front() == last);
  CHECK(runs[0] == runs[1]);
  CHECK_EQ(runs[0].size(), quiets.size());
}

}  // namespace forkeng::test
