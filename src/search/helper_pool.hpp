// SPDX-License-Identifier: GPL-3.0-or-later

// helper_pool: the helper threads of Lazy SMP (DESIGN.md §5.6 step 17a).
//
// Purpose: with Threads = N, N - 1 helper threads search the same root as
// the main search thread, each with its own Searcher (histories, stack,
// accumulators), sharing only the transposition table. Helpers print
// nothing, read no clock, ignore time and node limits and stop on the
// pool's own abort flag; the main thread's search manages time and its
// result is the move played (v1: no voting, no depth offsets).
// Invariants:
// - Threads are created when the helper count changes (resize, never during
//   a search) and parked on a condition variable between searches, not
//   created per go. Each helper allocates its Searcher on its own thread, so
//   first-touch placement puts its tables on that thread's memory node.
// - A search is begin_search (the coordinator has already run prepare_start;
//   every helper starts on a copy of the root), end_search (sets the abort
//   flag; returns at once, so bestmove never waits for a slow helper), then
//   wait_idle (every helper has returned from its search and is parked).
//   Nothing else touches the TT or a helper's Searcher until wait_idle has
//   returned; resize, clear_histories and the destructor wait for it too.
// - A helper whose search failed to start (no memory for its copy of the
//   root) idles for that go; a helper that could not be created at all is
//   dropped, and resize reports the count actually running.
// - Zero helpers (Threads = 1) start no thread: the session then runs the
//   single-threaded path exactly as before.
// - Idea 84's experiment (evaluator-diverse Lazy SMP): in a build with a
//   helper network (CMake FORK_HELPER_NET; helper_net() in eval/eval.hpp),
//   every helper evaluates with it under evaluator tag 1, while the main
//   thread's searcher keeps the embedded network and tag 0; the TT shares
//   moves, scores and bounds between them but each tag's static evals only
//   within that tag. Without one (the default), helpers use the embedded
//   network and tag 0, as before. The network is handed to each helper's
//   searcher when it wakes for a search, so it changes only between searches.
#pragma once

#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>

#include "core/position.hpp"
#include "search/searcher.hpp"
#include "search/trans_table.hpp"

namespace forkeng {

class HelperPool {
 public:
  explicit HelperPool(TransTable& tt);
  ~HelperPool();
  HelperPool(const HelperPool&) = delete;
  HelperPool& operator=(const HelperPool&) = delete;

  // Sets the number of helper threads (outside any search). Returns the
  // number now running: fewer than asked if a thread or its Searcher could
  // not be created.
  std::size_t resize(std::size_t helpers);
  std::size_t helper_count() const { return searchers_.size(); }
  // The helpers' searchers, for the main thread's SearchStart.
  Searcher* const* searchers() const { return searchers_.data(); }

  // Starts every helper on `root` with `switches` (the main searcher's), the
  // coordinator's `start` (its ranking; copied) and searchmoves and depth
  // from `limits` (no time, node or mate limit); `main` (the main thread's
  // searcher) heads the team whose depths the helpers' skip rule reads, and
  // its published counts are cleared with theirs. False if no helper started
  // (none exist, or no memory for the root's copy): nothing to end then.
  bool begin_search(const Position& root, const SearchSwitches& switches, const SearchStart& start,
                    const SearchQuota& limits, Searcher& main);
  void end_search() { abort_.store(true, std::memory_order_relaxed); }
  void wait_idle();

  // Forgets every helper's move-ordering history (ucinewgame, Clear Hash).
  void clear_histories();

#if defined(FORK_EVAL_NNUE)
  // The network and evaluator tag every helper searches with from the next
  // search on (outside any search; waits until every helper is parked). The
  // constructor sets helper_net() with tag 1 when the build has one; tests
  // set another. `net` must outlive the pool's searches.
  void use_net(const NetFile& net, std::uint8_t evaluator);
#endif

 private:
  struct HelperThread {
    std::thread thread;
    std::unique_ptr<Searcher> searcher;  // created on `thread`
    Position root;                       // the helper's copy of the root
    bool failed = false;                 // its Searcher could not be created
  };
  void helper_loop(HelperThread& h);
  void stop_all();  // ends and joins every thread

  TransTable& tt_;
  std::vector<std::unique_ptr<HelperThread>> helpers_;
  std::vector<Searcher*> searchers_;
  std::vector<const Searcher*> team_;  // the main thread's searcher, then the helpers' (begin_search)
  std::mutex mutex_;
  std::condition_variable wake_;  // a new search, or quit
  std::condition_variable idle_;  // a helper started or finished
  std::uint64_t searches_begun_ = 0;  // searches begun
  std::size_t busy_ = 0;          // helpers searching (or still starting up)
  bool quit_ = false;
  // The search every helper runs next (written under mutex_ while all are parked).
  Position root_;
  SearchSwitches switches_;
  SearchStart start_;
  SearchQuota limits_;
#if defined(FORK_EVAL_NNUE)
  const NetFile* net_ = nullptr;  // null: each helper's own default (the embedded network, tag 0)
  std::uint8_t evaluator_ = 0;
#endif
  // Read by every helper's search every StopCheckInterval nodes; written by
  // the coordinator only, on its own cache line.
  alignas(64) std::atomic<bool> abort_{false};
};

}  // namespace forkeng
