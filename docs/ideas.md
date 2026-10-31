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
  (KataGo), arXiv:1902.10565 (title, author and abstract checked on
  2026-10-24; that its full text describes playout cap randomization is
  UNVERIFIED: the PDF could not be read here and ar5iv did not respond).
- **status:** experiment approved and running (owner, 2026-10-30;
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
  about 10.2 throughout (the manifest's part_end). Arm B is run g2b.

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
  example; which auxiliary targets it uses is UNVERIFIED for the same
  reason.
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
