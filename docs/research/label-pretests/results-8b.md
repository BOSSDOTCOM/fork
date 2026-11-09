# Retrain 8b: offline label-quality pre-tests, results

Run on 2026-11-09 by the rules declared in `declaration-8b.md` (committed
7f8b55d at 3:12 PM EST, before any comparison; its time line corrected in
4c3f605, still before any result). Tools at 7f8b55d. Raw outputs stay
outside the repository (`~/fork-measure/i51/`).

## The held-out set's deep labels

jobctl `measure` job `i51-heldout-deep`, 3:13 to 3:35 PM EST, 2 workers at
below-normal priority beside data generation: 5,000 labels (161
mate-flagged), deep.tsv SHA-256
c012267c85fd9e95b2fe1d21826a2144a982549e252a441208e901ce9d6d76d8. The pinned
engine's SHA-256 and bench (14,149,617 / 1cb0717f040c294d) matched before
the first label and after the last. All 5,000 sites matched their
record (no shard, match or duplicate losses); 3,131 are kept by the
trainer's filter.

## Candidates 1 and 2: label error against the deep labels

Mean squared win-probability error on the 3,131 kept records (S = 92);
difference = candidate - control, 95% interval from 10,000 game resamples
(seed 51).

| Label | MSE | Difference | 95% interval | Passes |
|---|---|---|---|---|
| Control: 0.5 sigmoid(s / 92) + 0.5 z | 0.010535 | | | |
| TD(0.5) | 0.001428 | -0.009107 | [-0.010017, -0.008239] | yes |
| TD(0.8) | 0.002126 | -0.008409 | [-0.009276, -0.007572] | yes |
| TD(0.9) | 0.003817 | -0.006718 | [-0.007519, -0.005911] | yes |
| TD(0.95) | 0.007416 | -0.003119 | [-0.003906, -0.002317] | yes |
| TD(0.98) | 0.015866 | +0.005331 | [+0.004383, +0.006335] | no |
| Unfiltered: the control on all 5,000 saved records, against the kept ones | 0.009699 (all) / 0.010535 (kept) | -0.000836 | [-0.001384, -0.000278] | yes |

By end kind (kept records; control / TD(0.5) / TD(0.9) / TD(0.95)):
score adjudication (1,378) 0.00706 / 0.00077 / 0.00235 / 0.00483; mate
score (819) 0.01256 / 0.00170 / 0.00530 / 0.01038; table (599) 0.01704 /
0.00194 / 0.00446 / 0.00927; repetition (316) 0.00773 / 0.00262 / 0.00509
/ 0.00755; fifty moves (18) 0.01426 / 0.00098 / 0.00499 / 0.00718;
stalemate (1). TD(0.5) has the lowest error in every kind with more than
one record.

## Candidate 3: idea 48's closeness weighting (ranking test)

idea 59 step 3's test split: 30,000 sites, 27,475 used (finite bound, no
mate or table-band label), 1,346 games; n_eff 14,567 = 0.530 n. Mean
squared error (S = 89), plain / weighted: S512ppr3 0.047154 / 0.045065,
S512r2 0.048858 / 0.046572, S512+X 0.039720 / 0.037990. Differences
against S512r2 (95% intervals, 10,000 game resamples, seed 51):

| Network | Plain | Weighted |
|---|---|---|
| S512ppr3 | -0.001704 [-0.002006, -0.001408] | -0.001508 [-0.001872, -0.001155] |
| S512+X | -0.009139 [-0.009766, -0.008534] | -0.008582 [-0.009366, -0.007836] |

(a) holds (weighted error orders both pairs as their games did), (c) holds
(n_eff 0.53 n), but (b) fails: the plain error orders both pairs the same
way just as clearly. **Candidate 3 does not pass**: on this yardstick,
closeness weighting adds nothing that plain error lacks.

## Reading (the declaration's limits apply)

- Four of the five TD(lambda) labels and the unfiltered labels pass the
  declared rule; idea 48's weighting does not. At most two go to 8b; the
  owner chooses.
- The TD error rises steadily with lambda (0.5 best of those declared), and
  the control, half game result, is far from the deep labels. That is the
  pattern the declaration's first caveat predicts: the gold is S512ppr3 at
  1M nodes, the stored scores S512ppr3 at 20,000 nodes, so any label that
  leans on the stored scores and away from the result looks closer. The
  test cannot tell how much of the gap is label quality and how much is the
  shared network. A lambda this test favours may weight the result too
  little for training; the result is what corrects the network's own
  biases. The arm's games decide.
- The unfiltered pass is small (0.00084) and compares different position
  sets: the extra records (in check, captures, decided scores) have labels
  at least as close to deep labels as the kept ones. It says nothing about
  whether training on them helps.

## Exploratory (not declared, not used for any decision)

The TD grid of `td_labels.py compare` on the only deep labels that existed
before this run, the idea 59 step 3 sites that coincide with a saved record
of their game (S = 92, kept records): 1M-node labels, 44 records: MSE
lambda 0 0.00170, 0.5 0.00292, 0.9 0.00637, 0.95 0.00939, 1 0.02790; blend
0.5 0.00767. 100k-node labels, 790 records: lambda 0 0.00137, 0.5 0.00146,
0.9 0.00463, 0.95 0.00841, 1 0.04234; blend 0.5 0.01107. Lambda 0 (the
stored score itself) was lowest in both, consistent with the shared-network
caveat above.
