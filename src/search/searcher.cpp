// SPDX-License-Identifier: GPL-3.0-or-later

#include "search/searcher.hpp"

#include <algorithm>
#include <cstdio>
#include <cstdlib>

#include "core/material.hpp"
#include "core/movegen.hpp"
#include "eval/eval.hpp"
#include "search/endgame_tables.hpp"
#include "search/lmr_table.hpp"
#include "search/see.hpp"
#include "search/stats_report.hpp"
#include "tune/params.hpp"

namespace forkeng {

Searcher::Searcher(TransTable& tt) : tt_(tt) {
#ifdef FORK_SEARCH_STATS
  if (const char* every = std::getenv("FORK_SINGULAR_PROBE"))
    singular_probe_ = std::strtoull(every, nullptr, 10);
  if (const char* report = std::getenv("FORK_STATS_REPORT")) report_counters_ = report[0] && report[0] != '0';
  if (const char* trace = std::getenv("FORK_ITERATION_TRACE"))
    trace_iterations_ = trace[0] && trace[0] != '0';
  if (const char* every = std::getenv("FORK_PRUNE_LEDGER")) ledger_every_ = std::strtoull(every, nullptr, 10);
  if (const char* sites = std::getenv("FORK_EVAL_SITES")) {
    char* rest = nullptr;
    eval_site_every_main_ = std::strtoull(sites, &rest, 10);
    if (rest && *rest == ',') eval_site_every_quiesce_ = std::strtoull(rest + 1, nullptr, 10);
  }
#endif
#if defined(FORK_EVAL_NNUE)
  net_ = &embedded_net();  // read now, so no search ever allocates for it
#endif
}

[[gnu::always_inline]] inline void Searcher::play(int ply, Move m) {
#if defined(FORK_EVAL_NNUE)
  features_.push_move(*net_, ply, *pos_, m);
#endif
  (void)ply;
  pos_->make(m);
}

[[gnu::always_inline]] inline void Searcher::play_null(int ply) {
#if defined(FORK_EVAL_NNUE)
  features_.push_null(ply);
#endif
  (void)ply;
  pos_->make_null();
}

// Idea 79's band (the owner's plan: a band of 100 cp or less; the offline
// probe: the narrow readout is more than 100 cp from the full output at 5.6%
// of positions, tools/measure/head_probes.py narrow).
constexpr int NarrowFarBand = 100;

int Searcher::eval_gated(int ply, int alpha, int beta) {
  const int full = eval_at(ply);
#if defined(FORK_EVAL_NNUE) && FORK_NET_ARCH == 8
  if (switches.use_narrow_far) {
    const int narrow = features_.narrow_readout(*net_, ply, *pos_);
    if (window_gap(narrow, alpha, beta) > NarrowFarBand) return narrow;
  }
#else
  (void)alpha;
  (void)beta;
#endif
  return full;
}

[[gnu::always_inline]] inline int Searcher::eval_at(int ply) {
#if defined(FORK_EVAL_NNUE)
  return features_.evaluate(*net_, ply, *pos_);
#else
  (void)ply;
  return static_eval(*pos_);
#endif
}

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
// The LMR context's root score trend is clamped to ten pawns (DESIGN.md,
// "Search constants": beyond that a change only says "decisive").
constexpr int ScoreTrendLimit = 1000;
// Cursed wins and blessed losses (the fifty-move rule turns them into draws)
// score just off zero, so a real draw is never preferred to them and no real
// advantage is given up for them.
constexpr int TableNearDrawScore = 1;
// A late quiet move that gives check is reduced one ply less (tier 2 step 0;
// DESIGN.md, "Search constants": the smallest step in whole plies, which is
// the unit Fork's LMR table works in).
constexpr int LmrCheckRelief = 1;
#ifdef FORK_NODE_CLOCK
// Test-only builds (CMake FORK_NODE_CLOCK, never released): the search's
// clock reads its node count, this many nodes to the millisecond, so a timed
// search is deterministic and two builds can be compared on it byte for byte
// (DESIGN.md §5.6 step 10, the time-management switches' identity check).
constexpr std::uint64_t NodeClockRate = 1000;
#endif

// The side has a piece other than pawns and its king (the null move's main
// zugzwang guard: pawn endings are where passing is most often best).
bool has_non_pawn_material(const Position& pos, Color c) {
  return (pos.pieces(c) & ~pos.pieces(Pawn) & ~pos.pieces(King)) != 0;
}

// The fifty-move rule has been reached: a draw, unless the side to move is
// checkmated (mate takes precedence). Rare (50-move positions in check), so
// its move list is a local one.
int fifty_move_score(const Position& pos, bool in_check, int ply) {
  if (!in_check) return 0;
  MoveList evasions;
  generate<GenMode::Legal>(pos, evasions);
  return evasions.size() ? 0 : mated_score(ply);
}

}  // namespace

std::int64_t Searcher::elapsed_ms() const {
#ifdef FORK_NODE_CLOCK
  return static_cast<std::int64_t>(nodes_ / NodeClockRate);
#else
  return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start_)
      .count();
#endif
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
void Searcher::record_cutoff(PlyFrame& f, Move m, int depth) {
#ifdef FORK_SEARCH_STATS
  if (ledger_active_) return;  // a decision-ledger side search leaves the histories as they were (X10)
#endif
  const Position& here = *pos_;
  const int bonus = bonus_for_depth(depth);
  // The take history (tier 2, T11): a capture that cuts gains the bonus, and
  // the captures tried before a quiet or capture cutoff take the malus (a
  // non-capture promotion's cutoff updates nothing).
  if (switches.use_take_history) {
    const auto slot = [&](Move c) {
      return take_slot(here.piece_at(c.from()), c.to(),
                       c.is_en_passant() ? Pawn : kind_of(here.piece_at(c.to())));
    };
    if (m.is_capture()) take_history_.apply(slot(m), bonus);
    if (switches.use_history_malus)
      for (Move c : f.failed_moves)
        if (c.is_capture()) take_history_.apply(slot(c), -bonus);
  }
  if (m.is_capture() || !switches.use_history) return;
  const Color us = here.side_to_move();
  // Each quiet's threat bucket (T56) from this node's threat set, the one its
  // ordering read (0 with use_threat_buckets off).
  const Bitboard attacked = f.selector.attacked_by_opponent();
  history_.apply(us, m, bonus, threat_bucket(attacked, m));
  if (switches.use_history_malus)
    for (Move q : f.failed_moves)
      if (!q.is_capture()) history_.apply(us, q, -bonus, threat_bucket(attacked, q));
  // The pair histories (tier 2, T10) take the same bonus and malus.
  const auto update = [&](PairHistory& table, int arrival) {
    const Position& pos = *pos_;
    table.apply(arrival, pair_slot(pos.piece_at(m.from()), m.to()), bonus);
    if (switches.use_history_malus)
      for (Move q : f.failed_moves)
        if (!q.is_capture()) table.apply(arrival, pair_slot(pos.piece_at(q.from()), q.to()), -bonus);
  };
  if (switches.use_reply_history && f.arrival != NoArrival) update(pair_history_[ReplyTable], f.arrival);
  const int follow = follow_arrival(f);
  if (switches.use_follow_history && follow != NoArrival) update(pair_history_[FollowTable], follow);
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
#ifdef FORK_SEARCH_STATS
  // X10: the force of a decision-ledger side search applies to the node it
  // re-enters (the first call at its ply) and to nothing below it.
  LedgerForce force = LedgerForce::Keep;
  if (ledger_force_ != LedgerForce::Keep && ply == ledger_force_ply_) {
    force = ledger_force_;
    ledger_force_ = LedgerForce::Keep;
  }
  const int ledger_entry_depth = depth;  // before the no-move reduction: a re-entry applies it once
#endif
  if (depth <= 0 && switches.use_quiesce) return quiesce<OnPv>(alpha, beta, ply);
  pv_[ply].length = 0;
  ++nodes_;
  FORK_STAT(++counters.main_nodes);
  if (poll_limits()) return 0;
  max_ply_reached_ = std::max(max_ply_reached_, ply);
  Position& pos = *pos_;
  PlyFrame& f = frames_[ply];
  const bool in_check = pos.in_check();
  // A singular test's search of this node without its TT move (tier 2, T27):
  // it neither cuts on nor writes this node's TT entry, and skips the
  // node-level pruning, which would answer for the whole node.
  const bool withheld = !f.withheld_move.is_none();

  // Draws: repetition (one earlier occurrence is enough inside the search),
  // insufficient material, and the 50-move rule unless this move is mate.
  if (pos.repetition_count() >= 2 || pos.insufficient_material()) return 0;
  if (pos.fifty_move_reached()) return fifty_move_score(pos, in_check, ply);
  if (ply >= MaxPly) {
    FORK_STAT(counters.evals_horizon += !in_check);
    return in_check ? 0 : eval_at(ply);
  }
  if (depth <= 0) {
    FORK_STAT(++counters.evals_horizon);
    return eval_at(ply);  // only with the quiescence search switched off
  }

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
  if (tt_hit && !OnPv && !withheld) {
    const int s = score_from_tt(hit.score, ply);
    const bool deep_enough = switches.tt_exact_depth ? hit.depth == depth : hit.depth >= depth;
    if (deep_enough && bound_settles(hit.bound, s, alpha, beta)) return s;
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
      if (bound_settles(b, s, alpha, beta)) {
        if (switches.use_tt && !withheld)
          tt_.deposit(key, NoMove, score_to_tt(s, ply), ScoreNone, depth, b, OnPv);
        return s;
      }
      (b == TtBound::Lower ? table_floor : table_ceiling) = s;
    }
  }

  f.static_eval = in_check ? ScoreNone : tt_hit && hit.eval != ScoreNone ? hit.eval : eval_gated(ply, alpha, beta);
  FORK_STAT(++(in_check                          ? counters.check_nodes_main
               : tt_hit && hit.eval != ScoreNone ? counters.tt_eval_hits_main
                                                 : counters.evals_main));
#ifdef FORK_SEARCH_STATS
  // Idea 59 step 1: the static evaluation's gap to the nearest finite bound
  // of this node's window (after mate distance pruning), computed or reused.
  if (!in_check) {
    const bool reused = tt_hit && hit.eval != ScoreNone;
    const int gap = window_gap(f.static_eval, alpha, beta);
    const int band = gap_depth_band(depth);
    if (gap < 0) {
      ++(reused ? counters.eval_gap_main_reuse_infinite : counters.eval_gap_main_infinite);
      if (!reused) ++counters.eval_gap_band_infinite[band];
    } else if (reused) {
      ++counters.eval_gap_main_reuse_bins[window_gap_bin(gap)];
    } else {
      ++counters.eval_gap_main_bins[window_gap_bin(gap)];
      ++counters.eval_gap_band_bins[band][window_gap_bin(gap)];
      counters.eval_gap_main_one_sided += is_tb_or_mate(alpha) != is_tb_or_mate(beta);
    }
  }
#endif
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
#ifdef FORK_SEARCH_STATS
  // Crucial-point ground truth: a sampled main-search evaluation site
  // (computed or reused from the TT), with the window it was reached with.
  if (!in_check && eval_site_every_main_ && !ledger_active_ &&
      ++eval_site_seen_main_ % eval_site_every_main_ == 0)
    print_eval_site(0, tt_hit && hit.eval != ScoreNone, alpha, beta, f.static_eval, prune_eval, depth, ply,
                    tt_hit, hit, OnPv);
#endif
  const bool can_prune = !OnPv && !in_check;
  const bool can_prune_node = can_prune && !withheld;

#ifdef FORK_SEARCH_STATS
  // X10, the decision ledger's RFP rows: at a sampled candidate (every
  // condition but the margin), the node is also searched with RFP off here;
  // a prune (taken, or one a smaller margin would take) is wrong when that
  // search fails low. The real search goes on unchanged.
  if (ledger_every_ && !ledger_active_ && switches.use_rfp && can_prune_node && depth <= RfpMaxDepth &&
      !is_tb_or_mate(beta) && prune_eval >= beta) {
    ++counters.ledger_rfp_candidates;
    if (ledger_sampled(key)) {
      const int saved_eval = f.static_eval;
      std::uint64_t arm_nodes = 0;
      const int arm = ledger_side_search(alpha, beta, depth, ply, LedgerForce::RfpOff, arm_nodes);
      f.static_eval = saved_eval;
      if (stopped_) return 0;
      const int parent_eval = ply > 0 ? frames_[ply - 1].static_eval : ScoreNone;
      std::fprintf(stderr, "prune_ledger rfp|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%llu|%d\n", depth, ply,
                   prune_eval - beta, f.static_eval - beta, RfpMargin * depth,
                   tt_hit ? static_cast<int>(hit.bound) : 0, tt_hit ? static_cast<int>(hit.depth) : -1,
                   parent_eval != ScoreNone ? f.static_eval + parent_eval : ScoreNone, game_phase(pos),
                   prune_eval - RfpMargin * depth >= beta ? 1 : 0, std::clamp(arm - beta, -2000, 2000),
                   static_cast<unsigned long long>(arm_nodes), is_tb_or_mate(arm) ? 1 : 0);
      ++counters.ledger_rows;
    }
  }
#endif
  // Reverse futility pruning (T20): far enough above beta at shallow depth,
  // the node fails high without a search.
  if (switches.use_rfp && can_prune_node && depth <= RfpMaxDepth && !is_tb_or_mate(beta) &&
      prune_eval - RfpMargin * depth >= beta FORK_STAT_GATE(&&force != LedgerForce::RfpOff)) {
    FORK_STAT(++counters.rfp_cuts);
    return prune_eval;
  }

  // Null move pruning (T13): if passing still fails high on a reduced
  // search, the node is taken to fail high.
  if (switches.use_nmp && can_prune_node && depth >= NullMinDepth && !f.after_null && !is_tb_or_mate(beta) &&
      prune_eval >= beta && has_non_pawn_material(pos, pos.side_to_move())) {
    const int surplus_plies = std::min((prune_eval - beta) / NullSurplusPerPly, NullSurplusPliesMax);
    const int null_depth = depth / 2 - 1 - surplus_plies;                // 0 or less: the quiescence search
    if (switches.use_tt) tt_.prefetch_bucket(pos.predicted_null_key());  // review 2, claim (c)
    play_null(ply);
    frames_[ply + 1].after_null = true;
    frames_[ply + 1].arrival = NoArrival;
    frames_[ply + 1].expected_cut = !f.expected_cut;  // T17: passing should fail low below
    const int score = -negamax<false>(-beta, -beta + 1, null_depth, ply + 1);
    frames_[ply + 1].after_null = false;
    pos.unmake_null();
    if (stopped_) return 0;
    if (score >= beta) {
      FORK_STAT(++counters.null_cuts);
      return is_tb_or_mate(score) ? beta : score;  // a mate found after passing is not trusted
    }
  }

#ifdef FORK_SEARCH_STATS
  // The singular-extension measurement (tier 2; DESIGN.md, "Search
  // constants"): every Nth node where a singular test could run, under the
  // widest conditions considered, is printed for tools/singular_measure.py
  // (N from the environment variable FORK_SINGULAR_PROBE; unset or 0: none).
  if (singular_probe_ > 0 && !withheld && ply > 0 && depth >= 4 && tt_hit && !hit.move.is_none() &&
      (hit.bound == TtBound::Lower || hit.bound == TtBound::Exact) && hit.depth >= depth - 4) {
    const int s = score_from_tt(hit.score, ply);
    if (!is_tb_or_mate(s) && ++counters.singular_candidates % singular_probe_ == 0)
      std::fprintf(stderr, "singular_probe %s|%d|%s|%d|%d|%d|%d\n", pos.fen().c_str(), depth,
                   pos.move_to_uci(hit.move).c_str(), s, static_cast<int>(hit.bound),
                   static_cast<int>(hit.depth), OnPv ? 1 : 0);
  }
#endif

  // Internal iterative reduction (tier 2, T26; KB search-techniques.md
  // §3.20): a node with no TT move, deep enough, is searched one ply
  // shallower. Its ordering is poor, and the cheaper search stores a move
  // for the next iteration. Every node type: Fork does not track expected
  // cut nodes. After the node-level pruning, whose decisions keep the
  // node's full depth.
  if (switches.use_no_move_reduction && !withheld && depth >= NoMoveReduceMinDepth &&
      (!tt_hit || hit.move.is_none())) {
    --depth;
    FORK_STAT(++counters.no_move_reductions);
  }

  // Singular extension (tier 2, T27; KB search-techniques.md §3.21): when
  // the TT entry proves a score for its move at nearly this depth, this node
  // is searched again at half depth without that move, on a zero window
  // SingularMarginPerPly cp per ply below the entry's score. If every other
  // move fails low there, the TT move is the only good one, and it is
  // searched one ply deeper. The test runs before this node's own move
  // selection, since its search reuses this ply's frame.
  // The same test also finds the opposite case at non-PV nodes (T28, T30):
  // other moves reach the bar too. If the bar is at or above beta, at least
  // two moves beat beta, and the node fails high at once with the bar
  // (multi-cut; never with a mate or tablebase score). Otherwise, if the
  // entry's score is already at or above beta, the TT move is searched one
  // ply shallower: other moves are likely to refute as well (negative
  // extension).
  Move tested_move = NoMove;
  int tested_extension = 0;
  if ((switches.use_singular_extension || switches.use_multi_cut || switches.use_negative_extension) &&
      !withheld && ply > 0 && depth >= SingularMinDepth && tt_hit && !hit.move.is_none() &&
      (hit.bound == TtBound::Lower || hit.bound == TtBound::Exact) &&
      hit.depth >= depth - SingularEntrySlack) {
    const int s = score_from_tt(hit.score, ply);
    if (!is_tb_or_mate(s)) {
      const int bar = s - SingularMarginPerPly * depth;
      FORK_STAT(++counters.singular_tests);
      f.withheld_move = hit.move;
      const int score = negamax<false>(bar - 1, bar, depth / 2, ply);
      f.withheld_move = NoMove;
      if (stopped_) return 0;
      if (score < bar) {
        if (switches.use_singular_extension) {
          tested_move = hit.move;
          tested_extension = 1;
          FORK_STAT(++counters.singular_extended);
        }
      } else if (!OnPv && switches.use_multi_cut && bar >= beta && !is_tb_or_mate(bar)) {
        FORK_STAT(++counters.multi_cut_cuts);
        return bar;
      } else if (!OnPv && switches.use_negative_extension && s >= beta) {
        tested_move = hit.move;
        tested_extension = -1;
        FORK_STAT(++counters.negative_extensions);
      }
    }
  }

#ifdef FORK_SEARCH_STATS
  // X10, the decision ledger's futility rows: at a sampled candidate (every
  // condition but the margin: the static estimate at or below alpha), the
  // node is searched again with futility forced on and forced off here
  // (both side searches, so both see the same TT); futility is wrong when
  // the on arm fails low and the off arm fails high. Before the selector
  // starts, so the re-entries cannot disturb this node's move loop.
  if (ledger_every_ && !ledger_active_ && switches.use_futility && can_prune && depth <= FutilityMaxDepth &&
      !is_tb_or_mate(alpha) && prune_eval <= alpha) {
    ++counters.ledger_futility_candidates;
    if (ledger_sampled(key)) {
      const int saved_eval = f.static_eval;
      std::uint64_t on_nodes = 0, off_nodes = 0;
      const int on =
          ledger_side_search(alpha, beta, ledger_entry_depth, ply, LedgerForce::FutilityOn, on_nodes);
      if (stopped_) return 0;
      const int off =
          ledger_side_search(alpha, beta, ledger_entry_depth, ply, LedgerForce::FutilityOff, off_nodes);
      f.static_eval = saved_eval;
      if (stopped_) return 0;
      const int margin = FutilityOffset + FutilityGrowth * depth;
      const int parent_eval = ply > 0 ? frames_[ply - 1].static_eval : ScoreNone;
      std::fprintf(stderr, "prune_ledger futility|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%llu|%llu|%d\n", depth,
                   ply, alpha - prune_eval, alpha - f.static_eval, margin,
                   tt_hit ? static_cast<int>(hit.bound) : 0, tt_hit ? static_cast<int>(hit.depth) : -1,
                   parent_eval != ScoreNone ? f.static_eval + parent_eval : ScoreNone, game_phase(pos),
                   prune_eval + margin <= alpha ? 1 : 0, std::clamp(on - beta, -2000, 2000),
                   std::clamp(off - beta, -2000, 2000), static_cast<unsigned long long>(on_nodes),
                   static_cast<unsigned long long>(off_nodes),
                   is_tb_or_mate(on) || is_tb_or_mate(off) ? 1 : 0);
      ++counters.ledger_rows;
    }
  }
#endif
  // The selector checks the TT move (a colliding entry's move may not be
  // legal here) before it is tried first; a withheld move is not tried.
  f.selector.start_main(
      pos, tt_hit && !withheld ? hit.move : NoMove, switches.use_history ? &history_ : nullptr,
      switches.use_history ? pair_history_ : nullptr, switches.use_reply_history ? f.arrival : NoArrival,
      switches.use_follow_history ? follow_arrival(f) : NoArrival,
      switches.use_take_history ? &take_history_ : nullptr, switches.use_threat_buckets);
  f.failed_moves.count = 0;

  const int alpha_start = alpha;
  int best = -ScoreInfinite;
  Move best_move = NoMove;
  int moves_searched = 0;
  int moves_seen = 0;  // legal moves the selector yielded, searched or pruned
  int quiets_searched = 0;
  const bool lmp_node = switches.use_lmp && can_prune && depth <= LmpMaxDepth;
  const int futility_value = in_check ? 0 : prune_eval + FutilityOffset + FutilityGrowth * depth;
  // (Stats builds: a decision-ledger side search may force the margin's
  // test on or off at the node it re-enters, X10.)
  const bool futile_node = switches.use_futility && can_prune && depth <= FutilityMaxDepth &&
                           !is_tb_or_mate(alpha) &&
                           (FORK_STAT_GATE(force == LedgerForce::FutilityOn    ? true
                                           : force == LedgerForce::FutilityOff ? false
                                                                               :) futility_value <= alpha);
  FORK_STAT(counters.futile_nodes += futile_node);
  bool quiet_checks_only = false;
  for (Move m; !(m = f.selector.take_next()).is_none();) {
    if (m == f.withheld_move) continue;
    ++moves_seen;
    const bool quiet = !m.is_capture() && !m.is_promotion();
    const int extension = m == tested_move ? tested_extension : 0;
#ifdef FORK_SEARCH_STATS
    counters.futile_quiets_taken += futile_node && quiet;
    const bool bad_after_stop =
        f.selector.yielding_stage() == SelectorStage::BadCaptures && f.selector.quiets_stopped();
    counters.bad_captures_after_stop += bad_after_stop;
#endif
    // Pruning: only once a move has been searched (so no node is pruned into
    // a false stalemate or mate) and while not already losing to a mate.
    if (moves_searched > 0 && best > -MateBandFloor) {
      if (lmp_node && quiet && quiets_searched >= LmpQuietAllowance + depth) {
        f.selector.stop_quiets();  // late move pruning (T21)
        FORK_STAT(++counters.lmp_prunes);
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
        ++counters.see_prunes;
#endif
        continue;  // SEE pruning (T23)
      }
    }
    if (switches.use_tt) tt_.prefetch_bucket(pos.predicted_key(m));
    frames_[ply + 1].arrival = pair_slot(pos.piece_at(m.from()), m.to());
    // A quiet's threat bucket for the LMR context's history (T56): taken
    // here, on the board before the move (0 with use_threat_buckets off).
    const int bucket = quiet ? threat_bucket(f.selector.attacked_by_opponent(), m) : 0;
#ifdef FORK_SEARCH_STATS
    counters.pawn_makes += kind_of(pos.piece_at(m.from())) == Pawn;
    // X2 (DESIGN.md §5.7): the move's history values, read before it is made
    // (as the selector and sprt/lmr-history's term read them). The ordering
    // score uses the tables the selector uses; the raw entries are the
    // tables' own (the follow and reply entries only with their arrivals).
    const int stats_slot = pair_slot(pos.piece_at(m.from()), m.to());
    const int stats_follow = follow_arrival(f);
    const int stats_order_score =
        quiet ? quiet_order_score(pos, m, switches.use_history ? &history_ : nullptr,
                                  switches.use_history ? pair_history_ : nullptr,
                                  switches.use_reply_history ? f.arrival : NoArrival,
                                  switches.use_follow_history ? stats_follow : NoArrival, bucket)
              : 0;
    const int stats_quiet_value = quiet ? history_.value(pos.side_to_move(), m, bucket) : 0;
    const int stats_reply_value =
        quiet && f.arrival != NoArrival ? pair_history_[ReplyTable].value(f.arrival, stats_slot) : 0;
    const int stats_follow_value =
        quiet && stats_follow != NoArrival ? pair_history_[FollowTable].value(stats_follow, stats_slot) : 0;
    const int stats_take_value =
        m.is_capture()
            ? take_history_.value(take_slot(pos.piece_at(m.from()), m.to(),
                                            m.is_en_passant() ? Pawn : kind_of(pos.piece_at(m.to()))))
            : 0;
#endif
    // Node types (tier 2, T17; KB search-techniques.md §3.14), the expected
    // type of the child: a PV node's later children are expected cut nodes
    // (its first is a PV node); a cut node's children are expected all nodes,
    // and an all node's expected cut nodes, as in a minimal tree. A
    // prediction only: nothing relies on it being right.
    frames_[ply + 1].expected_cut = OnPv ? moves_searched > 0 : !f.expected_cut;
    play(ply, m);
#ifdef FORK_SEARCH_STATS
    ++counters.makes;
    counters.futile_quiets_searched += futile_node && quiet;
#endif
    int score;
    if (moves_searched == 0) {
      score = -negamax<OnPv>(-beta, -alpha, depth - 1 + extension, ply + 1);
    } else {
      // Late move reductions (T15): late quiet moves get a reduced
      // zero-window search first, then the full depth if they beat alpha.
      // With PVS off the windows stay full, but LMR keeps its meaning
      // (audit-1: the two switches were coupled).
      const int new_depth = depth - 1 + extension;
      int reduced = new_depth;
      // Tier 2 step 0 (KB T16's in-check term): with use_lmr_in_check, late
      // quiet evasions are reduced like any late quiet move.
      if (switches.use_lmr && depth >= LmrMinDepth && moves_searched + 1 >= LmrMinMove && quiet &&
          (!in_check || switches.use_lmr_in_check)) {
        // The table's reduction plus the evolvable correction (lmr_table.hpp;
        // 0 as committed). The move is already made here, so its mover is the
        // side not to move: its history is the mover's (mover_history).
        const int base = reduction_for(depth, moves_searched + 1);
        const LmrMoveFacts facts = lmr_move_facts(pos, m);
        const LmrContext context{.depth = depth,
                                 .move_number = moves_searched + 1,
                                 .base = base,
                                 .history = mover_history(history_, pos, m, bucket),
                                 .on_pv = OnPv,
                                 .piece = facts.piece,
                                 .threatened = facts.threatened,
                                 .attacks = facts.attacks,
                                 .quiet_moves = f.selector.stage_size(),
                                 .phase = game_phase(pos),
                                 .entry_bound = tt_hit ? static_cast<int>(hit.bound) : 0,
                                 .entry_depth = tt_hit ? static_cast<int>(hit.depth) : -1,
                                 .score_trend = score_trend_,
                                 .branch_share = branch_share_};
        const int rule = lmr_correction(context);
        const int correction = rule * LmrCorrectionStrength / LmrCorrectionUnit;
        // Tier 2 step 0 (KB T16's check term): a checking move starts a
        // forcing line, so it is reduced less. The move is already made, so
        // "gives check" is the child's side to move being in check.
        const int relief = switches.use_lmr_check_relief && pos.in_check() ? LmrCheckRelief : 0;
        // Node types (T17): an expected cut node's late quiets are reduced
        // CutNodeLmrPlies more.
        const int cut_extra = switches.use_cut_node_lmr && !OnPv && f.expected_cut ? CutNodeLmrPlies : 0;
        reduced = std::clamp(new_depth - (base + correction - relief + cut_extra), 1, new_depth);
#ifdef FORK_SEARCH_STATS
        ++counters.lmr_rule_sites;
        counters.lmr_rule_fires += rule != 0;
        counters.lmr_rule_changes += reduced != std::clamp(new_depth - base, 1, new_depth);
        // X2: the history values at this LMR site, and what the LMR history
        // term (sprt/lmr-history: the base less the ordering score / 24,000)
        // would do here. The correction is the same with that base: the
        // committed rule returns 0 whatever its context. The probe's
        // reduction keeps every other term of the real one (check relief,
        // the cut-node plies), so it differs only where the term fires.
        ++counters.lmr_order_bins[order_score_bin(stats_order_score)];
        ++counters.lmr_quiet_bins[table_value_bin(stats_quiet_value)];
        if (f.arrival != NoArrival)
          ++counters.lmr_reply_bins[table_value_bin(stats_reply_value)];
        else
          ++counters.lmr_reply_absent;
        if (stats_follow != NoArrival)
          ++counters.lmr_follow_bins[table_value_bin(stats_follow_value)];
        else
          ++counters.lmr_follow_absent;
        const int shift = lmr_history_probe_shift(stats_order_score);
        counters.lmr_history_fire_less += shift > 0;
        counters.lmr_history_fire_more += shift < 0;
        counters.lmr_history_changes +=
            std::clamp(new_depth - (base - shift + correction - relief + cut_extra), 1, new_depth) != reduced;
#endif
      }
#ifdef FORK_SEARCH_STATS
      // X2: a late capture (every LMR gate passed but "quiet"; R18's sites).
      if (m.is_capture() && depth >= LmrMinDepth && moves_searched + 1 >= LmrMinMove) {
        ++counters.late_capture_sites;
        ++counters.late_take_bins[table_value_bin(stats_take_value)];
      }
#endif
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
          if (quiet || m.is_capture()) record_cutoff(f, m, depth);
#ifdef FORK_SEARCH_STATS
          if (quiet && !OnPv && !in_check && depth < SearchCounters::CutoffDepths)
            ++counters.quiet_cutoff_index[depth]
                                         [std::min(quiets_searched - 1, SearchCounters::CutoffIndices - 1)];
          ++counters.beta_cutoffs;
          counters.first_move_cutoffs += moves_searched == 1;
          counters.cutoff_index_sum += static_cast<std::uint64_t>(moves_searched - 1);
#endif
          break;
        }
        alpha = score;
      }
    }
    if (quiet || m.is_capture()) f.failed_moves.add(m);
    // Once a move has been searched at a futile node not already lost to a
    // mate, every later non-checking quiet is pruned (the conditions at the
    // top of this loop), and both conditions only grow more true: the
    // selector may drop those quiets unscored.
    if (!quiet_checks_only && futile_node && best > -MateBandFloor) {
      f.selector.keep_quiet_checks();
      quiet_checks_only = true;
    }
  }
  // Futility pruning (T22): at a futile node the selector drops the quiets
  // that do not give check (keep_quiet_checks above), so every quiet the
  // loop sees there is a checking one. The bound stays honest as if each
  // dropped quiet had been seen.
  if (f.selector.quiets_filtered() > 0)
    best = std::max(best,
                    FORK_STAT_GATE(force == LedgerForce::FutilityOn ? std::min(futility_value, alpha_start) :)
                        futility_value);
  FORK_STAT(counters.futility_prunes += static_cast<std::uint64_t>(f.selector.quiets_filtered()));
  // No legal move is mate or stalemate; legal moves that were all pruned are
  // not (the guard above prevents it; this keeps the result right regardless).
  // Without its withheld move a node may have none left: it fails low, so the
  // withheld move counts as singular.
  if (moves_seen == 0) return withheld ? alpha : in_check ? mated_score(ply) : 0;
  if (moves_searched == 0) return best;
  best = std::clamp(best, table_floor, table_ceiling);
  if (switches.use_tt && !withheld) {
    const TtBound bound = result_bound(best, alpha_start, beta, OnPv);
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
  FORK_STAT(++(OnPv ? counters.quiesce_nodes_pv : counters.quiesce_nodes_non_pv));
  if (poll_limits()) return 0;
  max_ply_reached_ = std::max(max_ply_reached_, ply);
  Position& pos = *pos_;
  PlyFrame& f = frames_[ply];
  const bool in_check = pos.in_check();

  if (pos.repetition_count() >= 2 || pos.insufficient_material()) return 0;
  if (pos.fifty_move_reached()) return fifty_move_score(pos, in_check, ply);
  if (ply >= MaxPly) {
    FORK_STAT(counters.evals_horizon += !in_check);
    return in_check ? 0 : eval_at(ply);
  }

  const Key key = pos.key();
  TtHit hit{};
  const bool tt_hit = switches.use_tt && tt_.fetch(key, hit);
  if (tt_hit && !OnPv && (!switches.tt_exact_depth || hit.depth == 0)) {
    const int s = score_from_tt(hit.score, ply);
    if (bound_settles(hit.bound, s, alpha, beta)) return s;
  }

  const int alpha_start = alpha;
  int best = -ScoreInfinite;
  if (in_check) {
    f.static_eval = ScoreNone;
    FORK_STAT(++counters.check_nodes_quiesce);
  } else {
    f.static_eval = tt_hit && hit.eval != ScoreNone ? hit.eval : eval_gated(ply, alpha, beta);  // as in negamax
    FORK_STAT(++(tt_hit && hit.eval != ScoreNone ? counters.tt_eval_hits_quiesce : counters.evals_quiesce));
#ifdef FORK_SEARCH_STATS
    // Crucial-point ground truth: a sampled quiescence evaluation site.
    if (eval_site_every_quiesce_ && !ledger_active_ &&
        ++eval_site_seen_quiesce_ % eval_site_every_quiesce_ == 0)
      print_eval_site(1, tt_hit && hit.eval != ScoreNone, alpha, beta, f.static_eval, f.static_eval, 0, ply,
                      tt_hit, hit, OnPv);
    {  // Idea 59 step 1: the stand-pat evaluation's window gap.
      const bool reused = tt_hit && hit.eval != ScoreNone;
      const int gap = window_gap(f.static_eval, alpha, beta);
      if (gap < 0)
        ++(reused ? counters.eval_gap_quiesce_reuse_infinite : counters.eval_gap_quiesce_infinite);
      else
        ++(reused ? counters.eval_gap_quiesce_reuse_bins
                  : counters.eval_gap_quiesce_bins)[window_gap_bin(gap)];
      if (!reused && gap >= 0)
        counters.eval_gap_quiesce_one_sided += is_tb_or_mate(alpha) != is_tb_or_mate(beta);
    }
#endif
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
                           switches.use_history ? &history_ : nullptr,
                           switches.use_take_history ? &take_history_ : nullptr, switches.use_threat_buckets);

  Move best_move = NoMove;
  int moves_searched = 0;
  for (Move m; !(m = f.selector.take_next()).is_none();) {
    ++moves_searched;
    if (switches.use_tt) tt_.prefetch_bucket(pos.predicted_key(m));
#ifdef FORK_SEARCH_STATS
    const bool pawn_move = kind_of(pos.piece_at(m.from())) == Pawn;
    counters.pawn_makes += pawn_move;
    counters.pawn_makes_quiesce += pawn_move;
#endif
    play(ply, m);
    FORK_STAT(++counters.makes);
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
    const TtBound bound = result_bound(best, alpha_start, beta, OnPv);
    tt_.deposit(key, best_move, score_to_tt(best, ply), f.static_eval, 0, bound, OnPv);
  }
  return best;
}

int Searcher::search_root(int alpha, int beta, int depth) {
  Position& pos = *pos_;
  ++nodes_;
  FORK_STAT(++counters.root_nodes);
  pv_[0].length = 0;
  int best = -ScoreInfinite;
  // The root node counts too, so a node limit reached here stops here, not
  // one node later in the first child (audit-1, A1 suspicion 8).
  if (poll_limits()) return best;
  std::size_t best_index = 0;  // the move that last raised alpha
  for (std::size_t i = 0; i < root_count_; ++i) {
    const Move m = root_moves_[i].move;
    branch_share_ = root_moves_[i].share;
    const std::uint64_t nodes_before = nodes_;
    frames_[1].arrival = pair_slot(pos.piece_at(m.from()), m.to());
    frames_[1].expected_cut = i > 0;  // the root's later moves: expected cut nodes (T17)
    play(0, m);
    int score;
    if (i == 0 || !switches.use_pvs) {
      score = -negamax<true>(-beta, -alpha, depth - 1, 1);
    } else {
      score = -negamax<false>(-alpha - 1, -alpha, depth - 1, 1);
      if (!stopped_ && score > alpha && score < beta) score = -negamax<true>(-beta, -alpha, depth - 1, 1);
    }
    pos.unmake(m);
    root_moves_[i].nodes = nodes_ - nodes_before;
    root_moves_[i].nodes_all_passes += root_moves_[i].nodes;  // every pass's moves, before a stop returns
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

std::int64_t Searcher::soft_limit_now(const SearchQuota& limits) const {
  if (!switches.use_stability_time) return limits.soft_ms;
  const TimeScaleVariant variant =
      switches.use_share_time ? TimeScaleVariant::StabilityAndShare : TimeScaleVariant::StabilityOnly;
  return scaled_soft_ms(limits.soft_ms, limits.hard_ms, soft_scale_permille(variant, time_signals_));
}

#ifdef FORK_SEARCH_STATS
// X6 (DESIGN.md §5.7): after a finished iteration (its shares computed), the
// best move (the front root move, as a raw 16-bit move), its per mille of
// the last pass's nodes and of every pass's, the largest other root move's
// per mille of the last pass, the last pass's and the whole iteration's
// nodes, the score, the aspiration passes, the root moves and the deepest
// ply. Integers only, no allocation.
void Searcher::trace_iteration(int depth, int score, int passes, std::uint64_t iteration_nodes) const {
  std::uint64_t last_pass = 0, all_passes = 0;
  int runner_up = 0;
  for (std::size_t i = 0; i < root_count_; ++i) {
    last_pass += root_moves_[i].nodes;
    all_passes += root_moves_[i].nodes_all_passes;
    if (i > 0) runner_up = std::max(runner_up, root_moves_[i].share);
  }
  const std::uint64_t share_all = all_passes ? root_moves_[0].nodes_all_passes * 1000 / all_passes : 0;
  std::fprintf(stderr, "iteration_trace %d|%u|%d|%llu|%d|%llu|%llu|%d|%d|%d|%d\n", depth,
               static_cast<unsigned>(root_moves_[0].move.raw()), root_moves_[0].share,
               static_cast<unsigned long long>(share_all), runner_up,
               static_cast<unsigned long long>(last_pass), static_cast<unsigned long long>(iteration_nodes),
               score, passes, static_cast<int>(root_count_), max_ply_reached_);
}
#endif

#ifdef FORK_SEARCH_STATS
// Crucial-point ground truth (DESIGN.md §5.7): the site's kind, whether
// its evaluation was reused from the TT, the window, the static and the
// TT-refined evaluation, the depth (0 in quiescence), the ply, the parent's
// static evaluation (from the opponent's view; ScoreNone if none), the TT
// entry's bound and depth, whether the move that led here captured, the PV
// flag, and the FEN last. Integers except the FEN, which allocates a string:
// stats builds only, at sampled sites only (as FORK_SINGULAR_PROBE does).
void Searcher::print_eval_site(int kind, bool reused, int alpha, int beta, int eval, int prune_eval,
                               int depth, int ply, bool tt_hit, const TtHit& hit, bool on_pv) const {
  const int parent_eval = ply > 0 ? frames_[ply - 1].static_eval : ScoreNone;
  std::fprintf(stderr, "eval_site %d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%s\n", kind, reused ? 1 : 0, alpha,
               beta, eval, prune_eval, depth, ply, parent_eval, tt_hit ? static_cast<int>(hit.bound) : 0,
               tt_hit ? static_cast<int>(hit.depth) : -1, pos_->state().captured != NoPiece ? 1 : 0,
               on_pv ? 1 : 0, pos_->fen().c_str());
}

int Searcher::ledger_side_search(int alpha, int beta, int depth, int ply, LedgerForce force,
                                 std::uint64_t& side_nodes) {
  // A side search must leave the real search exactly as it was: no node
  // count, no node or time limit (the stop flag still ends it, and then the
  // real search stops too), no TT write, no history update, no counter.
  static const SearchQuota ledger_quota;  // no limits
  ledger_saved_counters_ = counters;
#if defined(FORK_EVAL_NNUE)
  ledger_saved_tally_ = features_.tally();
#endif
  const std::uint64_t saved_nodes = nodes_, saved_hits = table_hits_;
  const int saved_max_ply = max_ply_reached_;
  const SearchQuota* saved_limits = limits_;
  limits_ = &ledger_quota;
  ledger_active_ = true;
  tt_.set_hold_writes(true);
  ledger_force_ = force;
  ledger_force_ply_ = ply;
  const int score = negamax<false>(alpha, beta, depth, ply);
  ledger_force_ = LedgerForce::Keep;
  tt_.set_hold_writes(false);
  ledger_active_ = false;
  limits_ = saved_limits;
  side_nodes = nodes_ - saved_nodes;
  nodes_ = saved_nodes;
  table_hits_ = saved_hits;
  max_ply_reached_ = saved_max_ply;
  counters = ledger_saved_counters_;
#if defined(FORK_EVAL_NNUE)
  features_.set_tally(ledger_saved_tally_);
#endif
  counters.ledger_side_nodes += side_nodes;
  return score;
}
#endif

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
  frames_[0].arrival = NoArrival;
#if defined(FORK_EVAL_NNUE)
  features_.reset(*net_, pos);
#endif
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
  stable_iterations_ = 0;
  stable_move_ = NoMove;
  time_signals_ = {};
  last_soft_ms_ = limits.soft_ms;
  frames_[0].arrival = NoArrival;  // the root has none (the follow table's arrival at ply 1)

#if defined(FORK_EVAL_NNUE)
  features_.reset(*net_, pos);
#endif
  tt_.advance_age();
  tt_.set_age_blend(switches.tt_age_blend);
  tt_.set_keep_exact(switches.tt_keep_exact);
  tt_.set_keep_deeper(switches.use_tt_keep_deeper);
  SearchResult result;
  // The first iteration's root order is the selector's (no TT move).
  PlyFrame& root = frames_[0];
  MoveList root_list;  // once per search, so a local list
  root.selector.start_main(pos, NoMove, switches.use_history ? &history_ : nullptr, nullptr, NoArrival,
                           NoArrival, nullptr, switches.use_threat_buckets);
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
#ifdef FORK_SEARCH_STATS
    // X6: the passes and the iteration's nodes (every pass's nodes per root
    // move are reset below, in every build: time management reads them).
    int passes = 0;
    const std::uint64_t iteration_start = nodes_;
#endif
    iteration_best_ = NoMove;
    iteration_best_score_ = -ScoreInfinite;
    root_fail_high_ = NoMove;
    for (std::size_t i = 0; i < root_count_; ++i) root_moves_[i].nodes_all_passes = 0;
    int delta = AspirationHalfWidth;
    int alpha = -ScoreInfinite, beta = ScoreInfinite;
    if (switches.use_aspiration && depth >= AspirationMinDepth && !is_tb_or_mate(previous)) {
      alpha = std::max(previous - delta, -ScoreInfinite);
      beta = std::min(previous + delta, ScoreInfinite);
    }
    int score;
    for (;;) {
      score = search_root(alpha, beta, depth);
      FORK_STAT(++passes);
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
      } else {
        beta = is_tb_or_mate(score) ? ScoreInfinite : std::min(score + delta, ScoreInfinite);
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
      // The result then takes this iteration's depth with its move and
      // score, so it describes the same search as the last info line
      // (time_signals() keeps the last finished iteration).
      if (!iteration_best_.is_none() && result.depth > 0 && iteration_best_score_ > previous) {
        result.best = iteration_best_;
        result.score = iteration_best_score_;
        result.depth = depth;
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
    score_trend_ = depth > 1 ? std::clamp(score - previous, -ScoreTrendLimit, ScoreTrendLimit) : 0;
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
    // Time management's signals (§5.6 step 10, X6's definitions): stability
    // counts finished iterations in a row with this best move (1 for the
    // first), and the share is the best move's per mille of every pass's
    // nodes. Kept in every search (cheap); read only with use_stability_time.
    stable_iterations_ = result.best == stable_move_ ? stable_iterations_ + 1 : 1;
    stable_move_ = result.best;
    std::uint64_t all_passes = 0;
    for (std::size_t i = 0; i < root_count_; ++i) all_passes += root_moves_[i].nodes_all_passes;
    time_signals_ = {depth, stable_iterations_,
                     all_passes ? static_cast<int>(root_moves_[0].nodes_all_passes * 1000 / all_passes) : 0,
                     score};
#ifdef FORK_SEARCH_STATS
    if (trace_iterations_) trace_iteration(depth, score, passes, nodes_ - iteration_start);
#endif
    report_iteration(depth, score, 0, pv_[0]);
    if (limits.mate_moves > 0 && is_mate_score(score) && score > 0 &&
        mate_in_moves(score) <= limits.mate_moves)
      break;
    const bool timed = !(pondering && pondering->load(std::memory_order_relaxed));
    last_soft_ms_ = soft_limit_now(limits);
    if (timed && limits.soft_ms >= 0 && elapsed_ms() >= last_soft_ms_) break;
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
#ifdef FORK_SEARCH_STATS
  // Phase 4 step 1 (DESIGN.md §5.7): cumulative counters after each search,
  // for tools/measure/game_replay.py, which takes the differences.
  if (report_counters_) {
#if defined(FORK_EVAL_NNUE)
    print_counter_dump(counters, &features_.tally(), stderr);
#else
    print_counter_dump(counters, nullptr, stderr);
#endif
  }
#endif
  return result;
}

}  // namespace forkeng
