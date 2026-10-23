// Perft (move path enumeration) and the fixed bench workload.
#pragma once

#include <cstdint>
#include <ostream>

#include "core/position.hpp"

namespace fork {

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

}  // namespace fork
