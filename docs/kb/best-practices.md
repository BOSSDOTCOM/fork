# Best practices: testing discipline, determinism, pitfalls

Fork's working rules, each with its reason and source. Tags follow the KB
convention: **USE** (adopt as is), **REFERENCE ONLY** (idea studied, our own
implementation), **OFF-LIMITS** (never). "Verified" means the source page was
opened on that date.

---

## 1. Correctness gates

### Perft before anything else
- **What:** count the leaf nodes of the legal move tree to a fixed depth
  and compare them with published counts. Use `divide` (a count per root move)
  to find the move where a bug starts.
- **Why for Fork:** it's Phase 1's sign-off gate, and it re-runs on every
  build preset, so a movegen regression can't reach search testing.
- **Fork practice:** besides the suite, Fork runs a color-flipped copy of every
  position and checks internal invariants at every node. These include
  incremental key equals recomputed key, unmake restoring the exact state, FEN
  round-trip, capture and quiet lists partitioning the legal list, and
  `is_legal` agreeing with the generator. These catch bugs that a matching
  node count can hide.
- **Pitfall (Fork, 2026-10-23):** test oracles must be copied from the source
  page, never typed from memory. Position 6 was first entered without its
  black bishop on g4 and failed against correct move generation. Every oracle
  FEN and count is now checked against the page.
- **Pitfall:** perft with hashed node counts is faster but can be wrong on a
  key collision. Fork's perft tests don't hash.
- Tag: USE (technique). Sources: [CPW Perft](https://www.chessprogramming.org/Perft),
  [CPW Perft Results](https://www.chessprogramming.org/Perft_Results). Verified 2026-10-23.

### Sanitizers and two compilers
- **What:** debug builds run all tests under ASan + UBSan on Clang and GCC.
  Release builds are warning-free (`-Werror`) on both compilers.
- **Why for Fork:** undefined behaviour in bit tricks (shifts by 64,
  signed overflow) can stay silent on one compiler and break the other. TCEC
  builds Category 4 engines from source on Linux, so Fork must build cleanly
  wherever it's built (see [competition.md](competition.md)).
- **Pitfall:** MinGW GCC on Windows has no sanitizer runtimes, so the GCC
  sanitizer gate runs only on Linux (WSL2).
- Tag: USE. Source: Fork DESIGN.md section 2.

## 2. Determinism

### Bench is the fingerprint of a build
- **What:** `fork bench` runs a fixed workload and prints a node count and a
  signature. Every build preset compares them with `tests/bench.ref`. That
  covers both compilers, every arch target, PEXT and magics, PGO, and both
  OSes.
- **Why for Fork:** if the node count is the same, the search tree is the
  same. A change meant to be speed-only that changes bench isn't
  speed-only. OpenBench-style testing also uses the bench count to identify
  each commit.
- **Rules:**
  - Bench is single-threaded with fixed depth. Never use time-based limits
    in bench.
  - Every pseudo-random choice (magic search, Zobrist keys, any future
    randomization) uses a fixed seed.
  - A commit that changes search must update `bench.ref` and state the new
    count in its message.
  - Never read uninitialized memory or depend on hash-table contents left
    from a previous bench position. Clear the TT between bench positions
    (from Phase 3).
- **Pitfall:** floating point in eval or time management can differ between
  `-march` targets (FMA contraction). Keep search decisions in integer
  arithmetic, or compile with `-ffp-contract=off` where floats are
  unavoidable.
- Tag: USE.

### Fixed-depth vs. timed testing
- Deterministic fixed-depth or fixed-node games are easier to debug. Timed
  games test real behaviour. Use the first to find bugs and the second to
  accept changes.
- Search changes such as pruning, reductions and extensions depend more on
  time control than eval tuning does. A change only triggered at high depth
  needs a time control long enough to reach that depth.
- Source: [CPW Engine Testing](https://www.chessprogramming.org/Engine_Testing). Verified 2026-10-23.

## 3. Accepting changes: SPRT

- **What:** a sequential test that keeps playing game pairs until the
  log-likelihood ratio crosses a bound set from the error rates (alpha, beta),
  then accepts or rejects the hypothesis that the patch gains at least
  `elo1` rather than at most `elo0`.
- **Why for Fork:** the brief requires SPRT for every change. SPRT stops as
  soon as the result is significant, rather than after a fixed game count.
- **Fork rules:**
  - Every functional change gets an SPRT. Gainers use bounds like [0, 5]
    while Fork is far from the top. Simplifications use non-regression bounds
    like [-5, 0]. Bounds tighten as Fork gets stronger, because Elo gains
    compress near the top. The CPW table of common bounds runs from [0, 10]
    for most engines to [0.5, 2.5] for Stockfish LTC.
  - Use pentanomial statistics (scoring game pairs, not single games). The
    CPW page notes fastchess supports them and they end tests sooner.
  - Every opening is played twice with colours reversed (`-repeat`). TCEC
    pairs its openings the same way.
  - Test at short TC (STC) first, then at long TC (LTC) for anything touching
    search. TCEC plays 30'+3" to 120'+12".
  - An SPRT result applies only to the tested binary. Rebuild and retest
    after rebasing onto other accepted changes.
- **Pitfall:** stopping a test early when it looks good breaks the statistics.
  Let the LLR reach a bound.
- Tag: USE (method). Sources: [CPW SPRT](https://www.chessprogramming.org/Sequential_Probability_Ratio_Test),
  [CPW Match Statistics](https://www.chessprogramming.org/Match_Statistics). Verified 2026-10-23.

## 4. Testing under TCEC conditions

- **Match TCEC's adjudication, not older rules.**
  - The current TCEC draw rule applies at 6 or fewer pieces (kings counted,
    pawns not), with the eval within ±0.25 for 8 consecutive plies.
    Captures and pawn moves don't reset it, and there is no minimum move.
  - There is no eval-based win adjudication. Games end by mate, an illegal
    move, resignation or time.
  - Phase 8 scripts must read these values from `config/tcec.json` rather
    than the brief's older ones (see [competition.md](competition.md)).
- **Tablebases:** TCEC gives engines 7-man Syzygy. Local testing should
  use whatever is installed (5-man by default, 6-man optional), but Fork's
  probing must be tested against 7-man files before entry.
- **No pondering, no own book.** TCEC disables pondering and removes engine
  books. A hidden book means disqualification.
- **Scale:** TCEC hardware gives up to 512 threads and 256 GiB of hash, the
  latter only when hash initialization is multithreaded. Phase 6 needs a
  multithreaded hash clear and a test at the full thread count on whatever
  large machine is available.
- **Large pages:** the TCEC hardware page says large pages are used
  automatically. Fork must still never *depend* on them (the brief's
  rule), but should not defeat them either. For example, it shouldn't use an
  allocation pattern that prevents transparent huge pages.
- Sources: [TCEC Rules](https://wiki.chessdom.org/Rules),
  [TCEC Season Further information](https://wiki.chessdom.org/TCEC_Season_Further_information).
  Verified 2026-10-23.

## 5. Zero time losses

- Keep a `Move Overhead` safety margin and test under artificial CPU load
  (Phase 5). A time loss in TCEC costs a full point and is visible to
  everyone.
- Check the clock in search often enough at very high node rates (512
  threads), and make sure the stop signal reaches every thread promptly.
- Run the stress test (thousands of games) on the exact binary that will be
  submitted. Every crash and every time loss counts as a failure.
- Source: owner brief, Phases 5 and 8.

## 6. Originality hygiene (see [originality.md](originality.md))

- Log every reference in `docs/ORIGINALITY.md` when it's consulted, not
  afterwards.
- **OFF-LIMITS as training data:** anything labelled by another engine.
  That includes Stockfish evals, Lc0 evals, Lichess `[%eval]` comments and
  ChessBench (see [research.md](research.md)). Positions from CC0 game
  collections may be used as starting points if their evals are stripped
  and Fork rescores them.
- Fork is written with major help from AI, so under the TCEC Season 30 rules
  it falls into **Category 4**. The code must be public and buildable by
  TCEC admins, and the questionnaire must disclose the AI help truthfully.
  Under the TD statement of 2026-08-31, AI engines enter through the Swiss
  playoff and are not eligible for the regular Leagues.
  Source: [TCEC Swiss 10](https://wiki.chessdom.org/TCEC_Swiss_10). Verified 2026-10-23.

## 7. Repository discipline

- One commit per finished piece. Never commit with a failing test. The bench
  reference changes only in the commit that intends to change it.
- All tunable search and eval parameters live in one table (Phase 3) so SPSA
  can tune them at long time controls.
- Tournament-specific values live only in `config/tcec.json`. The engine
  never reads that file.
