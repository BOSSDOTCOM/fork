# Vision step 0: the calibrated residual pass and the head-routing refits (ideas.md 185; 2026-11-14/15)

> **Numbering note (coordinator, 2026-11-15):** this report uses the idea numbers first assigned to the vision ideas (185-198). ideas.md already held an idea 185 (the time scale's deep-depth clamp), so the vision ideas were renumbered by one there: step 0 is idea **186**, the routed heads 187, the auxiliary targets 188, the pinned-piece rows 189, the KK rows 190, defence surplus / attack balance 191, material ordinals 192, the file-line state 193, the king-zone lane 194, next-move double threats 195, the blockade occupant 196, trapped pieces / back rank 197, the Lichess puzzle diagnostic 198 and the sparse head 199. Read every idea number below as one higher.

Owner's order (2026-11-14, about 11:40 PM EST; DESIGN.md decisions log): "(1) run step 0 now (CPU, low priority
beside data generation): calibrate the residual kill line on known winners, the slider-vs-pawn/knight test for
x_lower, the full family panel, and the head-routing refits; report before anything else is built". The spec is
docs/research/vision-ideas-2026-11-14.md §2 (lens 2's L2-4, lens 3's F0, lens 1's CPU pass; Appendix A's L1-1 and
L1-2, Appendix D's idea 4). Measurement only: no engine or trainer change, no training, no adoption, nothing pushed.
Branch research/vision-step0 (from phase-4 91b17c0), local. Scripts in docs/research/vision-step0-2026-11-14/.
CPU only, every process at below-normal priority, at most 3 threads, beside g4d's data generation (not touched).
Times EST.

## Summary

| Question | Result | What it decides (the vision file's gates) |
|---|---|---|
| (a) Do Fork's known winners clear idea 175's 0.5% line? | **Mostly no.** On their pre-input nets, g4c (600,000 positions), by square / pooled / by bucket: the full exposure plane (S512r2) **0.61 / 0.79 / 0.85%**; x_lower's state (r3pp1) **0.15 / 0.27 / 0.29%**; the 608 pawn links (S512r2) **0.018 / 0.018 / 0.13%**. On g4s2-val all three are under 0.5% in every design. | **Idea 175's 0.5% line does not stand.** It would have killed x_lower (+17.6 FN) and the links (+46.1 FN, Fork's best input). The share does not rank winners by game value (links < x_lower < exposure; their FN gains run the other way), so no single line calibrates it. Implied lines (half the smaller winner, g4c): **0.009% by square or pooled, 0.066% by bucket** with the links; **0.077 / 0.133 / 0.144%** with the threat winners only. |
| Injected effect recovered? | Yes, under-read, never over-read: 0.50% injected into x_lower's mover cells reads 0.500% by square (its own share is 0.039%), 0.10% reads 0.125%; recovery (net of the family's own share) 71-93% for x_lower, the exposure plane and pins, 51-59% for the material cells and the 2,048-cell king pair (7 checks) | The tool sees effects of the size the winners show; a null is a null at about 0.01% (by square) for most families |
| (b) Order test: slider vs pawn/knight attackers | **Slider half larger.** r3kr1, g4c, both sides: cheaper-slider 0.088 / 0.160 / 0.175% against cheaper-pawn-or-knight 0.042 / 0.099 / 0.109%, at half the prevalence (3.3% vs 6.5% of positions). On the mover's side 0.033 vs 0.003% by square. g4s2-val agrees in direction (pooled 0.069 vs 0.054%). | **Lens 3's premise holds**; ideas 188, 190 and 194 are not stopped by (b) |
| (c) Panel (ideas 188-196, two controls) | **Every family is under the threat-calibrated line, in every design, on both sets** (largest on r3kr1: material ordinals by bucket 0.064%, loose/overprotected by bucket 0.047%, king pair by bucket 0.039%, the mover's own discovery candidates 0.036%, under-defended mover pieces 0.034%, the mover's pins 0.030%). Against the links' line (0.009% by square or pooled) the mover's pins, under-defended pieces, discovery candidates, the material ordinals and a few others are above it on g4c, and only under-defended pieces replicate on g4s2-val. The opponent's next-move forks and discovery candidates against the mover (idea 194's exact family) read **0.001-0.003%**, null. Both predicted-null controls (absolute 7th, bad bishop) read null by square and pooled. | See §5: under the threat line every panel idea's step-0 gate fails; the KK rows (189) and the opponent's double threats (194) fail every line; the controls confirm the filter |
| (d) Head routings (r3kr1's body frozen) | **None beats phase.** The control (phase refit) is 0.35% below the shipped heads' loss on g4c (0.0102038 vs 0.0102400). Against it on g4c: wings +1.8e-6 ± 2.1e-6, column 858 (chosen on g4s2-val) +3.8e-6 ± 1.9e-6, progress octiles +1.08e-3 (11% worse), phase x progress halves (extra) +1.4e-6 ± 1.7e-6. On g4s2-val wings reads -4.0e-6 ± 1.7e-6 (the one reading past 2 SE, 0.02% of the loss, opposite in sign to g4c) and the column chosen on g4c +6.9e-6 ± 3.1e-6 | **Idea 186's three routings are killed at their CPU step on g4c**, the deciding set (L1-1's rule: lower than the control by more than 2 fold SEs); I do not read wings' g4s2-val reading as beating phase clearly, so no fixed-node screen is proposed (§6 says what one would need) |

The decision on the line is the owner's (the vision file §2 and L2-4: "the owner decides" whether idea 175's states
are re-read against a new line). §5 lists what each reading implies.

## 1. Data, nets, label and checks

- **Positions:** idea 175's two held-out sets, its own dumps (`fork-train dump`: the trainer's filter and
  side-to-move view; docs/research/idea175-screens.md §1): **g4c**, the first 600,000 kept positions of 8c's TD(0.9)
  copy `td90-g4c-w00.vf`; **g4s2-val**, the 103,254 positions of 8c's validation blend copy `bl-g4s2-val.vf`.
- **Label:** the trainer's target at result weight 0, sigmoid(score / 92) of the copy's score; residual
  r = label - sigmoid(y / (QA x QB)), y the net's integer output before the scale (idea 175's definition).
- **Nets:** r3kr1 (architecture 9, the default), r8brft1 (architecture 8, idea 175's net, for comparability),
  r3pp1 (architecture 8, x_lower's same-recipe control: r3xl1 against r3pp1 gave x_lower's +17.60 ± 8.69 at fixed
  nodes, sprt-log, run 43646858806) and S512r2 (architecture 2: the net the exposure plane, S512+X +25.67 ± 10.26
  FN, run 42142711426, and the pawn links, S512+PP +46.09 ± 10.37 FN and +32.67 ± 10.48 STC, runs 42284077960 and
  42294907752, were measured against; DESIGN.md decisions log 2026-11-05/06). Each winner is calibrated on the net
  it was added to (its "pre-input net"), and on r3kr1 and r8brft1 too.
- **Reproduction of idea 175:** r8brft1's residual variance 0.010679 (g4c) and 0.019886 (g4s2-val), and the base
  table's held-out share 0.026% and 0.018%, as idea175-screens.md reports (0.0107 / 0.0199; 0.026% / 0.018%).
- **Evaluation checks:** every net's numpy output equals models.py's integer reference (`r_int`) on every 500th
  position (1,200 g4c and 207 g4s2-val positions per net, 0 mismatches). r3kr1's equals the engine's `evalfens`
  (build/clang-release, r3kr1 embedded) on every 20th position (30,000 and 5,163, 0 mismatches); the same check
  reports 475-494 mismatches of 500 for the three nets the build does not embed, so it can fail.
- **Finder checks** (step0_features.py, every 50th position: 12,000 g4c and 2,066 g4s2-val), against oracles written
  apart from the finders, 0 mismatches each: x_lower and the full exposure rule against models.py's
  `exposed_lower_squares` / `exposed_squares`; pins against python-chess's `Board.is_pinned`; discovery candidates
  and queen pins against a removal oracle (lift the piece, look for a newly revealed slider attack); the defender
  counts behind loose, overprotected and under-defended against python-chess's `Board.attackers`. **Fork's own
  `Position::pinned()` and `discoverers()`** (pins.cpp, a scratch program linked to build/clang-release's
  libforkcore.a; each position given with either side to move): 0 mismatches on 10,326 g4s2-val and 10,000 g4c
  positions, both sides each (step0_pins_cpp.py). The oracles fail when a finder is faulted: lone_shields without
  diagonals gives 70 pin, 12 discoverer and 1 queen-pin mismatches in 1,500 positions; one dropped under/loose cell
  gives 179 and 1,456.
- **Plies** (the progress target): the .vf games replayed and every record matched exactly to the next dump line:
  all 600,000 g4c positions (17,732 games) and all 103,254 g4s2-val positions (2,700 games, the set's documented
  count) matched (step0_plies.py).

## 2. Method (idea 175's study, extended)

step0_study.py keeps idea 175's design (tools/nnue/state_rows_study.py on proto/i175-state-rows): a family's
additive table (one column per cell) beside the base table (768 mover-relative colour x kind x square columns),
ridge least squares on r minus the training folds' mean, blocks of 2,000 consecutive positions, block b in fold
b mod 8, each fold predicted from the other seven, the base's ridge strength chosen alone, then the family's with the
base's kept; share = (held-out SSE of base - of base + family) / held-out sum of squares of r, pooled over folds, ±
the standard error of the 8 per-fold shares (a 95% interval is about ± 2.4 SE with 7 degrees of freedom). Three
designs per family: **by square** (idea 175's headline: side x kind x state x square), **pooled** (one column per
side x kind x state, holding the count) and **by bucket** (pooled x the net's 8 output buckets: the state-by-phase
table L2-4 asked for). Families with cells on both sides are measured for the mover's cells, the opponent's and
both. Two changes from idea 175's script, both stated in its docstring: the family's ridge grid runs to 1e7 as the
base's does (idea 175's stopped at 1e5), so a redundant family shrinks to nothing; and the centring uses each
column's sum, which is right for the pooled count columns (idea 175's used the Gram diagonal, exact only for 0/1
columns). The four nets share one bucket table (checked: identical buckets on every position).

Each family's definition is in step0_common.py's docstring (written from the concepts, with python-chess's attack
tables; pseudo-attacks on the occupancy, as the exposure rules use). In short: **xl** x_lower's state; **xpn/xsl**
x_lower split by the cheaper attacker (pawn or knight / bishop or rook); **xx** the full exposure plane (XGR's rule);
**pin** absolute pins; **pinq** pins to the own queen by an enemy bishop or rook; **disc** discovery candidates
(Fork's discoverers rule); **forkn** a side's safe knight fork squares (two of K, Q, R or undefended minors);
**forkp** pawn-push forks; **under** attacked twice or more, defended at most once, not exposed; **file** a rook's or
queen's first piece forward on its file (own heavy, enemy heavy, none); **block** a passer's stop-square occupant;
**loose** no defender / defenders - attackers >= 2; **kk** the king pair (32 x 64, mirrored); **mat** the material
thermometer (P >= 1..8, N/B/R >= 1..3, Q >= 1..2 per side) plus both bishop pairs and opposite bishops; **trap**
lens 3's d_mob rule (no destination not own-occupied and not pawn-attacked), **trapa** the same and attacked;
**back** the back-rank precondition; **sev** a rook on the 7th with the enemy king on the 8th; **bad** rammed own
pawns on the bishop's colour; **links** S512+PP's 608 links of both perspectives (tools/nnue/contacts.py).

**Injected-effect check** (`--inject`, r3kr1, g4c): a fixed random value per by-square cell of the family's side,
summed over a position's cells and scaled to a known share of r's variance (added on top of the family's own share):

| Family (side) | Injected, % of the new variance | Recovered by square | pooled | by bucket | Its own share by square (no injection) |
|---|---|---|---|---|---|
| x_lower (mover) | 0.498 | 0.500 ± 0.016 | 0.049 | 0.068 | 0.039 |
| x_lower (mover) | 0.100 | 0.125 ± 0.010 | 0.047 | 0.064 | 0.039 |
| full exposure (opponent) | 0.200 | 0.359 ± 0.034 | 0.280 | 0.278 | 0.217 |
| pins (both) | 0.498 | 0.436 ± 0.031 | 0.133 | 0.137 | 0.000 |
| pins (both) | 0.100 | 0.079 ± 0.015 | 0.059 | 0.054 | 0.000 |
| material ordinals (both) | 0.498 | 0.282 ± 0.024 | 0.071 | 0.160 | 0.028 |
| king pair (both) | 0.498 | 0.292 ± 0.014 | 0.001 | 0.057 | 0.000 |

Net of the family's own share, the by-square design recovers 93% and 86% of the effect for x_lower, 71% for the
exposure plane's opponent cells, 88% and 79% for pins, 51% for the material cells (much of a random effect on them
is linear in the piece counts the base table already carries) and 59% for the king pair (2,048 cells, about 290
positions each: ridge shrinkage). Pooled designs see a random per-square effect only through
its mean, as expected. So the study under-reads, by up to about half for the material and king-pair tables, and never over-reads.

## 3. (a) Calibration on the known winners

Share of the held-out residual variance, %, ± fold SE (step0_tables.py from study-g4c.json and study-g4s2val.json;
every row of every net is in tables.md beside the scripts). "Pre-input" is the net the winner was added to.

| Winner (FN gain) | Net | Side | g4c by square | g4c pooled | g4c by bucket | g4s2-val by square | g4s2-val pooled | g4s2-val by bucket | positions with any |
|---|---|---|---|---|---|---|---|---|---|
| full exposure plane (+25.67) | S512r2 (pre-input) | both | **0.608 ± 0.036** | **0.790 ± 0.046** | **0.849 ± 0.059** | 0.082 ± 0.023 | 0.403 ± 0.082 | 0.433 ± 0.078 | 38.1% |
| | S512r2 | mover | 0.174 ± 0.015 | 0.227 ± 0.017 | 0.276 ± 0.018 | 0.035 ± 0.012 | 0.100 ± 0.024 | 0.152 ± 0.027 | 30.6% |
| | S512r2 | opponent | 0.334 ± 0.027 | 0.430 ± 0.033 | 0.442 ± 0.044 | 0.030 ± 0.025 | 0.196 ± 0.072 | 0.190 ± 0.053 | 14.4% |
| | r3kr1 | both | 0.379 ± 0.042 | 0.567 ± 0.050 | 0.590 ± 0.061 | 0.027 ± 0.023 | 0.264 ± 0.062 | 0.246 ± 0.060 | |
| | r3kr1 | mover / opponent | 0.100 / 0.217 | 0.146 / 0.314 | 0.171 / 0.313 | 0.017 / 0.006 | 0.063 / 0.146 | 0.084 / 0.126 | |
| | r8brft1 | both | 0.448 ± 0.042 | 0.640 ± 0.052 | 0.669 ± 0.055 | 0.058 ± 0.023 | 0.298 ± 0.068 | 0.291 ± 0.073 | |
| x_lower's state (+17.60) | r3pp1 (pre-input) | both | **0.154 ± 0.025** | **0.265 ± 0.024** | **0.287 ± 0.030** | 0.010 ± 0.007 | 0.130 ± 0.042 | 0.155 ± 0.060 | 9.5% |
| | r3pp1 | mover | 0.038 ± 0.009 | 0.056 ± 0.008 | 0.075 ± 0.009 | 0.004 ± 0.007 | 0.041 ± 0.015 | 0.081 ± 0.031 | 8.4% |
| | r3pp1 | opponent | 0.109 ± 0.023 | 0.187 ± 0.022 | 0.194 ± 0.032 | 0.010 ± 0.007 | 0.075 ± 0.034 | 0.065 ± 0.023 | 1.5% |
| | r3kr1 | both | 0.149 ± 0.025 | 0.255 ± 0.024 | 0.273 ± 0.031 | 0.008 ± 0.007 | 0.132 ± 0.039 | 0.155 ± 0.056 | |
| | r8brft1 | both | 0.179 ± 0.027 | 0.292 ± 0.027 | 0.313 ± 0.030 | 0.014 ± 0.007 | 0.138 ± 0.041 | 0.159 ± 0.055 | |
| the 608 pawn links (+46.09) | S512r2 (pre-input) | both perspectives | **0.018 ± 0.008** | **0.018 ± 0.009** | **0.132 ± 0.018** | 0.008 ± 0.011 | 0.000 ± 0.000 | 0.079 ± 0.014 | 89.8% |
| | r3kr1 (has the links) | both | 0.004 ± 0.003 | 0.004 ± 0.006 | 0.042 ± 0.005 | 0.003 ± 0.009 | 0.000 ± 0.000 | 0.030 ± 0.012 | |
| | r8brft1 (has the links) | both | 0.004 ± 0.003 | 0.002 ± 0.002 | 0.030 ± 0.006 | 0.004 ± 0.009 | 0.000 ± 0.002 | 0.023 ± 0.014 | |

**Reading.**
- **Idea 175's 0.5% line does not stand.** Of the three inputs Fork has measured as winners, only the full exposure
  plane clears 0.5% on its pre-input net, and only on g4c. x_lower reads 0.15-0.29% and the pawn links 0.018% (by
  square or pooled); on g4s2-val all three are below 0.5% in every design. Idea 175's best state (a bishop attacked by
  an enemy pawn, 0.032% by square on r8brft1, g4c) reads **above** the links' share on their own pre-input net.
- **The share does not rank winners by their game value.** Fixed-node gain: links +46.1 > exposure +25.7 >
  x_lower +17.6; share: exposure 0.61 > x_lower 0.15 > links 0.018. The two threat inputs read 10-50 times the links.
  A residual table sees relations the body cannot form at all (attacks through lines and negations, section 0 of
  lens 3), not structure the body forms imperfectly but improves with in training (the links: pawn pairs the
  quadratic form can reach, which an extra row still sharpened by +46). So one line cannot be calibrated for both
  kinds; the tool is a usable screen only for threat-like families, and a null on a structure family means little.
- **The implied lines** (half the smaller winner's share, as the vision file proposes), g4c:
  - with all three winners: **0.009%** by square, **0.009%** pooled, **0.066%** by bucket (the links set it; g4s2-val:
    0.004 / 0.000 / 0.040). At this line the links on r3kr1 itself, a family the net already holds, read 0.004 /
    0.004 / 0.042: the by-bucket design's floor for an absorbed family is about 0.04%.
  - with the threat winners only (x_lower the smaller): **0.077%** by square, **0.133%** pooled, **0.144%** by bucket
    (g4s2-val: 0.005 / 0.065 / 0.078).
- **The labels matter.** Every share is several times larger on g4c (TD(0.9) copy) than on g4s2-val (the blend copy,
  half the game result): the blend's result half adds variance the inputs cannot explain (r's variance 0.0193 against
  0.0102 for r3kr1). g4c is the deciding set; g4s2-val is the replication.
- **The exposure plane's share is mostly the opponent's pieces** (0.31% of r3kr1's 0.57% pooled), as idea 178's
  count study found (its mover part 0.25-0.45): the label's search sees the mover's coming captures.

## 4. (b) The order test: cheaper slider against cheaper pawn or knight

x_lower split by the attacker that makes a piece exposed (a piece can be in both). Knights and bishops can only be
attacked by a cheaper pawn, so the slider half covers rooks (attacked by a bishop) and queens (by a bishop or a rook)
only. r3kr1 (r3pp1 within 0.01 in every cell), %:

| Side | Attacker | g4c by square | g4c pooled | g4c by bucket | g4s2-val by square | g4s2-val pooled | g4s2-val by bucket | positions with any |
|---|---|---|---|---|---|---|---|---|
| both | cheaper pawn or knight | 0.042 ± 0.021 | 0.099 ± 0.013 | 0.109 ± 0.020 | 0.004 ± 0.004 | 0.054 ± 0.018 | 0.051 ± 0.023 | 6.5% |
| both | **cheaper slider** | **0.088 ± 0.017** | **0.160 ± 0.024** | **0.175 ± 0.030** | 0.000 ± 0.000 | 0.069 ± 0.033 | 0.095 ± 0.033 | 3.3% |
| both | x_lower (either) | 0.149 ± 0.025 | 0.255 ± 0.024 | 0.273 ± 0.031 | 0.008 ± 0.007 | 0.132 ± 0.039 | 0.155 ± 0.056 | 9.5% |
| mover | cheaper pawn or knight | 0.003 ± 0.001 | 0.013 ± 0.005 | 0.018 ± 0.006 | 0.002 ± 0.004 | 0.019 ± 0.011 | 0.027 ± 0.016 | 5.6% |
| mover | **cheaper slider** | **0.033 ± 0.006** | **0.044 ± 0.009** | **0.062 ± 0.009** | 0.000 ± 0.000 | 0.029 ± 0.008 | 0.064 ± 0.014 | 2.9% |
| opponent | cheaper pawn or knight | 0.054 ± 0.016 | 0.082 ± 0.012 | 0.090 ± 0.019 | 0.002 ± 0.005 | 0.032 ± 0.018 | 0.027 ± 0.010 | 1.1% |
| opponent | cheaper slider | 0.067 ± 0.022 | 0.110 ± 0.022 | 0.107 ± 0.029 | 0.007 ± 0.007 | 0.037 ± 0.029 | 0.033 ± 0.024 | 0.4% |

**Reading: the prediction holds.** At half the pawn/knight half's prevalence, the slider half carries 62% of the two
halves' summed share pooled (0.160 of 0.259) and 68% by square on g4c; on the mover's side (idea 178's and 188's side)
it carries 11 times the pawn/knight half by square (0.033 vs 0.003) and 3.4 times pooled. The pawn/knight half reads
like idea 175's pawn states (0.003% by square for the mover). g4s2-val agrees in direction for both sides pooled and
by bucket; its by-square cells are too thin (103,254 positions) to resolve either half.

## 5. (c) The panel (ideas 188-196) and the two controls

r3kr1, %, ± fold SE; prevalence on g4c ("positions with any" set cell, and set cells per position). The lines: idea
175's 0.5%; the threat line (half x_lower's share on r3pp1: g4c 0.077 by square, 0.133 pooled, 0.144 by bucket);
the links' line (0.009 / 0.009 / 0.066). r8brft1's panel is in tables.md (within about 0.01 of r3kr1's in every
cell, with no family closer to any line).

| Idea | Family | Side | positions with any | cells / position | g4c by square | g4c pooled | g4c by bucket | g4s2-val by square | g4s2-val pooled | g4s2-val by bucket | 0.5% | threat line | links' line |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 188 | pinned (absolute) | mover | 8.38% | 0.085 | 0.000 ± 0.000 | 0.030 ± 0.005 | 0.031 ± 0.006 | 0.008 ± 0.007 | 0.000 ± 0.000 | 0.000 ± 0.000 | below | below | above (pooled), g4c only |
| 188 | pinned (absolute) | opponent | 7.45% | 0.076 | 0.000 ± 0.000 | 0.001 ± 0.001 | 0.001 ± 0.001 | 0.007 ± 0.013 | 0.000 ± 0.000 | 0.000 ± 0.000 | below | below | below |
| 188 | pinned to the queen | mover | 1.63% | 0.016 | 0.001 ± 0.002 | 0.007 ± 0.002 | 0.009 ± 0.003 | 0.003 ± 0.012 | 0.011 ± 0.012 | 0.000 ± 0.000 | below | below | below |
| 188 | pinned to the queen | opponent | 1.40% | 0.014 | 0.001 ± 0.001 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | below | below | below |
| 194 | discovery candidates against the mover (the opponent's) | opponent | 1.39% | 0.014 | 0.000 ± 0.000 | 0.002 ± 0.002 | 0.001 ± 0.002 | 0.002 ± 0.003 | 0.000 ± 0.001 | 0.003 ± 0.007 | below | below | below |
| (contrast) | the mover's own discovery candidates | mover | 1.31% | 0.013 | 0.000 ± 0.000 | 0.027 ± 0.009 | 0.036 ± 0.010 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | below | below | above (pooled), g4c only |
| 194 | knight fork squares against the mover (the opponent's) | opponent | 3.68% | 0.040 | 0.000 ± 0.000 | 0.001 ± 0.001 | 0.003 ± 0.002 | 0.004 ± 0.004 | 0.000 ± 0.000 | 0.000 ± 0.000 | below | below | below |
| (contrast) | the mover's knight fork squares | mover | 3.32% | 0.036 | 0.008 ± 0.003 | 0.013 ± 0.006 | 0.018 ± 0.006 | 0.019 ± 0.014 | 0.004 ± 0.005 | 0.000 ± 0.000 | below | below | above (pooled), g4c only |
| 194 | pawn-push forks against the mover (the opponent's) | opponent | 0.58% | 0.006 | 0.001 ± 0.001 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.001 | 0.001 ± 0.006 | below | below | below |
| (contrast) | the mover's pawn-push forks | mover | 0.58% | 0.006 | 0.007 ± 0.003 | 0.007 ± 0.003 | 0.006 ± 0.004 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | below | below | below |
| 190 | under-defended, not exposed | mover | 8.04% | 0.084 | 0.034 ± 0.009 | 0.030 ± 0.005 | 0.026 ± 0.007 | 0.011 ± 0.017 | 0.037 ± 0.011 | 0.001 ± 0.004 | below | below | **above (square, pooled), both sets pooled** |
| 190 | under-defended, not exposed | opponent | 5.66% | 0.059 | 0.000 ± 0.001 | 0.000 ± 0.001 | 0.003 ± 0.003 | 0.003 ± 0.003 | 0.002 ± 0.007 | 0.006 ± 0.008 | below | below | below |
| 190 | loose / overprotected | both | 97.66% | 3.879 | 0.001 ± 0.001 | 0.007 ± 0.003 | 0.047 ± 0.008 | 0.000 ± 0.002 | 0.013 ± 0.011 | 0.023 ± 0.018 | below | below | below |
| 192 | file-line contact (R, Q) | mover | 43.88% | 0.498 | 0.000 ± 0.000 | 0.015 ± 0.003 | 0.022 ± 0.008 | 0.000 ± 0.000 | 0.010 ± 0.020 | 0.001 ± 0.002 | below | below | above (pooled), g4c only |
| 192 | file-line contact (R, Q) | opponent | 43.57% | 0.498 | 0.000 ± 0.001 | 0.004 ± 0.001 | 0.002 ± 0.002 | 0.000 ± 0.000 | 0.000 ± 0.003 | 0.000 ± 0.000 | below | below | below |
| 195 | blockade occupant of passers | both | 20.28% | 0.232 | 0.000 ± 0.000 | 0.015 ± 0.007 | 0.016 ± 0.005 | 0.037 ± 0.029 | 0.008 ± 0.006 | 0.005 ± 0.004 | below | below | above (pooled), g4c only |
| 189 | king pair (KK) | (one cell) | 100% | 1 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.039 ± 0.011 | 0.000 ± 0.000 | 0.005 ± 0.010 | 0.011 ± 0.015 | below | below | below |
| 191 | captured-material ordinals | both | 100% | 16.2 | 0.028 ± 0.009 | 0.018 ± 0.006 | 0.064 ± 0.008 | 0.001 ± 0.006 | 0.000 ± 0.000 | 0.021 ± 0.007 | below | below | above (square, pooled), g4c only |
| 196 | trapped (d_mob rule) | both | 13.73% | 0.194 | 0.007 ± 0.005 | 0.014 ± 0.004 | 0.021 ± 0.008 | 0.000 ± 0.000 | 0.003 ± 0.006 | 0.003 ± 0.003 | below | below | above (pooled), g4c only |
| 196 | trapped and attacked | both | 0.67% | 0.007 | 0.002 ± 0.002 | 0.007 ± 0.005 | 0.008 ± 0.007 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | below | below | below |
| 196 | back-rank weakness | both | 0.53% | 0.005 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.008 ± 0.016 | 0.015 ± 0.013 | 0.003 ± 0.004 | below | below | below |
| control | absolute 7th | both | 5.70% | 0.061 | 0.000 ± 0.001 | 0.001 ± 0.001 | 0.000 ± 0.001 | 0.009 ± 0.010 | 0.011 ± 0.015 | 0.000 ± 0.001 | below | below | below |
| control | bad bishop | both | 31.74% | 0.490 | 0.000 ± 0.000 | 0.005 ± 0.006 | 0.024 ± 0.007 | 0.030 ± 0.032 | 0.000 ± 0.000 | 0.000 ± 0.001 | below | below | below |

(Every side split of every family, and r8brft1's numbers, are in tables.md. Shares shown 0.000 ± 0.000 are fits the
ridge shrank to nothing.)

**Reading.**
- **Against the threat line, every panel family is below in every design, on both sets**, by a factor of 2.2 or more
  (the largest, the material ordinals by bucket, 0.064 against 0.144). Against idea 175's 0.5% line, by a factor of 7.8
  or more.
- **The mover's side carries what there is** (pins 0.030 against 0.001; under-defended 0.030 against 0.000; the
  mover's own discovery candidates and fork squares 0.027 and 0.013 against the opponent's 0.002 and 0.001), the
  reverse of the exposure plane (opponent-heavy).
- **Lens 3's next-move threats against the mover (idea 194's family) are null**: the opponent's fork squares,
  pawn-push forks and discovery candidates read 0.000-0.003% in every design, below every line. The label's search
  does not show them as a residual the net misses.
- **Against the links' line (0.009% pooled), seven families are above on g4c, and only one replicates on g4s2-val:**
  under-defended, not exposed mover pieces (0.030 g4c, 0.037 g4s2-val, pooled).
- **The controls behave as predicted**: the absolute 7th reads 0.000-0.001% on g4c, the bad bishop 0.000 by square
  and 0.005 pooled. The bad bishop's 0.024% by bucket, the king pair's 0.039%, loose/overprotected's 0.047% and the
  material ordinals' 0.064% are at the by-bucket design's floor (the links, already in r3kr1, read 0.042% by bucket):
  a count crossed with the phase picks up some phase-dependent material signal, whatever it counts. So section 0's
  filter (pair and low-rank concepts are learned) is not contradicted.
- **The blockade by endgame buckets 0-2 alone** (L2-2's extra reading) was not computed separately; its by-bucket
  table (every bucket at once) reads 0.016% (g4c) and 0.005% (g4s2-val).

**What each result decides** (each idea's step-0 gate as the vision file states it; the owner decides which line
applies):

| Idea | Its gate (vision file) | Under the threat line (half x_lower) | Under the links' line (half the links) |
|---|---|---|---|
| 188 pinned rows | F0 share under the calibrated line kills | **killed** (0.030 pooled vs 0.133) | survives on g4c (0.030 vs 0.009), not replicated on g4s2-val (0.000) |
| 189 KK rows | under one third of the calibrating family's share kills | **killed** (0.000 by square and pooled; injection shows the design sees ~58% of a 0.5% effect) | **killed** (0.000 vs a third of 0.018 = 0.006) |
| 190 defence surplus / attack balance | L2-3: under a third of x_lower's share; L3-3: under a quarter of the mover's exposure share, or under 0.5% | loose/overprotected **killed** (0.001 by square vs 0.050); under-defended **passes L3-3's relative part by square** (0.034 vs a quarter of the mover's exposure share, 0.100 / 4 = 0.025) but not pooled (0.030 vs 0.146 / 4 = 0.037), and **fails its 0.5% absolute part** and the threat line | under-defended survives on both sets (the only one); loose killed |
| 191 material ordinals | under one third of the calibrating family's share kills | **killed** (0.028 by square vs 0.050) | survives on g4c (0.028 vs 0.006), not on g4s2-val (0.001) |
| 192 file-line contact | under the calibrated line kills | **killed** (0.015 pooled, mover) | survives on g4c (pooled), not on g4s2-val |
| 194 next-move double threats | under 0.5% kills | **killed** (0.001-0.003) | **killed** |
| 195 blockade occupant | under the calibrated line in every bucket group kills | **killed** | survives on g4c pooled (0.015), not on g4s2-val (0.008, under 0.009) |
| 196 trapped / back rank | each under 0.5% kills; back rank expected null | **both killed**; back rank null as expected | trapped survives on g4c pooled (0.014); back rank killed |
| 193 king-zone lane | (not in the panel order) | not run | not run |
| controls | material shares would mean the filter is wrong | null: the filter stands | null |
| idea 175's states (re-read, as L2-4 asks) | | still below (best 0.032 by square, 0.090 pooled vs 0.077 / 0.133) | its attacked-by-a-pawn family (0.025 / 0.090) and passed pawn (0.012 / 0.019) would be above; idea 175 was also killed on speed (0.905-0.913 against 0.95), which this does not change |

My reading (not a decision): the share separates the two threat winners from everything else, but cannot see the
links, so the links' line is a line at the noise level of the design (the absorbed links read 0.004 pooled and 0.042
by bucket on r3kr1) and passes families that do not replicate. The threat line is the one the tool can support, and
under it the step-0 gates of ideas 188-196 all fail. Idea 178's own falsifier is relative (the mover's share against
the opponent's), as the vision file notes, so this does not decide 178.

## 6. (d) Head routings on r3kr1's frozen body

**Method** (step0_routing.py). The body is r3kr1's first layer, frozen: each position's 1,024 clipped hidden values
from step0_eval.py (the same numpy evaluation checked against the engine), so a head is z = x . u + c with
x = (v / QA)^2, Fork's integer formula in floats; r3kr1's own heads in this form give a held-out loss within 5e-8 of
the integer net's (0.01024001 against 0.01023996 on g4c; 0.01928346 against 0.01928343). **Loss**: the trainer's
(tools/train/src/main.rs: `output.sigmoid().squared_error(target)`), the squared error between sigmoid(z) and
sigmoid(score / 92), summed, plus a ridge term toward a start head (r3kr1's head for the cell's phase bucket; for the
progress routing, r3kr1's heads averaged by the cell's bucket mix), its strength chosen per routing from a grid by
the pooled held-out loss. **Fit**: the exact minimum of that objective, by Gauss-Newton steps (the matrix recomputed
at the current fit at iterations 3, 8, 16, 32 and 64) with step halving per head. Idea 82's probe
(tools/measure/head_probes.py on tools/probes-1111) minimised the same squared error by full-batch Adam with early
stopping; this replaces early stopping with ridge and an exact optimum. **Folds**: idea 175's 8 block folds, each
fold's loss from heads fitted on the other seven; ± is the standard error of the 8 per-fold differences to the phase
refit, and lens 1's kill rule is "not lower than the control by more than 2 fold SEs". **Learned routings are
chosen on the other set**: the progress score (ridge least squares of ply / final ply on the 768 mover-relative
piece-square cells; held-out R^2 0.686 on g4c when fitted on g4s2-val, 0.680 the other way) and its octile
boundaries; the hidden column (all 1,024 pre-ranked by the residual SSE a per-(bucket, v_j > 0) linear correction
a + b z0 removes, the top 8 refit on the other set at ridge 10, the best held-out loss kept: column 858 chosen on
g4s2-val for g4c, column 38 chosen on g4c for g4s2-val). Kings' wings: files a-d against e-h, same or opposite.

| Set | Routing | Heads | Held-out loss | Against the phase refit (8-fold mean ± SE) | Ridge | Iterations |
|---|---|---|---|---|---|---|
| g4c | r3kr1 as shipped (integer) | 8 | 0.0102400 | +3.61e-5 ± 4.8e-6 (the refit's own gain) | | |
| g4c | **phase (control, refit)** | 8 | **0.0102038** | 0 | 100 | 10 |
| g4c | progress octiles | 8 | 0.0112828 | **+1.08e-3 ± 2.0e-5** (10.6% worse) | 10 | 14 |
| g4c | phase x kings' wings | 16 | 0.0102057 | +1.8e-6 ± 2.1e-6 | 100 | 12 |
| g4c | phase x column 858 (chosen on g4s2-val) | 16 | 0.0102076 | +3.8e-6 ± 1.9e-6 | 100 | 39 |
| g4c | phase x progress halves (extra) | 16 | 0.0102053 | +1.4e-6 ± 1.7e-6 | 100 | 11 |
| g4c | phase x column 38 (chosen **on g4c**: in-sample, selection-biased) | 16 | 0.0101957 | -8.1e-6 ± 2.4e-6 | 100 | 13 |
| g4s2-val | r3kr1 as shipped (integer) | 8 | 0.0192834 | +1.02e-5 ± 2.9e-6 | | |
| g4s2-val | **phase (control, refit)** | 8 | **0.0192734** | 0 | 1,000 | 9 |
| g4s2-val | progress octiles | 8 | 0.0208447 | **+1.58e-3 ± 1.5e-4** (8.2% worse) | 100 | 80 |
| g4s2-val | phase x kings' wings | 16 | 0.0192694 | **-4.0e-6 ± 1.7e-6** | 1,000 | 10 |
| g4s2-val | phase x column 38 (chosen on g4c) | 16 | 0.0192801 | +6.9e-6 ± 3.1e-6 | 10,000 | 10 |
| g4s2-val | phase x progress halves (extra) | 16 | 0.0192757 | +2.7e-6 ± 2.5e-6 | 1,000 | 9 |

(The g4s2-val rows other than progress come from the run with the ridge grid 10 to 1e5
(results/routing-extra-g4s2val.json); the first run's grid stopped at 1,000, where the control and wings sat, and gave
the same numbers for both. Progress on g4s2-val is from the first run (grid 0.1-1,000, optimum 100, interior); its
objective moved by under 2e-5 of itself over its last 20 iterations. The g4c progress row was refit with the
re-linearised fit and gave the same loss to 8 digits as the first fit; column 858's g4c row is from the first,
fixed-matrix fit (39 iterations).)

**Reading.**
- **The control reproduces r3kr1**: the refit's held-out loss is 0.35% (g4c) and 0.05% (g4s2-val) below the shipped
  heads', the gain from refitting on each set's own labels, which is why every routing is compared with the refit
  control, never with the shipped heads.
- **Progress octiles lose badly** (8-11% worse): one head per progress octile spans every material phase, and the
  material phase carries more than lateness. Within phase (the extra "phase x progress halves", lens 1's idea in the
  fairer form), progress adds nothing (+1.4e-6 and +2.7e-6).
- **Kings' wings**: null on g4c (+1.8e-6 ± 2.1e-6), **2.3 SE better on g4s2-val** (-4.0e-6 ± 1.7e-6, 0.02% of the
  loss). The larger, deciding set says no; the smaller says a hair yes; the signs disagree.
- **A self-chosen column does not transfer**: each set's choice is worse than phase on the other set (+3.8e-6 on g4c,
  +6.9e-6 on g4s2-val); only the in-sample reading (g4c's own column on g4c) looks better, by the size a best-of-8
  selection on the same folds can produce.
- **Decision (lens 1's rule, idea 186):** progress, wings and the self-chosen column are each **killed at their CPU
  step on g4c**, the deciding set. Wings on g4s2-val is the one reading past 2 SE, with the opposite sign on g4c; I do
  not read it as "beats phase clearly", so per the owner's order no fixed-node screen is proposed. If the owner wants
  wings tested anyway, a fixed-node screen would need: a net file with 16 output heads and the engine's bucket picker
  extended to phase x wing (an engine change, about half an EU, est.); both arms refit on the same training positions
  (the 8-head phase refit as the control net, so the refit's own gain cancels), quantised to Fork's grid (output
  weights x QB = 64 in int16, biases x QA x QB in int32) and checked by netcheck; then the usual 1,600-game screen.
  None of that was built or run.

## 7. Not run, and caveats

- **Not run:** idea 193's king-zone square-state lane (not in the panel order); the blockade by endgame buckets 0-2
  alone (only all buckets at once); the deep-label rerun (L2-4's reason 3: no deep-label set exists yet); any
  fixed-node screen, engine change, training or net file. The 608 links were evaluated on S512r2 with the reference
  loader (it reads architecture 2: the vision file's UNVERIFIED is resolved, yes).
- **Two runs stopped and restarted (my own jobs):** the first g4s2-val column selection (a stopping rule that rounding
  kept from firing; fixed, rerun), and the first extra refit (to widen the ridge grid). Their partial outputs are not
  used. g4d's data generation and every other job were left alone.
- **The residual share is a linear, additive probe.** It measures what an additive table over a family's cells adds
  to the net's prediction of its labels, held out. It cannot see interactions a hidden layer could use (idea 175's
  stated limit), and the links show that a winner can read near zero on it. The labels are 20,000-node self-play
  scores (TD(0.9) on g4c, the blend on g4s2-val): long-horizon concepts the labels do not see cannot show.
- **By-bucket floor:** an absorbed family (the links on r3kr1) reads 0.042% by bucket; by-bucket readings near that
  are not evidence.
- **Selection:** the column pre-rank and the top-8 refits used one ridge strength (10) for every candidate; the final
  refits used the grid. Choosing from 8 on the same folds biases the in-sample row; the cross-set rows do not have
  that bias.
- **Written from the concepts, not from any engine:** every finder (step0_common.py) and every family encoding.
  python-chess is the only outside code used (attack tables and the pin oracle); every Elo figure quoted is a Fork
  measurement from the sprt-log or the decisions log.

## 8. Files and names

- Scripts (docs/research/vision-step0-2026-11-14/): step0_common.py (finders, layouts), step0_features.py (the pass
  and its oracle checks), step0_pins_cpp.py with pins.cpp (Fork's own pinned()/discoverers() check), step0_eval.py
  (the four nets, with the r_int and evalfens checks), step0_plies.py (ply alignment), step0_study.py (shares,
  injections), step0_routing.py (refits), step0_tables.py (tables.md); the run scripts run_after_study.sh,
  run_routing.sh, run_extra.sh. Results: results/*.json (the study, injections, routings, selections, checks) and
  tables.md (every table row). The position, cell and hidden-value files (about 1 GB) stay in the scratch folder.
- Needs numpy, scipy and python-chess (a scratch venv: numpy 2.5.4, scipy 1.18.1, chess 1.11.2).
- **New names (none screened; measurement code only):** the scripts' file names; `position_cells`, `base_cells`,
  `lone_shields` (Python, named after Fork's own C++ helper), `layouts`, `FAMILY_NAMES`, the family keys (xl, xpn,
  xsl, xx, pin, pinq, disc, forkn, forkp, under, file, block, loose, kk, mat, trap, trapa, back, sev, bad, links),
  `oracle_check`, `Folds`, `Base`, `fold_stats`, `fold_sse`, `share`, `variants`, `family_matrix`, `prevalence`,
  `fit`, `gauss_newton`, `heads_of`, `cells_for`, `start_heads`, the routing names (phase, progress, phaseprog, wings,
  column). No search or engine constant; the grids, BLOCK 2,000 and FOLDS 8 are analysis settings (idea 175's).
