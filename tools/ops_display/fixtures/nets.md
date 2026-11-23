# Networks

## Format

Not a net section.

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
| Status | **The default network since 2026-11-11** (owner: promoted on its STC result, about 6:35 AM EST), and the labeller of the data generation from generation 4's part g4c on; the running label-depth arms stay on S512ppr3 and the cloud slice on r8btd90 until each finishes (DESIGN.md §5.3, labeller policy; §6, the decisions log) |

