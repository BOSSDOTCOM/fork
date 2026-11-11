# Ideas log

Candidate improvements, each with the evidence needed to adopt it.

## Fields

| Field | Meaning |
|---|---|
| **type** | **ELO**: a playing-strength change. It's measured by SPRT and sits behind a config flag until accepted. **TOOLING**: infrastructure measured by its own success metric. No flag needed. |
| **phase** | When the idea is scheduled. |
| **metric** | What decides success (SPRT result for ELO; the stated metric for TOOLING). |
| **status** | untested, in progress, accepted, rejected, inconclusive, parked (with the evidence and the date). |
| **sources** | References consulted. Every outside source is also logged in docs/ORIGINALITY.md. Ideas only, never code. |
| **runtime cost** | **none**: the shipped engine does no extra work (training- or test-side only). **possible**: the idea may cost speed in the engine itself. |
| **earliest phase** | The first phase whose infrastructure the idea needs. |

There were no entries before 2026-10-23, so no existing entries needed
marking as ELO. New ELO ideas use the same fields, with type ELO and the
name of their config flag.

**Rule (owner, 2026-10-24): any idea with "runtime cost: possible" must
report the nps change alongside its SPRT result** (bench nps from
`bench/ab.py`, bench node count unchanged or the change explained), so a
strength gain is never read without its speed price. The two fields were
added on 2026-10-24; ideas 1-12 predate them.

---

## 1. Formal verification with Z3

- **type:** TOOLING
- **idea:** Prove that bit tricks, attack lookups, and later the SIMD
  kernels match their scalar references for *all* inputs, not just the
  tested ones.
- **phase:** Phase 1 Part C for movegen and attack code; Phase 4 for every
  NNUE SIMD kernel.
- **metric:** the proofs pass and stay in the test suite.
- **status:** untested

## 2. Automated kernel search

- **type:** TOOLING
- **idea:** Generate and benchmark many variants of hot functions, and keep
  the fastest.
- **phase:** Phase 1 Part C (attack lookups, table layouts, move lists);
  Phase 4 (NNUE layers, accumulator updates).
- **metric:** a measured speed gain with the bench node count unchanged
  (bench/ab.py and bench/experiment.sh are the starting point).
- **status:** untested

## 3. Cross-engine idea mining

- **type:** TOOLING
- **idea:** Review open-source engines' commit histories and tested changes,
  plus Go and shogi engine research, for ideas already shown to gain Elo.
  Ideas only, never code. Each source is logged in docs/ORIGINALITY.md.
- **phase:** before the Phase 3 search work, repeated before Phases 4-6.
- **metric / output:** a ranked list of candidate ELO ideas, entered in this
  log.
- **status:** in progress: the Phase 3 idea mining was done (2026-10-24; KB search-techniques.md, ORIGINALITY.md); to be repeated before Phases 4-6.

## 4. TCEC game mining for blind spots

- **type:** TOOLING (feeds ELO work)
- **idea:** Analyze TCEC game archives for positions where top engines'
  evaluations swung sharply, and mark systematic misjudgments.
- **phase:** Phase 4 (training data for NNUE) and Phase 7 (steering toward
  opponents' weak position types).
- **metric / output:** a blind-spot position set with categories.
- **note:** TCEC games carry the playing engines' evaluations. Any position
  set used as *training data* must be rescored by Fork itself, so that no
  other engine's labels enter training (docs/kb/originality.md).
- **status:** untested

## 5. Efficient testing

- **type:** TOOLING
- **idea:** Pentanomial SPRT statistics, adaptive test bounds, and ranking
  ideas by expected gain and test cost before spending games.
- **phase:** starts in Phase 3 when SPRT testing begins; formalized in
  Phase 8.
- **metric:** games needed per accepted change.
- **status:** in progress: every Phase 3 SPRT is pentanomial (`tools/sprt.sh`, `tools/cloud/sprt_merge.py`).

## 6. On-demand analysis tools

- **type:** TOOLING
- **idea:** Each tool is built when its phase needs it:
  - search tree visualizer (Phase 3)
  - evaluation breakdown viewer (Phase 4)
  - per-game time usage plots (Phase 5)
  - thread scaling charts (Phase 6)
- **metric:** not specified by the owner. Proposed: each tool diagnoses at
  least one real issue in its phase.
- **status:** untested

## 7. TCEC-opening specialization

- **type:** ELO
- **flag:** none needed: testing use only (see the note).
- **idea:** Collect the openings TCEC used in past seasons from its
  published archives and use them as the opening set for all
  long-time-control confirmation testing, so that tests resemble the
  unbalanced positions Fork will actually be assigned.
- **phase:** Phase 8 (testing).
- **metric:** SPRT on TCEC openings.
- **note:**
  - **Testing only (review M6, 2026-10-24).** TCEC books are built with
    engine evaluations, and docs/kb/originality.md §3 lists books built from
    other engines' evaluations as off-limits for training. Using the book
    positions as NNUE training starts was the original second use of this
    idea; it is dropped unless the owner decides otherwise, in writing,
    before Phase 4.
  - Record which seasons' openings each test used.
- **status:** untested (testing use only)

## 8. Swiss-specific contempt

- **type:** ELO
- **flag:** a UCI style/contempt option (Phase 7), set per event and per
  opponent.
- **idea:** Win-seeking against lower-rated opponents; accepting draws
  against much stronger ones. It's driven by opponent rating when the
  tournament provides one (for example, the UCI `UCI_Opponent` option where
  the GUI sends it, or event configuration), and it's part of Fork's
  genuine evaluation and search preferences. It must never alter reported
  scores to trigger or avoid adjudication (the Phase 7 rule).
- **phase:** Phase 7.
- **metric:** SPRT in Swiss-like gauntlets: against weaker pinned opponents
  (score gain), and against stronger ones (no loss in score).
- **note:** whether TCEC's Swiss passes opponent identity or rating to
  engines is unverified. The current TCEC Swiss research (docs/kb, kb
  branch) should answer it.
- **status:** untested

## 9. Cache layout of Position and State (re-test with search nps)

- **type:** TOOLING (performance). Metric: search nps at a fixed bench, with
  bench unchanged. Microbenchmarks alone were inconclusive.
- **idea:** a smaller, cache-aligned per-ply State and Position, so make() copies
  fewer cache lines and Lazy SMP threads (Phase 6) each carry less.
- **measured 2026-10-23** (bench/ab.py, interleaved rounds, Ryzen 7600X3D;
  "min" = fastest sample, the most noise-robust estimate):
  - **v2** (State 128 B: narrowed fields, 5 check-square entries with King
    masked; Position alignas(64), bitboards first, uint8 mailbox):
    make/unmake -3..-6%, null move -6..-11%, gives_check +4..+8.5% slower,
    gcc is_pseudo_legal +6% slower.
  - **v3** (v2 with an int mailbox): gives_check still +9..+11% slower, so the
    mailbox is not the cause. gcc is_pseudo_legal back to neutral.
  - **v4** (v3 with a branchless King mask): gives_check worse (3.66 ns vs
    3.43 for v2). The v4 "uint8" binaries were mislabeled (actually v2); see
    the harness fix of that session (its notes were not kept).
  - **v5** (6 check-square entries, State 136 B, no State alignment, uint8
    mailbox): the gives_check regression is gone. make/unmake min -4..-5%,
    null move -5..-8%, gcc is_pseudo_legal min +5%. All verdicts "no
    significant difference" under the noise threshold.
  - Assembly (position.cpp at -O3 -march=native, both compilers): the uint8
    mailbox adds no conversion instructions (`movzx BYTE PTR` replaces
    `mov DWORD PTR`; instruction counts slightly lower).
- **decision (owner's rule):** not clearly better on both compilers, so main
  keeps its layout plus the uint8 mailbox (harmless, 192 fewer bytes per
  Position). v5 is kept as tag `archive/layout-exp` (c4531bd) for Phase 3
  re-testing with search nps.
- **per-ply check info (separate from the layout question):** Part A item 8
  made the State compute checkers, blockers/pinners and checking squares on
  every make(), and make/unmake became about 60% slower (before/after on
  2026-10-23, bench/ab.py min: +58% clang, +68% gcc). In Phase 3, measure
  with search nps whether eager check info pays off, and test a lazy variant
  that computes the check info only when it is first requested in a ply.
- **2026-10-24 (review H3 clean-room rewrite):** the per-type check squares
  are gone; direct checks are computed in `gives_check`, and the State keeps
  checkers, pinned and discovered-check candidates only (56 bytes). bench/ab.py:
  make/unmake -16% (clang and gcc), gives_check +76%. The lazy variant for
  pins (compute on first request in a ply) is still untested. layout-exp's v5
  no longer applies to the new State; re-derive any layout change from it.
- **pre-review vs after the clean-room rewrite** (2026-10-24, bench/ab.py,
  55f73c4 vs 4831f5a, release -march=native, 2 runs x 6 rounds per compiler):
  make/unmake is 16-19% faster (clang 25.2 -> 20.5 ns, gcc 26.9 -> 22.5 ns)
  and gives_check 70-80% slower (clang 3.09 -> 5.53 ns, gcc 2.04 -> 3.47 ns).
  Movegen, is_legal, is_pseudo_legal and attackers_to are within noise or
  faster. Each make saves about 4.5 ns and each gives_check call costs about
  1.4-2.4 ns more, so the trade pays only while search makes few gives_check
  calls per make.
- **Phase 3 task:** count gives_check calls per make() in real search
  (pruning and extension decisions may call it for moves that are never
  made). If the ratio approaches 2 or more, test the lazy per-ply
  check-squares variant: compute the direct-check squares on the first
  gives_check call in a ply and reuse them for that ply's remaining calls.
- **measured in Phase 3, Milestone B (2026-10-26)** with `bench/ab_search.py`
  (search nps, `fork bench` at depth 13, 12 interleaved rounds, core 4, WSL,
  clang 21; variants built from an experiment worktree off f919c01, none
  committed):
  - **gives_check ratio:** 0.646 calls per make (10.30M calls, 15.94M makes,
    FORK_SEARCH_STATS bench; 0.849 with deliverable 6's first values),
    almost all from futility pruning. Far below 2, so the lazy per-ply
    check-squares variant is not warranted.
  - **State 48 bytes** (bitboards first; castling, en passant square and
    captured piece as bytes; halfmove clock and game span stay 32-bit,
    since a FEN may carry a clock up to 10,000 that then grows): bench
    identical, median +0.4%, best +1.3%, noise threshold 3.0%: no
    significant difference.
  - **State alignas(64)**: bench identical, median -2.5%, best -2.4%,
    threshold 4.0%: no significant difference (leaning slower).
  - **History table int32** (instead of int16): bench identical, median
    -1.5%, best -0.5%, threshold 3.6%: no significant difference.
  - **TT 16-byte entries, 4 per bucket** (instead of 12-byte entries, 5 per
    bucket; padding only): bench 16,550,224 nodes (+0.06%, the capacity
    changes the tree), median -0.3%, best -0.2%, threshold 3.0%: no
    significant difference. Two TT tests assume 5 entries per bucket.
- **decision:** main keeps its layout (no candidate clears the noise rule).
  Revisit with Phase 6's threads (several State stacks per core) and Phase
  4's network, which change what the cache holds.
- **status:** tested in Phase 3, rejected for now
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 20):** layout changes only under the 1% cycles-per-node acceptance rule (X13), not as a standalone item.

## 10. Steer into TB-drawn 6-piece endings

- **type:** ELO
- **flag:** part of the Phase 7 TB-aware evaluation option (name set in
  Phase 7).
- **idea:** When worse, prefer lines that reach 6-piece endings the
  tablebases show as drawn, so that tablebase adjudication would end the
  game as a draw. Source: the brief (Phase 7 "TB-aware eval") and the plan.
- **phase:** Phase 7.
- **metric:** SPRT under TCEC conditions (`config/tcec.json`).
- **note:** the premise is TB adjudication at 6 pieces. The current TCEC
  rules have no tablebase adjudication (Leagues rules revision 6876,
  4 May 2025, removed it; Swiss 10 decisive games were played to mate). See
  docs/kb/competition.md on branch kb. A drawn TB ending is still a draw
  when played out, so a weaker form of the idea may survive; that is what
  the re-evaluation decides.
- **status:** re-evaluate (TB adjudication removed from the current rules)
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 20):** dropped from Phase 4: replaced by the structure-class calibration scale (R33, order step 17).

## 11. TB boundary training data

- **type:** ELO
- **flag:** none for the data; any net trained with it is a separate
  evaluator candidate behind the Phase 4 evaluator selection.
- **idea:** Training positions just above the tablebase boundary (7 pieces
  and up, converting into TB positions), labeled from Fork's own self-play
  with tablebase results, so the evaluation is accurate where games enter
  adjudication range. Source: the brief (Phase 7 TB-aware eval) and the plan.
- **phase:** Phase 4 (data) and Phase 7.
- **metric:** SPRT against the net trained without the extra data.
- **note:** the value of the boundary was tied to 6-piece TB adjudication,
  which the current rules no longer use (see idea 10). Engines now get
  7-man Syzygy in play (docs/kb/competition.md), so the relevant boundary
  may be 7-8 pieces instead. Tablebase-derived labels are not
  engine-generated data, but log the tablebase source in ORIGINALITY.md
  before use.
- **status:** re-evaluate (TB adjudication removed from the current rules)
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 17):** replaced by the depth-matched endgame-start slice (R32, starts of 8-16 pieces), deferred until item 8a's result.

## 12. Endgame conversion

- **type:** ELO
- **flag:** a UCI option for the conversion logic (name set in Phase 3).
- **idea:** Win won endgames reliably under the 50-move rule: DTZ-correct
  root probing (pick moves that keep the win while resetting the 50-move
  counter in time), WDL in search with correct handling of cursed wins and
  blessed losses, and halfmove-clock-aware scores so the search doesn't
  shuffle a won position into a 50-move draw.
- **phase:** Phase 3 (Syzygy integration) and Phase 7.
- **metric:** SPRT, plus a suite of won TB positions near the 50-move
  limit: the share converted when played out against a TB-perfect defender.
- **note:** matters more now that games are played to mate (no TB
  adjudication).
- **requirement (owner, 2026-10-23): probe 7-piece Syzygy correctly.**
  TCEC gives engines 7-man Syzygy (`SyzygyPath=/home/syzygy7`, every
  division; docs/kb/competition.md on branch kb). Design for 7 pieces from
  the start of Phase 3, and test with what is available locally:
  - piece limit taken from the tables actually found on `SyzygyPath`
    (3-7), never a hard-coded 5 or 6; a missing file is "no result", never
    an error or a wrong score;
  - large memory-mapped files, accessed with `madvise(MADV_RANDOM)` on Linux
    (TCEC asks this of 7-man users); probing must be thread-safe at 512
    threads, with initialization done once;
  - check whether the planned Fathom integration (DESIGN.md Phase 3)
    supports 7-piece tables, and how: **UNVERIFIED**, settle it before
    Phase 3 coding starts;
  - local tests use 3-4-5 (tools/install.sh), optionally 6; 7-piece paths
    are exercised with a few individual 7-man files if a small one can be
    downloaded (sizes **UNVERIFIED**), plus comparisons against the
    lichess tablebase API answers for 7-piece positions;
  - the DTZ, cursed-win and 50-move logic above is the same for 7 pieces;
    the suite of won positions near the 50-move limit includes 7-piece
    positions checked against that API.
- **status:** accepted (2026-10-27): deliverable 7 built it, and the mc-tables SPRT gave +17.5 ± 7.2 Elo at the cap (sprt-log); the conversion suite converted 100 of 100. The two UNVERIFIED notes above are settled (DESIGN.md §5.2 deliverable 7, ORIGINALITY.md).

## 13. Cheap/expensive self-play data mixing

- **type:** ELO (via the resulting net)
- **flag:** none in the engine; selected in the training-pipeline config
  (Phase 4), with a net trained with and without it.
- **idea:** Vary the search effort per position in self-play data
  generation: most positions get a cheap search that only moves the game
  along, a minority get a deep search, and only the deep searches are
  written as training targets. More games per CPU-hour, without diluting
  the labels with shallow evaluations. From KataGo's "playout cap
  randomization".
- **phase:** Phase 4.
- **metric:** SPRT of a net trained with the mixing against one trained
  without it, on the same self-play compute budget.
- **runtime cost:** none.
- **earliest phase:** Phase 4.
- **sources:** David J. Wu, "Accelerating Self-Play Learning in Go"
  (KataGo), arXiv:1902.10565. Title, author and abstract checked on
  2026-10-24; full text read on 2026-11-09 (v5 §3.1 "Playout Cap
  Randomization"; v1 §6.1 "Playout Cap Oscillation"): on a random fraction
  of turns a full search, capped at a large node count, is recorded for
  training; the other turns use a much smaller cap and are not recorded
  (KB research-idea13-prior-art.md §3.1).
- **status:** experiment done, H1 accepted (2026-10-31); approved (owner, 2026-10-30;
  DESIGN.md decisions log): fork_datagen's split search (`--save-percent`,
  `--unsaved-nodes`, `--check-nodes`, off by default); arm A is generation
  2's first 6 hours, arm B its own 6-hour part, both labelled by S-512 with
  the score adjudication and the same build, the split the only
  difference. **Arm A done** (2026-10-31): run g2 stopped at 12:28:41 AM
  EST after 21,738 s and sealed (data/manifests/g2.json): 390,227 games,
  35,592,241 positions (1,637 positions/s), every shard passing
  verify_games.py. The Lichess 2026-09 openings stream ran beside it for
  about 74 of its first 75 minutes (paused at 7:41:39 PM EST, until arm B
  ends); Windows CPU 91.1% with the stream, 85.3% without, WSL load1
  about 10.2 throughout (the manifest's part_end). **Arm B done**
  (2026-10-31): run g2b (seed 20261102, `--save-percent 50
  --unsaved-nodes 4000 --check-nodes 2000`) started at 1:16:54 AM EST and
  was stopped at 8:37:52 AM EST after 26,458 s, 1 h 21 min past its
  planned 6 hours (the stop was late, not a choice), and sealed
  (data/manifests/g2b.json): 864,114 games (32.7 games/s, arm A 18.0),
  79,693,421 records, of which 43,409,795 saved (1,641 per second, arm A
  1,637) and 36,283,626 unsaved (45.5%; positions in check are always
  saved, at 2,000 nodes, and a mate score always written); every shard
  passes verify_games.py. The openings stream stayed paused throughout:
  Windows CPU 84.7%, WSL load1 10.22, busy 83.0%, as arm A's paused
  stretch. So at the same rate of saved labels the split search played
  1.8 times as many games. Its games end differently: the score
  adjudication 42.3% (arm A 64.3%), a mate score 27.2% (13.5%), the
  tables 20.5% (10.9%), a rules draw 10.0% (11.2%); likely because
  unsaved positions do not count towards the 8 scores in a row, so the
  adjudication needs about twice the plies (not measured). So the arms
  differ in game endings as well as in the split, and the experiment's
  result reflects the split as implemented, not the split alone (owner,
  2026-10-31). Generation 2 keeps normal settings until the trained-net
  SPRT decides (owner, 2026-10-31). For the
  equal-budget comparison, arm B's training set is cut at arm A's
  21,738 s: each worker's first games in
  the share 21,738 / 26,458 of its total (fork_datagen's log, steady at
  3,011-3,012 records per second, gives 709,080 games at 21,720 s; the
  cut gives about 710,000).
  **Result (2026-10-31): H1 accepted.** Arm B's best net (i13b1) against
  arm A's best (i13a2) on [0, 5] at 8+0.08: +65.47 ± 12.90 Elo (nElo
  +88.52 ± 17.02) after 1,600 games (run 41236941019). Seed noise at the
  same conditions: arm A's seeds +3.3 ± 12.6, arm B's seeds -14.8 ± 12.4,
  so the gap between arms is several times the gap between seeds
  (docs/history/phase-4/sprt-log.md). The result covers the split as
  implemented, game endings included. Round 2's snapshot includes g2b,
  since the SPRT passed before it. Whether generation 2's next parts
  switch to the split settings is the owner's call.
  **Publication plan (owner, 2026-11-07):** once a prior-art search is done (is the split search, cheap
  unsaved moves interleaved with expensive saved ones in self-play, already published under another name;
  KataGo's playout-cap randomisation is the nearest known relative), write a reproduction guide in
  docs/research/ (mechanism, evidence, implementation, settings, costs and failures), then a TalkChess
  summary post and possibly an arXiv note, stating clearly that the idea came from an AI-assisted project.
  Anything published outside the repository needs the owner's go-ahead at the time.
  **Prior-art search done (2026-11-09, KB docs/kb/research-idea13-prior-art.md):** the mechanism is KataGo's
  playout cap randomization, already applied in AlphaZero-style chess (PeaZero PR 12, 2026-10-20, a gain of
  +67.36 ± 18.53 at 8+0.08 on its OpenBench; Braun 2026, arXiv:2609.37447, not retained). No application to
  alpha-beta NNUE data generation was found in the sources searched, so a write-up would present it as an
  application with a measured result, not a new mechanism (the owner decides the publication plan).

## 14. Auxiliary training targets

- **type:** ELO (via the resulting net)
- **flag:** none in the engine; a training-pipeline config switch (Phase 4).
- **idea:** Train the net to also predict extra quantities, for example
  game length or the material change over the next moves, through output
  heads used only during training and dropped from the inference net. The
  extra targets can shape the shared layers; the shipped net keeps only
  the evaluation output.
- **phase:** Phase 4.
- **metric:** SPRT of a net trained with the auxiliary heads against one
  trained without, same data. Also verify the shipped net is identical in
  size and speed (file size, layer shapes, bench nps with `bench/ab.py`).
- **runtime cost:** none (verify: the shipped net must be identical in
  size and speed).
- **earliest phase:** Phase 4.
- **sources:** KataGo (arXiv:1902.10565, as idea 13) is the motivating
  example; its full text (read 2026-11-09 for idea 13's prior-art search)
  adds an auxiliary target predicting the opponent's reply (§3.4), and its
  §5.2 ablation (NoVAux) removes the ownership and score targets (KB
  research-idea13-prior-art.md).
- **status:** untested

## 15. Adversarial robustness testing

- **type:** TOOLING
- **idea:** Search adversarially for Fork's own blind spots, not just
  opponents': for example, play a search-guided or learned adversary
  against Fork and collect the positions where Fork's evaluation or move
  choice fails against tablebases, deep-search consensus or the game
  result. Each confirmed blind spot becomes a regression position and a
  candidate training or tuning target.
- **phase:** Phase 7.
- **metric:** confirmed blind spots found per CPU-hour, and the share that
  stay fixed in later versions (regression suite).
- **runtime cost:** none.
- **earliest phase:** Phase 7.
- **sources:** Tony T. Wang, Adam Gleave, Tom Tseng et al., "Adversarial
  Policies Beat Superhuman Go AIs", arXiv:2211.00241 (abstract checked on
  2026-10-24): adversaries trained against KataGo won by inducing blunders
  rather than by playing well.
- **status:** untested

## 16. Tiny policy network for move ordering

- **type:** ELO
- **flag:** a UCI option enabling policy-based ordering (name set when it
  is built).
- **idea:** A very small policy net scores the moves at a node to improve
  move ordering (searching likely best moves first), alongside or instead
  of history heuristics.
- **phase:** parked until after Phase 8.
- **metric:** SPRT, reported together with the nps change (rule above):
  the ordering gain must outweigh the cost of evaluating the policy net.
- **runtime cost:** POSSIBLE: the net runs inside search, so it must beat
  its nps loss to pass SPRT.
- **earliest phase:** after Phase 8 (parked).
- **status:** parked until after Phase 8

## 17. Correction history shared across threads

- **type:** ELO
- **flag:** a build or tuning flag selecting shared or per-thread
  correction tables (name set in Phase 6).
- **idea:** Phase 3 keeps the static-eval correction tables (KB
  search-techniques.md T32) per thread. Share them between all search
  threads instead, with lockless access, so every thread learns from the
  whole tree. Published results show it neutral at 1 thread but gaining at
  high thread counts (Caissa 24fde49, 2024-12: +44 at 32 threads; Halogen
  #842, 2026-01: about +19 at 8 threads; KB §1 lesson 4). TCEC runs 512
  threads.
- **phase:** Phase 6.
- **metric:** SPRT at a high thread count (shared vs per-thread), at a long
  time control, reported with the nps change.
- **runtime cost:** possible (cache-line contention between threads).
- **earliest phase:** Phase 6 (needs T32 from Phase 3 and Lazy SMP).
- **sources:** docs/kb/search-techniques.md (branch kb), §1 and §3.23;
  engine references logged in ORIGINALITY.md (2026-10-24 rows).
- **status:** untested

## 18. Root moves ordered by previous-iteration node counts

- **type:** ELO
- **flag:** a SearchSwitches flag (name set when it is built).
- **idea:** Phase 3 orders root moves by move-to-front: after each root
  search the move that last raised alpha goes first and the others keep
  their order (DESIGN.md §5.2, implementation notes). Instead, order the
  moves after the first by the number of nodes their subtrees took in the
  previous iteration, largest first, on the reasoning that a move that was
  hard to refute is more likely to become the best.
- **phase:** Phase 3, tier 2 experiment (owner, 2026-10-24).
- **metric:** SPRT [0, 3] at STC, with an LTC confirmation (it changes the
  tree's shape), reported with the nps change.
- **runtime cost:** possible (a node count per root move).
- **earliest phase:** Phase 3 (after deliverable 2).
- **sources:** Fork's own idea, logged by the owner's request; no source
  consulted yet.
- **status:** untested

## 19. Explicit huge pages for the TT

- **type:** TOOLING (performance)
- **idea:** Fork's Hash is one 2 MiB-aligned block with
  `madvise(MADV_HUGEPAGE)` (transparent huge pages, a hint; DESIGN.md §5.1).
  Try explicit huge pages: `MAP_HUGETLB` with 2 MiB or 1 GiB pages on Linux
  (needs a reserved hugetlbfs pool), and large pages on Windows
  (`MEM_LARGE_PAGES`, needs the "Lock pages in memory" privilege), always
  with a silent fallback to the current path. With a 256 GiB TT, fewer TLB
  misses per probe could matter.
- **TCEC:** "Large pages: enabled automatically" (KB competition.md,
  verified 2026-10-23), which reads as transparent huge pages. Whether the
  servers reserve a hugetlbfs pool, and whether an engine may use
  `MAP_HUGETLB` or 1 GiB pages, is **UNVERIFIED**: add it to the TCEC
  Discord questions (KB competition.md) before relying on it.
- **phase:** Phase 6 (with the 256 GiB / NUMA work), measured earlier if
  cheap.
- **metric:** search nps with the A/B harness at a large Hash (bench
  unchanged), and `perf stat` dTLB misses.
- **runtime cost:** none in the search (allocation only); possible risk in
  allocation failure paths, which must keep the fallback.
- **earliest phase:** Phase 3 (the TT exists).
- **status:** untested

## 20. AVX-512 VNNI for Phase 4 inference

- **type:** TOOLING (performance)
- **idea:** Use AVX-512 VNNI (`vpdpbusd`, int8 dot products) in the NNUE
  layers where the network's quantization allows, with the scalar reference
  and equivalence tests the SIMD rules require (.claude/rules/simd.md);
  DESIGN.md §7 already plans an AVX-512 VNNI preset for Phase 4.
- **TCEC:** both servers are AVX-512 capable (KB); that their EPYC 9754 and
  9175F support AVX-512 VNNI is **UNVERIFIED** (check the CPU documentation
  in Phase 4). `update.sh` would then need a `FORK_ARCH` with VNNI, which
  TCEC's build must be told to use.
- **phase:** Phase 4.
- **metric:** inference speed (bench nps, A/B harness), bench identical
  across VNNI, AVX-512, AVX2 and scalar builds.
- **runtime cost:** none beyond the speed gain (inference only).
- **earliest phase:** Phase 4.
- **status:** untested

## 21. BOLT post-link optimization (optional, later)

- **type:** TOOLING (performance)
- **idea:** LLVM BOLT reorders a linked binary's code layout from a
  profile, on top of PGO and LTO. Optional, after the search and evaluation
  stabilize.
- **constraints (UNVERIFIED until checked):** TCEC builds Fork from source
  with `update.sh`, so BOLT would have to run inside that script on TCEC's
  machine (is `llvm-bolt` available there, and may the build run a profiling
  pass?); BOLT profiles normally come from hardware branch sampling (`perf`
  with LBR or AMD's equivalent), whose availability in WSL and on Zen 4 is
  to be checked; bench parity must hold, as BOLT changes layout only.
- **phase:** after Phase 8 (optional), or earlier only if TCEC's build
  allows it.
- **metric:** search nps (A/B harness), bench identical.
- **runtime cost:** none (layout only).
- **earliest phase:** Phase 3 (any time a stable binary exists).
- **status:** untested
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 20):** dropped from Phase 4: TCEC's build host is unlikely to have the tools, and PGO takes most of the gain.

## 22. Mate-aware late move pruning and reductions

- **type:** ELO
- **idea:** The deliverable 6 review found the default pruning delaying a
  mate in 3 in KQR v K (`8/8/5k2/8/8/8/5K2/RQ6 w - - 8 5`, from a random
  test game; the exact search finds mate in 5 plies at depth 6) until
  depth 11: at depth 10 it scores cp 1496 with every technique on, and
  finds the mate with LMR or LMP alone off (RFP, the null move, futility or
  SEE pruning off: still no mate). In K+Q+R v K every attacking move is
  quiet, so LMR shortens the mating line and LMP then drops the late quiet
  mating move. Candidates: no LMP or LMR when alpha or beta is already a
  mate score, or when the defending king has few squares; checks exempt
  from LMP. No wrong score is ever reported, only a later mate.
- **phase:** Phase 3 tier 2 (deliverable 9) or the removal round; measure
  with mate-suite solve counts (the kb-researcher's suite) and SPRT.
- **re-checked with tablebases** (owner, 2026-10-26, after deliverable 7):
  with today's search (Fork's own constants, the futile-node filter) the
  first mate appears at depth 8 without tables (a mate in 4) and at depth 9
  with the 3-4-5 tables, the mate in 3 by depth 14 in both. The tables do
  not fix this: they give win/draw/loss, not distance to mate, and probes
  need a zero halfmove clock (131 probes in that search). The case stays a
  search question.
- **metric:** SPRT; mate-suite solves at fixed nodes.
- **runtime cost:** a score test per pruning decision.
- **earliest phase:** Phase 3.
- **status:** untested

## 23. AI-driven discovery of search heuristics

Consolidated spec (owner, 2026-10-26; replaces the earlier fragments).

- **type:** TOOLING feeding ELO. Each discovered heuristic is its own ELO
  change behind its own switch; its runtime cost is reported with its SPRT
  (the rule above).

**Loop**
- An evolutionary loop (AlphaEvolve/FunSearch style): AI agents propose
  code changes, an automated evaluator scores them, and the best survive to
  seed the next generation.
- **Evolvable regions:** only delimited functions (pilot: the LMR formula
  only). Any candidate touching code outside them is rejected before
  building.
- **Residual mode (default):** candidates evolve a correction added to the
  current formula (final = base + correction), with its own strength
  coefficient for later SPSA tuning; a zero correction reproduces the
  baseline exactly. About 1 in 5 candidates may be full replacements, to
  keep the search open.
- **Diversity:** an island/MAP-Elites style population (e.g. axes: mean
  reduction and re-search rate).

**Agents**
- **Proposers:** 2 for the pilot, each with a distinct perspective and its
  own island (e.g. aggressive vs cautious); optionally a third reasoning
  from Fork's search statistics.
- **Explorer:** unconventional proposals that question standard
  assumptions and borrow from other fields; it uses the full-replacement
  share, and has its own protected island for a few generations before
  competing with the main population.
- **Critic:** reviews every proposal before building (determinism, the
  hot-path rules, resemblance to known engine formulas, proxy gaming);
  rejections are logged with reasons.
- **Analyst:** every N generations, summarizes what wins and loses and
  feeds the insights back to the proposers and the explorer.
- **Originality screener:** the existing originality-checker, for promoted
  survivors (constants and structure against known engines, since model
  memory can reproduce famous formulas).
- **Orchestrator:** a deterministic script, not an agent.
- All agents follow the clean-room rules; none sees another engine's
  source.

**Evaluator funnel**
1. **Gate:** build, perft, the minimax oracle with pruning off,
   determinism, the hot-path rules.
2. **Proxies:** best-move agreement and score error against Fork's own much
   deeper search, at equal node budgets, on a held-out self-play position
   set labeled by Fork's own search (data policy rule 1); nodes to depth
   only as a secondary signal, never alone. WAC and matetrack are excluded.
3. A short fast-game match against the baseline.
4. The full SPRT with gainer bounds, short then long time control per the
   LTC rule.

Survivors' constants are justified by the loop's log (DESIGN.md §8), then
tuned by SPSA.

**Pilot** (DESIGN.md §5.2, deliverable 8c)
- **Slot:** after Milestone C and the parameter table (8b), before tier 2
  (deliverable 9). Time box about two weeks. Target: the LMR formula only.
- **Prerequisites:** 8b done; the kb-researcher has verified the
  AlphaEvolve, FunSearch and MAP-Elites papers (cited in the KB and
  ORIGINALITY.md); run when weekly Claude capacity is fresh.
- **Metrics:** whether proxy rankings predict SPRT outcomes; the cost per
  accepted change (compute, games, tokens, session time); the gate-failure
  rate with and without the critic; the improvement rate against a
  single-proposer baseline; the explorer's survival rate and SPRT wins;
  residual against full-replacement results.
- **Ends with a stop for the owner's go/no-go decision.**
- **If go:** real campaigns in late Phase 4 (after the first strong network
  and the search re-validation), then a standing tool in the improvement
  pass; candidate future targets include pruning margins, history updates,
  move ordering and time management.
- **If no-go:** the loop is archived; its log and findings go into this
  file.

- **phase:** pilot as deliverable 8c (Phase 3); campaigns in late Phase 4
  and the improvement pass, if go.
- **metric:** the pilot metrics above; then SPRT for each heuristic.
- **sources:** verified from the primary sources by the kb-researcher
  (2026-10-26; KB research.md §9, ORIGINALITY.md): AlphaEvolve (Novikov et
  al., arXiv:2506.13131), FunSearch (Romera-Paredes et al., Nature 625,
  2024) and MAP-Elites (Mouret and Clune, arXiv:1504.04909). Not in any of
  them: the residual mode, the critic, analyst and explorer roles, any
  handling of noisy fitness (KB): those are this spec's own.
- **runtime cost:** possible: depends on the candidate (reported with each
  SPRT).
- **earliest phase:** Phase 3 (deliverable 8c).
- **status:** harness built (2026-10-26, `tools/evolve/`; DESIGN.md §5.2
  implementation notes): unit-tested and dry-run with stub agents; the
  evolution loop itself not started (owner). Since then: the validation
  run of 2026-10-27 (18 live proposals), the 4x position set and the
  held-out promotion check (DESIGN.md §5.2, deliverable 8c); the audit's
  gate, resume and pinning fixes are in (audit-1, merged 2026-10-28). The
  long run (40 generations) stays in **late Phase 4** (owner, 2026-10-28),
  after the first strong network and the search re-validation. Pilot scheduled
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 19):** the long run on the label-and-sweep proxy is replaced by a capped pilot with a game-based fitness (R38), after the LMR terms (§5.6 order step 20).
  **Restart plan (owner, 2026-11-09; plan only, still parked):** the first target is **the quiet move-ordering
  score** (how the history tables combine: the butterfly, reply, follow and take terms and their weights), with
  fitness = **nodes to a fixed depth on a large position set** (deterministic), a **held-out set** for confirmation,
  and a **guard that search results stay equivalent** (on a check set: the same best move, and the score within a
  declared tolerance); the winner then plays a **design R SPRT**. **Runner-up target:** the time-management
  formula, with a game-based fitness (time-management parameters stay out of SPSA, think tank decision 4).
  **Ordering pilot, 2026-11-09/10: NULL RESULT (owner, 2026-11-10; DESIGN.md decisions log).** 5 generations x 8
  candidates on the quiet ordering score (docs/research/idea23-pilot/, evolve/ordering-pilot 52a0fd6; 543,832 tokens
  of the 10 M cap; 0 gate failures, 0 guard refusals): the ordering formula is near-optimal for this fitness; the best
  candidate by the declared rule (#35: +0.39% nodes saved [-0.39, +1.19], held-out +1.43% [-0.33, +3.18], 85.6%
  equivalent) is within noise on both sets, so nothing goes to an SPRT. **The full replay was stopped before it
  finished by the owner's decision** (2026-11-10, about 9:00 AM EST, to free its CPU for the label-depth arms and the
  fix 1+2 pilot); **the pre-pilot tiny live run's full replay had reproduced every candidate exactly** (2026-11-09). **Idea 23 is parked again**; the time-management formula stays noted as the next possible target, **no
  run planned**.
- **Candidate region for the long run (owner, 2026-10-31):** a correction
  to the singular test's margin and depth (tier 2, T27), for example a
  dependence on the TT entry's depth deficit. The measured form (DESIGN.md
  "Search constants": 6 cp per ply, minimum depth 6, entry up to 3 plies
  shallower, test at d / 2) closely matches Stockfish 11's test as a whole
  (ORIGINALITY.md); an evolved correction is one route to a form of Fork's
  own.

## 24. TT victim policy under real table pressure

- **type:** ELO (switch `tt_age_blend`, UCI `UseTtAgeBlend` in tuning builds)
- **idea:** the blended victim policy (rank = depth − 2 plies per search of
  age, f140963) against the default lexicographic one (current search
  first, then depth). Its first SPRT (LTC 40+0.4, Hash 64 MB, 1 thread,
  [0, 3]) was stopped by the owner as inconclusive: +5.7 ± 13.8 Elo after
  1,400 games (2026-10-26, sprt-log.md). At 64 MB and one thread the table
  is rarely under pressure, so the victim choice seldom matters.
- **phase:** re-test after Phase 4's network (a different tree shape) and
  under Phase 6 conditions (large Hash, many threads), where table pressure
  differs.
- **metric:** SPRT [0, 3] at LTC, at Phase 6 Hash and thread counts.
- **runtime cost:** none measurable (one rank formula per replacement).
- **earliest phase:** Phase 6.
- **status:** inconclusive (Phase 3); default stays lexicographic

## 25. Queued tests: Hash size at LTC and time scaling

- **type:** TOOLING (measurement)
- **idea:** two tests queued by the owner (2026-10-26), skipped for now:
  1. **Hash 256 MB vs 16 MB at LTC** (40+0.4): how much a larger table is
     worth at Fork's current speed, which also informs idea 24.
  2. **Time-scaling mini-gauntlet at 60+0.6** against Stash 19.0 and
     WyldChess 1.51: whether Fork's score against fixed anchors holds,
     grows or shrinks with more time per move (Milestone B's gauntlet ran
     at 10+0.1).
- **phase:** when the machine is free (after deliverable 8, whose time
  management changes how longer games are played).
- **metric:** Elo difference with error bars for (1); score per anchor
  against the 10+0.1 gauntlet for (2).
- **runtime cost:** none (test-side only).
- **earliest phase:** Phase 3.
- **status:** queued

## 26. Upcoming repetition detection

- **type:** ELO (behind a switch)
- **idea:** detect that the side to move can force a repetition before it
  happens (owner, 2026-10-26, second external review), so a draw score is
  available one ply earlier, without searching the repeating moves. Built
  from the kb-researcher's clean-room description of the published method.
- **phase:** Phase 3 tier 2, or Phase 7 (tournament behaviour), whichever
  comes first after the description exists.
- **metric:** SPRT [0, 3].
- **runtime cost:** possible (a lookup per node).
- **earliest phase:** Phase 3.
- **status:** untested

## 27. Fifty-move-rule scaling of the evaluation in long endgames

- **type:** ELO (behind a switch)
- **idea:** scale the evaluation toward a draw as the fifty-move counter
  grows (owner, 2026-10-26, second external review), so the search prefers
  progress (captures, pawn moves) in long endgames instead of shuffling
  into a fifty-move draw. Tied to idea 12 (Syzygy: the DTZ and 50-move
  questions, and TCEC's long endgames): with tablebases the probe decides
  in the covered endings, and the scaling matters for the rest.
- **phase:** Phase 4 (the evaluation), after deliverable 7 (Syzygy).
- **metric:** SPRT [0, 3], plus the conversion suite (deliverable 7's).
- **runtime cost:** possible (one multiply per evaluation).
- **earliest phase:** Phase 4.
- **status:** untested

## 28. History malus balance

- **type:** ELO (a tunable parameter)
- **idea:** the quiet history's malus for the quiets tried before a cutoff
  is now the same size as the cutoff move's bonus. Make the ratio a
  parameter (owner, 2026-10-26, second external review) and let SPSA find
  it, with the removal round's UseHistoryMalus result as the reference.
- **phase:** a parameter-table entry still to add (8b was built without it); SPSA after Phase 4.
- **metric:** SPSA, then SPRT [0, 3] of the tuned value.
- **runtime cost:** none (a multiply where the malus is applied).
- **earliest phase:** Phase 3 (8b).
- **status:** untested
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 20):** becomes an SPSA parameter (the final retune by scaling class, R24), not an SPRT.

## 29. How often unconfirmed root fail highs hold

- **type:** TOOLING (measurement), possibly feeding ELO
- **idea:** the first external review's claim (a) proposed playing a root
  move that failed high when the search stops before its re-search ends.
  It was confirmed (626 of 34,254 node-limited searches over the bench
  positions and WAC stopped with a distinct fail high pending) and built
  (f0a9caf), but its SPRT rejected it: -14.6 +/- 10.8 Elo at STC after
  2,000 games, the 95% interval entirely below zero (owner, 2026-10-26;
  sprt-log.md rv-failhigh). The behaviour is reverted; the bookkeeping stays
  (Searcher::unresolved_fail_high).
  - **Measurement:** on the 626 sweep cases, re-search both moves (the
    pending fail high and the previous iteration's best) deeper, e.g. with
    `searchmoves` restricted to each, and count how often the fail high
    holds, by depth and by how far its re-search had got.
  - **Middle ground, if the data supports it:** play the fail high only
    when it has held through part of its re-search (some of its subtree
    searched with the wider window), or only by a margin.
- **Connection to deliverable 8:** the cleaner answer may be a time
  decision, not a move choice: when a stop would land during a root fail
  high's re-search, allow a bounded extension to finish it. Deliverable 8's
  stopping rules should consider that, measured by the same sweep.
- **phase:** the measurement after the current SPRT queue (it is a CPU job);
  any policy change is an SPRT on gainer bounds [0, 3].
- **metric:** the share of pending fail highs that hold at a deeper search;
  then SPRT.
- **runtime cost:** none for the measurement; a time extension costs time.
- **earliest phase:** Phase 3 (deliverable 8).
- **status:** measurement queued. **Run it before B-3 is revisited**
  (audit-1 B-3, re-searching a root fail high one ply shallower: reverted
  after its SPRT reached the cap undecided, +0.65 ± 3.56 Elo; sprt-log.md
  b3-shallow-fh). The audit meant this measurement to come first; B-3 ran
  without it.
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 20):** B-3 and the root fail-high fix are dropped from the re-validation queue: a timed search reaches the soft check only after a completed iteration, so no root fail high is pending there.

## 30. Keeping a stale TT entry that is still deeper once aged

- **type:** ELO (switch `use_tt_keep_deeper`, UCI `UseTtKeepDeeper` in
  tuning builds)
- **idea:** the position's own entry from an earlier search is kept against
  an inexact new result while its depth minus StaleDepthPerSearch plies per
  search of age still exceeds the new depth (audit-1, B-5; 808dd8a). Its
  LTC SPRT (40+0.4, Hash 64 MB, 1 thread, [0, 3]) was stopped by the owner
  as inconclusive, leaning negative: -5.1 +/- 10.1 Elo after 2,602 games
  (2026-10-28, sprt-log.md b5-keep-deeper). At 64 MB and one thread the
  table is rarely under pressure (as for idea 24).
- **phase:** Phase 6's TT tests, under large Hash and many threads.
- **metric:** SPRT [0, 3] at LTC, at Phase 6 Hash and thread counts.
- **runtime cost:** none measurable (one comparison per replacement of the
  position's own entry).
- **earliest phase:** Phase 6.
- **status:** inconclusive (Phase 3); off by default

## 31. Repetition of a position from before the root

- **type:** ELO (behind a switch)
- **idea:** inside the search a position that occurred once before scores
  as a draw (`repetition_count() >= 2`, searcher.cpp), also when that
  earlier occurrence is in the game before the root, a deliberate choice
  of deliverable 2 ("one repetition is enough inside the search"). But a
  position reached once in the game is not a draw yet: the opponent can
  deviate. So a losing Fork may steer for a "draw" the opponent declines,
  and a winning Fork avoids lines through old positions. Variant: three
  occurrences when the earlier ones are before the root, two when both are
  in the tree (audit-1, A1 suspicion 1).
- **phase:** tier 2, or Phase 7 (tournament behaviour).
- **metric:** SPRT [0, 3] at STC and LTC.
- **runtime cost:** none measurable (the same history walk).
- **earliest phase:** Phase 3.
- **status:** untested

## 32. Pruning guards for tablebase losses

- **type:** ELO (behind a switch)
- **idea:** late move pruning, futility and SEE pruning stop once the best
  score so far is a mate loss (`best <= -(MateScore - MaxPly)`), but go on
  when it is a tablebase loss, so at shallow non-PV nodes they may prune
  the quiet move that saves the draw. Guard with `is_tb_or_mate(best)`
  instead (audit-1, A1 suspicion 6). Heuristic: it matters only in table
  positions, which TCEC adjudicates.
- **phase:** with the next table work (Phase 8's 7-man measurements).
- **metric:** a table conversion and defence suite first, then SPRT
  [0, 3] with tables on both sides.
- **runtime cost:** none (one comparison).
- **earliest phase:** Phase 3.
- **status:** untested (measure first)

## 33. A shallow exact result replacing a deeper entry

- **type:** ELO (behind a switch)
- **idea:** `TransTable::deposit` keeps the position's own entry only
  against shallower inexact results, so an exact result from a shallow
  search (a quiescence PV, depth 0) overwrites a depth-N entry of the same
  search. That follows deliverable 3's spec, but may lose information.
  Variant: never replace a deeper entry of the same search (audit-1, A1
  suspicion 5).
- **phase:** tier 2, before the TT tests of Phase 6.
- **metric:** first a FORK_SEARCH_STATS counter of exact writes whose own
  entry was deeper (how often it happens); if frequent, SPRT [0, 3].
- **runtime cost:** none (one comparison per store).
- **earliest phase:** Phase 3.
- **status:** untested (measure first)

## 34. Reverse futility margin 40 cp per ply

- **type:** ELO (a search constant)
- **idea:** `RfpMargin` 40 instead of 80. Fork's own measurement (DESIGN.md,
  Search constants) bounds the margin from below: every M from 40 to 160
  keeps the share of RFP-prunable nodes whose search then fails low under
  1% at every depth 1-6, and 40 is the smallest such M. The data do not
  pick a value, so only games can.
- **phase:** audit-1 (2026-10-27, 304081e and 306bd9a); reverted to 80 on
  2026-10-28.
- **metric:** SPRT [0, 3] at STC, then LTC.
- **runtime cost:** none (a constant).
- **earliest phase:** Phase 3.
- **status:** **untested**. No SPRT decided it: the first STC run was
  superseded after 3,200 games (B-4 in both engines; +3.47 ± 9.61, LLR
  0.23), and its restart without B-4 was stopped in stage 0 when the owner
  accepted 40 without a test. The Phase D gauntlet then gave an
  **unfavorable but not conclusive** result: with 40, Fork scored 156.0
  of 357 games against Milestone C's 178.5 on the same games (43.7% vs
  50.0%, about -44 Elo, roughly two standard errors) before that gauntlet
  was stopped; with 80, all 1,200 games, it matched Milestone C (606.5 vs
  600.5; Ordo 2411.5 ± 22.5 against 2402.5 ± 23.3). Reverted to 80 by the
  owner's decision (sprt-log.md, history/phase-3/audit-1.md). **Revisit
  when the eval-dependent margins are retuned after Phase 4** (Quality
  control 6), with an SPRT.
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 20):** retired as a standalone test: RfpMargin is one point on the early SPSA's axis (R14, §5.6 order step 11).
  **2026-11-09: tuned by the R14 SPSA and adopted (owner):** RfpMargin 55 within the set (STC design R +37.93 ± 10.03, H1; DESIGN.md decisions log); the final retune widens its lower bound to about 30.

## 35. The bootstrap eval calls insufficient_material twice

- **type:** TOOLING (performance)
- **idea:** the bootstrap evaluation repeats the `insufficient_material`
  test that the search has already made at the node (12.4 M calls over
  the bench, about 0.2% of the profile; audit-1 P-5). Pass the result in,
  or drop the eval's own call.
- **phase:** only if the bootstrap eval is touched before Phase 4, whose
  network replaces it.
- **metric:** search nps with `bench/ab_search.py`, bench identical.
- **runtime cost:** none (a saving).
- **earliest phase:** Phase 3.
- **status:** untested

## 36. A SIMD pick in MoveSelector::take_next

- **type:** TOOLING (performance)
- **idea:** `take_next` is the largest single entry in the profile (20.5%
  at the audit-1 Phase D gate). Find the best remaining score with SIMD
  compares over the score array instead of a scalar scan (audit-1, A2
  speed suspicion).
- **phase:** after tier 2's history tables settle the selector's scores.
- **metric:** search nps with `bench/ab_search.py`, bench identical; the
  same move order as a scalar reference, by an equivalence test.
- **runtime cost:** none if it pays; report the maintenance cost first
  (Performance doctrine).
- **earliest phase:** Phase 3.
- **status:** untested
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 20):** closed: +1.0% in speed sprint round 2, not kept; C4 absorbed the gain.

## 37. A cache-friendlier MoveList and PlyFrame layout

- **type:** TOOLING (performance)
- **idea:** lay out the move list and the per-ply frame so that a node's
  hot fields share cache lines (audit-1, A2 speed suspicion).
- **phase:** with tier 2's PlyFrame changes (F-13, F-17/F-18), so the
  layout is settled once.
- **metric:** search nps with `bench/ab_search.py` and fork_micro, bench
  identical; `static_assert(sizeof(PlyFrame) <= 2688)` updated with it.
- **runtime cost:** none if it pays.
- **earliest phase:** Phase 3.
- **status:** untested
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 20):** layout changes only under the 1% cycles-per-node acceptance rule (X13), not as a standalone item.

## 38. Phase-end fuzzing on GitHub

- **type:** TOOLING
- **idea:** a manually triggered workflow (`workflow_dispatch`) that
  builds the clang-fuzz preset and runs each fuzz target with the
  plateau rule (`tools/fuzz/run_fuzz.py --max-seconds 3600
  --plateau-seconds 1200`), one job per target, then minimizes each run's
  corpus into the committed seeds (libFuzzer `-merge=1`) and uploads the
  coverage-adding inputs and any crash artifacts. Phase-end fuzzing then no
  longer uses the local machine: at the Phase 3 end, the local run of
  fuzz_moves was killed when the shared machine ran low on memory (owner,
  2026-10-28).
- **phase:** Phase 4 backlog (owner, 2026-10-28), ready before the Phase 4
  phase end.
- **metric:** each target's runs, coverage and plateau verdict as the
  local run reports them; the job fails on a crash artifact.
- **runtime cost:** none for the engine; hosted runners only.
- **earliest phase:** Phase 4.
- **status:** queued

## 39. Quiescence delta pruning

- **type:** ELO (switch `use_qs_delta`, branch exp/qs-delta)
- **idea:** in the quiescence search, skip a capture (not a promotion,
  side not in check, both sides with a piece) when stand-pat plus the
  captured piece's value plus QuiesceGainSlack (150 cp) cannot reach
  alpha, scoring it as that bound (fail-soft); tier 2 step 0 (KB
  search-techniques.md §3.27, T25's per-move form).
- **phase:** Phase 4 tier 2; revisit in the post-network re-validation
  (§5.2 Quality control 6), with the margin retuned for the network's
  centipawns (150 was read off a bench curve measured with the bootstrap
  evaluation's search, DESIGN.md decisions log 2026-10-29).
- **metric:** SPRT [0, 3] at STC, then LTC; the nps change beside it.
- **runtime cost:** possible (one comparison per quiescence capture; it
  saves nodes: bench 14,952,431 against 15,453,694). The nps change was
  not measured.
- **earliest phase:** Phase 3.
- **status:** **inconclusive** (2026-10-30, owner): against B0r1, -0.40
  ± 2.93 Elo (nElo -0.56 ± 4.13) after 27,200 games, LLR -1.39 on
  [0, 3], stopped undecided (history/phase-4/sprt-log.md). Kept off;
  exp/qs-delta keeps the code for the re-validation.

## 40. Structure System

- **type:** ELO, one flag per layer (names set at build time, each
  screened).
- **idea** (owner, 2026-11-02; one integrated idea, plan only; there were
  no earlier "Structure focus" entries in this file, any branch or the KB
  to replace): five layers about pawn structure, each able to stand on its
  own if a later one fails.
  - **L1 Knowledge:** a small learned network on pawns and kings only,
    its output cached by `pawn_structure_key` and added to the main
    network's evaluation.
    **First step (owner, 2026-11-05): pawn-pair inputs in the main
    network** (idea 41's architecture; KB nnue-inputs.md §2): structure
    knowledge learned inside the main network before any separate one.
  - **L2 Memory:** the pawn correction table (the pawn drift table, T32,
    in progress: its LTC SPRT started 2026-11-02) and the pawn-structure
    history (T12).
  - **L3 Direction:** a root-only planner: a deep search over pawns and
    kings, scored by L1's network, that produces a target structure and
    breaks near-ties between root moves toward it.
  - **L4 Teaching:** for the main network's training, a higher weight on
    the game result, a long-horizon auxiliary target, and the planner's
    verdicts as a further auxiliary target.
  - **L5 Proof:** a held-out strategic test set (positions decided by
    their structure, each verified by deep search), plus SPRTs and
    gauntlets.
- **gates, before any building:** measure how often root moves are near
  ties (whether L3 has anything to decide), and whether structures L1
  rates highly correlate with results in Fork's own games (whether L1's
  signal is real). Then build L2, L1, L3, L4, in that order, each with its
  own SPRT.
- **phase:** Phase 4, after the current tier-2 queue (DESIGN.md decisions
  log, 2026-11-02).
- **metric:** the two gates' measurements first (rules fixed before they
  run); then an SPRT per layer (L4 through the networks' own promotion
  tests), L5's test set and the gauntlet.
- **runtime cost:** possible (L1 evaluates a second network, mostly from
  its cache; L3 spends root time; L2's table is measured with its SPRT).
- **sources:** the owner's design; Fork's own KB descriptions (T12, T32);
  clean-room design throughout, every name and constant screened, every
  outside source logged in ORIGINALITY.md.
- **earliest phase:** Phase 4 (the pawn structure key exists since
  2026-11-02, branch tier2/drift).
- **status:** untested (planned 2026-11-02); L2's pawn table in progress.
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 20):** **L1 (the separate pawn-and-king network) and L2 (the pawn drift table) dropped; L3 (the root planner) parked**, kept here; L4 is handled by the decisive-share pilot and the result-weight arm (X11, R27); L5 becomes the blind-spot suite (X14).
- **L1's first step, S512+PP: speed** (branch nets/s512pp, not pushed;
  every number a quiet-machine median ratio to S512r2's nps by the
  identical-tree method: release builds whose net is S512r2's weights with
  every link weight zero, so bench is S512r2's 14180299, in interleaved
  bench rounds with the order rotated each round; the gate to train is
  0.90, the goal 0.95, DESIGN.md §5.4):
  - the links in a 32-bit accumulator (cab0114) 0.666; **in the main int16
    sums** (399a43b, with the 96-link bound) 0.787; plus the pawn-change
    flag (4ef9172) 0.784 (16 rounds, 2026-11-06).
  - **the changed-pair search in one tight pass** (9e04b4a: both sides'
    partners in one loop, the side read branch-free, constexpr tables
    with both orders of a pair): **0.818** (+4.3% over 4ef9172; 0.807 in a
    second 12-round session). Kept.
  - the pawn structure key in make/unmake (8851d34, tier2/drift's) 0.813;
    **a cache of each structure's link sum** keyed by it and checked
    against the pawns (1,024 slots of 1 KB per perspective and flip, per
    thread): without refills 0.791 (19.7% hits: a miss left the subtree
    uncached), with the parent's sum refilled on a miss 0.809 (61.7% hits
    in bench), 4,096 slots 0.824 (71.4% hits). No gain over the tight pass
    alone, so not kept (the owner's rule for the size: within the 3% noise
    rule, the smaller); the TT stall (perf, `TtEntry::bound`) varied from 5
    to 45 ns per node between repeated runs of the same build, with no
    consistent difference between 1,024 and 4,096 slots (three runs each).
    Archived on archive/s512pp-structure-cache.
  - **prefetch at make-move** on the cache: the cache slots 0.798, the
    piece rows 0.774, both 0.776: slower, not kept.
  - **fewer pairs with the tight pass:** links only between pawns at most
    one rank apart (R = 1) **0.895** (rounds 0.873-0.915), R = 2 0.859
    (12 rounds; R = 1 without the tight pass 0.860). R = 1 is just below
    the 0.90 gate; the full design is well below it. Earlier
    (2026-11-05/06, before the tight pass): 8-bit link rows, constexpr
    tables, the changes found at the push and their rows prefetched did
    not help (archive/s512pp-speed-switches); perf stat put the extra cost
    in instructions (the pair search about 200 per node), with branch
    misses about 20% of the extra cycles.
  - **not trained** (below the gate).

## 41. S-512 with Fork's own threat and pawn-pair inputs

- **type:** ELO (a network architecture: an entry like the bake-off's;
  its name and every new identifier screened at build time).
- **idea** (owner, 2026-11-05; replaces the S512+X plan): S-512 plus two
  input families of Fork's own design, from the concepts in the KB only
  (nnue-inputs.md §1-2, no engine's indexing or constants): threat inputs
  (attacker-victim pairs, with Fork's own redundancy removal: dropping
  pairs implied by others, mutual duplicates and impossible pairs) and
  pawn-pair inputs (pairs of pawns describing the structure's geometry; the
  first step of idea 40's L1).
- **phase:** Phase 4.
- **metric:** as the bake-off's entries: trained on the current snapshot,
  a fixed-node screen first, then an STC SPRT against the default network.
- **runtime cost:** possible (larger first layer, incremental threat
  updates; nps reported with the SPRT).
- **sources:** Fork KB nnue-inputs.md §1-2 (kb 962f1ab, 5cd96c3) and the
  sources it lists (ORIGINALITY.md, 2026-11-05).
- **earliest phase:** Phase 4.
- **status:** built on nets/s512cl (uncommitted engine code; trainer and reference committed), **held by the speed gate** (DESIGN.md §5.4, owner, 2026-11-05): not trained until it keeps 0.90 of the default's nps.
- **Speed, measured 2026-11-05** (quiet machine, every other CPU job suspended; release builds; a synthetic architecture-7 net, whose weights do not change the evaluation's cost):
  - fixed time (`go movetime 10000`, 6 bench positions, interleaved, Hash 16, 1 thread): S512cl median 680,114 nps, S512r2 3,591,160; per position **0.195** (0.095 to 0.475). Nodes reached on the start position: 3,405,824 (depth 14, seldepth 45) against 22,959,373 (depth 20, seldepth 32, stopped at 6.3 s); the synthetic net also deepens the quiescence lines, but the nps gap is the evaluation's cost, not the tree.
  - profile (perf, cpu-clock, Linux clang 21 RelWithDebInfo, the start position, 10 s): `sum_rows_saturated` 65.5%, `contact_inputs` with its helpers 16.2%: **82% of the time is the contact and link inputs, which are recomputed and summed from scratch at every evaluation**, not updated on make and unmake. S512r2's profile is led by its incremental accumulator update (17.6%) and the output layer (15.9%).
  - per-move change (200 g3s1 games, 37,720 perspective updates): 5.48 contact and link inputs change per move on average (contacts 4.20, links 1.28; p99 14 and 11), against 26.5 active (p99 66); a frame change (full refresh) in 452 updates.
  - storage: every first-layer row int16 (52,672 rows x 512 = 53.9 MB of the 53,953,760-byte file; the output layer 16 KB). Trained first-layer weights at scale 255 fit int8 for 98.1% (S512r2's piece rows) and 99.37% (S512+X's exposure rows, new inputs trained from zero; p99.9 215, max 471): 8-bit contact and link rows need clipping-aware training (QAT, idea 44) or a smaller scale; they would halve those rows to 26.6 MB.
  - cache: S512r2's first layer is 786 KB (within one core's 1 MB L2 on this machine); S512cl's table is 53.9 MB (27.4 MB with int8 contact rows), within this Ryzen 7600X3D's 96 MB L3 but larger than the L3 of most CPUs (TCEC's hardware: UNVERIFIED here). Rows read per evaluation now: about 27 per perspective (27 KB each side); incremental: about 5.5 per perspective per move.
  - **estimate, UNVERIFIED** (from the profile shares, not measured): incremental contact updates with the feature search reduced to the squares a move touches would bring S512cl to roughly 0.5-0.6 of S512r2's nps; the gate (0.90) leaves room for about 1-2 extra row updates per move, so the design also needs far fewer active inputs (or cheaper ones) to pass.

## 42. Continuation histories as inputs to the LMR history term

- **type:** ELO (flags set at build time).
- **idea** (owner, 2026-11-05): the LMR history term reads continuation
  histories as inputs. Note: the term as built (T16, `use_lmr_history`)
  already read the quiet ordering score, which sums the butterfly history
  and the reply and follow tables (1- and 2-ply continuations); it failed
  its STC SPRT at its measured divisor (H0, -10.81 +/- 5.01 Elo,
  2026-11-05). The plan is therefore a new form: each table as its own
  input with its own weight, and deeper continuations, each measured
  before its SPRT (KB search-techniques.md §3.36, T58, which has an SPRT
  plan step by step).
  **The LMR history term's follow-up** (owner, 2026-11-05): measured the
  same way as the term was (tools/lmr_history_measure.py's method: the
  25 M-node labels, both budgets, a rule and a wide grid declared before
  the runs), then its SPRT.
- **phase:** Phase 4.
- **metric:** a measurement with a pre-declared rule, then an STC SPRT.
- **runtime cost:** possible (small).
- **sources:** Fork KB §3.36 (kb 5fac98e) and its sources (ORIGINALITY.md).
- **earliest phase:** Phase 4.
- **status:** untested (planned 2026-11-05).
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 11):** folded into the round-once LMR step (R20) as its variant, run only if the centred history term passes; no longer §5.6's item 8.

## 43. Fractional depth

- **type:** TOOLING first (a search refactor with bench unchanged at the
  whole-ply equivalent), then ELO for what it enables.
- **idea** (owner, 2026-11-05): depth in sub-ply units, so reductions and
  extensions can be fractional (KB §3.35, T57: units, TT depth and its
  comparisons, thresholds, extensions), done **before the SPSA retuning**
  so the tuner sees smooth parameters.
- **phase:** Phase 4, before the post-network retune.
- **metric:** the refactor: bench node count and signature unchanged at the
  whole-ply setting, the full check; then SPRTs of the fractional uses.
- **runtime cost:** none for the refactor itself (to be confirmed with
  bench/ab.py).
- **sources:** Fork KB §3.35 (kb 024fb9e) and its sources (ORIGINALITY.md).
- **earliest phase:** Phase 4.
- **status:** untested (planned 2026-11-05); design below (owner, 2026-11-05:
  plan only, no code yet).
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 20):** shrunk to round-once LMR arithmetic (R20); the full refactor (level 2) is out of Phase 4 and no longer precedes the SPSA retune.
- **Design** (Fork's own, from the KB entry's concepts):
  - **Unit:** depth is held in units of 1/64 ply (`OnePly = 64`): a power
    of two, fine enough for SPSA to move a reduction in small steps
    (Fork's LMR table already computes its value in fixed point before the
    final division to whole plies), and far inside int32 at MaxPly (250 x
    64 = 16,000).
  - **What stays whole plies:** the TT stores depth / OnePly, rounded down,
    in its existing byte (the entry layout and its replacement unchanged;
    the KB's TT-sharing pitfall avoided, and a cutoff still needs a stored
    depth of at least the node's whole plies, so it stays conservative);
    the UCI `depth` the engine reports and `go depth N` (N x OnePly); the
    iteration counter; the history bonus by depth (whole plies until a
    measurement says otherwise); every depth threshold of the parameter
    table (`RfpMaxDepth` and the like stay in plies, compared as
    depth <= X x OnePly).
  - **Per-ply formulas** (RFP's and futility's margins, the singular test's
    margin, the null move's depth) read depth / OnePly while the uses are
    unconverted, so they compute exactly what they do now.
  - **The first fractional uses, in order, each behind its own switch,
    measured with a rule declared before its runs and then SPRTed:** (1) the
    base LMR reduction in units (the table's value without its final
    rounding; the KB's strongest evidence is fractional LMR); (2) the LMR
    adjustments as fractional amounts (the check relief, the cut-node and
    PV-trace steps, idea 42's continuation terms; the cut-node step is
    live at one whole ply since 2026-11-11, STC +6.02 ± 3.67 and LTC
    +9.75 ± 5.14, so its fractional form is measured against that); (3) the null move's depth;
    (4) extensions (the singular extension's +1 as a measured fraction).
- **Conversion plan, behaviour identical until each use is measured:**
  1. One refactor: negamax's depth and every child depth in units
     (depth - OnePly + extension x OnePly - reduction x OnePly), the
     quiescence search below one ply, thresholds and formulas through the
     whole-ply reads above. Every depth stays a multiple of OnePly, so
     **bench is unchanged, node count and signature**, and so is every test;
     the full check and bench/ab.py (no slowdown beyond the noise floor)
     confirm it before the commit.
  2. Tests added: a randomized check that the refactored search equals the
     whole-ply one node for node over the bench positions at several depths
     (both builds kept for the comparison during the change); the TT depth
     rounding; `go depth` and the reported depth.
  3. Each fractional use then lands as its own switch, off: bench
     unchanged until a switch is turned on after its measurement and SPRT,
     when the reference is recomputed in that commit.
  4. Timing: steps 1-3 for the first use (fractional LMR) come **before the
     post-network SPSA retune**, so the tuner sees the smooth parameters.
- **Pitfalls kept in view** (KB §3.35): rounding at every threshold (a node
  at 5.5 plies counts as 5 for a whole-ply limit unless a use says
  otherwise), TT depth rounding, and results that depend on time control
  (each use's SPRT at STC, and LTC where the rules ask).

## 44. Quantization-aware training

- **type:** TOOLING (the training pipeline), measured through the networks
  it trains.
- **idea** (owner, 2026-11-05): QAT in Fork's training pipeline (KB
  nnue-design.md §5.6: simulated rounding and clipping in training,
  straight-through gradients), so the trained float network and its
  integer form agree; small for the all-int16 S-512 family, more for later
  int8 layers.
- **phase:** Phase 4.
- **metric:** the quantised network's loss and its parity against the float
  network, then the network's promotion test.
- **runtime cost:** none (training only).
- **sources:** Fork KB nnue-design.md §5.6 (kb 02912f5) and its sources
  (ORIGINALITY.md).
- **earliest phase:** Phase 4.
- **status:** in progress: built behind an option, not yet run (2026-11-05).
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 20):** the validation session is retired; `--qat` stays for int8 designs; adaptive rounding of the output layer (R25) instead.
- **Built** (branch nets/s512cl, tools/train): `fork-train --qat` (train,
  eval, check; the S-512 family: S-512, H-512, S512+X, S512cl; refused for
  the others): the forward pass uses each weight and bias rounded to the
  grid of Fork's integer file (bullet's `faux_quantise`: 255 for the first
  layer, 64 for the output weights, 255 x 64 for their biases; half away
  from zero, as the save list rounds), the gradient passed through
  unchanged. Rounding the weights is the whole of Fork's quantization for
  these architectures (the accumulator is an exact sum of integer weights;
  the activation clips in integer units), so the QAT loss is the integer
  network's apart from the output layer's truncating divisions. The saved
  file is unchanged. Checked: the graphs build and their save lists match
  (fork-train check, S512 and S512cl, with and without --qat); the CPU
  build cannot run a graph, so the first run is on Kaggle.
- **Validation run, planned for Kaggle** (one session, two GPUs, after the
  S512cl training): S-512 warm-started from S512r2 on g2s1 + g3s1, 40
  superbatches at a low learning rate, runs A1 and A2 (seeds 1, 2) without
  and B1 and B2 with `--qat`. Each final net is then measured both ways with
  `--superbatches 0` (the initial validation loss of the float graph and of
  the QAT graph, the latter being the quantized net's). The rule, declared
  now: QAT is worth keeping if both B runs' quantized losses are below both A
  runs' by more than the larger of the two pairs' seed spreads; then a fixed-node match of the
  two quantized nets decides whether it enters the training settings.

## 45. Simple endings: a tablebase-labelled data slice, a standing endgame check, conversion

- **type:** ELO (the data slice), TOOLING (the check and the conversion test).
- **idea** (owner, 2026-11-05; put on hold the same day; **lifted 2026-11-06**: the slice and the acceptance test go with the next snapshot): three parts.
  1. **Endgame slice** for the next training snapshot: random legal
     positions of at most 5 pieces (KRK, KQK, KPK and the common 4-5 piece
     endings), labelled by their Syzygy WDL, a small fixed share of the
     data, so the nets learn endings that the games themselves end at
     (adjudication at table entry keeps them out of the data).
  2. **A standing acceptance test** with targets, reported for every new
     net: the KPK/KQK/KRK check below, on a committed position set.
  3. **A conversion test** without tables: does Fork mate from a won simple
     ending before the fifty-move rule?
- **why:** the endgame check (tools/nnue/endgame_check.py: 900 quiet random
  KPK, KQK and KRK positions, Syzygy-verified; a won position misjudged
  below +100 cp, a lost one above -100, a drawn one beyond +-200, declared
  before the run) found S512r2 misjudging 249 (27.7%), S512r3 329 (36.6%),
  S512+X 307 (34.1%); KQK S512r2 0 of 300, S512r3 41, S512+X 28; KRK all
  badly (S512r2 223 of 300, S512r3 264, S512+X 257). The retrained nets
  lost KQK and fail network-dependent tests (K+P v K promotion at depth 1,
  K+R v K mate in 2 at depth 4).
- **found so far** (2026-11-05):
  - conversion, KRK, S512r2 (the default build, bench 14180299), 200 ms
    per move, no tables, Hash 16, 1 thread, Fork for both sides, 20 won
    starts (seed 20261105): 17 mated (mean 15.6 moves, max 39), **3 drawn
    by the fifty-move rule** (starts with DTZ 27, 17 and 29). KQK was
    started and stopped when the work was put on hold.
  - the trainer's target is (1 - w) sigmoid(score / S) + w result, so the
    slice's records need a score as well as the result (a design choice
    still open: a fixed score per WDL, or the score of a search with the
    tables); and the loader reads shards in file order, shuffling only
    within its buffer, so slice games must be interleaved evenly into the
    snapshot's shards, not kept in a file of their own.
  - the choice of "common" 4-5 piece endings was to come from the material
    signatures Fork's own games reach at 5 pieces (a statistics run over a
    g3s1 shard was started and stopped).
- **tools written** (scratch, not committed): a conversion runner (python-chess
  driving Fork over UCI, start positions chosen and verified by the tables)
  and a table-entry statistics script.
- **originality:** tablebase labels are not engine-generated data (idea
  11's note); log the tablebase source in ORIGINALITY.md before use.
- **related:** idea 11 (TB boundary data), idea 12 (endgame conversion).
- **metric:** the endgame check's misjudged counts against targets (to be
  set), the conversion rate, then the net's promotion test.
- **status:** in the next snapshot (owner, 2026-11-06: lifted from its hold): the slice goes into g3s2, and the check becomes the standing acceptance test for the retrained default (DESIGN.md §5.6, order item 7).
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 10):** the acceptance target is at most 15 of 900 misjudged; part 3 (conversion without tables) dropped; part 2 extended to 4-5-man classes (X19).

## 46. Threat knowledge at a low speed cost: the design brainstorm

- **type:** ELO (a family of network, training and search designs; nothing
  built).
- **idea** (owner, 2026-11-06; design only, stopped for the owner's
  review): how to get XGR/S512+X-style threat knowledge into the
  evaluation without S512+X's speed loss (fixed-node +25.67 ± 10.26 Elo,
  STC −30.04 ± 10.82 at 0.818x nps). Four proposers with different briefs
  (systems/CPU, ML/compression, chess knowledge, novelty) wrote 17 designs
  from one brief of Fork's measured numbers; a judge merged and ranked
  them. Clean room: concepts only, no engine source opened; every estimate
  below is reasoned, not measured (UNVERIFIED until its experiment runs).
- **the judge's checks** (the parts that change the plan):
  - S512r2 is about 1,300 cycles per node (3.59 M nps at about 4.7 GHz,
    the clock UNVERIFIED): the 0.90 gate allows about 145 extra cycles per
    node, 0.95 about 70.
  - **Finding threats costs more than summing them.** Switching off XGR's
    set-wise exposure made it about 13% faster (§5.4), so finding exposed
    pieces is near 150 cycles before any rows are summed. A per-node attack
    map shared with move ordering saves less than it seems: most
    evaluations are at quiescence stand-pat, where quiet ordering does not
    run. Every "unshared" cost estimate should be read 0.03-0.06x worse
    until measured.
  - **The Elo value of speed is uncertain:** S512+X's swing gives about
    3.1 Elo per 1% nps (2.2-3.9), the usual rule of thumb about 0.9
    (UNVERIFIED for Fork). Plan with 2 ± 1 and measure it.
  - **An evaluation that depends on the search window** (alpha, beta, a
    pruning threshold) is not safe as proposed: the TT, the drift table's
    residuals, the improving flag and re-searches all assume a position
    has one static eval. Safe gates depend on the position only, or cache
    the fuller evaluation once computed (a TT flag that only upgrades).
  - A 1,600-game fixed-node match (about ±10 Elo) cannot screen designs
    worth +3 to +8: those need a loss screen, then an STC SPRT.
  - Column-restricted rows in the main accumulator break the loader's int16
    bound (it assumes at most 32 piece features): it would have to be redone.
  - 8-bit rows and additive low-rank factorization were argued out: S512+PP
    showed the cost is instructions and row width, and an additive
    factorization of attacker-victim weights reduces to per-square exposure
    features.
- **the designs, merged and ranked** (expected net Elo at STC per day of
  effort; effort in days of build, training and testing):

  | rank | design | proposers | effort | net STC Elo |
  |---|---|---|---|---|
  | 0 | the speed-Elo exchange rate (S512r2 against itself at 0.85x time) | judge | 0.5 + runners | enabler |
  | 0 | price the attack map in fork_micro (tiers: pawn attacks; + knights and kings; full per-kind maps; exposure sets) and split S512+X's 18% into finding and summing | systems, judge | 1 | enabler |
  | 0 | offline residual study: frozen S512r2's residuals against the labels, fitted by danger features and threat classes | chess knowledge, systems, novelty | 1-2 | kill test |
  | 1 | **distillation from S512+X** (teacher-blended score labels, λ 0.25 or 0.5, and an arm weighting positions where teacher and S512r2 disagree) **plus auxiliary threat targets** (a training-only head predicting hanging pieces and king-zone attacks): one Kaggle session, no speed cost | ML, novelty | 5-7 | 0 to +5 |
  | 2 | **threat-class output heads**: the head picked by phase x a cheap class (pawn and knight attacks on the mover's pieces), about 0.99x | systems, chess knowledge, novelty | 5-7 | 0 to +5 |
  | 3 | **gated threat evaluation** (S512+X's plane only where a position-only gate fires; one net trained with the plane dropped half the time); its oracle first: both nets in one engine at fixed nodes, no training | ML, systems, novelty | 3-4 (oracle), 12-15 | −10 to +8 |
  | 4 | **dense danger vector** into the last layer (counts of hanging and lower-attacked pieces, king-zone attackers, safe checks, restricted pieces), at the tier the attack-map pricing allows | chess knowledge, systems | 6-8 | −5 to +6 |
  | 5 | **column-restricted exposure rows**: exposure inputs confined to 64 of the 512 columns, updated incrementally (alive only if the attack map is cheap; a separate narrow lane is dominated by it) | systems (the lane: ML, chess knowledge, novelty) | 10-12 | −8 to +8 |
  | 6 | **pawn(+king)-keyed delta cache**, generalized from S512+PP's (after the cache's own measurement) | systems | 4-6 | 0 to +5 |
  | 7 | **threat-keyed correction and volatility tables** (a residual table keyed by the threat configuration; error magnitude scaling the pruning margins); an offline replay first | chess knowledge, novelty | 4-6 | 0 to +4 |
  | 8 | **stand-pat check under multiple threats** in quiescence (a new constant, measured on a wide grid) | chess knowledge | 4-6 | 0 to +4 |

- **first experiments, with their rules** (declared here, before any run;
  **approved by the owner as ranked, 2026-11-06, with the exchange rate
  first among these experiments (after the current SPRT queue: the threat
  set, then ProbCut), and every go/kill rule kept as written except rule
  5's, amended by the owner the same day**; DESIGN.md decisions log,
  2026-11-06):
  1. Exchange rate: S512r2 against itself at 0.85x time, STC, about 4,000
     games on GitHub's runners (about ±8 Elo). It sets every design's
     go/kill; under 1.5 Elo per 1% nps, the 0.90 gate would be too strict
     for designs with large judgment gains (the owner decides).
  2. Attack-map pricing (quiet machine): full maps plus exposure sets ≤ 60
     cycles keeps the dense vector and column-restricted rows alive; 60-120
     keeps only pawn/knight-tier features and the gate; over 120 kills
     every ungated slider-feature design; if finding is over 2/3 of
     S512+X's cost, the separate lane is dropped.
  3. Residual study (2-5 M held-out positions, frozen S512r2, WDL space):
     ≥ 0.5% loss reduction at an affordable tier trains the dense vector or
     the class heads there; 0.2-0.5% only the pawn-class heads (if ≥ 0.98x
     on a synthetic A/B); under 0.2% kills the output-layer family. The
     volatility table needs its top quintile of predicted uncertainty at
     ≥ 2x the bottom quintile's mean |residual|.
  4. Gate oracle (fixed nodes, both nets in one engine, 3,200 games):
     policies PV only, band 50, band 100 and a position-only gate; go if one
     keeps ≥ +15 with gate rate p x 18% + 3% ≤ 7%; the position-only gate is
     preferred if within 3 Elo of the best; otherwise the gated design is
     killed.
  5. Distillation and auxiliary targets (one Kaggle session; the relabelling
     by S512+X through jobctl): two seeds per arm; an arm is kept only if
     both seeds beat both control seeds beyond the spread with ≥ 0.3% lower
     loss on the original labels, then a fixed-node screen and an STC
     SPRT on [0, 5], as for every new network (owner, 2026-11-06; the
     judge's proposal to skip the screen, which cannot resolve gains of
     this size, was not adopted).
- **novelty** (the judge's view, low confidence, UNVERIFIED): possibly new
  are threat-class head selection, a threat-configuration key for
  correction tables, and confining an input family to a column subset of
  the main accumulator (block-sparse layers are known ML, so at most a new
  application). Not new: window-gated evaluation is classical lazy
  evaluation; uncertainty-scaled margins are partly public; auxiliary
  targets are standard multi-task learning.
- **sources to credit** (ORIGINALITY.md when a design is built): Fork KB
  nnue-inputs.md §1 and its sources (threat inputs in NNUE); Giraffe (M.
  Lai, 2015; attack and defend maps as inputs); public NNUE descriptions
  (phase and material output buckets, side paths into the output layer,
  accumulator refresh caches); Stockfish's public description of switching
  between a small and a big net by |eval|; correction history (public
  descriptions, first source UNVERIFIED); Chessprogramming wiki (Lazy
  Evaluation, Kogge-Stone Algorithm, SIMD and SWAR Techniques, Hyperbola
  Quintessence, Pawn Hash Table, King Safety, Attack and Defend Maps,
  Mobility, Trapped Pieces, Quiescence Search, Null Move, Botvinnik-Markoff
  Extension); Intel's ISA documentation and Wojciech Muła's blog (GFNI);
  KataGo (Wu 2019); Bucilua, Caruana and Niculescu-Mizil (2006); Hinton,
  Vinyals and Dean (2015); Furlanello et al. (2018); Shrivastava et al.
  (2016); Katharopoulos and Fleuret (2018); Jaderberg et al. (2016);
  Caruana (1997); Vapnik and Vashist (2009); Srivastava et al. (2014); Yu
  et al. (2018); Viola and Jones (2001); Teerapittayanon et al. (2016);
  Graves (2016); Denton et al. (2014); Jaderberg, Vedaldi and Zisserman
  (2014); Yuan and Lin (2006); Wen et al. (2016).
- **related:** ideas 40, 41 (S512cl), 44 (QAT); S512+X and XGR-512
  (DESIGN.md §5.4).
- **phase:** Phase 4.
- **metric:** each experiment's rule above; then SPRTs.
- **status:** approved as ranked (owner, 2026-11-06); the exchange rate
  runs first.
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 20):** distillation from S512+X dropped (refuted: the teacher is weaker than the default at fixed nodes) and the threat-keyed correction table dropped; threat inputs (ranks 3-5) parked; the residual study is redone against deep labels (X7); attack-map pricing folded into the zero-row build (X12); the stand-pat check only inside tail-risk-classed margins (R35); the speed-to-Elo measurement is the throttled 0.5x design (decision 7) and the gate is priced at 1.5 Elo per 1% nps (decision 8).

## 47. The better-training plan: relabelled data and quieter positions

- **type:** ELO.
- **idea** (owner, 2026-11-06): later experiments on the training data
  itself, each measured before any bulk change. Data generation meanwhile
  continues as it is: g3f generates new data labelled by S512+PP, the
  default since 2026-11-06, and nothing is relabelled now.
  1. **Relabelling old data with a newer net.** Generation 1 first (labelled
     by B0r1 and B0r2): rescore a sample of it with the current default and
     test it against an equal amount of newly generated data, with a small
     net (training cost of minutes, as B0's), before any bulk relabel.
     Generation 0 (bootstrap-labelled) only if generation 1's test helps.
     The test is declared before it runs: the same positions seen, two
     seeds per arm, one shared validation set; a gain only if the relabelled
     arm's mean loss is lower by more than the seed spread, then the usual
     SPRT path for a net trained on it. Relabelling keeps strategy A+ (Fork
     rescores its own data with its own nets, DESIGN.md §5.4 data decision
     1); each relabelled part gets its own manifest naming its new labeller.
  2. **Quiet-position selection** ("better labels"; KB
     research-nnue-dataset-quiet-positions.md, a clean-room summary of arXiv
     2412.17948): an offline pass marking positions whose static evaluation
     is far from their quiescence value as unsaved (score 32767, which the
     trainer already drops), written as derived shards with their own
     manifests; sealed data is never changed. First the offline counts on a
     wide pre-declared threshold grid (not centred on the paper's values:
     no constant is taken from it), and how much the test overlaps the
     capture-and-promotion filter; then training arms against the current
     filter, two seeds each, equal positions seen; then the usual path. The
     paper's second test (static evaluation against the label) is a
     measurement of the labelling net's error, as idea 46's residual study,
     not a filter; the Syzygy slice is exempt from both.
- **why:** the labels are only as good as the net that searched them, and
  the oldest data was labelled by the weakest evaluators; the paper claims
  a gain from quieter data but measured no ablation of its filter, so both
  ideas need Fork's own measurement.
- **phase:** Phase 4 or later, after item 7's retrain.
- **metric:** each experiment's declared rule above; then SPRTs.
- **status:** recorded (owner, 2026-11-06); not started.
  **2026-11-07 (owner, Phase 4 think tank; DESIGN.md §6, decision 20):** 47.1 (relabelling generation 1 first) dropped: the recency arm (R3) asks the question that matters; 47.2 (the quiet filter) shrunk to its offline count, low priority.

## Novel NNUE ideas (group, owner, 2026-11-07)

Six training and evaluation ideas the owner recorded after the Phase 4
think tank (docs/research/phase4-think-tank/), **plan only, scheduled after
item 8a**. The order of first experiments (owner): **51 and 52 first**
(training-only, cheap), then **53**, then **50**; 48 and 49 after them. Each
is tested at equal data with a small net first (B0's size, 768 -> 256,
training in minutes), then the usual path: parity, the fixed-node screen
for a new network design, the STC SPRT. Every number below is a placeholder
or a model prediction until measured; new names and constants go through
the screens before use.

## 48. Decision-focused loss: weight positions by search-decision sensitivity

- **type:** ELO (training-only; no runtime cost).
- **idea:** search uses the evaluation almost only through comparisons
  with thresholds (alpha, beta and the pruning margins), so an error that
  never flips a comparison costs nothing. Weight each training position by
  how close its evaluation sat to a decision boundary in Fork's own
  searches, instead of weighting all positions equally.
- **math:** for a position whose evaluation e meets a threshold b, an error
  delta flips the decision with probability about f(e - b) |delta|, where f
  is the density of (e - b) near zero; the expected decision cost is
  therefore about the sum over positions of w_i |delta_i| with w_i
  proportional to a kernel K(|e_i - b_i| / h). The weighted loss puts the
  net's capacity where decisions are made. The price is variance: with the
  weights normalised to mean 1, the effective sample size is
  n_eff = (sum w)^2 / sum w^2, which must stay at least half of n (else the
  gain is eaten by noise). It also explains, in part, why validation loss
  misranked S512+X and S512+PP (phase-a-evidence.md, A1 §2): plain loss
  counts errors that search never sees.
- **literature:** decision-focused or "predict-then-optimise" learning:
  Elmachtoub and Grigas, "Smart 'Predict, then Optimize'" (Management
  Science, 2022); Wilder, Dilkina and Tambe, "Melding the Data-Decisions
  Pipeline" (AAAI 2019) (both UNVERIFIED as exact citations).
- **first experiment:** offline. From the step 1 decision ledger (X10) and
  a search-log sample, attach to held-out positions the distance to the
  nearest bound or margin; score S512r2, S512+PP, S512ppr2 and S512+X with
  the weighted loss and check whether it orders them as their SPRTs did
  (where plain loss did not); report n_eff. Then a small-net pair at equal
  data, plain against weighted.
- **kill criterion:** the weighted loss does not rank the four nets in
  SPRT order better than plain loss, or n_eff below 0.5 n, or the small
  net's fixed-node result at or below zero.
- **data need:** training positions carry no search-log bounds today:
  either a datagen field (a data-format change) or an offline shallow
  search per sampled position; costed before building.
- **phase:** Phase 4, after item 8a. **metric:** the offline ranking test,
  then the fixed-node screen and the STC SPRT. **status:** untested (plan
  only, owner, 2026-11-07). **runtime cost:** none. **earliest phase:**
  Phase 4.

## 49. Pairwise ranking loss on sibling positions

- **type:** ELO (training-only; no runtime cost).
- **idea:** the move choice at a node depends on the order of its
  children's values, which value regression does not enforce. Add a
  ranking term over sibling positions (the children of one parent), ordered
  by Fork's own deeper search, to the value loss.
- **math:** a RankNet-style term, sum over sibling pairs (a above b) of
  log(1 + exp(-s (v_a - v_b))), with s the logistic scale; its gradient is
  largest for pairs the net orders wrongly or nearly ties, which are the
  pairs whose order changes the move played. A small value error on a
  close top-two pair costs a move; the same error on a lopsided pair costs
  nothing, so the ranking term spends capacity where regression does not.
  The total loss is L_value + mu L_rank with mu a placeholder set by a
  two-point ladder.
- **literature:** Burges et al., "Learning to Rank using Gradient Descent"
  (ICML 2005, RankNet); the Bradley-Terry model (1952) (UNVERIFIED as exact
  citations).
- **first experiment:** sibling sets generated offline from Fork's data:
  about 200,000 parents, up to 8 children each, labelled by a 20,000-node
  search of the default (about 32 G nodes, roughly 6 CPU-hours at 1.5 M
  nps per thread, UNVERIFIED); a small net with mu in {0, a placeholder},
  scored by top-1 agreement with a deeper search on held-out parents, then
  fixed-node games.
- **kill criterion:** top-1 agreement improves by less than 1 point, or
  the fixed-node result is at or below zero.
- **phase:** Phase 4, after 48's order slot. **metric:** top-1 agreement,
  then the fixed-node screen and the STC SPRT. **status:** untested (plan
  only, owner, 2026-11-07). **runtime cost:** none. **earliest phase:**
  Phase 4.

## 50. Conformal pruning margins from an uncertainty estimate

- **type:** ELO (search; runtime cost possible).
- **idea:** give pruning margins a coverage guarantee: a small head (or a
  cheap proxy) estimates each position's evaluation uncertainty u(x), and
  each margin is u(x) times a quantile calibrated on held-out search data,
  so the rate of wrong prunes is set directly rather than through fixed
  centipawn margins (the owner's "revision-head style").
- **math:** split conformal prediction. On a calibration set compute the
  normalised scores r_i = (e_i - s_i) / u_i (static evaluation minus
  search result, divided by the predicted uncertainty: how far the search
  fell below the evaluation) and take q, the
  ceil((n + 1)(1 - alpha)) / n empirical quantile; the margin m(x) = q u(x)
  then gives P(s < e - m) at most alpha for an exchangeable new position.
  It fits the think tank's margin model (phase-b-specialists.md, B11: the
  optimal margin satisfies P(r < -m*) = lambda C_d / L_d): conformal sets
  each depth's error rate alpha_d directly and adapts the margin to the
  position through u(x), which is what the heavy tail (B11: 59-89% of
  wrong depth-1 RFP prunes come from the tail) needs. Caveat: positions
  met in search are not exchangeable with the calibration set, so the
  guarantee is approximate and must be checked in the engine.
- **literature:** Vovk, Gammerman and Shafer, "Algorithmic Learning in a
  Random World" (2005); Lei et al., "Distribution-Free Predictive Inference
  for Regression" (JASA 2018); Angelopoulos and Bates, "A Gentle
  Introduction to Conformal Prediction" (2021) (UNVERIFIED as exact
  citations).
- **first experiment:** offline, from the decision ledger (X10): does u(x)
  (first a free proxy: the TT-refined minus raw evaluation, the last
  move's evaluation swing; then a trained uncertainty head) reduce wrong
  prunes at an equal prune count? Then the head's cost, computed only at
  pruning decisions.
- **kill criterion:** fewer than 20% fewer wrong prunes at an equal prune
  count offline (the think tank's I4 gate), or an nps cost above 1%
  without a matching gain, or H0.
- **phase:** Phase 4, after 53. **metric:** the offline wrong-prune
  reduction, nps, then the STC SPRT (and LTC: a pruning change). **status:**
  untested (plan only, owner, 2026-11-07). **runtime cost:** possible (an
  extra output, or a proxy at pruning nodes). **earliest phase:** Phase 4.

## 51. TD(lambda) targets from Fork's stored self-play games

- **type:** ELO (training-only; no runtime cost).
- **idea:** replace the score/result blend (result weight 0.5 since B0)
  with lambda-weighted targets built from the later search scores stored
  in the same game, ending in the result; compared with the current blend
  at equal data.
- **math:** the target for the position at ply t is
  (1 - lambda) sum_{k >= 1} lambda^(k-1) sigma(s_{t+k} / S), with the game
  result as the terminal value. Fork's measurements (phase-b-specialists.md,
  B4 M2 and B12 W4): the result is shared by about 35 kept positions per
  game, with a within-game correlation of 0.674, so a game carries only
  about 1.5 independent result observations; the stored score 16-32 plies
  later carries one half to two thirds of the result's information at
  about a third of its noise. Averaging the later scores therefore cuts the
  target's variance while keeping most of the information that only the
  result brings. lambda is chosen by measurement, not guessed: the value
  that minimises the target's error against the deep-label gold set (X7).
  Caveats (B13): only the saved, full-search scores may enter (the split
  search's cheap moves are not comparable), and the result's bias differs
  by endgame class, so the decisive-share pilot (X11) runs first.
- **literature:** Sutton, "Learning to Predict by the Methods of Temporal
  Differences" (Machine Learning, 1988); Baxter, Tridgell and Weaver,
  TDLeaf(lambda) in KnightCap (1998/2000); the KataGo paper's remark that
  the outcome target is data-limited (Wu, 2019) (UNVERIFIED as exact
  citations). **Credit (owner, 2026-11-09):** KataGo's short-term value
  targets (Wu, 2019: value targets built from the game's own later
  evaluations over short horizons, beside the final outcome) are the
  nearest relative of these TD(lambda) labels and are credited at concept
  level (UNVERIFIED as an exact description of the paper).
- **first experiment:** the offline variance study (lambda against gold-set
  error, CPU minutes once X7 exists); then a small net on the same
  positions, the current blend against the TD(lambda) target, two seeds,
  scored on the gold set and by fixed-node games. The trainer needs a
  reader flag for the per-game later scores.
- **kill criterion:** the TD arm's gold-set loss is not at least 2e-5
  better than the blend's, or its fixed-node result is within plus or minus
  4 Elo of the control (B12's kill rule), or the endgame check worsens.
- **phase:** Phase 4, after item 8a (first among this group). **metric:**
  gold-set loss, the fixed-node screen, then the STC SPRT. **status:**
  untested (plan only, owner, 2026-11-07); overlaps the think tank's R37
  (n-step and lambda-return targets), which this entry supersedes.
  **2026-11-10: retrain 8b's TD(0.9) arm, r8btd90, is promoted to the
  default network** (owner; its fixed-node screen against S512ppr3
  +17.39 ± 9.71, the highest of 8b's four candidates; STC [0, 5]
  +12.17 ± 5.71, H1 after 4,800 games; sprt-log, DESIGN.md §6). The
  TD(0.8) arm screened −1.09 ± 9.30 against S512ppr3. The idea's own keep
  rule (retrain 8b's plan §3 item 7: the TD arm's head-to-head against
  the control above +4 Elo, its endgame check not worse than the
  control's; both 7 of 900) is still pending: the td80 and td90
  head-to-heads against c are queued.
  **2026-11-11: kept (owner): TD(0.9) labels stay in the standard retrain
  recipe.** Head-to-heads against the control r8bc (800,000 nodes per
  move, 1,600 games each): td90 +4.13 ± 9.47 (run 42935666743), above the
  plan's +4 keep line, its endgame check 7 of 900 as the control's; td80
  −0.87 ± 9.13 (42930415181), not kept. The measured seed noise (c2
  against r8bc, −6.08 ± 9.42; idea 69) is as large as that margin, so
  every future retrain arm runs 2 seeds (owner, 2026-11-11). r8btd90's
  result fine-tune, r8brft1, is the default since 2026-11-11 (idea 70).
  **runtime cost:** none. **earliest phase:** Phase 4.

## 52. Ensemble-disagreement active learning

- **type:** ELO (training-only; no runtime cost).
- **idea:** each retrain already produces two seeds; the positions where
  they disagree most are where the network is least sure. Oversample those
  positions and give them deep labels.
- **math:** query by committee: the disagreement D(x) = |v_1(x) - v_2(x)|
  estimates the epistemic variance at x. Under a bias-variance view the
  reducible error at x grows with Var_seed(v(x)); allocating extra labels
  in proportion to its square root (Neyman allocation) minimises the total
  variance for a fixed labelling budget. The gain depends on how
  concentrated the disagreement is: if the top 5% of D hold no more error
  than average, there is nothing to buy.
- **literature:** Seung, Opper and Sompolinsky, "Query by Committee"
  (COLT 1992); Settles, "Active Learning Literature Survey" (2009)
  (UNVERIFIED as exact citations).
- **first experiment:** CPU minutes: the item-7 warm seeds' float weights
  (both kept in ~/fork-data/kaggle/g3s2-out/result/) score a held-out
  sample; compare the error of the top-5% D positions against deep labels
  (X7) with a random 5%. Then, if it passes, deep-label a top-D sample
  (sized by CPU cost: 1 M positions at 1 M nodes is about 185 CPU-hours,
  so start with 100,000-200,000 positions at 200,000 nodes) and train a
  small net at equal data against a random-sample control.
- **kill criterion:** the top-D positions' error is less than 1.5 times a
  random sample's, or the small-net arm is not better than the random arm
  by more than the seed spread.
- **phase:** Phase 4, after item 8a (with 51). **metric:** the error
  ratio, then gold-set loss, the fixed-node screen and the STC SPRT.
  **status:** first step done (2026-11-07; docs/research/idea52/report.md): the **warm pair** (item 7's
  warm seeds, in effect one net) fails the 1.5 line (eval-matched ratios 1.24-1.37); the **scratch pair**
  (independent initialisations) passes it (eval-matched 1.69-1.76 on three detectors, 1.49-1.50 on the
  fourth, unchanged with deep-search mates excluded), and the default net's own error is 1.6-1.7 times
  higher on the positions the scratch pair picks. Next (owner): disagreement of an independent pair is a
  detector in the crucial-point measurement, and **retrain 8b gets an idea-52 arm**: the top-disagreement
  positions (from an independent pair) deep-labelled and oversampled against the standard arm at equal
  data; every retrain from 8b on keeps one from-scratch run as the independent committee member.
  **Keep-or-drop rule** (owner, decided before 8b's result): if 8b's disagreement arm does not beat
  the standard arm by a meaningful margin (a fixed-node screen of +5 Elo or more, or a passing SPRT
  if it is screened), idea 52 is retired and the scratch-run rule dropped (saving its 2-4 hours per
  retrain); the result stays in the record either way.
  **2026-11-10, retrain 8b:** the i52 arm's fixed-node screen against S512ppr3 was +5.86 ± 9.13 (the
  control's +13.03 ± 9.37; the TD(0.9) arm, +17.39, was promoted); the keep rule's head-to-head against
  the control (r8b-h2h-i52) is running, so the idea is undecided.
  **2026-11-11:** the head-to-head against the control r8bc was **−4.13 ± 9.60** (run 42925024784, 1,600
  games at 800,000 nodes); **the i52 arm is not kept** (owner). It misses the keep-or-drop rule's +5 line,
  so by that rule idea 52 is retired and the scratch-run rule dropped; that consequence is the declared
  rule's, not yet confirmed by the owner (UNVERIFIED until then).
  **runtime cost:** none. **earliest phase:** Phase 4.

## 53. Pawn-structure-class output experts

- **type:** ELO (evaluation; runtime cost possible, expected near zero).
- **idea:** Fork's 8 output heads are chosen by material phase. Choose (or
  add) the head by pawn-structure class instead: a class id from a cached
  pawn-structure key, looked up once per pawn configuration, so each class
  gets its own readout of the same accumulator.
- **math:** a mixture of experts on the output layer: the gain is the
  variance of the optimal readout across classes, roughly
  sum_c p_c ||w_c - w_bar||^2 in the accumulator's covariance metric, paid
  for by fewer training positions per head (a class with share p_c sees
  p_c of the data; at about 650 positions per first-layer weight there is
  room). The cost is a table lookup by pawn key (pawn moves are 24.2% of
  makes on bench, 16% in game, X1), cached, so the nps cost should be near zero; the class map
  itself (hand classes such as open, closed, isolated queen's pawn,
  symmetrical, or clusters of pawn features) is chosen by the probe below,
  not guessed. Pawn links' success (S512+PP: +32.7 STC) is evidence that
  pawn structure carries knowledge that search does not reach.
- **literature:** Jacobs, Jordan, Nowlan and Hinton, "Adaptive Mixtures of
  Local Experts" (Neural Computation, 1991); output buckets are common
  NNUE practice (KB nnue-design.md); this gating is Fork's own (NOVEL as
  far as the think tank found, UNVERIFIED). Same family as the think tank's
  W2/R26 (output experts chosen by frozen-feature probes): this entry is one
  of its candidate gatings.
- **first experiment:** the CPU probe (W2's method): freeze S512ppr2's
  first layer, fit per-class readouts for a few class maps against the
  phase buckets on held-out data; train only the best map if it gains.
  Fork's incremental pawn key exists as `Position::pawn_key` on
  tier2/batch4 (not yet on phase-4); "pawn_structure_key" is the owner's
  descriptive name, and any new name is screened before use.
- **kill criterion:** the probe's validation gain is under 2e-5 for every
  class map, or the fixed-node result is at or below zero, or nps falls by
  more than 1%.
- **phase:** Phase 4, after 51 and 52. **metric:** the probe gain, nps,
  the fixed-node screen, then the STC SPRT. **status:** untested (plan
  only, owner, 2026-11-07). **runtime cost:** possible (near zero
  expected). **earliest phase:** Phase 4.

## Paradigm candidates (group, owner, 2026-11-07)

Five larger departures from Fork's present design, recorded by the owner
after the Phase 4 think tank, **plan only, after the current Phase 4
order**, except that **54 is the first to prototype, after item 8a**. Each
starts with a cheap offline study and a kill criterion, before any engine
change or SPRT. Every number below is a placeholder or a model prediction
until measured; new names and constants go through the screens before use.

## 54. Shared-accumulator policy head for move ordering, then reductions

- **type:** ELO (search and evaluation; runtime cost possible).
- **idea:** a small move-scoring head that reuses the NNUE accumulator
  already computed at the node: it scores candidate moves for ordering
  first, and only later informs reductions. Its cost per node and its
  ordering quality (the first-move cutoff rate) are measured before any
  SPRT.
- **math:** alpha-beta's tree approaches the minimal tree (on the order of
  b^(d/2) leaves, Knuth and Moore) only with good ordering; every cutoff found on
  a later move costs the earlier siblings' subtrees. The trade, at the
  think tank's rate of about 1.5 Elo per 1% nps (phase-a-evidence.md):
  Elo is about 1.5 x (the percentage of nodes saved at equal depth minus
  the percentage of nps lost). The head's cost is about one dot product of
  the accumulator with a per-move vector for each move scored (512
  multiply-adds), so roughly 15,000 per node if every quiet move is
  scored; it must therefore be gated (deep nodes only, or nodes without a
  TT move, where IIR already says ordering is weakest), which the think
  tank's W8 proposed.
- **literature:** policy priors in AlphaZero (Silver et al., Science 2018)
  and Leela Chess Zero; Fork's own idea 16 (a tiny policy net, parked) and
  the think tank's W8 (phase-b-specialists.md, B12) and its verdict (B14:
  WEAK as a Phase 4 plan change; the synthesis listed it as not for Phase
  4), which this entry now schedules as a prototype after item 8a.
- **first experiment:** offline: train the head on Fork's data (the move
  the search played is stored per position) and measure top-1 and top-3
  agreement with the search's move on held-out positions; then a stats
  build replay (the step 1 tooling, X1 and X2) recording, at gated nodes,
  whether the head's first move is the eventual cutoff move, against the
  current selector's first quiet, and the head's cost in cycles per node.
- **kill criterion:** the predicted node saving at equal depth does not
  exceed the measured nps cost (net Elo by the formula above at or below
  zero), or the first-move cutoff rate at gated nodes improves by less
  than 1 point.
- **phase:** prototype after item 8a. **metric:** first-move cutoff rate,
  node saving and cycles per node, then the STC SPRT (and LTC). **status:**
  untested (plan only, owner, 2026-11-07). **runtime cost:** possible.
  **earliest phase:** Phase 4.

## 55. A learned reduction and pruning function

- **type:** ELO (search; runtime cost possible).
- **idea:** replace the hand-written reduction and pruning formulas (LMR's
  table and adjustments, the futility and late-move pruning rules) with
  one tiny model trained from search outcomes, an approach the owner saw
  elsewhere under the name HARENN; it is the continuous counterpart of idea 23's evolutionary
  search over heuristic rules.
- **math:** a reduction is a bet: reducing a move saves the nodes of a
  full-depth search and loses when the move would have raised alpha. With
  p(x) the probability that the move matters, given features x (depth,
  move index, history scores, the improving flag, node type, the eval's
  distance to the bounds), the expected cost is about
  p(x) L(depth) - (1 - p(x)) C(depth, r), so the optimal reduction falls as
  p rises; a calibrated model of p (logistic regression first, a two-layer
  net only if it pays) gives the whole family of rules at once. Training
  labels come from the search itself: whether a reduced move later forced
  a re-search, and the decision ledger's counterfactual searches (X10).
- **literature:** an outside reference the owner saw, "HARENN" (source not located by
  this session, UNVERIFIED); learned evaluation and probability-guided
  search in Giraffe (Lai, arXiv 1509.01549, 2015); public discussion of a
  small network predicting the reduction (TalkChess,
  https://talkchess.com/viewtopic.php?p=825512, found by a web search on
  2026-11-07; its content not read, UNVERIFIED) (concepts only).
- **first experiment:** offline: log LMR decision features and their
  outcomes in the stats build over the step 1 replays; fit the model and
  compare its ranking of "moves that mattered" (AUC) with the ranking the
  current formula implies.
- **kill criterion:** the model's AUC beats the hand formula's by less than
  0.02, or its cost per decision is not covered by the predicted saving.
- **phase:** after the current Phase 4 order (and after idea 23's capped
  pilot, which tests the same space by search). **metric:** offline AUC,
  then the STC SPRT and LTC. **status:** untested (plan only, owner,
  2026-11-07). **runtime cost:** possible. **earliest phase:** Phase 4.

## 56. Probabilistic search with neural uncertainty

- **type:** ELO (search; runtime cost possible).
- **idea:** let search spend effort where the evaluation is uncertain,
  in the line of Bayesian and probabilistic game-tree search: each node
  carries a distribution (a mean and an uncertainty) instead of a point
  value, and the uncertainty steers expansion, reductions and stopping.
  It starts with an offline study of whether predicted uncertainty matches
  the actual evaluation error.
- **math:** with node values as distributions, the value of expanding a
  node is the expected change in the root decision (the
  value-of-computation view: Russell and Wefald); a node whose value is
  certain is not worth expanding however close it is to the bounds. All of
  it rests on one empirical premise: that the predicted uncertainty u(x)
  ranks and scales the actual error |s(x) - e(x)| (deep search result minus
  static evaluation). That premise is cheap to test and decides the rest.
- **literature:** Palay, "Searching with Probabilities" (1985); Baum and
  Smith, "A Bayesian Approach to Relevance in Game Playing" (Artificial
  Intelligence, 1997); Russell and Wefald, "Do the Right Thing" (1991)
  (UNVERIFIED as exact citations). It shares its uncertainty estimate with
  ideas 50 (conformal margins) and 52 (seed disagreement).
- **first experiment:** offline: on held-out positions with deep labels
  (the think tank's X7), compare candidate uncertainty estimates (the two
  seeds' disagreement, idea 52; an uncertainty head, idea 50; free proxies
  such as the TT-refined minus raw evaluation) with the actual error:
  Spearman correlation and a reliability diagram by decile.
- **kill criterion:** Spearman correlation below 0.3 for every estimate,
  or a reliability curve that is not monotone; then the whole family
  stops.
- **phase:** after the current Phase 4 order (the offline study may run
  earlier, as it shares X7). **metric:** the calibration study, then the
  design's own tests. **status:** untested (plan only, owner, 2026-11-07).
  **runtime cost:** possible. **earliest phase:** Phase 4.

## 57. In-game adaptation of a small part of the evaluation

- **type:** ELO (search and evaluation; runtime cost possible).
- **idea:** let a small adaptable part of the evaluation learn during a
  game from Fork's own search results, extending correction history (an
  additive term keyed by pawn structure) to, for example, a per-output-head
  bias or a low-rank update of the output layer, trained online on the
  residual (search result minus static evaluation) and decayed towards zero.
- **math:** online gradient descent on a convex loss has regret growing
  only as the square root of the number of updates (Zinkevich), so a small
  linear correction can track a game's systematic bias; exponential decay
  (rate eta, a placeholder) handles the drift as the game moves on. The
  risk is noise: residuals are themselves noisy labels, so the update must
  be small and its gain shown on later positions of the same game, never
  on the positions it learned from. Determinism holds within a search
  (the state resets at ucinewgame and per bench position); multi-threaded
  search (Phase 6) needs per-thread or shared state by design.
- **literature:** correction history (Chess Programming Wiki, "Static
  Evaluation Correction History"); test-time training (Sun et al., ICML
  2020); online convex optimisation (Zinkevich, ICML 2003) (UNVERIFIED as
  exact citations). The think tank's correction-table ranking (R34) is the
  nearest planned work.
- **first experiment:** offline replay of Fork's own games: simulate the
  online update on the recorded residuals and measure the residual
  reduction on later positions of the same game, against no adaptation and
  against the existing correction-table keys.
- **kill criterion:** a residual reduction under 5% on held-out later
  positions, or no gain over the best correction-table key.
- **phase:** after the current Phase 4 order (after R34). **metric:** the
  offline residual reduction, then the STC SPRT and LTC. **status:**
  untested (plan only, owner, 2026-11-07). **runtime cost:** possible.
  **earliest phase:** Phase 4.

## 58. Giant-teacher distillation

- **type:** ELO (training-only; no runtime cost).
- **idea:** a large network (wider, deeper, with rich inputs such as
  threats, far too slow for search) trained on Kaggle on Fork's own data
  and used only to label data for the fast NNUE. The teacher is Fork's own
  net on Fork's own data, so the data policy holds.
- **math:** distillation transfers a teacher's function to a smaller
  student (Hinton, Vinyals and Dean, 2015); it pays only if the teacher's
  labels are closer to the truth than the labels Fork has now (20,000-node
  searches of the current default). Two think-tank results bound it: the
  distillation from S512+X was refuted because that teacher was weaker
  than the default at fixed nodes (phase-b-specialists.md, B13), and
  elsewhere relabelling with a net's static output instead of a search
  lost about 3 Elo (B2). So the gate is the teacher's measured error
  against deep labels, not its size; a teacher that also searches (its
  evaluation inside a shallow search) is the stronger variant to test.
- **literature:** Hinton, Vinyals and Dean, "Distilling the Knowledge in a
  Neural Network" (2015); the think tank's T and B13 entries on teacher
  labels (UNVERIFIED as exact citations).
- **first experiment:** one Kaggle session: train a large network on g3s3
  and compare its error on the deep-label gold set (X7) with the error of
  the current 20,000-node search labels on the same positions; inference
  throughput on a T4 sets the relabelling cost.
- **kill criterion:** the teacher's gold-set error is not at least 10%
  lower than the current labels' error (a placeholder margin, set before
  the run), or a small student trained on teacher labels does not beat one
  trained on search labels at equal data by more than the seed spread.
- **phase:** after the current Phase 4 order. **metric:** gold-set error,
  then the small-net test, the fixed-node screen and the STC SPRT.
  **status:** untested (plan only, owner, 2026-11-07). **runtime cost:**
  none. **earliest phase:** Phase 4.

## 59. Boundary Refiner: a rich evaluation consulted only near the window

- **type:** ELO (evaluation and search; runtime cost possible).
- **idea** (owner, 2026-11-07; plan only, after item 8a): a fast base net
  evaluates everywhere; a richer refiner net is consulted only when the
  base evaluation lies within a margin of the current alpha-beta window,
  and it predicts a correction to the base evaluation. The refiner is
  trained specifically on near-window positions from Fork's own search
  logs, deeply labelled.
- **basis:** Fork's own evidence that rich inputs improve judgement but
  lose on per-node cost: S512+X gained +25.67 and XGR-512 +30.70 at fixed
  nodes, yet both lost at STC (−30.04 and −34.42), because each 1% of nps
  is worth about 1.5 Elo at STC (the think tank's fit to all eight
  fixed-node/STC pairs, phase-a-evidence.md). An evaluation error matters
  only where it can flip a comparison with a bound (idea 48), so most of a
  rich net's fixed-node gain should come from the few evaluations near the
  window.
- **cost model:** time per node is about t_base + r x t_refiner, with r
  the refiner's call rate per node (the share of evaluations that call it,
  times the evaluations per node: 0.54 in game, X1); the nps ratio is
  1 / (1 + r x t_refiner / t_base). With S512+X's 0.818 as the price of
  running the rich net at every node (about +22% time), a call rate of
  2-5% of evaluations costs well under 5% of nps, if the refiner's
  per-call cost is close to an incremental evaluation. That condition is
  the crux: a refiner consulted only sometimes cannot keep its own
  accumulator incrementally updated for free, and a refresh on demand
  costs many incremental updates (X1: 3.10 rows per update against a
  full refresh of every active feature). So the prototype measures the
  real per-call cost, with the refiner's accumulator either updated
  alongside the base one (a fixed cost per move) or refreshed lazily.
  Fixed-node gain retained is about q x 25.7, where q is the share of
  S512+X's gain that lives in the consulted evaluations: the experiment
  measures q at each margin.
- **literature:** cascades of classifiers (Viola and Jones, 2001) and
  conditional computation (Bengio, Leonard and Courville, 2013), where an
  expensive model runs only on hard inputs (both verified 2026-11-08:
  Viola and Jones, CVPR 2001; Bengio, Léonard and Courville,
  arXiv:1308.3432). **The window gate itself is classic lazy evaluation**
  (Chess Programming Wiki, "Lazy Evaluation": the costly terms are
  computed only when the cheap score lies near the window, and added to
  it), the same rule, not its opposite (corrected 2026-11-08). The prior-art
  search (2026-11-08; KB branch kb, docs/kb/research-boundary-refiner-prior-art.md)
  also found the near-bound rationale argued on TalkChess (2017), a 2020
  Stockfish proposal to choose its evaluation by the window (closed
  untested), Stockfish's conditional second networks under other gates,
  and decision-relevance arguments in the literature. What it did not find,
  within the sources searched: a separately trained residual refiner on a
  full NNUE base, consulted only within a small budget margin, trained on
  the engine's own near-window positions with deep labels, sharing the
  base accumulator; and a controlled test of where it is consulted (window
  gate against a random gate at equal call rate, plus a bias-only
  control). Any public text places idea 59 in the lazy and two-tier
  evaluation family and claims only what the search did not find. Related Fork entries: idea 46's gated
  evaluation's oracle (the same family), idea 48 (the decision-focused
  view at training time), idea 50 (near-boundary margins).
- **step 1 (measurement):** with the stats build (the step 1 tooling),
  record the distribution of |base evaluation − nearest window bound| at
  evaluation sites over the step 1 game replays, and report the call rates
  for margins of 10, 25, 50 and 100 cp, **separately for quiescence
  evaluations and main-search evaluations** (owner, 2026-11-07): X1 shows
  quiescence holds 68-72% of evaluations in game, and the gate's margin
  may need to differ between the two (two margins, m_main and m_qs, each a
  placeholder set by this measurement). The cost model then reads
  r = r_main + r_qs, each the share of evaluations inside its own margin.
- **step 2 (oracle prototype, no training):** S512ppr2 everywhere, and
  S512+X's evaluation (scale-matched to S512ppr2) only within the margin;
  a fixed-node screen against S512ppr2 and the nps at 2-3 margins.
  **Prediction (owner):** +10 to +20 Elo at fixed nodes, under 5% nps cost
  at a 2-5% call rate. **Kill:** less than one third of S512+X's
  fixed-node gain retained (below about +8.6) at a call rate under 10%.
  **The oracle is a pessimistic test of the cost** (owner, 2026-11-07): it
  runs two separate networks with two accumulators, so S512+X's
  accumulator must be kept up to date (or refreshed) even at the nodes
  where it is never consulted; step 3's design removes that cost, so step
  2's nps figure is an upper bound on step 3's.
- **step 3 (only if step 2 passes):** train a dedicated refiner (a
  residual target, near-window positions, rich inputs including threats),
  then the usual screens and the STC SPRT (and LTC). **Design: the refiner
  shares the base net's accumulator** (owner, 2026-11-07): its input is the
  base accumulator plus rich features (exposure and threats) computed on
  demand only when the gate fires, feeding the refiner's own small layers,
  so no second accumulator is ever updated. Its cost is then paid only per
  call: the on-demand rich features (an attack-map pass over the board)
  plus the small layers, and t_refiner in the cost model above is that
  per-call cost alone. The rich features enter the small layers directly
  (not a wide first layer), so they need no incremental update. **Watch:** TT
  inconsistency from mixed evaluations: the same position can get a
  different static evaluation depending on the window it was reached
  with, which touches the TT's stored evaluation, the improving flag and
  the correction tables; the prototype should store which evaluation was
  used, or always store the base evaluation.
- **phase:** Phase 4, after item 8a. **metric:** call rates (step 1), the
  fixed-node screen and nps (step 2), then the STC SPRT. **status:**
  untested (plan only, owner, 2026-11-07); step 1 measured (call rates; measure/step1). **Step 2
  passed, and the control split confirms the mechanism (owner, 2026-11-08).** Fixed-node screens of
  1,600 games, 800,000 nodes per move, against S512r2 alone (base 56dacaf; oracle and controls on
  exp/oracle, d5bb138 and 92aa87c):

  | setting | Elo | nElo | run |
  |---|---|---|---|
  | (a) window gate, main 25 / quiescence 10 cp, S512+X refines (3.81% of nodes consulted) | +29.82 +/- 9.78 | +52.21 | 42436884886 |
  | (b) window gate, main 25 / quiescence 25 cp | +41.01 +/- 9.97 | +70.68 | 42439918061 |
  | random gate at (a)'s call rate (key-hashed, 3.82% of nodes) | +7.60 +/- 9.93 | +13.04 | 42451958660 |
  | bias only: (a)'s gate adding its mean refinement, +10.776 cp, S512+X never consulted | −14.56 +/- 9.96 | −24.92 | 42448595388 |

  Both settings clear the kill line (+8.6) at a call rate far under 10%. At equal call rate the window
  gate beats the random gate by about 22 Elo (about 3 standard errors), and the random gate's own gain
  is inconclusive against zero: the gain comes from where the refiner is consulted. The bias-only
  control loses, so the gain is not a calibration shift: it lives in the refiner's position-specific
  corrections. The random sites' corrections are larger (mean |refinement| 36.9 cp against 25.6), so
  the size of the disagreement is not what pays; its position relative to the window is. Fixed-node
  results do not charge the second network's cost: the nps A/B awaits a quiet machine, and step 3's
  design (a shared accumulator) is what the cost claim rests on. **Next: step 3's design, for the
  owner's review before building** (with the owner's 2026-11-08 additions: a head-to-head of a wider
  quiescence margin and both margins SPSA-tunable; TT-reused evaluations considered in the gate; a
  confidence output; training weighted by closeness to the window, idea 48 applied here; a cap on the
  correction's size; features in the order exposure, a cheap bitboard danger summary, then threats only
  if they fit the speed budget), and a prior-art search for gated, boundary-specific evaluation
  refiners before any public claim. **Publication plan (owner, 2026-11-07):** if step 3 passes its STC and LTC
  SPRTs, write a reproduction guide in docs/research/boundary-refiner/ (the mechanism; the evidence,
  including the control split of window-gated refiner, bias-only and random gate; implementation details;
  the refiner's training; failures and costs; settings), then a TalkChess summary post and possibly an
  arXiv note, stating clearly that the idea came from an AI-assisted project. Anything published outside
  the repository needs the owner's go-ahead at the time. **runtime cost:** possible.
  **earliest phase:** Phase 4.
- **step 3 outcome (owner, 2026-11-09): the shared-accumulator refiner hurt; step 3 closes, step 3b
  parked.** Kernel v2 (idea59/step3 a9bbd88; the declared pick w2, cap 198, weighted arm, seed 2) cut
  validation loss from 0.0426 to 0.0227 but failed the offline acceptance (gated net flips −0.007 on test;
  a constant +122 cp shift scored +0.143, above the oracle's +0.079). By the owner's decision (2026-11-08)
  the net-flip yardstick is not a kill gate, and fixed-node screens decided instead (1,600 games,
  800,000 nodes per move, against S512ppr3 alone; gate main 25 / quiescence 10 cp):

  | setting | Elo | nElo | run |
  |---|---|---|---|
  | f1a: refiner (shared accumulator), both gates (idea59/step3 05061ce) | −19.78 +/- 9.67 | −34.91 | 42574807031 |
  | f1b: refiner, quiescence only (077d1c8) | −11.73 +/- 9.63 | −20.76 | 42589690181 |
  | f1c: second opinion, blend (base + second) / 2 with the independent net s512pp-scratch-s1 (exp/oracle dcbe8fb) | +9.56 +/- 9.45 | +17.24 | 42594402144 |
  | f1d: second opinion, replace by s512pp-scratch-s1 (ab1abce) | +3.47 +/- 9.34 | +6.33 | 42600420297 |

  Both refiner screens are at or below 0, so the refiner line ends (no SPRT ran; the pre-approved STC
  SPRTs needed a point estimate above 0). The independent-net screens match the pattern the
  independence hypothesis (owner, 2026-11-08) predicted, with the blend ahead of the replacement, but f1c is
  below the bar declared before the result (+10), so no step 3b plan is written. **Step 3b, parked as a
  hypothesis to revisit when compute allows:** a small independent near-window net (widths 64 / 128),
  blended with the base at gate fire with a tuned blend weight. The second network's nps cost (f1c and
  f1d about 25-30% slower on bench, indicative) is not charged by fixed-node screens, which is part of
  why the bar is set where it is. **status:** step 3 closed; step 3b parked.
- **linked follow-ups** (owner, 2026-11-08; plan only, after step 3's first
  results; each its own experiment, shared with idea 61's family):
  1. **Boundary controller:** the refiner's confidence output routes each
     near-window site to "use the correction" or "extend" (idea 60), from
     the confidence and simple tactical signals.
  2. **Boundary distillation:** label the refiner's training sites with
     the big teacher (idea 58) instead of, or alongside, deep search.
  3. **Conformal calibration** (idea 50) of the gate's and the prunes'
     margins from the crucial-point error distribution (measure/step1,
     daca926).
  4. **Closeness-weighted training of the base net** (idea 48's
     decision-focused loss), as step 3 does for the refiner.
  5. **Site selection by nearness to the window plus seed disagreement**
     (idea 52) for the refiner's labels. Evidence to weigh first: as a
     crucial-point gate on its own, the seeds' disagreement was near random
     (AUC 0.52-0.54, measure/step1), and idea 52 itself stands or falls by
     item 8b's keep-or-drop rule.
  6. **The gate policy as an idea 23 evolution target**, with a game-based
     fitness (decision 19: never the label-and-sweep proxy).

## 60. Near-window extension

- **type:** ELO (search; runtime cost: nodes, not nps).
- **idea** (owner, 2026-11-07; plan only; tested after item 8a, before idea
  59's step 3): at frontier nodes (depth 1, main search only at first) whose
  static evaluation lies within a narrow margin of the window, extend by one
  ply instead of trusting the evaluation; at most one such extension per
  line. It is complementary to idea 59: search verifies tactics, the
  refiner improves judgement.
- **basis:** a frontier node's result decides a comparison with a bound, and
  an evaluation error flips that comparison with a probability that grows as
  the evaluation nears the bound (idea 48's argument). Far from the window
  the evaluation's error cannot change the outcome; near it, one more ply
  turns a static guess into a short search, which resolves the tactical part
  of the error (captures and threats one move deeper than quiescence sees).
  Step 1 of idea 59 measured where those sites are (DESIGN.md §5.7 on
  branch measure/step1): depth 1 holds about two thirds of main-search
  computed evaluations, and 11.9% of depth-1 evaluations lie within 25 cp of
  the nearest finite bound (1.17% of nodes); the main-search share within
  10 cp is 4.2% overall. The limit of one extension per line bounds the
  search growth, as for singular extensions, which Fork already has.
- **node-cost model** (to be measured first): extending a depth-1 node
  replaces its subtree by a depth-2 one, about b_eff times larger
  (b_eff being the effective branching factor of a depth-1 subtree,
  quiescence included), so the added nodes are about
  f x (b_eff - 1) x s1, with f the share of depth-1 nodes extended and s1
  the share of all nodes inside depth-1 subtrees. With rough placeholders
  (b_eff about 3, s1 about 0.65; both UNVERIFIED), 25 cp
  (f about 0.12) costs about 15% of nodes and 10 cp (f about 0.05) about
  6%: so the kill line sits near the 25 cp margin, and the measurement
  decides.
- **literature:** extensions and their explosion control (Chess Programming
  Wiki, "Extensions"; singular extensions, Anantharaman, Campbell and Hsu,
  1990); frontier-node pruning, the opposite decision at the same nodes
  (Heinz, "Extended Futility Pruning", ICCA Journal 1998) (UNVERIFIED as
  exact citations). The gate itself is Fork's own (from idea 59's
  measurement).
- **first experiment:** from the step 1 tooling, the node cost at 10 and
  25 cp: a stats-build replay counting, at each gated depth-1 site, the
  nodes the depth-1 subtree took and the nodes a depth-2 search of the same
  node takes (the decision ledger's side-search machinery, X10, can supply
  the second); the 200k replay games of step 1. Then the margin by
  head-to-head selection (decision 3; 10 against 25 cp, the declared value
  the cheaper one), then a design R SPRT (decision 2) of the chosen margin
  against off.
- **kill criterion:** the node cost at the chosen margin above about 15%,
  or the SPRT fails (H0 or the futility stop).
- **phase:** Phase 4, after item 8a, before idea 59's step 3. **metric:**
  the measured node cost, the head-to-head pick, the design R SPRT (and LTC:
  an extension, on the LTC-sensitive list). **status:** **rejected
  (2026-11-08): the design R SPRT of 10 cp against off failed (H0, −5.43 ±
  7.25 Elo, 3,200 games, try 1 of 2), so by the kill criterion idea 60 is
  retired**, with no second try (owner, 2026-11-08); before it, the node cost passed (10 cp +6.2% / +5.6%) and the
  head-to-head kept 10 cp (25 − 10 −3.24 ± 12.04 nElo); docs/history/phase-4/sprt-log.md.
  (Plan: owner, 2026-11-07.) **runtime cost:** possible (more nodes per move at
  equal depth; nps unchanged). **earliest phase:** Phase 4.

## 61. Boundary-gated decisions

- **type:** ELO (search; runtime cost possible).
- **idea** (owner, 2026-11-08; plan only, after idea 59's refiner exists):
  apply idea 59's window principle to the search's own decisions, spending
  the refiner where a decision can flip. In order, each measured and
  SPRT-tested on its own:
  1. **Refiner-checked pruning:** when a prune's evaluation (reverse
     futility, futility, razoring and the like) lies within a narrow band
     of its threshold, consult the refiner before pruning, and prune only
     if the refined evaluation still clears the threshold.
  2. **Quiescence checks only near the window:** generate quiet checking
     moves in quiescence only at nodes whose evaluation lies near the
     window.
  3. **Near-window deep labelling for training data:** spend the deep
     labeller's budget on positions near the window (the refiner's own
     training data, and possibly the base net's).
  4. **Later, a gated move scorer** (idea 54's policy head), consulted only
     at nodes near the window.

  **Further applications** (owner, 2026-11-08), each its own experiment,
  after the refiner exists or sooner where none is needed:
  5. **Window-aware LMR** (no refiner needed): reduce less when the move's
     evaluation is near alpha; its constant by head-to-head selection.
  6. **Root-gap time management:** extra time when the top two root moves
     are near-tied; it complements the stability time management (R8).
  7. **Window-gated tablebase probing** for TCEC's 7-man tables: probe
     only near the window; measure the probe cost first.
  8. **TT replacement favouring near-bound entries:** tested at a
     TCEC-scaled hash (decision 23).
  9. **Near-window oversampling in data generation's save decision.**

  **Priority** (owner, 2026-11-08): borderline pruning (part 1) first, then
  window-aware LMR (5), then root-gap time management (6), then the rest.
  Linked follow-ups (the boundary controller, boundary distillation,
  conformal margins, closeness-weighted base training, site selection and
  the gate policy as an evolution target) are listed under idea 59.

  **Independence from idea 59's cost gate** (owner, 2026-11-08): the
  refiner-independent applications proceed whatever step 3's cost gate
  decides: idea 60 (the near-window extension), window-aware LMR (part 5),
  root-gap time management (part 6), window-gated tablebase probing (part
  7), near-bound TT replacement (part 8), near-window data saving (part 9),
  conformal margins (follow-up 3) and closeness-weighted base training
  (follow-up 4). **If step 3 pauses**, part 1 (refiner-checked borderline
  pruning) switches to a short verification-search variant: a near-threshold
  prune is confirmed by a short search instead of a refiner call.
- **basis:** idea 59's control split (2026-11-08, ideas.md idea 59): at
  equal call rate the window-gated refiner beat a random gate by about 22
  Elo at fixed nodes, and a constant shift lost, so a better evaluation
  pays where a comparison with a bound can flip. A prune is such a
  comparison (an evaluation plus a margin against alpha or beta), so the
  same gate should find the prunes most likely to go wrong. The DESIGN
  Focus note (2026-11-07) asks for exactly this kind of selectivity, and
  the crucial-point ground truth (measure/step1, daca926: 18.6% of sampled
  evaluation sites have the static evaluation and the deep value on
  opposite sides of the nearest bound) is the measurement to reuse.
- **first experiment (part 1):** with the stats build, count each prune
  kind's firings whose evaluation lies within a band of its threshold, and
  how often a deep search disagrees with the prune there (the crucial-site
  method applied to prunes); then build refiner-checked pruning for the
  kind with the most wrong prunes per refiner call, behind a switch, with
  the band chosen by head-to-head selection.
- **kill criterion:** per part: the part's design R SPRT fails (H0 or the
  futility stop), or its node or nps cost eats the gain (the speed gate,
  1.5 Elo per 1% nps). Part 1 is dropped before building if the
  measurement finds wrong prunes near the threshold no more often than
  elsewhere.
- **phase:** Phase 4 or later, after idea 59's step 3 passes. **metric:**
  wrong-prune rates near the threshold, then each part's SPRT. **status:**
  untested (plan only, owner, 2026-11-08); **part 5 (window-aware LMR)
  rejected (2026-11-08): the head-to-head kept the 10 cp band at depth >= 6
  (d0 - d6 -2.19 +/- 12.04 nElo), and its design R SPRT against off stopped
  for futility after stage 3 (-2.93 +/- 7.16 Elo, 3,200 games, try 1 of 2),
  so by the kill criterion part 5 is retired**; docs/history/phase-4/sprt-log.md.
  **runtime cost:** possible (refiner calls at pruning sites). **earliest phase:** Phase 4.

## 62. Label depth at equal generation time

- **type:** ELO (data generation; no runtime cost).
- **idea** (owner, 2026-11-09): do fewer positions with deeper saved
  searches (50,000 or 100,000 nodes) make a better network than more
  positions at the standing 20,000, at equal generation CPU? Unsaved and
  in-check searches stay at 4,000 and 2,000 nodes.
- **design:** docs/research/labels-teacher/report.md §1 (branch
  research/labels-teacher): three arms D20, D50, D100 side by side, 3
  threads each for 40 hours (120 thread-hours each), Hash 1 / 3 / 5 MB, one
  PGO build and one seed; predicted 36.2 M, 16.2 M and 8.5 M kept positions
  (estimates from g3's node model); B0 small nets, two seeds per arm,
  idea 13's recipe; seed-paired fixed-node stages (1,600 games each, 800,000
  nodes per move).
- **decision rule (declared in the design):** a deeper arm wins only at
  +5 Elo or more against D20 with its 95% interval above 0 (pooled over
  both seed pairs), then an STC network SPRT [0, 5]; otherwise 20k stays.
  A pass is a recommendation; the setting change is the owner's.
- **cost:** about 360 thread-hours, 3 T4 GPU-hours, 4-6 fixed-node stages,
  about 3 days; about 47.7 M kept positions of production forgone (the arm
  data stays usable).
- **status:** **approved (owner, 2026-11-09): starts after retrain 8b
  launches**, with a 30-minute rate probe first, then the arms as designed
  under the declared rule. **runtime cost:** none. **earliest phase:**
  Phase 4.

## 63. Ensemble teacher

- **type:** ELO (training data; no runtime cost in the TCEC binary).
- **idea** (owner, 2026-11-09): label or relabel training data with the
  averaged evaluation (with search) of 3-4 independently initialised S512
  networks, against the same-network bias of labels made by the default
  net alone (the bias idea 51's pre-test could not measure).
- **design:** docs/research/labels-teacher/report.md §2: E3 = S512ppr3 and
  item 7's two scratch seeds (no new GPU time); separate searches averaged
  in win probability (no engine code) or one search on the averaged
  evaluation (engine code later); staged: step 0 offline, step 2 small nets
  at equal data against the default searching to equal total nodes, step 3
  data generation. Compared with idea 58 in the design (cheaper at every
  stage; both share the lineage's label bias).
- **status:** **step 0 ordered (owner, 2026-11-09): run now, report before
  any small nets**, including the TD pre-test's measured same-network bias.
  Declared before any label in docs/research/labels-teacher/step0-declaration.md
  (dc90302): golds by both scratch seeds at 1M nodes on idea 51's set H,
  labels at 20k-100k on H and a new H2 (20,000 g3j-w05-val games), the gate
  to step 2. **Step 0 result (2026-11-09, 6:47-9:27 PM EST; docs/research/labels-teacher/step0-results.md,
  branch research/labels-teacher 1721493): killed by the declared gate.** S512ppr3 searching 60k nodes beats E3
  (three members at 20k each, equal total nodes) on both yardsticks: Y1 (Brier against results, 15,499 kept records)
  E3 - 60k +0.001111 [+0.000858, +0.001362]; gold-mean Y2 (3,131) +0.000455 [+0.000300, +0.000620]; all three 1M golds
  agree. Averaging helps against one 20k search, but by about a quarter of what three times the nodes on one net
  buys. No small net is trained. The same run measured idea 51's same-network bias: about zero (results-8b.md,
  idea51/td-labels 68d1527). **runtime cost:** none. **earliest phase:** Phase 4.

## 64. Score-fall time extension

- **type:** ELO (time management).
- **idea** (owner, 2026-11-09): beside idea 61's root-gap time, extend the
  soft limit when the root score fell over the last two finished
  iterations.
- **design:** docs/research/eval-trend-tm/design.md: fall = the drop over
  two iterations from depth 8, mate and table scores excluded; an
  extension factor up to ScoreFallExtra (placeholder 667 per mille) at
  ScoreFallSpan (placeholder 16 cp), combined with root gap by the larger
  of the two and multiplied onto time management (b); switch
  UseScoreFallTime, off by default. Names and constants screened
  (2026-11-09): no specific match. Fork's data: the signal is real, but an
  equal-time replay showed no gain over (b) (expected 0 to +4 Elo at STC,
  a judgement).
- **status:** **parked (owner, 2026-11-09)**: the design and the screened
  names are kept; implemented and queued only if GitHub is idle (test plan
  in the design: head-to-heads of span and extra, then design R at STC and
  LTC, after idea 61's items 60-62). **runtime cost:** none. **earliest
  phase:** Phase 4.

## Go-derived training ideas (owner, 2026-11-09)

Three training ideas taken at concept level from KataGo (David J. Wu,
"Accelerating Self-Play Learning in Go", arXiv:1902.10565, 2019; credited
as the source; UNVERIFIED as exact descriptions of the paper). Plan only:
each waits for the conversion-and-defense analysis
(docs/research/conversion-defense/, branch research/conversion-defense),
whose weaknesses and data gaps decide their targets and order.

## 65. Auxiliary training targets, revisited

- **type:** ELO (via the resulting net; training only).
- **idea:** training-only output heads beside the evaluation, for example
  the material balance some plies ahead, whether the game ends drawn, and
  the change of the search's evaluation between iterations; the heads shape
  the shared layers and are dropped from the inference net, so the shipped
  net has the same size and speed. This revisits idea 14 (untested) with
  targets chosen from the conversion-and-defense findings.
- **test:** a retrain arm (equal data against the control in a retrain
  round), screened per the testing rule; verify the shipped net is
  identical in size and speed (file size, layer shapes, bench nps).
- **needs:** the trainer's support for extra heads and the targets in the
  data (material ahead and the result are in the game records; the
  iteration change needs a datagen field).
- **status:** untested (plan only, owner, 2026-11-09; after the
  conversion-and-defense results). **runtime cost:** none. **earliest
  phase:** Phase 4.

## 66. Turning-point starts

- **type:** ELO (data generation).
- **idea:** start self-play games from positions where Fork's evaluation
  swung, or where it failed to hold a worse position (the
  conversion-and-defense analysis's turning points and defense failures,
  from Fork's own games only), so the data covers the positions that
  decide games; folded into the defense-data design.
- **data policy:** the starting positions come from Fork's own games (its
  self-play and SPRT games); positions from games against other engines
  are analysed, never used as training data or starts.
- **test:** a data arm at equal data in a retrain round, screened per the
  testing rule.
- **status:** untested (plan only, owner, 2026-11-09; after the
  conversion-and-defense results). **runtime cost:** none. **earliest
  phase:** Phase 4.
- **2026-11-10 (owner; DESIGN.md decisions log):** approved as the
  analysis's fixes 1 and 2, generated in one run: a **positional-advantage
  slice** (queens on, equal pieces, level or one pawn apart, |label| 80-400
  cp) and a **defense-start slice** (the side to move at -100 to -300,
  queens on), both drawn from Fork's own datagen records and played out at
  80,000 nodes with adjudication raised (report.md: 1,500 cp over 16
  plies, no decided-opening cut). **A pilot first** (about 16 CPU-h); the
  full slices (about 120 + 60 CPU-h) only if the pilot's rates and label
  checks look right; then **arms in retrain 8c** (fixed-node screen, STC
  SPRT [0, 5]). Fix 3 (R32's endgame-start slice, widened) waits for this
  result.
- **pilot, gold half (2026-11-10; research/defense-slices 5e42e4a):**
  9.6 CPU-h per million positions; the positional slice passed every
  declared check (gate +0.030 [+0.021, +0.040]); the defense slice failed
  check 3 (defenders hold 6.4%, minimum 10%). **Owner, 2026-11-10:** the
  positional slice at 12.5 M positions (~120 CPU-h); **the defense slice
  dropped for 8c**, no redesign now (a near-level band only if 8c's
  positional arm shows defense still lacking); the positional main pilot
  run first, the full slice only if it passes and after the label-depth
  arms.

## 67. Draw-probability head

- **type:** ELO (via the resulting net; training only).
- **idea:** a training-only head predicting the probability that the game
  is drawn, so the shared layers learn which worse positions are holdable
  (the defense failures); dropped at inference, no speed cost.
- **test:** a retrain arm at equal data, screened per the testing rule;
  report the head's calibration on held-out games.
- **status:** untested (plan only, owner, 2026-11-09; after the
  conversion-and-defense results). **runtime cost:** none. **earliest
  phase:** Phase 4.

## 68. Endgame slice v2 (ChessTB-labelled 6-7-piece positions)

- **type:** ELO (training data).
- **idea** (owner, 2026-11-09): random legal 6-7-piece (and selected 8-piece) positions in the material classes where
  Fork errs most (rook endings, rook against a minor, queen endings and queen imbalances, piece against pawns),
  labelled by ChessTB WDL, replacing half of the current 3-5-piece Syzygy slice so the slice stays 2% of a retrain.
- **design:** docs/research/endgame-slice-v2/design.md (branch research/endgame-slice-v2); facts and the data-policy
  line in the KB's chesstb.md (adopted, DESIGN.md training-data decision 1).
- **decisions (owner, 2026-11-09):** budget R (about 97 GiB downloaded, 34.5 GiB peak); the arm in retrain 8c; the
  pure-Python prober first, the C++ library only if labelling would exceed about a day; tables in WSL; the class shares
  wait for the final conversion-and-defense numbers.
- **keep rule (declared 2026-11-09, before any data):** v2 is kept if its arm's fixed-node screen interval is not
  entirely below 0 AND the held-out 6-7-piece misjudgment falls by at least 25% against the control arm.
- **status:** untested (designed; data generation after the conversion-and-defense results and before 8c).
  **runtime cost:** none. **earliest phase:** Phase 4.

## 69. Class-weighted sampling in the trainer

- **type:** ELO (training).
- **idea** (the conversion-and-defense analysis's fix 4, 2026-11-10): weight
  each training position by its material and structure class so the
  classes that decide games (queens-on middlegames with level material,
  equal pieces with level pawns, queens-on bishop against knight, passers
  on both sides) are seen more often, and the over-represented ones
  (rook-and-minor endings a piece up, queens-on a minor up) less; weights
  capped (report.md proposes 2x up and 0.5x down), normalised to equal
  positions seen. No new data generation.
- **evidence:** report.md item 5 (matched ratios 2.3-3.96 for the
  under-trained classes, 0.18-0.64 for the over-trained ones).
- **decision (owner, 2026-11-10):** a design review of the loader change
  first, then an arm in retrain 8c.
- **design review approved (owner, 2026-11-10; DESIGN.md decisions log):**
  docs/research/class-sampler/design.md (research/class-sampler f235d27),
  recommendations 1-9 as written (per-position loss weights, board-only,
  material class alone, all deciding positions as the target, small cells
  at 1, separate arms, a second control seed if the quota allows, no
  validation-loss kill rule), **with the conversion-failure classes (rook
  against minor pieces, queen imbalances, a piece against pawns, one-wing
  structures as the report classifies them) floored at 1.0 instead of
  0.5**, the scale re-solved to a mean weight of 1. **Keep rule (declared):
  +5 Elo head to head against the control, or a passing STC SPRT.**
- **after the pre-arm checks (owner, 2026-11-10):** 4 checks pass (class
  function, item 5's counts exactly, weighted shares, CPU determinism);
  all-ones against the control needs CUDA (a Kaggle preflight); the
  floors are **narrowed to the conversion-failure material classes**
  (rook against minors, queen imbalances, a piece against pawns as
  implemented: minor-EG with a minor up), **one-wing structures no
  longer floored**; the speed gate is **trained positions/s within 1%
  of the control's on Kaggle** (replacing the 3% CPU bound, which the
  CPU mapper missed at +4.95%). The trainer change merges only with the
  owner's OK.
- **2026-11-10 (owner): the arm runs now as an extra retrain 8b arm
  ("cw")**, on arm c's exact data, recipe and seed, after a Kaggle
  preflight; compared against 8b's control by the keep rule above.
- **test:** the 8c arm at equal positions against the control; per-class
  validation loss; fixed-node screen, STC SPRT [0, 5].
- **status:** **dropped (owner, 2026-11-11).** The cw arm (bake/r8bcw
  9fd957b): fixed-node screen against S512ppr3 +3.04 ± 9.74 (run
  42940727058), head-to-head against the control r8bc +3.04 ± 9.25
  (42945518194), then its STC SPRT r8b-stc-cw [0, 5] against r8bc **H0
  accepted, −7.60 ± 4.91 Elo** (nElo −13.18 ± 8.51) after 4 stages, 6,400
  games, LLR −4.16 (runs 42949849410 to 42955981034; sprt-log). Its
  second-seed control c2 (bake/r8bc2 38155d9) measured the seed noise:
  c2 against r8bc −6.08 ± 9.42 (1,600 games at 800,000 nodes, run
  42958000486), so **every future retrain arm runs 2 seeds** (owner,
  2026-11-11). **runtime cost:** none. **earliest phase:** Phase 4.

## 70. Result fine-tune of the base net

- **type:** ELO (training).
- **idea** (owner, 2026-11-10; from the clean-room engine survey 2026-11,
  concept level): fine-tune the base net with a 100% game-result target
  (no search-score target) at a low learning rate, as Ethereal reports
  (+42.7 STC / +35.6 LTC on its own net, one engine's self-report); several
  engines report smaller gains from result-weighted final stages.
- **plan:** right after retrain 8b's SPRT decides the base net, fine-tune
  the winner (td90 or the control) on existing 8b data, two seeds; the
  usual gates; a fixed-node screen against the base; an SPRT. Kaggle hours
  reported to the owner before the launch.
- **status:** **adopted: r8brft1 is the default network (owner,
  2026-11-11).** **2026-11-10:** 8b's SPRT decided the base net: r8btd90
  (the TD(0.9) arm, promoted), so the fine-tune starts from it. The run
  (docs/research/retrain-8b/rft-plan.md, branch retrain/8b-rft 43f6ecc):
  r8btd90's window average, result weight 1.0, LR 1e-5 constant, 60
  superbatches on g4s1, the mean of superbatches 46-60, seeds 1 and 2.
  Fixed-node screens against r8btd90: seed 1 +7.17 ± 9.93 (run
  42962187538), seed 2 +6.73 ± 9.44 (42966665389); seed 1's STC SPRT
  [0, 5] against r8btd90 **H1 accepted, +5.74 ± 3.81 Elo** (nElo +9.69 ±
  6.43) after 11,200 games (r8b-rft-stc; sprt-log); the endgame check 7
  of 900. Bench 10,708,227 / c5dfc0ec1923d3b0 (docs/nets.md). **runtime
  cost:** none. **earliest phase:** Phase 4.

## 71. Feature-transformer weight decay

- **type:** ELO (training).
- **idea** (owner, 2026-11-10; engine survey 2026-11, concept level): weight
  decay on the feature transformer's weights in the trainer, as Stockfish's
  recent trainer change reports (+4.0 STC / +5.3 LTC there).
- **plan:** a candidate arm for retrain 8c, at equal data against the
  control; the testing rule's screen, then the STC SPRT.
- **status:** untested (8c candidate). **runtime cost:** none. **earliest
  phase:** Phase 4.

## 72. Threat-aware quiet ordering, the any-attack set (tier 2, T56)

- **type:** ELO (search); flag `use_threat_buckets` (off).
- **idea** (KB search-techniques.md §3.34, its first family): the butterfly
  history split into four buckets by whether an enemy piece attacks the
  quiet move's from-square and its to-square in the position before the
  move ("any enemy attack"); read and update use the same bucket.
- **history:** built on tier2/batch3 (740c6cc, 2026-11-02) with a second
  set, the cheaper-attacker set (2f6f4ac). The offline measurement
  (tools/tier2_measure/threat_set.json, d5a6eb6) put both below off; the
  cheaper set was SPRTed and rejected (H0, −6.08 ± 3.59 after 12,800
  games, 2026-11-06; sprt-log "threat-set-cheaper-vs-base"). The
  any-attack set was never game-tested.
- **status:** untested; **first game test queued (owner, 2026-11-10):
  "first game test, not a retest"**. The offline measurement is no longer
  treated as decisive. Ported onto phase-4 b787fba (r8btd90) behind the
  switch, off (tier2/threat-any dc341d5, bench unchanged 9,594,307); test
  side sprt/threat-any bfbc1c8 (bench 9,236,850 / 0f723ee4c163a419).
  Design R STC SPRT `t56-any-stc` (ledger idea `t56-any`, try 1 of 2),
  night queue item 63, after root-gap's items 60-62. Nothing is adopted
  before its verdict; an H1 goes to the owner (LTC next by the owner's
  rule). The cheaper-attacker set stays closed.
- **runtime cost:** possible (an attack map built once per node that
  reaches its quiets or a quiet cutoff; the butterfly table grows from
  16 KB to 64 KB). Speed not yet measured (UNVERIFIED); the SPRT result is
  to be reported with its nps change (the 2026-10-24 rule).
- **earliest phase:** Phase 4.
