# Phase 3 SPRT log

Commit hashes from before the 2026-10-27 path rewrite (cited in some entries and commit messages) map to the current ones in [path-rewrite-2026-10-27.md](path-rewrite-2026-10-27.md).

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

### 20261026T124341Z mb-tier1-ltc

- base `69e830a` (69e830a), test `69e830a` (69e830a), bounds [0, 5] nElo, 40+0.4, Hash 64 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40, tuning builds, base opts option.UseRfp=false option.UseNmp=false option.UseLmr=false option.UseLmp=false option.UseFutility=false option.UseSeePrune=false
- Verdict: **H1 was accepted**; cap 10000 games.
```
Elo: 555.67 +/- 80.38, nElo: 1093.50 +/- 38.93
Games: 306, Wins: 284, Losses: 2, Draws: 20, Points: 294.0 (96.08 %)
Ptnml(0-2): [0, 0, 3, 18, 132], WL/DD Ratio: 2.00
LLR: 2.96 (100.5%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
```

### 20261026T135724Z ttblend-ltc

- base `f140963` (f140963), test `f140963` (f140963), bounds [0, 3] nElo, 40+0.4, Hash 64 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40, tuning builds, test opts option.UseTtAgeBlend=true
- Verdict: **INCONCLUSIVE (stopped by the owner, 2026-10-26)** after 1,561 finished games; the last report (1,400 games): blended +5.7 ± 13.8 Elo (nElo +7.5 ± 18.2), LLR 0.21 of 2.94. The lexicographic policy stays the default; the blended one stays behind its switch (`UseTtAgeBlend`), to be re-tested after Phase 4's network and under Phase 6 conditions (ideas.md idea 24). No time losses, crashes or illegal moves.
```
Elo: 5.71 +/- 13.79, nElo: 7.54 +/- 18.20
Games: 1400, Wins: 476, Losses: 453, Draws: 471, Points: 711.5 (50.82 %)
Ptnml(0-2): [64, 144, 251, 187, 54], WL/DD Ratio: 2.59
LLR: 0.21 (7.1%) (-2.94, 2.94) [0.00, 3.00]
```

### 20261026T210311Z rv-failhigh

- base `077db27` (077db27), test `f0a9caf` (f0a9caf), bounds [-3, 0] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40
- Verdict: **REJECTED (stopped by the owner, 2026-10-26)** after 2,143 finished games. The last report (2,000 games): the root fail-high fix (first external review, claim (a)) at -14.6 ± 10.8 Elo (nElo -20.7 ± 15.2), its 95% interval entirely below zero; LLR -0.95 of -2.94. The behaviour is reverted: when the search stops with a root fail high still awaiting its re-search, the previous iteration's move is kept (the bookkeeping stays; ideas.md idea 29). Rejected on STC alone: the owner's recorded exception to the LTC-retest rule (2026-10-27; DESIGN.md §5.2), with idea 29's measurement plan reopening the question. No time losses, crashes or illegal moves.
```
Elo: -14.60 +/- 10.75, nElo: -20.71 +/- 15.23
Games: 2000, Wins: 647, Losses: 731, Draws: 622, Points: 958.0 (47.90 %)
Ptnml(0-2): [88, 217, 447, 187, 61], WL/DD Ratio: 3.10
LLR: -0.95 (-32.3%) (-2.94, 2.94) [-3.00, 0.00]
```

### Note (owner, 2026-10-26): concurrency 8

From the futile-node filter's SPRT on, the remaining tests of the external
reviews' queue run at concurrency 8 (was 10), so development builds, tests
and checks can run beside the games at low priority.

### 20261026T223103Z rv-futile

- base `6ae4128` (6ae4128), test `3a8a1b6` (3a8a1b6), bounds [-3, 0] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 8, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40
- Verdict: **ACCEPTED (stopped by the owner, 2026-10-26)** after 2,046 finished games. The last report (2,000 games): the futile-node quiet filter (first external review, claim (d)) at +11.5 ± 11.9 Elo, on non-regression bounds [-3, 0]: the 95% interval's lower bound (-0.4) is above -3. The change is kept. No time losses, crashes or illegal moves.
```
Elo: 11.47 +/- 11.90, nElo: 14.69 +/- 15.23
Games: 2000, Wins: 734, Losses: 668, Draws: 598, Points: 1033.0 (51.65 %)
Ptnml(0-2): [92, 186, 402, 204, 116], WL/DD Ratio: 2.87
LLR: 0.80 (27.3%) (-2.94, 2.94) [-3.00, 0.00]
```

### 20261027T001443Z rv-ttrefine

- base `738daff` (738daff), test `738daff` (738daff), bounds [0, 3] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 8, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40, tuning builds, test opts option.UseTtEvalRefine=true
- Verdict: **PROVISIONAL (stopped by the owner, 2026-10-26), NEEDS VERIFICATION.** Gainer bounds [0, 3], not decided: +17.0 ± 19.9 Elo at 800 games when the owner stopped it; the last report before it ended (1,000 games, 1,027 finished) is below, +14.6 ± 17.8, LLR 0.40 of 2.94. The TT-refined pruning eval (second review, claim (d); KB T50) is turned on by default and keeps its switch `UseTtEvalRefine`; the end-of-Phase-3 removal round verifies it at STC and at LTC 40+0.4 (DESIGN.md §5.2, Quality control 6). No time losses, crashes or illegal moves.
```
Elo: 14.60 +/- 17.76, nElo: 17.74 +/- 21.53
Games: 1000, Wins: 374, Losses: 332, Draws: 294, Points: 521.0 (52.10 %)
Ptnml(0-2): [50, 102, 171, 110, 67], WL/DD Ratio: 3.17
LLR: 0.40 (13.7%) (-2.94, 2.94) [0.00, 3.00]
```

### Note (owner, 2026-10-26): keep-exact's cap and development priority

The keep-exact SPRT (`rv-keepexact`, below) runs at concurrency 8 on top of
the TT-refined eval's new default (008b67f with `UseTtEvalRefine=true` on
both sides), capped at about 5,000 games or 4 hours from its start
(01:08:55 UTC, so 05:08:55 UTC), whichever comes first. Undecided at the
cap, it is INCONCLUSIVE: keep-exact stays off by default and goes into the
end-of-Phase-3 removal round. Development now runs at normal priority beside
the games; after any time loss it drops back to low priority until the SPRT
ends. Once the queue is empty, SPRTs return to concurrency 10.

### 20261027T010855Z rv-keepexact

- base `008b67f` (008b67f), test `008b67f` (008b67f), bounds [-3, 0] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 8, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40, tuning builds, base opts option.UseTtEvalRefine=true, test opts option.UseTtEvalRefine=true option.UseTtKeepExact=true
- Verdict: **INCONCLUSIVE at the owner's cap** (about 5,000 games or 4 hours; stopped by its guard at 05:09:33 UTC after 4,845 finished games): -0.6 +/- 7.5 Elo at the last report (4,800 games), LLR 0.09 of 2.94. Keeping exact TT entries (the second review's claim (e)) stays **off by default** and goes into the end-of-Phase-3 removal round (DESIGN.md §5.2, Quality control 6). No time losses, crashes or illegal moves.
```
Elo: -0.58 +/- 7.49, nElo: -0.76 +/- 9.83
Games: 4800, Wins: 1670, Losses: 1678, Draws: 1452, Points: 2396.0 (49.92 %)
Ptnml(0-2): [224, 502, 956, 494, 224], WL/DD Ratio: 3.19
LLR: 0.09 (3.0%) (-2.94, 2.94) [-3.00, 0.00]
```

### 20261027T051243Z mc-tables

- base `b7ab410` (b7ab41033be35bd5b098cd8af37d9a133fa8ad31), test `b7ab410` (b7ab41033be35bd5b098cd8af37d9a133fa8ad31), bounds [0, 3] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40, test opts option.SyzygyPath=~/fork-tools/syzygy/3-4-5
- Verdict: **ACCEPTED (owner's decision, 2026-10-27)**: Syzygy probing (deliverable 7; the test side with the 3-4-5 tables, the base without) at **+17.5 +/- 7.2 Elo** at the 5,000-game cap, LLR 2.72 of 2.94, the 95% interval entirely above zero. Probing stays on. No time losses, crashes or illegal moves.
```
Elo: 17.46 +/- 7.18, nElo: 23.45 +/- 9.63
Games: 5000, Wins: 1846, Losses: 1595, Draws: 1559, Points: 2625.5 (52.51 %)
Ptnml(0-2): [179, 464, 1053, 535, 269], WL/DD Ratio: 2.76
LLR: 2.72 (92.3%) (-2.94, 2.94) [0.00, 3.00]
```

### 20261027T083215Z mc-time

- base `23f1b10` (23f1b10), test `4ec034d` (4ec034d), bounds [-3, 0] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40
- Verdict: **INCONCLUSIVE at the 5,000-game cap**: deliverable 8 (23f1b10 -> 4ec034d: the increment fix, the two-overhead reserve floor, the iteration rule) at -4.9 +/- 7.1 Elo, LLR -0.65 of -2.94. It leaned to about -10 Elo midway (3,300 games), which led the owner to split deliverable 8 (2026-10-27): the floor binds near the clock where 8+0.08 games settle (about 0.4-0.6 s left), and the test side spent 3-7% less time per move from move 41 on (PGN analysis). The variants are measured separately below (d8-*). No time losses, crashes or illegal moves.
```
Elo: -4.93 +/- 7.09, nElo: -6.71 +/- 9.63
Games: 5000, Wins: 1696, Losses: 1767, Draws: 1537, Points: 2464.5 (49.29 %)
Ptnml(0-2): [227, 508, 1075, 489, 201], WL/DD Ratio: 2.98
LLR: -0.65 (-22.0%) (-2.94, 2.94) [-3.00, 0.00]
```

### Note (owner, 2026-10-27): deliverable 8 split, variant chosen

Deliverable 8 was split (owner): (a) the increment fix alone, (b) the
low-clock reserve redesigned to be adaptive, as variant B1 "deficit"
(reserve max(clock/10, overhead - increment)) or B2 "danger zone" (one more
Move Overhead only when less than two overheads plus an increment is
available), and (c) the iteration rule. Stress tests, 2,000 games at 2+0.02
under full load each: (a) alone **3 time losses** (each with the clock down
to about one overhead), B1 0, B2 0; the full original deliverable 8 0.
**The owner chose B2 over B1 without a separate SPRT**: both have zero time
losses, and B2 acts only at a low clock while B1 reserves time on every
move whose increment is below the overhead. One SPRT follows: (a) + B2 +
(c) against (a) (the pre-deliverable-8 time management on the current code:
the increment fix gives the same numbers at an 80 ms increment), 8+0.08,
non-regression bounds [-3, 0], concurrency 10, capped at 5,000 games. If it
passes, it is merged and the Milestone C gauntlet starts, with the 40+0.4
check after; if it fails, B2 and (c) are tested separately.

### 20261027T165757Z d8-final

- base `d51462f` (d51462f: deliverable 8a, the increment fix, with the last-info-line fix), test `8b8e34c` (8b8e34c: + B2, the danger-zone reserve, + (c), the iteration rule), bounds [-3, 0] nElo, 8+0.08, Hash 16 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40; cap 5,000 games
- Verdict: **ACCEPTED (stopped by the owner, 2026-10-27: "I trust the changes")** after 2,303 finished games. The last report (2,200 games): +1.9 +/- 10.6 Elo, LLR 0.22 of 2.94 on non-regression bounds; it was not decided by the rule. With its stress results (B2 0 time losses in 2,000 games at 2+0.02 under full load, (a) alone 3, (c) alone 1), the combination is merged as deliverable 8. sprt.sh's own summary of this run was cut off, and the figures here are from its game log. (Audit-1, U-1: the cut-off was a bug in sprt.sh, which aborted on an unset BASE_OPTS when writing the entry, not the stop.) No time losses, crashes or illegal moves.
```
Elo: 1.89 +/- 10.62, nElo: 2.59 +/- 14.51
Games: 2202, Wins: 764, Losses: 752, Draws: 686, Points: 1107.0 (50.27 %)
LLR: 0.22 (7.6%) (-2.94, 2.94) [-3.00, 0.00]
```

### 20261027T194536Z d8-ltc

- base `d51462f` (deliverable 8a with the last-info-line fix), test `91365e2` (deliverable 8's final form, merged), bounds [-3, 0] nElo, 40+0.4, Hash 64 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40; cap 1,000 games ("a short check")
- Verdict: **INCONCLUSIVE (stopped by the owner, 2026-10-27)** after 592 finished games, no time losses, crashes or illegal moves. fastchess's last report (400 games): -14.8 +/- 20.9 Elo, LLR -0.23. All 590 games in complete pairs (counted by tools/cloud/sprt_merge.py from the game log): -4.7 +/- 18.0 Elo, nElo -7.3 +/- 28.0, LLR -0.09, Ptnml [18, 59, 144, 61, 13]. **Flagged for Phase 5**, which revisits time management at long time controls; **the iteration rule is the first thing to check there** (at 40+0.4 the danger-zone reserve should almost never bind, so a long-time-control effect, if any, is more likely the iteration rule's).
```
Elo: -14.77 +/- 20.88, nElo: -24.15 +/- 34.05
Games: 400, Wins: 124, Losses: 141, Draws: 135, Points: 191.5 (47.88 %)
Ptnml(0-2): [12, 43, 100, 40, 5], WL/DD Ratio: 2.85
LLR: -0.23 (-7.7%) (-2.94, 2.94) [-3.00, 0.00]
```

### Note (audit-1, 2026-10-28): SPRTs on the GitHub shards

From audit-1 on, the STC SPRTs run on GitHub-hosted runners
(`.github/workflows/sprt.yml`), in stages of 16 shards x 100 game pairs
(3,200 games), each shard a fastchess run over its own range of a
fixed-seed permutation of UHO_Lichess_4852_v1.epd (seed 20261027), both
engines with Syzygy 3-4-5. After each stage the shards' results are merged
by `tools/cloud/sprt_merge.py` (pentanomial, normalized Elo, alpha = beta =
0.05), which decides the SPRT; a run is capped at 20,000 games (it stops
after the stage that passes the cap). 8+0.08 s, Hash 16 MB, 1 thread.

### 20261028T045512Z b1-forced (GitHub shards)

- base `25c84a2` (25c84a2f1a13ff1389979001cd17f2fba290836c), test `15cf506` (15cf506e975db0b2ea016334123578e6ee2a2693: audit-1 B-1, stop a forced move early), bounds [-3, 0] nElo, 8+0.08, Hash 16 MB, 1 thread, 7 stages x 16 shards (runs 40634996379, 40637985671, 40640832350, 40643811569, 40647047024, 40650215657, 40653533452); cap 20,000 games
- Verdict: **ACCEPTED (owner decision, 2026-10-28)**. The SPRT reached the cap undecided (22,400 games, LLR 1.52 of 2.94, 0 time losses, 0 abnormal endings); its 95% interval, -2.58 to +4.50 Elo, lies entirely above the lower bound -3, so the change is kept without the resumed run that was queued.
```
Elo: 0.96 +/- 3.54, nElo: 1.24 +/- 4.55
Ptnml(0-2): [1132, 2249, 4342, 2379, 1098]
LLR: 1.52 (-2.94, 2.94) [-3.00, 0.00] nElo: continue
```

### 20261028T045620Z b5-keep-deeper

- base `15cf506` (15cf506e975db0b2ea016334123578e6ee2a2693), test `808dd8a` (808dd8a537e58254c10bee0540afab61a0122499), bounds [0, 3] nElo, 40+0.4, Hash 64 MB, 1 thread, concurrency 10, adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40, Syzygy 3-4-5 for both sides (~/fork-tools/syzygy/3-4-5)
- Builds: base Fork 0.3.0-dev, clang 21.1.8 (6ubuntu1), bench 17309921 372dc2e2d8a88e4b (= bench.ref); test Fork 0.3.0-dev, clang 21.1.8 (6ubuntu1), bench 17309921 372dc2e2d8a88e4b (= bench.ref). Openings in random order, -srand 20261028045620.
- Verdict: **INCONCLUSIVE: stopped by the owner (2026-10-28)** after 2,604 games (fastchess exit status 1: the stop); cap 10,000 games. The owner's decision, at 2,000 games (-7.3 +/- 11.5 Elo, LLR -0.55): stop, leaning negative; the rule is switched off (d33ee48) and deferred to Phase 6's TT tests under large Hash and many threads (ideas.md idea 30).
```
Elo: -5.07 +/- 10.08, nElo: -6.72 +/- 13.35
Games: 2602, Wins: 826, Losses: 864, Draws: 912, Points: 1282.0 (49.27 %)
Ptnml(0-2): [116, 306, 486, 286, 107], WL/DD Ratio: 2.04
LLR: -0.53 (-18.0%) (-2.94, 2.94) [0.00, 3.00]
```

### 20261028T082946Z b3-shallow-fh (GitHub shards)

- base `4b3a808` (4b3a80886533844e67bfca7873c100f19712c63a), test `b001d1e` (b001d1e7687019db81790d73bef2d1474e2fc433: audit-1 B-3, re-search a root fail high one ply shallower), bounds [0, 3] nElo, 8+0.08, Hash 16 MB, 1 thread, 7 stages x 16 shards (runs 40657189708, 40661209179, 40667882215, 40671981921, 40676026047, 40680069346, 40683903943); cap 20,000 games
- Verdict: **INCONCLUSIVE at the cap** (22,400 games, LLR -0.37, 0 time losses, 0 abnormal endings). Phase C keeps passes only: **reverted** in bc44071.
```
Elo: 0.65 +/- 3.56, nElo: 0.83 +/- 4.55
Ptnml(0-2): [1123, 2313, 4329, 2269, 1166]
LLR: -0.37 (-2.94, 2.94) [0.00, 3.00] nElo: continue
```

### Note (owner, 2026-10-28): non-regression early acceptance

From b2-tb-depth's stage 3 on, a non-regression SPRT ([-3, 0]) on a change
with a clear rationale stops once at least 10,000 games are in and the 95%
Elo interval's lower bound is above -3: **ACCEPTED (by rule)**, logged with
the interval (DESIGN.md §5.2, Testing setup). Gainer-bound tests never stop
early this way. The cloud driver checks it after every stage.

### 20261028T122710Z b2-tb-depth (GitHub shards)

- base `b001d1e` (b001d1e7687019db81790d73bef2d1474e2fc433), test `6ab7cb7` (6ab7cb7890ec034e48e0e76a7826caea8357ec9e: audit-1 B-2, a settling table result stored in the TT at full depth), bounds [-3, 0] nElo, 8+0.08, Hash 16 MB, 1 thread, Syzygy 3-4-5 for both sides, 7 stages x 16 shards (runs 40687916291, 40692238847, 40696702688, 40701359689, 40706348255, 40711472101, 40716437644); cap 20,000 games
- The early-acceptance rule was checked after stages 3-6: Elo intervals [-3.95, +5.53] at 12,800 games, [-4.42, +4.08] at 16,000, [-4.41, +3.32] at 19,200, [-4.49, +2.66] at 22,400; the lower bound never cleared -3.
- Verdict: **INCONCLUSIVE at the cap** (22,400 games, LLR 0.19, 0 time losses, 0 abnormal endings). Phase C keeps passes only: **reverted** in 8e87028.
```
Elo: -0.92 +/- 3.58, nElo: -1.16 +/- 4.55
Ptnml(0-2): [1172, 2299, 4281, 2312, 1136]
LLR: 0.19 (-2.94, 2.94) [-3.00, 0.00] nElo: continue
```
