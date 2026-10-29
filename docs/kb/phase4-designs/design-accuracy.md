# Phase 4 design proposal: accuracy-first ("AF")

Step 2 of the Phase 4 multi-agent plan (DESIGN.md on main, §5, "Phase 4
multi-agent plan"). One of three independent proposals; this one has the
**accuracy-first** brief: the most accurate evaluation Fork can realistically
feed with its own data and still run, accepting a slower eval where the
accuracy should buy more than the lost depth at TCEC's 30'+3" on 512 threads.

- **Written:** 2026-10-28, from the KB only: `nnue-design.md` (cited as
  "KB §x.y"), `phase4-pipeline.md` ("pipeline §x"), `training-data.md` §2-4,
  `data-policy.md`, `competition.md` (TCEC conditions), and DESIGN.md §5.3, §7,
  §8 on main. Fork's own code was read for two facts (`core/material.hpp`'s
  `game_phase`, 0-24; `score_bounds.hpp`'s `MaxPly` = 250). No engine source,
  no nnue-pytorch code, no web pages were opened, and no other designer's file
  was read.
- **Constants are Fork's own reasoning** (arithmetic, instruction limits,
  cache sizes, data volume). None is taken from an engine. The originality
  screen (DESIGN.md §8, match / no match only) still has to check every one of
  them, and every name in section 9, before anything is built.
- **Estimates are marked *estimate*.** Hardware facts that come from model
  knowledge rather than an opened source (Zen 4 cache sizes and 512-bit
  execution, T4 bandwidth) are marked **UNVERIFIED**. Nothing here was run.
- **Principle:** agents propose, training and SPRT decide. Every choice below
  that can be settled by a cheap measurement says which measurement.

---

## 1. Summary

AF is a **king-region-bucketed, horizontally mirrored piece-square input set
feeding a wide int16 accumulator, a pairwise-product activation, and a small
three-layer integer body that is duplicated per game phase (8 layer stacks)**,
with a staged path to a **compact, target-centric threat-input accumulator**
once the data can feed it. Every knob is sized from Fork's own numbers: king
regions are *fitted to the king-square histogram of Fork's own data* so each
region gets a guaranteed share of the samples; layer stacks are cut at
quantiles of Fork's own `game_phase` distribution; widths are chosen so each
first-layer weight row sees about as much data as B0's rows did. All integer
arithmetic is proven overflow- and saturation-free, so the scalar, AVX2,
AVX-512 and VNNI paths agree bit for bit and the parity test is exact. The
thesis it bets on, and which the bake-off can falsify: Fork's Elo gap to a
faster net **shrinks or reverses as the time control grows**, because the
accuracy gain is per node while the speed gain is per doubling of nodes.

| Part | AF-S (bake-off, step 4) | AF-L (confirmation, first production net) | AF-LT (later generation, ≥ 2.5 B positions) |
|---|---|---|---|
| Piece inputs | 768 per king region (2 colours × 6 types × 64 squares, side-to-move-relative, flipped vertically for Black), **mirrored left-right** so the own king is on files e-h; **B = 4 king regions**, each ≥ 10% of samples | same, **B ≤ 10** regions, each ≥ 3% of samples | as AF-L |
| Threat inputs | none | none | **7,296 target-centric relation features** (target square × target piece × attacker kind), mirrored with the piece inputs, count-valued, own accumulator |
| Training-only inputs | one shared 768 "all regions" factorizer, merged into every region at save | same | same (no threat factorizer) |
| Accumulator | **H = 512** int16 per perspective | **H = 1024** | **H = 768** (H = 1024 trained as the measured alternative) |
| First activation | clamp to [0, 1], then **pairwise product** of the two halves → H/2 values per perspective; both perspectives concatenated, side to move first → **H uint8 values in [0, 127]** | same | piece + threat sums (saturating add), then same |
| Body (per layer stack) | L1: H → 16, int8 weights, sparse kernel; SCReLU; L2: 16 → 32, int16 weights; SCReLU; L3: 32 → 1, int16 weights | same | same |
| Output buckets | **8 layer stacks**, chosen by `game_phase` (0-24) through a 25-entry table cut at the octiles of Fork's own phase histogram | same | same |
| Quantization | piece FT int16 × 255; threats int8 × 255 (widened to int16 when added); L1 int8 × 64; L2, L3 int16 × 8192; biases int32; output (y3 · M) >> 32 | same | same |
| Net file | **3.22 MB** | **15.9 MB** | **17.5 MB** (23.3 MB at H = 1024) |
| Est. nps vs bootstrap (7600X3D, v3) | 0.49-0.67× (*estimate*) | 0.34-0.52× | 0.24-0.46× (H 768) |

AF-S and AF-L are the same code with different constants; the bake-off
implementation *is* the production implementation. AF-LT adds one module
(threat features and their accumulator) on top.

---

## 2. Reasoning for each choice

### 2.1 Piece inputs: king regions with mirroring, fitted to Fork's data

**Choice.** The 768 piece-square set copied once per king region, the region
picked by the perspective's own king, with the board mirrored left-right
whenever that king stands on files a-d (KB §1.4, §1.5).

**Why this and not plain 768 (B0).** The first layer is the only layer that
costs nothing extra per eval when it grows (KB §1.2, §3.1): king-relative
knowledge (shelter, attack on a castled king, endgame king activity) learned
there is free at inference except for refreshes, which a refresh cache makes
cheap (KB §2.4). Plain 768 cannot express "this pawn is good *because* my king
is behind it" except through the small later layers. Measured evidence is
modest but positive (+5.47 ± 3.57 for a few buckets, +23.64 ± 8.91 for more,
KB §1.5, both from one engine and bundled with other changes).

**Why mirroring.** It halves the region map (32 king squares instead of 64)
and so doubles the data per region at almost no cost in strength (KB §1.4:
"hardly measurable"). It also gives Fork an exact test for free: a position
and its left-right mirror must evaluate identically (section 5.6), because
castling rights are not inputs.

**How many regions, and where: fitted, not chosen.** The region map is the
output of a deterministic procedure run on Fork's own data, so its count and
shape follow from data volume rather than from taste:

1. From the training data that passes the training filter, histogram the own
   king's square for every perspective sample, after orienting (vertical flip
   for Black) and mirroring to files e-h: 32 cells.
2. Start with every square as its own region. Repeatedly take the region with
   the smallest share and merge it into the edge-adjacent region with the
   smallest share (ties: same rank first, then lower square index), until every
   region holds at least θ of the samples **and** there are at most B_max
   regions.
3. Freeze the map with the histogram that produced it; it is stored in the
   net file header and in the constants table.

θ and B_max come from the data-per-weight anchor below: **AF-S: θ = 10%,
B_max = 4; AF-L: θ = 3%, B_max = 10.** The expected result is fine regions on
the home ranks, where the king spends most middlegames, and a few large
regions for the rest of the board, where it is mostly in endgames. That is the
usual reasoning (KB §1.5), but here the boundaries are measured.

**Data-per-weight anchor (Fork's own rule).** A first-layer weight row is
touched once per sample in which its feature is active. B0 (768 → 256, 200 M
positions, about 28 active pieces per perspective) gives each row on average
200 M × 2 × 28 / 768 ≈ **14.6 M** touches. AF keeps every region's rows within
a factor of about four of that anchor:

| Net | Data | Rows | Average touches per row | Rows of the smallest region |
|---|---|---|---|---|
| B0 | 0.2 B | 768 | 14.6 M | n/a |
| AF-S | 0.7 B | 768 × 4 | 0.7 B × 2 × 28 / 3,072 ≈ 12.8 M | 0.7 B × 2 × 0.10 × 28 / 768 ≈ 5.1 M |
| AF-L | 1.5 B | 768 × 10 | 1.5 B × 2 × 28 / 7,680 ≈ 10.9 M | 1.5 B × 2 × 0.03 × 28 / 768 ≈ 3.3 M |

The factorizer (KB §1.5) supplies the knowledge shared by all regions, so a
small region only has to learn its difference from the shared rows. The anchor
is a heuristic, not a law (KB §6.6: no source gives a positions-per-neuron
rule); section 4.4's learning curve is the measurement that overrides it.

**Rejected.**
- *Full king-square sets (32 mirrored squares, no regions).* 24,576 rows: at
  1.5 B positions the rarest king squares get a few hundred thousand touches
  per row. Starved (KB §1.2), and a refresh on every king move.
- *Unmirrored regions.* Half the data per region for an asymmetry (castling
  side) the piece inputs already see.
- *The merged-king-plane trick (KB §1.3).* It removes a redundancy only when
  every king square has its own weight set; with regions the own king still
  moves inside a region, so the plane carries information.
- *A hand-drawn region map.* It would be a taste-based constant and an
  originality risk; the fitted map has a recorded derivation.

### 2.2 Threat inputs: yes, staged, and in a compact form of Fork's own

**Why accuracy-first wants them.** They are the largest per-node accuracy gain
on record in the KB: +45.49 ± 2.23 and +33.51 ± 9.35 at fixed nodes, and the
net gain grows with time per move and with threads (+1.78 ± 1.37 and
+9.85 ± 4.24 at LTC, +13.03 ± 4.94 at 4 threads; KB §1.6). TCEC's Swiss is
30'+3" on 512 threads (competition.md), far beyond any of those tests.

**Why not in the first nets.**
- **Data.** The engines that use them train on billions of positions (KB §1.6;
  the minimum is UNVERIFIED). Fork's bake-off will have well under 1 B. An
  undertrained threat net would lose the bake-off for the wrong reason.
- **Speed.** They are "quite a big slowdown" (KB §1.6), and Fork cannot measure
  the multi-thread benefit until Phase 6 adds Lazy SMP.
- **Risk.** Incremental threat deltas are the hardest code in the whole design
  (KB §1.6 pitfalls). They should land on top of a working, parity-tested
  AF-L, not together with it.

So threats come at **AF-LT, the first generation with ≥ 2.5 B own positions**,
with their own SPRTs (section 4.3).

**Fork's encoding: target-centric relations.** The published encoding indexes
every (attacker piece and square, target piece and square) pair: tens of
thousands of indices (KB §1.6; my count for the full pair space is about 90 k
before deduplication). AF instead indexes a relation by **(target square,
target piece kind, attacker kind)**:
- target piece kinds: pawn, knight, bishop, rook, queen of either colour
  (relative to the perspective) = 10; kings are never targets (eval is not
  called in check, and the side not to move cannot be in check; KB §1.6 notes
  the same reasoning);
- target squares: 64 for pieces, 48 for pawns (no pawn on rank 1 or 8):
  8 × 64 + 2 × 48 = **608 target slots**;
- attacker kinds: 6 types × 2 colours (relative) = **12**;
- total **608 × 12 = 7,296 indices**, oriented and mirrored exactly like the
  piece inputs (so a mirror-line crossing is the only refresh trigger).

The attacker's square is dropped on purpose: the piece inputs already say
where every piece is, and the eval-relevant fact is *what is attacked, where,
and by what kind of piece* (hanging pieces, pressure, defence). Consequences:
- **12× fewer indices than the full pair space**, so each threat row sees
  about 2.5 B × 2 × 35 / 7,296 ≈ **24 M** touches at AF-LT's data volume
  (about 35 relations per perspective in a middlegame, *estimate*), above the
  piece rows' anchor. The encoding is sized to Fork's data.
- **A small table** (7,296 × H int8: 5.6 MB at H = 768) instead of tens of MB.
- **Fewer deltas per move.** A slider moving along a line that keeps attacking
  the same target produces no change, where the full pair encoding changes
  both entries.
- **Count-valued.** Each relation adds its row once; two knights attacking the
  same rook add the row twice. That is the natural incremental form (add a row
  per relation that appears, subtract per relation that disappears), and it
  gives the net the attacker count for free.

Whether this beats the full pair encoding in accuracy is unknown; it is a
Fork hypothesis, tested by its SPRT against AF-L, and the full encoding stays
the fallback if it loses at fixed nodes. Its originality (whether some engine
already uses exactly this) goes through the screen like every other choice.

### 2.3 Accumulator width

**AF-S H = 512, AF-L H = 1024, AF-LT H = 768.**
- *Accuracy.* Width is the first lever bullet's docs recommend (KB §3.1), and
  Elo tracked training loss across widths at fixed nodes in one published
  gauntlet (KB §3.1). The pairwise activation (2.4) halves the expensive L1
  input, which is what makes 1024 affordable.
- *Cost.* Update, activation and L1 all scale linearly in H (section 3). At
  1024 the eval costs about 175-215 ns (*estimate*), about as much as the rest
  of a node; doubling again (2048) would push it to about 350-430 ns and the
  nps to roughly a quarter of today's, with a 31 MB first layer.
- *Data.* Width does not change touches per row, but it adds capacity that
  correlated self-play positions can overfit. 1024 is the widest width whose
  first layer fits the data anchor at AF-L's volume with B ≤ 10; wider is a
  growth step (4.3) gated by the learning curve.
- *Cache.* 768 × 10 × 1024 × 2 B = 15.7 MB. Only the rows of the regions in use
  are hot (about 1.5 MB per region per perspective, and only the visited
  piece-squares of those), so the working set is a few MB (*estimate*). That
  matters on TCEC's EPYC 9754, whose L3 is 16 MB per 8-core complex shared by
  16 hardware threads (**UNVERIFIED**, model knowledge).
- *AF-LT drops to 768* so that piece plus threat work costs about what AF-L
  costs plus 40-60% (section 3). The KB notes that engines adopting threats
  cut width (KB §1.6); here the cut is the arithmetic of section 3. H = 1024
  with threats is trained once on the same data as the measured alternative.

H is a multiple of 64 in every variant, so a perspective's accumulator is a
whole number of AVX-512 registers and cache lines (512 × 2 B = 16 lines).

### 2.4 First activation: clamp, then pairwise product

Each perspective's accumulator is clamped to [0, 1] (in integers [0, 255]);
element j of the first half is multiplied by element j of the second half
(KB §3.4). Output: H/2 values per perspective, H in total, as unsigned 8-bit
values in [0, 127].

- **Why.** It halves L1's input count (L1 is the costliest dense layer, KB §3.2),
  and the product of two clipped values is a squared-type non-linearity between
  two different features (KB §3.4), the property that made squared clipped
  activations a clear gain (+35.8 ± 11.6, KB §4.1).
- **It increases sparsity.** A product is zero when either factor is zero,
  which the sparse L1 kernel (3.1) turns into speed.
- **Rejected:** *SCReLU on all 2H values into L1*: twice L1's inputs and
  denser activations, about 2-4× L1's cost for the same H (*estimate*);
  *plain CReLU*: weaker at every width in the published loss study (KB §4.1).

### 2.5 Body: three small integer layers per game-phase stack

**L1 H → 16 (int8), SCReLU, L2 16 → 32 (int16), SCReLU, L3 32 → 1 (int16).**

- **Why a body at all.** Accuracy at fixed nodes: deeper nets gain at fixed
  nodes but are hard to make pay at short time controls (KB §3.2), which is
  exactly the trade this brief accepts. Most knowledge stays in the first layer
  (KB §3.2), so the body is kept small.
- **L1 width 16.** The sparse L1 kernel multiplies one block of 4 input bytes by
  4 × 16 int8 weights = 64 bytes: one AVX-512 register or two AVX2 registers,
  and the 16 int32 outputs are one AVX-512 register or two AVX2 registers. 32
  outputs would double L1's cost, the largest term of the eval after the
  accumulator.
- **L2 width 32.** L2 has only 16 × 32 = 512 multiply-adds per eval
  (about 10 ns with L3, section 3); widening it costs little and gives L3 more
  features. 32 is the width where L3's int32 sum still provably fits with full
  int16 weights (section 5.4).
- **int16, not int8, after L1.** These layers are tiny, so int16 costs nothing
  measurable, and it removes most of the quantization error that grows with
  depth (KB §5.5). 16-bit pairwise multiply-add cannot saturate here (5.4).
- **SCReLU in both small layers.** Squared clipped activations are the
  documented strongest simple choice (KB §4.1). The KB reports one engine
  finding CReLU in one small layer and SCReLU in the next best (KB §3.6), and
  Swish-type gated units as a newer gain (KB §4.5). AF settles this by a
  **training-only loss sweep** (section 4.2), not by argument: SCReLU/SCReLU,
  CReLU/SCReLU and SCReLU/CReLU, each a 1.5 B-position run of AF-S.
- **Integer, not float, small layers.** Float layers avoid fixed-point error
  (KB §3.7) but their results depend on summation order and FMA contraction,
  which differ between AVX2, AVX-512 and scalar builds and between compilers;
  that breaks bench parity unless a canonical order is engineered into every
  path. With int16 weights at scale 8192 the integer error is far below the
  first layer's, and parity stays exact.

**Layer stacks by phase.** All three body layers exist in **8 copies**; the
copy is picked by Fork's own `game_phase` (knights and bishops 1, rooks 2,
queens 4, capped at 24; `core/material.hpp`) through a 25-entry table whose
cut points are the **octiles of the phase histogram of Fork's own training
data**, so each stack gets about 12.5% of the samples (rare-material stacks
are the documented risk, KB §3.3).
- *Why phase rather than piece count.* Two positions with the same number of
  pieces but queens on or off belong to different regimes (king safety,
  passed-pawn races); phase separates them, pawn counts are left to the
  first layer, and the function already exists in Fork.
- *Why 8.* L1 for 8 stacks at H = 1024 is 1024 × 16 × 8 = 128 KB of int8, which
  stays in a 1 MB L2 beside the accumulators; 16 stacks would give each stack
  about 6% of the data and 256 KB of L1 weights; 4 stacks would merge the
  queenless middlegame with the endgame. The choice of 8 against piece count
  is checked in the loss sweep (4.2).
- *Fallback.* If bullet cannot take a custom bucket function (UNVERIFIED,
  pipeline §1.3 lists only `MaterialCount`), use piece-count buckets with
  octile cut points instead; same 8 stacks.

**Rejected.** A direct linear input-to-output shortcut (KB §1.8 records one
being removed elsewhere; the factorizer already gives early training a shared
linear signal); WDL heads (KB §6.1: details UNVERIFIED, and a new output scale
would compound the margin-retune problem of KB §6.3); "dual activation"
(undefined in every opened source, KB §3.6, so not proposed).

### 2.6 Quantization and training-side measures

- **FT int16 at 255** (B0's QA, already justified and screened in DESIGN §5.3).
  bullet's default weight clip of ±1.98 (pipeline §1.3) gives quantized
  weights ≤ 505, so 32 features plus a bias stay below 16,665: half of int16
  (5.1).
- **Threat weights int8 at 255**, clipped to ±0.49 in training. With at most
  256 relations per perspective, the threat accumulator provably fits int16
  (5.2). Storing them as int8 halves their memory traffic (KB §1.6: about 5%
  speed for that alone, at negligible accuracy cost when clipped small).
- **L1 int8 at 64.** ±1.98 × 64 = ±126.7, so bullet's default clip maps onto the
  int8 range with no extra clipping, and with activations ≤ 127 the 16-bit
  pair sums of the non-VNNI instruction cannot saturate (5.3).
- **L2, L3 int16 at 8192.** ±1.98 × 8192 = ±16,220: fine resolution, and half
  the int16 range left as headroom.
- **Rounding, not truncation**, in every `SavedFormat` entry (`.round()`;
  truncation is bullet's default and biases every weight toward zero, KB §5.4).
- **Quantization measured, then QAT only if needed.** Fork's held-out loss tool
  (4.2) computes the loss of the quantized net and of the float net on the
  same held-out positions. If quantization costs more than 0.5% of the loss
  (*Fork's threshold*, chosen as well below the run-to-run noise expected
  between training runs), a short quantization-aware fine-tune follows (KB §5.6;
  bullet's QAT operation is UNVERIFIED, so the fallback is clamping in the
  optimizer, which bullet does natively).
- **Sparsity tracked as a metric** of every run (KB §3.5 pitfall): the converter
  reports the share of non-zero 4-byte L1 input blocks on the held-out set, and
  permutes FT neuron *pairs* so the most often non-zero ones sit together
  (an exact reordering of FT columns and L1 rows; the parity test covers it).
  An activation-sparsity penalty in training (KB §3.5) is optional; bullet
  support UNVERIFIED.

---

## 3. Expected inference cost (x86-64-v3 and v4)

All of this is ***estimate*** from operation counts; Fork's own `bench` decides.
Model machine: the owner's Ryzen 7600X3D (Zen 4, about 4.7 GHz single thread;
1 MB L2 per core, 96 MB L3: **UNVERIFIED** model knowledge). Assumed: two
256-bit memory operations per cycle and about three vector µops per cycle.

### 3.1 Operations per incremental update and per eval (AVX2, H = 1024)

| Step | Operations | Memory touched | Cycles | ns |
|---|---|---|---|---|
| Accumulator update, quiet move (fused: parent + 2 rows → child, per perspective) | per 16 lanes: 3 loads, 2 adds, 1 store; H/16 = 64 chunks × 2 perspectives → 512 memory ops, 256 ALU | parent 2 KB, rows 2 × 2 KB, child 2 KB, per perspective: **16 KB** total | 260-350 | 55-75 |
| Capture / castling | 3 / 4 rows per perspective | +25% / +50% | | |
| King region change (refresh through the cache) | load cached entry, apply the board difference (typically 2-10 pieces), store it back: about 2-3 updates' worth; king moves are about 4-8% of moves in middlegame trees (*estimate*; measure with a bench counter) | +2 KB entry | amortized +5-15% of the update | 6-10 |
| Activation + pairwise | per perspective: 64 loads, 128 clamps, 32 shifts, 32 rounding high multiplies, 16 packs, 8 stores, 8 lane fix-ups → about 580 µops | 4 KB read, 1 KB written | 150-200 | 35-40 |
| Non-zero block scan | per 32 bytes: compare, mask, table lookup of indices → about 160 µops | 1 KB | ~50 | ~10 |
| L1 (sparse, 1 stack) | per non-zero 4-byte block: broadcast, 2 weight loads, 2 byte multiply-adds, 2 widening multiply-adds, 2 adds = 9 µops; 256 blocks × 35-50% non-zero (*estimate*: element density 10-15%, block density 1 − (1 − d)^4) ≈ 100 blocks → ~900 µops | ~6 KB of the stack's 16 KB L1 weights | 250-300 | 55-65 |
| L1 out, L2, L3, output | ~150 µops | ~5 KB | 40-50 | ~10 |
| Evaluator overhead (stack select, scale, clamp) | | | | ~5 |
| **Total per evaluated node** | | | | **175-215** |

Same steps for the other variants: AF-S (H = 512) ≈ **100-120 ns**; B0 (one
256-wide update, a 512-term dot product) ≈ 25 ns.

**Threat accumulator (AF-LT).** Per changed relation and perspective: H int8
weights widened to int16 and added: H/16 widening loads + H/16 adds = 96 µops
at H = 768. About 6-12 relations change per move (*estimate*: the KB's 3-4×
the piece changes for the full pair encoding, KB §1.6, minus the cancellations
of the target-centric form): 12-24 row passes ≈ 1,150-2,300 µops plus the
threat accumulator's own load and store → **75-170 ns at H = 768**, 100-230 ns
at H = 1024. Refresh only when the own king crosses the d/e line (about 1-2%
of moves, *estimate*): about 35 rows, amortized +10-20% of the threat cost.
Adding the two accumulators before the activation: +H/16 saturating adds per
perspective, about 8 ns.

AF-LT (H = 768) per eval: piece work 0.75 × (160-200) + 15 + threats 75-170 +
8 ≈ **218-343 ns**.

### 3.2 From eval cost to nps

Today: 6.9 M nps = 145 ns per node with the bootstrap eval. Model: search work
without eval t_s ≈ 130 ns (*estimate*: 145 ns minus about 15 ns of bootstrap
eval, UNVERIFIED split), evals per node e ≈ 0.85 (*estimate*: qsearch stand-pat
and interior static evals, minus TT-cached evals). nps = 1 / (t_s + e × t_eval).
The low end multiplies t_eval by 1.6 for what the model leaves out (cache
misses on weight rows and refresh entries, lazy walk-backs over several plies).

| Net | t_eval (model) | nps, model | nps, ×1.6 penalty | vs 6.9 M bootstrap |
|---|---|---|---|---|
| B0 | ~25 ns | 6.6 M | 6.2 M | 0.90-0.96× |
| AF-S | 100-120 | 4.7 M | 3.4 M | **0.49-0.67×** |
| AF-L | 175-215 | 3.6 M | 2.4 M | **0.34-0.52×** |
| AF-LT, H 768 | 218-343 | 3.2 M | 1.7 M | **0.24-0.46×** |
| AF-LT, H 1024 | 285-455 | 2.7 M | 1.3 M | 0.19-0.39× |

### 3.3 x86-64-v4 and VNNI

- **AVX-512 on Zen 4 / Zen 4c** executes 512-bit operations as two 256-bit
  halves (**UNVERIFIED**, model knowledge), so throughput per byte barely
  changes. Gains come from half the instruction count, 32 registers (fewer
  passes over a 1024-wide accumulator: 64 AVX2 registers' worth against 32 zmm)
  and a compress instruction for building the non-zero index list (KB §3.5,
  used by Halogen 15). Expected: eval **5-20% faster** than v3 (*estimate*).
  On Intel cores with full-width AVX-512 the update and L1 halve.
- **VNNI** replaces L1's 2 byte multiply-adds + 2 widening multiply-adds + 2
  adds per block with 2 fused instructions (KB §7.2): L1 about 40-55% faster,
  the whole eval 12-20% faster (*estimate*). **AF does not depend on it**:
  section 5.3 proves the non-VNNI path cannot saturate, so both give identical
  integers, and VNNI on TCEC's EPYCs stays UNVERIFIED (KB §7.3).

### 3.4 Memory per thread, and TCEC's 512 threads

| Item | AF-S | AF-L | AF-LT (H 768) |
|---|---|---|---|
| Accumulator stack (MaxPly 250 + 1 plies × 2 perspectives × H × 2 B) | 0.5 MB | 1.0 MB | 0.75 MB + threat stack 0.75 MB |
| Refresh cache (regions × 2 mirror sides × 2 perspectives × (H × 2 B + 12 bitboards)) | 4 × 2 × 2 × 1.1 KB ≈ 18 KB | 10 × 2 × 2 × 2.1 KB ≈ 84 KB | 10 × 2 × 2 × 1.6 KB ≈ 64 KB |
| At 512 threads | ~0.27 GB | ~0.55 GB | ~0.8 GB |
| Shared read-only weights | 3.2 MB | 15.9 MB | 17.5 MB |

Only the plies actually reached are touched, so the hot stack is a few tens of
KB per thread. RAM is no issue (768 GiB). **The risk is the shared L3**: on the
EPYC 9754 two hardware threads share each core's L2 and 16 share an L3 slice
(**UNVERIFIED**). The 7600X3D's 96 MB L3 hides table size that TCEC's slices
will not, so local nps overstates AF-L and AF-LT on TCEC. Section 7 lists the
measurement.

---

## 4. Training plan and Kaggle cost

### 4.1 Throughput model (calibrated by B0's measured rate)

bullet's speed on a T4 is UNVERIFIED (pipeline §9). The sparse first layer's
float weight gathers and gradient scatters dominate, so throughput scales
inversely with the bytes they move per position: about 2 × (active inputs) ×
H × 4 B forward, the same again backward. With about 28 piece inputs and 35
threat relations per perspective (*estimate*):

| Net | Bytes per position (fwd + bwd) | Relative to B0 | Bound at 320 GB/s (T4, UNVERIFIED) | Assumed real (40-70%) |
|---|---|---|---|---|
| B0 | 115 KB | 1× | 2.8 M/s | 1.1-2.0 M/s |
| AF-S | 229 KB | 1/2 | 1.4 M/s | 0.56-0.98 M/s |
| AF-L | 459 KB | 1/4 | 0.70 M/s | 0.28-0.49 M/s |
| AF-LT (768) | 774 KB | 1/6.7 | 0.41 M/s | 0.17-0.29 M/s |

The dense layers (≤ 0.4 MFLOP per position) and the optimizer step (≈ 32 bytes
per parameter per batch: 0.3 GB per step for AF-L's 8.7 M training parameters,
under 1 ms) are small beside that. **Calibration rule:** once K5 measures B0's
real positions per second, AF's rates are B0's divided by the "relative"
column, and this whole table is redone. **Loader risk:** viriformat games are
decoded on Kaggle's 4 cores (pipeline §2.5); threat features add per-position
attack generation in Fork's Rust input type, so K17 must be re-run for AF-LT.

### 4.2 Measurements that need only training (cheap, decide the small choices)

**Held-out loss tool (Fork's own).** A hidden `fork` command reads a held-out
viriformat shard (whole games never trained on: a game-level split, because
positions of one game are correlated), evaluates every position with the
**quantized** net through Fork's inference, and reports the training loss
against the same targets the trainer uses, plus the float model's loss from
R-float (section 5.7). bullet's validation set is "not currently implemented"
(pipeline §1.3), so this is Fork's validation set, and it measures what Fork
actually plays with.

**Sweeps on AF-S (each about 1.5 B positions seen, about 0.4-0.7 GPU h):**
1. small-layer activations: SCReLU/SCReLU, CReLU/SCReLU, SCReLU/CReLU;
2. stack selector: phase octiles against piece-count octiles;
3. regions: B = 1 against B = 4 at H = 512 (does the bake-off data already
   feed regions?);
4. quantized against float loss (is QAT needed?).

Winners by held-out loss, with a fixed-nodes gauntlet (fast games at a small
node budget) where two are within noise. About **2-3 GPU h** in total.

### 4.3 Stages, data and GPU hours

Datagen rates scale with the labelling net's nps at a fixed node budget. With
the KB's 100-300 M positions a day for the bootstrap eval (an *estimate*,
training-data.md §3), the factors of section 3.2 give:

| Stage | Labelled by | New data | Total used | Net trained | Positions seen | GPU h (*estimate*) | Datagen days (*estimate*) |
|---|---|---|---|---|---|---|---|
| G0 | bootstrap search | 0.2 B | 0.2 B | B0 (step 0) | step 0 | step 0 | 1-2 |
| G1 | B0 (≈ 0.9×) | 0.5 B | 0.7 B | sweeps + **AF-S** (bake-off) | 4 × 1.5 B + 6 B | 2-3 + 1.7-3.0 | 2-5 |
| G2 | bake-off winner, small (≈ 0.5-0.65×) | 0.8 B | 1.5 B | **AF-L** (confirmation) | 15 B | 8.5-15 | 5-15 |
| G3 | AF-L (≈ 0.35-0.5×) | 1.0 B | 2.5 B | AF-L retrain; **AF-LT 768**; AF-LT 1024 only if 768 wins | 15 B; 20 B; 20 B | 8.5-15; 19-33; 25-45 | 7-25 |
| G4+ | best net | 1.0-1.5 B each | grows | growth steps below | 20 B | 20-35 each | 10-30 each |

- **Positions seen** are budgets with a stop rule: stop when held-out loss
  improves by less than 0.2% over the last fifth of the run (Fork's rule; the
  budget is then a ceiling, not a target). AF-S's 6 B is about 9 passes over
  0.7 B; AF-L's 15 B is 10 passes over 1.5 B.
- **Kaggle fit.** 30 GPU h a week in ≤ 12 h sessions (training-data.md §2.1):
  G1 fits one session, G2 two, G3's AF-LT about a week of quota. The two T4s of
  one session can run two independent trainings (pipeline §1.2; throughput
  UNVERIFIED, K22), which halves the wall time of the paired runs (sweeps,
  AF-LT 768 against 1024). Every run checkpoints and resumes (pipeline §1.4).
- **Datagen is the binding cost of accuracy-first, not GPU time.** Each
  stronger net labels 1.5-4× more slowly at the same node budget. Mitigation,
  measured rather than assumed: for each generation, keep the *time* per
  position constant (nodes per move proportional to the labelling net's nps),
  and compare held-out loss of AF-S trained on a small slice labelled each way.
  Labels may come from any Fork net (A+), so the fastest net that gives equal
  label quality labels.
- **What to drop.** G0's bootstrap labels are dropped from training once at
  least 1 B newer positions exist (the weak labels then cost more than the
  positions add); rescoring costs about as much CPU per position as new
  datagen, so new games win except for Syzygy-relabelled endgames, which are
  free.
- **Growth steps after AF-LT** (each its own SPRT, in this order of expected
  value per cost): H 768 → 1024 with threats once data ≥ 4 B and the learning
  curve (4.4) shows AF-LT is not data-limited; Swish-type units in the small
  layers (KB §4.5); pawn-pair inputs (KB §1.7) as a second, rarely-changing
  accumulator; finer regions (θ down to 2%) at ≥ 5 B.
- **Lc0 review gate** (data-policy decision 5): G3 crosses 2 B own positions.
  AF neither needs nor assumes Lc0 data; the gate is the owner's decision on
  the measured generation gains.

### 4.4 The data-sufficiency check (learning curve)

Before a bigger net is trained for adoption, train it and the current net at
25%, 50% and 100% of the available data with the same positions-seen budget.
If the bigger net's held-out loss still falls by more than half as much from
50% to 100% as from 25% to 50%, it is data-limited: wait a generation. This
replaces the data-per-weight anchor of 2.1 with a measurement on Fork's own
data. It costs three short runs per decision (about 3-6 GPU h for AF-L).

---

## 5. Integer arithmetic, overflow bounds and parity

Notation: per perspective p (side to move first), F_p the active piece
features (|F_p| ≤ 32, one per piece), R_p the active threat relations, H the
width. Right shifts are arithmetic (floor), which C++20 guarantees for signed
integers and numpy's `>>` matches. Scales below are the exact rationals that
`reference.py` uses; "≈" values are rounded for reading.

### 5.1 Piece accumulator (int16)

acc_p[j] = b0[j] + Σ_{f ∈ F_p} W0[f][j], with W0, b0 = round(255 × w).
- **Bound:** the loader rejects any net with max_j (|b0[j]| + 32 × max_f
  |W0[f][j]|) > 32,767 (B0's rule, unchanged). At bullet's ±1.98 clip:
  505 + 32 × 505 = **16,665**.
- **Intermediate overflow is harmless:** updates use wrapping int16 adds and
  subtracts (SIMD `add/sub` on 16-bit lanes; scalar conversion to int16 is
  modular since C++20). Wrapping arithmetic is exact modulo 2^16, and the final
  value is proven to lie inside int16, so any order of adds and subtracts gives
  the exact value. Incremental and from-scratch therefore agree bit for bit.

### 5.2 Threat accumulator (int16, int8 weights; AF-LT)

thr_p[j] = Σ_{r ∈ R_p} T[idx(r)][j], no bias (the bias lives in acc).
- **Bound on |R_p|:** every relation is (attacker, occupied attacked square);
  a knight or king attacks at most 8 squares, a slider at most the first
  occupied square on each of its at most 8 rays, a pawn 2. With at most 32
  pieces, |R_p| ≤ 32 × 8 = **256**.
- **Bound:** |thr| ≤ 256 × 127 = **32,512** < 32,767, for any int8 weights.
  No loader check is needed beyond the int8 type; wrapping makes intermediate
  states harmless (5.1).
- **Combining:** pre[j] = sat16(acc[j] + thr[j]) (saturating 16-bit add), then
  clamped to [0, 255]. Because 255 < 32,767, clamp(sat16(s)) = clamp(s) for
  every integer s, so this equals the exact int32 sum clamped.

### 5.3 Activation and L1 (uint8 × int8 → int32)

- v[j] = clamp(pre[j], 0, 255). For j < H/2:
  a_p[j] = (v[j] × v[j + H/2] + 256) >> 9 ∈ [0, 127].
  SIMD form: the rounding high multiply of (v[j] << 6) by v[j + H/2]:
  ((64 v_j v_k) + 2^14) >> 15 = (v_j v_k + 256) >> 9 exactly; v[j] << 6 ≤
  16,320 fits int16. Maximum: (65,025 + 256) >> 9 = 127. Scale:
  s_a = 65,025 / 512 ≈ 127.002 per 1.0.
- x = concat(a_stm, a_nstm): H values. For the chosen stack k:
  y1[o] = b1[k][o] + Σ_i x[i] × W1[k][i][o], W1 = round(64 × w), |W1| ≤ 127.
- **No saturation:** the non-VNNI byte multiply-add sums two products into a
  saturating int16: ≤ 2 × 127 × 127 = **32,258** < 32,767. So it never
  saturates, and the AVX2, AVX-512 and VNNI sums are identical integers.
- **int32 sum:** |Σ| ≤ H × 127 × 127 = 16,516,096 at H = 1024. Bias
  b1 = round(s1 × b) with s1 = 64 × s_a ≈ 8,128.1; loader requires |b1| ≤ 2^30.
- **Sparse equals dense:** skipping all-zero 4-byte blocks removes only exact
  zero products, and integer addition is associative, so the sparse kernel's
  result is identical to the dense scalar reference in every order.

### 5.4 SCReLU, L2 and L3 (int16 × int16 → int32)

- c1 = clamp(y1 >> 2, 0, 2,032); q1 = (c1 × c1) >> 11 ∈ [0, 2,016]
  (c1² ≤ 4,129,024 in int32 lanes). Scales: s_c1 = s1 / 4 ≈ 2,032.03;
  s_q1 = s_c1² / 2,048 ≈ 2,016.2.
- y2[o] = b2[k][o] + Σ_{i<16} q1[i] × W2[k][i][o], W2 = round(8,192 × w).
  16-bit pairwise multiply-add: q1 ≥ 0, so its one overflow case (both operands
  −32,768) cannot occur; pair sums ≤ 2 × 2,016 × 32,767 ≈ 1.32 × 10^8.
  **Worst case with any int16 weights:** 16 × 2,016 × 32,767 = **1,056,932,352**;
  loader requires that plus |b2| < 2^31. At the ±1.98 clip: |W2| ≤ 16,220.
- c2 = clamp(y2 >> 13, 0, 2,016); q2 = (c2 × c2) >> 11 ∈ [0, 1,984];
  s_q2 ≈ 2,016.2² / 2,048 ≈ 1,984.9.
- y3 = b3[k] + Σ_{i<32} q2[i] × W3[k][i], W3 = round(8,192 × w).
  **Worst case with any int16 weights:** 32 × 1,984 × 32,767 = **2,080,311,296**
  < 2^31 − 1 = 2,147,483,647. The loader checks the actual
  1,984 × Σ_i |W3[k][i]| + |b3[k]| < 2^31 for every stack. 32 is the widest L2
  for which even saturated int16 weights cannot overflow here.
- **Output:** eval = (y3 × M) >> 32 in int64, M = round(S × 2^32 / s_y3),
  s_y3 = s_q2 × 8,192 ≈ 1.626 × 10^7, S fitted as in B0. With S of a few hundred,
  M ≈ 10^5 and |y3 × M| < 2^48. Then clamp to ±(EvalLimit − 1).

### 5.5 What the loader checks (rejects the net otherwise)

Architecture id, dimensions, region map (32 entries, all < B), phase-stack map
(25 entries, all < 8, non-decreasing), the bounds of 5.1, 5.3 (bias) and 5.4,
and the payload's SHA-256. The loader is a parser, so `fuzz_net_file` (DESIGN
§5.3) covers the new header fields.

### 5.6 Exactness tests (all bit-exact)

- Scalar = AVX2 = AVX-512 = VNNI on randomized and edge inputs: activations at
  0 and 255, weights at ±127 and ±32,767 within the proven bounds, all 32
  pieces, all 256-relation constructions for threats.
- Incremental = from-scratch at every evaluation in debug builds, along random
  lines with captures, castling, en passant, promotions, null moves, king
  region changes, mirror-line crossings and refresh-cache hits and misses;
  threat accumulator checked the same way (KB §1.6 pitfall).
- Colour flip: a position and its colour-flipped twin give the same score from
  the side to move.
- **Horizontal mirror:** a position and its left-right mirror give the same
  score exactly (castling rights are not inputs; the region map, the threat
  index and `game_phase` are all mirror-invariant).
- Sparse = dense L1; permuted net (converter) = unpermuted net.

### 5.7 The trainer-engine parity test (DESIGN §5.3 deliverable 6)

- **F = R-int exactly**, every path, from FEN and incrementally: guaranteed
  by 5.1-5.4 (no saturation anywhere, identical rounding definitions; pmulhrsw
  and the shifts are emulated literally in numpy int64).
- **R-float = T** within float noise: R-float reads `weights.bin` by name,
  including the factorizer, and applies the same merge as the `SavedFormat`
  transform; T is bullet's `eval_raw_output` (pipeline §1.7). For AF-LT, T runs
  Fork's Rust threat input type; whether bullet's sparse input sums repeated
  indices (the count-valued relations) is **UNVERIFIED**, and the parity set
  contains a position with two same-kind attackers on one target to prove it.
  Fallback: a second "count ≥ 2" slot per index (14,592 indices), which the
  engine handles with a per-target counter.
- **R-int within the documented tolerance of T.** `reference.py` computes a
  **per-position interval bound**: each quantized weight is within half a step
  of its float value; the bound propagates through the accumulator (sum over
  the position's actual active features), the clamps (1-Lipschitz), the
  pairwise product (|Δ(uv)| ≤ |Δu| + |Δv| on [0, 1], plus the rounding's half
  step), each layer (Σ|w| × input error + Σ input × half weight step + bias
  half step), the squares (2-Lipschitz on [0, 1]) and the floors of each shift.
  It is a proof per position, tighter than a worst case over all positions,
  and it fails the test if exceeded. The report also gives max and 99th
  percentile of |R-int − T|; a new net whose 99th percentile is more than twice
  its predecessor's is flagged for review (a regression alarm, not a gate).
- **Able to fail:** a corrupted weight, a transposed tensor, a wrong region map
  and a swapped stack must each fail it.

---

## 6. Bake-off version and confirmation version

**AF-S (step 4).** H = 512, B = 4 fitted regions (θ = 10%), pairwise, 8 phase
stacks, 16 → 32 → 1 body, no threats; 3.22 MB; about 0.49-0.67× bootstrap nps
(*estimate*). Trained on the shared bake-off data (G0 + G1, about 0.7 B; or G1
alone if it holds at least 0.5 B, because G0's labels are weak), 6 B positions
seen with the stop rule, the small-layer activation from sweep 4.2.1.

Suggestions to the judge for a fair bake-off (they affect every candidate, not
just this one):
- **Equal positions seen, not equal GPU hours**, so architecture rather than
  training budget is compared.
- **SPRTs at two time controls**: STC and the LTC of the Phase 3 setup (40+0.4).
  The KB's evidence is that eval-for-speed trades flip sign between them (KB
  §1.6, §6.2). AF's thesis predicts its result improves from STC to LTC; a
  candidate that wins STC but whose margin shrinks at LTC is extrapolating the
  wrong way for TCEC, where a move gets about 10^4 times LTC's nodes (512
  threads × about 40 s; *estimate*). Multi-thread checks wait for Phase 6.
- A fixed-nodes gauntlet as a pure accuracy reading beside the SPRTs.

**AF-L (confirmation).** H = 1024, B ≤ 10 fitted regions (θ = 3%), else
identical; 15.9 MB; 0.34-0.52× bootstrap nps. Trained on G1 + G2 (about 1.5 B)
with 15 B positions seen. Adopted only if: the learning curve (4.4) says it is
not data-limited, its held-out loss beats AF-S on the same data, and it wins an
SPRT against AF-S at LTC (gainer bounds, per §5.2's policy). If it loses, AF-S
ships and AF-L waits a generation.

**AF-LT (G3).** H = 768 plus 7,296 threat features; trained on about 2.5 B;
SPRT against AF-L at STC and LTC, and later at multiple threads in Phase 6.

---

## 7. Risks, how each shows up, and when to abandon

| Risk | Shows up as | Response | Abandon when |
|---|---|---|---|
| **Speed loss not repaid** (the central bet) | AF-S loses the bake-off at STC and its margin does not improve at LTC | report to the judge; keep AF's parts as later-generation candidates | AF-S's LTC result has its 95% interval entirely below −5 Elo against the speed-first candidate, **or** its STC-to-LTC trend is flat or adverse |
| Data starvation | learning curve still steep (4.4); held-out loss of AF-L not better than AF-S on the same data; region histogram leaves a region under θ | fewer regions (θ up), stay at AF-S widths, wait for data | AF-L fails its SPRT against AF-S at LTC **and** improves held-out loss by < 1% |
| Speed model wrong | `fork bench` nps well below section 3.2 | profile; check sparsity and refresh counts | AF-L below 1.5 M nps on the 7600X3D (≈ 0.22×): cut H to 768 |
| TCEC cache pressure (shared L3 slices) | per-thread nps falls with thread count faster than for B0 or AF-S | a scaling run in Phase 6 (local 1-12 threads; a many-core cloud machine if the owner approves the cost) | AF-LT's per-thread nps at full core count below half its single-thread nps while AF-L's is not: drop threats or shrink their table |
| Sparsity collapse | non-zero block share above 60% (converter report) | activation penalty, neuron-pair permutation | not alone a reason; it feeds the speed criterion |
| Quantization loss | quantized held-out loss > float by 0.5% or more; parity bound exceeded | QAT fine-tune; rounding check | if QAT cannot bring it under 0.5%: move L1 to int16 weights (slower, exact) |
| Threat deltas wrong or slow | debug incremental check fails; AF-LT eval cost above 343 ns | fix with a failing test first (bugs never wait) | AF-LT fails [0, 5] at LTC **and** gains < +15 Elo at fixed nodes against AF-L |
| Datagen slowdown | positions per day with the AF-L labeller under 80 M | label with AF-S at a time-matched node budget (4.3) | not a reason to abandon the net, only to change the labeller |
| Eval scale against Phase 3 margins | mean \|eval\| on a fixed set differs from the bootstrap's by more than about 20% | output rescale until the margin retune (KB §6.3; CLAUDE.md item 8) | n/a |
| bullet features UNVERIFIED | custom stack selector, pairwise product, repeated sparse indices, Rust input type for threats | fallbacks: piece-count stacks; slice-and-multiply; a "count ≥ 2" slot; check bullet's documented API first | if no route expresses pairwise products: SCReLU on 2H with H halved (rerun the cost table) |
| Implementation size | many parts: regions, mirroring, refresh cache, stacks, sparse L1, threats | build in order: AF-S's parts are AF-L's; threats only after AF-L is parity-clean and adopted | n/a |

---

## 8. Constants

Every value is Fork's own reasoning; each goes through the originality screen
(match / no match only) before its commit, and a match goes to the owner.

| Constant | Value | Reasoning |
|---|---|---|
| Piece inputs per region | 768 | 2 colours × 6 types × 64 squares (the definition, KB §1.1) |
| Mirror rule | own king on files a-d → mirror left-right | halves the region map (KB §1.4); exact mirror test (5.6) |
| Region threshold θ, max regions B_max | AF-S 10%, 4; AF-L 3%, 10 | data anchor of 2.1: smallest region's rows get ≥ 1/4 of B0's average touches at that stage's data volume (5.1 M and 3.3 M against 14.6 M) |
| Region map | fitted (2.1 procedure) | stored in the net header with its histogram |
| Factorizer | one shared 768 set, training only | carries what all regions share; merged at save (KB §1.5) |
| H | AF-S 512, AF-L 1024, AF-LT 768 | 2.3: cost linear in H; 1024 is the widest within the data anchor and a ~200 ns eval; AF-LT trades width for threats; multiples of 64 |
| QA (FT clamp and scale) | 255 | B0's value (DESIGN §5.3); byte range |
| FT weight clip | ±1.98 | bullet's default (pipeline §1.3); gives ≤ 16,665 worst case, half of int16 |
| Max active piece features | 32 | one per piece |
| Threat indices | 7,296 = 608 target slots × 12 attacker kinds | 2.2 derivation: 8 piece kinds × 64 + 2 pawn kinds × 48 squares; 6 types × 2 colours |
| Max relations per perspective | 256 | 32 pieces × at most 8 attacked occupied squares (5.2) |
| Threat weights | int8 at 255, clip ±0.49 | 256 × 127 = 32,512 fits int16 for any weights; ±0.49 × 255 ≈ 125 ≤ 127 |
| Pairwise output | (v_j v_k + 256) >> 9, range [0, 127] | the rounding high multiply with a shift of 6; 127 keeps L1's 16-bit pair sums unsaturated (5.3) |
| L1 width | 16 | one 4-input × 16-output int8 block = 64 bytes = one zmm / two ymm; 16 int32 outputs = one zmm (2.5) |
| L1 weight scale | 64 | ±1.98 × 64 = ±126.7 ≤ 127: bullet's default clip fills int8 exactly |
| Sparse block | 4 bytes | four 8-bit activations per 32-bit lane: the unit of both the VNNI and the two-step byte multiply-add paths |
| L1 → L2 shift, clamp | >> 2, [0, 2,032] | brings y1 (scale ≈ 8,128) to ≈ 2,032 per 1.0, inside int16 with room to square in int32 |
| SCReLU square shift | >> 11 | 2,032² >> 11 = 2,016: keeps the squared value at the same magnitude (≈ 2,016 per 1.0) |
| L2 width | 32 | cheap (512 multiply-adds); the widest for which L3's sum fits int32 with any int16 weights (2.08 × 10^9 < 2^31) |
| L2, L3 weight scale | 8,192 | ±1.98 → ±16,220: fine resolution with half of int16 spare; worst-case sums proven in 5.4 |
| L2 → L3 shift, clamp | >> 13, [0, 2,016] | removes the 8,192 weight scale exactly |
| Output multiplier | M = round(S × 2^32 / s_y3), (y3 × M) >> 32 | deterministic integer rescale; relative error ≈ 5 × 10^-6 |
| S | fitted | as B0: logistic fit of result against score on Fork's data |
| Layer stacks | 8, by `game_phase` octiles | 2.5: ~12.5% of samples each; 128 KB of L1 weights at H 1024 fits L2 |
| Training weight clips (L1, L2, L3) | ±1.98 | bullet's default; all quantized ranges above derive from it |
| Quantization-loss threshold | 0.5% of held-out loss | 2.6: below expected run-to-run noise; triggers QAT |
| Training stop rule | < 0.2% held-out improvement over the last fifth | 4.3: turns positions-seen budgets into ceilings |
| Positions seen | AF-S 6 B, AF-L 15 B, AF-LT 20 B | about 9-10 passes over each stage's data; ceilings under the stop rule |
| Learning-curve rule | 50→100% gain > half of the 25→50% gain ⇒ data-limited | 4.4: a steep curve means more data still helps more than size |
| G0 drop point | once ≥ 1 B newer positions exist | 4.3: weak labels outweighed |
| Bake-off data | G0 + G1 ≈ 0.7 B (or G1 alone if ≥ 0.5 B) | 4.3 |
| Abandon thresholds | −5 Elo (LTC, 95% interval), 1% loss, 1.5 M nps, +15 fixed-node Elo, 60% density, 343 ns | section 7: each is set at a level where the design's premise is clearly false, not marginal |
| Parity regression alarm | 99th percentile > 2× predecessor's | 5.7: catches a quantization regression without a fixed tolerance |
| Datagen time-matching | nodes per move ∝ labeller's nps | 4.3: keeps CPU time per label constant across generations |

---

## 9. Candidate identifiers (for the §8 name check)

None of these has been checked. They go to a throwaway research subagent
(four-engine check, match / no match only) before any code uses them.

- **Types:** `KingRegionMap`, `PhaseStackMap`, `PieceSums` (if the owner keeps
  a Fork name instead of "accumulator"; B0's candidate is `FeatureSums`),
  `ThreatSums`, `ThreatIndex`, `RegionCache` (the refresh cache, avoiding the
  community name "Finny table", KB §2.4), `RegionCacheEntry`, `LayerStack`,
  `SparseBlockList`.
- **Functions:** `fit_king_regions`, `fit_phase_stacks`, `pairwise_clip`,
  `nonzero_blocks`, `sparse_affine`, `square_clip`, `threat_delta`,
  `refresh_threats`, `apply_region_cache`.
- **Files:** `src/eval/nnue/king_regions.hpp`, `phase_stacks.hpp`,
  `threat_features.hpp` / `.cpp`, `layer_stack.hpp`, `sparse_affine.hpp`,
  `region_cache.hpp`; `tools/nnue/fit_regions.py`, `tools/nnue/permute.py`,
  `tools/nnue/bound.py` (the per-position tolerance, if split out of
  `reference.py`); `tools/train/src/threat_input.rs` (Fork's Rust input type).
- **Commands:** `fork heldout` (held-out loss), `fork netstat` (sparsity,
  region and stack histograms).
- **Architecture ids:** `af-s`, `af-l`, `af-lt`.

---

## 10. UNVERIFIED items in this proposal

| Item | Why |
|---|---|
| Every nps, ns and cycle figure | operation-count model, not run |
| Zen 4 cache sizes and 512-bit execution; EPYC 9754's 16 MB L3 per complex | model knowledge, no source opened |
| T4 bandwidth (320 GB/s) and bullet's rate per net | model knowledge; bullet's speed is UNVERIFIED (pipeline §9); calibrated by K5 |
| Datagen positions per day per net | KB estimate scaled by modelled nps |
| Threat relations per position (~35) and changed per move (6-12) | reasoning; measure with a bench counter |
| Non-zero block density 35-50% | reasoning from element density; measure per net |
| Whether bullet takes a custom stack selector, a pairwise product, repeated sparse indices and a custom threat input type | pipeline §1.3 lists input and bucket types but not these; check bullet's documented API at the pin |
| Whether target-centric threats match the full pair encoding's accuracy | Fork hypothesis; AF-LT's SPRT decides |
| The data-per-weight anchor and θ values | heuristic; the learning curve (4.4) overrides it |
| VNNI on TCEC's CPUs | KB §7.3; AF does not depend on it |
