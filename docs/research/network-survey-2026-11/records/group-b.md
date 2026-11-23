# Network records, group B: Triumviratus, Obsidian, PlentyChess, Coda, Reckless, Incipit

Clean-room network survey of 2026-11-14 ([README](../README.md)). Written by survey agent B from public prose only and assembled unchanged except for local paths. Source numbers in brackets refer to the Sources table at the end of this file. Every engine here is REFERENCE ONLY for ideas; its code, nets and data are OFF-LIMITS for Fork.


Engines: Triumviratus 8.1, Obsidian 16.0, PlentyChess 8.0.0, Coda 0.9.4, Reckless 0.9.0, Incipit 0.6.0. Every fact below comes from a page opened on 2026-11-14 (numbered in "Sources") or is marked "prior survey" (the survey of 2026-11-10 in `docs/research/engine-survey-2026-11/`). Source types used in the tags: README, prose doc (a docs-folder document), release notes, PR text, commit text, TCEC, forum, release asset list (file names and byte sizes shown by a release page; no file was downloaded).

Reading notes that apply throughout:

- "FN" = fixed nodes; "STC" and "LTC" as each engine defines them. The time control is given with each figure.
- Elo figures are each project's own self-play measurements, mostly on unbalanced (UHO) books, so they are not comparable across engines.
- "Inference by arithmetic" marks a number I derived from published sizes. It is not a statement by the project.

---

## Triumviratus 8.1 (CCRL #2, 3796)

**One-line architecture:** assembled from the fields below (the project writes it as a table and a trainer feature-set name, not as one string): (threats 59,808 + king-relative piece-square 22,528 x 8 material "experts" per perspective + pawn pairs 4,560 + passed pawns 96 -> 1024) x 2 -> 32 -> 32 -> 1, with 8 layer stacks chosen by piece count, a PSQT output kept, and a 256 -> 256 -> 32 pawn-king subnetwork added into the first head layer. Architecture name "TRANN4", network "Consilium Plebis". [2, prose doc] [9, README]

### Inputs
- Feature set (what an input means; inputs per perspective if stated): Stockfish's SFNNv16 input set (threat inputs, king-relative piece-square inputs, pawn pairs) with two additions of the project's own: a passed-pawn block and material-routed copies ("experts") of the king-relative block. Total 244,688 inputs, plus 256 for the pawn-king subnetwork. [9, README] The 8.0 net had 154,576 (4 experts); the 7.0 net 86,992 (no experts). [2, prose doc]
- King input buckets: 32 on the king-relative block, 704 piece-square inputs per bucket, so 22,528 rows per expert. [11, prose doc] Which squares share a bucket is not described in the pages opened; by name it is Stockfish's mirrored king-relative set, inherited with the SFNN architecture. [2, prose doc]
- Horizontal mirroring: yes, by the feature set's name. The exact rule is not restated in prose: UNVERIFIED (only by reference to Stockfish's set). [2, 7, prose doc]
- Threat or attack inputs: Stockfish's full threat block, 59,808 inputs (which piece attacks which piece on which squares), int8 rows, updated incrementally from the move's changes. [2, prose doc] Per node the 8.0 engine read 6.54 threat rows and 2.83 king-relative rows on its bench. [11, prose doc]
- Pawn features:
  - Pawn pairs, 4,560 inputs: pairs of pawns on the same or adjacent files (idea credited to Jonathan Hallstrom, Pawnocchio; Stockfish's three-file-wide form). [2, prose doc]
  - Passed pawns, 96 inputs: one per passed pawn, 48 oriented squares per side. A pawn is passed when no enemy pawn is ahead on its own or adjacent files and no own pawn is directly ahead. It encodes only the square, is added to the threat accumulator and reuses the pawn-event update. [3, prose doc]
  - New in 8.1: the pawn-king subnetwork (see Body). [2, prose doc]
- Other input relationships (material routing), the engine's distinctive part:
  - 8.0 ("Consilium"): the king-relative block has 4 weight sets chosen by total piece count, kings and pawns included: up to 9, 10-15, 16-23, 24 or more (equal-frequency bins on the training corpus). One set serves both perspectives. A capture that crosses a boundary forces an accumulator refresh. [2, prose doc]
  - 8.1 ("Consilium Plebis"): 8 weight sets **per perspective**, each chosen by the non-pawn material that side is **facing**. The key is a pair of material signatures (own, opponent). A signature counts knights, bishops and rooks capped at two each and the queen capped at one: 54 values, 2,916 cells. A table stored in the net file maps each cell to one of 8 sets. [2, 10, prose doc]
  - The starting table uses the opponent's non-pawn material in textbook points (minor 3, rook 5, queen 9) in eight classes: 0-3, 4-5, 6-8, 9, 10-13, 14-18, 19-25, 26-31 (equal frequency on game positions). Pawn moves and pawn captures never change the set; only a non-pawn capture or a promotion can. [2, 10, prose doc]
  - Why the change: with piece-count bands a pawn more or less could move a position to another set, and both sides read a materially unbalanced position with the same set. [2, prose doc] On game lines, the share of legal captures that change the set fell from 0.262 (old rule) to about 0.108 for a per-perspective opponent-material rule. Pawn-count buckets were rejected (0.482). [11, prose doc]
  - The table can be learned in training (a hard EM step with a budget on how often a capture changes set), but in the released run it moved fewer than 1% of its cells (17-19 of 2,916). In practice the fixed material classes decide. [2, 10, prose doc]
  - No queen buckets in 8.1 (an explicit author decision). [10, 11, prose doc]
- Factoriser or other training-only input structure: each expert's weights are trained as a shared base (per king bucket, shared by all experts) plus a per-expert delta starting at zero, plus the trainer's usual virtual (factorised) king-bucket features. Export folds them into plain weight sets, so a rarely used expert falls back to the base. [2, 3, prose doc]

### Body
- First hidden layer (accumulator) width per perspective: 1024. [2, prose doc]
- Further layers: two, of width 32 and 32 ("L1 / L2 / L3 = 1024 / 32 / 32"), unchanged from 7.0 and 8.0. [2, prose doc]
- Layer stacks: 8, chosen by piece count (four pieces per stack). [2, prose doc]
- Output buckets: the 8 layer stacks are the output buckets. A PSQT output is kept (8 values at the end of every feature row). [2, 10, prose doc]
- Skip connections, pairwise multiplication, other structure:
  - Pairwise multiplication of the accumulator exists (the passed-pawn note relies on "the pairwise product of the first layer"). [3, prose doc]
  - Pawn-king subnetwork (new in 8.1): inputs from the side to move's view are own pawns, enemy pawns, own king, enemy king (64 squares each, at most 18 active); 256 hidden units; 32 outputs added to the 32 outputs of the chosen stack's first layer before its activations. [2, 10, prose doc] In the release it is computed only with at most one minor piece and no rook or queen on the board; elsewhere its mean output is used. [6, release notes]
  - The head is otherwise Stockfish's SFNNv16 head. Its internal skip and activation details are not restated in prose: UNVERIFIED (only by reference).

### Activations
- After the accumulator: clipped activation with a pairwise product. [3, prose doc] Exact form: UNVERIFIED (not restated in prose).
- In the head: not described beyond "as in Stockfish". The pawn-king hidden layer is a clipped linear unit. [2, prose doc]

### Quantisation
- Integer types per layer: all feature-transformer rows int8 in 8.1 (king-relative rows were int16 in 8.0; threats, pawn pairs and passed pawns were already int8). PSQT columns are not clipped to int8. Pawn-king subnetwork: int16 first-layer weights, int8 second-layer weights, int32 bias. The stacks are int8. [2, 10, 11, prose doc]
- Quantisation-aware training or other rounding care: the merged weight (base + expert delta + virtual feature) is clamped to the int8 grid during training, so export needs no correction. The trainer keeps the pawn-king weights on the integer grid, so the engine's integer form is exact. A Python integer evaluator had to match the trainer, and the engine had to match that evaluator, before and after the run. [2, 10, prose doc]
- What failed before training with a clamp (the 8.0 net had 1.57-1.65% of weights outside int8) [7, 11, prose doc]:
  - a per-row scale cost no measurable strength in precision (+2.78 +- 6.49 over 3,124 games, still int16), but its 8-bit path lost depth because the per-row multiply ate the bandwidth gain (-20.4 +- 23.8 over 222 games);
  - int8 with sparse exact corrections ran 7.8% more cycles;
  - plain clamping of the trained net changed the eval too much.

### Inference speed
Method: every speed change is checked at an identical search tree and measured with hardware counters (cycles and instructions per node) on a dual Xeon Gold 6138 and a Zen 4 laptop. [6, release notes] [7, prose doc] Up to 8.0 the inference code was ported from Stockfish; 8.1's is "written from a specification". [1, README]

- Accumulator refresh cache: yes ("Finny table"), kept per expert; 1.1 MB per thread for 4 experts, 2.3 MB projected for 8. [2, 11, prose doc]
  - Comparing a cache entry with the position by a branch-free bitboard operation cut the extra mispredictions of a rewrite from +6.2% to +1.9%. [7, prose doc]
  - 8.1 (contribution): the refresh skips the write-back of unchanged cache entries (part of a bundle, see SIMD). [4, prose doc]
- Lazy or deferred accumulator updates:
  - Since 5.1 the work a move causes for the network is deferred until an evaluation needs it: +26 to +42 Elo by time control, bundled with a native-tuned PGO build. [5, prose doc]
  - In 8.0 the make records only the moved piece. Before an evaluation the pending moves are undone on local copies and replayed; usually one move is pending. A fully eager variant (threat changes computed in every make) cost +2.7% instructions per node. [7, prose doc]
  - 2.16 accumulator updates per evaluation against a minimum of about 2. [7, prose doc]
- Fused updates: "both perspectives together" on AVX-512: +0.80% nps (8.0). [7, prose doc] 8.1 on AVX2: the second perspective's rows are gathered after the first one's update (part of the 1.7-3.2% instruction saving under SIMD). [4, prose doc]
- Accumulator stack:
  - A hybrid update keeps the threat part and rebuilds only the king-relative block from the refresh cache. Using it below 15 pieces too gave -0.55% / -0.54% cycles per node (middlegame / endgames). [7, prose doc]
  - 55-58% of full rebuilds happened because the position before a king move had never been evaluated. Bringing that position up to date first cost about 2.5% more time in rebuilds (rejected). [7, prose doc]
  - Accumulator stack and refresh cache on 2 MB pages (with the search tables): removing them costs 0.93% / 0.86% cycles per node. [7, prose doc]
- Pairwise multiplication of accumulator halves: present; no speed figure.
- int8 layers or int8 feature-transformer rows:
  - 8.1's int8 king-relative rows halve each row (2,112 -> 1,088 bytes), so "eight experts take the memory of four". [1, README] [11, prose doc]
  - Reported effect: incremental updates "slightly cheaper". No isolated nps figure for the released net (the planned ceiling measurement is not reported). [13, prose doc]
  - Stockfish's row pairing (two int8 rows widened together) is cited at +7.0% / +5.2% nps there. Triumviratus's own interleave was level or lost on its Xeon with int16 rows. [11, prose doc]
- Sparse first dense layer: yes.
  - First-layer neurons are permuted at export so zero activations fall in contiguous blocks the sparse layer skips: +2.5% nodes per second, identical evaluations (final net permuted on 2 million positions). [2, prose doc]
  - The accumulator width must be a multiple of 256 for the sparse path. [2, prose doc]
  - Non-zero groups of 4 inputs per evaluation, of 256: 84.7 (middlegame) and 91.8 (endgames) for the 8.0 net. [13, prose doc]
  - A 16-bit pre-sum of two chunks before the multiply-add on CPUs without VNNI was slower on the Xeon (+0.72% cycles) and dropped. [7, prose doc]
- Evaluation cache:
  - 8.0 had a per-thread evaluation cache (shrunk to 8-byte entries, -0.4% cycles in the middlegame). It was not a pure cache: it returned values computed with an earlier iteration's optimism. It was removed for 8.1 in a contributed speed patch. [4, 7, prose doc]
  - New in 8.1: a per-thread cache of the pawn-king subnetwork keyed by pawns, kings and side to move, 91-94% hits. A miss cost about 2,900 cycles with plain loops and about 1,250 after vectorising. Entries are aligned to cache lines and prefetched at the start of the evaluation. [2, 13, prose doc]
  - A pawn refresh cache in the accumulator refresh: -1.4% instructions (8.0). A 16-entry instead of 8-entry pawn-block cache gained nothing. [7, prose doc]
- SIMD and VNNI work:
  - Seven builds chosen at start-up: SSE4.1, AVX2 without PEXT, AVX2, AVX-VNNI, AVX-512, AVX-512 VNNI, AVX-512 with VBMI2. [1, README]
  - AVX-VNNI variant (contribution): +6% to +9% on the Raptor Lake CPUs measured. [1, README]
  - 8.1 contribution for AVX2 / AVX-VNNI (pawn cache in the refresh, first-layer sums kept in registers, perspectives one after the other): 1.7% to 3.2% fewer instructions per node on four CPUs. [4, prose doc]
  - 8.1 contribution for AVX-512 (last layers kept in registers, two independent chains in the second layer, early exit on empty threat masks): -0.2% cycles per node on Skylake-SP, -2.3% in the AVX-512 VNNI build on Zen 4, level elsewhere. [4, prose doc]
  - Threat feature generation with vector compaction on AVX-512: -1.11% cycles per node. The AVX2 form of the same idea was slower (+2.29%), so AVX2 keeps the loops. Passed pawns by bitboard fill: -0.81% (AVX-512) / -0.54% (AVX2). [7, prose doc]
  - Each build carries its own PGO profile in 8.1. One merged profile had cost the AVX builds about 5% more instructions per node. [6, release notes]
  - Register tiling, tried in the rejected expert blend, lowered instructions per cycle from 1.38 to 1.30. [8, prose doc]
- Memory layout and prefetching:
  - Large pages for the weights: about 7% faster at the same tree on 2 MB pages (Xeon, 8.1 development build). The net is about 250 MB and every evaluation reads rows scattered over it. [1, README]
  - Prefetch of the threat PSQT rows before the update: +1.76% nps (8.0). Early prefetch of the child's TT and eval-cache entries: +2.21% nps. [7, prose doc] Later reviews found that "on this machine only removing work pays, while prefetching and reordering loads do not" (six patches, none gained). [7, prose doc]
  - 8.1: threat rows are found through small tables that stay in the first-level cache and are stored in the order the update reads them (no figure). [6, release notes]
  - Where the misses are (8.0): 47% of last-level cache misses in the incremental accumulator update, 11% in refreshes from the cache, 8% in the hybrid update; 60% of L3 misses fall on weight rows; 195 cache lines of weights per node. [7, 11, prose doc]
  - Widening the int8 blocks to int16 at load: +60% L3 misses, -10% speed. [11, prose doc]
  - NUMA: each node reads its own copy of the network. On Linux, engines started together share one copy. [6, release notes]
  - File size: 255.7 MB (8.1), 170.3 MB (8.0), 92.4 MB (7.0). [9, README]
- Anything else that made the network faster: one board for search and network instead of a mirrored second board (speed-neutral, kept for simpler code); x-ray captures no longer emit two cancelling threat entries; one shared map of enemy attacks for move ordering and threat features. [6, release notes] [7, prose doc]
- Speed cost or gain reported for any architecture change:
  - Accumulator 2048 wide: -20.0% nps; 1536: -11.2%; 1024 with 4 experts: -7.5% (random nets of each shape). [2, prose doc]
  - 8.1's network against 8.0's, time per evaluation on the same tree, provisional (busy machine): +5.2% middlegame, +6.9% endgames after two optimisations. The final figure is not published. Its refreshes are fewer in the middlegame but each costs about 15% more. [13, prose doc]
  - Mobility input block (2,048 inputs): -16.2% nps, removed. [7, prose doc]
  - Blending two experts at a boundary: +15.4% / +17.8% cycles, -24.2 +- 11.1 Elo at 8+0.08 although +5.3 +- 7.9 at fixed nodes; closed. [8, prose doc]
  - One expert for a whole search (no expert changes): saved 4.9% / 2.8% cycles but lost -27.7 +- 18.2 Elo. [11, prose doc]
  - Split accumulator (king-relative part and threat part summed at eval time): +12.1% cycles per node, closed. [7, prose doc]
  - Passed-pawn relation block (graft): +1.5% / +2.9% cycles for about +1 to +2.5 Elo in endgames. Other grafts (king files, space, locked pawns, outposts) lost 7 to 19 Elo at 2-3% of cycles each. [7, 11, prose doc]
- Hardware sensitivity reported:
  - Without large pages Triumviratus loses more speed than Stockfish 19, whose net is smaller. [6, release notes]
  - Running 75 games on 40 physical cores (shared L1/L2 caches) hid the 8.0 net's gain: +0.8 +- 10.1 at 30+0.3 with 75 concurrent games against +23.4 +- 12.0 at 12+0.12 with 38. [2, 7, prose doc]
  - A socket with no memory of its own, and one with two memory channels instead of four, skewed results for memory-heavy features. [7, prose doc]
  - The Zen 4 laptop varied by up to 2% between identical builds. [7, prose doc]

### Training data
- Size: about 700 GB of public binpacks (43 files, 701.3 GB), roughly 270 billion usable positions. [2, 12, prose doc]
- Type: **Lc0 and Stockfish self-play data, all relabelled with Leela's BT4 network** (community relabellings on Hugging Face): Leela test60 and test77-test80 runs, older Leela sets, Stockfish self-play and DFRC, plus a small 5-man DTM set. The project's own self-play is excluded (it was about 6.5% of one early net only). [2, 12, prose doc] [prior survey]
- Openings, filtering, tablebase use: random position skipping; a soft skip of early plies (softer in 8.1 so the opening expert sees more openings); piece-count sampling shifted toward endgames in 8.1; quiet-position filters on; the loader draws files in proportion to size so each position weighs the same. [10, 12, prose doc]

### Training recipe (concepts only)
- Trainer: Stockfish's nnue-pytorch with the project's patches (expert block, routing table, pawn-king module, passed pawns). [2, 9, prose doc]
- Loss and target: the trainer's score-to-probability target with a result blend. The blend starts at pure evaluation, descends early to a fixed result-leaning value and is held there. In the 8.0 run a cycling blend that returned to pure evaluation stalled the game-result loss (and Elo) and was replaced by the fixed value. [2, prose doc]
- Stages and schedule:
  - 8.1: a one-cycle pretraining in epochs of one billion positions, stopped after epoch 496 of 550; a 60-epoch fine-tune from those weights at a fraction of the peak rate with a flat stretch; a 3-epoch continuation down to zero rate. The final net is the average of those 3 epochs' weights, then permuted. Fine-tune and average measured only +0.7 +- 2.8 over the end of pretraining. Hardware: two RTX 4090 for a week. [2, 10, prose doc]
  - 8.0: 374 + 80 + 60 epochs (about 472-514 billion positions seen), final net the average of the last five epochs, 105 USD on four RTX 5090. [2, 11, prose doc]
- Regularisation, optimiser, anything unusual: the learned routing table (hard EM rounds early in the run); verification gates before spending GPU time; a second cycle and restarts after the fine-tune gave worse nets and were discarded. Optimiser: not described in the prose read. [10, prose doc]

### Measured gains for network changes
- 8.1 net over 8.0 net: +10.3 +- 4.3, same search, 30k nodes per move, 8,332 games; +10.8 +- 5.5 and +10.3 +- 5.6 at 100k nodes for late pretraining exports. No timed net-only figure is published. [2, prose doc]
- 8.1 release over 8.0 release: +21.5 +- 6.7 at 15+0.15 (search and speed included). 8.1 against Stockfish 19: +0.3 +- 3.3 at 60+0.6 with large pages. [6, release notes]
- 8.0 net (4 experts): 8.0 over 7.0 +27.3 +- 8.3 at 15+0.15, about +15 of it the net with its retuned parameters; net step alone +23.4 +- 12.0 at 12+0.12. [2, 9, prose doc]
- Passed-pawn block: +6.96 (+- 6.6) at 15+0.15, net isolated, as a graft trained alone on a frozen base. [3, 9, prose doc]
- Pawn-pair block as a graft: +18.3 +- 9.9 at 20+0.2. [9, README]
- 7.0 net (first trained from scratch with all blocks): +23.4 +- 9.2 over the grafted net at 15+0.15. [9, README]
- Fine-tunes on a converged net that gained nothing: per-expert fine-tune +0.7 +- 6.1; 15 more epochs on new data of the same family -0.1 +- 3.2; an outpost input block -6.4 +- 3.9. [7, prose doc]
- Held-out loss: the 8.1 net was 2.9% better than 8.0's at the same result blend, 3-7% in endgames, 1.3-2.9% in the middlegame. [2, 10, prose doc]

### Architecture history
- 4.2: first own net, king-relative inputs only, accumulator 2560, trained on Leela T80; about -39 Elo against the Stockfish net of the time. [2, 5, prose doc]
- 5.0: threat inputs, accumulator 1024 (two stages: Stockfish data, then Leela data). [2, prose doc]
- 6.0: + pawn pairs (graft), + passed pawns (graft). [2, prose doc]
- 7.0: SFNNv16 set + passed pawns, trained from scratch. [2, prose doc]
- 8.0: king-relative block split into 4 experts by total piece count; int16 king-relative rows. [2, prose doc]
- **8.1 (the rated version; what changed in the network):** 8 experts per perspective chosen by the opponent's non-pawn material through a stored routing table; king-relative rows int8; pawn-king subnetwork with a per-thread cache; more endgame data; inference rewritten from a specification. [2, prose doc] [6, release notes]

### Since the rated version
- No net is in training. The designed next net ("TRANN5") [2, prose doc]:
  - 6 experts with the queen as a boundary (bare or one minor; one rook; at most one rook with up to two minors; two rooks; lone queen; queen with more), because the middlegame experts were 94-99% alike and a queen middlegame then never changes expert;
  - PSQT moved out of the rows into a 24 KB table per output bucket, so rows are exactly 1024 bytes;
  - pawn-king block cut to 128 hidden and active only in pawn endgames;
  - 32 layer stacks (piece count x which side has a queen);
  - projected 3.7% / 3.2% fewer cycles per node on the Xeon, 5.3% / 3.0% on Zen 4; size 256 MB -> about 204 MB.

### UNVERIFIED and not published
- Layout of the 32 king buckets and the exact mirroring rule (only by reference to Stockfish's feature set).
- Activation details of the head and the exact clipped/pairwise form after the accumulator (only by reference).
- Final, idle-machine speed cost of the 8.1 net against 8.0's (only provisional figures).
- A timed (not fixed-node) net-only Elo for the 8.1 net.
- Isolated nps gain of int8 king-relative rows for the released net.

---

## Obsidian 16.0 (CCRL #4, 3773)

**One-line architecture:** not published for 16.0. The only architecture string the project wrote in prose is an older one, "2x(4x768 -> 768) -> 8x1, with horizontal mirroring" (March 2024). [18, commit text] Since 15.0 (January 2025) the net is multi-layer ("finally with layers"). [17, release notes]

### Inputs
- Feature set: piece-square inputs in king buckets (768 per bucket), by the March 2024 string. [18, commit text] For 16.0: not published.
- King input buckets: 4 in March 2024; layout not described. For 16.0: UNVERIFIED (not published; only in code).
- Horizontal mirroring: yes since March 2024. [18, commit text]
- Threat or attack inputs: none mentioned on any page opened; not published.
- Pawn features: not published.
- Other input relationships: not published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 768 (March 2024), then 1280 (May 2024). [18, commit text] Width in 16.0: UNVERIFIED (not published).
- Further layers: present since 15.0; count and widths UNVERIFIED (not published; only in code).
- Layer stacks: not published.
- Output buckets: 8 since March 2024 (added at +6.3 +- 4.5, 8+0.08). The selector is not described. [18, commit text]
- Skip connections, pairwise multiplication: pairwise multiplication since August 2024. [18, commit text]

### Activations
- After the accumulator: pairwise clipped ReLU since August 2024, replacing SCReLU (+3.2 +- 2.1 at a nominal 6+0.06). [18, commit text]
- In the head: not published.

### Quantisation
- Integer types per layer: not published. A February 2024 commit returned the net to "normal quantization" (no detail). [18, commit text]
- Quantisation-aware training or other rounding care: not published.

### Inference speed
- Accumulator refresh cache: not published.
- Lazy or deferred accumulator updates: "Lazy accumulator updates", +10.6 +- 5.8 at 5+0.05 (June 2024). Also: updating the accumulator in PV nodes that have a cached eval, +4.1 +- 2.4 at 3+0.03 and +4.5 +- 2.5 at 4 threads (September 2024). [18, commit text]
- Fused updates: "Improve accumulator updates": +4% nps without PGO, neutral with PGO (January 2024). Reordering operations in the update: no speedup, the compiler already did it (February 2025). [18, commit text]
- Accumulator stack: avoiding a backward copy of the accumulator: +7% speed (November 2023). A January 2024 commit cached the accumulator delta of every possible move; the March 2024 king-bucket net "finally" removed a 150 MB table (probably the same thing; not stated). That net was 25% faster yet only +10.2 at STC, which the author read as poor scaling. [17, release notes] [18, commit text]
- Pairwise multiplication of accumulator halves: adopted August 2024; no separate speed figure.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: yes after 15.0. Non-zero counting "on the fly" (February 2025, no figure); "Permute weights for NNZ", +5.6 +- 2.6 at 2+0.02 (February 2025); a later improvement to the permuting has no figure. Net files carry a "perm" suffix from then on. [18, commit text] [19, release asset list]
- Evaluation cache: not published.
- SIMD and VNNI work: 15.0 dropped CPUs older than AVX2; build targets go up to AVX-512. A fix for an AVX2 / AVX-512 mismatch landed just before 16.0. [16, README] [17, release notes] [18, commit text]
- Memory layout and prefetching:
  - Using the network weights directly from the executable instead of a copy: 1,420,187 -> 1,786,090 nps on the author's speed script (about +26%, December 2024). [18, commit text]
  - Net file sizes: 25.7 MB to 38.0 MB for the 2024-2025 nets. Nets numbered 80-89 are 30.9 MB, and a May 2025 commit mentions net 88, so the 16.0 net is probably one of these (not confirmed). [19, release asset list]
- Anything else that made the network faster: nothing further published.
- Speed cost or gain reported for any architecture change: accumulator 1280 (May 2024): -5.0 +- 5.2 at 8+0.08, 0.0 +- 5.0 at 40+0.4, merged for long time controls. A further new architecture a week later: -4.0 +- 4.8 at STC, +23.3 +- 8.1 at fixed nodes, merged on trust in long time controls. [18, commit text]
- Hardware sensitivity reported: none.

### Training data
- Size: not published.
- Type: Lc0 data ("trained on Lc0 data"). [16, README] [prior survey] How labels were made or filtered: not published.
- Openings, filtering, tablebase use: not published. One March 2024 net "gained far less than expected", which the author put down to mixing binpacks that should not be mixed. [18, commit text]

### Training recipe (concepts only)
- Trainer: bullet. The 9.0 net was trained by another person (credited). [16, README]
- Loss and target: not published.
- Stages and schedule: not published.
- Regularisation, optimiser, anything unusual: not published. A May 2025 note mentions an issue introduced in an earlier net that halved training speed. [18, commit text]

### Measured gains for network changes
- 15.0's new multi-layer architecture: +7.7 +- 3.4 at 40+0.4 (commit of 2025-01-24). 15.0 over 14.0 as a release: +27.2 +- 4.0 at 40+0.4. [17, release notes] [18, commit text]
- Nets between 15.0 and 16.0: +3.6 (STC); +14.65 FN with +2.6 +- 5.2 STC unfinished; +3.3 (STC); +7.5 STC / +16.8 LTC (2025-05-15); +2.25 STC / +2.1 LTC (2025-05-20, the last before 16.0). [18, commit text]
- 16.0 over 15.0 as a release: +34.8 +- 3.9 at 10+0.1, +38.7 +- 3.6 at 60+0.6. [17, release notes] [prior survey]
- Output buckets +6.3 +- 4.5 (8+0.08). King buckets with mirroring +10.2 +- 5.9 (10+0.1). Pairwise activation +3.2. [18, commit text]

### Architecture history
- 2023-09 to 2023-12: bigger nets several times; a "far better dataset" net gained +31 and +16 in two steps (November 2023). [18, commit text]
- 2024-03-20: 8 output buckets. 2024-03-24: 4 king buckets, mirroring, accumulator 768. 2024-05-03: accumulator 1280. 2024-05-10: another new architecture (not described). 2024-08-15: pairwise activation. [18, commit text]
- 2025-01-24 / 15.0: multi-layer net. 2025-02: sparse first layer with permuted weights. 2025-05-21: 16.0. [17, release notes] [18, commit text]

### Since the rated version
- Two more nets within ten days of 16.0: +5.4 +- 2.6 and +8.3 +- 3.25 at 10+0.1 (the second fixed the training-speed issue). No release since 2025-05-21. [18, commit text] [prior survey]

### UNVERIFIED and not published
- The whole 16.0 architecture: king-bucket count and layout, accumulator width, number and width of head layers, layer stacks, output selector, quantisation, activations in the head (only in code; the TCEC questionnaire is confidential [20, TCEC]).
- Training data size, filtering, label source beyond "Lc0 data".
- Which net file is embedded in 16.0, and its size.
- Whether a refresh cache or an evaluation cache exists.

---

## PlentyChess 8.0.0 (CCRL #5, 3771)

**One-line architecture:** the engine's own string for the threat-input net introduced in October 2025 is "(79856+768x12 -> 640)x2 -> (16 -> 32 -> 1)x8" (before it: "(768x12 -> 1792)x2 -> (16 -> 32 -> 1)x8"). [29, PR text #400] The 8.0.0 net (June 2026) changed the inputs again (three threat classes removed, pawn pairs added), and no new string was published. [29, PR text #482]

### Inputs
- Feature set: threat inputs (every attack or defence between two pieces) plus piece-square inputs in king buckets; since the 8.0.0 net also pawn-pair inputs. [28, release notes] [29, PR text]
- King input buckets: 12 (768 x 12) in the published strings. [29, PR text #400] Layout: not published. History: king buckets first in June 2024 (+17.1 +- 7.6 at 8+0.08); a factoriser in July 2024 (+2.8); a mirrored king layout in August 2024 (+11.7 +- 4.9); "7 factorised king buckets" in October 2024. [29, PR text] [31, PR text]
- Horizontal mirroring: yes ("Mirrored king layout", August 2024). [31, PR text #232]
- Threat or attack inputs: 79,856 at introduction (October 2025). For the 8.0.0 net, threats into a king, from a king, and from pawn to pawn were removed; the remaining count is not published. Updated incrementally; int8 weights since October 2025. [29, PR text #400, #411, #482] The author's claim: the first top alpha-beta engine with efficiently updatable threat inputs; the input set came from Monty, and another engine inspired the incremental tracking. [25, TCEC] [29, PR text #400]
- Pawn features: pawn-pair features with a three-file-wide mask (credited to Jonathan Hallstrom), in the 8.0.0 net. [29, PR text #482]
- Other input relationships: not published.
- Factoriser: yes for king buckets (July 2024). [29, PR text #202]

### Body
- First hidden layer width per perspective: 640 with threat inputs (down from 1792 without them). [29, PR text #400] Another project's note also gives 640 for 8.0. [11, prose doc, second-hand] There is no first-party statement at the 8.0.0 release.
- Further layers: 16 -> 32 -> 1. [29, PR text #400] The multi-layer head dates from October 2024 ("More layers, smaller hidden layer": +13.6 +- 5.2 STC, +8.1 +- 4.7 LTC). [29, PR text #266]
- Layer stacks: the whole head is replicated 8 times ("x8"). [29, PR text #400]
- Output buckets: 8, by piece count (introduced March 2024, +11.7 +- 7.7). [29, PR text #125]
- Skip connections, pairwise multiplication: a test net of April 2025 is labelled "no pairwise", which implies the production nets use pairwise multiplication. Not stated directly: UNVERIFIED (implied only). [32, release notes]

### Activations
- After the accumulator: not published (see the pairwise note above).
- In the head: not published.

### Quantisation
- Integer types per layer: threat input weights int8 instead of int16 since October 2025; a later refactor made evaluations fit int16. Other layers: not published. [29, PR text #411] [31, PR text #453]
- Quantisation care: a "different quantisation" in July 2024 gained +5.0 +- 2.9 (8+0.08), and smaller weight limits +3.1; no detail. [29, 31, PR text]

### Inference speed
All figures are from PR texts; "VSTC" is 2+0.02 or 4+0.04, 1 thread.
- Accumulator refresh cache: "finny tables" with the first king-bucket net: +10.0 +- 5.7 at 8+0.08 (June 2024). [29, PR text #183]
- Lazy or deferred accumulator updates: accumulators updated only when an evaluation is called (January 2024, no figure). [29, PR text #51]
- Fused updates: "Speed up accumulator calculation by changing the DirtyPiece layout" +7.7 +- 3.5 (December 2025); "Refactor + Speedup accumulator updates" +2.4 +- 1.7 (after 8.0.0). [29, PR text #440, #490]
- Accumulator stack: threat and piece-square parts were separate accumulators in 8.0.0 and were fused only afterwards (see "Since"). [29, PR text #488] [11, prose doc, second-hand]
- Pairwise multiplication: UNVERIFIED (implied only, see Body).
- int8 feature-transformer rows: int8 threat weights: +9.9 +- 3.9 STC, +3.3 +- 2.6 LTC, -2.5 +- 4.1 at fixed nodes (so the gain is speed). [29, PR text #411]
- Sparse first dense layer: a non-zero ("NNZ") pass exists. Speeding it with VBMI2 together with the threat computation: +1.9 +- 1.5 and +7.4 +- 3.4 (two tests, June 2026). "Speed up L1 matmul on AVX512VNNI": +1.4 +- 1.1, and +5.1 +- 2.8 on a 1024-wide net. [29, PR text #483, #432]
- Evaluation cache: not published.
- SIMD and VNNI work:
  - Threat accumulator updates on AVX-512: +6.6 +- 3.1. [29, PR text #433]
  - Smaller tiling on AVX-512: "5% local speedup" (+12.4 +- 9.1, unfinished test). [29, PR text #485]
  - Pre-permuting for the pack instruction: no measurable speedup. [29, PR text #302]
  - NEON build up to 100% faster than the generic one on ARM. [28, release notes]
  - The AVX-512 VNNI target was replaced by an AVX-512 VBMI2 target for 8.0.0. The binary guide warns that AVX2 can be faster than AVX-512 on some systems. [28, release notes] [29, PR text #482]
- Memory layout and prefetching:
  - Prefetch of threat weights: +5.1 +- 2.7. [29, PR text #463]
  - Memory-mapped network (December 2024, no figure). [31, PR text #297]
  - NUMA replication of the network memory: 218.4M -> 317.4M nps on 288 threads over 4 NUMA nodes (about +45%). [29, PR text #449]
  - Huge pages requested since March 2024; a fix to the huge-page allocation after 8.0.0 gained +6.2 +- 3.0. [31, PR text #119, #489]
  - Net file of the 8.0.0 net: 47.8 MB as published (its predecessor 57.6 MB). [32, release asset list]
- Threat-update work (the bulk of "many speedups to make the architecture viable"):
  - faster ray calculation and dropping incremental threat tables: +3.4 +- 2.2 (one shared test); [29, PR text #405, #406]
  - three small Stockfish-style lookup tables instead of one big one: +3.5 +- 2.2; [29, PR text #421]
  - a swap-piece path that skips unnecessary threat updates: +1.4 +- 1.1 (8+0.08); [29, PR text #438]
  - a smaller threat-delta record: +1.4 +- 1.6; [31, PR text #437]
  - "PP and TI speedup": +7.3 +- 3.3 and +4.7 +- 2.6; "two minor speedups": +1.1 and +1.7. [29, PR text #481, #484]
- Anything else: not precomputing feature offsets, 3-8% faster across machines; fewer allocations, 5-6%; clang with LTO, about 10% on Windows. [29, PR text #102, #103, #362]
- Speed cost or gain for any architecture change:
  - Threat inputs with the accumulator cut from 1792 to 640: +45.5 +- 2.2 at fixed nodes, **-3.1 +- 2.9 at 8+0.08 (failed)**, +1.8 +- 1.4 at 40+0.4; "quite a big slowdown". [28, release notes] [29, PR text #400]
  - 8.0.0 net (threat classes removed, pawn pairs added): +1.4 +- 1.1 STC without the accompanying speedup; +4.1 +- 2.8 and +2.4 +- 3.0 LTC with it. [29, PR text #482]
  - Nets that lost at STC and were merged for long time controls: April 2025 net +15.4 FN, -5.3 STC, -1.9 LTC, -0.4 at 80+0.8; October 2024 net +19.1 at 25k nodes, +15.5 at 125k nodes, -7.3 STC, -0.9 LTC. [29, PR text #342, #261]
- Hardware sensitivity reported: the net after 8.0.0 "depends greatly on hardware (and especially cache sizes)". [29, PR text #487]

### Training data
- Size: "15+ billion self-generated positions (standard and Fischer random)". [27, README] [prior survey] First own-data net (3.0, November 2024): 10.5 billion generated in about three months from a PeSTO-style start, the best 7.2 billion used. [28, release notes] [29, PR text #279]
- Type: own self-play since 3.0 (Lc0 data before). The author's TCEC reply adds **adversarial games against Stockfish, using only positions where PlentyChess is to move**, which the author considers equivalent to self-generated data. "Self-distillation techniques for part of the training" (no detail). Search budget of data generation: not published. [25, TCEC] [27, README]
- Openings, filtering, tablebase use: a piece-probability distribution for the start positions of data generation gained +13.2 +- 5.6; "some TB data" +7.8 to +8.5; discarding 2 billion old positions in favour of a longer run +2.8; special DFRC data (DFRC +132 for 7.0.0, +108 for one net). [28, release notes] [29, PR text #227, #236, #238, #386]

### Training recipe (concepts only)
- Trainer: bullet. [25, TCEC] [27, README]
- Loss and target: a result blend, lowered twice in August 2024 (+1.4; and +15.1 together with a higher eval scale, although the lower blend alone lost 6.4). [29, 31, PR text #219, #226]
- Stages and schedule: net names with repeated "r" suffixes suggest chains of retrains from a previous net (my reading of the names; not explained in prose). Training for more superbatches: +3.6. [31, PR text #239]
- Regularisation, optimiser, anything unusual: SPSA tuning of the last layer's weights under 4 threads: +1.9 +- 1.6 STC, +0.9 +- 2.1 LTC (not conclusive), +4.6 +- 2.5 at 40+0.4 with 4 threads. [31, PR text #476] [prior survey]

### Measured gains for network changes
- First own-data net against the last Lc0-data net: the net alone about 15 to 30 Elo weaker; merged with other gains at +8.7 STC, +3.3 LTC, +29.0 DFRC. [28, release notes] [29, PR text #279]
- King buckets +17.1; refresh cache +10.0; factoriser +2.8; mirrored layout +11.7; 7 factorised buckets net +5.0 / +4.0; 8 output buckets +11.7; multi-layer head +13.6 / +8.1; accumulator 1024 +11.8 (August 2024); accumulator 2048 +3.9 STC / +9.0 LTC (March 2024). [29, 31, PR text]
- Threat inputs: +45.5 FN / -3.1 STC / +1.8 LTC at introduction. Follow-up nets (STC / LTC): +2.1 / +4.35, +5.3 / +6.9, +4.2 / +12.5 (unfinished), +1.5 / +1.6, +2.4 / +3.1, +1.2 / +3.4. [29, PR text]
- 8.0.0 over 7.0.0 (release): +41.8 +- 2.5 STC, +47.4 +- 2.35 LTC, +49.5 DFRC. [28, release notes]

### Architecture history
- 2024-01: (768 -> 1024)x2 -> 1 on Lc0 data. 2024-03: 8 output buckets, wider accumulator (2048).
- 2024-06/07: king buckets, refresh cache, factoriser. 2024-08: own data generation starts, accumulator 1024, mirrored layout.
- 2024-10: multi-layer head with a smaller accumulator. 2024-11 (3.0): own data only.
- 2025-04: full-threat test nets "(80624 -> 2048)x2 -> (16 -> 32 -> 1)x8, no pairwise" and "(80624 -> 1024)x2 -> 1x8" (experiments, 331 MB and 165 MB).
- 2025-10 (7.0.2): threat inputs with a 640 accumulator, then int8 threat weights.
- 2026-06 (8.0.0): threats into and from kings and pawn-to-pawn threats removed, pawn pairs added. [28, release notes] [29, PR text] [32, release notes]

### Since the rated version
- A new default net the day after the release: +3.7 +- 2.3 STC, hardware-dependent (76.4 MB against 47.8 MB). [29, PR text #487] [32, release asset list]
- Threat and piece-square accumulators fused into one: +4.3 +- 4.3 at 4+0.04 (test not finished). Accumulator update refactor +2.4. Huge-page allocation fix +6.2. [29, PR text #488, #490] [31, PR text #489]
- Search-side items are in the prior survey.

### UNVERIFIED and not published
- King-bucket layout; threat-input count of the 8.0.0 net; pawn-pair count.
- Accumulator width of the 8.0.0 net by a first-party statement (640 is from October 2025 and from a second-hand note).
- Activations (after the accumulator and in the head); integer types of the head; whether the published net files are compressed.
- Search budget (nodes or depth) of data generation; share of adversarial games; what "self-distillation" means in practice.
- That 8.0.0 embeds net "0178r" is inferred from merge and release dates.

---

## Coda 0.9.4 (CCRL #6, 3768)

**One-line architecture:** assembled. The project describes the 0.9.4-era net as "v10 pairwise dual FT=1024 L1=16 L2=32" [43, commit text], and in prose as king-bucketed piece-square inputs (16 king buckets) plus threat inputs feeding a 1024-wide accumulator per perspective with pairwise activation, then small hidden layers with material-bucketed output heads. [39, README] In the brief's notation: (768x16 + threats -> 1024)x2 -> pairwise -> 16 (dual activation) -> 32 -> 1 x output buckets.

### Inputs
- Feature set: piece-square inputs relative to the own king's bucket: 16 king buckets x 12 piece types x 64 squares = 12,288 inputs per perspective, plus threat inputs ("what attacks what"). [39, README] [40, prose doc]
- King input buckets: 16. Layout: the project's own "standard / consensus" 16-bucket layout, adopted in 0.9.1 when a 10-bucket layout copied from another engine was removed for licence reasons. The squares per bucket are not described in prose. [42, release notes] [43, commit text]
- Horizontal mirroring: yes. A king crossing between the d and e files re-mirrors every threat feature and forces a full refresh. [43, commit text]
- Threat or attack inputs:
  - Two selectable threat feature spaces: 66,864 features (with king-attacker threats) and 60,144 (without). The loaded net declares which. Without king threats, deltas per move fall from 8.40 to 3.86. [43, commit text]
  - Stated matrix sizes (threat block about 65-67 MB at int8, 1024 wide) match the 66,864 space for the production nets of this period (inference by arithmetic).
  - X-ray threat features were removed in 0.9.3. Threat rows are int8 and are updated from per-move delta lists. [42, release notes] [43, commit text]
- Pawn features: none in 0.9.4 (pawn pairs came in 0.9.5). [42, release notes]
- Other input relationships: none stated.
- Factoriser: named for an earlier net family (June 2026); not restated for the 0.9.4 net. [43, commit text]

### Body
- First hidden layer (accumulator) width per perspective: 1024 (768 before mid-2026). [39, README] [43, commit text]
- Further layers: 16 then 32. The first was 32 wide until 0.9.4 switched to 16 with dual activation. [42, release notes] [43, commit text]
- Layer stacks: none in 0.9.4 (hidden layers shared by all buckets; per-bucket hidden layers came in November 2026). [43, commit text]
- Output buckets: by material, uniform layout. The count is not stated in the pages opened: UNVERIFIED (not published in prose). A non-uniform output-bucket layout taken from another engine was tried and removed. [39, README] [43, commit text]
- Skip connections, pairwise multiplication: pairwise multiplication of the accumulator halves. No PSQT skip (tested and rejected, see below). [39, README] [43, commit text]

### Activations
- After the accumulator: pairwise clipped activation. [39, README]
- In the head: dual activation on the 16-wide layer (both a clipped and a squared-clipped form feed the next layer, "giving back roughly the effective width at a smaller footprint"). [42, release notes] [43, commit text]

### Quantisation
- Integer types per layer: accumulator int16 for piece-square rows, int8 for threat rows; first hidden layer int8 weights; the later layers float. [40, prose doc] [43, commit text] The README says "two small int8 hidden layers", while the project notes say the later layers are float. The two prose sources disagree; the float statement is the more specific one.
- Rounding care: the evaluation scale of a pairwise net must be measured, never computed, because of int8 saturation. A load-time exact check decides whether a faster fused kernel is safe for a net's weights. [40, prose doc] [43, commit text]

### Inference speed
Figures are from commit texts unless tagged; SPRTs are 10+0.1 on the project's OpenBench fleet.
- Accumulator refresh cache: yes ("Finny table", per perspective and king bucket). Its 64 entries are stored inline as one slab of about 138 KB instead of 64 heap blocks (June 2026, no figure). [40, prose doc] [43, commit text]
- Lazy or deferred accumulator updates: yes (materialised on demand). In 0.9.4 threat-delta generation was still eager. Because only 0.186 evaluations per node happen in endgames (0.572 in openings), searches starting with few pieces skip delta generation and re-enumerate instead: +7.8% nps at 10 pieces or fewer, but -21.6% at 17-24 pieces and -38.2% at 25-32, so it is gated by root piece count. [40, prose doc] [43, commit text]
- Fused updates: "fused accumulator update". [40, prose doc] Re-tiling the register-tiled update kernels when the accumulator grew from 768 to 1024 (the old chunking left a runtime tail on every call): SPRT +3.0. [43, commit text]
- Accumulator stack: separate piece-square and threat accumulators combined at evaluation time in 0.9.4 (fused later, see "Since"). [43, commit text]
- Pairwise multiplication: yes. The AVX-512 pack step was simplified to avoid a permute (perf-neutral). [43, commit text]
- int8 layers: int8 first hidden layer with dedicated kernels per width. [42, release notes] [43, commit text]
  - A column-major VNNI kernel for a 32-wide layer gave +8.5% nps on that net (Zen 5) and recovered most of the "about 10% nps tax" of 32 against 16.
  - The AVX-VNNI twin: +9.7% on the kernel (about +1-2% of the whole eval).
  - A fused multiply-add pair kernel for plain AVX2 at width 32: SPRT +2.1 +- 2.1.
  - The same for width 16 in 0.9.4 (no figure; that layer was 15.3% of endgame runtime on a Zen 1 AVX2 host against 6.3% on Zen 5 AVX-512).
- Sparse first dense layer: **tested and rejected.** At 16-32 neurons the non-zero search costs more than it saves: a proper sparse kernel was 1.8 to 2.4 times slower than dense at every density (measured input density 58-67%). [43, commit text]
- Evaluation cache: not published (a tablebase probe cache exists; no network-output cache is mentioned).
- SIMD and VNNI work: runtime dispatch among AVX2, AVX-512 VNNI and NEON. 0.9.1's ARM dot-product kernels lifted NNUE inference about 30% on an Apple M5 and a Cortex-A76 (about +30 Elo at short time controls on ARM). The x86-64-v3 binary is about 12% faster than v2. PGO currently regresses on most modern hardware. [39, README] [42, release notes]
- Memory layout and prefetching [42, release notes] [43, commit text]:
  - 64-byte aligned feature-transformer and first-layer weights: SPRT +1.4 (35.8k games).
  - Explicit huge-page (hugetlb) tier for the big weight matrices, because transparent huge pages silently delivered none on some kernels (no figure).
  - Prefetch at threat-apply entry: SPRT +1.67. Wider threat prefetch (first chunk of every row plus a next-chunk lookahead): about 5% fewer cache misses, 2% fewer cycles.
  - Prefetch of feature-transformer row heads: -1.7% cache misses, -0.5% cycles.
  - A TT prefetch before the move is made, from an approximate key (no figure).
  - Net file 93.7 MB (93,672,086 bytes) for the 0.9.4-period nets.
- Anything else: 0.9.1's licence clean-up (re-implemented set-wise kernels, threat path back to the project's own scalar code) cost about 3% nps on some x86 hosts. [42, release notes] [prior survey]
- Speed cost or gain for any architecture change:
  - X-ray threat features: removing them gained +12.5 +- 4.9 STC and +15.1 +- 5.3 LTC once a bug in the update path was fixed ("eval improved but by less than the nps cost"). [42, release notes]
  - First hidden layer 32 instead of 16: about -10% nps before the dedicated kernel; promoted at +4.1 +- 3.1 (June 2026). [43, commit text]
  - PSQT output and dual activation, tested on short matched runs in June 2026: PSQT -12.5 (eval quality equal, search 12% slower); dual -27.9 then; both together -104 (a scale clash). Dual activation succeeded two months later on the 16-wide layer. [43, commit text]
  - The activation-penalty net (0.9.4): nodes -22.1% at fixed depth and evaluations per node +9.4% (a sharper eval prunes a smaller tree with fewer transpositions); per-eval cost unchanged. [43, commit text]
- Hardware sensitivity reported: one worker class (a virtual host that is "not cache-bound") lost 1.5 Elo on a change that gained 6.1 and 10.9 on two others; prefetch gains "concentrate on memory-bound hosts"; ARM pays about 11% nps for the later pawn-pair block against 5-6% on x86. [43, commit text]

### Training data
- Size: "hundreds of billions of positions" (the full Lc0 dataset) plus some self-generated data. [39, README]
- Type: mostly **Lc0 self-play data, in 0.9.4 scored by Leela's BT4 network** ("switched the training dataset to BT4-scored LC0 training data"), plus CC0 data published on Kaggle by Joost VandeVondele and some own data. A June 2026 note says plainly that Coda trained on the shared Lc0/Stockfish datasets with no self-play training at that time. [39, README] [42, release notes] [43, commit text] [prior survey]
- Openings, filtering, tablebase use: not published for the training set (the data-generation tool supports self-play and material-imbalance generation). [39, README]

### Training recipe (concepts only)
- Trainer: a customised bullet. [39, README]
- Loss and target: result blend with the search score; values not recorded.
- Stages and schedule: multi-stage runs with a long final stage and stochastic weight averaging over the tail; a longer final stage alone gained +3.5. The 0.9.4 nets are long single-recipe runs with weight averaging. [43, commit text]
- Regularisation, optimiser, anything unusual: an L1 penalty on the feature-transformer's output activations (0.9.4), which "significantly sharpens eval quality": +5.9 +- 3.2. [42, release notes] [43, commit text]

### Measured gains for network changes
- BT4-scored data, same recipe: +5.9 +- 3.3 (12,180 games); the new net read about 1.11 times the old scale. [43, commit text]
- 16-wide dual-activation layer replacing a 32-wide one: +8.6 +- 4.0 at 10+0.1, +9.2 +- 4.05 at 40+0.4 (net and its tune together). [43, commit text]
- Activation L1 penalty: +5.9 +- 3.2 (12,942 games). [43, commit text]
- 0.9.4 over 0.9.3 (release): +38.3 +- 1.1 STC, +36.5 +- 2.1 LTC. [42, release notes] [prior survey]
- X-ray-free net (0.9.3): +12.5 / +15.1. Own 16-bucket layout replacing the borrowed 10-bucket one (0.9.1): +5.5 STC, +13 LTC ("+4 in SPRT" in the release notes). [42, release notes] [43, commit text]

### Architecture history
- By 2026-06: accumulator 768 -> 1024. 2026-06-21: first hidden layer 16 -> 32.
- 2026-07-13 (0.9.1): 10 king buckets -> the project's 16-bucket layout.
- 2026-07-25 (0.9.3): x-ray threats removed.
- 2026-08-04: BT4-scored data. 2026-08-15: first hidden layer 32 -> 16 with dual activation. 2026-08-18: activation penalty; this net (93.7 MB) is the last promoted before the 0.9.4 release of 2026-08-22. [42, release notes] [43, commit text]

### Since the rated version
- 0.9.5 (2026-10-21) [42, release notes] [43, commit text]:
  - Pawn-pair input block, 1,488 features (pairs of pawn squares on the same or a neighbouring file, four colour combinations), sharing the threat block's int8 rows: +4.6 +- 2.4 STC, +8.2 +- 3.2 LTC (matched pair: +2.6 / +9.3). Cost 4.9% nps after folding its indices into the threat-delta pass (15.1% before).
  - A linear readout from the first hidden layer's pre-activations to the output, so material still counts in decided positions: -1.0 +- 1.4 at LTC (non-regression).
  - Extra fine-tune steps.
- Speed after 0.9.4 [43, commit text]:
  - threat deltas generated lazily on first replay (54.7% were never consumed): +1.3 +- 1.4;
  - branch-free threat-delta compaction with a smaller history table: +2.7 (branch misses -9.2%, cycles -1.8%);
  - branch-free TT scan with in-loop threat-row prefetch: +2.0 +- 1.7;
  - not generating deltas that decode to no feature (19.7% of them): -3.1% instructions per node;
  - weights shared between processes on one machine: cycles per node 4940 -> 4030 at 16 concurrent engines and 10958 -> 6222 at 32;
  - NEON row kernels: +7.1 to +8.6% nps on an M5;
  - cheaper lazy delta materialisation: +1.0 +- 1.2;
  - **piece-square and threat accumulators fused into one, with a block swap on king-bucket changes: +3.0 +- 2.0** (2026-11-07);
  - in-place update rows and a lower refresh threshold: +2.3 +- 1.8.
- 2026-11-14: a net with hidden layers per output bucket promoted (STC and LTC passes; figures not in the message). [43, commit text]

### UNVERIFIED and not published
- Number of output buckets and their material boundaries.
- Squares per king bucket in the 16-bucket layout.
- Which threat space the 0.9.4 net uses (66,864 is an inference from sizes).
- Exact position count of the training set; filtering; any tablebase use.
- Whether a network-output cache exists.
- That 0.9.4 embeds the net promoted on 2026-08-18 is inferred from dates.

---

## Reckless 0.9.0 (CCRL #7, 3765)

**One-line architecture:** as the engine wrote it when threat inputs were merged (December 2025, three months before 0.9.0): "(79856 + 768x10 -> 384)x2 -> 16 -> 32 -> 1". [35, PR text #608] Two later changes before the release alter it without a new string: piece-to-king threat features were removed (February 2026), and the last net before 0.9.0 has no description. [35, PR text #703, #710]

### Inputs
- Feature set: threat inputs (all piece pairs where one attacks or defends the other) on top of king-bucketed piece-square inputs (2 x 6 x 64 per bucket). [34, release notes] [35, PR text #608]
- King input buckets: 10. Layout: not published. History: "input buckets" introduced June 2025 with 4 buckets (FN +25.5 +- 8.3, STC +3.4 +- 2.5, LTC +6.8 +- 3.9). [35, PR text #371, #402, #608]
- Horizontal mirroring: yes, since a mirrored net trained from scratch in March 2025 (FN +15.5, STC +11.2, LTC +10.5). [35, PR text #190]
- Threat or attack inputs: 79,856 at introduction. In February 2026 the piece-to-king threats were "simplified away", saving 6.4 MB of weights and some accumulator updates (+2.6 +- 2.0 at 4+0.04; +0.1 STC; +0.1 LTC). Updated incrementally from per-move threat deltas. [35, PR text #608, #703, #650-#653]
- Pawn features: none stated.
- Other input relationships: none stated.
- Factoriser: not published.

### Body
- First hidden layer width per perspective: 384 when threats were added (cut from 1024 "to offset the additional computational cost"). [35, PR text #608] Whether it changed before 0.9.0: UNVERIFIED (not published; a second-hand note of mid-2026 gives 768 for a later commit [11, prose doc, second-hand]).
- Further layers: 16 -> 32 -> 1. [35, PR text #402, #608]
- Layer stacks: none in the published string.
- Output buckets: none in the published string. An April 2026 PR (after 0.9.0) shows 8 output buckets in the engine's eval printout, so they were added at some point. Whether 0.9.0 has them: UNVERIFIED (not published). [35, PR text #889]
- Skip connections, pairwise multiplication: pairwise multiplication after the accumulator. [35, PR text #402]

### Activations
- After the accumulator: pairwise clipped ReLU. [35, PR text #402]
- In the head: clipped ReLU, then clipped ReLU ("pairwise crelu -> crelu -> crelu"). [35, PR text #402]

### Quantisation
- Integer types per layer: an integer first layer after the accumulator (a VNNI-style 8-bit dot product) and float second and third layers (a later proposal to quantise "the f32 L2/L3 tail" was not merged). [35, PR text #402, #1105] Row types are not stated first-hand; a second-hand note gives int16 piece rows and int8 threat rows. [11, prose doc, second-hand]
- Rounding care: separate quantisation factors for the two sides of the pairwise product; a pack-and-high-multiply trick credited to a Stockfish commit. [35, PR text #402]

### Inference speed
Figures from PR texts; "VSTC" is 4+0.04, 1 thread.
- Accumulator refresh cache: "Introduce accumulator cache": +16.0 +- 6.2 at 8+0.08 (June 2025). Tiling for full refreshes: +2.65 +- 1.9 VSTC. [35, PR text #372] [37, PR text #416]
- Lazy or deferred accumulator updates: accumulator updates only on legal moves: +6.2 +- 4.3 (February 2025). "Optimize accumulator handling": +19.1 +- 8.1 (August 2024). No statement of evaluation-time laziness. [35, PR text #95, #59]
- Fused updates: "operation fusion" for the accumulator: about +2.7% nps (August 2024). [35, PR text #58]
- Accumulator stack: separate piece-square and threat accumulators (the code was later split into two modules); second-hand confirmation. [35, PR text #796] [11, prose doc, second-hand]
- Pairwise multiplication: yes (see Activations).
- int8 layers: 8-bit first-layer dot products (VNNI or an emulation of it). [35, PR text #402]
- Sparse first dense layer: yes: a 4-chunk sparse matrix multiplication with a sparse-permutation tool (credited to other developers). [35, PR text #402]
  - Unrolling the sparse multiplication by two: +1.4 +- 1.2. [35, PR text #436]
  - Separating the accumulator activation from non-zero index finding: +2.2 +- 1.7. [35, PR text #448]
  - AVX-512 non-zero finder: +4.7 +- 2.7; unrolled and interleaved: +1.7 +- 1.4. [35, PR text #636, #662]
- Evaluation cache: not published.
- SIMD and VNNI work:
  - Handwritten AVX2: +24.0 +- 11.3 (March 2024). Manual SIMD for AVX2 and SSSE3: +36.0 +- 9.5 on a v2 baseline, +2.7 +- 3.6 on v3. [35, PR text #16, #239]
  - AVX-512 inference (July 2025, no figure). NEON: +18.0 +- 7.4 on ARM. [35, PR text #441] [37, PR text #621]
  - Threat accumulator updates on AVX-512: +4.9 +- 2.8; on AVX2: +5.8 +- 3.1. [35, PR text #634, #635]
  - Set-wise pawn threats +1.8; threat index by sign-extension +1.55; compacting threat deltas without a loop +1.8. [35, PR text #632, #637, #650]
  - Slider and x-ray deltas from byte-board tables: +4.3 +- 2.7. No redundant add/sub delta pairs: +3.4 +- 2.2. [35, PR text #652, #653]
  - A lookup table for ray permutation +1.5; set-wise slider threats +2.1 and +2.1. [37, PR text #660] [35, PR text #687, #688]
  - Incremental threat update ported to AVX2: +2.3 (AVX2 hosts), +1.1 (AVX-512 hosts). [35, PR text #728]
- Memory layout and prefetching: large pages on Linux: +4.25 +- 2.6 at 16 MB hash and +9.0 +- 4.1 at 128 MB hash (VSTC). Aligning the network parameters: about +2.8% speed (2024). An L2 prefetch hint: +2.65 +- 1.9. NUMA-aware thread pool, later with network weights replicated per NUMA domain (after 0.9.0). File size: not published. [35, PR text #56, #590, #927] [37, PR text #463]
- Anything else: none.
- Speed cost or gain for any architecture change:
  - Threat inputs with the accumulator cut from 1024 to 384: +53.4 +- 2.35 at fixed nodes, +4.2 +- 2.7 STC, +6.9 +- 3.45 LTC, +6.8 DFRC. [35, PR text #608]
  - Multi-layer head on a 1024 accumulator (June 2025): +27.8 +- 7.15 FN, +8.45 +- 4.0 at 10+0.1, +13.5 +- 4.9 at 60+0.6. [35, PR text #402]
  - Last net before 0.9.0: +19.6 +- 2.1 FN but -2.6 +- 2.5 STC (estimate), +14.0 +- 5.0 on an endgame book, +0.5 +- 1.35 LTC, +2.2 +- 1.8 at 8 threads; no description of what changed. [35, 37, PR text #710]
- Hardware sensitivity reported: none in prose.

### Training data
- Size: "billions of positions" (0.8.0). [34, release notes]
- Type: own self-play from a randomly initialised net, iterated (0.5.0); the whole set regenerated in October 2024 after a data-generation change. Data of the nets from 2025 on: not published. [34, release notes] [35, PR text #74] [prior survey] Another author's TCEC reply names Reckless among engines that use games against another engine (keeping own-side positions): second-hand, UNVERIFIED. [25, TCEC]
- Openings, filtering, tablebase use: 2024 method: a book position followed by 4 random half-moves; games adjudicated as drawn after several late near-zero scores. One 2025 net increased early-ply skipping. Label budget: not published. [35, PR text #72, #303]

### Training recipe (concepts only)
- Trainer: bullet (a custom trainer before 0.8.0). [33, README] [34, release notes]
- Loss and target: result blend, raised in a second stage (2024 recipe). [35, PR text #84]
- Stages and schedule: two-stage training (2024); not published since.
- Regularisation, optimiser, anything unusual: an L1 regularisation on the trainer side (February 2026): +4.0 FN, +7.2 +- 3.6 STC, +3.9 +- 2.5 LTC. [35, PR text #700]

### Measured gains for network changes
- (FN / STC / LTC) Mirroring +15.5 / +11.2 / +10.5; king buckets +25.5 / +3.4 / +6.8; multi-layer head +27.8 / +8.45 / +13.5; threat inputs +53.4 / +4.2 / +6.9. First 768-wide net: +13.3 FN / +6.9 STC. [35, PR text]
- DFRC-aimed nets: +39.4, +23.4, +14.0 in DFRC with about -1 to +3 in standard chess. [35, PR text #432, #437, #509]
- 0.9.0 over 0.8.0: +62.4 +- 3.3 at 40+0.4; +68.1 DFRC; +70.9 at 8 threads. [34, release notes]

### Architecture history
- 0.5.0 (2024-02): first NNUE, own data from random init. 0.6.0: SCReLU. 0.7.0 (2024-08): "(768 -> 384)x2 -> 1x4" with 4 output buckets, removed again in October 2024 ("(768 -> 384)x2 -> 1").
- 2025-03: mirroring. 2025-04: 768-wide. 2025-06-15: 4 king buckets and a refresh cache. 2025-06-28: "(768x4 -> 1024)x2 -> 16 -> 32 -> 1".
- 2025-12-03: "(79856 + 768x10 -> 384)x2 -> 16 -> 32 -> 1". 2026-02: piece-to-king threats removed; L1 regularisation. 2026-03-01: 0.9.0. [34, release notes] [35, PR text]

### Since the rated version
- Six further nets (March to May 2026), each +1 to +5. [35, PR text]
- Speed: vectorised feature-index generation on refresh +2.7; faster threat refresh +1.55; TT prefetch into all cache levels +1.1; reordered accumulator update +1.8; NEON improvements about 12% faster; network weights replicated per NUMA domain; a split of the two 8-bit dot-product accumulators in the first layer on AVX-512 VNNI +4.5 +- 2.7. [35, PR text]
- 8 output buckets visible by April 2026. A second-hand note for mid-2026 gives 10 king buckets, a 768-wide accumulator and 66,864 threat rows. [35, PR text #889] [11, prose doc, second-hand]
- Search-side items are in the prior survey.

### UNVERIFIED and not published
- Accumulator width, threat-input count and output buckets of the net actually embedded in 0.9.0 (no description after December 2025).
- King-bucket layout; integer types of the rows (second-hand only).
- All training data facts after 2024: size, source, label budget; the adversarial claim (second-hand).
- Net file size; evaluation cache; evaluation-time lazy updates.
- That 0.9.0 embeds net "v54" is inferred from merge and release dates. The TCEC questionnaire is confidential. [26, TCEC]

---

## Incipit 0.6.0 (CCRL #23, 3728)

**One-line architecture:** assembled from the README's sentence: piece-square inputs in 16 mirrored king buckets, plus pawn-pair and threat inputs -> 1024-wide accumulator per perspective with pairwise activation -> hidden layers of 16 and 16 -> 6 output buckets by material. [45, README] In the brief's notation: (768x16 + pawn pairs + threats -> 1024)x2 -> pairwise -> 16 -> 16 -> 1, hidden and output layers per output bucket (x6).

### Inputs
- Feature set: 768 piece-square inputs per king bucket (colour x piece type x square, from the perspective's side); pawn-pair inputs; threat inputs ("which pieces attack which"). [45, README] [47, prose doc]
- King input buckets: 16, mirrored. [45, README] Growth, each step measured [50, release notes] [51, commit text]:
  - none -> 4 buckets by king rank (rank 1, rank 2, ranks 3-4, ranks 5-8), factorised: +15.3 FN, +7.9 at 10+0.1;
  - 4 -> 8: +11.8;
  - 8 -> 16: +10.1 (described as "ranks 1-2 per file pair, wing/centre above, ranks 5-6 and 7-8 paired"; 8.6% slower than 4);
  - 16 -> 32 (one per square of the mirrored half-board): +2.8 (42k games);
  - back to 16 with threat inputs, because 16 equalled 32 at the same run length and is smaller.
- Horizontal mirroring: yes, when the own king is on files e-h. [47, prose doc]
- Threat or attack inputs:
  - Three variants exist, with 56,890, 56,218 and 54,090 features; the production nets use "variant B". int8 rows, shared by every king bucket, stored after all layers at a 64-byte offset. [47, prose doc] [51, commit text]
  - The file size of the release-period nets (84,774,784 bytes) is consistent only with the 56,890-feature variant plus the 608-feature pawn-pair window (inference by arithmetic from the published format). [50, release asset list]
  - Incremental update: only the pieces a move can affect are considered, computed as bitboard set differences per candidate attacker, with no threat lists. [51, commit text]
- Pawn features: pawn pairs: one input per unordered pair of pawn squares (ranks 2-7) on the same or adjacent files, per colour combination, from the perspective's view; shared by all king buckets. Three windows: all pairs (372 pairs, 1,488 inputs); same file at any distance plus adjacent files at most one rank apart (928); at most one rank apart (608). The first production pawn-pair net used the 608-input window. Rows are used as int8. [47, prose doc] [51, commit text]
- Other input relationships: none.
- Factoriser: king buckets were trained "factorised" at introduction; an output-bucket factoriser came after 0.6.0. [51, commit text]

### Body
- First hidden layer (accumulator) width per perspective: 1024 (512, then 768, then 1024 during the first week). [45, README] [51, commit text]
- Further layers: 16 and 16. The first is int8, one set of weights per output bucket; the second is float. [45, README] [47, prose doc] [51, commit text]
- Layer stacks: the hidden and output layers are kept per output bucket. [47, prose doc] [51, commit text]
- Output buckets: 6, by piece count in equal steps of six pieces (first bucket 2-7 pieces). Reduced from 8 so that the 2-5-piece positions which tablebase-adjudicated data generation never records do not leave one bucket trained only on old data: +3.9 (26.6k games). [47, prose doc] [50, release notes] [51, commit text]
- Skip connections, pairwise multiplication, other structure:
  - Pairwise multiplication of accumulator halves. [45, README]
  - A "pre-activation readout": the first hidden layer's pre-activations also feed the output linearly, added 2026-10-10 (+3.9 +- 2.1; "wrong-way" evaluations in decided positions fell from 20.4% / 14.8% to 0.9% / 0.2%). [51, commit text]
  - The format also supports a linear skip neuron and a dual-activation second layer. Whether the 0.6.0 net keeps the readout is not stated: UNVERIFIED. [47, prose doc]

### Activations
- After the accumulator: pairwise (clamp both halves and multiply); introduced 2026-10-07 at +6.6 over the SCReLU form and 7.3% faster with the neuron permutation. [47, prose doc] [51, commit text]
- In the head: squared clipped activation on the hidden layers by the format description. Dual activation is supported, but its use in 0.6.0 is not stated (the file size argues against it; inference by arithmetic). [47, prose doc]

### Quantisation
- Integer types per layer: accumulator int16 for piece-square rows; int8 for threat and pawn-pair rows (pair rows are clamped to int8; 0.1-0.2% of a trained net's pair weights exceeded it); first hidden layer int8 weights with float biases; later layers float. [47, prose doc] [51, commit text]
- Quantisation-aware training or other rounding care: QAT is part of the hidden-layer recipe. Rounding the first hidden layer's 8-bit inputs to nearest instead of flooring halved a mean error of 7.8 cp against the exact float forward and removed a systematic -2.4 cp side-to-move bias, at the same cost. [51, commit text]

### Inference speed
All from commit texts; "nps" figures are the engine's bench.
- Accumulator refresh cache: per (perspective, king bucket, mirror state) an accumulator plus the piece bitboards it stands for, so a rebuild applies only the pieces that differ. An 8-bucket net went from about 20% to about 12% slower than the unbucketed net (2026-10-01). With threats, a king changing bucket keeps its threat part: child = new bucket's cache entry + parent - old bucket's entry + changed threats (+3.7% nps on the threat net). A mirror change still refreshes fully. [51, commit text]
- Lazy or deferred accumulator updates: an accumulator is updated only when a position at or below it is evaluated; pending updates are applied from the nearest computed ancestor. About a third of pushed accumulators were never needed. +6% nps on the pawn-pair net (3.26M -> 3.47M), +19% on the threat net (1.43M -> 1.70M). [51, commit text]
- Fused updates: all rows a move changes (int16 piece rows, int8 pawn-pair and threat rows) are applied in one register-blocked pass, so the accumulator is read and written once per move instead of twice: 1.70M -> 1.91M nps (+12%, AVX-512). Before that, applying a move's threat rows in one prefetched pass instead of one pass per row: +7.9% (1.33M -> 1.435M). [51, commit text]
- Accumulator stack: each ply keeps its position and move for the deferred update. [51, commit text]
- Pairwise multiplication: yes, with a permutation that moves neuron pairs together (see the sparse item). [51, commit text]
- int8 layers: int8 first hidden layer; VNNI dot products where available, ARM dot-product kernels chosen at run time. [45, README] [51, commit text]
- Sparse first dense layer: yes. [51, commit text]
  - The kernels list non-zero groups of 4 inputs without branches (a table from each 8-bit mask to group offsets) and load only those weights: 1912 against 2345 cycles per node (AVX2) and 1733 against 2105 (AVX-512) for the dense kernels on a first probe net.
  - Listing the groups in the same pass as the 8-bit conversion: +1.7 to +2.3% nps.
  - Feature-transformer neuron permutation by co-activation, moving pairwise partners together: non-zero groups 53.5% -> 39.0%, +2.7% nps with 16 concurrent engines.
- Evaluation cache: an eval cache exists (its slot is prefetched for null-move and ProbCut children, with the TT bucket: about +0.7% nps under 16 concurrent benches). Size and hit rate: not published. [51, commit text]
- SIMD and VNNI work: AVX2 and BMI2 are the x86 floor; AVX-512, VNNI and PEXT paths are chosen at start-up; NEON kernels for every layer. An AVX-512 block holds 512 accumulator values in 16 registers, AVX2 128 in 8. The threat net ran 1.91M nps with AVX-512 against 1.73M forced to AVX2 on the same machine. [45, README] [51, commit text]
- Memory layout and prefetching [51, commit text]:
  - Feature-transformer and threat weights are used in place from the net embedded in the binary (64-byte aligned), so every process of one binary shares the pages: with 32 concurrent engines +35% to +45% nps per process, with 16 +18% to +19%, with one about equal; SPRT +2.3 (47k games).
  - One shared huge-page copy of the net per host, found by a hash of the weights, so different binaries with the same net share it: SPRT +3.0; 30 concurrent engines +3.4% (one binary) or +10.3% (two binaries); a single engine about 2.6% fewer cycles per node.
  - Weight buffers of 2 MB and more are aligned and marked for huge pages.
  - Tried and dropped: prefetching the second perspective's rows in the update (slightly slower; the hardware prefetcher already follows a row) and continuation-history rows at node entry.
  - Net file about 85 MB (84,774,784 bytes for the release-period nets; 51.7 MB before threat inputs). [50, release notes and asset list]
- Anything else: threat deltas restricted to affected pieces: 866k -> 1.33M nps (+54%); deltas from bitboard set differences: 1.98M -> 2.19M (+10.6%); indexing per attacker with a branch-free count step: +2.3%. [51, commit text]
- Speed cost or gain for any architecture change [51, commit text]:
  - Threat inputs: the first net ran at about 0.65 times the nps of the pawn-pair net on the test fleet, yet +20.2 at 10+0.1 and +90.9 at fixed nodes, with a shorter training run.
  - Pawn pairs (608-input window) against a twin without them: +18.6 FN, +1.6 STC, +6.5 LTC.
  - First hidden-layer net (4 buckets): 26% to 45% more cycles per node than the single-layer net on a probe; promoted at +7.3.
  - King buckets, 4 against none: fleet nps about 0.93-0.95; +7.9 at 10+0.1 with the refresh cache, +15.3 FN.
  - Accumulator 512 -> 768: +8.0 +- 3.3 at 10+0.1 ("the gain survives the slower eval").
- Hardware sensitivity reported: the sharing gains appear only with many concurrent engines; a single engine gains little. [51, commit text]

### Training data
- Size: about 33 billion positions for 0.6.0 (roughly double 0.5.0's). The public dataset now holds about 37.6 billion scored positions from about 323 million games. [45, README] [49, prose doc] [50, release notes]
- Type: **own self-play only**, generation after generation, bootstrapped from a hand-written material-and-mobility evaluation. Each generation is played by the best net trained on the earlier ones (about +180 Elo for the first trained step, then +10 to +55 per generation). Both sides are the same build and net. Published under CC BY 4.0. [49, prose doc]
- Labels: the search score of the playing engine at a fixed node budget per move: 5,000 for the first sets, 15,000 for some early sets, **8,000 for the standard sets since**. Label-depth experiments at 5,000 and 15,000 nodes exist (the 15,000-node sets were later dropped from the mix). [49, prose doc] [51, commit text]
- Openings, filtering, tablebase use [49, prose doc] [50, release notes]:
  - Openings are 8-9 random plies from the start position (or from a random double-Fischer-random start), kept only if the search score is within a bound. DFRC sets are held at about 10-15% of the data.
  - From early November 2026 some sets start from human grandmaster opening lines plus 2-3 random plies.
  - Decisive games are played out with 5-man tablebase adjudication. Older sets were relabelled with 5-piece Syzygy results (game result fixed at the first table position; table positions scored as flat wins, losses or draws).
  - Scores of all generations are put on one scale by a per-set calibration against that set's own win/draw/loss model. The trainer refuses uncalibrated data.

### Training recipe (concepts only)
- Trainer: bullet since October 2026 (a private training crate). A minimal CPU trainer of the project's own bootstrapped the first nets. [45, README] [48, README]
- Loss and target: result blend with calibrated search scores and a WDL output link; values not recorded. [51, commit text]
- Stages and schedule: single runs on the whole calibrated mix. Longer runs were measured twice: +5.7 STC and +5.0 LTC for a two-thirds longer run on the same data (October), and +2.9 for a 25% longer run at the release (November). Two seeds of the same recipe differed by about 4 Elo (-1.2 against +3.1). [51, commit text]
- Regularisation, optimiser, anything unusual: optimiser changed from AdamW to Ranger (+2.2); a piece-count filter (+2.9, bundled with a data change); QAT; a WDL-model filter on positions; a soft early-ply filter. [50, release notes] [51, commit text]

### Measured gains for network changes
- Calibrated labels against an uncalibrated twin: +6.7; promoted at +4.1 (the eval spread fell to about 0.82 times the previous net's). [51, commit text]
- Tablebase-relabelled old sets against the same data unrelabelled: +1.9; the unrelabelled net had failed (-3.7). [51, commit text]
- First set from grandmaster-book openings in the mix (with two other new sets): +6.4 (9.3k games). [51, commit text]
- 16 king buckets + Ranger + more data on the threat net: +4.9. [51, commit text]
- Threat net with 13% more data and a longer run: +10.1; doubling its run length again: +2.5. [51, commit text]
- 0.6.0 over 0.5.0 (release): +74.3 +- 5.45 at 40+0.4, +71.5 +- 6.0 at 10+0.1. [50, release notes]

### Architecture history
- 2026-09-29/30: first nets on own data, 512 wide, single layer, 8 material output buckets, mirrored; then 768 wide (+8.0). [51, commit text]
- 2026-10-01: 4 king buckets, 1024 wide, refresh cache (+7.9).
- 2026-10-05: first hidden-layer net: 1024 (SCReLU) -> 16 (int8, per output bucket) -> 16 -> 1, with QAT (+7.3); data 3.4 billion positions.
- 2026-10-07/08: pairwise accumulator with neuron permutation (+6.6); 16 king buckets (+14.2); pairwise with 16 buckets (+7.5).
- 2026-10-10/11: pre-activation readout (+3.9); 32 king buckets (+2.8).
- 2026-10-13: calibrated labels (+4.1). 2026-10-17: 0.5.0.
- 2026-10-20/21: pawn pairs (+3.1 with code; twin +1.6 / +6.5); longer runs.
- 2026-10-25: threat inputs (+20.2). 2026-10-27: 16 king buckets, Ranger.
- 2026-10-29: 6 output buckets (+3.9). 2026-11-01: tablebase-relabelled old data. 2026-11-05: release-candidate net at the longer run length (+2.9). 2026-11-06: 0.6.0. [50, release notes] [51, commit text]

### Since the rated version
- Three data-and-seed promotions (+1.7, +3.4, +3.1). [51, commit text]
- Refresh through the same one-pass row kernel as the update: +2.0. [51, commit text]
- A 1280-wide accumulator specialisation: that net runs at 0.88 times the nps of its 1024 twin (0.80 before); not production. [51, commit text]
- Output-bucket factoriser (a shared output layer added to each bucket's during training and merged afterwards): +9.4 over 10,266 games, where the same data without it was -0.8 (2026-11-14). [51, commit text]

### UNVERIFIED and not published
- Squares per king bucket of the final 16-bucket layout beyond the short phrase quoted above.
- Which threat variant and pawn-pair window the 0.6.0 net uses (56,890 and 608 are an inference from file size), and whether it keeps the readout.
- Exact definition of a threat feature (the prose refers to the source).
- The private research repository holds the training log; trainer values are in any case not recorded here.
- That 0.6.0 embeds the net promoted on 2026-11-05 rests on a commit message saying the next promotion was "the first after the v0.6.0 tag".

---

## Sources

All opened on 2026-11-14. "API" means the text was read through the signed-in `gh api` (prose endpoints only; 43 calls in total, quota never below 4,600).

| # | URL | What it is | Source type | Used for |
|---|---|---|---|---|
| 1 | https://raw.githubusercontent.com/Tors3/Triumviratus/HEAD/README.md | Triumviratus README | README | Triumviratus |
| 2 | https://raw.githubusercontent.com/Tors3/Triumviratus/HEAD/docs/networks/NETWORKS.md | Network log of every Triumviratus net | prose doc | Triumviratus |
| 3 | https://raw.githubusercontent.com/Tors3/Triumviratus/HEAD/docs/project/NOVELTIES.md | Register of claimed novelties | prose doc | Triumviratus |
| 4 | https://raw.githubusercontent.com/Tors3/Triumviratus/HEAD/docs/project/CONTRIBUTING.md | Contribution rules and merged contributions | prose doc | Triumviratus |
| 5 | https://raw.githubusercontent.com/Tors3/Triumviratus/HEAD/docs/project/HISTORY.md | Version history | prose doc | Triumviratus |
| 6 | https://github.com/Tors3/Triumviratus/releases/tag/v8.1 (API) | 8.1 release notes | release notes | Triumviratus |
| 7 | https://raw.githubusercontent.com/Tors3/Triumviratus/HEAD/docs/development/archive/DEVELOPMENT_8.0.md | 8.0 development log (sections 1-6, 9, 20, 23, 28-30, 36-37, 40, 46, 48.3 read) | prose doc | Triumviratus |
| 8 | https://raw.githubusercontent.com/Tors3/Triumviratus/HEAD/docs/development/archive/EXPERT_BLEND_8.0.md | Note on the rejected expert blend | prose doc | Triumviratus |
| 9 | https://raw.githubusercontent.com/Tors3/Triumviratus-Networks/HEAD/README.md | Networks repository README | README | Triumviratus |
| 10 | https://raw.githubusercontent.com/Tors3/Triumviratus-Networks/HEAD/recipes/07_consilium-plebis/README.md | Recipe README of the 8.1 net | prose doc | Triumviratus |
| 11 | https://raw.githubusercontent.com/Tors3/Triumviratus-Networks/HEAD/recipes/07_consilium-plebis/docs/DESIGN_NEXT_NETWORK_2026-10-21.md | Design study for the 8.1 net; also holds a second-hand table of other engines' nets | prose doc | Triumviratus; second-hand for PlentyChess, Reckless |
| 12 | https://raw.githubusercontent.com/Tors3/Triumviratus-Networks/HEAD/recipes/07_consilium-plebis/DATA.md | Training data list of the 8.1 net | prose doc | Triumviratus |
| 13 | https://raw.githubusercontent.com/Tors3/Triumviratus-Networks/HEAD/recipes/07_consilium-plebis/LOG_RUN.md | Run log (engine-cost sections read) | prose doc | Triumviratus |
| 14 | https://github.com/Tors3/Triumviratus/tree/main/docs (and /development, /development/archive, /networks, /project) | Folder listings, names only | other | finding documents |
| 15 | raw URLs for HISTORY.md at the repository root, docs/development/DEVELOPMENT_8.1.md, docs/development/archive/DEVELOPMENT_8.1.md, recipes/07_consilium-plebis/analysis/engine_speed/README.md | Failed fetches (404) | other | none |
| 16 | https://raw.githubusercontent.com/gab8192/Obsidian/HEAD/README.md | Obsidian README | README | Obsidian |
| 17 | https://github.com/gab8192/Obsidian/releases (API) | All release notes | release notes | Obsidian |
| 18 | https://github.com/gab8192/Obsidian/commits (API: four commit-message searches and the commit list 2024-10-22 to 2025-05-22, messages only) | Commit messages | commit text | Obsidian |
| 19 | https://github.com/gab8192/Obsidian-nets and its releases (API) | Net repository page and release asset list (names, sizes) | release asset list | Obsidian |
| 20 | https://wiki.chessdom.org/Obsidian_questionnaire_20251110 | TCEC questionnaire (confidential, no content) | TCEC | Obsidian |
| 21 | https://talkchess.com/viewtopic.php?t=83249 (8 pages) and ?p=957893 | TalkChess thread "About Obsidian" | forum | Obsidian (Lc0 data, second-hand; nothing else used) |
| 22 | https://www.chessprogramming.org/Obsidian, /PlentyChess, /Reckless; https://wiki.chessdom.org/Obsidian, /PlentyChess, /Plentychess, /Reckless | Failed fetches (404) | other | none |
| 23 | Web search "Obsidian chess engine gab8192 NNUE architecture ..." | One search; led to 21 only | other | none |
| 24 | https://wiki.chessdom.org/Engines_by_TCEC_Questionnaire | Index of questionnaires | TCEC | finding 20, 25, 26 |
| 25 | https://wiki.chessdom.org/Plentychess_questionnaire_20251012 | PlentyChess TCEC questionnaire | TCEC | PlentyChess; second-hand for Reckless |
| 26 | https://wiki.chessdom.org/Reckless_questionnaire_20251024 | TCEC questionnaire (confidential, no content) | TCEC | Reckless |
| 27 | https://raw.githubusercontent.com/Yoshie2000/PlentyChess/HEAD/README.md | PlentyChess README | README | PlentyChess |
| 28 | https://github.com/Yoshie2000/PlentyChess/releases (API) | All release notes | release notes | PlentyChess |
| 29 | https://github.com/Yoshie2000/PlentyChess/pulls (API: PR #400 and four PR-text searches) | PR titles and descriptions | PR text | PlentyChess |
| 30 | https://github.com/Yoshie2000/PlentyChess/pulls?q=is:closed (API, 400 titles) | PR title list | PR text | PlentyChess |
| 31 | https://github.com/Yoshie2000/PlentyChess/pull/N for N = 93, 97, 114, 119, 141, 206, 216, 226, 229, 232, 239, 261, 266, 297, 300, 340, 342, 400, 411, 432, 437, 453, 476, 481, 482, 487, 488, 489, 490 | PR conversation pages (description and comments; no diff tab) | PR text | PlentyChess |
| 32 | https://raw.githubusercontent.com/Yoshie2000/PlentyNetworks/HEAD/README.md and https://github.com/Yoshie2000/PlentyNetworks/releases (API) | Net repository README, release notes and asset list | release notes, release asset list | PlentyChess |
| 33 | https://raw.githubusercontent.com/codedeliveryservice/Reckless/HEAD/README.md | Reckless README | README | Reckless |
| 34 | https://github.com/codedeliveryservice/Reckless/releases (API) | All release notes | release notes | Reckless |
| 35 | https://github.com/codedeliveryservice/Reckless/pulls (API: three PR-text searches) | PR titles and descriptions | PR text | Reckless |
| 36 | same, merged 2025-06-10 to 2026-03-01 (API, 352 titles) | PR title list | PR text | Reckless |
| 37 | https://github.com/codedeliveryservice/Reckless/pull/N for N = 393, 416, 463, 608, 621, 660, 710 | PR conversation pages | PR text | Reckless |
| 38 | https://recklesschess.space/networks/Reckless/ | OpenBench network list (names and hashes only) | OpenBench | not used |
| 39 | https://raw.githubusercontent.com/adamtwiss/coda/HEAD/README.md | Coda README | README | Coda |
| 40 | https://raw.githubusercontent.com/adamtwiss/coda/HEAD/CLAUDE.md | Coda project notes for its agents | prose doc | Coda |
| 41 | https://raw.githubusercontent.com/adamtwiss/coda/HEAD/NOTICES.md | Attribution notices | prose doc | Coda (nothing network-specific) |
| 42 | https://github.com/adamtwiss/coda/releases (API) | All release notes and asset lists | release notes, release asset list | Coda |
| 43 | https://github.com/adamtwiss/coda/commits (API: three commit-message searches) | Commit messages | commit text | Coda |
| 44 | https://github.com/adamtwiss/coda and /tree/main/docs | Folder listings, names only | other | finding documents |
| 45 | https://raw.githubusercontent.com/adamtwiss/incipit/HEAD/README.md | Incipit README | README | Incipit |
| 46 | https://raw.githubusercontent.com/adamtwiss/incipit/HEAD/CLAUDE.md | Incipit rules for its agents | prose doc | Incipit (rules; no network facts) |
| 47 | https://raw.githubusercontent.com/adamtwiss/incipit/HEAD/docs/net-format.md | Network file format description | prose doc | Incipit |
| 48 | https://raw.githubusercontent.com/adamtwiss/incipit/HEAD/trainer/README.md and /datatools/README.md | Trainer and data-tool READMEs | README | Incipit |
| 49 | https://huggingface.co/datasets/adamtwiss/incipit-data/raw/main/README.md | Dataset card of Incipit's self-play data | prose doc | Incipit |
| 50 | https://github.com/adamtwiss/incipit/releases (API) | Release notes and asset lists | release notes, release asset list | Incipit |
| 51 | https://github.com/adamtwiss/incipit/commits (API: two commit-message searches) | Commit messages | commit text | Incipit |
| 52 | https://github.com/adamtwiss/incipit, /tree/main/docs; raw engine/README.md (404) | Folder listings, names only; one failed fetch | other | finding documents |
| 53 | https://github.com/gab8192?tab=repositories, https://github.com/Yoshie2000?tab=repositories | Repository lists, names only | other | finding 19 and 32 |

Credit lines (as the pages name them):

- **Triumviratus**: Francesco Torsello, in collaboration with Maurizio Platino; GPLv3 with an attribution term on its inference files. Credited by the project: pawn pairs to Jonathan Hallstrom (Pawnocchio); base architecture and trainer to Stockfish (GPLv3); training data to the Leela Chess Zero project and the Hugging Face relabellings by Joost VandeVondele, linrock and Shawn Xu. Speed contributions by Houze Guo and A Tin Man.
- **Obsidian**: gab8192 (handle; no other name on the pages opened). Licence not stated on the pages opened today (GPL-3.0 per the prior survey). Trainer: bullet by jw1912.
- **PlentyChess**: Yoshie2000 (the author asks to be identified by this handle); GPL-3.0. Threat inputs credited by the author to Viren6 and jw1912 (Monty), sscg13, vondele and linrock (Stockfish branch and test nets), and yukarichess; pawn pairs to Jonathan Hallstrom; speed ideas to anematode, cj5716, rn5f107s2 and 87flowers. Trainer: bullet by jw1912.
- **Coda**: Adam Twiss; GPL-3.0-or-later. Training data: the LCZero project (ODbL-1.0) and CC0 data by Joost VandeVondele. Trainer: bullet by jw1912.
- **Reckless**: codedeliveryservice with co-authors peregrineshahin and styxdoto (handles, as the release notes name them); AGPL-3.0. Threat inputs credited to jw1912 and Viren6 (Monty), Yoshie2000 (PlentyChess) and the Stockfish team; speed work largely by 87flowers. Trainer: bullet.
- **Incipit**: Adam Twiss; GPLv3 or later; training data CC BY 4.0 ("Incipit self-play data (Adam Twiss)"). Tools credited: OpenBench (Andrew Grant), fastchess, viriformat (Cosmo Bobak), bullet (Jamie Whiting), Fathom.

## Clean-room statement

I opened no source file, header, build file, training script, trainer configuration, patch, diff, "Files changed" tab, blame view, code search result or network file of any engine or trainer. I cloned or downloaded no repository, release archive, binary or network file. All reading was of READMEs, docs-folder prose, release notes, PR descriptions and comments, commit messages, TCEC wiki pages, one forum thread and one dataset card.

Things that came close, and how they were handled:

- **Folder listings.** GitHub folder listings (sources 14, 44, 52, 53) showed the names of source folders and files next to the documents. None was opened, and no source file name is recorded in this report.
- **Release asset lists.** Release pages list network files and binaries with their sizes (sources 19, 32, 42, 50). I used the names and byte sizes shown; nothing was downloaded.
- **Code-like material inside prose.** Triumviratus's recipe README and run log hold a signature formula, file-format tags, build flags, and script and patch names. Coda's notes hold a list of its source files and quantisation constants. Incipit's net-format document holds file-layout tables and index formulas. I did not transcribe those fragments; the report keeps only counts, layouts and concepts. No quantisation scale, clipping bound, learning rate, result-blend weight or search constant is recorded.
- **Commit messages close to code.** Coda's and Incipit's commit messages name functions, intrinsics and small formulas while describing changes. They are commit text (allowed), but closer to the code than the other sources. Every fact taken from them is tagged "commit text" and described without identifiers.
- **A second-hand table.** Source 11 (a Triumviratus design note) contains a table of other engines' network shapes that its authors compiled by reading those engines' source. It is public prose but second-hand. I used it only where tagged "second-hand", and never as the sole basis of a field.
- **API endpoints.** For commits I used only the list and search endpoints, which return messages, and never the single-commit or pull-request-files endpoints, which return patches.
- **My own arithmetic.** Two file-size consistency checks (Coda's threat space; Incipit's threat variant and pawn-pair window) are my own arithmetic from published sizes and are marked as inferences.

Files I created, all inside my scratch folder: three small text-extraction scripts (`strip.py`, `strip_tc.py`, `prbody.py`) and the fetched pages under `pages/`. `report.md` was not created (the harness refused the write). I deleted nothing, edited nothing in the repository or the kb worktree, committed nothing and started no job.
