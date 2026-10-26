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
//   moves by butterfly history (generation order without a history), then
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
  void start_main(const Position& pos, Move tt_move, const QuietHistory* history);
  // Quiescence search (all evasions when in check).
  void start_quiesce(const Position& pos, Move tt_move, bool see_filter, const QuietHistory* history);

  // The next move, or NoMove when there are no more.
  Move take_next();

  // From now on yields no more quiet moves (late move pruning, deliverable 6).
  void stop_quiets() { quiets_stopped_ = true; }

  // The stage the last move came from (search statistics only): a stage
  // still being yielded from, or the Make* stage after the TT move.
  SelectorStage yielding_stage() const { return stage_; }
  bool quiets_stopped() const { return quiets_stopped_; }

 private:
  void score_captures();
  void score_quiets();
  void score_evasions();
  std::size_t select_best();  // index of the best remaining move in list_, from next_

  const Position* pos_ = nullptr;
  const QuietHistory* history_ = nullptr;
  Move tt_move_ = NoMove;
  SelectorStage stage_ = SelectorStage::Done;
  bool quiesce_ = false;
  bool see_filter_ = false;
  bool quiets_stopped_ = false;

  MoveList list_;  // the stage's moves
  int scores_[MaxMoves];
  std::size_t next_ = 0;
  MoveList deferred_;  // bad captures and under-promotions, tried after the quiets
  std::size_t deferred_next_ = 0;
};

}  // namespace forkeng
