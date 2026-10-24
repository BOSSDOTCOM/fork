<!--
Archived 2026-10-24 (phase-end checklist) from the untracked MORNING.md:
the overnight sign-off queue of 2026-10-23. Paths and commit hashes were
updated to the rewritten history; the logs it cites were not kept.
-->

# Overnight queue: results

Started 2026-10-23 20:47:38. Commit 0f00021. Jobs run one at a time,
in order; each section below is written when its job finishes. Logs:
`build/overnight/` (Windows) = `/mnt/c/Users/<user>/fork/build/overnight/` (WSL).

## 1. Release depth-6 perft (perft_epd_full, clang-release)

- **Result: PASS** (exit 0)
- Runtime: 0h 30m 10s (finished 2026-10-23 21:17:48)
- Log: `build/overnight/j1-release-perft-d6.log`
- MSan reports in log: 0
    perft-random: 6838 positions to depth <= 6, 4185882506133 nodes, 0 mismatches
    1/1 Test #11: perft_epd_full ...................   Passed  1806.32 sec
    The following tests passed:
    100% tests passed, 0 tests failed out of 1

## 2. MSan suite without perft_epd_full (libc++ MSan, origins off)

- **Result: PASS** (exit 0)
- Runtime: 0h 34m 21s (finished 2026-10-23 21:52:09)
- Log: `build/overnight/j2-msan-suite.log`
- MSan reports in log: 0
     1/11 Test  #1: magics ...........................   Passed    0.09 sec
     2/11 Test  #2: fen ..............................   Passed    0.05 sec
     3/11 Test  #3: zobrist_ep .......................   Passed    0.05 sec
     4/11 Test  #4: perft_suite ......................   Passed   39.32 sec
     5/11 Test  #5: perft_mirror .....................   Passed   19.34 sec
     6/11 Test  #6: consistency ......................   Passed  1231.38 sec
     7/11 Test  #7: pseudo_legal .....................   Passed    1.61 sec
     8/11 Test  #8: perft_edge .......................   Passed    0.07 sec
    perftsuite: 126 positions to depth <= 6, 4580923686 nodes, 0 mismatches
    perft-random: 6838 positions to depth <= 4, 4135458706 nodes, 0 mismatches
     9/11 Test  #9: perft_epd ........................   Passed   69.49 sec
    perft-random: 6838 positions to depth <= 5, 132117547121 nodes, 0 mismatches
    10/11 Test #10: perft_epd_deep ...................   Passed  697.78 sec
    11/11 Test #11: bench_parity .....................   Passed    1.63 sec
    The following tests passed:
    100% tests passed, 0 tests failed out of 11

## 3a. Fuzz fuzz_fen, 90 min

- **Result: PASS** (exit 0)
- Runtime: 1h 30m 14s (finished 2026-10-23 23:22:23)
- Log: `build/overnight/j3a-fuzz-fen.log`
- fuzz_fen.exe: 5413 s, 12 jobs, cov 684, ft 2279, execs 278,714,431, corpus 411 files, still growing at the time limit, coverage last grew at 5060 s, 0 crash artifacts
- Crash artifacts: 0 new in fuzz/artifacts/

## 3b. Fuzz fuzz_moves, 90 min

- **Result: PASS** (exit 0)
- Runtime: 1h 30m 15s (finished 2026-10-24 00:52:38)
- Log: `build/overnight/j3b-fuzz-moves.log`
- fuzz_moves.exe: 5415 s, 12 jobs, cov 548, ft 2737, execs 67,847,852, corpus 717 files, still growing at the time limit, coverage last grew at 1589 s, 0 crash artifacts
- Crash artifacts: 0 new in fuzz/artifacts/

## 4. MSan perft_epd_full (libc++ MSan, origins off)

- **Result: PASS** (exit 0)
- Runtime: 5h 51m 39s (finished 2026-10-24 06:44:17)
- Log: `build/overnight/j4-msan-perft-d6.log`
- MSan reports in log: 0
    perft-random: 6838 positions to depth <= 6, 4185882506133 nodes, 0 mismatches
    1/1 Test #11: perft_epd_full ...................   Passed  21094.22 sec
    The following tests passed:
    100% tests passed, 0 tests failed out of 1

Queue finished 2026-10-24 06:44:17.
