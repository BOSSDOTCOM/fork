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
| Status | **The default evaluator since 2026-10-29** (owner; its failing tests were fixed, DESIGN.md §5.3). Bench with today's search: tests/bench-b0.ref |

## B0r1, B0's first retrain (2026-10-29)

| Item | Value |
|---|---|
| File | nets/b0r1.fnet on branch b0r1-candidate, 394,820 bytes, Fork checksum 11bbf22c07979e76 |
| Architecture | B0's (768 -> 256 -> 1, clipped ReLU, QA 255 / QB 64, S = 134: a warm start keeps its net's target scale) |
| Data | generation-0 snapshot g0s2 (data/manifests/g0s2.json): 867,948 games, 82,943,968 positions at 09:17; workers 0-8 for training (each g0s1 shard is a byte prefix of its g0s2 shard), worker 9 held out (its first 20,000 kept positions are the ones B0 validated on); hashes checked on Kaggle before training |
| Training | Kaggle kernel fork-train-b0r1 (T4), tools/train at ea96bc6: warm-started from B0's float weights (SHA-256 checked); before training, superbatch 0 reproduced B0's best validation loss exactly (0.02482651, required within 1e-5); B0's settings otherwise (target 0.5 sigmoid(score / 134) + 0.5 result, AdamW, LR 0.001 dropped tenfold every 40, batch 16,384 x 305 per superbatch, patience 8); best superbatch 19 of 27, validation loss 0.02298352; 234 s of training |
| Parity (tests/nnue/b0r1.parity, 446 positions) | quantization leg exact; R-float vs bullet's float evaluation at most 0.00012 cp; netcheck exact on all 446; quantization loss max 8.6 cp, p99 7.9 cp, mean 2.5 cp (within the B0-class thresholds) |
| SPRT | against B0 (phase-4), [0, 5], 8+0.08, on the GitHub shards: pending |
| Status | Candidate |
