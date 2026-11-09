# Ensemble teacher, step 0: declared before any label is computed

Written and committed 2026-11-09 at about 6:35 PM EST, before any step 0 label exists. The owner's order
(2026-11-09, verbatim): "Ensemble teacher (item 3): run step 0 now (E3 = S512ppr3 + the two scratch seeds,
~1.25 h on 2 workers, low priority beside g4); report it, including the measured same-network bias in the
TD pre-test, before any small nets." The design is report.md §2.5 beside this file; where this file is
more precise, this file rules. Nothing here changes after the results; a later change is a new, dated
section.

## Members and engines

All three members are built from the same source commit as H's gold labeller, 2b1c78b (phase-4, Fork
0.3.0-dev+2b1c78b), so they differ only in the embedded network:

- **S512ppr3:** `fork-release-2b1c78b.exe` (H's gold labeller, SHA-256 17ab2b41...0b34, bench 14,149,617 /
  1cb0717f040c294d).
- **scratch-s1:** 2b1c78b built with `-DFORK_NET=` s512pp-scratch-s1.fnet (exp/oracle dcbe8fb's file,
  SHA-256 769bffe2...6cb5; netcheck against its parity file before use).
- **scratch-s2:** 2b1c78b built with `-DFORK_NET=` s512pp-scratch-s2.fnet (item 7's Kaggle output; netcheck
  against the parity file beside it before use).

Each engine's SHA-256 and bench are recorded before its first label and checked after its last; a mismatch
voids that engine's labels. Each scratch build's bench becomes its reference at that point.

## Sites

- **H:** idea 51's held-out set, unchanged (declaration-8b.md on idea51/td-labels: 5,000 sites of
  g3j-w05-val, one saved record per game, 3,131 kept by the trainer's filter; S512ppr3 1M-node labels
  already computed).
- **H2:** `label_pretest.py sample g3j-w05-val.vf --games 20000 --seed 5203`, with any game already in H
  dropped before labelling (the count dropped is reported). g3j is in no member's training data (g3s3
  and g3s2 were built before it).

## Labels (one thread, Hash 16, `ucinewgame` before each, Syzygy 3-4-5; `label_pretest.py deep`)

| engine | nodes | sites |
|---|---|---|
| S512ppr3 | 20,000; 50,000; 60,000; 100,000 | H and H2 |
| scratch-s1 | 20,000 | H and H2 |
| scratch-s2 | 20,000 | H and H2 |
| scratch-s1 | 1,000,000 (gold) | H |
| scratch-s2 | 1,000,000 (gold) | H |

These searches start from a fresh table, so the 20,000-node S512ppr3 label is not the stored game score
(which came from a game-long table at Hash 1 MB); both are reported.

## Scores and labels compared

- Win probability p = sigmoid(cp / S) with **one S = 92** for every engine and every label (the trainer's
  scale in the 8a recipe, as declaration-8b used). The members' networks are each matched in scale
  (S = 89-90 at conversion), so one common S treats them alike.
- **E3** = the mean of the three members' 20,000-node p; **E2i** = the mean of the two scratch members'.
- **M1** (static E3) = the mean of the three members' static p (`fork evalfens` of each build).
- A mate-flagged label: in E3 and E2i, if a strict majority of the members report a mate for the same side,
  the ensemble label is that side's p = 1 or 0; otherwise the mate members are left out of the mean.
- The candidate labels: E3 (3 × 20k nodes); S512ppr3 at 60,000 (equal total nodes); E2i (2 × 20k) against
  S512ppr3 at 40,000 is **not** computed (40k is not labelled; report-only comparisons use 50k instead,
  and say so); M1 as a floor; S512ppr3 at 20k, 50k and 100k for the depth curve.

## Yardsticks

- **Y1 (network-free):** Brier score (p - z)^2 against the game result z (1 / 0.5 / 0 from the side to
  move), on the kept records of H and H2 (one record per game).
- **Y2:** squared error in p against each 1M gold (S512ppr3's, scratch-s1's, scratch-s2's) and against the
  gold mean (the mean of the three gold p), on the kept records of H. Each row names the members shared
  between candidate and gold.
- Intervals: 95% percentile, 10,000 bootstrap resamples of games (one record per game), seed 5203; paired
  differences where both sides score the same records.

## The gate to step 2 (as report.md §2.5)

- **Pass:** E3 has a lower Y1 than S512ppr3 at 60k (point estimate) **and** E3 minus S512ppr3-60k on the
  gold-mean Y2 has its interval entirely below 0.
- **Kill:** S512ppr3 at 60k is at least as good as E3 on both (Y1 point estimate and gold-mean Y2 point
  estimate).
- Otherwise the owner decides. Either way no small net is trained before the owner has the report.

## The TD pre-test's same-network bias (idea 51)

Report only: declaration-8b's rules stand, and its pass/fail results are not revisited. Its comparisons
(the control against TD(0.5), TD(0.8), TD(0.9), TD(0.95), TD(0.98) and the unfiltered labels) are
recomputed with `label_pretest.py labels` (same settings: S = 92, blend 0.5, 10,000 resamples, seed 51) on
H with each independent gold in turn (scratch-s1 1M, scratch-s2 1M, and their p mean) in place of
S512ppr3's. **The measured bias** for each comparison is (candidate - control) under S512ppr3's gold minus
(candidate - control) under the independent gold mean, with a paired bootstrap interval. A result goes in
results-8b.md (idea51/td-labels) as a new dated section.

## Cost and running

About 1.68e10 nodes (about 1.25-1.5 h on 2 workers), one jobctl `measure` job at below-normal priority
beside g4, started when idea 52's labelling job has freed the measure slot.
