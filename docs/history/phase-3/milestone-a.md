# Phase 3 Milestone A report (2026-10-25)

Milestone A (DESIGN.md §5.2): deliverables 1-4 (bootstrap evaluation, core
search, TT, quiescence search and SEE) done; Fork plays real chess.

## What was built

| Commit | Deliverable |
|---|---|
| 6ad9d8c | 1: bootstrap evaluation, chosen at build time (`FORK_EVALUATOR`) |
| ad4b848 | 2: fail-soft PVS, iterative deepening, aspiration windows, mate distance pruning, draws, MaxPly 250, search bench (46 positions, depth 6), first time budget; placeholder deleted |
| 0d32d51 | 3: transposition table |
| 8d6b283 | 4: quiescence search and SEE |
| 2beb9e3 | tuning builds: every search switch as a UCI option (`FORK_TUNE`) |
| bea68ed | Milestone A originality fixes: TT store redesigned, self-verifying TT entries, root move-to-front, `PvNode` -> `OnPv` |
| f736dc7 | `go movetime` keeps at least half its time |

Bench now: 7,533,640 nodes, signature 2711c23a13969520. Perft workload
unchanged (26,401,709, f298a22041a6270a). Every commit passed
`scripts/check.sh full` (Windows presets and UCI smoke loop, Linux,
Ubuntu 22.04 with gcc 11.4, g++-12, clang 16, clang 19).

## SPRTs (STC 8+0.08, details in sprt-log.md)

| Test | Result |
|---|---|
| Search vs Phase 2 placeholder | H1, 293-0-1 |
| Quiescence on vs off | H1, about +308 Elo |
| TT on vs off | H1, about +160 Elo |
| SEE pruning in quiescence | inconclusive, stopped by the owner: +9.5 ± 7.3 at 5,800 games (95% interval above zero); kept, removal round |
| PVS on vs off | H1, +110 ± 24 |
| Aspiration windows | inconclusive, stopped by the owner: +3.9 ± 7.6 at 3,200 games; kept, removal round |
| Mate distance pruning | not run (owner); kept, removal round |

Concurrency 10 from the PVS test on: 1,478 games/hour, 0 time losses in 943
games.

## Games (cutechess-cli 1.5.1, fastchess 1.8.2, bea68ed; 200 random 8-ply openings)

| Match | Games | Not ending by the rules |
|---|---|---|
| cutechess 10+0.1 / fastchess 10+0.1 | 200 / 200 | 0 / 0 |
| cutechess / fastchess depth 3 | 50 / 50 | 0 / 0 |
| cutechess / fastchess 50 ms per move (re-run with f736dc7) | 50 / 50 | 0 / 0 |
| cutechess 2+0.02, every CPU busy | 200 | **1 time loss** |

The time loss: at 2+0.02 under full load, White's clock had drained to about
the 100 ms Move Overhead; Fork then plans about 1 ms per move, but the
measured time per move (process wake-up and I/O under load) was 16-20 ms,
about the increment, so the clock never recovered, and one longer stall lost
the game. A time-management issue (keeping a larger reserve when the clock
is low), for deliverable 8, which has this test. No crashes, illegal moves
or disconnects in any game.

## Performance gate (perf-log.md)

Search nps (WSL, A/B harness, 3% noise floor): deliverable 2 about 12.0 M;
3 -6.4% and 4 -20.3%, both deliberate trades (the TT cuts bench time to the
same depth about 3 times; the quiescence search runs SEE on every
capture); the originality fixes -1.3% (noise). No hotspot out of place.

## Reviews

- Deliverable 2: three bugs fixed with tests (INT64_MIN clocks overflowed;
  Hash work at go not counted against movetime; a stop mid-iteration could
  leave the last info PV naming another move).
- Deliverable 3: a throwing Hash resize left the TT on freed memory (next go
  crashed; test `uci_hash_oom`); the age wrapped at 32 searches. Fixed.
- Deliverable 4: no bugs; one measured risk logged (PV quiescence nodes use
  full windows).
- Originality check: nothing transcribed; four medium findings fixed or
  cited (ORIGINALITY.md, "Phase 3 Milestone A originality check").

## Open

1. **Elo baseline gauntlet: not run.** The anchors (KB competition.md §5:
   Shallow Blue 2.0.0, Stash 12 / 15.3 / 19, BBC 1.1, Weiss 1.0) must be
   built from their source; the session's permission classifier refused to
   build external code. `tools/get_anchor_engines.sh` and
   `tools/elo_gauntlet.sh` are ready.
2. The time loss under load (deliverable 8).
3. Spec deviations: TT entries have 24 check bits and an 8-bit age (instead
   of 32 and 5); the parameter table `src/tune/params.*` is not created yet
   (only the on/off switches exist).
4. Queued: SPRT adjudication (after this chain), ideas 18-21.
