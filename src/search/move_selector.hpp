// SPDX-License-Identifier: GPL-3.0-or-later

// move_selector: the staged move picker (DESIGN.md §5.2, deliverable 5; KB
// search-techniques.md T8).
//
// Purpose: hand the search its moves one at a time, best first, generating
// each group only when it is reached, so a cutoff by the TT move or a good
// capture never pays for generating the quiet moves.
// Invariants:
// - Main search, not in check: the TT move (if it is legal here), then good
//   captures and queen promotions by most valuable victim and least valuable
//   attacker, a capture that loses material by SEE being deferred when it
//   comes up (SEE is computed only for the captures reached), then quiet
//   moves by butterfly history (its threat bucket when threat-aware;
//   generation order without a history), then
//   the deferred bad captures and under-promotions, in the order deferred.
// - In check (main search and quiescence): the TT move, then every evasion,
//   captures first (by victim and attacker), then quiets by history.
// - Quiescence, not in check: the TT move if it qualifies, then captures and
//   queen promotions by victim and attacker; under-promotions are dropped,
//   and with the SEE filter so are captures that lose by SEE.
// - Every move is yielded at most once (the TT move is skipped in its
//   stage), every yielded move is legal, and in the main search every legal
//   move is yielded unless stop_quiets() was called (tests/test_ordering.cpp).
// - No allocation; the selector lives in the search stack (PlyFrame).
#pragma once

#include <cstddef>
#include <cstdint>

#include "core/position.hpp"
#include "search/quiet_history.hpp"

namespace forkeng {

enum class SelectorStage : std::uint8_t {
  TtMove,
  MakeCaptures,
  GoodCaptures,
  MakeQuiets,
  Quiets,
  BadCaptures,
  MakeEvasions,
  Evasions,
  MakeQuiesce,
  QuiesceCaptures,
  Done
};

class MoveSelector {
 public:
  // Main search. `history` may be null: quiets then keep generation order.
  // With `pairs` (tier 2, T10: the reply and follow tables, indexed
  // ReplyTable and FollowTable) a quiet move's score adds its reply entry
  // after the move that led here (`arrival`), times ReplyWeight / 4, and its
  // follow entry after the side's own previous move (`follow_arrival`), times
  // FollowWeight / 4; NoArrival leaves a table out. Evasions keep the
  // butterfly history alone.
  // With `take_history` (tier 2, T11) a capture's score is its victim's
  // value (with any promotion's gain) times 8 plus its take history entry
  // times TakeWeight / 32, instead of MVV-LVA; evasions keep MVV-LVA.
  // With `threat_aware` (tier 2, T56) quiets and quiet evasions read the
  // butterfly history's threat bucket (quiet_history.hpp) for the opponent's
  // attacks in this position; without it, bucket 0.
  void start_main(const Position& pos, Move tt_move, const QuietHistory* history,
                  const PairHistory* pairs = nullptr, int arrival = NoArrival, int follow_arrival = NoArrival,
                  const TakeHistory* take_history = nullptr, bool threat_aware = false);
  // Quiescence search (all evasions when in check).
  void start_quiesce(const Position& pos, Move tt_move, bool see_filter, const QuietHistory* history,
                     const TakeHistory* take_history = nullptr, bool threat_aware = false);

  // The next move, or NoMove when there are no more.
  Move take_next();

  // From now on yields no more quiet moves (late move pruning, deliverable 6).
  void stop_quiets() { quiets_stopped_ = true; }
  // Quiet moves not yet generated will be only the checking ones (futility
  // pruning, review claim (d)); quiets_filtered() counts the others dropped.
  void keep_quiet_checks();
  int quiets_filtered() const { return quiets_filtered_; }
  // The moves of the stage being yielded from (for a late quiet: the quiets
  // generated at this node).
  int stage_size() const { return static_cast<int>(list_.size()); }

  // The stage the last move came from (search statistics only): a stage
  // still being yielded from, or the Make* stage after the TT move.
  SelectorStage yielding_stage() const { return stage_; }
  bool quiets_stopped() const { return quiets_stopped_; }

  // The squares the opponent attacks at this node, built at the first call
  // (the quiet or evasion stage, or the search's history update), so a node
  // cut before its quiets never pays for it; 0 unless threat-aware. The
  // position must still be this node's (no move made).
  Bitboard attacked_by_opponent() {
    if (!threat_aware_) return 0;
    if (!attacked_known_) {
      attacked_ = pos_->attacked_squares(~pos_->side_to_move());
      attacked_known_ = true;
    }
    return attacked_;
  }

 private:
  void score_captures();
  void score_quiets();
  void score_evasions();
  std::size_t select_best();  // index of the best remaining move in list_, from next_

  const Position* pos_ = nullptr;
  const QuietHistory* history_ = nullptr;
  const PairHistory* pair_history_ = nullptr;
  const TakeHistory* take_history_ = nullptr;
  std::int16_t arrival_ = NoArrival;
  std::int16_t follow_arrival_ = NoArrival;
  Move tt_move_ = NoMove;
  SelectorStage stage_ = SelectorStage::Done;
  bool quiesce_ = false;
  bool see_filter_ = false;
  bool quiets_stopped_ = false;
  bool quiet_checks_only_ = false;
  bool threat_aware_ = false;
  bool attacked_known_ = false;
  std::int16_t quiets_filtered_ = 0;  // at most MaxMoves; int16 keeps the flags above within the padding
  Bitboard attacked_ = 0;

  MoveList list_;                  // the stage's moves
  std::int16_t scores_[MaxMoves];  // every score fits (move_selector.cpp)
  std::size_t next_ = 0;
  MoveList deferred_;  // bad captures and under-promotions, tried after the quiets
  std::size_t deferred_next_ = 0;
};

}  // namespace forkeng
