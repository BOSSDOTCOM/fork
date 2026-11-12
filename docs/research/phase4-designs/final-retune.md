# The final retune by scaling class (R24, order step 19), with RfpMargin's lower bound widened: design, not adopted

Status: **design for the owner's review, 2026-11-09; the owner's decisions
of the same evening are recorded below.** §5.6 order step 19, after the
factorial removal round (step 18).

**The owner's decisions (2026-11-09, about 8 PM EST):** "Final retune:
apply all ten lower-bound widenings plus RfpMargin's; make the SPSA report
flag any parameter pinned at a bound." and "Calibration uses design R; the
VLTC check uses a non-regression rule". Applied the same evening (branch
retune/bounds-and-designs):
- **The eleven ranges are widened in src/tune/params.hpp** (defaults and
  steps unchanged, bench unchanged by the ranges): RfpMargin lowest 40 → 30,
  LmpQuietAllowance 6 → 3, FutilityOffset 50 → 30, FutilityGrowth 35 → 25,
  SingularMarginPerPly 3 → 2, SingularMinDepth 4 → 3, LmrMinMove 2 → 1,
  LmpMaxDepth 2 → 1; NoMoveReduceMinDepth highest 10 → 16, ReplyWeight
  8 → 12, NullSurplusPliesMax 4 → 6. RfpMargin's lowest is fixed at 30
  (decision 3 below: the floor is then 30 + c, 45 at c = 15). The defaults
  are phase-4's, R14's adopted values included (below).
- **ReplyWeight's int16 headroom at 12: checked, no overflow.** The quiet
  score (move_selector.cpp `score_quiets`, move_selector.hpp
  `quiet_order_score`) sums in `int` and clamps to ±INT16_MAX before the
  int16 store; every table entry stays within ±HistoryMax = 10,000
  (quiet_history.hpp), so the sum is at most 10,000 × (4 + 12 + 8) / 4 =
  60,000 in magnitude, exact in `int`. A reply entry alone at weight 12
  reaches 30,000, still inside int16 without the clamp; sums of tables were
  already clamped at the old highest values (ReplyWeight 8 with FollowWeight
  8). Tests: tests/test_ordering.cpp (the sum's bound from the table's
  highest values, every build; the scores at both limits with both weights
  at their highest, tuning builds).
- **The other bounds checked for hazards** (searcher.cpp): none breaks an
  assumption; two notes. (1) **LmrMinMove 1 is the same search as 2**: the
  first searched move takes the full-depth path, never the LMR branch
  (`moves_searched + 1 >= LmrMinMove` is only tested from the second move
  on), so the bound adds a value the SPSA cannot tell from 2 (a flat step,
  harmless; a tuning-build test checks equal nodes, move and score at 1 and
  2). (2) **SingularMinDepth 3** with SingularEntrySlack 3 admits a TT entry
  of depth 0 (a quiescence entry with a move and a lower bound) to the
  singular test at depth 3, searched at depth 1; the old ranges already
  reached that (slack 6 at depth 6). NullSurplusPliesMax 6 gives null depths
  at or below 0 more often, which the search already sends to the
  quiescence search; LmpMaxDepth 1, LmpQuietAllowance 3 (at least 4 quiets at
  depth 1), the margins at 30 / 25 / 2 per ply and NoMoveReduceMinDepth 16
  are plain comparisons. A tuning-build test searches each widened bound
  alone and all eleven at once (tests/test_search.cpp).
- **The pinned-at-bound flag** is in `spsa.py report` (branch
  tune/spsa-pinned, §3.3's tooling line).
- **The VLTC check's rule** is the non-regression rule of §5 item 4.
- **R14's tuned values were adopted on phase-4 the same evening (owner,
  2026-11-09):** RfpMargin 55, FutilityOffset 86, FutilityGrowth 50,
  CaptureSeeFloor 118, LmpQuietAllowance 8, NullSurplusPerPly 301, so the
  starts in §3 are the code's defaults (decision 1 below is settled). Every
  start lies inside its widened range.

Sources read: DESIGN.md §5.6 (step 19 and its 2026-11-09 note), the
decisions log (2026-11-07 decisions 4, 5, 21, 23; 2026-11-09 "RfpMargin's
follow-up moves to the final retune"), DESIGN.md §5.2's parameter-table rule
("about half to twice the default, depths in whole plies (at least 1, counts
at least 0), and an SPSA step of a twentieth of the range"),
src/tune/params.hpp (phase-4 8af5e4f), tools/github/spsa.py and
tools/github/spsa-r14.json (branch tune/spsa), the "SPSA on GitHub" section
of DESIGN.md on tune/spsa, ~/fork-spsa/github/spsa-r14-m2/report.txt and its
driver log, ~/fork-data/sprt/spsa-r14-m2-stc/driver.log, commit c59bd2b
(R14's values as defaults, branch tune/spsa-r14-m2-final),
docs/research/phase4-think-tank/phase-c-synthesis.md R24 and
phase-b-specialists.md O2, O3, O5, O6, O10 and B14.

## 1. Where things stand (2026-11-09, 7:34 PM EST)

- **R14 (the early pass) finished** 13 of 13 updates, 10,400 pairs at
  8+0.08 (report.txt): RfpMargin 80 → 55, FutilityOffset 100 → 86,
  FutilityGrowth 70 → 50, NullSurplusPerPly 300 → 301, CaptureSeeFloor 100 →
  118, LmpQuietAllowance 12 → 8, AspirationHalfWidth 12 (c59bd2b).
- **Its STC SPRT** (spsa-r14-m2-stc, run 42726060415, the local driver log):
  **+37.93 ± 10.03 Elo, nElo +64.91 ± 17.02, H1 accepted after 1,600 games**
  at 7:27 PM EST 2026-11-09 on design R's bounds ([0, 6], LLR bounds −1.56 /
  2.77). Not yet in the SPRT log; the LTC sign guard and the adoption are the
  owner's. **This design assumes R14's values are adopted before step 19;**
  if not, the phase-4 defaults are the starts and the floors below move
  accordingly.
- **The floor problem.** spsa.py keeps theta at least c inside its range
  (`lo, hi = lowest + c, highest − c` in `iteration_step`; the spec is refused
  unless `lowest + c <= start <= highest − c`), so a parameter can never
  settle below `lowest + c`. RfpMargin sat at 55 = 40 + 15 from iteration 4
  with its gradient still pushing down (the owner's 2026-11-09 note).
  **LmpQuietAllowance hit the same floor:** its trajectory reached 7.7 = 6 +
  1.7 at the eighth update and stayed there to the end (6 of the 13 updates;
  report.txt);
  the report's "step-limited" line (clamped steps in at least 2/3 of the
  updates) does not detect a bound pin, so it listed only RfpMargin.
  FutilityOffset (81.6 at the last update, floor 68.2) and FutilityGrowth
  (49.2, floor 42.5) were still falling, each within about one c of its floor.

## 2. Scaling classes (decision 4; R24; O5)

| class | what | tuned at | why |
|---|---|---|---|
| (a) shallow margins and ordering | RFP, futility, LMP, SEE pruning, null move, aspiration; history and ordering weights; LMR's non-divisor terms; step 12's and batch 4's adopted constants | STC 8+0.08 | they act within about 6 plies of the horizon, where the eval's error does not depend on the time control (O5) |
| (b) depth-scaling constants | the singular test (minimum depth, entry slack, margin per ply), IIR's minimum depth, the LMR divisor, double-extension limits if R28 is adopted | LTC 40+0.4, p about 5-6 | they change what happens at depths STC rarely reaches (O5; the IIR gain grew from +21.5 STC to +26.3 LTC) |
| (c) time management | the iteration rule and the time budget | never in an STC/LTC SPSA (decision 4; spsa.py `EXCLUDED_PARAMS` refuses them by name) | ratio 100 cannot see TCEC's allocation problem; Phase 5 |
| (d) the eval scale S | the network's output scale | never in SPSA (decision 4) | a degenerate direction (scaling S scales every cp margin at once); not a table parameter, so spsa.py cannot pass it |

Also left out: `TableProbeMinDepth` (Syzygy probing depends on TCEC's 7-man
tables and I/O, not reproducible with local 3-4-5; and its default 1 sits on
its lowest bound) and `StaleDepthPerSearch` (a TT victim-policy constant:
decision 23 tests TT policy at a hash scaled to TCEC's pressure, not at
Hash 16).

**Ambiguity:** R24 puts "LMR (now sub-ply)" in the STC pass and "the LMR
divisor" in the LTC pass. This design follows the explicit LTC list
(`LmrDivisorTenths` at LTC; `LmrMinDepth`, `LmrMinMove`,
`LmrCorrectionStrength` at STC). Owner to confirm.

## 3. The parameters, current values, proposed ranges and the floor check

"Start" is R14's value where R14 tuned it (assumed adopted), else the phase-4
default. `c` is R14's calibrated value where one exists (spsa-r14.json, from
spsa_calibrate.py on e5dbaab); for the rest it is set at step 19 by
spsa_calibrate.py's rule (default +- c changes the rule's bench firing count
by 10%, at 1, 2, 4 or 8 table steps) and is **a placeholder here, at least 1**
(spsa.py refuses c < 1). **Flag** marks a start within about 2c of a bound
(at most one c of travel before the floor `lowest + c` or the ceiling
`highest − c`), or a parameter already pinned.

### 3.1 Class (a): STC pass

| parameter | start | range now | step | c | room to floor / ceiling (in c) | flag and proposal |
|---|---|---|---|---|---|---|
| AspirationMinDepth | 5 | 2-10 | 1 | ? (>= 1) | 3 / 5 at c = 1 | ok at c = 1 |
| AspirationHalfWidth | 12 | **8-40 (was 6-24)** | 1 | 1.0 | 4 / 28 | ok; **range 8-40, the owner's decision (2026-11-12, about 8:50 AM EST, the staleness audit)**: the default stays 12 with no SPRT (R14's SPSA kept 12 within a range topped at 24, and game evidence outranks the audit's offline re-measure of 29); the range now holds the re-measured 29 well inside, so the SPSA can reach it |
| RfpMaxDepth | 6 | 3-12 | 1 | ? | 3 / 6 | ok at c = 1 |
| **RfpMargin** | 55 | 30-160 (was 40-160) | 6 | 15 | **1.0 (pinned)** / 7 | **lowest 30 (owner, 2026-11-09): floor 30 + c; at c = 15 the floor is 45.** Since c is recalibrated at step 19, the floor target (about 45) fixes lowest = 45 − c_new if c changes |
| NullMinDepth | 3 | 1-6 | 1 | ? | 2 / 3 at c = 1 | **flag**; lowest is already the rule's floor for depths (1), so no widening; a pin is resolved by a head-to-head of 2 against 3 (design R tooling) |
| NullSurplusPerPly | 301 | 150-600 | 23 | 7.8 | 19 / 38 | ok |
| NullSurplusPliesMax | 2 | 0-6 (was 0-4) | 1 | ? | 2 / 2 at c = 1 | **flag both sides**; lowest 0 is the counts' floor; highest 6 (beyond the rule's "twice"; **applied, owner 2026-11-09**) |
| LmrMinDepth | 3 | 1-6 | 1 | ? | 2 / 3 | **flag**; lowest at the depth floor; head-to-head if pinned |
| LmrMinMove | 4 | 1-8 (was 2-8) | 1 | ? | 2 / 4 | **flag**; lowest 1 (the rule's half is 2; **applied, owner 2026-11-09**; 1 searches exactly as 2, see the status note) |
| LmrCorrectionStrength | 64 | 0-128 | 6 | ? | wide | ok |
| LmpMaxDepth | 4 | 1-8 (was 2-8) | 1 | ? | 2 / 4 | **flag**; lowest 1 (**applied, owner 2026-11-09**) |
| **LmpQuietAllowance** | 8 | 3-24 (was 6-24) | 1 | 1.7 | **1.2 (pinned in R14 at 7.7)** / 9 | **lowest 3, applied (owner, 2026-11-09)** (floor 4.7 at c = 1.7; the rule `quiets_searched >= LmpQuietAllowance + depth`, searcher.cpp, stays meaningful: at least 4 quiets at depth 1) |
| FutilityMaxDepth | 6 | 3-12 | 1 | ? | 3 / 6 | ok |
| **FutilityOffset** | 86 | 30-200 (was 50-200) | 8 | 18.2 | **2.0 (still falling)** / 6.3 | **lowest 30, applied (owner, 2026-11-09)** (floor 48 at c = 18.2) |
| **FutilityGrowth** | 50 | 25-140 (was 35-140) | 5 | 7.5 | **2.0 (still falling)** / 12 | **lowest 25, applied (owner, 2026-11-09)** (floor 32.5) |
| SeePruneMaxDepth | 6 | 3-12 | 1 | ? | 3 / 6 | ok |
| QuietSeeFloor | 60 | 30-120 | 5 | 22.5 (the range cap: insensitive, 8.6% at 6 steps) | 1.3 / 2.7 | **flag**; left out again (as in R14, by B7 rule 7) unless spsa_calibrate finds it sensitive on the post-round engine |
| CaptureSeeFloor | 118 | 50-200 | 8 | 28 | 2.4 / 2.9 | marginal, ok |
| HistoryBonusFactor | 25 | 12-50 | 2 | ? | 6.5 / 12.5 at c = 2 | ok |
| HistoryBonusCap | 1250 | 625-2500 | 94 | ? | wide | ok (its range is tied to the history scale by tests/test_params.cpp) |
| ReplyWeight | 6 | 0-12 (was 0-8) | 1 | ? | 6 / **2** | **flag ceiling**; highest 12 (the rule's twice), **applied (owner, 2026-11-09) after the int16 headroom check: no overflow** (the status note; tests/test_ordering.cpp). **2026-11-12 (owner, the staleness audit's re-measure 8):** the range already holds 8 strictly inside (4 steps below the ceiling), so it is unchanged; widening it would break the checked property that one reply entry alone fits int16 unclamped |
| FollowWeight | 4 | **0-16 (was 0-8)** | 1 | ? | 4 / 12 | ok; **highest 16, the owner's decision (2026-11-12, about 8:50 AM EST, the staleness audit)**: the audit re-measured 8, the old ceiling; 16 is the ranges rule's twice of 8, so 8 lies strictly inside (the default stays 4). The int16 headroom (the status note) holds: HistoryMax × (4 + 12 + 16) / 4 = 80,000, exact in int and clamped before the store; one follow entry alone at 16 (40,000) reaches the clamp, which the selector applies to any sum with a pair table (tests/test_ordering.cpp) |
| TakeWeight | 4 | 0-16 | 1 | ? | 4 / 12 | ok (capture scores are int16: move_selector.cpp line 83's bound). **2026-11-12 (owner, the staleness audit's re-measure 2):** 2 lies strictly inside, 2 steps above the floor 0, the weight's natural floor (a negative weight would invert the history), so the range is unchanged |
| HistorySkipPerPly | 700 | 350-4000 | 183 | ? | 1.9 / 18 at c = 183 (one step) | **flag**: floor within 2c at one step (350 is the ranges rule's half of 700); the ceiling 4000, kept from the candidates' declared range, is beyond the rule's twice (1400): step 19's range check decides both (added 2026-11-12, the history skip's adoption) |
| HistorySkipMaxDepth | 3 | 1-6 | 1 | ? | 2 / 3 at c = 1 | **flag**; lowest at the depth floor (added 2026-11-12; a placeholder never measured on its own, so this pass is its measurement) |
| MinorDriftShare | 32 | **16-64 (was 32-128)** | 5 | ? | 3.2 / 6.4 at c = 5 (one step) | ok; **range 16-64, the owner's decision (2026-11-12, about 8:45 AM EST)**: the ranges rule's half to twice of the adopted 32, centred on it, replacing the range declared for the natural value 64, whose floor 32 was (added 2026-11-12, the minor drift table's adoption) |
| DriftLimit | 300 | 150-600 | 23 | ? | 6.5 / 13 at c = 23 (one step) | ok (added 2026-11-12 with the minor table; it applies to every drift table, so only the minor table's while the others are off) |

p = 22 tuned parameters (23 with QuietSeeFloor), minus any parameter of a
feature removed in step 18 (e.g. LMP's two if LMP is removed), plus the
constants of step 12's adoptions (each placed in (a) or (b) by the same
rule). R24's optional parametrisation (margins as shapes K·sigma_d from X10,
the margin multiplier m of M4, the malus ratio of S8b, razoring and
bad-capture futility as "off-equivalent" dimensions, the history malus
balance of decision 20) needs new parameters in the table (code, names to
screen); **owner decision** whether any is added before step 19. Without
them, the pass tunes the table as it stands. **2026-11-10 (owner): batch 4's
horizon drop (razoring: HorizonDropMargin, HorizonDropMaxDepth) and bad-capture
stop (BadCaptureStopMargin) are added as dimensions of the final retune's SPSA**
(dropped as standalone tests; their switches and an off-equivalent range are
set when step 19 is prepared, with the names and constants screened then).
**2026-11-11 (owner, about 7:45 PM EST): a constant the final retune will
tune gets no head-to-head before it**: one design R SPRT at STC at its
natural value against off, adopted if it passes (pre-approved), one retry
at a second value if it fails (the two-try limit); head-to-heads stay only
for constants that will not be retuned or values that differ in kind. So
the engine survey's **PriorCreditQuarters** (D9, natural value 4 quarters,
range 0-12, step 1 in the parameter table) and **DirectCheckBonus** (D13,
natural value 5000, range 0-20000, step 1000) **become class (a)
dimensions of this SPSA if they are adopted** (lane B items 69a/69b and
70a/70b, gated behind E1). D8 (the summed pair update) has no constant.
**2026-11-12: quiet history pruning's two constants join this pass** on its
adoption (the history skip, T24/B13; qhp-stc +6.04 ± 4.37 Elo at STC,
design R [0, 6]; DESIGN.md "Search constants"): `HistorySkipPerPly` (700,
the head-to-head's pick) and `HistorySkipMaxDepth` (3), class (a) because
the skip acts only at depths 1-3 (the rows above), so p grows by 2.
**2026-11-12: the minor drift table's two constants join this pass** on
its adoption (tier 2, E4; corr-minor-retry +5.57 ± 4.01 Elo at STC, design
R [0, 6]; DESIGN.md "Search constants"): `MinorDriftShare` (32/64, the
retry's share, the natural 64 having failed) and `DriftLimit` (300 cp, as
shipped). Class (a): the term changes the eval the pruning steps (RFP,
futility, the null move's gate) and the quiescence stand-pat use, and in
the offline diagnosis of 2026-11-12 half of the node visits where it is
read were quiescence nodes and most others depths 1-2. So p grows by 2
more. The learning weights (`DriftWeightCap`, `DriftWeightTotal`) stay out
(E5's follow-up measures the update rule).
**2026-11-12: D8, the summed pair-table update, adopted with no constant**
(survey-d8-stc +4.29 ± 3.46 Elo at STC, design R [0, 6]; DESIGN.md
"Search constants"), so p is unchanged. `ReplyWeight` and `FollowWeight`
(class (a) above) are tuned with the rule in place. The int16 headroom
check above still holds: `apply_from_sum` clamps each entry to
±HistoryMax.

### 3.2 Class (b): LTC pass

| parameter | start | range now | step | c | room | flag and proposal |
|---|---|---|---|---|---|---|
| SingularMinDepth | 6 | 3-12 (was 4-12) | 1 | ? | 2 / 6 | **flag**; lowest 3 (the rule's half; **applied, owner 2026-11-09**) |
| SingularEntrySlack | 3 | 0-6 | 1 | ? | 3 / 3 | ok at c = 1 |
| **SingularMarginPerPly** | 6 (22 if the SPRT below passes) | 2-12 (was 3-12); 2-44 on the SPRT's test commit | 1 | ? | 3 / 6 at c = 1; 1.5 at c = 2 | **flag**: O5 and R28 predicted a lower margin at LTC (SE precision rose with depth on S512, 0.91 at d6 to 0.97-0.98 at d7-12); lowest 2 (**applied, owner 2026-11-09**). **2026-11-12: a class (b) dimension either way (owner)**; T27's rule 1 re-run on r8brft1 now picks 22 (the note below), so the highest bound must reach past 22 whatever the SPRT says: step 19's range check sets highest 44 (the rule's twice of 22) |
| NoMoveReduceMinDepth | 8 | 2-16 (was 2-10) | 1 | ? | 6 / **2** | **flag ceiling**; highest 16 (the rule's twice; **applied, owner 2026-11-09**) |
| LmrDivisorTenths | 45 | 23-90 | 3 | ? | 7 / 15 steps | ok |
| CaptureProbeMinDepth | 9 | 4-18 | 1 | ? | 5 / 9 at c = 1 | ok (added 2026-11-11, ProbCut's adoption) |
| CaptureProbeReduction | 5 | 2-10 | 1 | ? | 3 / 5 at c = 1 | ok (added 2026-11-11) |
| CaptureProbeMargin | 80 | 40-160 | 6 | ? | 6.7 / 13.3 steps | ok (added 2026-11-11) |

p = 8 (9 with a double-extension limit if R28 is adopted). **2026-11-11: ProbCut's three constants join this pass**
on its adoption (the efficiency rule: a constant the final retune will tune is not tuned again before it). They are
class (b): ProbCut acts only at depth 9 and beyond, its STC SPRT on S512r2 ended H0 and its LTC design R test on
the tuned search passed (+9.40 ± 5.03 Elo; DESIGN.md "Search constants"), so STC is the wrong place to tune them.
Ranges as in the parameter table (src/tune/params.hpp); c is set at step 19 by spsa_calibrate.py.

**2026-11-12 (owner, about 7:20 AM EST): `SingularMarginPerPly` stays a class (b) dimension of this pass either
way.** Builder 3's C6 measurement (tier2/c6-singular-measure b71199d, on phase-4 32384e1's search and the current
net r8brft1; 5,600 nodes, 800 per depth 6-12) found that T27's own rule 1 now picks 22 cp per ply, against the
6 it picked on S512 in October: at 22 every depth 6-12 keeps 0.92-1.00 of its flagged moves strictly best at full
depth, at 20 depth 12 gives 0.88, at 6 depths 9-12 give 0.85-0.88. So the margin moved the other way from O5's and
R28's prediction (the "lower at LTC" flag above is from the S512 data). The owner ordered one design R SPRT of 22
against 6 on phase-4 75d53f0 (STC, then LTC 40+0.4 on a pass; adoption pre-approved on a pass; branches
tier2/singular-margin-22 and sprt/singular-margin-22, lane A items 15c and 15d). Its start here is 22 if that SPRT
passes, else 6; either way p stays 8 (it is already one of the 8) and the highest bound is raised to 44 when step 19
is prepared, so the start and the measured value both lie well inside the range.

### 3.3 Widening is a rule exception

**All eleven widenings are the owner's (2026-11-09) and applied**, and so are the three range changes of 2026-11-12 (§3.1: AspirationHalfWidth 8-40, FollowWeight 0-16, MinorDriftShare 16-64; the staleness audit and the minor table's adoption). Each breaks DESIGN.md §5.2's "about half to twice the default"
range rule as RfpMargin's does; the bounds are tuner limits only ("never
played as such"), and changing them changes no played value (bench
unchanged; tests/test_params.cpp needs only the default inside the range and
the step within it). Each table step is kept unchanged, so c calibrated in
table steps stays comparable.

An alternative fix in the tool (perturbed values clipped at the bound while
theta may reach it) biases the gradient near the bound; not recommended.

**Tooling (built 2026-11-09, owner's decision; branch tune/spsa-pinned):**
`spsa.py report` prints "pinned at a bound" for a parameter whose theta lies
at its reachable floor `lowest + c` or ceiling `highest − c` (c of the next
iteration, as the update clamps it; within c / 100, above the log's
3-decimal rounding) in at least a third of the updates (rounded up), or in
the last one; it names the side, the bound, the count and whether the last
update is at it, and final.json lists the pins. The "step-limited" flag is
kept. On spsa-r14-m2 it flags RfpMargin (floor 55, 10 of 13 updates, at the
end) and LmpQuietAllowance (floor 7.7, 6 of 13, at the end), and not
FutilityOffset (last 81.6, floor 68.2) or FutilityGrowth (lowest 49.1, floor
42.5), which were falling but never reached their floors.

## 4. Iterations, games and gains

Both passes use spsa.py's rules as R14 did (Spall's gain sequences with
alpha 0.602; c held fixed; each step clamped to 0.5 c; the mean of the last
30% of the updates; the stationary-loss budget 0.5 Elo; A at most 10% of the
pairs).

| | STC pass, class (a) | LTC pass, class (b) |
|---|---|---|
| spec name | `spsa-r24-stc` (placeholder) | `spsa-r24-ltc` (placeholder) |
| p | about 22 | about 5 |
| tc, hash | 8+0.08, 16 MB | 40+0.4, 64 MB (the LTC stage's) |
| games per iteration | 1,600 (16 shards x 50 pairs) | 1,664 (16 x 52 pairs) |
| iterations | 20-25 (32,000-40,000 games; R24 and O10: 30-40k) | 5-7 (8,320-11,648 games; R24: 8-12k) |
| pair_sd | 0.21 (R14's, A3 §2.5) | **0.19-0.20, a placeholder**: computed here from tm-r8-ltc's pentanomial [15, 561, 1,214, 674, 32] (0.188) and ltc-iir-on-vs-off's last [7, 164, 389, 244, 28] (0.199) |
| gain_end | 16 x 0.5 x (ln 10 / 1600) / (p sd^2), by spsa.py | the same formula |
| openings | the tuning reserve from line 2,010,401 (R14 used 2,000,001-2,010,400) | after the STC pass's last line |

The reserve (lines 2,000,001-2,632,036) holds 632,036 pairs; both passes use
about 26,000. spsa.py checks only that a run lies inside the reserve, not that
it misses earlier runs' lines, so each spec's `opening_reserve` is set by hand
past the previous run and recorded (read from resolve_spec; a cross-run check
is a possible tooling addition).

**The LTC pass runs only if** the STC pass's validation does not end H0
(R24's kill: "STC H0, then skip the LTC pass"), and O5's precondition (the
group plausibly holds at least 5 Elo) is judged by the owner at that point
from: whether R28 or R20 changed the depth constants, the singular and
multi-cut LTC confirmations (running now), and the class (b) constants'
history (all set by Phase 3/4 ladders, never by SPSA).

## 5. Validation (DESIGN.md "SPSA on GitHub", B7 O6)

1. **The tuned values are committed as defaults** (bench updated, the
   constants table's rows citing the SPSA log and the SPRT, **the constant
   screen before the commit**: SPSA outputs can land on famous values, as
   RfpMargin 45 did, a near match credited in ORIGINALITY.md and kept by the
   owner).
2. **STC pass:** an STC SPRT, tuned against the engine entering step 19,
   fresh openings; R14's ran on design R ([0, 6], beta 0.2) by its driver log,
   while the tune/spsa DESIGN text says [0, 5] at alpha = beta = 0.05 with a
   cap of 6. **Owner to pick one for both passes** (this design uses design
   R, as R14 actually ran). Then an LTC sign guard: 3 fixed stages at 40+0.4,
   passed if the nElo estimate is above 0.
3. **LTC pass:** an LTC SPRT of the LTC-tuned values against the STC pass's
   result, design R at 40+0.4 (cap 4-6).
4. **VLTC spot check** (decision 21): the final engine against the engine
   entering step 19, **120+1.2, 2 stages**, Hash 192-256 MB (a placeholder,
   scaling LTC's 64 MB with the time), fresh openings. sprt_run.sh's kinds
   accept only 8+0.08 and 40+0.4, so it runs in the positional form (stages
   0-1). **Declared rule: a non-regression rule (owner, 2026-11-09),**
   replacing this design's "above −1 SE": **pass if the nElo estimate of the
   2 stages' summed pentanomial (sprt_merge.py's `nelo`, the "nElo:"
   figure) is at or above −3**, the lower edge of the Testing setup's
   non-regression bounds [−3, 0]; the estimate is reported with its 95%
   interval. Why this form: it reads the same edge as the non-regression
   early-acceptance rule, but on the point estimate, because at 2 stages the
   interval cannot clear −3 (its half-width is about 12 nElo: 17.02 / √2),
   and a sequential [−3, 0] SPRT would need tens of VLTC stages (the LLR
   drifts about 0.06 per stage at a true 0). Its operating points at the
   2-stage SE of 6.1 nElo (8.68 / √2; my arithmetic, normal approximation):
   P(pass) about 0.90 at a true +5, 0.69 at 0, 0.50 at −3, 0.31 at −6, 0.13
   at −10. So a fail is a warning, not a verdict: it goes to the owner, with
   two declared options, (a) revert the LTC pass's values (the
   depth-sensitive ones) and keep the STC pass's, or (b) one extension by 2
   more stages, judged once on the 4-stage sum by the same rule (SE 4.3).
   The midpoint rule (pass if the LLR for [−3, 0] is positive, i.e. the
   estimate above −1.5) was considered and not chosen: it fails a true 0 in
   40% of checks. A VLTC stage is about 3 LTC stages of
   time (R24; LTC stages took 80-83 minutes in tm-r8-ltc, so about 4-4.2 hours,
   UNVERIFIED), near sprt.yml's 300-minute shard limit: split each stage into
   two half-stage runs of 800 games if the first one's shard times exceed 240
   minutes.

## 6. Order relative to the factorial round

**Retune after the round, as ordered (18 then 19).** Removing a feature moves
the optimum of the parameters around it (LMP's, futility's), and a removed
feature's parameters must not be tuned. The round itself runs on the engine
with R14's values (if adopted), so its estimates are made near the tuned
margins, not the bootstrap-era ones. Also before step 19: the structure-class
calibration (step 17), which changes evaluations in its classes and so the
eval-gated margins; the three owed LTC confirmations (singular extension,
multi-cut, take history; queued 2026-11-08); and R14's own LTC sign guard.

## 7. Cost

| part | GitHub time (UNVERIFIED) | stage-equivalents |
|---|---|---|
| STC pass, 20-25 iterations at 16.5-17.3 minutes (R14's iterations, driver log) | 5.7-7.2 h | 20-25 |
| STC validation SPRT | 0.3-2.4 h | 1-8 |
| LTC sign guard, 3 stages at 80-83 minutes | 4.1 h | 12 |
| LTC pass, 5-7 iterations of about 82 minutes | 6.8-9.6 h | 20-28 |
| LTC validation, design R cap 4-6 | 5.5-8.3 h | 16-24 |
| VLTC spot check, 2 stages | about 8-8.5 h | about 24 |
| **total** | **about 30-40 h** (R24 and the order: about 22-26 h plus validation and the VLTC check) | **about 93-121** |

Engineering: the bounds change (params.hpp, a one-line edit per parameter,
bench unchanged) and the pinned-at-bound report line, **both done
2026-11-09**; still to do at step 19: two spec files and c calibration on the
post-round engine (spsa_calibrate.py, minutes of local CPU). **The spec files
(`spsa-r24-stc.json`, `spsa-r24-ltc.json`, placeholder names) are not
written now:** their parameter lists depend on step 18's removals, their c
values on the calibration of the post-round engine and their openings on the
runs before them; when written, each `lowest` / `highest` is the table's
(spsa.py refuses a spec bound outside the table's range, and by default
takes the table's).

## 8. Decisions needed from the owner

1. Confirm R14's adoption (its STC SPRT passed; LTC sign guard pending), so
   the starts above hold. **Settled (owner, 2026-11-09): adopted on
   phase-4.**
2. The widenings beyond RfpMargin's: LmpQuietAllowance (lowest 3),
   FutilityOffset (30), FutilityGrowth (25), SingularMarginPerPly (2),
   SingularMinDepth (3), NoMoveReduceMinDepth (highest 16), ReplyWeight
   (highest 12, after a headroom check), NullSurplusPliesMax (highest 6),
   LmrMinMove (lowest 1), LmpMaxDepth (lowest 1). **Decided (owner,
   2026-11-09): all applied**, ReplyWeight after its check (no overflow).
3. RfpMargin's floor: lowest fixed at 30 (floor 30 + c), or lowest set to
   45 − c once c is recalibrated (floor exactly 45). **Decided (owner,
   2026-11-09): lowest 30, applied.**
4. `LmrDivisorTenths` in the LTC pass (R24's explicit list) or the STC pass.
5. The validation SPRT's design (design R as R14 ran, or [0, 5] at alpha =
   beta = 0.05 as the tune/spsa text says).
6. Whether R24's new dimensions (shapes, multiplier, malus ratio, demoted
   batch-4 features) are added before step 19.
7. The VLTC pass rule (above −1 SE) and its hash. **Rule decided (owner,
   2026-11-09): a non-regression rule, defined in §5 item 4 (estimate at or
   above −3 nElo); the hash is still open.** Decisions 4, 5 and 6 are still
   open.

## 9. Names and constants for the screens (none screened yet)

New bounds (lowest/highest values above; applied 2026-11-09, justified by
the floor check of §3: each gives at least about one c of room below the
start); the VLTC rule's −3 nElo threshold (the Testing setup's
non-regression edge, not new); the pinned flag's c / 100 tolerance; the spec names `spsa-r24-stc` and
`spsa-r24-ltc`; the LTC pair_sd 0.19-0.20 (Fork's own measurement, computed
here); the VLTC hash; the iteration counts; the "pinned at a bound" one-third
rule. Every tuned output value goes through the constant screen before its
commit (decision recorded for R14's values: "SPSA tuned values screened
clean", ded0f82).

## 10. Prior art (concept level)

SPSA: Spall (1992, IEEE TAC 37(3)) and Spall (1998, IEEE TAES 34(3)), as cited
in spsa.py. Tuning by the condition that matters (VLTC tunes failing STC and
passing at long time controls) is the think tank's reading of public
test-framework records (S1 §4, O5). No engine's parameter values or ranges are
used.

## 11. Unverified items

- Every wall time above except R14's measured iteration times and the
  measured LTC stage times.
- The LTC pair_sd at SPSA conditions (computed from two SPRTs' pentanomials,
  which include a real effect).
- Whether a VLTC stage fits sprt.yml's 300-minute shard limit.
- ~~ReplyWeight's int16 headroom at 12.~~ Checked 2026-11-09: no overflow
  (the status note; tests/test_ordering.cpp).
- The size of the gain (R24: +1 to +5, central +3; the R14 result, +37.93 ±
  10.03 Elo at STC, suggests the early pass found much more than predicted,
  +2 to +7 for R14, so the remaining headroom is UNVERIFIED either way).
