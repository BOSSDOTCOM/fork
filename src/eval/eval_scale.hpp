// eval_scale: the range every evaluator's scores stay within.
//
// Purpose: the bound the search's score bands are built around
// (search/score_bounds.hpp), without depending on which evaluator a build
// selects (eval/eval.hpp; audit-1 A9 F-12).
// Invariants:
// - Every static evaluation is within [-EvalLimit, EvalLimit], far below
//   the tablebase and mate bands.
#pragma once

namespace forkeng {

constexpr int EvalLimit = 20000;

}  // namespace forkeng
