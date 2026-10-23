#include <algorithm>

#include "core/perft.hpp"
#include "harness.hpp"
#include "suite.hpp"

using namespace fork;
using namespace fork::test;

namespace {

void run_suite(int (*depth_for)(const PerftPosition&), bool mirror) {
  for (const PerftPosition& pp : perft_suite()) {
    Position pos;
    CHECK_MSG(pos.set_fen(pp.fen), pp.name);
    if (mirror) pos = pos.mirrored();
    int depth = depth_for(pp);
    std::uint64_t nodes = perft(pos, depth);
    CHECK_MSG(nodes == pp.counts[depth - 1],
              pp.name << (mirror ? " (mirrored)" : "") << " depth " << depth << ": got " << nodes
                      << ", expected " << pp.counts[depth - 1]);
  }
}

}  // namespace

TEST_CASE("perft_suite", "cpw positions") {
  run_suite([](const PerftPosition& pp) { return Optimized ? pp.release_depth : pp.debug_depth; }, false);
}

TEST_CASE("perft_full", "cpw positions at release depths") {
  run_suite([](const PerftPosition& pp) { return pp.release_depth; }, false);
}

TEST_CASE("perft_mirror", "color-flipped cpw positions") {
  // Depth 5 for every position in optimized builds.
  run_suite([](const PerftPosition& pp) {
    return Optimized ? std::min(pp.release_depth, 5) : std::min(pp.debug_depth, 4);
  }, true);
}

TEST_CASE("perft_mirror", "mirror is an involution") {
  for (const PerftPosition& pp : perft_suite()) {
    Position pos;
    pos.set_fen(pp.fen);
    Position back = pos.mirrored().mirrored();
    CHECK_MSG(back.fen() == pos.fen() && back.key() == pos.key(), pp.name);
  }
}

TEST_CASE("perft_edge", "special-rule positions match the independent generator") {
  for (const EdgePosition& ep : edge_positions()) {
    for (bool mirror : {false, true}) {
      Position pos;
      CHECK_MSG(pos.set_fen(ep.fen), ep.what);
      if (mirror) pos = pos.mirrored();
      for (std::size_t d = 1; d <= ep.counts.size(); ++d) {
        std::uint64_t nodes = perft(pos, static_cast<int>(d));
        CHECK_MSG(nodes == ep.counts[d - 1], ep.fen << (mirror ? " (mirrored)" : "") << " depth " << d
                                                 << ": got " << nodes << ", expected " << ep.counts[d - 1]);
      }
    }
  }
}
