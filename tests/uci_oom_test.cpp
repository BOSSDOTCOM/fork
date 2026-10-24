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
std::atomic<long> failed{0};
std::thread::id input_thread;

bool should_fail() {
  const int t = target.load(std::memory_order_relaxed);
  if (t == Nobody) return false;
  const bool on_input = std::this_thread::get_id() == input_thread;
  if ((t == InputThread) != on_input) return false;
  if (countdown.fetch_sub(1) != 1) return false;
  failed.fetch_add(1);
  return true;
}

}  // namespace

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
  std::printf(failures ? "%d violations\n" : "no violations\n", failures);
  return failures ? 1 : 0;
}
