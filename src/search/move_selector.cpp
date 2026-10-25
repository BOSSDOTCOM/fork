#include "search/move_selector.hpp"

#include <utility>

#include "core/movegen.hpp"
#include "eval/bootstrap_eval.hpp"
#include "search/see.hpp"

namespace forkeng {

namespace {

// Evasion order: captures and promotions above every quiet move.
constexpr int EvasionCaptureBase = 1 << 20;

// Most valuable victim first, then least valuable attacker; a promotion
// counts its gain as part of the victim.
int victim_attacker_score(const Position& pos, Move m) {
  const int victim =
      m.is_capture() ? piece_value(m.is_en_passant() ? Pawn : kind_of(pos.piece_at(m.to()))) : 0;
  const int promo = m.is_promotion() ? piece_value(m.promo_type()) : 0;
  return (victim + promo) * 8 - kind_of(pos.piece_at(m.from()));
}

bool is_under_promotion(Move m) { return m.is_promotion() && m.promo_type() != Queen; }

}  // namespace

void MoveSelector::start_main(const Position& pos, Move tt_move, const QuietHistory* history) {
  pos_ = &pos;
  history_ = history;
  quiesce_ = false;
  see_filter_ = false;
  quiets_stopped_ = false;
  deferred_.count = 0;
  deferred_next_ = 0;
  tt_move_ = !tt_move.is_none() && pos.is_pseudo_legal(tt_move) && pos.is_legal(tt_move) ? tt_move : NoMove;
  stage_ = SelectorStage::TtMove;
}

void MoveSelector::start_quiesce(const Position& pos, Move tt_move, bool see_filter,
                                 const QuietHistory* history) {
  start_main(pos, tt_move, history);
  quiesce_ = true;
  see_filter_ = see_filter;
  // Out of check, the TT move counts only if the capture search would try it.
  if (!tt_move_.is_none() && !pos.in_check()) {
    const bool kind = tt_move_.is_capture() || tt_move_.is_promotion();
    const bool filtered = is_under_promotion(tt_move_) ||
                          (see_filter && tt_move_.is_capture() && !see_at_least(pos, tt_move_, 0));
    if (!kind || filtered) tt_move_ = NoMove;
  }
}

void MoveSelector::score_captures() {
  for (std::size_t i = 0; i < list_.size(); ++i) scores_[i] = victim_attacker_score(*pos_, list_[i]);
}

void MoveSelector::score_quiets() {
  const Color us = pos_->side_to_move();
  for (std::size_t i = 0; i < list_.size(); ++i) scores_[i] = history_ ? history_->value(us, list_[i]) : 0;
}

void MoveSelector::score_evasions() {
  const Color us = pos_->side_to_move();
  for (std::size_t i = 0; i < list_.size(); ++i) {
    const Move m = list_[i];
    scores_[i] = m.is_capture() || m.is_promotion() ? EvasionCaptureBase + victim_attacker_score(*pos_, m)
                 : history_                         ? history_->value(us, m)
                                                    : 0;
  }
}

// Partial selection sort: the best remaining move (the lowest current index
// on ties) is swapped to next_. Deterministic, but the swaps mean equal
// scores do not stay in generation order (review, deliverable 5).
std::size_t MoveSelector::select_best() {
  std::size_t best = next_;
  for (std::size_t j = next_ + 1; j < list_.size(); ++j)
    if (scores_[j] > scores_[best]) best = j;
  if (best != next_) {
    std::swap(list_.moves[next_], list_.moves[best]);
    std::swap(scores_[next_], scores_[best]);
  }
  return next_++;
}

Move MoveSelector::take_next() {
  for (;;) {
    switch (stage_) {
      case SelectorStage::TtMove:
        stage_ = pos_->in_check() ? SelectorStage::MakeEvasions
                 : quiesce_       ? SelectorStage::MakeQuiesce
                                  : SelectorStage::MakeCaptures;
        if (!tt_move_.is_none()) return tt_move_;
        break;

      case SelectorStage::MakeCaptures:
        list_.count = 0;
        generate<GenMode::Captures>(*pos_, list_);
        score_captures();
        next_ = 0;
        stage_ = SelectorStage::GoodCaptures;
        break;

      case SelectorStage::GoodCaptures:
        while (next_ < list_.size()) {
          const Move m = list_[select_best()];
          if (m == tt_move_) continue;
          if (is_under_promotion(m) || (m.is_capture() && !see_at_least(*pos_, m, 0))) {
            deferred_.add(m);
            continue;
          }
          return m;
        }
        stage_ = SelectorStage::MakeQuiets;
        break;

      case SelectorStage::MakeQuiets:
        stage_ = SelectorStage::BadCaptures;
        if (quiets_stopped_) break;
        list_.count = 0;
        generate<GenMode::Quiets>(*pos_, list_);
        score_quiets();
        next_ = 0;
        stage_ = SelectorStage::Quiets;
        break;

      case SelectorStage::Quiets:
        while (!quiets_stopped_ && next_ < list_.size()) {
          const Move m = list_[select_best()];
          if (m != tt_move_) return m;
        }
        stage_ = SelectorStage::BadCaptures;
        break;

      case SelectorStage::BadCaptures:
        while (deferred_next_ < deferred_.size()) {
          const Move m = deferred_[deferred_next_++];
          if (m != tt_move_) return m;
        }
        stage_ = SelectorStage::Done;
        break;

      case SelectorStage::MakeEvasions:
        list_.count = 0;
        generate<GenMode::Legal>(*pos_, list_);
        score_evasions();
        next_ = 0;
        stage_ = SelectorStage::Evasions;
        break;

      case SelectorStage::Evasions:
        while (next_ < list_.size()) {
          const Move m = list_[select_best()];
          if (m != tt_move_) return m;
        }
        stage_ = SelectorStage::Done;
        break;

      case SelectorStage::MakeQuiesce:
        list_.count = 0;
        generate<GenMode::Captures>(*pos_, list_);
        score_captures();
        next_ = 0;
        stage_ = SelectorStage::QuiesceCaptures;
        break;

      case SelectorStage::QuiesceCaptures:
        while (next_ < list_.size()) {
          const Move m = list_[select_best()];
          if (m == tt_move_ || is_under_promotion(m)) continue;
          if (see_filter_ && m.is_capture() && !see_at_least(*pos_, m, 0)) continue;
          return m;
        }
        stage_ = SelectorStage::Done;
        break;

      case SelectorStage::Done:
        return NoMove;
    }
  }
}

}  // namespace forkeng
