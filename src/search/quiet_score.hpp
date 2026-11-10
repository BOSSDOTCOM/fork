// SPDX-License-Identifier: GPL-3.0-or-later

// quiet_score: how a quiet move's history entries combine into its ordering
// score (DESIGN.md §5.2, deliverable 5; tier 2 T10), the heuristic-discovery
// loop's second evolvable region (ideas.md idea 23, the ordering pilot of
// 2026-11-09; tools/evolve/).
//
// Purpose: one function, quiet_score, that both the move selector
// (MoveSelector::score_quiets) and quiet_order_score (move_selector.hpp)
// call, so the loop replaces the combination in one place.
// Invariants:
// - Only the body between the markers may change; tools/evolve/regions.py
//   rejects anything else. The committed body is the butterfly entry plus
//   the reply entry times ReplyWeight / 4 and the follow entry times
//   FollowWeight / 4, each only when its arrival exists: exactly the score
//   the selector used before this function existed (bench unchanged).
// - Pure integer arithmetic on its inputs: no state, no allocation, the
//   same output for the same inputs (constexpr, so a compiler rejects a body
//   that is not). The caller clamps the result to [-INT16_MAX, INT16_MAX]
//   (the selector's int16 score array), so any int result is safe; a body's
//   own arithmetic must not overflow int at the inputs' extremes
//   (tests/test_ordering.cpp evaluates it there in a constant expression,
//   where signed overflow does not compile).
#pragma once

namespace forkeng {

// A quiet move's history entries and the weights that combine them. Every
// entry lies in [-HistoryMax, HistoryMax] (HistoryMax = 10,000,
// quiet_history.hpp); an entry whose table or arrival is missing is 0, with
// its flag false.
struct QuietScoreInputs {
  int butterfly;      // the mover's butterfly history entry (from-square, to-square); 0 without the table
  int reply;          // the reply table's entry: this move after the opponent's last move
  int follow;         // the follow table's entry: this move after the side's own previous move
  bool has_reply;     // the node has an arrival for the reply table (not the root, not after a null move)
  bool has_follow;    // the node has an arrival for the follow table
  int reply_weight;   // ReplyWeight (the parameter table), in quarters: 6 = 1.5
  int follow_weight;  // FollowWeight, in quarters: 4 = 1.0
};

constexpr int quiet_score(const QuietScoreInputs& s) {
  // FORK-EVOLVE-BEGIN quiet_order
  int score = s.butterfly;
  if (s.has_reply) score += s.reply * s.reply_weight / 4;
  if (s.has_follow) score += s.follow * s.follow_weight / 4;
  return score;
  // FORK-EVOLVE-END quiet_order
}

}  // namespace forkeng
