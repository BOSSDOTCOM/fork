# Eval-trend time management: design (docs only)

Status: **design for the owner's review; nothing built, no job run.**
Written 2026-11-09, about 6:10 PM EST, on branch `research/eval-trend-tm` from
`phase-4` (cf9285a). Bench is unchanged by this document: 14,149,617 /
1cb0717f040c294d.

The owner's item (verbatim): "4. Root/time layer: alongside root-gap TM,
design time allocation that also uses iteration-to-iteration eval trend."

Summary:

- **Signal.** The root score's fall over the last two finished iterations,
  `fall = max(0, s[k-2] - s[k])` in centipawns. It is read only after a
  finished iteration at depth 8 or more, and it is 0 when either score is a
  mate or tablebase score.
- **Factor.** An extension only: `F_fall = 1000 + ScoreFallExtra *
  min(fall, ScoreFallSpan) / ScoreFallSpan` per mille. Both constants are
  placeholders until a head-to-head picks them.
- **Combined formula.** The soft limit becomes `soft * max(TimeScaleFloor,
  P_b * max(F_gap, F_fall) / 1000) / 1000`, still clamped to the hard
  limit by `scaled_soft_ms`. `P_b` is the adopted stability and node-share
  scale. `F_gap` is root-gap's factor. The two extensions take the larger
  one and never stack.
- **Evidence (Fork's own data, section 2).** X6's 18,782 iterations show
  that the *signed* trend carries information about later best-move
  changes beyond stability and share. But a nodes-as-clock replay at equal
  mean spend shows no gain over variant (b) alone for any trend form
  tried. So the likely Elo is small, and the expected test outcome is
  futility or a small pass (prediction in section 7).
- **Test plan.** Switch `UseScoreFallTime`, off by default. Two
  head-to-heads (span, then extra), then design R at STC and LTC. All of
  it runs after idea 61's items 60-62, sequentially on whatever root-gap
  decision those produce.

---

## 1. What exists today

**Phase-4 (cf9285a).** `Searcher::soft_limit_now` (src/search/searcher.cpp)
scales the planned soft limit after each finished iteration by
`soft_scale_permille` (src/search/time_budget.cpp). That is variant (b):
best-move stability plus the best move's every-pass node share, from
Fork's X6 fit, divided by the depth-only fit, times a balance of 996 per
mille, floored at `TimeScaleFloor` = 360. `scaled_soft_ms` caps the
result at the hard limit and leaves `go movetime` (soft equal to hard)
unscaled. (b) was adopted on 2026-11-08 after design R passed at STC
(+18.69 ± 7.18 Elo) and LTC (+10.23 ± 5.14 Elo) (DESIGN.md §6). The
think tank's decision (1) of 2026-11-07 kept base allocation, the time
curve and a TCEC-ratio control in Phase 5. The time-management
parameters never go into SPSA (decision 4).

**Root-gap time (idea 61 part 6).** Branch `idea61/root-gap` (c14dc82,
5700f4d), switch `UseRootGapTime`, off. The soft limit is also multiplied
by `root_gap_permille`: 1000 + `RootGapExtra` (667) when a zero-window
probe at the iteration's depth finds another root move within
`RootGapBand` (14 cp) of the best one. The probe runs only once the
unextended soft limit has passed. The constants are placeholders. Queued
tests: 60-i61-h2h-band, 61-i61-h2h-extra, 62-i61-stc.

**The score trend already exists for LMR.** `score_trend_ = clamp(score -
previous, ±ScoreTrendLimit)` (searcher.cpp, the iterative-deepening loop)
feeds the LMR context. Time management does not read it.

**The UCI clock-go test** (tests/test_uci.cpp) checks two things:
- bestmove comes no sooner than the smallest scaled soft limit;
- no iteration starts after the largest one, `widest`.

On idea61/root-gap, `widest` is multiplied by (1000 + `RootGapExtra`)
when `UseRootGapTime` is on by default.

**Concept credit.** Spending more time when the score falls is a known,
general idea. It goes back to the fail-low time extension and to "panic
time" in early programs, and several engines have tested it publicly in a
continuous form. KB `time-management.md` §4.3 on branch kb records that
lineage from commit messages, PR texts and forum posts. This design uses
the idea at concept level only. No engine's source was opened for it, and
the form, the window and every constant below come from Fork's own data or
Fork's own reasoning. The KB's list of identifiers Fork must not use
(time-management.md, end) was checked: none of the names in section 6 is
on it.

---

## 2. Evidence from Fork's own data

Scratch scripts (not committed) on two data sets, both read only:
- X6's traces (`~/fork-measure/x6/n2m`): 2,086 searches at 2M nodes from
  60 games of `s512ppr2-stc`, with 18,782 rows at depth 8 or more after
  the mate and tablebase scores are left out;
- the gauntlet and SPRT PGNs.

Every number below comes from those runs on 2026-11-09. They are in
sample, not Elo.

### 2.1 X6: the signed trend against move changes

X6 itself (DESIGN.md §5.7) used the *absolute* one-step score change and
found a partial R² of 0.001 for it. The signed change tells a different
story. Two labels are used: `y` is X6's label, "the best move changes
within the next two iterations" (base rate 0.129). `yfin` is "this
iteration's move is not the 2M-node search's final move" (base rate
0.175).

| t2 = s[k] - s[k-2] (cp) | rows | P(y) | P(yfin) |
|---|---|---|---|
| ≤ -50 | 85 | 0.200 | 0.247 |
| -50 to -20 | 450 | 0.196 | 0.236 |
| -20 to -8 | 2,105 | 0.169 | 0.231 |
| -8 to -3 | 3,197 | 0.157 | 0.201 |
| -3 to 3 | 7,154 | 0.123 | 0.165 |
| 3 to 8 | 3,129 | 0.120 | 0.163 |
| 8 to 20 | 2,087 | 0.087 | 0.141 |
| 20 to 50 | 509 | 0.057 | 0.100 |
| ≥ 50 | 66 | 0.015 | 0.045 |

**Within stability strata**, P(yfin) for a falling t2 (≤ -10) / a flat
one / a rising one (≥ 10):

| Stability | Falling | Flat | Rising |
|---|---|---|---|
| 1-2 | 0.485 (365) | 0.400 (2,244) | 0.249 (414) |
| 3-5 | 0.321 (290) | 0.267 (2,784) | 0.159 (340) |
| 6-12 | 0.170 (929) | 0.135 (6,466) | 0.081 (850) |
| 13 or more | 0.063 (349) | 0.028 (3,423) | 0.024 (328) |

The fall matters most where (b) gives the least time: a long-stable move
whose score is sliding. At stability 13 or more, P(yfin) is 2.25 times
the flat rate.

**Logistic fits.** The features are (b)'s: stability capped at 72, the
share's logit and depth capped at 19. To them are added the fall part
min(max(0, -t), 500) / 100 and, in the "both" form, the rise part as well.

| Added term | Label y: LR χ² / ΔMcFadden | Label yfin: LR χ² / ΔMcFadden |
|---|---|---|
| t1, fall only | 7.2 / 0.0005 | 6.1 / 0.0004 |
| t2, fall only (coef +1.00 per pawn) | 19.0 / 0.0013 | 14.9 / 0.0009 |
| t2, both (fall +0.44, rise -5.50 per pawn) | 159.1 / 0.0110 | 139.2 / 0.0080 |
| fall from the peak of the last 3 iterations | 16.2 / 0.0011 | 12.1 / 0.0007 |

The base model reproduces X6's (b) fit: McFadden R² 0.1425, AUC 0.771.
The fall term is significant but small. Most of the trend's information
is on the rising side: a rising score predicts a settled move. As a scale,
the two-sided t2 term adds about as much as the share term itself (X6:
partial R² 0.0077). t2 beats t1 and the peak-of-3 form in every fit.

**Odd and even depths.** The one-step change has mean +0.36 cp at even
depths and -0.39 at odd ones, with mean |t1| of 4.81 and 4.69. So there
is no odd/even swing to cancel: t2 is chosen for its information, not for
parity.

**Size of the trend at depth 8 or more:**
- |t1|: p50 3, p75 6, p90 11 cp;
- |t2|: p50 4, p75 8, p90 15 cp;
- falls (t2 < 0, 41.9% of rows): p50 5, p75 9, p90 16 cp.

**By |score|**, P(yfin) falling / flat / rising:

| \|score\| (cp) | Falling | Flat | Rising |
|---|---|---|---|
| 0-50 | 0.233 | 0.167 | 0.137 |
| 50-150 | 0.248 | 0.187 | 0.128 |
| 150-400 | 0.179 | 0.153 | 0.076 |
| above 400 | 106 rows in all | too few to read | |

### 2.2 X6: the nodes-as-clock replay

The replay uses tm_curve.py's rules: soft budget B, hard 4B, the hard
stop, the soft check, the forced-move stop at 1/8, no iteration started
once 5/3 of the elapsed passes the hard limit. Each trend rule multiplies
(b)'s scale. The question is how often the move at the stop equals the
2M-node move. The replay was checked first: (b) alone gives 0.8202 at
100k nodes, the same as tm_curve.py's 0.8202.

- **At equal mean spend** (each rule rebalanced by bisection against (b)
  alone), every rule tried moves agreement by -0.0048 to +0.0024. One
  search is 0.0005. The rules tried:
  - falling-only on t2 and on the peak of 3, at 0.5, 1 and 2 per pawn;
  - the same on |t|;
  - rising-only and two-sided forms.

  For comparison, (b) over plain gained +0.012 at 100k, +0.020 at 250k and
  +0.040 at 500k (tm_curve.py, X6's run).
- **Unbalanced** (the proposed form, section 3), at span 16 and extra 667:
  - spend ×1.060 / ×1.054 / ×1.049 at 100k / 250k / 500k;
  - agreement +0.0034 / +0.0010 / +0.0067.
- **The control:** (b) with its balance raised uniformly, with no trend:
  - at ×1.06: spend ×1.047 / ×1.047 / ×1.034, agreement +0.0034 / -0.0005
    / +0.0034;
  - at ×1.09: spend ×1.070 / ×1.066 / ×1.055, agreement +0.0067 / +0.0000
    / +0.0048.

**Reading.** On this proxy, a fall extension buys about what the same
extra time spread evenly buys. The proxy has two blind spots:
- it scores every disagreement alike, while the case for falling-eval
  time is the *cost* of an error in a deteriorating position;
- in a game, the time comes from later moves, not from other searches in
  the sample.

Only games measure those, hence the head-to-head and SPRT plan. The proxy
does justify modest expectations (section 7). It also argues against the
two-sided form as the first try: its information is real, but at equal
spend it bought nothing here either.

### 2.3 Games: eval drops and time use

The data are the per-move comments `{eval/depth time}` of Fork's moves.
A drop is Fork's eval at this move minus its eval at its previous move,
taken only when |previous eval| ≤ 300 cp. The time ratio is this move's
time over the mean of up to six neighbouring Fork moves.

| Games | Drops ≤ -20 per move: win / draw / loss | Time ratio at -50 to -20 | Time ratio at -5 to 5 | Time ratio at +20 to +50 |
|---|---|---|---|---|
| Gauntlet run-42538371594, 10+0.1, (b) on, 1,400 games | 0.035 / 0.041 / 0.155 | 1.311 | 1.036 | 1.111 |
| tm-r8-ltc 40+0.4, "test" ((b) on), 4,992 games | 0.019 / 0.021 / 0.119 | 1.306 | 1.016 | 1.438 |
| tm-r8-ltc 40+0.4, "base" (off) | 0.019 / 0.021 / 0.119 | 1.099 | 1.003 | 1.037 |
| tm-r8-stc 8+0.08, "test" ((b) on), 3,200 games | 0.028 / 0.031 / 0.133 | 1.287 | 1.007 | 1.312 |
| tm-r8-stc 8+0.08, "base" (off) | 0.028 / 0.031 / 0.132 | 1.086 | 1.003 | 1.033 |

Ratios are means; the medians run lower.

- **(b) already spends more on moves whose eval moved, in both
  directions.** At LTC it spends more on rises (+20 to +50: 1.438) than on
  falls (-50 to -20: 1.306). Moves that change the score usually change
  the move, and (b) sees the change. A two-sided trend cut would work
  against that, so the first try is fall-only.
- **Abrupt collapses are rare.** Lost games in which Fork's eval went from
  -50 or better to -150 or worse in one of its moves:

  | Corpus | Collapses / lost games | Median time ratio of the move before, (b) on | Same, off |
  |---|---|---|---|
  | Gauntlet | 18 / 350 | 0.566 | |
  | LTC | 20 / 1,142 | 0.509 | 0.896 (11 / 1,289) |
  | STC | 23 / 761 | 0.597 | 0.814 (23 / 933) |

  So the move just before the collapse was played fast under (b), and
  faster than under off. The counts are small; the pattern is
  **UNVERIFIED**. Where it holds, it is a stable move with a sliding
  score, the case this design extends. The collapse move itself already
  got more time (median 1.35 gauntlet, 0.83 LTC, 1.21 STC).
- **Gradual losses are rarer still.** Few lost games fall from 0 or better
  to -150 or worse over 2-4 of Fork's moves with no single step of 150
  (gauntlet 1, LTC test 1, STC test 14). Most losses decline more slowly
  than any window here.

The turning points in these games (where a game was lost and what Fork
saw) are being analysed by another agent on branch
`research/conversion-defense`. Its results were not available at this
writing (the branch had no commits beyond phase-4), and this design does
not duplicate them. Its findings should be read before the first
head-to-head is queued.

---

## 3. The design

### 3.1 Measuring the trend

- **Which iterations.** Finished iterations only. The score `s[k]` is the
  iteration's resolved score (`result.score`), after the aspiration loop
  has settled any fail low or fail high. An unfinished iteration is never
  read; the soft check never runs there anyway (decision (1)).
- **Window and smoothing.** The window is two iterations:
  `t2 = s[k] - s[k-2]`, which equals the sum of the last two one-step
  changes. The two-iteration difference is the only smoothing.
  - It is preferred to t1 and to the fall from the peak of the last three
    iterations because it carries the most information in every X6 fit
    (section 2.1).
  - It needs no new constant beyond its length.
  - An exponential average was not tried: it adds a decay constant, and X6
    gives no sign that more than two iterations help.
- **Units.** Centipawns of the root score, as the search reports it. The
  fall is `max(0, -t2)`; a rise counts as 0 (fall-only, section 2.2-2.3).
- **Where.** From depth `TimeScaleMinDepth` (8), the existing gate. There,
  `s[k-2]` is the depth-6 score or deeper.
- **Mate and tablebase scores.** If `s[k]` or `s[k-2]` is a mate or
  tablebase score (`is_tb_or_mate`), the fall is 0. Differences between
  those bands are distances in plies, not evaluations. This follows the
  stability scale and root gap, and it heeds the KB pitfall (a mate-score
  fix was once needed elsewhere). (b) already returns 1000 at a mate or
  tablebase `s[k]`.
- **Large |score|.** There is no gate in the first try. X6 shows the
  effect up to 400 cp and has too few rows above. Expected-score units
  (section 3.6) would gate it naturally and are a try-2 option.

### 3.2 The factor

```
F_fall = 1000                                                    below depth 8, or fall = 0
F_fall = 1000 + ScoreFallExtra * min(fall, ScoreFallSpan) / ScoreFallSpan   otherwise
```

Integer arithmetic. The factor is non-decreasing in the fall, equals 1000
at no fall and 1000 + `ScoreFallExtra` from `ScoreFallSpan` on, and is
never below 1000. It only extends. The linear ramp up to the span is the
simplest monotone shape. The X6 fit (section 2.1) gives the logit a linear
fall term, and the replay cannot tell shapes apart.

### 3.3 One combined formula

After each finished iteration of a timed search:

```
P_b   = soft_scale_permille(variant, signals)    // (b): [360, about 10,900]; 1000 for Off, below depth 8, mate/TB
F_gap = root_gap_permille(...)                    // {1000, 1000 + RootGapExtra}; 1000 when UseRootGapTime is off
F_fall= score_fall_permille(depth, fall)          // [1000, 1000 + ScoreFallExtra]; 1000 when UseScoreFallTime is off
E     = max(F_gap, F_fall)                        // the extensions do not stack (3.4)
permille   = max(TimeScaleFloor, (P_b * E + 500) / 1000)
soft_now   = scaled_soft_ms(soft_ms, hard_ms, permille)     // <= hard_ms, >= 1; soft == hard: unchanged
```

The upper bound on P_b is (b)'s scale at stability 1 and the smallest
share: 2.48 at depth 8 rising to 10.89 at depth 19. These figures are
computed from the Q16 coefficients with balance 0.996, before the floor.

**Bounds, and why the invariants hold:**

- **The hard limit.** `scaled_soft_ms` clamps to `hard_ms` whatever the
  permille, and the hard-limit poll and the iteration rule (no iteration
  started once 5/3 of the elapsed time passes the hard limit) are
  untouched. With P_b at most about 10,900 and E at most 2,334 (if
  `ScoreFallExtra` were at its range's top of 1,334), the product fits in
  `int` many times over.
- **The clock-go test's lower bound.** E ≥ 1000, so the permille is never
  below P_b (or the floor). The smallest scaled soft limit is unchanged,
  and the test's `narrowest` needs no change.
- **The clock-go test's upper bound.** `widest` is multiplied by the
  largest extension the defaults allow:
  - (1000 + `ScoreFallExtra`) when `UseScoreFallTime` defaults to on;
  - (1000 + `RootGapExtra`) when `UseRootGapTime` does;
  - the larger of the two when both do (because of the max).

  With both off by default, the test is unchanged.
- **The floor.** It is kept explicitly so that a future cut (try 2,
  section 3.6) cannot pass below it.

**Where the trend can act at all.** On X6's rows:
- 5.1% have (b)'s scale at 2.4 or more, where the iteration rule ends the
  search before any further factor matters;
- 24.4% sit at the floor (0.36);
- 43.5% of the falling rows have (b) at 0.6 or less.

So in practice the fall factor acts mostly on stable moves. That is the
niche section 2.1 points to, and the main reason it overlaps little with
(b).

### 3.4 Interactions and double counting

- **With (b).** X6's fit (section 2.1) shows the fall is significant
  *given* stability and share, so a separate factor is not pure double
  counting. The overlap is limited in two ways:
  - when the best move has just changed, (b) is already large and the
    hard limit and the iteration rule cap the product;
  - when the move is stable, (b) is small, and the fall factor restores
    part of the time.

  Multiplying is the plain choice. A logit-space form (the fall term
  inside (b)'s fit) would shrink the trend's effect where (b) is large.
  It would need (b)'s fit, depth normaliser and balance refitted. The
  replay gives no reason to expect it to do better, and an adopted
  feature would have to change, so it is not the first try (section 3.6).
- **With root gap.** Both are "the decision is in doubt" signals, and
  they often fire together: when the best move's score falls, the
  alternatives come closer. Hence `E = max(F_gap, F_fall)`, never the
  product, and a double extension is impossible. Root gap's probe needs
  one extra condition: it runs only if `root_gap_permille(..., true) >
  F_fall`, that is, only if a close move would extend further than the
  fall already does. At the placeholders (667 and 667), a full fall makes
  the probe unnecessary, which saves its nodes. How often both fire is
  not known. The node-clock check (section 4) counts it.
- **With the forced-move stop.** Unchanged: a single root move still stops
  at 1/8 of the *planned* soft limit, whatever the scale.
- **With the LMR context.** `score_trend_` is read and never written by
  this design. The fall comes from the loop's own scores, so idea 61's LMR
  uses are unaffected.

### 3.5 Short searches and special cases

- **Very short searches.** Below depth 8 the factor is 1000. A search that
  never reaches depth 8 is untouched, as with (b) and root gap. At a 300 ms
  clock, depth 8 is reached early, so the factor applies there too.
  Whether a fall at depth 8-9 at such a clock is noise is **UNVERIFIED**;
  the node-clock check's 300 ms condition reports it.
- **`go movetime`.** soft equals hard, so `scaled_soft_ms` returns the soft
  limit unchanged. There is no effect.
- **Pondering, `go infinite`, depth, node and mate limits, bench, data
  generation.** There is no soft check, or `soft_ms` is -1, so there is no
  effect. **Bench is unchanged, and the labeller is untouched** (data
  generation is node-limited).
- **Low clock.** When the reserve caps the hard limit, the hard limit and
  the iteration rule bind first. The factor can only move the soft limit
  towards the hard one.
- **Endgame tables at the root and `searchmoves`.** The root moves are
  narrowed before the loop. The score trend is the trend of the narrowed
  search, so nothing changes. A tablebase root score is excluded anyway.
- **Threads (Phase 6).** Only the main thread's loop reads it, as with (b).

### 3.6 Alternatives and try-2 candidates

The project allows at most two tries per idea. The second try, if needed,
picks one of the following.

1. **Two-sided** (`ScoreRiseCut`): less time on a rising t2, with the cut
   derived so that the mean spend equals (b)'s on the X6 replay (the rise
   side pays for the fall side). X6 says the rising side carries the most
   information (section 2.1), but at equal spend it bought nothing in the
   replay, and (b) deliberately spends on rising moves in games
   (section 2.3). The KB's pitfall also applies: a time cut on rising
   scores was removed elsewhere as harmful to winning attacks.
2. **Cross-move reference:** the fall against the previous search's final
   score (two plies earlier, same side), kept in the Searcher across `go`
   commands and reset by `ucinewgame`. This is the classic form, but it is
   not "iteration-to-iteration" as the owner's item asks.
3. **Expected-score units:** fall measured as 1000·(σ(s[k-2]/S) −
   σ(s[k]/S)) per mille, with S the network's cp-per-logit scale (think
   tank I9). S is 89 for S512ppr3 in docs/nets.md. Whether the search's
   cp equals the trainer's scale units is **UNVERIFIED**. This damps falls
   at large |score|. σ can be computed in Fork's existing fixed point
   (`fixed_exp2_neg`). It needs a constant tied to the network, which goes
   stale at each promotion.
4. **Logit form:** the fall inside (b)'s fit, refitted with the depth
   normaliser and balance. The coefficient would be about +1.0 logit per
   pawn on X6, so a 16 cp fall gives about ×1.17 at a small change
   chance.

---

## 4. Cost in code (later; nothing is built here)

The design is about half of root-gap's size, because there is no probe.
Root-gap was about 75 lines in searcher.cpp, 10 in time_budget.cpp and 172
in tests. The work would build on root-gap's branch if root gap is adopted,
and on phase-4 if not (section 5.4).

| File | Change |
|---|---|
| src/search/time_budget.hpp/.cpp | `IterationSignals` gains `int score_fall = 0;` (appended, so existing aggregate initialisers still compile). New `int score_fall_permille(int depth, int fall)`. The header comment states the invariants of section 3.2. |
| src/search/searcher.hpp | Switch `X(use_score_fall_time, UseScoreFallTime, false)`, with its paragraph in the switch comment. The `soft_limit_now` comment names the combination. |
| src/search/searcher.cpp | In the loop, keep the score two iterations back (a local, `score_before_previous`) and set `time_signals_.score_fall` (0 at a mate or tablebase score, or before depth 3). In `soft_limit_now`, compute `E = max(F_gap, F_fall)` and the floor as in section 3.3. In root gap's block, add the one probe condition (section 3.4). |
| src/tune/params.hpp | `ScoreFallSpan` 16 (range 4-64, step 1) and `ScoreFallExtra` 667 (range 333-1334, step 50), as root gap's entries. They are in the table for the tuning build's options and the head-to-head commits, never for SPSA (decision 4). |
| tests/test_search.cpp | See below. |
| tests/test_uci.cpp | The clock-go upper bound multiplies by the largest default extension (section 3.3). Checked with the default flipped, as root gap's was. |
| docs | DESIGN.md §5.6 paragraph and Search constants rows, ideas.md entry, ORIGINALITY.md row (concept credit, name and constant screens). |

**Tests in tests/test_search.cpp:**

1. **`score_fall_permille` itself:**
   - 1000 below depth 8 and at fall 0;
   - non-decreasing in the fall;
   - exactly 1000 + `ScoreFallExtra` at and beyond the span;
   - never below 1000.
2. **The signal:**
   - on a search with a listener, `time_signals().score_fall` equals
     max(0, s[k-2] − s[k]), recomputed from the listener's own
     per-iteration reports (an independent oracle);
   - it is 0 when either score is a mate score (a mate-in-N position).
3. **The soft check:** with a listener that advances the clock past the
   unextended soft limit after an iteration with a fall, the switch on
   starts another iteration and the switch off stops. This mirrors root
   gap's clock tests.
4. **The combination:** when both root gap and the fall fire, `last_soft_ms`
   equals the soft limit × P_b × max(...) and not the product.
5. **Defaults:** `SearchSwitches{}.use_score_fall_time` is false, and the
   other time tests pin it off.
6. **Fault injection** (testing rules): replacing max with a product, or
   dropping the mate guard, must fail a test, and the failure is shown
   once.

**Checks before any game:**
- `fork bench` is unchanged (bench has no soft limit).
- The node-clock check (`FORK_NODE_CLOCK`): the 46 bench positions under
  §5.6 step 10's five conditions, 230 searches.
  - With the switch off, the output must be identical to the base commit.
  - With it on, report how many searches went deeper, the spend rise per
    condition, how often the fall and root-gap factors fired together, and
    the root-gap probes saved.
- The full check (CI) on the pushed commit.

---

## 5. Test plan

Conventions: switch off by default; constants by head-to-head (decision
3); design R for the SPRT (decision 2: [0, 6] nElo, alpha 0.05, beta
0.20, cap 8 stages, futility after stage 2); STC 8+0.08, then LTC 40+0.4,
because time management is on the LTC list and the owner's 2026-11-08 rule
adopts TM only after LTC passes; never SPSA. TCEC conditions
(config/tcec.json: 1800+3 in the Swiss) are not tested here; the
TCEC-ratio control stays in Phase 5.

### 5.1 Selection (head-to-head, tools/github/h2h_run.sh)

1. **`ScoreFallSpan`: 8, 16, 32** (round robin, `--prefer 16`, "the
   placeholder: X6's p90 fall"), at `ScoreFallExtra` 667. The candidates
   halve and double the p90, as root gap's band candidates did.
2. **`ScoreFallExtra`: 333, 667, 1000** (round robin, `--prefer 667`, "one
   iteration at growth 5/3"), at the span picked in step 1.

Each candidate is one commit on the implementation commit that switches
`UseScoreFallTime` on and sets the two values. Stages per pairing:
**UNVERIFIED** (root gap's are set in its queue items; use the same `--stages`).

### 5.2 SPRT

3. **The winner against off, design R at STC.** The off side is the
   implementation commit itself, with the switch off. Fresh openings
   (`--origin` past the head-to-head's stages, as h2h_run.sh prints).
4. **If H1: design R at LTC 40+0.4** (Hash as tm-r8-ltc's 64), then
   adoption by the owner.
5. **If STC stops for futility or H0:** try 1 is spent. Try 2, if the
   owner wants it, is one form from section 3.6. The recommended one is
   expected-score units if the losses cluster at large |score|, otherwise
   the logit form. If that fails too, the idea is retired (two tries).

### 5.3 Where it queues

After idea 61's items 60 (60-i61-h2h-band), 61 (61-i61-h2h-extra) and 62
(62-i61-stc), and after any root-gap LTC the owner adds under the TM rule.
Its items take the next free queue numbers. Suggested names:
`fall-h2h-span`, `fall-h2h-extra`, `fall-stc`, `fall-ltc`.

The reasons for queuing after root gap:
- the combination rule and the off side depend on root gap's outcome;
- both tests share the soft-check block;
- one heavy job at a time.

### 5.4 Separating its effect from root gap's

**Sequential, the default.**
- If root gap is adopted, the fall feature is built on root gap's
  adopted commit. Both sides of every fall test then have
  `UseRootGapTime` on, and the measured effect is the fall factor's
  *marginal* effect given root gap, with the max rule in place.
- If root gap is not adopted, the fall feature is built on phase-4,
  where `E = F_fall`.

Either way, each feature's adoption rests on its own SPRT against the
baseline at that time. That is the project's standard, and it is the
cheapest route.

**Factorial, optional.** This applies if the owner wants the interaction
estimated, for example because both pass and the max rule is in
question. A 2×2 at STC: {off, root gap, fall, both}, through the factorial
screen's per-shard options (decision 5). Whether that tool runs today, and
its cost in stages, is **UNVERIFIED**. The cheap partial alternative is
one more design R SPRT of "both, with product" against "both, with max".
That is only worth running if the node-clock check shows the two factors
firing together often.

### 5.5 Kill criteria

- The node-clock check shows the switch-off output differing from the base
  commit (a bug: fix it before any game).
- With the switch on, the spend rises by more than root gap's largest
  condition (18.3% at 60+0.6; DESIGN.md §5.6). If so, the span or extra is
  too aggressive and the candidate set is revisited before the
  head-to-head.
- Design R: futility after stage 2 or H0 at STC ends try 1, as does H0 at
  LTC.

---

## 6. New names and constants (to be screened later; not screened here)

The originality screens (names against Stockfish, Ethereal, Berserk and
Weiss, match / no match; constants by the originality-checker) run before
any of these are used. This design does not screen them.

**New names:**

| Name | Kind | Note |
|---|---|---|
| `use_score_fall_time` | switch member | |
| `UseScoreFallTime` | UCI option | |
| `score_fall_permille` | function (time_budget) | |
| `score_fall` | `IterationSignals` member | |
| `ScoreFallSpan` | constant (params.hpp) | |
| `ScoreFallExtra` | constant (params.hpp) | |
| `score_before_previous` | local in `Searcher::deliberate` | |
| `ScoreFallListener` | test listener (tests/test_search.cpp) | |
| `ScoreRiseCut` | try 2 only (two-sided) | screen only if used |
| `last_search_score_` | try 2 only (cross-move) | screen only if used |

**Constants:**

| Constant | Value | Status and justification |
|---|---|---|
| `ScoreFallSpan` | 16 cp | **Placeholder, to be chosen by head-to-head** (8, 16, 32; range 4-64, step 1). X6's p90 of the two-iteration falls at depth 8 or more (t2 < 0, 7,875 rows: p50 5, p75 9, p90 16 cp, 2026-11-09): a fall larger than nine in ten gets the full extension. |
| `ScoreFallExtra` | 667 per mille | **Placeholder, to be chosen by head-to-head** (333, 667, 1000; range 333-1334, step 50). One more iteration at Fork's measured iteration growth 5/3 (DESIGN.md, row "Iteration growth"), the same derivation and value as `RootGapExtra`. Root gap's screen found 667 to be a value-only near match with an unrelated clamp elsewhere (kept); it is re-screened in this role. |
| Window | 2 finished iterations | Structural. t2 carries more information than t1 or the fall from the peak of 3 in every X6 fit (section 2.1). No odd/even effect was found. |
| Depth gate | 8 (`TimeScaleMinDepth`, reused) | X6's primary depth; there are no fit rows below it. |
| Mate/TB exclusion | `is_tb_or_mate` (reused) | As (b) and root gap. |
| Floor | 360 (`TimeScaleFloor`, reused) | Unchanged. Kept explicit in the formula for a future cut. |
| Combination | max of the extensions | Reasoning (section 3.4): no stacking of two doubt signals. |

---

## 7. Prediction, recorded before any game

The proxy (section 2.2) shows no gain at equal spend. Unbalanced, the
proposed form's agreement gain matches a uniform increase in spend. For
comparison, (b)'s proxy gain over plain (+0.012 to +0.040) came with +18.69
Elo at STC.

The KB records other engines' score-trend and score-drop terms at +1.2 to
+6.2 at STC and +2.6 to +4.3 at longer controls, on top of their other time-management terms
(time-management.md §4.3). In one engine the gain grew with the time
control.

**Prediction:** 0 to +4 Elo at STC, and LTC at least STC within error.
The most likely design R outcome at STC is futility after stage 2 or a
narrow pass. Design R loses about a third of +3 nElo features early
(decision 2), so a futility stop here does not refute a small LTC gain.

The owner may prefer to:
- **skip STC and test at LTC directly** (the falling-eval gains elsewhere
  grew with the time control), or
- **give the stages to other items.**

That is a decision for the owner. The plan above follows the standard
order.

---

## 8. UNVERIFIED and open items

1. The game-level pattern "the move before a collapse is played fast
   under (b)" rests on 18-23 collapses per corpus.
2. Whether a fall at depth 8-9 under a very short clock is noise.
3. How often root gap and the fall fire together. The node-clock check
   counts it.
4. The stages per head-to-head pairing: use root gap's.
5. The factorial screen tool's readiness and cost.
6. Whether the search's centipawns equal the trainer's sigmoid units
   (S = 89), which matters for try 2's expected-score form.
7. The Elo prediction (section 7) is a judgement from the proxy and the
   KB's records, not a measurement.
8. The research/conversion-defense findings were not available. They may
   change the case for this design (for example, if losses come mostly
   from collapses, not from slides).
