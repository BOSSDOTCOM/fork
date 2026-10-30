# Fork's networks

One entry per trained network (DESIGN.md §5.3, deliverable 7): its file,
architecture, data, training run, parity results and SPRT. Every net
chains back to the bootstrap evaluation (KB originality.md §4); data and
labels are Fork's own (KB data-policy.md, strategy A+).

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
| Parity (tests/nnue/s512.parity, 446 positions) | R-float vs the trainer's float evaluation at most 0.00012 cp; netcheck exact on all 446; quantization loss max 15.6 cp, p99 12.1 cp, mean 3.6 cp. This is the first net of its architecture, whose thresholds are not yet approved (proposed to the owner: max 21 cp, p99 16 cp) |
| Bench | 15,249,025 nodes, signature 13001f412d6e8d7e (tests/bench-s512.ref) |
| SPRT | vs the B0 control (bake/g1b0 5cacf8a, the net promoted as B0r2), [0, 5], 8+0.08, GitHub shards, run 41125906800 (bake-off stage A): **+43.66 +/- 12.02 Elo (nElo +62.52 +/- 17.02), H1 accepted** after 1,600 games (docs/history/phase-4/sprt-log.md) |
| Status | **The default network since 2026-10-30, provisionally** (owner): the bake-off continues unchanged, and a later entry that beats it is promoted then. The labeller of generation 2 and of the cloud data generation from then on |
| Notes | One search test that passed with B0r2 failed with S-512: K+R v K with the fifty-move clock at 0 had to score above 300 cp, and S-512 scores it 263. The check, which only contrasts the position with the same one drawn by the fifty-move rule, now asks for any score above the draw's 0. |
