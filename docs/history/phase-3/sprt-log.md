# Phase 3 SPRT log

Every SPRT of Phase 3, in the order run, rejections included (DESIGN.md
§5.2, "Testing setup"). Entries are appended by `tools/sprt.sh`: fastchess
alpha 1.8.2, normalized Elo, pentanomial statistics, alpha = beta = 0.05,
game pairs with colours reversed, UHO_Lichess_4852_v1.epd openings (test
openings only), one thread per engine, run in WSL on the owner's Ryzen 7
7600X3D (shared machine; concurrency 5 until the SEE test, 10 from the PVS
test on: 1,478 games per hour with 0 time losses over its first 505 games,
against about 790 at 5). Bounds: [0, 5] until Milestone B,
[0, 3] for tier 2, [-3, 0] for non-regression (owner, 2026-10-24).
STC 8+0.08 s with 16 MB Hash, LTC 40+0.4 s with 64 MB.

### 20261025T022718Z ma-search-vs-placeholder

- base `2486428` (phase-2, the Phase 2 placeholder), test `2beb9e3` (deliverables 1-4), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 5. Result: **H1 accepted** (a sanity check: the search against the placeholder).
```
Elo: 1107.46 +/- nan, nElo: 5957.31 +/- 39.71
Games: 294, Wins: 293, Losses: 0, Draws: 1, Points: 293.5 (99.83 %)
Ptnml(0-2): [0, 0, 0, 1, 146], WL/DD Ratio: -nan
LLR: 2.96 (100.4%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
```

### 20261025T030356Z ma-search-vs-placeholder

- base `2486428` (phase-2), test `bea68ed` (bea68ed), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 5
```
Elo: 1107.46 +/- nan, nElo: 5957.31 +/- 39.71
Games: 294, Wins: 293, Losses: 0, Draws: 1, Points: 293.5 (99.83 %)
Ptnml(0-2): [0, 0, 0, 1, 146], WL/DD Ratio: -nan
LLR: 2.96 (100.4%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
```

### 20261025T030929Z ma-UseQuiesce

- base `bea68ed` (bea68ed), test `bea68ed` (bea68ed), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 5, tuning builds, base opts option.UseQuiesce=false
```
Elo: 281.30 +/- 45.45, nElo: 334.44 +/- 35.59
Games: 366, Wins: 283, Losses: 38, Draws: 45, Points: 305.5 (83.47 %)
Ptnml(0-2): [2, 9, 29, 28, 115], WL/DD Ratio: 6.25
LLR: 2.96 (100.5%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
```

### 20261025T033828Z ma-UseTT

- base `bea68ed` (bea68ed), test `bea68ed` (bea68ed), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 5, tuning builds, base opts option.UseTT=false
```
Elo: 173.76 +/- 29.28, nElo: 224.77 +/- 32.10
Games: 450, Wins: 283, Losses: 75, Draws: 92, Points: 329.0 (73.11 %)
Ptnml(0-2): [4, 13, 61, 65, 82], WL/DD Ratio: 7.71
LLR: 2.95 (100.2%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
```

### 20261025T041437Z ma-UseSeeQuiesce

- base `bea68ed` (bea68ed, option.UseSeeQuiesce=false), test `bea68ed` (default), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 5, tuning builds (started before the game cap existed).
- Verdict: **INCONCLUSIVE (stopped by the owner, 2026-10-25)** after 5,836 finished games. The last report (5,798 games) shows +9.47 ± 7.28 Elo, nElo +11.64 ± 8.94, LLR 2.19 of 2.94 (the owner's figure, +9.3 ± 7.4 at about 5,800 games, is the 5,600-game report): the 95% interval lies above zero. **Kept on.** Flagged for the end-of-Phase-3 removal round (DESIGN.md §5.2, Quality control 6). The stop killed fastchess before its final report, and the script of the time then exited without logging; this entry is written by hand from the fastchess log, and tools/sprt.sh now logs a stopped test as inconclusive.
```
Elo: 9.47 +/- 7.28, nElo: 11.64 +/- 8.94
Games: 5798, Wins: 2294, Losses: 2136, Draws: 1368, Points: 2978.0 (51.36 %)
Ptnml(0-2): [315, 508, 1169, 518, 389], WL/DD Ratio: 5.84
LLR: 2.19 (74.5%) (-2.94, 2.94) [0.00, 5.00]
```

### 20261025T120632Z ma-UsePvs

- base `bea68ed` (bea68ed), test `bea68ed` (bea68ed), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 10, tuning builds, base opts option.UsePvs=false
- Verdict: **H1 was accepted**; cap 20000 games.
```
Elo: 109.83 +/- 23.96, nElo: 132.64 +/- 27.04
Games: 634, Wins: 353, Losses: 159, Draws: 122, Points: 414.0 (65.30 %)
Ptnml(0-2): [17, 24, 115, 70, 91], WL/DD Ratio: 7.21
LLR: 2.96 (100.5%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
```

### 20261025T123220Z ma-UseAspiration

- base `bea68ed` (bea68ed, option.UseAspiration=false), test `bea68ed` (default), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 10, tuning builds, cap 20000 games.
- Verdict: **INCONCLUSIVE (stopped by the owner, 2026-10-25)** after 3,306 finished games. The last report (3,200 games) shows +3.91 ± 7.60 Elo, nElo +6.19 ± 12.04, LLR 0.49 of 2.94: the 95% interval includes zero. **Kept on.** Added to the end-of-Phase-3 removal round (DESIGN.md §5.2, Quality control 6). Entry written by hand: stopping the test chain also ended this test's script before it could log.
```
Elo: 3.91 +/- 7.60, nElo: 6.19 +/- 12.04
Games: 3200, Wins: 1252, Losses: 1216, Draws: 732, Points: 1618.0 (50.56 %)
Ptnml(0-2): [103, 195, 981, 205, 116], WL/DD Ratio: 4.91
LLR: 0.49 (16.6%) (-2.94, 2.94) [0.00, 5.00]
```

### Mate distance pruning (ma-UseMateDistance): not run

- Planned on non-regression bounds [-3, 0]; **not run at Milestone A**
  (owner, 2026-10-25). Kept on (it is exact: it changes only how fast mates
  are found, which the mate tests check). Added to the end-of-Phase-3
  removal round.

### 20261025T173305Z adj-check-UsePvs

- base `bea68ed` (bea68ed), test `bea68ed` (bea68ed), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40, tuning builds, base opts option.UsePvs=false
- Verdict: **H1 was accepted**; cap 20000 games.
```
Elo: 106.94 +/- 22.84, nElo: 134.39 +/- 26.92
Games: 640, Wins: 347, Losses: 156, Draws: 137, Points: 415.5 (64.92 %)
Ptnml(0-2): [17, 21, 116, 86, 80], WL/DD Ratio: 6.73
LLR: 2.96 (100.7%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
```

### 20261025T200719Z mb-d5-ordering

- base `52ac1b1` (52ac1b1), test `4fac691` (4fac691), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40
- Verdict: **H1 was accepted**; cap 20000 games.
```
Elo: 150.00 +/- 27.07, nElo: 196.65 +/- 31.34
Games: 472, Wins: 283, Losses: 91, Draws: 98, Points: 332.0 (70.34 %)
Ptnml(0-2): [2, 19, 79, 57, 79], WL/DD Ratio: 6.18
LLR: 2.95 (100.1%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
```

### 20261025T202717Z mb-UseHistory

- base `4fac691` (4fac691), test `4fac691` (4fac691), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40, tuning builds, base opts option.UseHistory=false
- Verdict: **STOPPED, superseded** (owner, 2026-10-25): halted after about 79 games, before any report, when the owner paused the queue to replace the history, LMP and null-move constants found by the originality check. Re-run on the new values (below).

### 20261025T212942Z mb-UseHistory

- base `69e830a` (69e830a), test `69e830a` (69e830a), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40, tuning builds, base opts option.UseHistory=false
- Verdict: **H1 was accepted**; cap 20000 games.
```
Elo: 418.92 +/- 60.19, nElo: 624.51 +/- 37.95
Games: 322, Wins: 283, Losses: 14, Draws: 25, Points: 295.5 (91.77 %)
Ptnml(0-2): [0, 1, 14, 22, 124], WL/DD Ratio: 13.00
LLR: 2.96 (100.6%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
```

### 20261025T214112Z mb-tier1

- base `69e830a` (69e830a), test `69e830a` (69e830a), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40, tuning builds, base opts option.UseRfp=false option.UseNmp=false option.UseLmr=false option.UseLmp=false option.UseFutility=false option.UseSeePrune=false
- Verdict: **H1 was accepted**; cap 20000 games.
```
Elo: 439.21 +/- 61.04, nElo: 698.69 +/- 38.19
Games: 318, Wins: 279, Losses: 8, Draws: 31, Points: 294.5 (92.61 %)
Ptnml(0-2): [0, 1, 9, 26, 123], WL/DD Ratio: 3.50
LLR: 2.96 (100.4%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
```

### 20261025T215305Z mb-UseSeePrune

- base `69e830a` (69e830a), test `69e830a` (69e830a), bounds [0, 5] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40, tuning builds, base opts option.UseSeePrune=false
- Verdict: **H1 was accepted**; cap 20000 games.
```
Elo: 21.16 +/- 10.08, nElo: 25.99 +/- 12.35
Games: 3042, Wins: 1166, Losses: 981, Draws: 895, Points: 1613.5 (53.04 %)
Ptnml(0-2): [142, 284, 556, 325, 214], WL/DD Ratio: 2.89
LLR: 2.95 (100.1%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
```
