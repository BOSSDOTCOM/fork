---
paths:
  - "src/**"
  - "tests/**"
  - "bench/**"
  - "fuzz/**"
  - "tools/**"
  - "CMakeLists.txt"
---
# Testing rules

- **Test data comes from primary sources, never memory.** Fetch the page or
  file, compare character by character, and cite the source in the test
  file. Large third-party suites are downloaded by CMake with a pinned
  SHA-256 into `.cache/` and not committed (see the perft_epd setup in
  CMakeLists.txt).
- **New behaviour needs a test that fails without it.** For a bug fix, write
  the failing test first and show it failing.
- **Oracles must be independent.** Compare against a slow obvious
  reimplementation, python-chess (tools/difftest), or published counts. Never
  compare a function with itself.
- **Check that a checker can fail.** Fault-inject once (as was done for
  difftest and the allocation counter) so a pass means something.
- **Bench:**
  - `fork bench` must match `tests/bench.ref` on every preset (the
    bench_parity test).
  - A change that alters search or move order updates bench.ref in the same
    commit, with the new count in the message.
- **Run before claiming done:**
  - `scripts/check.sh full` (the Stop hook and pre-commit run it too);
  - `scripts/build.sh` (all presets) before a phase sign-off;
  - slow suites (`ctest -L slow`) at sign-off.
- **Sanitizers:** clang-debug runs ASan+UBSan on Windows. GCC sanitizers,
  TSan, MSan and valgrind run on Linux.
- **Long jobs** (perft_epd_full, difftest, fuzzing) run one at a time, with
  their command and result recorded.
