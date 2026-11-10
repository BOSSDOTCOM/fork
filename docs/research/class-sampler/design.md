# Class-weighted training (ideas.md 69): design review

Written 2026-11-10 for the owner's review. The owner decided on 2026-11-10
(DESIGN.md decisions log, phase-4 4eba8f7) on "a design review first, then
an arm in retrain 8c". **This is a design only.** No trainer code, kernel or
data was changed or written; nothing was trained. Every number below is
either quoted from a cited source or computed from the committed aggregates
in `docs/research/conversion-defense/item5-data-gaps.json`. Section 8 gives
each number's justification. Anything not checked is marked UNVERIFIED.

Sources:
- the conversion-and-defense report, `docs/research/conversion-defense/report.md`
  on research/conversion-defense (be86410): item 5 and fix 4 in "Synthesis:
  ranked weaknesses";
- the trainer, `tools/train/src/main.rs` (unchanged between phase-4 and
  retrain/8b-prep);
- retrain 8b's plan and kernel, `docs/research/retrain-8b/plan.md` and
  `tools/train/kaggle/retrain_8b.py` on retrain/8b-prep (acb9875);
- bullet's trainer crate at the pinned revision da426a49 (MIT; Cargo.toml):
  `crates/trainer/src/reader.rs` and `crates/trainer/src/model/inputs.rs`.
  I read them only for the loader's generic bounds. Nothing from them is
  copied here.

## 1. The current pipeline

### 1.1 How positions reach the GPU

All line numbers below are in `tools/train/src/main.rs`.

- **Files and order.** `ShardReader` (lines 815-956) reads viriformat games
  from the `--data` files. The 8b kernel always passes `--interleave`
  (`retrain_8b.py` line 162, `stage_args`). Each pass then reads the files
  side by side, one game at a time, always from the file that is furthest
  behind in the share of its bytes read (`interleave_next`, lines 830-844,
  and its two unit tests at lines 1311-1339). So every file, the endgame
  slice included, is spread evenly through each pass. The reader loops
  forever. The run ends when the schedule's batch count is reached.
- **Filter.** Each game is expanded by viriformat's own conversion,
  `splat_to_bulletformat`, under `filter()` (lines 811-813): in-check
  positions, positions marked tactical (viriformat's `filter_tactical`;
  its exact meaning is UNVERIFIED, KB bullet-internals.md §5.2), and
  positions with |score| above 20,000 are dropped (`MAX_SCORE`, line 83). Mate and table scores
  are dropped this way. So are the records idea 52's arm marked unsaved
  with score 32767 (plan.md, "Equal data: oversampling replaces"). Kept
  positions are about 0.645 of saved positions on g3j's pool (plan.md §1).
- **Shuffle.** Kept positions go into a buffer of `--buffer` positions.
  The default is 2^24 = 16,777,216 (line 1145), and the kernel does not
  override it, so one buffer is about 3.4 superbatches. When the buffer is
  full it is Fisher-Yates shuffled with Fork's SplitMix stream, seeded once
  with `--seed` per run (lines 798-809, 884-895, 899-900), and handed on in
  chunks of 16,384. The stream is not reseeded at each pass, so each pass
  has a new order, and the whole order is reproducible from the seed.
- **Mapping.** bullet's `ReadMapLoader` (line 1218; bullet `reader.rs`
  lines 30-93) cuts the stream into batches and maps each one with
  `--threads 2` workers. The mapper (lines 789-796) builds the inputs with
  `fill`, which constructs a `Board` from the `ChessBoard` (lines 260-267,
  776-787), and builds the target as (1 − w)·sigmoid(score / S) + w·result.
  The kernel sets w = 0.5 and S = 92 (lines 62-65 and 85-91).
- **Loss.** `output.sigmoid().squared_error(target).reduce_sum_batch()`
  (line 679): every position counts the same. **No position is weighted
  today.**
- **Validation.** `--val` reads the first `--val-positions` kept positions
  of the validation file (20,000 per superbatch in 8b). The trainer computes
  its own MSE against the same target, outside the training graph (lines
  1157-1188). Validation loss is a diagnostic only (owner, 2026-11-09;
  DESIGN.md decisions log, the testing policy).

### 1.2 The slices, the blend copies and "equal data"

- **The Syzygy endgame slice.** Ten files (`slice1-01..09.vf`,
  `g3s2-slice1-00-rest.vf`) hold 26.0 M one-move games, 1.76% of g4s1's
  saved positions. "Every arm reads the same 10 slice files unchanged"
  (owner, 2026-11-09; plan.md §1). The kernel knows the slice files by name
  (`is_slice`, `retrain_8b.py` line 108) and gives them to every arm
  (`arm_files`, line 116). Endgame slice v2 (ideas.md 68) changes this slice
  only in its own 8c arm.
- **The blend copies** (`bl-`, plan.md §2, the TD arms) encode the control's
  target as a score, so that the TD arms can train at result weight 0. They
  change targets only, not which positions are seen.
- **Idea 52's arm** oversamples by duplication on disk. Each of 190,000
  sites is copied 16 times into `i52-sites.vf`. To keep the total fixed, the
  site's own record and 15 others per site are marked unsaved in copies of
  g3j-w00..w04. The arm therefore has exactly the control's kept positions,
  and `verify_arm` reads everything back to confirm it (plan.md §2).
- **Equal data** means equal positions seen. Every arm trains 360
  superbatches × 305 batches × 16,384 = 1,798,963,200 positions (plan.md
  §2), about 1.9 passes over g4s1's roughly 0.95 B kept positions. The
  0.95 B is UNVERIFIED (plan.md §1). Each arm uses seed 1 and the same warm
  start: S512ppr3's float weights, SHA-256 0221585…ecc3 (`retrain_8b.py`
  line 78). The schedule is LR 0.0001, dropped tenfold after superbatch 180.
  The candidate is the window average of superbatches 331-360.

## 2. The class function

### 2.1 Which classes

The function uses one partition: the report's **material class** (report.md
"Taxonomy", the `matcls` dimension of item5-data-gaps.json). Each position
falls in exactly one of the cells. The JSON's 42 observed cells hold 100.0%
of the training sample. I chose this partition for three reasons:

- it carries most of the measured gap (section 3.4: the total-variation
  distance between training and deciding shares is 0.26);
- the report says the material taxonomy is the part least affected by the
  trainer's quiet-position filter (report.md item 5), which is why it
  compared shares on it;
- its cells are large enough to measure. Of the 42 cells, 31 have at least
  50 deciding positions.

Structure (passers, wings) and phase are left out of 8c's function on
purpose (open question 3). A finer cross-product would split the 7,378
deciding positions into cells too small to estimate. The material class
already contains phase through its signature (the P >= 13 split for queens
on, P >= 10 without queens).

**Definition**, from the report's text, for the position as stored (the
side to move's frame). Every cell used is symmetric, so the frame does not
change a position's class:

- Counts per side of P, N, B, R, Q. Minors = N + B. The phase count is
  P = minors + 2·rooks + 4·queens over both sides, capped at 24 (as
  `Board::phase`, lines 271-274).
- **Signature:**
  - Q-MG: any queen on the board and P >= 13.
  - Q-EG: any queen and P <= 12.
  - noQ-MG: no queens, rooks and minors both present, P >= 10.
  - R+minor-EG: the same with P <= 9.
  - R-EG: no queens, no minors, at least one rook.
  - minor-EG: minors only, no rooks or queens.
  - pawn-EG: kings and pawns only.
- **Second part**, comparing the two sides' counts:
  - Q-imbalance: the queen counts differ.
  - R-vs-minors: the rook and minor counts differ in opposite directions.
  - minor-up: only the minor count differs.
  - other-imbalance: any other difference in counts.
  - B-vs-N: equal counts, but the bishops and knights differ.
  - If the pieces are fully equal, the pawn balance: level (equal pawns),
    pawn+-1 (one pawn apart) or pawn+-2+ (two or more apart).

Two details of the report's own script are UNVERIFIED, because the script
stayed outside the repository (report.md, "Files"):

1. whether "rooks and minors" counts both sides together, and
2. how a position with one side's rooks against the other side's minors
   and no queens is signed.

Test 5.1(b) settles both by reproducing the report's counts.

### 2.2 Where it is computed

**At load time, from the board, in the mapper.** `fill` already builds a
`Board` for every position (line 777). The class needs ten piece counts and
a few comparisons on that same board. A side file was considered and
rejected:

- it would mean writing and uploading class bytes for about 2.4 B records
  (writing data, which this task excludes);
- it would have to stay aligned with records through every derived copy
  (`bl-`, `td80-`, `i52-`);
- it would gain nothing, because the class is a pure function of the
  board.

The weight also needs one fact the mapper does not have: **which file a
position came from**, so that slices can be exempt (section 3.5). The reader
knows it, since `for_each_interleaved` passes the file index (line 865).
bullet's loader is generic over the record type: `DataReader<T>` and
`ReadMapLoader` require only `T: Clone + Send + Sync + 'static` (bullet
`reader.rs` lines 14 and 30-33), and `ModelInputsMapper<T>` only
`T: Send + Sync` (`inputs.rs` lines 86-89). So the reader can hand the
mapper a record that holds the `ChessBoard` plus one exempt bit, set by
file name, with no change to bullet. (Checked in bullet's source at the
pinned revision; not yet built.)

### 2.3 Cost per position

The class is about 32 piece visits and about 10 comparisons on a `Board`
that `fill` builds anyway. `fill` itself does much more: two 64-square
perspective scans plus S512+PP's pawn-pair links (lines 479-496, 551-599).
My estimate is under 2% of mapper time. This is **UNVERIFIED** until test
5.4 measures it. The weight lookup is one table read. On the GPU, the added
cost is one dense (1, 1) input per position and one multiply in the loss,
also UNVERIFIED (section 4.3).

## 3. The weighting scheme

### 3.1 The three options

| | (a) Rejection / acceptance in the reader | (b) Duplication (on disk, or by the reader) | (c) Per-sample loss weights (**recommended**) |
|---|---|---|---|
| How | Keep a position with probability w_c / max w | Emit ⌊w⌋ copies plus one with probability w − ⌊w⌋; on disk, as idea 52 did | Loss = Σ w_c·(sigmoid(out) − target)²; the stream is the control's |
| Equal positions seen | Yes (the schedule counts batches); the reader decodes 1 / mean acceptance = 2.0 times as many kept positions | Yes, if the mean multiplicity is 1 | Yes, trivially: the same 1,798,963,200 positions in the same order |
| Same positions as the control | No | No | **Yes, byte for byte** (same files, seed and shuffle); only gradient weights differ |
| Gradient variance | No weight variance; class mix changed by sampling | As (a), plus copies of a position sit near each other in time (within one 3.4-superbatch buffer) | Larger by the Kish factor E[w²] / E[w]² = **1.21** with section 3.4's weights (effective batch about 13,500 of 16,384); never above **1.5625** for weights in [0.5, 2] |
| Distinct positions never presented | About **14.5%** of the data (a third of each 0.5x cell), at about 3.8 reading passes | About **9.3%** (27% of each 0.5x cell) | **None** (each position about 1.9 times, as in the control) |
| Repetition of up-weighted positions | About 3.8 presentations per position instead of 1.9 | About 3.8 | Same as the control; the gradient is scaled instead |
| Reader load | About 2x decoding (K17: 1.37 M raw positions/s per thread, against 8a's 232,400 trained/s; probably keeps up, UNVERIFIED with two runs sharing Kaggle's 4 cores) | On disk: writes and uploads data (excluded here, and the cost of idea 52's arm); in the reader: as (a) | Unchanged |
| Code | Reader only | Data tool, or reader | Graph (one dense input, the loss) plus reader (exempt bit) plus mapper (class) |
| Exempting the slice exactly | Needs the slice's acceptance set to the mean acceptance, so its share stays put | As (a) | Weight 1 for the slice and no normalisation over it keeps its gradient share equal to its position share |

The "never presented" figures assume an independent draw per position per
pass. They use section 3.4's weights and plan.md's 1.89 passes (1,798,963,200
over about 0.95 B kept positions, UNVERIFIED).

**Recommendation: (c), per-sample loss weights.** Four reasons:

1. **It is the cleanest comparison.** The arm sees exactly the control's
   positions in the control's order. The arm-minus-control difference is
   the weighting alone, not a different sample of positions.
2. **No diversity is lost and nothing is repeated more.** Every rare
   position is still presented. A down-weighted cell keeps all its
   positions at half their gradient weight, never fewer positions.
3. **Exempting slices is exact,** and the WDL/score mix is untouched
   (section 3.5).
4. **The extra variance has a hard bound.** It is 1.21 measured from the
   weights and at most 1.5625 by the caps. AdamW's per-weight scaling makes
   the step size nearly independent of the loss's overall scale, so mean
   weight 1 keeps the effective learning rate close to the control's.

The price is a change to the training graph. Option (a) is the fallback if
the graph change cannot be made to reproduce the control exactly when all
weights are 1 (test 5.3).

Graph change, as a design: add a second dense input of shape (1, 1) beside
`target` (line 616 already declares one such input), and compute the loss
as `(output.sigmoid().squared_error(target) * weight).reduce_sum_batch()`.
Multiplying two nodes is already used at lines 622 and 676. Whether
`squared_error` keeps a per-position value before `reduce_sum_batch` is
**UNVERIFIED**. If it does not, the fallback `(d * d * weight)` with
d = sigmoid(out) − target uses only operations this file already uses. The
validation code computes its own unweighted MSE outside the graph (lines
1171-1188), so it is unaffected. As a result, 8b's gate "c's superbatch 0
equals S512ppr3's prefix loss within 1e-6" still holds for the class arm.
The trainer's training-loss log becomes the weighted loss, which is not
comparable with the control's log. The design records this, and the
comparison uses validation.

### 3.2 Why the weight depends on the board only

The report's evidence for fix 4 quotes **matched** ratios: shares among
training positions with |stored score| 100-600. A weight that depends on the
stored score or the result would select on the label. That changes the
weighted conditional distribution of the target given the position, so the
loss would be minimised by a different evaluation, with |eval| pushed up
in the favoured band. That is a bias, not a reallocation.

A weight that depends only on the position's class keeps the minimiser of
the squared loss at each position unchanged: it is the conditional mean of
the target either way. Only the network's limited capacity is reallocated
toward the weighted classes. **So the class weight comes from the
unmatched ratio**: the class's deciding share over its share of all
training positions. The matched ratios remain the evidence that the gap is
real.

This has a consequence the owner should see. The largest matched gap,
**Q-MG with level material** (matched 3.96), is only 1.23 unmatched. In the
training data that class is mostly near-zero scores, so a class weight
cannot raise its decisive-score part on its own. That part is what fix 1's
positional-advantage slice (ideas.md 66) targets. The class weight
addresses the material mix (Q-MG B-vs-N 2.11, Q-MG a pawn apart 1.84,
queen endings 2.5-3.0; the minor-up classes 0.22-0.52). It does not
address the score distribution within a class (open question 2).

### 3.3 From ratios to weights

For each cell c, with training share t_c and deciding share d_c:

1. **Reference set:** d_c is the share among "all deciding positions" in
   item5-data-gaps.json. That set has 7,378 positions: 478 gauntlet turning
   points, 3,287 Fork-against-Fork turning points, 90 conversion-failure
   drop points and 3,523 defense-loss window starts. These are the shares
   behind the report's ranked gaps. The gauntlet-only set (478) leaves most
   cells too small to use (open question 4).
2. **Small cells:** a cell with fewer than **50** deciding positions gets
   weight exactly 1. That is the report's own threshold for ranking a gap
   ("counts of 50 or more"). 11 of the 42 cells, 9.3% of training
   positions, are held at 1 this way.
3. **Raw ratio:** r_c = d_c / t_c.
4. **Cap and normalise together:** w_c = clip(k·r_c, 0.5, 2), where the
   scale k is chosen so that the mean weight over the non-small cells is 1,
   that is Σ t_c·w_c = Σ t_c. A bisection finds k, because the left side
   increases with k. With the small cells at 1, the overall mean weight is
   1, so equal positions seen also means equal total gradient weight.
   Clipping first and normalising afterwards would push weights past the
   caps; solving for k keeps the caps exact.
5. **On 8c's own snapshot:** t_c must be recounted on 8c's training files,
   excluding the exempt ones (test 5.2). The shares below come from g3j's
   1-in-500 sample alone, which "represents the mix only partly" (report.md
   item 5, caveat). The final weights are computed the same way from
   item5's d_c and the new t_c, then committed with their SHA-256 before the
   arm is launched.

### 3.4 The provisional weights (from item5-data-gaps.json; t_c from g3j)

Computed with steps 1-4 (k = 0.912). Mean weight 1.000. E[w²] = 1.213.
The total-variation distance between training and deciding shares falls
from **0.260** to **0.086**. Three cells reach the cap of 2 and three the
floor of 0.5. The deciding shares in the JSON sum to 1.0003, which is
rounding.

| Cell | Training | Deciding (n) | Ratio | Matched ratio | **Weight** | Weighted share |
|---|---|---|---|---|---|---|
| Q-MG, B-vs-N | 7.48% | 15.78% (1,164) | 2.11 | 3.10 | **1.92** | 14.39% |
| Q-MG, pawn+-1 | 5.26% | 9.68% (714) | 1.84 | 2.56 | **1.68** | 8.83% |
| Q-MG, level | 7.63% | 9.35% (690) | 1.23 | 3.96 | **1.12** | 8.53% |
| Q-MG, minor-up | 12.56% | 6.53% (482) | 0.52 | 0.32 | **0.50** | 6.28% |
| R+minor-EG, R-vs-minors | 6.98% | 5.49% (405) | 0.79 | 0.69 | **0.72** | 5.01% |
| Q-MG, R-vs-minors | 3.38% | 5.06% (373) | 1.50 | 1.23 | **1.36** | 4.61% |
| R+minor-EG, B-vs-N | 3.11% | 4.49% (331) | 1.44 | 1.56 | **1.32** | 4.09% |
| R-EG, pawn+-1 | 2.44% | 3.80% (280) | 1.56 | 2.34 | **1.42** | 3.47% |
| noQ-MG, B-vs-N | 2.75% | 3.35% (247) | 1.22 | 1.44 | **1.11** | 3.05% |
| Q-EG, Q-imbalance | 3.84% | 2.59% (191) | 0.67 | 0.78 | **0.62** | 2.36% |
| minor-EG, B-vs-N | 1.79% | 2.51% (185) | 1.40 | 1.64 | **1.28** | 2.29% |
| R+minor-EG, pawn+-1 | 1.66% | 2.48% (183) | 1.50 | 1.90 | **1.37** | 2.26% |
| Q-MG, pawn+-2+ | 1.51% | 2.45% (181) | 1.62 | 1.27 | **1.48** | 2.23% |
| noQ-MG, pawn+-1 | 1.52% | 2.33% (172) | 1.53 | 1.83 | **1.40** | 2.12% |
| R+minor-EG, minor-up | 9.08% | 1.97% (145) | 0.22 | 0.18 | **0.50** | 4.54% |
| Q-EG, pawn+-1 | 0.73% | 1.83% (135) | 2.50 | 3.23 | **2.00** | 1.47% |
| R-EG, level | 1.42% | 1.50% (111) | 1.06 | 4.07 | **0.97** | 1.37% |
| R-EG, pawn+-2+ | 2.41% | 1.48% (109) | 0.61 | 0.44 | **0.56** | 1.35% |
| noQ-MG, level | 1.45% | 1.45% (107) | 1.00 | 3.28 | **0.91** | 1.32% |
| minor-EG, pawn+-1 | 1.49% | 1.36% (100) | 0.91 | 1.85 | **0.83** | 1.24% |
| Q-EG, pawn+-2+ | 0.50% | 1.29% (95) | 2.60 | 1.74 | **2.00** | 0.99% |
| R+minor-EG, level | 1.13% | 1.21% (89) | 1.07 | 3.55 | **0.98** | 1.10% |
| Q-MG, other-imbalance | 1.99% | 1.17% (86) | 0.59 | 0.44 | **0.53** | 1.07% |
| R+minor-EG, pawn+-2+ | 1.14% | 1.08% (80) | 0.95 | 0.60 | **0.87** | 0.98% |
| Q-MG, Q-imbalance | 1.36% | 1.04% (77) | 0.76 | 0.56 | **0.70** | 0.95% |
| Q-EG, B-vs-N | 0.34% | 1.03% (76) | 2.99 | 3.68 | **2.00** | 0.69% |
| minor-EG, minor-up | 2.78% | 0.85% (63) | 0.31 | 0.32 | **0.50** | 1.39% |
| Q-EG, R-vs-minors | 0.57% | 0.83% (61) | 1.47 | 1.30 | **1.34** | 0.76% |
| minor-EG, pawn+-2+ | 1.03% | 0.77% (57) | 0.74 | 0.64 | **0.68** | 0.70% |
| Q-EG, level | 0.49% | 0.72% (53) | 1.48 | 4.39 | **1.35** | 0.66% |
| Q-EG, minor-up | 0.93% | 0.70% (52) | 0.75 | 0.60 | **0.69** | 0.64% |
| 11 small cells (n < 50): noQ-MG R-vs-minors, minor-up, pawn+-2+, other-imbalance; R+minor-EG other-imbalance; minor-EG level; Q-EG other-imbalance; R-EG other-imbalance; pawn-EG level, pawn+-1, pawn+-2+ | 9.26% | 3.86% | – | – | **1.00** | 9.26% |

By signature: Q-MG goes from 41.2% of training to a weighted 46.9%
(deciding 51.1%). R+minor-EG goes from 25.1% to 20.0% (17.3%), minor-EG from
8.0% to 6.5% (6.0%), noQ-MG from 10.3% to 11.1% (8.9%). Q-EG, R-EG and pawn-EG
barely move (7.9 to 8.1%, 7.1 to 7.0%, 0.5 to 0.5%).

**Sensitivity to the small-cell threshold** (the report flags cells under
15 as small): at 15, only 4 cells are held at 1. Then k = 0.950,
E[w²] = 1.249 and the distance falls to 0.055; noQ-MG minor-up (n 41,
ratio 0.19) and R+minor-EG other-imbalance (n 42, ratio 0.29) drop to
0.50. I recommend 50: cells with 15-49 deciding positions have relative
standard errors of about 14-26% on d_c, so their weights would be mostly
noise (open question 5).

### 3.5 Interactions

- **WDL/score mix.** The weight multiplies the whole per-position loss. The
  target (0.5·sigmoid(s / 92) + 0.5·z) is unchanged, and so is the result
  weight. The TD arms' result weight 0 would combine the same way.
- **The endgame slice: exempt, weight exactly 1.** The owner's rule keeps
  the slice the same in every arm. With weight 1 and no normalisation over
  it, the slice's share of the gradient equals its share of positions
  (1.76% in g4s1) in the class arm as in the control. Without the
  exemption, its ≤5-man positions would fall into the pawn-EG, minor-EG and
  R-EG cells and get those cells' weights, which were measured on data that
  contains no ≤5-man positions (report.md item 5: "at most 5 men 0.0%").
  The exemption goes by file name, as `is_slice` does in the kernel. Slice
  v2 (ideas.md 68) and any R32 slice are exempt the same way.
- **Idea 52's sites: exempt if they stay.** If 8b keeps idea 52, 8c's
  control holds `i52-sites.vf`, already oversampled 16 times. Class weights
  on top would compound to as much as 32 times and mix two ideas. Weight 1
  for that file. The control's dropped records (score 32767) never reach the
  mapper, so the normalisation counts only kept positions.
- **Fix 1 and 2's slices (ideas.md 66).** They raise the same Q-MG,
  equal-pieces classes with new data. The class arm should run against the
  control without those slices, and the slice arm without class weights,
  so that each idea's effect is measured alone. A combined arm comes after
  both results (open question 6). If the slices enter 8c's control, they
  are exempt like the Syzygy slice.

## 4. The 8c arm

### 4.1 Configuration

- **cw**: 8c's control command plus `--class-weights FILE` (the committed
  table, 56 cells, every possible cell listed; an unlisted cell is an
  error, never a silent 1) and the exempt file list (slices, and any
  oversampled-site file). The kernel's validity record gets the table's
  SHA-256 and the exempt list. The option names are placeholders. Under
  DESIGN.md §8 they go through the name screen (a separate subagent)
  before any code uses them.
- **The same as the control:** every training file and its order (the
  interleave), seed 1 (data shuffle and initialisation), the warm start
  (the default network's float weights, as in 8b), LR 0.0001 with the
  tenfold drop after superbatch 180, 360 × 305 × 16,384 =
  1,798,963,200 positions seen, S, result weight 0.5, the validation file,
  and the candidate rule (window average of superbatches 331-360, quantised
  by the trainer). The only difference is the loss weight.
- Kept per arm, as in 8b: the best checkpoint, ck-180 and ck-360, and the
  window.

### 4.2 GPU cost

- **One run: about 2.15 T4 GPU-hours**, measured for this architecture,
  batch and length. 8a's R1 and R2 each took 7,740.8 s at 232,400
  positions/s, and item 7's warm seed took 7,741 s (plan.md §4). The
  project's planning figure is about 5 GPU-h per arm (report.md synthesis;
  DESIGN.md §5.6 step 13). The measured 2.15 is the expected cost, and 5 is
  the budget ceiling. The overhead of the extra input and multiply is
  UNVERIFIED and expected to be negligible (test 5.4 bounds it on CPU; the
  first superbatch's time in the kernel log measures it on the GPU).
- An optional **c2** (the control at seed 2, +2.15 GPU-h) would measure
  seed noise for the head-to-head (open question 7).
- In 8c's session the arm queues on whichever GPU is less loaded. Kaggle's
  quota is 30 GPU-h a week, and whether a T4 x2 session is charged per GPU
  is UNVERIFIED (plan.md §4).

### 4.3 Implementation order (after approval; not done here)

1. The class function, with its unit test (5.1).
2. A `classes` subcommand (placeholder name) that counts cells on given
   files, prints per-position classes for a sample, and computes the
   weight table from item5's d_c (5.2).
3. The exempt bit in the reader's record, and the weight in the mapper.
4. The graph's weight input, with the all-ones check (5.3).
5. The kernel's arm, then a `--plan` dry run and `--check-inputs`.

Each step is committed separately. The trainer is a training tool, so the
engine's bench does not change. The commits still run the trainer's own
`cargo test`, and the parity chain at the arm's gates.

## 5. Tests before the arm

1. **The class function on known positions** (a Rust unit test beside
   `interleave_tests`).
   - (a) Constructed positions, written for this test from the definition
     in 2.1 (not recalled from any source), one for each signature, each
     second-part class and each boundary:
     - P = 13 and 12 with a queen on;
     - P = 10 and 9 without queens;
     - equal pieces with 0, 1 and 2 pawns apart;
     - B-vs-N with equal minor counts;
     - R-vs-minors in both directions;
     - minor-up;
     - a queen imbalance;
     - the same position seen from both sides, to show the class is
       symmetric.

     A second implementation, in Python and written separately from the
     report's text, must give the same class for every case. That makes the
     test independent (testing rules: "Oracles must be independent").
   - (b) **End to end against the analysis:** run the function on the
     report's training sample (every 500th kept position, offset 137, of
     g3j w00-w04, 124,288 positions). It must reproduce item5's `train_n`
     for every `matcls` cell exactly. If it does not, either the definition
     differs from the report's script (2.1's two UNVERIFIED details) or the
     sample differs (file order is UNVERIFIED). That is resolved before
     anything is trained. Fault-inject once (swap the P >= 13 and 12
     boundary) to show the comparison can fail.
2. **The realised shares match the targets.** Count the cells on 8c's
   training files (excluding exempt files) to fix t_c and the table. Then
   run the reader and mapper path on CPU for the first superbatch of the
   arm's own stream (4,997,120 positions) and add up the weights per cell.
   - Each cell's weighted share must be within **0.3 percentage points** of
     t_c·w_c.
   - The mean weight of non-exempt positions must be within **1 ± 0.005**.
   - Every exempt position must have weight exactly 1.
   - The exempt files' share of positions must match the control's
     stream.

   The tolerances: positions within one game are correlated (about 32 kept
   per game on g3j: 114.4 M saved × 0.645 kept over 2.28 M games; plan.md
   §1, report.md item 5), so the effective sample is at least about 156,000
   games. That gives a standard error of at most about 0.09 pp on a 14%
   share, and about 0.0012 on the mean weight (SD of w is 0.46). The bounds
   are about 3 and 4 standard errors.
3. **Determinism and equivalence.**
   - (a) Two runs of 5.2's sample give byte-identical per-position (class,
     weight) lists, and the Python oracle gives the same lists.
   - (b) An all-ones table must reproduce the control's float weights after
     one short run (a few batches, fixed seed) byte for byte. If two plain
     control runs already differ on the GPU (bullet's CUDA kernels may sum
     in a nondeterministic order: UNVERIFIED), the all-ones run must differ
     from the control by no more than two control runs differ from each
     other. If neither holds, the graph change is wrong, and option (a) is
     the fallback.
   - (c) The table's SHA-256 and the exempt list go in the kernel's
     validity record, and the session refuses to start if either does not
     match.
4. **Throughput.** The `loader` benchmark (line 1290) extended to decode,
   `fill` and classify, against decode and `fill` alone, on the same
   positions. Accept if the class costs at most 3% of that path's time.
5. **8b's gates for the arm** (plan.md §3, item 1): superbatch 0 equals the
   default's validation prefix loss within 1e-6 (validation is unweighted,
   so this still holds); conversion; the parity chain; the endgame check.

## 6. Risks

1. **Down-weighting classes where conversion is judged.** The
   conversion-failure drop points sit in the classes this weighting
   lowers. In the imbalance dimension they are R-vs-minors (ratio 2.20,
   n 23) and Q-imbalance (2.35, n 11), against the down-weights for
   R+minor-EG R-vs-minors (0.72), Q-EG and Q-MG Q-imbalance (0.62, 0.70)
   and the minor-up cells (0.50). Item 4 also measures the largest
   compression in queen endings with a queen imbalance and minor endings a
   piece up (report.md item 4). The counts are small and conversion was
   never lost (report.md item 3). Still, the arm could worsen what fix 3
   targets. Mitigations: the floor of 0.5, the endgame check (reported and
   flagged above 15 of 900), and per-class losses (section 7). Conversion
   at LTC is not measured by the STC SPRT.
2. **Rare-class diversity.** Under (c) no position is dropped, so this is
   a risk only for (a) and (b), where about 14.5% and 9.3% of distinct
   positions would never be presented.
3. **Over-fitting.** Under (c) no position is repeated more often than in
   the control. Its gradient is up to twice as large, about 3.8
   "presentation-equivalents" over the run for a 2x cell. Check: the
   per-class gap between a fixed training sample and validation, for both
   arms (section 7).
4. **Gradient noise.** Effective batch about 13,500 of 16,384 (Kish 1.21).
   This is a small change, and AdamW's moments smooth it. UNVERIFIED in
   effect on the final network.
5. **The reference distribution.** The deciding shares come from Fork's
   gauntlet at 10+0.1 with random 8-ply openings and no tables, and from
   Fork-against-Fork games on UHO openings. TCEC's openings and conditions
   differ (DESIGN.md decisions log, the transfer-testing policy of
   2026-11-09). The weights chase where Fork's own games are decided.
   Fork-against-Fork games dominate the reference: 6,410 of the 7,378
   deciding positions (87%) come from them (3,287 turning points, 3,051
   defense-loss starts and 72 conversion-failure drop points; report.md
   items 2-3). So it leans toward self-play endgames more than the gauntlet
   does.
6. **The training shares come from one part.** The provisional t_c are
   g3j's alone. Step 5 of 3.3 recounts them on 8c's snapshot before the
   table is fixed.
7. **Validation set.** g4s1-val, or 8c's equivalent, is an unweighted
   sample of the training mix, so the class arm is expected to lose a
   little there by design (it optimises a different mix). **The unweighted
   overall validation loss cannot be a kill criterion.** The report's
   proposed kill, "validation loss worse overall by more than the seed
   spread", conflicts with this and with the owner's 2026-11-09 rule that
   validation loss is a diagnostic. I recommend dropping it (open question
   8).
8. **Same-network labels.** The deep-label error measures (item 4) use
   S512ppr3's own search, so they share its biases. The game results, the
   screen and the SPRT do not.

## 7. Measures (declared before any result)

Diagnostics (no gate; every candidate and the control):

- **Per-class validation loss** on all of 8c's validation file. For each
  of the 42 cells: n, the unweighted MSE for both arms, and the difference
  with a bootstrap 95% interval resampled by game. Also the unweighted
  overall loss (the standing diagnostic) and the **weighted overall loss**
  with the same table for both arms, which is the arm's own objective.
  Expected: lower loss in the up-weighted cells, higher in the
  down-weighted cells, and the weighted loss lower for cw. None of these
  is a gate.
- **Per-class static-eval error against deep labels** on the held-out
  gold sets: idea 51's H (3,131 positions at 1 M nodes) and idea 52's
  2,000 controls (200,000 nodes, with game results). These are item 4's
  measures, by cell for cells with n >= 60. Expected: smaller win-
  probability error in Q-MG B-vs-N, Q-MG pawn+-1 and R-vs-minors. Also the
  Brier score against results on the controls.
- **Per-class train-validation gap** on a fixed 20,000-position training
  sample, for risk 3.
- **The endgame check** (900 positions), reported and flagged above 15
  misjudged.

Tests (the project's standard path; DESIGN.md decisions log, testing
policy, 2026-11-09):

1. Integrity gates (5.5): blocking.
2. **Fixed-node screen** against the default, 1,600 games at 800,000
   nodes per move. All of 8c's competing candidates are screened first.
3. **Head-to-head screen** cw-avg against c-avg, 1,600 games at 800,000
   nodes, for idea 69's keep-or-drop rule.
4. **STC SPRT `--kind network` [0, 5]** for the best-screened candidate,
   by 8b's promotion rule (at most two SPRTs per retrain).

**Proposed keep rule for idea 69** (to be declared before 8c's results):
keep class weighting if cw-avg beats c-avg by **+5 Elo or more** in the
head-to-head, or if cw-avg passes its STC SPRT. Otherwise idea 69 is
recorded as tested and dropped. The +5 bar is the one the owner set for
idea 52's keep-or-drop rule, which is also a resampling idea (decisions
log, 2026-11-07). A 1,600-game screen's 95% interval is about ±9.3-9.7 Elo
(recent screens in the decisions log: ±9.26 to ±9.67), so +5 is a weak
bar. A
passing SPRT is the real evidence.

## 8. Every number and its justification

| Number | Value | Source or reason |
|---|---|---|
| Caps | 0.5 to 2 | The report's proposal (fix 4). They also bound the Kish factor at (0.5 + 2)² / (4 · 0.5 · 2) = 1.5625, so the effective batch is never below 64%, and every class keeps at least half its natural weight |
| Normalisation | mean weight 1 over non-exempt kept positions | Equal positions seen with equal total gradient weight; the exempt slices keep their share |
| Small-cell threshold | 50 deciding positions | The report's ranking rule ("counts of 50 or more"); sensitivity at 15 given in 3.4 |
| Reference set | all deciding positions, n 7,378 | The report's ranked gaps use it; the gauntlet-only 478 leave most cells small |
| Partition | the 42 observed material-class cells (56 possible) | item5-data-gaps.json `matcls`; the report's taxonomy |
| Provisional k, E[w²], distance | 0.912, 1.213, 0.260 to 0.086 | Computed here from item5-data-gaps.json (section 3.4); recomputed on 8c's snapshot |
| Never-presented shares under (a) and (b) | 14.5%, 9.3% | Computed from the weights, at 1.89 passes (plan.md: 1,798,963,200 over about 0.95 B kept, UNVERIFIED) |
| Positions per run | 1,798,963,200 | plan.md §2 (360 × 305 × 16,384) |
| Shuffle buffer | 16,777,216 positions | main.rs line 1145 default; the kernel passes no `--buffer` |
| GPU per run | 2.15 T4 GPU-h (5 budgeted) | plan.md §4 (8a's 7,740.8 s); report.md synthesis and DESIGN.md §5.6 step 13 for 5 |
| Reader rate | 1.37 M raw positions/s per thread | DESIGN.md K17 (433,777 kept of 637,006) |
| Training rate | 232,400 positions/s | plan.md §4 (8a) |
| Slice share | 1.76% of g4s1's saved positions | plan.md §1 |
| Realised-share tolerances | 0.3 pp per cell, mean weight 1 ± 0.005 | About 3 and 4 standard errors, at about 32 kept positions per game (g3j: 114.4 M saved × 0.645 over 2.28 M games; plan.md §1, report.md) |
| Throughput bound | at most 3% | A reader-side cost below the run-to-run noise of a Kaggle run is not measurable in GPU hours; my choice, UNVERIFIED as a noise figure |
| Keep bar | +5 Elo head-to-head | Idea 52's rule (owner, 2026-11-07) |
| Screen | 1,600 games, 800,000 nodes | 8b's and the report's standard |
| SPRT | STC, `--kind network`, [0, 5] | CLAUDE.md, DESIGN.md testing policy |

## 9. Not checked (UNVERIFIED)

- Two details of the report's taxonomy script (2.1), settled by test
  5.1(b).
- The order of g3j's 1-in-500 sample (file order), for 5.1(b).
- Whether bullet's `squared_error` keeps a per-position value before
  `reduce_sum_batch` (3.1); the fallback uses operations main.rs already
  uses.
- Whether bullet's CUDA training is bitwise deterministic run to run
  (5.3(b)).
- The class function's and the weight input's cost (2.3, 4.2).
- Reader throughput under option (a) with two runs on Kaggle's 4 cores.
- g4s1's kept count (about 0.95 B, plan.md), so the 1.89 passes.
- 8c's snapshot and its class shares (not built yet).
- The effect on the network of the 1.21 gradient-variance factor.

## 10. Open questions for the owner, with recommendations

1. **Mechanism: (c) loss weights, (a) rejection or (b) duplication.**
   Recommended: (c), with (a) as the fallback if test 5.3(b) fails.
2. **Board-only weights from unmatched ratios, or score-band weights from
   matched ratios.** Recommended: board only. A weight that selects on the
   label biases the target. The score-distribution gap (Q-MG level
   material at decisive scores) is fix 1's job.
3. **Partition: the material class alone, or the material class crossed
   with passers.** A crossed version could be fitted by raking to both
   committed marginals (`matcls` and `sig_x_passers`); Q-MG with passers
   on both sides has ratio 2.68. Recommended: the material class alone for
   8c. That is one variable, a function test that can reproduce the
   report's counts, and a smaller variance factor. Passers would be a later
   arm if cw passes.
4. **Reference set: all deciding positions, or the gauntlet only.**
   Recommended: all (7,378), as the report ranked. The gauntlet's 478 leave
   most cells under 50.
5. **Small-cell threshold: 50 or 15.** Recommended: 50.
6. **Interaction with ideas 66 and 68 in 8c: separate arms against one
   control, or also a combined arm** (a 2 x 2 with fix 1's slice, +2.15
   GPU-h). Recommended: separate arms first, and a combined arm only after
   both have their own screens.
7. **A second control seed (c2, +2.15 GPU-h)** to read the head-to-head
   against seed noise. Recommended: yes if 8c's quota allows, since
   several 8c ideas share it; otherwise no.
8. **The report's validation-loss kill rule.** Recommended: drop it. The
   unweighted overall loss is expected to rise a little by design. Use
   the per-class and weighted losses as diagnostics, and the keep rule in
   section 7.
9. **The keep rule:** +5 Elo head-to-head or a passing SPRT. Recommended
   as written; declare it before 8c's results.
