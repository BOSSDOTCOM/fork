// SPDX-License-Identifier: GPL-3.0-or-later

// The pawn drift table (tier 2, T32; src/search/eval_drift.hpp): bounded
// under any updates, a weighted running mean, and per side and structure.
#include <memory>

#include "core/splitmix.hpp"
#include "harness.hpp"
#include "search/eval_drift.hpp"
#include "suite.hpp"

namespace forkeng::test {

TEST_CASE("eval_drift", "bounded by the limit under any updates") {
  auto drift = std::make_unique<EvalDrift>();
  std::uint64_t seed = 17;
  constexpr std::uint32_t Structure = 0x9e3779b9u;
  for (int i = 0; i < 200000; ++i) {
    // Errors far past the limit, depths past the weight cap.
    const int error = static_cast<int>(splitmix_next(seed) % 60001) - 30000;
    const int depth = 1 + static_cast<int>(splitmix_next(seed) % 64);
    drift->learn(i % 2 ? White : Black, Structure, error, depth);
    for (Color c : {White, Black}) {
      const int v = drift->offset(c, Structure);
      CHECK_MSG(v >= -DriftLimit && v <= DriftLimit, "drift " << v << " after error " << error);
    }
  }
}

TEST_CASE("eval_drift", "a running mean of the errors, weighted by depth") {
  auto drift = std::make_unique<EvalDrift>();
  constexpr std::uint32_t Structure = 0x12345678u;
  CHECK_EQ(drift->offset(White, Structure), 0);
  // One update at depth d moves the entry d / DriftWeightTotal of the way.
  drift->learn(White, Structure, 64, 2);
  CHECK_EQ(drift->offset(White, Structure), 64 * 2 / DriftWeightTotal);
  // Repeated updates converge on the error, and from below never pass it.
  for (int i = 0; i < 1000; ++i) drift->learn(White, Structure, 40, 10);
  CHECK(drift->offset(White, Structure) >= 39 && drift->offset(White, Structure) <= 40);
  // Deeper results weigh more: from the same start, a depth-8 update moves
  // further than a depth-1 one.
  auto shallow = std::make_unique<EvalDrift>(), deep = std::make_unique<EvalDrift>();
  shallow->learn(Black, Structure, 200, 1);
  deep->learn(Black, Structure, 200, 8);
  CHECK(deep->offset(Black, Structure) > shallow->offset(Black, Structure));
  // Read in whole centipawns, toward zero.
  auto small = std::make_unique<EvalDrift>();
  small->learn(White, Structure, -1, 1);
  CHECK_EQ(small->offset(White, Structure), 0);
}

TEST_CASE("eval_drift", "per side to move and per structure; clear empties it") {
  auto drift = std::make_unique<EvalDrift>();
  constexpr std::uint32_t A = 0x00000000u, B = 0xffffffffu;
  CHECK(EvalDrift::slot(A) != EvalDrift::slot(B));
  CHECK(EvalDrift::slot(B) < DriftSlots);
  for (int i = 0; i < 100; ++i) drift->learn(White, A, 120, 8);
  CHECK(drift->offset(White, A) > 0);
  CHECK_EQ(drift->offset(Black, A), 0);
  CHECK_EQ(drift->offset(White, B), 0);
  drift->clear();
  CHECK_EQ(drift->offset(White, A), 0);
}

}  // namespace forkeng::test
