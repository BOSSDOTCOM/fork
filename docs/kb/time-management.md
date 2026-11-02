# Fork KB: Time management for long time controls (Phase 5)

Added 2026-11-02. **REFERENCE ONLY.** Verified 2026-11-02. This is a
clean-room description of time-management (TM) techniques for Phase 5:
the base allocation, the adjustments made between iterations, behaviour
at long increment controls without pondering, safety under load, and how
engines test TM. Every source is in [sources.md](sources.md), under "Time
management (time-management.md)".

**How this was researched.**

- **Primary sources:**
  - the Chess Programming Wiki;
  - four papers, read in full from the authors' or publishers' PDFs;
  - author posts on talkchess;
  - the TCEC wiki and tcec-chess.com JSON;
  - the UCI specification;
  - the fastchess man page, the OpenBench wiki and the Lc0 flags page;
  - engine commit messages (GitHub commit-search API, message text only)
    and pull-request bodies (GitHub REST API);
  - fishtest run records (JSON API).
- **No engine source.** No engine repository was cloned or downloaded, and
  no engine source file was opened. One talkchess post (Grant, 2017)
  contains a short code listing; only its prose was used, and nothing from
  the listing was copied or kept.
- **No engine constants.** Following the owner's rule, this file records
  no engine's constant values (factors, fractions, move counts, caps in
  milliseconds), even where a commit message states them. It records
  mechanisms, test conditions and published Elo results only. Where a
  message gives only a title, the form is marked UNVERIFIED.
- **Licences.** The engines cited are GPL-3.0 (Stockfish, Ethereal,
  Berserk, Weiss, Koivisto, Stormphrax, PlentyChess, Halogen, Alexandria,
  Lc0) or AGPL-3.0 (Viridithas, Reckless), per the GitHub API on
  2026-11-02. The tools are fastchess (MIT) and OpenBench (GPL-3.0). CPW is
  CC BY-SA 3.0. The papers are copyrighted by their publishers. Only ideas
  are used.

Elo figures are each engine's own result at its own stage of development,
with the ± (95 %) and the time control as posted. "STC" means 8+0.08 or
10+0.1 unless stated otherwise. A gain at one engine's stage does not
transfer to Fork one to one.

---

## 1. What Fork does today (the baseline Phase 5 starts from)

Source: main's DESIGN.md (Deliverable 8, the Search constants table and
the Phase 5 bullet) and `src/search/time_budget.cpp` and
`src/search/searcher.cpp` on branch phase-4, read 2026-11-02.

| Piece | Fork today |
|---|---|
| Clock input | The side to move's clock less one Move Overhead (option, default 100 ms) is the time available. |
| Moves to go | `movestogo` clamped to `MaxMovesToGo` (40). Without `movestogo` (Fischer or sudden death), `AssumedMovesLeft` (30) is used, recomputed every move, so the planned moves never run out. |
| Share | The time available over the moves to go, plus three quarters of the increment (Fork's own "increment share"). |
| Soft limit | One share. It is checked only between iterations: no iteration starts after it. |
| Hard limit | `HardOverSoft` (4) shares. It is polled during the search every 1,024 nodes (`StopCheckInterval`). |
| Reserve | The hard limit never plans into the last tenth of the clock (`ReserveDivisor`). In the danger zone (time below `DangerZoneOverheads` = 2 overheads plus an increment), one more overhead is kept. |
| Iteration rule | No iteration starts if the measured growth (5/3, `IterationGrowthThirds`) would carry it past the hard limit. It binds only where the hard limit is close to the soft one (`go movetime`, or a low clock capped by the reserve). |
| Forced move | With one legal root move, a timed search stops once 1/`ForcedMoveFraction` (1/8) of the soft limit has passed (audit-1, B-1). |
| Movetime | Overhead taken off, but never below half the asked time. |
| Unlimited cases | A bare `go`, and `go ponder` until `ponderhit`, have no limit. A `go` that carries a clock only for the opponent also has none today; that is the open question in §8. |
| Dynamic adjustments | **None.** There is no best-move stability, score trend, fail-low extension or node-share term. |
| Credit | The share and hard-limit shape is credited to Berserk 4.5.0-8 (ORIGINALITY.md). |

**What Phase 5 inherits.** Deliverable 8 was SPRTed at 8+0.08 and
accepted there. Its 40+0.4 run (d8-ltc) stopped INCONCLUSIVE, and DESIGN
asks Phase 5 to revisit the iteration rule first (§4.6). Every constant
in the table above is "reasoning; measured in Phase 5".

---

## 2. TCEC conditions that drive time management

Checked 2026-11-02 against wiki.chessdom.org (Rules,
TCEC_Swiss_rules, TCEC_Swiss_10, TCEC_Season_Further_information) and
tcec-chess.com (tournament.json, live.json). competition.md has the full
record.

- **Time controls (Season 30):**
  - Swiss, Entrance League, L2, L1 and Cup: 30'+3". The Leagues rules
    section 9 states 30 minutes plus 3 seconds added per move for the
    whole game.
  - Premier Division and its playoff: 60'+6".
  - Superfinal: 120'+12".
  - All are Fischer controls (no `movestogo`).
  - live.json on 2026-11-02 showed "TCEC Season 30 - Swiss 10 Tiebreak 1
    Promotion To Entrance League" at `TimeControl 1800+3`.
  - Season 31's controls are **UNVERIFIED**: no S31 rules page exists yet
    (competition.md §1).
- **No pondering.** Pondering is disabled "because of performance
  limitations with only 1 computer" (Further information). So both engines
  run on the same server, alternating turns, and a TM gains nothing from
  thinking on the opponent's time.
- **A time loss is a loss and is not replayed** (Swiss rules 5.b and 6.d;
  Leagues and 4k sections). Time losses caused by lag or other
  interruptions not caused by the engines fall under the server-crash
  scenarios (Swiss rules 7.b).
- **Move Overhead.** Options stay at default unless the author asks. The
  Swiss 10 page's testing bug list has several engines losing on time in
  testing, then running with a raised MoveOverhead (PZChessBot, Jackal,
  Raphael three times in a row). It also notes "a one second margin" in the
  actual event, without saying what the margin applies to (**UNVERIFIED**
  meaning, as in competition.md).
- **Tablebases.** 7-man Syzygy: the WDL and DTZ files sit on NVMe, and a
  further 14 TiB HDD is listed "for Syzygy7 DTZ" (Further information).
  Which DTZ files Fork's `SyzygyPath` would read from the HDD is
  **UNVERIFIED**. A slow DTZ read at the root is a known source of TCEC
  time losses (§4.8).
- **Contention.** No TCEC page describes the CPU load an engine sees
  during its own move: OS and server work, the opponent's process, TB
  page-cache traffic (**UNVERIFIED**). Fork's Phase 5 "stress test under
  artificial system load" is Fork's own design, not a TCEC rule.

---

## 3. Long increment controls: what changes (Fork's arithmetic)

This is a model, not a measurement. It applies Fork's current formula
(§1) and assumes every move spends exactly its soft limit. Real moves stop
earlier or run past the soft limit, so actual clocks will differ.

- **First moves.** One share at 30'+3" is 1800/30 + 0.75·3 ≈ 62 s, with a
  hard limit of about 249 s. At 60'+6" the share is about 124 s; at
  120'+12" about 249 s.
- **The clock decays geometrically** by about 1/30 a move, and the
  increment refills it. Without overhead, the clock settles where the share
  equals the increment: the clock less the overhead is 30 × (1/4 of the
  increment) = 7.5 increments.
  - At 30'+3", the clock settles near 22.5 s, the move budget near 3 s and
    the hard limit near 12 s. The settled clock is 45 s at +6" and 90 s at
    +12".
  - On the same model the clock is about 480 s at move 40 (share ≈ 18 s)
    and about 140 s at move 80 (share ≈ 7 s).
  - So late in a long TCEC game Fork is **increment-dominated**: a move
    gets about 20 times less time than in the opening.
  - TCEC games often run long: draws are adjudicated only with 6 or fewer
    pieces (competition.md), and the Swiss 10 data had its earliest draw
    by the TCEC rule after 28 moves. So the late-game share of the
    increment (three quarters today) matters more at TCEC than in short
    self-play with adjudication.
- **Granularity.**
  - At long TC, with many threads, each iteration is a large block of
    time. Fork's measured growth is a median of 1.66 per iteration at
    depths 8-14 (DESIGN, "Iteration growth"). Its growth at depths 25-40
    on 512 threads is not measured.
  - With the soft limit checked only between iterations, a move whose
    last iteration starts just before the soft limit ends near 1.66 soft
    limits (median). So the mean spend sits above the share.
  - At long TC, the decision of whether to start one more iteration moves
    far more time than the per-node work of any adjustment.
- **Where the danger zone sits.** At 30'+3" Fork's danger zone needs a
  clock below about 3 overheads plus an increment (≈ 3.3 s at default
  overhead). The settled clock (≈ 22.5 s) never gets there. DESIGN's
  remark that it "should almost never bind at 40+0.4" holds even more
  strongly at TCEC controls.
- **Evidence that the value of time falls through the game.**
  - Laskos (talkchess, January 2015): in fixed-node Houdini matches, a
    doubling of nodes was worth markedly less when the games started from
    later positions of real games than from the opening.
  - Šolak and Vučković (2009) model the moves left from the moves played
    (and, in a variant, from the material left) on a database of master
    games.
  - Both support spending relatively more early, which a fixed
    moves-to-go divisor already does through the geometric decay.
  - Reckless measured a further reduction of time at high fullmove numbers
    only as non-regression (#390, #391, 2025-06).

---

## 4. Techniques

Each entry gives what it is, why it matters for Fork, its long-TC
behaviour, the evidence and lineage, its pitfalls, and where it would
live in Fork.

### 4.1 Base allocation: clock, increment, moves-to-go, soft and hard limits, reserve

- **What it is:**
  - A per-move **share** is computed from the clock, the increment and an
    estimate of the moves left (the real `movestogo` in cyclic controls).
  - The **soft (optimum) limit** decides whether another iteration
    starts. The **hard (maximum) limit** aborts a running iteration.
  - A **reserve** keeps a part of the clock unplannable.
  - The **overhead** is subtracted for latency.
  - CPW (Time Management, "Basic TM" and "Soft Bound") presents this
    two-level scheme as the large first improvement over a single budget.
- **Refinements engines measured (lineage only):**
  - **Increment weight.** Koivisto #160 and #173 (2021-11, 2022-01) used a
    larger part of the increment each move: +2.6 ± 2.1 STC and +3.5 ± 2.3
    at 40+0.4, then +4.8 ± 3.2 and +4.5 ± 2.6. Fork's three-quarter share
    is the analogous knob.
  - **Scale by the clock's size.** Stockfish cf3dbcb5 (2023-10) scales
    the optimum and maximum time with the logarithm of the time left. It
    passed gainer bounds at STC and LTC, with verification runs at
    3+0.03, 10+0 and 180+1.8.
  - **Shape over the game.**
    - Stockfish 9be2977d (2022-10) shifted time to the early game: passed
      at 10+0.1, at 60+0.6 and in sudden death.
    - Stockfish c6ce612f (2020-05) wrote separate equations for base plus
      increment and for moves-in-time controls. Its time curve tails
      downward for the first moves of the game; it passed non-regression
      at 7 controls, including fishtest's "TCEC style" (§6).
    - Reckless #176 and #177 (2025-03) scale the optimum and maximum by
      the move number.
  - **Cap on one move's share of the clock.** Viridithas #359 (2025-11)
    caps the share of the clock a single move may use: non-regression at
    STC, at 40+0.4 and on 4 threads. #400 (2026-01) tightened the cap,
    tested at 8+0.08 only. Fork's reserve plays the same role.
  - **Overhead counted as unusable.** Ethereal #147 (2020-09): treating
    MoveOverhead as time that cannot be planned on gained +68 ± 19 at
    10+0 and +35 ± 12 at 40/8, and was neutral at 10+0.1. It matters in
    sudden death and cyclic play, little with a real increment. Fork
    already subtracts it.
  - **Separate cyclic logic.**
    - Berserk #335 (2022-01) fixed cyclic TM for +36 ± 12 at 40/8 and
      +40 ± 14 at 40/40.
    - Stockfish 4d65257b (2026-09) stopped shrinking the move horizon in
      cyclic controls after 557 timeouts in 1,984 games at 40/1.
    - TCEC is Fischer-only, but `movestogo` must stay safe for local and
      CCRL-style tests.
  - **Options removed as harmful.** Stockfish removed "Minimum Thinking
    Time" (208c53df, 2020-06: it bypassed the dynamic adjustments) and
    "SlowMover" (536d692a, 2023-12: users changing it only lost Elo).
    Exposing TM factors as user options is a risk; tuning builds are the
    right place.
- **Long TC:** this is where the most time sits. A wrong share costs on
  every move, and at 30'+3" most of the game is played in the
  increment-dominated regime (§3).
- **Fork:**
  - It has the whole skeleton (§1). Phase 5 measures `AssumedMovesLeft`,
    the increment share, `HardOverSoft` and `ReserveDivisor` at long TC.
  - It would add an optional clock-size scaling only if a test shows it.
  - Component: `src/search/time_budget.cpp`.
- **Pitfalls:**
  - A larger increment share raises the settled late-game spend and
    lowers the settled clock (§3).
  - Check the hard limit against the reserve after every change; a test
    exists for it.
- **Expected value for Fork:** retuning the base constants at long TC is
  moderate (a few Elo). The structure is already there.

### 4.2 Best-move stability and best-move changes

- **What it is:**
  - Count how many consecutive iterations kept the same best move, or how
    often it changed recently.
  - A stable move shrinks the soft limit; recent changes stretch it.
  - The older binary form is the "easy move", where a single obvious move
    is played early. Hyatt's 2013 thread describes it, and CPW lists "how
    often did the best move change" as a consideration.
- **Why it works:** a move that has survived many deeper iterations is
  unlikely to be replaced by one more. Šolak and Vučković (2009) frame TM
  as continuing only while the probability that the current best move
  will be replaced is high.
- **Evidence and lineage:**
  - Weiss #297 (2020-05), more time when the best move differs from the
    previous iteration: +7.4 ± 5.1 at 10+0.1 and +2.9 ± 2.3 at 60+0.6.
  - Ethereal #148 (2020-09), more weight on stability: +2.3 ± 1.8 at
    10+0.1, +2.8 ± 2.2 at 60+0.6 and +5.5 ± 3.9 at 40/8.
  - Berserk #244 and #251 (2021-09): +4.7 ± 4.0 STC; then +3.0 ± 2.9 STC
    and +3.9 ± 3.3 at 40+0.4.
  - Viridithas #31 (2023-04): +5.8 ± 4.1 at 60+0.6.
  - PlentyChess #104 (2024-02): +7.3 ± 5.9 STC.
  - Reckless #42 (2024-03, title only, result not read), #144 (PV
    stability, +3.8 ± 2.9 STC) and #573
    (2025-11, best-move instability: +4.0 ± 2.7 at 40+0.4).
  - Halogen #757 (2025-10): +4.7 ± 2.8 at 40+0.4 and +2.7 ± 2.0 STC.
  - Alexandria #281 (2023-12): no result in the PR.
  - Stockfish:
    - 486c8175 (2017-11) replaced the old easy-move code with a simple
      rule: less time for a stable best move, and part of the saving
      carried to the next move. Non-regression at STC and LTC.
    - 285a79ea (2022-04) made its instability factor independent of
      depth.
    - fe7b9b14 (2025-05) made the reduction a smooth function: passed
      gainer bounds at STC and LTC, the LTC over 407,340 games.
    - c7875096 (2026-04) replaced that smooth function with a linear
      interpolation (non-regression).
- **Long TC:**
  - Iterations are fewer per move but each is deeper, so "stable for k
    iterations" spans much more search. The number of iterations a move
    must survive, and the size of the reduction, should be tuned at long
    TC.
  - Stockfish's fe7b9b14 needed 407k LTC games to pass gainer bounds, a
    sign the effect is small once the rest of TM is mature.
- **Phase 6 note:** with Lazy SMP, Stockfish 1982fe25 (2019-04) averages
  the best-move change count over all threads instead of the main thread's
  sample: gainer bounds passed at 4 and 8 threads (5+0.05) and at 8
  threads (20+0.2).
- **Fork:**
  - Add a per-search record of the best move at each completed iteration,
    in the iterative-deepening loop (`src/search/searcher.cpp`). A
    stability factor would multiply the soft limit only, never the hard
    limit or the reserve.
  - **Expected value: small to moderate (+3 to +8 in the engines above).
    Tier 1 for Phase 5.**
- **Pitfalls:**
  - Aspiration re-searches inside one iteration can change the best move
    temporarily. Count changes on completed iterations only, or decide
    deliberately.
  - Interacts with the node-share term (§4.4), which measures nearly the
    same thing; test them one at a time.

### 4.3 Score drops, fail-lows and score trend ("panic time")

- **What it is:** spend more time when the score falls, either within the
  current search (across iterations) or against the previous move's
  search, and less when it rises. The classic form is the **fail-low time
  extension**: when the root fails low, the best move has just been
  refuted and the engine extends its budget to look for a replacement.
- **History:**
  - Hyatt (talkchess, 2013-02-16) recalls adding a fail-low time
    extension to his program in the 1970s, after a game where a deeper
    iteration would have found the flaw in the chosen move. He says the
    idea was later published in the ICCA Journal (Hyatt 1984, "Using Time
    Wisely"; the paper itself was not opened, **UNVERIFIED** content).
  - In the same post he recounts Hsu's "panic time" idea: extend when the
    tree is growing abnormally, before any fail-low.
  - CPW lists fail-low panic time under "Historical techniques", which it
    describes as dropped once modern testing and tuning arrived. The
    evidence below shows the score-based adjustment survives in a
    continuous form.
- **Evidence and lineage:**
  - Ethereal:
    - 41e10402 (2018-07) scaled the extra time logarithmically with the
      size of the score drop: +2.5 ± 1.9 at 10+0.1, +3.4 ± 2.7 at 60+0.6,
      +3.9 ± 3.1 at 40/10 and +2.5 ± 1.9 at 40/40.
    - 9b29aaa0 (2018-07) removed the time *drop* when the score jumps up
      (non-regression).
    - #64 (2018-08), more time on a sudden score jump: failed at 10+0.1
      and 40/10, but passed at 60+0.6 (+4.1 ± 3.1) and 40/40 (+2.7 ±
      2.2). An unfinished 240+2.4 run stood at +32.8 ± 19.1 after 690
      games.
    - #67 extended it to smaller jumps: +2.5 ± 2.0 at 60+0.6 and +3.2 ±
      2.6 at 40/40.
    - This is one of the clearest published cases of a TM idea that gains
      at long TC and not at short TC.
  - Stockfish:
    - acc47e8b (2019-02) removed a separate "failed low" flag as adding
      nothing (non-regression).
    - 20484ccd (2019-12) made its falling-eval factor depend also on the
      score change over the last few iterations: passed STC and LTC.
    - 18f2b12c (2021-12) added the gap between the previous average best
      score and the current one: passed STC and LTC.
  - Berserk:
    - #101 (2021-05) let time grow with the number of aspiration-window
      re-expansions: +4.0 ± 3.2 at 10+0.1.
    - #412 (2022-10) used the score difference from the previous search.
      It did not pass gainer bounds (+3.3 ± 4.1 at 60+0.6, unfinished) and
      was merged on non-regression grounds.
    - #435 (2023-01) ignored positive differences (non-regression).
  - Stormphrax #187 (2024-08), less time when the score trend rises and
    more when it falls: +6.2 ± 3.4 STC and +2.6 ± 1.9 at 40+0.4.
  - Reckless #145 (eval stability, +6.2 ± 4.1 STC) and #375 (score trend,
    +4.3 ± 2.9 at 40+0.4).
  - PlentyChess #106 (eval difference, +4.7 ± 4.4 STC).
  - Halogen:
    - #761 (2025-10), the score change between searches: +1.2 ± 1.0 STC.
    - #294 (2021-04), more time on a fail-low, passed +4.1 ± 3.1 at 60+0.6
      and +6.7 ± 4.6 at 10+0.1 but was **not merged**. The reason is not
      stated (**UNVERIFIED**).
  - Alexandria #438 (eval stability, no data) and #618 (2026-07, score
    stability: +4.2 ± 2.6 STC and +4.0 ± 2.5 at 40+0.4).
- **Outside chess:**
  - Huang, Coulom and Lin (TAAI 2010, Go, MCTS): "think longer when
    behind" raised the win rate further on top of their other heuristics.
  - Baier and Winands (IEEE TCIAIG 2016) re-tested this "BEHIND" strategy
    with a control player that reproduces only its *distribution of time
    over the game*. In Connect-4 and 13×13 Go, BEHIND's gain came from that
    time shift alone. This is a methodological warning, not chess
    evidence (§6).
- **Long TC:** iterations are deep, so a drop seen at depth d is a real
  signal more often than at short TC. Ethereal's results show the gain
  growing with TC.
- **Fork:**
  - It already keeps the previous iteration's score for aspiration (T6).
  - A trend factor on the soft limit, from the score change over the last
    iterations and against the previous move's search, belongs beside the
    stability factor in the iterative-deepening loop.
  - A root fail-low inside the last iteration can also hold back the
    soft-limit stop until the iteration resolves. Fork's soft limit is
    already only checked between iterations, so the behaviour to decide
    is whether an unresolved fail-low may run up to the hard limit. It
    can today.
  - **Expected value: small to moderate (+2 to +6). Tier 1 for Phase 5.**
- **Pitfalls:**
  - Mate and TB scores make score differences meaningless. Berserk #327
    (2021-12) is a "fix with mate scores", non-regression. Clamp the trend
    the way Fork's LMR context clamps its score trend (`ScoreTrendLimit`).
  - Rising scores should not starve a winning attack of time; several
    engines removed the time drop on rising scores (Ethereal 9b29aaa0,
    Berserk #435).

### 4.4 Node share (search effort) on the best move

- **What it is:**
  - After an iteration, compare the nodes spent under the current best
    root move with the nodes of the whole iteration.
  - A large share means the alternatives were refuted quickly, so the move
    is probably right, and the soft limit shrinks.
  - A small share means several moves needed real work, so the soft limit
    grows.
- **Lineage:**
  - Hyatt's 2013 thread describes the idea (comparing the first root
    move's node count with the rest) as an easy and hard move detector.
    In the same thread he reports that transposition-table hits after a
    predicted move distort the counts.
  - Ethereal 60f4d5c5 (2022-06) says the idea was "first seen in
    Koivisto". Stockfish bf2c7306 (2024-02) also credits Koivisto and
    contrasts the forms: Koivisto scales the optimum time by the effort,
    while Stockfish stops early when the effort is high and time is past a
    scaled total.
  - The Koivisto commit that introduced it was not identified (a search of
    Koivisto's commit messages and PR titles for "time", "nodes" and "tm"
    did not name it; **UNVERIFIED**). Alexandria #167 (2023-06) thanks a
    Koivisto team member for pointing it out.
- **Evidence:** this is the largest and most consistent gain of any
  dynamic TM term in this survey.
  - Ethereal 60f4d5c5: +9.9 ± 6.2 at 10+0.1, +9.7 ± 6.0 at 60+0.6, +20.9
    ± 9.7 at 40/10 and +8.3 ± 5.5 at 40/40.
  - Viridithas #54 ("subtree-size TM", 2023-06): +5.6 ± 3.5 STC and +4.2
    ± 2.9 at 40+0.4.
  - Alexandria #167: +19.8 ± 7.4 STC and +15.9 ± 6.5 at 40+0.4.
  - Reckless:
    - #1 (2024-02): +17.3 ± 9.4 at 6+0.06.
    - #142 (2025-03), a distribution-based form: +17.6 ± 7.5 STC.
    - #143 skipped the term at low depth: +5.1 ± 3.5 STC.
  - PlentyChess #108 (2024-02): +4.1 ± 4.0 STC.
  - Stormphrax #137 (2024-05, re-enabled): +11.5 ± 6.1 at 14+0.14 and
    +20.8 ± 7.9 at 70+0.7.
  - Weiss #752 (2024-12): +11.4 ± 4.9 STC and +11.8 ± 4.9 at 40+0.4.
  - Halogen #638 (2025-06): +7.9 ± 3.8 STC, +13.4 ± 6.2 at 40+0.4 and +6.0
    ± 3.9 at 5+0.05 on 8 threads.
  - Stockfish bf2c7306: passed gainer bounds at STC and LTC. A later fix
    (944bee71, 2026-05) moved the counting back to its original place
    "right before making the move", and the formula was simplified
    (c9538625, 2025-11; non-regression).
- **Long TC:** the gains hold or grow at LTC in four engines (Stormphrax,
  Halogen, Weiss, Alexandria). A deep iteration's node distribution is a
  better estimate of how settled the root is than the depth-to-depth
  best-move history, which has few samples per move at long TC.
- **Fork:**
  - Needs per-root-move node counts: nodes before and after each root move
    in the root loop, summed over the iteration. This is cheap (two counter
    reads per root move).
  - With Lazy SMP (Phase 6), decide whether the main thread's counts or
    all threads' counts drive it. No published comparison was found
    (**UNVERIFIED**).
  - **Expected value: the largest single dynamic term (+5 to +20 in the
    engines above, often more at LTC). Tier 1 for Phase 5, first to
    test.**
- **Pitfalls:**
  - **TT distortion.** Hash hits make a root move's subtree look small
    (Hyatt 2013).
  - **Low depth.** At shallow depths the shares are noisy (Reckless #143).
  - **Where nodes are counted.** Counting in the wrong place silently
    changes the measure (Stockfish 944bee71).
  - **Single root move.** The share is trivially 100 %; the forced-move
    rule handles it first.
  - **Determinism.** The term uses node counts, not time, so it is
    deterministic for a fixed search; keep it out of `go depth` and bench.

### 4.5 Single legal moves, forced moves and recaptures

- **What it is:** spend little or no time when there is one legal move,
  or when a move is "obvious" (a lone recapture, a single non-losing
  reply).
- **Evidence and lineage:**
  - Šolak and Vučković (2009) name the single recapture in a quiet
    position as the typical case where thinking is wasted, and note the
    difficulty of defining "quiet". They carry the saved time forward to
    later moves.
  - Stockfish 04a32066 (2020-10) found that *not searching* a single
    legal move was not beneficial for strength. It now searches with
    normal TM under a small fixed cap, so the reported score is sensible.
    The message cites a TCEC Season 19 game where the unsearched move left
    artifacts in the output. A 2026-10 fix (f5940894) scales that cap in
    nodes-as-time mode.
  - Weiss #502 (2021-07) capped time on forced moves: non-regression at
    40+0.4.
  - Berserk #213 (2021-07) played a single legal move instantly
    (non-regression STC). Berserk #228 ("Instant Root Move") was
    non-regression; what it covers is not described (title only,
    **UNVERIFIED**).
  - Reckless #565 (2025-11), less time on recaptures: +4.5 ± 2.7 STC and
    +4.9 ± 3.1 at 40+0.4. #667 (2026-01) removed it again under
    non-regression bounds at STC and LTC.
  - Althoff (talkchess, 2016-12) lists the shortcuts in his CT800: one
    legal move, a mate available, a single move that prevents mate, and an
    easy move.
- **Fork:**
  - Has the forced-move stop (B-1): a fraction of the soft limit, so the
    score stays a few iterations short of normal (measured on a forced
    move at 60+0.6: 3,973 ms to depth 22 without it, 313 ms to depth 18
    with it, same score).
  - A recapture rule is not worth adding on this evidence: one engine
    gained and later removed it. The node-share term (§4.4) covers obvious
    recaptures implicitly.
  - **Expected value: small, mostly done.**
- **Long TC:** time saved on forced moves is more valuable with a large
  bank. Fork's rule already scales with the soft limit, so it saves more
  at long TC automatically.

### 4.6 "Will the next iteration finish?" rules

- **What it is:** before starting iteration d+1, predict its duration
  from the growth of the previous ones. If it probably cannot finish
  before some limit, either stop now, or spend the time on something
  useful.
- **Evidence, which points both ways:**
  - Grant (talkchess, 2017-12-23) predicted the next depth's duration from
    the last depth's time ratio and stopped if it would cross the maximum.
    He reported +9 to +13 at five single-thread controls (20+0.2, 5+0.05,
    40/4, 40/40) and one 3-thread control, and could not reproduce the
    gain with 6 threads. Hyatt replied that iterations often run long
    *because* a new best move is emerging, which is exactly when stopping
    hurts.
  - Ethereal 083c7286 (2018-07) then **removed** its "estimatedUsage"
    heuristic and *gained*: +11.9 ± 6.8 at 10+0.1, +6.5 ± 4.4 at 60+0.6,
    +6.8 ± 4.9 at 40/10 and +5.7 ± 4.1 at 40/40. That this is the 2017
    rule is Fork's inference from the name (**UNVERIFIED**).
  - Stockfish 69204f07 (2020-01) took a different route. Once a set share
    of the optimum time is used, it searches the *same depth again*
    instead of the next, reasoning that the next iteration takes about as
    long as everything so far. Repeating the depth still feeds helper
    threads and move ordering. It passed at STC and LTC on 1 thread and on
    8 threads.
  - That rule later let helper threads race to the maximum depth.
    2e02dd79 (2022-07) forced the effective depth to rise periodically
    (non-regression, including SMP LTC).
  - Berserk #379 (2022-06) checks the maximum time between depths, to
    prevent timeouts at low time without increment (non-regression at
    4+0.04).
  - Weiss #309 (2020-06) instead allowed *more* time to finish an
    iteration in cyclic controls: +4.2 ± 3.2 at 40/10 and +2.7 ± 2.2 at
    40/40.
  - CPW's "Premature termination" lists the elapsed-to-allocated check
    before a new iteration. Althoff and Muller (talkchess, 2016-12)
    describe the same "don't start if a set fraction is used" rule.
- **Fork:**
  - Fork's rule compares the predicted end with the **hard** limit, so at
    long TC it almost never binds (§1). It is a safety rule, not an
    allocation rule.
  - The long-TC question for Phase 5 is the allocation question: whether
    to stop *before* the soft limit when the next iteration would overrun
    it by a lot (Grant's form, later removed by Ethereal), or to let it
    run (Hyatt's objection), or to re-search the same depth (Stockfish's
    form, which mainly pays with threads).
  - The evidence conflicts, so this needs Fork's own LTC test. That
    matches DESIGN's "iteration rule first".
  - **Expected value: uncertain sign at long TC; small either way.**
- **Pitfalls:**
  - Iteration growth is noisy; Fork's p90 is 2.38 against a median of
    1.66.
  - With Lazy SMP, completion times vary more (Grant's 6-thread result).
  - A predictor tuned at depths 8-14 may not hold at depths 30+.

### 4.7 Other signals: complexity, clock difference, decisive positions, learned allocation

All of these are optional and lower priority; each needs its own test.

- **Position complexity.** Stockfish 2b037231 (2022-01) scaled time by a
  running average of an evaluation-complexity measure: passed gainer
  bounds at STC and LTC. It was later simplified away (38a80c0b, 2023-04,
  title only, **UNVERIFIED** detail). PlentyChess #422 (2025-11, a
  "corrplexity" factor from correction history): +1.5 ± 1.2 STC, but its
  LTC run stopped undecided (+0.9 ± 1.3, LLR 1.01) and it was merged.
- **Clock difference with the opponent.** Stockfish 5ca4bfe7 (2026-09,
  PR #7113) uses less time when its own clock is behind the opponent's.
  It passed gainer bounds at 10+0.1 and 60+0.6, and non-regression in
  sudden death 15+0 and 40/10. It is skipped in nodes-as-time mode and in
  the last move of a cyclic period. The formula is not described in the
  message or PR (**UNVERIFIED** form). A follow-up (23df8290, 2026-10)
  clamps negative clock values that some GUIs send, because they upset
  this calculation. This term reads the *opponent's* clock, which bears
  on §8.
- **Decisive positions.** Stormphrax #315 (2026-04), less time when the
  position is already decisive: merged after an unfinished
  non-regression run.
- **Learned allocation:**
  - Markovitch and Sella (IJCAI 1993; journal version Computational
    Intelligence 1996) frame TM as a resource-allocation problem with
    static, semi-dynamic (per move, before the search) and dynamic
    (during the search) strategies. They learned, in checkers, which
    positions benefit from a deeper search. Their learner recovered about
    a third of the possible gain over a random allocator, and they found
    the decision threshold must move with the resources left.
  - Kocsis, Uiterwijk and van den Herik (CG 2000) trained neural networks
    for semi-dynamic allocation in Lines of Action (the paper was not
    opened, **UNVERIFIED** detail; as described by Baier and Winands).
  - Fork's ideas.md idea 23 (heuristic discovery) could host such a
    search later. Nothing here suggests it beats hand-shaped terms.
- **"Stop when the best move cannot change."**
  - Lc0's `SmartPruningFactor` (Lc0 flags page) stops the search when no
    other move can overtake the current best in the remaining time.
  - Baier and Winands' "STOP" strategy is the same idea for MCTS and was
    their strongest strategy in all five games tested.
  - Both rely on MCTS visit counts. The alpha-beta analogue is the
    node-share term (§4.4), not a separate technique for Fork.

### 4.8 Emergencies, latency, Move Overhead and CPU contention

- **Move Overhead:**
  - It covers the time between the engine deciding and the GUI stopping
    its clock.
  - Several engines learned that it must not be shrunk by the increment
    (Stockfish 83c9e591, 2020-05), and that it must be counted as
    unusable time (Ethereal #147).
  - Stockfish raised its default after time losses reported by users
    (21926ce2, 2017-09).
  - Lc0 documents its overhead option as covering slow connections and
    inter-process communication.
  - At TCEC the option stays at the author's default unless the author
    asks, and the Swiss 10 testing list shows engines fixing time losses
    by raising it (§2).
  - Fork's default is 100 ms (owner); TCEC's recommended value is an open
    Discord question (competition.md, open question 5).
- **Clock polling:**
  - Fork polls every 1,024 nodes. Stockfish 4b297976 (2023-07) halved its
    poll interval when NNUE roughly halved its nps. A node-count interval
    means a time interval that changes with speed.
  - At 512 threads only one thread needs to read the clock: Reckless #707
    (2026-02) stopped helper threads from polling the OS clock, and #797
    (2026-03) fixed multithreaded time checks (+6.1 ± 3.2 at 5+0.05 on 8
    threads).
  - Phase 6 should keep the hard-limit check on one thread with a shared
    stop flag.
- **Blocking I/O between polls:**
  - Stockfish 4b88bea4 (2018-06) forced a clock check after every
    tablebase read. Thousands of probes on a spinning disk between two
    polls could exceed the Move Overhead.
  - Stockfish 4b71d8e2 (2025-11) allowed time checks after each DTZ probe
    in the root ranking. The message says Stockfish lost games on time at
    TCEC "when the HDD with the DTZ tables was too slow". Its local repro
    had 19 timeouts in 100 games with DTZ on a slow disk.
  - TCEC keeps 7-man DTZ on an HDD (§2). Fork's root DTZ probe runs before
    the first hard-limit poll; DESIGN already lists the 7-piece cold-cache
    cost as a Phase 8 measurement. **Phase 5 should add a test with a slow
    or cold tablebase path.**
- **Emergency play:**
  - Halogen #132 (2020-11) always completes a depth-1 search in time
    panic, so a legal, searched move exists (non-regression).
  - Halogen #377 (2022-03) fixed a path to illegal moves under extreme
    time pressure. Its non-regression run ended at H0 (-6.9 ± 4.6 at
    8+0.08) and it was merged anyway as a correctness fix. The PR gives no
    reason for the Elo loss (**UNVERIFIED**).
  - Fork already returns the best move of the last completed iteration,
    and has a stall test (deliverable 8). It should also check that a
    hard-limit abort during iteration 1 still yields a legal move.
- **CPU contention:**
  - Stockfish's nodes-as-time mode (926f2150, 2015-03) was introduced
    because OS scheduling does not share CPUs evenly between two engines
    in parallel games or beside background processes, which adds noise to
    timed tests.
  - The mode converts the clock to a node budget once per game.
  - It has an artifact the author names: nps rises toward the endgame,
    so a fixed nodes-per-ms rate skews the allocation.
  - It is for tuning only and needs equal engine speeds.
- **Under load (Fork's reasoning, not a published result):**
  - nps falls, so each iteration takes longer in time. A time-measured
    iteration rule and hard limit stay safe; node-measured terms (§4.4)
    are unaffected.
  - The danger is the gap between polls and the latency of `bestmove`
    output when the process is descheduled. That is exactly what the
    Move Overhead must absorb.
  - Deliverable 8's stress test (2,000 games at 2+0.02 with every CPU
    busy: B2 had 0 forfeits) is the right shape. Phase 5 should repeat it
    at a long-TC-shaped control (§6) and with a slow tablebase disk.
- **Fork component:** `src/search/time_budget.cpp`, `poll_limits` in
  `src/search/searcher.cpp`, and the root probe in
  `src/search/endgame_tables.cpp`.
- **Expected value:** no Elo when nothing goes wrong. Each avoided time
  forfeit at TCEC is a full point, and "no chance to patch" applies
  (competition.md). Highest priority for safety.

### 4.9 Repetition-draw and tablebase-adjacent time savings

- **Draw-PV extra time:**
  - Stockfish e50af36a (2017-10) thought longer when the PV ended in a
    repetition or fifty-move draw and it was ahead on time. It failed
    gainer bounds at STC but passed at LTC.
  - Four months later d71adc5b (2018-02) retired it under non-regression
    bounds, including sudden death and 1+1 checks. The message argues
    that TM "drifts" as search improves (fewer fail-lows, fewer best-move
    changes, lower mean time), and that a term which adds time anywhere
    can look good only because the base allocation had become too
    stingy. Re-tuning the base recovers the same Elo.
  - This is a general lesson for Fork: re-tune the base allocation after
    big search or evaluation changes (Phase 4's network) before trusting
    any add-on.
- **Tablebase root positions:**
  - When the root is in the tables, the root ranking decides the result
    class. Stockfish 108f0da4 (2018-04) describes ranking all root moves
    by TB result and letting the search choose among the best rank.
  - Whether an engine should then also save time (for example, move fast
    in a TB-won or TB-drawn root, where the search only picks among
    equal-result moves) has no published test in the sources read
    (**UNVERIFIED** value).
  - Berserk #228's title ("Instant Root Move") may be such a rule; its
    form is not described (**UNVERIFIED**).
  - At TCEC, games end by the draw rule soon after reaching 6 or fewer
    pieces with a near-zero evaluation (competition.md). Time saved in TB
    endings is therefore worth little in drawn endings, and could matter
    only in long won or lost 7-piece conversions.
- **Repetition at the root:**
  - No source read measured a time saving for positions where the engine
    can claim or force a repetition. CT800's shortcuts (Althoff 2016) do
    not include it.
  - **UNVERIFIED**: not documented in any source read.
- **Fork:** these are not worth adding before §4.2-4.4 are measured. A TB
  root time rule would be Fork's own idea, with its own non-regression
  test.

### 4.10 Pondering

- TCEC disables pondering (§2), so the techniques for pondering do not
  apply to Fork's Phase 5. These are ponder-hit budgets, focused
  pondering, and reducing time after a correct guess (Huang, Coulom and
  Lin 2010; CPW Pondering).
- Fork's limits count from `go ponder`, which leaves an instant move after
  `ponderhit` (DESIGN, audit-1 note). That stays a non-TCEC issue.

---

## 5. Short versus long time control, in one place

| Aspect | Short TC (8+0.08, 10+0.1) | Long TC (TCEC 30'+3" to 120'+12") |
|---|---|---|
| Iterations per move | many shallow ones; the soft limit is fine-grained | few deep ones; each start/stop decision moves seconds to minutes |
| Iteration growth | measured (Fork: median 1.66 at depths 8-14) | unmeasured at depths 25-40 and 512 threads (**UNVERIFIED** for Fork) |
| Overhead and polling | a large part of every move; reserve rules bind | negligible per move, but one stall (a TB read on HDD, descheduling) can still flag |
| Late game | the clock is mostly increment from early on | about 20× less time per move late than early (§3); the increment share sets the late-game budget |
| Dynamic terms | gains are real but noisy | several terms gain more at LTC (Ethereal #64, Stormphrax #137, Halogen #638); others pass STC and stall at LTC (PlentyChess #422) or the reverse (PlentyChess #358: failed at STC, passed at 80+0.8) |
| Tuning | cheap SPSA | Stockfish tuned TM separately at 180+1.8 (0f01a516: 35k games of SPSA, then passed at 180+1.8 and 240+2.4); PlentyChess tuned at 80+0.8 (#358) |

---

## 6. How engines tune and measure TM

- **SPRT at several controls:**
  - Stockfish and Ethereal routinely test a TM change at Fischer STC and
    LTC, **plus sudden death and a cyclic control as non-regression**
    (for example Stockfish 9be2977d, c6ce612f, 07a2619b and 82908e0f;
    Ethereal #147 and 60f4d5c5).
  - A TM change can be neutral at Fischer controls and decisive in sudden
    death (Ethereal #147).
  - For Fork, TCEC is Fischer-only, but local and rating-list games are
    not. Keep a sudden-death and a cyclic non-regression check.
- **TCEC-shaped controls:**
  - fishtest's "TCEC style" runs used 10+0.01: a short base with an
    increment of a thousandth of it. This was confirmed in the run records
    for c6ce612f and a615efb1.
  - TCEC's own ratio of increment to base is 1/600 (3 s on 1,800 s).
    60+0.1 keeps that ratio exactly at a testable cost. This is Fork's
    inference, not a published practice.
  - Such controls exercise the increment-dominated late game (§3) far
    more than 8+0.08 (ratio 1/100) or 40+0.4.
- **Very long TC:** Stockfish's VLTC TM tune was SPSA at 180+1.8, then
  SPRT at 180+1.8 and 240+2.4 (0f01a516). PlentyChess tuned TM at 80+0.8.
  TM parameters tuned at STC do not carry over (PlentyChess #358 failed at
  STC with the VLTC values and passed at 80+0.8).
- **Tunable TM parameters:** Viridithas #131 (2024-02) exposed its TM
  factors for tuning, and gained in the same commit (+20.9 ± 9.4 STC, +7.1
  ± 4.7 LTC) for a reason its author did not identify. Fork's parameter
  table (deliverable 8b) already holds the time constants, so SPSA can
  reach them in a `FORK_TUNE` build.
- **Time-odds tests:**
  - fastchess accepts a per-engine `tc=` (man page, `-engine` options), so
    a match can give one engine less time.
  - fishtest run records carry separate `tc` and `new_tc` fields (in the
    records read they were equal).
  - A fishtest issue (#910, 2021) proposed time handicaps to control the
    draw rate.
  - Use for Fork: measure how many Elo a given fraction of time is worth
    at the test control (Fork against itself at, say, 1.0× and 0.9×). A TM
    change that saves time on average can then be judged as "x % less time
    for y Elo", and a change that only spends more time overall can be
    caught.
- **Separate the time-shift effect.** Baier and Winands (2016) built
  "DISTRIBUTION" control players that reproduce only the average time per
  move number that a strategy produces, and found that some strategies
  gained only through that shift. Fork's version:
  1. log the time spent per move number in the candidate's games;
  2. build a variant that only reshapes the base allocation to match;
  3. SPRT the candidate against that variant.
  If the candidate does not beat it, the gain is just "spend time
  differently over the game", and the simpler base change should be kept.
- **Deterministic TM tests:**
  - Nodes-as-time (Stockfish 926f2150; Weiss #727 added it on 1 thread)
    removes scheduling noise for parameter tuning.
  - Its limits are those named in §4.8: equal speeds, an nps artifact,
    and not for SMP. Use it for SPSA, never for the safety stress test.
- **Runner margins hide overruns.**
  - OpenBench's wiki says it gives a 250 ms time-margin buffer in timed
    games "to avoid time losses". fastchess has a `timemargin` option.
  - For Fork's safety tests the margin must be zero, and forfeits are
    counted separately from the SPRT result.
  - fastchess can also print the measured-versus-reported "think latency"
    (`-show-latency`) and record time left and latency per move in the PGN
    (`-pgnout timeleft=true latency=true`). These are the right
    instruments for checking Move Overhead.
- **Cost of testing (Fork's rough arithmetic):**
  - A 60+0.1 game lasts about 2 × (60 s + 0.1 s × moves), roughly 2-2.5
    minutes.
  - 20,000 games come to about 45,000 game-minutes, around 95 hours at
    concurrency 8.
  - A 40+0.4 SPRT of similar length costs about the same.
  - TCEC's real control (1,800+3) cannot be SPRTed at all. That is why
    the engines above test at 40+0.4 to 240+2.4 and rely on terms that
    hold their sign across controls.
  - Plan Phase 5's runs on the GitHub and AWS shards, one heavy job at a
    time (CLAUDE.md).
- **Re-tune after the network.** Stockfish d71adc5b's drift argument
  (§4.9) and DESIGN's Phase 4 re-validation both say: retune the base
  constants after Phase 4's network changes the search's stability.

---

## 7. Phase 5 order for Fork, ranked by expected value at TCEC conditions

1. **Safety first (no Elo, a full point per avoided forfeit):**
   - the stress test repeated at a TCEC-shaped control;
   - a slow or cold tablebase path, with the root DTZ probe timed against
     the hard limit;
   - a zero-margin runner, with forfeits counted.
2. **Node share (§4.4):** the largest and most consistent published gain,
   often larger at LTC.
3. **Best-move stability (§4.2)** and **score trend / fail-low (§4.3):**
   test one at a time on top of 2, then together.
4. **The iteration rule at long TC (§4.6):** DESIGN's carried-over item.
   The evidence conflicts, so Fork must measure it.
5. **Base constants retuned at long TC (§4.1):** SPSA in a tuning build at
   a long control, then an SPRT, then again after Phase 4's network.
6. **Optional:** clock-difference, complexity and TB-root terms (§4.7,
   §4.9), each only with its own test. Recapture rules are not worth it
   (§4.5).

---

## 8. Open question from DESIGN: a `go` with a clock only for the opponent

- **What the spec says.** The UCI specification (April 2006,
  engine-interface.txt, re-read 2026-11-02; same SHA-256 as recorded in
  sources.md) says that a `go` parameter that is not sent "should be
  interpreted as it would not influence the search". It defines `wtime`
  and `btime` separately. So `go btime 1000 binc 10` with White to move
  literally puts no limit on White's search. That is Fork's behaviour
  today: it searches until `stop`.
- **What runners send** (uci.md §7):
  - fastchess and cutechess send `wtime` and `btime` together in timed
    games, so the case does not arise in normal play.
  - fastchess's compliance check sends `go wtime 100` alone. That carries
    the side to move's clock when White is to move. Which side is to move
    in that check is not recorded in uci.md (**UNVERIFIED** whether the
    check ever probes the opponent-only case).
- **How other engines handle it:** not documented in any commit message,
  PR or document read (**UNVERIFIED**). Stockfish's time-disadvantage
  term (§4.7) shows that engines do read both clocks, and its 23df8290
  shows GUIs do send odd clock values (negative times).
- **The options:**
  - **(a) Keep the spec-literal reading (no limit).**
    - Consistent with a bare `go`.
    - Costs a sure loss on time if a broken GUI or a typo ever sends it in
      a game.
  - **(b) Treat any clock argument as a timed game.** If the side to
    move's clock is missing, budget from the opponent's clock (the best
    available guess of the game's clock), or from a small fixed fallback.
    - Safe in a game, still easy to test.
    - Deviates from the literal spec only in a case the spec does not
      foresee.
  - **(c) Move at once.**
    - Safe, but plays a depth-1 move on bad input.
- **Fork's recommendation, for the owner to decide:** (b) with the
  opponent's clock as the proxy, falling back to (c)'s minimum budget if
  that clock is non-positive. Rationale: a TCEC game can only lose by
  searching forever, never by planning a budget.
- **Test:** a UCI transcript case where `go btime 1000 binc 10` with White
  to move returns `bestmove` within a bound. Fault-inject by removing the
  fallback; the test must then time out.

---

## 9. UNVERIFIED items in this entry

1. Season 31 time controls: not published (no S31 rules page).
2. The meaning of "a one second margin" on the Swiss 10 page.
3. Which DTZ files Fork's `SyzygyPath` would read from TCEC's HDD.
4. The CPU load an engine sees during its own move at TCEC: not described
   on any TCEC page.
5. Hyatt (1984) "Using Time Wisely" (ICCA Journal 7(1)) and Hyatt, Gower
   and Nelson (1985): not opened. Their content is known only from CPW,
   Hyatt's 2013 post and the citing papers.
6. Kocsis, Uiterwijk and van den Herik (2000): the author's postscript
   link failed. The content is from Baier and Winands' summary.
7. Šolak and Vučković (2009), "Time Management during a Chess Game"
   (ICGA Journal 32(4)): not opened. Only the Facta Universitatis paper
   was read.
8. Donninger (1994) "golden rules": known only as quoted by Baier and
   Winands; the paper was not opened.
9. The Koivisto commit that introduced node-share TM: not identified.
10. Whether Ethereal 083c7286's removed "estimatedUsage" heuristic is the
    rule from Grant's 2017 post: inferred from the name.
11. Why Halogen #294 (fail-low extra time) was not merged despite passing,
    and why Halogen #377's fix lost Elo.
12. The form of Berserk #228 "Instant Root Move" (title only).
13. The detail of Stockfish 38a80c0b (complexity removed; title only) and
    the formula of 5ca4bfe7 (clock difference; not in the message or PR).
14. Whether node share should use the main thread's or all threads'
    counts under Lazy SMP: no comparison found.
15. The value of TB-root or repetition time savings: no published test
    found.
16. How other engines treat a `go` with only the opponent's clock; whether
    fastchess's compliance check ever sends that case.
17. Fork's iteration growth at depths 25-40 and on 512 threads: not
    measured.
18. The arithmetic in §3 and §6 is Fork's model (every move spending
    exactly the soft limit; rough game lengths), not a measurement.

---

**Names Fork's code must not use** (identifiers seen in the commit
messages, PR texts and the forum post read for this file; DESIGN.md §8's
rule applies to all new names): `bestMoveChanges`,
`totBestMoveChanges`, `fallingEval`, `timeReduction`, `optimumTime`,
`maximumTime`, `increaseDepth`, `searchAgainCounter`, `highBestMoveEffort`,
`complexityAverage`, `stopOnPonderhit`, `npmsec`, `nodestime`, `easyMove`,
`SlowMover`, `improvingFactor`, `failedLow`, `estimatedUsage`,
`timeUsage`, `limitedBySelf`, `optScale`, `maxScale`, `minThinkingTime`,
`moveOverhead`. The concepts are fine; the identifiers are not.
