# Phase C: the ranked synthesis of Fork's Phase 4 think tank

Written 2026-11-07 by the Phase C judge, after reading the shared brief, the
Phase A evidence file (synthesis plus appendices A1-A3), the Phase B file
(three clean-room surveys, nine specialists, two skeptics) and, where a
ruling needed it, the primary files: HANDOFF.md, DESIGN.md §5.6, §6 and
Testing setup, `src/search/searcher.cpp` (the iterative-deepening loop),
KB competition.md. Nothing here was run against the engine. Every Elo figure
is a model prediction or a shrunk prior, head-to-head self-play, unless it
cites a logged run. No other engine's constants appear. The file is meant to
be public.

**One-paragraph summary.** The rest of Phase 4 should spend its scarce
resource, GitHub stages, where Fork's own evidence says the Elo is, and stop
spending it where the evidence says nothing can be decided. Three items carry
most of the expected gain: the network loop (the next retrain, which the
owner calls item 8, and the retrains after it), node-share time management
moved forward from Phase 5, and an SPSA retune split into an early margin
pass and a final pass by scaling class. One methodological change, a
budget-matched SPRT design for search features, roughly triples the Elo per
stage of every search item that follows. A week of cheap measurements
(mostly local CPU-hours and a few GitHub stages) decides more than ten
downstream items, and should come first. Several planned items are
negative-expected-value or cannot decide anything at Fork's budget and should
be dropped or redesigned: distillation from S512+X, S512cl's speed work, the
removal round as planned, idea 23's long run on its current proxy, the full
fractional-depth refactor, and the 0.85x time-odds speed measurement. The
honest total for the rest of Phase 4 is **about +22 to +52 Elo at LTC head to
head (central about +37)**, which is roughly +13 to +50 on a third-party
rating list, plus +3 to +10 at TCEC alone from building the TCEC binary
properly. SMP (Phase 6) outweighs all of it at TCEC and is out of scope.

Conventions. Agent IDs follow the Phase B file: M mathematics, T training,
S search theory, O tuning, ST statistics, H systems, C chess knowledge,
I search-eval interaction, W wildcard; the surveys are **SF** (Stockfish
lineage, B1), **OS** (open-source NNUE engines, B2), **TC** (TCEC and long
TC, B3); the skeptics are **B13** (network) and **B14** (search and the
rest). A1-A3 are the Phase A analysts, PA the Phase A synthesis.
HANDOFF.md is the project's untracked session notes (not public); its
facts are also recorded in DESIGN.md §5.6 and §6, docs/nets.md and
data/manifests/. **[V]** means I checked it in a primary file myself; otherwise the claim is
credited to the agent who verified it. Times are EST.

---

## 1. Executive summary

### 1.1 The decisions that matter most

1. **Keep the network loop fed, and run item 8 on Sunday evening.** Retrain
   on g3s3 (g3s2 + g3f + g3g) the moment g3g seals (target 366,424,464
   records, about 2:20 PM 2026-11-08), with the owner's standard recipe as
   the control arm plus three cheap arms (a cooldown branch, an anneal-only
   arm, and a recency arm if a deep-label yardstick exists). Expected **+4 to
   +12 (central +7)**. After it, retrain whenever a part adds about 150 M
   kept positions from a promoted labeller: **+2 to +10 more** over the rest
   of the phase. Networks returned 12.5 Elo per GitHub stage against 0.8 for
   search features (A3 §2.7); this lane is Kaggle- and datagen-bound, not
   GitHub-bound, so it never waits for the search queue.
2. **Move node-share time management (plus best-move stability) into Phase 4
   (owner plan change).** Zero nps, about 2 engineering days and 6-8 GitHub
   hours, **+5 to +12 at LTC** (B14's shrunk range, raised a little by a third
   engine's record, OS-Stormphrax), more plausibly at TCEC's 30'+3". The "resolution-aware soft stop" half of the proposals is refuted
   by the code: a timed Fork search only reaches the soft check after a
   completed iteration, with every aspiration re-search resolved
   (searcher.cpp lines 761-776 and 816 [V]). Labels are untouched (datagen
   sets only a node limit; B14 [V]).
3. **Replace the feature SPRT design.** Use design R for search features:
   [0, 6] nElo, α 0.05, β 0.20, cap 8 stages, futility stop after stage 2,
   plus head-to-head selection of constants (ST1 + ST6, reproduced by B14).
   It gives 2.6-3x the Elo per stage of today's [0, 3] capped at 13, which
   passes a real +3 Elo feature only about 21% of the time (PA §1e). The
   price is about 2% adoption of truly null features. Networks keep [0, 5].
4. **Split the SPSA retune.** Build the GitHub SPSA driver now (2-3 days;
   Fork cannot run SPSA on the shards today, B14 [V]), tune the eight
   eval-dependent margins early at STC (**+3 to +8 LTC**), and do the final
   retune by scaling class at the end (**+1 to +6**): shallow margins at STC,
   depth-scaling constants at LTC, time management never at a
   base/increment ratio of 100, the eval scale never.
5. **Measure before building.** About a week of cheap measurements decides
   most later items: a runner speed A/B (about 15-30 minutes of one runner),
   the in-game history-magnitude run (1-2 CPU-hours), the search counters
   (minutes), a combined deep relabel (about 2 hours on 2 threads), the
   node-share fit (1-4 CPU-hours), the anneal attribution (0.5 GPU-hours plus
   one fixed-node stage) and a throttled speed-to-Elo measurement (2 STC
   stages plus 1 LTC stage, replacing item 4's 0.85x time odds).
6. **Rebuild the removal round as a factorial screen** (ST5 with B14's four
   fixes): 22-32 stages that decide every low-prior switch, against about
   260 stages for the planned per-feature [−3, 0] SPRTs, which confirm a
   neutral removal only 5% of the time.
7. **Build the TCEC binary on purpose** (H1 without VNNI): x86-64-v4 with the
   parked AVX-512 output layer (C1), PGO with a fallback, the compiler chosen
   by a local A/B. Worth 0 in Fork's tests (both sides share the build) and
   **+3 to +10 at TCEC**. C1 also speeds data generation today (+2-3.5%),
   which needs no TCEC decision. VNNI stays blocked by the owner's
   2026-10-28 rule until TCEC answers (KB competition.md question 8 [V]).
8. **Network capacity: screen first, build at most one family, park
   threats.** No input family has a strong prior (B13 §3.5). Price designs
   with a zero-row build (H3), rank families by their residual against deep
   labels, and probe output-side capacity (W2) on CPU before any GPU time.
   Threat inputs are about −8 Elo expected at 1.5 Elo per 1% nps (B13).

### 1.2 The honest total, without double counting

Head-to-head Elo at LTC (40+0.4), for the rest of Phase 4. Ranges are
placeholders from the ranked list; the sum is shrunk for interactions and
for the winner's curse (ST2: 8-16% on adopted features; larger on small
passers).

| Block | Range | Central | Notes |
|---|---|---|---|
| Item 8 (retrain on g3s3) | +4 to +12 | +7 | B13's adjusted figure; the one-time anneal is already banked in S512ppr2 |
| Later retrains (8b, 8c) | +2 to +10 | +5 | each needs about 150 M new kept positions from a promoted labeller |
| Node-share TM + stability | +5 to +12 | +8 | zero nps; does not flow into labels; three engines' records (OS, OS-Stormphrax), shrunk |
| SPSA, early pass + final pass | +4 to +12 | +7 | R14 +3 to +8, R24 +1 to +6, not additive at the top |
| Search features under design R (14-17 tests) | +4 to +12 | +7 | ST1's yield under B14's tighter priors; adds R40 and R41 and firmer priors for R7, R12, R15, R16, R34 |
| Speed work, bench-identical (H4, H5, H7) | +2 to +7 | +4 | at 1.5 Elo per 1% nps; also more data per CPU-hour |
| Network capacity and training extras (one family or W2, the result-weight arm or R39's high-WDL branch, recency, book, slice) | 0 to +9 | +3.5 | probability-weighted; most may fail their gates |
| Removal round | 0 to +2 | +1 | mostly simplicity |
| **Sum of centrals** | | **+42.5** | |
| **After interaction shrink (about 10-15%)** | **+22 to +52** | **+37** | |

- **On a third-party list** divide by 1.0-1.7 (A1 §2.2, UNVERIFIED): about
  +13 to +50.
- **What OS-Stormphrax changed:** about +2 on the central (TM, SPSA, search
  features, one training branch). Its numbers are one engine's SPRT-selected
  estimates, so they moved ranges modestly and changed no verdict.
- **TCEC only:** the TCEC build adds +3 to +10 that no Fork test sees, and
  node-share TM is plausibly worth more at 30'+3" than at 40+0.4
  (UNVERIFIED).
- **For comparison**, the §5.6 order as written would spend about 550 or more
  STC-equivalent stages on its remaining search work (ST8) for perhaps half
  the search Elo, and would run three negative-expectation items
  (distillation from S512+X, idea 23 on its biased proxy, S512cl's speed
  work).

### 1.3 What the evidence says is not worth doing

- **Distillation from S512+X** (idea 46 rank 1): REFUTED (B13). The teacher
  is about 40 fixed-node Elo weaker than the default, and there is no
  generalisation gap to regularise.
- **S512cl's speed work** (item 14): full-width incremental contact rows
  cannot reach 0.90x by arithmetic (H3: about 22-33% of node time before
  discovery), and its 54 MB table would be DRAM-bound at TCEC (H9).
- **Threat inputs now** (H8, SF's narrow side accumulator, idea 46 ranks
  3-5): expected −8 (−20 to +5) at the measured speed price (B13).
- **The removal round as planned**: about 260 stages, removes almost
  nothing (A3 §2.6, ST5).
- **Idea 23's long run on the label-and-sweep proxy**: the proxy never
  predicted a gain and correlates at ρ ≈ −0.3 with SPRT outcomes (A2 §6).
- **The full fractional-depth refactor** (idea 43 level 2): about 0 Elo in the
  surveyed family; only round-once LMR arithmetic is needed (PA §3.2, B14
  §3.6).
- **The planned speed-to-Elo design** (0.85x time odds, 4,000 games): R to
  ±27 and biased by per-move latency; the throttled 0.5x design gives ±9 for
  fewer games (ST3).
- **S512+X and AF-S as "LTC candidates"**: the speed price barely falls from
  STC to LTC (XGR: 95 against 101 per doubling; A3 §1.4).
- **A blind result-weight ladder, a WDL-heavier end of training, TD-k
  targets or cross-entropy in item 8's main arms**: the result's bias is
  class-dependent and unmeasured; measure it first (B13 §3.2).
  OS-Stormphrax's high-WDL fine-tune gain earns only a cheap, guarded branch
  on a finished candidate (R39), never a change to the control.
- **Re-validation filler as queued** (B-3, the root fail-high fix, plain
  B-4, keep-exact): posterior means about 0 or below (ST8); the root
  fail-high premise does not arise in timed play (R8 below).
- **Also not now:** a dual net or PSQT shortcut, material or "major"
  correction tables, king buckets, a multi-layer head, fifty-move inputs,
  contempt, a first-move-out-of-book bonus, pulling SMP forward, a new test
  book (ST: the current book is within about 3% of maximum sensitivity),
  fixed-node games as variance reduction (they are not: ST).

---

## 2. The ranked list

### 2.0 Effort unit and method

**One effort unit (EU)** = one engineering day (an agent's working day), or
8 GitHub-hours (about 26 STC stages; an LTC stage counts as 4 STC stages),
or 10 Kaggle GPU-hours, or 10 local CPU-hours of a 2-thread job beside data
generation (a quiet-machine hour, with data generation paused, counts as 2
CPU-hours). GPU and CPU are cheap relative to GitHub and engineering, which
the unit reflects. **Elo/EU** = the central expected Elo at LTC divided by the
EU cost, with shared infrastructure split between its users. Enablers (no Elo
by themselves) are ranked separately, by information per cost.

Confidence: H high, M medium, L low. "Owner?" marks items that need an owner
decision before they run.

IDs are stable labels; the ranks were recomputed after folding in the
Stormphrax supplement (**OS-Stormphrax**: Phase B file, section B2,
supplement). Its numbers are one engine's SPRT-selected OpenBench point
estimates, so they were shrunk like every other survey prior: they move a
range by at most a third of the distance toward the external figure, and
never past what B13/B14 allowed for the same mechanism. The new items are R39,
R40 and R41; R7, R8, R12, R14, R15, R16, R24 and R34 changed range.

### 2.1 Summary table: Elo items

| Rank | ID | Title | LTC Elo (range) | Effort (EU; main resources) | Elo/EU | Conf. | NOVEL? | Owner? |
|---|---|---|---|---|---|---|---|---|
| 1 | R1 | g3h from the 2026-09 book | +0.7 (0 to +3) | 0.15 (a duplicate count; a setting) | 4.7 | L | no | yes |
| 2 | R2 | **Item 8: retrain on g3s3** (control + cooldown + anneal-only arms) | **+7 (+4 to +12)** | 1.9 (1 eng day, 6 GPU-h, 1-3 STC stages) | 3.7 | M | no | yes (recipe arms) |
| 3 | R3 | Recency arm in item 8 (half-weight S512 labels, never a hard purge), gated by the gold set | +1 (−2 to +6) | 0.3 (2 GPU-h) | 3.3 | L | no | no |
| 4 | R7 | Fail-firm RFP return | +1.5 (0 to +3) | 0.45 | 3.3 | L-M | no | no |
| 5 | R4 | Cut-node LMR (sub-ply) + TT-PV LMR at LTC | +2.5 (0 to +5) | 0.9 (built; ~6 STC + ~5 LTC stages) | 2.8 | M | no | no |
| 6 | R5 | Later retrains (8b, 8c) by the cadence rule | +5 (+2 to +10) | 2.0 (Kaggle, datagen lane) | 2.5 | M | no | no |
| 7 | R8 | **Node-share TM + best-move stability (+ score trend if X6 supports it), in Phase 4** | **+8 (+5 to +12)** | 3.3 (2 eng days, 3 CPU-h, ~8 GitHub-h) | 2.4 | M | method partly | **yes** |
| 8 | R12 | Upcoming repetition, as a correctness change | +1.5 (0 to +3); more at TCEC | 0.65 | 2.3 | L-M | no | idea 31 first |
| 9 | R6 | NMP at expected cut nodes; IIR gated by node type | +2 (0 to +4) | 0.9 | 2.2 | M-L | no | no |
| 10 | R9 | One link-pair enumeration for both perspectives | +2.5 (+1.5 to +4) | 1.2 (1 eng day, quiet A/B) | 2.1 | M | no | needs X13's rule |
| 11 | R10 | Post-LMR re-search depth from the reduced result | +1.5 (0 to +3) | 0.7 | 2.1 | L | no | no |
| 12 | R16 | History ageing between searches (per-`go` scaling) | +1.5 (0 to +3) | 0.7 | 2.1 | L-M | no | no |
| 13 | R11 | TCEC build: v4 + C1 (no VNNI) + PGO + compiler by A/B | 0 in tests; **TCEC +3 to +10** | 2.8 (2.5 eng days, 3 quiet h) | 2.1 (TCEC) | M | no | **yes** |
| 14 | R14 | **Early SPSA of the eight eval-dependent margins** | **+5 (+3 to +8)** | 2.8 (half of the driver, 9 GitHub-h) | 1.8 | M | no | **yes** |
| 15 | R39 | High-WDL final fine-tune of a finished candidate (a branch, judged by FN then STC) | +1 (−3 to +6) | 0.6 (0.3 GPU-h, 1 FN stage, an SPRT if it wins) | 1.7 | L | no | **yes** |
| 16 | R15 | History mechanics: linear bonus, TT-cutoff bonus, eval-fail-low bonus, joint continuation cap | +2.5 (0 to +5) | 1.6 | 1.6 | L-M | no | no |
| 17 | R13 | TT-eval hygiene (stand-pat refined only by main-search entries) | +1 (0 to +2) | 0.65 | 1.5 | L | no | no |
| 18 | R41 | Eval-change adjustment after a reduction (extend a reduced move whose eval improved; reduce one whose eval collapsed) | +2 (0 to +5), mostly LTC | 1.3 (0.5 eng day, ~5 LTC stages) | 1.5 | L | no | no |
| 19 | R17 | Improving as a measured mean shift (LMP first, then LMR) | +1.5 (0 to +3) | 1.2 | 1.25 | M-L | no | no |
| 20 | R18 | LMR for late and bad captures | +1.5 (0 to +3) | 1.2 | 1.25 | L | no | no |
| 21 | R19 | Network weights and history tables on huge pages | +1 (0 to +3) | 0.8 | 1.25 | L | no | no |
| 22 | R40 | Negative extension at expected cut nodes only, sub-ply, at LTC | +1.5 (0 to +4) | 1.3 (0.5 eng day, ~5 LTC stages) | 1.15 | L | no | yes (confirm it is a new idea, not a retest) |
| 23 | R20 | Round-once LMR + a centred, mean-preserving history term (idea 42 as its variant) | +2 (0 to +4) | 2.0 | 1.0 | M | partly | no |
| 24 | R21 | Pawn-structure history, gated by the cutoff-index metric | +0.3 (0 to +2) | 0.3 | 1.0 | L | no | no |
| 25 | R22 | Aspiration half-width re-measured (and score-dependent) | +0.3 (0 to +1) | 0.3 | 1.0 | M | no | no |
| 26 | R23 | Fused last-ply update + output kernel | +2 (+1 to +4) | 2.1 | 0.95 | L-M | no | report the maintenance cost |
| 27 | R24 | **Final retune by scaling class** (+ VLTC spot check) | +3 (+1 to +6) | 3.5 | 0.86 | M | no | **yes** |
| 28 | R25 | Adaptive rounding of the output layer | +0.8 (+0.5 to +1.5) | 1.0 | 0.8 | H (size) | no | no |
| 29 | R26 | Output experts chosen by frozen-feature probes | +2 (0 to +6) | 3.3 | 0.6 | L-M | method | no |
| 30 | R27 | Result-weight arm at the measured w* (either direction) | +1 (−2 to +6) | 1.6 | 0.6 | L | the derivation | no |
| 31 | R28 | Double extensions + depth-concave singular margin, LTC only | +1.5 (0 to +3) | 2.4 | 0.6 | L | partly | no |
| 32 | R29 | Quiet history pruning, after X2 and R16 | +0.3 (−1 to +2) | 0.5 | 0.6 | L | no | no |
| 33 | R30 | Removal round as a factorial screen | +1 (0 to +2), plus simplicity | 2.0 | 0.5 | M | **NOVEL** (process) | **yes** |
| 34 | R31 | Eager child update before the TT read (runner/TCEC regime only) | +1 (0 to +3) | 2.2 | 0.45 | L | **NOVEL** | yes (doctrine) |
| 35 | R34 | Correction tables: passive ranking, then the best key at LTC | +2 (0 to +4) | 4.5 | 0.44 | L-M | count gain | no |
| 36 | R32 | Depth-matched endgame-start slice | +1 (0 to +4); more at TCEC | 2.7 | 0.4 | L | partly | **yes** |
| 37 | R33 | Structure-class calibration scale on the eval | +1 (0 to +3) | 2.7 | 0.4 | L | no | yes (fit data) |
| 38 | R35 | Tail-risk-classed margins | +0.8 (0 to +3) | 3.5 | 0.23 | L | partly | no |
| 39 | R36 | One new input family, chosen by the screen (king-zone pawns or passers) | +1.5 (−3 to +6) | 7.5 | 0.2 | L | yes (UNVERIFIED) | no |
| 40 | R37 | n-step / λ-return value targets (second line) | +0.5 (−3 to +5) | 2.5 | 0.2 | L | yes (UNVERIFIED) | no |
| 41 | R38 | Idea 23 as a capped pilot with a game-based fitness | +1 (0 to +4) | 4.5 | 0.2 | L | partly | **yes** (or archive) |

Not recommended in Phase 4 (each with its B13/B14 verdict): cross-entropy
loss (WEAK-PLAUSIBLE; only once conversion-phase data exists), the threat
side lane (WEAK, about −8), accumulator policy ordering (WEAK, a plan
change), width narrowing or widening (WEAK), king buckets (WEAK), a
multi-layer head (WEAK for Phase 4; OS-Stormphrax's head grew with TC, but the
speed price and quantization risk at Fork's 512 width are unchanged), the
scratch equal-compute control (low
value), the 25% save-share arm (WEAK), QS futility (the qs-delta precedent is
null and the eval-avoidance ceiling is low, H §3.8; OS-Stormphrax reports a
gain for it, so it may run as idle filler, never ahead of ranked work), an
LTC-only ProbCut retest (OS-Stormphrax: neutral at STC, positive at LTC; Fork's
STC result was −5.3 and the owner ruled "no retest", so this is only an owner
question, §7 item 25).

### 2.2 Summary table: enablers and measurements, ranked by information per cost

| Rank | ID | Measurement or tool | Cost | Gates | Credits |
|---|---|---|---|---|---|
| 1 | X1 | Search counters: evaluations per node, quiescence share, TT-eval hits, refreshes per 1,000 updates, rows per update, pawn-move share | minutes, one stats bench | R9, R23, R31, R36 pricing; every eval-avoidance idea | A3 §1.2, H2 item 4, PA M4 |
| 2 | X2 | In-game history magnitudes (20 stats-build games) + the LMR-history branch's nps | 1-2 CPU-h | R20, R29 (and the order of R16); explains the −10.8 | A2 O3, S2, S8, B14 §3.7, PA M1 |
| 3 | X3 | Runner A/B speed job (identical-tree benches on shard runners, `lscpu` logged) | 0.5 eng day; ~15-30 min of one runner | the speed gate ratio in the build that plays, the S512+X outlier, C3's re-judgement, the TT regime, ST3's design | H2 item 3, A1 §4.2, PA M3, B14 §3.2 |
| 4 | X4 | Anneal attribution (S512+PP + 40 superbatches at 1e-5 on its own data, Elo-judged) + the two-seed soup | 0.5 GPU-h + 1 FN stage; CPU minutes | item 8's forecast; datagen-vs-training priority; the averaging premise | T6, W5, W3 D1, B13 §3.1 |
| 5 | X5 | SPRT design R + head-to-head constant selection (tooling) | 0.5 eng day | every search test after it | ST1, ST6, A3 §2.6, B14 §2.ST1 |
| 6 | X6 | Node-share fit: P(best move changes) against share, stability, score change, on ~2,000 positions; AUC and ρ_s² | 1-4 CPU-h | R8's go/kill and its curve (Fork's own) | S1, W1(a), B14 |
| 7 | X7 | Combined deep relabel: one stratified held-out sample, deep labels, four outputs (gold set, label noise, category shifts, residual by family) | 0.5 eng day + ~2 h on 2 threads | R3, R27, R36, idea 46's residual study | T3, C2, A1 B2, PA M7, B13 §3.5 |
| 8 | X8 | Throttled speed-to-Elo: a 0.5x test-only build, 2 STC + 1 LTC stages, per-shard in-situ ratios | 1 eng day (shared with X12) + ~2 GitHub-h | the gate price, the LTC-candidate bucket, idea 46's hurdles | A3 §1.5, ST3, H3, B14 §2.ST3 |
| 9 | X9 | Tier-2 block check on S512ppr2 (switches off together, 2 stages) | 2 STC stages | additivity of tier 2 on the new net; R30's step 0 | ST2 |
| 10 | X10 | Decision ledger (sampled counterfactual prunes), RFP and futility rows first | 2 eng days + 1-3 CPU-h | R14's ranges and parametrisation, R17, R35, R24's shapes | I1, S4, A2 O4, S3 |
| 11 | X11 | Corrected decisive-share pilot (20k with the split search against 100k, randomised replicates) | 1-1.5 CPU-h (2 threads) | R27 | T5, B13 §3.2 |
| 12 | X12 | Zero-row / zero-lane / throttle calibration build | 1-2 eng days + 1 quiet h | prices R36 and any input design before GPU time; supplies X8's throttle | H3, B13 |
| 13 | X13 | Measurement stack: cycles:u and instructions:u per bench node, a 1% acceptance rule, cachegrind at TCEC cache geometry | 2 eng days | R9, R19, R23, R31 | H2, SF 7.2.8 |
| 14 | X14 | Gauntlet of S512ppr2 + the knowledge-gap ledger and blind-spot suite | 1 GitHub run (~1-2 h, UNVERIFIED) + 1-2 eng days | external calibration; whether king-zone blind spots persist after the links (R36) | C1, owner's open item |
| 15 | X15 | Searched validation loss (quiescence and depth-2 value against the target) | 1.5 eng days + 1 CPU-h | ranking architectures (R26, R36) | M1 |
| 16 | X16 | Two-depth scaling classifier (node saving at depth 12 against 16) | 0.5 eng day; minutes | the LTC list; R30's routing | S9 |
| 17 | X17 | Stage throughput audit (job timings; cached engine builds; poll interval) | read-only, then 0.5-1 eng day | +15-25% stages per hour (UNVERIFIED) | ST7 |
| 18 | X18 | SPSA driver on GitHub (FORK_TUNE shard builds, micro-matches, gradient merge, jobctl driver) | 2-3 eng days | R14, R24, R30 (per-shard options), mini-SPSA | O4, O2, B14 §2.O4 |
| 19 | X19 | Extended endgame acceptance test (4-5-man classes) | 1 eng day | guards every retrain | C6 |
| 20 | X20 | Deep-search sanitizer audit (long single-thread searches under ASan/UBSan) | ~4 machine-h | TCEC safety | TC §2.H |
| 21 | X21 | Fixed-node doubling ladder (Elo per doubling against node budget) | 3-6 GitHub-h | TCEC speed-against-quality; late or optional | TC §2.C, PA M10 |
| 22 | X22 | Coverage and duplicate histograms of training data | CPU hours | R1, R32 | A1 B5, T8(a), PA M11 |
| 23 | X23 | Rule: TT-policy tests at a hash scaled to TCEC's entries-per-node pressure | free | any TT change | TC §2.E |

### 2.3 The entries, Elo items

Each entry gives the mechanism with its key derivation line, why it fits
Fork, the speed cost, data and compute, originality notes and credits, the
cheapest first experiment, a falsifiable prediction and a kill criterion.
Where a skeptic adjusted the agent's claim, the skeptic's figure is used.

#### R1. g3h from the 2026-09 book (T8a + OS N5 + A1 §8)

- **Mechanism.** Every part since g0 starts from lichess-2016-09 (591,871
  positions); g2 and g3 played about 25 M games, about 42 per opening. The
  unused lichess-2026-09 book (13.9 M positions, HANDOFF §3) gives about 1.8
  uses per start at the same volume, so early positions repeat far less.
- **Math.** If at least 10% of kept positions are early near-duplicates, the
  effective data is 10% smaller: −0.15 doublings, about −2 Elo at 10-20 Elo
  per doubling. Breadth may add a little more. Expected 0 to +3.
- **Why Fork.** A1 §8 "Opening diversity"; the next part starts anyway.
- **Speed cost; data.** None; a setting recorded in g3h's manifest.
- **Originality.** Lichess CC0 positions under the A+ policy.
- **Cheapest first experiment.** The duplicate count (64-bit Zobrist
  histogram over one shard per part), minutes.
- **Prediction.** At least 5% of kept positions at ply ≤ 20 are duplicates;
  refuted if under 2% (then the switch is cosmetic, still harmless).
- **Kill.** None needed; the switch costs nothing.

#### R2. Item 8: the next retrain on g3s3 (T1 + B13 §4 + A1 B2 + W3 D1 + T2 + W5)

See §5 for the full recipe. Summary:
- **Mechanism.** New labels from S512+PP and S512ppr2 (g3f, g3g; about
  158 M new kept positions, +19%, about +20 chain Elo of mean labeller),
  trained by the standard warm recipe, with a cheap cooldown-and-averaging
  branch (removes the residual LR-noise floor) and an anneal-only arm (tests
  whether warm retrains need their stable phase at all).
- **Math.** A1's model: 0.25 doublings × (10-30) + 0.31 × 20 ≈ +9 to +14,
  discounted for self-play inflation and for the anneal that S512ppr2
  already banked (B13 §3.1: the anneal explains perhaps +8 to +15 of its
  +20.1). Cooldown and averaging: the excess loss left at 1e-5 is about
  1.6-1.9e-4 / 9 ≈ 2e-5, so +1 to +3 (B13 §3.1, W3 §0). **+4 to +12, central
  +7.**
- **Why Fork.** The generational loop is Fork's proven engine (A1 §2); the
  warm recipe is understood (B13 §2.1).
- **Speed; compute.** No runtime cost; 5.0-7.1 GPU-h; 1-3 STC stages.
- **Prediction.** STC [0, 5] H1 with a final estimate of +4 to +12; refuted
  if H0 or below +3.
- **Kill.** If the best candidate's full-set offline loss is not at least
  2e-5 below S512ppr2's on g3s3-val, do not spend an SPRT; wait for g3h.

#### R3. Recency arm: half-weight S512 labels (T4 + OS N1 + W critique 3 + OS-Stormphrax + B13)

- **Mechanism.** About half of g3s2 is S512-labelled (about −200 chain Elo
  behind the default). With no generalisation gap, old labels add bias more
  than information. Arm B drops every other g2s1 file and lists g3g twice.
- **Math.** B − A ≈ 0.31 × 22 − 0.33 × (10 to 30) = −3 to +3.5 (T4): the
  model cannot sign it. External records lean positive but are SPRT-selected.
  −2 to +6.
- **OS-Stormphrax's data curriculum (concept).** Its newer, deeper-labelled
  data trained *alone* lost at STC and won only at long TC with threads; a
  staged recipe that kept the old data in the final stage beat the hard
  switch at STC and LTC. Two readings for Fork: (a) never purge the old
  labels outright: arm B down-weights g2s1, it does not drop it, and a
  "no g2s1" arm stays off the table; (b) Fork's standard warm recipe already
  has the winning shape (the lineage trained on the old data; each retrain
  trains on old and new together), so no staged-curriculum arm is needed in
  item 8a. The range stays −2 to +6; the evidence narrows the design, not the
  size.
- **Why Fork.** A1 §8 "old-label share"; idea 47.1's planned generation-1
  relabel targets data no current snapshot contains (T4).
- **Compute.** One 2.15 GPU-h arm in item 8's session.
- **Originality.** Data mixing by file list; no constants.
- **Cheapest experiment.** The arm itself, **only if X7's gold set exists by
  Sunday evening**: a validation set drawn from old or new data favours one
  side, so only a deep-label yardstick can judge a data-mix change (B13).
- **Prediction.** B's gold-set loss is at least 2e-5 below A's; refuted if
  B ≥ A, which also drops idea 47.1 for Phase 4.
- **Kill.** As refuted.

#### R4. Cut-node LMR with a sub-ply amount, and TT-PV LMR at LTC (S5 + S2 + A2 O6 + SF 7.1.b + OS 4.5 + batch 4)

- **Mechanism.** At an expected cut node only the refutation matters, so late
  moves can be reduced more; nodes once on a PV are reduced less. Batch 4
  has both behind switches as whole-ply placeholders; with round-once
  arithmetic (R20) the amount becomes sub-ply.
- **Math.** A rate change per ply (M2 of S: g² = Σ g^(−r_i)), so its value grows
  with depth; S5 puts cut-node LMR at +3 ± 3 whole-ply, +3.5 ± 2.5
  sub-ply, P(H1 under today's design) 0.28. B14 shrinks the shared LMR
  payload to +2 to +6 with R20 and idea 42. Here: +2.5 (0 to +5).
- **Why Fork.** Fork has no node types and never reads its stored TT-PV bit
  (A2 §1.3). Selectivity that defers or verifies information paid (IIR +21.5
  STC, +26.3 LTC); this is the same class.
- **Speed cost.** A flag read.
- **Compute.** Cut-node at STC under design R (about 5 stages); TT-PV is on
  the LTC list (about 5 LTC stages).
- **Originality.** Generic CPW node types (Knuth and Moore 1975); amounts by
  head-to-head selection (ST6), then the constant screen.
- **Cheapest experiment.** A head-to-head of ½ ply against 1 ply (2 stages),
  then design R against off.
- **Prediction.** Cut-node LMR passes design R at +2 to +5 STC; LTC estimate
  at least as large. Refuted if H0 at both amounts.
- **Kill.** H0 at both amounts; TT-PV LMR killed by its own LTC test.

#### R5. Later retrains by the cadence rule (T critique 11 + A1 B2 + PA §2.1)

- **Mechanism.** Each promotion or adoption starts a new part labelled by
  the new default (labeller policy). A retrain pays an SPRT slot when
  0.31·Δ(mean labeller) + a·Δlog₂(data) ≥ about +8, i.e. when new labels are
  at least 15-20% of the snapshot at a labeller jump of +20-30 chain Elo.
- **Math.** About 135-150 M kept positions take about 1.5-2 days of data
  generation (g3g's rate). Search adoptions that survive at 20k nodes raise
  the labeller too; at b ≈ 0.3 the loop returns about 30% of them a second
  time through the student (low confidence; A1 §2.2). Two more retrains at
  +1 to +5 each: +2 to +10.
- **Why Fork.** Label quality is the proven lever; volume is not binding
  (A1 §3.3).
- **Compute.** About 5 GPU-h and 1-3 stages per retrain.
- **Prediction.** Each retrain's SPRT estimate falls with the new-label
  share; refuted if a retrain with ≥ 20% new labels from a +20-labeller
  scores under +2.
- **Kill.** Two consecutive retrains under +3 → pause the loop until a
  larger labeller jump.

#### R6. NMP at expected cut nodes; IIR gated by node type (S6 a-b + OS 4.5 + B14)

- **Mechanism.** At a true all node the null search fails high only when the
  type prediction was wrong; its d/2-deep probes are mostly wasted there
  (about 13% of the node's subtree at d = 8, 5% at d = 12, by g^(d/2)/g^d
  with g = 1.66). IIR is justified by poor ordering, which matters only at
  cut and PV nodes.
- **Math.** Gain ≈ (1 − p)·(probe share) at expected all nodes, where p is
  the probe's success rate there; positive when p is small.
- **Why Fork.** NMP runs at every non-PV node with eval ≥ β (A2 §1.1); IIR
  fires at every node type.
- **Speed cost.** A flag read. Needs batch 4's `expected_cut`.
- **Cheapest experiment.** One stats bench: NMP success and IIR firing split
  by expected node type. If NMP's success rate at expected all nodes exceeds
  30%, drop (a).
- **Prediction.** NMP-at-cut passes design R at +2 to +4; refuted by H0. For
  IIR, the cut-and-PV form beats every-type by +1 to +4; refuted if both
  gated forms reach H0.
- **Kill.** As each prediction's refutation.
- **Originality.** Generic concepts; no constants.

#### R7. Fail-firm RFP return (A2 O5 + OS 4.7 + OS-Stormphrax)

- **Mechanism.** RFP returns the full `prune_eval`; returning a value between
  it and β limits inflated fail-soft bounds entering the TT.
- **Why Fork.** Every eval-gated loosening lost (A2 §3.1); this changes the
  bound, not the prune rate.
- **Evidence.** Two engines in the OS survey plus OS-Stormphrax (two passes,
  one depth-dependent) report gains at STC and smaller ones at LTC; shrunk,
  the range rises from 0 to +2 to **0 to +3 (central +1.5)**.
- **Cost.** A few lines; zero nps; the midpoint form has no tuned constant
  (a depth-dependent blend would be a constant to measure, not to copy).
- **Prediction.** Passes design R at +1 to +3 with bench nodes within ±2%;
  refuted by H0.
- **Kill.** H0.

#### R8. Node-share time management plus best-move stability, moved into Phase 4 (A2 O1 + S1 + W1(a) + SF 7.1.a + OS 4.2 + OS-Stormphrax + TC F.1 + ST8(b); verdict B14)

- **Mechanism.** After each completed iteration, scale the soft limit by a
  decreasing function of the best move's share of that iteration's nodes
  (normalised so the mean spend is unchanged), and extend when the best
  move changed in the last iteration. Fork already computes the shares every
  iteration (searcher.cpp lines 800-805 [V]). A score-trend term (Fork also
  records `score_trend_`) is a third candidate signal, added only if X6
  shows it predicts best-move changes beyond share and stability.
- **Math.** Allocating time t_i ∝ c_i under log utility gains about
  exp(ρ_s²·CV²/2) in time equivalent (S1 M5): at ρ_s²·CV² = 0.10, ×1.05,
  about +7.6 at 106 Elo per doubling. ρ_s² is assumed until X6 measures it.
  B14's shrunk range from two engines: +3 to +8 STC, +4 to +10 LTC.
  OS-Stormphrax adds a third engine whose node-fraction term was its largest
  single LTC search gain (about +21 LTC, at node-scaled controls), with
  stability and score trend adding about +3 to +5 each at LTC; like the
  others it is an SPRT-selected first-term gain in an engine with no dynamic
  TM before. Three engines now agree in sign and in "LTC ≥ STC". Shrunk:
  **+4 to +9 STC, +5 to +12 LTC (central +8)**. The iteration granularity
  trims it slightly (a 0.6x soft limit moves the realised spend less than
  0.6x).
- **What is dropped.** The "resolution-aware soft stop": the soft check
  (line 816) runs only after the aspiration loop (lines 761-776) has
  resolved the iteration's score, so no root fail high is pending there
  [V, confirming B14]. Idea 29's 1.8% came from node-limited bench
  searches cut mid-iteration. Only the stability term survives.
- **Why Fork.** Fork has no dynamic term (A2 §4); TCEC's 30'+3" makes every
  start and stop a large block of time; the final gauntlet and every LTC
  test should play with the TM that TCEC will see.
- **Labels.** Untouched: datagen sets only a node limit, `soft_ms = −1`
  gates every TM branch (B14 [V], self_play.cpp). The term must stay inside
  that guard and must read, not change, the shares idea 23's LMR context
  uses. The flip side: TM gains are not amplified through the label loop.
- **Compute.** About 2 engineering days; X6 (1-4 CPU-h); a 2-value
  head-to-head (≤ 4 stages), design R at STC (about 4-6 stages), then LTC
  (TM belongs on the LTC list; 3-4 LTC stages).
- **Originality.** The idea is generic and its lineage is credited in the KB
  (time-management.md §4.4). The curve and slope come from Fork's own fit
  (X6), not from any engine's factors; the constant screen runs before the
  commit.
- **Prediction.** X6's logistic model has AUC ≥ 0.70; the STC test passes at
  +4 to +9; LTC ≥ STC within error. Predict the STC Elo from X6's ρ_s²
  before the run and kill the *method* if the measured Elo lies outside
  0.5-2x the prediction (B14).
- **Kill.** AUC < 0.65 (fall back to the plain share term with a ladder),
  or H0 at both values.
- **Owner.** A plan change: DESIGN puts time management in Phase 5 (lines
  425 and 765 [V]). Base allocation, the time curve and anything tuned at
  a TCEC-shaped control (base/increment 600) stay in Phase 5.

#### R9. One link-pair enumeration per move for both perspectives (H4)

- **Mechanism.** The changed pawn-link pairs are enumerated once per
  perspective today, although the set of changed pairs is the same; only the
  final index mapping differs. Enumerate once, map twice.
- **Math.** Links cost about 150 cycles per node; enumeration is about 60% of
  the pair search's instructions; sharing saves about 35 of about 1,400
  cycles: +2.5% nps (1.5-3.5%), +2 to +5 Elo at 1.5 per 1% (B14: +1.5 to +4).
- **Why Fork.** Every speed win in idea 40's log came from fewer
  instructions (A3 §1.3).
- **Speed; compute.** A speed gain, bench-identical; needs X13's 1% rule to
  be accepted, since it sits under the 3% rule.
- **Prediction.** instructions:u per bench node −1.5% to −3%; refuted if
  under −1%.
- **Kill.** cycles:u gain under 1%.
- **Originality.** Fork's own code; new names screened.

#### R10. Post-LMR re-search depth from the reduced result (S6c + OS 4.6 + SF 7.1)

- **Mechanism.** When the reduced search beats α by a wide margin, re-search
  one unit deeper; when it barely does, one unit shallower. The reduced
  result is information about the move.
- **Why Fork.** Fork re-searches at exactly full depth (OS 4.6). Low-ρ
  selectivity class (S M3).
- **Cost.** One comparison per re-search; the margin from X10's LMR miss-rate
  rows, not from any engine.
- **Prediction.** Passes design R at +1 to +4; refuted by H0 at both margins.
- **Kill.** H0.

#### R11. The TCEC build on purpose (H1 + A3 §1.7 items 1, 3, 4 + PA M2; verdict B14 §3.8)

- **Mechanism.** update.sh builds clang-19 x86-64-v3 with no PGO (B14 [V]),
  and the output layer has no AVX-512 path anywhere. Build x86-64-v4 with
  C1's AVX-512BW output path when the CPU has it (a startup CPU check that
  fails loudly at `uci`, or a launcher if TCEC accepts one), PGO by default
  with a fallback to the plain build, and the compiler chosen by a local
  A/B among TCEC's four. The 7600X3D is the same core family as TCEC's Zen
  4c (UNVERIFIED in detail).
- **Math.** C1 +1.5 to +3.5%, v4 updates +0 to +2%, PGO +2 to +8%
  (unmeasured), compiler ±5%: +4 to +18% nps, central about +9% (H1, from
  memory of Zen 4 resources, UNVERIFIED). At TCEC the Elo per 1% is unknown;
  H discounts it to 0.5-1.0: **+3 to +10 at TCEC** (B14).
- **Side benefit now.** Datagen's PGO build already defaults to native (B14
  [V], cmake/pgo.cmake), so un-parking C1 speeds data generation by about
  +2-3.5% positions per CPU-hour at unchanged labels. This half needs no TCEC
  decision.
- **Compute.** 2-3 engineering days; 2-3 quiet hours (16 builds × 10
  interleaved rounds). Best in the quiet window at g3g's seal (§6).
- **Prediction.** v4 + C1 beats v3 by +3 to +6% on the identical tree; PGO
  adds +2 to +8%; refuted if v4 + C1 is under +1.5% or PGO under +1% on every
  compiler.
- **Kill.** Axis by axis below +1% (cycles per node) or below the harness
  rule.
- **Owner.** update.sh's default for TCEC; VNNI stays out (the 2026-10-28
  rule); the final gauntlet should play the TCEC build if it differs.

#### R12. Upcoming repetition, as a correctness change (S5 + batch 4 + KB §3.29 + OS-Stormphrax)

- **Mechanism.** Detect a reachable repetition one move early, for earlier
  draw scores and cheap cutoffs (cycle detection, van Kervinck, KB).
- **Evidence.** OS-Stormphrax passed it twice with sizeable STC gains; shrunk
  and discounted for UHO's lower repetition rate, the range rises from 0 to
  +2 to **0 to +3 (central +1.5)**, more at TCEC.
- **Why Fork.** UHO openings repeat less than TCEC's balanced-ish openings,
  which are never win-adjudicated, so SPRTs undervalue it (S5). Its history
  walk grows in long endgames: measure nps on an endgame-heavy set (S5).
- **Order.** Decide idea 31's pre-root convention first (S5; KB §3.29
  records a published correction for exactly that case).
- **Test.** Design R on non-regression bounds (a correctness change, B-1's
  precedent).
- **Prediction.** Within [−2, +2] at STC with no nps loss on endgames;
  refuted if worse than −2.
- **Kill.** Fails non-regression.

#### R13. TT-eval hygiene (I8; replaces the plain B-4 retest)

- **Mechanism.** B-4 refined the quiescence stand-pat by any TT bound and
  lost (−4.11 ± 3.93). Most quiescence entries are depth-0 results from
  window-dependent searches, so the refinement fed the search's own bounds
  back into itself. Refine only by main-search entries (depth ≥ 1). The
  ledger (X10) separately checks whether depth-0 refinements of
  `prune_eval` help.
- **Prediction.** Passes non-regression and lands at 0 to +3.
- **Kill.** H0 → off for good.

#### R14. Early SPSA of the eight eval-dependent margins (O1 + O2 + O3 + O6 + OS 4.1 + OS-Stormphrax + ST8(a) + PA rank 1; verdict B14 §3.1)

- **Mechanism.** Tune RfpMargin, FutilityOffset, FutilityGrowth,
  NullSurplusPerPly, AspirationHalfWidth, QuietSeeFloor, CaptureSeeFloor and
  LmpQuietAllowance jointly at STC. All but the history weights and SE's
  constants were set for the bootstrap evaluator and never refit (A2 §1.4).
- **Math.** One game pair informs every parameter at once: pair sd 0.21 =
  146 Elo per pair; the stationary loss per parameter is σ²/16·α, so the
  gain rate is set from a loss budget (O §0). O's simulation recovers about
  80% of a recoverable T at p = 8 in 20k games. **B14: +2 to +8 STC, central
  about +4; LTC +2 to +7.** The surveys' +15-35 is the mean of four SPRT-
  selected whole-set tunes in two engines, then raised: discarded.
  OS-Stormphrax adds a third engine: its first tune after a search rewrite
  gained about +14 STC / +18 LTC, and later tunes about +4 to +5 at LTC. That
  confirms the shape (the first tune after a big change pays most) but is
  again a whole-set tune (LMR, history and extensions included) and
  SPRT-selected. Shrunk and limited to eight margins: **+3 to +8 at LTC,
  central +5** (raised from B14's +4). Its 8-thread LTC tune that cost about
  19 Elo at STC is a second reason to tune each class at the condition it
  serves (O5, R24).
- **Why Fork.** Every one-sided loosening lost; SPSA moves all eight at once
  and can find a different shape. Batch 4's pruning items are substitutes
  and complements of these margins; tuning first makes their tests cleaner.
  Shallow margins transfer to datagen's depth (O1).
- **Compute.** The driver X18 (2-3 days, half charged here); 20k games (12.5
  stages, about 4 h); validation: design R or [0, 5] capped at 6 (about 4
  stages), then an LTC sign guard of 3 stages (about 3.75 h, UNVERIFIED stage
  time). About 9 GitHub-hours.
- **Rules (O2).** Parameters in c-units with c ≈ the 1-Elo half-width (O3:
  calibrate c from firing rates on a stats bench); gain from a 0.5-Elo loss
  budget; each update clamped to 0.5c; one update per stage; integers by
  random rounding; openings disjoint from every SPRT range. Report whether
  any parameter hit the clamp in ≥ 8 of 12 updates (step-limited, B14).
- **Originality.** SPSA is generic (Spall 1992). Every tuned value is a
  search constant: SPSA log plus the validation SPRT as its justification,
  and the originality screen before the commit.
- **Prediction.** The validation test accepts with an estimate of +3 to +8;
  the reasoning-set parameters (futility, null surplus, capture SEE) move
  further in c-units than the measured ones; LmpQuietAllowance moves down.
  Refuted if the validation is H0 or its estimate is under +3 nElo.
- **Kill.** As refuted; then the final pass shrinks to the LTC group.
- **Owner.** It reorders §5.6 (part of item 12 before batch 4) and needs a
  workflow change (a FORK_TUNE build input and per-pair options).

#### R15. History mechanics: linear bonus, TT-cutoff bonus, eval-fail-low bonus, joint continuation cap (OS 4.3 + OS-Stormphrax; verdict B14 +1 to +5 combined)

- **Mechanism.** Fork's bonus grows with depth squared, capped, under a
  gravity update; a quadratic bonus saturates entries after a few deep
  cutoffs (OS). Separately, Fork returns at a TT cutoff without rewarding the
  quiet TT move. OS-Stormphrax adds two concept-level candidates: a larger
  bonus when the static eval had failed low (the move refuted an expected
  loss), and one joint soft cap over a move's summed continuation terms
  instead of separate caps. Each is a single SPRT under design R; the
  bonus sizes come from head-to-head selection, never from another engine.
- **Range.** Four candidates instead of two, each with a small prior:
  **0 to +5, central +2.5** for the set (B14's +1 to +5 for two, plus
  OS-Stormphrax's passes, shrunk).
- **Why Fork.** Persistent, possibly saturated histories (A2 O3) are the
  amplifier behind the LMR-history loss (B14 §3.7).
- **Order.** The linear bonus changes every history scale: run it before the
  final retune, which then re-tunes the history weights (B14).
- **Prediction.** The linear bonus passes design R at +1 to +4; the
  TT-cutoff update at 0 to +2. Refuted by H0.
- **Kill.** H0 per item.
- **Originality.** Survey records are priors only; the bonus form is set by a
  head-to-head and screened.

#### R16. History ageing between searches: per-`go` scaling (S8a + OS-Stormphrax; X2 informs it)

- **Mechanism.** At each `go`, scale every history entry by s ∈ {1, 3/4,
  1/2}. The gravity update is an EMA with time constant H/b: about 830
  updates at d = 1 and 8 at d ≥ 10 (S8), so shallow-only entries persist
  across moves unchanged; Fork never decays between moves (A2 §1.1, PA d).
- **Evidence.** OS-Stormphrax found that keeping histories between searches
  pays (Fork already does) and that *more* ageing between searches paid a
  little more at STC and less at LTC. So mild ageing is a sound default
  question, not one that depends on X2 alone. Range **0 to +3 (central
  +1.5)**, raised from 0 to +2.
- **Test.** A head-to-head of s = 3/4 against s = 1/2 (2 stages), then
  design R against s = 1.
- **Prediction.** With s = 1/2 the in-game share of LMR sites at
  |score| ≥ 24,000 falls to within 2x of the bench's; the SPRT is 0 to +3.
- **Kill.** H0 at both values. X2 no longer gates the test; if X2 shows
  in-game magnitudes within 2x of bench, run it last among the history items.

#### R17. Improving as a measured mean shift (I7 + A2 O5 + SF 7.1.c + OS 4.5)

- **Mechanism.** Compute "improving" on `prune_eval` (what RFP uses; rising
  RFP compared raw evals). For LMP, split the existing quiet cutoff-index
  histogram by improving and set each class's allowance by LMP's own 1% rule;
  for RFP, offset the two classes by half the measured residual shift,
  mean-preserving.
- **Why Fork.** The flag's best-evidenced uses (LMP, LMR) were never tried;
  the one tried was a one-sided loosening on raw eval.
- **Cheapest experiment.** The LMP histogram split, one stats bench.
- **Prediction.** The non-improving 1% index is ≤ 0.75x the improving one;
  the LMP use passes design R at +1 to +3. Refuted if the indices differ by
  under 10%.
- **Kill.** Two H0s among the LMP and LMR uses → drop the flag (OS 4.5's
  rule).

#### R18. LMR for late and bad captures (SF 7.1.b + OS 4.6)

- **Mechanism.** Fork reduces only quiets. Reduce late captures from the
  bad-capture stage, ordered by take history, by less than quiets.
- **Why Fork.** Not on batch 4's list; take history (+4.5) supplies the
  signal.
- **Prediction.** Passes design R at +1 to +3; refuted by H0 at both
  amounts. **Kill:** H0, or an nps change below −1% with no gain.

#### R19. Network weights and history tables on huge pages (H7)

- **Mechanism.** The net is embedded in file-backed .rodata on 4 KB pages,
  which transparent huge pages do not back by default (UNVERIFIED for TCEC's
  kernel); copy the weights and the 2.4 MB of pair histories into a 2 MiB
  `madvise` block at startup.
- **Math.** About 8-12 L1-DTLB misses per node at about 7 cycles each, partly
  overlapped: 30-80 of 1,400 cycles, +1-3% locally, more at TCEC where TT
  probes sweep the L2 TLB (H7, from memory, UNVERIFIED).
- **Cheapest experiment.** `perf stat -e dTLB-load-misses` on bench; skip if
  under 2 per node.
- **Kill.** Under 1% cycles in both the 16 MB and 4 GB regimes.

#### R20. Round-once LMR + a centred, mean-preserving history term (S2 + A2 O2 + SF 7.1.d + PA §3.2 + idea 42; verdict B14)

- **Mechanism.** Compute the LMR reduction in 1/64 ply, add every adjustment
  in the same units, round once to plies for the child (idea 43's level 1
  only). Centre the history term on the LMR-candidate population and offset
  the base so the mean reduction over LMR sites is unchanged (the counters
  exist).
- **Math.** Over Fork's table the fractional parts are close to uniform, so
  a term of a ply/4 shifts the mean reduction by 0.25 ply (S2, computed):
  continuous in expectation. Today's `order_score / 24000` is exactly 0 for
  |score| < 24,000 and one ply beyond (PA c [V by PA]).
- **Mechanism of the −10.8 (B14 §3.7).** Composed: non-centred and asymmetric
  (most firings add a ply), amplified by never-decayed histories, made
  invisible by integer division; the per-quiet recomputation adds 1.5-3 Elo
  of cost at most.
- **Caveat.** The table stores whole plies (uint8), rounded at construction:
  bench identity of the 1/64 table must be proved, including the entries that
  sit one ply low (B14).
- **Speed.** A few adds per LMR site; carry the selector's stored score
  instead of recomputing it.
- **Prediction.** X2 shows E[order score | LMR site] < 0 by at least 10% of
  its range; the centred term passes design R at +2 to +5. Refuted if |mean|
  is under 5% of the range, or H0 at both slopes.
- **Kill.** The refactor is kept only if bench-identical and nps-neutral. If
  the centred term is H0, idea 42's continuation variant is not run (same
  mechanism).

#### R21. Pawn-structure history, gated (batch 4 + S5)

- **Gate.** SPRT only if the mean cutoff index improves by ≥ 1.5% relative
  (the metric that predicted 3 of 3 ordering features) and nps on a v3 build
  is within −1% (it adds a 768 KB table).
- **Prediction.** 0 to +2; **kill** at the gate.

#### R22. Aspiration half-width re-measured (I9 + A2 lower priority)

- **Mechanism.** 12 cp was measured on the bootstrap. Re-run Phase 3's bench
  method on S512ppr2 and bin by |previous score|.
- **Prediction.** p90 differs from 12 cp by more than 25%, and the >300 cp
  band's p90 is ≥ 2x the <100 band's; refuted if both are within 15%.
- **Kill.** As refuted. Otherwise the half-width becomes an SPSA parameter.

#### R23. Fused last-ply update and output kernel (H5 + A3 §1.7 item 6)

- **Mechanism.** At an evaluated node, compute the last ply's accumulator
  chunks, store them, and fold them into the SCReLU dot product while in
  registers: a load-bound loop and an ALU-bound loop share cycles.
- **Math.** 2.75 → 2.0 cycles per 16-lane chunk on AVX2 for the fused pair;
  +2 to +5% nps if half to a quarter of those 29% of node time is
  compute-bound (H5). B14: +1 to +4.
- **Cost.** One more SIMD kernel with a scalar reference and an equivalence
  test (simd.md): a maintenance cost to report (DESIGN §7).
- **Cheapest experiment.** A fork_micro kernel benchmark, an hour.
- **Kill.** Under 1% cycles in the engine A/B on v3.

#### R24. The final retune by scaling class (O10 + O5 + SF 7.2.6 + S7(4) + TC §2.B + I critique 1)

- **Mechanism.** After the last adoption and the removal round: an STC pass
  over the shallow margins, history and ordering weights, LMR (now sub-ply)
  and batch 4's adopted constants (p ≈ 18-24, 30-40k games); an LTC pass over
  the depth-scaling constants (singular margin per ply, its depth gates, IIR
  depth, the LMR divisor; p ≈ 5-6; 8-12k LTC games) only if that group
  plausibly holds ≥ 5 Elo; then one VLTC non-regression spot check (120+1.2,
  2 stages) of the result.
- **Parametrisation.** Margins as a few shapes (K·σ̂_d from X10, one K per
  technique) rather than offset, slope and depth cap each (I3); the margin
  multiplier m (M4) and the malus ratio (S8b) as SPSA dimensions; razoring
  and bad-capture futility, if kept, as dimensions initialised at
  "off-equivalent". **Never** time-management parameters (ratio 100 cannot
  see TCEC's allocation problem) and never the eval scale (a degenerate
  direction).
- **Math.** O's simulation: p = 24 at 40k games recovers about 9 of a T of
  15; after R14 the remaining T is what adoptions re-misplace plus untouched
  groups: +2 to +6 (O10); B14 +1 to +5. OS-Stormphrax's later LTC tunes
  (about +4 to +5 each, SPRT-selected) widen the top slightly: **+1 to +6,
  central +3**.
- **Compute.** About 22-26 GitHub-hours plus validation and the VLTC check.
- **Prediction.** The STC pass passes validation or caps above +3 nElo; LTC
  moves the extension constants toward more extension (O5); refuted if H0
  at STC (then skip the LTC pass).
- **Kill.** STC H0.

#### R25. Adaptive rounding of the output layer (M7; verdict B13 SOUND)

- **Mechanism.** Choose each output weight's rounding direction to minimise
  the squared output error over a position sample (Nagel et al., ICML 2020).
- **Math.** The output grid contributes sd 2.57 cp against the first layer's
  1.55; removing all quantization is worth at most 1.4-2.3 Elo.
- **Prediction.** Mean qloss 2.0 → ≤ 1.4 cp, p99 6.1 → ≤ 4.5; refuted if the
  cut is under 15%. Ships on non-regression only.
- **Also.** Retire idea 44's dedicated validation session (an expected 2e-5
  effect against a 1.2e-5 seed spread); keep `--qat` for any int8 design.

#### R26. Output experts chosen by frozen-feature probes (W2; verdict B13 PLAUSIBLE)

- **Mechanism.** The 8 phase-selected output heads are a hard-gated mixture
  of experts over one shared representation; the readout is linear given
  frozen features, so candidate gatings (phase × queens, imbalance class,
  pawn class, opposite castling; plus idea 46 rank 2's threat classes as
  candidate gates) are scored by ridge solves on CPU, then the winner is
  fine-tuned warm with each sub-bucket starting as its parent's copy.
- **Math.** A 16-bucket head reads one 2 KB row per evaluation: about 0.99-1.00
  nps; a second gating axis plausibly worth 2e-5 to 1.5e-4 of loss.
- **Prediction.** The probe finds a gating ≥ 3e-5 better than refit-phase on
  a disjoint 2 M-position set; fine-tuned FN +4 to +12. Refuted if every
  probe gain is under 2e-5, or FN < +3 after a probe gain ≥ 5e-5.
- **Kill.** As refuted.

#### R27. Result-weight arm, only if measured (T5 + M generational recursion + S2 N2 + SF λ schedule + C's L4 caution; ruling B13 §3.2)

- **Mechanism.** w* = Cov(p_deep − σ, p₂₀ₖ − σ) / Var(p₂₀ₖ − σ): the
  regression of the deep-play outcome residual on the shallow-play one,
  estimated from paired playouts (T5).
- **Why measure first.** Fork's results come from games in which half the
  moves are 4k-node moves (g3 settings `save_percent 50, unsaved_nodes 4000`,
  B13 [V]), and the bias is class-dependent: drawish endings want more result
  weight, rook endings less, islands are indifferent (C E2, B13). A global w
  is a compromise; a blind ladder cannot find it.
- **Gate.** X11's decisive-share gap: under 3 points → stop, 0.5 is recorded
  as measured; ≥ 8 points → the 4,000-position w* estimate (about 5 h on 2
  threads; SE ±0.15-0.2). Only w* ≤ 0.35 earns an arm in a later retrain, S
  re-matched, judged by FN then STC [0, 5]. If instead w* ≥ 0.65, the arm
  goes the other way, and R39's high-WDL fine-tune is the cheap form of it.
- **Kill.** FN ≤ 0 → keep 0.5.

#### R28. Double extensions and a depth-concave singular margin, at LTC only (S7 + S5 + SF 7.2.10 + batch 4)

- **Mechanism.** SE precision rises with depth (0.91 at d6, 0.97-0.98 at
  d7-12; A2 §5), so the margin per ply needed for 90% precision falls with
  depth. Fit the margin on deeper measurements (d 12-20), choose the double-
  extension margin as a higher precision quantile, and guard explosions by a
  per-line limit expressed as a fraction of root depth (Fork's own form, by
  ladder).
- **Math.** Extra nodes ≈ q × 0.306 × g if a fraction q of singular extensions
  become double: q = 0.1 is +5% nodes, about −7 Elo-equivalent at STC (S7).
  Expect STC ≤ 0, LTC ≥ 0.
- **Originality.** Do not adopt the absolute cap that matched another engine
  in batch 4's screen (DESIGN `DoubleExtensionsMax` row, per S7).
- **Prediction.** At d 16-20, 90% precision at ≤ 4 cp per ply; the concave
  margin passes LTC at +1 to +4. Refuted if precision does not rise above
  d 7-12's.
- **Kill.** LTC H0.

#### R29. Quiet history pruning (batch 4), after X2 and R16

- **Mechanism.** Skip late quiets with very negative history at low depth;
  use the reduced depth in its condition (OS §6). Thresholds from in-game
  distributions, not the bench.
- **Prediction.** 0 to +2 under design R. **Kill:** H0, or X2 refutes
  persistence and the bench-calibrated threshold already sits in the tail.

#### R30. Removal round as a factorial screen (ST5 + SF 7.2.5 combined guard + S9 routing; fixes B14 §2.ST5) [NOVEL for engine testing, UNVERIFIED]

- **Mechanism.** (0) Triage out every feature with P(value ≤ 0) under 1% on
  network-era data (SE, multi-cut, reply, follow, IIR and the tier-1 core):
  they go to SPSA, not removal. (1) The tier-2 block check (X9). (2) A
  factorial screen of the 8-12 low-prior switches: each shard plays one
  design row (m = 3-4 switches off) against the full engine, pentanomials fit
  by weighted least squares. (3) Remove a switch if its posterior mean value
  is ≤ +1 nElo. (4) One combined guard of all removals together.
- **Math.** Certifying a neutral feature at α = β = 0.05 on 3 nElo needs
  (3.29 × 245.67/3)² ≈ 72,600 pairs ≈ 91 stages per feature (ST5, B14 [C]).
  A k = 8, m = 3 design gives per-feature SE 4.1 nElo in 16 stages, 2.2-2.4x
  the efficiency of dedicated tests.
- **Fixes (B14).** No switch and its parent both as factors (multi-cut lives
  inside SE; check relief and lmr-in-check inside LMR); randomise the
  row-to-shard map every stage (runner CPUs differ); the guard on R-type
  bounds [−6, 0], β 0.2, cap 8 (the fixed 4-stage guard passes a −5 nElo set
  32% of the time).
- **Price the owner accepts.** The decision rule removes a true +3 nElo
  feature about 23% of the time.
- **Keep out of the round:** the switch `use_negative_extension` (off). Do
  not delete it before R40's cut-node retest (OS-Stormphrax §4).
- **Candidates for the screen.** lmr-in-check (bootstrap +4.2, never rechecked),
  SEE in quiescence (inconclusive), aspiration, mate distance pruning (never
  SPRTed), `UseTtEvalRefine` (never verified), the futile-node filter (a
  speed feature, CPU-dependent value), the forced-move stop, take history
  (+4.5), LMP, any small-estimate batch-4 adoption; check relief as the known
  control (−3.16 measured; the factorial should give about −5 ± 8 nElo).
- **Compute.** 22-32 STC stages (7-10 GitHub-hours) against about 260; the
  tooling (per-shard options, FORK_TUNE builds, WLS script) shares X18.
- **Prediction.** 2-4 switches come out ≤ +1 nElo; the combined guard passes;
  the control's sign is reproduced. Refuted if the factorial disagrees with
  dedicated estimates where both exist.
- **Kill.** A one-stage pilot (k = 4, check relief included, m = 2) with the
  control off by more than 2.5 SE → dedicated tests under design R (fixed 4
  stages each, decided by posterior).
- **Owner.** It replaces Quality control 6's per-feature [−3, 0] method and
  needs a workflow change.

#### R31. Eager child update before the TT read, runner and TCEC regime only (H6) [NOVEL for Fork, UNVERIFIED]

- **Mechanism.** A prefetch retires at once, a demand load does not; placing
  the child's accumulator update between the TT prefetch and the first read
  hides DRAM latency, at the cost of wasted updates at nodes that then cut.
- **Prediction.** Local −2% to +1% (C3's −0.8% is the precedent); runner and
  4 GB-hash +2 to +5%. Refuted if the runner A/B is under +1%.
- **Owner.** Adopting a change that is slower on the development machine is a
  doctrine change; only after X3 and X13.

#### R32. Depth-matched endgame-start slice (C5 + T7 + OS N6 + idea 11; verdict B13)

- **Mechanism.** Fork self-play from its own 8-16-piece positions with
  |label| 50-400 cp, played at 80k nodes with no split search and score
  adjudication raised or off (T7), mixed at about 1% of the next snapshot.
  The result half then carries deeper conversion and defence exactly where C
  measured biases growing with depth (one wing, ≤ 4 pawns, pure opposite
  bishops: −4.5 to −8 points at STC and LTC, z 5-16).
- **Cost.** About 10.5 h of the 10-thread machine, displacing about 100 M
  normal records (B13).
- **Gate.** A 4 M-position pilot (about 2.6 h): its one-wing residual against
  its own labels must sit nearer STC's −6 than the normal data's −2.25.
- **Prediction.** Equal-sample arms: the slice arm's category residuals
  shrink by ≥ 1/3; STC 0 to +4. Refuted if they move by under 1 point.
- **Owner.** A datagen setting change and a TCEC-relevance bet.

#### R33. Structure-class calibration scale on the eval (C3; verdict B13 PLAUSIBLE)

- **Mechanism.** A cached scale s[k] on the network output for a small
  structure-and-material class (phase, pawn count, one wing, pure opposite
  bishops, rook-only), fitted so each class's outcome curve matches the
  middlegame curve.
- **Math.** C's model gives about +2.6 Elo (range +1 to +5); C's own event
  studies (E6, null) and B13's note that STC → LTC growth is only about 1
  point argue for the low end: 0 to +3.
- **Owner.** Fitting a few dozen calibration constants on SPRT test games
  (a test-data use), or a dedicated 1.3 h local run.
- **Kill.** Offline variance cut under 30%, or H0 at STC with an LTC estimate
  ≤ 0.

#### R34. Correction tables: passive ranking first, then the best key at LTC (I5 + A2 O7 + SF 7.1.e + OS 4.4 + OS-Stormphrax)

- **Mechanism.** Re-run drift_measure.py's passive method on S512ppr2 for
  three keys: pawn, non-pawn per side including the king square (S-512 has no
  king buckets), and continuation (the last two arrival slots). Rank by
  decision accuracy at RFP and futility rows (X10) and tail-bin fitness, not
  summed error.
- **Why.** The pawn table was undecided at LTC on S512r2, before the links;
  the OS survey's record says tables pay as an ensemble, at LTC and with
  shared threads.
- **OS-Stormphrax partly contradicts "about 0 at STC".** Every one of its
  tables (pawn, non-pawn, continuation at several plies) passed at STC, table
  by table, with a gravity update; the OS survey's "about 0 at STC" rests
  mainly on one engine's many-tables test. Revised reading: the first tables
  pay at STC, marginal ones show only at LTC. For Fork the caveat is that the
  pawn links already carry much of the pawn table's target (I5's P7), so the
  non-pawn (king-inclusive) and continuation keys are the ones to expect at
  STC. Range raised from 0 to +3 to **0 to +4 (central +2)**. The test stays
  on the owner's LTC list; an STC H0 is now informative rather than expected.
- **Design notes (concept level).** Build tables without a side-to-move
  split (OS-Stormphrax simplified those away as non-regressions); use the
  gravity update; correction size as an LMR or RFP input is a later,
  separate test.
- **Drop.** Material, major and threat-keyed tables (removed elsewhere, or a
  key that changes almost every move).
- **Prediction.** The pawn key's passive fitness on S512ppr2 is ≥ 0.94
  (S512r2: 0.919), a king-inclusive non-pawn key ≤ 0.92; refuted if pawn ≤
  0.92. The best key passes LTC at +1 to +4.
- **Kill.** Every key's decision-accuracy gain under 2% of flipped decisions
  → shelve tables to Phase 6, where thread sharing is the real gain.

#### R35. Tail-risk-classed margins (I4; verdict B14 WEAK)

- **Mechanism.** A cheap risk bit (two pieces attacked by pawns; a minor
  attacking a major; the last move's eval swing) raises the margin on "hot"
  nodes and lowers it on "cold" ones at an unchanged prune count.
- **Weakness.** "RFP costs 20-35 Elo of wrong prunes" is inferred from one
  SPRT sliver (B14).
- **Gate.** X10 must show an indicator flagging ≤ 20% of candidates with ≥ 2x
  the tail rate; otherwise do not build.

#### R36. One new input family, chosen by the screen (C4 king-zone pawn links; M3a/C7 passers; B13 §3.5)

- **Candidates.** C4: own king square × pawns in a box around it, 896 inputs,
  about 0.95-0.97x nps (reasoned). M3a/C7: passed-pawn status on the links'
  pawn-change trigger, about 0.98-0.99x. B13's net expectations: C4 +1 (−5 to
  +6), passers +2 (−3 to +6).
- **Screen (all before any GPU).** X12 prices each design exactly; X7's
  deep-label residual by family (king-zone, pawn-status, threats) with X15's
  quiescence-resolved residual as the T/U separator; X14's gauntlet tells
  whether king-zone blind spots survived the links.
- **Rule.** Build at most one: the family with the best (deep-residual gain) /
  (X12 price). Kill all if none explains ≥ 0.5% of the deep-label residual
  variance (idea 46 rule 3's scale).
- **Prediction.** FN gain above 152·ln(1/r) + 5 at the measured ratio.
- **Kill.** Below that hurdle, or nps under 0.94 (C4) / 0.97 (passers).

#### R37. n-step and λ-return value targets, second line (M2 + W4; verdict B13 WEAK-PLAUSIBLE)

- **Mechanism.** Replace most of the result in the target by the stored
  score k plies later, or a λ-weighted average of later scores.
- **Correction.** M's martingale slope is 1.19, not 1.09 (B13). The gain is
  variance only under the martingale model, so small after cooldown and
  averaging; TD-k also cuts the weight on beyond-16-ply outcomes 4x, slowing
  exactly the long-horizon knowledge C flags.
- **Gate.** Only after R27's measurement, and only if the variogram
  recomputed with the training filter still shows ≥ 40% of the result
  residual absorbed within k plies.

#### R38. Idea 23 as a capped pilot with a game-based fitness (O9 + A2 O8.3 + W6 critique; or archive)

- **Mechanism.** Keep the harness; replace the label-and-sweep proxy by an
  antithetic fixed-node screen of the candidate's strength (local, 2
  threads), promote the top 5 to a one-stage GitHub screen, dose and SPRT the
  best one or two; 10 generations of 6, after R20 and R4 (so it searches
  beyond the known terms).
- **Math.** About 25 h local on 2 threads, about 0.75 M tokens, 10-15 stages;
  +0 to +4, P(at least one adoption) 25-40% (O9, guessed prior).
- **Kill.** The fitness ranks the two calibration rules wrongly (check relief
  positive; the tested LMR history form ≤ 0), or 0 of the top 5 pass.
- **Owner.** Run this capped pilot or archive idea 23 per its own spec.

#### R39. High-WDL final fine-tune of a finished candidate (OS-Stormphrax + OS N2 + SF λ schedule; weighed against B13 §3.2)

- **Mechanism.** After a retrain, branch a short low-LR continuation of the
  chosen candidate at a higher result weight (the value is a placeholder,
  set by measurement), re-match S, and judge the branch by FN against the
  candidate, then its own STC SPRT. The main arms of the retrain stay at
  w = 0.5, so the owner's control is untouched.
- **Evidence.** OS-Stormphrax: a constant high-WDL fine-tune of a finished
  net gained about +6 FN, +11 STC and +13 LTC; its three-stage recipe also
  ends on a short high-WDL stage. OS N2 records one engine's similar gain and
  the same family's −57 for a result-only fine-tune on recent data alone.
- **Against it, for Fork (B13 §3.2).** Fork's results come from games in
  which half the moves are 4k-node moves, and their bias is class-signed:
  more result weight helps drawish endings and hurts rook endings (C E2).
  OS-Stormphrax's results come from its own self-play at its own budgets, so
  its gain does not transfer one to one. Shrunk hard: **−3 to +6, central
  +1**.
- **Why it still earns a slot.** It is cheap (about 0.3 GPU-h and one FN
  stage) and leaves the control intact, so it tests the external finding on
  Fork's data without risking item 8a's decision.
- **Gate.** Skip it if X11 shows the shallow results over-convert (a
  decisive-share gap of ≥ 8 points with deep play less decisive): then more
  result weight imports the wrong bias.
- **Guards.** The endgame check, and C's rook-ending prediction made cheap:
  the branch's static eval against Syzygy WDL on 5-man KRPvKR and KPPvKP sets
  (minutes; B13). A branch that worsens the rook-ending set is not promoted.
- **Prediction.** FN +0 to +6 against its own parent; refuted if FN ≤ 0.
- **Kill.** FN ≤ 0, or the rook-ending guard fails.
- **Owner.** A target change on a branch (§7 item 10).

#### R40. Negative extension at expected cut nodes only, sub-ply, at LTC (OS-Stormphrax + A2 O6 + S critique 7)

- **Mechanism.** Fork's negative extension fired at every non-PV node whose TT
  score was ≥ β when the singular test was neither singular nor a multi-cut,
  and cut a whole ply from the move carrying the node: −8.73 ± 4.98, H0 (A2
  §2.2). With batch 4's expected node types and round-once arithmetic (R20),
  apply it only at expected cut nodes, by a sub-ply amount.
- **Evidence.** OS-Stormphrax's first gain from this idea was the cut-node
  form; a TT-score-at-or-above-β form followed. A2 O6 and the search
  specialist already argued the gated, fractional form is a different
  change, not a retest.
- **Why LTC.** Extensions are on Fork's "straight to LTC" list.
- **Prediction.** Passes LTC under design R at +1 to +4; never near the
  ungated form's −8. Refuted if H0 at both amounts (½ and ¼ ply).
- **Kill.** H0 at both amounts; then `use_negative_extension` may go in the
  removal round.
- **Owner.** Confirm that the gated, sub-ply form counts as a new idea rather
  than a retest of a rejected one (§7 item 26).

#### R41. Eval-change adjustment after a reduction (OS-Stormphrax + OS item 9 hindsight + S6c)

- **Mechanism.** After a heavily reduced search, extend the move by a unit
  when the child's static eval improved markedly over the parent's, and
  reduce one more when it collapsed. The eval change is information the
  reduction ignored (low-ρ class, S M3).
- **Evidence.** OS-Stormphrax: the extension form gained modestly at STC and
  much more at LTC; the reduction form was smaller, also larger at LTC.
  Close to the OS survey's "hindsight" item. Shrunk: **0 to +5, central +2,
  mostly at LTC**.
- **Speed.** Both evals are already in the frames; one comparison.
- **Constants.** The improvement and collapse thresholds come from X10's
  ledger or head-to-head selection, never from another engine.
- **Test.** An extension: straight to LTC per Fork's list (about 5 LTC
  stages); the reduction half at STC.
- **Prediction.** The extension form passes LTC at +1 to +5 and is about
  neutral at STC; refuted if LTC is H0 at both thresholds.
- **Kill.** As refuted.

### 2.4 The entries, enablers

Only what the summary table does not already say.

- **X1 counters.** The quiescence share of evaluations decides whether any
  eval-avoidance idea has a ceiling (A3 §1.2; H predicts 0.75-0.85
  evaluations per node, which would rule eval skipping out; refuted if under
  0.6).
- **X2 history magnitudes.** Prediction (B14 §3.7): the in-game share of LMR
  sites at |order score| ≥ 24,000 is ≥ 5x the bench's at moves 30-60, and
  ≥ 85% of the term's firings were on the "reduce more" side. Within 2x of
  bench → attribute the −10.8 to cost and measure the branch's nps.
- **X3 runner A/B.** Predictions: S512ppr2 against S512r2-with-zero-links at
  0.86-0.89 on runners (H2); S512+X's runner ratio below 0.80 would move it
  toward the speed line (A1 §4.2). Most shards ran on EPYC 7763 (B14 [V], DL);
  three concurrent hot sets of about 20 MB plausibly exceed its L3 (from
  memory, UNVERIFIED), so A3's "16 MB Hash L3-resident on every runner" is
  likely wrong for most shards, but only this job settles it.
- **X4 anneal attribution.** Judge by Elo, not loss (the 9.3 Elo per 1e-4 rate
  is computed from the same pair, so it is circular; B13): ≥ +12 FN means the
  anneal explains most of S512ppr2's +20.1, ≤ +5 means data and labels do.
  The soup control: averaging the two warm seeds should beat the worse seed;
  the scratch seeds' average should be far worse.
- **X5 design R.** sprt_merge.py already takes `--alpha/--beta`; sprt_run.sh
  needs a cap argument, the stage-2 futility check and (if chosen) the cap
  rule, about 20 lines (ST1). Replayed on nine logged tests it reaches the
  same nine verdicts in 30 stages instead of 59 (ST1). Adopt a limit of a few tries per idea (Fork's own rule: every retry
  spends α again; survey B1 reports a similar fishtest guideline,
  UNVERIFIED).
- **X6 node-share fit.** About 2,000 positions from g3 games, node-limited
  searches at about 2 M nodes, per-iteration share, stability and score
  change; logistic fit of "best move changes within 2 iterations". It sets the
  curve shape and predicts R8's Elo before any game.
- **X7 deep relabel.** One stratified sample of held-out positions (equal
  games per labeller generation, the slice, g3f and g3g held-out games),
  relabelled at about 1 M (or 500k) nodes by the default. Outputs: (a) a gold
  set for data-mix and recipe decisions *within one architecture* (never
  across architectures: it is still a static loss); (b) 20k-node label noise;
  (c) category shifts deep − shallow (C2's predictions: drawish endings ≥ 10
  cp closer to 0; refuted if both C2 shifts are under 5 cp); (d) the residual
  of frozen S512ppr2 by input family. Sharper kill than T3's (B13): gold-loss
  *differences* must order the two known promotions by size. Needs a UCI
  driver or relabel mode (UNVERIFIED whether one exists).
- **X8 throttle.** The throttle burns ALU cycles behind a compiler barrier;
  on memory-bound runners it may play at 0.55-0.60x instead of 0.50x and bias R
  low (B14). Each shard benches base and test before its games and records the
  per-CPU ratio; R is fitted on the realised ratio. Predictions: R_STC 85-125
  per doubling (refuted outside 60-150), R_LTC/R_STC ≥ 0.8 (refuted under
  0.6), the 8-net mean residual |c| < 8 Elo (else fixed-node screens need a
  depth correction). Optional 0.85x throttle point (2-3 stages) checks
  linearity where the gate decides.
- **X9 block check.** Prediction (ST2): tier 2 on S512ppr2 is worth +80 to
  +115 nElo; under +60 means features faded or interact.
- **X10 ledger.** Gives P(wrong | g, d) per heuristic, not the Elo cost of a
  wrong prune, so it fixes shape and ranges, never the level (B14). Replay
  Fork's own games with TT and histories carried (avoids the fresh-state bias
  of A2 §6). Its 1/32 deterministic counterfactual sampling is a valid
  Horvitz-Thompson estimator.
- **X12 zero-row build.** Prediction: one extra full-width int16 row costs
  50-80 cycles per perspective locally and 15-30% more on runners; the linear
  model predicts S512+PP's 0.895 within ±0.02 (H3).
- **X13 cycles rule.** B14 corrects H2's "+9 to +22 Elo thrown away" to +2 to
  +6 (P-2 and P-3 were adopted anyway). Still worth building for R9, R19, R23.
- **X14 gauntlet.** C's king-zone lifts (2.5-4.8x) rest on 4-7 positions per
  threshold and predate the links; a gauntlet with S512ppr2 is the cheapest
  check, and the owner has it open anyway. Positions are selected without
  the opponents' evaluations (no PGN eval comments) unless the owner rules
  otherwise, and no such selection is ever committed or trained on.
- **X18 SPSA driver.** Missing today: a FORK_TUNE build input, micro-match
  looping in the shard, per-pair θ± option strings, a gradient merge, a title
  format the ledger attributes, tests (B14 [V]). 2-3 days.

---

## 3. Novel ideas and their status after the skeptics

"NOVEL" here means not found in the KB or the surveys by the proposing agent;
none is claimed as a world first.

| Idea | Agent | Skeptic verdict | Status in this plan |
|---|---|---|---|
| Searched validation loss (QS / depth-2 value) to rank architectures | M1 | PLAUSIBLE (B13), restate on played nets over a fresh 200k set | X15, before any architecture decision |
| n-step (TD-k) score targets | M2 | WEAK-PLAUSIBLE; slope 1.19 not 1.09; Elo path via A1 B1 fails | R37, second line after R27 |
| Passed-pawn inputs on the pawn trigger + residual-interaction screen | M3 | PLAUSIBLE-WEAK; β pricing is noise | candidate in R36's screen |
| Gold-label validation set | T3 | PLAUSIBLE; not an architecture yardstick; kill test biased to pass | part of X7, sharper kill |
| Result weight from paired playouts (w* regression) | T5 | PLAUSIBLE with three fixes (independent replicates, split-search shallow arm, realistic SE) | X11 → R27 |
| Equal-marginal-error condition; concave RFP | S3, S4 | WEAK-PLAUSIBLE (σ_d read from tail averages); S4 PLAUSIBLE as a measurement | X10; shapes as SPSA parametrisation in R24 |
| Two-depth scaling classifier | S9 | PLAUSIBLE | X16 |
| Firing-rate calibration of SPSA perturbations | O3 | PLAUSIBLE | inside R14 |
| Antithetic screening | O7 | WEAK for selectivity (asymmetric harm screens "be careful" positive) | symmetric strengths only (history weights, TM slope, correction weights) |
| Node-odds screens for networks | ST4 | PLAUSIBLE; fastchess per-engine `nodes=` via TEST_OPTS UNVERIFIED | use for a new input family's screen at the shard and TCEC ratios |
| Factorial removal round | ST5 | PLAUSIBLE with four fixes | R30 |
| Eager child update before the TT read | H6 | WEAK-PLAUSIBLE | R31, after X3 and X13 |
| Blind-spot suite verified by Fork's deep search | C1 | SOUND (tooling) | X14 |
| Horizon study by chess category | C2 | SOUND | part of X7 |
| King-zone pawn links | C4 | PLAUSIBLE-WEAK | candidate in R36 |
| Pawn-status planes | C7 | WEAK (islands effect is a position type, B13 [V]) | passer plane only, inside R36's screen |
| Decision ledger | I1 | PLAUSIBLE | X10 |
| Count-based correction gain | I5 | untested | an arm inside R34's passive ranking |
| Margin credit for tail-reducing nets | I6 | WEAK | dropped from idea 46's accounting unless X10 shows S512+X's tail mass ≥ 20% lower |
| Value-of-computation TM; quantile horizon | W1 | (a) = node share, PLAUSIBLE; (b) WEAK, an upper bound, Phase 5 | (a) in R8; (b) Phase 5 at a ratio-600 control |
| Output experts by frozen probes | W2 | PLAUSIBLE | R26 |
| λ-returns, inverse-variance w(p) | W4 | WEAK-PLAUSIBLE (ignores the class-signed outcome bias) | R37 |
| Sequential halving for the search queue | W6 | PLAUSIBLE, not as the standard (dependencies, stacking) | only if a genuine batch of independent arms exists |
| Accumulator policy ordering at IIR nodes | W8 | WEAK, a plan change | parked (idea 16 stays after Phase 8) |
| Narrow threat side accumulator | SF 7.1.k | WEAK (old speed rate, no discovery cost, additive lane) | parked with H8 |
| History-persistence diagnosis | A2 O3 | SOUND as a measurement | X2 |
| TCEC-shaped TM control (ratio 600) | A2 O8.1 | Phase 5 | Phase 5 |
| Judge's addition: align quiet-machine A/Bs with part seals | this file | not reviewed | §6: the g3g seal on Sunday is a free quiet window before g3h starts |

---

## 4. The removal list

### 4.1 §5.6 items, planned experiments and ideas to drop, shrink or never build

| Item | Action | Reason |
|---|---|---|
| §5.6 item 4 as designed (0.85x time odds, ~4,000 games) | **replace** with X8 (throttled 0.5x, 2 STC + 1 LTC, in-situ ratios) | R ± 27 against ± 9; time odds are biased by fixed per-move latency (PA §1.1g) |
| Item 5, batch 4 as nine ladders + [0, 3] SPRTs | **redesign**: design R + head-to-head constants; order cut-node LMR, NMP at cut nodes, improving in LMP, upcoming repetition (after idea 31), structure history (gated); PV-trace and double extensions at LTC; history skip after X2 | ~140 stages for ~0.9 expected passes (S5, A3 §2.6) |
| Batch 4: razoring, bad-capture futility | **demote** to SPSA dimensions or idle filler | razoring adds 1.7% nodes at its placeholders (B14 [V], DESIGN row); bad-capture futility overlaps SEE pruning and node futility |
| Batch 4: history malus balance | **make it an SPSA parameter** (R24), no SPRT | it moves where history's zero is (S8 math); idea 28's own plan |
| Item 6, idea 46: distillation from S512+X with auxiliary threat targets | **drop** | REFUTED (B13 §3.6) |
| Item 6, idea 46: residual study against training labels | **redo against deep labels** (X7) with QS-resolved residuals (X15) | against 20k labels it measures fit to the labeller, not knowledge (C2) |
| Item 6, idea 46: attack-map pricing | **fold into X12** | priced in the engine, in context |
| Idea 46 ranks 3-5 (threat inputs), 7 (threat-keyed correction), 8 (stand-pat check) | **park** 3-5 (about −8 expected); **drop** 7 (key churn); rank 8 only inside R35 if X10 supports it | B13 §3.5, I5, I4 |
| Item 8 as numbered (idea 42, continuation histories in LMR) | **fold into R20** as its variant; run only if the centred term passes; measure by design R, not by the label-and-sweep proxy | same mechanism; the proxy favours "off" (A2 §6) |
| Item 9, the re-validation queue | **shrink**: B-4 → R13's depth ≥ 1 variant; drop B-3 and the root fail-high fix; keep-exact only at a TCEC-scaled hash (X23), otherwise drop | posterior means ≈ 0 or below (ST8); no pending root fail high at a soft stop (R8) |
| Item 10, fractional depth (idea 43) | **shrink** to round-once LMR (R20); level 2 out of Phase 4 (LTC-only if ever) | the surveyed family found level 2 ≈ 0 (OS §6) |
| Item 11, the full re-validation as per-feature [−3, 0] SPRTs | **replace** with R30 | ~260 stages that cannot decide neutral removals |
| Item 12, SPSA "STC then LTC" over everything | **split** into R14 now and R24 at the end, by scaling class; no TM, no S | tunes every parameter once at the condition that matters (O5) |
| Item 13, idea 23's long run on the proxy | **replace** with R38's capped pilot after R20/R4, or archive (owner) | the proxy predicted no gain and ranked inversely (ρ ≈ −0.3) |
| Item 14: S512cl's speed work | **drop** | cannot reach 0.90x by arithmetic (H3); DRAM-bound at TCEC (H9) |
| Item 14: idea 40 L1 as a separate cached pawn-and-king net | **drop**; pawn knowledge enters the main body as inputs (R36) | an additive side net cannot represent the piece dependence measured in M (d): 0.88 of the links' spread moves when a piece leaves |
| Idea 40 L2 pawn drift table | **drop** | undecided at LTC; overlaps the links (A2 O7, C, both surveys) |
| Idea 40 L3 root planner | **defer** past Phase 4; keep only the near-tie gate measurement | no evidence of missed long plans (C E4) |
| Idea 40 L4 teaching targets | **handled by X11/R27** | a higher result weight imports shallow-play bias (C) |
| Idea 40 L5 proof set | **becomes X14's suite** | C1 |
| Item 14: further correction tables (material, major, threat) | **drop** those three; non-pawn (king-inclusive) and continuation via R34; pawn stays off unless P7 fails | removed elsewhere; key churn |
| Item 14: QAT (idea 44) validation session | **retire**; keep `--qat` for int8 designs; R25 instead | expected effect at the seed-spread scale (M7, B13) |
| S512+X and AF-S as LTC candidates | **drop** | R_LTC ≈ R_STC (A3 §1.4) |
| Idea 45 part 3 (conversion without tables) | **drop**; extend part 2 (X19) | tables are present in every SPRT and at TCEC (C6) |
| Idea 47.1 (relabel generation 1 first) | **drop**; R3 asks the question that matters (g2s1) | generation 1 is not in g3s2 (T4) |
| Idea 47.2 (quiet filter) | **shrink** to its offline count, low priority | no ablation evidence; no overfitting to fix (T) |
| Idea 34 (RfpMargin 40) | **retire** as a standalone test | one point on R14's axis |
| Ideas 10, 11 | **replaced** by R33/R32; idea 11's boundary moves to 8-16 pieces | C |
| Idea 21 (BOLT) | **drop** from Phase 4 | needs tools TCEC's build host is unlikely to have; PGO takes most of the gain (H) |
| Idea 36 (SIMD pick) | **close** | E2 +1.0%, absorbed by C4 |
| Ideas 9, 37 (layout) | **only under X13's 1% rule** | every candidate was under 3% |
| Fifty-move eval scaling | **stays closed** | the search sees the fifty-move draw 10-30 plies ahead; at most about +0.7 Elo (C E5) |
| A dual net, a PSQT path, king buckets, a multi-layer head, fifty-move inputs, width changes, distillation, contempt, a first-move-out-of-book bonus, MCTS, SMP in Phase 4, the accumulator policy head, the 25% save-share arm, cross-entropy before conversion data exists, a new S (keep 92 unless the free fit leaves 88-96), M4's separate ladder (fold m into SPSA), I2 as a gate for SPSA (filler only) | **never build in Phase 4** | each by its B13/B14 verdict or survey record |
| LTC confirmations of STC passes outside the LTC list | **keep the 2026-11-06 policy** | one LTC stage resolves about ±17 nElo (ST) |

### 4.2 Existing search features: removal candidates for the re-validation

- **In the factorial screen (R30):** lmr-in-check (bootstrap +4.21 ± 2.89,
  never rechecked on a net), SEE in quiescence (+9.5 ± 7.3, inconclusive),
  aspiration (12 cp, bootstrap-measured), mate distance pruning (never
  SPRTed), `UseTtEvalRefine` (shipped by owner exception, +14.6 ± 17.8 at
  1,000 games, never verified), the futile-node quiet filter (a speed
  feature, +12.7% nps; its value is CPU-dependent, hence row randomisation),
  the forced-move stop (+0.96 ± 3.54), take history (+4.5 ± 3.0), LMP, any
  batch-4 adoption with a small estimate; check relief as the known control.
- **Triaged out (to SPSA, not removal):** SE, multi-cut, reply, follow, IIR,
  and the tier-1 core (PVS, TT, QS, NMP, LMR, RFP, futility, SEE pruning,
  Syzygy).
- **Horizon patches** (check relief, lmr-in-check, SEE in quiescence,
  aspiration) are expected to *lose* value with depth (S9): a "keep" verdict
  at STC is conservative for TCEC. If X16 flags one with no rate effect and
  the STC screen keeps it narrowly, one 2-stage LTC estimate is the cheapest
  tie-breaker.

### 4.3 How the removal round should run

1. After the last feature adoption, before the final retune (removing first
   lets the retune re-optimise the margins for the remaining set; O §3.4).
2. Step 0 is X9 (the tier-2 block check, 2 stages), run early as filler.
3. A one-stage pilot (k = 4, check relief included as the control, m = 2)
   validates the tooling.
4. The screen: k = 8-12 switches, m = 3-4 off per row, 16-24 stages, the
   row-to-shard map randomised per stage (seeded, logged), FORK_TUNE builds on
   both sides, no parent-child factor pairs.
5. Decide: remove if the posterior mean is ≤ +1 nElo (prior from ST2's
   fitted model).
6. The combined guard: all removals together against the full engine, design
   R bounds [−6, 0], β 0.2, cap 8.
7. Fold the surviving switches into plain code only after the guard passes
   (Quality control 6).

---

## 5. Item 8: the next retrain

### 5.1 Numbering

The owner calls the next retrain "item 8", while §5.6 numbers idea 42
(continuation histories in LMR) as item 8. Proposal: **"item 8" becomes the
retrain loop**, this run is **item 8a** (g3s3), later retrains are 8b, 8c;
idea 42 loses its own number and becomes R20's variant (it runs only if the
centred history term passes). The replacement order table in §6 uses this
numbering. If the owner prefers to keep §5.6's numbers, call the retrains 7b,
7c (as T and B13 did).

### 5.2 Data

- **g3s3** = g3s2's 81 training files + g3f's training shards + g3g's
  training shards (held-out games aside for validation), read with
  `--interleave`.
- **g3g**: target 366,424,464 records, about 199 M saved and about 135 M kept
  (the target counts unsaved records too; B13 [V], T §2.5); expected to seal
  about 2:20 PM on 2026-11-08 (HANDOFF §4; UNVERIFIED rate assumption).
- **New data:** about 158 M kept positions against g3s2's about 848 M: +19%,
  0.25 doublings; mean labeller +20 chain Elo (T §2.5).
- **The Syzygy slice stays** (keep it in every snapshot; T critique 5).
- **Validation g3s3-val:** the existing interleaving tool over every source
  plus 60 held-out games from each of g3f and g3g. The per-superbatch 20k
  prefix stays for monitoring only (validation runs at batch 1, so raising it
  costs time per superbatch; B13 [V]). Final and averaged candidates are
  scored **offline on all kept positions** (about 80k) with `--superbatches 0`.
- **Fixed settings:** S = 92 unless `fit_scale.py` on 2 M positions of the
  g3s3 mix lands outside 88-96 (B13 measured about 89 on the g3s2 mix with the
  training filter); result weight 0.5.

### 5.3 Arms (one Kaggle session on T4 x2; all warm from S512ppr2's float weights)

| Arm | What | Seed | GPU-h | Purpose |
|---|---|---|---|---|
| **R1, R2: the control** | **the owner's standard recipe unchanged**: LR 1e-4, tenfold drop after superbatch 180, 360 superbatches, best checkpoint by validation loss. Script change only: keep R1's superbatch-180 checkpoint (with optimiser state) and the float weights of superbatches 331-360 | 1, 2 | 4.3 | the decision baseline; yields R1-avg (mean of 331-360) for free |
| **CD: cooldown branch** | `--resume` R1's superbatch-180 checkpoint; zero-code staircase: 20 superbatches at 1e-5, 15 at 3e-6, 15 at 1e-6 (constant-LR resumes with a huge `--lr-step`); average the last 15 | as R1 | 0.3 | removes the residual noise floor (expect −1e-5 to −2.5e-5 against R1's 1e-5 window mean) at a sixth of the tail's GPU |
| **D1: anneal only** | S512ppr2 at 1e-5 for 60 superbatches on g3s3, no 1e-4 phase | 1 | 0.36 | information: does a warm retrain need its stable phase? If D1 matches R1, future retrains cost about 20 minutes |
| **B: recency (conditional)** | as R1, every other g2s1 file dropped, g3g listed twice | 1 | 2.15 | runs only if X7's gold set exists by session time; otherwise dropped |
| X4 (optional here) | the anneal attribution, if not already run | 1 | 0.24 | §2.4 |
| HW: high-WDL branch (optional, R39) | after the candidate is chosen: a short low-LR continuation at a higher result weight, S re-matched; FN against the candidate only after 8a's SPRT; promotes only through its own STC SPRT | 1 | ~0.3 | tests OS-Stormphrax's high-WDL fine-tune on Fork's data without touching the control; skipped if X11 shows the shallow results over-convert |

Total **5.0 GPU-h without B, 7.1 with B** (plus 0.24 for X4); wall time about
3-4.5 h (GPU 0: R1 then B; GPU 1: R2, D1, then CD once R1 passes superbatch
180). Whether T4 x2 counts once against the weekly quota is UNVERIFIED.

### 5.4 Schedule

- **Saturday 2026-11-07 to Sunday morning:** X4 on Kaggle (anneal
  attribution, 0.24-0.5 GPU-h) and its FN stage on GitHub; the two-seed soup
  scored on CPU; X7 (deep relabel, about 2 h on 2 threads) if a relabel driver
  exists, as a `measure` job; X11 (decisive-share pilot) after it; prepare the
  Kaggle script changes (checkpoint keeping, the staircase resumes, offline
  scoring).
- **Sunday 2026-11-08, about 2:20 PM:** g3g reaches its target; stop and seal
  through `cc_stop.py` or the Control Center (never `jobctl stop
  g3g-chain`); verify; commit the manifest (bench unchanged). Upload g3f
  (0.29 GB) and g3g (1.69 GB) as Kaggle datasets (upload time UNVERIFIED) and
  check hashes in a CPU session. Run `fit_scale.py` on the g3s3 mix. Build
  g3s3-val.
- **Sunday evening:** the Kaggle session (3-4.5 h wall).
- **Monday 2026-11-09:** conversion, parity, netcheck, scale match against
  S512ppr2, the endgame check, qloss, then the STC SPRT [0, 5] (1-3 stages,
  20-60 minutes). Report before any promotion (standing rule).

### 5.5 Decision rule (declared before the run)

1. **Validity.** Every warm arm reproduces S512ppr2's superbatch-0 loss on
   g3s3-val.
2. **Candidate.** Compare R-best (the owner's rule), R1-avg and CD-avg on all
   of g3s3-val's kept positions, offline; never by best-of-N. Take the lowest;
   if an averaged candidate is within 1e-5 of R-best, prefer the average (it
   carries no selection bias); differences under 1e-5 are ties, and a tie goes
   to R-best (the owner's standard). If the chosen candidate is not R-best,
   report both to the owner before the SPRT.
3. **Gates as today:** parity chain within S-512's limits, netcheck, S matched
   to S512ppr2's mean |eval|, the endgame check (S512ppr2 misjudges 8 of 900;
   proposed target ≤ 15, the owner sets it), plus X19's 4-5-man classes as
   report-only.
4. **Kill before the SPRT:** the candidate's full-set loss not at least 2e-5
   below S512ppr2's → no SPRT; wait for g3h.
5. **STC SPRT [0, 5] against S512ppr2.**
6. **Information, logged, nothing ships on it:** D1 against R1's 1e-5-phase
   window mean (within 3e-5 with an equal endgame check → propose the short
   recipe; worse by > 5e-5 → the stable phase carries learning); CD-avg
   against R1's window mean (confirms or refutes the ~2e-5 floor); B against
   R1 on the gold set (B better by ≥ 2e-5 → 8b adopts half-weight g2s1; else
   uniform stays and idea 47.1 is dropped for Phase 4).

### 5.6 Prediction

**+4 to +12 Elo at STC (central +7), the same at LTC** (same architecture and
speed; eval gains carry). If X4 shows the anneal explained ≥ +12 of
S512ppr2's +20.1, move the central to +5. **Refuted** if H0 or a final
estimate under +3: then the data-and-label model overstates this scale, and
the next retrain waits for at least 150 M new kept positions from a promoted
labeller.

### 5.7 What item 8a must not include yet

- No change to the result weight, no λ schedule, no WDL-heavier end, no TD-k
  or λ-return targets, no cross-entropy (each changes the target, needs its
  own S rematch and FN/STC, and the bias measurement has not run). One
  exception: if X11 and the full w* estimate finish before the session with
  w* ≤ 0.35 at SE ≤ 0.1, an arm at w* replaces B. The optional HW branch
  (R39) is not an exception: it branches from the finished candidate, never
  replaces an arm, and ships only through its own SPRT.
- No new S unless the free fit leaves 88-96.
- No architecture change (new inputs, buckets, heads, width).
- No endgame-start slice (R32 needs its pilot), no 2026-09-book data (not yet
  generated), no relabelled data, no 25% save-share data.
- No recency arm without the gold set.
- No distillation, no QAT, no scratch arm.
- Never drop the Syzygy slice; never warm-start at 1e-3.

### 5.8 After item 8a

- If promoted, the running part (g3h, started at g3g's seal by S512ppr2) ends
  at a game boundary and the next part starts from a fresh PGO build of the new
  default (labeller policy), from the 2026-09 book if R1 is approved.
- 8b when the new-label share reaches about 15-20% (about 150 M kept from a
  promoted labeller), with D1's verdict deciding whether 8b uses the short
  recipe, B's verdict deciding the mix, and R27's arm if earned.

---

## 6. The proposed order for the rest of Phase 4

This replaces §5.6's order table. Items 1-3 and 7 of §5.6 are done. Lanes run
in parallel: **G** GitHub (one run at a time), **K** Kaggle, **L** local CPU
(shared with data generation: one heavy job at a time, about 2 threads free;
quiet-machine A/Bs need data generation paused), **E** engineering (agent
days, which also gate the other lanes). Estimates are UNVERIFIED until run.
"Stages" are STC stages of 1,600 games (about 18.5 minutes); an LTC stage
(about 75 minutes, UNVERIFIED) counts as 4.

| # | Step | Lane | Why here | Depends on | Estimate |
|---|---|---|---|---|---|
| 1 | Cheap measurements: X1 counters, X2 history magnitudes + the LMR-history branch's nps, X6 node-share fit, X10's RFP/futility rows (in that order, one at a time) | L | each gates several later items; all are read-only | none | ~6-10 CPU-h at low priority over 2 days |
| 2 | X5 (design R tooling) and the owner's decisions on the SPRT design, TM and SPSA | E | everything on G after it uses design R | owner | 0.5 eng day |
| 3 | X4 anneal attribution + soup; its FN stage | K, G | sets item 8a's forecast and the datagen-vs-training priority | none | 0.5 GPU-h; 1 stage |
| 4 | X9 tier-2 block check | G | G is idle now; also R30's step 0 | a branch commit | 2 stages |
| 5 | X7 deep relabel (gold set, label noise, category shifts, residual by family), then X11 decisive-share pilot | L | gates R3 in item 8a, R27, R36 | a relabel driver (0.5 eng day; UNVERIFIED whether one exists) | ~2 h + 1-1.5 h on 2 threads |
| 6 | X12 throttle and zero-row build; X3 runner A/B workflow | E, G | X8 needs the throttle; X3 needs a workflow; both price the speed gate | owner (workflow) | 1.5-2.5 eng days; ~30 min of a runner |
| 7 | **The g3g seal (Sunday ~2:20 PM) as a quiet window**: R11's local build matrix, C1 for datagen, X12's zero-row measurements, before g3h starts | L (quiet) | data generation stops anyway at the seal; free quiet hours | step 6's build | 2-4 quiet hours; g3h starts after |
| 8 | **Item 8a**: uploads, Kaggle session, gates, STC SPRT; then the optional HW branch (R39) | K, G | the largest sure Elo; Kaggle-bound | g3g sealed; step 3, optionally step 5 | 5-7 GPU-h (+0.3 for HW); 1-3 stages (Monday), +1 FN stage for HW |
| 9 | X8 throttled speed-to-Elo (2 STC + 1 LTC, in-situ ratios) | G | resets the gate price; settles the LTC-candidate bucket | step 6 | ~6 stage-equivalents (~2 h) |
| 10 | **R8 node-share TM + stability**: code, 2-value head-to-head, design R at STC, LTC | E, G | best Elo per GitHub stage among search items; every later LTC test and the gauntlet should play with it | owner; X6 AUC ≥ 0.70 | 2 eng days; ~22 stage-equivalents (~7 h) |
| 11 | X18 SPSA driver, then **R14 early SPSA** + validation + LTC sign guard | E, G | margins never refit; cleaner batch-4 tests after it | owner (workflow); X10 for ranges | 2-3 eng days; ~29 stage-equivalents (~9 h) |
| 12 | Search features under design R, in this order: R7 (fail-firm, no dependency) → R20 (round-once + centred history, after X2) → R4 (cut-node; TT-PV at LTC) → R6 (NMP at cut nodes; IIR by type) → R12 (after idea 31) → R16 → R15 (history mechanics) → R17 (improving, LMP first) → R10 → R18 → R13 → R29 (if X2 confirms) → R21 (gated) → R22; at LTC: R41 (eval-change extension), R40 (cut-node negative extension, after R20 and node types), R28 after its deep precision measurement | E, G | the tier-2 remainder, ordered by Elo per effort and dependency; interleave with steps 10-11 while their code is written | X5; X2 for R20 and R29 | ~7 eng days; ~70 stages + ~20 LTC stages (~40 h) |
| 13 | **Item 8b** (and 8c if the cadence allows) | K, G | the loop: each adoption and promotion starts a part labelled by the new default | ≥ 150 M new kept from a promoted labeller | ~5 GPU-h and 1-3 stages each |
| 14 | Network screen: X15 searched loss, R26's probe, R36's family screen (X7 residuals + X12 prices); X14 gauntlet of S512ppr2; then at most one family (or R26's experts) warm-trained, node-odds or FN screen, STC | L, K, G | capacity at the speed price, decided before any GPU time | steps 5, 6, 7 | ~3-10 eng days; 1-6 GPU-h; 2-4 stages + the gauntlet run |
| 15 | Speed sprint 3 at quiet windows (part seals): X13's cycles rule, R9, R19, R23; R31 only on runner evidence | E, L (quiet) | +1.5 Elo per 1% at zero GitHub cost; more data per CPU-hour | X1, X3, X13 | ~4-6 eng days; ~4-6 quiet hours |
| 16 | R34 correction tables: passive ranking (local), then the best key at LTC | L, G | measured now, SPRT after R14 as the owner deferred | step 11 | 2-4 eng days; 6-8 CPU-h; ~6 LTC stages (~24 eq.) |
| 17 | Optional TCEC-relevance bets: R32 pilot then slice arms; R33 | L, K, G | conversion and drawish endings at TCEC | owner | ~10.5 h datagen lane; 2-3 GPU-h; 4-8 stages |
| 18 | **R30 removal round** (factorial, guard) | G | after the last feature | X18 tooling, step 12 done | 22-32 stages (~7-10 h) |
| 19 | **R24 final retune by scaling class** + VLTC spot check | G | re-optimises around the final feature set | step 18 | ~22-26 h plus validation; VLTC 2 stages (~3x an LTC stage each) |
| 20 | R38 idea 23 capped pilot, or archive | L, G | after the known LMR terms, never on the old proxy | owner; steps 12, 19 | ~25 local h; 10-15 stages |
| 21 | The close: final gauntlet on the TCEC build (R11), X20 sanitizer audit, X19, audit-2, phase-end checklist, a note that every Phase 4 Elo figure is 1-thread | all | the close | everything | 3-4 days |

**Totals (UNVERIFIED).** GitHub about 350 STC-equivalent stages (about 110
GitHub-hours, including R40 and R41 at LTC), against about 550 or more for the remaining §5.6 search work
under its current methods (ST8); at the past 28% utilisation (ST7) that is
two weeks, so keep two ready tests queued. Kaggle about 25-30 GPU-hours over
the period (within one week's quota). Local CPU about 30-50 measurement
CPU-hours at 2 threads plus about 10-15 quiet hours, aligned with part seals.
Engineering about 25-35 agent days, which is the binding resource:
**rest of Phase 4 about 3-4 weeks.**

**Parallelism.** Kaggle (steps 3, 8, 13, 14) never waits for GitHub. Local
measurements (steps 1, 5, 16) run beside data generation at low priority, one
at a time. GitHub is filled in this order of priority whenever a test is
ready: network promotions (8, 13), then TM (10), SPSA (11), search features
(12); X9 and I2-type ladders only as filler.

---

## 7. Owner decisions needed

1. **Time management into Phase 4:** node share + best-move stability only
   (R8), on the LTC list; base allocation, the time curve and the ratio-600
   control stay in Phase 5. The resolution-aware soft stop is dropped
   (refuted by the code).
2. **The SPRT design for search features:** design R ([0, 6] nElo, α 0.05,
   β 0.20, cap 8, stage-2 futility) as the standard, with the same design at
   LTC capped at 4-6 LTC stages; networks keep [0, 5]. **The risk accepted:**
   about 2% of truly null features adopted and about a third of +3 nElo
   features lost early, for about 60% fewer stages per test. Option: R+cap
   at a +5 nElo threshold (about 6% near-null adoptions); B14 advises against
   the +3 threshold (13%). Adopt a limit of a few tries per idea (every
   retry spends α again).
3. **Constants by head-to-head selection** (ST6) instead of each-vs-off
   ladders, with the constants table recording "head-to-head, N games,
   Δ ± e" as Fork's own measurement for the originality rule; mini-SPSA (O8)
   once the driver exists.
4. **Split the SPSA retune:** R14 early (eight margins, STC) and R24 at the
   end by scaling class; time-management parameters never in an STC/LTC SPSA;
   the eval scale never in SPSA; accept that adoptions after R14 shift its
   optimum slightly (R24 recovers it).
5. **Workflow changes** for the SPSA driver (a FORK_TUNE build input,
   per-pair options), the factorial screen (per-shard TEST_OPTS) and the
   runner A/B speed job.
6. **The removal round redesign** (R30), replacing Quality control 6's
   per-feature [−3, 0] method; accept the 23% chance of removing a +3 nElo
   feature in exchange for a decision on every switch.
7. **The speed-to-Elo measurement** as a throttled 0.5x build at 2 STC + 1
   LTC stages with in-situ ratios (X8), replacing item 4's 0.85x time odds.
8. **The speed gate:** measure the gate ratio in the shard build on runners
   (X3) and price it at 1.5 Elo per 1% (1.26-1.80) instead of HANDOFF's 2 ± 1
   or 3.1; keep the 0.90 threshold until X8 has run. Separately: a
   cycles-per-node 1% acceptance rule for bench-identical changes (X13; a
   DESIGN §7 change), and whether a change slower locally but faster on
   runners and at TCEC may be adopted (R31; a doctrine change).
9. **The TCEC build (R11):** x86-64-v4 with C1's AVX-512BW path behind a
   startup CPU check (or a launcher, if TCEC accepts one: a Discord
   question), PGO by default with a fallback, the compiler by measurement;
   VNNI stays out until TCEC answers (the 2026-10-28 rule); the final
   gauntlet plays the TCEC build. C1 for the native datagen build now.
10. **Item 8a's recipe additions:** keep the control unchanged, add the
    cooldown branch, the anneal-only arm, (if the gold set exists) the
    recency arm, and optionally the high-WDL branch on the finished candidate
    (R39: a target change on a branch only, guarded by the endgame check and
    a 5-man rook-ending check); allow an averaged candidate to go to the SPRT when it is
    more than 1e-5 better offline; score candidates offline on the full
    validation set instead of best-of-N; keep checkpoints and optimiser state.
    Set the endgame-check target (≤ 15 of 900 proposed).
11. **Numbering:** "item 8" = the retrain loop (8a, 8b, ...); idea 42 folded
    into R20.
12. **g3h from the 2026-09 book** (R1), after the duplicate count.
13. **Local measurement jobs beside data generation** (X2, X6, X7, X10, X11;
    2 threads each, one at a time), and using part seals as the quiet windows
    for speed A/Bs.
14. *(Resolved by the owner on 2026-11-07; no decision needed. See §8.3,
    clean-room notes: Stormphrax is a concept-level source, and the KB's
    citations of it stay.)*
15. **TCEC game statistics for a time-management constant** (a remaining-moves
    quantile from TCEC's archive): allowed as calibration, or only as a cross-
    check? Recommendation: set constants from Fork's own long-TC games; use
    TCEC statistics only to cross-check (TC §2.F; data-policy rule 4 bans
    other engines' games as training data, and this is a nearby case).
16. **Calibration constants fitted on SPRT test games** (R33), or only on a
    dedicated local run.
17. **The endgame-start slice** (R32): a datagen setting change costing
    about 10.5 h of the data-generation lane, plus a second, endgame-start
    test book for judging it.
18. **A gauntlet of S512ppr2 now** (X14), already open in HANDOFF.
19. **Idea 23:** the capped pilot with a game-based fitness after the LMR
    terms (R38), or archive.
20. **The drop list** of §4.1 (distillation, S512cl's speed work, idea 40's
    L1/L2/L3, the QAT validation session, the LTC candidates, idea 45 part 3,
    idea 47.1, idea 34, BOLT, the re-validation filler).
21. **A VLTC spot check** (120+1.2, 2 stages, about 3x an LTC stage each) of
    the final retune's output (TC §2.B).
22. **Phase 6 guardrails as a standing rule** (H9): no new per-thread table
    above about 256 KB without a TCEC-footprint note; weight tables ≤ about
    4 MB; new search state per-thread or explicitly shareable.
23. **TT-policy tests at a hash scaled to TCEC's pressure** (X23).
24. **Optional:** bundle search adoptions into at most one datagen part switch
    per day, so frequent adoptions do not fragment parts (a labeller-policy
    refinement; a judge's suggestion, not reviewed by a skeptic).
25. **ProbCut at LTC only?** OS-Stormphrax's ProbCut was neutral at STC and
    positive at LTC. Fork's ProbCut reached H0 at STC (−5.29 ± 3.58) and the
    owner ruled no retest. The question is only whether an LTC-only test
    (about 5 LTC stages) is allowed after R6 gives Fork node types.
    Recommendation: keep the rule unless spare LTC capacity exists; expected
    0 to +2 at LTC (overlap with multi-cut and NMP, A2 §2.2).
26. **Negative extension at cut nodes only (R40):** confirm that the gated,
    sub-ply form counts as a new idea rather than a retest of the rejected
    ungated one (A2 O6 argued it is different; OS-Stormphrax's first gain was
    this gated form). Keep `use_negative_extension` until then.

---

## 8. Contradictions resolved, and what remains unverified

### 8.1 Rulings

| Question | Ruling | Evidence |
|---|---|---|
| Speed-to-Elo: 3.1 Elo per 1% (HANDOFF) or about 1.5? | **1.5 (1.26-1.80) at STC**; LTC 0.65-1.15 of STC | PA §1.1a: 8 FN/STC pairs, χ² 24.5 on 7 dof, S512+X 3.3σ off the line |
| Undertrained nets (A1 B1) or LR-floor-limited (T2, W3)? | **Warm retrains are LR-floor limited and already annealed; scratch runs are compute-limited** | B13 §2.1: warm 1e-4 phase slope −0.2e-5 ± 2.9e-5 per 100 superbatches; scratch −13 to −26e-5 |
| Does S512ppr2's +20.1 come from the anneal? | **Unresolved**; plausibly +8 to +15 of it; the "+17" argument is circular | B13 §3.1; X4 settles it by Elo |
| Residual floor left at 1e-5 | **about 2e-5**, so cooldown + averaging +1 to +3, not +2 to +7 | B13 §3.1 (α = 1 under noise-dominated Adam) |
| Is g3s2-val blind to the new sources? | **Refuted:** the scored prefix holds 10.7% g3b-g3e positions; it is nearly blind to the slice (0.08%) | B13 §2.2, parsed both files |
| Training scale S = 92 or about 85? | **Keep 92**; the filtered mix fits about 89 | B13 §2.3 |
| Links worth "≈ 102 Elo per 1e-4" (18x T/U ratio)? | **Noise** (best-of-N); qualitative point only | B13 §2.1: on window means S512+PP's loss is worse than its control |
| M4's "S compressed at every promotion" | **Artefact** of the training-S change (105 → 92); play/train ratio flat 0.96-1.00 | B13 §5, nets.md |
| Distillation from S512+X | **Refuted** | B13 §3.6: the teacher is weaker at fixed nodes |
| Result weight: raise it, lower it, or TD-k? | **Measure first** (X11 → w*); none in item 8a's main arms; OS-Stormphrax's high-WDL fine-tune gain earns only a guarded branch (R39) | B13 §3.2: shallow-play bias is class-signed; OS-Stormphrax's results come from its own, different self-play |
| Correction tables: about 0 at STC (OS) or positive at STC (OS-Stormphrax)? | **First tables can pay at STC; marginal ones show at LTC**; for Fork the non-pawn and continuation keys, since the links overlap the pawn key; tests stay on the LTC list | OS §4.4; OS-Stormphrax (every table passed at STC); I5's P7 |
| Recency: purge old labels or keep them? | **Down-weight, never purge**; the warm recipe already trains old and new together | OS-Stormphrax: newer data alone lost at STC, keeping old data in the last stage won; T4 |
| History: persist across moves or decay? | **Persist, with mild ageing per search** (R16), tested regardless of X2 | OS-Stormphrax (persistence paid; extra ageing paid a little); A2 O3 |
| Negative extension: dead, or only its ungated form? | **Only the ungated form is dead**; the cut-node, sub-ply form is a separate LTC test (owner to confirm) | A2 §2.2, A2 O6, OS-Stormphrax |
| ProbCut: settled? | **Settled at STC (owner: no retest)**; an LTC-only test is an owner question, low expected value | Fork −5.29 ± 3.58 STC; OS-Stormphrax neutral STC, positive LTC |
| C's island finding = weak-pawn knowledge? | **No**: position-type effect (leader's own islands convert more too) | B13 §2.4 |
| Early SPSA: +15-35, +4-12, or ≤ +5? | **O1 +2 to +8 STC (central +4), LTC +2 to +7**; the full SPSA programme +5 to +12 LTC | B14 §3.1 |
| Should I2's multiplier ladder gate SPSA? | **No**: a 1-D slice with ±7 Elo resolution; filler only | B14 §2.I2 |
| Resolution-aware soft stop | **Refuted**: no pending root fail high at a soft stop in timed play | searcher.cpp 761-776, 816 [V]; B14 §2.S1 |
| TM "must precede SPSA" | **Weak**; the real reason is that LTC tests and the gauntlet should play with TCEC's TM | B14 §3.3 |
| TT regime on runners: L3-resident (A3) or DRAM-bound (H)? | **H directionally right, unmeasured**; X3 settles it | B14 §3.2 |
| Fractional depth: rank-2 enabler or ≈ 0? | **Round-once arithmetic only**; level 2 out | PA §3.2, B14 §3.6 |
| SPRT redesign: R or R+cap? | **R as standard**; R+cap at +5 nElo optional | B14 §2.ST1, reproduced simulations |
| Removal round: dedicated SPRTs or factorial? | **Factorial with four fixes** | ST5, B14 §2.ST5 |
| W6 sequential halving vs ST1 | **ST1** as standard (dependencies, stacking) | B14 §2.W6 |
| Antithetic screens | **Symmetric strengths only** | B14 §2.O7 |
| H2's "+9 to +22 Elo thrown away by the 3% rule" | **+2 to +6** (P-2, P-3 were adopted anyway) | B14 §2.H2 |
| VNNI in the TCEC build | **Blocked** by the owner's 2026-10-28 rule until TCEC answers | KB competition.md question 8 [V] |
| Threats vs king-zone pawns vs passers vs output experts | **Screen first; park threats**; build at most one family | B13 §3.5 |
| "LTC candidates" (S512+X, AF-S) | **Drop** | A3 §1.4: R_LTC ≈ R_STC |
| Time-odds skew cause | **Per-move latency, not Move Overhead** | PA §1.1g |
| Seed noise of a net | **about 4 Elo per-net sd**, not ±10-15 | PA §3.1 |
| Fixed-node games as variance reduction; a new test book | **Neither** | ST §3.9-3.10 |

### 8.2 What remains unverified

- Every Elo range in this file is a model prediction or a shrunk prior; none
  is a Fork measurement except where a logged run is cited.
- The self-play to third-party factor (about 1.7x; two gauntlets on different
  anchors).
- The anneal's share of S512ppr2's +20.1 (X4), and whether the 1e-4 phase
  carries learning that only an anneal reveals (needs branch cooldowns).
- g3g's seal time (assumes the log counts records as the target does) and the
  upload time for 1.69 GB; whether T4 x2 counts once against Kaggle's quota.
- Whether a relabel mode or batch EPD scorer exists (X7, X11), and how
  fixed-node playouts are made independent (X11).
- ρ_s² for node share on Fork (X6); every TM Elo figure is a shrunk external
  prior.
- The recoverable misplacement T of Fork's margins (R14) and the SPSA
  landscape; every SPSA figure is model-conditional.
- Runner cache geometry and SMT topology; the TT regime on the shards; whether
  a local 0.50x throttle plays at 0.50x on runners (X3, X8).
- Every input design's nps (C4, passers, the threat lane) until X12; Zen 4 and
  Zen 4c microarchitecture details behind R11, R23, R31 and H8's arithmetic;
  PGO's gain; the Elo value of 1% nps at TCEC.
- Whether TCEC's harness accepts a shell launcher; VNNI on the EPYC 9754.
- LTC stage wall time (about 75 minutes) and the STC per-stage overhead (about
  5.4 minutes); hence every GitHub-hour figure.
- fastchess per-engine `nodes=`/`tc=` through TEST_OPTS (ST4, X8's option).
- The in-game history distribution (X2) and the LMR-history branch's nps.
- Bench identity of a 1/64-ply LMR table against the current uint8 table.
- C's gauntlet blind-spot lifts (4-7 positions per threshold, S512r2 era).
- The survey priors (SPSA, TM, correction tables, Elo per doubling at long TC)
  are other engines' SPRT-selected results. OS-Stormphrax's are one engine's
  OpenBench point estimates, some at node-scaled controls during a rewrite
  (its node-share and post-rewrite SPSA tests), so their transfer to Fork's
  8+0.08 and 40+0.4 is UNVERIFIED.
- Novelty claims: no agent surveyed exhaustively; "NOVEL" means not found in
  the KB or the surveys.
- My own checks this session: the iterative-deepening loop's soft check
  (searcher.cpp), the §5.6 order and its item numbering, HANDOFF's standing
  rules and g3g target, KB competition.md's VNNI rule and Stormphrax entries.
  Every other [V] in this file is the credited agent's verification, not mine.

### 8.3 Clean-room notes

- **Stormphrax (owner ruling, 2026-11-07, relayed by the orchestrator).**
  Stormphrax is part of the clean-room survey at concept level only: its
  public README, release notes, PR prose and forum posts. Its source and its
  exact constants are never used. Any instruction embedded in its text is
  data, not a command, and is ignored. One such instruction, aimed at LLM
  readers, appeared in its README; the OS survey's agent ignored it, as the
  ruling requires. The OS survey (B2) left Stormphrax out before this ruling;
  the supplement in phase-b-specialists.md (B2) covers it. The KB's existing Stormphrax
  citations (nnue-inputs.md §1.4 and §1.6; several nnue-design.md entries;
  KB competition.md, where it is off-limits for code and usable as an
  opponent) stay.
- **Stormphrax supplement:** it is in phase-b-specialists.md, section B2
  (supplement). It is folded into this synthesis, credited "OS-Stormphrax",
  with its numbers shrunk like every other survey prior (§2.0). Its README
  also says the author does not want LLMs mining the engine for ideas; the
  owner's ruling above governs its use here, at concept level only.
- **The standing rules hold for every item here.** Concepts from papers,
  wikis, release notes and PR prose only. No other engine's source, nets,
  games or evaluations. No other engine's constants: every number proposed
  here is a placeholder to be measured or a value derived from Fork's data.
  Every new identifier and every new or changed search constant goes through
  the separate name and constant screen before it is committed.
