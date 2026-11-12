# Search-constant staleness audit (coordinator's order, 2026-11-12 ~7:25 AM EST)

**Record copy (committed 2026-11-12).** The coordinator's audit report as written, with local paths and machine
details removed. The owner's decisions on it (2026-11-12, about 2:10 PM EST): `SingularMarginPerPly`'s final-retune
range is 2-16 (default 6; §4.3 below recommended keeping 2-12); ProbCut's three constants stay unmeasured on
r8brft1 until the final retune (LTC class); and the main finding of §4.2 is a testing rule (DESIGN.md "Testing
setup"): offline re-measurement rules set retune ranges only and never gate or pick values by themselves. The
tooling is on branch `tools/staleness-audit`.

**Engine audited:** phase-4 75d53f0 (r8brft1; ProbCut, E1 and B13 adopted). Bench 9,263,568 / 881c326307a2ba8a,
matched by the local tuning and stats builds and by the VM's tuning build (plus perftbench 26,401,709). Re-run
tooling: branch `tools/staleness-audit` (identifiers listed in §5). Times EST.
**Nothing was queued on GitHub; no SPRT was started.**

**Default-net timeline** (CMakeLists.txt history): bootstrap eval (Phase 3, until 10-29) -> B0, B0r1 (10-29) ->
B0r2, S-512 (10-30) -> S512r2 (11-01) -> S512+PP, S512ppr2 (11-06) -> S512ppr3 (11-07) -> r8btd90 (11-10) ->
r8brft1 (11-11). Every constant set before 11-11 was set on a different net from today's.

## 1. Ranked table: the declared-rule re-runs, plus the placeholders

Ranked by the feature's SPRT gain (STC Elo unless marked; source: SPRT logs, transfer.json). % = (new - old) / old.
Flags: **MOVED** (|change| > ~30%), **PLACEHOLDER** (never measured as a value), stable.

| # | constant | old | new (re-measured) | % | method (rule's location) | set on (net, date) | feature gain | flag |
|---|---|---|---|---|---|---|---|---|
| 1 | SingularMarginPerPly | 6 | **22** | +267% | T27 rule 1 (tools/singular_measure.py docstring; DESIGN "Search constants") | S-512, 2026-10-31 | SE +14.12 ± 6.55 (S-512); LTC on/off +25.83 ± 6.38 (32c5517) | **MOVED; SPRTed 22 vs 6: H0, -26.76 ± 9.93 (6 stays)** |
| 1 | SingularMinDepth | 6 | 6 | 0% | T27 rule 2 | S-512, 10-31 | (SE) | stable (but see note: rule floor 6 in this sample) |
| 1 | SingularEntrySlack | 3 | -1 literal (deficit 0 fails at 0.85); deficits 1-3 pass (0.99 / 0.97 / 1.00) | n/a | T27 rule 3 | S-512, 10-31 | (SE) | stable in substance; rule output degenerate |
| 2 | NoMoveReduceMinDepth | 8 | 7 | -12.5% | tools/no_move_measure.py rule (docstring; option B) | S-512 labels, 2026-11-01 | IIR +21.45 ± 5.98; LTC on/off +26.25 ± 6.65 | stable |
| 3 | ReplyWeight | 6 | 8 (grid edge) | +33% | bench mean cutting-quiet index, depths 1-6 (DESIGN row, 10-31) | S-512, 2026-10-31 | +11.46 ± 5.57 | **MOVED** (weak, see §3) |
| 4 | CaptureProbeMinDepth | 9 | not re-measured (withdrawn) | n/a | tools/tier2_measure.py + capture_probe.json (d5a6eb6) | S512r2 labels, 2026-11-06 | ProbCut LTC +9.40 ± 5.03 (STC on S512r2: -5.29, H0) | **UNMEASURED on the current net** (set on S512r2): final retune LTC class |
| 4 | CaptureProbeReduction | 5 | not re-measured (withdrawn) | n/a | same measurement | S512r2, 11-06 | (ProbCut) | **UNMEASURED on the current net**: final retune LTC class |
| 4 | CaptureProbeMargin | 80 | not re-measured (withdrawn) | n/a | same measurement | S512r2, 11-06 | (ProbCut) | **UNMEASURED on the current net**: final retune LTC class |
| 5 | FollowWeight | 4 | 8 (grid edge = range ceiling 8) | +100% | bench mean cutting-quiet index | S-512, 2026-11-01 | +7.22 ± 3.92 | **MOVED** (weak) |
| 6 | TakeWeight | 4 | 2 | -50% | bench mean cutoff index (all cutoffs) | S-512, 2026-10-31 | +4.53 ± 2.99 | **MOVED** (weak) |
| 7 | AspirationHalfWidth | 12 | **29** | +142% | bench p90 of the iteration score change, aspiration off, depth >= 5 (69e830a; DESIGN row) | bootstrap, 2026-10-25; kept at 12 by R14 SPSA on S512ppr3 (11-09) | aspiration **+3.91 ± 7.60 Elo (nElo +6.19 ± 12.04), 3,200 games STC, bootstrap eval, stopped inconclusive 10-25; never re-tested on a net** | **MOVED** (rule) / SPSA says 12 |
| 7 | AspirationMinDepth | 5 | none (p90 25-31 cp at every depth 2-14; never settles) | n/a | same measurement | bootstrap, 10-25 | (aspiration) | **MOVED** (rule no longer identifies a depth) |
| 8 | TimeScaleStabilityCap | 72 | 32 | -56% | owner's 99th-percentile rule, tools/measure/tm_curve.py (X6) | X6 games of s512ppr2-stc, 2026-11-07 | TM (b) +18.69 ± 7.18; LTC +10.23 ± 5.14 | **MOVED** (low impact: floor binds above ~15) |
| 8 | TimeScaleMaxDepth | 19 | 21 | +11% | X6: last depth with >= 1% of rows | same | (TM b) | stable |
| 8 | StabilityFit / ShareFit / DepthFit | see §3 | refit | coefficients move 0-70%, curve within ~6% | X6 logistic fits | same | (TM b) | stable (as a curve) |
| 8 | TimeScaleBalanceStability / Share | 1030 / 996 | 1026 / 980 | -0.4% / -1.6% | X6 mean-spend balance | same | (TM b) | stable |
| 9 | IterationGrowthThirds | 5 | 5 (median 1.59; p75 1.89, p90 2.45; 322 ratios) | 0% | bench cumulative nodes, depths 8-14 (4ec034d) | bootstrap, 2026-10-26 | deliverable 8 (d8-final +1.89 ± 10.62, non-reg) | stable |
| 10 | ForcedMoveFraction | 8 | 6 (1.59^4 = 6.39) | -25% | derived from the growth median (audit-1 B-1) | bootstrap, 2026-10-28 | b1-forced +0.96 ± 3.54 (non-reg) | stable (under 30%) |
| P1 | RfpMaxDepth, NullMinDepth, NullSurplusPliesMax, LmrMinDepth, LmrMinMove, LmrDivisorTenths, LmpMaxDepth, FutilityMaxDepth, SeePruneMaxDepth, QuietSeeFloor | 6, 3, 2, 3, 4, 45, 4, 6, 6, 60 | not re-run (no declared rule) | | reasoning (DESIGN rows); LmrMinMove and LmpMaxDepth cite bench stats | bootstrap, 2026-10-25 | tier-1 group (RFP+NMP+LMR+LMP+futility+SEE) +439 STC / +556 LTC (bootstrap); SEE prune alone +21.16 ± 10.08 | **PLACEHOLDER** |
| P2 | HistoryBonusFactor, HistoryBonusCap | 25 (12.5·d²), 1250 | not re-run | | reasoning | bootstrap, 10-25 | history +418.9 (bootstrap) | **PLACEHOLDER** |
| P3 | HistorySkipMaxDepth | 3 | not re-run | | placeholder (DESIGN row) | 2026-11-05 build, r8brft1 test | history skip +6.04 ± 4.37 | **PLACEHOLDER** |
| P4 | TableProbeMinDepth | 1 | not re-run | | reasoning (Phase 8 measures it) | bootstrap, 10-26 | b2 inconclusive | **PLACEHOLDER** |
| P5 | AssumedMovesLeft, MaxMovesToGo, HardOverSoft, ReserveDivisor, DangerZoneOverheads | 30, 40, 4, 10, 2 | not re-run | | reasoning ("measured in Phase 5") | bootstrap, 10-26/27 | deliverable 8 non-reg | **PLACEHOLDER** (class c) |
| P6 | StaleDepthPerSearch | 2 | not re-run | | reasoning; its switch UseTtAgeBlend is off | bootstrap, 10-26 | none (switch off) | PLACEHOLDER (inactive) |

LmrMinMove's supporting stat moved a little: the share of cutoffs on the first move is 83.4% on today's bench
(was 87.8%); mean cutoff index 0.357 (was 0.27).

## 2. Full provenance table (every constant in src/tune/params.hpp, plus the TimeScale set)

| constant | value | set on (net, date) | method | feature | feature SPRT gain | re-run? |
|---|---|---|---|---|---|---|
| AspirationMinDepth | 5 | bootstrap, 2026-10-25 (69e830a) | measured on the bench (aspiration off, p90 settling) | aspiration | +3.91 ± 7.60 (inconclusive) | yes, §1 #7 |
| AspirationHalfWidth | 12 | bootstrap 10-25; R14 SPSA kept it (S512ppr3, 11-09) | measured (p90 rule), then SPSA (unchanged) | aspiration | as above; inside the R14 set (+37.93) | yes (cheap), §1 #7 |
| IterationGrowthThirds | 5 | bootstrap, 10-26 (4ec034d) | measured (bench growth median) | TM iteration rule | d8 non-reg | yes, stable |
| ForcedMoveFraction | 8 | bootstrap, 10-28 (audit-1 B-1) | derived (growth^4) | forced-move stop | +0.96 ± 3.54 non-reg | yes, 6 |
| RfpMaxDepth | 6 | bootstrap, 10-25 | reasoning | RFP | tier-1 group | no (placeholder) |
| RfpMargin | 55 | S512ppr3, 11-09 | **SPSA** spsa-r14-m2 (pinned at its floor 40 + c) | RFP | R14 set +37.93 ± 10.03 STC, +29.93 ± 8.71 LTC | no (SPSA) |
| NullMinDepth | 3 | bootstrap, 10-25 | reasoning | NMP | tier-1 group | no (placeholder) |
| NullSurplusPerPly | 301 | S512ppr3, 11-09 | **SPSA** R14 (300 = bootstrap knight, reasoning) | NMP | R14 set | no (SPSA) |
| NullSurplusPliesMax | 2 | bootstrap, 10-25 | reasoning | NMP | tier-1 group | no (placeholder) |
| TableProbeMinDepth | 1 | bootstrap, 10-26 | reasoning | Syzygy probing | b2 inconclusive | no (placeholder; excluded from SPSA) |
| LmrMinDepth | 3 | bootstrap, 10-25 | reasoning | LMR | tier-1 group | no (placeholder) |
| LmrMinMove | 4 | bootstrap, 10-25 | reasoning + bench stat (87.8% first-move cutoffs; now 83.4%) | LMR | tier-1 group | no (placeholder) |
| LmrDivisorTenths | 45 | bootstrap, 10-25 | reasoning (anchor points) | LMR | tier-1 group | no (placeholder) |
| LmrCorrectionStrength | 64 | 10-26 (8c) | a unit (rule slot is 0) | idea-23 slot | none | no (unit) |
| LmpMaxDepth | 4 | bootstrap, 10-25 | reasoning + cutoff-index histogram shape | LMP | tier-1 group | no (placeholder) |
| LmpQuietAllowance | 8 | S512ppr3, 11-09 | **SPSA** R14 (pinned at floor); was the bench 1% rule (12) | LMP | R14 set | no (SPSA) |
| FutilityMaxDepth | 6 | bootstrap, 10-25 | reasoning | futility | tier-1 group | no (placeholder) |
| FutilityOffset | 86 | S512ppr3, 11-09 | **SPSA** R14 (still falling) | futility | R14 set | no (SPSA) |
| FutilityGrowth | 50 | S512ppr3, 11-09 | **SPSA** R14 (still falling) | futility | R14 set | no (SPSA) |
| SeePruneMaxDepth | 6 | bootstrap, 10-25 | reasoning | SEE pruning | +21.16 ± 10.08 (bootstrap) | no (placeholder) |
| QuietSeeFloor | 60 | bootstrap, 10-25 | reasoning (left out of R14 as insensitive) | SEE pruning | +21.16 | no (placeholder) |
| CaptureSeeFloor | 118 | S512ppr3, 11-09 | **SPSA** R14 | SEE pruning | R14 set | no (SPSA) |
| SingularMinDepth | 6 | S-512, 10-31 | measured (T27 rule 2) | SE | +14.12 STC; +25.83 LTC on/off | yes (builder 3), stable |
| SingularEntrySlack | 3 | S-512, 10-31 | measured (T27 rule 3) | SE | as above | yes (builder 3), see §3 |
| SingularMarginPerPly | 6 | S-512, 10-31 | measured (T27 rule 1) | SE | as above | yes (builder 3): **22** |
| NoMoveReduceMinDepth | 8 | S-512, 11-01 | measured (no_move_measure.py; no depth beat "off") | IIR | +21.45 STC; +26.25 LTC | yes (VM): 7 |
| CutNodeLmrPlies | 1 | S512ppr3 both sides, 11-09..11 | **head-to-head** b4-cut-node-h2h (2 - 1 = -5.33 ± 12.04 nElo) | cut-node LMR | +6.02 STC, +9.75 LTC | no (head-to-head) |
| CaptureProbeMinDepth | 9 | S512r2, 11-06 | measured (tier2_measure capture_probe; no setting beat "off") | ProbCut | +9.40 LTC | yes (VM), not re-measured (withdrawn) |
| CaptureProbeReduction | 5 | S512r2, 11-06 | measured (same) | ProbCut | as above | yes (VM), not re-measured (withdrawn) |
| CaptureProbeMargin | 80 | S512r2, 11-06 | measured (same) | ProbCut | as above | yes (VM), not re-measured (withdrawn) |
| HistorySkipMaxDepth | 3 | first build 11-05; adopted on r8brft1 11-12 | **placeholder** | history skip | +6.04 ± 4.37 | no (placeholder) |
| HistorySkipPerPly | 700 | r8brft1, 11-11 | firing-rate candidates, then **head-to-head** qhp-h2h | history skip | +6.04 ± 4.37 | no (head-to-head; set yesterday on today's net) |
| HistoryBonusFactor | 25 | bootstrap, 10-25 | reasoning (12.5·d²) | history | +418.9 (bootstrap) | no (placeholder) |
| HistoryBonusCap | 1250 | bootstrap, 10-25 | reasoning (HistoryMax / 8) | history | +418.9 | no (placeholder) |
| ReplyWeight | 6 | S-512, 10-31 | measured (bench cutoff index) | reply table | +11.46 ± 5.57 | yes: 8 |
| FollowWeight | 4 | S-512, 11-01 | measured (bench cutoff index) | follow table | +7.22 ± 3.92 | yes: 8 |
| TakeWeight | 4 | S-512, 10-31 | measured (bench cutoff index) | take history | +4.53 ± 2.99 | yes: 2 |
| StaleDepthPerSearch | 2 | bootstrap, 10-26 | reasoning (switch off) | TT age blend | none (off) | no |
| AssumedMovesLeft | 30 | bootstrap, 10-26 | reasoning | time budget | d8 non-reg | no (class c) |
| MaxMovesToGo | 40 | bootstrap, 10-26 | reasoning | time budget | d8 | no (class c) |
| HardOverSoft | 4 | bootstrap, 10-28 | reasoning | time budget | d8 | no (class c) |
| ReserveDivisor | 10 | bootstrap, 10-26 | reasoning | time budget | d8 | no (class c) |
| DangerZoneOverheads | 2 | bootstrap, 10-27 | reasoning (B2 variant; stress-tested) | time budget | d8-final +1.89 ± 10.62 | no (class c) |
| TimeScaleMinDepth (not in params.hpp) | 8 | X6, 11-07 | X6 declared primary depth | TM (b) | +18.69 STC, +10.23 LTC | definition |
| TimeScaleMaxDepth | 19 | X6, 11-07 | X6 1% rule | TM (b) | as above | yes: 21 |
| TimeScaleStabilityCap | 72 | X6, 11-07 | owner's 99th-percentile rule | TM (b) | as above | yes: 32 |
| TimeScaleShareMin / Max | 5 / 995 | X6, 11-07 | declared clip | TM (b) | as above | definition |
| StabilityFit, ShareFit, DepthFit | see §3 | X6, 11-07 | logistic fits | TM (b) | as above | yes (refit) |
| TimeScaleBalanceStability / Share | 1030 / 996 | X6, 11-07 | mean-spend balance | TM (b) | as above | yes: 1026 / 980 |
| TimeScaleFloor | 360 | X6, 11-07 | derived from growth 5/3: (3/5)² | TM (b) | as above | growth unchanged, so 360 stands |

Not in this audit: the drift-table constants (branch tier2/corr-tables, every switch off on phase-4, reused from
T32's pawn-key measurement and marked UNVERIFIED for their keys); definitions and units (DriftShareUnit, ThreatBuckets,
HistoryMax, EvasionCaptureBase, the MVV-LVA form, TableNearDrawScore, ScoreTrendLimit, StopCheckInterval,
fail_report_ms, MovetimeFloorDivisor, the increment share 3/4, the 1-ply units).

## 3. Method notes and caveats per re-run

- **Singular (builder 3's run 2, b71199d; not redone).** 400 evolve positions at depth 13, 400 samples per
  depth 6-12 per was_pv stratum (5,600), release build, Hash 16. Its pooled pick is 22. Because the 50/50 strata
  over-sample PV entries (their natural share is 4-23% by depth, from collect's counts), I re-weighted the strata
  to their natural shares, offline from its results.jsonl (a scratch script, not committed). **Rule 1 still
  gives 22 and rule 2 gives 6.** Depths 11-12 decide it: they are 0.84-0.88 at M 6-20, on 96-48 flagged samples,
  so the pick is sensitive to sampling noise there. Rule 2's 6 is the floor of this sample (depths below 6 were not
  sampled), so it is not a fresh test of 4-5. Rule 3 at M 22: deficit 0 holds 0.85 (34 flagged), deficits 1, 2 and
  3 hold 0.99 (202), 0.97 (37) and 1.00 (22). The literal rule therefore returns -1; read in substance, slack 3 is
  unchanged.
- **Aspiration** (bench_rules.py aspiration; 46 bench positions, Hash 16, depth 14, UseAspiration off, tuning
  build). p90 of |Δscore| by depth 2-14: 25, 31, 30, 30, 29, 33, 40, 28, 47, 21, 23, 29, 23 cp. Pooled from depth 5:
  29 cp (460 changes; 71.5% within 12 cp). The original was taken in bootstrap-eval centipawns; the NNUE's
  iteration-to-iteration swings are about 2.4 times larger. The R14 SPSA (S512ppr3, c = 1.0) left the value at 12
  after 10,400 pairs, which is Elo evidence that 12 is not far off. Its range is 6-24, so the rule's 29 is outside
  what a retune could reach. **Depth sensitivity:** the rule is per iteration and the bench stops at depth 14; its
  p90 is 29-47 cp at depths 5-10 and 21-29 cp at 11-14 (46 samples per depth), a mild downward drift. LTC's
  iterations (depth ~16-20) are unmeasured by this rule, so its LTC value may be lower than 29 (UNVERIFIED). An STC
  result would not settle the LTC value.
- **Iteration growth** (bench_rules.py growth; default engine, depth 14): median 1.590, p75 1.889, p90 2.445 (322
  ratios at depths 8-14). Thirds stay at 5. The forced-move fraction 1.59^4 = 6.39 rounds to 6. The floor 360 is
  (3/5)², tied to 5/3, so it is unchanged.
- **History weights** (bench_rules.py weights; stats+tune build, UCI `bench`, one weight set, the others at their
  defaults; the original runs had the later tables off, which today's search no longer allows).
  - ReplyWeight, mean quiet index at grid points 0/1/2/4/6/8: 0.5327, 0.5187, 0.5116, 0.5136, 0.5185, **0.5069**.
  - FollowWeight, at 0/1/2/4/6/8: 0.5291, 0.5064, 0.5172, 0.5185, 0.5050, **0.4931**.
  - TakeWeight, mean cutoff index at 0/1/2/4/8/16: 0.3608, 0.3538, **0.3531**, 0.3571, 0.3577, 0.3610.
  - All three curves are non-monotone, with neighbouring points 1-3% apart. One deterministic bench has no noise
    estimate, so these picks are weak evidence: the rule's resolution is about the size of the differences.
    ReplyWeight and FollowWeight land on the grid's top edge; FollowWeight's 8 is also its range ceiling.
- **X6 / TimeScale** (tools/measure/game_replay.py + tm_curve.py; 60 games of qhp-stc, which plays the 700-per-ply
  history skip on adopt/e1 with r8brft1, i.e. today's search; seed 20261108, at most 35 test positions per game,
  2M nodes, Hash 16, Syzygy 3-4-5; 2,087 searches, 21,388 rows at depth >= 8, base rate 12.2% (was 12.9%)).
  - Fit (a): 0.174614 − 0.208077·s − 0.063239·d (was 0.534912, −0.207666, −0.096556).
  - Fit (b): 0.128307 − 0.174126·s − 0.226227·L − 0.069486·d (was 0.474586, −0.177596, −0.185073, −0.103338).
  - Depth fit: 0.248755 − 0.181462·d (was 0.567490, −0.211730).
  - The intercepts and depth slopes trade off, so the scale σ(fit)/σ(depth fit) is within −6% / +0% of the old
    one for stability up to 25 at depths 8-19 (the only large ratios come from the cap, above the floor's binding
    point).
  - Balances: (a) 1.017, 0.976, 1.085, mean 1.026; (b) 0.965, 0.934, 1.041, mean 0.980.
  - AUC: (a) 0.764, (b) 0.774.
- **IIR re-run** (VM, tools/staleness/vm_rerun.sh nomove). Labels at 25M nodes with the reduction off (Hash 64)
  over the 4,794 evolve positions; then no_move_measure.py's sweep (off, 2-8) at 250k and 2.5M nodes, Hash 16, and
  its rule. Run 7:26 AM-1:52 PM EST on the VM (8 vCPU, the filler paused and resumed at 1:52 PM).
  4,761 of 4,794 labelled. Fitness by setting: off 0.7377; 2 0.7142, 3 0.7175, 4 0.7178, 5 0.7179, 6 0.7172,
  **7 0.7280**, 8 0.7250.
  - **Chosen: 7.** It is the best by 0.0030, beyond the 0.001 tie margin. On S-512, 7, 8 and 4 had tied and 8 won
    the tie.
  - **No depth beats "off":** 7 scores −0.0097 [−0.0168, −0.0027], against 8's −0.0068 in November.
  - **Time to depth 16** (geometric mean, 4,448 positions): off 904,315 nodes, 7 622,665, 8 687,063.
  - Full report: Appendix A.
- **ProbCut re-run** (VM, vm_rerun.sh probcut). Labels at 25M nodes by the default engine; then tier2_measure.py's
  capture_probe spec unchanged: 120 settings screened at 250k nodes, the best 6 plus "off" at 250k and 2.5M. The
  measurement build widens the tuning ranges back to d5a6eb6's (min depth from 2, margin to 640), so that today's
  4-18 / 40-160 bounds do not fold the grid's 3 and 200-500 onto them. Defaults unchanged, bench parity checked.
  **Withdrawn before it started (coordinator, 2026-11-12 ~8:20 AM, the test-efficiency rule):** it would have taken
  about 12 h of the VM after IIR (~18 h of filler time), no smaller version could finish by 2:30 PM beside IIR on
  the same 8 vCPU, and the owner had already placed the three constants in the final retune's LTC class (6:15 AM).
  So they stay as measured on S512r2 (11-06) and adopted on r8brft1 by the LTC test (+9.40 ± 5.03), not
  re-measured. The driver and the widened-range measurement build remain on the branch for a later run.

## 4. Recommendation

### 4.1 Outcomes since the interim report (owner and coordinator, 2026-11-12)

- **SingularMarginPerPly 22 against 6:** SPRTed at design R STC. **H0 after stage 0, Elo −26.76 ± 9.93 (nElo
  about −46).** The re-measured value loses heavily. 6 stays.
- **AspirationHalfWidth:** no standalone SPRT. R14's SPSA kept 12 inside a range up to 24, and game evidence
  outranks the offline re-measure. Its final-retune range widens to about 8-40.
- **History weights (Reply / Follow / Take):** go to the final retune, with ranges that cover the re-measured
  values (8 / 8 / 2).
- **Time-management constants:** unchanged. They re-measured as stable, and they are not in the SPSA by rule
  (class c).
- **ProbCut's three constants:** the re-run was withdrawn before it started (the test-efficiency rule). They stay
  as measured on S512r2 (11-06) and adopted on r8brft1 by the LTC test. They sit in the final retune's LTC class.
- The range edits are made by the D8 adoption push, not by this audit.

### 4.2 Do the rules' proxy metrics track Elo? The record so far

No declared measurement rule has had its pick checked against another value in games and won. Where games or SPSA
did check a pick, the pick lost, or the tuner moved away from it, or the rule ranked the eventual winner last:

| rule family (tool) | proxy metric | game or SPSA check of the pick | verdict |
|---|---|---|---|
| quality per node (no_move_measure.py, lmr_history_measure.py, tier2_measure.py) | agreement with a 25M-node label's move, less score error / 1000, at a fixed node budget | **IIR:** the proxy ranked "off" above every depth, yet IIR passed +21.45 STC and +26.25 LTC. **ProbCut:** "off" ranked first; STC H0 (−5.29), LTC pass +9.40. **LMR history:** pick 24000 H0 (−10.81). **Rising RFP:** pick 25 H0. **Threat set:** the proxy picked "cheaper-attacker" (H0); its loser, "any-attack", later passed +7.49 STC and +8.07 LTC | **does not track Elo** (wrong sign or wrong order in 5 of 5) |
| flag precision (singular_measure.py, T27 rules 1-3) | share of flagged TT moves still strictly best at full depth (at least 90% at every depth) | the original pick 6 passed only as part of the feature test (no value comparison). **The re-run pick 22: H0, −26.76 ± 9.93** | **misleads** (below) |
| 1% cutoff bounds (LMP allowance, RFP margin floor) | share of cutoffs or fail-lows past the cut | **LMP 12:** SPSA moved it to 8 (pinned at its floor) inside a +37.93 set. **RFP 40** (rule's floor): lost about 22 points over 357 gauntlet games and was reverted; SPSA chose 55 | bounds only; the Elo optimum lies elsewhere |
| p90 score change (aspiration) | share of iterations needing no re-search | SPSA kept 12 while the rule now says 29 | not an Elo criterion |
| ordering index (reply / follow / take weights) | mean index of the cutting move on one bench | each feature passed against "off", but no weight was ever tested against another weight | **unknown**; single-bench noise is about the size of the differences |
| X6 fits (tm_curve.py) | logistic AUC; mean-spend balance | the curve's feature (TM b) passed +18.69 STC and +10.23 LTC; no value was tested against another value | the one rule whose output won in games, as a feature |

**Why T27's rule 1 misleads here.** It is a precision-only criterion: it asks that at least 90% of the moves it
flags stay best at full depth, and it ignores everything else the margin changes:
- **Recall: how many moves get extended.** Raising M from 6 to 22 cuts the flagged share from 0.26 to 0.09 at depth
  6 and from 0.12 to 0.05 at depth 12 (builder 3's table), so SE fires about a third as often. SE's value is in
  extending the critical moves, so missing two thirds of them costs more than a few false extensions.
- **Multi-cut.** Fork's multi-cut cuts when the singular bar S − M·d reaches beta. A larger M lowers the bar, so
  multi-cut fires less too. Its own value is +9.19 STC and +6.65 LTC.
- **Node cost.** Neither the cost of the test nor the node cost of an extension enters the rule. The bench falling
  10.5% at 22 shows the search effort moved off exactly the lines SE was spending it on.
- **Noise.** The pick is decided by the depth 11-12 cells, at 0.84-0.88 on 48-96 flagged samples (about ±4-5%
  standard error). A 90% bar on cells that small is a noisy threshold. Monotone precision gains at higher M come
  for free, because fewer, more obvious moves get flagged.
- In short, the rule optimises "is the flagged move right", not "is extending the flagged moves worth it". Its
  original pick of 6 worked because SE was tested as a whole against "off", not because 6 beat other margins.

**Consequence for this audit.** Treat every re-measured value as weak evidence, as the owner did for aspiration.
A re-run can usefully show that a constant's environment moved, for example the aspiration swings growing 2.4
times, or the IIR, ProbCut and ordering picks drifting. Those shifts justify putting the constant in the final
retune with a range that covers the new reading. They do not justify an SPRT at the re-measured value on their own.

### 4.3 Recommendation (under the owner's rule of 12:50 PM EST)

**What counts as "extreme".** The singular case shows that a big ratio is not enough: 22 against 6 (3.7x) lost by
27 Elo. So I count a re-measured value as extreme only if it shows the **current value no longer does what it was
set to do**. That means any of three things:
- the feature effectively never fires, or always fires, at the current value;
- the current value sits outside the code's valid domain for today's search (for example, a margin below the
  eval's own noise, or a depth limit past the depths searched);
- the rule's own metric is not just worse at the current value but broken there: an ordering weight at which the
  cutting move's mean index is worse than with the table off, or an aspiration window that fails on most
  iterations.

**Only a break of that kind is worth a standalone SPRT**, because the proxy metrics have no record of tracking Elo
(§4.2). **No constant re-measured today meets it:**
- at 12 cp aspiration still avoids a re-search in 71.5% of iterations;
- every weight beats its table's "off" on its own metric;
- the time-management curve is unchanged within about 6%.

So: **no standalone SPRTs. IIR's result is below.**

**Ranges that cover each moved value** (params.hpp lowest-highest, defaults and steps unchanged; for the D8
range push after the owner's approval):

| constant | current | re-measured | range now | proposed range | note |
|---|---|---|---|---|---|
| AspirationHalfWidth | 12 | 29 | 6-24 | **8-40** (owner) | step 1 kept (a twentieth of the range would be 1.6) |
| AspirationMinDepth | 5 | none (never settles) | 2-10 | 2-10, unchanged | the rule gives no value to cover |
| ReplyWeight | 6 | 8 | 0-12 | 0-12, unchanged | already covers 8 |
| FollowWeight | 4 | 8 (at the grid and range ceiling) | 0-8 | **0-16** (coordinator) | the int16 sum must be re-checked at 16 (the clamp exists; final-retune.md's headroom note covers Reply 12 + Follow 8 only) |
| TakeWeight | 4 | 2 | 0-16 | 0-16, unchanged | already covers 2 |
| SingularMarginPerPly | 6 | 22 (refuted: H0 −26.76) | 2-12 | **2-12, unchanged** (recommended) | covering 22 would mean 2-24; I advise against it, since games already refute 22 at STC and the SPSA's travel is better spent near 6. If the owner prefers the rule mechanically, use 2-24. The class (b) LTC pass is where a larger margin could still show |
| SingularEntrySlack | 3 | 3 in substance (literal −1) | 0-6 | 0-6, unchanged | |
| SingularMinDepth | 6 | 6 | 3-12 | 3-12, unchanged | |
| ForcedMoveFraction | 8 | 6 | 4-16 | 4-16, unchanged | class (c), not in the SPSA; the owner keeps 8 |
| IterationGrowthThirds | 5 | 5 | 3-10 | unchanged | class (c) |
| TimeScaleStabilityCap | 72 | 32 | (not a table parameter) | n/a | class (c), owner: unchanged |
| NoMoveReduceMinDepth | 8 | 7 | 2-16 | 2-16, unchanged | covers 7; class (b) |
| CaptureProbe x3 | 9 / 5 / 80 | not re-measured | 4-18 / 2-10 / 40-160 | unchanged | re-run withdrawn |

**NoMoveReduceMinDepth (IIR): **stable: rule now picks 7 (was 8, -12.5%), no SPRT; class (b) LTC dimension of the final retune; range 2-16 already covers 7.** As in November 1, the proxy ranks "off" above every depth (7: -0.0097 [-0.0168, -0.0027]) while IIR is worth +21 STC / +26 LTC in games, so the proxy cannot rank depths for Elo either; the retune decides.**

**Every other constant goes into the final retune's dimensions as final-retune.md classes them** (no range change
from this audit):
- **Class (a), STC:**
  - Aspiration: AspirationMinDepth, AspirationHalfWidth.
  - RFP and null move: RfpMaxDepth, RfpMargin, NullMinDepth, NullSurplusPerPly, NullSurplusPliesMax.
  - LMR and LMP: LmrMinDepth, LmrMinMove, LmrCorrectionStrength, LmpMaxDepth, LmpQuietAllowance.
  - Futility and SEE: FutilityMaxDepth, FutilityOffset, FutilityGrowth, SeePruneMaxDepth, CaptureSeeFloor,
    and QuietSeeFloor if it calibrates as sensitive.
  - History: HistoryBonusFactor, HistoryBonusCap.
  - Ordering weights: ReplyWeight, FollowWeight, TakeWeight.
  - History skip: HistorySkipPerPly, HistorySkipMaxDepth.
- **Class (b), LTC:** SingularMinDepth, SingularEntrySlack, SingularMarginPerPly (start 6), NoMoveReduceMinDepth,
  LmrDivisorTenths, CaptureProbeMinDepth, CaptureProbeReduction, CaptureProbeMargin.
- **Not in the SPSA by rule:**
  - Class (c) time management (Phase 5): IterationGrowthThirds, ForcedMoveFraction, AssumedMovesLeft,
    MaxMovesToGo, HardOverSoft, ReserveDivisor, DangerZoneOverheads, and the TimeScale set.
  - TableProbeMinDepth (Phase 8) and StaleDepthPerSearch (switch off).
- **Placeholders never measured, ranked by their feature's worth.** The retune is their first measurement:
  - the tier-1 depth limits and counts (RfpMaxDepth, FutilityMaxDepth, SeePruneMaxDepth, LmpMaxDepth, LmrMinDepth,
    LmrMinMove, NullMinDepth, NullSurplusPliesMax, LmrDivisorTenths; group +439 STC / +556 LTC);
  - the history bonus shape (HistoryBonusFactor, HistoryBonusCap; history +419);
  - QuietSeeFloor (SEE pruning +21);
  - HistorySkipMaxDepth (+6).
  - The limits at their range floors (NullMinDepth, LmrMinDepth, LmpMaxDepth, HistorySkipMaxDepth) are already
    flagged in final-retune.md for head-to-heads if they pin.


## 5. Tooling and identifiers for the screen

Branch `tools/staleness-audit`, first built at dc6cc18 on phase-4 75d53f0, re-created on phase-4's head and pushed
for the record on 2026-11-12 (not merged into phase-4).
- New files: `tools/staleness/bench_rules.py`, `tools/staleness/label_with.py`, `tools/staleness/vm_rerun.sh`.
- New identifiers:
  - bench_rules.py: `RuleDepthRow` (renamed from `Depth` after the name screen: `Depth` matched in all four
    engines screened), `bench_fens`, `below_normal`, `search`, `pct`, `run_all`, `aspiration`, `growth`,
    `bench_stats`, `weights`, `main`.
  - label_with.py: `OptionEngine`, `main`.
  - vm_rerun.sh: no functions besides `say`; variables `commit`, `kind`, `src`, `bin`, `out`, `labels`, `spec`.
- Brought over unchanged from earlier branches: `tools/tier2_measure.py` and `tools/tier2_measure/capture_probe.json`
  (d5a6eb6), `tools/lmr_history_measure.py` (aed999f).
- Scratch only, not committed: the singular re-weighting script, the X6 and bench (aspiration, growth) driver
  scripts, and the VM queue items stale-a-nomove and stale-b-probcut.

## Appendix A. The IIR re-run's report (VM, 2026-11-12)

no_move_measure.py's output for `NoMoveReduceMinDepth` on r8brft1 (§3, the IIR re-run), verbatim:

```
4761 positions; fitness is the mean per-position score over both budgets
 off: fitness 0.7377  250000: agree 0.7217 err 47.8 depth 12.83  2500000: agree 0.8299 err 28.4 depth 18.07
   2: fitness 0.7142 gain -0.0234 [-0.0318, -0.0151]  250000: agree 0.7093 err 47.1 depth 14.58  2500000: agree 0.7937 err 27.5 depth 20.88
   3: fitness 0.7175 gain -0.0202 [-0.0283, -0.0121]  250000: agree 0.7099 err 47.1 depth 14.20  2500000: agree 0.7994 err 27.3 depth 20.39
   4: fitness 0.7178 gain -0.0199 [-0.0282, -0.0114]  250000: agree 0.7066 err 46.9 depth 13.97  2500000: agree 0.8028 err 26.9 depth 20.12
   5: fitness 0.7179 gain -0.0197 [-0.0274, -0.0119]  250000: agree 0.7131 err 46.9 depth 13.74  2500000: agree 0.7969 err 27.2 depth 19.84
   6: fitness 0.7172 gain -0.0205 [-0.0283, -0.0123]  250000: agree 0.7083 err 46.7 depth 13.54  2500000: agree 0.7994 err 26.6 depth 19.60
   7: fitness 0.7280 gain -0.0097 [-0.0168, -0.0027]  250000: agree 0.7234 err 47.0 depth 13.41  2500000: agree 0.8061 err 26.6 depth 19.40
   8: fitness 0.7250 gain -0.0126 [-0.0199, -0.0059]  250000: agree 0.7146 err 47.1 depth 13.19  2500000: agree 0.8095 err 26.8 depth 19.14
time to depth 16 (4448 positions), geometric mean of nodes:
 off: 904,315
   2: 377,681
   3: 444,529
   4: 486,046
   5: 535,495
   6: 579,963
   7: 622,665
   8: 687,063
chosen minimum depth: 7 (fitness 0.7280; best 0.7280)
no depth's gain interval lies above zero
```
