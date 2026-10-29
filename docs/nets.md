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
| Parity (tests/nnue/b0.parity, 446 positions) | quantization leg exact; R-float vs bullet's own float evaluation at most 0.00012 cp (kernel fork-eval-t); Fork's inference = R-int on all 446 (embedded netcheck); quantization loss max 11.1 cp, p99 8.8 cp, mean 3.4 cp (thresholds proposed: max 15, p99 12; owner to approve) |
| Bench | 17,320,616 nodes, signature 801e340fab64384d (tests/bench-b0.ref on b0-candidate) |
| SPRT | vs the bootstrap evaluation, [0, 5], 8+0.08: **+486.85 +/- 32.07 Elo, H1 accepted** after 1,600 games (docs/history/phase-4/sprt-log.md) |
| Status | Not yet the default: see the SPRT log's note (two search/UCI tests fail with it; owner decision) |
