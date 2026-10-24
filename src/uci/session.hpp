// session: the UCI protocol loop and its threads of control.
//
// Purpose: read commands, keep the game position and options, run searches
// and report them (DESIGN.md §5.1).
// Invariants:
// - Commands are handled one at a time on the input thread (the caller of
//   run() or handle_line()), which a search never blocks: isready, stop,
//   ponderhit and quit are answered while a search runs.
// - A search runs on its own thread, on its own copy of the position. Every
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

#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

#include "core/position.hpp"
#include "uci/go_limits.hpp"
#include "uci/output.hpp"
#include "uci/tokens.hpp"

namespace forkeng {

// The engine's version string, "<semver>-dev+<short commit>" (DESIGN.md §5.1).
const char* engine_version();

// Limits on what a session may do, for the fuzz target: the defaults are the
// real engine's.
struct SessionConfig {
  bool allow_heavy_commands = true;  // `bench` and `go perft`
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
  void cmd_position(const std::vector<LineToken>& tokens, std::size_t first);
  void cmd_go(const std::vector<LineToken>& tokens, std::size_t first);
  void cmd_perft(const std::vector<LineToken>& tokens, std::size_t first);
  void cmd_bench();
  void cmd_board();
  void cmd_ponderhit();

  void stop_search();  // stops and joins the running search, if any
  bool search_running();
  void search_main(Position pos, GoLimits limits);  // the search thread
  void report_search(const Position& pos, Move best, std::uint64_t nodes, std::int64_t elapsed_ms);

  OutputChannel& out_;
  SessionConfig config_;
  Position root_;
  SearchSignals signals_;
  std::thread search_thread_;
};

}  // namespace forkeng
