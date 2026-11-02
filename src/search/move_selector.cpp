// SPDX-License-Identifier: GPL-3.0-or-later

#include "search/move_selector.hpp"

#include <algorithm>
#include <cstdint>

#include <utility>

#include "core/material.hpp"
#include "core/movegen.hpp"
#include "search/see.hpp"

namespace forkeng {

namespace {

// Evasion order: captures and promotions above every quiet move, whose
// history value is at most HistoryMax. With the largest victim-attacker
// score, (queen + queen promotion) * 8, every score fits the int16 score
// array (review claim (e), 2026-10-26: the array was int, 1,292 bytes).
constexpr int EvasionCaptureBase = HistoryMax + 1;
constexpr int LargestVictimAttackerScore = (piece_value(Queen) + piece_value(Queen)) * 8;
static_assert(EvasionCaptureBase + LargestVictimAttackerScore <= INT16_MAX);
static_assert(-HistoryMax >= INT16_MIN);

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

void MoveSelector::start_main(const Position& pos, Move tt_move, const QuietHistory* history,
                              const PairHistory* pairs, int arrival, int follow_arrival,
                              const TakeHistory* take_history, bool threat_aware) {
  pos_ = &pos;
  history_ = history;
  take_history_ = take_history;
  threat_aware_ = threat_aware;
  attacked_known_ = false;
  pair_history_ = pairs;
  arrival_ = static_cast<std::int16_t>(pairs ? arrival : NoArrival);
  follow_arrival_ = static_cast<std::int16_t>(pairs ? follow_arrival : NoArrival);
  quiesce_ = false;
  see_filter_ = false;
  quiets_stopped_ = false;
  quiet_checks_only_ = false;
  quiets_filtered_ = 0;
  deferred_.count = 0;
  deferred_next_ = 0;
  tt_move_ = !tt_move.is_none() && pos.is_pseudo_legal(tt_move) && pos.is_legal(tt_move) ? tt_move : NoMove;
  stage_ = SelectorStage::TtMove;
}

void MoveSelector::start_quiesce(const Position& pos, Move tt_move, bool see_filter,
                                 const QuietHistory* history, const TakeHistory* take_history,
                                 bool threat_aware) {
  start_main(pos, tt_move, history, nullptr, NoArrival, NoArrival, take_history, threat_aware);
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
  for (std::size_t i = 0; i < list_.size(); ++i) {
    const Move m = list_[i];
    if (!take_history_ || !m.is_capture()) {
      scores_[i] = static_cast<std::int16_t>(victim_attacker_score(*pos_, m));
      continue;
    }
    // The take history replaces the attacker term: the victim still counts
    // 8 per centipawn, and two entries at opposite limits differ by
    // 2 * HistoryMax * TakeWeight / 32 (2,500 at 4), so captures whose
    // victims are less than about 3.1 pawns apart can be reordered, never a
    // rook capture after a pawn capture (tests/test_ordering.cpp).
    const PieceType victim = m.is_en_passant() ? Pawn : kind_of(pos_->piece_at(m.to()));
    const int promo = m.is_promotion() ? piece_value(m.promo_type()) : 0;
    const int learned = take_history_->value(take_slot(pos_->piece_at(m.from()), m.to(), victim));
    scores_[i] = static_cast<std::int16_t>((piece_value(victim) + promo) * 8 + learned * TakeWeight / 32);
  }
}

void MoveSelector::score_quiets() {
  const Color us = pos_->side_to_move();
  const Bitboard attacked = history_ ? attacked_by_opponent() : 0;
  for (std::size_t i = 0; i < list_.size(); ++i) {
    const Move m = list_[i];
    int score = history_ ? history_->value(us, m, threat_bucket(attacked, m)) : 0;
    if (arrival_ != NoArrival || follow_arrival_ != NoArrival) {
      const int slot = pair_slot(pos_->piece_at(m.from()), m.to());
      if (arrival_ != NoArrival) score += pair_history_[ReplyTable].value(arrival_, slot) * ReplyWeight / 4;
      if (follow_arrival_ != NoArrival)
        score += pair_history_[FollowTable].value(follow_arrival_, slot) * FollowWeight / 4;
      // Weights above one can take the sum past int16 at the extremes.
      score = std::clamp(score, -INT16_MAX, INT16_MAX);
    }
    scores_[i] = static_cast<std::int16_t>(score);
  }
}

void MoveSelector::score_evasions() {
  const Color us = pos_->side_to_move();
  const Bitboard attacked = history_ ? attacked_by_opponent() : 0;
  for (std::size_t i = 0; i < list_.size(); ++i) {
    const Move m = list_[i];
    scores_[i] = static_cast<std::int16_t>(m.is_capture() || m.is_promotion()
                                               ? EvasionCaptureBase + victim_attacker_score(*pos_, m)
                                           : history_ ? history_->value(us, m, threat_bucket(attacked, m))
                                                      : 0);
  }
}

void MoveSelector::keep_quiet_checks() {
  quiet_checks_only_ = true;
  if (stage_ != SelectorStage::Quiets) return;  // later quiets are filtered when generated
  // Quiets already generated and scored: keep the checking ones not yet
  // yielded (with their scores), in their current order.
  std::size_t kept = next_;
  for (std::size_t i = next_; i < list_.size(); ++i) {
    if (pos_->gives_check(list_[i])) {
      list_.moves[kept] = list_[i];
      scores_[kept++] = scores_[i];
    } else if (list_[i] != tt_move_) {
      ++quiets_filtered_;
    }
  }
  list_.count = kept;
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
        if (quiet_checks_only_) {
          // Keep the checking quiets, in generation order; the TT move stays
          // out as before (it is skipped when yielded).
          std::size_t kept = 0;
          for (std::size_t i = 0; i < list_.size(); ++i)
            if (pos_->gives_check(list_[i]))
              list_.moves[kept++] = list_[i];
            else if (list_[i] != tt_move_)
              ++quiets_filtered_;
          list_.count = kept;
        }
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
