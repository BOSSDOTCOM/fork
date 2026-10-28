// eval: the static evaluation the search calls, chosen when Fork is built.
//
// Purpose: one entry point, static_eval(), whose implementation is fixed at
// build time (owner, 2026-10-24: no runtime interface and no indirect call;
// DESIGN.md §5.2 deliverable 1). Phase 3 has one evaluator, the bootstrap
// evaluation; Phase 4 adds others, selected by the FORK_EVALUATOR CMake option.
// Invariants:
// - Scores are centipawns from the side to move's view, within
//   [-EvalLimit, EvalLimit], far below the tablebase and mate bands.
// - Deterministic: no floating point, no state, no allocation.
#pragma once

#include "core/position.hpp"
#include "eval/eval_scale.hpp"

#if defined(FORK_EVAL_BOOTSTRAP)
#include "eval/bootstrap_eval.hpp"
#else
#error "no evaluator selected: configure with FORK_EVALUATOR=bootstrap"
#endif

namespace forkeng {

inline int static_eval(const Position& pos) {
#if defined(FORK_EVAL_BOOTSTRAP)
  return bootstrap_eval(pos);
#endif
}

}  // namespace forkeng
