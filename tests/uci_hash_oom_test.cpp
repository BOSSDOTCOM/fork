// SPDX-License-Identifier: GPL-3.0-or-later

// Review test (adversarial review of Phase 3 deliverable 3, 2026-10-24):
// after a Hash resize whose report string cannot be allocated, the session's
// TransTable must not keep pointing at the freed table.
//
// HashMemory::resize frees the old table (release() when the new size does
// not fit, os_free when it does) and only then builds its report string,
// which may throw std::bad_alloc. UciSession::apply_pending rebound tt_ only
// after resize returned, and had already cleared hash_pending_, so the next
// `go` searched through a TransTable over unmapped memory (a crash, shown by
// this test before the fix: apply_pending now unbinds the table first and
// rebinds it on every way out).
//
// Separate executable (replaces global operator new): for k = 1, 2, ... the
// k-th allocation on this thread during "isready" (which applies a pending
// Hash of 4194304 MB, more than any machine has) throws; then "go depth 4"
// runs on the same thread (use_threads = false). A crash is a failure, and
// so is an isready without its readyok (audit-1, R-2).
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <new>
#include <string>

#include "core/position.hpp"
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
  forkeng::init();
  bool missing_readyok = false;
  for (long k = 1; k <= 60; ++k) {
    std::FILE* f = std::tmpfile();
    if (!f) return 2;
    {
      forkeng::SessionConfig config;
      config.allow_files = false;
      config.use_threads = false;
      config.default_hash_mb = 1;
      forkeng::OutputChannel out(f);
      forkeng::UciSession session(out, config);
      session.handle_line("isready");  // 1 MB table allocated, tt_ bound to it
      session.handle_line("setoption name Hash value 4194304");
      failed = 0;
      countdown = k;
      session.handle_line("isready");  // resize frees the 1 MB table; allocation #k throws
      countdown = 0;
      const bool injected = failed.load() != 0;
      if (!injected) {
        std::printf("k=%ld: no allocation failed; no crash for any k\n", k);
        std::fclose(f);
        return missing_readyok ? 1 : 0;
      }
      std::printf("k=%ld: allocation failed during isready; engine output so far:\n", k);
      std::fflush(f);
      std::rewind(f);
      // Each isready still gets its readyok (audit-1, R-2): a GUI that never
      // sees readyok waits until its timeout and forfeits the engine, so two
      // isready lines need two readyok lines.
      int readyoks = 0;
      std::string line;
      for (int c; (c = std::fgetc(f)) != EOF;) {
        std::putchar(c);
        if (c != '\n') {
          line += static_cast<char>(c);
          continue;
        }
        if (line == "readyok" || line == "readyok\r") ++readyoks;
        line.clear();
      }
      if (readyoks != 2) {
        std::printf("FAIL k=%ld: %d readyok lines for 2 isready commands\n", k, readyoks);
        missing_readyok = true;
      }
      std::printf("now go depth 4\n");
      std::fflush(stdout);
      session.handle_line("position startpos");
      session.handle_line("go depth 4");
    }
    std::fclose(f);
  }
  std::printf("no crash\n");
  return 0;
}
