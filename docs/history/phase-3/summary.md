# Phase 3 summary: search (2026-10-24 to 2026-10-28)

Spec: DESIGN.md §5.2 (approved 2026-10-24). Closed by the owner on
2026-10-28 (tag `phase-3`) without tier 2, which moves into Phase 4.
Reports: milestone-a.md, milestone-b.md, milestone-c.md, audit-1.md; every
SPRT in sprt-log.md, every speed measurement in perf-log.md.

## What was built

- **Milestone A** (deliverables 1-4): the bootstrap evaluation; fail-soft
  PVS with iterative deepening, aspiration windows, mate distance pruning
  and draw detection; the transposition table; the quiescence search with
  SEE; the search bench; tuning builds with every search switch as a UCI
  option.
- **Milestone B** (5-6): the staged move selector (TT move, MVV-LVA
  captures with lazy SEE, history-ordered quiets with a malus); reverse
  futility, null move, late move reductions and pruning, futility and SEE
  pruning, each behind a switch; Fork's own constants after the
  originality screen, with the "Search constants" table.
- **Milestone C** (7-8): Syzygy probing through vendored Fathom (WDL in
  the search, DTZ ranking at the root); time management in its final form
  (the increment fix, a danger-zone reserve, the iteration rule); the
  external reviews' fixes; the parameter table (8b); the heuristic-
  discovery harness and its validation run (8c, idea 23).
- **Audit-1**: ten auditors, one reconciled list, the owner's decisions,
  then fixes one commit at a time: robustness (out-of-memory paths, `go
  mate N`, Clear Hash, a SyzygyPath overflow, exact node limits), tests
  (new oracles, mutants killed, TSan), tooling (reproducible,
  self-checking SPRTs; the full CI matrix), speed (lazy pins, an early SEE
  settle), docs and originality records.
- **Infrastructure**: the SPRT script and its log; cloud SPRTs on 16
  GitHub-hosted shards (and an AWS spot script, not yet used); the CI
  matrix on every push and pull request (Linux and Windows presets,
  sanitizers, MSan, TSan, fuzz seeds, PGO, TCEC's four compilers, the slow
  suites), with main protected by it.

## Results

| Point | Bench (nodes, depth 13 from B) | Elo (gauntlet, CCRL Blitz anchors) |
|---|---|---|
| Milestone A (2026-10-25) | 7,533,640 | 1773 ± 32 |
| Milestone B (2026-10-26) | 16,540,472 | 2343 ± 23 |
| Milestone C (2026-10-27) | 17,309,921 | 2402.5 ± 23.3 |
| Phase 3 end, after audit-1 (2026-10-28) | 17,309,921 (signature 372dc2e2d8a88e4b) | 2411.5 ± 22.5 |

The Elo figures are rough placements at 10+0.1 on this machine, not CCRL
ratings (Milestone A on its own anchor set; B, C and the end on the
Milestone B anchors). Search speed at the end: 6.93 M nps median on
`fork bench` (WSL, clang 21, -march=native), +3.3% over Milestone C on the
same tree.

## What was learned

- **Most refinements are small at STC.** Three of the audit's SPRTs
  reached the 20,000-game cap undecided (B-1, B-2, B-3). What decides then has to be fixed in advance:
  the cap, keeping only passes, and a non-regression early-acceptance rule
  that reads the interval on the bounds' own scale (normalized Elo).
- **Untested changes cost strength.** RfpMargin 40, adopted without an
  SPRT on a measurement that bounded the margin only from below, scored
  22.5 points below Milestone C on the same 357 gauntlet games and was
  reverted. The rule since: untested changes never ship; a skipped or
  unfinished test shelves the change (one owner-approved exception,
  `UseTtEvalRefine`).
- **Model memory reproduces famous values.** The time-budget formula and
  RfpMargin 80 turned out to match Berserk's; constants are now screened
  against four engines (match / no match only) and justified from Fork's
  own reasoning or measurements.
- **Speed came from doing less work**: skipping futile quiets (+12.7%),
  computing pins only when read, settling SEE early. `take_next` is now
  the largest single cost (about 20% of the profile).
- **Paired comparisons are sharper.** Gauntlets with a fixed schedule and
  seed compare two builds game for game; the RfpMargin question was
  answered that way in about 75 minutes of games.
- **CI catches what local checks miss**: AVX-512 binaries on runners
  without it, a fuzz target broken by a lazy field, Windows-only
  toolchain issues.

## Carried forward

- **Phase 4**: tier 2 (deliverable 9), its SPRTs on the GitHub shards
  beside the local self-play data generation; one removal round over every
  search feature after the first network (the end-of-Phase-3 round folds
  into it), with the retune of eval-dependent margins (RfpMargin 40 is
  revisited there, idea 34); the training-data decisions copied from the
  KB into the spec; the multi-agent plan (recorded, not started); idea
  23's long run in late Phase 4; Quality control 7's open items at the
  phase end.
- **Phase 5**: deliverable 8 at long time controls, the time-budget
  constants' measurement, `go mate N` against an opponent-only clock.
- **Phase 6**: B-5's keep-deeper TT rule, the per-thread memory and TT
  policy seams (F-22 to F-24).
- **Phase 8**: the TCEC-readiness list (Hash at TCEC sizes, Fathom's
  `exit()` paths and lineage, no-BMI2 CPUs, prefetch at large Hash, 7-man
  probe cost, ponder timing, a load run with the forced-move stop).
- **Anchors**: Supernova 2.4 and K2 0.99 for the gauntlet's gap above
  WyldChess (the owner builds them).

## Phase-end checklist (2026-10-28)

| Item | Result |
|---|---|
| 1. Checks | The full CI matrix on audit-1's merge (PR #5, run 40773853691): all 24 jobs green, perft_epd_deep and perft_epd_full included (Linux presets with ASan/UBSan, TSan, MSan, fuzz seeds, PGO, the tuning build, the Windows toolchains with the gcc-debug suite and the GCC smoke loop, TCEC's four compilers). Fuzzing on main 80f725e under the plateau rule: fuzz_fen plateaued at 1,224 s (cov 757, 247.8 M execs, 0 crashes, +36 inputs); fuzz_moves plateaued at 1,208 s (cov 532, 13.3 M execs, 0 crashes, +20 inputs); fuzz_uci ran its full hour without plateauing (cov 2,636, still growing at 3,576 s, 337,118 execs, 0 crashes, +563 inputs). fuzz_moves' first attempt was killed when the shared machine ran low on memory and was rerun with 5 jobs. **Not run**: a local `scripts/build.sh` of every preset on Windows and in a clean Linux clone (CI builds every preset from a clean checkout on Linux; the Windows rebuild stays in Quality control 7). |
| 2. Tag | `phase-3` on main after the close-out PR's merge, with the bench in its message. |
| 3. Untracked reports | HANDOFF.md and REVIEW-audit-1.md moved to audit-1-brief.md and audit-1-findings.md (headers added, bodies unchanged, checked for personal data). |
| 4. Branches and worktrees | audit-1 and the close-out branch are deleted after their merges; worktrees left: the pre-commit hook's tree and ../fork-kb. |
| 5. Stale build folders | Removed: WSL `~/fork-perf` (perf and fuzz builds, worktrees), `~/fork-audit` (the audit's scratch clone), Ubuntu-22.04 `/root/fork-perf` (TCEC A/B builds). Kept: the preset builds, `~/fork-check`, `~/fork-sprt` (the SPRT build cache), `~/fork-games` (game records), `~/fork-tools`. |
| 6. Docs and KB | DESIGN.md (status, roadmap, testing policy, decisions), ideas.md (34-38), ORIGINALITY.md and the history files updated; main merged into kb. The 24 UNVERIFIED marks in DESIGN.md, ORIGINALITY.md and ideas.md were listed, none resolved: each is an outside fact waiting on research or a question to TCEC or the owner, with its note on how to settle it. |
| 7. Memory notes | Reviewed: the project status, identity (branches, tags, protected main, backups) and machine notes updated; a time-zone preference added. |
| 8. Re-validation | The end-of-Phase-3 removal round folds into Phase 4's re-validation (owner, 2026-10-28). |
| 9. Summary | This page. |
| 10. Next phase | Phase 4 starts in a fresh session, from this summary and DESIGN.md. |
