# Audit-1, Phase B: reconciled findings

The list the owner approved on 2026-10-27, kept as the record behind
audit-1.md, which gives each item's outcome. It was untracked until the
Phase 3 end and is committed unchanged below this note (2026-10-28). When
it was written, branch `audit-1` was main at 6b04ed5 (bench 17309921 /
372dc2e2d8a88e4b) with nothing changed yet. The auditors' full reports,
patches and proof worktrees it names were session files and are not kept.

**Sources.** Ten Phase A auditors ran in parallel, each in its own worktree:
A1 search, A2 performance, A3 robustness, A4 TCEC/originality, A5 tests,
A6 tooling, A7 docs, A8 behavior, A9 refactoring and A10 past reviews. A
separate throwaway agent (A4b) then screened names and constants against
Stockfish, Ethereal, Berserk and Weiss. A4b used 15 shallow clones, reported
matches only and deleted the clones; the deletion was verified. No audit
agent opened another engine's source. The full reports, patches and scripts
are in the session scratchpad (`audit/A*.md`, `*.patch`). The failing proof
tests are uncommitted in `.claude/worktrees/agent-*`.

IDs: `S-` A1, `P-` A2, `R-` A3, `T-` A4, `Q-` A5, `U-` A6, `D-` A7, `B-` A8,
`F-`/`A9-` A9, `V-` A10. Where several auditors found the same thing, the
item lists every ID.

**Bottom line.**
- **Search: no correctness bug.** About 2,300 UCI searches were checked with
  python-chess, plus 210 tablebase root positions against python-chess's
  Syzygy reader, mate-score round trips and 18 self-play games with full
  history: 0 problems.
- **Past reviews: no regressions.** 61 of 68 recorded items were re-verified
  by fault injection.
- **TCEC build:** clean with all four compilers from a fresh offline clone,
  and every one gives bench parity.
- **Public history:** clean over all 186 commits.
- **The real problems are elsewhere:**
  - the tooling: sprt.sh, the evolve gate and update.sh;
  - tests that pass on broken code: 25 of 58 mutants survived;
  - stale records;
  - new constant matches to record or change.

---

## 1. Bugs, by severity

Effort: S < half a day, M about a day, L more. "Bench" = whether the fix
changes bench. Behavior-changing fixes get SPRT [-3, 0].

### Critical
None.

### High

| ID | Area | What and where | Evidence | Impact | Proposed fix | Effort | Bench |
|---|---|---|---|---|---|---|---|
| U-1 | tooling | `tools/sprt.sh:122-123` aborts under `set -u` when `BASE_OPTS` or `TEST_OPTS` is unset (added in 573020b) | It happened in the d8-final and mc-final queue logs ("BASE_OPTS: unbound variable", exit 1). Reproduced with a fake fastchess. | Every plain commit-vs-commit SPRT loses its log entry. The sprt-log blamed the d8-final cut-off on the stop, and the d8-ltc entry was rebuilt by hand. | `${BASE_OPTS:-}` and `${TEST_OPTS:-}`, plus a dry-run test with a fake fastchess | S | no |
| U-2 | tooling (idea 23) | The evolve gate cannot keep a candidate inside the LMR region. The guard (`gate.py:263-267`) is tautological, and the static rules miss several escapes: digraphs (`%:define`), a body that closes the function, `.5`/`1.f` floats, code after a `"//"` string, and `make_unique`. | Three candidates compiled with Fork's `-Werror` flags. Preprocessed, the digraph one turns `searcher.cpp:310` into `rule * 640 / 64`, outside the region. 5 failing tests in `tools/evolve/test_audit_a6.py`. | Gains could be credited to the wrong code. Hidden global state also passes the determinism check. **Must be fixed before the idea 23 long run.** | Lex the body properly (strings before comments). Reject digraphs, trigraphs and line splices. Require balanced braces that never go below 0. Broaden the float and allocation patterns. Best: compare the preprocessed searcher.cpp outside the body. | M | no |
| T-1 | TCEC build | In clone mode, `update.sh:28-39` swallows a failed `merge --ff-only` and exits 0. A `FORK_REF` branch name resolves to the local branch, which never moves. | Toy upstream: after a force push to 61d79fc, update.sh still built 6b04ed5, rc=0 (`a4-ff-test.log`) | After a history rewrite or force push (both have happened before), TCEC would build an old Fork with no error. Low probability, high impact. | Check out `origin/$ref` (then a tag or commit) explicitly, `fetch --force`, and fail loudly. Add a toy-upstream test. | S | no |
| Q-1 | tests | Nothing tests that the soft time limit ends a search | Deleting the soft-limit break (`searcher.cpp:665`, mutant M57) passes every test and bench parity | A regression would make every clock move run 2.5-4x its plan, and every SPRT time control would be distorted | A5's proof test, plus a UCI check that a clock `go` ends between the soft and hard limits | S | no |
| Q-2 | tests | UCI output is only syntax-checked: `valid_engine_line` accepts any 2-token `info` and any move-shaped `bestmove`. `write_move_text` is a second move printer that no UCI test exercises on castling. | Mutants that survive: castling printed `e1h1` (M47), `score mate 29999` (M46), PV cut to one move (M28) | An illegal bestmove loses at once, and a wrong mate score can end games through adjudication | Replay every `pv` and `bestmove` in `Gui::check_transcript`; A5's castling and mate-1 tests | S | no |
| Q-3 | tests | The fifty-move clock after a capture is untested (M01 survives, bench included), and so is the rule's exact boundary (M05, `>=` to `>`) | Mutation run, plus A5's proof test (killed by M01, M02, M05) | M01 would silently turn off every Syzygy probe after a capture, because probes need halfmove 0 | A5's proof test | S | no |

### Medium

| ID | Area | What and where | Evidence | Impact | Proposed fix | Effort | Bench |
|---|---|---|---|---|---|---|---|
| R-1 | engine | A SyzygyPath ending in the separator (`a;`, `/x:`, or just `;`) makes Fathom's `tb_init` read past its buffer (`tbprobe.c:886-901`), reached from `endgame_tables.cpp:71` | ASan: heap-buffer-overflow, no readyok, exit 1 (test `uci_audit` R-1) | Undefined behaviour on user input. TCEC's `/home/syzygy7` is safe; testers and multi-directory GUIs are not. | Drop empty path parts in `load_endgame_tables`; Fathom stays untouched | S | no |
| A9-2 | tuning builds | `UsePvs=false` also turns off LMR and every non-PV pruning in the PV subtree (`searcher.cpp:281-331`, `can_prune`) | Kiwipete at depth 7 (nodes): 49,187 normal; 2,585,319 with PVS off, whether LMR is on or off | The end-of-Phase-3 removal SPRT of `UsePvs` would measure three features at once. Release play is unaffected. | **Owner's choice:** (a) document it and leave PVS out of the removal round, or (b) decouple, so later moves become non-PV children with the full window. Add a test either way. | S | no |
| D-3, A9-1 | tuning builds | `UseTables` is not a UCI switch: 17 switches are declared (`session.cpp:183-196`), but DESIGN.md:1374 and the `sprt.yml` example name it | A FORK_TUNE build's `uci` lists no `UseTables` | The removal round cannot toggle tables, and an SPRT run as the sprt.yml example shows compares identical engines | Add it, best through F-5 (one switch list) | S | no |
| P-1 | speed (TCEC) | `lmr_move_facts` runs at every LMR site (2.3 M per bench) with g++ 11.4 + LTO, and with any build without LTO. Its result is unused, since the committed rule returns 0. | Disassembly of `negamax<false>` from the update.sh build with g++ 11.4; only clang + LTO removes it | Wasted work on a TCEC compiler (code-reading estimate about 2%) that grows as the evolve loop adds context inputs | Compute the facts lazily, only when the rule reads them. Add an objdump check to the evolve gate on gcc too. | S | no (A/B) |
| D-1, S-1, V-1, T-12 | docs | DESIGN.md:1712 (review 1(a)) says "Fixed (f0a9caf): the pending fail high is played". It was reverted in 1fb18f4 after the SPRT (-14.6 ± 10.8), and the decisions log has no row for it. | `git show 1fb18f4`; `searcher.cpp:628-635`; `test_search.cpp:552` asserts the opposite | The spec misdescribes root move choice | Amend the row and add a decisions-log row | S | no |
| D-5 | process | rv-failhigh was rejected on STC alone (stopped by the owner at LLR -0.95). DESIGN.md:1056 says an STC failure gets an LTC retest. | sprt-log; ideas.md idea 29 | The rule was not followed; an LTC gain could be lost | **Owner:** record an exception, or queue the LTC retest (with idea 29) | S/L | — |
| D-2 | process | DESIGN.md:999 says SPRTs give both sides 3-4-5 Syzygy after deliverable 7. Neither sprt.sh nor run_shard.sh passes a SyzygyPath. | grep; the d8-final and d8-ltc headers | Every SPRT since deliverable 7 ran without tables, which differs from the spec and from TCEC | **Owner:** add `option.SyzygyPath` (local and cloud; the cloud runners need the 3-4-5 set), or amend the spec | S | no |
| D-4, T-2 | originality | README.md:16-17 and ORIGINALITY.md:5-6 say Fork contains "no source code ... from other engines". The vendored Fathom is de Man's Stockfish/Cfish-lineage code, and the README credits neither Fathom nor the Berserk-shaped time budget. | The cited lines; `grep -i fathom README.md` is empty | A judge would quote the blanket claim, and TCEC's questionnaire asks exactly this | Qualify both sentences, and add a "Third-party code and credits" section to the README | S | no |
| T-3 | originality rule | The time-budget constants 30, 40, 4 and 1/10, and the 3/4 increment factor (`params.hpp:55-58`, `time_budget.cpp:68`), have no recorded justification. The table row points to notes that only restate them. A4b confirms that 30, 4 and 0.9 match Berserk 4.5.0/8; the match is already credited. | The cited lines; the A4b rows 28-34 | Breaks non-negotiable 6 for the very constants that match another engine | Record reasoning or a quick measurement for each (2+0.02 stress data, bench), with a row for 3/4; or replace them with measured values (an SPRT if they change) | S-M | no, unless the values change |
| A4b | originality (new matches) | **`RfpMargin` 80 per ply up to depth 6 = Berserk 4.5.0's RFP margin** (the 2026-10-25 screen recorded only near matches). **Move Overhead 100/0/10000 = Ethereal v12.75's option**, all three values (the Phase 2 limits were changed once already for matching Stockfish). `MaxFullmoveNumber` 100000 = Stockfish master's FEN bound (not a strength value). New near matches, all new to ORIGINALITY.md: `LmrMinMove` 4, `FutilityMaxDepth` 6, `SeePruneMaxDepth` 6, the cursed-win score 1, and the SPSA step rule range/20. | A4b report §5 | Fork's own rule: model memory reproduces famous values | **Owner:** for each, keep it with a record and its existing justification, or change it. A change to RfpMargin or the default overhead changes play (SPRT); a change to the max or to MaxFullmoveNumber does not. Record every item in ORIGINALITY.md. | S | depends |
| U-3 | tooling | Cloud SPRT stages play the book in file order from line 1 (`run_shard.sh:175-194`), and that slice is unrepresentative: lines 1-800 have 30% of openings at fullmove ≤ 4, against 1.8% in the whole file. Local sprt.sh uses random order. | `book_order.py` on the pinned EPD | Cloud verdicts are taken on a biased opening sample and are not comparable with local runs | A fixed-seed permutation of the book, its SHA pinned and the seed recorded in the shard meta | S | no |
| U-4 | tooling | `sprt_merge.py` refuses only shards with identical start indices; overlapping ranges merge silently (stages with different game counts, AWS mixed with GitHub) | 2 failing tests (`tools/cloud/test_audit_a6.py`) | Repeated openings make the LLR slightly optimistic | Store `opening_end` and the book hash; refuse any intersection or mix | S | no |
| U-5 | tooling | The pre-commit hook's `stash --keep-index` / unchecked `pop` leaves conflict markers and an orphan stash when a file is partly staged. It also tests untracked files the commit does not contain, and the stash stack is shared across worktrees and sessions. | `stash_probe.sh` in a throwaway repo | Lost work or a wrong check, silently | Check an exported index (`git checkout-index` into a temp folder); never touch the working tree | M | no |
| U-6 | tooling | `check.sh`'s fingerprint and the pre-commit filter omit `third_party/` (compiled into the engine). Pre-commit also omits `update.sh` and `tools/dump_tables.cpp`. | `coverage_probe.sh` | A Fathom or update.sh edit commits without the full check, and "unchanged since last pass" is reported | One shared path list, including third_party | S | no |
| U-7 | tooling (idea 23) | The evolve loop dies on any single agent or subprocess error and cannot resume; a restart adds a second baseline at generation 1 | 2 failing tests | A 9 h, 3M-token run is lost to one transient error | Per-candidate try/except with an error status, retry with backoff, `--resume`, and refuse a non-empty run dir | M | no |
| U-8 | tooling (idea 23) | `baseline_commit: "HEAD"` is resolved again for every candidate build | 1 failing test | A commit during a run changes the code under later candidates, and the gains are misattributed | Resolve the hash once and store it in state and the DB | S | no |
| V-4 | tests | b89185f (the LMR context's history) and 00bed14 (no re-search after a stop) have no guarding test: reverting either keeps every test and bench green | Fault injection (A10) | Both matter for idea 23's judging | A test seam capturing `LmrContext`, and an exact node-limit test with a forced deep reduction | S | no |
| Q-4 | tests | GUI-sendable zero or negative `go` values are untested: no clamp on `movestogo` means division by zero and an engine crash (M38); no clamp on `go nodes 0` means it never answers (M44) | Both mutants survive; killed by A5's proof test | A crash or hang loses a game | A5's proof test | S | no |
| Q-5 | tests | Which side's increment is used, and Move Overhead, are unobserved by any test (M40, M42 survive) | Mutation run; A5's lower-bound test kills M40 | Wrong pacing in increment games, which is what TCEC plays | Move the clock assembly into a free function tested with numbers, plus A5's test | S | no |
| Q-6 | tests | Table tests cover only KPPPPPvK win and loss: draw, cursed win, blessed loss and promotion roots never run (M34-M37 survive). Without the download 4 of 5 cases SKIP and check.sh passes, though CMakeLists says they "fail loudly". | Coverage plus mutation; the renamed-cache run | Half-point errors in TCEC's 7-man endgames would be unseen | A few small pinned 3-5-man files, positions confirmed by the lichess API, tests of probe, score and root ranking; make a failed download fail. Needs a kb-researcher source check. | M | no |
| Q-7 | tests | 11 mutants are caught only by bench parity, among them real errors: a TT upper bound cutting on the wrong side (M12), a fail-low PV stored as exact (M13), mate-distance pruning one ply tight (M14) | Mutation run | Any commit that changes bench anyway could carry one in | Zero-window oracle probes at several betas, MDP mate positions, a TT bound unit test, a zugzwang NMP test | M | no |
| Q-8 | tests | Untested search branches: qsearch mate on the 100th half-move (M15), `score_from_tt`'s band clamp (M08), null-move mate distrust (M16), playing an unfinished iteration's lower-scoring move (M24), soft and hard limits while pondering (M26, M27) | Mutation run; A5's proof tests kill M15, M08, M26 and M27 | Wrong scores near the fifty-move rule and in deep mates; false mates | A5's tests, plus two new cases (M16, M24) | S | no |

### Low

| ID | Area | What | Fix | Bench |
|---|---|---|---|---|
| R-2 | engine | A failed allocation during `isready` loses the `readyok` (`session.cpp:320-336`). Test: "1 readyok for 2 isready". | In the catch, answer `readyok` when the line was `isready` | no |
| R-3 | engine | A failed allocation inside `position` leaves the previous position (the other side to move), so the next `go` plays an illegal move (`session.cpp:423-454`). Test: #1-#9 fail. | **Owner:** retry once in the catch, or a "position unknown" flag | no |
| R-4 | engine | `go mate N` with no mate in N, `go mate 0`, and a clock given only for the opponent never answer (they run towards depth 249) | **Owner:** document it, or add a depth bound tied to N (a new constant) | no |
| V-2 | engine | Clear Hash is lost when applied at the same `isready` as a Hash change: `session.cpp:254` clears the flag without `clear_history()`. Test: 29030 vs 28698 nodes. | One line | no |
| S-3, B-1 | engine (time) | A position with one legal move spends its full soft budget: 3.97 s of a 60+0.6 clock, 1.17 s at 30+0. **Moved to §2 (B-1)**, because the fix changes play. | §2 | no |
| A1 susp. 8 | engine | The root PVS re-search has no `!stopped_` guard (the sibling of 00bed14). Node-limited searches overshoot by 1 node in 5 of 354, within the test tolerance. | One token. It changes only node-limited searches, by at most one node; I propose no SPRT, owner's call. | no |
| S-2 | comment | `searcher.hpp:16-17` "listener called once per finished iteration only" is false (the failing test shows 12 aspiration-fail calls and 12 repeats) | Reword | no |
| A1 susp. 9 | comment | `trans_table.hpp:14-16` calls a false key match "harmless"; it is rare, but it does supply a score | Reword | no |
| D-19 | comment | `searcher.hpp:19-20` "release defaults are the techniques adopted by SPRT" (several are provisional or never SPRTed) | Reword | no |
| P-4, Q-9 | stats, dead code | The futility branch in the move loop (`searcher.cpp:242-248`) never runs: 0 of 540k evaluations. Its `gives_check` is always true, and the `futility` counter prints 0, which misleads the removal round. | Drop the branch (or assert), count `quiets_filtered()` as `futility_filtered`, A/B | expected no (verify) |
| P-6 | speed (TCEC) | Without LTO, `piece_value`, `bucket_index`, `attackers_to` and `repetition_count` become calls. update.sh only warns, and `fork version` does not report LTO. | Inline these helpers in headers; print `lto on/off` | no |
| T-4, D-7 | originality rule | `LmrCorrectionStrength` 64 has no row in the Search constants table | One row | no |
| — | originality rule | The ±1000 score-trend clamp (`searcher.cpp:650`, an LMR-context input) has no row (A9 F-8). A4b: Berserk uses ±1000 in another role. | One row | no |
| T-5 | originality rule | The bootstrap-eval weights (8 values plus the ring formula) are unjustified; A4b found no match | A short justification table or a placeholder note | no |
| T-6 | originality rule | The TT digest multiplier `0xD6E8FEB86659FD93` (`trans_table.cpp:30`) has no source (A4b: no match; origin UNVERIFIED) | Cite it, or replace it with the cited splitmix64 finalizer. Bench may move through 24-bit digest collisions; if so, the SPRT rule applies. | maybe |
| T-7, T-8 | originality | The normalized four-engine check of Phase 1-2 names is now done (A4b): **0 distinctive coinages**, 15 borderline names (§6, decision 2) | Owner's call per name; record the result in ORIGINALITY.md | no |
| T-9, D-6, D-17 | ORIGINALITY.md | Missing items: the anchors Belette 2.0.0, Chal 1.3.0 and WyldChess 1.51; the second UHO pin a804a97e; name checks 16-32; the Claude CLI (Sonnet) in evolve; the Python tool row; the evasion offset (now HistoryMax+1); "GPL-3.0" where it should say -or-later | Edits | no |
| T-10 | README | "every commit carries both trailers": 22 commits lack `Claude-Session`, and 3 merges have neither. Only one model is named, while the evolve agents run Sonnet. | Reword | no |
| T-13 | licence form | No source file has an SPDX/licence line | **Owner:** add `// SPDX-License-Identifier: GPL-3.0-or-later` (third_party excluded), or not | no |
| D-8..D-16, V-3, T-12 | docs | Stale DESIGN.md: status line "towards Milestone A"; "repo private"; a nonexistent `pgo` target and scripts; "`fork bench` is perft" (§2/§4.7); `src/tb`/`TbBridge`/`NodeKind`; the switch list (14 vs 17); 7 UNVERIFIED items now resolvable; about 8 missing decisions-log rows; ideas.md statuses (ideas 3, 5, 9, 12, 22, 23 truncated, 28); the testing.md Stop-hook line; CLAUDE.md "kb's DESIGN.md is only a pointer" (it is a 695-line copy, 77 commits behind); fuzz_uci "with small node limits" (it sets none, and the stop flag is preset); Hash row "review M5" should be M8 | One docs commit | no |
| U-9 | tooling | `run_shard.sh` reports a crashed fastchess as `done`, exit 0 | Record `wait`'s status; `failed`/`short` states | no |
| U-10 | tooling | `sprt.sh` logs a run that never started as INCONCLUSIVE; it has no binary identity check (DESIGN says it has one); the compiler is not pinned (plain builds use clang 21, `TUNE=1` builds GCC 15) and is not in the cache key | Pass `CXX` and add it to the key; log `fork version`/bench for both sides; no log entry for 0 games | no |
| U-11 | tooling | The gate's `ctest -R` passes when no test matches (exit 0 on CMake 4.4; 3.22 UNVERIFIED) | `--no-tests=error`, plus a count check | no |
| U-12 | tooling | The Stop and after-edit hooks hide check.sh's "skipped, another check running" warning | Surface it | no |
| U-13 | tooling | The held-out split is per position, so every held-out position shares a game with evolve positions. The measured effect is negligible (ICC -0.02..+0.02). | Split by game in the next batch | no |
| U-14 | tooling | `pgn_summary.py` counts every adjudication as abnormal (it exits 1 on every SPRT) | Flag only forfeit, illegal, stall and the like | no |
| U-15, D-21 | tooling | `test_sprt_merge.py`, `test_evolve.py` and `test_hooks.sh` run in no check; test_hooks has no failure-path case | Run the Python suites in `check.sh quick` (under 3 s); add a broken-source hook case | no |
| U-16 | tooling | Local SPRT openings are not reproducible (no `-srand`, seed not logged) | Seed from the stamp and log it | no |
| U-17 | tooling | The gate builds with one compiler, and `constexpr lmr_correction` is accepted by clang but rejected by GCC | Build the gate with gcc 11.4 and clang 19, or make it non-constexpr; say so in the prompt | no |
| U-18 | tooling | `elo_gauntlet.sh` prints ratings after a failed fastchess (by reading; not run) | Exit non-zero | no |
| Q-10 | tests | DESIGN §5.2 lists ctest checks that don't exist: a tiny-hash search stress test, the tactical suites, difftest | Add a tiny-hash test and a short difftest ctest when .venv exists, or amend the spec | no |
| Q-11 | tests | The LMR-facts "python-chess" check is not committed (A5 re-derived it: all match); the danger-zone test restates the implementation; two stale "(uncommitted; failing tests)" headers | Commit the derivation; use literal expected values; fix the headers | no |
| Q-12 | tests | The `uci_timing` 4096 MB case skips under memory pressure and marks the whole suite Skipped | Size it from `available_memory()`; report skips per case | no |
| V-5 | tests | Speed-only fixes (1(c), 2(b), the null prefetch, the PlyFrame size) are unguarded by design | Optional: stats-build assertions and `static_assert(sizeof(PlyFrame) <= …)` | no |

---

## 2. Behavior improvements (A8), ranked by expected value

All of these change play, so each gets its own SPRT on the GitHub shards
(never bundled). Every new constant needs the originality-checker's
constant screen and the name checks before it is committed. Bench changes
only where noted.

| Rank | ID | Change | Evidence | Expected | New constant (justification) | SPRT | Effort |
|---|---|---|---|---|---|---|---|
| 1 | B-1 (= S-3, a proven flaw) | With one root move (after `searchmoves` and the table filter) in a timed, non-ponder search, stop between iterations at 1/8 of the soft limit (`searcher.cpp:665`) | Forced move at 60+0.6: 3,973 ms to depth 22 now, 313 ms to depth 18 with the rule, same move and score | +1 to +3 Elo; more seconds at TCEC time controls | `ForcedMoveFraction` 8: Fork's measured iteration growth 1.66^4 ≈ 7.6, so the score stays about four iterations short of a normal move's depth | **Owner:** [-3, 0] as a decision-flaw fix (A8, A1), or [0, 3]; plus the 2+0.02 load run | S; bench unchanged |
| 2 | B-3 | After a root aspiration fail high, re-search at depth − 1 (not cumulative); a fail low keeps the full depth | Bench nodes −1.0/−6.7/−7.9/−2.6% at depths 11-14; proxies neutral (−0.0007 [−0.0049, +0.0035]); KB T6 | +2 to +5 (low-medium confidence) | `AspirationFailHighCut` 1 ply: the smallest whole-ply step | [0, 3] STC, then LTC confirmation | S; **bench changes** |
| 3 | B-2 (A8-2) | Store a settling table WDL result in the TT at full depth instead of the node's depth (`searcher.cpp:146`) | 65 positions with the 3-4-5 set: probes 22,621 → 17,161 (−24%), nodes and best moves identical | Speed with 7-man tables on disk; 0 Elo with 3-4-5 in RAM | none | [-3, 0] with tables on both sides (needs the D-2 decision); a 7-man cold-cache probe measurement first | S; bench unchanged (no tables) |
| 4 | B-4 | Qsearch stand-pat refined by a TT bound (KB T50, qsearch variant), on its own switch | Bench −0.1/+0.8/−2.4/−4.4%; proxies neutral | +1 to +3 | none | [0, 3] STC and LTC, **after** the removal round settles UseTtEvalRefine | S |
| 5 | B-5 | Keep a stale own TT entry that is still deeper after aging (reuses `StaleDepthPerSearch`) | Game sequences −1.1% nodes (weak) | 0 to +2 | none | [0, 3] at LTC, together with idea 24's retest (Phase 6 table pressure) | S |

Measured and **not** recommended: root LMR (proxies −0.039, and still
negative at one ply), a TT cut one ply short, storing RFP/NMP cuts (+7%
nodes), history fade between searches (+3.8 to +6.4%), and four small
ordering/TT tweaks. Priority note: idea 29 (how often an unconfirmed fail
high holds) should run before or with B-3.

Candidates that need a measurement first (from the suspicions, not ranked):
- 3-fold repetition when the earlier occurrence is before the root (A1 s1, a design choice today);
- a TB-loss guard on LMP/futility/SEE pruning (A1 s6);
- never letting an exact shallow result replace a deeper entry of the same search (A1 s5).

---

## 3. Refactors and speed work (bench identical)

Every hot-path item needs `bench/ab_search.py --same-nodes` (DESIGN §7).
Every new name (listed in A9 §2.4) needs the §8 name check before use.

**Speed (A2).** Each needs an A/B with clang **and** g++ 11.4:
- P-1 lazy LMR facts (in §1, medium).
- P-2: pins and discoverers computed at every make, though 57% / 97.9% of that work is never read. Make them lazy, once per node. M; touches the Position invariants and the consistency tests.
- P-3: SEE early return. 30.3% of `see_at_least` calls are settled before any lookup (`victim − attacker ≥ threshold`). S; optionally incremental x-ray attackers (M).
- P-5: the bootstrap eval repeats `insufficient_material` (12.4 M calls, about 0.2%). Only if the eval is touched before Phase 4.
- P-6 header inlining (in §1).
- Suspicions to measure: a SIMD pick in `take_next` (17.6% of the profile; scalar reference and equivalence test required; maintenance cost reported first), and a cache-friendlier MoveList/PlyFrame layout.

**Refactors (A9), in A9's suggested order:**
1. Cold and independent:
   - F-5: one X-macro switch list, which also fixes UseTables;
   - F-1: delete the dead `root_fail_high_score_/pv_`;
   - F-6: designated initializers for `LmrContext`;
   - F-7: use `kind_of`;
   - F-9: one non-allocating move-to-text routine and one bench report;
   - F-10: one cited copy of the perft-suite FENs in src;
   - F-11: format drift in 6 files;
   - F-25: module-table docs.
2. Hot (prototyped F-1..F-7: bench identical, 11/11 tests, codegen differs by register allocation, so an A/B is needed): F-2 `bound_settles`/`result_bound` (the cutoff test is written 3 times), F-3 the fifty-move helper, F-4 a `FORK_STAT(...)` macro (20 `#ifdef` blocks).
3. F-12: decouple SEE, MVV-LVA and the LMR context from `bootstrap_eval.hpp` with a core material table, **before Phase 4**. Otherwise an eval retune silently moves SEE thresholds. Then F-8: name the magic numbers (`MateScore - MaxPly` ×8, the TT rank 256, the bit masks, `(900+900)*8`).
4. Before tier 2's first history table:
   - F-13: one make/unmake wrapper per ply that records move, piece and destination (needed by continuation history and NNUE);
   - F-14: one gravity function, a history family with one `clear()`, and a 12-slot piece index (1.125 vs 2 MiB per continuation table). **Trap:** int16 selector scores overflow once 4+ history tables are summed;
   - F-16: name the eval ladder;
   - F-15: split the 300-line `negamax` into always-inline steps;
   - F-17/F-18 are notes for the tier 2 spec. In singular search the excluded-move search reuses the ply frame, `moves_seen == 0` would report false mates, and an `excluded` field is needed;
   - F-20: pawn and non-pawn keys from the existing Zobrist keys (bench unchanged; State 56 → 80 B; fuzz rule).
5. Phase 4 F-21 (accumulator placement); Phase 5 the F-19 time seam; Phase 6 F-22 (the TT age and policy set once per `go` by its owner, not per searcher: a future data race), then F-23 (a search-pool seam), with F-24's memory numbers (420 MB of Searchers at 512 threads).

---

## 4. Cleanup

**Dead code** (bench should stay identical; build to confirm):
- `shift_north/south/east/west` (bitboard.hpp:46-49; also DESIGN.md:143);
- `Position::ply_count()`;
- `root_fail_high_score_`/`root_fail_high_pv_` (= F-1);
- the dead futility branch (P-4/Q-9).

Keep: the TT-PV flag (T19), `tt_exact_depth`, the idea 23 machinery while the pilot is on hold, and every `Use*` switch until the Phase 4 re-validation.

**Stale docs:** the D-8..D-17 list in §1 (one docs commit); the ideas.md status vocabulary; `docs/ideas.md:152` points to the untracked HANDOFF.md.

**Files:**
- `bench/baselines/*.txt` predate the clean-room rewrites: regenerate or delete;
- `tools/phase2_games.sh`: archive candidate;
- `tools/__pycache__`: delete;
- untracked fuzz corpora: minimize and promote at the phase end. No Phase 3 fuzz run is recorded, and fuzz_uci's code changed all through Phase 3.

**Branches and tags** (pushing and deleting remote branches is outward-facing, so each needs your explicit OK):
- delete d8-a, d8-b1, d8-b2, d8-c, d8-final (and the clean `../fork-d8` worktree), milestone-c and review-fixes, both locally and on GitHub. Each is merged or archived by a `d8/*` tag; push the archive tags first if you want them public;
- keep tcec-cutechess;
- push kb's unpushed e451077, and merge main into kb (77 behind) at the phase end;
- D-20: the tag `d8/final` / 8b8e34c says "variant (c) alone" but is B2 + (c), so re-annotate it.

**Build dirs:**
- one-offs `build/clang-stats` and `build/clang-tune` (not presets; there is no `clang-stats` preset);
- `clang-v3`, `clang-avx512`, `clang-nopext`, `clang-pgo`, `gcc-pgo` and `clang-fuzz` were last built 2026-10-24: rebuild (deferred list);
- the 10 audit worktrees under `.claude/worktrees/` (they hold the proof tests): remove after Phase C has taken the tests over.

---

## 5. Suspicions (unproven), each with how to settle it

1. **Tables and the TT**:
   - the TT ignores the halfmove clock, so a zero-clock table result can cut at a later visit with a non-zero clock, where it may be a fifty-move draw (A1 s4, A8 S-A8-1). B-2 widens this. Settle with a constructed 5-man two-path test;
   - a one-sided TB bound clamped inside the window is stored as Exact at PV nodes (A1 s2).
2. **Table probe cost at TCEC**: `TableProbeMinDepth` 1, Fathom's lazy first-probe mmap and malloc, and a root DTZ probe before the first hard-limit poll (A2 S-d, A3 s5). Settle with a 7-man cold-cache probe-rate and movetime run.
3. **Fathom `exit()` paths**: a failed `mmap` mid-game ends the process (A3 s1); a truncated table with a valid magic is read out of bounds (A3 s2). Settle with a crafted file or a FIFO swap.
4. **Hash at TCEC sizes**: a refused 256 GiB falls back to the previous size (16 MB at the start of an event), not the largest size that fits; and cgroup limits are invisible to `/proc/meminfo` (A3 s3, s4). Settle with a `systemd-run MemoryMax` run, then decide on a halving fallback.
5. **Data races**: none found by reading, but **TSan was not run**: the sandbox refused `wsl` in A3's worktree (A3 s6). Note also F-22 (Phase 6) and readiness note 8: `build_bitboard_tables()` is public (A10 s2).
6. **A default (x86-64-v3) binary on a CPU without BMI2 dies with SIGILL**: there are 47 `pext` instructions and no CPU check (A4 s1). TCEC's EPYCs have BMI2. Settle with Intel SDE `-nhm`.
7. **TT memory latency is invisible to bench**: the 16 MB bench table fits the 96 MB L3, so prefetch and TT changes are under-measured (A2 S-c). Settle with a 4 GB-Hash A/B with prefetch on and off.
8. **Ponder time counts from `go ponder`**, and there is no ponder move in `bestmove` (A1 s7).
9. **Mate distances beyond MaxPly overstated via the TT** (theoretical; A1 s3).
10. **Tooling and proxies**:
    - the proxies may favour the baseline's own LMR shape (A6 S-4, A8 S-A8-3);
    - the proxies barely see root fail highs (S-A8-2);
    - UB in a body passes the gate (Release, no sanitizers; A6 S-5);
    - file encoding in `Runner.tree` (A6 S-6);
    - the time-loss wording in `sprt_merge` is UNVERIFIED (A6 S-1);
    - spot-interruption pair bias (A6 S-2);
    - hook timeout (900 s) vs check.sh's 600 s lock wait plus build (A6 S-3);
    - the evolve loop's originality screen is a manual step (A4 s2).
11. **Tests**:
    - fuzz_uci may reach almost none of the search (A7 S-2);
    - the "just above available memory" test can race other processes (A5 S-1);
    - CI may stay green when the 7-man download fails (A5 S-3);
    - Phase 3 names not traceable per name to a check (A7 S-5): settled now by A4b.
12. **Originality**: whether TCEC treats Fathom's Cfish-derived code as another engine's code (UNVERIFIED; A4 s4); the public KB's technique prose was written by an agent that read engine code (A4 s5).
13. **Formatting**: the post-edit hook's clang-format version vs the one A9 used (A9 U-2).

---

## 6. For you to decide

1. **SPRT conditions:** tables on both sides in local and cloud SPRTs (D-2), or amend the spec?
2. **Borderline names (A4b):**
   - `WhiteOO/WhiteOOO/BlackOO/BlackOOO` (Stockfish, Weiss);
   - `parse_go` (Berserk; the same function whose time shape is credited);
   - `GoodCaptures/BadCaptures` (Stockfish 8), plus the stage-order parallel with Stockfish 11-16;
   - `DarkSquares` (Stockfish, exact), `NoPieceType` (Stockfish), `TbWinScore` (Berserk), `score_to_tt/score_from_tt` (Weiss), `rule50` (all four), `max_hash_mb` (Stockfish).

   Rename which? (Renames keep bench; each new name needs its own check.)
3. **New constant matches:** RfpMargin 80 (Berserk 4.5.0) and Move Overhead 100/0/10000 (Ethereal v12.75): keep and record, or change? And the near matches (LmrMinMove, FutilityMaxDepth, SeePruneMaxDepth, the cursed-win 1, SPSA range/20): record only?
4. **Time-budget constants** (T-3): justify the current values on paper now, or measure (and possibly change) them in Phase C?
5. **A9-2:** leave PVS out of the removal round (document it), or decouple PVS from LMR?
6. **B-1 bounds:** [-3, 0] (fix) or [0, 3] (gainer)?
7. **rv-failhigh** (D-5): record an exception, or queue the LTC retest?
8. **R-3** (illegal move after an OOM `position`): retry, or an "unknown position" flag? **R-4** (`go mate N`): document it, or a depth bound?
9. **README/ORIGINALITY wording** on Fathom (T-2), and SPDX headers (T-13): yes or no?
10. **Remote branch deletion and tag pushes** (§4): OK to do?
11. **T-6:** keep the TT multiplier with a cited source if one is found, or switch to the splitmix64 finalizer (possible bench change, then the SPRT rule)?

## 7. Proofs not yet run (I'll run them one at a time; machine otherwise idle)

Light (minutes each):
- TSan on the UCI suites, clang-tsan and gcc-tsan (A3 D-1). A3's sandbox refused `wsl`; I'll run it from this session if you approve;
- `uci_timing` on an idle machine;
- a FORK_REPO clone from GitHub through update.sh, plus bench (closes DESIGN:72);
- ctest 3.22 exit status with no matching test;
- `test_hooks.sh`;
- the two Python suites;
- a stats bench confirming futility 0;
- fuzz_uci search coverage on a `go depth 5` seed;
- the Syzygy insufficient-material tool.

Medium:
- the slow suites;
- the Windows rebuild of clang-v3, clang-avx512, clang-nopext and both PGO presets;
- U-2 end to end through the real gate;
- no-BMI2 under SDE (if SDE is available).

Belong to Phase C, per item:
- the A/B speed checks (P-1, P-2, P-3, P-6, the F-1..F-7 prototype);
- the 7-man probe-cost runs (needs 7-man files on disk; UNVERIFIED that they are here);
- the large-Hash prefetch A/B;
- the fastchess time-loss wording;
- the book-slice match;
- the stress and load runs.

## 8. Process notes

- A1, A3 and A6 had `wsl` (and, for A1, `. scripts/env.sh`) refused inside
  their worktrees. A1 worked round the env.sh refusal by building with
  literal-path copies of the scripts in the scratchpad. A2, A4 and A8 could
  use WSL. The TSan run is therefore still owed.
- A4b's report describes, in words, the other engines' values for constants
  that did **not** match. That is more than "match / no match". It stays in
  the scratchpad and nothing of it goes into the repo; ORIGINALITY.md gets
  only the matches. Any constant changed in Phase C must be justified by
  Fork's own reasoning or measurement.

## 9. Proposed Phase C order (after your answers)

1. Tooling needed for Phase C's own SPRTs: U-1, U-3, U-4, U-9, U-10, U-14, U-16, the D-2 decision. Push-free; the cloud runs only once these are in.
2. Bench-identical engine fixes: R-1, R-2, V-2, (R-3, R-4 per decision), the UseTables/F-5 switch list, the comment fixes, T-1 (update.sh).
3. Test additions: Q-1..Q-8, V-4, taking over the auditors' proof tests.
4. Docs and originality records: D-1, D-4/T-2, T-3/T-4/T-5/T-6 rows, the A4b matches, T-9/T-10, D-8..D-17, plus any renames you choose.
5. Remaining tooling: U-2, U-5..U-8, U-11..U-13, U-15, U-17, U-18 (U-2/U-7/U-8 before idea 23 resumes).
6. Refactors and speed (A/B each, bench identical): F-1..F-7, P-1, P-6, P-3, P-2, F-9/F-10/F-11, F-12, F-8; dead code; the futility branch.
7. Behavior SPRTs, one at a time on the GitHub shards: B-1, B-3, B-2, then B-4 and B-5 when their prerequisites are met.
8. Phase D.
