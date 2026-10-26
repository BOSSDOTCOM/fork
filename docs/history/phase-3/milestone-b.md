# Phase 3 Milestone B report (2026-10-26)

Milestone B (DESIGN.md §5.2): deliverables 5 (move ordering) and 6 (tier 1
pruning and reductions) done, with Fork's own constants after the
originality check, and the queued experiments run.

## What was built

| Commit | Content |
|---|---|
| 4fac691 | 5: staged `MoveSelector` (TT move, good captures by MVV-LVA with lazy SEE, quiets by butterfly history, deferred losing captures and under-promotions; evasions in check), `QuietHistory` with the standard gravity update and a malus; `tools/solve_suite.py` (WAC) |
| 40fdf8f | 6: reverse futility pruning, null move pruning, late move reductions (integer log table), late move pruning, futility pruning, SEE pruning, each switched; bench depth 6 -> 13 |
| 69e830a | Fork's own constants (owner's decisions on the originality check): LMP count, null-move depth, history scale and bonus, aspiration window replaced; four renames; the "Search constants" table and the process rule; the matetrack mate suite |
| f919c01 | Renames of exact compound name matches (`SearchQuota`, `AspirationHalfWidth`, `deliberate`); domain vocabulary recorded (DESIGN.md §8) |
| 061053d | Queued experiments: results only (no code change) |
| 9572da9, 905db3d, dcfe2f0 | Owner's plans: ideas.md idea 23 (heuristic-discovery loop), its pilot scheduled as deliverable 8c, the improvement pass as a roadmap entry |

Bench now: 16,540,472 nodes, signature 779d36c67f079e12 (depth 13). Every
code commit passed `scripts/check.sh full` (Windows presets and UCI smoke
loop, Linux, Ubuntu 22.04 with gcc 11.4, g++-12, clang 16, clang 19); CI
passed on 69e830a and f919c01 (pushed). One pre-commit failure was caught
by the check itself: `tests/bench.ref` written from the Windows binary had
CRLF line endings and failed the TCEC toolchain's comparison; rewritten
with LF.

## SPRTs (STC 8+0.08, bounds [0, 5], details in sprt-log.md)

| Test | Build | Result |
|---|---|---|
| Move ordering (4fac691) vs its parent | release | H1, 472 games, 70.3% |
| Butterfly history on vs off | 69e830a, tuning | H1, +419 Elo, 322 games |
| Tier 1 pruning, all six on vs all off | 69e830a, tuning | H1, +439 Elo, 318 games |
| SEE pruning on vs off (its WAC count was doubtful) | 69e830a, tuning | H1, +21.2 ± 10.1 Elo, 3,042 games |

The owner shortened the queue (2026-10-25): tier 1 as one grouped test,
individual techniques and the history malus to the end-of-Phase-3 removal
round; check extensions do not exist yet (tier 2). A first UseHistory run
on the superseded constants was stopped at about 79 games and is marked
superseded in the log. Adjudication (52ac1b1) was on for every test.

## Tactical and mate guards (`tools/solve_suite.py`, 200,000 nodes per position)

| Build | WAC (300) | Mate in 1-5 (297, matetrack) |
|---|---|---|
| 40fdf8f (first values), all six techniques off | 209 | — |
| 40fdf8f (first values) | 250 | — |
| Fork's own pruning values, first aspiration window, all six off | — | 126 |
| Fork's own pruning values, first aspiration window | 253 | 136 |
| 69e830a (own pruning values and the measured aspiration window) | 247 | 132 |
| 69e830a, aspiration off | 245 | 128 |

The counts move by 3-6 under small trajectory changes alone (the same build
solves 245 at 150,000 nodes and 248 at 250,000), so they catch collapses,
not small differences. With the first values, each technique off in turn:
RFP 249, NMP 246, LMR 236, LMP 245, futility 245, SEE pruning 254 (hence its
individual SPRT, which it passed). WAC was verified by the kb-researcher
(download-only, licence UNVERIFIED); matetrack is a diagnostic only, never a
tuning target or training data (owner, KB data-policy.md decision 7).

## Originality

- **Originality check of deliverables 5 and 6** (web pages only): no copied
  code or data; the first LMP count and null-move reduction were Stockfish's
  formulas, the history scale and bonus Ethereal's, and four names matched
  Ethereal or Stockfish in another case style. All replaced by the owner's
  decision, each value with a recorded justification (DESIGN.md §5.2,
  "Search constants"): LMP measured from Fork's own cutoff-index
  histogram, the null-move depth from Fork's knight value, the history
  scale from int16 headroom.
- **Constant screen** (the new owner rule): every search constant against
  Stockfish (current and historical), Ethereal, Berserk and Weiss. It found
  the first aspiration scheme identical to Berserk 1.0.0's, replaced by a
  window measured on the bench (12 cp from depth 5) with Fork's own
  widening rule; the new values match nothing; near matches are recorded
  in ORIGINALITY.md.
- **Name checks** now cover the four engines, exact and case- and
  separator-insensitive (batches 11-14). The three exact compound matches
  were renamed; textbook vocabulary is kept deliberately (DESIGN.md §8).

## Elo baseline gauntlet (f919c01, TCEC build)

1,000 games at 10+0.1, 200 against each anchor, from the same 200 random
8-ply openings as Milestone A (both colours), concurrency 10, fastchess;
Ordo with the anchors fixed at their CCRL Blitz 2'+1" ratings (list of
2026-10-24). The Milestone B set (owner, 2026-10-25): Stash 15.3 and 19.0
kept, three unrelated code bases added, BBC dropped.

| Opponent | CCRL Blitz | Fork's score | At Milestone A |
|---|---|---|---|
| Belette 2.0.0 | 2115 | 124.0 / 200 (62%) | — |
| Stash 15.3 | 2173 | 133.5 / 200 (67%) | 44.5 / 200 (22%) |
| Chal 1.3.0 | 2285 | 136.5 / 200 (68%) | — |
| Stash 19.0 | 2473 | 81.0 / 200 (40%) | 18.5 / 200 (9%) |
| WyldChess 1.51 | 2603 | 38.5 / 200 (19%) | — |

**Fork: 2343 ± 23** (Ordo, 1,000 simulations), against **1773 ± 32** at
Milestone A: about +570 on the same scale. The same caveats as at
Milestone A: a rough placement, not a CCRL rating (10+0.1 on this
machine, not CCRL's 2'+1"), the anchors keep their default hash, and the
scores against Belette, Stash 15.3 and Chal do not follow their CCRL order
(62%, 67%, 68% against 2115, 2173, 2285), so the anchors' ratings fit this
machine and time control only loosely. All 1,000 games ended by the rules
(mates 875, draws 125: repetition 76, insufficient material 26, fifty
moves 22, stalemate 1); no time losses, crashes, illegal moves or
disconnects. Chal 1.3.0 ignores `go movetime` (it searches on), so it is
used in clocked games only.

## Performance

Search nps (WSL, A/B harness, depth-13 bench, 3% noise floor; details in
perf-log.md): deliverable 5 within noise of the Milestone A build (two
runs disturbed by load, best-run estimates -1.7% and +3.4%); deliverable 6
-41.7%, a deliberate trade (a pruned move costs its selection, SEE and
gives_check but is not a node); Fork's own constants (69e830a) +4.8%
against 40fdf8f (B faster: the milder late move pruning and null move
leave fewer pruned moves per node). Profile: `MoveSelector::take_next`
25.9%, eval 12.9%, `see_value` 10.8%, `negamax` 8.6%.

## Queued experiments (ideas.md idea 9)

- Legal generation stays: pseudo-legal generation with lazy `is_legal`
  measured -2.3% (within noise), with a tie-break so both variants searched
  the same tree.
- `gives_check` 0.646 calls per make: the lazy check-squares variant is not
  warranted.
- Layout unchanged: State 48 bytes +0.4%, State aligned to 64 bytes -2.5%,
  int32 history -1.5%, 16-byte TT entries -0.3% (all within noise).

## Reviews

- Deliverable 5: no wrong-result bug. Clear Hash did not clear the history
  (a repeated search did not reproduce; fixed, with a UCI test); two
  header comments were false (the search invariant, the tie order).
- Deliverable 6: no correctness defect. The LMR header overstated
  exactness (fixed); the pruning can delay a mate in KQR v K (ideas.md
  idea 22). The reviewer's mate-score, state-leak and probe tests were
  kept in the suite.
- The first stalemate test could not fail; a zero-window probe seam
  (`probe_zero_window`) now tests the node directly, fault-injected.

## Open

1. The time loss under load (deliverable 8).
2. Removal round at the end of Phase 3: SEE in quiescence, aspiration,
   mate distance pruning, the history malus, each tier 1 technique.
3. Idea 22 (mate-aware LMP and LMR).
4. Chal 1.3.0 ignores `go movetime` (it searches on); only clocked games
   use it.
