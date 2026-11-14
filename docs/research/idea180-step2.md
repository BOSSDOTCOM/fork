# Idea 180, step 2: r8brft1's heads rescaled by phase and queen state (2026-11-14)

**Status: prepared, not screened.** Owner's plan (2026-11-14): "Idea 6 step 2 first (no training): rescale
r8brft1's output heads by queen state (and phase) from Fork's own calibration fit; FN screen vs r8brft1 + UHO
diagnostic. Report before any label work." The fixed-node screen is queued only after retrain 8c's promotion
decision; everything before it is done here. Proposal: docs/research/network-novelty-2026-11-14.md, idea 6 (E6, E7,
E12); ideas.md 180.

## Summary

- **The fit, split by output bucket and queen state, says the class structure is phase, not queen state.** In
  Fork's STC games the logistic scale k of the search score against the result falls steadily with the phase
  bucket, from 107 cp in bucket 0 (phase 0-3) to 55 cp in bucket 7 (opening material); within a bucket the queens-on
  and queenless cells differ little and not in one direction (bucket 3: on 70.0, off 66.2; bucket 4: on 61.9,
  off 65.0). The pooled "queens on 59.6, off 74.1" (E6) is mostly the phase mix: queenless positions sit in the low
  buckets. LTC shows the same pattern, a little stronger; the 20,000-node data games show **none** (every cell
  69-74 cp). The same trend appears with a balanced book (the decision-audit games), so it is not the UHO book's.
- **Factors** (declared rule: the pooled STC k over the cell's k; thin cells at their bucket's factor; clipped to
  [0.70, 1.40]): 0.70 (bucket 0, fitted 0.61) rising to 1.18 (bucket 7). The queen-state split changes four
  cells by 0.02-0.05 from their bucket's value.
- **Two candidates built:** (a) an engine change, a Q12 multiplier per (bucket, queen state) after the head
  (default builds unchanged, bench 5,386,021 / 5ecd49d976e215e1; the candidate's bench 5,263,251 /
  1e9d3fff8873a2d3); (b) a pure net-file edit of the 8 heads (r8brft1hs, bench 4,913,609 / ba18170f0bf15ae7).
- **UHO/SF19 diagnostic:** adv static +40.0 -> +47.5 (a) / +48.0 (b), search +50 -> +57; levelql static +24.0 ->
  +21.5 / +21.0. Both moved the declared way but **neither crossed the declared 8 cp line** (adv +7.5 / +8.0 is
  not "more than 8"), so by the rule the diagnostic **did not move**. Not a scale shift (levelql fell).
- **Speed:** (b) is phase-4's engine with another net file of the same architecture (ratio 1 by construction). (a)
  adds a bitboard test, a table load and a 64-bit multiply per evaluation; bench/ab_search.py found no difference,
  but on a machine at 87-93% CPU load its noise threshold was 10.7-13.2% (section 5): not re-measured in a quiet window.
- **The screen items are ready** (not queued): ~/fork-runners/scratch-i180/item-i180-fn-{a,b}.sh, 1,600 games at
  800,000 nodes per move on stage 6's openings, fresh for the fit (decision 16 of 2026-11-07).

## 1. The fit

Method declared before any per-class number (~/fork-runners/scratch-i180/fit/method.md): calib-1112's model
unchanged (E[points] = sigmoid((s + c_t) / k), one intercept per engine tag, maximum likelihood with draws as half a
point on 5-cp bins of |s| < 1000, the first 6 engine plies, mates, |s| > 20,000 and (timed games) clock < 12.5% of
base excluded; 95% CIs by an opening-clustered bootstrap, 200 clusters, 400 resamples, seed 20261114).

- **Classes.** Output bucket b = r8brft1's own phase table applied to the phase (N, B 1, R 2, Q 4, capped at 24):
  phase 0-3 -> 0, 4-5 -> 1, 6-7 -> 2, 8-11 -> 3, 12-15 -> 4, 16-19 -> 5, 20-22 -> 6, 23-24 -> 7. Queen state:
  **off** = no queen of either colour, **on** = any queen. Why: E7's regime is the position with no queen at all,
  the engine tests it with one bitboard, and calib-1112 used the same split. A single queen (one side only) is a
  large imbalance, usually decisive and rare (78,019 of 2.64 M STC positions); it stays in "on". Bucket 0 cannot hold
  a queen (a queen alone is phase 4); buckets 6 and 7 cannot be queenless (queenless phase is at most 16).
- **Data, Fork's own games only.** D20K: data part g4c (fork_datagen 75d53f0, r8brft1 self-play, 20,000 nodes per
  saved move, lichess-2026-09 openings, adjudicated at 700 cp for 8 plies), the first 2,500 games of each of its 10
  shards, saved positions only (25,000 games, 1,206,619 positions; the decoder checked against python-chess's
  replay on 30 games, 1,366 records, 0 mismatches). STC: calib-1112's SPRT-STC (33,600 games of r8brft1 against
  itself at 8+0.08, UHO; 2,638,939 positions). LTC: calib-1112's SPRT-LTC (probcut-ltc2, 4,992 games at 40+0.4;
  431,841). The STC and LTC PGNs were re-read with calib-1112's own parser functions to add each move's phase and
  queens; the joined records equal calib-1112's plies files byte for byte on their columns (both groups), and the
  pooled fits reproduce its k (65.1, 67.0; queens on / off 59.6 / 74.1 at STC).

### The table: k in cp (95% CI), positions

| cell | D20K (20k nodes) | STC | LTC | STC static (r8brft1, 4 per game) | f = k_ref / k (STC) | used (Q12) |
|---|---|---|---|---|---|---|
| all | 71.2 (69.9-72.5) 1,206,619 | **65.1** (64.2-66.1) 2,638,939 | 67.0 (64.4-69.3) 431,841 | 76.9 (76.0-78.0) 134,400 | | |
| queens on | 71.0 (69.6-72.6) 586,850 | 59.6 (58.8-60.5) 1,560,706 | 57.8 (55.4-60.4) 237,720 | 75.2 (73.7-76.5) 70,085 | | |
| queens off | 71.4 (69.6-73.3) 619,769 | 74.1 (72.5-75.7) 1,078,233 | 81.0 (76.9-84.9) 194,121 | 78.5 (77.3-79.9) 64,315 | | |
| b0 (off only) | 74.3 (70.4-78.7) 107,143 | 106.9 (101.6-112.2) 236,972 | 116.9 (101.2-132.4) 49,518 | 82.9 (81.1-85.1) 14,399 | 0.609 (0.584-0.638) | **0.700** (2867), clipped |
| b1 | 70.0 (67.1-73.1) 177,526 | 77.3 (74.6-80.1) 237,659 | 86.5 (79.2-94.1) 48,751 | 79.2 (77.3-81.1) 18,676 | 0.842 (0.816-0.868) | 0.842 (3451) |
| b1 on | 57.7 (43.4-72.7) 3,762 | 124.2 (76.8-157.3) 2,463 | 59.6 (38.2-121.5) 335 | 86.1 (56.8-101.8) 418 | 0.524 (0.412-0.850) | thin: 0.842 (3451) |
| b1 off | 70.1 (67.2-73.2) 173,764 | 77.0 (74.3-79.7) 235,196 | 86.8 (79.5-94.2) 48,416 | 79.1 (77.1-81.0) 18,258 | 0.846 (0.818-0.871) | 0.846 (3465) |
| b2 | 72.8 (70.3-75.5) 153,880 | 72.3 (69.7-74.4) 208,215 | 76.7 (69.9-84.0) 37,801 | 75.3 (73.1-77.7) 15,051 | 0.902 (0.878-0.931) | 0.902 (3693) |
| b2 on | 86.3 (73.7-100.0) 19,406 | 107.3 (90.6-125.0) 19,943 | 115.7 (75.4-161.5) 4,355 | 81.2 (73.6-89.5) 1,877 | 0.607 (0.519-0.722) | thin: 0.902 (3693) |
| b2 off | 71.3 (68.7-74.1) 134,474 | 68.8 (67.0-70.4) 188,272 | 71.0 (66.0-76.0) 33,446 | 74.6 (72.7-76.9) 13,174 | 0.946 (0.927-0.973) | 0.946 (3876) |
| b3 | 71.0 (68.6-73.4) 221,374 | 67.2 (66.1-68.4) 348,621 | 68.8 (65.1-72.6) 56,074 | 77.4 (75.6-79.7) 19,927 | 0.969 (0.954-0.983) | 0.969 (3970) |
| b3 on | 73.6 (68.7-78.9) 81,610 | 70.0 (67.1-72.5) 106,962 | 70.8 (63.0-78.4) 19,490 | 78.1 (74.9-81.1) 8,225 | 0.931 (0.899-0.968) | 0.931 (3813) |
| b3 off | 69.7 (67.3-71.8) 139,764 | 66.2 (64.7-67.5) 241,659 | 68.0 (64.4-71.7) 36,584 | 76.9 (74.4-79.9) 11,702 | 0.985 (0.967-1.003) | 0.985 (4033) |
| b4 | 70.5 (68.2-72.9) 157,044 | 63.4 (62.0-64.8) 328,557 | 65.9 (61.4-71.5) 48,476 | 78.0 (75.7-80.4) 15,315 | 1.027 (1.008-1.046) | 1.027 (4206) |
| b4 on | 68.0 (65.0-70.9) 96,469 | 61.9 (60.2-63.4) 167,713 | 61.5 (57.8-65.5) 24,759 | 77.6 (74.6-80.4) 9,130 | 1.052 (1.028-1.075) | 1.052 (4308) |
| b4 off | 73.6 (70.4-76.7) 60,575 | 65.0 (62.7-67.3) 160,844 | 70.8 (62.5-83.3) 23,717 | 78.6 (74.9-82.6) 6,185 | 1.002 (0.973-1.035) | 1.002 (4105) |
| b5 | 68.6 (66.8-70.6) 146,445 | 60.1 (59.1-61.3) 327,667 | 59.4 (56.3-62.6) 47,290 | 79.0 (76.1-81.5) 13,714 | 1.084 (1.068-1.101) | 1.084 (4440) |
| b5 on | 68.3 (66.4-70.3) 142,396 | 60.2 (59.1-61.3) 312,377 | 59.2 (56.1-62.3) 44,850 | 79.3 (76.2-81.9) 13,117 | 1.082 (1.065-1.100) | 1.082 (4431) |
| b5 off | 80.5 (69.1-94.5) 4,049 | 57.6 (52.6-63.1) 15,290 | 63.2 (51.3-80.2) 2,440 | 70.1 (58.9-83.0) 597 | 1.131 (1.035-1.240) | thin: 1.084 (4440) |
| b6 (on only) | 72.4 (70.4-74.4) 176,849 | 57.4 (56.4-58.4) 667,662 | 54.4 (52.3-56.6) 99,655 | 71.3 (69.3-73.3) 26,754 | 1.134 (1.118-1.150) | 1.134 (4645) |
| b7 (on only) | 71.3 (68.5-74.2) 66,358 | 55.4 (53.9-56.9) 283,586 | 51.9 (48.8-55.3) 44,276 | 70.1 (66.8-73.5) 10,564 | 1.176 (1.151-1.206) | 1.176 (4819) |

Factor CIs are paired (the same cluster draws for every cell of a group). "Thin" (declared): fewer than 20,000 STC
positions, or a CI on k wider than 30% of k.

**Book check (diagnostic, not used for the factors):** calib-1112's decision-audit games (r8brft1's moves against
s512ppr3, 10+0.1, no adjudication; 200 resamples): balanced 8-ply book b0 109.3, b1 73.8, b2 72.3, b3 60.2, b4
54.3, b5 53.3, b6 49.2, b7 45.8 (pooled 56.4); UHO book b0 141.5, b1 85.0, b2 76.1, b3 65.9, b4 61.6, b5 58.4,
b6 58.9, b7 54.8 (pooled 69.4). The phase trend is there with either book.

**Readings.**
- The trend is in the search score, not the static evaluation: the static k varies only from 70 to 83 across
  buckets (STC sample), the search's from 55 to 107. The proposal's E6 ("the static eval shows much less of it")
  holds per bucket too.
- It grows with the budget: flat at 20,000 nodes, strong at STC, a little stronger at LTC (b0 107 -> 117, b7 55 ->
  52). That is E12's direction. One confound is not separable here: the data games are adjudicated at 700 cp and
  use a balanced lichess book, the timed games neither.
- Queen state within a bucket: small, mixed in sign, within or near the CIs; at 20,000 nodes the pooled queens
  on/off k are equal (71.0 / 71.4).

## 2. The factors and why

- **f(b, q) = k_ref / k(b, q), k_ref = the pooled STC k (65.15).** The hypothesis is about the relative scale of
  the classes; normalising to the pooled fit keeps the evaluation's average level (the position-weighted mean of
  f over the STC positions is 1.006 unclipped, 1.014 (b) and 1.017 (a) with bucket 0's clip), so the search's eval-dependent margins, tuned on r8brft1's scale, stay where they
  are, and the screen tests the class correction, not a global rescale. **Rejected for step 2: f = 88 / k** (S
  over the fit, the deleted CalibratedScore's mapping): it would raise every evaluation by about 1.35 and move every
  margin at once, a retune question confounded with the class question.
- **STC, not an extrapolation.** The factors use the STC fit: the largest n, and the screen's 800,000 nodes per
  move lies between the STC and LTC budgets. Extrapolating the trend (step 3's label form) needs more budgets
  than 20k, STC and LTC, and the 20k column is confounded (above).
- **Search-score fits, not static.** The head scale is the inference form of rewriting the labels' search scores
  by class (step 3); the static fit is reported as the cross-check. A static-matched variant would barely move
  anything (static k is nearly flat) and is not built.
- **Thin cells** take the bucket's factor (b1 on, b2 on, b5 off; the impossible cells b0 on, b6 off, b7 off too);
  the **rails** [0.70, 1.40] bind once: bucket 0's 0.609 -> 0.700.
- **Fixed point:** Q12, m = round(4096 f). Output = clamp(y S m / (QA QB 4096)), int64 throughout (y below 2^32,
  S below 2^17, m below 2^13); m = 4096 gives exactly today's clamp(y S / (QA QB)) (the same rational, truncated
  the same way). No floating point in the engine.

### How the queen-state factor is applied

The net file has one head per phase bucket. Two forms were built:
- **(a) after the head, per (bucket, queen state):** src/eval/nnue/head_scale.hpp, a [8][2] Q12 table selected by
  the bucket and `pieces(Queen) != 0`, applied in accumulator.cpp's phase-picked output. Default builds carry the
  unit table (`HeadScaleActive` false; the `if constexpr` branch is discarded): bench unchanged, 5,386,021 /
  5ecd49d976e215e1 (checked, commit f4d0fb4). `-DFORK_EXPERIMENT=HEAD_SCALE` selects the fitted table: bench
  5,263,251 / 1e9d3fff8873a2d3. The candidate commit for the screen turns the table on by default. Colour
  symmetry is kept (the queen state and the bucket are colour-symmetric). Test: the unit multiplier equals the
  unscaled output and 2x / 0.5x scale exactly against the scaling written another way (16,000 values x 4 scales;
  fault-injected m + 1 fails it); the default table is the unit and every entry is inside the rails.
- **(b) the 8 heads in the net file (phase only):** r8brft1hs. S cannot carry per-head factors and r8brft1's heads
  already reach |w| = 127 of the loader's 128, so no head can be scaled up in place: S goes from 88 to
  ceil(88 x 1.176) = 104 and each head's weights and bias are multiplied by g(b) = f(b) x 88 / 104 <= 1 (rounded half
  away from zero). The realised factors equal f(b) to 4 places; the weight rounding costs mean |dev| 2.03 cp, p99
  9.0 cp, max 14.6 cp against the ideal f(b) x r8brft1 on the 446 parity positions (comparable to r8brft1's own
  quantization loss, max 10.7 cp). netcheck exact (446 positions, the Python R-int of the edited file).

(a) and (b) differ only where the queen-state split moved a cell off its bucket's factor: b1 off 0.846 / 0.842,
b2 off 0.946 / 0.902, b3 0.931 on / 0.985 off / 0.969, b4 1.052 on / 1.002 off / 1.027. Most of either change is
the phase rescale.

## 3. Candidates

| variant | branch, commit | engine | default net | bench |
|---|---|---|---|---|
| base | phase-4 d63ddc6 | | r8brft1 | 5,386,021 / 5ecd49d976e215e1 |
| (a) code, table off | exp/i180-head-scale f4d0fb4 | head_scale.hpp, unit table | r8brft1 | 5,386,021 / 5ecd49d976e215e1 |
| (a) candidate | exp/i180-head-scale ed54dbe | the fitted table on by default | r8brft1 | 5,263,251 / 1e9d3fff8873a2d3 |
| (b) candidate | exp/i180-head-scale-b 449434a | phase-4 d63ddc6's | r8brft1hs (SHA-256 94d9dd5b...3631) | 4,913,609 / ba18170f0bf15ae7 |

## 4. UHO/SF19 diagnostic

tools/nnue/uho_diag.py run, 100,000 nodes, Threads 1, Hash 16, on ~/fork-data/uho-diag/sets; the base re-run on
f4d0fb4's default build (r8brft1, identical evaluation and search to phase-4 d63ddc6: same bench), the static
evaluation checked against the Python R-int (base and (b); (a)'s static is the binary's own, since its table is not in
the net file). Raw cp, medians.

| net | adv static | adv search | levelql static | levelql search | S trade (SF) | S qxq (SF) | F trade (game) |
|---|---|---|---|---|---|---|---|
| r8brft1 (d63ddc6 engine) | +40.0 | +50.0 | +24.0 | +17.0 | 0.08 (0.05) | 0.40 (0.40) | 0.12 (0.12) |
| (a) i180a | +47.5 | +57.0 | +21.5 | +14.5 | 0.09 (0.05) | 0.47 (0.40) | 0.13 (0.12) |
| (b) i180b | +48.0 | +57.0 | +21.0 | +13.5 | 0.09 (0.05) | 0.53 (0.40) | 0.12 (0.12) |

SF19: adv +97.5, levelql 0. **Declared reading** (proto/r3-king-a's king-inputs-design.md §5.5, before any
result): the queens-on part moves if adv static rises by more than 8 cp, with the search column the same way; the
queenless part moves if levelql static falls by more than 8 cp; adv and levelql rising together is a scale shift.
**Result: neither part moved by the rule** (adv +7.5 / +8.0, search +7 / +7; levelql -2.5 / -3.0); the
directions are the predicted ones and it is not a scale shift. Mechanically expected: the adv set is book
positions (bucket 7, factor 1.18, so +40 x 1.18 = +47), and levelql's queenless positions sit in buckets with
factors 0.85-1.0. Piece and queen trade rates stay within a few positions of the base (S qxq 0.40 -> 0.47 / 0.53 on
15 positions). Per-net JSON: ~/fork-runners/scratch-i180/uho/.

## 5. Speed

bench/ab_search.py, 10 interleaved rounds each, not pinned (Windows), with the nps lock held; the machine was at
87-93% CPU load from other jobs throughout, so the noise is high.

| run | A | B | median | best | noise threshold | verdict |
|---|---|---|---|---|---|---|
| A/A | f4d0fb4 default (unit table) | its copy | +1.9% | -1.7% | 13.2% | no significant difference |
| A/B | f4d0fb4 default (unit table) | f4d0fb4 HEAD_SCALE (fitted) | +2.8% | +12.1% | 10.7% | no significant difference |

The unit build is code-identical to phase-4 d63ddc6 (the scaled branch is an `if constexpr` discarded at compile
time; bench identical). Bench node counts differ between A and B by design, so only nps is compared. The added work
per evaluation is one bitboard test, one table load and one 64-bit multiply inside the output pass (3.4% of cycles
by speed sprint 3's profile, E1), so a cost near 0 is expected, but this measurement cannot bound it below about 10%.
**Before any STC test of (a), re-measure in a quiet window** (a part seal) or read the runners' in-situ ratio. The
fixed-node screen itself does not depend on speed. (b) needs no measurement: the same engine and the same
architecture, only the weights and S differ.

## 6. The screen (prepared, not queued)

- Script ~/fork-runners/scratch-i180/i180_screen.sh, items ~/fork-runners/scratch-i180/item-i180-fn-a.sh and
  -b.sh (bash -n clean), in the pattern of retrain 8c's screens (r8c_screen.sh, rftep.sh): sprt_run.sh's custom
  form NAME d63ddc6 TEST 0 5 6 6, 1,600 games, 800,000 nodes per move, TC 600+6 (never binds), Hash 16, Syzygy
  3-4-5; the [0, 5] LLR ignored, the stage played whole. Stage 6's openings are fresh for the fit (its STC games used
  stages 0-5, its LTC games 8-10; decision 16 of 2026-11-07). Exit 0 done, 20 not ready, else failure; results to
  ~/fork/MORNING.md's Results and ~/fork-runners/scratch-i180/screen-results.txt.
- **To queue (after 8c's promotion decision):** push exp/i180-head-scale and exp/i180-head-scale-b to origin;
  copy the item(s) into the night queue's items folder (lane B's runner worktree is set; change W for another
  lane). (a) is the owner's requested form (queen state and phase); (b) is the phase-only net edit, a second
  screen if wanted. Expected cost: one FN screen each (about 40 minutes of runners).
- **Reading:** FN + 118 log2(r) with r the speed ratio ((b): 1, the same engine; (a): section 5). The proposal's
  falsifier: kill the label version (step 3) if the screen is at or below 0 and the diagnostic did not move; the
  diagnostic did not move by its rule, so the screen decides.

## 7. Not run, caveats

- The 20,000-node fit uses 25,000 of g4c's 2.38 M games; the D20K column's flatness may be partly its
  adjudication (700 cp, 8 plies) and its balanced book, not only its budget.
- No LTC-only or depth-extrapolated factor set; no static-matched variant; no endgame or held-out checks on
  r8brft1hs (a uniform rescale of a head cannot change a result's sign, but those checks read thresholds in cp).
- The fit's games are SPRT games played by r8brft1 against itself at 2026-11-11/12 engines; the engine has
  changed since (bench 5,386,021 now); the fit is not redone on the current engine's games.
- No outside source was consulted; the nearest relatives on file are R33 (docs/research/phase4-designs/
  structure-class-calibration.md, the same after-output fixed-point multiply on structure classes) and the
  survey's F10 (material-based eval scaling, never tried by Fork).
- New names (to be screened by the coordinator before any adoption): head_scale.hpp, HeadScaleOne,
  HeadScaleTable, HeadScaleActive, scaled_head_cp, HEAD_SCALE (FORK_EXP_HEAD_SCALE), r8brft1hs, and the job names
  i180-fn-a, i180-fn-b, i180_screen.sh.
