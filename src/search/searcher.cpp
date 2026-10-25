#include "search/searcher.hpp"

#include <algorithm>
#include <cstdlib>

#include "core/movegen.hpp"
#include "eval/bootstrap_eval.hpp"
#include "eval/eval.hpp"
#include "search/lmr_table.hpp"
#include "search/see.hpp"

namespace forkeng {

namespace {

// Fork's own starting values (Phase 3 settles structure, not tuning).
// Aspiration (measured on the bench, DESIGN.md §5.2 "Search constants"): from
// depth 5, nine in ten iterations move the score by at most 12 cp.
constexpr int AspirationMinDepth = 5;              // iterations before this use the full window
constexpr int AspirationWindow = 12;               // first half-width, in centipawns
constexpr std::uint64_t StopCheckInterval = 1024;  // nodes between clock and stop-flag polls
constexpr std::int64_t FailReportMs = 1000;        // aspiration fails are reported only after this

// Tier 1 pruning and reductions (deliverable 6). Every value has its
// justification in DESIGN.md §5.2 ("Search constants"); all move into the
// parameter table in deliverable 8b and are retuned after Phase 4 (they
// depend on the evaluation's scale).
constexpr int RfpMaxDepth = 6;
constexpr int RfpMargin = 80;  // centipawns per ply of remaining depth
constexpr int NullMinDepth = 3;
// The null search gets half the remaining depth, less one ply, and one ply
// less again per NullSurplusPerPly of static eval above beta (at most
// NullSurplusPliesMax).
constexpr int NullSurplusPerPly = 300;  // the bootstrap evaluation's knight value (bootstrap_eval.cpp)
constexpr int NullSurplusPliesMax = 2;
constexpr int LmrMinDepth = 3;
constexpr int LmrMinMove = 4;  // the first three moves searched are never reduced
constexpr int LmpMaxDepth = 4;
// Quiet moves searched at depth d before the rest are pruned:
// LmpQuietAllowance + d (measured, DESIGN.md §5.2).
constexpr int LmpQuietAllowance = 12;
constexpr int FutilityMaxDepth = 6;
constexpr int FutilityOffset = 100;  // the futility margin is FutilityOffset + FutilityGrowth * depth
constexpr int FutilityGrowth = 70;
constexpr int SeePruneMaxDepth = 6;
constexpr int QuietSeeFloor = 60;     // a quiet may lose at most this much by SEE, per ply of depth
constexpr int CaptureSeeFloor = 100;  // a capture likewise

// The side has a piece other than pawns and its king (the null move's main
// zugzwang guard: pawn endings are where passing is most often best).
bool has_non_pawn_material(const Position& pos, Color c) {
  return (pos.pieces(c) & ~pos.pieces(Pawn) & ~pos.pieces(King)) != 0;
}

}  // namespace

std::int64_t Searcher::elapsed_ms() const {
  return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start_)
      .count();
}

bool Searcher::poll_limits() {
  if (stopped_) return true;
  if (limits_->nodes && nodes_ >= limits_->nodes) return stopped_ = true;
  if (nodes_ % StopCheckInterval != 0) return false;
  if (stop_->load(std::memory_order_relaxed)) return stopped_ = true;
  const bool timed = !(pondering_ && pondering_->load(std::memory_order_relaxed));
  if (timed && limits_->hard_ms >= 0 && elapsed_ms() >= limits_->hard_ms) return stopped_ = true;
  return false;
}

// A quiet move cut off: it gains a bonus that grows with depth, and the
// quiet moves tried before it here lose as much (the malus).
void Searcher::record_cutoff(const PlyFrame& f, Move m, int depth) {
  if (!switches.use_history) return;
  const Color us = pos_->side_to_move();
  const int bonus = bonus_for_depth(depth);
  history_.apply(us, m, bonus);
  if (switches.use_history_malus)
    for (Move q : f.failed_quiets) history_.apply(us, q, -bonus);
}

void Searcher::update_pv(int ply, Move m) {
  PrincipalLine& line = pv_[ply];
  const PrincipalLine& child = pv_[ply + 1];
  line.moves[0] = m;
  std::copy(child.moves, child.moves + child.length, line.moves + 1);
  line.length = child.length + 1;
}

template <bool OnPv>
int Searcher::negamax(int alpha, int beta, int depth, int ply) {
  if (depth <= 0 && switches.use_quiesce) return quiesce<OnPv>(alpha, beta, ply);
  pv_[ply].length = 0;
  ++nodes_;
  if (poll_limits()) return 0;
  max_ply_reached_ = std::max(max_ply_reached_, ply);
  Position& pos = *pos_;
  PlyFrame& f = frames_[ply];
  const bool in_check = pos.in_check();

  // Draws: repetition (one earlier occurrence is enough inside the search),
  // insufficient material, and the 50-move rule unless this move is mate.
  if (pos.repetition_count() >= 2 || pos.insufficient_material()) return 0;
  if (pos.fifty_move_reached()) {
    if (!in_check) return 0;
    f.moves.count = 0;
    generate<GenMode::Legal>(pos, f.moves);
    return f.moves.size() ? 0 : mated_score(ply);
  }
  if (ply >= MaxPly) return in_check ? 0 : static_eval(pos);
  if (depth <= 0) return static_eval(pos);  // only with the quiescence search switched off

  if (switches.use_mate_distance) {
    alpha = std::max(alpha, mated_score(ply));
    beta = std::min(beta, mate_score(ply + 1));
    if (alpha >= beta) return alpha;
  }

  // The TT: a cutoff at non-PV nodes when the entry is deep enough and its
  // bound points the right way; otherwise its move is tried first. Moves come
  // from the legal generator, so a colliding entry's move is never played
  // unless it is legal here.
  const Key key = pos.key();
  TtHit hit{};
  const bool tt_hit = switches.use_tt && tt_.fetch(key, hit);
  if (tt_hit && !OnPv) {
    const int s = score_from_tt(hit.score, ply);
    const bool deep_enough = switches.tt_exact_depth ? hit.depth == depth : hit.depth >= depth;
    if (deep_enough && (hit.bound == TtBound::Exact || (hit.bound == TtBound::Lower && s >= beta) ||
                        (hit.bound == TtBound::Upper && s <= alpha)))
      return s;
  }

  f.static_eval = in_check ? ScoreNone : static_eval(pos);
  const bool can_prune = !OnPv && !in_check;

  // Reverse futility pruning (T20): far enough above beta at shallow depth,
  // the node fails high without a search.
  if (switches.use_rfp && can_prune && depth <= RfpMaxDepth && !is_tb_or_mate(beta) &&
      f.static_eval - RfpMargin * depth >= beta) {
#ifdef FORK_SEARCH_STATS
    ++counters.rfp_cuts;
#endif
    return f.static_eval;
  }

  // Null move pruning (T13): if passing still fails high on a reduced
  // search, the node is taken to fail high.
  if (switches.use_nmp && can_prune && depth >= NullMinDepth && !f.after_null && !is_tb_or_mate(beta) &&
      f.static_eval >= beta && has_non_pawn_material(pos, pos.side_to_move())) {
    const int surplus_plies = std::min((f.static_eval - beta) / NullSurplusPerPly, NullSurplusPliesMax);
    const int null_depth = depth / 2 - 1 - surplus_plies;  // 0 or less: the quiescence search
    pos.make_null();
    frames_[ply + 1].after_null = true;
    const int score = -negamax<false>(-beta, -beta + 1, null_depth, ply + 1);
    frames_[ply + 1].after_null = false;
    pos.unmake_null();
    if (stopped_) return 0;
    if (score >= beta) {
#ifdef FORK_SEARCH_STATS
      ++counters.null_cuts;
#endif
      return is_tb_or_mate(score) ? beta : score;  // a mate found after passing is not trusted
    }
  }

  // The selector checks the TT move (a colliding entry's move may not be
  // legal here) before it is tried first.
  f.selector.start_main(pos, tt_hit ? hit.move : NoMove, switches.use_history ? &history_ : nullptr);
  f.failed_quiets.count = 0;

  const int alpha_start = alpha;
  int best = -ScoreInfinite;
  Move best_move = NoMove;
  int moves_searched = 0;
  int moves_seen = 0;  // legal moves the selector yielded, searched or pruned
  int quiets_searched = 0;
  const bool lmp_node = switches.use_lmp && can_prune && depth <= LmpMaxDepth;
  const int futility_value = in_check ? 0 : f.static_eval + FutilityOffset + FutilityGrowth * depth;
  const bool futile_node = switches.use_futility && can_prune && depth <= FutilityMaxDepth &&
                           !is_tb_or_mate(alpha) && futility_value <= alpha;
  for (Move m; !(m = f.selector.take_next()).is_none();) {
    ++moves_seen;
    const bool quiet = !m.is_capture() && !m.is_promotion();
    // Pruning: only once a move has been searched (so no node is pruned into
    // a false stalemate or mate) and while not already losing to a mate.
    if (moves_searched > 0 && best > -(MateScore - MaxPly)) {
      if (lmp_node && quiet && quiets_searched >= LmpQuietAllowance + depth) {
        f.selector.stop_quiets();  // late move pruning (T21)
#ifdef FORK_SEARCH_STATS
        ++counters.lmp_prunes;
#endif
        continue;
      }
      if (futile_node && quiet) {
#ifdef FORK_SEARCH_STATS
        ++counters.gives_check_calls;
#endif
        if (!pos.gives_check(m)) {  // futility pruning (T22); the bound stays honest
          best = std::max(best, futility_value);
#ifdef FORK_SEARCH_STATS
          ++counters.futility_prunes;
#endif
          continue;
        }
      }
      if (switches.use_see_prune && can_prune && depth <= SeePruneMaxDepth &&
          !see_at_least(pos, m, -(quiet ? QuietSeeFloor : CaptureSeeFloor) * depth)) {
#ifdef FORK_SEARCH_STATS
        ++counters.see_prunes;
#endif
        continue;  // SEE pruning (T23)
      }
    }
    if (switches.use_tt) tt_.prefetch_bucket(pos.predicted_key(m));
    pos.make(m);
#ifdef FORK_SEARCH_STATS
    ++counters.makes;
#endif
    int score;
    if (moves_searched == 0 || !switches.use_pvs) {
      score = -negamax<OnPv>(-beta, -alpha, depth - 1, ply + 1);
    } else {
      // Late move reductions (T15): late quiet moves get a reduced
      // zero-window search first, then the full depth if they beat alpha.
      const int new_depth = depth - 1;
      int reduced = new_depth;
      if (switches.use_lmr && depth >= LmrMinDepth && moves_searched + 1 >= LmrMinMove && quiet && !in_check)
        reduced = std::clamp(new_depth - reduction_for(depth, moves_searched + 1), 1, new_depth);
      score = -negamax<false>(-alpha - 1, -alpha, reduced, ply + 1);
#ifdef FORK_SEARCH_STATS
      counters.lmr_searches += reduced < new_depth;
      counters.lmr_researches += reduced < new_depth && score > alpha;
#endif
      if (score > alpha && reduced < new_depth)
        score = -negamax<false>(-alpha - 1, -alpha, new_depth, ply + 1);
      if (OnPv && score > alpha && score < beta) score = -negamax<true>(-beta, -alpha, new_depth, ply + 1);
    }
    pos.unmake(m);
    if (stopped_) return 0;
    ++moves_searched;
    quiets_searched += quiet;
    if (score > best) {
      best = score;
      if (score > alpha) {
        best_move = m;
        if (OnPv) update_pv(ply, m);
        if (score >= beta) {
          if (quiet) record_cutoff(f, m, depth);
#ifdef FORK_SEARCH_STATS
          if (quiet && !OnPv && !in_check && depth < SearchCounters::CutoffDepths)
            ++counters.quiet_cutoff_index[depth]
                                         [std::min(quiets_searched - 1, SearchCounters::CutoffIndices - 1)];
#endif
#ifdef FORK_SEARCH_STATS
          ++counters.beta_cutoffs;
          counters.first_move_cutoffs += moves_searched == 1;
          counters.cutoff_index_sum += static_cast<std::uint64_t>(moves_searched - 1);
#endif
          break;
        }
        alpha = score;
      }
    }
    if (quiet) f.failed_quiets.add(m);
  }
  // No legal move is mate or stalemate; legal moves that were all pruned are
  // not (the guard above prevents it; this keeps the result right regardless).
  if (moves_seen == 0) return in_check ? mated_score(ply) : 0;
  if (moves_searched == 0) return best;
  if (switches.use_tt) {
    const TtBound bound = best >= beta                 ? TtBound::Lower
                          : OnPv && best > alpha_start ? TtBound::Exact
                                                       : TtBound::Upper;
    tt_.deposit(key, best_move, score_to_tt(best, ply), f.static_eval, depth, bound, OnPv);
  }
  return best;
}

// The quiescence search: at the horizon, only captures and queen promotions
// are searched (all evasions in check), and the side to move may stand pat
// on the static evaluation unless it is in check. Captures that lose
// material by SEE are skipped.
template <bool OnPv>
int Searcher::quiesce(int alpha, int beta, int ply) {
  pv_[ply].length = 0;
  ++nodes_;
  if (poll_limits()) return 0;
  max_ply_reached_ = std::max(max_ply_reached_, ply);
  Position& pos = *pos_;
  PlyFrame& f = frames_[ply];
  const bool in_check = pos.in_check();

  if (pos.repetition_count() >= 2 || pos.insufficient_material()) return 0;
  if (pos.fifty_move_reached()) {
    if (!in_check) return 0;
    f.moves.count = 0;
    generate<GenMode::Legal>(pos, f.moves);
    return f.moves.size() ? 0 : mated_score(ply);
  }
  if (ply >= MaxPly) return in_check ? 0 : static_eval(pos);

  const Key key = pos.key();
  TtHit hit{};
  const bool tt_hit = switches.use_tt && tt_.fetch(key, hit);
  if (tt_hit && !OnPv && (!switches.tt_exact_depth || hit.depth == 0)) {
    const int s = score_from_tt(hit.score, ply);
    if (hit.bound == TtBound::Exact || (hit.bound == TtBound::Lower && s >= beta) ||
        (hit.bound == TtBound::Upper && s <= alpha))
      return s;
  }

  const int alpha_start = alpha;
  int best = -ScoreInfinite;
  if (in_check) {
    f.static_eval = ScoreNone;
  } else {
    f.static_eval = static_eval(pos);
    best = f.static_eval;
    if (best >= beta) {
      if (switches.use_tt)
        tt_.deposit(key, NoMove, score_to_tt(best, ply), f.static_eval, 0, TtBound::Lower, OnPv);
      return best;
    }
    alpha = std::max(alpha, best);
  }
  // Captures and queen promotions (under-promotions dropped, and with the SEE
  // filter captures that lose material), or every evasion in check.
  f.selector.start_quiesce(pos, tt_hit ? hit.move : NoMove, switches.use_see_quiesce,
                           switches.use_history ? &history_ : nullptr);

  Move best_move = NoMove;
  int moves_searched = 0;
  for (Move m; !(m = f.selector.take_next()).is_none();) {
    ++moves_searched;
    if (switches.use_tt) tt_.prefetch_bucket(pos.predicted_key(m));
    pos.make(m);
#ifdef FORK_SEARCH_STATS
    ++counters.makes;
#endif
    const int score = -quiesce<OnPv>(-beta, -alpha, ply + 1);
    pos.unmake(m);
    if (stopped_) return 0;
    if (score > best) {
      best = score;
      if (score > alpha) {
        best_move = m;
        if (OnPv) update_pv(ply, m);
        if (score >= beta) break;
        alpha = score;
      }
    }
  }
  if (in_check && moves_searched == 0) return mated_score(ply);
  if (switches.use_tt) {
    const TtBound bound = best >= beta                 ? TtBound::Lower
                          : OnPv && best > alpha_start ? TtBound::Exact
                                                       : TtBound::Upper;
    tt_.deposit(key, best_move, score_to_tt(best, ply), f.static_eval, 0, bound, OnPv);
  }
  return best;
}

int Searcher::search_root(int alpha, int beta, int depth) {
  Position& pos = *pos_;
  ++nodes_;
  pv_[0].length = 0;
  int best = -ScoreInfinite;
  std::size_t best_index = 0;  // the move that last raised alpha
  for (std::size_t i = 0; i < root_count_; ++i) {
    const Move m = root_moves_[i].move;
    pos.make(m);
    int score;
    if (i == 0 || !switches.use_pvs) {
      score = -negamax<true>(-beta, -alpha, depth - 1, 1);
    } else {
      score = -negamax<false>(-alpha - 1, -alpha, depth - 1, 1);
      if (score > alpha && score < beta) score = -negamax<true>(-beta, -alpha, depth - 1, 1);
    }
    pos.unmake(m);
    if (stopped_) return best;
    if (score > best) best = score;
    if (score > alpha) {
      best_index = i;
      update_pv(0, m);
      if (score < beta) {
        iteration_best_ = m;
        iteration_best_score_ = score;
        iteration_pv_ = pv_[0];
        alpha = score;
      } else {
        break;
      }
    }
  }
  // Move to front: the move that last raised alpha is searched first next
  // time; the others keep their order.
  const RootEntry front = root_moves_[best_index];
  for (std::size_t i = best_index; i > 0; --i) root_moves_[i] = root_moves_[i - 1];
  root_moves_[0] = front;
  return best;
}

void Searcher::report_iteration(int depth, int score, int bound, const PrincipalLine& pv) {
  if (!listener_) return;
  const IterationReport r{depth,        max_ply_reached_,    score, bound, nodes_,
                          elapsed_ms(), tt_.fill_permille(), &pv};
  listener_->on_iteration(*pos_, r);
}

int Searcher::probe_zero_window(Position& pos, int beta, int depth, const std::atomic<bool>& stop) {
  static const SearchLimits no_limits;
  start_ = std::chrono::steady_clock::now();
  pos_ = &pos;
  limits_ = &no_limits;
  stop_ = &stop;
  pondering_ = nullptr;
  listener_ = nullptr;
  nodes_ = 0;
  max_ply_reached_ = 0;
  stopped_ = false;
  frames_[0].after_null = false;
  return negamax<false>(beta - 1, beta, depth, 0);
}

SearchResult Searcher::explore(Position& pos, const SearchLimits& limits, const std::atomic<bool>& stop,
                               const std::atomic<bool>* pondering, SearchListener* listener) {
  start_ = limits.go_received.value_or(std::chrono::steady_clock::now());
  pos_ = &pos;
  limits_ = &limits;
  stop_ = &stop;
  pondering_ = pondering;
  listener_ = listener;
  nodes_ = 0;
  max_ply_reached_ = 0;
  stopped_ = false;

  tt_.advance_age();
  SearchResult result;
  // The first iteration's root order is the selector's (no TT move).
  PlyFrame& root = frames_[0];
  root.moves.count = 0;
  root.selector.start_main(pos, NoMove, switches.use_history ? &history_ : nullptr);
  for (Move m; !(m = root.selector.take_next()).is_none();) root.moves.add(m);
  root_count_ = 0;
  for (Move m : root.moves)
    if (limits.restrict_to.size() == 0 || limits.restrict_to.contains(m)) root_moves_[root_count_++] = {m};
  if (root_count_ == 0)  // no searchmoves move is legal: search every move
    for (Move m : root.moves) root_moves_[root_count_++] = {m};
  if (root_count_ == 0) {
    result.score = pos.in_check() ? mated_score(0) : 0;
    return result;
  }
  result.best = root_moves_[0].move;

  int previous = 0;
  for (int depth = 1; depth <= std::min(limits.depth, MaxPly - 1); ++depth) {
    iteration_best_ = NoMove;
    iteration_best_score_ = -ScoreInfinite;
    int delta = AspirationWindow;
    int alpha = -ScoreInfinite, beta = ScoreInfinite;
    if (switches.use_aspiration && depth >= AspirationMinDepth && !is_tb_or_mate(previous)) {
      alpha = std::max(previous - delta, -ScoreInfinite);
      beta = std::min(previous + delta, ScoreInfinite);
    }
    int score;
    for (;;) {
      score = search_root(alpha, beta, depth);
      if (stopped_) break;
      if (score > alpha && score < beta) break;
      if (elapsed_ms() >= FailReportMs) report_iteration(depth, score, score <= alpha ? -1 : 1, pv_[0]);
      // Only the failing side moves. The half-width grows by how far the
      // fail-soft score already is from the previous iteration's: at least
      // the old half-width (the score fell outside the window), more after a
      // big jump. A decisive score opens that side fully.
      delta = std::min(delta + std::abs(score - previous), ScoreInfinite);
      if (score <= alpha) {
        alpha = is_tb_or_mate(score) ? -ScoreInfinite : std::max(score - delta, -ScoreInfinite);
      } else {
        beta = is_tb_or_mate(score) ? ScoreInfinite : std::min(score + delta, ScoreInfinite);
      }
    }
    if (stopped_) {
      // An unfinished iteration counts only through a move that came back
      // with an exact score above the last finished iteration's best.
      if (!iteration_best_.is_none() && result.depth > 0 && iteration_best_score_ > previous) {
        result.best = iteration_best_;
        result.score = iteration_best_score_;
        report_iteration(depth, iteration_best_score_, 0,
                         iteration_pv_);  // the last info names the move played
      }
      break;
    }
    previous = score;
    result.best = root_moves_[0].move;
    result.score = score;
    result.depth = depth;
    report_iteration(depth, score, 0, pv_[0]);
    if (limits.mate_moves > 0 && is_mate_score(score) && score > 0 &&
        mate_in_moves(score) <= limits.mate_moves)
      break;
    const bool timed = !(pondering && pondering->load(std::memory_order_relaxed));
    if (timed && limits.soft_ms >= 0 && elapsed_ms() >= limits.soft_ms) break;
  }
  result.nodes = nodes_;
  return result;
}

}  // namespace forkeng
