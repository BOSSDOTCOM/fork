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
