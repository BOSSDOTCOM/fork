# Prior art for idea 59, the Boundary Refiner (window-gated evaluation refinement)

Created 2026-11-08. This file is the prior-art search the owner asked for
before any public claim (a TalkChess post or an arXiv note) that idea 59 is
new. Idea 59 is described in main's `docs/ideas.md` ("59. Boundary Refiner:
a rich evaluation consulted only near the window", read on branch phase-4
on 2026-11-08, including its step 2 results of 2026-11-08).

**How this file was written (clean room).**
- Concepts only. No engine repository was cloned or downloaded, and no
  engine source file or pull-request diff was opened. Stockfish pull
  requests were read only as prose (title, description, commit message and
  discussion comments) through the GitHub REST API. Code that appeared
  inside a comment or a forum post was skipped and is not reproduced here.
- Every page opened, including the failed ones, is logged in
  [sources.md](sources.md), section "Boundary Refiner prior art
  (research-boundary-refiner-prior-art.md), 2026-11-08".
- Anything not confirmed on an opened page is marked **UNVERIFIED**, with
  the reason.
- No engine constant (threshold or margin) is recorded. Where a source
  gives a threshold, this file says only that a threshold exists.

**Tags.**
- Every prior-art item below: **REFERENCE ONLY** (ideas, studied and cited,
  never copied).
- Stockfish code and nets: **OFF-LIMITS** (GPL-3.0 code, other engines'
  nets; see [research.md](research.md) §1). Nothing from them is wanted for
  idea 59.
- Licences: Chess Programming Wiki text is CC BY-SA 3.0 (page footer,
  checked 2026-11-08). The arXiv papers were cited from their abstract
  pages or arXiv's HTML rendering; their licences were not checked because
  nothing is reused beyond a citation. Forum posts belong to their authors
  and are cited, not quoted.

**Phase and component.** Phase 4, evaluation and search: idea 59's step 3
(a dedicated refiner sharing the base net's accumulator) and its write-up
under main's `docs/research/boundary-refiner/`, and any external post. This
file changes no engine code.

---

## 1. The idea being checked (Fork's own words, summarised)

A fast base NNUE evaluates every position. A second, richer evaluator is
consulted only when the base evaluation lies within a small margin of the
nearest finite bound of the current alpha-beta window (separate margins for
the main search and quiescence). The second evaluator supplies a correction
(a residual) to the base evaluation. In step 3 the refiner shares the base
net's accumulator, computes extra features (exposure and threats) on demand
only when the gate fires, and is trained on near-window positions taken from
Fork's own search, with deep-search labels.

Step 2 (2026-11-08, fixed nodes, 1,600 games each) used an oracle: the
richer net's whole evaluation, scale-matched, in place of the base one
inside the margin. A window gate at about 3.8% of nodes gained about
+30 Elo (and about +41 at a wider quiescence margin), a random gate at the
same call rate gained an inconclusive +7.6, and a bias-only control lost.
These are Fork's own results, quoted from ideas.md, not prior art.

The question is which parts of this already exist in public engines,
forums or papers.

---

## 2. Prior-art items

Closeness scale: **same** (the same gate and the same evaluator role),
**partial** (shares one essential element), **different** (related family,
different gate and role).

### 2.1 Classic lazy evaluation (Chess Programming Wiki)

- **What it is.** The evaluation is split into stages, usually two. The
  cheap first stage (material and piece-square terms, often updated
  incrementally) is computed first. If its score is already above beta by a
  margin, or below alpha by the same margin, it is returned and the costly
  remaining terms are skipped. The wiki calls this taking the alpha-beta
  principle one step further.
- **Gate.** Distance of the cheap partial score from the alpha-beta window.
- **Second evaluator's role.** The costly terms are added to the cheap
  score, so in effect they are a correction to it, computed only when the
  cheap score is near the window.
- **Closeness: same gate, same additive role.** "Skip the costly part far
  from the window" and "compute the costly part only near the window" are
  the same rule. Idea 59's own literature note calls lazy evaluation "the
  opposite direction"; that framing is not accurate and should not appear
  in a public claim. The real differences are elsewhere: in lazy evaluation
  the stages are parts of one hand-written evaluator, the margin is meant
  as a safety bound (wide enough that the skipped terms rarely matter), and
  nothing is learned.
- **Source:** https://www.chessprogramming.org/Lazy_Evaluation (opened
  2026-11-08; the page's own forum list runs from 1995 to 2017).
- **Verified** 2026-11-08. Tag: **REFERENCE ONLY**. Licence: CC BY-SA 3.0
  (wiki text).

### 2.2 TalkChess, "Is expensive eval required for QS?" (July 2017)

- **What it is.** A thread asking whether quiescence search needs the full
  evaluation. In one reply H. G. Muller says that lazy evaluation usually
  suffices for capture lines that gain material against the principal
  variation score, and that the full evaluation is only needed when the
  line ends very close to that score. Another reply (Jon Dart) notes that
  full and partial evaluations complicate an evaluation cache or hash
  table.
- **Gate.** Closeness to the PV score, which is the window bound in a PVS
  search.
- **Role.** The full evaluation replaces the lazy one near the bound.
- **Closeness: same rationale** ("the costly evaluation matters only near
  the bound"), stated as forum advice, with no learned evaluator and no
  measurement.
- **Why it matters for Fork.** It is a public statement of idea 48's
  argument (an evaluation error matters only where it can flip a comparison
  with a bound) applied to evaluation cost, eight years before idea 59.
  Dart's cache remark is the same concern as idea 59's "Watch" note on TT
  consistency.
- **Source:** https://talkchess.com/viewtopic.php?t=64674 (linked from the
  CPW page above; opened 2026-11-08).
- **Verified** 2026-11-08 (forum posts, the authors' own statements).
  Tag: **REFERENCE ONLY**.

### 2.3 TalkChess, "adaptive lazy eval" (Ed Schroder, August 2017)

- **What it is.** A proposal to set the lazy-evaluation margin from search
  itself: keep a running average of how far the full evaluation lands from
  the cheap incremental score, and use that average plus a safety amount as
  the margin. A reply reports a small self-play gain with a wide error bar.
- **Gate.** Window distance, with a margin calibrated to the measured size
  of the costly terms.
- **Role.** As in 2.1.
- **Closeness: partial** (margin calibration for a window gate). Fork sets
  its margins by measured call rate and SPRT instead; the calibration
  target differs.
- **Source:** https://talkchess.com/viewtopic.php?t=65047 (opened
  2026-11-08).
- **Verified** 2026-11-08 (forum). Tag: **REFERENCE ONLY**.

### 2.4 Stockfish's lazy evaluation of 2017 (PR 966)

- **What it is.** After the cheap evaluation terms, if the score exceeds a
  fixed threshold, a scaled-down score is returned and the rest is skipped.
  The discussion raises multi-stage variants and notes that applying lazy
  evaluation only at some nodes could make the transposition table
  inconsistent.
- **Gate.** Size of the cheap score (an absolute threshold), per the PR
  description; the window is not mentioned.
- **Role.** Skipping the costly terms (the cheap score stands in).
- **Closeness: partial** (staged evaluation; different gate).
- **Source:** https://api.github.com/repos/official-stockfish/Stockfish/pulls/966
  and its issue comments (prose only; opened 2026-11-08).
- **Verified** 2026-11-08. Tag: **REFERENCE ONLY** (code **OFF-LIMITS**).

### 2.5 Stockfish's classical/NNUE hybrid, 2020 to 2023

- **What it is.** From August 2020 Stockfish used NNUE only in positions
  with fairly balanced material and its classical evaluation otherwise
  (PR 2916; the CPW Stockfish NNUE page says this sped search up and gained
  Elo). A maintainer's comment on PR 2916 says the switch applied at any
  search score, only according to material imbalance. Later patches
  changed the gate: a larger threshold as the fifty-move counter grows
  (PR 3011, to send shuffling, fortress-like lines back to NNUE), the
  classical evaluation when the previous ply's evaluation was very large
  (PR 3035), a random 1-in-16 use of the classical evaluation at moderate
  imbalance (PR 3107), and a probabilistic switch back to NNUE with
  opposite-coloured bishops (PR 3146).
- **Gate.** Material imbalance, then rule-50 count, previous-ply score, a
  random draw.
- **Role.** Replacement: one evaluator or the other.
- **Closeness: partial** (a richer evaluator used selectively; the gate is
  not the window).
- **Sources:** PRs 2916, 3011, 3035, 3107, 3146 via the GitHub API (prose
  only); https://www.chessprogramming.org/Stockfish_NNUE, section "Hybrid"
  (opened 2026-11-08).
- **Verified** 2026-11-08. Tag: **REFERENCE ONLY**.

### 2.6 Stockfish PRs 2993, 2994 and 2995: the hybrid condition from the window (August 2020)

- **What it is.** Three pull requests by the same author, all titled
  "Modify the hybrid condition so it uses alpha-beta window information",
  opened on 2020-08-13. Each description says only that alpha and beta are
  used to decide whether to use lazy evaluation, which in the hybrid of the
  time meant the classical evaluation in place of NNUE. All three were
  closed within minutes of opening, unmerged. The comments ask for test
  results and the author says his repository needs fixing; no test result
  appears in the opened prose.
- **Gate.** The alpha-beta window. The exact condition (which bound, what
  margin, which direction) is **UNVERIFIED**: it is stated only in the
  diff, which was not opened under the clean-room rule.
- **Role.** Replacement (which evaluator to use).
- **Closeness: partial, and the nearest public precedent found for gating
  the choice of a richer NNUE evaluation on the window.** It has no
  learned residual, no refiner trained for the region, and no published
  result.
- **Source:** https://api.github.com/repos/official-stockfish/Stockfish/pulls/2993
  (also /2994, /2995, their comments and 2995's commit message; opened
  2026-11-08).
- **Verified** 2026-11-08 (existence, title, description, dates, closure).
  Gate details **UNVERIFIED** (diff not read). Whether a fishtest run was
  made: **UNVERIFIED** (fishtest not searched).

### 2.7 The NNUE "lazy" path through the PSQT output (Stockfish, 2021)

- **What it is.** In 2021 Stockfish's network had a cheap PSQT output
  alongside the costly positional layers. A "lazy" path trusted the PSQT
  output alone and skipped the positional layers in some cases (PR 3499
  made its threshold a named parameter; PR 3503 removed the path,
  reporting that the extra positional evaluations paid for their speed
  cost).
- **Gate.** A "lazy threshold" on the PSQT output. Whether it involved the
  window is **UNVERIFIED** (the prose does not say).
- **Role.** The costly head was computed conditionally on top of the same
  feature transformer, which is the shared-accumulator, conditional-head
  structure of idea 59's step 3, used in the opposite sense (skipped
  rather than added).
- **Closeness: partial** (shared accumulator, conditional extra
  computation; gate not shown to be the window; no learned residual for
  the region).
- **Sources:** PRs 3499 and 3503 via the GitHub API (opened 2026-11-08).
- **Verified** 2026-11-08, except as marked. Tag: **REFERENCE ONLY**.

### 2.8 Stockfish's `simple_eval` lazy evaluation (2023, PR 4771)

- **What it is.** A purely material evaluation replaced the network when
  the side to move already had a large material advantage, with guards
  (shuffling lines, an imbalance already at the root, a winning or losing
  root score) and a little random noise. The description says about 2% of
  leaves were evaluated this way. Removed in 2024 once the dual network
  existed (PR 5037).
- **Gate.** Material advantage, plus root conditions.
- **Role.** Replacement by a cheaper evaluator.
- **Closeness: different** (a cheap evaluator in a region, the reverse of
  idea 59).
- **Sources:** PRs 4771 and 5037 via the GitHub API (opened 2026-11-08).
- **Verified** 2026-11-08. Tag: **REFERENCE ONLY**.

### 2.9 Stockfish's dual network: small net and big-net re-evaluation (2023 to 2026)

- **What it is.** Stockfish 16.1 (release post dated 2024-02-24) added a
  secondary network "used to quickly evaluate positions that are easily
  decided". The pull requests say the small net is used when the material
  imbalance is high (PR 4910), and that it was trained only on positions
  with a large material difference, the same region it serves (PR 4915).
  The material threshold was later made to fall as pawns come off
  (PRs 5252, 5323). From May 2024 some small-net positions were
  re-evaluated with the main net "when small net evals hint that higher
  eval accuracy may be worth the slower eval speeds" (PR 5238); the
  condition was then changed to re-evaluate only when the small net's
  output contradicts the material count (PR 5271), and later rewritten so
  that it depends only on the small net's own outputs (PR 5501). PR 5083
  computed only the small net's PSQT part when its evaluation was large.
  PR 6796 (May 2026) proposed removing the small net; it reports
  non-regression tests that failed, but argues from the measured speed
  loss that the small net's lower evaluation quality was itself costly,
  and cites a fortress misjudged because the material difference passed
  the threshold. Whether 6796 itself was merged was not checked; the KB's
  Stockfish 19 entry ([research.md](research.md) §1) records the release
  that dropped the small net.
- **Gate.** Material imbalance (small net); the small net's own output
  (big-net re-evaluation). The window does not appear in any opened
  description.
- **Role.** Replacement in both directions; no residual.
- **Closeness: partial.** The re-evaluation step is the nearest Stockfish
  mechanism in spirit (a richer evaluation called only where the cheap
  one's output suggests accuracy matters), but its gate is the cheap
  output's own value, not the distance to alpha or beta. The small net's
  training on its own gate region is a precedent for training an evaluator
  on the positions its gate selects, which idea 59's step 3 also does.
- **Sources:** https://stockfishchess.org/blog/2024/stockfish-16-1/;
  PRs 4898, 4910, 4915, 5083, 5238 (and its commit message), 5252, 5271,
  5323, 5501, 5674, 6796 via the GitHub API (opened 2026-11-08).
- **Verified** 2026-11-08. The exact re-evaluation condition is
  **UNVERIFIED** beyond the prose quoted in paraphrase above (it is stated
  only in code). Tag: **REFERENCE ONLY** (code, nets and their
  Lc0-labelled data **OFF-LIMITS**).

### 2.10 Deep Blue's fast and slow evaluation

- **What it is (as remembered, not confirmed).** The Deep Blue chess chip
  is often described as having a fast evaluation and a slower, fuller one,
  with the slow one skipped when the fast one is far enough outside the
  window.
- **Status: UNVERIFIED.** The primary source (M. Campbell, A. J. Hoane Jr.
  and F.-h. Hsu, "Deep Blue", Artificial Intelligence 134(1-2):57-83, 2002,
  DOI 10.1016/S0004-3702(01)00129-1; metadata confirmed via Crossref) could
  not be opened: ScienceDirect returned HTTP 403, and the CPW Deep Blue
  page does not describe the evaluation stages. If confirmed, it would be
  another window-gated two-stage evaluation (same family as 2.1) in
  hardware.

### 2.11 LCZero mailing list, "use multiple neural nets?" (Warren D. Smith, December 2018)

- **What it is.** Two posts. The first suggests a slow, stronger net for the
  first nodes of each search and a fast net afterwards. The second suggests
  training the net to also predict the size of its own error (against a
  search-backed value), then using the fast net everywhere and re-evaluating
  with the slow net when the predicted error is unusually large, with the
  threshold tuned by play. The author says he does not know whether it
  would gain strength.
- **Gate.** Search order (first post); the cheap net's predicted error
  (second post).
- **Role.** Replacement.
- **Closeness: partial** (a fast net everywhere plus a stronger net on a
  gated subset; the gate is predicted uncertainty, not window distance).
- **Source:** https://groups.google.com/g/lczero/c/EGcJSrZYLiw/m/netJ4S38CgAJ
  (opened 2026-11-08).
- **Verified** 2026-11-08 (mailing-list post). Tag: **REFERENCE ONLY**.

### 2.12 Multiple Policy Value MCTS (Lan, Li, Wei and Wu, 2019)

- **What it is.** Two policy-value networks of different sizes in one MCTS
  (tested on NoGo). Each grows its own tree under a fixed simulation budget;
  the large network evaluates the not-yet-evaluated leaf with the highest
  visit count in the small network's tree, and the two values are blended
  with a fixed weight. It beats either network alone at equal compute.
- **Gate.** A budget split, and importance by visit count.
- **Role.** Blending, not a residual.
- **Closeness: partial** (an expensive network spent on the "important"
  states of a search; MCTS rather than alpha-beta, no window).
- **Source:** arXiv:1905.13521 (v1, 2019-05-31), abstract via the arXiv API
  and method section via ar5iv (opened 2026-11-08). The abstract page lists
  no journal reference; the IJCAI 2019 venue is **UNVERIFIED** (seen only
  in search results).
- **Verified** 2026-11-08. Tag: **REFERENCE ONLY**.

### 2.13 Two-fidelity best-action identification in minimax trees (Chen and Chen, 2026)

- **What it is.** A minimax tree search with a cheap biased evaluator and an
  expensive accurate one. At decision-critical nodes the algorithm chooses
  between expanding with the cheap evaluator and certifying locally with
  the expensive one. It keeps confidence intervals and refines a node only
  as far as its uncertainty could still change the comparison at the root,
  with proofs of correctness and cost bounds.
- **Gate.** Decision relevance: whether the node's uncertainty can still
  flip a root comparison.
- **Role.** The two evaluators' intervals are intersected (both inform the
  value); no learned residual.
- **Closeness: partial, and the closest academic statement of idea 59's
  rationale** (spend the expensive evaluation where it can change a
  decision). The setting differs: fixed-confidence identification in
  stochastic trees with known error envelopes, not an alpha-beta engine
  with a window margin and a trained refiner.
- **Source:** arXiv:2606.01708 (v2; v1 submitted 2026-06-01), abstract via
  the arXiv API and the HTML rendering of v2 (opened 2026-11-08).
- **Verified** 2026-11-08. Tag: **REFERENCE ONLY**.

### 2.14 Value of computation in game search (Russell; Russell and Wefald)

- **What it is.** Decision-theoretic search control: a computation is worth
  doing according to its expected effect on the final decision. Russell's
  paper extends this to single successor evaluations and gives an improved
  MGSS* algorithm with results on Othello.
- **Gate.** Expected value of a computation.
- **Role.** Chooses which nodes to expand or evaluate, not which evaluator.
- **Closeness: different** (the general principle behind 2.13 and idea 48).
- **Sources:** arXiv:1304.1133, S. Russell, "Fine-Grained Decision-Theoretic
  Search Control" (abstract opened 2026-11-08). S. Russell and E. Wefald,
  "Principles of metareasoning", Artificial Intelligence 49(1-3):361-395,
  1991, DOI 10.1016/0004-3702(91)90015-C: metadata confirmed via Crossref,
  content **UNVERIFIED** (not opened).
- Tag: **REFERENCE ONLY**.

### 2.15 Conditional computation, cascades and early exit (machine learning)

- **What they are.** Networks or pipelines that spend more computation only
  on hard inputs: conditional computation with learned gates (Bengio,
  Leonard and Courville, arXiv:1308.3432, 2013), early-exit side branches
  taken when confidence is high (BranchyNet, Teerapittayanon, McDanel and
  Kung, arXiv:1709.01686, 2017), a learned number of steps per input
  (Adaptive Computation Time, Graves, arXiv:1603.08983, 2016), and boosted
  cascades of simple features (Viola and Jones, CVPR 2001, pages
  I-511-I-518, DOI 10.1109/CVPR.2001.990517).
- **Gate.** A learned gate, the cheap model's confidence, or an early
  rejection stage.
- **Role.** Skip or add computation inside one model or pipeline.
- **Closeness: different** (the general family; none uses a search window).
- **Verified** 2026-11-08: the three arXiv abstracts. Viola and Jones:
  metadata via Crossref only; its content is **UNVERIFIED** (IEEE page not
  opened). Idea 59's ideas.md entry cites Viola and Jones (2001) and
  Bengio, Leonard and Courville (2013); both citations match the metadata
  above. Tag: **REFERENCE ONLY**.

### 2.16 Correction history (residual corrections from search)

- **What it is.** Engines keep tables, indexed by hashes of board features
  (pawns, material, minor pieces and others), of the difference between
  search results and the static evaluation, and add the table's value to
  later static evaluations. The CPW page credits Caissa (October 2023) as
  the first.
- **Gate.** None: applied at every static evaluation, with update
  conditions on the search result.
- **Role.** A residual added to the static evaluation, learned online from
  search.
- **Closeness: partial** (a residual correction learned from search
  results, but ungated, a table rather than an evaluator, and learned
  during play rather than offline from deep labels).
- **Source:** https://www.chessprogramming.org/Static_Evaluation_Correction_History
  (opened 2026-11-08). Fork already has correction history (search-techniques.md).
- **Verified** 2026-11-08. Tag: **REFERENCE ONLY**. Licence: CC BY-SA 3.0.

### 2.17 Futility pruning (window distance as a gate for a different decision)

- **What it is.** At frontier nodes, a move is skipped when the static
  evaluation plus a margin cannot reach alpha.
- **Closeness: different.** It uses the same quantity as idea 59's gate
  (the evaluation's distance to a bound) to decide pruning, not which
  evaluator to call. Listed so that a public claim does not suggest the
  gating quantity itself is new.
- **Source:** https://www.chessprogramming.org/Futility_Pruning (opened
  2026-11-08). **Verified** 2026-11-08. Tag: **REFERENCE ONLY**.

### 2.18 Searched with nothing relevant found

- **Shogi (YaneuraOu, Suisho).** The CPW YaneuraOu page mentions
  interchangeable evaluation files but no gated second evaluator; CPW has
  no Suisho page (HTTP 404). Web searches found nothing. YaneuraOu's own
  documentation was not opened: **UNVERIFIED** either way.
- **Lc0 and AlphaZero-family engines.** Apart from 2.11 and 2.12, nothing
  was found on gating a second network. The Lc0 blog and its GitHub
  discussions were not searched systematically.
- **arXiv keyword searches** (cascade, lazy evaluation, expensive
  evaluation and alpha-beta, NNUE, value of computation, multi-fidelity
  tree search): only 2.12 to 2.14 were relevant. Rapfi (arXiv:2503.13178,
  Gomoku, incremental distilled network) was checked at abstract level and
  has no gated second evaluator in its abstract.

---

## 3. Summary table

| # | Source | Gate | Second evaluator's role | Closeness | Status |
|---|---|---|---|---|---|
| 2.1 | CPW, Lazy Evaluation | cheap score's distance beyond alpha or beta | costly terms added only near the window | **same** gate and additive role (hand-written, safety margin, nothing learned) | verified |
| 2.2 | TalkChess t=64674 (Muller, Dart; 2017) | closeness to the PV score | full evaluation instead of lazy near the bound | same rationale (forum advice) | verified |
| 2.3 | TalkChess t=65047 (Schroder, 2017) | window distance, margin from running average | as 2.1 | partial | verified |
| 2.4 | Stockfish PR 966 (2017) | absolute cheap-score threshold | skip costly terms | partial | verified |
| 2.5 | Stockfish hybrid (PR 2916 and later; CPW) | material imbalance; rule 50; previous ply; random | replace (NNUE or classical) | partial | verified |
| 2.6 | Stockfish PRs 2993-2995 (2020) | alpha-beta window (exact form unknown) | replace (lazy or not) | partial; nearest NNUE-era precedent; closed untested | existence verified; condition **UNVERIFIED** |
| 2.7 | Stockfish PRs 3499, 3503 (2021) | "lazy threshold" on the PSQT output | skip positional layers on a shared accumulator | partial | verified; window use **UNVERIFIED** |
| 2.8 | Stockfish PRs 4771, 5037 (2023-24) | material advantage plus root guards | replace with material only | different | verified |
| 2.9 | Stockfish dual NNUE (SF 16.1; PRs 4898-6796) | material imbalance; small net's own output | replace (small net; big-net re-evaluation) | partial | verified; exact condition **UNVERIFIED** |
| 2.10 | Deep Blue (Campbell, Hoane, Hsu 2002) | window distance (as remembered) | slow evaluation near the window | would be same family | **UNVERIFIED** (403) |
| 2.11 | LCZero list (W. D. Smith, 2018) | search order; predicted error | replace | partial | verified |
| 2.12 | MPV-MCTS, arXiv:1905.13521 | budget; visit count | blend | partial | verified |
| 2.13 | 2FFS, arXiv:2606.01708 | decision relevance (can flip a root comparison) | intervals intersected | partial; closest academic rationale | verified |
| 2.14 | Russell (arXiv:1304.1133); Russell and Wefald 1991 | value of computation | chooses expansions | different | 1304.1133 verified; 1991 **UNVERIFIED** |
| 2.15 | Conditional computation, BranchyNet, ACT, Viola-Jones | learned gate; confidence; cascade stage | skip or add computation | different | arXiv verified; Viola-Jones **UNVERIFIED** |
| 2.16 | CPW, Correction History | none | residual from search, every evaluation | partial | verified |
| 2.17 | CPW, Futility Pruning | evaluation plus margin against alpha | prune (not an evaluator) | different | verified |

---

## 4. Verdict: what is new and what is not

**Not new.** Consulting a costlier evaluation only when a cheap score lies
near the alpha-beta window is classic lazy evaluation (2.1), described on
the Chess Programming Wiki (which lists forum threads on it from 1995 on), with the
costly part added to the cheap score just as idea 59 adds a correction. The
argument that the costly evaluation matters only near the bound was stated
publicly (2.2). In the NNUE era, Stockfish used a richer evaluator
selectively under several gates (2.5, 2.9), computed costly layers
conditionally on a shared accumulator (2.7), and trained a network on the
very region its gate selected (2.9). A Stockfish pull request in 2020 even
proposed choosing between NNUE and the classical evaluation from the window
(2.6), though it was closed unmerged with no published result. Gating a
second network on predicted error (2.11) and spending an expensive
evaluator where it can change a decision (2.12, 2.13) are also published.
So a public post must not claim that window-gated evaluation, two-tier
evaluation, or a residual correction to a static evaluation is new; and
step 2's oracle (the richer net's evaluation used inside the margin) is in
mechanism a near-window evaluator swap of the lazy-evaluation family.

**Possibly new (within the sources searched).** No source found combines:
(a) a complete, strong NNUE as the base evaluator with a separately
**trained** refiner whose output is a residual, consulted only within a
small margin of the nearest window bound (main search and quiescence
margins set separately), where the margin is a budget choice rather than a
safety bound (in step 2 the mean absolute correction at the gated sites, 25.6 cp,
was as large as the main-search margin and larger than the quiescence one);
(b) training that refiner specifically on near-window positions from the
engine's own search, with deep-search labels; (c) sharing the base
accumulator and computing the extra features only when the gate fires; and
(d) a controlled measurement isolating the gate's location: at equal call
rate, a window gate against a random gate, plus a bias-only control.
Item (d) is the strongest candidate for a contribution: no source found
reports such a control in any engine.

**Suggested wording for a careful public claim.** "Idea 59 belongs to the
family of lazy and two-tier evaluation, where costly evaluation work is
done only when a cheap score is near the alpha-beta window; that gate is
decades old, and Stockfish has used selective second networks under other
gates. What we have not found in public engine documentation, Stockfish
pull requests, the Chess Programming Wiki, the forum threads we read or the
papers we checked is a separately trained residual network, trained on the
engine's own near-window positions with deep-search labels, consulted only
inside a small window margin on top of a full NNUE, together with a
controlled test showing that the gain depends on where the refiner is
consulted (window gate against a random gate at equal call rate, and a
bias-only control). We would be glad to hear of earlier work." This is a
statement about a search, not a priority claim: Discord discussions,
fishtest test descriptions, other engines' commit histories and most
TalkChess threads were not searched systematically, and several sources
remain UNVERIFIED (2.6's exact condition, 2.10, 2.14's 1991 paper, 2.15's
Viola-Jones content).

---

## 5. Limits of this search

- **Not searched:** Discord servers (no public quotations found), the
  fishtest test database (test descriptions there could hold
  window-gated experiments that never became pull requests), commit
  histories of engines other than Stockfish, OpenBench instances, and most
  TalkChess threads (only threads reached from the CPW Lazy Evaluation page
  and from web searches were opened).
- **Not read by rule:** diffs and source code, so every exact gate
  condition stated only in code is UNVERIFIED.
- **Paywalled or blocked:** the Deep Blue paper (ScienceDirect, HTTP 403),
  Russell and Wefald 1991 (not attempted after the 403 on the same
  publisher), Viola and Jones (IEEE).
- **Recommended before a post:** search fishtest for tests by the author of
  PRs 2993-2995 in August 2020, and post the claim as a question
  ("is this known?") to TalkChess first; replies there are the fastest way
  to surface unpublished precedent.
