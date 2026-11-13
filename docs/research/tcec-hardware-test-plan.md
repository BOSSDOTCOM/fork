# TCEC hardware test plan

Measurements that only TCEC-class hardware can decide: many threads, a large Hash, two sockets
(NUMA). Each entry says what to measure, how, against what, and the rule that decides it, so the
session on such a machine (the "TCEC hardware session", owner, 2026-11-13; the machine is not yet
chosen) runs from this list. Started 2026-11-13 by the owner's order of about 12:40 PM EST:
"(1) Colour fold: keep the tag; revisit in step 17a (Lazy SMP) and measure in the TCEC hardware
session. (2) Add R19 huge pages at a TCEC-sized hash (e.g. 4 GB+) to the TCEC hardware test plan."

## The target conditions

From config/tcec.json (verified 2026-10-23; KB competition.md, branch kb):

| | TCEC | this PC | a GitHub runner |
|---|---|---|---|
| CPU | 2x AMD EPYC 9754 (256 cores, 512 threads) | Ryzen 7 7600X3D (6 cores, 12 threads) | 4 vCPUs (model varies by run) |
| Memory | 768 GiB; all engine RAM capped at 320 GiB | 1-2 GB free while data generation runs (perf-log, speed sprint 4) | 16 GB |
| Threads | 512 | | |
| Hash | 262144 MB (256 GiB; the cap when Hash initialisation is multithreaded, which Fork's is: `HashMemory::clear`; otherwise 32 or 64 GiB) | | |
| Large pages | "enabled automatically" (read as transparent huge pages; whether a hugetlbfs pool exists is KB competition.md question 7, UNVERIFIED) | THP in `madvise` mode (WSL kernel 6.18) | |
| NUMA nodes | unknown (`numa_nodes: null`) | 1 | 1 |

## Common method

- **Builds:** A and B from their commits through update.sh with TCEC's compiler choice and target
  (DESIGN.md §6, 2026-11-07 decision 9: x86-64-v4, PGO by default), each binary's `fork version`
  checked for target and commit (bench/ab_search.py's identity check). Bench-identical pairs are
  checked with `fork bench` first (nodes and signature equal).
- **Interleaving:** A B / B A rounds, the same core set for both sides, identity checked on every run
  (bench/ab_search.py's rules; the runner workflow .github/workflows/speed-ab.yml does the same on
  GitHub's runners for `fork bench`).
- **The speed rule** (DESIGN.md §7 and §6, 2026-11-07 decision 8): nps counts when median and best
  both move the same way by more than max(3%, twice the round-to-round spread); for a bench-identical
  change, cycles per node by the same two estimators with a 1% floor (`perf stat -e
  cycles:u,instructions:u`); a change slower locally is adopted if it is faster on the runners and in
  the TCEC build.
- **Record with every run:** the CPU, the kernel, `/sys/kernel/mm/transparent_hugepage/enabled` and
  `defrag`, `numactl --hardware`, Threads, Hash, the process's `AnonHugePages` and RSS
  (`/proc/<pid>/smaps_rollup`), and the commits.
- **Not built yet:** `fork bench` runs one thread at 16 MB Hash, so the entries below need a driver
  that sets `Hash` and `Threads` over UCI, searches the bench positions to a fixed node count (one
  thread: deterministic, so the node counts must match between A and B) or a fixed time (many threads:
  nps only), and reads nps from the last `info` line. It is to be written before the session, with
  tests, from the existing UCI test harness's process handling.

## Entries

### 1. R19: huge pages for the network and the Searcher at a TCEC-sized Hash

- **Source:** docs/history/phase-4/perf-log.md, "Speed sprint 4" (2026-11-13); ideas.md idea 174 (a) and
  idea 19; think tank R19 (docs/research/phase4-think-tank/).
- **Candidate:** archive/speed4-r19-hugepages (2f076e5, on 49494bb): the parsed `NetFile` and the
  `Searcher` each in their own 2 MiB-aligned `MADV_HUGEPAGE` block (build flags `FORK_S4_NET`,
  `FORK_S4_SEARCHER`). The TT already uses such a block on Linux. Bench identical.
- **What is known:** at bench's 16 MB Hash the mechanism worked (AnonHugePages 16 -> 24 MB; L1 DTLB
  misses per node 23.6 -> 17.7, the AMD event mapping UNVERIFIED) and cost nothing measurable:
  cycles per node -0.13% / -0.07% (threshold 4.11%). R19's kill rule (under 1% of cycles in both the
  16 MB and the 4 GB regimes) is met at 16 MB only; the 4 GB regime could not run on this PC.
- **Why a large Hash can change it:** a 4 GB table on 2 MiB pages needs 2,048 TLB entries (Zen 4's L2
  DTLB holds 3,072, perf-log; the EPYC 9754's Zen 4c figure UNVERIFIED), so at 4 GB and above the
  network's and the Searcher's 4 KB pages start to compete with the TT for the L2 DTLB, and at 256 GiB
  (131,072 2 MiB pages) the TT's own walks dominate.
- **Runs:** rebase the candidate on the then-current head (bench identity rechecked), then A = head,
  B = head + R19, at Hash 4096 MB, 16384 MB and TCEC's 262144 MB (32768 or 65536 MB too if the
  machine or the 320 GiB cap requires), each at Threads = 1 (fixed nodes, cycles and nps) and at the
  machine's full thread count (fixed time, nps). THP in `madvise` mode (what Fork's blocks ask for)
  and, as the upper bound with no code change, in `always` mode with the base binary. Per run:
  cycles and instructions per node, dTLB loads and misses per node, AnonHugePages.
- **Cheaper first:** the 4 GB regime fits a GitHub runner (16 GB), so it can be measured there before
  the session, single-threaded, once the driver exists; the runner workflow itself times only
  `fork bench` (16 MB).
- **Decision:** the speed rule. Faster at TCEC's Hash and thread count, not slower at 16 MB:
  adopt (with the maintenance note perf-log records: a second allocation path). Within the noise at
  every size: R19 is closed and the tag stays as the record.

### 2. The pair tables' colour fold

- **Source:** perf-log.md, "Speed sprint 4"; ideas.md idea 174 (b); the concurrency review of
  2026-11-11, A5 (kept outside the repository, as ideas.md idea 164 notes).
- **Candidate:** archive/speed4-pair-fold (41e5e2b, on 49494bb): each pair table 384 x 768 instead of
  768 x 768 (a row per arrival piece type and square), the same values in half the memory: 1.125 MiB
  instead of 2.25 MiB per searcher, about 0.56 GB less at 512 threads. Bench identical
  (6,426,679 / 4c4375887f835cc7 at 49494bb).
- **What is known:** one thread on this PC: cycles per node -0.29% / -0.78% (threshold 2.45%),
  instructions +0.31%: no difference, so not adopted under the speed rule. The bytes touched per
  node are the same, so a gain, if any, comes from many threads sharing caches and memory, which one
  thread cannot show; the review's advice was to measure per-thread nps at TCEC-class thread counts
  before shrinking anything.
- **When:** the owner's order: keep the tag, **revisit in step 17a (minimal Lazy SMP, DESIGN.md
  §5.6)**, once per-thread searchers exist, and measure in the TCEC hardware session.
- **Runs:** rebase onto step 17a's result (bench identity at Threads = 1 rechecked; the fold's
  oracle tests in tests/test_ordering.cpp and its debug-build pairing check come with it). A = 17a,
  B = 17a + fold, Hash fixed (TCEC's size if the machine allows), Threads = 1, 16, 64, 256 and 512
  (and one socket's worth, pinned with `numactl`, to separate NUMA from cache effects), fixed time per
  position: total nps and nps per thread, RSS and the process's memory per thread.
- **Decision:** the speed rule at TCEC's thread count (nps; cycles per node does not apply with many
  threads, whose node counts differ run to run), with no loss at Threads = 1. Within the noise
  everywhere: the fold stays a memory option for the owner (0.56 GB at 512 threads against the
  320 GiB cap), not a speed change.

## Related open questions

- KB competition.md question 7 (explicit huge pages, `MAP_HUGETLB`, 1 GiB pages) and question 8 (CPU
  features of both servers) bear on entry 1; ideas.md idea 19 holds the explicit-pages design.
- DESIGN.md §5's Phase 8 TCEC-readiness checks (Hash at TCEC sizes and under cgroups) need the
  same machine and may share its session.
