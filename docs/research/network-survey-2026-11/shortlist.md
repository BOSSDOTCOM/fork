# Network changes for Fork: cost estimates and a ranked shortlist

Clean-room network survey of 2026-11-14 ([README](README.md)), the brief's items 2 and 3, written for the
owner's order of 2026-11-14 (about 7:30 PM EST). For the owner's review; nothing here is built, run or
decided.

## 1. How to read this file

- **Sources.** Only the survey's own files (README, [matrix.md](matrix.md), [speed.md](speed.md),
  `records/`) and Fork's repository. No engine page, source or file was opened for this file, and no web
  page.
- **Fork's figures** come from Fork's measurements: the round 3 reports (proto/r3-king-a, -b1, -c, -d),
  `docs/research/network-novelty-2026-11-14.md` (evidence E1 to E13), ideas.md (40, 41, 175 to 184),
  docs/nets.md, DESIGN.md (the round 1 bake-off record, the decisions log of 2026-11-14) and the design
  proposal `docs/kb/phase4-designs/design-accuracy.md` (commit a6cbd4c). Three round 3 results come from
  the coordinator's brief of 2026-11-14 and are not yet in the decisions log at b7ea9bf: H512+PP (option a:
  4 king regions, M4, with the refresh cache) passed its STC SPRT against r8ceplo2 at **+8.04 ± 4.75** and
  is being promoted; x_lower gained **+17.60** at fixed nodes against its control but was **−3.16**
  speed-adjusted against r8ceplo2; idea 182 (move-delta rows) was not adopted (**−2.5%** on the EPYC
  runners).
- **Peers' figures** are each engine's own, as the survey's records cite them; they are priors, not
  predictions.
- **"(est.)"** marks every figure that is neither a Fork measurement nor a survey record. All are my
  estimates, UNVERIFIED.

### The units (Fork's cost lesson)

- **Speed price:** 1.72 Elo per 1% nps, so a change at nps ratio r must gain **−118·log2(r)** Elo at fixed
  nodes (FN) to break even. For reference: r = 0.98 needs +3.4; 0.97 +5.2; 0.95 +8.7; 0.944 +9.8 (the
  design report rounds it to +9.9); 0.93 +12.4; 0.92 +14.2; 0.90 +17.9; 0.85 +27.7; 0.80 +38.0;
  0.75 +49.0; 0.70 +60.7; 0.60 +87.0.
- **What costs speed (E1, E2):** rows cost, and finding mostly does not. The network was 47.6% of cycles
  in speed sprint 3 (the accumulator update 26.3%, the output pass 3.4%; 3.09 rows per perspective
  update); the fused update then removed 31.4% of instructions, and the engine has not been profiled
  since, so today's network share is UNVERIFIED (about 40% by that arithmetic, speed.md). King-window
  machinery with every row suppressed ran at 1.005; its rows took it to 0.784. The exception is a
  finder run at every evaluation: the exact exposure finder costs about 6% and its rows about 7%;
  idea 175's state finder cost 7-8%.
- **Effort unit (EU):** an engineering day, 8 GitHub-hours, 10 GPU-hours or 10 CPU-hours. One STC stage
  is about 18 minutes, a fixed-node screen about 40 minutes, a 360-superbatch seed about 2.2 T4 GPU-hours
  and a 60-superbatch fine-tune about 0.4 (network-novelty file, cost units).
- **Data per weight:** Fork's own anchor (design-accuracy.md §2.1): a first-layer row is touched once per
  sample in which its feature is active, about 28 active pieces per perspective, so
  touches per row = positions × 2 × 28 / rows. B0 had 14.6 M at 200 M positions; the design kept every
  region within a factor of about four of that (3.6 M or more). The design itself calls it a heuristic,
  not a law. Fork's data is about **1.80 B saved, 1.17 B kept** (8c plan, g4s2), and grows by about
  **150-211 M kept per retrain cadence** (the 8c plan's cadence rule of 150 M, met with about 211 M).
  The 8b-to-8c cadence took about four days (est. for future cadences).

## 2. The three findings, applied to Fork

### (a) The narrow single-layer body against the peers' wider bodies with a head

- **What the survey shows.** 33 of the 42 NNUE engines with a published body have a head after the
  accumulator, nearly all 16 -> 32 -> 1 (or 32 -> 32 -> 1) in 8 stacks by piece count, on accumulators
  of 640 to 2048 whose halves are multiplied pairwise. The nine single-layer nets are all 1024 or wider,
  and all but Alexandria rank 24th or lower. No listed engine publishes a single-layer net as narrow as
  Fork's 512 (matrix.md §4, items 1-2). Heads gained +6 to +30 when added (PlentyChess +13.6 STC / +8.1
  LTC; Reckless +27.8 FN, +8.45 at 10+0.1, +13.5 at 60+0.6; Incipit's first head +7.3 at 3.4 B
  positions; Raphael −3.7 STC, +6.6 LTC; several lost at STC and passed at LTC; records B, C, F).
- **What it means at Fork's prices.** Widening the single layer is the expensive way to add capacity: the
  update and the output pass both scale with width, so 768 is about 0.82-0.86 and 1024 about 0.68-0.75
  (est., from a network share of about 40%; Fork's round 1 record, not an A/B: S-512 ran at 0.78 of B0's
  256-wide nps). They would need +26 to +34 and +49 to +66 FN. The peers' record on wide single layers
  is mixed at best (pawnocchio's 1024 lost at every single-thread control; Berserk reverted a wide single
  layer; JustBot's 1024 −4.9 STC, +8.9 LTC). The head is the cheaper way: pairwise halves the dense
  layer's input, and a sparse int8 first dense layer skips most of it.
- **AF-S, and what is different now.** AF-S (round 1-2) had pairwise products and an int8 first dense
  layer evaluated densely, on 4 fitted king regions trained from scratch; it ran at about 0.75 of H-512
  (round 1's bench nps beside data generation, 1.66 M against 2.21 M, not an A/B), had a quantisation
  loss of 23.6 / 20.9 cp in the dry run and 32 cp in the survey's record, gained +10.43 FN and lost
  −48.52 and −55.85 at STC. Five things differ now:
  1. **Sparse evaluation with a neuron permutation** (and often a sparsity penalty in training), which AF-S
     never had: Raphael 1.12x in all, Incipit 1,912 against 2,345 cycles per node, Stockfish up to +10%
     nps (speed.md A2-A4). Coda's warning stands: at 58-67% non-zero the sparse kernel was 1.8 to 2.4
     times slower than dense, so the sparsity must be measured before the kernel is chosen.
  2. **The rounding loss has known answers:** train on the integer grid (Fork's `--qat` is built, its
     validation never run) or keep the small later layers in float (Viridithas, Coda, Reckless, Incipit).
  3. **Data:** AF-S trained on 93.5 M positions (round 1) and 416 M (round 2); Fork now has 1.17 B kept.
     H-512's diagnosed failure was overfitting at about 1.7 M touches per row (DESIGN.md, round 1 record).
  4. **The body:** AF-S carried four fitted regions trained from scratch; a head now sits on a warm,
     tested body (S512+PP or H512+PP), though a head cannot be warm-started function-preservingly.
  5. **The gate is priced in advance:** the speed price lets a speed prototype kill the head before any
     training, which round 1 could not do.
- **What is not different.** Fork's update kernel is already fused and instruction-bound, so the head's
  cost is added to a smaller total than in round 1, which makes its relative price larger, not smaller
  (est.). The engine still has AF-S's dense int8 path (architecture 4 in `net_shape.hpp`), the natural
  base for a sparse prototype.

### (b) Threat inputs need incremental updates, int8 rows and lazy updates before they can pay

- **The peers' record** (speed.md A7-A11): every engine that reports it lost speed first and needed
  incremental updates from a per-move list of changed threats, int8 threat rows and lazy threat updates;
  every one cut its accumulator when threats arrived (to 384-1024) and every rated threat net has a head.
- **Fork's two threat nets were unfinished by that record.** S512cl summed its contact and link inputs from
  scratch at every evaluation: 0.195 of the default's nps, 82% of its time in those inputs, a 53.9 MB
  table (ideas.md 41). S512+X added its exposure rows at every evaluation: 0.818 (E4). Fork's own estimate
  for incremental contacts was 0.5-0.6 (ideas.md 41, UNVERIFIED).
- **x_lower is the per-evaluation form that passed the gate:** 0.932-0.934, found at every evaluation from
  the enemy's pawn, minor and rook attacks only, its rows added into a copy of the sums. Its +17.60 FN
  against its control fell short of its speed price (−3.16 speed-adjusted against r8ceplo2).
- **Which of the peers' three fixes would help x_lower.** Lazy: x_lower is already computed only when an
  evaluation needs it. Incremental: the round 3 report found that the lazy walk has no board at
  intermediate plies, so attack maps would have to be kept eagerly at every push (about 1.4 pushes per
  evaluation), and the saving is bounded by the finder's share, about 6% for the exact rule and less for
  x_lower's cheaper rule. int8 rows: Fork's update is instruction-bound at 1.41 MB of rows (int8 rows lost
  0.9% with +11.6% instructions, speed sprint 3), so int8 pays only when the table outgrows the cache,
  as the peers' 50-250 MB tables do. **So the peers' fixes target a memory-bound full threat set, not
  Fork's compact plane.** For x_lower the remaining levers are fewer rows (the side to move's pieces
  only) and narrower rows (a 64-column block): idea 178 (shortlist rank 2).
- **A full threat set (about 60,000 inputs) does not fit Fork's data yet.** With about 20 active contacts
  per perspective (est., from S512cl's 26.5 active contacts and links) over 50,416 contact inputs, 1.17 B
  kept positions give about 0.9 M touches per row (est.), a quarter of the anchor's floor. It would need
  about 4.5 B kept to reach the floor and about 18 B to reach B0's 14.6 M (est.); the peers who use full
  sets train on 15-37 B or on hundreds of billions. It would also need the head and, by the peers'
  record, a width Fork already has (speed.md A11: "Fork is already at the width the others cut down to").

### (c) Data scale against bucket count

- **The peers** (matrix.md §3): Hobbes, Minke and Raphael merged their first 4 king buckets at 1.7 B,
  2.5 B and 3.0 B positions (Raphael's failed STC on less), 8 at 5-6.9 B and 16 at 10.7-17 B. In touches
  per row (Fork's formula, est.): about 31-55 M at 4 buckets, 46-63 M at 8, 49-78 M at 16. They kept
  touches per row roughly level as they added buckets.
- **Fork:** H512+PP's M4 regions at about 1.17 B kept give about 21 M touches per row on average
  (est.). That is about 0.7 times the lowest peer figure (Hobbes at 1.7 B), and far above round 1's
  failed H-512 (about 1.7 M, overfitted). So **the promotion is consistent with the peers' 4-bucket
  threshold**, a little below it. Two Fork choices plausibly lower the threshold (est., not separately
  measured): the warm start (every region starts as r8ceplo2's rows and learns only differences) and the
  hand-drawn map.
- **When Fork's data supports the next steps:**

| Step | Touches per row at 1.17 B (est.) | Kept data for M4's 21 M per row (Fork's rule, est.) | The peers' merge point (record) | Cadences from today at 150-211 M (est.) |
|---|---|---|---|---|
| 4 regions (M4) | 21 M | 1.17 B (today) | 1.7-3.0 B | 0 |
| 8 regions (M8) | 10.7 M | about 2.3 B | 5-6.9 B | about 5-8 by Fork's rule; 18-38 by the peers' |
| 16 buckets | 5.3 M | about 4.7 B | 10.7-17 B | about 17-24 by Fork's rule; 45-106 by the peers' |

  Fork's "kept" is after its training filter; the peers' figures are not always stated on the same basis
  (Integral's 16.7 B is unfiltered), so the comparison is loose by up to the 1.5x between Fork's own
  saved and kept counts.

## 3. Item 2: the cost estimate of every candidate the survey surfaces

The ratio r is against the default the change would sit on (H512+PP once promoted; for data and training
changes there is no runtime cost). "FN needed" is −118·log2(r). "Phase-scale fit" asks whether the change
addresses idea 180's finding: in Fork's own STC games the score-to-result scale k falls from 106.9 cp in
output bucket 0 to 55.4 cp in bucket 7 (LTC 116.9 to 51.9), but it is **flat at 69-74 cp in the
20,000-node data games**, and the queens-on/off gap is largely phase mix. Idea 175 added that
pawn-relation states explain about 0.006% of the residual. **The labels therefore do not carry the
phase-dependent scale.** A network trained on them inherits their flat scale whatever its architecture, so
only label-side or inference-side changes (idea 180's head rescale and label arm) address the scale
directly. A change in the data's composition can change what each phase head sees.

| # | Candidate | nps ratio on Fork's body (basis) | FN needed | Data need | GPU and engineering cost | Phase-scale fit | Peers' evidence (survey) |
|---|---|---|---|---|---|---|---|
| C1 | **8 king regions (M8)**, a refinement of M4 (so a function-preserving warm start from H512+PP) | 0.924 measured against S512+PP; about **0.979 against H512+PP** (ratio of two measurements in one session, est.) | **+3.6** | 10.7 M touches per row at 1.17 B: about 2.3 B kept by Fork's rule, 5-7 B by the peers' | prototype exists (proto/r3-king-a, a1 M8); port into architecture 9, about 1 day; one session arm, 2 seeds, about 4.4 GPU-h; screens and STC | Neither. M8's stated reason (the queens-on middlegame) is weakened by idea 180's finding | 8-16 buckets is the common range; Minke's 8 buckets with 8 output buckets +9.4 FN, +9.0 STC; the steps are rarely separated |
| C2 | **16 king buckets** | 0.92-0.96 against H512+PP (est.: Incipit measured 16 buckets 8.6% slower than 4; Fork's M4-to-M8 step cost about 2%) | +7 to +14 | 5.3 M per row: about 4.7 B by Fork's rule, 10.7-17 B by the peers' | as C1 plus a new map; a table of about 13 MB (est.) against TCEC's 2 MB of L3 per core (idea 182's −2.5% on the EPYC runners is the warning) | Neither | Incipit: 32 against 16 only +2.8, went back to 16 |
| C3 | **Wider single layer, 768** | 0.82-0.86 (est.: update and output scale with width; network share about 40%) | +26 to +34 | touches per row unchanged; 1.5x the weights; fits 1.2 B by the design anchor | engine width is a build constant (`NetHidden`); trainer flag; from-scratch or net2net-style widening, 2 seeds about 5-6 GPU-h (est.) | Neither | Hobbes 512 to 768 with threats +25.31 at 20,000 nodes, +10.11 LTC; single-layer nets are all at least 1024 and rank low |
| C4 | **Wider single layer, 1024** | 0.68-0.75 (est.) | +49 to +66 | 2x the weights; the design anchor's widest fit at 1.5 B (design-accuracy §2.3) | as C3, about 6-8 GPU-h (est.) | Neither | pawnocchio's 1024 lost at every single-thread control; JustBot's 1024 −4.9 STC, +8.9 LTC |
| C5 | **Pairwise-multiplied halves** on the single layer (no head) | 0.99-1.01 (est.: it only changes the output pass, 3.4% of cycles) | 0 to +2 | none new | not function-preserving from SCReLU, so a from-scratch arm: 2 seeds plus a same-recipe control, about 6.6 GPU-h; engine and trainer about 1 day | Neither | Raphael +4.2 STC at equal width; Lizard +1.6 STC; PZChessBot +1.06 on non-regression bounds before its head. Its value is as the head's entry |
| C6 | **16 -> 32 -> 1 head**: pairwise into a sparse int8 first dense layer with a neuron permutation, 8 stacks, QAT or float later layers | **0.85-0.92** (est.: AF-S's dense form about 0.75 of H-512, not an A/B; the peers' sparse, permuted, penalised forms 1.12-1.23 times faster than dense) | **+14 to +28** | head weights about 65,000 plus small layers (est.); each stack sees an eighth of the data, which is ample; the 1.2 B limit is the accumulator's, as today | the largest build: sparse kernel with scalar reference, AVX2 and AVX-512 paths and an equivalence test (3-4 days, est.); trainer (AF-S's architecture exists; permutation, sparsity penalty and QAT validation, 1-2 days); from-scratch training, 2 seeds plus control with QAT, about 8-10 GPU-h (est.) | Neither for the scale (it inherits the labels'); its 8 stacks give each phase a nonlinear head | 33 of 42 have it; +6 to +30 when added; often lost at STC and passed at LTC |
| C7 | **Full threat set, incremental + int8 + lazy** (about 50,000-60,000 inputs) on the 512 single layer | 0.55-0.70 (est.: idea 41's 0.5-0.6 for incremental contacts; 4.2 contacts change per move against 3.09 piece rows today) | +61 to +102 | about 0.9 M touches per row at 1.17 B (est.): about 4.5 B to reach the anchor's floor, about 18 B for B0's level | the largest of all: incremental changed-threat lists, int8 rows widened as added, then by the peers' record a head (C6); 27-54 MB tables against TCEC's caches | Neither (tactical knowledge; idea 175 found little residual in pawn-relation states) | PlentyChess +45.5 FN but −3.1 STC at first; Reckless threats +53.4 FN, +4.2 STC, +6.9 LTC; every rated threat net has a head and a cut width |
| C8 | **Compact threat plane: x_lower** (as trained in round 3) | 0.932-0.934 measured | +11.6 to +12.0 | 640 rows; trained on today's data | built (nets/r3-xlower, architecture 10) | Neither | Fork's own: +17.60 FN against its control, −3.16 speed-adjusted against r8ceplo2 |
| C9 | **Side-to-move liabilities plane in a 64-column block** (idea 178; x_lower's rule, the mover's pieces only) | 0.965-0.975 (the proposal's estimate, from round 3's split: finder about 6%, rows about 7%) | +4.3 to +6.1 | about 20,000 weights (proposal); not data-limited, since x_lower trained on the same data | x_lower's code plus a side filter, a column range and its `net_file` bound; speed prototype on proto/r3-king-c's code 0.5 day; one session arm, about 4.4 GPU-h | Neither | none in the survey for a side-to-move-only plane (its novelty is UNVERIFIED); the column block is idea 46's rank 5 and the think tank's H8 |
| C10 | **More pawn-pair inputs**: links at rank distance 2, or the full same/adjacent-file set | R = 2: about 0.96 against R = 1; the full set about 0.914 (both measured on S512r2 before the fused update: 0.859 and 0.818 against R = 1's 0.895; today's ratios UNVERIFIED) | +7; +15 | 1,488 link rows for the full set (DESIGN.md, S512cl); fits | trainer and engine have both forms (the rank limit is a constant); an arm needs a non-zero warm start for the new links, about 4.4 GPU-h | Neither: idea 175's residual study found pawn-relation knowledge explains about 0.006% | 4,560-pair sets in 5 rated nets, 1,488 in ZigQueen, 608 in Incipit (README, finding 2) |
| C11 | **Output buckets by piece count** (instead of Fork's 8 by game phase) | 1.00 | 0 | per head as today | selector change in engine and trainer (0.5 day); a fine-tune arm from r8ceplo2's heads, 2 seeds, 0.8 GPU-h | It re-cuts the axis that idea 180 found carries the scale, but it cannot add the scale the labels lack; the phase selector is already the axis k varies on | the peers' gains (+5 to +45) are for adding output buckets where there were none; Fork has 8 already. Incipit uses 6 so that no bucket holds only positions its tablebase-adjudicated data never records |
| C12 | **QAT** (training on the integer grid) | 1.00 (training only) | 0 | none | `--qat` is built; its validation was retired 2026-11-07. A fine-tune arm 0.8 GPU-h | Neither | Stockfish +4.4 STC. For Fork's int16 net there is little to recover (r8ceplo2's quantisation loss max 9.9 cp, p99 7.8); it is a requirement of C6 and of int8 rows, not a standalone gain |
| C13 | **Larger-teacher relabelling** (a bigger net, used only to relabel, blended with the stored search score) | 1.00 in play | 0 | the teacher's own: it must beat the student at equal nodes on the same 1.2 B, and wider nets overfit sooner (H-512's lesson) | teacher training about 4-6 GPU-h (est.); an engine able to screen it (M8 exists as a prototype; a wider net needs `NetHidden` as a build option, about 1 day); relabelling on the GPU about 1-2 GPU-h (est.); then a student arm | Partial: a teacher's static output has its own scale, not the 20,000-node search's, so it could move the phase-scale either way (UNVERIFIED) | pawnocchio +11 to +12 (a much larger own net), Tarnished +3 to +4, Viridithas distillation +3.7 LTC; Viridithas's relabelling by static output **lost**. Fork's own: deeper labels lost (E5), idea 83 killed |
| C14 | **Piece-count balancing** of the training positions | 1.00 | 0 | none (it removes positions, so slightly less data) | a trainer selection rule (0.5 day); an arm, about 4.4 GPU-h, or a fine-tune pair 1.6 GPU-h | **Partial:** it changes how many positions each phase head trains on, not the labels' scale | Halogen +13.2 LTC; Rebel's net author about +10. Fork's warning: reweighting lost twice (class weights −7.60, idea 52's oversampling) |
| C15 | **Result/score disagreement filter** | 1.00 | 0 | none (it removes positions) | a trainer filter (0.5 day); as C14 | Partial: it removes the positions whose label most contradicts the result; it does not rescale the rest | Halogen +4.0 LTC |
| C16 | **A blend of adjudicated and unadjudicated games** | 1.00 | 0 | new data: one generation part with adjudication off (about 150 M kept, one cadence) | no engine work; a generation setting (fork_datagen `--adjudicate-cp 0`), games about 10% longer (est.: the rule saved 9.3% of g1b's positions), so the same CPU gives about 9% fewer games; the trainer's manifest mix (0.5 day); one arm, 4.4 GPU-h | **Yes, in composition:** Fork's win adjudication (700 cp for 8 plies since generation 2) would have ended 65.7% of g1b's games early in the study that adopted it, so the conversion phase of decided games, the low-phase buckets where STC's k is lowest, is largely missing from the data. The Syzygy endgame slice covers only part of it | Halogen +21 to +25 against either alone (README, finding 10) |
| C17 | **No TT or history sharing between data-generation games** | 1.00 | 0 | none | **none: Fork already does this.** `SelfPlayGame::play` clears the table and the history at every game's start (`src/datagen/self_play.cpp`) | n/a | Raphael +5.8 |

**Reading.** On Fork's price list three groups separate:
- **Free at runtime** (C11-C17): only data and training cost, and C17 is already in place.
- **Cheap at runtime** (C1, C5, C9, C10 at R = 2): under +7 FN to break even. C1 is gated by data, C5
  only matters with a head, and idea 175's finding makes C10 unlikely to pay.
- **Expensive at runtime** (C2-C4, C6-C8): +12 FN or more. The only one with a peers' record of paying on
  a body like Fork's is C6, the head.

## 4. Item 3: the ranked shortlist

Ranked by expected Elo per unit of cost to a full decision, with chance and the dependency on data growth.
"Expected" is chance × central net Elo; every chance and central Elo is my estimate (est.), and the
spread between ranks is within the guesses' error, so the table reads best as three groups: data
hygiene now (1, 3, 4), the threat lesson applied to Fork's own plane (2), and the structural steps
gated by data or speed (5, 6, 7).

| Rank | Addition | Novel for Fork, or established at peers | Cheapest deciding test (the falsifier first) | Cost to a decision | FN Elo needed | Data need | Phase-scale fit | Central net Elo, chance (est.) | Why this rank |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Unadjudicated games in the blend** (C16) | Established at peers (Halogen); new for Fork, which has adjudicated wins since generation 2 | **Offline, CPU minutes:** from the shards' recorded moves, count the plies the 700 cp rule cut and the output-bucket mix of what remains, against the mix of the playing games (the calib-1112 STC set). **Kill** if adjudication removes under 5% of the positions the low buckets (0-2) would hold (est. threshold). Then **a data-only arm:** one part with adjudication off, mixed into the next retrain as one arm, 2 seeds | falsifier 0.1 EU; the arm about 1.5 EU (4.4 GPU-h, 2 FN screens, an STC SPRT, the trainer's mix 0.5 day) plus one cadence of calendar time; generation about 9% fewer games for that part (est.) | 0 | one part, about 150 M kept | **Yes** (composition of the low-phase buckets) | +5, 30% | No runtime cost; the falsifier costs minutes; it is the only candidate that touches the phase-dependent part of the data; one engine's large figure, so the chance is modest. It needs the owner's choice of which generation part runs without adjudication (production is never stopped) |
| 2 | **Side-to-move liabilities plane, 64-column block** (C9; idea 178; Fork's answer to finding (b)) | Fork's own (the side-to-move halving: no relative in the survey, novelty UNVERIFIED; the column block is idea 46's and H8's) | **Offline, CPU minutes:** the mover's exposed pieces' share of r8ceplo2's residual against the opponent's (`exposure_pretest.py` exists). **Kill** if the mover's share is under half. Then **a zero-weight speed prototype** on proto/r3-king-c's code, bench-identical, 20 rounds. **Kill** below 0.95 | falsifiers about 0.6 EU; to a decision about 2.5-3 EU (one session arm beside x_lower's control, about 4.4 GPU-h; 2 FN screens; STC SPRT; trainer 1 day) | +4.3 to +6.1 | not limiting | Neither | +6, 35-40% | The only candidate with a measured Fork signal behind it (x_lower's +17.60 FN); it removes exactly the costs that sank x_lower, the rows and their width. It stacks with H512+PP, after the combined nps is measured (the owner's stacking rule of 2026-11-14). The owner's plan already puts it after x_lower's result, which is in |
| 3 | **Result/score disagreement filter** (C15) | Established at peers (Halogen); new for Fork, whose filter drops checks, tactical positions and extreme scores only | **Offline, CPU minutes:** the share of kept positions whose stored score and game result disagree beyond a margin, by output bucket. **Kill** if under 1% (est. threshold: nothing to filter). Then **a data-only arm** (a 60-superbatch fine-tune pair on r8ceplo2, 2 seeds, or one arm of the next retrain), read on the held-out endgame gate too (E9: result-side changes have raised endgame errors) | falsifier 0.1 EU; to a decision about 1.3 EU; the gain expected (+2 to +4) is inside an FN screen's ±9, so it needs its STC SPRT | 0 | none | Partial | +2, 30% | Cheap and free at runtime, but a small expected gain that only an SPRT can see |
| 4 | **Piece-count balancing** (C14) | Established at peers (Halogen, Rebel's net author); new for Fork in this form | **Offline, CPU minutes:** the kept data's histogram by piece count and by output bucket. **Kill** if every bucket is within 1.5x of the mean (est. threshold: nothing to balance). Then **a data-only arm**, by selection (dropping positions), not by loss weights | falsifier 0.1 EU; to a decision about 1.3 EU | 0 | none | Partial | +3, 20% | The peers' figures are large, but Fork's two reweighting attempts lost (class weights −7.60, idea 52), so the chance is low; it is cheap enough to keep |
| 5 | **8 king regions (M8)** on H512+PP (C1) | Established at peers (8-16 is the common range); new for Fork beyond M4 | **Now, a speed check:** a1 M8 against the H512+PP default, bench-identical (the prototype exists). **Kill** below 0.97. **At about 2 B kept:** M8 warm-started by splitting each M4 region (function-preserving), one session arm beside a same-recipe M4 control, speed-adjusted FN screens, STC SPRT | speed check 0.5 EU now, then about 3 EU at the data point (port 1 day, about 4.4 GPU-h, screens, STC): about 3.5 EU in all | +3.6 (est.) | about 2.3 B kept by Fork's rule (about 5-8 cadences), 5-7 B by the peers' | Neither | +4, 35% | Cheap at runtime and the peers' most regular step, but Fork's data supports it only in a few weeks (est.), and its stated reason (the queens-on middlegame) is weakened by idea 180 |
| 6 | **Larger-teacher relabelling** (C13) | Established at peers (pawnocchio, Tarnished, Viridithas); new for Fork | **The teacher first:** train one larger float net on today's data (for example M8 or 16 regions, which the engine can already prototype) and screen it against r8ceplo2 at fixed nodes. **Kill** if it is not clearly better (under +15 FN, est. threshold): a teacher no better at equal nodes cannot improve the labels. Then a 60-superbatch fine-tune on blended labels, 2 seeds | falsifier about 1.5 EU (4-6 GPU-h, a screen, engine support if needed); to a decision about 3.5 EU | 0 in play | the teacher is the data-limited part: it must not overfit 1.2 B | Partial (UNVERIFIED direction) | +4, 25% | The peers' best figures come from much larger teachers than Fork's data can train well today; Fork's label levers keep losing (E5, idea 83); it improves as the data grows |
| 7 | **The head** (C6, with C5 and C12 inside it) | Established at peers (33 of 42); tried by Fork only in AF-S's dense form; the sparse, permuted form is new for Fork | **Offline first:** the share of all-zero groups of four in a pairwise-activated accumulator on held-out positions (an AF-S net from round 1-2 if its file is kept, else a short pairwise training, 1-2 GPU-h). **Kill** if over 55% of the groups are non-zero (est. threshold; Coda's region, where sparse lost to dense). Then **a micro-benchmark** of the sparse int8 first dense layer at that sparsity against today's output pass (fork_micro), converted to an nps ratio by the network share. **Kill** below 0.90 | falsifiers about 2.5 EU; to a decision about 9-10 EU (kernel 3-4 days, trainer 1-2 days, from-scratch training 8-10 GPU-h, screens, STC, likely an LTC too: the peers' heads often lost at STC and passed at LTC) | +14 to +28 (est.) | not data-limited for the head itself | Neither for the scale; per-phase nonlinear capacity | +8, 20% | The largest ceiling and the survey's main structural finding, but the largest cost and AF-S's failure behind it. Last by expected Elo per unit, but its 2.5-EU falsifier is the cheapest way to learn whether Fork can ever take the peers' shape, and it can run in a quiet window whatever else is chosen |

**Expected Elo per EU** (chance × central / cost to a decision, est.): 1: about 1.0; 2: about 0.8; 3: about
0.45; 4: about 0.45; 5: about 0.4; 6: about 0.3; 7: about 0.15.

**Not shortlisted, and why:**
- **16 king buckets (C2):** about 4.7 B kept by Fork's rule and 10.7-17 B by the peers' record; revisit
  after M8.
- **Wider single layer (C3, C4):** +26 to +66 FN needed; the peers' wide single layers rank low and
  pawnocchio's lost; capacity is cheaper through the head.
- **Full threat set (C7):** +61 to +102 FN needed on Fork's body, about 0.9 M touches per row on
  today's data, and by the peers' record it needs a head first.
- **More pawn pairs (C10):** idea 175's residual study leaves little for more structure inputs to
  explain. If wanted, R36's residual rule on the R = 2 pairs (CPU, half a day; kill under 0.5%) decides
  it cheaply.
- **Output buckets by piece count (C11):** Fork already has 8 output buckets, and idea 180 shows its
  phase axis is the one the scale varies on. Idea 180's head rescale (r8brft1hs) is the test that matters
  on this axis, and it is already ordered.
- **Pairwise alone (C5) and QAT alone (C12):** worth something only as parts of the head and of int8 rows.
- **No TT or history sharing (C17):** Fork already does it.

**Novel for Fork against established at peers.** Rank 2 is Fork's own design (the side-to-move halving
has no relative in the survey; novelty UNVERIFIED). Ranks 1, 3, 4, 5, 6 and 7 are established at the
peers and new to Fork, except that 7 was tried once in a dense form (AF-S).

**Dependencies.** Ranks 1, 3 and 4 are data-only and stack with any body. They can share one retrain as
separate arms (the owner's rule: the control plus arms testing new ideas, 2 seeds each). Rank 2 stacks
with H512+PP after a combined nps measurement. Rank 5 waits for about 2 B kept positions. Rank 6
improves with data. Rank 7 is independent of data but replaces the output layer, so ideas 183 and 184
(the head-side refinements) would have to be re-planned around it.

## 5. UNVERIFIED in this file

- Every figure marked (est.), every chance and central Elo, and the thresholds marked as estimates.
- Today's network share of cycles (not profiled since the fused update).
- The M8 ratio against H512+PP (a ratio of two ratios from one session, not measured directly).
- Fork's data growth per day (from one cadence).
- Whether an AF-S net file from round 1-2 is still kept (not checked).
- Whether the peers' data figures are counted before or after their filters.
- The three round 3 results taken from the brief (H512+PP +8.04 ± 4.75 STC, x_lower +17.60 FN and
  −3.16 speed-adjusted, idea 182 −2.5% on the EPYC runners) are not yet in the decisions log at b7ea9bf.
