# Fork's networks

One entry per trained network (DESIGN.md §5.3, deliverable 7): its file,
architecture, data, training run, parity results and SPRT. Every net
chains back to the bootstrap evaluation (KB originality.md §4); data and
labels are Fork's own (KB data-policy.md, strategy A+).

## Quantization-loss limits

Each architecture has limits on the quantization loss |R-int - R-float|
over the 446 parity positions (DESIGN.md §5.3, deliverable 6), set from
its first healthy net and approved by the owner. **The rule** (owner,
2026-10-30): the limits leave headroom above the first healthy net's loss,
to catch broken conversions (a missing rounding step, a too-coarse scale,
a transposed tensor), not to rank nets. They are checked with
`tools/nnue/reference.py legs --max-loss MAX --p99-loss P99` when a net is
added; no CI job applies them automatically.

| Architecture | First net and its loss (max / p99) | Limits (max / p99) | Approved |
|---|---|---|---|
| B0 (768 -> 256 -> 1) | B0: 11.1 / 8.8 cp | 15 / 12 cp | owner, 2026-10-29 |
| S-512 (768 mirrored -> 512 SCReLU -> 8 by phase) | S512: 15.6 / 12.1 cp | 21 / 16 cp | owner, 2026-10-30 |
| S512+PP (S-512 plus 608 pawn links of rank limit 1, in the main int16 sums) | s512pp (bake/s512pp 412b13f, seed 2): 8.3 / 6.8 cp | 21 / 16 cp (S-512's) | owner, 2026-11-06 |

## B0 (2026-10-29)

| Item | Value |
|---|---|
| File | `nets/b0.fnet` on branch b0-candidate (79b1a6c), 394,820 bytes, Fork checksum c3f6c06ea403a475 |
| Architecture | 768 inputs per perspective -> 256, clipped ReLU, concatenated side to move first -> 1; QA 255 / QB 64 (bullet's convention); S = 134 |
| Data | generation-0 snapshot g0s1 (data/manifests/g0s1.json): 99,775 games, 9,535,083 positions of Fork self-play with the bootstrap evaluation (20,000 nodes per move, openings from Lichess 2016-09, Syzygy 3-4-5 adjudication); 9 shards for training, worker 9's shard held out for validation; every shard hash-checked against the manifest on Kaggle before training |
| Training | Kaggle kernel fork-train-b0 (T4), tools/train at fadfc02 on bullet-trainer da426a49: target 0.5 sigmoid(score / 134) + 0.5 result; AdamW (bullet's defaults), LR 0.001; batch 16,384, 305 batches per superbatch; early stopping (patience 8): best superbatch 3 of 11, validation loss 0.02483; 106 s of training |
| Parity (tests/nnue/b0.parity, 446 positions) | quantization leg exact; R-float vs bullet's own float evaluation at most 0.00012 cp (kernel fork-eval-t); Fork's inference = R-int on all 446 (embedded netcheck); quantization loss max 11.1 cp, p99 8.8 cp, mean 3.4 cp (thresholds for B0-class nets: max 15, p99 12; owner, 2026-10-29) |
| Bench | 17,320,616 nodes, signature 801e340fab64384d (tests/bench-b0.ref on b0-candidate) |
| SPRT | vs the bootstrap evaluation, [0, 5], 8+0.08: **+486.85 +/- 32.07 Elo, H1 accepted** after 1,600 games (docs/history/phase-4/sprt-log.md) |
| Status | The default network from 2026-10-29 (owner; its failing tests were fixed, DESIGN.md §5.3) until B0r1 replaced it the same day; still buildable with `-DFORK_NET=nets/b0.fnet`. Bench with today's search: tests/bench-b0.ref |

## B0r1, B0's first retrain (2026-10-29)

| Item | Value |
|---|---|
| File | `nets/b0r1.fnet` (branch b0r1-candidate 3d66a40, merged into phase-4), 394,820 bytes, Fork checksum 11bbf22c07979e76 |
| Architecture | B0's (768 -> 256 -> 1, clipped ReLU, QA 255 / QB 64, S = 134: a warm start keeps its net's target scale) |
| Data | generation-0 snapshot g0s2 (data/manifests/g0s2.json): 867,948 games, 82,943,968 positions at 09:17; workers 0-8 for training (each g0s1 shard is a byte prefix of its g0s2 shard), worker 9 held out (its first 20,000 kept positions are the ones B0 validated on); hashes checked on Kaggle before training |
| Training | Kaggle kernel fork-train-b0r1 (T4), tools/train at ea96bc6: warm-started from B0's float weights (SHA-256 checked); before training, superbatch 0 reproduced B0's best validation loss exactly (0.02482651, required within 1e-5); B0's settings otherwise (target 0.5 sigmoid(score / 134) + 0.5 result, AdamW, LR 0.001 dropped tenfold every 40, batch 16,384 x 305 per superbatch, patience 8); best superbatch 19 of 27, validation loss 0.02298352; 234 s of training |
| Parity (tests/nnue/b0r1.parity, 446 positions) | quantization leg exact; R-float vs bullet's float evaluation at most 0.00012 cp; netcheck exact on all 446; quantization loss max 8.6 cp, p99 7.9 cp, mean 2.5 cp (within the B0-class thresholds) |
| Bench | 15,453,694 nodes, signature 13b0972dfaf384ee (tests/bench-b0r1.ref) |
| SPRT | vs B0 (phase-4 a3dd67c), [0, 5], 8+0.08, GitHub shards, run 40916705615: **+200.24 +/- 16.05 Elo (nElo +263.05 +/- 17.02), H1 accepted** after 1,600 games (docs/history/phase-4/sprt-log.md) |
| Status | The default network from 2026-10-29 until B0r2 replaced it on 2026-10-30, and generation 1's labeller until then; still buildable with `-DFORK_NET=nets/b0r1.fnet` (tests/bench-b0r1.ref) |
| Notes | Three search tests that passed with B0 failed with B0r1, all fixed in the tests (DESIGN.md §5.3): the determinism test now clears the history as well as the TT; the stop-during-fail-high test scans every bench position, since B0r1's first ten gave no qualifying stop; and at depth 1 B0r1 plays Rb2 instead of Rxd5 in 3rk3/8/8/3p4/8/8/3R4/3RK3 w (it scores 2R v R+P at 447 cp over the K+R v K it reaches after the exchanges at 420). That is not a weakness: every legal move there keeps the tablebase win (lichess API: Rxd5 DTM 31, Rb2 DTM 41). With a network, the test now checks a K+R+P v K+R position where 4 moves keep the win and 12 do not. |

## B0r2, B0's shape on generation 1 (2026-10-30)

| Item | Value |
|---|---|
| File | `nets/b0r2.fnet` (the bake-off's B0 control, branch bake/g1b0 5cacf8a as `nets/g1b0.fnet`), 394,820 bytes, Fork checksum 245cdb44ff2b4cc9 |
| Architecture | B0's (768 -> 256 -> 1, clipped ReLU, QA 255 / QB 64), S = 105 (fit on g1s1, DESIGN.md §5.4) |
| Data | generation-1 snapshot g1s1 (data/manifests/g1s1.json): 1,505,322 games, 150,117,509 positions of Fork self-play labelled by B0r1 at 10:32 AM EST; workers 0-8 for training (93,502,604 positions pass the filter), worker 9 held out; hashes checked on Kaggle before training |
| Training | Kaggle kernel fork-bake (T4), commit d4ccadb on bullet-trainer da426a49, seed 1, no warm start: target 0.5 sigmoid(score / 105) + 0.5 result, AdamW, LR 0.001 dropped tenfold after 40, batch 16,384 x 305 per superbatch, 80 superbatches (400 M positions seen), the checkpoint with the lowest validation loss kept: superbatch 61, validation loss 0.02167907 (seed 2: 0.02180452 at 71); 1,083 s |
| Parity (tests/nnue/b0r2.parity, 446 positions) | quantization leg exact; R-float vs the trainer's float evaluation at most 0.00012 cp; netcheck exact on all 446; quantization loss max 9.0 cp, p99 7.2 cp, mean 2.0 cp (within the B0-class thresholds) |
| Bench | 14,589,665 nodes, signature 9dba694dd1ee4c41 (tests/bench-b0r2.ref) |
| SPRT | vs B0r1 (phase-4 c9a4a7c), [0, 5], 8+0.08, GitHub shards, run 41104107035: **+235.45 +/- 16.04 Elo (nElo +334.16 +/- 17.02), H1 accepted** after 1,600 games (docs/history/phase-4/sprt-log.md) |
| Status | The default network on 2026-10-30 (owner's standing instruction, DESIGN.md §5.4 games plan item 0) until S-512 replaced it the same day, and the labeller of generation 1's part g1b; the bake-off entries still play against it as the B0 control; still buildable with `-DFORK_NET=nets/b0r2.fnet` (tests/bench-b0r2.ref) |
| Notes | One search test that passed with B0r1 failed with B0r2: the repetition case checked that the evaluation of the position after 1. e4 Nf6 2. Nf3 Ng8 3. Ng1 is not 0, and B0r2 scores it exactly 0. The line now starts without Black's queen and the check asks for an evaluation below -300, so it holds for any evaluator. |

## S512, the bake-off's S-512 entry (2026-10-30)

| Item | Value |
|---|---|
| File | `nets/s512.fnet` (branch bake/g1s512 ba8c4cb as `nets/g1s512.fnet`, byte-identical), 804,064 bytes, Fork checksum ef88709dc8d2bcba |
| Architecture | 768 inputs per perspective, mirrored left-right, -> 512 SCReLU -> 8 outputs, one picked by game phase (H-512's phase octiles; owner, 2026-10-30); QA 255 / QB 64; S = 101, matched to the B0 control's output scale (DESIGN.md §5.4, plan 2) |
| Data | generation-1 snapshot g1s1, as B0r2 (workers 0-8 for training, worker 9 held out) |
| Training | Kaggle kernel fork-bake at d4ccadb (T4), seed 1, no warm start: target 0.5 sigmoid(score / 105) + 0.5 result, AdamW, LR 0.001 dropped tenfold after 40, batch 16,384 x 305 per superbatch, 80 superbatches (400 M positions seen); the checkpoint with the lowest validation loss kept: superbatch 68, validation loss 0.020974 (seed 2: 0.021176 at 71, branch bake/g1s512b). Still improving when training stopped (DESIGN.md §5.4) |
| Parity (tests/nnue/s512.parity, 446 positions) | R-float vs the trainer's float evaluation at most 0.00012 cp; netcheck exact on all 446; quantization loss max 15.6 cp, p99 12.1 cp, mean 3.6 cp: the first net of its architecture, within the limits set from it (max 21 cp, p99 16 cp; owner, 2026-10-30; see "Quantization-loss limits") |
| Bench | 15,249,025 nodes, signature 13001f412d6e8d7e (tests/bench-s512.ref) |
| SPRT | vs the B0 control (bake/g1b0 5cacf8a, the net promoted as B0r2), [0, 5], 8+0.08, GitHub shards, run 41125906800 (bake-off stage A): **+43.66 +/- 12.02 Elo (nElo +62.52 +/- 17.02), H1 accepted** after 1,600 games (docs/history/phase-4/sprt-log.md) |
| Status | The default network from 2026-10-30 (provisionally, owner) until S512r2 replaced it on 2026-11-01, and the labeller of generation 2 and of the cloud data generation until then; still buildable with `-DFORK_NET=nets/s512.fnet` (tests/bench-s512.ref), and checked in CI as round 1's S-512 entry |
| Notes | One search test that passed with B0r2 failed with S-512: K+R v K with the fifty-move clock at 0 had to score above 300 cp, and S-512 scores it 263. The check, which only contrasts the position with the same one drawn by the fifty-move rule, now asks for any score above the draw's 0. |

## S512r2, S-512 retrained in round 2 (2026-11-01)

| Item | Value |
|---|---|
| File | `nets/s512r2.fnet` (branch bake/r2s512 84dc337 as `nets/r2s512.fnet`, byte-identical: the net that played the SPRT), 804,064 bytes, Fork checksum 093e3fda66afab43 |
| Architecture | S-512's (768 inputs per perspective, mirrored left-right, -> 512 SCReLU -> 8 outputs picked by game phase; QA 255 / QB 64), with round 2's phase octiles (tools/nnue/s512.json at 6600af3, refitted on g2s1); S = 92 |
| Data | generation-2 snapshot g2s1 (data/manifests/g2s1.json): 9,176,386 games, 614,769,222 saved positions labelled by S512 (local parts g2-g2e and 8 cloud runs; 415,949,440 pass the training filter); validation on g2s1-val (780 games, 60 from a designated shard of each of the 13 sources) |
| Training | Kaggle kernel fork-round2a at 6600af3 (T4), seed 2, no warm start: target 0.5 sigmoid(score / 92) + 0.5 result, AdamW, LR 0.001 dropped tenfold after 180, batch 16,384 x 305 per superbatch, 360 superbatches (1.8 B positions seen, about 4.3 passes); the checkpoint with the lowest validation loss kept: superbatch 307, validation loss 0.019458 (seed 1: 0.019496 at 305; the owner's rule: the seed with the lower loss); 5,929 s. The curve is flat from about superbatch 220 (within about 0.0002) |
| Parity (tests/nnue/s512r2.parity, 446 positions) | quantization leg exact; R-float vs the trainer's float evaluation at most 0.00014 cp; netcheck exact on all 446; quantization loss max 12.5 cp, p99 10.2 cp, mean 2.9 cp (within S-512's limits, 21 / 16 cp) |
| Scale | **S = 92, the scale it played its SPRT with** (owner, 2026-11-01: promoted with exactly the tested scale). Scale matching on the first 10,000 filtered positions of g2s1-val gave two values: matched to the current default S512, the SPRT's opponent, 92 (mean \|eval\| 226.39 against S512's 226.68 cp), the trainer's own S, so no rescale; matched to round 2's B0 control (seed 2, the bake-off plan's reference), 89 (B0's mean \|eval\| 219.04 cp). 92 was chosen for the SPRT because it keeps the evaluation at the scale the search's margins were tuned on, which is the purpose of matching (DESIGN.md §5.4, plan 2), and the pairing was against S512. 89 is untested: if it is preferred on principle, it gets its own SPRT before any change |
| Bench | 17,904,298 nodes, signature 698205c2870d96a4 (tests/bench-s512r2.ref; search at 32bb1ff) |
| SPRT | vs S512 (phase-4 6600af3), [0, 5], 8+0.08, GitHub shards, run 41349145950: **+151.35 +/- 12.50 Elo (nElo +233.38 +/- 17.02), H1 accepted** after 1,600 games (docs/history/phase-4/sprt-log.md) |
| Status | The default network from 2026-11-01 (owner, after review) until S512+PP replaced it on 2026-11-06, and the labeller of generation 3 and of the cloud data generation until then (DESIGN.md §5.3, labeller policy); still buildable with `-DFORK_NET=nets/s512r2.fnet` (tests/bench-s512r2.ref: 14,180,299 / 4cf778ff753861f7 with today's search), checked in CI's `nets` job |
| Notes | One search test failed with S512r2 and was fixed in the test: the mate-confirmation test's "exact" search still had multi-cut on, which prunes, and missed two real mates in 7 plies that S512r2's search reported (4k3/8/1Q6/8/8/r7/8/1R2K3 w: the lichess tablebase gives DTM 7). The exact search now also switches off multi-cut, the negative extension and the no-move reduction. |

## S512+PP, S-512 with pawn links (2026-11-06)

| Item | Value |
|---|---|
| File | `nets/s512pp.fnet` (branch bake/s512pp 412b13f, the net that played both tests), 1,426,656 bytes, Fork checksum d570c637a0da031e |
| Architecture | Architecture 8: S-512 (768 inputs per perspective, mirrored left-right, -> 512 SCReLU -> 8 outputs picked by game phase; QA 255 / QB 64) plus 608 pawn-link inputs, one per pair of pawns at most one rank apart (R = 1), kept incrementally in the main int16 accumulator (the reader's bound: 64 active links); S = 90 (ideas.md idea 40, L1's first step) |
| Data | g2s1 and g3s1 together (data/manifests/g2s1.json, g3s1.json): 16,498,106 games, 988,611,737 saved positions, labelled by S512 (g2s1) and S512r2 (g3s1); validation on g3s1-val |
| Training | Kaggle kernel fork-s512pp version 1 at 2143f1d (T4 x2), seed 2, warm-started from S512r2's float weights with the link inputs at zero (which compute S512r2's output exactly; the warm start reproduced S512r2's validation loss within 1e-6): target 0.5 sigmoid(score / 92) + 0.5 result, AdamW, LR 0.001 dropped tenfold after 180, batch 16,384 x 305 per superbatch, 360 superbatches; the checkpoint with the lowest validation loss kept: superbatch 350, validation loss 0.01929241 on g3s1-val (S512r2: 0.01930359; seed 1: 0.01945583); 7,802 s |
| Scale | S = 90, matched to S512r2's mean \|eval\| on 4,000 g3s1-val positions (217.63 cp against S512r2's 221.88 at S = 92); promoted with the scale it was tested at |
| Conversion | 2 of 311,296 link weights clamped to their units' allowance under the reader's 64-link bound (2 of 512 units over it; the owner's fallback); the unclamped net passes every leg with the same losses |
| Parity (tests/nnue/s512pp.parity, 446 positions) | trainer leg at most 0.00018 cp; netcheck exact on all 446; quantization loss max 8.3 cp, p99 6.8 cp, mean 2.2 cp (within S512+PP's limits, S-512's 21 / 16 cp; owner, 2026-11-06) |
| Speed | **0.895 of S512r2's nps** (identical-tree method, 12 rounds 0.873-0.915; bench nps 2,342,208 on a loaded machine): the owner's recorded exception to the 0.90 speed gate (DESIGN.md §5.4; ideas.md idea 40) |
| Endgame check | tools/nnue/endgame_check.py, 900 positions: **351 misjudged against S512r2's 249** (KQK 59 of 300 against 0; KRK 267 against 223). The Syzygy endgame slice in item 7's snapshot g3s2 is meant for this |
| Bench | 13,909,380 nodes, signature 831e5c9295839f87 (tests/bench-s512pp.ref) |
| Tests | vs S512r2 (phase-4 684bac6): fixed nodes, 800,000 per move, run 42284077960: +46.09 +/- 10.37 Elo (nElo +76.54 +/- 17.02), 1,600 games; then STC 8+0.08 [0, 5], run 42294907752: **+32.67 +/- 10.48 Elo (nElo +53.37 +/- 17.02), H1 accepted** after 1,600 games (docs/history/phase-4/sprt-log.md) |
| Status | The default network on 2026-11-06 (owner: promoted on its STC result) until S512ppr2 replaced it the same evening, and the labeller of generation 3's part g3f (DESIGN.md §5.3, labeller policy); item 7's retrain used its architecture and its float weights. Still buildable with `-DFORK_NET=nets/s512pp.fnet` (tests/bench-s512pp.ref), checked in CI's `nets` job |
| Notes | Two network-dependent search checks failed with S512+PP and were rewritten to hold for any evaluator: at depth 1 in K+P v K it plays e1f2, not b7b8q, and the check now accepts any move that keeps the tablebase win (b7b8q, b7b8r and the five king moves; Syzygy 3-4-5 and the lichess tablebase agreeing); K+R v K with the halfmove clock at 0 scored at most 0 at depth 3, so the fifty-move contrast now uses a forced mate in 2 (0 with the clock at 99, the mate with the clock at 0). |

## S512ppr2, S512+PP retrained on g3s2 (2026-11-06)

| Item | Value |
|---|---|
| File | `nets/s512ppr2.fnet` (branch bake/s512ppr2 d56c2cf, the net that played its test), 1,426,656 bytes, Fork checksum 9daf35fd54878f7b |
| Architecture | Architecture 8, as S512+PP (S-512 plus 608 pawn-link inputs of rank limit 1); S = 89. Its speed is S512+PP's (the same architecture; not measured separately) |
| Data | g3s2 (data/manifests/g3s2.json): g2s1 and g3s1 as they are, plus every generation-3 part since (g3's rest, g3b to g3e), labelled by S512 and S512r2, and the Syzygy endgame slice (10 files of 2,600,000 one-move games of at most 5 pieces, about 2.1% of the training positions); 81 training files, about 1.24 B positions, read interleaved; validation on g3s2-val (1,800 games) |
| Training | Kaggle kernel fork-retrain-g3s2 version 1 at d599df3 (DESIGN.md §5.6, item 7): the warm recipe (from S512+PP's float weights, LR 0.0001 dropped tenfold after 180), seed 1; best validation loss 0.01908862 at superbatch 352 (warm mean 0.01909453 over 2 seeds, scratch mean 0.01951758: the warm recipe better by 0.00042, about ten times S-512's seed spread of 4e-5, so resolved; DESIGN.md §5.6, item 7); 7,741 s |
| Scale | S = 89, matched to S512+PP's mean \|eval\| on 4,000 g3s2-val positions (220.91 cp against 221.33) |
| Conversion | 2 of 311,296 link weights clamped to their units' allowance under the reader's 64-link bound (2 of 512 units over it); the unclamped net passes every leg with the same losses |
| Parity (tests/nnue/s512ppr2.parity, 446 positions) | trainer leg at most 0.0002 cp; netcheck exact on all 446; quantization loss max 7.9 cp, p99 6.1 cp, mean 2.0 cp (within S-512's 21 / 16 cp) |
| Endgame check | tools/nnue/endgame_check.py, 900 positions: **8 misjudged (0.9%) against S512+PP's 351** (at the trained S = 92: KQK and KRK 0 of 600, KPK 8 of 300; S512+PP KQK 59, KRK 267, KPK 25) |
| Tests | vs S512+PP (phase-4 b115e03): STC 8+0.08 [0, 5], runs 42335141916 and 42336446490: **+20.11 +/- 7.22 Elo (nElo +33.60 +/- 12.04), H1 accepted** after 3,200 games (docs/history/phase-4/sprt-log.md) |
| Bench | 14,626,377 nodes, signature 9e43990217b0886d (tests/bench-s512ppr2.ref) |
| Status | The default network from 2026-11-06 (owner: promoted on its STC result) until S512ppr3 replaced it on 2026-11-07, and the labeller of generation 3's parts g3g, g3h and g3i (DESIGN.md §5.3, labeller policy); item 8a's retrain started from its float weights. Still buildable with `-DFORK_NET=nets/s512ppr2.fnet` (tests/bench-s512ppr2.ref), checked in CI's `nets` job |

## S512ppr3, S512ppr2 retrained on g3s3 (2026-11-07)

| Item | Value |
|---|---|
| File | `nets/s512ppr3.fnet` (branch bake/s512ppr3 720fe7b, the net that played its tests), 1,426,656 bytes, Fork checksum 5861c1a319ca267b |
| Architecture | Architecture 8, as S512+PP and S512ppr2; S = 89 |
| Data | g3s3 (data/manifests/g3s3.json): g3s2 as it is plus the sealed parts g3f (S512+PP labels) and g3g (S512ppr2 labels), the Syzygy endgame slice kept; 101 training files read interleaved; validation on g3s3-val (1,920 games) |
| Training | Kaggle kernel fork-retrain-g3s3 version 1 at 6053b51 (item 8a, DESIGN.md §6 decision 10): the standard recipe (from S512ppr2's float weights, LR 0.0001 dropped tenfold after 180, 360 superbatches), seed 1; the network is R1-avg, the mean of superbatches 331-360's float weights. Full g3s3-val loss 0.01966655 against S512ppr2's 0.01968472 (R1's best checkpoint 0.01965562, R2's 0.01972978, the cooldown average 0.01977483, the anneal-only arm 0.01975487); the candidate by the declared rule, 1.82e-5 below S512ppr2, short of the 2e-5 SPRT margin, so the owner's tie-break: a fixed-node screen, the STC SPRT only at +5 Elo or more |
| Scale | S = 89, matched to S512ppr2's mean \|eval\| on 4,000 g3s3-val positions (214.84 cp against 213.86) |
| Conversion | 1 of 311,296 link weights clamped to its unit's allowance under the reader's 64-link bound (1 of 512 units over it); the unclamped net passes every leg with the same losses |
| Parity (tests/nnue/s512ppr3.parity, 446 positions) | trainer leg at most 0.00015 cp; netcheck exact on all 446; quantization loss max 9.4 cp, p99 7.5 cp, mean 2.3 cp (within S-512's 21 / 16 cp) |
| Endgame check | tools/nnue/endgame_check.py, 900 positions: **8 misjudged (0.9%), as S512ppr2** |
| Tests | vs S512ppr2 (phase-4 98cf000): fixed nodes, 800,000 per move, run 42426868742: +15.65 +/- 9.26 Elo (nElo +28.80 +/- 17.02), 1,600 games, above the owner's +5 tie-break; then STC 8+0.08 [0, 5], runs 42429984619, 42431412304, 42432793282, 42434196075 and 42435511074: **+7.12 +/- 4.53 Elo (nElo +11.98 +/- 7.61), H1 accepted** after 8,000 games (docs/history/phase-4/sprt-log.md) |
| Bench | 14,149,617 nodes, signature 1cb0717f040c294d (tests/bench-s512ppr3.ref) |
| Status | The default network on phase-4 from 2026-11-07 (owner: promoted on its STC result); on this candidate branch, the control the candidate is screened against. The labeller of the data generation from generation 3's part g3j on (DESIGN.md §5.3, labeller policy) |

## r8brft2, a retrain 8b candidate (2026-11-10, candidate branch only)

| Item | Value |
|---|---|
| File | `nets/r8brft2.fnet`, this candidate branch's default network (not promoted) |
| Training | Idea 70's result fine-tune, seed 2: r8btd90's window average fine-tuned at result weight 1.0, LR 1e-5 constant for 60 superbatches on g4s1, the mean of superbatches 46-60 (docs/research/retrain-8b/plan.md, branch retrain/8b-prep) |
| Bench | 10,564,507 nodes, signature 74fed831fcb1e0ed (tests/bench-r8brft2.ref) |
| Status | **The default network since 2026-11-10 on this candidate branch only**, for retrain 8b's fixed-node screens against S512ppr3 (the default on phase-4); not promoted |

## The bake-off entries in CI (2026-10-31)

Every round-2 architecture is built with its entry's network and checked
on every CI run (owner, 2026-10-31): the `nets` job of
`.github/workflows/ci.yml` runs `.github/ci/net-check.sh NET` for each, a
clang release build of `fork` with `-DFORK_NET=nets/NET.fnet`, then
netcheck against `tests/nnue/NET.parity` (446 positions) and bench parity
against `tests/bench-NET.ref`. The H-512, AF-S and XGR-512 files are the
bake-off's own (bake/g1h512 21fb7fc, bake/g1afs b5da3bc, bake/g1xgr
a697945), byte for byte; the S-512 and B0 control entries were already
here as `s512` and `b0r2` (byte-identical to bake/g1s512's and
bake/g1b0's nets).

| Entry | Network | Architecture id | Bench (nodes / signature) |
|---|---|---|---|
| S-512 (round 1; the default until 2026-11-01) | `nets/s512.fnet` | 2 | 15,249,025 / 13001f412d6e8d7e |
| B0 control | `nets/b0r2.fnet` | 1 | 14,589,665 / 9dba694dd1ee4c41 |
| H-512 | `nets/g1h512.fnet` | 3 | 14,987,230 / 1190b45ba0d0ab53 |
| AF-S | `nets/g1afs.fnet` | 4 | 26,382,157 / 4d87061f4e7b57ac |
| XGR-512 | `nets/g1xgr.fnet` | 5 | 15,540,185 / 9564dc8f27cd9708 |

Checked at phase-4 6eef2a7 in WSL (clang 21, -march=native): netcheck 0
mismatches and bench parity for all five; the perft workload is the same
for every network (26,401,709 / f298a22041a6270a). The script fails on a
wrong bench reference, a wrong parity value or a missing reference
(fault-injected).
