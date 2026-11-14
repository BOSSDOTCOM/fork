### Gauntlet: 1400 games
Model: the Ordo fit, the anchors fixed at their CCRL Blitz ratings (-m), the white advantage and the draw rate fitted (-W -D), errors from 1,000 simulations (-s 1000) at Ordo's default 95%
```

   # PLAYER           :  RATING  ERROR  POINTS  PLAYED   (%)
   1 Clover 6.1       :  3639.0   ----   136.5     200    68
   2 Altair 7.0.0     :  3579.0   ----   101.5     200    51
   3 Fork             :  3553.7   22.0  1003.0    1400    72
   4 Marvin 6.3.0     :  3458.0   ----    66.0     200    33
   5 Laser 1.7        :  3292.0   ----    33.0     200    16
   6 Winter 0.9       :  3168.0   ----    26.0     200    13
   7 Monolith 2.01    :  3061.0   ----    17.5     200     9
   8 Weiss 1.0        :  2896.0   ----    16.5     200     8

White advantage = 141.19 +/- 10.56
Draw rate (equal opponents) = 25.39 % +/- 1.67
```
### Gap to the reference opponents (outside the Ordo fit)
- Model: plain logistic conversion of Fork's mean pair score, Elo = -400 log10(1/score - 1), no white advantage or draw model; the SPRTs' logistic Elo scale; interval from the pentanomial game pairs
- Stockfish 19 (CCRL Blitz 3792, for context only): Fork 103/400 (25.8%), +64 =78 -258; Elo -184.0, 95% interval -209.7 to -160.0 (pentanomial, 200 pairs, Ptnml(0-2) [59, 76, 65, 0, 0])
### Anchor check: gain over the previous gauntlet
- Model: plain logistic fit, E = 1 / (1 + 10^(-diff/400)), the anchors fixed at their CCRL Blitz ratings, no white advantage or draw model (a draw counts half); the SPRTs' logistic Elo scale
- On Altair 7.0.0, Clover 6.1, Laser 1.7, Marvin 6.3.0, Monolith 2.01, Weiss 1.0, Winter 0.9: +38.2 Elo, bootstrap SD 9.0, 95% interval +20.6 to +55.7 (paired by opening: 100 openings, 1400 and 1400 games; plain logistic fit, the anchors at their CCRL Blitz ratings; bootstrap of 4000 resamples of the openings, seed 20261109)
- Per anchor: Altair 7.0.0 +29.6 (SD 19.2); Clover 6.1 +33.3 (SD 18.4); Laser 1.7 +38.1 (SD 22.7); Marvin 6.3.0 +59.8 (SD 18.6); Monolith 2.01 +52.8 (SD 39.1); Weiss 1.0 -5.8 (SD 32.0); Winter 0.9 +22.0 (SD 26.8)
### Anchor check: running transfer ratio since the baseline gauntlet (run 41465146207, commit 3902d00)
- Model: plain logistic fit, E = 1 / (1 + 10^(-diff/400)), the anchors fixed at their CCRL Blitz ratings, no white advantage or draw model (a draw counts half); the SPRTs' logistic Elo scale; the self-play sum is the SPRTs' logistic Elo of each change
- Self-play: 23 adopted changes sum to +240.1 +/- 26.4 Elo (95%): S512+PP +32.67; select_best in a register (5ba7d0d) +6.00; S512ppr2 +20.11; S512ppr3 +7.12; Time management (b) +18.69; R14 SPSA tuned margins (spsa-r14-m2) +37.93; r8btd90 (retrain 8b, TD(0.9) labels) +12.17; r8brft1 (idea 70, result fine-tune of td90) +5.74; cut-node (R4, 1 ply) +6.02; T56 any-attack threat buckets +7.49; ProbCut (T31, capture probe 9 / 5 / 80) +9.40; E1 pass-best stop rule +3.26; Quiet history pruning (T24/B13, the history skip, 700 per ply) +6.04; Minor drift table (E4, MinorDriftShare 32/64) +5.57; D8 summed pair-table update +4.29; D13 direct-check ordering bonus (DirectCheckBonus 5000) +5.50; History skip's exemption for checking quiets (B13 with D13) +2.80; D17 history ageing between searches (HistoryKeepQuarters 2) +5.71; B9 improving flag in LMP (LmpImprovingEighths 1) +6.82; B9 improving flag in LMR (LmrNotImprovingPlies 1) +12.71; R20 round-once LMR with a centred history term (LmrHistoryPerPly 10000) +6.21; D11 linear history bonus (LinearBonusPerPly 125) +8.98; B16 quiescence move cap (QuiesceMoveCap 2) +8.90
- Against the anchors (Altair 7.0.0, Laser 1.7, Marvin 6.3.0, Monolith 2.01, Weiss 1.0, Winter 0.9): +114.1 Elo, bootstrap SD 12.7, 95% interval +90.1 to +139.9 (paired by opening: 100 openings, 1200 and 1200 games; plain logistic fit, the anchors at their CCRL Blitz ratings; bootstrap of 4000 resamples of the openings, seed 20261109)
- Transfer ratio 0.48, 95% interval 0.37 to 0.60 (each bootstrap draw of the anchor gain over a normal draw of the sum); gap -126.0 +/- 18.5 Elo (1 SE)
- Self-play sum median-unbiased at each SPRT's design and stop stage: +234.8 Elo, transfer ratio 0.49, 95% interval 0.38 to 0.62: S512+PP +32.67; select_best in a register (5ba7d0d) +6.00; S512ppr2 +20.09; S512ppr3 +6.98; Time management (b) +18.45; R14 SPSA tuned margins (spsa-r14-m2) +37.93; r8btd90 (retrain 8b, TD(0.9) labels) +12.03; r8brft1 (idea 70, result fine-tune of td90) +5.41; cut-node (R4, 1 ply) +4.86; T56 any-attack threat buckets +7.25; ProbCut (T31, capture probe 9 / 5 / 80) +9.06; E1 pass-best stop rule +3.26; Quiet history pruning (T24/B13, the history skip, 700 per ply) +5.83; Minor drift table (E4, MinorDriftShare 32/64) +5.23; D8 summed pair-table update +4.11; D13 direct-check ordering bonus (DirectCheckBonus 5000) +5.15; History skip's exemption for checking quiets (B13 with D13) +2.80; D17 history ageing between searches (HistoryKeepQuarters 2) +4.94; B9 improving flag in LMP (LmpImprovingEighths 1) +6.28; B9 improving flag in LMR (LmrNotImprovingPlies 1) +12.71; R20 round-once LMR with a centred history term (LmrHistoryPerPly 10000) +6.08; D11 linear history bonus (LinearBonusPerPly 125) +8.91; B16 quiescence move cap (QuiesceMoveCap 2) +8.82
