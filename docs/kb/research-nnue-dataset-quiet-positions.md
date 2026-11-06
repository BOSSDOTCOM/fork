# Quiet-position selection for NNUE data: "Study of the Proper NNUE Dataset" (arXiv 2412.17948)

Created 2026-11-06. This file goes deeper than the short entries in
[research.md](research.md) ("Study of the Proper NNUE Dataset") and
[nnue-design.md](nnue-design.md) §0 item 8 and §6.5. Those entries stay
as they are and agree with this one; where detail differs, this file is
newer and takes precedence.

**How this file was written (clean room).**
- The only source opened is the paper itself: the arXiv abstract page and
  the full text (PDF v1, cross-checked against arXiv's HTML rendering for
  the margins and the distribution targets). Both are logged in
  [sources.md](sources.md), section "Quiet-position selection (research-
  nnue-dataset-quiet-positions.md), 2026-11-06".
- No engine or trainer repository was cloned or downloaded, and no engine
  source was opened. The paper's references (among them a Stockfish
  trainer wiki page it cites for "datasets should be mostly quiet") were
  **not** opened.
- **Concepts only.** The paper prints a short algorithm listing and a
  short network definition. Neither is reproduced here; the method is
  described in prose, in this file's own words.
- **The paper's numbers are the paper's.** Every threshold or target it
  gives is quoted below as "paper's value". None of them is a Fork
  constant. Fork's rule: every constant is Fork's own measurement on a
  pre-declared grid, with a recorded justification and a constant screen
  before use (CLAUDE.md non-negotiable 6; DESIGN.md "Search constants").
- Fork facts in section 3 were read from Fork's own repository (branch
  phase-4, 2026-11-06): `src/datagen/self_play.hpp`,
  `tools/train/src/main.rs`, `tools/datagen/endgame_slice.py`,
  `docs/DESIGN.md` §5.3 and §5.6, `docs/ideas.md` ideas 13, 45 and 46.

**Tags.**
- The paper's method: **REFERENCE ONLY** (study the idea, write Fork's own
  code). Paper licence: **CC BY 4.0** (as stated on the arXiv listing,
  checked 2026-11-06).
- The paper's data (grandmaster Xiangqi games plus self-play games between
  other engines): **OFF-LIMITS** to Fork in any case (other engines'
  games; and it is Xiangqi). Nothing from it is wanted.
- Fork's own self-play data, Fork's own evaluators (the default network
  and the bootstrap evaluation) and Syzygy WDL labels: **USE** under
  strategy A+ ([data-policy.md](data-policy.md) rules 1-4).

**Phase and component.** Phase 4, the training-data side: the training
filter in `tools/train` (Rust, bullet-trainer with viriformat's reader),
an offline pass over sealed shards built on `fork` / `fork_datagen`
(`src/datagen`), and the data manifests. No engine (search or inference)
change.

**Source.** D. Tan and N. Watkinson Medina (University of California,
Riverside), "Study of the Proper NNUE Dataset", arXiv:2412.17948v1
[cs.AI], submitted 2024-12-23, 10 pages, 4 figures; DOI
10.48550/arXiv.2412.17948 (arXiv-issued); no journal reference listed.
https://arxiv.org/abs/2412.17948. Verified 2026-11-06.

---

## 1. The quiet-position selection method

Verified 2026-11-06 against the full text.

### 1.1 Setting

- **The game is Xiangqi (Chinese chess), not chess.** The authors chose it
  because material counts for less there and because perpetual check or
  chase loses, so games are sharper and draw less. Chess results are left
  to future work.
- **Source games.** About 44,000 master-level tournament games (2008-2024)
  from two Xiangqi game sites (paper's figure), plus about 30,000
  "synthetic" games (paper's figure) played between other engines and the
  authors' own engine, started from random positions taken out of the
  master games.
- **Candidate positions.** The candidates are not only the positions that
  occurred in those games. For every game position, the method plays
  **each legal move** in turn and tests the resulting child position. So
  the candidate pool is the one-ply neighbourhood of the game record,
  including children reached by bad moves, which the quiet test is then
  expected to remove when they leave material hanging.

### 1.2 What counts as quiet

The paper's working definition: a position is quiet when no forcing
sequence available from it (captures, forks, checks) changes the material
balance by much. The paper illustrates it with four diagrams: a king in
check (rejected), a rook that can be taken for free (rejected), a knight
fork of king and rook (rejected), and a position where only roughly equal
exchanges are possible (kept). Its worded example of "not quiet" is a
piece that can be won for free next turn so that the score swings by about
five pawns.

The test has three parts, applied to each candidate:

1. **Not in check.** Any position with the side to move in check is
   rejected outright. Being out of check is necessary but not sufficient
   (a fork can exist without a check).
2. **Static eval against quiescence.** Compute the static evaluation of the
   position and the quiescence-search value. If they differ by more than a
   first margin, reject: the gap means a capture sequence is pending that
   the static score does not see (the hanging-rook diagram).
3. **Static eval against a full search.** Compute a negamax (alpha-beta)
   search value. If it differs from the static evaluation by more than a
   second margin, reject: the gap signals a mating attack or a forcing
   tactic beyond plain captures (the fork diagram).

Both comparisons use the absolute difference, so a position is rejected
whether the search finds it better or worse than the static score.

**Paper's values (not Fork constants):** first margin (static against
quiescence) 60 centipawns; second margin (static against search) 70, the
unit not stated in the text (centipawns by context). The paper says both
were found "through testing" but shows no sweep, no data and no
alternatives tried. Fork must not adopt either value without its own
measurement and screen.

### 1.3 Diversity and the score distribution

The paper insists the kept set must still cover all kinds of positions:
balanced and lopsided, middlegame and endgame, open and closed. Its
argument: a net that never sees large material deficits will not learn to
punish them (its example: giving away two rooks and still calling it
equal). It states distribution targets for the scores of the kept
positions, from the side to move's view.

**Paper's values (not Fork targets):** half the positions with a positive
and half with a negative score (the sentence literally says "50% ... have
position evaluation values" and "50% ... have negative"; the first half is
read here as "positive", an interpretation); at least 50% with scores in
[-100, +100]; at least 40% outside that band. How the targets are reached
(subsampling, reweighting, or generation choices) is not described.

### 1.4 Labels and network

- **Evaluator.** The starting evaluation was a simple handcrafted one
  (piece-square tables only, from a 2008 UCLA dissertation the paper
  cites); a second, richer handcrafted evaluation (an open-source Xiangqi
  engine's) was also used to show the method does not depend on the
  evaluator.
- **What the label is: UNVERIFIED.** The paper speaks of
  "position/evaluation pairs" but does not say whether the stored target
  is the static score, the quiescence value or the search value, what
  search depth was used, whether game results enter the target, or how
  scores are mapped into the sigmoid output. The loss is called mean
  squared error. Quiescence details (captures only or with checks) and the
  negamax depth are also not given (**UNVERIFIED**: not in the text).
- **Network.** A very small two-layer net: about 1,620 inputs per side,
  one hidden layer per perspective whose two halves are concatenated,
  clipped to [0, 1], and a single sigmoid output; about 0.6 MB. The text
  gives the hidden layer as 256 while the printed definition reads as 128
  per perspective concatenated to 256: the two agree only if "256" means
  the concatenated width (an inconsistency in the paper, noted, not
  resolved).

## 2. Results

Verified 2026-11-06 against the full text.

- **Headline.** The Xiangqi NNUE trained on the filtered data scored 65%
  against the same engine with its previous piece-square-table
  evaluation, which the paper reports as "around +100 Elo" (paper's
  figures). For scale, a 65% score is about +108 Elo under the usual
  logistic model (Fork's arithmetic, not the paper's).
- **What is missing from that result:**
  - the number of games, the time control or node budget, the openings,
    and any error bar or confidence interval (none given);
  - **any ablation of the filter**: no run trains the same net on
    unfiltered data, on check-only filtering or with other margins. So the
    +100 measures "NNUE against a piece-square table", not "quiet filter
    against no filter". The filter's own contribution is **not measured**
    in the paper;
  - any loss numbers. The claims that noisy positions stop training from
    converging, raise the mean squared error "drastically", and make the
    engine sacrifice material or hesitate are qualitative, with no figures.
- **Second evaluator.** With the richer handcrafted evaluation the method
  is said to work "perfectly fine"; no numbers are given.
- **Rating over time.** A chart shows the engine's rating rising from
  about 2400 to about 2650-2660 over six months after adopting NNUE
  (values read off the figure, approximate). The rating pool is not named
  and the gain mixes further training and search improvements, as the
  paper itself says.
- **The authors' own limits.** The method is "not mathematically proven",
  may need changes for other evaluators, and is to be tested on chess,
  shogi and other variants in future work. Success is judged only by
  playing strength.
- **Fork's reading of the evidence: weak.** One variant that is not chess,
  a handcrafted-evaluation baseline far below Fork's current default, no
  ablation, no statistics. It is a clear description of a filter that the
  community also describes informally (nnue-design.md §6.5), not evidence
  that the filter adds strength on top of Fork's existing one.

## 3. How it could apply to Fork's data

### 3.1 Where this sits in Fork's plan

**UNVERIFIED: no written "better labels" experiment was found.** On
2026-11-06 the phrases "better labels", "label filter(ing)", "label
quality" and "quiet position(s)" were searched in `docs/ideas.md`,
`docs/DESIGN.md`, `docs/` and `tools/` on phase-4, across every local
branch's `docs/` and `tools/` (git grep), and in this KB. The only hit is
design-accuracy.md §4.3 ("the fastest net that gives equal label quality
labels", about time-matched labelling). The nearest written plans are:

- DESIGN.md §5.3 (deliverable 2, "What is recorded"): filtering happens
  at training time, not in datagen, "so the data stays complete for later
  rescoring and filter changes". A quiet filter is exactly such a change.
- ideas.md idea 46, rank 0: the offline residual study (frozen S512r2's
  residuals against the labels on 2-5 M held-out positions). The
  residual it measures is the paper's second quantity (static eval
  against the search label) with S512r2 as the static evaluator.
- ideas.md idea 45 and DESIGN.md §5.6 item 7: the Syzygy endgame slice in
  g3s2.
- phase4-designs/design-novelty.md and judgement.md: the optional
  relaxation of the "best move is a capture" filter for exposed captures.

So this section is written as input to a filtering experiment that has yet
to be specified; the owner should confirm where it belongs.

### 3.2 Fork's pipeline today (facts from the repo, 2026-11-06)

- **Data.** Fork's own self-play in viriformat (one packed board per game,
  then a move and a 16-bit White-view score per position), labelled by
  the default engine's search (labeller policy, DESIGN.md §5.3) at 20,000
  nodes per saved position. The split search (idea 13, standing since
  2026-10-31) saves about half the positions not in check; unsaved
  positions get a 4,000-node search and the sentinel score 32767, and
  positions in check a 2,000-node search.
- **Trainer filter** (`tools/train/src/main.rs`, viriformat's built-in
  filter): drop the side to move in check; drop positions whose recorded
  move was "tactical" (a capture or promotion, measured in deliverable
  4); drop |score| > 20000 (mate and tablebase scores, and through the
  sentinel every unsaved record).
- **Endgame slice** (`tools/datagen/endgame_slice.py`): random legal
  positions of at most 5 pieces, side to move not in check, each written
  as a one-move game with a quiet legal move and a score of plus or minus
  a fixed large value (or 0) chosen so the trainer's target equals the
  Syzygy WDL.

### 3.3 Which of the paper's ideas fit

1. **Not in check.** Already in Fork's filter. Nothing to add.
2. **Static eval against quiescence** fits best. It needs only the
   position and an evaluator, not the label, so it does not feed the
   labeller's own errors back into the selection (the risk in item 3).
   Fork's current proxy ("the move played was a capture or promotion")
   overlaps with it but differs in both directions: it drops positions
   where an equal trade was simply the best move (which the paper would
   keep, as its "equal exchanges" diagram says), and it keeps positions
   whose best move is quiet while a capture sequence is still pending,
   for example the middle of an exchange or a hanging piece that the
   search chose to answer with a stronger quiet move (which the paper's
   test would drop). Which evaluator supplies the static score is itself
   a choice to measure: the labelling network (S512r2 today), or Fork's
   own bootstrap evaluation, which mirrors the paper's use of a simple
   handcrafted evaluation and is independent of the net being trained.
3. **Static eval against the search score.** Fork already stores the
   search score: it is the label. So this test needs no new search, only
   the static eval of each kept position. But with the labelling network
   as the static evaluator it means "drop the positions the current net
   gets most wrong", which removes the hardest and most informative
   examples and can freeze the net's blind spots (the data feedback loop
   in design-speed.md's risk table). It is better used as a
   **measurement** (how much of the residual is concentrated in
   "tactical" positions, idea 46's residual study) than as a filter, unless
   an experiment shows otherwise.
4. **The score distribution targets.** Worth measuring, not adopting.
   Fork's games are shaped by the opening discard (first search beyond
   400 cp), the 700 cp / 8-ply score adjudication and Syzygy
   adjudication at table entry, so lopsided positions may be scarcer than
   the paper wants. A histogram of the kept scores of g3s2 by band (side
   to move's view) shows whether there is a gap; any rebalancing (a band
   weight or subsampling in the trainer) is its own experiment.
5. **Children of every legal move.** A poor fit. Each extra position
   would need its own 20,000-node label, and datagen is Fork's binding
   cost (design-accuracy.md §4.3). Not recommended unless a later
   diversity experiment asks for it.

### 3.4 How it could be built without touching sealed data

- **An offline pass, not a datagen change.** A Fork tool (a `fork`
  subcommand or a `fork_datagen` mode, run through `tools/jobs/jobctl.py`)
  replays each sealed shard, and for every position the trainer would
  keep computes the static eval and the quiescence value with a named
  evaluator. Sealed shards and their manifests are never modified.
- **Output that the trainer needs no new code for.** Write a derived copy
  of each shard in which the positions the quiet test rejects carry the
  existing sentinel score (32767): the trainer's |score| > 20000 rule then
  drops them, the game's move chain stays intact, and
  `verify_games.py` can check the copy like any shard. Alternatively a
  per-position keep mask read by a custom filter path in `tools/train`.
  The derived set gets its own manifest naming the source part, the
  evaluator (network name or "bootstrap"), the build, the test and its
  threshold.
- **Self-play shards only.** The Syzygy slice must be exempt: its scores
  are deliberately far from any static eval, so a static-against-label
  test would reject all of it, and its labels are exact, so the
  noisy-label argument does not apply.
- **The cost of the pass is UNVERIFIED** (one static eval and one
  quiescence search per kept position, over hundreds of millions of
  positions): measure it on one shard before planning a full run.

### 3.5 What would need measuring

All rules declared before any run, as Fork does for every experiment:

1. **Offline counts first** (no training): on a held-out sample of g3s2
   (idea 46's 2-5 M positions would serve), the distribution of
   |static - quiescence| and |static - label| for each candidate
   evaluator, the share of kept positions each threshold on a wide grid
   (not centred on the paper's values) would drop, and the overlap with
   the existing tactical filter. A test that drops almost nothing beyond
   the capture filter can stop there.
2. **Training arms**: control (today's filter) against one or two
   thresholds of the quiescence test, and optionally "quiescence test in
   place of the capture filter". Two seeds per arm, identical schedules
   and positions seen (as item 7's recipe comparison), the drop rate
   recorded.
3. **One shared validation set** for every arm (today's filter), plus a
   report on a quiet-only subset: losses of nets trained on differently
   filtered data are otherwise not comparable.
4. **Strength decides.** The best arm then goes through the standard new
   network path: parity chain, endgame acceptance test, fixed-node screen
   and an STC SPRT on [0, 5] against the default. A loss improvement alone
   does not promote anything.
5. **Any threshold kept** goes into the constants record with its
   measurement and is screened against known engines before the commit.

### 3.6 Risks

- **Weak transfer evidence.** Xiangqi, a handcrafted baseline, no
  ablation (section 2). The filter's value on top of Fork's capture filter
  and a 20,000-node search label is **UNVERIFIED** and could be zero.
- **Training-serving mismatch.** Fork's search calls the evaluation at
  many non-quiet nodes (pruning decisions at interior nodes, quiescence
  stand-pat before captures are resolved). A net that never sees such
  positions may be worse calibrated exactly there.
- **Self-reference.** Filtering by the labelling net's own disagreement
  with its search label removes hard examples and biases later
  generations (section 3.3, item 3).
- **Lost data.** Every dropped saved position cost a 20,000-node search;
  a strict test wastes a share of the most expensive input Fork has.
- **Provenance and bookkeeping.** The pass must not alter sealed shards,
  must record its evaluator and threshold, and must keep each labelling
  net's parts apart (DESIGN.md decisions log, 2026-10-30), or later nets
  cannot be traced.
- **Data policy.** Fully inside A+ as long as the static and quiescence
  scores come from a Fork binary and the positions are Fork's own
  self-play. No external evaluator, dataset or engine may be used for the
  test.

## 4. UNVERIFIED items in this file

- The label the paper trains on, the negamax depth, the quiescence
  details and the score-to-target mapping (not stated in the paper).
- The unit of the second margin (not stated; centipawns by context).
- The reading of "50% ... have position evaluation values" as "positive"
  (an interpretation of the sentence).
- The paper's game count, time control and error bars for its +100 Elo
  result (not given), and the rating pool of its chart.
- That Fork has a written "better labels" experiment (none found; section
  3.1).
- The cost of an offline quiescence pass over Fork's data, and the value
  of any quiet filter for Fork (both need measuring).
