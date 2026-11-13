# Phase 4 SPRT log

Every SPRT of Phase 4, in the order run, rejections included (DESIGN.md
§5.2, "Testing setup", and §5.3). Runs on the GitHub shards
(`.github/workflows/sprt.yml`, 16 shards, stages of 1,600 games merged with
`tools/cloud/sprt_merge.py`): fastchess 1.8.2-alpha, normalized Elo,
pentanomial statistics, alpha = beta = 0.05 (from 2026-11-07, alpha and
beta per entry: search features use design R, [0, 6] nElo, alpha 0.05,
beta 0.20, cap 8 stages, futility stop after 2; each entry names its
design, idea and try, and its result is **H1 accepted**, **H0 accepted**,
**futility stop** or **capped**), game pairs with colours
reversed, UHO_Lichess_4852_v1.epd (shuffled, seed 20261027; test openings
only), one thread per engine, Syzygy 3-4-5 for both, update.sh builds
(Ubuntu 22.04, g++ 11.4, x86-64-v3). STC 8+0.08 s with 16 MB Hash.

### 2026-10-29 b0-vs-bootstrap (step 0, deliverable 7)

- base `bfc8340` (phase-4, the bootstrap evaluation), test `79b1a6c`
  (branch b0-candidate: B0 embedded, nnue the default), bounds [0, 5] nElo,
  8+0.08, Hash 16 MB. Run 40821861574 (dispatched from b0-candidate, so its
  gated build_pair.sh ran netcheck on B0: passed). Result: **H1 accepted**
  after stage 0.
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: 486.85 +/- 32.07, nElo: 764.57 +/- 17.02
Ptnml(0-2): [0, 2, 53, 71, 674]
LLR: 50.51 (-2.94, 2.94) [0.00, 5.00] nElo: H1 accepted
```
- Not adopted on phase-4 yet (overnight failure rule): with B0 as the
  default, the TT-at-exact-depth = minimax search test and the zero-window
  probe test fail on a KRK position at depth 6 (554 vs 558), and a
  mate-in-2 UCI test fails; the network hookup was verified exact at every
  evaluation (DESIGN.md §5.3 build status). The owner decides.

### 2026-10-29 lmr-check-relief (tier 2 step 0, experiment)

- base `7c84ae7` (phase-4, bootstrap), test `f2796f7` (branch
  exp/lmr-check-relief: a late quiet move that gives check is reduced one
  ply less; its constant matches one engine's, so it waits for the owner),
  bounds [0, 3] nElo, 8+0.08, Hash 16 MB.
- Stage 0 (run 40819940042):
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: 15.86 +/- 13.86, nElo: 19.53 +/- 17.02
Ptnml(0-2): [78, 157, 282, 180, 103]
LLR: 0.72 (-2.94, 2.94) [0.00, 3.00] nElo: continue
```
- Stages 1-5: runs 40825124514 (after a pause for the B0 SPRT),
  40826734135, 40828537082, 40830278485, 40831983959. Result: **H1
  accepted** after 9,600 games:
```
Shards: 96 (done); pairs 4800, games 9600 (9600 finished, time losses 0, abnormal 0)
Elo: 11.26 +/- 5.54, nElo: 14.13 +/- 6.95
Ptnml(0-2): [469, 938, 1763, 1073, 557]
LLR: 3.01 (-2.94, 2.94) [0.00, 3.00] nElo: H1 accepted
```
- Not merged: its constant matches one engine's in the same role, so the
  owner decides first.

### 2026-10-29 lmr-in-check (tier 2 step 0, experiment)

- base `e370847` (phase-4, bootstrap), test `db99ebd` (branch
  exp/lmr-in-check: late quiet evasions get the normal reduction instead
  of none), bounds [0, 3] nElo, 8+0.08, Hash 16 MB.
- Stages 0-21: runs 40833730003 to 40878713471. Result: **H1 accepted**
  after 35,200 games:
```
Shards: 352 (done); pairs 17600, games 35200 (35200 finished, time losses 0, abnormal 0)
Elo: 4.21 +/- 2.89, nElo: 5.30 +/- 3.63
Ptnml(0-2): [1784, 3623, 6523, 3722, 1948]
LLR: 3.32 (-2.94, 2.94) [0.00, 3.00] nElo: H1 accepted
```
- Merged into phase-4 with the check relief (owner, 2026-10-29).

### 2026-10-29 b0r1-vs-b0 (step 4, deliverable 7)

- base `a3dd67c` (phase-4: B0, bench 16,538,042), test `3d66a40` (branch
  b0r1-candidate: B0r1 embedded, bench 15,453,694; only the network
  differs), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, Syzygy 3-4-5 for both,
  book UHO_Lichess_4852_v1 (shuffled, seed 20261027). Run 40916705615,
  dispatched once CI was idle. An earlier dispatch (run 40894512618) went
  out while the nightly run was active and was cancelled within a minute,
  with no result. Result: **H1 accepted** after stage 0:
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: 200.24 +/- 16.05, nElo: 263.05 +/- 17.02
Ptnml(0-2): [10, 37, 191, 235, 327]
LLR: 17.27 (-2.94, 2.94) [0.00, 5.00] nElo: H1 accepted
```
- Merged into phase-4 as the default network (docs/nets.md; three search
  tests fixed for it, DESIGN.md §5.3).

### 2026-10-29 qs-delta-vs-b0r1 (tier 2 step 0, experiment)

- base `bb4f75a` (phase-4, B0r1, bench 15,453,694), test `a3b2859`
  (branch exp/qs-delta: delta pruning in the quiescence search behind
  `use_qs_delta`, QuiesceGainSlack 150 cp; bench 14,952,431), bounds
  [0, 3] nElo, 8+0.08, Hash 16 MB.
- Stages 0-16: runs 40948681273 to 40983743442, one at a time, each
  dispatched only while CI was idle. After stage 15 the stage loop was
  stopped when the machine ran low on memory; stage 16 had already been
  dispatched and was collected. Result: **inconclusive**, stopped by the
  owner (2026-10-30) after 27,200 games:
```
Shards: 272 (done); pairs 13600, games 27200 (27200 finished, time losses 0, abnormal 0)
Elo: -0.40 +/- 2.93, nElo: -0.56 +/- 4.13
Ptnml(0-2): [946, 3135, 5417, 3208, 894]
LLR: -1.39 (-2.94, 2.94) [0.00, 3.00] nElo: continue
```
- Not merged; the switch stays off (it exists only on exp/qs-delta).
  Revisited in the post-network re-validation (ideas.md 39).

### 2026-10-30 g1b0-vs-b0r1 (bake-off games plan item 0)

- base `c9a4a7c` (phase-4, B0r1, bench 15,453,694), test `5cacf8a`
  (branch bake/g1b0: the bake-off's B0 control, B0's shape trained on
  snapshot g1s1, seed 1, S = 105; bench 14,589,665), bounds [0, 5] nElo,
  8+0.08, Hash 16 MB, GitHub shards.
- Stage 0: run 41104107035, dispatched while CI was idle. The local stage
  loop was stopped by the machine's low memory while the stage played;
  the run finished on GitHub and was collected afterwards. Result: **H1
  accepted** after stage 0:
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: 235.45 +/- 16.04, nElo: 334.16 +/- 17.02
Ptnml(0-2): [7, 20, 140, 288, 345]
LLR: 21.98 (-2.94, 2.94) [0.00, 5.00] nElo: H1 accepted
```
- Promoted as B0r2 by the owner's standing instruction (DESIGN.md §5.4,
  games plan item 0): the default network (docs/nets.md; one search test
  fixed for it) and generation 1's labeller from then on. The bake-off
  entries still play against this net as the B0 control (bake/g1b0).

### 2026-10-30 g1s512-vs-g1b0 (bake-off stage A, games plan 3)

- base `5cacf8a` (branch bake/g1b0: the B0 control, promoted as B0r2;
  bench 14,589,665), test `ba8c4cb` (branch bake/g1s512: S-512, seed 1,
  S = 101; bench 15,249,025), bounds [0, 5] nElo, 8+0.08, Hash 16 MB,
  Syzygy 3-4-5, GitHub shards.
- Stage 0: run 41125906800, dispatched while CI was idle. Result: **H1
  accepted** after stage 0:
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: 43.66 +/- 12.02, nElo: 62.52 +/- 17.02
Ptnml(0-2): [30, 137, 320, 229, 84]
LLR: 3.98 (-2.94, 2.94) [0.00, 5.00] nElo: H1 accepted
```
- Promoted provisionally as the default network S512 by the owner
  (docs/nets.md); the bake-off continues unchanged (H-512 next), and a
  later entry that beats it is promoted then.

### 2026-10-30 g1h512-vs-g1b0 (bake-off stage A, games plan 3)

- base `5cacf8a` (branch bake/g1b0: the B0 control, promoted as B0r2;
  bench 14,589,665), test `21fb7fc` (branch bake/g1h512: H-512, seed 1,
  S = 100; bench 14,987,230), bounds [0, 5] nElo, 8+0.08, Hash 16 MB,
  Syzygy 3-4-5, GitHub shards.
- Stage 0: run 41141375944: Elo -25.67 +/- 12.92, nElo -33.97 +/- 17.02,
  LLR -2.42, continue. Stage 1: run 41143214710. Result: **H0 accepted**
  after stage 1:
```
Shards: 32 (done); pairs 1600, games 3200 (3200 finished, time losses 0, abnormal 0)
Elo: -24.36 +/- 9.06, nElo: -32.48 +/- 12.04
Ptnml(0-2): [172, 398, 623, 296, 111]
LLR: -4.64 (-2.94, 2.94) [0.00, 5.00] nElo: H0 accepted
```
- Stage A fail: under games plan item 3 the entry goes back to training,
  not out of the bake-off.

### 2026-10-30 g1afs-vs-g1b0 (bake-off stage A, games plan 3)

- base `5cacf8a` (branch bake/g1b0: the B0 control, promoted as B0r2;
  bench 14,589,665), test `b5da3bc` (branch bake/g1afs: AF-S, seed 2,
  S = 111; bench 26,382,157), bounds [0, 5] nElo, 8+0.08, Hash 16 MB,
  Syzygy 3-4-5, GitHub shards.
- Stage 0: run 41144977957. Result: **H0 accepted** after stage 0:
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: -48.52 +/- 12.78, nElo: -65.51 +/- 17.02
Ptnml(0-2): [109, 213, 304, 139, 35]
LLR: -4.51 (-2.94, 2.94) [0.00, 5.00] nElo: H0 accepted
```
- Stage A fail: under games plan item 3 the entry goes back to training,
  not out of the bake-off.

### 2026-10-30 g1xgr-vs-g1b0 (bake-off stage A, games plan 3)

- base `5cacf8a` (branch bake/g1b0: the B0 control, promoted as B0r2;
  bench 14,589,665), test `a697945` (branch bake/g1xgr: XGR-512, seed 2,
  S = 96; bench 15,540,185), bounds [0, 5] nElo, 8+0.08, Hash 16 MB,
  Syzygy 3-4-5, GitHub shards.
- Stage 0: run 41159549810, dispatched once CI was idle. Result: **H0
  accepted** after stage 0:
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: -38.15 +/- 13.03, nElo: -50.26 +/- 17.02
Ptnml(0-2): [102, 210, 297, 143, 48]
LLR: -3.50 (-2.94, 2.94) [0.00, 5.00] nElo: H0 accepted
```
- Stage A fail: under games plan item 3 the entry goes back to training,
  not out of the bake-off.
- Stage A complete: S-512 passed, H-512, AF-S and XGR-512 failed against
  the B0 control. Next per the games plan: stage B (fixed nodes, no SPRT)
  and the S-512 seed-noise match, after the owner's review.
- Owner's review (2026-10-31, DESIGN.md §5.4 "Amendments after stage A"):
  the fail rule above is replaced. No entry is retrained alone; an entry
  without an accuracy advantage over the control in stage B (its Elo
  point estimate not above 0; rule set before any stage B result) is dropped,
  and the remaining entries, S-512 and the control included, are
  retrained together in round 2 on about 500 M positions.

### 2026-10-31 bake-off stage B: fixed nodes (games plan 4, diagnostic, no SPRT)

- Each entry (its stage A test commit) against the B0 control (`5cacf8a`),
  800,000 nodes per move for both engines (fastchess `nodes=800000`) under
  a 600+6 clock that never binds, Hash 16 MB, Syzygy 3-4-5, the UHO book,
  stage 0's openings, 1,600 games on the GitHub shards; the runs' LLR
  (bounds [0, 5]) is ignored. Rule (owner, set before any stage B result):
  an entry stays for round 2 if its Elo point estimate is above 0.
- The node limit binds: in shard 0 of S-512's run, S-512's median move took
  1.26 times B0's (its measured speed is 0.78 of B0's, so 1.28 was
  expected), and no game lost on time. B0's median move took 0.33 s for
  800,000 nodes, so the runners search about 2.4 M nodes/s, not the 3.8 M
  estimated from the first-move depth when the count was chosen (DESIGN.md
  §5.4): an average STC move is nearer 500,000 nodes, and stage B searches
  deeper than STC (median depth 17 against 15 in S-512's stage A games).

| Entry | Test commit | Run | Elo | nElo | Ptnml | Stage A Elo | Stays |
|---|---|---|---|---|---|---|---|
| S-512 | ba8c4cb | 41170753141 | +74.52 ± 12.10 | +108.13 ± 17.02 | [21, 101, 304, 267, 107] | +43.66 ± 12.02 | yes |
| H-512 | 21fb7fc | 41172824043 | +32.23 ± 12.03 | +45.89 ± 17.02 | [37, 151, 309, 233, 70] | −24.36 ± 9.06 | yes |
| AF-S | b5da3bc | 41174960498 | +41.67 ± 12.01 | +59.65 ± 17.02 | [30, 138, 329, 217, 86] | −48.52 ± 12.78 | yes |
| XGR-512 | a697945 | 41177610204 | +52.07 ± 11.81 | +76.24 ± 17.02 | [21, 134, 318, 240, 87] | −38.15 ± 13.03 | yes |

- Owner's reading (2026-10-31): S-512 +74.5 at fixed nodes against +43.7
  at STC, so about 30 Elo is spent on speed; H-512 +32.2 at fixed nodes
  against -24.4 at STC: better judgement than the control, lost on speed
  and overfitting.
- Stage B complete: all four entries are above 0 at fixed nodes, so all
  four stay for round 2 with the B0 control.

### 2026-10-31 S-512 seed noise (games plan 5)

- Base `ba8c4cb` (bake/g1s512: S-512 seed 1, the entry), test `236fc58`
  (bake/g1s512b: seed 2, S = 101 as seed 1; bench 16,059,585), 8+0.08,
  Hash 16 MB, Syzygy 3-4-5, the UHO book, stage 0's openings, 1,600 games
  on the GitHub shards, no SPRT (the run's LLR on [-5, 5] is ignored).
- Run 41180151074:
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: -0.87 +/- 12.25, nElo: -1.21 +/- 17.02
Ptnml(0-2): [62, 178, 314, 194, 52]
```
- The two seeds do not differ by more than about 10 Elo (item 5's
  threshold for repeated trainings): the estimate is -0.9. The match
  cannot rule out a difference of that size either (95% interval about
  ±12 Elo).

### 2026-10-31 Idea 13 seed noise, arm A (ideas.md 13)

- Base `dd2027e` (bake/i13a2: arm A seed 2, S = 90; bench 19,291,319), test
  `ab5cfed` (bake/i13a1: arm A seed 1, converted at S = 89; bench
  18,340,829), 8+0.08, Hash 16 MB, Syzygy 3-4-5, the UHO book, stage 0's
  openings, 1,600 games on the GitHub shards, no SPRT (the run's LLR on
  [-5, 5] is ignored).
- Run 41230452410:
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: 3.26 +/- 12.62, nElo: 4.40 +/- 17.02
Ptnml(0-2): [56, 196, 293, 187, 68]
```
- Arm A's two seeds are within item 5's 10 Elo: the estimate is +3.3, the
  95% interval about ±12.6. A duplicate of this match (run 41231978376),
  started by a stale queue script, was cancelled after about a minute and
  is not counted.

### 2026-10-31 Idea 13 seed noise, arm B (ideas.md 13)

- Base `0f1f4b6` (bake/i13b1: arm B seed 1, S = 90; bench 18,091,193), test
  `6b92eb8` (bake/i13b2: arm B seed 2, S = 90; bench 15,940,717), same
  conditions as arm A's.
- Run 41235532025:
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: -14.77 +/- 12.36, nElo: -20.38 +/- 17.02
Ptnml(0-2): [68, 199, 320, 159, 54]
```
- Arm B's seed 2 is weaker than seed 1: the estimate, -14.8, is past item
  5's 10 Elo, and the 95% interval (about -27.1 to -2.4) excludes 0 but not
  differences below 10. Seed 1, the better own-validation loss (0.02532),
  is the one the SPRT plays.

### 2026-10-31 i13b1-vs-i13a2 (idea 13: the split search's data against the normal data)

- Base `dd2027e` (bake/i13a2: arm A's best own-validation net, 0.02380),
  test `0f1f4b6` (bake/i13b1: arm B's best, 0.02532), bounds [0, 5] nElo,
  8+0.08, Hash 16 MB, Syzygy 3-4-5, the UHO book. Each arm's nets were
  trained on its own data at the same compute budget (arm B cut at arm A's
  21,738 s: data/manifests/g2bc.json) with the same schedule
  (tools/train/kaggle/idea13.py). Run 41236941019. Result: **H1 accepted**
  after stage 0.
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: 65.47 +/- 12.90, nElo: 88.52 +/- 17.02
Ptnml(0-2): [32, 110, 314, 216, 128]
LLR: 5.70 (-2.94, 2.94) [0.00, 5.00] nElo: H1 accepted
```
- The gap is far beyond the seed noise above (up to about 15 Elo between
  seeds of one arm). As the owner noted, it measures the split search as
  implemented, including its different game endings (fewer score
  adjudications, more mates and table results), not the split alone.

### 2026-10-31 se-vs-base (tier 2, T27: singular extension)

- Base `2179297` (phase-4: singular extension built, switch off; bench
  15,249,025), test `e94a3e6` (branch tier2/se: the switch on; bench
  19,910,368), bounds [0, 5] nElo (a large gain expected: Fork had no
  extensions), 8+0.08, Hash 16 MB, Syzygy 3-4-5, the UHO book, S-512 the
  default network. Runs 41243485437, 41244836141 and 41246310199 (stages
  0-2). Result: **H1 accepted** after stage 2.
```
Shards: 48 (done); pairs 2400, games 4800 (4800 finished, time losses 0, abnormal 0)
Elo: 14.12 +/- 6.55, nElo: 21.21 +/- 9.83
Ptnml(0-2): [98, 544, 958, 665, 135]
LLR: 3.72 (-2.94, 2.94) [0.00, 5.00] nElo: H1 accepted
```
- Stages: 0 +9.56 +/- 11.35 (LLR 0.79), 1 +12.49 +/- 7.98 (2.17), 2 H1.
- Adopted: the switch is on in phase-4 (the next tier-2 SPRTs build on it).

### 2026-10-31 mc-vs-se (tier 2, T28: multi-cut)

- Base `1e1e2e9` (branch tier2/se-on: singular extension on; bench
  19,910,368), test `ab9d471` (branch tier2/mc: multi-cut on as well; bench
  19,841,861), bounds [0, 3] nElo (a few Elo expected), 8+0.08, Hash 16 MB,
  Syzygy 3-4-5, the UHO book, S-512. Stages 0-5. Result: **H1 accepted**.
```
Shards: 96 (done); pairs 4800, games 9600 (9600 finished, time losses 0, abnormal 0)
Elo: 9.19 +/- 4.62, nElo: 13.85 +/- 6.95
Ptnml(0-2): [215, 1091, 1976, 1261, 257]
LLR: 2.95 (-2.94, 2.94) [0.00, 3.00] nElo: H1 accepted
```
- Stages: 0 +1.95 +/- 11.62 (LLR 0.05), 1 +6.62 +/- 8.06 (0.67), 2 +6.37
  +/- 6.54 (0.96), 3 +6.57 +/- 5.63 (1.34), 4 +8.08 +/- 5.06 (2.12), 5 H1.
- Adopted (owner, 2026-10-31: adopt on passing, with the credit note for the
  textbook form, ORIGINALITY.md).

### 2026-10-31 ne-vs-mc (tier 2, T30: negative extension)

- Base `ab9d471` (singular extension and multi-cut on; bench 19,841,861),
  test `75e98f9` (branch tier2/ne: the negative extension on as well; bench
  14,233,520), bounds [0, 3], conditions as above. Stages 0-4. Result:
  **H0 accepted**.
```
Shards: 80 (done); pairs 4000, games 8000 (8000 finished, time losses 0, abnormal 0)
Elo: -8.73 +/- 4.98, nElo: -13.36 +/- 7.61
Ptnml(0-2): [218, 1002, 1699, 925, 156]
LLR: -2.96 (-2.94, 2.94) [0.00, 3.00] nElo: H0 accepted
```
- Stages: 0 -11.95 +/- 11.61, 1 -12.06 +/- 7.93, 2 -8.76 +/- 6.46, 3 -8.63
  +/- 5.60, 4 H0.
- Rejected: the switch stays off. Its form (every non-PV node whose TT score
  is at or above beta, one ply less) took 28% off the bench's nodes at fixed
  depth and lost Elo at STC; a narrower gating (KB §3.21: Fork's choice by
  experiment) is left for later.

### 2026-11-01 reply-vs-mc (tier 2, T10: the reply table)

- Base `dc6dec8` (phase-4: singular extension and multi-cut on; bench
  19,841,861), test `8464d29` (branch tier2/reply: the reply table on as
  well; bench 19,724,297), bounds [0, 5] nElo (set before the run, by the
  expected gain), 8+0.08, Hash 16 MB, Syzygy 3-4-5, the UHO book, S-512.
  Stages 0-3, after CI run
  41263900061 on dc6dec8 (passed). Result: **H1 accepted**.
```
Shards: 64 (done); pairs 3200, games 6400 (6400 finished, time losses 0, abnormal 0)
Elo: 11.46 +/- 5.57, nElo: 17.53 +/- 8.51
Ptnml(0-2): [126, 697, 1409, 776, 192]
LLR: 3.99 (-2.94, 2.94) [0.00, 5.00] nElo: H1 accepted
```
- Stages: 0 +6.30 +/- 11.14 (LLR 0.47), 1 +6.08 +/- 7.78 (0.92), 2 +10.79
  +/- 6.45 (2.77), 3 H1.
- Adopted: the switch is on in phase-4 (the follow table's SPRT builds on
  it).

### 2026-11-01 follow-vs-reply (tier 2, T10: the follow table)

- Base `cf85955` (phase-4: singular extension, multi-cut and the reply table
  on; bench 19,724,297), test `4a7cbe9` (branch tier2/follow: the follow
  table on as well; bench 19,702,992), bounds [0, 3] nElo (set before the
  run: the second table expected to add less than the first), conditions
  as above. Stages 0-7. Result: **H1 accepted**.
```
Shards: 128 (done); pairs 6400, games 12800 (12800 finished, time losses 0, abnormal 0)
Elo: 7.22 +/- 3.92, nElo: 11.09 +/- 6.02
Ptnml(0-2): [274, 1454, 2714, 1648, 310]
LLR: 3.05 (-2.94, 2.94) [0.00, 3.00] nElo: H1 accepted
```
- Stages: 0 +11.08 +/- 11.11 (LLR 0.62), 1 +6.95 +/- 7.73 (0.74), 2 +4.99
  +/- 6.33 (0.75), 3 +6.90 +/- 5.53 (1.45), 4 +7.91 +/- 4.97 (2.11), 5
  +7.42 +/- 4.52 (2.37), 6 +7.76 +/- 4.18 (2.91), 7 H1.
- Adopted: the switch is on in phase-4 (the take history's SPRT builds on
  it).

### 2026-11-01 take-vs-follow (tier 2, T11: the take history)

- Base `459d487` (phase-4: singular extension, multi-cut, the reply and
  follow tables on; bench 19,702,992), test `93360ea` (branch tier2/take:
  the take history on as well; bench 19,698,287), bounds [0, 3] nElo (set
  before the run, by the expected gain), conditions as above. Stages 0-12
  ended without a verdict (LLR 2.70), so the test continued with stages
  13-24 (testing rules: an SPRT runs to its verdict); stage 13 decided.
  Result: **H1 accepted**.
```
Shards: 224 (done); pairs 11200, games 22400 (22400 finished, time losses 0, abnormal 0)
Elo: 4.53 +/- 2.99, nElo: 6.90 +/- 4.55
Ptnml(0-2): [503, 2609, 4745, 2779, 564]
LLR: 3.01 (-2.94, 2.94) [0.00, 3.00] nElo: H1 accepted
```
- Stages: 0 -3.69 +/- 10.78 (LLR -0.29), 1 +1.30 +/- 7.81 (0.04), 2 +4.20
  +/- 6.42 (0.59), 3 +2.77 +/- 5.57 (0.43), 4 +3.78 +/- 5.00 (0.85), 5
  +4.20 +/- 4.56 (1.17), 6 +4.99 +/- 4.22 (1.70), 7 +4.75 +/- 3.96 (1.82),
  8 +4.46 +/- 3.75 (1.88), 9 +4.54 +/- 3.55 (2.14), 10 +4.05 +/- 3.39
  (2.03), 11 +4.42 +/- 3.23 (2.49), 12 +4.41 +/- 3.10 (2.70), 13 H1.
- Adopted: the switch is on in phase-4. The reach question the tier-2
  review raised (two entries at opposite limits can reorder victims up to
  about 3.1 pawns apart) is answered in games: the history as built gains.

### 2026-11-01 r2s512-vs-s512 (bake-off round 2: S-512 retrained, promotion test)

- Base `6600af3` (phase-4: S512, round 1's S-512, the default; bench
  19,698,287), test `84dc337` (branch bake/r2s512: S-512 retrained on
  g2s1, seed 2, S = 92; bench 17,904,298), bounds [0, 5] nElo, 8+0.08,
  Hash 16 MB, Syzygy 3-4-5, GitHub shards; started before round 2's other
  nets were ready (owner).
- Stage 0: run 41349145950. Result: **H1 accepted** after stage 0:
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: 151.35 +/- 12.50, nElo: 233.38 +/- 17.02
Ptnml(0-2): [3, 47, 224, 343, 183]
LLR: 15.30 (-2.94, 2.94) [0.00, 5.00] nElo: H1 accepted
```
- Promoted by the owner as the default network S512r2, with the scale it
  was tested at (S = 92; docs/nets.md).

### 2026-11-01 round 2: fixed nodes against S512r2 (DESIGN.md §5.4, round 2 amendment; no SPRT)

- Each remaining round-2 entry (the seed with the lower validation loss,
  scale-matched to S512r2 on g2s1-val) against S512r2 (base: phase-4 with
  S512r2 as the default; bench 17,904,298), 800,000 nodes per move for both
  engines under a 600+6 clock that never binds, Hash 16 MB, Syzygy 3-4-5,
  the UHO book, 1,600 games on the GitHub shards; the runs' LLR (bounds
  [0, 5]) is ignored. Rule (owner, set before any round-2 game result): an
  entry proceeds to an STC promotion SPRT against S512r2 on [0, 5] only if
  its Elo point estimate is above 0; the others leave the bake-off.

| Entry | Base | Test commit | Run | Elo (95%) | nElo | Ptnml | Proceeds |
|---|---|---|---|---|---|---|---|
| H-512 (seed 1, S = 92) | 4c68385 | 828bdc7 | 41371135671 | −12.17 ± 10.58 | −19.60 ± 17.02 | [37, 211, 339, 197, 16] | no |
| AF-S (seed 1, S = 89) | 40198f5 | 5e72ab1 | 41390867039 | +10.43 ± 10.36 | +17.15 ± 17.02 | [25, 169, 368, 209, 29] | yes |
| XGR-512 (seed 2, S = 89) | 40198f5 | 22c3494 | 41395484353 | +30.70 ± 10.37 | +50.67 ± 17.02 | [20, 139, 356, 250, 35] | yes |

- H-512: 1,600 games finished, no time losses, no abnormal ends. Its Elo
  interval, −22.75 to −1.59, lies wholly below 0, so it is not a retest
  candidate for after the post-network search retune (owner, 2026-11-02:
  an entry whose interval included 0 would have been recorded as one).
  It leaves the bake-off. At round 1's stage B it scored +32.23 ± 12.03
  against B0 under the same conditions.
- AF-S: 1,600 games finished, no time losses, no abnormal ends. Its point
  estimate is above 0 (interval −0.07 to +20.79), so it proceeds to the
  STC promotion SPRT against S512r2 on [0, 5]. At round 1's stage B it
  scored +41.67 ± 12.01 against B0.
- XGR-512: 1,600 games finished, no time losses, no abnormal ends. Its
  point estimate is above 0 (interval +20.33 to +41.07), so it proceeds to
  the STC promotion SPRT against S512r2 on [0, 5]. At round 1's stage B it
  scored +52.07 ± 11.81 against B0.
- Stray runs: between 2026-11-01 8:12 PM and 2026-11-02 12:38 AM EST, six
  sprt runs (41371254296, 41374609261, 41374700577, 41390975177,
  41395037917, 41395238185) failed at checkout within about a minute. They
  were stages 2 to 7 of the cancelled first IIR SPRT, whose local driver
  kept dispatching against the replaced test commit 988843c; no games were
  played, and the driver was stopped. None of them is part of any result.

### 2026-11-02 r2afs-vs-s512r2 (bake-off round 2: AF-S, promotion test)

- Base `9814ad6` (phase-4: S512r2, the default; bench 17,904,298), test
  `5e72ab1` (branch bake/r2afs: AF-S, round 2 seed 1, S = 89 matched to
  S512r2; bench 25,009,605), bounds [0, 5] nElo, 8+0.08, Hash 16 MB,
  Syzygy 3-4-5, GitHub shards; entered on its fixed-node screen (+10.43 ±
  10.36, above).
- Stage 0: run 41399769054. Result: **H0 accepted** after stage 0:
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: -55.85 +/- 11.42, nElo: -84.71 +/- 17.02
Ptnml(0-2): [80, 253, 326, 124, 17]
LLR: -5.78 (-2.94, 2.94) [0.00, 5.00] nElo: H0 accepted
```
- Not promoted. Under the round 2 candidate rules (DESIGN.md §5.4, set
  2026-11-02 before this result): an **LTC / TCEC-conditions candidate**
  (it beat S512r2 at fixed nodes and failed its STC SPRT), and a **retest
  candidate** for after the post-network search retune (its fixed-node
  interval, −0.07 to +20.79, includes 0; its STC interval, −67.27 to
  −44.43, does not). At equal nodes it was ahead; at equal time, about 0.72
  of S512r2's speed (round 1's bench nps, 0.56 against 0.78 of B0's), it
  lost by about 56 Elo.

### 2026-11-02 r2xgr512-vs-s512r2 (bake-off round 2: XGR-512, promotion test)

- Base `9814ad6` (phase-4: S512r2, the default; bench 17,904,298), test
  `22c3494` (branch bake/r2xgr512: XGR-512, round 2 seed 2, S = 89 matched
  to S512r2; bench 18,390,499), bounds [0, 5] nElo, 8+0.08, Hash 16 MB,
  Syzygy 3-4-5, GitHub shards, driven by tools/github/sprt_run.sh; entered
  on its fixed-node screen (+30.70 ± 10.37, above).
- Stage 0: run 41402192712. Result: **H0 accepted** after stage 0:
```
Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
Elo: -34.42 +/- 11.88, nElo: -49.69 +/- 17.02
Ptnml(0-2): [66, 241, 315, 141, 37]
LLR: -3.46 (-2.94, 2.94) [0.00, 5.00] nElo: H0 accepted
```
- Not promoted. Under the round 2 candidate rules (DESIGN.md §5.4, set
  before this result): an **LTC / TCEC-conditions candidate** (it beat
  S512r2 at fixed nodes, +30.70, and failed its STC SPRT); **not a retest
  candidate** (its fixed-node interval, +20.33 to +41.07, and its STC
  interval, −46.30 to −22.54, both exclude 0). At equal nodes it was about
  31 Elo ahead; at equal time it lost by about 34.
- Round 2 ends with no promotion: S512r2 stays the default. LTC candidates:
  AF-S and XGR-512; retest candidate: AF-S.

### 2026-11-02 iir-d8-vs-s512r2 (tier 2, T26: internal iterative reduction)

- Base `387f338` (phase-4: S512r2, the default; singular extension,
  multi-cut, the reply, follow and take tables on; bench 17,904,298), test
  `5282a71` (branch tier2/iir: the same with `use_no_move_reduction` on,
  NoMoveReduceMinDepth 8; bench 14,180,299), bounds [0, 3] nElo, 8+0.08,
  Hash 16 MB, Syzygy 3-4-5, GitHub shards, driven by
  tools/github/sprt_run.sh. The first attempt (on S512, before S512r2's
  promotion) was cancelled at stage 0 and is not part of this result.
- Stages (Elo, nElo, LLR after each): 0 (run 41404320026) +22.18 ± 10.34,
  +36.63 ± 17.02, 1.40; 1 (run 41406334196) +20.11 ± 7.34, +33.05 ± 12.04,
  2.51; 2 (run 41408301291) H1. Result: **H1 accepted** after stage 2:
```
Shards: 48 (done); pairs 2400, games 4800 (4800 finished, time losses 0, abnormal 0)
Elo: 21.45 +/- 5.98, nElo: 35.35 +/- 9.83
Ptnml(0-2): [60, 472, 1080, 688, 100]
LLR: 4.04 (-2.94, 2.94) [0.00, 3.00] nElo: H1 accepted
```
- Adopted: the switch is on in phase-4. The measurement that chose the
  depth had found no depth better than "off" on its quality proxy (DESIGN.md
  Search constants, `NoMoveReduceMinDepth`); in games the reduction gains.


### 2026-11-02 ltc-r2xgr512-vs-s512r2 (round 2's LTC candidate: XGR-512 at 40+0.4)

- Base `9814ad6` (phase-4: S512r2, the default), test `22c3494` (branch
  bake/r2xgr512: XGR-512, round 2 seed 2, S = 89): the same pair as its
  STC SPRT, so the network is the only difference (neither has IIR).
  Bounds [0, 5] nElo, **40+0.4, Hash 64 MB**, x86-64-v3 on both sides,
  Syzygy 3-4-5, GitHub shards (16 per stage, 1,664 games per stage, cap
  9,984 games: the owner's 10,000 in whole stages without reusing an
  opening), driven by tools/github/sprt_run.sh (owner, 2026-11-02: the
  LTC tests on GitHub's shards; the AVX-512 x86-64-v4 half of the
  TCEC-conditions check waits for the 32-vCPU AWS quota).
- Stage 0: run 41469160529. Result: **H0 accepted** after stage 0:
```
Shards: 16 (done); pairs 832, games 1664 (1664 finished, time losses 0, abnormal 0)
Elo: -30.56 +/- 9.96, nElo: -51.53 +/- 16.69
Ptnml(0-2): [37, 249, 386, 143, 17]
LLR: -3.72 (-2.94, 2.94) [0.00, 5.00] nElo: H0 accepted
```
- Not promoted; it loses at LTC by about as much as at STC (−34.42 ±
  11.88). Its x86-64-v4 check at TCEC conditions is still owed when the
  AWS quota allows (owner's plan), but this result gives no reason to
  expect a pass.

### 2026-11-02 AF-S at LTC: shelved, not tested (owner)

- Round 2's other LTC candidate, AF-S (`5e72ab1`), is **not tested at
  LTC**: it trailed XGR-512 at fixed nodes (+10.43 ± 10.36 against
  +30.70 ± 10.37) and at STC against S512r2 (−55.85 ± 11.42 against
  −34.42 ± 11.88), and XGR-512 failed at LTC (above). No game was played
  for it at LTC. It stays a retest candidate after the post-network
  search retune (DESIGN.md §5.4).

### 2026-11-02 ltc-drift-vs-base (tier 2, T32: the pawn drift table, correction history)

- Base `2d582fc` (phase-4: S512r2 with IIR on), test `0342ad6` (branch
  tier2/drift: the pawn structure key, the drift table with the measured
  constants DriftWeightTotal 256, DriftWeightCap 4, DriftLimit 300, and
  `use_pawn_drift` on). Bounds [0, 3] nElo, **40+0.4, Hash 64 MB**
  (straight to LTC per Testing setup), x86-64-v3 on both sides, Syzygy
  3-4-5, GitHub shards (16 per stage, 1,664 games per stage, cap 9,984
  games), driven by tools/github/sprt_run.sh.
- Stages 0-5: runs 41484476694, 41506184505, 41519311035, 41532210496,
  41544978779, 41555370610. After each stage (cumulative): +4.59 ± 9.19,
  +0.84 ± 6.41, −0.35 ± 5.26, −0.94 ± 4.51, −1.09 ± 4.05, then the cap.
  Result: **undecided at the 9,984-game cap**:
```
Shards: 96 (done); pairs 4992, games 9984 (9984 finished, time losses 0, abnormal 0)
Elo: -0.35 +/- 3.72, nElo: -0.64 +/- 6.82
Ptnml(0-2): [62, 1224, 2447, 1180, 79]
LLR: -0.53 (-2.94, 2.94) [0.00, 3.00] nElo: continue
```
- Not adopted: a test that ends without a verdict counts as not passed
  (Testing setup: the change is shelved, the baseline stays), so
  `use_pawn_drift` stays off and tier2/drift is not merged. The interval
  (nElo −7.5 to +6.2) leaves little room for the gain the bounds asked
  for; the owner decides whether the further correction tables, queued
  after this result, go ahead.

### 2026-11-03 ltc-iir-on-vs-off (tier 2, T26: internal iterative reduction's LTC confirmation)

- Base `0f62af5` (branch ltc/iir-off: phase-4 with `use_no_move_reduction`
  off), test `2d582fc` (phase-4: S512r2 with IIR on, adopted on its STC
  pass above). Non-regression bounds [−3, 0] nElo, **40+0.4, Hash 64 MB**,
  x86-64-v3 on both sides, Syzygy 3-4-5, GitHub shards (16 per stage,
  1,664 games per stage, cap 9,984 games), driven by
  tools/github/sprt_run.sh (owner, 2026-11-02: the LTC queue's third entry).
- Stages (Elo, nElo, LLR after each): 0 (run 41738319103) +25.52 ± 9.48,
  +45.13 ± 16.69, 1.93; 1 (run 41748641433) H1. Result: **H1 accepted**
  after stage 1:
```
Shards: 32 (done); pairs 1664, games 3328 (3328 finished, time losses 0, abnormal 0)
Elo: 26.25 +/- 6.65, nElo: 46.80 +/- 11.80
Ptnml(0-2): [17, 312, 790, 493, 52]
LLR: 4.00 (-2.94, 2.94) [-3.00, 0.00] nElo: H1 accepted
```
- Confirmed: IIR stays on. Its LTC gain (+26.25 ± 6.65) is at least its
  STC one (+21.45 ± 5.98). With this result the LTC queue of 2026-11-02 is
  done (XGR-512 failed, the drift table undecided, AF-S shelved).

### 2026-11-05 lmrh-24000-vs-base (tier 2, T16: the LMR history term)

- Base `684bac6` (phase-4: S512r2, IIR on), test `cf614e0` (branch
  sprt/lmr-history: the same with `use_lmr_history` on and the measured
  LmrHistoryDivisor 24000; bench 14,141,348). Bounds [0, 3] nElo, 8+0.08,
  Hash 16 MB, Syzygy 3-4-5, GitHub shards, driven by
  tools/github/sprt_run.sh.
- Stages (Elo, nElo, LLR after each): 0 (run 42113566721) −13.90 ± 10.10,
  −23.47 ± 17.02, −0.99; 1 (run 42116312709) −12.49 ± 7.09, −21.23 ±
  12.04, −1.81; 2 (run 42119021732) −9.12 ± 5.78, −15.51 ± 9.83, −2.03;
  3 (run 42121703916) H0. Result: **H0 accepted** after stage 3:
```
Shards: 64 (done); pairs 3200, games 6400 (6400 finished, time losses 0, abnormal 0)
Elo: -10.81 +/- 5.01, nElo: -18.38 +/- 8.51
Ptnml(0-2): [104, 830, 1496, 701, 69]
LLR: -3.16 (-2.94, 2.94) [0.00, 3.00] nElo: H0 accepted
```
- Not adopted: `use_lmr_history` stays off and tier2/lmr-history is not
  merged as a change of the default. It agrees with its measurement, where
  no divisor beat "off" (DESIGN.md, Search constants). The branch's
  ordering-score refactor and test fix stay available to the later items
  built on it (tier2/batch4).

### 2026-11-05 S512+X: fixed nodes against S512r2, then the STC promotion SPRT (owner)

- The owner (2026-11-05, on its 2.2% lower validation loss) made S512+X a
  promotion candidate: a fixed-node match against S512r2 first, then, if it
  scores above 0, an STC SPRT against S512r2 on [0, 5] and a speed
  measurement; a pass is reported before any promotion.
- Candidate: bake/s512x c62bb3b (nets/s512x 3641a51, phase-4 merged, with
  S512+X seed 2 as the default network, S = 89; bench 14,141,414,
  signature 029f61c7d020711e). Network-dependent tests failing on the
  candidate, logged in its commit (updated only if the SPRT passes): the
  K+P v K promotion at depth 1, the K+R v K mate in 2 at depth 4 and its
  go mate stop, the web test's eval threshold. The endgame check: 307 of
  900 misjudged against S512r2's 249 (KQK 28 of 300 against 0).
- Base: 684bac6 (phase-4, S512r2; bench 14,180,299).

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| fixed nodes, 800,000 per move (600+6 clock that never binds, Hash 16, Syzygy 3-4-5, UHO book) | 42142711426 | 1,600 (no time losses, no abnormal ends) | +25.67 ± 10.26 | +42.76 ± 17.02 | [18, 152, 355, 244, 31] | above 0: the SPRT follows |
| STC 8+0.08, [0, 5] (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027) | 42149140337 (stage 0) | 1,600 (no time losses, no abnormal ends) | −30.04 ± 10.82 | −47.52 ± 17.02 | [49, 235, 338, 161, 17] | **H0 accepted** (LLR −3.32) after stage 0: not promoted |

- Speed (2026-11-05, the owner's method): every other CPU job suspended
  in place (the machine about 6% busy), 12 interleaved rounds of
  single-thread `fork bench`, the order alternating each round, both
  clang-release builds from the candidate's own tree (c62bb3b), S512r2's
  with `FORK_NET` set to nets/s512r2.fnet (its bench 14,180,299, as the
  reference); only the network differs. Median nps: S512r2 3,730,026,
  S512+X 3,060,734; the pairwise ratio median **0.818** (0.793 to 0.846):
  S512+X searches about 18% fewer nodes per second. (A first, loaded
  measurement, 8 pairs beside measurement c, gave the same ratio, 0.818.)

- **Decision: S512+X is not promoted; S512r2 stays the default.** Its
  per-node gain (+25.67 at fixed nodes) does not survive its cost in
  speed at a real clock: at STC it lost 30.04 ± 10.82 Elo. The 0.818 nps
  ratio alone explains part of the swing; the rest is UNVERIFIED (a
  fixed-node match and a timed match also differ in how a net's
  per-node quality turns into depth). The exposure plane's evaluation
  cost is the thing to cut before a retest; the S512cl design, which
  replaces it, is measured for speed before it trains (owner,
  2026-11-05).
- **LTC candidate, low priority** (owner, 2026-11-05; §5.4's rule: it beat
  S512r2 at fixed nodes and failed at STC): S512+X is recorded as an LTC /
  TCEC-conditions candidate. Its priority is low: XGR-512 showed the same
  pattern with a larger fixed-node gain (+30.70 ± 10.37) and failed at LTC
  as well (ltc-r2xgr512-vs-s512r2: −30.56 ± 9.96, H0).

### 2026-11-05 attribution audit of the evening's SPRT runs (owner)

- Why: two SPRT drivers believed stopped kept running (stopping their
  tool tasks ended only a wrapper shell), and the session reported the
  check-relief filler's stage 7 (run 42140703160) as the rising-RFP SPRT's
  stage 0. The owner asked for the job supervisor first (DESIGN.md
  decisions, 2026-11-05) and then this audit.
- Method: every run of sprt.yml created from 5:00 PM EST on, each
  attributed by the inputs GitHub recorded for it (BASE, TEST and STAGE in
  its build job's environment, TC and TEST_OPTS in its shard jobs, read
  from the run's log), then compared with every driver log and with this
  log. Each folder of merged results was checked too (16 shard results,
  every one's meta naming its stage's base, test and stage). Every run
  below is now in the run-ID ledger, imported with that evidence.

| Run | Created (EST) | Base | Test | Stage | TC | Conclusion | Attributed to |
|---|---|---|---|---|---|---|---|
| 42119021732 | 5:09 PM | 684bac6 | cf614e0 | 2 | 8+0.08 | success | lmrh-24000-vs-base, stage 2 (as logged above) |
| 42121703916 | 5:27 PM | 684bac6 | cf614e0 | 3 | 8+0.08 | success | lmrh-24000-vs-base, stage 3, H0 (as logged above) |
| 42124558432 | 5:48 PM | 684bac6 | 7d72dc5 | 0 | 8+0.08 | success | reval-no-check-relief, stage 0 |
| 42127059653 | 6:06 PM | 684bac6 | 7d72dc5 | 1 | 8+0.08 | success | reval-no-check-relief, stage 1 |
| 42129326936 | 6:26 PM | 684bac6 | 7d72dc5 | 2 | 8+0.08 | success | reval-no-check-relief, stage 2 |
| 42131787180 | 6:45 PM | 684bac6 | 7d72dc5 | 3 | 8+0.08 | success | reval-no-check-relief, stage 3 |
| 42134041089 | 7:03 PM | 684bac6 | 7d72dc5 | 4 | 8+0.08 | success | reval-no-check-relief, stage 4 |
| 42136314266 | 7:22 PM | 684bac6 | 7d72dc5 | 5 | 8+0.08 | success | reval-no-check-relief, stage 5 |
| 42138562937 | 7:40 PM | 684bac6 | 7d72dc5 | 6 | 8+0.08 | success | reval-no-check-relief, stage 6 |
| 42140703160 | 7:59 PM | 684bac6 | 7d72dc5 | 7 | 8+0.08 | success | reval-no-check-relief, stage 7 (**reported at the time as rising-RFP stage 0: wrong**) |
| 42142711426 | 8:16 PM | 684bac6 | c62bb3b | 0 | 600+6, nodes=800000 | success | S512+X fixed-node match (as logged above) |
| 42147267048 | 8:58 PM | 684bac6 | 7d72dc5 | 8 | 8+0.08 | success | reval-no-check-relief, stage 8 |
| 42149140337 | 9:15 PM | 684bac6 | c62bb3b | 0 | 8+0.08 | success | s512x-vs-s512r2-stc, stage 0, H0 (as logged above) |
| 42151218549 | 9:34 PM | 684bac6 | 7d72dc5 | 9 | 8+0.08 | cancelled | reval-no-check-relief, stage 9, cancelled at 9:39 PM so that PR #7's CI ran alone; not merged |

- Corrections:
  - **The rising-RFP SPRT (684bac6 against db6a238, [0, 3]) has not
    played a game.** Its driver started at 7:53 PM, waited for an idle
    GitHub and never dispatched; it was killed with the filler's driver.
    No run of it exists.
  - **The check-relief filler was not paused at 7:52 PM**: its driver kept
    running and dispatched stages 6 to 9 (stage 9 cancelled). Stages 6, 7
    and 8 are valid results of its own test and are kept.
  - The milestone checklist (docs/history/phase-4/m1-checklist.md, PR #7)
    quotes the filler after stage 5 (9,600 games), stale when written; its
    standing is the stage 8 line below.
- No result was merged into the wrong SPRT: every driver logged and merged
  only its own runs (the merge's meta check), and the S512+X and
  LMR-history results above stand.

### 2026-11-06 rising-rfp-25-vs-base (tier 2, T18: the improving flag's RFP use)

- Base `684bac6` (phase-4: S512r2, IIR on), test `db6a238` (branch
  sprt/rising-rfp: the same with `use_rising_rfp` on and the measured
  RfpRisingRelief 25; bench 13,348,788). Bounds [0, 3] nElo, 8+0.08, Hash
  16 MB, Syzygy 3-4-5, GitHub shards, under the job supervisor (job
  sprt-queue); base and test confirmed from the driver's log, every run in
  the ledger.
- Stages (Elo, nElo, LLR after each): 0 (run 42182458597) +2.61 ± 10.13,
  +4.38 ± 17.02, 0.11; 1 (42184474127) −4.89 ± 6.95, −8.47 ± 12.04,
  −0.79; 2 (42186645482) −3.76 ± 5.77, −6.41 ± 9.83, −0.94; 3
  (42188861332) −4.29 ± 5.03, −7.26 ± 8.51, −1.39; 4 (42191066128) −5.43 ±
  4.50, −9.18 ± 7.61, −2.12; 5 (42193358994) −4.96 ± 4.12, −8.36 ± 6.95,
  −2.35; 6 (42195711045) −3.32 ± 3.84, −5.56 ± 6.43, −1.96; 7
  (42197996963) −3.77 ± 3.59, −6.32 ± 6.02, −2.49; 8 (42200356838) −3.23 ±
  3.39, −5.42 ± 5.67, −2.48; 9 (42202745022) −3.02 ± 3.20, −5.08 ± 5.38,
  −2.62; 10 (42205083270) −3.10 ± 3.05, −5.22 ± 5.13, −2.94 (continue); 11
  (42207392364) H0. Result: **H0 accepted** after stage 11:
```
Shards: 192 (done); pairs 9600, games 19200 (19200 finished, time losses 0, abnormal 0)
Elo: -3.78 +/- 2.92, nElo: -6.37 +/- 4.91
Ptnml(0-2): [279, 2405, 4409, 2260, 247]
LLR: -3.76 (-2.94, 2.94) [0.00, 3.00] nElo: H0 accepted
```
- Not adopted: `use_rising_rfp` stays off. It agrees with its measurement,
  where no relief beat "off" (relief 25 chosen, gain interval below zero).

### ProbCut (tier 2, T31): queued after rising-RFP and the filler (owner, 2026-11-06)

- The measurement (tools/tier2_measure.py, spec capture_probe.json,
  declared 2026-11-05; 120 settings screened at 250,000 nodes, the best 6
  with "off" at both budgets) chose d9-r5-m80 (CaptureProbeMinDepth 9,
  CaptureProbeReduction 5, CaptureProbeMargin 80): fitness 0.7490 against
  off 0.7539, gain −0.0049 [−0.0101, +0.0006]; **no setting's gain interval
  lies above zero**, and the depth and reduction sit at the top edge of
  their grids. No grid extension (owner).
- **The SPRT decides** (STC, [0, 3]; owner): measurement scores below
  "off" also preceded IIR's adoption (no depth beat "off" in its
  measurement, then +21.45 ± 5.98 Elo at STC and +26.25 ± 6.65 at LTC), so a
  score below "off" does not by itself predict the SPRT.
- The constant screen (before the commit that sets the values) found the
  margin 80 an exact same-role match (Ethereal 12.50-13.00's ProbCut
  margin; also Xiphos); the reduction 5 matches as a literal only (Fork's
  verification search is one ply deeper); the minimum depth 9 has no
  same-role match. **The owner kept 80 with a credit note** (2026-11-06,
  ORIGINALITY.md on tier2/batch3; no finer grid), and the test commit
  follows.
- The SPRT: base 684bac6 (S512r2), test 899c10b (sprt/probcut), [0, 3],
  8+0.08, job sprt-probcut, started 4:35 PM EST on 2026-11-06, after
  S512+PP's STC SPRT. **The owner's rule after S512+PP's promotion**
  (2026-11-06): if it passes, a quick confirmation on S512+PP (the same
  change on the new default, STC [0, 3], at most 2 stages) before it is
  adopted; if it fails, no retest.
- Stages 0-7: runs 42297962496, 42300440558, 42302881667, 42305269054,
  42307539187, 42309763357, 42311908276, 42313931445 (ledger).
- **Result (after stage 7, 7:04 PM EST): H0 accepted.** 12,800 games, Elo
  −5.29 +/- 3.58, nElo −8.90 +/- 6.02, LLR −3.31 (−2.94, 2.94), Ptnml [198,
  1611, 2937, 1496, 158]; no time losses. ProbCut (d9-r5-m80) stays off;
  no retest (the owner's rule).

### 2026-11-06 threat-set-cheaper-vs-base (tier 2, T56: threat-aware ordering): H0, rejected (stays off)

- The measurement (threat_set.json, declared 2026-11-05): off 0.7539,
  any-attack 0.7331 (gain −0.0208 [−0.0285, −0.0128]), cheaper-attacker
  0.7377 (−0.0162 [−0.0237, −0.0087]): cheaper-attacker chosen; no gain
  interval above zero, so the SPRT decides. No new constants.
- Base `684bac6` (phase-4: S512r2, IIR on), test `541ea70` (branch
  sprt/threat-set: `use_threat_buckets` and `use_cheaper_threats` on; bench
  13,277,455, signature a2aa28300166a46d; the full non-slow suite passes).
  Bounds [0, 3] nElo, 8+0.08, under the job supervisor (job sprt-threat),
  started 9:47 AM EST; stage 0 is run 42237009121 (ledger). It took the
  GitHub slot while ProbCut's test commit waits on the owner.
- Stages 1-4: runs 42270364725, 42273143225, 42275889794, 42278631502
  (stages 3-4 dispatched by a driver that outlived its job's stop; their
  results are valid and in the ledger). Re-attached for stages 5-7 by job
  sprt-threat2 (`RUN_ID`): runs 42281365784, 42289547143, 42292120505.
- **Result (after stage 7, 4:11 PM EST): H0 accepted.** 12,800 games, Elo
  −6.08 +/- 3.59, nElo −10.20 +/- 6.02, LLR −3.72 (−2.94, 2.94),
  Ptnml [180, 1671, 2922, 1447, 180]; no time losses. The cheaper-attacker
  threat set costs about 6 Elo at STC: `use_threat_buckets` and
  `use_cheaper_threats` stay off. As with the measurement, both variants lost
  to "off"; T56 is closed for this network (a later net may be re-tested only
  as a new idea).

### 2026-11-06 S512+PP R = 1: fixed nodes against S512r2, then the STC SPRT (owner)

- The owner's rule (2026-11-06, DESIGN.md §5.6 item 7): the fixed-node
  screen against S512r2 first; an STC SPRT only if it exceeds about +30
  Elo; a pass makes S512+PP the architecture of item 7's retrain, and is
  reported before any promotion.
- Candidate: bake/s512pp 412b13f (S512+PP seed 2, S = 90, 2 of 311,296
  link weights clamped; bench 13,909,380, signature 831e5c9295839f87).
  Network-dependent search checks failing on it, logged in its commit:
  the K+P v K promotion at depth 1, K+R v K at depth 3 scoring at most 0.
  Endgame check: 351 of 900 misjudged against S512r2's 249 (KQK 59 of 300
  against 0). Speed: 0.895 of S512r2's nps (identical-tree method, the
  owner's recorded exception to the 0.90 gate; ideas.md idea 40).
- Base: 684bac6 (phase-4, S512r2; bench 14,180,299). Both under the job
  supervisor (jobs sprt-ppfixed, sprt-ppstc).

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| fixed nodes, 800,000 per move (600+6 clock that never binds, Hash 16, Syzygy 3-4-5, UHO book) | 42284077960 | 1,600 (no time losses, no abnormal ends) | +46.09 ± 10.37 | +76.54 ± 17.02 | [16, 121, 339, 284, 40] | above +30: the STC SPRT follows |
| STC 8+0.08, [0, 5] (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027) | 42294907752 (stage 0) | 1,600 (no time losses, no abnormal ends) | **+32.67 ± 10.48** | +53.37 ± 17.02 | [14, 154, 341, 250, 41] | **H1 accepted** (LLR 3.37) after stage 0, 4:33 PM EST |

The driver's result blocks (jobs sprt-ppfixed and sprt-ppstc):

```
s512pp-r1-fixednode, stage 0, run 42284077960:
    Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 46.09 +/- 10.37, nElo: 76.54 +/- 17.02
    Ptnml(0-2): [16, 121, 339, 284, 40]
s512pp-r1-stc, stage 0, run 42294907752:
    Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 32.67 +/- 10.48, nElo: 53.37 +/- 17.02
    Ptnml(0-2): [14, 154, 341, 250, 41]
    LLR: 3.37 (-2.94, 2.94) [0.00, 5.00] nElo: H1 accepted
```

- Unlike S512+X (+25.67 at fixed nodes, −30.04 at STC), most of S512+PP's
  per-node gain survives its speed cost at a real clock.
- **Consequence (the owner's pre-declared gate): item 7's retrain uses the
  S512+PP architecture** (retrain_g3s2.py's ARCH = s512pp; the warm recipe
  starts from this candidate's float weights).
- Reported to the owner with what was open: the two failing search
  checks, the weaker endgame check (KQK 59 of 300, which the Syzygy slice
  in g3s2 is meant to fix) and the nps ratio below the 0.90 gate.
- **Promoted (owner, 2026-11-06, the same evening): S512+PP is the default
  network**, with the speed exception (0.895) and the endgame-check result
  recorded (docs/nets.md); the two search checks rewritten to hold for any
  evaluator (the promotion rule); bench 13,909,380 / 831e5c9295839f87.
  Generation 3's part g3e was stopped and sealed, and the next part, g3f,
  is labelled by S512+PP (the labeller policy). Item 7's candidate must
  now beat S512+PP.

### 2026-11-06 S512ppr2 (item 7's retrain): the STC SPRT against S512+PP (owner)

- The owner's rule (2026-11-06, DESIGN.md §5.6 item 7): the better
  recipe's best seed goes through parity, the endgame acceptance test and
  its STC SPRT against S512+PP, the default; reported before any
  promotion.
- Candidate: bake/s512ppr2 d56c2cf (S512+PP retrained on g3s2 with the
  Syzygy endgame slice: the warm recipe, seed 1, S = 89, 2 of 311,296 link
  weights clamped; bench 14,626,377, signature 9e43990217b0886d). Recipes:
  warm mean best loss 0.01909453, scratch 0.01951758 (resolved). Parity:
  quantization loss max 7.9 cp, p99 6.1 cp. Endgame check: 8 of 900
  misjudged against S512+PP's 351 (a recall figure: 898 of the 900 are slice
  positions; bug review T1, 2026-11-11). The full non-slow suite passes on it.
- Base: b115e03 (phase-4, S512+PP; bench 13,909,380). Under the job
  supervisor (job sprt-ppr2).

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| STC 8+0.08, [0, 5] (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027) | 42335141916 (stage 0), 42336446490 (stage 1) | 3,200 (no time losses, no abnormal ends) | **+20.11 ± 7.22** | +33.60 ± 12.04 | [36, 323, 720, 462, 59] | **H1 accepted** (LLR 4.12) after stage 1, 11:18 PM EST |

The driver's result blocks (job sprt-ppr2):

```
s512ppr2-stc, stage 0, run 42335141916:
    Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 27.42 +/- 10.34, nElo: 45.36 +/- 17.02
    Ptnml(0-2): [21, 143, 357, 247, 32]
    LLR: 2.84 (-2.94, 2.94) [0.00, 5.00] nElo: continue
s512ppr2-stc, stage 1, run 42336446490:
    Shards: 32 (done); pairs 1600, games 3200 (3200 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 20.11 +/- 7.22, nElo: 33.60 +/- 12.04
    Ptnml(0-2): [36, 323, 720, 462, 59]
    LLR: 4.12 (-2.94, 2.94) [0.00, 5.00] nElo: H1 accepted
```

- **Promoted (owner, 2026-11-06, the same evening): S512ppr2 is the
  default network**; bench 14,626,377 / 9e43990217b0886d. The warm start
  at LR 0.0001 becomes the standard retrain recipe. Generation 3's part
  g3f was stopped and sealed, and the next part, g3g, is labelled by
  S512ppr2 (the labeller policy).

### 2026-11-07 S512ppr3 (item 8a's retrain): fixed nodes against S512ppr2, then the STC SPRT (owner)

- The owner's tie-break (2026-11-07, declared before any result; DESIGN.md
  §6): item 8a's candidate by the declared rule, R1-avg, was 1.82e-5 below
  S512ppr2 on g3s3-val's full set, short of the 2e-5 SPRT margin, so one
  1,600-game fixed-node screen decides: the STC SPRT [0, 5] runs only if
  the screen reaches +5 Elo or more. From now on retrain candidates are
  gated by the fixed-node screen instead of the validation-loss margin.
- Candidate: bake/s512ppr3 720fe7b (S512ppr2 retrained warm on g3s3 with
  the standard recipe, seed 1, the mean of superbatches 331-360's float
  weights; S = 89, 1 of 311,296 link weights clamped; bench 14,149,617,
  signature 1cb0717f040c294d). Parity: quantization loss max 9.4 cp, p99
  7.5 cp. Endgame check: 8 of 900 misjudged, as S512ppr2. The full
  non-slow suite passes on it.
- Base: 98cf000 (phase-4, S512ppr2; bench 14,626,377). Under the job
  supervisor (jobs s512ppr3-fixednode, s512ppr3-stc, s512ppr3-stc-r).
- The STC driver stopped when the machine crashed at about 8:07 PM EST,
  just after it had dispatched stage 2 (run 42432793282); it was resumed at
  8:13 PM as job s512ppr3-stc-r with RUN_ID for that stage (the run the
  ledger already recorded for it), which it waited for and merged; no stage
  was dispatched twice.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| fixed nodes, 800,000 per move (600+6 clock that never binds, Hash 16, Syzygy 3-4-5, UHO book) | 42426868742 | 1,600 (no time losses, no abnormal ends) | +15.65 ± 9.26 | +28.80 ± 17.02 | [7, 161, 406, 205, 21] | above +5: the STC SPRT follows (7:28 PM EST) |
| STC 8+0.08, [0, 5] (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027) | 42429984619 (stage 0), 42431412304 (1), 42432793282 (2), 42434196075 (3), 42435511074 (4) | 8,000 (no time losses, no abnormal ends) | **+7.12 ± 4.53** | +11.98 ± 7.61 | [100, 908, 1848, 1016, 128] | **H1 accepted** (LLR 3.14) after stage 4, 9:02 PM EST |

The drivers' result blocks (jobs s512ppr3-fixednode, s512ppr3-stc and
s512ppr3-stc-r):

```
s512ppr3-fixednode, stage 0, run 42426868742:
    Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 15.65 +/- 9.26, nElo: 28.80 +/- 17.02
    Ptnml(0-2): [7, 161, 406, 205, 21]
    LLR: 1.74 (-2.94, 2.94) [0.00, 5.00] nElo: continue
s512ppr3-stc, stage 0, run 42429984619:
    Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 10.43 +/- 10.08, nElo: 17.63 +/- 17.02
    Ptnml(0-2): [14, 189, 358, 213, 26]
    LLR: 1.00 (-2.94, 2.94) [0.00, 5.00] nElo: continue
s512ppr3-stc, stage 1, run 42431412304:
    Shards: 32 (done); pairs 1600, games 3200 (3200 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 6.95 +/- 7.17, nElo: 11.67 +/- 12.04
    Ptnml(0-2): [38, 373, 726, 413, 50]
    LLR: 1.21 (-2.94, 2.94) [0.00, 5.00] nElo: continue
s512ppr3-stc, stage 2, run 42432793282 (merged by the resumed driver, s512ppr3-stc-r):
    Shards: 48 (done); pairs 2400, games 4800 (4800 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 7.96 +/- 5.85, nElo: 13.38 +/- 9.83
    Ptnml(0-2): [57, 547, 1105, 611, 80]
    LLR: 2.16 (-2.94, 2.94) [0.00, 5.00] nElo: continue
s512ppr3-stc, stage 3, run 42434196075:
    Shards: 64 (done); pairs 3200, games 6400 (6400 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 7.28 +/- 5.08, nElo: 12.20 +/- 8.51
    Ptnml(0-2): [80, 728, 1476, 810, 106]
    LLR: 2.57 (-2.94, 2.94) [0.00, 5.00] nElo: continue
s512ppr3-stc, stage 4, run 42435511074:
    Shards: 80 (done); pairs 4000, games 8000 (8000 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 7.12 +/- 4.53, nElo: 11.98 +/- 7.61
    Ptnml(0-2): [100, 908, 1848, 1016, 128]
    LLR: 3.14 (-2.94, 2.94) [0.00, 5.00] nElo: H1 accepted
```

- **Promoted (owner, 2026-11-07, about 9:05 PM EST): S512ppr3 is the
  default network**; bench 14,149,617 / 1cb0717f040c294d. Generation 3's
  part g3i ends at a game boundary and is sealed as its part, and the next
  part, g3j, is labelled by S512ppr3 from a fresh PGO build (the labeller
  policy).

### reval-no-check-relief (re-validation filler: check relief removed, [−3, 0]; undecided at the cap)

- Base `684bac6` (phase-4: S512r2, IIR on), test `7d72dc5`
  (reval/no-check-relief: `use_lmr_check_relief` off; bench 13,846,386).
  Non-regression bounds [−3, 0] nElo: H1 would mean the feature can be
  simplified away. 8+0.08, Hash 16 MB, Syzygy 3-4-5, GitHub shards.
- After each stage (runs above; Elo, nElo, LLR): 0 −2.61 ± 10.27, −4.32 ±
  17.02, −0.11; 1 −2.06 ± 7.18, −3.46 ± 12.04, −0.16; 2 −3.91 ± 5.84,
  −6.58 ± 9.83, −0.61; 3 −2.77 ± 5.09, −4.63 ± 8.51, −0.50; 4 −4.56 ±
  4.58, −7.58 ± 7.61, −1.21; 5 −3.58 ± 4.17, −5.98 ± 6.95, −1.07; 6 −3.57 ±
  3.86, −5.95 ± 6.43, −1.24; 7 −4.53 ± 3.61, −7.55 ± 6.02, −1.93; **8
  (14,400 games) −3.86 ± 3.40, −6.44 ± 5.67, LLR −1.77: continue.**
- Resumed at stage 9 under the job supervisor (job sprt-queue) after the
  rising-RFP SPRT: 9 (run 42210007657) −2.89 ± 3.23, −4.82 ± 5.38, −1.32;
  10 (42212271728) −2.37 ± 3.09, −3.94 ± 5.13, −1.07; 11 (42214489259)
  −2.90 ± 2.97, −4.80 ± 4.91, −1.57; 12 (42216819947), the last stage.
  Result: **undecided at the 12-stage cap** (20,800 games):
```
Shards: 208 (done); pairs 10400, games 20800 (20800 finished, time losses 1, abnormal 1)
Elo: -3.16 +/- 2.86, nElo: -5.22 +/- 4.72
Ptnml(0-2): [331, 2616, 4656, 2505, 292]
LLR: -1.92 (-2.94, 2.94) [-3.00, 0.00] nElo: continue
```
- Removing check relief cost about 3 Elo (−3.16 ± 2.86, the interval
  almost entirely below zero), so H1 (simplify it away) was not reached:
  check relief stays on. **Closed by the owner** (2026-11-06): check relief
  stays on, and the filler is not run further.

### 2026-11-08 time management (think tank R8, idea tm-r8): head-to-head (a) against (b), then the design R SPRT of (b) against off (owner): H1 at STC and LTC, adopted

- Variants behind two switches (tm/node-share c3780dc, switches off;
  bench 14,149,617 / 1cb0717f040c294d): (a) stability only (tm/a ccdf814),
  (b) stability plus the every-pass node share (tm/b 620cd05). The
  constants are fitted on Fork's own X6 data; the stability cap is 72,
  derived by the owner's declared rule after the cap 10 matched other
  engines (constant screens and re-screen: ORIGINALITY.md on tm/node-share).
- Head-to-head (owner, 2026-11-07: pick by head-to-head before the design
  R SPRT, preferring (a) within the 0.5 e margin; decision 3), STC 8+0.08,
  2 stages of 1,600 games on the same openings, job tm-h2h, runs
  42488242225 and 42495448043: **b − a +22.75 ± 12.04 nElo**, 3,200 games,
  Ptnml [23, 347, 763, 422, 45]: (b) picked (beyond the tie margin).
- Design R SPRT (decision 2; [0, 6] nElo, alpha 0.05, beta 0.20, cap 8,
  futility after 2 stages), STC, fresh openings from stage 2, job
  tm-r8-stc, try 1 of 2:

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| STC 8+0.08, design R [0, 6] (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027), (b) against off | 42503358810 (stage 2), 42504937998 (3) | 3,200 (no time losses, no abnormal ends) | **+18.69 ± 7.18** | +31.40 ± 12.04 | [37, 319, 738, 447, 59] | **H1 accepted** (LLR 4.52) after stage 3, 12:46 PM EST |
| LTC 40+0.4, design R [0, 6], cap 6 (Hash 64, Syzygy 3-4-5, UHO book, seed 20261027, fresh openings from stage 4), (b) against off | 42509883303 (stage 4), 42516750821 (5), 42523612679 (6) | 4,992 (no time losses, no abnormal ends) | **+10.23 ± 5.14** | +19.22 ± 9.64 | [15, 561, 1214, 674, 32] | **H1 accepted** (LLR 4.02) after stage 6, 5:30 PM EST |

- Predicted beforehand (UNVERIFIED model): +3 to +4 Elo at STC; the result
  is far above it. Time management is on the LTC list: its LTC SPRT
  (design R at 40+0.4, Hash 64, 1,664 games per stage, cap 6, fresh
  openings from stage 4; job tm-r8-ltc) started at 1:24 PM EST (owner,
  2026-11-08: adopt into phase-4 only after LTC passes). Time management
  does not run in data generation (node-limited), so its adoption does not
  touch the labeller.
- **(b) adopted into phase-4** after the LTC pass (owner's rule of
  2026-11-08): tm/b merged, `UseStabilityTime` and `UseShareTime` on by
  default, both kept as switches until the Phase 4 re-validation; bench
  unchanged (14,149,617 / 1cb0717f040c294d).

### 2026-11-08 idea 60 (near-window extension): head-to-head 10 against 25 cp, then the design R SPRT of 10 cp against off (owner): H0, retired

- Build: idea60/extension 4f4ddf2 (switch off; bench 14,149,617);
  candidates idea60/m10 e5fb07d and idea60/m25 f0d0efb. Node cost at equal
  depth (job idea60-cost): +6.2% / +5.6% at 10 cp, +14.4% / +11.5% at 25 cp
  (depths 12 / 14), both under the ~15% kill line. Constant screen passed
  (ORIGINALITY.md on idea60/extension).
- Head-to-head, STC, 2 stages of 1,600 games on the same openings, job
  idea60-h2h, runs 42497021804 and 42498592679: **25 − 10 −3.24 ± 12.04
  nElo**, 3,200 games, Ptnml [49, 396, 726, 382, 47]: 10 kept (the declared,
  cheaper value).
- Design R SPRT, STC, fresh openings from stage 2, job idea60-stc, try 1
  of 2:

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| STC 8+0.08, design R [0, 6] (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027), 10 cp against off | 42506706880 (stage 2), 42508251512 (3) | 3,200 (no time losses, no abnormal ends) | **−5.43 ± 7.25** | −9.01 ± 12.04 | [46, 425, 705, 381, 43] | **H0 accepted** (LLR −1.91) after stage 3, 1:24 PM EST |

- By its kill criterion (ideas.md idea 60: the SPRT fails), **idea 60 is
  retired**; the switch stays off on its branch, and nothing reaches
  phase-4. Window-aware LMR (idea 61 part 5) no longer needs a combined
  test with it.

### 2026-11-08 idea 61 part 5 (window-aware LMR): head-to-head of the minimum depth, then the design R SPRT of the pick against off (owner): futility stop, retired

- Build: idea61/window-lmr e84827a (switch off; bench 14,149,617). M1 found
  reductions near alpha beat alpha 58 times as often as reductions far from
  it; M2's node cost at equal depth kept two 10 cp variants under the ~15%
  kill line (+13.2% / +14.4% at every depth; +9.3% / +9.2% at depth >= 6,
  D = 6 by the declared rule) and dropped 25 and 50 cp. Constant screens
  passed (ORIGINALITY.md on idea61/window-lmr); a Stockfish relative
  (5f7348f0) credited at concept level. Candidates idea61/lmr-b10d ce50ca4
  (depth >= 6) and idea61/lmr-b10 720937c (every depth).
- Head-to-head, STC, 2 stages of 1,600 games on the same openings, job
  idea61-h2h, runs 42530631909 and 42532153075: **d0 − d6 −2.19 ± 12.04
  nElo**, 3,200 games, Ptnml [51, 374, 754, 378, 43]: d6 kept (the declared,
  cheaper value).
- Design R SPRT, STC, fresh openings from stage 2, job idea61-stc, try 1
  of 2:

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| STC 8+0.08, design R [0, 6] (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027), d6 against off | 42533970705 (stage 2), 42535473794 (3) | 3,200 (no time losses, no abnormal ends) | **−2.93 ± 7.16** | −4.93 ± 12.04 | [37, 422, 719, 375, 47] | **futility stop** (nElo < 0 after 2 stages; LLR −1.26) after stage 3, 6:48 PM EST |

- By its kill criterion (ideas.md idea 61: a part's SPRT fails, H0 or the
  futility stop), **part 5 is retired**; the switch stays off on its
  branch, and nothing reaches phase-4.

### 2026-11-09 the R14 SPSA's tuned values (idea r14-spsa): the STC design R SPRT against 32c5517 (owner): H1, adopted

- spsa-r14-m2 (think tank decision 4's early pass, R14): seven margins at STC, 13 iterations, 10,400 pairs at 8+0.08 on
  32c5517 (~/fork-spsa/github/spsa-r14-m2: report.txt, final.json). Final values (the mean of the last updates, rounded):
  RfpMargin 80 -> 55 (pinned at the run's floor 40 + c, 15), FutilityOffset 100 -> 86, FutilityGrowth 70 -> 50,
  NullSurplusPerPly 300 -> 301, CaptureSeeFloor 100 -> 118, LmpQuietAllowance 12 -> 8 (pinned at 6 + c, 1.7),
  AspirationHalfWidth 12. Constant screens: no match (ORIGINALITY.md, 2026-11-09).
- Test commit tune/spsa-r14-m2-final c59bd2b (32c5517 with the tuned defaults; bench 10,374,064 / 677c436fa145e07f), job
  night queue item 20, try 1 of 2:

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| STC 8+0.08, design R [0, 6] (Hash 16, Syzygy 3-4-5, UHO book), tuned against 32c5517 | 42726060415 (stage 0) | 1,600 | **+37.93 ± 10.03** | +64.91 ± 17.02 | [9, 139, 358, 257, 37] | **H1** after 1 stage (LLR 4.92) |

- **Adopted on phase-4 (owner, 2026-11-09)** as an explicit exception to the LTC-sensitive rule; bench
  10,374,064 / 677c436fa145e07f. The LTC design R SPRT (item 21, origin 8) and the level 1 anchor check (item 22, claim +38) run
  afterwards as non-blocking confirmations; a failure is reported to the owner, not reverted automatically.

## LTC confirmations of 2026-11-09/10 (night queue items 21, 30, 31)

LTC 40+0.4 on GitHub's shards (Hash 64 MB, x86-64-v3, Syzygy 3-4-5, UHO book), 1,664-game stages; the tuned
values under design R at LTC, the two feature confirmations on non-regression bounds [-3, 0] (alpha = beta = 0.05).
All three ran on the engine before R14's tuned values (test 32c5517 is the pre-R14 phase-4 engine), except item 21,
whose test is the tuned engine.

| Item | Test | Base | Runs | Games | Elo | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|---|---|
| 21, spsa-r14-m2-ltc (design R at LTC, [0, 6], beta 0.20, origin 8) | R14's tuned values `c59bd2b` | `32c5517` | 42738433272 | 1,664 | **+29.93 ± 8.71** | +57.64 ± 16.69 | [4, 137, 418, 258, 15] | **H1** after 1 stage (LLR 4.52) |
| 30, ltc-se-on-vs-off ([-3, 0]) | singular extension on `32c5517` | off `04a58ba` | 42715080880, 42750899342 | 3,328 | **+25.83 ± 6.38** | +48.00 ± 11.80 | [11, 310, 796, 515, 32] | **H1** after 2 stages (LLR 4.09) |
| 31, ltc-mc-on-vs-off ([-3, 0]) | multi-cut on `32c5517` | off `1ba8c7f` | 42728467715, 42759625754, 42801683415, 42812800226, 42824839186, 42837701937 | 9,984 | **+6.65 ± 3.65** | +12.42 ± 6.82 | [49, 1126, 2466, 1287, 64] | **H1** after 6 stages (LLR 3.45) |

- Item 21 confirms the adoption of R14's values (owner's exception, 2026-11-09) at LTC; item 22's anchor check
  (gauntlet run 42747850201, claim +38) also confirmed them: pooled +28.7 (interval +10.4 to +45.9).
- Item 31's stage 2 first ran as 42779796858, whose shard 2 died mid-run (a runner failure); the queue retried the
  stage as 42801683415. Item 32 (take history's LTC confirmation) was dropped by the owner on 2026-11-10: the
  factorial removal round covers that switch.

### 2026-11-10 r8btd90 (retrain 8b's TD(0.9) arm): fixed-node screens of 8b's candidates against S512ppr3, then the STC SPRT (owner)

- Retrain 8b (docs/research/retrain-8b/plan.md §3, declared before any result; branch retrain/8b-prep): every
  candidate is its arm's window average, gated (S = 89, netcheck exact on 446 positions, quantization loss within
  S-512's limits; the endgame check reported: 7 of 900 misjudged for each of c, i52, td80 and td90, S512ppr3 8),
  then screened against S512ppr3 at fixed nodes; the highest screen goes to the STC SPRT [0, 5] against S512ppr3.
- Base: c67fd26 (phase-4, S512ppr3; bench 10,374,064 / 677c436fa145e07f). Candidates: bake/r8bc 33da6a5 (the
  control), bake/r8bi52 4dddcc2 (idea 52's arm), bake/r8btd80 7af782f and bake/r8btd90 115daad (idea 51's TD(0.8)
  and TD(0.9) arms; bench 9,594,307 / 4eb36793548711d4). Jobs r8b-fn-c, r8b-fn-i52, r8b-fn-td80, r8b-fn-td90 and
  r8b-stc-1 (`--kind network`, idea retrain-8b, try 1 of 2).

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| fixed nodes, 800,000 per move (600+6, Hash 16, Syzygy 3-4-5, UHO book), c against S512ppr3 | 42889810114 | 1,600 | +13.03 ± 9.37 | +23.70 ± 17.02 | [9, 175, 375, 229, 12] | screen (3:34 PM EST) |
| the same, i52 against S512ppr3 | 42896624050 | 1,600 | +5.86 ± 9.13 | +10.93 ± 17.02 | [9, 181, 393, 208, 9] | screen (4:17 PM EST) |
| the same, td80 against S512ppr3 | 42903541854 | 1,600 | −1.09 ± 9.30 | −1.99 ± 17.02 | [12, 194, 392, 191, 11] | screen (5:01 PM EST) |
| the same, td90 against S512ppr3 | 42910703028 | 1,600 | +17.39 ± 9.71 | +30.53 ± 17.02 | [9, 174, 367, 228, 22] | the highest screen: the STC SPRT follows (5:42 PM EST) |
| STC 8+0.08, [0, 5] (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027), td90 against S512ppr3 | 42917050282 (stage 0), 42919747964 (1), 42922442883 (2) | 4,800 (no time losses, no abnormal ends) | **+12.17 ± 5.71** | +20.96 ± 9.83 | [61, 483, 1147, 645, 64] | **H1 accepted** (LLR 3.67) after stage 2, 6:38 PM EST |

The drivers' result blocks:

```
r8b-fn-td90, stage 0, run 42910703028:
    Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 17.39 +/- 9.71, nElo: 30.53 +/- 17.02
    Ptnml(0-2): [9, 174, 367, 228, 22]
    LLR: 1.86 (-2.94, 2.94) [0.00, 5.00] nElo: continue
r8b-stc-1, stage 0, run 42917050282:
    Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 8.47 +/- 9.54, nElo: 15.13 +/- 17.02
    Ptnml(0-2): [16, 168, 393, 207, 16]
    LLR: 0.84 (-2.94, 2.94) [0.00, 5.00] nElo: continue
r8b-stc-1, stage 1, run 42919747964:
    Shards: 32 (done); pairs 1600, games 3200 (3200 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 10.64 +/- 7.00, nElo: 18.32 +/- 12.04
    Ptnml(0-2): [43, 321, 775, 417, 44]
    LLR: 2.10 (-2.94, 2.94) [0.00, 5.00] nElo: continue
r8b-stc-1, stage 2, run 42922442883:
    Shards: 48 (done); pairs 2400, games 4800 (4800 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 12.17 +/- 5.71, nElo: 20.96 +/- 9.83
    Ptnml(0-2): [61, 483, 1147, 645, 64]
    LLR: 3.67 (-2.94, 2.94) [0.00, 5.00] nElo: H1 accepted
```

- **Promoted (owner, 2026-11-10, about 6:45 PM EST): r8btd90 is the default network**; bench 9,594,307 /
  4eb36793548711d4. The labeller policy (owner): the running label-depth arms stay on S512ppr3 until they end
  (switching would confound that experiment); the positional slice and g4c use r8btd90.
- Still open (plan §3 items 6 and 7, not decided by this promotion): the head-to-head screens of i52, td80 and td90
  against the control c (r8b-h2h-i52 running; the TD arms' queued), which decide ideas 51 and 52.

### 2026-11-10/11 retrain 8b's head-to-heads against the control; idea 69's cw arm and the seed-noise run (owner)

- Retrain 8b's plan §3 items 6 and 7 (declared before any result): each arm's keep rule is its head-to-head against
  the control c (bake/r8bc 33da6a5) at the screens' settings (800,000 nodes per move, 600+6, Hash 16, Syzygy 3-4-5,
  UHO book), 1,600 games: idea 51's TD arms are kept above +4 Elo, idea 52's arm at +5 or more (ideas.md 51, 52).
  Idea 69's cw arm (bake/r8bcw 9fd957b: arm c's data, recipe and seed with the class weights; keep rule +5 head to
  head against the control, or a passing STC SPRT) and the control's re-run with another seed, c2 (bake/r8bc2
  38155d9), were added on 2026-11-10 (DESIGN.md §6). Jobs r8b-h2h-i52, r8b-h2h-td80, r8b-h2h-td90, r8b-fn-cw,
  r8b-h2h-cw, r8b-stc-cw (`--kind network`, idea idea69, try 1 of 2) and r8b-h2h-c2.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| fixed nodes, 800,000 per move, i52 against c | 42925024784 | 1,600 | −4.13 ± 9.60 | −7.32 ± 17.02 | [19, 192, 393, 181, 15] | head-to-head (7:19 PM EST, 11-10): not kept |
| the same, td80 against c | 42930415181 | 1,600 | −0.87 ± 9.13 | −1.62 ± 17.02 | [14, 179, 415, 181, 11] | head-to-head (7:59 PM EST, 11-10): not kept |
| the same, td90 against c | 42935666743 | 1,600 | **+4.13 ± 9.47** | +7.42 ± 17.02 | [13, 186, 383, 205, 13] | head-to-head (8:40 PM EST, 11-10): above +4, **TD(0.9) labels kept** |
| the same, cw against S512ppr3 (c67fd26) | 42940727058 | 1,600 | +3.04 ± 9.74 | +5.31 ± 17.02 | [20, 177, 390, 195, 18] | screen (9:21 PM EST, 11-10) |
| the same, cw against c | 42945518194 | 1,600 | +3.04 ± 9.25 | +5.60 ± 17.02 | [10, 185, 400, 191, 14] | head-to-head (10:00 PM EST, 11-10): below +5, so the STC SPRT decides |
| STC 8+0.08, [0, 5] (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027), cw against c | 42949849410 (stage 0), 42951964846 (1), 42954032939 (2), 42955981034 (3) | 6,400 (no time losses, no abnormal ends) | **−7.60 ± 4.91** | −13.18 ± 8.51 | [85, 819, 1510, 723, 63] | **H0 accepted** (LLR −4.16) after stage 3, 11:14 PM EST, 11-10: **idea 69 dropped** |
| fixed nodes, 800,000 per move, c2 against c (seed noise) | 42958000486 | 1,600 | −6.08 ± 9.42 | −11.00 ± 17.02 | [16, 201, 388, 185, 10] | the control against itself on another seed (11:53 PM EST, 11-10) |

- **Decided (owner, 2026-11-11, about 6:35 AM EST):** idea 69 dropped (cw H0 −7.60); TD(0.9) labels stay in the
  standard retrain recipe (td90 against the control +4.13); i52 and td80 not kept; seed noise measured (c2 against
  the control −6.08), so **every future retrain arm runs 2 seeds**.

### 2026-11-11 r8brft1 (idea 70's result fine-tune of r8btd90): fixed-node screens of both seeds against r8btd90, then the STC SPRT (owner)

- Idea 70 (docs/research/retrain-8b/rft-plan.md, branch retrain/8b-rft 43f6ecc, declared before any run): r8btd90's
  window average fine-tuned at result weight 1.0, LR 1e-5 constant, 60 superbatches on g4s1, each seed's candidate
  the mean of superbatches 46-60. Both seeds passed the gates (S = 88, netcheck exact on 446, quantization loss within
  S-512's limits; the endgame check 7 of 900 for each, r8btd90 7; ~/fork-jobs/night/state/r8b-rft-ready.json).
- Base: bake/r8btd90 115daad (engine c67fd26; bench 9,594,307 / 4eb36793548711d4). Candidates: bake/r8brft1 4da54db
  (seed 1; bench 10,708,227 / c5dfc0ec1923d3b0) and bake/r8brft2 1ce98b2 (seed 2; bench 10,564,507 /
  74fed831fcb1e0ed). Jobs r8b-rft-fn-rft1, r8b-rft-fn-rft2 and r8b-rft-stc (`--kind network`, idea result-finetune,
  try 1 of 2).

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| fixed nodes, 800,000 per move (600+6, Hash 16, Syzygy 3-4-5, UHO book), rft1 against r8btd90 | 42962187538 | 1,600 | **+7.17 ± 9.93** | +12.29 ± 17.02 | [14, 189, 372, 200, 25] | the higher screen: the STC SPRT follows (12:34 AM EST) |
| the same, rft2 against r8btd90 | 42966665389 | 1,600 | +6.73 ± 9.44 | +12.14 ± 17.02 | [12, 181, 385, 208, 14] | screen (1:45 AM EST) |
| STC 8+0.08, [0, 5] (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027), rft1 against r8btd90 | 42974677403 (stage 0), 42976787971 (1), 42979050772 (2), 42981298644 (3), 42983543508 (4), 42985980827 (5), 42988446282 (6) | 11,200 (no time losses, no abnormal ends) | **+5.74 ± 3.81** | +9.69 ± 6.43 | [131, 1331, 2511, 1476, 151] | **H1 accepted** (LLR 3.34) after stage 6, 3:55 AM EST |

The final stage's result block (r8b-rft-stc, stage 6, run 42988446282):

```
    Shards: 112 (done); pairs 5600, games 11200 (11200 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 5.74 +/- 3.81, nElo: 9.69 +/- 6.43
    Ptnml(0-2): [131, 1331, 2511, 1476, 151]
    LLR: 3.34 (-2.94, 2.94) [0.00, 5.00] nElo: H1 accepted
```

- **Promoted (owner, 2026-11-11, about 6:35 AM EST): r8brft1 is the default network**; bench 10,708,227 /
  c5dfc0ec1923d3b0. The labeller policy (owner): the label-depth arms stay on S512ppr3 and the cloud slice on r8btd90
  until each finishes; g4c and later parts use r8brft1.

### 2026-11-10/11 batch 4 after R14: cut-node (R4) and the structure history (R21, weight 5), design R at STC (owner)

- Base tier2/b4-r14 ff0c088 (batch 4 on phase-4 after R14, every switch off; S512ppr3, as batch 4 keeps its bases).
  Cut-node's constant first, by a head-to-head of CutNodeLmrPlies 1 (6b4e407) against 2 (efefa4b), 2 stages of 1,600
  games on the same openings (b4-cut-node-h2h, runs 42883612798 and 42886734291): **2 − 1 −5.33 ± 12.04 nElo**, 3,200
  games, Ptnml [49, 388, 744, 381, 38]; declared tie rule: 1 (the smaller reduction) unless beaten by more than 0.5 e:
  **1 kept**. Then each switch's design R SPRT ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look after 2
  stages; Hash 16, Syzygy 3-4-5, UHO book, seed 20261027): b4-cut-node-stc (idea r4-cut-node, try 1 of 2, fresh
  openings from stage 2) and b4-structure-stc (tier2/b4-structure-r14 ec00954, StructureHistoryWeight 5; idea
  r21-structure, try 1 of 2).

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| STC 8+0.08, design R [0, 6], cut-node (CutNodeLmrPlies 1) against off | 42948984895 (stage 2), 42951755956 (3), 42953826857 (4), 42955789912 (5), 42957784702 (6), 42959823164 (7), 42961813575 (8) | 11,200 (no time losses, no abnormal ends) | **+6.02 ± 3.67** | +10.55 ± 6.43 | [110, 1281, 2633, 1457, 119] | **H1** (LLR 4.20) after stage 8, 12:10 AM EST, 11-11 |
| STC 8+0.08, design R [0, 6], the structure history (weight 5) against off | 42964043071 (stage 0), 42966088335 (1), 42968522278 (2), 42970581081 (3), 42972740255 (4), 42974917524 (5), 42977050811 (6), 42979311765 (7) | 12,800 (1 time loss, 1 abnormal end) | +2.93 ± 3.46 | +5.10 ± 6.02 | [148, 1482, 3021, 1612, 137] | **capped undecided** (8 of 8 stages, LLR 1.33), 2:45 AM EST, 11-11: not passed |

- **Decided (owner, 2026-11-11, about 6:35 AM EST):** **no retry of structure** (its switch stays off). Cut-node:
  its LTC confirmation b4-cut-node-ltc (40+0.4, Hash 64, design R [0, 6], cap 6, fresh openings from stage 2) is
  running (stage 2, run 42991551149: +6.47 ± 9.17, 1,664 games; after stage 3, run 43002660790: +5.64 ± 6.32, 3,328
  games, LLR 1.25, continue); **pre-approved: adopt cut-node (1 ply) if its LTC confirmation passes; report if it
  fails.**

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| LTC 40+0.4, design R [0, 6], cap 6 (Hash 64, Syzygy 3-4-5, UHO book, seed 20261027, fresh openings from stage 2), cut-node (CutNodeLmrPlies 1) against off | 42991551149 (stage 2), 43002660790 (3), 43013618465 (4) | 4,992 (no time losses, no abnormal ends) | **+9.75 ± 5.14** | +18.28 ± 9.64 | [23, 537, 1250, 649, 37] | **H1 accepted** (LLR 3.79) after stage 4, 7:59 AM EST, 11-11 |

The final stage's result block (b4-cut-node-ltc, stage 4, run 43013618465):

```
    Shards: 48 (done); pairs 2496, games 4992 (4992 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 9.75 +/- 5.14, nElo: 18.28 +/- 9.64
    Ptnml(0-2): [23, 537, 1250, 649, 37]
    LLR: 3.79 (-1.56, 2.77) [0.00, 6.00] nElo: H1 accepted
```

- **Cut-node adopted (owner's pre-approval of 2026-11-11):** ported onto phase-4 b5f11ae alone (branch
  adopt/cut-node), `UseCutNodeLmr` on with CutNodeLmrPlies 1, the switch kept until the Phase 4 re-validation.
  Bench 9,942,973 / accfb975ccd6ccf5 (r8brft1; 10,708,227 / c5dfc0ec1923d3b0 with the switch off); with
  S512ppr3 10,280,126 / 7db684469b226aa7, equal to the tested commit 6b4e407's.
- **Batch 4 closed:** cut-node adopted (STC +6.02 ± 3.67, LTC +9.75 ± 5.14); the structure history not passed
  (+2.93 ± 3.46, capped undecided), no retry; the others dropped, demoted or deferred as the decisions log
  records (2026-11-10: history-skip dropped, razoring and bad-capture futility to the final retune's SPSA,
  PV-trace to the re-validation).

### 2026-11-11 idea 61 part 6 (root-gap time management): head-to-heads of the band and of the extra time, then the design R SPRT of the picks against off (owner): H0, dropped

- Night queue items 60-62 (ledger idea 61.6), rebased onto phase-4 after R14 (decisions log, 2026-11-10). Off:
  320e2f2 (switch off). RootGapBand candidates: b14 734e79c (the placeholder: the 75th percentile of the root
  score's change per iteration on the bench), b7 8aac410, b28 eceaaa1. RootGapExtra candidates, at b7: x667 8aac410
  (the placeholder: one more iteration at Fork's iteration growth 5/3), x333 00d6e61, x1000 1691620. Each
  head-to-head a round robin, STC 8+0.08, 2 stages of 1,600 games per pairing on the same openings (9,600 games),
  declared tie rule: the placeholder unless beaten by more than 0.5 e.
- Band head-to-head (job i61-rg-band, from stage 0; runs 42981823066 and 42984092827 for b14-b7, 42986534047 and
  42989248284 for b14-b28, 42991719425 and 42994331667 for b7-b28): **b7 − b14 +23.84 ± 12.04 nElo**, Ptnml
  [36, 330, 758, 421, 55]; b28 − b14 −12.67 ± 12.04, [48, 397, 768, 349, 38]; b28 − b7 −13.59 ± 12.04, [43, 407,
  760, 359, 31]. Least squares over the three pairings, against b14: b7 **+16.20 ± 9.83** nElo, b28 −5.03 ± 9.83:
  **b7 picked** (beyond the tie margin), 4:38 AM EST.
- Extra head-to-head (job i61-rg-extra, from stage 2; runs 42996954489 and 42999533555 for x667-x333, 43002464741
  and 43005076924 for x667-x1000, 43007628981 and 43010212369 for x333-x1000): **x333 − x667 +5.71 ± 12.04 nElo**,
  Ptnml [44, 367, 744, 404, 41]; x1000 − x667 −3.99 ± 12.04, [40, 372, 798, 349, 41]; x1000 − x333 −14.78 ±
  12.04, [42, 412, 756, 362, 28]. Least squares, against x667: x333 **+7.41 ± 9.83** nElo, x1000 −5.68 ± 9.83:
  **x333 picked** (beyond the tie margin), 6:32 AM EST.
- Design R SPRT ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look after 2 stages), STC, fresh openings
  from stage 4, job i61-rg-stc, try 1 of 2:

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| STC 8+0.08, design R [0, 6] (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027), band b7 + extra x333 (00d6e61) against off (320e2f2) | 43012786722 (stage 4), 43015340549 (5) | 3,200 (no time losses, no abnormal ends) | **−4.89 ± 7.03** | −8.36 ± 12.04 | [46, 392, 762, 361, 39] | **H0 accepted** (LLR −1.81) after stage 5, 7:09 AM EST |

- **Dropped (owner, 2026-11-11, about 3:30 PM EST):** no second try; part 6 is retired, its switch stays off on its
  branch, and nothing reaches phase-4.

### 2026-11-11 T56 any-attack (tier 2, threat-aware quiet ordering; idea 72): the design R SPRT against off at STC, then its LTC confirmation (owner): H1 at both, adopted

- The any-attack set's first game test (the cheaper-attacker set's H0 of 2026-11-06 is above). Base tier2/threat-any
  dc341d5 (the any-attack buckets ported onto phase-4 b787fba behind `use_threat_buckets`, off; r8btd90; bench
  9,594,307 / 4eb36793548711d4); test sprt/threat-any bfbc1c8 (the same tree with the switch on; bench 9,236,850 /
  0f723ee4c163a419). Jobs t56-any-stc and t56-any-ltc (ledger idea t56-any, try 1 of 2), design R ([0, 6] nElo,
  alpha 0.05, beta 0.20, futility look after 2 stages), fresh openings from stage 3.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| STC 8+0.08, design R [0, 6], cap 8 (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027), any-attack buckets against off | 43017939593 (stage 3), 43020606092 (4), 43023298002 (5), 43025985854 (6) | 6,400 (no time losses, no abnormal ends) | **+7.49 ± 4.89** | +13.04 ± 8.51 | [72, 706, 1502, 852, 68] | **H1 accepted** (LLR 3.19) after stage 6, 8:23 AM EST |
| LTC 40+0.4, design R [0, 6], cap 6 (Hash 64, 1,664 games a stage, Syzygy 3-4-5, UHO book, seed 20261027), the same pair | 43029851342 (stage 3), 43068666654 (4), 43081871545 (5) | 4,992 (no time losses, no abnormal ends) | **+8.07 ± 5.15** | +15.12 ± 9.64 | [20, 563, 1227, 653, 33] | **H1 accepted** (LLR 3.01) after stage 5, 3:13 PM EST |

- LTC by stage: stage 3 +4.18 ± 8.93; stage 4 alone +10.02, stage 5 alone +10.02 (Elo from each stage's own
  pentanomial counts; after stage 4 the total was +7.10 ± 6.33, LLR 1.70).
- **Stage 4's outage reruns:** runs 43042667430 (9:52 AM EST), 43048079900 (10:24 AM) and 43050144902 (10:37 AM)
  each ended in failure about two minutes after dispatch, in the build job's toolchain step, before any game was
  played (43042667430's log: "Could not resolve 'archive.ubuntu.com'", apt exit code 100; the other two logs were
  not readable through the API when this was recorded, HTTP 502, so their cause rests on the driver's report:
  UNVERIFIED). They are not results. The driver stopped after each and resumed stage 4 (resume of try 1); the
  fourth dispatch, 43068666654 (12:29 PM EST), played the stage.

The final stage's result block (t56-any-ltc, stage 5, run 43081871545):

```
    Shards: 48 (done); pairs 2496, games 4992 (4992 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 8.07 +/- 5.15, nElo: 15.12 +/- 9.64
    Ptnml(0-2): [20, 563, 1227, 653, 33]
    LLR: 3.01 (-1.56, 2.77) [0.00, 6.00] nElo: H1 accepted
```

- **Adopted (owner's pre-approval of 2026-11-11, 8:35 AM EST: "T56 any-attack: pre-approved for adoption if its LTC
  confirmation (item 64) passes"):** dc341d5's change ported onto phase-4 4470f24 alone (branch adopt/t56-any),
  `UseThreatBuckets` on, the switch kept until the Phase 4 re-validation. Bench 10,166,167 / d874b380155a2e8c
  (r8brft1; 9,942,973 / accfb975ccd6ccf5 with the switch off, equal to 4470f24's); with r8btd90 and cut-node off
  9,236,850 / 0f723ee4c163a419, equal to the tested commit bfbc1c8's tests/bench-r8btd90.ref. Speed not measured
  (bench/ab.py not run; UNVERIFIED).

### 2026-11-11 probcut-ltc2 (tier 2, T31, ProbCut d9-r5-m80): one LTC-only design R test on the tuned search (owner)

- **Owner, 2026-11-11 3:10 PM EST:** "ProbCut: I lift the no-retest rule for ONE LTC-only design R test on the current default (tuned search); record it as LTC try 1 of 2. Start it now in the free lane." The no-retest rule after
  probcut-d9r5m80-vs-base (above: H0 at STC on S512r2) is lifted for this
  one test only.
- Base `a40b1ff` (tier2/probcut-r2: phase-4 4470f24 with ProbCut ported
  behind `use_capture_probe`, off; bench 9,942,973 / accfb975ccd6ccf5),
  test `d145d40` (sprt/probcut-r2: the switch on; bench 9,903,350 /
  95f7f190cf02d64e). Design R, `--kind search`: [0, 6] nElo, alpha 0.05, beta
  0.20, 40+0.4, Hash 64, 1,664 games a stage, cap 6, futility look after
  2 stages. Ledger idea `t31-probcut`, LTC try 1 of 2. Fresh openings
  from stage 8 (openings 6,657 on; ProbCut's STC stages 0-7 played 1-6,400).
  Night queue lane A, item 18-probcut-ltc; the driver started at 3:55 PM
  EST. Both sides are the default at the owner's instruction (4470f24):
  T56 any-attack, adopted at 3:43 PM EST (db0bb31), is in neither.
- **Moved to db0bb31's engine (T56 on) as probcut-ltc2:** the coordinator moved it (about 4:00 PM EST) because T56 any-attack was adopted at 3:43 PM EST (db0bb31), so "the current default" of the owner's exception includes T56; the first version (probcut-ltc, base a40b1ff / test d145d40 on 4470f24) was stopped before any stage was dispatched, so no try was spent. Base `d47e479`
  (tier2/probcut-r3: phase-4 b4b048f, engine db0bb31, ProbCut off; bench 10,166,167 /
  d874b380155a2e8c), test `6d7ffb1` (sprt/probcut-r3: on; bench 9,639,207 / 07f7ae19b9250f38).
  Same idea t31-probcut (LTC try 1 of 2), same design, fresh openings from stage 8; lane A
  item 18 rewritten for it and released at 4:17 PM EST. The base and test above (a40b1ff,
  d145d40) were never dispatched.
- Stages 8-10 (runs by the ledger: `ledger.py runs probcut-ltc2`):

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| LTC 40+0.4, design R [0, 6], cap 6 (Hash 64, 1,664 games a stage, Syzygy 3-4-5, UHO book, seed 20261027), ProbCut d9-r5-m80 (6d7ffb1) against off (d47e479), r8brft1 on both sides | 43109070620 (stage 8), 43120086216 (9), 43129867831 (10) | 4,992 (no time losses, no abnormal ends) | **+9.40 ± 5.03** | +18.03 ± 9.64 | [24, 516, 1283, 647, 26] | **H1 accepted** (LLR 3.73) after stage 10, 9:08 PM EST |

- By stage: after stage 8 +3.76 ± 8.95 (LLR 0.33); after stage 9 +6.58 ± 6.21 (LLR 1.57).

The final stage's result block (probcut-ltc2, stage 10, run 43129867831):

```
    Shards: 48 (done); pairs 2496, games 4992 (4992 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 9.40 +/- 5.03, nElo: 18.03 +/- 9.64
    Ptnml(0-2): [24, 516, 1283, 647, 26]
    LLR: 3.73 (-1.56, 2.77) [0.00, 6.00] nElo: H1 accepted
```

- **Adopted (the owner's overnight pre-approval of 2026-11-11 for search items that pass their SPRT, and their
  LTC where required):** d47e479's change ported onto phase-4 a95e269 alone (branch adopt/probcut; the code lines
  equal d47e479's), `UseCaptureProbe` on, the switch kept until the Phase 4 re-validation. Bench 9,639,207 /
  07f7ae19b9250f38 (r8brft1), byte for byte the tested commit 6d7ffb1's tests/bench-r8brft1.ref, so the port equals
  the tested code; 10,166,167 / d874b380155a2e8c with the switch off, phase-4's. The constants 9 / 5 / 80 join the
  final retune's SPSA (class (b)). An LTC result only: ProbCut's one STC SPRT (on S512r2, above) ended H0.
  The adopting commit was rebased onto phase-4 d33a4db before the push (e005049; no engine file changed between
  a95e269 and d33a4db, so the bench checks stand). Speed (clang-release, Windows, the shared machine busy; A = phase-4 a95e269, B = the adopting commit e005049, r8brft1): bench/ab_search.py, 10 interleaved rounds, not pinned: median nps 2,043,662 against 2,034,450 (-0.5%), best 2,075,512 against 2,061,329 (-0.7%), under its 3.1% noise threshold, no significant difference; 12 further paired ABBA rounds: B/A nps 0.999, 95% interval 0.989 to 1.009 (t, 11 df). So no measurable nps price; the bench itself finishes in about 5% less time because it searches 5% fewer nodes.

### 2026-11-11/12 E1, the pass-best stop rule (bug review 2026-11-11; `use_pass_best_stop`): design R at STC, capped undecided, then a non-regression SPRT under the owner's rule: H1, adopted

- The bug review's E1 (docs/research/bug-review-2026-11-11.md; the owner's decision of 2026-11-11, about 6:20 PM
  EST): a search stopped mid-iteration played a move of the unfinished iteration only if its exact score beat the
  last finished iteration's. Base tier2/stop-rule `959cc32` (phase-4 e63101a's engine, db0bb31, with the rule
  built in behind `use_pass_best_stop`, off; r8brft1; bench 10,166,167 / d874b380155a2e8c); test sprt/stop-rule
  `d97e358` (the same tree with the switch on; bench unchanged, as bench's searches finish their iterations).
  Ledger idea `e1-stop-rule`. Night queue lane B item 66a (the STC), then the non-regression test.
- **The owner's rule (2026-11-11, about 10:08 PM EST, as relayed by the coordinator):** an H0 or undecided result
  with a non-negative estimate gets one non-regression test, and the change is adopted if it passes.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| stop-rule-stc: STC 8+0.08, design R [0, 6], alpha 0.05, beta 0.20, cap 8 (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027), the pass-best stop rule against off, openings from stage 0 | 43128978493 (stage 0), 43131239890 (1), 43134456304 (2), 43136610415 (3), 43138984593 (4), 43141183185 (5), 43143339430 (6), 43145414123 (7) | 12,800 (no time losses, no abnormal ends) | **+3.26 ± 3.35** | +5.86 ± 6.02 | [118, 1436, 3184, 1532, 130] | **capped undecided** (LLR 1.82, bounds −1.56, 2.77) after stage 7, 10:20 PM EST |
| stop-rule-nonreg: STC 8+0.08, non-regression [−3, 0] nElo, alpha = beta = 0.05 (LLR bounds ±2.94), the same pair, fresh openings from stage 8 (stages 8-20) | 43147600231 (stage 8), 43149673392 (9), 43151677185 (10), 43153770929 (11), 43155826893 (12), 43157820490 (13), 43159893398 (14), 43162227098 (15), 43164303623 (16), 43166409802 (17), 43168594883 (18), 43170827922 (19), 43173009038 (20) | 20,800 (no time losses, no abnormal ends) | **+2.41 ± 2.69** | +4.22 ± 4.72 | [215, 2413, 5033, 2491, 248] | **H1 accepted** (LLR 2.96) after stage 20, 2:26 AM EST 2026-11-12 |

- stop-rule-stc by stage: after stage 6 +3.16 ± 3.55 (LLR 1.52). stop-rule-nonreg by stage: after stage 17 +1.95 ±
  3.05 (LLR 1.97), stage 18 +2.74 ± 2.91 (2.77), stage 19 +2.55 ± 2.80 (2.86).
- **Tooling gap:** the non-regression run used the driver's legacy custom-bounds mode, which wrote no verdict file;
  the coordinator wrote `verdict` ("H1 accepted") from the driver log's last line (~/fork-data/sprt is
  outside the repository; the driver log is the record).
- **Adopted** under the owner's rule: commit e5a073f on phase-4 (the code of adopt/e1 25623ab, ported onto
  fa2ad80), the switch on; bench unchanged (9,639,207 / 07f7ae19b9250f38 with r8brft1). The gated tests (quiet
  history pruning, the drift tables, D8, D9, D13) were rebased onto the rule before they run ("later tests use the
  corrected engine"; branches with the suffix -e1).

### 2026-11-11/12 quiet history pruning (tier 2, T24; the engine survey's B13; idea 74): head-to-head of the threshold, then the design R SPRT of the pick against off (owner): H1, adopted

- The owner's order (2026-11-11, 3:10 PM EST): "Build quiet history pruning (B13) with a threshold chosen to actually
  fire (quick measurement first), then design R at STC." Candidates 2000, 1300 and 700 per ply by the firing-rate
  measurement (tools/tier2_measure/history_skip.json; DESIGN.md "Search constants"). Ledger idea `qhp`, try 1.
- **Head-to-head qhp-h2h** (lane B item 66; declared 5:38 PM EST, the tie rule: 2000, the most cautious, unless
  beaten by more than 0.5 e): a round robin of 2 stages of 1,600 games a pairing on the same openings, STC 8+0.08,
  test commits sprt/qhp-t56-2000 c06d62b, sprt/qhp-t56-1300 f6397e0 and sprt/qhp-t56-700 13d4d05 (children of
  tier2/qhp-t56 c84722b, phase-4 b2e083e's engine, r8brft1):

| Pairing | Runs | Games | Elo (95%) | nElo | Ptnml |
|---|---|---|---|---|---|
| 1300 against 2000 | 43113474240, 43115971883 | 3,200 | +2.71 ± 6.83 | +4.78 ± 12.04 | [32, 377, 755, 406, 30] |
| 700 against 2000 | 43118461639, 43120846151 | 3,200 | +8.14 ± 6.88 | +14.26 ± 12.04 | [30, 355, 766, 408, 41] |
| 700 against 1300 | 43123165165, 43125463839 | 3,200 | −2.50 ± 6.77 | −4.44 ± 12.04 | [33, 389, 776, 372, 30] |

- Least squares over the three pairings: 1300 − 2000 +9.42 ± 9.83 nElo, 700 − 2000 +9.62 ± 9.83 nElo; **700 picked**
  (7:30 PM EST; the tie rule not applied).
- **qhp-stc** (lane B item 67): base tier2/qhp-t56-e1 4cae4f4 (the skip behind `use_history_skip`, off, on adopt/e1
  25623ab = phase-4 26323e1 with E1; bench 10,166,167 / d874b380155a2e8c), test sprt/qhp-t56-700-e1 4701319 (the
  same tree with the switch on and `HistorySkipPerPly` 700; bench 9,886,698 / 8e7db959846159f4), r8brft1 on both
  sides; design R ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look after 2 stages), fresh openings from
  stage 2. The gated tests' rebase onto E1 (gate-e1) moved it from 13d4d05 to 4701319.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| STC 8+0.08, design R [0, 6], cap 8 (Hash 16, Syzygy 3-4-5, UHO book, seed 20261027), the history skip at 700 per ply against off | 43182618097 (stage 2), 43185180728 (3), 43187763748 (4), 43190519934 (5), 43193266205 (6) | 8,000 (no time losses, no abnormal ends) | **+6.04 ± 4.37** | +10.52 ± 7.61 | [83, 899, 1917, 998, 103] | **H1 accepted** (LLR 2.99) after stage 6, 4:57 AM EST 2026-11-12 |

- By stage: after stage 2 +0.43 ± 9.61 (LLR −0.18); stage 3 +6.52 ± 6.83 (1.35); stage 4 +7.02 ± 5.63 (2.21);
  stage 5 +6.35 ± 4.90 (2.56).

The final stage's result block (qhp-stc, stage 6, run 43193266205):

```
    Shards: 80 (done); pairs 4000, games 8000 (8000 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 6.04 +/- 4.37, nElo: 10.52 +/- 7.61
    Ptnml(0-2): [83, 899, 1917, 998, 103]
    LLR: 2.99 (-1.56, 2.77) [0.00, 6.00] nElo: H1 accepted
```

- **Adopted (the owner's overnight pre-approval of 2026-11-11 for search items that pass their SPRT; held for the
  CI fix before it is pushed):** 4cae4f4's change with 4701319's switch-on and 700 ported onto phase-4 e79cbf7
  alone (branch adopt/qhp; the code lines equal the tested diff, apart from the parameter table's realignment beside
  ProbCut's rows and merged comments), `UseHistorySkip` on, the switch kept until the Phase 4 re-validation. Bench
  9,263,568 / 881c326307a2ba8a (r8brft1). With the skip off 9,639,207 / 07f7ae19b9250f38, phase-4's; with the skip
  on and ProbCut off (the tested base had no ProbCut) 9,886,698 / 8e7db959846159f4, byte for byte 4701319's
  tests/bench-r8brft1.ref, so the port equals the tested code. `HistorySkipPerPly` 700 and `HistorySkipMaxDepth` 3
  join the final retune's SPSA (class (a)). Speed after the adopting commit 9d574d9 (built as 22ab719, before its rebases onto 32384e1 and 8cb60b8, which changed no engine code) (bench/ab_search.py, A =
  e79cbf7): median nps -2.5% (12 rounds) and -2.9% (16 rounds), best -1.2% and +0.2%, each under its noise
  threshold (3.7%, 6.3%): no significant difference; a small price is possible but not resolved (UNVERIFIED).

### 2026-11-12 the drift tables (tier 2: think tank R34, engine survey E4; idea 78): design R SPRTs of each table against off in the passive ranking's order (owner): threat H0 twice, minor H0 at 64 then H1 at 32, adopted

- The owner's order (2026-11-11): each table a design R STC SPRT against off at its share's natural value 64 and,
  only if that fails, one retry at 32 (try 2), in the passive ranking's order (threat, minor, major, pieces), no
  head-to-head (the shares are final-retune SPSA dimensions), a pass adopted (pre-approved). Night queue lane A
  items 19-corr-a to 19-corr-d so far, gated on E1 (gate-e1). Base tier2/corr-tables-e1 dd5db13 for every test
  (the four tables behind their switches, all off, on adopt/e1 25623ab = phase-4 26323e1 with E1, no ProbCut, no
  history skip; bench 10,166,167 / d874b380155a2e8c); each test commit is the base plus one switch on and, for
  a retry, its share at 32 (bench with r8brft1): threat 64 sprt/corr-threat-64-e1 c125860 (10,031,831 /
  9234d2e322dcfdcd), threat 32 sprt/corr-threat-32-e1 ef0e207 (9,333,289 / a358efa270cbccb7), minor 64
  sprt/corr-minor-64-e1 8f4c748 (9,450,299 / b09db81dc93c2d97), minor 32 sprt/corr-minor-32-e1 62b911f (9,633,320
  / 2467c017a6bb6ec4). STC 8+0.08, Hash 16, Syzygy 3-4-5, UHO book (seed 20261027), r8brft1 on both sides; design R
  ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look after 2 stages). Ledger ideas e4-threat-drift and
  e4-minor-drift. Data: ~/fork-data/sprt/corr-*.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| corr-threat-stc: the threat table at 64/64 against off (try 1), stages 0-1 | 43182768879 (stage 0), 43186154908 (1) | 3,200 (no time losses, no abnormal ends) | −10.53 ± 6.95 | −18.27 ± 12.04 | [38, 433, 753, 340, 36] | H0 accepted (LLR −3.38) after stage 1, 4:08 AM EST |
| corr-threat-retry: the threat table at 32/64 against off (try 2), stages 8-9 | 43188815709 (8), 43191589635 (9) | 3,200 | −7.38 ± 7.01 | −12.69 ± 12.04 | [41, 421, 736, 369, 33] | H0 accepted (LLR −2.50) after stage 9, 4:45 AM EST; both tries used |
| corr-minor-stc: the minor table at 64/64 against off (try 1), stage 0 | 43194342325 (0) | 1,600 | −18.26 ± 9.95 | −31.31 ± 17.02 | [32, 208, 386, 160, 14] | H0 accepted (LLR −2.73) after stage 0, 5:04 AM EST |
| **corr-minor-retry: the minor table at 32/64 against off (try 2), stages 8-13** | 43197094411 (8), 43199888833 (9), 43202617289 (10), 43205316293 (11), 43209264753 (12), 43211912908 (13) | 9,600 (no time losses, no abnormal ends) | **+5.57 ± 4.01** | +9.66 ± 6.95 | [105, 1081, 2295, 1193, 126] | **H1 accepted** (LLR 3.18) after stage 13, 7:04 AM EST 2026-11-12 |

- By stage (corr-minor-retry): after stage 8 +5.43 ± 9.77 (LLR 0.51); stage 9 +4.99 ± 6.89 (0.91); stage 10 +5.14
  ± 5.62 (1.43); stage 11 +4.13 ± 4.87 (1.34); stage 12 +4.26 ± 4.37 (1.75). corr-threat-stc after stage 0 −9.56
  ± 9.97 (−1.54); corr-threat-retry after stage 8 −0.22 ± 9.88 (−0.27).
- The offline diagnosis (2026-11-12, 6:20-7:05 AM EST, while the retry ran; not committed: 40 of the r8b-rft-stc
  games replayed at 200,000 nodes against 1,000,000-node labels, a scratch stats build): at share 64 a single
  table's term runs away (the applied term enters the subtree results it then learns from; minor 64: mean term
  44.9 cp, 3.0% of node visits at the 300 cp limit, search error +23.7 cp [+14.5, +34.2] against the labels;
  threat 64 +17.8 cp), which orders the two H0s at 64; at 32 the term stays bounded (minor 32: mean 17.5 cp,
  0.016% at the limit) and the search error improves (minor 32 −2.5 cp [−4.5, −0.8]; threat 32 −1.4 cp [−3.3,
  +0.4], so its H0 is not explained by accuracy: the threat key's two attack maps per node are its likely cost,
  UNVERIFIED, not measured).

The final stage's result block (corr-minor-retry, stage 13, run 43211912908):

```
    Shards: 96 (done); pairs 4800, games 9600 (9600 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 5.57 +/- 4.01, nElo: 9.66 +/- 6.95
    Ptnml(0-2): [105, 1081, 2295, 1193, 126]
    LLR: 3.18 (-1.56, 2.77) [0.00, 6.00] nElo: H1 accepted
```

- **Adopted (the owner's overnight pre-approval of 2026-11-11 for search items that pass their SPRT; the owner's
  table rule: if several tables pass alone, only the best is adopted and the next-best is tested on top of it;
  minor 32 is the first to pass):** dd5db13's drift tables (relative to 25623ab) with 62b911f's switch-on and share
  ported onto phase-4 75d53f0 alone (branch adopt/corr-minor; the code lines equal the tested diff apart from the
  parameter table's and the switch list's realignment beside ProbCut's and the history skip's rows and merged
  comments; tests added), `UseMinorDrift` on at `MinorDriftShare` 32, the piece, major and threat tables present
  and off, every switch kept until the Phase 4 re-validation. Bench 9,366,920 / 6d72bf03d34c65ec (r8brft1). With every table off
  9,263,568 / 881c326307a2ba8a, phase-4's; with the minor table on and ProbCut and the history skip off
  (the tested base had neither) 9,633,320 / 2467c017a6bb6ec4, byte for byte 62b911f's tests/bench-r8brft1.ref, so the port equals
  the tested code. `MinorDriftShare` 32 and `DriftLimit` 300 join the final retune's SPSA (class (a)). Speed: measured before the commit with bench/ab_search.py (clang-release, Windows, not pinned, the shared machine busy; A = phase-4 75d53f0, B = the port's build of this commit's engine code from the uncommitted tree on 75d53f0, r8brft1; identity checked on all 24 runs): 12 interleaved rounds, median nps -2.0%, best -3.4%, under the 4.9% noise threshold: no significant difference; a small price (the material keys kept at each make, the table read at each estimate) is possible but not resolved at this noise (UNVERIFIED). The bench searches 1.1% more nodes (9,366,920 against 9,263,568).

### 2026-11-12 the summed pair-table update (the engine survey's D8; idea 75): design R SPRT against off (owner): H1, adopted

- The owner's order (2026-11-11, 3:10 PM EST): "the survey's top cheap techniques: D8 (summed continuation update),
  D9 (failed-child prior-move bonus), D13 (direct-check ordering bonus), each design R at STC." D8 has no constant,
  so no head-to-head. Lane B item 68 (survey-d8-stc), gated on E1 (gate-e1). Base tier2/d8-pair-sum-e1 aa8dd0d (the
  update behind `use_pair_sum_update`, off, on adopt/e1 25623ab = phase-4 784b1b0's engine with E1, no ProbCut, no
  history skip, no drift table; bench 10,166,167 / d874b380155a2e8c); test sprt/d8-pair-sum-e1 dd132c9 (the switch
  on; 10,236,778 / 6338c0c3a941915a). STC 8+0.08, Hash 16, Syzygy 3-4-5, UHO book (seed 20261027), r8brft1 on both
  sides; design R ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look after 2 stages), from stage 0. Ledger
  idea `d8-pair-sum`, try 1. Data: ~/fork-data/sprt/survey-d8-stc.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| **survey-d8-stc: D8 on against off, stages 0-7** | 43196026493 (0), 43198826553 (1), 43201894676 (2), 43205178148 (3), 43207959370 (4), 43210641210 (5), 43213291041 (6), 43216014186 (7) | 12,800 (no time losses, no abnormal ends) | **+4.29 ± 3.46** | +7.47 ± 6.02 | [136, 1483, 3011, 1627, 143] | **H1 accepted** (LLR 2.84) after stage 7, 7:32 AM EST 2026-11-12 |

- By stage: after stage 0 +1.09 ± 10.03 (LLR −0.09); stage 1 +2.06 ± 7.03 (0.08); stage 2 +1.52 ± 5.74 (−0.09);
  stage 3 +1.90 ± 4.93 (0.09); stage 4 +1.65 ± 4.38 (−0.05); stage 5 +3.40 ± 4.00 (1.39); stage 6 +4.09 ± 3.70
  (2.30).

The final stage's result block (survey-d8-stc, stage 7, run 43216014186):

```
    Shards: 128 (done); pairs 6400, games 12800 (12800 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 4.29 +/- 3.46, nElo: 7.47 +/- 6.02
    Ptnml(0-2): [136, 1483, 3011, 1627, 143]
    LLR: 2.84 (-1.56, 2.77) [0.00, 6.00] nElo: H1 accepted
```

- **Adopted (the owner's overnight pre-approval of 2026-11-11 for search items that pass their SPRT; an STC-only
  item):** aa8dd0d's change with dd132c9's switch-on ported onto phase-4 2c294d3 alone (branch adopt/d8; the code
  lines equal the tested diff apart from the merge beside ProbCut's, the history skip's and the drift tables'
  switch entries and comments), `UsePairSumUpdate` on, the switch kept until the Phase 4 re-validation. Bench
  8,773,005 / 413d5ae2f1af08de (r8brft1). With D8 off 9,366,920 / 6d72bf03d34c65ec, phase-4's; with D8 on and ProbCut, the history skip and the
  minor drift table off (the tested base had none of them) 10,236,778 / 6338c0c3a941915a, byte for byte dd132c9's
  tests/bench-r8brft1.ref, so the port equals the tested code. No constant, so nothing joins the final retune's
  SPSA. Speed: bench/ab_search.py (clang-release, Windows, not pinned, the shared machine busy; A = phase-4 2c294d3, B = the port's build of this commit's engine code from the uncommitted tree on 2c294d3 plus the zugzwang tools, r8brft1; identity checked on all 24 runs): 12 interleaved rounds, median nps -0.5%, best -0.4%, under the 3.0% noise threshold: no significant difference (a price of that size is inside the noise, UNVERIFIED). The bench searches 6.3% fewer nodes (8,773,005 against 9,366,920).

### 2026-11-12 stacking check 1 (the owner's stacking safeguard): ProbCut + E1 + B13 together, design R at STC: H1, +6.30

- The owner's safeguard (2026-11-12, about 6:20 AM EST): "after every 3 adoptions, queue one confirmation SPRT of
  the new head vs the head before those 3 (design R, STC); report if the stack's combined gain is much below the
  sum." Group 1 = ProbCut (e005049; LTC +9.40 ± 5.03), E1 (e5a073f; STC +3.26 ± 3.35, then non-regression H1) and
  B13 quiet history pruning (9d574d9; STC +6.04 ± 4.37): sum +18.70. Lane A item 15a (stack-check-1-stc). OFF
  d33a4db (phase-4 just before ProbCut's adoption; bench r8brft1 10,166,167 / d874b380155a2e8c), TEST 75d53f0
  (phase-4 after B13; 9,263,568 / 881c326307a2ba8a). STC 8+0.08, Hash 16, Syzygy 3-4-5, UHO book (seed 20261027),
  r8brft1 on both sides; design R ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look after 2 stages), from
  stage 0. Ledger idea `stack-check-1`. Data: ~/fork-data/sprt/stack-check-1-stc.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| **stack-check-1-stc: 75d53f0 against d33a4db, stages 0-4** | 43232197558 (0), 43235690079 (1), 43239285016 (2), 43242535923 (3), 43245915650 (4) | 8,000 (no time losses, no abnormal ends) | **+6.30 ± 4.40** | +10.89 ± 7.61 | [74, 943, 1850, 1030, 103] | **H1** (LLR 3.14) |

- By stage: after stage 0 +8.47 ± 9.80 (LLR 0.93); stage 1 +4.34 ± 6.95 (0.72); stage 2 +2.90 ± 5.73 (0.47);
  stage 3 +5.48 ± 4.96 (2.04).
- **Reading (owner, 2026-11-12 10:45 AM EST; no follow-up):** against the raw sum (+18.70) the ratio is 0.34, but
  ProbCut's gain was measured at LTC (it lost at STC originally), so an STC check undercounts it. Without it the
  STC sum is about +9.3 (E1 +3.26, B13 +6.04) and the check's +6.30 is a ratio of about 0.68, within the usual
  range (the decision audit's 0.62-0.80).
- **Rule for future stacking checks (owner, same date):** compare against the sum of each item's gain at the
  check's own time control; if the batch includes LTC-only items, run the check at LTC or exclude those items
  from the comparison.

### 2026-11-12 the direct-check ordering bonus (the engine survey's D13; idea 77): design R SPRT against off (owner): H1, adopted

- The owner's order (2026-11-11, 3:10 PM EST): "the survey's top cheap techniques: D8 (summed continuation update),
  D9 (failed-child prior-move bonus), D13 (direct-check ordering bonus), each design R at STC." Re-planned (about
  7:45 PM EST): no head-to-head for a constant the final retune will tune; one SPRT at the natural value,
  `DirectCheckBonus` 5000, one retry at 2500 if it fails. Lane B item 70a (survey-d13-stc), gated on E1 (gate-e1).
  Base tier2/d13-check-order-e1 35209f0 (the bonus behind `use_check_order_bonus`, off, on adopt/e1 25623ab =
  phase-4 784b1b0's engine with E1, no ProbCut, no history skip, no drift table, no D8; bench 10,166,167 /
  d874b380155a2e8c); test sprt/d13-check-order-5000-e1 cc7b3bc (the switch on, 5000; 10,253,460 /
  8f28bb6e1d52fa6e). STC 8+0.08, Hash 16, Syzygy 3-4-5, UHO book (seed 20261027), r8brft1 on both sides; design R
  ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look after 2 stages), from stage 0. Ledger idea
  `d13-check-order`, try 1 (the retry, item 70b, not needed). Data: ~/fork-data/sprt/survey-d13-stc.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| **survey-d13-stc: D13 (5000) on against off, stages 0-5** | 43229400100 (0), 43232422086 (1), 43235937751 (2), 43240230646 (3), 43244234784 (4), 43247622236 (5) | 9,600 (no time losses, no abnormal ends) | **+5.50 ± 3.93** | +9.73 ± 6.95 | [93, 1082, 2306, 1218, 101] | **H1 accepted** (LLR 3.21) after stage 5, 10:44 AM EST 2026-11-12 |

- By stage: after stage 0 +6.30 ± 9.48 (LLR 0.66); stage 1 +7.38 ± 6.74 (1.62); stage 2 +6.08 ± 5.48 (1.89);
  stage 3 +5.75 ± 4.77 (2.31); stage 4 +4.30 ± 4.31 (1.83).

The final stage's result block (survey-d13-stc, stage 5, run 43247622236):

```
    Shards: 96 (done); pairs 4800, games 9600 (9600 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 5.50 +/- 3.93, nElo: 9.73 +/- 6.95
    Ptnml(0-2): [93, 1082, 2306, 1218, 101]
    LLR: 3.21 (-1.56, 2.77) [0.00, 6.00] nElo: H1 accepted
```

- **Adopted (the owner's overnight pre-approval of 2026-11-11 for search items that pass their SPRT; an STC-only
  item):** 35209f0's change with cc7b3bc's switch-on ported onto phase-4 85672d8 alone (branch adopt/d13; the
  code lines equal the tested diff apart from the merge beside ProbCut's, the history skip's, the drift tables'
  and D8's switch and parameter entries and comments), `UseCheckOrderBonus` on, `DirectCheckBonus` 5000, the
  switch kept until the Phase 4 re-validation. Bench 9,118,607 / 208629aa15e140a9 (r8brft1). With D13 off 8,773,005 / 413d5ae2f1af08de, phase-4's;
  with D13 on and ProbCut, the history skip, the minor drift table and D8 off (the tested base had none of them)
  10,253,460 / 8f28bb6e1d52fa6e, byte for byte cc7b3bc's tests/bench-r8brft1.ref, so the port equals the tested code.
  `DirectCheckBonus` joins the final retune's SPSA (class (a)). The history skip reads the ordering score
  without the bonus (each kept as tested; UNVERIFIED whether the skip should see it). Speed: bench/ab_search.py (clang-release, Windows, not pinned, the shared machine busy; A = phase-4 85672d8, B = the port's build of this commit's engine code from the uncommitted tree on 85672d8, r8brft1; identity checked on all 24 runs): 12 interleaved rounds, median nps +1.2%, best -2.9%, under the 6.0% noise threshold: no significant difference (a price of that size is inside the noise, UNVERIFIED). The bench searches 3.9% more nodes (9,118,607 against 8,773,005).

### 2026-11-12 the prior-move credit (the engine survey's D9; idea 76): design R SPRT at the natural value, then the retry (owner): H0, then a futility stop; rejected

- The owner's order (2026-11-11, 3:10 PM EST; as D8 above) and the re-plan (about 7:45 PM EST): no head-to-head
  for a constant the final retune will tune; one SPRT at the natural value, `PriorCreditQuarters` 4 (one cutoff
  bonus at the node's depth), one retry at 3 quarters if it fails; adopted if it passes (pre-approved). Lane B
  items 69a (survey-d9-stc) and 69b (survey-d9-retry), gated on E1 (gate-e1). Base tier2/d9-prior-credit-e1
  54543fe (the credit behind `use_prior_move_credit`, off, on adopt/e1 25623ab = phase-4 784b1b0's engine with
  E1, no ProbCut, no history skip, no drift table; bench 10,166,167 / d874b380155a2e8c); tests
  sprt/d9-prior-credit-4-e1 ab7e93f (4 quarters; 9,946,948 / 9feddb70e3ad7ea6) and sprt/d9-prior-credit-3-e1
  6c3c302 (3 quarters; 10,516,912 / 6f70b02f416d4523). STC 8+0.08, Hash 16, Syzygy 3-4-5, UHO book (seed
  20261027), r8brft1 on both sides; design R ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look after 2
  stages); try 1 from stage 0, try 2 on fresh openings from stage 1. Ledger idea `d9-prior-credit`, tries 1 and
  2. Data: ~/fork-data/sprt/survey-d9-stc and survey-d9-retry.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| survey-d9-stc: 4 quarters against off (try 1), stage 0 | 43218877995 (0) | 1,600 (no time losses, no abnormal ends) | −11.95 ± 9.62 | −21.17 ± 17.02 | [20, 204, 407, 149, 20] | H0 accepted (LLR −1.92) after stage 0, 7:51 AM EST |
| **survey-d9-retry: 3 quarters against off (try 2), stages 1-2** | 43221778723 (1), 43224719234 (2) | 3,200 (no time losses, no abnormal ends) | **−1.95 ± 6.94** | −3.39 ± 12.04 | [32, 408, 742, 382, 36] | **futility stop** (nElo −3.39 < 0 after 2 stages; LLR −1.02) after stage 2, 8:28 AM EST 2026-11-12; both tries used |

- By stage (survey-d9-retry): after stage 1 −7.38 ± 10.12 (LLR −1.23).

The final stage's result block (survey-d9-retry, stage 2, run 43224719234):

```
    Shards: 32 (done); pairs 1600, games 3200 (3200 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: -1.95 +/- 6.94, nElo: -3.39 +/- 12.04
    Ptnml(0-2): [32, 408, 742, 382, 36]
    LLR: -1.02 (-1.56, 2.77) [0.00, 6.00] nElo: continue
```

- **Rejected** (the two-try limit): `use_prior_move_credit` stays off on its branch, nothing reaches phase-4, and
  `PriorCreditQuarters` is not a final-retune dimension.

### 2026-11-12 fail-firm returns at reverse futility (the engine survey's B3, think tank R7; idea 87): design R SPRT at the natural value: H0; the retry not yet run

- The coordinator's overnight build list (2026-11-11: "B3 / R7 - fail-firm (blended) returns: RFP first, then
  stand-pat / fail-high. Shape: nat/retry") under the owner's rules of 2026-11-11 (the SPRT at the natural value,
  one retry at 1 quarter if it fails; a pass adopted, pre-approved). Lane A item 50a (survey-b3-rfp-stc), gated on
  E1 (gate-e1). Base tier2/b3-firm 9201f8f (the three sites behind `use_firm_rfp`, `use_firm_stand_pat` and
  `use_firm_fail_high`, all off, on phase-4 26323e1's engine: no E1, ProbCut, history skip or drift table; bench
  10,166,167 / d874b380155a2e8c); test sprt/b3-firm-rfp-2 08c6b97 (`use_firm_rfp` on, `FirmRfpQuarters` 2, the
  midpoint; 9,433,481 / a5bc641703fee6d7). STC 8+0.08, Hash 16, Syzygy 3-4-5, UHO book (seed 20261027), r8brft1 on
  both sides; design R ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look after 2 stages), from stage 0.
  Ledger idea `b3-firm-rfp`, try 1. Data: ~/fork-data/sprt/survey-b3-rfp-stc.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| **survey-b3-rfp-stc: reverse futility's firm return (2 quarters) against off (try 1), stages 0-4** | 43214602250 (0), 43217403466 (1), 43220281013 (2), 43223486903 (3), 43226480523 (4) | 8,000 (no time losses, no abnormal ends) | **−2.82 ± 4.49** | −4.79 ± 7.61 | [103, 1021, 1809, 972, 95] | **H0 accepted** (LLR −3.10) after stage 4, 8:39 AM EST 2026-11-12 |

- By stage: after stage 0 +6.73 ± 9.93 (LLR 0.68); stage 1 +1.95 ± 7.06 (0.05); stage 2 +0.14 ± 5.75 (−0.66);
  stage 3 −0.43 ± 5.03 (−1.19).

The final stage's result block (survey-b3-rfp-stc, stage 4, run 43226480523):

```
    Shards: 80 (done); pairs 4000, games 8000 (8000 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: -2.82 +/- 4.49, nElo: -4.79 +/- 7.61
    Ptnml(0-2): [103, 1021, 1809, 972, 95]
    LLR: -3.10 (-1.56, 2.77) [0.00, 6.00] nElo: H0 accepted
```

- Not adopted; `use_firm_rfp` stays off. The one retry, item 50b (survey-b3-rfp-retry: `FirmRfpQuarters` 1,
  sprt/b3-firm-rfp-1 3f94316, bench 10,012,393 / d49f21c9a90f5c38, against the same off on fresh openings from
  stage 5; try 2), had not run at 2:15 PM EST (no driver folder and no state file: lane A runs one item at a time
  in name order, and earlier items have held it since); it gets its own section. The stand-pat and fail-high
  sites (items 50d-50g) are queued after it.

### 2026-11-12 the singular margin re-measured (tier 2, T27; `SingularMarginPerPly` 22 against 6): design R SPRT at STC (owner): H0, 6 stays

- The owner's order (2026-11-12, about 7:20 AM EST): "Singular margin: queue one design R SPRT now,
  SingularMarginPerPly 22 (T27's rule on the current net) vs 6, on phase-4's head, STC then LTC on a pass
  (singular extensions gained most at LTC); pre-approved adoption on pass. Add the margin to the final retune's
  dimensions either way." Builder 3's C6 measurement (tier2/c6-singular-measure b71199d, r8brft1) found T27's rule
  1 now picks 22 cp per ply. Lane A item 15c (singular-margin-22-stc), gated on E1 (gate-e1). Base
  tier2/singular-margin-22 = phase-4 75d53f0 (`SingularMarginPerPly` 6; ProbCut, E1 and B13 on; bench 9,263,568 /
  881c326307a2ba8a); test sprt/singular-margin-22 7307f47 (22, range 2-44; 8,289,752 / d76ad0ceb27b306f). Value 22
  screened (Stockfish, Ethereal, Berserk, Weiss): no match, 2026-11-12. STC 8+0.08, Hash 16, Syzygy 3-4-5, UHO
  book (seed 20261027), r8brft1 on both sides; design R ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look
  after 2 stages), from stage 0. Ledger idea `singular-margin-22`, try 1. Data:
  ~/fork-data/sprt/singular-margin-22-stc.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| **singular-margin-22-stc: 22 against 6, stage 0** | 43249368697 (0) | 1,600 (no time losses, no abnormal ends) | **−26.76 ± 9.93** | −46.06 ± 17.02 | [28, 243, 366, 150, 13] | **H0 accepted** (LLR −3.90) after stage 0, 10:59 AM EST 2026-11-12 |

The final stage's result block (singular-margin-22-stc, stage 0, run 43249368697):

```
    Shards: 16 (done); pairs 800, games 1600 (1600 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: -26.76 +/- 9.93, nElo: -46.06 +/- 17.02
    Ptnml(0-2): [28, 243, 366, 150, 13]
    LLR: -3.90 (-1.56, 2.77) [0.00, 6.00] nElo: H0 accepted
```

- **6 stays.** The LTC (item 15d, singular-margin-22-ltc) was to run only on an STC H1, so it did not run (its
  log, 11:00 AM EST: "the STC singular-margin-22-stc ended 'H0 accepted': no LTC"). The margin stays a
  final-retune dimension (class (b)) as ordered; its range 2-16 is the owner's decision of about 2:10 PM EST
  (DESIGN.md decisions log; final-retune.md §3.2), and this result is the staleness audit's evidence for the rule
  that offline re-measurement rules set retune ranges only (docs/research/staleness-audit-2026-11-12.md).

### 2026-11-12 the piece drift tables (tier 2: think tank R34; idea 78): design R SPRT against off (owner): H1, +7.86; not adopted alone, the stack folds into idea 59's redesign

- The fourth of the drift tables' tests in the passive ranking's order, under the rules of the drift tables'
  section above (share 64 first, one retry at 32 only if it fails, a pass adopted, pre-approved; the owner's table
  rule: if several tables pass alone, only the best is adopted and the next-best is tested on top of it). Lane A
  item 19-corr-g (corr-piece-stc), gated on E1 (gate-e1). Base tier2/corr-tables-e1 dd5db13 (every table off;
  bench 10,166,167 / d874b380155a2e8c); test sprt/corr-piece-64-e1 768e5d7 (`UsePieceDrift` on, `PieceDriftShare`
  64; 9,811,399 / c893e56f8e99e97a). STC 8+0.08, Hash 16, Syzygy 3-4-5, UHO book (seed 20261027), r8brft1 on both
  sides; design R ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look after 2 stages), from stage 0. Ledger
  idea `r34-piece-drift`, try 1 (the retry at 32, item 19-corr-h, not needed). Data: ~/fork-data/sprt/corr-piece-stc.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| **corr-piece-stc: the piece tables at 64/64 against off (try 1), stages 0-4** | 43254091984 (0), 43257542504 (1), 43261689047 (2), 43268725090 (3), 43272352038 (4) | 8,000 (no time losses, no abnormal ends) | **+7.86 ± 4.35** | +13.77 ± 7.61 | [81, 882, 1904, 1041, 92] | **H1 accepted** (LLR 4.28) after stage 4, 1:01 PM EST 2026-11-12 |

- By stage: after stage 0 +4.78 ± 9.63 (LLR 0.43); stage 1 +5.21 ± 6.83 (0.98); stage 2 +6.23 ± 5.54 (1.92);
  stage 3 +5.10 ± 4.83 (1.91).

The final stage's result block (corr-piece-stc, stage 4, run 43272352038):

```
    Shards: 80 (done); pairs 4000, games 8000 (8000 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 7.86 +/- 4.35, nElo: 13.77 +/- 7.61
    Ptnml(0-2): [81, 882, 1904, 1041, 92]
    LLR: 4.28 (-1.56, 2.77) [0.00, 6.00] nElo: H1 accepted
```

- **Not adopted alone.** The minor table at 32 was already on phase-4 (adopted that morning), so under the table
  rule the piece tables were next to be tested on top of it, after an offline gate of the combination (the shares
  would sum to 96 of 64, the runaway the diagnosis had flagged). **The gate failed** (about 1:43 PM EST; the
  report ~/fork-jobs/night/reviews/corrstack-gate-2026-11-12.txt, outside the repo): pieces 64 on minor 32
  against the minor 32 head, search error +12.74 cp [+6.50, +19.11] and the minor table at the limit on 1.23% of
  visits; pieces 32 on minor 32, +2.99 cp [+1.19, +5.09] and 0.24%. With the depth-scaled share both stacks tie
  the head (pieces 64: +0.50 [−1.32, +2.45]; pieces 32: −0.06 [−1.27, +1.28]), the minor table at the limit on
  about 0.013% of visits.
- **The owner's decision (2026-11-12, about 2:05 PM EST):** no standalone stacking SPRT now; the stack folds into
  idea 59's follow-up redesign (item 1): the depth-scaled (and window-gated) variant of minor 32 + pieces 32 (the
  shares summing to 64) is tested against the minor 32 head when slots open. Rule: the offline gate is a safety
  check only (it blocks runaway: worse error, or more than 0.1% of visits at the limit); a stack that passes it
  goes to a design R SPRT, which decides adoption (DESIGN.md decisions log; ideas.md 78 and 59). `UsePieceDrift`
  stays off on phase-4.

### 2026-11-12 upcoming repetition (think tank R12, the engine survey's F7; idea 26): design R SPRT against off: H0; the non-regression fallback queued

- Lane B item 81a (f7-revisit-stc; built by builder 2): upcoming repetition as a correctness change under Fork's
  repetition rule as it stands (one earlier occurrence counts, before the root too; ideas.md idea 31). No
  constant to tune (the table size is a credited natural value). R12 itself suggested non-regression bounds; the
  coordinator's shape for this queue is design R [0, 6]. Base tier2/f7-revisit 718ad42 (`use_revisit_draw` off,
  on phase-4 26323e1's engine: no E1, ProbCut, history skip or drift table; bench 10,166,167 / d874b380155a2e8c);
  test sprt/f7-revisit 778cbf5 (the switch on; 9,524,186 / b47d75ab53d667ce). STC 8+0.08, Hash 16, Syzygy 3-4-5,
  UHO book (seed 20261027), r8brft1 on both sides; design R ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility
  look after 2 stages), from stage 0. Ledger idea `f7-revisit`, try 1. Data: ~/fork-data/sprt/f7-revisit-stc.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| **f7-revisit-stc: upcoming repetition on against off, stages 0-7** | 43256629088 (0), 43260045314 (1), 43265641314 (2), 43268982050 (3), 43272256853 (4), 43275457446 (5), 43278711403 (6), 43281990289 (7) | 12,800 (no time losses, no abnormal ends) | **−0.03 ± 3.48** | −0.05 ± 6.02 | [156, 1544, 2971, 1603, 126] | **H0 accepted** (LLR −1.94) after stage 7, 1:57 PM EST 2026-11-12 |

- By stage: after stage 0 +1.74 ± 10.09 (LLR −0.01); stage 1 +6.41 ± 6.88 (1.31); stage 2 +4.27 ± 5.66 (1.05);
  stage 3 +4.02 ± 4.96 (1.24); stage 4 +3.43 ± 4.38 (1.18); stage 5 +1.01 ± 4.01 (−0.59); stage 6 +0.93 ± 3.73
  (−0.78).

The final stage's result block (f7-revisit-stc, stage 7, run 43281990289):

```
    Shards: 128 (done); pairs 6400, games 12800 (12800 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: -0.03 +/- 3.48, nElo: -0.05 +/- 6.02
    Ptnml(0-2): [156, 1544, 2971, 1603, 126]
    LLR: -1.94 (-1.56, 2.77) [0.00, 6.00] nElo: H0 accepted
```

- Not adopted by this test; `use_revisit_draw` stays off. Item 81b (f7-revisit-nonreg; the owner's bug-fix
  fallback as used for E1, set up by the coordinator on 2026-11-11, about 10:55 PM EST): a result other than H1
  whose estimate is not clearly negative (above −2 Elo with its 95% interval reaching above 0, as here: −0.03,
  upper bound +3.45) gets a non-regression SPRT, nElo [−3, 0], alpha = beta = 0.05, STC, the same commits, 13
  stages on fresh openings from stage 8 (the driver's custom mode, not a try of the idea); it adopts nothing (the
  result goes to the coordinator and the owner). Queued in lane B; not started at 2:15 PM EST. It gets its own
  section.

### 2026-11-12 stacking check 2 (the owner's stacking safeguard): minor drift table + D8 + D13 together, design R at STC: H1, +7.86

- Group 2 of the owner's safeguard (2026-11-12, about 6:20 AM EST): the minor drift table (2c294d3; STC +5.57 ±
  4.01), D8 the summed pair-table update (3770a5f; STC +4.29 ± 3.46) and D13 the direct-check ordering bonus
  (96ebfec; STC +5.50 ± 3.93): STC sum +15.36. All three are STC results, so the check runs at STC (the owner's rule
  of 10:45 AM EST). Lane A item 15e (stack-check-2-stc). OFF ec4a4be (phase-4 just before the minor table's adoption;
  engine = 75d53f0's, bench r8brft1 9,263,568 / 881c326307a2ba8a), TEST 96ebfec (phase-4 after D13; 9,118,607 /
  208629aa15e140a9). STC 8+0.08, Hash 16, Syzygy 3-4-5, UHO book (seed 20261027), r8brft1 on both sides; design R
  ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look after 2 stages), from stage 0. Ledger idea
  `stack-check-2`. Data: ~/fork-data/sprt/stack-check-2-stc.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| **stack-check-2-stc: 96ebfec against ec4a4be, stages 0-4** | 43275555142 (0), 43278798485 (1), 43282055382 (2), 43285216067 (3), 43288433711 (4) | 8,000 (no time losses, no abnormal ends) | **+7.86 ± 4.33** | +13.83 ± 7.61 | [71, 899, 1902, 1034, 94] | **H1** (LLR 4.31) |

- By stage: after stage 0 +11.08 ± 9.51 (LLR 1.34); stage 1 +8.90 ± 6.83 (2.02); stage 2 +3.26 ± 5.58 (0.65);
  stage 3 +5.59 ± 4.83 (2.18).
- **Reading (owner, 2026-11-12 about 2:55 PM EST): accepted, no follow-up.** Against the STC sum (+15.36) the ratio
  is 0.51, below the decision audit's 0.62-0.80, and the sum lies above the 95% interval (upper bound +12.2). The
  overlap between D8 and D13 (both move ordering) is left to the factorial removal round, which tests every switch
  on the full head. **Planning factor (owner):** for overlapping small search adoptions, estimate the combined gain
  at about 0.5-0.6 times the sum of the separate SPRT claims. With stacking check 1 (+6.30), the session's six
  adoptions measure about +14 Elo at STC directly.

### 2026-11-12 the history skip's exemption for checking quiets (B13 with D13; idea 74; night queue items 71 and 71b): design R at STC, capped undecided, then a non-regression SPRT (owner): H1, adopted

- The owner's order (2026-11-12, about 12:50 PM EST): "exempt quiet checking moves from B13's history skip; test as
  one small design R SPRT, pre-approved on pass." Base tier2/skip-check-exempt `5cd267c` (phase-4 96ebfec's engine
  with the exemption built in behind `use_skip_check_exempt`, off; bench 9,118,607 / 208629aa15e140a9); test
  sprt/skip-check-exempt `cb66f9b` (the switch on; 9,443,408 / 6d421599a985f97c). STC 8+0.08, Hash 16, Syzygy
  3-4-5, UHO book (seed 20261027), r8brft1 on both sides. Ledger idea `skip-check-exempt`, try 1 of 2. Data:
  ~/fork-data/sprt/skip-check-exempt-stc and ~/fork-data/sprt/skip-check-exempt-nonreg.
- **The owner's order after the cap (about 4:50 PM EST):** "run one non-regression SPRT [-3, 0] ... adopt on a pass
  (pre-approved), drop if it fails."

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| skip-check-exempt-stc: STC 8+0.08, design R [0, 6], alpha 0.05, beta 0.20, cap 8, futility look after 2 stages, the exemption on against off, openings from stage 0 | 43285168897 (stage 0), 43288399518 (1), 43291592716 (2), 43294739213 (3), 43297872580 (4), 43300997867 (5), 43304142044 (6), 43307235492 (7) | 12,800 (no time losses, no abnormal ends) | **+2.80 ± 3.43** | +4.90 ± 6.02 | [136, 1494, 3030, 1611, 129] | **capped undecided** (LLR 1.21, bounds −1.56, 2.77) after stage 7, 4:27 PM EST |
| skip-check-exempt-nonreg: STC 8+0.08, non-regression [−3, 0] nElo, alpha = beta = 0.05 (LLR bounds ±2.94), the same pair, fresh openings from stage 8 (stages 8-20) | 43330489013 (stage 8), 43333017715 (9), 43335574422 (10), 43338054287 (11), 43340523805 (12), 43342950697 (13), 43345340105 (14), 43347608667 (15), 43349839281 (16), 43352110384 (17), 43354250164 (18), 43356312529 (19) | 19,200 (no time losses, no abnormal ends) | **+2.86 ± 2.77** | +5.08 ± 4.91 | [167, 2274, 4587, 2378, 194] | **H1 accepted** (LLR 3.14) after stage 19, 10:21 PM EST |

- skip-check-exempt-stc by stage: after stage 0 +1.95 ± 9.85 (LLR 0.03); stage 1 +2.28 ± 6.89 (0.16); stage 2
  +1.52 ± 5.69 (−0.09); stage 3 +3.15 ± 4.86 (0.80); stage 4 +2.91 ± 4.34 (0.84); stage 5 +2.71 ± 3.98 (0.83);
  stage 6 +3.10 ± 3.68 (1.35). skip-check-exempt-nonreg by stage: after stage 8 +4.99 ± 9.93 (0.40); stage 9
  +2.06 ± 6.94 (0.40); stage 10 +1.66 ± 5.62 (0.53); stage 11 +3.20 ± 4.83 (1.14); stage 12 +2.78 ± 4.32 (1.27);
  stage 13 +3.11 ± 3.92 (1.67); stage 14 +2.89 ± 3.63 (1.84); stage 15 +1.66 ± 3.40 (1.41); stage 16 +2.22 ± 3.21
  (1.94); stage 17 +2.08 ± 3.04 (2.06); stage 18 +2.57 ± 2.89 (2.65). Verdict files: "capped" and "H1 accepted".

The final stage's result block (skip-check-exempt-nonreg, stage 19, run 43356312529):

```
    Shards: 192 (done); pairs 9600, games 19200 (19200 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 2.86 +/- 2.77, nElo: 5.08 +/- 4.91
    Ptnml(0-2): [167, 2274, 4587, 2378, 194]
    LLR: 3.14 (-2.94, 2.94) [-3.00, 0.00] nElo: H1 accepted
```

- **Adopted (the owner's pre-approval of about 4:50 PM EST):** 5cd267c's change with cb66f9b's switch-on ported onto
  phase-4 016d952 alone (branch adopt/skip-check-exempt; the code lines equal the tested diff apart from two
  comments), `UseSkipCheckExempt` on, the switch kept until the Phase 4 re-validation. Bench 9,443,408 /
  6d421599a985f97c (r8brft1), byte for byte cb66f9b's tests/bench-r8brft1.ref; with the exemption off 9,118,607 /
  208629aa15e140a9, phase-4's, so the port equals the tested code. Every other reference re-pinned from its own
  build. Speed: bench/ab_search.py (clang-release, Windows, not pinned; A = phase-4 016d952, B = the port's build of this commit's engine code from the uncommitted tree on 016d952, r8brft1; identity checked on all 24 runs): 12 interleaved rounds, median nps -0.1%, best +0.2%, under the 3.0% noise threshold: no significant difference. The bench searches 3.6% more nodes (9,443,408 against 9,118,607).

### 2026-11-12 history ageing between searches (the engine survey's D17, think tank R16; idea 89; night queue item 52a): design R SPRT against off (owner's rule): H1, adopted

- The owner's rule (2026-11-11, about 7:45 PM EST): a constant the final retune will tune gets one design R SPRT
  at its natural value, adopted if it passes (pre-approved), one retry at a second value if it fails. The
  coordinator's overnight build list (2026-11-11), item 3: "D17 / R16 - history ageing between searches.
  nat/retry." Base tier2/d17-history-ageing `94999a9` (phase-4 a95e269's engine with the ageing built in behind
  `use_history_ageing`, off); test sprt/d17-history-ageing-2 `ee3a6c7` (the switch on, `HistoryKeepQuarters` 2);
  bench 10,166,167 / d874b380155a2e8c on both (each bench position starts from cleared histories). STC 8+0.08,
  Hash 16, Syzygy 3-4-5, UHO book (seed 20261027), r8brft1 on both sides; design R ([0, 6] nElo, alpha 0.05,
  beta 0.20, cap 8, futility look after 2 stages), from stage 0. Ledger idea `d17-history-ageing`, try 1 of 2
  (the retry, item 52b at 3 quarters, not needed). Gated behind state/gate-e1.done; started 9:15 PM EST. Data:
  ~/fork-data/sprt/survey-d17-stc.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| **survey-d17-stc: D17 (2 quarters) on against off, stages 0-6** | 43350847538 (0), 43353063962 (1), 43355155758 (2), 43357245468 (3), 43359342771 (4), 43361375711 (5), 43363398879 (6) | 11,200 (no time losses, no abnormal ends) | **+5.71 ± 3.77** | +9.74 ± 6.43 | [132, 1278, 2626, 1402, 162] | **H1 accepted** (LLR 3.75) after stage 6, 11:25 PM EST 2026-11-12 |

- By stage: after stage 0 +13.90 ± 9.82 (LLR 1.68); stage 1 +11.51 ± 6.91 (2.72); stage 2 +4.99 ± 5.71 (1.33);
  stage 3 +3.04 ± 4.98 (0.70); stage 4 +4.43 ± 4.45 (1.82); stage 5 +4.63 ± 4.08 (2.33). Verdict file: "H1
  accepted".

The final stage's result block (survey-d17-stc, stage 6, run 43363398879):

```
    Shards: 112 (done); pairs 5600, games 11200 (11200 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 5.71 +/- 3.77, nElo: 9.74 +/- 6.43
    Ptnml(0-2): [132, 1278, 2626, 1402, 162]
    LLR: 3.75 (-1.56, 2.77) [0.00, 6.00] nElo: H1 accepted
```

- **Adopted (the owner's pre-approval, rule of 2026-11-11; an STC-only item):** 94999a9's change (relative to a95e269) with ee3a6c7's switch-on onto phase-4 1b5a482 alone (branch adopt/d17): the tables' `age` (QuietHistory, PairHistory, TakeHistory), `Searcher::age_histories` and its call at each search's start in `deliberate` (after the TT's age advance), the switch `UseHistoryAgeing` (now on), `HistoryKeepQuarters` 2 in the parameter table (after `HistoryBonusCap`, range 0-4, step 1) and the tests; the code lines equal ee3a6c7's diff against a95e269 apart from the switch list's and the parameter table's merge beside the entries adopted since (ProbCut, E1, the history skip, the drift tables, D8, D13, the exemption; ee3a6c7's switch entry, which sat on `UseThreatBuckets`' line, has its own line) and the comments (the switch's comment, the default checks' comments); both tier-2 all-switches cases (test_pruning, test_pruning_review) list it. The same tables are aged as tested: the butterfly history (every threat bucket), reply, follow and take. The drift tables (eval_drift.hpp, added since the tested base) are not aged; whether they should be is not measured (UNVERIFIED; a follow-up for the owner). `UseHistoryAgeing` on, `HistoryKeepQuarters` 2, the switch kept until the Phase 4 re-validation. **Bench equivalence** (clang-release, Windows, r8brft1): with the ageing on, 9,443,408 / 6d421599a985f97c, phase-4 1b5a482's; with it off (a build with the switch's default flipped), the same 9,443,408 / 6d421599a985f97c. Each bench position starts from cleared histories, so ageing them changes nothing, as on the tested pair (both 10,166,167 / d874b380155a2e8c); the port's tests check that it changes a second search and that a first search after `clear_history()` equals the switch-off one. No bench reference changes. `HistoryKeepQuarters` joins the final retune's SPSA (class (a)). Speed: bench/ab_search.py (clang-release, Windows, not pinned, the shared machine busy; A = phase-4 1b5a482, B = the port's build of this commit's engine code from the uncommitted tree on 1b5a482, r8brft1; identity checked on all 24 runs, `--same-nodes`): 12 interleaved rounds, median nps +0.9%, best +2.5%, under the 3.0% noise threshold: no significant difference. The bench pays one ageing pass per position (each position is its own search, on cleared tables), so the pass's price is inside that measurement; the bench's nodes are unchanged.

### 2026-11-13 the improving flag in late move pruning (the engine survey's B9, think tank R17; idea 90; night queue item 53a): design R SPRT against off: H1, adopted

- The coordinator's overnight build list (2026-11-11), item 4: "B9 / R17 - improving flag as a measured mean
  shift in LMP, then LMR. R-STC." Base tier2/b9-improving `74e485a` (phase-4 a95e269's engine with both uses
  built in behind `use_improving_lmp` and `use_improving_lmr`, off; bench 10,166,167 / d874b380155a2e8c); test
  sprt/b9-improving-lmp `3273148` (`use_improving_lmp` on, `LmpImprovingEighths` 1; bench 9,874,402 /
  7065feb1fafd4e5f). STC 8+0.08, Hash 16, Syzygy 3-4-5, UHO book (seed 20261027), r8brft1 on both sides;
  design R ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look after 2 stages), from stage 0. Ledger idea
  `b9-improving-lmp`, try 1 of 2. Gated behind state/gate-e1.done; started 11:25 PM EST 2026-11-12. Data:
  ~/fork-data/sprt/survey-b9-lmp-stc.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| **survey-b9-lmp-stc: B9's LMP use (1 eighth) on against off, stages 0-4** | 43365482176 (0), 43367469073 (1), 43369441638 (2), 43371526398 (3), 43373575905 (4) | 8,000 (no time losses, no abnormal ends) | **+6.82 ± 4.37** | +11.87 ± 7.61 | [85, 890, 1907, 1019, 99] | **H1 accepted** (LLR 3.53) after stage 4, 12:59 AM EST 2026-11-13 |

- By stage: after stage 0 −0.87 ± 9.89 (LLR −0.36); stage 1 +0.11 ± 7.02 (−0.45); stage 2 +3.40 ± 5.68 (0.69);
  stage 3 +5.21 ± 4.89 (1.93). Verdict: "H1 accepted".

The final stage's result block (survey-b9-lmp-stc, stage 4, run 43373575905):

```
    Shards: 80 (done); pairs 4000, games 8000 (8000 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 6.82 +/- 4.37, nElo: 11.87 +/- 7.61
    Ptnml(0-2): [85, 890, 1907, 1019, 99]
    LLR: 3.53 (-1.56, 2.77) [0.00, 6.00] nElo: H1 accepted
```

- **Adopted (the owner's pre-approval; an STC-only item):** 74e485a's change (relative to a95e269) with 3273148's switch-on onto phase-4 254841c alone (branch adopt/b9-lmp): `PlyFrame::pruning_eval` (16 bits in the frame's padding; the 2,704-byte guard holds), the flag in `negamax` and the root frame's reset in `deliberate`, both uses (`UseImprovingLmp`, now on; `UseImprovingLmr`, off: its own SPRT, survey-b9-lmr-stc, night item 53d, runs against the same off 74e485a), `LmpImprovingEighths` 1 (after `LmpQuietAllowance`, range 0-4, step 1) and `LmrNotImprovingPlies` 1 (after `CutNodeLmrPlies`, range 0-3, step 1; unused while its switch is off) in the parameter table, and the tests. The code lines equal 3273148's diff against a95e269 apart from the switch list's and the parameter table's merge beside the entries adopted since (74e485a's two switch entries, which sat on `UseThreatBuckets`' line, have their own lines), the root reset's place beside the drift keys' set-up, and the comments; both tier-2 all-switches cases (test_pruning, test_pruning_review) list both uses, and the B9 case's switch-off side sets both uses off explicitly (the LMP use is on by default). The flag compares `prune_eval`, the variable RFP uses, as tested; since the minor drift table's adoption (2026-11-12) it includes that table's term, which the tested base did not have. R17's kill rule (two H0s among the LMP and LMR uses drop the flag) no longer applies to the LMP use. `UseImprovingLmp` on, `LmpImprovingEighths` 1, the switches kept until the Phase 4 re-validation. **Bench equivalence** (clang-release, Windows, r8brft1): with the LMP use off, 9,443,408 / 6d421599a985f97c, phase-4 254841c's; with it on and ProbCut, E1, the history skip, the minor drift table, D8, D13, the exemption and D17 off (the tested base had none of them), 9,874,402 / 7065feb1fafd4e5f, byte for byte 3273148's tests/bench-r8brft1.ref, so the port equals the tested code. **Bench changes (intended):** 9,430,886 / 647c5ee9a57cae18 with r8brft1 (0.1% fewer nodes than 9,443,408); every other reference re-pinned from its own build. `LmpImprovingEighths` joins the final retune's SPSA (class (a)). Speed: bench/ab_search.py (clang-release, Windows, 12 interleaved rounds, not pinned, identity checked on all 24 runs), A = 254841c, B = the port: median nps -2.1%, best -1.7%, under the 3.0% noise threshold, so no significant difference.

### 2026-11-13 the improving flag in LMR (the engine survey's B9, think tank R17; idea 90; night queue item 53d): design R SPRT against off: H1, adopted

- The coordinator's overnight build list (2026-11-11), item 4: "B9 / R17 - improving flag as a measured mean
  shift in LMP, then LMR. R-STC." Base tier2/b9-improving `74e485a` (phase-4 a95e269's engine with both uses
  built in behind `use_improving_lmp` and `use_improving_lmr`, off; bench 10,166,167 / d874b380155a2e8c); test
  sprt/b9-improving-lmr `d3b3930` (`use_improving_lmr` on, `LmrNotImprovingPlies` 1, the LMP use off; bench
  7,186,034 / debc7162447eb810). STC 8+0.08, Hash 16, Syzygy 3-4-5, UHO book (seed 20261027), r8brft1 on both
  sides; design R ([0, 6] nElo, alpha 0.05, beta 0.20, cap 8, futility look after 2 stages), from stage 0.
  Ledger idea `b9-improving-lmr`, try 1 of 2. Started 12:59 AM EST 2026-11-13 (after item 53a). Data:
  ~/fork-data/sprt/survey-b9-lmr-stc.

| Test | Run | Games | Elo (95%) | nElo | Ptnml | Result |
|---|---|---|---|---|---|---|
| **survey-b9-lmr-stc: B9's LMR use (1 ply) on against off, stages 0-1** | 43375821546 (0), 43377962512 (1) | 3,200 (no time losses, no abnormal ends) | **+12.71 ± 7.00** | +21.88 ± 12.04 | [35, 336, 750, 435, 44] | **H1 accepted** (LLR 3.00) after stage 1, 1:38 AM EST 2026-11-13 |

- By stage: after stage 0 +10.86 ± 10.02 (nElo +18.47 ± 17.02, LLR 1.23, Ptnml [21, 168, 373, 216, 22]).
  Verdict: "H1 accepted".

The final stage's result block (survey-b9-lmr-stc, stage 1, run 43377962512):

```
    Shards: 32 (done); pairs 1600, games 3200 (3200 finished, time losses 0, abnormal 0)
    Tables: 3-4-5 (both engines); book: UHO_Lichess_4852_v1.shuffled-20261027.epd, seed 20261027
    Elo: 12.71 +/- 7.00, nElo: 21.88 +/- 12.04
    Ptnml(0-2): [35, 336, 750, 435, 44]
    LLR: 3.00 (-1.56, 2.77) [0.00, 6.00] nElo: H1 accepted
```

- **Adopted (the owner's pre-approval; an STC-only item):** phase-4 17717a8 already carried both uses (B9's LMP adoption ported 74e485a's change, the LMR use off, `LmrNotImprovingPlies` 1 in the parameter table); this adoption (branch adopt/b9-lmr) only turns `UseImprovingLmr` on, the same one-line switch-on as d3b3930's against 74e485a, and updates test_pruning's B9 default checks (both uses on). Stats builds only: X2's LMR history probe now keeps B9's not-improving plies in its counterfactual reduction, as its comment says it keeps every other term of the real one (search_stats X2's check that the probe's changes need a firing failed without it with the use on; d3b3930 had the same omission; no release-build change). Tested without the LMP use (off on both sides), it is adopted on top of it under the one-at-a-time rule; the stacking check that follows covers the interaction. R17's kill rule (two H0s among the LMP and LMR uses drop the flag) no longer applies. `UseImprovingLmr` on, `LmrNotImprovingPlies` 1, the switches kept until the Phase 4 re-validation. **Bench equivalence** (clang-release, Windows, r8brft1): with the LMR use off, 9,430,886 / 647c5ee9a57cae18, phase-4 17717a8's; with it on and the LMP use, ProbCut, E1, the history skip, the minor drift table, D8, D13, the exemption and D17 off (the tested base had none of them), 7,186,034 / debc7162447eb810, byte for byte d3b3930's tests/bench-r8brft1.ref, so the port equals the tested code. **Bench changes (intended):** 6,238,381 / 8d4a17943d604c99 with r8brft1 (33.9% fewer nodes than 9,430,886); every other reference re-pinned from its own build. `LmrNotImprovingPlies` joins the final retune's SPSA (class (a)). Tests: clang-release (Windows): every non-slow test passes (34 of 34, eval and uci_timing skipped as usual, bench_parity included; the search suite re-run after the stats probe's fix, 27 of 27); clang-debug: ordering (17 cases), pruning (33) and search (27) pass; clang-stats: search_stats passes (11 cases) with the probe's fix (X2 failed without it, the check that the probe's changes need a firing). No new pin: the two cases that pin the LMP use off (test_search's null-move zugzwang-guard case and search_stats X2's zero-band carry-over comparison) pass with the LMR use on, so neither pins it. Speed: bench/ab_search.py (clang-release, Windows, 12 interleaved rounds, not pinned, identity checked on all 24 runs), A = 17717a8, B = the port: median nps +0.5%, best +0.3%, under the 3.0% noise threshold, so no significant difference.
