# Retrain 8b: offline label-quality pre-tests, declared before any comparison

Written 2026-11-09, 3:20 PM EST, before any comparison below was run. The
owner's request (2026-11-09, verbatim): "Offline label-quality pre-tests on
held-out positions with deep labels: current score/result blend vs
TD(lambda) labels at a few lambda values (idea 51; build the label tooling
from stored self-play games); quiet-filtered vs unfiltered label error;
idea 48's closeness weighting for base training. Declare before running: a
candidate earns an 8b arm only if it's measurably closer to deep labels
than the control."

Tools: `tools/datagen/td_labels.py` (the TD(lambda) labels) and
`tools/measure/label_pretest.py` (`sample`, `deep`, `labels`, `rank`), at
the commit that adds this file. No training. Nothing here is changed after
the results come in; any later change is a new, dated section.

## Why a new held-out set

No existing deep-labelled set covers stored game positions. Idea 59 step 3's
1M-node sites (test/n1m, test/n1m2, val/n1m, pilot/n1m: 40,000 sites) are
search-tree nodes at tree ply 1 or deeper, not game records: only 46 of them
coincide with a saved record of their own game (counted by position, no
error computed). Its 100k-node training split (1,000,000 sites) gives 896.
So the label comparisons use a new set, H.

## The held-out set H

- **Positions:** 5,000 games of `g3j-w05-val.vf` (generation 3's part g3j,
  validation shard, 379,542 games, SHA-256 54c0cfaf...eed1e1 as in
  data/manifests/g3j.json; labelled by S512ppr3 at 20,000 nodes; in no
  training set, g3s3 having been built before g3j), drawn by
  `label_pretest.py sample --games 5000 --seed 51`, and in each game one
  saved record chosen uniformly (the same seed stream). 5,000 sites, 3,131
  of them kept by the trainer's filter. File:
  `~/fork-measure/i51/held-out/sites.jsonl`, SHA-256
  64862be3cd681611b239d24fb37a0f30c2307bad01c389f6a3b848ae9cf3ec52.
- **Deep labels:** `label_pretest.py deep` with the pinned engine
  `fork-release-2b1c78b.exe` (Fork 0.3.0-dev+2b1c78b, net s512ppr3,
  SHA-256 17ab2b41b1b43adf42da9031f005c9d8c3d9b6eb656b798bf535939f765c0b34,
  idea 59 step 3's labeller), 1,000,000 nodes, one thread, Hash 16,
  `ucinewgame` before each, Syzygy 3-4-5 tables; the engine's SHA-256 and
  bench (tests/bench-s512ppr3.ref) checked before the first label and after
  the last, a mismatch voiding the labels. Two workers at below-normal
  priority, as a jobctl `measure` job. The deep value is the side to move's
  last reported score; a mate is +-20,000 and flagged, and stays in the set
  (a decided position is a valid target).

## The metric

Squared error in win probability between a label, from the side to move,
and the deep label's sigmoid(deep / S), with S = 92: the trainer's --scale
in the 8a recipe (`tools/train/kaggle/retrain_g3s3.py`, SCALE = 92). The
mean over the records named in each comparison.

## The control

The trainer's current target (tools/train/src/main.rs, `mapper`):
(1 - w) sigmoid(s / S) + w z, with s the record's stored score, z the game
result (side to move's view), w = 0.5 (`--result-weight`, RESULT_WEIGHT in
the 8a recipe), S = 92. Scored on the kept records of H (not in check, no
capture or promotion played, |s| <= 20,000).

## The candidates

1. **TD(lambda) labels** at lambda = 0.5, 0.8, 0.9, 0.95 and 0.98 (per ply),
   td_labels.py's default definition: the lambda-return over the game's
   full-search scores (saved, not in check), starting from the record's own
   score, plies outside the chain taking the next chain value, the stored
   result as the terminal value for every kind of end; S = 92. On the kept
   records of H, paired with the control.
2. **Unfiltered labels:** the control's label on every saved record of H
   (in check, captures, promotions and |s| > 20,000 included) against the
   control on the kept records only.
3. **Idea 48's closeness weighting**, which changes no label, so it cannot
   be "closer to deep labels" by construction. Its yardstick is idea 48's
   own offline test: does weighting the evaluation error by closeness to
   the search window rank networks the way games did, where plain error
   does not. Data: idea 59 step 3's test split (test/n1m and test/n1m2,
   30,000 search sites with 1M-node labels and Syzygy; SHA-256 of
   sites.jsonl 1a5cbbc5...0865d and 68ff2d85...0d3d, deep.tsv
   3aa61a19...434b and cf065d50...0c23), with each site's evaluation by
   S512ppr3, S512r2 and S512+X through R-int (seed-<net>.tsv, already
   computed). Error: (sigmoid(e / 89) - sigmoid(deep / 89))^2, S = 89 the
   networks' output scale. Weight: exp(-gap^2 / (2 h^2)), gap = |site eval -
   nearest finite bound|, h = 25 cp at main-search sites and 17 cp at
   quiescence sites (idea 59 step 3's kernel). Sites without a finite bound
   and mate-flagged or table-band labels are left out. Reference: S512r2.
   Expected order, from fixed-node games (the evaluation's quality without
   speed): S512+X better than S512r2 (+25.67 +/- 10.26 Elo, 800,000 nodes,
   run 42142711426); S512ppr3 better than S512r2 through a chain (S512+PP
   +46.09 +/- 10.37 at fixed nodes, S512ppr2 over S512+PP +20.11 +/- 7.22 at
   STC, S512ppr3 over S512ppr2 +15.65 +/- 9.26 at fixed nodes; docs/nets.md).

## The pass rule

- **Candidates 1 and 2:** a 95% percentile interval, from 10,000 bootstrap
  resamples of the games (seed 51), of (candidate's mean error - control's
  mean error) lying entirely below 0. H has one record per game, so a
  resample of games is a resample of positions; for candidate 2 both means
  are recomputed on each resample (the kept records are a subset of the
  saved ones).
- **Candidate 3:** passes only if all three hold: (a) the weighted error's
  interval (10,000 resamples of games, seed 51; a game's sites move
  together) of (net - S512r2) lies entirely below 0 for both S512+X and
  S512ppr3; (b) the plain error does not do so for at least one of the two;
  (c) the weights' n_eff is at least 0.5 n (idea 48's kill rule).
- At most two passing candidates go into the 8b plan, and the owner
  chooses them. Seven comparisons at 95% each: if none of the candidates
  were better, the chance that at least one passes by luck is up to about
  30%. The report gives every interval, not only the passes.

## What these tests can and cannot show

- They measure label quality against a deeper search by the same network
  that labelled the games (S512ppr3 at 1M nodes against S512ppr3 at 20,000).
  The two share the network's biases, which favours labels built from the
  stored scores (the control's score half, small lambdas) over the game
  result. A pass is evidence of closeness to a deeper search, not to the
  truth; the arm still has to win its games.
- Candidate 2 compares different position sets (all saved against kept):
  it shows whether the extra positions' labels are as close to deep labels
  as the kept ones, not whether training on them helps.
- Candidate 3 shows only whether closeness weighting orders two network
  pairs as their games did, on near-window sites. Those sites were selected
  close to their windows, so the weights vary less than on game records;
  two pairs are weak evidence; it cannot show that training with the
  weights gains anything. And the base-training positions carry no window
  today: an 8b arm would need a data field or an offline search per
  position first (idea 48's data need).
