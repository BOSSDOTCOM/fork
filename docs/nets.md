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

## Endgame checks

Owner, 2026-11-12 (about 4:40 PM, 5:00 PM and 5:50 PM EST; DESIGN.md decisions log):

- **The integrity/recall gate:** tools/nnue/endgame_check.py's 900 positions, at most 15 misjudged. A gate: it
  catches missing or corrupted slice data (898 of its positions are slice positions, so it measures recall, not
  understanding of endings). tools/nnue/gates.sh enforces it in its exit status for a net trained with the
  endgame slice and reports it only for any other; the calling chain states which in the required
  `SLICE_TRAINED` (1 or 0, no default).
- **The held-out checks** (4-5 pieces, tools/nnue/endgame_heldout.py; 6-7 pieces, tools/nnue/heldout_67.py; 8-12
  pieces, tools/nnue/heldout_deep.py): reported for every candidate and flagged for the owner's review when the
  count is more than 15% worse than the **current default net's** (the net a promotion would replace), never a gate
  on screening or promotion. tools/nnue/gates.sh prints the flag line and, with `HELDOUT_WARM` set, the change
  against the run's warm-start net, for diagnosis.

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
| Scale | S = 90, matched to S512r2's mean \|eval\| on 4,000 g3s1-val positions (S512r2's 217.63 cp against S512+PP's 221.88 at S = 92; the two were swapped here until 2026-11-11, bug review T5); promoted with the scale it was tested at |
| Conversion | 2 of 311,296 link weights clamped to their units' allowance under the reader's 64-link bound (2 of 512 units over it; the owner's fallback); the unclamped net passes every leg with the same losses |
| Parity (tests/nnue/s512pp.parity, 446 positions) | trainer leg at most 0.00018 cp; netcheck exact on all 446; quantization loss max 8.3 cp, p99 6.8 cp, mean 2.2 cp (within S512+PP's limits, S-512's 21 / 16 cp; owner, 2026-11-06) |
| Speed | **0.895 of S512r2's nps** (identical-tree method, 12 rounds 0.873-0.915; bench nps 2,342,208 on a loaded machine): the owner's recorded exception to the 0.90 speed gate (DESIGN.md §5.4; ideas.md idea 40) |
| Endgame check | tools/nnue/endgame_check.py, 900 positions: **351 misjudged against S512r2's 249** (KQK 59 of 300 against 0; KRK 267 against 223). The Syzygy endgame slice in item 7's snapshot g3s2 is meant for this. Held-out check (tools/nnue/endgame_heldout.py, 3,800 positions the slice cannot generate; 2026-11-11): 945 misjudged (S512r2 658). 6-7-piece held-out check (tools/nnue/heldout_67.py, 5,599 positions since 2026-11-11 (one found in training excluded; no count changed), ChessTB WDL; 2026-11-11): 828 misjudged (S512r2 809) |
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
| Endgame check | tools/nnue/endgame_check.py, 900 positions: **8 misjudged (0.9%) against S512+PP's 351** (at the trained S = 92: KQK and KRK 0 of 600, KPK 8 of 300; S512+PP KQK 59, KRK 267, KPK 25). **A recall figure** (bug review T1, 2026-11-11): 898 of the 900 positions are in the slice's files verbatim. Held-out check (tools/nnue/endgame_heldout.py, 3,800 positions the slice cannot generate): **454 misjudged against S512+PP's 945**. 6-7-piece held-out check (tools/nnue/heldout_67.py, 5,599 positions since 2026-11-11 (one found in training excluded; no count changed), ChessTB WDL): 731 misjudged against S512+PP's 828 |
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
| Endgame check | tools/nnue/endgame_check.py, 900 positions: **8 misjudged (0.9%), as S512ppr2** (recall of slice positions, bug review T1). Held-out check (tools/nnue/endgame_heldout.py, 3,800 positions): 514 misjudged. 6-7-piece held-out check (tools/nnue/heldout_67.py, 5,599 positions since 2026-11-11 (one found in training excluded; no count changed)): 723 misjudged |
| Tests | vs S512ppr2 (phase-4 98cf000): fixed nodes, 800,000 per move, run 42426868742: +15.65 +/- 9.26 Elo (nElo +28.80 +/- 17.02), 1,600 games, above the owner's +5 tie-break; then STC 8+0.08 [0, 5], runs 42429984619, 42431412304, 42432793282, 42434196075 and 42435511074: **+7.12 +/- 4.53 Elo (nElo +11.98 +/- 7.61), H1 accepted** after 8,000 games (docs/history/phase-4/sprt-log.md) |
| Bench | 14,149,617 nodes, signature 1cb0717f040c294d (tests/bench-s512ppr3.ref) |
| Status | The default network from 2026-11-07 (owner: promoted on its STC result) until r8btd90 replaced it on 2026-11-10, and the labeller of generation 3's part g3j, generation 4's parts g4 and g4b, and the label-depth arms, which stay on it until they end (owner, 2026-11-10; DESIGN.md §5.3, labeller policy); retrain 8b started from its float weights. Still buildable with `-DFORK_NET=nets/s512ppr3.fnet` (tests/bench-s512ppr3.ref), checked in CI's `nets` job |

## r8btd90, S512ppr3 retrained on g4s1 with TD(0.9) labels (retrain 8b, 2026-11-10)

| Item | Value |
|---|---|
| File | `nets/r8btd90.fnet` (branch bake/r8btd90 115daad, the net that played its tests), 1,426,656 bytes, Fork checksum f7421c4bec5435d5, SHA-256 3d299a38db2fb48e0b0945b59839f53fa45918d2d24a67f76db93075ad27d08d |
| Architecture | Architecture 8, as S512+PP, S512ppr2 and S512ppr3; S = 89 |
| Data | g4s1 (docs/research/retrain-8b/plan.md §1 and its manifests, branch retrain/8b-prep 320c0be): g3s3 unchanged plus the sealed parts g3h, g3i (S512ppr2's labels), g3j and g4 (S512ppr3's), the Syzygy endgame slice kept; validation on g4s1-val (2,160 games) |
| Training | Kaggle kernel fork-retrain-8b at 320c0be (retrain 8b, DESIGN.md §5.6 item 8; idea 51's TD(0.9) arm): the standard recipe from S512ppr3's float weights (LR 0.0001 dropped tenfold after 180, 360 superbatches, seed 1) at result weight 0, on TD(0.9) labels (td_labels.py, S = 92) of g3j's and g4's files, every older file read as its blend copy (the control's target); the network is the window average, the mean of superbatches 331-360's float weights. Full g4s1-val loss (a diagnostic only, plan §1): 0.01980678, against the control's average 0.01982635 and S512ppr3's 0.01988801 |
| Scale | S = 89, matched to S512ppr3's mean \|eval\| on 4,000 g4s1-val positions (213.84 cp against 213.43) |
| Conversion | 1 of 311,296 link weights clamped to its unit's allowance under the reader's 64-link bound (1 of 512 units over it); the unclamped net passes every leg with the same losses |
| Parity (tests/nnue/r8btd90.parity, 446 positions) | trainer leg at most 0.00015 cp; netcheck exact on all 446; quantization loss max 10.6 cp, p99 9.1 cp, mean 2.7 cp (within S-512's 21 / 16 cp) |
| Endgame check | tools/nnue/endgame_check.py, 900 positions: **7 misjudged (0.8%) against S512ppr3's 8** (KPK 7 of 300, KQK and KRK 0 of 600; recall of slice positions, bug review T1). Held-out check (tools/nnue/endgame_heldout.py, 3,800 positions): 526 misjudged against S512ppr3's 514. 6-7-piece held-out check (tools/nnue/heldout_67.py, 5,599 positions since 2026-11-11 (one found in training excluded; no count changed)): 732 misjudged |
| Tests | vs S512ppr3 (phase-4 c67fd26): fixed nodes, 800,000 per move, run 42910703028: +17.39 +/- 9.71 Elo (nElo +30.53 +/- 17.02), 1,600 games, the highest of retrain 8b's four candidate screens; then STC 8+0.08 [0, 5], runs 42917050282, 42919747964 and 42922442883: **+12.17 +/- 5.71 Elo (nElo +20.96 +/- 9.83), H1 accepted** after 4,800 games (docs/history/phase-4/sprt-log.md) |
| Bench | 9,594,307 nodes, signature 4eb36793548711d4 (tests/bench-r8btd90.ref) |
| Status | The default network from 2026-11-10 (owner: promoted on its STC result, about 6:45 PM EST) until r8brft1 replaced it on 2026-11-11 (default 11-10 to 11-11), and the labeller of the cloud slice, which stays on it until it finishes (owner, 2026-11-11; DESIGN.md §5.3, labeller policy; §6, the decisions log); idea 70's result fine-tune started from its window average. Still buildable with `-DFORK_NET=nets/r8btd90.fnet` (tests/bench-r8btd90.ref), checked in CI's `nets` job |

## r8brft1, r8btd90 fine-tuned on the game result (idea 70, 2026-11-11)

| Item | Value |
|---|---|
| File | `nets/r8brft1.fnet` (branch bake/r8brft1 4da54db, the net that played its tests), 1,426,656 bytes, Fork checksum cc1ef83b43b0bad6, SHA-256 501c473ab4dd03f487c9c5ee6c26939ea11687d8a9ae0326144cd441477e4218 |
| Architecture | Architecture 8, as S512+PP, S512ppr3 and r8btd90; S = 88 |
| Data | g4s1 (as r8btd90): arm c's 129 training files, the Syzygy endgame slice included; at result weight 1.0 every copy of a position carries the same target, its stored game result (the slice's, its WDL); validation on g4s1-val |
| Training | Kaggle kernel fork-retrain-8b-rft version 1 at 43f6ecc (idea 70's result fine-tune; docs/research/retrain-8b/rft-plan.md, branch retrain/8b-rft): warm from r8btd90's window average (its float weights), result weight 1.0, LR 1e-5 constant (no drop), 60 superbatches of 305 x 16,384 positions, seed 1; the network is the window average, the mean of superbatches 46-60's float weights. Full g4s1-val loss (a diagnostic only): at the control's blended target 0.02007601 against r8btd90's 0.01980678 (the fine-tune leaves that target), at the result target 0.05818876 against 0.05823161. Seed 2 (r8brft2) passed the same gates and screened +6.73 +/- 9.44 against r8btd90 |
| Scale | S = 88, matched to the base net's mean \|eval\| on 4,000 g4s1-val positions (214.47 cp against 213.84; 224.24 cp at the trainer's S = 92) |
| Conversion | 1 of 311,296 link weights clamped to its unit's allowance under the reader's 64-link bound (1 of 512 units over it); the unclamped net passes every leg with the same losses |
| Parity (tests/nnue/r8brft1.parity, 446 positions) | trainer leg at most 0.00015 cp; netcheck exact on all 446; quantization loss max 10.7 cp, p99 8.4 cp, mean 2.4 cp (within S-512's 21 / 16 cp) |
| Endgame check | tools/nnue/endgame_check.py, 900 positions: **7 misjudged (0.8%), as r8btd90** (recall of slice positions, bug review T1; within the integrity/recall gate, at most 15). Held-out check (tools/nnue/endgame_heldout.py, 3,800 positions; 2026-11-11): **612 misjudged against r8btd90's 526**, the most of the slice-trained nets (queen against two minor pieces 189 of 600, r8btd90 126): **the result fine-tune raised the held-out five-piece errors from 126 to 189**, and future fine-tunes report this set (owner, 2026-11-11; tools/nnue/gates.sh reports it for every candidate, flagged when more than 15% worse than the current default's count, above 1.15 times it, with the change against the run's warm start also reported since 2026-11-12; never a gate). 8-12-piece deep-label check (tools/nnue/heldout_deep.py, human positions labelled by r8brft1's own 10M-node search; 1,337 classed since 2026-11-11 (six positions found in training excluded; no count changed)): **80 misjudged, r8btd90 76, S512ppr3 77, S512ppr2 73, S512+PP 81**: the same order, no pair significant (r8brft1 against S512ppr2 12 to 5 discordant, p = 0.14; docs/research/bug-review-followup-2026-11-11.md). 6-7-piece held-out check (tools/nnue/heldout_67.py, 5,599 positions since 2026-11-11 (one found in training excluded; no count changed), ChessTB WDL): **770 misjudged against r8btd90 732, S512ppr3 723, S512ppr2 731**, significant (against S512ppr2 84 to 45 discordant, p = 0.0008; against r8btd90 58 to 20) |
| Tests | vs r8btd90 (bake/r8btd90 115daad, engine c67fd26): fixed nodes, 800,000 per move, run 42962187538: +7.17 +/- 9.93 Elo (nElo +12.29 +/- 17.02), 1,600 games, the higher of the two seeds' screens; then STC 8+0.08 [0, 5], runs 42974677403, 42976787971, 42979050772, 42981298644, 42983543508, 42985980827 and 42988446282: **+5.74 +/- 3.81 Elo (nElo +9.69 +/- 6.43), H1 accepted** after 11,200 games (docs/history/phase-4/sprt-log.md) |
| Bench | 10,708,227 nodes, signature c5dfc0ec1923d3b0 (tests/bench-r8brft1.ref), the same on the bake branch's engine (c67fd26) and on phase-4's at the promotion (20d83fa) |
| Status | The default network from 2026-11-11 (owner: promoted on its STC result, about 6:35 AM EST) until r8ceplo2 replaced it on 2026-11-14 (default 11-11 to 11-14), and the labeller of the data generation from generation 4's part g4c on, until the labeller switch to r8ceplo2 (locally at the next part, g4d, started 2026-11-14 at 7:59 PM EST; the cloud VM at its next run, pending; one switch per day, no running generator switched; DESIGN.md §5.3, labeller policy; §6, the decisions log). Still buildable with `-DFORK_NET=nets/r8brft1.fnet` (tests/bench-r8brft1.ref), checked in CI's `nets` job |

## r8ceplo2, retrain 8c's control (seed 2) with the endgame-preserving result fine-tune (2026-11-14)

| Item | Value |
|---|---|
| File | `nets/r8ceplo2.fnet` (branch bake/r8ceplo2 29b4d28, the net that played its tests; byte for byte the gated cand.fnet), 1,426,656 bytes, Fork checksum d86c55541d030633, SHA-256 f4634cecaf35d6ba2444b8ebb97d6a3394ef30bf54bb246f7288b83d97d49f5a |
| Architecture | Architecture 8, as S512+PP, r8btd90 and r8brft1; S = 87 |
| Data | g4s2 (docs/research/retrain-8c/plan.md §1, branch retrain/8c-prep): g4s1 plus the parts sealed since (g4b, g4c, the label-depth arms ld-d20, ld-d50 and ld-d100, the cloud filler runs) and a fresh Syzygy endgame slice, TD(0.9) copies of the parts labelled by S512ppr3 or later and blend copies of the older ones (196 training files); validation on g4s2-val. The fine-tune reads the same files with the piece-count mask (rft-ep): the result target only on records with 8 or more pieces, the base's own target kept on records with 7 or fewer, the slices at their WDL |
| Training | Kaggle kernel fork-retrain-8c-a1 at 178f16b (retrain 8c, session A1; plan §2, arms 1 and 4): **the control c, seed 2** (r8cc2): warm from r8btd90's float weights (plan option O4), the standard recipe (LR 1e-4 dropped tenfold after superbatch 180, 360 superbatches of 305 x 16,384 positions, result weight 0 on the label copies), the window average of superbatches 331-360; then **rft-ep-lo, seed 2**: warm from that window average, LR 5e-6 constant, 60 superbatches, the network the mean of superbatches 46-60's float weights. Full g4s2-val loss (a diagnostic only): 0.01969502 at the blended target against the control's 0.01956360 (the fine-tune leaves that target), 0.05711598 at the result target against 0.05714512. Seed 1 (r8ceplo1) passed the same gates |
| Scale | S = 87, matched to r8brft1's mean \|eval\| on 4,000 g4s2-val positions (230.06 cp against 229.47; 243.32 cp at the trainer's S = 92) |
| Conversion | 1 of 311,296 link weights clamped to its unit's allowance under the reader's 64-link bound (1 of 512 units over it); the unclamped net passes every leg with the same losses |
| Parity (tests/nnue/r8ceplo2.parity, 446 positions) | trainer leg at most 0.00014 cp; netcheck exact on all 446; quantization loss max 9.9 cp, p99 7.8 cp, mean 2.5 cp (within S-512's 21 / 16 cp) |
| Endgame check | tools/nnue/gates.sh (SLICE_TRAINED=1, exit 0; ~/fork-data/8c/a1-state/gates-r8ceplo2.log): the integrity/recall gate **8 of 900 misjudged (0.9%), r8brft1 7** (KPK 8 of 300, KQK and KRK 0 of 600; at most 15: passed). Held-out 4-5 pieces (tools/nnue/endgame_heldout.py, 3,800 positions): **525 misjudged against the default r8brft1's 612, ratio 0.858** (not flagged); against its warm start r8cc2 525 against 506 (+19, +3.8%, for diagnosis). Held-out 6-7 pieces (tools/nnue/heldout_67.py, 5,599 positions): **756 against r8brft1's 770, ratio 0.982** (not flagged); against r8cc2 756 against 738 (+18, +2.4%). The 8-12-piece deep-label check (tools/nnue/heldout_deep.py) was not run for this net |
| Tests | Fixed nodes, 800,000 per move, 1,600 games: against its own control r8cc2 (bake/r8cc2 e8f3eca), run 43617323018: +13.47 +/- 9.14 Elo (nElo +25.13 +/- 17.02); rft-ep-lo against the control pooled over both seeds +5.21 +/- 6.39 (3,200 games). No fixed-node screen against r8brft1 (dropped under the promotion safeguard, DESIGN.md §6). Then STC 8+0.08 [0, 5] against r8brft1 (phase-4 b49d6f5; r8ceplo2-promo-stc), runs 43632268487, 43634542473, 43636232270, 43637881329, 43639519074, 43641166102, 43643208644 and 43644837732: **+5.48 +/- 3.32 Elo (nElo +9.94 +/- 6.02), H1 accepted** (LLR 3.95) after 12,800 games (docs/history/phase-4/sprt-log.md) |
| Bench | 5,403,414 nodes, signature 34c916638218aa11 (tests/bench-r8ceplo2.ref), the same on the bake branch's engine (b49d6f5) and on phase-4's at the promotion (63f1fa5) |
| Status | The default network from 2026-11-14 (owner: promotion pre-approved on H1 with the gates passing and no held-out flag; H1 at about 5:12 PM EST) until r3kr1 replaced it the same day (default 2026-11-14 until r3kr1; owner's order, about 7:20 PM EST). The labeller of generation 4's part g4d (arm A, the score adjudication at 1,500 cp over 16 plies; started 2026-11-14 at 7:59 PM EST from a fresh x86-64-v3 PGO build of phase-4 1b5d686, bench-checked), by the one-switch-per-day rule; the cloud VM's switch at its next run is pending (DESIGN.md §5.3, labeller policy; §6, the decisions log). Still buildable with `-DFORK_NET=nets/r8ceplo2.fnet` (tests/bench-r8ceplo2.ref), checked in CI's `nets` job, which also runs its nnue suite: the cases of architecture 8, which the default build (architecture 9) no longer compiles |

## r3kr1, bake-off round 3's option (a): H512+PP, king regions with a refresh cache (2026-11-14)

| Item | Value |
|---|---|
| File | `nets/r3kr1.fnet` (branch bake/r3-kr1 3b40d1e, the net that played its tests; byte for byte the gated cand.fnet), 3,785,952 bytes, Fork checksum 7c1d7d61077e6dbb, SHA-256 a650ef23b15d2cb7797aea7eef909e0c1fc7b47f94aa6ea65c1010352d10dcc8 |
| Architecture | **Architecture 9, H512+PP**, the first default of that architecture: S512+PP's 768 piece inputs per own-king region, four regions (M4, read from the net file's 32-entry map of the mirrored own-king cell: e1 / f1-h1 / rank 2 / ranks 3-8), then the 608 pawn-link inputs of rank limit 1 shared by every region; 512 SCReLU; 8 outputs by game phase; QA 255, QB 64. Trained with a 768-input factoriser, merged into every region when saved (3,680 saved inputs, 4,448 in training). The engine refreshes a perspective whose frame changes lazily, from a per-thread refresh cache (16 frame snapshots, 2 perspectives x 2 file flips x 4 regions, about 18 KB per thread). Design and verification: docs/research/bakeoff-r3/option-a-plan.md (the design report docs/research/bakeoff-r3/king-inputs-design.md on branch proto/r3-king-a); S = 89 |
| Data | Retrain 8c's control files on g4s2 (196 training files: TD(0.9) copies of the parts labelled by S512ppr3 or later, blend copies of the older ones, the fresh Syzygy endgame slice slice1b), result weight 0; validation on g4s2-val |
| Training | Kaggle kernel fork-bakeoff-r3 version 1 (tools/train/kaggle/bakeoff_r3.py at retrain/r3-kr4 b96a514; session A: arm kr1 and its same-recipe S512+PP control pp1 side by side, seed 1, the same data order): warm from **r8ceplo2's float window average** (r8ceplo2-avg.bin, dataset fork-r3-init-8c, SHA-256 4118015e47ca596a966ee29821a43ae613155af9b0c9a95913d6fc81e06f3539) laid out as H512+PP (tools/nnue/extend_weights.py --arch h512pp: regions zero, the factoriser r8ceplo2's piece rows; its float loss equal to r8ceplo2's, 0.02011181, and its quantisation identical, both checked in the session), 8c's control recipe (LR 1e-4 dropped tenfold after superbatch 180, 360 superbatches of 305 x 16,384 positions, S = 92), the window average of superbatches 331-360. Full g4s2-val loss (a diagnostic only): **0.01925385** against the control pp1's 0.01955113 and r8ceplo2's 0.01969502; at the result target 0.05670459 (r8ceplo2 0.05711598). No result fine-tune (rft-ep-lo) was run on it |
| Scale | S = 89, matched to r8brft1's mean \|eval\| on 4,000 g4s2-val positions (230.65 cp against 229.47; 238.44 cp at the trainer's S = 92; the gates' control was r8brft1, the default when the chain was written) |
| Conversion | 1 of 311,296 link weights clamped to its unit's allowance under the reader's 64-link bound (1 of 512 units over it; no unit over the bound by its piece weights alone); the unclamped net passes every leg with the same losses |
| Parity (tests/nnue/r3kr1.parity, 446 positions) | trainer leg at most 0.00019 cp; netcheck exact on all 446; quantization loss max 10.2 cp, p99 7.6 cp, mean 2.2 cp, checked against S-512's limits (21 / 16 cp; architecture 9 has no limits row of its own approved in the table above) |
| Endgame check | tools/nnue/gates.sh (LAYOUT=tools/nnue/h512pp.json, SLICE_TRAINED=1, exit 0; ~/fork-data/r3/state/gates-r3kr1.log): the integrity/recall gate **5 of 900 misjudged (0.6%), r8brft1 7** (KPK 4 of 300, KRK 1 of 300, KQK 0 of 300; at most 15: passed). Held-out 4-5 pieces (tools/nnue/endgame_heldout.py, 3,800 positions): **522 misjudged against the then default r8brft1's 612, ratio 0.853** (not flagged); against its warm start r8ceplo2 522 against 525 (-3, -0.6%). Held-out 6-7 pieces (tools/nnue/heldout_67.py, 5,599 positions): **722 against r8brft1's 770, ratio 0.938** (not flagged); against r8ceplo2 722 against 756 (-34, -4.5%). The 8-12-piece deep-label check was not run for this net. UHO/SF19 diagnostic (report only; ~/fork-data/r3/state/uho-diag.md): adv static +38 cp (r8ceplo2 +42, pp1 +39), levelql static +24 (+24, +23): neither declared movement |
| Speed | Production code, bench/ab_search.py (identical trees on r8brft1kr4, x86-64-v3, WSL, 40 interleaved rounds): **0.941 (0.936-0.947)** of S512+PP's nps (docs/research/bakeoff-r3/option-a-plan.md §5); in-situ in the screens' own games 0.933-0.935. Passes the speed gate's 0.90, misses the 0.95 goal |
| Tests | Fixed nodes, 800,000 per move, 1,600 games: against its same-recipe control r3pp1 (bake/r3-pp1), run 43639332954: **+23.92 +/- 9.12 Elo** (nElo +44.80 +/- 17.02), in-situ r 0.9333, speed-adjusted FN_adj +12.18; against r8brft1 (phase-4 7a7f99b), run 43644769111: +21.09 +/- 8.77 (nElo +41.05 +/- 17.02), r 0.935, FN_adj +9.66. Then STC 8+0.08 [0, 5] against **r8ceplo2** (phase-4 5041eb2; r3kr1-promo-stc, `--kind network`), runs 43649791429, 43651376277, 43652992128 and 43654530597: **+8.04 +/- 4.75 Elo (nElo +14.42 +/- 8.51), H1 accepted** (LLR 3.16) after 4 stages, 6,400 games, Ptnml [42, 739, 1506, 855, 58], no time losses (H1 at about 7:00 PM EST; docs/history/phase-4/sprt-log.md). LTC confirmation against r8ceplo2: ordered as non-blocking, no auto-revert (pending) |
| Bench | 5,205,904 nodes, signature dfe99ebe03b0972d (tests/bench-r3kr1.ref), the same on the bake branch's engine (7a7f99b) and on phase-4's at the promotion (b7ea9bf) |
| TCEC build path | Checked 2026-11-14 on the promoting commit (1ce1a70): `./update.sh` (Release, LTO, `build/tcec/fork`) with FORK_ARCH=x86-64-v3 and x86-64-v4 for each compiler: on Windows (Git Bash) with LLVM-MinGW clang 23.1.3 and WinLibs gcc 16.2.0, and in WSL Ubuntu 22.04 on a clean clone with TCEC's compilers gcc 11.4.0, g++-12 (12.3.0), clang 16.0.6 and clang 19.1.7: all 12 binaries bench 5,205,904 / dfe99ebe03b0972d and perftbench equal to tests/perft_bench.ref, netcheck 0 mismatches on tests/nnue/r3kr1.parity, and scripts/uci-smoke.sh 5 of 5 starts. The labeller's build path (a clang PGO build of fork and fork_datagen for x86-64-v3, cmake/pgo.cmake, clang 19.1.7 in WSL) benches the same and its fork_datagen labels with r3kr1 (40 games, 4,094 positions; tools/datagen/verify_games.py: ok). The nps of these runs were taken on the shared, busy machine and are not a speed measurement |
| Status | **The default network since 2026-11-14** (owner's order, about 7:20 PM EST, after the STC H1). The labeller of new data from the next part boundary on, pending: generation 4's part g4d had already started on r8ceplo2 (7:59 PM EST, that day's switch), so by the one-switch-per-day rule the local data generation switches to r3kr1 at the next part after g4d, not before 2026-11-15, and the cloud VM at its next run (from a fresh build of the promoting commit; whether that run goes straight to r3kr1 or first to r8ceplo2 is the coordinator's call); no running generator is switched (DESIGN.md §5.3, labeller policy; §6, the decisions log) |

## Idea 84's helper nets: r8ceplo2kr4 and r3pp1kr4-s90 (experiment branches only, 2026-11-15)

Not trained: two of Fork's own architecture-8 nets carried to architecture 9 (r3kr1's, H512+PP) so that a
build can embed one beside r3kr1 as the helper threads' network (docs/ideas.md item 84, the owner's plan of
2026-11-15, steps 1-3; CMake FORK_HELPER_NET, branch exp/i84-helper-net). They live on the experiment branches
only (exp/i84-helper-net and the two match branches, exp/i84-h-r8ceplo2 and exp/i84-h-r3pp1), not on phase-4.

| Item | r8ceplo2kr4 | r3pp1kr4-s90 |
|---|---|---|
| File | `nets/r8ceplo2kr4.fnet`, 3,785,952 bytes | `nets/r3pp1kr4-s90.fnet`, 3,785,952 bytes |
| Fork checksum (header, of the payload) | 1dd169031f279226 | 3297846b1a36987e |
| SHA-256 of the file | 0578efed68cbfd8a57dcf1d34501e02e7237bd653177607efc47af800577b81b | bc1abf0867a3b8b4455b8914ea7de62f2ce5d0c52e4f8fa2b410c190ca4c7378 |
| Source net | r8ceplo2 (`nets/r8ceplo2.fnet`, architecture 8, S512+PP; its entry above) | r3pp1, r3kr1's same-recipe S512+PP control (branch bake/r3-pp1; architecture 8) |
| Step | tools/nnue/extend_weights.py --arch h512pp: the piece rows copied into each of the four king regions (the lossless step that made r8brft1kr4 from r8brft1) | the same, then the header's S set from its own 89 to the matched 90 (a header edit; the checksum covers the payload only, so it is unchanged) |
| Header | version 2, architecture 9, 3,680 inputs, 512 hidden, QA 255, QB 64, 8 buckets, **S 87** (its own) | the same with **S 90** |
| Score scale (step 2, tools/nnue/match_scale.py, r3kr1 the control, 4,000 held-out positions) | matched S 87 = its own; mean abs eval 230.06 against r3kr1's 230.65 (-0.26%, within the 2% pass line) | matched S 90 (its own 89); at S 90 mean abs eval 231.5 against 230.65 (+0.37%, within 2%) |
| Bench check (step 1) | equal to r8ceplo2's in an architecture-9 build, per the preparing session (not re-run here) | equal to r3pp1's, per the preparing session (not re-run here) |

The header fields, sizes and checksums above were read from the files with tools/nnue/netformat.py
(`header_fields`, the checksum at byte 40) and `sha256sum`; the score-scale figures are the preparing session's
match_scale.py output. The calibration-agreement gate (step 2's second gate) is recorded with the matches, not
here.

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
