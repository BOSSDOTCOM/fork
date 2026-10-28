// SPDX-License-Identifier: GPL-3.0-or-later

// Times the Hash table's allocation and parallel clear per worker count
// (DESIGN.md §5.1, test 2: "hash clear time at 1, 4 and 16 GiB recorded per
// thread count"). The engine itself clears with max(Threads, hardware
// threads) workers; this tool sets the count directly to show the scaling.
//
//   fork_hash_timing <MB> [<MB> ...]      e.g. fork_hash_timing 1024 4096 16384
//
// For each size: the first resize (allocation plus first-touch clear) with
// every worker count, then a re-clear of the touched table. A size that does
// not fit in available memory is reported as refused, as the engine would.
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <thread>
#include <vector>

#include "search/hash_memory.hpp"

namespace {

double ms_since(std::chrono::steady_clock::time_point t) {
  return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t).count();
}

}  // namespace

int main(int argc, char** argv) {
  using namespace forkeng;
  const unsigned hw = std::max(1u, std::thread::hardware_concurrency());
  std::vector<unsigned> counts = {1, 2, 4, 8};
  for (unsigned w = 12; w <= hw; w += 4) counts.push_back(w);
  if (counts.back() != hw && hw > 8) counts.push_back(hw);
  std::printf("hardware threads %u, available memory %zu MB\n", hw, available_memory() / BytesPerMB);
  std::printf("%10s %8s %14s %12s\n", "MB", "workers", "alloc+clear ms", "re-clear ms");
  for (int i = 1; i < argc; ++i) {
    const std::size_t mb = std::strtoull(argv[i], nullptr, 10);
    for (unsigned w : counts) {
      HashMemory h;  // fresh each time, so every first touch faults pages in
      std::string report;
      auto t = std::chrono::steady_clock::now();
      if (!h.resize(hash_bytes_for_mb(mb), report)) {
        std::printf("%10zu %8u  refused: %s\n", mb, w, report.c_str());
        break;
      }
      h.clear(w);
      const double first = ms_since(t);
      t = std::chrono::steady_clock::now();
      h.clear(w);
      std::printf("%10zu %8u %14.1f %12.1f\n", mb, w, first, ms_since(t));
    }
  }
  return 0;
}
