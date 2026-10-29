# Phase 3 Milestone C report (2026-10-27)

Milestone C (DESIGN.md §5.2): deliverables 7 (Syzygy probing) and 8 (basic
time management) done, so the core of Phase 3 is complete. Since Milestone
B: the two external reviews' fixes and their SPRTs, deliverable 8b (the
parameter table) and the harness for the heuristic-discovery pilot (8c,
not started).

## What was built

| Commit | Content |
|---|---|
| 6ae4128, 3a8a1b6, 1efade9, 738daff | The external reviews' fixes: SEE pruning skips proven-good captures; futile nodes keep only checking quiets (nps +12.7%); early-exit SEE threshold, TT static-eval reuse, null-move TT prefetch (+2.9%); switches for the TT-refined pruning eval and keeping exact TT entries |
| 1fb18f4 | The root fail-high fix reverted (its SPRT rejected it); the bookkeeping stays (ideas.md idea 29) |
| 23f1b10 | 7: Syzygy probing through vendored Fathom (MIT, pinned), WDL in the search, root ranking by DTZ, `SyzygyPath`, tbhits |
| 4ec034d, 008b67f | 8, first form; the budget formula credited to Berserk 4.5.0-8 (owner's decision: kept, with an explanation and a credit) |
| 2a7541f | The TT-refined pruning eval on by default, provisionally (owner) |
| a11a396 | 8b: the parameter table (`src/tune/params.hpp`, 28 parameters then, 29 now: LmrCorrectionStrength and DangerZoneOverheads added, ReserveOverheads removed; tuning builds declare them as spin options; bench unchanged) |
| 980b891, 7cbf45b, c3ab1aa | 8c preparation: the heuristic-discovery harness (`tools/evolve/`), its position set, dry run and proxy budget |
| afe8946 | The last info line names the move played after a reported aspiration fail (a reporting gap found by a load-dependent test failure) |
| 91365e2 | 8, final form (the owner's split): the increment fix, the danger-zone reserve (B2), the iteration rule |

Also: development at normal priority beside games with low priority after
a time loss (b7ab410); checks that never overlap and report skips
(58f899d); the Linux check rebuilding when its source tree changes
(afe8946); no user-name paths in the harness config or the SPRT log (a
rewrite of twelve unpushed commits, hash table in
path-rewrite-2026-10-27.md). Every code commit passed `scripts/check.sh full`
(Windows presets and UCI smoke loop, Linux, Ubuntu 22.04 with gcc 11.4,
g++-12, clang 16, clang 19, bench parity), except two the owner asked to
commit without it (008b67f, comments only; 2a7541f, a default flip whose
bench parity the next full check confirmed).

Bench now: 17,309,921 nodes, signature 372dc2e2d8a88e4b (depth 13; it
changed once, with the TT-refined eval's default).

## SPRTs (details in sprt-log.md)

| Test | Bounds | Result |
|---|---|---|
| Root fail-high fix (review 1, a) | [-3, 0] | **REJECTED**, -14.6 ± 10.8 at 2,000 games (stopped by the owner); reverted |
| Futile-node quiet filter (review 1, d) | [-3, 0] | **ACCEPTED**, +11.5 ± 11.9 at 2,000 (stopped by the owner) |
| TT-refined pruning eval (review 2, d) | [0, 3] | **PROVISIONAL**, +14.6 ± 17.8 at 1,000 (stopped by the owner); on by default, removal round at STC and LTC |
| Keep exact TT entries (review 2, e) | [-3, 0] | **INCONCLUSIVE** at the owner's cap, -0.6 ± 7.5 at 4,800; off, removal round |
| Syzygy probing on vs off (7) | [0, 3] | **ACCEPTED** (owner's decision), +17.5 ± 7.2 at the 5,000 cap, the 95% interval above zero |
| Time management, first form (8) | [-3, 0] | INCONCLUSIVE at the cap, -4.9 ± 7.1 (about -10 midway): led to the owner's split |
| Time management, final form vs (a) | [-3, 0] | **ACCEPTED** (stopped by the owner), +1.9 ± 10.6 at 2,200 |
| Final form at 40+0.4 vs (a) | [-3, 0] | INCONCLUSIVE (stopped by the owner): -14.8 ± 20.9 at 400 games, -4.7 ± 18.0 over all 590; no faults. Flagged for Phase 5, the iteration rule first |

Earlier in this stretch (owner's queue of 2026-10-26): tier 1 pruning on vs
off at 40+0.4, H1, +556 Elo in 306 games; the TT victim policy (blended
against lexicographic) at 40+0.4, stopped inconclusive at +5.7 ± 13.8.

## Deliverable 7: Syzygy probing

- Fathom vendored at a pinned commit (MIT; ORIGINALITY.md, third-party);
  probes from depth 1 at non-root nodes with no castling rights and a zero
  halfmove clock; root ranking by DTZ (WDL fallback); cursed wins and
  blessed losses just off zero; `SyzygyPath` only (owner).
- Tests: Fork's probes against python-chess on 3,000 random 3-4-5
  positions, 0 disagreements (fault-injected: 147 of 500 disagree); the
  7-man KPPPPPvK pair (downloaded by CMake, pinned), checked against the
  lichess tablebase API; missing and partial paths; Linux `MADV_RANDOM`.
- **Conversion suite** (`tools/conversion_suite.py`): 100 random TB-won
  4-5 piece positions near the fifty-move limit, played out against a
  TB-perfect defender: **100 of 100 converted**.
- SPRT: +17.5 ± 7.2 Elo (accepted by the owner).

## Deliverable 8: time management

- **Final form** (the owner's split, 2026-10-27): (a) the increment adds
  three quarters of itself, multiplied before dividing; (b) the reserve is
  a tenth of the clock, plus one Move Overhead only in the danger zone
  (less than two overheads plus an increment available); (c) no iteration
  starts that would probably not finish before the hard limit.
- **Time losses** (2,000 games at 2+0.02 with every CPU busy, each):

| Build | Time forfeits |
|---|---|
| Milestone B (before 8) | 0 |
| 8, first form (fixed two-overhead floor) | 0 |
| (a) increment fix alone | **3** (clock down to about one overhead each time) |
| (c) iteration rule alone | 1 |
| B1 "deficit" reserve | 0 |
| B2 "danger zone" reserve (chosen) | 0 |

  Every SPRT since Milestone B: 0 time losses, crashes or illegal moves in
  24,825 games (ten SPRTs, three of them at 40+0.4; the stress tests
  above add 12,000 games under full load).
- **Timing on an idle machine**: the timing tests pass on Windows and Linux
  release builds (stop to bestmove 0.28-0.55 ms, against 10 ms);
  `go movetime` never overran (30 searches each: at most 25.2, 100.2 and
  884.9 ms after go for 50, 200 and 1,000 ms).

## Elo: the Milestone C gauntlet

1,200 games at 10+0.1 (91365e2, TCEC build), 200 against each anchor, from
the same 200 random 8-ply openings as Milestones A and B (both colours),
concurrency 10, fastchess; Ordo with the anchors fixed at their CCRL Blitz
2'+1" ratings (list of 2026-10-24). The anchors: the Milestone B set plus
Weiss 1.0 above it (set c). The two further anchors the KB found for the
2603-2896 gap, Supernova 2.4 (2679) and K2 0.99 (2750), are not built yet
(Open, 2).

| Opponent | CCRL Blitz | Fork's score (W / D / L) | At Milestone B |
|---|---|---|---|
| Belette 2.0.0 | 2115 | 142.5 / 200 (71%; 133 / 19 / 48) | 124.0 (62%) |
| Stash 15.3 | 2173 | 145.0 / 200 (72%; 135 / 20 / 45) | 133.5 (67%) |
| Chal 1.3.0 | 2285 | 131.0 / 200 (66%; 118 / 26 / 56) | 136.5 (68%) |
| Stash 19.0 | 2473 | 97.5 / 200 (49%; 90 / 15 / 95) | 81.0 (40%) |
| WyldChess 1.51 | 2603 | 61.5 / 200 (31%; 48 / 27 / 125) | 38.5 (19%) |
| Weiss 1.0 | 2896 | 23.0 / 200 (12%; 18 / 10 / 172) | not played |

**Fork: 2402.5 ± 23.3 on the Milestone B anchors** (the 1,000 games without
Weiss, Ordo, 1,000 simulations), against **2343 ± 23** at Milestone B and
1773 ± 32 at Milestone A: about +60 on the same scale. With Weiss 1.0 as a
sixth anchor: **2409.5 ± 22.9**. The same caveats as before: a rough
placement at 10+0.1 on this machine, not a CCRL rating; the anchors keep
their default hash. All games ended by the rules except two time losses,
both Stash 15.3's (398 ms and 15,140 ms over, games 280 and 724), both won
by Fork; Fork lost none on time, and nothing crashed or disconnected.

## Performance

Search nps (WSL, `tools/perf_gate.sh 91365e2 f919c01`: the A/B harness,
6 interleaved rounds, identity checked on all 12 runs, noise threshold
4.7%): Milestone C (91365e2) against the Milestone B build (f919c01):
median 5,953,901 -> 6,625,718 (**+11.3%**), best +12.6%: B faster. The two
search different trees (bench 17,309,921 against 16,540,472 nodes: the
TT-refined eval's default changed it), so this is the builds' speed, not a
same-tree comparison. The review's fixes were measured on the same tree
when made: the futile-node quiet filter +12.7%; the early-exit SEE test,
TT static-eval reuse and null-move prefetch +2.9% together (within the 3%
noise rule then). Profile (perf, `fork bench`): `MoveSelector::take_next`
19.5% (25.9% at B), `see_at_least` 12.9%, eval (`side_score`) 10.8%,
`generate<Captures>` 9.5%, `refresh_check_info` 7.7%, `negamax<false>`
7.7%, `quiesce<false>` 5.6%, TT 8.0%, make/unmake 6.7%, `predicted_key`
2.2%. (The gate's profile step failed on a relative path, fixed in
`tools/perf_gate.sh`; the profile was taken by hand.)

## Originality

- The budget formula's shape matched Berserk 4.5.0-8's (found by the
  constant screen; earlier screens had missed it): kept with an
  explanation and a credit (owner's decision), ORIGINALITY.md corrected.
- Constant screens: deliverable 8's new values (no match), the reserve
  variants B1 and B2 (no match; B1's nearest relative a Weiss horizon
  term).
- Name checks 23-30: no non-generic match; plain English words kept
  (`reserve`, `lowest`, `highest`, `conversion`, `Loop`, `Population`,
  `merge`, `bounds`, `report`).
- The idea 23 method references verified from primary sources
  (AlphaEvolve, FunSearch, MAP-Elites; KB research.md §9).

## Deliverable 8b and the idea 23 harness (in parallel)

- **8b**: every tunable search parameter in `src/tune/params.hpp`
  (name, default, range, SPSA step); release builds compile constants
  (bench unchanged), tuning builds expose spin options. Two formulas became
  integer parameters with identical arithmetic (the LMR divisor in tenths,
  the iteration growth in thirds).
- **Harness** (`tools/evolve/`): regions with a mutator guard, the
  evaluator funnel (gate, proxies, short match, SPRT hand-off), agents and
  prompts, a MAP-Elites population in SQLite, budgets and stop conditions;
  24 unit tests; a one-generation dry run with stub agents (each funnel
  outcome as scripted; it found a perft-parsing bug, fixed). The position
  set: 1,420 positions from Fork's self-play labeled at depth 18. Proxy
  budget (owner): **200,000 nodes**, depth median 11 (middle half 11-13),
  at most about 5 minutes per candidate. The loop itself is not started.

## Open

1. The end-of-Phase-3 removal round: SEE in quiescence, aspiration, mate
   distance pruning, the history malus, each tier 1 technique, plus the
   TT-refined eval (at STC and LTC) and keeping exact TT entries.
2. Supernova 2.4 and K2 0.99 as gauntlet anchors: their build entries are
   in `tools/get_anchor_engines.sh` (building them was outside this
   session's permissions; the owner runs it).
3. Idea 29 (how often unconfirmed root fail highs hold): measurement queued.
4. Deliverable 8c, the heuristic-discovery pilot, after the owner's go.
5. Phase 5: deliverable 8 at long time controls (the 40+0.4 check was
   stopped inconclusive), the iteration rule first.
6. Cloud SPRT support (`tools/cloud/`, `.github/workflows/sprt.yml`, KB
   tools.md section 11): built and tested locally (the merge against
   fastchess's figures, a shard run to the end and one interrupted); the
   GitHub workflow needs to be on main to be started, and the AWS script
   has not been run (it needs the owner's account). Estimated cost per
   5,000-game SPRT: $0 on GitHub's public runners, about $0.6 on one AWS
   c7a.16xlarge spot instance.
7. CI runs only on main and pull requests: milestone-c's commits have been
   checked locally (every code commit's full check, which includes TCEC's
   compilers), not by CI.
