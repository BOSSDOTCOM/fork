// Test runner: `fork_tests <suite>` runs one suite, `fork_tests` runs all
// suites that are not slow-only.
#include <chrono>
#include <cstring>
#include <iostream>

#include "core/position.hpp"
#include "harness.hpp"

namespace fork::test {

namespace {
int failures = 0;
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

}  // namespace fork::test

int main(int argc, char** argv) {
  using namespace fork::test;
  fork::init();
  const char* only = argc > 1 ? argv[1] : nullptr;
  int ran = 0;
  for (const Case& c : registry()) {
    if (only ? std::strcmp(c.suite, only) != 0 : std::strcmp(c.suite, "perft_full") == 0) continue;
    int before = failures;
    auto start = std::chrono::steady_clock::now();
    c.fn();
    double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    std::cout << (failures == before ? "ok   " : "FAIL ") << c.suite << '/' << c.name << " (" << secs
              << " s)\n";
    ++ran;
  }
  if (ran == 0) {
    std::cerr << "no test cases matched '" << (only ? only : "") << "'\n";
    return 2;
  }
  std::cout << ran << " cases, " << failures << " failures\n";
  return failures ? 1 : 0;
}
