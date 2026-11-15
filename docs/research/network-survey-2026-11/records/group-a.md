# Network records, group A: Stockfish, Torch, Dragon by Komodo, Ethereal

Clean-room network survey of 2026-11-14 ([README](../README.md)). Written by survey agent A from public prose only and assembled unchanged except for local paths. Source numbers in brackets refer to the Sources table at the end of this file. Every engine here is REFERENCE ONLY for ideas; its code, nets and data are OFF-LIMITS for Fork.


Survey date 2026-11-14. Clean-room: public prose only (see the statement at
the end). Every fact carries a source number from the table at the end and
its source type. "Prior survey" marks facts carried from
`engine-survey-2026-11`.

**How to read the Elo figures.**
- Stockfish reports SPRT results as win/loss/draw totals, not Elo. Where a
  figure is marked **(derived)** I computed the point estimate from the
  totals printed in the commit message; a passed SPRT's estimate leans
  high. Figures without that mark are quoted as the source reports them.
- Stockfish time controls as its commit messages name them: STC 10+0.1,
  LTC 60+0.6, VLTC 180+1.8 (single thread) or 60+0.6 with 8 threads
  ("VLTC SMP") [4, commit text]. The conditions of "VVLTC" are not spelled
  out in the text I read.
- Ethereal (OpenBench): STC 10+0.1, LTC 60+0.6, one thread, as each commit
  message prints them [51, commit text].

---

## Stockfish 19 (CCRL #1, 3803)

Released 2026-09-05 [3, release notes]. Its release notes name the network
generation **SFNNv16** [3, release notes]; the architecture history dates
SFNNv16 from 2026-07-20 to 2026-09-30 [1, docs]. The last net change before
the release is the AdamW-trained net of 2026-08-19 [5, commit text], so that
is the rated net. SFNNv17 to v20 are development-branch work and are kept
under "Since the rated version".

**One-line architecture:** assembled by me from the SFNNv16 documentation
diagram's labels [10, docs diagram] and the release notes [3]:
`(86,896 inputs -> 1024) x 2 perspectives -> pairwise product (1024 -> 512 per perspective) -> 1024 -> 32 -> [squared + plain clipped ReLU, 64] -> 32 -> [squared + plain clipped ReLU; concatenated with the previous 64 = 128] -> 1, in 8 layer stacks picked by piece count; plus a direct piece-square (PSQT) path of 8 outputs`.
The engine does not print this string anywhere I could read.

### Inputs
- Feature set (what an input means; inputs per perspective if stated):
  three blocks summed into one accumulator, **86,896 inputs per
  perspective** [10, docs diagram]:
  - **HalfKAv2_hm** piece-square inputs: (own king square on a mirrored
    half board, piece square, piece kind) = 32 x 64 x 11 = **22,528**
    [10, docs diagram; 4, commit text of 2024-04 prints 22528];
  - **Full_Threats**: one input per "piece A on square a attacks piece B on
    square b" [2, docs; 12, PR attachment]. **59,808** inputs (the figure
    is printed on the SFNNv18-v20 diagrams; 86,896 − 22,528 − 4,560 gives
    the same number for v16, my arithmetic) [10, docs diagram];
  - **PP_3Wide** pawn pairs: **4,560** inputs (same remark) [10, docs
    diagram].
- King input buckets: 32, one per king square after mirroring the king
  onto files e-h; no coarser grouping [2, docs; 10, docs diagram]. The
  bucket count was never "grown"; it has been 32 since SFNNv3 (2021-08),
  when mirroring halved the 64 king squares [4, commit text].
- Horizontal mirroring: each perspective's board is mirrored so its own
  king stands on files e-h; the documentation says the strength difference
  against no mirroring is "hardly measurable" while the first layer halves
  [2, docs]. Threat and pawn-pair inputs are mirrored by the same king rule
  [2, docs; 12, PR attachment].
- Threat or attack inputs:
  - relation: attacker piece, attacked piece and both squares; x-ray
    attacks are not included (an x-ray variant lost more than 50 Elo at
    fixed nodes in Monty, the engine the idea came from) [12, PR
    attachment];
  - redundant inputs removed: when the attack is necessarily mutual, only
    one direction is kept (pawn-bishop, pawn-queen, pawn-king,
    bishop-queen, rook-queen, king-queen); for two pieces of the same kind
    one of the two orderings is dropped; king-king is impossible [2, docs];
  - king threats: SFNNv11 removed "piece attacks king" (non-regression;
    saved 13 MB and about 0.8 threat updates per incremental update);
    SFNNv12 removed "king attacks piece" (non-regression) [4, commit text;
    1, docs]. The v16 diagram describes threats as non-king to non-king
    [10, docs diagram];
  - SFNNv14 added "pawn pushes against a pawn" (the square in front of a
    pawn counts as attacked when another pawn stands on it) [4, commit
    text]; SFNNv16 removed all pawn-pawn threats because the pawn-pair
    block covers them [4, commit text; 2, docs];
  - how they are updated: incrementally, from a per-move list of changed
    threats built with bitboards in make-move; the technique came from
    PlentyChess and was ported by its author and a Stockfish developer
    [12, PR attachment]. Since 2026-06 threats and piece-square inputs
    share one accumulator per side [4, commit text].
- Pawn features: PP_3Wide = unordered pairs of pawns (either colours) on
  the same or adjacent files, indexed by the two colours and two squares.
  The index space covers all pawn pairs for fast SIMD indexing, but pairs
  more than one file apart never fire [2, docs]. The idea is credited to
  pawnocchio's author, who found that in a net trained on all pawn pairs
  the important ones were at most one file apart [4, commit text]. No
  passed-pawn input.
- Other input relationships: none in SFNNv16 beyond the three blocks. Side
  to move is expressed by ordering the two perspectives [2, docs].
  (Opponent-queen and "no heavy pieces" routing arrived after the rated
  version.)
- Factoriser or other training-only input structure: the trainer uses
  virtual "factor" inputs (for example plain piece-square inputs shared by
  all king squares) whose weights are folded into the real ones after
  training; the documentation says the factoriser matters mainly early in
  training [2, docs]. Which factors the SFNNv16 recipe used:
  UNVERIFIED (only in the recipe's configuration file).

### Body
- First hidden layer (accumulator) width per perspective: **1024**
  (int16) [10, docs diagram; 1, docs: "L1 size reduced to 1024" at
  SFNNv10].
- Further layers: 2 hidden dense layers and an output: 1024 -> 32, then
  64 -> 32, then a 128-input dot product [10, docs diagram].
- Layer stacks: **8** copies of the whole head; the stack is picked by
  (piece count − 1) / 4, integer division [10, docs diagram; 2, docs].
- Output buckets: the same 8 stacks serve as output buckets; the PSQT path
  also has 8 outputs picked the same way [10, docs diagram].
- Skip connections, pairwise multiplication, other structure:
  - **pairwise multiplication**: each perspective's 1024 clipped
    activations are split into two halves of 512 and multiplied element by
    element, giving 512 per perspective and 1024 inputs to the first dense
    layer [10, docs diagram]. Introduced in SFNNv4 as a non-linearity
    "slightly faster" than a quantised sigmoid; it also halves the next
    layer's inputs [4, commit text];
  - **skip paths (SFNNv15)**: the output layer reads the concatenation of
    both hidden layers' activations (64 + 64 = 128), and two of the first
    dense layer's 32 outputs also feed the result directly [6, PR text;
    10, docs diagram];
  - **PSQT path**: every input also has 8 direct weights; the result is
    half the difference of the two perspectives, added to the head's
    output [10, docs diagram]. (Removed in SFNNv17.)

### Activations
- After the accumulator: clipped ReLU, then the pairwise product [10, docs
  diagram].
- In the head: **dual activation** after each hidden layer: a squared
  clipped ReLU and a plain clipped ReLU of the same 32 values,
  concatenated [10, docs diagram]. The first layer has had it since SFNNv5
  (2022-05) [4, commit text]; SFNNv15 extended it to the second layer [10,
  docs diagram, v14 against v15].

### Quantisation
- Integer types per layer: accumulator int16; piece-square first-layer
  weights int16 in v16 [10, docs diagram]; threat weights int8, widened to
  int16 when added [4, commit text 2025-12; 12, PR attachment];
  pawn-pair weights int8 [2, docs]; dense layers int8 weights with int32
  biases and int32 sums; output int32; the final conversion to engine
  units is done in int64 since the QAT net [2, docs; 4, commit text
  2026-05]. No float layer.
- Quantisation-aware training: yes, since the net of 2026-05-27
  ("SFNNv14.1"): the trainer fake-quantises weights and activations, and
  the scheme was changed so that scales are powers of two and layers may
  use different weight scales [4, commit text; 6, PR text]. Gain
  **+4.4 STC / +1.75 LTC (derived)** [5, commit text]. Before that, the
  trainer only clamped weights to the representable range after each
  optimiser step [2, docs].
- Int8 threat weights: in PlentyChess "+10 Elo STC, +3 LTC, −2 at fixed
  nodes"; Stockfish reports "a similar gain" [12, PR attachment].

### Inference speed
Every item is "no functional change" unless said otherwise.

- **Accumulator refresh cache ("Finny tables")**: added 2024-04-20. Per
  thread, one cached accumulator per king square with the piece bitboards
  it was built from; a refresh applies only the difference between the
  cached and the current position. Idea credited to Koivisto's author. The
  commit text gives test links but **no figure**; the fishtest pages would
  not load [4, commit text; 18]. Follow-ups: combining the remove and add
  passes of a cache refresh, STC +0.8 (derived, 364,032 games); an
  AVX-512 (Ice Lake) version of the cache refresh passed STC (2026-03);
  caches are cleared with the histories, not at each search [4, commit
  text]. Since SFNNv18 the cache also tracks opponent-queen presence [4].
- **Lazy or deferred accumulator updates**:
  - 2020-09/10: update from the accumulator two plies back when the
    previous one is missing, without copying: "about 2% speedup"; then
    look back further and also fill the accumulator one ply before the
    target: "roughly 2-3%" [4, commit text];
  - 2023-02: explicit "populate the parent's accumulator" hint when
    several children will be evaluated: STC +2.3 (derived), passed LTC [4];
  - 2024-09: update all accumulators along the path during an incremental
    update instead of at most two: "at least 0.5%, up to 1% at shorter TC"
    [4];
  - 2025-02: the hint was replaced: **only an evaluation call triggers
    accumulator work**, and when an accumulator must be built from scratch
    the engine also updates *backwards* so later positions find a usable
    parent: **STC +2.7, LTC +0.9 (derived; 337,308 games at LTC)** [4];
  - 2025-04: "double incremental" update (when the second of two pending
    moves captures the piece the first one moved, skip the middle
    accumulator and cancel an add against a remove): STC +1.7 (derived).
    **Removed 2026-04** as non-regression: with the smaller 1024
    accumulator the bookkeeping cost outweighed it; one developer measured
    −0.9%, two others +2% for the removal [4].
- **Fused updates**: add/remove pairs applied in one pass since 2020;
  2025-02 "combine the last 3 add/remove operations" STC +2.4 (derived),
  simplified away 2025-04 [4]. 2026-11 (after the rated version): leftover
  adds and subs combined into one difference, STC +1.2 (derived, my
  figure from 29468/29078/56526) [4].
- **Accumulator stack**: accumulators live on a per-thread stack indexed
  by ply; no copy on make-move. 2025-10: a fixed array instead of a
  growable vector, "+0.45% ± 0.10%" [4]. 2025-01: a simplification of
  per-move updates measured +0.96% (Ryzen 5 7600X), +1.73% (Ryzen 9
  5950X), +1.03% (Core i7-6700K), +0.74% (Raspberry Pi 5) [4].
- **One accumulator for piece-square and threat inputs (2026-06-10)**:
  instead of summing two accumulators at evaluation time, store their sum;
  saves a load/store and halves the accumulators' cache footprint:
  "about 2.5% speedup locally", **STC +4.6 (derived)** [4]. Drawback: every
  king move then recomputed all threat and pawn-pair inputs, fixed by:
- **Hybrid king-move update (2026-07-26, in SF 19)**: new accumulator =
  previous − previous piece-square part + new piece-square part + the
  move's threat and pawn-pair changes, with both piece-square parts taken
  from the refresh cache; used only when enough pieces are on the board
  and not for castling: "+0.60% ± 0.08%" (Core Ultra 9 185H), **STC +2.7
  (derived)**. The author notes his own machine's best piece threshold did
  badly on fishtest [4].
- **Both perspectives updated together (2026-08-01)**: when both sides can
  be updated incrementally, the changed threats are decoded once and the
  pawn-pair enumeration is shared: STC +1.7 (derived) [4].
- **Pairwise multiplication of accumulator halves**: 2024-05 a shift plus
  high-multiply trick removes half of the max operations (the weights are
  stored doubled to make it work): **+1.74% (clang) / +1.79% (gcc)** on a
  Core i7-6700K, STC +1.8 (derived) [4]. 2026-07 fused squared + plain
  clipped ReLU on AVX2: **+2.45%** (EPYC 7R13), STC +0.8 (derived);
  AVX-512 paired activations +0.64% [4].
- **int8 layers or int8 feature-transformer rows**: threat rows int8 since
  SFNNv10, pawn-pair rows int8, reason given: memory bandwidth is the
  bottleneck of accumulation with large input sets, and ARM widens int8 to
  int16 more cheaply than x86 [2, docs; 12, PR attachment]. The
  documentation's blocked sparse layer also relies on int8 weights [2].
  (All rows int8 and row pairing: after the rated version.)
- **Sparse first dense layer**: added 2023-06 (SF 16). Inputs are grouped
  in blocks of 4 and only non-zero blocks are multiplied; the net's
  neurons are permuted so likely-non-zero ones sit together. "Up to 10%"
  (+9.9% on a Ryzen 7 5700U), **STC +10.0 (derived, 8,864 games)** [4].
  The permutation alone is "a minor (~2%), but essentially free" gain
  [2, docs]. Documented input density of that layer: 15% or less for
  common sizes [2, docs]. ARM port: +18.5% / +13.2% / +27.1% / +12.1% /
  +8.2% on five ARM cores [4]. Non-SSSE3 fallback +8.6% [4]. Later:
  smaller index lookup table (2025-01, passed STC after 452,800 games);
  AVX-512 non-zero search "about 1%", VBMI2 "about 0.7%" (2025); the
  non-zero blocks as a bitset computed while the previous layer is
  activated (2026-05): avx2/bmi2 STC +4.6 (derived), "~0 for avx512icl",
  ARM Neoverse V2 +1.3% [4].
- **Evaluation cache**: not reported in anything I read.
- **SIMD and VNNI work**:
  - tiling of accumulator updates in registers (2020-09): STC +10.4, LTC
    +2.2 (derived; small samples) [4];
  - AVX-512: 2023-09 using 16 instead of 32 registers for accumulation,
    **"up to 17%"** depending on compiler (gcc spilled registers; Zen 4);
    2020-08 note that AVX-512 downclocking made avx2 or vnni256 better in
    multithreaded use on Cascade Lake [4];
  - VNNI dot products since 2020-08; splitting the dot-product
    accumulation into 2 or 3 independent chains: 3-way STC +1.1
    (derived); NEON sparse 3-way +1.21% (M3 Pro), NEON dense 2-way +0.56%,
    AVX-VNNI 2-way +0.98% (Core Ultra 9 285H), VNNI dense +0.31% [4];
  - ARM dot-product instructions (2023-02): **+12.6%** on an Apple M1 [4];
  - permuting the first-layer outputs at load time instead of at run time
    (AVX2 and newer): +0.53%, STC +1.35 (derived) [4];
  - peeling one iteration off the piece-square incremental update
    (2026-08): passed on AVX2, **failed on avx512icl**, so gated to AVX2;
    +1.17% locally [4];
  - compiler unrolling: clang left fixed-size update loops rolled on
    AVX-512 builds, forcing 1 KiB stack copies; forcing unrolling gave
    **about +41% nps** in a short non-PGO test (Xeon Platinum 8573C);
    later made unconditional for the critical loops (non-regression) [4];
  - gcc 15 code generation cost ARM about 4% until optimisation barriers
    were added (1,041,619 -> 999,214 -> 1,031,369 nps) [4].
- **Threat-input indexing and bookkeeping** (all after SFNNv10): a first
  speed pass **+5.4%** (Ryzen 9 3950X), STC +4.3 (derived); not copying
  the changed-threat list on make-move, STC +1.8 (derived); index
  generation +0.85%, then +1.32% with unsigned intermediates; early
  rejection of invalid attacker/victim pairs +1.04% (avx512icl); writing
  an index unconditionally and advancing the count only when valid
  (branch-free) +0.67%; precomputed tables on AVX512ICL +0.94%; table
  folding +0.56% [4].
- **Memory layout and prefetching**:
  - prefetching the threat weight rows while the changed-threat list is
    built, into the L2 cache (the threat table was 78 MB): **STC +1.2,
    LTC +1.6 (derived)**, also passed on 8 threads [4];
  - large pages for the weights since 2020 (STC +3.9 derived); 1 GB Linux
    huge pages in SF 19 (no figure) [4; 3, release notes];
  - **shared memory for weights across processes** (in SF 18): up to
    **+38% nps and +24.8 ± 1.9 Elo** on a many-core machine with a large
    L3 running many single-thread games; +5.2 ± 3.5 at 8 threads per
    side; **+4.69 ± 1.4 Elo STC** on the fishtest hardware mix; 1-2%
    slower for a single process where large pages cannot be used [4];
  - NUMA: weights replicated per node, "up to 2.8x" on dual-socket
    machines [3, release notes];
  - net compression: LEB128 for the first layer, 70 -> 39 MiB embedded
    (2023-06); judged useless for int8 rows (2025-12) [4];
  - net file size: 133 MiB at SFNNv9 (3072 accumulator) [4]. SFNNv16's
    size is **not published**; by my arithmetic from the stated
    dimensions and types it is about 115 MB (not a published figure).
- **Anything else**: SF 19 retired the secondary small net (see below);
  universal binaries pick the instruction set at start [3, release notes].
- **Speed cost or gain reported for architecture changes**:
  - threat inputs (SFNNv10, 3072 -> 1024 accumulator): "around +30 Elo at
    fixed nodes"; **5 to 15% slower on x86, comparable on ARM**; STC +2.0,
    LTC +3.8, VVLTC +7.0 (derived); "+13.9 ± 1.9" LTC on ARM; a first
    single-layer 256-wide attempt was "−90 Elo with +50% time odds";
    before int8 rows and incremental tracking the branch stood at −9 STC
    [12, PR attachment; 4, commit text];
  - pawn pairs (SFNNv16): "originally far too large (some 10%)", **3.5%
    slower** at merge; **STC −0.1 (failed), LTC +1.15, VLTC +2.2, VVLTC
    +2.3 (derived)** [4];
  - second hidden layer 16 -> 32 (SFNNv13): STC +0.0 (failed), LTC +3.0,
    VLTC SMP +4.5 (derived); justified by the accumulator having shrunk
    [4];
  - wider accumulators before threats: 1024 -> 1536 +26.9 at 25k nodes
    but STC −6.1 (derived), passed VLTC; 1536 -> 2048 **−7.0% nps**, STC
    −7.2 (derived), LTC "+0.68 ± 1.5"; 2048 -> 2560 **−12.5% nps**, +16.2
    at 25k nodes, STC −6.6 (derived), passed only at VLTC SMP; 2560 ->
    3072 STC "−7.66 ± 3.8", passed VVLTC after SPSA of the net [4];
  - small net removed (2026-05): **−2.5% nps**, STC −3.1, VVLTC −0.5
    (derived, both failed non-regression) and merged anyway because the
    loss was smaller than a pure 2.5% slowdown predicts and the small net
    misjudged fortresses [4];
  - AdamW-trained net (the SF 19 net): first-dense-layer input sparsity
    fell from "60+%" to "50-52%", "a significant slowdown"; STC −0.6
    (failed non-regression), VLTC +1.0, VVLTC +1.7 (derived) [5, commit
    text; 17, PR comment].
- **Hardware sensitivity reported**: several of the above (AVX-512
  register spills; avx512icl failing where AVX2 gained; the non-zero
  bitset neutral on avx512icl); extracting the add/sub loops into
  functions gave +1.13% on one machine and, on fishtest, "a sizable
  speedup on many machines, but also a sizable slowdown on some" [4];
  shared weights gain most with many cores and a large L3 [4]; threat
  inputs cost x86 but not ARM [12].

### Training data
- Size: "hundreds of billions of training positions" [3, release notes];
  the full recipe needs "800+ GB" of data [8, README]. An exact position
  count for the SF 19 net is not published in prose.
- Type: **Lc0 data, relabelled by an Lc0 net.** "Predominantly" Lc0 data,
  with some Stockfish-generated data remaining for the early stages
  [11, TCEC]. From 2026-06 the fine-tuning stage used positions rescored
  with the value head of Lc0's BT4 network: first about 2 B positions
  (LTC +3.9, VLTC +5.0 derived), then +3.5 B (STC +2.1, LTC +1.7), then
  +74 B (STC +4.2, LTC +6.0) [5, commit text]; the release notes say all
  positions were "consistently rescored using a strong Leela net" [3].
  Older Stockfish-generated sets were depth-9 or 5,000-node self-play; the
  last good set of that kind had 16 B positions [16, wiki].
- Openings, filtering, tablebase use: the raw Lc0 data is post-processed
  and filtered, "which involves analyzing all positions with SF at low
  depth" [11, TCEC]. The trainer skips positions by rule: positions with 3
  or 4 pieces were more than 4% of the data and those past ply 100 more
  than 16%, so skipping by piece count was made finer and early plies get
  a soft filter [6, PR text]. Lc0-derived sets are tablebase-rescored by
  Lc0's rescorer [16, wiki]. Stockfish-generated sets used a short opening
  book [16, wiki].

### Training recipe (concepts only)
- Trainer: nnue-pytorch (GPU, PyTorch), about 20 contributors [11, TCEC];
  recipes and their execution in vondele/nettest: one configuration file
  per net, stages chained with restarts, 4-5 days on a high-end GPU
  [9, README]. The recipe files themselves are configuration and were not
  opened.
- Loss and target: evaluation and game result are both mapped to
  win-probability space and blended; the documentation notes an exponent
  above 2 worked well [2, docs]. Recipe changes in 2026: the result blend
  mostly without a schedule (2026-05), then a smooth cosine-shaped
  transition for the last stages (2026-07: STC +3.1, LTC +1.6 derived)
  [5, commit text].
- Stages and schedule: historically first Stockfish-generated data, then
  retraining on Lc0-derived data, "the order of the datasets matters"
  [16, wiki]; 6- and 10-stage sequences for the 2023-24 nets [4]. Weight
  averaging: a nettest change titled "Efficient swa3" preceded the
  2026-05-10 net (STC +3.9, LTC +3.3 derived); its content is
  UNVERIFIED (title only) [7, PR text; 5].
- Regularisation, optimiser, anything unusual:
  - optimiser changed from a Ranger21 variant (with lookahead) to AdamW
    for the SF 19 net: about 5% faster training and less memory; the net
    came out less sparse (see above) [5, commit text];
  - no explicit sparsity loss is used; "the optimiser simply did it", and
    the learning rate seems to affect it [17, PR comment];
  - SPSA of net parameters in games (2024): output weights and biases,
    second-layer weights, first-layer biases, each +1 to +3 Elo per round
    [5]; the 3072 net needed SPSA to pass [4]. The first threat net was
    **not** SPSA-tuned; SPSA was worth about 8 Elo on the previous net
    [12, PR attachment];
  - the small net (2023-12 to 2026-05) was trained only on positions with
    a large material imbalance [4].

### Measured gains for network changes
- SFNNv2 (2021-05: 512x2, HalfKAv2, PSQT, 8 stacks): "+21.74 ± 3.4" STC,
  "+5.85 ± 1.7" LTC; "~15-20% slower" [4, commit text].
- SFNNv3 (mirroring, 1024x2, second layer 16 -> 8): STC +2.8, LTC +3.9
  (derived) [4].
- SFNNv4 (pairwise product, 1024 -> 16 with a 15 + 1 split): STC +5.2,
  LTC +5.4 (derived) [4].
- SFNNv5 (dual activation after the first dense layer): STC +3.4, LTC +3.9
  (derived) [4].
- Dual net (small 128-wide net for lopsided positions, 2023-12): STC +2.0,
  LTC +2.0 (derived) [4].
- SFNNv10 threat inputs: STC +2.0, LTC +3.8, VVLTC +7.0 (derived) [4].
- SFNNv11 / v12 (king threats removed): non-regression [4].
- SFNNv13 (second layer 32): LTC +3.0 (derived), STC neutral [4].
- SFNNv14 (pawn-push threats): STC +2.5, LTC +1.4 (derived) [4].
- QAT net (SFNNv14.1): STC +4.4, LTC +1.75 (derived) [5].
- SFNNv15 (skip architecture, with relabelled data and recipe changes,
  bundled): STC +4.2, LTC +3.3 (derived) [4; 5].
- SFNNv16 (pawn pairs): LTC +1.15, VLTC +2.2, VVLTC +2.3; STC failed
  (derived) [4].
- Release: SF 19 against SF 18 "up to 44" Elo [3, release notes].

### Architecture history
- 2020-08 SFNNv1: HalfKP 256x2-32-32-1 [1; 4].
- 2021-05 SFNNv2: 512x2-16-32-1, HalfKAv2, PSQT outputs, 8 layer stacks
  by piece count [4].
- 2021-08 SFNNv3: horizontal mirroring, 1024x2, second layer 8 [4].
- 2021-11/2022-02 SFNNv4: pairwise product, 1024 -> 16 (15 + 1) [4; 1].
- 2022-05 SFNNv5: dual activation [4].
- 2023-05 to 2024-04 SFNNv6-v9: accumulator 1536, 2048, 2560, 3072 [1].
- 2023-06: sparse first dense layer, compression [4]. 2023-12 to 2026-05:
  secondary small net [4; 3].
- 2025-11 SFNNv10: threat inputs, accumulator 1024; inputs 102,384 [1; 10].
- 2026-01/02 SFNNv11, v12: king threats removed; inputs 89,392 then
  82,672 [1; 10].
- 2026-02 SFNNv13: second layer 32 [1]. 2026-04 SFNNv14: pawn-push
  threats; inputs 83,248 [1; 10]. 2026-05 SFNNv14.1: QAT scheme [1].
- 2026-07-03 SFNNv15: skip architecture, dual activation on both layers
  [6; 10]. 2026-07-20 SFNNv16: pawn pairs; inputs 86,896 [1; 10].

### Since the rated version
- SFNNv17 (2026-09-30): PSQT path removed, non-regression (STC +1.8, LTC
  +1.9 derived), "training speed significantly faster" [4].
- Longer training (2026-09-13): STC +1.6, LTC +1.5; longer low-rate
  fine-tune (2026-10-10): STC +0.6, LTC +1.8 (derived) [5; prior survey].
- **SFNNv18 (2026-10-13)**: three changes at once [17, PR comment]:
  piece-square inputs conditioned on opponent-queen presence (32 king
  squares x 2 = 45,056 inputs, total 109,424); layer stacks 8 -> 32 (piece
  count x own/opponent queen presence); **all first-layer rows int8**,
  compression dropped. STC +4.2, LTC +3.6 (derived). The three
  single-change ablations all failed non-regression against the bundle;
  "output buckets only" came closest [4; 10].
- **Pairing int8 rows (2026-10-17)**: widen two rows at once with one
  shuffle; rows permuted at load: **+7.0% (avx512icl), +5.2% (avx2),
  +10.7% (sse4.1)** on an Ice Lake server core, STC +4.5 (derived) [4;
  prior survey].
- SFNNv19 (2026-10-28): a third piece-square block for "no rooks or
  queens" (32 x 3 = 67,584 inputs, total 131,952): STC +2.4, LTC +2.7
  (derived) [4; 10].
- SFNNv20 (2026-11-09): stack selection extended by pawn layout (both
  halves, one half, none) and "either side has two or more officers":
  192 raw stacks, factorised in training, rare ones pruned and rerouted;
  lower learning rate for the non-factoriser input weights; STC +2.8, LTC
  +2.1 (derived) [4; 10].
- First-layer weight decay (2026-11-10): STC +4.0, LTC +5.3 (derived)
  [5; prior survey].
- Prefetching the next weight tile during accumulator updates
  (2026-11-14): +1.6% ± 0.2% on Zen 3+; **lost on avx512 and on Zen 1/2
  (−1.85% on a 3950X)**, so compiled only for bmi2 and avxvnni builds;
  STC +2.9 (derived) on those workers [4].

### UNVERIFIED and not published
- The exact factoriser set, loss exponent, stage list and position counts
  of the SF 19 recipe: only in configuration files (not opened).
- The Finny-table gain: test pages behind a bot check [18].
- SFNNv16's net file size (my arithmetic only).
- VVLTC's exact time control.
- Whether weight averaging is in the SF 19 recipe (PR title only).
- An evaluation cache: nothing found; absence not confirmed.

---

## Torch v4 (CCRL #3, 3777)

Private Chess.com engine; no source, no release notes for v4, and its TCEC
questionnaire is confidential [20, TCEC]. What follows is everything
network-related I could confirm in public prose. Nothing below is dated
later than mid-2025, so **none of it is confirmed for v4 specifically**.

**One-line architecture:** not published. The nearest statements, both
about earlier versions: its lead author, replying to "does Torch 2 have a
dimension 3072 network?", wrote that he does not see Torch "as
mirrored-halfka x 2560, but rather as N x 22528" (March 2024, Torch v2)
[24, forum]; a write-up attached to a Stockfish pull request says "Torch is
currently an L1=2560 engine" (July 2025; the document names no author and
is written in the first person by someone running Chess.com's servers)
[14, PR attachment].

### Inputs
- Feature set: mirrored HalfKA-style piece-square inputs, 22,528 per
  perspective, per the March 2024 forum remark (v2) [24, forum]. v4:
  UNVERIFIED (not published).
- King input buckets: 22,528 = 32 x 64 x 11 implies one bucket per
  mirrored king square (my reading of the number, v2). v4: not published.
- Horizontal mirroring: yes for v2 ("mirrored") [24, forum]. Rule (when
  the king crosses the middle): not published.
- Threat or attack inputs: not published.
- Pawn features: not published.
- Other input relationships: not published.
- Factoriser or other training-only input structure: not published.

### Body
- First hidden layer (accumulator) width per perspective: 2560 (v2, March
  2024 [24, forum]; "currently", July 2025 [14, PR attachment]). v4:
  UNVERIFIED.
- Further layers: not published. The same write-up lists, among things
  engines "like Stockfish or Torch" do to their weights, pre-shuffling
  "the first hidden layer ... to utilize sparse matrix multiplication",
  which implies at least one dense hidden layer after the accumulator
  [14, PR attachment].
- Layer stacks: not published.
- Output buckets: not published.
- Skip connections, pairwise multiplication, other structure: the write-up
  lists the "doubled input-layer weights to get an implicit max" trick
  (the pairwise-multiplication optimisation Stockfish adopted in 2024)
  among the weight preprocessing steps [14, PR attachment]; whether Torch
  itself uses pairwise multiplication is not stated outright: UNVERIFIED.

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
- Pairwise multiplication of accumulator halves: see Body; no figure.
- int8 layers or int8 feature-transformer rows: not published.
- Sparse first dense layer: implied by the weight pre-shuffle above
  [14, PR attachment]; no figure.
- Evaluation cache: not published.
- SIMD and VNNI work: weights are pre-shuffled to match the output order
  of packing vector instructions ("an Ethereal trick that has made its way
  everywhere") and every weight and bias array is 64-byte aligned
  [14, PR attachment]; no figure.
- **Memory layout: the "verbatim" network file.** The network is stored
  already preprocessed (decompressed, shuffled, aligned) so it is plain
  constant data that the operating system shares between processes; Torch
  either embeds that file or memory-maps it at start [14, PR attachment].
  Reported effect, total nps of N concurrent single-thread engines,
  verbatim against the default format (my readings off the document's
  graphs, approximate):
  - 2 x Xeon 8452Y (72 cores, 144 threads), 140 engines: about 1.04x for
    a 256-wide accumulator, 1.22x for 1024, 1.65x for 2560, 1.76x for
    3072, 2.05x for 4096;
  - Ryzen 9 7950X, 32 engines: about 1.07x (256), 1.33x (1024), 2.05x
    (2560), 2.2x (3072), 2.67x (4096);
  - with the default format total nps *fell* beyond 50% machine load; the
    document estimates "+~70% more compute" for Stockfish 17.1 on such
    servers.
  The lesson stated: the bigger the net and the more concurrent engines,
  the bigger the loss from unshared weights; gains appear well before the
  machine is full [14, PR attachment]. Stockfish's shared-memory change
  cites these measurements [4, commit text].
- Net size: "100MBs of neural network weights" for "a modern engine, like
  Stockfish or Torch" [14, PR attachment]; no exact figure.
- Light and full nets: the Chess.com browser offers "a lighter and much
  faster option that uses a miniature neural network" or the full version
  [23, vendor]; the browser build "is NOT the same as proper Torch"
  [24, forum].
- Anything else / speed cost of architecture changes / hardware
  sensitivity: only the concurrency sensitivity above.

### Training data
- Size: not published.
- Type: **mixed, v4 unknown.** "Some versions of Torch use Neural Networks
  partially trained on data published by the Leela Chess Zero team"
  (ODbL) [23, vendor]. Second-hand: a tester's slides (2025-09-14) say
  Torch "uses half original and half Leela data" and list v3's data as
  "Orig / Leela" [30, other]; PlentyChess's author mentions "the latest
  Torch version without Lc0 data" and names Torch among engines using
  adversarial games with only its own side's positions [29, TCEC,
  second-hand]. All three second-hand statements are UNVERIFIED.
- Openings, filtering, tablebase use: not published. Its lead author:
  "I don't think there is a lot of FRC data in our nets" (2025-07)
  [26, forum].

### Training recipe (concepts only)
- Trainer: the 2023 announcement lists "pytorch-nnue" among the
  open-source tools supporting development [22, vendor]; the tester's
  slides list the trainer as original [30, other, second-hand]. Which
  trainer v4's net used: UNVERIFIED.
- Loss and target, stages, regularisation: not published.

### Measured gains for network changes
- None published.

### Architecture history
- 2023-07-17: announced; all code stated to be original [22, vendor;
  21, CPW].
- 2023-10-18: in the Chess.com browser with a light and a full net
  [23, vendor; 21, CPW].
- 2024-03-20: Torch v2; mirrored HalfKA-style inputs, 2560 accumulator
  [24, forum].
- 2024-06: strength development paused [25, forum].
- 2025-07: "L1=2560" [14, PR attachment]. 2025-09: v4 "recently sent to
  testers" [30, other, second-hand].

### Since the rated version
- Nothing public.

### UNVERIFIED and not published
- Everything about v4's network: inputs, widths, head, buckets,
  activations, quantisation, file size, data, trainer.
- Whether the 2560 accumulator and 22,528 inputs still hold for v4.
- Lc0 data share and adversarial data (second-hand only).

---

## Dragon by Komodo 3.2 (CCRL #11, 3755)

Commercial, private repository [31, TCEC]. Released 2022-12-19 [41, forum].
(The prior survey's record is for 3.3; facts specific to 3.3 are under
"Since the rated version".)

**One-line architecture:** not published.

### Inputs
- Feature set, king buckets, mirroring, threat inputs, pawn features,
  other relationships, factoriser: **not published.** The vendor says only
  that training a net on Komodo's evaluation required "experimentation
  with architectures" [45, vendor]. One indirect clue about the *first*
  Dragon (2020): its co-author ran a Stockfish-12-era net inside Dragon
  and it played, losing by 244 Elo over 2,200 bullet games to Dragon's own
  net ("it works decently but not properly") [35, forum]. That suggests a
  compatible HalfKP-style input layout in Dragon 1, but the architecture
  is not stated, and Dragon 3 changed the structure: UNVERIFIED.

### Body
- Accumulator width, further layers, layer stacks, output buckets, skip
  connections: not published. Known only as relative changes: Dragon 2.5
  "a larger, 'smarter', better trained net" [37, forum]; Dragon 3 "new net
  structure, new nets" [39, forum]; 3.1 and 3.2 "a newer net" [40; 41,
  forum].
- Indirect size clue: the Chess.com write-up on shared weights says
  "Komodo 3.3 follows" the scaling line of an engine with shared weights
  and that "we could imagine that Komodo 3.3 is an L1=0 engine" [14, PR
  attachment]; that is, even 3.3's net (50% larger than 3.2's) is small
  enough not to load memory bandwidth. No number.

### Activations
- Not published.

### Quantisation
- Not published.

### Inference speed
- Accumulator refresh cache, lazy updates, fused updates, accumulator
  stack, pairwise multiplication, int8, sparse layer, evaluation cache:
  not published ("those are trade secrets" [31, TCEC]).
- SIMD: an AVX2 build is "quite a bit faster and stronger" than the
  standard build; no BMI2 build "as we have not found any meaningful
  benefit to BMI2 beyond the benefit of AVX2" [36, forum]. AVX2 "strongly
  recommended" [45, vendor].
- Memory layout: the net is embedded in the binary [34, forum].
- Speed of architecture changes: Dragon 3.2 gained from "a newer net,
  search improvements, and speedups", about +10 Elo with normal openings
  at CCRL blitz (2'+1"), one to eight threads, and +20 with unbalanced
  openings; not split by cause [41, forum].
- Hardware sensitivity: "we seem to do better with the newer" computers
  [37, forum].
- The inference code was written by Dmitry Pervov of Chess.com, who also
  found "ways to speed it up"; it does not use Stockfish's NNUE code
  [34, forum; 31, TCEC].

### Training data
- Size: "billions of positions" [35, forum; 45, vendor]; no exact count.
- Type: **own engine's games, mixed with games against other engines.**
  "Trained only from Komodo moves in mostly Komodo versus itself games,
  but also some games against other programs (again only using Komodo
  moves)" [31, TCEC]; labels are Komodo evaluations [34, forum]; a
  supervised phase on the handcrafted Komodo evaluation followed by a
  reinforcement-learning phase [45, vendor; 32, CPW].
- Openings, filtering, tablebase use: trained partly on Chess960 games
  [35, forum]; some handicap (odds) positions were included [35, forum].
  Filtering and tablebase use: not published. A third party speculated in
  2020 that the first nets were made with Stockfish's trainer; the team's
  trainer author declined to say [34; 44, forum]: UNVERIFIED.

### Training recipe (concepts only)
- Trainer: "Dietrich Kappe wrote original code for NNUE training"
  [31, TCEC]. Details not published.
- Loss, stages, regularisation: not published.
- A status note from the co-author, March 2023: "Progress with NN training
  came to a halt, I won't pretend to know why", after the release of 3.2
  [43, forum].

### Measured gains for network changes
- Dragon 1 against Komodo 14.1 (first net): about +190 Elo on one thread,
  +160 on four, at 2'+1" [35, forum].
- Dragon 2.5 (larger net plus search): +50 to +72 over Dragon 2 [37].
- Dragon 3 (new net structure, new nets, search): +17 over 2.6.1 on one
  thread, 30,000 games, about double with unbalanced openings [39].
- Dragon 3.1 (newer net, search): about +10 [40].
- Dragon 3.2 (newer net, search, speedups): about +10 normal openings,
  +20 unbalanced [41].
- None of these isolates the net.

### Architecture history
- 2020-11-10 Dragon 1: first NNUE net, embedded [35].
- 2021-09-24 Dragon 2.5: larger net [37]. 2021-12-20 Dragon 2.6: newer
  nets [38].
- 2022-04-26 Dragon 3: new net structure [39]. 2022-07-30 Dragon 3.1
  [40]. 2022-12-19 Dragon 3.2 [41].

### Since the rated version
- Dragon 3.3 (2023-10-04): the net was upgraded "to a 50% larger size
  with increased strength, still trained on Dragon moves"; +8 Elo over
  3.2 with normal openings (40,000 games at 1'+0.6" and 11,400 games at
  5'+2"), +12 (bullet) to +15 (blitz) with unbalanced openings, "the
  increased gains with longer time controls presumably due to the larger
  net" [42, forum; 45, vendor; prior survey].

### UNVERIFIED and not published
- The whole architecture, activations, quantisation, every inference
  technique, the trainer's recipe, exact data size and filters.
- Dragon 1's input layout (inferred from one experiment only).

---

## Ethereal 14.25 (CCRL #28, 3722)

Released 2023-10-21 [53, forum]. Code GPL-3.0; networks all rights reserved
[48, TCEC; 49, README]. The 14.25 changelog ends with SPSA tuning; its last
network change is entry 14.24, "new default network, with 100 epochs of
reduced LR" [53, forum], which is the net of 2023-09-04 [51, commit text].

**One-line architecture:** as the author writes it in commit messages:
mirrored HalfKP, `[2x768]->8->32->1` (the Fischer-random net's commit
spells the shape out; the standard net's says the input layer became
`[2x768]` on the `[2x1024]->8x32x1 mirrored halfkp` architecture)
[51, commit text].

### Inputs
- Feature set: **HalfKP**: (own king square, piece square, piece kind and
  colour, kings excluded): 40,960 inputs per perspective in 13.00
  [55, CPW quoting the author]. Since 2021-08 mirrored, which halves the
  first layer's weights [51, commit text] (so 20,480, my arithmetic).
- King input buckets: none beyond HalfKP itself, i.e. one weight set per
  own-king square (32 after mirroring). No coarser grouping is mentioned.
- Horizontal mirroring: files a-d are mirrored onto e-h (by the king's
  file, per perspective); "this speeds up training, but not gameplay";
  +8.19 ± 1.97 STC, +4.21 ± 1.60 LTC together with 8-bit quantisation of
  the first dense layer [51, commit text]. The author calls himself "a
  simultaneous inventor of the mirrored format" [48, TCEC].
- Threat or attack inputs: none mentioned.
- Pawn features: none mentioned.
- Other input relationships: none mentioned.
- Factoriser: 13.00 trained with 43,850 inputs, i.e. 2,890 extra factor
  inputs on top of 40,960 [55, CPW]. A king-distance factoriser was
  removed in 2022-06 as "not sound theoretically" once the king index is
  mirrored: +6.22 ± 4.15 STC, +8.46 ± 5.69 LTC [51, commit text]. Which
  factors remain: not published.

### Body
- Accumulator width per perspective: **768** [51, commit text; 53,
  changelog 14.12].
- Further layers: 2 x 768 -> 8 -> 32 -> 1 [51, commit text].
- Layer stacks: none mentioned.
- Output buckets: none mentioned.
- Skip connections, pairwise multiplication, other: none mentioned.

### Activations
- After the accumulator: a ReLU-type activation (a later commit speaks of
  "the HalfKP relu") [51, commit text]; clipped or not: not stated.
- In the head: not stated.

### Quantisation
- Integer types per layer: in 13.00, int16 first-layer weights and int16
  accumulator, then int32 converted to float, and float for the later
  layers, to avoid packing down and keep precision [55, CPW quoting the
  author]. Since 2021-08 the first dense layer's weights are 8-bit, made
  possible by "a new initialization scheme" [51, commit text]. Whether the
  last layers are still float in 14.25: not restated.
- Rounding care: since 2022-02 the first dense layer's weights are clamped
  during training to the 8-bit range, "no elo has been demonstrated"
  [51, commit text]. No quantisation-aware training mentioned.

### Inference speed
- **Accumulator refresh cache (Finny tables)**: 14.11, 2023-05:
  **+8.60 ± 4.67 Elo STC** [51, commit text; prior survey].
- **Lazy or deferred updates**: accumulators are validated per colour and
  rebuilt by walking back; splitting the "accurate" flag by colour avoids
  needless refreshes: **+7.03 ± 4.13 STC**; a faster check of whether an
  update is possible: "10k-12k nps", untested in games [51, commit text].
- Fused updates: 2021-06: the first removal is folded into the copy from
  the previous accumulator; whole patch "approx 1.5%" speed, SPRT
  inconclusive (+0.55 ± 1.32) [51, commit text].
- Accumulator stack / copy avoidance: no accumulator copy after a null
  move: **+2.30 ± 1.85 STC** [51, commit text].
- Pairwise multiplication: not used (not mentioned).
- int8 layers: 8-bit first dense layer (see Quantisation) [51].
- Sparse first dense layer: not mentioned.
- **Evaluation cache**: 12.48 (2020, handcrafted eval) added a 512 KB
  cache per thread: +11.86 ± 6.27 at 12+0.12, +4.04 ± 2.89 LTC. Removed
  2022-06: once static evals are stored in the TT early in quiescence the
  cache's hit rate "plummets by orders of magnitude"; removal
  +0.85 ± 1.68 STC, +2.28 ± 2.16 on 8 threads [51, commit text; 50,
  release notes].
- **SIMD**:
  - register tiling of accumulator updates (14.00, contributed by
    Berserk's author): **+9.95 ± 5.09 STC** for partial refreshes,
    +7.12 ± 4.16 for the version covering full refreshes too (separate
    tests, not additive) [51, commit text; prior survey];
  - four byte-multiply-add results accumulated before each widening step
    in the dense layer (13.87): **+6.90 ± 4.61 STC**, "big speed up"; it
    allows saturation in theory, not seen to depth 30 on the benchmark
    [51, commit text; 50, release notes];
  - SSSE3 is the minimum; AVX2 fastest, then AVX [50, release notes].
- Memory layout and prefetching: prefetch moved to right after the move
  is made: **+5.40 ± 3.52 STC** [51, commit text]. Weight pre-shuffle for
  packing instructions is credited to Ethereal by the Chess.com write-up
  [14, PR attachment].
- Anything else: Clang with PGO became the default build (13.89, no
  figure) [50, release notes].
- **Speed cost or gain of architecture changes** (each a new net on the
  same data unless said):
  - 2 x 256 -> 2 x 384: +9.75 ± 6.23 STC, +19.34 ± 9.24 LTC [51];
  - 2 x 384 -> 2 x 512: **−2.91 ± 4.91 STC (failed)**, +5.52 ± 4.20 and
    +5.89 ± 2.39 LTC [51];
  - head 16 -> 16 changed to 8 -> 32: +10.21 ± 5.20 STC, +4.66 ± 3.19
    LTC, +5.75 ± 3.64 at 240+2.4 [51];
  - 2 x 512 -> 2 x 1024: **−9.37 ± 5.59 STC (failed)**, +3.92 ± 2.85 LTC
    [51]; with twice the data: +5.91 STC, +2.77 LTC more [51];
  - 2 x 1024 -> 2 x 768: +14.60 ± 6.33 STC, +9.45 ± 4.89 LTC [51]: the
    narrower net won at both controls (the commit names the same combined
    data as the 2 x 1024 net; the release changelog says "with additional
    data" [53], so the comparison may not be like for like);
  - [2x192]x32x32 -> "faster but larger" [2x256]x16x16 (2022-02, with new
    data): +10.65 ± 1.94 STC, +6.59 ± 3.71 LTC [51].
- Hardware sensitivity: none reported.

### Training data
- Size of the rated net's data: **11,450,167,587 training positions**
  (plus 46 M held out): 8.35 B self-play (set S44, 100 M games) and
  3.10 B from adversarial sets S51-S56 (about 84 M games) [51, commit
  text; sums are the commit's].
- Type: **mixed: own self-play plus games against Stockfish, own side
  only.** Self-play: 100 M games at **40,000 nodes** per move; labels are
  Ethereal's own search scores [51]. Adversarial: Ethereal against
  Stockfish with a node handicap (40k against 14k) "to approach 50%
  results"; only positions with Ethereal to move and Ethereal's
  evaluations are kept, no Stockfish evaluation [51; 48, TCEC].
- Openings, filtering, tablebase use: openings from 10 random moves,
  discarding those a depth-10 search scores beyond a bound; games
  adjudicated by score and by tablebases, no draw adjudication; a position
  is kept only if not in check and the next game move is not a capture or
  promotion [51, commit text].

### Training recipe (concepts only)
- Trainer: his own, written in C, CPU-only, heavily threaded (NNTrainer);
  a modified Adam for very sparse inputs [55, CPW; 48, TCEC].
- Loss and target: search score mapped through a sigmoid whose slope was
  fitted to the data's score-to-result relation [51, commit text]; the
  blend with the game result for the rated net is not stated.
- Stages and schedule: one long stage at the base learning rate, then a
  short stage at a much lower rate; making that drop deeper was part of
  each 13.78-13.82 net [50, release notes]. The rated net adds 100 more
  low-rate epochs: +2.61 ± 3.35 STC, +2.18 ± 1.75 LTC; "historically this
  has not been very fruitful" [51, commit text]. Each data generation
  uses the newest net; node budget raised 5k -> 20k -> 40k [50].
- Regularisation, optimiser, anything unusual: none stated beyond the
  weight clamp. The author later could not train a new net from scratch
  that matched the incumbent; "the leading theory right now is dead
  neurons" [51, commit text].

### Measured gains for network changes
- Label budget 5k nodes (13.78): +9.92 STC / +6.01 LTC; 20k (13.79):
  +9.82 / +19.27; 40k (13.82): +2.83 / +12.67 [51, commit text].
- Regenerating data with the newer net (13.86): +5.11 / +7.91 [51].
- First adversarial data (14.17: 8.4 B self-play + 1 B adversarial
  positions, against the previous net trained on "2x as many" self-play
  positions): +12.79 ± 5.90 / +12.95 ± 5.79; next rounds +2.44 / +5.55
  and +5.46 / +5.56 [51].
- Release: 14.25 over 14.00, +61.49 ± 3.74 at 60+0.6 with unbalanced
  openings [53, forum; prior survey].

### Architecture history
- 2020-09: a small pawn-king net (224 inputs, 32 hidden) added to the
  handcrafted evaluation: +25.81 / +23.39 [51].
- 2021-06, 13.00: HalfKP `[2x256]x32x32x1`, 2 to 4 B positions per net
  [51; 55]. 2021-08: mirrored; 8-bit first dense layer; a 2x196 variant
  (as written) [51].
- 2022-02: `[2x256]x16x16` [51]. 2022-08: 2x384, then 2x512 [50; 51].
- 2023-02, 14.00: `[2x512]->16->16->1`, tiling [50; 51]. 14.01: 8 -> 32
  head. 14.02: 2x1024. 14.11: Finny tables. 14.12: 2x768 [53].

### Since the rated version
- **Result-only fine-tune (2024-04-19)**: the best net was un-quantised,
  loaded back into the trainer (losing the factoriser split and optimiser
  state) and trained further on the same data with the game result as the
  only target: **+42.67 ± 11.49 STC, +35.63 ± 8.10 LTC** [51; prior
  survey].
- Two more adversarial sets added: +3.54 / +3.91. Then, because the
  target is the result only, Stockfish-to-move positions were added too
  (16.57 B positions, adversarial share from about 33% to 50%):
  +3.91 ± 3.29 / +5.30 ± 4.04 [51].
- Activation merged into the first dense layer's loop (2024-05):
  **+1.626% nps, +7.41 ± 4.86 STC** [51].
- Fischer-random net given the same result-only fine-tune: +16.52 ± 1.93
  (FRC) [51].

### UNVERIFIED and not published
- Net file size; activation details; the integer type of the last layers
  in 14.25; the result/score blend of the rated net; remaining factoriser
  inputs; whether an accumulator copy is avoided on ordinary moves.
- NNTrainer's README would not load (404; the repository appears
  private) [56].

---

## Sources

Every page opened on 2026-11-14, failed fetches included. "SF" Stockfish,
"T" Torch, "D" Dragon, "E" Ethereal.

| # | URL | What it is | Source type | Used for |
|---|---|---|---|---|
| 1 | https://raw.githubusercontent.com/official-stockfish/nnue-pytorch/master/docs/nnue_architecture_history.md | Stockfish network architecture history, SFNNv1-v20 | docs (prose) | SF |
| 2 | https://raw.githubusercontent.com/official-stockfish/nnue-pytorch/master/docs/nnue.md | The NNUE document; code blocks stripped by script before reading | docs (prose) | SF |
| 3 | GitHub API `repos/official-stockfish/Stockfish/releases` (same text as https://github.com/official-stockfish/Stockfish/releases) | Release notes, Stockfish 12 to 19 | release notes | SF |
| 4 | GitHub API commit list of official-stockfish/Stockfish, limited to commits touching the network folder, 4 pages (2020-08-05 to 2026-11-14); message text only | Commit messages | commit text | SF, T (shared-memory commit) |
| 5 | GitHub API commit list of official-stockfish/Stockfish, limited to net-update commits (by the evaluation header's path), 2 pages; message text only | Commit messages of net updates | commit text | SF |
| 6 | GitHub API `repos/official-stockfish/nnue-pytorch/pulls/{430,477,480,502,511,563,570}`, title and body | Trainer pull requests | PR text | SF |
| 7 | GitHub API `repos/vondele/nettest/pulls/{329,346,359,369,395,426,448,462,488}`, title and body (most bodies empty) | Recipe pull requests | PR text | SF |
| 8 | https://raw.githubusercontent.com/official-stockfish/nnue-pytorch/master/README.md | Trainer README | README | SF |
| 9 | https://raw.githubusercontent.com/vondele/nettest/main/README.md | Recipe-runner README | README | SF |
| 10 | https://raw.githubusercontent.com/official-stockfish/nnue-pytorch/master/docs/img/SFNNv16_architecture_detailed_v2.svg and the same for v5, v9, v10, v11, v12, v13, v14, v14.1, v15, v17, v18, v19, v20 | Architecture diagrams in the trainer's docs; text labels only, extracted by script | docs diagram | SF |
| 11 | https://wiki.chessdom.org/Stockfish_questionnaire_20251019 | TCEC questionnaire | TCEC | SF |
| 12 | https://github.com/user-attachments/files/23478634/Stockfish.threat.inputs.PR.summary.pdf | "Stockfish threat inputs PR summary", attached to Stockfish PR #6411 | PR attachment (prose) | SF |
| 13 | https://github.com/user-attachments/files/23478441/NewInputs.pdf | "Monty Inputs V2" slides, attached to the same PR (an earlier input scheme of another engine; background only) | PR attachment (prose) | SF |
| 14 | https://github.com/user-attachments/files/21386224/verbatim.pdf | "Memory Optimizations for High Concurrency Machines", cited by Stockfish's shared-memory commit; no author named | PR attachment (prose) | T, D, SF, E |
| 15 | https://raw.githubusercontent.com/official-stockfish/nnue-pytorch/master/docs/training.md | Trainer docs: network training | docs (prose) | SF |
| 16 | https://github.com/official-stockfish/nnue-pytorch/wiki and its pages Training-datasets, Training-examples, Basic-training-procedure-(training-workflows) | Trainer wiki | wiki | SF |
| 17 | GitHub API `repos/official-stockfish/Stockfish/issues/{6982,7215,7043,6890,5183,6796}/comments` | Conversation comments on six pull requests | PR comments | SF |
| 18 | https://tests.stockfishchess.org/tests/view/6a85df4c5b1b38ebda864ccd, .../6a85df595b1b38ebda864ccf, and https://tests.stockfishchess.org/api/get_elo/6a85df4c5b1b38ebda864ccd | fishtest release tests. **Failed**: bot verification page; the API returned an empty object | fishtest | none |
| 19 | https://computerchess.org.uk/404/cgi/engine_details.cgi (four engines) and the coordinator's saved list | CCRL Blitz engine pages, list of 2026-11-14 | CCRL | all (ranks, Elo) |
| 20 | https://wiki.chessdom.org/Torch_questionnaire_20250620 | TCEC questionnaire, confidential | TCEC | T |
| 21 | https://www.chessprogramming.org/Torch | CPW page | CPW | T |
| 22 | https://www.chess.com/news/view/torch-chess-engine | "Announcing Torch" (2023-07-17) | vendor | T |
| 23 | https://www.chess.com/news/view/torch-engine-available-on-chesscom | Torch in the Chess.com browser | vendor | T |
| 24 | https://talkchess.com/viewtopic.php?t=83499 (3 pages) | "Torch 2 is here" | forum | T |
| 25 | https://talkchess.com/viewtopic.php?t=83917 (4 pages), also reached as ?p=965569 | "End of the Torch Experiement" | forum | T |
| 26 | https://talkchess.com/viewtopic.php?p=981490 | "Torch #1 in FRC list" | forum | T |
| 27 | https://talkchess.com/viewtopic.php?t=82734 and ?t=82317 | "Torch now on Chess.com!", "Mystery BEATS Dragon!" (nothing used) | forum | T |
| 28 | https://www.chessdom.com/torch-enters-tcec-season-29/ | chessdom announcement (nothing technical) | TCEC / chessdom | T |
| 29 | https://wiki.chessdom.org/Plentychess_questionnaire_20251012 and https://wiki.chessdom.org/Tarnished_questionnaire_20251016 | Other engines' questionnaires that mention Torch | TCEC (second-hand) | T |
| 30 | https://forum.killerchesstraining.com/uploads/short-url/gnbboWwbS2BCOVY5ThbZxrlct1M.pdf | John Hartmann, "Beyond Stockfish and Leela", slides dated 2025-09-14 (a tester, not the engine's team) | other (second-hand) | T |
| 31 | https://wiki.chessdom.org/KomodoDragon_questionnaire_20251108 | TCEC questionnaire | TCEC | D |
| 32 | https://www.chessprogramming.org/Dragon_by_Komodo_Chess | CPW page | CPW | D |
| 33 | https://www.chessprogramming.org/Komodo | CPW page | CPW | D |
| 34 | https://talkchess.com/viewtopic.php?t=75651 (5 pages; also ?p=870317) | "Komodo 14.1 Release and Dragon Announcement" | forum | D |
| 35 | https://talkchess.com/viewtopic.php?t=75748 (page 1, page 7; page 6 via ?p=872672) | "Dragon by Komodo Chess" | forum | D |
| 36 | https://talkchess.com/viewtopic.php?t=77244 | "Komodo Dragon 2 released" | forum | D |
| 37 | https://talkchess.com/viewtopic.php?t=78244 | "Komodo Dragon 2.5 released" | forum | D |
| 38 | https://talkchess.com/viewtopic.php?t=78942 | "Komodo Dragon 2.6 released" | forum | D |
| 39 | https://talkchess.com/viewtopic.php?t=79766 and ?p=925166 | "Komodo Dragon 3 Released" | forum | D |
| 40 | https://talkchess.com/viewtopic.php?p=931184 | "Dragon 3.1 Released" | forum | D |
| 41 | https://talkchess.com/viewtopic.php?t=81166 (5 pages; also ?p=939866; ?p=940086 gave 404) | "Dragon 3.2 Released at KomodoChess.com" | forum | D |
| 42 | https://talkchess.com/viewtopic.php?t=82669 (also ?p=953167) | "Dragon 3.3 Released" | forum | D |
| 43 | https://talkchess.com/viewtopic.php?t=81715 | "KomodoChess and chess.com" | forum | D |
| 44 | https://talkchess.com/viewtopic.php?t=75890 | "Speculations about NNUE development" (third-party speculation) | forum (second-hand) | D |
| 45 | Wayback Machine copies of komodochess.com: dragon-3.3.htm (20231025), dragon-2.5.htm (20230317), dragon-2.htm (20230321) read. **Failed (HTTP 429)**: dragon-3.2.htm, dragon-3.1.htm, dragon-3.htm, dragon-2.6.htm, dragon.htm, home page | Vendor product pages | vendor | D |
| 46 | https://www.chess.com/news/view/komodo-releases-powerful-new-dragon-chess-engine | Chess.com article (2020-11) | vendor | D |
| 47 | https://komodochess.com/dragon-3.2.htm | **Failed**: expired TLS certificate | vendor | none |
| 48 | https://wiki.chessdom.org/Ethereal_questionnaire_20251109 | TCEC questionnaire | TCEC | E |
| 49 | https://raw.githubusercontent.com/AndyGrant/Ethereal/master/README.md | README | README | E |
| 50 | GitHub API `repos/AndyGrant/Ethereal/releases` | Release notes and changelogs to 14.00 | release notes | E |
| 51 | GitHub API commit list of AndyGrant/Ethereal, 2 pages (2020-08 to 2024-06); message text only | Commit messages | commit text | E |
| 52 | http://chess.grantnet.us/Ethereal/ | Author's product page for 14.25 | vendor | E |
| 53 | https://talkchess.com/viewtopic.php?p=953753 | "Commercial Release of Ethereal 14.25" with changelog | forum | E |
| 54 | https://talkchess.com/viewtopic.php?p=942809 | "Commercial Release of Ethereal 14.00" | forum | E |
| 55 | https://www.chessprogramming.org/Ethereal | CPW page (quotes the author on 13.00's network) | CPW | E |
| 56 | https://raw.githubusercontent.com/AndyGrant/NNTrainer/master/README.md | **Failed**: 404 | README | none |
| 57 | https://www.chessprogramming.org/Stockfish_NNUE | CPW page, fetched, not used | CPW | none |
| 58 | Web searches (3): "Dragon 3.2" Komodo released; Torch v4 chess engine; Torch 4 testers data. Used only to find pages then opened (41, 30) | search | D, T |
| 59 | https://wiki.chessdom.org/Engines_by_TCEC_Questionnaire | Index of questionnaires | TCEC | all |
| 60 | `docs/research/engine-survey-2026-11/` (engines.md, sources.md, comparison.md, provenance.md), read-only | The prior survey | prior survey | all |

**Credits.**
- Stockfish: "the Stockfish authors" (community project; maintainers
  named in its questionnaire: Disservin and vondele). Code GPL; networks
  CC0 [11]. Trainer nnue-pytorch: about 20 contributors [11]; recipes:
  vondele/nettest. Commit authors cited above include Tomasz Sobczyk,
  Linmiao Xu, sscg13, Shawn Xu, Tony Wang, anematode (Timothy Herchen),
  mstembera, Carlos Esparza, gab8192, AndrovT, cj5716, Viren6, Dubslow,
  Joost VandeVondele, Yoshie2000 and others, as the commit messages name
  them.
- Torch: Chess.com; team as its announcement names it: Andrew Grant, Finn
  Eggers, Kim Kåhre, Jay Honnold, Michael Whiteley, Dietrich Kappe;
  advisers Mark Lefler and Larry Kaufman [22]. Proprietary.
- Dragon by Komodo: Mark Lefler and Larry Kaufman (originally Don
  Dailey); NNUE inference Dmitry Pervov, training Dietrich Kappe [31; 34].
  Proprietary; now owned by Chess.com [43].
- Ethereal: Andrew Grant, with Laldon and Alayan listed as co-authors
  [48]. Code GPL-3.0; networks all rights reserved [48].
- Chess Programming Wiki and TCEC wiki text: CC BY-SA 3.0 (TCEC wiki
  footer [11]).

## Clean-room statement

I opened no engine or trainer source file, header, build file, training
script, trainer configuration file, diff, patch, "Files changed" tab,
blame view, code search result or network file. I cloned no repository and
downloaded no release archive, binary or network file. All facts above
come from pages opened today; nothing is from memory.

Things that came close, in full:

1. **Commit messages and PR text embed fragments.** Several Stockfish
   commit messages and PR comments contain short code fragments (compiler
   warnings, a few C++ and Python lines) and trainer command lines with
   hyperparameter values; Ethereal's contain game-runner command lines.
   They were on screen while I read the messages. I skipped them and
   transcribed none; no learning rate, result-blend weight, clamp bound,
   sigmoid coefficient or quantisation scale is recorded here.
2. **Commit lists were filtered by path.** Two API queries limited
   Stockfish's commit list to commits touching the network folder and the
   evaluation header. Only the query used the path; the responses were
   commit metadata, reduced to hash, date, author and message. That
   endpoint returns no file content or diff.
3. **Bot review comments.** Two PR comment threads (Stockfish #6890,
   #6796) contain an automated reviewer's summary of the code change,
   naming code identifiers and one source file name. Not used.
4. **nnue.md has code blocks.** I removed all fenced and indented code
   blocks with a script before reading (2,017 lines removed unseen) and
   read only the prose.
5. **Architecture diagrams.** I read the text labels of the trainer's
   documentation diagrams (14 SVG files) with a script. The labels include
   quantisation scale values and per-layer formulas; I recorded only
   widths, counts, types and selectors.
6. **A screenshot of search code.** The third-party slide deck (source 30)
   shows, on its second slide, a screenshot of Stockfish search code. I
   did not read or use it, and deleted the file.
7. **GitHub API use.** 32 calls (plus 4 rate-limit checks), all to
   release, commit-list, pull-request and issue-comment endpoints; quota
   stayed above 4,500.

Files deleted, all created by me, each by exact name, in
`agent-A\pages\`: `sf_nnue_commits_p1.txt` to `_p4.txt`,
`sf_netupdate_commits_p1.txt`, `sf_netupdate_commits_p2.txt`,
`ethereal_commits_p1.txt`, `ethereal_commits_p2.txt`,
`ethereal_net_commits.txt`, `sf_pr_comments.txt`,
`sf_pr_comments_prose.txt`, `sf_nnue_md_raw.md`,
`nnue_pytorch_readme_raw.md`, `nettest_readme_raw.md`,
`kct_presentation.pdf`, and the HTML copies of three trainer wiki pages
that held command blocks (`npw_Training-datasets.html`,
`npw_Training-examples.html`,
`npw_Basic-training-procedure-_training-workflows_.html`; their text
copies remain); and the three drafts of this report in `agent-A\`
(`part1.md`, `part2.md`, `part3.md`). Code-free copies of the commit dumps
(`*.clean.txt`) remain.

Check run after deleting: a search of every remaining file under
`agent-A\pages\` for C++ and intrinsic markers found none (the same search
over `agent-A\scripts\` matches only my own filter script, which lists
those markers as its search pattern), and a search of
the folder found no `.git` directory, no source file, no archive and no
network file. What remains: `report.md`, saved copies of prose pages
(HTML and text), the 14 diagram SVGs, three prose PDFs (sources 12-14) and
six small scripts of my own in `agent-A\scripts\`.
