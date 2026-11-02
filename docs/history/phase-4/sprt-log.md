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

