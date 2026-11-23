# Fork — bug review (read-only), 2026-11-11

Companion to the engineering review, `docs/research/engineering-review-2026-11-11.md`.

**Verdict:** no correctness bug found in the engine; one decision-rule gap, one time-control hazard, one latent overflow gap, and several gate weaknesses in the tooling.

**Scope.** All of `src/` read line by line, except the non-shipped network architectures' internals, the stats-only reporting code and the bootstrap evaluator. Two sub-reviewers covered the test-statistics tooling and the network/data tooling. Not reviewed: `third_party/fathom`, the test sources, CI scripts.

**What was not done.** The engine was not built and the project's own test suite was not run. Nothing in the repo was changed.

**Snapshot.** Engine db0bb31 (branch `phase-4`), net r8brft1. Tests ran on a copy of the play binary, one thread, below-normal priority.

## 1. Tests run (python-chess as an independent oracle)

| Test | Size | Result |
|---|---|---|
| Legal bestmove, legal PV on every info line, PV head = bestmove | 7,000 positions, depth 9–12, including 1 MB hash with no clear between searches | 0 faults |
| Mate claims proved by brute force (mate in ≤ 3) | 397 of 564 claims (the rest were longer) | 0 false; every PV ended in mate |
| Tablebase play vs python-chess Syzygy (3-4-5), high halfmove clocks included | 4,000 positions | 0 thrown wins or draws, 0 false win/loss scores |
| Node-limited searches (each stops mid-iteration), run twice | 2,500 | deterministic, limit respected, final line consistent |
| Static eval symmetry (colour mirror, left-right mirror) | 4,000 positions | 0 mismatches |

The tablebase run flagged five positions scored 0 at halfmove clocks of 95–98. One was checked by hand (the fifty-move rule is reached one ply before the capture, so 0 is right); the others have the same shape. This is the documented off-by-one zone of DTZ values, not an engine fault.

## 2. Engine findings

| # | Where | What | Severity |
|---|---|---|---|
| E1 | `src/search/searcher.cpp:1121` (root bookkeeping at `:876–887`) | When a search stops mid-iteration, a move with an exact score is played only if it beats the *previous iteration's* score. If the old best move drops and another move is found better at the new depth, the old move is still played. | Decision quality: every node-limited search (data generation, fixed-node screens) and hard-limit stops |
| E2 | `src/search/time_budget.cpp:95`, `:178` | The soft-limit scale clamps depth at 19. Beyond that, a best move stable for 20+ iterations gets the 0.36 floor at any node share. | Time-control hazard at TCEC depths |
| E3 | `src/eval/nnue/accumulator.cpp:125–130`, `:176–194`; `src/eval/nnue/net_file.cpp:107–110` | The AVX2 squared-output sum is reduced in 32 bits; the loader only bounds each output weight at 128. Worst case is 8.5e9, four times int32. | Latent |
| E4 | `src/uci/session.cpp:174`; `src/search/hash_memory.cpp:94–99` | `Threads` is accepted and silently ignored by the search. The hash clear uses max(Threads, hardware threads), so Threads=1 does not bound it. | Operator surprise |
| E5 | `src/datagen/self_play.cpp:113` with `src/search/searcher.cpp:1030` | The TT age is advanced twice per move. Harmless with default switches; it doubles staleness if age-blend or keep-deeper is turned on. | Cosmetic |

### E1 in detail

- `iteration_best_` is set whenever a root move returns an exact score above alpha in the current pass. At a stop it is used only if `iteration_best_score_ > previous`, where `previous` is the last *finished* iteration's score.
- Case that loses: the previous best move m1 is searched first and comes back lower (inside the window, or after a fail-low re-search). A later move m2 then returns an exact score above m1's. m2 is better at this depth, but its score is at or below `previous`, so m1 is played.
- The rule was written after the "play an unresolved root fail-high" test lost 14.6 Elo. That is a different case: here the score is exact.
- Measured: in 2,500 node-limited searches the engine took the unfinished iteration's move in 249 (10%). How often it discarded a better one cannot be seen from outside the engine.
- Suggested rule: accept the current pass's best exact move once the previous best has been re-searched in that pass (reset `iteration_best_` at each pass).

### E2 in detail

Scale (per mille of the soft limit) from the engine's own function at depth 19 and beyond, where it no longer changes with depth:

| Node share | s=1 | s=3 | s=5 | s=8 | s=12 | s=16 | s≥20 |
|---|---|---|---|---|---|---|---|
| 200‰ | 6387 | 4756 | 3487 | 2141 | 1089 | 544 | 360 |
| 500‰ | 5171 | 3806 | 2765 | 1682 | 849 | 423 | 360 |
| 800‰ | 4150 | 3025 | 2181 | 1317 | 661 | 360 | 360 |
| 950‰ | 3213 | 2321 | 1663 | 997 | 498 | 360 | 360 |

(s = finished iterations in a row with the same best move; values above 4000 are capped at the hard limit.)

- In four 25-second searches of bench positions, three had s ≥ 20 by depth 22–27; the fourth changed its move at depth 19 and stood at s = 5.
- First-move budgets: 30'+3" gives soft 62.2 s, hard 249 s, floor 22.4 s; 120'+12" gives soft 249 s, hard 996 s, floor 89.6 s.
- So at TCEC depths most moves would get about 0.36 of the planned time. The docs flag the depth cap; the size of the effect is new.

### E3 in detail

- Shipped net (r8brft1), per output bucket: the largest reachable sum is 0.25–0.31 of the int32 range, so it is safe today. A sum of 2^31 corresponds to about 45,400 cp before the clamp.
- The loader's stated guarantee ("all paths give identical results") is not enforced for this sum.
- The SIMD equivalence test uses random nets, whose weights cancel, so it cannot catch it.
- Fix: bound 255² × Σ|w| per bucket in the loader, or widen the final reduction to 64 bits.

### Already on the project's lists, re-confirmed in code

- TT cutoffs ignore the halfmove clock (`searcher.cpp:241`).
- A repetition of a pre-root position counts as a draw (`searcher.cpp:217`).
- A one-sided tablebase bound can be stored as exact at PV nodes (`searcher.cpp:735–738`).

## 3. Improvements noticed while reading

- **Root moves are never reduced** (`searcher.cpp:864–868`): later root moves get full depth.
- **Data generation uses a hard node limit only.** A soft limit checked between iterations, with the hard limit as a cap, would give more uniform label depth for the same nodes.
- **`go mate N` caps depth at 2N − 1** (`src/uci/session.cpp:572–581`): a pruned search at that nominal depth can miss a mate in N.

## 4. Tooling findings (from the sub-reviewers; their checks were not re-run)

| # | Where | What | Confidence |
|---|---|---|---|
| T1 | `tools/nnue/endgame_check.py:36–53`, `tools/datagen/endgame_slice.py:52, 142, 158–160` | The endgame check's 900 positions come from the same population the Syzygy slice trains on: 509 of 900 were found verbatim in one slice file (KPK 184, KQK 170, KRK 155 of 300 each). The "351 → 8" result measures recall, not understanding. | Confirmed by run |
| T2 | `~/fork-data/8b/gates.sh:29–33, 45`; `pp_bound.py` | The quantization-loss limits are applied to the unclamped net; the shipped, clamped net's parity legs are not gated. The clamp script lives in a temp scratchpad, outside the repo. Today 1–2 weights are clamped, so shipped evals are unaffected. | By reading |
| T3 | `tools/cloud/sprt_merge.py:178–206`, `tools/github/sprt_run.sh:352–353`, `tools/cloud/run_shard.sh:79–81` | A shard is merged without requiring `done` and a full pair count; a failed final snapshot can leave a partial shard in a green run. | Acceptance confirmed by run; trigger by reading |
| T4 | `tools/gauntlet/report.py:320–341` | The transfer ratio's denominator sums estimates taken at the SPRT stop, which are biased upward: +7.6 nElo at a true 3, +5.1 at 6, +3.2 at 9. The ratio is therefore understated. | Bias confirmed by simulation; its size in the ratio is not |
| T5 | `tools/nnue/match_scale.py:35–51` | The scale is matched on mean \|eval\| over 4,000 positions from 98 games; 56% of the sum comes from positions above 400 cp. | Suspected |
| T6 | `tools/github/sprt_run.sh:286`, `:303–311` | The identity check covers base, test and stage only, and the run title is the same for two SPRTs of one commit pair, so two lanes could adopt each other's run. | Scope by reading; race suspected |
| T7 | `tools/github/sprt_run.sh:200–202`, `:249–253` | A `--first` resume can skip a stage boundary's decision, including the futility look. | By reading |
| T8 | `tools/jobs/jobctl.py:409–424`, `:371–383` | A record left "running" is treated as live when its PID is reused. | Confirmed by run (synthetic record) |
| T9 | `tools/train/src/main.rs:1049` | `fork-train dump --keep-all` silently filters when the flag is the last argument. | By reading |

**T4 corrects the engineering review**, which leaned on the 0.28 transfer figure. Part of that gap is this bias, so the real transfer is better than 0.28 by an unknown amount.

**Design R power (simulation, 40,000 trials per point):**

| Design | True nElo | Passes | H0 | Futility stop | Capped |
|---|---|---|---|---|---|
| Search STC | 0 | 1.6% | 38% | 36% | 24% |
| Search STC | 6 | 37% | 5% | 14.5% | 43% |
| Search STC | 9 | 72% | 1% | 7% | 20% |
| Search LTC (cap 6) | 6 | 26% | 5% | 14% | 56% |
| Search LTC (cap 6) | 9 | 58% | 1% | 6% | 35% |
| Network STC [0, 5] (cap 13) | 6 | 58% | 0.5% | none | 41% |

**SPSA (branch `tune/spsa`, `tools/github/spsa.py:194–201`):** theta is clamped to [lowest + c, highest − c], and a parameter pinned there is not flagged. In run spsa-r14-m2, RfpMargin sat at 55 for the last 10 of 13 updates and LmpQuietAllowance at 7.7 for the last 6, both with the gradient still pointing down. The project's final-retune design already widens these bounds; whether the "pinned" flag is in place was not checked.

**Clean:** the SPRT arithmetic (LLR, nElo, error bars, test/base sign; pair counts equal fastchess's own report on 4,256 stored shards), `bench/ab.py`, the trainer's targets and feature indexing, the converter and Python reference against the C++ inference, TD labels, checkpoint averaging, the endgame slice's labels, and the game-record format.

**Tooling improvements suggested by the sub-reviewers:**
- Commit `gates.sh` and `pp_bound.py`; gate the clamped net's loss or fail above a small clamp count.
- Build the endgame check from positions the slice cannot generate, and add four- and five-piece endings.
- Require `status == done` and a full pair count for every merged shard.
- Record the tooling commit, the fastchess version and the adjudication settings in the shard meta and add them to the merge keys.
- `ShardReader::read_chunks` ignores its skip count, so every `--resume` restarts the data stream.

## 5. Held back

Quantifying E1 needs an instrumented engine build: roughly 2–3 minutes of compile at about 0.5 GB. At review time the machine was at 100% CPU with 3.5 GB free and a 1 GB watchdog floor, so it was not run.

## 6. Where the evidence is

Scripts and outputs: a session temp folder of the reviewing session (path withheld: it contains the machine's user name) — `soundness.py`, `tbcheck.py`, `stopcheck.py`, `evalsym.py`, `stability.py`, `netbound.py`, `tm_table.cpp`, the `sound-*.json` and `tb-1.json` results, and the sub-reviewers' `tools-a` and `tools-b` folders. It may be cleaned up.

## Copied into the repo (2026-11-11)

Copied by the coordinating session after the personal-data scan: the review is unchanged except its first line (it
now points at the engineering review's repo copy) and section 6 (a scratchpad path holding the machine's user name
is withheld). The owner's decisions on it are in DESIGN.md's decisions log, 2026-11-11.
