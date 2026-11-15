# Network records, group C: Gaia, Cinder, Berserk, Alexandria, pawnocchio, Integral

Clean-room network survey of 2026-11-14 ([README](../README.md)). Written by survey agent C from public prose only and assembled unchanged except for local paths. Source numbers in brackets refer to the Sources table at the end of this file. Every engine here is REFERENCE ONLY for ideas; its code, nets and data are OFF-LIMITS for Fork.


Engines: Gaia 4.4.1, Cinder 0.6.1, Berserk 20250606, Alexandria 8.0.0,
pawnocchio 2.0, Integral 8. Every fact below comes from a page opened on
2026-11-14 (source number and type in brackets; the table is at the end) or
is marked `[prior survey]`. Elo figures are self-play SPRT or progression
results as the authors posted them; time controls are given as posted.
"FN" means a fixed-node test. Trainer hyperparameter values, quantisation
scales and clipping bounds were seen on some pages and are deliberately
described only as concepts.

---

## Gaia 4.4.1 (CCRL #8, 3763)

**One-line architecture:** as the engine writes it in the README at tag
v4.4.1: "GaiaNet-T2b (12 king buckets × 768 PST inputs, plus 4,560 pawn
pairs and 59,808 filtered piece-interaction threat features → 1024 → paired
SCReLU → 16 → 32 → 1), 8 material-based output buckets and a PSQT head,
87 MB" [2, README]. The network file of 4.4.1 is `gaianet-t2b-t5`
[5, release notes; 6, model card].

### Inputs
- Feature set (what an input means; inputs per perspective if stated):
  king-bucketed piece-square inputs (12 buckets × 768), plus 64,368
  "auxiliary" features: 4,560 pawn pairs and 59,808 filtered
  piece-interaction (threat) features [6, model card]. Total per
  perspective is not stated; 12 × 768 + 64,368 = 73,584 by my arithmetic.
- King input buckets: count; layout; how chosen or grown: 12 [2, README;
  6, model card]. Layout: not published. History of the count: 13 in 4.1.0
  [11, forum], 12 in the T1 and T2b generations, 32 (every square of files
  a-d) in T7 [6, model card].
- Horizontal mirroring: not stated for T2b. Stated only for the later T7
  ("folded to files a-d") [6, model card].
- Threat or attack inputs: 59,808 "filtered piece-interaction (threat)
  features" [6, model card]; which pairs are filtered out is not published.
  In 4.4.1 they were not yet updated from the move on every SIMD tier: 4.4.2
  reports about 6% more nodes per second from updating threat features "from
  the move played, on every SIMD tier" [5, release notes].
- Pawn features: 4,560 pawn pairs [2, README; 6, model card].
- Other input relationships: none in T2b. (T7 adds a split by whether the
  opponent has a queen; see "Since the rated version".)
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 1024; the
  piece-square rows and the auxiliary rows are "accumulated into a
  1024-wide layer" [6, model card].
- Further layers: count and widths: 16, then 32, then 1 [2, README;
  6, model card].
- Layer stacks: not stated for T2b beyond the output buckets below.
- Output buckets: 8, "material-based" [2, README; 6, model card]. The
  exact selector (piece count or material value) is not published.
- Skip connections, pairwise multiplication, other structure: "paired
  SCReLU" between the accumulator and the 16-wide layer; a PSQT head
  [6, model card].

### Activations
- After the accumulator: paired SCReLU (T2b). The older T1 generation used
  CReLU plus pairwise [6, model card].
- In the head: not published for T2b.

### Quantisation
- Integer types per layer: piece-square feature-transformer rows int16,
  auxiliary (pawn-pair and threat) rows int8 [6, model card]. Head types
  for T2b: not published.
- Quantisation-aware training or other rounding care: the rated net's
  recipe (t5) lists quantisation-aware training [7, superseded model-card
  revision].

### Inference speed
- Accumulator refresh cache: a "Finny table cache" was listed for 4.1.0
  [11, forum]; no figure. Not restated for 4.4.1.
- Lazy or deferred accumulator updates: not published.
- Fused updates: not published.
- Accumulator stack: not published.
- Pairwise multiplication of accumulator halves: yes (paired SCReLU; the
  1024-wide accumulator feeds a 16-wide layer) [6, model card]; no figure.
- int8 layers or int8 feature-transformer rows: the 64,368 auxiliary rows
  are int8, the piece-square rows int16 [6, model card]; no speed figure.
  File size 87 MB [2, README].
- Sparse first dense layer: "sparse L1" listed for 4.1.0 [11, forum]. For
  T2b the model card describes a sparse first layer that skips 4-byte groups
  of zero activations [6, model card] (that it was already active in 4.4.1
  is my inference from the T2b description; the reordered file came later,
  see "Since").
- Evaluation cache: not published.
- SIMD and VNNI work: runtime dispatch between AVX-512+VNNI, AVX-512, AVX2
  and scalar from CPUID, NEON on ARM; all x86-64 binaries built with PGO
  with every selectable SIMD tier profiled [2, README]. 4.3.2: "AVX2 network
  evaluation is 12% faster" (no detail of how). 4.3.1: ARM 14% faster on
  Raspberry Pi 5 class cores by dispatching the network's dot products to
  the ARM dot-product instruction [5, release notes]. No statement of which
  x86 tier won or lost.
- Memory layout and prefetching: one copy of the weights shared between
  engine processes (Linux, Windows from 4.3.3); on multi-node machines each
  memory node gets its own copy of the network and threads are pinned to
  processor groups sharing a cache: +16% (opening) to +92% (endgame) nodes
  per second on a dual-socket, 192-thread machine; large pages for the hash
  and history tables (not stated for the network) [5, release notes].
- Anything else that made the network faster: nothing further for 4.4.1.
- Speed cost or gain reported for any architecture change: none published
  for T1 → T2b.
- Hardware sensitivity reported: the NUMA figures above; nothing about
  cache size.

### Training data
- Size: not published.
- Type: own self-play at least in part. The README up to 4.3.0 said
  "trained with Bullet on self-play data" [3, README]; the archived
  `gaianet-t1-1000` "generated part of the training data used by its
  successors" [6, model card] and is called the "generator of the gen2
  self-play data" in a commit title [8, model-card commit titles]. The
  4.4.1 README no longer says where the data comes from [2, README]. Label
  budget: not published. The t3a step used "more positions with better
  evaluation targets" [6, model card]; what made the targets better is not
  published.
- Openings, filtering, tablebase use: training-time filter of random
  position skipping and a minimum ply, both tightened sharply at e044
  [6, model card]. Openings and tablebase use in data generation: not
  published.

### Training recipe (concepts only)
- Trainer: Bullet for T1; "in-house trainers built on" Bullet for T2b and
  T7 [6, model card]. The 4.2.2 release says the NNUE trainer was open
  sourced with the engine [5, release notes].
- Loss and target: t5 (the rated net) was "trained from scratch with a new
  training recipe (win-rate loss, evaluation-weighted targets, one-cycle
  learning rate, quantisation-aware training)" [7, superseded model-card
  revision]. Earlier T2b nets blended in the game result with a weight that
  was lowered step by step across e013 → e017 → t3b [6, model card].
- Stages and schedule: before t5, each net was a short cosine fine-tune
  from a common parent checkpoint; t5 restarted from scratch; t6 is the t5
  recipe "at full length, on a larger set of positions" [6, model card].
- Regularisation, optimiser, anything unusual: heavy random position
  skipping (e044) [6, model card]. Optimiser: not published.

### Measured gains for network changes
(All from superseded revisions of the model card [7]; the author later
removed Elo figures from the card, commit title "Model card: no Elo
figures" [8].)
- t3b-1000 (T1) vs t2: +12.0 ± 9.5, SPRT, 2,588 games [7].
- e013 fine-tune vs its parent: +25.4 ± 9.7 [7].
- e017 (lower result weight) vs e013: +3.2 ± 2.6, 36,702 games [7].
- e044 (stricter skipping and ply filter) vs e017: +4.8 ± 3.6, 18,420
  games, at 200k nodes [5, release notes; 7; 8].
- t3a (more positions, better targets) vs e044: +15.9 ± 7.5 at 200k nodes,
  4,145 games [7].
- t3b (lower result weight again) vs t3a: +2.8 ± 3.5 at 200k nodes, 19,826
  games, promoted while the test was still running [7].
- t5 (the rated net: from scratch, new recipe) vs t3b: +26.8 ± 10.0 at
  200k nodes [7].

### Architecture history
- 4.1.0 (2026-02-22): "HalfKA architecture (13 king buckets, 14,657 input
  features including compact threat/mobility features), 768 →
  SCReLU+pairwise → 32 → 64 → 1, 8 output buckets"; sparse first layer;
  Finny table cache; trained on one generation of data [11, forum].
- 4.2.1 (2026-08-09): GaiaNet-T1: "more detailed threat features, and a
  larger network" [5, release notes]: 12 king buckets × 768 + filtered
  threat features (about 41K inputs) → 640 → CReLU + pairwise → 16 → 32 →
  1, 8 output buckets [6, model card].
- 4.3.0 (2026-09-05): first release of the T2b generation [6, model card];
  which T2b file it shipped is not stated. The README at tag v4.3.0 still
  printed the T1 line [3, README].
- 4.3.1: e017. 4.3.2-4.3.3: e044. 4.4.1 (2026-10-19): t5 [6, model card;
  5, release notes].

### Since the rated version
- 4.4.2 (2026-10-24): net t6 (same recipe, full length, more positions);
  threat features updated from the move played on every SIMD tier, about
  +6% nodes per second [5, release notes].
- `t6-ftperm` (2026-10-26, unreleased): the same weights with the
  feature-transformer neurons reordered so zero outputs fall into the same
  4-byte groups; the sparse first layer reads about 24% fewer groups;
  evaluations identical; about 1.3% faster on Zen 5 and 2% on ARM
  [6, model card].
- 4.4.3 (2026-11-05): GaiaNet-T7, "about +10 Elo at 2+0.1 over 4.4.2's
  network" [5, release notes]. T7 [1, README; 6, model card]:
  - piece-square inputs indexed by the king's square (32 squares after
    folding to files a-d) and by whether the opponent has a queen: 45,056
    inputs, both kings sharing one plane (704 per bucket), plus the same
    64,368 auxiliary features;
  - every feature-transformer row int8;
  - one 1024-wide accumulator per perspective → pairwise product → a sparse
    1024 → 32 layer → a dual [x², x] activation giving 64 → a gated layer
    (32 gates × 32 values, value scaled by the squared rectified gate) → 96
    → 1, plus a skip connection from the first layer;
  - 32 output stacks chosen by piece count and queens; no PSQT head;
  - integer inference end to end; 113 MB;
  - trained from scratch with a final short stretch at half the batch
    size; neurons already reordered for the sparse layer.

### UNVERIFIED and not published
- King-bucket layout of T2b; whether T2b mirrors horizontally: not
  published.
- Which threat pairs the "filtered" set drops; how threats are updated in
  4.4.1: not published.
- Output-bucket selector detail ("material-based" only): not published.
- Head activations and head integer types of T2b: not published.
- Data size, label budget (nodes or depth), openings, tablebase use:
  not published.
- Whether all data is own self-play: UNVERIFIED (the README stopped
  saying so after 4.3.0; no other source named).
- Refresh cache, lazy updates, fused updates in 4.4.1: UNVERIFIED (the
  only statement is the 4.1.0 forum post).
- Speed cost of T1 → T2b (640 → 1024 wide, pawn pairs added): not
  published.
- The Elo figures marked [7] were withdrawn from the current model card by
  the author; treat them as superseded prose.

---

## Cinder 0.6.1 (CCRL #9-10, 3759)

**One-line architecture:** assembled. The last architecture string the
author published is the title of PR #916 (2025-11-18): "768x16hm -> 4096/2
-> ([16*2 -> 16*2 -> 16*2 -> 1] + [16*2 + 1])x8" [15, PR title]. Threat
inputs (#1158) and pawn-pawn inputs (#1168) were then added before 0.6.0
[14, release notes]; no string was published for the result. 0.6.1 has the
same change list and the same LTC test as 0.6.0 [14, release notes].

### Inputs
- Feature set: king-bucketed, horizontally mirrored piece-square inputs
  ("768x16hm") [15, PR title], plus threat inputs and pawn-pawn inputs
  [14, release notes]. Inputs per perspective: not published.
- King input buckets: 16 [15, PR title]; grown 8 → 12 → 16 between
  2025-09-25 and 2025-10-03 (#886, #891, #895) [15, PR titles]. Layout:
  not published.
- Horizontal mirroring: yes ("hm") [15, PR title]; the exact rule is not
  published.
- Threat or attack inputs: added by #1158 (2026-08-04); count, relation
  and update method not published [16, PR text].
- Pawn features: pawn-pawn inputs added by #1168 (2026-08-10); count not
  published [16, PR text].
- Other input relationships: none published for 0.6.1.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer width per perspective: UNVERIFIED. The string says
  "4096/2"; an earlier one said "2048x2" and then "2048^2" [15, PR titles].
  A later PR title speaks of growing "L12 from 1024x16 to 1024x32"
  [15, PR title], which fits 2048 per perspective halved to 1024 by
  pairwise multiplication, but no page says so.
- Further layers: a four-layer network since #908 ("Increase NNUE
  architecture to 4 layers") [15, PR title]; widths as written in the
  string: 16*2, 16*2, 16*2, then 1.
- Layer stacks: the whole head is "x8" [15, PR title]; selector not
  published.
- Output buckets: 8 [15, PR title]; selector not published.
- Skip connections, pairwise multiplication, other structure: a residual
  connection "from L2 to output" (#906), written as the "+ [16*2 + 1]"
  branch [15, PR titles]. What "16*2" denotes (two perspectives or two
  activations) is not published.

### Activations
- After the accumulator: not published.
- In the head: not published.

### Quantisation
- Integer types per layer: not published. Two separate quantisation
  constants exist, one for the feature transformer and one for the hidden
  layers (#1170) [15, PR title; 16, PR text].
- Quantisation-aware training or other rounding care: "Preserve eval as f32" (#1006, title only, no
  description): +8.29 ± 5.18 at 1+0.01 [16, PR text]. Retuning the two quantisation constants (#1170): +6.69 ±
  3.42 at 8+0.08 and +5.35 ± 3.01 at 20+0.2 [16, PR text].

### Inference speed
- Accumulator refresh cache: "Cache last seen accumulators per king
  bucket" (#890): +9.94 ± 4.45 at 1+0.01. SIMD for the cached refresh
  (#937): +7.72 ± 3.85 at 1+0.01. "Preserve accumulator cache throughout the
  game" (#938): +4.11 ± 2.65 at 1+0.01 [16, PR text].
- Lazy or deferred accumulator updates: lazy updates (#792): +7.50 ± 3.90
  at 1+0.01; reverted to eager two days later (#794): +3.49 ± 2.45; lazy
  evaluation reinstated (#861, a revert of the revert): +2.10 ± 1.68, all
  at 1+0.01 [16, PR text]. So the same change tested positive in both
  directions months apart.
- Fused updates: "Fuse all updates to the accumulator" (#735): +6.33 ±
  3.65 at 1+0.01 [16, PR text].
- Accumulator stack: "Only ever refresh the NNUE accumulator for the
  moving side" (#629, 2024); no SPRT figure, gauntlet only [16, PR text].
- Pairwise multiplication of accumulator halves: implied by the "/2" in
  the architecture string; not described in prose.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: non-zero indices are computed with AVX-512 and
  BMI2 instructions (#1019): +7.60 ± 3.86 at 1+0.01 [16, PR text]. Training
  encourages sparsity with an L1 penalty (#1119) [16, PR text]. Neuron
  permutation came after 0.6.1 (see "Since").
- Evaluation cache: a per-thread cache of position evaluations (#944),
  moved into the shared search data (#942: +0.16 ± 1.40, non-regression),
  then given a share of the hash (#1015: +2.02 ± 2.76 on non-regression
  bounds at 256 MB), its entries narrowed to 32 bits (#1088: +1.80 ± 1.46
  at 1 MB hash) and its share reduced (#1094: +0.56 ± 2.19, test not
  finished) [16, PR text].
- SIMD and VNNI work:
  - AVX2 and SSSE3 (#558, 2023): +48.6 ± 24.0 at 3+0.025; AVX-512 inference
    (#801): no figure; ARM SIMD (#726): no figure [16, PR text];
  - "Improve SIMD implementation of NNUE inference" (#745): +6.60 ± 3.73;
    "Slightly improve the NNUE SIMD speed" (#903): +4.92 ± 2.96; a rewrite
    on portable SIMD (#899): +0.84 ± 1.97 (non-regression), all at 1+0.01;
  - **less loop unrolling in inference to avoid register spill** (#985):
    +40.46 ± 9.31 on the AVX-512 build and +0.31 ± 1.55 on the VNNI-512
    build, both at 1+0.01 [16, PR text]. The plain AVX-512 path had been
    badly hurt by spilling; the VNNI path had not.
- Memory layout and prefetching: a huge-page-backed allocator (#911):
  +2.83 ± 3.13 at 64 MB; parallel zeroing of huge pages (#917): +4.53 ±
  3.80; advice to the OS that access is random (#919): no figure; all at
  1+0.01 [16, PR text]. Net data was compressed to shrink the binary in
  2023 (#579) and embedded verbatim again in 2025 (#888) [16, PR text]. Net
  file size: not published.
- Anything else that made the network faster: PGO was removed (#929):
  +4.68 ± 3.87 at 1+0.01 for the build without it [16, PR text].
- Speed cost or gain reported for any architecture change: none published
  as nps. Elo by step is under "Measured gains".
- Hardware sensitivity reported: the AVX-512 against VNNI-512 split of
  #985 above; hardware not named.

### Training data
- Size: not published.
- Type: Lc0. "trained with bullet ... using data generated by the Leela
  Chess Zero project", under the ODbL [13, README]. Which Lc0 runs: not
  published. The first network (2023) was trained "with a modified version
  of" nnue-pytorch "using data sets generated with Stockfish and Lc0"
  [16, PR text #478].
- Openings, filtering, tablebase use: "probabilistic ply filtering"
  (#1130) and a configurable minimum ply (#1128) [16, PR text]. Nothing
  else published.

### Training recipe (concepts only)
- Trainer: bullet since #886 (2025-09-25) [16, PR text]; nnue-pytorch
  (modified) for the 2023 nets [16, PR text #478].
- Loss and target: since #1160 (2026-08-07) the net trains "purely on
  scores" (no game-result term), with the same data sets in every stage:
  +8.10 ± 3.82 at 16+0.16. An asymmetric loss that penalises positive
  error more (#1124): +4.34 ± 2.67 at 16+0.16 and +6.70 ± 3.74 at 25,000
  nodes [16, PR text].
- Stages and schedule: at least two stages with a fine-tuning stage that
  was lengthened (#1128): +5.42 ± 3.07 at 10+0.1. A 4x larger batch
  (#896): +4.48 ± 2.86 at 1+0.01. Retraining on reshuffled data (#1134):
  +5.79 ± 3.19 at 5+0.05 and +10.20 ± 4.73 at 25,000 nodes [16, PR text].
- Regularisation, optimiser, anything unusual: L1 regularisation to encourage sparsity
  (#1119): +3.59 ± 2.39 at 16+0.16 and +4.19 ± 2.72 at 1+0.01. AdamW
  until October 2026 (see "Since") [16, PR text].

### Measured gains for network changes
- 768x8hm → 1024x2 → 1x8 with the new bullet trainer (#886): +5.21 ± 3.18
  at 1+0.01 [16, PR text].
- Width 1024 → 1536 (#888): +3.69 ± 2.54 at 1+0.01 [16].
- King buckets 8 → 12 (#891): +6.96 ± 3.76 at 1+0.01 [16].
- King buckets 12 → 16 and width 1536 → 2048 (#895): +7.30 ± 3.64 at
  8+0.08 [16].
- First multi-layer head, "2048^2 -> [16 -> 32 -> 1]x8" (#901): +11.40 ±
  4.69 at 10+0.1 [16].
- "[16*2 -> 32 -> 1]x8" (#902): +12.27 ± 5.11 at 1+0.01 [16].
- Residual connection from the second layer to the output (#906): +6.41 ±
  3.55 at 1+0.01 [16].
- Fourth layer (#908), "768x16hm -> 4096/2 -> [(16*2 -> 16*2 -> 32 -> 1)
  + (16 -> 1)]x8": +2.42 ± 1.85 at 10+0.1 [16].
- The #916 form: +0.76 ± 2.01 at 1+0.01, on non-regression bounds [16].
- Threat inputs (#1158): **+32.87 ± 7.97 at 40+0.4** (256 MB) [16].
- Pawn-pawn inputs (#1168): +8.54 ± 4.30 at 25,000 nodes; +3.92 ± 2.52
  at 5+0.05 [16].
- Release totals: 0.6.0 and 0.6.1 against 0.5.2: +55.04 ± 6.02 at 40+0.4;
  0.5.0 against 0.4.1: +113.71 ± 4.40 at 40+0.4 [14, release notes].

### Architecture history
- 2023-07 (#478): NNUE replaces the hand-written evaluation, "the same
  architecture as Stockfish 14 (SFNNv2)"; +172.1 ± 11.3 against the old
  evaluation at 3+0.025 [16, PR text].
- 2023-12 (#582): "HalfKAv2 -> 512x2 -> 1x8 with PSQT" [15, PR title].
- 2024-08 (#636): "HalfKA_hm[8] -> [768 + 8]x2 -> [1 + 1]x8"
  [15, PR title].
- 2025-09 to 2025-11: the steps listed under "Measured gains" (#886 to
  #916) [15, PR titles].
- 0.4.0 (2025-12-04): ships the #916 architecture [14, release notes].
- 0.6.0 / 0.6.1 (2026-08-16): threat inputs and pawn-pawn inputs
  [14, release notes].

### Since the rated version
- "Merge redundant king-king KA features" (#1189, 2026-09-26): +3.14 ±
  2.21 at 4+0.04 [16, PR text].
- King buckets raised "to the maximum of 32" (#1195, 2026-10-03): +6.04 ±
  3.21 at 8+0.08 [16].
- First dense layer grown "from 1024x16 to 1024x32" (#1198): +0.99 ± 1.94
  at 10+0.1, on non-regression bounds [16].
- Weight permutation to improve sparsity (#1199): no figure [16].
- Explicitly vectorised accumulator updates (#1202): **+19.06 ± 5.93 at
  4+0.04**; updates to both perspectives fused (#1203): +4.22 ± 2.58 at
  4+0.04 [16].
- "Trade the 4th layer by a 2x wider 3rd layer with pairwise mul
  activation", with a move from AdamW to Ranger (#1205, 2026-10-24):
  +10.84 ± 4.44 at 8+0.08 [16].
- "Various performance improvements" (#1206): the bench ran in 5.648 s
  against 6.303 s for the base (the base 11.6% slower), +17.63 ± 5.67 at
  4+0.04. Its commit list includes reusing the previous accumulator instead
  of the cache where possible, one non-zero-block scan shared by all
  instruction sets, and fewer branches in computing threat features
  [16, PR text].
- "More search speed improvements" (#1207): +15.93 ± 5.39 at 4+0.04; its
  commit list includes inlining the accumulator activation and a wider
  accumulation chunk [16].
- "Various small speed improvements" (#1211, 2026-11-01): +7.63 ± 3.65 at
  4+0.04; includes work on the incremental threat update [16].

### UNVERIFIED and not published
- Accumulator width per perspective and the meaning of "4096/2", "2048^2"
  and "16*2": UNVERIFIED (only in code; the strings are not explained).
- Threat-input and pawn-pawn input counts, their relation and update
  method: UNVERIFIED (only in code; the PRs have no description).
- King-bucket layout and the mirroring rule: not published.
- Output-bucket selector: not published.
- Activations (accumulator and head): not published.
- Integer types per layer: not published.
- Net file size: not published.
- Data size, which Lc0 runs, any relabelling: not published.
- Whether the body changed between #916 and 0.6.1 other than the two input
  additions: UNVERIFIED (no PR title says so, but #1158 and #1168 carry no
  description).
- That the rated net includes #1160 (scores-only training) and #1170
  (quantisation constants): an inference from merge dates (2026-08-07 and
  2026-08-15, before the release PR #1172 of 2026-08-16); the release's
  own change list names neither.
- The author's name is not on the pages opened; the GitHub login is
  brunocodutra.

---

## Berserk 20250606 (CCRL #9-10, 3759)

**One-line architecture:** assembled. 16 horizontally mirrored king
buckets (12,288 inputs per perspective) [19, README at the rated commit]
feeding "(2x1024)->16->32->1" [22, PR text #504, 2023-09]. The README at
the rated commit still printed "2x(12288 -> 512) -> 1" [19, README], which
the PR text shows to be out of date since 2023. "20250606" matches the
merge date of PR #583 (2025-06-06) [21, PR titles]; that the CCRL build is
exactly that commit stays an inference [prior survey].

### Inputs
- Feature set: king-bucketed piece-square inputs, 16 buckets × 768 =
  12,288 per perspective [19, README].
- King input buckets: 16, horizontally mirrored [19, README]. Grown in
  steps: king "quadrant" indexing (#342, 2022-02), mirroring (#365), 8
  buckets "after reflecting the king to the kingside" (#372), 16 buckets
  (#410, 2022-09) [22, PR text]. Layout of the 16: not published.
- Horizontal mirroring: yes, the king is reflected to one side of the
  board (#365, #372) [22, PR text].
- Threat or attack inputs: none in the rated version (added 2026-10; see
  "Since").
- Pawn features: none in the rated version.
- Other input relationships: none published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer width per perspective: 1024 [22, PR text #504]; a
  2026 commit message also speaks of "the full 1024 element bucket state"
  and "2KB of L1 activations" for the pre-rearchitecture code [22, PR text
  #594].
- Further layers: 16, then 32, then 1 [22, PR text #504].
- Layer stacks: none stated.
- Output buckets: none stated for this architecture. (The 2026 architecture
  has 8; see "Since".)
- Skip connections, pairwise multiplication, other structure: none stated
  for the rated version.

### Activations
- After the accumulator: ReLU, clipped at the 8-bit maximum since #505, so
  "effectively CReLU" [22, PR text #505].
- In the head: not published.

### Quantisation
- Integer types per layer: accumulator int16 (overflow was the reason for
  #508); accumulator outputs clipped to 8 bits for the sparse product
  [22, PR text #505, #508]; second and third layers quantised so the
  network value is computed in int16 (#572, 2025-02): +3.09 ± 2.14 at
  60+0.6 on non-regression bounds; the same patch dropped the SSSE3 and
  SSE2 paths and added a full NEON path [22, PR text].
- Quantisation-aware training or other rounding care: the input-layer quantisation was changed to prevent int16
  overflow (#508): +0.61 ± 1.95 at 6+0.06 (non-regression) [22, PR text].
  Networks are loaded already quantised since #373 (2022) to keep the
  binary and the files small [22, PR text]. QAT: not published.

### Inference speed
- Accumulator refresh cache: "Faster refresh using cached accumulator
  states" (#384, 2022-06): +7.13 ± 4.59 at 8+0.08 [22, PR text]; the
  Berserk 9 notes call it "fast refresh logic for ~3.5% speedup"
  [20, release notes].
- Lazy or deferred accumulator updates: #471 (2023-02): +11.83 ± 5.49 at
  8+0.08. The author notes the same idea had earlier tested at about −1
  Elo and became good only once the prefetch was moved to a speculative
  place [22, PR text].
- Fused updates: "Accumulator update via Move" (#404): the difference is
  derived from the move; +0.85 ± 2.97 at 10+0.1 (neutral). "Optimize Apply
  Updates" (#453): +12.00 ± 5.56 at 10+0.1 [22, PR text].
- Accumulator stack: not described in prose.
- Pairwise multiplication of accumulator halves: not in the rated version.
- int8 layers or int8 feature-transformer rows: 8-bit accumulator outputs
  feed the first dense layer [22, PR text #505]; no int8 feature rows in
  the rated version.
- Sparse first dense layer: introduced with the 1024-wide accumulator
  (#504, 2023-09): "in order to use such a large FT, Berserk now relies on
  sparse matrix multiplication after the FT"; −0.21 ± 5.17 at 8+0.08 and
  +6.39 ± 3.82 at 60+0.6 for the bundle. Sorting the weights so that
  active neurons fall in the same chunks (#505) cut 4-chunk sparsity from
  14.6% to 13% for about 0.75% more speed. Adding int16 products in pairs
  before widening to int32 (#508) measured about 0.4 to 0.9% faster, with
  no further gain from groups of four [22, PR text].
- Evaluation cache: not published.
- SIMD and VNNI work: AVX-512 everywhere (#506, 2023-10). The PR's speed
  table (nodes per second, one machine, hardware not named) reads about
  1.57M for SSSE3, 2.05M for AVX2, 2.09M for AVX2 with PEXT, 2.20M for
  AVX-512, 2.25M for AVX-512 with PEXT and **2.10M for VNNI-512 with PEXT**:
  the VNNI build was slower than the plain AVX-512 one [22, PR text].
  Chunking loops so the compiler unrolls and vectorises them (#408): "~6%
  nps", +7.24 ± 5.35 at 10+0.1; a follow-up simplification (#409): about
  +1% [22, PR text].
- Memory layout and prefetching: "Prefetch before NN Accumulator updates"
  (#359, 2022-04): +9.37 ± 5.43 at 8+0.08 [22, PR text], "~6% speedup" in
  the Berserk 9 notes [20, release notes]. Allocation alignment (#499):
  +2.06 ± 3.62 on non-regression bounds, bundled with other changes
  [22, PR text]. Net file size: not published.
- Anything else that made the network faster: SPSA tuning of the net's
  final layer in games (#583, the last change before the rated date):
  **+17.23 ± 5.18 at 60+0.6** after 12k iterations, +10.99 ± 4.34 after 6k
  [22, PR text]. (A strength gain, not a speed gain.)
- Speed cost or gain reported for any architecture change: a 1024-wide
  single layer (#397, 2022-07) caused "a major slowdown": −11.15 ± 3.94
  STC, +7.02 ± 4.22 LTC; it was reverted to 512 a month later (#402, +1.32
  ± 2.13) because the scaling did "not outweigh the negatives". 768 wide
  (#458, 2023-01): +4.48 ± 4.80 STC, +10.69 ± 5.18 at 60+0.6
  [22, PR text].
- Hardware sensitivity reported: the VNNI result above; nothing on cache
  size.

### Training data
- Size: not published as a total. The data is a rolling window: from
  2023-09 each new net swapped "oldest data" out for 2.1 to 2.7 billion
  new positions from the newest engine, later smaller additions; the last
  net before the rated date (2024-03-24) was trained after removing the
  September 2023 data [23, commit text].
- Type: own self-play through the engine's own generator ("Berserk
  FenGen") [19, README]. A mix "of Berserk and Koivisto data" was adopted
  in 2023-01 (#445: +5.28 ± 3.49 STC, +6.14 ± 4.20 at 60+0.6)
  [22, PR text]; whether any Koivisto data was still in the window in 2024
  is not published. Label budget, as written in the commit messages:
  "20.5k minnodes" (2023-10), then "10k min" and "15k min" positions
  (2023-11 to 2024-03) [23, commit text]. Relabelling: none stated.
- Openings, filtering, tablebase use: DFRC start positions were added
  (2.2 billion positions, 2023-10; another batch 2023-11: +19.36 ± 6.00
  and +17.38 ± 5.41 in FRC tests, +0.65 ± 1.64 and +3.19 ± 2.97 in the
  standard tests)
  [23, commit text]. Filtering and tablebase use: not published.

### Training recipe (concepts only)
- Trainer: Grapheus since #504 ("the first network in Berserk trained by
  Grapheus") [22, PR text; 19, README]; Koivisto's CUDA trainer before
  (#371, 2022-05); the author's own trainer up to 8.5.1 [19, README].
  bullet only from 2026-10 [18, README; 22, PR text #600].
- Loss and target: in 2023-10 and 2023-11 the result share of the target
  was raised in three steps up to a result-only target, each step retrained
  from an earlier net: +11.07 ± 4.85 and +11.26 ± 5.01 (10+0.1, 60+0.6),
  then +5.25 ± 3.26 and +7.03 ± 4.12, then +3.34 ± 3.03 and +3.25 ± 2.68
  [23, commit text].
- Stages and schedule: each net is "trained from previous network" with
  the data window moved [23, commit text]; #505 trained on from an earlier
  net for a further run of epochs with 3 billion positions swapped in
  [22, PR text].
- Regularisation, optimiser, anything unusual: an "L1 penalty" is listed for Berserk 8
  (2021, the author's own trainer) [20, release notes]; nothing later.

### Measured gains for network changes
- King quadrant indexing (#342): +6.91 ± 3.52 and +8.66 ± 5.20 (the second
  at 40+0.4) [22, PR text].
- Horizontal mirroring (#365): +1.12 ± 1.27 at 8+0.08, called Elo-neutral
  but enabling [22].
- 8 king buckets (#372): +16.72 ± 4.86 STC, +14.83 ± 7.11 at 40+0.4 [22].
- 16 king buckets (#410): +5.25 ± 4.27 STC, +5.73 ± 3.98 at 60+0.6 [22].
- 1024 wide, single layer (#397): −11.15 STC, +7.02 LTC; reverted [22].
- 768 wide (#458): +4.48 STC, +10.69 at 60+0.6 [22].
- First multi-layer net, "(2x768)-8-32-1" (#477, 2023-03): +2.64 ± 2.08
  at 60+0.6 [22].
- "(2x1024)->16->32->1" with a sparse first layer (#504): −0.21 STC,
  +6.39 ± 3.82 at 60+0.6; "increases the network size by ~33%" [22].
- Retrain with 3 billion fresh positions and sorted weights (#505): +5.64
  ± 4.24 at 8+0.08, +7.64 ± 4.78 at 40+0.4 [22].
- Result-heavy targets, three steps: see "Training recipe" [23].
- SPSA of the final layer (#583): +17.23 ± 5.18 at 60+0.6 [22].
- Release totals: Berserk 13 against 12: +52.78 ± 3.25 at 60+0.6; 12
  against 11: +81.33 ± 4.53; 9 against 8.5.1: +54.37 ± 2.65 at 40+0.4
  [20, release notes].

### Architecture history
- Berserk 6 (2021-10): first NNUE, trained on 350 million positions from
  Berserk 5 self-play. Berserk 7: 950 million positions, pieces indexed
  relative to the king's side of the board, hidden layer 512. Berserk 8:
  1.2 billion positions from Berserk 6 self-play [20, release notes].
- Berserk 9 (2022-06): mirrored 8-bucket input, "6144 -> (512x2) -> 1",
  trained on about 8 billion positions from 8.5.1 self-play with
  Koivisto's trainer [20, release notes].
- Berserk 10 (2022-10): 16 king buckets; 1024 tried and reverted
  [20, release notes].
- Berserk 11 (2023-02): 768 hidden neurons; Berserk and Koivisto data
  mixed [20, release notes].
- 2023-03: "(2x768)-8-32-1" (#477). 2023-09: "(2x1024)->16->32->1",
  sparse first layer, Grapheus (#504) [22, PR text].
- 2023-09 to 2024-03: 22 network updates by data rotation and target
  changes [23, commit text]. No network commit between 2024-03-24 and
  #572 (2025-02) [23, commit titles].
- 2025-06-06: final-layer SPSA (#583), the rated state [22, PR text].

### Since the rated version
- Berserk 14 was released on 2026-05-24 [20, release notes]; its README
  still prints the old line and its notes describe no network change
  [19, README; 20].
- #594 (2026-08): the accumulator activation and the non-zero scan fused
  into one pass; second-layer weights transposed to drop a horizontal
  reduction ("+1.6%" on its own); the refresh pass skipped when nothing
  changed; forward pass specialised on the side to move; about 5.7% faster
  overall with identical node counts; +8.40 ± 3.18 at 10+0.1
  [22, PR text]. Openly co-authored with an AI agent [22].
- #600 (2026-10-31) "new arch ... heavily influenced by PlentyChess, SF,
  and others", trained with Bullet. "Inputs: 16x12x64 K-PSQT + 60144
  threats. Forward Pass: ordered 2x(pairwise mul 512) -> 8x[16 -> 32 ->
  1]"; +3.27 ± 2.10 at 60+0.6, then +4.03 ± 1.85 and +7.22 ± 3.35 with
  more data [22, PR text]. From its commit messages [22]:
  - 8-bit accumulator activations; the head first in float, then integer
    and vectorised; the head's weights stored already quantised by the
    trainer; a skip connection into the last layer was tried and dropped;
  - hidden widths 1536 and 1024 were tried, 512 shipped;
  - one accumulator for piece-square and threat rows; threat changes
    collected while the move is made; threat rows and the piece-square
    rows of a lazy update are prefetched;
  - threats the network has no feature for are never recorded (pawn
    attacking bishop or queen, bishop or rook attacking queen: 7.5% of
    recorded entries): +0.79% (clang) and +1.26% (gcc) nodes per second;
  - threat attack sets taken from the engine's attack helpers: +1.11%
    (clang), +0.44% (gcc).
- #603 (2026-11-01): int8 threat rows widened two at a time in accumulator
  updates, a port of a Stockfish PR: +1.93% and +2.17% in two runs. Two
  other variants lost 0.49% and 0.55% [22, PR text].
- #604 (2026-11-01): pawn-pair inputs, credited to pawnocchio, Stockfish
  and PlentyChess. "Inputs: 16x12x64 K-PSQT + 59808 piece threats + 4560
  pawn pairs"; +1.92 ± 1.69 at 60+0.6 over 40,002 games [22, PR text].
- #609: one more shard of data: +4.74 ± 2.58 at 60+0.6. #610: "a short
  second training stage on game results": **+11.67 ± 4.18 at 60+0.6**
  [22, PR text].
- #613 (2026-11-14): on AVX-512 the fused threat update runs in four
  128-lane tiles instead of one 512-lane tile (as AVX2 already did):
  +8.63% and +8.66% on a Zen 4 EPYC 9R14 (clang 18, PGO, AVX-512 VNNI
  build); at hidden width 640: +7.8% for 4 tiles against 16, +6.7% for 10
  against 16, +1.3% for 4 against 2 [22, PR text].
- The current README: "2x(12288 + 60144 -> 512) -> Pairwise -> 512 -> 16
  -> 32 -> 32 -> 1", "Clamped + Squared activations, 8 Output Buckets (by
  piece count)" [18, README]; it does not yet mention the pawn pairs.

### UNVERIFIED and not published
- That CCRL's "20250606" is the commit of #583: UNVERIFIED (date match
  only).
- Layout of the 16 king buckets: not published.
- Output buckets in the rated architecture: none stated; UNVERIFIED that
  there are none.
- Head activations and integer types of each head layer: not published
  beyond "int16 via quantised 2nd and 3rd layers".
- Total data size at the rated date; whether Koivisto data remained;
  filtering; tablebase use; opening book of the generator: not published.
- What "minnodes" means exactly (a minimum node count per move is my
  reading): UNVERIFIED.
- Net file size: not published.
- Hardware of the #506 speed table: not stated.
- Whether Berserk 14 (2026-05) carries any network change: UNVERIFIED
  (notes silent; no commit list opened for 2025-06 to 2026-05).

---

## Alexandria 8.0.0 (CCRL #12-13, 3754)

**One-line architecture:** as the engine writes it in the 8.0.0 release
notes: "(768->1536x16)x2->1x8" [26, release notes]. Released 2025-03-03.

### Inputs
- Feature set: 768 piece-square inputs per king bucket, 16 buckets
  [26, release notes].
- King input buckets: 16; "the input bucket count went from 1 to 16"
  [26, release notes]. Layout: not published in prose (a commit title says
  only "make bucket layout more readable") [29, PR text #493]. The count
  went from 1 to 16 in one release.
- Horizontal mirroring: yes, since 7.1.0: "Horizontal mirroring was
  introduced, improving the net strength without increasing its size"
  [26, release notes]; the PR says the two perspectives became independent
  and each can need its own refresh [29, PR text #445].
- Threat or attack inputs: none in 8.0.0.
- Pawn features: none in 8.0.0.
- Other input relationships: none published.
- Factoriser or other training-only input structure: not published for
  8.0.0. (A 2026 commit title mentions "account for factoriser"
  [29, PR text #589].)

### Body
- First hidden layer width per perspective: 1536, "shrinked from 2048"
  when the buckets arrived [26, release notes].
- Further layers: none; a single hidden layer [26, release notes].
- Layer stacks: none.
- Output buckets: 8 [26, release notes], introduced in 2024-04 (#380)
  [29, PR text]; selector not published.
- Skip connections, pairwise multiplication, other structure: none in
  8.0.0. A pairwise multi-layer net was merged in 2024-08 (#457) and
  replaced two months later by the plain 2048-wide net (#474) [29, PR
  text; 26, release notes].

### Activations
- After the accumulator: squared clipped ReLU; the 2024-02 SIMD patch
  explains that a smaller quantisation scale "allows the squared clipped
  relu to fit within an int16" [29, PR text #334]. Not restated for 8.0.0.
- In the head: there is no head in 8.0.0.

### Quantisation
- Integer types per layer: int16 arithmetic for the activation
  [29, PR text #334]; other types not published.
- Quantisation-aware training or other rounding care: weights are clipped in training "allowing for better
  quantization" (7.1.0) [26, release notes]. The quantisation scale was
  lowered for SIMD (#334: +15.50 ± 7.12 at 8+0.08) and raised again with a
  reworked SIMD multiply "with no slowdown while having increased accuracy"
  (#344: +12.54 ± 6.44 at 8+0.08) [29, PR text]. QAT: not published.

### Inference speed
- Accumulator refresh cache: "Finny tables were added to greatly speed-up
  the evaluation" [26, release notes]: **+25.87 ± 6.93 at 8+0.08** (#495,
  one table per thread, per side) [29, PR text]. Faster refreshes (#500):
  +3.35 ± 2.30 at 4+0.04 [29, PR text].
- Lazy or deferred accumulator updates: "Delay NNUE update until we
  actually need to get an eval" (#305, 2024-01), to skip the update when a
  node is left early, for example on a TT cutoff; no figure
  [29, PR text]. 7.1.0: "the eval update is now fully lazy"
  [26, release notes].
- Fused updates: all changes of a move applied at once instead of one call
  per piece change (#299): +8.19 ± 4.54 at 8+0.08, the idea credited to
  Seer's author [29, PR text].
- Accumulator stack: "Reuse old accumulator states" (#292): no figure;
  "Do not needlessly copy the accumulator when doing incremental updates"
  (#403): +10.98 ± 4.42 at 8+0.08 [29, PR text]; 7.0.0 lists "removing one
  accumulator copy" [26, release notes].
- Pairwise multiplication of accumulator halves: not in 8.0.0.
- int8 layers or int8 feature-transformer rows: not in 8.0.0.
- Sparse first dense layer: not in 8.0.0 (no dense layer).
- Evaluation cache: not published; 7.0.0 saves the evaluation in the TT
  during quiescence [26, release notes].
- SIMD and VNNI work: hand-written SIMD since #334 (above). "Simplify avx2
  sum reduction" (#498): +0.86 ± 1.83; compiler-flag work (#508): +1.80 ±
  1.43, both at 8+0.08; an auto-vectorised rewrite (#514, reverted and
  reintroduced as #520): +0.72 ± 1.74 [29, PR text].
- Memory layout and prefetching: nothing for 8.0.0. Net file size: not
  published. (The file was memory-mapped from 8.1.0.)
- Anything else that made the network faster: nothing further.
- Speed cost or gain reported for any architecture change: the 16-bucket
  1536 net "failed STC" at −1.27 ± 2.36 (8+0.08) and "passed LTC" at
  +12.89 ± 4.88 (40+0.4) (#493) [29, PR text]. The 2024 pairwise
  multi-layer net: −8.48 ± 5.14 STC, +9.26 ± 4.11 LTC (#457) [29].
- Hardware sensitivity reported: none.

### Training data
- Size: not published for 8.0.0. The last stated figure is "around 3B
  fens from the jan2023 binpack" for 5.0.0 (2023-09) [26, release notes].
- Type: Lc0. "neural networks trained on data provided by the Leela Chess
  Zero project", under the ODbL [25, README]. 4.0.0 swapped 200 million
  Koivisto positions for 370 million Leela positions [26, release notes].
  Relabelling: none stated.
- Openings, filtering, tablebase use: not published for 8.0.0.

### Training recipe (concepts only)
- Trainer: bullet; older nets with CudAD [25, README].
- Loss and target: not published for 8.0.0.
- Stages and schedule: not published for 8.0.0. Two nets were made for
  the bucketed architecture (2024-12-14 and 2024-12-23) before the release
  [27, network release notes].
- Regularisation, optimiser, anything unusual: weight clipping (7.1.0) [26, release notes];
  "several hyperparameters improvements" (7.0.0) [26]. Nothing else.

### Measured gains for network changes
- Perspective net "(768->512)x2->1" replacing a single-perspective one
  (4.0.0); 1024 wide and about 3 billion positions (5.0.0)
  [26, release notes]; no separate figures.
- Output buckets (#380): +5.44 ± 4.06 at 8+0.08, +7.87 ± 6.28 at 40+0.4
  [29, PR text].
- 1536 wide (#381): +10.94 ± 6.04 at 8+0.08 [29].
- Horizontal mirroring (#445): +5.48 ± 3.19 STC, +8.81 ± 4.04 LTC [29].
- 16 king buckets with 1536 wide (#493): −1.27 STC, +12.89 LTC [29].
- Finny tables (#495): +25.87 at 8+0.08 [29].
- Second bucketed net (#499): +4.17 ± 2.65 STC, +3.34 ± 2.26 LTC [29;
  27, network release notes].
- Release totals: 8.0.0 against 7.1.0: +14.89 ± 2.80 at 60+0.6 on a
  balanced book, +42.25 ± 4.53 on an unbalanced book [26, release notes].

### Architecture history
- 4.0.0 (2023-07): "768->512->1" to "768->512x2->1"; Leela data replaces
  Koivisto data [26, release notes].
- 5.0.0 (2023-09): "768->1024x2->1" [26].
- 7.0.0 (2024-05): "(768->1536)x2->1x8" [26].
- 2024-08 (#457): "(768 -> 1536) x 2 --pairwise-> (16 -> 32 -> 1) x 8",
  merged [29, PR text].
- 7.1.0 (2024-10): "(768->2048)x2->1x8", mirrored, lazy updates [26].
- 8.0.0 (2025-03): "(768->1536x16)x2->1x8", Finny tables [26].

### Since the rated version
- 8.1.0 (2025-08): "major NNUE simplification", faster indexing, the net
  file memory-mapped, a net "trained with WDL skipping"; 8.1.12: "a 2 step
  training" (+4.09 ± 2.56 on top of +3.27 ± 2.22, both 40+0.4)
  [26, release notes; 27].
- 9.0 (2026-02): "Finally switched to a Multi-layer architecture, with
  L2=16 and L3=32" (#589: +8.30 ± 3.85 at 40+0.4); dual activation;
  piece-count filtering (+5.08 ± 2.95 STC, +2.28 ± 1.72 LTC); a result
  term added to the loss, then a net titled "linear WDL" (+5.58 ± 3.11
  STC, +8.02 ± 3.77 LTC); add-sub Finny tables (#592: +6.95 ± 3.49 at 6+0.06);
  sparse inference without permutation (#598: −0.04 ± 1.34, kept "for
  later" because the nets were neither permuted nor big enough) [26; 29].
- 9.1 (2026-10-04): sparsity-maximising permutation at build time (#621:
  +1.85 ± 1.46 at 8+0.08); the Finny refresh fused into the accumulator
  activation with register tiling (#620: about +3 to +4% nodes per second
  on a Ryzen 5 7535HS with AVX2, eight registers per tile measured
  fastest; +3.51 ± 2.31, then +6.39 ± 3.33 at 4+0.04) [26; 29].
- After 9.1 [27, network release notes; 29, PR text]:
  - threat inputs (#630): +15.53 ± 5.50 STC, +13.43 ± 4.96 LTC; king
    threats are not recorded;
  - first layer raised to 768 with threat inputs (#632, no figure in the
    PR; the network release of the same day reads +2.01 ± 1.59 STC,
    +7.01 ± 3.48 LTC);
  - threat inputs to threat inputs plus pawn pairs (#634: "remove some of
    the threats ... add PP as a superset"): +12.78 ± 4.87 STC, +13.50 ±
    4.90 LTC;
  - BT4 data (#635): −7.35 ± 4.92 at 25,000 nodes, +3.28 ± 2.22 STC,
    +11.33 ± 4.49 LTC; more BT4 data (#636): +6.67 ± 3.72 FN, +17.70 ±
    5.81 STC, **+25.01 ± 6.65 LTC**;
  - first layer 1024 (#638): +4.89 ± 2.87 STC;
  - king buckets 16 → 32 (#639): +11.96 ± 5.03 FN, +17.96 ± 5.85 STC,
    +10.58 ± 4.33 LTC, +10.62 ± 4.33 at 60+0.6;
  - quantisation moved into the trainer (#629).
- Data added after 8.0.0: positions from the T60 run of 2020 (2026-01),
  "some T79 data" (2026-09), BT4 data (2026-10) [29, PR text].

### UNVERIFIED and not published
- Layout of the 16 king buckets and the mirroring rule: UNVERIFIED (only
  in code).
- Output-bucket selector: not published.
- Activation in 8.0.0 (squared clipped ReLU is stated for 2024-02 only):
  UNVERIFIED for the release itself.
- Integer types per layer: not published.
- Which network file 8.0.0 shipped (net02 of 2024-12-23 by date):
  UNVERIFIED.
- Data size, which Lc0 runs, filtering and result weighting of the 8.0.0
  net: not published.
- Net file size: not published.
- First-layer width of the 9.0 and 9.1 multi-layer nets: not published.
- Licence: not stated on the pages opened today (GPL-3.0 per the
  [prior survey]).

---

## pawnocchio 2.0 (CCRL #12-13, 3754)

**One-line architecture:** assembled, and incomplete. The README sends the
reader to a source file for "specifics about the network" [30, README],
which this survey may not open. The last architecture string in prose is
PR #11 (2026-01-23): "(768x16hm->2048)x2-pw>(16->32->1)x8"
[33, PR text]. Before 2.0 (2026-06-27) the net gained dual activation
(#13), threat inputs and pawn-pawn inputs (#64) [33, PR text]; the 2.0
notes say it "now has several hidden layers, and a much more expressive set
of inputs, now including threat inputs as well as pawn-pawn inputs (my own
invention)" and is "fully quantised, in the vein of Stormphrax"
[31, release notes]. Widths after the input change are not published.

### Inputs
- Feature set: king-bucketed, mirrored piece-square inputs ("768x16hm")
  [33, PR text #11], plus threat inputs and pawn-pawn inputs
  [31, release notes]. Inputs per perspective: UNVERIFIED (only in code).
- King input buckets: 16 at #11 [33, PR text]; layout not published;
  whether still 16 in 2.0 is UNVERIFIED.
- Horizontal mirroring: yes ("hm"), since v1.3 (2025-03):
  "(768hm->640)x2->1x8" [31, release notes].
- Threat or attack inputs: "Finally implemented threat inputs!" (#64,
  2026-06-15) [33, PR text]. Count and relation: UNVERIFIED (only in
  code). Commit titles in that PR say threats are stored "in a packed
  fashion"; a later commit computes threats lazily for "a small speedup"
  [33, PR text; 34, commit text].
- Pawn features: "pawn-pawn (pp) inputs", the author's "own innovation",
  described in a commit title as "masked pawn-pawn inputs" [33, PR text
  #64]. Count: not published by pawnocchio. (Berserk and Integral, which
  credit pawnocchio for the idea, each state 4,560 pawn-pair inputs
  [22; 37]; Gaia states the same count without naming a source [6].)
- Other input relationships: none published for 2.0.
- Factoriser or other training-only input structure: a commit of
  2026-04-06 speaks of "constraints to factorized families"
  [34, commit text]; nothing more is published.

### Body
- First hidden layer width per perspective: 2048 at #11 [33, PR text].
  For 2.0: UNVERIFIED (only in code). The first PR after the release is
  titled "Larger net" with the description "L1=1024" [33, PR text #68],
  so the released width was presumably below that in the same notation,
  but no page says what it was.
- Further layers: 16, then 32, then 1 at #11 [33, PR text].
- Layer stacks: the head is "x8" [33, PR text #11].
- Output buckets: 8 [33, PR text #11; 31, release notes for v1.3 to
  v1.4]; selector not published.
- Skip connections, pairwise multiplication, other structure: pairwise
  multiplication after the accumulator ("-pw>") [33, PR text #11].

### Activations
- After the accumulator: not published beyond the pairwise product.
- In the head: dual activation after the first dense layer, "concat
  crelu(l1) with csrelu(l1)", implemented "in the vein of" Stormphrax, the
  idea "from SF originally" [33, PR text #13].

### Quantisation
- Integer types per layer: "fully quantised" [31, release notes];
  "working int multilayer" [33, PR text #11]. Per-layer types: UNVERIFIED
  (only in code).
- Quantisation-aware training or other rounding care: "Preserve more precision in the crelu side of dual act"
  (#59): +1.17 ± 0.90 at 10+0.1; "Preserve more precision in inference"
  (#61): +0.37 ± 1.57 at 4+0.04 and +1.31 ± 1.98 at 10+0.1, with "the
  expensive part" dropped [33, PR text]. QAT: not published.

### Inference speed
- Accumulator refresh cache: Finny tables exist (a "measurement tool for
  finny tables" was added 2026-02-15) [34, commit text]; no figure.
- Lazy or deferred accumulator updates: "proper lazy updates"
  (2026-02-15) [34, commit text]; no figure.
- Fused updates: not published. (The author contributed "Finny table fused
  updates" to Integral: +3.45 ± 2.23 at 4+0.04 [41, PR text #192].)
- Accumulator stack: "Decouple nnue state from accumulator storage and
  skip some copies in favor of sometimes needing to refresh the
  accumulators twice" (#53): +3.78 ± 3.00 at 10+0.1 and +4.55 ± 2.86 at
  4+0.04 [33, PR text].
- Pairwise multiplication of accumulator halves: yes (#11) [33, PR text];
  no separate figure.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: "compute accumulator->l1 matmul sparsely"
  (#12): **+10.18 ± 4.38 at 4+0.04**; the non-zero table was made smaller
  and uses popcount. The net file is permuted when it is processed for
  embedding (#11), and permuted again for sparsity after 2.0 ("slightly
  faster") [33, PR text; 34, commit text]. A "Sparser net" (#19): +7.93 ±
  4.31 at 20,000 nodes, +10.47 ± 4.39 at 10+0.1, +8.07 ± 3.79 at 40+0.4
  [33, PR text]; how it was made sparser is not published.
- Evaluation cache: not published.
- SIMD and VNNI work: an emulated VNNI dot product built from multiply-add
  instructions ("faster dpbusd", "speedier dpbusd"); inline assembly found
  "much faster" than a C helper; SSE2 and SSSE3 paths added [33, PR text
  #11; 34, commit text]. A dedicated NEON path for the multi-layer net
  (#42, by a contributor): bench 1,289,760 → 1,544,604 nodes per second
  as posted, and "1.05 times faster" by wall time [33, PR text].
- Memory layout and prefetching: NUMA support "~3% speedup" (2026-03-29)
  [34, commit text]. Release binaries are about 67 MB [31, release notes];
  the net file size itself is not published.
- Anything else that made the network faster: "small inference speedup"
  commits without figures [34, commit text].
- Speed cost or gain reported for any architecture change: see the
  "Larger net" under "Since the rated version": it won at fixed nodes and
  lost at every single-thread time control.
- Hardware sensitivity reported: none beyond the thread counts of that
  test.

### Training data
- Size: not published.
- Type: mixed. "a neural net trained on self play games from zero
  knowledge, as well as games played by Vine", an MCTS engine co-written by
  the author [30, README]; Vine data entered with v1.9 (2026-01)
  [31, release notes]. Labels are replaced by the evaluations of a much
  larger own network (the "chonker"): "train on data rescored with a much
  bigger net" (#33), and later "evals from new chonker with TI and PP
  inputs" (#63) [33, PR text]. Whether the big net's label is a static
  evaluation or a search is not published [prior survey: same gap].
  Self-play label budget: not published.
- Openings, filtering, tablebase use: not published.

### Training recipe (concepts only)
- Trainer: bullet [30, README].
- Loss and target: a retrain on game results only (#15): −1.65 ± 2.77 at
  10+0.1, +4.16 ± 2.57 at 40+0.4; after relabelling the result weight was
  lowered again ("lower wdl with new better scores", #34): +1.65 ± 1.34 at
  40+0.4 [33, PR text].
- Stages and schedule: a "pretraining stage" (2026-04-03): +2.16 ± 1.65 at
  40+0.4 [34, commit text]; a fine-tune on new data (#65): +3.44 ± 2.30 at
  10+0.1, **+13.61 ± 4.95 at 40+0.4, +19.32 ± 5.85 at 40+0.4 with 4
  threads** [33, PR text].
- Regularisation, optimiser, anything unusual: not published.

### Measured gains for network changes
- Multi-layer net "(768x16hm->2048)x2-pw>(16->32->1)x8" (#11): +10.01 ±
  4.37 at 10+0.1 [33, PR text].
- Sparse first dense layer (#12): +10.18 ± 4.38 at 4+0.04 [33].
- Dual activation (#13): +8.54 ± 3.97 at 10+0.1, +6.27 ± 3.29 at 40+0.4
  [33].
- Sparser net (#19): +7.93 FN, +10.47 STC, +8.07 LTC [33].
- Relabelling by the larger net (#33): +0.45 ± 3.35 and +5.73 ± 3.16 at
  10+0.1; +1.64 ± 1.32 and +4.69 ± 2.79 at 40+0.4 (two nets) [33].
- Labels from a larger net that itself has threat and pawn-pawn inputs
  (#63): +11.98 ± 4.72 at 10+0.1, +11.04 ± 4.46 at 40+0.4 [33].
- Threat inputs plus pawn-pawn inputs (#64): **+26.71 ± 6.85 at 10+0.1,
  +30.32 ± 7.48 at 40+0.4** [33]. No separate figure for either input set.
- New net "trained with new chonker" (#66): +8.37 ± 3.84 at 10+0.1,
  +4.02 ± 2.49 at 40+0.4 [33].
- Release totals: 2.0 against 1.9.2: +103.48 ± 3.21 at 10+0.1, +111.33 ±
  3.58 at 40+0.4, +110.29 ± 4.75 at 40+0.4 with 4 threads; "most of the
  gain is from large improvements to the network on all fronts"
  [31, release notes].

### Architecture history
- v1.2 (2025-02): first NNUE. v1.3: "(768hm->640)x2->1x8". v1.3.1415:
  "(768hm->768)x2->1x8". v1.4: "(768hm->1024)x2->1x8". v1.6 and v1.7: "new
  bigger net" each, sizes not stated [31, release notes].
- v1.9 (2026-01-03): "New net trained with a portion of data from Vine"
  [31, release notes].
- 2026-01-12: "2048hl pairwise net, +2 elo" [34, commit text].
- 2026-01-23: multi-layer (#11), sparse first layer (#12), dual
  activation (#13) [33, PR text].
- 2026-03: relabelling by the larger net (#33, #34) [33].
- 2026-06-15: threat and pawn-pawn inputs (#64). 2026-06-25: #65 and #66.
  2026-06-27: v2.0. 2026-06-29 14:29 UTC: v2.0.1, "windows and fastchess
  compatibility fixes" [33; 31].

### Since the rated version
- "Larger net" / "Girthier net", "L1=1024" (#68 and #69, opened and
  merged 2026-06-29 between 15:39 and 15:52 UTC, after v2.0.1)
  [33, PR text]:
  - **+18.10 ± 5.64 at 10,000 nodes** (passed);
  - **−11.02 ± 5.55 at 10+0.1** (failed);
  - **−7.16 ± 4.39 at 40+0.4** (failed);
  - −5.89 ± 8.98 at 40+0.4 with 4 threads (undecided);
  - +5.02 ± 3.54 at 60+0.6 with 8 threads and 512 MB (not finished);
  - merged all the same; the next day's commit reads "bigger net, scales
    ... not fully tested properly but we tryna merge some bangers for
    TCEC" [34, commit text].
- 2026-07-01: "permute net for sparsity ... slightly faster". 2026-08-04:
  "reperm". 2026-09-29: "neon speedups". 2026-10-07: "various fixes, and
  merged kings" [34, commit text]. No figures.
- The nets repository lists files up to `pp_big11` (2026-10-07) with no
  notes [35, release list].

### UNVERIFIED and not published
- Everything the README delegates to the source file: accumulator width
  in 2.0, threat-input count and relation, pawn-pawn count and masking
  rule, king-bucket layout, integer types per layer: UNVERIFIED (only in
  code).
- Output-bucket selector: not published.
- Accumulator activation: not published.
- Data size, self-play node budget, openings, filtering, tablebase use:
  not published.
- Share of Vine data in the 2.0 net: not published.
- Whether the big network's labels are static evaluations or searches:
  not published.
- Size and architecture of the big labelling network: not published.
- How the "Sparser net" was made sparser: not published.
- Net file size (only the roughly 67 MB binaries are visible).
- Whether CCRL's "2.0" is the v2.0 or the v2.0.1 build: UNVERIFIED; both
  predate the larger net.

---

## Integral 8 (CCRL #14, 3751)

**One-line architecture:** as the engine writes it in the README at tag
v8: "[(768 + 1x11)x12hm (Factorized) + 60144hm -> 768]x2 -> (16 -> 32 ->
1)1x8", described as "a horizontally mirrored perspective network,
containing 12 factorized king input buckets with threat inputs and
fifty-move rule inputs, an L1 of 768 neurons, an L2 of 16 neurons, an L3
of 32 neurons, and 8 output buckets" [38, README at v8]. Released
2026-09-11 [39, release notes].

### Inputs
- Feature set: per king bucket, 768 piece-square inputs plus 11
  fifty-move-rule inputs; plus 60,144 mirrored threat inputs
  [38, README]. Per perspective that is 12 × 779 + 60,144 = 69,492 by my
  arithmetic.
- King input buckets: 12, factorised [38, README]. Layout: not published.
  Growth: "add 4 input buckets" (#75, 2024-09), 9 (#99, 2024-10), 12 (v7,
  2025-02), 16 after v8 (#256) [41, PR text; 38].
- Horizontal mirroring: yes, since #69 (2024-09): +4.05 ± 3.14 at 8+0.08
  [41, PR text]. The exact rule is not published.
- Threat or attack inputs: 60,144, added by #243 (2026-08-30): **+24.43 ±
  7.77 at 40+0.4**. The PR's commit titles mention table lookups for the
  threat index, ray geometry on a mailbox board with AVX2, separate threat
  accumulators and incremental threat updates [41, PR text]. Which
  attacker and victim pairs are included is not published.
- Pawn features: none in v8 (pawn pairs came after; see "Since").
- Other input relationships: 11 half-move-clock inputs ("1x11"), in v8
  tied to the king bucket [38, README]; #246 (2026-09-09), "Integral's
  first novel neural network architecture patch": +1.54 ± 1.17 at 20,000
  nodes, +2.07 ± 1.63 at 10+0.1, +3.66 ± 1.93 at 10+0.1 on a fortress
  book, +3.70 ± 2.40 at 40+0.4 [41, PR text]. How the clock maps to the 11
  inputs is not published.
- Factoriser: yes, on the king buckets ("Factorized") [38, README], since
  #99 [41, PR title].

### Body
- First hidden layer width per perspective: 768 [38, README]. It had been
  1280 in v7 and 1536 from 2025-03 (#182); the threat-input net shrank it
  [38, README at v7; 41, PR text].
- Further layers: 16, then 32, then 1 [38, README].
- Layer stacks: "(16 -> 32 -> 1)1x8": one head per output bucket
  [38, README].
- Output buckets: 8 [38, README]; selector not published.
- Skip connections, pairwise multiplication, other structure: none stated.
  In v8 the threat features and the piece-square features have separate
  accumulators (merged only after v8, #266) [41, PR text].

### Activations
- After the accumulator: not published.
- In the head: not published.

### Quantisation
- Integer types per layer: not published.
- Quantisation-aware training or other rounding care: with the first multi-layer net, "weight clipping and
  increasing L1 quantization" gained +4.42 ± 2.76 (#153); one 2025 net was
  tested "with rounded input layer" (#201) [41, PR text]. QAT: not
  published.

### Inference speed
- Accumulator refresh cache: "Cache each bucket's last known accumulator
  (finny tables)" (#81, 2024-09): +7.78 ± 3.78 at 8+0.08 [41, PR text].
- Lazy or deferred accumulator updates: "Only update the accumulator when
  evaluating (lazy updating)" (#77): +9.21 ± 5.17 at 8+0.08 [41].
- Fused updates: "Finny table fused updates" (#192, contributed by
  pawnocchio's author): +3.45 ± 2.23 at 4+0.04; templated fused updates
  (#179): +1.18 ± 2.16 at 5+0.05, no functional change [41].
- Accumulator stack: "Avoid copying accumulator when updating" (#67):
  **+27.95 ± 9.53 at 8+0.08** [41].
- Pairwise multiplication of accumulator halves: not stated.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: "Sparsity table speedup" (#171): +5.90 ± 4.21
  at 4+0.04; "Sparse Neuron Permutation" (#185): no figure [41].
- Evaluation cache: not published.
- SIMD and VNNI work: SIMD inference (#58, 2024-09): +40.32 ± 11.29 at
  8+0.08; SIMD for the accumulator (#130): +2.42 ± 1.83; inference fix and
  speedups (#181): +4.21 ± 5.12; "Speedup and refactors" (#242): +4.21 ±
  2.45 at 4+0.04; faster threat-input updates (#244, by a contributor):
  +4.21 ± 2.55 at 10+0.1 [41]. Nothing on AVX-512 or VNNI specifically.
- Memory layout and prefetching: "Pre-process the network and use it
  directly from the binary" (#190). The PR posts two pairs of
  nodes-per-second figures (about 951k and about 1.27M) with the patched
  and base builds within 0.1% of each other in each pair; what separates
  the pairs is not explained [41]. Net file size: not published.
- Anything else that made the network faster: early "Accumulator
  speedups" (#53): +20.11 ± 8.70 at 1+0.01 [41].
- Speed cost or gain reported for any architecture change: none as nps
  for v8. Fixed-node against timed results are given for several width
  steps under "Measured gains".
- Hardware sensitivity reported: none for v8 (see #266 and #262 under
  "Since").

### Training data
- Size: "Dataset grew to 16.7b unfiltered positions" [39, release notes];
  "hundreds of millions of self-play games" [38, README].
- Type: own self-play. The first net was trained on data from version 4,
  which had a hand-written evaluation; "all early-network data has been
  thrown out"; "a majority of Integral's data is generated using a search
  of 20k soft-nodes per-side" [38, README]. No relabelling is stated.
- Openings, filtering, tablebase use: most games start with "3-4 randomly
  selected moves off a randomly selected opening from the
  UHO_Lichess_4852_v1 book"; "a majority of the data uses 5-man Syzygy
  endgame tablebases to guide the data generation search" [38, README].
  Earlier generations used 6 to 9 random opening moves drawn with a
  piece-type bias, without material-losing moves, and tablebase
  adjudication [38, README at v5 to v7]. Evaluation scaling is switched
  off during data generation (#174), and an insufficient-material check
  was added to its adjudication (#207) [41, PR titles].
- Public availability: the README says the datasets are public on Hugging
  Face [38]; today that repository holds only a 21-byte README (MIT
  licence line) and a `.gitattributes` file, one commit [42, dataset card
  and file list]. So the data itself was not found there.

### Training recipe (concepts only)
- Trainer: bullet [38, README].
- Loss and target: not published for v8.
- Stages and schedule: not published for v8. Up to v7, each net was
  trained "on a fresh dataset using the prior network" [38, README at v7].
- Regularisation, optimiser, anything unusual: weight clipping (#153) [41]. AdamW at v8, by
  implication of the later switch (see "Since"). Nothing else.

### Measured gains for network changes
- First NNUE (#52, 2024-09): +78.52 ± 18.04 at 8+0.08; two further
  results in the same PR, not labelled, read +31.70 ± 10.54 and +35.64 ±
  10.85 [41, PR text].
- More positions (#55): +22.91 ± 9.83 at 25,000 nodes [41].
- Width 512 (#57): +10.73 ± 5.93 STC. Width 1024 with 1,411,841,446
  self-play positions (#64): +29.11 ± 9.89 STC [41].
- Width 1280 and 4 king buckets (#75): +23.36 ± 9.14 STC, +46.13 ± 14.09
  at 25,000 nodes [41].
- Width 1536 and 9 factorised king buckets (#99): +7.68 ± 3.89 STC,
  +16.09 ± 6.42 at 25,000 nodes [41].
- Multi-layer network (#153, 2025-01): +16.86 ± 5.86 at 8+0.08, **+29.53
  ± 7.41 at 40+0.4** [41].
- First layer 1536 on the multi-layer net (#182): +4.52 ± 2.88 at 40+0.4
  [41].
- Net "Zekrom v7" (#212, no description): +23.55 ± 7.10 FN, +19.91 ± 5.78
  STC, +25.88 ± 8.14 LTC [41].
- Threat inputs (#243): +24.43 ± 7.77 at 40+0.4 [41].
- Half-move-clock inputs (#246): +3.70 ± 2.40 at 40+0.4 [41].
- Release totals: v8 against v7: +99.16 ± 4.91 at 10+0.1, +109.63 ± 4.28
  at 40+0.4 [39, release notes].

### Architecture history
- v5 and v6 (2024-11, 2024-12): "(768x9 -> 1536)x2 -> 1x8" [38, README at
  v5 and v6].
- v7 (2025-02): "(768x12 (Factorized) -> 1280)x2 -> (16 -> 32 -> 1)1x8"
  [38, README at v7].
- 2025-03: first layer 1536 (#182) [41].
- v8 (2026-09): the line at the top of this section [38].

### Since the rated version
- "Bulbasaur" net (#253, 2026-09-20): "Added roughly 136M games of Vine
  data and 30M games of 10k soft nodes Integral data": +26.59 ± 8.01 at
  25,000 nodes, +20.71 ± 7.21 at 10+0.1, +14.94 ± 5.97 at 40+0.4
  [41, PR text]. So from here the data is mixed (own plus another
  engine's).
- Pawn-pawn pair inputs (#254), "Idea from Pawnocchio author!": +11.86 ±
  5.90 at 20,000 nodes, +6.63 ± 3.86 at 10+0.1, +7.22 ± 3.97 at 40+0.4
  [41].
- Half-move-clock weights decoupled from the king buckets and king
  buckets raised to 16 (#256): +4.23 ± 2.65 at 10+0.1, +2.17 ± 1.64 at
  40+0.4 [41].
- "Zapdos" net (#257): L1 regularisation of the feature-transformer
  output added to the loss: +4.27 ± 2.87 at 20,000 nodes, +6.13 ± 3.70 at
  10+0.1, +5.23 ± 3.32 at 40+0.4 [41].
- Clang preferred as the default compiler, with PGO (#258) [41, PR
  title].
- Threat index speedups (#261): "1.4% +- 0.39" [41].
- Network and correction histories replicated per NUMA node (#262): 25.21
  ± 13.31 Elo in favour of pinning at 10+0.1 with 256 threads, tested on a
  third party's hardware [41].
- #266 (2026-10-27) [41, PR text]:
  - threat and piece-square accumulators merged: "+6% speedup on my
    7900X. Speedup varies based on CPU"; +1.70 ± 1.36 at 10+0.1;
  - Ranger against AdamW: +3.22 ± 2.26;
  - **first layer 1024 with Ranger: +21.35 ± 6.98 at 25,000 nodes, but
    +0.70 ± 1.64 at 60+0.6** (256 MB), the test undecided; the author adds
    that the gain "is less on highly concurrent machines, most likely due
    to lack of NUMA node pinning across SPRT workers" (the per-worker
    breakdown is an image that could not be read).
- Current README: "[768x16hm (Factorized) + 1x11 (HMC) + 59808hm (TI) +
  4560hm (PP) -> 768]x2 -> (16 -> 32 -> 1)1x8", with 16 king buckets
  [37, README]. It still says 768 although #266's title says 1024.

### UNVERIFIED and not published
- King-bucket layout and mirroring rule: UNVERIFIED (only in code).
- Which threat pairs make up the 60,144 inputs: not published.
- How the half-move clock maps to 11 inputs: not published.
- Output-bucket selector: not published.
- Activations (accumulator and head): not published.
- Integer types per layer; QAT: not published.
- Net file size: not published.
- Loss, result weighting and schedule of the v8 net: not published.
- Share of data at the 20k-soft-node budget ("a majority" only) and the
  budget of the rest: not published.
- That the v8 net contains no Vine data: an inference from dates (the
  Vine addition is PR #253 of 2026-09-20, nine days after v8)
  [prior survey: same caveat]; UNVERIFIED.
- The public dataset: not found at the linked repository today.
- Licence: none stated on the repository pages opened today
  ([prior survey]: no licence detected); the dataset card says MIT.
- The author's name is not on the pages opened; the GitHub login is
  aronpetko.

---

## Cross-engine notes for Fork (drawn only from the records above)

1. **A wider first layer wins at fixed nodes and loses or draws on the
   clock, in three engines.** pawnocchio's 1024-wide net: +18.1 at fixed
   nodes, −11.0 at 10+0.1, −7.2 at 40+0.4, positive only at 60+0.6 with 8
   threads. Integral's 1024-wide net: +21.4 at fixed nodes, +0.7 at
   60+0.6. Berserk's 2022 single-layer 1024: −11.2 STC, +7.0 LTC, reverted.
   Alexandria's 16-bucket net: −1.3 STC, +12.9 LTC. This is Fork's own
   pattern; none of the three found a fix other than a longer time control
   or more threads.
2. **The inputs that paid most were threats, then pawn pairs, and they
   came with a narrower first layer.** Threat inputs: +32.9 LTC (Cinder),
   +24.4 LTC (Integral), +13.4 LTC (Alexandria, after 8.0.0), bundle +30.3
   LTC (pawnocchio). Integral's threat-input net has a 768-wide first
   layer where its 2025 net had 1536; Berserk shipped 512 after trying
   1536 and 1024; Gaia
   keeps 1024 with int8 threat rows. Pawn pairs alone: +3.9 STC (Cinder),
   +7.2 LTC (Integral), +1.9 LTC (Berserk), about +13 LTC as part of a
   reshuffle (Alexandria).
3. **Speed work with a number attached** (collected in the final message
   and in each engine's "Inference speed"): the largest single items are
   avoiding accumulator copies (+28.0 Integral, +11.0 Alexandria), the
   refresh cache (+25.9 Alexandria, +9.9 Cinder, +7.8 Integral, +7.1
   Berserk), lazy updates (+11.8 Berserk, +9.2 Integral), the sparse first
   dense layer (+10.2 pawnocchio), explicit vectorisation of accumulator
   updates (+19.1 Cinder), register tiling of the threat update (+8.6% nps
   Berserk on AVX-512; +3 to 4% nps Alexandria on AVX2), and Cinder's
   reduction of unrolling that had caused register spill on plain AVX-512
   (+40.5). Berserk's 2023 speed table shows its VNNI build slower than
   its plain AVX-512 build.
4. **Result-heavy or score-only targets are not settled.** Berserk gained
   at every step toward a result-only target in 2023 (+11, +5 to +7, +3)
   and again +11.7 LTC from a short result stage in 2026; pawnocchio's
   result-only retrain was −1.7 STC, +4.2 LTC and was partly undone after
   relabelling; Cinder went the other way and trains on scores only (+8.1);
   Gaia lowered the result weight twice for small gains.
5. **Labels from a much larger own network** (pawnocchio): between +0.5
   and +5.7 over four tests for the first relabel, and +11 to +12 when the
   big network itself got threat and pawn-pair inputs. This is the only own-data route in this
   group that reports a double-digit gain from labels alone.

---

## Sources

All opened on 2026-11-14. "Used for" names the engine sections that cite
the page; "nav" means it was opened only to find other pages; "nothing
used" means it held nothing about the network.

| # | URL | What it is | Source type | Used for |
|---|---|---|---|---|
| 1 | https://raw.githubusercontent.com/jromang/gaiachess/HEAD/README.md | Gaia README, main | README | Gaia |
| 2 | https://raw.githubusercontent.com/jromang/gaiachess/v4.4.1/README.md | Gaia README at the rated tag | README | Gaia |
| 3 | https://raw.githubusercontent.com/jromang/gaiachess/v4.3.0/README.md | Gaia README at v4.3.0 | README | Gaia |
| 4 | https://raw.githubusercontent.com/jromang/gaiachess/v4.2.2/README.md | Gaia README at v4.2.2 | README | Gaia (same T1 line as 3) |
| 5 | https://github.com/jromang/gaiachess/releases (pages 1 to 3; page 3 empty) | Gaia release notes 4.1.0 to 4.4.3 | release notes | Gaia |
| 6 | https://huggingface.co/jromanghf/gaiachess-networks/raw/main/README.md | Gaia network model card, current | README (model card) | Gaia; pawnocchio (pawn-pair count) |
| 7 | https://huggingface.co/jromanghf/gaiachess-networks/raw/COMMIT/README.md for COMMIT = 15df2ff6a5b7be927f4e61bc451ae1234f708260, 481626e802d4ca076bed1c620ffbe141542bed05, 9e2bf6ca5e9c15c23b0e0ca46368dbda4664c133, 9d9dd3b3bcbb7477a9173f1525aceffeb5a86835, 7bba9c313ff5f07f2b857912c194d5dbbe0ab256, a4f6f97a13f4796cbb290094ac20805135f60777 | Six superseded revisions of the same model card | README (model card), superseded | Gaia (recipe of t5; Elo figures later withdrawn) |
| 8 | https://huggingface.co/jromanghf/gaiachess-networks/commits/main | Commit titles of the model-card repository | PR / issue / commit text | Gaia |
| 9 | https://huggingface.co/jromanghf | Author's Hugging Face page (models and datasets list) | other | nav (no training dataset listed) |
| 10 | https://github.com/jromang/gaiachess ; /tree/master/docs ; /tree/main/tools ; /commits/main/ | Repository front page, two folder listings (names only), commit titles | other; commit text | nav (docs holds images only; 19 squashed release commits) |
| 11 | https://www.talkchess.com/viewtopic.php?p=989751 and https://www.talkchess.com/viewtopic.php?t=86038&start=10, 20, 30, 40 | TalkChess thread "Gaia 4.1.0 — Back after 20 years" | forum | Gaia |
| 12 | https://www.chessprogramming.org/Gaia | CPW page (the 2003-2006 C engine) | CPW | nothing used |
| 13 | https://raw.githubusercontent.com/brunocodutra/cinder/HEAD/README.md | Cinder README | README | Cinder |
| 14 | https://github.com/brunocodutra/cinder/releases (pages 1, 2) | Cinder release notes | release notes | Cinder |
| 15 | https://github.com/brunocodutra/cinder/pulls?q=... (merged PRs: all non-bot pages 1 to 11; searches NNUE (2 pages), accumulator, inference, simd, quantization, sparse, training, feature, avx512, vnni, cache) | Cinder pull-request title lists | PR / issue / commit text (titles) | Cinder |
| 16 | https://github.com/brunocodutra/cinder/pull/N for N = 478 558 579 582 629 636 726 735 745 792 794 801 847 861 886 888 890 891 895 896 899 901 902 903 906 907 908 911 916 917 919 929 937 938 942 944 965 980 985 1006 1015 1019 1088 1094 1119 1124 1128 1130 1134 1158 1160 1168 1170 1179 1180 1189 1195 1198 1199 1202 1203 1205 1206 1207 1211 | Cinder PR conversation pages (65) | PR / issue / commit text | Cinder |
| 17 | https://github.com/brunocodutra/cinder/discussions ; https://github.com/brunocodutra/cinder/issues?q=is%3Aissue | Discussion and issue title lists | PR / issue / commit text (titles) | nothing used |
| 18 | https://raw.githubusercontent.com/jhonnold/berserk/HEAD/README.md | Berserk README, main | README | Berserk |
| 19 | https://raw.githubusercontent.com/jhonnold/berserk/REF/README.md for REF = eef2a8a, 14, 13, 12, 11, 10, 9 | Berserk README at the rated commit and at release tags | README | Berserk |
| 20 | https://github.com/jhonnold/berserk/releases (pages 1 to 4) | Berserk release notes 3.2.0 to 14 | release notes | Berserk |
| 21 | https://github.com/jhonnold/berserk/pulls?q=... (merged pages 1 to 8; closed unmerged page 1) | Berserk pull-request title lists | PR / issue / commit text (titles) | Berserk |
| 22 | https://github.com/jhonnold/berserk/pull/N for N = 342 359 365 371 372 373 384 397 402 404 408 409 410 438 445 452 453 458 471 477 482 499 504 505 506 508 520 572 583 594 600 603 604 609 610 613 | Berserk PR conversation pages (36) | PR / issue / commit text | Berserk; pawnocchio (pawn-pair count) |
| 23 | `gh api repos/jhonnold/berserk/commits?since=2023-09-01&until=2025-06-23` (2 calls: titles, then full messages of the network-update commits) | Berserk commit messages, 100 commits | PR / issue / commit text | Berserk |
| 24 | https://www.chessprogramming.org/Berserk | CPW page | CPW | nothing used beyond author and licence |
| 25 | https://raw.githubusercontent.com/PGG106/Alexandria/HEAD/README.md | Alexandria README | README | Alexandria |
| 26 | https://github.com/PGG106/Alexandria/releases (pages 1 to 3) | Alexandria release notes 3.0.1 to 9.1 | release notes | Alexandria |
| 27 | https://github.com/PGG106/Alexandria-networks/releases (pages 1, 2) ; https://github.com/PGG106/Alexandria-networks ; https://raw.githubusercontent.com/PGG106/Alexandria-networks/HEAD/README.md | Alexandria network releases net01 to net16, repository front page, two-line README | release notes; README | Alexandria |
| 28 | https://github.com/PGG106/Alexandria/pulls?q=... (merged pages 1 to 6; searches net, nnue, bucket, finny, accumulator, simd, avx, inference, quantis) | Alexandria pull-request title lists | PR / issue / commit text (titles) | Alexandria |
| 29 | https://github.com/PGG106/Alexandria/pull/N for N = 292 299 305 334 344 380 381 403 445 457 474 490 491 492 493 495 497 498 499 500 508 514 520 522 538 549 550 561 589 592 595 598 599 600 603 610 613 616 620 621 623 627 629 630 632 634 635 636 638 639 | Alexandria PR conversation pages (50) | PR / issue / commit text | Alexandria |
| 30 | https://raw.githubusercontent.com/JonathanHallstrom/pawnocchio/HEAD/README.md | pawnocchio README | README | pawnocchio |
| 31 | https://github.com/JonathanHallstrom/pawnocchio/releases (pages 1 to 3) | pawnocchio release notes v1.0 to v2.0.1 | release notes | pawnocchio |
| 32 | https://github.com/JonathanHallstrom/pawnocchio/pulls?q=is%3Apr (pages 1 to 4; page 4 empty) | pawnocchio pull-request title list | PR / issue / commit text (titles) | pawnocchio |
| 33 | https://github.com/JonathanHallstrom/pawnocchio/pull/N for N = 11 12 13 14 15 19 33 34 42 53 59 61 63 64 65 66 68 69 | pawnocchio PR conversation pages (18) | PR / issue / commit text | pawnocchio |
| 34 | https://github.com/JonathanHallstrom/pawnocchio/commits/main/ ; /commits/dev/ ; `gh api repos/JonathanHallstrom/pawnocchio/commits?sha=dev&since=2025-12-01` (4 calls, 289 commits) | pawnocchio commit titles and messages | PR / issue / commit text | pawnocchio |
| 35 | https://raw.githubusercontent.com/JonathanHallstrom/pawnocchio-nets/HEAD/README.md ; https://github.com/JonathanHallstrom/pawnocchio-nets/releases | Nets repository README (licence line) and release list (file names, no notes) | README; release notes | pawnocchio |
| 36 | https://furybench.com/test/6520/ ; https://furybench.com/networks/Pawnocchio/ | One OpenBench test page; the networks page (no content without login) | OpenBench | pawnocchio (confirms the #64 result; nothing more) |
| 37 | https://raw.githubusercontent.com/aronpetko/integral/HEAD/README.md | Integral README, main | README | Integral; pawnocchio (pawn-pair count) |
| 38 | https://raw.githubusercontent.com/aronpetko/integral/TAG/README.md for TAG = v8, v7, v6, v5 | Integral README at release tags | README | Integral |
| 39 | https://github.com/aronpetko/integral/releases (page 1; page 2 empty) | Integral release notes v1 to v8 | release notes | Integral |
| 40 | https://github.com/aronpetko/integral/pulls?q=is%3Apr+is%3Amerged (pages 1 to 8) | Integral pull-request title list | PR / issue / commit text (titles) | Integral |
| 41 | https://github.com/aronpetko/integral/pull/N for N = 52 53 55 57 58 64 67 69 75 77 81 99 102 130 145 153 167 171 174 178 179 181 182 185 190 192 193 196 199 201 202 212 242 243 244 246 253 254 256 257 261 262 266 | Integral PR conversation pages (43) | PR / issue / commit text | Integral; pawnocchio (#192) |
| 42 | https://huggingface.co/datasets/aronpetkovski/integral-datasets/raw/main/README.md ; https://huggingface.co/datasets/aronpetkovski/integral-datasets/tree/main | Integral dataset card (licence line only) and file list (two small files) | README; other | Integral |
| 43 | Failed or empty: https://www.chessprogramming.org/Alexandria, /Integral, /Pawnocchio, /Cinder (404 each); https://wiki.chessdom.org/Berserk, /Alexandria, /Integral, /Pawnocchio, /Cinder, /Gaia (404 each); https://raw.githubusercontent.com/jhonnold/berserk/fen-gen/README.md (404); https://github.com/JonathanHallstrom/pawnocchio (front page, file names only, no prose document besides the README) | Failed fetches and one navigation page | CPW; TCEC; README; other | none |
| 44 | https://www.talkchess.com/viewtopic.php?p=989822, 989906, 990140, 990251, 991403, 976425, 991475 | TalkChess pages reached from search results (Gaia follow-ups, "NNUE incomplete?", "pawnocchio 2.0 Pre", "New engine releases H1 2025", an unrelated engine) | forum | nothing used |
| 45 | Six web searches (Gaia, pawnocchio, Cinder, GaiaChess releases, Integral, pawnocchio 2.0 on TalkChess) | Search result lists | other | nav only; no fact taken from a snippet |
| P | the agent's scratch folder (engines.md, sources.md, comparison.md sections H to K, provenance.md), read-only | The earlier survey of 2026-11-10 | prior survey | all six |

Credit lines (engine; author as the pages name them; licence as the pages
state it):

- **Gaia** (GaiaChess): Jean-François Romang and David Rabel; GPL-3.0 or
  later [1; 6]. Trainer credit: Bullet by jw1912.
- **Cinder**: GitHub user brunocodutra (no personal name on the pages
  opened; Bruno Dutra per the prior survey); GPL-3.0 [13]. Credits bullet by Jamie Whiting, Lc0 data under
  the ODbL, and shakmaty-syzygy by Niklas Fiekas.
- **Berserk**: Jay Honnold; GPL v3.0 per CPW [24; 20]. Credits Grapheus
  and CudAD (Luecx), bullet, Koivisto, and for the 2026 architecture
  PlentyChess, Stockfish and pawnocchio.
- **Alexandria**: GitHub user PGG106, with contributors (among them
  cj5716); licence not stated on the pages opened (GPL-3.0 per the prior
  survey). Credits bullet, CudAD, and Lc0 data under the ODbL.
- **pawnocchio**: Jonathan Hallström; code GPL-3.0, assets CC-BY-ND 4.0
  [30], nets CC-BY-SA [35]. Credits bullet, Stormphrax, Pyrrhic (Andrew
  Grant), and contributors kelseyde, jgilchrist and anematode.
- **Integral**: GitHub user aronpetko (Hugging Face name aronpetkovski);
  no licence stated on the repository pages opened; the dataset card says
  MIT [42]. Credits bullet; pawnocchio's author for pawn-pair inputs and
  fused cache updates.

---

## Clean-room statement

I opened no source file, header, build file, training script, trainer
configuration, network-loading code, diff, patch, "Files changed" tab,
blame view, code-search result or raw source file of any engine or trainer,
and I read no network file's bytes or header. I cloned no repository and
downloaded no release archive, binary or network file. What I saved to my
folder is HTML of prose pages, raw README and model-card prose, and commit
messages from the commit-list endpoint (which returns no diff).

Things that came close, and how they were handled:

- **pawnocchio's README sends readers to a source file** for the network's
  specifics. I did not open it; those fields are UNVERIFIED (only in
  code).
- **Code fragments on prose pages.** READMEs and model cards contain build
  commands in code fences. My page-to-text script drops any `<pre>` block
  that looks like code and keeps only test-result and plain-text blocks;
  for raw READMEs I filtered the fences. A few shell build lines (a
  download command and compiler invocations from the Gaia README and model
  card, and the "build it yourself" lines of the Berserk 14 release)
  were displayed while searching those pages. They are build instructions,
  not engine source; nothing was taken from them.
- **Identifiers inside PR and commit text.** Commit titles and PR
  descriptions (Berserk #594, #600 and #613, Cinder #1206 and #1207,
  Alexandria #620) name functions, macros and one source file, and a
  coverage bot's comment on Cinder PRs lists source file paths. This is PR
  and commit text, which the brief allows; I recorded the concepts only
  and no identifier or file name.
- **Values I saw and left out on purpose:** quantisation scale constants
  (Cinder #1170, Alexandria #334 and #344 titles, Berserk #508), result
  weights and learning-rate figures (Gaia model card, Berserk commit
  messages, pawnocchio titles), and skip rates and schedule lengths (Gaia
  model card). They are described as concepts.
- **Folder listings.** I viewed the file-name listing of the Gaia
  repository root, its docs and tools folders, and the pawnocchio root,
  only to look for prose documents. No file in them was opened.
- **Review comments.** I checked the saved PR pages for embedded diff
  tables; none of the 212 pages contains one.
- **GitHub API:** 6 calls to the commit-list endpoint (messages only) and
  3 rate-limit checks; the remaining quota stayed above 4,500.
- **One fact from a search snippet was not used:** a snippet named
  Cinder's author; no opened page does, so the report gives the GitHub
  login only.
- **Superseded prose.** The Gaia Elo figures and the t5 recipe come from
  earlier public revisions of the model card that the author has since
  shortened ("Model card: no Elo figures"). They are marked as such.

Deleted: only my own working files `part1.md`, `part2.md`, `part3.md` and
`part4.md` in my scratch folder, by exact name, after they were joined
into `report.md`. Everything else I created (the `pages` and `scripts`
folders and `fetchlog.txt`) is left in place. Nothing outside my folder
was written, edited or deleted, and nothing was committed.
