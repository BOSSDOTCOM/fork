# The final retune, expanded: inventory, sensitivity screen, grouped SPSA, RSPSA, cost (plan only, 2026-11-15)

Status: **a plan for the owner's review. Nothing was run.** No games, no workflow dispatches, no builds, no
jobs. This expands roadmap step 19 (DESIGN.md §5.6; docs/research/phase4-designs/final-retune.md, "FR" below)
in response to the owner's order of 2026-11-15: "(1) inventory every tunable constant ... (2) propose a cheap
sensitivity screen ... (3) group the important ones by subsystem ... (4) evaluate RSPSA ... (5) estimate games
and GitHub hours per group. Report before running anything."

Sources read: src/tune/params.hpp and params.cpp (phase-4 14eed00); `FORK_SEARCH_SWITCHES`
(src/search/searcher.hpp:277-329); the searcher, move selector, LMR table and drift table code where each
parameter is read; docs/research/staleness-audit-2026-11-12.md ("audit"); FR; DESIGN.md §5.2 Testing setup
and "Search constants", §5.6 rows 17a/18/19 and step 17a's spec, §6 rows to 2026-11-15;
docs/research/phase4-designs/factorial-removal-round.md ("FRR"); the SPSA tooling on branch
`tune/spsa-pinned` 41ec3b4 (tools/github/spsa.py, spsa_run.sh, spsa_calibrate.py, spsa-r14.json; **not merged
into phase-4**); tools/github/sprt_run.sh; docs/ideas.md idea 150; think tank B7 O2
(phase-b-specialists.md). Measured data read-only: ~/fork-spsa/github/spsa-r14-m2/ (iterations.jsonl,
report.txt) and every SPRT driver log under ~/fork-data/sprt/ (220 folders). The two scratch scripts that
read them were deleted after use; their method is stated where each number is used.

> **The owner's decisions on this plan (2026-11-15, about 7:40 PM EST).** (1) `CutNodeLmrPlies` and
> `LmrNotImprovingPlies` are converted to 64ths of a ply with today's values exactly (bench identical): now
> `CutNodeLmrSixtyFourths` and `LmrNotImprovingSixtyFourths`, 64, range 0-192, step 10, both in
> phase4-designs/final-retune.md's tables. (2) The batch-4 razoring and bad-capture dimensions are dropped from
> the plan (not in phase-4's code; not worth porting). (3) The sensitivity screen (all 32 STC candidates
> perturbed, never updated) stays as the first step. (4) RSPSA: rejected for the main runs; an offline
> simulation pilot only. (5) The SPSA driver is made lane-aware now (sprt_run.sh's capacity rule instead of
> waiting for every other run). Order unchanged: Lazy SMP's tests, the removal round, then the retune. Where
> the text below differs (the two whole-ply rows, the batch-4 dimensions, RSPSA as an option, the tooling
> list), these decisions govern.

## 0. Summary

- **57 parameters** in `FORK_SEARCH_PARAMS`. **41 are retune candidates**: 32 class (a) at STC and 9 class (b)
  at LTC. **16 are out**: 7 time management (by rule), 2 not in the SPSA by FR (TableProbeMinDepth,
  StaleDepthPerSearch), 2 **inert** (HistoryBonusFactor, LmrCorrectionStrength), 2 left to E5 (the drift
  learning rate), 3 belonging to switches that are off. The eval scale is not a parameter, so it cannot be tuned
  (FR §2 class (d)).
- **Not in params.hpp but needed if the owner wants them tuned:** whole-ply terms that could become 64ths
  (CutNodeLmrPlies and LmrNotImprovingPlies already are parameters but their whole-ply ranges leave SPSA almost
  nothing to search; LmrCheckRelief is a literal), finer units for HistoryKeepQuarters and LmpImprovingEighths
  (FR's open decisions), and batch 4's three razoring and bad-capture dimensions (HorizonDropMargin,
  HorizonDropMaxDepth, BadCaptureStopMargin). The owner added those three to the retune on 2026-11-10, but they
  are **not in phase-4's code** (grep of src/).
- **Screen (recommended, design S1):** one *zero-gain SPSA* run, a random-balance fold-over screen that
  reuses spsa.yml's per-pair draws. All 32 class (a) candidates go in at once, with c_screen = min(2c,
  distance to the bound), theta held fixed, **8 STC stages (12,800 games, about 2.4 lane-hours)**. In c-units
  the per-parameter slope SE is 0.89 Elo, and P(flagged) is 0.05 / 0.38 / 0.88 / 0.99 at a true secant of
  0 / 1.5 / 2.8 / 4 Elo. The alternative (S2) is a Plackett-Burman screen on step 18's per-shard factorial
  tooling.
- **Groups:** G1a eval-margin pruning (8), G1b move-count and SEE pruning (7), G2 STC reductions (4), G3
  history and ordering (9, with the history skip), G4 correction and the aspiration window (4), and G5, the LTC
  group of all 9 class (b) parameters (optionally split into G5a extensions/IIR and G5b
  LMR-divisor/history/ProbCut on the two lanes).
- **RSPSA: reject for the main runs.** Keep idea 150 open, with an offline simulation pilot only (no GitHub
  pilot) (§4).
- **Cost:** about **47-63 lane-hours** of GitHub time in total, and **about 31-41 hours of critical path** on
  two lanes (§5). FR's own estimate was 30-40 h; the difference is the screen, the larger STC set (32
  candidates against FR's about 22) and a 9-parameter LTC group (FR assumed about 5).

## 1. Inventory

Columns: default, range and step from src/tune/params.hpp:42-98. Provenance is the audit's §2 table, the
constants table (DESIGN.md "Search constants") and FR §3 for the later adoptions. Class follows FR §2. Switch
is the feature's switch in `FORK_SEARCH_SWITCHES` and its default. "Factor" marks a switch that is a factor
in step 18's removal round (FRR §2): its parameters drop out if the switch is removed. **Every value was set on a
net before r3kr1**, which has been the default since 2026-11-14 (DESIGN §6). The audit ran on r8brft1.

### 1.1 Class (a): STC candidates (32)

| # | parameter | subsystem / group | default | range | step | provenance (last justification) | switch | flag |
|---|---|---|---|---|---|---|---|---|
| 1 | RfpMaxDepth | pruning, G1a | 6 | 3-12 | 1 | reasoning, bootstrap 10-25: **placeholder** | use_rfp (on) | |
| 2 | RfpMargin | G1a | 55 | 30-160 | 6 | SPSA R14 (S512ppr3, 11-09), pinned at the floor 40 + c | use_rfp | the floor was widened to 30 |
| 3 | NullMinDepth | G1a | 3 | 1-6 | 1 | reasoning: **placeholder** | use_nmp (on) | FR flag: near floor |
| 4 | NullSurplusPerPly | G1a | 301 | 150-600 | 23 | SPSA R14 (moved +0.17c: flat) | use_nmp | |
| 5 | NullSurplusPliesMax | G1a | 2 | 0-6 | 1 | reasoning: **placeholder** | use_nmp | FR flag: both sides |
| 6 | FutilityMaxDepth | G1a | 6 | 3-12 | 1 | reasoning: **placeholder** | use_futility (on) | |
| 7 | FutilityOffset | G1a | 86 | 30-200 | 8 | SPSA R14 (still falling) | use_futility | |
| 8 | FutilityGrowth | G1a | 50 | 25-140 | 5 | SPSA R14 (still falling) | use_futility | |
| 9 | LmpMaxDepth | pruning, G1b | 4 | 1-8 | 1 | reasoning + histogram: **placeholder** | use_lmp (on, **factor**) | |
| 10 | LmpQuietAllowance | G1b | 8 | 3-24 | 1 | SPSA R14, pinned at floor 7.7 | use_lmp | floor widened to 3 |
| 11 | LmpImprovingEighths | G1b | 1 | 0-4 | 1 | natural value, +6.82 ± 4.37 STC (11-13) | use_improving_lmp (on) | **unit**: FR flag, one step from floor |
| 12 | SeePruneMaxDepth | G1b | 6 | 3-12 | 1 | reasoning: **placeholder** | use_see_prune (on) | |
| 13 | QuietSeeFloor | G1b | 60 | 30-120 | 5 | reasoning; left out of R14 as insensitive | use_see_prune | FR: only if sensitive |
| 14 | CaptureSeeFloor | G1b | 118 | 50-200 | 8 | SPSA R14 | use_see_prune | |
| 15 | QuiesceMoveCap | G1b | 2 | 1-6 | 1 | retry value, +8.90 ± 5.56 STC (11-13) | use_quiesce_move_cap (on) | **unit**: FR flag |
| 16 | LmrMinDepth | reductions, G2 | 3 | 1-6 | 1 | reasoning: **placeholder** | use_lmr (on); also root LMR and capture LMR read it (searcher.cpp:947, 1181) | FR flag |
| 17 | LmrMinMove | G2 | 4 | 1-8 | 1 | reasoning + bench stat (83.4% first-move cutoffs now) | use_lmr | 1 searches exactly as 2 (FR) |
| 18 | CutNodeLmrSixtyFourths (was CutNodeLmrPlies) | G2 | 64 | 0-192 | 10 | head-to-head 2 − 1 = −5.33 ± 12.04 nElo; STC +6.02, LTC +9.75 | use_cut_node_lmr (on) | **missing from FR §3's tables**; whole plies: at c = 1 SPSA reaches only 1-2 (needs 64ths) |
| 19 | LmrNotImprovingSixtyFourths (was LmrNotImprovingPlies) | G2 | 64 | 0-192 | 10 | natural value, +12.71 ± 7.00 STC (11-13) | use_improving_lmr (on) | whole plies, as #18 |
| 20 | HistoryBonusCap | history/ordering, G3 | 1250 | 625-2500 | 94 | reasoning (HistoryMax / 8): **placeholder** | use_history (on) | caps the linear bonus |
| 21 | LinearBonusPerPly | G3 | 125 | 63-250 | 9 | natural value, +8.98 ± 5.70 STC (11-13) | use_linear_bonus (on) | |
| 22 | HistoryKeepQuarters | G3 | 2 | 0-4 | 1 | natural value, +5.71 ± 3.77 STC (11-12) | use_history_ageing (on) | **unit**; acts between searches, so its LTC behaviour is UNVERIFIED (FR) |
| 23 | ReplyWeight | G3 | 6 | 0-12 | 1 | bench index (S-512, 10-31); re-measured 8 (weak) | use_reply_history (on) | FR flag: ceiling |
| 24 | FollowWeight | G3 | 4 | 0-16 | 1 | bench index (S-512, 11-01); re-measured 8 | use_follow_history (on) | |
| 25 | TakeWeight | G3 | 4 | 0-16 | 1 | bench index (S-512, 10-31); re-measured 2 | use_take_history (on) | |
| 26 | DirectCheckBonus | G3 | 5000 | 2500-10000 | 375 | natural value, +5.50 ± 3.93 STC (11-12) | use_check_order_bonus (on) | |
| 27 | HistorySkipPerPly | G3 (see §3.1) | 700 | 350-4000 | 183 | head-to-head pick (r8brft1, 11-11) | use_history_skip (on) | FR flag: floor |
| 28 | HistorySkipMaxDepth | G3 | 3 | 1-6 | 1 | **placeholder** | use_history_skip | FR flag: floor |
| 29 | MinorDriftShare | correction, G4 | 32 | 16-64 | 5 | retry value, +5.57 ± 4.01 STC (11-12) | use_minor_drift (on) | |
| 30 | DriftLimit | G4 | 300 | 150-600 | 23 | reused from T32's pawn-table measurement (UNVERIFIED for these keys) | use_minor_drift | |
| 31 | AspirationMinDepth | window, G4 | 5 | 2-10 | 1 | bench p90 (bootstrap); the re-run no longer settles | use_aspiration (on, **factor**) | |
| 32 | AspirationHalfWidth | G4 | 12 | 8-40 | 1 | bench p90, then kept by R14 SPSA; re-measured 29 | use_aspiration | |

### 1.2 Class (b): LTC candidates (9)

| # | parameter | subsystem | default | range | step | provenance | switch |
|---|---|---|---|---|---|---|---|
| 33 | SingularMinDepth | extensions | 6 | 3-12 | 1 | T27 rule 2 (S-512) | use_singular_extension (on) |
| 34 | SingularEntrySlack | extensions | 3 | 0-6 | 1 | T27 rule 3 | same |
| 35 | SingularMarginPerPly | extensions | 6 | 2-16 | 1 | T27 rule 1; 22 refuted (H0 −26.76 ± 9.93) | same (multi-cut reads the same bar) |
| 36 | NoMoveReduceMinDepth | reductions (IIR) | 8 | 2-16 | 1 | no_move_measure (S-512); re-measured 7 | use_no_move_reduction (on) |
| 37 | LmrDivisorTenths | reductions | 45 | 23-90 | 3 | reasoning (anchors): **placeholder** | use_lmr (FR decision 4 still open: LTC or STC) |
| 38 | LmrHistoryPerPly | reductions | 10000 | 5000-20000 | 750 | natural value; STC +8.04, LTC +6.21; LTC class by the owner (11-13) | use_centred_lmr_history (on) |
| 39 | CaptureProbeMinDepth | pruning (ProbCut) | 9 | 4-18 | 1 | tier2_measure on S512r2 (11-06), not re-measured | use_capture_probe (on; FRR's LTC **priority switch**) |
| 40 | CaptureProbeReduction | pruning | 5 | 2-10 | 1 | same | same |
| 41 | CaptureProbeMargin | pruning | 80 | 60-200 | 6 | same; range widened 11-13 | same |

### 1.3 Out of the retune (16)

| parameter(s) | why out |
|---|---|
| IterationGrowthThirds, ForcedMoveFraction, AssumedMovesLeft, MaxMovesToGo, HardOverSoft, ReserveDivisor, DangerZoneOverheads | **time management, class (c), by rule** (2026-11-07 decision 4). spsa.py `EXCLUDED_PARAMS` refuses exactly these 7 by name. Ratio-100 STC/LTC cannot see TCEC's allocation; they belong to Phase 5 (idea 23 is placed after the retune: §6, 2026-11-14). The TimeScale set (time_budget.cpp:94-117) is not in the table and is out by the same rule. |
| TableProbeMinDepth | FR §2: it depends on TCEC's 7-man tables and I/O; Phase 8. |
| StaleDepthPerSearch | its switch `tt_age_blend` is off; TT policy is tested at a pressure-matched Hash (decision 23). |
| HistoryBonusFactor | **inert**: not read while `use_linear_bonus` is on (quiet_history.hpp:57-68; FR §3.1 proposes leaving it out). |
| LmrCorrectionStrength | **inert**: it scales `lmr_correction()`, whose committed body returns 0 (lmr_table.hpp:182-187; searcher.cpp:869-870). FR §3.1 still lists it in class (a); tuning it is a null dimension that costs about 0.17 Elo (B7 O2 rule 7). Idea 23 comes after the retune. |
| DriftWeightCap, DriftWeightTotal | the learning rate, left to E5 (FR §3.1; constants table). |
| PieceDriftShare, MajorDriftShare, ThreatDriftShare | their switches are off (searcher.hpp:314-317). |
| the eval scale S | class (d): a degenerate direction, and not a table parameter (FR §2). |

### 1.4 Constants of adopted features that are not in params.hpp

| constant (file) | value | status | needed before tuning? |
|---|---|---|---|
| LmrCheckRelief (searcher.cpp:99) | 1 ply | a "minimal unit" in whole plies; LMR has summed in 64ths since R20 | only if the owner wants it tuned: a new 64ths parameter |
| CutNodeLmrPlies, LmrNotImprovingPlies in 64ths | 64 at default | today whole plies, range 0-3 | **recommended** if they are to be tuned at all: bench-neutral at 64, names to screen; else freeze them |
| HistoryKeepQuarters in eighths, LmpImprovingEighths in sixteenths, QuiesceMoveCap | — | FR's open "finer unit" decisions | owner's choice; at c = 1 each is a two- or three-point search |
| HorizonDropMargin, HorizonDropMaxDepth, BadCaptureStopMargin | — | **not built** (owner 2026-11-10: dimensions of the final retune) | code, switches, off-equivalent ranges and name and constant screens before step 19, or drop them |
| R24's optional parametrisations (margin shapes, multiplier, malus ratio) | — | FR decision 6, open | owner |
| Singular extension +1, negative extension −1, singular test depth d/2, null depth d/2 − 1, improving's ply-2/ply-4 comparison, the aspiration widening rule | units and forms | definitions (constants table) | no |
| HistoryCentre::Shift 10, LmrFineUnit 64, DriftSlotBits 15, DriftGrain 128, DriftShareUnit 64, HistoryMax 10000, MVV-LVA ×8, EvasionCaptureBase, TT CurrentSearchBonus 256 (trans_table.cpp:55) | — | structural, units or TT policy | no |
| Lazy SMP v1 | none | "No new search constant" (§5.6 step 17a) | no |
| Future adoptions (rare-ideas queue 200-202, 2026-11-15) | — | each would add its constant to its group under the 11-11 rule | as they pass |

## 2. The sensitivity screen

**Goal and rule.** The screen decides *which* constants enter a group, never a value: games decide, which is
consistent with the 2026-11-12 rule. Offline proxies (spsa_calibrate's firing counts) only set the perturbation
size c, which is a tuner setting like a range (owner to confirm: §6 Q3).

**What it should measure.** The Elo a retune can recover from parameter i is about its slope there. Under a
local quadratic model E(x) = E* − ½h(x − x*)², the secant D_i = E(θ + c) − E(θ − c) = −2hc(θ − x*), and the
recoverable Elo is D_i²/(16w), where w = ½hc² is the Elo cost of a ±c perturbation at the optimum (my
derivation; B7 O2 rule 2 aims c at w ≈ 1 Elo). So D_i is the screening quantity. A parameter already at its
optimum shows D = 0 and correctly needs no retune. Its curvature is not measured; that is affordable only at
far more games (below).

### 2.1 Design S1 (recommended): a zero-gain SPSA, the random-balance fold-over screen

- **Play.** Each pair plays θ + c_scr·s against θ − c_scr·s, with Rademacher signs drawn per pair and θ held at
  the defaults (no update). This is spsa.yml/spsa_shard.py exactly, with the update switched off, so the
  per-pair option plumbing exists and the factorial per-shard rows are not needed.
- **Estimate.** D̂_i = (mean of r_j s_ij) / k, with k = ln 10 / 1600 = 0.001439 score per Elo at equality
  (spsa.py `SCORE_PER_ELO`). Var(D̂_i) ≈ σ²/(k²N), with σ the pair-score SD and N the pairs. Two properties of
  the fold-over (my derivation): for a quadratic E, two-factor interactions cancel in θ + cs against θ − cs, so
  main effects are free of them; and the other parameters add variance k²ΣD_j², about 5% of σ² even with 40
  parameters at D = 5 Elo. So **all 32 go in one run at the same per-parameter SE**. The 9 class (b) parameters
  can ride along as a diagnostic only (they are tuned at LTC whatever they show).
- **Perturbation.** c_scr = min(2c, distance to the nearer bound) per parameter, where c is spsa_calibrate's
  value or the fallback in §3.2. For a quadratic, D(2c) = 2·D(c) exactly, so z doubles and the games needed for
  a given z fall by 4 (my derivation). A parameter with no room for 2c (QuiesceMoveCap, LmpImprovingEighths,
  CutNodeLmrPlies, LmrNotImprovingPlies: one step from a bound) is screened at its room, at half the power.
- **Size: 8 STC stages, 6,400 pairs, 12,800 games.** σ = 0.2037, the median pair SD over 91 STC SPRTs
  (computed from each driver log's last pentanomial with at least 800 pairs; range 0.183-0.223). SE(D) at c_scr
  is 0.2037/(0.001439·√6400) = 1.77 Elo, which is **0.885 Elo in c-units**. That equals 32 stages at c.
- **Decision map** (z = D̂/SE in c-units):

  | z | class | action |
  |---|---|---|
  | \|z\| ≥ 2 | important | joins its group |
  | 1 ≤ \|z\| < 2 | ambiguous | joins if it is a never-measured placeholder (§1.1) or its group is under 6 parameters; else frozen |
  | \|z\| < 1 | flat | frozen at its default for this retune (logged "screened flat", with D̂ ± SE) |

  P(\|z\| ≥ 2) at a true D (c-units) of 0 / 1.5 / 2.5 / 2.8 / 4 Elo is **0.05 / 0.38 / 0.80 / 0.88 / 0.99**
  (normal approximation, my arithmetic). At w = 1, D = 2.8 is about 0.5 Elo recoverable (B7 O2 rule 7's
  inclusion bar), and D = 4 is about 1.0. With 32 flat parameters about 1.6 false positives are expected; each
  costs about 0.17 Elo of dilution (O2 rule 7), which is cheaper than missing a real one.
- **Fork's own evidence that it separates.** R14's per-iteration z (iterations.jsonl, 13 iterations × 800
  pairs, θ moving) pooled to −14.96 for RfpMargin, −6.33 LmpQuietAllowance, −4.12 FutilityGrowth, −2.23
  FutilityOffset, and +0.29 / +0.80 / +0.85 for AspirationHalfWidth / CaptureSeeFloor / NullSurplusPerPly.
  The first four are exactly the parameters that moved or pinned, and the last three moved at most 0.65c
  (report.txt).
- **Cost:** 8 stages × 18 min = **2.4 lane-hours** on one lane (§5.1).
- **Engineering:** a `screen` mode in spsa.py (no update; report D̂, SE and z per parameter in c-units, and
  c_scr) plus its test with the fake shard; per-parameter `c_screen` in the spec. About half a day. Names to
  screen.

### 2.2 Design S2 (alternative): Plackett-Burman over the factorial round's per-shard rows

This uses step 18's tooling (per-shard rows, row permutation, WLS fit; FRR §3) with a two-level PB design.
For 32 parameters the next PB size is 36 rows, with fold-over to 72 runs, so it needs 5 stages per replicate,
since a stage holds 16 rows. Per game it has the same efficiency as S1 (both are orthogonal two-level
designs), with exact orthogonality instead of random. The costs: it needs the factorial kind and fit, and each
shard is one configuration, so runner heterogeneity (FRR fix 2) is averaged over 16 rows rather than over
800 pairs. **Choose S2 only if the owner wants one design system for steps 18 and 19.** It is the same 8
stages for the same SE.

### 2.3 Rejected

- **One at a time** (θ + c against θ − c per parameter): the same SE per parameter costs 32 times the games
  (256 stages for SE 0.885).
- **A curvature screen** (each side perturbing a random half against the default, a three-level design): the
  per-parameter curvature SE at 12,800 pairs is about 2.5 Elo (indicator variance ¼; my arithmetic), too coarse
  to measure a w of about 1 Elo.
- **An LTC screen:** an LTC game costs 4.27 times an STC game (§5.1), and the LTC group (9) is small enough to
  tune whole.

## 3. Groups, SPSA settings and order

### 3.1 Groups (after the screen; candidates shown)

| group | tc | candidates | why together |
|---|---|---|---|
| **G1a eval-margin pruning** | STC | RfpMaxDepth, RfpMargin, FutilityMaxDepth, FutilityOffset, FutilityGrowth, NullMinDepth, NullSurplusPerPly, NullSurplusPliesMax (8) | margins in the eval's cp against the pruning eval; R14 tuned them together; all eval-scale dependent |
| **G1b move-count and SEE pruning** | STC | LmpMaxDepth, LmpQuietAllowance, LmpImprovingEighths, SeePruneMaxDepth, QuietSeeFloor, CaptureSeeFloor, QuiesceMoveCap (7) | move-loop and horizon counts and SEE bars |
| **G2 reductions (STC)** | STC | LmrMinDepth, LmrMinMove, CutNodeLmrPlies, LmrNotImprovingPlies (4) | LMR's non-divisor terms (FR §2); the last two only if converted to 64ths, else frozen |
| **G3 history and ordering** | STC | HistoryBonusCap, LinearBonusPerPly, HistoryKeepQuarters, ReplyWeight, FollowWeight, TakeWeight, DirectCheckBonus, HistorySkipPerPly, HistorySkipMaxDepth (9) | **the history skip goes here, not with pruning**: its threshold is on `quiet_order_score`'s scale (searcher.cpp:766-767), which the weights and the check bonus set |
| **G4 correction + window** | STC | MinorDriftShare, DriftLimit, AspirationMinDepth, AspirationHalfWidth (4) | the drift term changes the scores whose iteration-to-iteration swings set the window (the audit: NNUE swings 2.4 times the bootstrap's) |
| **G5 LTC group (class b)** | LTC 40+0.4 | Singular×3, NoMoveReduceMinDepth, LmrDivisorTenths, LmrHistoryPerPly, CaptureProbe×3 (9) | depth-scaling constants (FR §2); option: G5a = singular×3 + IIR (4) and G5b = LMR divisor + LMR history + ProbCut×3 (5), one per lane |

Rules: a group left with fewer than 3 parameters after the screen merges with its neighbour (G2 with G4, G1a
with G1b). A parameter of a switch removed in step 18 is dropped (e.g. LMP's three and aspiration's two).
Time management stays out by rule (spsa.py refuses it).

### 3.2 SPSA settings (method; spsa.py's rules as in R14, nothing copied)

- **c:** spsa_calibrate.py's rule (θ ± c moves the rule's bench firing count by 10%). **It covers only 8
  parameters** (`COUNTER_FOR_PARAM`: RfpMargin, FutilityOffset, FutilityGrowth, NullSurplusPerPly,
  AspirationHalfWidth, QuietSeeFloor, CaptureSeeFloor, LmpQuietAllowance). For the other 33, either add
  FORK_SEARCH_STATS counters (code, bench-neutral) or use a declared fallback: c = 1 for whole-unit integers
  (depth limits, counts, quarters) and 2 table steps for margins and weights. This is an owner choice; the
  fallback is a placeholder. Every c must be at least 1 (spsa.py refuses less), with start ± c inside the
  bounds.
- **a:** gain_end = 16·ε·k/(p·σ²), from the stationary-loss budget ε (spsa.py `gain_end`). R14 used ε = 0.5 Elo
  and passed (+37.93 ± 10.03 STC). With **ε = 0.5 per group** each group's gain grows as 1/p_g, and the total
  pairs are about what one combined run would need. The summed stationary budget is then 0.5 Elo per group
  (about 2.5 for five STC groups), reduced in practice by the mean over the last 30% (B7 O2 rule 9). Splitting
  ε by p_g instead would keep the single-run gain but multiply the pairs by the number of groups. Owner
  decision (§6 Q4).
- **A:** 10% of the run's pairs (Spall 1998 §III-B as cited in spsa.py; spsa.py enforces it as the maximum,
  and R14 used 1,040 of 10,400). α = 0.602, c fixed (`c_decay` 0), each step clamped to 0.5c, θ at least c
  inside the bounds, integers by stochastic rounding.
- **σ (`pair_sd`):** STC 0.204, the median of the 91 SPRTs above (R14's spec used 0.21). LTC 0.1845, the median
  of 14 LTC SPRTs (range 0.180-0.189; FR estimated 0.19-0.20 from two).
- **Iterations:** iter_g = max(8, ⌈1.9·p_g⌉) at STC (800 pairs each). The 1.9 is R14's ratio (13 iterations
  for 7 parameters, about 1,486 pairs per parameter, in which the sloped parameters travelled about 1.7-2.6c).
  Gain ∝ 1/p, so the travel per pair falls with p and the pairs needed scale with p. At LTC (832 pairs per
  iteration) the same travel needs (0.2037/0.1845)² = 1.22 times fewer pairs at equal effect, so
  iter = max(6, ⌈1.9·p/1.22⌉). FR's cheaper ratio (about 900 pairs per parameter) is the lower variant in §5.
- **Openings:** the tuning reserve. R14 ended at line 2,010,400, so 621,636 pairs remain. The whole plan uses
  at most about 69,000 (6,400 screen + 51,200 STC + 11,648 LTC), with each spec's `opening_reserve` set past
  the previous run.
- **Reports:** spsa.py's step-limited and pinned-at-bound flags. A pinned whole-ply limit goes to a
  head-to-head (FR §3.1).

### 3.3 Order and interaction checks

1. **Wave 0:** the screen (lane A).
2. **Wave 1, two lanes in parallel from the post-screen engine:** G1a (lane A) and G3 (lane B). They have the
   largest priors: R14's pins and the never-measured depth limits; the ordering group sets the history
   skip's scale.
3. **Wave 2, from wave 1's values:** G1b (lane A) and G2 + G4 (lane B). G1b follows G1a because futility and
   LMP prune the same late quiets (the redundant pair noted in FRR §2).
4. **STC validation:** an SPRT of the whole STC-tuned set against the untuned engine (design R [0, 6], cap 8,
   fresh openings; FR decision 5 still open) and, in parallel on the other lane, FR's LTC sign guard (3
   stages, nElo > 0). **R24's kill:** an STC H0 skips the LTC pass. On an H0, locate it with per-group SPRTs
   (2-8 stages each) and revert the failing group, under the two-try rule.
5. **G5 at LTC** on the STC-tuned engine (one lane, or G5a and G5b on two lanes), then its LTC SPRT against
   the STC-tuned engine (design R, cap 4-6).
6. **VLTC spot check** (FR §5 item 4): the final engine against the engine entering step 19, at 120+1.2 for 2
   stages, passing if nElo ≥ −3.
7. Commit: tuned values as defaults, bench updated, **constant screen before the commit**, constants-table rows
   citing the SPSA logs and SPRTs.

Interactions *within* a group are what SPSA estimates jointly. *Across* groups they are handled by the waves
(each later wave starts from the earlier values) and checked by step 4's combined SPRT, which tests the joint
set against the untuned engine. Step 6 checks depth scaling.

## 4. RSPSA for Fork's driver

**Source opened:** L. Kocsis and Cs. Szepesvári, "Universal parameter optimisation in games based on SPSA",
*Machine Learning* 63:249-286, 2006, DOI 10.1007/s10994-006-6888-8
(https://www.jhuapl.edu/spsa/PDF-SPSA/Kocsis_Szepesvari_MachineLearning06.pdf). Its text was read through a
crude local text extraction, so ligatures in the quotes may differ. The issue number (3) comes from the search
index (dblp, via a search snippet) and is **UNVERIFIED**. The conference version (Kocsis, Szepesvári and
Winands, "RSPSA: Enhanced Parameter Optimization in Games", DOI 10.1007/11922155_4) was **not opened**: its
venue is UNVERIFIED (Springer redirected to a login). Spall 1992 (IEEE TAC 37(3), DOI 10.1109/9.119632) and
Spall 1998 (IEEE TAES 34(3), DOI 10.1109/7.705889) are cited as spsa.py cites them and were not re-opened
here. OpenBench and fishtest SPSA pages were not consulted.

**What it changes (paper §3.2).** RSPSA feeds SPSA's gradient estimate into iRPROP−. Each parameter has its own
step Δ_i, and the update is θ_i += Δ_i·sign(g_i), so the gradient's magnitude is ignored. Δ_i grows by a factor
η+ > 1 while the sign holds and shrinks by η− < 1 on a sign reversal, clamped to [Δ−, Δ+]. On a reversal the
gradient term is zeroed for that step. The authors drop iRPROP+'s backtracking because "if the objective
function is observed in noise then the utility of blocking will be limited". The optional *coupling* sets the
perturbation size c_i = ρ·Δ_i, so the perturbations shrink where the steps do. The paper bounds the sign error
by Markov's inequality, P(sign wrong) ≤ M/G² (the estimate's mean square error over the squared slope), so
"the performance of RSPSA will be bound by the mean square error".

**Evidence of benefit in games (paper §5).**
- Poker (MCRAISE) opponent model, 6 parameters: RSPSA reached +0.170 sb/h against +0.095 for RFDSA. Batches
  were 40 perturbations × 2 × 250 games per iteration (Table 1).
- Plain SPSA "with no enhancements failed to make progress using the allocated resources". For the
  evaluation-function and policy tasks, "no parameter settings were found using which SPSA could produce
  acceptable results".
- The comparison is RSPSA *with* common random numbers, antithetic dealing and sample reuse against
  unenhanced SPSA, so the RPROP part's own share is not isolated.
- On the synthetic task, performance "gets worse faster than for SPSA as the batch-size is decreased".
- A Lines of Action use (Kocsis 2005) is cited in the conclusions; **not opened, UNVERIFIED**. The paper has no
  chess experiment.

**Fork's own data on the sign signal** (R14, ~/fork-spsa/github/spsa-r14-m2/iterations.jsonl, 800 pairs per
iteration, the per-iteration z that spsa.py logs):
- **Strong slopes never reversed:** RfpMargin 0 of 12 consecutive pairs, LmpQuietAllowance 0 of 12. RPROP
  would have grown their steps, but both were stopped by **bounds**, not by step size: RfpMargin sat at its
  floor from iteration 4 (report.txt). So growth would have bought nothing that the widened ranges do not.
- **Moderate slopes reversed often:** FutilityGrowth 5 of 12 (pooled z −4.12), FutilityOffset 5 of 12 (pooled
  −2.23). With η+ = 1.1 and η− = 0.85, one of the paper's own Table 1 settings, the step shrinks whenever the
  reversal rate exceeds ln 1.1 / (ln 1.1 + ln(1/0.85)) = 0.37 (my arithmetic). Both observed rates (0.42) would
  have *shrunk* the steps of real, still-falling parameters.
- **Flat parameters** reversed 5-7 of 12, close to a coin's 0.5. Their steps would collapse, which is the useful
  effect, but the screen (§2) delivers it before the run by not tuning them.

**Risks for Fork.**
1. **The noisy objective.** At 800 pairs, sign reliability is Φ(mean per-iteration z) ≈ 0.87 even for
   FutilityGrowth. RSPSA would need much larger batches, the paper's lesson, which means fewer updates in a
   fixed budget.
2. **Step collapse**, and with coupling, c below 1 table step for integers. spsa.py refuses c < 1, so the
   coupling cannot follow below it.
3. **Too few iterations to adapt.** At η+ = 1.1 a step needs ln 2 / ln 1.1 ≈ 7.3 agreeing iterations to double.
   The groups run 8-23 STC iterations and 6-14 at LTC.
4. **The loss-budget rule no longer applies.** Fork's gain comes from a stationary-loss budget (B7 O2). A
   sign-based step has no such calibration, so Δ−, Δ+ and Δ0 become new hand-set tuner constants, which also
   need names and constant screens.

**Implementation cost.** In spsa.py: per-parameter Δ and the previous sign in state.json (and restored by
`rewind`), the sign update in `iteration_step`, spec options for η±, Δ bounds, Δ0 and the coupling ρ, report
lines and tests (test_spsa.py, the fake shard). About 1-2 days with tests, plus name screens. No workflow
change.

**Recommendation: reject for the final retune's runs; keep idea 150 open with an offline pilot only.**
- **The pilot:** a local simulation of both update rules on a synthetic quadratic Elo surface. Inputs are
  Fork's measured noise (σ 0.204 STC, 0.1845 LTC), 800 or 832 pairs per iteration, the group sizes and
  iteration counts of §3, and a mix of slopes matching R14's pooled z. It compares the mean final loss and the
  pin rate over a few hundred seeds. It costs minutes of CPU and decides only the *driver method*, never a
  constant.
- **The gate:** a GitHub pilot (two runs on one small group, then an SPRT of their results, about 6-8
  lane-hours) only if RSPSA's simulated final loss is at least 30% below SPSA's (a placeholder bar) at Fork's
  iteration counts.
- **Why not more now:** the two mechanisms RSPSA would add are already covered. Freezing flat parameters is
  the screen's job, and the room for strong slopes comes from the widened bounds and the pinned flag.

## 5. Cost

### 5.1 Measured throughput (one lane = one 16-shard run at a time)

- **STC:** median **18 min** dispatch-to-merge per 1,600-game stage (n = 295 stages since 2026-11-11; p25-p75
  18-19, max 32), from the timestamps in ~/fork-data/sprt/*/driver.log (design.json `tc` 8+0.08). R14's SPSA
  iterations: mean **16.78 min** (16.47-17.30, 13 iterations, `wall_minutes`), 95.4 games per minute. The
  plan uses 18 min per 1,600 games (11.25 lane-min per 1,000 games).
- **LTC:** median **80 min** per 1,664-game stage (n = 39 since 11-11; p25-p75 79-81, range 78-86), which is
  48.1 lane-min per 1,000 games. **An LTC game costs 4.27 STC games.** No LTC SPSA has run, so its iteration
  time is assumed equal to an LTC stage (UNVERIFIED).
- **Lanes:** sprt_run.sh admits a stage when the other runs leave room for its 16 shard jobs plus a build job
  within `FORK_GH_JOBS` (default **40** since the owner's Pro note of 2026-11-11, sprt_run.sh:55 and :144).
  17 × 2 = 34, so two lanes. (A memory note of 2026-11-11 still says 20; the driver's 40 is the newer record.)
  A lane-hour is about 16 runner-hours.

### 5.2 Per part (E = expected: the screen keeps about half, small groups merged; U = upper: every candidate kept)

| part | params | iterations / stages | games | lane-hours |
|---|---|---|---|---|
| screen S1 | 32 (+9 diagnostic) | 8 STC stages | 12,800 | 2.4 |
| G1a | E 5 / U 8 | 10 / 16 | 16,000 / 25,600 | 3.0 / 4.8 |
| G1b | E 4 / U 7 | 8 / 14 | 12,800 / 22,400 | 2.4 / 4.2 |
| G3 | E 5 / U 9 | 10 / 18 | 16,000 / 28,800 | 3.0 / 5.4 |
| G2 + G4 (E merged) / G2, G4 (U) | E 4 / U 4 + 4 | 8 / 8 + 8 | 12,800 / 25,600 | 2.4 / 4.8 |
| **STC groups total** | E 18 / U 32 | 36 / 64 | 57,600 / 102,400 | **10.8 / 19.2** |
| STC validation SPRT (design R, cap 8, futility look at 2) | | 2-8 stages | 3,200-12,800 | 0.6-2.4 |
| LTC sign guard | | 3 LTC stages | 4,992 | 4.0 |
| G5 LTC, one group (R14 ratio) | 9 | 14 | 23,296 | 18.7 |
| G5 LTC, FR's cheaper ratio (variant) | 9 | 9 | 14,976 | 12.0 |
| G5 split G5a (4) + G5b (5), floor 6 | 4 + 5 | 7 + 8 | 24,960 | 9.3 + 10.7 = 20.0 |
| LTC validation SPRT (design R, cap 4-6) | | 2-6 LTC stages | 3,328-9,984 | 2.7-8.0 |
| VLTC spot check, 2 stages at 120+1.2 | | 2 | 3,200-3,328 | about 8 (UNVERIFIED: about 3 LTC stages each, FR §5) |

**Totals.**
- **Expected:** 2.4 + 10.8 + 0.6-2.4 + 4.0 + 18.7 + 2.7-8.0 + 8 = **47-54 lane-hours**, about 120,000 games.
- **Upper:** 2.4 + 19.2 + 2.4 + 4.0 + 18.7 + 8.0 + 8 = **about 63 lane-hours**, about 170,000 games.
- **With FR's cheaper LTC ratio:** subtract 6.7 h from either total.
- **A per-group bisection** after an STC H0 would add 0.6-2.4 h per group tested.

### 5.3 Critical path on two lanes (expected case; upper case in brackets)

| step | lane A | lane B | wall h |
|---|---|---|---|
| wave 0 | screen | (free) | 2.4 |
| wave 1 | G1a | G3 | 3.0 [5.4] |
| wave 2 | G1b | G2 + G4 | 2.4 [4.8] |
| STC validation | STC SPRT | LTC sign guard | 4.0 |
| LTC pass | G5a | G5b | 10.7 (a single G5: 18.7) |
| final checks | LTC SPRT | VLTC (run speculatively beside it; wasted if the LTC SPRT fails) | 8.0 |
| **total** | | | **about 30.5 [35.3]; 38.5 [43.3] with a single-lane G5** |

The wall times assume both lanes are free. Network screens and promotions take priority over search items and
may take both lanes (owner, 2026-11-14), so calendar time is UNVERIFIED.

### 5.4 What must finish first

1. **Lazy SMP step 17a's pending tests** (DESIGN §6, 2026-11-15, and §5.6 step 17a's scaling plan):
   - the one-thread cost on GitHub runners (speed-ab.yml, run 43774753294);
   - sprt.yml's `concurrency` input (its edits and run_shard.sh's are uncommitted in this working tree);
   - the nps and time-to-depth curve at 1 and 2 threads, then 2-vs-1 matches at STC and LTC, and the
     thread-versus-time check;
   - the TSan suites with `smp`;
   - 4-vs-2 only on the PC or rented hardware, which is not on the retune's path.

   The retune runs at Threads = 1, the old path (bench unchanged at 5,205,904), so it needs Lazy SMP adopted
   and its one-thread speed settled, not the multi-thread results.
2. **Step 18, the removal round** (FRR: 21-43 STC stages plus the LTC guard for the ProbCut priority switch).
   Its removals delete parameters from §1 (LMP's three, aspiration's two, ProbCut's three).
3. **The network for TCEC** (§6 Q1). The eval-margin group G1a and the correction group are eval-scale
   dependent. A net promoted after the retune would make them stale again, as the audit found for every
   pre-11-11 constant.
4. **Tooling** (none built):
   - port tune/spsa-pinned onto phase-4's head. spsa.yml must match sprt.yml's current conditions: the
     complete-shard rule and the new concurrency input;
   - **spsa_run.sh still dispatches only when no run of any workflow is queued or in progress**
     (spsa_run.sh:31), so it blocks the second lane and is blocked by it. It needs sprt_run.sh's
     `FORK_GH_JOBS` capacity rule;
   - jobctl's docstring says one `github` job at a time; how two lanes are admitted is UNVERIFIED here;
   - the screen mode (§2.1);
   - firing counters or the fallback c (§3.2);
   - the 64ths units and the batch-4 dimensions, if wanted (§1.4).

   About 2-3 days, with tests.

## 6. Open questions for the owner

1. **Freeze the default network before step 19?** The next network bet, the sparse int8 head (§6,
   2026-11-15), is the risk to the eval-dependent groups. Otherwise re-run G1a and G4 after any later
   promotion.
2. Approve screen S1 (8 STC stages at c_scr = min(2c, room), the decision map of §2.1) or S2.
3. c for the 33 parameters without firing counters: add counters, or the declared fallback (1 unit for
   integers, 2 table steps for margins)? Is calibrating c from firing counts acceptable under the 2026-11-12
   rule? It sets a tuner setting, not a value.
4. ε per group: 0.5 Elo each (R14's validated setting; the totals above assume it) or ε split by p_g (more
   games).
5. CutNodeLmrPlies and LmrNotImprovingPlies (and LmrCheckRelief): convert to 64ths parameters, or freeze? The
   finer units for HistoryKeepQuarters, LmpImprovingEighths and QuiesceMoveCap (FR's open items).
6. Confirm HistoryBonusFactor and LmrCorrectionStrength out (inert), and CutNodeLmrPlies in (it is missing
   from FR §3).
7. Still open from FR §8: LmrDivisorTenths at LTC or STC (decision 4); the validation design (decision 5); the
   R24 extra dimensions (decision 6), including whether batch 4's razoring and bad-capture dimensions are built
   before step 19 or dropped.
8. G5 as one LTC group (18.7 h on one lane) or split over two lanes (about 10.7 h wall, 20 lane-h)?
9. Run the VLTC check beside the LTC SPRT (saves about 8 h of wall time, wasted on an LTC fail)?
10. HistoryKeepQuarters: an LTC check of its STC value (FR §3.1)?
11. The VLTC check at one thread per engine (as planned) or two? Whether class (a) optima hold at TCEC's thread
    counts is UNVERIFIED.

## 7. UNVERIFIED

- The mapping from D to recoverable Elo assumes a local quadratic and w ≈ 1 Elo at the calibrated c. c comes
  from a firing-count proxy whose Elo cost is unmeasured.
- D(2c) = 2·D(c) holds only for quadratic shapes. Cliffs (bounds, margins near the eval's noise) distort the
  screen.
- The iteration rule ⌈1.9·p⌉ extrapolates from one run (R14). The LTC 1.22 factor assumes equal Elo effects at
  LTC.
- An LTC SPSA iteration's time is assumed equal to an LTC SPRT stage (80 min). VLTC stage time (about 4 h) and
  sprt.yml's 300-minute shard limit (FR §5).
- Lane availability (network priority), FORK_GH_JOBS 40 against the older memory note of 20, and how jobctl
  admits two GitHub lanes.
- RSPSA: the journal issue number, the conference version's venue, and Kocsis 2005 (Lines of Action) were not
  opened. Quotes come from a crude PDF text extraction. Spall 1992/1998 are as cited in spsa.py, not re-read.
- Whether STC/LTC optima at Threads = 1 transfer to TCEC's thread count and hash.
- Whether the batch-4 dimensions and the rare-ideas items (200-202) will exist by step 19.
- The drift constants' fitness for the minor key (constants table, already marked UNVERIFIED).
