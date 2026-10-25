// searcher: the alpha-beta search (DESIGN.md §5.2, deliverables 2-6).
//
// Purpose: iterative deepening with aspiration windows over a fail-soft
// principal variation search (negamax), with draw detection, mate distance
// pruning and a transposition table, ending in a quiescence search over
// captures and queen promotions (all evasions in check).
// Invariants:
// - One Searcher per search thread; it owns all per-thread state (the search
//   stack, PVs, root moves) and is created once, outside any search: explore()
//   never allocates (tests/alloc_test.cpp).
// - Scores follow score_bounds.hpp: fail-soft, from the side to move's view,
//   mates by distance from the root.
// - explore() is deterministic for a given position, limits, switches, TT
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

struct SearchLimits {
  int depth = MaxPly - 1;     // iterations to finish at most
  std::uint64_t nodes = 0;    // 0: no node limit
  int mate_moves = 0;         // > 0: stop once a mate in at most this many moves is found
  std::int64_t soft_ms = -1;  // -1: none; checked between iterations
  std::int64_t hard_ms = -1;  // -1: none; polled during the search
  MoveList restrict_to;       // searchmoves; empty: every legal move
  // When `go` arrived: the time limits count from here, so work done before
  // the search starts (a Hash change applied at go) uses the move's time.
  // Default: when explore() starts.
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
  MoveList moves;         // scratch: root moves, the 50-move mate check
  MoveList quiets_tried;  // quiet moves searched here without a cutoff (the malus)
  int static_eval;        // ScoreNone in check
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
};

class Searcher {
 public:
  explicit Searcher(TransTable& tt) : tt_(tt) {}

  // Searches `pos` (restored on return) until a limit is reached or `stop`
  // becomes true. While `pondering` is true, time limits do not apply.
  SearchResult explore(Position& pos, const SearchLimits& limits, const std::atomic<bool>& stop,
                       const std::atomic<bool>* pondering, SearchListener* listener);

  SearchSwitches switches;
#ifdef FORK_SEARCH_STATS
  SearchCounters counters;
#endif

  // Forgets the move-ordering history (ucinewgame, and each bench position).
  void clear_history() { history_.clear(); }

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
  const SearchLimits* limits_ = nullptr;
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
  std::size_t root_count_ = 0;
  // The best root move found in the running iteration with an exact score,
  // and its PV (reported if a stop makes it the move played).
  Move iteration_best_ = NoMove;
  int iteration_best_score_ = -ScoreInfinite;
  PrincipalLine iteration_pv_;
};

}  // namespace forkeng
