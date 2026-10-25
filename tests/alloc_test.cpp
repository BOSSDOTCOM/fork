// Separate executable: replaces global operator new/delete with counting
// versions and asserts that the hot paths (move generation, make/unmake,
// null moves, legality and check queries, the search) never touch the heap.
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <new>
#include <vector>

#include "core/movegen.hpp"
#include "core/perft.hpp"
#include "search/search_bench.hpp"
#include "search/searcher.hpp"

namespace {
std::atomic<long> allocations{0};
}

void* operator new(std::size_t n) {
  allocations.fetch_add(1, std::memory_order_relaxed);
  if (void* p = std::malloc(n ? n : 1)) return p;
  throw std::bad_alloc();
}
void* operator new[](std::size_t n) { return operator new(n); }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }

namespace {

std::uint64_t walk(forkeng::Position& pos, int depth) {
  forkeng::MoveList legal, captures, quiets;
  forkeng::generate<forkeng::GenMode::Legal>(pos, legal);
  forkeng::generate<forkeng::GenMode::Captures>(pos, captures);
  forkeng::generate<forkeng::GenMode::Quiets>(pos, quiets);
  std::uint64_t n = legal.size();
  for (forkeng::Move m : legal) {
    n += pos.is_pseudo_legal(m) + pos.is_legal(m) + pos.gives_check(m) + (pos.predicted_key(m) & 1);
    if (depth > 1) {
      pos.make(m);
      n += walk(pos, depth - 1);
      pos.unmake(m);
    }
  }
  if (!pos.in_check()) {
    pos.make_null();
    n += pos.repetition_count() + pos.insufficient_material();
    pos.unmake_null();
  }
  return n;
}

}  // namespace

int main() {
  forkeng::init();
  {
    // The counter must see allocations, or a zero below would mean nothing.
    long before = allocations.load();
    int* volatile probe = new int(1);  // volatile: the pair may not be elided
    delete probe;
    if (allocations.load() == before) {
      std::printf("FAIL: counting operator new is not in effect\n");
      return 3;
    }
  }
  const char* fens[] = {
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
      "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
      "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
      "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
  };
  int failures = 0;
  for (const char* fen : fens) {
    forkeng::Position pos;  // setup may allocate (FEN parsing, state stack reserve)
    if (!pos.set_fen(fen)) return 2;
    long before = allocations.load();
    std::uint64_t n = walk(pos, 4);
    long during = allocations.load() - before;
    std::printf("%-75s %llu checks, %ld heap allocations\n", fen, static_cast<unsigned long long>(n), during);
    if (during != 0) ++failures;
  }
  {
    // Review M1 (2026-10-23): a search thread works on a copy of the root
    // position, so a copy must keep the State stack's reserve too.
    forkeng::Position root;
    if (!root.set_fen(fens[1])) return 2;
    forkeng::Position copy = root;
    forkeng::Position assigned;
    assigned = root;
    for (forkeng::Position* pos : {&copy, &assigned}) {
      long before = allocations.load();
      std::uint64_t n = walk(*pos, 4);
      long during = allocations.load() - before;
      std::printf("%-75s %llu checks, %ld heap allocations\n",
                  pos == &copy ? "copy-constructed Position" : "copy-assigned Position",
                  static_cast<unsigned long long>(n), during);
      if (during != 0) ++failures;
    }
  }
  {
    // The search (DESIGN.md §5.2, hot-path rule 3): after setup (the
    // Searcher is created once, outside any search), explore() never allocates,
    // on any of the search-bench positions.
    std::vector<forkeng::TtBucket> memory(16384);  // a 1 MB table, allocated before counting
    forkeng::TransTable tt;
    tt.bind_memory(reinterpret_cast<std::byte*>(memory.data()), memory.size() * sizeof(forkeng::TtBucket));
    auto searcher = std::make_unique<forkeng::Searcher>(tt);
    const std::atomic<bool> stop{false};
    forkeng::SearchLimits limits;
    limits.depth = 4;
    long during = 0;
    std::uint64_t nodes = 0;
    for (const std::string_view fen : forkeng::search_bench_fens()) {
      forkeng::Position pos;
      if (!pos.set_fen(fen)) return 2;
      long before = allocations.load();
      nodes += searcher->explore(pos, limits, stop, nullptr, nullptr).nodes;
      during += allocations.load() - before;
    }
    std::printf("search depth 4 on the %zu bench positions: %llu nodes, %ld heap allocations\n",
                forkeng::search_bench_fens().size(), static_cast<unsigned long long>(nodes), during);
    if (during != 0) ++failures;
  }
  std::printf("%s\n", failures ? "FAIL: hot path allocated" : "ok: no heap allocation in the hot path");
  return failures ? 1 : 0;
}
