// SPDX-License-Identifier: GPL-3.0-or-later

// Review test (the correctness audit of 2026-11-16, area 1, L1): a Threads
// change whose pool resize runs out of memory must not crash the engine.
//
// HelperPool::resize grew its bookkeeping vectors (the kept helpers, the
// searcher list, the team) while helper threads already existed; a
// std::bad_alloc there destroyed a vector holding a joinable std::thread, and
// std::terminate ended the engine at isready or go.
//
// Separate executable (replaces global operator new): for k = 1, 2, ... the
// k-th allocation on any thread during "isready" (which applies a pending
// Threads 3, so two helpers are created) throws; then "go depth 3" runs, and
// the session is destroyed (which joins every thread). A crash is a failure,
// and so is an isready without its readyok or a go without its one bestmove.
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <new>
#include <string>

#include "uci/output.hpp"
#include "uci/session.hpp"

namespace {

std::atomic<long> countdown{0};
std::atomic<long> failed{0};

bool should_fail() {
  if (countdown.load() <= 0) return false;
  if (countdown.fetch_sub(1) != 1) return false;
  failed.fetch_add(1);
  return true;
}

}  // namespace

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

int main() {
  bool bad = false;
  for (long k = 1;; ++k) {
    std::FILE* f = std::tmpfile();
    if (!f) return 2;
    bool injected = false;
    {
      forkeng::SessionConfig config;
      config.allow_files = false;
      config.default_hash_mb = 1;
      forkeng::OutputChannel out(f);
      forkeng::UciSession session(out, config);
      session.handle_line("isready");  // the 1 MB table
      session.handle_line("setoption name Threads value 3");
      failed = 0;
      countdown = k;
      session.handle_line("isready");  // the pool grows to 2 helpers; allocation #k throws
      countdown = 0;
      injected = failed.load() != 0;
      session.handle_line("position startpos");
      session.handle_line("go depth 3");
      session.handle_line("isready");
    }  // destroyed: the search is stopped and joined, and so is every helper thread
    std::fflush(f);
    std::rewind(f);
    int readyoks = 0, bestmoves = 0;
    std::string line;
    for (int c; (c = std::fgetc(f)) != EOF;) {
      if (c != '\n') {
        line += static_cast<char>(c);
        continue;
      }
      if (line == "readyok" || line == "readyok\r") ++readyoks;
      if (line.rfind("bestmove", 0) == 0) ++bestmoves;
      line.clear();
    }
    std::fclose(f);
    if (readyoks != 3 || bestmoves != 1) {
      std::printf("FAIL k=%ld: %d readyok lines for 3 isready, %d bestmove lines for 1 go\n", k, readyoks,
                  bestmoves);
      bad = true;
    }
    if (!injected) {
      std::printf("k=%ld: no allocation failed; no crash for any k\n", k);
      break;
    }
  }
  std::printf("%s\n", bad ? "FAIL" : "no crash");
  return bad ? 1 : 0;
}
