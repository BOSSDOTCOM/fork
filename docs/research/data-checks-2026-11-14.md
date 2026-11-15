# Data checks for the network shortlist's ranks 3 and 4 (2026-11-14)

The owner's order (2026-11-14, about 8:00 PM EST): "(3) run the cheap checks for ranks 3 and 4 (disagreement
share by bucket; piece-count histogram) and report before any arm". The checks and their kill lines are from
docs/research/network-survey-2026-11/shortlist.md §4, ranks 3 (C15, the result/score disagreement filter) and 4
(C14, piece-count balancing). This is offline CPU work on Fork's own data only: no training, no engine change, no
arm built.

## Verdicts

- **Rank 3, the result/score disagreement filter: KILL.** Every X and every bucket falls under the 1% kill line,
  measured both on the label the control trains on and on the stored search score. At X = 200 cp the share of
  kept positions where the side to move's score is at least +200 and it lost, or at most −200 and it won, is
  **0.009%** for the trained label and **0.19%** for the stored search score. The largest bucket value is 0.42%
  (bucket 7, stored score). A filter at that margin would remove about 1 position in 500. The kill line is not
  close at X = 200 cp and above. The only values over 1% are on the stored score at X = 100 cp in buckets 4-7
  (1.08-1.85%). That is a one-pawn margin, inside what a 20,000-node score misjudges routinely, and still 0.93%
  over all buckets.
- **Rank 4, piece-count balancing: KILL by output bucket.** Every output bucket is within 1.5x of the mean:
  bucket shares run from 0.74x (bucket 7) to 1.28x (bucket 6). By piece count, bins 6 to 30 are within 0.82x to
  1.39x. Only the tails fall outside 1.5x: 3 and 5 pieces (0.27x and 0.36x, the Syzygy slice only), no 4-piece
  positions at all, and 31 and 32 pieces (0.32x and 0.36x, the opening). These tails are structural, not an
  imbalance a selection rule can fix (§3.3). The kill line says "every bucket"; this report reads it as the
  output buckets. **For the owner:** if it was meant per piece-count bin, those four tail bins fail it.

## 1. Data, reader and label

- **Data: retrain 8c A1's control, all of it.** The 196 files c2 trained on
  (`~/fork-data/8c/a1-out/result/c2/files.json`, the same list as c1's): 83 TD(0.9) copies (td90-, the parts
  labelled by S512ppr3 or later), 103 blend copies (bl-, the older parts) and the 10 files of the fresh Syzygy
  slice slice1b. Each file's sealed original (and, for a TD part, its td90- copy) was found on this machine by its
  size in the committed manifests (origin/retrain/8c-q data/manifests). Every one of the 279 files' SHA-256 was
  then checked against those manifests (§5).
- **Reader: Fork's trainer.** `fork-train stats` and `fork-train dump` (tools/train), from the build at
  `~/fork-runners/scratch-r3kr4/target` (the round 3 worktree's build of 2026-11-14). Its `filter()`, `dump` and
  `stats` code match retrain/8c-q's main.rs line for line, and its viriformat and bulletformat pins match
  8c-q's Cargo.lock. So the kept set is exactly the trainer's: not in check, best move not a capture or promotion,
  |score| <= 20,000, saved (the unsaved marker lies beyond the limit).
  - `stats` ran on **every kept position of all 196 files: 1,200,189,032**. It gives the exact counts by game
    phase and piece count. A TD copy keeps exactly its original's set: `stats` was identical on g4c-w00 and
    td90-g4c-w00 (8,099,887 each).
  - `dump` gave the side to move's score and result for **the first 300,000 kept positions of each file** (all
    of a smaller file): **52,258,397 positions (4.4%)**. Each file's sample is weighted by its exact kept count,
    so the mix is the trainer's. As a check, the weighted sample's bucket shares match the exact ones within 0.1
    point (e.g. bucket 7: 9.3% against 9.31%).
- **Label: the control's trained target**, at result weight 0, S = 92:
  - TD parts: the td90- copy's score. The original and its copy were dumped side by side, and every line's
    pieces and result were equal (0 mismatches in 318 M kept, 52 M compared). So the same position also gives
    its stored search score.
  - Blend parts: td_labels.py's blend at W = 0.5 (r8b-blend.json), computed from the original's score and
    result by blend_pair and pair_to_score. Checked against the real copy bl-g4s2-val.vf: all 103,254 kept
    positions are equal except 52 one-move games at ±2,000 that the tool copies unchanged (2,000 against 2,064,
    the same sign; no count here changes).
  - The slice: its stored score, ±2,000 or 0, the table's WDL.

  The default r8ceplo2 then had the rft-ep-lo fine-tune, whose target on 8 or more pieces *is* the result. Its
  disagreement there is zero by construction, so the control's target is the one that can disagree.
- **Output bucket:** the trainer's and engine's selector, `table[phase]` with s512pp.json's 25-entry table
  (0,0,0,0,1,1,2,2,3,3,3,3,4,4,4,4,5,5,5,5,6,6,6,7,7). The phase is knights and bishops 1, rooks 2, queens 4,
  capped at 24 (tools/train `Board::phase`; the engine's `phase_bucket` reads the net's table).
- Run: 7:54 to about 9:00 PM EST, WSL, nice 19, 3 worker processes. Scripts in
  `~/fork-runners/scratch-datachecks/` (build_table.py, datachecks.py, summarise.py, verify.py, sha_check.py; not
  in the repository: one-off).

## 2. Rank 3: disagreement by output bucket

**Definition.** A kept position disagrees at margin X when the side to move's score is >= +X and the side to
move lost, or <= −X and it won. Draws with |score| >= X are shown beside the main figures but are not part of
the owner's definition.

**Why X = 200 is the headline.** At S = 92, +200 cp is sigmoid(200/92) = 0.90: the label expects 90% of the
points. A loss from there contradicts the label rather than just missing a close call. 400 cp (0.987) and 800 cp
(0.9998) bracket it from above. Generation adjudicates at 700 cp for 8 plies, so a lost game that holds +800
anywhere is nearly impossible, and the 800 column is a sanity check. X = 100 (0.75) was added below the asked
sweep to see where the share would reach 1%.

**The trained label** (td90 copy / blend copy / slice score):

| Bucket (phase) | Kept share | X = 100 | X = 200 | X = 400 | X = 800 | draws, 100 | draws, 200 | draws, 400 |
|---|---|---|---|---|---|---|---|---|
| 0 (0-3) | 11.3% | 0.008% | 0.002% | 0.000% | 0.000% | 0.74% | 0.07% | 0.00% |
| 1 (4-5) | 14.7% | 0.008% | 0.001% | 0.000% | 0.000% | 0.66% | 0.09% | 0.00% |
| 2 (6-7) | 11.4% | 0.026% | 0.002% | 0.000% | 0.000% | 0.95% | 0.09% | 0.00% |
| 3 (8-11) | 15.3% | 0.050% | 0.005% | 0.000% | 0.000% | 0.90% | 0.09% | 0.00% |
| 4 (12-15) | 11.3% | 0.096% | 0.009% | 0.000% | 0.000% | 0.93% | 0.08% | 0.00% |
| 5 (16-19) | 10.6% | 0.122% | 0.016% | 0.000% | 0.000% | 0.81% | 0.08% | 0.00% |
| 6 (20-22) | 16.0% | 0.181% | 0.017% | 0.000% | 0.000% | 0.86% | 0.08% | 0.00% |
| 7 (23-24) | 9.3% | 0.209% | 0.028% | 0.000% | 0.000% | 0.75% | 0.11% | 0.00% |
| **all** | 100% | **0.085%** | **0.009%** | **0.000%** | **0.000%** | 0.82% | 0.09% | 0.00% |
| TD parts (26.5% of kept) | | 0.321% | 0.035% | 0.000% | 0.000% | 3.08% | 0.33% | 0.00% |
| blend parts (71.3%) | | 0.000% | 0.000% | 0.000% | 0.000% | 0.01% | 0.00% | 0.00% |
| slice (2.2%) | | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

The blend parts cannot disagree, by construction. At W = 0.5 a lost game's target is at most 0.5 (score <= 0) and
a won game's at least 0.5. A drawn game's target lies in [0.25, 0.75], so |label| <= 101 cp. The TD(0.9) labels
lean toward the result too. So the recipe already neutralises what this filter would remove.

**The stored search score** (the originals; what a peer-style filter on the search eval would read):

| Bucket (phase) | X = 100 | X = 200 | X = 400 | X = 800 | draws, 100 | draws, 200 | draws, 400 |
|---|---|---|---|---|---|---|---|
| 0 (0-3) | 0.128% | 0.025% | 0.000% | 0.000% | 5.70% | 0.72% | 0.01% |
| 1 (4-5) | 0.150% | 0.032% | 0.002% | 0.000% | 4.94% | 0.92% | 0.06% |
| 2 (6-7) | 0.388% | 0.076% | 0.003% | 0.000% | 6.15% | 1.01% | 0.06% |
| 3 (8-11) | 0.648% | 0.143% | 0.005% | 0.000% | 5.41% | 0.90% | 0.04% |
| 4 (12-15) | 1.079% | 0.200% | 0.005% | 0.000% | 4.99% | 0.82% | 0.03% |
| 5 (16-19) | 1.526% | 0.362% | 0.016% | 0.000% | 4.26% | 0.89% | 0.03% |
| 6 (20-22) | 1.847% | 0.331% | 0.008% | 0.000% | 3.98% | 0.66% | 0.01% |
| 7 (23-24) | 1.811% | 0.417% | 0.003% | 0.000% | 3.27% | 0.86% | 0.01% |
| **all** | **0.928%** | **0.191%** | **0.005%** | **0.000%** | 4.86% | 0.84% | 0.03% |
| TD parts | 0.681% | 0.120% | 0.002% | 0.000% | 4.10% | 0.60% | 0.01% |
| blend parts | 1.048% | 0.223% | 0.007% | 0.000% | 5.29% | 0.96% | 0.04% |

The two directions are balanced: on the stored score at X = 200, 0.099% are lost at >= +200 and 0.092% won at
<= −200 (on the label, 0.005% each). The share rises with phase, about 15x from bucket 0 to bucket 7 at X = 200.
That fits idea 180's falling score-to-result scale: middlegame scores say less about the result.

**Reading.** The kill line is "under 1%: nothing to filter". At the headline X = 200 the filter would remove
0.009% of what the control trains on, or 0.19% if it read the search score. That is too few positions to move a
net. Even adding the draws (not part of the definition), the stored-score share at X = 200 is 1.03%. On the
trained label it is 0.10%.

## 3. Rank 4: kept positions by output bucket and piece count (exact, all 1,200,189,032)

### 3.1 By output bucket

| Bucket (phase) | Kept positions | Share | Share / mean (12.5%) |
|---|---|---|---|
| 0 (0-3) | 135,551,729 | 11.29% | 0.90x |
| 1 (4-5) | 176,794,135 | 14.73% | 1.18x |
| 2 (6-7) | 137,526,002 | 11.46% | 0.92x |
| 3 (8-11) | 183,037,393 | 15.25% | 1.22x |
| 4 (12-15) | 135,557,549 | 11.29% | 0.90x |
| 5 (16-19) | 128,183,831 | 10.68% | 0.85x |
| 6 (20-22) | 191,789,990 | 15.98% | 1.28x |
| 7 (23-24) | 111,748,403 | 9.31% | 0.74x |

Range 0.74x to 1.28x, inside [0.67x, 1.5x]. The table was fitted to balance these buckets (s512.json, fitted on
g2s1), and it still does on today's data.

### 3.2 By piece count (kings included)

Mean over the 29 populated bins: 41,385,829. Bins 2 and 4 are empty.

| Pieces | Kept | Share | / mean | | Pieces | Kept | Share | / mean |
|---|---|---|---|---|---|---|---|---|
| 3 | 11,254,848 | 0.94% | 0.27x | | 18 | 43,330,238 | 3.61% | 1.05x |
| 5 | 14,745,152 | 1.23% | 0.36x | | 19 | 41,802,786 | 3.48% | 1.01x |
| 6 | 44,313,819 | 3.69% | 1.07x | | 20 | 42,802,478 | 3.57% | 1.03x |
| 7 | 57,348,932 | 4.78% | 1.39x | | 21 | 41,315,280 | 3.44% | 1.00x |
| 8 | 52,936,218 | 4.41% | 1.28x | | 22 | 43,773,056 | 3.65% | 1.06x |
| 9 | 55,211,148 | 4.60% | 1.33x | | 23 | 41,869,951 | 3.49% | 1.01x |
| 10 | 51,879,335 | 4.32% | 1.25x | | 24 | 46,153,377 | 3.85% | 1.12x |
| 11 | 51,150,246 | 4.26% | 1.24x | | 25 | 42,732,262 | 3.56% | 1.03x |
| 12 | 48,990,972 | 4.08% | 1.18x | | 26 | 49,006,529 | 4.08% | 1.18x |
| 13 | 47,717,923 | 3.98% | 1.15x | | 27 | 41,956,268 | 3.50% | 1.01x |
| 14 | 46,725,922 | 3.89% | 1.13x | | 28 | 49,271,245 | 4.11% | 1.19x |
| 15 | 45,335,583 | 3.78% | 1.10x | | 29 | 33,754,569 | 2.81% | 0.82x |
| 16 | 44,868,068 | 3.74% | 1.08x | | 30 | 38,415,606 | 3.20% | 0.93x |
| 17 | 43,316,849 | 3.61% | 1.05x | | 31 | 13,328,211 | 1.11% | 0.32x |
| | | | | | 32 | 14,882,161 | 1.24% | 0.36x |

Exact phase histogram (phase 0-24): 11150884 16882000 64727752 42791093 99915108 76879027 88537609 48988393
60085713 40826155 49309382 32816143 45192875 28190859 39181028 22992787 30651086 24196977 38732746 34603022
62210192 47608332 81971466 43324275 68424128.

### 3.3 Reading

- **The output buckets pass the kill line.** Every head sees between 0.74x and 1.28x of an equal share, so there
  is nothing to balance on the axis the net's heads use.
- **The piece-count tails are structural.** Generation ends a game at Syzygy table entry (5 pieces), so
  self-play has no position of 5 pieces or fewer. Every 3- and 5-piece position is the slice's. By endgame_slice.py's
  design the slice is half KPK/KQK/KRK and half the table-entry signatures Fork's games reach, which are 5-piece,
  so **no kept position has 4 pieces** (a gap, not an imbalance). 31 and 32 pieces are the first plies after the
  openings. In play, 5 pieces or fewer is a table probe (TCEC has 7-piece tables), and 31-32 is book. Selection
  can only drop positions, so balancing toward these tails would mean discarding most of bins 6-30 to raise
  shares the net barely uses.
- The joint sample (summarise.py's output; not tabled here) shows each bucket spans about 10 piece counts. Bucket
  0's positions are 3-12 pieces, bucket 7's 23-32.

## 4. What an arm would look like (not built; both checks killed)

- **Rank 3, if it had passed:** a trainer filter option (tools/train, `Filter` plus one predicate in the reader):
  drop a kept position when the side to move's stored search score is >= +X and it lost, or <= −X and it won.
  The flag needs a test showing that X off reproduces the control's kept set. It would run as a 60-superbatch
  fine-tune pair on r8ceplo2 (2 seeds, about 0.8 GPU-h) against an unfiltered same-recipe pair, read on the
  held-out endgame gate too (E9), then its STC SPRT. At X = 200 it would drop about 2.3 M of 1.2 B positions,
  most of them not even mislabelled under the TD/blend targets. If wanted, a variant that drops draws with
  |score| >= 200 (0.84% on the stored score, 0.09% on the label) is the only form near 1%.
- **Rank 4, if it had passed:** selection, not loss weights (the shortlist; class weights lost −7.60, idea 52's
  oversampling lost). A per-bin keep probability p_k = min(1, c / n_k) at read time, seeded so the selection is
  reproducible. It could be keyed by output bucket, with c the smallest bucket's count (about 0.74x the mean),
  dropping about 42% of bucket 6 and 39% of bucket 3, or by piece count over bins 6-30 only. It would run as one
  arm of the next retrain, 2 seeds, at equal superbatches against the control (so it sees fewer distinct
  positions), with an FN screen and an STC SPRT.

## 5. Checks and UNVERIFIED

- Every input's SHA-256 matched its committed manifest: 279 of 279 (196 originals, 83 td90- copies;
  sha_check.py, origin/retrain/8c-q's manifests).
- The trainer build used is not a retrain/8c-q build. Its filter, dump and stats code and its crate pins were
  compared with 8c-q's and are identical (above).
- **UNVERIFIED:** the rank 3 figures come from each file's first 300,000 kept positions (its first games), not
  a stride through the whole file. The bucket mix matches the exact one within 0.1 point, but a time trend inside
  one shard would not show. Rank 4's figures are exact.
- **UNVERIFIED:** the X thresholds and the 1.5x and 1% kill lines are the shortlist's estimates, not measured
  breakpoints.
