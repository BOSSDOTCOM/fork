# Idea 52, first step: seed disagreement (2026-11-07, 4:45-5:10 PM EST)

Verdict: **kill** under idea 52's 1.5 line once |eval| is controlled for.

- Nets: item 7's warm seeds s512pp-warm-s1 (= S512ppr2) and s512pp-warm-s2, both at S = 89. Integer
  evaluation (R-int) matched the engine's evalfens on all 77,335 positions; quantization error about 2.0 cp
  mean for both.
- Positions: g3s3-val with the trainer's filter (77,335; g3s2-val's 1,800 games + 120 new g3f/g3g games).
- D in cp: mean 3.95, median 3, p95 10, p99 14; above 2x/3x/5x the median: 18.7% / 6.5% / 0.6%; the top 5%
  hold 16% of total D. The warm seeds are nearly one net (median D about the quantization error).
- D in win probability (sigmoid(cp/89)): median 0.0021, p95 0.0154; its concentration is mostly the sigmoid
  (correlation with |eval| −0.52; D in cp +0.09).
- By phase: middle phases disagree most (13-18: mean 3.59 cp), endgames least (0-6: 3.01).
- Deep labels: S512ppr2 at 1,000,000 nodes (median depth 16), 1,000 positions per group, 2,932 searches.
- Error ratio, top D over random (both seeds, 95% bootstrap): top by D in cp 1.39 [1.21, 1.59] (cp);
  top by D in win probability 0.52 [0.45, 0.60] in cp but 2.01 [1.81, 2.24] in win probability (the |eval|
  effect). Matched for |eval|: 1.24-1.37, upper bounds 1.41-1.59. The games' stored scores over all 77k
  agree (top by D in cp: 1.41 [1.35, 1.48]).
- Caveat: the warm seeds share S512+PP's start and a low LR, so they are a weak committee; the scratch seeds
  (s512pp-scratch-s1/s2) or independently started nets are the only follow-up worth considering.
- CPU: about 40 CPU-minutes (jobs idea52-rint, idea52-float, idea52-deep300, idea52-deep1000, all exit 0).
- Results: dist.json, ratio_300.json and ratio_1000.json beside this report. The scripts (prep.py, rint_all.py,
  float_all.py, deep.py, analyze.py and the job scripts) and the bulky data (positions, deep labels, evaluation
  outputs, the converted seed-2 net) stayed in the session's scratch folder: the scripts hard-code local paths.

## The scratch pair (2026-11-07, 5:42-6:01 PM EST, job idea52-scratch)

Owner request: the same check on item 7's two scratch seeds (independent initialisations,
s512pp-scratch-s1/s2, converted at S = 89; quantization error 2.3-2.4 cp mean), same positions, method,
kill line and eval-size matching; deep labels by S512ppr2 at 1,000,000 nodes (2,788 new searches, the rest
reused). The scratch seeds disagree far more than the warm pair (top-5% threshold about 57 cp; the
endgame phases 0-6 disagree most, unlike the warm pair).

Error ratio, top 5% by disagreement over the random rest, matched for |eval| (95% bootstrap):

| detector | warm pair | scratch pair | S512ppr2's own error on the scratch-chosen positions |
|---|---|---|---|
| D in cp, error in cp | 1.24 [1.10, 1.41] | 1.69 [1.49, 1.92] | 1.71 [1.50, 1.95] |
| D in cp, error in win probability | 1.37 [1.22, 1.54] | 1.75 [1.52, 2.00] | 1.66 [1.42, 1.93] |
| D in win probability, error in cp | 1.28 [1.11, 1.50] | 1.70 [1.49, 1.92] | 1.62 [1.40, 1.86] |
| D in win probability, error in win probability | 1.25 [1.12, 1.41] | 1.50 [1.35, 1.66] | 1.39 [1.24, 1.55] |

Verdict: **the scratch pair passes the 1.5 line** on three of the four detectors (the fourth sits at it),
so idea 52 is not killed: two independently initialised nets disagree most where the default net itself
errs about 1.6-1.7 times more than elsewhere at equal |eval|; the warm pair (one net in effect) carries no
such signal.

**Mates excluded** (owner request, recomputed the same evening): the cp errors above already left out
deep-search mate scores; only the win-probability errors counted them (as 0 or 1). With every mate
position dropped from every group (44 from the top-by-cp group, 5 from the random rest), the matched
ratios barely move:

| detector | with mates | mates excluded |
|---|---|---|
| D in cp, error in cp | 1.69 [1.49, 1.92] | 1.70 [1.51, 1.93] |
| D in cp, error in win probability | 1.75 [1.52, 2.00] | 1.76 [1.55, 2.01] |
| D in win probability, error in cp | 1.70 [1.49, 1.92] | 1.70 [1.50, 1.93] |
| D in win probability, error in win probability | 1.50 [1.35, 1.66] | 1.49 [1.36, 1.67] |

S512ppr2's own matched error ratios with mates excluded: 1.71, 1.67, 1.62, 1.39. **The result holds**
(at or above 1.5 on three detectors, at 1.49 on the fourth).
Results: scratch_dist.json, scratch_ratio_1000.json and scratch_ratio_1000_nomates.json beside this report.
