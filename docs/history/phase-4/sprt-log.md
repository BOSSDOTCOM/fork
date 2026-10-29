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
- Stage 1: run 40825124514 (paused for the B0 SPRT between stages 0 and 1).
