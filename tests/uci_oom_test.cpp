// Review test (adversarial review of Phase 2, 2026-10-24): one failed heap allocation
// must not cost a game. The session's own comments promise that every `go`
// gets exactly one bestmove, "Out of memory while formatting: still answer
// the go, once" (session.cpp, search_main), and that a search thread that
// cannot start is answered on the input thread (cmd_go).
//
// Separate executable: replaces global operator new so that exactly the k-th
// allocation from now, on a chosen thread (the input thread or any other),
// throws std::bad_alloc; every later one succeeds. For each k it drives a
// fresh UciSession in process ("isready", "position startpos", "go depth 1",
// "stop", "isready", destruction) and checks the output written to a temporary file:
//   - exactly one bestmove line;
//   - in the start position (20 legal moves) that bestmove is a move, not
//     "(none)" (a GUI scores "bestmove (none)" with legal moves as a loss).
//
// Audit-1 R-3 (owner, 2026-10-28): a `position` command that runs out of
// memory is tried once more, and if that fails too, no go searches until a
// position command succeeds. Two paths, on the input thread:
//   - one failed allocation (each k in turn) in "position startpos moves
//     e2e4": the retry succeeds, and the go plays a legal move for Black
//     (before the fix the root stayed the start position, so the go played
//     White's move);
//   - every allocation of that line fails: the go answers "bestmove 0000"
//     with an info string error, and after a "position startpos" that
//     succeeds the next go plays a legal move again.
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <new>
#include <string>
#include <thread>
#include <vector>

#include "core/position.hpp"
#include "uci/output.hpp"
#include "uci/session.hpp"

namespace {

enum Target : std::uint8_t { Nobody = 0, InputThread = 1, OtherThreads = 2 };

std::atomic<int> target{Nobody};
std::atomic<long> countdown{0};
std::atomic<bool> fail_every{false};  // every allocation on the target thread fails
std::atomic<long> failed{0};
std::thread::id input_thread;

bool should_fail() {
  const int t = target.load(std::memory_order_relaxed);
  if (t == Nobody) return false;
  const bool on_input = std::this_thread::get_id() == input_thread;
  if ((t == InputThread) != on_input) return false;
  if (fail_every.load()) {
    failed.fetch_add(1);
    return true;
  }
  if (countdown.fetch_sub(1) != 1) return false;
  failed.fetch_add(1);
  return true;
}

}  // namespace

// GCC's -Wmismatched-new-delete (gcc-debug, -O1) takes these replacement
// operators' std::free for a mismatch; it pairs with the std::malloc below.
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC diagnostic ignored "-Wmismatched-new-delete"
#endif
void* operator new(std::size_t n) {
  if (should_fail()) throw std::bad_alloc();
  if (void* p = std::malloc(n ? n : 1)) return p;
  throw std::bad_alloc();
}
void* operator new[](std::size_t n) { return operator new(n); }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }

namespace {

std::vector<std::string> read_lines(std::FILE* f) {
  std::vector<std::string> lines;
  if (std::fseek(f, 0, SEEK_SET) != 0) return lines;
  std::string cur;
  for (int c; (c = std::fgetc(f)) != EOF;) {
    if (c == '\n') {
      if (!cur.empty() && cur.back() == '\r') cur.pop_back();
      lines.push_back(cur);
      cur.clear();
    } else {
      cur.push_back(static_cast<char>(c));
    }
  }
  return lines;
}

// Runs one session with the k-th allocation on `who` failing. Returns false
// on a violation and prints it.
bool run_once(Target who, long k, bool& injected) {
  std::FILE* f = std::tmpfile();
  if (!f) {
    std::printf("cannot create a temporary file\n");
    injected = true;
    return false;
  }
  {
    forkeng::SessionConfig config;
    config.allow_files = false;
    config.default_hash_mb = 1;
    forkeng::OutputChannel out(f);
    {
      forkeng::UciSession session(out, config);
      session.handle_line("isready");
      session.handle_line("position startpos");
      failed = 0;
      countdown = k;
      target = who;
      session.handle_line("go depth 1");
      if (who == InputThread) target = Nobody;  // only the go's own allocations
      session.handle_line("stop");              // joins the search thread: its bestmove is out
      target = Nobody;
      injected = failed.load() != 0;
      session.handle_line("isready");
    }
  }
  const std::vector<std::string> lines = read_lines(f);
  (void)std::fclose(f);
  int bestmoves = 0;
  std::string bestmove, error;
  for (const std::string& l : lines) {
    if (l.starts_with("bestmove")) {
      ++bestmoves;
      bestmove = l;
    }
    if (l.starts_with("info string error")) error = l;
  }
  const bool ok = bestmoves == 1 && bestmove != "bestmove (none)";
  if (!ok && injected)
    std::printf("FAIL: %s allocation #%ld fails: %d bestmove line(s)%s%s%s%s\n",
                who == InputThread ? "input-thread" : "search-thread", k, bestmoves,
                bestmove.empty() ? "" : ", last: '", bestmove.c_str(), bestmove.empty() ? "" : "'",
                error.empty() ? "" : (", engine said '" + error + "'").c_str());
  return ok || !injected;
}

// The bestmove lines and whether an info string error was printed.
struct Answer {
  std::vector<std::string> bestmoves;
  bool error = false;
};

Answer answers(const std::vector<std::string>& lines) {
  Answer a;
  for (const std::string& l : lines) {
    if (l.starts_with("bestmove")) a.bestmoves.push_back(l);
    if (l.starts_with("info string error")) a.error = true;
  }
  return a;
}

// R-3, one failed allocation: returns false on a violation.
bool position_retried(long k, bool& injected) {
  std::FILE* f = std::tmpfile();
  if (!f) {
    injected = true;
    return false;
  }
  {
    forkeng::SessionConfig config;
    config.allow_files = false;
    config.default_hash_mb = 1;
    forkeng::OutputChannel out(f);
    forkeng::UciSession session(out, config);
    session.handle_line("isready");
    session.handle_line("position startpos");
    failed = 0;
    countdown = k;
    target = InputThread;
    session.handle_line("position startpos moves e2e4");
    target = Nobody;
    injected = failed.load() != 0;
    session.handle_line("go depth 1");
    session.handle_line("stop");
  }
  const std::vector<std::string> lines = read_lines(f);
  (void)std::fclose(f);
  const Answer a = answers(lines);
  forkeng::Position after;
  after.make(after.parse_uci("e2e4"));
  const bool legal = a.bestmoves.size() == 1 && a.bestmoves[0].size() > 9 &&
                     !after.parse_uci(a.bestmoves[0].substr(9)).is_none();
  if (!legal && injected)
    std::printf(
        "FAIL: position allocation #%ld fails: %zu bestmove line(s), last '%s' (not Black's after e2e4)\n", k,
        a.bestmoves.size(), a.bestmoves.empty() ? "" : a.bestmoves.back().c_str());
  return legal || !injected;
}

// R-3, every allocation of the position line fails: returns false on a violation.
bool position_unknown() {
  std::FILE* f = std::tmpfile();
  if (!f) return false;
  std::vector<std::string> before_reset, after_reset;
  {
    forkeng::SessionConfig config;
    config.allow_files = false;
    config.default_hash_mb = 1;
    forkeng::OutputChannel out(f);
    forkeng::UciSession session(out, config);
    session.handle_line("isready");
    session.handle_line("position startpos");
    failed = 0;
    fail_every = true;
    target = InputThread;
    session.handle_line("position startpos moves e2e4");
    target = Nobody;
    fail_every = false;
    session.handle_line("go depth 1");
    session.handle_line("stop");
    session.handle_line("isready");
    std::fflush(f);
    before_reset = read_lines(f);
    session.handle_line("position startpos");
    session.handle_line("go depth 1");
    session.handle_line("stop");
  }
  after_reset = read_lines(f);
  (void)std::fclose(f);
  const Answer a = answers(before_reset);
  bool ok = failed.load() > 0 && a.bestmoves.size() == 1 && a.bestmoves[0] == "bestmove 0000" && a.error;
  if (!ok)
    std::printf("FAIL: position with every allocation failing: %zu bestmove line(s), last '%s', error %s\n",
                a.bestmoves.size(), a.bestmoves.empty() ? "" : a.bestmoves.back().c_str(),
                a.error ? "yes" : "no");
  const Answer b = answers(std::vector<std::string>(
      after_reset.begin() + static_cast<std::ptrdiff_t>(before_reset.size()), after_reset.end()));
  forkeng::Position start;
  const bool again = b.bestmoves.size() == 1 && b.bestmoves[0].size() > 9 &&
                     !start.parse_uci(b.bestmoves[0].substr(9)).is_none();
  if (!again)
    std::printf("FAIL: after a position that succeeded: %zu bestmove line(s), last '%s'\n",
                b.bestmoves.size(), b.bestmoves.empty() ? "" : b.bestmoves.back().c_str());
  return ok && again;
}

}  // namespace

int main() {
  forkeng::init();
  input_thread = std::this_thread::get_id();
  int failures = 0;
  for (Target who : {InputThread, OtherThreads}) {
    int injected_runs = 0;
    for (long k = 1; k <= 200; ++k) {
      bool injected = false;
      failures += !run_once(who, k, injected);
      if (!injected) break;  // k is past the last allocation of this `go`
      ++injected_runs;
    }
    std::printf("%s: %d allocations of `go depth 1` tried\n",
                who == InputThread ? "input thread" : "search thread", injected_runs);
  }
  {
    int injected_runs = 0;
    for (long k = 1; k <= 200; ++k) {
      bool injected = false;
      failures += !position_retried(k, injected);
      if (!injected) break;
      ++injected_runs;
    }
    std::printf("position, retried: %d allocations of `position startpos moves e2e4` tried\n", injected_runs);
    failures += !position_unknown();
    std::printf("position, every allocation failing: checked\n");
  }
  std::printf(failures ? "%d violations\n" : "no violations\n", failures);
  return failures ? 1 : 0;
}
