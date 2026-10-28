// session: the UCI protocol loop and its threads of control.
//
// Purpose: read commands, keep the game position and options, run searches
// and report them (DESIGN.md §5.1).
// Invariants:
// - Commands are handled one at a time on the input thread (the caller of
//   run() or handle_line()), which a search never blocks: isready, stop,
//   ponderhit and quit are answered while a search runs.
// - A search runs on its own thread, on its own copy of the position, with
//   the session's one Searcher (src/search/searcher.hpp). Every
//   `go` produces exactly one `bestmove`, printed by that thread after its
//   final `info` line.
// - At most one search exists. A command that changes what a search depends
//   on (position, ucinewgame, setoption, go, and the heavy Fork extensions)
//   first stops and joins the running search, as if `stop` had come first,
//   so its bestmove is printed before the command takes effect.
// - `go infinite` and `go ponder` searches never end by themselves: bestmove
//   waits for stop (or, for ponder, ponderhit and the normal limits).
// - quit, EOF on the input and destruction stop and join the search; no
//   thread outlives the session. No exception escapes handle_line().
#pragma once

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <mutex>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

#include "core/position.hpp"
#include "search/hash_memory.hpp"
#include "search/searcher.hpp"
#include "uci/go_limits.hpp"
#include "uci/options.hpp"
#include "uci/output.hpp"
#include "uci/tokens.hpp"

namespace forkeng {

// The engine's version string, "<semver>-dev+<short commit>" (DESIGN.md §5.1).
const char* engine_version();

// The search limits of a go: depth (clamped to [1, MaxPly - 1]), nodes (at
// least 1), mate (ignored unless positive, at most MaxPly) and searchmoves as
// sent, and, unless go infinite, the time budget (plan_time) from the clock
// and increment of `us`, the side to move, and the Move Overhead. A free
// function so that tests can check it with numbers (audit-1 Q-5).
SearchQuota quota_for_go(const GoLimits& go, Color us, std::int64_t move_overhead_ms);

// Limits on what a session may do, for the fuzz target: the defaults are the
// real engine's.
struct SessionConfig {
  bool allow_heavy_commands = true;  // `bench` and `go perft`
  bool allow_files = true;           // LogFile and the SyzygyPath scan
  std::int64_t default_hash_mb = 16;
  std::int64_t max_hash_mb = 4194304;  // 4 TiB (DESIGN.md §5.1)
  std::int64_t max_threads = 4096;
  // false: no thread is ever started. go is answered on the calling thread
  // at once (go infinite and go ponder too, as nothing could stop them) and
  // the Hash is cleared by the calling thread. For the fuzz target, which
  // exercises the command parsers in isolation.
  bool use_threads = true;
};

class UciSession {
 public:
  explicit UciSession(OutputChannel& out, SessionConfig config = {});
  ~UciSession();
  UciSession(const UciSession&) = delete;
  UciSession& operator=(const UciSession&) = delete;

  // Handles one input line (without its line terminator). Returns false
  // after `quit`.
  bool handle_line(std::string_view line);

  // Reads lines from `in` until `quit` or end of input, accepting LF, CRLF
  // and lone CR terminators. Returns the process exit status.
  int run(std::FILE* in);

 private:
  struct SearchSignals {
    std::mutex mutex;
    std::condition_variable wake;
    bool stop = false;     // stop: end the search now
    bool ponder = false;   // a ponder search not yet hit
    bool finished = true;  // the search thread has printed bestmove
  };

  void dispatch(const std::vector<LineToken>& tokens, std::size_t first, std::string_view line);
  void cmd_uci();
  void cmd_isready();
  void cmd_position(const std::vector<LineToken>& tokens, std::size_t first, std::string_view line);
  void cmd_go(const std::vector<LineToken>& tokens, std::size_t first);
  void cmd_perft(const std::vector<LineToken>& tokens, std::size_t first);
  void cmd_bench();
  void cmd_board();
  void cmd_ponderhit();
  void cmd_setoption(const std::vector<LineToken>& tokens, std::size_t first, std::string_view line);
  void cmd_ucinewgame();

  void declare_options();
  // Allocates or clears the hash as the options last asked. Runs only at
  // isready, ucinewgame and go, so every option sent before is in effect
  // (a GUI may send Hash before Threads). Returns true if it cleared the table.
  bool apply_pending();
  unsigned hash_workers() const;

  void stop_search();  // stops and joins the running search, if any
  bool search_running();
  void search_main(Position pos, SearchQuota limits, bool waits);  // the search thread
  // The last info line when no iteration was reported (none finished, or
  // no legal move), in a fixed buffer.
  void report_unfinished(const Position& pos, const SearchResult& r, std::int64_t elapsed_ms);
  // Answers a go when memory has run out (review 2026-10-24): fixed buffers,
  // `best` or, if not `known`, the first legal move.
  void answer_without_memory(const Position& pos, Move best, bool known) noexcept;

  OutputChannel& out_;
  SessionConfig config_;
  OptionTable options_;
  HashMemory hash_;
  TransTable tt_;             // a view over hash_, rebound whenever hash_ is resized
  bool hash_pending_ = true;  // the table is allocated at the first isready, ucinewgame or go
  bool clear_pending_ = false;
  // SyzygyPath: loaded at the next isready, ucinewgame or go, outside any
  // search (deliverable 7).
  std::string syzygy_path_;
  bool tables_pending_ = false;
  Position root_;
  // cmd_position builds the new position here, then swaps it with root_.
  // Both reserve GameStatePlies States at startup, so a move list of a long
  // game never allocates (audit-1 R-3).
  Position spare_;
  // The last position command failed even when tried again: no go searches
  // (the root may be the previous position, the other side to move) until a
  // position command succeeds (audit-1 R-3).
  bool position_unknown_ = false;
  bool go_answered_ = false;  // the go being handled has started its search or answered
  SearchSignals signals_;
  // The search reads these without the mutex: stop is set with signals_.stop
  // (stop_search), pondering is cleared by ponderhit.
  std::atomic<bool> stop_flag_{false};
  std::atomic<bool> pondering_{false};
  std::unique_ptr<Searcher> searcher_;  // created once, used by one search at a time
  std::thread search_thread_;
};

}  // namespace forkeng
