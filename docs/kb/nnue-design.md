# NNUE design: concepts, costs and evidence (Phase 4, step 1)

Created 2026-10-28 for step 1 of the Phase 4 multi-agent plan (DESIGN.md on
main, section 5). The three designer agents of step 2 read this file before
they propose architectures. It describes **ideas only**.

**How this file was written (clean room).**
- No chess engine's source code was opened, and nothing from nnue-pytorch's
  code either. The sources are documentation, papers, the Chess Programming
  Wiki, release notes, pull-request *descriptions* (fetched as text through
  the GitHub API, which returns no diff), blog posts and bullet's docs.
  Each one is listed in the Sources table at the end.
- Some permitted pages include illustrative code: the CPW NNUE page, the
  nnue-pytorch `nnue.md` document, and two blog posts by Viridithas's author
  that quote that engine's Rust code. From those pages only the prose was
  used. Nothing here is a code line, and no identifier lists were taken.
- **No exact constants from any engine** appear here: no layer widths,
  bucket maps, bucket counts, quantization factors, eval scales, learning
  rates or king-bucket layouts. Where a source gives a number tied to an
  engine, this file gives the idea, a range, or the reasoning.
- Elo figures are self-play results quoted from the cited page, as the
  measured value with its error bar. They are evidence, not constants.
  "STC" and "LTC" mean each project's short and long test time controls;
  "fixed nodes" means a fixed node budget per move.
- Anything not confirmed on an opened primary source is marked
  **UNVERIFIED**, with the reason.

**Tags.** Every technique here is **REFERENCE ONLY**: study the idea, write
Fork's own code. bullet is **USE** (MIT, a tool). Data labelled by any
other engine is **OFF-LIMITS** ([data-policy.md](data-policy.md)).
Everything was verified on **2026-10-28** unless a line says otherwise.

**Phase and component.** All of this is Phase 4: the NNUE inference code,
the network file format, the datagen tool, the training setup (bullet
configuration on Kaggle), and the Phase 4 re-validation of the search
margins that depend on eval (CLAUDE.md, phase-end item 8).

---

## 0. Key findings

1. **Threat inputs are now mainstream (since late 2025), and their gain
   grows with time control.** Two published PR results show large gains at
   fixed nodes, roughly neutral at STC, and positive at LTC and with more
   threads (§1.6). They cost speed and memory bandwidth, so they are a
   later-generation option, not a first net.
2. **Simple first, measured steps.** bullet's own docs warn against
   starting with large feature sets or Stockfish-style architectures before
   having the data for them. They advise widening the single hidden layer
   before adding layers (§3.1).
3. **Own-data precedent.** PlentyChess moved from Lc0 data to fully self-
   generated data on a few billion positions. Its author estimated the first
   own-data net about 15 Elo weaker than the Lc0 one, and architecture work
   more than made up for it. Halogen bootstrapped a net from random weights
   (TDLeaf, then supervised self-play) and beat its previous main net
   (§6.9). Both support strategy A+.
4. **Eval scale matters to search.** The WDL/score blend weight changes how
   large the net's outputs are. A search tuned to one eval scale can lose
   Elo on a net with a different scale, and rescaling at inference
   recovered it in one published test (§6.3). Fork's Phase 3 margins were
   tuned on the HCE scale.
5. **Activations:** squared clipped ReLU gives a clear published gain over
   clipped ReLU (§4). Smooth gated activations (Swish, SwiGLU) in the small
   later layers are a 2026 result with positive SPRTs (§4.5).
6. **Quantization-aware training** was used for Stockfish 19's nets. bullet
   has a merged PR titled "Add QAT operation" (October 2025), but its docs
   do not describe it, so how it works is **UNVERIFIED** (§5.6).
7. **Parity.** bullet's docs specify its saved file layout: little-endian,
   column-major, a quantized file padded to 64 bytes, and a separate raw
   float file. Its default quantization **truncates** unless rounding is
   requested. bullet has a merged PR titled "Eval FENs with WDL output", but
   no docs, so whether it can evaluate a FEN with a float model is
   **UNVERIFIED**. nnue-pytorch documents a trainer-against-engine
   cross-check script that runs in its CI (§8).
8. **arXiv 2412.17948 resolved:** its quiet-position filter drops positions
   in check and positions whose static eval differs too much from a
   quiescence search score or from a search score. It also targets a
   balanced eval distribution. It is a **Xiangqi** study with no SPRT or
   ablation, so the evidence is weak (§6.5).

---

## 1. Input feature sets

### 1.1 Plain 768 piece-square inputs
- **What.** One binary input per (piece type, colour, square): 6 × 2 × 64 =
  768. The board is seen from a "perspective": for the second accumulator
  it is flipped vertically and colours are swapped, so "own pieces" and
  "enemy pieces" mean the same thing for both sides. Both perspectives
  share the same weights.
- **Why it helps.** It is the smallest sensible set. At most 32 inputs are
  active, and a move changes 2 to 4 of them (quiet move or promotion 2,
  capture 3, castling 4). Every weight sees a lot of data, so it trains
  well on modest datasets.
- **Cost.** Cheapest updates and refreshes. The weight table is small
  (768 rows × hidden width), so it mostly stays in cache.
- **Interactions.** Perspective inputs encode the side to move naturally
  (§2.1). Output buckets (§3.3) and a wider hidden layer are the usual next
  steps.
- **Pitfalls.** Flip-versus-rotate confusion for the second perspective.
  Chess is mirror-symmetric top to bottom, so flip. The original shogi-
  derived code rotated, which nnue-pytorch calls arguably wrong for chess,
  though it worked.
- **Evidence.** bullet's docs recommend starting here. They say large king-
  relative sets need more data than a newcomer has, perhaps ever, and that
  custom bucket schemes generally do better with less data. The CPW basic
  NNUE description uses this set.
- Sources: bullet docs `1-basics.md`; CPW NNUE; nnue-pytorch `nnue.md`
  ("A simple input feature set", "Which set of weights to use").

### 1.2 King-relative sets (HalfKP without king features; HalfKA with them)
- **What.** Each input is (own king square, piece square, piece type,
  piece colour). HalfKP leaves kings out as pieces. HalfKA includes them.
  It is the 768-style set copied once for every square of the
  perspective's own king.
- **Why it helps.** The net can learn piece placement *relative to the
  king* (king safety, pawn shelters, endgame king activity) inside the
  first layer, where it costs nothing at eval time.
- **Cost.**
  - Very large weight table (tens of thousands of input rows).
  - Every own-king move changes all of that perspective's features, so it
    forces a refresh (§2.3).
  - Training is slower to converge, because each weight sees only the
    positions with the king on one square.
- **Interactions.** It is the motivation for factorizers (§1.5), mirroring
  (§1.4) and refresh caches (§2.4). HalfKP has no king-position input at
  all, so a virtual "king" factor is sometimes added during training.
- **Pitfalls.** Data starvation for rare king squares. Big net files.
- **Evidence.** nnue-pytorch calls HalfKP the classic set that later ones
  build on. bullet's docs warn that HalfKA/HalfKP need more data than a
  beginner has. No isolated SPRT for HalfKP against 768 was found in the
  opened sources (**UNVERIFIED** as a number).
- Sources: nnue-pytorch `nnue.md` (HalfKP, HalfKAv2); bullet `1-basics.md`.

### 1.3 Merged-king variant (HalfKAv2)
- **What.** In HalfKA, once the own king's square is fixed, the own-king
  piece uses exactly one of its 64 squares, and the enemy king can never
  share it. So the two king "piece slots" can be merged into one, which
  leaves 11 piece slots instead of 12. The table is about 8% smaller with
  no loss of information.
- **Why it helps.** Smaller nets for the same information.
- **Pitfalls.** When factorizers are used, the merge has to be undone for
  the virtual feature set. Otherwise the two kings get mixed up across
  buckets.
- **Related.** Viridithas 16.0.0's release notes list "take advantage of
  bucket layout to merge king planes". The notes do not explain it
  (**UNVERIFIED** details).
- Sources: nnue-pytorch `nnue.md` (HalfKAv2); Viridithas v16.0.0 release.

### 1.4 Horizontal mirroring
- **What.** For each perspective, if the own king is on one half of the
  board (files a-d, say), mirror the whole board left to right so the king
  always sits on the other half. Only half the king squares (or king
  buckets) need weights.
- **Why it helps.** It halves the king-dependent weight set. CPW says it
  makes training data "between one and two times" more effective,
  depending on the architecture.
- **Cost.** When the king crosses the centre line, every input of that
  perspective changes, so it forces a refresh. The two perspectives can be
  mirrored independently.
- **Interactions.** Works with king buckets (the bucket map only covers
  half the board). Threat inputs can also be mirrored, and then they only
  need a refresh when the king crosses the centre (§1.6).
- **Pitfalls.** Chess is not truly left-right symmetric: castling rights
  differ by side. nnue-pytorch reports the strength difference as "hardly
  measurable" while the feature transformer halves. Getting the mirror test
  wrong for one perspective is a classic bug.
- **Evidence.**
  - nnue-pytorch: Stockfish has used it since August 2021 to keep large
    first layers practical.
  - Berserk 9 (2022) moved to a mirrored, bucketed system; its notes give
    no isolated number.
  - Alexandria 7.1 notes say mirroring improved strength without growing
    the net; no number given.
- Sources: CPW NNUE (Horizontal Mirroring); nnue-pytorch `nnue.md`
  (HalfKAv2_hm); Berserk 9 and Alexandria v7.1.0 releases.

### 1.5 King input buckets, and the data-versus-accuracy trade
- **What.** Instead of one weight set per king square (HalfKA), group the
  king squares into a few regions ("buckets"). Each bucket has its own
  first-layer weights, and the perspective's own king picks the bucket.
  It is a mixture of experts with a hand-made gate.
- **Why it helps.** Each expert specializes. A bucket used only when the
  king is on its home rank can concentrate on attacks against a castled
  king, for example. Viridithas's author makes this point.
- **The trade-off.** With B buckets, each weight sees roughly 1/B of the
  data (less for rarely visited regions), so more buckets need more data,
  or a factorizer, to train well. Fewer, larger buckets train faster but
  specialize less. Finer buckets where the king usually lives, and coarse
  ones elsewhere, is the common design reasoning; the exact layouts are
  engine choices and are not recorded here. Viridithas's author notes that
  combining input experts with output experts does not multiply the data
  need, because every expert must pass through the same activation
  bottleneck, which regularizes them.
- **Factorizer.** A training-only "virtual" bucket (or plain 768-style
  feature) that is always active and learns what all buckets share. After
  training its weights are added into every real bucket, so inference cost
  is unchanged. nnue-pytorch finds it matters mostly early in training and
  can be dropped later. CPW says it helps buckets with little data.
- **Cost.** Bucket changes force refreshes, which refresh caches make cheap
  (§2.4). The weight table grows linearly with the bucket count, so memory
  and file size grow too.
- **Pitfalls.** A bucket the data never visits stays untrained. Watch the
  bucket-visit histogram of the dataset.
- **Evidence (release notes, Viridithas).**
  - Moving from no buckets to a few: +5.47 ± 3.57 (v12.0.0, 2024-03).
  - A later net with more buckets: +23.64 ± 8.91 (v13.0.0, 2024-06). That
    net may also differ in other ways (data, training).
  - Alexandria 8.0.0 went from 1 bucket to many while shrinking the hidden
    layer; the notes give no isolated number.
- Sources: CPW NNUE (King Input Buckets, Feature Factorizer); nnue-pytorch
  `nnue.md` (Feature factorization); asteri.sm "NNUE research 02"
  (2024-07-15); Viridithas v12.0.0, v13.0.0 releases; Alexandria v8.0.0
  release.

### 1.6 Threat-aware inputs (attacker/target relations)
- **What.** Extra binary inputs, one per (attacking piece and square,
  attacked piece and square) pair where the first piece attacks the
  second, seen from each perspective. They cover both threats (attacks on
  enemy pieces) and defences (attacks on own pieces). This adds tens of
  thousands of possible input indices.
- **Why it helps.** The plain piece-square inputs can only infer attacks
  indirectly. Threat inputs hand the net the interaction graph directly.
  The nnue-pytorch docs describe piece inputs as the foundation and threat
  inputs as many small corrections. Threat inputs cannot stand alone,
  because a quiet position has none.
- **Removing redundancy (the principle).**
  - If piece type A's attack pattern is contained in piece type B's, then
    "A attacks B" implies "B attacks A". One direction can be dropped. A
    rook and a queen on the same line are an example.
  - For two pieces of the same type, one of each mutual pair can be
    dropped by a fixed ordering rule.
  - King-attacks-king never happens in a legal position.
  - Attacks *on* a king are of little use, because eval is not called in
    check. Stockfish's architecture history shows its threat set later
    dropped king-related threats in two steps.
- **Keeping it incremental.**
  - Threat inputs get their **own accumulator**, because they refresh on
    different triggers. With mirroring they need a refresh only when the
    king crosses the centre line, not on every king-bucket change. The two
    accumulators are combined at eval time.
  - Per move, the changed threat inputs come from the attack relations
    that changed. Reasoning (**not stated in the opened sources**): those
    are the moved piece's attacks before and after, attacks on its from
    and to squares, any captured piece's relations, and sliders whose rays
    pass through the from or to square. The PlentyChess PR credits Yukari
    for the incremental threat-tracking approach. Its details are
    **UNVERIFIED** (not opened).
- **Cost.**
  - Clearly slower. PlentyChess's notes call it "quite a big slowdown".
  - In a typical middlegame, three to four times as many threat inputs
    change as piece inputs (nnue-pytorch), so memory bandwidth becomes the
    bottleneck.
  - Storing threat weights as int8 and widening them to int16 while
    accumulating saved about 5% speed on x86 (about 10% on ARM). It needs
    the threat weights clipped small in training, at negligible loss.
  - Engines that adopted threat inputs cut their first-layer width sharply
    to pay for them. Stockfish's history shows the same move. Exact widths
    are not recorded here.
- **Data.** More inputs to learn. The minimum data volume needed is not
  stated anywhere opened (**UNVERIFIED**). The projects that use threat
  inputs train on billions of positions.
- **Evidence (PR descriptions, self-play).**

  | Test | PlentyChess PR #400 (2025-10) | Stormphrax PR #293 (2026-02) |
  |---|---|---|
  | fixed nodes | +45.49 ± 2.23 | +33.51 ± 9.35 |
  | STC (8+0.08) | −3.08 ± 2.89 (SPRT failed) | +2.73 ± 2.07 |
  | LTC (40+0.4) | +1.78 ± 1.37 | +9.85 ± 4.24 |
  | 4 threads (20+0.2) | not given | +13.03 ± 4.94 |

  The gain at equal nodes is large. The speed cost eats most of it at short
  time controls, and the net gain grows with time per move and with
  threads. That fits TCEC's long time controls. Stockfish 18's release
  (2026-01) introduced threat inputs. Stockfish 19's release (2026-09)
  removed redundant threat inputs to shrink the binary.
- **History.** Both PR descriptions credit the Monty project (jw1912,
  Viren6) with introducing this input encoding (Monty is an MCTS engine).
  The Stormphrax PR credits the Yukari engine with showing it works in
  NNUE. PlentyChess's notes call it the first top alpha-beta engine with
  efficiently updated threat inputs (October 2025).
- **Pitfalls.** Correctness of incremental threat deltas: test them against
  a from-scratch rebuild at every node in debug builds. Accumulator
  overflow is more likely with many more active inputs (§5.1). The net
  must still work when no threats are present.
- Sources: nnue-pytorch `nnue.md` (Full_Threats, deduplication, I8 threat
  weights); `nnue_architecture_history.md`; PlentyChess PR #400 and
  b-v7.0.2 and b-v8.0.0 releases; Stormphrax PR #293 and v8.0.0 release;
  Stockfish 18 and 19 releases; Reckless v0.9.0 and Integral v8 releases
  (adoption).

### 1.7 Pawn-structure inputs
- **What.** Inputs for unordered pairs of pawns (any colours) on the same
  or adjacent files. They generalize pawn-to-pawn attacks, which are then
  removed from the threat set to avoid duplication. Stockfish's history
  also lists "opposed-pawn" inputs added to its threat set (2026). The
  weights are stored as int8, as for threats.
- **Why it helps.** Pawn structure (doubled, isolated, passed, phalanx)
  is a relation between pawns that piece-square inputs only see
  indirectly. Pawns move rarely, so these inputs change slowly.
- **Cost.** Few active pairs, rare changes. nnue-pytorch notes that its
  indexing reserves the whole pair space for fast SIMD indexing, so many
  indices are never active and never trained (wasted file space).
- **Evidence.** Stockfish 19's release credits the new pawn-pair inputs
  for increased strength. Stormphrax 8.0.0 and PlentyChess 8.0.0 also
  added pawn-pair inputs, both bundled with other changes. **No isolated
  SPRT number was found** in the opened sources (**UNVERIFIED**).
- Sources: nnue-pytorch `nnue.md` (PP_3Wide); `nnue_architecture_history.md`;
  Stockfish 19 release; Stormphrax v8.0.0; PlentyChess b-v8.0.0.

### 1.8 Other input ideas since 2024
- **Augmented inputs tried by the community.** Viridithas's author planned
  tests of passed-pawn, castling-rights and bishop-pair inputs (2024-06).
  No published result was found (**UNVERIFIED**).
- **The direct PSQT-like shortcut removed.** Stockfish's architecture
  history records removing a direct linear connection from inputs to
  output in 2026-09, so the deep path alone now carries the eval. No
  reason or result is given there (**UNVERIFIED** effect).
- **Training-time input tricks** (factorizers, §1.5) cost nothing at
  inference. They are the cheapest way to make a richer input set
  trainable.
- Search for 2025-2026 arXiv papers on NNUE architecture: one search
  (2026-10-28) found none beyond 2412.17948. That is search-based
  absence, not proof (**UNVERIFIED**).

---

## 2. Accumulator design

### 2.1 Perspective: two accumulators, side to move first
- **What.** Keep one first-layer output vector per colour, each computed
  from that colour's oriented view. At eval time, concatenate them with
  the side to move's first, then feed the later layers.
- **Why.** The net learns tempo for free, and the output is from the side
  to move's point of view. bullet's docs say perspective inputs are much
  better than white-relative ones. nnue-pytorch lists the options:
  white-first, side-to-move-first, or interleaved (useful only for exotic
  sparse designs).
- **Weights.** Shared weights with an oriented board are the norm.
  nnue-pytorch notes that separate weights per colour are valid but larger
  and slower to train.
- Sources: bullet `1-basics.md` (Perspective Networks); CPW NNUE
  (Perspective); nnue-pytorch `nnue.md`.

### 2.2 Incremental updates, fused updates, copy-make stack
- **What.**
  - On a move, subtract the weight rows of inputs that turned off and add
    the rows of inputs that turned on.
  - **Fused** routines do all of a move's adds and subtracts in one pass
    over the vector: two rows for a quiet move, three for a capture, four
    for castling, per perspective. The accumulator is loaded and stored
    once.
  - A **ply-indexed stack** of accumulators (copy-make) means unmake is
    free: just step back down the stack.
- **Why.** Integer updates are exact. With floats, repeated add/subtract
  drifts, and a stack bounds the drift to the search depth (nnue-pytorch).
  Fusing saves memory traffic. One blog post measured about 3% from
  keeping the vector in registers through a multi-row update.
- **Cost model (reasoning).** Each changed input costs W int16 adds per
  perspective, where W is the accumulator width: W/16 vector ops on AVX2,
  W/32 on AVX-512. A quiet move touches 4 rows across both perspectives.
- Sources: CPW NNUE (Efficient Updates, Fused Updates, Copy-Make);
  nnue-pytorch `nnue.md` (Accumulator); asteri.sm "NNUE performance
  improvements" (2024-06-01).

### 2.3 Refresh cost, and what forces a refresh
- **Refresh** means rebuilding a perspective's accumulator: the bias plus
  every active input's row, up to 32 rows for piece inputs (more with
  threat inputs). An incremental update touches about 2-4 rows.
- **Triggers (piece accumulator):**
  - the own king changes bucket;
  - the own king crosses the mirror line;
  - a new root position (`position`, `ucinewgame`);
  - a lazy walk-back that hits one of the triggers above.
  Only the perspective whose king moved needs a refresh; the other one
  updates incrementally.
- **Triggers (threat accumulator, if any):** in the nnue-pytorch design
  only the mirror-line crossing. nnue-pytorch says threat refreshes are
  uncommon, so their cost is negligible.
- Sources: CPW NNUE (King Input Buckets, Horizontal Mirroring);
  nnue-pytorch `nnue.md` (HalfKP, Full_Threats).

### 2.4 Refresh caches keyed by king bucket ("Finny tables")
- **What.** Per thread and per perspective, keep one cached accumulator and
  the board (piece bitboards) it was built from, for each king bucket (and
  mirror side). On a refresh:
  - load the cached entry for the new bucket;
  - diff its bitboards against the current board;
  - apply only the differences;
  - store the result back into the cache.
  An empty cache entry (bias only, empty board) works as a starting point,
  so no separate fill step is needed.
- **Why.** Positions that share a king bucket tend to differ by only a few
  pieces, so a refresh costs a handful of rows instead of the whole board.
- **Credit.** CPW credits Finn Eggers (Koivisto).
- **Evidence.**
  - Berserk 9: "fast refresh logic" gave about 3.5% speed.
  - Alexandria 8.0.0 notes say it "greatly" sped up evaluation.
  - Later Alexandria releases added fused add/sub for cache updates and
    better cache handling, without numbers.
- **Pitfalls.**
  - Memory: buckets × mirror sides × perspectives × W × 2 bytes per thread.
    At TCEC's hundreds of threads that is real memory (reasoning).
  - The cache must be reset whenever the network changes (for example on a
    new `EvalFile`).
- **Naming note.** "Finny table" is a community term. Any Fork name goes
  through the DESIGN.md §8 screen.
- Sources: CPW NNUE (Accumulator Refresh Table); asteri.sm 2024-06-01;
  Berserk 9, Alexandria v8.0.0, v9.0.0 and v9.1.0 releases.

### 2.5 Lazy (deferred) updates
- **What.** On make-move, record only which inputs changed and mark the
  accumulator dirty. When eval is actually needed, walk back down the
  stack to the nearest clean accumulator, then apply the recorded changes
  forward. A refresh cache is used if a bucket change sits on the path.
- **Why.** Many nodes never need an eval: TT cutoffs, and evals cached in
  the TT. CPW stresses this for Lazy SMP, where the shared TT saves even
  more evals.
- **Variants and evidence.**
  - Caissa 1.26 generalized the walk so that every dirty node on the path
    is filled in. Siblings at any depth can then reuse the intermediate
    accumulators: +1.24 Elo at STC with identical search output.
  - Viridithas 15 added "speculatively force accumulator materialisation
    for some positions"; the notes give no details.
  - Alexandria 7.1 made eval updates "fully lazy" for a speed gain; no
    number given.
- **Pitfalls.** Each perspective's dirty state is separate. A refresh on
  one perspective must not mark the other clean.
- Sources: CPW NNUE (Lazy Updates); asteri.sm 2024-06-01; Caissa 1.26,
  Viridithas v15.0.0, Alexandria v7.1.0 releases.

### 2.6 Null move and other special cases
- **Null move.** No piece moves, so no input changes in either
  perspective. The accumulator can be reused or copied; only the order of
  concatenation flips, because the side to move changed. This follows
  directly from the input definition; no opened source states it.
- **Side-to-move order** is applied at eval time, never baked into the
  accumulator.
- **Castling and en passant** are ordinary multi-row updates: four rows for
  castling, three for en passant (the captured pawn is not on the target
  square).
- **Promotion** removes a pawn and adds the new piece: two rows, or three
  with a capture.
- Sources: CPW NNUE (Efficient Updates); reasoning noted above.

### 2.7 Threads and memory
- Accumulator stacks and refresh caches are per thread. The weights are
  shared, read-only.
- Viridithas 16 uses `mmap` to share net weights across processes.
  Stockfish 18 introduced shared memory for net weights across processes.
  Both mainly matter for running many engine instances, as in testing.
- Sources: Viridithas v16.0.0 release; Stockfish 18 release.

---

## 3. Network body

### 3.1 A single hidden layer
- **What.** Inputs, then the accumulator (one per perspective), then an
  activation, then one output neuron. In shorthand, (inputs → W)×2 → 1.
- **Why.** The accumulator is the only layer that can be updated
  incrementally, so it holds most of the knowledge. Once the accumulator is
  ready, eval costs one dot product.
- **Width trade-off.**
  - CPW: wider layers trade speed for accuracy. Most top engines use more
    than about a thousand neurons, and some use a few thousand.
  - bullet's docs advise widening this layer (into the low thousands)
    before adding depth.
  - Viridithas's author ran a fixed-node gauntlet of nets from a few dozen
    to a few thousand neurons: Elo tracked training loss closely.
- **Evidence.** Viridithas 9.1.0: a much larger net trained on more data
  gained +20.20 ± 9.42.
- Sources: CPW NNUE (Accumulator); bullet `1-basics.md`; asteri.sm
  "NNUE research 02"; Viridithas v9.1.0 release.

### 3.2 Deeper stacks (multi-layer)
- **What.** After the activated accumulator, one or two small dense layers
  (widths of a few to a few dozen), then the output.
- **Why.** More capacity per eval, and room for gating tricks (§3.4,
  §4.5). nnue-pytorch: most knowledge stays in the first layer, and later
  layers add little and can add quantization error. Keep them small.
- **Cost.** The first dense layer (accumulator output × its width) is
  usually the most expensive part of the forward pass. It needs hand-
  written SIMD, int8 quantization or float, and sparse kernels (§3.5).
- **Evidence.**
  - CPW: multi-layer nets are generally stronger but can lose at very short
    test time controls.
  - bullet: deeper nets gain at fixed nodes, but it is hard to keep the
    speed hit from losing Elo.
  - Many engines moved to multi-layer nets in 2024-2026 (Viridithas 14,
    Obsidian 15, Halogen 14, Integral 7, Alexandria 9, Caissa 2.0). Each
    release bundles other changes, so there are no isolated numbers.
- Sources: CPW NNUE (Multiple Layers); nnue-pytorch `nnue.md` ("Further
  layers"); bullet `1-basics.md`; listed releases.

### 3.3 Output buckets and layer stacks chosen by material
- **What.** Several copies of the output layer (or of every layer after the
  accumulator, "layer stacks"), picked by a cheap, slowly changing
  property. The usual choice is the piece count, cut into equal ranges.
  In training, all copies are computed as one wide layer and the right
  slice is gathered for each position.
- **Why.** Openings, middlegames and endgames need different weightings.
  Almost free at inference.
- **Evidence.**
  - Viridithas's author: a "modest but clear" loss improvement over a
    single output (2024-06).
  - Reckless 0.7 and Viridithas 14 added output buckets among other
    changes; no isolated SPRT.
  - CPW calls layer stacks a generalization of output buckets and says
    most multi-layer top engines use something like them.
- **Pitfalls.** Buckets for rare material counts get little data, so keep
  ranges coarse early.
- Sources: CPW NNUE (Output Buckets, LayerStacks); nnue-pytorch `nnue.md`
  (Multiple subnetworks); asteri.sm "NNUE research 01"; releases above.

### 3.4 Pairwise multiplication of accumulator halves
- **What.** Split each perspective's activated accumulator into two halves
  and multiply them element by element. The vector feeding the next layer
  is half as long. Pairing elements half a vector apart, rather than
  adjacent ones, makes the SIMD simpler.
- **Why.**
  - It halves the cost of the expensive first dense layer.
  - The product of two clipped values behaves like a squared activation,
    but between two *different* features.
  - Viridithas's author frames it as a gated linear unit variant (a "GLU"
    whose two branches are both activated).
- **Cost.** At equal width it is faster but less accurate (CPW). It pays
  for itself by allowing a wider accumulator or deeper layers.
- **Quantization.** The product of two values in the quantized activation
  range exceeds 8 bits, so it is rescaled with a power-of-two shift.
  nnue-pytorch's product-pooling notes describe giving up a sliver of
  output range to make the divisor a power of two.
- **Evidence.** It is used by many multi-layer engines (Viridithas 14,
  Caissa 2.0). No isolated SPRT was found (**UNVERIFIED** as a number).
- Sources: CPW NNUE (Pairwise Multiplication); asteri.sm "multilayer"
  (2024-08-17) and "activation" (2026-01-13); nnue-pytorch `nnue.md`
  (Product Pooling); Caissa 2.0 release.

### 3.5 Sparse first dense layer
- **What.** After clipping, most accumulator outputs are zero. nnue-pytorch
  shows density at or below about 15% for common widths. The first dense
  layer then only processes the non-zero inputs, found with a bit mask. It
  works in blocks of four adjacent 8-bit activations (one 32-bit chunk),
  so one index covers four inputs and the bookkeeping stays small.
- **Making it sparser.**
  - An L1 penalty on the accumulator *activations* in training (not on the
    weights) increases sparsity. Viridithas's author says it also helped
    strength on its own.
  - Permuting neurons so that often-non-zero ones sit together raised
    zero-block odds for about 2% speed (nnue-pytorch).
  - Alexandria 9.1 added a permutation step to maximize sparsity.
- **AVX-512.** Halogen 15 uses a 16-bit compress instruction to handle many
  blocks of four activations at once.
- **Pitfalls.** An activation change can quietly kill sparsity, and speed
  with it: a Hard-Swish experiment dropped block sparsity from about 70% to
  about 50% (§4.5). Track sparsity as a metric of every training run.
- Sources: nnue-pytorch `nnue.md` (Linear layer with sparse input, blocked
  sparse input, "Helping the odds"); asteri.sm "multilayer" and
  "activation-2"; Halogen v15 and Alexandria v9.1.0 releases; Stockfish 16
  release (sparsity in inference).

### 3.6 "Dual activation", and mixed activations per layer
- Alexandria 9.0.0 and 9.1.0 list "dual activation" in their net
  architecture. **No opened source defines the term** (**UNVERIFIED**; one
  web search found no primary description). A designer must not assume a
  meaning.
- **Documented nearby idea.** Different activations in different small
  layers. Viridithas's author reports that one strong engine found a plain
  clipped ReLU in one small layer and a squared clipped ReLU in the next
  worked best (§4.5).
- Sources: Alexandria v9.0.0 and v9.1.0 releases; asteri.sm "activation-2"
  (2026-01-27).

### 3.7 Small later layers in float32
- **What.** The layers after the first dense layer are tiny, so some
  engines run them in float32. That avoids fixed-point error, and the cost
  is small.
- Source: asteri.sm "multilayer" (2024-08-17), describing Viridithas.
- **Pitfall.** Float results can differ across compilers and instruction
  sets (FMA contraction, summation order). That can break bench parity
  across builds unless the summation order is fixed. This is Fork
  reasoning tied to DESIGN.md's bench-parity rule. Viridithas 16 lists a
  "separate sum vector for reproducible bench", which hints at the same
  issue (no details given).

---

## 4. Activations

### 4.1 ReLU, clipped ReLU (CReLU), squared clipped ReLU (SCReLU)
- **ReLU** (max(x, 0)) is unbounded, so quantized outputs can overflow.
  CPW says it is rarely used for that reason.
- **CReLU** clamps to [0, 1]. In integers that becomes [0, Q], where Q is
  the activation quantization factor. It is simple and auto-vectorizes.
- **SCReLU** squares the clamped value. It adds non-linearity, and CPW
  calls it the most common and strongest choice for single-layer nets. It
  needs hand-written SIMD.
- **Evidence.**
  - Viridithas 9.0.0: squaring the CReLU of the feature transformer gained
    +35.8 ± 11.6.
  - Viridithas's author's loss study: SCReLU beat CReLU at every width,
    worth about a 50% wider layer at the larger widths. He also notes many
    engines saw double-digit gains, though not every developer found it an
    improvement.
  - Reckless 0.6 switched to SCReLU (no number given).
- Sources: CPW NNUE (Activation Function table); asteri.sm "NNUE research
  01", "NNUE performance improvements"; Viridithas v9.0.0, Reckless v0.6.0
  releases.

### 4.2 Integer forms and the overflow problem
- With activation factor Q_A and output-weight factor Q_B, CReLU output
  times weight fits int16 when the weights are clipped. For SCReLU,
  however, v² can reach Q_A² by itself. With Q_A in the low hundreds, that
  exceeds int16 before it is even multiplied by a weight.
- One older workaround picked Q_A small enough that Q_A² fits int16.
  Viridithas's author calls this obsolete, because the precision loss hurts
  at long time controls.

### 4.3 The published reordering trick ("Lizard SCReLU")
- **The arithmetic.**
  - Compute (v × w) first, in 16 bits, then multiply that by v using the
    instruction that multiplies 16-bit pairs and adds neighbouring products
    into 32-bit lanes.
  - This stays exact if |v × w| ≤ 32767. Since v ≤ Q_A, the float output
    weights must satisfy |w_float| ≤ 32767 / (Q_A × Q_B), so training
    clips them to that bound.
  - Only the final 32-bit sum is divided back down, by Q_A, then by
    Q_A × Q_B, and scaled.
- **Credit.** CPW credits Liam McGuire (Lizard engine).
- **Tighter clipping as a knob.** Clipping weights to a smaller range
  allows a proportionally larger quantization factor, which means less
  rounding error. Motor reported +6.84 ± 4.40 at STC and +8.74 ± 4.98 at
  LTC from this. Alexandria 7.1 notes also tightened clipping "for better
  quantization" (value not recorded here).
- **A pitfall the sources do not mention (Fork reasoning).** Each lane's
  32-bit partial sum adds up to 2W products, each up to 32767 × Q_A. For
  widths in the thousands and Q_A in the hundreds, the worst case passes
  2³¹. Real weights are far below the clip bound and activations are
  sparse, so this does not happen in practice. A designer should still
  either prove a bound for the chosen sizes or check the maximum partial
  sum over a large position set in a debug build.
- Sources: CPW NNUE (Quantization, Lizard SCReLU); asteri.sm
  "NNUE performance improvements", "NNUE research 02"; Alexandria v7.1.0
  release.

### 4.4 Sigmoid approximations and product pooling
- nnue-pytorch describes **Quantmoid4**: a piecewise-quadratic stand-in for
  a stretched sigmoid that needs only add, multiply and shift, with output
  in an 8-bit range. In training, the non-smooth function's gradient is
  replaced by the smooth sigmoid's. This is the straight-through idea of
  §5.6.
- **Product pooling** (multiplying pairs, as in §3.4) adds capacity, while
  average or max pooling only reduce width.
- Source: nnue-pytorch `nnue.md` (Quantmoid4, Pooling layers,
  Non-differentiable layers).

### 4.5 Smooth and gated activations in the small layers (2026)
- **What.** Viridithas replaced SCReLU in its two small hidden layers with
  Swish (x · sigmoid(x)), using a cheap hard approximation at first. It
  then replaced the second with SwiGLU, a gated unit (Shazeer, arXiv
  2002.05202).
- **Evidence (Viridithas's author, 2026-01-27).**
  - Swish: +13.77 ± 5.04 at STC and +5.90 ± 3.11 at LTC.
  - SwiGLU on top of that: +5.47 ± 3.04 at LTC.
  - The output histograms also became smoother.
- **Pitfall found.** Hard-Swish is unbounded above. It cut the block
  sparsity of the first-layer output from about 70% to about 50%, which
  hurt speed badly. An L1 penalty on those activations restored it.
- **Context.** Viridithas does not clip the weights after its first dense
  layer, which may interact with these results (author's caveat).
- Sources: asteri.sm "activation" (2026-01-13) and "activation-2"
  (2026-01-27); arXiv 2002.05202 (abstract).

---

## 5. Quantization

### 5.1 int16 accumulators, and choosing the scale from overflow bounds
- **What.** First-layer weights and biases are stored as int16, scaled by
  Q_A, and the accumulator adds them up in int16.
- **Bound reasoning (Fork's derivation from the definitions).**
  - |accumulator| ≤ |bias| + (number of active inputs) × max|weight|.
  - With piece inputs only, at most 32 are active per perspective. So
    32767 / 33 ≈ 990 is the largest quantized weight magnitude that can
    never overflow. Q_A × max|w_float| must stay under it, or the trainer
    must clip the weights.
  - Threat inputs raise the active count a lot, so the bound tightens.
    That is one reason threat weights are kept small and stored as int8
    (§1.6).
- nnue-pytorch says the scheme "must be chosen such that no combination of
  possible active features can exceed the maximum value". In practice,
  sources treat the feature transformer and biases as safe, because real
  weights are far from the bound.
- **Activation range.** Clipping to [0, Q_A] after accumulation, then
  packing to 8 bits (if the next layer is int8), is the documented
  pattern.
- Sources: nnue-pytorch `nnue.md` (Accumulator, Quantization, "Accounting
  for quantization in the trainer"); CPW NNUE (Quantization).

### 5.2 int8 or int16 hidden weights
- **int8 weights with 8-bit activations** use the multiply-unsigned-by-
  signed-bytes instructions: 4 products per 32-bit lane per instruction
  with VNNI, or 2 into 16 bits followed by a widening step without it
  (§7.2). That is about twice the throughput of int16, but the weight range
  is small. With weight factor s_W, the largest float weight is about
  127 / s_W, so training must clamp weights to it.
- **int16 weights** use the 16-bit pairwise multiply-add. They are simpler,
  with more range and precision, and slower.
- **bullet's position.** bullet's maintainer says (issue #167) that anyone
  doing int8 inference should quantize the float weights themselves. Such
  nets usually also need factorizer merging and neuron permutation, which
  bullet does not aim to handle. He added int8 as a quantization target,
  but the default stays int16.
- **Float option.** Run the small layers in float32 (§3.7).
- Sources: nnue-pytorch `nnue.md` (Linear layer quantization); bullet
  issue #167 (maintainer comment, 2024-11-10).

### 5.3 Scale factors, shifts and output scaling
- For a dense layer with input factor s_A and weight factor s_W:
  - biases are scaled by s_A·s_W;
  - the integer product is divided by s_W to land back in the activation
    range.
- Choose s_W as a power of two so the division is a shift. There is no
  SIMD integer divide.
- **Output layer.** An extra output factor s_O maps the float output to
  internal eval units. It is applied in training too, in the loss, so the
  last layer's weights stay in a range similar to the others.
- Source: nnue-pytorch `nnue.md` ("The math of quantization", Implementation).

### 5.4 Rounding
- bullet's `SavedFormat` **truncates by default** (value × Q cut toward
  zero). Rounding must be requested explicitly. Truncation biases every
  weight toward zero, a free accuracy loss that is easy to miss. bullet
  also refuses to write the quantized file if any value overflows the
  target type (training continues regardless).
- Source: bullet `4-saved-networks.md`.

### 5.5 How quantization error propagates
- nnue-pytorch: error grows with depth, but for shallow NNUE nets it is
  negligible. A floating-point accumulator would drift under incremental
  updates, while integers are exact.
- The bigger risks are training-versus-inference mismatches:
  - weights outside the clip range;
  - a different clamp point in training and in inference;
  - truncation instead of rounding (§5.4);
  - an activation that saturates in int8 but not in float.
- Source: nnue-pytorch `nnue.md` (Quantization 101, Accounting for
  quantization in the trainer).

### 5.6 Quantization-aware training (QAT)
- **What.** In training, the forward pass simulates the integer inference:
  weights and activations are rounded and clipped to their quantized grids
  ("fake quantization"), while the stored weights stay in float. The
  backward pass treats rounding as the identity (a straight-through
  estimator), so gradients still flow. The net learns weights that are
  robust to the rounding it will meet at inference.
- **Foundations.**
  - Jacob et al. (arXiv 1712.05877) describe simulating quantization in
    the forward pass, with fake-quantization operators placed where
    tensors are down-cast at inference.
  - Bengio et al. (arXiv 1308.3432) name and analyze the straight-through
    estimator.
  - nnue-pytorch's lighter version clamps weights to the representable
    range after every optimizer step, without simulated rounding. For
    non-differentiable layers it substitutes a smooth gradient.
- **Evidence in chess.** Stockfish 19's release (2026-09) lists QAT among
  the new training techniques. No isolated Elo is given (**UNVERIFIED** as
  a number). Stockfish's history also records an "updated fixed-point
  quantization" step in 2026-05.
- **bullet support.** bullet has a merged PR #483, "Add QAT operation"
  (2025-10-20), with an empty description. **bullet's docs do not mention
  QAT.** What the operation does and how to use it are **UNVERIFIED** from
  docs. Reading bullet's code would answer it; that is allowed for a tool
  under MIT, but was not done here.
- **When it matters.** Most for int8 layers and small quantization factors.
  Least for int16 accumulators with generous factors (reasoning).
- Sources: Stockfish 19 release; `nnue_architecture_history.md`; arXiv
  1712.05877 (paper text, section 3); arXiv 1308.3432 (abstract);
  nnue-pytorch `nnue.md`; bullet PR #483 (title and metadata only).

---

## 6. Training practice

### 6.1 Targets: blending the search score and the game result
- **What.**
  - Convert the stored search score to win probability:
    sigmoid(score / scale), with a scale of a few hundred centipawns.
  - Mix it with the game result (0, ½, 1) using a weight λ:
    target = λ·sigmoid(score/scale) + (1−λ)·result.
  - nnue-pytorch shows this can be done on the targets or on the two
    losses, and says which works better depends on the setup.
- **Scheduling λ.**
  - Alexandria's notes mention "WDL scheduling" and a two-step training.
  - Viridithas's newer net uses a different λ in the final stage of
    training.
  - Exact values are engine choices and are not recorded here.
- **WDL heads.** Viridithas is experimenting with nets that output win,
  draw and loss probabilities instead of one value. Alexandria 9.0 "added
  a WDL component to loss". Neither gives details (**UNVERIFIED**).
- Sources: nnue-pytorch `nnue.md` (Loss functions); CPW NNUE (Output Layer);
  asteri.sm "nnue-eval-scale" (2025-12-12); Alexandria v8.1.12, v9.0.0 and
  v9.1.0 releases.

### 6.2 The loss and its exponent
- **What.** Squared error between the predicted and target probabilities.
  An exponent above 2 punishes large errors more and small ones less.
  nnue-pytorch reports Stockfish trained well with an exponent above 2
  (value not recorded here). Cross-entropy is the documented alternative.
- **Evidence (STC SPRTs reported by Viridithas's author).**
  - Starzix: +15.76 ± 7.25 from a higher exponent.
  - Motor: +23.96 ± 9.04 from a higher exponent.
- **Caution.** Combining a higher exponent, tighter clipping and an
  optimizer tweak in Viridithas gave:
  - +14.81 ± 5.85 at fixed nodes;
  - +6.82 ± 3.55 at STC;
  - +0.72 ± 3.75 at LTC (neutral).
  A training change can look good at fixed nodes and fade at long time
  controls, so test at the time control that matters.
- Sources: nnue-pytorch `nnue.md` (MSE, Cross entropy); asteri.sm "NNUE
  research 02" (2024-07-15).

### 6.3 Eval scale, and how it interacts with search
- **What.** At inference the raw output is multiplied by the same scale
  that the sigmoid used in training. The finding: the blend weight λ
  changes how large the outputs come out. Score-only targets push the net
  to predict big numbers for positions that are already won.
- **Evidence.**
  - Viridithas's author trained test nets across the λ range: the needed
    rescaling moved steadily with λ.
  - A net used at the "wrong" scale for a search tuned on another scale
    lost strength.
  - Rescaling the inference output to match the old net's average
    absolute eval gave one test net +28 Elo at fixed nodes. Rescaling did
    not help the low-λ nets.
  - Viridithas 19's release credits "a trivial breakthrough in evaluation
    scaling" for a much stronger net.
- **For Fork.** Fork's Phase 3 pruning margins (RFP, futility, razoring,
  and so on) were tuned on the HCE's scale. The first net will need either
  an output rescale to match, or the Phase 4 margin retune. CLAUDE.md
  already requires that retune after the network. Comparing mean absolute
  eval on a fixed position set is a cheap check.
- **Reporting.** Several engines normalize UCI output so that +100 cp
  means about a 50% win chance (Viridithas 8.1, Berserk 11, Stormphrax 3).
  This is display only and separate from the internal scale.
- Sources: asteri.sm "nnue-eval-scale"; Viridithas v19.0.1, v8.1.0;
  Berserk 11; Stormphrax v3.0.0 releases.

### 6.4 Optimizer, learning-rate schedule, batch size
- **Optimizer.** AdamW is the standard.
  - Raising the first-moment decay (β₁) slightly gained +3.95 ± 3.03 in
    Motor.
  - Ranger21 lost badly in three Starzix tests (−25 to −200 Elo), and Lion
    lost about −59.
  - Schedule-free AdamW reached lower loss than a Ranger baseline but was
    weaker: −4.55 ± 3.48 at fixed nodes and −5.12 ± 3.43 at STC (2026).
- **Schedule.** In short runs, the schedules tested were nearly
  indistinguishable, with cosine slightly ahead (2024). The same author's
  2026 note recommends linear decay if unsure. Caissa 2.0 lists a cosine
  schedule; Caissa 1.26 trained in several LR phases. Exact rates are not
  recorded here.
- **Batch size.** In short runs, smaller batches trained more efficiently
  per compute. When another engine tried it on a long run, it did not
  help. Possible reasons offered: loss does not equal Elo, long runs
  differ, or big batches regularize. Unresolved.
- **Overfitting.** For nets this small, trained on billions of positions
  seen roughly once with weight decay, the author argues overfitting is
  unlikely. bullet gained test-set support anyway.
- Sources: asteri.sm "NNUE research 01", "NNUE research 02", "optimisers"
  (2026-07-27); Caissa 1.26 and 2.0 releases.

### 6.5 Position filtering
- **Common filters.**
  - Skip positions in check.
  - Skip positions where the best move is a capture or other tactical move.
  - Skip mate scores.
  - Skip positions whose static eval disagrees sharply with a quiescence
    or search score.
- bullet's binpack loaders take a filter function to drop "noisy"
  positions. Viridithas added binpack subsampling (taking only some
  positions from each game). Alexandria added "piece-count filtering" and
  "WDL filtering/skipping". Caissa's PGN converter keeps only quiet,
  not-in-check positions.
- **arXiv 2412.17948 (Tan and Watkinson Medina, 2024-12-23).**
  - **Filter:** a position is kept only if it is not in check, its static
    eval is within a margin of its quiescence score, and within a second
    margin of its search score. Both margins are under a pawn in their
    tuning.
  - **Distribution targets:** roughly half the positions favour each side,
    at least half are near equality, and a large share are clearly
    imbalanced, so the net learns to punish material deficits.
  - **Setting:** Xiangqi, not chess. Starting positions came from
    grandmaster games plus self-play between engines (including other
    engines). A one-hidden-layer net trained on PST-labelled data beat
    the handcrafted eval by about 100 Elo (65% score).
  - **Weaknesses:** no SPRT, no ablation of the filter, no chess results.
    Treat it as a description of a method, not proof of its value.
- Sources: bullet `3-data.md`; Viridithas v15.0.0; Alexandria v8.1.0,
  v9.0.0 and v9.1.0; Caissa 1.26 releases; arXiv 2412.17948 (full text).

### 6.6 Data volume and network size
- **No opened source gives a rule for positions per hidden neuron**
  (**UNVERIFIED**). What projects report:
  - Halogen's first supervised nets on its own data: about 0.6 billion
    positions, then about 1.35 billion, for a small single-layer net. It
    beat the previous main net by about +31 Elo.
  - PlentyChess's first own-data net: 7.2 billion positions.
  - Integral 8: 16.7 billion unfiltered positions.
  - Caissa 1.26: a 20.5-billion-position dataset, with several hundred
    billion positions seen in training (multiple passes).
  - Stockfish: "hundreds of billions" of positions (Lc0-rescored data,
    off-limits to Fork as data, cited only for scale).
- **Qualitative rules from the sources.**
  - bullet: big input sets need data a beginner lacks.
  - Viridithas: Elo tracks training loss across widths at fixed nodes.
  - Stormphrax 6: fixing a datagen bug and regenerating everything gave a
    big jump (+77 to +87 Elo at LTC and STC against 5.0.0, bundled with
    other changes).
- **For Fork (estimate).** The owner's datagen estimate is 100-300 million
  positions a day. One billion positions then takes about 3-10 days, and
  5 billion about 17-50 days. The first architecture's size should fit
  what a few weeks of datagen can feed.
- Sources: Halogen PR #517 description; PlentyChess b-v3.0.0; Integral v8;
  Caissa 1.26; Stockfish 19 releases; bullet `1-basics.md`; asteri.sm
  "NNUE research 02"; Stormphrax v6.0.0 release.

### 6.7 Growing the net across generations
- **The common path.** Small net and data → better net → better data →
  bigger net. Examples:
  - Viridithas trained generation after generation on its own games, each
    generation's data produced by the previous net. Its notes credit one
    early jump mostly to learning-rate tuning.
  - Reckless started from a random net and iterated.
  - Alexandria's widths and bucket counts grew over releases.
- Each step should be SPRT-tested (bullet's "skipped progression" warning).
- **Bigger at equal data is not free.** Alexandria 8.0 added buckets while
  shrinking the width. Threat-input engines cut width sharply.
- Sources: Viridithas v4.0.0 and v5.0.0 (footnotes on generations);
  Reckless v0.5.0; Alexandria v4.0.0 to v9.1.0 releases; bullet
  `1-basics.md`.

### 6.8 Rescoring
- **What.** Re-label old positions with a newer, stronger net, with or
  without search, and retrain.
  - Stockfish 19 rescored all its data with a Leela net. The label source
    is off-limits for Fork; the technique is cited only.
  - Viridithas 4 and 5 trained on "filtered and re-evaluated" data from
    the previous version's games.
- **For Fork.** Rescoring only with Fork nets is already decision A+.
- Sources: Stockfish 19 release; Viridithas v4.0.0, v5.0.0 releases;
  data-policy.md.

### 6.9 Bootstrapping from zero (precedents for A+)
- **From an HCE.** Generation 0 data is labelled by Fork's own HCE search
  (techniques.md §5). Viridithas did this: its early nets trace back to
  data from its HCE (v4.0.0 footnote).
- **From random weights.** Reckless 0.5 iterated from a randomly
  initialized net.
- **Halogen (2024).**
  - It began with TDLeaf(λ) reinforcement learning from random weights,
    over several runs of 8-16 hours each, then added temporal coherence.
  - It played out Syzygy endgames to fix endgame play.
  - It filtered out very unbalanced openings.
  - The final TD net was still about −182 Elo against the previous main
    net. Two rounds of supervised self-play datagen at a fixed node count
    (tens of thousands of nodes per move), trained with bullet, then beat
    the old main net by about +31.
- **PlentyChess (2024).** It switched from Lc0 data to its own on 7.2
  billion positions. The author estimated about −15 Elo for the net
  itself, but the release was the strongest yet thanks to a better
  architecture.
- Sources: Halogen PR #517, v12; Reckless v0.5.0; PlentyChess b-v3.0.0;
  Viridithas v4.0.0 releases; research.md (KnightCap/TDLeaf entry).

### 6.10 Self-play datagen practice
- **Node budget.** Viridithas's author describes typical datasets as
  self-play with "a small, fixed number of nodes per move". Halogen used
  fixed nodes in the tens of thousands.
  - Fixed nodes keep games reproducible and spread the work evenly across
    threads.
  - Fixed depth gives uneven times per move (reasoning).
  - OpenBench assumes deterministic games under fixed nodes or depth, so
    it does not play reversed colours by default.
- **Openings.**
  - OpenBench's `genfens` interface has the engine generate its own
    openings from a seed (random plies, optionally from a book). The
    engine must use all 64 bits of the seed, and print
    `info string genfens <fen>` lines.
  - Fork's A+ decision uses Lichess CC0 positions, then random plies.
  - Halogen dropped openings that were already far from balanced (several
    pawns).
  - PlentyChess 4 credits "a different way of generating training data"
    for much better play at high time controls. No details are given
    (**UNVERIFIED**).
- **Adjudication.** End games early with Syzygy WDL when few pieces
  remain, which is Fork's A+ rule. Halogen played out Syzygy endgames to
  teach endgames.
- **Compact game-based formats.** bullet recommends binpack-style formats,
  which store whole games and compress well. viriformat is "the most
  commonly used" among people who generate their own data. Its spec:
  - a 32-byte packed starting board;
  - then a 16-bit move and 16-bit score pair per ply;
  - four zero bytes to end the game;
  - little-endian throughout;
  - castling written as king-takes-rook (Chess960-safe).
  bulletformat is a simple fixed per-position record, stored relative to
  the side to move and without castling or halfmove data, suited to small
  nets.
- Sources: asteri.sm "nnue-eval-scale"; Halogen PR #517; OpenBench wiki
  "Data Generation Workloads"; viriformat README; bullet `3-data.md`;
  PlentyChess b-v4.0.0; training-data.md §3.4.

---

## 7. SIMD inference

### 7.1 Registers and lanes
- AVX2 has 16 vector registers of 256 bits (16 int16 lanes). AVX-512 has
  32 registers of 512 bits (32 int16 lanes). nnue-pytorch notes that past
  a few hundred neurons the accumulator update needs several passes,
  because AVX2 lacks registers to hold it all. AVX-512's extra registers
  help both the accumulator and the dense layers.
- Source: nnue-pytorch `nnue.md` ("First set of hidden neurons", Optimized
  implementation).

### 7.2 The dense-layer instructions, and a saturation trap
- **Without VNNI** (AVX2 and plain AVX-512):
  - multiply unsigned bytes by signed bytes;
  - add each neighbouring pair of products into a **saturating** int16
    (`pmaddubsw`);
  - then widen to int32 with a 16-bit multiply-add by 1.
  If an activation-weight pair sum passes ±32767, it silently saturates
  (CPW SSSE3 page). That is why int8 weights must stay small.
- **With AVX-512 VNNI**, one instruction (`vpdpbusd`) multiplies unsigned
  by signed bytes and adds groups of four products straight into the
  int32 accumulator, with no 16-bit intermediate (CPW AVX-512 page). VNNI
  is therefore faster, and it does not saturate where the older path
  would.
- **Parity consequence (reasoning).** VNNI, AVX-512, AVX2 and scalar builds
  agree bit for bit only if weights and activations are bounded so the
  16-bit path can never saturate. Prove it from the clip bounds, or test
  it. Fork's ideas.md idea 20 and DESIGN.md §7 already require SIMD
  against scalar equivalence.
- Sources: CPW SSSE3 (PMADDUBSW); CPW AVX-512 (VNNI, VPDPBUSD);
  nnue-pytorch `nnue.md` (m256_add_dpbusd_epi32).

### 7.3 AVX2 against AVX-512 and VNNI in practice
- **Evidence (release notes).**
  - Stormphrax 8: its AVX-512 build requires VNNI and VBMI2 and is
    "significantly" faster than the AVX2 build.
  - PlentyChess: AVX-512 with VNNI is the fastest build, but warns that the
    AVX2 build may be faster on some AVX-512 CPUs.
  - Halogen tables list AVX-512 VNNI from Zen 4 / Zen 5 on AMD.
  - Viridithas: its AVX2 build was about 40 Elo stronger than its generic
    build at 8+0.08 (2023).
- **TCEC's EPYCs.** The KB still lists VNNI on TCEC's CPUs (EPYC 9754 and
  9175F) as an **open question** (competition.md question 8; main's
  ideas.md idea 20). AMD's product and series pages opened today list no
  instruction-set extensions. **UNVERIFIED.** Halogen's tables imply that
  Zen 4 and Zen 5 have AVX-512 VNNI, but a release note is not AMD
  documentation.
- Sources: Stormphrax v8.0.0; PlentyChess b-v7.0.2, b-v8.0.0; Halogen
  v13-v16; Viridithas v7.0.0 releases; AMD EPYC 9754 and 9175F product
  pages.

### 7.4 Cost per eval and nps
- **No opened source measures the eval share of node time** for modern nets
  (**UNVERIFIED**). Known reference points:
  - CPW: the first Stockfish NNUE roughly halved Stockfish's search speed
    but was much stronger.
  - CPW: a 2020 hybrid that used the classical eval in lopsided positions
    gained up to about 10% speed and about 20 Elo.
  - Stockfish 18's release says top hardware searches over 500 million
    positions per second, with no per-thread figure.
  - PlentyChess: threat inputs cost "quite a big slowdown".
- **Ballpark nps of small against large nets:** no published per-thread
  figures were found for named architectures (**UNVERIFIED**).
- **Fork-side arithmetic (estimate, symbols only).**
  - Per eval: the accumulator update is about (changed rows) × W/lanes
    vector ops per perspective; the first dense layer is (2W, or W after
    pairwise) × L₁ multiply-adds at 64 per VNNI instruction (AVX-512) or
    32 per two to three instructions (AVX2 path), times the non-zero share
    if sparse; the rest is small.
  - Fork's HCE search runs at about 6.9 M nps (owner figure), so each node
    has roughly 150 ns of budget today. A net whose eval costs several
    hundred nanoseconds will cut nps severalfold unless lazy updates and
    TT eval caching skip evals.
  - The first net should be benchmarked with Fork's own `bench`, not
    predicted.

---

## 8. Trainer-engine parity

**Documented practice found:**
- **nnue-pytorch.** Its development guide documents `cross_check_eval.py`.
  It runs a trainer checkpoint and a matching Stockfish binary with the
  exported net on positions from a binpack, and compares their evals. Its
  pipeline test covers training, checkpoints, restarts, serialization, and
  feature-transformer optimization, and runs in CI. This is the clearest
  published parity check: the trainer's model against the engine's
  quantized inference, automated.
- **bullet.** Its docs say what is written, not how to check it:
  - each checkpoint holds `quantised.bin` (quantized, padded to a multiple
    of 64 bytes) and `raw.bin` (float values, no transform, no padding);
  - primitives are little-endian;
  - every weight matrix is written column-major, unless a transpose
    transform is applied;
  - quantization truncates unless rounding is requested;
  - transforms (for example merging a factorizer into the buckets) run in
    the order given, and rounding and quantization always come last;
  - the quantized file is skipped if any value overflows.
  **So the quantized file layout is documented, and is defined by Fork's
  own `SavedFormat` list.**
- **Can bullet evaluate a FEN with a trained float model?** The docs do not
  say. The repo has a merged PR #178, "Eval FENs with WDL output"
  (2024-11-29), with an empty description. **UNVERIFIED:** whether such a
  feature exists in the current version, what it outputs (float or
  quantized, WDL or score), and how to call it. Answering it means reading
  bullet's code or examples. That is allowed for a tool under MIT, but was
  out of scope for this clean-room file.
- **Engine-side debug views.**
  - Stockfish documents an `eval` command (a static eval breakdown) and an
    `export_net` command.
  - Caissa 1.26 added `eval detailed`: raw and activated accumulator
    values, saturated neurons, per-bucket outputs, and a per-piece value
    board.
  - Stockfish also documents `flip` (swap the side to move), which can be
    used to test perspective symmetry.

**Parity checks a design can adopt (Fork reasoning, from the facts above):**
1. **Float reference.** A small float evaluator (Python or C++) reading
   `raw.bin` and Fork's documented layout. Fork's quantized eval should
   match it within a tolerance derived from the quantization factors, over
   a fixed FEN suite. Run the check in CI.
2. **Exactness tests.**
   - Incremental against refresh: every node in debug builds
     (techniques.md §4).
   - SIMD against scalar: bit-exact (§7.2).
   - Colour-flipped position: the same eval from the mover's side.
   - Mirror symmetry, where the design uses mirroring.
3. **Range checks.** Log the maximum |accumulator| and the 32-bit partial
   sums over a large position set (§4.3, §5.1).
4. **Scale check.** Mean |eval| on a fixed set compared with the previous
   net (§6.3).

---

## 9. Design space for Fork

This section is neutral: it lists the main choices and their trade-offs,
with no recommendation.

**Fork's constraints.**
- **CPUs.** Targets are x86-64-v3 (AVX2, BMI2) and v4 (AVX-512). VNNI on
  TCEC's EPYCs is **UNVERIFIED** (§7.3). The scalar fallback must stay
  bit-identical.
- **Training.** Kaggle T4 ×2 or P100, 30 GPU hours a week in sessions of
  at most 12 hours (training-data.md §2.1). Long runs must checkpoint and
  resume across sessions. Throughput for a given width is **UNVERIFIED**:
  no published bullet speed on these GPUs was opened.
- **Data.** Only Fork's own self-play (A+), starting from the HCE.
  Datagen is estimated at 100-300 million positions a day on 12 threads
  (owner estimate, *not measured*). Lichess CC0 openings; Syzygy
  adjudication and labels.
- **Search.** About 6.9 M nps with the HCE today. Margins are tuned to the
  HCE scale and get retuned in Phase 4.
- **TCEC.** Long time controls and many threads favour accuracy per node
  over raw speed (§1.6, §3.2 evidence). The Swiss runs on the CPU server.

**The axes.**

| Axis | Simpler end | Richer end | Trade-off |
|---|---|---|---|
| Input set | 768 piece-square, mirrored or not | king buckets (few → many); later threat and pawn-pair inputs | data per weight and refresh cost against accuracy per eval. Threat inputs gain at fixed nodes and LTC, roughly neutral at STC |
| King handling | none | mirroring; buckets; refresh caches | each adds refresh triggers and cache memory per thread |
| First-layer width | a few hundred | a few thousand | speed and update cost against accuracy. Elo tracks loss at fixed nodes |
| Body depth | single layer | 1-2 small layers; layer stacks by material | fixed-node gains against speed and SIMD and quantization work |
| Output selection | one output | output buckets / layer stacks | nearly free at inference; rare buckets get little data |
| Activation | CReLU | SCReLU; pairwise; Swish/SwiGLU in small layers | non-linearity and Elo against overflow risk, hand SIMD and sparsity |
| Hidden precision | int16 everywhere | int8 dense layers (VNNI); float small layers | throughput against range, clipping, saturation and reproducibility |
| Quantization | post-training (round, clip) | clamp-in-optimizer; full QAT | accuracy at long time controls against trainer complexity (bullet's QAT **UNVERIFIED**) |
| Sparsity | dense first layer | sparse with NNZ blocks, L1 activation penalty, permutation | speed against extra code and training terms |
| Target and loss | fixed λ, squared error | λ schedule, exponent >2, WDL head | must be judged at the target time control; changes the eval scale, which affects search margins |
| Data per generation | ≈ hundreds of millions | many billions | days of datagen against net size; see §6.6 for what projects used |
| Generations | one big net early | small net first, grow per generation | faster first result and cleaner SPRT steps against more cycles |

**Coupled decisions to settle together.**
- Bucket count against data volume.
- Width against hidden precision against SIMD tier.
- λ schedule against eval scale against the search-margin retune.
- Threat inputs against width against time control.
- Mirroring, buckets and threat accumulators against refresh triggers and
  cache memory at hundreds of threads.

**Originality.** Every distinctive choice (inputs, bucketing, layer shapes,
activations, quantization scheme, file format) goes through the DESIGN.md
§8 screen and is logged in ORIGINALITY.md. Fork's numbers come from Fork's
own reasoning, sweeps and SPRTs, never from another engine.

---

## 10. UNVERIFIED items (this file)

| Item | Why unverified |
|---|---|
| What "dual activation" means (Alexandria 9.x) | Only named in release notes; no opened source or search result defines it |
| Isolated Elo of HalfKP/HalfKA against 768, of mirroring, of pairwise multiplication, of output buckets | No isolated SPRT in the opened sources (loss-only evidence for output buckets) |
| Isolated Elo of pawn-pair and opposed-pawn inputs | Only bundled release results found |
| Minimum data needed for threat inputs, and a positions-per-width rule | No opened source states one |
| How incremental threat deltas are computed (the Yukari approach) | Credited in a PR description; not opened. §1.6's list is Fork reasoning |
| Results of passed-pawn, castling-rights and bishop-pair inputs | Planned in a 2024 blog post; no result found |
| Effect of removing Stockfish's direct PSQT-like shortcut | History doc gives only the change |
| Viridithas "merge king planes", "speculative materialisation" and "separate sum vector" details | Release notes give titles only |
| What bullet's QAT operation (PR #483) does, and how to use it | Empty PR description; not in docs |
| Whether bullet can evaluate a FEN with a float model (PR #178) | Empty PR description; not in docs |
| Stockfish 19's QAT gain | Release names the technique, gives no number |
| PlentyChess 4's "different way of generating training data" | Not described in the notes |
| WDL-head details (Viridithas experiments, Alexandria's WDL loss term) | Not described |
| VNNI on TCEC's EPYC 9754 and 9175F | AMD pages opened list no ISA extensions; KB question still open |
| Eval share of node time; per-thread nps of small against large nets | No measurement in opened sources |
| bullet training throughput on Kaggle T4 or P100 | Not published in opened sources |
| 2025-2026 arXiv NNUE architecture papers | One search found none; absence is not proof |

---

## Sources

Every page opened for this file is listed in [sources.md](sources.md), section "NNUE design concepts, Phase 4 step 1 (nnue-design.md), 2026-10-28".
