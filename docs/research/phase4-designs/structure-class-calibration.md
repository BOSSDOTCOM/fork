# Structure-class calibration (R33): design, not adopted

Status: **design for the owner's review, 2026-11-09; two decisions taken
the same evening (below). Nothing is queued or built.** §5.6 order step 17: "The structure-class calibration scale
(R33: fitted on SPRT games, adopted on fresh games)", after 8a (done).

Sources read: DESIGN.md §5.6 (order step 17; ideas 10 and 11 replaced) and
the decisions log (2026-11-07 decisions 4, 16, 20; 2026-11-09 testing
policy); docs/research/phase4-think-tank/phase-c-synthesis.md R33 and
phase-b-specialists.md C §0 (E1, E2, E3, E6) and C3, with B13's verdict;
docs/ideas.md (ideas 10, 11, 50, 53); ~/fork-data/sprt/ (the stored SPRT
folders, listed, not opened game by game).

**The owner's decisions (2026-11-09, about 8 PM EST):** "Idea 53's 2e-5
stop-loss and calibration's 30% offline kill become diagnostic only." and
"Calibration uses design R". So: **step 1's 30% cut of the held-out
category residual is reported, never a gate** (the fit and its
cross-validation always go on to step 2; a cut under 30% is reported to the
owner beside the fitted scales), and **the STC SPRT (step 4) and the LTC
SPRT (step 5) are design R** (`--kind search`: [0, 6] nElo, alpha 0.05,
beta 0.20, cap 8 STC stages / 4-6 LTC stages, the futility look after 2
STC stages), not the network kind. §6 is amended accordingly.

## 1. What "structure-class calibration" refers to

**The records point to one thing:** R33, the think tank's "structure-class
calibration scale on the eval" (C3, verdict B13 PLAUSIBLE): a cached scale
`s[k]` multiplying the network's output for a small structure-and-material
class `k`, fitted so that each class's outcome curve matches the middlegame
curve. The order's step 17 names it, decision 20 replaced ideas 10 and 11 with
it ("replaced by R33 and R32"; ideas.md idea 10's status), and decision 16
governs its data: "**Calibration constants may be fitted on SPRT test games**
(R33) only if the constant's adoption test then uses fresh games."

Readings considered and rejected, so the owner can see them:
- idea 50's conformal calibration of pruning margins (a different object:
  margins, not the eval; "calibration set" in ideas.md 50);
- the think tank's M4 (one eval-margin scale factor by error matching at
  each promotion): global, not per structure class;
- idea 53 (structure-class output experts): a network change, listed by the
  owner separately (idea53-structure-experts.md).

**Ambiguities that remain (flagged for the owner):**
1. **Who fits on what.** Decision 16 permits fitting on SPRT test games; C3
   also offered a dedicated local run (4,000 games at 300,000 nodes per
   move, about 1.3 hours of the 10-thread machine). This design uses SPRT
   games (decision 16) and keeps the local run as the fallback.
2. **The reference curve.** C3 says "match the pooled middlegame curve
   (E1's mid row)". An alternative is one global curve over all phases. This
   design follows C3; the global variant is computed as a diagnostic.
3. **Is `s[k]` "the eval scale"?** Decision 4 keeps the eval scale out of
   SPSA. `s[k]` is fitted offline by maximum likelihood, never by SPSA, and is
   per class, not the global training scale S, so decision 4 does not forbid
   it; the owner confirms the reading.
4. **Refits.** `s` depends on the network (C3: "refit per promoted net").
   Whether each refit needs its own adoption test is not in the records
   (§6 proposes one).

## 2. The classes (C3's key, with Fork's own precise definitions)

C3's key: phase bucket (3) x pawn-count bucket (3) x all pawns on one wing
(2) x pure opposite-coloured bishops (2) x rook-only ending (2): at most 72
cells, most empty, shrunk toward 1.0. Definitions (the leader's view is not
needed: every feature is colour-symmetric):

| feature | definition | source of the edges |
|---|---|---|
| phase | non-pawn material with N, B 3, R 5, Q 9 summed over both sides: >= 44 "open", 20-43 "mid", < 20 "end" | C §0.1 (the think tank's own categories) |
| pawns | total pawns: <= 4, 5-8, >= 9 | C3 |
| one wing | at least one pawn, and every pawn of both sides on files a-d, or every pawn on files e-h | C3 names the class; the a-d / e-h split is a **placeholder** (C's feat.py is not in the repository, so its exact definition is UNVERIFIED) |
| pure OCB | each side has exactly one bishop, on opposite square colours, and no knight, rook or queen | C §0.3 ("opposite bishops, nothing else") |
| rook-only | each side has exactly one rook and no other piece but pawns | C §0.3 ("rook ending (one rook each)") |

The class function is shared with idea 53's (one implementation of the
pawn-structure primitives, tested once).

Cost: a few popcounts on the piece and pawn bitboards and two square-colour
masks, about 10-20 instructions per evaluation, cacheable in the position's
per-ply state (changes only on captures, promotions and pawn moves). C3:
"expected < 0.3% nps (UNVERIFIED; bench/ab.py) → < 0.5 Elo" at the price of the
time; at the current 1.72 Elo per 1% the same 0.3% is about 0.5 Elo.

## 3. Data

Fork's own STC games with the **current default network on both sides, or on
the side whose evals are used**. Candidates on disk (~/fork-data/sprt/,
folder names; game counts from the SPRT log or the local driver logs; each
run's network is to be read from its shard meta before use, UNVERIFIED
here):

| folder | games | networks | note |
|---|---|---|---|
| s512ppr3-stc | 8,000 | S512ppr3 vs S512ppr2 | only S512ppr3's evals usable |
| tm-r8-stc | 3,200 | S512ppr3 | time management on/off |
| tm-r8-ltc | 4,992 | S512ppr3 | LTC 40+0.4: an LTC fit and check |
| idea60-stc, idea61-stc | 3,200 each (2 stages; sprt-log) | S512ppr3 | |
| spsa-r14-m2-stc | 1,600 | S512ppr3 | tuned margins vs default |
| ltc-se-on-vs-off, ltc-mc-on-vs-off | running | S512ppr3 | LTC |
| the SPSA run spsa-r14-m2 | 20,800 | S512ppr3, perturbed margins | whether its artifacts keep PGNs with evals is UNVERIFIED |

So about 15,000-20,000 STC games of the default, against C's 4,618-game
STC-ppr2 set, which already gave z of 5-6 for the main cells (C §0.3). If a
new network is promoted before step 17 runs, the fit uses that network's games
(its promotion SPRT gives half a set; the next SPRTs the rest).

Position selection (C §0.1, Fork's rule): every second position of a game
after the book exit, with the searched evaluation that the moving engine
printed for it (fastchess PGN comments, `{+0.27/15 ...}`); folded to the
leader's view (the side the eval favours); kept when the eval lies in
[50, 300) cp; excluded: mate scores and tablebase-scored evals (the
`is_tb_or_mate` band of src/search/score_bounds.hpp, as printed), and
positions from games without a normal end.
Outcome: the game's score from the leader's view (1, 1/2, 0). Standard errors
clustered by game.

## 4. The fit

1. **Reference:** on the "mid" phase cells, fit `E[y | e] = sigmoid(e / L)`
   by maximum likelihood (Bernoulli cross-entropy with fractional y), one
   parameter L.
2. **Per cell k:** `E[y | e, k] = sigmoid(s_k e / L)`, `s_k` by penalised
   maximum likelihood with a normal prior on `log s_k` centred on 0 (s = 1)
   with standard deviation `tau` (the shrink strength), and `s_k` limited to
   (0, 1.2] (C3). Cells with fewer than `n_min` positions keep s = 1
   (`n_min` a placeholder, set so a cell's SE on `s` is below 0.1).
3. **tau:** two candidate values (C3's "2 shrink strengths"), chosen by
   cross-validated log-likelihood (below), not by an SPRT ladder; the owner
   may ask for a head-to-head instead.
4. **Cross-validation:** split by game into halves A and B (and, as a check,
   by run); fit on A, score on B, and swap. Statistic: the summed squared
   category residual over C's E2 categories (one wing, at most 4 pawns, pure
   OCB, rook ending, and the rest of E2's rows), before and after the scale.
5. **Fixed point:** the engine stores `S_k = round(1024 s_k)` and computes
   `e' = (e * S_k) / 1024` (integer, so search stays deterministic; the 1024
   denominator is a placeholder chosen for resolution, not tuned).

Expected (C3, low confidence): `s` between about 0.6 and 0.85 in the one-wing,
few-pawn and OCB end cells; near 1 elsewhere.

## 5. The engine change

- After the network's output (eval.hpp's `static_eval`, the bare network
  today), before any use: `e' = e * S_k / 1024` behind a switch (C3's
  suggested `UseStructureScale`, name to screen), so the scaled value is what
  the TT stores, what the pruning margins compare and what the search
  returns. Draw scores, mate and tablebase scores are untouched (they are not
  static evals).
- The table `S_k` is data compiled in per network (beside its network file
  and bench reference), refitted at each promotion (§6).
- Bench changes with the switch on (a new signature, tests/bench.ref in the
  same commit if adopted); with the switch off bench is unchanged, checked.
- Tests: the class function against the Python reference on positions of
  every cell; e' = e with all `S_k` = 1024; the switch-off bench identity.

## 6. Testing and the decision rule

The fit uses SPRT games; **every adoption test uses fresh games** (decision
16): its openings start past the highest book line any fit game used
(`--origin`, read from each fit run's design.json and shard meta), so no fit
game's opening reappears.

| step | test | continue if | otherwise |
|---|---|---|---|
| 1 | offline fit and cross-validation (§4), no engine work | always (owner, 2026-11-09: diagnostic only); the held-out summed squared category residual's fall is reported against R33's 30% line (C3 predicted at least 50%) | (no stop here; a fall under 30% is reported to the owner) |
| 2 | nps A/B (bench/ab.py, the class computed and the table at 1024 against the switch off) | under 1% slower | make the class incremental once, else stop |
| 3 | fixed-node screen, speed-adjusted, against the switch off (1 stage, 800,000 nodes; testing rule: an evaluation-side candidate whose speed differs plays it first) | `FN + 118 log2(r) > 0` | stop (a try of idea r33) |
| 4 | STC SPRT, design R ([0, 6], beta 0.2, cap 8, futility after 2), fresh openings | H1 | if H0 or the futility stop with an STC estimate above 0: one fixed 2-stage LTC estimate; if that is at or below +2 nElo, keep it off (C3's "within ±2" kill); if above, the owner decides |
| 5 | LTC SPRT, design R at 40+0.4 (cap 4-6), fresh openings (C3 asks for the LTC-sensitive list: the bias grows with depth, E2) | H1 | not adopted |

Which SPRT kind: R33 changes the evaluation but is a switch-gated engine
feature, so this design uses design R ("search features stay on design R");
the network kind ([0, 5], alpha = beta = 0.05) was the alternative.
**Decided (owner, 2026-11-09): design R.** Step 1's offline gate was R33's
own recorded kill criterion, and this design first kept it as a stop-loss;
**decided (owner, 2026-11-09): diagnostic only**, as the testing rule of
2026-11-09 has it for offline metrics (the same decision as idea 53's
probe).

**Refits:** at each later promotion, `s` is refitted on the new network's
games and rides along with that network's own promotion SPRT (the network is
tested with its refitted table, which is a fresh-games test of the refit).
Owner decision (ambiguity 4).

## 7. Order and interactions

- Step 17 is before the factorial round (18) and the final retune (19): the
  scale changes evaluations in the affected classes, and the eval-gated margins
  should be tuned after it (C3: "run it before item 12, or refit after"; A2
  O4).
- With idea 53: the experts learn the training labels' calibration, and the
  labels show little of the bias (C §0.3: the 20k-node data column's residuals
  are −1.5 to −2.3 against STC's −4.5 to −6), so the two are complementary; if
  idea 53 is adopted, `s` is refitted on its games.
- With the endgame slice (R32, deferred) and the data's result weight
  (R27): both move the labels toward the games' outcomes and would shrink the
  fitted scale's departures from 1; the refit absorbs that.

## 8. Cost

| item | lane | estimate (UNVERIFIED) |
|---|---|---|
| offline fit and CV (Python on stored PGNs) | L | under 1 CPU-hour; 1 day of engineering |
| engine change, tests, Python reference | E | 1-2 days (C3: 2-3 days in all) |
| fixed-node screen | G | 1 stage |
| STC SPRT | G | 2-8 stages |
| LTC SPRT | G | 4-6 LTC stages (16-24 stage-equivalents) |
| total | | about 4-8 STC stages (R33's estimate) plus the LTC test |

Expected value: R33 +1 (0 to +3) (synthesis; C3's model +2.6, range +1 to +5;
E6's null event studies and B13's "STC to LTC growth only about 1 point" argue
for the low end).

## 9. Names and constants for the screens (none screened yet)

Names: `UseStructureScale` (C3's suggestion), the table (e.g.
`StructureScale`), the class function (shared with idea 53), the fit script
(e.g. `tools/nnue/fit_structure_scale.py`; the existing fit_scale.py fits the
training scale S, a different thing). Constants: the eval band [50, 300) cp
and the every-second-position sampling (C §0.1); the phase edges 44 / 20 in
3-3-5-9 units (C §0.1); the pawn edges 4 / 8 and the cap 1.2 (C3); the one-wing
split; `tau` (two candidates, placeholders); `n_min` (placeholder); the
1024 denominator; the 30% line (R33; a diagnostic since 2026-11-09,
owner). The fitted `S_k` values are
Fork's own measurements; C3 asks that the shrink strength go through the
constant screen.

## 10. Prior art (concept level)

Scaling drawish endgames toward zero is long-standing evaluation practice
(CPW's evaluation topics on drawish endgames and opposite-coloured bishops;
exact page names UNVERIFIED, C3). The fit here is a post-hoc per-subgroup
calibration: Platt (1999, "Probabilistic Outputs for Support Vector
Machines"); Zadrozny and Elkan (2002). No engine's scale values are used; `s`
is fitted on Fork's games.

## 11. Unverified items

- C's exact class definitions (scripts not in the repository); the a-d / e-h
  wing split.
- Which stored runs keep PGNs with evaluation comments, and their exact game
  counts (folders listed, not opened).
- The nps cost and the Elo value.
- Whether the SPSA run's artifacts include usable game records.
