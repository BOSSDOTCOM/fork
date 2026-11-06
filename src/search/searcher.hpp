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
// - use_rising_rfp: reverse futility's margin is RfpRisingRelief cp smaller
//   when the side to move's static eval has risen since its previous turn
//   (tier 2, T18's flag, its RFP use alone: the owner's order tests one use
//   at a time). Off until measured and SPRTed.
// - use_threat_buckets: the butterfly history is read and updated in one of
//   four buckets by whether the opponent attacks the quiet move's from- and
//   to-square before the move (tier 2, T56's threat-indexed history, "any
//   enemy attack"; quiet_history.hpp). Off: every move uses bucket 0, the
//   table as before. Off until SPRTed.
// - use_cheaper_threats: with use_threat_buckets, a square counts as
//   threatened for the moving piece only when an enemy piece cheaper than it
//   attacks it (AttackTiers::threatening), not any enemy attack (T56's second
//   threat set, measured against the first). Off.
// - use_capture_probe: ProbCut (tier 2, T31): at a non-PV node at least
//   CaptureProbeMinDepth deep, a capture that holds CaptureProbeMargin above
//   beta in a quiescence search and then in a search CaptureProbeReduction
//   plies shallower than a normal child makes the node fail high. Off until
//   measured and SPRTed.
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
  X(use_rising_rfp, UseRisingRfp, false)                 \
  X(use_threat_buckets, UseThreatBuckets, true)          \
  X(use_cheaper_threats, UseCheaperThreats, true)        \
  X(use_capture_probe, UseCaptureProbe, false)

struct SearchSwitches {
#define FORK_SWITCH_MEMBER(member, option, value) bool member = value;
  FORK_SEARCH_SWITCHES(FORK_SWITCH_MEMBER)
#undef FORK_SWITCH_MEMBER
  // Tests only (no option): a TT entry cuts only at exactly the depth it was
  // searched to, so a search equals plain minimax (tests/test_search.cpp).
  bool tt_exact_depth = false;
};

struct SearchResult {
  Move best = NoMove;
  int score = 0;
  int depth = 0;  // last finished iteration (0 if none finished)
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
};

// Root moves are kept in search order: the initial capture order, then after
// every root search the move that last raised alpha moves to the front and
// the others keep their order (Fork's rule; the PV move is searched first).
struct RootEntry {
  Move move;
  std::uint64_t nodes = 0;  // nodes under this move in the current iteration's last pass
  int share = 0;            // its per mille of the last finished iteration's nodes
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
struct SearchCounters {
  std::uint64_t beta_cutoffs = 0;        // main-search nodes that failed high
  std::uint64_t first_move_cutoffs = 0;  // ... on the first move searched
  std::uint64_t cutoff_index_sum = 0;    // sum of the cutoff move's index (0 = first)
  std::uint64_t makes = 0;               // moves made in the main and quiescence searches
  // Deliverable 6: nodes cut by RFP and the null move; moves pruned by LMP,
  // futility and SEE; LMR's reduced searches and their full-depth re-searches.
  std::uint64_t rfp_cuts = 0;
  std::uint64_t null_cuts = 0;
  std::uint64_t lmp_prunes = 0;
  std::uint64_t futility_prunes = 0;
  std::uint64_t see_prunes = 0;
  std::uint64_t lmr_searches = 0;
  std::uint64_t lmr_researches = 0;
  std::uint64_t lmr_plies_sum = 0;  // plies taken off by reductions (the loop's mean-reduction descriptor)
  // The heuristic-discovery rule (lmr_correction, idea 23): the LMR sites it
  // ran at, those where it returned non-zero, and those where that changed
  // the reduction after scaling and clamping (the loop's trigger rate).
  std::uint64_t lmr_rule_sites = 0;
  std::uint64_t lmr_rule_fires = 0;
  std::uint64_t lmr_rule_changes = 0;
  // Quiet cutoffs at non-PV nodes out of check, by remaining depth (1-6) and
  // the cutting move's index among the quiets searched there (the late move
  // pruning measurement, DESIGN.md §5.2 deliverable 6).
  static constexpr int CutoffDepths = 7;
  static constexpr int CutoffIndices = 48;
  std::uint64_t quiet_cutoff_index[CutoffDepths][CutoffIndices] = {};
  // External review (2026-10-26). (c) SEE tests by the main-search SEE
  // pruning, by where the move came from; bad captures reached after late
  // move pruning stopped the quiets, and how many SEE pruning then drops.
  std::uint64_t see_tests_good_captures =
      0;  // SEE >= 0 already shown by the selector: skipped since claim (c)
  std::uint64_t see_tests_bad_captures = 0;  // SEE < 0 already shown by the selector
  std::uint64_t see_tests_quiets = 0;
  std::uint64_t see_tests_other = 0;  // TT moves and in-check evasions
  std::uint64_t bad_captures_after_stop = 0;
  std::uint64_t bad_captures_after_stop_pruned = 0;
  // (d) Futile nodes: quiet moves taken from the selector there, and those
  // searched (the checking ones and the first move).
  std::uint64_t futile_nodes = 0;
  std::uint64_t futile_quiets_taken = 0;
  std::uint64_t futile_quiets_searched = 0;
  // (f) Quiescence nodes at PV and non-PV nodes.
  std::uint64_t quiesce_nodes_pv = 0;
  std::uint64_t quiesce_nodes_non_pv = 0;
  // Tier 2: nodes where a singular test could run (the measurement's sampling).
  std::uint64_t singular_candidates = 0;
  std::uint64_t singular_tests = 0;       // singular tests run (their searches)
  std::uint64_t singular_extended = 0;    // ... that found the TT move singular
  std::uint64_t multi_cut_cuts = 0;       // ... where another move also beat beta: the node failed high
  std::uint64_t negative_extensions = 0;  // ... where the TT move was searched one ply shallower
  std::uint64_t no_move_reductions = 0;   // nodes without a TT move searched one ply shallower (T26)
  std::uint64_t capture_probes = 0;       // captures the capture probe searched (T31)
  std::uint64_t capture_probe_cuts = 0;   // ... nodes it made fail high
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
#endif

  // Forgets the move-ordering history (ucinewgame, and each bench position).
  void clear_history() {
    history_.clear();
    for (PairHistory& table : pair_history_) table.clear();
    take_history_.clear();
  }

  // Tests only: the root move that failed high in the iteration the last
  // deliberate() stopped in and was not yet re-searched to an exact score
  // (NoMove if none).
  Move unresolved_fail_high() const { return unresolved_fail_high_; }

  // Tests only: one zero-window search of `pos` as a non-PV node (window
  // [beta - 1, beta]), with no time limit; returns its fail-soft score.
  int probe_zero_window(Position& pos, int beta, int depth, const std::atomic<bool>& stop);

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
  std::int64_t elapsed_ms() const;
  void record_cutoff(PlyFrame& f, Move m, int depth);
  // The follow table's arrival at frame `f`: the move that led to the ply
  // above, the side's own previous move (none at the root's children).
  int follow_arrival(const PlyFrame& f) const { return &f == frames_ ? NoArrival : (&f - 1)->arrival; }
  // Whether the side to move's static eval at `ply` is above its eval at its
  // previous turn (tier 2, T18): two plies back, or four when two plies back
  // was in check. False when there is nothing to compare (in check now, the
  // root's children, or check at both earlier turns): without evidence of a
  // rise the cautious margin applies.
  bool eval_rising(int ply) const;
  // The move selector's threat set from the switches (T56).
  ThreatSet threat_set() const {
    if (!switches.use_threat_buckets) return ThreatSet::Off;
    return switches.use_cheaper_threats ? ThreatSet::CheaperAttacker : ThreatSet::AnyAttack;
  }
  void update_pv(int ply, Move m);
  void report_iteration(int depth, int score, int bound, const PrincipalLine& pv);

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
  // LMR context inputs kept by the search (lmr_table.hpp): the root score's
  // last change between iterations, and the share of the current root move.
  int score_trend_ = 0;
  int branch_share_ = 0;
  // The last finished iteration's PV, and the first move of the last line
  // reported: a stop after a reported fail repeats the finished iteration,
  // so the last line before bestmove names the move played.
  PrincipalLine finished_pv_;
  Move last_reported_ = NoMove;
#ifdef FORK_SEARCH_STATS
  std::uint64_t singular_probe_ = 0;  // FORK_SINGULAR_PROBE: print every Nth singular candidate
#endif
#if defined(FORK_EVAL_NNUE)
  const NetFile* net_;
  FeatureStack features_;
#endif
};

}  // namespace forkeng
