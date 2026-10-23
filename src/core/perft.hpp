// perft: move path enumeration and the fixed bench workload.
//
// Purpose: perft/divide for move generator verification, and bench(), the
// deterministic workload whose node count and signature fingerprint a build.
// Invariants:
// - bench() output is identical on every build preset, compiler and OS
//   (tests/bench.ref, checked by the bench_parity test). It changes only in a
//   commit that intends to change it.
#pragma once

#include <cstdint>
#include <ostream>

#include "core/position.hpp"

namespace forkeng {

std::uint64_t perft(Position& pos, int depth);

// Prints the node count below each root move, then the total.
std::uint64_t divide(Position& pos, int depth, std::ostream& out);

struct BenchResult {
  std::uint64_t nodes;
  std::uint64_t signature;  // fold of the key at every interior node, in visit order
  double seconds;
};

// Runs the fixed bench workload (DESIGN.md 2). The node count and signature
// are identical on every build.
BenchResult bench();

}  // namespace forkeng
