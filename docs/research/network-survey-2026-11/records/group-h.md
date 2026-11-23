# Network records, group H: Fritz, Ginkgo, Revenge, Lc0, Chess System Tal, Stoofvlees, Rebel, rofChade

Clean-room network survey of 2026-11-14 ([README](../README.md)). Written by survey agent H from public prose only and assembled unchanged except for local paths and one restricted item (the Stoofvlees record says which). Source numbers in brackets refer to the Sources table at the end of this file. Every engine here is REFERENCE ONLY for ideas; its code, nets and data are OFF-LIMITS for Fork.


Survey date 2026-11-14. Every fact below comes from a page opened today; the number in brackets is the row in "Sources" and the word after it is the source type. "[prior survey]" marks facts carried from `docs/research/engine-survey-2026-11/` without re-opening. Ranks and ratings are from the CCRL Blitz engine-detail pages of 2026-11-14 [1-8, CCRL].

Six of these eight engines are closed. "Not published" means: not stated on any page I could open today.

---

## Fritz 20 (CCRL #29, 3721)

**One-line architecture:** not published. The vendor says only that the engine has "neural network evaluation" [24, vendor] [25, vendor]. Assembled context: the engine is Frank Schneider's, and Ginkgo "is currently also the engine used in Chessbase's Fritz products" [19, TCEC]; its NNUE line began with Fritz 18 Neuronal in March 2022 [26, vendor] [9, CPW].

### Inputs
- Feature set (what an input means; inputs per perspective if stated): not published.
- King input buckets: count; layout; how the layout was chosen or grown: not published.
- Horizontal mirroring: not published.
- Threat or attack inputs: not published.
- Pawn features: not published.
- Other input relationships: not published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: not published.
- Further layers: count and widths: not published.
- Layer stacks: not published.
- Output buckets: not published.
- Skip connections, pairwise multiplication, other structure: not published.

### Activations
- After the accumulator: not published.
- In the head: not published.

### Quantisation
- Integer types per layer: not published.
- Quantisation-aware training or other rounding care: not published.

### Inference speed
- Accumulator refresh cache: not published.
- Lazy or deferred accumulator updates: not published for Fritz 20. For Ginkgo (the same author's engine, used in Fritz products) the author says incremental network updates are done separately for each side and per full move rather than per half move, and that this differs from the engines he knows; no figure [19, TCEC]. UNVERIFIED that Fritz 20 has it (the questionnaire is about Ginkgo, 2025-10).
- Fused updates: not published.
- Accumulator stack: not published.
- Pairwise multiplication of accumulator halves: not published.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: not published.
- Evaluation cache: not published.
- SIMD and VNNI work: for the predecessor Fritz 18 Neuronal (2022), the vendor reports that the AVX-512 build reaches about the same nodes per second as the hand-written-evaluation Fritz 18 engine, and that the AVX2 build is "only 5% slower" than it; SSE2, AVX2 and AVX-512 builds are named [26, vendor]. No hardware stated. Nothing for Fritz 20 itself.
- Memory layout and prefetching: not published.
- Anything else that made the network faster: not published.
- Speed cost or gain reported for any architecture change: only the Fritz 18 Neuronal figure above (a network evaluation at 0 to 5% nps cost against the old evaluation) [26, vendor].
- Hardware sensitivity reported: not published.

### Training data
- Size of the rated net's data: not published for Fritz 20.
- Type: not published for Fritz 20. History of the line, all own self-play:
  - Fritz 18 Neuronal (March 2022): about 5 million games played, from which 400 million scored positions were generated; the first net was trained on the evaluations of 200,000 self-play games of the hand-written-evaluation Fritz 18 [26, vendor].
  - Ginkgo at the 2022 software championship: about 40 million self-play games on a lent 128-core, 512 GB machine in the two months before the event, for "testing and (further) training of the network" [27, vendor].
  - Ginkgo, October 2025: about 6.7 billion positions from self-play games of earlier Ginkgo versions [19, TCEC].
- Openings, filtering, tablebase use: not published.

### Training recipe (concepts only)
- Trainer: not published for Fritz 20; Ginkgo uses a privately written trainer built on the Eigen and MiniDNN libraries [19, TCEC].
- Loss and target: not published. Ginkgo "transforms scores before training and transforms them back after evaluating" [19, TCEC] (a target transform; its form is not published).
- Stages and schedule: Fritz 18 Neuronal was reached by a bootstrap net from the old evaluation followed by 80 training iterations, with about 300 intermediate nets tested and the best kept at each step [26, vendor]. For the 2022 Ginkgo "a good 500 versions" were developed and tested [27, vendor].
- Regularisation, optimiser, anything unusual: not published.

### Measured gains for network changes
- Network evaluation replacing the hand-written one (Fritz 18 to Fritz 18 Neuronal): about +120 Elo "at shorter time controls" (about 3300 to 3400+), at equal nps with AVX-512 and 5% fewer with AVX2 [26, vendor].
- Fritz 20 engine over Fritz 19: "over 100 Elo" (whole engine, not the network alone; no time control given) [24, vendor]; estimated 3,580 [25, vendor] [29, vendor].

### Architecture history
- November 2019 and November 2021: Fritz 17 and 18, engines by Frank Schneider [9, CPW].
- March 2022: Fritz 18 Neuronal, a free update with an NNUE evaluation [9, CPW] [26, vendor].
- July 2022: Ginkgo wins the software championship; its "network architecture essentially corresponds" to Fritz 18 Neuronal's [27, vendor].
- November 2023: Fritz 19 [9, CPW] [28, vendor].
- 2025-05-29: Fritz 20 announced; the engine shared first place in the software category of the 2024 championship in Santiago de Compostela [24, vendor].

### Since the rated version
- Nothing found.

### UNVERIFIED and not published
- Everything about the network's shape, inputs, activations and quantisation: not published.
- Whether Fritz 20's net equals the net of "Ginkgo Santiago 1.0" (CCRL rates them 23 points apart): UNVERIFIED, no page says.
- Fritz 20's training data size: not published (the 6.7 B figure is stated for Ginkgo in October 2025).
- ChessBase support pages 1377 and 1405 on the Fritz 18 engines would not load (redirect loop).

---

## Ginkgo Santiago 1.0 (CCRL #40-41, 3698)

**One-line architecture:** not published. Assembled: an NNUE-type network with an incremental update done per side and per full move [19, TCEC]; its 2022 ancestor's architecture "essentially corresponds" to Fritz 18 Neuronal's [27, vendor]. No sizes anywhere.

### Inputs
- Feature set: not published.
- King input buckets: not published.
- Horizontal mirroring: not published.
- Threat or attack inputs: not published.
- Pawn features: not published.
- Other input relationships: not published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: not published.
- Further layers: not published.
- Layer stacks: not published.
- Output buckets: not published.
- Skip connections, pairwise multiplication, other structure: not published.

### Activations
- After the accumulator: not published.
- In the head: not published.

### Quantisation
- Integer types per layer: not published.
- Quantisation-aware training or other rounding care: not published.

### Inference speed
- Accumulator refresh cache: not published.
- Lazy or deferred accumulator updates: the author's one published detail. Incremental updates are done separately for the two sides and over full moves instead of half moves; he believes no other engine does this. No gain figure, no hardware [19, TCEC]. How it works (for example, whether one side's half is brought up to date only when that side's view is needed) is not published.
- Fused updates: not published (the full-move update above may amount to one; UNVERIFIED).
- Accumulator stack: not published.
- Pairwise multiplication of accumulator halves: not published.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: not published.
- Evaluation cache: not published.
- SIMD and VNNI work: only the 2022 ancestor's figure (AVX-512 about equal nps to the old evaluation, AVX2 5% slower) [26, vendor].
- Memory layout and prefetching: not published.
- Anything else that made the network faster: not published.
- Speed cost or gain reported for any architecture change: not published.
- Hardware sensitivity reported: not published.

### Training data
- Size: about 6.7 billion positions [19, TCEC]. The questionnaire is dated 2025-10-13 and speaks of "Ginkgo"; that the figure is the Santiago 1.0 net's is carried from the prior survey and is UNVERIFIED (the release date of "Santiago 1.0" is on no page I opened).
- Type: own self-play, games played by earlier Ginkgo versions [19, TCEC]. Label method (search budget, relabelling): not published. Earlier points on the same chain: 400 million positions from about 5 million games in March 2022, the first net trained on the old evaluation's scores from 200,000 games [26, vendor]; about 40 million further self-play games before the July 2022 championship [27, vendor].
- Openings, filtering, tablebase use: not published (probing code is Ronald de Man's Syzygy code [19, TCEC]; use in training not stated).

### Training recipe (concepts only)
- Trainer: private, written on Eigen and MiniDNN [19, TCEC].
- Loss and target: scores are transformed before training and transformed back after evaluation [19, TCEC]; the transform is not published.
- Stages and schedule: an iterated chain (80 training iterations and about 300 candidate nets for the first release [26, vendor]; "a good 500 versions" for 2022 [27, vendor]).
- Regularisation, optimiser, anything unusual: not published.

### Measured gains for network changes
- None published for Ginkgo itself. See Fritz 20 for the 2022 figure (+120 Elo for the first network) [26, vendor].

### Architecture history
- 2014: Ginkgo started from scratch with a tuned hand-written evaluation [10, CPW].
- March 2022: first network (as Fritz 18 Neuronal) [26, vendor].
- July 2022: software world champion with essentially the same architecture [27, vendor].
- 2024: shared first in the software category at Santiago de Compostela (stated of the Fritz engine) [24, vendor].
- October 2025: 6.7 B positions; ratings the author quotes: about 3600 on CCRL 40/15 4CPU, about 3730 on CCRL 2+1 8CPU [19, TCEC].

### Since the rated version
- Nothing found.

### UNVERIFIED and not published
- All network dimensions, inputs, activations, quantisation: not published.
- That 6.7 B positions is the Santiago 1.0 net's data: UNVERIFIED (see above).
- The mechanics and gain of the per-side, per-full-move update: not published.
- Search depth or node budget of the self-play labels: not published.

---

## Revenge 4.0 (CCRL #40-41, 3698)

**One-line architecture:** not published. The author's words: evaluation is a "pure neural network", and 4.0 has a "new and bigger neural network" than 3.0 [31, vendor]. Its ancestor Pedone 3.0 was "a similar idea" to Stockfish's NNUE "with small differences to the net" [36, forum].

### Inputs
- Feature set: not published.
- King input buckets: not published.
- Horizontal mirroring: not published.
- Threat or attack inputs: not published.
- Pawn features: not published.
- Other input relationships: not published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: not published. Only the direction is known: 2.0's net was "new and bigger" than 1.0's [35, forum] and 4.0's "new and bigger" than 3.0's [31, vendor].
- Further layers: not published.
- Layer stacks: not published.
- Output buckets: not published.
- Skip connections, pairwise multiplication, other structure: not published.

### Activations
- After the accumulator: not published.
- In the head: not published.

### Quantisation
- Integer types per layer: not published.
- Quantisation-aware training or other rounding care: not published.

### Inference speed
- Accumulator refresh cache: not published.
- Lazy or deferred accumulator updates: not published. Revenge 2.0 lists "speed up neural network incremental update", no figure [35, forum].
- Fused updates: not published.
- Accumulator stack: not published.
- Pairwise multiplication of accumulator halves: not published.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: not published.
- Evaluation cache: not published.
- SIMD and VNNI work: 4.0 adds an executable for 256-bit VNNI and one for Linux ARMv8.2, and lists "speed optimizations in neural network calculations"; no figure for either [31, vendor]. 2.0: "speed up neural network calculation", no figure [35, forum].
- Memory layout and prefetching: large and huge pages are supported [31, vendor] [11, CPW]. The net has been embedded in the executable since Pedone 3.0 [36, forum]. File size not published.
- Anything else that made the network faster: not published.
- Speed cost or gain reported for any architecture change: not published.
- Hardware sensitivity reported: not published.

### Training data
- Size of the rated net's data: not published.
- Type: an own chain, as far as stated. Pedone 3.0 (January 2021): 300 million positions scored by Pedone's hand-written evaluation at depth 14 [36, forum]. Revenge 1.0 (July 2021): the search scores of Pedone 3.1, "that was trained with its predecessor and so on" [34, forum]. Revenge 2.0, 3.0 and 4.0: not stated.
- Openings, filtering, tablebase use: not published.

### Training recipe (concepts only)
- Trainer: the author's own training code (stated for Pedone 3.0 and Revenge 1.0) [36, forum] [34, forum].
- Loss and target: search scores of the previous version (Revenge 1.0) [34, forum]; any result blend not published.
- Stages and schedule: each version's net is trained on the previous version's search scores [34, forum]; nothing more.
- Regularisation, optimiser, anything unusual: not published.

### Measured gains for network changes
- No network-only figure exists. Whole-release figures, all self-play:
  - Pedone 3.0 (first network) over 2.1: about +150 [36, forum].
  - Revenge 1.0 over Pedone 3.1: about +50 [34, forum].
  - Revenge 2.0 over 1.0: about +90 at 1:00+0.5; the author adds that the new net is stronger in all phases, "especially in the endgame" [35, forum].
  - Revenge 4.0 over 3.0: +38 at 1:00+0.5 over 10,000 games with balanced openings [33, forum] [31, vendor].

### Architecture history
- 2021-01-01: Pedone 3.0, first pure network evaluation [36, forum] [12, CPW].
- 2021-07-09: Revenge 1.0, "new neural network" [34, forum].
- 2021-12-18: Revenge 2.0, "new and bigger" network, faster incremental update and calculation [35, forum].
- 2025-01-01: Revenge 4.0, "new and bigger" network, faster network calculation, VNNI-256 build; released free [31, vendor] [33, forum].

### Since the rated version
- Nothing found; 4.0 is the latest release [31, vendor].

### UNVERIFIED and not published
- Revenge 3.0's notes: UNVERIFIED. Both TalkChess posts of its release thread return 404; a search result summarised it as a new network plus speed work in network calculation, which I could not confirm on a page.
- Every dimension, the input features, activations and quantisation: not published.
- Data of 2.0 to 4.0 (size, type, label depth): not published.
- Any nps or Elo figure for the VNNI build or the network speed work: not published.

---

## Lc0 0.29.0 with network w753723 on an RTX 2080 (CCRL #45, 3695)

Lc0 is a GPU engine: the network gives a move policy and a value to a PUCT tree search, and is not an NNUE. The template is adapted; every field is still filled.

**One-line architecture:** assembled from the project's pages: a residual convolutional tower with squeeze-and-excitation, 15 blocks of 192 filters (training run T75), 112 input planes of 8×8, a convolutional policy head, a win-draw-loss value head and (in the general topology) a moves-left head. Evidence: the 0.29.0-rc0 notes say "15b default net is now 753723" [46, release notes]; the 0.29.0 notes keep it as the default for the two backends that lack attention-policy support [45, release notes]; "Latest T75" is listed in the "15/16 blocks x 192 filters" group as a finished test run [40, wiki]; run names are the leading digits of the network number [38, wiki].

### Inputs
- Feature set: 112 planes of 8×8 [37, wiki]. The Chessformer paper spells out the same 112 as used per square by the transformers, which follow Lc0's input scheme: 12 piece planes for each of the current and the last 7 positions (96), 8 repetition flags, 4 castling rights, side to move, the half-move clock scaled, and two constant planes kept for edge detection [53, paper]. The board is flipped to the side to move [53, paper] [49, blog]. Which numbered input format T75 used is UNVERIFIED (the history page's T75 entry is blank [42, wiki]).
- King input buckets: none (not an NNUE).
- Horizontal mirroring: none stated for T75. T77 lists "input format 4" without explanation [42, wiki].
- Threat or attack inputs: none as inputs.
- Pawn features: none as inputs.
- Other input relationships: history of 7 earlier positions, repetition flags, castling, fifty-move counter, side to move [53, paper].
- Factoriser or other training-only input structure: none.

### Body
- First hidden layer (accumulator) width per perspective: not applicable. Input convolution from 112 planes to the filter count (192 here) [37, wiki].
- Further layers: 15 residual blocks, each two 3×3 convolutions with a squeeze-and-excitation unit and a skip connection; batch normalisation is folded into the weights for inference [37, wiki]. The count of 15 is from the release notes [46, release notes]; the filters from the legacy list [40, wiki].
- Layer stacks: none.
- Output buckets: none. Heads [37, wiki]:
  - policy: two convolutions ending in 80 planes, from which a vector of 1858 move logits is gathered (the "convolution" policy format; 753723 has no attention policy [45, release notes]);
  - value: a convolution to 32 planes, a dense layer to 128, then three outputs with softmax (win, draw, loss). All nets from July 2019 have the WDL head [51, blog];
  - moves left: a small convolution and two dense layers to one number [37, wiki]. Present in T75: UNVERIFIED.
- Skip connections, pairwise multiplication, other structure: residual skips; squeeze-and-excitation (global pooling, two dense layers, a sigmoid gate and an added bias) [37, wiki].

### Activations
- After the accumulator: not applicable. In the tower: ReLU in the general topology [37, wiki]; T79 and T80 replaced ReLU with mish [42, wiki]. T75's activation is UNVERIFIED (nothing says it differs from ReLU).
- In the head: ReLU in the value and moves-left heads, softmax on WDL, no activation on the policy output [37, wiki].

### Quantisation
- Integer types per layer: none; floating point. The ONNX backends can run a network file in fp16, the default for onnx-cuda and onnx-dml from 0.29.0 [45, release notes].
- Quantisation-aware training or other rounding care: none for the rated net. See "Since the rated version" for INT8.

### Inference speed
The NNUE fields do not apply; the equivalents Lc0 reports are given.
- Accumulator refresh cache: not applicable.
- Lazy or deferred accumulator updates: not applicable.
- Fused updates: not applicable.
- Accumulator stack: not applicable.
- Pairwise multiplication of accumulator halves: not applicable.
- int8 layers or int8 feature-transformer rows: not in 0.29.0.
- Sparse first dense layer: not applicable.
- Evaluation cache: yes, the "NNCache" stores network outputs and reuses them when a position is reached again by transposition; no figure [43, wiki] [48, blog].
- SIMD and VNNI work: GPU backends instead (cuda, cudnn, onnx, metal, opencl, dx12, and CPU backends blas, dnnl, eigen) [45, release notes] [17, CPW]. 0.28.0 lists performance work for the cuda and cudnn backends and 0.28.2 "improved cuda performance for 512 filter networks" on one GPU generation, both without figures [46, release notes]. Which backend CCRL ran on its RTX 2080 is not published.
- Memory layout and prefetching: cost and file size grow with blocks times filters squared [38, wiki]. File size of 753723: not published.
- Anything else that made the network faster: batching of evaluations (0.29.0's benchmark assistant proposes batch sizes for three time controls) [47, blog].
- Speed cost or gain reported for any architecture change: 0.29.0's new onnx-dml backend is "a bit slower" than dx12 but runs attention-policy nets, whose strength "more than overcomes this speed loss" (no numbers) [47, blog].
- Hardware sensitivity reported: smaller nets search more nodes per second; the project advises the largest net the hardware supports [39, wiki] [17, CPW].

### Training data
- Size of the rated net's data: not published (T75's entry in the project history has only its end date, 2021-10-16 [42, wiki]; the server's run list no longer shows T75 [55, other]).
- Type: own self-play by reinforcement learning, as for all official runs [38, wiki]; "completely original and unadulterated" [22, TCEC] [23, TCEC]. Labels: the search's visit distribution as the policy target and the game result as the value target [53, paper]; a blend of search value and result, and tablebase rescoring of results, exist in the project [prior survey]. T75's own settings: not published.
- Openings, filtering, tablebase use: for T75 not published.

### Training recipe (concepts only)
- Trainer: the project's own lczero-training code (TensorFlow-based) [22, TCEC] [17, CPW].
- Loss and target: policy loss plus value loss plus a weight-norm regularisation term [43, wiki].
- Stages and schedule: a reinforcement-learning run in which each new network generates the next games; step-wise learning-rate drops during a run are logged for neighbouring runs [42, wiki]; checkpoints use stochastic weight averaging [53, paper].
- Regularisation, optimiser, anything unusual: T75 was one of the "test" runs used to try ideas for later main runs [38, wiki] [40, wiki]. Its purpose is not written down (blank entry [42, wiki]).

### Measured gains for network changes
- WDL value head: in all nets since July 2019; no Elo figure in the post [51, blog].
- Attention policy head (T78, T79, T80; after 753723): "more accurate", no figure [47, blog].
- Transformer against convolutional body: see "Since the rated version".

### Architecture history
- 2018: residual towers of 6×64, then 10×128, 15×192 and 20×256 [42, wiki] [17, CPW].
- T35: squeeze-and-excitation first used [43, wiki]. T40: 20×256 with SE. T50: WDL value head. T60: 24×320, later 30×384 [42, wiki].
- T75: 15 blocks × 192 filters, ended 2021-10-16 [40, wiki] [42, wiki].
- 0.28.0: a "larger/stronger 15b default net"; 0.29.0-rc0: "15b default net is now 753723" [46, release notes].
- 0.29.0 (December 2022): default net 791556 (T79, attention policy) on most backends, 753723 kept for opencl and dx12 [45, release notes] [47, blog].

### Since the rated version
- T78: 40 blocks × 512 filters (the 195 M-parameter convolutional net the paper calls Leela-CNN) [42, wiki] [53, paper]. T79: 15×192 with an attention policy head and mish. T80 (from 2022-04): 15×512, same head and activation, started from a net pre-trained on T79 data [42, wiki].
- Transformers ("BT" nets): encoder-only, one token per square (64 tokens), post-layer-norm, mish in the feed-forward layers, learned positional embedding [49, blog]:

  | Net | Layers | Embedding | FFN | Heads | Smolgen | New embedding | Params (M) | FLOPS (G) | Policy Elo vs T78 |
  |---|---|---|---|---|---|---|---|---|---|
  | T78 (CNN) | 40 blocks | 512 filters | - | - | - | - | 194.5 | 12.45 | 0 |
  | BT1 | 12 | 1024 | 1536 | 8 | no | no | 92 | 5.637 | +13 |
  | BT2 | 15 | 768 | 1024 | 12 | yes | no | 82 | 3.964 | +123 |
  | BT3 | 15 | 768 | 1024 | 24 | yes | yes | 105.5 | 4.158 | +179 |
  | BT4 | 15 | 1024 | 1536 | 32 | yes | yes | 191.3 | 7.613 | +270 |

  [49, blog]. BT4 is the paper's "Leela-CF" [49, blog] [53, paper].
- Each transformer addition with its reported cost [49, blog]:
  - a trainable bias added to the attention logits per head and layer: "play as if 50% larger" at negligible throughput loss;
  - smolgen (the paper's Geometric Attention Bias): the position is compressed to a small vector from which extra attention logits are generated per head through a projection shared by the whole model: another 50% effective size for a 10% throughput loss;
  - a wider feed-forward block gave little; small head depth is best;
  - a new embedding that lets every token see the whole board: as if 15% larger for 5% more latency;
  - planned for BT5: dropping biases and centring in most places, "training 10% faster and inference 5% faster" with no quality loss;
  - INT8 quantisation "could speed up our models by 50% without quality degradation" (stated as early success, February 2024).
- Heads in the paper: value = mean pooling, a 128-wide layer with ReLU, three WDL logits; policy = attention between source and destination squares giving a 64×64 move table, with a bias for promotions [53, paper]. BT3 and BT4 carry several policy heads [50, blog].
- Measured: Leela-CF against Leela-CNN in the engine at equal time: +112 ± 7, +111 ± 7 and +105 ± 7 Elo at three time controls, 2000 games each, on 8 RTX 4090 and 4 A100 GPUs where the CNN runs at about 20,000 playouts per second [53, paper]. Per evaluation the transformer needs 7.6 B FLOPs against 12.5 B for the CNN [53, paper]. In a small ablation the geometric bias beat a plain absolute position encoding by 83 Elo and matched it at about 60% of the parameters and computation [53, paper].
- Data and recipe of BT4 [53, paper]: supervised training on a fixed set of self-play games from a reinforcement-learning run made by a 100 M-parameter transformer at 600 nodes per move, keeping only games from after that run's strength levelled off; Nadam optimiser, gradient clipping, stochastic weight averaging, two late learning-rate drops. The paper's finding: nets trained on games made by convolutional nets and by transformers "reach virtually identical playing strengths", so the strength of the game generator matters more than its architecture. Data size in positions: not found in the passages I read.
- Current competition net: "BT4-it332" (1024 × 15, 365 MB file, about 4 GB of GPU memory); also listed: BT4 (330 MB), BT3 768×15 (190 MB), T82 768×15, distilled T3 512×15 with 16 heads (150-155 MB), T1 512×15 and T1 256×10 (30-40 MB) [39, wiki].
- Official runs today: test80 (the 2022 main run, inactive; its listed game budget is 10,000 visits per move), test90 and test91, "debug" runs training BT4 by reinforcement learning at 400 and 800 visits per move; their newest nets are 15 blocks × 1024 [55, other] [56, other].
- The 2026 questionnaire says the current net is trained by Kovax with the code of lczero-training pull request 251 [23, TCEC], whose description adds "value depth attention" and "policy depth attention" modules to the encoder [54, PR text].
- Backends since 0.29.0 [46, release notes]: attention-body and smolgen support and a persistent L2 cache optimisation for the cuda backend (0.30.0); multi-head nets BT3 and BT4, an XLA backend and backend-suggested batch sizes (0.31.0); a TensorRT backend and a backend for AMD, Intel and NVIDIA GPUs (0.32.0); in 0.33.0-rc0 fused multi-head attention in the cuda backend, less lock contention when splitting batches, quantisation control and bf16 in the TensorRT backend, fp16 and fp32 weight encodings in the net format. No speed figures in the notes.

### UNVERIFIED and not published
- T75's exact shape is read from "15b default net is now 753723" plus the "15/16 blocks x 192 filters" group; no single page states "753723 is 15×192".
- T75's input format, activation, moves-left head, value-target blend, visits per move, opening book, start date and number of games: not published on the pages opened.
- File size of 753723: not published.
- CCRL's backend and settings on the RTX 2080: not published.
- Size of BT4's training set in positions: not found.

---

## Chess System Tal 3.00 (CCRL #47-49, 3693)

**One-line architecture:** not published. The authors' words: "a freshly trained neural network and a rebuilt NNUE evaluation" [57, vendor] [58, README]. Engine code by Chris Whittington, network development by Ed Schröder [58, README].

### Inputs
- Feature set: not published.
- King input buckets: not published.
- Horizontal mirroring: not published.
- Threat or attack inputs: not published.
- Pawn features: not published.
- Other input relationships: not published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: not published. The release notes print the embedded net's identifier; one of its tokens is "1024", which may be a layer width, but no page explains the string: UNVERIFIED [58, release notes].
- Further layers: not published.
- Layer stacks: not published.
- Output buckets: not published.
- Skip connections, pairwise multiplication, other structure: not published.

### Activations
- After the accumulator: not published.
- In the head: not published.

### Quantisation
- Integer types per layer: not published.
- Quantisation-aware training or other rounding care: not published.

### Inference speed
- Accumulator refresh cache: not published.
- Lazy or deferred accumulator updates: not published.
- Fused updates: not published.
- Accumulator stack: not published.
- Pairwise multiplication of accumulator halves: not published.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: not published.
- Evaluation cache: not published.
- SIMD and VNNI work: 3.00 ships as AVX2 only, with no AVX-512 or scalar build yet [57, vendor]. For the older 2.07 the site says the AVX-512 build is "about 20% faster, though it varies by machine" than AVX2 [57, vendor].
- Memory layout and prefetching: the net is embedded in a single executable of about 113 MB (2.07's builds are about 40 MB each) [57, vendor]. The net's own size is not published.
- Anything else that made the network faster: not published.
- Speed cost or gain reported for any architecture change: not published.
- Hardware sensitivity reported: the "varies by machine" remark above [57, vendor].

### Training data
- Size of the rated net's data: not published.
- Type: not published for 3.00. What the authors say about their nets in general: the original Chess System Tal net was trained by Whittington on "probably a great mix of stuff, weighted" (his own recollection), while Schröder "uses his own training data" [65, forum]. Schröder's guest-engine nets are made from the guest engine's self-play, in two cases mixed with Leela data [62, vendor]. Whether 3.00's net contains Leela data: UNVERIFIED.
- Openings, filtering, tablebase use: not published for 3.00; Schröder's data tools are described under Rebel 17.0.

### Training recipe (concepts only)
- Trainer: not published. The net identifier in the release notes names the AdamW optimiser; its other tokens look like trainer settings and are not recorded here [58, release notes].
- Loss and target: not published.
- Stages and schedule: not published. The piece-value study on the authors' site profiles a 3.00 net labelled "ep285", so nets are kept per epoch [59, vendor].
- Regularisation, optimiser, anything unusual: style nets (EAS, Extreme, Absurd) are made by changing a "formula" in net creation and trade Elo for aggression; the Absurd net brings the engine down to about 3000 [63, vendor]. Asked how a net is made aggressive, Schröder answered: unbalanced games, boosted short decisive games, and rescoring every position with the hand-written ProDeo evaluation [66, forum].

### Measured gains for network changes
- None published for 3.00. Strength claim: about 3610 on the authors' own 10-engine gauntlet at 40 moves in 10 seconds, anchored to CCRL 40/15 4CPU [57, vendor] [58, README].

### Architecture history
- February 2022: four Tal-style nets by Whittington for Rebel 14.1 [67, forum] [14, CPW].
- June 2023: Chess System Tal 2.00, with an Elo flavour and a style flavour [13, CPW].
- 2.07 with the "E1019" net for strength, about 40 MB builds [57, vendor].
- 2026-09-29: 3.00 released as a binary; source not public [58, release notes] [58, README].

### Since the rated version
- Nothing after 3.00 found. (Chess System Tal EXTREME, a style net, dates from January 2026, before 3.00 [63, vendor].)

### UNVERIFIED and not published
- All dimensions, inputs, activations, quantisation: not published.
- Meaning of the net identifier, including the "1024": UNVERIFIED.
- Data type and size for 3.00: not published.
- The site and README say 3.00 "has not been tested by CCRL", yet CCRL lists it with 1,743 games [5, CCRL]; the pages are probably older than the CCRL entry. Not resolved.
- A forum post by a third party mentions "very large networks" and a 139 MB uncompressed executable for an earlier style build [60, forum]: second-hand, UNVERIFIED.

---

## Stoofvlees II b5 (CCRL #47-49, 3693)

Stoofvlees is a private GPU engine: MCTS with a neural network, not an NNUE.

**One-line architecture:** not published in any page I could open. Assembled: a Monte-Carlo tree search engine with a deep convolutional network run on NVIDIA GPUs through NVIDIA's libraries [20, TCEC] [16, CPW]. Blocks, filters, heads and input planes: not published (they are said to be in a paywalled journal article, see below).

### Inputs
- Feature set: not published.
- King input buckets: none (not an NNUE).
- Horizontal mirroring: not published.
- Threat or attack inputs: not published.
- Pawn features: not published.
- Other input relationships: not published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: not applicable.
- Further layers (tower): not published.
- Layer stacks: not published.
- Output buckets / heads: not published.
- Skip connections, pairwise multiplication, other structure: not published. The author says that apart from being "a MCTS + NN engine, pretty much every implementation detail or technique" is probably unique, and that some were later rediscovered in Leela [20, TCEC]; in 2019 he called it "a new design", made to try ideas "that never made it to Leela" [72, forum].

### Activations
- In the tower: not published.
- In the heads: not published.

### Quantisation
- Number types: not published.
- Quantisation-aware training or other rounding care: not published.

### Inference speed
- Accumulator refresh cache: not applicable (GPU network).
- Lazy or deferred accumulator updates: not applicable.
- Fused updates: not applicable.
- Accumulator stack: not applicable.
- Pairwise multiplication of accumulator halves: not applicable.
- int8 layers: not published.
- Sparse first dense layer: not applicable.
- Evaluation cache: not published.
- SIMD and VNNI work: runs on NVIDIA GPUs through NVIDIA libraries [20, TCEC]. For the 2019 version a tester reports that it also runs on a CPU "but about 300 points weaker" [72, forum].
- Memory layout and prefetching: the 2019 version's net file was about 44 MB as listed by a tester [72, forum]. b5's: not published.
- Anything else that made the network faster: not published.
- Speed cost or gain reported for any architecture change: not published.
- Hardware sensitivity reported: the author gives about 3750 Elo, "strongly hardware dependent" [20, TCEC].

### Training data
- Size: not published.
- Type: mixed. "Self-play games and Leela Zero Chess data" [20, TCEC]. Which version that covers, and the shares: not published.
- Openings, filtering, tablebase use: not published (Fathom is used for tablebase probing in play [20, TCEC]).

### Training recipe (concepts only)
- Trainer: the author's own, "written in raw PyTorch" [20, TCEC].
- Loss and target: not published.
- Stages and schedule: not published.
- Regularisation, optimiser, anything unusual: not published.

### Measured gains for network changes
- None published.

### Architecture history
- 2007: the first Stoofvlees, feature recognisers feeding a small network trained on grandmaster games [16, CPW].
- 2019: Stoofvlees II (versions a9 to a12), a new GPU design with its own net [72, forum] [16, CPW].
- World computer chess champion, announced by the ICGA [74, other] (2023 per the prior survey).
- b5: date and changes not published.

### Since the rated version
- Not published.

### UNVERIFIED and not published
- The article "Sin Dolor No Hay Gloria: On Conquering 2 World Computer Chess Championships in Spain" (ICGA Journal 47(3)), which the author names as the description of the engine's internals [20, TCEC], is paywalled: the publisher's page returned 403 and two metadata look-ups found nothing.
- One public abstract page of that article (in the source table) carries a notice against use with AI tools. The agent saw the notice only after opening the page. Nothing from that page is recorded in this survey.
- Everything about the b5 network's size, inputs, heads and data volume: not published.

---

## Rebel 17.0 (CCRL #50, 3688)

**One-line architecture:** not published. Stated: Rebel 17 "uses the same network as Rebel-16.3" and is 55 Elo stronger from engine-code changes alone [61, vendor]. Code base by Chris Whittington, network by Ed Schröder [61, vendor].

### Inputs
- Feature set: not published.
- King input buckets: not published.
- Horizontal mirroring: not published.
- Threat or attack inputs: not published.
- Pawn features: not published.
- Other input relationships: not published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: not published.
- Further layers: not published.
- Layer stacks: not published.
- Output buckets: not published.
- Skip connections, pairwise multiplication, other structure: not published.

### Activations
- After the accumulator: not published.
- In the head: not published.

### Quantisation
- Integer types per layer: not published.
- Quantisation-aware training or other rounding care: not published.

### Inference speed
- Accumulator refresh cache: not published.
- Lazy or deferred accumulator updates: not published.
- Fused updates: not published.
- Accumulator stack: not published.
- Pairwise multiplication of accumulator halves: not published.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: not published.
- Evaluation cache: not published.
- SIMD and VNNI work: not published (Rebel 14's inference code was optimised by Whittington, no figure [14, CPW]).
- Memory layout and prefetching: not published.
- Anything else that made the network faster: not published.
- Speed cost or gain reported for any architecture change: not published.
- Hardware sensitivity reported: not published.

### Training data
- Size of the rated net's data: not published. In November 2023 the net author showed statistics of "our 4B test data" [64, forum]; that this set trained the 16.3 net is UNVERIFIED.
- Type: not published for the 16.3 net. The author's guest-engine nets show his method: millions of fixed-depth self-play games of the source engine (46 million Shredder 13 games at depth 9 giving 3.65 billion positions after filtering; 16 million games at depth 6 giving 1.2 billion), and for two guests self-play "mixed with some Leela data" [62, vendor]. He asks for at least one billion positions, "14-15 million self play games", and offers a ready set of one billion Leela positions as the alternative to a second billion of self-play [65, forum]. Whether Rebel's own net contains Leela data: UNVERIFIED.
- Openings, filtering, tablebase use (the author's data tools, described in his own posts [64, forum]):
  - a "quiet" filter that can drop captures, positions in check and promotions; he keeps the in-check positions because "removing them cost elo", and reports that captures which sacrifice material can be learned, but only by a small net;
  - a sanity check that the set is balanced: equal white and black wins and a draw share held near two fifths, never much above a half;
  - balancing the number of positions per piece count by adding data where counts are thin: "good for ~10 elo, in this particular case";
  - removing positions whose score contradicts the game result beyond a margin (thresholds not recorded here);
  - shuffling before training; extracting material-imbalance and bishop-ending subsets as extra data.

### Training recipe (concepts only)
- Trainer: not published.
- Loss and target: not published; for the guest engines Whittington believes "the training is targeting eval" and leaves it to Schröder to confirm [65, forum].
- Stages and schedule: not published.
- Regularisation, optimiser, anything unusual: style nets are made by feeding unbalanced games, boosting short decisive games and rescoring every position with the hand-written ProDeo evaluation [66, forum].

### Measured gains for network changes
- Rebel 16.3 over Rebel-EAS: 35-40 Elo, "purely based on a stronger neural network" (estimate, no time control) [68, vendor].
- Piece-count balancing of the data: about +10 Elo in one case [64, forum].
- First networks: about +450 Elo at once, a further 250 within a year (the author's summary) [68, vendor].
- For contrast, engine code only: Rebel 17 over 16.3, +55 with the same net [61, vendor].

### Architecture history
- January 2022: Rebel 14, based on Fruit 2.1, with the authors' own NNUE implementation "Benjamin 1.1" and inference code by Whittington [14, CPW].
- February 2022: Rebel 14.1 with four style nets by Whittington [67, forum] [14, CPW].
- April 2022: Rebel 15, based on Toga [14, CPW].
- November 2022: Rebel 16, Whittington's Chess System Tal code with Schröder's "much improved" network [67, forum] [14, CPW].
- November 2023: Schröder halts NNUE development of Rebel, his hardware being "insufficient to make further progress in an acceptable time" [64, forum].
- Rebel 17: same net as 16.3 [61, vendor]. Release date not on the pages opened.

### Since the rated version
- Style engines only: Rebel-EAS-3.0 (January 2026, about 3570) and Rebel Maniac (about 3300), which uses ProDeo's hand-written evaluation code as well [63, vendor] [61, vendor].
- Guest engines (S13-NNUE, Strong Malt, SP3-NNUE, Maverick-NNUE) run the same search with nets trained from other engines' self-play [62, vendor].

### UNVERIFIED and not published
- All dimensions, inputs, activations, quantisation: not published.
- Data size and type of the 16.3 net: not published.
- The author's two documentation pages on his NNUE work, linked from the REBEL-Dev thread, now return 404, and rebel13.nl (the Rebel 14 to 16 and Benjamin pages) returns 526. Archived copies exist but the archive refused every request (429). The detail may well be there: UNVERIFIED, page would not load.

---

## rofChade 3.1 (CCRL #51, 3686)

**One-line architecture:** as the author writes it: "(2x768)x8x1" [71, forum]. The previous release, 3.0, was "HALFKA (2×256)x32x32x1" [69, vendor] [70, forum].

### Inputs
- Feature set: 3.0 used HalfKA [69, vendor]. For 3.1 the author gives only the string above; whether the inputs are still HalfKA is not stated (UNVERIFIED). The prior survey calls 3.1's net "simpler" [prior survey].
- King input buckets: 3.0: HalfKA, so one feature block per king square [69, vendor]; 3.1: not published.
- Horizontal mirroring: not published.
- Threat or attack inputs: none stated.
- Pawn features: none stated.
- Other input relationships: none stated. Outside the network, the engine switches to PeSTO piece-square tables when the evaluation is beyond a threshold [21, TCEC].
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 768 (3.1), 256 (3.0), reading the strings in the usual way [71, forum] [69, vendor].
- Further layers: 3.1: one hidden layer of 8, then the output. 3.0: two hidden layers of 32, then the output [71, forum] [69, vendor].
- Layer stacks: none stated.
- Output buckets: one output in both strings; none stated.
- Skip connections, pairwise multiplication, other structure: not published.

### Activations
- After the accumulator: not published.
- In the head: not published.

### Quantisation
- Integer types per layer: not published.
- Quantisation-aware training or other rounding care: not published.

### Inference speed
- Accumulator refresh cache: not published.
- Lazy or deferred accumulator updates: not published.
- Fused updates: not published.
- Accumulator stack: not published.
- Pairwise multiplication of accumulator halves: not published.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: not published.
- Evaluation cache: not published.
- SIMD and VNNI work: figures measured by a tester and relayed by the author for 3.1: on an Intel machine the AVX-512 build was about 19% faster than the BMI2/AVX2 build (opening position); on an AMD Zen 4 the AVX-512-VNNI build was about 10% faster than BMI2/AVX2 [71, forum]. The author's own machine has no AVX-512. The SSE builds broke during the architecture experiments and were rebuilt after release [71, forum]. The network code is the author's own, its matrix arithmetic "heavily influenced" by Cfish [69, vendor].
- Memory layout and prefetching: not published.
- Anything else that made the network faster: not published.
- Speed cost or gain reported for any architecture change: not published.
- Hardware sensitivity reported: the two AVX-512 figures above differ by CPU maker (19% Intel, 10% Zen 4 with VNNI) [71, forum].

### Training data
- Size: about 10 billion positions for 3.1 [71, forum]; 2.8 billion for 3.0, about 600 million of them Fischer-random positions [69, vendor].
- Type: own. Positions generated by rofChade and rescored repeatedly: "multiple recalculations during the last 1,5 year" (3.1) [71, forum]; "rescored a few times with intermediate networks to simulate reinforcement learning" (3.0) [69, vendor]. The author confirms self-generated data up to version 3.105 [21, TCEC]. The chain began in 2021 with one billion positions rescored by the hand-written evaluation at depth 10 [69, vendor]. Label depth for later rounds: not published.
- Openings, filtering, tablebase use: Fischer-random and double Fischer-random start positions were added to generate data (3.0) [69, vendor]. Tools exist for regenerating positions, rescoring them and recomputing game results [69, vendor]. Filtering details: not published.

### Training recipe (concepts only)
- Trainer: "a very old release" of the nnue-pytorch trainer [21, TCEC] [69, vendor].
- Loss and target: not published.
- Stages and schedule: repeated rescoring of the whole set by intermediate nets, then retraining [69, vendor] [71, forum].
- Regularisation, optimiser, anything unusual: the first attempt to rescore the set with the first network (10 days on 126 threads) gave "disappointing" training results [69, vendor].

### Measured gains for network changes
- First network (a standard HalfKA net on 1 B positions scored by the old evaluation at depth 10): about +100 Elo over the hand-written evaluation [69, vendor].
- Tuning the trainer's parameters on the same data: about +40 more [69, vendor].
- The net shipped in 3.0 against the net of test version 2.321: "only marginally stronger", 2 to 3 Elo [70, forum].
- 3.0 to 3.1 (new architecture, 10 B positions, search changes): no figure given.

### Architecture history
- December 2021: first HalfKA net on 1 B positions [69, vendor].
- May 2022: 3.0, HalfKA (2×256)→32→32→1, 2.8 B positions; "for now, this still gives the best results" [69, vendor] [70, forum].
- September 2023: 3.1, "after multiple nn architecture experiments", (2×768)→8→1 on about 10 B positions [71, forum].

### Since the rated version
- From development version 3.105 the author mixes his own data with "some older filtered Stockfish training data based on" Lc0 data, and for that reason declares the engine not compliant with TCEC's NNUE guideline [21, TCEC].

### UNVERIFIED and not published
- 3.1's input features, activations, quantisation, output scaling: not published.
- Whether "(2x768)" means 768 per perspective over a plain piece-square input set, or over a king-bucketed set: UNVERIFIED.
- Label depth or node budget after the first round: not published.
- Any Elo figure for the move from the 3.0 to the 3.1 architecture: not published.

---

## Sources

All opened 2026-11-14. "F" rows are fetches that returned no usable page.

| # | URL | What it is | Type | Used for |
|---|---|---|---|---|
| 1 | computerchess.org.uk/ccrl/404/cgi/engine_details.cgi?match_length=30&print=Details+(text)&eng=Fritz 20 64-bit 8CPU | CCRL Blitz engine details | CCRL | Fritz |
| 2 | same, eng=Ginkgo Santiago 1.0 64-bit 8CPU | CCRL Blitz engine details | CCRL | Ginkgo |
| 3 | same, eng=Revenge 4.0 64-bit 8CPU | CCRL Blitz engine details | CCRL | Revenge |
| 4 | same, eng=Lc0 0.29.0 64-bit w753723 RTX2080 | CCRL Blitz engine details | CCRL | Lc0 |
| 5 | same, eng=Chess System Tal 3.00 64-bit | CCRL Blitz engine details | CCRL | CSTal |
| 6 | same, eng=Stoofvlees II b5 64-bit RTX2080 | CCRL Blitz engine details | CCRL | Stoofvlees |
| 7 | same, eng=Rebel 17.0 64-bit | CCRL Blitz engine details | CCRL | Rebel |
| 8 | same, eng=rofChade 3.1 64-bit 8CPU | CCRL Blitz engine details | CCRL | rofChade |
| 9 | chessprogramming.org/Fritz | CPW page | CPW | Fritz |
| 10 | chessprogramming.org/Ginkgo | CPW page | CPW | Ginkgo |
| 11 | chessprogramming.org/Revenge | CPW page | CPW | Revenge |
| 12 | chessprogramming.org/Pedone | CPW page | CPW | Revenge |
| 13 | chessprogramming.org/Chess_System_Tal | CPW page | CPW | CSTal |
| 14 | chessprogramming.org/Rebel | CPW page | CPW | Rebel, CSTal |
| 15 | chessprogramming.org/RofChade | CPW page (pre-network description) | CPW | rofChade |
| 16 | chessprogramming.org/Stoofvlees | CPW page | CPW | Stoofvlees |
| 17 | chessprogramming.org/Leela_Chess_Zero | CPW page | CPW | Lc0 |
| 18 | wiki.chessdom.org/Engines_by_TCEC_Questionnaire | index of questionnaires | TCEC | all |
| 19 | wiki.chessdom.org/Ginkgo_questionnaire_20251013 | author's questionnaire | TCEC | Ginkgo, Fritz |
| 20 | wiki.chessdom.org/Stoofvlees_questionnaire_20251109 | author's questionnaire | TCEC | Stoofvlees |
| 21 | wiki.chessdom.org/RofChade_questionnaire_20251112 | author's questionnaire | TCEC | rofChade |
| 22 | wiki.chessdom.org/LCZero_questionnaire_20251107 | team's questionnaire | TCEC | Lc0 |
| 23 | wiki.chessdom.org/LCZero_questionnaire_20261106 | team's questionnaire | TCEC | Lc0 |
| 24 | en.chessbase.com/post/brand-new-release-fritz-20 | announcement | vendor | Fritz, Ginkgo |
| 25 | en.chessbase.com/post/review-fritz-20-a-revolutionary-leap-forward-in-chess-software | review on the vendor's site | vendor | Fritz |
| 26 | en.chessbase.com/post/free-fritz18-update-fritz18neuronal-engine | Fritz 18 Neuronal announcement | vendor | Fritz, Ginkgo |
| 27 | en.chessbase.com/post/ginkgo-fritz-is-world-champion | news item, July 2022 | vendor | Fritz, Ginkgo |
| 28 | en.chessbase.com/post/presenting-fritz-19 | announcement | vendor | Fritz |
| 29 | shop.chessbase.com/en/products/fritz_20 | product page | vendor | Fritz |
| 30 | talkchess.com/viewtopic.php?p=923656 | thread "Fritz 18 Neuronal" (repeats 26) | forum | Fritz |
| 31 | revengechess.com | author's site, 4.0 notes | vendor | Revenge |
| 32 | revengechess.com/getit.html | download page | vendor | Revenge |
| 33 | talkchess.com/viewtopic.php?p=974682 | "New release Revenge 4.0" | forum | Revenge |
| 34 | talkchess.com/viewtopic.php?p=899066 | Revenge 1.0 announcement and author's reply | forum | Revenge |
| 35 | talkchess.com/viewtopic.php?p=915268 | "New release Revenge 2.0" | forum | Revenge |
| 36 | talkchess.com/viewtopic.php?p=883632 | "New release Pedone 3.0" | forum | Revenge |
| 37 | lczero.org/dev/backend/nn/ | "Neural network topology" | wiki | Lc0 |
| 38 | lczero.org/play/networks/ and /play/networks/basics/ | "Networks and Runs" | wiki | Lc0 |
| 39 | lczero.org/play/networks/bestnets/ | best networks (updated 2026-10-09) | wiki | Lc0 |
| 40 | lczero.org/play/networks/legacy/ | legacy networks | wiki | Lc0 |
| 41 | lczero.org/dev/wiki/best-nets-for-lc0/ | older copy of 39 and 40 | wiki | Lc0 |
| 42 | lczero.org/dev/wiki/project-history/ and github.com/LeelaChessZero/lc0/wiki/Project-History | project history (same text) | wiki | Lc0 |
| 43 | lczero.org/dev/wiki/technical-explanation-of-leela-chess-zero/ | glossary and overview | wiki | Lc0 |
| 44 | lczero.org/dev/wiki/training-runs/, /neural-net-training/, /training-data-format-versions/ | older wiki pages; nothing on T75 | wiki | Lc0 |
| 45 | github.com/LeelaChessZero/lc0/releases/tag/v0.29.0 | release notes | release notes | Lc0 |
| 46 | github.com/LeelaChessZero/lc0/releases (pages 1 and 2) and /releases/tag/v0.28.0 | release notes v0.28.0 to v0.33.0-rc0 | release notes | Lc0 |
| 47 | lczero.org/blog/2022/12/lc0-release-v0.29.0/ | blog | forum (blog) | Lc0 |
| 48 | lczero.org/blog/2023/01/2022-progress/ | blog | forum (blog) | Lc0 |
| 49 | lczero.org/blog/2024/02/transformer-progress/ | blog | forum (blog) | Lc0 |
| 50 | lczero.org/blog/2024/02/how-well-do-lc0-networks-compare-to-the-greatest-transformer-network-from-deepmind/ | blog | forum (blog) | Lc0 |
| 51 | lczero.org/blog/2020/04/wdl-head/ | blog | forum (blog) | Lc0 |
| 52 | lczero.org/blog/2021/06/the-importance-of-open-data/ and blog index pages 1-6 | blog (data licence; index) | forum (blog) | Lc0 |
| 53 | arxiv.org/abs/2605.19091 and arxiv.org/html/2605.19091 | "Chessformer: A Unified Architecture for Chess Modeling" | paper | Lc0 |
| 54 | github.com/LeelaChessZero/lczero-training/pull/251 | pull request title and description only | PR / issue / commit text | Lc0 |
| 55 | training.lczero.org/training_runs | server's run list | other | Lc0 |
| 56 | training.lczero.org/networks/3 (and two query variants) | server's network list (number, blocks, filters) | other | Lc0 |
| 57 | whittingtonchess.com and /chess-system-tal | authors' site | vendor | CSTal |
| 58 | github.com/ChrisWhittington/ChessSystemTal3 and /releases | README and release notes of a binary-only repository | README / release notes | CSTal |
| 59 | whittingtonchess.com/research, /reverse-engineered-nnue, /about | research pages | vendor | CSTal |
| 60 | talkchess.com/viewtopic.php?p=987998, p=978682, p=950084 | Chess System Tal threads | forum | CSTal |
| 61 | rebel7775.wixsite.com/rebel | Rebel home page | vendor | Rebel |
| 62 | rebel7775.wixsite.com/rebel/guest-engines | guest engines | vendor | Rebel, CSTal |
| 63 | rebel7775.wixsite.com/rebel/ pages: about-1, about-1-1, absurd-1-0, blank-1, copy-of-kasparov, copy-of-stc-rating-list, downloads, emulate, kopie-van-rebel-eas-2-0, playing-style-rating-list, protools, simex, stc-rating-list | other pages of the site | vendor | Rebel, CSTal |
| 64 | talkchess.com/viewtopic.php?p=954580 | thread "REBEL-Dev" | forum | Rebel |
| 65 | talkchess.com/viewtopic.php?p=993164 | "New Guest Engine: Maverick NNUE" | forum | Rebel, CSTal |
| 66 | talkchess.com/viewtopic.php?p=969684 | "New REBEL's" | forum | Rebel, CSTal |
| 67 | talkchess.com/viewtopic.php?p=938739, p=920074, p=941432, p=941426, p=923855, p=992006, p=991990 | Rebel 16; four new Rebels; "Games for Training NNUE?"; Rodent NN; Strong Malt | forum | Rebel, CSTal |
| 68 | en.chessbase.com/post/rebel-and-playing-style-in-chess | interview with Ed Schröder | vendor (news) | Rebel |
| 69 | rofchade.nl, rofchade.nl/?p=411, /?p=375, /?page_id=7 | author's blog and downloads | vendor | rofChade |
| 70 | talkchess.com/viewtopic.php?p=925751 | "New release: rofChade 3.0" | forum | rofChade |
| 71 | talkchess.com/viewtopic.php?p=952948 and ?t=82649&start=10, &start=20 | rofChade 3.1 release thread | forum | rofChade |
| 72 | talkchess.com/viewtopic.php?t=70631 (and &start=10), ?t=71145 | "the digital rebirth of Deep Sjeng", 2019; a CEGT list | forum | Stoofvlees |
| 73 | ebsco.com/articles/sports-and-leisure/a4bb23c2-1e26-51bc-b40b-a0278e41e4f0/sin-dolor-no-hay-gloria-on-conquering-2-world-computer-chess-championships-in-spain | abstract page of the ICGA Journal article; carries a notice against use with AI tools | other | Stoofvlees (flagged, not used) |
| 74 | icga.org/?p=3864 | world champion announcement | other | Stoofvlees |
| 75 | talkchess.com/viewtopic.php?p=918384 | a test of a third-party net trained on T75 data (not about 753723) | forum | not used |
| 76 | sjeng.org | author's site; nothing on Stoofvlees | vendor | not used |
| F1 | journals.sagepub.com/doi/10.1177/13896911251360654 | the Stoofvlees article | failed (403) | - |
| F2 | api.openalex.org and api.crossref.org look-ups of that DOI | metadata | failed (404) | - |
| F3 | content.iospress.com/articles/icga-journal/icg230232 and icg230225 | ICGA Journal reports | failed (403) | - |
| F4 | talkchess.com/viewtopic.php?p=929347 and p=929354 | Revenge 3.0 thread | failed (404) | - |
| F5 | rebel13.nl/home/benjamin.html, /windows/rebel-14.html, rebel-15.html, rebel-16.html | Rebel pages | failed (526) | - |
| F6 | rebel7775.wixsite.com/rebel/kopie-van-adrl-blitz-1 and -2 | Schröder's NNUE documentation and data blog | failed (404) | - |
| F7 | web.archive.org copies of F5 and F6 (the availability look-up answered; every page request was refused) | archive | failed (429; unreachable by the fetch tool too) | - |
| F8 | archive.ph copy of F6 | archive | failed (host not resolved) | - |
| F9 | en.chessbase.com/post/free-fritz-update-ai-engine-fritz-18-neuronal; de.chessbase.com/post/kostenloses-fritz18-update-fritz18-neuronal-engine | guessed addresses | failed (404) | - |
| F10 | en.chessbase.com/support-kb/content/details/1377 and 1405 | support articles on the Fritz 18 engines | failed (redirect loop) | - |
| F11 | training.lczero.org/networks/3?show_all=1 | full list | returned only the latest 100 nets; 753723 not shown | - |
| S | Web searches, snippets used only to find pages: T75 and 753723; the Stoofvlees article; Fritz 18 Neuronal; Ginkgo and NNUE; "Ginkgo Santiago"; Revenge 4.0; Revenge 3.0; rofChade 3.1; Rebel 16 network (two); Stoofvlees network; Rebel 17; the ProDeo forum | search | other | - |

Credit lines:
- Fritz 20: ChessBase GmbH; engine by Frank Schneider. Commercial.
- Ginkgo: Frank Schneider. Private; the author owns the copyright and sometimes licenses it [19].
- Revenge (formerly Pedone): Fabio Gobbato. Closed; free to download since 4.0 [33].
- Leela Chess Zero (Lc0): the LCZero team (the questionnaire names borg, crem and others). GPL version 3 with an additional permission for NVIDIA libraries [22]; training data under ODbL and DbCL [52]. Chessformer paper: Daniel Monroe, George Eilender, Philip Chalmers, Zhenwei Tang, Ashton Anderson; CC BY 4.0 [53].
- Chess System Tal 3: Chris Whittington, network development by Ed Schröder. Binary only; source not public [58].
- Stoofvlees II: Gian-Carlo Pascutto. Proprietary [20].
- Rebel 17: code base Chris Whittington, network Ed Schröder, opening book Jeroen Noomen [61]. Closed binary.
- rofChade: Ronald Friederich. Closed; uses the MIT-licensed Fathom library [21].
- Chess Programming Wiki: CC BY-SA 3.0. TCEC wiki: CC BY-SA 3.0.

## Clean-room statement

I opened no source file, header, build file, training script, trainer configuration, diff, "Files changed" tab, blame view, code search result or network file of any engine or trainer, and I cloned or downloaded no repository, release archive, binary or network. I made no `gh api` calls. Pages were fetched with curl under a generic browser User-Agent and stripped to text by a small script of my own that drops `pre` and `code` elements.

Things that came close:
- The arXiv HTML of the Chessformer paper [53] contains one figure of "Torch-like pseudocode" that is not marked up as code, so my stripper let about ten lines of it into a tool output. It is pseudocode in a published CC BY paper, not engine source. I did not use or transcribe it.
- The Lc0 training server's run page [55] lists each run's self-play command line, which includes search parameters. I recorded only the visits per move (the data-generation budget the brief asks for) and none of the search constants.
- The Lc0 project-history page [42] lists learning rates and regularisation weights of several runs. None is recorded.
- The release notes of Chess System Tal 3.00 [58] print the embedded net's identifier, a string that looks like a training-run tag. I recorded only that it contains "1024" and the optimiser's name.
- The REBEL-Dev thread [64] gives numeric thresholds for a data filter; I described the filter without them.
- The pull-request page [54] was read for its title and description only; I did not open its commits or changed files, and stopped at the start of the automated review.
- The abstract page [73] of the Stoofvlees article carries a notice that its content may not be used with AI tools. I saw the notice only after opening the page. Its two additional claims appear in no engine field and are isolated in one flagged bullet for the owner to keep or strike.

Files: I wrote only inside my scratch folder: `tools\get.sh`, `tools\h2t.py` and the fetched pages under `pages\` (HTML and stripped text). `report.md` does not exist there because the Write tool refused it; this message is the only copy of the report. I deleted nothing and wrote nothing outside that folder. A search of the folder for `.git`, archives, executables, network files and source files found none.
