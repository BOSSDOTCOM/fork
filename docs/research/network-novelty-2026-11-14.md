<!-- Copied into the repository on 2026-11-14 (owner's instruction) from the proposal file written by Fable that day, unchanged below this note. Its "Snapshot" line says H512+PP and x_lower were in training; at copy time neither was yet (option (a) was built and smoke-tested; x_lower was being built). The ideas are recorded in docs/ideas.md as ideas 175-184 (this file's ideas 1-10, in order), novelty UNVERIFIED; the owner's plan for them is in DESIGN.md's decisions log, 2026-11-14. -->

# Fork: novel network ideas (read-only proposal, 2026-11-14)

**Status.** Proposal only. Nothing was built, run, tested, edited or committed, and no job, queue, GitHub, Kaggle or cloud resource was touched. Every Elo and nps figure that does not cite a logged Fork measurement is my estimate, not a measurement. Every outside citation is from memory and **UNVERIFIED** until someone fetches the primary source. No engine source and no web page was opened. Names here are placeholders: none has been through the name or constant screens.

**Snapshot.** Branch `phase-4`, default net r8brft1 (architecture 8, S512+PP: 768 mirrored piece inputs + 608 pawn links, 512 SCReLU, 8 phase heads). In training today: H512+PP (round 3 option a) and x_lower, beside a same-recipe control.

**What I read.**
- Myself: the four round 3 reports on the proto branches, the UHO/SF19 analysis, the trade analysis, speed sprint 3's profile, the calibration results (lines 1-377 of 583), the novel-ideas file, `ideas.md` entries 13-14, 40-41, 44-59, 62-71, 79-86, 153-161, 167-174, the engine survey's network, speed, training and data tables, the structure-class calibration design (R33), `net_shape.hpp`, `accumulator.hpp`, the output code in `accumulator.cpp`, and the trainer's outline (`tools/train/src/main.rs`).
- Through two read-only sub-readers: both SPRT logs, `transfer.json` and the transfer report, the perf log, all 11 gauntlet summaries, every MORNING and HANDOFF file, the 8c and 8c-early records, and the staleness, tune-build and retrain-8c reviews.
- **Gaps in the novelty check.** The think tank's three files and `DESIGN.md` were searched by key term for each idea, not read in full. The KB was searched the same way. No outside prior-art search was made.

**Cost units** (the project's own). One STC stage = 1,600 games, about 18 minutes. One fixed-node (FN) screen = about 40 minutes. One 360-superbatch retrain seed = about 2.2 T4 GPU-hours; a 60-superbatch fine-tune = about 0.4. One effort unit (EU) = an engineering day, 8 GitHub-hours, 10 GPU-hours or 10 CPU-hours. Speed is priced at 1.72 Elo per 1% nps, so a candidate at speed ratio r must show −118·log2(r) Elo at fixed nodes to break even.

---

## The evidence these ideas lean on

| # | Finding | Source |
|---|---|---|
| E1 | The network is 47.6% of cycles. The accumulator update alone is 26.3%; the output pass is 3.4%. There are 0.524 evaluations per node and 3.09 rows per perspective update. | speed sprint 3 profile; round 3 design report |
| E2 | Rows cost, finding does not. The king-window machinery with every row suppressed ran at 1.005; with its rows, 0.784. For the exposure plane the finder alone costs 6% and applying the rows about 7%. Adding rows inside the output pass was slower than the tiled update. | round 3 reports (b1, c) |
| E3 | Carrying the board in a move's delta is free (the same 1.005 build). | round 3 report (b1) |
| E4 | Every richer net won at fixed nodes and lost on the clock: S512+X +25.67 FN, −30.04 STC at 0.818; XGR +30.70, −34.42; AF-S +10.43, −55.85. Pawn links are the exception: +46.09 FN, +32.67 STC at 0.895. | SPRT log |
| E5 | Training-side levers are nearly spent. 2.5x training −0.43 ± 9.44; idea 80 pooled −0.98; class weights −7.60 (H0); deeper labels lost; seed noise is about ±6 Elo. | 8c-early verdicts, A1 record, SPRT log |
| E6 | Search scores are steeper with queens on. Logistic scale k of score against result in Fork's own STC games: 59.6 cp queens on, 74.1 queens off (ratio 1.24; 1.40-1.49 in the audit sets). The static eval shows much less of it (1.04-1.25). The net trains at S = 88. | calibration results, R1 and R4 |
| E7 | Level queenless positions are dead-drawn but scored as edges. Queenless, score 0-0.5 pawns: 94% draws, actual 0.521 against 0.565 fitted. | calibration results, SPRT-STC queens-off |
| E8 | Against SF19 from 200 advantaged UHO starts: 0 wins. Static +40, search +50, where SF19 says +97.5; level queenless +24 / +17.5 where SF19 says 0. Recent nets sit within 3-4 cp of each other. The edge goes at a median of ply 23, queens on in 146 of 198, material level in 107. Trades are not the cause. | UHO/SF19 and trade analyses |
| E9 | The result fine-tune gained +5.74 STC but raised held-out endgame errors (526 to 612; 732 to 770). The slice-preserving variants removed the drift at equal strength. | SPRT log, ideas.md 70, A1 record |
| E10 | Loss does not predict strength. S512+PP: loss −0.06%, +32.7 STC. S512+X: loss −2.2%, −30 STC. | transfer report |
| E11 | The pawn links' contribution moves by 0.88 of its spread when a piece leaves, so structure knowledge must interact with pieces inside the hidden layer; an additive side term cannot carry it. | think tank, skeptic's note on the side lane |
| E12 | The gap between scores and results grows with search depth: class residuals of −1.5 to −2.3 in 20,000-node data against −4.5 to −6 at STC. | R33 design §7 |
| E13 | Data: about 1.80 B saved positions, about 1.17 B after the training filter (UNVERIFIED for the newest parts). | 8c plan |

Two readings shape the list.
- **E1 with E2:** the price of an input is the number of 512-wide row operations it adds per move. An input that changes *which* row a piece uses, and adds none, is nearly free. Ideas 1, 2 and 4 are built on that.
- **E6 with E12:** the queens-on gap sits in the search score and widens with depth, and Fork's labels are 20,000-node scores. So the labels understate it at exactly the depths Fork plays at. Idea 6 acts on that.

---

## Idea 1. State-folded rows: each piece's row chosen by its own pawn-relation state

**Mechanism.**
- Today a piece contributes one row, indexed by (piece, square). Give each piece a small **state** computed from its square and the pawns only, and index its row by (piece, square, state). The piece still has exactly one row.
- Tier A states (all change only when a pawn moves or the piece itself moves):
  - knights, bishops, rooks, queens: attacked by an enemy pawn (1 bit);
  - knights, bishops: defended by an own pawn (1 bit: outposts and protected minors);
  - rooks: file open, half-open or closed (3 values);
  - king: pawn-shield class, 0 to 3 own pawns on the three files one or two ranks ahead (4 values);
  - pawns: passed (1 bit; on file already as R36's passer candidate).
- Tier B (built only if tier A passes): a **king-pressure bit** for sliders and knights. A bishop, rook or queen has it when its attack set, computed with only the pawns as blockers, reaches the enemy king's 3x3 zone; a knight when it attacks a zone square.
- **Train factored, infer fused.** In training a piece emits its base input plus one shared delta input per set bit, so each delta sees every position where the bit is set. When saved, each variant row is base + its deltas (the king-bucket factoriser's merge, applied per piece).
- Warm start: deltas at zero, so every variant equals r8brft1's row and bench is 5,386,021 / 5ecd49d976e215e1.

**Row operations, against adding the same bits as extra rows.**

| Event | Extra-row form | Folded form |
|---|---|---|
| A piece moves; k bits set before, k' after | 2 + k + k' | 2 |
| A pawn move flips one bit of another piece | 1 | 2 |

Prevalent states (pawn-defended, file state, shield) favour folding; a piece carrying two set bits would cost four extra operations per move in the extra-row form and none here.

**Design principle.**
1. *Data per weight.* Tier A adds about 1,536 delta rows (786,000 weights). The rarest bit is "attacked by a pawn"; its share per (piece, square) is UNVERIFIED and should be counted on one shard first (CPU minutes). The factored form is what keeps rare variants trainable.
2. *Information the net cannot cheaply learn.* Each bit is a conjunction of a piece square and a pawn square. A single 512-wide layer cannot hold the several hundred such conjunctions cleanly. Pawn links were the same kind of knowledge and paid +46.
3. *Fewer is better.* No new active inputs per position: 32 rows at most, as now.
4. *Cheap to update.* No extra row on any non-pawn move.

**Why it fits Fork's evidence.**
- E2 is the cost lesson stated as a design: this adds row *choices*, not rows.
- E11: the bits sit inside the accumulator, so they interact with every piece through the squared activations. The same counts fed linearly into the output (option d's "pieces attacked by pawns", shelter) cannot.
- E8: the edge erodes positionally with queens on. Outposts, open files, the shield and (tier B) which pieces bear on the king are the classical content of such edges.
- E4 with E10: the inputs that survived the clock were structural, long-horizon ones. These states are pawn-clocked like the links.

**Novelty and nearest relatives.** I know of no engine that buckets a piece's row by a per-piece local state; plainly unsure. Relatives: king input buckets and their factoriser (the same fold, keyed by the king square, needing refreshes); queen-routed input buckets (survey H9); threat inputs (extra rows); R36's candidates (passed-pawn rows, minor x supporting pawn, as extra rows); option d's counts; idea 86 (bishop colour complexes).

**nps.** Estimate 0.96-0.98 for tier A, 0.94-0.96 with tier B. UNVERIFIED.
- Non-pawn moves: two bit tests against pawn-attack bitboards for the moved piece; no extra rows.
- Pawn moves (24% of makes on bench, 16% in games): find the pieces on the few squares whose pawn attack or defence changed, and on a file whose state changed; about 0.1 extra row operations per push on average.
- Tier B adds about one pawns-only magic lookup per moved slider, and a re-test of up to seven pieces on enemy-king and pawn moves.
- Table size: 2,816 piece rows + 608 links = 3.5 MB (tier A), inside the 4 MB guardrail. Tier B on all four piece types reaches 5.6 MB and breaks it; on rooks and queens only, 4.5 MB.

**Expected gain and risk.** +8 to +15 at fixed nodes, +6 net at STC (−2 to +12). Chance 40%.
- Main risk: the layer already forms these conjunctions for the common squares, so the residual is small.
- Second: state flips cluster on pawn moves near kings, and the real cost is above the estimate.
- Third: it multiplies with king regions. If H512+PP is promoted, the fused table is regions x states (about 14 MB), so the two are alternatives unless the rare bits stay as extra rows.

**Cheapest falsifier.**
1. Residual study, CPU only (R36's rule): on held-out positions, fit an additive table per (piece, square, bit) to r8brft1's residual against the label. **Kill** a bit that explains under 0.5% of residual variance. About 1 CPU-hour, half an engineering day.
2. Zero-delta speed prototype by round 3's method (bench-identical, 20 interleaved rounds). **Kill** below 0.95. One engineering day, one quiet hour.
3. Only then: two seeds beside a same-recipe control (4.4 GPU-hours), speed-adjusted FN screens, the UHO diagnostic, STC SPRT.

**Changes.** Engine: `net_shape.hpp` (architecture id, state counts), `accumulator.{hpp,cpp}` (`feature_index` takes the state; `FeatureDelta` carries the board on pawn moves and the flip list is found in the evaluation walk, as link changes are), `net_file.cpp` (bound over the larger table), the NNUE suite's incremental-against-refresh walks. Trainer: the state function in Rust, Python reference and C++; delta inputs; `merge_factors` fuses them; `extend_weights.py` appends zero deltas; `convert.py`.

---

## Idea 2. Split-clone columns: part of the hidden layer specialised by queen state, at no speed cost

**Mechanism.**
- Pick E of the 512 hidden columns (placeholder 64 or 128). Keep two copies of them: one used when a queen is on the board, one when none is. The other 512 − E columns are shared.
- A position still evaluates exactly 512 columns, so the update and output cost are unchanged. The net holds 512 + E distinct columns.
- Warm start: permute r8brft1's columns (function-preserving) so the chosen E sit in one block, and start both copies equal. The step-0 net is r8brft1 exactly; training lets the copies diverge.
- When the queen state changes along a line (the last queen leaves, or a promotion), the E-column block is recomputed from the board at the next evaluation: about 30 rows x E columns, the cost of two to four ordinary updates, on well under 1% of moves.
- E is a dial from today's fully shared net (E = 0) to two separate nets (E = 512).

**Design principle.**
1. Each copy sees only its share of the data (roughly half each; the exact split is UNVERIFIED), on E x 1,376 weights: thousands of positions per weight at E = 64.
2. It adds capacity, not information. That is its weak point against the principle.
3. Everything outside the block keeps sharing all examples.
4. No row is added; the block refresh is rare.

**Why it fits.**
- E6 and E8 say the two regimes are judged on different scales and that more data does not move it. Today only the eight output heads can differ by regime; the features cannot.
- E5: capacity is the binding limit, and every way of adding it so far cost speed (E4). This adds it at about 1.0.

**Novelty and nearest relatives.** A novel combination. Nearest: queen-routed input buckets (survey H9), which switch *every* column and need a full refresh and a double table; a separate endgame net (H10); Stockfish's big and small nets (public, concept level); output buckets and layer stacks. This is H9 confined to a column block, with a clone warm start.

**nps.** About 0.99-1.00 (the kernel runs over two segments; the block refresh is rare). Measurable bench-identical with equal copies.

**Expected gain and risk.** +4 (0 to +10). Chance 35%.
- Risk: the net already silences regime-specific columns through the queen rows' large weights, so the copies barely diverge.

**Cheapest falsifier.**
1. CPU, minutes: per-column utilisation by output bucket in r8brft1 (output weight x mean squared activation). It picks the columns and shows whether any are already regime-specific. Unmeasured so far.
2. Trainer-only look: a 60-superbatch fine-tune with and without clones (0.8 GPU-hours for two seeds each); do the copies diverge, and does held-out loss by regime move? Diagnostic only, by the owner's rule on offline metrics.
3. The deciding test needs the engine change: FN screens of both seeds against the same-recipe fine-tune. **Kill:** pooled result at or below 0.

**Changes.** Engine: the row table gets 512 + E columns; the update kernel takes two column segments; a stack entry records which block it holds; block refresh from the position; `net_file`. Trainer: the block as a second first-layer piece selected by a queen-state input (bullet's `select`; UNVERIFIED that it selects a vector chunk); converter; reference.

---

## Idea 3. Banded first layer: each piece family writes to part of the hidden layer

**Mechanism.**
- Split the hidden layer into sectors (placeholder 8 of 64 columns) arranged on a ring. Pawns, kings and links write to every sector. Each of the eight other families (own and enemy knights, bishops, rooks, queens) writes to a run of five consecutive sectors, placed so that every pair of families shares at least two sectors.
- A knight, bishop, rook or queen row is then 320 columns wide, not 512, and its update touches 5/8 of the tiles.
- Two ways to spend it: the same 512 columns at lower cost, or a wider layer (8 x 96 = 768) at about today's cost.

**Design principle.**
1. Fewer weights per row, so more examples per weight.
2. No new information.
3. This is the principle's third point applied to connections: fewer of them, each trained on more.
4. It cuts the rows-times-width product directly, the quantity E1 says dominates.

**Why it fits.**
- E1: the update is 26.3% of all cycles and is instruction-bound on Zen 4 (the int8 rows cut bandwidth and lost 0.9%; the 512-bit build gained nothing). Fewer tiles per row is the one lever not yet pulled.
- A squared activation forms pairwise products, so a column needs only the families whose interaction it models.

**Novelty and nearest relatives.** A novel combination; I have not seen a feature transformer with designed block sparsity. Nearest: idea 46's column-restricted exposure rows (one family, 64 columns); idea 79's nested width; block-sparse layers and structured pruning in ML (Wen et al. 2016, in idea 46's source list); activation-sparsity tricks in multi-layer heads (survey I3), which are a different thing.

**nps.** About +5% to +7% at 512 columns (a 20-25% cut in update work), UNVERIFIED; or a 768-wide layer at an estimated 0.93-0.95 where a dense one would be near 0.85.

**Expected gain and risk.** +6 if the accuracy cost is small (−8 to +12). Chance 25%.
- Risk: three-family patterns (queen and knight against a king) lose columns that see all three, and accuracy falls by more than the speed buys.

**Cheapest falsifier.** The design allows a clean two-part test.
1. *Accuracy, with no engine change.* Fine-tune r8brft1 for 60 superbatches with the out-of-band weights held at zero (after permuting columns to the best-fitting sectors), beside an unmasked fine-tune; play FN screens. Today's engine runs a masked net as it is, since the masked weights are just zeros. About 0.8 GPU-hours, 2 FN screens, 1-1.5 trainer days.
2. *Speed, bench-identical.* The same masked net with a kernel that skips the zero tiles against the kernel that does not. One engineering day, one quiet hour.
- **Kill:** FN loss greater than 1.72 x the measured speed gain in percent.

**Changes.** Engine: per-family column ranges in the update kernels; nothing else. Trainer: either per-weight clamps at zero (UNVERIFIED in bullet) or one first-layer piece per sector with its own sparse input list; the mapper emits per-sector lists; converter and reference follow.

---

## Idea 4. The stand-pat liabilities plane: exposure for the side to move only, in a 64-column block

**Mechanism.**
- Keep the exposure rule (a piece attacked by a cheaper enemy piece, or attacked and undefended), but apply it **only to the side to move's pieces**.
- Add those rows into a 64-column block of the accumulator, not all 512 columns. In training that is two first-layer pieces: pieces and links into 448 columns; pieces, links and exposure into 64.
- The rows are found and added at each evaluation, as in the x_eval prototype; nothing is kept incrementally.
- Two cuts to prototype: L-lower (the x_lower rule, side to move only) and L-exact (the full rule, side to move only).

**Design principle.**
1. 320 active-capable rows x 64 columns = 20,000 weights; data is ample.
2. Quiescence resolves the mover's own captures, so the opponent's exposed pieces are information the search already has. The mover's exposed pieces are what a stand-pat cannot see. Halving the plane this way keeps the half the search lacks.
3. Half the inputs of the full plane.
4. Outside the incremental sums; the rows touch one eighth of the width.

**Why it fits.**
- E2 split the plane's 13.5% cost into about 6% finding and 7% rows. Confining rows to 64 columns removes most of the second half; side-to-move-only removes about half of both.
- E11 says a separate lane loses the threat x piece interaction. A block inside the accumulator keeps it, in 64 columns.
- The dangerous static errors are the mover's: reverse futility and stand-pat both trust the mover's static score.

**Novelty and nearest relatives.** The side-to-move halving is, as far as I know, new for a network input; unsure. The column block is not new: it is idea 46's rank 5 (parked) and the think tank's H8. What has changed since they were parked: the finder is now measured at 6%, not the assumed 13%, and rows are known to be half the cost, so the block's saving is real. Other relatives: x_lower (round 3), idea 46's threat-class heads ("attacks on the mover's pieces"), classical hanging-piece terms.

**nps.** L-lower about 0.965-0.975; L-exact about 0.95-0.96. Reasoned from the round 3 measurements, UNVERIFIED. L-exact still needs the mover's own defence map, so its finder saves less than half.

**Expected gain and risk.** +12 to +18 at fixed nodes if it keeps two thirds of the plane's +25.7; +6 net (−4 to +12). Chance 35%.
- Risk: the +25.7 was measured on S512r2, before the links and three retrains, and came from full-width rows.
- Second: S512+X lost 30 Elo at STC where its speed predicted 8.5, so the plane's fixed-node gain may not transfer.

**Cheapest falsifier.**
1. CPU, minutes (the exposure code and `exposure_pretest.py` exist): how much of r8brft1's residual do counts of the mover's exposed pieces explain, against the opponent's? **Kill** if the mover's share is under half of the two together.
2. Speed prototype on proto/r3-king-c's code. **Kill** below 0.95. Half an engineering day.
3. Then one session beside x_lower's control, read against x_lower's own result.

**Changes.** Engine: the exposure rows' column range; the finder restricted to one side; `net_file` bound for 64-column rows. Trainer: s512x's parts with the side-to-move filter and the two-piece first layer; reference and converter.

---

## Idea 5. A king-offset lane with per-king-square snapshots

**Mechanism.**
- Option (b)'s king-relative offset inputs (1,815 own-king, 2,250 enemy-king), but feeding a separate narrow lane (placeholder 64 columns per perspective) whose clipped squares join the output, not the 512-wide sums.
- A king move changes every offset. Handle it as option (a) handles bucket changes: keep one snapshot of the lane per king square (96 slots of about 224 bytes, 43 KB per thread) and bring it to the current board by the pieces that differ.

**Design principle.**
1. 4,065 inputs x 64 = 260,000 weights, every position exercising about 60 of them.
2. Attack geometry relative to a king is translation-shared: learned on g1, valid on h1. Absolute squares cannot share it.
3. No factoriser needed; the offsets are the sharing.
4. Each extra row operation is one eighth of a full row.

**Why it fits.**
- Round 3's report calls (b) "the design aimed at" unseen attack potential, the queens-on half of E8. It failed only on speed (0.53-0.78).
- E2 put that cost in rows, with free machinery. At one-eighth width the 4.2 to 8.5 extra rows per update become 0.5 to 1.1.
- E11's objection to lanes concerned threat x piece terms. Here attackers, defenders and shelter are all offset inputs, so they interact inside the lane.

**Novelty and nearest relatives.** A novel combination of parts already on Fork's table: option (b), the lazy snapshot refresh (b477ba2), and the narrow side lane (think tank H8, for threats). I found no record of the three together.

**nps.** About 0.92-0.95 at 64 columns with both sets; about 0.96 at 32. UNVERIFIED; the snapshot hit rate decides it.

**Expected gain and risk.** +5 (−6 to +12). Chance 25%.
- Risk: its value is unproven anywhere (ideas.md 157); three implementations to keep in parity; a lane cannot interact with pawn structure in the main layer.

**Cheapest falsifier.** A zero-weight speed prototype on proto/r3-king-b's machinery plus the snapshot port: 1.5 engineering days, one quiet hour. **Kill** below 0.93. Training only after the owner sees that number.

**Changes.** Engine: a second small sum per perspective and king set, its snapshots, the output over 2 x (512 + lane) values. Trainer: the offset feature function (Rust, Python, C++), a second first-layer piece, concatenation.

---

## Idea 6. Depth-extrapolated class calibration of the labels

**Mechanism.**
- From Fork's own games at several budgets (20,000-node data games, STC and LTC SPRT games), fit for each class c a monotone map g_c from search score to the score that predicts results. Classes: queen state x phase band, plus R33's structure classes.
- Fit the trend of each class's map against search depth and extrapolate one step, to the budget Fork plays at.
- Rewrite each stored score s as g_c(s) in a derived shard, then build the usual TD(0.9) targets on the rewritten scores. The result terms are untouched.
- The fit has a few dozen parameters estimated from millions of positions, so it adds no label noise.

**Design principle.** No inputs, no weights, no inference cost. It changes what the existing weights are asked to learn.

**Why it fits.**
- E6 and E7 are measured in Fork's own games: queens-on scores mean more than the labels say, and small queenless scores mean almost nothing.
- TD(0.9) cannot correct this. In a long drawn ending the result's weight after 100 plies is nil, so "level queenless positions are +20" is a fixed point of the labels.
- E9: the result fine-tune moved the net toward results and gained +5.74, at the price of noise (about 1.5 independent results per game) and endgame drift. This takes the class-level part of that signal, which is nearly noise-free, and leaves the per-position part to the search.
- E12: the gap grows with depth, so labels made at 20,000 nodes understate it for the search that will use the net.
- By construction it moves the UHO diagnostic in both declared directions.

**Novelty and nearest relatives.** A novel combination. Nearest: R33 (the same fit, applied as an inference-time scale on structure classes; designed, not built); material-based eval scaling (survey F10, never tried by Fork), the hand-written inference form; the result fine-tune (idea 70); the per-class lambda arm (idea 85), which changes horizon, not level; idea 83 (killed), which regressed toward a deeper search by the same net and so shared the bias this one removes. The label side and the depth extrapolation are the parts I did not find on file.

**nps.** None.

**Expected gain and risk.** +3 (−2 to +8). Chance 40%. It can correct the level of the evaluation by class; it cannot teach which moves keep an edge.
- Risk: class-level interventions have hurt before (class weights, −7.60).
- Second: the gain may show only against stronger opponents, which self-play screens underread (transfer 0.48-0.65).

**Cheapest falsifier.**
1. CPU, under an hour: extend the calibration study's pipeline with a split by output bucket and queen state at each budget.
2. No training: scale each output head of r8brft1 by its fitted ratio (an edit of the net file, within the loader's weight bound) and play one FN screen and the UHO diagnostic. This is the inference form, close to F10. **Kill** the label version if this is at or below 0 and the diagnostic does not move.
3. Then a 60-superbatch fine-tune on rewritten labels, two seeds, against the same-recipe fine-tune: 0.8 GPU-hours, 2 FN screens, an STC SPRT, and one anchor check.

**Changes.** None in the engine. An offline builder beside the TD label builder (class function, per-class map, derived manifests); the fit script, which can share R33's.

---

## Idea 7. Bound-supervised targets: learn from the moves the search refuted

**Mechanism.**
- A saved 20,000-node search scores the best move exactly and proves each other root move no better than it. Record, for a few non-best root moves, the proven upper bound and the depth it was proven at.
- For the position after such a move, the bound is a one-sided target: the loss is zero when the net's value is on the right side and squared error when it is not.
- Only quiet children are kept (static equals quiescence), so the lesson is positional.

**Design principle.** No inference cost. The new records are positions the search actually visits (after inferior moves), where today's data, drawn from game lines, has none.

**Why it fits.**
- E8: the edge is lost through many small, individually acceptable moves. The static eval after a slightly inferior quiet move is where the net is unsupervised.
- Idea 49 asks for the same ordering signal but pays a 20,000-node search per sibling. Here the bounds come free from searches already made.
- Only violated bounds give gradient, so it trains on the net's own mistakes.

**Novelty and nearest relatives.** A novel application, not a new mechanism. Nearest: TreeStrap(alpha-beta) (Veness, Silver, Uther and Blair, 2009: updates from search bounds; UNVERIFIED), which I did not find in Fork's files; idea 49 (sibling ranking); idea 156 (PV harvest); the search-site slice the earlier proposal left out.

**nps.** None.

**Expected gain and risk.** +3 (−3 to +8). Chance 25%.
- Risk: root-move bounds come from reduced-depth searches and are weak; most violations are tactical and the quiet filter leaves too few.
- It needs a new datagen field, so existing data cannot be used.

**Cheapest falsifier.** CPU only: re-search 50,000 saved positions at 20,000 nodes with the root's bounds logged (about 1 G nodes, well under one CPU-hour). Measure the share of quiet children whose static value breaks the bound by more than a margin, and check a sample against a 1M-node search. **Kill** if under 2% are violated or under 80% of sampled bounds hold. Then a small fine-tune arm on 10-20 M bound records.

**Changes.** Engine: `fork_datagen` writes a sidecar of (move, bound, depth) per saved search. Trainer: a per-record target type and the one-sided loss (UNVERIFIED that bullet's operators express it directly).

---

## Idea 8. Move-delta rows: one row per quiet move, not two

**Mechanism.** For a quiet non-pawn move the update subtracts row(piece, from) and adds row(piece, to). Precompute their difference for every geometric (piece, from, to) at net load, and apply one row. Captures apply the delta row plus the captured piece's row; pawn moves keep their link rows.

**Design principle.** No inputs or weights. It attacks the dominant cost directly: rows per update fall from 3.09 to about 2.1.

**Why it fits.** E1: the update is instruction-bound, and each row is a load and an add per tile. Per tile the work falls from about 5.1 to 4.1 operations, a fifth of 26.3% of cycles.

**Novelty and nearest relatives.** Unsure; it is simple enough that someone may have tried it. Fork's files have no record. Nearest: fused add-sub kernels (Fork has them), refresh caches, and the S512+PP link-sum cache (tested, not kept).

**nps.** +3% to +5% if the table stays in cache; negative if it does not. About 7,600 rows, 7.8 MB, against 1.4 MB today.
- Fork's own record warns here: prefetching piece rows made S512+PP slower.
- TCEC's EPYC is the hard case (about 2 MB of L3 per core; UNVERIFIED).
- With king regions the table is four times larger, so this is for the S512+PP body only.

**Expected gain and risk.** +5 where it works. Chance 25%. No accuracy risk: bench is identical.

**Cheapest falsifier.** It is its own test: build it, check bench parity, run the A/B harness for 20 rounds, and repeat on a runner through the speed A/B workflow. One engineering day. **Kill** under the standing 1% cycles-per-node rule.

**Changes.** `net_file` builds the table at load; `accumulator.cpp` gets the one-row path and its scalar reference and equivalence test. Nothing in the trainer.

---

## Idea 9. Knot-tied heads: a head for every phase and queen state, generated from a few knots

**Mechanism.** The output is linear in the head's weights, so a head that is a blend of knot heads can be precomputed. Train 5 knot heads per queen state and define the head at phase p as the piecewise-linear blend of its two neighbours. The converter writes one finished head per (phase, queen state): 25 x 2, about 100 KB. The engine picks one head by table lookup and runs one dot product, as now.

**Design principle.** No speed cost. Each knot is trained by every position near it, so fine conditioning does not divide the data (points 1 and 3). The value no longer jumps at a bucket edge, which is where every piece trade is judged.

**Why it fits.** E6: scale differs by queen state, and today's phase buckets mix light queens-on positions with heavy queenless ones.

**Novelty and nearest relatives.** A refinement, not a new mechanism. Nearest: idea 159 (experts by material class), which this makes trainable at fine grain; XGR's learned gate, which blended two experts continuously at run time; idea 53; output buckets.

**nps.** About 1.00.

**Expected gain and risk.** +2 (−2 to +6). Chance 35%. An effect this size sits inside the ±6 seed noise of a screen, so it would need its STC SPRT to be read at all.

**Cheapest falsifier.** Trainer and converter only, half a day each, plus the head lookup. A 60-superbatch fine-tune, two seeds (0.8 GPU-hours), the UHO diagnostic, then straight to an STC SPRT. **Kill** on H0.

**Changes.** Engine: the head index by (phase, queen state). Trainer: knot heads and the blend weights as a dense input; converter writes the finished heads.

---

## Idea 10. Queen-gated king-zone values

**Mechanism.** Option (b2)'s king-zone vector costs 8.6% because it is computed for both kings at every evaluation. Compute a king's 16 values only when the enemy still has a queen, and feed zeros otherwise; train it the same way.

**Design principle.** The gate depends on the position only, which idea 46's judge named as the safe kind. The values are spent where the misjudgment is.

**Why it fits.** E8 puts the underrating in queens-on positions. (b2) is in reserve at 0.914; this is the same vector at a lower price.

**Novelty and nearest relatives.** A small trick, a novel combination at most: (b2), position-only gates (idea 46), queen-routed buckets (H9).

**nps.** About 0.95-0.96, if roughly half of evaluated positions have queens on (UNVERIFIED; one stats run gives it).

**Expected gain and risk.** +3 if (b2) has value at all, which is unmeasured. Chance 30%.

**Cheapest falsifier.** Add the gate to proto/r3-king-b2 and re-measure: under half a day. **Kill** below 0.95. Training rides on whatever is decided for (b2).

**Changes.** Two tests in `context.cpp`; the trainer's vector function mirrors the gate.

---

## Ranking by expected Elo per unit of cost

"Chance" is my guess that the idea passes its SPRT. "Cost to kill" is the falsifier alone; "full cost" runs to the SPRT. The last column is chance x central Elo / full cost.

| Rank | Idea | Central Elo | Chance | Cost to kill (EU) | Full cost (EU) | Expected Elo per EU |
|---|---|---|---|---|---|---|
| 1 | 8. Move-delta rows | +5 | 25% | 1.5 | 1.5 | 0.83 |
| 2 | 6. Depth-extrapolated class calibration | +3 | 40% | 0.7 | 2.2 | 0.55 |
| 3 | 4. Stand-pat liabilities plane | +6 | 35% | 1.0 | 4 | 0.53 |
| 4 | 1. State-folded rows | +6 | 40% | 1.7 | 6.5 | 0.37 |
| 5 | 9. Knot-tied heads | +2 | 35% | 2 | 2 | 0.35 |
| 6 | 2. Split-clone columns | +4 | 35% | 3.5 | 5 | 0.28 |
| 7 | 10. Queen-gated king-zone values | +3 | 30% | 0.4 | 3.5 | 0.26 |
| 8 | 5. King-offset lane | +5 | 25% | 1.5 | 7 | 0.18 |
| 9 | 3. Banded first layer | +6 | 25% | 2.5 | 9 | 0.17 |
| 10 | 7. Bound-supervised targets | +3 | 25% | 0.6 | 6 | 0.13 |

Every input to this table is a guess, and the values span a factor of six, so read it as three groups: cheap and quick (8, 6, 4), structural with a higher ceiling (1, 2, 9, 10), and long builds (5, 3, 7).

**Against the two priorities.**
- Queens-on misjudgment: 6 (level, labels), 1 tier B and 5 (attack knowledge), 2 and 9 (regime-specific capacity and scale), 10.
- The threat plane's accuracy inside the speed gate: 4, and tier A of 1 for the pawn-attack part.

**Novel** (I know no relative doing the same thing): 1, 2, 8, and the side-to-move halving in 4. I am unsure about 8.

**Novel combination of known parts:** 3 (structured sparsity), 4's column block (idea 46 rank 5 and H8, re-priced by today's measurements), 5 (option b + snapshots + lane), 6 (R33 moved to the labels, plus depth), 7 (TreeStrap applied to stored searches), 9 (a refinement of idea 159), 10.

---

## The three to test first

Not the table's top three: idea 8 is a one-day A/B that answers nothing else, and it should fill the next quiet hour whatever is chosen.

1. **Idea 1's two screens** (residual study, then the zero-delta speed prototype). It is the only idea that serves both priorities, it applies today's cost lesson most directly, and both screens reuse methods Fork already trusts (R36's rule, round 3's speed method). Cost to a decision: under two EU, no GPU. Idea 2's column-utilisation count rides on the same data pass.
2. **Idea 6's fit and head-rescale screen.** One CPU-hour and one FN screen test the leading explanation itself: if rescaling by class from Fork's own results neither gains nor moves the diagnostic, the "level" half of the two-sided misjudgment is not worth Elo, and effort should go to knowledge (ideas 1, 5). If it gains, the label arm follows for under one GPU-hour.
3. **Idea 4's share measurement and speed prototype.** Minutes of CPU and half a day on existing prototype code decide whether the threat plane has a form that passes the gate with the exact rule. Its result should be read beside x_lower's, which is training now.

---

## Interactions with what is training now

- **H512+PP (option a).** Ideas 1 and 8 multiply their tables by the region count, so each is an alternative to (a) on the S512+PP body, not an addition. Ideas 2, 4, 6, 7, 9 and 10 stack with either body.
- **x_lower.** Idea 4 is its next step: if x_lower gains at fixed nodes but its speed-adjusted result is marginal, the side-to-move cut and the column block roughly halve its price.
- **The per-class lambda arm (A2).** Idea 6 is independent of it: it rewrites scores before the lambda-return is built.

## On file already, and relevant

Not proposed here because they are recorded, but each bears on the queens-on finding and is cheap:
- **Material-based eval scaling (survey F10, never tried).** The hand-written form of idea 6's step 2: it raises queens-on scores and lowers queenless ones.
- **R33, the structure-class scale** (designed 2026-11-09, not built). Its fit script is most of idea 6's.
- **Idea 159, output experts by material class** (round 3 priority). Idea 9 is a way to train it at fine grain.
- **d_lite and (b2)** in reserve at 0.923 and 0.914.

## Considered and left out

- **Asymmetric-strength self-play for defence examples.** Idea 81, parked by the owner for its result bias.
- **Near-window gating of expensive inputs.** Idea 59's family; the refiner lost 19.8 and the owner has already named gating as the fallback for (b).
- **A WDL or sharpness head.** Ideas 65 and 67 and survey J19.
- **Weighting positions by TD error.** Reweighting has lost twice (class weights, idea 52's oversampling).
- **Training on principal-variation leaves.** Classical TDLeaf, already credited under idea 51.
- **A wider dense layer or a multi-layer head.** Tried (AF-S) and in the survey.

## Sources to credit if any idea is built (all UNVERIFIED, from memory)

- Veness, Silver, Uther and Blair, "Bootstrapping from Game Tree Search" (NIPS 2009): idea 7.
- Platt (1999) and Zadrozny and Elkan (2002), as R33 already credits; Guo et al., "On Calibration of Modern Neural Networks" (2017): idea 6.
- Wen et al., "Learning Structured Sparsity in Deep Neural Networks" (2016), in idea 46's list: idea 3.
- Jacobs, Jordan, Nowlan and Hinton, "Adaptive Mixtures of Local Experts" (1991), as idea 53 credits: ideas 2 and 9.
- Public NNUE descriptions of king input buckets, factorisers and refresh caches, as recorded in Fork's KB: ideas 1, 2 and 5.
- Fork's own round 3 reports, R33, R36, idea 46 and the think tank's H8, for the parts reused.
