# B1: the pruning eval's error at RFP, futility and the null move (2026-11-22)

Owner-approved offline check, input for the final retune's group G1a
(RfpMargin, FutilityOffset, FutilityGrowth, NullSurplusPerPly and their
depth limits), which runs last among the STC groups.

**Rule (DESIGN.md §5.2, Testing setup, owner 2026-11-12): an offline
measurement only informs the retune's ranges. Nothing here picks a value or
gates a test; the retune's games decide.**

## Method

A pruned node has no search result, so each sampled node is searched a
second time with the one site switched off there, in a side search the real
search never sees (the decision ledger, DESIGN.md §5.7, X10; the null-move
rows are new, behind `FORK_NULL_LEDGER`, commit 35899250 on
`measure/b1-eval-error`). The real search, and so the population of
candidate nodes, is the play build's: the stats bench with the ledger on
gives 5,205,938 / a85d03889dade5af, the reference.

- **Error** = pruning eval (the static eval after the drift tables and the
  TT refinement: the value the site compares with its margin) minus the
  side search's result, in cp.
- **RFP rows**: every RFP condition but the margin, and pruning eval >= beta.
  Result: the node with RFP off there. Wrong prune: today's margin (55·d)
  prunes and the result fails low. Missed: it does not prune and the result
  fails high.
- **Futility rows**: every condition but the margin, and pruning eval <=
  alpha. Result: the node with futility off there (a second arm forces it
  on). Wrong prune: today's margin (86 + 50·d) makes the node futile, the on
  arm fails low and the off arm fails high (X10's rule). Missed: not futile,
  and both arms fail low.
- **Null rows**: every null-move condition holds (the null search is
  tried). Result: the node with the null move off there. Wrong cut: the null
  search reached beta and the result fails low. Missed: no cut, and the
  result fails high.
- **Bound level**: the result's side of the window. Every site runs only at
  non-PV nodes, which Fork searches on a zero window, so a result is a lower
  bound (fail high) or an upper bound (fail low) and **never exact**: the
  counter `ledger_wide_windows` (arms entered on a window wider than one
  point) is 0 over both runs. The exact level is empty by construction. A
  fail-soft lower bound v means the true value is at least v, so a "lower"
  row's error over-states the true error and an "upper" row's under-states
  it.
- Rows whose arm or null score is a mate or tablebase score (0.4%) are left
  out of the error statistics and counted under "mate"; arms are clamped to
  ±2,000 cp around beta by the engine.
- Sampling: 1 in 8 candidates by the position's key (`FORK_PRUNE_LEDGER=8`,
  `FORK_NULL_LEDGER=1`).

**Positions.** (1) The bench (46 positions, its own depth, a cleared state
per position). (2) 300 evolve positions at depth 12. The set behind the
RfpMargin row's "300 evolve positions at depth 12" (audit-1, commit
304081e1, 2026-10-28) **could not be found**: no file, seed or selection
rule is recorded in DESIGN.md, ideas.md idea 34, docs/history/phase-3 or
that commit, and `tools/evolve/positions.jsonl` was regenerated (the 4x set,
090252ef) the evening before. So the rule here, stated before the run:
`random.Random(20261122).sample` of the 4,794 rows of split "evolve" in
`tools/evolve/positions.jsonl` at 3875ca9f, 300 drawn, kept in file order
(`eval_error.py select`). Each is searched from a cleared state
(`ucinewgame`), Hash 16, one thread, no tablebases, `go depth 12`.

**Runs** (jobctl job `b1-eval-error`, type measure, 11:41 to 11:44 PM EST):
the clang-stats build at 35899250 (Windows, net r3kr1). Bench: 36.1 s wall,
274,386 rows. Evolve: 157.3 s wall, 23,967,464 search nodes, 1,200,789 rows.
The side searches took 4,257,977 (bench) and 19,031,291 (evolve) extra
nodes, uncounted by the real search. One single-threaded engine at a time,
so the CPU time is about the wall time (not measured separately;
UNVERIFIED). Bench and evolve agree closely (per-source tables from
`eval_error.py report`), so the tables below pool them.

## Error by site, bound and depth (pooled, cp)

| site | bound | depth | count | mean | SD | p5 | p25 | p50 | p75 | p95 |
|---|---|---|---|---|---|---|---|---|---|---|
| rfp | lower | 1 | 705578 | -56.1 | 165.3 | -402 | -90 | -6 | 25 | 117 |
| rfp | lower | 2 | 173516 | -4.1 | 152.7 | -324 | -30 | 11 | 74 | 169 |
| rfp | lower | 3 | 96632 | 65.8 | 137.0 | -80 | 13 | 47 | 103 | 287 |
| rfp | lower | 4 | 38422 | 79.5 | 135.2 | -58 | 14 | 52 | 123 | 289 |
| rfp | lower | 5 | 22331 | 87.8 | 132.9 | -36 | 18 | 56 | 141 | 299 |
| rfp | lower | 6 | 13403 | 103.6 | 141.3 | -12 | 28 | 63 | 171 | 337 |
| rfp | upper | 1 | 11512 | 39.8 | 53.3 | 5 | 13 | 24 | 45 | 132 |
| rfp | upper | 2 | 5204 | 47.4 | 61.2 | 4 | 14 | 28 | 57 | 157 |
| rfp | upper | 3 | 2869 | 35.9 | 45.6 | 4 | 11 | 23 | 43 | 107 |
| rfp | upper | 4 | 1444 | 30.4 | 33.8 | 3 | 10 | 20 | 39 | 91 |
| rfp | upper | 5 | 823 | 27.0 | 40.0 | 2 | 7 | 15 | 29 | 90 |
| rfp | upper | 6 | 526 | 21.8 | 23.9 | 2 | 7 | 15 | 28 | 68 |
| rfp | all | 1 | 717090 | -54.5 | 164.5 | -399 | -87 | -5 | 26 | 117 |
| rfp | all | 2 | 178720 | -2.6 | 151.0 | -318 | -27 | 13 | 73 | 169 |
| rfp | all | 3 | 99501 | 65.0 | 135.3 | -76 | 12 | 46 | 101 | 283 |
| rfp | all | 4 | 39866 | 77.7 | 133.2 | -55 | 13 | 50 | 118 | 285 |
| rfp | all | 5 | 23154 | 85.6 | 131.3 | -33 | 16 | 53 | 134 | 297 |
| rfp | all | 6 | 13929 | 100.5 | 139.6 | -10 | 25 | 59 | 166 | 336 |
| futility | lower | 1 | 56659 | -182.7 | 180.1 | -558 | -274 | -119 | -43 | -11 |
| futility | lower | 2 | 17993 | -140.9 | 158.2 | -484 | -198 | -78 | -29 | -8 |
| futility | lower | 3 | 8662 | -140.9 | 159.8 | -485 | -196 | -77 | -28 | -7 |
| futility | lower | 4 | 4033 | -108.3 | 144.3 | -432 | -147 | -46 | -17 | -5 |
| futility | lower | 5 | 2414 | -107.2 | 153.1 | -445 | -132 | -34 | -13 | -3 |
| futility | lower | 6 | 1489 | -70.1 | 122.8 | -349 | -57 | -20 | -10 | -3 |
| futility | upper | 1 | 102314 | -56.0 | 105.9 | -262 | -63 | -20 | -1 | 23 |
| futility | upper | 2 | 42834 | -57.7 | 107.4 | -265 | -70 | -22 | -1 | 28 |
| futility | upper | 3 | 19491 | -67.0 | 107.3 | -267 | -88 | -30 | -6 | 18 |
| futility | upper | 4 | 12236 | -81.6 | 115.4 | -294 | -110 | -41 | -12 | 11 |
| futility | upper | 5 | 4471 | -84.1 | 115.0 | -300 | -120 | -40 | -12 | 6 |
| futility | upper | 6 | 3455 | -106.3 | 121.4 | -331 | -173 | -59 | -18 | 0 |
| futility | all | 1 | 158973 | -101.2 | 149.9 | -414 | -143 | -39 | -9 | 16 |
| futility | all | 2 | 60827 | -82.3 | 130.3 | -355 | -106 | -33 | -7 | 21 |
| futility | all | 3 | 28153 | -89.8 | 130.4 | -359 | -120 | -41 | -11 | 12 |
| futility | all | 4 | 16269 | -88.2 | 123.8 | -335 | -117 | -42 | -13 | 7 |
| futility | all | 5 | 6885 | -92.2 | 130.1 | -363 | -123 | -38 | -12 | 0 |
| futility | all | 6 | 4944 | -95.4 | 123.0 | -337 | -150 | -42 | -13 | 0 |
| null | lower | 3 | 52780 | -21.4 | 116.2 | -290 | -21 | 4 | 31 | 81 |
| null | lower | 4 | 25974 | -1.1 | 107.7 | -219 | -6 | 15 | 48 | 108 |
| null | lower | 5 | 16520 | 19.6 | 103.9 | -179 | 0 | 28 | 65 | 150 |
| null | lower | 6 | 10168 | 34.6 | 114.8 | -210 | 9 | 36 | 83 | 200 |
| null | lower | 7-8 | 7122 | 61.5 | 121.6 | -110 | 10 | 42 | 97 | 282 |
| null | lower | 9-11 | 1682 | 21.4 | 103.8 | -137 | 0 | 5 | 49 | 214 |
| null | lower | 12+ | 17 | 76.4 | 149.8 | -55 | 0 | 27 | 68 | 437 |
| null | upper | 3 | 2775 | 32.5 | 32.8 | 4 | 11 | 23 | 43 | 91 |
| null | upper | 4 | 1445 | 29.4 | 30.5 | 3 | 10 | 20 | 39 | 87 |
| null | upper | 5 | 815 | 25.3 | 34.4 | 2 | 7 | 15 | 28 | 81 |
| null | upper | 6 | 517 | 22.4 | 25.4 | 2 | 7 | 15 | 28 | 70 |
| null | upper | 7-8 | 421 | 19.4 | 26.1 | 1 | 5 | 11 | 22 | 62 |
| null | upper | 9-11 | 91 | 23.1 | 35.9 | 1 | 5 | 12 | 26 | 76 |
| null | all | 3 | 55555 | -18.8 | 114.1 | -280 | -18 | 6 | 32 | 81 |
| null | all | 4 | 27419 | 0.5 | 105.2 | -208 | -3 | 15 | 48 | 107 |
| null | all | 5 | 17335 | 19.9 | 101.8 | -172 | 0 | 27 | 64 | 150 |
| null | all | 6 | 10685 | 34.0 | 112.2 | -203 | 8 | 36 | 79 | 200 |
| null | all | 7-8 | 7543 | 59.2 | 118.7 | -94 | 9 | 42 | 92 | 279 |
| null | all | 9-11 | 1773 | 21.5 | 101.4 | -125 | 0 | 7 | 48 | 209 |
| null | all | 12+ | 17 | 76.4 | 149.8 | -55 | 0 | 27 | 68 | 437 |

(No "exact" rows: see Method.) Reading: RFP's result is a lower bound in
96-98% of its rows, so its "lower" errors are mostly upper bounds on the
true error; its "upper" rows (where a prune would be wrong) sit only 15-28
cp below the pruning eval on median. Futility's errors are negative (the
search ends above the pruning eval), with a spread (SD 120-150 cp) that
barely changes with depth while the margin grows 50 cp per ply. The null
move's mean error grows with depth from -19 cp (depth 3) to +59 cp (7-8).

## Calls at today's margins (pooled)

wrong/fired: the share of today's prunes (cuts) that were wrong.
missed/unfired: the share of the candidates today's margin keeps whose
result says the prune would have held.

| site | depth | rows | mate | fired | wrong | wrong/fired | missed | missed/unfired |
|---|---|---|---|---|---|---|---|---|
| rfp | 1 | 720435 | 3345 | 529907 | 1461 | 0.28% | 180477 | 94.72% |
| rfp | 2 | 179498 | 778 | 92384 | 260 | 0.28% | 82170 | 94.32% |
| rfp | 3 | 99685 | 184 | 42348 | 40 | 0.09% | 54508 | 95.07% |
| rfp | 4 | 39928 | 62 | 12045 | 4 | 0.03% | 26443 | 94.84% |
| rfp | 5 | 23184 | 30 | 5639 | 3 | 0.05% | 16725 | 95.33% |
| rfp | 6 | 13946 | 17 | 3125 | 0 | 0.00% | 10295 | 95.14% |
| rfp | all | 1076676 | 4416 | 685448 | 1768 | 0.26% | 370618 | 94.73% |
| futility | 1 | 159721 | 748 | 47173 | 4 | 0.01% | 62739 | 55.74% |
| futility | 2 | 61143 | 316 | 17407 | 0 | 0.00% | 27196 | 62.18% |
| futility | 3 | 28363 | 210 | 6336 | 0 | 0.00% | 13717 | 62.27% |
| futility | 4 | 16373 | 104 | 3580 | 0 | 0.00% | 8791 | 68.72% |
| futility | 5 | 6945 | 60 | 1068 | 0 | 0.00% | 3450 | 58.70% |
| futility | 6 | 4980 | 36 | 781 | 0 | 0.00% | 2686 | 63.97% |
| futility | all | 277525 | 1474 | 76345 | 4 | 0.01% | 118579 | 58.94% |
| null | 3 | 55848 | 293 | 25681 | 108 | 0.42% | 27488 | 91.12% |
| null | 4 | 27557 | 138 | 11883 | 35 | 0.29% | 14252 | 90.93% |
| null | 5 | 17417 | 82 | 7122 | 14 | 0.20% | 9492 | 92.20% |
| null | 6 | 10750 | 65 | 4256 | 10 | 0.23% | 5975 | 92.01% |
| null | 7-8 | 7587 | 44 | 2938 | 5 | 0.17% | 4217 | 90.71% |
| null | 9-11 | 1798 | 25 | 555 | 4 | 0.72% | 1144 | 92.04% |
| null | 12+ | 17 | 0 | 6 | 0 | 0.00% | 11 | 100.00% |
| null | all | 120974 | 647 | 52441 | 176 | 0.34% | 62579 | 91.31% |

Per source, wrong/fired: RFP 0.37% (bench) and 0.23% (evolve), futility
0.02% and 0.00%, null 0.58% and 0.28%. Wrong events are few: every cell
with fewer than 100 wrong events (all but RFP depths 1-2 and null depth 3)
is thin, and its rate is rough.

## Margin sweeps (pooled)

RFP: share of the candidates pruned / wrong rate among the prunes, at a
margin of M·d (today M = 55).

| depth | M=30 | M=40 | M=45 | M=50 | M=55 | M=60 | M=65 | M=70 | M=80 | M=100 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 87.0% / 0.48% | 81.8% / 0.37% | 79.1% / 0.33% | 76.4% / 0.30% | 73.6% / 0.28% | 70.6% / 0.25% | 67.6% / 0.23% | 64.7% / 0.21% | 59.0% / 0.19% | 49.1% / 0.16% |
| 2 | 71.3% / 0.50% | 62.2% / 0.36% | 58.2% / 0.33% | 54.8% / 0.31% | 51.5% / 0.28% | 48.3% / 0.26% | 45.5% / 0.25% | 43.0% / 0.23% | 38.5% / 0.19% | 31.0% / 0.13% |
| 3 | 62.2% / 0.17% | 52.9% / 0.13% | 49.1% / 0.11% | 45.7% / 0.10% | 42.5% / 0.09% | 39.6% / 0.09% | 36.9% / 0.07% | 34.3% / 0.06% | 29.4% / 0.04% | 20.9% / 0.02% |
| 4 | 47.8% / 0.12% | 39.0% / 0.06% | 35.8% / 0.03% | 32.9% / 0.04% | 30.2% / 0.03% | 27.7% / 0.03% | 25.3% / 0.01% | 22.8% / 0.00% | 18.4% / 0.00% | 12.8% / 0.00% |
| 5 | 43.5% / 0.14% | 34.8% / 0.09% | 31.0% / 0.07% | 27.4% / 0.05% | 24.3% / 0.05% | 21.5% / 0.06% | 18.8% / 0.02% | 16.8% / 0.03% | 13.1% / 0.00% | 8.7% / 0.00% |
| 6 | 41.2% / 0.02% | 32.4% / 0.00% | 28.6% / 0.00% | 25.3% / 0.00% | 22.4% / 0.00% | 19.6% / 0.00% | 17.4% / 0.00% | 15.3% / 0.00% | 12.2% / 0.00% | 7.6% / 0.00% |

Futility: share of the candidates futile / wrong rate among them, at a
margin of offset + growth·d (today 86 + 50·d).

| depth | 86+50d | 60+40d | 70+45d | 100+50d | 86+35d | 86+65d | 100+70d | 50+30d | 120+60d |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 29.5% / 0.01% | 36.6% / 0.03% | 33.2% / 0.02% | 27.7% / 0.01% | 32.1% / 0.02% | 27.5% / 0.01% | 25.3% / 0.00% | 42.7% / 0.07% | 24.2% / 0.01% |
| 2 | 28.5% / 0.00% | 34.6% / 0.01% | 31.9% / 0.00% | 26.8% / 0.00% | 32.4% / 0.01% | 25.0% / 0.00% | 22.1% / 0.00% | 39.7% / 0.04% | 22.1% / 0.00% |
| 3 | 22.3% / 0.00% | 29.6% / 0.00% | 26.5% / 0.00% | 20.9% / 0.00% | 28.3% / 0.00% | 17.9% / 0.00% | 15.2% / 0.00% | 34.3% / 0.01% | 16.2% / 0.00% |
| 4 | 21.9% / 0.00% | 30.4% / 0.00% | 26.4% / 0.00% | 20.6% / 0.00% | 29.7% / 0.00% | 17.0% / 0.00% | 14.8% / 0.00% | 36.7% / 0.02% | 16.1% / 0.00% |
| 5 | 15.4% / 0.00% | 22.3% / 0.00% | 19.3% / 0.00% | 14.8% / 0.00% | 22.2% / 0.00% | 13.0% / 0.00% | 11.9% / 0.00% | 27.4% / 0.05% | 12.7% / 0.00% |
| 6 | 15.7% / 0.00% | 20.3% / 0.00% | 18.1% / 0.00% | 15.0% / 0.00% | 20.5% / 0.00% | 12.0% / 0.00% | 9.9% / 0.00% | 26.6% / 0.00% | 11.7% / 0.00% |

Null move by surplus (pruning eval - beta; today one more ply of reduction
per 301 cp, at most 2): rows / share cut / wrong among the cuts. The bands
are the reduction's steps (0-300: none; 301-601: one ply; 602+: two).

| depth | 0-99 | 100-300 | 301-601 | 602+ |
|---|---|---|---|---|
| 3 | 39773 / 36.9% / 0.68% | 16075 / 68.5% / 0.07% | 0 / -% / -% | 0 / -% / -% |
| 4 | 18438 / 32.7% / 0.55% | 9119 / 64.1% / 0.03% | 0 / -% / -% | 0 / -% / -% |
| 5 | 10248 / 27.8% / 0.46% | 7169 / 59.5% / 0.02% | 0 / -% / -% | 0 / -% / -% |
| 6 | 5942 / 25.5% / 0.59% | 4426 / 57.1% / 0.04% | 382 / 56.5% / 0.00% | 0 / -% / -% |
| 7-8 | 4060 / 22.6% / 0.55% | 2237 / 57.2% / 0.00% | 1003 / 54.4% / 0.00% | 287 / 67.9% / 0.00% |
| 9-11 | 1032 / 18.5% / 2.09% | 464 / 45.0% / 0.00% | 237 / 46.8% / 0.00% | 65 / 67.7% / 0.00% |
| 12+ | 9 / 22.2% / 0.00% | 4 / 25.0% / 0.00% | 4 / 75.0% / 0.00% | 0 / -% / -% |

The empty cells are structural: RFP (55·d, up to depth 6) cuts first every
node whose surplus reaches 55·d, so the null move sees a surplus over 300
cp only from depth 6, and over 601 cp only from depth 7. NullSurplusPerPly
acts only where RFP does not, so it is coupled to RfpMargin and RfpMaxDepth.

## What the data suggest for G1a's ranges (ranges only)

None of this picks a value; each line only says where a range should reach.

- **RfpMargin (55).** At M = 30 the wrong rate among prunes rises to 0.48%
  (depth 1) and 0.50% (depth 2), and stays at 0.17% or less at depths 3-6:
  within audit-1's 1% criterion, while the prune share at depth 1 grows from
  74% to 87%. The data do not exclude the planned lower bound of about 30
  and give no reason against 25. Above about 80 the prune share falls fast
  (depth 1: 59% at 80, 49% at 100) while the wrong rate falls only from
  0.28% to 0.16%. Suggested range about 25-100.
- **RfpMaxDepth (6).** The wrong rate falls with depth at every margin
  (0.00% at depth 6 for M >= 40). That points to including 7-8 in the
  range, but no row exists beyond depth 6 (the ledger samples only RFP's
  own depths), so this is extrapolation (UNVERIFIED). Suggested range 5-8.
- **FutilityOffset, FutilityGrowth (86 + 50·d).** Today 4 wrong of 76,345
  futile rows; even 50 + 30·d has at most 0.07% (depth 1). 56-69% of the
  candidates today's margin keeps fail low with both arms. The data point
  below today's values: suggested ranges offset about 30-120 and growth
  about 25-70 (both lower ends at today's tuning floors in
  src/tune/params.hpp). Caveat: X10's rule counts only outcome flips (on
  fails low, off fails high), not a changed score inside a fail low.
- **FutilityMaxDepth (6).** No wrong prune at depths 3-6 at any swept
  margin; as for RFP, no row beyond depth 6 (UNVERIFIED). Suggested range
  5-8.
- **NullSurplusPerPly (301).** Wrong cuts concentrate at a surplus of 0-99
  cp (0.46-0.68% of the cuts at depths 3-8); at 100 cp and above they are
  0.00-0.07%, the reduced null searches included (0 wrong of 546 one-ply
  and 195 two-ply surplus cuts at depths 7-8; thin). More reduction per cp
  of surplus shows no visible cost here: suggested range about 150-450 (the
  lower end the tuning floor). Tune it with RfpMargin and RfpMaxDepth, which
  decide where it acts at all.
- **NullMinDepth (3).** Wrong-cut rate 0.42% at depth 3 against 0.20-0.29%
  at depths 4-6; no data at depth 2 (rows start at the limit). Suggested
  range 2-4.

## Tests and checks

- clang-release bench 5,205,938 / a85d03889dade5af before and after; its
  `.text`, `.data` and `.pdata` sections are byte-identical to 3875ca9f's
  build (`.rdata` differs by the embedded commit id only). clang-stats bench
  the same, with the ledger off and on.
- search_stats: the new case "null-move ledger rows match the real search's
  null searches" passes; fault check: without the `ledger_null_candidates`
  increment it fails (825 vs 0). Two cases fail at 3875ca9f before this
  change as after it ("the feature stack's tally matches hand counts" and
  "X2 histograms add up, and history carries over between searches"),
  unrelated to B1 and left as they are.
- tools/measure tests: 41 pass (7 new in test_eval_error.py, one new check
  in test_engine_lines.py); the pre-commit `check.sh quick` passed.

## Reproduce

    python -I tools/measure/eval_error.py select tools/evolve/positions.jsonl evolve300.fen
    python -I tools/measure/eval_error.py run build/clang-stats/fork OUT --bench --every 8
    python -I tools/measure/eval_error.py run build/clang-stats/fork OUT --fens evolve300.fen --depth 12 --every 8
    python -I tools/measure/eval_error.py report OUT --every 8
