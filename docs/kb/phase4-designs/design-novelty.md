# Phase 4 design N (novelty-first): the XGR net

Step 2 of the Phase 4 multi-agent plan (DESIGN.md on main, §5, "Phase 4
multi-agent plan"; principle: agents propose, training and SPRT decide).
Brief: **novelty-first**, a design that is Fork's own, with at least one
new element that has a concrete, testable reason to gain strength.

- **Written** 2026-10-28 by the novelty-first designer agent, independently
  of the other two designers (no other file in `phase4-designs/` was read).
- **Sources read:** KB `nnue-design.md` (what is already published),
  `data-policy.md`, `training-data.md` §1.8 and §2-4, `originality.md`,
  `phase4-pipeline.md` (bullet and Kaggle facts); DESIGN.md on main §5
  (the plan), §5.3 (step 0: B0 and the pipeline), §6 (decisions log),
  §7 (performance doctrine), §8 (naming); Fork's own `src/eval/` and
  `src/search/` headers and `src/tune/params.hpp` for the eval interface,
  the TT's eval field and the current pruning margins.
- **No engine source was opened**, nor nnue-pytorch's code, and nothing was
  browsed. Every number below comes from Fork's own reasoning (arithmetic,
  cache and register sizes, data volume) or from Fork's own code, and is
  listed with that reasoning in section 8. Every constant still goes
  through the originality screen (match / no match only) before it is
  built.
- **Estimates are marked as estimates.** Nothing here was run. Claims I
  could not confirm are marked **UNVERIFIED**.

---

## 1. Summary

**The XGR net** (eXposure, Gate, Revision) is a single-hidden-layer
perspective network on a standard, data-appropriate base (768 piece-square
inputs, horizontally mirrored, four king regions with a training-only
factoriser, SCReLU, int16 throughout), plus three new elements, each
aimed at the place where a static evaluation inside Fork's alpha-beta
search goes wrong most often: (X) an **exposure plane**, a small set of
per-piece "en prise" inputs (attacked by a cheaper enemy piece, or attacked
and undefended) that is summed from scratch at every evaluation and keeps
no incremental state; (G) a **learned phase gate**, carried in a spare
lane of the accumulator and updated incrementally for free, which blends
two output experts continuously (and tapers two linear "material" lanes)
instead of switching between discrete material buckets; and (R) a
**revision head**, a second output fitted *after* training, on the frozen
integer activations, by Fork's own CPU regression tool, which predicts how
far Fork's search will move this net's static eval, so that the search can
widen or tighten its eval-dependent pruning margins per position. R is
refitted on each new generation's own search data, which only Fork's
pipeline (self-play with the current net, then rescoring) produces. All
three can be switched off independently, each falls back to a standard
choice, and X and R also port to whichever design wins the bake-off.

| Part | Bake-off (XGR-512) | Confirmation (XGR-1024) |
|---|---|---|
| Base inputs | 768 piece-square per perspective (own/enemy × 6 types × 64 squares), board flipped vertically for Black, flipped left-right when the perspective's own king is on files a-d; × 4 own-king regions = **3,072 rows** | same |
| Exposure inputs (X) | own/enemy × 5 non-king types × 64 squares = **640 rows**, same orientation as the base; a piece is active when attacked by a lower-value enemy piece, or attacked and not defended; ≤ 30 active; summed from scratch per eval | same |
| Training-only factorisers | 768 rows (shared by the 4 regions) + 10 rows (exposure: own/enemy × type); merged into the real rows at save | same |
| Accumulator | per perspective: H int16 hidden lanes + 8 int16 side lanes (lane 0 gate, lanes 1-2 linear, 3-7 reserved zero); incremental, lazy, per-ply stack; full refresh on a king-region change or mirror flip | same |
| Hidden width H | **512** | **1,024** |
| Activation | SCReLU: clamp(y, 0, 1)², computed with the multiply-before-square reordering (KB nnue-design.md §4.3) | same |
| Body | none: the 2H activated values (side to move first) feed the output experts directly | same |
| Output | two experts A and B (each 2H → 1, plus a linear lane term), blended by the gate g ∈ [0, 1]: out = o_B + g·(o_A − o_B); no material buckets | same |
| Revision head (R) | fitted after the bake-off on the winning net (any design); not part of the bake-off SPRT | 2H → 1, fitted on the net's own generation data |
| Quantization | hidden and side weights int16 at QA = 255 (clip 0.99 per tensor, so a merged weight ≤ 1.98); expert weights int16 at QB = 64 (clip 1.98); expert biases int32 at QA·QB; gate at 1/255 resolution; revision weights int16 at a power-of-two QR chosen by the fit | same |
| VNNI | not used or needed (no int8 dot products anywhere) | same |
| Net file | **≈ 3.87 MB** | **≈ 7.68 MB** |

**What is new against the published concepts in nnue-design.md**

| Element | Closest published concept (nnue-design.md) | What differs |
|---|---|---|
| X, the exposure plane | §1.6 threat inputs: one input per (attacker, target) pair, own accumulator, updated incrementally, 3-4× the piece-input changes per move | X is **unary** (one bit per piece), encodes a value comparison and a defence count that pairwise features only express through several active inputs together, has ≤ 30 active and typically a few (estimate), and is **stateless**: summed from scratch at each eval, so it needs no incremental deltas, no stack state and no refresh logic. Whether any engine uses such inputs: **UNVERIFIED** (not in nnue-design.md; the screen should check the idea's name and constants) |
| G, the learned phase gate | §3.3 output buckets and layer stacks, picked by a hand-made piece-count rule | a **learned** phase coordinate, computed by an extra accumulator lane at no update cost, **blending** two experts continuously (no eval jump at a bucket boundary, every position trains both experts); the linear lanes resemble §1.8's PSQT-like shortcut, but tapered by the learned gate; optional seeding of the lanes from Fork's bootstrap evaluation |
| R, the revision head | none in nnue-design.md (WDL heads, §6.1, predict the game result, not the search's revision) | a second output **fitted post hoc on frozen integer activations** by a Fork CPU tool, **refitted per generation** on the net's own search scores, used by the search to scale pruning margins and **computed only where it can change a pruning decision** (a borderline band) |

Everything else (perspective inputs, mirroring, king regions with a
factoriser, SCReLU and its reordering trick, int16 quantization, lazy
incremental updates, the score/result blend target) is published practice,
chosen here on Fork's own reasoning.

---

## 2. Reasoning for each choice

### 2.1 Base inputs: mirrored 768 × 4 king regions

- **Why not plain 768 (B0).** It cannot tie piece placement to the king's
  position inside the first layer, where it is free at eval time. Region
  experts are the published cheap way to add it (§1.5; release-note
  evidence of single-digit to low-double-digit gains).
- **Why only 4 regions.** Fork's data is its own and slow to make: about
  100-300 M positions a day (owner estimate, not measured), so 1-2 billion
  positions by the confirmation net. Each region's rows see roughly a
  quarter of the data (less for rare regions); with the factoriser carrying
  the shared part, 4 regions keep every row well fed (section 4.1 counts
  it). Many-bucket or full king-square sets (HalfKA) are rejected for the
  same reason the bullet docs give: data a newcomer does not have.
- **The region map** (after mirroring, so the own king is on files e-h; my
  own reasoning, to be screened): (1) the home square e1 (the king that
  still has its castling options and its full pawn cover); (2) the castled
  corner f1, g1, h1 (both wings land here after mirroring: a c1 king
  mirrors to f1, b1 to g1); (3) the second rank e2-h2 (the king has left
  its cover or made luft); (4) everything from the third rank up (the
  active, endgame king). The first three are where a middlegame king
  spends nearly all its time, so they get the fine distinctions; the
  fourth is one big region because endgame kings walk around and a region
  boundary there would cost refreshes for little gain. **UNVERIFIED** how
  often each region is visited in Fork's data: `bucket-count`-style
  histogram on generation 0-1 data before training (section 7).
- **Mirroring** halves the king-dependent table and makes queen-side and
  king-side castled positions share weights (§1.4). Cost: a refresh when a
  king crosses the d/e line, which is rare.
- **Alternatives rejected:** threat inputs (§1.6) as the *first* own-data
  net: their published fixed-node gain is large, but they are data-hungry,
  memory-bound and complex to update; X is designed as their cheap cousin
  for Fork's data volume. Pawn-pair inputs (§1.7): no isolated evidence;
  a later candidate.

### 2.2 Novel element X: the exposure plane

**Definition (exact; all three implementations must agree, section 5.4).**
For each non-king piece of either colour on square s, with value class
P < N = B < R < Q:
- s is attacked by an enemy piece of a strictly lower class, or
- s is attacked by at least one enemy piece and defended by none of its
  own pieces.
"Attacked" and "defended" mean pseudo-attacks on the real occupancy:
sliders stop at the first piece, pins are ignored, x-rays do not count,
kings count as attackers and defenders, en passant does not count. For a
perspective, the active feature is (own or enemy, type, oriented square),
oriented exactly as the base plane (vertical flip for Black, horizontal
flip when that perspective is mirrored). Kings are never exposed (an
attacked king is check, and Fork does not stand pat in check).

**Mechanism.** The static eval is used where it is least reliable: at the
quiescence stand-pat and at the shallow pruning tests (reverse futility,
futility). The largest static errors there come from pieces that are en
prise: a stand-pat ignores that the side to move must save a piece (or
cannot save two), and a pruning test at depth 1-6 accepts or rejects a node
on an eval that does not know a piece is loose. Piece-square inputs only
reach this through nonlinear combinations of two or more inputs (attacker,
target, and every square on a slider's ray), which one hidden layer of a
few hundred neurons represents poorly. X hands the first layer the
answer directly: one input per loose piece. The stm-first concatenation
tells the net whose move it is, so "my piece hangs and I am to move" and
"his piece hangs and I am to move" are learnable separately. The
published threat-input evidence (§1.6: +33 to +45 Elo at fixed nodes in
two engines) shows that attack relations carry a lot of eval accuracy; X
bets that the part of it that matters most is captured by one bit per
piece, at a fraction of the cost.

**Why stateless (summed from scratch).** Exposure changes are non-local: a
slider move can expose or cover pieces far away, so incremental deltas
need the attack maps before and after anyway. Since the active count is
small (≤ 30, a few on average, estimate), summing the active rows at eval
time costs about what an incremental update would, needs no per-ply state,
no lazy walk-back and no refresh rule, and cannot drift out of sync. The
rows are added inside the activation pass, so the sum never touches
memory as a separate vector (section 3).

**Falsifying experiment (cheap).**
1. Feature statistics on 10 M generation-1 positions (local CPU, minutes):
   the distribution of the active count k and of the main net's residual
   |static − search| split by k = 0 against k ≥ 1. If positions with k ≥ 1
   carry no larger residual than k = 0, X has nothing to fix: stop.
2. Two XGR-512 nets on the same data and steps, with and without X (about
   1-4 T4 hours each, section 4): compare held-out loss overall and on
   k ≥ 1 positions.
3. SPRT at fixed nodes, then STC and LTC. **X is kept only if** the
   fixed-node gain is at least +10 Elo with its 95% interval above zero
   **and** the LTC test passes non-regression [−3, 0] after the speed cost.
   (The threshold is about what X's estimated 20-25% speed cost could
   take back at short time controls; section 3 and the slowdown
   calibration in section 7 refine it.)

**Fallback.** X-lite (only "attacked by an enemy pawn", two shifts per
side, about 5 ns, estimate) if full X gains at fixed nodes but loses after
speed; plain base inputs if X-lite also fails. If the measured mean k is
above 4, the plane can instead be made incremental (the exposure bitboards
stored per ply and diffed), without changing the net.

### 2.3 Novel element G: the learned phase gate and tapered linear lanes

**Definition.** Each input row carries 8 extra int16 side lanes. Lane 0 is
the **gate lane**; lanes 1 and 2 are **linear lanes** for experts A and B.
Per evaluation:
- z = gate_stm + gate_ntm (each perspective's lane 0, bias included), and
  g = clamp(z, 0, 1) in float (clamp(z_q, 0, 255) in integers);
- o_A = w_A · h + c_A + 2·(lin1_stm − lin1_ntm), o_B likewise with w_B, c_B,
  lane 2, where h is the 2H SCReLU vector (stm first);
- out = o_B + g·(o_A − o_B).
The gate is colour-symmetric (a sum over both perspectives); the linear
term is antisymmetric (own view minus the opponent's), so the
colour-flip test of step 0 still holds exactly.

**Mechanism.**
- *Continuous phase.* Material buckets cut the game into hand-made ranges;
  a capture that crosses a boundary makes the eval jump, which the
  quiescence search then sees as a tactical swing that is not on the board.
  A blended output has no boundary.
- *Data.* With K discrete buckets each output weight trains on about 1/K of
  the positions; with the blend every position trains both experts, in
  proportion to g and 1 − g. This matters most for Fork's small early data.
- *A learned phase.* The gate lane is a linear function of the inputs, so it
  can learn what "phase" means for this net (a queen may count more than
  two rooks, pawns may count) instead of a fixed piece count.
- *Linear lanes.* Large material balances (a piece up) must otherwise be
  carried through clipped hidden neurons, which saturate; a linear term
  carries them at full range and leaves the hidden layer for the subtle
  part. Tapering that term by the gate is the network form of the tapered
  piece-square evaluation that Fork's bootstrap eval is built on.
- *Cost.* The gate and linear lanes ride in one 128-bit side vector per row:
  one extra load and add per changed row. The second expert costs one more
  dot product over the 2H activations (about 6% of node time at H = 512 on
  AVX2, section 3).

**Optional seeding (minor, zero inference cost).** Initialize lanes 1-2
from the bootstrap eval's middlegame and endgame per-piece-square values
(divided by the fitted scale S) and lane 0 from Fork's own phase weights
(`PhaseWeight` in `core/material.hpp`, divided so that the two
perspectives' lanes sum to phase / 24), so the net starts as the bootstrap
eval's tapered PST and learns from there. Only the per-piece-square
additive terms of the bootstrap eval can be seeded; its bare-king term is
left out. Done by writing an initial `weights.bin` in bullet's documented
record layout and loading it with `load_weights_from_file`
(phase4-pipeline.md §1.4). Kept only if the loss falls faster in the first
10% of training than from random weights; otherwise dropped.

**Falsifying experiment.** XGR-512 with the gate against XGR-512 with 8
material output buckets instead (same everything else; 1-4 T4 hours):
held-out loss, the gate histogram over the data (collapse to always 0 or
always 1 means one expert is dead weight), then a fixed-node SPRT and an
STC non-regression test.

**Fallback.** G1: keep the gate on the linear lanes only, with a single
nonlinear expert (exactly the cost of one output, plus a few scalar
operations). If G1 also does not beat material buckets on held-out loss,
use material output buckets (published).

### 2.4 Novel element R: the revision head

**Definition.** A second output r = u · h + c_u over the same 2H SCReLU
vector, in centipawns after scaling. It predicts the magnitude by which
Fork's search will revise this net's static eval:
target t = min(|e − s|, 1,024 cp), where e is the net's own integer static
eval of the position and s the score of the search that chose the move in
that position (the stored datagen score, from the side to move's view).

**How it is fitted (Fork's own code, CPU, no trainer change).**
1. After net n is trained, generation n+1 datagen starts with it (DESIGN.md
   §5.3 deliverable 7). From the first ≈ 5 M positions of that data (a
   fixed-seed sample; in-check positions and mate or TB scores removed,
   but tactical positions **kept**, since the search meets them too),
   Fork's tool computes each position's integer activations and e.
2. Ridge regression of t on φ_i = v_i² / QA² (the same features the experts
   read), by the normal equations in double precision (2,049 unknowns at
   H = 1,024; Cholesky solve), on 4 M positions; the ridge strength is
   chosen by the error on the remaining 1 M, over powers of ten. Fixed
   sample, fixed summation order, single-threaded reduction per block:
   reproducible bit for bit.
3. The fitted head is quantized (section 5.2) and written into the net
   file, which gets a new hash; the parity record is extended to it.
4. Refitted for every net on its own generation's data, so its meaning
   stays exactly "how much will *this* net's search revise *this* net's
   eval".

**How the search uses it.** Each eval-dependent margin M (reverse
futility, futility; later razoring and qsearch delta tests) becomes
M · m with m = clamp(r / r̄, 1/2, 2), where r̄ is the mean target over the
fit sample (stored in the net header). The decision needs r only in a
**borderline band**: if eval − 2M already passes the test, or eval − M/2
already fails it, the outcome does not depend on m, so r is not computed.
Inside the band, r is computed (fused with the expert dot products when
the eval is computed at a pruning-candidate node, or with one extra pass
when the eval came from the TT). Fork's TT has no room for r (its int16
eval field already spans ±EvalLimit = 20,000), which is why the band
matters.

**Mechanism.** Pruning margins are a fixed stand-in for the uncertainty of
the static eval. A margin wide enough for volatile positions wastes
pruning in quiet ones; one tight enough for quiet positions prunes wrongly
in volatile ones. A per-position prediction of the revision lets the
search prune harder where the eval is trustworthy and less where it is
not. The head is complementary to a correction of the eval's *mean*
(Fork has none today); it predicts the *size* of the error. It costs no
training time, no Kaggle time and no bullet change, and it attaches to any
single-layer design's frozen accumulator, so it offers its gain to the
bake-off's winner whichever it is.

**Falsifying experiment (offline first, no games).** On the 1 M held-out
positions: Spearman rank correlation ρ between r and |e − s|, against a
baseline linear predictor on six cheap features (active exposure count of
each side, piece count, phase, |e|, side to move's exposure count).
**R is dropped** if ρ < 0.25, or if it beats the baseline by less than
0.05 (then the baseline features, which need no head, are tried in the
search instead). Online: reverse futility with m(r) against constant
margins at STC on gainer bounds [0, 3], then LTC; futility next, one change
per SPRT.

**Fallback.** The head is simply not used (zero inference cost, since it is
computed only on request), or replaced by the baseline predictor.

### 2.5 Width, body, activation

- **H = 512 for the bake-off, 1,024 for confirmation.** Width is the most
  reliable accuracy lever for a single-layer net (Elo tracking loss across
  widths, §3.1). 1,024 is the largest width at which the expert dot product
  needs no mid-sum widening on AVX2: each of AVX2's 8 int32 lanes then sums
  exactly 256 activations, the largest power of two within the provably
  safe count of 260 (section 5.1). Data also caps it: at 1,024 the net has about 4.6 M
  trainable first-layer parameters, which 1-1.5 billion positions feed
  comfortably (section 4.1).
- **Single hidden layer.** Fork's data volume and nps budget argue for it
  (§3.1, §3.2: deeper bodies gain at fixed nodes but are hard to make pay
  at speed), and the novelty budget is spent where the mechanisms are. X,
  G and R are all compatible with a later multi-layer body.
- **SCReLU** over CReLU: the clearest published activation gain for
  single-layer nets (§4.1). Pairwise multiplication is rejected: it pays
  only by cheapening a following dense layer, which this body does not
  have.
- **int16 everywhere, no int8 layers.** With no dense hidden layer there is
  no int8 dot product to speed up, so VNNI is irrelevant: the design is
  equally good on x86-64-v3 and v4, with or without VNNI (UNVERIFIED on
  TCEC's EPYCs, and no longer a question for this design). AVX-512 VNNI's
  16-bit multiply-accumulate could fuse two instructions in the expert dot
  product as an optional speedup only.

### 2.6 Training target

The step 0 pipeline's target unchanged: λ·sigmoid(score / S) + (1 − λ)·result
with squared error, Syzygy-adjudicated results for games that reach 5
pieces, the step 0 filters. The design adds one **optional experiment**
enabled by X: relax the "best move is a capture" filter for captures of an
exposed piece (the net can now see why the score is high). Compared by
held-out loss and a fixed-node SPRT; default off.

---

## 3. Expected inference cost (estimates)

**Assumptions** (all estimates; to be replaced by `fork bench` and
perf-log.md numbers):
- 4.7 GHz sustained clock on the 7600X3D (assumed, UNVERIFIED), about 2.5
  instructions per cycle in these SIMD loops (assumed).
- Rows mostly hit L2 (1 MB per Zen 4 core, AMD figure not re-checked
  here; UNVERIFIED): the rows a search tree touches are a small, hot subset
  of the table.
- Today's 6.9 M nps means about 145 ns per node; about 25 ns of it is the
  bootstrap eval (assumed; profile to confirm), leaving 120 ns of
  search, move generation and make/unmake.
- 85% of nodes evaluate (in-check nodes and TT-eval hits do not; assumed).
  Updates are counted at every node (the lazy walk-back applies an
  unevaluated parent's update anyway when a child evaluates).
- k = 2 active exposure features per perspective on average (assumed;
  measured in experiment 2.2-1).
- 25% of evaluations are at pruning-candidate nodes that also compute r
  (assumed; the band makes the true share smaller).
- 2% of moves cause a king-region or mirror refresh in one perspective
  (assumed; a bench counter measures it).

**Instruction counts** (C = H/16 int16 chunks on AVX2, H/32 on AVX-512):

| Operation | Instructions per chunk | Count |
|---|---|---|
| Quiet-move update, one perspective (fused: load parent, 2 rows, sub, add, store) | 6 | C, plus 6 for the side lanes |
| Activation and experts, one perspective (load accumulator; k exposure rows: load + add; max, min; per expert: load weight, multiply, multiply-add, add) | 3 + 2k + 8 = 15 at k = 2 | C |
| Revision head when fused | 4 | C per perspective |
| Refresh, one perspective (bias + 32 rows, store) | about 66 | C |
| Exposure attack maps (scalar, ISA-independent: about 20 attack-table lookups plus about 30 bit operations, then index extraction) | | about 40-80 ns; 60 ns used below |

**Per-operation time** (ns; instructions / 2.5 / 4.7 GHz):

| | 512 AVX2 | 512 AVX-512 | 1,024 AVX2 | 1,024 AVX-512 |
|---|---|---|---|---|
| Update per move, both perspectives | 396 instr → 34 | 204 → 17 | 780 → 66 | 396 → 34 |
| Activation + 2 experts, both perspectives | 960 → 82 | 480 → 41 | 1,920 → 163 | 960 → 82 |
| Exposure attack maps | 60 | 60 | 60 | 60 |
| Revision (fused, × 25%) | 5.4 | 2.7 | 11 | 5.5 |
| Refresh (180 ns at 512 AVX2, × 2%) | 3.6 | 1.8 | 7.2 | 3.6 |

**Node time and nps** (120 + update + refresh + 0.85 × (attack maps +
activation/experts + revision)):

| | 512 AVX2 | 512 AVX-512 | 1,024 AVX2 | 1,024 AVX-512 |
|---|---|---|---|---|
| ns per node | 283 | 227 | 392 | 283 |
| nps (one thread) | ≈ 3.5 M | ≈ 4.4 M | ≈ 2.6 M | ≈ 3.5 M |
| relative to the bootstrap eval (6.9 M) | ≈ 0.51 | ≈ 0.64 | ≈ 0.37 | ≈ 0.51 |

For scale, the same model gives B0 (768 → 256 CReLU, one output, AVX2)
about 150 ns per node, ≈ 6.7 M nps (≈ 0.97 of the bootstrap): B0's cost is
small next to the search's own 120 ns.

**Where XGR's cost goes** (512 AVX2): the exposure plane (attack maps plus
the fused row adds, 2k × 2 instructions per chunk) is about 70 ns per node,
**about 25% of node time**; the second expert about 18 ns, **about 6.5%**;
the revision head about 2%. The rest is the base net. These shares set the
bars in sections 2.2 and 2.3: X must buy back a 25% slowdown, the gate a
6.5% one.

**Memory touched.**
- Per move: parent accumulator read, 2 rows read (3 for a capture, 4 for
  castling), child written: 4 × 2H bytes per perspective, so 8 KB (512)
  or 16 KB (1,024) for both perspectives, plus 16-byte side-lane reads.
- Per eval: both accumulators (2 or 4 KB), the expert weights (4 or 8 KB,
  hot in L1/L2), 2k exposure rows (1 or 2 KB each; 4 rows at k = 2,
  mostly L2), and the attack tables already used by move generation.
- Weight table: 3.8 MB (512) or 7.6 MB (1,024), inside the 7600X3D's 96 MB
  L3 (DESIGN.md §5 Phase 8 note). TCEC's EPYC L3 per CCD: UNVERIFIED.
- Per thread (Phase 6): the accumulator stack holds MaxPly (250) plies × 2
  perspectives × (H + 8) × 2 bytes = 520 KB (512) or 1.03 MB (1,024); X
  adds nothing (stateless). A refresh cache, if adopted later, would add
  4 regions × 2 mirror sides × 2 perspectives × (2H + 16 + board) bytes,
  about 34 KB per thread at 1,024. Hundreds of threads: a few hundred MB,
  acceptable but to be checked against TCEC's memory (UNVERIFIED).

**Refresh frequency.** Only on a king-region change or a d/e-line crossing,
and only in the moving king's perspective. Estimated at 2% of moves
(assumed above); a refresh cache (§2.4, published) is deferred until the
measured share justifies it.

---

## 4. Training plan and cost on Kaggle

### 4.1 Data volume

- **Bake-off (XGR-512):** the shared bake-off data (step 4 trains every
  candidate on the same positions). I suggest at least **400 M positions
  after filtering**, from generations 0-1: 1.5-4 days of datagen at the
  estimated 100-300 M/day.
  - Rows per perspective: 3,072 base + 640 X; trainable parameters with
    factorisers ≈ (3,072 + 640 + 768 + 10) × 512 ≈ 2.3 M.
  - Base rows: 32 active of 3,072 means an average row is active in about
    400 M × 32 / 3,072 ≈ 4.2 M positions (spread unevenly; the factoriser
    covers the rare ones).
  - X rows: 400 M × 2 / 640 ≈ 1.25 M activations per row on average (k = 2,
    assumed); rare rows (an exposed queen in a corner) lean on the 10
    exposure factor rows.
- **Confirmation (XGR-1024):** **1.0-1.5 billion positions** from
  generations 1-3 (4-15 days of datagen), about 4.6 M trainable
  parameters: about 250 positions per parameter.

### 4.2 GPU hours (estimate, tied to K5's measurement)

- **Model of bullet's cost.** For a sparse single-layer net the first
  layer dominates: per position, each active row is gathered in the
  forward pass and receives a gradient in the backward pass, about
  3 × H × 4 bytes of memory traffic per active row. The dense AdamW step
  (about 2.3 M or 4.6 M weights per batch) is negligible per position.
- **Active rows per position** (both perspectives, pessimistic: factor
  rows as separate rows): 2 × (32 base + 32 factor + 2 X + 2 X-factor)
  = 136. B0: 2 × 32 = 64.
- **Traffic per position:** XGR-512: 136 × 3 × 512 × 4 B ≈ 0.84 MB;
  XGR-1024 ≈ 1.67 MB; B0 (H = 256): 64 × 3 × 256 × 4 B ≈ 0.20 MB.
- **So XGR-512 trains at about 0.24× B0's measured K5 rate** (pessimistic;
  up to about 0.5× if bullet merges factor rows before the gather, which
  is UNVERIFIED), and XGR-1024 at about 0.12-0.25×.
- **Absolute guess:** at an effective 200-300 GB/s on a T4, XGR-512 at
  about 0.25-1.0 M positions/s and XGR-1024 at about 0.12-0.5 M/s. bullet's
  real T4 throughput is UNVERIFIED (nnue-design.md §9); K5 fixes it.
- **Data loading:** viriformat decoding plus the X features in Rust (ray
  loops, about 200-500 ns per position, estimate) gives 2-5 M positions/s
  per loader thread, above the GPU's rate on Kaggle's 4 cores; K17
  measures it.

| Run | Position visits | GPU hours (estimate) | Sessions |
|---|---|---|---|
| XGR-512, bake-off entry | 400 M × 10 passes = 4 B | 1.1-4.4 | 1 |
| Ablations (no X; material buckets instead of G) | 2 × 4 B | 2.2-8.9 | 1 (both GPUs of a T4 x2 session in parallel, if K22 passes) |
| XGR-1024, confirmation | 1.2 B × 10 = 12 B | 6.7-28 | 1-3, chained by checkpoints (phase4-pipeline.md §1.4) |
| Revision fit | none (local CPU) | 0 | n/a |

The bake-off entry and its ablations fit in one week's 30 GPU hours with
room for the other designs if the throughput is near the middle of the
range; the confirmation run takes most of a week at worst.

**Revision fit cost (local CPU, estimate).** 4 M positions × (2H + 1)² / 2
multiply-adds for the normal equations ≈ 8.4 × 10¹² at H = 1,024; at about
100 GFLOP/s in double on 6 cores that is under 3 minutes, less with the
zeros of the SCReLU output skipped. Evaluating 5 M positions with Fork's
inference takes seconds. Not a heavy job in the CLAUDE.md sense, but run
outside datagen anyway.

### 4.3 Custom trainer work

All Fork's own code in `tools/train/` (Rust, against bullet's documented
API at the pinned commit; bullet's code may be read, as an MIT tool):

1. **An input type** implementing bullet's sparse-input trait: the mirrored
   region base plane, the 768-row factoriser, the exposure plane and its
   10-row factoriser, for both perspectives, from bulletformat's
   `ChessBoard` (side-to-move relative). Attacks by Fork-written ray loops
   (no magic tables needed in the trainer). Maximum active per perspective:
   32 + 32 + 30 + 30 = 124. Estimated 300-400 lines.
2. **The graph:** affine `l0` (inputs → H) and affine `s0` (inputs → 3) on
   both perspectives; SCReLU and concatenation (stm first); experts `oa`,
   `ob` (2H → 1); gate = crelu(s0_stm[0] + s0_ntm[0]); linear terms
   2·(s0_stm[k] − s0_ntm[k]); out = o_B + g·(o_A − o_B). Needs node
   addition, subtraction, scaling by a constant, slicing (or three
   one-output affines instead of `s0`), and an elementwise product of two
   one-wide nodes (or `pairwise_mul` over a two-wide concatenation).
   **UNVERIFIED** which of these bullet's graph builder offers at
   `da426a49`; to be read in its code before the spec. If a needed op is
   missing: write it as a bullet custom op (G1 needs the same product, so
   it is no way around a missing op), or fall back to material output
   buckets (no product needed), or, last resort, a small PyTorch trainer
   on Kaggle for the gate experiments only (slower; throughput
   UNVERIFIED).
3. **SavedFormat** with transforms that merge the factor rows into the
   region rows and the exposure factor into the X rows, `.round()` on
   every quantized tensor, per-tensor clips set with
   `set_params_for_weight` (0.99 for `l0`, `s0` and their factors; 1.98
   for the experts).
4. **Optional seeding** (section 2.3): a Python script writes the initial
   `weights.bin` in bullet's documented record layout.
5. **Engine side:** the revision fit tool (C++, reads viriformat shards,
   replays games, runs Fork's inference; about 400 lines) and the
   reference evaluator's additions (section 5.4).

---

## 5. Integer arithmetic, overflow bounds and parity

### 5.1 Layer by layer

Notation: q(w) = round(w × factor) (always `.round()`, never bullet's
default truncation; nnue-design.md §5.4).

1. **Hidden and side lanes (int16, QA = 255).** Training clips each of the
   region tensor and its factor to ±0.99, so a merged weight is at most
   1.98 and q ≤ round(1.98 × 255) = round(504.9) = 505. The same holds for
   the exposure rows and the side lanes, and for the biases.
   - Active rows per perspective: ≤ 32 base (at most 32 pieces, kings
     included) + ≤ 30 exposure (non-king pieces) = 62, plus the bias.
   - |y| ≤ 63 × 505 = **31,815 < 32,767**. All adds are wrapping (`vpaddw`,
     `vpsubw`, never the saturating forms) and the scalar path computes in
     int32 and narrows (modular in C++20), so every intermediate order gives
     the same final value, and the final value cannot wrap.
   - The loader re-checks it per neuron j and per side lane:
     |b_j| + 32·max over base rows |w_j| + 30·max over X rows |w_j| ≤ 32,767,
     and rejects the net otherwise (checked, not assumed, as for B0).
2. **SCReLU and the experts.** v = clamp(y, 0, 255). Expert weights are
   clipped to ±1.98, so q ≤ round(1.98 × 64) = round(126.72) = 127.
   - v·w ≤ 255 × 127 = **32,385 < 32,767**: the 16-bit multiply is exact.
   - Multiply-add of (v·w) by v into int32: each pair ≤ 2 × 32,385 × 255 =
     16,516,350, exact.
   - **Lane rule:** an int32 lane accumulates at most 256 activations
     (256 × 32,385 × 255 = 2,114,092,800 < 2,147,483,647), then is widened
     to int64. At H = 1,024 on AVX2 (2,048 activations over 8 lanes) each
     lane holds exactly 256, so one widening at the end suffices; on
     AVX-512 each lane holds 128. Wider nets widen every 256 per lane. The
     scalar path sums in int64. No path can overflow, so all paths agree.
   - S_k = (int64 sum) / 255 with C++ truncation toward zero (the reference
     must use truncation, not numpy's floor division). |S_k| ≤ 2H × 32,385
     ≈ 6.6 × 10⁷ at H = 1,024.
   - o_k = S_k + c_k + 128 × (lane_k,stm − lane_k,ntm), in QA·QB = 16,320
     units: c_k is int32 at QA·QB; the linear-lane factor 128 = 2 (the
     float multiplier) × 64 (QB) converts QA units to QA·QB units exactly.
     |lane difference| ≤ 63,630, so the term is ≤ 8.2 × 10⁶.
3. **Gate.** z_q = gate_stm + gate_ntm (int32, |z_q| ≤ 63,630); g_q =
   clamp(z_q, 0, 255). out = (o_B × 255 + g_q × (o_A − o_B)) / 255 in
   **int64** (|o_B × 255| ≤ about 2 × 10¹⁰), truncating division.
4. **Final scale.** eval = out × S / 16,320 (S the fitted integer scale,
   int64 product, truncating division), clamped to ±(EvalLimit − 1) =
   ±19,999 as for every evaluator.
5. **Revision head.** The fit produces float u_i (on the target scaled by
   1/1,024) and c. QR is the largest power of two ≤ 64 with
   max|q(u × QR)| ≤ 127, so the step 2 bounds hold unchanged. r_q =
   (Σ v·(v·u_q)) / 255 + q(c × 255 × QR); r_cp = max(0, r_q) × 1,024 /
   (255 × QR). The search's factor is computed in fixed point:
   m64 = clamp(64 × r_cp / r̄, 32, 128), margin × m64 / 64.

### 5.2 Quantization tolerance against the trainer's float model

Following DESIGN.md §5.3 deliverable 6, `reference.py` computes a bound
**per position** from the actual quantized weights and the position's
actual active rows (tighter than a global worst case):
- each rounded weight is off by at most half a step: |Δy_j| ≤ (active rows
  + 1) × 0.5 / 255 in float units;
- the clamp cannot amplify it; the square's slope is at most 2, so
  |Δ(v²)| ≤ 2|Δy| + |Δy|²;
- each expert: |Δo| ≤ Σ|w|·|Δ(v²)| + Σ v²·0.5/64 + 0.5/16,320 (bias) +
  2 × the side-lane rounding + 1/16,320 (truncation);
- the gate: |Δg| ≤ |Δz| + 1/255 (resolution and truncation), so
  |Δout| ≤ |Δo_B| + g·|Δ(o_A − o_B)| + |Δg|·|o_A − o_B|;
- times S, plus the final truncation.
The test fails if any parity position exceeds its bound and reports the
maximum and 99th percentile of |R-int − T| beside it.

### 5.3 What must match (the step 0 test, extended)

1. **Feature parity (new leg, runs first).** For every parity position and
   1 M positions sampled from Fork's data: the active index sets (regions,
   mirroring, exposure) from Fork's C++, from the Rust input type (a CPU-only
   test binary in `tools/train`, no GPU needed) and from `reference.py`
   (exposure computed independently with python-chess's attacker sets) are
   **identical**.
2. **F = R-int exactly** for the main eval, the gate and the revision head,
   on every path (scalar, AVX2, AVX-512, VNNI preset) and both routes (from
   the FEN, and incrementally from a parent).
3. **R-float vs T ≤ 0.01 cp** (T from bullet's `eval_raw_output` on Kaggle,
   which uses the same input type, so X is included).
4. **R-int vs T within the per-position bound** (5.2).
5. **Revision head:** R-int vs the fit tool's float model within its own
   bound (the head is not in bullet, so the fit tool is its "trainer").
6. **Exactness tests** (step 0's list plus): incremental against refresh at
   every eval in debug builds; colour flip exact; left-right mirror exact
   (with no castling rights in the inputs, a position and its mirror give
   the same features in each perspective); worst-case positions (30
   exposed pieces, all lanes near the bound).
7. **The checker can fail:** a corrupted weight, a transposed tensor, and a
   deliberately wrong exposure rule (≤ instead of <) must each fail it.

---

## 6. Bake-off and confirmation versions

**Bake-off entry: XGR-512** (step 4: trained on the same data as the other
candidates, compared by SPRT).
- H = 512, 4 regions mirrored, X, G (two experts), no revision head.
- Why no R in the bake-off: R changes the search, not the eval, and fits
  onto any single-layer net; keeping it out keeps the bake-off a
  comparison of evaluations. After the bake-off R is fitted on the winner,
  whichever design that is.
- Alongside it, two ablation nets trained on the same data and judged on
  held-out loss (and a fixed-node SPRT if the loss difference is
  material): **XGR-512 without X**, and **XGR-512 with 8 material output
  buckets instead of G**. They tell the judge whether the new elements,
  rather than the base, carry the result, and they give the standard
  fallbacks ready-trained.
- Expected cost: ≈ 3.5 M nps on AVX2, ≈ 4.4 M on AVX-512 (estimates,
  section 3); about 1-4 T4 hours per net (section 4).

**Confirmation: XGR-1024**, if XGR-512 wins (or ties the best and its
elements pass their own tests).
- H = 1,024 on 1.0-1.5 billion positions from generations 1-3, with
  whichever of X and G passed; R fitted on generation-n+1 data.
- SPRT against XGR-512 and against the current net, at STC and at LTC
  (the time controls TCEC cares about; the threat-input evidence and
  Viridithas's fixed-node-only gains, §1.6 and §6.2, show that fixed nodes
  alone can mislead).

---

## 7. Risks, how each shows up, and when to abandon

| Risk | How it would show up | Response |
|---|---|---|
| X's speed cost eats its gain at short time controls | fixed-node gain positive, STC neutral or negative (the pattern of §1.6) | judge at LTC as well; X-lite; drop X if LTC also fails |
| X's rows are too sparse to train | low activation counts per row (loader histogram); held-out loss no better on k ≥ 1 positions | exposure factoriser already in; X-lite (fewer rows, more data each); drop |
| Mean k larger than assumed | the bench counter shows mean k > 4 | incremental X (exposure bitboards per ply), same net |
| The gate collapses | gate histogram: nearly all positions at g = 0 or 1 | then it is a learned two-way selector; if held-out loss is no better than material buckets, G1 or buckets |
| The second expert's 6.5% speed cost is not repaid | G2 equal to G1 on loss and fixed nodes | G1 |
| R does not predict the revision | Spearman ρ < 0.25, or baseline features within 0.05 | drop R or use the baseline features |
| R predicts but the search does not gain | RFP-with-m SPRT fails on [0, 3] | keep R unused (zero cost); retry with the Phase 4 margin retune, since m is centred on margins tuned for the bootstrap eval's scale |
| Trainer and engine disagree on features | feature-parity leg fails | fixed before any game; never "within tolerance" |
| bullet lacks a needed graph op | the training program does not build | custom op, G1, or the PyTorch fallback (section 4.3) |
| Accumulator overflow | loader rejects the net; or the debug range log approaches 31,815 | the clip rule makes it impossible; the check guards against a wrong clip setting |
| The estimates in section 3 are badly wrong | measured nps below 0.7 × estimate | profile; X's attack maps first (the largest single item) |
| Training throughput far below estimate | K5 scaled by the section 4.2 factor gives > 12 h for the bake-off entry | fewer passes, or the bulletformat route if decoding is the limit (K17) |
| Eval-scale shift (the blend and the linear lanes change the output size) | mean |eval| on a fixed set differs from B0's (§6.3) | S refit; the Phase 4 margin retune is required anyway |
| Phase 6 memory at hundreds of threads | per-thread stacks of about 1 MB at H = 1,024 | acceptable (estimate); no refresh cache unless measured useful |

**Calibration test for every design (cheap, suggested).** One SPRT of Fork
against itself slowed down by 25% (a busy loop per node) at STC and at
LTC measures what 25% of nps costs in Elo for Fork's search. That turns the
"must buy back its speed cost" bars of sections 2.2-2.3 into numbers
instead of rules of thumb, and helps the judge compare designs of
different speeds.

**When to abandon the design.** XGR stops being a distinct candidate if
(a) X fails its test (section 2.2) and X-lite too, and (b) G does not beat
material buckets on held-out loss and fails non-regression at STC. What
remains is then a standard mirrored-region SCReLU net, which the other
designs cover. R survives regardless: it is a separate, portable
experiment.

---

## 8. Constants

Every value with Fork's own reasoning. All go through the originality
screen (match / no match only) before they are built.

| Constant | Value | Reasoning |
|---|---|---|
| King regions | 4: {e1}, {f1, g1, h1}, {e2-h2}, {ranks 3-8}, after mirroring | home square with castling options; castled corner (both wings after mirroring); king off its cover; active king. Four keeps each region's rows fed at Fork's data volume (section 4.1) and the refresh cache small |
| Mirror rule | flip files when the own king is on files a-d | puts every own king on e-h; the d/e boundary is crossed rarely in the middlegame |
| Base rows | 4 × 768 = 3,072 | regions × piece-square inputs |
| Exposure rows | 2 × 5 × 64 = 640 | own/enemy × non-king types × squares |
| Exposure value classes | P < N = B < R < Q | the usual material ordering; knight and bishop treated as equal so a minor attacked by the other minor counts only if undefended |
| Exposure maximum active | 30 | 32 pieces minus 2 kings |
| Factoriser rows | 768 (base), 10 (exposure: own/enemy × type) | one shared copy of each plane; the exposure factor drops the square, the coarsest grouping that still separates the piece types |
| Side lanes | 8 int16 (3 used: gate, 2 linear) | one 128-bit vector per row: the smallest SIMD unit on both targets |
| Linear-lane multiplier | 2 | with merged weights ≤ 1.98, a lane value per feature reaches 3.96 in sigmoid units (≈ 3.96 × S cp), enough for a queen's material value, which 1.98 alone might not cover at Fork's fitted S; a power of two, so a shift |
| H, bake-off | 512 | a step up from B0's 256 for the bake-off's ≈ 400 M positions (about 170 positions per parameter); 1 KB rows (16 cache lines) and a 1 KB accumulator per perspective, so a fused update keeps the parent, two rows and the child (4 KB) well inside L1 |
| H, confirmation | 1,024 | the largest width whose AVX2 expert dot product needs no mid-sum widening (256 activations per int32 lane; section 5.1); about 250 positions per parameter at 1.2 B positions |
| QA | 255 | B0's value: the largest activation that fits an unsigned byte, keeping step 0's machinery |
| QB | 64 | B0's value; with the 1.98 clip, |q| ≤ 127 keeps v·w within int16 (32,385) |
| Hidden and side clip | ±0.99 per tensor (region, factor, X, X-factor, side) | so that merged weights stay ≤ 1.98, and 63 × 505 = 31,815 < 32,767 |
| Expert clip | ±1.98 | bullet's documented AdamW default (a tool default, not an engine constant), which yields q ≤ 127 at QB = 64 |
| Gate resolution | 1/255 | the gate lane is at QA scale, so clamp(z_q, 0, 255) needs no extra scale; worst rounding effect 0.5/255 of |o_A − o_B| |
| Lane widening interval | 256 activations per int32 lane | each activation adds at most 32,385 × 255 = 8,258,175, so at most 260 fit under 2³¹ − 1 = 2,147,483,647; 256 is the largest power of two within that (256 × 8,258,175 = 2,114,092,800) |
| Revision target clip | 1,024 cp | about twice Fork's largest current eval margins (reverse futility 80 × 6 = 480 cp; futility 100 + 70 × 6 = 520 cp; `src/tune/params.hpp`), so the margin factor's upper end (2) is covered; larger residuals are mostly blunders and would dominate a squared-error fit; a power of two |
| Revision factor range | m ∈ [1/2, 2] (m64 ∈ [32, 128]) | a factor of two either way around the tuned margin limits the damage of a miscalibrated head; tuned later (SPSA on the parameter table) |
| Revision fit sample | 4 M fit + 1 M held-out | about 2,000 positions per unknown at H = 1,024 (2,049 unknowns) for a linear model; small enough for a few minutes of CPU |
| QR | largest power of two ≤ 64 with max|q| ≤ 127 | reuses the expert bounds unchanged |
| Ridge strength | chosen on the held-out 1 M over powers of ten | data-driven, recorded with the net |
| Bake-off data | ≥ 400 M filtered positions, 10 passes | 1.5-4 days of datagen; enough for 2.3 M parameters (section 4.1) |
| Confirmation data | 1.0-1.5 B positions, 10 passes | generations 1-3; fits one week's GPU quota at the middle of the throughput range |
| Assumed k (cost model only) | 2 per perspective | estimate, replaced by measurement (experiment 2.2-1) |
| Thresholds for keeping X | fixed-node gain ≥ +10 Elo with the 95% interval above 0, and LTC [−3, 0] passed | about what a 20-25% nps loss could cost at short time controls (estimate; refined by the calibration test) |
| Thresholds for keeping R | ρ ≥ 0.25 and ≥ 0.05 above the baseline | 0.25: below that the head explains too little rank order to steer margins; 0.05: the head must beat six free features clearly to justify its code |
| λ, S, loss, schedule | the step 0 pipeline's | not design-specific |

---

## 9. Candidate new identifiers (for the name check)

To be handed to the throwaway name-check subagent (DESIGN.md §8) before
any code uses them:

- **Types:** `ExposurePlane`, `PhaseGate`, `SideLanes`, `RevisionHead`,
  `KingRegion`, `XgrNet`, `XgrInputs` (the Rust input type),
  `RevisionFit`.
- **Functions and members:** `exposure_mask`, `exposed_pieces`,
  `king_region`, `mirror_files`, `gate_value`, `revision_estimate`,
  `margin_factor`, `side_lanes_`.
- **Files and tools:** `exposure.hpp` / `exposure.cpp`, `phase_gate.hpp`,
  `revision_head.hpp`, `tools/train/src/xgr_inputs.rs`,
  `tools/nnue/revision_fit` (or a hidden command `fork revfit`),
  `test_exposure.cpp`, `test_revision.cpp`, `tests/nnue/exposure.epd`.
- **Constants:** `ExposureRows`, `RegionCount`, `SideLaneCount`,
  `LinearLaneMultiplier`, `LaneWidenInterval`, `RevisionClipCp`,
  `RevisionFactorMin`, `RevisionFactorMax`.
- **Concept names** worth screening as well, since they would appear in
  docs and the questionnaire: "exposure plane", "phase gate", "revision
  head".
