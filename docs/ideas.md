# Ideas log

Candidate improvements, each with the evidence needed to adopt it.

## Fields

| Field | Meaning |
|---|---|
| **type** | **ELO**: a playing-strength change. It's measured by SPRT and sits behind a config flag until accepted. **TOOLING**: infrastructure measured by its own success metric. No flag needed. |
| **phase** | When the idea is scheduled. |
| **metric** | What decides success (SPRT result for ELO; the stated metric for TOOLING). |
| **status** | untested, in progress, accepted, rejected (with the evidence). |
| **sources** | References consulted. Every outside source is also logged in docs/ORIGINALITY.md. Ideas only, never code. |

There were no entries before 2026-10-23, so no existing entries needed
marking as ELO. New ELO ideas use the same fields, with type ELO and the
name of their config flag.

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
- **status:** untested

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
- **status:** untested

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
- **status:** untested

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
    HANDOFF.md, harness fix.
  - **v5** (6 check-square entries, State 136 B, no State alignment, uint8
    mailbox): the gives_check regression is gone. make/unmake min -4..-5%,
    null move -5..-8%, gcc is_pseudo_legal min +5%. All verdicts "no
    significant difference" under the noise threshold.
  - Assembly (position.cpp at -O3 -march=native, both compilers): the uint8
    mailbox adds no conversion instructions (`movzx BYTE PTR` replaces
    `mov DWORD PTR`; instruction counts slightly lower).
- **decision (owner's rule):** not clearly better on both compilers, so main
  keeps its layout plus the uint8 mailbox (harmless, 192 fewer bytes per
  Position). v5 is kept on branch `layout-exp` (97ab028) for Phase 3
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
  3090058 vs 9a5031b, release -march=native, 2 runs x 6 rounds per compiler):
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
- **status:** deferred to Phase 3

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
- **status:** untested (7-piece requirement set)
