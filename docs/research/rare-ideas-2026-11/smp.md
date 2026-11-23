# Lazy SMP practice found by the survey

Part of the rare-ideas survey of 2026-11-15 (README.md). Everything the four groups found about Lazy SMP, gathered
for roadmap row 17a and Phase 6, and cross-referenced to the knowledge-base entry **docs/kb/lazy-smp.md** (branch
kb, written the same day; read with `git show kb:docs/kb/lazy-smp.md`). Section numbers "KB §x" refer to that
entry; "T53" and "T54" are its sister entries in search-techniques.md §3.31 and §3.32. Every idea is **REFERENCE
ONLY**; every figure is the engine's own report. Fork searches on one thread today.

## What is new here, against the KB entry

The KB entry already holds the mechanism, the history, the measurements up to Stockfish's 2026 shared-history
commits, the first-implementation results of Tarnished, Hobbes, Raphael and RubiChess (KB §2.4), the best
practices (KB §3) and a suggested minimal v1 (KB §6.3). The survey adds:

1. **Diversity measured in three engines** (rare.md RI-35): Stockfish's per-thread offsets, Reckless's reduction
   noise and bias, Potential's helper reduction bias. The KB names the options (KB §3.2, T54) but has no SPRT
   result for reduction-side diversity.
2. **Soft-stop voting** (RI-36, Reckless) and **SMP-only TT policy** (RI-37, Reckless; F3's thread-scaling peers).
3. **Table sizes by thread count** (RI-38, Potential) and **continuation history shared across threads**
   (Potential), next to Stockfish's (KB §3.3).
4. **More hygiene results** for items the KB lists as practice: aligned per-thread node counters (PZChessBot,
   JustBot), main-thread-only stopping (JustBot), per-thread state kept between searches (Tcheran), torn-cluster
   checksums (Viridithas, neutral).
5. **Counter-evidence on SPSA under SMP** (three engines whose SMP tunes did not cost single-thread strength).
6. **Depth-relaxed TT cutoffs** passing at 8 threads (RI-27, Ethereal), and F3-style eager TT writes whose gains grow
   with threads (evidence.md, F3).

## 1. Hygiene: start, stop, store, count

| Practice | Evidence (engine's own) | KB entry | Fork's plan |
|---|---|---|---|
| Start and stop all threads at a barrier; keep threads alive between searches | Tarnished #136 (with the next row) +14.48 ± 5.19 at 2 threads, +20.08 ± 6.03 at 4 threads, 8+0.08, [0, 3]; JustBot #137 persistent workers, 8-thread non-regression; Viridithas #310 a persistent pool, -9.01 at 2 threads STC but +10.29 at 2 threads LTC (inconsistent) (G2, G3) | §3.1 lifecycle; §6.3 items 1 and 10 | in the suggested v1 |
| A stopped search stores nothing (TT entries, scores) in any thread; an interrupted search's score is not reported or voted on | Tarnished #136 (above); RubiChess #528 (wrong upper-bound scores after an interrupted multi-thread search) and #516 (early reset of the best-move score to avoid wrong voting), no figures (G2; rare.md RI-34) | §3.4 "Never store an aborted search's result"; §6.3 item 9 | in the suggested v1; a unit test each (RI-34) |
| Allocate per-thread search data once, reuse across `go` | Tcheran c822258: +8.95 ± 5.20 at 2 against 2 threads; 2-against-1-thread odds from +54.97 to +75.96 (1,024 games each); 1 thread neutral (G3). Halogen #792 and #859 huge pages for thread-local state (G3) | §3.1; §6.3 item 1 | in the suggested v1 |
| Per-thread node counters on their own cache lines, summed on demand | PZChessBot #310 +22.61 ± 9.74 (0.5+0.01, 8 threads, 1,816 games), #309 relaxed loads +9.49 ± 5.57 (8 threads); JustBot #143 +38.88 ± 10.71 (4 threads, 4+0.04) and +21.66 ± 8.35 (4 threads, 20+0.2), bundled with unchecked lookups; Velvet 3.1.3 bulk global node updates (no figure); Titan #130 batched updater, neutral at 1 thread (G3) | §3.5; §6.3 item 7 | in the suggested v1 |
| Only the main thread reads the clock and stops the helpers | JustBot #109 +19.10 ± 5.95 (8+0.08, 4 threads, [0, 3], 3,296 games) (G3); Icarus "SMP TM" +22.66 ± 8.36 at 2 threads (probably a fix) (G4) | §3.1, §3.5 (Reckless #707, #797; Hobbes #396) | in the suggested v1 |
| A checksum against torn TT clusters | Viridithas #437, neutral at 8 threads, called a "vanity change" (G2) | §3.4 (lockless XOR check; Fork's digest) | Fork's existing digest check plus the torn-write stress test |
| All threads start at depth 1 | Viridithas #372, non-regression at 4 and 8 threads (G2) | §3.2 ("none" scheme) | consistent with v1 (no depth offsets) |

## 2. Diversity between threads (T54)

| Form | Evidence | KB entry | Fork |
|---|---|---|---|
| Later threads reduce slightly less | Stockfish 39c077f1: SMP STC +0.70, SMP LTC +2.04 ([0, 2] then [0.5, 2.5]) (G1) | §3.2 (depth schemes only); T54 | never tried |
| First aspiration window widened with the thread number | Stockfish 8ecfc3c8: +1.31 / +1.31 (G1); Clover #401 "more aspiration windows for some threads" (title) (G2) | not covered | never tried |
| Odd-numbered threads reduce the null move a little less | Stockfish 61c68717: +0.79 / +0.91 (2026-10-28) (G1) | not covered | never tried |
| Small random reduction noise in helpers | Reckless: 1 thread non-regression (-0.10 ± 1.03, [-2.75, 0.25]); 8 threads at 5+0.05 +3.19 ± 2.37, [0, 4] (G1) | not covered | never tried |
| A small deterministic per-helper reduction bias | Reckless +1.96 ± 1.58 (TC not stated: UNVERIFIED); a much larger bias failed (G1). Potential (credited to 87flowers): 1 thread -4.22 ± 5.57 (stopped), 8 threads at 5+0.05 +9.13 ± 6.36, [0, 7.5], 4,188 games (hand-crafted era) (G4) | not covered | never tried |
| Draw-score randomisation (also a diversity source) | Ethereal LTC +3.63 ± 2.88 (STC not passed); others mostly non-regression (G1, G3; common.md CG-9) | not covered | never tried |
| Evaluator-diverse helpers | (Fork's own idea 84, novel-ideas 6; no peer evidence found) | — | idea 84 |

**Reading:** every reduction-side form gained only with threads and was neutral or slightly negative at one
thread, which is what a diversity mechanism should do. The KB's v1 (KB §6.3 item 3: no depth offsets or skip rules;
diversity from timing and per-thread histories only) is the right baseline; the first diversity SPRT after v1
should be one reduction-side form (rare.md RI-35: helpers identical against helpers with a small per-thread
reduction offset, at 4 to 8 threads, plus a 1-thread non-regression).

## 3. Choosing the move and stopping (T53)

| Form | Evidence | KB entry |
|---|---|---|
| Thread voting | Stormphrax #273 (Stockfish's scheme) +4.92 ± 3.83 at 7 threads on [-3, 1], merged "before TCEC Swiss"; Viridithas #415 "improve thread selection" +2.86 ± 2.02 at 8 threads; Tarnished removed voting (non-regression at 2 threads) (G2); Halogen #780 / #781 +8.44, +2.26 at 8 threads; Halogen #458 "thread meritocracy" +29.39 ± 5.41 (5+0.05, 8 threads, 5,000 fixed games; mechanism undescribed: UNVERIFIED) (G3) | §3.6; T53; §6.3 item 4 (main thread's result in v1, voting a separate SPRT) |
| Majority vote for the soft stop | Reckless: 8 threads at 25+0.25 +4.48 ± 2.94, [0, 4]; 8 threads at 5+0.05 unfinished (+1.21, LLR 0.67); 16 threads at 5+0.05 +2.59 ± 2.02 (G1; rare.md RI-36) | §3.7 (time management with threads) does not have it |
| The highest-depth thread drives optimism | Reckless +1.95, +2.44, then +7.64 ± 4.03 at 25+0.25, 8 threads (G1) | — ; no fit: Fork has no optimism (F11 stopped by the owner) |

## 4. Shared data and table sizes

| Form | Evidence | KB entry | Fork |
|---|---|---|---|
| Correction histories shared, per NUMA node | Halogen #842 (in idea 17): +18.63 ± 5.78 at 20+0.2 with 8 threads, +44.24 ± 8.83 at 32 threads (5+0.05, 1,374 games) (G3); Viridithas #390 +3.89 ± 2.42 with 4 threads; Caissa 1.25 +6 on 4 threads (G2) | §3.3 (Stockfish 1a67ccc7, per NUMA node) | idea 17; KB §6.3 item 5 keeps histories per thread in v1 |
| Continuation history shared | Potential +12.08 ± 7.45 (8 threads, 5+0.05), +6.85 ± 5.03 (8 threads, 20+0.2), [0, 7.5] (G4) | §3.3 (Stockfish f9b002cf) | never tried |
| Table sizes scaled with the thread count | Potential: correction tables +11.73 ± 7.11 and pawn history +8.96 ± 5.99, both 8 threads at 20+0.2; failed or flat at 5+0.05 (G4; rare.md RI-38) | §3.10 covers the TT's Hash only | never tried |
| Static eval in the TT, eager eval-only writes | Igel #357 +21.22 ± 5.22 at 8 threads (5+0.05) against +7.97 STC / +2.07 LTC at 1 thread; Seer "towards no eval cache" H0 at STC, +10.26 ± 5.27 at 8 threads, 20+0.2 (G3, G4; evidence.md F3) | — | F3 never tried: test with or after 17a |
| SMP-only TT store of intermediate results | Reckless: 1 thread -3.61 ± 3.36 (H0), 8 threads +3.99 ± 2.78 (G1; rare.md RI-37) | §3.4 (replacement under SMP) | never tried |
| Depth-relaxed TT cutoffs | Ethereal 75bfcfb: +3.43 ± 3.22 at 5+0.05 with 8 threads, [-1, 3], besides its STC and LTC passes (G3; rare.md RI-27) | — | never tried; a 1-thread test first |
| An exact result replacing a lower-bound entry | Halogen #593: +1.54 ± 1.56 at 8 threads, unresolved (G3; rare.md RI-28) | — | never tried |

## 5. Tuning and testing under SMP

- **SPSA under SMP conditions (G4 row).** Hobbes #401 and #411 (4 threads, 20+0.2) and Raphael #160 (8 threads) each
  also passed a 1-thread LTC test; Viridithas #388 +9.57 ± 4.02 at 4 threads; Caissa 1.24 and 1.25 about +5 and
  +3.1 at 4 threads (G2). Against: Reckless's 1-thread loss (comparison.md G4) and Halogen #778 (KB §2.4, T54).
  The KB keeps Fork's tuning at one thread unless Fork's own test says otherwise; the new results make that test
  worth running once SMP exists.
- **Lazy SMP baselines.** Hobbes "very naive" first version: 2 against 1 thread +65.86 ± 6.06, 4 threads +135.90 ±
  7.27 at 8+0.08; Horsie 2 threads +81.18, 4 threads +139.90 (G2). The KB's §2.4 has the same range from Tarnished,
  Hobbes and Raphael. A yardstick for Fork's first result.
- **Long-TC dependence.** Potential's thread-scaled tables and Seer's eager TT writes gained only at the longer
  TC, Stockfish's removal of depth skipping passed only at 60+0.6 (KB §3.2), and Reckless's soft-stop vote was
  unresolved at 5+0.05 but passed at 25+0.25. SMP SPRTs for Fork belong at the longer TCs (KB §3.11, §6.4).
- **NUMA.** RubiChess disabled its NUMA support after TCEC (#507; also KB §2.4); Stormphrax #294 a shared net plus
  NUMA, "5~10% bench speedup on 14 threads"; PZChessBot #348 NUMA pinning (G2, G3). Measure on the TCEC box's
  topology first (KB §3.8; tcec-hardware-test-plan.md).
- **Hardware sensitivity.** Triumviratus's memory-bandwidth-dependent result (rare.md RI-43) matters most for SMP
  and shared-table features, whose cost is memory traffic.

## 6. Suggested order for Fork's SMP tests (suggestions, not decisions)

Following the KB's v1 (KB §6.3) and its test list (KB §6.4):

1. v1 with the hygiene rules of section 1 (no Elo test of its own; the 2-against-1-thread SPRT measures the whole).
2. The first diversity SPRT (RI-35), one reduction-side form, at 4 to 8 threads, with a 1-thread non-regression.
3. Voting (T53) and the soft-stop vote (RI-36), each as its own SPRT at the longer TC.
4. Shared correction tables per NUMA node (idea 17), then thread-scaled sizes (RI-38), at the longer TC only.
5. F3 and the SMP-only TT policies (RI-37, RI-27's 8-thread angle) after the first three, since their gains grow
   with threads.
