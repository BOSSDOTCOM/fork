# Phase 4, milestone 1: the pre-merge checklist (phase-4-m1 into main)

Prepared 2026-11-05 on branch phase-4-m1 (phase-4 at 8d22e72 plus the
README update). The pull request is opened only when GitHub is free (owner,
2026-11-05). Every check below was run on that date unless it says otherwise.

## 1. Every default-on search feature and its SPRT

main (the Phase 3 close-out, PR #6) has 20 search switches; this merge adds
9, every one tested by an SPRT on GitHub (docs/history/phase-4/sprt-log.md):

| Switch | Default | SPRT (STC 8+0.08 unless stated) | Result |
|---|---|---|---|
| use_lmr_check_relief | on | 2026-10-29 lmr-check-relief, [0, 3] | H1, +11.26 ± 5.54 (bootstrap evaluation) |
| use_lmr_in_check | on | 2026-10-29 lmr-in-check, [0, 3] | H1, +4.21 ± 2.89 (bootstrap evaluation) |
| use_singular_extension | on | 2026-10-31 se-vs-base, [0, 5] | H1, +14.12 ± 6.55 |
| use_multi_cut | on | 2026-10-31 mc-vs-se, [0, 3] | H1, +9.19 ± 4.62 |
| use_negative_extension | **off** | 2026-10-31 ne-vs-mc | H0, -8.73 ± 4.98: rejected |
| use_reply_history | on | 2026-11-01 reply-vs-mc, [0, 5] | H1, +11.46 ± 5.57 |
| use_follow_history | on | 2026-11-01 follow-vs-reply, [0, 3] | H1, +7.22 ± 3.92 |
| use_take_history | on | 2026-11-01 take-vs-follow, [0, 3] | H1, +4.53 ± 2.99 |
| use_no_move_reduction (IIR) | on | 2026-11-02 iir-d8-vs-s512r2, [0, 3]; LTC 40+0.4 2026-11-03, [-3, 0] | H1, +21.45 ± 5.98; LTC H1, +26.25 ± 6.65 |

The network: each default net passed an SPRT ([0, 5], 8+0.08) against the
one before it (docs/nets.md): B0 against the bootstrap evaluation
+486.85 ± 32.07; B0r1 against B0 +200.24 ± 16.05; B0r2 against B0r1
+235.45 ± 16.04; S-512 against the B0 control +43.66 ± 12.02; S512r2 against
S-512 +151.35 ± 12.50 (run 41349145950).

**Inherited from main, not changed here** (an audit of both phases' SPRT
logs, 2026-11-05): 16 of the 25 default-on switches have an SPRT pass of
their own. The other 9 came in with Phase 3 under the owner's decisions of
that phase, and are all due for the Phase 4 re-validation round (every
search feature switched off in turn with the network, DESIGN.md §5.2,
Quality control 6; not started):

- use_mate_distance: never SPRTed (kept as exact);
- use_history_malus: tested only inside the deliverable 5 ordering test;
- use_rfp, use_nmp, use_lmr, use_lmp, use_futility: passed as a group
  (STC +439.21 ± 61.04, LTC +555.67 ± 80.38), not one by one;
- use_aspiration, use_see_quiesce: inconclusive, kept under the Milestone A
  allowance;
- use_tt_eval_refine: the owner-approved exception (provisional, LLR 0.40);
- use_forced_move_stop, use_tables: accepted by the owner at the game cap
  (LLR 1.52 and 2.72).

The network re-validation of check relief and in-check LMR has started as
filler (`reval/no-check-relief`: -3.86 ± 3.40 after stage 8, 14,400 games,
nElo -6.44 ± 5.67, LLR -1.77 on [-3, 0], undecided; `reval/no-lmr-in-check`
not started). Corrected 2026-11-06: the figure first written here was the
stage 5 result (9,600 games), already stale when written; the run IDs are in
the SPRT log's attribution audit (docs/history/phase-4/sprt-log.md).

## 2. Experimental switches and builds are off

- Off by default: tt_age_blend, tt_keep_exact, use_tt_keep_deeper (each
  inconclusive or negative in Phase 3), use_negative_extension (H0 above).
- `FORK_TUNE` OFF, `FORK_EXPERIMENT` empty (CMakeLists.txt); `update.sh`
  sets neither.
- No tier-2 batch branch is merged: tier2/batch3, tier2/batch4 and the
  sprt/* test branches stay outside phase-4, with their switches off.

## 3. The default network is in the repository

- `nets/s512r2.fnet` (804,064 bytes) is tracked and is CMake's default
  (`FORK_EVALUATOR` nnue, `FORK_NET` nets/s512r2.fnet); `fork version`
  reports `net s512r2`.
- `fork netcheck tests/nnue/s512r2.parity`: 446 positions, 0 mismatches.
- The build needs no untracked file (CI builds from a clean clone).

## 4. Bench matches

- clang-release build of phase-4-m1 (875c964): nodes 14,180,299, signature
  4cf778ff753861f7, equal to tests/bench-s512r2.ref.
- The engine is unchanged since the gauntlet's commit 3902d00 (only
  `src/web` changed since), so the README's 3445.8 ± 21.6 describes the
  engine merged here.
- CI checks the same bench on every job of the pull request's run.

## 5. Before opening the pull request

- `bash scripts/scan-push.sh phase-4-m1`, passing, as its own step, then the
  push (the push gate).
- GitHub idle (no SPRT stage running). The pull request's CI runs the full
  matrix including perft_epd_full (CMakeLists.txt changes since main), about
  2 hours.
- Branch protection: every job green before the merge.
