# Network records, group G: Velvet, Minke, Tcheran, Seer, Uralochka, Motor, Renegade

Clean-room network survey of 2026-11-14 ([README](../README.md)). Written by survey agent G from public prose only and assembled unchanged except for local paths. Source numbers in brackets refer to the Sources table at the end of this file. Every engine here is REFERENCE ONLY for ideas; its code, nets and data are OFF-LIMITS for Fork.


Clean-room survey of 2026-11-14. Every fact below comes from a page opened today (source number in brackets, with the source type) or is carried from the survey of 2026-11-10 ("prior survey"). Elo figures are each engine's own self-play results under its own conditions. "FN" is a fixed-nodes test, "STC" and "LTC" are the engine's own short and long time controls (given once per engine where stated). No search constant, quantisation scale, clipping bound, learning rate, result-blend weight or loss exponent is recorded, even where the page shows one.

Corrections to the prior survey found on the way:

- **Minke 7.0.0's network is minke39, trained on 17 B positions**, not 23 B. The 23 B figure belongs to minke44, merged on 2026-10-22, eight weeks after the 7.0.0 tag [7, 9, 10].
- **Five of the seven engines have a TCEC questionnaire** (Velvet, Tcheran, Seer, Uralochka, Renegade) which the prior survey did not open [4, 18, 23, 33, 42].
- **The prior survey's "QAT: Motor +8, +12"** appears to be Motor PR #224 (+8.1 at 60+0.6, +12.1 at 10+0.1). That PR is a new net on the post-0.9.0 restart branch (more positions, described as QAT) against its predecessor, not an isolated test of quantisation-aware training [36].

---

## Velvet 8.1.0 (CCRL #37-38, 3702)

**One-line architecture:** assembled from the fields below, not written by the engine as one string for 8.1.0: 32 king buckets x 768 inputs -> 2 x 1024 -> 1, with 8-bit input-layer weights. The engine's own string is the 6.0.0 one, "32x768->2x512->1" [2, release notes]; the hidden layer then grew to 2x768 (7.2.0) and 2x1024 (8.0.0) [2, release notes]. That the 32 buckets were kept through 8.1.0 is UNVERIFIED (not restated after 6.0.0).

### Inputs
- Feature set: 768 piece-square inputs per bucket ("32x768") [2, release notes]. Inputs per perspective: not published as a number (32 x 768 = 24,576 by arithmetic).
- King input buckets: 32 since 6.0.0. The release gives "32x768"; the commit of 2023-12-03 is titled as increasing the number of king buckets and removing the piece-combination buckets [2, release notes; 5, commit text]. Layout: not published. How it was chosen: not published.
- Horizontal mirroring: not published. (32 = 4 files x 8 ranks would fit a mirrored half board, but that is my arithmetic, not a statement: UNVERIFIED.) Since 3.0.0 the net always evaluates from White's point of view by colour-flipping positions with Black to move, which halved the net [2, release notes; 5, commit text].
- Threat or attack inputs: none published.
- Pawn features: none published.
- Other input relationships: before 6.0.0 the inputs were "3x5x768", a product of king buckets and "piece-combination" buckets (which factor is which is not stated). The author describes the early system as buckets "based on the presence of certain pieces (for example, a different bucket when there were no queens left)". 6.0.0 dropped this material routing in favour of more king buckets [2, release notes; 4, TCEC; 5, commit text]. A commit of 2023-01 removed "king-position-relative buckets for king pieces" [5, commit text].
- Factoriser or other training-only structure: not published. The Velvet 9 trainer (after the rated version) uses an embedding layer instead of sparse tensors to train faster [4, TCEC].

### Body
- First hidden layer width per perspective: 1024 ("2x1024") since 8.0.0 [2, release notes; 5, commit text].
- Further layers: none. 3.2.0 "removed additional hidden layers" as a speed measure and the architecture strings since end in "->1" [2, release notes].
- Layer stacks: none published.
- Output buckets: none published (single output in the 6.0.0 string).
- Skip connections, pairwise multiplication, other: none published.
- Two complete nets are embedded, "Normal" and "Risky", chosen by a UCI option; the Risky net costs about 25 Elo [1, README; 2, release notes].

### Activations
- After the accumulator: a clipped ReLU, by inference from a commit title of 2024-06-28 (a net "trained using higher upper ReLU bound") [5, commit text]. Otherwise not published.
- In the head: none (no head).

### Quantisation
- Integer types: 8.1.0 switched the input layer from 16-bit to 8-bit weights, described as "a partial switch to 8-bit quantized weights" [2, release notes; 5, commit text]. Type of the output layer: not published.
- Quantisation-aware training or rounding care: not published. The author wrote his own quantisation tool [4, TCEC].

### Inference speed
- Accumulator refresh cache: not published.
- Lazy or deferred updates: since 3.2.0 (2022) updates and calculations are deferred until the evaluation is called; no figure [2, release notes; 5, commit text].
- Fused updates: a commit of 2023-07-23 combines the added and the removed piece in one accumulator update; no figure [5, commit text].
- Accumulator stack: not published.
- Pairwise multiplication: none published.
- int8 layers or int8 feature-transformer rows: yes, the input layer since 8.1.0. No separate figure: the release as a whole (search changes and the 8-bit switch) is put at about +40 Elo in a gauntlet and +60 in self-play at 60+0.6 [2, release notes]. Binaries of 8.1.1 (bug-fix release) are about 49 MB with two nets embedded [2, release notes]; 32 x 768 x 1024 one-byte weights are about 25 MB per net, which fits (my arithmetic, not the author's statement).
- Sparse first dense layer: not applicable (no dense layer).
- Evaluation cache: 7.0.0 lists, under performance optimisations, caching evaluation scores in the transposition table and "up to 50% higher performance in positions with fewer pieces"; the two are written together, so whether the figure belongs to the cache alone is not clear [2, release notes]. A separate network-output table: not published.
- SIMD and VNNI: AVX-512 build added in 8.1.0 (Linux only at first); a commit of 2024-09-07 reworked the network code with AVX-512 and NEON paths; a 2022 commit hand-vectorised the incremental updates to work round a compiler regression; no figures [2, release notes; 5, commit text]. Which instruction set won: not published.
- Memory layout and prefetching: 32-byte alignment of the network arrays "for a small speed-up" (2021); prefetch support for ARM and a changed prefetch hint on x86 (2024); network parameters shared by all search threads (2021); the embedded net is compressed (3.2.0), with Huffman coding replaced by a simpler and faster scheme at 6.0.0 [2, release notes; 5, commit text]. Net file size: not published.
- Anything else: 9.0.0-dev7 (after the rated version) keeps a mirrored board representation so the board need not be mirrored at run time [2, release notes].
- Speed cost or gain of an architecture change: not published.
- Hardware sensitivity: not published.

### Training data
- Size of the rated net's data: not published. The only size ever given is 800 million positions for the first net (2.0.0) [2, release notes].
- Type: own self-play. The first net was trained on self-play of the previous, hand-crafted-evaluation Velvet; later nets on "game results and evaluations" of matches between previous Velvet versions [4, TCEC; 2, release notes]. Older sets were re-scored for 5.3.0 [2, release notes].
- Label adjustments: 7.0.0 rescaled the scores; 7.2.0 scaled down scores of drawn games for certain material combinations; 8.0.0 lowered scores where a sacrifice ended in a loss or draw and adjusted scores from statistics of similar material combinations [2, release notes].
- Openings, filtering, tablebase use: Chess960 positions since 3.3.0 and DFRC generation since 2022 [2, release notes; 5, commit text]. Search budget of the labels, filtering and tablebase use: not published.

### Training recipe (concepts only)
- Trainer: the author's own; a multi-core CPU trainer at 4.0.0, a GPU trainer again at 5.1.0; a newer private version for Velvet 9 [2, release notes; 4, TCEC].
- Loss and target: evaluations and game results both enter the target [4, TCEC]; the blend is not published.
- Stages and schedule: not published.
- Anything unusual: 7.2.0's first 2x768 net was trained "with some experimental changes" and was only slightly better than the 2x512 net; a retrain (7.3.0) added about 10 Elo [2, release notes].

### Measured gains for network changes
- 3.2.0, hidden layer 64 to 256, deferred updates, extra hidden layers removed: about +130 for the release [2, release notes].
- 6.0.0, "3x5x768->2x512->1" to "32x768->2x512->1" plus new data: about +35 for the release (under +10 in FRC/DFRC) [2, release notes].
- 7.2.0, hidden 2x512 to 2x768: about +20 for the release; 7.3.0 retrain about +10 [2, release notes].
- 8.0.0, hidden 2x768 to 2x1024 plus label adjustments: about +35 for the release [2, release notes].
- 8.1.0, 8-bit input weights plus search: about +40 (gauntlet), +60 (self-play), 60+0.6 [2, release notes].

### Architecture history
- 2.0.0 (2021-07): first net, 800 M self-play positions [2, release notes].
- 3.0.0: net halved by removing colour-specific inputs [2, release notes].
- 3.2.0: hidden 64 -> 256; deferred updates; additional hidden layers removed; compressed net files [2, release notes].
- 3.3.0: hidden 256 -> 512; Chess960 positions [2, release notes].
- 4.0.0: inputs "768x24 instead of 768x5", hidden 2x288 instead of 512; new CPU trainer [2, release notes].
- 5.1.0: larger hidden layer (size not given) [2, release notes].
- 2023: king buckets reduced; king-relative buckets for king pieces removed [5, commit text].
- 6.0.0 (2023-12): "32x768->2x512->1" [2, release notes].
- 7.2.0 / 7.3.0 (2024-04): 2x768 [2, release notes].
- 8.0.0 (2024-08): 2x1024; two style nets [2, release notes].
- 8.1.0 (2024-10-28): 8-bit input weights; AVX-512 [2, release notes].

### Since the rated version
- 8.1.1: bug fixes only [2, release notes].
- 9.0.0-dev3 (TCEC preview): hidden layer 2x1024 -> 2x1536 on newly generated data; the Risky net dropped for now [2, release notes].
- 9.0.0-dev7: another new net; mirrored board representation [2, release notes].
- The Velvet 9 net was trained with a private trainer version [4, TCEC].

### UNVERIFIED and not published
- King-bucket layout, and whether 8.1.0 still has 32 buckets (not restated).
- Horizontal mirroring (not published).
- Activation, output-layer integer type, any rounding care (not published).
- Data size, label search budget, filtering, tablebase use (not published).
- Loss blend, schedule, optimiser (not published).
- Any nps figure for the 8-bit switch (not published).

---

## Minke 7.0.0 (CCRL #39, 3701)

**One-line architecture:** as the engine writes it: "(768x16hm->1280pw)x2->(16x2->32->1)x8" [6, README at v7.0.0; 8, release notes]. The net in 7.0.0 is **minke39**: its default-network PR was merged 2026-08-21, the version bump 2026-08-25, the tag is the merge commit of PR #204 (2026-08-26), and minke40 followed on 2026-09-04 [8, release notes; 9, PR titles; 10, PR text].

### Inputs
- Feature set: 768 piece-square inputs per king bucket, per perspective ("768x16hm") [6, README].
- King input buckets: 16, on the mirrored half board (4 files x 8 rows in the log's table). Reading the table row by row: each of the 4 files on the first row has its own bucket, and so has each on the second row; the third row has two buckets (files in pairs) and the fourth row two more; rows five and six share two buckets (file pairs); rows seven and eight share the last two [7, network log]. Which row is the king's home rank is not stated; the fine buckets being on the first two rows suggests it is the first (UNVERIFIED).
- How the layout grew [7, network log]:
  - minke17, 2.5 B positions: 4 buckets (two on the first row in file pairs, one for the second row, one for everything else), +15.5 at 16+0.16;
  - minke21, 3.8 B: 6 buckets, +3.7 at 16+0.16;
  - minke25, 6.9 B: 8 buckets (first row one per file) together with 8 output buckets, +9.4 FN and +9.0 STC;
  - minke28, 9.2 B: 10 buckets (first two rows one per file), with a fine-tune change, +3.5 STC;
  - minke39, 17 B: 16 buckets, +8.6 FN and +4.2 STC.
- Horizontal mirroring: yes ("hm"), from minke6 on (+17.0 at 16+0.16) [7, network log].
- Threat or attack inputs: none.
- Pawn features: none.
- Other input relationships: none published.
- Factoriser: not published.

### Body
- Accumulator width per perspective: 1280, with pairwise multiplication ("pw") [6, README; 7, network log].
- Further layers: two hidden layers of 16 and 32, then the output; the first is written "16x2" because of the dual activation [6, README; 7, network log].
- Layer stacks: the head "(16x2->32->1)" is written "x8", eight copies [6, README]. What selects a copy: not published in prose (the log only says "output buckets"): UNVERIFIED (only in code).
- Output buckets: 8, added "accidentally" with minke25 and kept because separate tests showed them neutral (+0.75 +- 3.79 STC) [7, network log].
- Skip connections: none published.

### Activations
- The log's activation line for minke31 onward reads "crelu+csrelu -> screlu -> crelu"; for minke30 it read "pw -> screlu -> crelu" [7, network log]. The PR that introduced the change is titled "Dual activation for L1 (CReLU + SCReLU)" [10, PR text]. So there is a pairwise-multiplied accumulator, clipped and squared-clipped ReLU side by side on the 16-wide layer, and squared and plain clipped ReLU further on; the exact mapping of the three entries to layers is my reading (UNVERIFIED).

### Quantisation
- "Quantized NNUE" [6, README]; the log gives three quantisation scales, one per stage (values not recorded) [7, network log]. Integer types per layer: not published (only in code).
- Quantisation-aware training: not published.

### Inference speed
STC is 8+0.08, LTC 40+0.4, unless noted.
- Accumulator refresh cache ("Finny table"): present by 2026-07 (no PR title introduces it; king buckets arrived with PR #102). "Finny table fused updates": +2.4 +- 2.6 at 4+0.04 on non-regression bounds. Storing the cache's board as 8 bitboards (six piece types plus two colours): -0.6 +- 2.6 at 4+0.04, a sanity check [10, PR text].
- Lazy updates: "NNUE lazy updates", +15.1 +- 6.3 STC (2026-05, on the single-layer net of that time) [10, PR text].
- Fused updates: "NNUE fused updates", +9.2 +- 4.8 STC [10, PR text].
- Accumulator stack: an earlier "improve cache locality when updating Accumulator" change, +6.3 +- 4.4 at 1+0.01 [10, PR text]. Details of the stack: not published.
- Pairwise multiplication: part of the first multi-layer net (minke30); no separate figure [7, network log].
- int8 layers: not published.
- Sparse first dense layer: "sparse affine inference and permute network for sparsity", +2.8 +- 2.3 STC; the parameters are permuted when the network is prepared, from measured activation counts [10, PR text]. "Optimize sparse iterator for AVX512": about 8% faster on AVX-512, +11.0 +- 5.8 at 4+0.04 on AVX-512, +1.0 +- 2.4 (non-regression) on AVX2 [10, PR text]. Both are in 7.0.0.
- Evaluation cache: not published (the raw evaluation is stored in the TT) [9, PR titles].
- SIMD and VNNI: builds for AVX2, BMI2, AVX-512, native and Apple silicon [6, README]. After 7.0.0: "optimise ARM NEON dotprod", 1.11 +- 0.01 times faster [10, PR text].
- Memory layout and prefetching (after 7.0.0): huge pages for the network, 1.01 +- 0.01 times faster single-threaded on an i5-12400F, about 4% at 12 data-generation threads, "~4" (unit not given) with 192 concurrent instances on a 2 x EPYC 192-core machine, +5.7 +- 3.9 at 4+0.04 [10, PR text]. Net file size: not published.
- Anything else: a PGO build (2026-06) [9, PR titles].
- Speed cost or gain of architecture changes [7, network log; 10, PR text]:
  - multi-layer head (minke30): +38.7 FN, +9.7 STC, +17.9 LTC;
  - accumulator 1024 -> 1280 (minke34): +14.7 FN, -0.6 STC (unfinished), +4.0 LTC;
  - 10 -> 16 king buckets (minke39): +8.6 FN, +4.2 STC.
- Hardware sensitivity: the huge-page gain grows with the number of threads or instances ("more cache pressure") [10, PR text].

### Training data
- Size: 17 B positions for minke39 (data batches 12 to 33 of the engine's own generations) [7, network log].
- Type: own self-play only, started from a randomly initialised net (minke0, 16 M positions) and iterated: 103 M, 141 M, ... 3.8 B at minke22, the first net to replace the earlier Stockfish- and Lc0-trained nets (2026-06), "3.8 billion positions over 23 iterations" [7, network log; 10, PR text; 8, release notes for the 2.0 and 3.0 data].
- Label search budget: not published for the batches behind minke39. Later batches are "12ksn" (12,000 soft nodes) [7, network log].
- Openings, filtering, tablebase use: generation from opening books was added just before 7.0.0 (2026-08-20); data are stored in viriformat; piece-count filtering from minke38; old batches are dropped as new ones arrive (batches 0-6 gone by minke18, 7-11 at minke26) [7, network log; 10, PR text]. Tablebase use in generation: not published.

### Training recipe (concepts only)
- Trainer: bullet [6, README].
- Loss and target: a blend of search score and game result whose result share is held low at first and then ramps up [7, network log].
- Stages and schedule: two stages from minke26: a long main stage with a decaying learning rate, then a fine-tune stage at a very low rate. The fine-tune's result share was raised step by step (minke28, 32, 33) and is result-only from minke37 [7, network log].
- Regularisation and other: random position skipping from minke27; an activation regulariser "to encourage sparse first-layer activations" from minke36 [7, network log]. Optimiser: not published.

### Measured gains for network changes
All [7, network log] unless noted; "FN" is 25,000 nodes.
- Horizontal mirroring (minke6): +17.0 +- 7.4 at 16+0.16.
- 4 king buckets (minke17): +15.5 +- 6.5 at 16+0.16.
- 6 buckets (minke21): +3.7 +- 2.8 at 16+0.16.
- Lower final result share (minke22): +8.6 +- 5.2 STC.
- +1 B data (minke23): +15.4 +- 7.1 FN. +2.1 B more (minke24): +1.4 +- 1.4 FN, not conclusive.
- 8 buckets and 8 output buckets (minke25): +9.4 FN, +9.0 STC; output buckets alone +0.75 +- 3.79 STC.
- +3 B data, 0.7 B old data removed, fine-tune stage added (minke26): +11.8 +- 6.7 STC.
- Random position skipping (minke27): +5.3 +- 3.5 FN.
- 10 buckets and a higher fine-tune result share (minke28): +3.5 +- 3.1 STC.
- +3.8 B data (minke29): +5.2 +- 4.2 STC.
- Multi-layer head with pairwise multiplication (minke30): +38.7 +- 12.9 FN, +9.7 +- 5.3 STC, +17.9 +- 7.2 LTC [also 10, PR text].
- Dual activation (minke31): +9.9 FN, +8.6 STC, +6.0 +- 3.9 LTC.
- Higher fine-tune result share (minke32, then minke33): FN -1.9 and -1.6, STC +1.3 and +2.0 (unfinished), LTC +8.1 and +8.1.
- Accumulator 1280 (minke34): +14.7 FN, -0.6 STC, +4.0 +- 3.0 LTC.
- +4 B data (minke35): +5.4 +- 4.1 FN.
- Sparsity regulariser (minke36): -0.4 FN, +5.0 STC, +3.7 +- 2.8 LTC.
- Decaying fine-tune rate and result-only fine-tune (minke37): -3.7 FN, +3.6 +- 2.8 LTC.
- Piece-count filtering (minke38): +4.6 FN, +2.2 STC (unfinished), +10.8 +- 5.6 LTC.
- 16 buckets (minke39): +8.6 +- 5.6 FN, +4.2 +- 3.2 STC.

### Architecture history
- 1.0.0 (2025-08): "(768 -> 1024)x2 -> 1", SCReLU, bullet [8, release notes].
- 2.0.0: a net trained on about 13 B Stockfish positions; 3.0.0: a mix of Lc0 and Stockfish data [8, release notes]. Both dropped in 2026-06.
- minke0-minke16: single-layer nets grown 16 -> 64 -> 128 -> 192 -> 256 -> 384 -> 512 -> 768 -> 1024 as the data grew from 16 M to 2.2 B; mirroring at minke6 [7, network log].
- minke17-minke29: king buckets 4 -> 6 -> 8 -> 10; 8 output buckets at minke25 [7, network log].
- minke30 (2026-07-21): multi-layer head; minke31: dual activation; minke34: 1280 wide; minke39 (2026-08-21): 16 buckets [7, network log; 9, PR titles].

### Since the rated version
- minke40: +1.6 B data and a longer main stage, +6.3 FN, +4.4 STC.
- minke41: +2.2 B positions at 12,000 soft nodes, +8.0 +- 4.9 STC.
- minke42: older data removed from the fine-tune set, +3.8 +- 2.9 LTC.
- minke43: games whose result disagrees with 6-man tablebases filtered out, +2.3 +- 1.8 STC (LTC unfinished at +1.2).
- minke44 (2026-10-22): +2.4 B positions at 12,000 soft nodes (23.2 B in the main stage) and a narrower fine-tune set (8.9 B), -0.2 FN, +9.1 +- 5.1 LTC; the new data alone were neutral [7, network log; 9, PR titles].
- NEON dot-product and huge-page changes (above); network inference and accumulator update logic decoupled (refactor) [9, PR titles; 10, PR text].

### UNVERIFIED and not published
- What selects one of the 8 output buckets (only in code).
- Orientation of the bucket table and the exact mapping of activations to layers (my reading).
- Integer types per layer; quantisation-aware training (not published).
- Label search budget of the data behind minke39; tablebase use in generation (not published).
- The PR that introduced the refresh cache, and its gain (not found).
- Optimiser; net file size (not published).

---

## Tcheran 14.0 (CCRL #42, 3697)

**One-line architecture:** as the engine writes it: "(768x8hm->1024)x2->(16->32->1)x8": "a multi-layer, horizontally-mirrored network with 1024, 16 and 32 node hidden layers, and eight output buckets" [12, README at v14.0]. The net in 14.0 is network #25 [13, network log; 14, changelog].

### Inputs
- Feature set: 768 piece-square inputs per king bucket, per perspective [12, README].
- King input buckets: 8 (network #19), up from "a basic 4-bucket layout" (network #16) [13, network log; 16, commit text]. Which squares share a bucket: not published in prose (only in code). The layout is computed at compile time so that it can be taken over unchanged from the trainer's definition [16, commit text].
- Horizontal mirroring: yes, since network #13 [13, network log]. The move information is kept until evaluation so that a mirror-frame change can be detected and a full refresh done [16, commit text].
- Threat or attack inputs: none.
- Pawn features: none.
- Other input relationships: none published.
- Factoriser: not published.

### Body
- Accumulator width per perspective: 1024 [12, README].
- Further layers: 16 and 32, then the output [12, README].
- Layer stacks: the head is written "x8" [12, README].
- Output buckets: 8, "chosen based on remaining material" [16, commit text].
- Skip connections, pairwise multiplication: none published; the architecture string has no pairwise marker.

### Activations
- After the accumulator: SCReLU, computed as a 16-bit multiply by the weight followed by the squaring multiply in 32 bits (the changelog calls it "Lizard's SCReLU formulation") [14, changelog; 16, commit text].
- In the head: "dual activation for L2" from network #23 [13, network log]. Which activations are paired: not published.

### Quantisation
- Integer types per layer: not published (only in code).
- Quantisation-aware training: not published.

### Inference speed
STC is 8+0.08, LTC 40+0.4.
- Accumulator refresh cache: "Accumulator caching (a.k.a. finny tables)", 2026-01; no figure of its own. The 4-bucket net was tested together with it "to avoid getting results that incorporate a significant slowdown from full accumulator refreshes": +17.3 +- 8.3 FN (10,000 nodes), +23.1 +- 8.8 STC, +19.0 +- 7.7 in the network log [13, network log; 16, commit text].
- Lazy updates: each move's pending changes are kept on a stack of accumulators with a stale flag; at evaluation the engine starts from the newest valid entry and applies the changes forward. "A huge speedup": +33.1 +- 11.0 STC (2025-11, single-layer net) [14, changelog; 16, commit text].
- Fused updates: "update NNUE features in a single loop when moving a single piece", +10.7 +- 6.2 [14, changelog].
- Accumulator stack and copy avoidance: "prevent accidental accumulator copies" (both perspectives were being copied on every evaluation), +13.0 +- 6.6 STC. Thread data, including the accumulator stack, is no longer reallocated before each search: +9.0 +- 5.2 at 2 threads, and the 2-against-1-thread advantage rose from 55 to 76 Elo [14, changelog; 16, commit text].
- Pairwise multiplication: not used.
- int8 layers: not published.
- Sparse first dense layer: "NNZ inference and permute the network for sparsity" (credited to Reckless and Hobbes). The figure the commit calls sparsity went from 58.72% to 47.88% by permuting; speed 1,475,423 -> 1,557,100 nps, about 5.5%; +12.1 +- 5.9 STC. Network #25's sparsity loss then took the same figure from 48.11% to 37.54% before and 33.00% after permuting [14, changelog; 16, commit text].
- Evaluation cache: static evaluations are cached in the transposition table (+5.1) and may overwrite entries of old searches (+7.9) [14, changelog]. A separate table: not published.
- SIMD and VNNI: "handwritten SIMD for NNUE output layer", +10.6 +- 5.6. The SCReLU formulation above, +9.2 +- 5.2, with OpenBench speeds of about 1.45 M -> 1.60 M and 1.77 M -> 1.91 M nps on two workers. A SIMD rewrite around one generic implementation with per-architecture primitives was neutral on AVX-512 (-0.2 +- 1.7) and AVX2 (+2.1 +- 3.2). Stepping the inference loops by vector lanes, +4.7 +- 4.5 (non-regression). AVX-512, AVX2 and NEON paths exist, with a fallback where NEON has no dot-product instruction [14, changelog; 16, commit text].
- Memory layout and prefetching: 64-byte alignment of the network weights, +5.5 +- 4.1 [14, changelog]. Nets are downloaded at build time [14, changelog]. Net file size: not published.
- Anything else: making the first layer's weights a multi-dimensional table (the bucket is resolved once per update call), -0.1 +- 2.6, neutral [16, commit text].
- Speed cost or gain of architecture changes: hidden 512 -> 768 on the same data, -6.6 +- 5.5 at time control but +20.8 +- 9.5 at 40,000 fixed nodes; it passed (+27.1) only with a higher result share. 768 -> 1024 with nothing else changed, -2.3 +- 3.8; with a longer schedule +9.4 [13, network log].
- Hardware sensitivity: not published beyond the AVX-512 and AVX2 tests above.

### Training data
- Size: no total is published. Stated pieces: network #11 "an entirely new dataset" at 5,000 soft nodes without tablebase adjudication (size not given); +416 M positions at 20,000 soft nodes (#15); +2.1 B (#16); +185 M DFRC (#17); +1 B at 5,000 soft nodes (#25) [13, network log]. The published data set is 19.7 GB [17, other].
- Type: own self-play only, "from earlier versions of Tcheran", first by an internal generator, now by OpenBench data generation; published on Hugging Face (access needs a login and acceptance of conditions; no dataset card) [12, README; 13, network log; 17, other; 18, TCEC].
- Openings, filtering, tablebase use: the first set was depth-8 searches without tablebases; then 5-man tablebases; no tablebase adjudication from network #11; viriformat storage and filtering from network #7; DFRC start positions can be generated [13, network log; 14, changelog].

### Training recipe (concepts only)
- Trainer: bullet (Jamie Whiting) [12, README; 18, TCEC]. Some nets were trained by other people: the README thanks JonathanHallstrom, and a commit thanks "swedishchef" for network #19 [12, README; 16, commit text].
- Loss and target: a blend of search score and game result; the result share was raised in steps over the history. Network #25 adds a sparsity loss term [13, network log].
- Stages and schedule: a result-heavier fine-tune stage since network #14 (+5.0); a result-share ramp in the first stage lost (-7.0 +- 4.6); a "much longer" schedule "about half way between my existing one and Hobbes'" at network #18 (+14.2) [13, network log].
- Optimiser: Ranger instead of AdamW, +3.5 +- 2.8 (#20) and +4.5 +- 3.3 again on the multi-layer net (#22) [13, network log].

### Measured gains for network changes
All [13, network log]; the log does not give each figure's time control (the commits give both for some).
- 8 output buckets (#12): +9.9 +- 5.6 (STC) [16, commit text].
- Horizontal mirroring (#13): +7.5 +- 4.6 (LTC; +9.0 STC) [16, commit text].
- Result-heavier fine-tune (#14): +5.0 +- 3.6.
- +416 M positions at 20,000 soft nodes (#15): +19.2 +- 7.6.
- 4 king buckets with +2.1 B positions (#16): +19.0 +- 7.7.
- DFRC data (#17): +91.1 +- 19.0 in DFRC.
- Longer schedule (#18): +14.2 +- 6.6.
- 4 -> 8 king buckets (#19): +2.95 +- 2.37 (LTC) [16, commit text].
- Ranger (#20): +3.5. Multi-layer head (#21): +16.5 +- 7.1. Ranger again (#22): +4.5. Dual activation (#23): +7.2 +- 4.5 (LTC; +8.4 at 25,000 fixed nodes) [16, commit text].
- +1 B positions and a sparsity loss (#25): +16.0 +- 7.1 LTC, +19.9 STC, +10.7 at 30,000 fixed nodes [16, commit text].
- 14.0 against 13.0 overall: +65.3 +- 5.7 STC, +57.2 +- 10.5 LTC [15, release notes].

### Architecture history
- 6.0 (2025-10): first net "(768->256)x2->1" on about 100 M positions, +223.7 [13, network log; 14, changelog].
- 8.0: 384 -> 512 -> 768 wide on a 1 B set [13, network log].
- 9.0: 1024 wide [13, network log].
- 11.0 (2026-02): new 5,000-soft-node data; 8 output buckets; mirroring; fine-tune stage [14, changelog].
- 12.0: 20,000-soft-node add-on [14, changelog].
- 13.0 (2026-07): 4 then 8 king buckets; multi-layer head; dual activation; Ranger [14, changelog].
- 14.0 (2026-10-14): network #25; sparse first dense layer [14, changelog].

### Since the rated version
- No network change in the unreleased section of the changelog [14, changelog].

### UNVERIFIED and not published
- King-bucket layout (only in code).
- Which activations the dual activation pairs (not published).
- Integer types per layer; quantisation-aware training (not published).
- Total data size (not published as a total).
- A gain figure for the refresh cache alone (not published).
- Net file size (not published).

---

## Seer 2.8.0 (CCRL #43-44, 3696)

**How it differs from the usual design** [23, TCEC; 20, README; 24, forum]:
1. it predicts **win, draw and loss probabilities** (three outputs through a softmax), not one score;
2. the layers after the first are **floating point**, not quantised;
3. the head uses **dense, concatenating skip connections**;
4. its inputs are **HalfKA**, which the author says Seer used first;
5. its first net came from **retrograde learning out of 6-man tablebases**, with no other engine's evaluation anywhere in the chain;
6. it keeps a **hash table of network outputs** (an evaluation cache) and a **refresh cache**, and corrects the evaluation with a history keyed on a locality-sensitive hash of its hidden layers.

**One-line architecture:** assembled, and incomplete: HalfKA inputs -> a feature transformer per side -> a small floating-point head with dense skip connections -> 3 outputs (W, D, L). The layer widths of the 2.8.0 net are UNVERIFIED (only in code). The only published widths are "160x2" for the first layer in 2021 [24, forum; 27, PR titles] and "2x1024" for a net merged in 2024-11, after the rated version [27, PR text].

### Inputs
- Feature set: HalfKA: each feature is a (own king square, piece, square) combination, kings included [23, TCEC; 24, forum]. Inputs per perspective: not published.
- King input buckets: none in the bucket sense; HalfKA uses the king square itself. Any grouping of king squares: not published.
- Horizontal mirroring: a training PR of 2021 lists "add mirroring" among its commit titles [27, PR text]; what is mirrored, and whether inference mirrors, is not published (UNVERIFIED).
- Threat or attack inputs: none published.
- Pawn features: none published.
- Other input relationships: none published.
- Factoriser: the 2021 training used "dropout regularization and factorization", which the author says removed most problems of training on few positions [24, forum].

### Body
- Accumulator width per perspective: 160 in 2.0.x (2021), then an "asymmetric feature transformer" [24, forum]. In 2021-11 the two sides came to share one set of feature-transformer weights ("shared-affine") [27, PR text]. Five PRs named "fat-seer" followed (2022-02, 2022-04, 2022-09 and 2023-05 before 2.8.0; 2024-11 after it). The name suggests larger nets, but only the last says what grew: the first layer, to 2x1024 [27, PR text; 28, commit text]. The 2.8.0 width: UNVERIFIED (only in code).
- Further layers: "the topology of the subnetwork above the feature transformer is fairly different" from Stockfish's [24, forum]; count and widths not published.
- Layer stacks: 1.1 (2020) introduced "phased" networks that take the game phase into account, about twice as fast at similar training accuracy [25, forum]. Whether 2.8.0 still has them: not published.
- Output buckets: none published; the output is 3 scalars, softmaxed to win, draw and loss probabilities [24, forum; 20, README].
- Skip connections: dense, concatenating skip connections [23, TCEC].

### Activations
- After the accumulator and in the head: not published. A 2020 commit fused the ReLU into the affine transform [28, commit text].

### Quantisation
- Integer types per layer: the feature transformer is quantised (PR "quantized-ft", 2022-04); everything after the first layer stays floating point, which the author lists as a Seer novelty [23, TCEC; 28, commit text]. Until 2022 the whole net was 32-bit float [22, CPW; 25, forum]. Bit width of the quantised part: not published.
- Rounding care: quantised weights are embedded directly since 2023-10, tested neutral (+0.0 +- 2.8) [28, commit text]. Quantisation-aware training: not published.
- Why float was chosen (2020): single-precision speed is close to 32-bit integer speed on modern processors, and float makes skip connections and mixed layer types easy to try. Its cost was that incremental updates could not be undone exactly, so accumulators were copied on the stack at every ply [25, forum].

### Inference speed
STC is 8+0.08 and LTC 40+0.4 unless noted. Most figures are from the squash-commit messages of pull requests whose descriptions are empty, so what each change does is known only from its title.
- Accumulator refresh cache: "feature-reset-cache" (2023-06), +10.7 +- 6.5 STC, +5.8 +- 4.3 LTC [28, commit text].
- Lazy updates: "lazy accumulator update, larger eval cache" (2022-04), +3.7 +- 2.9 STC, +1.9 +- 1.5 LTC [28, commit text].
- Fused updates: "towards optimized accumulator updates" +2.3 +- 1.8 STC, +1.6 LTC; "optimized accumulator updates" (with AVX-512 and fallback versions) +5.2 +- 4.0 STC, +5.6 +- 3.5 LTC (2023-06) [28, commit text]. Whether these are add-sub fusions: not published.
- Accumulator stack: copies per ply in 2020 (above); later form not published.
- Pairwise multiplication: not published.
- Quantised feature transformer: "quantized-ft" (2022-04), +41.0 +- 11.8 STC, +21.9 +- 7.2 LTC; "quantization-experiment" (2022-08), +20.9 +- 9.7 STC, +21.5 +- 9.5 LTC [28, commit text].
- Sparse first dense layer: not published. The inference "elides the feature transformer output copy by transposing the L1 layer weights" [23, TCEC]. A 2020 commit fused the ReLU into the affine transform for a 10 to 20% speed-up and notes that the sparsity of the inputs can be used to speed up the first layer [28, commit text].
- Evaluation cache (a hash table of network outputs): added 2021-03, +23.6 +- 10.4 at 10+0.1 and +25.6 +- 10.0 at 60+0.6; not resetting it between searches +6.2 STC, +4.2 LTC; prefetching it +4.1 and +5.1 STC (two PRs, 2021-11) [27, PR text; 28, commit text].
- SIMD and VNNI: "optimize-simd-dot-product" +11.1 +- 5.7 STC, +10.2 LTC; "optimize-matmul" +18.6 +- 9.1 STC, +10.5 +- 6.3 LTC; "vectorization experiment" +12.0 STC, +11.2 LTC; "towards-optimized-ft" +10.1 STC, +7.3 LTC; "optimized-ft" +34.7 +- 12.5 STC, +23.8 +- 10.1 LTC (all 2022). AVX-512 support twice (no figures); SSSE3 support; ARM through an SSE-to-NEON translation layer [28, commit text; 27, PR titles; 22, CPW]. The code uses OpenMP SIMD directives and intrinsics [20, README]. In 2020 the AVX2 builds with FMA gave slightly different evaluations from the others [25, forum].
- Memory layout and prefetching: prefetch of the evaluation cache (above). Net file size: forum members quote 108 MiB for the float weights file of 1.0 (2020) and about 60 MB for the 2.0.x net; the 2.8.0 size is not published [25, forum; 24, forum].
- Anything else: 2.6.0 and 2.7.0 each credit "optimizations to the network inference implementation" with about half and a third of their gains (about +100 and +50 Elo in self-play) [21, release notes].
- Speed cost or gain of architecture changes: 1.1's architecture optimisation gave 50 to 100% more nps and more accuracy [21, release notes]. The "fat-seer" steps: +10.2 +- 2.5 LTC (2022-02), +4.9 and +7.9 LTC (2022-04), +5.0 STC and +6.8 LTC (2022-09), +2.6 +- 1.8 at 60+0.6 (2023-05) [28, commit text].
- Hardware sensitivity: in 2020 the author reported 600-700 knps locally, about 50 to 60% of the speed of other engines of the time, and disproportionately good results on his own processor; on 2.0.0, 800-1000 knps [25, forum; 24, forum].

### Training data
- Size: the seed stage used about 700 million positions sampled from human Lichess games (positions only; the labels are independent of those games' results), of which about 20 million had 6 men or fewer [24, forum]. The size of the later self-play data behind 2.8.0: not published.
- Type: own. Seed labels by retrograde learning: positions with 6 men or fewer get tablebase win/draw/loss values; then, for each piece count N from 7 to 32, a net trained on everything already labelled plays each quiet N-man position out by search to a quiet position with fewer men, whose static win/draw/loss prediction becomes the label. One net is carried through all piece counts. Since 2.2.0 the nets come from "many self play iterations" starting from that seed net [20, README; 21, release notes; 23, TCEC; 24, forum].
- Openings, filtering, tablebase use: only quiet positions are labelled in the seed stage; playouts can run 30 moves deep [24, forum]. Self-play openings, search budget and filtering: not published.

### Training recipe (concepts only)
- Trainer: the author's own PyTorch code (seer-training); the repository has no README [20, README; 23, TCEC; 29, other].
- Loss and target: win/draw/loss probabilities. 2.3.0 trained on a mixture of game result and search score, "far superior" in the author's tests; 2.8.0's net is fine-tuned on the game result alone [21, release notes].
- Stages and schedule: retrograde seed, then self-play iterations, then (2.8.0) a result-only fine-tune: +5.0 +- 4.6 STC and +15.9 +- 9.5 LTC, and a second round +5.6 STC and +5.8 LTC [28, commit text].
- Regularisation and other: dropout and factorisation in the seed stage [24, forum]; "a new regularization scheme" for 2.7.0 [21, release notes]. Optimiser: not published.
- The author's view on targets (2021): shallow-search labels and results of randomised self-play both favour positions with many good moves; long precise playouts give a sharper style [24, forum].

### Measured gains for network changes
- "160x2" layer dimensions (2021-04): +17.3 +- 8.7 at 20+0.2 [27, PR text].
- Shared feature-transformer weights (2021-11): +5.6 +- 4.2 STC, +2.9 +- 2.4 LTC [28, commit text].
- "fat-seer" steps and the result-only fine-tune: as above.
- Seed net against the best Stockfish-data net of 1.x: about 15 Elo weaker (2021) [24, forum].
- 2.8.0 against 2.7.0: +52.2 +- 3.4 LTC [21, release notes].

### Architecture history
- 1.0 (2020-10): own float net trained on Stockfish self-play data [21, release notes].
- 1.1: "phased" nets, 50 to 100% more nps [21, release notes; 25, forum].
- 2.0.0 (2021-04): retrograde-learning net; no Stockfish-derived data; 160x2 first layer, HalfKA, 3 outputs; weights embedded [21, release notes; 24, forum].
- 2.2.0 onward: self-play iterations from the seed net [21, release notes].
- 2021-11: shared feature-transformer weights [27, PR text].
- 2022: quantised feature transformer; several inference optimisations; three "fat-seer" steps [28, commit text].
- 2023: fourth "fat-seer" step; refresh cache; embedded quantised weights; result-only fine-tune; 2.8.0 on 2023-12-31 [28, commit text; 21, release notes].

### Since the rated version
- 2024-11: first layer raised to 2x1024, +15.0 +- 6.6 LTC [27, PR text; 28, commit text].
- 2026-03: work towards dropping the evaluation cache (evaluations cached eagerly), +0.4 +- 0.9 STC; it did not pass its gain bounds but was merged [27, PR text; 28, commit text].
- 2026-11: "misc-optimization" +12.3 STC, +13.9 LTC; "shuffled-net" +0.5 +- 2.4 LTC [28, commit text].

### UNVERIFIED and not published
- Layer widths and head layout of the 2.8.0 net (only in code).
- Activations (not published).
- Bit width of the quantised feature transformer (only in code).
- Whether the phase-dependent structure of 1.1 survives (not published).
- Mirroring at inference (not published).
- Size, openings and search budget of the self-play data (not published).
- What each inference-optimisation PR does (descriptions are empty).
- Net file size of 2.8.0 (not published).

---

## Uralochka 3.41a (CCRL #43-44, 3696)

The README at tag v.3.41 is taken as the description of 3.41a; no separate tag or text for the "a" build exists [30, README; 32, commit text].

**One-line architecture:** as the engine writes it: "(2x(12288x1024))x6", with the input layer "KingArea*Piece*Color*PieceSquare 16*6*2*64"; "a neural network similar to NNUE of the first versions with HalfKP" [30, README at v.3.41].

### Inputs
- Feature set: 12,288 inputs per perspective = 16 king areas x 6 piece types x 2 colours x 64 squares [30, README]. All six piece types are included, so kings are inputs too.
- King input buckets: 16 "king areas". Layout and how it was chosen: not published.
- Horizontal mirroring: not published.
- Threat or attack inputs: none.
- Pawn features: none in 3.41. (A king-and-pawn net existed for one version in 2022, before the full net [32, commit text].)
- Other input relationships: none published.
- Factoriser: not published.

### Body
- Accumulator width per perspective: 1024 [30, README]. 3.40 "increased NN size" (from what, not stated) [31, release notes].
- Further layers: none; the string has only the first layer and the outputs [30, README].
- Layer stacks: none in 3.41.
- Output buckets: 6 ("x6"). What selects one: not published [30, README; prior survey: "6 OB"].
- Skip connections, pairwise multiplication: none in 3.41.

### Activations
- Not published for 3.41. SCReLU arrived in 2025-05, after the rated version [32, commit text].

### Quantisation
- Not published.

### Inference speed
- Refresh cache, lazy updates, fused updates: none in 3.41; all three arrived in 2025-06 (below) [32, commit text].
- Accumulator stack: "implementation of inference in the engine using the accumulator principle" [30, README]; details not published.
- Evaluation cache: the transposition table also caches the evaluation, and the evaluation is stored before a node is cut off (which the author believes was unusual in 2021) [30, README; 33, TCEC].
- SIMD: SSE, AVX2 and AVX-512 builds; the vector code for the output layer follows a principle the author took from Koivisto (credited) [30, README; 33, TCEC].
- Everything else (int8, sparse layer, prefetch, net size, gains, hardware sensitivity): not published.

### Training data
- Size: not published for 3.41. (The later README gives 28 billion positions for 3.42.)
- Type: mixed. Own self-play of previous versions (the very first set was labelled by the hand-crafted evaluation), plus, since 3.40, positions from Uralochka's games against other engines (mainly Stockfish, also Berserk, Igel and others), "evaluated by the current version of Uralochka and used for data diversity" [30, README; 31, release notes; 33, TCEC].
- Label search budget: "ultra-short control (8-9 half-moves)" [30, README]. A node-based generator was added in 2023-01 [32, commit text].
- Openings, filtering, tablebase use: DFRC start positions and a small book of unbalanced positions generated by Uralochka itself [33, TCEC]. Tablebase probing in data generation existed in 2022 [32, commit text]; its role for 3.41: not published.

### Training recipe (concepts only)
- Trainer: the author's own, PyTorch (Keras for early versions), using the sparse feature-transformer class of Stockfish's nnue-pytorch (credited), which made training several times faster [30, README; 33, TCEC].
- Loss and target: "a more complex formula for the final position evaluation" is named as one of the trainer's own ideas [33, TCEC]; nothing more is published.
- Stages, optimiser, regularisation: not published.

### Measured gains for network changes
- 3.40 (larger net, more diverse data, fixes): +82.4 +- 3.2 on a balanced book and +99.8 +- 3.5 on an unbalanced book [31, release notes].
- 3.41 (SPSA tuning, new net, time manager fix): +140.9 +- 5.2 at 10+0.1, +69.0 +- 4.9 at 60+0.6 [31, release notes]. No network-only figure.

### Architecture history
- 2022-04/05: a king-and-pawn net, then a full net replacing the hand-crafted evaluation (3.33) [32, commit text].
- 2023-02: "new NN architecture"; nnue-pytorch's fast feature transformer adopted in the trainer [32, commit text].
- 3.40 (2023-11): larger net; positions from games against other engines [31, release notes].
- 3.41 (2024-05-04): new net; "(2x(12288x1024))x6" [30, README; 31, release notes].

### Since the rated version
- 3.42 (2025-09-06) is written "(2 x (12288 x (1280 + psqt x 6)) -> crelu -> pairwise multiplication + concat: 1280 -> (6 -> screlu -> 32 -> relu -> 1 + psqt) x 6", same inputs: a 1280-wide accumulator with a PSQT output per bucket, pairwise multiplication, and a 6 -> 32 -> 1 head in six copies. Its data set is 28 billion positions from games at 10 to 12 plies, including positions from games against other engines scored by Uralochka. +84.0 +- 3.5 at 10+0.1 and +85.0 +- 4.9 at 60+0.6 over 3.41 [30, README at v.3.42; 31, release notes].
- Commit titles on the way there: SCReLU (2025-05), fused updates (2025-06-02), pairwise multiplication in the first layer (2025-06-22), lazy accumulator updates (2025-06-24), "Finny table" (2025-06-26), multiple hidden layers (2025-07) [32, commit text]. No figures.

### UNVERIFIED and not published
- King-area layout; mirroring (not published).
- What selects the 6 outputs (not published).
- Activation and quantisation of 3.41 (not published).
- Data size for 3.41 (not published).
- Loss, schedule, optimiser (not published).
- Any speed figure (not published).
- Whether "3.41a" differs from the v.3.41 tag (no text found).

---

## Motor 0.9.0 (CCRL #46, 3694)

**One-line architecture:** as the engine writes it: "(768 x 8 -> 1536) x 2 -> 1" [34, README at v0.9.0].

### Inputs
- Feature set: 768 piece-square inputs per king bucket [34, README].
- King input buckets: 8 since 0.8.0 [35, release notes]. Layout: not published. Growth: 6 buckets on a 1024-wide net (2024-07-06, +27.1 +- 9.7 at 10+0.1, +17.7 +- 7.6 at 40+0.4); two days later "3 input buckets" (+3.7 +- 2.9 at 10+0.1); 8 buckets on a narrower, 1024-wide net (2024-09, +3.7 +- 2.4 at 40+0.4) [36, PR text].
- Horizontal mirroring: yes, since 0.6.0 (+25.6 +- 12.2 in the PR's test) [35, release notes; 36, PR text].
- Threat inputs, pawn features, other relationships, factoriser: none published.

### Body
- Accumulator width per perspective: 1536 [34, README; 36, PR text].
- Further layers: none.
- Layer stacks and output buckets: none ("-> 1").
- Skip connections, pairwise multiplication: none published.

### Activations
- SCReLU since 0.4.0 [35, release notes]. Not restated for 0.9.0.

### Quantisation
- Integer types: not published. Two quantisation changes are recorded by title only: one worth +8.2 +- 5.5 (2024-04) and "bigger net with new quantization" +11.1 +- 5.8 at 40+0.4 (2024-06) [36, PR text].
- Rounding care: "stricter weight clipping +8" in 0.7.0 [35, release notes].

### Inference speed
- Refresh cache: not published.
- Lazy updates: none in 0.9.0. Added on 2026-10-25, after the rated version, with no figure ("defer NNUE accumulator copies until evaluation") [36, PR text].
- Fused updates, accumulator stack, int8, sparse layer, evaluation cache, prefetching, net file size: not published.
- SIMD: "custom AVX2 simd" in 0.4.0, put at +40 in the PR (and SCReLU at +40) [35, release notes; 36, PR text]. ARM NEON evaluation added 2026-10-30 [36, PR titles].
- Speed cost or gain of architecture changes: 1024 -> 1536 wide (2024-06, with a quantisation change) +11.1 at 40+0.4; 1536 wide on 3 buckets (2024-07) +11.8 +- 5.9 at 40+0.4; the 0.9.0 net (1536 wide, 8 buckets, bullet) +4.8 +- 2.8 at 60+0.6 [36, PR text].
- Hardware sensitivity: not published.

### Training data
- Size, type, label budget, openings, filtering, tablebase use of the 0.9.0 net: not published (prior survey: unknown). One PR is titled "net trained on some new data" with no description [36, PR text].

### Training recipe (concepts only)
- Trainer: bullet for the 0.9.0 net; earlier nets with the author's own PyTorch trainer "forge" [34, README; 36, PR text; 37, README].
- Loss and target: a loss with an exponent above 2 was adopted in 0.7.0 (+24) and kept, with a different exponent, for the 8-bucket net [35, release notes; 36, PR text].
- Stages and schedule: a fine-tune with the Ranger optimiser, +6.4 +- 4.2 at 10+0.1 (2024-07) [36, PR text].
- Other: not published.

### Measured gains for network changes
- 0.7.0 list: 3 king input buckets +11; the loss change +24; stricter weight clipping +8 [35, release notes].
- 0.9.0 against 0.8.0 overall: +44.2 +- 3.7 at 10+0.1 and +50.5 +- 3.4 at 60+0.6 on an unbalanced book, +21.0 +- 2.2 at 60+0.6 on a balanced book; "most elo comes from correction history experiments" [35, release notes].

### Architecture history
[35, release notes]
- 0.1.0 (2024-02): "(768 -> 32) x 2 -> 1", trainer forge.
- 0.2.0: 64 wide. 0.3.0: 256. 0.4.0: 512, SCReLU, own AVX2 code.
- 0.5.0: 1024. 0.6.0 (2024-06): 1536, horizontal mirroring.
- 0.7.0 (2024-08): 3 king buckets.
- 0.8.0 (2024-10): 8 input buckets (on a 1024-wide net [36, PR text]).
- 0.9.0 (2025-06-02): 1536 wide with 8 buckets, trained with bullet.

### Since the rated version
On a development branch, from 2026-10-30 [36, PR text and titles]:
- the engine's own data generator, compact data format and GPU trainer were added, and the net is downloaded from Hugging Face at build time;
- a restart from nothing: a "768 -> 16 -> 1" net trained on data from a randomly initialised net, then repeated retraining on self-play from 8 random opening plies: 4.95 M positions from 60,000 games; 10.6 M positions from 129,691 games at 25,000 nodes per move (+110.9 at 10+0.1); 42.5 M (+31.0 at 10+0.1, +15.8 at 60+0.6); 114 M with a cosine schedule (+84.4, +74.6); nets described as quantisation-aware trained (+19.4 and +18.2; then +12.1 and +8.1); hidden size raised to 32 on 2026-11-06 (+108.5 at 10+0.1);
- lazy accumulator updates and ARM NEON evaluation (no figures).

### UNVERIFIED and not published
- King-bucket layout (only in code).
- Integer types (not published).
- Everything about the 0.9.0 net's training data (not published).
- Every inference-speed technique except the 2024 SIMD note (not published).
- Net file size (not published).
- Licence: the prior survey found no licence file; not re-checked today.

---

## Renegade 1.3.0 (CCRL #47-49, 3693)

**One-line architecture:** as the engine writes it: "(768x14hm -> 1600)x2 -> 1x8", "a perspective net with input buckets and horizontal mirroring, featuring approximately 17.2 million parameters" [38, README at v1.3.0]. The net in 1.3.0 is Net 36 [40, PR titles]; 1.3.0's notes say the architecture is unchanged from 1.2.0 [39, release notes].

### Inputs
- Feature set: 768 piece-square inputs per king bucket [38, README].
- King input buckets: 14, "based on the king's position" [39, release notes]. Layout: not published. History: first buckets at Net 23 (2024-07, +19.1 +- 10.0 at 8+0.08); 16 buckets at Net 30 (2025-01); 14 at Net 31 (2025-04) [40, PR text].
- Horizontal mirroring: yes, by the king's position, since Net 22 (+13.8 +- 7.6 at 8+0.08; +13.6 at 25,000 fixed nodes) [39, release notes; 40, PR text].
- Threat inputs, pawn features, other relationships: none.
- Factoriser: "input buckets are factorized" from Net 30 [40, PR text].

### Body
- Accumulator width per perspective: 1600 [38, README].
- Further layers: none.
- Layer stacks: none.
- Output buckets: 8, "based on pieces on board" (piece count) [39, release notes; 40, PR text].
- Skip connections, pairwise multiplication: none.
- After the net: the output is scaled by material (1.2.0) and scaled down with the half-move clock (+2.9 +- 2.1 at 10+0.1) [39, release notes; 40, PR text].

### Activations
- SCReLU (stated for 1.0.0; not restated since) [39, release notes].

### Quantisation
- Quantised integer inference; 1.1.0 mentions an "improved order of operations" for its accumulator quantisation [39, release notes]. Integer types: not published.
- Quantisation-aware training: not published.

### Inference speed
- Accumulator refresh cache: "caching accumulators for each bucket (aka Finny tables)", +5.3 +- 3.2 at 3+0.03 (2025-02). Before it, "only recalculate the side-to-move accumulator during a refresh", +12.6 +- 5.3 at 3+0.03 (2024-11) [40, PR text].
- Lazy updates: lost single-threaded, -9.0 +- 4.8 at 10+0.1, but gained at 8 threads, +5.7 +- 3.3 at 5+0.05. The author traced the loss to the transposition-table prefetch becoming less effective; a follow-up that prefetches earlier on a speculative hash recovered +5.5 +- 3.3 at 3+0.03 [40, PR text].
- Fused updates: failed its test (-0.1 +- 1.6 at 4+0.04) although about 5% faster on the author's machine; kept, with a note that its value depends on the machine. Later "fuse update operations for cached accumulators", +3.0 +- 2.1 at 3+0.03 [40, PR text].
- Accumulator stack: not published.
- Pairwise multiplication, int8, sparse layer: none published.
- Evaluation cache: the raw network output is stored in the transposition table [39, release notes].
- SIMD: binaries target x86-64-v3 (BMI2); nothing on AVX-512 or VNNI is published [39, release notes].
- Memory layout and prefetching: huge pages requested where available, +11.5 +- 4.7 at 3+0.03 with 256 MB hash on a many-thread test machine; "shouldn't affect performance on consumer hardware" [40, PR text]. The net is embedded in the binary [42, TCEC]. Net file size: not published.
- Speed cost or gain of architecture changes [40, PR text]:
  - hidden 1024 -> 1408 (Net 29): +28.9 +- 9.1 at 25,000 fixed nodes, +0.5 +- 3.3 at 10+0.1, +7.3 +- 3.9 at 50+0.5;
  - "quadrupled net size" (Net 30: 16 factorised input buckets, 8 output buckets, cosine schedule, 4.16 B positions, 80 hours of training): +7.0 +- 3.8 at 10+0.1, +6.0 +- 3.4 at 50+0.5;
  - Net 31 (14 buckets, 1600 wide, two-stage training, 5.66 B positions): +6.9 +- 3.6 at 10+0.1, +8.1 +- 3.8 at 50+0.5.
- Hardware sensitivity: stated twice (fused updates depend on the machine; lazy updates gain only with threads) [40, PR text].

### Training data
- Size: 8.4 billion positions from 91 million games [39, release notes; 38, README].
- Type: own self-play only, each generation labelled by the engine's own search; the chain began from "a very basic handcrafted king tropism function" [42, TCEC; 39, release notes]. "A large chunk" is published on Kaggle (the page could not be read today) [42, TCEC; 41, other].
- Label search budget: soft node limits of 10,000 and 20,000; the last 5,000-soft-node data were replaced at Net 35 [39, release notes; 40, PR text].
- Openings, filtering, tablebase use: generation from opening books since 1.2.0; a DFRC share of about 15% (928 M positions at 20,000 soft nodes); stored as viriformat, which "allows experimenting with position filtering" [39, release notes; 40, PR text]. Filter rules and tablebase use: not published.

### Training recipe (concepts only)
- Trainer: bullet [38, README; 42, TCEC].
- Loss and target: a blend of score and game result whose result share tapers upward during training; the taper was moved higher at Net 32 [39, release notes; 40, PR text].
- Stages and schedule: cosine schedule since Net 30; two-stage training since Net 31; Net 36 was the first trained on a server rather than a laptop GPU [40, PR text].
- Regularisation, optimiser: not published.

### Measured gains for network changes
[40, PR text]; STC 10+0.1 and LTC 50+0.5 from late 2024, 8+0.08 before.
- Hidden 512 -> 768 (Net 15): +24.8 +- 11.3. 768 -> 1024 (Net 17): +8.1.
- +500 M positions to 1.57 B (Net 16): +18.0 +- 9.8. +470 M to 2.04 B (Net 18): +4.8. +530 M to 2.78 B (Net 21): +6.9. +850 M to 3.6 B (Net 25): +3.4.
- 200 M DFRC positions (Net 20): +117 then +27 in DFRC, +1.1 standard.
- Regenerating the oldest 1 B positions: +12.2 +- 8.0 (Net 24), +16.2 +- 6.5 (Net 26); a further 1 B and all FRC data (Net 28): +3.8 standard, +10.2 FRC.
- Net 32 (oldest two sets replaced by 10,000-soft-node data, higher result share): +7.1 +- 3.7 STC, +7.9 +- 3.8 LTC.
- Net 33 (oldest 1.1 B replaced): +9.7 +- 4.3 STC, +11.8 +- 4.7 LTC.
- Net 34 (DFRC set regenerated at 20,000 soft nodes, 6.04 B total): +42.3 DFRC, +2.7 STC, +7.7 +- 3.7 LTC.
- Net 35 (last 5,000-soft-node data replaced, 6.30 B total): +6.8 +- 3.5 STC, +11.7 +- 4.7 LTC.
- Net 36 (one set replaced by 30.75 M games at 20,000 soft nodes): +2.9 +- 2.1 STC, +2.9 +- 2.0 LTC; "smaller than expected", which the author puts down to saturation of the architecture or the training setup.
- 1.3.0 against 1.2.0 overall: +78.3 STC, +91.6 LTC [39, release notes].

### Architecture history
[39, release notes; 40, PR titles]
- 1.0.0 (2024-01): "768->512x2->1", SCReLU, 640 M positions.
- 1.1.0 (2024-06): "(768->1024)x2->1", 2.78 B positions.
- 2024-07: mirroring (Net 22), king buckets (Net 23). While the mirroring code was being written a Motor net was used as a stand-in; the merged net was self-trained (commit titles in the PR) [40, PR text].
- 2024-10: 1408 wide (Net 29).
- 2025-01: 16 factorised input buckets, 8 output buckets (Net 30).
- 1.2.0 (2025-05): 14 buckets, 1600 wide, 5.6 B positions, "over 20 times as large" as 1.1.0's net.
- 1.3.0 (2026-06-17): same architecture, data fully regenerated (Nets 32 to 36).

### Since the rated version
- 1.3.1 (2026-07-14): two bug fixes, no network change [39, release notes]. No network PR since [40, PR titles].

### UNVERIFIED and not published
- King-bucket layout (only in code).
- Integer types; quantisation-aware training (not published).
- Filter rules, tablebase use in generation (not published).
- Optimiser (not published).
- Net file size (not published).
- The Kaggle data description (page blocked by a browser check).

---

## Sources

All opened on 2026-11-14.

| # | URL | What it is | Type | Used for |
|---|---|---|---|---|
| 1 | https://raw.githubusercontent.com/mhonert/velvet-chess/HEAD/README.md | Velvet README | README | Velvet |
| 2 | https://github.com/mhonert/velvet-chess/releases (pages 1-3) | Velvet release notes, 1.2.0 to 9.0.0-dev7 | release notes | Velvet |
| 3 | https://www.chessprogramming.org/Velvet | CPW page (no network detail beyond "NNUE since 2.0.0") | CPW | Velvet |
| 4 | https://wiki.chessdom.org/Velvet_questionnaire_20251017 | TCEC questionnaire | TCEC | Velvet |
| 5 | GitHub API, commit-message search in mhonert/velvet-chess (9 queries: quantized, 8-bit, bucket, avx512, network architecture, training data, NN, neural network, hidden layer) | commit titles and bodies, no diffs | PR / issue / commit text | Velvet |
| 6 | https://raw.githubusercontent.com/enfmarinho/Minke/HEAD/README.md and .../v7.0.0/README.md | Minke README, current and at the rated tag | README | Minke |
| 7 | https://raw.githubusercontent.com/enfmarinho/MinkeNets/HEAD/history.txt | Minke's network log (minke0 to minke44) | other (network log) | Minke |
| 8 | https://github.com/enfmarinho/Minke/releases | Minke release notes | release notes | Minke |
| 9 | https://github.com/enfmarinho/Minke/pulls?q=is:pr+is:closed (pages 1-10) and ...pulls?q=is:pr+finny | PR title lists | PR / issue / commit text | Minke |
| 10 | https://github.com/enfmarinho/Minke/pull/N for N = 6, 54, 77, 91, 92, 102, 136, 146, 148, 164, 168, 173, 190, 204, 205, 209, 213 | PR conversation pages (description, commit titles) | PR / issue / commit text | Minke |
| 11 | https://raw.githubusercontent.com/enfmarinho/MinkeNets/HEAD/README.md and https://github.com/enfmarinho/MinkeNets | MinkeNets README (one line) and repository page | README | Minke |
| 12 | https://raw.githubusercontent.com/tcheran-chess/tcheran/HEAD/README.md and .../v14.0/README.md | Tcheran README | README | Tcheran |
| 13 | https://raw.githubusercontent.com/tcheran-chess/tcheran/HEAD/NET.md and .../v14.0/NET.md (identical) | Tcheran network history | other (network log) | Tcheran |
| 14 | https://raw.githubusercontent.com/tcheran-chess/tcheran/HEAD/CHANGELOG.md | Tcheran changelog | release notes | Tcheran |
| 15 | https://github.com/tcheran-chess/tcheran/releases | Tcheran release page | release notes | Tcheran |
| 16 | GitHub API, commit-message search in tcheran-chess/tcheran (11 queries: NNZ, sparsity, accumulator, finny, buckets, mirroring, SIMD, multi-layer, dual activation, Network datagen, SCReLU) | commit titles and bodies, no diffs | PR / issue / commit text | Tcheran |
| 17 | https://huggingface.co/datasets/jgilchrist/tcheran (gated, no dataset card, 19.7 GB); .../raw/main/README.md returned 401 | Tcheran's public data set | other | Tcheran |
| 18 | https://wiki.chessdom.org/Tcheran_questionnaire_20260616 | TCEC questionnaire | TCEC | Tcheran |
| 19 | https://github.com/tcheran-chess/tcheran/pulls?q=is:pr+is:closed | PR list (one PR, not network) | PR / issue / commit text | Tcheran |
| 20 | https://raw.githubusercontent.com/connormcmonigle/seer-nnue/HEAD/README.md | Seer README | README | Seer |
| 21 | https://github.com/connormcmonigle/seer-nnue/releases (pages 1-2) | Seer release notes | release notes | Seer |
| 22 | https://www.chessprogramming.org/Seer | CPW page | CPW | Seer |
| 23 | https://wiki.chessdom.org/Seer_questionnaire_20251030 | TCEC questionnaire | TCEC | Seer |
| 24 | https://www.talkchess.com/forum3/viewtopic.php?f=2&t=77187 (start = 0 to 110; start=100 failed once, then loaded) | TalkChess thread "Seer 2.0.0", 2021-2024, posts by the author | forum | Seer |
| 25 | https://www.talkchess.com/forum3/viewtopic.php?f=2&t=75433 (start = 0 to 120) | TalkChess thread "Seer", 2020 | forum | Seer |
| 26 | https://www.talkchess.com/forum3/viewtopic.php?f=2&t=75890&start=10 (start=0 failed to load) | TalkChess thread on NNUE development, 2020; nothing used | forum | Seer |
| 27 | https://github.com/connormcmonigle/seer-nnue/pulls?q=is:pr+is:closed (pages 1-9) and /pull/N for N = 2, 4, 12, 14, 39, 87, 95, 97, 103, 105, 119, 123, 124, 125, 132, 134, 135, 139, 141, 143, 144, 152, 156, 157, 161, 162, 173, 176, 177, 196, 205, 209, 210 | PR titles and conversation pages (most descriptions empty) | PR / issue / commit text | Seer |
| 28 | GitHub API, commit-message search in connormcmonigle/seer-nnue (12 queries) | squash-commit titles and bodies (test results), no diffs | PR / issue / commit text | Seer |
| 29 | https://github.com/connormcmonigle/seer-training and /releases; README.md returned 404 | trainer repository page (no description) and release list (bodies not read: code-like blocks were dropped unread) | other | Seer |
| 30 | https://gitlab.com/freemanzlat/uralochka3/-/raw/TAG/README.md for TAG = v.3.41, main, v.3.42, v.3.40 (v.3.39, v.3.38, v.3.36, v.3.33 are empty stubs) | Uralochka README at several tags | README | Uralochka |
| 31 | https://gitlab.com/api/v4/projects/freemanzlat%2Furalochka3/releases | Uralochka release notes 3.40 to 3.42 | release notes | Uralochka |
| 32 | https://gitlab.com/api/v4/projects/freemanzlat%2Furalochka3/repository/tags and .../repository/commits (pages 1-3) | tag list and commit titles, no diffs | PR / issue / commit text | Uralochka |
| 33 | https://wiki.chessdom.org/Uralochka_questionnaire_20251107 | TCEC questionnaire | TCEC | Uralochka |
| 34 | https://raw.githubusercontent.com/martinnovaak/motor/HEAD/README.md and .../v0.9.0/README.md (identical) | Motor README | README | Motor |
| 35 | https://github.com/martinnovaak/motor/releases | Motor release notes 0.1.0 to 0.9.0 | release notes | Motor |
| 36 | https://github.com/martinnovaak/motor/pulls?q=is:pr+is:closed (pages 1-10) and /pull/N for N = 66, 71, 89, 105, 113, 116, 122, 130, 149, 164, 201, 206, 211, 213, 214, 217, 219, 220, 221, 222, 223, 224, 225 | PR titles and conversation pages | PR / issue / commit text | Motor |
| 37 | https://raw.githubusercontent.com/martinnovaak/forge/HEAD/README.md | README of Motor's old trainer (one line) | README | Motor |
| 38 | https://raw.githubusercontent.com/pkrisz99/Renegade/HEAD/README.md and .../v1.3.0/README.md (differ only in a version line) | Renegade README | README | Renegade |
| 39 | https://github.com/pkrisz99/Renegade/releases (page 1 read; page 2 fetched, not read) | Renegade release notes | release notes | Renegade |
| 40 | https://github.com/pkrisz99/Renegade/pulls?q=is:pr+is:closed (pages 1-8) and /pull/N for N = 16, 17, 18, 25, 27, 29, 31, 33, 35, 37, 42, 56, 59, 60, 67, 68, 72, 76, 79, 115, 124, 126, 130, 131, 136, 139, 142, 147, 158, 159 | PR titles and conversation pages | PR / issue / commit text | Renegade |
| 41 | https://www.kaggle.com/datasets/pkrisz/renegade-chess-engine-training-data-viriformat | Kaggle data set page: browser check with curl; only the page title through the fetch tool | other (failed) | Renegade |
| 42 | https://wiki.chessdom.org/Renegade_questionnaire_20251015 | TCEC questionnaire | TCEC | Renegade |
| 43 | https://wiki.chessdom.org/Engines_by_TCEC_Questionnaire; and https://wiki.chessdom.org/NAME for the seven engine names (all 404) | questionnaire index; failed engine-page probes | TCEC | all |
| 44 | Two web searches (Velvet and Uralochka on TalkChess); results were blogs and unrelated threads; nothing opened or used | web search | other | Velvet, Uralochka |
| 45 | the agent's scratch folder (engines.md, sources.md, comparison.md sections H-K, provenance.md) | the survey of 2026-11-10 | prior survey | all |

GitHub API use: 36 calls in total (32 commit-message searches, 4 quota checks); the core quota was 4,558 at the last check.

Credit lines (author as the page names them; licence as the page states it):
- Velvet: Martin Honert; GPL v3 [1, 4].
- Minke: enfmarinho (GitHub); licence badge only on the README, GPL-3.0 per the prior survey [6].
- Tcheran: Jonathan Gilchrist (jgilchrist); GNU AGPL v3.0 [18].
- Seer: Connor McMonigle; GPL-3.0 [23].
- Uralochka: Ivan Maklyakov; GNU GPL v3.0 [30, 33].
- Motor: Martin Novak (martinnovaak); no licence stated on the pages opened [34].
- Renegade: Krisztián Peőcz (pkrisz99); MIT [42].
- Chess Programming Wiki: CC BY-SA 3.0 [3, 22]. TCEC wiki: CC BY-SA 3.0 [4, 18, 23, 33, 42]. TalkChess posts belong to their authors [24, 25].

## Clean-room statement

I opened no source file, header, build file, training script, trainer configuration, network-loading code, diff, patch, "Files changed" tab, blame view, code-search result or network file, of any engine or trainer. I cloned and downloaded no repository, release archive, binary or network file. Everything saved in my folder is the HTML, Markdown or JSON of the prose pages listed above, plus four small helper scripts of my own (`tools\h2t.py`, `tools\rel.py`, `tools\prbody.py`, `tools\pr.sh`). `report.md` does not exist: the Write tool refused it and I did not write it another way.

What came close:

- **Pull-request pages.** Only the conversation tab was fetched. It lists commit titles next to the description; no diff was requested.
- **Commit messages.** Read through the commit-search API (GitHub) and the commit-list API (GitLab), which return titles and bodies without patches. Some of Tcheran's messages name identifiers from its code; none is recorded.
- **Code fragments on prose pages.** My converter replaces code-looking preformatted blocks with a marker before I see them (README build commands, a command block in a forum post, the bodies of the seer-training releases). Two short code fragments in the Uralochka TCEC questionnaire are inline text, so they did appear in my output; I did not use or transcribe them.
- **Hyperparameter values.** Minke's network log, Tcheran's network log and changelog, and several PR titles show learning rates, result-blend weights, quantisation scales, a loss exponent and a few search constants. I saw them and recorded none; they are described as concepts only.
- **Motor PR #214** shows a network file's checksum in a commit description; not recorded.

Deleted: nothing. Edited: only files I created in my own folder. Nothing was written to the user's repository or the kb worktree, and nothing was committed.
