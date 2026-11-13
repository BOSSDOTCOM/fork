// SPDX-License-Identifier: GPL-3.0-or-later

// game_fibers: stacks and switches for fork_datagen's interleaved workers
// (ideas.md idea 165, prototype; built only with FORK_DATAGEN_INTERLEAVE).
//
// Purpose: one worker thread plays several self-play games, each on a stack
// of its own. At the search's pause point (Searcher::set_pause) a game hands
// the thread to the next game, so the TT line one game waits for arrives
// while another game works.
// Invariants:
// - x86-64 System V (Linux) only: CMake refuses FORK_DATAGEN_INTERLEAVE on
//   other targets and with sanitizers (they would need every switch
//   announced to them).
// - A switch saves only what the ABI says a call preserves: rbx, rbp,
//   r12-r15 and the stack pointer. Fork never changes MXCSR or the x87
//   control word, so they are not saved.
// - A stack is mapped once per game slot, with an inaccessible guard page
//   below it; its pages are committed only when touched. Nothing is
//   allocated per switch or per node.
// - A fiber's entry function never returns: it ends by switching away for
//   good.
#pragma once

#include <cstddef>

namespace forkeng {

// The stack each game gets: what a Linux std::thread gets by default, so a
// game's search has the room it has in today's one-game-per-thread worker.
constexpr std::size_t FiberStackBytes = std::size_t{8} << 20;

// One fiber's stack (owns the mapping).
class FiberStack {
 public:
  FiberStack() = default;
  FiberStack(const FiberStack&) = delete;
  FiberStack& operator=(const FiberStack&) = delete;
  ~FiberStack();

  // Maps `bytes` (rounded up to whole pages) and the guard page; false if
  // the mapping fails.
  bool map(std::size_t bytes);
  // The saved stack pointer that starts entry(arg) on this stack when it is
  // first switched to.
  void* prepare(void (*entry)(void*), void* arg);

 private:
  void* base_ = nullptr;
  std::size_t bytes_ = 0;
};

// Saves the running context's stack pointer in *save and resumes the
// context whose stack pointer is `next`.
extern "C" void forkeng_fiber_switch(void** save, void* next);

}  // namespace forkeng
