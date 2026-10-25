// score_bounds: the search's score scale (DESIGN.md §5.2, deliverable 2).
//
// Purpose: the constants and helpers that place evaluations, tablebase
// results and mates on one integer scale, and the conversion of mate and
// tablebase scores between "from the root" and "from this node" for the TT.
// Invariants:
// - Every score fits in 16 bits: |score| <= ScoreInfinite < 32767.
// - Bands, from the top: a mate found at ply n scores MateScore - n, in
//   [MateScore - MaxPly, MateScore]; a tablebase win at ply n scores
//   TbWinScore - n, in [TbWinScore - MaxPly, TbWinScore]; evaluations stay
//   within [-EvalLimit, EvalLimit] (eval/eval.hpp), far below both. Losses
//   mirror wins. The bands do not overlap.
// - Draws score 0 (contempt is Phase 7).
// - Values are Fork's own choice, not taken from any engine.
#pragma once

#include <algorithm>
#include <cstdlib>

#include "eval/eval.hpp"

namespace forkeng {

// The deepest ply a search may reach (root = ply 0). Bounds the search stack.
constexpr int MaxPly = 250;

constexpr int ScoreInfinite = 31000;
constexpr int ScoreNone = 32000;  // "no score" (e.g. no static eval in check); never compared
constexpr int MateScore = 30000;
constexpr int TbWinScore = 29500;

static_assert(MateScore - MaxPly > TbWinScore && TbWinScore - MaxPly > EvalLimit);
static_assert(ScoreInfinite > MateScore && ScoreNone < 32767);

constexpr int mate_score(int ply) { return MateScore - ply; }    // we mate at `ply`
constexpr int mated_score(int ply) { return -MateScore + ply; }  // we are mated at `ply`

constexpr bool is_mate_score(int s) { return std::abs(s) >= MateScore - MaxPly; }
// A forced result: a mate or a tablebase win or loss.
constexpr bool is_tb_or_mate(int s) { return std::abs(s) >= TbWinScore - MaxPly; }

// Mate and tablebase scores count plies from the root; the TT stores them
// counted from the node, so an entry stays right wherever it is found.
constexpr int score_to_tt(int s, int ply) {
  if (s >= TbWinScore - MaxPly) return s + ply;
  if (s <= -(TbWinScore - MaxPly)) return s - ply;
  return s;
}
// A result too far below this node to count from the root within MaxPly
// stays at the bottom of its band (review, 2026-10-24: it fell out of it).
constexpr int score_from_tt(int s, int ply) {
  if (s >= MateScore - MaxPly) return std::max(s - ply, MateScore - MaxPly);
  if (s <= -(MateScore - MaxPly)) return std::min(s + ply, -(MateScore - MaxPly));
  if (s >= TbWinScore - MaxPly) return std::max(s - ply, TbWinScore - MaxPly);
  if (s <= -(TbWinScore - MaxPly)) return std::min(s + ply, -(TbWinScore - MaxPly));
  return s;
}

// Moves to mate for UCI "score mate N": positive when we mate.
constexpr int mate_in_moves(int s) { return s > 0 ? (MateScore - s + 1) / 2 : -(MateScore + s) / 2; }

}  // namespace forkeng
