# Audit-1: the full engine audit (2026-10-27 to 2026-10-28)

The owner's audit of Fork after Milestone C and before idea 23 and tier 2,
on branch `audit-1` from main 6b04ed5. Phase A: ten auditors in parallel
(A1-A10: search correctness, performance, robustness, TCEC and
originality, tests, tooling, docs, behaviour proposals, refactoring, and
a re-check of every earlier review's items), subagents that never opened
another engine's source. Phase B: one
reconciled list, approved by the owner with answers to its questions.
Phase C: fixes and improvements, one commit each, every behaviour change
by SPRT on the GitHub shards. Phase D: the performance gate against main
and a gauntlet against the Milestone C anchors.

## Result

- **Strength: unchanged, as intended.** The search is identical to
  main's at fixed depth (bench 17,309,921 / 372dc2e2d8a88e4b, the same as
  main's). Every behaviour proposal that did not pass its SPRT was
  reverted. Gauntlet: **Fork 2411.5 ± 22.5** on the Milestone B anchors,
  against Milestone C's 2402.5 ± 23.3.
- **Speed: +3.3%** search nps against main on the same tree (significant
  at the 3.0% noise threshold).
- **Robustness:** out-of-memory paths in `isready` and `position`, `go
  mate N`, Clear Hash beside a Hash change, a SyzygyPath overflow in
  Fathom, exact node limits, decoupled PVS/LMR switches.
- **Tests:** new oracles and mutants killed (soft limit, fifty-move clock,
  UCI transcript replay, zero windows, mate bands, TT bounds, 3-4-5
  tables, `go` arithmetic), TSan run.
- **Tooling and CI:** the full CI matrix on GitHub (Linux presets,
  sanitizers, MSan, TSan, fuzz seeds, PGO, Windows toolchains, TCEC's four
  compilers, slow suites); SPRT tooling made reproducible and
  self-checking; the cloud SPRT shards pinned to x86-64-v3.
- **Docs and originality:** stale passages fixed, constants justified,
  an SPDX line in every source file, ORIGINALITY completed; name and
  constant screens through throwaway clones, match or no match only.

## Behaviour changes (SPRTs on the GitHub shards)

| Change | Bounds | Result | Outcome |
|---|---|---|---|
| B-1: stop a forced move early (one root move, timed search) | [-3, 0] | +0.96 ± 3.54 after 22,400 games, interval [-2.58, +4.50] | **kept** (owner; interval above -3) |
| B-2: a settling table result stored at full depth | [-3, 0] | -0.92 ± 3.58 at the cap, interval never above -3 | reverted (8e87028) |
| B-3: re-search a root fail high one ply shallower | [0, 3] | +0.65 ± 3.56 at the cap | reverted (bc44071) |
| B-4: quiescence stand-pat refined by the TT score | [0, 3] | -4.11 ± 3.93, H0 accepted at 19,200 games | reverted (1e16853) |
| B-5: keep a stale TT entry still deeper once aged | [0, 3], 40+0.4 | -5.07 ± 10.08 at 2,604 games, stopped | off by default, deferred to Phase 6 (idea 30) |
| RfpMargin 40 (was 80) | [0, 3] | no SPRT: accepted by the owner, then the gauntlet below | reverted to 80 (fd7d4b5), untested (idea 34) |

Details and every run's data: sprt-log.md. The RfpMargin episode set a
standing rule (owner, 2026-10-28; DESIGN.md §5.2, Testing setup):
**untested changes never ship**; a skipped or unfinished test shelves the
change and keeps the baseline.

## Phase D

### Performance gate (perf-log.md)

`tools/perf_gate.sh` in WSL, clang 21.1.8, -march=native, LTO, the A/B
harness with identity checks:

| Comparison | Bench | Median nps | Verdict |
|---|---|---|---|
| audit head with RfpMargin 40 (72148a8) vs main 6b04ed5, 6 rounds | different trees | 6,750,883 -> 6,943,739 (+2.9%) | no slowdown (threshold 3.0%) |
| 8550a78 (audit-1, RfpMargin 80) vs main, 10 rounds | identical | 6,707,903 -> 6,928,647 (+3.3%) | faster (threshold 3.0%) |

8550a78's code is the final audit-1 code. The gain comes from P-2 (pins
and discovered-check candidates computed on first read), P-3 (an early
settle in `see_at_least`) and the cleanups; `refresh_check_info`, 7.7% of
the profile at Milestone C, left the top 15.

### Gauntlet against the Milestone C anchors

Milestone C's settings throughout: update.sh's TCEC build (clang 21.1.8,
x86-64-v3, LTO), the same 200 random 8-ply openings (SHA-256 checked),
`tools/elo_gauntlet.sh` with anchor set c, 200 games per anchor at
10+0.1, concurrency 10, the same seed and schedule; Ordo with the anchors
fixed at their CCRL Blitz ratings. The headline uses the 1,000 games
without Weiss 1.0, as Milestone C's did (the filter reproduces Milestone
C's 2402.5 ± 23.3 exactly from its own games). The schedule is
deterministic, so each game has a counterpart in Milestone C's run.

**RfpMargin 80 (8550a78), all 1,200 games: Fork 2411.5 ± 22.5** (2416.0 ±
22.2 with Weiss as a sixth anchor; Milestone C: 2402.5 ± 23.3 and 2409.5 ±
22.9).

| Anchor | CCRL Blitz | Fork's score (W / D / L) | Milestone C, same games |
|---|---|---|---|
| Belette 2.0.0 | 2115 | 146.0 / 200 (73%; 136 / 20 / 44) | 142.5 |
| Stash 15.3 | 2173 | 145.0 / 200 (73%; 134 / 22 / 44) | 145.0 |
| Chal 1.3.0 | 2285 | 146.5 / 200 (73%; 128 / 37 / 35) | 131.0 |
| Stash 19.0 | 2473 | 92.0 / 200 (46%; 82 / 20 / 98) | 97.5 |
| WyldChess 1.51 | 2603 | 57.5 / 200 (29%; 43 / 29 / 128) | 61.5 |
| Weiss 1.0 | 2896 | 19.5 / 200 (10%; 18 / 3 / 179) | 23.0 |

Fork's median search depth was 17 plies (Milestone C: 17), at 0.19-0.22 s
per move. Three time losses, all by anchors in games Fork won (Stash 15.3
twice, Stash 19.0 once); Fork lost none on time, and nothing crashed or
disconnected.

**RfpMargin 40 (72148a8), stopped after 357 games** (the owner's decision,
to run RfpMargin 80 instead): 156.0 points against Milestone C's 178.5 on
the same 357 games (43.7% vs 50.0%, about -44 Elo, roughly two standard
errors), lower against five anchors and level against Weiss. Unfavourable
but not conclusive; RfpMargin is the only fixed-depth difference between
the two builds.

## The reconciled list: what was done

- **Bugs:** all fixed, most with a test shown failing first: the tooling
  bugs (U-1..U-18, T-1), the UCI and robustness bugs (R-1..R-4, V-2),
  the switch coupling (A9-2), the test gaps (Q-1..Q-12, V-4), the docs and
  originality items (the D- and T- items and A4b's constant matches; D-20,
  the `d8/final` tag text, recorded in the decisions log rather than
  rewritten, since the owner allows no force push), A1 suspicions 8 and 9. Partly done: Q-7 and Q-8 (mutants M13 and M16
  survive: no reachable position was found for either), V-5 (only the
  PlyFrame size assert; the optional stats-build assertions were not
  added), P-1 (fixed with `always_inline` rather than lazy facts; no
  objdump check in the evolve gate).
- **Refactors (bench identical):** F-1..F-8, F-10..F-12, F-25. F-8 and
  F-10 in reduced form (the TT flag bits stay literals, since the proposed
  name matched another engine's; a guard test instead of a shared FEN
  header). **F-9 skipped** (owner: cold code, new names for little gain;
  the UCI transcript replay checks both printers).
- **Speed:** P-2 and P-3 adopted; P-6's inlining measured, no gain, not
  adopted (only `lto on/off` in `fork version`).
- **Cleanup:** dead members and the never-pruning futility branch removed,
  stale baselines and scripts removed, merged branches deleted after
  archive tags, worktrees removed.

## Open items carried forward

Deferred with a target (recorded in DESIGN.md, ideas.md or the phase
notes):
- **Tier 2, before its first history table:** F-13 (one make/unmake
  wrapper per ply recording move, piece and destination), F-14 (one
  gravity function, one history family with one `clear()`, a 12-slot piece
  index; beware int16 selector overflow once four or more tables are
  summed), F-15 (split `negamax` into always-inline steps), F-16 (name the
  eval ladder), F-17/F-18 (singular-search notes: the excluded-move search
  reuses the ply frame, `moves_seen == 0` would report false mates, an
  `excluded` field is needed), F-20 (pawn and non-pawn keys); the
  near-term TT/fifty-move two-path test (suspicion 1a); ideas 31-33
  (measure first).
- **Phase 4:** F-21 (accumulator placement); the retune of eval-dependent
  margins, where RfpMargin 40 is revisited with an SPRT (idea 34); the
  multi-agent plan (recorded, not started).
- **Phase 5:** F-19 (the time seam); the time-budget constants' measurement
  (T-3); `go mate N` against an opponent-only clock.
- **Phase 6:** F-22 (TT age and policy set once per `go`), F-23 (a
  search-pool seam), F-24 (per-thread memory: copies reserve their own
  plies plus 1,024); B-5's keep-deeper rule under large Hash and many
  threads (idea 30).
- **Phase 8 (TCEC readiness):** table probe cost on 7-man files, Fathom's
  `exit()` paths, Hash at TCEC sizes and cgroup limits, a no-BMI2 CPU
  under SDE, the 4 GB-Hash prefetch A/B, ponder timing.

The rest, given targets by the owner (2026-10-28):
- **Phase 8 TCEC-readiness list** (DESIGN.md, Phase 8): whether TCEC
  treats Fathom's Cfish-derived code as another engine's (suspicion 12a,
  UNVERIFIED), the KB's technique prose written by an agent that read
  engine code (12b), and a load and stress run with B-1's forced-move
  stop.
- **Next phase-end audit** (DESIGN.md §5.2, Quality control 7): suspicions
  1b (a one-sided table bound stored as Exact at PV nodes), 9 (mate
  distances beyond MaxPly via the TT), 10a, 10b, 10c and 10h (idea 23's
  proxies and gate, before idea 23 resumes), 10f (spot-interruption pair
  bias, before the first AWS SPRT), 11b (the memory test's race), 13 (the
  hook's clang-format version); the proofs not run: fuzz_uci's search
  coverage, the book-slice match (may be dropped: the shuffled cloud book
  removes the bias it would measure), `test_hooks.sh`'s two build cases,
  `uci_timing` on an idle machine, and the local Windows rebuild of the
  v3, AVX-512, no-PEXT and PGO presets.
- **ideas.md:** P-5 as idea 35, the SIMD pick in `take_next` as idea 36,
  the MoveList/PlyFrame layout as idea 37; idea 29 is to run before B-3 is
  revisited (linked both ways).

## Owner's decisions after the report (2026-10-28)

- Merge audit-1 into main through a pull request once the full CI matrix
  is green.
- **The early-acceptance rule reads the normalized-Elo interval**, the
  scale of the SPRT bounds (fastchess `model=normalized`; the same model in
  `sprt_merge.py`); it first read the logistic one. On the nElo scale B-1's
  interval is [-3.31, +5.79], which does not clear -3. B-1 was kept by
  the owner's decision on the logistic interval, before this correction,
  and the owner kept it after it: B-1 ran its full SPRT to the cap
  (22,400 games, LLR +1.52 of 2.94, no time losses), and the gauntlet with
  it matched Milestone C (sprt-log.md).
- AWS SPRTs stay on x86-64-v3 until Phase 4.
- Every open item has a target (above).
