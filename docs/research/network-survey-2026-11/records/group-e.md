# Network records, group E: Astra, Raphael, RubiChess, Starzix, Tarnished, Clover, Halogen

Clean-room network survey of 2026-11-14 ([README](../README.md)). Written by survey agent E from public prose only and assembled unchanged except for local paths. Source numbers in brackets refer to the Sources table at the end of this file. Every engine here is REFERENCE ONLY for ideas; its code, nets and data are OFF-LIMITS for Fork.


Engines: Astra 7.0, Raphael 4.2.0, RubiChess 20240817, Starzix 6.0, Tarnished 6.0,
Clover 9.1, Halogen 16.0.0. Ranks and Elo are the coordinator's (CCRL Blitz list
computed 2026-11-14).

Conventions:

- `[n, type]` is the source number in the table at the end and the source type.
  `[prior survey]` marks a fact carried from `engine-survey-2026-11` and not
  re-opened today.
- Elo figures are self-play SPRT or match results as the page reports them, with
  the time control the page gives. "STC" and "LTC" are the engine's own labels.
  "Non-regression" means the test ran on bounds that only ask for "not worse".
- Values the brief excludes (quantisation scales, clipping bounds, learning rates,
  result-blend weights, loss exponents, schedule lengths, adjudication thresholds)
  were seen on some pages and are described as concepts only.
- Every statement of mine that is a reading or an inference, not the page's own
  words, is marked "(my reading)" and listed under UNVERIFIED.

---

## Astra 7.0 (CCRL #21-22, 3729)

**One-line architecture:** UNVERIFIED for 7.0 (not published: the 7.0 notes only
say the network architecture changed [3, release notes], and the self-play branch's
commit messages say "new architecture" six times without a string [6, commit text]).
The last string the author published is for the Lc0-data net of December 2025:
`(13x768->1536)x2 -> (16 -> 32 -> 1)x8 -> selected output` [4, PR text].

### Inputs
- Feature set (what an input means; inputs per perspective if stated): 768
  piece-square inputs per king bucket, as the strings `10x768`, `12x768` and
  `13x768` show [3, release notes] [4, PR text]. For 7.0: not published.
- King input buckets: count; layout (which king squares share a bucket, in words); how the layout was chosen or grown: 10 in 5.0, 12 in 6.0, 13
  in the December 2025 net [3, release notes] [4, PR text]. One more "new input
  bucket" net was merged on the self-play branch on 2026-04-28 (+4.14 +- 2.25 at
  10+0.1, same data) [6, commit text]. Count in 7.0, layout and how the layout was
  chosen: not published.
- Horizontal mirroring (when the king crosses the middle, or other): not published.
- Threat or attack inputs (what relation they encode; how many; how they are updated): none mentioned on any page opened; UNVERIFIED (not
  published).
- Pawn features (pawn pairs, passed pawns, other): none mentioned; UNVERIFIED (not published).
- Other input relationships (material or queen routing, pins, mobility, side-to-move, castling, anything else): 5.0 added a "phase evaluation" beside the network
  [3, release notes]; nothing else published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 1536 in 6.0 and in the
  December 2025 net [3, release notes] [4, PR text]. In 7.0: not published.
- Further layers: count and widths: 16 then 32 then 1 in the December 2025 net
  [4, PR text]. In 7.0: not published.
- Layer stacks (several copies of the head): count and what selects one: 8 copies of the head ("x8") in the December 2025 net; the selector
  is not stated [4, PR text].
- Output buckets: count and what selects one (piece count, material, phase, queen presence, other): introduced in the rewritten code base on 2025-08-26 [6, commit
  text]; 8 in the December 2025 net, written as "selected output" [4, PR text].
  What selects one: not published.
- Skip connections, pairwise multiplication, other structure: not published.

### Activations
- After the accumulator: squared clipped ReLU since 6.0 (clipped ReLU before)
  [3, release notes].
- In the head (dual activation, others): the two head layers were changed from squared clipped ReLU to
  clipped ReLU on 2025-12-18: +6.36 +- 3.36 at 40+0.4 [4, PR text]. In 7.0: not
  published.

### Quantisation
- Integer types per layer (int8, int16, float layers): not published. A commit inside PR #14 is titled as an
  update to the first dense layer's quantisation, and another as better
  floating-point accuracy for the non-SIMD path, which suggests float arithmetic
  somewhere in the head (my reading) [4, PR text].
- Quantisation-aware training or other rounding care: not published.

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: not published. One commit title (2025-08-27) says
  the accumulator is no longer refreshed unnecessarily; no figure [6, commit text].
- Lazy or deferred accumulator updates (computed only when an evaluation is needed; walked back along the stack): introduced 2025-08-21 in the rewritten
  code base; no figure [6, commit text].
- Fused updates (several feature changes applied in one pass; add-sub forms): not published.
- Accumulator stack (how accumulators are kept along the search path; copy avoidance): not published.
- Pairwise multiplication of accumulator halves (as a way to halve the next layer's input): not published.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer (non-zero block iteration, neuron permutation for sparsity): the 7.0 net's weights were permuted after training
  (2026-05-21): +2.54 +- 2.58 at 4+0.04 on non-regression bounds [6, commit text].
  The commit does not say what the permutation is for; that it serves a sparse
  first dense layer is my reading, UNVERIFIED.
- Evaluation cache (a hash table of network outputs, separate from the TT): not published.
- SIMD and VNNI work (AVX2, AVX-512, VNNI dot products, NEON; register tiling; anything about which instruction set won or lost): AVX2 added in 4.0, AVX-512 in 4.0.1; SIMD re-added on
  2025-08-21 after the rewrite; no figures [3, release notes] [6, commit text].
- Memory layout and prefetching (alignment, huge pages, weight ordering, prefetch of rows or cache entries, net compression and file size): weights are embedded in the binary with incbin
  [1, README]. Net file size: not published.
- Anything else that made the network faster: PGO builds allowed from 2026-05-26;
  no figure [6, commit text].
- Speed cost or gain reported for any architecture change: none reported.
- Hardware sensitivity reported (cache size, core count, a machine where a technique lost): none reported.

### Training data
- Size (positions or games) of the rated net's data: about 12 billion positions [1, README]
  [3, release notes]. The published data set is 29.6 GB [7, dataset card].
- Type: own self-play / Lc0 or Lc0-relabelled / another engine's / mixed / unknown; and how the labels are made (search budget, relabelling, teacher): own self-play, started from randomly initialised weights; 21 networks
  were trained in sequence, each generating data for the next, before one beat
  the Lc0-data net on the main branch [1, README] [3, release notes]. Versions up
  to 6.1.1 were trained on Lc0-generated games [1, README]. Search budget of the
  labels: not published.
- Openings, filtering, tablebase use: positions before ply 8 are filtered out
  (+4.97 +- 2.89 at 10+0.1, LLR 2.20, same data) [6, commit text]. Openings and
  tablebase use: not published. Games are stored in Stockfish's binpack format
  [1, README].

### Training recipe (concepts only)
- Trainer: Sorei, the author's own CUDA training library (MIT) [1, README]
  [8, README]. Before: Astra-Trainer from 5.0, CudAD below 5.0, a PyTorch net
  below 4.0 [2, README].
- Loss and target (result blend, as a concept): a result weight that ramps linearly during training gained
  +9.62 +- 3.61 at 10+0.1 on the same data [6, commit text].
- Stages and schedule (warm start, fine-tunes, weight averaging): net "v14" is a fine-tune of "v13" on the game result
  alone: +47.35 +- 7.76 at 10+0.1 [6, commit text]. Whether the 7.0 net keeps
  such a stage: not published.
- Regularisation, optimiser, anything unusual: old generations are merged back
  in ("v16" merged v15's data with v9's: +13.92 +- 4.36 at 10+0.1) [6, commit
  text]. Optimiser: not published.

### Measured gains for network changes
- 10 king buckets and a new net, 5.0 against 4.1 (whole release): +186.0 +- 7.3
  at 8+0.08 [3, release notes].
- 12 buckets, 1024 to 1536, squared clipped ReLU, 6.0 against 5.2 (whole
  release): +127.59 +- 9.58 at 60+0.6 [3, release notes].
- Single layer `(12x768 -> 1536)x2 -> 1` to the multi-layer net with 13 buckets
  and 8 output buckets: +5.28 +- 3.02 at 40+0.4 [4, PR text].
- Clipped ReLU instead of squared clipped ReLU in the two head layers: +6.36 +-
  3.36 at 40+0.4 [4, PR text].
- Self-play ladder, each against the previous net [6, commit text]:
  - about 5 million positions against random weights: every game won;
  - two further "new data, weights and architecture" steps: +543 and +677;
  - v4, about 125 M new positions: +223.0 +- 23.1 at 10+0.1;
  - v5, about 150 M: +33.0; v6, new architecture, about 350 M: +33.1;
  - v7, new architecture, about 2.5 B: +94.6 +- 10.5;
  - v8, new architecture, about 2 B: +9.4; plus 700 M more: +4.9;
  - v11, about 3 B new: +23.5 +- 5.7; new architecture on v12's data: +13.2;
  - v17, v16's data plus 2 B new: +7.3; v19, plus about 2.3 B new: +5.2 at 8+0.08;
  - v20, new architecture and 1.6 B new: +9.1 +- 4.3 at 8+0.08;
  - v21, new architecture on v20's data: +8.56 +- 3.93 at 60+0.6.
- Self-play net (about 12 B) replacing the Lc0-data net on main: +7.21 +- 3.68 at
  60+0.6 [6, commit text].
- 7.0 against 6.1.1 (whole release): +99.33 +- 6.17 at 60+0.6 [3, release notes].

### Architecture history
- 3.0 (2024-10): `768->2x256->1`, replacing `768->2x512->1` [3, release notes].
- 4.0 (2024-11): `768 -> 2x1024 -> 1`, over 1 billion positions, AVX2 [3, release notes].
- 5.0 (2025-02): `2x(10x768->1024)->1`, plus a phase evaluation [3, release notes].
- 6.0 (2025-07): `(12x768 -> 1536)x2 -> 1`, squared clipped ReLU [3, release notes].
- 2025-08: code base rewritten; network, SIMD, lazy updates and output buckets
  re-introduced within a week [6, commit text].
- 2025-12-14: `(13x768->1536)x2 -> (16 -> 32 -> 1)x8` [4, PR text].
- 2025-12-18: clipped ReLU in the head [4, PR text].
- 2026-01-31 to 2026-05-20: self-play branch, 21 nets from random weights; the
  architecture changed at least six times, strings not given [6, commit text].
- 7.0 (2026-05-26): self-play net, "changes to the neural network architecture"
  [3, release notes].

### Since the rated version
- 2026-06-15: new network, +2.95 +- 2.08 at 40+0.4 [6, commit text].
- 2026-06-19: new network with a filter based on piece count, +2.82 +- 2.33 at
  40+0.4 (LLR 2.17, merged before the bound) [6, commit text].

### UNVERIFIED and not published
- The architecture of the 7.0 net (widths, bucket count, head, activations): not
  published; only "new architecture" in commit messages.
- King-bucket layout, mirroring, the output-bucket selector: not published.
- Integer types and quantisation: not published.
- Label search budget, openings, tablebase use, optimiser: not published.
- Purpose of the weight permutation (sparse first dense layer): my reading.
- Float arithmetic in the head: my reading of two commit titles.
- The data-set card on Hugging Face is empty; only its size and licence show.

---

## Raphael 4.2.0 (CCRL #21-22, 3729)

**One-line architecture:** `((768x16+60144)hm->768pw)x2->(32->32->1)x8`, as the
engine's network log writes it for the net marked "default for v4.2"
[11, prose net log].

### Inputs
- Feature set (what an input means; inputs per perspective if stated): two blocks per perspective, both horizontally mirrored: 768
  piece-square inputs in each of 16 king buckets, and 60,144 threat inputs
  [11, prose net log]. Since the 16-bucket net the two king planes are merged, so
  a bucket really holds 704 inputs, which cut the net size by 8% [11, prose net log].
- King input buckets: count; layout (which king squares share a bucket, in words); how the layout was chosen or grown: 16, over the four files left after mirroring. The log
  prints a 4-by-8 table: the first two rows give every file its own bucket
  (8 buckets); the third and fourth rows have two buckets each (outer file pair
  and inner file pair); the fifth and sixth rows share one such pair of buckets,
  and so do the seventh and eighth [11, prose net log]. That the first row is the side's own
  back rank is my reading; the log does not label the rows.
  How it grew, each step trained on more data [11, prose net log] [14, PR text]:
  - 4 buckets: +2.90 +- 2.21 at fixed nodes, failed STC; merged only after more
    data (+25.42 +- 9.23 STC with 3.0 B positions, oldest set dropped);
  - 6 buckets, 4.0 B: +33.36 +- 10.48 STC;
  - 8 buckets, 5.5 B: +10.32 +- 5.53 STC;
  - 10 buckets, 7.0 B: +9.73 +- 5.42 STC;
  - 16 buckets, 10.7 B: +8.30 +- 4.85 STC.
  How the layout itself was chosen: not published.
- Horizontal mirroring (when the king crosses the middle, or other): yes ("hm"), added early: +16.51 +- 8.00 STC [11, prose net log]. The
  exact trigger (which king files flip the board): not published.
- Threat or attack inputs (what relation they encode; how many; how they are updated): 60,144 per perspective, added in 4.2; the
  implementation is "heavily based on" Stormphrax's [14, PR text]. What relation
  an input encodes and how they are updated: not published in Raphael's prose
  (UNVERIFIED, only in code).
- Pawn features (pawn pairs, passed pawns, other): none; the README's feature list leaves "Pawn pair inputs"
  unticked [10, README].
- Other input relationships (material or queen routing, pins, mobility, side-to-move, castling, anything else): none published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 768 in the rated net
  [11, prose net log]. Path: 64, 128, 256, 512, 768, 1024, 1280 (4.1), then 512 when threat
  inputs arrived, then 768 [11, prose net log].
- Further layers: count and widths: 32, then 32, then 1 [11, prose net log]. Before threat inputs: 16, 32, 1 [11, prose net log].
- Layer stacks (several copies of the head): count and what selects one: 8 copies of the head ("x8"); selector not stated [11, prose net log].
- Output buckets: count and what selects one (piece count, material, phase, queen presence, other): 8, added when the net was `(768hm->256)x2->1x8`: +12.66 +- 6.55
  STC [11, prose net log]. What selects one: not published.
- Skip connections, pairwise multiplication, other structure: pairwise
  multiplication of the accumulator ("pw") since 4.0 [11, prose net log] [12, release notes].

### Activations
- After the accumulator: pairwise multiplication; squared clipped ReLU before
  that [11, prose net log].
- In the head (dual activation, others): squared clipped ReLU after the first head layer and clipped ReLU
  after the second; the second was changed from squared to plain clipped ReLU
  when the head went integer, "to deal with the effects of quantization" [11, prose net log].
  Dual activation on the first head layer was tried and failed: -1.25 +- 3.97 at
  fixed nodes [11, prose net log].

### Quantisation
- Integer types per layer (int8, int16, float layers): the whole net runs in integers since the multi-layer
  net was merged, chosen so the bench is identical on every instruction set; the
  log lists three quantisation scales for the multi-layer nets and two for the
  single-layer ones [11, prose net log]. The first multi-layer attempt ran its last two layers
  in float [11, prose net log]. Bit widths per layer: not published.
- Quantisation-aware training or other rounding care: in the first head layer
  the squared activation is applied before the down-shift, and the shift is then
  twice as large, instead of shifting first: +2.62 +- 2.05 STC (idea credited to
  the author of Prune) [14, PR text].

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: "Finny tables", added with king buckets: +6.14 +-
  3.96 STC measured on the 4-bucket net [11, prose net log] [14, PR text].
- Lazy or deferred accumulator updates (computed only when an evaluation is needed; walked back along the stack): listed as a feature since 2.1; no figure
  [10, README].
- Fused updates (several feature changes applied in one pass; add-sub forms): not published.
- Accumulator stack (how accumulators are kept along the search path; copy avoidance): a refactor that stops doing the accumulator update work
  twice for the two perspectives: +8.16 +- 5.52 at 4+0.04 (non-regression
  bounds) [14, PR text].
- Pairwise multiplication of accumulator halves (as a way to halve the next layer's input): +4.21 +- 3.10 STC and +0.88 +-
  2.61 LTC (non-regression) at equal width 1024 [11, prose net log] [14, PR text].
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer (non-zero block iteration, neuron permutation for sparsity): the first head layer skips blocks of four inputs that
  are all zero; the net's neurons are permuted at build time so that non-zero
  blocks sit together; and a light regularisation of the accumulator's
  activations in training reduces how many are non-zero [11, prose net log] [14, PR text].
  Reported on AVX2, bench time against the dense version [14, PR text]:
  - sparse iteration alone: 1.04 times faster (153 of 256 blocks non-zero on
    average);
  - plus permutation: 1.08 times (118 of 256);
  - plus the regularised net: 1.12 times (82 of 256 before permuting, 71 after).
  In games on AVX-512: +13.04 +- 5.83 at 4+0.04 against main, and +7.32 +- 5.54
  (non-regression) against the old net permuted but not regularised [14, PR text].
  A later step uses AVX-512 VBMI2 compression to build the non-zero index list:
  +10.21 +- 5.35 at 4+0.04 (idea taken from a Stockfish pull request) [14, PR text].
- Evaluation cache (a hash table of network outputs, separate from the TT): not published.
- SIMD and VNNI work (AVX2, AVX-512, VNNI dot products, NEON; register tiling; anything about which instruction set won or lost):
  - AVX-512 against AVX2 on the single-layer net: +20.65 +- 7.74 STC [14, PR text];
  - after the dot-product loop was unrolled differently, the native VNNI dot
    product became faster than the multiply-add emulation on VNNI machines; the
    same change was slightly slower on AVX2 [14, PR text];
  - removing an unnecessary sum in the multi-layer path: +1.46 +- 2.63 at 4+0.04
    (non-regression; after 4.2.0) [14, PR text];
  - release notes warn that AVX-512 may be slower than AVX2 on older processors
    such as older Xeons, and that the BMI2 build can be slower on Zen 1 and 2
    [12, release notes].
- Memory layout and prefetching (alignment, huge pages, weight ordering, prefetch of rows or cache entries, net compression and file size): threat-input weight rows are prefetched: +1.93
  +- 1.55 at 4+0.04 [14, PR text]. Linux huge pages since 2.2 and NUMA thread
  pinning since 4.2; NUMA replication of the net is listed as not done
  [10, README]. Net file: 63,726,144 bytes [15, release asset metadata].
- Anything else that made the network faster: one commit in the multi-layer
  pull request is titled as a 4% speed-up, without saying how [14, PR text].
- Speed cost or gain reported for any architecture change:
  - threat inputs (accumulator cut from 1280 to 512, head widened to 32 -> 32):
    bench speed down about 36%; +47.25 +- 14.25 at fixed nodes, +13.23 +- 6.35
    STC, and +6.69 +- 4.30 STC on AVX2 [11, prose net log] [14, PR text];
  - multi-layer head: +28.13 (float) and +23.24 (integer, other things equal) at
    fixed nodes, -3.70 +- 4.64 STC, +6.60 +- 4.20 LTC; integer and float versions
    had "virtually no difference" in bench speed [11, prose net log] [14, PR text];
  - accumulator 1024 to 1280: +26.23 +- 9.99 at fixed nodes, +6.48 +- 4.11 LTC
    [11, prose net log].
- Hardware sensitivity reported (cache size, core count, a machine where a technique lost): the threat-input gain was about half as large
  on AVX2 as on the author's first test; the sparse layer and VBMI2 results were
  measured on AVX-512 [14, PR text].

### Training data
- Size (positions or games) of the rated net's data: 29.8 billion positions for the main stage (sets
  d8 to d17) and 28.3 billion for the fine-tune (d9 to d17) [11, prose net log].
- Type: own self-play / Lc0 or Lc0-relabelled / another engine's / mixed / unknown; and how the labels are made (search budget, relabelling, teacher): own self-play; every net since 3.0 trains on games played by earlier
  Raphael nets [10, README] [11, prose net log]. Labels come from a search with a soft node
  limit: 5,000 soft nodes for most sets, 24,000 for part (d14, d15, d18 and most
  of d17) [11, prose net log]. The very first set (about 200 M positions, rotated out long ago)
  was positions from earlier tests, public CCRL games and books re-evaluated by
  the hand-crafted Raphael 1.8 [11, prose net log].
- Openings, filtering, tablebase use: positions whose best move is noisy or
  where the side to move is in check are filtered out [11, prose net log]. Sets mix standard
  chess and DFRC (25% to 44% DFRC in the DFRC-bearing sets the rated net uses;
  two early sets were all DFRC) [11, prose net log]. The newest set
  in the rated net (d17, 55.34 M games, 5.0 B positions) mixes both node budgets,
  half of its low-budget part is DFRC, and about 6 M games start from an endgame
  book [11, prose net log]. Old sets are dropped as new ones arrive [11, prose net log]. Tablebase use: not
  published.
  Data-generation notes from the log [11, prose net log] [14, PR text]:
  - its own generator is 23% faster than OpenBench's;
  - games no longer share the TT and history tables: +5.78 +- 5.85 at fixed
    nodes against OpenBench data; with sharing, -3.77 +- 2.80;
  - training on all sets beat training on the newest set alone (the newest-only
    net was -7.98 +- 6.71);
  - a branch tuned by SPSA at the higher node budget was 42 Elo stronger at the
    low budget and 107 at the high one, but cost too much time per position and
    was dropped.

### Training recipe (concepts only)
- Trainer: bullet, since the second net; a custom PyTorch trainer for the first
  [10, README] [11, prose net log].
- Loss and target (result blend, as a concept): a blend of search score and game result whose result share
  ramps up linearly during the main stage: +5.41 +- 3.86 STC against a constant
  share [11, prose net log]. A steeper ramp lost: -8.48 +- 6.63 STC [11, prose net log].
- Stages and schedule (warm start, fine-tunes, weight averaging): a main stage with warm-up and cosine decay of the learning
  rate, then a shorter fine-tune on the newer sets with a constant, higher result
  share and a low, linearly decaying learning rate [11, prose net log]. Gains: fine-tune stage
  +18.29 +- 7.52 STC; a longer fine-tune +3.47 STC and +1.89 LTC; linear instead
  of constant learning rate in it +4.83 STC; a higher result share in it +3.53
  STC. Cosine decay in the fine-tune was neutral, and a result ramp in the
  fine-tune lost (-1.63 STC, -4.57 LTC) [11, prose net log].
- Regularisation, optimiser, anything unusual: AdamW [11, prose net log]. Random position
  skipping: +2.36 +- 1.87 STC [11, prose net log]. An eight times larger batch with as many
  fewer batches per epoch was neutral (+0.32 +- 2.97 at fixed nodes,
  non-regression) and shortened training to about five hours on a laptop GPU
  [11, prose net log]. Skipping positions to match a target piece-count distribution failed:
  -2.65 +- 3.93 LTC (+1.23 STC) [11, prose net log]. The output scale of each net is
  recalibrated against a fixed reference [11, prose net log].

### Measured gains for network changes
- First bullet net on own self-play (615 M positions): +155.84 +- 23.70 STC [11, prose net log].
- Mirroring: +16.51 STC [11, prose net log].
- Accumulator widths, single layer: 128 +59.33; 256 with more data +82.63; 512
  +18.14; 768 +15.73; 1024 +6.59 (all STC) [11, prose net log].
- DFRC games added to the data: +16.03 +- 7.49 STC in standard chess, +121.70 in
  DFRC [11, prose net log].
- Output buckets: +12.66 STC [11, prose net log].
- King buckets: see Inputs.
- More data at the higher node budget (19.7 B total): +7.77 +- 4.66 STC [11, prose net log].
- More data and old sets dropped (25.8 B): +3.72 +- 2.87 at fixed nodes [11, prose net log].
- Threat-input net widened from 512 to 768, with one more data set: +17.97 +-
  7.54 STC [11, prose net log] [14, PR text].
- 4.2 against 4.1 (whole release): +57 STC, +75 LTC [12, release notes].

### Architecture history
- 2.0 (2025-12): `(768->64)x2->1`, squared clipped ReLU, own PyTorch trainer [11, prose net log].
- 3.1 (2026-03): `(768hm->768)x2->1x8`, bullet [11, prose net log] [10, README].
- 3.2 (2026-03): `(768x4hm->1024)x2->1x8`, refresh cache [11, prose net log].
- 3.3 (2026-04): `(768x16hm->1024)x2->1x8`, fine-tune stage [11, prose net log].
- 4.0 (2026-04): `(768x16hm->1024pw)x2->1x8` [11, prose net log].
- 4.1 (2026-05): `(768x16hm->1280pw)x2->(16->32->1)x8`, sparse first head layer
  [11, prose net log] [12, release notes].
- 4.2 (2026-06-27): `((768x16+60144)hm->768pw)x2->(32->32->1)x8` [11, prose net log] [12, release notes].

### Since the rated version
- 2026-07-02: accumulator 768 to 1024 with one more data set (32.0 B main stage):
  +7.86 +- 4.22 LTC [11, prose net log] [14, PR text].
- 2026-07-25: the unnecessary-sum removal above [14, PR text].
- The README still lists dual activations, pawn-pair inputs and
  relabelling or distillation as not done [10, README].

### UNVERIFIED and not published
- What a threat input encodes and how threat accumulators are updated: only in
  code.
- The output-bucket selector; the mirroring trigger; how the bucket layout was
  chosen: not published.
- Bit widths per layer; int8 rows; fused updates; an evaluation cache: not
  published.
- Row order of the bucket table: my reading.
- Tablebase use in data generation: not published (the log mentions a tablebase
  blunder rate as a data-quality check, nothing more).
- The log writes "around 30m pos" for the low-budget part of set d17; whether it
  means games or positions is unclear.

---
## RubiChess 20240817 (CCRL #24-26, 3727)

**One-line architecture:** assembled, and incomplete: a Stockfish-style net on the
HalfKAv2_hm feature set, described by the author as "512x32x32x1 ... besides the
smaller input layer identical to SFv5" for the first net of this family, with the
first layer later widened to 768 and then 1024 [19, README]. The width of the
rated net (nn-bc638d5ec9-20240730) is not restated; 1024 is the last width the
author gives. UNVERIFIED (not published for this net).

### Inputs
- Feature set (what an input means; inputs per perspective if stated): HalfKAv2_hm, Stockfish's king-relative piece-square set with
  horizontal mirroring, since the net of 2022-08-31 [19, README]. The trainer's
  documentation describes it as HalfKAv2 with the board mirrored per perspective
  so that the own king is always on one half of the files, halving the feature
  transformer [26, trainer docs]. Inputs per perspective: not published by
  RubiChess.
- King input buckets: count; layout (which king squares share a bucket, in words); how the layout was chosen or grown: the feature set is indexed by the king square itself
  (each mirrored king square has its own block) (my reading of "HalfKA"); no
  coarser bucket layout is published.
- Horizontal mirroring (when the king crosses the middle, or other): yes, per perspective, by the own king's file half
  [26, trainer docs].
- Threat or attack inputs (what relation they encode; how many; how they are updated): none in the rated version. Added after it (see
  "Since the rated version").
- Pawn features (pawn pairs, passed pawns, other): none published.
- Other input relationships (material or queen routing, pins, mobility, side-to-move, castling, anything else): none published. Old versions switched to the
  hand-crafted evaluation for one-sided material (2.0) and scaled the network
  output by game phase (2021) [18, changelog].
- Factoriser or other training-only input structure: the author's label for the
  feature set ends in "^", the trainer's mark for a factorised set (my reading);
  not otherwise published.

### Body
- First hidden layer (accumulator) width per perspective: 512 (2022-08), 768
  (2023-01), 1024 (2023-06, trained from scratch) [19, README]. For the rated
  net: UNVERIFIED (not restated; last stated 1024). The engine can also load
  2560-wide nets since October 2023 [23, PR text].
- Further layers: count and widths: "x32x32x1" in the author's string for the 2022 net [19, README]. The
  author says the layout is Stockfish's "SFv5" [19, README]; the trainer's history page
  gives that architecture only as a diagram, and says the next one differs from
  it only by a first layer of 1536 instead of 1024 [26, trainer docs].
- Layer stacks (several copies of the head): count and what selects one: UNVERIFIED (only in the diagram and in code). The trainer
  documentation describes, in general, 8 layer stacks chosen by piece count
  [26, trainer docs]; whether RubiChess's nets use them is not stated in RubiChess's prose.
- Output buckets: count and what selects one (piece count, material, phase, queen presence, other): UNVERIFIED (same reason).
- Skip connections, pairwise multiplication, other structure: not published.

### Activations
- After the accumulator: not published.
- In the head (dual activation, others): not published.

### Quantisation
- Integer types per layer (int8, int16, float layers): not published. Net files are stored LEB128-compressed
  since 2023-09 and could be zlib-compressed since 2022-11 [18, changelog].
- Quantisation-aware training or other rounding care: the last layer is rescaled
  after training by a factor a little below one, which gained about 2 to 6 Elo
  each of the four times it is logged (2021-2022) [19, README].

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: "Finny tables", April 2024: +7.52 +- 5.16 at 10+0.1
  and +5.43 +- 4.37 at 60+0.6 [23, PR text] [18, changelog]. Before it, a wiki
  note of 2023-03 counted 65.0% incremental updates, 34.9% full refreshes and
  0.1% "cached" [21, wiki].
- Lazy or deferred accumulator updates (computed only when an evaluation is needed; walked back along the stack): not published under that name. Related
  items: 2.1 uses differential updates over several plies as long as they cost
  less than a full update [18, changelog]; October 2023 adds a "speculative"
  accumulator update for nodes likely to have many children, so that the
  children can update incrementally ("some more speed", no figure) [23, PR text].
- Fused updates (several feature changes applied in one pass; add-sub forms): not published.
- Accumulator stack (how accumulators are kept along the search path; copy avoidance): a merged-accumulators change landed in October 2026, after
  the rated version; no description [23, PR text].
- Pairwise multiplication of accumulator halves (as a way to halve the next layer's input): not published.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer (non-zero block iteration, neuron permutation for sparsity): June 2023: propagation of the sparse first layer,
  "invented by AndrovT for Stockfish", with the net's neurons sorted by
  activation probability (statistics from a deep search of the start position).
  Speed "from almost identical to about 8% faster depending on the CPU"
  [23, PR text] [19, README].
- Evaluation cache (a hash table of network outputs, separate from the TT): not published.
- SIMD and VNNI work (AVX2, AVX-512, VNNI dot products, NEON; register tiling; anything about which instruction set won or lost): builds from SSE2 to AVX-512, ARM NEON and (since 2024-01)
  ARMv8.2 dot product [17, README] [18, changelog]. The AVX-512 build was cut to
  16 registers because a tester reported it faster (October 2023) [23, PR text].
  2022-08: 1 to 3% faster on x86 and over 10% on ARM [18, changelog]. The author recommends
  Intel's icx compiler, then clang, over gcc for speed [17, README].
- Memory layout and prefetching (alignment, huge pages, weight ordering, prefetch of rows or cache entries, net compression and file size): large pages on Windows since 2.0 [18, changelog]. Net
  compression as above. File size: not published.
- Anything else that made the network faster: fixing a long-standing bug (an
  opponent king move needlessly broke the incremental update) gained about 7%
  speed in the start position [23, PR text]. A later feature-transformer
  speed-up branch was closed as "a lot of code for a questionable speedup"
  [23, PR text].
- Speed cost or gain reported for any architecture change: first layer 512 to
  768 (2023-01): +35 Elo at fixed nodes but only +6 to +8 at STC and LTC, "from
  the lower speed of this network" [19, README]. 768 to 1024 from scratch
  (2023-06): +0.63 +- 1.30 at 10+0.1 (the test failed) and +5.45 +- 3.58 at
  60+0.6; "expected a little more" [23, PR text] [19, README].
- Hardware sensitivity reported (cache size, core count, a machine where a technique lost): the sparse layer's gain depends on the CPU; the
  16-register AVX-512 report came from one tester's machine [23, PR text].

### Training data
- Size (positions or games) of the rated net's data: 55 GB of binpack files; against the previous
  training the oldest 13 GB were replaced by 26 GB of new data [19, README]
  [23, PR text]. Positions: not published for this net (earlier nets: 12.5
  billion in 2022-08, 14 billion in 2022-10) [19, README].
- Type: own self-play / Lc0 or Lc0-relabelled / another engine's / mixed / unknown; and how the labels are made (search budget, relabelling, teacher): own games only, generated by RubiChess on one server running since 2020;
  the generating version is switched to the current one every two or three
  months [21, wiki] [24, TCEC]. Labels are fixed-depth searches: depth 6 to 13
  in 2020-2021, depth 9 with pruning disabled for the sets of 2022 [19, README]. Depth
  for the newest sets: not published. The chain started from the hand-crafted
  evaluation, then each net labelled the next data [19, README] [18, changelog].
- Openings, filtering, tablebase use: games start from several opening books
  such as Stefan Pohl's UHO (2022) [18, changelog]. Six-man tablebases were used
  in early generations; a late-2022 set was made without tablebases [19, README]. Data
  is shuffled across generations, and the oldest quarter was rotated out in 2023
  [19, README].

### Training recipe (concepts only)
- Trainer: an old fork (March 2023) of Stockfish's nnue-pytorch, slightly
  modified [24, TCEC]. Earlier: the Stockfish learner binary and the
  Nodchip/Sergio Vieri trainer [19, README].
- Loss and target (result blend, as a concept): a blend of search score and game result; the author tried
  several blend values and switched the blend late in training [19, README].
- Stages and schedule (warm start, fine-tunes, weight averaging): the rated net was trained from scratch for 400 epochs;
  three checkpoints in a row passed tests (epoch 319: +9.10 STC, +3.04 LTC
  against master; epoch 339: +4.93, +3.06; epoch 399: +2.49, +4.55, each against
  the one before) [23, PR text]. Earlier nets were continued from the previous
  net's checkpoint; every epoch's net was pre-tested, not only the ones with
  lower loss [18, changelog] [19, README].
- Regularisation, optimiser, anything unusual: the 1024-wide net of 2023 took
  ten days on a GTX 1050 Ti [19, README]. Not otherwise published.

### Measured gains for network changes
- First NNUE net against the hand-crafted evaluation (2020-10): +95 +- 25 [19, README].
- Rescaling the last layer: +2 to +6 each time [19, README].
- 768-wide first layer: +35 fixed nodes, +6 to +8 on the clock [19, README].
- 1024-wide first layer: +0.63 STC (failed), +5.45 +- 3.58 LTC [23, PR text].
- Refresh cache: +7.52 STC, +5.43 LTC [23, PR text].
- 20240817 against 20240112 (whole release): "about +30 Elo" [20, release notes].

### Architecture history
- 1.9 (2020-11): Stockfish's original net format supported; nets trained on own
  data labelled by the hand-crafted evaluation [18, changelog] [19, README].
- 20221120: new architecture (HalfKAv2_hm, 512-wide), 14 billion positions
  [18, changelog] [19, README].
- 2023-01: 768-wide; 2023-06: 1024-wide from scratch, neurons sorted for the
  sparse layer [19, README].
- 20230918: several architectures and input sizes loadable; compressed nets [18, changelog].
- 20240817: net bc638d5ec9, from scratch on 55 GB; refresh cache [18, changelog] [19, README].

### Since the rated version
- 2025-01: the net's last layer tuned by SPSA: +1.93 +- 2.17 at 60+0.6
  [23, PR text] [19, README].
- 2025-05 to 2025-11: further nets on nearly the same data; the notes say
  "seems to gain 5-10 Elo" for one and "maybe 3 Elo" for the next [19, README] [23, PR text].
- 2026-08: threat features and a net in Stockfish's "SFNNv13" architecture: +44.36
  +- 11.14 at 60+0.6 against master, then +9.64 +- 4.36 for a longer-trained net
  [23, PR text] [19, README]. The trainer's documentation says threat inputs encode
  "piece A attacks piece B" pairs with redundant pairs removed, are mirrored like
  the piece inputs, and are stored as 8-bit weights [26, trainer docs].
- 2026-10: a net on newly generated data [19, README].

### UNVERIFIED and not published
- The rated net's first-layer width, head sizes, layer stacks, output buckets,
  activations and integer types: stated only through the reference to
  Stockfish's "SFv5", whose details are in a diagram and in code.
- That the feature set is indexed by exact king square, and the meaning of the
  "^" mark: my reading.
- Positions in the 55 GB set; label depth of the newest sets: not published.
- Lazy updates, fused updates, pairwise multiplication, int8 rows, evaluation
  cache: not published.

---

## Starzix 6.0 (CCRL #24-26, 3727)

**One-line architecture:** `(768x2x5 -> 1024)x2 -> 1`, as the README at the 6.0
tag writes it [27, README].

### Inputs
- Feature set (what an input means; inputs per perspective if stated): 768 piece-square inputs, times 2, times 5 [27, README]. The README
  lists two properties beside the string: inputs mirrored along the vertical axis
  by king square, and 5 enemy-queen input buckets [27, README]. That the "x2" is the
  mirror state and the "x5" the queen buckets is my reading.
- King input buckets: count; layout (which king squares share a bucket, in words); how the layout was chosen or grown: none published (the only king dependence stated is the
  mirror).
- Horizontal mirroring (when the king crosses the middle, or other): yes, "based on king square" [27, README]; merged
  2024-07-25 [30, PR text]. The exact trigger: not published.
- Threat or attack inputs (what relation they encode; how many; how they are updated): none published.
- Pawn features (pawn pairs, passed pawns, other): none published.
- Other input relationships (material or queen routing, pins, mobility, side-to-move, castling, anything else): 5 input buckets chosen by the enemy queen
  [27, README], merged 2024-08-01 [30, PR text]. What about the enemy queen
  selects a bucket (its presence, count or square): not published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 1024 [27, README].
- Further layers: count and widths: none; the accumulators feed one output [27, README].
- Layer stacks (several copies of the head): count and what selects one: none published.
- Output buckets: count and what selects one (piece count, material, phase, queen presence, other): none (the string ends in "-> 1") [27, README].
- Skip connections, pairwise multiplication, other structure: not published.

### Activations
- After the accumulator: squared clipped ReLU in 4.0 [27, README at 4.0]; not
  restated for 6.0.
- In the head (dual activation, others): no head.

### Quantisation
- Integer types per layer (int8, int16, float layers): not published.
- Quantisation-aware training or other rounding care: not published. The
  trainer's README says its export step "optionally quantizes" [31, README].

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: "Finny tables", merged 2024-08-06, no description
  and no figure [30, PR text].
- Lazy or deferred accumulator updates (computed only when an evaluation is needed; walked back along the stack): not published.
- Fused updates (several feature changes applied in one pass; add-sub forms): not published.
- Accumulator stack (how accumulators are kept along the search path; copy avoidance): not published.
- Pairwise multiplication of accumulator halves (as a way to halve the next layer's input): not published.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer (non-zero block iteration, neuron permutation for sparsity): not applicable (no dense head).
- Evaluation cache (a hash table of network outputs, separate from the TT): not published.
- SIMD and VNNI work (AVX2, AVX-512, VNNI dot products, NEON; register tiling; anything about which instruction set won or lost): a pull request titled "Original SIMD" (2024-07-30), no
  description [30, PR text]. Release notes: AVX2 is the recommended binary,
  AVX-512 the fastest [28, release notes].
- Memory layout and prefetching (alignment, huge pages, weight ordering, prefetch of rows or cache entries, net compression and file size): not published.
- Anything else that made the network faster: a pull request titled "Speedup" (2024-07-24) without a
  description [30, PR text].
- Speed cost or gain reported for any architecture change: none reported.
- Hardware sensitivity reported (cache size, core count, a machine where a technique lost): none reported.

### Training data
- Size (positions or games) of the rated net's data: not published for 6.0.
- Type: own self-play / Lc0 or Lc0-relabelled / another engine's / mixed / unknown; and how the labels are made (search budget, relabelling, teacher): Lc0 data [27, README]. How the labels are used (Lc0's own values or
  others): not published for 6.0.
- Openings, filtering, tablebase use: not published.

### Training recipe (concepts only)
- Trainer: the author's own trainer ("nn-trainer" in the 6.0 README, which now
  returns 404; "Starway" in the 6.1 README) [27, README] [31, README].
- Loss and target (result blend, as a concept): a power loss with an exponent above two instead of squared
  error, merged 2024-07-05 (title only) [30, PR text].
- Stages and schedule (warm start, fine-tunes, weight averaging): not published.
- Regularisation, optimiser, anything unusual: mixed-precision training
  (bfloat16), merged 2024-07-02 (title only) [30, PR text].

### Measured gains for network changes
- None published. Starzix's pull requests carry bench counts only [30, PR text]. Whole
  release: 6.0 against 5.0, +105.1 +- 7.4 at 10+0.1 and +132.9 +- 16.1 at 60+0.6
  [28, release notes].

### Architecture history
- 3.0 (2023-11): `768->384x2->1` [27, README at 3.0].
- 4.0 (2024-01): `(768->512)x2->1`, Lc0 data, squared clipped ReLU [27, README].
- 5.0 (2024-05): `(768->1024)x2->1`, own trainer [27, README] [28, release notes].
- 2024-07-25: mirrored net; 2024-08-01: 5 enemy-queen buckets; 2024-08-06:
  refresh cache [30, PR text].
- 6.0 (2024-10-24): `(768x2x5 -> 1024)x2 -> 1` [27, README] [28, release notes].

### Since the rated version
- 6.1 (2025-04-06): fixes for TCEC, "equal strength as 6.0", same net string
  [28, release notes] [27, README].
- 2025-02: the engine was rewritten; the same net was re-added on 2025-02-07
  [30, PR text].
- 2025-03-11: a new net on "leela data relabeled with Stockfish net (static
  eval)" (title only) [30, PR text].
- 2025-04-24: one more input bucket and more data, "5 billion total" (title
  only) [30, PR text].
- 2025-04-26: accumulator 1024 to 1536 [30, PR text]. The README now reads
  `(768x2x6 -> 1536)x2 -> 1`, mirrored, on Lc0 data [27, README at HEAD].
- The trainer's README credits the Monty project for training data and names
  another engine of the author's as its user [31, README].

### UNVERIFIED and not published
- What selects an enemy-queen bucket; the mirror trigger; the reading of "x2x5":
  not published or my reading.
- Activation, integer types, data size, label source within the Lc0 data,
  filtering: not published for 6.0.
- Every speed technique except the names "Finny tables" and "SIMD": not
  published; no gain figure for any network change.
- No TCEC questionnaire for Starzix is in the wiki's questionnaire category
  [54, TCEC].

---

## Tarnished 6.0 "Eternal" (CCRL #24-26, 3727)

**One-line architecture:** `(768x16hm->1792)x2->(16->32->32)x8`, as the README and
the 6.0 release notes write it [32, README] [33, release notes]. The net-repository
entry for the same net (Lichdragon 3) writes `(768x16hm->1792)x2->(16->32->1)x8`
[34, release notes]. That the README's middle "32" is the 16 outputs doubled by the
dual activation is my reading.

### Inputs
- Feature set (what an input means; inputs per perspective if stated): (piece, square, colour) inputs, 768 per king bucket [32, README].
- King input buckets: count; layout (which king squares share a bucket, in words); how the layout was chosen or grown: 16, mirrored. The published 8-by-8 table is symmetric
  left to right; on the four files of one half: the first and second rows give
  every file its own bucket (8 buckets); the third and fourth rows share four
  buckets, one per file; the fifth and sixth rows share two buckets (the two
  outer files, the two inner files), and so do the seventh and eighth
  [34, release notes]. That the first row is the own back rank is my reading.
  How it grew, all at 40+0.4 [36, PR text]:
  - 4 buckets, 2025-08: +8.84 +- 4.04;
  - 6 buckets, 2025-10: +11.37 +- 4.59;
  - 8 buckets against master: +26.70 +- 7.20, with a new 16-billion-position
    data set;
  - 12 against 8: +15.77 +- 5.40;
  - 16, no new data: +4.97 +- 2.87.
  How the layout was chosen: not published.
- Horizontal mirroring (when the king crosses the middle, or other): yes: +28.23 +- 7.35 at 40+0.4 (2025-08) [36, PR text].
  Trigger: not published.
- Threat or attack inputs (what relation they encode; how many; how they are updated): none.
- Pawn features (pawn pairs, passed pawns, other): none.
- Other input relationships (material or queen routing, pins, mobility, side-to-move, castling, anything else): none published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 1792 [32, README]. Path: 128,
  512, 1024, 1280, 1536, 1792 [33, release notes] [34, release notes] [36, PR text].
- Further layers: count and widths: 16, then 32, then one output [34, release notes]; see the note
  on the README's string above.
- Layer stacks (several copies of the head): count and what selects one: 8 copies of the head; selector not stated [32, README].
- Output buckets: count and what selects one (piece count, material, phase, queen presence, other): 8 [32, README]. What selects one: not published.
- Skip connections, pairwise multiplication, other structure: not published. The
  multi-layer inference is "heavily based off Alexandria" [36, PR text]
  [32, README].

### Activations
- After the accumulator: squared clipped ReLU in 2.0 [33, release notes]; not
  restated for the multi-layer nets.
- In the head (dual activation, others): dual activation, added 2026-02-22: +3.50 +- 2.48 LTC
  [36, PR text] [32, README]. Which two activations: not published.

### Quantisation
- Integer types per layer (int8, int16, float layers): not published.
- Quantisation-aware training or other rounding care: not published.

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: "Finny tables": +5.80 +- 3.19 at 8+0.08 [36, PR
  text]. The day before, removing redundant updates inside the refresh: +9.34 +-
  4.18 at 8+0.08 [36, PR text].
- Lazy or deferred accumulator updates (computed only when an evaluation is needed; walked back along the stack): the accumulator is updated only when it
  is needed: +14.69 +- 5.31 at 8+0.08 [36, PR text].
- Fused updates (several feature changes applied in one pass; add-sub forms): a fused accumulator refresh, with SIMD for the add, add-sub and
  similar update forms: +2.83 +- 2.05 at 4+0.04 [36, PR text].
- Accumulator stack (how accumulators are kept along the search path; copy avoidance): +28.53 +- 10.27 at 8+0.08 (non-regression bounds; June
  2025, on the 512-wide net) [36, PR text].
- Pairwise multiplication of accumulator halves (as a way to halve the next layer's input): not published.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer (non-zero block iteration, neuron permutation for sparsity): not published.
- Evaluation cache (a hash table of network outputs, separate from the TT): not published.
- SIMD and VNNI work (AVX2, AVX-512, VNNI dot products, NEON; register tiling; anything about which instruction set won or lost): 2.0 vectorised inference with "the Lizard SCReLU trick"
  "for a notable speed boost" [33, release notes]. AVX-512 needed aligned biases
  [36, PR title]. A POWER9 SIMD path exists because the author's university
  cluster is PowerPC; it is the only part written with AI help [38, TCEC].
- Memory layout and prefetching (alignment, huge pages, weight ordering, prefetch of rows or cache entries, net compression and file size): the net is embedded with incbin [32, README]. Net file
  (Lichdragon 3): 44,308,512 bytes [34, release asset metadata].
- Anything else that made the network faster: in 2.0 the accumulator was refreshed only for promotions and en
  passant captures, to be improved later [33, release notes].
- Speed cost or gain reported for any architecture change: not reported as speed; the
  Elo of each widening is under "Measured gains".
- Hardware sensitivity reported (cache size, core count, a machine where a technique lost): the fine-tune tests of 2025-11 were all run on an AVX-512
  cluster [36, PR text]. Nothing else reported.

### Training data
- Size (positions or games) of the rated net's data: about 22 billion positions [32, README] [33, release notes].
- Type: own self-play / Lc0 or Lc0-relabelled / another engine's / mixed / unknown; and how the labels are made (search budget, relabelling, teacher): own self-play from a random net [32, README] [33, release notes]; "all data is completely self
  generated" [38, TCEC]. Games are played at 5,000 or 20,000 soft nodes
  [32, README]. The whole set was then relabelled by a much larger net,
  `(768x8hm->4096)x2->(96->192->192->1)x8` [32, README] [33, release notes]; first relabelled net +3.24
  and +3.02 LTC, second +4.07 LTC [36, PR text]. Where the teacher net came from
  (which data it was trained on): not published.
- Openings, filtering, tablebase use: 8 random plies for the opening [32, README]; 10%
  of generated start positions are DFRC since 2025-10 [36, PR text]. Filtering
  and tablebase use: not published (the first net's note distinguishes about 1
  billion unfiltered from about 650 million filtered positions [36, PR text]).

### Training recipe (concepts only)
- Trainer: bullet [32, README] [38, TCEC].
- Loss and target (result blend, as a concept): a result weight raised in the final stage: a higher fine-tune
  weight gained +7.16 +- 3.59 LTC (2025-10) and +3.87 +- 2.76 LTC (2025-11)
  [36, PR text].
- Stages and schedule (warm start, fine-tunes, weight averaging): a main stage, a fine-tune, and a last "refine" stage
  [36, PR text]. Reported at LTC on AVX-512 (2025-11) [36, PR text]:
  - a fine-tune twice as long: +3.78 +- 2.87;
  - a longer main stage: +1.73 +- 1.37;
  - the refine stage run on a smaller mixed set (20,000-node standard games,
    5,000-node standard games and 5,000-node DFRC games): +6.55 +- 3.46;
  - the same without the 5,000-node standard games: +6.94 +- 3.44;
  - on the 20,000-node standard games alone: +4.2 +- 2.85.
- Regularisation, optimiser, anything unusual: not published. Data generation
  and training ran on the author's university cluster [32, README].

### Measured gains for network changes
- 512-wide net on about 1 billion positions: +91.96 +- 15.98 at 8+0.08 [36, PR text].
- 1024-wide: +5.83 +- 3.96 at 40+0.4, and +10.41 +- 5.60 at 30+0.3 after a
  fine-tune [36, PR text].
- Mirroring, king buckets: see Inputs.
- A new net in 2025-09 (no description): +4.54 +- 2.76 LTC [36, PR text].
- 1280-wide: +4.76 +- 2.79 LTC; 1536-wide with a new schedule: +9.43 +- 3.80
  LTC (local test) [36, PR text].
- Relabelling by the large teacher: +3.24, +3.02, +4.07 LTC [36, PR text].
- Multi-layer head `(768x16hm->1536)x2->(16->32->1)x8`: +20.71 +- 2.57 LTC [36, PR text].
- Dual activation: +3.50 LTC [36, PR text].
- 1792-wide: +2.74 +- 1.92 LTC; two retrains: about +3 and +8.31 +- 2.46 LTC
  [36, PR text].
- 6.0 against 5.0 (whole release): "+32 elo" [33, release notes].

### Architecture history
- 2.0 (2025-05): `(768->128)x2->1x8`, squared clipped ReLU, random start,
  5,000 soft nodes [33, release notes].
- 2.1: `(768->512)x2->1x8`, about 650 M positions [33, release notes].
- 3.0 (2025-06): `(768->1024)x2->1x8`, about 1.7 B [33, release notes].
- 2025-08: mirrored `(768x1hm->1024)x2->1x8` [34, release notes].
- 4.0 (2025-08): `(768x4hm->1024)x2->1x8`, about 3.5 B [33, release notes].
- 2025-10: 6, 12 and 16 buckets; 1280-wide [34, release notes] [36, PR text].
- 2025-12: 1536-wide [34, release notes].
- 5.0 (2026-02): `(768x16hm->1536)x2->1x8`, about 22 B, relabelled [33, release notes].
- 2026-02-21: multi-layer head; 2026-02-22: dual activation; 2026-02-25:
  1792-wide [34, release notes] [36, PR text].
- 6.0 (2026-06-10): the Lichdragon 3 net of 2026-03-19; the bench count in the
  6.0 commit equals that net's [37, commit text] [36, PR text].

### Since the rated version
- Nothing network-related: one pull request (a UCI option) since 6.0
  [37, commit text]. The 6.0 notes say it "may be the final release"
  [33, release notes].

### UNVERIFIED and not published
- The reconciliation of `(16->32->32)x8` and `(16->32->1)x8`: my reading.
- The teacher net's own training data: not published.
- The output-bucket selector, mirror trigger, how the bucket layout was chosen,
  which activations the dual activation pairs: not published.
- Integer types, quantisation care, pairwise multiplication, sparse layer,
  evaluation cache: not published.
- Filtering rules and tablebase use: not published.
- Row order of the bucket table: my reading.

---
## Clover 9.1 (CCRL #27, 3725)

**One-line architecture:** assembled from release notes and pull-request titles,
and incomplete: 768 piece-square inputs in 7 king buckets, one hidden layer last
stated as 1280 wide with squared clipped ReLU, trained with an input-bucket
factoriser [40, release notes] [42, PR text]. The author publishes no architecture
string for 9.x; output buckets and mirroring are not stated. UNVERIFIED in those
parts.

### Inputs
- Feature set (what an input means; inputs per perspective if stated): piece-square inputs per king bucket. The last full string the
  author published is `4x768 - 2x768 - 1` for 3.3 (2023), where every input is
  mapped through a king-position table [40, release notes]. Inputs per
  perspective in 9.1: not published.
- King input buckets: count; layout (which king squares share a bucket, in words); how the layout was chosen or grown: 7 in 9.1. History: a king-position table in 3.3; 5 buckets
  in 4.1 ("gained pretty nice, 15-20 Elo"); 7 buckets in 8.0, a "scheme
  eye-balled based on the distribution of the king square"; a smaller 4-bucket
  net was merged on 2025-08-04 and the "original 7 buckets scheme" restored a
  week later, after the data grew and the factoriser was added
  [40, release notes] [42, PR text]. Which squares share a bucket: not published
  in prose (the 3.3 note prints a table as a code block, which I did not read).
- Horizontal mirroring (when the king crosses the middle, or other): 3.3 flipped the board so that the own king is on the
  queen side [40, release notes]. Whether 9.1 still does: not published.
- Threat or attack inputs (what relation they encode; how many; how they are updated): none published.
- Pawn features (pawn pairs, passed pawns, other): none published.
- Other input relationships (material or queen routing, pins, mobility, side-to-move, castling, anything else): none published.
- Factoriser or other training-only input structure: an input-bucket
  factoriser, new in 9.0 [40, release notes] [42, PR text].

### Body
- First hidden layer (accumulator) width per perspective: 256 (3.0), 512 (3.1),
  768 (3.3), 1024 (6.0), 1280 (7.0) [40, release notes]. The 4-bucket net of
  2025-08-04 is titled "1280hl" [42, PR text]; the width of the 9.1 net is not restated.
  UNVERIFIED (last stated 1280).
- Further layers: count and widths: none published. The author told TCEC the "NNUE arch isn't at
  all interesting" [45, TCEC].
- Layer stacks (several copies of the head): count and what selects one: not published.
- Output buckets: count and what selects one (piece count, material, phase, queen presence, other): not published.
- Skip connections, pairwise multiplication, other structure: not published.

### Activations
- After the accumulator: squared clipped ReLU since 7.0, plain ReLU before
  [40, release notes].
- In the head (dual activation, others): not published.

### Quantisation
- Integer types per layer (int8, int16, float layers): not published.
- Quantisation-aware training or other rounding care: not published.

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: not published.
- Lazy or deferred accumulator updates (computed only when an evaluation is needed; walked back along the stack): not published.
- Fused updates (several feature changes applied in one pass; add-sub forms): a pull request titled "Fuse loops" from a network branch was
  merged on 2025-08-29, without a description or a figure [42, PR text].
- Accumulator stack (how accumulators are kept along the search path; copy avoidance): not published.
- Pairwise multiplication of accumulator halves (as a way to halve the next layer's input): not published.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer (non-zero block iteration, neuron permutation for sparsity): not published.
- Evaluation cache (a hash table of network outputs, separate from the TT): not published.
- SIMD and VNNI work (AVX2, AVX-512, VNNI dot products, NEON; register tiling; anything about which instruction set won or lost): three builds (old, AVX2, AVX-512), AVX-512 "the fastest"
  [39, README] [40, release notes]. 3.1: about half of that release's +200 Elo
  came from SIMD code [40, release notes].
- Memory layout and prefetching (alignment, huge pages, weight ordering, prefetch of rows or cache entries, net compression and file size): the net is used verbatim since 2025-07 (title
  only) [42, PR text]. File size: not published.
- Anything else that made the network faster: PGO builds were removed as "worthless" (2024-11) [41, PR title].
- Speed cost or gain reported for any architecture change: none reported.
- Hardware sensitivity reported (cache size, core count, a machine where a technique lost): none reported.

### Training data
- Size (positions or games) of the rated net's data: not published for the 9.1 net. The first 9.0-cycle net was trained on
  about 2.7 billion unfiltered positions, published on Kaggle; later nets added
  "more data" without a count [42, PR text].
- Type: own self-play / Lc0 or Lc0-relabelled / another engine's / mixed / unknown; and how the labels are made (search budget, relabelling, teacher): own self-play [45, TCEC]. Labels come from searches with a minimum node
  count of 5,000 or 20,000 per move [40, release notes]. The 9.1 net was trained
  on the 20,000-node data only (neutral against the previous net), then
  retrained further [42, PR text].
- Openings, filtering, tablebase use: about half standard chess and half DFRC in
  9.0, against all-DFRC data before; the author expects 9.0 to be a little
  weaker in DFRC for it [40, release notes]. Data-generation changes of July
  2025, titles only: games whose opening score is too high are not stored; early
  adjudication; the two players of a game search independently; the TT is
  refreshed for each game [42, PR text] [43, commit text]. Data is written in
  Viridithas's binpack format since 2025-05 [42, PR text]. Tablebase use: not published.

### Training recipe (concepts only)
- Trainer: bullet now; the author's own trainer first, CudAD from 4.0
  [45, TCEC] [40, release notes] [39, README].
- Loss and target (result blend, as a concept): a blend of score and result. In the 9.0 cycle one net was
  trained at a lower result weight, then retrained at a higher one; the 9.1 net
  ends with a retrain whose result weight ramps up linearly [42, PR text].
- Stages and schedule (warm start, fine-tunes, weight averaging): a main run, then extra retraining at a lowered learning
  rate; cosine learning-rate decay since 2024-09 [42, PR text].
- Regularisation, optimiser, anything unusual: not published.

### Measured gains for network changes
- No per-net test results are published; Clover's pull requests have no
  descriptions [42, PR text]. Release-level figures [40, release notes]:
  - 4.0, same architecture, CudAD instead of the own trainer: "80-100-120 elo";
  - 4.1, 5 king buckets: 15 to 20 Elo;
  - 6.0, 1024-wide and DFRC data: 35 to 40 in standard chess, 145 to 150 in DFRC;
  - 7.0, squared clipped ReLU and 1280-wide, with search: 25 to 30, "scaling
    as you use longer time controls";
  - 9.0, new data and the factoriser, with search: no figure against 8.2;
  - 9.1 against 9.0: "around 10-15 Elo".

### Architecture history
- 3.0 (2022-01): `768x256x1`, 320 M positions at depth 9 from Clover 2.4 [40, release notes].
- 3.1 (2022-03): `768x512x1`, 500 M positions [40, release notes].
- 3.3 (2023-02): `4x768 - 2x768 - 1`, king-mapped inputs, own CUDA trainer [40, release notes].
- 4.0 (2023-04): CudAD; 4.1 (2023-05): 5 king buckets [40, release notes].
- 6.0 (2023-08): 1024-wide, trained on DFRC data [40, release notes].
- 7.0 (2024-07): squared clipped ReLU, 1280-wide [40, release notes].
- 8.0 (2024-09): 7 king buckets [40, release notes].
- 9.0 (2025-08): mixed 5,000- and 20,000-node data, half DFRC; factoriser [40, release notes].
- 9.1 (2025-09-14): net on the 20,000-node data with a longer retrain [42, PR text].

### Since the rated version
- Nothing found: the newest pull request in the list is the one merged on the
  9.1 release day [41, PR titles]. The 9.1 notes say the author will "probably
  not work on Clover for quite some time" [40, release notes].

### UNVERIFIED and not published
- The 9.1 architecture string: width (last stated 1280), output buckets,
  mirroring, which squares form the 7 buckets, integer types.
- Size of the 9.1 data; tablebase use; the Kaggle data-set page would not load
  (browser check on a plain fetch, 404 through the fetch tool) [46, other].
- Every inference-speed technique: none is described in prose.
- Per-net Elo: not published.
- The author's remark of "spicy stuff" in data generation is not explained
  [45, TCEC].

---

## Halogen 16.0.0 (CCRL #30, 3720)

**One-line architecture:** `768x8hm-1536-dp-pw-16-32-1x8`, as the network release
notes write it for the first multi-layer net (2025-07-19), plus the dual activation
added two days later [49, release notes]. No later net up to the one in version 16
(150521a9) reports an architecture change [49, release notes] [48, release notes]. That "dp"
means both perspectives and "pw" pairwise multiplication is my reading.

### Inputs
- Feature set (what an input means; inputs per perspective if stated): 768 piece-square inputs in each of 8 king buckets, horizontally
  mirrored ("768x8hm") [49, release notes].
- King input buckets: count; layout (which king squares share a bucket, in words); how the layout was chosen or grown: 8. Path: none (2024-07-15); 8 buckets without mirroring
  (2024-07-20: +7.49 +- 4.70 LTC, +5.74 +- 4.15 STC); 4 buckets with mirroring
  (2024-07-22: +13.40 +- 6.56 LTC, +15.80 +- 7.58 STC) [51, PR text]; 8 with
  mirroring by 2025-07 [49, release notes]. Layout and how it was chosen: not published.
- Horizontal mirroring (when the king crosses the middle, or other): yes. A later pull request says the threat accumulator is
  rebuilt when the king crosses the middle of the board, and that this is a
  strict subset of the cases where the king-bucket accumulator is rebuilt
  [51, PR text].
- Threat or attack inputs (what relation they encode; how many; how they are updated): none in version 16. Added twelve days later (see
  "Since the rated version").
- Pawn features (pawn pairs, passed pawns, other): none published.
- Other input relationships (material or queen routing, pins, mobility, side-to-move, castling, anything else): none published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 1536 [49, release notes]. Path: 512
  (2024-07), 1024 (by 2025-07), 1536 (2025-07-08: +10.13 +- 4.27 LTC, +4.75 +-
  2.88 STC) [49, release notes] [51, PR text].
- Further layers: count and widths: 16, then 32, then 1 [49, release notes].
- Layer stacks (several copies of the head): count and what selects one: 8 ("x8"); selector not stated [49, release notes].
- Output buckets: count and what selects one (piece count, material, phase, queen presence, other): 8; what selects one: not published.
- Skip connections, pairwise multiplication, other structure: "pw" in the
  string (my reading: pairwise multiplication) [49, release notes].

### Activations
- After the accumulator: squared clipped ReLU in the 2024 single-layer nets
  [51, PR text]; for the multi-layer net see "pw" above.
- In the head (dual activation, others): dual activation: +2.87 +- 2.04 LTC, +4.01 +- 2.59 STC
  [49, release notes] [51, PR text]. Which pair: not published.

### Quantisation
- Integer types per layer (int8, int16, float layers): not published. Hints in titles only: a closed
  experiment "compress FT activations into int8 for dense l1 layer" (2025-05),
  use of the VNNI 8-bit dot-product instruction (2025-08), and a change that
  makes the last layer's inference give identical results on every platform
  (2025-08) [50, PR titles] [51, PR text]. The net file is 19,305,792 bytes
  [49, release asset metadata].
- Quantisation-aware training or other rounding care: not published.

### Inference speed (the owner wants every network-speed technique, each with its reported gain)
- Accumulator refresh cache: "Finny tables" (2024-07): +8.62 +- 5.15 at 8+0.08
  [51, PR text].
- Lazy or deferred accumulator updates (computed only when an evaluation is needed; walked back along the stack): (2024-07) +9.21 +- 5.31 at 8+0.08, +7.73
  +- 4.65 at 40+0.4, +14.37 +- 6.78 at 5+0.05 with 8 threads, +10.08 +- 4.87 at
  20+0.2 with 8 threads [51, PR text]. A first attempt to optimise them further was a
  slowdown, -1.301% +- 0.277% (2024-09, closed, kept "for future reference as
  the network grows") [51, PR text]. Not updating the accumulator state on a null move:
  +0.70 +- 1.56 at 8+0.08 (2025-09) [51, PR text].
- Fused updates (several feature changes applied in one pass; add-sub forms): (2024-07) +2.379% +- 0.245% speed, +2.49 +- 1.99 at 8+0.08 [51, PR text].
- Accumulator stack (how accumulators are kept along the search path; copy avoidance): moved into the search stack (2024-07): +5.349% +- 0.218%
  speed, +29.06 +- 10.23 at 8+0.08 [51, PR text]. Not recomputing the accumulator of the
  side not to move: +7.89 +- 4.88 at 8+0.08 [51, PR text]. Splitting the accumulator into
  separate sides was slower: -1.403% with gcc 12, -1.240% with clang 18 (closed)
  [51, PR text].
- Pairwise multiplication of accumulator halves (as a way to halve the next layer's input): in the net string; no separate
  figure [49, release notes].
- int8 layers or int8 feature-transformer rows: the int8 compression of
  accumulator outputs for the dense layer was closed without a figure
  [50, PR titles].
- Sparse first dense layer (non-zero block iteration, neuron permutation for sparsity): the non-zero search handles 32 blocks of four
  accumulator outputs at once with an AVX-512 compress instruction: +3.399% +-
  0.733% speed, +7.04 +- 3.45 at 4+0.04 [51, PR text]. The feature-transformer neurons
  are permuted for each net at build time; one net shipped with a wrong
  permutation, and fixing it gained +13.29 +- 6.15 at 8+0.08 [51, PR text]. A check that
  the permutation is valid was added later [50, PR titles].
- Evaluation cache (a hash table of network outputs, separate from the TT): CPW lists an "evaluation hash table" [52, CPW]; nothing
  newer is published.
- SIMD and VNNI work (AVX2, AVX-512, VNNI dot products, NEON; register tiling; anything about which instruction set won or lost):
  - hand-written SIMD inference code for SSE, AVX2 and AVX-512: +14.98 +- 5.36
    at 8+0.08 (2025-05) [51, PR text];
  - the squared-clipped-ReLU trick "from Lizard engine": +16.09 +- 7.10 LTC,
    +13.95 +- 6.82 STC (2024-07) [51, PR text];
  - an unnamed inference speed-up: +4.855% +- 0.186% (2024-07, closed) [51, PR text];
  - VNNI dot product and masked compress-store "to speed up Zen 5 builds":
    +1.183% +- 0.217% [51, PR text];
  - aligning weights, biases and accumulators to 32 bytes for AVX2: +1.63 +- 4.23
    at 8+0.08 (2024-03) [51, PR text];
  - NEON inference, a faster NEON emulation of the 8-bit dot product, and the
    ARMv8.2 dot-product instruction (2025-11): no figures [51, PR text].
- Memory layout and prefetching (alignment, huge pages, weight ordering, prefetch of rows or cache entries, net compression and file size): huge pages for thread-local search state
  (2025-10; tested through a Stockfish commit, no figure here) [51, PR text]. Huge pages
  on Windows: -0.07 +- 2.87 at 8+0.08 [51, PR text]. One copy of the net per NUMA node:
  +0.68 +- 1.56 at one thread, closed [51, PR text].
- Anything else that made the network faster: none.
- Speed cost or gain reported for any architecture change: the multi-layer net gained
  +13.20 +- 3.53 LTC and +6.34 +- 3.79 STC; no speed figure [49, release notes] [51, PR text].
- Hardware sensitivity reported (cache size, core count, a machine where a technique lost): the Zen 5 item above; fused updates and prefetching
  measured separately on AVX2 and AVX-512 after version 16 (below).

### Training data
- Size (positions or games) of the rated net's data: 14.8 billion positions for the version-16 net: 0.6 B from the last
  temporal-difference net, 0.7 B from the first bullet net, 8.2 B from Halogen
  12, 0.8 B from 13.12 and 4.5 B from 15.0 [49, release notes].
- Type: own self-play / Lc0 or Lc0-relabelled / another engine's / mixed / unknown; and how the labels are made (search budget, relabelling, teacher): own data only, from a randomly initialised network [53, TCEC]
  [47, README]. The first two supervised sets were generated "at 40k nodes"
  [51, PR text]. Node budget of the later sets: not published.
- Openings, filtering, tablebase use: [49, release notes] [51, PR text]
  - positions whose best move is a capture or promotion, or that are in check,
    are removed; the set is shuffled; results are rescored with Syzygy;
  - piece-count distribution filtering "as inspired by Stockfish": +13.24 +-
    4.97 LTC, +9.34 +- 4.29 STC;
  - probabilistic filtering of positions where result and evaluation disagree:
    +4.00 +- 2.55 LTC, +5.37 +- 3.14 STC (this is the version-16 net);
  - win and draw adjudication in data generation, tuned by relabelling old
    unadjudicated games; fully adjudicated data against none was +9.38 +- 4.76
    with test-time adjudication on and -24.17 +- 4.70 with it off; a 65/35 blend
    of adjudicated and unadjudicated data beat both (+20.91 +- 4.64 and +25.29
    +- 4.56) and was chosen because its piece-count distribution was favourable;
  - 4 billion more Halogen 12 positions plus Syzygy: +5.41 +- 3.43 LTC, +6.21
    +- 3.40 STC;
  - in the temporal-difference phase: Syzygy endgames played out, 5% DFRC, and
    wildly unbalanced openings filtered.

### Training recipe (concepts only)
- Trainer: bullet, with the author's own configuration [49, release notes] [53, TCEC]. The
  first lineage was trained from random weights by TDLeaf(lambda) inside the
  engine, later with temporal coherence, in runs of 8 to 16 hours; its last net
  was 182 Elo behind the then master, and supervised training took over
  [51, PR text] [47, README].
- Loss and target (result blend, as a concept): a constant result weight raised in steps: +2.66 +- 1.99 STC
  and +9.15 +- 4.08 LTC, then +0.79 +- 2.51 STC and +4.01 +- 2.54 LTC [49, release notes]. A
  further raise failed STC (-7.52 +- 4.13), was neutral at LTC (+0.41 +- 1.74)
  and passed at 120+1.2 (+2.71 +- 2.17); it was merged [49, release notes].
- Stages and schedule (warm start, fine-tunes, weight averaging): a much longer run of the same recipe: +4.38 +- 2.69 LTC,
  +9.81 +- 4.44 STC [51, PR text].
- Regularisation, optimiser, anything unusual: not published for the version-16
  net (the Ranger optimiser is named only after it) [49, release notes].

### Measured gains for network changes
- From-scratch `(768->512)x2->1` net replacing the older lineage: +31.56 +- 5.70
  LTC, +30.92 +- 6.37 STC [51, PR text].
- Data growth in August 2024, same architecture: 2.0 B positions +25.97 LTC and
  +27.81 STC; 3.2 B +22.80 and +18.95; 5.3 B +9.56 and +5.44 [51, PR text].
- King buckets, mirroring, 1536-wide, multi-layer, dual activation: see above.
- Halogen 15 data added (14.8 B): +12.26 +- 4.78 LTC, +9.15 +- 5.04 STC [49, release notes].
- 16 against 15 (whole release): +58.57 +- 4.91 LTC at one thread, +82.91 STC
  and +89.85 LTC at 8 threads [48, release notes].

### Architecture history
- Halogen 7 (2020-09): first incrementally updated net [52, CPW].
- 2022-02: a "half" architecture (title only) [50, PR text].
- 2024-07-15: `(768->512)x2->1`, squared clipped ReLU, from scratch [51, PR text].
- 2024-07-20 and 22: king buckets, then mirroring [51, PR text].
- 2024-08-01: a net whose branch label reads `768x4x2-1024x2-1x8` [51, PR text].
- 2025-07-08: 1536-wide; 2025-07-19: `768x8hm-1536-dp-pw-16-32-1x8`;
  2025-07-21: dual activation [49, release notes].
- 2026-02-03: net 150521a9; 2026-02-10: version 16 [49, release notes] [48, release notes].

### Since the rated version
Networks [49, release notes] [51, PR text]:
- 2026-02-12: a fine-tune on the game result alone: +6.89 +- 3.45 LTC, +0.34 +-
  1.81 STC.
- 2026-02-22: "full 79856-512 threat inputs network", built with help from
  PlentyChess's training file: +10.38 +- 4.41 LTC, +3.84 +- 2.60 STC.
- 2026-03-03: first layer 512 to 640: +2.47 +- 1.85 LTC, +0.69 +- 1.02 STC (not
  passing), +9.84 +- 4.68 at fixed nodes.
- 2026-03-13: a Ranger setting plus a result weight that ramps up linearly in
  the first stage: +5.38 +- 3.01 LTC, +12.30 +- 4.99 STC.
- 2026-05-20: a loss skew that makes scores more pessimistic: +3.20 LTC, +3.15
  STC.
- 2026-07-01: 9.3 B new positions from 16.5 (24.2 B in all): +12.64 +- 4.86 LTC,
  +11.39 +- 4.74 STC.
- 2026-07-03: 640 to 768: +7.85 +- 3.74 LTC, +4.45 +- 2.81 STC.

Speed work on the threat-input net [51, PR text]:
- threat code refactor with fused threat updates and smaller tables: +1.5%;
- the 8-bit dot-product loop split into two running sums: +1.171% on AVX2,
  +2.325% on AVX-512;
- four independent dot-product chains on AVX-512: +0.455%;
- a faster comparison mask on NEON: 1.01 +- 0.03 times;
- all of one side's threat changes applied in a single pass over the
  accumulator, read straight from the previous accumulator (no separate copy of
  the unchanged side): +2% on AVX2, +3.693% +- 0.876% on AVX-512;
- "even lazier" accumulators: a move only records itself and the two board
  states; the king-bucket and threat changes are worked out the first time the
  accumulator is needed, so subtrees cut off before any evaluation pay nothing:
  +0.24% on AVX2, +0.934% +- 0.269% on AVX-512 VNNI;
- threat-weight prefetches for both sides issued before either side is
  accumulated: +1.12% +- 0.20% on AVX2, +1.803% +- 0.249% on AVX-512. The
  description says the threat accumulator update is the hottest function of
  the search (about 22% of time), that the threat weight table is about 51 MB
  with an effectively random access pattern, and that the cost is memory
  latency, not arithmetic; the weight rows are 8-bit and widened as they are
  added;
- removing dead resets (among them a 256-byte clear on every move): +1.47% +-
  0.23% on AVX2, +0.581% +- 0.253% on AVX-512.

### UNVERIFIED and not published
- The meaning of "dp" and "pw" in the net string: my reading.
- Whether any architecture detail changed between 2025-07-21 and the version-16
  net: none is reported; not positively confirmed.
- King-bucket layout, output-bucket selector, the dual activation's pair,
  integer types: not published.
- Node budget of the data after the first two sets; whether the 65/35
  adjudication blend applies to all 4.5 B Halogen-15 positions: not stated.
- What the 79,856 inputs of the later threat net consist of: only in code.

---
## Sources

All opened on 2026-11-14. Pages of one kind in one repository share a number; the
row lists every page. "API" marks a `gh api` call that returned prose or metadata
only (10 calls in all, plus one quota check that showed 4,786 remaining). Saved
copies are in `pages/` beside this report; `fetchlog.tsv` has every plain fetch
with its HTTP status.

| # | URL | What it is | Type | Used for |
|---|---|---|---|---|
| 1 | https://raw.githubusercontent.com/h1me01/Astra/HEAD/README.md | Astra README | README | Astra |
| 2 | same path at revisions `09157eb`, `7.0`, `6.1.1`, `selfgen`, `689ba78` | Astra README at five revisions | README | Astra |
| 3 | https://github.com/h1me01/Astra/releases and `?page=2` | Astra release notes 3.0 to 7.0 | release notes | Astra |
| 4 | https://github.com/h1me01/Astra/pulls?q=is%3Apr ; /pull/14 ; /pull/15 | PR list and two PR conversations | PR text | Astra |
| 5 | https://github.com/h1me01/Astra/issues?q=is%3Aissue | issue titles | issue text | Astra (nothing used) |
| 6 | API `repos/h1me01/Astra/commits`: `since=2025-11-01`; `sha=selfgen`; `until=2025-11-01` pages 1 to 3 (page 3 empty) | commit messages only | commit text | Astra |
| 7 | https://huggingface.co/datasets/h1me01/astra-selfplay | data-set card (empty card; size 29.6 GB, licence MIT) | other (data set) | Astra |
| 8 | https://github.com/h1me01/Sorei | Sorei repository front page (README; MIT) | README | Astra |
| 9 | https://raw.githubusercontent.com/h1me01/Astra-Trainer/HEAD/README.md | FAILED, 404 | README | - |
| 10 | https://raw.githubusercontent.com/Orbital-Web/Raphael/HEAD/README.md | Raphael README | README | Raphael |
| 11 | https://raw.githubusercontent.com/Orbital-Web/Raphael/main/src/eval/net/history.txt | Raphael's "NNUE History", the prose net log the README links | prose net log | Raphael |
| 12 | https://github.com/Orbital-Web/Raphael/releases | Raphael release notes | release notes | Raphael |
| 13 | https://github.com/Orbital-Web/Raphael/pulls?page=1..8&q=is%3Apr | PR titles #6 to #164 | PR text | Raphael |
| 14 | https://github.com/Orbital-Web/Raphael/pull/N for N = 55, 56, 67, 78, 86, 89, 102, 113, 114, 115, 116, 121, 127, 137, 139, 145, 147, 148, 151, 155, 162 | PR conversations | PR text | Raphael |
| 15 | https://raw.githubusercontent.com/Orbital-Web/Raphael-Net/HEAD/README.md ; https://github.com/Orbital-Web/Raphael-Net/releases ; API `repos/Orbital-Web/Raphael-Net/releases/tags/yogsothoth_v3` (asset name and size only) | net repository README, release list (bodies are preformatted blocks, not read), asset metadata | release notes / metadata | Raphael |
| 16 | https://wiki.chessdom.org/Raphael_questionnaire_20260617 | TCEC questionnaire | TCEC | Raphael |
| 17 | https://raw.githubusercontent.com/Matthies/RubiChess/HEAD/README.md | RubiChess README | README | RubiChess |
| 18 | https://raw.githubusercontent.com/Matthies/RubiChess/master/ChangeLog.txt | RubiChess change log | changelog | RubiChess |
| 19 | https://raw.githubusercontent.com/Matthies/NN/HEAD/README.md | net repository README (history of every master net) | README | RubiChess |
| 20 | https://github.com/Matthies/RubiChess/releases | release notes | release notes | RubiChess |
| 21 | https://github.com/Matthies/RubiChess/wiki ; /wiki/TCEC-Questionnaire ; /wiki/Statistics | wiki pages | wiki | RubiChess |
| 22 | https://github.com/Matthies/RubiChess/pulls?page=1..4&q=is%3Apr | PR titles #409 to #540 | PR text | RubiChess |
| 23 | https://github.com/Matthies/RubiChess/pull/N for N = 413, 414, 415, 416, 427, 429, 432, 433, 442, 459, 462, 469, 473, 478, 483, 499, 501, 509, 517, 523, 529, 533, 535 | PR conversations | PR text | RubiChess |
| 24 | https://wiki.chessdom.org/RubiChess_questionnaire_20251029 | TCEC questionnaire | TCEC | RubiChess |
| 25 | https://www.chessprogramming.org/RubiChess | CPW page | CPW | RubiChess (nothing used) |
| 26 | https://raw.githubusercontent.com/official-stockfish/nnue-pytorch/master/docs/nnue.md (prose from the HalfKAv2_hm section to the end; code fences stripped) ; .../docs/nnue_architecture_history.md | Stockfish trainer documentation | other (trainer docs) | RubiChess |
| 27 | https://raw.githubusercontent.com/zzzzz151/Starzix/REV/README.md for REV = HEAD, 6.0, 6.1, 5.0, 4.0, 3.0 ; REV = v6.0 FAILED, 404 | Starzix README at six revisions | README | Starzix |
| 28 | https://github.com/zzzzz151/Starzix/releases | release notes | release notes | Starzix |
| 29 | https://github.com/zzzzz151/Starzix/pulls?page=1..9&q=is%3Apr | PR titles #1 to #203 | PR text | Starzix |
| 30 | https://github.com/zzzzz151/Starzix/pull/N for N = 5, 14, 16, 26, 88, 89, 94, 95, 97, 100, 127, 158, 195, 200 | PR conversations (titles and bench counts only; no descriptions) | PR text | Starzix |
| 31 | https://raw.githubusercontent.com/zzzzz151/Starway/HEAD/README.md ; https://raw.githubusercontent.com/zzzzz151/nn-trainer/HEAD/README.md FAILED, 404 | trainer README | README | Starzix |
| 32 | https://raw.githubusercontent.com/Bobingstern/Tarnished/HEAD/README.md | Tarnished README | README | Tarnished |
| 33 | https://github.com/Bobingstern/Tarnished/releases and `?page=2` | release notes 2.0 to 6.0 | release notes | Tarnished |
| 34 | https://raw.githubusercontent.com/Bobingstern/tarnished-nets/HEAD/README.md ; https://github.com/Bobingstern/tarnished-nets/releases and `?page=2` ; API `.../releases/tags/lichdragon-3` (asset name and size only) | net repository README, 18 net notes, asset metadata | release notes / metadata | Tarnished |
| 35 | https://github.com/Bobingstern/Tarnished/pulls?page=1..7&q=is%3Apr | PR titles #1 to #160 | PR text | Tarnished |
| 36 | https://github.com/Bobingstern/Tarnished/pull/N for N = 7, 14, 33, 50, 55, 63, 96, 101, 106, 110, 111, 115, 116, 118, 119, 121, 124, 128, 130, 131, 135, 141, 144, 151, 152, 154, 155, 156 | PR conversations | PR text | Tarnished |
| 37 | API `repos/Bobingstern/Tarnished/commits?since=2026-03-01` | commit messages only | commit text | Tarnished |
| 38 | https://wiki.chessdom.org/Tarnished_questionnaire_20251016 | TCEC questionnaire | TCEC | Tarnished |
| 39 | https://raw.githubusercontent.com/lucametehau/CloverEngine/HEAD/README.md | Clover README | README | Clover |
| 40 | https://github.com/lucametehau/CloverEngine/releases and `?page=2..4` | release notes 2.1 to 9.1 | release notes | Clover |
| 41 | https://github.com/lucametehau/CloverEngine/pulls?page=1..6&q=is%3Apr | PR titles #255 to #407 | PR text | Clover |
| 42 | https://github.com/lucametehau/CloverEngine/pull/N for N = 269, 288, 301, 318, 331, 332, 339, 347, 369, 370, 371, 372, 375, 376, 377, 378, 386, 387, 388, 393, 399, 407 | PR conversations (mostly without descriptions) | PR text | Clover |
| 43 | API `repos/lucametehau/CloverEngine/commits?since=2025-07-15&until=2025-09-15` | commit messages only | commit text | Clover |
| 44 | https://www.chessprogramming.org/Clover | CPW page | CPW | Clover (nothing newer than 3.x) |
| 45 | https://wiki.chessdom.org/Clover_questionnaire_20251109 | TCEC questionnaire | TCEC | Clover |
| 46 | https://www.kaggle.com/datasets/lucametehau/clover-viribinpack-format-data | FAILED twice: a browser-check page on a plain fetch, 404 through the fetch tool | other (data set) | - |
| 47 | https://raw.githubusercontent.com/KierenP/Halogen/HEAD/README.md | Halogen README | README | Halogen |
| 48 | https://github.com/KierenP/Halogen/releases | release notes 14 to 16 | release notes | Halogen |
| 49 | https://github.com/KierenP/Halogen-Networks/releases and `?page=2` (pages 3 to 8 were fetched and are empty) ; .../Halogen-Networks/HEAD/README.md FAILED, 404 ; API `.../releases/tags/150521a9` (asset name and size only) | 16 network notes, asset metadata | release notes / metadata | Halogen |
| 50 | https://github.com/KierenP/Halogen/pulls?page=1..22&q=is%3Apr | PR titles #350 to #912 | PR text | Halogen |
| 51 | https://github.com/KierenP/Halogen/pull/N for N = 401, 517 to 523, 526, 527, 529 to 532, 534, 546 to 549, 564, 616, 618 to 621, 635, 661, 662, 680, 685, 708, 719, 720, 722, 726, 732, 739, 741, 784, 789, 792, 816, 820, 822, 844, 857, 858, 862, 863, 864, 867, 870, 872, 873, 875, 876, 878, 883, 885, 887 to 890 | PR conversations | PR text | Halogen |
| 52 | https://www.chessprogramming.org/Halogen | CPW page | CPW | Halogen |
| 53 | https://wiki.chessdom.org/Halogen_questionnaire_20251013 | TCEC questionnaire | TCEC | Halogen |
| 54 | https://wiki.chessdom.org/Category:TCEC_Questionnaire | list of questionnaires (none for Astra or Starzix) | TCEC | all |
| 55 | the agent's scratch folder (engines.md, sources.md, comparison.md sections H to K, provenance.md) | the earlier survey, read only | prior survey | all |

Credit lines (author as the page names them; licence only where a page I opened
states it):

- Astra: h1me01 (no other name on the pages opened). Engine licence: not stated
  on the pages opened. Data set: MIT [7]. Sorei trainer: MIT [8].
- Raphael: Rei Meguro ("Orbital-Web") [16]. "GPL 3" in the questionnaire of
  2026-06-17 [16]; a pull request of July 2026 is titled as a switch to AGPL
  [13].
- RubiChess: Andreas Matthies. GPLv3 [21] [24] [25].
- Starzix: zzzzz151. Licence: not stated on the pages opened.
- Tarnished: Anik P ("Bobingstern") [38]. "No license (yet)" in October 2025
  [38]; a commit of 2026-06-10 adds the GNU GPL v3 [37].
- Clover: Luca Metehau. GPL 3.0 [45].
- Halogen: Kieren Pearson. GPL-3.0 [53] [52].
- bullet trainer: Jamie Whiting (jw1912), as Halogen's questionnaire names him
  [53]. nnue-pytorch documentation: the official-stockfish project [26].
- Chess Programming Wiki: CC BY-SA 3.0, as its pages state [25] [44] [52]. TCEC
  wiki: CC BY-SA 3.0, as its pages state [38].

## Clean-room statement

I opened no source file, header, build file, training script, trainer
configuration file, diff, patch, "Files changed" tab, blame view, code-search
result or network file of any engine or trainer. I cloned no repository and
downloaded no release archive, binary or network file. The three net file sizes
come from release-asset metadata (name and byte count), not from the files.

Everything that came close:

1. **Two lines of code reached my terminal once.** The conversation page of
   Halogen pull request #792 embeds a review comment with a diff hunk; my first
   listing of that page printed two declaration lines from it before I had a
   filter for such blocks. I read nothing more of it, recorded nothing from it,
   and changed my page converter to drop inline review code views; every pull
   request page was then re-converted. Nothing in this report rests on it.
2. **Bot review summaries.** Several Halogen pull-request pages carry
   automated review overviews that name source files and identifiers and, in
   one case (#789), numeric thresholds. I filtered them out for later pages and
   recorded no file name, identifier or threshold from them.
3. **Identifiers in authors' own prose.** Halogen's descriptions of #883 and
   #887 to #889, and RubiChess and Raphael commit titles, name functions and
   instructions. They are described here as concepts only.
4. **Code blocks in prose pages** were replaced by a marker by my converter and
   never read: build commands in READMEs, the Raphael-Net release bodies, the
   king-table block in Clover's 3.3 release note, usage examples in Sorei's
   README, and the code fences of the Stockfish trainer documentation.
   Preformatted blocks that are plainly test-result or timing tables (Elo, LLR,
   bench times) were kept.
5. **Raphael's network log** (source 11) is a prose text file that sits in the
   engine's source tree; the README links it as documentation and the earlier
   survey used it. It lists trainer settings (learning rates, result weights,
   quantisation scales, schedule lengths); none of those values is recorded.
6. **Links I did not follow:** the trainer configuration files and source files
   that Halogen's network notes link, the other engines' source files linked
   from Raphael's pull request #113, and Stockfish commits and pull requests
   linked from several pages.
7. **Repository front pages** (Sorei) show directory names; nothing was taken
   from them.
8. The architecture diagrams of the Stockfish trainer documentation were not
   opened; RubiChess's "SFv5" details are therefore UNVERIFIED.

Values seen and deliberately not recorded: learning rates, result-blend weights,
quantisation scales, loss exponent and skew, optimiser constants, schedule
lengths, random-skip probability and adjudication thresholds.

Files: I wrote only inside my scratch folder (`report.md`, `part1.md` to
`part4.md`, `fetchlog.tsv`, `apicalls.log`, `tools/`, `pages/`). I deleted
nothing. I edited nothing in the repository or the kb worktree, committed
nothing and started no job.
