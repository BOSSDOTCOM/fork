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
- **Untested changes never ship** (owner, 2026-10-28; DESIGN.md §5.2,
  Testing setup): a behaviour change ships only after its SPRT's verdict,
  a speed claim only with the A/B harness, every change only with the full
  check. If the test is skipped or stopped before a verdict, the change is
  shelved (reverted or left off behind its switch), the baseline stays,
  and ideas.md logs it as untested with its partial data.
- **Run before claiming done:**
  - the full check: the CI matrix (`.github/workflows/ci.yml`) green on
    the pushed commit, or `scripts/check.sh full` on demand (pre-commit
    runs `check.sh quick` on the staged tree; the Stop hook runs
    `check.sh stop`);
  - `scripts/build.sh` (all presets) before a phase sign-off;
  - slow suites (`ctest -L slow`) at sign-off. CI runs perft_epd_full
    only when move generation's files change, plus nightly on main, so a
    sign-off cannot rely on a push having run it.
- **Sanitizers:** clang-debug runs ASan+UBSan on Windows. GCC sanitizers,
  TSan, MSan and valgrind run on Linux. TSan has its own presets,
  `clang-tsan` and `gcc-tsan` (Linux only; `FORK_TSAN=ON`, no
  `fork_alloc_test`), and must be clean on the UCI suites, which drive a
  TSan-built engine: run them with `TSAN_OPTIONS=halt_on_error=1` so a
  report kills the engine and fails the test.
- **no_alloc runs everywhere except TSan, MSan and valgrind.** The
  counting-allocator test (`fork_alloc_test`) replaces global operator
  new/delete. That collides with those tools' own replacements: a link
  error under TSan and MSan, and under valgrind the test's self-check fails
  ("counting operator new is not in effect") with a new/free mismatch
  report. Those runs exclude it (`-E no_alloc`, built without the
  `fork_alloc_test` target, or not run under valgrind), and those are its
  only sanctioned exclusions. The same applies to `uci_oom`
  (`fork_uci_oom_test`, which fails each allocation of a `go` in turn) and
  `uci_hash_oom` (`fork_uci_hash_oom_test`, which fails each allocation of a
  Hash resize in turn). Every other build runs it, the ASan/UBSan
  presets included, and
  `scripts/check.sh` fails if its Passed line is missing. (The PGO builds run
  bench parity only, no ctest.)
- **SPRT builds pin their target** (DESIGN.md §5.2 "Build target per
  machine"): GitHub's SPRT shards use x86-64-v3, set as `FORK_ARCH` in
  `.github/workflows/sprt.yml`, because hosted runners may lack AVX-512;
  AWS uses `aws_spot_sprt.sh --arch` (x86-64-v3 by default, x86-64-v4 for
  AVX-512); local SPRTs use update.sh's x86-64-v3. Never `native`.
  `tools/cloud/build_pair.sh` refuses to build without an explicit target.
- **Valgrind needs a non-AVX-512 build** (`FORK_ARCH=x86-64-v3`): it cannot
  decode AVX-512, which `-march=native` emits on the Ryzen 7600X3D.
- **Long jobs** (perft_epd_full, difftest, fuzzing) run one at a time, with
  their command and result recorded.
