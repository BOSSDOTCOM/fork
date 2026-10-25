# Phase 3 SPRT log

Every SPRT of Phase 3, in the order run, rejections included (DESIGN.md
§5.2, "Testing setup"). Entries are appended by `tools/sprt.sh`: fastchess
alpha 1.8.2, normalized Elo, pentanomial statistics, alpha = beta = 0.05,
game pairs with colours reversed, UHO_Lichess_4852_v1.epd openings (test
openings only), one thread per engine, run in WSL on the owner's Ryzen 7
7600X3D (shared machine, concurrency 5). Bounds: [0, 5] until Milestone B,
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
