# Transfer and testing: self-play gains against anchors, an anchor check, and fixed-node screens first

Analysis of 2026-11-09, about 5:45-6:20 PM EST, for the owner's review (items 1, 5 and 6 of the
big-picture follow-ups). Docs only; nothing adopted, no jobs started (GitHub artifacts downloaded and Ordo
run in WSL for about a minute). Result files beside this report: `gauntlet-gain.json`, `sprt-sum.json`,
`nps-insitu.json`, `fn-stc.json`, `power.json`. The scripts (standard-library Python: gauntlet_gain.py,
ordo_like.py, make_ordo_inputs.py, sprt_sum.py, nps_insitu.py, fn_stc.py, power.py) stayed in the session's
scratch folder.

The owner's items (verbatim):

> 1. Trend check: from the SPRT log and gauntlets, estimate the self-play-to-anchor transfer rate since
>    S512r2 (SPRT gains vs shared-anchor gauntlet gains), with uncertainty.
> 5. External check: design a short anchor match (Clover/Altair) as a confirmation step for major
>    adoptions, if the transfer rate in (1) shows a meaningful gap.
> 6. Testing policy: propose making speed-adjusted fixed-node screens the default first filter, with
>    offline metrics as diagnostics only.

## Summary

- **Transfer ratio since S512r2: 0.65, 95% interval 0.36-0.99** (bootstrap; delta method 0.35-0.96).
  Self-play sum +84.6 ± 15.3 Elo against a shared-anchor gain of +55.4 (paired SD 12.2). Every accounting
  puts the ratio below 1 (0.65-0.76; P(ratio < 1) 0.93-0.98); the gap is -29 ± 14.5 Elo (1 SE), meaningful
  in size but only marginal statistically (1.45-2.0 SE), and no single adoption can be resolved.
- **Anchor check:** a light step, not a check after every adoption: level 0 (no games: paired gain and a
  running transfer ratio in every gauntlet report) and level 1 (a 1,600-game paired OLD/NEW match against
  Clover 6.1 and Altair 7.0.0, for major adoptions only, about one STC stage of runner time).
- **Fixed-node screens first:** with the speed ratio measured in each screen's own games, the
  speed-adjusted screen predicted the STC sign and the SPRT verdict for 9 of 9 network pairs (leave one
  out); the raw "fixed nodes above 0" rule got 3 of 9; validation loss agreed with the STC sign in 4 of 7.
  The refit price is 1.72 Elo per 1% nps (1.56-1.88), above the adopted 1.5.
- **Doc correction:** the gauntlet plays openings 1-100 against each anchor (both colours), not 200; only
  the Stockfish reference uses all 200.

## 1. Trend check

### 1.1 Anchor side

Three gauntlets, compared on the six anchors they share (Weiss, Monolith, Winter, Laser, Marvin, Altair):

| Run | Commit | Date (EST) | Ordo, as published | Ordo, shared anchors |
|---|---|---|---|---|
| 41465146207 | 3902d00 | Nov 2, 9:46-10:10 AM | 3445.8 ± 21.6 | 3445.8 |
| 42392526865 | a24d41f | Nov 7, 11:41 AM-12:04 PM | 3488.2 ± 22.2 | 3488.2 |
| 42538371594 | 32c5517 | Nov 8, from 7:06 PM | 3488.2 ± 20.4 | 3501.2 (Clover removed) |

Conditions in every run: 100 openings per anchor, each with both colours (openings 1-100); 10+0.1, one
thread, Hash 16; no Syzygy for Fork and no adjudication. The runner CPU mix differs between runs.

Gains by model (A = 3902d00 to a24d41f, B = a24d41f to 32c5517):

| Gain | Ordo per run | Ordo joint | Plain logistic | Three-outcome fit | Paired SD | Unpaired SD |
|---|---|---|---|---|---|---|
| A | 42.4 | 40.8 | 38.0 | 41.9 | 10.5 | 15.5 |
| B | 13.0 | 15.1 | 13.9 | 17.5 | 11.0 | 17.3 |
| A+B | 55.4 | 55.9 | 52.0 | 59.4 | 12.2 | 16.5 |

- Per-anchor A+B gains (Elo): Weiss +90, Monolith +33, Winter +38, Laser +48, Marvin +39, Altair +55.
- Pair scores on the same opening correlate 0.26-0.37 between runs (Marvin about 0, Weiss and Monolith
  0.5-0.6), so pairing by opening matters: the paired bootstrap over openings gives SDs of 10.5 / 11.0 /
  12.2, and the delta method agrees.
- Variance from the runner hardware mix between runs is not in the bootstrap; its size is UNVERIFIED.

### 1.2 Self-play side

Changes adopted between 3902d00 and 32c5517 (the engine diff checked file by file; 3902d00 has the same
engine source as 684bac6):

| Change | Test | Self-play Elo (95%) | Segment |
|---|---|---|---|
| S512+PP | STC [0, 5], run 42294907752 | +32.67 ± 10.48 | A |
| select_best in a register (5ba7d0d) | **no SPRT** (412b13f lacks it; both sides of the S512ppr2 SPRT have it); +4.0% local nps | +6.0 (5.0-7.2), priced at 1.5 Elo per 1% | A |
| S512ppr2 | STC [0, 5] | +20.11 ± 7.22 | A |
| S512ppr3 | STC [0, 5], 8,000 games | +7.12 ± 4.53 | B |
| Time management (b) | STC design R | +18.69 ± 7.18 | B |
| Time management (b), LTC (sensitivity only) | LTC design R | +10.23 ± 5.14 | - |

- Sum: **+84.6 ± 15.3 Elo** (95%); +78.6 without select_best. Elo per nElo is 0.59-0.61 in every test,
  so all comparisons use logistic Elo.
- **Selection bias (winner's curse), simulated per test design:** stages of 800 pairs, nElo standard error
  8.686 per stage, LLR = (e1 - e0) / s^2 · (x - (e0 + e1) / 2); the model reproduces every logged LLR.
  Bias-adjusted values 31.8 / 19.6 / 6.2 / 17.9 against the observed 32.67 / 20.11 / 7.12 / 18.69, about
  3 Elo in total. P(H1) at the adjusted value is 0.98-1.0; a null that passes reports about +8.8 nElo
  (quoted from the think tank, not re-derived). Not modelled: the screen-then-SPRT selection, where screen
  and SPRT shared stage-0 openings.

### 1.3 The ratio

| Accounting | SPRT sum | Anchor gain | Ratio | 95% bootstrap | 95% delta | P(ratio < 1) | Gap ± 1 SE |
|---|---|---|---|---|---|---|---|
| Main | 84.6 ± 7.8 (SE) | 55.4 ± 12.2 | **0.65** | 0.36-0.99 | 0.35-0.96 | 0.98 | -29.2 ± 14.5 |
| No select_best | 78.6 | 55.4 | 0.70 | 0.38-1.06 | - | 0.95 | -23.2 |
| TM at its LTC value | 76.1 | 55.4 | 0.73 | 0.39-1.10 | - | 0.93 | -20.7 |
| Selection-adjusted | 81.5 | 55.4 | 0.68 | 0.37-1.02 | - | 0.97 | -26.1 |
| Segment A | 58.8 | 42.4 | 0.72 | 0.36-1.15 | - | - | - |
| Segment B | 25.8 | 13.0 | 0.50 | -0.34-1.46 | - | - | - |

The bootstrap interval combines a bootstrap of the gauntlets over openings with a normal draw for the SPRT
sum. The decisions log's earlier 0.80 for segment A (nets only) agrees with this.

**Verdict:** the gap is meaningful in size: about a quarter to a third of the self-play gain does not show
against the anchors, and every accounting puts the ratio below 1. Statistically it is marginal (1.45-2.0
SE), and no single adoption can be resolved (segment B alone: 0.50, -0.34 to 1.46).

**Likely causes, none measured:** the UHO opening book of the SPRTs against the gauntlet's balanced
openings; Syzygy tables and adjudication in the SPRTs but not in the gauntlet; self-play inflation.
Time management's gain at 10+0.1 is about +17.5 by interpolation (UNVERIFIED).

**Which conditions matter for TCEC (owner's note, 2026-11-09).** The SPRTs' conditions resemble TCEC's
more closely than the gauntlet's: TCEC plays from unbalanced, curated openings with tablebases available,
as the SPRTs do (UHO openings, Syzygy 3-4-5, adjudication), while the gauntlet plays random balanced 8-ply
openings without tables. A ratio below 1 therefore does not by itself mean the self-play gains are
inflated for TCEC: part of the gap may be gains that show under TCEC-like conditions and not under the
gauntlet's. The anchor check (§5) guards against self-play inflation; it does not replace the SPRTs as the
measure of TCEC strength.

## 5. Anchor check (recommendation)

The gap justifies a light step, not a check after every adoption.

- **Level 0, no extra games:** every gauntlet report shows its paired-by-opening gain over the previous
  gauntlet on the shared anchors (SD about 11 Elo) and the running transfer ratio. A `report.py` change,
  built on 2026-11-09 (below, "Built: how to run").
- **Level 1, major adoptions only:** a paired match of OLD and NEW Fork, each against Clover 6.1 and Altair
  7.0.0 on the same 200 openings.
  - **Major:** a claimed STC gain of +30 Elo or more, a new architecture, a time-management change, or
    unconfirmed adoptions summing to +40 or more.
  - **Format:** 1,600 games at 10+0.1, each shard playing both Fork versions; a fixed sample, no
    sequential stop.
  - **Cost:** about 25 minutes of wall time and about 5.3 runner-hours, roughly one STC stage.
  - **Precision:** SE 9.2 Elo in the model, realistically about 10.5; power 0.70 for a true +20 Elo gain
    against anchors, 0.49 for +15, 0.95 for +30. Below a claim of about +25 it is not worth the runner
    time.
  - **Outcomes:** confirmed (lower 95% bound above 0), consistent, or flagged for the owner's review. It
    never reverts anything.
  - **Slot:** after adoption and the labeller switch, at the next idle slot. It needs a two-engine mode in
    `gauntlet.yml`, built on 2026-11-09 (below).

Power by design:

| Design | Games | SE (Elo) | Power at +10 / +15 / +20 / +30 |
|---|---|---|---|
| Clover + Altair, 100 openings | 800 | 13.1 | 0.19 / 0.31 / 0.46 / 0.74 |
| **Clover + Altair, 200 openings** | **1,600** | **9.2** | 0.29 / 0.49 / 0.70 / 0.95 |
| Clover + Altair + Marvin, 200 openings | 2,400 | 7.7 | 0.36 / 0.62 / 0.83 / 0.99 |
| All seven anchors, 100 openings | 2,800 | 8.7 | 0.31 / 0.54 / 0.75 / 0.97 |

The model SE reads about 10-15% low against the observed run-to-run differences. Per-anchor SE for 100
openings (Elo): Clover 21.0, Altair 16.6, Marvin 19.8, Laser 21.0, Winter 29.6, Monolith 37.6, Weiss 35.4
(Clover's pair-score correlation from one run; 0.15 assumed). Cost basis: a 100-game shard took 16-20
minutes (Altair 18.5-20, Clover 17.5-19.5); builds 1-5 minutes; the 2026-11-08 gauntlet of 18 shards about
26 minutes.

**Optional checks of the causes:** one gauntlet rerun with Syzygy for Fork; one network SPRT replayed on
the gauntlet's balanced openings.

### Built: how to run

Built on 2026-11-09 (owner's decision of that day, item 5; branch `gauntlet/anchor-check`). Usage is also
in the docstrings of `tools/gauntlet/report.py` and `.github/workflows/gauntlet.yml`.

- **Method, both levels:** openings are identified by the game's FEN header; only (anchor, opening) cells
  that both sides played count. The gain is the difference of two plain logistic fits of Fork's rating
  with the anchors fixed at their CCRL Blitz ratings. This is the "plain logistic" column of §1.1, on the
  same logistic Elo scale as the SPRTs' "Elo". The uncertainty is a bootstrap over openings: 4,000
  resamples, seed 20261109, the same openings for both sides and every anchor.
- **Level 0:** runs in every gauntlet. `tools/gauntlet/transfer.json` holds four things:
  - `baseline`: the gauntlet run the transfer ratio starts from;
  - `previous`: the last gauntlet run;
  - `adopted`: each change adopted since the baseline, as `change`, `elo`, `ci95` (the half-width of its
    95% interval) and `test`;
  - `about`: what the file is for.

  When the file is on the branch, the ordo job downloads both runs' `gauntlet-result` artifacts. The report
  then adds two sections: the gain over the previous gauntlet (overall and per anchor) and the running
  transfer ratio. If an artifact cannot be downloaded (they are kept 90 days; run 41465146207's expires on
  2027-01-31), only its section is left out.

  After each gauntlet, set `previous` to that run. Add every adopted change to `adopted` before the next
  gauntlet: the starting list stops at 32c5517.

  Locally:
  `python -I tools/gauntlet/report.py --previous RUN_DIR --baseline RUN_DIR --adopted tools/gauntlet/transfer.json SHARDS TABLE OUT ORDO`.
- **Level 1:** a dispatch of the gauntlet workflow with the `old` and `new` inputs. It plays 16 shards, each
  against one anchor on 25 openings: OLD plays 50 games on them and NEW plays the same 50, and the order
  alternates by shard. With the default anchors (Clover 6.1 and Altair 7.0.0) that makes 1,600 games. The
  run takes about 20 minutes plus the builds. Start it on an idle queue (no SPRT, CI or web run going):

  ```
  gh workflow run gauntlet.yml -R BOSSDOTCOM/fork --ref BRANCH \
    -f old=OLD_COMMIT -f new=NEW_COMMIT -f claim=CLAIMED_ELO [-f anchors="clover-6.1 altair-7.0.0"]
  ```

  BRANCH must carry the new workflow file (`gauntlet/anchor-check`, or `phase-4` once merged). The run's
  title is `anchor check OLD NEW`. The job "Anchor check: NEW - OLD" puts the report in its summary and in
  the `check-result` artifact. The report gives NEW - OLD per anchor and pooled, each with its bootstrap SD
  and 95% interval, and one of three outcomes:
  - **confirmed:** the pooled lower 95% bound is above 0;
  - **consistent:** not confirmed, but the pooled gain is at least the claim minus 2 bootstrap SDs;
  - **flagged for the owner's review:** anything else.

  It never reverts anything. Without `old` and `new` (a push to `gauntlet-run`, or a dispatch without them),
  the run is the gauntlet as before.
- **Reproduction on the three gauntlets of §1.1** (level 0's code):
  - Gains: A +38.03, B +13.92, A+B +51.95. These match the plain-logistic column (38.0 / 13.9 / 52.0), and
    the per-anchor gains match §1.1 exactly.
  - Paired SDs: 10.54 / 11.06 / 12.36, against the report's 10.5 / 11.0 / 12.2 (the same method with a
    different random stream).
  - Against the headline's Ordo per-run figures (42.4 / 13.0 / 55.4) the logistic gains are lower. Ordo
    also fits a white advantage and a draw rate (`-W -D`).
  - The running ratio from the starting `transfer.json` is 0.61 (95% interval 0.32-0.95), against the
    headline's 0.65. The difference comes from the gain's model, not from the data.

## 6. Fixed-node screens as the first filter

### 6.1 The speed ratio from the screen's own games

The ratio of the two engines' mean move times at fixed nodes, read from each screen's PGN, costs nothing
extra; for S512+PP it reproduces the local identical-tree ratio (0.897 against 0.895). Limits: a few
milliseconds of overhead per move, three games at a time per runner, and tree effects are included.

| Screen | In-situ ratio | Local log2 used before |
|---|---|---|
| S-512 r1 | 0.811 | -0.358 |
| H-512 r1 | 0.754 | -0.415 |
| AF-S r1 | 0.572 | -0.837 |
| XGR r1 | 0.545 | -1.059 |
| AF-S r2 | 0.694 | -0.478 |
| XGR r2 | 0.740 | -0.642 |
| S512+X | 0.752 | -0.290 (0.818 on the bench) |
| S512+PP | 0.897 | -0.160 (0.895 identical-tree) |
| S512ppr3 | 0.999 | 0 |
| Oracle a / b / random / bias | 0.743 / 0.729 / 0.738 / 0.770 | - |
| f1a / f1b / f1c / f1d | 0.919 / 0.938 / 0.737 / 0.736 | - |

S512+X is slower in games than on the bench (0.752 against 0.818), which explains why it was the outlier
in the speed fit.

### 6.2 Fits (weighted least squares; LOO = leave one out)

| Fit | a | R (Elo per doubling) | Elo per 1% | chi^2 / dof | LOO sign | LOO verdict | LOO RMS |
|---|---|---|---|---|---|---|---|
| In situ, a = 1 | 1 | **118.3 ± 5.6** | **1.72** (1.56-1.88) | 11.1 / 8 | 9/9 | 9/9 | 10.2 |
| In situ, a free | 1.01 ± 0.11 | 119.0 ± 9.1 | 1.73 | 11.1 / 7 | 9/9 | 9/9 | 10.7 |
| Local ratios, a = 1 | 1 | 105.7 ± 5.0 | 1.53 | 27.1 / 8 | 9/9 | 9/9 | 16.5 |
| Raw "FN > 0" | - | - | - | - | 3/9 | 3/9 | - |

The in-situ fit's scatter is at the level of sampling noise. The adopted 1.5 sits just below its interval.
The 0.90 speed gate costs about 18.0 Elo at R = 118. LTC has one pair (XGR r2: R_LTC about 141).

Leave-one-out prediction against the STC result (Elo):

| Pair | Predicted | STC |
|---|---|---|
| S-512 r1 | 38.6 | 43.7 |
| H-512 r1 | -15.3 | -24.4 |
| AF-S r1 | -55.3 | -48.5 |
| XGR r1 | -57.3 | -38.2 |
| AF-S r2 | -51.4 | -55.9 |
| XGR r2 | -19.5 | -34.4 |
| S512+X | -22.2 | -30.0 |
| S512+PP | 27.5 | 32.7 |
| S512ppr3 | 15.5 | 7.1 |

Screens with no STC test, adjusted at R = 118:

| Screen | FN_adj | Break-even ratio |
|---|---|---|
| H-512 r2 | -38.4 | - |
| Oracle a | -20.9 | 0.840 |
| Oracle b | -13.0 | 0.786 |
| Random gate | -44.2 | 0.956 |
| f1c | -42.6 | 0.945 |
| f1d | -48.8 | 0.980 |

### 6.3 Offline metrics against game results

| Comparison | Offline metric | FN | STC |
|---|---|---|---|
| S-512 r1 vs B0 | loss -3.25% | +74.5 | +43.7 |
| H-512 r1 vs B0 | loss +3.09% (worse) | +32.2 | -24.4 |
| AF-S r1 vs B0 | loss -0.22% | +41.7 | -48.5 |
| XGR r1 vs B0 | loss -2.20% | +52.1 | -38.2 |
| S512+X vs S512r2 | loss -2.2% | +25.7 | -30.0 |
| S512+PP vs S512r2 | loss -0.06%; endgame check worse (351 vs 249) | +46.1 | +32.7 |
| S512ppr2 vs S512+PP | endgame check 8 vs 351 | - | +20.1 |
| S512ppr3 vs S512ppr2 | loss -1.82e-5 (below the 2e-5 margin) | +15.7 | +7.1 |
| idea 59 refiner f1a | loss 0.0426 -> 0.0227; net flips -0.007 | -19.8 | - |
| S512r3 vs S512r2 | loss worse | never played | - |

Validation-loss sign agreed with the fixed-node sign in 6 of 7 cases and with the STC sign in 4 of 7. The
endgame check was wrong for S512+PP (351 of 900 misjudged, yet +32.7 Elo); the 2e-5 loss margin would have
blocked S512ppr3; the refiner's lower loss went with -19.8 Elo at fixed nodes. Label MSE has never been
paired with a game result (UNVERIFIED as a predictor).

**Failure cases:** the raw fixed-node result alone; local bench ratios (S512+X predicted at -4, measured
-30); no pairs for search features; a screen costs about two STC stages (36-43 minutes against 18-20; over
the nine nets, screening first would have added about 12 stage-equivalents); screens shared stage-0
openings with their SPRTs, so the agreement above is slightly optimistic.

### 6.4 Proposed rule

- **Integrity gates stay blocking:** parity, quantization limits, bench, tests.
- **Offline metrics become diagnostics only.** This changes two existing rules, the owner's call: the 2e-5
  validation-loss margin and decision 10's endgame acceptance target.
- **Every network or evaluation-side candidate whose speed differs from the default** gets a fixed-node
  screen first: FN_adj = FN + 118 · log2(r), r the in-situ speed ratio. FN_adj > 0: the STC SPRT [0, 5]
  follows; otherwise the candidate is screened out (a try of the idea, not the SPRT try).
- **Prototypes** go on to engineering only if FN + 118 · log2(target r) > 0 (for example, idea 59's oracle
  needs r of at least 0.79-0.84 to break even).
- **A single same-architecture retrain** goes straight to its STC SPRT; if several candidates compete,
  screen them all.
- **Search features stay on design R:** no validation pairs exist, their effects are below one screen's
  resolution, and time management cannot be tested at fixed nodes. Optional validation: pair a fixed-node
  screen with the next 6 design R SPRTs of node-efficiency features (not time management), about 12
  stage-equivalents.
- **The speed gate** (decision 8) would use the in-situ ratio priced at the refit R.

## Unverified

- The Elo scale difference between the UHO book and balanced openings.
- How much the tablebase and adjudication difference explains.
- select_best's speed-up on the runners.
- Variance from the runner hardware mix.
- Time management's gain at 10+0.1 (about +17.5 by interpolation).
- Clover's pair-score correlation (one run; 0.15 assumed).
- R at other node budgets and at LTC (one pair).
- Whether the in-situ ratio is stable across CPU types.
- Two figures quoted from the think tank and not re-derived: XGR's LTC rate and +8.8 nElo for an accepted
  null.

## Method notes

Gauntlet games: runs 41465146207 and 42538371594 from the local gauntlet folder; run 42392526865 from its
`gauntlet-result` artifact; openings identified by the FEN header. Fixed-node PGNs downloaded from runs
41170753141, 41172824043, 41174960498, 41177610204, 41371135671, 41390867039, 41395484353 and 42142711426;
the others from the local SPRT folders.
