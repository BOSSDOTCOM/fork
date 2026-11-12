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
  and ideas.md logs it as untested with its partial data. One
  owner-approved exception: `UseTtEvalRefine` stays on (DESIGN.md §5.2,
  Testing setup).
- **Early acceptance reads nElo** (owner, 2026-10-28): the SPRT bounds
  are normalized Elo, so the non-regression early-acceptance rule reads
  the "nElo: x +/- e" interval, never the logistic "Elo" one (DESIGN.md
  §5.2, Testing setup).
- **Offline re-measurement rules set retune ranges only** (owner,
  2026-11-12): a declared measurement rule (a label-and-sweep grid, a
  cutoff-rate or accuracy proxy) re-run on a new net or search only
  widens or sets the final retune's range for its constant. It never
  gates a test and never picks a value by itself; games (SPRT, SPSA,
  head-to-head) decide. Evidence: SingularMarginPerPly 22, T27's rule
  re-run on r8brft1, lost to 6 by −26.76 ± 9.93 Elo (design R STC,
  2026-11-12), and the staleness audit
  (docs/research/staleness-audit-2026-11-12.md) found that in every case
  where games or SPSA checked a rule's pick, the pick lost or the tuner
  moved away (DESIGN.md §5.2, Testing setup).
- **Run before claiming done:**
  - the full check: the CI matrix (`.github/workflows/ci.yml`) green on
    the pushed commit, or `scripts/check.sh full` on demand (pre-commit
    runs `check.sh quick` on the staged tree; the Stop hook runs
    `check.sh stop`);
  - `scripts/build.sh` (all presets) before a phase sign-off;
  - slow suites (`ctest -L slow`) and the full TSan suites at sign-off.
    CI runs perft_epd_full only when move generation's files change, and
    the full TSan suites (`.github/workflows/tsan.yml`) only when threads,
    the TT or the UCI layer change (`.github/ci/changed-areas.sh`), plus
    both nightly on main, so a sign-off cannot rely on a push having run
    them.
- **Sanitizers:** clang-debug runs ASan+UBSan on Windows. GCC sanitizers,
  TSan, MSan and valgrind run on Linux. TSan has its own presets,
  `clang-tsan` and `gcc-tsan` (Linux only; `FORK_TSAN=ON`, no
  `fork_alloc_test`), and must be clean on the UCI suites, which drive a
  TSan-built engine: run them with `TSAN_OPTIONS=halt_on_error=1` so a
  report kills the engine and fails the test. CI runs TSan in two sizes
  (owner, 2026-11-07): the job "TSan, threaded suites" (uci_protocol,
  uci_options, uci_timing, tt, datagen, web; both TSan presets, no bench
  parity) on every code change, and the full fast suite with bench parity
  (tsan.yml) when threads, the TT or the UCI layer change, nightly on
  main, and on demand (dispatch tsan.yml, or ci.yml with `force-tsan`). A
  new suite that starts threads joins the threaded list in ci.yml's
  tsan-threaded job (it checks that all of them exist).
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
  AWS uses `aws_spot_sprt.sh --arch`, kept at x86-64-v3 until Phase 4
  (owner, 2026-10-28; x86-64-v4 exists for AVX-512); local SPRTs use
  update.sh's x86-64-v3. Never `native`.
  `tools/cloud/build_pair.sh` refuses to build without an explicit target.
- **Valgrind needs a non-AVX-512 build** (`FORK_ARCH=x86-64-v3`): it cannot
  decode AVX-512, which `-march=native` emits on the Ryzen 7600X3D.
- **Long jobs** (perft_epd_full, difftest, fuzzing) run one at a time, with
  their command and result recorded.
