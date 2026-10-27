// Minimal in-house test harness: named suites of cases, CHECK macros.
#pragma once

#include <cstdio>
#include <sstream>
#include <string>
#include <vector>

namespace forkeng::test {

struct Case {
  const char* suite;
  const char* name;
  void (*fn)();
};

std::vector<Case>& registry();
void record_failure(const char* file, int line, const std::string& what);
// The current case cannot test what it is for (a missing precondition, e.g.
// memory): it ends as SKIPPED, never as passed (owner, 2026-10-26).
void record_skip(const std::string& reason);
// Something worth seeing that is not a failure (e.g. a timing attempt that
// had to be retried); printed as a NOTE line, which scripts/check.sh reports.
void record_note(const std::string& what);

struct Registrar {
  Registrar(const char* suite, const char* name, void (*fn)()) { registry().push_back({suite, name, fn}); }
};

// True in optimized builds: deep perft depths run only there by default.
constexpr bool Optimized =
#ifdef NDEBUG
    true;
#else
    false;
#endif

}  // namespace forkeng::test

#define FORK_CAT2(a, b) a##b
#define FORK_CAT(a, b) FORK_CAT2(a, b)

#define TEST_CASE(suite, name)                                                                    \
  static void FORK_CAT(test_fn_, __LINE__)();                                                     \
  static ::forkeng::test::Registrar FORK_CAT(test_reg_, __LINE__)(suite, name,                    \
                                                                  &FORK_CAT(test_fn_, __LINE__)); \
  static void FORK_CAT(test_fn_, __LINE__)()

#define CHECK(cond)                                                          \
  do {                                                                       \
    if (!(cond)) ::forkeng::test::record_failure(__FILE__, __LINE__, #cond); \
  } while (0)

#define CHECK_EQ(a, b)                                                         \
  do {                                                                         \
    auto&& check_a_ = (a);                                                     \
    auto&& check_b_ = (b);                                                     \
    if (!(check_a_ == check_b_)) {                                             \
      std::ostringstream check_os_;                                            \
      check_os_ << #a " == " #b " (" << check_a_ << " vs " << check_b_ << ")"; \
      ::forkeng::test::record_failure(__FILE__, __LINE__, check_os_.str());    \
    }                                                                          \
  } while (0)

// Ends the current case as skipped, with the reason.
#define SKIP(msg)                                 \
  do {                                            \
    std::ostringstream skip_os_;                  \
    skip_os_ << msg;                              \
    ::forkeng::test::record_skip(skip_os_.str()); \
    return;                                       \
  } while (0)

// Logs a NOTE line without failing the case.
#define NOTE(msg)                                 \
  do {                                            \
    std::ostringstream note_os_;                  \
    note_os_ << msg;                              \
    ::forkeng::test::record_note(note_os_.str()); \
  } while (0)

// Like CHECK, but adds context (e.g. a FEN) to the failure message.
#define CHECK_MSG(cond, msg)                                                \
  do {                                                                      \
    if (!(cond)) {                                                          \
      std::ostringstream check_os_;                                         \
      check_os_ << #cond << " [" << msg << "]";                             \
      ::forkeng::test::record_failure(__FILE__, __LINE__, check_os_.str()); \
    }                                                                       \
  } while (0)
