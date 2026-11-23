# Network records, group D: Caissa, Viridithas, Stormphrax, Hobbes, Horsie, Lizard

Clean-room network survey of 2026-11-14 ([README](../README.md)). Written by survey agent D from public prose only and assembled unchanged except for local paths. Source numbers in brackets refer to the Sources table at the end of this file. Every engine here is REFERENCE ONLY for ideas; its code, nets and data are OFF-LIMITS for Fork.


Date of all page visits: 2026-11-14. Source numbers refer to the table in "Sources". Source types: README, release notes, PR text, commit text, prose log, blog (the author's own website), slides, prior survey.

Conventions:

- "FN" = fixed-nodes test; "STC" / "LTC" as the engine itself ran them (time control given with each figure); "VSTC" = 4+0.04 or shorter.
- Elo figures are the engines' own self-play results, with their 95% intervals where the page gave them.
- Trainer hyperparameter values, quantisation scales and clipping bounds appear on several pages opened. They are described as concepts only; their values are not recorded.
- "Inferred" marks a conclusion drawn from dates or file sizes; each is repeated under "UNVERIFIED and not published".

---

## Caissa 2.0 (CCRL #15-16, 3747)

**One-line architecture:** `(32×768 → 1536) × 2 → 16 → 32 → 1`, with 8 copies of the whole output network picked by piece count. As the engine writes it [1, README] [2, release notes].

### Inputs
- Feature set (what an input means; inputs per perspective if stated): absolute piece-square inputs, 768 per perspective (12 piece types × 64 squares), one set per king bucket; one accumulator per side [1, README].
- King input buckets: 32 [1, README] [2, release notes]. Layout in words: not published (see UNVERIFIED). Growth: none (0.7 to 1.10) → 5 in 1.11 (2.3 B positions) → 11 in 1.20 (12.6 B) → 32 in 1.25 (net file about 17 MB → 48 MB) [2, release notes].
- Horizontal mirroring: yes, "horizontal symmetry" of the piece coordinates [1, README]. The trigger is not spelled out.
- Threat or attack inputs: none published.
- Pawn features: none published.
- Other input relationships: none in the network. Outside it the engine keeps hand-written endgame routines and, since 1.24, a castling-rights bonus for FRC/DFRC [1, README] [2, release notes].
- Factoriser or other training-only input structure: yes. One shared 768-input block is trained beside the 32 buckets and folded into every bucket on export, so the net file format is unchanged [1, README] [5, commit text]. Reported effect: clearly lower validation error in a short from-scratch run, no difference when fine-tuning an existing net, about 13% lower trainer throughput [5, commit text].

### Body
- First hidden layer (accumulator) width per perspective: 1536 (up from 1024 in 1.26) [1, README] [2, release notes].
- Further layers: two hidden layers, 16 and 32 wide, then one output (`1536 → 16 → 32 → 1` after pairing) [1, README].
- Layer stacks: 8 copies of the whole output network, chosen by piece count [1, README] [2, release notes].
- Output buckets: the same 8 (stack and output bucket are one thing here). History: 4 last-layer variants by piece count in 1.6 ("idea borrowed from Stockfish"), 8 in 1.8 [2, release notes].
- Skip connections, pairwise multiplication, other structure: pairwise multiplication of the two halves of each accumulator, giving 768 values per perspective and 1536 inputs to the first dense layer [1, README].

### Activations
- After the accumulator: clip, then pairwise product [1, README].
- In the head: clipped ReLU in both hidden layers [1, README]. No dual activation published. (The last single-layer net, 1.26, used squared clipped ReLU on its one hidden layer [2, release notes].)

### Quantisation
- Integer types per layer: int16 feature-transformer weights; int8 weights in both hidden layers [1, README]; the paired activations are unsigned bytes, the output layer has int16 weights, biases are 32-bit [5, commit text]. No float layer.
- Quantisation-aware training or other rounding care: all layers are trained against the integer grid used at run time [1, README]. A bucket weight and its factoriser weight are rounded as one sum [5, commit text]. Since the rated version the trainer's float reference network is rounded the same way, after the author found the unrounded master weights drift off the grid during fine-tunes [5, commit text].

### Inference speed
- Accumulator refresh cache: present since 1.12 ("accumulator caching"); no figure [2, release notes] [1, README].
- Lazy or deferred accumulator updates: yes. A refresh walks from the nearest valid ancestor and fills in every stale accumulator on the path, so sibling nodes reuse the intermediate ones: +1.24 ± 1.20 Elo STC [2, release notes] [5, commit text]. Eager updates are forced only in PV nodes and from a small depth upward: about 2% faster when that depth went from 1 to 3 (1.25) [2, release notes].
- Fused updates: matching add/remove pairs are cancelled while the changes are collected (introduced as an overflow fix in 1.25; no speed figure) [2, release notes].
- Accumulator stack: the accumulator copy during a refresh was optimised in 1.25 (no figure) [2, release notes].
- Pairwise multiplication: halves the first dense layer's work and leaves about 75% of the paired activations at zero, which is what the sparse path needs [5, commit text].
- int8 layers: int8 weights in both hidden layers; pairing caps the activations so the byte-wise multiply-add cannot saturate [5, commit text].
- Sparse first dense layer: the layer runs only over non-zero groups of 4 input bytes. Against the scalar reference loop it replaced: +219.7% nps (AVX2, MSVC build) [5, commit text]. A permutation tool reorders accumulator neurons so rarely-active pairs share a group: live groups 47.45% → 36.56% (121 → 94 of 256 per evaluation), 2.62 M → 2.69 M nps; a greedy ordering beat a "busiest first" sort by about three points [5, commit text].
- Evaluation cache: a cached network score in the evaluator context was removed at 2.0 with no functional change (title only; no figure) [5, commit text].
- SIMD and VNNI work: hand-written AVX-512 (optional VNNI and VBMI2), AVX2 (optional VNNI), SSE4, NEON and scalar paths [1, README]. A new AVX-512 "Ice Lake" build: +4.2% nps on Zen 4 [2, release notes] [5, commit text]. Turning on AVX-512 and AVX-VNNI in the makefile: +3.86 ± 2.15 Elo overall, split by worker CPU as +0.91 ± 3.47 (BMI2), +1.16 ± 3.77 (AVX-VNNI), +10.81 ± 3.96 (AVX-512) [5, commit text]. Horizontal-add instructions replaced by shuffle plus add (1.25, no figure) [2, release notes].
- Memory layout and prefetching: first and second dense-layer weights are stored grouped by input so the sparse path reads the embedded file in place (zero-copy) [5, commit text]. Net file: 75.7 MB for the rated net, 50.4 MB for 1.26's, about 48 MB for 1.25's [3, release notes] [2, release notes]. Large pages are named for the transposition table only [1, README].
- Anything else: GCC code-generation flags, +0.5% to +2.5% nps [2, release notes].
- Speed cost or gain for an architecture change: the switch to the multilayer net as a whole: +20.58 ± 6.13 (60+0.6), +18.21 ± 4.88 (10+0.1), +4.95 ± 3.02 (DFRC 10+0.1), +53.67 ± 7.28 (endgame book), +29.93 ± 7.14 at 10k nodes [5, commit text]. No nps ratio between the single-layer and multilayer nets is published.
- Hardware sensitivity: the AVX-512 split above (the gain is almost all on AVX-512 machines) [5, commit text].

### Training data
- Size: "20.5+ billion" self-play positions [1, README]; the next net's release note states 21.0 B positions in 2,849 files [3, release notes]. The rated net "was trained from scratch for 312B positions" (positions seen, not distinct positions) [2, release notes].
- Type: own self-play, with one exception stated by the author: a "Fishtest1" set from Stockfish LTC games on Fishtest, about 1% of the total [4, README]. So: **mixed** (about 99% own). Games are generated at fixed nodes or fixed depth [1, README]. Budgets stated in prose over time: at most 50k nodes and depth 14 (1.4); 20k and 40k nodes per move (1.6) [2, release notes].
- Openings, filtering, tablebase use: UHO books or DFRC openings [1, README]. Positions from SPRT test games (about 350 M in 1.16, about 220 M more in 1.17), games started from positions sampled from TCEC, CCRL and SP-CC games (1.14), about 40 M random endgame positions scored with 7-man tablebases (1.17), 32 M positions from an endgame book (1.26, worth over 50 Elo on that book), "queens-only" games (1.23), 7-man tablebases for scoring endgame positions since 1.5 [2, release notes]. Later additions named in a net note: "missing-pawn" books with seven queens, bishops, knights or rooks, a fortress book and others [3, release notes]. Old games are purged so the net sees only recent engine versions [1, README]. A PGN converter keeps quiet, non-check positions and can add Syzygy WDL [2, release notes].

### Training recipe (concepts only)
- Trainer: the author's own CUDA trainer, written from scratch [1, README].
- Loss and target: a blend weight between search score and game result exists as a trainer option [5, commit text]. The later fine-tune stages use the game result only [3, release notes].
- Stages and schedule: cosine learning-rate schedule with checkpoints and resume [1, README]. The multilayer net was built in steps: a from-scratch run; a head-only fine-tune with the feature transformer frozen (+3.30 ± 1.92 STC, +1.91 ± 1.46 at 25k nodes) [5, commit text]; a further net (inferred to be the 1536-wide retrain) [3, release notes]; finally the last layer of buckets 1-7 tuned by SPSA in games: 6,769 iterations, 108,304 games at 6+0.06, +6.09 ± 3.21 (40+0.4) and +5.97 ± 2.73 (8+0.08) [5, commit text] [2, release notes].
- Regularisation, optimiser, anything unusual: AdamW [1, README]. Weight decay on the feature transformer, none on the head [3, release notes]. "Bucket leak": a position near the edge of a piece-count range also trains the neighbouring output network [5, commit text]. Optional dead-neuron revival in the head [5, commit text]. Training batches are sorted by king bucket for throughput [5, commit text]. Throughput: 2.07 M positions/s for a full fine-tune and 3.22 M for a head-only one, on an RTX 5070 [3, release notes].

### Measured gains for network changes
- Multilayer net replacing the single-layer SCReLU net: +20.58 LTC (60+0.6), +18.21 STC (10+0.1), +29.93 at 10k nodes [5, commit text].
- Head-only fine-tune, feature transformer frozen: +3.30 STC [5, commit text].
- Next net ("eval-ml-8"): +7.32 ± 3.54 (60+0.6), +1.58 ± 1.19 (10+0.1), +22.73 ± 5.65 at 25k nodes [5, commit text]. The file grew from 50.5 to 75.7 MB at this step [3, release notes], which fits the widening from 1024 to 1536 (inferred).
- SPSA of the last layer in games: +6.09 (40+0.4), +5.97 (8+0.08) [5, commit text].
- SCReLU on the single hidden layer (1.26): +7.17 ± 3.01 STC, +3.93 ± 2.78 LTC, +22.52 ± 5.18 on an endgame book [5, commit text].
- 32 M endgame-book positions added: over +50 on that book [2, release notes].
- Release 2.0 over 1.26: +40.41 ± 4.85 (60+0.6), +29.15 ± 4.59 (10+0.1), +28.69 ± 10.70 (DFRC 10+0.1) [2, release notes].

### Architecture history
- 0.6: a Stockfish NNUE, temporarily [1, README]. 0.7: own network and trainer [2, release notes].
- 1.2: `704x512x16x32`. 1.5: `704-768-1` [2, release notes].
- 1.6: accumulator 1024; 4 last-layer variants by piece count. 1.7: 1536. 1.8: 8 variants [2, release notes].
- 1.9: pure network evaluation, PSQT dropped [2, release notes].
- 1.10: accumulator split into white and black perspectives, 1024 wide [2, release notes].
- 1.11: 5 king buckets. 1.12: accumulator 1024, accumulator cache. 1.20: 11 king buckets [2, release notes].
- 1.25 (2026-04): 32 king buckets, new CUDA trainer [2, release notes].
- 1.26 (2026-08): SCReLU [2, release notes].
- 2.0 (2026-09-19): multilayer, pairwise, 1536 wide, sparse inference [2, release notes].

### Since the rated version
- 2026-10-17: a result-only fine-tune of the pre-SPSA net with the SPSA last-layer change added back on top ("transplant"): +3.47 ± 2.00 (10+0.1), +0.98 ± 1.25 (60+0.6, stopped) [3, release notes] [5, commit text].
- 2026-11-13/14: 16 output networks instead of 8, the piece-count bucket doubled by "any queen on the board": +1.40 ± 1.08 (10+0.1), +1.35 ± 1.28 (60+0.6). The new net was started by copying each old head twice and fine-tuning the heads only [5, commit text] [3, release notes].
- 2026-11-08: both perspectives updated in one pass when both are one move from the parent: +0.67% to +0.83% nps. Forced eager updates one ply deeper only: +0.83% nps. Accumulators moved out of the per-node search record so neighbouring plies share cache lines: +0.41% nps [5, commit text].
- Many of these commits carry an AI co-author line [5, commit text].

### UNVERIFIED and not published
- King bucket layout: not published. 32 equals the number of squares on a mirrored half board, so one bucket per king square is likely, but no page opened says so.
- Which net file ships in 2.0: inferred to be the SPSA-tuned "eval-ml-8-152B" (published the day of the release and called master's net a month later) [3, release notes]. Not stated on the release page.
- How the "312B positions" divide between stages: not published.
- Node budget of the current data: not published in prose (file-name tokens in a net note suggest about 15k-16k nodes).
- The result/score blend of the main training stage: only as trainer options; UNVERIFIED (only in code).
- Whether the network weights use large pages; any evaluation cache after 2.0: not published.
- The data source of 0.7's first net: not published [prior survey].

---

## Viridithas 20.0.0 (CCRL #15-16, 3747)

**One-line architecture:** `(704×16hm + (59808 + 4560)hm → 1024)×2 → (32 → 32×2 → 1)×8`. As the author writes it, on the network release that introduced pawn-pawn inputs one week before 20.0.0 [8, release notes]. Two later nets before the release changed training only (see UNVERIFIED for the exact net).

### Inputs
- Feature set: 704 piece-square inputs per king bucket (768 reduced to 704 by merging the king planes, which the bucket layout makes possible) [8, release notes] [10, PR text], plus 59,808 threat inputs and 4,560 pawn-pawn inputs [8, release notes]. Before pawn-pawn inputs the threat block was 60,144 [8, release notes] [10, PR text].
- King input buckets: 16 [7, release notes] [8, release notes]. Layout: UNVERIFIED (see below). Growth with data: none → 4 mirrored (2024-01, +5.47 ± 3.57 LTC) → 9 (2024-03, +34.12 FN, +23.64 STC) → 13 tried → 16 with a factoriser (2024-07) [11, prose log] [8, release notes]. The author describes buckets as a hand-gated mixture of experts, for example one expert for the back rank so it need not learn king-escorts-pawn positions [19, blog].
- Horizontal mirroring: yes ("hm"), since the 4-bucket net [8, release notes] [11, prose log]. Trigger not described in prose.
- Threat or attack inputs: yes, since 2026-04-15. The feature set is the "SFNNv12" one, with every threat that involves a king left out [10, PR text]. Update machinery, each a separate patch: no intermediate buffering in the threat update, prefetching of threat weights, branchless threat indexing [10, PR text]. The author credits Stormphrax's implementation as the model [10, PR text].
- Pawn features: pawn-pawn inputs ("swedishchef's"), 4,560, since 2026-06-20 [8, release notes] [7, release notes]; a VBMI path builds their indices [10, PR text].
- Other input relationships: none published. Experiments with a PSQT subnet failed or were suspected buggy [11, prose log]. Planned in 2024: passed pawns, castling rights, bishop pair [17, blog]; no result published.
- Factoriser: a king-bucket factoriser arrived with the 16-bucket net. A fresh retrain with "whole-network factorisation" gained +7.81 FN and +2.06 ± 1.61 LTC (2025-05). Fine-tunes started from a net with the factoriser already merged lost 15 to 49 Elo; from the unmerged checkpoint they were about level; the author's lesson was that the factoriser matters "even for fine-tuning runs". Removing only the factoriser on the first dense layer later tested neutral (−0.31 ± 2.62), and it was dropped in the 2025-11 net [11, prose log] [8, release notes].

### Body
- First hidden layer (accumulator) width per perspective: 1024 [8, release notes]. It was 2560 before threat inputs [10, PR text].
- Further layers: three after the accumulator: 32, then 32, then 1. The second is written "32×2" because its matrix produces twice the width for the gated activation [8, release notes].
- Layer stacks: 8, selected with the output bucket; the author calls them "sparsely routed subnetworks" in all three later layers [23, blog].
- Output buckets: 8, by the number of pieces on the board [19, blog] [11, prose log]. Removing them tested about level (+1.06 FN on non-regression bounds, −1.10 ± 1.33 STC unresolved); they were kept [11, prose log].
- Skip connections, pairwise multiplication, other structure: pairwise multiplication after the accumulator (pairs half a vector apart) [20, blog]. A residual connection across the second layer, its input added to its output (2026-04) [8, release notes].

### Activations
- After the accumulator: clipped ReLU, then pairwise product; the author treats this as a gated unit with both branches activated [20, blog] [22, blog].
- In the head: hard-Swish on the first dense layer, SwiGLU on the second, sigmoid on the output in training [23, blog] [8, release notes]. Before 2026-01 both hidden layers used squared clipped ReLU. Stockfish-style dual activation was tried twice and lost (−4.92 ± 3.35 LTC, bundled with a schedule change; −5.52 ± 2.61 STC) [11, prose log].

### Quantisation
- Integer types per layer: the paired accumulator outputs are single bytes [20, blog]; the first dense layer's weights and inputs are int8 [27, slides]; the layers after it run in floating point, chosen because they are small and this avoids fixed-point error [20, blog].
- Rounding care: no weight clipping on the layers after the first dense layer [23, blog]. A 2024 re-quantisation made a fully 16-bit SIMD path possible (+16.76 ± 6.68 STC). A later scheme credited to Lizard's author restored full precision at the same speed (+9.06 ± 5.33 STC): the weight is multiplied in after clipping and before squaring, so everything stays in 16 bits [16, blog] [10, PR text] [11, prose log]. QAT: not published.

### Inference speed
- Accumulator refresh cache: one slot per king bucket holding a past position and its accumulator; on a bucket change the engine applies the piece difference to the cached entry instead of rebuilding [16, blog]. No separate figure.
- Lazy updates: changes are recorded and the accumulator is built only when an evaluation is asked for: about 2.3% faster (2024-02) [10, PR text] [16, blog]. "Speculatively" forcing the build for some positions: +7.15 ± 4.10 at 1+0.01 [10, PR text].
- Fused updates: add/subtract forms for quiet moves, captures and castling applied in one pass from the old accumulator to the new one: +8.88 ± 7.06 STC [16, blog] [10, PR text]. Applying all updates at once: +4.1 ± 4.3 (not a completed SPRT) [10, PR text].
- Accumulator stack: a stack of accumulators along the search path, with fused updates reading the parent and writing the child [16, blog].
- Pairwise multiplication: adopted to halve the cost of the first dense layer, the network's most expensive product [20, blog] [22, blog].
- int8 layers: first dense layer in int8, as above [27, slides].
- Sparse first dense layer: blocks of four activation bytes are tested as one 32-bit word and only non-zero blocks are multiplied [20, blog]. An L1-norm penalty on the accumulator outputs trains them to be sparse [20, blog]. Block sparsity is about 70% zero; the first hard-Swish net fell to 50% and lost its speed until the penalty was added [23, blog] [11, prose log]. Measured patches [10, PR text]:
  - permuting neurons to cut the non-zero count: +4.70 ± 2.86 at 4+0.04;
  - re-permuting for a new net: +3.74 ± 2.40 at 4+0.04;
  - breaking a data dependency in the sparse product: +8.75 ± 3.98 at 4+0.04;
  - unrolling the product: +4.87 ± 3.38 at 4+0.04;
  - computing the non-zero mask in the same pass as the activation: +1.53 ± 1.19 at 1+0.01;
  - propagating two inputs at a time: +3.69 ± 2.52 at 1+0.01.
- Evaluation cache: not published.
- SIMD and VNNI work: a generic SIMD layer gave about +28.9% on AVX-512, no change on AVX2 and about 30% slower on NEON until fixed [10, PR text]. "Register juggling" (keeping a fixed set of registers live across the refresh loop): about +3.3% on a laptop and about +1.7% on a server; the same idea applied to fused updates was about 0.6% slower [16, blog] [10, PR text]. Unrolling the feature transformer two at a time: +7.24 ± 5.60 at 1+0.01 [10, PR text]. NEON inference added 2025-10 [10, PR text].
- Memory layout and prefetching: prefetch before make-move state updates, about 8% faster (2024-02) [10, PR text]. Prefetch of threat weights: +1.98 ± 1.56 at 4+0.04 [10, PR text]. Weights are memory-mapped so many engine processes share one copy and put less pressure on the caches [10, PR text] [27, slides]. Nets are zstd-compressed and embedded: 52.4 MB compressed for the net of this period [8, release notes].
- Anything else: removing intermediate buffering in the threat update: +3.21 ± 2.18; branchless threat indexing: +2.51 ± 1.86; VBMI path for pawn-pawn indices: +2.22 ± 1.70; all at 4+0.04 [10, PR text].
- Speed cost or gain for an architecture change:
  - threat inputs (with accumulator 2560 → 1024 and first dense layer 16 → 32): "about 87% the speed of the old one" on AVX-512, for +27.43 ± 7.91 at 25k nodes, +2.98 ± 2.09 at 8+0.08, +5.38 ± 2.97 at 40+0.4 [10, PR text];
  - a 3072-wide net with a 64-wide second layer: +23.83 FN but −21.52 ± 6.67 at 40+0.4 [11, prose log];
  - accumulator 1024 → 1536 in 2023: the author expected a 50% slower evaluation and accepted +1.98 ± 1.60 LTC [10, PR text];
  - accumulator 2048 → 2560 alone: +19.04 FN, −0.21 ± 1.33 at 80+0.8 [11, prose log].
- Hardware sensitivity: the AVX-512 and NEON differences above; the slides call the 1024 → 32 dense layer the most expensive part of the engine [27, slides].

### Training data
- Size: not published for the rated net. Known steps: 963 M positions (2023-06), a 2,812 M set (2024-06), "5b" and "8b" sets in 2024-07 experiments, then injections of about 0.55 B, 1.2 B and more [11, prose log] [8, release notes] [18, blog].
- Type: own self-play only; "no network has ever been trained on the output of an engine other than Viridithas" [6, README]. Positions come from games at a small fixed node count per move, labelled with the game result and the engine's search value [21, blog]. "25k-node" data is the current high-quality tier; older data was purged and 25k-node data up-sampled in several nets [11, prose log] [10, PR text].
- Openings, filtering, tablebase use: datagen needs no opening book, with optional book starts since 2025-01 [6, README] [10, PR text]; one net added UHO-book games [11, prose log]. Classical and DFRC games are mixed [8, release notes]. In 2024 some runs had 6-piece tablebases and some had none [18, blog]. Data generated with evaluation scaling switched off was added in 2025-12 [8, release notes]. Less early-ply filtering was blamed for one failed net [11, prose log].

### Training recipe (concepts only)
- Trainer: bullet since version 11; marlinflow before [6, README].
- Loss and target: squared error on a blend of search value and game result [19, blog] [21, blog]. The author's main finding: the blend weight changes the scale of the net's output, so nets trained toward the result look bad unless the output scale is recomputed. With the scale matched, a pure-result net went from −28 to level at 25k nodes [21, blog]. An eval-scale tool was added for this [10, PR text].
- Stages and schedule: the 2025-11 net ramps the result weight up over the run, uses a cosine learning rate and heavy random skipping, and rescales the output: −3.49 FN, +4.84 STC, +9.29 ± 4.06 LTC, +9.27 ± 4.03 at 120+1.2 [8, release notes] [11, prose log]. A pure-result fine-tune at a very low learning rate added +2.38 ± 1.74 LTC [8, release notes]. The net of 20.0.0 uses a "new training schedule" credited to pawnocchio's author and derived from PlentyChess's (+16.57 ± 8.66 at 40+0.4, merged before the test finished) [10, PR text].
- Regularisation, optimiser, anything unusual: Ranger instead of Adam: +8.98 ± 3.92 LTC in 2026-06 (it had lost at LTC a year earlier) [8, release notes] [11, prose log]. L1-norm penalty on accumulator outputs [23, blog]. Schedule-free AdamW reached a lower loss but "did not prove stronger" [24, blog]. In a fixed-nodes gauntlet, Elo tracked final loss across widths 32 to 4096 [19, blog]. Squared clipped ReLU at 1024 matched plain clipped ReLU at 1536 in loss [18, blog].

### Measured gains for network changes
- Threat inputs: +27.43 FN, +2.98 STC, +5.38 LTC, at 87% speed [10, PR text].
- Pawn-pawn inputs: +3.65 ± 3.00 at 25k nodes (test not finished) [10, PR text].
- Residual connection across layer two: +8.05 FN, +8.21 STC, +9.38 ± 4.05 LTC [8, release notes].
- Hard-Swish for squared clipped ReLU in the head (with the sparsity penalty): +13.77 ± 5.04 STC, +5.90 ± 3.11 LTC [8, release notes].
- SwiGLU on the second dense layer: +5.47 ± 3.04 LTC [8, release notes].
- Multilayer head with pairwise (2024-08): +42.88 FN, +9.44 ± 4.12 LTC [11, prose log].
- 2048 wide, 16 buckets, factoriser: +31.64 FN, +0.51 STC, +4.83 ± 2.85 LTC [11, prose log].
- 8 output buckets with more data: +19.76 FN, +23.89 STC [11, prose log].
- Wider (2560) with more data: +22.50 FN, +2.90 ± 2.04 LTC [8, release notes].
- More data on the first threat net: +6.15 FN, +5.33 STC, +5.57 LTC [8, release notes].
- Failures worth knowing [11, prose log]:
  - fine-tune on recent data only with a pure result target, before the author used rescaling: −57.19 ± 2.69; the same with a low result weight: −9.67 STC, −6.36 at 120+1.2;
  - relabelling the data with the net's own static output: −2.72 FN, −3.12 LTC; with a 4096-wide teacher's output: −2.44 FN, −3.19 STC;
  - distilling from an 8192-wide teacher (2025): −12.69 FN, −25.95 STC;
  - rescoring with TD(λ): −3.55 FN, −4.05 LTC;
  - WDL-head nets: −14.70 FN to −33.72 LTC; a later value-supervised WDL head: +4.13 FN but −4.78 LTC (also [25, blog]);
  - result weight scaled by material: −20.89 LTC;
  - a skip from the first to the third dense layer: −10.23 STC; a 64-wide third layer: −9.36 STC.

### Architecture history
- 2022-10: first net, 768 inputs [7, release notes].
- 2023: 768×2 and 1024×2 nets, a HalfKA phase (64×2 to 768×2), then 1024×2 and 1536×2 unbucketed SCReLU nets [11, prose log] [8, release notes].
- 2024-01: 4 mirrored buckets, 1536. 2024-03: 9 buckets. 2024-07: 8 material output buckets; then 2048 with 16 buckets [8, release notes].
- 2024-08 (v14): `2048x2 -(pairwise)> 16 -> 32 -> 1`, permuted for sparsity [8, release notes] [7, release notes].
- 2025-01: 704 inputs (merged king planes), non-regression [8, release notes].
- 2025-12: accumulator 2560 [8, release notes].
- 2026-01: hard-Swish, then SwiGLU [8, release notes].
- 2026-04: threat inputs, accumulator 1024, first dense layer 32; then the residual connection [8, release notes] [10, PR text].
- 2026-06-20: pawn-pawn inputs. 2026-06-25: Ranger. 2026-06-26: new schedule. 2026-06-27: release 20.0.0 [8, release notes] [7, release notes].
- A 2048-wide variant of a 2026-01 net was built "for TCEC" [8, release notes].

### Since the rated version
- 2026-08-28: the main net is distilled from a much larger teacher net (teacher: +35.33 ± 8.65 at 25k nodes; student: +3.69 ± 2.35 at 40+0.4) [8, release notes] [10, PR text].
- 2026-08-31: improved initialisation and weight clipping: +6.52 ± 3.70 at 40+0.4 on non-regression bounds [8, release notes].
- 2026-10-01: huge pages for the transposition table and the network weights: +3.15 ± 2.15 at 4+0.04 [10, PR text].
- Licence changed from MIT to AGPL-3.0-only after 20.0.0; nets are CC0 [6, README].

### UNVERIFIED and not published
- King bucket layout for 16 buckets: UNVERIFIED (only as a code fragment inside a network release note, skipped under the brief). The 9-bucket and 4-bucket layouts exist only as images.
- The exact net inside 20.0.0: inferred to be the "new schedule" net merged the day before the release; the release page does not name it.
- Data size of the rated net: not published.
- Integer type of the feature-transformer and threat weights in 20.0.0: not published.
- Whether any factoriser is used in the rated net's training: not published after the 2025-11 note.
- Content of the "new training schedule": not published.
- Evaluation cache; tablebase use in current datagen: not published.

---

## Stormphrax 8.0.0 (CCRL #17, 3744)

**One-line architecture:** `(704x16hm+60144->640)x2->(32x2->32->1)x8`, as the author wrote it when threat inputs were merged (2026-02) [36, PR text]. Assembled additions before 8.0.0: a skip connection across the second dense layer and pawn-pawn inputs [36, PR text] [33, release notes]. The release itself gives no architecture string.

### Inputs
- Feature set: 704 piece-square inputs per king bucket (merged king planes), plus 60,144 threat inputs [36, PR text], plus pawn-pawn inputs (count not stated) [36, PR text] [33, release notes].
- King input buckets: 16 [36, PR text]. Layout: not published. Growth: buckets first in 3.0 (2023-10); 8 buckets with 1024 (2024-03, +19.44 FN, neutral to losing at STC, merged on trust in scaling); 16 buckets with 1280 (2024-07, +9.01 FN, +13.72 STC) [36, PR text] [33, release notes].
- Horizontal mirroring: yes ("hm"), since 2024-06 with a 1536-wide net: +34.97 FN, −4.84 ± 4.02 STC, +4.90 ± 2.91 LTC [36, PR text].
- Threat or attack inputs: "SFNNv12 style", with no threats to or from the king [36, PR text]. Removing the remaining king threats: −2.38 FN, +1.66 STC and a "decent net size reduction" [36, PR text]. Fast incremental threat updates were contributed by a second developer [36, PR text]. The piece-square part (with the biases) and the threat part are separate accumulators, so a king-bucket change does not refresh the threats: +9.04 ± 4.10 STC [36, PR text].
- Pawn features: pawn-pawn inputs from pawnocchio's author: +6.36 FN, +2.08 STC, +3.09 LTC for the inputs alone; +10.54 ± 4.61 STC together with the threat-inference speedups in the same patch [36, PR text].
- Other input relationships: none published.
- Factoriser: not published.

### Body
- First hidden layer (accumulator) width per perspective: 640 [36, PR text]. Earlier 1792 (first multilayer net), 1536, 1280, 1024 [36, PR text].
- Further layers: 32 (doubled to 64 values by the dual activation), then 32, then 1 [36, PR text].
- Layer stacks: 8 [36, PR text].
- Output buckets: 8; they replaced material scaling in 2023-11 [36, PR text]. Selector: not published.
- Skip connections, pairwise multiplication, other structure: pairwise since 2024-08 [36, PR text]. Skip connection across the second dense layer, "inspired by" Viridithas: +4.45 FN, −2.66 ± 3.22 STC, +1.82 ± 1.45 LTC [36, PR text].

### Activations
- After the accumulator: pairwise clipped ReLU [36, PR text].
- In the head: Stockfish-style dual activation on the first dense layer (the pre-activations are duplicated, one copy squared, both clipped, then concatenated): +6.95 FN, +6.20 STC, +12.05 ± 4.69 LTC. Clipped ReLU on the next layer [36, PR text].

### Quantisation
- Integer types per layer: the whole net is integer. Quantising the dense layers cost −6.36 ± 2.98 FN and −5.58 ± 2.39 LTC against float layers and was accepted for identical results on every platform. A follow-up (clipped ReLU on the last hidden layer, "better precision") recovered +12.51 FN against the quantised version and stood +4.64 above the float one [36, PR text]. Per-layer widths (int8 or int16): not published.
- Rounding care: doubling one quantisation scale ("l1 quant"): +2.25 FN (2025-01); "improve net quantisation precision": +3.72 FN, +3.26 ± 2.22 STC (2026-06) [36, PR text]. QAT: not published.

### Inference speed
- Accumulator refresh cache: "cache previous similar accumulator states": about 1%, "scales with more buckets" and a wider layer (2024-01). Fused refresh-table updates: +2.76 ± 2.07 at 3+0.03 [36, PR text].
- Lazy updates: +3.38 ± 2.33 STC (2024-06) [36, PR text].
- Fused updates: batching accumulator updates after make-move and skipping an unneeded accumulator copy: 4% faster. Fused add/sub threat updates: +2.20 ± 1.73 at 4+0.04 [36, PR text].
- Accumulator stack: the copy avoidance above; nothing more published.
- Pairwise multiplication: supported since 2024-08; no separate figure [36, PR text].
- int8 layers: not published per layer.
- Sparse first dense layer: computing the product in sparse blocks: +13.73 ± 5.32 STC on x86 and about 6% faster on NEON. An AVX-512 routine for finding the non-zero blocks (a Stockfish technique): +10.94 ± 4.46 STC [36, PR text]. An L1-norm penalty on the accumulator outputs: −2.22 FN, +3.21 ± 2.30 STC, +1.87 ± 2.52 LTC [36, PR text].
- Evaluation cache: not published.
- SIMD and VNNI work: fast incremental threat updates: +10.22 ± 4.46 at 4+0.04 on AVX-512 but only +2.23 ± 2.41 on AVX2 [36, PR text]. The AVX-512 build needs VNNI and VBMI2 and is called "significantly faster" than the AVX2 build [33, release notes]. A VNNI build was worth about 0.5% on Zen 4 in 2024 [36, PR text]. NEON: 177% faster on an M1; NEON dot-product: about 33% faster on an M4 Pro [36, PR text]. Hand-written SIMD against compiler vectorisation: 7% faster with clang, 153% with gcc [36, PR text]. PGO was switched off by default after testing at −0.41 ± 1.70 [36, PR text].
- Memory layout and prefetching: prefetch before make-move and the accumulator update: about 5% [36, PR text]. A "verbatim" net (the file grew from 34.4 to 53.1 MB, so apparently stored uncompressed) shared across NUMA nodes: 5% to 10% faster bench on 14 threads [36, PR text] [34, release notes]. The release notes list "better performance when running multiple instances at once" [33, release notes]. Net file: 55.9 MB for the rated net; 19.2 MB for 7.0.0's [34, release notes].
- Speed cost or gain for an architecture change: threat inputs with the accumulator cut to 640 and the first dense layer doubled to 32: +33.51 ± 9.35 FN, +2.73 ± 2.07 STC, +9.85 ± 4.24 LTC, +13.03 ± 4.94 at 20+0.2 on 4 threads [36, PR text]. First dense layer 16 → 32 alone: +10.30 FN, −1.42 STC, +0.44 LTC ("shows scaling behaviour") [36, PR text]. No nps ratio is published.
- Hardware sensitivity: the AVX-512 versus AVX2 gap above.

### Training data
- Size: not published.
- Type: own self-play only, from random weights; "will never use data generated by a third party" [32, README]. In 2026-04 a full dataset was generated at 24k soft nodes with draw scaling off; the older tier is 5k-node data, later regenerated without draw scaling too [36, PR text].
- Openings, filtering, tablebase use: the first nets used DFRC self-play only; standard-chess data was added in 3.0 [33, release notes]. A datagen bug was fixed and the whole dataset regenerated for 6.0.0 [33, release notes]. Filtering: random position skipping and skipping early plies (−0.85 STC, +3.03 ± 2.11 LTC); later only positions whose move is a capture passing a static-exchange test are filtered [36, PR text]. Tablebase use: not published.

### Training recipe (concepts only)
- Trainer: bullet; marlinflow for the earliest nets [32, README].
- Loss and target: a result weight that ramps up; details not described beyond the schedule notes [36, PR text].
- Stages and schedule: a pre-train step at a low result weight, a long main stage with a ramping result weight, then a short low-rate fine-tune at a high result weight (+5.61 FN, +10.63 STC, +12.77 ± 4.86 LTC when first added) [36, PR text]. With the 24k-node data: stage one on the old data, stage two on the new data with a pure result target: +24.86 FN, +24.93 STC, +24.71 ± 6.92 LTC, +16.91 at 60+0.6 on 8 threads [36, PR text].
- Regularisation, optimiser: Ranger, "no other adjustments": +5.79 FN, +7.30 STC, +5.52 ± 3.10 LTC [36, PR text]. L1-norm penalty as above.

### Measured gains for network changes
- Multilayer `(704x16hm->1792)x2->(16->32->1)x8` (2025-06): +41.04 FN, +8.15 ± 5.10 STC, +22.69 ± 6.51 LTC [36, PR text].
- Dual activation: +12.05 LTC. Ranger: +5.52 LTC [36, PR text].
- Threat inputs: +33.51 FN, +2.73 STC, +9.85 LTC [36, PR text].
- Replacing the whole dataset with 24k-node data, same recipe: −49.23 ± 12.71 FN, −28.35 ± 9.02 STC, −7.42 ± 4.69 LTC, but +13.56 ± 4.80 at 60+0.6 on 8 threads; the author had "never seen scaling this extreme" [36, PR text].
- 700 M more positions: +3.17 FN, +2.10 STC, +1.10 LTC [36, PR text].
- First net on the regenerated dataset (6.0.0): +47.53 ± 10.30 STC [36, PR text].
- 8.0.0 over 7.0.0: +62.44 (8+0.08), +81.93 (60+0.6), +94.51 (8 threads, 60+0.6) [33, release notes].

### Architecture history
- 1.0 (2023-07): first NNUE, trained from random weights through five earlier nets on DFRC self-play [33, release notes]; 384 hidden neurons [36, PR text].
- 3.0: first bucketed net. 2023-11: squared clipped ReLU, output buckets [36, PR text] [33, release notes].
- 2024: 8 buckets and 1024; mirrored 1536; 16 buckets and 1280; pairwise; back to 1536 (+12.26 FN, +3.57 LTC) [36, PR text].
- 2025-06 (7.0.0): multilayer, 1792 wide, dual activation, sparse blocks [36, PR text] [33, release notes].
- 2026-02: threat inputs, 640 wide, first dense layer 32, split accumulators [36, PR text].
- 2026-05: skip connection. 2026-06: pawn-pawn inputs, finer quantisation. 2026-06-27: 8.0.0 [36, PR text] [33, release notes].

### Since the rated version
- 2026-07: a longer training run with the 24k-node data also in stage one: +39.62 ± 9.81 FN, −15.28 ± 6.92 STC, +3.20 ± 2.17 at 20+0.2 on 8 threads [36, PR text].
- 2026-08: stage-one data included in stage two: +24.23 FN, +22.62 STC, +10.25 ± 4.29 LTC [36, PR text].
- The development nets grew from 55.9 MB to 89.4 MB [34, release notes]; what changed is not described.

### UNVERIFIED and not published
- That the accumulator is still 640 wide in 8.0.0: assembled from PR text. No PR between the threat-input merge and the release changes it, but the release does not state the architecture.
- Number of pawn-pawn inputs; king bucket layout; output bucket selector: not published.
- Integer type of each layer: not published.
- Data size; openings; tablebase use in datagen: not published.
- Whether a factoriser is used: not published.
- Architecture of the 89 MB development nets: not published.

---

## Hobbes 3.0 (CCRL #18, 3742)

**One-line architecture:** `((768x16+60144)hm->768)x2->(16x2->32->1)x8`. As the engine writes it [37, README]; the network log gives the same string for the net published the day before 3.0 [41, prose log] [39, release notes].

### Inputs
- Feature set: 768 piece-square inputs per king bucket plus 60,144 threat inputs [37, README] [41, prose log]. King planes are merged in the stored net (a post-processing step; non-regression −0.49 ± 1.23) [42, PR text].
- King input buckets: 16. Layout, from the grid in the network log (8 rows of 4 files, the mirrored half board; first row taken to be the king's own back rank): rows 1 and 2 have one bucket per file (8 buckets); rows 3-4 have one bucket per file shared by the two ranks (4); rows 5-6 have two buckets, each covering two files (2); rows 7-8 the same (2) [41, prose log]. Growth with data [41, prose log]:
  - mirrored, no buckets, at 0.31 B positions;
  - 4 buckets at 1.7 B (back rank split in two, second rank, the rest): +25.96 ± 9.12 STC (with the extra data);
  - 6 buckets at 2.1 B: +6.93 ± 4.45 STC;
  - 8 buckets at 5 B: +2.15 ± 1.86 LTC;
  - 10 buckets at 7 B: +4.69 ± 3.46 STC (with the extra data);
  - 16 buckets at 17 B: +3.71 ± 2.81 LTC (with a higher result weight in the fine-tune stage).
- Horizontal mirroring: yes: +37.48 ± 11.32 STC when added at 0.31 B positions [41, prose log] [42, PR text].
- Threat or attack inputs: yes, since 2026-07-20. The author says the implementation follows Reckless, Viridithas and Stormphrax and adds nothing original [38, release notes] [42, PR text]. Updates, all at 4+0.04: incremental threat updates +6.79 ± 3.94; lazy threat updates +18.30 ± 6.75; SIMD and other speedups +5.36 ± 3.44 [42, PR text].
- Pawn features: none in 3.0 (see "Since the rated version").
- Other input relationships: none published.
- Factoriser: not published.

### Body
- First hidden layer (accumulator) width per perspective: 768 [37, README]. Raised from 512 two days after threat inputs went in: +25.31 ± 8.45 at 20k nodes, +10.11 ± 4.87 LTC [42, PR text].
- Further layers: 16 (doubled by the dual activation), 32, 1 [37, README].
- Layer stacks: 8 [37, README].
- Output buckets: 8 [37, README]. Selector: not published.
- Skip connections, pairwise multiplication, other structure: pairwise in the non-threat multilayer nets ("pw" in their strings) [41, prose log]. For the threat-input nets see UNVERIFIED.

### Activations
- After the accumulator: clipped ReLU with pairwise product in the 2026-03 to 2026-07 nets [41, prose log].
- In the head: dual activation on the first dense layer (clipped ReLU plus clipped squared ReLU), then clipped ReLU, then clipped ReLU [41, prose log]. Dual activation: +9.51 ± 4.82 STC, +16.46 ± 6.39 LTC [42, PR text].

### Quantisation
- Integer types per layer: not published. The log lists two quantisation scales for every net, one for the feature transformer and one for the next layer [41, prose log].
- QAT or other rounding care: not published.

### Inference speed
- Accumulator refresh cache: "Finny tables": +13.60 ± 7.54 at 5+0.05. Fused refreshes: −0.30 ± 2.01 at 4+0.04 (kept as non-regression) [42, PR text].
- Lazy updates: +19.32 ± 7.54 at 4+0.04 (2025-11); lazy threat updates: +18.30 ± 6.75 at 4+0.04 [42, PR text].
- Fused updates: +5.84 ± 6.57 STC (2025-07) [42, PR text].
- Accumulator stack: refactored twice; no figure [42, PR text].
- Pairwise multiplication: arrived with the multilayer net; no separate figure [41, prose log].
- int8 layers: not published.
- Sparse first dense layer: sparse matrix multiplication: +11.68 ± 5.76 at 4+0.04. Re-permuting the net for sparsity: bench 1.02 times faster, +3.80 ± 3.60 at 4+0.04 [42, PR text].
- Evaluation cache: not published.
- SIMD work: AVX2 support: +14.34 ± 7.92 STC; AVX-512 support: +16.65 ± 8.34 at 5+0.05. A NEON pack tweak measured no change [42, PR text].
- Memory layout and prefetching: merged king planes [42, PR text]. Net file: 65.2 MB for the rated net; 43.5 MB at 512 wide; 34.8 MB for the last net without threats [39, release notes].
- Speed cost or gain for an architecture change:
  - threat inputs (the accumulator went 1536 → 512): +35.77 ± 8.85 at 20k nodes, +23.66 ± 7.67 at 40+0.4 [42, PR text];
  - accumulator 1280 → 1792 without threats: +27.71 ± 9.32 at 20k nodes, +3.02 ± 2.31 LTC, then reverted six days later; the revert lists 6.44 ± 4.97 at 40+0.4 and −0.86 ± 3.29 at 80+0.8 without saying which side is which [42, PR text];
  - 1280 → 1536 a month later: +18.10 FN, +4.37 ± 2.96 LTC [42, PR text].
  - No nps ratios are published.
- Hardware sensitivity: not published.

### Training data
- Size: 37.5 B positions in the main stage for the rated net: 30 B standard and 7.5 B DFRC [41, prose log]; the README calls it roughly an 80/20 split [37, README].
- Type: own self-play, built up from a randomly initialised net over 46 iterations [37, README] [41, prose log]. Label budgets: most data at 5k soft nodes; 2 B at 20k soft nodes; 12.5 B at 12k soft nodes (7.5 B standard, 5 B DFRC) [41, prose log] [42, PR text]. Before 2025-09 the engine used Calvin's net, trained on Lc0 data rescored by Calvin's 5k soft-node search [42, PR text]; the own net equalled it at 7 B positions (+3.70 ± 7.18) [41, prose log].
- Openings, filtering, tablebase use: random position skipping in the loader (+8.90 ± 5.18 STC when introduced) [42, PR text] [41, prose log]. DFRC data: +158.84 in DFRC and +6.21 ± 4.05 in standard chess [42, PR text]. Openings and tablebase use: not published.

### Training recipe (concepts only)
- Trainer: bullet [37, README].
- Loss and target: a result weight that starts low, ramps up through the main stage and is high in the fine-tune stage [41, prose log].
- Stages and schedule: a main stage on all data with a cosine learning rate, then a short fine-tune at a very low constant rate on the most recent data only [41, prose log]. Adding the fine-tune stage: +1.71 STC; restricting it to recent data: +6.65 ± 4.07 STC; restricting it to the newest 10 B positions at 12k soft nodes with a higher result weight: +8.86 ± 4.57 LTC [42, PR text] [41, prose log].
- Regularisation, optimiser: AdamW throughout [41, prose log].

### Measured gains for network changes
- Data steps (STC): 0.9 B with 512 wide +67.38; 1 B with 768 wide +25.75; 1.2 B with 1024 wide +13.00; 3.3 B +15.65; 4.2 B +12.54; 5 B +4.97; 12.5 B +8.82 [41, prose log].
- 2 B positions at 20k soft nodes: −0.89 ± 2.70 STC, +2.64 ± 2.09 LTC. 10 B at 12k soft nodes: +3.12 STC, +6.18 ± 3.69 LTC [42, PR text].
- Multilayer head `(768x16hm->1280pw)x2->(16->32->1)x8`: +42.56 ± 11.55 at 20k nodes, +9.03 STC, +24.31 ± 7.75 LTC [41, prose log]. The whole multilayer branch at merge: +72.59 FN, +20.33 ± 7.11 LTC [42, PR text].
- Dual activation: +16.46 LTC [42, PR text].
- Threat inputs: +35.77 FN, +23.66 LTC; wider to 768: +10.11 LTC [42, PR text].
- 3.0 over 2.1: +49.96 ± 6.02 at 60+0.6 [38, release notes].

### Architecture history
- 2025-07 to 2025-09: `(768->32)x2->1` up to `(768hm->1024)x2->1`, all SCReLU, data 33 M → 1.2 B [41, prose log].
- 2025-08 to 2025-10: 4, 6, 8, 10 and 16 buckets; 1280 wide [41, prose log].
- 2026-03: multilayer with pairwise and dual activation (released in 2.0, 2026-05) [38, release notes] [41, prose log].
- 2026-04/05: 1536 wide, sparse multiplication, permutation, merged king planes [38, release notes].
- 2026-07-20/22 (3.0): threat inputs at 512, then 768 [38, release notes].

### Since the rated version
- 2026-08-31: pawn-pair inputs, `((768x16+59808ti+4560pp)hm->768)x2->(16x2->32->1)x8`, with a new three-stage schedule and 40 B positions: +21.06 ± 6.65 FN, +11.73 ± 4.68 STC, +16.61 ± 6.26 LTC [41, prose log].
- 2026-09-01: accumulator 1024: +25.98 ± 7.93 FN, +3.57 ± 2.34 LTC; net file 91.2 MB [41, prose log] [39, release notes].
- 2026-11-13: Hobbes 4.0, +42.54 ± 6.07 at 40+0.4 over 3.0 [38, release notes].

### UNVERIFIED and not published
- Whether the threat-input nets still use the pairwise product: the strings for those nets drop the "pw" mark and no page says either way.
- Which row of the bucket grid is rank 1: not stated (assumed the first).
- Integer types per layer; QAT: not published.
- Output bucket selector: not published.
- What the 60,144 threat inputs encode: not described by Hobbes itself (the count equals Viridithas's and Stormphrax's).
- Openings and tablebase use in datagen; evaluation cache; factoriser: not published.

---

## Horsie 1.1.0 (CCRL #19, 3735)

**One-line architecture:** `(768x14 -> 2048)x2 -> (16 -> 32 -> 1)x8`. Assembled: Horsie's own pages give no architecture string. This is the string Lizard's README gives for 11.2 [46, README] and the net repository gives for the net Horsie adopted in 2024-12 [48, release notes] [45, PR text]. See UNVERIFIED.

**What Horsie and Lizard share:** Horsie is an "(almost) functionally identical" C++ port of Lizard (C#) by the same author. Search, network and data are common; at fixed nodes every one of 5,155 opening pairs between them came out level. Most testing is done on Horsie because it is faster, and Lizard is brought up to date from it in batches [43, README] [50, PR text]. Lizard 11.2 can load Horsie's C++ evaluation code as a native library [47, release notes].

### Inputs
- Feature set: 768 piece-square inputs per king bucket [46, README].
- King input buckets: 14 [46, README] [48, release notes]. Layout: not published. (History under Lizard.)
- Horizontal mirroring: not stated for this net (see UNVERIFIED).
- Threat or attack inputs: none published. Pawn features: none published.
- Other input relationships: none published.
- Factoriser: yes, "pre-merged" into the published net [48, release notes].

### Body
- Accumulator width per perspective: 2048 [46, README].
- Further layers: 16, 32, 1 [46, README].
- Layer stacks: 8 [46, README].
- Output buckets: 8, by material count [48, release notes].
- Other structure: pairwise multiplication [48, release notes].

### Activations
- After the accumulator: pairwise clipped ReLU [48, release notes] [50, PR text].
- In the head: not published.

### Quantisation
- Integer types per layer: first dense layer weights are int8 [45, PR text]. Other layers: not published.
- Rounding care: "utilitarian quantisation": the first dense layer's weights are stored at twice the precision, accepting that a few saturate. In that net 81 weights saturate, about 262,000 gain precision and about 9,400 stop rounding to zero: +12.09 ± 4.56 at 25k nodes, +7.65 ± 3.71 STC [45, PR text].

### Inference speed
- Accumulator refresh cache: inherited from Lizard (Finny tables); no Horsie figure.
- Lazy updates: inherited from Lizard; no Horsie figure.
- Fused updates: not published.
- Accumulator stack: accumulators were moved out of the board state into a separate list, so a null move needs no special case and a state can be copied whole: neutral (−0.00 ± 2.00 STC) after a bug fix had cost 12.74 [45, PR text].
- Pairwise multiplication: inherited ("a speedup at the (potential) cost of some accuracy") [50, PR text].
- int8 layers: first dense layer, as above.
- Sparse first dense layer: a "pre-permuted" net was adopted with NEON support in 2025-11 (after 1.1) [45, PR text]. Sparse iteration itself: not published.
- Evaluation cache: not published.
- SIMD work: builds for AVX-512, AVX2 and older CPUs [44, release notes].
- Memory layout: net file about 21.2 MB compressed [48, release notes].
- Anything else: clang with LTO and PGO instead of gcc with LTO: +11.39 ± 4.52 STC [45, PR text]. The language port itself: +26.27 ± 6.95 at 8+0.08 over Lizard with identical search [43, README]; +30.53 ± 7.87 for Horsie 1.0 over Lizard 11.2 [44, release notes].
- Speed cost or gain for an architecture change: multilayer head: +5.12 ± 2.96 STC, +13.72 ± 4.99 LTC [45, PR text]. Wider accumulator with a narrower first dense layer (1536/32 → 2048/16): +8.60 ± 3.97 STC, +4.14 ± 2.42 LTC, "does well in DFRC" [45, PR text].
- Hardware sensitivity: not published.

### Training data
- Size: about 6.6 B positions (Lizard's figure for the shared net) [46, README].
- Type: **mixed** lineage, same as Lizard: self-play data that began with about 200 M positions generated by Lizard's 10.5 net, which was trained on Lc0 data [47, release notes] [46, README]. Horsie's own datagen was ported in 2025-02 [45, PR text].
- Openings, filtering, tablebase use: not published for Horsie.

### Training recipe (concepts only)
- Trainer: bullet [46, README].
- Loss, stages, regularisation: not published.

### Measured gains for network changes
- Multilayer head: +13.72 LTC [45, PR text].
- 2048/16 net: +8.60 STC, +4.14 LTC [45, PR text].
- Utilitarian quantisation: +7.65 STC [45, PR text].
- 1.1 over 1.0 (search and build changes, same net): +32.41 ± 6.27 STC, +29.37 ± 5.95 LTC [44, release notes].

### Architecture history
- 2024-12-10: multilayer. 2024-12-25: 2048 wide with a 16-wide first dense layer. 2025-01-01: utilitarian quantisation. 2025-01-08: 1.0. 2025-05-12: 1.1 [45, PR text] [44, release notes].

### Since the rated version
- 2025-11: NEON support and a pre-permuted net [45, PR text].
- 2026-06: an undescribed "net-017" appeared in the net repository (12.1 MB) [48, release notes].

### UNVERIFIED and not published
- That 1.1 ships exactly the 2048/16 net: inferred (no network PR between 2025-01 and the 1.1 release); Horsie's pages do not name the net.
- King bucket layout for 14 buckets; whether this net is mirrored: not published.
- Head activations; integer types beyond the first dense layer: not published.
- Label budget of the self-play data; openings; tablebase use: not published.
- Loss, schedule and regularisation: not published.
- Refresh-cache, lazy-update and sparse-layer figures measured in Horsie itself: not published.

---

## Lizard 11.2 (CCRL #20, 3732)

**One-line architecture:** `(768x14 -> 2048)x2 -> (16 -> 32 -> 1)x8`, as the engine writes it [46, README].

### Inputs
- Feature set: 768 piece-square inputs per king bucket [46, README].
- King input buckets: 14 in 11.2 [46, README]. Layout: not published. Growth: 4 (2024-04, on Lc0 data) → 5 (10.4) → back to 1 mirrored for the first self-play net (2024-08) → 4 (2024-09) → 8 with a factoriser (2024-10) → 16 (11.1) → 14 (11.2) [50, PR text] [46, README] [48, release notes].
- Horizontal mirroring: the first self-play net was "horizontally mirrored" [50, PR text]. For the bucketed nets: not stated.
- Threat or attack inputs: none published. Pawn features: none.
- Other input relationships: none published.
- Factoriser: yes, since the 8-bucket net; merged before publishing [48, release notes]. With 8 buckets it was worth +82.28 ± 15.07 in DFRC and +14.66 ± 4.73 at 25k nodes in standard chess [50, PR text].

### Body
- Accumulator width per perspective: 2048 [46, README].
- Further layers: 16, 32, 1 [46, README].
- Layer stacks: 8 [46, README].
- Output buckets: 8, by material count [48, release notes].
- Other structure: pairwise multiplication [48, release notes].

### Activations
- After the accumulator: pairwise clipped ReLU since 2024-10 [50, PR text].
- In the head: not published.

### Quantisation
- Integer types per layer: first dense layer weights int8 (shared with Horsie) [45, PR text]. The engine notes small floating-point differences after the quantisation change, so some arithmetic is float [50, PR text].
- Rounding care: utilitarian quantisation, as in Horsie [50, PR text]. An earlier scheme by the same author for squared clipped ReLU (multiply by the weight after clipping and before squaring, so the products stay in 16 bits at full precision) was picked up by other engines [16, blog].

### Inference speed
- Accumulator refresh cache: Finny tables arrived with the first bucketed net; the two were tested together: −6.25 ± 7.59 STC, +13.85 ± 8.88 at 40+0.4, with the buckets costing about 13% speed [50, PR text].
- Lazy updates: +29.84 ± 7.81 at 4+0.04, +27.52 ± 7.03 at 8+0.08; modelled on Stormphrax's [50, PR text].
- Fused updates: not published.
- Accumulator stack: updating the child accumulator directly from the parent instead of copying first: about 11% faster, +23.35 ± 9.06 at 4+0.04 [50, PR text].
- Pairwise multiplication: +1.64 ± 1.79 STC in standard chess, +43.84 ± 10.74 at 40+0.4 in DFRC [50, PR text].
- int8 layers: as above.
- Sparse first dense layer: not published for 11.2.
- Evaluation cache: not published.
- SIMD work: AVX-512 path (2024-04); manual loop unrolling because the runtime does not unroll [50, PR text]. Native C++ evaluation code from Horsie loaded as a library when AVX2 is present: +24.86 ± 6.77 STC [50, PR text] [47, release notes].
- Memory layout: zstd-compressed nets, about 45% smaller files [50, PR text]; 21.2 MB compressed for 11.2's net [48, release notes]. Huge pages for the transposition table [50, PR text].
- Anything else: JIT compilation instead of ahead-of-time: +16.24 ± 5.63 at 4+0.04 [50, PR text].
- Speed cost or gain for an architecture change: king buckets about 13% slower (above). The multilayer head "almost certainly loses at STC" in C# because of the slowdown; the C++ port stood +20.43 ± 8.07 at 4+0.04 above it [50, PR text].
- Hardware sensitivity: needs AVX2 "to be performant" [47, release notes].

### Training data
- Size: about 6.6 B positions for 11.2; about 4.5 B for 11.1 [46, README].
- Type: **mixed** lineage. Through 10.5 the nets were trained on Lc0 data (about 8 B positions; one 2024-04 net names 2 B and 3 B positions from two months of Lc0 "T80" training data) [46, README] [50, PR text]. From 11.0 on, self-play data only: the 10.5 net generated about 200 M positions, and each later net was trained on the growing set and generated more [47, release notes]. The switch cost −33.04 ± 6.83 at 8+0.08 and −36.45 ± 9.13 at 40+0.4 in standard chess and gained +112.14 in DFRC [50, PR text].
- Openings, filtering, tablebase use: about 750 M positions were removed in 2024-09 for wrong scores and node-limit problems [50, PR text]. DFRC positions are part of the set (about 10% already in 10.5) [47, release notes]. Label budget, openings, tablebases: not published.

### Training recipe (concepts only)
- Trainer: bullet [46, README].
- Loss and target: not published for the self-play nets.
- Stages and schedule: retraining from a late checkpoint with new data and cosine annealing is mentioned once [50, PR text].
- Regularisation, optimiser: not published.

### Measured gains for network changes
- 16 input buckets: +14.89 ± 5.40 STC [50, PR text].
- 8 buckets with a factoriser: +82.28 DFRC, +14.66 FN standard [50, PR text].
- Hidden layer 1536 → 2048 (with extra DFRC positions): +71.23 ± 13.22 at 40+0.4 [50, PR text].
- 4 buckets after the data clean-up: +14.71 STC, −65.23 DFRC [50, PR text].
- 5 buckets with 8 material output buckets: +7.78 ± 3.95 STC [50, PR text].
- 0.8 B DFRC positions added: +2.23 standard, +26.55 DFRC [50, PR text].
- 11.2 over 11.1: +15.02 ± 5.26 STC, +18.55 ± 5.35 at 60+0.6 [47, release notes].

### Architecture history
- 9.3: "its own NNUE evaluation"; 10.0 (2024-01): "first non-Stockfish NNUE" (both as the README words it) [46, README].
- 2024-04/05: `(768x4 -> 1024)x2 -> 8`, then `(768x4 -> 1536)x2 -> 8` with Finny tables [50, PR text].
- 10.5 (2024-07): `(768x5 -> 1536)x2 -> 8`, Lc0 data [46, README].
- 11.0 (2024-09): self-play data, `(768 -> 1536)x2 -> 8` mirrored, then 4 buckets [50, PR text].
- 11.1 (2024-11): `(768x16 -> 2048)x2 -> 8`, pairwise, factoriser [46, README] [48, release notes].
- 2024-12: `(768x14 -> 1536)x2 -> (32 -> 32 -> 1)x8`, then `(768x14 -> 2048)x2 -> (16 -> 32 -> 1)x8` [48, release notes].
- 11.2 (2025-01-08) [47, release notes].

### Since the rated version
- A `(704x32 -> 2048)x2 -> (16 -> 32 -> 1)x8` mirrored net was published in the net repository in 2025-01; no page says it was adopted [48, release notes].
- 2025-03 to 2026-01: search patches merged over from Horsie [50, PR text].

### UNVERIFIED and not published
- King bucket layout; whether the bucketed nets are mirrored: not published.
- Head activations; integer types beyond the first dense layer: not published.
- Label budget, openings and tablebase use of the self-play data: not published.
- Loss, schedule, optimiser of the self-play nets: not published.
- Sparse first dense layer and evaluation cache in 11.2: not published.

---

## Cross-engine notes for Fork

1. **The shape of the result is the same everywhere.** Larger nets win at fixed nodes, are level or negative at 8+0.08, and win at 40+0.4 or longer; all six authors merged on the long test. Examples: Stormphrax's mirrored 1536 net (+35.0 FN, −4.8 STC, +4.9 LTC); Lizard's first buckets (−6.3 STC, +13.9 LTC); Viridithas's 2048/16-bucket net (+31.6 FN, +0.5 STC, +4.8 LTC); Stormphrax's 24k-node data (−28 STC, −7 LTC, +13.6 at 60+0.6 on 8 threads). Counter-examples where width alone stopped paying at very long control: Viridithas 2560 (−0.2 at 80+0.8); Hobbes 1792 (reverted).
2. **Threat inputs were never added to a wide single-layer net.** Viridithas, Stormphrax and Hobbes each cut the accumulator sharply when adding them (2560 → 1024, 1792 → 640, 1536 → 512 then 768) and widened the first dense layer to 32, on top of a multilayer head with sparse int8 inference. Reported cost: 87% of the previous speed on AVX-512 (Viridithas). Stormphrax's split of piece-square and threat accumulators was worth +9.0 STC, and its fast incremental threat updates gained +10.2 on AVX-512 but only +2.2 on AVX2.
3. **A result-heavy final stage needs the output scale recomputed.** Viridithas measured 28 Elo at 25k nodes between a pure-result net with and without rescaling, and −57 for a pure-result fine-tune that was not rescaled. With rescaling the same idea is positive in Viridithas (+9.3 LTC), Stormphrax (+24.7 LTC for the two-stage recipe on new data) and Hobbes (+8.9 LTC, fine-tune on the newest higher-node data only).
4. **The multilayer head is paid for by a fixed package**, each part with a figure above: pairwise product, int8 first dense layer, sparse non-zero-block iteration, neuron permutation, a sparsity penalty in training, lazy updates and a refresh cache. For the rounding loss Fork saw, the answers here are QAT on every layer (Caissa), float layers after the first dense one (Viridithas), finer scales with deliberate saturation (Horsie, +7.65 STC) and precision fixes (Stormphrax, +3.3 STC and +12.5 FN).

---

## Sources

All opened 2026-11-14.

| # | URL | What it is | Type | Used for |
|---|---|---|---|---|
| 1 | https://raw.githubusercontent.com/Witek902/Caissa/HEAD/README.md | Caissa README | README | Caissa |
| 2 | https://api.github.com/repos/Witek902/Caissa/releases | Caissa release notes, 0.2 to 2.0 | release notes | Caissa |
| 3 | https://api.github.com/repos/Witek902/Caissa-Nets/releases | Caissa net release notes and file sizes | release notes | Caissa |
| 4 | https://raw.githubusercontent.com/Witek902/Caissa-Nets/HEAD/README.md | Caissa-Nets README | README | Caissa |
| 5 | https://api.github.com/repos/Witek902/Caissa/commits (3 pages, 300 newest) | Caissa commit messages | commit text | Caissa |
| 6 | https://raw.githubusercontent.com/cosmobobak/viridithas/HEAD/README.md | Viridithas README | README | Viridithas |
| 7 | https://api.github.com/repos/cosmobobak/viridithas/releases | Viridithas release notes | release notes | Viridithas |
| 8 | https://api.github.com/repos/cosmobobak/viridithas-networks/releases | Viridithas net release notes and file sizes | release notes | Viridithas |
| 9 | https://raw.githubusercontent.com/cosmobobak/viridithas-networks/HEAD/README.md | viridithas-networks README | README | Viridithas (licence) |
| 10 | https://api.github.com/repos/cosmobobak/viridithas/pulls (5 pages, #2 to #481) | Viridithas PR titles and descriptions | PR text | Viridithas |
| 11 | https://raw.githubusercontent.com/cosmobobak/viridithas/HEAD/notes/networkhistory.txt | Viridithas network history, a prose table | prose log | Viridithas |
| 12 | https://github.com/cosmobobak/viridithas/tree/master/notes | Folder listing (names only) | other | finding 11 |
| 13 | https://cosmo.tardis.ac/ | Redirect notice to asteri.sm | other | finding 15 |
| 14 | https://cosmo.tardis.ac/2024/06/25/nnue-research-01/ | **Failed: 404** (moved; see 18) | blog | none |
| 15 | https://asteri.sm/ | Author's site index | blog | Viridithas |
| 16 | https://asteri.sm/files/2024-06-01-nnue.html | "NNUE performance improvements" | blog | Viridithas, Lizard |
| 17 | https://asteri.sm/files/2024-06-02-advanced-nnue.html | "The advanced NNUE program" | blog | Viridithas |
| 18 | https://asteri.sm/files/2024-06-25-nnue-research-01.html | "Experimenting with NNUE configurations" | blog | Viridithas |
| 19 | https://asteri.sm/files/2024-07-15-nnue-research-02.html | "More experimentation in NNUE" | blog | Viridithas |
| 20 | https://asteri.sm/files/2024-08-17-multilayer.html | "Deep NNUE" | blog | Viridithas |
| 21 | https://asteri.sm/files/2025-12-12-nnue-eval-scale.html | "Training dynamics of target weighting" | blog | Viridithas |
| 22 | https://asteri.sm/files/2026-01-13-activation | "Chess networks use a Gated Nonlinear Unit" | blog | Viridithas |
| 23 | https://asteri.sm/files/2026-01-27-activation-2 | "Better activation functions for NNUE" | blog | Viridithas |
| 24 | https://asteri.sm/files/2026-07-27-optimisers.html | "A few optimisers, and Schedule-Free NNUE" | blog | Viridithas |
| 25 | https://asteri.sm/pages/network-diagrams.html | "Network Diagrams" | blog | Viridithas |
| 26 | https://asteri.sm/pages/talks.html | Talks page | blog | finding 27 |
| 27 | https://asteri.sm/rustweek-2026/delivered.pdf | Slides, "Writing a Top-10 Chess Engine in Rust" | slides | Viridithas |
| 28 | https://asteri.sm/sitemap.html | Sitemap | blog | finding pages |
| 29 | https://asteri.sm/pages/external.html | Links page | blog | not used |
| 30 | https://asteri.sm/files/2026-02-12-az-rl-and-spsa.html | "AlphaZero, RL, and SPSA" | blog | fetched, not read, not used |
| 31 | https://asteri.sm/files/2026-06-11-mcts-policy.html | "MCTS & neural policies" | blog | fetched, not read, not used |
| 32 | https://raw.githubusercontent.com/Ciekce/Stormphrax/HEAD/README.md | Stormphrax README | README | Stormphrax |
| 33 | https://api.github.com/repos/Ciekce/Stormphrax/releases | Stormphrax release notes | release notes | Stormphrax |
| 34 | https://api.github.com/repos/Ciekce/stormphrax-nets/releases | Stormphrax net releases (names, dates, sizes) | release notes | Stormphrax |
| 35 | https://raw.githubusercontent.com/Ciekce/stormphrax-nets/HEAD/README.md | stormphrax-nets README (one line) | README | none |
| 36 | https://api.github.com/repos/Ciekce/Stormphrax/pulls (4 pages, #2 to #349) | Stormphrax PR titles and descriptions | PR text | Stormphrax |
| 37 | https://raw.githubusercontent.com/kelseyde/hobbes-chess-engine/HEAD/README.md | Hobbes README | README | Hobbes |
| 38 | https://api.github.com/repos/kelseyde/hobbes-chess-engine/releases | Hobbes release notes | release notes | Hobbes |
| 39 | https://api.github.com/repos/kelseyde/hobbes-networks/releases | Hobbes net releases (names, dates, sizes; bodies empty) | release notes | Hobbes |
| 40 | https://raw.githubusercontent.com/kelseyde/hobbes-networks/HEAD/README.md | hobbes-networks README | README | none |
| 41 | https://raw.githubusercontent.com/kelseyde/hobbes-chess-engine/HEAD/network_history.txt | Hobbes network history, a prose table | prose log | Hobbes |
| 42 | https://api.github.com/repos/kelseyde/hobbes-chess-engine/pulls (6 pages, 423 PRs) | Hobbes PR titles and descriptions | PR text | Hobbes |
| 43 | https://raw.githubusercontent.com/liamt19/Horsie/HEAD/README.md | Horsie README | README | Horsie, Lizard |
| 44 | https://api.github.com/repos/liamt19/Horsie/releases | Horsie release notes | release notes | Horsie |
| 45 | https://api.github.com/repos/liamt19/Horsie/pulls (#1 to #39) | Horsie PR titles and descriptions | PR text | Horsie, Lizard |
| 46 | https://raw.githubusercontent.com/liamt19/Lizard/HEAD/README.md | Lizard README | README | Lizard, Horsie |
| 47 | https://api.github.com/repos/liamt19/Lizard/releases | Lizard release notes | release notes | Lizard, Horsie |
| 48 | https://api.github.com/repos/liamt19/lizard-nets/releases | Lizard net release notes and sizes | release notes | Lizard, Horsie |
| 49 | https://raw.githubusercontent.com/liamt19/lizard-nets/HEAD/README.md | lizard-nets README (title only) | README | none |
| 50 | https://api.github.com/repos/liamt19/Lizard/pulls (2 pages, #1 to #126) | Lizard PR titles and descriptions | PR text | Lizard, Horsie |
| 51 | https://www.chessprogramming.org/Caissa, /Viridithas, /Stormphrax, /Hobbes, /Horsie, /Lizard | **Failed: 404 on all six** (no such pages) | CPW | none |
| 52 | https://www.chessprogramming.org/NNUE | Fetched only to confirm the wiki was reachable; not read | CPW | none |
| 53 | https://www.chessprogramming.org/index.php?search=Caissa+Witanowski&title=Special%3ASearch | **Failed: 404** | CPW | none |
| 54 | https://api.github.com/rate_limit | Quota check (twice) | other | none |

Local, read-only: the earlier survey's `engines.md`, `sources.md`, `comparison.md` (sections H to K) and `provenance.md`, cited as [prior survey].

GitHub API use: 34 calls in total (11 release lists, 18 pull-request pages, 3 commit pages, 2 quota checks), all prose endpoints. Quota remaining at the second check: 4,708.

Not reached or not opened: Discord; Kaggle dataset pages (script-rendered); the OpenBench test pages behind the results (results were taken from the PR and release text that quotes them); TCEC and CCRL pages.

Credit lines:

- Caissa: Michał Witanowski (Witek902). MIT; network files MIT [1] [4].
- Viridithas: Cosmo (cosmobobak). AGPL-3.0-only on master, MIT up to and including 20.0.0; networks CC0 1.0 [6] [9].
- Stormphrax: Ciekce. Licence not stated in the text of the pages opened (README shows a badge only).
- Hobbes: Dan Kelsey (kelseyde). README shows a badge only; MIT, nets without a licence [prior survey].
- Horsie and Lizard: liamt19. Not stated on the pages opened; Horsie GPL-3.0, Lizard MIT [prior survey].
- bullet (trainer used by Viridithas, Stormphrax, Hobbes, Horsie, Lizard): jw1912; named on the READMEs, not opened.

---

## Clean-room statement

- I opened no engine or trainer source file, no diff, no "Files changed" tab, no blame view, no code search result and no network file. I cloned and downloaded no repository, release archive, binary or network file. The only files fetched were prose pages, API responses holding release, pull-request and commit text, two prose logs and one slide deck (PDF).
- Things that came close:
  - One Viridithas network release note (source 8) embeds a code fragment holding the 16-bucket king layout. It arrived inside the release text. I did not use or transcribe it; the layout is marked UNVERIFIED.
  - The author's blog articles (16 to 25) embed code blocks. A script stripped them before I read the text, so I read none. Result tables in the same kind of block were stripped with them; the same figures were taken from PR and release text.
  - The slide deck (27) contains code slides. I read a text extraction with code-like lines filtered out. A few short fragments (type and field names from the board and hash-table slides, nothing from the network) got through and were not used.
  - Caissa commit messages (5) and one Caissa net note (3) describe inference at instruction level and quote trainer command lines. A Lizard PR (50) and Stormphrax and Hobbes pages (36, 41) quote training settings. I recorded concepts, layer widths, integer types and results only: no scale factors, clipping bounds, learning rates, blend weights or identifiers.
  - The Hobbes log (41) names one source file path in a note, and a Viridithas PR (10) links to a trainer source file. Neither was opened or recorded.
  - Directory listing 12 shows two file names in a notes folder; nothing else was listed.
- Files I created, all inside the agent's scratch folder: the fetched pages and API dumps (`readme_*`, `releases_*`, `prs_*`, `commits_*`, `page_*`, `text_*`, `viri_networkhistory.txt`, `hobbes_network_history.txt`, `hobbes_nh_compact.txt`, `tmp_probe.txt`, `tmp_probe2.txt`), `pdf\rustweek-2026-delivered.pdf` and its `.txt`, and two helper scripts in `tools\`. `report.md` was not created (the Write tool blocked it).
- I deleted nothing, wrote nothing outside the folder, edited nothing in the repository and committed nothing.
