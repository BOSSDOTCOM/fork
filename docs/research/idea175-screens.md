<!-- Copied onto phase-4 on 2026-11-14 for the record (owner's instruction), from local branch proto/i175-state-rows (commit 40c5727), unchanged below this note. The prototype code stays on that unpushed branch: idea 175 was killed, so its new names were never screened. -->

# Idea 175's two screens and idea 176's column count (2026-11-14)

Owner's plan (2026-11-14): "Idea 1: residual study (ranking only) + zero-delta speed prototype; kill below 0.95.
Fold idea 2's column-utilisation count into the same data pass. Note idea 1 and option (a) are alternatives on one
body." Idea 1 is ideas.md 175 (state-folded rows), idea 2 is ideas.md 176 (split-clone columns); the proposal is
docs/research/network-novelty-2026-11-14.md. Branch proto/i175-state-rows (from phase-4 d63ddc6), not pushed, not
merged. No training, no GitHub workflow, no push. All times EST.

## Summary

| Screen | Kill line (proposal) | Result | Against the line |
|---|---|---|---|
| Residual study, each tier A state's share of r8brft1's residual variance (held out) | a state under 0.5% | **every state 0.032% or less** on 600,000 g4c positions (largest: a bishop attacked by an enemy pawn, 0.032% +- 0.014); 0.017% or less on the 103,254 g4s2-val positions; all tier A states together 0.006% (by square) / 0.107% (pooled over squares) | **every state is below the line, by a factor of 15 or more** (ranking only; the decision is the owner's) |
| Zero-delta speed prototype, nps of B (architecture 11, r8brft1 laid out with zero deltas) over A (phase-4 d63ddc6, r8brft1) | below 0.95 | **0.905 (95% 0.885-0.925)**, 60 interleaved rounds, and 0.913 (0.894-0.931), 40 rounds, in a second session; A/A pairs 0.991-1.001. Rows per update +14%; a measurement build that finds every state but applies no state row runs at 0.923 (0.887-0.961): most of the cost is the finding, not the rows | **below the kill line in both sessions** (both upper bounds under 0.95); it would need about +15 Elo at fixed nodes to pay for itself (-118 log2 0.913) |
| Idea 176's count | (none: a look) | no dead column; 74 of 512 columns are 4x or more as used with queens on as off at matched output buckets (5 the other way); the top 256 by use hold 82.5% of it | the net already has queens-on-specific columns |

**Idea 175 and option (a) are alternatives on one body.** Both re-index the same piece rows, so their tables
multiply: tier A on S512+PP is 2,816 piece rows + 608 links = 3,424 rows x 1,024 bytes = **3.5 MB**; on H512+PP's
four regions (M4) it would be 4 x 2,816 + 608 = 11,872 rows = **12.2 MB**, against option (a)'s 3,680 rows (3.8 MB)
and r8brft1's 1,376 (1.4 MB). With option (a) promoted, idea 175 would need its rare states kept as extra rows
instead, as the proposal says (its "Third" risk).

## 1. Data and label

- **Positions, two held-out sets** (neither is in r8brft1's training data, g4s1):
  - **g4s2-val**, retrain 8c's validation file (`~/fork-data/8c/val/bl-g4s2-val.vf`, SHA-256 184596c6...0bf2f; 2,700
    games: g4s1-val's 2,160 plus 60 held games of each newer part), its blend copy: the file 8c's gates and validation
    loss read. 103,254 positions after the training filter. The primary set, as the brief suggested: it is the
    validation set of the recipe whose target the label copies.
  - **g4c**, the first 600,000 kept positions of `td90-g4c-w00.vf` (8c's TD(0.9) copy of g4c's first file, SHA-256
    e5a91090...962af): g4c was generated after r8brft1 was trained (labelled by r8brft1's own search), so it is
    held out from r8brft1 too, and six times larger. Used for power: at 0.5% the line is about 25 standard errors
    above the g4s2-val estimates but the rarest states (pawn-attacked rook and queen, 0.005 per position) have
    only about 500 instances in 103k positions.
- **Positions as training sees them:** `fork-train dump` (the trainer's own reader and filter: not in check, no
  capture or promotion played, |score| <= 20,000, unsaved records dropped; side-to-move relative), the build at
  ~/fork-runners/scratch-r3kr4 (the option (a) branch's trainer; the filter is unchanged since 8b).
- **Label = the trainer's target as retrain 8c defines it**: result weight 0 on the label copies (8c plan,
  "standard recipe since 8b"), so the target is sigmoid(s / 92) of the copy's score s, where the copy is the blend
  copy (s such that sigmoid(s / 92) = 0.5 sigmoid(score / 92) + 0.5 result: g4s2-val) or the TD(0.9) copy (g4c). The
  trainer's mapper: `target = (1 - w) * sigmoid(score / S) + w * result` (tools/train/src/main.rs), w = 0, S = 92.
- **The prediction**: r8brft1's output in the trainer's space, sigmoid(y / (QA x QB)), y its integer output before
  the scale (the net's S = 88 only rescales centipawns). Computed in numpy with models.py's features and bucket;
  **checked against Fork's own `evalfens`** (phase-4 d63ddc6's clang-release build, r8brft1) on every 10th g4s2-val
  position (10,326) and every 60th g4c position (10,000): **0 mismatches**.
- **Residual** r = label - prediction: variance 0.0199 on g4s2-val (label variance 0.149), 0.0107 on g4c (TD labels
  are smoother; label variance 0.138); mean +0.003 and +0.001.

## 2. Residual study (idea 175, ranking only)

**Method** (tools/nnue/state_rows_study.py; R36's scale, "explains >= 0.5% of the residual variance", R36 being the
think tank's rule for choosing an input family, phase-c-synthesis.md; no R36 tool existed, so this is new code).
- Each tier A state gets an additive table over (piece colour relative to the side to move, piece type, square from
  the side to move, state value), fitted beside a base table over (colour, type, square) by ridge least squares, one
  column per cell, r centred. Shares are **held out**: positions in blocks of 2,000 consecutive positions (whole games
  but at the edges), 8 folds by block; each fold is predicted from the other seven. The base table's ridge strength
  is chosen alone, then the state table's with the base's kept (grids 1 to 1e5 and to 1e7), each by the pooled
  held-out error.
- **A state's share** = (held-out SSE of the base table - held-out SSE of base + state table) / held-out sum of
  squares of r, pooled over the folds; +- is the standard error over the 8 folds. Also "pooled over squares": the
  state's table with one value per colour, type and state (a low-variance check of any average effect).
- **States** (the proposal's tier A): a knight, bishop, rook or queen attacked by an enemy pawn; a knight or bishop
  defended by an own pawn; a rook's file closed (an own pawn), half-open (no own pawn, an enemy one) or open; the
  king's shield class, min(3, own pawns on its own and the neighbouring files one or two ranks ahead); a passed pawn
  (no enemy pawn ahead on its own or a neighbouring file).
- **The checker can fail (and first did)**: `--inject FAMILY SIZE` adds a known effect to r. The first version (one
  ridge strength for both tables) found only 0.013% of an injected 0.49% (the base table's overfitting drove the
  common strength to the top of the grid); the version used here finds **0.475% of the injected 0.49%** for "a knight
  attacked by an enemy pawn" (ranked first; pooled 0.597%), and for a common state ("defended by an own pawn", 1.95%
  of the variance injected, much of it a piece-count effect the base table absorbs) ranks that family first at
  0.689%.

**Results** (share of residual variance, %, held out; the line is 0.5):

| State (family) | g4c, by square | g4c, pooled | g4s2-val, by square | g4s2-val, pooled | ridge (g4c / g4s2-val) |
|---|---|---|---|---|---|
| bishop attacked by an enemy pawn | 0.032 +- 0.014 | 0.044 +- 0.010 | 0.003 +- 0.006 | 0.003 +- 0.005 | 30 / 100 |
| attacked by an enemy pawn (N, B, R, Q together) | 0.025 +- 0.011 | 0.090 +- 0.022 | 0.008 +- 0.004 | 0.034 +- 0.017 | 100 / 300 |
| passed pawn | 0.012 +- 0.003 | 0.019 +- 0.005 | -0.000 +- 0.001 | 0.009 +- 0.011 | 1e4 / 1e5 |
| rook attacked by an enemy pawn | 0.003 +- 0.005 | 0.034 +- 0.012 | 0.002 +- 0.031 | 0.040 +- 0.017 | 30 / 3 |
| king shield class | 0.001 +- 0.003 | -0.001 +- 0.001 | -0.001 +- 0.003 | -0.002 +- 0.003 | 3e4 / 1e5 |
| queen attacked by an enemy pawn | 0.001 +- 0.001 | 0.003 +- 0.005 | 0.000 +- 0.001 | -0.000 +- 0.000 | 300 / 300 |
| bishop defended by an own pawn | 0.000 +- 0.001 | 0.000 +- 0.001 | 0.017 +- 0.016 | -0.002 +- 0.001 | 3e4 / 3e3 |
| knight attacked by an enemy pawn | -0.000 +- 0.000 | 0.012 +- 0.010 | 0.005 +- 0.003 | 0.004 +- 0.003 | 1e5 / 300 |
| defended by an own pawn (N, B together) | -0.000 +- 0.000 | 0.001 +- 0.001 | 0.003 +- 0.014 | -0.006 +- 0.003 | 1e5 / 1e4 |
| knight defended by an own pawn | -0.000 +- 0.000 | 0.000 +- 0.001 | -0.000 +- 0.002 | -0.005 +- 0.003 | 1e5 / 1e5 |
| rook file state | -0.000 +- 0.001 | 0.005 +- 0.003 | 0.001 +- 0.003 | 0.001 +- 0.007 | 1e5 / 3e4 |
| **all tier A states together** | 0.006 +- 0.005 | 0.107 +- 0.020 | 0.001 +- 0.003 | 0.000 +- 0.016 | 3e4 / 1e5 |

The base table alone explains 0.026% (g4c) and 0.018% (g4s2-val) held out. "All together" takes one ridge strength
for every state's cells, so it sits below the attacked-by-a-pawn family alone (whose cells want a weak penalty
while the others want a strong one).

**Ranking** (g4c, by square, the larger set): bishop attacked by an enemy pawn 0.032%; the attacked family 0.025%;
passed pawn 0.012%; then everything at or below 0.003%. The only states above two standard errors on g4c are the
attacked family (bishop) and the passed pawn, and neither reaches a tenth of the line; on g4s2-val nothing does. **By
the proposal's kill line every tier A state is killed** (the owner decides). The proposal's main risk, "the layer
already forms these conjunctions", is what the data shows for r8brft1: its residual carries no additive
(piece, square, state) structure. What this study cannot see (stated, not measured): interactions a hidden layer
could use beyond an additive table, which is the proposal's argument E11 for folding the states into the
accumulator rather than adding them linearly.

**Frequencies** (the "rarest bit" question; g4c, 600,000 positions; "cells" are (colour, square) pairs with at
least 100 pieces of the type; per-million is set instances per million positions, per cell):

| State | share of the pieces of the type | per position | cells never set | per-million per cell: median |
|---|---|---|---|---|
| knight attacked by an enemy pawn | 1.56% | 0.024 | 39 of 128 | 31.7 |
| bishop attacked by an enemy pawn | 0.95% | 0.016 | 37 of 128 | 35.0 |
| **rook attacked by an enemy pawn** | **0.18%** | 0.005 | 34 of 128 | 14.2 |
| **queen attacked by an enemy pawn** | 0.52% | **0.005** | 48 of 128 | **3.3** |
| knight defended by an own pawn | 35.5% | 0.539 | 35 of 128 | 196 |
| bishop defended by an own pawn | 16.8% | 0.287 | 33 of 128 | 299 |
| rook file open / half-open / closed | 27.9% / 18.5% / 53.6% | 0.73 / 0.48 / 1.39 | 0 | 4,068 / 1,705 / 2,110 |
| king shield 0 / 1 / 2 / 3 | 28.3% / 31.0% / 27.4% / 13.3% | 0.57 / 0.62 / 0.55 / 0.27 | 0 / 30 / 41 / 67 of 126 | 2,926 / 1,163 / 115 / 0 |
| passed pawn | 11.6% | 1.03 | 0 of 96 | 11,033 |

The rarest state is **attacked by an enemy pawn on a rook or a queen** (0.005 per position each; the queen's median
cell 3.3 per million, about 3,900 instances per cell in 1.17 B training positions; the training filter keeps
positions whose best move is quiet, so a queen attacked by a pawn appears only when it then moves away quietly).
The "never set" counts include cells no position can reach (a piece on its own eighth rank cannot be attacked by an
enemy pawn; a shield of three needs pawns ahead, so none on the eighth rank).

## 3. Idea 176's column count (same data pass)

Per hidden column j (512, each used by both perspectives' halves), output bucket k and queen state (a queen of
either side on the board, or none): utilisation U = sum over both halves of |w_out[k][half][j]| x mean(v^2) over the
positions, v the clipped sum, in centipawns (/ QA x S / (QA x QB)), as the proposal defines it (output weight x mean
squared activation). The **queen ratio** compares a column's U with queens on and off at matched buckets: buckets 1-5
(the only ones holding both: 0 has no queens, 6-7 always a queen), the queens-off rows weighted by the queens-on
bucket mix. g4c's numbers (g4s2-val's agree to the second digit):

- Queens on in 48.4% of positions; 600,000 positions.
- **No dead column**: the least-used column has 0.074 cp, the median 1.32 cp, the most-used 48.9 cp (column 174).
  The use is concentrated: the top 8 columns hold 15.4%, the top 64 44.6%, the top 128 61.8%, the top 256 82.5%.
- **Queen ratio**: median 1.27; 5th-95th percentile 0.46-9.0. **74 columns are used 4x or more as much with queens
  on** (162 at 2x), against **5 columns 4x or more with queens off** (38 at 2x). Among the 256 most-used columns, 42
  are 2x queens-on and 22 2x queens-off.
- The most regime-specific heavy column is **69** (11.7 cp overall; 31.9 cp with queens on, 2.3 off; ratio 13.7);
  others: 157 (8.9 / 0.45), 225, 231, 12, 81, 431. The most queens-off-leaning: 232 (4.4 / 12.5), 125 (15.8 / 23.3),
  459, 169, 483, 428, 178. The heaviest columns are shared (174, 403, 376, 133, 111, 306, 151: ratios 0.88-1.14).
- By bucket: the top 64 columns hold 63% of bucket 0's use (no queens, few pieces) and 42-48% of buckets 3-7's; each
  bucket's column profile correlates 0.77-0.97 with the overall one (bucket 0 0.78, bucket 7 0.80).

**Reading:** r8brft1 already has a block of queens-on-specific columns (about 75, mostly lightly used, with one
heavy one, 69) that are close to silent with queens off, and few queens-off-specific ones. That is the proposal's
stated risk for idea 176 ("the net already silences regime-specific columns through the queen rows' large
weights"): the specialisation it would add exists in part. Whether cloning would still help is not answered by
this count (it is a look, not a falsifier: the proposal's step 2 is a trainer-only fine-tune).

## 4. The zero-delta speed prototype (idea 175, architecture 11)

**Design** (commit 87d40bb on proto/i175-state-rows, and 2161580's measurement build `sr_find_only`; round 3's
method, proto/r3-king-a/-b/-c):
- Architecture 11 = S512+PP whose 768 piece rows become 2,816: a piece's row is (colour, type, square, its state),
  the states of a type in consecutive 64-row blocks (pawn 2, knight 4, bishop 4, rook 6, queen 2, king 4: 22 blocks
  per colour); the 608 links follow. Other architectures' indices are unchanged (state 0, one block per type).
- A piece's state depends only on its square and the pawns. The delta carries its own pieces' states (computed at
  the push from the pawns before and after the move: two or three table lookups) and, on pawn changes (33.5% of
  perspective updates on the bench), the board before the move. **The flipped pieces are found once per pawn-changing
  delta in the evaluation walk** (lazily, as link changes are, then shared by both perspectives): set-wise, the
  squares whose enemy-pawn attack or own-pawn defence changed, the rooks on a file whose pawns changed, the king
  if its shield's pawns changed, and the pawns whose passed status changed; each candidate's state is recomputed
  before and after, and each flip is one row out and one row in.
- The net: `tools/nnue/state_rows_net.py make nets/r8brft1.fnet sr-zero.fnet` (every state's rows equal to the base
  row: a factored training's warm start with zero deltas; 3,523,808 bytes, SHA-256 e6dc3616...022bd).

**Bench identity:** the architecture 11 build with the zero-delta net: **5,386,021 / 5ecd49d976e215e1**, r8brft1's
(tests/bench-r8brft1.ref) and phase-4 d63ddc6's. (The brief's numbers; tests/bench.ref, 6,346,280, is the bootstrap
evaluator's reference.) The find-only build gives the same. The default build (r8brft1, architecture 8) is
unchanged and passed the pre-commit quick check at both commits (clang-release, the core and quick-search suites,
bench parity).

**Correctness checks:**
1. **Incremental against refresh**, Debug build (FORK_DEBUG: every evaluation's sums compared with a refresh from the
   board) on a **perturbed** net whose state rows differ (`--perturb`: each state > 0 row + a deterministic -3..3,
   held within each unit's largest piece weight so the reader's int16 bound holds; SHA-256 8feb7fce...6d3c): the full
   bench ran without a mismatch, **5,374,516 / f9aa3c836b0c4b29**, on 87d40bb.
2. **The check can fail:** with a deliberate fault (find_state_flips forgetting rooks on a file whose pawns changed;
   a temporary edit, reverted) the Debug bench trapped at the first mismatch (illegal instruction, exit 132).
3. **The refresh against an independent evaluation:** `state_rows_net.py evals` computes each position's evaluation
   in Python with the states found square by square from python-chess's attack queries (written apart from the
   engine's set-wise code); on the perturbed net it equals the architecture 11 build's `evalfens` on all **2,512**
   positions (the 446 parity positions and 2,066 g4s2-val positions; the perturbed net's evaluation differs from
   r8brft1's in 2,244 of them). That check can fail too: with the shield rule faulted (one rank ahead only) 311 of
   600 positions mismatch. The zero-delta build's `evalfens` equals phase-4's on all 2,512.

**Work per update** (stats builds, FORK_SEARCH_STATS, the bench): rows per perspective update **3.092 (A) -> 3.530
(B), +14.2%**, at the same 8,473,527 updates, 3,613,642 evaluations and 33.5% pawn-changing updates. So a
pawn-changing update carries about 1.3 extra rows (0.65 flips each needing two), far above the proposal's "about 0.1
extra row operations per push" estimate.

**Speed** (bench/ab_search.py's Side via the round 3 paired wrapper, a scratch copy; A = phase-4 d63ddc6 with
r8brft1, B = 87d40bb with the zero-delta net; both bench 5,386,021 / 5ecd49d976e215e1, checked every run; WSL
Ubuntu, clang 21.1.8, Release, LTO, x86-64-v3, FORK_BUILD_TESTS=OFF, core 4, interleaved; paired ratio = geometric
mean of B/A per round with a normal 95% interval on the log ratios; taken under ~/fork-jobs/
nps-measure.lock; the machine was shared: WSL load average 0.9-1.3, Windows CPU load about 50% from other agents'
jobs at one check, hence the wide A/A intervals):

| Session (EST) | A/A before | **A/B: B = 87d40bb, zero-delta net** | B = 2161580 sr_find_only (finding, no state rows) | A/A after |
|---|---|---|---|---|
| 1, 12:28-12:39 PM | 0.996 (0.935-1.061), 40 rounds | **0.905 (0.885-0.925)**, 60 rounds; median -8.2%, best -9.7% | not run | 0.994 (0.962-1.026), 40 rounds |
| 2, 12:48-12:58 PM | 0.991 (0.971-1.013), 30 rounds | **0.913 (0.894-0.931)**, 40 rounds; median -9.9%, best -11.0% | 0.923 (0.887-0.961), 40 rounds; median -5.6%, best -5.4% | 1.001 (0.985-1.017), 30 rounds |

(A first try at 12:24 PM ran its two A/A pairs, 1.044 (0.970-1.125) and 1.009 (0.977-1.042) at 20 rounds, but its
A/B never started: a script error; its results are not used.)

**Against the kill line: 0.905 and 0.913, both intervals entirely below 0.95** (and straddling the speed gate's
0.90). At 0.913 a fixed-node screen would need about +15 Elo (-118 log2 r) to break even.

**Where the cost is.** The find-only build (2161580, `-DFORK_EXPERIMENT=sr_find_only`, zero-delta nets only: it keeps
the push's states, the walk's flip finding and the refresh's piece_state, but uses state 0's rows and applies no
flip row) runs at 0.923, so the finding costs about 7-8% and the extra rows about 1% more (0.913 / 0.923 = 0.989,
inside the noise). A perf profile of one bench each (4,000-4,400 samples, single runs, so rough) agrees:
FeatureStack::push_move rises from 6.5% of samples (A, with its inlined part) to 7.9% (B: the states of the moved
and captured pieces at every push, and the board copy on pawn moves), and find_state_flips takes 3.3%. The
proposal's estimate (0.96-0.98) assumed about 0.1 extra rows per pawn push and a cheap finder; measured, a
pawn-changing update brings 1.3 extra rows and the finder is the larger cost. A cheaper finder (states computed
lazily in the walk instead of at every push, flips found from the Position at the push, no board copy) is the
obvious lever; it was not tried. The rows alone appear to cost about 1% (0.989, inside the noise), so whether this
design can pass 0.95 depends on how cheap the finding can be made, not on the rows (UNVERIFIED: no cheaper finder
was built or measured).

## 5. New names (for the coordinator's screen; none screened yet)

| Name | Kind | Where |
|---|---|---|
| `NetStateRows`, `NetKindStates`, `NetSideBlocks`, `NetPieceRows` | constants | src/eval/nnue/net_shape.hpp |
| `kind_block` | function | net_shape.hpp |
| `piece_state`, `find_state_flips` | functions | accumulator.hpp/.cpp |
| `StateFlips` (members `count`, `piece`, `square`, `before`, `after`) | struct | accumulator.hpp |
| `removed_state`, `added_state`, `pieces_before` | FeatureDelta members | accumulator.hpp |
| `flips` | FeatureStack::Entry member; columns_for / advance_perspective parameter | accumulator.hpp/.cpp |
| `sr_find_only` (`FORK_EXP_sr_find_only`) | measurement build variant | accumulator.cpp |
| `StateMasks` (`passed_span`, `shield`), `make_state_masks`, `Masks`, `pawn_attack_set`, `passed_pawns`, `file_fill`, `set_states`, `pawns_now` | internal | accumulator.cpp |
| `state_rows_net.py` (`make`, `evals`, `state_of`, `STATES`, `STARTS`, `SIDE_BLOCKS`, `STATE_ROWS`, `--perturb`) | tool | tools/nnue |
| `state_rows_study.py` (`FAMILIES`, `ATT`, `DEF`, `FILE`, `SHIELD`, `PASSED`, `COLUMNS`, `BLOCK`, `FOLDS`, `LAMBDAS`, `BASE_LAMBDAS`, `FILE_OF`, `UP_SPAN`, `DOWN_SPAN`, `SHIELD_UP`, `SHIELD_DOWN`, `masks`, `states`, `read_dump`, `decode`, `board_of`, `load_net`, `evaluate`, `fen_of`, `check_evalfens`, `gram`, `fold_parts`, `heldout_sse`, `family_share`, `study`, `pooled_share`, `frequencies`, `utilisation`, `--inject`) | tool | tools/nnue |

No new search constant. The study's grid values (BLOCK 2,000, FOLDS 8, the ridge grids) are analysis settings, not
engine constants; the perturbation's -3..3 and its multiplier are check-net settings (round 3's proto_expand.py used
the same form).

## 6. Not run, and caveats

- No training, screen, SPRT or UHO diagnostic; no tier B (king-pressure) states; no factored trainer, Rust or
  converter work.
- The prototype is not optimised beyond the lazy, shared flip list (no incremental attack sets, no SIMD in the
  finder); an AVX-512 (native) pair, a runner (GitHub) pair and in-game (non-bench) flip rates were not measured.
- The tests of the NNUE suite were not extended to architecture 11 (FORK_BUILD_TESTS=OFF for its builds, as in round
  3); the checks are the Debug bench, the fault injection and the independent evaluation above.
- The residual study measures additive (piece, square, state) structure in r8brft1's residual on two held-out sets;
  it does not measure what a trained state-folded net would gain through hidden-layer interactions. The labels are
  r8brft1's or older nets' own searches (TD or blend), not deep labels (R36 named X7's deep relabel; that set does
  not exist yet).
- state_rows_study.py needs numpy, which the repository's .venv does not have (a scratch venv held numpy 2.5.4 and
  python-chess 1.11.2).
- `fork-train dump` came from the build at ~/fork-runners/scratch-r3kr4 (its filter function is the trainer's
  `filter()`, unchanged on phase-4).

## 7. How it was produced (2026-11-14, about 11:30 AM to 1:15 PM EST)

- Worktree ~/fork-runners/scratch-i175/wt (branch proto/i175-state-rows), baseline worktree scratch-i175/base
  (phase-4 d63ddc6, detached).
- Dumps: `fork-train dump --data bl-g4s2-val.vf --count 100000000` and `--data td90-g4c-w00.vf --count 600000`.
- Study: `python -I tools/nnue/state_rows_study.py DUMP --net nets/r8brft1.fnet --out OUT.json --fork <phase-4
  clang-release fork.exe> --check-every 10|60`, below-normal priority, at most 3 BLAS threads; injection checks with
  `--inject 'pawn-attacked N' 0.062` and `--inject 'pawn-defended (N,B)' 0.02` on g4s2-val. Run times: about 2 min
  (g4s2-val) and 6 min (g4c).
- Builds (WSL Ubuntu): `cmake -S . -B build/v3-NAME -G Ninja -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_BUILD_TYPE=Release
  -DFORK_ARCH=x86-64-v3 -DFORK_BUILD_TESTS=OFF [-DFORK_NET=sr-zero.fnet]`, with GIT_DIR pointed at the worktree's
  Windows git directory so the binaries carry their commits; stats builds with `-DFORK_SEARCH_STATS=ON`; Debug checks
  with `-DCMAKE_BUILD_TYPE=Debug -DFORK_SANITIZE=OFF`.
- Speed: `python3 -I ab_paired.py base A/fork B/fork d63ddc6 87d40bb|2161580 ROUNDS 4 [--allow-identical]
  [--b-variant sr_find_only]` (the round 3 wrapper, a scratch copy given a B-variant option).
- Profile: `perf record` of one bench per binary on core 4; `perf report --sort symbol` addresses resolved with
  addr2line and summed by function.
