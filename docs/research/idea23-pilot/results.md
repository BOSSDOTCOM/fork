# Idea 23, the ordering pilot: results

The pilot declared in declaration.md (committed before any result, 1f22075),
run on 2026-11-09 and 2026-11-10 (times EST). No SPRT was run; whether one
follows is the owner's decision.

## The owner's decision (2026-11-10, about 8:40 AM EST)

**A null result.** The quiet ordering formula is near-optimal for this
fitness, and the best candidate is within noise on both sets. Idea 23 is
parked; the time-management formula stays noted as the next possible target,
with no run planned (phase-4 22153a4: DESIGN.md decisions log, ideas.md 23).
No SPRT.

## Summary

- **No candidate beats the committed quiet ordering score beyond noise.** The
  best by the declared rule, #35, saves **+0.39% of the nodes [-0.39%,
  +1.19%]** on the 4,794 generation positions and **+1.43% [-0.33%, +3.18%]**
  on the 940 held-out positions: both intervals include zero, so by the
  declared reading it is not a candidate worth an SPRT decision.
- The R14-tuned combination looks locally optimal for node count: both
  calibration bodies (both weights one step down or up) need more nodes
  (-1.38% and -0.40%), and 26 of the 37 measured proposals did too.
- The harness worked as designed: 0 gate failures in 40 gate runs (the
  base, the two calibration bodies and the 37 proposals the critic passed,
  two compilers each), 0 guard refusals, the self-check exact, and the
  replay check below.
- Cost: **543,832 tokens of the 10,000,000 cap** (85 CLI calls, sonnet), 8.2
  hours of wall time at nice 19 beside data generation.

## Prerequisites (2026-11-09, evening)

- **The gate end to end on Linux** (tools/evolve/gate_e2e.py, WSL
  Ubuntu-22.04, g++ 11.4 and clang++-19 at 147b25a): every planted
  candidate stopped where expected. Region quiet_order, 14 of 14: a clean
  body passed every step with both compilers (464 s, bench 9,623,599); the
  five audit-1 U-2 escapes (a %:define digraph, a '}' that leaves the
  function, code after a "//" inside a string literal, make_unique, hidden
  static state) were refused by the static rules, and with the static rules
  switched off by later steps (the digraph at the preprocessed comparison,
  the others at the compile step); `return std::div(s.butterfly, 3).quot;`
  passes the static rules and clang++-19 and was refused by g++; a product
  of three entries was refused by the overflow static_assert. Region lmr,
  12 of 12 (its clean body passed in 384 s). The run found one harness bug,
  fixed with a test that failed first: the second compiler's `build-1/`
  folder counted as a tree difference.
- **Two-compiler gating:** every check with both compilers, their benches
  equal; tests with fakes (either compiler failing any step refuses; a
  one-compiler gate passes what two refuse, the fault injection) and with
  the real compilers (GCC 11 rejects the `std::div` body clang accepts).

## Retargeting

Region `quiet_order` (src/search/quiet_score.hpp, 147b25a, bench unchanged
10,374,064 / 677c436fa145e07f); fitness mode `nodes`, the guard, the
self-check, the logs and the replay (1f22075); declaration.md (1f22075).
During the run: the critic told the requested mode (29ce7a8, after
generation 1); replay fixes (b58b065, d64e4e8).

## The run

- **Base:** 1f22075 (phase-4 d42c248 with the refactor; R14's values). The
  base's nodes to depth 12: 818,092,953 on the generation set, 163,364,132
  on the held-out set. **Self-check:** both repeated exactly on a different
  split (3 engine processes instead of 2): 0 of 4,794 and 0 of 940
  positions differed.
- **Guard calibration:** weights one step down 77.35% equivalent (-1.377%
  [-2.384, -0.406]), one step up 78.56% (-0.399% [-1.350, +0.561]);
  threshold 75.35%.
- **Interruptions (mine, recorded in the run's events):** after generation 1
  the pilot was stopped at the generation boundary to give the critic the
  requested mode (it had rejected both explorer full replacements as "not
  requested"), resumed, then stopped again within a minute to raise the
  run's candidate cap from 40 to 48 (an interrupted request's proposal
  counts toward the cap and is asked again, so 40 would have cut
  generation 5's last request) and resumed. Candidates #12 and #13 are those
  two interrupted requests (status `interrupted`); 40 proposals went
  through the funnel, as declared: 3 rejected by the critic, 37 measured.

### Every candidate

Nodes saved against the base (positive: fewer nodes) with the 95% paired
bootstrap interval, and the equivalent share, on each set.

| # | Gen | Island | Mode | Status | Generation set | Equiv. | Held-out | Equiv. |
|---|---|---|---|---|---|---|---|---|
| 2 | 0 | calibration | | calibration | -1.377% [-2.384, -0.406] | 77.3% | | |
| 3 | 0 | calibration | | calibration | -0.399% [-1.350, +0.561] | 78.6% | | |
| 4 | 1 | bold | residual | scored | -0.701% [-1.689, +0.276] | 81.1% | +1.163% [-0.917, +3.345] | 80.2% |
| 5 | 1 | bold | residual | scored | -0.575% [-1.489, +0.374] | 79.2% | +1.294% [-0.766, +3.313] | 77.9% |
| 6 | 1 | bold | residual | scored | -0.294% [-1.118, +0.541] | 82.1% | +0.325% [-1.641, +2.345] | 82.6% |
| 7 | 1 | careful | residual | scored | -0.877% [-1.642, -0.117] | 88.2% | +0.728% [-0.916, +2.302] | 88.3% |
| 8 | 1 | careful | residual | scored | -0.183% [-0.888, +0.536] | 87.7% | +0.194% [-1.448, +1.741] | 86.6% |
| 9 | 1 | careful | residual | within noise | +0.011% [-0.005, +0.032] | 100.0% | -0.001% [-0.004, +0.000] | 100.0% |
| 10 | 1 | explorer | full | critic rejected | | | | |
| 11 | 1 | explorer | full | critic rejected | | | | |
| 12 | 2 | bold | residual | interrupted | | | | |
| 13 | 2 | bold | residual | interrupted | | | | |
| 14 | 2 | bold | residual | scored | -0.818% [-1.730, +0.104] | 80.5% | +0.256% [-1.858, +2.309] | 81.7% |
| 15 | 2 | bold | residual | scored (= #6) | -0.294% [-1.096, +0.564] | 82.1% | +0.325% [-1.652, +2.187] | 82.6% |
| 16 | 2 | bold | residual | scored | -0.612% [-1.593, +0.390] | 76.7% | -0.614% [-2.998, +1.671] | 76.7% |
| 17 | 2 | careful | residual | within noise | +0.068% [-0.478, +0.619] | 93.7% | -0.632% [-1.926, +0.565] | 95.0% |
| 18 | 2 | careful | residual | within noise | +0.223% [-0.002, +0.472] | 98.5% | -0.108% [-0.553, +0.334] | 98.2% |
| 19 | 2 | careful | residual | scored | -0.167% [-0.618, +0.260] | 95.3% | -0.146% [-1.164, +0.834] | 95.2% |
| 20 | 2 | explorer | full | scored | -0.181% [-1.236, +0.805] | 76.6% | +1.644% [-0.443, +3.686] | 76.4% |
| 21 | 2 | explorer | full | scored | -0.145% [-0.916, +0.617] | 85.7% | -0.380% [-2.104, +1.211] | 86.7% |
| 22 | 3 | bold | residual | scored | -0.957% [-1.792, -0.115] | 85.1% | +0.311% [-1.278, +1.896] | 84.8% |
| 23 | 3 | bold | residual | scored | -0.671% [-1.568, +0.130] | 83.7% | +0.416% [-1.347, +2.157] | 84.7% |
| 24 | 3 | bold | residual | scored | -2.058% [-3.052, -0.994] | 76.1% | -0.019% [-2.216, +2.075] | 76.9% |
| 25 | 3 | careful | residual | scored | -0.782% [-1.589, +0.033] | 84.0% | +0.149% [-1.573, +1.920] | 84.8% |
| 26 | 3 | careful | residual | scored | -0.911% [-1.770, -0.085] | 82.9% | -0.726% [-2.782, +1.166] | 84.9% |
| 27 | 3 | careful | residual | scored | -0.869% [-1.869, +0.128] | 76.5% | -1.341% [-3.582, +0.963] | 74.4% |
| 28 | 3 | explorer | full | scored | -1.007% [-1.888, -0.114] | 81.5% | +0.006% [-2.020, +1.897] | 82.7% |
| 29 | 3 | explorer | full | scored | -1.499% [-2.518, -0.464] | 76.1% | +0.446% [-1.934, +2.829] | 76.3% |
| 30 | 4 | bold | residual | scored | -0.850% [-1.693, +0.011] | 84.0% | +1.450% [-0.395, +3.253] | 85.0% |
| 31 | 4 | bold | residual | scored (= #8) | -0.183% [-0.937, +0.566] | 87.7% | +0.194% [-1.384, +1.800] | 86.6% |
| 32 | 4 | bold | residual | scored (= #8) | -0.183% [-0.922, +0.520] | 87.7% | +0.194% [-1.333, +1.823] | 86.6% |
| 33 | 4 | careful | residual | scored (= #8) | -0.183% [-0.940, +0.515] | 87.7% | +0.194% [-1.428, +1.850] | 86.6% |
| 34 | 4 | careful | residual | within noise | +0.131% [-0.139, +0.398] | 98.4% | -0.111% [-0.668, +0.420] | 97.8% |
| **35** | 4 | careful | residual | within noise | **+0.395% [-0.391, +1.185]** | 85.6% | **+1.430% [-0.325, +3.183]** | 86.0% |
| 36 | 4 | explorer | residual | critic rejected | | | | |
| 37 | 4 | explorer | full | within noise | +0.033% [-0.269, +0.334] | 98.3% | +0.219% [-0.417, +0.879] | 97.8% |
| 38 | 5 | bold | residual | not confirmed on the held-out set | +0.291% [+0.029, +0.571] | 97.7% | +0.257% [-0.317, +0.860] | 97.7% |
| 39 | 5 | bold | residual | within noise (= base) | +0.000% | 100.0% | +0.000% | 100.0% |
| 40 | 5 | bold | residual | not confirmed (= #38) | +0.291% [+0.030, +0.569] | 97.7% | +0.257% [-0.298, +0.836] | 97.7% |
| 41 | 5 | careful | residual | scored (= #8) | -0.183% [-0.929, +0.566] | 87.7% | +0.194% [-1.451, +1.856] | 86.6% |
| 42 | 5 | careful | residual | within noise | +0.063% [-0.312, +0.418] | 97.5% | +0.112% [-0.659, +0.899] | 96.3% |
| 43 | 5 | careful | residual | scored (= #30) | -0.850% [-1.711, +0.027] | 84.0% | +1.450% [-0.341, +3.143] | 85.0% |
| 44 | 5 | explorer | full | scored | -1.017% [-1.798, -0.203] | 86.1% | +0.259% [-1.425, +1.942] | 85.9% |
| 45 | 5 | explorer | full | within noise | +0.266% [-0.110, +0.622] | 96.7% | +0.327% [-0.520, +1.185] | 96.2% |

"= #n": the same node counts as #n on both sets (the same search; the bodies
repeat an earlier one or are equivalent rewrites of it). The intervals of
repeated bodies differ slightly because the bootstrap's seed includes the
candidate's id.

### The best candidate by the declared rule: #35

The highest generation-set reduction among the candidates that passed the
guard (proposer careful, generation 4, residual mode). Its rationale: when
the reply entry is missing (after a null move), the follow term counts 1.5
times its weight.

```cpp
  int score = s.butterfly;
  if (s.has_reply) score += s.reply * s.reply_weight / 4;
  if (s.has_follow) {
    int f = s.follow * s.follow_weight / 4;
    score += f;
    if (!s.has_reply) score += f / 2;
  }
  return score;
```

| | Generation set (4,794) | Held-out (940) |
|---|---|---|
| Base's nodes | 818,092,953 | 163,364,132 |
| #35's nodes | 814,863,406 | 161,028,384 |
| Nodes saved (95% interval) | +0.395% [-0.391%, +1.185%] | +1.430% [-0.325%, +3.183%] |
| Positions with fewer / equal / more nodes | 2,405 / 27 / 2,362 | 478 / 4 / 458 |
| Median per-position ratio | 0.99998 | 0.99990 |
| Geometric mean ratio | 0.99846 | 0.98972 |
| Equivalent to the base (guard) | 85.57% (threshold 75.35%: passed) | 85.96% |
| Bench (both compilers) | 9,655,193 | |

Per position the effect is a coin flip (as many positions gain as lose,
median ratio 1.0000); the total moves by a fraction of a percent, within the
spread of the totals over the positions. The held-out gain is larger than
the generation set's but its interval is wider and includes zero.

The only candidate whose generation-set interval lies above zero is #38
(and its repeat #40): +0.291% [+0.029%, +0.571%], 97.7% equivalent, held out
+0.257% [-0.317%, +0.860%], not confirmed. One of 40 intervals above zero at
95% is about what chance gives.

## Findings

1. **Noise floor:** at depth 12 on 4,794 positions a candidate's node total
   is uncertain to about ±0.7-1.0% (the 95% half-width, for an order change that
   moves 15-20% of the answers), and to about ±0.3% for changes that keep
   97-98% of the answers equivalent. The held-out set's 940 positions give
   intervals about 2.2 times wider. Gains of the size this region offers
   (under half a percent) are at or below what this design resolves.
2. **The equivalence guard never bound:** the threshold (75.35%) came from
   the calibration, and every candidate stayed at or above 76.1%. A change
   of move order moves about a fifth of the fixed-depth answers even for the
   tuner's neighbouring weights, so "the same best move and score" is a
   loose constraint at this depth.
3. **Repeats:** 8 of the 37 measured proposals reproduced an earlier
   search exactly (#15, #31-33, #39 = the base, #40, #41, #43; #9 is
   nearly the base). The proposers saw only the last 8 candidates, so older
   ideas came back; a dedupe on the body (or on the bench signature, which
   the gate already has) before the measurement would save about a fifth
   of the time.
4. **Sign confusion:** the analyst (after generation 3) reported that
   several rationales read a negative "node reduction" as a gain; the
   prompts would read better as "nodes saved" with an explicit sign
   convention.
5. **The critic and the explorer:** the critic rejected both generation-1
   explorer proposals because it did not know a full replacement had been
   requested; fixed after generation 1 (29ce7a8). Of the explorer's eight
   later proposals, seven reached the gate; the eighth (#36) labelled
   itself residual when asked for full.
6. **Speed:** about 11-12 minutes per candidate under the night's load (data
   generation on 10 threads), 8.2 hours in all, faster than the declared
   estimate of 14 hours.

## The replay check

- **The pilot's full replay was stopped at the owner's decision before it
  finished** (2026-11-10, about 9:00 AM EST, to free its CPU for other
  work; job evolve-pilot-replay, started 7:32 AM, `orchestrator.py
  --replay-from` with the replay plan of b58b065 and the pinned commit
  1f22075 of d64e4e8). It got through generation 0 and the first two of
  generation 1's eight requests, and was gating #6 when it stopped. **The
  5 candidates it finished all matched the log exactly**: the base, both
  calibration bodies, #4 and #5, each with the same body, status, fitness
  and answers (SHA-256 of every position's nodes, move and score) on both
  sets (the calibration bodies on the generation set, where they are
  measured). 0 mismatches. Its self-check repeated the pilot's: 818,092,953
  nodes on the 4,794 positions and 163,364,132 on the 940, the same digests,
  0 positions differing, and the guard threshold came out at the same
  75.35%. The other 40 candidates (#6-#45) were not replayed: their
  reproducibility is **unverified**.
- **The pre-pilot tiny live run's full replay** (2026-11-09: the run 10:06
  to 10:42 PM EST, its replay 10:42 to 11:17 PM; 1 generation x 2
  candidates on 300 and 100 positions, 22,091 tokens) **reproduced every
  candidate exactly**: the base, the calibration body and both proposals,
  with the same body, status, fitness and answers on both sets, and no agent
  call whose role or prompt differed from the log.
- The replay of a stopped and resumed run (the pilot's case) was tested with
  fakes (test_quiet_order.py, b58b065): every candidate equal, no prompt
  mismatch.

## Tokens and wall time

- Tokens: 543,832 of the 10,000,000 cap (input, output, cache creation and
  cache reads, as the CLI reports them), over 85 CLI calls: 42 proposals
  (two in interrupted requests), 42 critic reviews and one analyst summary.
- Wall time: 11:18 PM to 7:31 AM EST (8.2 hours, including the two
  restarts), at nice 19 with 2 build jobs and 2 engine processes.

## Unverified

- Whether any of these combinations changes playing strength: no game was
  played (no SPRT without the owner).
- The cost in speed of #35's extra branch was not measured.
- That candidates #6-#45 reproduce exactly from the log: their full replay
  was stopped by the owner before it reached them (above).
