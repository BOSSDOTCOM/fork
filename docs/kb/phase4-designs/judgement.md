# Phase 4 designs: judgement (step 3)

Step 3 of the Phase 4 multi-agent plan (DESIGN.md on main, §5, "Phase 4
multi-agent plan"). Written 2026-10-28 by the judge agent from the three
proposals in this folder (`design-speed.md` "S", `design-accuracy.md` "AF",
`design-novelty.md` "XGR"), KB `nnue-design.md`, `phase4-pipeline.md`,
`data-policy.md`, `training-data.md` §2-3, `competition.md` (TCEC hardware),
and DESIGN.md §5 (the plan), §5.2 "Testing setup", §5.3 (step 0) and §7.

- **No engine source, no nnue-pytorch code and no web page was opened.**
  No other engine's constant is introduced here. Every number below comes
  from the proposals, the KB, or the judge's own arithmetic, which is shown.
- **Nothing was run.** Every speed, Elo, GPU-hour and datagen figure is an
  *estimate*; unconfirmed facts are marked **UNVERIFIED**.
- **What this file decides:** which candidates enter the bake-off (step 4),
  at what sizes, and how the bake-off and the parity test should work. It
  does not pick the net. Training and SPRT pick the net.

---

## Summary (one page)

**Recommendation: four bake-off entries, all at accumulator width 512, on
the same data (G0 + G1, about 0.7 B positions), compared head to head in a
factorial order.**

| Entry | Source | Bake-off size | Confirmation size | Why it is in |
|---|---|---|---|---|
| **S-512** | S | 768 mirrored → 2×512 SCReLU → 8 piece-count buckets (0.8 MB) | width sweep S-768 / S-1024 against S-512 on G1+G2 | Fastest (about 0.74× the bootstrap's nps, judge's common model), lowest risk, exact parity proof. Datagen workhorse whatever wins. Size raised from S's proposed 256 so all entries share one width (S-256 stays as an optional B0 ladder rung) |
| **H-512 (hybrid)** | AF inputs + S kernel + XGR clip rule | AF's fitted 4-region mirrored input with factoriser → 2×512 SCReLU → 8 phase-octile buckets (3.2 MB) | H-1024 with AF-L's region rule (B ≤ 10) | The control that makes the bake-off readable: S vs H isolates king regions at nearly equal speed; H vs AF-S isolates AF's body; H vs XGR isolates X + G. Settles the S/AF dispute on whether 0.7 B own positions can feed king regions |
| **AF-S** | AF | as proposed: H = 512, same fitted 4-region map as H, pairwise → 16 → 32 → 1, 8 phase stacks (3.2 MB) | AF-L (H = 1024, B ≤ 10); AF-LT (threats) stays a later generation | The only entry with a body; the bet that matches TCEC's long time controls. About 0.58-0.62× nps (common model) |
| **XGR-512** (conditional) | XGR | as proposed: hand 4-region map, single layer, exposure plane X, phase gate G; no revision head | XGR-1024 | Highest originality value. Enters only if X passes its offline pre-test (XGR §2.2 step 1) on B0 + G1 data **and** bullet can express the gate (or G falls back to G1/buckets); otherwise X, G and R move to the swap list. The bake-off never waits for it |

**Errors found in the proposals** (details in §1): AF's int16 accumulator
proof ignores the factoriser merge (two ±1.98 tensors merge to ±3.96:
33 × 1,010 = 33,330 > 32,767); XGR's revision head caps its scale at 64 while
its target is scaled by 1/1,024, so the fitted weights (order 10⁻³) quantize
to zero; XGR's exposure rule gives kings no value class although kings count
as attackers; AF's and XGR's per-position "half-step" parity bounds, and step
0's own worst-case bound for B0, are vacuous at these widths and let
converter errors through; XGR's AVX-512 column assumes full-width 512-bit
execution, which S and AF say Zen 4 lacks; S's datagen advantage
"1.3-2.7×" holds against 1024-wide bodies, not against the 512-wide entries
(about 1.2-1.45×); smaller slips in AF (33, not 32, is the widest safe L2;
a "per perspective" µop count that is both perspectives; factoriser rows
left out of its GPU model) and XGR (the "1,024 needs no widening" limit
holds only with one accumulator register).

**Protocol changes** (§6):
1. **Equal positions seen** (about 6 B each, the same schedule), GPU hours
   recorded; plus one **training-noise check** (S-512 trained twice).
2. **Every candidate's output rescaled** to the same mean |eval| as B0 on a
   fixed set before games, so the Phase 3 margins don't decide the bake-off.
3. **STC and LTC for every decisive pairing; LTC decides** (DESIGN §5.2);
   complex against simpler on gainer bounds [0, 5]; an inconclusive result
   keeps the simpler design ahead. If the top two end within about 10 Elo
   at LTC, **confirm both** at the large size.
4. **Speed price measured once**: B0 against itself at **2:1 time odds**,
   2,000 games each at STC and LTC (S's method, run with B0 instead of the
   bootstrap); XGR's busy-loop slowdown is not needed.
5. **Bake-off builds are scalar + AVX2 only** (the SPRT target is
   x86-64-v3); AVX-512 and VNNI only for the winner.
6. **Parity test (deliverable 6) rebuilt**: drop the worst-case bound (it
   passes by construction); add a **quantization leg** (the reference
   quantizes `weights.bin` itself and must equal bullet's `quantised.bin`
   and Fork's net file integer for integer), keep F = R-int exact and
   R-float = T, gate on the **exactly computed** quantization loss
   |R-int − R-float| with recorded thresholds, add XGR's **feature leg**
   (index sets from C++, Rust and an independent python-chess reference,
   over 1 M positions), and extend the mutation cases (missing `.round()`,
   wrong mirror side, wrong region or bucket map, wrong feature rule), each
   tied to the leg that must catch it. This applies to B0 too.

**Questions for the owner** (§7): equal width versus half-size bake-off
entries; whether four candidate implementations (scalar + AVX2 + parity
each) are acceptable before the bake-off; LTC as the decider; approving the
time-odds games and an optional AWS many-core nps run; a design-level
originality screen for X, G, R, the fitted regions and the target-centric
threats; reading bullet's code at the pin to settle the UNVERIFIED trainer
features first; who sets the quantization-loss gate per architecture;
waiting for G1 before the bake-off; and whether Fork may ship two nets (a
fast datagen net and a different playing net).

---

## 1. Claim checks

### 1.1 Overflow arithmetic, redone layer by layer

All three use QA = 255 (FT), bullet's AdamW clip ±1.98 unless stated, and
round-to-nearest quantization.

| Proposal, layer | Claim | Judge's check | Verdict |
|---|---|---|---|
| S, FT int16 | round(255 × 1.98) = 505; 33 × 505 = 16,665 | 504.9 → 505; 505 × 33 = 16,665 < 32,767. No factoriser | correct |
| S, output, QB = 64 | 255 × 64 × 1.98 ≤ 32,767; loader \|Oq\| ≤ 128 | 32,313.6 ≤ 32,767; floor(32,767/255) = 128; 255 × 128 = 32,640 | correct |
| S, SCReLU product | t·v ≤ 8,323,200; pmaddwd pair 16,646,400; K ≤ 258 per int32 lane | 32,640 × 255 = 8,323,200; floor(2,147,483,647 / 8,323,200) = 258; K = 2H/(8r) on AVX2 → H ≤ 1,032 at r = 1 | correct |
| S, tail | \|Σ\| ≈ 8.5 × 10⁹ at H = 512 (int64); \|Cq\| ≤ 32,314 | 1,024 × 8,323,200 = 8.52 × 10⁹; 255 × 64 × 1.98 = 32,314 | correct |
| S, QB = 128 variant | 255 × 128 × 0.99 = 32,314 | 32,313.6; \|Oq\| ≤ round(126.7) = 127 | correct |
| S, parity proof | \|R-int − S·Rq\| < S/(QA·QB) + 1 < 2 cp | Accumulator = QA × Rq's sum exactly; clamp and square exact on that grid; only the two truncations differ. Holds **if Rq's integers equal the net file's** (see §6.6) | correct, with that premise |
| AF, piece FT int16 | "≤ 505, so 32 features plus a bias stay below 16,665" | **AF trains a factoriser** (§2.1) and merges it into every region at save. Region and factoriser tensors are each clipped at ±1.98, so a merged weight reaches ±3.96 → 1,010, and 33 × 1,010 = **33,330 > 32,767** | **error**: the proof fails; the loader check still guards real nets. Fix: clip each tensor at ±0.99 (XGR's rule) |
| AF, threats int8 | \|R_p\| ≤ 256; 256 × 127 = 32,512 | Also safe at −128: 256 × (−128) = −32,768 fits int16. Clip 0.49 × 255 → 125 | correct |
| AF, saturating combine | clamp(sat16(s)) = clamp(s) | saturation limits lie outside [0, 255] | correct |
| AF, pairwise | (v_j v_k + 256) >> 9 ∈ [0, 127]; mulhrs form exact | (65,025 + 256) >> 9 = 127; (64x + 2¹⁴) >> 15 = (x + 256) >> 9 exactly; 255 << 6 = 16,320 fits | correct |
| AF, L1 int8 | pair sum ≤ 2 × 127 × 127 = 32,258 | no pmaddubsw saturation; int32 sum ≤ 1,024 × 16,129 = 16,516,096 | correct |
| AF, L2 | 16 × 2,016 × 32,767 = 1,056,932,352 | correct | correct |
| AF, L3 | 32 × 1,984 × 32,767 = 2,080,311,296; "32 is the widest" | product correct; but 33 × 1,984 × 32,767 = 2,145,321,024 < 2,147,483,647, so 33 also fits | minor error (harmless) |
| AF, output | (y3·M) >> 32, \|y3·M\| < 2⁴⁸ | for S up to about 400; larger S still fits int64 | correct |
| XGR, FT + exposure + side lanes | 63 × 505 = 31,815 with 0.99 per tensor | 32 base + 30 X + bias; merged ≤ 1.98 → 505 | correct |
| XGR, experts | 255 × 127 = 32,385; 256 per lane, 2,114,092,800 | floor(2,147,483,647 / 8,258,175) = 260 | correct; the "1,024 is the largest width without mid-sum widening" holds only with **one** accumulator register per expert |
| XGR, linear lanes, gate | ×128 term ≤ 8.2 × 10⁶; gate int64 | 2 × 64 = 128; 63,630 × 128 = 8.14 × 10⁶ | correct |
| XGR, revision head | QR = largest power of two **≤ 64** with max\|q\| ≤ 127 | The target is \|e − s\| / 1,024: typical targets are 0.03-0.1, spread over hundreds of active φ ∈ [0, 1], so ridge weights are of order 10⁻³ (*estimate*). At a step of 1/64 they **round to zero**; the head degenerates to its bias. The int16 bound (\|q\| ≤ 128) allows QR up to 128 / max\|u\|, i.e. thousands | **error**: lift the ≤ 64 cap (or rescale the target) |

### 1.2 Speed estimates, put on one footing

The three use different assumptions, so their nps factors are not directly
comparable:

| Assumption | S | AF | XGR |
|---|---|---|---|
| Bootstrap eval per call; non-eval node time | 15 ns; 133 ns | 15 ns; 130 ns | 25 ns; 120 ns |
| Share of nodes evaluated | 0.8, applied to updates too | 0.85 | 0.85; updates at every node |
| Throughput | 3 vector µops/cycle, 4.1 GHz, +15% misses | 3 µops/cycle, 4.7 GHz; ×1.6 at the low end | 2.5 instructions/cycle, 4.7 GHz |
| AVX-512 on Zen 4 | 1.0-1.2× (double-pumped, UNVERIFIED) | 5-20% | **assumes the instruction count halves the time** |

**Judge's common model** (S's assumptions for everyone, each proposal's own
µop counts; *estimate*): net ns = µops × 0.0935 (= 1.15 / (3 × 4.1)) plus
scalar extras; node ns = 133 + 0.8 × net ns; factor = 145 / node ns.

| Net | Vector µops per eval | Scalar extras | Node ns | × bootstrap | Proposal's own figure |
|---|---|---|---|---|---|
| B0 (768 → 256 CReLU) | 384 | none | 162 | 0.90 | 0.90-0.97 |
| S-256 | 416 | none | 164 | 0.88 | 0.88 |
| **S-512** | 832 | none | 195 | **0.74** | 0.74 |
| **H-512** (hybrid, §4) | 847-890 (refresh +4-15% of updates) | none | 196-200 | **0.73** (plus any L2 spill) | n/a |
| XGR-512 without X | 1,100 | none | 215 | 0.67 | n/a |
| **AF-S** | 1,307-1,480 (L1 blocks 35-50% non-zero) | 5 ns | 235-248 | **0.58-0.62** | 0.49-0.67 |
| **XGR-512** | 1,356 (k = 2) | 60 ns attack maps | 282 | **0.51** | 0.51 |
| S-1024 | 1,664 | none | 258 | 0.56 | 0.56 |
| AF-L | 2,464-2,810 | 5 ns | 321-347 | 0.42-0.45 | 0.34-0.52 |
| XGR-1024 | 2,700 | 60 ns | 383 | 0.38 | 0.37 |

What this shows:
- **Ranking is robust**: S ≈ H > AF-S > XGR at the bake-off width; X is the
  single largest cost item in any design (0.67 → 0.51, about 0.4 speed
  doublings), consistent with XGR's own 25% figure.
- **Speed gaps in doublings** (log₂ of nps ratios): S-512 or H-512 against
  AF-S about 0.25-0.35; against XGR-512 about 0.5. At confirmation sizes,
  S-512 against AF-L about 0.75-0.8, H-1024 against AF-L about 0.3-0.4.
- **S's update cost is slightly understated**: lazy updates still run on
  most interior nodes whose children evaluate, so applying f = 0.8 to the
  update undercounts by roughly 5% of node time. Same direction for all.
- **XGR's AVX-512 column is optimistic for Zen 4/4c**: if 512-bit operations
  are double-pumped (S and AF; UNVERIFIED), its 0.64 and 0.51 v4 figures
  shrink toward its AVX2 ones.
- **TCEC's cache differs from the local one**: the 7600X3D's 96 MB L3 hides
  table size; the EPYC 9754 has (UNVERIFIED, model knowledge) 1 MB L2 per
  core shared by two SMT threads and 16 MB L3 per 8-core complex. AF-L's
  15.9 MB table would fill that L3 by itself, so local nps overstates AF-L
  and AF-LT at TCEC; S's 0.8 MB table is least affected, though "fits in L2
  at 512 threads" weakens when two threads' stacks, histories and TT lines
  share each L2 (S §2.1 leaves 25% for all of that).

### 1.3 Training cost and data volume against Kaggle and Fork's data rate

Kaggle (KB): T4 x2, about 30 GPU h a week, sessions ≤ 12 h, 4 CPU cores and
29 GB per GPU session; bullet's T4 throughput UNVERIFIED (K5); two
trainings per T4 x2 session UNVERIFIED (K18/K22).

| Claim | Check | Verdict |
|---|---|---|
| S: 2 B positions at 0.3-3 M/s → 0.2-1.9 h; sweep 4.8 B; gen-3 15 B | arithmetic correct (2 × 10⁹ / 3 × 10⁵ = 1.85 h, etc.); gen-3 needs two chained sessions at the slow end | correct |
| AF: bytes/position 2 × active × H × 4 B, fwd + bwd; AF-S 229 KB | counts only the region rows; **the factoriser's always-active rows are left out**. XGR counts them (pessimistic) | AF-S/AF-L may train up to 2× slower than tabled (UNVERIFIED how bullet gathers factorised inputs); AF-L 8.5-15 h becomes up to 17-30 h: still inside a week, chained |
| AF: sweeps "4 × 1.5 B" | the listed sweeps need about 5 runs including the baseline | minor undercount |
| XGR: 136 active rows × 3 × H × 4 B; XGR-512 at 0.24-0.5× B0's rate; 1.1-4.4 h per net | arithmetic correct (835,584 B against 196,608 B) | correct |
| XGR: X features computed in the Rust loader, 200-500 ns/position | plausible on 3 loader threads against a GPU rate under 1 M/s; must be in K17's measurement with the real input type | plausible (UNVERIFIED) |
| All: datagen 100-300 M positions/day "for the bootstrap", scaled by nps | training-data.md §3 derived 130-260 M/day assuming **5k nodes per move and a small net at 0.7-1.5 M nps per thread**, not the bootstrap; step 0 sets the node count by depth 8-9 instead | every datagen-days figure in all three is uncertain by about 3×; deliverable 2 measures it |
| S: "1.3-2.7× as many positions per day" | against the bake-off entries (common model): 0.74 / 0.60 ≈ 1.2× vs AF-S, 0.74 / 0.51 ≈ 1.45× vs XGR-512; 1.6-1.9× vs AF-L | **overstated for the bake-off sizes**; holds at confirmation sizes |

**Data the designs need against what Fork can supply over Phase 4**
(*estimate*): bake-off G0 + G1 ≈ 0.7 B (AF's figure; XGR asks ≥ 0.4 B, S
0.2 B); confirmation 0.6-1.5 B; AF-LT ≥ 2.5 B; S's king-bucket step about
2 B. At a nominal 100-300 M/day times labeller factors of 0.5-0.9, eight
weeks of datagen give roughly 3-15 B. Everything except AF-LT fits
comfortably; AF-LT lands late in Phase 4 at the low end.

### 1.4 Dependencies on unconfirmed bullet features

Confirmed in the KB (phase4-pipeline.md §1.3-1.6): `Chess768`, bucketed and
mirrored bucketed input types (`ChessBuckets`, `ChessBucketsMirrored`),
factorised inputs, `MaterialCount` output buckets, `screlu`/`crelu`,
`concat`, `select`, per-tensor clip (`set_params_for_weight`), `.round()`,
i8/i16/i32 quantization targets, `SavedFormat` transforms,
`load_weights_from_file`, `eval_raw_output`.

| Design | Unconfirmed feature | Fallback |
|---|---|---|
| S | one-bucket map in the mirrored bucketed input | small custom input type in `tools/train` |
| S | a 33-entry custom piece-count bucket map (MaterialCount's mapping unknown) | custom bucket function, or adopt MaterialCount's mapping if it is equal widths |
| AF, H | arbitrary 32-square region map in the mirrored, factorised input | custom input type |
| AF, H | custom output-bucket / stack function (phase octiles) | piece-count octiles (AF's own fallback) |
| AF | pairwise product node | slice + elementwise multiply (also unconfirmed) → custom op → last resort SCReLU on 2H with H halved |
| AF | layer stacks across three layers (`select` after each) | believed expressible with `select` (UNVERIFIED); otherwise output buckets on L3 only |
| AF | QAT operation (PR #483) | clamping in the optimizer |
| AF | activation-sparsity penalty | optional; neuron-pair permutation in Fork's converter works without it |
| AF-LT | custom Rust threat input type; repeated sparse indices summed | a "count ≥ 2" slot per index (14,592 indices) |
| XGR | custom input type (regions, mirror, factoriser, exposure plane, exposure factoriser) via bullet's sparse-input trait | none for X (drop X) |
| XGR | node add, subtract, constant scale, slice, elementwise product of 1-wide nodes, crelu on a 1-wide node (gate) | custom op; G1 (still needs the product); material buckets; PyTorch trainer for gate experiments (slow, UNVERIFIED) |
| all | the exact rounding of `.round()` (Rust-style half away from zero is likely) and whether factoriser merges are summed in f32 | matters for the parity quantization leg (§6.6); read at the pin |

**One reading of bullet's code at the pin** (allowed: MIT tool) settles every
row above and should precede the bake-off spec.

### 1.5 Errors and weak points, by proposal

**S**
1. Datagen advantage "1.3-2.7×" overstated against the 512-wide entries
   (about 1.2-1.45×); right against 1024-wide bodies (§1.3).
2. Update cost scaled by f = 0.8 although lazy walk-backs update most
   interior nodes (about 5% of node time, §1.2).
3. The exchange-rate model treats the fixed-node accuracy gap as
   independent of time control. Both terms compress at long time controls
   and the accuracy term depends on the node count, so the extrapolation to
   1800+3 on 512 threads is weak; its "R_LTC < 10" abandonment threshold is
   an estimate.
4. "Core-local at 512 threads" weakens under SMT (two threads per L2).
5. The < 2 cp parity proof is correct but rests on the reference's
   quantized integers equaling the net file's; S does not test that
   premise. A numpy reference using `np.round` (half to even) could differ
   from bullet on exact ties. The quantization leg of §6.6 closes it.
No arithmetic error found.

**AF**
1. **Accumulator overflow proof ignores the factoriser merge**: 33,330 >
   32,767 is possible (§1.1). Real nets are guarded by the loader check, but
   the stated proof is wrong; clip each tensor at ±0.99.
2. "32 is the widest L2" is false; 33 fits (harmless).
3. "Activation + pairwise, per perspective, about 580 µops" is the
   two-perspective count (288 each).
4. GPU model omits factoriser rows (up to 2× slower training).
5. Its nps upper ends (0.67, 0.52) use 4.7 GHz with no miss penalty; the
   common model puts AF-S at 0.58-0.62 and AF-L at 0.42-0.45.
6. **Parity bound vacuous**: a half-step worst case per weight, propagated
   through a 512-1024-wide accumulator and a dense L1, yields a tolerance of
   hundreds of centipawns or more, so a converter error below it passes
   (§6.6).

**XGR**
1. **Exposure rule incomplete**: the classes P < N = B < R < Q leave the king
   out, yet kings count as attackers; "attacked by a strictly lower class"
   is undefined for a king attacker. The C++, Rust and python-chess
   implementations cannot agree until it is fixed (suggested: the king
   ranks highest, so it exposes only an undefended piece).
2. **Revision head quantizes to zero** (QR ≤ 64 against a 1/1,024 target
   scale, §1.1).
3. **Parity bound vacuous**, as AF-6, and looser through the gate term
   |Δg|·|o_A − o_B|.
4. AVX-512 estimates assume full-width 512-bit execution (§1.2).
5. "1,024 is the largest width without mid-sum widening" holds only with one
   accumulator register per expert; with two (normal, to hide latency) the
   limit doubles. Weak justification for the confirmation width.
6. The gate's colour-symmetry argument is unnecessary: the colour-flip test
   holds for any perspective net, because the twins have identical
   (stm, ntm) feature sets. Harmless.
7. The hand-drawn region map is a taste constant (screen it); AF's fitted
   map has a recorded derivation.

---

## 2. Comparison

| Criterion | S | AF | XGR | H (hybrid, §4) |
|---|---|---|---|---|
| Expected strength at STC (*estimate*) | strongest per its thesis: highest nps, accuracy of a single 768 layer | must earn about 0.3 doublings (AF-S vs S) at fixed nodes | must earn about 0.5 doublings; X carries most of the cost | close to S's speed; gains if regions pay at fixed nodes |
| At LTC | gap to richer nets narrows | its thesis: improves relative to S | X's value expected to grow with time (threat-like evidence, KB §1.6) | between S and AF |
| At TCEC (1800+3, up to 512 threads, large Hash, EPYC Zen 4c; VNNI UNVERIFIED) | smallest table, best cache behaviour; lowest accuracy ceiling | highest accuracy ceiling (AF-L, later threats); largest tables, L3 pressure; gains most from VNNI (12-20%, AF's estimate) | int16 only, no VNNI need; X's scalar cost does not scale with SIMD width | int16 only; 3-6 MB table |
| Data at bake-off / confirmation | 0.2 B / 0.6 B; growth step at 2 B | 0.7 B / 1.5 B; AF-LT ≥ 2.5 B | ≥ 0.4 B / 1.0-1.5 B | 0.7 B / 1.5 B |
| Kaggle cost, bake-off (6 B positions seen, relative to B0's K5 rate) | about 0.5× rate: lowest | 0.25-0.5× rate + 3-5 sweep runs | 0.24-0.5× rate + 2 ablations | 0.25-0.5× rate |
| Implementation size | B0 + mirror, 2-entry cache, SCReLU, buckets | largest inference: regions, factoriser, region cache, pairwise, sparse int8 L1 with NNZ and permutation, two int16 layers, stacks; later threats | largest trainer risk: custom input type with attack features in 3 languages, side lanes, gate, two experts, custom graph ops; R fit tool later | S's kernel + AF's front end (both needed anyway) |
| Parity difficulty | lowest (< 2 cp proof) | medium (multi-layer integer emulation; quantization loss larger) | medium-high (feature leg essential; gate; R needs its own leg) | lowest (S's proof applies) |
| Originality value | low (all published practice) | medium-high (data-fitted regions, phase-octile stacks from Fork's `game_phase`, target-centric threats) | high (X, G, R, bootstrap-PST seeding) | medium (AF's fitted regions) |
| Originality risk (screens) | constant screen will likely report matches for common round values (512, 8 buckets); generic, justified by Fork reasoning | design-level screen for target-centric threats (a recent, crowded area); constant screen for 16/32 widths and the shift chain | design-level screen for X and R concepts; constant screen for the hand region map | as S + AF |
| Fit with B0's pipeline | almost none changes | new converter steps (merge, permutation, int8), fitted-map tool, held-out tool | new Rust input type, custom graph, seeding script, R fit tool | small changes (custom map, merge) |

---

## 3. Recommendation and sizes

The bake-off should answer the two questions that decide Fork's
architecture and that argument cannot: **do king regions pay on Fork's own
0.7 B positions, and does a body pay after its speed cost?** A third,
cheaper question is whether XGR's new elements pay. The four entries below
answer these in a factorial order, each comparison changing one thing.

1. **S-512** (bake-off), confirmation: S-768 and S-1024 against S-512
   retrained on G1 + G2, winner by LTC with S's §2.8 criterion. Equal width
   with the others removes the width confound; S-512 is the net S would
   ship. S-256 is kept only as an optional ladder (B0 → S-256 shows what
   SCReLU, buckets and mirroring are worth, for the analyst).
2. **H-512** (hybrid, §4), confirmation H-1024 with AF-L's region rule.
3. **AF-S** as proposed (H = 512, B = 4 with θ = 10%, the **same fitted map
   as H**, pairwise, 16 → 32 → 1, 8 phase stacks), confirmation AF-L.
   Before the bake-off, AF may run only its small-layer activation sweep
   (3 runs at 1.5 B positions seen, chosen by held-out loss); its B = 1
   against B = 4 sweep is answered by S against H in games, and the
   quantized-against-float sweep by the parity loss report. AF-LT is a
   later generation (≥ 2.5 B), not a bake-off question.
4. **XGR-512** as proposed (no revision head), confirmation XGR-1024,
   **conditional**: X must pass XGR's offline pre-test (residual |static −
   search| larger on k ≥ 1 positions, on 10 M G1 positions with B0, a few
   CPU minutes), and bullet must express the gate (else G1 or material
   buckets, per XGR's fallbacks). Its two ablation nets (no X; buckets
   instead of G) are trained only if it enters. If it does not enter, X, G
   and R head the swap list (§5).

**Order of decisive comparisons:** H vs S (regions) → AF-S vs the better of
S and H (body) → XGR vs H (X + G, with the region map as a known confound).

---

## 4. Hybrid H: AF's inputs on S's kernel

| Part | H-512 (bake-off) | H-1024 (confirmation) | Source |
|---|---|---|---|
| Piece inputs | 768 per region, side-to-move-relative, vertical flip for Black, **mirrored** so the own king is on e-h | same | AF §2.1 (S and XGR mirror the same way) |
| King regions | **B = 4, fitted** to the own-king histogram of the bake-off data (θ = 10%, B_max = 4), the identical map AF-S uses | AF-L's rule (θ = 3%, B_max = 10) on G1 + G2 | AF §2.1 |
| Factoriser | one shared 768 set, training only, merged at save | same | AF §2.1, XGR §2.1 |
| Clip | region and factoriser tensors **±0.99 each** (merged ≤ 1.98), biases ±0.99, output ±1.98 | same | XGR §5.1 (fixes AF's bound) |
| Accumulator | 2 × 512 int16, copy-make stack, lazy | 2 × 1,024 | S §2.3 |
| Refresh | on a region change or mirror crossing, through a cache of regions × 2 sides per perspective per thread (S's 2-entry cache generalised) | same | S §2.3, AF §3.1 |
| Activation | SCReLU, multiply-before-square order | same | S §2.5 |
| Body | none: 2H → 1 per bucket | same | S §2.4 |
| Output buckets | 8, by `game_phase` octiles of the training data (piece-count octiles if bullet lacks a custom function), the same selector as AF-S | same | AF §2.5 |
| Quantization | QA 255, QB 64, output bias int32 at QA·QB, `.round()` everywhere | same | S §2.6 (B0's convention) |
| Net file | 3,072 × 512 × 2 + 1,024 + 8 × 1,024 × 2 + 32 = **3,163,168 B** (3.2 MB) | 6,326,304 B at B = 4; up to 15.8 MB at B = 10 | judge |

**Why these parts work together.** King regions cost nothing at inference
except refreshes, which the cache makes cheap, so H keeps S's speed thesis
almost intact (common model 0.73× against S-512's 0.74×) while adding the
king-relative knowledge AF and XGR both argue for. A single layer keeps S's
int16-only kernels (no VNNI or saturation question) and S's exact < 2 cp
parity proof. AF's fitted map and θ rule answer S's data objection (each
region ≥ 10% of samples, a factoriser for the shared part); S itself plans
king buckets as its first growth step, and the bake-off can show whether
0.7 B positions already suffice. Using AF-S's exact input set and output
selector makes H the control for AF's body; S is the control for regions.
H also tests S's L2 claim: its hot set (0.75-1.5 MB: one region block per
perspective) exceeds the 1 MB L2, so `fork bench` of H against S at equal
width shows whether the spill costs anything.

**Overflow bounds.**
- FT: |Bq| ≤ round(0.99 × 255) = 252; merged |Wq| ≤ 505; |acc| ≤ 252 + 32 ×
  505 = 16,412 < 32,767. Loader re-checks |Bq[i]| + 32 · max_f |Wq[f][i]|
  ≤ 32,767 (B0's rule).
- Output: as S §5.3: |Oq| ≤ 127 (loader ≤ 128), v·w ≤ 32,640, ≤ 258 products
  per int32 lane (H-1024 on AVX2 with one register: 256), int64 tail,
  |Cq| ≤ 32,314.
- Parity: |R-int − S_out · Rq| < S_out / 16,320 + 1 < 2 cp (S's proof), given
  the quantization leg.

**Cost** (*estimate*). nps about 0.73× the bootstrap at 512 (common model,
plus an unknown L2-spill penalty), about 0.55× at 1,024. Refresh cache
4 × 2 × 2 × (1,024 + 96) B = 17.9 KB per thread (9 MB at 512 threads).
Training: 2 × (32 + 32) active rows → about 0.25-0.5× B0's K5 rate; 6 B
positions seen ≈ 1.7-6.7 GPU h if B0 trains at 1-2 M/s (UNVERIFIED);
H-1024 on 15 B positions about 8-35 GPU h (two to three chained sessions at
the slow end). Data: 0.7 B gives each region row about 12.8 M touches on
average and the smallest region about 5.1 M (AF's arithmetic). bullet
dependencies: custom region map and phase selector, both with fallbacks
(§1.4).

**Risk.** Low: every part comes from a proposal and is needed by S or AF
anyway. Originality: AF's fitted map and phase selector go through the
screens as part of AF.

---

## 5. Components to test later as swaps

Each is one SPRT on the winner (gainer bounds [0, 3], or [-3, 0] for a
removal or simplification; changes to pruning confirmed at LTC, DESIGN
§5.2). Order, with the reason:

| # | Component | From | Kind of test | Why this position |
|---|---|---|---|---|
| 1 | Training-only quantization precision: QB = 128 with ±0.99 output clip | S | held-out loss, then STC [0, 3] | zero inference cost, cannot lose speed; settles quantization headroom before anything else |
| 2 | Bootstrap-PST seeding of linear lanes / first layer | XGR | loss curve over the first 10% of training | training-only; a Fork-only originality gain if it helps |
| 3 | Output selector: piece count vs phase octiles vs learned gate G vs G1 | S, AF, XGR | held-out loss, fixed nodes, STC | cheap at inference; independent of data volume; small expected effect, so early and quick |
| 4 | Exposure plane X (then X-lite if X gains at fixed nodes but loses after speed) | XGR | offline pre-test, fixed nodes, STC + LTC | the cheapest attack-relation feature on offer; must come **before** threat inputs, since threats would make it redundant |
| 5 | Region count and map (fitted θ steps; hand map vs fitted) | AF, XGR | learning curve (AF §4.4), then LTC | depends on data volume; revisit each generation |
| 6 | Width (sweep per S §2.8 criterion) | S | LTC | the confirmation stage already does one step; repeat as data grows |
| 7 | Small-layer activations; L1 width; pairwise on/off (only if the winner has a body) | AF | loss sweep, then STC + LTC | body-internal; meaningless for single-layer winners |
| 8 | Revision head R (with the corrected QR) | XGR | offline ρ test, then RFP-with-m STC [0, 3] and LTC; futility next | it scales search margins, so it must follow the Phase 4 margin retune; fits any frozen net |
| 9 | Threat inputs (AF's target-centric encoding; full pair encoding as fallback) | AF | fixed nodes, STC, LTC, later Phase 6 threads | needs ≥ 2.5 B positions and the hardest incremental code; after X, and then test removing X |
| 10 | Pawn-pair inputs | AF (growth step) | STC + LTC | no isolated evidence (KB §1.7); late |
| 11 | Speed-only levers: refresh cache variants, int8 FT storage, VNNI dot path, in-register AVX-512 update | S, AF | A/B harness with bench unchanged (DESIGN §7), non-regression SPRT only if search changes | not Elo questions; run whenever profiles point at them |
| 12 | Mirroring removal | all | [-3, 0] | every design uses it and the KB calls its cost "hardly measurable"; lowest priority |
| — | Data-side: time-matched labelling (AF), capture-filter relaxation for exposed captures (XGR) | AF, XGR | held-out loss on a slice, SPRT | step 7 analyst's queue, not architecture swaps |

---

## 6. Bake-off protocol and the parity test

### 6.1 Equal positions seen, not equal GPU hours (adopt AF's suggestion)

GPU time is not the binding constraint at bake-off sizes (each entry trains
in roughly 1-7 GPU h; the week has 30); data is. Equal positions seen
compares architectures. So: the same shards, filters, λ and fitted S; the
same schedule shape and **about 6 B positions seen for every entry** (about
9 passes over 0.7 B); GPU hours recorded per entry; each entry's held-out
loss checked for a plateau at the end (AF's stop rule as a check, not as a
per-entry budget). If one entry is still improving clearly, extend all
equally. Confirmation-size training must also be shown to fit the Kaggle
week.

**Training noise.** bullet runs are not reproducible (clock-seeded shuffle,
phase4-pipeline §1.4), so one training per entry carries seed luck. Train
S-512 twice (cheap) and play the two against each other (2,000 games at
STC). If they differ by more than about 10 Elo, bake-off margins below that
mean nothing and the top two need repeated trainings.

### 6.2 Eval-scale normalization

Each net's output scale depends on its training (KB §6.3), and the Phase 3
margins were tuned on the bootstrap's scale. Before any bake-off game,
rescale every entry's S_out so its mean |eval| on a fixed position set
equals B0's. Otherwise the margins, not the architecture, can decide a
pairing. The margin retune follows the winner (DESIGN §5.2 QC 6).

### 6.3 Stages and SPRTs

- **A. Sanity**: each entry against B0 at STC, gainer [0, 5]. A fail sends
  the entry back to training, not out of the bake-off.
- **B. Diagnostics (no SPRT)**: a fixed-node round robin (about 1,000-2,000
  games per pair at a node budget near STC's per-move nodes) for the
  accuracy term; `fork bench` nps on the 7600X3D with datagen paused; the
  held-out loss of each quantized net through Fork's inference (AF's
  `fork heldout` idea, game-level split).
- **C. Decisive pairings** (§3's order), the more complex design against the
  simpler on gainer bounds [0, 5], **at STC and at LTC; LTC decides** (DESIGN
  §5.2: no rejection on STC alone, and TCEC plays far longer). Caps 20,000
  games at STC and 10,000 at LTC; an inconclusive result keeps the simpler
  design ahead and is logged.
- **D. Confirmation** of the winner at its large size (SPRT against its
  small version and the current net, STC and LTC). If the top two ended
  within about 10 Elo at LTC or LTC was inconclusive, **confirm both** (one
  extra large training), because small sizes favour designs whose edge is
  speed over designs that scale with data.
- **Builds**: scalar + AVX2 for every entry (the SPRT target is x86-64-v3 on
  GitHub runners and AWS; DESIGN §5.2). AVX-512 and VNNI are written only for
  the winner in step 5. The bake-off then slightly understates AF on TCEC
  hardware if VNNI exists there (UNVERIFIED); §6.4's speed price lets that be
  costed.

### 6.4 Speed price: time odds (adopt S's method, run with B0)

S's 2:1 time odds gives a large, cheap signal with no engine change; XGR's
25% busy-loop slowdown is a smaller effect (about 0.4 doublings) that needs
many more games and a code hack. Adopt: **B0 against itself at 2:1 time
odds, 2,000 games each at STC and LTC** (fixed length, not SPRT), on the
GitHub shards. Use B0, not the bootstrap: the engine's Elo per doubling
depends on its strength and draw rate, and the bake-off entries resemble B0
far more than the bootstrap. Optional: 1.5:1 at STC to check that the
log-linear assumption holds over the 0.25-0.8 doubling range that separates
the entries, and a smaller run at 120+1.2 for the trend toward TCEC.

Use: with the fixed-node results of stage B, S's exchange-rate model
predicts each STC and LTC pairing. Agreement makes the extrapolation toward
TCEC a reasonable tie-break input; disagreement means the model (which
treats the accuracy term as time-control-independent, §1.5 S-3) is not good
enough to extrapolate. It never replaces an SPRT.

### 6.5 Many-thread and cache behaviour

Not measurable locally (6 cores, 96 MB L3). Optional, owner-approved: run N
concurrent single-thread `fork bench` processes on an AWS c7a instance
(Zen 4 EPYC, smaller L3 per core complex than the X3D; specifics
UNVERIFIED) for each entry, to see per-thread nps under shared-cache
pressure. Minutes of compute. Otherwise this waits for Phase 6.

### 6.6 The parity test (DESIGN §5.3 deliverable 6): what to adopt

**The problem: a worst-case bound passes by construction.** Step 0's bound,
AF's and XGR's per-position "half-step" bounds all assume every rounded
weight is off by half a step in the worst direction. For B0 (768 → 256
CReLU): Δacc ≤ 33 × 0.5/255 ≈ 0.065 per lane; through the output layer that
is Σ|w_out| × 0.065 over 512 terms, about 3.3 output units at an assumed
mean |w_out| of 0.1, times S (a few hundred cp): **of the order of 1,000 cp**
(*estimate*). Wider nets and bodies make it worse. The R-int-against-T leg
is the only leg that checks the converter (F and R-int both read Fork's net
file), so a converter error below that bound would pass. The step 0 spec's
own mutation cases would likely expose this at build time (a single
corrupted weight probably stays under the bound). S's critique is right.

**S's proposal, and its own trap.** S compares R-int with Rq, a float model
on dequantized weights, and computes the quantization loss Rq − R-float per
position. That is sound **only if Rq's integers come from `weights.bin`
through code independent of the converter**. If Rq were built from Fork's
net file (or from the converter's own quantizer), R-int = Rq would hold by
construction and every converter error would be absorbed by the "computed
loss" term of S's gate. S's gate also accepts any size of quantization loss
by itself; S's p99/max checks are only alarms.

**Adopt (for B0 and every later net):**
1. **Quantization leg (Q, new, exact).** `reference.py` quantizes
   `weights.bin` itself (factoriser merges and transforms in f32 in bullet's
   order, f32 multiply, bullet's rounding rule read at the pin, Rust-style
   half away from zero likely; never `np.round`, which rounds half to even),
   in code separate from `convert.py`. Its integers must equal bullet's
   `quantised.bin` and the tensors of Fork's net file, integer for integer.
   This checks bullet's quantizer, the converter and the layout, three
   implementations against each other.
2. **F = R-int exactly** (unchanged), every path, from FEN and incrementally.
3. **R-float = T within 0.01 cp** (unchanged; the GPU leg, a few hundred
   positions).
4. **Feature leg (from XGR).** Active index sets (regions, mirroring,
   buckets or stacks, any computed features) from Fork's C++, from the Rust
   input type (a CPU-only test binary; bullet builds without GPU features)
   and from `reference.py` written independently (python-chess for attacks)
   must be identical, on the parity EPD **and 1 M positions sampled from
   Fork's data**. It costs no GPU, so it covers far more cases than T can.
   Required for any design beyond plain 768.
5. **Quantization loss gate.** |R-int − R-float| computed exactly per
   position (no bound). Its max and p99 must stay under thresholds set per
   architecture at its first net, recorded in the net registry, changed
   only with the owner's approval. `fork netcheck` refuses a net over them.
   For single-layer designs, S's proven |R-int − S·Rq| < 2 cp is kept as an
   assertion (with leg Q it costs nothing).
6. **Mutation cases, each tied to the leg that must catch it**: corrupted
   weight (Q), transposed tensor (Q), missing `.round()` (Q), wrong mirror
   side in C++ (F = R-int or feature leg), wrong region or bucket map
   (feature leg), wrong feature rule such as XGR's ≤ for < (feature leg),
   swapped stack (F = R-int), too-coarse QB (loss gate).
7. **Drop the worst-case bound** from the gate. If it is kept at all, only
   as a report.

The CI placement of step 0 stays: F = R-int as a ctest on every preset; the
Python legs when `src/eval/**`, `nets/**`, `tests/nnue/**` or `tools/nnue/**`
change; the 1 M-position feature leg nightly or on change.

---

## 7. Open questions for the owner

1. **Bake-off sizes**: all entries at width 512 (judge's recommendation,
   cleaner factorial), or each at half its confirmation size (S-256, as S
   proposed)?
2. **Implementation budget**: four candidate implementations (scalar +
   AVX2 + parity each) before the bake-off, or three (drop XGR to the swap
   list, or drop H)?
3. **Decider**: LTC decides each pairing, STC informs (judge's
   recommendation), and an inconclusive pairing keeps the simpler design?
4. **Compute**: approve the time-odds games (about 4,000 games, plus the
   optional 1.5:1 and 120+1.2 runs) and the training-noise pair, on the
   GitHub shards; approve an AWS many-core nps run (§6.5)?
5. **Originality**: run a design-level screen (concept, match / no match)
   for X, G, R, the fitted regions, the phase-octile stacks and the
   target-centric threats, in addition to the name and constant screens?
   And is originality a tie-break (prefer XGR or AF's distinctive parts when
   Elo is equal)?
6. **bullet at the pin**: one research task reading bullet's code (MIT) to
   settle §1.4's unconfirmed features and the rounding rule, before the
   bake-off spec?
7. **Quantization-loss gate**: may the implementer set each architecture's
   thresholds from its first net, with the owner approving?
8. **Timing**: the bake-off waits for G1 (about 0.7 B positions in all;
   several days of datagen after B0, unmeasured)?
9. **Two nets**: if a slower net wins the playing slot, may Fork keep a
   faster net (e.g. S) for datagen, with two inference paths to maintain?
10. **Threat inputs**: are they in scope for Phase 4 at all (AF-LT needs
    ≥ 2.5 B positions and the hardest incremental code), or a Phase 4+
    improvement-pass item?

---

## 8. UNVERIFIED items in this judgement

| Item | Why |
|---|---|
| Every nps factor, ns and µop count | operation-count models; the common model uses S's assumptions; `fork bench` replaces them |
| Zen 4 / Zen 4c 512-bit execution; EPYC 9754 cache sizes (1 MB L2 per core, 16 MB L3 per 8 cores); VNNI on TCEC's CPUs | model knowledge, no AMD source opened |
| bullet's T4 throughput; how it gathers factorised inputs; two trainings per T4 x2; quota counting | K5, K17, K18/K22 measure them |
| Every bullet feature in §1.4 marked unconfirmed, and `.round()`'s tie rule | read bullet's code at the pin |
| Datagen positions per day | unmeasured; the KB's 100-300 M/day was derived for a small net at 5k nodes |
| Typical revision-head weight magnitudes (order 10⁻³) | judge's estimate from the target scale; the fit would show it |
| B0's worst-case parity bound "of the order of 1,000 cp" | illustrative, from an assumed mean output weight of 0.1 |
| Elo per speed doubling for Fork; training run-to-run noise | §6.4 and §6.1 measure them |
