# Fork KB: Search Techniques (Phase 3 idea mining and clean-room descriptions)

Pre-Phase 3 research, 2026-10-24. Two parts:

1. **Idea mining:** every search technique on the Phase 3 list, with what
   it depends on, a tier, a Fork phase and an expected value, all backed by
   published test results.
2. **Clean-room descriptions** of every tier 1 and tier 2 technique: what it
   does, why it gains Elo, conditions and pitfalls, and how to test it.

**Update 2026-10-26:** §3A adds clean-room descriptions of T50-T55 (new
IDs) and full descriptions of T25, T34, T36/T37 and T41 (with T16's check
terms), researched without cloning any engine.

All of it is **REFERENCE ONLY**. No code, pseudocode, tuned constants or
comment text from any engine appears in this file. Parameters are
described by their shape only ("a margin that grows with depth"). Fork
picks its own values by its own tests. The Elo figures and commit
references are published test results, cited so they can be checked. They
are not parameters.

The short entries in [techniques.md](techniques.md) section 3 stay as they
are. This file goes deeper and takes precedence for Phase 3 planning.
Papers on these topics are in [research.md](research.md), "Research
library".

---

## 0. How this was researched, and how to read the numbers

**Sources** (all opened 2026-10-24; full list in
[sources.md](sources.md), section "Search techniques"):
- **Stockfish:** commit messages from a blob-less clone of
  official-stockfish/Stockfish (HEAD dbe600b7), five fishtest run records
  (JSON API), and the "Elo impact" comments that Stockfish's search code
  carried from 2018 to 2025.
- **Fifteen engines that test with SPRT:** Ethereal, Berserk, Weiss,
  Koivisto, Stormphrax, Viridithas, Obsidian, Caissa, Reckless, Alexandria,
  Integral, PlentyChess, Halogen, Seer and Patricia. Their commit messages
  and about 150 pull request bodies, which carry the OpenBench or
  cutechess results, were read.
- **Chess Programming Wiki (CPW)** pages on each technique. Every page was
  served in the wiki's "temporary, read-only recovery" state, and several
  pages are missing (listed in §5).
- **Primary papers and author posts:** Heinz, David-Tabibi & Netanyahu,
  Jiang & Buro, Hyatt & Cozzie, Winands et al., Romstad, Hyatt (2010),
  Madsen (2020). Citations are in §4.

**What the reading of engine code was limited to.** The Stockfish research
agent read the current search code to describe *conditions* (node type,
depth range, in-check) in prose. The engine research agent read three diffs
(Viridithas #352, Reckless #112 and #277) for the same purpose. Nothing
from that code was copied into this file. The author of this file worked
from the agents' prose reports and did not open engine source. The
originality review (2026-10-24) found that several condition lists still
followed Stockfish's current gating in their combination and order; they
were rewritten as generic ideas, with one-engine variants moved to the
evidence lists.

**Reading the Elo numbers.**
- Every figure belongs to one engine, one time control and one stage of
  that engine's development. It does not transfer to Fork. A feature added
  early to a weak engine shows far more Elo than the same feature added to
  a mature one.
- **SPRT stopping bias:** a test that passes stops early, so its point
  estimate runs high. A non-regression ("simplification") pass shows only
  that a feature is worth about zero or less. It is not an exact value.
- **STC / LTC:** Stockfish's fishtest uses 10+0.1 and 60+0.6 seconds, one
  thread (confirmed in the API for 4 runs; assumed for the rest,
  UNVERIFIED). The OpenBench engines mostly use 8+0.08 or 10+0.1 for STC,
  and 40+0.4 or 60+0.6 for LTC.
- **"derived":** many Stockfish commit messages carry only win/loss/draw
  counts. The research agent computed the Elo from those counts. Those
  values are approximate.
- **Removal tests** (feature turned off, everything else kept) are the best
  measure of a feature's worth in a finished engine. Two engines published
  them; §1 has both.

**Tiers.**
- **Tier 1, core:** the search skeleton and the large, universal gains.
  Every strong engine has them, and later techniques depend on them. Build
  first.
- **Tier 2, proven refinement:** has passed SPRT in many independent engines
  and survives in current top engines. Build after tier 1, one at a time.
- **Tier 3, fine-tuning:** small, engine-specific, scaling-sensitive, or
  removed again by the engines that tried it. Try it only after tier 2 is
  in and tuned, and expect many to fail for Fork.

**Expected value bands** (Fork's estimate for a mature engine, from the
evidence below):

| Band | Elo |
|---|---|
| very large | more than 100 |
| large | 30 to 100 |
| medium | 10 to 30 |
| small | 2 to 10 |
| marginal | below 2, or Elo-neutral (kept for safety or simplicity) |

**Phases.** Every technique here is Phase 3 unless stated otherwise. Two
cross-phase effects:
- **Eval-gated pruning margins must be retuned in Phase 4.** Phase 3
  searches with a simple evaluation, and Phase 4 replaces it with a PST
  evaluation and then NNUE. RFP, futility, razoring, ProbCut, the null-move
  eval gate and SEE thresholds are all tied to the eval's scale and
  accuracy.
- **Shared tables are a Phase 6 decision.** That covers history and
  correction tables shared between threads (see §3.20).

---

## 1. What the evidence says, in one page

**Removal tests in two finished engines.** Each row is the Elo lost when
that one feature was switched off.

| Feature | Stockfish 2024-03 snapshot (STC) | Ethereal 2020-01 (#113, 12+0.12) |
|---|---|---|
| Quiescence search | about 155 | (not tested) |
| History / move ordering | (not tested) | 759 |
| LMR | about 117 | 249 |
| Shallow-depth pruning, all of it | about 120 | quiet pruning 175 |
| Late move pruning | about 8 (it was about 30 in 2018) | 77 |
| Singular extension | about 94 | all extensions 60 |
| Null move pruning | about 35 | 93 |
| SEE pruning | about 4 (quiet) and about 11 (captures) | 42 |
| Reverse futility pruning | about 40 | 32 |
| ProbCut | about 10 | 9 |
| IIR | about 9 | (not tested) |
| Futility pruning (parent node) | about 13 | 3 |
| Continuation-history pruning | about 2 | 8 (countermove), 2 (follow-up) |
| Razoring | about 1 | (not tested) |

Stockfish's figures come from its "Elo impact" comments (campaigns in 2018,
2020, 2021 and 2024, last updated in commit a96b0d46). They were deleted in
2025-01 (aa894c0f), and the commit message calls them outdated.
Ethereal's come from commit e755a81 / PR #113: fixed-length tests at
12+0.12 with node-rate normalisation, not SPRT. Features overlap, so the
rows don't add up.

**Older measurement.** Robert Hyatt (OpenChess, 12 July 2010, Crafty 23.3,
30,000 games per version) measured the two big selectivity techniques. On a
base with both null move and LMR turned off:

| Configuration | Elo |
|---|---|
| null move alone | about +130 |
| LMR alone | about +185 |
| both together | about +246 |

The two overlap, so their gains are not additive. The time control was not
stated (UNVERIFIED).

**Lessons that shape Fork's Phase 3:**
1. **Qsearch, move ordering (TT move plus histories), LMR, null move and
   shallow pruning are most of the strength.** Get them right first, and
   test them well.
2. **History quality carries everything downstream.** LMR, LMP and history
   pruning all decide by history, and history is also what let engines drop
   killers and countermoves. Stockfish (2024-07) and five other engines
   (2023-2026) removed them in non-regression tests.
3. **Several terms gain more at long time controls.** Correction history
   gained about 3 times as much at LTC as at STC in Seer #183. Stockfish's
   triple extensions, more aggressive IIR and TT-PV pruning lost Elo at STC
   and passed at VLTC. Low-depth singular extensions gain only at longer
   TC, if at all. TCEC plays very long games, so a search change that is
   neutral or slightly negative at STC is not rejected without a longer-TC
   run.
4. **Thread count matters for shared tables.** Sharing the correction
   history between threads was neutral at 1 thread but gained +44 Elo at 32
   threads in Caissa (24fde49, 2024-12) and about +19 at 8 threads in
   Halogen (#842, 2026-01). TCEC runs up to 512 threads. This belongs in
   Phase 6.
5. **Verification search for null move is Elo-neutral in current engines.**
   Four engines show it neutral, and Halogen gained about +23 by removing
   it (#149, 2020-11). Fork still wants some zugzwang guard: TCEC games
   reach long endgames, and a zugzwang blunder costs a game, not a fraction
   of an Elo. The two goals are in tension; §3.12 has the plan.

---

## 2. Technique table

Dependencies refer to the IDs in the first column. Tiers, phases and
expected values are as defined in §0.

| ID | Technique | Tier | Phase | Depends on | Expected value |
|---|---|---|---|---|---|
| T1 | Negamax alpha-beta, fail-soft | 1 | 3 | eval from side to move's view | foundation |
| T2 | Iterative deepening | 1 | 3 | T1; TT for reuse | foundation (enables ordering, time management) |
| T3 | Quiescence search (captures, evasions; stand-pat) | 1 | 3 | T1, SEE for ordering | very large |
| T4 | Transposition table: cutoffs, TT move, bounds | 1 | 3 | Phase 2 hash memory; T1 | very large (with ordering) |
| T5 | Principal variation search | 1 | 3 | T2, T4, ordering | medium to large |
| T6 | Aspiration windows | 1 | 3 | T2, T5 | small to medium |
| T7 | Static exchange evaluation | 1 | 3 | Phase 1 attacks | enabler (ordering, pruning) |
| T8 | Move ordering: TT move, captures by MVV plus capture history, quiets by history | 1 | 3 | T4, T7, T9 | very large |
| T9 | Butterfly (quiet) history with a gravity update | 1 | 3 | T1 | very large (with T8) |
| T10 | Continuation history (1- and 2-ply, later more) | 2 | 3 | T9, search stack with previous moves | medium |
| T11 | Capture history | 2 | 3 | T7, T9 | small to medium |
| T12 | Pawn-structure history | 2 | 3 (after Phase 4 pawn key decisions, if any) | T9, a pawn hash | small |
| T13 | Null move pruning (eval gate, depth- and eval-based reduction) | 1 | 3 | T1, T4, static eval | large |
| T14 | NMP zugzwang guard: verification search at high depth | 2 | 3 | T13 | marginal (safety) |
| T15 | Late move reductions, base form | 1 | 3 | T5, T8, T9 | very large |
| T16 | LMR adjustments: cut node, TT-PV, captures, improving, history, gives check | 2 | 3 | T15, T17, T18, T10, T11 | medium (together) |
| T17 | Node-type tracking (PV, expected cut, expected all) | 2 | 3 | T5 | enabler |
| T18 | "Improving" flag | 2 | 3 | search stack with static evals | small to medium (through its uses) |
| T19 | TT-PV flag (position was on a PV) | 2 | 3 | T4 | small to medium |
| T20 | Reverse futility pruning | 1 | 3 (retune in 4) | static eval, T18 | large |
| T21 | Late move pruning (move-count pruning) | 1 | 3 | T8, T9, T18 | large |
| T22 | Futility pruning (parent node, quiets) | 1 | 3 (retune in 4) | static eval, T9 | small to medium |
| T23 | SEE pruning (main search: quiets and captures; qsearch: losing captures) | 1 | 3 | T7, T3 | medium to large |
| T24 | Quiet history pruning | 2 | 3 | T9, T10 | small to medium |
| T25 | Qsearch futility / delta pruning (full description §3.27) | 2 | 3 (retune in 4) | T3, T7 | small |
| T26 | Internal iterative reduction | 2 | 3 | T4, T17 | small to medium |
| T27 | Singular extensions | 2 | 3 | T4 (deep, bounded entries), excluded-move search | large |
| T28 | Multi-cut (from the singular search) | 2 | 3 | T27 | small |
| T29 | Double and triple extensions, with a per-line cap | 2 | 3 | T27 | small (scaling-positive) |
| T30 | Negative extensions, including the cut-node form | 2 | 3 | T27, T17 | small |
| T31 | ProbCut | 2 | 3 (retune in 4) | T3, T7, T4 | small to medium |
| T32 | Static evaluation correction history (pawn, non-pawn per side, minor, continuation) | 2 | 3 (late), revisit in 4; sharing in 6 | static eval, T4 bounds, search results | medium (more at long TC and high thread count) |
| T33 | Mate distance pruning | 3 | 3 | mate scores by ply | marginal (helps mate finding) |
| T34 | Razoring (full description §3.25) | 3 | 3 (retune in 4) | T3, static eval, T17 | marginal to small |
| T35 | TT lower-bound early cutoff ("small ProbCut" in Stockfish's comments) | 3 | 3 | T4 | marginal to small |
| T36 | Losing-capture-stage futility ("bad noisy futility"; stop at losing captures when hopeless; §3.26) | 3 | 3 | T8 staged picker, T7, static eval | small |
| T37 | Capture futility (main search; §3.26) | 3 | 3 | static eval, T11 | marginal |
| T38 | Low-depth singular extensions | 3 | 3 | T27 | marginal (LTC only, if at all) |
| T39 | Quadruple / unbounded extra extensions | 3 | 3 | T29 | marginal; tried and removed three times in Stockfish |
| T40 | Recapture extension | 3 | 3 | T4 | marginal; removed in Stockfish 2025 |
| T41 | Check extension (full description with T16's check terms, §3.28) | 3 | 3 | T7 | marginal; removed in Stockfish 2024 |
| T42 | Refutation history bonus after a null move | 3 | 3 | T13, T9 | marginal (one engine, +2) |
| T43 | Null-move threat use (reduce moves that ignore the refuting capture) | 3 | 3 | T13, fail-soft | small, in one engine |
| T44 | Fail-firm / fail-medium return values (RFP, stand-pat, multi-cut, TT cutoff) | 3 | 3 | T1 | small, engine-specific |
| T45 | Killers | 3 | 3 (optional) | T9 | marginal once histories are strong |
| T46 | Countermove table | 3 | 3 (optional) | T9 | marginal once T10 exists |
| T47 | Correction history: threat and material tables, uses in LMR/RFP/extension margins | 3 | 3-4 | T32 | marginal to small |
| T48 | Post-hoc depth adjustment from the eval trend over the last two plies | 3 | 3 | T18 | small |
| T49 | Multi-ProbCut (several depth pairs) | 3 | — | T31 | untested in modern engines; not planned |
| T50 | Static eval refined by the TT score, by bound type (§3.24) | 2 | 3 | T4, static eval, T32 | small to medium |
| T51 | Upcoming-repetition detection, cuckoo table of reversible moves (§3.29) | 3 | 3 | Zobrist keys, key history, halfmove clock | small |
| T52 | Fifty-move eval scaling toward a draw (§3.30) | 2 | 3 (revisit in 4) | static eval, halfmove clock, T4 | small (more at LTC) |
| T53 | Lazy SMP final move selection: voting by depth and score (§3.31) | 2 | 6 | Lazy SMP, per-thread root move lists | small to medium at high thread counts |
| T54 | Lazy SMP thread diversity (§3.32) | 2-3 | 6 | Lazy SMP | small each |
| T55 | History bonus versus malus balance (§3.33) | 2 | 3 | T9, T10, T11 | small |

Not on the list, but used in this file: **staged move generation**
(Phase 1 already has the pieces), **excluded-move search** (needed by T27),
**search stack** (per-ply static eval, current move, flags), **history
malus** (penalty to moves tried before the cutoff move).

### Suggested build order

This is based on CPW's "Improved Connorpasta" list (Aron Petkovski;
community advice, not measured) and the evidence above. One SPRT per step:

1. T1, T2, T3 (with MVV ordering), T4, T5, T6.
2. T7 and SEE ordering (good captures, then quiets, then bad captures).
3. T9 with gravity and malus.
4. T20, T13, T15.
5. T21, T22, T26, T18.
6. T23 (qsearch first, then main search).
7. T10, T11, T24.
8. T17 and T19, then T16 one adjustment at a time.
9. T27, T28, T29, T30.
10. T31, T32, T25, T14.
11. Tier 3, one by one, with longer-TC confirmation.

Tune parameters after each block (SPSA). Phase 4 changes the eval scale,
so the eval-margin parameters get a retune there.

---

## 3. Clean-room descriptions: tier 1 and tier 2

Each entry follows the same layout: **What it does / Why it gains /
Conditions / Pitfalls / How to test / Evidence**. **Condition lists are
unions of ideas across engines, not an implementation order.** Fork
designs its own gating, and the order of its checks, from these ideas; it
does not transcribe any engine's. These are Fork's own
words, written from the research reports. No engine's code, pseudocode or
tuned constant appears here.

**Tests that apply to every entry** (from DESIGN.md §7 and ideas.md, plus
the evidence in §1):
- Put the technique behind a flag, so it can be compared on and off in the
  same binary.
- Run an SPRT at STC on gainer bounds (simplification bounds for
  removals). Then confirm at a longer TC whenever the change alters tree
  shape (pruning, reductions, extensions). Scaling effects are common
  (§1 lesson 3).
- Report the bench node count, signature and nps change. A search change
  changes bench by design, so update `tests/bench.ref` in the same commit.
- Add search counters in debug builds (cutoff rates, prune counts,
  re-search counts). They show whether a condition fires as intended,
  which an Elo test can't show.
- Before relying on a feature, check that the engine still finds mates and
  wins on a published tactical or mate test set, fetched from its primary
  source and cited (non-negotiable 1). Fixed-depth or fixed-node solve
  counts expose pruning that hides tactics.

### 3.1 T1 Negamax alpha-beta, fail-soft

- **What it does:** One routine searches for both sides. A child's score is
  negated on the way back up, so every node maximises from the side to
  move's view. Alpha-beta skips moves that can't change the result given
  the bounds the ancestors already hold. In the fail-soft form, a node
  returns the best score it actually found, even when that score lies
  outside the window, instead of clamping it to alpha or beta.
- **Why it gains:** Fail-soft bounds are tighter, so TT entries prune more
  later. The extra information also helps several techniques: null-move
  threat detection (a fail-soft null search can show "I get mated if I
  pass", which a clamped one can't), RFP and multi-cut return values,
  aspiration re-search placement.
- **Conditions:** All node types. Mate scores are encoded by distance from
  the root, so shorter mates score higher.
- **Pitfalls:**
  - Fail-soft makes search instability easier to see: a re-search can
    disagree with the bound that triggered it. Code that reads returned
    scores must accept bounds, not exact values.
  - When storing in the TT, the bound type must follow from where the score
    lies relative to the original window.
- **How to test:**
  - Compare against a plain minimax at small depths on random positions
    (Fork has perft-style infrastructure and python-chess for legality).
    The root score must be identical for exact windows.
  - The fail-hard vs fail-soft switch is an SPRT-able flag.
- **Evidence:** Fishburn, SIGART Bulletin No. 84, 1983 (DOI
  10.1145/1056623.1056628). Ethereal a0d84b6 (2018) made razoring, RFP and
  ProbCut fail-soft: +2.6 STC, +5.1 LTC.

### 3.2 T2 Iterative deepening

- **What it does:** Searches depth 1, then 2, then 3, until time runs out
  or a limit is reached. Each iteration reuses the TT, histories and the
  previous best move.
- **Why it gains:** The shallower iterations cost little, and they fill the
  TT and histories so that the next iteration's ordering is much better.
  The total is usually cheaper than one direct search to the final depth.
  It also always has a move ready, and its score history drives aspiration
  windows and time management.
- **Conditions:** Root only. A partially finished iteration can be used if
  its first (previous-best) move finished and the result is trusted, or
  ignored. That is a Phase 3 design choice.
- **Pitfalls:**
  - Don't throw away a better move found in an unfinished iteration
    without thought.
  - Make sure "stop" is checked often enough (Phase 2 already handles the
    stop signal).
  - Bench must stay deterministic: fixed depth, one thread, cleared state
    (DESIGN.md Phase 3).
- **How to test:** The root move at depth N matches a fresh depth-N search
  in score. Bench determinism over repeated runs. Time-to-depth
  measurements.
- **Evidence:** Slate & Atkin, Chess 4.5 (1977) is the first documented use
  (via Korf 1985, as quoted on CPW). The KB techniques.md entry has the
  details.

### 3.3 T3 Quiescence search

- **What it does:** At the horizon, keeps searching captures (and queen
  promotions) only, until the position is quiet. The side to move may
  "stand pat": accept the static eval as a lower bound instead of
  capturing. When in check there is no stand-pat, and all evasions are
  searched.
- **Why it gains:** Without it, the eval is read in the middle of exchanges,
  and the search plays into captures it can't see (the horizon effect).
  Stockfish's 2024 snapshot put it at about 155 Elo, the biggest single
  term measured.
- **Conditions:**
  - Captures ordered by MVV plus capture history, or by SEE.
  - Losing captures (SEE below zero) are skipped (see T23).
  - TT probing and cutoffs work there as in the main search, at non-PV
    nodes.
  - Checks in qsearch are optional. Stockfish removed them in 2024 at no
    measurable cost.
- **Pitfalls:**
  - Qsearch explodes without ordering and SEE pruning.
  - Stand-pat must be off in check.
  - Mate detection in qsearch: when in check with no evasions, the side to
    move is mated.
  - Qsearch results stored in the TT must be marked with the lowest
    depth, so they never satisfy a real-depth probe.
- **How to test:**
  - Node counts and nps at fixed depth.
  - A set of positions with pending exchanges: the qsearch value must
    match a hand-checked material outcome. Construct those positions for
    Fork, with an oracle result checked by python-chess.
  - SPRT against "eval at depth 0" is pointless (the gain is huge), so test
    variants against each other: checks on/off, pruning on/off.
- **Evidence:** Stockfish 2024 snapshot (~155 Elo). Stockfish 703f1797
  (qsearch checks removed, 2024, non-regression). Weiss #344 (losing
  captures sorted last: +18 STC on a young engine).

### 3.4 T4 Transposition table: cutoffs, TT move, bounds

- **What it does:** A hash table keyed by the Zobrist key stores, for each
  searched position, the best move, the score, the depth searched and
  whether the score is exact, a lower bound or an upper bound. On a revisit
  it can end the search outright (a TT cutoff), or at least give the best
  move to try first.
- **Why it gains:** Transpositions are common, so whole subtrees are
  skipped. The TT move is the best ordering signal of all: CPW reports that
  in nodes that have a hash move, most cutoffs come from it (CPW's figure
  for Stockfish has no source; UNVERIFIED). Iterative deepening relies on
  the TT to carry information between iterations.
- **Conditions:**
  - Cut only at non-PV nodes, so that the PV is always searched and
    reported.
  - The stored depth must be at least the remaining depth.
  - The bound must point the right way: a lower bound at or above beta, an
    upper bound at or below alpha, or an exact score.
  - Several engines refine the depth rule by node type or allow a
    shallower entry in narrow conditions (tier 3).
- **Pitfalls:**
  - Mate scores are stored relative to the node and converted by ply on
    store and probe (KB techniques.md, CPW Score).
  - A colliding entry can carry an illegal move: validate it with the
    Phase 1 `is_pseudo_legal` and `is_legal`.
  - **Graph history interaction:** a stored draw-by-repetition or 50-move
    score is path-dependent. Stockfish added a workaround at high 50-move
    counts (75f07da9, 2025).
  - Results that depend on the window through pruning must not be stored
    as exact scores (Heinz's note).
  - Excluded-move searches (T27) must not overwrite the real entry.
  - Lockless SMP access needs torn-entry detection (Phase 6; KB
    techniques.md).
- **How to test:**
  - A deterministic bench with TT on, compared against TT off at small
    depth: the root score must agree for exact searches without pruning.
  - A Zobrist consistency check (Phase 1 already has one).
  - A stress test with a tiny hash, to force replacement and collisions.
  - TT hit-rate and cutoff counters.
  - Hyatt & Cozzie (2005) showed that 64-bit keys with move validation make
    collisions harmless in practice: one error per million probes changed
    nothing in their test set.
- **Evidence:** Inherited from Glaurung in Stockfish. Many TT refinements
  each passed at +1 to +4 Elo (Stockfish 582c88ee, b280d2f0, 43e100ae,
  6e9b5af0). Hyatt & Cozzie, ICGA J. 28(3), 2005.

### 3.5 T5 Principal variation search

- **What it does:** At each node, the first move (the expected best) is
  searched with the full window. Every later move is first searched with a
  zero-width window just above alpha, which only asks "is this move better
  than the best so far?". Only if the answer is yes, and the node is a PV
  node, is the move searched again with the full window to get its exact
  score.
- **Why it gains:** With good ordering, the first move is best most of the
  time. Zero-width searches are much cheaper than full-window ones, so the
  later moves are refuted cheaply. CPW estimates about a 10% saving with
  good ordering. PVS is also what makes LMR's reduced searches and their
  re-searches fit together.
- **Conditions:**
  - Carry an explicit PV/non-PV flag through the recursion, rather than
    inferring PV-ness from the window width.
  - Non-PV nodes never re-search with a wider window, because their window
    is already zero-width.
- **Pitfalls:**
  - Inside an aspiration window, the first move's full-window search can
    itself fail, leaving no move and no PV. Handle this.
  - Re-search with the original bounds, not with the null-window result.
  - The PV must be collected only from exact results.
- **How to test:**
  - At fixed depth with no pruning, PVS must return the same root score as
    plain alpha-beta, with fewer nodes.
  - Count re-searches per node.
  - SPRT against plain alpha-beta (expected clear gain).
- **Evidence:** Marsland & Campbell 1982 (as quoted on CPW). CPW's
  Principal Variation Search page.

### 3.6 T6 Aspiration windows

- **What it does:** From some small depth on, the root search uses a narrow
  window centred on the previous iteration's score (or a running average)
  instead of the full range. If the result falls outside, the failing side
  is widened, more each time, and the root is searched again.
- **Why it gains:** A narrow window prunes much more. Most iterations land
  inside it.
- **Conditions:**
  - The window starts small. Engines grow it with the score's size,
    because large evaluations swing more.
  - On a fail, only the failing side moves, by a geometrically growing
    step.
  - Several engines search one ply less after a fail-high, because a
    fail-high usually means the move is good and the exact value matters
    less.
  - Decisive (mate or TB) scores open the window fully.
- **Pitfalls:**
  - Search instability: a re-search can fail the other way. Widening only
    the failing side avoids oscillation.
  - Mate scores outside the window need a full-width search (the CPW page
    does not mention it; UNVERIFIED there, but it follows from the score
    encoding).
  - Fail-lows feed time management (Phase 5).
- **How to test:**
  - Count re-searches per iteration.
  - SPRT of the window-size and widening rules after SPSA.
  - The "reduce depth after fail-high" variant gets its own SPRT.
- **Evidence:** Stockfish 4634be8b (2009, +11 at the developers' own TC)
  and many refinements, each a few Elo. Weiss #117 (smaller initial
  window: +18.6 STC). Reckless #122 and Caissa 723807a (reduce depth
  after a fail-high: +4.6, +1.2). Stockfish 081af908 (2018) similar,
  derived +10.7 / +6.5.

### 3.7 T7 Static exchange evaluation

- **What it does:** Estimates the material outcome of a capture sequence on
  one square without searching it. The sides alternately recapture with
  their least valuable attacker, x-ray attackers join as pieces move off
  the line, and each side may stop when continuing would lose. When judging
  a given move, that first move is forced. The common modern form answers
  a threshold question ("does this move win at least T?") instead of
  computing the exact value, which is faster and enough for every use.
- **Why it gains:** It is an enabler, used for:
  - ordering (good captures before quiets, bad captures after);
  - qsearch pruning;
  - main-search SEE pruning;
  - the ProbCut move filter;
  - LMR treatment of captures.
- **Conditions:** Uses Fork's existing attack generation (Phase 1). En
  passant and promotions need care.
- **Pitfalls:**
  - Pins: a pinned piece may not legally recapture. Stockfish handled pins
    in its SEE from 2016 on. Whether pin-awareness is worth its cost for
    Fork is open: measure it.
  - Kings may capture only when the square is not defended.
  - Promotions change values mid-sequence; decide and document what Fork
    does with them.
- **How to test:**
  - A unit test over constructed positions with hand-derived exchange
    results.
  - Randomised differential testing against a slow reference: a full
    capture-only minimax on one square, which Fork writes itself.
  - Property: the threshold form agrees with the exact value's sign at
    every threshold.
- **Evidence:** Spracklen & Spracklen, BYTE 3(11), 1978 (via CPW).
  Stockfish history: pin-aware SEE (2016), threshold form (0fa80c9b,
  2016), faster version (83ecfa7c, 2020, +2.5 / +2.5).

### 3.8 T8 Move ordering

- **What it does:** Decides the order in which moves are tried. The modern
  order:
  1. the TT move;
  2. good captures and queen promotions, scored by the victim's value plus
     a capture history term;
  3. quiet moves, scored by the sum of several history tables;
  4. captures that lose material by SEE.

  Moves are generated in stages, so that a cutoff from the TT move or a
  good capture saves generating the quiets. The best remaining move is
  picked one at a time (a partial selection sort), not by sorting the
  whole list.
- **Why it gains:** Alpha-beta's savings depend almost entirely on trying
  the best move first. LMR, LMP and history pruning also decide by
  position in this order, so good ordering is what lets them be
  aggressive. Ethereal's removal test of its history tables (−759 Elo) is
  the largest number in this research.
- **Conditions:**
  - Never generate a move twice: the TT move must be skipped when it comes
    up again in its stage.
  - In check, order evasions by their own rules (captures first, then
    quiets by history).
  - Killers and countermoves are optional (tier 3, T45 and T46).
- **Pitfalls:**
  - The TT move must be validated before it is played.
  - Under-promotions belong with the quiets or the bad moves, not with the
    good captures.
  - Staged generation must yield the same set of moves as full generation:
    a bug here silently loses moves.
- **How to test:**
  - An exhaustive test over Fork's perft positions: the staged picker
    yields exactly the legal moves, each once, in every stage combination,
    including with a bogus TT move. This reuses the Phase 1 difftest
    infrastructure.
  - Instrumentation: the share of cutoffs that come from the first move
    (target: a large majority) and the average index of the cutoff move.
  - SPRT for each scoring change.
- **Evidence:** Ethereal #113 (history −759). Stockfish capture history
  (4bc11984, 2017: +5.3 / +2.7). Stockfish killer and countermove removals
  (2024, non-regression). CPW Move Ordering page.

### 3.9 T9 Butterfly history with a gravity update

- **What it does:** A table indexed by side to move and the quiet move's
  from- and to-squares. When a quiet move causes a beta cutoff, its entry
  gets a bonus that grows with depth. Every quiet move tried before it at
  that node gets a penalty (the malus).

  The update is self-limiting ("gravity"): the change shrinks as an entry
  approaches its bound, so values stay bounded. A result that contradicts
  a large stored value moves it more than one that confirms it. Entries
  fade between searches, or are kept, by Fork's choice.
- **Why it gains:** It orders quiet moves by how often they refuted things
  elsewhere in the tree, and that generalises across positions. It is the
  main input to quiet ordering, LMR, LMP and history pruning.
- **Conditions:**
  - Update only on beta cutoffs by quiet moves.
  - The bonus grows with depth and is capped.
  - Captures use their own table (T11).
- **Pitfalls:**
  - Without gravity, values saturate and stop discriminating.
  - Updates at very shallow depth are noise; engines scale them down.
  - Thread sharing is a Phase 6 decision (KB techniques.md).
  - Integer overflow when tables are summed: choose widths deliberately.
- **How to test:**
  - Unit tests on the update rule: a bounded range for any update sequence,
    and monotone responses.
  - Cutoff-position statistics before and after.
  - SPRT of malus on/off and of the update shape.
- **Evidence:**
  - Schaeffer (1983, 1989; KB research.md).
  - Ethereal 013ca36 (2018, gravity form, credited to Stockfish's approach).
  - Halogen #232 (2021, history decay: +19 STC, +36 LTC).
  - Weiss #571 (new bonus formula: +23 / +15).
  - Stockfish 942c18ef (2010, negative values allowed, stated +12).

### 3.10 T10 Continuation history

- **What it does:** History tables keyed by a pair of moves: the move played
  one ply ago (the opponent's), two plies ago (one's own previous move), and
  sometimes four or six plies ago, each paired with the current quiet move.
  Moves are identified by moving piece and destination square. The quiet
  ordering score sums these tables with the butterfly history.
- **Why it gains:** Many good replies depend on what was just played, and
  this captures that context. It generalises the older countermove and
  follow-up ideas into graded scores. It has been one of the larger
  ordering gains in every engine that measured it.
- **Conditions:**
  - Needs a search stack that records each ply's moved piece and
    destination, with a defined entry for a null move (Fork's choice: a
    neutral slot or no update).
  - Updated together with the butterfly history, with the same bonus and
    malus.
- **Pitfalls:**
  - Memory: a 2-ply table indexed by piece and square pairs is large.
    Measure cache effects with `bench/ab.py`.
  - Deeper plies help less. Stockfish removed one of its deeper updates in
    2026 (a43f3682).
- **How to test:** Add the 1-ply table first, then the 2-ply table, then
  deeper ones, each its own SPRT. Watch nps.
- **Evidence:**
  - Stockfish 13c11f40 (2015, countermove history: +8.8 / +7.8) and
    a273b6ef (2016, follow-up history: +7.0 / +8.9).
  - Ethereal 23b841e (2018; with history pruning: +24 STC, +34 LTC) and
    4d20c35 (follow-up: +7.0 / +8.9).
  - Weiss #477 (+45 / +34, early development).
  - Origin: Bill Henry's 2015 proposal (CPW).

### 3.11 T11 Capture history and T12 pawn-structure history

- **T11, what it does:** A history table for captures, indexed by moving
  piece, destination and captured piece type. It gets bonuses and maluses
  like the quiet history. It replaces the "least valuable attacker" part of
  MVV-LVA ordering, and its value also feeds capture SEE thresholds and
  LMR for captures.
- **T12, what it does:** A quiet history indexed by a few bits of the
  pawn-structure hash, the moving piece and the destination. Good moves
  depend on the pawn structure, and this table learns that.
- **Why they gain:**
  - T11 learns which captures actually work in this tree, which static
    piece values can't know.
  - T12 adds a context, the pawn structure, that is stable across many
    positions.
- **Conditions:**
  - T11 is updated for captures on any cutoff. When a quiet move cuts, the
    captures tried before it get a malus too.
  - T12 needs a pawn hash, maintained incrementally. Phase 1 removed
    Fork's pawn key (ORIGINALITY.md, H3 rewrite), so adding it back is a
    new design decision. Its Zobrist part reuses Fork's own keys.
- **Pitfalls:**
  - T11: a weight that is too large lets history override real material
    differences. Test the balance between victim value and history.
  - T12: a table that is too small collides. Size it by measurement.
- **How to test:** SPRT each. Ordering statistics for captures (the share
  of good-capture cutoffs).
- **Evidence:**
  - T11: Stockfish 4bc11984 (2017, +5.3 / +2.7); Ethereal 907e891 (2020,
    +2.8 / +2.3); Seer #90 (+6.7 / +11.0); Weiss #428 failed STC but
    passed LTC (the slowdown costs at STC).
  - T12: Seer #174 (2023-10-23, the earliest in the set: +4.2 / +3.3);
    Stockfish b0658f09 (2023-10-27, credited to Seer: +1.1 / +2.0);
    Weiss #705 (+4.3 / +1.9); PlentyChess #169 / #170 (+2.5, then +9.4).

### 3.12 T13 Null move pruning and T14 its zugzwang guard

- **What it does (T13):** At a node where the side to move already looks at
  least as good as beta, it passes: makes a "null move" that hands the
  opponent a free move. It then searches the result with a much reduced
  depth and a zero window at beta. If even after passing the result is
  still at least beta, the real position is almost certainly at least beta
  too, and the node returns without searching any real move.

  The reduction grows with depth and with how far the static eval exceeds
  beta. A large surplus means a shallower check is enough.
- **Why it gains:** In most positions, having the move is an advantage (the
  null-move observation). So a pass that still fails high proves a lot,
  cheaply. It removes large parts of the tree at nodes that would fail high
  anyway, and it is one of the two biggest selectivity gains: +130 Elo
  alone in Hyatt's Crafty test, about 35 Elo in Stockfish's 2024 snapshot,
  and 93 Elo in Ethereal's removal test.
- **Conditions:**
  - Non-PV nodes. Several engines restrict it to expected cut nodes
    (Stockfish c8d8e362, 2024, non-regression).
  - Not in check.
  - Not right after another null move.
  - Not inside an excluded-move search.
  - The side to move has non-pawn material (the main zugzwang guard).
  - Static eval at or above beta. Engines loosen this gate with depth and
    when improving (T18).
  - Beta is not a mate score.
  - Don't return an unproven mate score from the null search; return beta
    or the bound instead.
  - Skip it when a TT entry already says the position is below beta.
- **Pitfalls:**
  - **Zugzwang:** in positions where any move worsens one's position
    (common in pawn and minor-piece endgames), passing is better than any
    real move, so the null search lies. The non-pawn-material condition
    covers pawn endings only.
  - The null move must update the key, side to move, en passant and
    repetition history consistently. A null move is irreversible for
    repetition purposes.
  - Interaction with ProbCut and multi-cut: all three prune the same kind
    of node (Romstad; Jiang & Buro).
- **T14, the guard:**
  - **The paper's method** (David-Tabibi & Netanyahu 2002, from the arXiv
    PDF): when the null search fails high, the node is not cut. Its depth
    is reduced by one ply and it is searched normally, with verification
    switched off in that subtree, where null fail-highs cut as usual. If
    that search finds no move reaching beta, the node is treated as a
    zugzwang: the depth is restored and the node re-searched. The paper
    uses an aggressive null reduction together with this verification.
  - The paper's measurements predate LMR: verified pruning with an
    aggressive reduction solved more tactics than both plain settings
    while its tree size lay between them.
  - Current engines find verification Elo-neutral and mostly apply some
    form of it at high depth only.
  - **Fork's guard:** a verification at high depth only, whose exact scope
    Fork designs and tests itself, as zugzwang insurance for TCEC endgames,
    on non-regression bounds.
- **How to test:**
  - Zugzwang positions from a published source, fetched and cited (CPW's
    Zugzwang and Null Move pages list positions; each FEN is to be checked
    character by character). The engine must find the right move at
    reasonable depth with NMP on.
  - Counters: null attempts, null cutoffs, verification failures.
  - SPRT for NMP on/off (expected large), then one SPRT per gate or
    reduction change.
  - T14 on non-regression bounds at LTC.
- **Evidence:**
  - Hyatt 2010 (+130 alone).
  - Stockfish: 76971d8a (eval gate relaxed with depth, 2016: +4.2 / +8.2);
    d878bc8c (less at TT-PV, 2020: +3.2 / +7.9).
  - Weiss #129 (eval-based reduction: +5.4 / +11.5).
  - Halogen #491 (skip NMP when the TT says below beta: +9.5 / +10.0).
  - Verification neutral: Berserk #524, Stormphrax #205, Integral #137,
    Reckless #242; Halogen #149 (removal: +23).
  - David-Tabibi & Netanyahu, ICGA J. 25(3), 2002 (arXiv:0808.1125).
  - Heinz 1999 (adaptive reduction: 10-30% fewer nodes than a fixed
    reduction, in DarkThought).

### 3.13 T15 Late move reductions (base) and T16 its adjustments

- **What it does (T15):** Moves late in the ordering are searched at reduced
  depth with a zero window. If such a move unexpectedly beats alpha, it is
  searched again at full depth (first with the zero window, then, at PV
  nodes, with the full window). The reduction grows slowly with both the
  remaining depth and the move's position in the list. Engines use the
  product of two logarithms, a shape CPW describes, and precompute it in a
  table. The reduced depth is clamped so it stays at least one ply and
  below the full depth.
- **Why it gains:** With good ordering, a node's cutoff comes from one of
  the first few moves or not at all, so the late moves are mostly wasted
  effort at full depth. Reducing them saves most of that work, and the
  re-search catches the exceptions. LMR is the largest single selectivity
  gain:
  - Hyatt: +185 Elo alone;
  - Ethereal: −249 when removed;
  - Stockfish: about 117 Elo.

  It works at fail-low nodes, so it complements null move, which works at
  fail-high nodes (Romstad).
- **Conditions (base):**
  - Not for the first move or two. Captures and promotions with good SEE
    are reduced less or not at all (engines differ; see T16).
  - Not when in check: reduce less, or not at all. Engines differ, and
    Alexandria and Obsidian gained by allowing it.
  - Only above a small minimum depth.
- **T16, the adjustments** (each its own SPRT, in roughly this order of
  evidence strength):
  - **History:** reduce good-history moves less and bad-history ones more,
    from the summed quiet histories (capture history for captures).
    Berserk #43: +28; Weiss #451: +14 / +14; Stockfish 74e2fa97 (2016): +1.9
    / +5.5.
  - **Improving:** reduce more when the side to move's eval is not
    improving. Stockfish fff6b9f0 (2013): +7.6 / +6.0; Alexandria #28: +12.
  - **Expected cut node:** reduce more at nodes expected to fail high,
    because a cutoff there needs only one good move and the late moves are
    unlikely to be it. Stockfish 4bebb15e (2013): +3.8 / +6.8; Berserk
    #278: +7.2 / +3.1; Halogen #622: +8.6 / +6.6.
  - **PV and TT-PV:** reduce less at PV nodes and at positions that were on
    a PV earlier (T19). Stockfish 70880b8e (2019): +2.2 / +2.9; Reckless
    #119: +9.0.
  - **TT move is a capture:** reduce quiet moves more, since the position
    is probably tactical and the capture is likely best. Stockfish 77342126
    (2017): +7.2 / +1.8; Obsidian 275d50a: +6.6.
  - **Captures:** reduce captures too, but less, by capture history.
    Stockfish 8493c8c6 (2016): +9.7 / +1.9; Weiss #185: +5.8 / +15.0.
  - **Gives check:** reduce checking moves less. Berserk #281: +13.9;
    Reckless #113: +10.9; Stockfish once exempted checks entirely, then
    reduced them since 5d90c149 (2013): +7.8 / +4.0.
  - **After the reduced search:** if a reduced move came back well above
    the best score, re-search slightly deeper. If it came back barely above
    alpha, re-search slightly shallower. Stockfish c228f319 (2021): +1.8 /
    +1.9.
- **Pitfalls:**
  - Tactics hidden in reduced moves.
  - Reductions must never push depth below the qsearch boundary
    inconsistently.
  - Re-search windows: a reduced search that fails high at a non-PV node
    re-searches at full depth with the same zero window.
  - Fractional reductions (several engines) need care in rounding.
  - History-based adjustments depend on the window, which creates
    instability (CPW Search Instability).
- **How to test:**
  - Counters: share of reduced moves, re-search rate, re-search success
    rate.
  - Tactical-suite solve rates at fixed time.
  - SPRT of the base on/off, then one adjustment at a time. Tune the
    table's two coefficients by SPSA, starting from values Fork derives
    itself.
- **Evidence:** Romstad's LMR article (Glaurung site, via Wayback), plus the
  results listed above.

### 3.14 T17 Node-type tracking and T19 TT-PV flag

- **T17, what it does:** Each node knows whether it is a PV node, an
  expected cut node (likely to fail high) or an expected all node (likely
  to fail low). The root and the first child of a PV node are PV. A cut
  node's children are all nodes and vice versa, with the first child of an
  all node treated as a cut node. The flag is passed down the recursion.
- **T19, what it does:** A bit in each TT entry records that the position
  was searched as a PV node at some point. Later visits, even as non-PV
  nodes, know they are on or near a critical line and prune or reduce less.
- **Why they gain:** Pruning and reduction decisions differ by node type.
  At a cut node, aggressive reductions of late moves are cheap. At PV-like
  nodes, mistakes change the move played. These flags are inputs to LMR,
  NMP, IIR, singular extensions, razoring and RFP.
- **Conditions:** T19 is set when a PV node stores an entry, or inherited
  from a probe that hit a TT-PV entry. It needs one spare bit in the TT
  entry, so the Phase 3 TT entry layout must reserve one.
- **Pitfalls:**
  - Expected node types are only predictions. Code must stay correct when
    they are wrong.
  - T19 can spread too far through the tree (Stockfish tried and removed
    a rule that propagated it, e31f97e3, 2022).
- **How to test:**
  - Counters: the predicted vs actual fail-high rate per node type.
  - SPRT of each use separately.
- **Evidence:**
  - T17: Stockfish 3b8f66f8 / 4bebb15e (2013).
  - T19: Stockfish 70880b8e (2019-01, "Flag critical search tree in hash
    table": stated +2.2 STC, +2.9 LTC); Alexandria #202 (+2.0);
    Viridithas #151 (+2.6); Seer #171 (+1.8 / +2.8).

### 3.15 T18 Improving

- **What it does:** A flag, or a graded value, saying whether the side to
  move's static eval is better now than it was two plies ago, that is, at
  its own previous turn. When two plies ago was in check (no static eval),
  engines look four plies back, or count it as improving.
- **Why it gains:** If the position is getting better, cutoffs are more
  likely and pruning is safer. If it is getting worse, more care is needed.
  It tunes many decisions at once:
  - RFP margin;
  - LMP count;
  - LMR amount;
  - NMP gate;
  - ProbCut margin.
- **Conditions:** Needs a search stack holding each ply's static eval,
  marked absent when in check.
- **Pitfalls:**
  - Whether to compare raw or corrected eval (T32) is not settled by any
    source found (UNVERIFIED). Test both.
  - The in-check fallback must be well defined.
- **How to test:** SPRT it per use, not as one change.
- **Evidence:** Stockfish 5ee16a18 (2013, first use, in LMP: derived +4.3
  / +7.0); Stockfish 4231d99a (2021, graded "smooth" version: +3.9 / +2.2).
  CPW's Improving page lists the uses.

### 3.16 T20 Reverse futility pruning

- **What it does:** At shallow depth, at a non-PV node not in check, if the
  static eval exceeds beta by more than a safety margin, the node returns at
  once without searching. The margin grows with depth, because more depth
  means more chance for the opponent to recover. Some engines return a
  value between eval and beta rather than the raw eval.
- **Why it gains:** Many shallow nodes are hopelessly won for the side to
  move. Searching them proves nothing new. The test is a null-move cut
  without even making the null move. Stockfish put it at about 40 Elo
  (2024) and Ethereal at 32.
- **Conditions:**
  - Non-PV, and in several engines also not TT-PV.
  - Not in check.
  - Depth below a limit.
  - Eval well above beta, and beta not a mate score.
  - Margin smaller when improving.
  - Engines add further gates and margin terms of their own; see the
    evidence list. Fork picks its own by test.
- **Pitfalls:**
  - It relies on the eval's accuracy. Phase 3's simple eval and Phase 4's
    NNUE need different margins. Retune in Phase 4.
  - Zugzwang (the same assumption as null move).
  - Mate scores must never be the returned value.
- **How to test:**
  - SPRT on/off, then the margin shape by SPSA.
  - Counter: prune rate by depth.
  - The tactical suite at fixed nodes, to catch over-pruning.
- **Evidence:**
  - Stockfish 05a8c318 (2010, "post futility pruning"); 65c3bb85 (2018,
    improving margin: +4.5 / +7.6); 08cdbca5 (2023, return a blend: +6.5 /
    +1.2).
  - Weiss #181, Koivisto #150, Halogen #629 (improving: +5 to +12).
  - Stormphrax #207, Halogen #626, Reckless #174 (return-value variants:
    +7 to +10).
  - One engine's variants: skip RFP when the TT move is quiet (Stockfish's
    current gating); a margin adjusted by the previous move's history
    (Stockfish 8b4afcf8, 2022); RFP only without a TT move or with a
    good-history one (Weiss #584: +3.5 / +2.6).
  - The inventor is unknown (UNVERIFIED).

### 3.17 T21 Late move pruning

- **What it does:** At shallow depth, once a set number of quiet moves have
  been searched at a node, the remaining quiet moves are skipped. The
  number grows quickly with depth (roughly with its square) and is larger
  when improving. With a staged move picker, it simply stops handing out
  quiet moves.
- **Why it gains:** Late quiet moves at low depth, ranked low by history,
  almost never raise alpha. Skipping them saves a lot of work near the
  leaves. Ethereal's removal test: 77 Elo. MadChess gained +29 when adding
  it.
- **Conditions:**
  - Non-root, not in check, quiet moves only.
  - Some engines also require non-pawn material for the side to move (an
    engine-specific guard, not part of the idea).
  - The best score so far is not a mated score.
- **Pitfalls:**
  - **False stalemate or mate:** if every move is pruned, the node must not
    conclude "no legal moves". Keep a count of legal moves seen, separate
    from moves searched.
  - It interacts with LMR: tune them together.
- **How to test:**
  - A unit test: a position with only quiet legal moves at low depth does
    not return a stalemate score.
  - SPRT, then SPSA of the count shape.
- **Evidence:** Stockfish 6e1cb6e4 (2010) and 352bd6f5 (2017, skip the
  remaining quiets: +7.8 / +2.0); Weiss #104 (+20 / +25) and #435 (+8.9 /
  +22.8); Madsen 2020 (+29); Ethereal #113 (−77).

### 3.18 T22 Futility pruning

- **What it does:** At shallow depth, at a node where the static eval plus
  an optimistic margin is still at or below alpha, quiet moves are skipped,
  because no quiet move is likely to gain that much. Forms differ between
  engines. One form, of several, applies it per move, using the depth that
  move would get after reduction, and lets the move's history shift the
  margin. Raising the best score to the futility value when pruning keeps
  the node's fail-soft bound honest.
- **Why it gains:** It saves searching quiet moves at nodes that are clearly
  lost by a margin. The value depends heavily on what else prunes the same
  moves: about 13 Elo in Stockfish (2024), only 3 in Ethereal.
- **Conditions:**
  - Not in check.
  - The move is not a capture or promotion and does not give check.
  - Alpha is not near a mate score.
  - Depth below a limit.
  - The margin grows with depth.
- **Pitfalls:**
  - False stalemate (as for LMP).
  - Window-dependent results in the TT (Heinz).
  - Retune in Phase 4.
  - Mate blindness if the margin is too tight.
- **How to test:** SPRT, SPSA of the margin, and prune counters.
- **Evidence:** Heinz 1998 (extended futility pruning and limited razoring:
  13-28% fewer nodes at 8-12 plies, with nearly unchanged solve rates; KB
  research.md). Stockfish 910f779e (2020, +5.9 / +2.7) and fa6c30af (2025,
  +3.7 / +2.4). PlentyChess #72 (more when improving: +8.4).

### 3.19 T23 SEE pruning, T24 quiet history pruning, T25 qsearch futility

- **T23, what it does:** In the main search at shallow depth, a move is
  skipped if SEE says it loses more material than a threshold allows. The
  threshold grows with depth, separately for captures and quiets. The
  shapes differ between engines (some grow faster for quiets, some for
  captures), so Fork fits its own. In qsearch, captures that lose material
  are skipped outright, or once the picker reaches the losing-capture stage.
- **T24, what it does:** At shallow depth, a quiet move is skipped if a
  combination of its quiet history tables, weighted as Fork chooses, is
  below a negative threshold that grows with depth.
- **T25, what it does:** In qsearch, a capture is skipped when stand-pat
  plus the captured piece's value plus a margin can't reach alpha. The
  node-level form, delta pruning, is the same test using the best possible
  capture.
- **Why they gain:** They remove moves that are either materially losing
  (T23), historically bad (T24) or too small to matter (T25), before any
  search is spent on them.
  - T23: Ethereal −42 removed; Stockfish 2010 introduction stated +17.
  - T24: Ethereal 23b841e +24 / +34 (with sorting); about 2 Elo in
    Stockfish by 2021-2024 as other pruning grew.
  - T25: Weiss #188 (+34, early development), Stormphrax #69 (+4.2).
- **Conditions:**
  - Not in check. Not when the best score is a mated score.
  - T23 and T24 are non-root and need at least one move already searched.
    Some engines exempt the TT move.
  - T25 is not used in check and is switched off in the late endgame,
    where giving up material can still win or draw.
- **Pitfalls:**
  - T23 can prune real sacrifices. Engines blend capture history into the
    threshold so known-good sacrifices survive (Stockfish 5d720325, 2024:
    +2.5 / +1.1).
  - T24 thresholds tie to the history scale. Changing the history update
    changes T24.
  - T25 is wrong for promotions, unless the promotion gain is included.
  - All of them: false stalemate.
- **How to test:** SPRT each separately (qsearch SEE first). Tactical
  solve rate at fixed nodes, to catch lost sacrifices.
- **Evidence:** Stockfish 55297064 (2010, stated +17), 4eca981e (2015,
  history pruning: +3.4 / +4.6) and b0658f09 (pawn history in pruning);
  Weiss #355 (qsearch SEE: +36 / +25); Seer #22, #38, #46 (+5 to +15).

### 3.20 T26 Internal iterative reduction

- **What it does:** At a node with no TT move (or no TT entry), deep enough,
  and at a PV node or an expected cut node, it reduces the depth by one ply
  before searching.
- **Why it gains:** A node without a TT move will have poor ordering, so a
  full-depth search there is expensive and unreliable. The shallower search
  costs little and stores a TT move, which the next iteration uses. It
  replaced internal iterative deepening (a separate shallow search to find
  a move) in most engines, being simpler and at least as strong.
- **Conditions:** Above a minimum depth. Engines differ on PV vs cut-node
  use. Stockfish disabled it on PV lines in 2026 (e20ef7ed: +1.9 / +1.7).
- **Pitfalls:**
  - It depends on TT replacement keeping deep entries.
  - Stockfish notes that making IIR more aggressive scales poorly (lost at
    STC, gained at VLTC in some versions): test at long TC.
- **How to test:** SPRT; time-to-depth.
- **Evidence:** Ed Schröder (Rebel, 2020; credited by Weiss #316, +8.0 /
  +5.6, and Berserk #89, +6.7). Stockfish e64b9572 / d90d893b (2020, +1.8 /
  +1.3) and 30fdbf43 (cut nodes, 2021: +1.2 / +2.4). Seer #23 (+14 / +11).

### 3.21 T27 Singular extensions, T28 multi-cut, T29 double and triple extensions, T30 negative extensions

- **T27, what it does:**
  - At a node whose TT entry has a move, a lower bound (or exact score), a
    depth close to the current one, and a non-mate score, it asks whether
    the TT move is much better than every alternative.
  - It searches the node again at about half depth, with the TT move
    excluded and a zero window placed some distance below the TT score.
    That distance grows with depth.
  - If every alternative fails low, the TT move is "singular", and it is
    searched one ply deeper.
- **T28, what it does:** If that excluded search instead fails high above
  beta, at least two moves beat beta, so the node is very likely a cutoff.
  It returns immediately (multi-cut).
- **T29, what it does:** If the alternatives fail low by a wide margin, the
  TT move is extended by two plies, and larger extensions use further,
  wider margins. Which node or move features widen those margins is Fork's
  own choice, by test. The total number of such extra extensions along one
  line is capped, relative to the root depth.
- **T30, what it does:** When the excluded search shows that other moves
  come close to the TT score, the TT move is searched at reduced depth
  instead: a negative extension. Other moves are likely to refute too, so
  the TT move needn't be searched deeply. Fork decides the gating (which
  node types, how large a reduction) by experiment.
- **Why they gain:**
  - A forced or only move is where a fixed-depth search most often misses
    tactics. Extending it buys depth exactly where it matters.
  - The excluded search also reveals the opposite case, many good moves,
    which multi-cut and negative extensions use to save work.
  - Stockfish's singular extension was worth about 94 Elo (2024), and
    Ethereal's extensions as a whole about 60.
- **Conditions:**
  - Not at the root.
  - Not inside another excluded search: one exclusion at a time.
  - Depth above a minimum, which may depend on node type.
  - The TT score is not a mate or TB score.
  - The excluded-move search uses a distinct key or flag, so it neither
    probes as the real node nor overwrites the real node's TT entry.
- **Pitfalls:**
  - **Search explosion:** double and triple extensions must be capped per
    line. Stockfish 559942d6 (2021) added the cap. Seer counts double
    extensions per line.
  - **TT pollution** from excluded searches.
  - **Cost:** each singular test is a whole extra search. The depth
    threshold matters.
  - **Mate-score false cuts** from multi-cut (Halogen #637 fixed one).
  - **Scaling:** Stockfish's triple extensions lost at STC and gained at
    VLTC, and quadruple extensions were removed three times. Test at long
    TC (§1 lesson 3).
  - **Lineage:** CPW says the restricted form in Stockfish 1.6 (2009) may
    originate from Rybka 3 via the disputed Ippolit sources (unproven).
    The Larry Kaufman remark CPW quotes only notes the change in
    Stockfish 1.6. Fork cites the 1988/1990 papers and CPW's description
    only, and never consults Ippolit or Robbolito code (ORIGINALITY.md).
- **How to test:**
  - Counters: singular tests, singular rate, multi-cut rate, extension
    depth histogram, maximum ply reached (to catch explosions).
  - Bench nodes and time-to-depth.
  - SPRT T27 alone, then T28, then T29 (with an LTC check), then T30.
  - A max-ply stress test: search a set of forcing positions to high depth
    and assert no stack overflow and bounded ply.
- **Evidence:**
  - Anantharaman, Campbell & Hsu (1988, 1990; KB research.md).
  - Stockfish 77eec9f9 / 16acf577 (2009).
  - Stockfish f69106f7 (2019, multi-cut, citing CPW: +2.5 / +3.2).
  - Stockfish 33a858ea (2021, double extensions: +2.4 / +1.0; the 559942d6
    message states they were worth about 10 Elo).
  - Stockfish f2b6b5cf (2024, triple: +0.9 / +2.0).
  - Stockfish e1f12aa4 (2022, negative: +2.1 / +1.6) and e551964e (2023,
    cut node: +1.2 / +1.2).
  - Ethereal aa36bc0 (2018, SE: +6.2), #109 (2019, multi-cut: +5.7 / +3.6)
    and 4cff656 (2022, negative: +3.4 / +6.4).
  - Berserk #102 (2021, double: +2.9).
  - Alexandria #332 (2024, triple: +1.9).
  - Björnsson & Marsland (CG 1998 and TCS 2001; multi-cut's origin).

### 3.22 T31 ProbCut

- **What it does:** At a non-PV node of sufficient depth, it asks whether a
  good capture would beat beta by a clear margin. It tries captures whose
  SEE could reach that raised beta, first with a qsearch and then, if that
  passes, with a search several plies shallower, against the raised beta.
  If one succeeds, the node returns, since a shallow search well above
  beta reliably predicts a deep one above beta.
- **Why it gains:** It cuts nodes with an obvious winning capture far more
  cheaply than the full search. The idea is Buro's statistical model
  (Othello), simplified. Plain ProbCut did not help Crafty (Jiang & Buro
  2003), but the capture-only modern form gains about 10 Elo in Stockfish
  (2018-2024) and 9 in Ethereal.
- **Conditions:**
  - Depth above a minimum; beta not a mate score.
  - Skip it if the TT already holds a deep-enough value below the raised
    beta.
  - Only captures and queen promotions that pass the SEE filter. The
    margin is smaller when improving.
  - Store a success in the TT as a lower bound.
- **Pitfalls:**
  - It overlaps with NMP (the same nodes).
  - The margin is tied to the eval scale: refit it per evaluation (Phase 4)
    and after each new net.
  - Tactical blindness if the margin is too small.
- **How to test:** SPRT; counters (attempts, cuts); tactical solve rates.
- **Evidence:**
  - Buro 1995 (KB research.md); Jiang & Buro 2003 (Multi-ProbCut in
    Crafty: 59.4% over 64 games; plain ProbCut no gain).
  - Stockfish 2e8998ea (2011, stated +6 / +5), c5f6bd51 (2018, improving
    margin: +5.0 / +2.9) and 5e91c5dc (2020, TT store: +1.5 / +1.9).
  - Ethereal 744f902 (2017), c2f4305 (2022, TT skip: +3.6 / +4.2).
  - Weiss #283 (+6.4 / +6.7).

### 3.23 T32 Static evaluation correction history

- **What it does:** Small tables learn how far search results tend to land
  from the static eval in positions that share a feature. The feature can
  be:
  - the same pawn structure;
  - the same non-pawn pieces of one side;
  - the same minor pieces (CPW's credited Sirius variant includes the
    king; Stockfish's key does not);
  - the same last two moves.

  Each table is indexed by a hash of its feature and the side to move. The
  learned error from every table is summed, scaled and bounded, then added
  to the raw static eval. The result is the "corrected eval" that the
  pruning decisions use (RFP, futility, NMP gate, razoring, ProbCut,
  improving).

  After a node is searched, each table moves toward the observed error,
  weighted by depth, with a self-limiting update like the history gravity.
- **Why it gains:** Any evaluation has systematic blind spots (some pawn
  structures, some material balances). The search sees them; the eval
  doesn't. Correcting the eval makes every eval-gated decision more
  accurate. The gain is larger with:
  - longer time controls (Seer #183: +5.5 STC, +16.0 LTC);
  - more threads, when the tables are shared (Caissa 24fde49: +44 at 32
    threads; Halogen #842: about +19 at 8 threads).

  Both matter for TCEC.
- **Conditions (when to update):**
  - Not in check.
  - The best move is quiet, or there is no best move.
  - Not inside an excluded-move search.
  - The bound agrees with the direction of the error: a fail-high bound
    only proves the eval was too low, and a fail-low only that it was too
    high.
  - The result is not a mate score.
- **Pitfalls:**
  - The corrected eval must never reach the mate or TB score range: clamp
    it.
  - Keep the raw eval for anything that becomes NNUE training labels
    (Phase 4, data-policy.md). Corrections are search state.
  - Tables are per thread at first. Sharing them across threads is Phase 6,
    with the lockless-access care that implies.
  - The pawn-key requirement is the same as for T12.
  - Weights between tables need tuning (SPSA). Some tables lost their
    value in some engines: Stockfish removed its material and major-piece
    tables, and Viridithas gained by removing material correction.
- **How to test:**
  - A unit test: the correction stays within its bound under any update
    sequence.
  - The mean absolute difference between corrected eval and search score,
    which must fall. This is an offline measure from a search log, in
    Fork's own tooling.
  - SPRT per table, at STC and LTC.
  - In Phase 6, an SMP test of shared vs per-thread tables.
- **Evidence:**
  - Caissa aff7559 (2023-10-24, pawn: +1.7) and 403c8ad (material);
    CPW credits Caissa with the origin.
  - Seer #182 / #183 (2023-12).
  - Stockfish b4d995d0 (2023-12-31, PR #4950: +1.2 / +1.6).
  - Stockfish 60351b9d (2024, minor, major and non-pawn: +4.4 / +8.7) and
    6592b13d (continuation: +0.8 / +1.6).
  - Stormphrax #188 / #189 / #190 (major +3.3, non-pawn +7.6, continuation
    +8.4).
  - The gravity update: Integral #147 (+6.3), Berserk #573 (+2.7 / +3.4).
  - Thread sharing: Caissa 24fde49, Halogen #842.
  - CPW's table of variants credits Caissa, Motor, Sirius, Starzix and
    ice4.

---

## 3A. More clean-room descriptions (added 2026-10-26)

Ten more descriptions, written before implementation at the owner's
request. Three of them are new IDs. The others expand IDs that already
existed as tier 3 or short tier 2 entries, so the table keeps one row per
technique:

| Topic | ID | Status before this section |
|---|---|---|
| Static eval refined by the TT score, by bound type | **T50** (new) | not in the KB |
| Razoring | T34 | short tier 3 entry (§4) |
| Futility for losing captures in the main search | T36, T37 | short tier 3 entries (§4) |
| Delta pruning in qsearch | T25 | three lines in §3.19 |
| Check extension and check-aware LMR | T41, plus the check terms of T16 | short tier 3 entry; one word in T16 |
| Upcoming-repetition detection | **T51** (new) | one UNVERIFIED line in techniques.md |
| Fifty-move eval scaling | **T52** (new) | not in the KB |
| Lazy SMP: choosing the move to play | **T53** (new, Phase 6) | one line in techniques.md §7 |
| Lazy SMP: keeping threads diverse | **T54** (new, Phase 6) | one line in techniques.md §7 |
| History bonus versus malus balance | **T55** (new) | "history malus" named in §2 only |

**How this round was researched.** No engine repository was cloned or
downloaded, and no engine source file was opened. The sources were:
- CPW pages (still the read-only recovery);
- papers and author posts (van Kervinck 2013, Heinz 1998, Moreland, and
  TalkChess threads by Lefler, Marcel and Homan);
- Stockfish commit messages, read through the GitHub commit-search API
  (message text only, no diffs);
- pull-request bodies from the GitHub REST API (the description and the
  posted SPRT result only).

Every page and query is in [sources.md](sources.md), section "Search
techniques, round 2". The CPW pages on razoring, delta pruning and Lazy
SMP quote engine code (Stockfish, Crafty, Strelka, Berserk, PlentyChess,
CPW-Engine). Two commit or PR texts also contained code lines (Stockfish
91a76331, Halogen #853). None of that code was used, and none of it is
reproduced or paraphrased line by line here. The rules of §3 apply
unchanged:
- condition lists are unions of ideas, not an order of checks;
- parameters are described by shape only;
- numbers quoted from a source are marked as **source examples, not
  Fork's values**;
- Elo figures are published results, not parameters.

Every entry here is **REFERENCE ONLY**, verified 2026-10-26. The engines'
licences are those in §5 (GPL-3.0 or AGPL-3.0 for the engines cited here,
MIT for Caissa; Integral has none). The van Kervinck preprint carries
"Copyright 2013, for preview" and no licence, so only its idea is used.
CPW text is CC BY-SA 3.0, and its code quotes are OFF-LIMITS.

### 3.24 T50 Static eval refined by the TT score

- **What it does:** The TT may hold a searched score for the current
  position. The bound type says which way that score is informative:
  - a **lower bound** (the stored search failed high) proves the true value
    is at least the score. If that is above the static eval, the estimate
    is raised to it;
  - an **upper bound** (failed low) proves the value is at most the score.
    If that is below the static eval, the estimate is lowered;
  - an **exact** score can replace the estimate outright;
  - a bound that points the other way says nothing new, and the eval stays
    as it is.

  The refined value feeds the eval-gated decisions: RFP (T20), the
  null-move gate (T13), razoring (T34), futility (T22, T36, T37), ProbCut
  (T31) and the qsearch stand-pat (T3). The unrefined eval is still what
  gets stored in the TT's eval slot.
- **Why it gains:** A TT score comes from a real search, so it already
  reflects tactics the static eval cannot see. Mark Lefler put the idea to
  TalkChess in 2010. A stand-pat score that is too high hides the fact that
  the side to move would lose material if it had to move, and an upper
  bound from the TT corrects that. Eval-based pruning decisions likewise
  become more accurate. Stockfish's first version (2010) used the refined
  value for the null-move conditions and the reductions, and a 2013 commit
  extended it to the qsearch stand-pat.
- **Conditions (union of ideas across sources):**
  - a TT hit with a stored score, and a bound that points the useful way;
  - not in check (no static eval is used for pruning there);
  - not inside an excluded-move (singular) search. Halogen gained from
    skipping refinement there (#744);
  - an unproven mate score must not become the qsearch stand-pat value
    (Halogen #516). Clamp it out of the mate and TB range, or skip it.
  - None of the sources opened sets a minimum TT depth for the entry. That
    is a Fork test, not a known condition.
- **Variants:**
  - Main search first, then qsearch too (Stormphrax #50, then #56 and
    #140).
  - In qsearch at PV nodes only. Berserk #459 removed qsearch refinement,
    and four days later #461 put it back for PV nodes. The PV condition is
    taken from the titles only (UNVERIFIED).
  - "Only when it is more informative" (Weiss #745; the exact rule is
    UNVERIFIED, title wording).
  - Using the refined value more directly in RFP (Viridithas #385: it
    failed its STC gainer test, then passed an LTC non-regression test).
- **Pitfalls:**
  - **Search instability.** On the 2010 thread, Richard Vida (Critter)
    reported that a null-window fail high which came from a TT entry may
    not reproduce in the re-search if the entry has since been
    overwritten. With fail-soft and aspiration windows the score can
    overshoot.
  - **Mate scores** (see Conditions).
  - **Order of eval adjustments.** Correction history (T32), fifty-move
    scaling (T52) and TT refinement all modify the eval. PlentyChess #384
    applies fifty-move scaling after the static eval is read back from the
    TT, and Stormphrax #178 stopped storing scaled evals in the TT. Fork
    should fix one documented order in DESIGN.md (for example: raw eval,
    then correction, then scaling, then TT refinement) and store only the
    raw eval.
  - **Path dependence near the fifty-move horizon.** Stockfish #2453 (2019)
    stops using TT values once the clock is close to 100. The same concern
    applies to refinement; this is Fork's inference, not a measured result.
  - Whether "improving" (T18) should compare refined or unrefined evals is
    open (§6 item 9).
- **How to test:**
  - Behind a flag, with main search and qsearch use switched separately.
  - SPRT at STC and LTC, plus one SMP run: Weiss #336 gained most at 8
    threads, where a shared TT makes hits more common.
  - A debug counter for how often refinement changes the eval, split by
    bound type.
- **Evidence:**
  - Stockfish 807844ea (2010-01-05, "Introduce refine_eval()": +14 in 908
    games at 1+0) and 984ee9d0 (2013-10-08, refined value for stand-pat:
    passed STC and LTC).
  - Weiss #336 (2020): +10.8 at 10+0.1, +12.1 at 60+0.6, +21.4 at 8
    threads 20+0.2.
  - Stormphrax #56 (+3.7) and #140 (+3.6).
  - Halogen #509 (+5.2 at 40+0.4, +11.0 at 8+0.08).
  - Weiss #745 (+2.4 STC, +2.8 LTC).
- **Fork:** `src/search` (searcher, trans_table), Phase 3, after T4, T20,
  T13 and T32. Tier 2. Expected value: small to medium.

### 3.25 T34 Razoring (full description)

- **What it does:** At low remaining depth in a non-PV node, the static
  eval may be so far below alpha that even a large margin, growing with
  depth, can't close the gap. The node then runs a qsearch on a null
  window at alpha instead of a full-depth search. If the qsearch confirms
  that alpha can't be reached, the node returns that fail-low score.
  Otherwise the normal search goes ahead.
- **Historical forms** (CPW, Heinz):
  - **Birmingham & Kent (1977):** at depth-2 expected all-nodes, every move
    was made and statically evaluated, then the moves were sorted. Once a
    move's static value no longer exceeded alpha, it and every move below
    it were pruned. The paper was not opened (UNVERIFIED beyond CPW's
    summary).
  - **Heinz, limited razoring (1998):** at depth-3 nodes, if material plus
    a margin of at least a queen is at or below alpha, the depth is cut by
    one ply, and extended futility pruning then applies at the new depth.
    The exceptions: few opposing pieces left, or an extension on the
    previous move.
  - **Amir Ban (Junior), as quoted on CPW:** razoring means searching to
    reduced depth instead of skipping the subtree.
  - **Dropping into qsearch:** Hyatt's form, from an idea by Romstad, was
    used near the tips at null-window nodes with the eval several pawns
    below beta. CPW says it was dropped from Crafty after cluster testing.
- **Why it gains:** Near the horizon, a position far below alpha almost
  always fails low. The qsearch is cheap, and it checks the one way out,
  which is a capture that wins the material back. Heinz measured limited
  razoring on top of extended futility pruning (DarkThought, 2,180
  positions of ECM, WAC and WCS):
  - 5-15% smaller trees at fixed depths above 10 plies;
  - no measurable loss in solutions.
- **Conditions:**
  - non-PV;
  - not in check;
  - depth below a small limit;
  - eval below alpha by a margin that grows with depth (CPW describes
    Stockfish's 2022 margin as quadratic in depth: a shape, not a value);
  - alpha not near a mate score;
  - the returned score must not be a mate or TB score (CPW mentions later
    precautions for mate finding).
- **Variants:**
  - Reduce instead of prune (Heinz, Ban).
  - Return only on a fail low, which is the safe form. Alternatively, at
    depth 1, also return when the qsearch fails high (Strelka, per CPW).
    Koivisto removed that second form (#223).
- **Pitfalls:**
  - **Never fail high from razoring.** In a TCEC Season 23 game, Koivisto
    saw a tablebase win 47 plies away but would not make progress. Its
    depth-1 fail-high razoring was blamed, and removing it passed a
    non-regression test (#223, +0.5).
  - The margins are tied to the eval scale: retune them in Phase 4.
  - Heinz: a score whose computation depends on alpha must not be stored
    in the TT as exact. The node's result must also be initialised in case
    every move is pruned.
- **How to test:**
  - SPRT.
  - Mate and tactical suites at fixed nodes.
  - A progress test in a long won tablebase ending. If the position from
    Koivisto #223 is used, copy its FEN character by character from the PR
    page and cite it (non-negotiable 1).
- **Evidence:**
  - Stockfish PR #3921 (2022-02, reintroduced: passed STC and LTC on
    gainer bounds);
  - Berserk #339 (+6.0 STC, +7.2 LTC);
  - Reckless #127 (+8.9 STC);
  - Koivisto #223;
  - Heinz 1998;
  - the 2020 removal (§4).
- **Fork:** `src/search`, Phase 3 (retune in 4). Tier 3. Expected value:
  marginal to small.

### 3.26 T36 and T37 Futility for captures in the main search

- **What they do:**
  - **T37, per-move capture futility:** at a shallow non-PV node, a
    capture is skipped when static eval plus the captured piece's value
    plus a margin growing with depth still can't reach alpha. Some engines
    add a capture-history term to the margin.
  - **T36, losing-capture stage:** once the staged picker reaches the
    captures that SEE calls losing, and eval plus a margin can't reach
    alpha, the node stops searching its remaining moves.
  - **A related form:** PlentyChess #439 lets the ordinary quiet-move
    futility test (T22) also prune bad captures.
- **Why they gain:** By CPW's account, captures are normally exempt from
  futility for tactical safety, or only those that could lift the score
  above alpha plus a margin are kept. In a node that is already hopeless,
  a capture that loses material, or wins too little, almost never restores
  the balance.
- **Conditions:**
  - not in check;
  - non-PV (Stockfish's 2021 reintroduction excluded PV nodes and
    promotions);
  - the capture does not give check (Stockfish's 2020 introduction applied
    it to late captures that don't give check);
  - depth below a limit;
  - alpha not near a mate score;
  - a legal move already counted, so the node can't report a false
    stalemate.
- **Variants:**
  - Leave more margin when a less valuable piece takes a more valuable one.
    The recapture is forced, which can leave room for further gains
    (Stockfish bbe98576).
  - Exempt PV lines whose eval is a draw (Stockfish 616eb600).
  - A large capture-history term (Stockfish fb7d3ab3).
- **Pitfalls:**
  - Stockfish has added and removed this idea repeatedly:
    - 2008: bad captures were allowed to be pruned;
    - January 2010: a capture futility was added and retired three days
      later;
    - 2020: introduced, tuned, simplified, then removed in October 2020;
    - December 2021: reintroduced.
  - Its value is small and depends on what else prunes the same moves:
    SEE pruning (T23), LMP (T21) and T36. Tune them together.
  - It can prune real sacrifices.
- **How to test:** separate flags for T36 and T37, SPRT, and tactical
  suites at fixed nodes.
- **Evidence:**
  - Reckless #277 ("bad noisy pruning", 2025-04: +5.3 STC);
  - PlentyChess #439 (+1.4 STC, +2.3 LTC);
  - Integral #259 (+2.1 STC);
  - Stockfish a3477af2 (2008), 6247f27a and e84488ed (2010), 4776dc0e,
    616eb600, bbe98576, e663bc53, 64a63464, 17fb3a8c (2020), fb7d3ab3
    (2021).
- **Fork:** `src/search` (searcher, move_selector), Phase 3 (retune in 4).
  Tier 3. Expected value: small (T36), marginal (T37).

### 3.27 T25 Delta pruning in qsearch (expanded)

- **What it does:** Futility pruning used only in the quiescence search.
  There are two forms:
  - **Per move:** before a capture is tried, if stand-pat plus the
    captured piece's value plus a safety margin can't reach alpha, the
    capture is skipped.
  - **Per node:** if stand-pat plus the largest possible material swing (a
    queen, plus the promotion gain if a pawn can promote) still falls short
    of alpha, the node returns without generating moves.
- **Why it gains:** In a hopeless qsearch node, small captures can't change
  the result. Skipping them saves the move generation, the SEE calls and
  the child nodes. CPW's example: a side that is a rook down need not try
  pawn captures, though a minor-piece capture plus positional compensation
  might still be enough. CPW gives a typical margin of about two pawns,
  depending on the piece values. That is a **source example, not Fork's
  value**.
- **Conditions:**
  - Not in check: there is no stand-pat in check.
  - Switched off in the late endgame. Otherwise the qsearch can't see
    insufficient-material cases, or a winning transition bought with
    material (CPW).
  - Promotions: include the promotion gain, or exempt them.
  - Some engines exempt recaptures (Viridithas #319) and checking captures
    (Viridithas #418).
- **Variants:**
  - The margin based on the capture's SEE value instead of the captured
    piece's value (Berserk #72, "QS and Delta Pruning around SEE Scoring";
    the details are UNVERIFIED, title only).
  - A margin adjusted by the correction value (Reckless #867, title only,
    UNVERIFIED).
  - Exempt only promotions rather than all advanced pawn pushes (Weiss
    #748, non-regression).
- **Pitfalls:**
  - The margin depends on the eval scale: retune it in Phase 4.
  - **The node-level form can become redundant.** Weiss removed it (#455):
    it passed non-regression bounds at +1.9 STC and +6.7 LTC, and the PR
    says the per-move futility tests do its job better. Its first version
    (#31, 2019) used a very pessimistic margin, because a weak eval
    misjudged promotion and capture potential.
- **How to test:** separate flags for the per-node and per-move forms,
  SPRT, an endgame suite, and qsearch node counts.
- **Evidence:**
  - Weiss #31, #455, #748 (and #188 in §3.19);
  - Stormphrax #69 (§3.19) and #139 (+7.9 at 14+0.14);
  - Reckless #169 (+2.2);
  - Viridithas #319 (+0.9) and #418 (+1.7).
- **Fork:** `src/search` (qsearch), Phase 3 (retune in 4). Tier 2.
  Expected value: small.

### 3.28 T41 Check extension, and check-aware reductions (T16's check terms)

- **What the check extension does:** It searches a move one ply deeper
  than usual because it gives check, or because the side to move is in
  check (CPW names both forms).
  - **Never dropping into qsearch while in check** is also a form of check
    extension (CPW). It matters most when the qsearch doesn't generate
    evasions.
  - **Variants in sources:**
    - extend only checks that SEE doesn't call losing. CPW reports Hyatt
      claiming a clear gain in Crafty from not extending, or even reducing,
      checks with negative SEE;
    - limit the extension by move count, but always extend a checking first
      move (Stockfish 7c5d7247, 2016);
    - extend only at higher depth in decisive positions, judged by the
      static eval (Stockfish e8418bb1, 2021);
    - extend only below the singular-extension depth (Berserk #229, title
      only);
    - extend only just before qsearch (Berserk #328).
- **Why it was used:** A check starts a forcing sequence, and the replies
  are few, so the extension is cheap and limits horizon effects (CPW).
  Moreland calls it probably the oldest extension in computer chess. He
  also warns that losing programs are great "spite-checkers", which makes
  it a neutral extension rather than a win-seeking one.
- **Why modern engines dropped it:**
  - Stockfish removed it in 2024 (96837bc4, passed non-regression at STC
    and LTC).
  - So did Stormphrax (#67, +5.5 when removed), PlentyChess (#268, the
    removal passed gainer bounds at +2.7), Reckless (#254, non-regression)
    and Halogen (#752, in-check extensions: +2.4 LTC, +8.3 STC).
  - Singular extensions (T27) and smaller reductions for checks now cover
    the same ground.
  - Reckless added it in March 2025 (#175) and removed it a month later
    (#254). Halogen's later attempts to re-add it were not merged (#824,
    #835, #852).
- **Check-aware reductions (T16):** instead of extending checks, reduce
  them less.
  - CPW lists "reduce less while in check" and "reduce less on moves which
    give check" among common LMR adjustments. Older LMR schemes didn't
    reduce such moves at all ("uncommon conditions" on CPW).
  - Halogen #212 (2020) replaced that exemption with normal LMR for moves
    made in check, moves that give check, and endgames: +2.9 at 60+0.6,
    +5.0 at 10+0.1. A smaller, nonzero reduction beat exclusion there.
  - Ethereal #162 ("Reduce LMR for move that gave check") has no result in
    its body (UNVERIFIED size).
- **Pitfalls:**
  - Search explosion through long checking sequences (CPW forum list;
    Moreland).
  - It overlaps with singular extensions (a check is often singular) and
    with the LMR check terms. Test them as a group.
  - Pruning gates that exempt checking moves (futility, LMP) interact with
    all of this.
- **How to test:**
  - Flags for the extension and for each LMR check term.
  - SPRT, including a removal test once T27 exists.
  - A mate suite at fixed nodes, because check handling affects mate
    finding most.
- **Fork:** `src/search`, Phase 3. The extension stays a tier 3 candidate
  flag. The LMR check terms are part of T16 (tier 2). Fork's qsearch
  already handles evasions in check (T3).

### 3.29 T51 Upcoming-repetition detection (van Kervinck's cycle detection)

- **What it does:** It detects, without generating any moves, that the
  side to move has one reversible move back to a position already seen on
  the current line (or in the game history). Such a node is worth at least
  a draw to the side to move. If alpha is below the draw score, it can be
  raised to draw, and if the draw score is already at least beta, the node
  can return at once.
- **The method** (van Kervinck, 2013 preprint; paraphrased):
  1. **Precompute reversible moves.** For each piece of each colour,
     list every pair of squares it could move between on an empty board
     with a non-pawn, non-capturing move. Each pair gets a "move key": the
     XOR of that piece's two square keys, combined with the side-to-move
     key. XOR is symmetric, so a move and its reverse share one key.
  2. **Store them in a cuckoo hash table** (Pagh & Rodler 2001). Each key
     has exactly two possible slots, so a lookup always takes at most two
     probes. Each slot also stores the two squares. The paper reports 7,336
     such move keys for chess (half that once a move and its reverse are
     merged) and a table of 8,192 slots indexed by two different bit fields
     of the key. **These are the paper's figures, not Fork's values:** Fork
     enumerates its own set and checks the count by an independent test.
  3. **Walk back through the key history.** From the current position,
     look at positions an odd number of plies back (3, 5, 7, ...), where
     the other side was to move, and only as far back as the halfmove clock
     allows. The current key XOR such an earlier key equals a single move
     key exactly when the two positions differ by one piece standing on one
     of two squares.
  4. **Cheap filter first.** Before probing the table, check that the
     opponent's pieces are back where they were. The paper shows that this
     can be read from the key history alone: the XOR of the key differences
     of the opponent's own moves along the path must cancel to zero, modulo
     the side-to-move key. The running XOR is updated two plies at a time,
     so most nodes never touch the table.
  5. **Confirm legality.**
     - The squares strictly between the two squares must be empty, since a
       slider's path can be blocked.
     - The mover's king can't be left in check, because the target
       position already occurred legally.
     - A false match from key collisions never appeared in the paper's
       deep searches from 50,000 positions.
- **How to use the result:**
  - It gives only a lower bound: one drawing move exists, and nothing is
    known about the others. So it helps only where a draw score would raise
    alpha.
  - At null-window nodes, test alpha against the draw score before calling
    it.
  - In fail-soft search, a node that would otherwise return a score below
    the draw score returns the draw score. Otherwise the upper bound is too
    low and a re-search can disagree (the paper's §3.7).
- **Why it gains:** A heuristic search sees a repetition draw only once the
  cycle actually closes. The paper's plot of short against long search
  scores shows a cross along the axes caused by exactly these draws.
  Detecting a cycle one ply early moves the draw into an earlier iteration
  and can give a cheap cutoff. Results in Rookie 3.7:
  - +9.0 Elo over 12,000 games at 40 s + 2 s;
  - 5-6 CPU cycles per node;
  - tree size changed by less than 0.4%.
- **Conditions and corrections from Stockfish's commit history:**
  - Stockfish adopted it in 91a76331 (2018-05, Tom Truscott; passed STC
    and LTC on gainer bounds).
  - **The first occurrence matters.** If the earlier position lies in the
    game history before the root, it must already have occurred twice for
    the cycle to mean a draw. Stockfish ad8b78ad (2019) fixed a case where
    a single earlier repetition plus a move back to a repeated position was
    wrongly scored as an upcoming threefold, and a winning move was missed.
  - Stockfish 6b782211 (2024) dropped an extra "no progress" test and kept
    only the paper's check. Per the message, every decisive PV then ended
    in mate or a TB position.
- **Fork dependencies:**
  - XOR-based Zobrist keys with a side-to-move key (Phase 1 has Zobrist
    hashing; check how its side key is applied);
  - a key-history stack that reaches into the game history back to the
    last irreversible move;
  - the halfmove clock;
  - a null move counts as irreversible (the paper).

  The paper ignores castling and en passant for simplicity. A move that
  changes castling rights also changes the key by the castling term, so
  its difference shouldn't match any table entry. That is Fork's
  inference, to be confirmed by a test, not a claim from the source.
- **Pitfalls:**
  - Building a cuckoo table can loop forever. The paper's remedy is to
    re-seed the Zobrist keys or change the slot functions. Fork's build
    must be deterministic and checked by a test.
  - The game-history twofold rule (above).
  - Draw scores are path-dependent, which brings the usual TT issues
    (graph history interaction; techniques.md §3).
- **How to test:**
  - A unit test that the table's entry count equals an independent
    brute-force enumeration.
  - Positions with an upcoming repetition, built by Fork from move
    sequences rather than typed FENs.
  - A randomized check against a brute-force reference that generates
    legal moves and compares them with the history (Fork's own tool).
  - SPRT.
- **Fork:** `src/core` (Zobrist, the move-key table) and `src/search`,
  Phase 3. Tier 3: one paper and one engine measured here. Other engines
  were not checked. Expected value: small.
- **Sources:** van Kervinck, "A fast software-based method for upcoming
  cycle detection in search trees", preview 2013-04-06 (author copy via
  the Wayback Machine; the direct marcelk.net fetch failed). Pagh &
  Rodler, "Cuckoo Hashing", ESA 2001, LNCS 2161, pp. 121-133, DOI
  10.1007/3-540-44676-1_10 (Crossref record; the paper itself was not
  opened).

### 3.30 T52 Fifty-move eval scaling

- **What it does:** The static eval shrinks toward the draw score as the
  halfmove clock grows. In a long reversible sequence (a fortress, or
  shuffling), the engine then sees its advantage fade. It prefers moves
  that reset the clock, a pawn move or a capture, while the advantage is
  still there.

  The sources describe the shape only loosely: a factor that falls as the
  clock rises, applied to the whole eval (Stockfish moved from scaling one
  endgame term to scaling the eval directly, and from 2020 also the NNUE
  eval). The curve is a Fork choice to test.
- **Why it gains:** Stockfish's 2019 PR (#2306) reports two effects:
  - in endgames where no progress is possible (fortresses, opposite
    bishops), the eval falls toward a draw;
  - in the middlegame, after several shuffling moves with an advantage,
    the engine becomes slightly anxious and tries a pawn move or an
    exchange to keep its edge. The search then reaches the follow-ups
    earlier.

  Halogen measured more at a longer TC: +5.4 at 40+0.4 against +1.4 at
  8+0.08 (#554).
- **Conditions and variants:**
  - **What it applies to:** the static eval only, not search scores, mate
    scores or TB scores.
  - **When it is applied:** after the eval is read from the TT and
    corrected (PlentyChess #384). Store only the unscaled eval in the TT
    (Stormphrax #178, non-regression).
  - **A cap on the adjustment** (Halogen #559, non-regression).
  - **TT keys that include a bucketed clock:** positions identical except
    for the clock then score differently. Results differ:
    - PlentyChess #443 passed non-regression and gained +4.4 on a
      fortress-like test;
    - Halogen #617 failed its gainer test.
  - **Related TT rules near the horizon:**
    - Stockfish #2453 (2019) stops using TT scores as the clock nears 100;
    - Stockfish #6271 (2025) skips TT cutoffs at high clock counts when
      the TT move resets the clock;
    - Stormphrax #338 and #339 (2026) downgrade decisive TT scores and
      reject cutoffs near a fifty-move draw (titles only, UNVERIFIED
      details).
  - Correction history bucketed by the clock (Reckless #934, title only).
- **A search-side alternative that was dropped:** Stockfish's 2019
  "shuffle detection" scored long reversible stretches as draws and
  extended in the PV (76f1807b). It was reverted at once: an extension at
  the leaves made a fixed-depth search hang (5928cb2b). It came back in a
  simpler form, and its extension was removed in November 2019 (ef38046e,
  non-regression at STC, LTC and VLTC). Extensions triggered near the
  leaves need a hard cap.
- **Pitfalls:**
  - Graph history interaction and the TT (above).
  - Phase 4 training labels must not use scaled evals (data-policy.md).
    Scaling is search state, like correction history.
  - **TCEC adjudication:** the draw rule uses the engines' reported evals
    (README). Scaling that pulls reported scores toward zero could matter
    there. Whether it can trigger an early draw adjudication was not
    checked (UNVERIFIED; check against competition.md in Phase 5).
- **How to test:**
  - SPRT at STC and LTC.
  - A fortress test set from a cited primary source.
  - Check that the reported score in a won but slow ending stays sensible.
- **Evidence:**
  - Stockfish 7b064752 (2019-09, "Scale down endgame factor when
    shuffling": passed STC and LTC), 3af083a7 (2020-06, damp the eval
    directly), e5f450cf (2020-08, also damp NNUE evals: passed STC and LTC)
    and 180cab44 (2024, simplification);
  - Stormphrax #15 (2023, no result in the PR body);
  - PlentyChess #71 (+3.2 STC);
  - Halogen #554 and #559.
- **Fork:** `src/search` (where the eval is consumed); the eval module
  stays scale-free. Phase 3, revisited in Phase 4. Tier 2. Expected value:
  small (more at long TC).

### 3.31 T53 Lazy SMP: choosing the move to play (Phase 6)

- **What it is:** When the search stops, each thread has its own best
  move, score and completed depth. The published ways to pick the move:
  1. **Main thread only.** Homan's first EXchess version (2013) used only
     the main thread's result.
  2. **Best single thread.** Choose any thread that has a better mate
     score, or both a better score and a greater depth (Berserk #472,
     2023: +6.0 at 8 threads, 4+0.04).
  3. **Voting.** Each thread votes for its best move. The weight grows
     with the thread's score margin over the lowest score among all
     threads, and with its completed depth (CPW's description, and
     Stockfish d96c1c32). The move with the most weight wins, and a thread
     that voted for it reports the PV.
     - Stockfish's 2018 introduction (Stefano Cardanobile, joint work with
       Stefan Geschwentner, from ideas by Michael Stembera) passed STC at 4 threads and LTC at 8. An LTC run at 4
       threads failed, and a 31-thread LTC was stopped at +1.7.
     - A later change made the weight quadratic (67ae53b0: +5.6 at 31
       threads, 5+0.05).
     - Other engines adopted voting: Berserk #533 (+3.5 at 8 threads),
       Halogen #780 (+8.4 at 8 threads) and #781 (+2.3), PlentyChess #152
       (+18.1 at 8 threads), and Stormphrax #60 and #273 (#273: a
       non-regression pass at 7 threads).
  4. **Voting over several moves per thread.** PlentyChess let each thread
     vote for all of its scored root moves, weighted by depth and score
     margin (CPW; PlentyChess #191, +6.8 with LLR 1.69, so the SPRT had not
     passed when it was merged). It later partly dropped its custom scheme
     (#304) and removed multi-move votes (#371, no result in the body).
- **Special cases (Stockfish):**
  - With mate scores, take the shortest mate, and when being mated, the
    longest defence (9d3a2eca, 2019).
  - No voting for TB losses or mates (84f3bf59, 2020).
  - Among threads with the same move, report the PV of the largest voter
    (d60f5de9; display only).
- **Why it gains:** Helper threads that reached a greater depth or a better
  score know something the main thread doesn't. Voting is also robust to a
  single thread's outlier fail high.
- **Pitfalls:**
  - Compare only completed iterations. A partial iteration's score is only
    a bound.
  - Mate and TB scores need explicit rules (above).
  - The effect depends on the thread count: Stockfish's 4-thread LTC
    failed while the 8-thread one passed.
  - Halogen #458 ("thread meritocracy", +29 at 8 threads) has no
    description, so its method is UNVERIFIED.
- **How to test:** SMP SPRTs at several thread counts at normal (not
  ultra-short) TCs. Single-thread bench is unaffected by design.
- **Fork:** the Phase 6 thread pool and root move list. Tier 2 for Phase
  6. Expected value: small to medium at high thread counts.

### 3.32 T54 Lazy SMP: keeping thread searches diverse (Phase 6)

- **What it is:** Ways to stop helper threads from repeating the main
  thread's work, so that what they write to the shared TT adds coverage.
  The published approaches:
  1. **Nondeterminism alone.**
     - Every thread searches the same root, with the same window, and
       shares only the TT. Timing noise and per-thread history and killer
       tables make the trees drift apart (CPW "Shared Hash Table").
     - Homan's EXchess also had half its threads search one ply deeper. He
       reported about +70 Elo for 2 threads and +140 for 4 in a 6+0.1
       gauntlet, against about +105 for one thread at double time (KB
       research.md).
  2. **Depth offsets and skip patterns.**
     - In Cheng (CPW pseudo-code description), every second helper starts
       one ply deeper.
     - Stockfish added distinct iteration paths per thread in 2015
       (38adb487: +8.9 at 20 threads LTC) and rotating skip patterns in
       2016 (9a10313a).
     - Stockfish **removed** the scheme in 2019 (66818f2e, PR #1972). The
       removal failed its [-3, 1] test at 5+0.05 and at 20+0.2 with 8
       threads, but passed at 60+0.6 with 8 and with 4 threads. The PR
       thread argued that very short SMP tests reward skipping, and that
       SMP changes should be tested at normal TCs.
     - Halogen added depth skipping (#30: +55 at 8 threads, 5+0.05, early
       in its development). Its simplification (#130) passed at 5+0.05 but
       lost 4.4 at 20+0.2, which was accepted.
  3. **Varied root move ordering** (CPW's general description). No
     measured instance was opened (UNVERIFIED).
  4. **Per-thread aspiration windows.** Halogen used them (#84, #87). It
     removed them in #244 despite a loss of 9.4 at 8 threads, as
     potentially unsound at very high core counts.
  5. **Per-thread search-parameter bias.** Reckless #926 (2026) gives
     helper threads a small fixed bias on their reductions, with the sign
     alternating by thread ID, and leaves the main thread unchanged. It
     gained +2.0, while a much larger bias came out at -1.4 (not
     significant). The bias sizes are source examples, not Fork's values.
  6. **Thread-count-aware parameters.**
     - Stockfish reduces more as the thread count grows, "since Lazy SMP
       naturally widens search" (135caee6, 2021: passed STC and LTC; an
       earlier version had been simplified away).
     - Tuning with SPSA at 4 threads (Halogen #778) cost 3 to 7 Elo single
       threaded but gained +9.0 at 8 threads, 20+0.2. Tuning for SMP trades
       away single-thread strength.
  7. **ABDADA (Weill).** Rather than relying on diversity, TT entries
     count the processors searching a node, so a thread can defer moves
     another thread is already on (CPW). It is an alternative design, and
     none of the engines read here use it.
- **Why it matters:** Identical threads duplicate work. Diversity turns
  shared TT hits into extra coverage. Homan's numbers show the Elo gain
  outrunning the time-to-depth gain.
- **Pitfalls:**
  - Tests at ultra-short TCs mislead (the PR #1972 discussion).
  - TCEC scale (up to 512 threads, README) can't be reproduced locally.
    Test at Fork's own maximum, and keep the design simple enough to trust
    beyond it.
  - Keep the main thread unbiased, so single-thread bench and behaviour
    stay deterministic (Reckless #926's design).
- **How to test:** SMP SPRTs at 4, 8 and the machine's maximum thread
  count, at STC and LTC, with an unchanged single-thread bench.
- **Fork:** the Phase 6 thread pool. Tier 2-3. Expected value: small each,
  except the base Lazy SMP itself (Stockfish ecc5ff66, 2015: +44.8 at 20
  threads LTC against the previous YBWC search).

### 3.33 T55 History bonus versus malus: a tunable balance

- **What it is:** When a quiet move causes a cutoff, it gets a history
  bonus, and every quiet move tried before it at that node gets a malus (a
  penalty). CPW: the malus keeps values from saturating and gives
  unpromising moves negative history. CPW also notes that stronger
  programs use a separate formula for the malus.
- **The balance as a parameter:**
  - The malus need not be the negated bonus. It can have its own depth
    slope, offset and cap.
  - Several engines scale it by how many moves were searched before the
    cutoff.
  - Fork should tune the two shapes as independent SPSA parameters. Add
    separate sets per table (quiet, capture, continuation) only if a tune
    shows they differ.
- **Evidence** (all shapes engine-specific):
  - Weiss #296 (2020): the malus itself, +37.5 at 60+0.6, early in its
    development.
  - Separate bonus and malus formulas:
    - Stockfish 442c294a (2023-11: passed STC and LTC on gainer bounds);
    - Weiss #695 (+5.8 LTC; its STC test stopped at +0.6 without passing);
    - Reckless #21 (+3.4).
  - No negative score at depth 1: Stockfish d49b3738 (2024).
  - A malus scaled by move count:
    - Stockfish a016abd6 (2025);
    - Berserk #577 (+2.3 STC, +2.0 LTC);
    - Reckless #444 (+2.0) and #1038 (a decaying quiet malus, +4.7 STC,
      +5.2 LTC).
  - **The best balance keeps moving.**
    - Stockfish split the quiet and capture parameters in August 2025
      (b177b739), simplified them two weeks later (e2fdf6f0) and reverted
      the split in November 2025 (a49b52cf).
    - It simplified the malus again in 2026 (91c6ea82).
- **Pitfalls:**
  - History pruning thresholds (T24) and LMR's history term (T16) depend
    on the history scale. Retune them when the update changes.
  - The gravity update (T9) keeps values bounded whatever the balance.
- **Fork:** `src/search` (quiet_history and the capture and continuation
  tables), Phase 3, tuned with T9 to T11. Tier 2 (as part of T9).
  Expected value: small.

---

**Names Fork's code must not use** (engine-specific identifiers or comment
names the originality review found close to this file's vocabulary;
DESIGN.md §8 grep rule applies to all new names): `statScore`, `ttPv`,
`cutNode`, `Stack` (as the search stack type), `nmpMinPly`, `singularBeta`,
`opponentWorsening`, `hindsight`, `doDeeperSearch`, `doShallowerSearch`,
`BadNoisy`. Added 2026-10-26 from the commit messages, PR texts and CPW
quotes read for §3A: `refine_eval`, `ttValue`, `has_game_cycle`,
`upcoming_repetition`, `progressKey`, `rule50_count`, `stat_bonus`,
`stat_malus`, `get_best_thread`, `completedDepth`, `voteMap`, `ThreadValue`,
`bestThread`. The concepts are fine; the identifiers are not.

## 4. Tier 3 entries (short)

Description, dependencies and evidence only. Each one gets a clean-room
description before it is implemented, if it is ever picked up.

- **T33 Mate distance pruning.** At ply n, no score can be better than
  "mate in n" or worse than "mated in n". Tighten the window to those
  bounds, and return if it closes. Safe; helps mate finding, little Elo.
  CPW's Glass example shows trees up to half the size once a mate is
  found. Cheap: add it with T1.
- **T34 Razoring** (full description in §3.25). At low depth at an expected all node, if the eval is
  far below alpha (a margin growing with depth), run a qsearch, and trust
  it if it can't reach alpha. Stockfish removed it in 2020 (neutral) and
  reintroduced it in 2022 (+1.0 / +1.4), at about 1-2 Elo throughout.
  Other engines show +3 to +9 (Berserk #339, Reckless #127). Pitfall:
  Koivisto #223 cites a TCEC S23 game where depth-1 razoring blocked
  progress in a won tablebase ending. Never let it fail high. Origin:
  Birmingham & Kent 1977; Heinz's limited razoring 1998.
- **T35 TT lower-bound early cutoff.** If the TT holds a lower bound well above beta at a
  depth close to the current one, return without searching. Stockfish
  7c30091a (2021, in check only: +1.1 / +2.1), generalised in 2023-2024 by
  non-regression steps; about 4 Elo (2024). No other engine in the set
  names it. Halogen #745 is a relative (+2.3).
- **T36 Losing-capture-stage futility** (full description in §3.26). Once the staged picker reaches the losing
  captures at a low-depth non-PV node, if eval plus a margin can't reach
  alpha, stop searching the node's remaining moves. Reckless #277
  (2025-04, the first in the set: +5.3), PlentyChess #439 (+1.4), Integral
  #259 (+2.1). Depends on T8 staging.
- **T37 Capture futility (main search)** (§3.26). Futility for captures, using the
  captured piece's value and capture history. Stockfish removed it in
  2010, then reintroduced (2020), removed (2020) and reintroduced it
  (2021, +1.5 / +3.6); about 2 Elo.
- **T38 Low-depth singular extensions.** Below the normal singular depth,
  judge singularity from the static eval instead of an excluded search.
  Koivisto #192 (2022, +2.8 / +8.3 on two STC tests), Stormphrax #221
  (+1.6). Viridithas failed and removed it. Reckless #1033 failed STC and
  passed LTC (+1.1).
- **T39 Quadruple or unbounded extra extensions.** Stockfish tried them
  three times (2024-05 to 2025-01) and simplified them away each time.
  Reckless #705 prefers "more extensions on average" (+2.8 STC; its LTC
  results were not opened, UNVERIFIED).
- **T40 Recapture extension.** Extend a TT-move recapture at PV nodes.
  Stockfish 863a1f2b (2023, +1.6 / +1.2), measured at about 0 STC / 1 LTC
  (2024), removed in 67573218 (2025).
- **T41 Check extension** (full description in §3.28). Extend checking moves by one ply, often only
  when SEE is not negative. Stockfish removed it in 96837bc4 (2024-02):
  singular extensions and reduced LMR for checks cover it. Keep it as a
  candidate flag only.
- **T42 Refutation history bonus after a null move.** In the node right
  after the opponent's null move, give the cutoff move's history update
  the weight of a slightly deeper search. Viridithas #352 (2025-11,
  +2.3), the only instance found.
- **T43 Null-move threat use.** When the null move fails low to a capture,
  reduce the moves that neither give check nor deal with the threatened
  piece more. Berserk #125 (+5.1), later simplified (#296). Stockfish's
  older threat-move uses were all removed (f5727dee, 2013). Needs
  fail-soft.
- **T44 Fail-firm / fail-medium returns.** Return a value between the
  fail-soft score and the bound, for RFP, stand-pat, multi-cut and TT
  cutoffs. Many small gains (Stormphrax #207 +6.8, Halogen #626 +7.8,
  PlentyChess #393 +6.7 in qsearch), but the details are engine-specific.
  Tune Fork's own after tier 2.
- **T45 Killers.** Two quiet moves per ply that caused cutoffs, tried after
  the good captures. Stockfish removed them in 2024 (non-regression, about
  0 ± 1.7 at LTC), and so did Reckless, Halogen and Stormphrax. Others cut
  them down to one. Fork: optional. Add only if histories turn out weak,
  and SPRT it.
- **T46 Countermove table.** The quiet reply that last refuted the previous
  move. Uiterwijk (1992, ICCA J. 15(1)). Stockfish removed it in a45c2bc3
  (2024: −0.3 ± 0.5 STC over 978k games), and so did Reckless, Viridithas
  and Caissa. Subsumed by the 1-ply continuation history.
- **T47 Further correction history uses.** Threat-keyed tables (credited to
  Motor by CPW; no standalone instance found, UNVERIFIED). A material
  table (removed in Stockfish and Viridithas). Using the correction's
  magnitude as a "complexity" signal in LMR (Stockfish e7e78aa0,
  Stormphrax #212), RFP (Stockfish 1611b9c9) and extension margins
  (Reckless #450). Each +1 to +2.
- **T48 Post-hoc depth adjustment.** Change a node's depth after the fact,
  using how the eval moved across the last two plies (Stockfish a944f082,
  Reckless #219: +6.0). It overlaps with T18.
- **T49 Multi-ProbCut.** Several depth pairs with fitted parameters (Buro
  1997; Jiang & Buro 2003 in Crafty). No modern engine in the set uses it.
  Not planned.

---

## 5. Literature and other sources

Papers (citations confirmed via Crossref, arXiv or the author's copy
unless marked):
- John P. Fishburn, "Another optimization of alpha-beta search", ACM SIGART
  Bulletin No. 84, pp. 37-38, 1983. DOI 10.1145/1056623.1056628 (fail-soft).
- Omid David-Tabibi, Nathan S. Netanyahu, "Verified Null-Move Pruning",
  ICGA Journal 25(3), pp. 153-161, 2002. DOI 10.3233/ICG-2002-25305;
  arXiv:0808.1125 (opened).
- O. David-Tabibi, N. S. Netanyahu, "Extended Null-Move Reductions", CG
  2008, LNCS, pp. 205-216, DOI 10.1007/978-3-540-87608-3_19 (citation only;
  the PDF returned 404, so the content is UNVERIFIED).
- Ernst A. Heinz, adaptive null-move pruning (ICCA J. 1999) and extended
  futility pruning / limited razoring (ICCA J. 1998). Author copies opened
  at people.csail.mit.edu/heinz; already in KB research.md.
- Albert Xin Jiang, Michael Buro, "First Experimental Results of ProbCut
  Applied to Chess", Advances in Computer Games 10, 2003 (author PDF
  opened).
- Robert Hyatt, Anthony Cozzie, "The Effect of Hash Signature Collisions in
  a Chess Program", ICGA Journal 28(3), pp. 131-139, 2005. DOI
  10.3233/ICG-2005-28302 (author page via the Wayback Machine).
- Yngvi Björnsson, Tony Marsland, "Multi-cut Pruning in Alpha-Beta Search",
  CG 1998, LNCS (1999), DOI 10.1007/3-540-48957-6_2; and "Multi-cut
  alpha-beta-pruning in game-tree search", Theoretical Computer Science
  252(1-2), 2001, DOI 10.1016/S0304-3975(00)00081-5. Citations only: the
  author PDFs return 404, so their measurements are UNVERIFIED.
- Mark Winands et al., "Enhanced Forward Pruning" (Information Sciences
  175(4), 2005; preprint opened) and "The Relative History Heuristic" (CG
  2004; author PDF opened). Both measured in Lines of Action, not chess.
- Jos Uiterwijk, "The Countermove Heuristic", ICCA Journal 15(1),
  pp. 8-15, 1992, DOI 10.3233/ICG-1992-15103 (citation only).
- Anantharaman, Campbell & Hsu, singular extensions (1988, 1990), and Buro,
  ProbCut (1995): already in KB research.md.

Author posts:
- Tord Romstad, "An Introduction to Late Move Reductions" (Glaurung site,
  Wayback capture 2015-02-12).
- Robert Hyatt, OpenChess, 2010-07-12 (Crafty null move and LMR Elo).
- Erik Madsen, MadChess blog, 2020-02-08 (LMP).

Community guidance: CPW "Search Progression" (the Connorpasta and Improved
Connorpasta lists).

Engines (commit messages and PR bodies; ideas and results only; licences
from the GitHub API and the LICENSE files):

| Engine | HEAD read | Licence |
|---|---|---|
| Stockfish | dbe600b7 | GPL-3.0 |
| Ethereal | 0e47e9b | GPL-3.0 |
| Berserk | 3262851 | GPL-3.0 |
| Weiss | c735b8f | GPL-3.0 |
| Koivisto | 6de225a | GPL-3.0 |
| Stormphrax | d1468d9 | GPL-3.0 |
| Obsidian | 720614a | GPL-3.0 |
| Alexandria | 54d4c20 | GPL-3.0 |
| PlentyChess | 94aff00 | GPL-3.0 |
| Halogen | f1df842 | GPL-3.0 |
| Seer | cf18bf0 | GPL-3.0 |
| Viridithas | b407e3e | AGPL-3.0 |
| Reckless | 69aea90 | AGPL-3.0 |
| Caissa | 324f1f9 | MIT |
| Patricia | 67d83d7 | MIT |
| Integral | bed1786 | none (all rights reserved) |

Integral has no licence: nothing from it may be used beyond the idea level,
which applies to every engine here anyway.

**CPW gaps.** These pages returned 404 in the recovered wiki: Verified Null
Move Pruning, Adaptive Null-Move Pruning, Late Move Pruning, Move Count
Based Pruning, Extended Futility Pruning, Deep Razoring, Followup Move,
Continuation History, Capture History, Engine Programming Discord. The
"Late Move Reduction Test Results" page has lost its result tables. The
wiki text is licensed CC BY-SA 3.0 (page footer). Its code snippets quote
engines under their own licences and are OFF-LIMITS.

## 6. UNVERIFIED items

1. Fishtest STC/LTC settings were confirmed for 4 runs only and assumed for
   the others.
2. Derived Stockfish Elo values are the research agent's trinomial
   arithmetic from win/loss/draw counts, not fishtest's pentanomial
   figures.
3. The time control of Hyatt's 2010 Crafty test.
4. CPW's "most cutoffs at hash-move nodes come from the hash move" figure
   for Stockfish has no source on the page.
5. Origins: the inventors of RFP, "improving" and deep razoring are not
   given on CPW. The first history-based LMR term in Stockfish (before
   2014-09) was not located. Neither was the Stockfish commit that
   introduced the eval-difference quiet ordering bonus or the gravity
   history update.
6. Origins of ideas credited to engines outside the set that were not
   opened (Sirius, Starzix, Motor, ice4, Blackmarlin, Rebel), including a
   standalone threat correction table.
7. Measurements in papers whose PDFs failed: Björnsson & Marsland
   (multi-cut), Extended Null-Move Reductions, Eiríksson 2011, Uiterwijk
   1992, the 1988 singular extensions paper.
8. Reckless #705's LTC and VLTC results; Integral #35's result.
9. Whether "improving" should compare raw or corrected eval.
10. Mate scores in aspiration windows (CPW silent); whether pin-aware SEE
    is worth its cost for Fork (to be measured).
11. (§3A, 2026-10-26) Details known only from PR titles: Berserk #461's PV
    condition for qsearch TT refinement; Weiss #745's "more informative"
    rule; Berserk #72's SEE-based delta margin; Reckless #867 and #934;
    Berserk #229; Stormphrax #338 and #339. Ethereal #162 and Stormphrax #15
    have no result in their PR bodies, and Halogen #458 ("thread
    meritocracy") has no description.
12. Birmingham & Kent 1977 (razoring) is known only from CPW's summary; the
    paper was not opened. Pagh & Rodler 2001 was checked on Crossref only.
13. Whether fifty-move eval scaling (T52) can make TCEC's eval-based draw
    adjudication trigger earlier: not checked against the rules.
14. Whether Fork's Zobrist scheme gives move keys that match T51's
    cuckoo-table assumptions for moves that change castling rights: Fork's
    inference, to be settled by a test.
15. Varied root move ordering as a Lazy SMP diversity method: described on
    CPW, but no measured instance was opened.
16. Emil Fredrik Ostensen's 2016 Lazy SMP thesis (University of Oslo): the
    repository link redirected again on 2026-10-26, so it is still unread.
