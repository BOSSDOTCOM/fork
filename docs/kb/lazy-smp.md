# Lazy SMP for Fork

Owner's order (2026-11-15): a knowledge-base entry on Lazy SMP with the
papers, measurements and best practices. Fork searches on one thread today;
minimal Lazy SMP is roadmap row 17a (main's DESIGN.md §5.6, after the
engineering review's W1) and the Phase 6 "SMP" line (DESIGN.md §5).

- **Verified:** 2026-11-15 (every page in §8 opened that day, unless a row
  says it failed).
- **Scope:** concepts, published measurements and testing practice only.
  No engine source was cloned, downloaded or read. Some CPW pages, commit
  messages and PR texts opened here contain code lines; none of them were
  used or are reproduced or paraphrased here.
- **Constants:** following the KB's rule (search-techniques.md §3), other
  engines' parameter values are not recorded. Elo figures, node rates and
  speedups are published results, not parameters. Numbers that came from a
  source and could be read as settings are marked as **source examples,
  not Fork's values**.
- **Overall tag:** **REFERENCE ONLY** (ideas and evidence). Tools named in
  §3.11 and §4.1 (ThreadSanitizer, numactl) are **USE**. Other engines'
  code is **OFF-LIMITS**.
- **Related KB entries:** techniques.md §7 (the short SMP and NUMA notes);
  research.md "Lazy SMP" and "DTS" (papers); search-techniques.md §3.31
  (T53, choosing the move across threads) and §3.32 (T54, keeping threads
  diverse); time-management.md (the Phase 6 notes: best-move instability
  over all threads, re-searching the same depth, one thread reading the
  clock); nnue-design.md §2.5 (lazy accumulator updates and the shared TT);
  competition.md §2 (TCEC hardware and engine settings); os-memory.md
  (Hash allocation facts). This entry adds to them and is consistent with
  them. Where an item is already covered there, it links rather than
  repeats.

---

## 1. What Lazy SMP is

### 1.1 The mechanism

- Every thread runs the engine's normal iterative-deepening search on the
  same root position. The threads do not divide the tree among
  themselves: there are no split points, work queues or messages between
  threads during the search.
- They cooperate only through the shared transposition table (TT). A
  thread that reaches a position another thread has already searched finds
  that thread's bound, depth and best move there, and can cut off or at
  least order its moves better.
- One thread (the **main** thread) talks to the GUI, watches the clock and
  reports the move. The others (**helpers**) search until told to stop.
- Stockfish's commit that introduced it describes it the same way: all
  threads start on the root, and the shared TT is the only means of
  synchronisation (Stockfish ecc5ff66, 2015-10-06).
- CPW describes the variants: helpers launched at different depths, or with
  varied root move ordering, relying on timing nondeterminism to make the
  trees differ (CPW "Lazy SMP").

### 1.2 History

| When | What | Source |
|---|---|---|
| 1993 | Vincent David's PhD thesis (ENSAE Toulouse) describes a parallel search (αβ*) built on a shared hash table, the idea Lazy SMP later reused. | CPW "Lazy SMP", "Shared Hash Table" |
| before 2012 | Pure shared-hash-table search had the reputation of poor speedup even on two processors, although its nodes-per-second scaling was close to perfect. | CPW "Parallel Search", "Shared Hash Table" |
| 2012-12-27 | Julien Marcel coins the name "Lazy SMP" on TalkChess. His original idea differed (splitting move generation and evaluation; KB sources.md, 2026-10-26). | CPW "Lazy SMP" |
| 2013-01-12 | Daniel Homan, "Lazy SMP, part 2": EXchess threads search the same root with the same window and share only the hash tables; history, reply and killer tables are per thread; about half the threads search one ply deeper; only the main thread's result is used. Measured: +70 Elo for 2 threads and +140 for 4 in a 6s+0.1s gauntlet, against about +105 for one thread at double time, while time to fixed depth improved far less (§2.2). | TalkChess t=46858 |
| 2013-03-09 | Homan, "part 3": root moves divided between even and odd threads; time to depth looked much better, but games showed the new version weaker. The cause was a bug that made odd threads ignore the hash move, which the test suite did not reveal but games did. | TalkChess t=47455 |
| 2013-07-03 | Homan, "Lazy SMP and Work Sharing": an ABDADA-like step, where a thread moves a move to the end of its list if another thread is searching the same move at the same depth at that ply; about 10% faster than the previous scheme. | TalkChess t=48536 |
| 2015 | Martin Sedlak's Lazy SMP in Cheng (every second helper one ply deeper; CPW's pseudo-code description). Kai Laskos's comparison of Lazy SMP, YBWC and DTS engines (§2.2). | CPW; TalkChess t=56019 |
| 2015-10-06 | Stockfish replaces its YBWC search with Lazy SMP (ecc5ff66), released in Stockfish 7 (January 2016, per CPW). | GitHub commit; CPW |
| 2017-08 | Peter Österlund publishes Texel's Lazy SMP and "lazy cluster" (MPI) with NPS and Elo scaling to 32 cores and 16 cluster nodes (§2.2). | TalkChess t=64824 |
| 2018-08 | chess22k at TCEC on 44 cores: authors discuss helper depth-skip rules and a NUMA placement bug that cost one engine almost half its speed (§4.6). | TalkChess t=68154 |
| 2024-05 | Stockfish adds NUMA awareness: threads bound to NUMA nodes and the network weights replicated per node (PR #5285; Stockfish 17, September 2024). | GitHub PR #5285; Stockfish 17 post |
| 2025-12, 2026-06 | Stockfish starts sharing some history tables between threads (correction history per NUMA node, then continuation history), with gains at 8 to 256 threads at a cost in nps (§3.3). | Stockfish 1a67ccc7, f9b002cf |

### 1.3 Why it works

- **TT sharing.** Results stored by any thread save work for the others
  (CPW "Shared Hash Table": the speedup comes from not re-searching nodes
  another thread already stored).
- **Diversity.** The threads' trees drift apart through timing noise,
  per-thread move-ordering tables and, in many designs, different depths.
  Homan attributed his Elo gain to two things: helpers one ply deeper leave
  deeper TT results for the main thread, and independent pruning
  heuristics make it less likely that a key move is pruned in every thread
  (t=46858).
- **Widening.** A Lazy SMP search at a fixed depth plays stronger than the
  same engine's one-thread search at that depth, so time to depth
  understates its benefit. Laskos measured this directly: at fixed depth,
  8 threads against 1 scored +66 Elo for Cheng (213 games) and +53 for
  Komodo (105 games); Andscacs's +191 came from only 30 games. The YBWC
  and DTS engines in his test did not widen, so for them time to depth
  equals the effective speedup (t=56019). Stockfish still treats widening
  as real: it reduces more as the thread count grows "since Lazy SMP
  naturally widens search" (KB T54, 135caee6).
- **Near-perfect nps scaling and simplicity.** With no split points the
  threads never wait for each other. In Laskos's 8-thread table the Lazy
  SMP engines reached about 7.2x nps against 6.3x to 6.9x for the YBWC
  engines (t=56019). Österlund chose it because it is easy to make fully
  asynchronous (t=64824).
- **Why it replaced YBWC and DTS in practice.** Stockfish's switch
  measured +44.75 Elo at 20 threads LTC against its own YBWC search
  (ecc5ff66). In a 2021 thread a university project reported YBW scaling
  poorly at high thread counts, and the thread's author suggested that
  aggressive pruning lowers the effective branching factor, which hurts
  YBW (t=78631). That explanation is a forum opinion, not a measurement
  (**UNVERIFIED** as the cause).
- **What it does not do.** Lazy SMP makes almost no attempt to reduce
  search overhead (Hyatt's reply in t=56019). Its time to depth is worse
  than YBWC's or DTS's (CPW "Lazy SMP"; Laskos's table in §2.2). It wins
  on Elo, not on depth.

---

## 2. Papers and measurements

### 2.1 Academic and published papers

No peer-reviewed paper measuring Lazy SMP was found, which confirms
research.md (2026-10-23). The evidence is forum posts, engine test logs and
one M.Sc. thesis. The papers below cover the older algorithms Lazy SMP
replaced and the lockless TT it relies on. "Metadata" means only the
Crossref record was opened (authors, title, venue, pages); the paper's
content is then known only from CPW's description and is marked so.

| Paper | What it covers or measured | Opened | Tag |
|---|---|---|---|
| T. A. Marsland, M. Campbell, "Parallel Search of Strongly Ordered Game Trees", *ACM Computing Surveys* 14(4):533-551, 1982. doi:10.1145/356893.356895 | Survey of parallel alpha-beta, including principal-variation splitting (CPW). | metadata | REFERENCE ONLY |
| R. M. Hyatt, B. W. Suter, H. L. Nelson, "A parallel alpha/beta tree searching algorithm", *Parallel Computing* 10(3):299-308, 1989. doi:10.1016/0167-8191(89)90102-6 | Shared-memory parallel alpha-beta from the Cray Blitz team (CPW). | metadata | REFERENCE ONLY |
| R. Feldmann, B. Monien, P. Mysliwietz, O. Vornberger, "Distributed Game-Tree Search", *ICCA Journal* 12(2):65-73, 1989. doi:10.3233/icg-1989-12203 | The Young Brothers Wait Concept: a node's first move is searched completely before its other moves are handed to other processors. CPW reports a speedup of about 11 on 16 processors, which Schaeffer criticised in the same journal for not accounting for the serial search's efficiency (reply: doi:10.3233/icg-1990-13104). | metadata; content via CPW | REFERENCE ONLY |
| J.-C. Weill, "The ABDADA Distributed Minimax-Search Algorithm", *ICCA Journal* 19(1):3-16, 1996, doi:10.3233/icg-1996-19102; also *Proc. 1996 ACM Computer Science Conference* (CSC '96) pp. 131-138, doi:10.1145/228329.228345 | All processors start at the root on a shared TT; each entry counts the processors currently searching its node, so a thread can defer moves another thread is on. CPW: about 30% faster inside a recursive NegaScout than a non-recursive search. Used by Frenchess on a 128-processor Cray T3D (WCCC 1995). | metadata; content via CPW | REFERENCE ONLY |
| M. G. Brockington, "A Taxonomy of Parallel Game-Tree Search Algorithms", *ICCA Journal* 19(3):162-174, 1996. doi:10.3233/icg-1996-19303 | Classifies parallel algorithms by how control is distributed and where parallelism and synchronisation happen (CPW reproduces the table). | metadata | REFERENCE ONLY |
| R. M. Hyatt, "The Dynamic Tree-Splitting Parallel Search Algorithm", *ICCA Journal* 20(1):3-19, 1997. doi:10.3233/icg-1997-20102 | DTS: an idle processor may join any node of any active subtree. Best reported speedups of its time; very hard in a recursive search (research.md entry, 2026-10-23). | metadata (research.md has the entry) | REFERENCE ONLY |
| J. W. Romein, H. E. Bal, J. Schaeffer, A. Plaat, "A performance analysis of transposition-table-driven work scheduling in distributed search", *IEEE TPDS* 13(5):447-459, 2002. doi:10.1109/tpds.2002.1003855 | Distributed search where work moves to the machine that owns the position's TT entry. Relevant only to clusters. | metadata | REFERENCE ONLY |
| R. M. Hyatt, T. Mann, "A Lockless Transposition-Table Implementation for Parallel Search", *ICGA Journal* 25(1):36-39, 2002. doi:10.3233/icg-2002-25104 | Store the key XORed with the data next to the data; a reader re-XORs and compares, so a torn entry almost always reads as a miss instead of corrupt data (CPW "Shared Hash Table"; CPW credits Harry Nelson with the idea). | metadata; content via CPW (author's page failed, research.md) | REFERENCE ONLY |
| E. F. Østensen, *A Complete Chess Engine Parallelized Using Lazy SMP*, M.Sc. thesis, University of Oslo, 2016 | Abstract only: an engine of about 2238 estimated Elo, whose Lazy SMP doubled search speed with 4 threads. Full text refused (HTTP 403 from the repository's download service). | abstract (NVA record) | REFERENCE ONLY |

### 2.2 Measurements (forum and engine reports)

| Source | Setup | Result |
|---|---|---|
| Homan, EXchess (2013-01-12, t=46858) | Gauntlet of 10 opponents, 6s+0.1s; time to depth 12 over 317 positions | Elo over 1 thread: 2 threads +70 ± 18, 4 threads +140 ± 16, 1 thread at double time +105 ± 18. Time to depth 0.305 s (1 thread), 0.233 s (2), 0.185 s (4): far below the Elo gain. In a reply, Jörg Oster's Stockfish runs (699 games each) gave 4 threads +74 and 1 thread at double time +78. |
| Laskos (2015-04-16, t=56019) | 150 positions, 1 to 8 threads; time to depth (TTD), nps, and fixed-depth 8-vs-1 matches | TTD at 8 threads: Zappa (DTS) 5.62, Stockfish (YBWC) 4.76, Houdini (YBWC) 4.13, Cheng (Lazy) 2.42, Andscacs (Lazy) 1.54, Komodo 1.83. Nps at 8 threads: 5.60 to 7.23, Lazy SMP engines highest. Fixed-depth widening: §1.3. Adam Hair's replies: median TTD speedups at 8 cores from 0.99 to 5.58 across the engines he tested, and Stockfish (then YBWC) at 1 core with 4x the time scored even against 8 cores (2000 games), an effective speedup of about 4. |
| fastgm and Laskos (2016-11, t=62146) | Stockfish 8 (Lazy SMP), 3,000 games each | 2 threads at half time against 1 thread at full time: the single thread was about 6 ± 5 Elo ahead; Laskos converted that to an effective 2-thread speedup of about 1.91, and a 4-thread follow-up to about 3.52. These are his estimates from self-play doubling values. |
| Österlund, Texel (2017-08-06, t=64824) | AWS 2-socket Xeon, 32 cores / 64 hyperthreads, 2 NUMA nodes; games at 24s+0.24s, 1,000 to 2,000 games, ±4 to 6 Elo | Nps over 1 thread: 2.01x (2), 4.00x (4), 7.94x (8), 15.72x (16), 30.78x (32), 36.54x (64 threads on 32 cores). Hash size barely changed nps. Elo per doubling of **time**: +112, +100, +85, +72, +63; per doubling of **cores**: +72, +76, +73, +66, +44 (1 to 32 cores). With a very small TT the core doublings fell much more than the time doublings, so a small TT hurts thread scaling most. Lazy SMP was about 12 Elo weaker than Texel's older SMP at 16 cores. |
| Grant, Ethereal NNUE (2020-12-30, t=76190) | Self-play, 10s+0.1s (the post also says 10s+0.01s) | 2 vs 1 thread +86 (1,000 games), 4 vs 2 +76 (1,000), 8 vs 4 +63 (2,500). He argued that falling margins at high strength come from rising draw rates, not from NNUE scaling worse. |
| Stockfish wiki "Useful data", Threading efficiency (date, version and hardware not stated) | Fixed node budgets ("nodestime"): how many more nodes the threaded side needs to match the serial side | At 64 threads and a 240+2.4 Mnodes budget the threaded side needs about twice the nodes (efficiency about 50%), and efficiency rises with the budget. Extrapolated (the page calls it a leap of faith) to TCEC-sized budgets: 80% or more at over 300 threads, **provided nps scales with threads**. Older games: 8 vs 1 thread at 60+0.6 +178.6 ± 14.0 against +217.9 ± 15.8 for 8x the time (about 82%); at 10+0.1 about 83%. |
| Stockfish ecc5ff66 (2015-10-06) | Lazy SMP against Stockfish's own YBWC | Non-regression [-3, 1] passed at LTC with 3 threads and at STC and LTC with 7 threads, but **failed at STC with 3 threads**. Fixed games at 20 threads: +44.75 ± 7.6 at LTC and +28.01 ± 6.7 at 120 s. |
| Stockfish PR #5285 (2024-05, vondele's comment) | 60 s search from the start position, 40 GB hash | Dual-socket machine with 8 NUMA domains, 256 threads: nps 2.70x higher with NUMA binding and replicated network weights than without, about equal to running under `numactl --interleave`. Quad socket, 4 domains, 288 threads: 1.86x (1.13x against `numactl --interleave`). A table in the thread (one process on all cores against separate per-node processes, summed) shows the gap widening over 2023-2024 as the networks and accumulator caches grew. |
| Stockfish 1a67ccc7 (2025-12-23) | Correction history shared between threads | Passed at 1 thread (non-regression), 8 threads (STC, LTC), 64 threads (two LTC runs) and a 256-thread NUMA test. Sharing one table across NUMA nodes cost about 40% nps in the author's 256-thread test, so it uses one table per node (about 6% nps cost). |
| Stockfish f9b002cf (2026-06-14) | Continuation history shared between threads | Passed at 8, 16 and 64 threads; nps fell about 4% (4x70-core machine) and 6% (8x32), which the author attributes to false sharing. |

### 2.3 What the measurements say, taken together

1. Lazy SMP's nps scales almost linearly to the core count, and less well on
   SMT siblings (Österlund's 64 threads on 32 cores).
2. Its time to depth is poor, but its Elo per doubling of cores is close to
   the Elo per doubling of time: about 82-83% of the time-equivalent at 8
   threads (Stockfish wiki), effective speedups of about 1.9 at 2 threads
   and 3.5 at 4 (Laskos's estimate for Stockfish 8).
3. Efficiency falls with more threads and rises with the search budget, so
   short-TC tests understate it (Stockfish wiki; KB T54's PR #1972 note).
4. At hundreds of threads on several sockets, memory placement dominates:
   the nps lost to cross-node traffic can be several-fold (PR #5285).
5. A small TT hurts thread scaling more than time scaling (Österlund).
6. Elo gains per doubling shrink toward high strength in self-play, partly
   from draw rates (Grant). Absolute Elo per thread count is engine- and
   condition-specific. Fork must measure its own.

### 2.4 First implementations in recent OpenBench engines (2025-2026)

Added at the coordinator's request (2026-11-15) from the engines' public
PR descriptions and commit messages. These are small engines' self-play
results at short TCs; they show what a first Lazy SMP and its early fixes
are worth, not TCEC-scale behaviour.

| Engine (licence) | Change | Result as posted |
|---|---|---|
| Tarnished (GPL-3.0) #28, 2025-05-30 | "Fix SMP scaling (somewhat)" | 2 vs 1 thread SPRT passed, +76.5 ± 14.9 (8+0.08); 4 vs 1 fixed games +102.4 ± 11.9 |
| Tarnished #65, 2025-06-29 | "Smp Fix" | 1-thread non-regression passed; 2 vs 2 threads against the previous version +62.1 ± 12.4; 2 vs 1 +75.5 ± 11.7 |
| Tarnished #136, 2025-12-30 | "SMP Rewrite": fixes helper threads writing results of **aborted** searches into the TT; removes thread voting for now (non-regression at 2 threads); starts and stops the threads at a **barrier** (inspired by Clockwork's SMP); stops re-allocating the search stack and accumulators | +14.48 ± 5.19 at 2 threads and +20.08 ± 6.03 at 4 threads (8+0.08, gainer SPRTs), for the whole bundle; the parts were not measured separately |
| Hobbes (MIT) #394, 2026-06-27 | first multi-threaded search ("a very naive impl") | 1-thread non-regression passed; 2 vs 1 +65.9 ± 6.1, 4 vs 1 +135.9 ± 7.3 (8+0.08, 8 MB Hash) |
| Hobbes #396, 2026-06-30 | helper threads stop checking time management | non-regression passed at 2 threads |
| Hobbes #397, 2026-06-30 | thread voting | +5.02 ± 3.25 at 8 threads, 5+0.05 |
| Hobbes #401 and #411, 2026-07 | SPSA tunes run with 4 threads at 20+0.2 (per the PR titles) | each passed a 4-thread gainer SPRT (+4.51 ± 3.01, +4.65 ± 3.05) **and** a 1-thread non-regression SPRT at 40+0.4 (+4.76 ± 3.85, +4.41 ± 4.22) |
| Hobbes #425, 2026-08-19 | bug fix "since introducing SMP" | a `position` command arriving before the previous search had ended was skipped, so the engine played the previous search's move: an illegal move |
| Raphael (AGPL-3.0) #92, 2026-04-11 | Lazy SMP | 1-thread non-regression passed (40+0.4); 2 vs 1 +73.3 ± 6.2, 4 vs 1 +135.3 ± 5.8 (8+0.08) |
| Raphael #160, 2026-07-18 | "smp tune" (the PR does not state the tuning conditions) | passed an 8-thread LTC gainer SPRT (+7.60 ± 4.07, 20+0.2) and a 1-thread LTC gainer SPRT (+3.27 ± 2.39, 40+0.4) |
| Raphael #153, 2026-06-25 | pins threads to NUMA nodes | no result posted |
| RubiChess (GPL-3.0) 9d92aad6, 2025-10-01; 97d60cd1, 2025-11-10 | NUMA support for Linux (each thread allocates its own position object; libnuma allocation; randomised first node), then **disabled** | the disabling commit says only that it worked badly at TCEC; no measurement or cause given |

What they add to §2.3:

- A plain first version gains roughly +65 to +76 Elo at 2 threads and +100
  to +136 at 4 threads over one thread at 8+0.08 in these engines, and
  early fixes brought further gains (Tarnished).
- Tuning under SMP conditions did not cost one-thread strength in Hobbes or
  Raphael, unlike Halogen #778 (KB T54: 4-thread SPSA cost 3 to 7 Elo at
  one thread). The evidence is mixed; Fork's tuning stays at one thread
  unless its own test says otherwise.
- NUMA code that is not tested on TCEC-class hardware can lose (RubiChess),
  which supports keeping it behind a switch and measuring it there.

---

## 3. Best practices (concepts only)

### 3.1 Thread roles

- **Main thread:** runs the UCI-facing search: prints `info` lines,
  checks the clock, decides when to stop, and reports `bestmove`. Helpers
  print nothing.
- **Helpers:** run the same search on their own copy of the position and
  stop when a shared flag is set.
- Engines differ on whether a helper's result can replace the main
  thread's. EXchess (2013) ignored helper results. Texel lets a helper that
  finishes an iteration first hand its score to the main thread (t=64824).
  Grant (Ethereal) reported that "pick the best thread" never worked for
  him and that he listens only to the main thread; Wasp lets only the
  master update the global score and PV (t=68154). Stockfish and several
  OpenBench engines later adopted voting (KB T53).
- Only one thread should read the OS clock (time-management.md: Reckless
  #707 and #797; Hobbes #396 removed time checks from helpers with no
  loss, §2.4).
- **Lifecycle:** start and stop all threads together at a barrier, keep
  the threads alive between searches, and allocate their stacks and
  accumulators once, not per search (Tarnished #136, §2.4).

### 3.2 Depth schemes for helpers

Options and evidence are in KB T54 (search-techniques.md §3.32). In short:

- **None:** every thread runs its own iterative deepening from depth 1 and
  relies on nondeterminism and per-thread tables.
- **Depth offsets:** some helpers search one ply deeper (EXchess, Cheng,
  Texel). Österlund suggested larger offsets for some helpers when there
  are many (t=64824).
- **Skip rules:** a helper skips an iteration that a set share of the
  other threads have already reached (Grant, after Demolito; Wasp; Rodent
  reported it "really helpful" after previously gaining nothing past 16
  threads; t=68154). The shares quoted there are source examples, not
  Fork's values.
- Stockfish added and later **removed** depth skipping: the removal failed
  at short TCs but passed at 60+0.6, and the PR argued that very short SMP
  tests reward skipping (KB T54, PR #1972).
- Restarting every helper whenever the main thread finishes an iteration
  is discouraged (Grant, t=68154). Free-running helpers are the norm.

### 3.3 Per-thread versus shared data

| Data | Usual placement | Notes and sources |
|---|---|---|
| Transposition table | shared | the one structure Lazy SMP depends on (§3.4) |
| Position copy, search stack, PVs, root move list | per thread | each thread searches independently |
| History tables, killers, counter-moves | per thread (traditional) | per thread in EXchess, Texel, chess22k (t=46858, t=64824, t=68154); part of the diversity |
| Correction histories, continuation histories | **shared, per NUMA node** (recent) | Stockfish 1a67ccc7 and f9b002cf: gains at 8 to 256 threads, at an nps cost from cross-node traffic and false sharing; Caissa shared correction history first (per that commit). Updates are deliberately racy and excluded from TSan; atomics were too slow there. |
| NNUE accumulators and refresh caches | per thread | allocate after binding the thread to its NUMA node, so first touch puts them on the thread's node (Stockfish PR #5285 discussion) |
| Network weights | read-only, shared; **one copy per NUMA node** at scale | PR #5285: replicated per node; the largest single nps effect on multi-socket machines |
| Evaluation or pawn caches | either | Texel: per thread; chess22k: shared (t=64824, t=68154) |
| Node counters | per thread, summed on demand | shared counters cause cache-line contention (techniques.md §7; Hyatt, "NUMA 101") |
| Attack tables, Zobrist keys | read-only after start-up, shared | written once before any search |
| Syzygy WDL probes | shared, thread-safe in Fathom | main's DESIGN.md (Syzygy section) cites Fathom's README for this; the DTZ root probe is not thread-safe and stays on one thread |

### 3.4 The TT under concurrency

- **Lockless, self-checking entries.** Locks per entry or per region cost
  too much with millions of entries and many threads (CPW "Shared Hash
  Table"). The standard answer is the Hyatt-Mann scheme: store a check
  value derived from the key and the data, so a torn entry (words from two
  different writes) fails the check and reads as a miss.
- **C++ rules.** Two conflicting accesses to the same memory from
  different threads, at least one non-atomic and neither ordered before
  the other, are a data race, and a data race is **undefined behaviour**
  ([intro.races] ¶17 of the C++ working draft). Relaxed atomic
  operations cannot contribute to a data race (note in ¶3). So entries
  must be read and written through atomic operations (relaxed ordering is
  enough, since the check value catches tearing), not plain loads and
  stores.
- **Why it matters in practice.** In a 2013 thread, Rein Halbersma showed
  how an optimiser that assumes single-threaded code could merge or
  repeat loads so that the check passes on one load and the data used
  comes from another; the user "syzygy" made the same point about
  re-loading. The practical rule: **load each entry word exactly once into
  locals, verify, then use only the locals** (t=50388).
- **Validate the TT move** before playing it (it can come from a
  colliding or torn entry). Martin Sedlak's first advice for random SMP
  crashes (t=63454).
- **Never store an aborted search's result.** A search cut off by the stop
  flag returns a meaningless score; a thread that stores it poisons the
  table for every other thread. Fixing exactly this in helper threads was
  part of Tarnished's +14.5 / +20.1 rewrite (#136, §2.4).
- **Replacement under SMP:** many threads write the same buckets; the
  same replacement rules apply, but the table fills faster (§3.10).

### 3.5 Node counting and stop signalling

- Each thread counts its own nodes. The main thread sums them for `info
  nodes`, `nps` and node limits. Counters written by different threads
  must not share a cache line (Hyatt, "NUMA 101": keep them 64 bytes
  apart).
- One shared atomic stop flag. Only the main thread checks the clock and
  sets it; helpers only poll it (time-management.md; Reckless #707 stopped
  helper threads polling the clock, and #797 fixed multithreaded time
  checks, +6.1 at 8 threads).
- `go nodes N` with many threads: the total across threads is the usual
  reading, and it cannot be deterministic. Fixed-node testing stays at one
  thread (§3.11).

### 3.6 Choosing the move

See KB T53 (search-techniques.md §3.31): main thread only, best single
thread, or depth- and score-weighted voting, with special rules for mate
and tablebase scores, and only completed iterations compared. The effect
depends on the thread count (Stockfish's 4-thread LTC failed while the
8-thread one passed).

### 3.7 Time management with threads

Already in time-management.md: Stockfish 1982fe25 averages best-move
changes over all threads; 69204f07 re-searches the same depth late in the
budget, which mainly pays with threads, and 2e02dd79 later stopped helpers
racing to the maximum depth; Grant saw completion times vary more at 6
threads; whether node share should use the main thread's or all threads'
counts is open (**UNVERIFIED**, no comparison found).

### 3.8 NUMA

- **Placement is by first touch.** After boot the Linux default policy is
  local allocation on the node of the CPU that faults the page in, and a
  page stays where it was first placed unless migrated (kernel "NUMA
  Memory Policy"). `malloc` alone places nothing; the thread that first
  writes a page decides its node (Hyatt, "NUMA 101").
- **Bind threads to nodes, then allocate.** Bind each search thread to a
  NUMA node (Stockfish binds to nodes rather than single CPUs, so the OS
  can still schedule within the node, and fills nodes evenly), then let the
  thread allocate and first-touch its own data (PR #5285). Wasp lost almost
  half its speed in a TCEC submission because a per-thread array was
  allocated and first touched by one thread (t=68154).
- **Replicate read-only hot data per node:** the network weights above
  all (PR #5285: 2.70x nps on a 256-thread, 8-domain machine).
- **Spread the shared TT:** have threads on each node clear their share of
  the table, so its pages are spread across nodes (Hyatt). Huge pages keep
  each 2 MiB (or 1 GiB) page on one node, so the spread is at that
  granularity (Hyatt). Texel allocated its TT on node 0 if it fit, and
  noted that skipping depth-0 TT probes on remote nodes might cost Elo
  (t=64824).
- **Do not rely on automatic NUMA balancing.** Österlund measured Texel at
  16 threads on a 2-node machine: about 14% more nps with the engine's own
  NUMA handling, no gain from the kernel's automatic balancing, and much
  less run-to-run variation (Hyatt, "NUMA 101" thread).
- **Respect the process's affinity mask** (a user's `taskset` or
  `numactl`), and drop empty nodes (PR #5285 and its follow-up comment).
- **Windows:** processor groups of up to 64 logical processors; affinity
  across groups only from Windows 11 / Server 2022 (PR #5285; KB
  techniques.md §7). Local testing only; TCEC runs Linux.

### 3.9 Large pages

- TCEC's CPU server has transparent huge pages in **madvise** mode (TCEC
  "Further information", revision 9615, 2026-11-09), so a mapping gets
  huge pages only if the engine asks for them. Fork's Hash already does
  (`madvise(MADV_HUGEPAGE)`, DESIGN.md `Hash` row).
- Stockfish uses large pages automatically and falls back to normal pages
  (Stockfish wiki "Advanced topics"). Never depend on them (KB README
  finding 5).
- Whether huge pages for the per-thread tables or the network weights
  would also help is **UNVERIFIED** (no measurement found).

### 3.10 Hash size

- More threads fill the TT faster. Stockfish's FAQ scales the recommended
  Hash with the thread count, and its measurements suggest keeping average
  `hashfull` below about 30% (Stockfish FAQ; "Useful data", Elo cost of
  small Hash).
- Österlund: a too-small TT hurts core scaling more than time scaling
  (§2.2).
- At TCEC the Hash is 256 GiB with multithreaded initialisation (§5), so
  the table is large; the open TT-policy questions parked "until Phase 6"
  (engineering review W2) become testable only with many threads and long
  searches.

### 3.11 Determinism and how engines test SMP

- **Determinism is lost** with more than one thread: node counts, PVs and
  even moves differ between runs. Keep the one-thread search bit-for-bit
  deterministic, so bench and fixed-node tests still mean something.
- **Stockfish (fishtest):** ordinary tests are single-threaded; SMP tests
  run at exactly 8 threads and are part of the monthly regression tests
  and pre-release testing; "scaler" patches are tested at 60+0.6 with 8
  threads (or 70+0.7 with 7) (fishtest wiki "Creating my first test";
  Stockfish wiki "Regression Tests": 8 threads at 60+0.6 since
  2023-06-29). Changes that touch SMP are tested at several thread counts
  (1a67ccc7: 1, 8, 64, 256).
- **OpenBench:** an SMP test is an ordinary test with `Threads=N` in the
  engine options; the worker then plays fewer games at once (concurrency
  is the worker's threads divided by the larger thread count) (OpenBench
  wiki, "SPRT and Fixed-Game Workloads", "Workload Assignment").
  Reckless runs SMP tests before every release (competition.md).
- **Scaling tests:**
  - N threads against 1 thread at N times the time (fastgm, Stockfish
    wiki): the share of the time-odds gain that threads recover.
  - Equivalent node budgets (Stockfish wiki): how many more nodes the
    threaded side needs to match the serial one.
  - Elo per doubling of threads next to Elo per doubling of time
    (Österlund).
  - Nps against threads, and time to depth, as diagnostics only: time to
    depth misled Homan (part 3) and understates widening.
- **Time control:** avoid ultra-short TCs for SMP decisions (KB T54, PR
  #1972; ecc5ff66's STC 3-thread failure against its LTC pass).
- **Tuning under SMP:** Hobbes and Raphael ran SPSA under multi-thread
  conditions and the results also passed at one thread; Halogen's did not
  (§2.4; KB T54). If Fork ever tunes with threads, it checks one thread
  too.

---

## 4. Pitfalls

### 4.1 Data races, and catching them

- **ThreadSanitizer (USE):** compile and link everything with
  `-fsanitize=thread`; it costs about 5-15x in time and 5-10x in memory;
  uninstrumented code can hide races or cause false reports; static libc
  is not supported (clang ThreadSanitizer documentation).
- TSan finds UCI-layer races that rarely crash: Stockfish's 2017 fix of a
  non-atomic ponder field written by the input thread and read by the
  search thread came from a sanitized run of a ponder/ponderhit script
  (5410424e).
- Keep suppressions narrow and documented. Stockfish removed a suppression
  once its race was fixed (7e897a64), and documents the history updates it
  leaves racy on purpose (1a67ccc7).
- Classic sources of SMP bugs from the 2017 "How to find SMP bugs?"
  thread (t=63454): `static` locals, unvalidated TT moves, master-helper
  communication between iterations; tools suggested were stack traces of
  every thread, assertions on move legality, the thread sanitizer, and
  switching the TT off to bisect.

### 4.2 False sharing and contention

- Any per-thread counter or flag that shares a 64-byte line with another
  thread's writes bounces the line between cores (Hyatt). Pad or separate
  them.
- Shared tables that many threads write (shared histories) lose nps to
  false sharing (Stockfish f9b002cf: about 4-6%).
- An atomic increment of one shared node counter per node would serialise
  every thread on one cache line (techniques.md §7).

### 4.3 Misleading benchmarks

- A test-suite time-to-depth gain can hide a strength loss (Homan part 3:
  a bug that dropped the hash move in half the threads looked like a
  speedup). Decide with games.
- Short-TC SMP results can point the wrong way (§3.11).

### 4.4 UCI and thread lifecycle

- `Threads` changes: re-create the thread pool and each thread's tables
  outside any search, and (with NUMA) re-bind; Stockfish re-creates its
  threads and TT when the NUMA policy changes (PR #5285) and recommends
  setting Hash after Threads (Stockfish wiki, UCI page).
- `stop`, `ponderhit` and `quit` must reach every thread: one stop flag
  for all, one pondering flag read by the main thread, every thread joined
  or parked before `bestmove`; exactly one `bestmove` per `go`.
- A `position` (or `ucinewgame`, `setoption`) that arrives while threads
  are still finishing must wait for them, not be dropped: Hobbes played an
  illegal move because a `position` command was skipped during a search's
  wind-down (#425, §2.4). Fork's session already stops and joins its one
  search thread on these commands; the pool must keep that guarantee.
- **Thread start latency:** creating and joining hundreds of threads on
  every `go`, or allocating per-thread tables per search, adds latency to
  every move. A persistent pool of parked threads avoids it. This is
  Fork's engineering inference; no measurement of the cost at 512 threads
  was opened (**UNVERIFIED** magnitude).
- Hash clearing at `ucinewgame` with many threads is already parallel in
  Fork; with NUMA it doubles as the TT's placement step (§3.8).

### 4.5 Reproducibility

- SMP crashes rarely reproduce (t=63454). Keep a one-thread mode that is
  fully deterministic, log enough (thread count, Hash, position, `go`
  line) to replay a game position, and run the same scenario many times
  under TSan rather than once.

### 4.6 Scale-specific traps

- **NUMA misplacement** (§3.8): up to several-fold nps loss on
  multi-socket machines.
- **Per-thread memory times 512:** Fork's pair tables alone are 2.25 MiB
  per searcher (docs/research/tcec-hardware-test-plan.md entry 2), about
  1.1 GiB at 512 searchers. The EPYC 9754 has 256 MB of L3 per 128-core
  socket (AMD product page), about 2 MB per core, so per-thread tables no
  longer fit in cache as they do on the development PC.
- **SMT:** TCEC's 512 threads are 256 cores with two hardware threads
  each. Per-thread nps drops on SMT siblings (Österlund: 64 threads on 32
  cores gave 36.5x, not 64x). The Stockfish FAQ calls SMT beneficial.
  Grant cites a 192-core versus 384-thread test at about +20 Elo per
  doubling, but that test was not opened (**UNVERIFIED**, second-hand).
- **Helpers racing ahead** in depth when the main thread repeats a depth
  (time-management.md, 2e02dd79).

---

## 5. TCEC specifics

- **Hardware (TCEC "Further information", revision 9615, last edited
  2026-11-09):**
  - CPU server (S28 onward): 2x AMD EPYC 9754 (256 cores / 512 threads),
    768 GiB DDR5, Ubuntu 22.04, gcc 11.4.0, g++-12 12.3.0, clang 16.0.0
    and 19.1.7. Transparent huge pages in `madvise` mode. The listed CPU
    flags include `avx512f`, `avx512bw` and `avx512_vnni` (this also
    confirms, from TCEC's own page, the owner's 2026-11-08 answer to
    competition.md open question 8).
  - GPU server: 2x AMD EPYC 9175F (32 cores / 64 threads), 8x RTX 5090.
  - Up to 512 threads per engine; up to 256 GiB of Hash if its
    initialisation is multithreaded, else 32 or 64 GiB; all engine RAM
    capped at 320 GiB, and the page notes that threads have their own RAM
    use. "Large pages are automatically in use."
  - The live Swiss 10 game used `Threads=512` and `Hash=262144`
    (competition.md, 2026-10-23).
- **EPYC 9754 (AMD product page):** 128 cores / 256 threads per socket,
  256 MB L3, 12 memory channels, 460.8 GB/s per socket, launched
  2023-06-13.
- **NUMA layout: UNVERIFIED.** TCEC's page does not state how many NUMA
  nodes the CPU server exposes (`config/tcec.json`: `numa_nodes: null`).
  The AMD product page does not list NUMA modes. Stockfish's PR #5285
  measured a dual-socket machine with 8 NUMA domains, so 2 to 8 nodes are
  all plausible for this class of machine. Fork must detect the layout at
  run time rather than assume one; the question belongs on competition.md's
  TCEC question list.
- **What top engines report at this size:**
  - Stockfish: the wiki's extrapolation (80% or better efficiency above 300
    threads at TCEC budgets, if nps scales); PR #5285's several-fold nps
    gain from NUMA handling on 256-288 threads, and a contributor tying a
    TCEC slowdown to cross-node traffic from bigger networks and caches;
    shared correction history tested at 256 threads (1a67ccc7).
  - Reckless: NUMA-aware threads in v0.9.0 (+71 Elo SMP against v0.8.0),
    multithreaded TT init and NUMA binding in place before its Superfinal
    run (competition.md).
  - Earlier TCEC entries hit the same problems: chess22k asking how to use
    44 cores, and Wasp's NUMA placement bug (t=68154).
  - RubiChess added Linux NUMA support in October 2025 and disabled it in
    November 2025 because it worked badly at TCEC (commit message only;
    the cause is not given; §2.4).

---

## 6. Fork's situation (read at origin/phase-4, 69e1080; read-only)

### 6.1 What exists

| Item | State at 69e1080 | Where |
|---|---|---|
| Search threads | One `Searcher` and one search thread per `go`. The thread is created in `go` and joined at `stop`. `Threads` (1 to 4096) is accepted, but only sets the Hash clear's workers, and an `info string` says so. | `src/uci/session.cpp` (Threads option; `go`; `stop_search`) |
| Per-thread state | `Searcher` owns all search state: stack frames, PVs, root moves, butterfly, pair (reply/follow), take and threat-bucket histories, the drift tables (Fork's correction-history equivalent), LMR history centres, node counter, NNUE feature stack (accumulators) and, per DESIGN, the per-thread refresh cache. `deliberate()` never allocates. | `src/search/searcher.hpp` |
| Network weights | Read-only, reached through a pointer, shared by design. | `searcher.hpp` (`net_`) |
| TT | 64-byte buckets of five 12-byte entries; each entry's check is the key's 24 bits XORed with a digest of all its other fields, so a torn entry reads as a miss. Plain (non-atomic) accesses; the header says Phase 6 must make them relaxed atomics and add the torn-write stress test under TSan. | `src/search/trans_table.hpp` |
| Hash memory | One block from the OS, `madvise(MADV_HUGEPAGE)`, cleared in parallel slices by `min(Threads, size-based cap)` workers; no NUMA placement. | `src/search/hash_memory.cpp` |
| Stop and clock | Every 1,024 nodes the searcher reads the stop flag and the pondering flag (relaxed atomics) and checks the hard time limit itself. | `searcher.cpp` (`poll_limits`) |
| Time management | Soft and hard limits, best-move stability and node share from the searcher's own root-move node counts. | `time_budget.*`, `searcher.cpp` |
| Syzygy | WDL probes in search through Fathom (thread-safe); the DTZ root probe runs once per search on the search thread and is not thread-safe; its result is held in a file-scope object. | `src/search/endgame_tables.cpp`; DESIGN §5.2 |
| Other shared state | A quick scan found file-scope tables written once at start-up (attack tables, Zobrist keys) besides the Syzygy root result. A full audit of mutable global state is part of the work (not done here). | `src/core/*.cpp` |
| Sanitizers and CI | `clang-tsan` and `gcc-tsan` presets (Linux); `.github/workflows/tsan.yml` runs every fast suite under both; per CLAUDE.md the full TSan suites run when threads, the TT or the UCI layer change, and "TSan, threaded suites" on every code change. `no_alloc` is not built under TSan. | `CMakePresets.json`, `CMakeLists.txt`, workflows |
| Bench | One thread, 16 MB Hash, fixed depth, deterministic; a `FORK_NODE_CLOCK` build turns time into a node count for deterministic timed tests. | DESIGN §5.2; `searcher.cpp` |
| Plans already written | DESIGN §5 Phase 6 (TT atomics and torn-write stress test; the move-agreement and diversity choices from T53 and T54; memory per thread); roadmap row 17a (bench parity at Threads=1, TSan suites, a scaling curve, 2-vs-1 and 8-vs-4 matches; revisit the pair tables' colour fold); tcec-hardware-test-plan.md (nps and memory at 1 to 512 threads, one CCX pinned, NUMA). | main's DESIGN.md; docs/research/ |

### 6.2 What Lazy SMP needs (gap list)

1. A persistent pool of N searchers, created and sized when `Threads`
   changes (outside any search), each owning its position copy and tables.
2. Atomic TT entry access (the planned relaxed atomics), with each entry
   loaded once, verified, then used from locals (§3.4).
3. One stop flag for all threads; only the main thread reads the clock and
   the pondering flag's effect on time.
4. Per-thread node counters, readable by the main thread, on separate cache
   lines; `info nodes`, `nps` and node limits from the sum.
5. A root move list prepared once by the main thread (Syzygy DTZ
   filtering, `searchmoves`) and copied to every helper before it starts.
6. The move-choice rule (T53) and the diversity rule (T54).
7. NUMA: thread binding, per-node network copies, TT spread across nodes
   (a later step; §6.3 item 9).
8. A review of global mutable state and of the UCI signals under TSan with
   many threads.

### 6.3 A suggested minimal first version (suggestions, not decisions)

Each item is a suggestion for the Phase 6 / 17a spec. Any constant it
needs follows the constants policy (recorded justification, screen before
commit), and any new name goes through the name screen (DESIGN §8).

1. **Pool.** Thread 0 is today's search thread with its current output and
   time logic. Threads 1 to N-1 are parked helpers woken per `go`, each
   with its own `Searcher` built when `Threads` changes, never during a
   search, so `deliberate()` stays allocation-free.
2. **Helpers search silently**: same root moves, same search, no output,
   no clock reads, stop on the shared flag.
3. **No depth offsets or skip rules in v1.** Diversity from timing and
   per-thread histories only. The simplest design to make correct; T54's
   options become separate SPRTs afterwards.
4. **The main thread's result is played.** Voting (T53) is a separate
   SPRT afterwards.
5. **Histories stay per thread**, as now. Shared drift (correction)
   tables are a later idea, after Stockfish 1a67ccc7, measured at high
   thread counts only.
6. **TT:** relaxed atomic word accesses plus the existing digest check;
   the torn-write stress test from DESIGN §5.
7. **Node counts:** one counter per searcher, written only by its owner
   (a relaxed atomic store, so the main thread's reads are not a race),
   padded to its own cache line.
8. **Threads=1 must take today's path exactly**, so bench, fixed-node
   tests and every Phase 4 result stay comparable (bench node count and
   signature unchanged).
9. **Aborted searches store nothing:** a stopped search returns without
   any TT store, in every thread. Fork's searcher already returns at once
   after a stop at each move loop (`searcher.cpp`; read, not tested); the
   spec should state it and a test should check it.
10. **Threads start and stop together** (a barrier or equivalent) and are
    parked, not re-created, between searches (item 1; Tarnished #136).
11. **NUMA in v1:** none beyond letting each helper allocate and first-touch
   its own tables on its own thread (cheap, and right by default). Binding,
   per-node network copies and a node-aware TT clear come in v2, decided by
   the TCEC-hardware measurements in tcec-hardware-test-plan.md.

### 6.4 Tests that would prove it (suggestions)

| Test | What it proves | Notes |
|---|---|---|
| Bench at Threads=1 | no functional change for one thread | node count and signature equal to `tests/bench.ref` |
| TT torn-write stress test under TSan | concurrent TT access is race-free and every accepted hit is one writer's complete entry | DESIGN §5 Phase 6 plan |
| Session test under TSan with Threads = 2, 4, 8, 16 | `go`/`stop`/`ponderhit`/`isready`/`quit` loops, `Threads` and `Hash` changes between searches, exactly one `bestmove` per `go` | the race class Stockfish 5410424e found |
| `uci-smoke.sh` and the compliance runs with Threads > 1 | start, stop and exit cleanly on every preset | Windows and Linux |
| Stop latency at many threads | `bestmove` arrives promptly after `stop` and at the hard limit | measured at the machine's maximum thread count |
| Scaling curve (diagnostic) | nps, time to depth and fixed-depth Elo (widening) at 1, 2, 4, 6 and 12 threads locally, 512 on TCEC-class hardware | roadmap 17a; tcec-hardware-test-plan.md |
| Thread-vs-time equivalence | N threads at time T against 1 thread at N×T | the Stockfish wiki method; shows the efficiency Fork reaches |
| SMP SPRTs | 2 vs 1 and 8 vs 4 threads (roadmap 17a), then every SMP change at 2 or more thread counts | not at ultra-short TCs (§3.11); the development PC has 12 hardware threads and the GitHub runners 4 vCPUs, so 8-thread games run one at a time locally |

---

## 7. UNVERIFIED items

1. The NUMA layout of TCEC's CPU server (number of nodes; EPYC NUMA mode).
   Not on TCEC's page or AMD's product page. To ask TCEC, and to detect at
   run time.
2. Whether aggressive pruning (low effective branching factor) is why YBW
   lost ground to Lazy SMP: a forum opinion (t=78631), not measured.
3. Østensen's thesis beyond its abstract (download refused, HTTP 403).
4. The content of the 1982, 1989, 1996, 1997 and 2002 papers beyond CPW's
   descriptions: only their Crossref metadata was opened.
5. Grant's cited 192-core versus 384-thread hyperthreading result (about
   +20 Elo per doubling): second-hand, the test itself not opened.
6. The cost of thread creation and per-search allocation at 512 threads
   (§4.4): Fork's inference, not measured.
7. Whether huge pages for per-thread tables or network weights help.
8. Whether node share should use the main thread's or all threads' counts
   (time-management.md, still open).
9. The "NPS=4" in Stockfish 1a67ccc7's 40% figure reads as the BIOS's
   NUMA-nodes-per-socket mode, but the commit does not say so.
10. The Stockfish wiki's threading-efficiency figures carry no date,
    Stockfish version or hardware.
11. CPW says Stockfish 7 (January 2016) was the first release with Lazy
    SMP; the release itself was not opened here (the commit, 2015-10-06,
    was).
12. The tuning conditions of Raphael #160 ("smp tune"): the PR states only
    the SPRT results, so the thread count used for the SPSA is not
    confirmed. Hobbes's thread count and TC (4 threads, 20+0.2) come from
    its PR titles.
13. Why RubiChess's NUMA support "worked badly" at TCEC: not stated.
14. Which of Tarnished #136's four changes produced its gain: measured
    only as a bundle.

---

## 8. Sources (all opened 2026-11-15)

| Title | Author | URL | Used for |
|---|---|---|---|
| Lazy SMP | CPW | https://www.chessprogramming.org/Lazy_SMP | §1, forum post list, thesis listing (page contains code; not used) |
| Parallel Search | CPW | https://www.chessprogramming.org/Parallel_Search | taxonomy, scaling-thread list (first 100,000 characters read) |
| Shared Hash Table | CPW | https://www.chessprogramming.org/Shared_Hash_Table | lockless TT, history |
| ABDADA | CPW | https://www.chessprogramming.org/ABDADA | §2.1 |
| Young Brothers Wait Concept | CPW | https://www.chessprogramming.org/Young_Brothers_Wait_Concept | §2.1 |
| NUMA | CPW | https://www.chessprogramming.org/NUMA | §3.8 (general only), forum list |
| Lazy SMP, part 2 | Daniel Homan (2013-01-12) | https://talkchess.com/viewtopic.php?t=46858 | §1.2, §2.2 |
| Lazy SMP, part 3 | Daniel Homan (2013-03-09) | https://talkchess.com/viewtopic.php?t=47455 | §1.2, §4.3 |
| Lazy SMP and Work Sharing | Daniel Homan (2013-07-03) | https://talkchess.com/viewtopic.php?t=48536 | §1.2 |
| How could a compiler break the lockless hashing method? | Rein Halbersma and replies (2013-12) | https://talkchess.com/viewtopic.php?t=50388 | §3.4 |
| Empirical results with Lazy SMP, YBWC, DTS | Kai Laskos and replies (2015-04-16) | https://talkchess.com/viewtopic.php?t=56019 | §1.3, §2.2 |
| NUMA 101 | Robert Hyatt and replies (2016-01-07) | https://talkchess.com/viewtopic.php?t=58830 | §3.5, §3.8, §4.2 |
| Stockfish 8 - Double time control vs. 2 threads | fastgm, Kai Laskos (2016-11-15) | https://talkchess.com/viewtopic.php?t=62146 | §2.2 (first fetch: connection reset; second succeeded) |
| How to find SMP bugs ? | Lucas Braesch and replies (2017-03-15) | https://talkchess.com/viewtopic.php?t=63454 | §3.4, §4.1, §4.5 |
| Lazy SMP and lazy cluster experiments | Peter Österlund (2017-08-06) | https://talkchess.com/viewtopic.php?t=64824 | §2.2, §3.2, §3.3, §3.8 |
| Lazy SMP and 44 cores | Sander Maassen vd Brink and replies (2018-08-07) | https://talkchess.com/viewtopic.php?t=68154 | §1.2, §3.1-§3.3, §3.8 |
| Dispelling the Myth of NNUE with LazySMP | Andrew Grant and replies (2020-12-30) | https://talkchess.com/viewtopic.php?t=76190 | §2.2, §4.6 |
| Research paper comparing various parallel search algorithms | koedem and replies (2021) | https://talkchess.com/viewtopic.php?t=78631 | §1.3 (Brockington citation; YBW opinions) |
| Crossref records | Crossref API | api.crossref.org/works (DOIs in §2.1) | §2.1 metadata |
| A Complete Chess Engine Parallelized Using Lazy SMP (record) | Emil Fredrik Østensen (2016) | https://www.duo.uio.no/handle/10852/53769 → NVA record, api.nva.unit.no/publication/019c90f3ef23-2d2c8bfe-b12f-4bfe-939f-bf305aba28cf | §2.1 (abstract); PDF links redirected, download API returned 403 |
| Lazy SMP (commit ecc5ff66) | mbootsector et al., Stockfish (2015-10-06) | https://github.com/official-stockfish/Stockfish/commit/ecc5ff6693f116f4a8ae5f5080252f29b279c0a1 | §1.2, §2.2 (message only) |
| NUMA memory replication for NNUE weights (PR #5285) and comments | Sopel97, vondele and others (2024-05) | https://github.com/official-stockfish/Stockfish/pull/5285 | §2.2, §3.3, §3.8, §4.4 (description and comments; code in them not used) |
| Stockfish 17 release post | Stockfish team (2024-09-06) | https://stockfishchess.org/blog/2024/stockfish-17/ | NumaPolicy, "up to 2.8x" |
| Share correction history between threads (1a67ccc7) | anematode, Stockfish (2025-12-23) | https://github.com/official-stockfish/Stockfish/commit/1a67ccc72ef2e3c06e9c905a793a14416d53643f | §2.2, §3.3 (message only) |
| Share continuation history between threads (f9b002cf) | anematode, Stockfish (2026-06-14) | https://github.com/official-stockfish/Stockfish/commit/f9b002cf7db4a6ec53dd5f06d72601638e326b82 | §2.2, §4.2 |
| Fix a race on Limits::ponder (5410424e); Remove race suppression (7e897a64) | Joost VandeVondele, Stockfish (2017) | github.com/official-stockfish/Stockfish/commit/{5410424e, 7e897a64} | §4.1 |
| Stockfish commit search ("false sharing", "thread sanitizer", "data race", "nodes counter") | GitHub search | gh search commits, repo official-stockfish/Stockfish | finding the commits above |
| Useful data | Stockfish wiki | https://github.com/official-stockfish/Stockfish/wiki/Useful-data (raw markdown) | §2.2, §3.10 |
| Stockfish FAQ; Advanced topics; UCI Protocol and Stockfish Commands; Regression Tests; wiki index | Stockfish wiki | https://github.com/official-stockfish/Stockfish/wiki (pages named) | §3.8-§3.11, §4.4 |
| UCI-&-Commands (old page name) | Stockfish wiki | https://github.com/official-stockfish/Stockfish/wiki/UCI-&-Commands | failed: no such page (editor shown); raw variants 404 |
| Stockfish README | Stockfish | raw.githubusercontent.com/official-stockfish/Stockfish/master/README.md | checked; no thread or NUMA content |
| Creating my first test | fishtest wiki | https://github.com/official-stockfish/fishtest/wiki/Creating-my-first-test | §3.11 |
| Fishtest-Testing-Guidelines, Regression-Tests (fishtest wiki) | fishtest wiki | raw wiki paths | failed: 404 |
| OpenBench README; wiki Home, SPRT and Fixed-Game Workloads, Workload Assignment, Running Your Instance Properly, Configuring Your OpenBench Instance | Andrew Grant | https://github.com/AndyGrant/OpenBench (wiki) | §3.11 (README has no SMP content; Creating-Tests and Test-Creation pages 404) |
| ThreadSanitizer | LLVM/Clang documentation | https://clang.llvm.org/docs/ThreadSanitizer.html | §4.1 |
| [intro.races] | C++ working draft | https://eel.is/c++draft/intro.races | §3.4 |
| NUMA Memory Policy | Linux kernel documentation | https://docs.kernel.org/admin-guide/mm/numa_memory_policy.html | §3.8 |
| TCEC Season Further information (revision 9615, 2026-11-09) | TCEC | https://wiki.chessdom.org/TCEC_Season_Further_information | §5 (curl with a browser User-Agent) |
| AMD EPYC 9754 | AMD | https://www.amd.com/en/products/processors/server/epyc/4th-generation-9004-and-8004-series/amd-epyc-9754.html | §4.6, §5 (fetch tool timed out; curl succeeded) |
| Tarnished releases; PRs #28, #65, #93, #94, #136 (via gh api) | Bobingstern and contributors (GPL-3.0) | https://github.com/Bobingstern/Tarnished | §2.4, §3.1, §3.4 (descriptions only) |
| RubiChess commits 9d92aad6, 0cfbbb3a, 97d60cd1; PRs #490, #507; releases (no NUMA text) | Andreas Matthies (GPL-3.0) | https://github.com/Matthies/RubiChess | §2.4, §5 (messages only) |
| Hobbes PRs #394, #396, #397, #398, #401, #411, #425, #430 (via gh api) | kelseyde (MIT) | https://github.com/kelseyde/hobbes-chess-engine | §2.4, §3.1, §3.11, §4.4 (descriptions only) |
| Raphael PRs #92, #153, #160; releases (via gh api) | Orbital-Web (AGPL-3.0) | https://github.com/Orbital-Web/Raphael | §2.4 (descriptions only) |
| Web search: "Lazy SMP" papers on arXiv | search engine | (search results only) | finding candidates; nothing relied on from snippets |
