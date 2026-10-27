// Test runner: `fork_tests <suite>` runs one suite, `fork_tests` runs all
// suites that are not slow-only.
#include <chrono>
#include <cstring>
#include <iostream>

#include "core/position.hpp"
#include "harness.hpp"

namespace forkeng::test {

namespace {
int failures = 0;
int skipped = 0;
std::string skip_reason;  // the current case's, if it skipped
const Case* current = nullptr;
constexpr int MaxReported = 20;
}  // namespace

std::vector<Case>& registry() {
  static std::vector<Case> cases;
  return cases;
}

void record_failure(const char* file, int line, const std::string& what) {
  if (++failures <= MaxReported) std::cerr << file << ':' << line << ": FAILED " << what << '\n';
  if (failures == MaxReported) std::cerr << "(further failures not shown)\n";
}

void record_skip(const std::string& reason) { skip_reason = reason.empty() ? "no reason given" : reason; }

void record_note(const std::string& what) {
  std::cout << "NOTE " << (current ? current->suite : "?") << '/' << (current ? current->name : "?") << ": "
            << what << '\n';
}

}  // namespace forkeng::test

namespace {
// Suites run only when named explicitly (CTest label "slow").
bool is_slow(const char* suite) {
  for (const char* s : {"perft_full", "perft_epd_deep", "perft_epd_full"})
    if (std::strcmp(suite, s) == 0) return true;
  return false;
}
}  // namespace

int main(int argc, char** argv) {
  using namespace forkeng::test;
  forkeng::init();
  const char* only = argc > 1 ? argv[1] : nullptr;
  int ran = 0;
  for (const Case& c : registry()) {
    if (only ? std::strcmp(c.suite, only) != 0 : is_slow(c.suite)) continue;
    int before = failures;
    current = &c;
    skip_reason.clear();
    auto start = std::chrono::steady_clock::now();
    c.fn();
    double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    if (failures == before && !skip_reason.empty()) {
      ++skipped;
      std::cout << "SKIP " << c.suite << '/' << c.name << ": " << skip_reason << " (" << secs << " s)\n";
    } else {
      std::cout << (failures == before ? "ok   " : "FAIL ") << c.suite << '/' << c.name << " (" << secs
                << " s)\n";
    }
    ++ran;
  }
  if (ran == 0) {
    std::cerr << "no test cases matched '" << (only ? only : "") << "'\n";
    return 2;
  }
  std::cout << ran << " cases, " << failures << " failures";
  if (skipped) std::cout << ", " << skipped << " skipped";
  std::cout << '\n';
  // 77: nothing failed but something was skipped, which CTest shows as
  // "Skipped" (SKIP_RETURN_CODE in CMakeLists.txt), not as passed.
  return failures ? 1 : skipped ? 77 : 0;
}
