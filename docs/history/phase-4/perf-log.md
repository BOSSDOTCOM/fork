# Phase 4 performance log

Speed changes to the default engine that keep bench identical (nodes and
signature): no SPRT, each verified by `bench/ab_search.py` (interleaved, core
4, identity-checked, `--same-nodes`) on a quiet machine; a change counts only
if both estimators move the same way by more than 3% or twice the
round-to-round spread (the harness's rule), and is kept only then (owner,
2026-11-06). WSL Ubuntu, clang 21.1.8, Release, `-march=native`, Ryzen 7
7600X3D.

## The speed sprint of 2026-11-06 (owner)

**Profile** (the default engine, S512r2 with IIR, phase-4 at 684bac6; perf
cpu-clock at 4 kHz over 64 UHO positions, every 4,000th line of
`UHO_Lichess_4852_v1.epd`, `go movetime 250` each after `ucinewgame`, Hash
16, 1 thread; self time by source function as `llvm-addr2line -f` names
the sampled address, so inlined code is counted under the inlined function
(`TtEntry::bound`, for example, is the inlined read of a TT entry, not a
call; corrected 2026-11-06); shares of Fork's samples):

| area | share | largest functions |
|---|---|---|
| network | 41.5% | `advance_values` 17.2 (the accumulator update), `squared_sum` 14.5 (the output layer), `sum_perspective` 2.5 (refreshes), `evaluate_with` 1.9, `column` 1.7 |
| move ordering | 14.7% | `MoveSelector::select_best` 5.9, `see_at_least` 3.1, `take_next` 2.8, `score_quiets` 1.8, `score_captures` 0.9 |
| TT | 12.7% | `TtEntry::bound` 8.3 (the first read of the bucket: the stall), `predicted_key` 1.6, `deposit` 1.0, `splitmix_finalize` 0.8 |
| move generation | 10.8% | `SliderEntry::table_index` 2.4 (PEXT), `fill_moves` 2.4, `add_piece_moves` 1.8, `attackers_to` 1.7 |
| search | 5.7% | `negamax` 3.6, `quiesce` 1.2 |
| make/unmake | 2.0% | `make` 0.7, `toggle_keys` 0.6 |
| other | 12.6% | spread thin (largest 0.7) |

Two of the owner's candidates were already in place: lazy accumulator updates
(FeatureStack computes a ply's sums only when its evaluation is needed) and
the TT bucket prefetched at make-move (`predicted_key`, review 2), on a table
with transparent huge pages (`madvise`).

**Candidates**, each behind a build flag in one tree (perf/sprint), every
bench 14180299 / 4cf778ff753861f7; 10 interleaved rounds each against the
same base:

| candidate | median | best | verdict |
|---|---|---|---|
| C1: the output layer on AVX-512 (VNNI's `dpwssd` where compiled), four independent sums | not measured | | **parked** (owner): the SPRT shards build x86-64-v3 only, so the path would never run there; to be revisited for TCEC's x86-64-v4 builds. AVX2 stays the default path. Its code is kept on archive/sprint-candidates. |
| C2: the delta's feature rows prefetched at make-move, all 16 lines | −2.9% | −2.7% | no significant difference: not kept |
| C2, 4 lines per row | −1.4% | −1.1% | no significant difference: not kept |
| C3: the child's TT bucket prefetched before the pruning tests (not after them) | −0.8% | −0.9% | no significant difference: not kept |
| **C4: `select_best` keeping the best score in a register** (the same first maximum, so the same order) | **+4.0%** | **+3.3%** | **faster: kept** |
| C2 (4 lines) + C3 together (owner: every candidate below the threshold, combined) | −2.0% | | no significant difference: not kept |

C4's loop compared each score with the score at the best index, a load that
depended on the previous iteration's choice; keeping the best score in a
register leaves only the compare and two moves per element. Ties keep the
first maximum, so the order of moves, and bench, are unchanged.

**Cumulative speedup of the kept changes: +4.0% median, +3.3% best (C4
alone).**

### Round 2 (2026-11-06, the owner's "new candidates from the profile")

On phase-4 with C4 (9f368d6) as the base, each behind a build flag on
archive/sprint-candidates-2, every bench 14180299 / 4cf778ff753861f7; a
debug build with all three passed the consistency, search, ordering,
pruning and nnue suites (its every incremental accumulator checked against
a refresh); 10 interleaved rounds each on a quiet machine (g3e and the
SPRT driver suspended):

| candidate | median | verdict |
|---|---|---|
| E1: a per-thread slot per perspective and file flip holding that frame's last sums and their pieces, so a frame change (the king across the d/e line) applies only the pieces that differ instead of summing every piece (the refresh-cache concept publicly described for NNUE engines, "Finny tables") | −5.3% | **slower**: not kept |
| E2: `select_best`'s scan on AVX2 (the largest score 16 at a time, then the first index holding it: the same first maximum) for lists of 16 or more | +1.0% | no significant difference: not kept |
| E4: both perspectives advanced in one pass when both need the same plies | −0.6% | no significant difference: not kept |
| E2 + E4 together (owner: every candidate below the threshold, combined) | −0.2% (noise threshold 5.1% in that run) | no significant difference: not kept |

Round 2 keeps nothing; **the cumulative speedup stays +4.0% (C4)**. E1's
loss likely comes from copying 1 KB per slot at every frame change and the
larger FeatureStack, against refreshes that were only 2.5% of the time
(UNVERIFIED, not profiled).

## Speed sprint 3 (2026-11-12, the owner's order of about 3:35 PM EST): the network evaluation

**Profile** (phase-4 at e6b2ac3, r8brft1, `fork bench`; perf in WSL on the
x86-64-v3 Release+LTO build, pinned; the profile report is kept outside the
repository): the network is 47.6% of cycles, `advance_values` (the
accumulator update) 26.3% self, `push_move` 4.7, `squared_sum` 3.4. The
update's disassembly showed its inner loop running once per 16 lanes and per
row: a pointer load, the subtract or add with its memory operand, then the
loop's increment, compare and branch, so five instructions per row and
vector, with the samples on the instruction after each weight load. The
stats build (FORK_SEARCH_STATS) gave 6.0 M evaluations, 14.1 M perspective
updates of 3.15 rows each, 10.8 frame refreshes per 1,000 updates and 1.19
plies walked per evaluation.

**Main metric while data generation runs: instructions:u per bench** (perf
stat; deterministic to about 1e-8), with nps A/Bs in quiet windows
(data generation suspended).

**nnue-fused (b3b1f5c), adopted:** the update works in register tiles (8 of
AVX2's 16 vectors; up to 16 of AVX-512's 32, the whole 512-wide perspective).
Each tile of the parent's sums is loaded once, every removed and added row is
applied to it with one pass per row, and the tile is stored once. int16
addition wraps, so the row order cannot change the sums, and every path still
equals the scalar reference (tests/test_nnue.cpp's equivalence tests,
unchanged).

| measure | A = e6b2ac3 | B = b3b1f5c | change |
|---|---|---|---|
| instructions:u per bench (WSL, x86-64-v3) | 42,841,608,071 | 29,390,085,210 | -31.4% |
| nps, WSL x86-64-v3, core 4, 24 rounds (median / best) | 2,959,981 / 3,037,681 | 3,393,689 / 3,507,132 | **+14.7% / +15.5%** (noise threshold 4.5%: faster) |
| nps, Windows clang-release (native, AVX-512 path), unpinned, 24 rounds (median / best) | 3,035,288 / 3,079,853 | 3,199,610 / 3,262,802 | **+5.4% / +5.9%** (noise threshold 3.2%: faster) |

Quiet window of 4:02-4:07 PM EST (g4c suspended); bench/ab_search.py,
interleaved, identity checked (variant, commit, SHA-256) before the run and
on all 48 runs of each part, `--same-nodes`. Bench identical on every build:
9,118,607 nodes / 208629aa15e140a9 (r8brft1). The AVX-512 path gains less
because its old loop already had twice the lanes per row pass.

**Maintenance cost (non-negotiable 7): small.** The kernel keeps its shape
(load, the rows, store) with one more loop level, about 20 lines more. The
scalar reference and the tests are unchanged. The tile sizes are coupled to
the register files, and a static_assert stops the build if a future hidden
size is not a multiple of a tile (768 on AVX-512, for example, needs a tile
of 8 or 24, a one-line change). Speed under GCC (TCEC's gcc 11.4 and g++-12)
is UNVERIFIED: measured with clang 21 only; CI's bench parity covers GCC's
correctness.
