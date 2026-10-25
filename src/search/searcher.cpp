#include "search/searcher.hpp"

#include <algorithm>

#include "core/movegen.hpp"
#include "eval/bootstrap_eval.hpp"
#include "eval/eval.hpp"

namespace forkeng {

namespace {

// Fork's own starting values (Phase 3 settles structure, not tuning).
constexpr int AspirationMinDepth = 4;              // iterations before this use the full window
constexpr int AspirationWindow = 25;               // first half-width, in centipawns
constexpr std::uint64_t StopCheckInterval = 1024;  // nodes between clock and stop-flag polls
constexpr std::int64_t FailReportMs = 1000;        // aspiration fails are reported only after this

// Move ordering scores until the staged selector (deliverable 5): the TT
// move first, then captures and promotions by most valuable victim and
// least valuable attacker, then quiet moves in generation order.
constexpr int OrderCapture = 1 << 20;
constexpr int OrderTtMove = 1 << 30;

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

void Searcher::order_moves(PlyFrame& f, Move tt_move) const {
  for (std::size_t i = 0; i < f.moves.size(); ++i) {
    const Move m = f.moves[i];
    int s = 0;
    if (m == tt_move) {
      s = OrderTtMove;
    } else if (m.is_capture() || m.is_promotion()) {
      const int victim = m.is_capture() ? (m.is_en_passant() ? Pawn : kind_of(pos_->piece_at(m.to()))) : 0;
      const int promo = m.is_promotion() ? piece_value(m.promo_type()) : 0;
      s = OrderCapture + (piece_value(PieceType(victim)) + promo) * 8 - kind_of(pos_->piece_at(m.from()));
    }
    f.move_scores[i] = s;
  }
}

// Brings the best-scored move among i.. to position i (first one on ties).
void Searcher::pick_next(PlyFrame& f, std::size_t i) {
  std::size_t best = i;
  for (std::size_t j = i + 1; j < f.moves.size(); ++j)
    if (f.move_scores[j] > f.move_scores[best]) best = j;
  if (best != i) {
    std::swap(f.moves.moves[i], f.moves.moves[best]);
    std::swap(f.move_scores[i], f.move_scores[best]);
  }
}

void Searcher::update_pv(int ply, Move m) {
  PrincipalLine& line = pv_[ply];
  const PrincipalLine& child = pv_[ply + 1];
  line.moves[0] = m;
  std::copy(child.moves, child.moves + child.length, line.moves + 1);
  line.length = child.length + 1;
}

template <bool PvNode>
int Searcher::negamax(int alpha, int beta, int depth, int ply) {
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
  // The horizon (deliverable 4 puts the quiescence search here).
  if (ply >= MaxPly) return in_check ? 0 : static_eval(pos);
  if (depth <= 0) return static_eval(pos);

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
  if (tt_hit && !PvNode) {
    const int s = score_from_tt(hit.score, ply);
    const bool deep_enough = switches.tt_exact_depth ? hit.depth == depth : hit.depth >= depth;
    if (deep_enough && (hit.bound == TtBound::Exact || (hit.bound == TtBound::Lower && s >= beta) ||
                        (hit.bound == TtBound::Upper && s <= alpha)))
      return s;
  }

  f.static_eval = in_check ? ScoreNone : static_eval(pos);
  f.moves.count = 0;
  generate<GenMode::Legal>(pos, f.moves);
  if (f.moves.size() == 0) return in_check ? mated_score(ply) : 0;
  // A colliding entry's move may not be legal here: checked as the spec asks,
  // though only moves from the legal generator are searched today.
  const Move tt_move = tt_hit && pos.is_pseudo_legal(hit.move) && pos.is_legal(hit.move) ? hit.move : NoMove;
  order_moves(f, tt_move);

  const int alpha_start = alpha;
  int best = -ScoreInfinite;
  Move best_move = NoMove;
  for (std::size_t i = 0; i < f.moves.size(); ++i) {
    pick_next(f, i);
    const Move m = f.moves[i];
    if (switches.use_tt) tt_.prefetch_bucket(pos.predicted_key(m));
    pos.make(m);
    int score;
    if (i == 0 || !switches.use_pvs) {
      score = -negamax<PvNode>(-beta, -alpha, depth - 1, ply + 1);
    } else {
      score = -negamax<false>(-alpha - 1, -alpha, depth - 1, ply + 1);
      if (PvNode && score > alpha && score < beta) score = -negamax<true>(-beta, -alpha, depth - 1, ply + 1);
    }
    pos.unmake(m);
    if (stopped_) return 0;
    if (score > best) {
      best = score;
      if (score > alpha) {
        best_move = m;
        if (PvNode) update_pv(ply, m);
        if (score >= beta) break;
        alpha = score;
      }
    }
  }
  if (switches.use_tt) {
    const TtBound bound = best >= beta                   ? TtBound::Lower
                          : PvNode && best > alpha_start ? TtBound::Exact
                                                         : TtBound::Upper;
    tt_.deposit(key, best_move, score_to_tt(best, ply), f.static_eval, depth, bound, PvNode);
  }
  return best;
}

int Searcher::search_root(int alpha, int beta, int depth) {
  Position& pos = *pos_;
  ++nodes_;
  pv_[0].length = 0;
  for (std::size_t i = 0; i < root_count_; ++i) root_moves_[i].score = -ScoreInfinite;
  int best = -ScoreInfinite;
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
    root_moves_[i].score = (i == 0 || score > alpha) ? score : -ScoreInfinite;
    if (score > best) best = score;
    if (score > alpha) {
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
  // Stable insertion sort by score, best first (std::stable_sort may allocate).
  for (std::size_t i = 1; i < root_count_; ++i) {
    const RootEntry e = root_moves_[i];
    std::size_t j = i;
    for (; j > 0 && root_moves_[j - 1].score < e.score; --j) root_moves_[j] = root_moves_[j - 1];
    root_moves_[j] = e;
  }
  return best;
}

void Searcher::report_iteration(int depth, int score, int bound, const PrincipalLine& pv) {
  if (!listener_) return;
  const IterationReport r{depth,        max_ply_reached_,    score, bound, nodes_,
                          elapsed_ms(), tt_.fill_permille(), &pv};
  listener_->on_iteration(*pos_, r);
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
  PlyFrame& root = frames_[0];
  root.moves.count = 0;
  generate<GenMode::Legal>(pos, root.moves);
  root_count_ = 0;
  if (root.moves.size()) {
    order_moves(root, NoMove);
    for (std::size_t i = 0; i < root.moves.size(); ++i) {
      pick_next(root, i);
      const Move m = root.moves[i];
      if (limits.restrict_to.size() == 0 || limits.restrict_to.contains(m))
        root_moves_[root_count_++] = {m, 0};
    }
    if (root_count_ == 0)  // no searchmoves move is legal: search every move
      for (std::size_t i = 0; i < root.moves.size(); ++i) root_moves_[root_count_++] = {root.moves[i], 0};
  }
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
      // Only the failing side moves, by a doubling step; a decisive score
      // opens that side fully.
      if (score <= alpha) {
        alpha = is_tb_or_mate(score) ? -ScoreInfinite : std::max(score - delta, -ScoreInfinite);
      } else {
        beta = is_tb_or_mate(score) ? ScoreInfinite : std::min(score + delta, ScoreInfinite);
      }
      delta += delta;
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
