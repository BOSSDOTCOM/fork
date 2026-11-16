// SPDX-License-Identifier: GPL-3.0-or-later

#include "search/helper_pool.hpp"

namespace forkeng {

HelperPool::~HelperPool() { stop_all(); }

void HelperPool::stop_all() {
  end_search();
  {
    std::unique_lock<std::mutex> lock(mutex_);
    idle_.wait(lock, [&] { return busy_ == 0; });
    quit_ = true;
  }
  wake_.notify_all();
  for (const std::unique_ptr<HelperThread>& h : helpers_)
    if (h->thread.joinable()) h->thread.join();
  helpers_.clear();
  searchers_.clear();
  std::scoped_lock lock(mutex_);
  quit_ = false;
}

std::size_t HelperPool::resize(std::size_t helpers) {
  if (helpers == helpers_.size()) return helpers_.size();
  stop_all();
  // Every container's room first, while no helper thread exists: below this
  // nothing that can throw runs once a thread is joinable, but make_unique
  // and std::thread's own construction, which are caught.
  std::vector<std::unique_ptr<HelperThread>> kept;
  try {
    helpers_.reserve(helpers);
    kept.reserve(helpers);
    searchers_.reserve(helpers);
    team_.reserve(helpers + 1);
  } catch (...) {
    return 0;  // no memory even for the lists: no helper
  }
  // Each new thread counts as busy until its Searcher exists (or failed).
  for (std::size_t i = 0; i < helpers; ++i) {
    try {
      auto h = std::make_unique<HelperThread>();
      HelperThread& ref = *h;
      helpers_.push_back(std::move(h));
      {
        std::scoped_lock lock(mutex_);
        ++busy_;
      }
      try {
        ref.thread = std::thread(&HelperPool::helper_loop, this, std::ref(ref));
      } catch (...) {
        std::scoped_lock lock(mutex_);
        --busy_;
        ref.failed = true;
        throw;
      }
    } catch (...) {
      break;  // no thread or no memory: run with the helpers made so far
    }
  }
  {
    std::unique_lock<std::mutex> lock(mutex_);
    idle_.wait(lock, [&] { return busy_ == 0; });
  }
  // Drop the helpers that could not start (their threads have returned);
  // kept, searchers_ and team_ have their room already.
  for (std::unique_ptr<HelperThread>& h : helpers_) {
    if (h->failed) {
      if (h->thread.joinable()) h->thread.join();
      continue;
    }
    kept.push_back(std::move(h));
  }
  helpers_ = std::move(kept);
  searchers_.clear();
  for (const std::unique_ptr<HelperThread>& h : helpers_) searchers_.push_back(h->searcher.get());
  team_.assign(1, nullptr);  // the main thread's slot, set at each begin_search
  team_.insert(team_.end(), searchers_.begin(), searchers_.end());
  return helpers_.size();
}

void HelperPool::helper_loop(HelperThread& h) {
  try {
    h.searcher = std::make_unique<Searcher>(tt_);  // allocated and first touched on this thread
    h.root.reserve_plies(root_plies_);             // so copying the root never allocates (A2)
  } catch (...) {
    h.failed = true;
  }
  std::uint64_t seen;
  {
    std::scoped_lock lock(mutex_);
    seen = searches_begun_;
    --busy_;
  }
  idle_.notify_all();
  if (h.failed) return;
  for (;;) {
    {
      std::unique_lock<std::mutex> lock(mutex_);
      wake_.wait(lock, [&] { return quit_ || searches_begun_ != seen; });
      if (quit_) return;
      seen = searches_begun_;
      h.searcher->switches = switches_;
    }
    // Every input below was written before the search count changed and stays
    // unchanged until every helper is idle again.
    try {
      h.root = root_;  // may allocate (a longer game than the copy's room): then no search this go
      h.searcher->deliberate(h.root, limits_, abort_, nullptr, nullptr, &start_);
    } catch (...) {
      // ignored: this helper sits out the search; the others and the main thread go on
    }
    {
      std::scoped_lock lock(mutex_);
      --busy_;
    }
    idle_.notify_all();
  }
}

bool HelperPool::begin_search(const Position& root, const SearchSwitches& switches, const SearchStart& start,
                              const SearchQuota& limits, Searcher& main) {
  if (helpers_.empty()) return false;
  {
    std::scoped_lock lock(mutex_);
    try {
      root_ = root;  // may allocate (a longer game than the copy's room)
    } catch (...) {
      return false;  // no memory: the main thread searches alone
    }
    switches_ = switches;
    start_.table_ranked = start.table_ranked;
    start_.table_kept = start.table_kept;
    start_.helpers = nullptr;  // helpers report nothing, so they add up no one's counts
    start_.helper_count = 0;
    team_[0] = &main;
    start_.helper = true;
    start_.team = team_.data();
    start_.team_size = team_.size();
    main.clear_published();  // so no helper reads the last search's depth
    limits_ = SearchQuota{};
    limits_.depth = limits.depth;
    limits_.restrict_to = limits.restrict_to;
    abort_.store(false, std::memory_order_relaxed);
    for (Searcher* s : searchers_) s->clear_published();
    busy_ = helpers_.size();
    ++searches_begun_;
  }
  wake_.notify_all();
  return true;
}

void HelperPool::wait_idle() {
  std::unique_lock<std::mutex> lock(mutex_);
  idle_.wait(lock, [&] { return busy_ == 0; });
}

void HelperPool::clear_histories() {
  wait_idle();
  for (Searcher* s : searchers_) s->clear_history();
}

}  // namespace forkeng
