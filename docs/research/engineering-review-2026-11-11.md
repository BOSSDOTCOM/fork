# Fork — engineering review (read-only), 2026-11-11

## Context

You asked for a complete read-only analysis of Fork: weaknesses, improvements and new ideas, respecting the project's docs and rules, with production running.

- **Snapshot reviewed:** branch `phase-4` at `d1fe24b`, default net `r8brft1` (768 mirrored + 608 pawn links → 512 SCReLU → 8 phase outputs), bench 10,166,167.
- **What I read myself:** all of `src/search`, `src/tune`, the NNUE inference (`src/eval/nnue`), move generation and `Position`, `src/datagen`, the UCI session, CLAUDE.md, HANDOFF.md, the three rules files.
- **What was digested for me by read-only sub-readers:** DESIGN.md (all 4,513 lines), ideas.md, both SPRT logs, MORNING.md, nets.md, the engine survey, the think-tank synthesis, the phase-4 designs, the transfer report, audit-1, the KB and the tooling.
- **What I did not do:** no build, bench, test or match was run, and no file in the repo was changed. Every Elo figure marked "my estimate" is a judgement, not a measurement.

## Bottom line

Fork is a carefully built, honest 3510-Elo single-thread engine whose process is better than most engines ten times its age. Its three biggest problems are not in the search code:

1. **It cannot use the machine it will play on.** Search is single-threaded; TCEC runs 512 threads.
2. **It is being optimised for a game it will never play** (8+0.08, one thread, 16 MB hash), and today's gauntlet shows the cost: the last five adoptions summed to +69 in self-play and delivered **+19.4** against other engines (transfer 0.28).
3. **The network is small and under-trained**, and the rule that keeps it small (the 0.90 speed gate) was derived at the wrong time control and on the wrong class of CPU.

Search heuristics come fourth. The search is thin next to its peers, but that is the cheapest gap to close and the one the project is already working on.

## What is strong (keep doing it)

- Correctness discipline: legal move generation, no-allocation search, fuzzing, sanitizers, mutation testing, parity checks on every net. I found no search bug in my read.
- Every technique behind a switch and every constant in one table (`src/tune/params.hpp`).
- The measurement tooling (decision ledger, eval-site sampling, node-share fit) is rare and valuable.
- The speed-adjusted fixed-node screen (`FN + 118·log2 r`) predicted 9 of 9 network verdicts.
- The data loop itself: split-search datagen (+65), TD labels, the Syzygy slice with an endgame acceptance test.

## Weaknesses, ranked by what they cost at TCEC

### W1. No parallel search

- `Threads` only parallelises the hash clear (`src/uci/session.cpp:174`, `:223`); one `Searcher` runs on one thread (`:538`).
- The TT is prepared for sharing (self-verifying entries) but its accesses are not yet atomic.
- At 512 threads this is worth hundreds of Elo; nothing else on any list is within a factor of five of it.
- **The sequencing is the real problem.** The factorial removal round (step 18) and the final retune (step 19) are scheduled before SMP exists. Both will be decided at one thread, then SMP changes the search's shape (effective depth, TT pressure, history sharing) and both must be redone.

### W2. The optimisation target is not the competition target

- An STC game searches about 0.7 M nodes per move. A TCEC move at 30'+3" on 512 threads searches on the order of 10^10: four orders of magnitude more.
- Consequences I can point to in the code and logs:
  - Depth-scaling parameters (LMR divisor, null-move depth, singular depth and margin, IIR depth 8) are fitted at depth 12–19. The time-management fit clamps depth at 19 (`src/search/time_budget.cpp:95`).
  - The TT is never under pressure in testing: 16 MB holds 1.3 M entries against 0.7 M nodes per move. Every TT-policy test (age blend, keep-deeper, keep-exact) came back "inconclusive" for that reason, and they are parked until Phase 6.
  - SPRT games use resign adjudication; TCEC has no win adjudication, so conversion is never exercised in testing.
- **Transfer is falling:** 0.65 overall, 0.48 running, 0.28 (0.02–0.56) for the window just measured. The self-play number is steadily less informative.

### W3. Network capacity, training length, and the gate that guards them

- The project's own accounting: networks returned 12.5 Elo per test stage, search 0.8. Yet the net is one 512-wide layer with no king-relative inputs.
- **Under-trained.** Per the docs a run is 360 superbatches of about 5 M samples, roughly 1.8 B samples — about one and a half passes of the data. Strong nets of this shape are normally trained on tens of billions of samples. "Warm beats scratch" is what an under-trained scratch run looks like. The limit is the Kaggle quota (30 GPU-hours a week), not the method. *(Verify the per-superbatch size: the trainer's default is 6,104 batches, the docs say the recipe uses about 305.)*
- **The speed gate is measured in the wrong place, twice:**
  - It prices speed at 1.72 Elo per 1% nps, fitted at 8+0.08. The value of a doubling shrinks as searches get deeper in every engine I know; Fork's one LTC data point (XGR) does not show it, so it needs measuring, not assuming. Step 9 (the throttled speed-to-Elo measurement) was never run.
  - The development CPU (7600X3D) has 96 MB of L3 for 6 cores. TCEC's EPYC 9754 has about 2 MB of L3 per core, shared by two threads *(public specs; verify)*. The net is 1.4 MB and each searcher's reply and follow tables are 2.4 MB (`src/search/quiet_history.hpp:133`). Speed results from the dev box, including "refresh cache −5.3%", do not predict the target.
- King buckets and the refresh cache were each rejected alone: king regions at 93.5 M positions (over-fit and slow), the cache on a mirror-only net where refreshes are rare. They were never tried together, and data is now 15 times larger.

### W4. Statistical power

- Design R has 21% power at a true +3 Elo (the think tank's figure). A 3500-Elo engine's typical good patch is +1 to +3. The pipeline rejects most real improvements and over-states the ones it accepts.
- Fixed-node network screens (±9–10 Elo) are run against seed noise of 4–15 Elo. td80 at −1 against td90 at +17 is noise, and td90 was kept on +4.13 ± 9.47.
- Verdicts are not carried across regime changes. Rising RFP, ProbCut, the LMR history term and qsearch delta pruning were all rejected before the R14 retune moved the margins by a third (+38 Elo). Those rejections describe the old search.
- Base drift: cut-node was tested on S512ppr3 and adopted onto r8brft1; T56 was tested without cut-node.

### W5. The search is thin where peers get most of their Elo

All verified in `src/search/searcher.cpp`:

- **LMR** (`:603–633`) is a whole-ply table plus two one-ply terms. No history term, no PV or TT-PV term, captures are never reduced. The failed history test divided the *summed* ordering score by 24,000, so it rarely fired; that test does not refute the idea.
- **No correction history is on.** The pawn drift table (branch `tier2/drift`) is soundly built and ended undecided at LTC, on S512r2 and the pre-R14 margins.
- **Null move** (`:358–375`) has no verification search. It cannot matter at STC and can at depth 40.
- **Singular extension** is +1 only; double extension is built on `tier2/b4` and unported.
- **The TT-PV flag is stored and never read** (`src/search/trans_table.hpp:62`, no reader in `searcher.cpp`).
- Histories update only on a beta cutoff; continuation history stops at 2 plies; evasions use the butterfly table alone (`src/search/move_selector.cpp:114`).
- Root moves are ordered by move-to-front only (`:890–894`).

### W6. Defence and a compressed eval

- From the project's own loss analysis: 0 of 112 from unfavourable exits against Stockfish 19; 88.6% of lost defence windows are queens-on middlegames; only 2.4% of losses are horizon errors.
- That is the signature of an eval with no king-relative features: a mirrored 768-input net cannot represent "pieces near my king". This is independent evidence for king buckets (W3).

### W7. TCEC-readiness hazards (none costs Elo until the day it costs a game)

- **7-man Syzygy on disk, probed from depth 1 on every thread** (`searcher.cpp:256`, `src/search/endgame_tables.cpp:101`), with no probe-depth or probe-limit option.
- **TT cutoffs ignore the halfmove clock** (`searcher.cpp:241`); with no win adjudication, fifty-move blindness in conversions is live.
- Reported scores are in "bootstrap centipawns", not calibrated to win probability. TCEC's draw rule reads |eval| ≤ 0.25.
- The TCEC build (`update.sh`) is x86-64-v3 without PGO; the SCReLU output layer has an AVX2 path only (`src/eval/nnue/accumulator.cpp:176–199`; the AVX-512 output path exists only for B0).
- No CPU-feature check at start (SIGILL without BMI2), Fathom's `exit()` paths, no Chess960 castling (`src/core/movegen.cpp:122`) if FRC events matter.

## Recommended order

| # | Action | Why now | My estimate | How it is tested under Fork's rules |
|---|---|---|---|---|
| 1 | **Minimal Lazy SMP**, ahead of steps 18–19 | Everything tuned before it is tuned for the wrong regime | Hundreds at TCEC | Bench parity at Threads=1; TSan suites; scaling curve (nps and time-to-depth vs threads); 2-vs-1 and 8-vs-4 thread matches |
| 2 | **Measure the speed price where it matters**: same binary at 1× and 0.5× time, at STC, LTC and 120+1.2; nps under full load on a many-core EPYC cloud box | Sets the gate for every network decision | Enabler | `bench/ab.py` method; a few stages per time control |
| 3 | **Train longer** (rent a GPU): one from-scratch run of 20–40 B samples on the current architecture, against the standard recipe | Cheapest Elo on the board | +10 to +25 at fixed nodes | Existing gates: parity, endgame check, FN screen, STC [0, 5] |
| 4 | **Bake-off round 3 under the re-derived gate**: king buckets *with* the refresh cache; a wider layer (768 or 1024) | W3 and W6 point at the same change | +20 to +50 if the gate moves | Speed-adjusted FN screen with the price from #2, then LTC |
| 5 | **LMR as round-once fractional (R20) with per-table history terms**, then TT-PV and capture reductions | Largest search family still missing | +10 to +25 together | Design R, STC then LTC |
| 6 | **Correction tables on the tuned search** (already queued as R34/E4), then D8/D9 | Consensus items rejected in the old regime | +5 to +15 | Straight to LTC, as the project's list says |
| 7 | **Buy test power**: spot compute for SPRT; tighter bounds once games are cheap | W4 | Enabler | — |
| 8 | **Readiness fixes**: Syzygy probe limits, halfmove guard on TT cutoffs, null-move verification at high depth, score calibration, CPU check | Cheap insurance | Small | LTC non-regression [−3, 0]; zugzwang and fifty-move test positions |

Do now, with no code: treat the gauntlet as the truth and self-play as the screen; run the anchor check after every two or three adoptions.

## New ideas (not in ideas.md or the survey, as far as the digests show)

1. **Pressure-matched hash testing.** Pick Hash so nodes-per-move divided by TT entries matches TCEC's (about 1). At 40+0.4 that is Hash 8–16 MB, not 64. TT-policy tests then become decidable today instead of waiting for Phase 6.
2. **Factorial admission screen.** The fractional-factorial design drawn up for *removing* switches (R30) works forward too: screen the survey's eight search proposals in one experiment at about 4 nElo standard error each, instead of eight separate capped SPRTs.
3. **A regime-change retest rule.** After any retune or net change worth more than about 20 Elo, every consensus idea (four or more engines report a gain) on the rejected list gets one new try. The "two tries per idea" rule currently discards ideas for reasons unrelated to the idea.
4. **A target-class speed lane.** Add one many-core EPYC measurement to the speed doctrine, with every hardware thread loaded. Size per-thread tables against 2 MB of L3 per core: the reply/follow tables are the first candidates to shrink or share.
5. **King-relative offset inputs** as a cheaper alternative to full king buckets: a small extra input family indexed by piece and its offset from the enemy king, refreshed only on king moves. It targets the defence finding directly at a fraction of the input count.
6. **Node-count draw jitter** (±1 around 0, `src/search/score_bounds.hpp:15`): trivial, and it reduces repetition blindness once many threads search the same lines.
7. **No-adjudication conversion runs** as a standing nightly: play won positions out to mate under TCEC rules, so the path TCEC actually scores is tested.

## Where I agree with the project's rejections

- Negative extension in its ungated form, idea 23's evolutionary loop on a proxy, distillation from a weaker teacher, class-weighted sampling, S512cl at 0.195× nps.
- Killers and countermoves were never built; with reply/follow tables that is the right call.
- The clean-room rules cost speed of development, not strength. Nothing above needs another engine's code.

## Verification

- This review changed nothing; the only file written is this one.
- Claims with a `file:line` reference were read directly. Claims about history, results and plans come from the docs via sub-readers; two are flagged *verify* above (training samples per run, EPYC cache sizes).
- Each recommendation names its test in the table. None should ship on my estimate: the project's own rule ("untested changes never ship") applies to every line here.


## Verification by the coordinating session (2026-11-11)

Done after the review, against the snapshot it names (`d1fe24b`) and the docs; the review text above is unchanged.

- **The TT-PV flag is stored and never read: confirmed.** `src/search/trans_table.hpp:57` keeps it in bit 2 of
  `flags`, `was_pv()` (`:62`) reads it, and `trans_table.cpp:86` copies it into `TtHit`; the only reader of
  `TtHit::was_pv` is `tests/test_tt.cpp:62`. Nothing in `src/search` uses it.
- **TT cutoffs ignore the halfmove clock: confirmed.** `searcher.cpp:241-245` cuts on depth and bound only.
- **Syzygy probing from depth 1: confirmed, with a qualification.** `TableProbeMinDepth` is 1
  (`src/tune/params.hpp:47`, range 1-4) and the probe sits at `searcher.cpp:256`; there is no UCI probe-depth or
  probe-limit option. But `probe_table_wdl` (`endgame_tables.cpp:101-103`) probes only within the tables' piece
  count, with no castling rights and **a halfmove clock of zero**, so a probe happens only right after a capture or
  pawn move, not at every node in a table position.
- **Samples per training run: confirmed.** The trainer's default is 6,104 batches per superbatch
  (`tools/train/src/main.rs:1210`); Fork's recipe passes 305 (`tools/train/kaggle/bakeoff.py:47` and its
  successors) at batch 16,384, so 4.997 M samples per superbatch and **1.80 B samples** per 360-superbatch run.
- **EPYC 9754 L3 per core: confirmed from a secondary source.** 128 cores / 256 threads; Zen 4c has 16 MB of L3
  per 8-core CCX, so **2 MB per core**, shared by its two threads (256 MB total if every CCX is enabled, derived).
  Source: Wikipedia's Epyc and Zen 4 pages (2026-11-11); AMD's product page timed out twice, so the figure is not
  from the primary source.

No claim checked was wrong.
