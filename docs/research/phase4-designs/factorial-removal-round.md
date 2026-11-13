# The factorial removal round (R30 with the skeptic's four fixes): design, not adopted

Status: **design for the owner's review, 2026-11-09; two of its decisions
taken the same evening (below). Nothing is queued or built.** It is §5.6 order step 18 (after step 12's search features),
the Phase 4 re-validation that replaces Quality control 6's per-feature
[−3, 0] SPRTs (decisions log 2026-11-07, think tank decision 6).

Sources read: DESIGN.md §5.6 (order steps 4, 12, 18, 19), Quality control 6,
Testing setup (design R, the kinds, head-to-head), the decisions log
(2026-11-07 decisions 2, 5, 6; 2026-11-09 testing policy);
docs/research/phase4-think-tank/phase-c-synthesis.md R30 and
phase-b-specialists.md ST5 and B14 §2.ST5 / §3.5; src/search/searcher.hpp
(`FORK_SEARCH_SWITCHES` at phase-4 8af5e4f); docs/history/phase-4/sprt-log.md;
tools/github/sprt_run.sh and .github/workflows/sprt.yml (one `test_opts` per
run today).

**The owner's decisions (2026-11-09, about 8 PM EST):** "Factorial removal
threshold: "estimate <= 0"." and "build the factorial tooling when step 18
comes up". So: **the removal rule is rule A** (§5.2: remove a switch whose
estimate `v_j` is at or below 0 nElo, subject to the guard), the risk
decision 6 accepted (about 23-24% of removing a +3 nElo feature at 16
stages); and **the tooling of §3 (per-shard rows, the factorial and guard
kinds, the row permutation, the design file, the fit script) is built when
step 18 comes up**, not before. §8's decisions 2, 3, 4 and 6 are still open.

## 1. What decision 6 accepted

The round becomes a factorial screen (R30) with B14's four fixes; "accepted:
about a 23% chance of removing a +3 nElo feature, for a decision on every
switch" (decisions log, 2026-11-07, decision 6). The four fixes (B14 §3.5):
1. **no switch and its parent both as factors** (multi-cut lives inside the
   singular test; check relief and lmr-in-check inside LMR);
2. **the row-to-shard map randomised every stage** (runner CPUs differ; a
   speed-type switch's value is CPU-dependent);
3. **the combined guard on design-R-type bounds [−6, 0], beta 0.2, cap 8**
   (a fixed 4-stage guard passes a −5 nElo set 32% of the time);
4. **the owner's explicit acceptance** of the 23% rate (done: decision 6).

Why not dedicated tests: certifying a neutral feature within 3 nElo at alpha
= beta = 0.05 needs about 72,600 pairs, about 91 stages per feature (ST5,
checked by B14); the check-relief removal test spent 13 stages (20,800 games)
without a decision (sprt-log, reval-no-check-relief).

## 2. The switch census (src/search/searcher.hpp, phase-4 8af5e4f)

31 switches. Disposition by R30's triage rule (step 0: "leave out every
feature whose network-era measurement puts P(value <= 0) below 1%"; they go
to SPSA, not removal) and by the parent rule.

| switch | default | evidence (sprt-log / searcher.hpp comments) | disposition |
|---|---|---|---|
| use_tt, use_pvs, use_quiesce, use_history, use_rfp, use_nmp, use_lmr, use_futility, use_see_prune, use_tables | on | tier-1 core (ST5 step 0) | out: triaged |
| use_singular_extension | on | +14.12 ± 6.55 STC (z about 4.3); LTC confirmation running (ltc-se-on-vs-off, undecided after stage 0 at 7:08 PM EST 2026-11-09, local driver log) | out: triaged |
| use_multi_cut | on | +9.19 ± 4.62 STC (z about 3.9); inside the singular test | out: triaged, and parent rule; LTC confirmation dispatched (ltc-mc-on-vs-off) |
| use_reply_history | on | +11.46 ± 5.57 (z about 4.0) | out: triaged |
| use_follow_history | on | +7.22 ± 3.92 (z about 3.6) | out: triaged |
| use_no_move_reduction (IIR) | on | +21.45 ± 5.98 STC; LTC H1 on [−3, 0] | out: triaged |
| use_stability_time, use_share_time | on | STC +18.69 ± 7.18, LTC +10.23 ± 5.14 (2026-11-08) | out: triaged (and time management) |
| use_take_history | on | +4.53 ± 2.99 at 22,400 games on S-512 (z about 2.96, P(<= 0) about 0.15%) | **out by the 1% rule**, although R30 lists it as a candidate: owner decision (§8); its LTC confirmation is queued (2026-11-08) |
| use_aspiration | on | Milestone A: +3.9 ± 7.6, stopped inconclusive (Quality control 6) | **factor** |
| use_mate_distance | on | never SPRTed (Quality control 6) | **factor** |
| use_see_quiesce | on | Milestone A: +9.5 ± 7.3 inconclusive (Quality control 6) | **factor** (parent `use_quiesce` triaged out, so allowed) |
| use_history_malus | on | never tested separately (Phase 3 milestone B deferred it to the removal round) | **factor** (parent `use_history` out) |
| use_lmp | on | tier-1 adoption, bootstrap era | **factor** (R30's list) |
| use_tt_eval_refine | on | the owner's exception: SPRT stopped undecided (+14.6 ± 17.8 at 1,000 games); Quality control 6 wants STC and LTC | **factor**; LTC treatment §5.3 |
| use_lmr_in_check | on | +4.21 ± 2.89, bootstrap era, never rechecked | **factor** (parent LMR out) |
| use_lmr_check_relief | on | removal on S512r2: −3.16 ± 2.86 Elo, nElo −5.22 ± 4.72 (P(<= 0) about 1.5%: above the 1% line) | **factor, the known control** |
| use_forced_move_stop | on | audit-1 B-1; never SPRTed; acts only with one legal root move, at the time budget | **out: time management** (owner decision, §8): STC cannot see TCEC's allocation, the reason decision 4 keeps time management out of STC tuning |
| tt_age_blend, tt_keep_exact, use_tt_keep_deeper, use_negative_extension | off | off features (the round removes on-features) | out; their disposition in §6 |

The "futile-node filter" R30 names has no switch on phase-4 (it is part of
`use_futility`, searcher.cpp around line 498-701); including it would need a
new switch (a code change with bench parity, owner). Any step-12 adoption
with a small estimate joins the factors when step 12 is done (R30: "any
small-estimate batch-4 adoption").

**The factor set today: k = 8** (aspiration, mate distance, SEE in
quiescence, history malus, LMP, TT eval refine, lmr-in-check, check relief).
No two are parent and child (fix 1): check relief and lmr-in-check are
siblings under LMR, which is not a factor. Known redundant pairs (B14
§2.ST5(a)): LMP with the futile-node filter (not a factor), TT eval refine with
RFP and futility (not factors); none inside the set.

## 3. Prerequisites (tooling; approved in principle by decision 5, "per-shard options for the factorial screen")

1. **Per-shard options:** sprt.yml passes one `test_opts` to every shard
   today; a design run passes a 16-row table (one fastchess option string per
   row) and the shard plays its row. sprt_merge.py's same-options check gets
   a design-mode exemption (ST5's effort note). A kind for the driver
   (`--kind factorial`, a placeholder name) fixed in design.json like the
   others.
2. **Tuning builds on both sides:** switches are UCI options only in
   FORK_TUNE builds (B14 §2.ST5(e)); both sides are the same binary, so
   speed is equal by construction.
3. **Row-to-shard randomisation (fix 2):** per stage, a permutation of the
   16 rows over the 16 shards from a seed derived from the run's name and
   stage (SHA-256, as spsa.py derives its draws), written into the stage's
   dispatch record and each shard's meta; the merge refuses a shard whose
   row does not match the recomputed permutation.
4. **The design:** an A-optimal 16-row block for k = 8, m = 3 (each row 3
   switches off), found by search and committed as data before the first
   stage; each stage plays the same 16 rows, permuted.
5. **The fit:** a weighted-least-squares script (name to screen) over the
   per-shard pentanomials: per shard the mean pair score minus 1/2 and its
   variance from the shard's own pentanomial, the model
   `score_row = sum_j x_row,j b_j` with no intercept (the base is the full
   engine), weights the inverse variances; `b_j` converted to nElo with the
   same conversion sprt_merge.py's `nelo` uses, on the pooled pentanomial
   variance. Output per switch: the estimate of its value `v_j = −b_j` (nElo
   lost by switching it off), its SE, and a lack-of-fit statistic (the 16
   row means against the additive model: 16 − 8 = 8 degrees of freedom), the
   one diagnostic for interactions a main-effects screen has.
6. **The guard kind:** design R's alpha 0.05, beta 0.2, cap 8 on bounds
   [−6, 0] (fix 3); `--kind search` fixes [0, 6], and the positional form
   runs alpha = beta = 0.05, so the guard needs its own kind or option
   (`--kind guard`, placeholder).

## 4. The design

### 4.1 Steps

| step | what | stages |
|---|---|---|
| 0 | triage (§2), done on paper here, rechecked at step 18 against the then-current SPRT log | 0 |
| 1 | the tier-2 block check (X9, order step 4): not found in sprt-log at 8af5e4f; run if still not run | 2 |
| 2 | **pilot**: k = 4 (check relief, lmr-in-check, aspiration, mate distance), m = 2, 1 stage | 1 |
| 3 | **main screen**: k = 8, m = 3, 16 rows per stage, 16 stages; extended to 24 only under the one-look rule below | 16-24 |
| 4 | **combined guard** of every removal together, STC, [−6, 0], beta 0.2, cap 8 | 2-8 |
| 5 | LTC guard, only if the removal set contains an LTC-flagged switch (§5.3) | 4-6 LTC stages |

### 4.2 What the screen can resolve (my arithmetic; the scratch script is not committed)

Per-stage noise: an STC stage of 1,600 games gives ±17.02 nElo at 95%
(sprt-log, every 1,600-game stage), SE 8.68; a shard is 1/16 of a stage, SE
34.7 per row. Per-switch SE of the least-squares estimate for the best
random 16-row block found (3,000 random draws per design; an upper bound on
the A-optimal value):

| design | stages | per-switch SE (nElo) | P(estimate <= 0) at a true value of 0 / +3 / +5 / +8 |
|---|---|---|---|
| k = 8, m = 3 | 16 | 4.28 | 0.50 / 0.24 / 0.12 / 0.03 |
| k = 8, m = 3 | 20 | 3.83 | 0.50 / 0.22 / 0.10 / 0.02 |
| k = 8, m = 3 | 24 | 3.49 | 0.50 / 0.20 / 0.08 / 0.01 |
| k = 10, m = 4 | 24 | 3.90 | 0.50 / 0.22 / 0.10 / 0.02 |
| k = 12, m = 4 | 24 | 4.55 | 0.50 / 0.25 / 0.14 / 0.04 |
| pilot k = 4, m = 2 | 1 | 13.85 | 0.50 / 0.41 / 0.36 / 0.28 |

ST5's A-optimal search gave 4.10 (k = 8, m = 3, 16 stages) and 3.35 (24),
close to these; for k = 12, m = 4 it gave 4.48 at 16 stages where the random
search here finds 5.57, so larger designs depend on a real A-optimal search
(the tooling's step 4; ST5's figure UNVERIFIED here).

**The pilot cannot check the control's sign** (SE 13.9 against an expected
−5): it validates the plumbing (each shard's row and options applied, equal
shard counts, no opening reused, the permutation recomputed) and catches gross
errors only. The real check of the method is the control inside the main
screen (expected about −5 ± 8.6 at 95%, R30).

### 4.3 Time control and conditions

STC 8+0.08, Hash 16, Syzygy 3-4-5, the UHO book, as every SPRT stage; fresh
openings for each stage (stages never reuse lines); 1,600 games per stage,
100 per shard (one row per shard). The screen is STC by design (R30's
compute is STC); §5.3 handles the LTC-flagged switch.

### 4.4 The one look

After 16 stages: if every switch's estimate is more than 1 SE from the
removal threshold, stop; otherwise run 8 more stages (to 24) and decide there.
One look, declared now, so the stopping bias stays small (UNVERIFIED in size;
not simulated here).

## 5. Analysis and decision rules

### 5.1 Main effects and interactions

- `v_j` is the value of switch j with about m − 1 = 2 others also off. A
  redundant partner biases `v_j` toward "keep" (safe); a synergistic one
  toward "remove", which the guard catches by testing the joint removal
  (ST5, B14).
- The lack-of-fit statistic is reported; if it rejects additivity at 1%, the
  owner sees it before any removal, with the row means.
- **The control:** check relief's estimate must lie within 2.5 SE of the
  dedicated estimate (nElo −5.22 ± 4.72 on S512r2); otherwise the method is
  refuted and the round falls back to R30's kill: dedicated tests under
  design R (fixed 4 stages each, decided by estimate).

### 5.2 Per switch (owner decision on the threshold, §8)

R30 states the rule as "remove if the posterior mean value is <= +1 nElo"
and quotes the 23% removal rate of a +3 feature. **The two do not match
under a flat prior.** ST5's rates (50% at 0, 23% at +3, 11% at +5, 2.5% at +8)
are reproduced by "remove if the estimate is <= 0" at SE 4.1 (my
reconstruction; ST5 does not state the prior). With "estimate <= +1":

| rule | SE | P(remove) at 0 / +3 / +5 / +8 |
|---|---|---|
| A: estimate <= 0 | 4.28 (16 stages) | 0.50 / 0.24 / 0.12 / 0.03 |
| A | 3.49 (24) | 0.50 / 0.20 / 0.08 / 0.01 |
| B: estimate <= +1 | 4.28 | 0.59 / 0.32 / 0.18 / 0.05 |
| B | 3.49 | 0.61 / 0.28 / 0.13 / 0.02 |

**Rule A, decided by the owner (2026-11-09)** (it is the risk decision 6
accepted). An
empirical-Bayes posterior mean across the k switches (ST2's shrinkage) is
reported beside each estimate as a diagnostic; it does not change the rule.
So per switch:
- `v_j <= 0`: **remove** (subject to the guard);
- `v_j > 0`: **keep**; its switch is folded into plain code after the round
  (Quality control 6: only after the re-validation);
- the control (check relief) is decided like any other switch.

### 5.3 The guard, and LTC

- **STC guard (fix 3):** the engine with every removal applied (switches off)
  against the full engine, [−6, 0] nElo, alpha 0.05, beta 0.2, cap 8,
  idea id `r30-guard`. H1 (the set costs nothing measurable): the removals
  stand. H0 or capped: **one** second try (the two-try rule) with the
  removal whose `v_j` was largest put back; if that fails too, nothing is
  removed this phase and every switch stays.
- **LTC:** Quality control 6 flagged `UseTtEvalRefine` for STC and LTC
  40+0.4 testing, and features on the LTC-sensitive list are removal-tested at
  LTC. Proposal: if the removal set contains such a switch, the guard is
  repeated at LTC 40+0.4 (the same bounds, cap 4-6 LTC stages); a keep needs
  no LTC test (keeping is the safe direction). Owner decision (§8).
- **Priority switch: `UseCaptureProbe` (ProbCut), tested at LTC (owner, 2026-11-13, about 2:00 PM EST).** The over-pruning check
  found no broad over-pruning (phase-4 929f114 solves the WAC and ECM suites as d33a4db does, 1-2 plies
  deeper), but the tactical misses concentrate in ProbCut: with it off the head solves significantly more
  (483 positions: 350 vs 335 at 100k nodes, 429 vs 412 at 1M, 456 vs 434 at 2 s), while it passed its LTC
  games (+9.40 ± 5.03 Elo). ProbCut is kept for now; in this round it is flagged as a priority switch and its
  removal is tested at LTC 40+0.4 whatever the STC screen shows. The 18 positions the head newly failed are a
  ready diagnostic set for ProbCut variants (~/fork-jobs/tactics/ on the dev machine, not
  committed; the suites are Arasan's wacnew and ecmgcp, ORIGINALITY.md).

### 5.4 After the round

Removed features: their code and switch deleted in one commit per feature
(bench changes only if the feature was on; the guard's binary had them off, so
the guard's bench is the reference), the constants table and ideas.md
updated, every estimate logged in the SPRT log (including the kept ones).
Kept features: switches folded into plain code (bench unchanged). Their
parameters go to the final retune (final-retune.md), which runs on the
post-round engine.

## 6. The off switches (not in the round)

`tt_age_blend` (the owner's 2026-10-26 experiment), `tt_keep_exact`
(re-validation item 2: only at a TCEC-scaled hash, else dropped, 2026-11-07),
`use_tt_keep_deeper` (Phase 6's TT tests) and `use_negative_extension`
(kept until R40's cut-node retest, R30 "Keep out of the round"). Deleting an
off switch's code changes nothing played (bench unchanged), so it needs no
SPRT; each deletion waits for the decision its own record names. The owner
decides whether `tt_age_blend`, which no record keeps for a later test, is
deleted at the fold-in.

## 7. Cost (GitHub stages; STC stage about 18 minutes, DESIGN.md §5.6)

| part | stages | about |
|---|---|---|
| X9 block check, if not yet run | 2 | 0.6 h |
| pilot | 1 | 0.3 h |
| main screen | 16-24 | 4.8-7.2 h |
| STC guard (1-2 tries) | 2-16 | 0.6-4.8 h |
| LTC guard, only with an LTC-flagged removal | 4-6 LTC stages (16-24 stage-equivalents; an LTC stage took 80-83 minutes in tm-r8-ltc) | 5.3-8.3 h |
| **total** | **21-43 STC stages, plus the LTC guard if needed** | **about 6-13 GitHub-hours** |

R30 estimated 22-32 stages; the upper end here adds a second guard try.
Engineering: about 2 days (ST5), shared with the SPSA driver's per-pair
option plumbing (X18).

## 8. Decisions needed from the owner

1. The removal threshold: rule A (estimate <= 0, the 23% figure) or R30's
   wording (posterior mean <= +1, about 28-32% at our SEs). **Decided
   (owner, 2026-11-09): rule A, "estimate <= 0".**
2. `use_take_history`: out by the 1% triage rule (z about 2.96) or a factor
   as R30's candidate list says.
3. `use_forced_move_stop`: out as time management, or a factor.
4. The LTC guard for a removal set containing `UseTtEvalRefine` (or any
   LTC-listed switch).
5. The tooling: per-shard rows, the factorial and guard kinds, the WLS
   script (decision 5 approved per-shard options in principle). **Decided
   (owner, 2026-11-09): built when step 18 comes up.**
6. Whether `tt_age_blend` is deleted at the fold-in.

## 9. Accepted risks (decision 6, and those this design adds)

- About a 23% chance of removing a true +3 nElo feature (rule A at SE about
  4); about 50% of removing a neutral one, which is the point.
- Main effects only: two-factor interactions alias into the estimates; the
  guard tests the joint removal and the lack-of-fit statistic flags gross
  non-additivity, nothing more.
- STC only, except the LTC guard of §5.3: a feature worth more at LTC than at
  STC (the IIR pattern: +21.5 STC, +26.3 LTC, think tank O5) can be removed
  on STC evidence.
- Runner heterogeneity is averaged by the per-stage permutation, not removed.

## 10. Names and constants for the screens (none screened yet)

Names: the kinds `factorial` and `guard`, the design file (e.g.
`design-rows.json`), the fit script (e.g. `tools/github/factorial_fit.py`),
any new metadata field (`row`). Constants: k = 8 and m = 3 (ST5's design),
16-24 stages, the one-look rule (1 SE), the removal threshold 0 nElo (rule
A, the owner's choice on 2026-11-09), the guard's [−6, 0], beta 0.2, cap 8 (B14), the pilot's
k = 4, m = 2, 1 stage (R30), the lack-of-fit 1% level, the control's 2.5 SE
(R30). Statistics constants, none taken from an engine.

## 11. Prior art (concept level)

Factorial and fractional-factorial screening: Fisher, The Design of
Experiments (1935); Plackett and Burman, Biometrika 33 (1946); Box, Hunter and
Hunter, Statistics for Experimenters (2nd ed. 2005) (as cited by ST5). The
combined guard of simplifications is the think tank's S1 §7.2.5 suggestion
from public test-framework practice. No engine project is known to use
factorial screens (ST5; UNVERIFIED).

## 12. Unverified items

- The X9 block check's status (not in sprt-log at 8af5e4f).
- ST5's A-optimal SEs (only bounded here by a random search).
- The stopping bias of the one look.
- LTC stage time at VLTC-like loads (not needed here) and the runners' CPU
  mix per stage.
