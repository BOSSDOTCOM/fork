# Phase 4, milestone 2: the pre-merge checklist (phase-4-m2 into main)

Prepared 2026-11-08 on branch phase-4-m2: phase-4 at feb7b9d, plus the
three tooling branches ci/speed (38e0251), tools/design-r (aee7cb0) and
measure/step1 (e0d586d), plus origin/main (0e7247b, milestone 1's README
and checklist from PRs #7, #8 and #9), plus this checklist and the README
update (owner's decision, 2026-11-08: one pull request, the full CI matrix,
merged on green). Every check below was run on that date unless it says
otherwise.

## 1. Every default-on search feature and its SPRT

main (milestone 1, PR #7) has 25 default-on switches and 4 off; this merge
adds 2, both on, and changes no other default
(docs/history/phase-4/sprt-log.md):

| Switch | Default | SPRT | Result |
|---|---|---|---|
| use_stability_time, use_share_time (time management (b), §5.6 step 10) | on | 2026-11-08 design R [0, 6], (b) against off: STC 8+0.08 (runs 42503358810, 42504937998), then LTC 40+0.4, Hash 64 (runs 42509883303, 42516750821, 42523612679) | STC H1, +18.69 ± 7.18 (3,200 games); LTC H1, +10.23 ± 5.14 (4,992 games) |

Variant (b) was chosen over (a), stability alone, by a head-to-head at STC
(runs 42488242225 and 42495448043: b − a +22.75 ± 12.04 nElo, 3,200 games).

The network: each new default net passed an SPRT ([0, 5], STC 8+0.08)
against the one before it (docs/nets.md):

- S512+PP against S512r2: +32.67 ± 10.48 (run 42294907752, 1,600 games),
  after +46.09 ± 10.37 at fixed nodes (run 42284077960);
- S512ppr2 against S512+PP: +20.11 ± 7.22 (runs 42335141916 and
  42336446490, 3,200 games);
- S512ppr3 against S512ppr2: +7.12 ± 4.53 (runs 42429984619 to
  42435511074, 8,000 games), after +15.65 ± 9.26 at fixed nodes (run
  42426868742).

The 9 default-on switches inherited from main without an SPRT pass of
their own (milestone 1's checklist, §1) are unchanged and still due for the
Phase 4 re-validation round (DESIGN.md §5.2, Quality control 6).

## 2. Experimental switches and builds are off

- Off by default, as at milestone 1: tt_age_blend, tt_keep_exact,
  use_tt_keep_deeper, use_negative_extension.
- `FORK_TUNE` OFF, `FORK_EXPERIMENT` empty (CMakeLists.txt); `update.sh`
  sets neither.
- Phase 4 step 1's instrumentation (measure/step1) is compiled only with
  `FORK_SEARCH_STATS`, which only the `clang-stats` preset sets; the default
  build's bench is unchanged by it (§4).
- No experiment branch is merged: tier2/batch3, tier2/batch4, the idea 59,
  60 and 61 branches and exp/oracle stay outside phase-4-m2.

## 3. The default network is in the repository

- `nets/s512ppr3.fnet` (1,426,656 bytes) is tracked and is CMake's default
  (`FORK_NET` nets/s512ppr3.fnet); `fork version` reports `net s512ppr3`.
- `fork netcheck tests/nnue/s512ppr3.parity`: 446 positions, 0 mismatches.
- The build needs no untracked file (CI builds from a clean clone).

## 4. Local checks and bench

On the merged tree (clang-release, Windows, LLVM-MinGW):

- `scripts/check.sh quick` through the pre-commit hook on every merge
  commit that touched code: ok.
- `ctest -LE slow`: 34 tests, 33 passed, 1 reported skipped by design (`eval`: three of its four cases check the
  bootstrap evaluation's own values and skip in the NNUE build; the fourth,
  colour symmetry, passed).
- Every tooling test (check.sh's tool tests, the `all` set: the Python
  suites with python-chess, the SPRT and head-to-head drivers against a
  fake gh, the cloud scripts): ok; 9 Python suites, 275 tests, plus the
  shell tests.
- The `clang-stats` build (the measurement instrumentation, not built in
  CI): built; search_stats and the bench parity tests, 3 of 3 passed.
- Bench: nodes 14,149,617, signature 1cb0717f040c294d, equal to
  tests/bench-s512ppr3.ref.
- The gauntlet's engine: run 42538371594 played phase-4 32c5517. Since then
  the engine's sources changed only by measure/step1's stats-only
  instrumentation, and the bench is the same, so the README's
  3488.2 ± 20.4 and the −222 gap to Stockfish 19 describe the engine merged
  here.

## 5. Before opening the pull request

- `bash scripts/scan-push.sh phase-4-m2`, passing, as its own step, then the
  push (the push gate).
- The pull request's CI runs the full matrix, including perft_epd_full and
  the full TSan suites (CMakeLists.txt changed since main).
- Branch protection: main requires every job by name today. The new
  workflow's one required check is "CI result"; the owner's rollout
  (2026-11-08) switches main's protection to it immediately after this
  merge, before any docs-only pull request.
