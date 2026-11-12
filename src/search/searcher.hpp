// SPDX-License-Identifier: GPL-3.0-or-later

// searcher: the alpha-beta search (DESIGN.md §5.2, deliverables 2-6).
//
// Purpose: iterative deepening with aspiration windows over a fail-soft
// principal variation search (negamax), with draw detection, mate distance
// pruning and a transposition table, ending in a quiescence search over
// captures and queen promotions (all evasions in check).
// Invariants:
// - One Searcher per search thread; it owns all per-thread state (the search
//   stack, PVs, root moves) and is created once, outside any search: deliberate()
//   never allocates (tests/alloc_test.cpp).
// - Scores follow score_bounds.hpp: fail-soft, from the side to move's view,
//   mates by distance from the root.
// - deliberate() is deterministic for a given position, limits, switches, TT
//   contents and move-ordering history when no time limit applies (bench
//   parity); the history persists between searches until clear_history()
//   (ucinewgame, Clear Hash, each bench position).
// - No exceptions, virtual calls or std::function inside the recursion; the
//   listener is called outside it: once per finished iteration (bound 0),
//   once per reported aspiration fail (bound +1 or -1, after fail_report_ms),
//   and at most once more when a search stops, repeating or replacing the
//   last line (audit-1, A1 S-2: this said "once per finished iteration only").
// - Every technique has a switch in SearchSwitches, so one binary can test
//   it on and off; release defaults follow the SPRT log, and the provisional
//   ones are marked where they are declared (audit-1, A7 D-19).
#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>
#include <optional>

#include "core/position.hpp"
#include "search/move_selector.hpp"
#include "search/quiet_history.hpp"
#include "search/score_bounds.hpp"
#include "search/time_budget.hpp"
#include "search/trans_table.hpp"

#if defined(FORK_EVAL_NNUE)
#include "eval/nnue/accumulator.hpp"
#endif

namespace forkeng {

struct SearchQuota {
  int depth = MaxPly - 1;     // iterations to finish at most
  std::uint64_t nodes = 0;    // 0: no node limit
  int mate_moves = 0;         // > 0: stop once a mate in at most this many moves is found
  std::int64_t soft_ms = -1;  // -1: none; checked between iterations
  std::int64_t hard_ms = -1;  // -1: none; polled during the search
  MoveList restrict_to;       // searchmoves; empty: every legal move
  // When `go` arrived: the time limits count from here, so work done before
  // the search starts (a Hash change applied at go) uses the move's time.
  // Default: when deliberate() starts.
  std::optional<std::chrono::steady_clock::time_point> go_received;
};

// Technique switches (DESIGN.md §5.2: every technique sits behind a flag):
// X(member, option name in tuning builds, default). One list, so a switch
// cannot exist without its tuning option (src/uci/session.cpp; a hand-kept
// second list lost six switches once, in 6ab7cb7).
// - use_see_quiesce: qsearch skips captures that lose material by SEE.
// - use_history: quiet moves ordered by butterfly history (else generation
//   order); use_history_malus: quiets tried before a cutoff lose what the
//   cutoff move gains.
// - Tier 1 pruning and reductions (deliverable 6): reverse futility (T20),
//   null move (T13), LMR (T15), LMP (T21), futility (T22), SEE pruning in
//   the main search (T23).
// - tt_age_blend: TT victims ranked by depth minus two plies per search of
//   age instead of current-search-first (owner's experiment, 2026-10-26;
//   off by default).
// - tt_keep_exact: an exact TT entry is not replaced by a bound of the same
//   depth from the same search (review 2, claim (e), 2026-10-26; off by
//   default).
// - use_tt_eval_refine: pruning decisions use the static eval corrected by
//   the TT score's bound (review 2, claim (d); KB T50). On by default since
//   2026-10-26, provisionally (owner): its SPRT was stopped undecided, so
//   the end-of-Phase-3 removal round verifies it, at 40+0.4 too.
// - use_forced_move_stop: with one root move a timed search stops at
//   1 / ForcedMoveFraction of its soft limit (audit-1, B-1).
// - use_tt_keep_deeper: a stale TT entry still deeper after aging is kept
//   against an inexact result (audit-1, B-5). Off by default (owner,
//   2026-10-28): its LTC SPRT was stopped undecided, leaning negative; it
//   is retested with Phase 6's TT tests under large Hash and many threads.
// - use_tables: Syzygy endgame tables, when loaded (deliverable 7):
//   win/draw/loss probes in the search and the ranking of root moves.
// - use_lmr_check_relief: a late quiet move that gives check is reduced
//   LmrCheckRelief plies less (tier 2 step 0, KB T16's check term; its STC
//   SPRT passed, +11.26 +/- 5.54 Elo; owner, 2026-10-29).
// - use_lmr_in_check: late quiet evasions get the normal reduction instead
//   of none (tier 2 step 0, KB T16's in-check term, §3.28: Halogen #212
//   gained by replacing the exemption with normal LMR; its STC SPRT passed,
//   +4.21 +/- 2.89 Elo).
// - use_singular_extension: a TT move that the singular test shows to be the
//   only good move is searched one ply deeper (tier 2, T27). On since its
//   STC SPRT passed: +14.12 +/- 6.55 Elo after 4,800 games ([0, 5],
//   2026-10-31).
// - use_multi_cut, use_negative_extension: the same test's other outcome at
//   non-PV nodes (T28, T30): a node where another move also reaches a bar at
//   or above beta fails high at once; otherwise a TT move whose score is at
//   or above beta is searched one ply shallower. Multi-cut is on since its
//   STC SPRT passed (+9.19 +/- 4.62 Elo after 9,600 games, [0, 3]); the
//   negative extension is off: its SPRT rejected it (-8.73 +/- 4.98 Elo
//   after 8,000 games, H0; 2026-10-31).
// - use_reply_history: quiet moves are also ordered by the pair history
//   after the opponent's last move, updated with the butterfly history's
//   bonus and malus (tier 2, T10, the 1-ply table). On since its STC SPRT
//   passed (+11.46 +/- 5.57 Elo after 6,400 games, [0, 5]; 2026-11-01).
// - use_follow_history: the same after the side's own previous move, two
//   plies back (T10's 2-ply table). On since its STC SPRT passed (+7.22
//   +/- 3.92 Elo after 12,800 games, [0, 3]; 2026-11-01).
// - use_take_history: captures are ordered by their victim and the take
//   history instead of MVV-LVA; a capture that cuts gains the history bonus,
//   and the captures tried before any cutoff take it as a malus (tier 2,
//   T11). On since its STC SPRT passed (+4.53 +/- 2.99 Elo after 22,400
//   games, [0, 3]; 2026-11-01).
// - use_no_move_reduction: a node without a TT move, at least
//   NoMoveReduceMinDepth deep, is searched one ply shallower (tier 2, T26,
//   internal iterative reduction). On since its STC SPRT passed (+21.45
//   +/- 5.98 Elo after 4,800 games, [0, 3]; 2026-11-02).
// - use_stability_time, use_share_time: a timed search's soft limit is
//   scaled after each finished iteration by soft_scale_permille
//   (time_budget.hpp; §5.6 step 10, think tank R8): use_stability_time alone
//   by best-move stability (variant a), both by stability and the best
//   move's every-pass node share (variant b); use_share_time alone does
//   nothing. (b) won the head-to-head against (a) and is on (both
//   switches) since its SPRTs against off passed: STC +18.69 +/- 7.18 Elo
//   after 3,200 games, LTC +10.23 +/- 5.14 Elo after 4,992 games, design R
//   [0, 6]; 2026-11-08.
// - use_cut_node_lmr: node types (tier 2, T17): each node gets an expected
//   type from its parent (PlyFrame::expected_cut: a PV node's later children
//   and an all node's children are expected cut nodes, a cut node's are
//   expected all nodes), and at an expected cut node late quiet moves are
//   reduced CutNodeLmrPlies more. On since its SPRTs against off passed
//   (CutNodeLmrPlies 1, the head-to-head's pick over 2): STC +6.02 +/- 3.67
//   Elo after 11,200 games, LTC +9.75 +/- 5.14 Elo after 4,992 games, design
//   R [0, 6]; 2026-11-11.
// - use_threat_buckets: the butterfly history is read and updated in one of
//   four buckets by whether the opponent attacks the quiet move's from- and
//   to-square before the move (tier 2, T56's threat-indexed history, "any
//   enemy attack"; quiet_history.hpp). Off: every move uses bucket 0, the
//   table as before. On since its SPRTs against off passed: STC +7.49 +/-
//   4.89 Elo after 6,400 games, LTC +8.07 +/- 5.15 Elo after 4,992 games,
//   design R [0, 6]; 2026-11-11.
// - use_capture_probe: ProbCut (tier 2, T31): at a non-PV node at least
//   CaptureProbeMinDepth deep, a capture that holds CaptureProbeMargin above
//   beta in a quiescence search and then in a search CaptureProbeReduction
//   plies shallower than a normal child makes the node fail high. Its STC
//   SPRT on S512r2 ended H0 (-5.29 +/- 3.58 Elo after 12,800 games,
//   2026-11-06); on since its one LTC-only design R test on the tuned search
//   (owner, 2026-11-11) passed: +9.40 +/- 5.03 Elo after 4,992 games, design
//   R [0, 6]; 2026-11-11.
// - use_pass_best_stop: the stop rule for a search stopped mid-iteration
//   (bug review 2026-11-11, E1; searcher.cpp, the stop rule). Off: a move
//   from the unfinished iteration is played only if its exact score beats
//   the last finished iteration's. On: also once the last finished
//   iteration's best move has been searched again in the unfinished pass,
//   whatever the score, since the pass's best exact move is then that move
//   or one that scored above it at the new depth; the iteration's best is
//   kept per aspiration pass, so an earlier pass cannot supply it. An
//   unresolved root fail high is never played either way. Its STC design R
//   SPRT against off was capped undecided (+3.26 +/- 3.35 Elo after 12,800
//   games, [0, 6]); on since its non-regression SPRT then passed (+2.41 +/-
//   2.69 Elo after 20,800 games, [-3, 0]; the owner's rule, 2026-11-12).
// - use_material_scale: the static evaluation is scaled down as non-pawn
//   material leaves the board: by MaterialScaleSlope per mille per pawn unit
//   below MaterialScaleFull units (both sides; core/material.hpp's
//   non_pawn_units), 1000 per mille at or above it (the engine survey's F10,
//   the think tank's R33 in its simplest form). The search, the TT and the
//   data generator's labeller all see the scaled value. Off until its SPRT.
#define FORK_SEARCH_SWITCHES(X)                          \
  X(use_tt, UseTT, true)                                 \
  X(use_pvs, UsePvs, true)                               \
  X(use_aspiration, UseAspiration, true)                 \
  X(use_mate_distance, UseMateDistance, true)            \
  X(use_quiesce, UseQuiesce, true)                       \
  X(use_see_quiesce, UseSeeQuiesce, true)                \
  X(use_history, UseHistory, true)                       \
  X(use_history_malus, UseHistoryMalus, true)            \
  X(use_rfp, UseRfp, true)                               \
  X(use_nmp, UseNmp, true)                               \
  X(use_lmr, UseLmr, true)                               \
  X(use_lmp, UseLmp, true)                               \
  X(use_futility, UseFutility, true)                     \
  X(use_see_prune, UseSeePrune, true)                    \
  X(tt_age_blend, UseTtAgeBlend, false)                  \
  X(tt_keep_exact, UseTtKeepExact, false)                \
  X(use_tt_eval_refine, UseTtEvalRefine, true)           \
  X(use_forced_move_stop, UseForcedMoveStop, true)       \
  X(use_tt_keep_deeper, UseTtKeepDeeper, false)          \
  X(use_tables, UseTables, true)                         \
  X(use_lmr_check_relief, UseLmrCheckRelief, true)       \
  X(use_lmr_in_check, UseLmrInCheck, true)               \
  X(use_singular_extension, UseSingularExtension, true)  \
  X(use_multi_cut, UseMultiCut, true)                    \
  X(use_negative_extension, UseNegativeExtension, false) \
  X(use_reply_history, UseReplyHistory, true)            \
  X(use_follow_history, UseFollowHistory, true)          \
  X(use_take_history, UseTakeHistory, true)              \
  X(use_no_move_reduction, UseNoMoveReduction, true)     \
  X(use_stability_time, UseStabilityTime, true)          \
  X(use_share_time, UseShareTime, true)                  \
  X(use_cut_node_lmr, UseCutNodeLmr, true)               \
  X(use_threat_buckets, UseThreatBuckets, true)          \
  X(use_capture_probe, UseCaptureProbe, true)            \
  X(use_pass_best_stop, UsePassBestStop, true)           \
  X(use_material_scale, UseMaterialScale, true)

struct SearchSwitches {
#define FORK_SWITCH_MEMBER(member, option, value) bool member = value;
  FORK_SEARCH_SWITCHES(FORK_SWITCH_MEMBER)
#undef FORK_SWITCH_MEMBER
  // Tests only (no option): a TT entry cuts only at exactly the depth it was
  // searched to, so a search equals plain minimax (tests/test_search.cpp).
  bool tt_exact_depth = false;
};

// The move played with the score and depth of the search behind it: those of
// the last reported line. That is the last finished iteration, or the
// unfinished one when a stop takes its move (searcher.cpp, the stop rule;
// then one more than time_signals().depth). depth is 0 only if no iteration
// finished.
struct SearchResult {
  Move best = NoMove;
  int score = 0;
  int depth = 0;
  std::uint64_t nodes = 0;
};

struct PrincipalLine {
  Move moves[MaxPly];
  int length = 0;
};

struct IterationReport {
  int depth;
  int max_ply_reached;
  int score;
  int bound;  // 0 exact, +1 lower bound (aspiration fail high), -1 upper bound (fail low)
  std::uint64_t nodes;
  std::int64_t elapsed_ms;
  int fill_permille;
  const PrincipalLine* pv;
  std::uint64_t table_hits;  // successful endgame-table probes so far (UCI tbhits)
};

// Receives one report per finished iteration (and per reported aspiration
// fail); called from the search thread, outside the recursion.
class SearchListener {
 public:
  virtual void on_iteration(const Position& root, const IterationReport& report) = 0;

 protected:
  ~SearchListener() = default;
};

// One ply of the search stack.
struct PlyFrame {
  MoveSelector selector;
  MoveList failed_moves;        // quiet moves and captures searched here without a cutoff (the maluses)
  int static_eval;              // ScoreNone in check
  bool after_null = false;      // this node was reached by a null move (no second one in a row)
  Move withheld_move = NoMove;  // set while a singular test searches this node without that move
  int arrival = NoArrival;      // the pair-history slot of the move that led here (none after a null move)
  bool expected_cut = false;    // expected to fail high (a cut node), from the parent (T17)
};

// Root moves are kept in search order: the initial capture order, then after
// every root search the move that last raised alpha moves to the front and
// the others keep their order (Fork's rule; the PV move is searched first).
struct RootEntry {
  Move move;
  std::uint64_t nodes = 0;             // nodes under this move in the current iteration's last pass
  int share = 0;                       // its per mille of the last finished iteration's nodes
  std::uint64_t nodes_all_passes = 0;  // nodes under it in every aspiration pass of the current iteration
};

// The moved piece's facts for the LMR context, from the position after a
// quiet move: its type, whether the opponent attacked its square before the
// move (on the board as it stood then), and whether it now attacks an enemy
// piece other than a pawn or the king. Always inlined (its helpers are all
// inline table lookups), so a compiler drops the work when the LMR rule reads
// none of the facts: g++ 11.4 with LTO (a TCEC compiler) called it at every
// LMR site otherwise, while clang inlined and dropped it (audit-1, P-1). A
// castling move is read as its king's move: it is encoded king to rook
// square, so its target square may be empty afterwards.
struct LmrMoveFacts {
  int piece;
  bool threatened;
  bool attacks;
};
[[gnu::always_inline]] inline LmrMoveFacts lmr_move_facts(const Position& after, Move m) {
  const Color them = after.side_to_move();
  const Color mover = ~them;
  const Bitboard targets = after.pieces(them) & ~after.pieces(Pawn) & ~after.pieces(King);
  // Castling is legal only out of check, so the king's square was not
  // attacked; the king now stands on its landing square.
  if (m.is_castle()) return {King, false, (king_attacks(after.king_square(mover)) & targets) != 0};
  const Square from = m.from(), to = m.to();
  const PieceType type = kind_of(after.piece_at(to));
  const Bitboard before = (after.pieces() & ~bb(to)) | bb(from);
  const Bitboard diagonal = after.pieces(them, Bishop, Queen), straight = after.pieces(them, Rook, Queen);
  const Bitboard attackers =
      (pawn_attacks(mover, from) & after.pieces(them, Pawn)) |
      (knight_attacks(from) & after.pieces(them, Knight)) | (bishop_attacks(from, before) & diagonal) |
      (rook_attacks(from, before) & straight) | (king_attacks(from) & after.pieces(them, King));
  const Bitboard reach = type == Pawn ? pawn_attacks(mover, to) : attacks(type, to, after.pieces());
  return {static_cast<int>(type), attackers != 0, (reach & targets) != 0};
}

// The LMR context's history: the mover's entry for the move, read from the
// position after the move, where the mover is the side not to move (b89185f:
// it read the opponent's table; tests/test_pruning.cpp). `bucket` is the
// move's threat bucket, taken before the move was made (T56; 0 when off).
inline int mover_history(const QuietHistory& history, const Position& after, Move m, int bucket = 0) {
  return history.value(~after.side_to_move(), m, bucket);
}

// Debug counters (DESIGN.md §5.2), compiled in only with the CMake option
// FORK_SEARCH_STATS: they show whether ordering and pruning behave as
// intended, which an Elo test cannot. Normal builds have none.
// FORK_STAT(statement) runs a counter statement in stats builds only.
#ifdef FORK_SEARCH_STATS
#define FORK_STAT(...) __VA_ARGS__
#else
#define FORK_STAT(...) static_cast<void>(0)
#endif
// FORK_STAT_GATE(tokens): tokens that stats builds add to a search
// condition (the decision ledger's force, X10); nothing in normal builds,
// so their conditions are exactly as written without it.
#ifdef FORK_SEARCH_STATS
#define FORK_STAT_GATE(...) __VA_ARGS__
#else
#define FORK_STAT_GATE(...)
#endif

#ifdef FORK_SEARCH_STATS
// The decision ledger (DESIGN.md §5.7, X10): one technique switched at one
// node of a side search: RFP off, futility off, or futility on (dropping
// the non-checking quiets after the first move, its bound capped at alpha
// so the arm claims a fail low, as the rule always does).
enum class LedgerForce : std::uint8_t { Keep, RfpOff, FutilityOff, FutilityOn };
#endif
// The scalar counters, one list (as the switches above), so the per-search
// dump (stats_report.hpp) cannot miss one: X(member).
// - beta_cutoffs: main-search nodes that failed high; first_move_cutoffs:
//   ... on the first move searched; cutoff_index_sum: the cutoff move's index
//   summed (0 = first); makes: moves made in the main and quiescence searches.
// - Deliverable 6: nodes cut by RFP and the null move; moves pruned by LMP,
//   futility and SEE; LMR's reduced searches, their full-depth re-searches,
//   and the plies the reductions took off (the loop's mean-reduction
//   descriptor).
// - The heuristic-discovery rule (lmr_correction, idea 23): the LMR sites it
//   ran at, those where it returned non-zero, and those where that changed
//   the reduction after scaling and clamping (the loop's trigger rate).
// - External review (2026-10-26). (c) SEE tests by the main-search SEE
//   pruning, by where the move came from: good captures (SEE >= 0 already
//   shown by the selector: skipped since claim (c)), bad captures (SEE < 0
//   shown by the selector), quiets, other (TT moves and in-check evasions);
//   bad captures reached after late move pruning stopped the quiets, and how
//   many SEE pruning then drops. (d) Futile nodes: quiet moves taken from
//   the selector there, and those searched (the checking ones and the first
//   move). (f) Quiescence nodes at PV and non-PV nodes.
// - Tier 2: nodes where a singular test could run (the measurement's
//   sampling); singular tests run (their searches); those that found the TT
//   move singular; those where another move also beat beta, so the node
//   failed high (multi-cut); those where the TT move was searched one ply
//   shallower; nodes without a TT move searched one ply shallower (T26);
//   captures the capture probe searched and the nodes it made fail high
//   (T31).
// - Phase 4 step 1, X1 (DESIGN.md §5.7): nodes at the root and in the main
//   search (with the quiescence nodes above they sum to the node count);
//   static evaluations computed, taken from the TT entry instead, or not
//   needed (in check), in the main and the quiescence search, and at the ply
//   limit (evals_horizon); moves made that move a pawn, all and in the
//   quiescence search alone.
// - X10: candidates of RFP and futility (every condition but the margin),
//   the ledger rows printed, and the nodes its side searches took (kept
//   apart: a side search restores every other counter).
// - Idea 59 step 1: evaluation sites whose window has no finite bound (both
//   in the mate or tablebase band), main and quiescence, computed and
//   reused from the TT; computed ones with exactly one finite bound.
// - X2: LMR sites whose node has no reply or no follow arrival (a null move
//   or the root above), so those tables have no entry; late captures (every
//   LMR gate passed but "quiet": R18's sites); and at LMR sites, where the
//   LMR history term of sprt/lmr-history would reduce less (its shift > 0),
//   more (< 0), and where it would change the reduction.
#define FORK_SEARCH_COUNTERS(X)      \
  X(beta_cutoffs)                    \
  X(first_move_cutoffs)              \
  X(cutoff_index_sum)                \
  X(makes)                           \
  X(rfp_cuts)                        \
  X(null_cuts)                       \
  X(lmp_prunes)                      \
  X(futility_prunes)                 \
  X(see_prunes)                      \
  X(lmr_searches)                    \
  X(lmr_researches)                  \
  X(lmr_plies_sum)                   \
  X(lmr_rule_sites)                  \
  X(lmr_rule_fires)                  \
  X(lmr_rule_changes)                \
  X(see_tests_good_captures)         \
  X(see_tests_bad_captures)          \
  X(see_tests_quiets)                \
  X(see_tests_other)                 \
  X(bad_captures_after_stop)         \
  X(bad_captures_after_stop_pruned)  \
  X(futile_nodes)                    \
  X(futile_quiets_taken)             \
  X(futile_quiets_searched)          \
  X(quiesce_nodes_pv)                \
  X(quiesce_nodes_non_pv)            \
  X(singular_candidates)             \
  X(singular_tests)                  \
  X(singular_extended)               \
  X(multi_cut_cuts)                  \
  X(negative_extensions)             \
  X(no_move_reductions)              \
  X(capture_probes)                  \
  X(capture_probe_cuts)              \
  X(root_nodes)                      \
  X(main_nodes)                      \
  X(evals_main)                      \
  X(tt_eval_hits_main)               \
  X(check_nodes_main)                \
  X(evals_quiesce)                   \
  X(tt_eval_hits_quiesce)            \
  X(check_nodes_quiesce)             \
  X(evals_horizon)                   \
  X(pawn_makes)                      \
  X(pawn_makes_quiesce)              \
  X(lmr_reply_absent)                \
  X(lmr_follow_absent)               \
  X(late_capture_sites)              \
  X(lmr_history_fire_less)           \
  X(lmr_history_fire_more)           \
  X(lmr_history_changes)             \
  X(ledger_rfp_candidates)           \
  X(ledger_futility_candidates)      \
  X(ledger_rows)                     \
  X(ledger_side_nodes)               \
  X(eval_gap_main_infinite)          \
  X(eval_gap_quiesce_infinite)       \
  X(eval_gap_main_reuse_infinite)    \
  X(eval_gap_quiesce_reuse_infinite) \
  X(eval_gap_main_one_sided)         \
  X(eval_gap_quiesce_one_sided)

// X2's histogram bins (DESIGN.md §5.7; measurement settings, no search
// effect). Sign-magnitude bins: the value 0 and the positive values fill the
// upper half from its first bin, the negative ones the lower half from its
// last, so every bin edge sits at a multiple of the width in |v| and the
// share at or beyond any multiple (24,000: the LMR history term's divisor)
// is exact. Table values, within [-HistoryMax, HistoryMax], in bins of 250
// (a fortieth of the range per side: fine enough for the quantiles; 82
// bins); ordering scores, within int16, in bins of 500 (24,000 is the 48th
// edge; 132 bins).
constexpr int TableBinWidth = 250;
constexpr int TableBins = 2 * (HistoryMax / TableBinWidth + 1);
constexpr int OrderBinWidth = 500;
constexpr int OrderBins = 2 * (INT16_MAX / OrderBinWidth + 1);
constexpr int table_value_bin(int v) {
  const int b = v >= 0 ? TableBins / 2 + v / TableBinWidth : TableBins / 2 - 1 - (-v) / TableBinWidth;
  return b < 0 ? 0 : b >= TableBins ? TableBins - 1 : b;
}
constexpr int order_score_bin(int s) {
  const int b = s >= 0 ? OrderBins / 2 + s / OrderBinWidth : OrderBins / 2 - 1 - (-s) / OrderBinWidth;
  return b < 0 ? 0 : b >= OrderBins ? OrderBins - 1 : b;
}
// The LMR history term being measured (branch sprt/lmr-history, 7d94d93:
// the base reduction less the ordering score / 24,000, integer division, so
// it acts only at |score| >= 24,000). A measurement setting: the stats build
// counts where the term would act, and the search never reads it.
constexpr int LmrHistoryProbeDivisor = 24000;
constexpr int lmr_history_probe_shift(int order_score) { return order_score / LmrHistoryProbeDivisor; }

// Idea 59 step 1 (DESIGN.md §5.7; measurement settings, no search effect):
// the gap between a static evaluation and the nearest finite bound of the
// node's window, in bins of 1 cp up to 255 (so a margin of any whole number
// of cp up to 255 is counted exactly), 64 cp up to 4,095 (the tail's shape),
// and one overflow bin. A bound in the mate or tablebase band counts as
// infinite: no gate could be set against it. Main-search sites are also
// split by remaining depth: 1, 2, 3-4, 5-7, 8 and more.
constexpr int GapBinsFine = 256;
constexpr int GapBins = GapBinsFine + (4096 - GapBinsFine) / 64 + 1;
constexpr int GapBands = 5;
// The gap, or -1 when neither bound is finite.
constexpr int window_gap(int eval, int alpha, int beta) {
  const bool low = !is_tb_or_mate(alpha), high = !is_tb_or_mate(beta);
  if (!low && !high) return -1;
  const int to_alpha = eval > alpha ? eval - alpha : alpha - eval;
  const int to_beta = eval > beta ? eval - beta : beta - eval;
  return !low ? to_beta : !high ? to_alpha : to_alpha < to_beta ? to_alpha : to_beta;
}
constexpr int window_gap_bin(int gap) {
  return gap < GapBinsFine ? gap : gap < 4096 ? GapBinsFine + (gap - GapBinsFine) / 64 : GapBins - 1;
}
constexpr int gap_depth_band(int depth) {
  return depth <= 1 ? 0 : depth == 2 ? 1 : depth <= 4 ? 2 : depth <= 7 ? 3 : 4;
}

struct SearchCounters {
#define FORK_COUNTER_MEMBER(member) std::uint64_t member = 0;
  FORK_SEARCH_COUNTERS(FORK_COUNTER_MEMBER)
#undef FORK_COUNTER_MEMBER
  // Quiet cutoffs at non-PV nodes out of check, by remaining depth (1-6) and
  // the cutting move's index among the quiets searched there (the late move
  // pruning measurement, DESIGN.md §5.2 deliverable 6).
  static constexpr int CutoffDepths = 7;
  static constexpr int CutoffIndices = 48;
  std::uint64_t quiet_cutoff_index[CutoffDepths][CutoffIndices] = {};
  // X2 (DESIGN.md §5.7): at LMR sites, the ordering score (quiet_order_score)
  // and the raw entries of the mover's butterfly history and of the reply
  // and follow tables (when the node has those arrivals); at late captures,
  // the take history's entry.
  std::uint64_t lmr_order_bins[OrderBins] = {};
  std::uint64_t lmr_quiet_bins[TableBins] = {};
  std::uint64_t lmr_reply_bins[TableBins] = {};
  std::uint64_t lmr_follow_bins[TableBins] = {};
  std::uint64_t late_take_bins[TableBins] = {};
  // Idea 59 step 1 (DESIGN.md §5.7): window gaps at evaluation sites with a
  // finite bound: computed in the main search and in quiescence, reused
  // from the TT entry (main, quiescence), and the computed main-search ones
  // by depth band (with each band's infinite-window count).
  std::uint64_t eval_gap_main_bins[GapBins] = {};
  std::uint64_t eval_gap_quiesce_bins[GapBins] = {};
  std::uint64_t eval_gap_main_reuse_bins[GapBins] = {};
  std::uint64_t eval_gap_quiesce_reuse_bins[GapBins] = {};
  std::uint64_t eval_gap_band_bins[GapBands][GapBins] = {};
  std::uint64_t eval_gap_band_infinite[GapBands] = {};
};

class Searcher {
 public:
  explicit Searcher(TransTable& tt);

  // Searches `pos` (restored on return) until a limit is reached or `stop`
  // becomes true. While `pondering` is true, time limits do not apply.
  SearchResult deliberate(Position& pos, const SearchQuota& limits, const std::atomic<bool>& stop,
                          const std::atomic<bool>* pondering, SearchListener* listener);

  SearchSwitches switches;
  // Aspiration fails are reported (as upperbound or lowerbound lines) only
  // once a search has run this long; tests set 0 to see every fail.
  std::int64_t fail_report_ms = 1000;
#ifdef FORK_SEARCH_STATS
  SearchCounters counters;
#if defined(FORK_EVAL_NNUE)
  // The network's update counts (X1), kept by the feature stack.
  const FeatureStackTally& feature_tally() const { return features_.tally(); }
#endif
#endif

  // Forgets the move-ordering history (ucinewgame, and each bench position).
  void clear_history() {
    history_.clear();
    for (PairHistory& table : pair_history_) table.clear();
    take_history_.clear();
  }
  // Tests only: the butterfly history (the threat buckets' read and update
  // checks, tier 2 T56).
  const QuietHistory& butterfly_view() const { return history_; }

  // Tests only: the root move that failed high in the iteration the last
  // deliberate() stopped in and was not yet re-searched to an exact score
  // (NoMove if none).
  Move unresolved_fail_high() const { return unresolved_fail_high_; }

  // Tests only: one zero-window search of `pos` as a non-PV node (window
  // [beta - 1, beta]), with no time limit; returns its fail-soft score.
  int probe_zero_window(Position& pos, int beta, int depth, const std::atomic<bool>& stop);

  // Tests only: moves the search's clock forward (called from a listener, on
  // the search thread, between iterations); the last finished iteration's
  // time-management signals (set before its report); and the soft limit the
  // last soft check compared against.
  void advance_clock(std::chrono::milliseconds by) { start_ -= by; }
  const IterationSignals& time_signals() const { return time_signals_; }
  std::int64_t last_soft_ms() const { return last_soft_ms_; }

 private:
  template <bool OnPv>
  int negamax(int alpha, int beta, int depth, int ply);
  template <bool OnPv>
  int quiesce(int alpha, int beta, int ply);
  int search_root(int alpha, int beta, int depth);

  // The evaluator's hooks (DESIGN.md §5.3, deliverable 5): every move and
  // null move the search makes, and every static evaluation, go through
  // these. With the bootstrap evaluation they are exactly make, make_null
  // and static_eval; with the network they also keep its per-ply
  // accumulators (FeatureStack). `ply` is the node's ply.
  void play(int ply, Move m);
  void play_null(int ply);
  int eval_at(int ply);

  bool poll_limits();  // true once the search must stop
  // The soft limit for this iteration's soft check: the planned one, or with
  // use_stability_time scaled by the last finished iteration's signals.
  std::int64_t soft_limit_now(const SearchQuota& limits) const;
  std::int64_t elapsed_ms() const;
  void record_cutoff(PlyFrame& f, Move m, int depth);
  // The follow table's arrival at frame `f`: the move that led to the ply
  // above, the side's own previous move (none at the root's children).
  int follow_arrival(const PlyFrame& f) const { return &f == frames_ ? NoArrival : (&f - 1)->arrival; }
  void update_pv(int ply, Move m);
  void report_iteration(int depth, int score, int bound, const PrincipalLine& pv);
#ifdef FORK_SEARCH_STATS
  // X6 (DESIGN.md §5.7): one `iteration_trace` line for a finished iteration.
  void trace_iteration(int depth, int score, int passes, std::uint64_t iteration_nodes) const;
  // X10: the node at `ply` searched again with `force` applied there only,
  // invisible to the real search (nodes, limits, TT writes, histories,
  // counters and the tally restored); `side_nodes` gets the nodes it took.
  int ledger_side_search(int alpha, int beta, int depth, int ply, LedgerForce force,
                         std::uint64_t& side_nodes);
  // Crucial-point ground truth (DESIGN.md §5.7): one `eval_site` line for a
  // sampled evaluation site (kind 0 main search, 1 quiescence).
  void print_eval_site(int kind, bool reused, int alpha, int beta, int eval, int prune_eval, int depth,
                       int ply, bool tt_hit, const TtHit& hit, bool on_pv) const;
  // X10: a decision at a position with this key is sampled (1 in ledger_every_).
  bool ledger_sampled(Key key) const { return key % ledger_every_ == 0; }
#endif

  TransTable& tt_;
  QuietHistory history_;
  PairHistory pair_history_[2];  // tier 2, T10: the reply and follow tables (ReplyTable, FollowTable)
  TakeHistory take_history_;     // tier 2, T11
  Position* pos_ = nullptr;
  const SearchQuota* limits_ = nullptr;
  const std::atomic<bool>* stop_ = nullptr;
  const std::atomic<bool>* pondering_ = nullptr;
  SearchListener* listener_ = nullptr;
  std::chrono::steady_clock::time_point start_;
  std::uint64_t nodes_ = 0;
  std::uint64_t table_hits_ = 0;
  int max_ply_reached_ = 0;
  bool stopped_ = false;

  PlyFrame frames_[MaxPly + 1];
  PrincipalLine pv_[MaxPly + 1];
  RootEntry root_moves_[MaxMoves];
  // The iteration's root move that failed high and is not yet resolved by a
  // re-search (review claim (a), 2026-10-26). Recorded, not played: a stop
  // keeps the previous iteration's move (ideas.md idea 29 measures how often
  // such fail highs hold).
  Move root_fail_high_ = NoMove;
  Move unresolved_fail_high_ = NoMove;
  std::size_t root_count_ = 0;
  // The best root move found in the running iteration with an exact score,
  // and its PV (reported if a stop makes it the move played).
  Move iteration_best_ = NoMove;
  int iteration_best_score_ = -ScoreInfinite;
  PrincipalLine iteration_pv_;
  // The last finished iteration's best move, and whether the running
  // aspiration pass has searched it to a score (use_pass_best_stop).
  Move prior_best_ = NoMove;
  bool prior_best_searched_ = false;
  // LMR context inputs kept by the search (lmr_table.hpp): the root score's
  // last change between iterations, and the share of the current root move.
  int score_trend_ = 0;
  int branch_share_ = 0;
  // The last finished iteration's PV, and the first move of the last line
  // reported: a stop after a reported fail repeats the finished iteration,
  // so the last line before bestmove names the move played.
  PrincipalLine finished_pv_;
  Move last_reported_ = NoMove;
  // Time management (§5.6 step 10): finished iterations in a row with the
  // same best move, that move, the last finished iteration's signals, and
  // the soft limit last compared against.
  int stable_iterations_ = 0;
  Move stable_move_ = NoMove;
  IterationSignals time_signals_;
  std::int64_t last_soft_ms_ = -1;
#ifdef FORK_SEARCH_STATS
  std::uint64_t singular_probe_ = 0;  // FORK_SINGULAR_PROBE: print every Nth singular candidate
  bool report_counters_ = false;      // FORK_STATS_REPORT: dump the counters after each search
  bool trace_iterations_ = false;     // FORK_ITERATION_TRACE: one line per finished iteration
  // X10: FORK_PRUNE_LEDGER's sampling rate (0: no ledger), whether a side
  // search is running, the force for the node it re-enters, and what it
  // restores afterwards.
  std::uint64_t ledger_every_ = 0;
  bool ledger_active_ = false;
  // Crucial-point ground truth: FORK_EVAL_SITES=N,M samples every Nth
  // main-search and every Mth quiescence evaluation site (0: none).
  std::uint64_t eval_site_every_main_ = 0;
  std::uint64_t eval_site_every_quiesce_ = 0;
  std::uint64_t eval_site_seen_main_ = 0;
  std::uint64_t eval_site_seen_quiesce_ = 0;
  LedgerForce ledger_force_ = LedgerForce::Keep;
  int ledger_force_ply_ = -1;
  SearchCounters ledger_saved_counters_;
#if defined(FORK_EVAL_NNUE)
  FeatureStackTally ledger_saved_tally_;
#endif
#endif
#if defined(FORK_EVAL_NNUE)
  const NetFile* net_;
  FeatureStack features_;
#endif
};

}  // namespace forkeng
