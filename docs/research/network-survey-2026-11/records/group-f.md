# Network records, group F: Quanticade, Igel, PZChessBot, ZigQueen, Devre, JustBot, Titan

Clean-room network survey of 2026-11-14 ([README](../README.md)). Written by survey agent F from public prose only and assembled unchanged except for local paths. Source numbers in brackets refer to the Sources table at the end of this file. Every engine here is REFERENCE ONLY for ideas; its code, nets and data are OFF-LIMITS for Fork.


Opened on 2026-11-14. Ranks and Elo are the coordinator's (CCRL Blitz list computed 2026-11-14). Every fact carries its source number and source type; "prior survey" means the 2026-11-10 survey in the user's repository. Elo figures are the engines' own self-play results unless stated. Time controls are written as the pages write them (seconds + increment).

Reading notes that apply to all sections:

- "STC" and "LTC" are each project's own labels; the time control is repeated beside each result.
- "FN" is a fixed-node test.
- A result marked "unfinished" stopped before its SPRT bound.

---

## Quanticade Cronus 3.0 (CCRL #31, 3716)

**One-line architecture:** `(768->1536x13)x2->(16->32->1)x8`, as the author writes it in the pull request that introduced the multi-layer net [6, PR text #212]. No later PR before the Cronus release changes that string, but no page restates it for the release itself.

### Inputs
- Feature set (what an input means; inputs per perspective if stated): 768 piece-square inputs per king bucket [6, PR text #212]. Inputs per perspective: 768 × 13 = 9,984 (my arithmetic).
- King input buckets: 13, horizontally mirrored [4, release notes Fenrir 1.0; 6, PR text #212]. Layout: not published. How grown: king buckets first (+7.09 ± 3.64 at 40+0.4) [6, PR text #143], refresh of only the side whose king moved (+9.65 ± 4.14 at 8+0.08) [6, PR text #144], then the mirrored net (+24.12 ± 7.24 at 8+0.08) [6, PR text #148].
- Horizontal mirroring (when the king crosses the middle, or other): yes [4, release notes Fenrir 1.0]. The trigger is not described in prose.
- Threat or attack inputs: none in Cronus. They arrive later (see "Since the rated version") [6, PR text #404].
- Pawn features: not published; none named.
- Other input relationships: not published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 1536 [6, PR text #212].
- Further layers: two hidden layers of 16 and 32, then the output [6, PR text #212].
- Layer stacks: 8 copies of the 16 → 32 → 1 head [6, PR text #212]. The selector is not stated in prose.
- Output buckets: 8 [6, PR text #212; 4, release notes Electra 0.9]. Added in #75 (+5.59 ± 3.32 at 8+0.08) [6, PR text #75]. Selector: not published.
- Skip connections, pairwise multiplication, other structure: none stated. The architecture string has no pairwise marker.

### Activations
- After the accumulator: UNVERIFIED (only in code).
- In the head: SCReLU on the second and third layers, from commit titles inside the PR ("screlu on l2 l3") [6, commit titles in PR #212].

### Quantisation
- Integer types per layer: not published. Related prose:
  - the feature weights and biases are rounded inside the engine since the "MSE net" [6, commit message in PR #213];
  - the first dense layer's weight range was narrowed so that its quantisation precision could double (+1.34 ± 1.05 at 8+0.08) [6, PR text #214];
  - that layer's quantisation scale was then raised (+1.70 ± 1.38 at 8+0.08) [6, PR text #215];
  - its values were put in an unsigned 8-bit range with less shifting (+4.60 ± 2.78 at 8+0.08) [6, PR title and text #222];
  - an earlier net came with a "new quantisation" and a retrain (+3.32 ± 2.27 at 40+0.4; STC about +1.8) [6, PR text and commit message #172].
- Quantisation-aware training or other rounding care: not published beyond the items above.

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: "Finny tables", +28.57 ± 7.52 at 8+0.08 [6, PR text #156]. Its updates were then fused, +3.77 ± 2.47 at 8+0.08 [6, PR text #157].
- Lazy or deferred accumulator updates: not in Cronus. Added afterwards, +14.93 ± 5.38 at 4+0.04 [6, PR text #331].
- Fused updates: +11.70 ± 5.98 at 40+0.4 and +11.65 ± 6.33 at 8+0.08 [6, PR text #7].
- Accumulator stack: +9.01 ± 5.23 at 8+0.08 on first merge; after a revert and re-apply, +11.99 ± 5.04 at 8+0.08 with one thread and +25.76 ± 7.57 at 4+0.04 with two threads [6, PR text #56, #66]. A contributor's "accumulator nocopy" change: +10.00 ± 4.35 at 8+0.08 [6, PR text #97; 4, release notes Chimera 1.0].
- Pairwise multiplication of accumulator halves: not stated.
- int8 layers or int8 feature-transformer rows: see Quantisation; the first dense layer's values are kept in an 8-bit range [6, PR title #222].
- Sparse first dense layer: not in Cronus. Added afterwards ("NNZ"): +2.67 ± 1.97 and +3.76 ± 2.59 at 4+0.04, crediting Berserk for the idea; a lookup table and a VBMI2 variant are named in commit titles [6, PR text #328, #329; commit titles in #329, #343].
- Evaluation cache: not published.
- SIMD and VNNI work:
  - first SIMD inference, +27.94 ± 9.65 at 8+0.08 [6, PR text #27];
  - the multi-layer inference has AVX2 and AVX-512 paths, and VNNI is switched off by default [6, commit titles in PR #212];
  - the release notes tell users the AVX-512 binary is faster [4, release notes Chimera 1.1];
  - after Cronus: NEON and ARM dot-product support, "25% speed improvement in bench" on an Apple M1 laptop, tested as a non-regression (+0.96 ± 2.09 at 2+0.02) [6, PR text #330].
- Memory layout and prefetching: not in Cronus. Afterwards: huge pages on Linux, +23.38 ± 7.20 at 2+0.02 with a 512 MB hash ("under the right conditions") [6, PR text #341]; "Prefetch better", +10.21 ± 4.43 at 4+0.04 [6, PR text #428]. Net file size for Cronus: not published.
- Anything else that made the network faster: the Clang build is "a LOT faster" than GCC (0.7 era) [4, release notes 0.7].
- Speed cost or gain reported for any architecture change: the multi-layer net "loses some elo on STC but gains on LTC" (+6.18 ± 3.30 at 40+0.4) [6, PR text #212]. No nps figure.
- Hardware sensitivity reported: the huge-page gain is conditional [6, PR text #341]; nothing else.

### Training data
- Size (positions or games) of the rated net's data: not published.
- Type: Lc0 data. The README at the Cronus tag says the net is trained on Lc0 data, and the release notes call Cronus the last release with it [3, README; 4, release notes Cronus 3.0]. Label details: not published.
- Openings, filtering, tablebase use: not published.

### Training recipe (concepts only)
- Trainer: bullet [3, README credits].
- Loss and target: the loss moved from a higher-power error to plain MSE (+4.00 ± 3.90 at 180+1.8, unfinished; "loses elo at STC, LTC") [6, PR text and commit message #213]. Result blend: not published.
- Stages and schedule: commit titles name nets by superbatch count (100 to 700) and "retrain" steps [6, commit titles in PR #212; commit message in #172]. Nothing more.
- Regularisation, optimiser, anything unusual: not published for Cronus.

### Measured gains for network changes
- Own net replacing a Stockfish net: +152.79 ± 5.38 at 8+0.08 [6, PR text #5]
- `(768->1536)x2->1`: +13.46 ± 6.79 at 40+0.4, +6.51 ± 4.46 at 8+0.08 [6, PR text #6]
- Output buckets: +5.59 ± 3.32 at 8+0.08 [6, PR text #75]
- Same architecture, "better training and more data": +10.56 ± 4.60 at 8+0.08, +12.07 ± 4.78 at 40+0.4 [6, PR text #130]
- King buckets: +7.09 ± 3.64 at 40+0.4 [6, PR text #143]
- Horizontal mirroring: +24.12 ± 7.24 at 8+0.08 [6, PR text #148]
- Multi-layer head: +6.18 ± 3.30 at 40+0.4; loses at STC [6, PR text #212]
- MSE loss: +4.00 ± 3.90 at 180+1.8, unfinished [6, PR text #213]

### Architecture history
- 0.6 (2024-07): a Stockfish net through a probing library [4, release notes 0.6, 0.7].
- 0.7 (2024-07): own net [6, PR text #5]; `(768->1536)x2->1` [6, PR text #6].
- Aurora 0.8 (2024-08): `(768 -> 2048)x2 -> 1` [4, release notes].
- Electra 0.9 (2024-10): `(768->2048)x2->1x8` [4, release notes].
- Fenrir 1.0 (2025-03): 13 mirrored king buckets, more Lc0 data [4, release notes].
- 2025-06: `(768->1536x13)x2->(16->32->1)x8` [6, PR text #212].
- Cronus 3.0 (2025-12-15): "Multi layered NNUE trained on Lc0 data" [4, release notes].

### Since the rated version
- Self-play nets from scratch, 2026-01 onwards [6, PR text #299]. The self-play net replaced the Lc0 net at +14.69 ± 5.25 at 60+0.6 [6, PR text #343].
- Small nets first (a 256-wide step is named), buckets re-added ("buckets are good", +51.79 ± 11.27 at 10+0.1), 1536 wide again (+1.92 ± 1.53 at 60+0.6) [6, PR text #305, #314, #323].
- Data: 1 B positions at 25,000 nodes (+6.49 ± 3.35 at 40+0.4, 4 threads) [6, PR text #368]; 2 B more, of which 1 B adversarial at 5,000 nodes, 0.5 B normal at 25,000 nodes and 0.5 B adversarial DFRC at 5,000 nodes (+6.43 at 10+0.1, +7.79 at 60+0.6, DFRC +59.08) [6, PR text #397]; piece-count filtering (+6.89 at 10+0.1, +8.29 at 60+0.6) [6, PR text #398]; 12 B more positions (+20.40 ± 6.24 at 10+0.1, +19.93 ± 16.81 at 60+0.6) [6, PR text #412]; a relabel plus 3 B positions at 25,000 nodes (+10.81 ± 4.53 at 10+0.1, +13.16 ± 6.66 at 60+0.6, unfinished) [6, PR text #439].
- 16 king buckets: +4.26 ± 4.47 at 40+0.4 with 8 threads [6, PR text #370].
- L1 regularisation: +3.19 ± 2.20 at 10+0.1, +1.30 ± 1.92 at 60+0.6 [6, PR text #371].
- Threat inputs with a 768-wide accumulator: +7.66 ± 3.67 at 60+0.6 [6, PR text #404]. Speed work on them: a branchless threat index ("5 elo VSTC") and delta ray-casting ("14 elo VSTC") [6, PR text #402, #403].
- 1024-wide accumulator: +1.52 ± 4.56 at 20+0.2 with 8 threads, unfinished, merged on the author's judgement that it scales [6, PR text #440].
- The development README now says "NNUE trained on selfplay data" [2, README].

### UNVERIFIED and not published
- King bucket layout; output bucket selector; accumulator activation; integer types per layer: UNVERIFIED (only in code).
- Whether Cronus's net is exactly the net of PR #212 to #222: UNVERIFIED (no page says which net the release ships).
- Data size, label budget, filtering, result blend, schedule: not published.
- Cronus net file size: not published.

---

## Igel 3.8.0 (CCRL #32, 3714)

**One-line architecture:** `2x(22528 + 60144 -> 1024) -> 16 -> 32 -> 1` with "HalfKAv2_hm + FullThreats", 32 mirrored king buckets, 8 output buckets and 8 PSQT buckets, as the README at tag 3.8.0 writes it [9, README]. Caveat: the same lines already stand in the README at tag 3.7.0 [10, README], whose release notes say the standard network was reverted to a 2023 network [11, release notes 3.7.0]. So the README's lines did not track every net change, and no release note or PR states the architecture of 3.8.0's net by name. The net's file size supports the README (see Memory layout). This resolves, with that caveat, the prior survey's UNVERIFIED on threats [1, prior survey].

### Inputs
- Feature set: "HalfKAv2_hm" king-bucketed piece-square inputs, 22,528 per perspective, plus "FullThreats", 60,144 per perspective [9, README]. 22,528 = 32 × 704 (my arithmetic).
- King input buckets: 32, horizontally mirrored [9, README]. Layout: not published.
- Horizontal mirroring: yes [9, README].
- Threat or attack inputs: the FullThreats set, 60,144 inputs [9, README]. What a threat encodes and how it is updated: not described in Igel's own prose.
- Pawn features: none named.
- Other input relationships: 8 PSQT buckets [9, README].
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 1024 [9, README].
- Further layers: 16, then 32, then the output [9, README].
- Layer stacks: not stated separately from the output buckets.
- Output buckets: 8 [9, README]. Selector: not published.
- Skip connections, pairwise multiplication, other structure: PSQT path with 8 buckets [9, README]. Pairwise: not stated.

### Activations
- After the accumulator: UNVERIFIED (only in code).
- In the head: UNVERIFIED (only in code).

### Quantisation
- Integer types per layer: not published.
- Quantisation-aware training or other rounding care: not published.

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: two items in the release notes. "implement finny table" (3.7.0; idea credited to Luecx in Koivisto; no figure in the PR) [11, release notes 3.7.0; 14, PR title #331]. "cache accumulator" (3.8.0): +13.81 ± 4.19 at 10+0.1 [11, release notes 3.8.0; 14, PR text #361]. The prior survey's "+13.8 refresh cache" is this second item [1, prior survey].
- Lazy or deferred accumulator updates: not published.
- Fused updates: not published.
- Accumulator stack: not published.
- Pairwise multiplication of accumulator halves: not published.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: not published.
- Evaluation cache: not published.
- SIMD and VNNI work:
  - AVX-512 and VNNI-512 support: the AVX-512 VNNI build of 3.6.7 against the AVX2 build of 3.6.6 scored +14.3 ± 7.1 at 6+0.06 (two versions, so not a pure instruction-set comparison) [14, PR text #317];
  - "speed-up inferencing code": +4.7 ± 5.4 at 6+0.06 on non-regression bounds [14, PR text #318];
  - VNNI-256 support: +1.4 ± 1.9 at 2.5+0.025 on [-1, 1] bounds [14, PR text #338];
  - AVX2 is the baseline of every released binary; AVX-512, VNNI-512 and AVX-VNNI builds exist [9, README].
- Memory layout and prefetching: the network is embedded in GCC and Clang builds [9, README]. Net file: 105 MB for 3.8.0's network (asset `6b953e78.standard`, uploaded 2026-09-19) [12, release asset list; 11, release notes 3.8.0]. A 22,528 × 1024 table of 16-bit weights alone is about 46 MB, so 105 MB fits a net with a large second input block (my arithmetic, not a published statement).
- Anything else that made the network faster: PGO builds with Clang give "the fastest binary" [9, README].
- Speed cost or gain reported for any architecture change: none.
- Hardware sensitivity reported: `pext` is slower on Zen 1 and Zen 2 (move generation, not the network) [9, README].

### Training data
- Size (positions or games) of the rated net's data: not published. Older generations: ign-0 2.3 B at depth 8 plus 500 M at depth 12; ign-1 12 B at depth 8 plus 1 B at depth 12; ign-2 and ign-3 more than 30 B at depths 5, 8 and 16 [10, README at 3.4.0].
- Type: own. "Using Igel evaluation and search data" [9, README]; own network on Igel data since late 2020 [9, README; 15, CPW]. The 2020 rules: evaluation, search and PV come only from Igel, starting from the hand-crafted 2.6.0; versions 2.7.0 and 2.8.0 (a third-party net) are excluded [10, README at 3.4.0]. Labels: fixed-depth searches in the generations listed above.
- Openings, filtering, tablebase use: not published.

### Training recipe (concepts only)
- Trainer: nnue-pytorch is acknowledged [9, README]; the prior survey records Stockfish's feature set and trainer [1, prior survey].
- Loss and target: one earlier net was the previous net retrained "with a different lambda", that is, a changed blend between search score and game result [11, release notes 3.2.0].
- Stages and schedule: not published. A PR names a net by epoch number [14, PR text #326].
- Regularisation, optimiser, anything unusual: not published.

### Measured gains for network changes
- 3.8.0's network (PR "3.7.5: release new standard network"): +13.56 ± 4.26 at 10+0.1, +19.26 ± 4.90 at 60+0.6, +19.79 ± 4.95 at 90+0.9 [14, PR text #358]
- 3.6.14 network: +15.2 ± 7.3 (VSTC), +2.4 ± 1.9 (STC), +3.9 ± 3.1 (LTC), +4.0 ± 3.1 (VLTC) [14, PR text #326]; later reverted to the 2023 net, the revert itself testing at −1.09 ± 1.55 at 10+0.1 [14, PR text #339]
- 3.5.0 architecture: +11.12 ± 5.68 at 10+0.1, +4.43 ± 3.16 at 60+0.6 [14, PR text #276]; eval scaling +5.81 at 10+0.1, +14.20 at 60+0.6 [14, PR text #277]
- 3.3.0 architecture: +27.44 at 3+0.03, +34.07 at 10+0.1, +41.87 at 60+0.6 [14, PR text #271]

### Architecture history
- 2.7.0 to 2.8.0 (2020): a third-party net [9, README].
- ign-0, ign-1 (2020 to 2022): `halfkp_256x2-32-32` [10, README at 3.4.0].
- 3.3.0 (2023-01): ign-2, `halfkav2_512x2-16-32` [10, README at 3.4.0].
- 3.4.0 (2023-01): ign-3, `halfkav2_hm_1024x2-8-32`; pure NNUE [10, README at 3.4.0; 11, release notes 3.4.0].
- 3.5.0 (2023-06): "new network architecture", net c049c117 [11, release notes 3.5.0].
- 3.7.0 (2026-08): AVX-512, finny table, a new standard net and then a revert to c049c117 [11, release notes 3.7.0]. The README at this tag already lists 32 mirrored buckets and FullThreats [10, README at 3.7.0].
- 3.8.0 (2026-10-18): new standard network 6b953e78, accumulator cache [11, release notes 3.8.0].

### Since the rated version
- New standard network 5adc00b8 (105 MB): +19.65 ± 5.10 at 10+0.1, +18.72 ± 4.76 at 60+0.6, +23.03 ± 5.37 at 90+0.9 [14, PR text #371; 12, release asset list].
- "speed up nnue and prefetch": +8.83 ± 5.03 at 3+0.03 [14, PR text #372].
- "speed up nnue and move ordering": +10.65 ± 5.55 at 3+0.03 [14, PR text #373].
- NUMA support with a new network: +1.96 ± 1.38 at 10+0.1, +4.17 ± 2.15 at 60+0.6, +5.02 ± 2.82 at 90+0.9 (unfinished) [14, PR text #375]. A "universal" network file of 105 MB was uploaded on 2026-11-10 [12, release asset list].

### UNVERIFIED and not published
- That 6b953e78 is a threat-input net: stated by the tagged README only, with the caveat above; supported by the 105 MB file size. No page says it by network name.
- King bucket layout, output bucket selector, activations, pairwise, integer types: UNVERIFIED (only in code).
- Data size, depths, filtering and recipe of the 3.8.0 net: not published.
- What the 3.7.0 "finny table" and the 3.8.0 "cache accumulator" each cache: not published.

---

## PZChessBot 7.1 (CCRL #33, 3711)

**One-line architecture:** `(768x12hm->1280)x2pw->(16->32->1)x8`, as the README at tag v7.1 writes it [18, README]. The net is PZNet53, published with the same string [20, release notes pznet53; 22, PR title #341].

### Inputs
- Feature set: 768 piece-square inputs per king bucket, horizontally mirrored ("hm") [18, README]. Inputs per perspective: 768 × 12 = 9,216 (my arithmetic).
- King input buckets: 12 [18, README]. Layout: not published. How grown, from the network log and PRs:
  - 1 → 2 (+20.78 ± 8.54 at 8+0.08) [22, PR text #180];
  - 4 (+13.66 ± 6.61 at 8+0.08) [22, PR text #190];
  - 8: failed at 8+0.08 (−0.65 ± 3.07), +1.68 ± 1.72 at 40+0.4 (unfinished), +5.85 ± 3.88 at 120+1.2, +5.45 ± 3.71 at 360+3.6 [22, PR text #267];
  - 10 (+3.38 ± 2.69 at 8+0.08) [22, PR text #331];
  - 12 with PZNet53; no figure in the PR [20, release notes; 22, PR #341].
- Horizontal mirroring: yes [18, README]. First added at +24.30 ± 9.72 at 8+0.08 [22, PR text #86]; re-added after the retrain from scratch at +17.52 ± 8.36 [22, PR text #167].
- Threat or attack inputs: none in 7.1. Added afterwards (see below).
- Pawn features: none.
- Other input relationships: none stated.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 1280 [18, README].
- Further layers: 16, then 32, then the output [18, README]. A review summary on the PR calls it a three-layer network [22, PR comment #306].
- Layer stacks: 8 copies of the 16 → 32 → 1 head [18, README].
- Output buckets: 8 [18, README]. Selector: "material output buckets" in the commit title that first added them [22, commit title in PR #34]; not restated for 7.1.
- Skip connections, pairwise multiplication, other structure: pairwise multiplication of the accumulator ("pw") [18, README; 22, PR title #303].

### Activations
- After the accumulator: pairwise multiplication; a commit title says the accumulator is clipped beforehand [22, commit title in PR #306].
- In the head: a single SCReLU between the first and second head layers in 7.1 [22, PR text #357, describing the state before its change].

### Quantisation
- Integer types per layer: not published. Commit titles in the multi-layer PR mention floats, FMA and a VNNI reduction, so part of the head is float and a VNNI path exists; which layers is not stated [22, commit titles in PR #306].
- Quantisation-aware training or other rounding care: not published.

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: "finny-like tables", +14.92 ± 7.14 at 8+0.08 (2025-09) [22, PR text #125]; rebuilt in the lazy-update overhaul below.
- Lazy or deferred accumulator updates: one PR rebuilt the update system with incremental lazy updates, finny tables and fused updates together: +11.78 ± 5.93 at 4+0.04 [22, PR text and commit titles #294].
- Fused updates: in the same PR [22, commit titles in PR #294].
- Accumulator stack: copy-make board, "~3% speedup", +7.92 ± 5.39 at 4+0.04 on non-regression bounds [22, PR text #291].
- Pairwise multiplication of accumulator halves: +1.06 ± 2.96 at 8+0.08 on non-regression bounds [-5, 0], before the multi-layer head existed [22, PR text #303].
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: not published.
- Evaluation cache: not published.
- SIMD and VNNI work:
  - vectorised evaluation, +7.39 ± 4.93 at 8+0.08 [22, PR text #54];
  - removing an extraneous computation in inference, +10.20 ± 5.41 at 8+0.08 [22, PR text #259];
  - the multi-layer PR adds an AVX2 and AVX-512 abstraction, loop unrolling of the first two head layers and alignment fixes [22, commit titles and PR comment #306];
  - ARM (NEON) support, checked under emulation, speed not measured [22, PR text #333];
  - binaries: AVX-512, AVX2 with pext, a no-pext build for Zen 2, NEON [19, release notes v7.1].
- Memory layout and prefetching:
  - huge pages by `madvise`: +6.20 ± 4.18 at 2+0.02 with 4 threads and a 2048 MB hash; the "collapse" form lost [22, PR text #324];
  - NUMA first-touch allocation of thread data: "approx speedup: 4% on NUMA systems" [22, PR text #321];
  - pinning threads to NUMA nodes: +25.04 ± 10.73 at 1+0.01 with 192 threads [22, PR text #348].
- Anything else that made the network faster: PGO, +7.61 ± 4.61 at 8+0.08 [22, PR text #304]. A Windows fix worth about 30% speed in v5.0 [19, release notes v5.0].
- Speed cost or gain reported for any architecture change:
  - multi-layer head: +8.55 ± 5.00 at 8+0.08, +16.02 ± 7.06 at 40+0.4 [22, PR text #306];
  - 1024 → 1280 wide: +7.21 ± 4.45 at 40+0.4 [22, PR text #323];
  - no nps figures for either.
- Hardware sensitivity reported: the Zen 2 no-pext binary [19, release notes v7.1]; NUMA gains only on NUMA machines [22, PR text #321].

### Training data
- Size (positions or games) of the rated net's data: not published as a total. The project's OpenBench instance lists its data-generation runs from 2026-04-04. The runs created before PZNet53 (2026-06-18) produced about 90.1 M games (my sum of 17 runs, 616 to 890) [24, OpenBench]. Whether all of them, or older data from before that instance, trained PZNet53 is not stated. Position counts: not published.
- Type: own self-play, "trained from zero-knowledge" [18, README], from a random network since v4.0 [19, release notes v4.0; 22, commit title in PR #163]. Labels come from the self-play searches at a soft node limit: 5,000 in most runs, 10,000 and 20,000 in some [24, OpenBench].
- Openings, filtering, tablebase use: opening books UHO_Lichess_4852_v1, a DFRC book and, in one run of 1.0 M games, an endgame book; the position-generation arguments are "filter 1 nmoves 8" [24, OpenBench]. An earlier PR text says games begin with random opening moves, "typically 12 per game" [22, PR text #261]. An "opening filtering" step appears as a commit title [22, commit title in PR #163]. Tablebase use in data generation: not published.

### Training recipe (concepts only)
- Trainer: bullet [18, README].
- Loss and target: not published for PZNet53. One net in the cycle was a fine-tune on game results only ("seems to scale well"; +0.80 ± 3.91 at 40+0.4 and +1.29 ± 3.03 at 120+1.2, both unfinished) [22, PR text #329].
- Stages and schedule: not published.
- Regularisation, optimiser, anything unusual: not published.

### Measured gains for network changes
- Self-play net from a random start against the Lc0-data net of v3.0: +158 ± 8 at 8+0.08, +134 ± 12 at 60+0.6 (whole release) [19, release notes v4.0]
- Retrain from scratch, v5.0: +120 STC, +90 LTC (whole release) [19, release notes v5.0]
- Scratch ladder, each at 8+0.08: 64 wide +72.68; output buckets +25.15; 128 wide +63.92; mirroring +17.52; next width +59.85; 512 wide +34.37; 1024 wide +3.32 ± 3.37 (unfinished, merged) [22, PR text #164 to #172]
- PZNet40: +6.11 at 8+0.08, +7.95 at 40+0.4 [22, PR text #265]
- Multi-layer head: +8.55 at 8+0.08, +16.02 at 40+0.4 [22, PR text #306]
- 1280 wide: +7.21 ± 4.45 at 40+0.4 [22, PR text #323]
- PZNet48: +11.85 ± 6.03 at 8+0.08, +10.36 ± 5.49 at 40+0.4 [22, PR text #325]
- 10 buckets: +3.38 ± 2.69 at 8+0.08 [22, PR text #331]
- Early separate endgame net: "around 20 ELO" [22, PR text #47]; removed when king buckets arrived (+54.31 ± 14.82 at 8+0.08) [22, PR text and commit titles #60]

### Architecture history
- 2025-03: first NNUE [22, PR text #23]; trained on a public Lc0-derived binpack [22, PR text #28].
- 2025-04 to 06: 256 wide, material output buckets, a separate endgame net, king buckets, 512 wide [22, PR text #30, #34, #47, #60, #66].
- 2025-10 (v4.0, v5.0): self-play from a random net; `(768hm->1024)x2->1x8` by PZNet25 [19, release notes; 20, release notes pznet25].
- 2025-10 to 2026-02: 2, then 4 mirrored buckets; PZNet41 `(768x8->1024)x2->1x8` [20, release notes pznet29 to pznet41].
- 2026-04: PZNet42 adds pairwise; PZNet43 `(768x8hm->1024)x2pw->(16->32->1)x8` [20, release notes].
- 2026-05-07: v7.0 [19, release notes].
- 2026-05-23: PZNet47, 1280 wide; 2026-05-30: PZNet50, 10 buckets; 2026-06-18: PZNet53, 12 buckets [20, release notes].
- 2026-06-27: v7.1 [19, release notes].

### Since the rated version
- Dual activation in the head (PZNet55, `16x2`): the first head layer's output goes through both a clipped ReLU and a squared clipped ReLU, so the next layer sees 32 inputs at "minimal" extra cost; no test figure in the PR [22, PR text #357; 20, release notes pznet55].
- 16 input buckets: +1.86 ± 2.83 at 8+0.08, unfinished, merged [22, PR text #370].
- Threat inputs (PZNet59, `(768x16hm+60144->512)x2pw->(16x2->32->1)x8`): 60,144 inputs of (attacker, its colour and square, victim, its colour and square); "~30% slowdown"; FN +43.34 ± 11.64, +3.93 ± 2.78 at 8+0.08, +14.91 ± 6.08 at 40+0.4; the refresh cache was switched off for simplicity; implementation details credited to Viridithas [22, PR text #371; 20, release notes pznet59].
- 768 wide with threats (PZNet60): FN +25.56, −4.01 ± 4.29 at 8+0.08 (failed), +5.72 ± 3.49 at 40+0.4 [22, PR text #373].
- Threat speed work: splitting the threat and piece-square accumulators, +27.92 ± 8.55 at 4+0.04 [22, PR title and text #376]; then deferred threat discovery, accumulator updates tiled in SIMD registers, fewer attack lookups, compact feature indices, king-bucket reuse and huge pages for the weights: +16.80% nps over 20 paired runs (+14.86% over 8 depth-14 pairs), +22.28 ± 7.53 at 4+0.04 [22, PR text and commit message #378].
- 1024 wide (PZNet63): FN +9.92, −1.73 ± 3.11 at 8+0.08 (failed), +4.92 ± 3.20 at 40+0.4 [22, PR text #383].
- Smaller speedups: not zero-filling a container, "~5%", +8.13 ± 5.06 at 4+0.04 [22, PR text #354]; avoiding a second accumulator copy, +2.58 ± 3.15 at 4+0.04 on non-regression bounds [22, PR text #356].
- Development architecture today: `(768x16hm+60144->768)x2pw->(16x2->32->1)x8` in the README [17, README]; the newest nets (PZNet63 to 65) are 1024 wide [20, release notes].

### UNVERIFIED and not published
- King bucket layout; integer types per layer; which head layers are float: UNVERIFIED (only in code).
- Output bucket selector for 7.1: a 2025 commit title says material; not restated.
- Data total, position count, result blend, schedule: not published.
- PZNet53's own test result: not in its PR.

---

## ZigQueen 6.5.0 (CCRL #34, 3709)

**One-line architecture:** mirrored HalfKA with 16 king buckets, 60,144 threat features and 1,488 pawn-pair features (1,278 live) into a 1024-wide feature transformer; eight material buckets, each `1024 → 16 → 32 → 1`; a PSQT head. This is the engine's own table [26, NETWORK.md]. 6.5.0 ships 6.4.0's network unchanged [29, release notes 6.5.0].

### Inputs
- Feature set: three sparse input families per perspective [26, NETWORK.md; 28, ARCHITECTURE.md]:
  - king-bucketed piece-square inputs (HalfKA), 16 × 768 = 12,288 rows [33, trainer README];
  - 60,144 threat inputs;
  - 1,488 pawn-pair inputs.
  Deployed rows: 73,920 [33, trainer README].
- King input buckets: 16. Each perspective picks its bucket from its own king square after mirroring files e to h onto a to d (black's frame is rank-flipped). Layout on the four files a to d: rank 1 has one bucket per file; rank 2 has one bucket per file; rank 3, rank 4, ranks 5 to 6 and ranks 7 to 8 each have two buckets, one for files a to b and one for c to d [26, NETWORK.md]. How grown: the 6.0.0 to 6.3.0 nets had 8 buckets (rank 1 split a-b and c-d, rank 2 split the same way, then one bucket each for rank 3, rank 4, ranks 5 to 6 and ranks 7 to 8), described as the common layout of bullet-trained engines; 6.4.0 split each of the eight in two. The map is stored in the net file, not fixed in the engine [27, PROVENANCE.md].
- Horizontal mirroring: when the own king stands on files e to h the board is mirrored [26, NETWORK.md].
- Threat or attack inputs: a feature is (attacker, attacker square, victim, victim square) for an attack under the current occupancy. Attackers are pawns to queens; kings are never victims; four redundant pairs are left out (pawn on bishop, pawn on queen, bishop on queen, rook on queen); both directions of a mutual attack count, which differs from Stockfish's rule. 60,144 = 2 × 30,072. The index order is the project's own (attacker, its square, the target's place in the attacker's empty-board attack set, victim class) [26, NETWORK.md; 27, PROVENANCE.md]. Updates: a move changes threats away from its own squares, so the changed features are found per changed square. Pawns and knights change only their own features on that square. Sliders are read in "ray space": the board is held as eight rays per square in vector registers, and the first blocker on each ray comes from byte arithmetic (credited to 87flowers, as used in Stormphrax). Updating around the changed squares is credited to Stockfish. Threat rows depend on the mirror but not on the king bucket [28, ARCHITECTURE.md; 27, PROVENANCE.md].
- Pawn features: "PP1" pawn pairs. An unordered pair of pawns of either colour on ranks 2 to 7 whose files differ by at most one: 480 same-file rows and 1,008 adjacent-file rows. The 210 rows that duplicate a pawn-on-pawn threat stay zero (Stockfish drops the duplicate threats instead), leaving 1,278 live rows, at most 120 active per perspective. They depend on the mirror but not on the king bucket, and change only when a pawn set changes [26, NETWORK.md; 27, PROVENANCE.md; 28, ARCHITECTURE.md].
- Other input relationships: a per-feature PSQT head shared by the eight output buckets [27, PROVENANCE.md].
- Factoriser or other training-only input structure: a 768-row factoriser in the trainer (74,688 trainer rows against 73,920 deployed) [33, trainer README].

### Body
- First hidden layer (accumulator) width per perspective: 1024 [26, NETWORK.md].
- Further layers: 16, then 32, then the output [26, NETWORK.md].
- Layer stacks: eight, one per material bucket [26, NETWORK.md].
- Output buckets: eight, selected by material [26, NETWORK.md].
- Skip connections, pairwise multiplication, other structure: clipped ReLU with pairwise multiplication of the accumulator halves, so the first dense layer sees 1024 inputs from two 1024-wide perspectives; the PSQT head is added to the output [27, PROVENANCE.md; 28, ARCHITECTURE.md].

### Activations
- After the accumulator: clipped ReLU, then pairwise multiplication [27, PROVENANCE.md].
- In the head: squared clipped ReLU after the first dense layer [27, PROVENANCE.md]. After the second: not stated.

### Quantisation
- Integer types per layer: piece-square rows int16; threat and pawn-pair rows int8; accumulators int16; first dense layer int8 (run with VNNI or ARM dot-product) [26, NETWORK.md; 27, PROVENANCE.md; 28, ARCHITECTURE.md]. Later layers: not stated. All arithmetic is integer and gives the same evaluation on every build [25, README].
- Quantisation-aware training or other rounding care: the whole network was finished with QAT. Every layer runs through the engine's integer arithmetic in the trainer, with straight-through gradients; the 8-bit weights are clamped to their deployed range during this stage [26, NETWORK.md; 33, trainer README]. Evidence given: with head-only QAT on the same float run, held-out error rose 2.8% from float to deployed, mostly in the feature transformer; the shipped net's deployed held-out error is 1.9% below that sibling's. At export the engine's evaluation matched an exact reference on 3,934 positions, and a range check rules out overflow [26, NETWORK.md]. The earlier head-only QAT (6.2.0) read +9 ± 8 Elo in 2,000 games, SPRT unresolved [38, release notes 6.2.0].

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: a king move that changes the bucket syncs from a per-bucket refresh cache, diffed against the mailbox. A king move across the d/e files rebuilds the mirrored threat half from a separate "flip cache" [28, ARCHITECTURE.md]. No figure.
- Lazy or deferred accumulator updates: updates are deferred until a node evaluates; nodes that cut off before a static evaluation skip them [28, ARCHITECTURE.md]. No figure.
- Fused updates: one pass per move and perspective applies the piece-square, threat and pawn-pair rows together [28, ARCHITECTURE.md]. No figure.
- Accumulator stack: not described beyond "no heap allocation" and fixed-size arrays [28, ARCHITECTURE.md].
- Pairwise multiplication of accumulator halves: yes. An "AVX2 pair layout" change gave +3.1% nodes per second on a Zen 3 CPU, exact output [37, STRENGTH.md at v6.4.0].
- int8 layers or int8 feature-transformer rows: threat and pawn-pair rows int8, first dense layer int8 [26, NETWORK.md]. No separate figure.
- Sparse first dense layer: not stated. The notes mention a grouped AVX2 first-layer dot product and a "row-blocked first-layer finisher" [32, release validation 6.3.0].
- Evaluation cache: yes, separate from the TT. It holds raw static evaluations of positions the TT evicted: 8-way sets of 8-byte entries in one 64-byte line, sized at a quarter of the hash setting within fixed bounds, private to each thread [28, ARCHITECTURE.md]. No figure.
- SIMD and VNNI work:
  - portable vector code lowers to AVX-512, AVX2 or NEON with a scalar fallback [28, ARCHITECTURE.md];
  - 6.3.0 speed pass, time for identical work at one thread on a Ryzen 5 7600X3D, Windows 11, no large pages: AVX2 −3.6% (tablebases off) and −5.4% (on); AVX-512 −7.7% and −8.2%. Part of the AVX-512 gain is that its network kernels now run 512 bits wide; the compiler's default tuning for that target had kept them at 256. An earlier measurement before that step: 1.9 to 3.3% on a Ryzen 9 9950X3D with large pages [32, release validation 6.3.0];
  - the same pass: threat updates touch only the attacker groups a move changes; hot functions aligned to 64 bytes [32, release validation 6.3.0];
  - 6.2.0: threat bookkeeping with dense pointers and direct reads of the stored threat words, +1.5% [38, release notes 6.2.0];
  - 6.0.0: the incremental threat accumulator plus nine optimisation rounds, about +21% node throughput on AVX2 [38, release notes 6.0.0];
  - 6.5.0: "about 20% faster, with the same search"; the named pieces are the ray-space threat updates, threat updates around the changed squares and PGO builds; no per-piece figures [29, release notes 6.5.0; 27, PROVENANCE.md].
- Memory layout and prefetching: huge pages for the network weights, TT, eval cache, histories and search context; cache-line layouts for accumulators and weights; prefetch of TT and hint-table entries at make time (no network-row prefetch is described) [28, ARCHITECTURE.md]. Net file 88,724,892 bytes, embedded [26, NETWORK.md]. An option shares one copy of the weights between processes, about 90 MB saved per extra process [29, release notes 6.5.0].
- Anything else that made the network faster: PGO release builds, relinked from LTO bitcode with context-sensitive PGO [28, ARCHITECTURE.md].
- Speed cost or gain reported for any architecture change: the 6.4.0 net (16 buckets instead of 8, plus pawn pairs) searches about 4% fewer positions per second than 6.3.0 and gained 15 to 23 Elo in self-play; the binary grew by about 14 MB [30, release notes 6.4.0].
- Hardware sensitivity reported: some older Intel CPUs slow down under AVX-512, so AVX2 may be faster there [31, release notes 6.3.0]. Speed numbers from the Zen 4 and Zen 5 machines must not be compared [32, release validation 6.3.0]. ARM speed was not measured [32, release validation 6.3.0].

### Training data
- Size (positions or games) of the rated net's data: 131,124,072,315 positions kept, of 225,520,878,403 rows read from 42 published components (about 701 GB of downloads); 7,998,177 held out [26, NETWORK.md; 34, data-r2 README]. The float run read 590,246,838,272 samples, about 4.5 passes; QAT read two passes over the first 21 billion records [26, NETWORK.md].
- Type: Lc0 and Stockfish-project training data relabelled with Lc0 BT4 evaluations, taken from published collections. No self-play. The project relabelled nothing; every training score is a fixed function of a published score [26, NETWORK.md; 34, data-r2 README]. Several components carry a 5,000-node budget in their published names [26, NETWORK.md].
- Openings, filtering, tablebase use: rows removed, in order: scores at the top of the published range (7.04%); positions before ply 16 (4.82%); positions whose recorded move is a capture, promotion, castling or en passant (16.08%); side to move in check (5.80%); extreme scores after rescaling (8.12%); held-out keys (0.004%). 58.14% kept. No deduplication. Components are mixed by quota, not by size [34, data-r2 README]. Tablebases: no score of the rated net's data was replaced by a tablebase value [34, data-r2 README]. The tablebase rescoring the prior survey records belongs to the 6.2.0 head continuation only (exact scores at five pieces or fewer and 223 six-piece anchors) [38, release notes 6.2.0; 1, prior survey].

### Training recipe (concepts only)
- Trainer: bullet with the project's own patches (threat and pawn-pair inputs, deployed-arithmetic QAT, seeded initialisation); the data loader is the project's own [26, NETWORK.md; 33, trainer README].
- Loss and target: a constant blend, mostly the teacher score passed through a sigmoid, with a small share of the game result [26, NETWORK.md]. Held-out error is reported as MSE [26, NETWORK.md].
- Stages and schedule: from seeded random weights; a float run of 5,902 superbatches of about 100 M samples in two cosine phases (4,721 then 1,181); then 330 superbatches of full-network QAT continuing the weights and optimiser state. The endpoint was fixed in advance and no checkpoints were averaged. The 6.3.0 net instead averaged 13 late checkpoints and then ran head-only QAT [26, NETWORK.md; 35, NETWORK.md at v6.3.0]. Compute: one RTX 5080, 375,179 s for the float run and 37,642 s for QAT [26, NETWORK.md].
- Regularisation, optimiser, anything unusual: AdamW [33, trainer README]. The PSQT head starts from conventional piece values [33, trainer README]. Candidate nets are screened for colour symmetry and material ordering before games; training loss alone does not promote a net [35, NETWORK.md at v6.3.0]. A pawn-pair pilot with a scrambled control is mentioned without results [33, trainer README].

### Measured gains for network changes
- 6.4.0 net (16 buckets, pawn pairs, full QAT) against the 6.3.0 net: +15 to +23 Elo in self-play, about 4% slower [30, release notes 6.4.0]. The prior survey files this under pawn pairs alone; the source gives one figure for the whole net [1, prior survey].
- 6.3.0 net (same architecture, 42 components instead of 27): +10.8 ± 7.5 at 8+0.08 (2,554 games), +7.9 ± 6.0 at 60+0.6 (3,368 games) [35, NETWORK.md at v6.3.0]
- Head-only QAT continuation (6.2.0): +9 ± 8, SPRT unresolved [38, release notes 6.2.0]
- Full-network QAT against head-only QAT: deployed held-out error 1.9% lower; no Elo figure [26, NETWORK.md]
- AVX2 pair layout: +3.1% nodes per second [37, STRENGTH.md at v6.4.0]
- 6.3.0 speed pass with one small search change: +8.4 ± 6.3 at 8+0.08, +17.1 ± 9.7 at 20+0.2, +11.3 ± 7.4 at 60+0.6 [37, STRENGTH.md at v6.4.0]
- External gauntlets (own estimates): 6.3.0 3676, 6.4.0 3701, 6.5.0 3717 against a stronger field [36, STRENGTH.md]

### Architecture history
- 5.x (2026-07): a smaller "lean" threat set of 7,680 inputs, attacker square dropped [27, PROVENANCE.md].
- 6.0.0 (2026-08-19): 8 mirrored buckets, 60,144 threats, width 1024, eight `1024 -> 16 -> 32 -> 1` stacks; 74,587,732 bytes; 27 components [38, release notes 6.0.0; 26, NETWORK.md].
- 6.2.0 (2026-09-09): head continued with QAT for 1.07 B positions [38, release notes 6.2.0].
- 6.3.0 (2026-09-25): same architecture, retrained from scratch on 42 components; checkpoint averaging, head-only QAT [35, NETWORK.md at v6.3.0].
- 6.4.0 (2026-10-10): 16 buckets, pawn pairs, full-network QAT; 88,724,892 bytes [26, NETWORK.md].
- 6.5.0 (2026-10-21): same network; speed rework [29, release notes 6.5.0].

### Since the rated version
- Nothing found. The repository's README is headed 6.5.0 [25, README].

### UNVERIFIED and not published
- Activation after the second dense layer; integer types of the second and third layers: not stated.
- Whether the first dense layer skips zero inputs (sparse iteration): not stated.
- Per-technique gains inside the 6.5.0 speed rework: not published.
- The network diagram in the architecture document is an image and predates the 16 buckets; not opened.

---

## Devre 7.0 (CCRL #35, 3704)

**One-line architecture:** `(768x12 + 4560) -> 1024x2 -> 16 -> 32 -> 1`, as the README at tag v7.0 writes it [42, README]. The release notes agree: 13,776 inputs into 1024, 12 king buckets, 8 output buckets [44, release notes 7.0].

### Inputs
- Feature set: king-bucketed piece-square inputs over 12 mirrored buckets (768 × 12 = 9,216) plus 4,560 pawn-pair inputs; 13,776 in all [42, README; 44, release notes 7.0].
- King input buckets: 12, mirrored [42, README]. Layout: not published. How grown: Devre 6.0 had no buckets, `(768->1536)x2->1` [44, release notes 6.0].
- Horizontal mirroring: yes ("12 mirrored buckets") [42, README].
- Threat or attack inputs: none in 7.0. Added afterwards (see below).
- Pawn features: 4,560 pawn-pair inputs [42, README]. Which pairs they cover: not published.
- Other input relationships: none stated.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 1024 [42, README].
- Further layers: 16, then 32, then the output [42, README].
- Layer stacks: not stated separately; the output head "is picked from 8 material buckets" [42, README].
- Output buckets: 8, by material [42, README].
- Skip connections, pairwise multiplication, other structure: each accumulator is combined pairwise into 512 activations [42, README].

### Activations
- After the accumulator: pairwise multiplication [42, README]. The clipping form is not stated.
- In the head: not published. Devre 6.0 used SCReLU on its single layer [44, release notes 6.0].

### Quantisation
- Integer types per layer: not published.
- Quantisation-aware training or other rounding care: not published.

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: not stated for 7.0. A later commit title reads "Fused NNUE accumulator with Finny table" [46, commit title in PR #81].
- Lazy or deferred accumulator updates: "Lazy Update", +3.86 ± 2.43 at 10+0.1 [46, PR text #65].
- Fused updates: see the later commit title above.
- Accumulator stack: not published.
- Pairwise multiplication of accumulator halves: yes [42, README]; no separate figure.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: not published.
- Evaluation cache: not published.
- SIMD and VNNI work: builds for AVX-512, AVX2 and SSSE3 [42, README]. "NNUE Speed-up": "%3.74 speed increase" [46, PR text #57]. "Optimize nnue" (2026-07): no description and no figure [46, PR #73].
- Memory layout and prefetching: the net is embedded in the binary [42, README]. Nothing else.
- Anything else that made the network faster: nothing stated.
- Speed cost or gain reported for any architecture change: the new architecture (king buckets, pawn pairs, pairwise, multi-layer head) was about neutral at short time control (+0.39 ± 4.45 at 10+0.1, unfinished) and +24.10 ± 6.63 at 60+0.6 [46, PR text #68]. No nps figure.
- Hardware sensitivity reported: none.

### Training data
- Size (positions or games) of the rated net's data: not published. A Hugging Face dataset repository named in a commit message holds ten data files, 7.97 GB in all, uploaded three to four months before today, one of them labelled DFRC; it has no dataset card [46, commit message in PR #75; 47, Hugging Face]. A later PR names a data set of 15.5 M games at 5,000 nodes [46, PR text #81]; whether that is the data behind 7.0's net is UNVERIFIED.
- Type: own self-play. "Switched to built-in self-play data generation" [44, release notes 7.0]; "self-generated training data" [42, README]. Earlier nets used Lc0 data: more than 2 billion positions in 4.0 and 5.0, Lc0 data again in 6.0 [44, release notes 4.0; 43, README at v5.0 and v6.0]. Whether any Lc0 data remains in 7.0's net: UNVERIFIED, as in the prior survey [1, prior survey].
- Openings, filtering, tablebase use: not published.

### Training recipe (concepts only)
- Trainer: bullet [42, README]. Earlier versions used the author's own CUDA trainer [44, release notes 4.0].
- Loss and target: not published for 7.0.
- Stages and schedule: not published for 7.0.
- Regularisation, optimiser, anything unusual: not published for 7.0. The PR for the new architecture attaches a trainer configuration file and two images; none was opened [46, PR #68].

### Measured gains for network changes
- New architecture (12 buckets, pawn pairs, pairwise, 16 → 32 head): +0.39 ± 4.45 at 10+0.1, +24.10 ± 6.63 at 60+0.6 [46, PR text #68]
- Switch to self-generated data: no figure in the PR [46, PR #75]
- 7.0 against 6.0 overall: +113.63 ± 7.65 at 30+0.3 [44, release notes 7.0]
- 6.0-cycle nets: +10.38 ± 4.65 and +8.15 ± 4.00 (time control 10+0.1 where given) [46, PR text #21, #24]

### Architecture history
- 3.0 (2022): `768 -> (512x2) -> 1` [46, PR title #6].
- 4.0 and 5.0 (2022 to 2023): `32*768 -> (512x2) -> 1`, 2 billion Lc0 positions, own CUDA trainer [43, README at v5.0; 44, release notes 4.0].
- 6.0 (2024-08): `(768->1536)x2->1`, SCReLU [44, release notes 6.0].
- 2026-03: the new architecture [46, PR text #68].
- 2026-08-05: self-generated data [46, PR title #75].
- 7.0 (2026-08-07) [44, release notes 7.0].

### Since the rated version
- Threat inputs: three input blocks, 768 × 12 piece-square, 4,560 pawn pairs and 59,808 threats, 73,584 inputs into 768, then pairwise, 16, 32 and one output; output buckets removed; +30.60 ± 7.40 at 60+0.6; inference and architecture "inspired by" PlentyChess and Stockfish [46, PR text #79].
- A larger net distilled from the author's own transformer teacher: +21.65 ± 6.38 at 30+0.3. The teacher has 6 layers, width 256, 8 heads and 2.84 M parameters, takes the 64 squares as input, and was trained on 15.5 M games of 5,000-node data; it is "+180 elo better than main at 1k node". The student is trained from scratch on the teacher's labels alone for 1,000 superbatches of 100 M positions, then fine-tuned for 500 more with a small result share that ramps in [46, PR text #81].
- Development architecture today: `(768x12 + 4560 pawn-pairs + 59808 Threat Inputs) -> 1024x2 -> 32 -> 32 -> 1` [41, README].

### UNVERIFIED and not published
- King bucket layout; pawn-pair definition; head activations; integer types: UNVERIFIED (only in code).
- Data size, node budget, openings and filtering of 7.0's net: not published.
- A commit message inside PR #75 describes a README update to a "768->2048x2 SCReLU" net [46, commit message in PR #75], which does not match the README at the v7.0 tag two days later. The tagged README and the release notes agree with each other and are followed here; the commit message is unexplained.
- Whether Lc0 data remains in the 7.0 net: UNVERIFIED (not stated).

---

## JustBot 0.5.0 (CCRL #36, 3703)

**One-line architecture:** assembled, not the engine's own string: 768 piece-square inputs × 4 horizontally mirrored king buckets into a 1024-wide single hidden layer, with output buckets. Assembled from PR titles [50, release notes 0.3.0 to 0.5.0], and from the name and size of the net the release test used, `754a4ib-1024`, 6.03 MB [56, OpenBench test 823; 53, release asset list]. The README does not describe the network [49, README].

### Inputs
- Feature set: piece-square inputs with king buckets; counts are not written anywhere. 768 × 4 inputs of 1024 16-bit weights is 6.29 million bytes, 6.0 MiB, which fits the 6.03 MB file (my arithmetic).
- King input buckets: 4 [52, PR title #163]. Layout: not published. How grown: mirroring first (+7.97 ± 4.03 at 8+0.08, +7.71 ± 3.72 at 40+0.4) [52, PR text #88]; 3 buckets (+2.56 ± 1.96 at 8+0.08) [52, PR text #93]; 4 buckets with more games (FN +14.54 ± 5.52 at 40,000 nodes, +5.74 ± 3.16 at 8+0.08, +8.72 ± 3.94 at 40+0.4) [52, PR text #163].
- Horizontal mirroring: yes [52, PR title #88].
- Threat or attack inputs: none stated.
- Pawn features: none stated.
- Other input relationships: none stated.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 1024 [52, PR title #136].
- Further layers: none in 0.5.0; the multi-layer net comes after the release [52, PR title #177].
- Layer stacks: none.
- Output buckets: present since 0.3.0 (+44.89 ± 9.97 at 8+0.08) [52, PR text #62]. Count and selector: not published.
- Skip connections, pairwise multiplication, other structure: none stated.

### Activations
- After the accumulator: UNVERIFIED (only in code).
- In the head: no head in 0.5.0.

### Quantisation
- Integer types per layer: not published. The file size fits 16-bit first-layer weights (my arithmetic above).
- Quantisation-aware training or other rounding care: not published.

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: "Finny Tables and Some SIMD Intrinsics", +2.74 ± 1.90 at 8+0.08 [52, PR text #101].
- Lazy or deferred accumulator updates: +3.01 ± 2.13 at 8+0.08 [52, PR text #96].
- Fused updates: +5.88 ± 3.23 at 8+0.08 [52, PR text #95].
- Accumulator stack: not published.
- Pairwise multiplication of accumulator halves: not stated.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: not applicable to a single-layer net; not stated.
- Evaluation cache: not published.
- SIMD and VNNI work: optimisations to the output function, +16.75 ± 5.58 at 8+0.08 [52, PR text #102]. Builds: AVX-512 ("the fastest"), AVX2, generic, NEON [49, README].
- Memory layout and prefetching: "TT Prefetching and Other Minor Optimizations", regression test +4.15 ± 4.27 at 8+0.08 (not network specific) [52, PR text #129]. Unchecked look-ups and aligned node counters: +38.88 ± 10.71 at 4+0.04 and +21.66 ± 8.35 at 20+0.2, both with 4 threads [52, PR text #143]. Net file 6.03 MB [53, release asset list].
- Anything else that made the network faster: nothing stated.
- Speed cost or gain reported for any architecture change: the 1024-wide net failed at short time control (−4.85 ± 3.40 at 8+0.08) and passed at 40+0.4 (+8.91 ± 4.02) [52, PR text #136]. The 768-wide net before it: +10.05 ± 4.54 at 8+0.08, +18.29 ± 5.87 at 40+0.4 [52, PR text #105].
- Hardware sensitivity reported: none.

### Training data
- Size (positions or games) of the rated net's data: not published as a total. The project's OpenBench instance lists every data-generation run. The runs up to the one the rated net is named after (run 754) produced 102,935,610 games (my sum of 20 runs) [55, OpenBench]. Which of them trained the rated net is not stated. PR titles say each net was "re-trained with additional games", one of them with 6 million more [50, release notes 0.5.0]. Position counts: not published.
- Type: own self-play, generated through OpenBench, starting from the PeSTO evaluation [49, README; 50, release notes 0.1.0, 0.2.0; 1, prior survey]. Labels come from the self-play searches at a node limit per move: 40,000 in the first runs, then 20,000, 10,000 and 5,000 (runs from 2026-08 to mid 2026-09), and 12,000 in the two runs just before the rated net; "soft" node limits from run 704 on [55, OpenBench].
- Openings, filtering, tablebase use: runs up to 704 use no opening book; the engine makes its own random openings [55, OpenBench; 50, release notes 0.2.0]. Runs 725 and 754 use the UHO_Lichess_4852_v1 book [55, OpenBench]. A labelling bug fix gained +12.95 ± 5.65 at 8+0.08 [52, PR text #43]. On the run pages I read in full, tablebase adjudication is listed as optional and tablebase WDL as disabled [55, OpenBench]. Filtering: not published.

### Training recipe (concepts only)
- Trainer: bullet; game records are converted with a tool from another engine's author [49, README].
- Loss and target: not published.
- Stages and schedule: not published; whether each retrain starts from the previous net is not stated.
- Regularisation, optimiser, anything unusual: not published.

### Measured gains for network changes
- First NNUE (16 wide) replacing PeSTO: +210.61 ± 29.03 at 8+0.08 [52, PR text #24]
- 512 wide: +17.06 ± 6.51 at 8+0.08 [52, PR text #61]
- Output buckets: +44.89 ± 9.97 at 8+0.08 [52, PR text #62]
- More games from the newest generator: +6.24 at 8+0.08, +7.96 at 40+0.4 [52, PR text #75]
- Mirroring: +7.97 at 8+0.08, +7.71 at 40+0.4 [52, PR text #88]
- "Restructured network": +6.85 ± 3.51 at 8+0.08 [52, PR text #89]
- 3 buckets: +2.56 ± 1.96 at 8+0.08 [52, PR text #93]
- 768 wide: +10.05 at 8+0.08, +18.29 at 40+0.4 [52, PR text #105]
- 6 million more games: +4.17 ± 2.65 at 8+0.08, +7.86 ± 3.73 at 40+0.4 [52, PR text #135]
- 1024 wide: −4.85 at 8+0.08, +8.91 at 40+0.4 [52, PR text #136]
- 4 buckets and more games: FN +14.54, +5.74 at 8+0.08, +8.72 at 40+0.4 [52, PR text #163]

### Architecture history
- 0.1.0 (2026-06): PeSTO evaluation [50, release notes].
- 0.2.0 (2026-06): 16, 32, 64, then 128 wide [50, release notes].
- 0.3.0 (2026-07): 256 and 512 wide, output buckets [50, release notes].
- 0.4.0 (2026-08): mirroring, 3 buckets, fused and lazy updates, finny tables, 768 wide [50, release notes].
- 0.5.0 (2026-09-24): 1024 wide, 4 buckets [50, release notes].

### Since the rated version
- 8 buckets: +12.30 ± 4.83 at 8+0.08, +13.27 ± 4.98 at 40+0.4 [52, PR text #173].
- Multi-layer net: FN +24.12 ± 7.17, +5.90 ± 3.25 at 8+0.08, +14.79 ± 5.30 at 40+0.4 [52, PR text #177]. Net file 12.1 MB [53, release asset list].
- 10 buckets: FN −0.70 ± 2.13, +1.82 ± 1.46 at 8+0.08, +3.06 ± 2.14 at 40+0.4 [52, PR text #179]. Net file 15.1 MB [53, release asset list].
- 16 buckets: soft nodes +12.88 ± 5.19, +6.73 ± 3.51 at 8+0.08, +8.01 ± 3.77 at 40+0.4 [52, PR text #187]. Net file 24.1 MB [53, release asset list].
- Data generation moved to runs of 25 million games and to 25,000 nodes per move in the newest runs [55, OpenBench].

### UNVERIFIED and not published
- The architecture string itself: assembled from PR titles and a file name, not stated by the engine.
- Output bucket count and selector; king bucket layout; activation; integer types: UNVERIFIED (only in code).
- That the net's name means "data up to run 754": my reading of the matching numbers, not a published statement.
- Position count, filtering, result blend, schedule: not published.

---

## Titan 1.1.0 (CCRL #37-38, 3702)

**One-line architecture:** assembled: a single-layer, king-bucketed, horizontally mirrored NNUE with SCReLU. The first three properties are the author's own words in the 1.0 release notes [59, release notes 1.0]; SCReLU is from a PR title [61, PR title #85]. 1.1.0 is a bug-fix release a month later [59, release notes 1.1]. No page gives a width or a bucket count.

### Inputs
- Feature set: not described beyond "king bucketed" [59, release notes 1.0].
- King input buckets: present; count and layout not published. Added with the mirrored net: +14.72 ± 7.60 at 40+0.4, +3.66 ± 3.26 at 8+0.08 [61, PR text #167].
- Horizontal mirroring: yes [59, release notes 1.0].
- Threat or attack inputs: none stated.
- Pawn features: none stated.
- Other input relationships: none stated.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: not published.
- Further layers: none ("single-layer") [59, release notes 1.0].
- Layer stacks: none.
- Output buckets: not published.
- Skip connections, pairwise multiplication, other structure: none stated.

### Activations
- After the accumulator: SCReLU, with a different net, +111.25 ± 19.55 at 8+0.08 [61, PR title and text #85]. The release notes mention an earlier activation of the author's own that was superseded [59, release notes 1.0].
- In the head: no head.

### Quantisation
- Integer types per layer: not published. One commit message line in the SIMD PR says a quantisation scale was changed [61, commit message in PR #126].
- Quantisation-aware training or other rounding care: not published.

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: not stated. A branch label on the unrolling PR suggests an accumulator cache was tried [61, PR page #170]; nothing more.
- Lazy or deferred accumulator updates: "Lazy acc", a "pure speedup patch", +13.07 ± 6.80 at 8+0.08; then applied to the AVX-512 code [61, PR text #161, #162].
- Fused updates: not stated.
- Accumulator stack: the accumulator moved from the board to a stack, which avoids copies and avoids updating it for illegal moves: +6.72 ± 4.75 at 8+0.08 ("I was kind of hoping for more") [61, PR text #114].
- Pairwise multiplication of accumulator halves: not stated.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: not applicable; not stated.
- Evaluation cache: not published.
- SIMD and VNNI work:
  - "Faster simd": +7.87 ± 5.24 at 8+0.08 [61, PR text #126];
  - helping the compiler unroll the accumulator updates: +10.27 ± 6.12 at 8+0.08 [61, PR text #169];
  - two builds: one relies on compiler auto-vectorisation; the other uses hand-written AVX-512 code and needs a nightly compiler [58, README].
- Memory layout and prefetching: 64-byte alignment tested as a non-regression, −0.22 ± 2.67 at 8+0.08 [61, PR text #120]. TT prefetch +7.01 ± 4.95 at 8+0.08 (not the network) [61, PR text #92].
- Anything else that made the network faster: nothing stated.
- Speed cost or gain reported for any architecture change: none with an nps figure.
- Hardware sensitivity reported: the AVX-512 build is expected to crash on CPUs without AVX-512 [58, README]. ZigQueen's testers report that Titan's published binary crashed on their Zen 3 machine [37, STRENGTH.md at v6.4.0].

### Training data
- Size (positions or games) of the rated net's data: not published.
- Type: Lc0 data [59, release notes 1.0]. The current README credits Lc0 for the data and a third-party tool for filtering and converting it [57, README; 1, prior survey]. Labels: those of the Lc0 data; details not published.
- Openings, filtering, tablebase use: filtering by the third-party tool [57, README]; its settings are not published.

### Training recipe (concepts only)
- Trainer: bullet [57, README].
- Loss and target: not published.
- Stages and schedule: not published.
- Regularisation, optimiser, anything unusual: not published.

### Measured gains for network changes
- SCReLU with a new net: +111.25 ± 19.55 at 8+0.08 [61, PR text #85]
- New net: +7.05 ± 4.75 at 8+0.08 [61, PR text #153]
- Mirrored king-bucket net: +14.72 ± 7.60 at 40+0.4, +3.66 ± 3.26 at 8+0.08 [61, PR text #167]

### Architecture history
- 2023-10 to 12: first NNUE, SIMD, SCReLU [61, PR titles #14, #38, #85].
- 2024-03: new net [61, PR text #153].
- 2024-04: mirrored king-bucket net [61, PR text #167].
- 1.0 (2024-05-07), 1.1.0 (2024-06-09) [59, release notes].

### Since the rated version
- Removal of unnecessary accumulator copies, a non-functional speedup, no figure [61, commit message in PR #185].
- Nets moved to a separate repository, and a new net "trained on significantly more data": +5.16 ± 3.04 at 8+0.08 [61, PR text #186].
- A further net step: +4.54 ± 2.78 at 8+0.08 [61, PR text #187].

### UNVERIFIED and not published
- Accumulator width, king bucket count and layout, output buckets, integer types: UNVERIFIED (only in code).
- Data size, filter settings, result blend, schedule: not published.
- Whether the README's data credits (written after 1.1.0) describe the 1.1.0 net's pipeline exactly: UNVERIFIED; the README at the 1.1.0 tag has no credits section [58, README].

---

## Sources

All opened on 2026-11-14. The complete URL list with HTTP codes is in the agent's scratch folder (437 lines; two lines stand for the 43 index pages of each OpenBench instance).

| # | URL | What it is | Source type | Engines |
|---|---|---|---|---|
| 1 | the agent's scratch folder (engines.md, sources.md, comparison.md, and the lines for these engines in README.md, ranking.md, provenance.md, precedents.md) | the 2026-11-10 survey | prior survey | all |
| 2 | https://raw.githubusercontent.com/Quanticade/Quanticade/HEAD/README.md | README, development branch | README | Quanticade |
| 3 | https://raw.githubusercontent.com/Quanticade/Quanticade/Cronus-3.0/README.md | README at the rated tag | README | Quanticade |
| 4 | https://github.com/Quanticade/Quanticade/releases and `?page=2` | release notes, 0.6 to Phoenix dev | release notes | Quanticade |
| 5 | https://github.com/Quanticade/Quanticade/pulls?q=is%3Apr+is%3Aclosed&page=1 to 19 | PR titles (435) | PR / issue / commit text | Quanticade |
| 6 | https://github.com/Quanticade/Quanticade/pull/N for N = 5, 6, 7, 27, 56, 66, 75, 97, 130, 143, 144, 148, 156, 157, 172, 177, 178, 191, 212 to 215, 222, 282, 299, 301 to 317, 320 to 323, 325 to 331, 333, 337, 341, 343, 368, 370, 371, 373, 395, 397, 398, 401 to 404, 412, 422, 427, 428, 439, 440 | PR conversation pages: title, description, comments, commit titles and messages | PR / issue / commit text | Quanticade |
| 7 | https://github.com/Quanticade/Networks/releases ; README at HEAD (404) | network repository: release text, asset names and sizes | release notes | Quanticade |
| 8 | https://raw.githubusercontent.com/vshcherbyna/igel/HEAD/README.md | README, development branch | README | Igel |
| 9 | https://raw.githubusercontent.com/vshcherbyna/igel/3.8.0/README.md | README at the rated tag | README | Igel |
| 10 | the same README at tags 3.7.0, 3.6.0, 3.5.0, 3.4.0, 3.3.0, 3.1.0, 3.0.0 | older READMEs | README | Igel |
| 11 | https://github.com/vshcherbyna/igel/releases | release notes 3.0.0 to 3.8.0 | release notes | Igel |
| 12 | https://github.com/vshcherbyna/igel/releases/tag/0.8 and `/releases/expanded_assets/0.8` | the release that stores network files: asset names, sizes, dates | release notes | Igel |
| 13 | https://github.com/vshcherbyna/igel/pulls?q=is%3Apr+is%3Aclosed&page=1 to 15 | PR titles (332) | PR / issue / commit text | Igel |
| 14 | https://github.com/vshcherbyna/igel/pull/N for N = 270, 271, 272, 276, 277, 313, 317, 318, 326, 331, 338, 339, 358, 361, 371 to 375 | PR conversation pages | PR / issue / commit text | Igel |
| 15 | https://www.chessprogramming.org/Igel | CPW page | CPW | Igel |
| 16 | https://talkchess.com/viewtopic.php?p=974676 | forum thread page; ends 2025-01, nothing on 3.8.0; not used | forum | Igel |
| 17 | https://raw.githubusercontent.com/kevlu8/PZChessBot/HEAD/README.md | README, development branch | README | PZChessBot |
| 18 | https://raw.githubusercontent.com/kevlu8/PZChessBot/v7.1/README.md | README at the rated tag | README | PZChessBot |
| 19 | https://github.com/kevlu8/PZChessBot/releases | release notes v1.0 to v7.1 | release notes | PZChessBot |
| 20 | https://raw.githubusercontent.com/kevlu8/PZChessBot-Networks/HEAD/README.md ; https://github.com/kevlu8/PZChessBot-Networks/releases and `?page=2` to `4` | network log: one architecture string per net | release notes | PZChessBot |
| 21 | https://github.com/kevlu8/PZChessBot/pulls?q=is%3Apr+is%3Aclosed&page=1 to 16 | PR titles | PR / issue / commit text | PZChessBot |
| 22 | https://github.com/kevlu8/PZChessBot/pull/N for N = 23, 28, 30, 34, 36, 47, 54, 60, 66, 86, 88, 125, 163 to 169, 172, 180, 190, 259, 261, 265, 267, 291, 294, 303, 304, 306, 308, 321 to 325, 329, 330, 331, 333, 341, 348, 354, 356, 357, 370, 371, 373, 376, 378, 383 | PR conversation pages | PR / issue / commit text | PZChessBot |
| 23 | https://ob.int0x80.ca/index/ and `/index/1` to `/index/43` | the project's OpenBench index (used only to find the run pages) | OpenBench or fishtest | PZChessBot |
| 24 | https://ob.int0x80.ca/datagen/N/ for N = 616, 617, 618, 643, 644, 645, 661, 662, 684, 688, 703, 733, 744, 772, 776, 830, 871, 882, 890, 966, 984, 989, 1012, 1022, 1032, 1036, 1049, 1094, 1114, 1129, 1165 | data-generation run pages: net, node limit, book, games | OpenBench or fishtest | PZChessBot |
| 25 | https://raw.githubusercontent.com/stierms/zigqueen/HEAD/README.md | README (6.5.0) | README | ZigQueen |
| 26 | .../zigqueen/HEAD/docs/NETWORK.md | network document | other (project document) | ZigQueen |
| 27 | .../zigqueen/HEAD/docs/PROVENANCE.md | provenance record | other (project document) | ZigQueen |
| 28 | .../zigqueen/HEAD/docs/ARCHITECTURE.md | architecture document | other (project document) | ZigQueen |
| 29 | .../zigqueen/HEAD/docs/RELEASE_NOTES_6.5.0.md | release notes | release notes | ZigQueen |
| 30 | .../zigqueen/HEAD/docs/RELEASE_NOTES_6.4.0.md | release notes | release notes | ZigQueen |
| 31 | .../zigqueen/HEAD/docs/RELEASE_NOTES_6.3.0.md | release notes | release notes | ZigQueen |
| 32 | .../zigqueen/HEAD/docs/RELEASE_VALIDATION_6.3.0.md | release checks and speed measurements | other (project document) | ZigQueen |
| 33 | .../zigqueen/HEAD/docs/trainer/README.md | prose description of the trainer patches (the patches were not opened) | README | ZigQueen |
| 34 | .../zigqueen/HEAD/docs/data-r2/README.md | data alterations record | README | ZigQueen |
| 35 | .../zigqueen/v6.3.0/docs/NETWORK.md | network document at 6.3.0 | other (project document) | ZigQueen |
| 36 | .../zigqueen/HEAD/docs/STRENGTH.md | gauntlet results | other (project document) | ZigQueen |
| 37 | .../zigqueen/v6.4.0/docs/STRENGTH.md | gauntlet and acceptance tables at 6.4.0 | other (project document) | ZigQueen, Titan |
| 38 | .../zigqueen/HEAD/docs/RELEASE_NOTES_6.2.0.md, _6.1.0.md, _6.0.0.md | older release notes | release notes | ZigQueen |
| 39 | .../zigqueen/HEAD/docs/README.md, ORIGINALITY.md, docs/PERFORMANCE_PRINCIPLES.md, RELEASE_VALIDATION_6.4.0.md, TUNING.md, ANDROID.md (searched for three words), v6.2.0/docs/NETWORK.md (searched for history lines); fetched and not read: QUALITY_GATES.md, v6.3.0/docs/STRENGTH.md; 404: RELEASE_VALIDATION_6.5.0.md | other project documents | other (project document) | ZigQueen |
| 40 | https://github.com/stierms/zigqueen/releases | release page (same text as the documents; 5.8.x commit messages) | release notes | ZigQueen |
| 41 | https://raw.githubusercontent.com/OmerFarukTutkun/Devre/HEAD/README.md | README, development branch | README | Devre |
| 42 | https://raw.githubusercontent.com/OmerFarukTutkun/Devre/v7.0/README.md | README at the rated tag | README | Devre |
| 43 | the same README at tags v6.0 and v5.0 | older READMEs | README | Devre |
| 44 | https://github.com/OmerFarukTutkun/Devre/releases | release notes 1.0 to 7.0 | release notes | Devre |
| 45 | https://github.com/OmerFarukTutkun/Devre/pulls?q=is%3Apr&page=1 to 5 | PR titles | PR / issue / commit text | Devre |
| 46 | https://github.com/OmerFarukTutkun/Devre/pull/N for N = 6, 18, 19, 21, 24, 57, 65, 68, 73, 75, 79, 81 | PR conversation pages | PR / issue / commit text | Devre |
| 47 | https://huggingface.co/datasets/DevreChess/Datagen , `/tree/main` , https://huggingface.co/DevreChess | dataset page (no card), file names and sizes, organisation page | other (dataset page) | Devre |
| 48 | https://github.com/OmerFarukTutkun/DevreNets/releases (no releases); README at HEAD (404); https://github.com/DevreChess (404) | network repository | other | Devre |
| 49 | https://raw.githubusercontent.com/HasanFakih21/JustBot/HEAD/README.md and `/v0.5.0/README.md` (same size) | README | README | JustBot |
| 50 | https://github.com/HasanFakih21/JustBot/releases | release notes 0.1.4-beta to 0.6.0-dev | release notes | JustBot |
| 51 | https://github.com/HasanFakih21/JustBot/pulls?q=is%3Apr&page=1 and 2 | PR titles | PR / issue / commit text | JustBot |
| 52 | https://github.com/HasanFakih21/JustBot/pull/N for N = 24, 43, 44, 61, 62, 74, 75, 88, 89, 92, 93, 95, 96, 101, 102, 105, 129, 135, 136, 143, 163, 173, 177, 179, 187 | PR conversation pages | PR / issue / commit text | JustBot |
| 53 | https://github.com/HasanFakih21/JustBot-Networks/releases and `/releases/expanded_assets/Networks`; README at HEAD (404) | network repository: asset names, sizes, dates | release notes | JustBot |
| 54 | https://ob.justchess.xyz/index/ and `/index/1` to `/index/43` | the project's OpenBench index (used only to find the run pages) | OpenBench or fishtest | JustBot |
| 55 | https://ob.justchess.xyz/datagen/N/ for N = 2, 12, 20, 52, 54, 116, 176, 277, 279, 346, 409, 540, 541, 553, 595, 638, 704, 725, 731, 754, 797, 802, 844, 875, 938, 969, 983, 1081, 1100 | data-generation run pages | OpenBench or fishtest | JustBot |
| 56 | https://ob.justchess.xyz/test/N/ for N = 536, 549, 550, 737, 738, 739, 823 | test pages: title, networks, result | OpenBench or fishtest | JustBot |
| 57 | https://raw.githubusercontent.com/jeff-pow/Titan/HEAD/README.md | README, development branch | README | Titan |
| 58 | https://raw.githubusercontent.com/jeff-pow/Titan/v1.1.0/README.md | README at the rated tag | README | Titan |
| 59 | https://github.com/jeff-pow/Titan/releases | release notes 1.0, 1.1 | release notes | Titan |
| 60 | https://github.com/jeff-pow/Titan/pulls?q=is%3Apr&page=1 to 10 | PR titles (225) | PR / issue / commit text | Titan |
| 61 | https://github.com/jeff-pow/Titan/pull/N for N = 7, 14, 22, 37, 38, 67, 84, 85, 89, 92, 114, 120, 126, 131, 153, 161, 162, 167, 169, 170, 177, 185, 186, 187, 227 | PR conversation pages | PR / issue / commit text | Titan |
| 62 | https://github.com/USER?tab=repositories for jeff-pow, HasanFakih21, OmerFarukTutkun, Quanticade, Haxk20, kevlu8, stierms, vshcherbyna; DevreChess (404) | repository lists, used to find network repositories | other | all |
| 63 | https://wiki.chessdom.org/NAME for Igel, Quanticade, Devre, PZChessBot, Titan, Zigqueen, ZigQueen, JustBot | all 404 ("no text in this page") | TCEC | none (failed) |
| 64 | three web searches (Igel 3.8.0 threats; zigqueen forum; Devre, PZChessBot, JustBot releases) | nothing usable; result text not used; one result page opened as source 16 | other | none |

Credit lines:

- **Quanticade**: GitHub user Haxk20 and contributors; the prior survey records GPL-3.0. Based on Maksim Korzh's BBC tutorial engine [3].
- **Igel**: Volodymyr Shcherbyna (GitHub vshcherbyna); "licensed under the GPL" [15]. Forked from GreKo 2018.01 [9].
- **PZChessBot**: GitHub users kevlu8 and wdotmathree; the prior survey records AGPL-3.0.
- **ZigQueen**: stierms, with AI assistants as the README states; GPL-3.0-or-later [25]. Training data credits: the LCZero contributors, linrock, vondele, the Stockfish data contributors, xushawn, the BT4 relabelling contributors; parts under ODbL 1.0 [26].
- **Devre**: Ömer Faruk Tutkun (GitHub OmerFarukTutkun); the prior survey records GPL-3.0.
- **JustBot**: GitHub user HasanFakih21; AGPL v3.0 badge in the README [49].
- **Titan**: GitHub user jeff-pow; the prior survey records GPL-3.0.
- **bullet** (trainer used by six of the seven): Jamie Whiting, MIT [27].
- **Chess Programming Wiki**: CC BY-SA 3.0 as the prior survey records.

## Clean-room statement

I opened no source file, header, build file, training script, trainer configuration file, patch, diff, "Files changed" tab, blame view, code search result or network file, in any language, of any engine or trainer. I cloned and downloaded no repository, release archive, binary, dataset or network file. Release-asset and dataset pages were read for file names, sizes and dates only. The GitHub API was used for two rate-limit checks and nothing else. Nothing was deleted. I wrote only in my own folder (`tools\` and `pages\` under `agent-F`), made no change to the user's repository and committed nothing. `report.md` itself was not written, because the Write tool refused it; this message carries its content.

What came close, stated plainly:

1. **Diff context inside review comments.** GitHub shows a few lines of diff context under each review comment on a PR's conversation page. My first reads of two PZChessBot PR pages (#330 and #354) printed such lines: two lines of a build script in one, three lines of a small container class in the other. Neither concerns the network; I recorded and used nothing from them. I then changed my page converter to drop every such block, and all later pages show a "diff hunk skipped" marker instead (Igel #358, Devre #68 and #81 among them).
2. **Code fences in prose documents.** I read the first READMEs and ZigQueen's ARCHITECTURE.md as raw markdown before adding a filter for fenced blocks. The fences held build commands, and in ARCHITECTURE.md a module map naming directories and a few source files. Nothing from them is recorded. Later documents were read with fenced blocks removed.
3. **Prose that names code.** ZigQueen's PROVENANCE.md contains tables of search parameter names and values, and its trainer README names trainer source files and gives schedule and learning-rate values. Automated review comments on PZChessBot #23 and #306 list source file names. Quanticade PR titles begin with source file names. These are prose pages within the rules; I recorded none of the names or values (no search constants, quantisation factors, clipping bounds, learning rates or result weights appear in this report).
4. **Attachments not opened.** Devre PR #68 attaches a trainer configuration file and two images, and ZigQueen's architecture document links a network diagram image. I opened none of them.
5. **Test-result blocks and commit messages.** Match results and commit message bodies are rendered as preformatted text on GitHub. My converter prints result lines (Elo, SPRT, LLR, games) and commit message bodies, and replaces every other preformatted block with a marker.
6. **OpenBench pages** show commit hashes and "compare" links. I followed no compare link.
