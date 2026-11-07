# Phase A synthesis: verification, models and ranked bottlenecks (Phase 4 think tank)

**Summary.** I checked the three analysts' most load-bearing claims against
the repo, the trainer, the SPRT tooling and the Kaggle run records. Most of
them hold. Three need correcting, and the corrections change some
priorities.

- **The speed-to-Elo rate is solid:** 106 Elo per doubling of nps at STC,
  or 1.53 Elo per 1%. The 95% band is 88-124 per doubling (1.26-1.80 per
  1%) once the fit's overdispersion is allowed for. A1's "good fit" and
  its "S512+X is a 1.7σ outlier" both come from using 95% bars as σ. The
  true χ² is 24.5 on 7 dof, and S512+X sits 3.3σ off the line.
- **A3's SPRT power figure is right.** A true +3 Elo (+5 nElo) passes
  [0, 3] under the 13-stage cap 18-25% of the time analytically, and 20.5%
  in my simulation.
- **A1's two training mechanisms are only partly right.** The facts hold:
  there is no Adam bias correction, warm starts begin with fresh moments,
  and no run before g3s2 interleaved its shards. The causal claims do not.
  A learning rate of 1e-3 drives a scratch run to the same 0.0200-0.0211
  band that a warm start at 1e-3 jumps to, so the LR alone explains the
  spike. The "10x seed spread" is a warm-start effect, not an
  interleaving effect: interleaved scratch runs spread 8.2e-5, more than
  the non-interleaved S512 r2's 3.8e-5.
- **A3's time-odds trap is real, but its cause is not the Move Overhead.**
  Fork takes the overhead off the clock once, not off each move. The skew
  comes from fixed per-move latency in the increment-bound phase.

Across the whole engine the evidence ranks the bottlenecks as follows:

1. search constants never refit on the network (no SPSA since the
   bootstrap evaluator);
2. undertrained networks (low-LR compute per run, best-of-360 selection);
3. static time management, which no current Fork test can see in TCEC's
   shape;
4. the label-generation loop's throughput and age;
5. an SPRT design that spends most GitHub time on capped, undecided
   tests;
6. speed and the build regime (the TCEC binary is v3, with no PGO and no
   AVX-512 output layer);
7. an under-informed LMR with never-decayed histories;
8. the untuned training target (λ = 0.5).

SMP (Phase 6) outweighs all of these at TCEC. It is out of Phase 4's scope
and listed separately.

Conventions: A1/A2/A3 = the analyst reports (appended), cited by section.
S1/S2/S3 = the clean-room surveys in tank/b. SL = docs/history/phase-4/sprt-log.md;
DL = DESIGN.md §6; K = `~/fork-data/kaggle/<run>/`. My scripts are
in tank/a/scratch (fit.py, sprt.py, tm.py); they are read-only arithmetic on
logged numbers. **[V]** = verified by me against the primary file;
**[C]** = computed by me; **[I]** = my inference; UNVERIFIED as usual.

---

## 1. Verification verdicts

| # | Claim | Verdict | Evidence location |
|---|---|---|---|
| a | Speed-to-Elo: A1 152 ± 28 per e-fold; A3 106 ± 20 per doubling | **CONFIRMED** (point estimate and realistic band); **PARTLY** on A1's goodness of fit | SL 2026-10-31 stage B table (lines ~226-229), SL 2026-11-01 round 2 (~455-512, 566-576), SL 2026-11-05 S512+X (~667), SL 2026-11-06 S512+PP (~844-845); ratios DESIGN.md §5.4 line ~3196 and DL 2026-11-05/06; my fit.py |
| b | Trainer's AdamW lacks bias correction and restarts moments on a warm start | Facts **CONFIRMED**; "mechanically explains" the 1e-3 spike **PARTLY** (contributory, not necessary) | KB bullet-internals.md §5.4 ("no bias correction and no step counter"); tools/train/src/main.rs ~1189-1193 (`--init-weights`: "AdamW's moments fresh"), ~1162-1165 (`--resume` loads optimiser_state); K g3s2-out val.txt curves |
| c | LMR history term uses integer division by 24000 and fires only past ±24,000 | **CONFIRMED** | branch sprt/lmr-history: searcher.cpp `reduction_for(...) - order_score / LmrHistoryDivisor` (int/int); params.hpp `LmrHistoryDivisor 24000` (range 3000-24000); score = butterfly (±10,000, quiet_history.hpp HistoryMax) + reply×6/4 + follow×4/4, clamped to int16; bench 14,180,299 → 14,141,348 (SL 2026-11-05 lmrh) |
| d | Histories never decayed between moves | **CONFIRMED** (with one nuance) | searcher.hpp header ("the history persists between searches until clear_history()"); clear_history() called only at ucinewgame, Clear Hash and per bench position (session.cpp ~252, 267, 443; search_bench.cpp 122). Nuance: the update rule v + b − v·\|b\|/HistoryMax (quiet_history.hpp) is self-limiting, so values saturate softly and any opposite update pulls them back; "stale" is plausible, "frozen" is not |
| e | [0, 3], 13-stage cap: a true +3 Elo passes only ~21% | **CONFIRMED** | tools/cloud/sprt_merge.py (bounds in nElo, LLR normal approximation, n = pairs); sprt_run.sh `last=${7:-12}` (stages 0-12 = 13). Analytic: per-stage nElo SE 245.7/√800 = 8.69; LLR drift 0.0398·(θ − 1.5) per stage, sd 0.345; for θ = 5 nElo, P(above +2.944 at stage 13) = 0.18 (lower bound), continuous-barrier crossing 0.25 (upper bound); simulation 0.205 (sprt.py). +5 nElo ≈ +3 Elo needs Elo/nElo ≈ 0.6, which holds at STC (S512ppr2: 20.11 Elo = 33.60 nElo) |
| f | Pre-g3s2 runs lacked shard interleaving | Fact **CONFIRMED**; the "~10x seed spread" attribution **REFUTED** | `--interleave` added 2026-11-06 (commit 8bccd0b); only tools/train/kaggle/retrain_g3s2.py passes it (grep). Spread: interleaved g3s2 scratch seeds 8.2e-5 vs non-interleaved S512 r2 3.8e-5 (A1 §3.2's own numbers); the 1.2e-5 belongs to warm runs from identical weights |
| g | Time-odds design skewed because Move Overhead 100 ms > increment 80 ms | Premise **CONFIRMED**, mechanism **REFUTED**, conclusion (time odds bias R high; prefer a throttled build) **holds for a different reason** | session.cpp `add_spin("Move Overhead", 100, ...)`; run_shard.sh sets no overhead; time_budget.cpp subtracts the overhead once from the remaining clock (`available = remaining − overhead`), not from each increment. tm.py (simplified model: 1.3× soft spend): with zero latency the half-time engine gets 0.496 of the time (overhead 100) vs 0.499 (overhead 0). With 10 ms of real per-move latency: 0.463 overall and 0.39 after move 50; the overhead adds only 0.006 of that |

### 1.1 Notes on the verdicts

**(a) The speed fit [V][C].** I recomputed from the logged FN and STC
results with their 95% bars and the §5.4 ratios. The round-2 ratios are
re-based on S512r2 = 0.78 of B0: AF-S 0.56/0.78, XGR 0.50/0.78. The
weighted least-squares fit through the origin gives **R = 105.7 per
doubling (152 per e-fold), statistical 1σ = 5.0**. Three corrections to
the reports follow:

- **The χ² is 24.5 on 7 dof** (p ≈ 0.001), not A1's 6.4. A1 divided by
  the 95% half-widths as if they were σ, which shrinks χ² by 3.84. The
  model is overdispersed by about 1.9x in sd.
- **The honest band** scales the error by √(χ²/dof): 1σ = 9.4, so the
  95% band is **88-124 per doubling, 1.26-1.80 Elo per 1%**. A3's "±20"
  and A1's "±28 per e-fold" (= ±19 per doubling) both land here, by
  different routes. A3's "±9.9 statistical" is a 95% figure (1.96 × 5.0).
- **S512+X's residual is 3.3σ**, not 1.7σ. Without it, R = 102.4 and
  χ² = 13.2 on 6 dof (p = 0.04), so it is the main but not the only
  source of excess scatter. XGR r1 is the other large residual: +34 Elo
  above its leave-one-out prediction.

Leave-one-out predictions get all eight STC signs right. S512+X's is
marginal: predicted −4, observed −30. That confirms A3 §2.4's "8 of 8".
A1's fixed-rate χ² table keeps its ranking, but every value is 3.84x
larger: 0.9 per 1% gives 96, 2 per 1% gives 68, 3 per 1% gives 435.

Caveats, all from the reports, which I confirm:

- the round-1 ratios are loaded-machine bench nps;
- the FN and STC runs share openings, so their errors are correlated and
  the gap bars are conservative;
- FN 800k searches about 2 plies deeper than STC.

**(b) AdamW [V][C].** The step-size arithmetic is right: with no bias
correction, a steady gradient gives a step of
(1 − 0.9ᵗ)/√(1 − 0.999ᵗ) × LR, which is 3.2x at t = 1, 6.5x at t = 10,
3.2x at t = 100 and 1.26x at t = 1,000. One superbatch is 305 steps
(batch 16,384 × 305; retrain_g3s2.py header). But scratch runs at 1e-3
sit in the 0.0199-0.0218 band until superbatch 180 (K g3s2-out:
scratch-s1 0.01990 and scratch-s2 0.02051 at superbatch 180). A warm
start at 1e-3 jumps to 0.0207-0.0217, the same band, and stays there long
after the bias factor has decayed to about 1.0 (by superbatch 4). So the
1e-3 noise floor explains the destruction on its own. The missing bias
correction only makes the first superbatch worse.

The practical remedies are unchanged: never warm-start at 1e-3; use a
short warmup or resumed moments. Resuming moments is possible only for a
same-shape net, since `--resume` loads optimiser_state. A widened net
(new input rows) cannot resume the moments of rows it did not have.

One correction on noise: A1 §3.2 puts superbatch jitter at 1e-4 at
2-7e-5, but warm-s1 moved 1.4e-4 between superbatches 179 and 180, both
at 1e-4. So a single run's best loss is uncertain to about 1e-4, about 6-10 Elo
at A1's own exchange rate.

**(d) and (c) together [I].** With histories persisting and soft-saturating,
A2's hypothesis (O3) is mechanically plausible. Bench clears the history
per position, so a term that fires only at |score| ≥ 24,000 can be nearly
invisible on bench (0.27% of nodes) and frequent in games. It stays
unmeasured, and it is the cheapest open measurement (§7, M1). The branch
also computes `quiet_order_score` for every quiet move made when the
switch is on, not only for LMR candidates [V]. So A2's cost hypothesis is
real at the code level too. Its nps was never measured.

**(g) Time odds [V][C].** The bias that matters is any cost per move
that does not scale with the clock: process I/O and fastchess latency on
a shared 4-vCPU runner. It shrinks the slower side's usable time by
more than 2:1 in the increment-bound phase. A 2:1 time-odds match would
then estimate R from a true ratio of about 2.2:1. That inflates R by
roughly 10% (log₂(1/0.46) = 1.12 doublings), more if runner latency
exceeds 10 ms. My model is simplified (a constant 1.3× overspend, no hard
stops) and the latency is UNVERIFIED. The throttled build A3 §1.5
proposes avoids the issue entirely; so would recording each side's
actual mean time per move.

---

## 2. Executive summary

1. **The generational loop (labels from a stronger default) is the proven
   engine, and it is contracting.** A1's zero-dof fit gives b ≈ 0.3
   student Elo per labeller Elo [C, low confidence]. If that is right,
   any gain that improves the 20k-node labeller earns about
   b/(1 − b) ≈ +45% more through later generations. That includes search
   gains that survive at 20k nodes. Labels alone do not sustain growth.
   The loop amplifies gains made elsewhere [I, new here].
2. **The networks are undertrained, not data-starved.** At ≥ 0.4 B kept
   positions, validation loss is below training loss: about −0.0010 warm
   and −0.0008 scratch over superbatches 351-360, recomputed from K
   g3s2-out [V]. The scratch curves were still falling at 360, and the
   warm recipe's win is mostly accumulated low-LR compute (A1 §5.2d).
   This is the cheapest net lever: Kaggle hours, no data, no speed cost.
3. **Speed is priced at 1.5 Elo per 1% at STC** and about the same at LTC
   (one XGR point: 95 ± 22 per doubling, ratio to STC 0.90 ± 0.25). The
   gates cost 0.95 → 7.8 Elo, 0.90 → 16.1, 0.818 → 30.6. C4's +4%
   bought about +6, the size of a typical tier-2 feature.
4. **Every search failure since the network arrived was "trust the static
   eval more"; every win added information** (a search, an ordering
   signal, the node budget) (A2 §3.1). The eval-gated margins are still
   bootstrap-era values, and no SPSA has run on any network (A2 §1.4;
   S2 §4.1).
5. **Time management is static,** and Fork's test controls
   (base/increment = 100) cannot see TCEC's allocation problem
   (base/increment = 600) (A2 §4; S3 §1). Per-root node shares are
   already computed every iteration [V: searcher.cpp ~802-805].
6. **The testing machinery is the binding constraint for search work.**
   [0, 3] with a 13-stage cap passes a real +3 Elo feature about 21% of
   the time and confirms a neutral removal 5% of the time [V]. Search
   tests return about 0.8 Elo per GitHub stage against 12.5 for
   networks (A3 §2.7).
7. **Three pre-SPRT signals carry little or no information:** the
   label-and-sweep proxy (ρ = −0.3 against SPRT outcomes, n = 5; I
   re-derived it), raw FN for slower nets (2 of 7 signs), and validation
   loss across architectures. Three carry real information: the
   speed-adjusted FN screen (8 of 8, leave-one-out included) and the
   mechanism metrics (cutoff index, SE precision). Idea 23's funnel
   still uses the first.
8. **TCEC conditions are unrepresented by every Phase 4 test:** 1 thread
   against 512, a 16 MB TT against 256 GiB, g++ v3 shards against the
   clang-19 v3 TCEC build, no PGO, and 3-4-5 tables against 7-man (A3
   §1.6, S3). This is a known, scheduled gap, but it bounds how much any
   Phase 4 STC result means for TCEC.

---

## 3. Reconciliation

### 3.1 Between analysts

| Topic | A1 | A2 | A3 | Resolution |
|---|---|---|---|---|
| Speed rate | 152/e-fold "good fit" | 1-3 Elo per 1%, "~3" for nps-costly features (O8.2) | 106/doubling, χ² 24.5 | **1.53 per 1% (1.26-1.80).** A2's "~3" predates the fit; its nps arguments (LMR history cost, threat buckets) should be re-priced at 1.5 |
| Exchange rate at LTC | k_LTC 137 vs 146, "unlikely to flip" | IIR grew at LTC; XGR's penalty barely shrank | R_LTC 95 vs 101; "LTC candidate premise contradicted" | **The single LTC point cannot tell "no decline" from a Stockfish-like decline:** R_LTC/R_STC = 0.90 ± 0.25 includes S3's ~0.7 over a similar TC step. The practical conclusion still holds: at 0.7, S512+X projects to about +4 at LTC and AF-S to about −25, so neither is worth an LTC slot. The TCEC question (14 doublings) stays open (§6, item 6) |
| Seed noise of a net | idea-13 seeds −14.8 apart | n/a | "±10-15 Elo of seed luck" | **Overstated.** The three seed matches (−0.9, +3.3, −14.8, each ±12.3 at 95%) imply a per-net seed sd of about 4 Elo once match noise is removed [C], at the B0 scale where seeds matter most. Treat promotion SPRTs under +10 as possibly part seed luck, not under +15 |
| Validation loss | 6-10 Elo per 1e-4 within architecture | n/a | loss ranks recipes, not architectures | Agree. Add: a single run's best loss is uncertain to about 1e-4 (§1.1b), so within-architecture differences under about 1e-4 (≈ 6-10 Elo) are unresolved from one run |
| Interleaving | explains seed spread and part of +20.1 | n/a | n/a | Only "unattributable share of +20.1" survives (§1, f) |
| What to do with search GitHub time | n/a | O1-O8, batch 4 after O2 | power is low; futility stop; fixed-length estimates | Compatible. A2 ranks *what*, A3 prices *how*. Both imply fewer, larger search tests (TM, SPSA) beat many small ones |

### 3.2 Analysts against the surveys

- **Fractional depth (A2 O2 vs S2).** A2 ranks idea 43 second, as the
  enabler of continuous LMR terms. S2 §5 records it as worth about zero
  elsewhere: one engine removed it on a non-regression pass, another's
  versions failed STC and passed only at very long TC. The two reconcile
  on mechanism: what A2 needs is **sub-ply arithmetic inside the LMR
  formula** (compute the reduction in fixed point from base, history,
  node-type and check terms, then round once to plies), not fractional
  depth throughout the tree. That costs hours, not 2-3 days, and does not
  gate SPSA [I]. The full refactor can wait for evidence that sub-ply
  depth itself pays at LTC.
- **SPSA timing (plan item 12; S2 "first"; A2 O4; A3 #7).** Everyone
  agrees the retune is owed. The surveys put the first post-network SPSA
  in the family at roughly +10 to +20 at LTC (S2 §4.1: several engines'
  logged tests; priors only, with winner's curse). Fork has never run
  one. The plan's dependency "fractional depth must precede SPSA" is the
  only blocker, and §3.2's first point removes it. A2's error-quantile
  measurement (O4) is the right way to set SPSA's starting points and
  ranges.
- **Time management.** A2 O1, S2 finding 2 and S3 finding 3 agree:
  node-share is the strongest single dynamic term in the surveyed family.
  Its gains hold or grow at LTC, and Fork already has the counts. DESIGN
  puts full TM in Phase 5 (line ~765). Moving node-share forward is a
  plan change for the owner.
- **Speed at TCEC.** S3 (Stockfish wiki table, derived) puts Elo per
  doubling at long TC well below STC's. That would make eval quality
  relatively more valuable at TCEC than Fork's STC gate implies. Fork's
  own data cannot test this beyond 40+0.4. A fixed-node doubling ladder
  (S3 §C) is the only Fork-pure way to measure it (§7, M10).
- **Correction tables.** A2 O7 (pawn overlaps the links; try continuation
  or non-pawn) matches S2 finding 3: they pay as an ensemble, at LTC and
  with shared threads, and one material-keyed table was useless. Keep
  them deferred, but measure first with the cheap passive method.
- **Data practice.** A1 B2/B5 match S2 finding 4: purge or downweight old
  labels, upsample the newest, a WDL-heavier end of training, and endgame
  data added deliberately. S2's "WDL-heavier end" is independent support
  for A1's untuned λ (B4).
- **The orchestrator's notes** I checked: SMP is Phase 6 and TM is
  Phase 5 in DESIGN (line ~765, "Full time management is Phase 5").
  Data generation labels at a fixed node count (20k), so TM changes do
  not alter labels. The brief's "STC SPRT up to 12 stages" is 13 stages
  in sprt_run.sh (0-12).

---

## 4. Quantitative models Fork can plan with

All Elo is head-to-head self-play unless marked. Self-play may overstate
third-party gains by about 1.7x (A1 §2.2, two gauntlets on different
anchors, UNVERIFIED), so divide by 1.0-1.7 when projecting to a rating
list.

| Model | Estimate | Uncertainty (95%) | Basis | Main caveat |
|---|---|---|---|---|
| **Speed → Elo, STC** | 106 Elo per doubling of nps = **1.53 per 1%** (k = 152 per e-fold) | 88-124 per doubling; 1.26-1.80 per 1% | 8 FN/STC pairs, overdispersion-scaled (§1.1a) | round-1 ratios from a loaded machine; the FN depth effect may inflate R slightly |
| Speed → Elo, LTC | 95 per doubling | ±22 (one point) | XGR r2 FN +30.70, LTC −30.56 | n = 1; consistent with 0.65-1.15 of STC |
| Speed → Elo, TCEC | unknown; likely lower | — | S3 (external, derived) | needs a doubling ladder |
| Speed-gate prices (STC) | 0.95 → 7.8; 0.90 → 16.1; 0.895 → 16.9; 0.818 → 30.6; 0.195 → 250 | ±17% | R × log₂(1/r) | measured in the native X3D regime, not on runners (A3 §1.6) |
| **Speed-adjusted FN screen** | STC ≈ FN − 106·log₂(1/r) | residual RMSE ≈ 14 Elo | leave-one-out 8/8 signs | in-sample; reliable for ±20-50 effects, not ±5 |
| **Loss → Elo, same architecture** | 6-10 Elo per 1e-4 | ±50% | 2 clean pairs + 2 input families (A1 §3.1) | needs a shared validation set; single-run noise ≈ 1e-4 |
| Loss → Elo, across architectures | no usable relation | −10 to +40 per 1e-4 | A1 §3.1 | do not rank architectures by loss |
| Loss resolution of one run | ≈ 1e-4 (best-of-360 optimism plus jitter) | — | K curves (§1.1b) | use final and EMA losses on a larger validation set |
| **Data scaling** | ≈ 64 per doubling at 10-80 M kept; ≈ 30 at 0.1-0.4 B; 10-20 guessed at ~1 B | factor 2 | zero-dof fit (A1 §2.2) | confounded with labeller and compute |
| **Labeller → student** | b ≈ 0.3 student Elo per labeller Elo | 0.1-0.5 (guess) | zero-dof fit | implies loop amplification 1/(1 − b) ≈ 1.45 [C] |
| Effective data unit | games, not positions | — | idea 13 (+65.5 at 1.8x games) | shown at the 24 M scale only; weaker without overfitting |
| Data throughput | ≈ 1,000 kept positions/s on 10 threads ≈ 86 M/day; doubling g3s2's ~0.85 B kept takes ≈ 10 days | ±20% | A1 §8 (g3g rate) | the next doubling is worth only 10-20 Elo |
| Relabel vs fresh | relabel ≈ 1.7x cheaper per kept position, but renews only the score half | — | A1 §8 | fresh data also adds games (H1) |
| Label-noise test cost | 100k positions at 320k nodes ≈ 16 min at datagen's 34 M nodes/s, ≈ 80 min at 2 threads [C] | — | A1 §8 rates | cheap; see M7 |
| **Seed noise of a net** | per-net seed sd ≈ 4 Elo | 0-9 | 3 seed matches minus match noise [C] | B0-scale nets; n = 3 |
| **SPRT power, [0, 3] nElo, cap 13** | P(H1): +1.8 Elo 5%; +3.0 21%; +4.2 50%; +6.0 89%; neutral removal on [−3, 0] confirmed 5% | ±2 points (simulation) | §1, e | Elo/nElo ≈ 0.6 at STC |
| Cost per decision | 1 STC stage ≈ 18.5 min (1,600 games); a small-effect [0, 3] test ≈ 12.5-12.9 stages ≈ 4 h; LTC stage ≈ 75 min (UNVERIFIED) | — | A3 §2.1, 2.6 | a futility stop at stage 2 saves ≈ 40% (A3 table; Fork's stage-wise logs support it) |
| **Games per resolution** | STC ±2 Elo → 41k games; ±3 → 18k; ±5 → 6.6k. LTC ±3 → 15.8k (≈ 4.3x STC's cost per Elo) | — | pair sd 0.208-0.214 STC, 0.193-0.198 LTC (A3 §2.5) [C] | pentanomial; current era only |
| Return per GitHub stage | networks ≈ 12.5 Elo; search features ≈ 0.8 | descriptive | A3 §2.7 | ignores Kaggle and datagen days; networks pass in 1-2 stages because their effects are large |
| Winner's curse | 1-3-stage H1 estimates (+14 to +33) are biased up | — | A3 §2.7 | the final gauntlet is the check |
| TM overspend | mean finish ≈ 1.30x soft (growth g = 1.66: (g − 1)/ln g) | p90 g 2.38 → up to 1.57x | A2 §4 [C re-derived] | growth measured on bootstrap, depths 8-14 |
| History-term firing | needs \|order score\| ≥ 24,000 of a ±35,000 range | — | §1, c | in-game share unmeasured |

---

## 5. What worked and what failed

| Item | Result | Best-supported explanation | Confidence |
|---|---|---|---|
| Bootstrap → B0 → B0r1 → B0r2 | +487, +200, +235 | Replacing the evaluator, then 8.7x the data (data-starved regime), then a +687 Elo stronger labeller | high |
| S512 (width, SCReLU, phase buckets, mirroring) | FN +74.5, STC +43.7 at 0.78 nps | Capacity gain partly spent on speed (30.9 ≈ 106 × 0.358) | high |
| S512r2 | +151.4 | 4.45x data + a +279 stronger labeller + split-search share + 4.5x the compute; not separable | high (sum), low (split) |
| Idea 13 split search | +65.5 | More independent games per label plus coverage of late phases (cross-scores show B covers A, not the reverse) | medium |
| Pawn links (S512+PP) | FN +46.1, STC +32.7 at 0.895 | Incremental, slow-structure knowledge that no shallow search resolves; loss barely moved | medium-high |
| S512ppr2 (warm 1e-4, g3s2, slice, interleave) | +20.1 | Low-LR compute on the lineage + newer labels (+16 mean labeller Elo); the slice fixed 351 → 8 endgame misjudgments; shares unattributable | medium |
| Warm start at 1e-3 (S512r3; also +X and +PP runs) | loss worse than its start; endgame 249 → 329 | The 1e-3 noise floor overwrites unanchored knowledge; no bias correction and fresh moments amplify the first superbatch | high |
| S512+X (exposure inputs) | FN +25.7, STC −30.0 at 0.818 | Speed (≈ 31 Elo) + search-resolvable knowledge; 3.3σ off the speed line, so its runner or in-game slowdown may be worse than 0.818 (UNVERIFIED) | medium |
| XGR-512 | FN +30.7, STC −34.4, LTC −30.6 | Speed (0.64): R × 0.642 = 68 at STC; the LTC penalty barely smaller | high |
| AF-S | FN +10.4, STC −55.9 | Speed (0.72) + quantization loss (32 cp max) | high |
| H-512 | r1 FN +32.2 / STC −24.4; r2 FN −12.2 | r1: speed + overfitting; r2: more capacity fitting the training distribution, not UHO play (A1 §3.5.3) | low-medium |
| S512cl | never trained | 0.195 nps ≈ −250 Elo; the gate worked | high |
| SE / multi-cut | +14.1 / +9.2 | Search more where the TT move is singular; prune only after a verifying search; precision rises with depth | high |
| Reply / follow / take | +11.5 / +7.2 / +4.5 | Ordering information, weights picked by a mechanism metric (mean cutoff index) | high |
| IIR | +21.5 STC, +26.3 LTC | Node efficiency where ordering is unknown; the proxy was blind to it | high |
| SEE pruning, Syzygy, check relief | +21.2, +17.5, +11.3 (now ≈ +3) | Standard; check relief's value shrank with the net | high |
| Negative extension | −8.7 | Ungated (no node types), whole-ply cut on the move that carries the node | medium |
| LMR history term | −10.8 | Unresolved among: persistence (fires mostly in games), cost (computed for every quiet), asymmetry (high-history moves sit before LmrMinMove); an anomaly for 0.27% of bench nodes | low |
| Rising RFP / RfpMargin 40 | −3.8 / gauntlet −44 | One-sided loosening of eval-gated pruning; the margin was never refit | medium |
| ProbCut | −5.3 | Overlap with NMP and multi-cut; tight margin; QS probe cost | medium |
| Threat-aware ordering | −6.1 | Per-node attack cost + a 4x butterfly table (out of L1) + update dilution + overlap with reply | medium |
| QS delta, pawn drift table | −0.4 / −0.35 (LTC) | Expected ≈ 0: QS pruning saves little where eval is 42% of time; the pawn table overlaps the links and cut error only 8% | medium |
| Fifty-move scaling | proxy only | Proxy artifact (the score rescaling is counted as error); never game-tested | medium-high |
| Root fail-high fix (bootstrap) | −14.6 | Played unverified moves; the time-side fix (do not stop while unresolved) is untried | medium |
| C4 select_best | +4.0% nps | Dependency-chain fix; transfers to any CPU | high |
| C2, C3, E1, E4 | −0.6 to −5.3% | Latency already hidden by a 96 MB L3 and a 16 MB TT; may differ at TCEC | medium |
| Idea 40 speed steps | 0.666 → 0.895 | Fewer instructions won; every cache or prefetch idea lost | high |
| Label-and-sweep proxy | never predicted a gain; ρ = −0.3 | Labels by the "off" engine reward similarity; fresh state hides history and TT effects; the score term penalizes rescaling | high |
| Raw FN screen for slower nets | 2 of 7 signs | Speed unpriced | high |
| Speed-adjusted FN screen | 8 of 8 (leave-one-out too) | Prices speed at R ≈ 106 | medium-high |
| Validation loss across architectures | misranked S512+X, S512+PP and H-512 | Search-resolvable vs search-invisible knowledge; coverage; quantization (A1 §3.5) | high |

---

## 6. Ranked diagnosis of the real bottlenecks

Ranked by (Elo plausibly at stake at LTC) × confidence, with cost as a
tie-breaker. Elo ranges are head-to-head placeholders, not predictions.
**0** is outside Phase 4.

| Rank | Bottleneck | Evidence | Conf. | LTC Elo at stake | Cheapest resolving measurement |
|---|---|---|---|---|---|
| 0 | **No SMP** (Phase 6 by design) | session.cpp: one search thread; TCEC 512 threads | high (fact) | hundreds at TCEC; 0 in Phase 4 tests | outside Phase 4. Avoid Phase 4 designs that need large per-thread memory without a TCEC estimate |
| 1 | **Search constants never refit on any network; no SPSA** | A2 §1.4 (every eval-gated margin in bootstrap cp; LMP from butterfly-only ordering; growth from the bootstrap); every eval-gated loosening lost (A2 §3.1); S2 priors for a first post-net SPSA | medium | +10 to +25 | A2 O4's error-quantile log (local CPU, hours) to set SPSA ranges and test "margins differ > 20% in some depth band"; then SPSA at STC, about 40-60k games (≈ 25-38 stages, 8-12 GitHub h), confirmed by STC [0, 5] and one LTC run |
| 2 | **Networks undertrained per run** (compute, schedule, selection) | no generalisation gap at ≥ 0.4 B [V]; scratch still falling at 360; 1.8 B scratch ≈ 3.6 B lineage; the 1e-3 half sits on a noise floor; best-of-360 selection (A1 §3.2, §5) | medium | +8 to +20 (eval gains carry to LTC at least undiminished: XGR's FN gain did not shrink relative to speed) | one Kaggle session (T4 x2, ≈ 13 GPU-h): standard warm recipe vs the same start with a 3x longer low-LR phase and a short warmup. Compare final/EMA losses on a fixed 200k multi-source validation set, then FN 1,600 games (equal speed, so FN ≈ STC). Kill: < 4e-5 or FN ≤ 0 |
| 3 | **Static time management; tests blind to TCEC's shape** | no dynamic term; 1.30x structural overspend noise; base/increment 100 in all tests vs 600 at TCEC; root fail high handled only by move choice (A2 §4); S2/S3 priors | medium-high | +5 to +15 at 40+0.4; more at TCEC (unmeasurable today) | build node-share scaling (zero nps; counts already exist [V]). Ladder of two slopes at STC (2 stages each), STC SPRT, then LTC. Add a TCEC-shaped control (e.g. ratio 600 at the STC increment, A2 O8.1) for allocation constants only. Plan change (Phase 5 → 4) |
| 4 | **Label loop: age and throughput** | b ≈ 0.3; half of g3s2 labelled by S512 (−204 chain Elo behind the default); doubling takes ≈ 10 days; 20k-node depth set for the bootstrap (A1 §2.2, §8) | medium | +10 to +20 per generation, decaying | Kaggle: g3-only vs g3s2 at equal samples (2 × ≈ 2 h GPU). CPU: label noise, 20k vs 320k nodes on 100k kept positions (≈ 80 min at 2 threads). If old labels hurt, purge or downweight by age |
| 5 | **SPRT design spends GitHub time on undecided outcomes** | power 21% at +3 Elo; 13-stage caps; 57% of net-era search stages bought rejections or caps; the ladder picks the best of 3 only 48-62% of the time (A3 §2.6) [V power] | high | multiplier: about 1.5-3x more Elo per GitHub hour on all remaining search work. At ≈ 150-250 search stages left, roughly +5 to +15 more adopted Elo | no measurement needed: owner decision on a stage-2 futility stop (keeps α ≈ 0) and on fixed-length estimates for the removal round. Back-test on the logged stage-wise results (free) |
| 6 | **Speed and build regime** | 1.53 Elo per 1%; the TCEC build is clang-19 v3 with no PGO and no AVX-512 output layer (DL 2026-10-24 "revisit then"; C1 parked); speed measured in an X3D/native/16 MB regime unlike runners and TCEC; S512+X 3.3σ off the line (A3 §1.6-1.7) | medium | +1.5 per 1% from any sprint; +3 to +10 at TCEC from v4 + C1 + PGO (UNVERIFIED); gate decisions shift by ±10 if runner ratios differ | local quiet A/B (1-2 h): S512ppr2 vs S512r2 built g++ v3, clang-19 v3, v4, v4 + PGO; one GitHub job benching both builds interleaved on a runner (tests the S512+X outlier and every gate ratio) |
| 7 | **Under-informed LMR and never-decayed histories** | LMR has no history, node-type, TT-PV, improving or capture terms; TT-PV bit stored and unused; the history term's −10.8 anomaly; histories persist [V] (A2 §2.2, O2-O6) | medium-low per item | +5 to +15 cumulative over several SPRTs, each underpowered (see 5) | A2 O3: 20 stats-build self-play games, share of LMR sites with \|score\| ≥ 24,000 at moves 30-60 vs bench (1 h local CPU). Then a centred, sub-ply history term (§3.2) and cut-node LMR |
| 8 | **Training target untuned** (λ = 0.5 since B0; sigmoid MSE; scale) | `--result-weight` default 0.5, never varied in any Kaggle script [V]; 81% decisive games; the result half is shallow-play outcome noise (A1 §3.2, §8); S2's WDL-heavier end | low-medium | 0 to +15 | two warm continuations differing only in w (one value either side, chosen by reasoning and recorded), each scale-matched; FN 1,600 games each. Free side-fix: log the score and result MSE components separately |
| 9 | **Coverage censoring in the data** | game ends at table entry and after 8 plies beyond 700 cp; 18.6% of starts discarded as decided; one 2016 opening book; 18-20% draws; the slice's 2.1% fixed 97.7% of misjudgments (A1 §6) | low (Elo), medium (exists) | 0 to +10 at STC/LTC; possibly more at TCEC (no win adjudication, long games, 7-man tables) | histograms of phase, \|eval\| band and material signature: training positions vs Fork's SPRT games (CPU hours, no training). Prediction: some band under-represented > 3x |
| 10 | **Architecture capacity under the speed constraint** | only the incremental, search-invisible input (links) passed; every recomputed input failed on speed (A1 §9 B7) | low | 0 to +30 over the rest of Phase 4, spread over several designs | the speed-adjusted FN screen as the gate (FN > 106·log₂(1/r) + 5) after a runner-measured ratio; king regions as zero-initialized widening from S512ppr2 is the cheapest candidate |
| 11 | **Idea 23's proxy** | the evaluator funnel uses the label-and-sweep proxy, which never predicted a gain (ρ = −0.3, n = 5) and is biased to "off" by construction (A2 §6; A3 §2.3) | medium-high (that it is biased) | negative risk: 3+ days of compute selecting toward the baseline | validate a repaired proxy on the five known SPRT outcomes before the long run: labels by a longer default search, history and TT carried across a game, no score-error term. Kill the long run if IIR's sign is wrong |
| 12 | **Validation-loss methodology** | 20k positions from about 490 games; best-of-360; a 4e-5 threshold below the single-run noise | high | indirect (wrong recipe or candidate choices) | free: a fixed 200k multi-source validation set plus a quiet subset; report final and EMA loss; always `--interleave` |
| 13 | Quantization | S512ppr2 max 7.9 / p99 6.1 cp | medium | ≤ 3 | none now; revisit for int8 or wider designs |

**Notes on the ranking [I].**

- Items 1, 3 and 7 share one root: the search was tuned for an evaluator
  that no longer exists, and the instruments that would show it
  (proxies, fresh-state benches) are blind in the same direction.
- Items 2, 4, 8 and 12 share another: network decisions are made on a
  noisy single-run loss, while the cheap levers (compute, λ, label age)
  were never varied one at a time.
- Item 5 is not Elo itself, but it decides how much of items 1, 3 and 7
  Fork can afford to find.
- The "LTC candidates" (S512+X, AF-S) do not appear: at any plausible
  R_LTC they stay at or below zero (§3.1).

---

## 7. Cheapest open measurements, ranked by information per cost

Costs are wall time on the stated resource. Every one is read-only with
respect to the default engine and runs through jobctl where it is a job.

| Rank | Measurement | Cost | What it resolves | Prediction / decision rule |
|---|---|---|---|---|
| M1 | **In-game history magnitudes** (A2 O3): FORK_SEARCH_STATS build, 20 self-play games, share of LMR sites with \|order score\| ≥ 24,000 by move number, vs bench | ~1 h local CPU, low priority | the LMR-history anomaly; whether batch 4's history thresholds (HistorySkip, malus balance) need in-game calibration; whether a per-search history scale-down is worth an SPRT | ≥ 5x bench at moves 30-60 → persistence confirmed; within 2x → attribute to cost or asymmetry and bench the nps |
| M2 | **Build-regime nps A/B** (A3 §1.7 items 1, 3, 4): S512ppr2/S512r2 under g++ v3, clang-19 v3, v4, v4 + PGO; C1 on v4 | 1-2 h quiet local | the real gate ratio in the SPRT and TCEC builds; C1 and PGO value for TCEC (+1.5 Elo per 1%) | v3 ratio 0.86-0.89 (A3); C1 ≥ 3% total → owner decision on v4 for TCEC |
| M3 | **Runner-interleaved bench** of S512r2 vs S512+X vs S512ppr2 in one GitHub job | ~20-30 min of one runner | the S512+X outlier (a runner ratio near 0.70 would put it on the line); whether local gate numbers transfer | runner ratio ≥ 0.80 → S512+X is noise or an in-game effect; ≤ 0.74 → measure every gate on runners |
| M4 | **Search counters** (A3 §1.2): QS-eval share, TT-eval hit rate, refreshes per 1,000 updates, plies walked per lazy eval | one debug bench, minutes | the ceiling of every "evaluate fewer nodes" or accumulator idea | if QS evals < 30% of evals, drop QS eval-avoidance ideas |
| M5 | **Speed-to-Elo measurement, redesigned** (A3 §1.5): 0.5x throttled build (same binary, burned cycles), 2 STC stages + 1 LTC stage | ~1.5 h GitHub | R_STC to ±13 and R_LTC to about ±20; settles the gate and the LTC-candidate question at 40+0.4 | R_STC 88-124 (refuted outside 60-150); R_LTC/R_STC > 0.8. If time odds are used instead, record each side's mean time per move and fit against the realized ratio (§1.1g) |
| M6 | **Error-quantile margins** (A2 O4): log (depth-d search result − prune_eval) at RFP/futility/NMP candidate nodes on S512ppr2 | hours, local CPU beside datagen | SPSA's starting points and ranges; whether the bootstrap margins are mis-shaped by depth | some depth band > 20% off → seed SPSA from quantiles; all within ±15% → plain SPSA |
| M7 | **Label noise at 20k nodes**: relabel 100k kept positions at 20k and at 320k nodes; MSE in sigmoid space | ~80 min at 2 threads (≈ 16 min at 10) | whether label depth limits the net (A1 B2); the reducible-loss budget | label variance < 10% of reducible loss → leave depth alone |
| M8 | **Validation set and loss reporting** (A1 B6): fixed 200k multi-source set + quiet subset; final and EMA loss; component split (score MSE vs result MSE) | ~0 (offline, one script) | every future recipe decision; A1's irreducible-noise estimate | — |
| M9 | **Long low-LR arm** (A1 B1) and **λ arm** (A1 B4) in one Kaggle session | ≈ 13 GPU-h + 2 FN stages | bottlenecks 2 and 8 | long arm beats standard by ≥ 8e-5 final and FN ≥ +5; λ arms within ±5 FN → keep 0.5 |
| M10 | **Fixed-node doubling ladder** (S3 §C): Fork(N) vs Fork(2N) at three N spanning STC to beyond LTC depth | ~3-6 GitHub h (the largest N is costly) | how Elo per doubling falls with depth; extrapolation toward TCEC; how much speed matters there vs eval quality | a fall of > 10% per doubling → relax the gate for TCEC-only builds (an owner decision) |
| M11 | **Coverage histograms** (A1 B5) | CPU hours, no training | which censored regions to fill next (adjudication horizon, the 2026-09 book, 6-7 piece slice) | any band under-represented > 3x → change the next part's settings |
| M12 | **Proxy validation for idea 23** (A2 O8.3) on the five known SPRT outcomes | hours local CPU | whether idea 23's long run can work at all | wrong sign on IIR → do not run idea 23 on this proxy |
| M13 | **g3-only vs g3s2 at equal samples** | ≈ 4 GPU-h + 1 FN stage | label age (bottleneck 4) | g3-only better by ≥ 5 FN → age-weight or purge old parts |
| M14 | **SPRT policy back-test** on the logged stage-wise results | 0 (arithmetic) | how many stages a stage-2 futility stop would have saved, and whether it would have dropped any adopted feature | (A3 estimates ≈ 25 of 50 rejected-test stages) |

M1-M4 and M8 are nearly free and should come first; each also changes
how later items are designed. M5 is the only GitHub item in the top
half. It is cheaper and sharper than the planned 0.85x, 4,000-game
version (§5.6 item 4).

---

## 8. What I could not verify

- The actual per-move latency on GitHub runners, which sets the size of
  the time-odds skew (§1.1g); tm.py is a simplified model.
- Whether g3s2-val's first 20,000 kept positions include the five new
  sources (A1 §3.2).
- Every nps ratio on runners and under the TCEC build (only local native
  ratios exist).
- The in-game distribution of history magnitudes (M1), and the nps cost
  of the LMR history branch.
- The labeller-transfer coefficient b and the data-scaling rates. Both
  come from zero-dof fits with confounded steps, so the loop amplification
  of 1.45 inherits that weakness.
- The self-play inflation factor (about 1.7x; gauntlets on different
  anchor sets).
- External priors (S1-S3: SPSA, node-share TM, correction tables, Elo
  per doubling at long TC) are other engines' logged results, biased
  upward by SPRT selection. None is a Fork measurement.
- LTC stage wall time (about 75 min) is A3's estimate; I did not query
  GitHub.


---

# Appendix A1. Network, training and data evidence

## A1: network, training and data evidence (Phase 4 think tank, Phase A)

**Summary.** Read across every net, training run and data part, Fork's
evidence points to five things. **(1) Label quality is the proven engine.**
The generational loop (new data labelled by a stronger default) gives most
of the gains. A crude two-factor fit to the head-to-head chain gives about
**0.3 Elo of student strength per Elo of labeller strength**, and about
**30 Elo per doubling of filtered data at the 0.1-0.4 B scale** (about 64 at
the 10-80 M scale). Both are low-confidence, because the confounds are
large. **(2) Training compute per run is a binding and unexploited
constraint.** In the large-data runs there is no generalisation gap:
validation loss is at or below training loss, which I computed from the
runs' own `train.log`. A from-scratch run of 1.8 B samples on g3s2 ends
0.0002 *worse* than S512+PP, whose lineage had 3.6 B samples. The "warm
start wins" result is mostly "more low-LR steps win", and a 4x longer run
fits in one Kaggle session. **(3) Validation loss is a poor Elo predictor,
for identifiable reasons.** The validation set is about 20,000 positions
from roughly 500 games, drawn from the training distribution. Its loss is
dominated by result noise, and the reported figure is the best of 360 noisy
checkpoints. Every run before g3s2 also read shards in file order, which
inflated seed spread by about 10x. Within one architecture, loss is worth
about 6-10 Elo per 1e-4. Across architectures the rate ranges from negative
(H-512) to about 40+ per 1e-4 (pawn links). **(4) Speed accounting.** A
single exchange rate of **k = 152 ± 28 Elo per e-fold of nps (about 1.5 Elo
per 1% at small gaps; about 105 per doubling)** fits all 8 FN/STC pairs
(chi² 6.4 on 7 dof). The ~3 Elo per 1% rate taken from S512+X is rejected
(chi² 113), and 0.9 Elo per 1% is too low (chi² 26). S512+X itself is the
one outlier, at 1.7σ. **(5) Coverage gaps from datagen censoring are
real.** The Syzygy slice (2.1% of positions) took endgame misjudgments from
351 to 8, and idea 13's cross-scores show that a net can be better on its
own validation set and still lose by 65 Elo. Two further findings are new
here. The **0.5 result weight has never been tuned** since B0, although
81% of training games are decisive. And bullet's **AdamW has no bias
correction**, which mechanically explains why a warm start at LR 1e-3
destroys the starting net within one superbatch.

Conventions: **READ** = a number taken from a file (cited). **COMPUTED** =
my arithmetic on read numbers. **INFERRED** = my interpretation.
**UNVERIFIED** = unsure. SL = docs/history/phase-4/sprt-log.md, NM =
docs/nets.md, DL = DESIGN.md §6 decisions log, HO = HANDOFF.md, K =
`~/fork-data/kaggle/<run>/result/<net>/run.json` (Kaggle run records:
validation curves, cross-scores), TL = the same folders' `train.log`.

---

## 1. The evidence base in one table

READ unless marked. "Kept" means positions passing the trainer's filter
(not in check, played move not a capture or promotion, |score| ≤ 20000;
tools/train/src/main.rs `filter()`). The kept share is 67.7% of saved
positions (g2s1: 615.8 M saved, 416 M kept; NM); kept counts for later sets
are COMPUTED with that share. "Lineage samples" is the number of training
samples behind the net, counting the warm-start chain.

| Net | Data (kept) | Labeller (its chain Elo over bootstrap) | Samples this run / lineage | Val loss (set) | FN | STC (vs) |
|---|---|---|---|---|---|---|
| B0 | g0s1 9.5 M pos (~6.5 M kept) | bootstrap (0) | best at superbatch 3 = 15 M | 0.02483 (g0) | n/a | +486.9 (bootstrap) |
| B0r1 | g0s2 82.9 M (~50 M kept, 9/10 shards) | bootstrap (0) | best at 19 = 95 M; warm from B0 at 1e-3 | 0.02298 (g0) | n/a | +200.2 (B0) |
| B0r2 | g1s1 93.5 M kept | B0r1 (+687) | 400 M, scratch | 0.021679 (g1s1-val) | n/a | +235.5 (B0r1) |
| S512 | g1s1 93.5 M kept | B0r1 (+687) | 400 M, scratch | 0.020974 (g1s1-val) | +74.5 (B0r2) | +43.7 (B0r2) |
| S512r2 | g2s1 416 M kept | S512 (+966) | 1.8 B, scratch | 0.019458 (g2s1-val); 0.01930359 (g3s1-val) | n/a | +151.4 (S512) |
| S512r3 | g2s1+g3s1 ~669 M kept (COMPUTED) | S512 and S512r2 | 1.8 B, warm at 1e-3 | 0.01933709 (g3s1-val), worse than its start | not played | not played |
| S512+X | as S512r3 | as S512r3 | 1.8 B, warm at 1e-3 | 0.01887023 (g3s1-val) | +25.7 (S512r2) | −30.0 at 0.818 nps |
| S512+PP | as S512r3 | as S512r3 | 1.8 B warm at 1e-3 / 3.6 B | 0.01929241 (g3s1-val); 0.019305 (g3s2-val) | +46.1 (S512r2) | +32.7 at 0.895 nps |
| S512ppr2 | g3s2 ~848 M kept incl. 26 M slice (COMPUTED) | S512, S512r2 (+1117) + Syzygy | 1.8 B warm at 1e-4 / 5.4 B | 0.01908862 (g3s2-val) | n/a | +20.1 (S512+PP) |
| g3s2 scratch (2 seeds) | as S512ppr2 | as S512ppr2 | 1.8 B scratch | best 0.01948/0.01956, final 0.019617 both (K) | n/a | n/a |

The bake-off entries (SL; K bake-out, r2a/b/c-out):

| Entry | Round-1 val (g1s1-val) | R1 FN / STC vs B0r2 | Round-2 val (g2s1-val) | R2 FN / STC vs S512r2 | nps ratio |
|---|---|---|---|---|---|
| H-512 | 0.022349 | +32.2 / −24.4 | 0.019343 (s1) | −12.2 / n/a | 0.75 of B0 (R1); about 0.96 of S-512 |
| AF-S | 0.021631 | +41.7 / −48.5 | 0.019396 | +10.4 / −55.9 | 0.56 of B0; about 0.72 of S-512 |
| XGR-512 | 0.021201 | +52.1 / −38.2 | 0.018978 | +30.7 / −34.4 (LTC −30.6) | 0.48 of B0 (R1); about 0.64 of S-512 after the speed-up |

The R1 nps ratios are bench nps measured beside data generation, not A/B
runs (DESIGN.md §5.4, "Local bench nps beside datagen"). The R2 ratios are
COMPUTED from them. S512+X and S512+PP have quiet-machine A/B ratios
(SL 2026-11-05; ideas.md 40).

---

## 2. Q1: what drove each gain

### 2.1 Per step (READ facts, INFERRED attribution)

- **Bootstrap → B0, +487.** A hand evaluation replaced by a network, on
  9.5 M positions. Not comparable to anything else in the chain.
- **B0 → B0r1, +200.** One factor only: about 8.7x more data (3.1
  doublings) from the same labeller, with the same architecture and
  settings. B0 had overfitted (best checkpoint 3 of 11, early stopped), so
  this is a data-starved regime. **About 64 Elo per doubling** of data and
  samples together (COMPUTED).
- **B0r1 → B0r2, +235.** Data grew only 1.7x (0.77 doublings of kept
  positions: ~55 M to 93.5 M). The labeller went from bootstrap to B0r1
  (+687 Elo stronger), the scale was refitted (134 → 105), and training
  ran 80 superbatches from scratch. INFERRED: most of the +235 is label
  quality.
- **B0r2 → S512, +43.7 STC / +74.5 FN, same data and labeller.** Pure
  architecture (width 512, SCReLU, 8 phase outputs, mirroring), with loss
  −0.00071. The STC result is +30 below the FN result: speed, at 0.78 nps
  (§4).
- **S512 → S512r2, +151.** Many changes at once:
  - 4.45x kept data (2.15 doublings);
  - a labeller +279 Elo stronger (S512 against B0r1);
  - about 41% of g2s1's saved labels from the split search (COMPUTED from
    the part sizes in HO §3: g2b 43.4 M saved, g2e 100.2 M, and roughly
    108 M from the AWS runs, inferred from their unsaved records;
    UNVERIFIED);
  - 360 superbatches instead of 80 (the same ~4.3 passes);
  - S 101 → 92.
- **S512r2 → S512+PP, +46.1 FN / +32.7 STC.** Pawn links, plus g3s1 (374 M
  saved, labelled by S512r2), trained warm at LR 1e-3. The same recipe
  without links (S512r3) did not even beat its starting loss: 0.01933709
  against 0.01930359 on g3s1-val. Its endgame misjudgments rose from 249
  to 329, and it was never played (DL 2026-11-05). INFERRED: almost all of
  S512+PP's gain is the links, not the added data. The 1e-3 warm start
  wiped out what a retrain could have gained from the new data (§5).
- **S512+PP → S512ppr2, +20.1 STC.** Several changes:
  - data +25% (0.33 doublings), almost all of it S512r2-labelled;
  - the mean labeller strength rose by about +16 Elo (COMPUTED: the
    S512r2-labelled share went from 374/988 to about 600/1240 positions);
  - the Syzygy slice (2.1%);
  - the warm recipe at 1e-4 (+1.8 B low-LR samples on the lineage);
  - **the first run with `--interleave`** (§3.4).
  These are not separable from this one run.

### 2.2 A crude two-factor model (COMPUTED, low confidence)

Model: ΔElo = a·Δlog₂(kept data) + b·Δ(labeller chain Elo). Fitted on
B0r1→B0r2 (0.77a + 687b = 235) and S512→S512r2 (2.15a + 279b = 151), it
gives **a ≈ 30 Elo per doubling and b ≈ 0.31**. Checks:

- B0→B0r1 needs a = 64. That is consistent with diminishing returns: B0
  sat in a smaller, data-starved regime.
- S512+PP→S512ppr2: the model predicts 0.33·30 + 16·0.31 ≈ +15; the
  observed result is +20.1 ± 7.2. The remaining ~5 (slice, interleave,
  extra compute) is within noise.
- Idea 13: arm B had 1.8x the games at the same saved labels. At the B0
  scale, 0.85 "doublings of games" × 64 ≈ +54, against +65.5 ± 12.9
  observed (§7). This only fits if **games, not positions, are the unit
  of effective data**.

Confounds: the S512r2 step folds in the split share and 4.5x longer
training (inflating a); the bootstrap→B0r1 label jump need not be linear;
chain Elo is self-play Elo. On the last: between the 2026-10-31 gauntlet
(3315.6 ± 19.6) and the 2026-11-02 one (3445.8 ± 21.6) the head-to-head
SPRTs sum to +219 (S512r2 151.4, SE 14.1, MC 9.2, reply 11.5, follow 7.2,
take 4.5, IIR 21.5) against a gauntlet move of +130 on *different anchor
sets* (DL 2026-11-02), so head-to-head may overstate third-party gains by
about 1.7x (UNVERIFIED).

**Elo per doubling of data, my estimate:** about 60 at 10-80 M, about 30
at 0.1-0.4 B, probably 10-20 now, since at ≥ 0.4 B there is no
generalisation gap (§3.3). Confidence low; measurement in §9 B2.

---

## 3. Q2: why validation loss is an unreliable predictor

### 3.1 Loss deltas against Elo, same validation set (COMPUTED from READ values)

| Pair | Δ val loss | Elo | Elo per 1e-4 | Kind |
|---|---|---|---|---|
| S512ppr2 vs S512+PP (g3s2-val) | −0.000216 | +20.1 STC (same speed) | **9.3** | same architecture: data, labels, compute |
| S512 vs B0 control (g1s1-val) | −0.000705 | +74.5 FN | 10.6 | width and buckets |
| XGR r2 vs S512r2 (g2s1-val) | −0.00048 | +30.7 FN | 6.4 | rich inputs |
| S512+X vs S512r2 (g3s1-val) | −0.00043 | +25.7 FN | 6.0 (5.5 vs S512r3) | exposure inputs |
| AF-S r2 vs S512r2 | −0.00006 | +10.4 FN | 17 (noise) | pairwise body |
| H-512 r2 vs S512r2 | −0.000115 | −12.2 FN | **−10.6** (wrong sign) | king regions |
| H-512 r1 vs B0 control | **+0.00067** | +32.2 FN | (wrong sign) | regions and width |
| S512+PP vs S512r2 (g3s1-val) | −0.0000112 | +46.1 FN | **≈ 41** (≈ 80-115 vs S512r3) | pawn links |
| idea 13, i13b1 vs i13a2, on arm A's val | **+0.00078** | +65.5 STC | wrong sign | data distribution |
| idea 13, same nets, on arm B's val | −0.00160 | +65.5 STC | 4.1 | data distribution |

Cross-scores for idea 13 are in K `i13-out/result/b0-*/run.json`
(`held_out_loss`). i13a2: A-val 0.02380, B-val 0.02693. i13b1: A-val
0.02458, B-val 0.02532. They are not in any repo document.

**Rule of thumb (INFERRED):** for "same inputs, better data or training",
about 6-10 Elo per 1e-4 of validation loss (about 0.5% relative). Across
input or architecture changes, loss does not rank nets.

### 3.2 The noise floor of a reported loss (READ curves from K, COMPUTED spreads)

- **Seed spread of the best loss** is mostly far wider than the 4e-5 used
  as the resolution threshold (retrain_g3s2.py `SEED_SPREAD`): g3s2 warm
  1.2e-5, g3s2 scratch 8.2e-5, S512 r2 3.8e-5, S512 r1 2.0e-4, S512+PP
  1.6e-4 (seed 1 never beat its initial weights), XGR r2 4.3e-4, H-512 r2
  4.6e-4, idea-13 arm A 4.8e-4.

- **Superbatch-to-superbatch jitter** is 3e-4 to 1e-3 at LR 1e-3 (scratch
  seed 1 on g3s2: 0.021999 at superbatch 40, 0.021366 at 41) and about
  2e-5 to 7e-5 at LR 1e-4 with interleaving.
- **Best-of-360 selection bias** (the "optimizer's curse"; Smith and
  Winkler, Management Science 52(3), 2006). The kept checkpoint is the
  minimum of about 360 noisy evaluations on the same 20,000 positions
  that report it. Examples: warm seed 1's best is 0.019089 at superbatch
  352 against 0.019154 at 360; scratch seed 2's best is 0.019559 at 281
  against 0.019617 at 360. The **final** losses of the two g3s2 scratch
  seeds are identical to 1e-6 (0.019617), so most of their "spread" is
  selection. INFERRED: the reported best loss is optimistic by roughly
  the jitter amplitude, and comparing best losses compares two
  selection-biased minima.
- **The validation set is small and correlated.** The trainer uses the
  first 20,000 *kept* positions of the validation file (main.rs
  `--val-positions` default; every Kaggle script sets 20000). g3s2-val
  has 1,800 games and 109,522 saved positions (g3s2.json), so at about 68%
  kept the 20,000 come from roughly the first 490 games (COMPUTED). The
  result half of the target therefore rests on about 490 independent
  outcomes.
  - If the file is concatenated in the order its manifest lists ("g3s1-val
    (25 sources x 60 games) and 5 new sources x 60 games"), then **none of
    the five new sources (g3b-g3e, the slice) is in the positions actually
    scored** (UNVERIFIED: depends on how g3s2-val.vf was assembled).
- **The result half is mostly irreducible noise** (INFERRED, estimate).
  The target is 0.5·sigmoid(score/S) + 0.5·result (main.rs `mapper`), so
  the irreducible part is 0.25·Var(result | position).
  - A balanced position at 60% draws has Var 0.10, contributing 0.025.
  - A lopsided one at 90% wins and 10% draws has Var 0.0225, contributing
    0.0056.
  - Training games are 81% decisive (manifests: draws 18.1-19.7% in every
    part).
  - So the floor is plausibly 0.010-0.016 of the 0.019 total, and a 1e-4
    change is 3-10% of the reducible part (UNVERIFIED: a loss split by
    component would settle it, §9 B4).

### 3.3 No generalisation gap at scale (COMPUTED from TL, new here)

Mean training loss (bullet's per-batch loss) against validation loss over
the same superbatches:

| Run | Train − val gap |
|---|---|
| R1 bake-off, 93.5 M kept, superbatches 71-80 | S512 +0.0016, B0 +0.0009, XGR +0.0043, AF-S +0.0043, H-512 +0.0049 (overfitting, as §5.4 said) |
| R2, 416 M kept, superbatches 351-360 | S512 −0.0005, H-512 −0.0004 to 0.0000, AF-S +0.0001, XGR −0.0002 to +0.0002 |
| g3s2 runs, superbatches 351-360 | warm −0.0010, scratch −0.0007 |

At ≥ 0.4 B kept positions there is no overfitting for any of these
architectures: validation is at or below training loss. **Implication
(INFERRED):** volume is not the binding constraint for S-512-class nets
any more. Fitting (compute, schedule) and target quality are.

Two caveats. The training-loss level varies by data source (see §3.4). And
validation lies below training probably because the validation positions
are an easier mix (UNVERIFIED).

### 3.4 Non-interleaved training before g3s2 (READ code, INFERRED effect; new here)

The shard reader reads files **in order**, shuffling only within a buffer
of 2²⁴ ≈ 16.8 M positions (main.rs `ShardReader`, `--buffer` default).
Only `retrain_g3s2.py` passes `--interleave` (grep of tools/train/kaggle).
So every net from B0 to S512+PP (the bake-off, S512r2, S512r3, S512+X,
S512+PP) trained on non-iid streams. A buffer holds about 3.4 superbatches
of one file region, meaning one labeller, one part, one worker and one
time period.

Signatures of this in TL:
- the training loss jumps *up* by about 0.001 at superbatch 181 in the
  r3v2 runs (0.02049 → 0.02149) while validation drops: a file boundary,
  not the LR drop;
- seed spreads of 1.6e-4 to 4.6e-4 before g3s2, against 1.2e-5 for the
  interleaved warm runs;
- large superbatch jitter at 1e-3.

The kept checkpoint also depends on which file region the run ended on
relative to the validation sources (a recency effect; cf. catastrophic
forgetting, McCloskey and Cohen 1989).

**Consequences.** (a) Pre-g3s2 loss comparisons carry an extra
"file-order lottery" term. (b) Part of S512ppr2's +20.1 may be
interleaving, unattributable. (c) The idea-13 seeds (−14.8 Elo apart in
arm B) may partly reflect it.

### 3.5 Why loss misranks architectures (INFERRED mechanisms, ranked by evidence)

1. **Search-resolvable against search-invisible knowledge.** Exposure,
   threat and region inputs improve the static eval where quiescence and
   1-3 ply search already find the truth (hanging pieces, immediate
   threats), so the loss improves but the searched value barely changes.
   Pawn links encode slow structure no horizon resolves. Evidence:
   exposure-type gains run at 6.0-6.4 Elo per 1e-4 (S512+X, XGR,
   consistently), links at ≥ 41. Test: S512+X's loss gain should
   concentrate where static eval and quiescence disagree (the residual
   study, idea 46 rank 0, can split it).
2. **Coverage blindness.** The validation set comes from the same
   generator, so it cannot see what the generator censors: idea 13 (A-net
   better on A-val, −65 Elo) and the endgame check (S512+PP 351
   misjudged, still +32.7). See §6.
3. **Data-to-test distribution shift.** Data starts from Lichess 2016-09
   2000+ openings plus 4-8 random plies (2-4 at book creation, 2-4 per
   game; datagen_main.cpp); tests start from UHO_Lichess_4852. A
   higher-capacity input set (H-512: about 2.0 M first-layer weights
   against 0.39 M) can fit the training distribution without gaining on
   the test one, a plausible reading of H-512 r2 (better validation,
   −12 FN). UNVERIFIED.
4. **Quantization is invisible to float loss** (AF-S r2: 32.4 / 20.2 cp;
   S512ppr2 only 7.9 / 6.1).
5. **Sigmoid-space MSE barely weighs decided positions**
   (sigmoid(400/92) = 0.987), so wrong conversion technique (KRK) barely
   moves the loss.
6. **Eval shape against search margins** tuned on older nets: S matching
   equalises only the mean |eval|.

---

## 4. Q3: the speed-accounting model

### 4.1 The model and the fit (COMPUTED, script in my scratchpad: `speedfit.py`)

STC Elo ≈ FN Elo − k·ln(1/r), where r is the nps ratio. This is the
first-order model of KB phase4-designs/design-speed.md §2.8 ("R(TC)" per
doubling = k·ln 2). Weighted least squares over the 8 pairs, with the
deficit's error taken as √(FN² + STC²) of the 95% bars:

| Entry | FN − STC | ± | ln(1/r) | k per e-fold | Elo per 1% (linear) |
|---|---|---|---|---|---|
| S512 r1 | 30.9 | 17.1 | 0.248 | 124 | 1.40 |
| H-512 r1 | 56.6 | 15.1 | 0.288 | 197 | 2.26 |
| AF-S r1 | 90.2 | 17.5 | 0.580 | 156 | 2.05 |
| XGR r1 | 90.2 | 17.6 | 0.734 | 123 | 1.73 |
| AF-S r2 | 66.3 | 15.4 | 0.329 | 202 | 2.37 |
| XGR r2 | 65.1 | 15.8 | 0.446 | 146 | 1.81 |
| S512+X | 55.7 | 14.9 | 0.201 | **277** | **3.06** |
| S512+PP | 13.4 | 14.7 | 0.111 | 121 | 1.28 |

- **No intercept: k = 152 ± 28 per e-fold**, chi² 6.4 on 7 dof, a good fit.
  That is about **1.5 Elo per 1% nps** at small gaps, or **105 Elo per
  doubling** of speed at STC.
- With an intercept: k = 115 ± 59, c = +17 (FN overstating the
  STC-equivalent accuracy; see 4.3), chi² 4.4.
- Without S512+X: k = 148 ± 29, chi² 3.5 on 6 dof.

Fixed rates scored against all 8 points:

| Rate | chi² (8 points) | Verdict |
|---|---|---|
| 0.9 Elo per 1% (k = 90) | 25.6 | too low: under-predicts every rich net's STC loss by 1.4-2.5σ |
| **1.5 per 1% (k = 150)** | **6.5** | best; S512+X off by 1.7σ |
| 2 per 1% (k = 200) | 17.5 | XGR r1 off by 3.2σ |
| 3 per 1% (k = 300) | 113 | rejected: predicts S512 r1 at 0 (observed +43.7) and AF-S r1 at −132 (observed −48.5) |

**Verdict: about 1.5 Elo per 1% (k ≈ 150 per e-fold) is the rate most
consistent with all the data.** The 3.1 from S512+X's single swing is an
outlier, and the plan value of "2 ± 1" (HO §5) should be centred lower.
Caveat: the R1 ratios are loaded-machine bench nps and the R2 ratios are
derived from them. Only S512+X and S512+PP have clean A/B ratios, and those
two alone give k = 240 ± 127.

### 4.2 Why S512+X sits off the line (INFERRED hypotheses)

1. **Runner nps differ from the local A/B.** 0.818 was measured on the
   Ryzen X3D (96 MB L3). GitHub's runners (EPYC 7763 and similar, 4 vCPU
   VMs, shared L3; DL 2026-10-31 lists the CPUs) may penalise S512+X's
   per-evaluation 32-bit row sums more. A runner ratio of about 0.70 would
   put it on the line (152·ln(1/0.70) = 54). Cheapest test: bench both
   builds interleaved *on a runner* (§9 B7). The same caveat applies to
   every local speed-gate number, and to TCEC's many-thread EPYC.
2. **Noise** (1.7σ; expected once in about 11 such points).
3. **Phase-dependent cost.** Exposure cost grows with the number of exposed
   pieces, so game positions (tactical middlegames) may cost more than
   the 46 bench positions. UNVERIFIED.

### 4.3 Other model terms

- **The FN budget is not STC-equivalent.** 800,000 nodes searches deeper
  than STC: median depth 17 against 15 (SL stage B notes). If an
  evaluation gain grows with depth, FN overstates the STC accuracy term
  (the +17 intercept).
- **LTC.** XGR r2 lost −30.6 at LTC against −34.4 at STC. With FN +30.7,
  k_LTC ≈ 137 against k_STC ≈ 146 (each about ±40). INFERRED: the exchange
  rate falls only slightly from 8+0.08 to 40+0.4, so **"LTC candidates"
  are unlikely to flip sign**. This weighs (weakly) against S512+X and
  AF-S ever passing at LTC on speed grounds alone.

### 4.4 Implications (COMPUTED)

- **Speed-gate prices at k = 152:** 0.95 costs 7.8 Elo; 0.90 costs 16.0;
  0.818 costs 30.5; S512cl's 0.195 costs 249. A new input type needs an
  STC-equivalent accuracy gain above 152·ln(1/r).
- **Predictions for §5.6 item 4** (S512r2 against itself at 0.85x time,
  about 4,000 games, ±8):
  - **k = 152 predicts −24.7 Elo**, 95% band about [−34, −15];
  - k = 300 predicts −49; k = 90 predicts −15.
  - The measurement separates 1.5 from 3 per 1% at about 3σ, but 1.5
    from 0.9 only marginally. If budget allows, 0.70x time (ln = 0.357,
    predicted −54) discriminates better per game.

---

## 5. Q4: warm start at 1e-4 against 1e-3 against scratch

### 5.1 Facts (READ, K curves)

- **Warm at 1e-3** (S512r3, S512+X, S512+PP): validation jumps from
  0.0193 to about 0.0207-0.0217 after **one superbatch** (5 M samples). It
  then hovers at 0.0200-0.0211 through superbatch 180 and drops only after
  the LR falls to 1e-4. S512r3 ends no better than its start. S512+PP's
  seed 1 never beats its start, and seed 2 beats it by 1.1e-5. Every 1e-3
  warm start lost endgame knowledge it had never been taught: endgame
  misjudgments S512r2 249 → S512r3 329, S512+X 307, S512+PP 351, with KQK
  going from 0 to 28-59 (DL 2026-11-05; NM).
- **Warm at 1e-4** (S512ppr2's recipe): 0.019305 → 0.019345 after one
  superbatch, then a smooth fall to 0.01912 by superbatch 180. The 1e-5
  phase (181-360) adds only about 3e-5 more.
- **Scratch at 1e-3 on g3s2:** 0.0253 → about 0.0200-0.0218 band through
  180 → 0.0198 at 181 → still falling at 360 (0.019617).

### 5.2 Mechanisms

**(a) bullet's AdamW has no bias correction** (KB bullet-internals.md §5.4:
"no bias correction and no step counter"; moments restart fresh on a warm
start, main.rs "AdamW's moments fresh"). With β₁ = 0.9 and β₂ = 0.999,
after t steps of a steady gradient the step is about
(1 − 0.9ᵗ)/√(1 − 0.999ᵗ) times the LR: ≈ 3.2x at t = 1, 6.5x at t = 10,
3.2x at t = 100, 1.26x at t = 1,000 (COMPUTED). So the first ~1,000 steps
(about 3 superbatches) move *every* weight 1.3-6.5x the nominal LR along
noisy gradients; at 1e-3 that is up to about 6e-3 per step, a large
perturbation of a trained first layer, which explains the instant spike.
Standard Adam corrects this initialisation bias (Kingma and Ba, "Adam: A
Method for Stochastic Optimization", arXiv:1412.6980); the usual remedy
is LR warmup (Goyal et al., "Accurate, Large Minibatch SGD",
arXiv:1706.02677), and bullet ships a `Warmup` scheduler (KB §5.3). The
checkpoints already store AdamW's moments (main.rs "optimiser_state/"),
so a warm start could also *resume* them.

**(b) The 1e-3 phase sits on an LR-noise floor.** Every S-512-class run,
warm or scratch, hovers at 0.0200-0.0211 while LR = 1e-3. The gains come
only after the drop. INFERRED: the step schedule's first half explores at
a high noise temperature, so the effective "fitting" happens in the low-LR
phase, which means 0.9 B samples per 360-superbatch run.

**(c) Decoupled weight decay depends on the LR.** decay 0.01 × LR per step
(bullet defaults; Loshchilov and Hutter, "Decoupled Weight Decay
Regularization", arXiv:1711.05101). Over a run, a weight shrinks by
exp(−0.01·ΣLR·steps): about 0.55 for scratch (1e-3 then 1e-4) and about
0.94 for warm 1e-4 (COMPUTED, 54,900 steps per phase). The two recipes
therefore also differ in regularisation strength (effect UNVERIFIED).

**(d) The lineage effect is a compute effect.** On g3s2-val:

| Net | Lineage samples | Loss |
|---|---|---|
| S512+PP | 3.6 B | 0.019305 |
| Scratch on g3s2 (more and better data) | 1.8 B | 0.019617 final, 0.01948 best |
| Warm (S512ppr2) | 5.4 B | 0.019089 |

INFERRED: **the warm recipe's +0.00042 over scratch is mostly accumulated
low-LR training compute, not a property of warm starting.** Each net is
undertrained at 1.8 B samples, and the scratch curves are still falling at
360. This is not catastrophic forgetting of data: g3s2 contains all the
old data. It is optimisation progress being kept.

### 5.3 What it implies

- **Effective data:** with no generalisation gap (§3.3), extra passes are
  not wasted. Samples seen at low LR are the lever.
- **Kaggle cost** (COMPUTED from K): S512+PP runs at 21.5 s per superbatch
  on one T4 (7,741 s / 360). 1,080 superbatches take 6.5 h and 1,440 take
  8.6 h. Either fits a 9-12 h session, with two such runs in parallel on
  T4 x2, out of about 30 GPU-h per week.
- **Risks of the warm lineage** (INFERRED): seeds stop exploring (warm
  seeds differ by 1.2e-5); old-label biases are never forgotten; every
  architecture change must be zero-initialised widening (fine for input
  rows, harder for new layers).
- **The fair control is still missing:** scratch at equal total samples
  (3.6-5.4 B). If it matches warm, then periodic long scratch runs are
  viable (they free architecture changes, e.g. hidden layers).

---

## 6. Q5: the endgame slice, and coverage gaps

**Facts (READ).**
- S512ppr2 misjudges 8 of 900 (KQK 0, KRK 0, KPK 8 of 300), against
  S512+PP's 351 (59 / 267 / 25) and S512r2's 249 (0 / 223 / 26) (NM, HO).
- The slice is 26.0 M one-move games (2.1% of g3s2), half KPK/KQK/KRK and
  half the signatures Fork's games reach at table entry, with targets
  saturated to the WDL (SLICE_SCORE 2000, endgame_slice.py).
- Game ends in g3 (manifest, share of written games): score adjudication
  (700 cp for 8 plies) 40.2%, mate found 27.9%, table result 21.3%,
  repetition 10.0%, fifty-move 0.6%. Besides those, 1,221,012 games (18.6%
  of attempted games) were discarded as "decided openings" (first search
  beyond 400 cp after the per-game random plies; self_play.cpp).

**What it says (INFERRED).**
1. **The data never contains positions past a censoring point:** ≤ 5
   pieces (the game ends at table entry), and anything after 8 plies beyond
   700 cp (conversion technique; roughly twice that in split-search parts,
   since unsaved plies do not count toward the 8). The net's eval there is
   unconstrained, which is why KQK went 0 → 59 → 0 with no data on it.
2. **Marginal value of coverage is very high:** 2.1% of positions fixed
   97.7% of the misjudgments. Its Elo is probably small *in SPRT
   conditions* (both engines probe Syzygy 3-4-5 in search; TCEC has 7-man
   tables). **No slice ablation exists; its share of the +20.1 is
   UNVERIFIED** (INFERRED: ≤ 5).
3. **Other censored regions that matter more at TCEC:** conversion phases
   with 6+ pieces; long manoeuvring and fortress positions (0.6%
   fifty-move ends, draws only 18.1-19.7% in every part); and openings
   unlike the book's (the 4-8 random plies make about 19% of starts
   lopsided enough to discard, so survivors skew toward ±400 cp). See §9
   B5.
4. **Rare-pattern knowledge is not anchored:** any large perturbation (the
   1e-3 warm starts) scrambles patterns absent from the data, so "the
   endgame check got worse" was a coverage signal, not a recipe signal.

---

## 7. Q6: idea 13's split search (+65.5): mechanisms consistent with the data

Facts (READ, ideas.md 13; SL; K i13-out): equal saved labels (arm A
1,637 per second, arm B 1,641), arm B played **1.8x the games**;
- ends: score adjudication 42.3% against 64.3%, mates 27.2% against 13.5%,
  tables 20.5% against 10.9%;
- both arms trained 400 M samples on about 24 M kept positions each
  (~16 passes);
- arm A's best checkpoints came at superbatches 15/24, arm B's at 43/53;
- cross-scores as in §3.1.

| # | Hypothesis | Consistent evidence | Against | Test |
|---|---|---|---|---|
| H1 | **More independent games per label.** Positions within a game share one result and much structure, so the effective sample size is closer to games than positions; 1.8x games ≈ 0.85 doublings ≈ +54 at the B0-scale rate (§2.2) | arm B overfits later (best checkpoint 43-53 against 15-24); the +54 prediction is within 1σ of +65.5 | none | small-net arms at save 25% and 50% (equal saved labels); H1 predicts a further, smaller gain |
| H2 | **Coverage of late game phases.** The doubled effective adjudication horizon and more mates and table endings put conversion phases into the data | A-net on B-val 0.02693 against B-net 0.02532 (A cannot cover B's positions); B-net on A-val 0.02458, close to A's own 0.02380 (B covers A) | none | arm A with adjudication plies 16 |
| H3 | **Exploration from 4k-node moves.** Weaker moves diversify trajectories (a "temperature") | plausible | weaker moves also make results noisier | save 50% with unsaved nodes 20k (no cheap moves) |
| H4 | Result-label noise from weaker play | would *lower* B's quality | B won | (none) |

**Most likely (INFERRED): H1 + H2 together.** H1 alone accounts for most
of the Elo at that data-starved scale, and H2 is what the cross-scores
uniquely show. **Transfer warning:** at today's scale there is no
overfitting (§3.3), so H1's diversity benefit should be smaller than at
idea 13's 24 M. H2 (coverage) and the result-label averaging (more
independent outcomes) still apply.

**Cost model for lower save shares** (COMPUTED). CPU per record is
p·20k + (1 − p)·4k nodes (ignoring checks at 2k). Against p = 0.5, p = 0.25
gives **1.5x the games and 0.75x the saved labels** per CPU-hour; p = 0.1
gives 2.1x and 0.43x. If games are the unit, p = 0.25 is worth testing
(§9 B3).

---

## 8. Q7: data-quality questions still open

| Question | What is known (READ) | Assessment (INFERRED) | Cheapest measurement |
|---|---|---|---|
| **Result weight w = 0.5 (λ = 0.5)** | Set for B0 because "neither is trusted over the other", to be "tuned per generation" (DESIGN.md constants table); **never tuned**; the labeller is now about +1,100 chain Elo above bootstrap, and 81% of games are decisive at 20k-node play | likely mis-set now. The score half is a 20k-node search by a ~3450-rated engine; the result half is a shallow-play outcome. Changing w changes the eval scale (KB nnue-design.md §6.3), so it needs S rematched and **cannot be judged by loss** (different targets) | two nets differing only in w (same seed, data, schedule), each scale-matched; FN then STC. Report both target components on one shared set |
| **Label noise (20k nodes)** | 20k chosen on 2026-10-28 for median depth 8.5 *with the bootstrap* (constants table); not re-measured for S512ppr2 + tier 2 | label depth and noise today UNVERIFIED | relabel 100k kept positions at 20k and at 320k nodes; MSE in sigmoid space between them is the label-noise variance; compare with the reducible loss (§3.2) |
| **Quiet filtering** | proxy: played move is a capture or promotion (viriformat filter); idea 47.2 planned; arXiv 2412.17948 has no ablation (KB research-nnue-dataset-quiet-positions.md §2) | low expected value now: no overfitting, and a stricter filter discards 20k-node labels. The training-serving mismatch risk (KB §3.6) is real | the offline counts first (idea 47's plan) |
| **Duplicates** | openings tool removed 845 duplicate openings; **no duplicate count for training positions** | early-game near-duplicates are likely (the same 591,871 roots, about 37 games each across g3s2's ~19.6 M games, COMPUTED) | 64-bit Zobrist histogram of kept positions on one shard per part |
| **Opening diversity** | every part uses lichess-2016-09 (591,871); lichess-2026-09 (13.9 M) unused (HO §3); 2-4 random plies at book creation plus 2-4 per game | the base structural diversity is the 2016 book; the random plies add tactical noise rather than plausible variety (18.6% of starts discarded) | switch the next part to the 2026-09 book (a new part anyway); A/B by a small-net arm if wanted |
| **Draw and adjudication share** | draws 18.1-19.7% in every part; score adjudication 40%; no draw adjudication (DESIGN.md §5.3) | the result half teaches that small edges convert. True at 20k nodes, false at TCEC depth: the net likely overrates winning chances in drawish endgames (UNVERIFIED, a TCEC-relevant bias) | histogram of results by final eval band and phase; compare with the SPRT games' draw rates by band |
| **Positions per game** | 94 records, 51 saved, about 35 kept per game (manifests, COMPUTED) | if effective data ∝ games, a lower save share or keep-sampling within games is a lever (§7) | the save-share arms in §9 |
| **Old-label share** | ~50% of g3s2 labelled by S512 (−151 against S512r2, −204 against S512ppr2, chain Elo) | by the b ≈ 0.3 model, label age costs Elo. Relabelling costs about as much CPU as fresh data (below) and fixes only the score half | train g3-only against g3s2, at equal samples |
| **Validation design** | first 20k kept positions of one file; best of 360 | §3.2 | fixed 200k-position, multi-source validation plus a quiet subset; report final and EMA-smoothed loss, not best-of-N |

**Relabelling against fresh generation** (COMPUTED; g3g rate 2,707
records/s with 54.4% saved, HO §4):
- generation gives about 1,470 saved/s, which is about 1,000 kept/s;
- data generation spends about 12.7k nodes per record, so about 34 M
  nodes/s;
- a 20k-node relabel therefore runs at about 1,700 positions/s;
- relabelling g2s1's 416 M kept positions takes about 2.8 days of the
  10-thread CPU, against about 4.8 days for 416 M fresh kept positions.

Relabelling is about 1.7x cheaper per kept position, but it keeps
weaker-play trajectories and old game results (half the target). Fresh
generation renews both halves and adds new games (H1). INFERRED: relabel
only if a g3-only against g3s2 arm shows that old labels hurt.

---

## 9. Q8: ranked bottlenecks, with the cheapest experiments

Ranked by expected Elo × confidence. Every Elo figure is a placeholder
derived above, to be measured.

**B1. Training compute per run and the LR schedule.** Confidence high
(loss), medium (Elo).
- Mechanism: undertrained nets. There is no generalisation gap, the
  curves are still falling, and a 3.6 B-sample lineage beats 1.8 B from
  scratch. The 1e-3 half of the schedule sits on a noise floor. There is
  no warmup, and Adam has no bias correction (§5).
- Model: the same-architecture rate is 6-10 Elo per 1e-4. A 3x longer
  low-LR phase is guessed at −1e-4 to −2.5e-4 (the warm run gained 1.9e-4
  in its first 180 superbatches at 1e-4), so **+8 to +20 STC**. That the
  gain continues is UNVERIFIED.
- Literature: LR annealing (Loshchilov and Hutter, SGDR,
  arXiv:1608.03983); data against steps trade-offs (Kaplan et al.,
  arXiv:2001.08361; Hoffmann et al., arXiv:2203.15556), as general ML
  evidence only.
- Cheapest experiment: one Kaggle session on T4 x2. Arm (a) is the
  standard warm recipe. Arm (b) has the same start, 1,080 superbatches,
  a short warmup and a decay toward about 1e-6 (shape and values to be
  measured, not adopted). Optionally (c): scratch at 1,080 superbatches,
  the fair control for §5.3. Compare *final* losses on a fixed, larger
  validation set, then FN or STC.
- Prediction: (b) beats (a) by ≥ 8e-5 and ≥ +5 Elo STC.
- Kill: < 4e-5, or an STC point estimate ≤ 0 over 3,200 games.
- Cost: no speed cost, existing data, about 6.5 h of GPU per arm.

**B2. Label quality and label age.** Confidence medium.
- Mechanism: the student tracks the labeller (b ≈ 0.31 per labeller Elo,
  §2.2). Half of g3s2 is S512-labelled. The 20k-node label depth was set
  for the bootstrap.
- Prediction: the next snapshot is g3s2 plus g3f plus g3g, about 1.6 B,
  with ~0.4 B new labels from S512+PP and S512ppr2. Retrained by the
  standard recipe it gains +10 to +20 STC. Refuted if < +5 or > +35.
- Cheapest experiments:
  - g3-only against g3s2 at equal samples (Kaggle only);
  - the 20k against 320k label-noise measurement on 100k positions (CPU,
    through jobctl, hours).
- Kill for relabelling: g3-only ≤ g3s2, and label-noise variance < 10%
  of the reducible loss.

**B3. Effective sample size is games, not positions.** Confidence medium
(strong at small scale).
- Mechanism: §7 H1.
- Experiment: idea 13's design (B0-sized nets, minutes of Kaggle each) on
  two short parts, save 25% against save 50% at equal saved labels.
- Prediction: +10 to +30 for 25% at the small-net scale. Refuted if ≤ 0
  with seeds within ±15.
- Cost: about 12 h of local data generation; they can run as the next
  parts.

**B4. Target design** (w = 0.5, loss form, scale). Confidence medium
that it is mis-set, low on the direction.
- Mechanism: §8 row 1. The KB records gains elsewhere from loss-exponent
  changes and λ scheduling (nnue-design.md §6.1-6.2; no values copied).
- Experiment: warm continuations differing only in w, or separately the
  loss exponent, scale-matched. FN 1,600 games, then STC [0, 5].
- Kill: all within ±5 at FN; keep 0.5.
- Free side-fix: log the score-MSE and result-MSE components on the
  shared set.

**B5. Coverage censoring** (adjudication, table entry, openings, draws).
Confidence medium that gaps exist, low on Elo; possibly the most
TCEC-relevant item.
- Cheapest measurement, no training: histograms of phase, |eval| band and
  material signature, training positions against Fork's own SPRT games
  (measurement only; test games never train).
- Prediction: some band is under-represented by > 3x (refuted if all are
  < 1.5x).
- Then: longer adjudication plies in the next part if the post-advantage
  band is thin; the 2026-09 book; later a 6-7 piece boundary slice (idea
  11).

**B6. Decision methodology.** Confidence high that it is a problem; the
Elo cost is indirect.
- Problems: a 20k-position, single-file, same-distribution validation
  set; best-of-360 selection; non-interleaved runs before g3s2; a 4e-5
  threshold below most measured spreads.
- Free fixes: a fixed 200k multi-source validation set plus a quiet
  subset; final and EMA losses; always `--interleave`; compare only
  like-for-like regimes.
- Example of the risk: S512r3 was skipped on a 3.3e-5 difference (it was
  probably no better anyway).

**B7. Architecture capacity under the speed constraint.** Confidence high
on the constraint.
- At k ≈ 152 per e-fold, every input family must pay 152·ln(1/r) at FN.
- Links (search-invisible, incremental, 0.895) passed. Inputs recomputed
  at every evaluation (exposure, contacts) did not.
- Consistent directions (INFERRED; for Phase B to judge):
  - capacity with no per-move work (small post-accumulator or output-side
    layers);
  - incremental inputs that encode search-invisible structure;
  - king regions retried as zero-initialised widening from S512ppr2. A
    region delta at 0 reproduces the parent. At about 0.96x nps the
    hurdle is about 6 Elo FN. Data is now about 22 M touches per row,
    above design-accuracy.md §2.1's 12.8 M anchor (COMPUTED for 1.24 B
    positions).
- **First, a free check:** measure nps ratios *on a GitHub runner* (both
  builds interleaved in one job) to test §4.2's hypothesis 1. Every speed
  gate number so far is from the X3D.
- Kill for any new input: FN gain < 152·ln(1/r) + 5.

**B8. Quantization (QAT).** Small. S512ppr2's quantization loss is max
7.9 / p99 6.1 / mean 2.0 cp; expected gain ≤ 3 Elo (INFERRED). Keep it for
int8 or wider designs.

---

## 10. What I could not verify

- Whether g3s2-val.vf's first 20,000 kept positions include the five new
  sources (§3.2).
- Every nps ratio on GitHub's runners (§4.2). The round-1 ratios were not
  A/B measurements.
- The irreducible share of the validation loss, and today's label noise at
  20k nodes.
- The split-search share of g2s1 (~41%, inferred).
- Why validation lies below training loss at scale.
- The self-play inflation ratio (~1.7x; the two gauntlets used different
  anchor sets).
- The slice's and interleaving's shares of S512ppr2's +20.1 (no ablation).
- Whether a longer low-LR schedule keeps improving (B1's central
  prediction).
- Any statement about other engines' recipes beyond the KB's. No engine
  source was opened, and no other engine's constants are quoted.


---

# Appendix A2. Search evidence

## A2: search evidence, Phase 3 and Phase 4 (think tank, Phase A)

**Summary.** Fork's search today is a clean, conventional tier-1 core
(PVS, aspiration, TT, QS with SEE, RFP, NMP, a bare log-log LMR, a linear
LMP, futility, SEE pruning) plus six tier-2 adoptions that together
measured about +68 Elo at STC on the networks (SE +14.1, multi-cut +9.2,
reply +11.5, follow +7.2, take +4.5, IIR +21.5) and two bootstrap-era LMR
check terms (+11.3, +4.2). Every attempt to **prune or reduce more from
static or shallow evidence** has failed or been null (negative extension
−8.7, LMR history −10.8, rising RFP −3.8, ProbCut −5.3, qs-delta −0.4,
B-4 −4.1, RfpMargin 40 bad in a gauntlet), while **searching more where it
matters or ordering better** has paid. Three mechanisms explain most of
the failures better than "the idea does not work for Fork": (1) every
reduction is in **whole plies**, so adjustments are coarse step functions
that fire only at extremes; (2) the move-ordering histories **persist for
a whole game with no decay**, so history-gated terms calibrated on
fresh-state benches and measurements behave differently in games; (3) the
**label-and-sweep proxy** used to pick constants is structurally biased
to "off" (no search change has ever scored above "off"; its ranking of
five SPRTed features correlates at ρ ≈ −0.3 with their SPRT results, and
the fifty-move measurement was mostly a score-scale artifact). The
eval-dependent margins are still bootstrap-era values in bootstrap
centipawns; mean-|eval| matching has held the scale roughly constant
since S512, so the margins do not drift much from net to net, but they
were never refit after the bootstrap → NNUE change or to the net's error
distribution. Time management is entirely static (no node share, no
stability, no score trend), the clearest long-TC gap, and Fork's own test
controls (base/increment = 100) cannot see TCEC's shape (30'+3",
base/increment = 600). Ranked opportunities are in section 7.

Labels used below: **[read]** = taken from a file (cited); **[inferred]** =
my reasoning from the evidence; **UNVERIFIED** = not checked.

---

## 1. Inventory of the current search (phase-4 at a24d41f)

Source: `src/search/searcher.cpp`, `searcher.hpp`, `lmr_table.hpp`,
`quiet_history.hpp`, `move_selector.cpp`, `time_budget.cpp`,
`trans_table.hpp`, `src/tune/params.hpp`; provenance from DESIGN.md §5.2
"Search constants" (lines ~2061-2125) and the tier-2 branches' copies of
that table. **[read]**

"Era" = the evaluator the constant was set under. "Units" = whether the
value is in eval centipawns (scale-dependent) or material/plies/counts.

### 1.1 On (default)

| Feature | Constants (default) | Provenance | Era | Units |
|---|---|---|---|---|
| Fail-soft PVS, iterative deepening | — | SPRT +109.8 (bootstrap) | bootstrap | — |
| Aspiration windows | MinDepth 5, HalfWidth 12 cp; widen by \|score − previous\| | **measured** on bench score changes (p90) | bootstrap | **eval cp** |
| Mate distance pruning | — | not SPRTed (exact) | — | — |
| TT (5 × 12-byte entries / 64-byte bucket), cutoffs non-PV only, depth ≥ | lexicographic victim policy | spec; TT-PV bit stored but **unused** | — | — |
| TT-refined pruning eval (`UseTtEvalRefine`) | — | SPRT stopped undecided (+14.6 ± 17.8, 1,000 g); owner exception, never verified | bootstrap | — |
| QS: captures + queen promos, all evasions; SEE ≥ 0 filter; stand-pat | — | QS +281; SEE-in-QS +9.5 ± 7.3 inconclusive | bootstrap | — |
| Move ordering: TT, good captures (victim·8 + take history), quiets (butterfly + reply·6/4 + follow·4/4), bad captures | HistoryMax 10000, bonus 12.5·d² cap 1250, malus = bonus | bonus/cap **reasoning**; weights **measured** (mean cutoff index, S-512) | S-512 | counts |
| History persistence | cleared only at ucinewgame / Clear Hash; **no decay between moves** | spec | — | — |
| RFP | MaxDepth 6, margin **80 cp/ply**, returns the full prune_eval | lower bound **measured** (fail-low share), value by reasoning; Berserk match credited; 40 reverted after a gauntlet | bootstrap | **eval cp** |
| NMP | MinDepth 3, R = d/2 + 1 + min(surplus/300, 2); no verification | **reasoning** (300 = bootstrap knight) | bootstrap | **eval cp** |
| LMR (quiets only; first 3 moves exempt) | MinDepth 3, MinMove 4, round(log2 d · log2 m / 4.5), clamp [1, d−1]; no PV, cut-node, history, improving or capture terms | MinMove from cutoff stats; divisor by **reasoning** (anchors) | bootstrap | plies |
| LMR check relief | 1 ply | unit; +11.26 ± 5.54 (bootstrap); removal on S512r2 −3.16 ± 2.86 (undecided, kept) | bootstrap / S512r2 | plies |
| LMR on quiet evasions | normal reduction | +4.21 ± 2.89 (bootstrap); removal test never run | bootstrap | — |
| LMP | MaxDepth 4, **12 + d** quiets (linear) | **measured** cutoff-index histogram (butterfly history only, bootstrap) | bootstrap | counts |
| Futility (parent, quiets; checking quiets kept) | MaxDepth 6, **100 + 70·d cp** | **reasoning** | bootstrap | **eval cp** |
| SEE pruning | MaxDepth 6, quiets −60·d, captures −100·d | reasoning | bootstrap | material cp (scale-free) |
| Singular extension (+1) / multi-cut (return bar) | MinDepth 6, EntrySlack 3, margin 6 cp·d, test at d/2 | **measured** (flagged-move precision, S-512); Stockfish 11 near match credited | S-512 | **eval cp** |
| IIR (all node types, after node pruning) | MinDepth 8 | proxy said "below off"; SPRT +21.45 STC, +26.25 LTC | S512r2 | plies |
| Syzygy WDL in search, DTZ at root | ProbeMinDepth 1 | +17.5 ± 7.2 | bootstrap | — |
| Forced-move stop | 1/8 of soft | derived from growth 1.66 | bootstrap | — |
| Time budget | share = (clock − overhead)/30 + ¾·inc; soft = share, hard = 4·share ≤ 0.9·clock; danger-zone reserve; no new iteration if elapsed·5/3 > hard | **reasoning**, "measured in Phase 5"; shape credited to Berserk | bootstrap | ms |

### 1.2 Off (switch exists or on a branch)

Negative extension (H0), LMR history term (H0), rising RFP (H0),
threat-aware ordering (H0), ProbCut (H0), pawn drift table (undecided at
LTC), fifty-move scaling (measurement only), qs-delta (inconclusive),
TT age blend / keep-exact / keep-deeper (inconclusive), B-3/B-4/root
fail-high fix (reverted). Batch 4 on `tier2/batch4`, all placeholders:
razoring (`HorizonDrop*`), quiet history pruning (`HistorySkip*`),
bad-capture futility, malus balance, double extensions, cut-node and
PV-trace LMR, pawn-structure history, upcoming repetition. **[read]**

### 1.3 Absent entirely

No improving flag in any use; no expected-node-type tracking; no use of
the TT-PV bit; no LMR for captures; no history, PV or cut-node term in
LMR; no killers or countermoves (by design, DESIGN.md §5.2 "Out of
scope"); no continuation history deeper than 2 plies; no correction
history; no QS futility; no NMP verification; no dynamic time management
of any kind. **[read]**

### 1.4 Constants tuned under the bootstrap evaluator and never refit

AspirationHalfWidth 12 cp and MinDepth 5; RfpMargin 80 and RfpMaxDepth 6;
NullSurplusPerPly 300 (explicitly "the bootstrap knight value") and
NullSurplusPliesMax 2; FutilityOffset 100, FutilityGrowth 70,
FutilityMaxDepth 6; LmpQuietAllowance 12 (measured with butterfly-only
ordering, before the pair tables cut the mean cutoff index from 0.650 to
0.579, DESIGN.md `FollowWeight` row); LmrMinMove 4 (bootstrap cutoff
stats); the LMR divisor; IterationGrowthThirds 5 (growth measured at
depths 8-14 before tier 2 and the NNUE); every time-budget constant. SE's
three constants were measured on S-512 (S = 101), two nets and about
+200 Elo of eval ago (S512 → S512r2 +151, → S512+PP +32.7, → S512ppr2
+20.1). **[read]** DESIGN.md §5.6 owes the SPSA retune of all of them.

---

## 2. What worked, what failed, and why

### 2.1 Adopted, with sizes (STC 8+0.08 unless noted) [read]

| Change | Result | Games | Notes |
|---|---|---|---|
| Tier 1 as a block (bootstrap) | +439 STC, **+555 LTC** | 318 / 306 | pruning value grows with TC |
| SEE pruning | +21.2 ± 10.1 | 3,042 | |
| Syzygy probing | +17.5 ± 7.2 | 5,000 | |
| LMR check relief (bootstrap) | +11.26 ± 5.54 | 9,600 | on S512r2 its removal costs −3.16 ± 2.86 (20,800 g): value shrank about 3-4× |
| LMR on quiet evasions (bootstrap) | +4.21 ± 2.89 | 35,200 | never re-checked on a net |
| Singular extension | +14.12 ± 6.55 | 4,800 | bench nodes +30% |
| Multi-cut (on SE) | +9.19 ± 4.62 | 9,600 | ends 24% of singular tests |
| Reply table | +11.46 ± 5.57 | 6,400 | |
| Follow table | +7.22 ± 3.92 | 12,800 | |
| Take history | +4.53 ± 2.99 | 22,400 | |
| IIR (d ≥ 8, every node type) | **+21.45 ± 5.98 STC, +26.25 ± 6.65 LTC** | 4,800 / 3,328 | bench nodes −21%; proxy predicted a loss |
| Futile-node quiet filter (speed) | +11.5 ± 11.9 on [−3, 0] | 2,000 | +12.7% nps |

Sum of the tier-2 adoptions on networks: about +68 STC, measured
sequentially on top of each other, so roughly additive by construction.

### 2.2 Failed or null, with the best mechanistic explanation

**Negative extension (T30): −8.73 ± 4.98, 8,000 games, H0.** Fork's form
fires at *every* non-PV node whose TT score is ≥ beta when the singular
test is neither singular nor a multi-cut, and takes a whole ply off the
TT move: bench nodes −28%. [read] Mechanism [inferred]: the TT move at such
a node is the likely cutoff move; cutting a full ply from the one move
that carries the node, at expected all-nodes as much as cut-nodes (Fork
has no node types), is a large, ungated loss of verification depth. The
KB (§3.21) says the gating (cut-node form) is decided by experiment;
Fork had nothing to gate with, and no fractional amount to try. Overlap:
multi-cut already harvests the strongest "others also beat beta" cases.
Not evidence against a cut-node-only or fractional form. Note: the rule at
the time asked for an LTC retest of an STC failure in extensions/
reductions before rejection; none was run (DESIGN.md Testing setup, "Until
2026-11-06 ..."). [read]

**LMR history term (T16): −10.81 ± 5.01, 6,400 games, H0.** [read] The
term subtracts `order_score / 24000` (integer division) from the base
reduction; the summed ordering score spans about ±35,000, so the term is
nonzero only when |score| ≥ 24,000, i.e. when all three tables are near
saturation in the same direction. On the bench (histories cleared per
position) it changed only 0.27% of nodes (14,180,299 → 14,141,348). An
11-Elo loss from a change touching 0.3% of bench nodes is an **anomaly**.
Three candidate mechanisms [inferred]:
1. **History persistence.** In games, histories are never cleared or
   decayed between moves (session.cpp clears only on ucinewgame/Clear
   Hash), so after dozens of moves many entries sit near ±10,000 and the
   term fires far more often than on the bench or in the measurement
   (which searched every position "from a fresh state"). It then acts on
   stale, saturated values. This would make both the bench and the
   measurement blind to the term's real effect. Testable cheaply (§7, O3).
2. **Asymmetry.** High-history quiets are ordered early, mostly before
   `LmrMinMove`, so in practice the term mostly *adds* a ply to
   bad-history late moves: a net increase in reduction, the direction
   every other failure shares.
3. **Speed.** The test build computes `quiet_order_score` (three table
   reads, two of them in 1.2 MB pair tables) for every quiet made, not
   only for LMR candidates, duplicating the selector's work
   (`score_quiets` is 1.8% of the profile, perf-log). Probably 1-2% nps
   [inferred, unmeasured]; at 1-3 Elo per 1% nps that is 1-6 Elo.
The measurement (fitness rising toward "off" as the term weakens, 24000 at
the grid's weak edge) agrees in sign but cannot separate these.

**Rising RFP (T18 in RFP): −3.78 ± 2.92, 19,200 games, H0.** [read] Form:
margin `80·d − 25` when the raw static eval beats the eval two plies back;
bench −5.9% nodes. Mechanism [inferred]: it is a one-sided loosening, not
a re-partition. RfpMargin 80 was set (and kept against 40) as an average
over improving and non-improving nodes; relieving it only on improving
nodes raises the overall prune rate, which is the direction that loses
for Fork (RfpMargin 40's gauntlet). The flat 25 cp is 31% of the margin
at d = 1 and 5% at d = 6, so it acts almost only at the shallowest,
most numerous nodes. It also compares raw evals while RFP uses the
TT-refined `prune_eval`, so the flag and the pruned quantity disagree.

**ProbCut (T31): −5.29 ± 3.58, 12,800 games, H0** (d9-r5-m80, measured
below "off"). [read] Mechanism [inferred]: **overlap**. ProbCut, NMP and
multi-cut all cut fail-high nodes; with multi-cut already returning a
verified lower bound at 24% of singular tests, ProbCut's marginal nodes
are the ones the others decline, at the cost of a QS probe per
qualifying capture. Its depth and reduction sat at the top of their
grids (min depth 9, the probe 6 plies below the node), i.e. the
measurement was pushing it toward "almost never fires". A margin of 80 in
a grid of 50-500 is at the tight end; at S512r2's eval quality a tight
ProbCut margin is exactly the eval-gated aggression that keeps losing.

**Threat-aware ordering (T56, cheaper-attacker buckets): −6.08 ± 3.59,
12,800 games, H0.** [read] Bench −6.4% nodes. Mechanism [inferred]: (a)
cost: `attacked_squares` per node that reaches quiets, and a butterfly
table grown 16 KB → 64 KB (out of L1); (b) **dilution**: four buckets split
each move's updates four ways, which matters most for a history that is
already sparse relative to the pair tables; (c) overlap with the reply
table, which already encodes "what the opponent just did" (a new attack
is usually the last move). A history split only pays if its information
exceeds what the existing 1-ply table carries.

**Quiescence delta pruning: −0.40 ± 2.93, 27,200 games, inconclusive** on
B0r1 with a bootstrap-measured 150 cp slack. [read] Near zero is the
expected value for QS pruning at Fork's speed profile (eval is 41.5% of
the profile, so pruned QS captures save little relative to the risk).

**Fifty-move eval scaling (T52): measurement only; "every span lost to
off", best −0.199.** [read] This number is **not evidence of harm**
[inferred, strong]: the measurement scored positions with halfmove clocks
20-99 by agreement with labels from the scaling-off engine and by
|score − label score|. Scaling the eval by (span − clock)/span shrinks
every reported score (score error grows ∝ |score|·clock/span) and makes
the engine prefer clock-resetting moves (disagreement with the "off"
labeller): both terms penalize the feature's intended behaviour, and the
loss "shrinks toward off as the span grows", exactly as a pure scale
artifact would. The owner closed it with no retest; if it is ever
revisited it needs a game test, not this proxy.

**Pawn drift table (T32): −0.35 ± 3.72 at LTC, 9,984 games, undecided;
off.** [read] It learned slowly (an update moves min(d, 4)/256 of the
way; the grid's edge in both directions) and cut the passive prediction
error by only about 8% (fitness 0.919). Mechanisms [inferred]: (a) a
small error reduction gives a small Elo effect: the interval (nElo −7.5
to +6.2) is consistent with +1-2 Elo; (b) the **pawn** table is the weakest
correction feature, and since S512+PP the net itself has 608 pawn-link
inputs, so the systematic pawn-structure error it targets has partly
moved into the eval; (c) at one thread it lacks the shared-table gain the
KB reports for many threads (Phase 6).

**Bootstrap-era reverts (Phase 3).** [read]
- *Root fail-high fix* (play an unresolved root fail high at the stop):
  −14.6 ± 10.8 at 2,000 games. Mechanism [inferred]: a zero-window fail
  high of a non-first root move under a weak eval often collapses on its
  re-search; playing it trades a verified move for an unverified one.
  With a stronger net the share that holds should rise (idea 29's
  measurement, never run). The better fix is a time decision, not a move
  decision (§4).
- *B-3* (re-search a root fail high one ply shallower): +0.65 ± 3.56 at
  22,400 games, null.
- *B-4* (QS stand-pat refined by the TT bound): −4.11 ± 3.93, H0. Probably
  a feedback loop: most QS TT entries are depth-0 QS results, so the
  "refinement" recycles the QS's own window-dependent bounds [inferred].
- *RfpMargin 40*: 156.0/357 against Milestone C's 178.5 on the same games
  (about −44 Elo, ~2 SE), while the fail-low-share measurement called every
  margin 40-160 safe.
- *Keep-deeper* (LTC −5.1 ± 10.1), *age blend* (LTC +5.7 ± 13.8),
  *keep-exact* (−0.6 ± 7.5): unresolved, low table pressure at 64 MB.

---

## 3. Patterns

### 3.1 Over- or under-pruned?

Evidence, grouped by direction [read]:

| Direction | Changes | Results |
|---|---|---|
| Prune/reduce more on static or shallow evidence | negative ext., LMR history (mostly), rising RFP, ProbCut, qs-delta, B-4, RfpMargin 40 | −8.7, −10.8, −3.8, −5.3, −0.4, −4.1, gauntlet −44 |
| Prune more, but verified by a search | multi-cut | +9.2 |
| Reduce where ordering is known bad, then re-search next iteration | IIR | +21.5 / +26.3 LTC |
| Search more on forcing or singular lines | SE, check relief | +14.1, +11.3 (now ~+3) |
| Order better | reply, follow, take | +11.5, +7.2, +4.5 |
| Order differently at a cost | threat buckets | −6.1 |

Reading [inferred]: in the **eval-gated** dimension (RFP, futility, NMP
gate, ProbCut, QS delta) Fork is at or past the point where its eval
supports more aggression; every loosening lost. In the **late-move**
dimension Fork is structurally *simple* rather than demonstrably over- or
under-reduced: LMR has no history, node-type, PV or capture terms, and
LMP is linear and loose (13 quiets at depth 1). The one late-move
adjustment that failed (LMR history) has implementation-specific
explanations (whole plies, persistent history, cost). So the defensible
statement is: **Fork is not under-pruned on static evidence; its LMR is
under-informed, not under-reduced.** Selectivity that adds information
(a search, a TT move, an ordering signal) has paid; selectivity that only
trusts the static eval more has not.

Why would the static eval not support more aggression after +500 Elo of
net improvements? [inferred] (1) The margins were never refit, so "more
aggression" was always tested as a perturbation of bootstrap-era values,
by one-sided reliefs; the optimum may lie on a different shape (e.g.
tighter at low depth and looser at high depth), which one-sided tests
cannot find. (2) Fail-soft returns: RFP returns the full `prune_eval`,
NMP its raw score; looser pruning then also injects more inflated bounds
into the TT (the KB, §3.16, lists return-value variants as a separate
gain). (3) What the fail-low-share measurement checks (is the pruned node
also a fail-high at the same depth?) is not what costs Elo; RfpMargin 40
passed that check and still played worse.

### 3.2 Do margins drift with S?

- **Since S512, little.** Each promoted net's S is chosen to match the
  previous default's mean |eval| on a shared validation set (S512 101 →
  S512r2 92 → S512+PP 90 → S512ppr2 89; mean |eval| about 217-226 cp at
  each step; docs/nets.md). [read] So a margin in cp means roughly the same
  fraction of the eval's spread from net to net.
- **The bootstrap → NNUE step was not matched.** Bootstrap cp are
  Shannon material units; B0 used the trainer's S = 134, B0r2 S = 105 fit
  by `fit_scale.py` to the data. The margins (RFP 80, futility 100 + 70d,
  NMP 300, aspiration 12) were set in bootstrap units and carried over.
  Whether bootstrap's spread resembled ~220 cp mean |eval| is UNVERIFIED.
- **Matching mean |eval| is not matching what a margin needs.** A
  pruning margin should scale with the spread of (search result − static
  eval) at that depth, i.e. with the eval's *error*, not its magnitude
  [inferred; this is Buro's ProbCut model, see O4]. A better net keeps
  mean |eval| fixed while its error shrinks (for example S512ppr2
  misjudges 8 of 900 endgame-check positions against S512r2's 249; the
  head-to-head chain S512 → S512ppr2 is about +200 Elo), so fixed margins
  become relatively looser as nets improve. The aspiration window (12 cp)
  depends on iteration-to-iteration score noise, which also changes with
  the eval. Neither has been measured on any net.
- Measurements of Fork's eval error exist only indirectly: the drift
  measurement's p99 |exact result − raw eval| < 280 cp at 200,000-node
  searches (S512r2), and score errors of 24-26 cp between 0.25-2.5 M-node
  searches and 25 M-node labels. [read]

### 3.3 Bench nodes depend on the net, not just on the search

The same search gives bench 17,102,670 (bootstrap), 14,180,299 (S512r2),
13,909,380 (S512+PP), 14,626,377 (S512ppr2). [read] The tree shape (and so
every margin's effective prune rate) moves with each net, another reason
the margins need per-net calibration rather than a one-time retune.

---

## 4. Time management

**What Fork does** [read, time_budget.cpp; searcher.cpp]: share =
(clock − overhead)/30 + ¾·increment; soft = share, checked only between
iterations; hard = 4·share capped at 0.9 of the clock; a danger-zone
reserve; no iteration starts if elapsed·5/3 exceeds the hard limit; a
forced move stops at 1/8 of soft; with movestogo, clamp to 40.

**What has been tested** [read]: deliverable 8 at STC (d8-final +1.9 ±
10.6, accepted on non-regression after 2,202 games, plus stress tests:
B2 0 time losses in 2,000 games at 2+0.02 under load); its LTC run
(d8-ltc) stopped inconclusive at −4.7 ± 18.0 over 590 games, with "the
iteration rule is the first thing to check" recorded; B-1 forced-move
stop (+0.96 ± 3.54, kept). Hash 256 vs 16 MB at LTC and the 60+0.6
time-scaling gauntlet (idea 25) were queued and never run.

**What is untested** [read]: every constant (30, 40, 4, 1/10, ¾, 5/3) is
"reasoning; measured in Phase 5"; no dynamic term exists (no node share,
no best-move stability, no score trend, no fail-high resolution).

**Derived properties** [inferred]:
- *Overspend.* With geometric iteration growth g and the soft limit
  checked only between iterations, the finishing time over the soft
  limit is g^U with U ~ Uniform(0, 1) in log terms, so its mean is
  (g − 1)/ln g. For Fork's measured median g = 1.66 that is **1.30×
  soft** (up to 1.66×, more at p90 g = 2.38). Fork effectively plans
  ~23 moves ahead, not 30, and the spend per move is noisy by ±30% for
  reasons unrelated to the position.
- *Shape at TCEC.* At 30'+3" (base/increment 600) Fork's clock decays
  toward about 7.5 increments (KB time-management.md §3: ~22.5 s), so
  late in TCEC's long games a move gets ~20× less time than in the
  opening. Every Fork test runs at base/increment = 100 (8+0.08,
  40+0.4), where the increment dominates much sooner. **No test Fork runs
  can see the allocation question TCEC poses** (how much of the bank to
  spend before the game becomes increment-bound).
- *Root fail highs.* The −14.6 result says "do not play an unresolved
  fail high"; the complementary policy, "do not stop while a root fail
  high (or fail low) is unresolved, within the hard limit", has never
  been tried. Fork already continues a running iteration to the hard
  limit; the gap is the *soft* stop between iterations and the iteration
  rule, which can stop with a fresh fail high pending.
- *The data is already there.* `root_moves_[i].nodes` and `.share` are
  computed every iteration (searcher.cpp ~800) but feed only idea 23's
  LMR context. A node-share term needs no new bookkeeping.

The KB (time-management.md §4.4, §7) ranks node share first: across about
ten engines it is "the largest and most consistent gain of any dynamic TM
term", holding or growing at 40+0.4; stability and score trend are next.
[read; KB survey, other engines' results]

---

## 5. Long-TC evidence and scaling with depth

| Evidence | STC | LTC | Reading |
|---|---|---|---|
| Tier 1 pruning block (bootstrap) | +439 | +555 | selectivity value grows with depth [read] |
| IIR | +21.45 ± 5.98 | +26.25 ± 6.65 | at least as large at LTC [read] |
| XGR-512 (net, slower) | −34.42 ± 11.88 | −30.56 ± 9.96 | the speed penalty of a 0.8-0.9× net barely shrinks at 5× the time [read] |
| Pawn drift table | not run | −0.35 ± 3.72 (9,984 g) | undecided; interval allows +3 [read] |
| d8 time management | +1.9 ± 10.6 | −4.7 ± 18.0 (590 g) | inconclusive [read] |
| TT keep-deeper / age blend | — | −5.1 ± 10.1 / +5.7 ± 13.8 | unresolved at 64 MB [read] |

Depth scaling inside measurements [read]: SE's flagged-move precision
rises with depth (0.91 at d6, 0.97-0.98 at d7-12), so singular decisions
get more reliable deeper (scaling-positive, consistent with the KB's
"extensions gain more at LTC"); IIR cuts time to depth 14 by 21%; the
LMP and RFP measurements were per depth 1-6 only. Iteration growth
(1.66 median) was measured at depths 8-14 on the bootstrap; at TCEC
depths (30+) and with tier 2 it is unknown.

LTC games are lower-variance per pair: the drift LTC run's pentanomial
[62, 1224, 2447, 1180, 79] gave nElo ± 6.82 over 9,984 games while Elo
± was 3.72; an LTC stage resolves about as finely per game as an STC
stage despite the draws. [read]

**Consistency note** [read]: Testing setup's "straight to LTC" list
includes all extensions and capture history; SE, multi-cut and take
history were adopted on STC passes and have no LTC confirmation; §5.6
lists "none outstanding" (owner's 2026-11-06 policy). The only LTC search
confirmation is IIR's.

---

## 6. Pre-SPRT signals that mispredicted

1. **The label-and-sweep proxy** (agreement with 25 M-node labels by the
   *feature-off* engine minus capped score error, at 0.25 M and 2.5 M
   nodes from a fresh state). [read] It never scored any search change
   above "off" (IIR, LMR history, rising RFP, ProbCut, threat sets,
   fifty-move scaling). Gap vs SPRT for five SPRTed features: IIR
   −0.0068 → +21.5; LMR history −0.0016 → −10.8; ProbCut −0.0049 → −5.3;
   rising RFP −0.0146 → −3.8; threat −0.0162 → −6.1. Spearman ρ between
   the proxy gap and the SPRT Elo is **−0.3** (n = 5) [computed]. Why
   [inferred]: (a) labels from the "off" engine count any change of move
   choice as an error, so the proxy measures *similarity to the
   baseline*; (b) fresh-state searches remove history and TT carry-over,
   which games have (see LMR history); (c) the score-error term penalizes
   any feature that legitimately rescales scores (fifty-move scaling);
   (d) agreement on near-equal moves is noise for Elo. The streamlined
   policy (SPRT ladders) already moved away from it for constants; **idea
   23's evaluator funnel still uses exactly this proxy** (DESIGN.md
   §5.2, 8c) and would inherit the bias.
2. **Bench node counts.** IIR −21% nodes → +21; negative extension −28% →
   −8.7; threat buckets −6.4% → −6.1; rising RFP −5.9% → −3.8; LMR
   history −0.3% → −10.8. No relation. [read]
3. **The RFP fail-low share** (Phase 3): every margin 40-160 below 0.37%
   wrong; 40 then lost about 44 Elo in the paired gauntlet. [read]
4. **Fixed-node screens for slower nets** (nets, but the same lesson for
   search features with a speed cost): S512+X +25.7 → −30.0 STC; XGR +30.7
   → −34.4; AF-S +10.4 → −55.9; H-512 (round 1) +32.2 → −24.4; only
   S512+PP (+46.1 → +32.7) survived. [read] Any search feature with a
   per-node cost is exposed to the same conversion, and no failed search
   feature had its nps measured (qs-delta: "the nps change was not
   measured").
5. **What predicted well** [read]: the mean-cutoff-index metric for
   ordering weights (reply 6, follow 4, take 4: all three passed); SE's
   precision rule (6/6/3: passed); the LMP cutoff histogram. These
   measure the *mechanism* directly (ordering quality, decision
   precision) instead of end-to-end agreement with a biased label.

---

## 7. Ranked bottlenecks and opportunities

Ranked by expected Elo at long TC per unit of effort, with confidence.
Every number proposed here is a placeholder to be measured.

### O1. Dynamic time management: node share first, then stability and fail-high resolution — **high value, medium-high confidence**

- **Mechanism.** After each iteration, scale the soft limit by how much of
  the iteration's nodes went to the best root move: a dominant move
  (alternatives refuted cheaply) stops early, a contested root gets more.
  Second, do not stop at the soft check while the last iteration ended
  with the best move changed or a root fail high pending.
- **Model.** Fork's spend is 1.30× soft on average for reasons unrelated
  to the position (§4). Re-allocating the same total by root difficulty
  is a pure allocation gain. The KB survey (time-management.md §4.4) lists
  node-share gains across about ten engines from a few to about 20 Elo at
  STC, holding at 40+0.4, and stability gains of a few Elo; Fork, with
  *no* dynamic term, sits at the low-hanging end. Expect **+5 to +12 at
  STC, at least as much at LTC** [inferred].
- **Literature.** KB time-management.md §4.2-4.4 (Hyatt 2013 thread;
  Šolak and Vučković 2009); the node-share idea's lineage as recorded
  there. Credit in ORIGINALITY.md before building.
- **Prediction.** STC [0, 3] passes within 2-4 stages; refuted if H0 at
  STC *and* an LTC run is ≤ 0.
- **Fit.** The counts already exist (`root_moves_[i].nodes`, `.share`);
  the change is in the iterative-deepening loop only, deterministic in
  nodes, outside bench (`go depth`).
- **Cost and first experiment.** Zero nps. A ladder of two slopes for the
  share factor at STC (2 stages each), then STC SPRT and LTC (time
  management belongs on the LTC-sensitive list). **Kill:** H0 at both
  ladder values. This was "Phase 5" in the roadmap; it should precede the
  SPSA retune because every later LTC test and TCEC itself plays with it.

### O2. Fractional depth, then the LMR adjustments re-done in sub-ply units — **medium-high value, medium confidence**

- **Mechanism.** Every Fork reduction and extension is whole plies, so an
  adjustment is a step: `order_score / 24000` is nonzero only beyond
  ±24,000 of a ±35,000 range; check relief is a full ply. Idea 43's
  refactor (1/64 ply) lets the history term, node-type terms, PV terms
  and the check relief act continuously.
- **Model.** The KB (§3.13) ranks history, expected-cut-node and gives-check
  as the best-evidenced LMR adjustments in other engines; Fork has one of
  them. With continuous terms, each adjustment moves the average
  reduction by a fraction of a ply over many nodes instead of a whole
  ply over a few. Expect the fractional base alone ≈ 0 to +3, a centred
  history term +3 to +8, cut-node +2 to +6 [inferred].
- **Prediction.** After the bench-identical refactor, a centred
  (mean-zero over late moves) fractional history term passes [0, 3];
  refuted if both ladder values reach H0.
- **Fit.** Already planned (idea 43, §5.6 item 10) and designed; this
  evidence argues for moving it ahead of batch 4's LMR items (cut-node and
  PV-trace LMR are whole-ply placeholders today) and re-running LMR
  history in its centred fractional form rather than closing it.
- **Cost.** Refactor 2-3 days; zero nps if done as designed. **Kill:** the
  refactor itself is kept regardless (it serves SPSA); the uses die by
  their SPRTs.

### O3. Diagnose history persistence before any history-gated pruning — **cheap, medium value, medium confidence**

- **Mechanism.** Histories are never decayed between moves. Terms gated
  on history magnitude (LMR history, batch 4's quiet history pruning
  `HistorySkipPerPly`, the malus balance) are calibrated on benches and
  measurements that clear histories, then played in games where values
  drift toward saturation and go stale as the position changes.
- **Model.** If the share of LMR sites with |order score| ≥ 24,000 is
  several times higher at move 30+ than on the bench, the LMR history
  SPRT's −10.8 on a 0.3%-of-nodes change is explained, and every
  history-threshold constant needs in-game calibration.
- **Prediction (NOVEL for Fork's process).** In 20 stats-build self-play
  games, the fraction of LMR sites with |score| ≥ 24,000 at moves 30-60
  is ≥ 5× the bench's. Refuted if it is within 2×.
- **Follow-up if confirmed.** (a) A per-search history scale-down at
  each `go` (a fraction to be laddered; 1 = today's behaviour), SPRTed on
  [0, 3]; (b) calibrate batch 4's history thresholds on in-game
  distributions.
- **Cost.** One stats build, an hour of local CPU at low priority, no
  GitHub. **Kill:** distribution matches the bench → drop the
  hypothesis and attribute LMR history's loss to cost/asymmetry
  (measure its nps with bench/ab.py, also cheap).

### O4. Calibrate eval-gated margins from Fork's own error distribution, per net — **medium value, high confidence that a retune is owed**

- **Mechanism.** Buro's ProbCut model: a shallow value predicts a deep
  one with a linear fit and residual σ; a margin should be a quantile of
  that residual. Log, at RFP/futility/NMP-candidate nodes on the current
  net, (search result at depth d − prune_eval) by d, and express each
  margin as a quantile of that distribution.
- **Model.** If σ_d at d = 1-6 is well below what 80·d implies, RFP can be
  tightened at low depth and possibly loosened at high depth (a shape
  change one-sided tests could not find); same for futility's 100 + 70d.
  It also gives SPSA principled starting points and ranges, and an
  automatic refit after each net promotion (the nets change tree shape:
  bench 13.9-14.6 M with the same search).
- **Literature.** Buro 1995 (ProbCut; KB research.md); Jiang and Buro
  2003. Heinz 1998 on futility (KB §3.18).
- **Prediction.** The quantile-derived margins differ from the current
  ones by more than 20% in at least one depth band; refuted (and left to
  plain SPSA) if all are within ±15%.
- **Fit.** Fork's margins are bootstrap-era (§1.4); mean-|eval| matching
  holds magnitude, not error (§3.2). The measurement is a FORK_SEARCH_STATS
  counter plus a script, beside data generation.
- **Cost.** Local CPU only; the Elo arrives through the SPSA retune (§5.6
  item 12). **Kill:** quantile-margin SPRT H0 → keep SPSA's values.

### O5. Improving as a re-partition; RFP's return value — **cheap, low-medium value, medium-low confidence**

- **Mechanism.** Rising RFP loosened pruning on improving nodes only. A
  symmetric form (margin −x when improving, +x when not, x laddered)
  keeps the overall RFP rate about constant and tests only the flag's
  information. Separately, RFP returns the full `prune_eval`; returning
  beta or a blend toward beta limits inflated fail-soft bounds (KB §3.16
  lists return-value variants as a separate gain in several engines).
- **Prediction.** Each passes [0, 3] at +2 to +4; refuted by H0. The
  symmetric form should show bench nodes within ±2% of today (unlike
  rising RFP's −5.9%); if it does not, it is not a re-partition.
- **Fit.** Both are a few lines; the blend has no tuned constant if it
  returns beta or the midpoint.
- **Cost.** Zero nps; one ladder (two values) plus one SPRT each.
  **Kill:** H0 at both ladder values; no LTC.

### O6. Node types and the TT-PV bit (batch 4), then a gated negative extension — **medium value, medium confidence**

- **Mechanism.** Fork stores the TT-PV bit and never reads it, and has no
  expected-node type. Cut-node LMR, PV-trace LMR and IIR/NE gating all
  need them. Negative extension failed ungated and whole-ply (§2.2); its
  cut-node, fractional form is a different change.
- **Prediction.** Cut-node LMR passes [0, 3] (+2 to +6); PV-trace LMR is
  on the LTC-sensitive list; NE at cut nodes only, −½ ply after O2,
  passes or is null, never −8.
- **Cost.** Built on tier2/batch4 already (placeholders). Do it after O2
  so the amounts can be fractional. **Kill:** per SPRT.

### O7. Correction tables: skip pawn, try continuation/non-pawn later, share in Phase 6 — **medium value at LTC/threads, low-medium confidence now**

- **Mechanism.** The pawn drift table cut prediction error only ~8% and
  was undecided at LTC; S512+PP/S512ppr2 now see pawn links directly, so a
  pawn-keyed correction overlaps the net. Non-pawn and continuation keys
  target errors the net's inputs do not carry.
- **Prediction.** A continuation-keyed table cuts passive prediction
  error by more than the pawn table's 8% on the same 120-game method;
  refuted if ≤ 8%. Gains, if any, larger at LTC and with shared tables
  (KB §1 lesson 4).
- **Cost.** The owner has deferred these after SPSA (§5.6); the passive
  measurement (drift_measure.py's method) is cheap and can run first.

### O8. Test methodology for search and TM — **enabling; high confidence**

1. **A TCEC-shaped control for TM changes** (NOVEL for Fork): keep TCEC's
   base/increment ratio of 600 at affordable cost, e.g. 48+0.08 (6× STC
   cost, the STC increment, so the danger-zone behaviour is unchanged).
   Only time-management changes need it; 40+0.4 (ratio 100) cannot test
   allocation across the game. Prediction: AssumedMovesLeft and the
   increment share have measurably different optima at ratio 600 than at
   100; refuted if a two-value ladder of AssumedMovesLeft agrees at both.
2. **Record nps beside every search SPRT** (bench/ab.py on the two
   commits, 10 interleaved rounds). The implied STC slope from S512+X is
   ~3 Elo per 1% nps (§5.6 item 4 will measure it); at that slope a 2%
   cost decides a feature worth 3-5 Elo, and no failed search feature has
   an nps figure.
3. **Repair idea 23's proxy before its long run**: labels from a
   configuration the candidates are not perturbations of (a longer search
   by the *current default*, re-labelled after each adopted change, or a
   held-out stronger net), TT and history carried over across a game's
   positions instead of fresh state, and no score-error term for
   features that rescale scores. Validate the repaired proxy on the five
   known SPRT outcomes (§6) before trusting it: require at least the
   right sign on IIR and on two of the four failures.

### Lower priority (one line each)

- **LMP re-measured on today's ordering** (the 12 + d rule came from
  butterfly-only ordering; the pair tables cut the mean cutoff index
  10%): a stats-build histogram, then SPSA. Small, cheap. [inferred]
- **Double extensions** (batch 4, LTC-sensitive): SE's precision rises
  with depth, so extra extensions are scaling-positive by Fork's own
  measurement; after O2 they can be fractional.
- **Aspiration half-width** re-measured on the current net (same bench
  method as Phase 3); cheap, small.
- **Iteration growth** re-measured on the current search and at deep
  iterations before O1's tuning (it feeds the iteration rule and the
  forced-move fraction).
- **LMR for captures / TT-move-is-capture**: absent and not on any list;
  KB §3.13 lists both; wait for O2.
- **Killers/countermoves**: KB says marginal once histories are strong;
  not recommended.

### Summary ranking

| Rank | Item | Value (long TC) | Confidence | Cost |
|---|---|---|---|---|
| 1 | O1 node-share + stability + fail-high-aware stop | +5 to +12, more at LTC | medium-high | ~1-2 days, 0 nps |
| 2 | O2 fractional depth → centred history, cut-node LMR | +3 to +10 total | medium | 2-3 days + SPRTs |
| 3 | O3 history persistence diagnosis (gates batch 4's history items) | enabler; explains −10.8 | medium | 1 hour CPU |
| 4 | O4 error-quantile margins → SPSA | +3 to +10 via retune | high (owed), magnitude low | local CPU |
| 5 | O6 node types / TT-PV, gated NE | +2 to +6 | medium | built on batch4 |
| 6 | O5 symmetric improving, RFP return | +2 to +4 each | medium-low | trivial |
| 7 | O7 continuation/non-pawn correction (passive measure first) | +0 to +5, LTC/threads | low-medium | deferred |
| 8 | O8 methodology (TCEC-shaped TC, nps per SPRT, idea 23 proxy) | enabler | high | small |

---

## What I could not verify

- The nps cost of any failed search feature (LMR history's extra
  `quiet_order_score`, threat buckets, ProbCut): never measured; my 1-2%
  estimates are inferred.
- The in-game distribution of history magnitudes (O3's premise).
- Bootstrap eval's spread relative to the NNUE's ~220 cp mean |eval|
  (whether the bootstrap → NNUE step changed margin units by much).
- Iteration growth on the current search and at TCEC depths; Fork's
  actual mean spend over the soft limit (1.30× is derived from the
  Phase 3 growth median, not measured from game logs).
- Whether the SPRT shards' PGNs record depth/nodes per move (which would
  let nps and depth be read from existing SPRT games).
- The decomposition of the fifty-move measurement's −0.199 into score
  error and agreement (the scale-artifact reading is inferred from the
  method and the trend, not from the per-term numbers).
- Expected Elo for O1-O7 rests on the KB's survey of other engines'
  results and on my inference; none is a Fork measurement.


---

# Appendix A3. Speed, systems and testing-methodology evidence

## A3: speed, systems and testing methodology (Phase 4 think tank, Phase A)

**Summary.** Fork spends about 42% of its search time in the network
(accumulator update 17%, output layer 15%), 15% in move ordering, 13% in the
TT and 11% in move generation. That is the one profile taken in Phase 4
(perf-log 2026-11-06, S512r2 with IIR). Of seven speed candidates since, one
won (C4 select_best, +4.0%). The losers lost because the local machine
already hides the latency they targeted: a 96 MB L3, a 16 MB Hash and
refreshes at 2.5% of time. That same regime (native AVX-512 clang, an
L3-resident TT, one thread) is unlike both the SPRT shards (g++ x86-64-v3,
smaller caches) and TCEC (clang x86-64-v3 by update.sh's default, no PGO,
256 GiB Hash, 512 threads, and no SMP in Fork yet).

The main new results come from re-analysing the logged games:

- **Speed-to-Elo rate.** Eight networks with both a fixed-node and an STC
  result give **R ≈ 106 ± 20 Elo per doubling of nps at STC, about
  1.5 Elo per 1% nps** (range 1.2-2.8). The 3.1 figure is S512+X's
  outlier. The rate barely falls at LTC (XGR: about 95).
- **Speed-adjusted fixed-node screens.** Fixed nodes plus R × log2(nps
  ratio) predicts the STC sign for 8 of 8 networks, against 2 of 7 for the
  raw fixed-node result.
- **SPRT power.** The current setup ([0, 3] nElo, 13-stage cap) passes a
  real +3 Elo feature only about 21% of the time. A neutral feature is
  confirmed removable only about 5% of the time on [−3, 0]. Batch 4 and the
  full removal round therefore cost about 40 and about 80 GitHub-hours for
  little decided output.
- **Return per stage.** Networks have returned 12-44 Elo per GitHub stage,
  search features about 0.8.

Every number below is labelled as **[read]** (from a file), **[derived]**
(my arithmetic on logged numbers) or **[est]** (a reasoned estimate),
UNVERIFIED where unsure.

---

## Part 1: speed

### 1.1 What Fork runs on and how fast [read unless marked]

- Default S512ppr2: 768 mirrored piece inputs plus 608 pawn-link inputs
  (rank limit 1). These feed 2 x 512 int16 accumulators, then SCReLU, then
  8 output buckets picked by game phase. The first layer is
  (768 + 608) x 512 x 2 B = **1.41 MB** [derived from net_shape.hpp]. That
  exceeds a 1 MB L2 (local Zen 4, TCEC Zen 4c) and is nearly 3x a Zen 3
  runner's 512 KB L2 (L2 sizes from memory, UNVERIFIED).
- Local nps: S512r2 bench 3.73 M (12-round quiet A/B, sprt-log 2026-11-05
  S512+X). S512+PP/S512ppr2 run at 0.895 of S512r2 (identical-tree,
  nets.md). C4 adds +4%. So the default is about **3.5 M bench nps** on the
  7600X3D [derived, UNVERIFIED as a direct measurement], about 1,300-1,400
  cycles per node (idea 46's judge: about 1,300 for S512r2).
- On the runners: B0 searched about 2.4 M nps in games (stage B note,
  sprt-log 2026-10-31). An average STC move is about 500k nodes, at about
  depth 15. The 800k-node fixed-node screens reach about depth 17.
- Bootstrap-era search ran at about 6.9 M nps (KB), so the network about
  halved nps, which matches the KB's general pattern.
- **Fork against other engines:** the KB records no per-thread nps for any
  named engine (nnue-design.md §7.4, "no published per-thread figures").
  No comparison is possible from Fork's sources. The only external
  strength anchor is the gauntlet (3445.8 ± 21.6 on the CCRL Blitz scale,
  S512r2 era).

### 1.2 Profile model: where a node's time goes

Profile [read]: perf-log 2026-11-06. S512r2 with IIR, before C4, 64 UHO
positions at movetime 250, Hash 16, 1 thread, native build. Nanoseconds use
278 ns/node (3.6 M nps) [derived]. The last column is my reading.

| area | share | ns/node | inside | comment |
|---|---|---|---|---|
| accumulator update (`advance_values`) | 17.2% | 48 | per perspective, per ply walked; AVX-512 on native, AVX2 on shards | ~384 µops per quiet move both sides on AVX2; ~half on AVX-512 [est] |
| output layer (`squared_sum`) | 14.5% | 40 | 64 AVX2 iterations of max/min/mullo/madd/add over 1,024 values | **AVX2 only, even on native** (C1's AVX-512/VNNI path parked); near throughput-bound [est] |
| refresh (`sum_perspective`) | 2.5% | 7 | scalar loop over pieces on a mirror-frame crossing | small, which is why E1 lost (−5.3%) |
| other network (`evaluate_with`, `column`) | 3.6% | 10 | bucket pick, scaling, pointer math | |
| move ordering | 14.7% | 41 | select_best 5.9, see_at_least 3.1, take_next 2.8, score_quiets 1.8 | C4 then removed about a third of select_best's cost [derived from +4% total] |
| TT | 12.7% | 35 | `TtEntry::bound` 8.3% = first read of the bucket (the stall) | idea 40 log: the stall varied **5-45 ns per node between repeated runs of one build** |
| move generation | 10.8% | 30 | PEXT index 2.4, fill_moves 2.4, attackers_to 1.7 | |
| search bodies | 5.7% | 16 | negamax 3.6, quiesce 1.2 | |
| make/unmake | 2.0% | 6 | | |
| other | 12.6% | 35 | spread thin | |

For S512ppr2 [est]: links add about 30 ns per node (the 10.5% slowdown).
The idea-40 speed log puts the extra cost in instructions: the
changed-pair search is about 200 instructions per node, branch misses are
about 20% of the extra cycles, and the rest is the extra rows added on pawn
moves. So today's network share is probably about 45-48%.

**Not measured (gaps):**

- the share of evaluations made at quiescence nodes. It decides whether any
  eval-avoidance idea is worth anything. `FORK_SEARCH_STATS` has
  `quiesce_nodes_*` counters, but no NNUE-era count is logged.
- the fraction of evaluations served from the TT (`hit.eval`).
- refreshes per 1,000 updates (design-speed §3.4 asked for this counter).
- the average plies walked back per lazy evaluation.

All four are one debug-build bench run away. They should be measured
before any further network-speed design work.

### 1.3 The speed sprints: what won, what lost, why [read; the "why" is partly derived]

| candidate | result | why (my reading) |
|---|---|---|
| C4: select_best keeps the best score in a register | **+4.0% median** (kept) | Removed a load-to-use dependency across loop iterations. A pure dependency-chain fix, independent of cache size, so it transfers to every machine. |
| C1: output layer on AVX-512/VNNI | not measured, **parked** | Parked because the shards build v3. **But a speed-only, bench-identical change needs an A/B, not an SPRT** (Testing setup, "bounds policy"). The 7600X3D is Zen 4, the same core family as TCEC's Zen 4c, so it is the best TCEC proxy available. The parking reason does not hold for the TCEC build (see 1.6). |
| C2: prefetch the delta's feature rows at make | −2.9% / −1.4% (no) | The rows are already L1/L2-resident locally. Extra prefetch µops cost more than the latency they hide. |
| C3: earlier child TT prefetch | −0.8% (no) | With a 16 MB TT inside a 96 MB L3, latency is about 12-15 ns, so there is little to hide. **Under TCEC memory (DRAM plus TLB misses on 256 GiB) the same idea could be positive**, and no local test in the current regime can show it. |
| E1: refresh cache for mirror-frame changes | **−5.3%** | Refreshes were only 2.5% of time. A 1 KB copy per frame change and a larger FeatureStack cost more. Correctly rejected; perf-log marks it UNVERIFIED (not profiled). |
| E2: AVX2 select_best scan | +1.0% (n.s.) | C4 already took most of the gain. |
| E4: both perspectives in one pass | −0.6% (n.s.) | AVX2 has 16 ymm registers; one perspective's 512 lanes already need two passes. |
| idea 40 speed steps for S512+PP | 0.666 → 0.787 → 0.818 → 0.895 | Wins came from **fewer instructions**: links folded into the int16 sums, the tight pair pass, and R = 1 (fewer pairs). Every cache or prefetch step lost: the structure-key cache, slot and row prefetch, 8-bit rows. The judge drew the same lesson for idea 46: "cost is instructions and row width". |
| XGR set-wise exposure | +15.5% | Again fewer instructions. Switching exposure off entirely was about 13% faster, so *finding* threats costs more than *summing* them (idea 46). |
| Phase 3 audit-1 | P-2 lazy pins +2.4%, P-3 SEE early exit +2.3% (both below the 3% rule; adopted for simplicity) | |

**Pattern** [derived]: on this machine, gains come from cutting
instructions or dependency chains, never from hiding memory latency. That
will **not** hold on TCEC hardware, where the TT and possibly the weight
rows are latency-bound (1.6).

### 1.4 The speed-to-Elo rate: derived from the eight fixed-node/STC pairs [derived]

Model (design-speed.md §2.8): STC Elo ≈ fixed-node Elo + R × log2(nps
ratio). Every network that had both a fixed-node screen at 800k nodes and
an STC result against the same opponent gives one estimate of R. The nps
ratios come from §5.4's local bench ratios; round-2 ratios are re-based on
S512r2 = 0.78 of B0.

| net | log2(nps ratio) | FN | STC | gap ± 95% | implied R (Elo/doubling) | Elo per 1% nps |
|---|---|---|---|---|---|---|
| S512 r1 vs B0 ctl | −0.358 | +74.5 | +43.7 | −30.9 ± 17.1 | 86 | 1.24 |
| H-512 r1 | −0.415 | +32.2 | −24.4 | −56.6 ± 15.1 | 136 | 1.96 |
| AF-S r1 | −0.837 | +41.7 | −48.5 | −90.2 ± 17.5 | 108 | 1.55 |
| XGR r1 | −1.059 | +52.1 | −38.2 | −90.2 ± 17.6 | 85 | 1.22 |
| AF-S r2 vs S512r2 | −0.478 | +10.4 | −55.9 | −66.3 ± 15.4 | 139 | 1.99 |
| XGR r2 | −0.642 | +30.7 | −34.4 | −65.1 ± 15.8 | 101 | 1.46 |
| S512+X | −0.290 | +25.7 | −30.0 | −55.7 ± 14.9 | 192 | 2.76 |
| S512+PP | −0.160 | +46.1 | +32.7 | −13.4 ± 14.7 | 84 | 1.20 |

- **Weighted least squares through the origin: R = 105.7 ± 9.9 Elo per
  doubling (statistical), 1.52 Elo per 1% nps.** χ² is 24.5 on 7 degrees
  of freedom, about 1.9x the expected scatter, so a realistic band is
  **R ≈ 85-125, about 1.2-1.8 Elo per 1%**.
- The planning figure of 3.1 per 1% (idea 46) is **S512+X alone, the
  largest outlier** (residual −25). Its exposure cost may vary by position
  (more in tactical, quiescence-heavy positions than on the bench), so its
  in-game ratio may be worse than 0.818 (UNVERIFIED).
- The "rule of thumb 0.9" (R ≈ 63) sits below every one of the eight
  points.
- **Caveats:**
  - The gap mixes speed with a depth effect: the FN screen searches deeper
    than STC (depth 17 against 15). If a better eval gains more at depth,
    R is overestimated.
  - The nps ratios were measured natively with AVX-512 updates, not on
    the shards' AVX2 builds (1.6).
  - The FN and STC runs shared stage 0's openings, which correlates their
    noise. The gap error bars above assume independence, so they are
    conservative.
- **LTC.** XGR r2 scored −30.56 at LTC against +30.70 at fixed nodes, so
  **R_LTC ≈ 95**, against R_STC ≈ 101. The exchange rate barely fell from
  8+0.08 to 40+0.4. IIR (a node-efficiency feature) grew from +21.5 at STC
  to +26.3 at LTC.

**Consequences:**

1. The speed gate at 0.90 costs about 16 Elo at STC (R × log2 0.9 =
   −16.1). A new input type must buy at least that much at fixed nodes,
   **about 13-19 FN Elo for 0.90x and about 6-9 for 0.95x** (R 85-125)
   [derived].
2. C4's +4.0% was worth about **+6 Elo at STC** [derived], about as much
   as a typical tier-2 feature, at zero GitHub cost. A further 5% of nps
   is worth about +7.5 Elo. Speed work is not low-value at Fork's level.
3. **Speed-adjusted fixed-node screens predict the STC sign for 8 of 8
   nets** (in-sample; leaving each net out moves R to about 95-115, and
   only S512+X's sign then becomes marginal). The raw rules ("FN > 0",
   "FN > +30") predicted 2 of 7. Rule to propose: **go to STC only if
   FN + R̂ × log2(nps ratio) > 0**, with R̂ = 100 until measured.
4. **The "LTC / TCEC-conditions candidate" bucket** (beat S512r2 at FN,
   failed STC: AF-S, S512+X) has no support. Its premise is that R falls
   a lot with time; XGR's LTC run says it does not (95 against 101). Both
   should be dropped rather than kept as owed tests.

### 1.5 Designing the speed-to-Elo measurement (§5.6 item 4) [derived]

The plan is S512r2 against itself at 0.85x time, about 4,000 games. The
expected effect is R × log2(0.85) ≈ −25 Elo at R = 106, measured to about
±6.5 Elo (95%, 4,000 games, pair sd 0.21). R would come out to about
**±28 (±26%)**.

| design | expected Elo at R = 106 | games | ± on R (95%) |
|---|---|---|---|
| 0.85x time (planned) | −24.9 | 4,000 | ±28 |
| **0.5x time (1 doubling)** | −106 | 1,600 | ±13 (1 stage) |
| 0.5x time | −106 | 3,200 | ±9 |
| 0.7x as a linearity check | −54.5 | 1,600 | ±20 |

Two traps:

- **Move Overhead.** The default is 100 ms against an 80 ms increment.
  Time odds by tc=4+0.04 do not halve the usable time: the overhead is
  fixed, so the odds come out larger than 2:1 and R biased high. Lower the
  overhead for both engines in that test, or better:
- **Use a throttled build instead of time odds.** The same binary burns a
  calibrated number of cycles per node (for example, the output layer
  evaluated k extra times behind a compiler barrier, as a test-only build
  flag). The nps ratio is set by ab_search, and time management behaves
  identically. This is exactly the speed gate's question: a slower net,
  the same tree. It needs a build flag; nothing ships.

Run it at STC (2 stages, 0.5x) and LTC (1-2 stages at 1,664 games, 0.5x).
That gives R_STC and R_LTC directly and settles items 2-4 of 1.4.
**Prediction:** R_STC in 85-125; refuted if outside 60-150. R_LTC/R_STC
above 0.8; refuted if below 0.6.

### 1.6 TCEC hardware against what the STC shards test [read: KB competition.md; architecture details from memory are UNVERIFIED]

| dimension | SPRT shards (STC) | local A/B (speed claims) | TCEC Swiss | implication |
|---|---|---|---|---|
| threads | 1 | 1 | **512** (2x EPYC 9754, 256 cores with SMT) | Fork has **no SMP**: `Threads` only sizes the Hash clear (session.cpp; DESIGN §5.1 table). At TCEC Fork today uses 1 of 512 threads. Lazy SMP is Phase 6. **SMP scaling has never been measured because it does not exist.** By far the largest TCEC strength item [est: hundreds of Elo, UNVERIFIED]. |
| ISA / build | g++ 11.4, x86-64-v3 (AVX2) | clang 21, **native (AVX-512 + VNNI)** | update.sh default: **clang++-19 first, x86-64-v3, no PGO** | The SPRT binary, the speed-gate binary and the TCEC binary are three different builds. The output layer has no AVX-512 path anywhere. TCEC should get x86-64-v4 with C1 (both servers are AVX-512 per the KB; Zen 4c VNNI from memory, UNVERIFIED) and PGO if it pays (gain unmeasured). |
| Hash | 16 MB (L3-resident on every runner) | 16 MB inside a 96 MB L3 | **256 GiB** | Every TT probe at TCEC is a DRAM access plus, with 2 MB pages, almost always a TLB miss (131,072 huge pages against a few thousand L2 TLB entries, UNVERIFIED). The local profile's 35 ns TT is a best case; 100+ ns per probe is plausible [est]. C3 and idea 19 (explicit or 1 GB pages) are untestable in the current regime. |
| caches | Zen 3 runners: 512 KB L2, 32 MB L3 per 8 cores; also Zen 4/5 and Xeon | 1 MB L2, 96 MB L3 for 6 cores | Zen 4c: 1 MB L2, 16 MB L3 per 8 cores (about 2 MB a core), two SMT threads per L2 (UNVERIFIED) | S512ppr2's 1.41 MB first layer spills L2 everywhere. Locally it sits in the huge L3; at TCEC two threads share 1 MB L2 and 2 MB of L3 each. **Any new input family (S512cl's 54 MB table!) is measured locally in the most cache-friendly CPU on the market.** |
| time per move | about 0.2 s, about 500k nodes | n/a | about 40-60 s single-thread, x512 threads | LTC (40+0.4) covers about 2.3 doublings over STC; TCEC is about 7-8 single-thread doublings away before threads [derived]. |
| tablebases | 3-4-5 | | 7-man on NVMe/HDD | Probe latency on disk; `TableProbeMinDepth` deferred to Phase 8. |
| adjudication | resign 1000 cp x 5, draw \|10\| x 10 from move 40 (run_shard.sh) | | no win adjudication; draw only at ≤ 6 pieces, \|eval\| ≤ 0.25 for 8 plies | Endgame conversion is tested less hard in SPRTs than TCEC demands (idea 45). |
| SMT | runners: 4 vCPU, concurrency 3; whether the vCPUs are SMT siblings is UNVERIFIED | 1 thread on a dedicated core | yes (512 on 256) | If runner vCPUs are siblings, the shards' nps sit about 30-40% below a dedicated core and vary between shards. |

**What STC never tests:** multi-thread TT contention and replacement
(ideas 24 and 30 were deferred for exactly this reason), memory-latency-bound
TT probing, AVX-512 inference, the TCEC compiler (clang-19 against the
shards' g++), PGO, and 7-man probing. A Phase 4 change that is neutral at
STC can be positive or negative at TCEC for these reasons alone.

### 1.7 Speed experiments worth running (cheapest first) [derived and est]

Each item gives mechanism, model, prediction, cost and kill rule.
R = 106 Elo/doubling turns nps into Elo: 1% nps ≈ 1.5 Elo at STC.

1. **Measure the speed gate in the shard and TCEC builds** (local, about
   1 h quiet). S512ppr2 against S512r2 built by update.sh with g++ v3 and
   with clang-19 v3/v4, against the native ratio of 0.895. The model:
   AVX2 doubles the µops of every extra link row, so the link cost should
   be larger on AVX2. Prediction: v3 ratio 0.86-0.89; refuted if v3 ≥
   native. If confirmed, the gate must be measured in the build that plays
   SPRTs and TCEC.
2. **Large-Hash regime profile** (local, about 1 h). The same 64 UHO
   positions with Hash 16 against 4,096-8,192 MB, nps and perf (dTLB
   misses from `perf stat`). Then C3 and an explicit huge-page or 1 GB
   variant (idea 19) in *that* regime. Prediction: the TT share grows from
   13% to 20-30% and C3 turns positive. Kill: if Hash 8 GB costs under 3%
   nps against 16 MB, drop TT-latency work until Phase 6.
3. **C1 un-parked for the TCEC build** (local A/B on Zen 4, v4 against
   v4+C1, bench identical). It cuts the output layer's instructions (about
   15% of time). Zen 4 double-pumps 512-bit ops, so expect 10-25% of that
   layer [est], **+1.5-4% total, worth +2-6 Elo at STC-like rates**. It
   needs an owner decision that update.sh builds x86-64-v4 for TCEC (a CPU
   check, falling back to v3). Kill: < 3% (the harness rule).
4. **PGO in update.sh** (local A/B: clang-19 v3/v4 with and without PGO,
   bench identical). The gain is unmeasured in any log (UNVERIFIED);
   datagen already uses PGO builds. It matters only for TCEC; shards use
   the same build on both sides.
5. **Counters before design** (one debug bench): quiescence-eval share,
   TT-eval hit rate, refresh rate, walk-back depth. This decides whether
   "evaluate fewer nodes" ideas (qsearch stand-pat shortcuts, TT eval
   reuse) have a ceiling worth chasing.
6. **Fused update and output** for the leaf being evaluated: compute the
   child's sums and fold them into the SCReLU dot product in one pass.
   Saves a 2 KB reload and loop overhead. Expect 2-5% of network time,
   +1-2% total [est]. Low priority; kill below 3%.

---

## Part 2: testing methodology

### 2.1 Actual SPRT settings [read: sprt.yml, run_shard.sh, sprt_merge.py, Testing setup]

- fastchess 1.8.2-alpha with `-repeat` (game pairs, colours reversed),
  1 thread per engine, `-concurrency nproc-1` (3 on 4-vCPU runners).
- Openings: UHO_Lichess_4852_v1, a fixed-seed permutation (20261027).
  Stage S, shard I starts at 1 + (S·N + I)·G/2, so no opening is reused;
  `sprt_merge` refuses overlapping ranges.
- Adjudication: resign at 1000 cp for 5 moves (two-sided); draw from move
  40 at |10 cp| for 10 moves. Syzygy 3-4-5 for both engines.
- Statistics: **pentanomial, normalized Elo**, LLR by the normal
  approximation of the GSPRT, α = β = 0.05 (bounds ±2.944). LLR is checked
  only at stage ends, which is slightly conservative.
- Stages: STC 8+0.08, Hash 16, **1,600 games**, about 18.5 min per stage
  (ledger dispatch spacing). LTC 40+0.4, Hash 64, 1,664 games (time per
  stage UNVERIFIED, about 75 min est).
- Caps:
  - STC: 13 stages (sprt_run.sh default 0-12, 20,800 games). take-vs-follow
    ran 14 stages under "an SPRT runs to its verdict", in conflict with the
    cap rule.
  - LTC: 9,984 games.
  - Non-regression early acceptance: ≥ 10k games and the nElo lower bound
    above −3.
- Bounds: [0, 5] for big expected gains and networks, [0, 3] for features,
  [−3, 0] for removals and safety. Since 2026-11-06 constants come from a
  ladder (2-3 values, each capped at 2 stages).
- Builds: update.sh with g++ x86-64-v3 on the shards (sprt.yml). Hosted
  runners: EPYC 7763 most often, also EPYC 9V74/9V45 and Xeon (from the
  gauntlet's records).

### 2.2 Every Phase 4 SPRT and screen, with what predicted it [read; nElo and sd derived from the logged pentanomials]

Notation: games to decision (or cap). "Pre" = the measurement made
before the SPRT, and whether it agreed.

**Networks (all STC [0, 5] unless noted):**

| test | games | result | pre-SPRT predictor | agreed? |
|---|---|---|---|---|
| B0 vs bootstrap | 1,600 | H1 +486.9 | parity, netcheck | n/a |
| B0r1 vs B0 | 1,600 | H1 +200.2 | val loss | yes |
| g1b0 (B0r2) vs B0r1 | 1,600 | H1 +235.5 | — | |
| S512 vs B0 ctl | 1,600 | H1 +43.7 | FN (later) +74.5 | sign yes |
| H-512 vs ctl | 3,200 | H0 −24.4 | FN +32.2 | **no** (speed 0.75, overfitting) |
| AF-S vs ctl | 1,600 | H0 −48.5 | FN +41.7 | **no** (speed 0.56) |
| XGR vs ctl | 1,600 | H0 −38.2 | FN +52.1 | **no** (speed 0.48) |
| seed noise S512, i13a, i13b (no SPRT) | 1,600 each | −0.9, +3.3, **−14.8** | "seeds within 10 Elo" | 1 of 3 broke it |
| i13b vs i13a (data) | 1,600 | H1 +65.5 | own-val losses (different sets, not comparable) | n/a |
| S512r2 vs S512 | 1,600 | H1 +151.4 | val loss, 5x data | yes |
| FN round 2: H-512 / AF-S / XGR | 1,600 each | −12.2 / +10.4 / +30.7 | | |
| AF-S r2 | 1,600 | H0 −55.9 | FN +10.4 | **no** (speed 0.72) |
| XGR r2 | 1,600 | H0 −34.4 | FN +30.7 | **no** (speed 0.64) |
| XGR r2 LTC [0, 5] | 1,664 | H0 −30.6 | "R falls at LTC" | **no** (R barely falls) |
| S512+X (S512r3 skipped) | FN 1,600 + 1,600 | H0 −30.0 | **val loss −2.2%**, FN +25.7 | **no** (speed 0.818, not priced) |
| S512+PP | FN 1,600 + 1,600 | H1 +32.7 | val loss "barely moved", FN +46.1 | FN yes; val loss no |
| S512ppr2 vs S512+PP | 3,200 | H1 +20.1 | recipe loss (10x seed spread), endgame 351 → 8 | yes |

**Search (STC [0, 3] unless noted):**

| test | games | result | pre-SPRT predictor | agreed? |
|---|---|---|---|---|
| lmr-check-relief (bootstrap) | 9,600 | H1 +11.3 | — | |
| lmr-in-check (bootstrap) | 35,200 | H1 +4.2 | — | (past today's cap) |
| qs-delta (B0r1) | 27,200 | stopped, −0.4 | margin read off a bench curve after seeing data | no gain |
| SE [0, 5] | 4,800 | H1 +14.1 | constants measured | yes |
| multi-cut | 9,600 | H1 +9.2 | | |
| negative extension | 8,000 | H0 −8.7 | | |
| reply [0, 5] | 6,400 | H1 +11.5 | measured weight | yes |
| follow | 12,800 | H1 +7.2 | measured weight | yes |
| take | 22,400 | H1 +4.5 | measured weight | yes |
| **IIR** | 4,800 | **H1 +21.5** | proxy: **no depth beat "off"** | **no** (proxy blind to node savings) |
| IIR LTC [−3, 0] | 3,328 | H1 +26.3 | STC +21.5 | yes (grew at LTC) |
| drift table LTC | 9,984 | **cap**, −0.35 | measured 256/4 (gain implied) | **no** |
| LMR history | 6,400 | H0 −10.8 | proxy: no divisor beat off | yes |
| rising RFP | 19,200 | H0 −3.8 | proxy below off | yes |
| ProbCut | 12,800 | H0 −5.3 | proxy −0.0049 [−0.0101, +0.0006] | yes |
| threat ordering | 12,800 | H0 −6.1 | proxy −0.0162 | yes |
| reval: no check relief [−3, 0] | 20,800 | **cap**, −3.16 | (removal) | not decided |

Phase 3 (local and GitHub, bootstrap eval) [read]:

- Milestone A/B feature checks: 300-650 games each, all H1.
- SEE in quiescence and aspiration: stopped inconclusive.
- B-1: accepted at the cap. B-2, B-3: cap, reverted. B-4: H0 at 19,200.
- rv-failhigh: rejected at 2,000. TT-refine: stopped at 1,000 (shipped by
  exception). keep-exact: cap. mc-tables: cap +17.5, accepted. RfpMargin
  40: no test, then reverted by the gauntlet.
- **Undecided or stopped outcomes in Phase 3: 12 of about 25 tests.**

### 2.3 Mispredictions and their causes [derived]

| cause | cases | evidence |
|---|---|---|
| **speed not priced** | H-512, AF-S, XGR (r1 and r2), S512+X: 6 of 6 FN→STC sign flips | Each disappears with R ≈ 100 (1.4). S512+X's val-loss gain (−2.2%) also ignored speed. |
| **TC dependence assumed but absent** | the XGR LTC rescue; the "LTC candidate" bucket | R_LTC ≈ 95 against R_STC ≈ 101 |
| **proxy structurally biased** | IIR (proxy "off is best", SPRT +21.5) | The label-and-sweep fitness scores move agreement at a fixed node budget against labels made by "off". It cannot see a feature's main benefit, fewer nodes to the same depth (IIR reached depth 14 in 21% fewer nodes, DESIGN constants row), and it favours "off" by construction. 5 of 5 SPRTed proxy results read "below off". Its sign agreed on 4 of 5, but it never once predicted a gain, so its discriminating power is unproven. **Correctly retired** by the streamlined standard. |
| **noise / seed** | i13 arm B seeds −14.8 apart; the qs-delta margin chosen post hoc | A single-seed network SPRT carries about ±10-15 Elo of seed luck on top of the recipe effect. |
| **loss metric across architectures** | S512+X (loss −2.2%, STC −30), S512+PP (loss ≈ 0, STC +33), S512r3 (loss worse, never tested) | Validation loss ranks recipes within one architecture; it does not rank architectures, which differ in speed and in how errors matter. |
| **interaction / base drift** | ProbCut, rising RFP and threat ordering tested on S512r2 while the default moved to S512+PP, then S512ppr2 | No retest (owner's rule). The magnitude is unknown. |
| **book** | none identified | The book is shuffled with no reuse; the UHO bias is symmetric by colour reversal. |
| **eval scale** | none attributable in the log | S is matched on every network SPRT. |

### 2.4 How often FN screens predicted the STC sign [derived]

- Raw FN sign: **2 of 7** (S512 r1, S512+PP). FN always overstated STC;
  the smallest overstatement was 13 Elo (PP).
- Speed-adjusted FN (1.4): **8 of 8** in sample (7-8 of 8 leaving each
  out). Residual RMSE about 14 Elo, roughly 2x the pure noise.
- The judge's point stands: a 1,600-game FN match (±10) cannot screen
  designs worth +3 to +8. But for big changes (new input types, ±20-50)
  the speed-adjusted screen is cheap and reliable.

### 2.5 Draw rate, pentanomial variance, games per Elo resolution [derived from the logged Ptnml]

Per-pair standard deviation of the pair score (0..1), the quantity that
sets the error bars:

| era / TC | pair sd | Elo/nElo | extreme pairs (0 or 2) | pair score 1 |
|---|---|---|---|---|
| bootstrap search, STC | 0.276-0.282 | 0.78-0.80 | 20-21% | 37-39% |
| B0r1/S-512 era, STC | 0.23-0.25 | 0.65-0.71 | 9-14% | 40-44% |
| S512r2 era, STC (near-zero tests) | **0.208-0.214** | **0.59-0.61** | 5.5-6% | 45-47% |
| S512r2 era, LTC | **0.193-0.198** | **0.55-0.56** | 2.8-4% | 47-49% |
| FN 800k nodes, round 2 | 0.212-0.219 | 0.61-0.62 | 6.6-6.9% | 42-46% |

- **Game draw rate:** it cannot be recovered from pentanomial counts. It
  lies between 24% and 70% for the S512r2-era STC tests (a pair scoring 1
  can be two draws or a win and a loss). The gauntlet's Ordo gives 25.4%
  between equal opponents, on random 8-ply openings at 10+0.1, not UHO.
  The UHO-specific draw rate is UNVERIFIED; it is computable from the
  shards' PGNs.
- **Games for a 95% interval of ±X logistic Elo**, games = 2 ×
  (1.96 × 245.7 × r / X)²:
  - **STC (r = 0.595): ±2 → 41k games, ±3 → 18k, ±5 → 6.6k.**
  - **LTC (r = 0.553): ±3 → 15.8k.** LTC needs about 13% fewer games per
    unit of Elo resolution, but each game costs about 5x, so LTC
    resolution costs about **4.3x STC's** per Elo.
- The pair variance fell about 40% from the bootstrap era to S512r2 (sd
  0.28 → 0.21). In logistic Elo the tests are now about 1.8x cheaper per
  unit of resolution. Because the bounds are nElo, a fixed logistic gain
  is now a *larger* nElo signal (+3 Elo ≈ +5 nElo, against +3.8 before).

### 2.6 Power of the current SPRT and what the caps imply [derived; simulation with the normal approximation, stage-wise checks, 20,000 trials per row]

[0, 3] nElo, 1,600-game stages, cap 13 stages:

| true nElo (≈ Elo at STC) | P(H1) | P(H0) | P(cap) | mean stages |
|---|---|---|---|---|
| −6 (−3.6) | 0.00 | 0.79 | 0.21 | 10.1 |
| −3 (−1.8) | 0.00 | 0.34 | 0.66 | 12.1 |
| 0 | 0.00 | 0.05 | 0.95 | 12.9 |
| +3 (+1.8) | 0.05 | 0.00 | 0.95 | 12.9 |
| +5 (+3.0) | **0.21** | 0.00 | 0.79 | 12.5 |
| +7 (+4.2) | 0.50 | 0.00 | 0.50 | 11.6 |
| +10 (+6.0) | 0.89 | 0.00 | 0.11 | 9.3 |

- **Removals on [−3, 0], same cap:** a feature worth exactly 0 nElo is
  confirmed removable (H1) **5%** of the time and caps 95%; one worth −1.5
  caps 97%.
- The early-acceptance rule cannot fire for it either. At 20,800 games
  the nElo half-width is 4.7, so the estimate would need to exceed +1.7.
- **reval-no-check-relief** played out exactly this way: 13 stages, cap.
- **The full re-validation (item 11)** removal-tests about 20+ switches at
  about 12.9 stages each, **about 260 stages, about 80 GitHub-hours**. It
  will almost surely remove nothing that is merely useless; it only
  catches features that are clearly harmful (≤ about −5 nElo).
- **Batch 4** has nine "possible few Elo" items. Ladders cost 4-6 stages
  each, then the SPRT about 10.5 stages under a prior of N(0, 8) nElo,
  about **140 stages, about 43 h**.
- **The ladder** (2-3 values, 3,200 games each, ±12 nElo): for three
  values spaced 4 nElo apart, P(it picks the truly best) = **0.62**; at a
  2 nElo spacing 0.48. That is close to the 0.33 of a random pick. For
  small-effect constants the ladder mostly certifies originality; it does
  not optimise. SPSA refines later anyway.

**Policy comparison**: expected nElo gained per test and per stage. Each
policy faced the same prior of true effects; accepted negatives are
counted as losses.

| policy | prior N(0, 8) gain/stage | prior N(2, 8) gain/stage | prior N(4, 15) gain/stage | P(accepted change is < 0), prior N(0, 8) |
|---|---|---|---|---|
| current: SPRT [0, 3], cap 13 | 0.20 | 0.30 | 0.92 | 0.00 |
| + futility stop after stage 2 if estimate < 0 | 0.32 | 0.44 | 1.31 | 0.00 |
| SPRT [0, 5], cap 8 | 0.31 | 0.45 | 1.44 | 0.00 |
| fixed 4 stages, accept if nElo estimate > +2 | **0.68** | **0.95** | **1.98** | 0.10 |
| SPRT [0, 5] cap 6 + stage-2 futility + accept at cap if estimate > +3 | **0.69** | **0.91** | **2.25** | 0.04 |

[0, 3] with a 13-stage cap is the least efficient design here by 2-3x in
Elo per GitHub stage. It buys a near-zero false-accept rate, but most of
its spend goes on "cap, not passed" outcomes, which then *also* ship
nothing. A futility stop alone (stop at 3,200 games if the estimate is
negative) keeps α at about 0 and saves about 40% of stages. This is the
one change that needs no relaxation of "untested changes never ship".
Fork's own data fit it:

- rising RFP was at −8.5 nElo after stage 1 and −6.4 after stage 2, then
  ran 12 stages;
- LMR history −21 / −15.5;
- the negative extension −12 / −12.

The futility stop would have saved about 25 of the 50 stages spent on
rejected net-era search tests [derived from the logged stage-wise
estimates; ProbCut's and threat ordering's stage-wise values were not
logged].

### 2.7 GitHub budget per decision and per Elo [derived; stage counts from sprt-log, times from ledger spacing; LTC stage time UNVERIFIED]

Phase 4 to date: **161 STC-condition stages** (fixed-node stages counted
as one) **plus 9 LTC stages**: 257,600 + 14,976 games. That is about 50 h
of STC slot plus about 11 h of LTC [est], over about 9 days.

| group | stages | decisions | Elo adopted (STC, each on its own base) | Elo per stage |
|---|---|---|---|---|
| bootstrap-era (B0 steps, check relief, lmr-in-check, qs-delta) | 48 | 6 | B0 chain +922 (3 stages); search +15.5 (45 stages) | 307 (nets) / 0.34 (search) |
| net-era networks (bake-off, FN screens, seeds, i13, r2, S512+X, PP, ppr2) | 25 + 1 LTC | 13 | +313 (S512 43.7, i13 65.5, S512r2 151.4, PP 32.7, ppr2 20.1) | **12.5** |
| net-era search (SE … reval) | 88 + 8 LTC | 14 | +68.0 (SE, MC, reply, follow, take, IIR) | **0.77** (about 33 GitHub-min per Elo with LTC) |
| of which rejected or undecided | 50 STC + 6 LTC | 8 | 0 | — |

- **Network and data work returned about 15-40x more Elo per GitHub
  stage than search features.** For networks the binding resources are
  Kaggle and datagen CPU, not GitHub.
- Search testing is where GitHub time goes, and 57% of its stages bought
  rejections or caps.
- Elo estimates from SPRTs that stop early are biased upward (the
  winner's curse): S512+PP's +32.7 after 1 stage, SE's +14.1 after 3. The
  sum of adopted estimates overstates the real gain; the gauntlet is the
  check (3315.6 → 3445.8 across a change of anchor set, so not a clean
  measurement).

---

## Part 3: ranked bottlenecks (speed and methodology)

Confidence: H = high, M = medium, L = low.

| # | bottleneck | evidence | what it gates | confidence | cheapest fix |
|---|---|---|---|---|---|
| 1 | **SPRT design has little power for the effects that remain** ([0, 3] nElo, 13-stage cap: P(H1) about 0.21 for +3 Elo; removal round confirms a neutral feature 5%) | 2.6 simulation; reval-check-relief and drift capped; 4 of 14 net-era search tests ran ≥ 12 stages | batch 4 (9 items, about 43 h), item 8, item 11 (about 80 h, removes almost nothing), the reval queue | H (math; matches the log) | futility stop at stage 2; for item 11 test only the bootstrap-era or small features (check relief, lmr-in-check, SEE-quiesce, aspiration, TT-refine, mate distance) with a fixed-length estimate, not an SPRT to a verdict; an owner decision on accept-at-cap rules (2.6 table) |
| 2 | **The speed-to-Elo rate is not measured, and the planned design is weak** | derived R ≈ 106 ± 20 (1.5 Elo per 1%), not 3.1; the 0.85x/4,000-game plan gives ±26% | the 0.90 speed gate, S512cl, idea 46's designs, the LTC-candidate bucket, speed-sprint ROI | M-H | 0.5x throttled build, 2 STC stages + 1-2 LTC stages (1.5) |
| 3 | **The "LTC / TCEC candidate" premise is contradicted** | XGR R_LTC 95 against R_STC 101; FN-pass/STC-fail nets 0 of 1 at LTC | AF-S and S512+X owed tests; how idea 46's speed costs are judged | M (one LTC point) | settled by #2's LTC half; until then drop both candidates |
| 4 | **Speed is measured in an unrepresentative regime** | native AVX-512 clang + 96 MB L3 + 16 MB Hash; shards use g++ AVX2; TCEC clang-19 v3, no PGO, 256 GiB, 2 MB L3 per core; the TT stall varied 5-45 ns per node run to run | the speed gate (0.895 may be about 0.87 on AVX2, UNVERIFIED), C1, C3, idea 19, S512cl's 54 MB table | M | 1.7 items 1-2 (about 2 h local) |
| 5 | **The TCEC binary is untested and under-built** | update.sh: v3 default, no PGO, clang-19 first; SPRTs use g++ 11.4; the output layer has no AVX-512 path | about +2-6 Elo (C1) plus PGO's unknown gain, free at TCEC | M | owner decision on v4 for TCEC; A/B C1 and PGO locally on Zen 4 |
| 6 | **No SMP; nothing in Phase 4 sees threads** | session.cpp: one search thread; ideas 24 and 30 deferred to Phase 6 | the TCEC result overall; TT policy decisions made at 1 thread | H (fact), magnitude UNVERIFIED | outside Phase 4; avoid adopting per-thread memory-heavy designs without a TCEC-memory estimate |
| 7 | **Proxy measurements and the ladder carry little decision information** | the proxy never predicted a gain and missed IIR (+21.5); the ladder picks the best of 3 only 48-62% of the time | constants in batch 4 and later | M | keep the ladder as the originality measurement only, at 1 stage per value or folded into the SPRT; let SPSA choose values |
| 8 | **Validation loss is used across architectures** | S512+X (−2.2% loss, −30 STC), PP (≈ 0, +33) | idea 46's distillation rule ("≥ 0.3% lower loss"), future architecture triage | H | rank architectures by speed-adjusted FN; use loss only within an architecture |
| 9 | **GitHub spend is skewed toward the lowest-yield tests** | nets 12.5 Elo/stage against search 0.77 | the order of §5.6 | H (descriptive) | always give network and data tests the slot first (already mostly done); cap search spend per Elo expected |
| 10 | **Seed variance in network candidates** | i13 arm B seeds −14.8 ± 12.4 at STC | promotion margins of +10-20 | M | pick the candidate seed by loss (done); treat promotion SPRTs under +15 as possibly part seed luck |
| 11 | **Profile counters missing** | quiescence-eval share, TT-eval hit rate, refresh rate, walk-back: none logged for NNUE | any eval-avoidance or accumulator idea | H | one FORK_SEARCH_STATS bench |
| 12 | **Winner's curse in adopted Elo** | 1-3-stage H1s report +14 to +33 | expectations for re-validation, SPSA headroom | L-M | quote stage-wise medians; the final gauntlet |

---

## What I could not verify

- **TCEC hardware internals**: Zen 4c per-core L2 (1 MB) and per-CCX L3
  (16 MB per 8 cores), AVX-512 VNNI on the EPYC 9754, and its double-pumped
  512-bit execution are from memory or the KB's UNVERIFIED notes.
- **GitHub runners**: whether the 4 vCPUs are SMT siblings, and their L2
  sizes, are not checked.
- **LTC stage wall time** (about 75 min) is estimated; I did not query
  GitHub run timings, per the brief.
- **The R fit** uses local native-build nps ratios from §5.4 (bench, not
  in-game). Part of the FN-STC gap may be a depth effect rather than speed.
- **The UHO game draw rate** is only bounded (24-70%); exact figures need
  the shards' PGNs.
- **Current default nps** (about 3.5 M bench) is derived, not directly
  read; nets.md's 2,342,208 was on a loaded machine.
- **PGO's gain** for Fork: no log records it.
- **Batch-4 cost and yield** depend on the assumed prior of effects,
  N(0, 8) nElo, which is my assumption informed by the net-era tier-2
  results, not a measurement.
- **ProbCut's and threat ordering's stage-wise estimates** were not
  logged, so the futility-stop savings (about 25 stages) are a lower-bound
  reconstruction.
