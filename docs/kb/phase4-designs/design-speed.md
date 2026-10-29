# Phase 4 design proposal: speed-first ("S")

Written 2026-10-28 for step 2 of the Phase 4 multi-agent plan (DESIGN.md
on main, §5, "Phase 4 multi-agent plan"). Brief: **speed-first**. The
cheapest evaluation per node that still clearly beats the bootstrap
evaluation and scales with data, so the search goes deepest.

**Inputs used.** `nnue-design.md` (step 1, the main source),
`phase4-pipeline.md`, `data-policy.md`, `training-data.md` §2-4, and
DESIGN.md §5.3 (B0 and the pipeline), §7 and §8 on main. One local
measurement: the CPU's cache sizes (Windows CIM and WSL `lscpu`,
2026-10-28). No engine source was opened. The other designers' files
were not read. Every number here comes with Fork's own reasoning;
estimates are marked *estimate*, unconfirmed facts **UNVERIFIED**.

---

## 1. Summary

S is B0 with three cheap upgrades and a width set by the cache.
The input stays the 768 piece-square set, but each perspective is
mirrored left to right so its own king always stands on files e-h.
That doubles the data each weight sees, and the only refresh it causes
is a king crossing the d/e line. A two-entry refresh cache per
perspective makes that refresh cheap. There is one hidden layer of
**H = 512** per perspective (bake-off: 256) with squared clipped ReLU,
and **8 output buckets** chosen by piece count. There are no king buckets, no
threat inputs and no second layer. Every kernel is int16 with int32
sums, so the design needs no VNNI and no saturating 8-bit instruction.
Exactness against the scalar path can be proved, not just tested.
The whole first-layer table (768 KB) fits in a 1 MB L2 per core, so the
weights stay core-local even at TCEC's 512 threads. Estimated speed:
about **0.65-0.8× the bootstrap's nps** on AVX2 (*estimate*, §3), against
roughly 0.3-0.5× for designs with deep bodies or threat inputs (by the
same arithmetic). Datagen then produces about 1.3-2.7 times as many positions
per day as with such a net. S is a serious candidate for the playing net
at short and medium time controls. Whatever wins at TCEC, it is the
natural **datagen workhorse**, and the bake-off decides the rest.

| Part | S-512 (confirmation, first playing net) | S-256 (bake-off) |
|---|---|---|
| Inputs | 768 = 2 colours × 6 types × 64 squares per perspective; perspective flip (Black: rank mirror, colours swapped); **horizontal mirror when the perspective's own king is on files a-d** | same |
| Accumulator | 2 × 512 int16 (one per perspective, shared weights), side to move first at eval time; copy-make stack, lazy; **refresh only on a mirror-line crossing**, through a 2-entry cache per perspective | 2 × 256 |
| Body | none: the activated accumulator feeds the output directly (2 × 512 → 1) | 2 × 256 → 1 |
| Activation | SCReLU: clamp(x, 0, 1)², integer clamp to [0, 255] then the "multiply by weight, then by activation" order | same |
| Output buckets | 8, by total piece count through a 33-entry lookup table (start: 4 counts per bucket) | same |
| Quantization | FT weights and biases int16 × QA = 255; output weights int16 × QB = 64 (QB = 128 if the trained output weights allow a ±0.99 clip, §2.6); output bias int32 × QA·QB; final eval = trunc(trunc(Σ/QA) + bias) · S_out / (QA·QB), all in int64 after the SIMD reduction | same |
| Net file size | 768·512·2 + 512·2 + 8·1024·2 + 8·4 = **803,872 bytes** (785 KB) + Fork header | 768·256·2 + 256·2 + 8·512·2 + 8·4 = **401,952 bytes** (393 KB) |
| Hot memory per evaluated quiet node | about 12 KB (two 2 KB accumulators, four 1 KB weight rows, 2 KB output slice, one re-read) | about 6 KB |

---

## 2. Reasoning for each choice

### 2.1 Where the speed goes, and the rule that sets the width

Fork's bootstrap search runs at about 6.9 M nps, which is 145 ns per
node. An NNUE adds per evaluated node:
- an incremental update, which grows with the number of changed inputs
  times H;
- the forward pass, which grows with the body.
Everything else in the node (move generation, TT probe, ordering,
pruning) stays the same. The design rule follows: **make the net's share
of node time small enough that doubling the net would cost more Elo in
speed than it could gain in accuracy, and no smaller.** Shrinking below
that point wins little speed, because the non-eval part of the node
(about 130 ns, *estimate*) dominates. Growing past it pays more in depth
than it earns in accuracy. §2.8 turns this into a measurable criterion.

The second rule is the **cache**. Each changed input reads one weight
row of H int16 values. If the first-layer table stays in the core's L2,
those reads cost about one L2 access per cache line. If it spills to L3
or DRAM, they cost several times that, and at 512 threads the DRAM
traffic is shared by 256 cores. The local Ryzen 7600X3D has 1 MB of L2
per core (measured: `lscpu` reports 6 MiB in 6 instances, 2026-10-28).
TCEC's EPYC 9754 is Zen 4c, and 1 MB of L2 per core is AMD's usual figure
for that core (**UNVERIFIED**: not checked on a primary source here).
The table is 768 × H × 2 bytes:

| H | First-layer table | Share of a 1 MB L2 |
|---|---|---|
| 256 | 384 KB | 38% |
| 384 | 576 KB | 56% |
| **512** | **768 KB** | **75%** |
| 768 | 1,152 KB | 113% (spills) |
| 1024 | 1,536 KB | 150% (spills) |

**H = 512 is the widest table that still leaves a quarter of the L2 for
everything else** (TT lines in flight, history tables, the accumulator
stack). The hot part is smaller still. Rows for pieces on squares they
rarely reach (pawns on ranks 1 and 8 never occur; kings rarely leave
their side) are seldom touched, so the working set is a fraction of 768
KB. That makes 512 the cache ceiling of this design, not a hard wall:
768 is the first width where the whole table cannot fit, and §6
includes it in the confirmation sweep so measurement settles it.

### 2.2 Inputs: plain 768, horizontally mirrored

- **Why not king buckets (yet).** Each bucket multiplies the table: two
  buckets at H = 512 make 1.5 MB, which spills out of L2. Each bucket
  boundary is also a refresh trigger. Each weight also sees about 1/B of
  the data, and Fork's data is all self-generated and scarce in the first
  generations (100-300 M positions a day, owner estimate). Buckets are
  the first growth step once the data is there (§4.3), not a starting
  point.
- **Why mirroring.** It costs no table size (still 768 rows) and makes
  each weight serve two king placements. CPW puts that at "between one
  and two times" more effective data (nnue-design.md §1.4), and
  nnue-pytorch calls the strength difference "hardly measurable" when it
  halves the table. For a data-starved project that is a free data
  multiplier. Its only inference cost is one refresh trigger: the own
  king crossing between files d and e.
- **Mirror side.** Mirror when the perspective's own king (in that
  perspective's orientation) is on files a-d, so the king always ends up
  on e-h. The most common king homes (e1 at the start, g1 after short
  castling) then need no flip. The flip itself costs the same either
  way; the choice must match the trainer's input mapping, which is read
  in bullet's code at the pin (phase4-pipeline.md §1.6), and the parity
  test's R-float-against-T leg catches any mismatch.
- **A free exactness property.** The inputs ignore castling rights, so a
  position and its left-right mirror have identical feature sets in
  both perspectives. Their evaluations must therefore be **bit-
  identical**: a cheap, exact test (§5.5). The cost is that the net
  cannot tell kingside from queenside castling rights, which
  nnue-pytorch reports as hardly measurable.
- **Rejected: threat inputs.** They are the strongest evidence against a
  speed-first design: +45 and +34 Elo at fixed nodes, roughly neutral at
  STC, +2 to +10 at LTC, +13 at four threads (two PR results,
  nnue-design.md §1.6). They cost "quite a big slowdown", three to four
  times as many changed inputs per move, their own accumulator, and
  billions of positions to train. They stay out of S on purpose. §2.8
  explains when that choice should lose, and §7 makes it an abandonment
  criterion.
- **Rejected: pawn-pair inputs.** Cheap at inference, but there is no
  isolated evidence for them (nnue-design.md §1.7 **UNVERIFIED**), and
  they add a second sparse table. They can be revisited after the first
  generations.

### 2.3 Accumulator: copy-make stack, lazy, refresh only at the mirror line

- **Update cost.** A quiet move changes 2 inputs per perspective, a
  capture 3, castling 4 (en passant 3, promotion 2 or 3). With a fused
  update (all adds and subtracts in one pass, the accumulator loaded and
  stored once), a quiet move at H = 512 on AVX2 is 2 perspectives × 32
  chunks × (3 loads, 2 add/sub, 1 store). §3 counts it.
- **Lazy materialization** (already in DESIGN.md §5.3, deliverable 5):
  make records the changed inputs and the accumulator is computed only
  when `static_eval` needs it. Fork already caches the static eval in the
  TT (`searcher.cpp` reuses `hit.eval`), so TT hits skip both the update
  and the forward pass. At 512 threads the shared TT makes such hits more
  common.
- **Refresh triggers.** Only the root (new position) and a mirror-line
  crossing of the perspective's own king. No king-bucket boundaries, so
  ordinary king moves (Kg1-h1, Ke1-f1) update incrementally. Only the
  perspective whose king crossed refreshes; the other updates normally.
- **Refresh cache: two entries per perspective per thread**, one per
  mirror side. Each holds an accumulator plus the 12 piece bitboards it
  was built from. A refresh diffs the cached boards against the current
  ones, applies only the differences, and stores the result back. Size
  per thread at H = 512: 2 perspectives × 2 sides × (1,024 + 96) bytes =
  4,480 bytes. At 512 threads that is 2.3 MB, against tens of megabytes
  for a bucketed design's cache (B buckets × 2 sides × 2 perspectives ×
  2H bytes per thread). An empty entry (bias only, empty boards) is a
  valid start, so there is no fill step. Reset on every net change.
- **Rejected: update in place with undo** (subtract on unmake). It halves
  accumulator traffic but makes unmake do work, and it breaks laziness:
  every make and unmake would have to update. Copy-make with laziness
  does work only on evaluated nodes.
- **Null move** copies (or reuses) the parent's accumulator; only the
  order of the halves flips at eval time.

### 2.4 Body: none

- The activated accumulator feeds one output per bucket. Once the
  accumulator is ready, an eval is a single 2H-element dot product.
- **Why no hidden layer.** The first dense layer is "usually the most
  expensive part of the forward pass" (nnue-design.md §3.2). Making it
  cheap needs int8 weights with `pmaddubsw`, which saturates silently
  (§7.2 there), or VNNI, which is UNVERIFIED on TCEC's CPUs. It also
  needs sparse kernels, neuron permutation and an L1 activation penalty
  in training, which bullet does not do by itself (§5.2, issue #167).
  bullet's own docs say to widen the single layer before adding depth,
  and that deeper nets gain at fixed nodes but struggle to keep that gain
  once the speed loss counts (§3.1-3.2). For a speed-first design at
  Fork's data volumes, that settles it.
- **Rejected: pairwise multiplication** of accumulator halves. In a
  single-layer net it halves the dot product's length but adds a second
  clamp and a multiply per pair. By the µop count of §3 (about 5 against
  7 per 16 inputs) it saves roughly a quarter of the dot product, but it
  is less accurate at equal width (CPW, §3.4 there), and its main point,
  feeding a cheaper hidden layer, does not apply here.

### 2.5 Activation: SCReLU

- SCReLU costs one extra 16-bit multiply per 16 inputs over CReLU: 7 µops
  per chunk instead of 6 in the dot product, so the dot product costs
  about 17% more and the whole net about 9% more (§3).
- In return, the loss study cited in nnue-design.md §4.1 found SCReLU
  worth about a 50% wider layer, and one engine measured +35.8 ± 11.6
  from the switch. A 50% wider CReLU net would cost about 50% more net
  time. **Per unit of eval cost, SCReLU is the best deal on the menu**,
  which is why a speed-first design takes it.
- **Integer form.** v = clamp(acc, 0, QA). First t = v · w (exact in 16
  bits because |w| ≤ 128 and v ≤ 255), then t · v through the 16-bit
  multiply-add into 32-bit lanes (`pmaddwd`, which does not saturate for
  these operand ranges). This is the reordering credited to Lizard in
  nnue-design.md §4.3. The bounds are proved in §5.
- **Rejected: Swish and SwiGLU.** These belong in small hidden layers,
  and S has none.

### 2.6 Quantization: int16 throughout, scales derived from the clip

- **FT: QA = 255.** It is the largest activation that fits an unsigned
  byte, the same as B0, which keeps a later int8 path open. With
  bullet's default AdamW clip of ±1.98 (phase4-pipeline.md §1.3), the
  largest quantized FT value is round(255 × 1.98) = 505. Then
  33 × 505 = 16,665 (bias plus 32 active inputs), so **the accumulator
  provably cannot overflow int16** (§5.1).
- **Output: QB = 64**, derived from the clip. SCReLU's reordering needs
  QA × QB × max|w_out| ≤ 32,767. That gives QB ≤ 32,767 / (255 × 1.98)
  = 64.9, and 64 is the largest power of two below it. A power of two
  is not needed for this layer (no shift happens), but it keeps the
  float-to-int map exact in binary.
- **Optional precision upgrade, inference-free: QB = 128 with a ±0.99
  output clip.** If the first trained nets' output weights stay well
  under 0.99 in magnitude (read from `weights.bin`), clipping them to
  ±0.99 and doubling QB halves the output layer's rounding step at no
  speed cost: 255 × 128 × 0.99 = 32,314 ≤ 32,767. Tighter clipping for
  better quantization has published SPRT gains (+6.8 STC, +8.7 LTC in
  one engine, nnue-design.md §4.3). The analyst (step 7) tests it as a
  pure training change.
- **Rounding, not truncation.** bullet truncates unless `.round()` is
  given (§5.4 there). Fork's `SavedFormat` list must use `.round()` on
  every quantized tensor. The parity test's quantization-loss report
  (§5.4) would show a missing `.round()` as a one-sided error.
- **QAT: not needed for S.** Its value is largest for int8 layers and
  small factors (nnue-design.md §5.6). S has neither, and §5.4 measures
  the remaining loss directly.
- **Rejected: int8 FT storage** (widened to int16 while accumulating).
  It would halve the table, so H = 1024 would fit in L2, but int8 at a
  useful scale needs |w| ≤ 127 / QA_ft. With QA = 255 that is a ±0.5
  clip. A separate smaller FT scale would need a shift before the clamp,
  plus a second set of bounds. Kept as a lever (§4.3) if profiles show
  FT misses at a width the data wants.

### 2.7 Output buckets: 8 by piece count, through a lookup table

- They cost nothing at inference beyond choosing which 2H weights to
  read: 2 KB at H = 512. All 8 slices together are 16 KB, of which only
  the one or two buckets near the current material are hot.
- **Why 8.** There are 31 possible piece counts (2-32). Eight buckets of
  about 4 counts each mean one bucket per two trades, roughly. That is
  fine enough to separate opening, middlegame, simplified middlegame and
  endgame weightings, and coarse enough that each bucket gets about an
  eighth of the data (the output layer has only 2H weights per bucket,
  so even an eighth of 200 M positions is 25 M samples for 1,024
  weights).
- **A 33-entry table, not a formula.** Positions with 5 pieces or fewer
  are adjudicated by Syzygy in datagen (A+), so a bucket of 2-5 pieces
  would get almost no data. Any mapping costs the same through a table.
  The starting map is equal widths ((pieces − 2) / 4, capped at 7). It is
  then checked against the bucket histogram of the first data, and any
  bucket below 2% of positions merges into its neighbour (the table
  repeats an index). The map must match the trainer's bucket function.
  bullet's built-in `MaterialCount` mapping is **UNVERIFIED** (read it at
  the pin), and Fork's training program can supply its own.

### 2.8 Speed, accuracy and time control: when S should win, and when it should lose

**The exchange rate.** Let R(TC) be the Elo Fork gains from doubling its
speed at a given time control. Between two nets A and B at equal data:

  ΔElo(A − B, TC) ≈ ΔElo_fixed_nodes(A − B) + R(TC) × log2(nps_A / nps_B)

The fixed-node term is the accuracy gap. The second term is the speed
gap priced at that time control. This is a first-order model
(*reasoning*), but every term in it can be measured. R(TC) falls as time
grows (diminishing returns of depth), and Lazy SMP lowers it further,
because doubling the threads is worth less than doubling single-thread
speed. The threat-input results fit this pattern: at fixed nodes the
accuracy gain is large, and the speed cost cancels it at STC but not at
LTC or with threads.

**What this means for S at each time control:**
- **Fixed nodes:** S loses to any richer net. Expected and harmless.
- **STC (8+0.08, Fork's SPRT TC):** R is largest. A 2× speed edge is
  worth the most here, so S is at its strongest. Most of Fork's
  development SPRTs run here, and faster games are cheaper to run.
- **LTC (40+0.4) and TCEC (1800+3, 512 threads):** R is smaller, so an
  accuracy gap counts for more. S must stay close to the richer
  candidates at fixed nodes to win here.
- **Many threads (Phase 6):** two effects pull in opposite directions.
  More threads lower R. But per-node memory traffic matters more: 256
  cores share the DRAM bandwidth of a two-socket server, and a net
  whose weights spill out of L2 and L3 competes for it. S keeps its
  whole table in each core's L2, so its nps should scale with threads
  close to the bootstrap's (*reasoning*; measurable only in Phase 6 or
  on a rented many-core machine).

**The measurement S asks for** (cheap, GitHub shards, before the
bake-off): play the bootstrap build against itself at time odds 2:1, at
STC and LTC, about 2,000 games each, giving R_STC and R_LTC directly.
A third, smaller run at 120+1.2 shows the trend toward TCEC. The judge
can then turn fixed-node results and measured nps into a predicted
result at any TC, and check the prediction against the bake-off SPRTs.

**The width criterion (rule 1 of §2.1, made concrete).** Let s be the
net's share of node time. Doubling H multiplies node time by about
(1 + s), which costs R × log2(1 + s) Elo. At H = 512 the estimate is
s ≈ 0.32 (§3), so doubling costs about 0.4 R. Widen only if the fixed-
node gain of the wider net exceeds that. The confirmation sweep (§6)
measures both terms.

**The datagen argument (independent of TCEC).** Datagen plays fixed-node
games, so positions per day are proportional to nps. A net at 0.75× the
bootstrap's nps produces about twice as many positions per day as one
at 0.35×. Data is the binding constraint of strategy A+, and every
generation is produced by the previous generation's best net. So a fast
net speeds up the whole improvement loop, even if a slower net ends up
playing at TCEC. A+ allows any Fork net as the labeller.

---

## 3. Expected inference cost on x86-64-v3 and v4

All of this is *estimate*. Deliverable 5's `fork bench` and perf-log.md
replace it with measurements.

### 3.1 µop counts per evaluated node

Notation: H = width per perspective. One AVX2 chunk is 16 int16 lanes
(256 bits); one AVX-512 chunk is 32.

**Incremental update, both perspectives, fused** (2H/16 = H/8 AVX2
chunks):

| Move kind | Per chunk | AVX2 total | AVX-512 total |
|---|---|---|---|
| quiet (2 rows per perspective) | 3 loads + 2 add/sub + 1 store = 6 | 0.75·H | 0.375·H |
| capture (3 rows) | 4 loads + 3 add/sub + 1 store = 8 | 1.0·H | 0.5·H |
| castling (4 rows) | 5 + 4 + 1 = 10 | 1.25·H | 0.625·H |

**Forward pass** (one 2H dot product, H/8 AVX2 chunks): load
accumulator, max, min, load weight, `mullo`, `madd`, add = 7 µops per
chunk, so 0.875·H (AVX2) or 0.4375·H (AVX-512), plus about 15 for the
horizontal reduction and the scalar tail. With AVX-512 VNNI, `vpdpwssd`
fuses the `madd` and the add, making 6 per chunk (−14% on the dot
product). It is optional and exact, because the 16-bit products cannot
saturate (§5.3).

**Quiet-move total (update + eval), AVX2:** 1.625·H µops.

| H | AVX2 µops | AVX-512 µops | Hot bytes per node (accs + rows + output slice) |
|---|---|---|---|
| 256 | 416 | 208 | about 6 KB |
| 384 | 624 | 312 | about 9 KB |
| 512 | 832 | 416 | about 12 KB |
| 768 | 1,248 | 624 | about 18 KB |
| 1024 | 1,664 | 832 | about 24 KB |

Hot bytes at H = 512: parent accumulator read (2 KB), child write
(2 KB), 4 weight rows (4 × 1 KB), output-bucket slice (2 KB, usually in
L1), accumulator re-read for the eval (2 KB, L1 hit). Only the weight
rows normally come from L2.

### 3.2 From µops to nps (Zen 4, AVX2)

Assumptions (each *estimate* or measured as stated):
- Sustained 3 vector µops per cycle in these loops (range 2-4; Zen 4's
  real figure for this mix is **UNVERIFIED**).
- Clock 4.1 GHz: the maximum clock Windows reports for this CPU
  (`Win32_Processor.MaxClockSpeed` = 4101, 2026-10-28). Boost may be
  higher, which would make the net slightly cheaper.
- +15% on net time for cache misses on weight rows, refreshes and lazy
  walk-back bookkeeping.
- f = 0.8 of nodes need a fresh static eval: not in check, no TT eval
  (**UNVERIFIED** for Fork; a counter in bench measures it).
- The bootstrap eval costs about 15 ns per call (*estimate*; it is a
  75-line from-scratch PST-style eval). So the non-eval node time is
  145 − 0.8 × 15 ≈ 133 ns.

Net time per evaluated node = µops / 3 / 4.1 GHz × 1.15. Node time =
133 + 0.8 × net time.

| H | Net ns per eval | Node ns | Est. nps | × bootstrap | Net share s | Range (2-4 µops/cycle) |
|---|---|---|---|---|---|---|
| 256 | 38.9 | 164 | 6.1 M | 0.88 | 0.19 | 0.81-0.93 |
| 384 | 58.3 | 180 | 5.6 M | 0.81 | 0.26 | 0.71-0.86 |
| **512** | **77.8** | **195** | **5.1 M** | **0.74** | **0.32** | **0.64-0.81** |
| 768 | 116.7 | 226 | 4.4 M | 0.64 | 0.41 | 0.53-0.71 + L2 spill |
| 1024 | 155.6 | 258 | 3.9 M | 0.56 | 0.48 | 0.45-0.64 + L2 spill |

For comparison, by the same arithmetic (*reasoning*, not a claim about
any other design): a net that adds a first dense layer over a
1,024-wide or wider accumulator, or threat inputs with their three to
four times as many changed rows, lands at roughly 0.3-0.5× the
bootstrap. The first Stockfish NNUE roughly halved Stockfish's nps
(CPW, nnue-design.md §7.4).

### 3.3 AVX-512 (x86-64-v4)

- **Zen 4 (the local CPU, and Zen 4c in TCEC's EPYC 9754):** 512-bit
  operations are reported to run as two 256-bit halves (**UNVERIFIED**).
  Then the µops halve but execution cycles barely change. Expected
  1.0-1.2× the AVX2 kernel speed, from fewer instructions and 32
  registers. At H = 512 one perspective is exactly 16 zmm registers, so
  a fused update can keep the whole perspective in registers while it
  streams rows. AVX2's 16 ymm registers hold only half a perspective
  (two passes).
- **Full-width AVX-512 cores** (Zen 5, as in the 9175F of TCEC's GPU
  server, and recent Intel server cores; **UNVERIFIED**): about 1.6-1.9×
  on the net part. On the CPU server it is the Zen 4 case that matters.
- **VNNI:** present locally (`/proc/cpuinfo` lists `avx512_vnni`,
  2026-10-28), UNVERIFIED on TCEC's CPUs. S uses it only for the
  optional `vpdpwssd` dot-product fusion. **Without it S loses about 7%
  of net time and nothing else.**

### 3.4 Refresh frequency

- The only trigger is a perspective's own king crossing the d/e line.
  King moves are a small share of moves in middlegames and more in
  endgames. A guess of 1-3% of updates being crossings is *estimate*,
  and a bench counter (`refreshes per 1,000 updates`) replaces it.
- With the 2-entry cache, a refresh applies only the pieces that changed
  since this side was last cached, typically a handful of rows, not
  the 32 rows of a full rebuild. At 2% of updates costing three times a
  normal update, the overhead is about +4% of update time, about +2% of
  net time. Without the cache the same crossings would cost about +30%
  of update time.

### 3.5 Memory per thread at TCEC scale

- Weights: one shared read-only copy, 786 KB (S-512).
- Accumulator stack: (MaxPly + 1) = 251 entries × 2 KB = 502 KB per
  thread allocated, of which only the plies actually reached are
  touched (about 30-60 KB in a typical search).
- Refresh cache: 4.5 KB per thread.
- 512 threads: about 260 MB of stacks and 2.3 MB of caches, far inside
  TCEC's 320 GiB cap on engine memory (config/tcec.json).

---

## 4. Training plan and cost on Kaggle

S trains on step 0's pipeline unchanged: viriformat shards, bullet at the
pinned commit, Fork's own training program in `tools/train/`, commit runs
of at most 12 hours with checkpoint and resume.

### 4.1 What changes from B0 in the training program

- Input type: the mirrored 768 set with a single king bucket. Either
  bullet's mirrored bucketed input with every king square mapped to bucket 0
  (whether it accepts a one-bucket map is **UNVERIFIED**; read at the
  pin), or a small custom input type in Fork's program.
- `screlu` in place of `crelu`.
- 8 output buckets (bullet's material buckets if their map matches
  Fork's table, otherwise a custom bucket function).
- `.round()` on every quantized `SavedFormat` entry; output-weight clip
  ±1.98 (or ±0.99 for the QB = 128 variant).
- Everything else (target blend λ, eval scale S_out, loss, schedule,
  filters) as step 0 fixes it, then tuned by the step 7 analyst.

### 4.2 GPU hours

bullet's throughput on a T4 is **UNVERIFIED** (K5 and K17 measure it).
For a single-layer net with 32 active inputs per perspective, the GPU
work per position is small, so the 4-core viriformat decode may well be
the limit (phase4-pipeline.md §2.5). The table uses three assumed rates,
R_train. "Passes" is how many times each position is seen.

| Stage | Data | Passes (*estimate*) | Positions seen | GPU h at 0.3 M/s | at 1 M/s | at 3 M/s |
|---|---|---|---|---|---|---|
| Bake-off S-256 on gen-0 data | 200 M | 10 | 2 B | 1.9 | 0.6 | 0.2 |
| S-512 trial on the same data | 200 M | 10 | 2 B | 1.9-3.7 | 0.6-1.1 | 0.2-0.4 |
| Confirmation sweep H = 384 / 512 / 768 (each) | 600 M (gen 0 + gen 1) | 8 | 4.8 B | 4.4-8.9 | 1.3-2.7 | 0.4-0.9 |
| Gen-2 retrain of the winner | 1.5 B | 6 | 9 B | 8.3-17 | 2.5-5 | 0.8-1.7 |
| Gen-3 retrain (or first king-bucket trial) | 3 B | 5 | 15 B | 14-28 | 4.2-8.3 | 1.4-2.8 |

The ranges assume the GPU-bound part grows with H, by up to 2× from 256
to 512. If the loader is the limit, all widths train at the same rate.
Even the pessimistic column fits a 30-hour week, except the gen-3 run
(two chained 12-hour sessions). On T4 x2 two widths can train at once,
one per device (UNVERIFIED, K22). **Training is not S's bottleneck.
Datagen is.**

### 4.3 Data and growth across generations

- **Datagen rate** (*estimate*): positions per day ∝ nps at a fixed node
  count. If the bootstrap delivers about 300 M a day on 10 workers
  (inside the KB's 100-300 M range), then S-512 at 0.74× delivers about
  220 M a day, and a net at 0.35× about 105 M. The first two
  generations then take:

  | Generation | Size | With S-512 | With a 0.35× net |
  |---|---|---|---|
  | gen 1 | 500 M | about 2.3 days | about 4.8 days |
  | gen 2 | 1 B | about 4.5 days | about 9.5 days |

- **Growth path**, each step SPRTed at LTC (not only STC, per §2.8), and
  taken only when the data volume supports it:
  1. Gen 0 (bootstrap labels, about 200 M): S-256 (bake-off) and S-512.
  2. Gen 1 (about 500 M, S-labelled): confirmation sweep H ∈ {384, 512,
     768}; the winner by the §2.8 criterion becomes the playing net.
  3. Gen 2+ (1-2 B): training-only gains first, since they are free at
     inference: λ schedule, loss exponent, the QB = 128 clip, longer
     schedules.
  4. At about 2 B positions: **two king buckets, mirrored** (own king on
     its first two ranks, or anywhere else), with a factorizer in
     training. Its refresh trigger is a king leaving or returning to
     the back two ranks, rare in middlegames. It doubles the table, so it
     is tried at H = 384 (1.15 MB, a slight L2 spill) and at H = 512
     (1.5 MB). Adopted only if the LTC SPRT pays for the spill.
  5. Speed levers if a profile shows the need: int8 FT storage (§2.6),
     the VNNI dot path, the in-register AVX-512 update.
- This path never needs a second accumulator, a dense layer or int8
  activations, so step 5's implementation stays one kernel family for
  every generation.

---

## 5. Integer arithmetic, overflow bounds and parity

Symbols: QA = 255, QB = 64 (or 128 with the ±0.99 clip), n ≤ 32 active
inputs per perspective, H = 512 (all bounds below are stated for H, and
hold for every H ≤ 1024).

### 5.1 First layer (int16)

- Wq = round(QA · w), Bq = round(QA · b). With |w|, |b| ≤ 1.98:
  |Wq|, |Bq| ≤ round(504.9) = 505.
- acc_P[i] = Bq[i] + Σ_{f active in P} Wq[f][i]. Bound:
  |acc| ≤ 505 + 32 × 505 = 16,665 < 32,767. **Proved by the clip**, and
  the loader re-checks it per net: for every i,
  |Bq[i]| + 32 · max_f |Wq[f][i]| ≤ 32,767 (B0's rule, unchanged).
- **Incremental updates wrap safely.** SIMD 16-bit adds wrap modulo
  2^16, and C++20 defines conversion to a signed type as modular. Any
  order of adds and subtracts (for example a capture's add before its
  subtracts) therefore ends at the exact sum whenever the final value is
  in range, which the bound guarantees. The scalar reference does the
  same arithmetic with explicit int16 wrapping, so the two paths are
  equal by construction.

### 5.2 Activation

- v_i = clamp(acc_i, 0, 255), an int16 in [0, 255]. Identical in every
  path (max and min are exact).

### 5.3 Output (int16 products, int32 lanes, int64 tail)

- Oq = round(QB · o); the loader rejects |Oq| > 128 = floor(32,767 /
  255). With the ±1.98 clip and QB = 64, |Oq| ≤ 127.
- t_i = v_i · Oq_b[i]: |t| ≤ 255 × 128 = 32,640 ≤ 32,767, **exact in
  16-bit `mullo`** (no wrap).
- p_i = t_i · v_i: |p| ≤ 32,640 × 255 = 8,323,200. `pmaddwd` adds two
  such products per 32-bit lane: |pair| ≤ 16,646,400, exact. It
  saturates only when both operand pairs are −32,768, which cannot
  happen because v ≥ 0 and |t| ≤ 32,640.
- **Lane bound.** An int32 lane that accumulates K products stays exact
  if K × 8,323,200 ≤ 2,147,483,647, so **K ≤ 258**. With r accumulator
  registers, K = 2H / (8r) on AVX2 and 2H / (16r) on AVX-512. With one
  register, AVX2 is safe for H ≤ 1,032 and AVX-512 for H ≤ 2,064. The
  kernel uses r ≥ 2 anyway, to hide latency. The scalar reference
  accumulates in int64, so its sum is the same integer whenever no lane
  overflows, which the bound guarantees. A `static_assert` ties H, r and
  the lane width to K ≤ 258.
- **Tail (shared scalar code for every path):**
  - Σ = horizontal sum of the lanes, in int64; |Σ| ≤ 2H × 8,323,200 ≈
    8.5 × 10^9 at H = 512.
  - y = trunc(Σ / QA) + Cq_b, where Cq = round(QA · QB · c), an int32
    with |Cq| ≤ 32,314 at QB = 64.
  - eval = trunc(y · S_out / (QA · QB)) in int64, then clamped to
    ±(EvalLimit − 1). S_out is the fitted integer eval scale. With
    S_out ≤ 2,048 and |y| ≤ 3.4 × 10^7, the product stays below
    7 × 10^10, far inside int64.
- Every SIMD path produces the same Σ (integer addition is associative
  when nothing overflows), and the tail is one shared function, so
  **scalar, AVX2, AVX-512 and VNNI agree bit for bit by proof**. The
  `nnue_parity` ctest then confirms it.

### 5.4 Parity with the trainer: a tolerance that is mostly proved

The four legs of DESIGN.md §5.3, deliverable 6, apply unchanged. S adds
one more reference value that makes the quantization tolerance tight:

- **Rq, the dequantized-weights float model.** `reference.py`
  quantizes the float checkpoint (`weights.bin`) itself, independently
  of the converter, then runs the float forward pass in float64 with the
  dequantized weights (Wq/QA, Oq/QB, Cq/(QA·QB)).
- **R-int against Rq: proved within 2 cp.** The accumulator equals
  QA × (the dequantized float sum) exactly. The clamp and the square are
  exact on that grid. So Σ / (QA² · QB) equals Rq's pre-bias output
  exactly, and the only differences are the two truncations: less than 1
  unit of y, then less than 1 cp after scaling. So
  |R-int − S_out · Rq| < S_out / (QA · QB) + 1 < 2 cp for any
  S_out < 16,320. **This is a proof, not a fitted tolerance.** It holds
  because S has no layer after the accumulator except the output.
- **Rq against R-float: the quantization loss, computed exactly per
  position.** It is the effect of weight rounding alone, and the
  reference computes it in float64 rather than bounding it. The test
  reports its maximum and 99th percentile beside each net. Two alarms,
  starting values set at the first net and recorded in the net registry:
  p99 above 5 cp or max above 25 cp (*estimate*; a missing `.round()`
  or a too-coarse QB shows up here as a one-sided shift).
- **The gate:** for every parity position,
  |R-int − T| ≤ 2 cp + |S_out · (Rq − R-float)| + 0.01 cp. The first
  term is proved, the second is computed exactly for that position, and
  the third is the float-noise bound of R-float against T. A converter
  bug, a transposed tensor or a wrong mirror convention breaks the
  first or third term by far more than these margins. The deliberate
  corrupted-weight and transposed-tensor cases must fail it.
- Why this is better than a worst-case propagated bound: a strict worst
  case over 33 rounded FT weights and about 1,000 output terms grows
  linearly with width, and at H = 512 it comes to hundreds of
  centipawns, which is useless as a test. Rq makes that slack
  unnecessary.

### 5.5 Exactness tests specific to S

- **Left-right mirror invariance:** a position and its horizontal mirror
  give identical evals, exactly (§2.2). Run over the parity set and
  random positions.
- **Colour-flip invariance:** a position and its colour-flipped twin give
  identical evals from the side to move's view, exactly (as for B0).
- **Refresh against scratch:** in debug builds, after every refresh
  through the cache, the result equals a from-scratch rebuild. This is
  part of the existing incremental-against-scratch check at every
  evaluation.
- **Crossing lines:** test game lines that walk a king back and forth
  across the d/e line, with captures in between, so cached entries go
  stale and must be diffed. Include castling queenside (the king lands
  on c1, which triggers a mirror flip) and kingside.
- **Range logging:** a debug counter of the maximum |acc| and maximum
  |lane| over bench and the parity set, reported with each net (the
  bounds hold by proof; the log shows the real headroom).

---

## 6. Bake-off and confirmation versions

### 6.1 Bake-off: S-256

- 768 mirrored → 2 × 256 SCReLU → 8 output buckets; 393 KB.
- Trained on the shared bake-off dataset with the same schedule as the
  other candidates.
- **It is B0 plus exactly three changes** (SCReLU, mirroring with the
  refresh cache, output buckets). An optional ladder of three cheap
  SPRTs on the GitHub shards (B0 → +SCReLU → +buckets → +mirror) shows
  what each change is worth, which helps the analyst later. It is not
  required for the bake-off.
- **What it is compared on** (the §2.8 exchange rate makes these
  consistent):
  1. against B0 at STC, gainer bounds (sanity: it must win);
  2. against the other candidates' small versions at **STC and LTC**;
  3. a fixed-node match as a diagnostic, not a gate, to split each
     result into its accuracy and speed parts;
  4. `fork bench` nps of every candidate on the same machine.
- Size ratio: S-256 is half the width of S-512, with a quarter of the
  hot weight bytes of a 1,024-wide design. If the other designs' small
  versions are scaled down by a similar factor, the bake-off compares
  like with like.

### 6.2 Confirmation: S-512, with a width sweep

- 768 mirrored → 2 × 512 SCReLU → 8 output buckets; 785 KB; on gen-0 +
  gen-1 data (about 600 M positions or more).
- Trained alongside H = 384 and H = 768 (cheap, §4.2). The winner is
  chosen by LTC SPRT, with the §2.8 criterion as the explanation: the
  wider net must gain more at fixed nodes than R_LTC × log2(1 + s)
  costs it.
- Confirmed only if it passes the parity test, beats the bootstrap and
  S-256 by SPRT, and its measured nps is within the §3 range (at least
  0.6× the bootstrap at H = 512). Below that, the speed premise needs
  rethinking before the comparison means anything.

---

## 7. Risks, how each would show up, and when to abandon S

| Risk | How it shows up in measurements | Response |
|---|---|---|
| **Accuracy ceiling**: a single-layer 768 net plateaus while richer nets keep gaining | The fixed-node gap to the best rich candidate grows with each generation; the LTC SPRT against it fails | Take growth steps 3-4 (§4.3); if they do not close it, S yields the playing slot (below) |
| **Speed estimate wrong** (µop throughput, misses) | S-512 bench nps below 0.6× the bootstrap | Profile (perf counters if WSL exposes them, UNVERIFIED; otherwise A/B with `bench/ab.py` at H = 384 and 512 with the same random weights); drop to H = 384 if the L2 knee is earlier than computed |
| **L2 rule wrong** (no knee at the L2 boundary) | nps against H, measured with random weights, is smooth through 512 → 768 | Good news: widen freely by the §2.8 criterion |
| **Refresh rate higher than expected** (endgames) | the bench counter shows more than 5% of updates are refreshes, or the cache hit diff is large | Larger cache (several boards per side), or measure whether mirroring pays at all (one SPRT without it) |
| **Mirror convention mismatch** with the trainer | R-float against T fails on positions with a king on files a-d | Fix the mapping; the parity test blocks games until then |
| **Output bucket starvation** | Bucket histogram: a bucket below 2% of positions; that bucket's loss stays high | Merge buckets through the table (§2.7) |
| **Eval scale mismatch** with Phase 3's margins | Mean absolute eval over a fixed set differs from the bootstrap's by more than about 20% | Rescale S_out to match until the Phase 4 margin retune (nnue-design.md §6.3) |
| **Quantization loss** larger than expected | The §5.4 alarms: p99 above 5 cp or max above 25 cp | Check `.round()`; try the QB = 128 clip; QAT is the last resort |
| **TCEC thread scaling unmeasurable locally** | Only 6 cores here; the cache argument of §2.8 stays an argument | A rented many-core run in Phase 6 before the TCEC net is chosen; until then the argument is weighted as a hypothesis, not evidence |
| **Data feedback loop**: a fast but blind net labels its own blind spots | Generation gains shrink (the A+ review gate: two generations under about 10 Elo) | Common to every design; rescoring with a richer net is allowed by A+ and would help S's data too |

**When to abandon S, in two levels:**
1. **As the TCEC playing net**, if any of these hold:
   - at confirmation size and equal data, a richer candidate wins the LTC
     SPRT against the best S width;
   - the measured R_LTC is below about 10 Elo per doubling, which would
     mean speed buys little at long time controls, so S's main asset
     is weak exactly where TCEC plays (threshold *estimate*);
   - two growth steps in a row (§4.3) fail to close a fixed-node gap that
     the exchange rate says is decisive at TCEC.
2. **Entirely** (including as the datagen net), if S-512's measured nps
   is not clearly better than the winning candidate's (under 1.3×),
   because then it has neither accuracy nor a speed advantage to offer.

---

## 8. Constants

Every value with Fork's reasoning. All go through the originality
screen (match / no match only) before their commit.

| Constant | Value | Reasoning |
|---|---|---|
| Input count | 768 | 2 colours × 6 piece types × 64 squares: the full piece-square set (B0's). |
| Mirror rule | flip files when the perspective's own king is on files a-d | Only half of the king positions need weights; e-h kept unflipped so the start position and the usual castled positions need no flip (§2.2). Must equal the trainer's mapping. |
| King buckets | 1 (none) | Table size and data per weight (§2.1-2.2); first growth step at about 2 B positions. |
| H (confirmation, first playing net) | 512 | Widest table (768 × H × 2 bytes = 768 KB) that leaves a quarter of a 1 MB L2 free (§2.1); estimated net share of node time 0.32 (§3.2). |
| H (bake-off) | 256 | Half the confirmation width; equals B0, so the bake-off version differs from B0 only in the three upgrades (§6.1). |
| H sweep | 384, 512, 768 | One step below, the cache ceiling, and the first width that spills L2 (§6.2). |
| L2 budget share | 75% of a 1 MB L2 | One quarter left for TT lines in flight, history tables and the accumulator stack (*reasoning*; the knee is measured, §7). |
| L2 per core | 1 MB | Measured locally (`lscpu`: 6 MiB, 6 instances, 2026-10-28); TCEC's Zen 4c: **UNVERIFIED**. |
| QA | 255 | Largest unsigned-byte activation; with the 1.98 clip the accumulator bound is 16,665 < 32,767 (§5.1). |
| QB | 64 | Largest power of two with QA × QB × 1.98 ≤ 32,767 (64.9 → 64), so SCReLU's v·w product is exact in int16 (§2.6). |
| QB (variant) | 128 with output clip ±0.99 | 255 × 128 × 0.99 = 32,314 ≤ 32,767; halves the output rounding step if trained weights fit (§2.6). |
| Weight clip | ±1.98 (bullet's AdamW default) | All bounds of §5 are derived from it; keeping the trainer default removes a configuration risk. |
| Loader bound, FT | \|Bq[i]\| + 32 · max_f \|Wq[f][i]\| ≤ 32,767 | No legal position has more than 32 pieces, so no input set can overflow the accumulator (B0's rule). |
| Loader bound, output | \|Oq\| ≤ 128 | floor(32,767 / 255): keeps t = v · w exact in 16 bits (§5.3). |
| Lane product limit | K ≤ 258 products per int32 lane | floor(2,147,483,647 / 8,323,200); `static_assert` over H, the register count and the lane width (§5.3). |
| Output buckets | 8 | 31 piece counts at about 4 per bucket; each bucket still gets about an eighth of the data for only 2H weights (§2.7). |
| Bucket map | 33-entry table, start (pieces − 2) / 4 capped at 7; buckets under 2% of positions merged | Syzygy adjudication leaves almost no data at 5 pieces or fewer (§2.7). The 2% floor is about 4 M positions in a 200 M generation, against 1,024 weights per bucket (*reasoning*). |
| Refresh-cache entries | 2 per perspective per thread (one per mirror side) | Mirroring is the only refresh trigger; 4.5 KB per thread at H = 512 (§2.3). |
| Accumulator alignment | 64 bytes | Cache line (DESIGN.md §7); also 512-bit load alignment. |
| S_out (eval scale) | fitted | As B0: logistic fit of result against score on the training generation's data; rescaled to match the previous net's mean absolute eval until the margin retune (§7). |
| Quantization-loss alarms | p99 > 5 cp, max > 25 cp | Starting values (*estimate*), fixed at the first net from its measured distribution and recorded in the net registry (§5.4). |
| Parity bound, R-int against Rq | < 2 cp | Proved: two truncations, below 1 unit of y and then below 1 cp after scaling (§5.4). |
| Exchange-rate calibration | 2:1 time odds, about 2,000 games each at 8+0.08 and 40+0.4, plus a smaller run at 120+1.2 | Fork's existing STC and LTC; the third run shows the trend toward TCEC's 1800+3 (§2.8). |
| Widening criterion | widen only if the fixed-node gain > R_LTC × log2(1 + s) | First-order exchange-rate model (§2.8). |
| Abandon thresholds | R_LTC < about 10 Elo per doubling; S-512 nps under 1.3× the winner; nps under 0.6× the bootstrap at H = 512 | §6.2, §7 (*estimates*, revisited with the calibration data). |
| Training passes | 10 (gen 0), 8, 6, 5 as data grows | *Estimate* for the GPU budget only (§4.2); the real schedule is step 0's then the analyst's. |
| Growth-step data volumes | sweep at about 600 M; king buckets at about 2 B | *Estimate*: about a week of datagen per step at S-512's rate (§4.3). |

---

## 9. Candidate new identifiers (need the §8 name check)

B0's names (`FeatureSums`, `FeatureStack`, `NetFile`, `NetHeader`,
`netcheck`, `nnue_parity`, `net_format`, `feature_sums`, `output_layer`
and the rest) are already queued for the check and are reused, not
repeated here. New for S:

| Name | Kind | Purpose |
|---|---|---|
| `MirroredSquares` | type | the mirrored 768 input set: feature index for (perspective, piece, square, king half) |
| `mirrored_squares.hpp` / `.cpp` | files | that input set |
| `king_half` | function | which half (a-d or e-h) a perspective's own king is on |
| `needs_flip` | function | whether a perspective's squares are flipped left to right |
| `KingSideCache` | type | the 2-entry refresh cache per perspective (accumulator plus boards) |
| `king_side_cache.hpp` / `.cpp` | files | that cache |
| `refresh_from_cache` | function | diff a cached entry against the board and apply the differences |
| `FeatureDelta` | type | inputs added and removed by one move, both perspectives (the lazy record) |
| `apply_delta` | function | the fused update kernel |
| `squared_clip_dot` | function | the SCReLU output kernel (v · w, then · v, into int32 lanes) |
| `finish_eval` | function | the shared scalar tail (int64 reduce, divide, bias, scale, clamp) |
| `PieceCountBucket` | constant table | the 33-entry piece count → output bucket map |
| `bucket_for` | function | looks a position's bucket up |
| `MaxLaneProducts` | constant | the 258 bound of §5.3, in the `static_assert` |
| `refresh_count` | bench counter | refreshes per 1,000 updates |
| `nnue_mirror`, `nnue_refresh` | ctest names | §5.5's mirror-invariance and refresh tests |
| `tools/nnue/quant_loss.py` | file | Rq and the quantization-loss report (could live inside `reference.py` instead) |
| `tools/time_odds.sh` | file | the 2:1 time-odds calibration matches of §2.8 |

"SCReLU", "refresh", "bucket" and "accumulator" are field vocabulary
(nnue-design.md; DESIGN.md §8 keeps domain terms). The compound names
above still get the check.

---

## UNVERIFIED items in this proposal

| Item | Why |
|---|---|
| 1 MB L2 per core on TCEC's EPYC 9754 (Zen 4c) | Not checked on an AMD primary source; the local value is measured |
| Zen 4 runs 512-bit operations as two 256-bit halves; Zen 5 at full width | Not checked on a primary source; affects only the v4 speed estimate |
| VNNI on TCEC's CPUs | Open KB question; S does not depend on it |
| 3 vector µops per cycle, 15 ns bootstrap eval, f = 0.8 | Estimates feeding §3.2; replaced by `fork bench` and counters at deliverable 5 |
| bullet T4 throughput; viriformat decode rate on 4 cores | K5 and K17 measure them |
| bullet's mirrored-input convention and one-bucket support; `MaterialCount` mapping | Read in bullet's code at the pin (allowed: MIT tool) |
| R(TC) values for Fork | The calibration matches of §2.8 measure them |
| Refresh frequency (1-3% of updates) | A bench counter measures it |
