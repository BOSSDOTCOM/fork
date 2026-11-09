# Phase 4 SPRT log

Every SPRT of Phase 4, in the order run, rejections included (DESIGN.md
§5.2, "Testing setup", and §5.3). Runs on the GitHub shards
(`.github/workflows/sprt.yml`, 16 shards, stages of 1,600 games merged with
`tools/cloud/sprt_merge.py`): fastchess 1.8.2-alpha, normalized Elo,
pentanomial statistics, alpha = beta = 0.05, game pairs with colours
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
  misjudged against S512+PP's 351. The full non-slow suite passes on it.
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
