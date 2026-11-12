# Fork: novel ideas for strength (read-only proposal, 2026-11-11)

**Status.** Proposal only. Nothing was built, run, tested, edited or committed, and no job, queue, GitHub, Kaggle or cloud resource was touched. Every Elo figure below that does not cite a logged Fork run is my judgement, not a measurement. Every outside citation is from memory and is **UNVERIFIED** until someone fetches the primary source. Names and constants here are placeholders: none has been through the name or constant screens.

**Snapshot.** Branch `phase-4`, default net r8brft1 (architecture 8: 768 mirrored inputs + 608 pawn links → 512 SCReLU → 8 phase heads), gauntlet 3510.5 ± 20.5 (2026-11-11).

**What I read.**
- Myself: `CLAUDE.md`, `HANDOFF.md`, `MORNING.md`, all of `docs/ideas.md` (ideas 1–77), the engine survey's `comparison.md` (135 rows) and `ranking.md`, the transfer report, the conversion-and-defense report (branch `research/conversion-defense`), the engineering review, the bug review, the idea 59 step 1 and crucial-point results in `DESIGN.md` §5.7, and the NNUE, datagen and TT headers under `src/`.
- Through read-only sub-readers: `DESIGN.md` (all of it), both SPRT logs, `nets.md`, the perf logs, the phase-4 designs, and the think tank.
- **Gap in the novelty check:** the think tank's `phase-b-specialists.md` (700 KB) was read in full only for its surveys, summaries, ranked tables, skeptic verdicts and every "Mechanism" line; the long bodies of T2–T9, S2–S3, S6–S9, O0–O10, ST1–ST8, H1–H9, I1–I9 and W3–W6 were not. I searched `docs/` and the KB for each idea's key terms and found no match, but an idea could still be buried in those bodies.

**Cost units** (the project's own): one STC stage = 1,600 games ≈ 18 min on 16 shards; a fixed-node (FN) screen ≈ 1 stage of 36–43 min; one LTC stage ≈ 75–79 min; one 360-superbatch retrain seed ≈ 2.2 T4 GPU-hours; data generation ≈ 1.0 CPU-hour per million kept positions at 20,000 nodes and 9.6 at 80,000. Every training arm is costed at 2 seeds (owner's rule, 2026-11-11).

---

## The evidence these ideas lean on

| # | Finding | Source |
|---|---|---|
| E1 | Networks and data return about 12.5 Elo per test stage, search features about 0.8. Split search +65.5, TD(0.9) +12.2, result fine-tune +5.7, pawn links +32.7 at 0.895 nps. | SPRT log, think tank |
| E2 | Speed costs 1.72 Elo per 1% nps at STC (118 per doubling). Every richer net won at fixed nodes and lost on the clock. | transfer report §6 |
| E3 | **The control split of idea 59:** S512+X consulted only within 25/10 cp of the window (3.8% of nodes) gained +29.8 ± 9.8 at fixed nodes, and +41.0 at 25/25; a random gate at the same call rate +7.6 ± 9.9; S512+X at *every* node +25.7. So almost all of a better evaluation's value sits near the window. | ideas.md 59 |
| E4 | Yet every cheap way to exploit E3 failed: the shared-accumulator refiner −19.8, the near-window extension −5.4, window-aware LMR −2.9, root-gap time −4.9. An *independent* net blended near the window gave +9.6 (replace: +3.5). | ideas.md 59–61 |
| E5 | Step 1 of idea 59: 0.524 evaluations per node; of computed evaluations, 34.8% (main) and 51.9% (quiescence) lie within 100 cp of the nearest bound, 19.4% and 29.4% within 50 cp. So 53% of computed evaluations are more than 100 cp from the window and 73% more than 50 cp. | DESIGN §5.7 |
| E6 | Profile: the network is 41.5% of time (accumulator update 17.2%, output layer 14.5%). | perf log |
| E7 | Split search saves a random 50% of positions at 20,000 nodes; the rest get 4,000 nodes and are **discarded by the trainer** (45.5% of records; e.g. 227.8 M of g3's 500 M). | ideas.md 13, HANDOFF §3 |
| E8 | The TD label builder relabels saved records only; an unsaved record keeps score 32767 and stays dropped. It has a `--from-next` mode whose target leaves the record's own score out. | `td_labels.py` on `idea51/td-labels` |
| E9 | Result label: within-game correlation 0.674, about 1.5 independent results per game. Later scores predict the result with slope 1.19, not 1: scores are not martingales, they drift away from zero. | think tank M, B13 |
| E10 | **Compression:** static eval minus deep label, signed toward zero: −78.7 cp at 200k nodes, −126.4 at 1M; it grows with the label and by class (queen endings −291, queens-on B-vs-N −77). | conversion-defense §4 |
| E11 | **Defense:** 0 of 164 games from unfavourable exits against Stockfish and Clover; of 541 core losses only 13 are horizon errors; turning swing median 82 cp; opponents see +150 a median 4.5–11.5 moves before Fork sees −150, against 0.5 moves between two Forks. Loss turning points are 69% queens-on middlegames. | conversion-defense §1–2 |
| E12 | **Data gap:** queens-on middlegames with level material are 2.4% of training positions at decisive scores but 23% of gauntlet deciding positions (ratio 9.7). Top error classes: queens-on B-vs-N and rook-against-minors. | conversion-defense §4–5 |
| E13 | The defense-start slice was dropped: defenders held 6.4% in its pilot, under the 10% minimum. | ideas.md 66 |
| E14 | **Endgame recall:** 509 of the endgame check's 900 positions are verbatim in the Syzygy slice, so "351 → 8 misjudged" measures recall. Earlier retrains without the slice lost KQK (0 → 28–59 of 300). The net's behaviour off its data is unmeasured and drifts. | bug review T1 |
| E15 | **Transfer:** self-play gains show at 0.65 against anchors (0.48 running, 0.28 in the last window; the stopping bias T4 understates all three). "A blind spot both sides share is invisible to self-play SPRTs." | transfer report, think tank C |
| E16 | Ensemble teacher, step 0: three nets at 20k nodes each beat one 20k search, but by about a quarter of what three times the nodes on one net buys. | ideas.md 63 |
| E17 | TCEC: 512 threads, 256 GiB hash; the think tank puts 1 → 512 threads at +200 to +450 Elo, about 22–50 per thread doubling. Minimal Lazy SMP (step 17a) is next. | think tank TC-A, DESIGN |
| E18 | Offline proxies mislead: the proxy rejected IIR (games: +21) and ranked T56's variants backwards; validation loss agreed with the STC sign in 4 of 7 cases. Speed-adjusted FN screens predicted 9 of 9. | SPRT log, transfer report |

---

## Idea 1. Nested-width evaluation: a narrow net far from the window, the full net near it

**Mechanism.**
- Train one net whose first K hidden columns (say 256 of 512) are themselves a usable evaluator. The SCReLU output is a sum over columns, so let the full head's weights on columns 0..K−1 *be* the narrow head's weights: the narrow evaluation is then a partial sum of the full one (plus its own bias), and nothing is computed twice.
- Training loss: loss(full) + μ · loss(narrow partial sum), on the same targets. Warm-start from the default with the narrow bias at zero, which leaves the full output unchanged.
- At an evaluation site, update only columns 0..K−1 of the lazy accumulators and take the partial sum. If it lies more than a band (placeholder 50–100 cp, set from the measured |narrow − full| quantile) from the nearest finite bound, use it. Otherwise finish columns K..511 along the lazy chain and return the full evaluation.
- The TT stores which kind it holds in a spare flag bit and only upgrades.
- **The same machinery runs the other way:** a 768- or 1024-wide net whose first 512 columns are today's net. Far evaluations cost what they cost now; only near-window evaluations pay for the width.

**Why it should work for Fork.**
- E3 says evaluation accuracy far from the window is worth almost nothing: S512+X near the window recovered all of S512+X everywhere. By the same measurement, a *worse* evaluation far from the window should cost almost nothing.
- E5 and E6 size the prize. Halving the width for 53–73% of evaluations saves up to half of 31.7% of node time on those sites: about 8–12% of time, +9–13% nps, worth +15 to +22 Elo at Fork's price before the accuracy cost.
- It is the first design that exploits E3 without a second accumulator, new inputs or a separately trained patch. Those were the three things that sank E4's attempts: the oracle's two accumulators (in-situ speed 0.743), and the refiner, a residual trained on near-window sites that lowered loss and lost 19.8 Elo. Here both evaluators are one jointly trained ordinary net.
- The wide direction turns the speed gate from a wall into a dial, which the engineering review's W3 (net too small, gate derived at the wrong time control) asks for.

**Novelty and nearest relatives.** Novel combination; I am not aware of an engine doing it, but I am unsure.
- Classical lazy evaluation and idea 59 itself (same gate, opposite direction: 59 adds cost near the window, this removes cost far from it).
- Stockfish's small-net/big-net switch, public at concept level: two separate nets, gated by material, not by the window.
- Nested or "matryoshka" representations and slimmable networks in ML (Kusupati et al. 2022; Yu et al. 2018, already in idea 46's source list).
- Idea 46 rank 5 (inputs confined to a column subset) is the nearest Fork entry.

**What has changed since the related rejections.** The think tank ruled "dual/small net: never in Phase 4", and idea 46's judge called window-dependent evaluation unsafe for the TT, the improving flag and corrections. Both predate the control split (2026-11-08), where an engine with mixed evaluations *gained* 30–41 Elo at fixed nodes.

**Expected gain and main risk.** Narrow-far: +6 Elo at STC (−5 to +15). Wide-near: larger but needs a wider net to be genuinely better at fixed nodes. At TCEC speed is worth less, so the wide direction matters more there.
- Main risk: the narrow constraint degrades the full net, or the band must be so wide that few evaluations qualify.
- Second risk: bookkeeping for half-finished accumulators eats the saving.

**Cheapest falsifier.** An accuracy oracle with no training.
1. On CPU, refit a narrow readout on r8brft1's frozen first 256 columns (the probe method of R26 and idea 53, stage A). This is a pessimistic narrow evaluator: those columns were never trained to stand alone.
2. Measure |narrow − full| offline to set the band.
3. On the `exp/oracle` machinery, play an FN screen of "narrow far, full near" against the default. Fixed nodes charge no speed, so this isolates the accuracy cost.
- **Kill:** worse than −8 Elo at a band of 100 cp or less (the speed gain cannot exceed about +15).
- **Cost:** about 2 CPU-hours, 0 GPU, 1–2 FN stages (0.7–1.4 GitHub-hours), 1–2 engineering days.
- If it lives: price the speed with a synthetic half-width build on a quiet machine (1 CPU-hour), then train 2 seeds (about 5 GPU-hours), FN_adj screen, STC SPRT, LTC.

**Code changes.** `net_shape.hpp` (a narrow width constant, a new architecture id), `accumulator.{hpp,cpp}` (per-half `computed` flags in `FeatureStack::Entry`, kernels over a column range, the partial-sum output), `searcher.cpp` (`eval_at` takes the window; the gate), `trans_table.hpp` (one flag bit), `net_file.cpp` (bounds, narrow biases), `tools/train` (second loss term), `tools/nnue/reference.py` and the parity legs.

---

## Idea 2. Label the unsaved half: TD targets need no search of their own

**Mechanism.** The split search discards 45.5% of its records because they have no 20,000-node score. But the standard recipe's target does not need one.
- **Variant A (no new assumption).** For an unsaved, not-in-check position at ply t, the TD(λ) target is the λ-return that starts at the next saved record: exactly what `--from-next` computes, minus the position's own score. Write those targets for unsaved records too, into derived shards with their own manifests. In the result fine-tune stage (result weight 1.0) an unsaved position needs no score at all.
- **Variant B (PV-child fill).** When the previous position was saved, its search score *is* a search score of this position: the game move is that search's best move, so the child's value is the parent's value (the same White-view number), from a subtree that held most of the 20,000 nodes. Use it as the record's own-score term.
- Sealed data is never changed; this is an offline builder like `td_labels.py`.

**Why it should work for Fork.**
- E7 and E8: about 83% more trainable positions (0.455 / 0.545) from games already on disk, for zero generation CPU. The think tank's two-factor model prices a doubling of kept data at 10–20 Elo now.
- E1: every data-side change has paid; this is the cheapest one left.
- TD(0.9) is already the standard recipe, so Variant A's targets are the same kind of label the default net was trained on.

**Novelty and nearest relatives.** Novel as far as I know, and specific to Fork because it only exists where a split search meets TD labels. Nearest relatives: KataGo's playout-cap randomization (fast-search positions are not recorded as value targets there; UNVERIFIED), KataGo's short-term value targets, TDLeaf(λ), and ordinary datagen where every ply is searched.

**Expected gain and main risk.** +3 Elo at STC (0 to +7).
- Main risk: the new positions are adjacent to saved ones and share their targets, so the effective gain may be far less than 83%. Other engines report gains from *skipping* correlated positions (survey row J17), and the think tank rated a 25% save share WEAK.
- Idea 13's result does not settle it: it compared arms at equal CPU, not at equal games.
- B13's caveat (cheap-search scores must not enter the TD chain) is respected: no 4,000-node score is used.

**Cheapest falsifier.** One retrain arm on existing data: the standard recipe with unsaved positions labelled (Variant A) against the control, 2 seeds each, at equal samples seen.
- **Kill:** head-to-head against the control at or below 0 on both seeds.
- **Cost:** about 20 CPU-hours for the builder over a snapshot (UNVERIFIED: a pure-Python pass over about 1.5 B records may need the Rust reader instead), 4.4 GPU-hours beyond the control, 2 FN stages, then an STC SPRT of the better seed (1–5 stages).
- A B0-size small-net pair on one part first costs minutes of GPU and 2 FN stages.

**Code changes.** None in the engine. `tools/datagen/td_labels.py` gains an `--unsaved label` mode (and Variant B's fill); a manifest type for derived shards; the trainer is unchanged because the filled records carry ordinary scores.

---

## Idea 3. Colour-coherent split search: Fork-pure sparring games with every position labelled

**Mechanism.** Today each position is independently saved (20,000 nodes) or not (4,000). Instead, in a share of games, give the roles to colours: one side (chosen at random) searches 20,000 nodes on every move and the other 4,000.
- The strong side's positions are saved as now.
- The weak side's positions get Variant B's label from idea 2: the strong side's preceding search already valued them. So **every position in the game is labelled**, both sides to move, for one 20,000-node and one 4,000-node search per two plies: about 12,000 nodes per labelled position against 24,000 today.
- A defender-favoured form for worse positions: from a start where the side to move is at −100 to −300 with queens on, the defender gets the larger budget.

**Why it should work for Fork.**
- E11: Fork's losses to stronger engines are slow slides it registers late, and that lag does not exist between two equal Forks (0.5 moves). Equal self-play therefore contains almost no examples of it. A strength gap inside Fork's own games is the only Fork-pure way to produce them: the survey's K8 (games against other engines, +2.4 to +5.6 per round for Ethereal) is excluded by the data policy, and this is its Fork-pure analogue.
- E12: in equal self-play a level position with a decisive future is rare; in an asymmetric game it is the normal state of the first 20–30 moves. That is the class with the 9.7× gap.
- E13: the defense slice failed only because defenders at equal strength almost never hold. Giving the defender the budget attacks exactly that check.
- E7: the split search's own lesson was that who plays the unrecorded moves is a free design lever, worth +65 the first time it was pulled.
- E15: gains that only show against stronger opponents are the ones the transfer gap says Fork is missing.

**Novelty and nearest relatives.** Novel combination. Nearest: KataGo's asymmetric playouts for handicap games (UNVERIFIED), league and exploiter training in AlphaStar-style self-play, adversarial data against other engines (K8), and idea 66's slices, which select starts but play both sides equally.

**Expected gain and main risk.** +4 Elo in self-play (−3 to +10), possibly more against anchors.
- Main risk: a 4,000-node side loses by tactical blunders, not slow slides, so the data teaches nothing about E11.
- Second: the result label now mixes the position's merit with the skill gap. With random role assignment that adds variance, not bias, but the variance is real.
- Third: the defender-favoured form may teach the net that worse positions hold when Fork's own search cannot hold them.

**Cheapest falsifier.** A pilot of 20,000 colour-coherent games beside 20,000 standard ones (about 2 CPU-hours each at production rates), measured three ways with the conversion-defense tooling:
- the lag between the strong side's sustained +150 and the weak side's sustained −150;
- the swing at the turning point;
- the share of level-material queens-on positions with a decisive TD label.
- **Kill:** median lag under 2 moves, or median swing over 150 cp (blunders, not slides), or the class share under twice the standard data's.
- If it lives: a 60 M-position arm (about 30 CPU-hours at the halved cost), 4.4 GPU-hours beyond the control, 2 FN stages, an STC SPRT, and one level-1 anchor check (about one stage) as the secondary measure, since self-play may not see the gain.

**Code changes.** `SelfPlayConfig` and `self_play.cpp` (a per-game role, the save decision by colour, the child-label write), `datagen_main.cpp` (options), the part manifest (new fields), `verify_games.py` (the new record semantics). The labeller policy holds: every label still comes from the default engine.

---

## Idea 4. Multi-fidelity output heads: learn from every budget, ship the deep-label head

**Mechanism.** Give each training record a fidelity tag from its source file and let the trainer pick the output head by phase *and* fidelity (8 phase heads × 2 or 3 fidelities). The feature transformer is shared and learns from everything. The engine ships and evaluates only the high-fidelity heads, so the net's size and speed are unchanged.
- Low fidelity: standard 20,000-node split-search games.
- High fidelity: the label-depth arms (50,000 and 100,000 nodes), the positional slice (80,000 nodes, no cheap moves, adjudication raised), and the tablebase slices (exact).

**Why it should work for Fork.**
- E10: labels at different budgets are different functions (compression shrinks as the budget grows), and E9 shows the drift is systematic. Today's recipe mixes 20,000-node labels, 80,000-node slice labels and exact tablebase labels into one head, which can only average them.
- An output head has about 1,025 weights per phase bucket, so the roughly 37 M high-fidelity positions already generated are ample to fit it, while the 300,000 link weights and the piece rows keep the 1.5 B cheap positions. This is the cheapest way to get part of what idea 62 (deeper labels at equal time) is testing, without paying five times the generation cost.
- E14 argues for head-only specialisation: full-net fine-tunes on narrow data are what lost KQK.
- The survey's note on a peer (data regenerated at a higher node budget: fixed nodes −49, STC −28, LTC −7.4, LTC at 8 threads +13.6) says deep-label nets are what long, threaded games want and what STC punishes. Fork can hold both heads in one training run and measure each.

**Novelty and nearest relatives.** Novel combination; I have not seen fidelity-conditioned heads in an NNUE engine, but I am unsure. Nearest: phase and material output buckets; idea 53 and R26 (heads by structure class); mixed-budget fine-tunes (survey K2, Tarnished +6.5 to +6.9 LTC); multi-fidelity learning in ML (Kennedy and O'Hagan 2000); R27's paired shallow and deep playouts.

**Expected gain and main risk.** +4 Elo (0 to +10), more at LTC and with threads.
- Main risk: the deep-label head is better at long time controls and worse at STC, so Fork's STC-first testing rejects it. Test it at LTC before discarding.
- Second: the high-fidelity sources differ in more than budget (older labellers, selected starts), so the head learns a source effect.

**Cheapest falsifier.** A CPU probe on data already on disk: freeze r8brft1's first layer, refit the 8 heads on high-fidelity records, and compare with the shipped heads on the 1M-node gold set (overall and by class: the compression in queens-on classes should fall). Then convert and play one FN screen against r8brft1.
- **Kill:** no gold-set gain beyond the seed spread *and* an FN screen at or below 0.
- **Cost:** 2–4 CPU-hours, 0 GPU, 1 FN stage, half an engineering day if the probe tooling exists (UNVERIFIED whether idea 53's stage-A tool was built).
- If it lives: one trainer arm, 4.4 GPU-hours, 2 FN stages, STC SPRT, then LTC.

**Code changes.** `tools/train` (a fidelity tag per input file; bucket index = phase + 8 × fidelity), `tools/nnue/convert.py` (write only the chosen heads), nothing in the engine.

---

## Idea 5. Label super-resolution: predict the deep label from the cheap one

**Mechanism.** Fit a small regression, on a gold set labelled at 1M nodes, from what every training record already has to the gap between its cheap label and the deep one.
- Inputs: the stored 20,000-node score, the default's static evaluation of the position (recomputable), the difference between them, the score band, the phase and material class; optionally the search's score at half budget and the depth it finished.
- Output: the expected deep label. Rewrite every label offline (derived shards) and build TD targets on the corrected scores.
- The correction uses search telemetry the static net cannot see, so it is information the net does not already have.

**Why it should work for Fork.**
- E10 and E9 are the same fact seen twice: search scores drift away from zero as the budget or the game advances (slope 1.19, compression growing from 200k to 1M nodes). A drift that systematic is predictable, and "search minus static" is the obvious predictor of its direction.
- Idea 62 asks whether deeper labels pay at five times the cost per position. This asks how much of that can be had for nothing, on all 1.5 B existing labels.

**Novelty and nearest relatives.** Novel as far as I know; I am unsure whether an engine author has tried it privately. Nearest: idea 62 (label depth), idea 58 (a giant teacher), TD(λ), Richardson extrapolation, and the score-trend terms used in time management.

**Expected gain and main risk.** +3 Elo (0 to +8).
- Main risk: it amplifies the lineage's own bias. The 8M-node search does not see the slow slides either (E11), so a regression toward Fork's own deep labels cannot teach them.
- Second: extrapolation adds variance to every label.

**Cheapest falsifier.** Entirely on existing data: idea 51's 3,131 positions (stored score plus a 1M-node label) and idea 52's 2,000 controls (200k labels). Cross-validate the regression.
- **Kill:** the corrected label's squared error against gold, in win-probability space, is not at least 10% below the raw label's, or the slope on "search minus static" is not positive with its interval clear of zero.
- **Cost:** CPU minutes, 0 GPU, 0 GitHub, half an engineering day. Logging per-iteration scores for 20,000 positions adds about 5 CPU-minutes.
- If it lives: 4.4 GPU-hours, 2 FN stages, STC SPRT.

**Code changes.** None in the engine for the first form. An offline builder beside `td_labels.py`. The half-budget input needs one optional datagen field, which the record format does not have room for today (a sidecar file, not a format change).

---

## Idea 6. Evaluator-diverse Lazy SMP: threads that disagree on purpose

**Mechanism.** In Lazy SMP every thread searches the same tree with the same evaluation and differs only by depth and timing. Instead, give thread groups different networks of the same shape: the default for most threads, an independently initialised net for the rest.
- They share the TT's moves, scores and bounds. A stored static evaluation carries a one-bit evaluator tag and is reused only by its own group.
- At the root, vote across groups, so a move must survive two differently-wrong evaluators.
- Later, train the second net to be *decorrelated* from the first (a penalty on the covariance of its error with the frozen default's), not merely independent.

**Why it should work for Fork.**
- E16 measured the single-thread trade: an ensemble is worth about a quarter of the nodes it costs. That 4:1 is why ensembles lose at one thread.
- E17 changes the price: at TCEC a doubling of threads is worth 22–50 Elo, against 118 for a doubling of speed at one thread. The nodes an ensemble gives up are 2.5–5 times cheaper, so the same trade moves from a clear loss toward break-even or better as threads grow.
- E4: the one near-window variant that gained was a blend with an independent net (+9.6), and the warm seed pair is "in effect one net" (idea 52), so diversity has to be built deliberately.
- E3 says where the benefit would land: at frontier nodes near the window, which is where helper threads' trees differ from the main thread's.

**Novelty and nearest relatives.** Novel as far as I know; plainly unsure, since SMP diversity is an old topic. Nearest: depth skipping and thread voting (survey G3), per-thread parameter jitter (tried in several engines), shared correction history (G2), idea 63 (ensemble teacher, killed at one thread for the reason above), negative-correlation learning (Liu and Yao 1999).

**Expected gain and main risk.** At 8 threads +3 Elo (−6 to +12); at TCEC scale possibly +10 to +30, which nothing Fork owns can measure.
- Main risk: mixed scores in one TT make the search inconsistent and it simply loses.
- Second: the second net must be about as strong as the default. A scratch net is weaker (validation 0.01948 against 0.01909), so the first test is pessimistic.

**Cheapest falsifier.** After step 17a, on GitHub's 4-core runners: 4 threads on the default against 3 + 1 (and 2 + 2) with a second net, design R at STC. A stage takes about three times as long, since each runner plays one game at a time.
- **Kill:** at or below 0 at both 4 and 8 threads.
- **Cost:** 2–8 stages ≈ 2–7 GitHub-hours; one scratch run for the second net (2.2 GPU-hours) if none of 8b's is still usable; an 8-thread confirmation on the PC or the VM, about 45 thread-hours.
- Costs nothing to prepare for now: keep the net pointer per searcher when 17a is built.

**Code changes.** `Searcher` already evaluates through its own `net_`; make that per-thread. A second embedded or loaded net (1.4 MB), one TT flag bit, the root vote, a UCI option for the group sizes.

---

## Idea 7. Class-matched TD horizon

**Mechanism.** Replace the single λ = 0.9 with a λ per phase bucket (or per material class), chosen from Fork's own data: longer horizons where the search label lags the truth, shorter where the search is accurate and the result is noisy.

**Why it should work for Fork.**
- λ matters and steeply: TD(0.9) screened +17.4 and TD(0.8) −1.1 on the same data. Nothing above 0.9 has been tried.
- E11 puts the lag in queens-on middlegames at 9–23 plies, well beyond TD(0.9)'s effective horizon of about 10. E10 says the search label is most compressed in endgame classes, and B13 noted the result's bias is class-signed. One λ cannot fit both.

**Novelty and nearest relatives.** A refinement of idea 51, so a novel combination at most. Nearest: KataGo's several fixed horizons (UNVERIFIED), R37's TD-k family, R27's result weight from paired playouts.

**Expected gain and main risk.** +2 Elo (−2 to +6). Risk: the fitted λ values differ by less than the noise, and with seed noise near ±6 Elo an effect this size may be unresolvable.

**Cheapest falsifier.** Offline, before any training: the result-residual variogram by class on existing games (the think tank computed it overall: 0.0443 at 1 ply down to 0.0156 at 32), and the λ that minimises error against the gold set per class.
- **Kill:** the best λ for queens-on middlegames and for endgames differ by less than 0.05.
- **Cost:** CPU minutes. If it lives: 4.4 GPU-hours, 2 FN stages, STC SPRT. A plain global TD(0.95) arm is the obvious control to run beside it.

**Code changes.** `td_labels.py` only (λ as a function of the record's class).

---

## Idea 8. Pawn-clocked context rows: bishop colour complexes

**Mechanism.** Pawn links worked because pawn structure is long-horizon knowledge that changes on few moves. Extend that rule: add inputs that pair each pawn with a piece of *slow* context, so the rows change only when a pawn moves or the context does.
- The new member: (which bishop colour complexes each side still has: own light, own dark, enemy light, enemy dark) × (pawn colour × square), 384 rows.
- A bishop move never changes its complex, so these rows change only on pawn moves (16% of moves in games) and on the rare capture or promotion of a bishop. There is no pair search: four flags and the moved pawn's square.
- The frame's left-right mirror swaps light and dark, so the complex index flips with it.

**Why it should work for Fork.**
- E12: queens-on B-vs-N is the single largest error class that is also common (win-probability error 0.080, 12.7% of gauntlet loss turning points, the leading class between two Forks, training ratio 3.1). Good and bad bishops are a pawn-colour question.
- Pawn links paid +46 at fixed nodes for 0.895 nps, and their measured cost was mostly finding pairs (about 200 instructions per node). This family has no finding cost, only about one row operation per move on average.
- By the think tank's price (one extra 512-wide row change ≈ 3.5–7 Elo), the gain must clear roughly 5 Elo.

**Novelty and nearest relatives.** A new member of a known family, not a new paradigm; say so in any write-up. Nearest: R36's candidates (king-zone pawn links C4, passed-pawn rows, minor × supporting pawn), the engineering review's king-offset inputs, the survey's material-routed buckets (H9), and classical bad-bishop terms. It belongs inside R36's existing screen.

**Expected gain and main risk.** +3 Elo net of speed (−4 to +10). Risk: a single SCReLU layer already forms bishop × pawn products, so the rows add little; and up to 64 more active rows need the loader's int16 bound re-derived.

**Cheapest falsifier.** R36's own screen: price it with the zero-row build (1 quiet CPU-hour) and measure how much of the deep-label residual the family explains on the gold set (CPU minutes).
- **Kill:** under 0.5% of residual variance, or speed below 0.95.
- If it lives: warm-start with the new rows at zero, 4.4 GPU-hours, FN_adj screen, STC SPRT.

**Code changes.** `net_shape.hpp` (a new architecture id and row block), `contacts.{hpp,cpp}` (the row list and its changes), `accumulator.cpp` (`FeatureDelta` carries the bishop-complex flags), `net_file.cpp` (bounds), `tools/nnue/contacts.py`, `models.py`, `reference.py`, `tools/train`.

---

## Ranking by expected Elo per unit of cost

One effort unit (EU) is the think tank's: an engineering day, 8 GitHub-hours, 10 GPU-hours or 10 CPU-hours. "Chance" is my guess that the idea passes its SPRT. "Cost to kill" is what the falsifier costs; "full cost" is everything through the SPRT. The last column is chance × central Elo ÷ full cost, so it charges every idea as if it ran to the end; an idea with a cheap kill test is better than its number.

| Rank | Idea | Class | Central Elo if it works | Chance | Cost to kill (EU) | Full cost (EU) | Expected Elo per EU |
|---|---|---|---|---|---|---|---|
| 1 | 4. Multi-fidelity heads | novel combination | +4 | 40% | 0.8 | 2.8 | 0.57 |
| 2 | 2. Label the unsaved half | novel | +3 | 45% | 1.0 (small-net pair) | 3.5 | 0.39 |
| 3 | 5. Label super-resolution | novel | +3 | 30% | 0.5 | 2.5 | 0.36 |
| 4 | 7. Class-matched TD horizon | novel combination (refinement) | +2 | 30% | 0.3 | 1.8 | 0.33 |
| 5 | 1. Nested-width evaluation | novel combination | +6 (wide form: more) | 35% | 2.3 | 9 | 0.23 |
| 5 | 3. Colour-coherent split search | novel combination | +4 (more against anchors) | 35% | 1.5 | 6 | 0.23 |
| 5 | 8. Pawn-clocked context rows | novel combination (new family member) | +3 | 30% | 0.5 | 4 | 0.23 |
| — | 6. Evaluator-diverse Lazy SMP | novel | +3 at 8 threads; +10 to +30 at TCEC, unmeasurable | 30% | 1.0 after 17a | 3.5 | 0.26 at 8 threads; not comparable at TCEC scale |

Reading the table:
- The numbers are within a factor of 2.5 of each other and every input is a guess, so treat the order as three groups: the label ideas (4, 2, 5, 7), the structural ideas (1, 3, 8), and idea 6 on its own.
- The label ideas lead because they are cheap, not because they are large. That matches Fork's own record (E1).
- Idea 1 has the highest ceiling of the single-thread ideas and is the only one that changes what a future wider net costs.
- Idea 6 is the only one aimed at where the engineering review says the Elo is (512 threads). It cannot be tested before step 17a, and its real payoff is at a thread count Fork cannot test at all.

**Novel** (no relative I know does the same thing): 2, 5, 6.
**Novel combination of known parts:** 1, 3, 4, 7, 8.

---

## The three to test first

This is not the top three of the table: idea 7 gives way to idea 1, because a +2 refinement cannot be resolved against ±6 Elo of seed noise and idea 1's test answers a larger question.

1. **Idea 2, label the unsaved half.** It is the only idea here whose raw material is already paid for: 45% of every split-search part sits unused on disk. It needs no engine change, fits the next retrain round as one arm, and tests a clean question (do adjacent positions add anything at equal games?) whose answer also decides idea 3's economics.
2. **Idea 4's CPU probe, with idea 5's regression riding on the same gold set.** Both run on data that exists today (the label-depth arms, the 80,000-node slice, idea 51's and 52's gold labels), cost CPU-hours and no GPU, and each ends in a number with a declared kill line. Between them they say whether Fork's labels are being held back by their budget, which is also what idea 62 is spending three days of generation to learn.
3. **Idea 1's accuracy oracle.** One FN stage on machinery that already exists decides whether a weaker evaluation far from the window is nearly free, as the control split implies. If it is, Fork has a route to a faster net now and an affordable wider net later; if it is not, the control split's reading needs revising, which is worth knowing before any more near-window work.

Design in now, at no cost: keep the network pointer per searcher when step 17a is built, so idea 6 is a configuration and not a refactor.

---

## Considered and left out

- **A search-site slice** (train on positions sampled from the search tree, not the game line; motivated by E14). It overlaps idea 61 part 3 (near-window deep labelling, "possibly the base net's"), and the one model trained on search sites, idea 59's refiner, lost. One free measurement is still worth making: static error at the 5,433 crucial-point sites against game positions matched by phase and score band. If sites are no worse, the covariate-shift worry closes.
- **Two-seed weight soups.** Already in the think tank (W5, X4).
- **King-zone pawn links and king-offset inputs.** Already R36's C4 and the engineering review's idea 5.
- **A move-specific futility margin from a table of expected eval gains.** A gains table of this kind was standard in older engines; not novel.
- **Trend-driven draw value** (prefer draws when the game-level score is sliding). The think tank lists contempt as "never", the evidence that drawing lines existed in the lost games is missing, and it cannot be tested in self-play.
- **Branching self-play to average several results per position.** At equal CPU, fresh games carry the same information.

## Sources to credit if any idea is built (all UNVERIFIED, from memory)

- Wu, "Accelerating Self-Play Learning in Go" (KataGo), arXiv:1902.10565: playout-cap randomization, short-term value targets, asymmetric playouts.
- Kusupati et al., "Matryoshka Representation Learning" (2022); Yu et al., "Slimmable Neural Networks" (2018).
- Viola and Jones (2001) and the Chess Programming Wiki's "Lazy Evaluation", as idea 59 already credits.
- Liu and Yao, "Ensemble learning via negative correlation" (1999).
- Kennedy and O'Hagan, "Predicting the output from a complex computer code when fast approximations are available" (2000).
- Sutton (1988) and Baxter, Tridgell and Weaver (TDLeaf(λ)), as idea 51 already credits.
- Vinyals et al., "Grandmaster level in StarCraft II using multi-agent reinforcement learning" (2019), for league and exploiter self-play.

## Copied into the repo (2026-11-11)

Copied unchanged by the coordinating session after the personal-data scan. The owner recorded ideas 1-8 as candidates 79-86 in docs/ideas.md (novelty UNVERIFIED until a prior-art check), with the plan in DESIGN.md's decisions log, 2026-11-11.
