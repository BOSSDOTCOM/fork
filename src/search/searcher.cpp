#include "search/searcher.hpp"

#include <algorithm>
#include <cstdlib>

#include "core/movegen.hpp"
#include "eval/bootstrap_eval.hpp"
#include "eval/eval.hpp"
#include "search/endgame_tables.hpp"
#include "search/lmr_table.hpp"
#include "search/see.hpp"
#include "tune/params.hpp"

namespace forkeng {

namespace {

// Fork's own values, each justified in DESIGN.md §5.2 ("Search constants").
// The tunable ones are in the parameter table (src/tune/params.hpp,
// deliverable 8b): aspiration (AspirationMinDepth, AspirationHalfWidth); the
// iteration rule (no new iteration when elapsed * IterationGrowthThirds / 3
// passes the hard limit: the work grows by a measured median of 1.66 per
// iteration); reverse futility (RfpMaxDepth, RfpMargin cp per ply); the null
// move (NullMinDepth; half the remaining depth less one ply, and one ply less
// again per NullSurplusPerPly of static eval above beta, at most
// NullSurplusPliesMax); endgame tables from TableProbeMinDepth in the main
// search; LMR (LmrMinDepth, LmrMinMove; the table in lmr_table.hpp); late
// move pruning (LmpMaxDepth; LmpQuietAllowance + d quiets); futility
// (FutilityMaxDepth; FutilityOffset + FutilityGrowth * depth); SEE pruning
// (SeePruneMaxDepth; QuietSeeFloor and CaptureSeeFloor cp per ply). The
// margins are in the bootstrap evaluation's centipawns and are retuned after
// Phase 4. These stay constants (not strength parameters):
constexpr std::uint64_t StopCheckInterval = 1024;  // nodes between clock and stop-flag polls
// Cursed wins and blessed losses (the fifty-move rule turns them into draws)
// score just off zero, so a real draw is never preferred to them and no real
// advantage is given up for them.
constexpr int TableNearDrawScore = 1;

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
    MoveList fifty_scratch;  // rare (50-move positions in check), so a local list
    generate<GenMode::Legal>(pos, fifty_scratch);
    return fifty_scratch.size() ? 0 : mated_score(ply);
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

  // A TT entry stores the static evaluation of its position (review 2, claim
  // (b)): it is reused instead of evaluating again.
  // Endgame tables (deliverable 7): within the tables' piece count, with no
  // castling rights and a zero halfmove clock, the result is known. A win is
  // a lower bound (a faster mate may exist), a loss an upper bound, a draw
  // exact; the node returns at once when the bound settles it, and otherwise
  // the searched result is kept within it (a lost node is worth no more than
  // its loss, a won node no less than its win).
  int table_floor = -ScoreInfinite, table_ceiling = ScoreInfinite;
  if (switches.use_tables && depth >= TableProbeMinDepth && ply > 0) {
    if (const std::optional<TableWdl> wdl = probe_table_wdl(pos)) {
      ++table_hits_;
      const int s = *wdl == TableWdl::Win           ? TbWinScore - ply
                    : *wdl == TableWdl::Loss        ? -(TbWinScore - ply)
                    : *wdl == TableWdl::CursedWin   ? TableNearDrawScore
                    : *wdl == TableWdl::BlessedLoss ? -TableNearDrawScore
                                                    : 0;
      const TtBound b = *wdl == TableWdl::Win    ? TtBound::Lower
                        : *wdl == TableWdl::Loss ? TtBound::Upper
                                                 : TtBound::Exact;
      if (b == TtBound::Exact || (b == TtBound::Lower && s >= beta) || (b == TtBound::Upper && s <= alpha)) {
        // A table result holds at any depth, so it is stored as deep as the
        // TT allows: a deeper visit in a later iteration cuts on it instead of
        // probing again (audit-1, B-2).
        if (switches.use_tt)
          tt_.deposit(key, NoMove, score_to_tt(s, ply), ScoreNone,
                      switches.use_tables_full_depth ? MaxPly : depth, b, OnPv);
        return s;
      }
      (b == TtBound::Lower ? table_floor : table_ceiling) = s;
    }
  }

  f.static_eval = in_check ? ScoreNone : tt_hit && hit.eval != ScoreNone ? hit.eval : static_eval(pos);
  // The eval the pruning decisions use (review 2, claim (d); KB T50): a TT
  // score from a real search corrects the static estimate in the direction
  // its bound proves (a lower bound above it raises it, an upper bound below
  // it lowers it, an exact score replaces it). Mate and tablebase scores are
  // left out; the TT keeps the raw static eval.
  int prune_eval = f.static_eval;
  if (switches.use_tt_eval_refine && tt_hit && !in_check) {
    const int s = score_from_tt(hit.score, ply);
    if (!is_tb_or_mate(s) &&
        (hit.bound == TtBound::Exact || (hit.bound == TtBound::Lower && s > prune_eval) ||
         (hit.bound == TtBound::Upper && s < prune_eval)))
      prune_eval = s;
  }
  const bool can_prune = !OnPv && !in_check;

  // Reverse futility pruning (T20): far enough above beta at shallow depth,
  // the node fails high without a search.
  if (switches.use_rfp && can_prune && depth <= RfpMaxDepth && !is_tb_or_mate(beta) &&
      prune_eval - RfpMargin * depth >= beta) {
#ifdef FORK_SEARCH_STATS
    ++counters.rfp_cuts;
#endif
    return prune_eval;
  }

  // Null move pruning (T13): if passing still fails high on a reduced
  // search, the node is taken to fail high.
  if (switches.use_nmp && can_prune && depth >= NullMinDepth && !f.after_null && !is_tb_or_mate(beta) &&
      prune_eval >= beta && has_non_pawn_material(pos, pos.side_to_move())) {
    const int surplus_plies = std::min((prune_eval - beta) / NullSurplusPerPly, NullSurplusPliesMax);
    const int null_depth = depth / 2 - 1 - surplus_plies;                // 0 or less: the quiescence search
    if (switches.use_tt) tt_.prefetch_bucket(pos.predicted_null_key());  // review 2, claim (c)
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
  const int futility_value = in_check ? 0 : prune_eval + FutilityOffset + FutilityGrowth * depth;
  const bool futile_node = switches.use_futility && can_prune && depth <= FutilityMaxDepth &&
                           !is_tb_or_mate(alpha) && futility_value <= alpha;
#ifdef FORK_SEARCH_STATS
  counters.futile_nodes += futile_node;
#endif
  bool quiet_checks_only = false;
  for (Move m; !(m = f.selector.take_next()).is_none();) {
    ++moves_seen;
    const bool quiet = !m.is_capture() && !m.is_promotion();
#ifdef FORK_SEARCH_STATS
    counters.futile_quiets_taken += futile_node && quiet;
    const bool bad_after_stop =
        f.selector.yielding_stage() == SelectorStage::BadCaptures && f.selector.quiets_stopped();
    counters.bad_captures_after_stop += bad_after_stop;
#endif
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
#ifdef FORK_SEARCH_STATS
      if (switches.use_see_prune && can_prune && depth <= SeePruneMaxDepth) {
        const SelectorStage st = f.selector.yielding_stage();
        ++(st == SelectorStage::GoodCaptures  ? counters.see_tests_good_captures
           : st == SelectorStage::BadCaptures ? counters.see_tests_bad_captures
           : st == SelectorStage::Quiets      ? counters.see_tests_quiets
                                              : counters.see_tests_other);
      }
#endif
      // A capture from the good-capture stage already has SEE >= 0, above
      // every (negative) threshold here, so it is not tested again (review
      // claim (c), 2026-10-26).
      if (switches.use_see_prune && can_prune && depth <= SeePruneMaxDepth &&
          f.selector.yielding_stage() != SelectorStage::GoodCaptures &&
          !see_at_least(pos, m, -(quiet ? QuietSeeFloor : CaptureSeeFloor) * depth)) {
#ifdef FORK_SEARCH_STATS
        counters.bad_captures_after_stop_pruned += bad_after_stop;
#endif
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
    counters.futile_quiets_searched += futile_node && quiet;
#endif
    int score;
    if (moves_searched == 0) {
      score = -negamax<OnPv>(-beta, -alpha, depth - 1, ply + 1);
    } else {
      // Late move reductions (T15): late quiet moves get a reduced
      // zero-window search first, then the full depth if they beat alpha.
      // With PVS off the windows stay full, but LMR keeps its meaning
      // (audit-1: the two switches were coupled).
      const int new_depth = depth - 1;
      int reduced = new_depth;
      if (switches.use_lmr && depth >= LmrMinDepth && moves_searched + 1 >= LmrMinMove && quiet &&
          !in_check) {
        // The table's reduction plus the evolvable correction (lmr_table.hpp;
        // 0 as committed). The move is already made here, so its mover is the
        // side not to move: its history is the mover's (mover_history).
        const int base = reduction_for(depth, moves_searched + 1);
        const LmrMoveFacts facts = lmr_move_facts(pos, m);
        const LmrContext context{depth,
                                 moves_searched + 1,
                                 base,
                                 mover_history(history_, pos, m),
                                 OnPv,
                                 facts.piece,
                                 facts.threatened,
                                 facts.attacks,
                                 f.selector.stage_size(),
                                 game_phase(pos),
                                 tt_hit ? static_cast<int>(hit.bound) : 0,
                                 tt_hit ? static_cast<int>(hit.depth) : -1,
                                 score_trend_,
                                 branch_share_};
        const int rule = lmr_correction(context);
        const int correction = rule * LmrCorrectionStrength / 64;
        reduced = std::clamp(new_depth - (base + correction), 1, new_depth);
#ifdef FORK_SEARCH_STATS
        ++counters.lmr_rule_sites;
        counters.lmr_rule_fires += rule != 0;
        counters.lmr_rule_changes += reduced != std::clamp(new_depth - base, 1, new_depth);
#endif
      }
      if (!switches.use_pvs && reduced == new_depth) {
        score = -negamax<OnPv>(-beta, -alpha, new_depth, ply + 1);  // plain alpha-beta
      } else {
        // PVS off: the reduced search gets the full window, as a non-PV child.
        score = -negamax<false>(switches.use_pvs ? -alpha - 1 : -beta, -alpha, reduced, ply + 1);
#ifdef FORK_SEARCH_STATS
        counters.lmr_searches += reduced < new_depth;
        counters.lmr_plies_sum += static_cast<std::uint64_t>(new_depth - reduced);
        counters.lmr_researches += reduced < new_depth && score > alpha;
#endif
        // No re-search once the search has stopped: a stopped child returns 0,
        // which can beat alpha, and each call would still count a node past a
        // node limit (found by the heuristic-discovery gate, 2026-10-27).
        if (!stopped_ && score > alpha && reduced < new_depth)
          score = switches.use_pvs ? -negamax<false>(-alpha - 1, -alpha, new_depth, ply + 1)
                                   : -negamax<OnPv>(-beta, -alpha, new_depth, ply + 1);
        if (!stopped_ && switches.use_pvs && OnPv && score > alpha && score < beta)
          score = -negamax<true>(-beta, -alpha, new_depth, ply + 1);
      }
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
    // Once a move has been searched at a futile node not already lost to a
    // mate, every later non-checking quiet is pruned (the conditions at the
    // top of this loop), and both conditions only grow more true: the
    // selector may drop those quiets unscored.
    if (!quiet_checks_only && futile_node && best > -(MateScore - MaxPly)) {
      f.selector.keep_quiet_checks();
      quiet_checks_only = true;
    }
  }
  // Futility pruning (T22): at a futile node the selector drops the quiets
  // that do not give check (keep_quiet_checks above), so every quiet the
  // loop sees there is a checking one. The bound stays honest as if each
  // dropped quiet had been seen.
  if (f.selector.quiets_filtered() > 0) best = std::max(best, futility_value);
#ifdef FORK_SEARCH_STATS
  counters.futility_prunes += static_cast<std::uint64_t>(f.selector.quiets_filtered());
#endif
  // No legal move is mate or stalemate; legal moves that were all pruned are
  // not (the guard above prevents it; this keeps the result right regardless).
  if (moves_seen == 0) return in_check ? mated_score(ply) : 0;
  if (moves_searched == 0) return best;
  best = std::clamp(best, table_floor, table_ceiling);
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
#ifdef FORK_SEARCH_STATS
  ++(OnPv ? counters.quiesce_nodes_pv : counters.quiesce_nodes_non_pv);
#endif
  if (poll_limits()) return 0;
  max_ply_reached_ = std::max(max_ply_reached_, ply);
  Position& pos = *pos_;
  PlyFrame& f = frames_[ply];
  const bool in_check = pos.in_check();

  if (pos.repetition_count() >= 2 || pos.insufficient_material()) return 0;
  if (pos.fifty_move_reached()) {
    if (!in_check) return 0;
    MoveList fifty_scratch;  // rare (50-move positions in check), so a local list
    generate<GenMode::Legal>(pos, fifty_scratch);
    return fifty_scratch.size() ? 0 : mated_score(ply);
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
    f.static_eval = tt_hit && hit.eval != ScoreNone ? hit.eval : static_eval(pos);  // as in negamax
    best = f.static_eval;
    // The stand-pat value corrected by the TT score in the direction its
    // bound proves, as the main search's pruning eval (KB T50, its quiescence
    // use; audit-1, B-4). Mate and table scores are left out; the TT keeps
    // the raw static eval.
    if (switches.use_tt_stand_pat && tt_hit) {
      const int s = score_from_tt(hit.score, ply);
      if (!is_tb_or_mate(s) && (hit.bound == TtBound::Exact || (hit.bound == TtBound::Lower && s > best) ||
                                (hit.bound == TtBound::Upper && s < best)))
        best = s;
    }
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
    branch_share_ = root_moves_[i].share;
    const std::uint64_t nodes_before = nodes_;
    pos.make(m);
    int score;
    if (i == 0 || !switches.use_pvs) {
      score = -negamax<true>(-beta, -alpha, depth - 1, 1);
    } else {
      score = -negamax<false>(-alpha - 1, -alpha, depth - 1, 1);
      if (score > alpha && score < beta) score = -negamax<true>(-beta, -alpha, depth - 1, 1);
    }
    pos.unmake(m);
    root_moves_[i].nodes = nodes_ - nodes_before;
    if (stopped_) return best;
    if (score > best) best = score;
    if (m == root_fail_high_ && score < beta) root_fail_high_ = NoMove;  // resolved by its re-search
    if (score > alpha) {
      best_index = i;
      update_pv(0, m);
      if (score >= beta) root_fail_high_ = m;
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
  last_reported_ = pv.length ? pv.moves[0] : NoMove;
  if (!listener_) return;
  const IterationReport r{depth,        max_ply_reached_,    score, bound,      nodes_,
                          elapsed_ms(), tt_.fill_permille(), &pv,   table_hits_};
  listener_->on_iteration(*pos_, r);
}

int Searcher::probe_zero_window(Position& pos, int beta, int depth, const std::atomic<bool>& stop) {
  static const SearchQuota no_limits;
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

SearchResult Searcher::deliberate(Position& pos, const SearchQuota& limits, const std::atomic<bool>& stop,
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
  unresolved_fail_high_ = NoMove;

  tt_.advance_age();
  tt_.set_age_blend(switches.tt_age_blend);
  tt_.set_keep_exact(switches.tt_keep_exact);
  tt_.set_keep_deeper(switches.use_tt_keep_deeper);
  SearchResult result;
  // The first iteration's root order is the selector's (no TT move).
  PlyFrame& root = frames_[0];
  MoveList root_list;  // once per search, so a local list
  root.selector.start_main(pos, NoMove, switches.use_history ? &history_ : nullptr);
  for (Move m; !(m = root.selector.take_next()).is_none();) root_list.add(m);
  root_count_ = 0;
  for (Move m : root_list)
    if (limits.restrict_to.size() == 0 || limits.restrict_to.contains(m)) root_moves_[root_count_++] = {m};
  if (root_count_ == 0)  // no searchmoves move is legal: search every move
    for (Move m : root_list) root_moves_[root_count_++] = {m};
  if (root_count_ == 0) {
    result.score = pos.in_check() ? mated_score(0) : 0;
    return result;
  }
  // Endgame tables at the root (deliverable 7): only the moves that keep the
  // best result under the fifty-move rule are searched, in the tables' order
  // (within any searchmoves). A repetition since the last capture or pawn
  // move makes the ranking avoid repeating again.
  table_hits_ = 0;
  if (switches.use_tables && endgame_table_pieces() > 0) {
    MoveList kept;
    if (rank_root_by_tables(pos, pos.repetition_count() >= 2, kept)) {
      MoveList searched;  // the kept moves that are root moves, in the tables' order
      for (Move m : kept)
        for (std::size_t i = 0; i < root_count_; ++i)
          if (root_moves_[i].move == m) {
            searched.add(m);
            break;
          }
      if (searched.size() > 0) {
        root_count_ = 0;
        for (Move m : searched) root_moves_[root_count_++] = {m};
      }
      ++table_hits_;
    }
  }
  result.best = root_moves_[0].move;

  int previous = 0;
  for (int depth = 1; depth <= std::min(limits.depth, MaxPly - 1); ++depth) {
    iteration_best_ = NoMove;
    iteration_best_score_ = -ScoreInfinite;
    root_fail_high_ = NoMove;
    int delta = AspirationHalfWidth;
    int alpha = -ScoreInfinite, beta = ScoreInfinite;
    if (switches.use_aspiration && depth >= AspirationMinDepth && !is_tb_or_mate(previous)) {
      alpha = std::max(previous - delta, -ScoreInfinite);
      beta = std::min(previous + delta, ScoreInfinite);
    }
    int score;
    // After a fail high the re-search only has to place a score already shown
    // to be at least beta, so it searches FailHighDepthCut plies less (once,
    // not cumulatively); a fail low gets the full depth again (audit-1, B-3;
    // KB T6). The iteration is still reported at `depth`.
    int pass_depth = depth;
    for (;;) {
      score = search_root(alpha, beta, pass_depth);
      if (stopped_) break;
      if (score > alpha && score < beta) break;
      if (elapsed_ms() >= fail_report_ms) report_iteration(depth, score, score <= alpha ? -1 : 1, pv_[0]);
      // Only the failing side moves. The half-width grows by how far the
      // fail-soft score already is from the previous iteration's: at least
      // the old half-width (the score fell outside the window), more after a
      // big jump. A decisive score opens that side fully.
      delta = std::min(delta + std::abs(score - previous), ScoreInfinite);
      if (score <= alpha) {
        alpha = is_tb_or_mate(score) ? -ScoreInfinite : std::max(score - delta, -ScoreInfinite);
        pass_depth = depth;
      } else {
        beta = is_tb_or_mate(score) ? ScoreInfinite : std::min(score + delta, ScoreInfinite);
        if (switches.use_shallow_fail_high) pass_depth = std::max(1, depth - FailHighDepthCut);
      }
    }
    if (stopped_) {
      unresolved_fail_high_ = root_fail_high_;
      // An unfinished iteration counts only through a move that came back
      // with an exact score above the last finished iteration's best. A root
      // fail high still awaiting its re-search is not trusted: playing it
      // lost -14.6 +/- 10.8 Elo at STC (owner, 2026-10-26; sprt-log.md
      // rv-failhigh), so the previous iteration's move is kept. The fail
      // high is still recorded (unresolved_fail_high, ideas.md idea 29).
      if (!iteration_best_.is_none() && result.depth > 0 && iteration_best_score_ > previous) {
        result.best = iteration_best_;
        result.score = iteration_best_score_;
        report_iteration(depth, iteration_best_score_, 0,
                         iteration_pv_);  // the last info names the move played
      }
      // A reported fail (a fail low has no PV, a fail high names a move
      // that is not played) must not be the last line: the finished
      // iteration is reported again.
      if (result.depth > 0 && !(last_reported_ == result.best))
        report_iteration(result.depth, result.score, 0, finished_pv_);
      break;
    }
    // The LMR context's iteration inputs: the root score's last change, and
    // each root move's share of this iteration's nodes for the next one.
    score_trend_ = depth > 1 ? std::clamp(score - previous, -1000, 1000) : 0;
    std::uint64_t iteration_nodes = 0;
    for (std::size_t i = 0; i < root_count_; ++i) iteration_nodes += root_moves_[i].nodes;
    for (std::size_t i = 0; i < root_count_; ++i)
      root_moves_[i].share =
          iteration_nodes ? static_cast<int>(root_moves_[i].nodes * 1000 / iteration_nodes) : 0;
    previous = score;
    result.best = root_moves_[0].move;
    result.score = score;
    result.depth = depth;
    finished_pv_ = pv_[0];
    report_iteration(depth, score, 0, pv_[0]);
    if (limits.mate_moves > 0 && is_mate_score(score) && score > 0 &&
        mate_in_moves(score) <= limits.mate_moves)
      break;
    const bool timed = !(pondering && pondering->load(std::memory_order_relaxed));
    if (timed && limits.soft_ms >= 0 && elapsed_ms() >= limits.soft_ms) break;
    // With one root move (one legal move, one searchmoves move, or one the
    // tables keep) nothing the search finds can change the move: only the
    // reported score and the next move's TT and history gain from more
    // time, so a fraction of the soft limit is enough (audit-1, B-1).
    if (timed && switches.use_forced_move_stop && root_count_ == 1 && limits.soft_ms >= 0 &&
        elapsed_ms() * ForcedMoveFraction >= limits.soft_ms)
      break;
    // An iteration that would probably not finish before the hard limit is
    // not started (deliverable 8): its time would be spent for nothing. This
    // binds where the hard limit is close to the soft one: `go movetime`,
    // and a low clock whose reserve caps the hard limit.
    if (timed && limits.hard_ms >= 0 && elapsed_ms() * IterationGrowthThirds / 3 > limits.hard_ms) break;
  }
  result.nodes = nodes_;
  return result;
}

}  // namespace forkeng
