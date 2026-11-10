# Idea 53: pawn-structure-class output experts (design, not adopted)

Status: **design for the owner's review, 2026-11-09 (owner's order of the same
day); one decision taken the same evening (below). Nothing here is queued or
built.** Every constant below is
either justified from a cited file or marked a placeholder to be set by
measurement; names are listed at the end for the screens, which have not run.

Sources read: docs/ideas.md idea 53; docs/research/phase4-think-tank/
phase-c-synthesis.md R26 and phase-b-specialists.md W2 (with B13's verdict and
§3.5 ruling); docs/nets.md (architecture 8, S512+PP and its retrains);
src/eval/nnue/accumulator.cpp (`phase_bucket`, the arch-8 output),
src/eval/nnue/net_file.hpp (format version 2), src/core/material.hpp
(`game_phase`), tools/nnue/s512pp.json, tools/train/src/main.rs (`Picker`,
`bucket`); DESIGN.md Testing setup ("Which test a candidate gets", 2026-11-09)
and the decisions log of 2026-11-09 (the speed price).

**The owner's decision (2026-11-09, about 8 PM EST):** "Idea 53's 2e-5
stop-loss and calibration's 30% offline kill become diagnostic only." So the
probe's 2e-5 line is **reported, never a gate**: the probe still ranks the
class maps and picks the one Stage B trains (a selection among candidates,
not a pass/fail), and whether any map clears 2e-5 with its interval
excluding 0 is reported with the ranking; if none does, the owner is told,
and the idea still goes on to Stage B with the best-ranked map, whose
fixed-node screen decides (the 2026-11-09 testing rule: offline metrics are
diagnostics). §5.1 and §7 are amended accordingly.

## 1. What it is

S512+PP (architecture 8, the default network family since 2026-11-06) reads
its output through one of 8 linear heads picked by game phase:
`out_weights[8][2 * 512]` (int16), `out_bias[8]`, the bucket
`net.phase_table[game_phase(pos)]` (a 25-entry table, tools/nnue/s512pp.json,
S512r2's octiles), applied to the squared clipped accumulator of both
perspectives (`squared_sum`, accumulator.cpp). That is a hard-gated mixture of
experts over one shared representation (W2's reading). Idea 53 changes or
extends the gate: each position's head is chosen by a **pawn-structure class**
as well as (or instead of) phase, so each class gets its own readout of the
same accumulator. Idea 53 is one family of R26's candidate gatings (R26: "phase
x queens, imbalance class, pawn class, opposite castling"); this design keeps to
pawn-structure gates, as the owner's order names idea 53.

Why it might pay (ideas.md 53; W2): capacity on the output side costs almost
no work per node, every input-side capacity attempt failed on speed (H-512,
XGR, AF-S, S512+X; W2 "Why Fork"), and pawn links' +32.67 STC (nets.md) says
pawn structure carries knowledge search does not reach. Expected value: R26
**+2 (0 to +6)** (synthesis table), B13 +1 to +6. Both are model estimates.

What it will not fix: the structure-class *outcome* biases the think tank
measured in Fork's games (C's E2: one wing, at most 4 pawns, pure opposite
bishops overrated by 4.5-8 score points at STC and LTC) are nearly absent in
the training labels (E2's 20k-node "data" column: −1.5 to −2.3). A head
trained on those labels learns the labels' calibration, not the games'. That
is the structure-class calibration's job (structure-class-calibration.md);
the two are complementary, and the calibration is refitted after this one if
both land.

## 2. The classes

### 2.1 Requirements

1. **Cheap:** computed from the two pawn bitboards (and, for 2-D maps, the
   phase already computed), with shifts, ANDs, ORs and popcounts only; no
   loop over pawns, no table larger than a few bytes.
2. **Well-defined for both perspectives.** One bucket selects the head for
   the concatenated [side to move, other side] vector, so a class must be
   either colour-symmetric (the same for both colours, e.g. "some side has a
   passed pawn") or expressed relative to the side to move (e.g. "only the
   side to move has a passed pawn"). Never "White has ...".
3. **Invariant under the left-right mirror** S-512 applies to its inputs: a
   class must not distinguish the queenside from the kingside (so "all pawns
   on one wing" is a class, "all pawns on the queenside" is not).
4. **Computable identically** in the trainer (Rust, from its `Board`), the
   Python reference (tools/nnue/reference.py) and the engine (C++), checked
   by the parity test.

### 2.2 Primitive features (Fork's own definitions; placeholders where marked)

Notation: `W`, `B` the white and black pawn bitboards, `P = W | B`;
`north`/`south` shift one rank toward rank 8/1; `fill_n`/`fill_s` the
north/south fills (the bitboard ORed with its shifts by 8, 16, 32);
`files(x)` = the 8-bit set of files holding a bit of `x`; `adj(f)` the
adjacent files of a file set (shift left and right within the byte, masked).

| feature | definition | values |
|---|---|---|
| `n` | `popcount(P)` | 0-16 |
| `rams` | `popcount(north(W) & B)`: a black pawn directly in front of a white pawn | 0-8 |
| `passer(W)` | `W & ~fill_s(south(B | east(B) | west(B)))` non-empty: a white pawn with no black pawn ahead of it on its own or an adjacent file; mirror for Black | bool per side |
| `one_wing` | `P` non-empty and `files(P)` lies within files a-d or within e-h | bool |
| `sym_files` | `files(W) == files(B)` | bool |
| `iqp(side)` | the side has a pawn on the d-file and no pawn of its own on the c- or e-file | bool per side |
| `islands(side)` | the number of runs of consecutive set bits in `files(side)` | 0-4 |

The passer definition matches the think tank's ("no enemy pawn ahead on its
own or adjacent files", phase-b-specialists.md C §0.1); the exact bitboard form
is Fork's own. **The a-d / e-h split for "one wing" is a placeholder**: C's
scripts (feat.py) are not in the repository, so its exact wing definition is
UNVERIFIED; the probe can try a second split (a-c / f-h with d/e as centre) as
a separate map if the owner wants.

### 2.3 Candidate class maps, declared before the probe

Each map gives a bucket count `8K` (phase octile times `K` pawn classes)
unless marked. Bucket edges are **placeholders**, chosen to give each class
a non-trivial share; the probe logs each class's share on its fit set, and an
edge may change only before the probe runs (declared rule), never after
seeing gains.

| map | gate | K | buckets |
|---|---|---|---|
| M0 | phase only, the 8 heads refitted (baseline; also answers "is the trained readout converged?", W2) | 1 | 8 |
| M1 | phase x pawn count {n <= 4, 5-8, >= 9} | 3 | 24 |
| M2 | phase x closedness {rams = 0, 1-2, >= 3} | 3 | 24 |
| M3 | phase x passers {neither side, at least one side} | 2 | 16 |
| M4 | phase x passers, side-to-move-relative {neither, mover only, other only, both} | 4 | 32 |
| M5 | phase x one wing {pawns on both wings or none, one wing} | 2 | 16 |
| M6 | phase x symmetric pawn files {yes, no} | 2 | 16 |
| M7 | phase x isolated d-pawn {either side has one, neither} | 2 | 16 |
| M8 | phase x islands {max over sides <= 2, >= 3} | 2 | 16 |
| M9 | pawn structure only, replacing phase: closedness (3) x passers (2) | 6 | 6 |
| M10 | phase merged to 4 (octiles 0-1, 2-3, 4-5, 6-7) x closedness (3) x passers (2) | 6 | 24 |

M9 tests "choose instead of add" (ideas.md 53's "choose (or add)"); M10 is the
2-D gate at a bucket count equal to M1/M2's. Eleven maps (W2's screen was "10
declared gatings"). Threat classes (B13's suggestion, idea 46 rank 2) are out of
idea 53's scope; the owner may add them as extra probe rows at no extra
engineering.

### 2.4 Cost of computing the class

All primitives above are 2-20 bitboard operations each (the passer test is
the largest: three shifts, a fill of three shifts, two ANDs per side). Two
ways to pay it, chosen by measurement (bench/ab.py on an identical tree: the
default network's heads duplicated into every sub-bucket, so the search and
bench are unchanged and only the cost differs; §6):
- **(a) per evaluation**, from the bitboards at the output step;
- **(b) incrementally:** stored in the position's per-ply state and
  recomputed only when a pawn moves, is captured or promotes (pawn moves were
  24.2% of makes on bench and 16% in game, X1, ideas.md 53), copied otherwise.

Fork has no pawn hash key on phase-4 (`Position::pawn_key` exists only on
tier2/batch4, ideas.md 53), so a cache keyed by pawn structure is not
proposed; (b) gives the same saving without a key.

## 3. The head and inference

- **Layout:** `out_weights[8K][2 * 512]` int16 and `out_bias[8K]` int32,
  bucket `= phase_table[game_phase(pos)] * K + pawn_class(pos)` (row-major by
  phase, so a map's sub-buckets of one phase are adjacent). One 2 KB row is
  read per evaluation, as today. The table grows from 16 KB (8 rows of 2 KB) to
  2 KB per bucket: 32 KB at 16 buckets, 48 KB at 24, 64 KB at 32 (M4), 12 KB
  for M9; within a game phase and structure change slowly, so the
  rows actually touched stay few (UNVERIFIED: measured by the nps A/B, not
  assumed).
- **File format:** version 2 already carries a bucket count in its header
  (net_file.hpp: "the bucket count in version 2") and a 128-byte map block
  holding the 25-byte phase table. Proposal: a **new architecture id** (the
  next free one, 9, a placeholder) whose map block also records the class
  map's id (one byte), so a file can only be read by a build that computes the
  same class; the reader refuses any mismatch, as it does today for every
  field. The arch-8 path is untouched, so every existing network and its
  bench reference stay valid.
- **Integer path:** unchanged arithmetic (the same `squared_sum` on a
  different row), so the scalar/SIMD identity and the int32 bounds hold as
  for arch 8 (net_file.hpp's reader bound is per row).
- **Parity:** tools/nnue/reference.py computes the class from the same
  definitions; tests/nnue/<net>.parity must contain positions of every class
  (the 446 parity positions are checked for coverage; positions are added from
  Fork's own data where a class has none); netcheck exact on all of them.
- **Switch:** none at inference (the class is part of the network, like the
  phase table). The comparison is network against network.

## 4. Trainer changes (tools/train, tools/nnue)

- main.rs: a new `Picker` variant (name to screen) computing
  `table[phase] * K + class` from its `Board`; `s.buckets = 8K` (today
  asserted to be 8: "Always 8 outputs"); `bucket()` gains the arm.
- tools/nnue: a spec file like s512pp.json with the class map id and K;
  convert.py, models.py and netformat.py write and read the wider output
  layer; reference.py computes the class.
- **Warm start, function-preserving** (W2; the think tank's A1 rule for warm
  starts): every sub-bucket starts as a copy of its phase bucket's weights and
  bias, so at step 0 the network computes exactly the parent's output (checked
  as S512+PP's warm start was: the validation loss at step 0 equal to the
  parent's within 1e-6, nets.md).
- **No hidden-size option exists today** (main.rs fixes `hidden` per
  architecture), so the small-net test (§5.2) needs one, training-side only.

## 5. The tests, in order

### 5.1 Stage A: the probe (local CPU, no engine change)

W2's method, unchanged in substance: freeze the default network's float first
layer (S512ppr3 today; the default at run time), compute the 1,024 SCReLU
activations for a fit set of about 2-4 M kept positions and a **disjoint
held-out set of 2 M positions** (B13: keep them disjoint; drawn from
g3s3-val plus a held-out training shard, split by game), and fit, for each map,
one readout per bucket by Gauss-Newton steps on the training target
(0.5 sigmoid(score / S) + 0.5 result, S the network's training scale), each a
weighted ridge solve of a 1,025 x 1,025 system per bucket accumulated in a
stream. Score: held-out loss of each map minus M0's (the refitted phase
heads), with a bootstrap interval resampling games.

- Cost: W2 computed about 3-5 minutes per Gauss-Newton pass at 30-50 GFLOP/s
  and about 5 passes per map, so 11 maps are about 3-5 CPU-hours plus the
  activation dump (UNVERIFIED until run); on 2 threads beside data generation
  (decision 13), one measurement job at a time.
- Output: the ranked maps, the class shares, and M0's gain over the trained
  heads (if over 2e-5, the trained readout is under-converged: W2's side
  question, reported, not acted on here).

**Settled (owner, 2026-11-09): diagnostic only.** The paragraph below is
the question as it was put; the stop-loss it proposed is not used.

**Owner decision (conflict in the records).** Idea 53's recorded kill
criterion is "the probe's validation gain is under 2e-5 for every class
map" (ideas.md, 2026-11-07). The testing rule of 2026-11-09 says offline
metrics are diagnostics, never a gate. The probe is not a validation-loss gate
on a candidate network but a cheap selection step before any GPU spend, so
this design keeps it as **a stop-loss and a selector** (stop if every map's
held-out gain is under 2e-5 with its interval including 0; otherwise train the
best map, and the second-best if within its interval), and leaves the
promotion decision to the fixed-node screen and the SPRT. The owner confirms
or removes the stop-loss.

### 5.2 Stage B: the small-net test at equal data (Kaggle)

Purpose: a trained (not frozen) comparison in which the first layer
co-adapts to the gate, cheap enough to run before a full-size run.

- **Two arms, identical except the head:** arm C (control) the 8 phase heads;
  arm E the chosen map. Same architecture family (S512+PP's inputs), a reduced
  hidden width (128, a placeholder; the cheapest width at which the phase
  heads still differ, to be confirmed by the first run's curves), trained
  from scratch on the **same data in the same order** (one g3s3 subset,
  the same superbatch count and learning-rate schedule as the standard recipe
  scaled to the subset, placeholders), **two seeds per arm** to measure the
  seed spread at this size.
- **Read-out:** validation loss on g3s3-val (diagnostic), then a fixed-node
  screen of arm E against arm C (1,600 games, 800,000 nodes per move, the
  fixed-node settings of DESIGN.md's 2026-11-09 rows), speed-adjusted
  (`FN + 118 log2(r)`, r from the screen's own games).
- **Rule:** go on to Stage C if the screen's adjusted estimate is above 0
  (the testing rule's prototype gate) and arm E's mean validation loss is not
  worse than arm C's by more than the measured seed spread (diagnostic,
  reported). If the screen is at or below 0, the idea stops here (it counts
  as a try of idea 53).
- Transfer from the small width to 512 is UNVERIFIED; that is why Stage C
  has its own control.

### 5.3 Stage C: full size, with an equal-data control (Kaggle)

- **Arm E:** the default network warm-started into the chosen map
  (function-preserving copies, §4), fine-tuned.
- **Arm C:** the same default network fine-tuned with its 8 phase heads,
  **the same data, schedule and seed**. Without arm C, any gain could be the
  extra training, not the gate (the question the think tank raised about
  S512ppr2's +20: T6, the anneal attribution, order step 3).
- Schedule: W2 proposed a warm fine-tune at LR 1e-5 for 60-120 superbatches
  (placeholders); the alternative is the standard retrain recipe (from the
  default's float weights, LR 0.0001, tenfold drop after 180, 360
  superbatches; DESIGN.md §5.6 item 8) run on the next snapshot, in which case
  arm C *is* that retrain (the retrain loop's next candidate) and idea 53
  rides on it. The second saves one GPU run and is the recommendation if a
  retrain (8b or later) is due at the time; otherwise W2's short fine-tune.
- Integrity checks block: parity (trainer leg, netcheck exact), the
  quantization limits of S-512 (21 / 16 cp), bench; the endgame check is
  reported and a large regression flagged (non-blocking, 2026-11-09).

### 5.4 Stage D: the speed-adjusted fixed-node screen (GitHub)

Arm E against arm C (both finished candidates, competing candidates are
all screened first per the testing rule), 1 stage of 1,600 games at 800,000
nodes per move; r from the screen's own games; **`FN_adj = FN + 118 log2(r)`
must be above 0**. If arm C is itself a retrain candidate, arm C also gets
its own screen against the default, and the better of the two goes on.

### 5.5 Stage E: the STC SPRT (GitHub)

Arm E against the default network, `--kind network` ([0, 5] nElo, alpha =
beta = 0.05, up to 13 STC stages), idea id `53`. Not on the LTC-sensitive
list (an evaluation change with near-zero speed cost); the owner may add an
LTC confirmation.

## 6. The speed cost, priced

- **Price:** 1.72 Elo per 1% nps (1.56-1.88; decisions log 2026-11-09,
  testing policy item 4), i.e. 118 Elo per doubling.
- **Estimate (UNVERIFIED until measured):** the class by (b) about 20 bitboard
  operations on the 16-24% of makes that touch a pawn, plus a multiply-add for
  the bucket index per evaluation; the output row is the same size as today.
  Expected 0.995-1.000 of today's nps, a price of 0 to 0.9 Elo
  (118 x log2(0.995) = −0.85). W2 estimated 0.99-1.00 for a 16-bucket head.
- **Kill on speed:** nps down by more than 1% (ideas.md 53), measured by
  bench/ab.py (interleaved, identity-checked) on the engine with the class
  computed and the bucket used, against the arch-8 engine with the same
  network weights duplicated into every sub-bucket (identical tree, so an
  nps-only comparison), and in situ from Stage D's games.
- The fixed-node screen's speed adjustment then prices whatever remains.

## 7. Decision rule (declared before any result)

| stage | continue if | otherwise |
|---|---|---|
| A, probe | always (owner, 2026-11-09: diagnostic only): the best-ranked map goes on; whether any map's held-out gain over M0 reaches 2e-5 with a bootstrap interval excluding 0 is reported | (no stop at the probe; a ranking with no map above 2e-5 is reported to the owner) |
| speed | nps down at most 1% (bench/ab.py) | redesign the class computation once (a to b), else stop |
| B, small nets | FN_adj of E against C above 0 | stop (a try of idea 53) |
| C, full size | integrity checks pass | fix the conversion; not a strength decision |
| D, screen | FN_adj of E against C, and of E against the default, above 0 | stop (a try) |
| E, STC SPRT | H1 | not adopted; at most two tries per idea and time control |

Adoption, if E passes, is the owner's (promotion of a default network, with
its bench reference, nets.md entry, parity file, the endgame check reported,
the labeller policy's part switch, and the transfer-check list).

## 8. Costs

| item | lane | estimate (UNVERIFIED) |
|---|---|---|
| engineering: class function in C++, Rust and Python, the arch-9 reader and writer, trainer picker, parity coverage, tests | E | 2-4 days (B13's 2-4 d for W2) |
| Stage A probe | L | about 3-5 CPU-hours on 2 threads, plus the activation dump |
| Stage B, 2 arms x 2 seeds at reduced width | K | 4 runs; each shorter than a full-size run (S512ppr2's 360-superbatch retrain took 7,741 s, about 2.1 hours; nets.md) |
| Stage C, 2 arms | K | 2 runs: about 0.35-0.7 GPU-hours each for a 60-120-superbatch fine-tune by that rate, or about 2.1 each at the standard recipe (or 1 extra run if arm C is the due retrain) |
| Stage D | G | 1 stage (2 if arm C also screens against the default) |
| Stage E | G | 1-13 STC stages (a +5 nElo network typically decides in a few; the network kind's cap is 13) |

## 9. Names and constants for the screens (none screened yet)

Names: `pawn_class` (function), `PawnClassCount` (K), the class-map ids
(M0-M10 as data, not code names), a trainer `Picker` variant (e.g.
`PhasePawn`), the spec file name (e.g. `s512ppe.json`), the architecture's
short name (e.g. "S512+PPE"), and any member holding the incremental class in
the position state. Constants: K per map; the pawn-count edges 4 / 8; the ram
edges 0 / 2; the island edge 2; the one-wing file split a-d / e-h; the phase
merge of M10; the probe's 2 M held-out size and 2e-5 line (a diagnostic since 2026-11-09, owner; the latter
from ideas.md 53); the small-net width 128; the fine-tune LR and length. All
are placeholders or record values from ideas.md 53 / W2; none is taken from
another engine.

## 10. Prior art (concept level)

Mixtures of experts: Jacobs, Jordan, Nowlan and Hinton, "Adaptive Mixtures of
Local Experts", Neural Computation 3(1), 1991. Linear probes on frozen
features: Alain and Bengio, arXiv:1610.01644 (2016). Function-preserving
expansion: Chen, Goodfellow and Shlens, "Net2Net", ICLR 2016. Output buckets
selected by material are common public NNUE practice (KB nnue-design.md §3.3,
as cited by W2 and ideas.md 53). Pawn-structure categories (closed, open,
isolated queen's pawn, passed pawns) are general chess vocabulary. Choosing
the gate by a probe and gating by pawn structure are Fork's own as far as the
think tank found (UNVERIFIED that no engine does it). No engine's bucket count
or boundaries are used.

## 11. Unverified items

- The value (+2, 0 to +6) and the speed (0.995-1.000) are model estimates.
- C's exact "one wing" definition (its scripts are not in the repository).
- Every Kaggle and CPU time above.
- Transfer of a small-width result to width 512.
- Whether a 32-64 KB head changes cache behaviour measurably (the nps A/B
  decides).
- The parity file's class coverage (not yet counted on the 446 positions).
