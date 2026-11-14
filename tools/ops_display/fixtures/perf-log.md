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
