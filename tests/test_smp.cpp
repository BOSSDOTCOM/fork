// SPDX-License-Identifier: GPL-3.0-or-later

// Lazy SMP's helper threads (src/search/helper_pool.hpp; DESIGN.md §5.6 step
// 17a): the pool's life cycle, the coordinator's once-per-search setup, the
// abort flag and the main thread's summed counts. In CI's TSan threaded list,
// which also checks the pool, the shared TT and the counters for races.
#include <atomic>
#include <chrono>
#include <memory>
#include <thread>
#include <vector>

#include "core/movegen.hpp"
#include "core/position.hpp"
#include "harness.hpp"
#include "search/helper_pool.hpp"
#include "search/searcher.hpp"
#include "search/trans_table.hpp"

namespace forkeng::test {

namespace {

struct SmpHash {
  std::vector<TtBucket> buckets = std::vector<TtBucket>(16384);
  TransTable table;
  SmpHash() {
    table.bind_memory(reinterpret_cast<std::byte*>(buckets.data()), buckets.size() * sizeof(TtBucket));
  }
};

// The last report's node count.
struct LastNodes final : SearchListener {
  std::uint64_t nodes = 0;
  void on_iteration(const Position&, const IterationReport& r) override { nodes = r.nodes; }
};

bool legal(const Position& pos, Move m) {
  MoveList moves;
  generate<GenMode::Legal>(pos, moves);
  for (Move x : moves)
    if (x == m) return true;
  return false;
}

// One pooled search as the UCI session runs it (session.cpp, search_main).
SearchResult pooled_search(TransTable& tt, Searcher& main, HelperPool& pool, Position& pos,
                           const SearchQuota& limits, SearchListener* listener) {
  std::atomic<bool> stop{false};
  SearchStart plan;
  prepare_start(tt, main.switches, pos, plan);
  if (pool.begin_search(pos, main.switches, plan, limits, main)) {
    plan.helpers = pool.searchers();
    plan.helper_count = pool.helper_count();
  }
  const SearchResult r = main.deliberate(pos, limits, stop, nullptr, listener, &plan);
  pool.end_search();
  pool.wait_idle();
  return r;
}

}  // namespace

TEST_CASE("smp", "helpers search beside the main thread, whose reports and result add up their nodes") {
  SmpHash hash;
  auto main = std::make_unique<Searcher>(hash.table);
  HelperPool pool(hash.table);
  CHECK_EQ(pool.resize(2), std::size_t{2});
  Position pos;
  SearchQuota limits;
  limits.depth = 9;
  LastNodes last;
  const SearchResult r = pooled_search(hash.table, *main, pool, pos, limits, &last);
  CHECK(legal(pos, r.best));
  CHECK_EQ(r.depth, 9);
  const std::uint64_t own = main->published_nodes();  // the main thread's alone, published at its end
  std::uint64_t helpers = 0;
  for (std::size_t i = 0; i < pool.helper_count(); ++i) {
    const std::uint64_t n = pool.searchers()[i]->published_nodes();
    CHECK_MSG(n > 0, "helper " << i << " searched no published node");
    helpers += n;
  }
  // The result was summed before the helpers stopped, so it lies between the
  // main thread's own count and the final total.
  CHECK_MSG(r.nodes > own && r.nodes <= own + helpers, r.nodes << " against " << own << " + " << helpers);
  CHECK_MSG(last.nodes > 0 && last.nodes <= r.nodes, last.nodes << " against " << r.nodes);
}

// `go nodes` with helpers counts every thread's nodes (the owner's rule,
// 2026-11-15): the main thread stops once the published sum reaches the
// limit, so its own count stays below it. One thread keeps the exact limit
// (the search suite's node-limit cases).
TEST_CASE("smp", "a node limit with helpers counts every thread's nodes") {
  SmpHash hash;
  auto main = std::make_unique<Searcher>(hash.table);
  HelperPool pool(hash.table);
  CHECK_EQ(pool.resize(3), std::size_t{3});
  Position pos;
  SearchQuota limits;
  limits.nodes = 200000;
  const SearchResult r = pooled_search(hash.table, *main, pool, pos, limits, nullptr);
  CHECK(legal(pos, r.best));
  const std::uint64_t own = main->published_nodes();
  CHECK_MSG(own < limits.nodes, "the main thread searched " << own << " nodes itself, the whole limit");
  CHECK_MSG(r.nodes >= limits.nodes, "stopped at " << r.nodes << " nodes in all, under the limit");
}

TEST_CASE("smp", "the coordinator advances the TT's age once per search, whatever the thread count") {
  SmpHash hash;
  auto main = std::make_unique<Searcher>(hash.table);
  HelperPool pool(hash.table);
  CHECK_EQ(pool.resize(3), std::size_t{3});
  Position pos;
  SearchQuota limits;
  limits.depth = 5;
  for (int search = 1; search <= 3; ++search) {
    const int before = hash.table.age();
    pooled_search(hash.table, *main, pool, pos, limits, nullptr);
    CHECK_EQ(hash.table.age(), (before + 1) % 256);
  }
  // And a single-threaded search (no SearchStart) still advances it itself.
  std::atomic<bool> stop{false};
  const int before = hash.table.age();
  main->deliberate(pos, limits, stop, nullptr, nullptr);
  CHECK_EQ(hash.table.age(), (before + 1) % 256);
}

TEST_CASE("smp", "end_search stops helpers with no depth limit, and wait_idle returns once all are parked") {
  SmpHash hash;
  auto main = std::make_unique<Searcher>(hash.table);
  HelperPool pool(hash.table);
  CHECK_EQ(pool.resize(3), std::size_t{3});
  Position pos;
  SearchStart plan;
  prepare_start(hash.table, main->switches, pos, plan);
  CHECK(pool.begin_search(pos, main->switches, plan, SearchQuota{}, *main));  // depth MaxPly - 1: never ends alone
  std::this_thread::sleep_for(std::chrono::milliseconds(50));
  const auto t0 = std::chrono::steady_clock::now();
  pool.end_search();
  pool.wait_idle();
  const auto ms =
      std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count();
  CHECK_MSG(ms < 2000,
            "helpers took " << ms << " ms to stop");  // generous: sanitizer builds on a loaded machine
  for (std::size_t i = 0; i < pool.helper_count(); ++i) CHECK(pool.searchers()[i]->published_nodes() > 0);
}

TEST_CASE("smp", "resize grows, shrinks to none and grows again between searches; histories clear") {
  SmpHash hash;
  auto main = std::make_unique<Searcher>(hash.table);
  HelperPool pool(hash.table);
  CHECK_EQ(pool.helper_count(), std::size_t{0});
  Position pos;
  SearchQuota limits;
  limits.depth = 4;
  CHECK(!pool.begin_search(pos, main->switches, SearchStart{}, limits, *main));  // no helpers: nothing starts
  for (std::size_t n : {std::size_t{4}, std::size_t{1}, std::size_t{0}, std::size_t{2}}) {
    CHECK_EQ(pool.resize(n), n);
    CHECK_EQ(pool.helper_count(), n);
    const SearchResult r = pooled_search(hash.table, *main, pool, pos, limits, nullptr);
    CHECK(legal(pos, r.best));
    pool.clear_histories();
  }
}

// Lazy SMP v2's skip rule (use_helper_skip; DESIGN.md §5.6 step 17a): a
// helper skips each depth that at least half of the team is already
// searching, never past the depth limit. Fault-checked: with "<" for "<="
// in the half (a strict majority) the second and sixth cases fail.
TEST_CASE("smp", "skip rule: a helper skips depths at least half the team is already searching") {
  const auto next = [](int depth, int limit, std::vector<int> team) {
    return helper_next_depth(depth, limit, team.size(), [&](std::size_t i) { return team[i]; });
  };
  CHECK_EQ(next(5, 60, {4, 4, 4, 4}), 5);  // nobody at 5 yet: search it
  CHECK_EQ(next(5, 60, {5, 5, 4, 4}), 6);  // half at 5: skip to 6, where nobody is
  CHECK_EQ(next(5, 60, {7, 6, 6, 4}), 7);  // 3 of 4 at >= 6, 1 at >= 7: 7
  CHECK_EQ(next(5, 60, {9, 9, 9, 9}), 10);
  CHECK_EQ(next(5, 8, {9, 9, 9, 9}), 8);  // never past the limit
  CHECK_EQ(next(3, 60, {3, 0}), 4);        // two threads: the helper stays a depth ahead of the main thread
  CHECK_EQ(next(1, 60, {0, 0, 0}), 1);     // a new search: all at 0
}

TEST_CASE("smp", "with the skip rule on, a pooled search plays a legal move and no helper passes the depth limit") {
  SmpHash hash;
  auto main = std::make_unique<Searcher>(hash.table);
  main->switches.use_helper_skip = true;
  HelperPool pool(hash.table);
  CHECK_EQ(pool.resize(3), std::size_t{3});
  Position pos;
  SearchQuota limits;
  limits.depth = 10;
  const SearchResult r = pooled_search(hash.table, *main, pool, pos, limits, nullptr);
  CHECK(legal(pos, r.best));
  CHECK_EQ(r.depth, 10);
  // Every helper reached the depth limit (it never searches past it).
  for (std::size_t i = 0; i < pool.helper_count(); ++i) CHECK(pool.searchers()[i]->searching_depth() <= 10);
}

}  // namespace forkeng::test
