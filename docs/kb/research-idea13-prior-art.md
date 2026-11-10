# Prior art for idea 13, the split search in data generation

Created 2026-11-09. This file is the prior-art search the owner asked for
(order of 2026-11-09) before any public write-up of idea 13: a reproduction
guide under main's `docs/research/`, a TalkChess post or an arXiv note (the
"Publication plan (owner, 2026-11-07)" in main's `docs/ideas.md`, idea 13,
read on branch phase-4 on 2026-11-09). Idea 13 is described there and in
main's `docs/DESIGN.md` (the fork_datagen "Split search" paragraph, read
the same day).

**How this file was written (clean room).**
- Concepts only. No engine repository was cloned or downloaded, and no
  engine source file or diff was opened. GitHub pull requests were read
  only as prose (title, description, comments) through the GitHub REST API;
  READMEs and documentation pages were read as prose. Command lines or code
  that appeared inside a comment, README or blog post were skipped and are
  not reproduced here.
- Every page opened, including the failed ones, is logged in
  [sources.md](sources.md), section "Idea 13 prior art
  (research-idea13-prior-art.md), 2026-11-09".
- Anything not confirmed on an opened page is marked **UNVERIFIED**, with
  the reason.
- The KataGo paper's own settings (fractions and playout caps) are given
  because they are published experimental parameters of a paper, needed
  to compare it with Fork's settings, which were fixed and measured before
  this search. No chess engine's search constant is recorded.

**Tags.**
- Every prior-art item below: **REFERENCE ONLY** (ideas, studied and
  cited, never copied).
- Engine code, nets and data from any project named here: **OFF-LIMITS**
  (research.md §1; data-policy.md: engine-labelled data is never Fork
  training data).
- Licences: Chess Programming Wiki text is CC BY-SA 3.0 (page footer,
  checked 2026-11-08 for research-boundary-refiner-prior-art.md). Papers are cited,
  not reused; their licences were not checked. Forum and blog posts belong
  to their authors and are cited, not quoted. Repositories named here are
  cited for their published prose only; their licences, where listed in
  sources.md, are for the record.

**Phase and component.** Phase 4, data generation (fork_datagen's split
search, `--save-percent`, `--unsaved-nodes`, `--check-nodes`) and the
publication plan for it. This file changes no engine code.

---

## 1. The idea being checked (Fork's own words, summarised)

In Fork's self-play data generation, every position not in check is
randomly either **saved** or **unsaved**. A saved position is searched with
the full node budget (20,000 nodes), its score is written as a training
target, and that search's move is played. An unsaved position gets a cheap
search (4,000 nodes) used only to choose the move and keep the game going;
its record carries a sentinel score that the trainer drops. Positions in
check get their own small budget (2,000 nodes) and are dropped by the
trainer anyway. The standing setting saves half of the positions not in
check. At the same rate of saved labels per second, the split played about
1.8 times as many games, and a net trained on the split data beat one
trained on unsplit data by +65.47 ± 12.90 Elo on [0, 5] at 8+0.08
(arm B against arm A, 2026-10-31; main's ideas.md 13 and
docs/history/phase-4/sprt-log.md). These are Fork's own results, quoted
from ideas.md, not prior art.

The questions: is this published under another name, and which published
schemes are related but different?

---

## 2. Classification

- **(a) same mechanism:** cheap moves that are not recorded, interleaved
  with expensive moves that are recorded, chosen per position at random,
  inside self-play.
- **(b) related, different:** a different selection rule or a different
  split of compute (random search depth, sampling which positions to
  write, relabelling a sample afterwards, budgets that change over
  training, adaptive budgets, and so on).
- **none:** checked; nothing relevant.

---

## 3. Items of class (a): the mechanism itself and its applications

### 3.1 KataGo's playout cap randomization (Wu, 2019; arXiv:1902.10565)

- **What it is (verified from the paper's full text).** In KataGo's
  self-play, a small random fraction of turns gets a full search, stopped
  when the tree reaches a large node cap; all other turns get a fast search
  with a much smaller cap. Only the full-search turns are recorded as
  training samples. On the fast turns the exploration settings (Dirichlet
  noise and the like) are switched off, so those moves are as strong as
  possible. The main run used a quarter of turns as full searches, with
  caps of 600 and 100 nodes at first, raised later in the run (v5, §3.1).
- **Why, in the paper's terms.** The game-outcome value target gets only
  one noisy sample per game, so value training wants many cheap games; the
  policy target needs a large search to differ usefully from the prior. The
  random split serves both: most moves are cheap, so more games finish, but
  most of the compute still goes to the recorded full searches.
- **Evidence in the paper.** Ablation runs at equal self-play cost
  (§5.2): the randomized cap beat every fixed cap tried (100 to 600
  playouts). The paper's summary table credits it with roughly a 1.37x
  training-time factor, approximate and from short runs.
- **Name history.** arXiv v1 (2019-02-27) calls it "playout cap
  oscillation" or "visit cap oscillation" (§6.1) and adds that on fast turns
  the search tree is kept and the small cap is applied to the whole tree;
  v5 (2020-11-09) calls it "playout cap randomization". v1 presents it as
  KataGo's own innovation and credits no earlier source for it. Which of
  v2 to v4 introduced the new name is **UNVERIFIED** (only v1 and v5 were
  read).
- **Relation to Fork's idea 13: (a), the same mechanism, and its source.**
  Idea 13 was taken from it (ideas.md 13 says so). The differences are of
  setting, not of mechanism: Fork's search is alpha-beta with fixed nodes,
  not MCTS; the recorded target is a search score (plus the game result)
  for an NNUE value net, not a policy distribution; half the positions are
  saved rather than a quarter; positions in check have their own budget;
  unsaved positions stay in the record stream with a sentinel score
  (viriformat cannot skip a ply); and the unsaved positions do not count
  towards Fork's score adjudication, which changed how games end (ideas.md
  13 records that the result covers the split "as implemented").
  The analogy carries over: in Fork, the game result is the per-game
  target that more games improve, and the search score plays the part of
  KataGo's policy target, the one that needs the full search.
- **Source:** https://arxiv.org/abs/1902.10565 (abstract page, submission
  history v1 to v5); full text of v5 (https://arxiv.org/pdf/1902.10565)
  and v1 (https://arxiv.org/pdf/1902.10565v1), PDFs downloaded to a
  temporary folder and converted to text locally (deleted after). Opened
  2026-11-09.
- **Verified** 2026-11-09. This resolves ideas.md 13's earlier UNVERIFIED
  note (the PDF could not be read on 2026-10-24). The CPW page on David J.
  Wu cites the paper and describes KataGo but does not describe the
  technique. Tag: **REFERENCE ONLY**.

### 3.2 Playout cap randomization applied in AlphaZero-style chess projects (2026)

Each of these applies 3.1 directly, by name, in chess with Monte Carlo tree
search and policy/value networks. None is an alpha-beta engine or NNUE
data generation.

- **slcz, "alphazero-style-chess"** (repository created 2026-09-22; the
  URL github.com/slcz/chess redirects to it). Its README says it uses
  KataGo's idea to keep self-play economical: a quarter of plies get a
  full search and are the only plies trained on, the rest a much smaller
  one. Class **(a)**. Source: the README via the GitHub API, opened
  2026-11-09. No licence is listed.
- **WGCodings, PeaZero** (a Rust project whose README says it is an
  experiment in having an LLM build a MuZero-style chess engine). Pull
  request 12, "pcr", merged 2026-10-20: a quarter of positions get a
  larger search and are used as value targets, the rest only move the
  game along. The description reports an OpenBench SPRT of +67.36 ± 18.53
  Elo on [0, 5] at 8+0.08 (940 games), which the linked OpenBench page
  (test 636) confirms. The author notes that training progress per step
  is usually a little slower. Class **(a)**, and the only chess result of
  the mechanism found with a measured gain before Fork's. Sources: the PR
  and README via the GitHub API, and the OpenBench page, opened
  2026-11-09. No licence is listed.
- **Bertil Braun, "Engineering Efficient Self-Play Chess: Search, Replay,
  and Throughput Under Limited Compute"**, arXiv:2609.37447 (v1,
  2026-09-27). An AlphaZero-style chess system trained on one eight-GPU
  node. Section 4.1.2 reports that a KataGo-inspired split (cheap searches
  on most moves, full searches on a random minority that alone became the
  main policy targets) was **not retained**: the author argues that chess
  games are shorter and their value target was already learning, so the
  split spent search on positions it then discarded, without showing that
  the extra games made up for the lost policy targets. The retained design
  searches every recorded move to a fixed cap that rises in stages. Class
  **(a), with a negative result** in chess MCTS. Source: arXiv API
  abstract and the HTML rendering (https://arxiv.org/html/2609.37447),
  opened 2026-11-09.
- **Ragu-123, nova-chess-rl ("NovaZero")** (README, 2026-10-22). Claims
  "playout cap randomization" with a fifth of moves at several times the
  simulations, described as aimed at "critical positions". Whether the
  choice is random and whether the cheap moves are left out of training
  is **UNVERIFIED** (the README does not say). Class **(a) or (b),
  unclear.**

### 3.3 Playout cap randomization in other games (examples)

- **cgreer, alpha-zero-boosted** (AlphaZero with gradient-boosted trees;
  Connect Four, Quoridor): the author wrote on Hacker News on 2020-06-22
  that he had implemented KataGo's playout cap randomization and found it
  much more efficient; in the same thread another user (jonath_laurent),
  writing about AlphaZero.jl, said it was on his to-do list. Class **(a)** (forum
  statement; the linked chart was not opened). Source:
  https://news.ycombinator.com/item?id=23600875, opened 2026-11-09.
- GitHub search results also show the name in projects for Magic: The
  Gathering drafting (adams-shaun/gorge PR 11, title only), hexagonal
  chess and Hex. Only titles were seen; not opened further.

These show that the mechanism is in general use in AlphaZero-style
projects. They add nothing beyond 3.1.

---

## 4. Items of class (b): related but different

### 4.1 Stockfish's `generate_training_data_nonpv` (Sopel97, December 2020)

- **What it is.** A data generator added to the NNUE "learner" fork of
  Stockfish (nodchip/Stockfish PR 264, "Add gensfen_nonpv", merged
  2020-12-24) and documented in official-stockfish/Stockfish's `tools`
  branch. Self-play games are played at a fixed node budget drawn between
  a minimum and a maximum, for exploration. A small random fraction of the
  positions **evaluated inside those searches** (not the game positions;
  1 in 100 by default) is kept, and the kept positions are later rescored
  with a separate fixed-depth search. An option removes positions in
  check or whose best move is a capture or promotion. The PR reports that
  a net trained on such data beat one trained on ordinary depth-4 data by
  about +26 Elo in a 1,000-game match, and notes the data compresses
  poorly. In the PR discussion, vondele suggested keeping only positions
  whose evaluation is near the alpha-beta window.
- **Relation: (b), and the nearest chess precedent found.** It shares the
  economics (cheap search moves every game forward; only a random sample
  gets a label search) but not the mechanism: every game move is cheap,
  the labelled positions come from inside search trees rather than from
  the game, and labelling is a second pass, not the search that plays the
  move. Whether the node budget is drawn per move or per game is
  **UNVERIFIED** (the documentation does not say).
- **Sources:** https://api.github.com/repos/nodchip/Stockfish/pulls/264
  and its comments (prose); `docs/generate_training_data_nonpv.md` on
  official-stockfish/Stockfish's `tools` branch (GitHub contents API).
  Opened 2026-11-09.
- **Verified** 2026-11-09. Tag: **REFERENCE ONLY** (code **OFF-LIMITS**).

### 4.2 Stockfish's `generate_training_data` (gensfen) options

- **What it is.** The `tools` branch documentation of the older generator:
  the search depth can be drawn per position from a range, a node limit can
  apply instead, positions are written only within a ply window, random
  moves are mixed in early, and the multi-PV search that picks those
  random moves has its own depth and node settings.
- **Relation: (b).** Random effort per position and a write window, but
  every searched position in the window is written; no cheap unrecorded
  moves.
- **Source:** `docs/generate_training_data.md`, `tools` branch, GitHub
  contents API, opened 2026-11-09. **Verified.** Tag: **REFERENCE ONLY**.

### 4.3 Play cheaply, then relabel a random sample (Wasp, 2023)

- **What it is.** John Stanback (Wasp) wrote on TalkChess (thread
  "Games for Training NNUE?", 2023-01-12) that he plays fast games, picks
  about a tenth of each game's positions at random, resolves each to a
  quiet position, and scores those with a fixed-node search of his latest
  version.
- **Relation: (b).** The same compute split as 4.1 (cheap play, an
  expensive label on a random sample), done in two passes; the label
  search does not choose the game's moves. In the same thread Andrew Grant
  reports that his best nets came from a moderate fixed node count per move
  and that doubling it lost Elo, and Ed Schröder replies; neither
  describes a split.
- **Source:** https://talkchess.com/viewtopic.php?t=81330&start=10, opened
  2026-11-09. **Verified** (the authors' own statements). Tag:
  **REFERENCE ONLY**.

### 4.4 "Sample only some positions" (Jon Dart, TalkChess, March 2021)

- **What it is.** In the "nnue-trainer" thread Dart suggests sampling only
  some positions per game instead of writing all of them, and notes that
  this raises the compute per position written. Ferdy replies by pointing
  to gensfen's random-move options.
- **Relation: (b).** Sampling which positions to write, with no cheaper
  search for the rest; the cost Dart mentions is the one idea 13's cheap
  search removes.
- **Source:** https://talkchess.com/viewtopic.php?t=76964, opened
  2026-11-09. **Verified** (forum). Tag: **REFERENCE ONLY**.

### 4.5 Lc0's KL-divergence stopping rule for training games (2019)

- **What it is.** Lc0 PR 721 (Tilps, merged 2019-02-10) adds an option to
  stop a search when the visit distribution has stopped changing much
  (measured by KL divergence over an interval) instead of at a fixed visit
  count, proposed for training games. PR 755 extends it to timed games and
  was not merged.
- **Relation: (b).** The budget varies per move by a convergence test, and
  every move is still recorded. No Lc0 issue or PR found by GitHub search
  mentions playout cap randomization (searches for "playout cap",
  "randomized visits" and "KataGo" in the LeelaChessZero organisation);
  one comment on issue 768 quotes the KataGo paper's reduced-visit play in
  decided games (4.6).
- **Sources:** PRs 721 and 755 and issue 768 via the GitHub API (prose),
  opened 2026-11-09. **Verified.** Lc0's Discord and blog were not searched
  for this: **UNVERIFIED** either way.

### 4.6 KataGo's reduced visits in decided games (same paper, Appendix D)

- **What it is.** Instead of resigning, KataGo lowers the visit cap
  towards the fast cap once the losing side's win rate has stayed very low
  for several turns, and records those positions with a reduced
  probability.
- **Relation: (b).** The budget falls by game state, not at random, and
  recording is thinned rather than switched off. A possible later step for
  Fork's score adjudication, noted for the write-up only.
- **Source:** as 3.1 (v5 Appendix D; v1 §6.2.1). **Verified** 2026-11-09.

### 4.7 Budget schedules and curricula in zero-knowledge training

- **MiniZero** (Wu et al., arXiv:2310.11305, abstract): "progressive
  simulation", a search budget that grows over the course of training.
  **(b)**: the budget changes across training, not across positions.
- **Braun (2609.37447), §6.1, "Late-game target poisoning":** an earlier design cut
  the search budget for late-game positions that were excluded from the
  training targets, and the author reports that it starved the model of
  endgame conversion examples until a dedicated full search was restored at
  the cut-off. **(b)**: cheap unrecorded moves chosen by game phase, not at
  random; a cautionary result relevant to Fork's unsaved positions (Fork
  saves at random across the whole game, so no phase is left without
  labels).
- **Björnsson, Jónsson and Jónsson, "Expediting Self-Play Learning in
  AlphaZero-Style Game-Playing Agents"**, ECAI 2023, FAIA 372, pp. 263-270,
  DOI 10.3233/FAIA230279 (abstract from the IOS Press page): self-play that
  first emphasises late game phases and extends to whole games as training
  goes on (Connect Four, Breakthrough). **(b)**. Its comparison with other
  speed-up strategies is in the full text, which was not opened (PDF link
  behind the publisher's page): whether it tests playout cap randomization
  is **UNVERIFIED**.
- **Go-Exploit** (Trudeau and Bowling, arXiv:2302.12359, abstract): starts
  self-play from an archive of states of interest, giving shorter games and
  more independent value targets, and compares itself with KataGo.
  **(b)**: more value targets per compute by a different route.
- Tag for all: **REFERENCE ONLY**.

### 4.8 A proposal for a checkers engine (brainwagon.org, 2026-05-28)

- **What it is.** Mark VandeWettering's post on his checkers engine
  "claudius" (alpha-beta search with a neural network) proposes labelling a
  subset of positions with a much deeper search while ordinary-depth play
  keeps the games moving, and says mixing two search times in self-play
  had gained Elo at small scale.
- **Relation: (b).** A proposal, not an implementation; in it the other
  positions keep their ordinary labels, so nothing is left unrecorded.
- **Source:** https://brainwagon.org/blog/2026_05_28_how_do_we_achieve_superhuman_performance,
  opened 2026-11-09. **Verified** (the author's own post). Tag:
  **REFERENCE ONLY**.

---

## 5. Checked, nothing relevant

- **Chess NNUE trainers and engines' public prose:** the READMEs of bullet
  (MIT), marlinflow (GPL-3.0), nnue-pytorch (GPL-3.0), Viridithas
  (AGPL-3.0; its history section describes its own self-play data and
  rescoring, no split), Stormphrax (GPL-3.0; soft-node options only) and
  Monty (AGPL-3.0; its datagen crate has no README, and its source was not
  opened). ChessCoach's README (GPL-3.0) lists KataGo-inspired ideas but
  not this one.
- **TalkChess datagen threads:** "How do NNUEs self train?" (t=83343),
  "Best practices for NNUE training data generation?" (t=83944) and
  "Generating original training data" (t=84811): fixed node budgets per
  move, random openings and adjudication; no split.
- **Chess Programming Wiki:** no KataGo page (HTTP 404; the wiki's title
  index has no entry for it); the pages Leela Chess Zero, NNUE, AlphaZero,
  Reinforcement Learning, Training an nnue and David J. Wu do not describe
  the technique.
- **Shogi:** the YaneuraOu wiki pages on evaluation-function learning and
  on Fukaura-ou training (its self-play command takes one fixed playout
  count; none of the options listed is a split); Tadao Yamaoka's dlshogi
  blog, searched for "Playout Cap" (no hits) and "KataGo" (the hits
  include a 2021-03-16 post that borrows KataGo's §3.2 idea for policy
  targets, not playout cap randomization).
- **Papers at abstract level:** MuZero (arXiv:1911.08265), EfficientZero
  (arXiv:2111.00210), Polygames (arXiv:2001.09832) and
  arXiv:2608.27757 (searchless chess fine-tuning): no such scheme in the
  abstracts. Their full texts were not read. Gumbel AlphaZero and Gumbel
  MuZero (MiniZero's abstract confirms they exist): the paper was not
  read. Its citation, recalled as Danihelka et al., ICLR 2022, is
  **UNVERIFIED**: the OpenReview page tried returned only a script shell
  and OpenReview's API refused the request (HTTP 403). Its content is
  **UNVERIFIED** too.

---

## 6. Summary table

| # | Source | Setting | What varies, and how | Recorded | Class |
|---|---|---|---|---|---|
| 3.1 | KataGo, arXiv:1902.10565 (2019) | Go, MCTS | full or fast search per turn, at random | full-search turns only | **(a)**, the source |
| 3.2 | slcz alphazero-style-chess (2026) | chess, MCTS | as 3.1 | full only | (a), application |
| 3.2 | PeaZero PR 12 (2026-10-20) | chess, MuZero-style MCTS | as 3.1; SPRT +67 Elo | full only | (a), application |
| 3.2 | Braun, arXiv:2609.37447 (2026) | chess, MCTS | as 3.1; not retained | full only | (a), negative |
| 3.2 | NovaZero README (2026) | chess, MCTS | deeper search on a fifth of moves | not stated | unclear, **UNVERIFIED** |
| 3.3 | alpha-zero-boosted (HN, 2020) | Connect Four, Quoridor | as 3.1 | as 3.1 | (a), application |
| 4.1 | Stockfish nonpv generator (2020) | chess, alpha-beta, NNUE | cheap games; random 1% of in-search positions rescored later | sample only | (b), nearest in chess |
| 4.2 | Stockfish gensfen docs | chess, alpha-beta | random depth per position; ply window | every position in window | (b) |
| 4.3 | Wasp (Stanback, 2023) | chess, alpha-beta, NNUE | fast games; random tenth rescored | sample only | (b) |
| 4.4 | Dart, TalkChess (2021) | chess | write a sample only | sample only | (b) |
| 4.5 | Lc0 PR 721 (2019) | chess, MCTS | budget by KL convergence | all | (b) |
| 4.6 | KataGo Appendix D | Go | lower cap in decided games | thinned | (b) |
| 4.7 | MiniZero; Braun's late-game cut; Björnsson et al.; Go-Exploit | various | budget over training; by game phase; curriculum; start states | various | (b) |
| 4.8 | brainwagon (2026) | checkers, alpha-beta | deeper labels on a subset (proposal) | all | (b) |

---

## 7. Verdict

**The mechanism is not new, and it is published under a name: KataGo's
playout cap randomization** (Wu 2019, called "playout/visit cap
oscillation" in the paper's first version). Fork took idea 13 from it, as
ideas.md 13 already records. AlphaZero-style chess projects have applied
it too: one reports a gain of the same size as Fork's on the same bounds
and time control (PeaZero, 2026-10-20, before Fork's experiment of
2026-10-31), and one paper reports that it did not help its chess MCTS
system (Braun, September 2026).

**Not found in the sources searched:** playout cap randomization applied
to an alpha-beta engine's NNUE data generation, where the recorded target
is the search score and the game result rather than a policy
distribution, with a controlled test at equal CPU of nets trained with and
without it. The nearest chess practice (4.1, 4.3) gets a similar compute
split a different way: every game move is searched cheaply and a random
sample is relabelled afterwards by a separate search, which does not play
the move.

**What this means for the publication plan (the owner decides).** The
write-up cannot present the split search as a new mechanism. An accurate
framing: "an application of KataGo's playout cap randomization to
alpha-beta NNUE data generation, with a measured result at equal CPU". The
evidence worth publishing is the measurement and its caveats (the arms also
differed in how games ended, ideas.md 13), the contrast with Braun's
negative chess MCTS result (a value-score target may benefit where a policy
target did not), and a comparison that has not been run: the split against
cheap play plus relabelling a random sample (4.1, 4.3) at equal compute.
Suggested wording: "We applied KataGo's playout cap randomization (Wu,
2019) to self-play data generation for an alpha-beta engine with an NNUE
evaluation ... We have not found an earlier report of it in this setting,
and would be glad to hear of one."

---

## 8. Limits of this search

- **Not searched:** Discord servers (Stockfish, Lc0, engine programming),
  the fishtest and OpenBench test databases beyond one test page, most
  TalkChess threads (only those reached by web search), Lc0's blog, and
  commit histories. Datagen settings that exist only in code were not read
  by rule, so an engine could use this split without saying so in prose.
- **Not read in full:** the Gumbel paper (page not readable), Björnsson et
  al. 2023 (full text behind the publisher's page), and the papers listed
  at abstract level in §5.
- **Chinese- and Japanese-language sources** were covered only through
  the YaneuraOu wiki and the dlshogi blog search.
- **Recommended before a post:** ask on TalkChess as a question ("is this
  known in alpha-beta datagen?"), and consider the relabelling comparison
  in §7 if the owner wants a stronger claim.
