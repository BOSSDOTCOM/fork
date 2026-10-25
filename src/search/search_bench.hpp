// search_bench: Fork's bench workload from Phase 3 on (DESIGN.md §5.2,
// "Search bench"): a fixed-depth, one-thread search of fixed positions.
//
// Purpose: fingerprint a build (node count and signature, tests/bench.ref)
// and measure search speed (nps).
// Invariants:
// - The node count and signature are identical on every preset, compiler,
//   operating system and TCEC compiler: no time limit applies, and every
//   position starts from a cleared search state.
// - The positions are the six CPW perft-suite positions and 40 positions
//   from the Lichess CC0 database (tools/make_bench_positions.py), covering
//   openings, middlegames, endgames and positions in check.
// - Changing a position, the depth or the search changes the reference.
#pragma once

#include <cstdint>
#include <span>
#include <string_view>

namespace forkeng {

struct SearchBenchResult {
  std::uint64_t nodes;
  std::uint64_t signature;  // fold of each position's nodes, best move, score and depth
  double seconds;
};

SearchBenchResult run_search_bench();

// The bench positions (for tests that search the same workload).
std::span<const std::string_view> search_bench_fens();

}  // namespace forkeng
