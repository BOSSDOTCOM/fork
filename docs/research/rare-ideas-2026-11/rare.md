# Rare techniques with a measured gain (one to three engines)

Part of the rare-ideas survey of 2026-11-15 (README.md). Every idea here is **REFERENCE ONLY**; every engine's
code, nets and data are **OFF-LIMITS**. Every Elo figure is the engine's own report under its own conditions,
and SPRT stopping inflates the point estimate of a passing test. No other engine's constant, margin, threshold
or code identifier is recorded.

## How to read an entry

- **Id.** RI-01 to RI-45, grouped by theme. The bracket gives the section ids the entry merges: G1-xx (group 1),
  G2-n (group 2's candidates R1-R10, renamed so they do not collide with the think tank's R1-R41), G3-n (group 3's
  R3-n), G4-xx (group 4's letters). The think tank's list is always written R1-R41.
- **Count.** Engines whose prose describes the same mechanism. "Possible" engines (a title only, or a mechanism
  the prose does not state) are listed but not counted. An entry counted at four or more moved to common.md;
  an entry at three or fewer that would pass three with its possible engines is marked **borderline**.
- **Evidence class.** SPRT (bounds), SPRT unresolved, non-regression (passed on bounds such as [-3, 0]: no loss,
  not a gain), fixed games, release (bundled), title only, anecdote. "a / b" is the engine's STC / LTC. TCs are
  the engine's own: mostly 8+0.08 and 40+0.4 (OpenBench engines), 10+0.1 and 60+0.6 (fishtest, Ethereal).
  Stockfish figures are derived by group 1 from each commit's W/L/D.
- **Sources.** "PR/commit only" means the entry rests only on GitHub pull-request or commit text (titles,
  descriptions, squash messages, with OpenBench or fastchess result lines), which is beyond the owner's source
  list (README.md, flag 1). Other source kinds are named.
- **After release.** "after rated" when a group flagged the change as merged after the CCRL-rated version, or
  the date shows it; "not checked" otherwise (README.md, flag 2).
- **Fork.** Status at origin/phase-4 (31701e3), as the groups read ideas.md, the Phase 4 SPRT log and DESIGN.md
  on 2026-11-15, and where this synthesis checked a conflict against those files (README.md, reconciliations).
- **Fit** uses Fork's evidence: the king-region net (4 own-king regions x 768 + 608 pawn-link inputs, 512 SCReLU,
  8 phase heads), the cost lesson (speed cost = accumulator rows changed per move; 1.72 Elo per 1% nps; a
  candidate at speed ratio r must show -118 log2(r) Elo at fixed nodes), the calibrated residual line (idea 186:
  residual share ranks and trims candidate inputs, never kills alone), Lazy SMP next (Fork tests on one thread
  so far), and TCEC's long TC.
- **Cheapest test** names the decision it could change and its cost. "Design R" is Fork's search SPRT design
  ([0, 6] nElo, beta 0.20, cap 8, futility after 2). No test was run for this survey.

## Index

| Id | Technique | Engines (count) | Sources | After release |
|---|---|---|---|---|
| RI-01 | King-attack and threat knowledge in quiet ordering | Reckless, Coda, Triumviratus (3) | PR/commit + Triumviratus NOVELTIES.md | not checked |
| RI-02 | History bonus scaled by moves searched before the cutoff | Stockfish, PlentyChess, Alexandria (3); possible Renegade, Starzix: **borderline** | PR/commit only | Stockfish PV form 2026-11-14: not checked |
| RI-03 | Continuation update scaled by cross-ply consistency | Stockfish (1) | PR/commit only | not checked |
| RI-04 | King-square-relative quiet history | Cinder (1) | PR/commit only | not checked |
| RI-05 | History bonus scaled by the margin over beta | Integral, Viridithas (2); possible Stockfish | PR/commit only | not checked |
| RI-06 | History bonus for the null move's refutation | Viridithas, Potential (2); possible pawnocchio | PR/commit only | not checked |
| RI-07 | Fixed positive intercept on the history bonus | Integral (1) | PR/commit only | not checked |
| RI-08 | Surprise-weighted history bonus | Tcheran, Stormphrax, Velvet (3) | commit + Tcheran CHANGELOG | Tcheran: in 14.0 |
| RI-09 | Continuation history split by the earlier move's tactical state | Ethereal, JustBot (2); possible Stockfish | PR/commit only | JustBot: after rated (0.5.0); Ethereal: presence in 14.25 UNVERIFIED |
| RI-10 | Pawn-structure refutation move | Renegade (1); possible Clover | PR/commit only | not checked |
| RI-11 | Gain history (average eval change of a quiet move) | Incipit (1) | PR/commit only | rated version is the only version |
| RI-12 | Root LMR keyed to the aspiration state | Ethereal (1) | PR/commit only | presence in 14.25 UNVERIFIED |
| RI-13 | Extra reduction for king-move evasions | Ethereal (1) | PR/commit only | presence in 14.25 UNVERIFIED |
| RI-14 | LMR by laterality and best-move chain length | Reckless (1) | PR/commit only | not checked |
| RI-15 | Less LMR in loose alpha windows | Stockfish, Reckless (2) | PR/commit only | not checked |
| RI-16 | Causal reduction | Triumviratus (1) | project document (NOVELTIES.md) | not checked |
| RI-17 | Factorised LMR | Tarnished, Hobbes, Cinder (3); possible Viridithas: **borderline** | PR + Tarnished README + Hobbes 4.0 notes | Hobbes 4.0 notes: after rated (3.0) |
| RI-18 | Double extension with a single legal move | Renegade (1) | PR/commit only | not checked |
| RI-19 | Singular and double-extension margins moved by correction value or quiet history | Potential (1) | PR/commit only | not checked |
| RI-20 | Stay out of quiescence when the TT holds a move | Reckless, PlentyChess, Stockfish (3); possible PZChessBot: **borderline** | PR/commit only (an OpenBench branch name for the possible engine) | not checked |
| RI-21 | Quiescence check before an RFP cutoff at the top RFP depths | Hobbes (1) | PR/commit only | not checked |
| RI-22 | Improving flag in RFP only under a high-value threat | PlentyChess (1) | PR/commit only | not checked |
| RI-23 | More LMP when the static eval suggests a fail high | Integral (1) | PR/commit only | not checked |
| RI-24 | NMP skipped when the TT move is a valuable piece's | Potential (1) | PR/commit only | not checked |
| RI-25 | Skip SEE when the destination square is unattacked | Hobbes, pawnocchio (2) | PR/commit only | not checked |
| RI-26 | No TT cutoff near the fifty-move horizon | Stockfish, Cinder, Stormphrax (3) | PR/commit only | not checked |
| RI-27 | Depth-relaxed TT cutoffs | Ethereal, Halogen (2) | PR/commit only | Halogen: before 16.0.0 |
| RI-28 | An exact result may replace a lower-bound entry | Halogen (1) | PR/commit only | before 16.0.0 |
| RI-29 | TT replacement penalising window-mismatched entries | Stockfish (1) | commit + issue #6742 | not checked |
| RI-30 | Graph-history-interaction mitigation for transpositions | Reckless, Alexandria (2; Alexandria counter-evidence) | PR/commit only | not checked |
| RI-31 | Correction update toward the mean of raw and corrected eval | Motor, Renegade (2) | PR/commit only | not checked |
| RI-32 | Correction keys by material band or halfmove clock | Reckless, Triumviratus (2) | PR + Triumviratus NOVELTIES.md | not checked |
| RI-33 | Correction keyed by a hash of the net's hidden state | Seer (1) | TCEC questionnaire + PR squash message | **after rated (2.8.0)** |
| RI-34 | Lazy SMP hygiene: barrier start and stop, no stores from aborted helpers | Tarnished, RubiChess (2) | PR/commit only | RubiChess: after rated |
| RI-35 | Thread diversity: per-thread offsets and helper reduction bias | Stockfish, Reckless, Potential (3); possible Clover: **borderline** | PR/commit only | not checked |
| RI-36 | Majority thread vote for the soft stop | Reckless (1) | PR/commit only | not checked |
| RI-37 | SMP-only TT store of intermediate results | Reckless (1) | PR/commit only | not checked |
| RI-38 | Table sizes scaled with the thread count | Potential (1) | PR/commit only | not checked |
| RI-39 | Output-bucket factoriser in training | Incipit (1) | PR/commit only (and the network survey's group-b record) | rated version is the only version |
| RI-40 | Label shrink toward a draw for drawish material | Velvet (1) | commit + release notes | in 7.2.0 |
| RI-41 | Elementary-mate regression suites | Stockfish (1) | issue thread #6742 + commit | not checked |
| RI-42 | Elo by game length in release gauntlets | Velvet (1) | release notes | n/a (practice) |
| RI-43 | Hardware-sensitivity checks (A/A, per-machine splits) | Triumviratus (1) | project document (DEVELOPMENT_8.0.md) | n/a (practice) |
| RI-44 | SPSA from a deliberately biased start | Coda (1) | PR/commit only | not checked |
| RI-45 | Bayesian optimisation of a constant group | Reckless, Ethereal (2) | PR/commit only | Ethereal: presence in 14.25 UNVERIFIED |

---

## A. Move ordering and history

### RI-01. King-attack and threat knowledge in quiet move ordering [G1-01]
- **What:** static, cheap knowledge about attacks on the enemy king and threats added to the ordering score of
  quiet moves: resist moving the pawns in front of one's castled king; reward rook moves that hit the enemy
  king's surroundings, attacks from squares the enemy cannot contest ("offense" squares, for pieces and for the
  queen), pawn pushes that attack from advanced squares, moving a threatened piece out of harm; slider threats
  seen through one's own queen, with a penalty for the queen stepping into a threat.
- **Engines (3):** Reckless; Coda (a "good quiet" bonus for quiets whose best enemy target outweighs the moving
  piece, stacked on a Reckless-style offense bonus); Triumviratus (king shield, outposts, safe-square attacks).
- **Reported gain:** Reckless, seven SPRTs passed at 8+0.08 and 40+0.4, [0, 3]: +1.42 / +2.02, +2.34 / +1.13,
  +2.45 / +3.66, +1.23 / +5.74, +2.20 / +2.04, +1.97 / +2.10, +3.40 / +1.26 (summed LTC about +18; stacked terms
  rarely add fully). Coda +2.6 at [0, 3] after about 25,000 games. Triumviratus: each term neutral alone (-1.57,
  +0.21, +0.39, each about ± 4-5), an ordering SPSA vector +3.4 ± 3.9 (about 8,100 games), a later ordering SPSA
  flat. **Evidence:** SPRT at STC and LTC (Reckless), SPRT (Coda), fixed games (Triumviratus).
- **Why not spread:** each term needs attack sets per move; Triumviratus measured its ordering bundle plus its
  causal reduction at about 3.7% more instructions per node.
- **Fork:** has the direct-check ordering bonus (D13, adopted 2026-11-12) and threat-aware quiet ordering (T56
  any-attack, adopted 2026-11-11: STC +7.49 ± 4.89, LTC +8.07 ± 5.15; the cheaper-attacker form lost -6.08 on
  2026-11-06). The "move a threatened piece out of harm" term overlaps T56; the king-attack terms are never tried.
- **Fit:** good. Fork's net sees the board through own-king regions; king-attack knowledge in ordering is
  search-side and adds no accumulator rows, but the attack sets cost nps, so the cost lesson applies as an nps
  rule (1.72 Elo per 1%). T56's sets may be reusable (UNVERIFIED).
- **Cheapest test:** the two Reckless terms with the best LTC records (queen offense squares; attacks from safe
  squares): nps A/B with bench/ab.py, then one design R STC SPRT per term at a natural value. *Decision:* whether
  king-attack knowledge in ordering complements the king-region net. *Cost:* two builds, two A/B runs, two to
  four STC SPRTs.
- **Sources:** PR/commit only for the figures; the concept also in Triumviratus's NOVELTIES.md.

### RI-02. History bonus scaled by the number of moves searched before the cutoff [G1-09] (borderline)
- **What:** the best move's history bonus grows with how many other moves were tried before it cut off.
- **Engines (3):** Stockfish (non-PV nodes; extended to PV nodes as a non-regression on 2026-11-14), PlentyChess
  (idea credited to Alexandria's search rewrite), Alexandria. Possible: Renegade's "apply move-ordering bonuses as
  many times as failing high" (+3.35 ± 2.29, [0, 3]; also credited to Alexandria, mechanism UNVERIFIED) and a
  Starzix title ("a bigger bonus the more times PVS fails high"); if either is the same idea, the entry is common.
- **Reported gain:** Stockfish +0.92 / +2.27 (derived); PlentyChess +2.12 ± 1.65 at 8+0.08. **Evidence:** SPRT at
  STC and LTC (Stockfish), SPRT at STC (PlentyChess).
- **Why not spread:** small; bonus-shape tuning (D11) competes for the same effect.
- **Fork:** never tried. The linear bonus (D11 / R15) is adopted; it scales by depth only.
- **Fit:** medium. Zero nps cost, sits on the bonus Fork just changed.
- **Cheapest test:** one design R STC SPRT of one switch at a natural scale. *Decision:* whether the bonus gains a
  move-count axis. *Cost:* one STC SPRT.
- **Sources:** PR/commit only.

### RI-03. Continuation-history update scaled by cross-ply consistency ("CMHC") [G1-08]
- **What:** the size of each continuation-history update depends on how consistently the move scores well across
  the stacked plies' tables: consistent moves move more, inconsistent ones less.
- **Engines (1):** Stockfish (8b6d8def, 2026-03-07).
- **Reported gain:** +1.39 / +2.48 (derived). **Evidence:** SPRT at STC and LTC.
- **Why not spread:** recent; one engine.
- **Fork:** never tried. D8 (the summed update base) is adopted, which this would refine.
- **Fit:** medium; no nps cost; LTC-leaning, which suits TCEC.
- **Cheapest test:** one design R STC SPRT. *Decision:* adopt or drop. *Cost:* one STC SPRT.
- **Sources:** PR/commit only.

### RI-04. King-square-relative quiet history [G1-10]
- **What:** a quiet-history table indexed also by the own king's square, or by the enemy king's square.
- **Engines (1):** Cinder.
- **Reported gain:** own king +2.26 ± 1.78 (45,594 games); enemy king +1.55 ± 1.26 (91,954 games), both at 1+0.01,
  [0, 3]. **Evidence:** SPRT at a very short TC.
- **Why not spread:** a much larger table (cache pressure); only very short-TC evidence.
- **Fork:** never tried.
- **Fit:** the king-relative indexing mirrors the king-region net's view of the board, but a table this size is a
  cache cost on the hot path, so an nps A/B comes first.
- **Cheapest test:** nps A/B, then one design R STC SPRT. *Decision:* whether king-relative history earns its
  memory. *Cost:* one A/B, one SPRT.
- **Sources:** PR/commit only.

### RI-05. History bonus scaled by how far the best score beat beta [G2-4]
- **What:** when a quiet move causes a cutoff, its bonus (and the maluses of the moves before it) grows when the
  score cleared beta by a wide margin; the bonus reflects the size of the refutation, not only depth.
- **Engines (2):** Integral (#104, a margin over beta); Viridithas (#344, updates scaled by the best score instead
  of alpha). Possible: Stockfish (UNVERIFIED, not re-read).
- **Reported gain:** Integral +2.79 ± 2.04 at 8+0.08, [0, 3]; Viridithas +4.33 ± 2.67 at 8+0.08, [0, 3].
  **Evidence:** SPRT at STC, two engines.
- **Why not spread:** small STC-only results; many engines tune the bonus shape instead (D11).
- **Fork:** never tried (the linear bonus scales by depth only).
- **Fit:** medium; pure ordering, zero speed cost.
- **Cheapest test:** one design R STC SPRT at a natural scale; a head-to-head ladder only if the natural value
  stops for futility. *Decision:* whether the bonus gains a second axis. *Cost:* one SPRT.
- **Sources:** PR/commit only.

### RI-06. History bonus for the move that refuted a null move [G2-6, G4-P4]
- **What:** when the null-move search fails low (passing was refuted), the refuting move gets a quiet-history
  bonus, so the threat is tried early elsewhere.
- **Engines (2):** Viridithas (#352); Potential (#427, title-based, mechanism UNVERIFIED, idea credited to
  J. Hallström, pawnocchio's author). Possible: pawnocchio (UNVERIFIED).
- **Reported gain:** Viridithas +2.32 ± 1.76 at 8+0.08, [0, 3] (2025-11). Potential STC +10.05 ± 6.05, LTC
  +7.92 ± 5.01, [0, 5], in its hand-crafted-eval era (a much weaker engine). **Evidence:** SPRT at STC
  (Viridithas); SPRT at STC and LTC in a weak engine (Potential, counted one level lower in ranking.md).
- **Why not spread:** small, recent; most engines keep the null search's best move only as a "threat move".
- **Fork:** never tried. D9 (prior-move credit, a different update) was rejected (H0, then a futility stop,
  2026-11-12; ideas.md 76).
- **Fit:** medium; zero runtime cost; Fork's history tweaks have been mixed.
- **Cheapest test:** one design R STC SPRT, the bonus at the normal cutoff bonus. *Decision:* adopt or not.
  *Cost:* one SPRT.
- **Sources:** PR/commit only.

### RI-07. Fixed positive intercept on every history bonus [G2-7]
- **What:** a constant added to the depth-based bonus, so even shallow cutoffs move the history by a minimum.
- **Engines (1):** Integral (#138).
- **Reported gain:** +5.24 ± 3.06 at 8+0.08, [0, 3] (2024-11). **Evidence:** SPRT at STC.
- **Why not spread:** overlaps bonus-shape tuning; engines that SPSA the bonus formula have it implicitly.
- **Fork:** never tried; Fork's linear bonus has no intercept.
- **Fit:** medium-low; one more dimension for the final retune.
- **Cheapest test:** the intercept at zero as one SPSA dimension in the final retune; a separate SPRT only if it
  moves clearly off zero. *Decision:* whether the bonus gets an intercept. *Cost:* one SPSA dimension.
- **Sources:** PR/commit only.

### RI-08. Surprise-weighted history bonus [G3-4]
- **What:** a quiet move that causes a cutoff the static evaluation did not predict gets a larger bonus. Tcheran's
  form: the static eval was below alpha. Velvet's form: the move had no positive history.
- **Engines (3):** Tcheran (5fb1eed, 2026-07-28, in 14.0; the commit credits Stormphrax), Stormphrax (by that
  credit; its own figure not read: UNVERIFIED), Velvet (a0e038b, 2024-01-02).
- **Reported gain:** Tcheran +2.66 ± 2.14 at 8+0.08, [0, 5], 26,514 games. Velvet: no figure. **Evidence:** SPRT
  at STC (one engine); anecdote (Velvet).
- **Why not spread:** small STC gain; overlaps other bonus-shape tweaks (D11).
- **Fork:** never tried. Fork has the linear bonus (D11) and the summed pair update (D8); D9 failed twice
  (-11.95, -1.95), so history tweaks have not all transferred.
- **Fit:** good; no speed cost; a natural factor (double the bonus) as the first value.
- **Cheapest test:** one design R STC SPRT at the natural factor. *Decision:* adopt or drop. *Cost:* one SPRT.
- **Sources:** commit text plus Tcheran's CHANGELOG (a project document).

### RI-09. Continuation history split by the earlier move's tactical state [G3-7]
- **What:** the continuation tables get a separate slice by whether the earlier move was a capture (or otherwise
  tactical), so follow-ups to captures and to quiet moves are learned apart.
- **Engines (2):** Ethereal (bdeaaae, 2021-11-29, "idea first seen in Stockfish"); JustBot (#180, 2026-10-13,
  after its rated 0.5.0). Possible: Stockfish (not re-read: UNVERIFIED).
- **Reported gain:** Ethereal +2.50 ± 2.00 at 10+0.1 (31,608 games), +3.72 ± 2.39 at 60+0.6 (13,072), [0, 5].
  JustBot +0.18 ± 1.21 STC (82,356), +2.90 ± 2.05 LTC (25,966), [0, 3]. **Evidence:** SPRT, both LTC-led.
- **Why not spread:** doubles the tables and their cache footprint; LTC-only gains.
- **Fork:** never tried. Whether the earlier move's capture flag is part of Fork's pair-table key is UNVERIFIED;
  it is not in the switch list.
- **Fit:** medium; a memory cost on the hot path (nps check); LTC-first per the evidence; interacts with the pair
  tables' colour-fold question at TCEC thread counts (DESIGN.md step 17a).
- **Cheapest test:** nps A/B (bench/ab.py), then an LTC design R SPRT. *Decision:* adopt or drop. *Cost:* one A/B,
  one LTC SPRT.
- **Sources:** PR/commit only.

### RI-10. Pawn-structure refutation move [G4-R1]
- **What:** a move-ordering slot keyed by the pawn hash: the move that last refuted in this pawn structure gets an
  ordering bonus.
- **Engines (1):** Renegade (#105, then tuned in #106). Possible: Clover (#324, "the move that was best before in
  the same king-and-pawn structure", title only, no figure).
- **Reported gain:** +2.14 ± 1.67, [0, 3], 43,514 games; tuned +2.64 ± 1.95, 31,796 games (10+0.1).
  **Evidence:** SPRT at STC.
- **Why not spread:** small; overlaps killer-style ordering, which many engines dropped.
- **Fork:** never tried. Fork has no killers or countermoves (D16).
- **Fit:** low.
- **Cheapest test:** none recommended now; if ever, one design R STC SPRT.
- **Sources:** PR/commit only (Renegade's TCEC questionnaire names four "small novelties"; which four was not
  recorded by group 4: UNVERIFIED).

### RI-11. Gain history [G4-I2]
- **What:** a table by piece and destination learns the average change in corrected static eval a quiet move
  brings, from evals the search computes anyway, and adds it to quiet ordering.
- **Engines (1):** Incipit (the author calls it "probably unique"; a gains table was standard in older engines).
- **Reported gain:** STC +1.6 ± 1.2 (86.7k games); medium TC +0.9 ± 1.8 (35.5k, not significant); non-regression
  -0.3 ± 1.6; used in history pruning +0.5 ± 1.0 (128.6k games). Incipit's "STC" TC is not stated (UNVERIFIED).
  **Evidence:** SPRT at STC.
- **Why not spread:** small gain.
- **Fork:** considered and left out as "not novel" (docs/research/novel-ideas-2026-11-11.md).
- **Fit:** low.
- **Cheapest test:** not recommended.
- **Sources:** PR/commit only.

## B. Reductions and extensions

### RI-12. Root LMR keyed to the aspiration state [G3-1]
- **What:** the root knows whether this iteration re-searches after a fail high or a fail low. After a fail
  high, every root move except the previous best is reduced; after a fail low, root moves are reduced less.
- **Engines (1):** Ethereal (993abdc, 2020-07-23). Other root-LMR tweaks found are different ideas (PZChessBot
  less LMR at the root, +3.70 STC / +2.23 LTC; Tcheran and Quanticade start root LMR later, +0.50 and +0.94;
  pawnocchio delays root LMR to later moves, +5.74 ± 3.18 at 10+0.1).
- **Reported gain:** +2.98 ± 2.35 at 12+0.12 (29,968 games), +3.14 ± 2.42 at 60+0.6 (20,000 games), [0, 5].
  **Evidence:** SPRT at STC and LTC, in Ethereal's hand-crafted-eval era; whether it is still in 14.25 is
  UNVERIFIED (a 2022 commit standardised Ethereal's LMR as a non-regression).
- **Why not spread:** most engines had no root LMR or kept it plain; small; old.
- **Fork:** never tried. Fork reduces late quiet root moves by the plain table since 2026-11-13 (idea 124:
  +17.71 STC, +14.94 LTC), with no context terms. The audit-1 B-3 change (root fail-high re-searched one ply
  shallower) is a different mechanism (iteration depth, not per-move reductions).
- **Fit:** high; no accumulator cost; no constant in its sign-only form; builds on a feature just adopted;
  aspiration fails happen in every TCEC search.
- **Cheapest test:** behind a switch (bench unchanged when off), one design R STC SPRT against off; one LTC
  confirmation if it passes. *Decision:* adopt or drop the root aspiration term. *Cost:* one STC SPRT (Fork's
  recent ones stopped after 3,200 to 12,800 games), one LTC SPRT on a pass.
- **Sources:** PR/commit only (Ethereal commit message).

### RI-13. Extra reduction for king-move check evasions [G3-6]
- **What:** among late quiet evasions, a king move is reduced one step more than other evasions.
- **Engines (1):** Ethereal (05e1cc4, 2019-05-26).
- **Reported gain:** +2.15 ± 1.71 at 10+0.1 (64,140 games), +6.53 ± 4.27 at 60+0.6 (8,200 games), [0, 5].
  **Evidence:** SPRT at STC and LTC; hand-crafted-eval era; presence in 14.25 UNVERIFIED.
- **Why not spread:** a narrow case; many engines changed evasion LMR wholesale instead.
- **Fork:** never tried. Fork gives late quiet evasions the normal reduction (`use_lmr_in_check`, +4.21 ± 2.89).
- **Fit:** good; one whole-ply term (a natural value), no nps cost; LTC-leaning, which suits TCEC.
- **Cheapest test:** one design R STC SPRT at one whole ply; LTC if it passes or reaches the cap undecided.
  *Decision:* adopt or drop. *Cost:* one STC SPRT.
- **Sources:** PR/commit only.

### RI-14. LMR by "laterality" and by best-move chain length [G1-06]
- **What:** reductions grow with the accumulated lateral distance of a node from the main line ("laterality"),
  and separately with the length of the chain of best moves leading to it (inspired by heavy-light
  decomposition). The exact definition beyond that is UNVERIFIED.
- **Engines (1):** Reckless.
- **Reported gain:** laterality +6.13 / +2.21; chain length +2.03 / +1.82; SPRT [0, 3] at 8+0.08 and 40+0.4.
  **Evidence:** SPRT at STC and LTC.
- **Why not spread:** recent; the prose does not define it fully.
- **Fork:** never tried.
- **Fit:** medium; no nps cost; Fork would have to define the measure itself (a design task, not a port).
- **Cheapest test:** define the measure from the concept, then one design R STC SPRT. *Decision:* adopt or drop.
  *Cost:* design time plus one SPRT.
- **Sources:** PR/commit only.

### RI-15. Less LMR in loose (wide) alpha windows [G1-15]
- **What:** less reduction when the alpha-beta window at the node is wide.
- **Engines (2):** Stockfish (5f7348f0, 2026-08-19), Reckless.
- **Reported gain:** Reckless +2.19 / +4.27; Stockfish +1.48 / +1.10 (derived). **Evidence:** SPRT at STC and LTC
  in both.
- **Why not spread:** recent.
- **Fork:** a relative was tried and retired: idea 61 part 5 (window-aware LMR, reduce less near the window),
  futility stop at STC, -2.93 ± 7.16 (2026-11-08; the SPRT log credits Stockfish 5f7348f0 at concept level).
  The wide-window form itself is untested.
- **Fit:** low-medium after Fork's own retired relative.
- **Cheapest test:** one design R STC SPRT of the wide-window form only if the owner wants the family reopened.
  *Decision:* whether the window-width form differs from the retired one. *Cost:* one SPRT.
- **Sources:** PR/commit only.

### RI-16. Causal reduction [G1-13]
- **What:** after a quiet move fails low, the squares involved in the opponent's refutation are marked; later
  quiet siblings that touch none of them get a fractional extra reduction (checks, the hash move and passed-pawn
  pushes excluded; nothing pruned).
- **Engines (1):** Triumviratus (author's idea).
- **Reported gain:** +4.27 ± 4.13 at 25+0.25 over 6,594 games, stopped at LLR 1.17 once zero was excluded; two
  follow-up variants scored negative before SPSA. **Evidence:** early-stopped SPRT (close to fixed games).
- **Why not spread:** new, one engine, weak evidence.
- **Fork:** never tried.
- **Fit:** medium; small bookkeeping per node.
- **Cheapest test:** one design R STC SPRT. *Decision:* adopt or drop. *Cost:* one SPRT.
- **Sources:** project document (NOVELTIES.md), not PR/commit text.

### RI-17. Factorised LMR [G1-21, G2-5] (borderline)
- **What:** the reduction assembled from tuned terms, one per condition (improving, cut node, TT-PV, capture,
  check and so on), and, per the name, tuned terms for combinations of conditions, found by SPSA and stored in a
  precomputed table. Whether pairwise combination terms are included is UNVERIFIED.
- **Engines (3):** Tarnished (#58, #72, #138; README "Late Move Reductions (Factorized formulation)"), Hobbes
  (#413; 4.0 release notes), Cinder. Possible: Viridithas "FLKR" (#248, +13.86 ± 5.07 at 40+0.4, [0, 3]; the PR
  has no prose, meaning UNVERIFIED); if it is the same idea, the entry is common.
- **Reported gain:** Tarnished +4.03 ± 3.03 at 8+0.08 and +6.35 ± 4.12 at 40+0.4, [0, 5]; its precomputed table
  +5.98 ± 3.30 at 4+0.04, [0, 3]. Hobbes +1.82 ± 1.45 at 20+0.2 with 4 threads, [0, 3]. Cinder non-regression at
  1+0.01 (+2.53 ± 2.98, [-3, 1]), seeding the factors +3.86 ± 2.52 at 10+0.1, [0, 3]. **Evidence:** SPRT at STC
  and LTC (Tarnished), SPRT (Hobbes, Cinder). Counter-evidence for the learned-from-data form: Triumviratus's
  offline-learned reductions went H0 (-1.36 ± 1.44, about 60,000 games); Tarnished's "Base LMR NN" passed STC
  (+5.20 ± 3.68, [0, 5]) and was reverted by its author as "flawed logic, magic STC pass".
- **Why not spread:** needs an SPSA budget for many more parameters; small once a hand-made LMR is tuned.
- **Fork:** never tried. Fork's LMR is a log-log table plus additive terms (check relief, cut node, not improving,
  the centred history term): per-condition terms without combination terms. Idea 55 (a learned reduction) is the
  larger version.
- **Fit:** medium; LMR terms are allowed in SPSA (decision 4 excludes only time management); each combination term
  needs a recorded justification (the constants rule).
- **Cheapest test:** combination terms for the four or five conditions Fork has, at zero (bench identical), as
  dimensions of the final retune's SPSA; drop any whose tuned value stays within its noise band; one design R SPRT
  of the survivors against none. *Decision:* whether Fork's LMR gets interaction terms before idea 55. *Cost:*
  extra SPSA dimensions in a run that happens anyway, then one SPRT.
- **Sources:** PR text plus Tarnished's README and Hobbes's 4.0 release notes (for the concept).

### RI-18. Double extension when the side to move has a single legal move [G4-R2]
- **What:** inside the tree, a node with only one legal move is extended by two plies.
- **Engines (1):** Renegade (#66). The classical single-reply extension is old (CPW); no other top-50 use was found.
- **Reported gain:** +2.66 ± 2.04, [0, 3.5], 28,244 games at 10+0.1 (the author did not expect it to pass).
  **Evidence:** SPRT at STC.
- **Why not spread:** small; the positions are rare.
- **Fork:** never tried in the tree. Fork stops the root early with one legal move (forced-move stop), a root-only
  cousin.
- **Fit:** medium; no constant beyond the natural "two plies".
- **Cheapest test:** one design R STC SPRT. *Decision:* adopt or drop. *Cost:* one SPRT. Low priority.
- **Sources:** PR/commit only.

### RI-19. Singular and double-extension margins moved by the correction value or quiet history [G4-P5, P6]
- **What:** the low-depth singular-extension margin is adjusted by the node's correction value; the
  double-extension margin by quiet history, or by the correction value.
- **Engines (1):** Potential (hand-crafted eval when measured; much weaker than Fork).
- **Reported gain:** low-depth SE by correction: LTC +9.13 ± 5.41, [0, 5], 5,442 games (#545). Double extension by
  quiet history: LTC +4.85 ± 3.38 (#387). Double extension by correction: LTC +0.74 ± 2.66 (stopped), 120+1.2
  +7.05 ± 5.20 (#456), VLTC only. **Evidence:** SPRT at LTC and VLTC in a weak engine.
- **Why not spread:** one weak engine; LTC- and VLTC-only gains are costly to confirm.
- **Fork:** never tried. Related: correction size in pruning (C15) never tried; double extensions queued LTC-only
  (R28).
- **Fit:** TCEC's long TC matches; needs LTC SPRTs.
- **Cheapest test:** after R28, one LTC design R SPRT. *Decision:* the margin's form. *Cost:* one LTC SPRT.
- **Sources:** PR/commit only.

## C. Pruning and quiescence

### RI-20. Stay out of quiescence when the TT holds a move [G1-02, G3-8] (borderline)
- **What:** a node about to drop into quiescence (or a quiescence node) whose TT entry holds a quiet move is
  searched as a one-ply main-search node instead, so the quiet TT move is tried; variants gate it by the TT
  entry's depth or bound.
- **Engines (3):** Reckless ("reverse qsearch"; refined so an upper-bound entry does not trigger it; a guard
  against two null moves in a row that this path could cause), PlentyChess ("sometimes prevent the qsearch drop
  for TT moves"), Stockfish (its existing extension of nodes about to enter qsearch, now allowed only with a deep
  enough TT entry, 4f4f78f8). Possible: PZChessBot (#136, meaning from its title and the OpenBench branch name
  "qs-pre-ext": UNVERIFIED); if it is the same idea, the entry is common.
- **Reported gain:** Reckless LTC +1.13 (138,604 games), refined LTC +2.68 ± 1.94; the guard LTC non-regression.
  Stockfish +3.02 / +1.48 (derived). PlentyChess non-PV form STC -0.47 (H0) but LTC +1.88 ± 1.42 (passed); PV form
  failed STC and LTC and passed only at 80+0.8, +2.13 ± 1.54. PZChessBot +4.89 ± 3.57 at 8+0.08, [0, 5], 11,148
  games. **Evidence:** SPRT; LTC passes in three engines; a clear scaling-with-TC signature in PlentyChess.
- **Why not spread:** STC tests miss it (PlentyChess's STC H0); risk of tree growth at the horizon.
- **Fork:** never tried.
- **Fit:** good; no nps cost; LTC-leaning evidence suits TCEC; Fork's STC-first pipeline is exactly the filter
  that would miss it.
- **Cheapest test:** one switch (a quiescence node whose TT move is quiet and whose entry is not an upper bound is
  searched as a depth-1 main-search node); a bench node and nps check, then design R at **LTC first**. *Decision:*
  whether quiescence should ever re-enter the main search. *Cost:* one build, one LTC SPRT.
- **Sources:** PR/commit only (plus an OpenBench test page's branch name for the possible engine).

### RI-21. A quiescence check before an RFP cutoff at the top RFP depths [G2-2]
- **What:** at the upper end of reverse futility pruning's depth range, before taking the cutoff, run a
  quiescence search at beta and prune only if that holds too.
- **Engines (1):** Hobbes (#426, 2026-08). It resembles ProbCut's quiescence pre-check, applied to RFP.
- **Reported gain:** +4.55 ± 2.78 at 8+0.08 and +2.19 ± 1.68 at 40+0.4, [0, 3]. **Evidence:** SPRT at STC and LTC.
- **Why not spread:** a quiescence search per guarded cut; small; recent.
- **Fork:** never tried. Sibling of the threat-gated RFP (common.md CG-2): one targets wrong RFP cuts by a static
  threat test, this one by a tactical search.
- **Fit:** good; it costs nodes, not nps, and only at the deepest RFP depths; it needs a depth bound (a new
  constant: placeholder, then the screen).
- **Cheapest test:** run the X10 decision ledger (stats builds, RFP ledger lines) over the bench and evolve
  positions with CG-2's study; tabulate RFP errors by depth and how many a quiescence search at beta would catch;
  stop if under about a third of the top-depth errors are caught (group 2's estimate, UNVERIFIED); else a design R
  STC SPRT, then LTC. *Decision:* whether RFP's deepest band needs a tactical check. *Cost:* shares CG-2's ledger
  run (about 1-2 CPU-h), then one or two SPRTs.
- **Sources:** PR/commit only.

### RI-22. Improving flag in RFP only when the opponent threatens a high-value piece [G1-14]
- **What:** the improving adjustment to RFP is applied only when the opponent has a threat against a high-value
  piece.
- **Engines (1):** PlentyChess (#281).
- **Reported gain:** +1.85 ± 1.48 at 8+0.08, [0, 3]. **Evidence:** SPRT at STC.
- **Why not spread:** small, one engine.
- **Fork:** the plain form (B8, rising RFP) failed (-3.78 ± 2.92); this gated form is untested. Halogen's plain
  improving-RFP passed at STC and LTC (evidence.md, B8).
- **Fit:** medium; joins the threat-gated RFP family (common.md CG-2).
- **Cheapest test:** one design R STC SPRT, after CG-2's ledger study. *Decision:* whether the improving flag
  returns to RFP in a gated form. *Cost:* one SPRT.
- **Sources:** PR/commit only.

### RI-23. More late-move pruning when the static eval already suggests a fail high [G2-10]
- **Engines (1):** Integral (#203).
- **Reported gain:** +3.13 ± 2.06 at 10+0.1, [0, 2.5]; at 40+0.4 +2.07 ± 2.25, unresolved (LLR 1.37).
  **Evidence:** SPRT at STC; LTC unresolved.
- **Why not spread:** small, one engine.
- **Fork:** never tried; Fork's LMP is scaled by the improving flag (B9, adopted 2026-11-13).
- **Fit:** low-medium; overlaps the improving scaling just adopted.
- **Cheapest test:** one design R STC SPRT. *Decision:* adopt or drop. *Cost:* one SPRT.
- **Sources:** PR/commit only.

### RI-24. Null-move pruning skipped when the TT move is played by a valuable piece [G4-P3]
- **What:** no null move when the TT move belongs to a "valuable" piece (which pieces count: UNVERIFIED).
- **Engines (1):** Potential (#608, NNUE era, 2026-08; a much weaker engine). Common.md CG-4 (NMP adjusted when
  the TT move is a capture) is a different gate.
- **Reported gain:** STC +12.42 ± 6.97, LTC +10.14 ± 6.23, [0, 7.5], about 2,900 games each. **Evidence:** SPRT at
  STC and LTC, wide bounds, weak engine.
- **Why not spread:** one weak engine.
- **Fork:** never tried; Fork's NMP gates are depth, no null in a row, eval at or above beta and non-pawn material.
- **Fit:** medium; "valuable" needs a piece-class definition (a candidate constant to screen).
- **Cheapest test:** one design R STC SPRT with queen moves only as the natural first form. *Decision:* an NMP gate.
  *Cost:* one SPRT.
- **Sources:** PR/commit only.

### RI-25. Skip SEE when the destination square is not attacked [G2-9]
- **What:** a move to a square no enemy piece attacks cannot lose material there, so the SEE call is skipped in SEE
  pruning, quiescence SEE pruning and SEE in LMR. A speed simplification with an identical tree.
- **Engines (2):** Hobbes (#250, #301, #302; idea credited to pawnocchio's author), pawnocchio.
- **Reported gain:** +0.78 ± 2.73 at 4+0.04, +1.68 ± 3.17 and +0.39 ± 2.37 at 8+0.08, all non-regression [-5, 0].
  **Evidence:** non-regression.
- **Why not spread:** pays only when SEE is a visible share of the time.
- **Fork:** never tried; idea 171 (speed sprint 3: captures generation and SEE) is the place for it.
- **Fit:** worth exactly its nps change by the cost lesson (1.72 Elo per 1%).
- **Cheapest test:** a fork_micro or bench/ab.py A/B with bench unchanged; drop under about +0.3% nps (group 2's
  estimate). *Decision:* fold into speed sprint 3 or drop. *Cost:* one A/B run.
- **Sources:** PR/commit only.

## D. Transposition table and the fifty-move rule

### RI-26. No TT cutoff near the fifty-move horizon [G1-07, G2-8]
- **What:** a TT score found with a different halfmove clock can be wrong near the fifty-move limit (a graph-history
  problem), so no TT cutoff is taken there, at least at low depth; Stockfish's form applies when the rule-50 count
  is high and the TT move resets it.
- **Engines (3):** Stockfish (75f07da9, 2025-08-25), Cinder, Stormphrax (#339). Hobbes's fifty-move hash buckets
  (F9) solve the same problem another way.
- **Reported gain:** Stockfish +1.27 / +1.04 (derived); Cinder +2.98 ± 2.21 at 1+0.01, [0, 3]; Stormphrax +0.37 ±
  1.57 at 8+0.08 and +3.79 ± 3.18 at 40+0.4, both on non-regression bounds [-3, 1]. Stormphrax's companion that
  downgrades decisive TT scores beyond the horizon (#338) lost -6.44 ± 4.58 at STC and was merged as a correctness
  change. **Evidence:** SPRT at STC and LTC (Stockfish), SPRT at a very short TC (Cinder), non-regression
  (Stormphrax).
- **Why not spread:** normal books rarely reach the horizon, so tests show little; it is a correctness change.
- **Fork:** never tried. F8 (fifty-move eval scaling) failed; F9 never tried; idea 160 (fifty-move and repetition
  proximity inputs) is a bake-off round 3 candidate.
- **Fit:** TCEC-relevant (long endgames at long TC); no rows change; costs about nothing.
- **Cheapest test:** offline, count TT cutoffs taken with the clock near the limit in Fork's own LTC games; stop if
  under 0.1% of cutoffs (group 2's estimate, UNVERIFIED); else a non-regression design SPRT at LTC on an endgame
  book (Fork's endgame-slice positions). *Decision:* a correctness rule for TCEC. *Cost:* CPU minutes, then one
  LTC SPRT.
- **Sources:** PR/commit only.

### RI-27. Depth-relaxed TT cutoffs [G3-2]
- **What:** a TT cutoff from an entry shallower than the current depth in two situations: (a) Ethereal, when the
  current search will be re-searched anyway (a reduced or null-window search that precedes a re-search); (b)
  Halogen, a fail-high entry whose score clears beta by a margin that grows with the missing depth.
- **Engines (2):** Ethereal (75bfcfb, 2022-08-15), Halogen (#745, 2025-09-21). Obsidian's "TT cutoffs on a fail
  high only from deeper entries" (+2.00 at 60+0.6) goes the opposite way.
- **Reported gain:** (a) +4.34 ± 3.30 at 10+0.1, [0, 4], 21,232 games; +4.59 ± 3.61 at 60+0.6, [0, 5], 17,096;
  +3.43 ± 3.22 at 5+0.05 with 8 threads, [-1, 3], 21,870. (b) +2.26 ± 1.73 at 8+0.08, [0, 3], 41,584.
  **Evidence:** SPRT at STC, LTC and 8 threads (a); STC (b).
- **Why not spread:** TT-cutoff correctness is distrusted; (b) needs a tuned margin; (a) needs the "a re-search will
  follow" context passed down.
- **Fork:** never tried. Fork cuts at non-PV nodes only when the entry is deep enough and its bound settles (F4).
- **Fit:** medium-good; the 8-thread pass points at a shared-TT benefit, and Lazy SMP is next; form (a) has no
  constant.
- **Cheapest test:** form (a) first: one design R STC SPRT with the pressure-matched Hash, then LTC. *Decision:*
  adopt form (a) or drop. *Cost:* one STC SPRT, one LTC SPRT on a pass.
- **Sources:** PR/commit only.

### RI-28. An exact result may replace a lower-bound entry even when its score is lower [G3-9]
- **Engines (1):** Halogen (#593, 2025-04-24).
- **Reported gain:** +3.29 ± 2.28 at 8+0.08, [0, 3], 25,990 games; +1.54 ± 1.56 at 5+0.05 with 8 threads, 50,438
  games, unresolved (LLR 1.87). **Evidence:** SPRT at STC.
- **Why not spread:** replacement rules are engine-specific; small.
- **Fork:** never tried in this form. Related: ideas.md 33 (a shallow exact result replacing a deeper entry,
  measure first); `tt_keep_exact` off.
- **Fit:** medium; no constant; needs the pressure-matched Hash, which Fork has.
- **Cheapest test:** a FORK_SEARCH_STATS count of how often the case arises (idea 33's method); an SPRT only if it is
  frequent. *Decision:* whether the case is common enough to test. *Cost:* CPU minutes.
- **Sources:** PR/commit only.

### RI-29. TT replacement that penalises entries whose inexact bound disagrees with the current window [G1-11]
- **What:** entries whose inexact score disagrees with the current window lose priority in replacement (described
  as a refinement of secondary ageing).
- **Engines (1):** Stockfish (319d61ef, 2026-05-19; it came out of issue #6742, RI-41).
- **Reported gain:** +0.71 / +1.73 (derived); a VVLTC test of reverting it failed to gain. **Evidence:** SPRT at
  STC and LTC, plus a VVLTC revert test.
- **Why not spread:** recent; one engine.
- **Fork:** never tried (Fork's replacement favours current-search entries, F5).
- **Fit:** medium; pairs with RI-41's mate suites, which would show whether Fork has the failure it fixed.
- **Cheapest test:** RI-41's suite first; if Fork reproduces the failure, one design R STC SPRT with the
  pressure-matched Hash. *Decision:* whether Fork's replacement needs the rule. *Cost:* CPU minutes, then one SPRT.
- **Sources:** commit text plus issue #6742's thread.

### RI-30. Graph-history-interaction (GHI) mitigation for transpositions [G1-20]
- **Engines (2):** Reckless (gain on a fortress book); Alexandria (counter-evidence, merged anyway).
- **Reported gain:** Reckless +9.74 ± 4.05 on fortress openings, [0, 4], 3,496 games, then non-regression on normal
  openings ([-4, 0]). Alexandria -4.15 ± 3.40 at STC (H0), -0.10 at LTC and -0.81 at 60+0.6, all [0, 3] (#543).
  **Evidence:** SPRT on a special book; counter-evidence on normal books.
- **Why not spread:** neutral or negative on normal books.
- **Fork:** never tried.
- **Fit:** medium (TCEC fortresses); test only on a fortress or endgame book.
- **Cheapest test:** after RI-26, a non-regression SPRT on a fortress book. *Decision:* a correctness rule. *Cost:*
  one SPRT.
- **Sources:** PR/commit only.

## E. Correction (drift) tables

### RI-31. Correction update toward the mean of the raw and the corrected static eval [G4-M1, G4-R3]
- **What:** the correction table's update target is the average of the raw and the corrected static evaluation,
  not one of them.
- **Engines (2):** Motor (#178, credited as Renegade's idea), Renegade (#74). The authors collaborate.
- **Reported gain:** Motor +7.91 ± 3.82 at 10+0.1, [0, 3], 8,394 games (updating toward the corrected eval alone was
  neutral: +0.89 STC, +0.34 LTC; "allow bigger correction" +1.87 ± 1.50). Renegade +3.63 ± 2.54, [0, 3.5], 18,744
  games, bundled with a larger correction cap ("both ideas were neutral on their own"). **Evidence:** SPRT at STC,
  two engines.
- **Why not spread:** published only in two PRs.
- **Fork:** never tried (E5's family never tried); the base exists: the minor drift table, adopted 2026-11-12.
- **Fit:** good; the mean is a natural value; no nps cost.
- **Cheapest test:** one design R STC SPRT on the adopted drift table. *Decision:* Fork's drift-table update rule.
  *Cost:* one SPRT.
- **Sources:** PR/commit only.

### RI-32. Correction keys split by material band, or bucketed by the halfmove clock [G1-05]
- **What:** pawn and minor-piece correction keys mixed with a material band, so each structure is corrected per
  game phase; or correction history bucketed by the halfmove clock.
- **Engines (2):** Triumviratus (material band), Reckless (halfmove clock).
- **Reported gain:** Reckless +1.27 ± 1.00 / +2.30 ± 1.68, SPRT. Triumviratus +3.2 ± 3.8 over 8,634 games at 12+0.12
  (-5.1 ± 8.1 before a prefetch fix); a diagnostic showed slightly more eval error removed, from light endgames;
  corrections per fifty-move band +1.25 ± 2.87 (off), faded with the fifty-move counter -2.7 ± 4.3 (off).
  **Evidence:** SPRT at STC and LTC (Reckless); fixed games, interval across zero (Triumviratus).
- **Why not spread:** small; table-size cost.
- **Fork:** never tried; Fork has the minor drift table.
- **Fit:** medium; the halfmove form speaks to TCEC's long endgames.
- **Cheapest test:** one design R STC SPRT per form, the halfmove form first (it has the SPRT). *Decision:* a key
  refinement. *Cost:* one or two SPRTs.
- **Sources:** PR text plus Triumviratus's NOVELTIES.md.

### RI-33. Correction keyed by a hash of the network's hidden state [G4-S1]
- **What:** a correction table indexed by a locality-sensitive hash of the hidden activations ("what the net
  itself thinks is similar") instead of by pawns or pieces.
- **Engines (1):** Seer (listed as a novelty in its TCEC questionnaire).
- **Reported gain:** the PR titled "nn-eval-correction-history" (#185): STC 8+0.08 +3.08 ± 2.85, [0, 3], 28,020
  games; LTC 40+0.4 +3.93 ± 3.47, [0, 3], 18,664 games. That this PR is the hidden-layer hash is inferred from its
  title (UNVERIFIED). Merged 2024-01-04, **after** the rated 2.8.0 (2023-12-31). **Evidence:** SPRT at STC and LTC,
  mapping UNVERIFIED.
- **Why not spread:** needs cheap access to hidden activations; modest gain; published only as a questionnaire line
  and a PR title.
- **Fork:** never tried.
- **Fit:** good in spirit: a key from the signs of a few fixed random projections of the 512-wide accumulator adds a
  little arithmetic per evaluation and no accumulator rows (nps cost UNVERIFIED until measured); close to the
  calibrated residual line's idea of letting the net's own state rank errors.
- **Cheapest test:** a passive ranking like R34's: the drift table's error reduction on held-out positions with this
  key against the existing keys; one design R STC SPRT only if it ranks well. *Decision:* whether a further
  drift-table key is worth an engine change. *Cost:* offline CPU minutes plus a small tool, then one SPRT.
- **Sources:** TCEC questionnaire (concept) plus a PR squash message (figures).

## F. Lazy SMP

See smp.md for how these fit together and with the KB entry docs/kb/lazy-smp.md (branch kb).

### RI-34. Lazy SMP hygiene: barrier start and stop, no TT or score writes from aborted helper searches [G2-3]
- **What:** threads start and stop at a barrier; a helper told to stop stores nothing of its unfinished search;
  the score of an interrupted search is not reported or used for voting.
- **Engines (2):** Tarnished (#136, "inspired by Clockwork", also dropping thread voting as a non-regression at 2
  threads); RubiChess (#528, wrong upper-bound scores after an interrupted multi-thread search; #516, wrong
  voting; after its rated version). Clockwork is outside the top 50.
- **Reported gain:** Tarnished +14.48 ± 5.19 at 2 threads and +20.08 ± 6.03 at 4 threads, 8+0.08, [0, 3], against
  its own earlier SMP (partly a bug fix). RubiChess: no figure. **Evidence:** SPRT (bundle); title only.
- **Why not spread:** treated as a bug fix, rarely measured.
- **Fork:** not applicable yet (one thread). **Already written into the KB entry's suggested v1** (lazy-smp.md §3.4
  "Never store an aborted search's result", §3.1 lifecycle, §6.3 items 9 and 10).
- **Fit:** direct. Fork's root already treats unfinished results carefully (rv-failhigh: playing an unresolved
  fail high lost -14.6).
- **Cheapest test:** none as an Elo test: two rules in the 17a spec, each with a unit test (no store after the stop
  flag; barrier start and stop); the first 2-against-1-thread SPRT measures the whole. *Decision:* Lazy SMP's
  design. *Cost:* about zero.
- **Sources:** PR/commit only (the same PR is also in the KB entry).

### RI-35. Thread diversity: per-thread search offsets and helper reduction bias [G1-04, G4-P1]
- **What:** helper threads search slightly differently from the main thread: later threads reduce slightly less,
  the first aspiration window widens with the thread number, odd-numbered threads reduce the null move a little
  less (Stockfish); small random reduction noise or a small deterministic per-helper bias (Reckless); a bias in
  LMR and non-PV search for helpers "to look at a wider variety of variants", off at one thread (Potential,
  credited to 87flowers).
- **Engines (3):** Stockfish (39c077f1, 8ecfc3c8, 61c68717), Reckless, Potential. Possible: Clover (#401, "more
  aspiration windows for some threads", title only).
- **Reported gain:** Stockfish SMP STC +0.70 and SMP LTC +2.04 ([0, 2] then [0.5, 2.5]); +1.31 / +1.31; +0.79 / +0.91
  (2026-10-28). Reckless reduction noise: 1 thread non-regression (-0.10 ± 1.03, [-2.75, 0.25]), 8 threads at
  5+0.05 +3.19 ± 2.37, [0, 4]; a deterministic bias +1.96 ± 1.58 (TC not stated: UNVERIFIED); a much larger bias
  failed. Potential: 1 thread at 8+0.08 -4.22 ± 5.57 (stopped); 8 threads at 5+0.05 +9.13 ± 6.36, [0, 7.5], 4,188
  games (hand-crafted era). **Evidence:** SMP SPRTs in three engines.
- **Why not spread:** matters only with threads; most engines rarely test SMP.
- **Fork:** never tried; Lazy SMP not built. The concept is on the Phase 6 roadmap (DESIGN.md "(h) thread agreement
  and diversity"; KB T54); idea 84 (evaluator-diverse Lazy SMP) is a different form. The KB's suggested v1 has no
  depth offsets or skip rules (lazy-smp.md §6.3 item 3), leaving them to separate SPRTs.
- **Fit:** high: Lazy SMP is next; TCEC runs hundreds of threads; zero cost at one thread, so Fork's 1-thread tests
  stay valid.
- **Cheapest test:** once 17a lands, the first diversity SPRT: helpers identical against helpers with a small
  per-thread reduction offset, at 4 to 8 threads, plus a 1-thread non-regression. *Decision:* whether Fork's Lazy
  SMP needs explicit diversity. *Cost:* one SMP SPRT pair (runner time grows with threads).
- **Sources:** PR/commit only.

### RI-36. Majority thread vote for the soft stop [G1-12]
- **What:** the soft time limit is taken only when a majority of threads agree, rather than on the main thread's
  view alone.
- **Engines (1):** Reckless.
- **Reported gain:** 8 threads at 25+0.25 +4.48 ± 2.94, [0, 4]; 8 threads at 5+0.05 unfinished (+1.21, LLR 0.67);
  16 threads at 5+0.05 +2.59 ± 2.02. **Evidence:** SMP SPRT.
- **Why not spread:** one engine; SMP-only.
- **Fork:** never tried (Phase 6).
- **Fit:** high for TCEC's thread counts; a time-management parameter (decision 4: not in SPSA).
- **Cheapest test:** after 17a and the first time-management work under threads, one SMP SPRT at 8 threads.
  *Decision:* the soft-stop rule under SMP. *Cost:* one SMP SPRT.
- **Sources:** PR/commit only.

### RI-37. SMP-only TT store of intermediate search results [G1-18]
- **Engines (1):** Reckless. Also its "highest-depth thread drives optimism" (+1.95, +2.44, then +7.64 ± 4.03 at
  25+0.25, 8 threads), which has no fit: Fork has no optimism (F11 stopped by the owner).
- **Reported gain:** 1 thread H0 (-3.61 ± 3.36); 8 threads +3.99 ± 2.78, [0, 4]. **Evidence:** SMP SPRT, with a
  1-thread loss.
- **Why not spread:** loses at one thread.
- **Fork:** never tried; related to F3 (early eval-only TT write, never tried), whose peers' gains grow with threads
  (evidence.md, F3).
- **Fit:** medium; SMP-only by construction.
- **Cheapest test:** with F3, after 17a: one 8-thread SPRT with a 1-thread non-regression. *Decision:* an SMP-only
  TT policy. *Cost:* one SMP SPRT pair.
- **Sources:** PR/commit only.

### RI-38. Table sizes scaled with the thread count [G4-P2]
- **What:** correction tables and pawn history grow with the number of threads.
- **Engines (1):** Potential (hand-crafted era).
- **Reported gain:** correction tables: 4 threads at 5+0.05 -5.32 ± 11.03 (stopped at 1,568 games); 8 threads at
  20+0.2 +11.73 ± 7.11, 2,666 games (#557). Pawn history: 8 threads at 5+0.05 -0.41 ± 8.00 (stopped); 8 threads
  at 20+0.2 +8.96 ± 5.99, 3,606 games (#568). Both [0, 7.5]. **Evidence:** SMP SPRT, gains only at the longer TC,
  wide bounds, weak engine.
- **Why not spread:** long TC and threads only; tables were small elsewhere.
- **Fork:** never tried; the drift tables exist; Fork has no pawn history (D7 queued).
- **Fit:** high for TCEC conditions (long TC, many threads); depends on whether the tables are shared (G2).
- **Cheapest test:** a Phase 6 multi-thread SPRT at the longer TC only. *Decision:* table sizing in Phase 6.
  *Cost:* one 8-thread SPRT.
- **Sources:** PR/commit only.

## G. Network and training

### RI-39. Output-bucket factoriser in training [G4-I1]
- **What:** in training, a shared output layer is added to each material bucket's own output layer; after training
  it is merged into the buckets, so inference cost does not change.
- **Engines (1):** Incipit (the network survey's group-b record lists the result; matrix.md and shortlist.md do not
  carry it, hence listed here).
- **Reported gain:** STC [0, 2]: H1 +9.4 over 10,266 games (LLR 2.97); the same data without it H0 at -0.8; at a
  quarter of the training length the factoriser gave only +0.8. Incipit's STC is not stated (UNVERIFIED).
  **Evidence:** SPRT at STC.
- **Why not spread:** new (2026-11); invisible at short training, so short screens miss it.
- **Fork:** never tried. Fork factorises inputs (the H-512 family) but not its 8 phase heads. Idea 183 (knot-tied
  heads) is a later, different refinement; idea 187 (routed heads) was killed at its step-0 gate.
- **Fit:** ideal for the cost lesson: speed ratio 1.00, so any fixed-node gain is net Elo; no new inputs, so the
  residual line does not apply. Each of Fork's 8 heads already sees ample data, so the gain may be smaller; the
  long-training-only behaviour argues for a full-length arm.
- **Cheapest test:** one retrain arm at the full schedule (trainer: shared head plus per-phase delta, merged at
  export; engine unchanged), then the fixed-node screen and an STC SPRT. *Decision:* whether every future retrain
  trains factorised heads. *Cost:* one training arm plus one STC slot.
- **Sources:** PR/commit only (Incipit commit messages).

### RI-40. Training labels shrunk toward a draw for material combinations that often end drawn [G3-12]
- **Engines (1):** Velvet (903316b, 2024-03-14; shipped in 7.2.0).
- **Reported gain:** 7.2.0 (a bigger net, search changes and this) "estimated ~20 Elo" in total. **Evidence:**
  release (bundled).
- **Why not spread:** the gain cannot be separated; needs per-signature draw statistics.
- **Fork:** never tried. Related: R33's structure-class scale (queued, step 17), idea 180 (depth-extrapolated class
  calibration), F10 (eval-side material scaling, dropped by the owner on 2026-11-15).
- **Fit:** low-medium; Fork-pure (its own games), but a training arm on a weak prior.
- **Cheapest test:** offline: draw rate by material signature in Fork's self-play against the label means; only a
  large mismatch would justify an arm. *Decision:* whether to open an arm. *Cost:* CPU minutes.
- **Sources:** commit text plus release notes.

## H. Testing, tuning and practice

### RI-41. Elementary-mate regression suites [G1-03]
- **What:** after Stockfish took far too long to mate in KRvK, KRvKP and KBNvK at TCEC season 29 with about 500
  threads, its maintainers reproduced a loss of found mates at high node counts on one thread, traced it to a TT
  ageing change and fixed it (RI-29); they then proposed tracking elementary-mate suites (KRvK, KBNvK, KBBvK,
  KQvKR, KNNPvK) in the mate-tracking CI. One comment suggests probing WDL tables only at the root and says
  Stormphrax does this (second-hand, UNVERIFIED).
- **Engines (1):** Stockfish (issue #6742, 2026-04-18 to 05).
- **Reported gain:** a documented TCEC failure and its fix; no Elo. **Evidence:** anecdote (issue thread).
- **Why not spread:** most engines never see TCEC-scale node counts.
- **Fork:** idea 22 (mate-aware LMP and LMR) is open and uses a mate suite; DESIGN.md runs matetrack mates as a
  diagnostic; no elementary-endgame suite at high node counts is run on TT or tablebase changes.
- **Fit:** high for TCEC (long TC, many threads, 7-man tables).
- **Cheapest test:** Fork at fixed nodes on KRvK and KBNvK starts generated by Fork's own tooling and verified with
  Syzygy (not copied from Stockfish's suites), with and without tables in search, before and after any TT or TB
  change. *Decision:* whether Fork's TT ageing or WDL probing reproduces the failure (and whether idea 22 or RI-29 is
  needed). *Cost:* local CPU minutes; no SPRT.
- **Sources:** an issue thread and a commit message.

### RI-42. Elo by game length in release gauntlets [G3-10]
- **What:** a release's gauntlet result split by how many moves the won games lasted, to see whether a change helped
  middlegames or long endgames (Velvet 7.0.0's largest gains were in games won after 60 to 120 moves).
- **Engines (1):** Velvet (release notes 5.2.0, 6.0.0, 7.0.0, 7.1.0).
- **Evidence:** anecdote (a diagnostic, no SPRT).
- **Why not spread:** most developers use SPRT only.
- **Fork:** never tried; the closest is idea 172's UHO diagnostics by class.
- **Fit:** high as tooling; zero engine cost; Fork's SPRT shard PGNs exist; it speaks to the open conversion question
  (idea 172's 0-of-200 UHO conversions).
- **Cheapest test:** an offline script over existing SPRT PGNs (net candidate against base): score by game-length
  bands with error bars. *Decision:* whether a net arm's gain or loss sits in long games, which would route it to the
  endgame or conversion work rather than to search. *Cost:* CPU minutes, no games.
- **Sources:** release notes.

### RI-43. Hardware-sensitivity checks: A/A runs and per-machine splits [G1-16]
- **What:** an A/A test (the same binary on both sides) on each machine type, and results split by machine for
  memory-heavy features. In Triumviratus, a passed-pawn graft won on a four-memory-channel socket and lost on a
  two-channel one; the author concluded a feature whose value depends on memory bandwidth is a poor release
  candidate.
- **Engines (1):** Triumviratus.
- **Evidence:** anecdote.
- **Fork:** not done; GitHub runners vary.
- **Fit:** medium; Fork's SPRT shards run on mixed runners, and TCEC's machine differs from all of them.
- **Cheapest test:** split an existing memory-heavy SPRT's shards by runner CPU (if the ledger records it:
  UNVERIFIED). *Decision:* whether runner type must be balanced or recorded. *Cost:* CPU minutes.
- **Sources:** project document (DEVELOPMENT_8.0.md).

### RI-44. SPSA from a deliberately biased start [G1-17]
- **What:** a large SPSA started from deliberately aggressive values (wider pruning, higher depth caps) converged to
  a different basin (bench nodes fell by about two thirds).
- **Engines (1):** Coda (PR #1; Coda is written with Claude Code).
- **Reported gain:** +12.3 at [0, 5] after 3,132 games, on top of a normal retune's +7.2. TC not stated
  (UNVERIFIED). **Evidence:** SPRT.
- **Why not spread:** one engine, one test.
- **Fork:** never tried (ideas 150-151 are other tuners).
- **Fit:** medium-good for the final retune.
- **Cheapest test:** a second final-retune SPSA started from a biased point, compared with the normal one by one
  SPRT. *Decision:* whether the final retune runs from two starts. *Cost:* one extra SPSA run plus one SPRT.
- **Sources:** PR/commit only.

### RI-45. Bayesian optimisation of a group of constants [G1-19, G3-11]
- **What:** a few search constants tuned with a Bayesian optimiser (Ethereal: a tree-based surrogate) instead of
  SPSA.
- **Engines (2):** Ethereal (0b605f2, 2020-06-17; presence in 14.25 UNVERIFIED), Reckless (null-move constants).
- **Reported gain:** Ethereal +3.62 ± 2.73 at 12+0.12 (21,952 games), +3.26 ± 2.33 at 60+0.6 (21,712), [0, 4].
  Reckless +2.60 STC; LTC +2.77, merged at LLR 2.38 of 2.89. **Evidence:** SPRT at STC and LTC (Ethereal); STC pass
  and LTC near-pass (Reckless).
- **Why not spread:** SPSA is cheaper per parameter and became the OpenBench standard.
- **Fork:** never tried. Fork's SPSA works (R14: +37.93 STC, +29.93 LTC); ideas.md 151 plans CLOP-style local fitting
  for 1-3 parameter questions.
- **Fit:** low; overlaps idea 151.
- **Cheapest test:** none now; if idea 151 runs, a Bayesian surrogate as a second arm on the same known-answer
  question.
- **Sources:** PR/commit only.

---

## Also found, not ranked

Single-engine results that are small, title-only, mechanism-unknown or likely bug fixes. Listed so the owner can
see them; none is ranked.

| Item | Engine and figure | Why not ranked |
|---|---|---|
| Stop once mate in 1 or 2 (or mated in 1) is found, with time management on | Stockfish 7b370328 (after CCC time losses); no Elo | a cheap extension of Fork's forced-move stop; a unit test, owner's call |
| Exponential root-score average weighted by effort; discovered and double checks raised in capture ordering; larger futility value when capturing the last-moved piece; history scaled by statscore; smaller malus for late quiets; "adaptive beta cut"; "risk tolerance" (removed later) | Stockfish, about +1 each (derived) | small; the last two have no described mechanism (UNVERIFIED) |
| Extension margins smaller on a repeat PV; TT depth in LMR; discard the TT move when a potentially better move exists; NMP margin by confidence in the estimate; null-move history adjusting the NMP margin; less time on recaptures (later removed at non-regression); less time late in long games; "increase reduction based on correct expectation" (mechanism UNVERIFIED) | Reckless: +3.39 / +1.70; +2.20 / +1.80; +2.16 / +2.62; +2.91 / +1.54; +1.96 STC; +4.48 / +4.91; non-reg; +3.08 / +4.13 | one engine; mostly small or doubtful |
| BCH-code Zobrist keys | Reckless +2.66 at Hash 2 MB, +1.96 at 8 MB | a hash-pressure item of small size; Fork stores more check bits than the key-width item concerns (DESIGN.md, the Phase 3 TT layout) |
| History update as a listwise ranker (softmax gradient) | Triumviratus, non-regression only (11,166 games) | too weak |
| Quiescence TT entries' stored depth | Triumviratus +3.38 ± 2.58 (20,162 games at 10+0.1); Obsidian in-check qsearch entries +0.81 ± 0.87 | an implementation detail; Fork stores depths below 0 as 0 (group 2 read trans_table.hpp), so the wrap bug class (Lizard #35, Caissa 1.23) does not apply |
| Buffered output and a high-resolution clock | Triumviratus +29.8 ± 7.4 at 5+0.05 with an identical tree, from a coarse Windows clock and unbuffered output | a check item: Fork writes each UCI line with one flush under a mutex, and TCEC is Linux |
| Malus to the prior move on a TT cutoff; in-check qsearch store depth; TT cutoffs on a fail high only from deeper entries | Obsidian +1.55 at 10+0.1; +0.81; +2.00 at 60+0.6 | small |
| More reduction when an earlier PV visit of the same position failed low | PlentyChess +1.03 STC | small |
| Data from "more positions, from better and worse nets" | PlentyChess +32.90 ± 10.14 at 8+0.08 (LLR 2.21) | confounded with more data (UNVERIFIED how much is the mixing) |
| No NMP when the opponent has an easy capture | Berserk STC +4.13 ([0, 2]), LTC +0.55 unfinished; Triumviratus -0.34 ± 4.04 | mixed; merged "good for testing and datagen" |
| Quiet checks generated at qsearch's first plies | Berserk +5.39 / +7.36 at 8+0.08 / 40+0.4 (2023) | widespread in older engines; Triumviratus found endgame quiet checks neutral; Fork removed qsearch checks (Phase 3); a possible LTC item |
| No history update for a "trivial" best move | Berserk +2.05 / +8.11 | "trivial" undefined (UNVERIFIED); see D15 in evidence.md |
| Recapture guard on quiescence futility | Integral +1.20 ± 0.98 at 10+0.1, [0, 2.5] | a refinement of B17, which failed for Fork |
| More move-loop pruning in TT-PV nodes | Stormphrax #298 +3.14 ± 2.20 / +3.11 ± 2.16, [0, 3] | the condition is not in prose (UNVERIFIED) |
| Less time in decisive positions | Stormphrax #315 -0.25 ± 3.64 on [-5, 0], unresolved | no gain |
| Bigger bonus when the TT move changed; extra bonus at cut nodes; the singular search's score in LMR | Hobbes +3.14 ± 2.52 [0, 4]; +2.08 ± 1.76; +2.44 ± 1.95 (STC) | one engine, STC only, small |
| Larger futility margin when the static eval is at or above beta | Hobbes #447 +2.96 ± 2.11 STC, LTC +1.12 ± 1.99 unresolved | LTC unresolved |
| Corrections also updated inside the singular search | Raphael #119 +3.39 ± 2.55 STC, [0, 5] | one engine, STC |
| "Store native depth in TT" | RubiChess #474 +3.20 ± 2.99 at 10+0.1, +8.36 ± 5.45 at 60+0.6 | meaning UNVERIFIED |
| Seeding the aspiration running average with the first iteration | Caissa 1.26: neutral at STC, "+38 Elo in fixed low-node searches" | only at tiny node counts |
| Correction size in time management | PlentyChess (credited to Tarnished's author) +1.47 STC, LTC +0.93 at LLR 1.01 | weak; A4 family |
| An eval cache carved from the hash; second-degree follow-up history; continuation correction keyed by hash differences; a capped moves-left prediction in time management | Cinder: non-reg; non-reg; non-reg; +7.48 ± 3.62 at 4+0.04 (engines.md) | non-regression only, or known |
| Internal iterative deepening; "SMP TM"; "reduce more in exact nodes"; qsearch returns the static eval when every move was a bad capture | Icarus +3.82 / +3.83 ([0, 4]); +22.66 at 2 threads; +3.61 ([0, 4]); +11.24 / +7.04 ([0, 5]) | likely young-engine fixes or mechanisms UNVERIFIED |
| Reduce more at PV nodes when the TT move is "old" compared with alpha | Potential #436 STC H0 -0.06, LTC +3.30 ± 2.65 | mechanism UNVERIFIED |
| "Material structure history" in ordering | Motor #145 +2.22 ± 1.71, [0, 3] | what it indexes is UNVERIFIED |
| Larger history steps when an entry's pawn structure changed | Renegade #61 +3.73, then simplified to "always the larger step" (non-reg) | the pawn condition did not matter |
| Futility setting the best score to the mean of alpha and the best score so far | Renegade #88 +3.65 ± 2.41 | B3 family (evidence.md) |
| LMR by the child's static eval | Incipit (an offline "selectivity census" and a lower branching factor; no Elo) | no Elo published (UNVERIFIED) |
| Feature-transformer weights shared across processes; one shared huge-page net per host | Incipit +2.3 (47,462 games), +3.0 | a test-environment effect (many engine processes per host), not engine strength |
| Igel "adaptive LMR"; Quanticade "use static eval when checking if we can use the TT score", "Yellow Armageddon", "average before storing to TT and corrhist", "bigger history updates if we failed low"; JustBot "scale soft time bound based on number of moves", "average LMR correction", "apply history updates at the end of search"; Titan "use more board info to key correction history" | figures in group 3 §6 | title-only, meaning UNVERIFIED |

## Rare ideas without a published figure (not ranked)

| Idea | Engine (source) | Note for Fork |
|---|---|---|
| Per-move node counts for positions near the root, kept across iterations, used for ordering | Caissa (README "Node Caching") | idea 18 (root moves by previous-iteration node counts) is the root-only form, untested |
| Independent players in data generation: each side keeps its own TT and history in a self-play game | Viridithas #337, Clover #372 (no figures); Raphael's different form (no sharing between games) +5.78 ± 5.85 at fixed nodes on [-5, 0] | Fork shares one searcher between both sides within a game (cleared per game). Offline check: label agreement of split against shared state on a few thousand positions |
| More aspiration windows for some helper threads | Clover #401 (title) | a Lazy SMP diversity option (RI-35) |
| "Sharpen" the normalised eval with a mild power transform | Stormphrax #264 (no test) | Fork's UHO diagnostic found a two-sided misjudgment, which a symmetric transform fits only half of; not recommended without an offline check on uho_diag's sets |
| Never-active pawn input slots (first and last rank) reused for global features (bishop pair, opposite-coloured bishops, locked pawns, passed pawns by file) | Viridithas notes/IDEAS.txt (untested idea list) | a rarely changing feature changes rows rarely, so by the cost lesson it is almost free; whether Fork's map keeps those dead rows is UNVERIFIED; a candidate family for idea 186's residual pass |
| Evaluation scaling switched off during data generation | Integral #174 (no figure) | moot after F10 was dropped |
| Data generation from material-imbalance starts | Coda README | no figure |
| Contempt built on a WDL head; a time bonus for the first move out of book (meaning inferred from option names, UNVERIFIED); deblunder rescoring and "action replay" | Lc0 (blog, TCEC configuration) | idea 8 (Phase 7); "never in Phase 4" (phase-c-synthesis §4.1); Fork has no WDL head (J19 plan). The book-exit bonus costs nothing in nps and an STC SPRT would measure it, but its TCEC value is unknown |
| A hand-made piece-square evaluation beyond an absolute score threshold | rofChade (questionnaire) | low fit; Fork's accumulator is incremental anyway |
| Incremental network updates per side and per full move; a score transform before training and back after evaluation | Ginkgo (TCEC questionnaire) | no measured gain |
| Output buckets by material and king bucket | SSSimpler (commit, no figure) | effectively tried: idea 187 (routed heads) killed at its step-0 gate |
| TT ageing by move count; pinned-piece buckets in threat inputs; an optimiser that gates steps by a reliability estimate | Bread, Jackal, Soul (questionnaires) | no gain, or not adopted |
| Surprise-weighted replay sampling; a volatility auxiliary head | DeepFin (questionnaire) | no figure; private code; OFF-LIMITS data |
