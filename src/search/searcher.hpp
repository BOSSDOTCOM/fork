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
//   listener is called once per finished iteration only.
// - Every technique has a switch in SearchSwitches, so one binary can test
//   it on and off; release defaults are the techniques adopted by SPRT.
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

// Technique switches (DESIGN.md §5.2: every technique sits behind a flag).
struct SearchSwitches {
  bool use_tt = true;
  bool use_pvs = true;
  bool use_aspiration = true;
  bool use_mate_distance = true;
  bool use_quiesce = true;
  bool use_see_quiesce = true;    // qsearch skips captures that lose material by SEE
  bool use_history = true;        // quiet moves ordered by butterfly history (else generation order)
  bool use_history_malus = true;  // quiets tried before a cutoff lose what the cutoff move gains
  // Tier 1 pruning and reductions (deliverable 6).
  bool use_rfp = true;        // reverse futility pruning (T20)
  bool use_nmp = true;        // null move pruning (T13)
  bool use_lmr = true;        // late move reductions (T15)
  bool use_lmp = true;        // late move pruning (T21)
  bool use_futility = true;   // futility pruning (T22)
  bool use_see_prune = true;  // SEE pruning in the main search (T23)
  // TT victims ranked by depth minus two plies per search of age instead of
  // current-search-first (owner's experiment, 2026-10-26; off by default).
  bool tt_age_blend = false;
  // Tests only: a TT entry cuts only at exactly the depth it was searched
  // to, so a search equals plain minimax (tests/test_search.cpp).
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
  MoveList moves;           // scratch: root moves, the 50-move mate check
  MoveList failed_quiets;   // quiet moves searched here without a cutoff (the malus)
  int static_eval;          // ScoreNone in check
  bool after_null = false;  // this node was reached by a null move (no second one in a row)
};

// Root moves are kept in search order: the initial capture order, then after
// every root search the move that last raised alpha moves to the front and
// the others keep their order (Fork's rule; the PV move is searched first).
struct RootEntry {
  Move move;
};

// Debug counters (DESIGN.md §5.2), compiled in only with the CMake option
// FORK_SEARCH_STATS: they show whether ordering and pruning behave as
// intended, which an Elo test cannot. Normal builds have none.
struct SearchCounters {
  std::uint64_t beta_cutoffs = 0;        // main-search nodes that failed high
  std::uint64_t first_move_cutoffs = 0;  // ... on the first move searched
  std::uint64_t cutoff_index_sum = 0;    // sum of the cutoff move's index (0 = first)
  std::uint64_t makes = 0;               // moves made in the main and quiescence searches
  std::uint64_t gives_check_calls = 0;   // gives_check calls by the pruning (ideas.md idea 9)
  // Deliverable 6: nodes cut by RFP and the null move; moves pruned by LMP,
  // futility and SEE; LMR's reduced searches and their full-depth re-searches.
  std::uint64_t rfp_cuts = 0;
  std::uint64_t null_cuts = 0;
  std::uint64_t lmp_prunes = 0;
  std::uint64_t futility_prunes = 0;
  std::uint64_t see_prunes = 0;
  std::uint64_t lmr_searches = 0;
  std::uint64_t lmr_researches = 0;
  // Quiet cutoffs at non-PV nodes out of check, by remaining depth (1-6) and
  // the cutting move's index among the quiets searched there (the late move
  // pruning measurement, DESIGN.md §5.2 deliverable 6).
  static constexpr int CutoffDepths = 7;
  static constexpr int CutoffIndices = 48;
  std::uint64_t quiet_cutoff_index[CutoffDepths][CutoffIndices] = {};
  // External review (2026-10-26). (c) SEE tests by the main-search SEE
  // pruning, by where the move came from; bad captures reached after late
  // move pruning stopped the quiets, and how many SEE pruning then drops.
  std::uint64_t see_tests_good_captures = 0;  // SEE >= 0 already shown by the selector
  std::uint64_t see_tests_bad_captures = 0;   // SEE < 0 already shown by the selector
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
};

class Searcher {
 public:
  explicit Searcher(TransTable& tt) : tt_(tt) {}

  // Searches `pos` (restored on return) until a limit is reached or `stop`
  // becomes true. While `pondering` is true, time limits do not apply.
  SearchResult deliberate(Position& pos, const SearchQuota& limits, const std::atomic<bool>& stop,
                          const std::atomic<bool>* pondering, SearchListener* listener);

  SearchSwitches switches;
#ifdef FORK_SEARCH_STATS
  SearchCounters counters;
#endif

  // Forgets the move-ordering history (ucinewgame, and each bench position).
  void clear_history() { history_.clear(); }

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

  bool poll_limits();  // true once the search must stop
  std::int64_t elapsed_ms() const;
  void record_cutoff(const PlyFrame& f, Move m, int depth);
  void update_pv(int ply, Move m);
  void report_iteration(int depth, int score, int bound, const PrincipalLine& pv);

  TransTable& tt_;
  QuietHistory history_;
  Position* pos_ = nullptr;
  const SearchQuota* limits_ = nullptr;
  const std::atomic<bool>* stop_ = nullptr;
  const std::atomic<bool>* pondering_ = nullptr;
  SearchListener* listener_ = nullptr;
  std::chrono::steady_clock::time_point start_;
  std::uint64_t nodes_ = 0;
  int max_ply_reached_ = 0;
  bool stopped_ = false;

  PlyFrame frames_[MaxPly + 1];
  PrincipalLine pv_[MaxPly + 1];
  RootEntry root_moves_[MaxMoves];
  // The iteration's root move that failed high and is not yet resolved by a
  // re-search, with its lower bound and line (review claim (a), 2026-10-26).
  Move root_fail_high_ = NoMove;
  int root_fail_high_score_ = 0;
  PrincipalLine root_fail_high_pv_;
  Move unresolved_fail_high_ = NoMove;
  std::size_t root_count_ = 0;
  // The best root move found in the running iteration with an exact score,
  // and its PV (reported if a stop makes it the move played).
  Move iteration_best_ = NoMove;
  int iteration_best_score_ = -ScoreInfinite;
  PrincipalLine iteration_pv_;
};

}  // namespace forkeng
