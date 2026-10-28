# Audit-1: the owner's brief and the state at handoff

The session note that started audit-1, kept as its record: written
2026-10-27 at the end of the session that ran the idea 23 validation
pilot, untracked until the Phase 3 end and committed unchanged below this
note on 2026-10-28. Its "state" sections describe that day; what the
audit did is in audit-1.md.

## The owner's brief (verbatim, 2026-10-27)

Full engine audit, cleanup and improvement, before idea 23 and
tier 2. Run in a fresh session; agents must never open any other
engine's source. Token cost is not a constraint: run agents in
parallel.

Do ALL work on a new branch (e.g. audit-1) created from current
main. Nothing touches main until I approve the final results.

PHASE A: AUDIT (review only, change nothing)
Separate subagents, in parallel:
1. Search correctness: mate scores, TT bounds and replacement,
   repetition and fifty-move handling, tablebase score
   integration, aspiration windows, PV handling, stop handling.
2. Performance: hot paths, cache use, per-thread memory,
   unnecessary allocation or recomputation, against the profile.
3. Robustness and concurrency: UCI threads, stop/quit races, Hash
   allocation and fallbacks, OOM handling, time management under
   load.
4. TCEC judge and originality: structure and constants vs the four
   screened engines (via the name/constant-check procedure),
   licenses and credits, TCEC-toolchain build, public-repo hygiene.
5. Test suite: untested paths, flaky tests, tests that would pass
   on broken code.
6. Tooling: sprt.sh, cloud shard scripts, idea 23 harness, perf
   gate, check.sh and hooks.
7. Docs and consistency: DESIGN.md, ORIGINALITY.md, SPRT log,
   ideas.md, README credits vs the actual code; dead code; stale
   switches and parameters.
8. Behavior improvements: propose changes to how Fork plays that
   could gain strength or search efficiency, within the features
   it already has: better conditions or missed cases in pruning,
   reductions and extensions; move-ordering scoring; TT use and
   replacement; quiescence; tablebase use in search; time
   management decisions. Each proposal states its reasoning, the
   expected effect, and any constants it introduces (each needing a
   recorded justification). Don't duplicate the planned tier 2
   techniques in deliverable 9. Ideas come from Fork's own
   reasoning, measurements and the KB's clean-room descriptions,
   never from another engine's code.
9. Refactoring: clarity, maintainability and simplification, and
   better structure for what's coming (tier 2's new history tables
   and extensions, Phase 4's network evaluator, Phase 6's
   threads), modern C++ idioms. Refactors must not change behavior
   (bench identical).
Also re-check that every item from both external reviews and the
Phase 1/2 reviews is resolved as recorded.

Rules: no claimed bug without proof (a failing test, reproduction
or measurement); unproven concerns go in a separate suspicions
list. Heavy-CPU proofs only when no SPRT or long job is running.

PHASE B: RECONCILE
One merged, deduplicated list, in sections:
- Bugs, sorted by severity (critical, high, medium, low): what,
  where, evidence, impact on strength or TCEC, proposed fix, effort.
- Behavior improvements (agent 8), ranked by expected value.
- Refactors (agent 9).
- Cleanup items (dead code, stale docs, unused files and branches).
- Suspicions.
STOP for my approval.

PHASE C: FIX AND IMPROVE (on the audit branch, after approval)
- Each change in its own commit, in approved order; full check
  after each.
- Refactors, cleanups and pure speed fixes must keep bench
  identical; no SPRT needed.
- Every behavior improvement gets its own SPRT on the GitHub
  shards, one per SPRT, never bundled, gainer bounds ([0, 5], or
  [0, 3] for small expected effects). Keep only those that pass;
  revert and log the rest.
- Behavior-changing bug fixes: SPRT on the GitHub shards,
  non-regression bounds [-3, 0].

PHASE D: VERIFY
- Performance gate: audit branch vs current main.
- Gauntlet: audit branch against the Milestone C anchors, same
  openings and settings, compared with Milestone C's 2402.5.
- Push the audit branch, report everything, and STOP. I'll decide
  whether to merge it into main.

## State at handoff

- main = origin/main = 6b04ed5 (held-out promotion check added after 090252e). Bench 17309921 / 372dc2e2d8a88e4b. CI green
  through 65f9b63; 090252e (positions data + DESIGN.md) pushed after.
- Nothing is running: no SPRT, no evolve loop, no position generation.
- Idea 23 (heuristic discovery, LMR region): validation run done; the long
  run (40 generations, 3M tokens, 9 h) is **on hold until the audit is
  approved**. Its state, measurements and the 4x position set are in
  DESIGN.md §5.2 (deliverable 8c bullets). The audit's agent 6 covers
  `tools/evolve/`.
- Found this session and already fixed on main (so the audit can verify
  them, not rediscover them):
  - b89185f: the LMR context's `history` read the opponent's history.
  - be70f48: GCC `-Wshadow` in a test (a local `Case` struct).
  - 3dfbe91: `lmr_move_facts` on castling (king-to-rook encoding).
  - 00bed14: LMR re-searches entered after a stop (a node-limit overshoot
    of 1-2 nodes).
- Commits since 2026-10-27 evening went in **without the local full
  check** at the owner's request (CI checked each). The audit's Phase C
  rule is a full check after each change.
- The SPRT shard workflow (`sprt.yml`, `tools/cloud/`) was validated on
  GitHub on 2026-10-27 (run 40593075091, 16 shards, about 21 min).
- Branches: d8-a, d8-b1, d8-b2, d8-c, d8-final (worktree `../fork-d8`),
  milestone-c, review-fixes, tcec-cutechess; kb at e451077 (unpushed
  commit e451077). Cleanup candidates for agent 7.
- Open from earlier: the end-of-Phase-3 removal round (after tier 2), the
  Phase 5 LTC check of deliverable 8, the Supernova 2.4 / K2 0.99 anchors
  (the owner builds them).

## Note (owner, 2026-10-28)

Phase 4 multi-agent plan recorded in DESIGN.md; not started.
