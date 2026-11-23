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
of 8 or 24, a one-line change). Speed under GCC: confirmed in window 2 below
(gcc 11.4.0 through update.sh, +9.0% median, +7.8% best).

### Speed sprint 3, window 2 (2026-11-12, 5:14-5:28 PM EST): the network candidates after nnue-fused

Each candidate on its own branch on top of phase-4 46f2b1e (nnue-fused adopted), committed through the pre-commit
check, not merged; bench/ab_search.py, 24 interleaved rounds, core 4, WSL, identity checked on every run,
`--same-nodes` (bench identical within every pair); g4c suspended.

| part | A | B | instructions:u per bench | nps median / best | verdict |
|---|---|---|---|---|---|
| GCC 11.4.0, update.sh, x86-64-v3 (Ubuntu-22.04): nnue-fused on TCEC's compiler | e6b2ac3 | 46f2b1e | | +9.0% / +7.8% (threshold 4.5%) | faster: the fused gain holds on GCC (clang +14.7%) |
| I4: int8 feature-transformer rows (FORK_FT_INT8, net r8brft1i8 on both sides) | 46f2b1e int16 rows | b550b5b | 28,195,288,830 -> 31,479,184,599 (+11.6%) | -0.9% / -0.9% (threshold 3.0%; a clean rerun at 5:39-5:41 PM: the first run in the window was disturbed, threshold 36.5%) | no significant difference, below the owner's 3% bar: no SPRT, not adopted |
| AVX-512 output layer (x86-64-v4) | 46f2b1e | 6e01c57 | 26,940,852,566 -> 25,860,277,956 (-4.0%) | +2.1% / +1.6% (threshold 3.0%) | no significant difference: not adopted |
| the same with VNNI on both sides | 46f2b1e | 6e01c57 | 26,928,843,546 -> 25,872,282,013 (-3.9%) | +1.4% / +1.6% (threshold 3.0%) | no significant difference: not adopted |
| frame changes refreshed lazily from per-frame snapshots (x86-64-v3) | 46f2b1e | b477ba2 | 29,390,082,350 -> 28,660,350,321 (-2.5%) | +1.1% / +1.1% (threshold 3.0%) | no significant difference: not adopted |
| the lazy refresh without snapshots (measurement build) | 46f2b1e | b477ba2 + FORK_S3_NOSNAP | 29,390,082,350 -> 29,314,175,562 (-0.26%) | not run (below any threshold) | not adopted |
| x86-64-v3 against native, both cmake/pgo.cmake clang PGO builds of 46f2b1e | v3 | native | | -1.5% / -1.4% for native (threshold 3.0%) | no significant difference: native is not faster |

Bench was identical in every pair: 9,118,607 / 208629aa15e140a9 (r8brft1); 8,794,009 / 8ac56bcaac6e05ff on
r8brft1i8 for the I4 part. The instruction counts fell for the AVX-512 output layer and the snapshot refresh, but
neither moved nps beyond the noise; I4 added 11.6% instructions (the widen-and-multiply) and halving its rows'
bytes did not pay on this CPU (1 MB L2, 96 MB L3; why is UNVERIFIED, not profiled). TCEC's EPYCs (less L3 per
CCD, shared by many threads) could differ: UNVERIFIED, worth one re-measurement in the TCEC build matrix if the
net grows. I4's quality gates on r8brft1i8 all passed (quantization loss max 17.7, p99 13.7, mean 3.6 cp against
r8brft1's 10.7 / 8.4 / 2.4 and the limits 21 / 16; endgame 7 of 900 as r8brft1; held-out 4-5 piece 606 against
612, 6-7 piece 786 against 770, both within the 1.15 flag), so a larger net that is bandwidth-bound could revisit
it (tools/nnue/int8_rows.py and the FORK_FT_INT8 build stay on the unmerged branch speed3/nnue-i4).

The PGO comparison answers which target the native builds (g4d's Control Center build, the play build) should
use: x86-64-v3 is at least as fast as native for the fused head (native -1.5%, within the noise).

The candidate branches are kept locally, not merged: speed3/nnue-i4 (b550b5b), speed3/nnue-avx512 (6e01c57: the
AVX-512 output layer and a startup CPU check, src/core/cpu_gate.cpp, which refuses with a message a CPU without
the instruction sets the build targets; a design for idea 163, whole-engine dispatch at main, is in the speed
sprint report), speed3/nnue-refresh (b477ba2).

### Speed sprint 3, the search core (2026-11-12): captures generation adopted under the cycles-per-node rule

**Profile** (phase-4 at e6b2ac3, r8brft1, `fork bench`, 1 thread; WSL clang 21.1.8, x86-64-v3 Release+LTO and a
frame-pointer twin; perf `cycles:u` over 6 bench runs per build, pinned, ASLR off, 64,576 and 70,339 samples;
addresses resolved with their inline frames; each sample charged to the first subsystem found from the leaf
outward, so `attackers_to` under SEE counts as SEE; g4c running throughout, so shares, not speeds): network 47.6%,
move selection 13.2%, TT 7.4% (its layout and atomics are left to step 17a's SMP design), move generation 7.3%
(captures generation 4.1% inclusive), the negamax body 7.0%, SEE 4.8%, make/unmake 3.7%, the drift tables 2.6%,
the quiescence body 1.9%, gives_check 0.7%, draw detection 0.6%. A cheaper gives_check is therefore capped below
the 1% rule, and the quiet scoring is already lazy at stage level (quiets are generated and scored only when the
selector reaches them; scoring per pick would change the order of equal scores).

**Candidates** (each bench-identical by construction, on its own branch on phase-4 46f2b1e, through the
pre-commit check):

- **capgen** (speed3/capgen-skip 204c33a): the captures-only generation visits only the king squares of the kind
  it generates, and only the pawns that can add a move (on the seventh rank, attacking a capture target, beside
  the en passant square); the skipped squares and pawns added nothing and the rest keep their ascending order,
  so every list is the same move for move.
- **see** (speed3/see-xray f8e2289): `see_at_least` takes `attackers_to` once and at each later lookup looks up
  only the last capturer's line again.

**A/B** (quiet window 5:29-5:39 PM EST, g4c suspended; WSL, clang 21.1.8 Release+LTO; a scratch driver
interleaving A B / B A rounds pinned to core 4, each `fork bench` under `perf stat -e cycles:u,instructions:u`,
identity checked through bench/ab_search.py's own check (variant, commit, SHA-256) on every run, bench nodes and
signature equal within every pair; the nps verdict is ab_search.py's rule, the cycles verdict the 1% rule with
the same two estimators: median and best both beyond 1% or twice the round-to-round spread):

| pair (20 rounds) | instructions:u per bench | cycles/node median / best | nps median / best | verdict |
|---|---|---|---|---|
| A/A, base 46f2b1e against its byte copy (8 rounds), x86-64-v3 | +0.000% | -0.46% / -0.07% (threshold 2.19%) | -0.73% / -0.30% | no difference (the harness's floor) |
| capgen against base, x86-64-v3 | 29,388,081,772 -> 28,880,744,798 (-1.73%) | **+2.91% / +3.00% faster** (threshold 1.59%) | +2.70% / +3.09% (threshold 3.0%) | **faster by the cycles rule**; nps rule not met |
| capgen against base, x86-64-v4 | 26,938,851,406 -> 26,473,215,112 (-1.73%) | **+2.40% / +2.30% faster** (threshold 1.54%) | +2.47% / +2.06% (threshold 3.0%) | **faster by the cycles rule**; nps rule not met |
| capgen + see against capgen, x86-64-v3 | -0.06% | -0.09% / +0.05% (threshold 2.29%) | +0.04% / +0.13% | no difference: see adds nothing |
| capgen + see against base, x86-64-v3 | -1.78% | +2.40% / +2.53% faster (threshold 1.82%) | +2.23% / +2.45% | faster by the cycles rule |
| capgen + see against base, x86-64-v4 | -1.79% | +3.15% / +2.12% (threshold 3.47%) | +3.05% / +2.06% (threshold 3.56%) | no significant difference |

Bench identical in every pair: 9,118,607 / 208629aa15e140a9 (r8brft1).

**Adopted (owner, about 5:50 PM EST): capgen**, under the 1% cycles-per-node rule for bench-identical speed
changes (DESIGN.md §6, 2026-11-07 decision 8; the think tank's X13): +2.9% cycles per node on x86-64-v3 and
+2.4% on x86-64-v4, beyond their noise thresholds; the nps rule's 3% floor was not met. **see is dropped**: it
adds nothing on top of capgen (archived as archive/speed3-see-xray, and the pair as archive/speed3-see-capgen).
The first SEE version, which updated its attacker set after every capture, cost +0.13% instructions: exchanges
settled by the threshold tests paid for an update no lookup used.

**Maintenance cost (non-negotiable 7): small.** About 15 lines in `fill_moves`: one mask for the king's squares
and, in the captures-only mode, one pawn mask made of two shifts per side and the en passant neighbours, each
with its comment. Legal generation is unchanged (its king mask stays `~ours`); the quiets-only mode gains only
the king mask. The perft suites (perft_epd, perft_epd_deep, the mirror and edge suites), the difftest
against python-chess and bench parity on every network and the bootstrap evaluation cover it.

## Speed sprint 4 (2026-11-13, the owner's order of about 11:20 AM EST): huge pages (R19) and the pair tables' colour fold

**Setup.** Each candidate against the same base, phase-4 49494bb (r8brft1; bench 6,426,679 / 4c4375887f835cc7), WSL
Ubuntu, clang 21.1.8, Release + LTO, x86-64-v3; a scratch driver interleaving A B / B A rounds pinned to core 4,
each `fork bench` under `perf stat -e cycles:u,instructions:u`, identity checked through bench/ab_search.py's own
check (variant, commit, SHA-256) on every run. **The PC was loaded throughout** (g4c's 10 data-generation threads
and other agents' work on 12 hardware threads; no quiet window was authorised): nps varied by a factor of two
within one A/B (medians 0.58 M to 1.2 M against about 3.4 M in sprint 3's quiet window), so the nps rule's noise
thresholds were 24-43% and only cycles per node (thresholds 2.5-4.1%) and instructions can decide. Rules as in
sprint 3: nps by ab_search.py's (3% or twice the spread), cycles per node by the 1% rule (DESIGN.md §6,
2026-11-07 decision 8).

**What existed.** On Linux the TT was already one 2 MiB-aligned block with `madvise(MADV_HUGEPAGE)` (hash_memory.cpp;
WSL's kernel 6.18 runs transparent huge pages in `madvise` mode, and bench's 16 MB table was 16,384 kB of
AnonHugePages). The network is not in file-backed .rodata as R19's write-up assumed: `embedded_net()` parses the
embedded bytes into a heap `NetFile` once, so the weights the search reads sit on ordinary 4 KB heap pages.
Windows large pages need SeLockMemoryPrivilege, which this account does not hold (`whoami /priv` lists no
SeLockMemoryPrivilege), so a Windows path could be built but not measured here: not built.

| candidate (16 rounds each) | instructions:u per bench | cycles/node median / best | nps median / best | verdict |
|---|---|---|---|---|
| upper bound with no code change: the same binary with `GLIBC_TUNABLES=glibc.malloc.hugetlb=1` (12 rounds; it gave huge pages to part of the Searcher only, AnonHugePages 16 -> 20 MB) | -0.015% | +0.10% / +0.86% faster (threshold 1.33%) | -2.4% / -6.2% (threshold 8.7%) | no difference |
| **R19**: the `NetFile` and the `Searcher` (its histories, pair tables, drift tables, frames) each in their own 2 MiB-aligned, `MADV_HUGEPAGE` block, sized up to whole 2 MiB pages (AnonHugePages 16 -> 24 MB) | -0.030% | **-0.13% / -0.07%** (threshold 4.11%) | +0.45% / -11.8% (threshold 43.0%) | **no difference: not adopted** |
| **colour fold**: each pair table 384 x 768 instead of 768 x 768 (below) | **+0.312%** | **-0.29% / -0.78%** (threshold 2.45%) | -0.71% / +16.4% (threshold 24.5%) | **no difference: not adopted under the speed rule** |

Bench identical in every pair (6,426,679 / 4c4375887f835cc7).

**R19's mechanism worked; it did not pay.** perf's generic TLB events (3 runs each, per node; on this AMD CPU
`dTLB-loads` and `dTLB-load-misses` are taken to be L1 DTLB misses and L2 DTLB misses, the mapping UNVERIFIED):
base 23.6 L1 misses and 0.78 page walks, R19 17.7 and 0.60. The six fewer L1 misses per node hit the L2 TLB and
cost nothing measurable in cycles (about 2,150 cycles per node under this load). R19's kill rule (under 1% of
cycles in both the 16 MB and 4 GB regimes) is met in the 16 MB regime; the 4 GB regime cannot run on this PC (about
1-2 GB of memory available) and stays unmeasured. On Zen 4 (3,072 L2 DTLB entries) a 4 GB table on 2 MiB pages
needs 2,048 entries, so that is where the net's and the Searcher's 4 KB pages would start to compete: the case for
a runner (16 GB) or TCEC-class re-measurement, not for adoption now. Archived as archive/speed4-r19-hugepages
(the build-flag prototype: `FORK_S4_NET`, `FORK_S4_SEARCHER`).

**The colour fold** (the concurrency review of 2026-11-11, A5): at a node the arrival's colour follows from the
slot's (the opponent's move for the reply table, the side's own for the follow table), so a row per arrival piece
type and square (`pair_row`) and a column per full slot hold every value the 768 x 768 table held, in half the
memory: 1.125 MiB instead of 2.25 MiB per searcher (about 0.56 GB less at 512 threads). The bytes touched per node
are the same (a row's used half is still 384 contiguous entries), so it saves memory, not cache; the fold's
compare-and-subtract per read and update adds 0.31% instructions, and cycles show no difference either way.
Tests: a 1:1 map of each pairing onto the folded table and 400,000 random updates, summed-base updates and
ageings against an unfolded 768 x 768 oracle (tests/test_ordering.cpp), and a debug-build check that each table
keeps one pairing (same or opposite colours) until it is cleared, which the search and pruning suites passed in a
gcc Debug build (so every search path, R20's LMR reads, the X2 probe's reads and D8's summed update, keeps the
rule); idea 42's 4-ply follow read (branch sprt/i42-cont-inputs) is a same-colour read and needs no change. Not a
speed gain, so not adopted under the speed rule; archived as archive/speed4-pair-fold, ready if the owner wants
the memory (a memory change, not a speed one; the review's own advice was to measure per-thread nps at TCEC-class
thread counts before shrinking anything).

**Runner measurement: not done.** No workflow exists for an A/B on GitHub's runners (ci.yml, nightly.yml and
tsan.yml check, sprt.yml and gauntlet.yml play games); the smallest one is a dispatchable `speed-ab.yml` (a matrix
of up to 4 runners, each building A and B and running bench/ab_search.py with `--same-nodes`, plus perf stat if
the runner's VM exposes the PMU, UNVERIFIED for Azure's), proposed to the owner. A dispatchable workflow must be
on the default branch.

**Commits.** Both candidates sit on archive tags, each on 49494bb: archive/speed4-pair-fold (41e5e2b) and
archive/speed4-r19-hugepages (2f076e5). The pre-commit check skipped both (another session's check was running;
"no pass recorded"); the fold's tests ran in a gcc Debug build in WSL (ordering, search, pruning and bench parity
passed), and both release builds gave bench 6,426,679 / 4c4375887f835cc7. Names screened (2026-11-13: `PairRows`,
`pair_row`, `check_colours`, `pairing_`, `Unpaired`, `proto_block_allocate`, `proto_block_free`, `proto_round`,
`FORK_S4_NET`, `FORK_S4_SEARCHER`): no match in Stockfish, Ethereal, Berserk or Weiss.

**Maintenance cost (non-negotiable 7):** R19 would add a second allocation path (a class-level operator new for
the Searcher, placement new for the network); the fold adds one constexpr function and a debug-only check. Neither
is adopted.
