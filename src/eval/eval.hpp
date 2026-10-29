// SPDX-License-Identifier: GPL-3.0-or-later

// eval: the static evaluation the search calls, chosen when Fork is built.
//
// Purpose: one entry point, static_eval(), whose implementation is fixed at
// build time (owner, 2026-10-24: no runtime interface and no indirect call;
// DESIGN.md §5.2 deliverable 1), selected by the FORK_EVALUATOR CMake
// option: the bootstrap evaluation (Phase 3), or the network (Phase 4,
// DESIGN.md §5.3), whose file FORK_NET is compiled in. Inside the search the
// network is kept incrementally (search/searcher.cpp, FeatureStack);
// static_eval() itself evaluates a position from scratch.
// Invariants:
// - Scores are centipawns from the side to move's view, within
//   [-EvalLimit, EvalLimit], far below the tablebase and mate bands.
// - Deterministic: no floating point, no state that changes, no allocation
//   after the network is read once (embedded_net()).
#pragma once

#include "core/position.hpp"
#include "eval/eval_scale.hpp"

#if defined(FORK_EVAL_BOOTSTRAP)
#include "eval/bootstrap_eval.hpp"
#elif defined(FORK_EVAL_NNUE)
#include "eval/nnue/accumulator.hpp"
#include "eval/nnue/net_file.hpp"
#else
#error "no evaluator selected: configure with FORK_EVALUATOR=bootstrap or nnue"
#endif

namespace forkeng {

#if defined(FORK_EVAL_NNUE)
// The network compiled into this build, read and validated on first use.
const NetFile& embedded_net();
#endif

inline int static_eval(const Position& pos) {
#if defined(FORK_EVAL_BOOTSTRAP)
  return bootstrap_eval(pos);
#elif defined(FORK_EVAL_NNUE)
  Accumulator acc;
  accumulate_board(embedded_net(), pos, acc);
  return output_layer(embedded_net(), acc, pos.side_to_move());
#endif
}

}  // namespace forkeng
