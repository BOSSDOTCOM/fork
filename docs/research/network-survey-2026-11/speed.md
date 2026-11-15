# Network speed techniques: what the engines report, Fork's status, expected gain

Clean-room network survey of 2026-11-14 ([README](README.md)), the brief's item 4.
Every technique the 51 engines report for making the network faster, with the gain each
engine reported, Fork's status with Fork's own measurement, and an expected gain for Fork's
network on this PC and on TCEC's EPYC. The untried ones are ranked in §5.

## 1. How to read this file

- **Peers' figures** are each engine's own, under its own conditions, as the group records
  cite them (`records/group-*.md`; the group letter is given once per engine in
  [matrix.md](matrix.md)). "nps" figures are speed; "Elo" figures are SPRT point estimates at
  the time control shown, which lean high for passed tests. Stockfish's Elo figures are derived
  by the survey agent from the win/loss/draw totals in its commit messages.
- **Fork's status** comes from `docs/history/phase-4/perf-log.md` (speed sprints 1 to 4),
  `docs/ideas.md` (ideas 40 and 41) and the code comments of `src/eval/nnue/accumulator.hpp`
  and `net_file.hpp`, read on 2026-11-14 at phase-4 b7ea9bf. The speed rule: a change counts
  when median and best nps both move by more than 3% or twice the round-to-round spread; for
  a bench-identical change 1% of cycles per node also counts (DESIGN.md §7).
- **Expected gain** is my estimate, not a measurement. Its basis is stated per row: the share
  of Fork's cycles the technique can touch, Fork's own A/B where one exists, and the peers'
  figures scaled to Fork's network size. Nothing has been measured on an EPYC. Every figure in
  the two "expected" columns is **UNVERIFIED**.

### Fork's network and where its time goes

- Default net r8ceplo2, architecture 8 (S512+PP): 768 mirrored piece inputs plus 608 pawn
  links per perspective, one 512-wide SCReLU layer, 8 outputs picked by phase, int16.
- First-layer weights: 1,376 rows x 512 x 2 bytes = **1.41 MB** (0.70 MB with int8 rows);
  the output layer is 16 KB.
- Last profile (speed sprint 3, before the fused update was adopted): the network was 47.6% of
  cycles; the accumulator update 26.3%, the move push 4.7%, the output pass 3.4%; 0.524
  evaluations per node, 3.09 rows per perspective update, 10.8 frame refreshes per 1,000
  updates, 1.19 plies walked per evaluation. The fused update then removed 31.4% of all
  instructions (+14.7% nps). **The engine has not been profiled since**, so today's network
  share is UNVERIFIED (roughly 40% by that arithmetic).

### The two machines

| | This PC | TCEC |
|---|---|---|
| CPU | Ryzen 5 7600X3D (Zen 4), 6 cores, 12 threads | 2 x EPYC 9754 (Zen 4c), 128 cores and 256 threads each |
| L2 per core | 1 MB | 1 MB |
| L3 | 96 MB for the 6 cores | 16 MB per group of 8 cores (2 MB per core) |
| What Fork's tests use | 1 thread, so 1 MB of L2 and up to 96 MB of L3 to itself | 512 threads: two threads share each core's 1 MB L2; 16 threads share each 16 MB L3 |
| AVX-512 | yes (the Windows native build uses it) | yes (Zen 4c keeps Zen 4's instructions); VNNI not confirmed |

Sources and their weakness: the TCEC machine is from `config/tcec.json` and the TCEC hardware
test plan. The cache figures are from Wikipedia's Zen 4 and Epyc articles, opened 2026-11-14;
every AMD page timed out, so they are **second-hand and UNVERIFIED against AMD**. The per-core
L3 figure is my division. The repository's documents call the PC's CPU "Ryzen 7 7600X3D";
the part is listed as Ryzen 5 7600X3D.

What follows from the table: Fork's first layer (1.41 MB) does not fit a core's L2 on either
machine, and on the PC a single test thread has the whole 96 MB L3 behind it. At TCEC sixteen
threads share 16 MB, and each brings its own history tables (the pair tables alone are 2.25 MiB
per searcher, perf-log, speed sprint 4). So a technique that only reduces bytes touched can
measure nothing here and still pay there. That is the one systematic reason the two "expected"
columns differ.

## 2. Techniques that apply to Fork's present network

Status key: **have**; **tried, lost** (measured, not adopted); **never tried**.

| # | Technique | What the engines report | Fork's status | Expected, this PC | Expected, EPYC |
|---|---|---|---|---|---|
| S1 | **Lazy accumulator updates**: a ply's sums are computed only when its evaluation is needed, walking forward from the nearest computed ancestor | Lizard +29.8 at 4+0.04; Tcheran +33.1 STC; Hobbes +19.3 at 4+0.04; Minke +15.1 STC; Quanticade +14.9; Tarnished +14.7; Titan +13.1; Berserk +11.8; Obsidian +10.6; Integral +9.2; Halogen +9.2 STC, +7.7 LTC; Incipit +6% and +19% nps; Stormphrax +3.4; Viridithas 2.3% faster; Stockfish (evaluation-only form) +2.7 STC; Triumviratus +26 to +42 bundled with a PGO build. Against: Renegade −9.0 at 1 thread (+5.7 at 8 threads) until its TT prefetch was moved earlier; Berserk's first try was about −1 for the same reason; Cinder measured a gain in both directions (lazy +7.5, back to eager +3.5, lazy again +2.1) | **have** since before sprint 1 (`FeatureStack`); 1.19 plies walked per evaluation | 0 (in place) | 0 |
| S2 | **Fused updates in register tiles**: every row a move changes applied to a tile of the parent's sums held in registers, read once and stored once | Incipit +12% nps (AVX-512); Berserk +12.0; Quanticade +11.7; Minke +9.2 STC; Tcheran +10.7; Alexandria +8.2; Cinder +6.3; JustBot +5.9; Viridithas +8.9 STC; Hobbes +5.8; Ethereal tiling +9.95 STC; Stockfish tiling (2020) +10.4 STC; Halogen +2.4% nps; Reckless +2.7% nps; Stormphrax 4% faster; Coda re-tiling for a new width +3.0. Against: Renegade 5% faster locally but 0 Elo ("depends on the machine") | **have**: nnue-fused, +14.7% / +15.5% nps on x86-64-v3 (clang), +9.0% with gcc 11.4, +5.4% on the AVX-512 build | 0 (in place) | 0 |
| S3 | **No accumulator copy**: the child is written from the parent in the same pass; nothing is copied on a move or a null move | Integral +28.0; Lizard about 11% faster, +23.4; Alexandria +11.0; Quanticade +10.0; Titan +6.7; Halogen accumulator in the search stack +5.3% nps; Tcheran (accidental copies removed) +13.0; Tarnished +28.5 (512-wide net); Obsidian +7% speed; Ethereal no copy on a null move +2.3; Stockfish fixed-array stack +0.45% | **have**: the fused update reads the parent and stores the child; a null move's child is the parent's accumulator (`push_null`) | 0 | 0 |
| S4 | **Both perspectives in one pass** | Stockfish +1.7 STC (its gain is decoding the changed threats once); Caissa +0.7 to +0.8% nps; Triumviratus +0.8% nps on AVX-512; Raphael (duplicated work removed) +8.2 at 4+0.04. Against: Halogen separate sides −1.3%; Stockfish's "double incremental" update removed once its accumulator shrank to 1024 | **tried, lost**: E4, −0.6% (round 2); with E2, −0.2% | 0 to +1% | 0 to +1% |
| S5 | **Accumulator refresh cache** ("Finny table"): per king frame, the last sums and the pieces they stand for, so a refresh applies only the difference | Quanticade +28.6; Alexandria +25.9; Reckless +16.0; PZChessBot +14.9; Igel +13.8; Hobbes +13.6; Seer +10.7 STC; PlentyChess +10.0; Cinder +9.9; Integral +7.8; Berserk +7.1; Halogen +8.6; Ethereal +8.6; RubiChess +7.5 / +5.4; Raphael +6.1; Tarnished +5.8; Renegade +5.3; Incipit brought an 8-bucket net from 20% to 12% slower than no buckets; Stormphrax about 1%, "scales with more buckets". All with king buckets: RubiChess counted 34.9% full refreshes before it | **tried, lost** for the mirror frame alone: E1 −5.3% (round 2); the snapshot form +1.1% / +1.1%, below the bar (sprint 3). Fork refreshes 10.8 times per 1,000 updates, so there is little to recover. H512+PP's code already refreshes lazily from a per-frame snapshot | 0 for S512+PP. For a king-bucket net it is a requirement, not a gain | the same |
| S6 | **int8 first-layer rows**, widened as they are added | PlentyChess (threat rows) +9.9 STC, +3.3 LTC, −2.5 at fixed nodes; Stockfish "a similar gain", and after the rated version all rows int8 with row pairing +5 to +11% nps; Triumviratus: widening its int8 blocks back to int16 cost +60% L3 misses and 10% speed (a 250 MB net), its per-row-scale 8-bit path lost; Velvet 8.1 (no separate figure); Incipit and Coda int8 threat and pair rows | **tried, lost**: I4, −0.9% / −0.9% nps with +11.6% instructions (sprint 3); 8-bit link rows did not help either (idea 40). Its quality gates passed; the branch speed3/nnue-i4 is kept | 0 (measured) | 0 to +3%: the rows fall from 1.41 MB to 0.70 MB, which fits a core's L2. Peers gain where rows miss the cache; whether Fork's do at 512 threads is unmeasured |
| S7 | **Prefetch of first-layer rows** at make-move | Stockfish threat rows +1.2 STC, +1.6 LTC; PlentyChess threat rows +5.1; Coda +1.7 and "2% fewer cycles"; Raphael +1.9; Viridithas +2.0; Triumviratus +1.76% nps, then six later prefetch patches gained nothing. Dropped: Incipit (the hardware prefetcher already follows a row). All gains are for threat tables of 50 to 250 MB | **tried, lost**: C2 −2.9% (16 lines per row), −1.4% (4 lines); the link rows prefetched at the push did not help (idea 40) | 0 | 0 to +1% |
| S8 | **Prefetch of the TT entry, early** | Ethereal (right after the move) +5.4 STC; Viridithas about 8% faster (2024); Stormphrax about 5%; Renegade (earlier, on a speculative key) +5.5; Triumviratus child's TT and eval-cache entries +2.2% nps | **have** (`predicted_key` before `make`); moving it before the pruning tests was C3, −0.8% | 0 | 0 |
| S9 | **AVX-512 and VNNI in the output pass** | VNNI dot products belong to int8 dense layers, which Fork's net does not have. rofChade AVX-512 +19% over AVX2 on Intel, +10% with VNNI on Zen 4; Stormphrax VNNI 0.5% on Zen 4; Hobbes AVX-512 +16.7; Raphael +20.7 STC; Chess System Tal about 20%. Against: PlentyChess and Raphael warn AVX2 can beat AVX-512 on some CPUs; Stockfish gated one change to AVX2 after it failed on AVX-512 | **tried, lost**: the AVX-512 output layer +2.1% / +1.6%, with VNNI +1.4% / +1.6% (sprint 3). The fused update already uses AVX-512 where built | 0 (measured) | 0 to +2% |
| S10 | **Which build target** (x86-64-v3, v4, native) and code generation in the update kernel | Stockfish: AVX-512 with 16 instead of 32 registers "up to 17%" (gcc spilled registers, Zen 4); clang left update loops rolled on AVX-512 builds, about +41% nps once forced; a gcc 15 regression cost ARM 4%. RubiChess cut its AVX-512 build to 16 registers. Cinder: less loop unrolling, to stop register spills, +40.5 Elo on its AVX-512 build and +0.3 on its VNNI build. Berserk's VNNI build was slower than its plain AVX-512 build (2.10 M against 2.20 M nps). ZigQueen, on a Ryzen 5 7600X3D: the compiler's default tuning had kept its AVX-512 kernels 256 bits wide. Incipit AVX-512 +10% over AVX2. Stormphrax hand SIMD against compiler vectorisation: 7% (clang), 153% (gcc) | **partly measured**: on this PC native (AVX-512) against x86-64-v3 is −1.5% (no difference), both clang PGO. gcc 11.4 was measured on v3 only. **The TCEC build (v4, TCEC's four compilers) has not been timed against v3** | 0 | unknown: 0 to +5% if TCEC's compilers handle the v4 kernel as clang does here; more if one of them spills or fails to unroll. The one row where a cheap check can change the TCEC build choice |
| S11 | **Huge pages for the weights and the search tables** | Quanticade +23.4; Reckless +4.3 at 16 MB hash, +9.0 at 128 MB; PZChessBot +6.2 at 4 threads and a 2 GB hash; Renegade +11.5 at 256 MB hash on a many-thread machine, "shouldn't affect consumer hardware"; Minke 1% single-threaded, 4% at 12 threads, +5.7; Viridithas +3.2; Triumviratus 7% (a 250 MB net); Stockfish (2020) +3.9 STC; PlentyChess allocation fix +6.2; Coda needs explicit huge pages because transparent ones "silently delivered none on some kernels". Against: Halogen on Windows −0.07 | **tried, lost** at 16 MB hash: R19, −0.13% cycles (sprint 4), mechanism confirmed (fewer TLB misses). The TT already uses huge pages. **Not measured at a large hash**: TCEC hardware test plan, entry 1 | 0 (measured) | +1 to +4% at TCEC's hash and thread count: every peer that split the result by hash size or thread count saw it grow with both |
| S12 | **Weights used in place and shared between processes** (the net as constant data in the binary or a shared mapping, not a per-process heap copy) | Stockfish up to +38% nps and +24.8 Elo with many games on a many-core machine, +4.7 STC on its test fleet, 1 to 2% slower for one process without huge pages; Incipit +35 to +45% per process with 32 engines, +18% with 16, about 0 with one; Obsidian about +26% on its own script; the Torch write-up: with 140 engines 1.04x at a 256-wide accumulator, 1.22x at 1024, 1.65x at 2560; Viridithas, PlentyChess and Alexandria memory-map; Gaia and ZigQueen share one copy; Clover "verbatim" | **never tried**: `embedded_net()` parses the embedded bytes into a heap `NetFile` once per process. One process's threads already share it | 0 for one engine. Under full concurrent load (many engines at once, as in SPRT runs) perhaps +3 to +10% total throughput by the Torch curve between 256 and 1024 wide | 0 at TCEC (one process, 512 threads) |
| S13 | **NUMA**: a copy of the weights per node, threads pinned | Gaia +16% (opening) to +92% (endgame) nps on a dual-socket, 192-thread machine from a copy per node and threads pinned to cores that share a cache; PlentyChess +45% on 288 threads over 4 nodes; Stockfish "up to 2.8x" on dual-socket machines; PZChessBot pinning +25.0 Elo with 192 threads, first-touch allocation about 4%; Stormphrax 5 to 10% on 14 threads; pawnocchio about 3%; Triumviratus, Reckless, Raphael (pinning). Against: Halogen neutral at one thread | **never tried** (Phase 6; `numa_nodes` unknown in config/tcec.json) | not applicable | 0 to +2% from the weight copies (1.41 MB stays in each core's caches, unlike the peers' 50 to 250 MB). Pinning and first-touch placement of each thread's tables apply to Fork in full and are the peers' largest many-thread figures: unknown, possibly +3 to +15%. Cannot be measured before a two-socket machine |
| S14 | **Evaluation cache** (a table of network outputs beside the TT) | Seer +23.6 / +25.6 (2021, a slow float net); Ethereal +11.9 with a hand-written evaluation, then removed once the TT held the static evaluation early ("hit rate plummets"); Triumviratus removed its cache for 8.1; Caissa removed a cached score at 2.0; Incipit has one (+0.7% nps from prefetching its slot); Cinder's gained 0 to +2 per step; ZigQueen keeps one for positions the TT evicted; Lc0's NNCache | **never tried**; the TT stores the static evaluation and the search reuses it (0.524 evaluations per node) | 0 or below | 0 or below |
| S15 | **Speculative or forced updates** (bringing a parent up to date when several children will be evaluated; eager updates in PV nodes) | Stockfish parent hint +2.3 STC, later replaced; Caissa about 2% faster; Obsidian +4.1; Viridithas +7.2 at 1+0.01; RubiChess "some more speed". Against: Triumviratus measured 2.5% more time (rejected) | **never tried**; Fork walks 1.19 plies per evaluation, close to the floor of 1 | 0 to +1% | 0 to +1% |
| S16 | **PGO, and one profile per build** | Lizard and Horsie clang LTO + PGO +11.4 STC; PZChessBot +7.6; Triumviratus: one merged profile cost its AVX builds 5% instructions; Stockfish forces unrolling in non-PGO builds. Against: Stormphrax off by default (−0.4); Coda "regresses on most modern hardware"; Cinder removed it (+4.7 without); Clover "worthless"; Obsidian's update gain vanished under PGO | **have** for data generation and the play build; the TCEC build's PGO is planned (R11) | 0 | measured by R11, not here |
| S17 | **Alignment of weights and sums** | Tcheran 64-byte +5.5; Reckless +2.8% speed; Coda +1.4; Halogen 32-byte +1.6 | **have** (64 bytes, `net_file.hpp`) | 0 | 0 |
| S18 | **Output-pass arithmetic for SCReLU** (multiply by the weight before squaring, so the products stay in 16 bits) | Tcheran +9.2 (1.45 M to 1.60 M nps); Halogen +16.1 LTC; Viridithas +9.1 STC; Tarnished "a notable speed boost"; all credit Lizard's author | **have**: `squared_sum` computes v x (v x w) | 0 | 0 |

## 3. Techniques that belong to an architecture Fork does not ship

These are the bulk of what the stronger engines report. None can be measured on S512+PP. They
are the price list for the architectures in [matrix.md](matrix.md), and they explain why those
architectures lost for Fork on the clock.

| # | Technique | What the engines report | Fork's status | What it would take |
|---|---|---|---|---|
| A1 | **Pairwise multiplication** of the accumulator's halves (halves the next layer's input; makes most activations zero) | Stockfish: "slightly faster" than its old activation, later +1.7% nps from a multiply trick and +2.45% from fusing activations; Incipit +6.6 Elo and 7.3% faster with the permutation; Raphael +4.2 STC at equal width; Lizard +1.6 STC, +43.8 in DFRC; Caissa: about 75% of paired activations are zero | **tried** inside AF-S only (pairwise, int8 first dense layer, dense, not sparse): AF-S lost on the clock, −48.52 and −55.85 STC, with a 32 cp quantisation loss | A multi-layer head; of no use to a single-layer net (the output pass is 3.4% of cycles) |
| A2 | **Sparse first dense layer**: only non-zero groups of four inputs are multiplied | Stockfish up to +10% nps, +10.0 STC; Caissa +220% against a scalar loop; Stormphrax +13.7 STC; Hobbes +11.7; Tcheran +5.5% nps, +12.1; pawnocchio +10.2; Raphael 1.04x alone; Incipit 1,912 against 2,345 cycles per node; Quanticade +2.7 and +3.8; Minke +2.8; Berserk needed it to afford a 1024 accumulator. **Against: Coda, at 16 to 32 neurons, measured the sparse kernel 1.8 to 2.4 times slower than dense** | **never tried** (AF-S's layer was dense) | A multi-layer head with pairwise inputs |
| A3 | **Neuron permutation** so zero activations fall in the same groups | Obsidian +5.6; Viridithas +4.7, re-permuting +3.7; Hobbes 1.02x, +3.8; Caissa +2.7% nps (live groups 47% to 37%); Incipit +2.7% nps (53.5% to 39%); Triumviratus +2.5% nps; Raphael 1.08x with the sparse pass; Stockfish about 2%; Astra +2.5. Halogen once shipped a wrong permutation: fixing it +13.3 | **never tried** | Free once A2 exists; a build step |
| A4 | **A sparsity penalty in training** (L1 on the accumulator's outputs) | Raphael 1.12x with A2 and A3 (non-zero groups 118 to 71 of 256), +13.0 at 4+0.04; Tcheran's figure 48% to 33%; Stormphrax +3.2 STC; Viridithas: without it a new activation dropped sparsity from 70% to 50% and lost the speed. Stockfish's rated net lost sparsity (60% to 50% zero) from an optimiser change: "a significant slowdown", −0.6 STC | **never tried** (comparison.md J6) | A trainer option; pays only with A2 |
| A5 | **A faster non-zero finder** (AVX-512 compress, VBMI2; the mask built in the same pass as the activation) | Stormphrax +10.9 STC; Raphael +10.2; Halogen +3.4% nps; Reckless +4.7; Minke 8% on AVX-512, +11.0; Stockfish 1% and 0.7%, mask-in-pass +4.6 on AVX2 and 0 on AVX-512; Incipit +1.7 to +2.3% nps; PlentyChess +1.9 and +7.4 | **never tried** | With A2 |
| A6 | **int8 first dense layer with care for rounding** | Horsie's double-precision weights with deliberate saturation +7.7 STC; Stormphrax precision fixes +3.3 STC and +12.5 at fixed nodes; Raphael's order of shift and square +2.6; Incipit rounding to nearest halved a 7.8 cp error; Caissa and Stockfish (+4.4 STC) and Triumviratus train against the integer grid; Viridithas, Coda, Reckless, Incipit keep the later layers in float | AF-S had an int8 first dense layer and a 32 cp loss; `--qat` is built, its validation never run | The answers to AF-S's 32 cp are here: train on the grid, or keep the small later layers in float |
| A7 | **Threat inputs made incremental** (a per-move list of changed threats from bitboards, only for the pieces a move can affect) | Incipit +54% nps, then +10.6%; Stockfish first pass +5.4%, STC +4.3; Hobbes +6.8, lazy threat updates +18.3; Reckless a dozen patches of +1.5 to +5.8; Stormphrax +10.2 on AVX-512 but +2.2 on AVX2; PlentyChess +3.4 to +7.3 per step; PZChessBot lost about 30% nps to threats, then regained +27.9 and +22.3 at 4+0.04 from deferred discovery, tiling and compact indices; ZigQueen about +21% throughput over nine rounds; Berserk tiling +8.6% nps; Gaia +6% nps | Fork's exposure and contact inputs were summed from scratch at every evaluation: S512cl ran at 0.195 of the default's nps (82% of its time in those inputs), S512+X at 0.818 | An incremental design; the peers treat this as the entry ticket |
| A8 | **int8 threat rows** | PlentyChess +9.9 STC, pure speed; Stockfish "similar"; standard in every threat net surveyed | designed for S512cl (int8 contact rows), not built | With A7 |
| A9 | **Dropping king threats and x-ray threats** | Coda: changes per move 8.40 to 3.86 without king threats; removing x-rays +12.5 STC, +15.1 LTC; Stockfish removed both king directions as non-regressions (13 MB, 0.8 updates fewer); Stormphrax +1.7 STC; Reckless +2.6 | not applicable to Fork's own input design | A design choice at the start |
| A10 | **One accumulator or two** for piece and threat parts | Split: Stormphrax +9.0 STC (a bucket change does not touch the threats). Merged: Stockfish +2.5% nps, +4.6 STC, then a hybrid king-move update +2.7 STC; PlentyChess merged +4.3; Integral merged +6% speed. Triumviratus split +12.1% cycles (closed) | not applicable | Merged with a hybrid king-move update is where the larger engines ended |
| A11 | **A much narrower accumulator when threats arrive** | Viridithas 2560 to 1024 (87% of its old speed); Stormphrax 1792 to 640; Hobbes 1536 to 512; PlentyChess 1792 to 640; Reckless 1024 to 384; Raphael 1280 to 512 (36% slower, still +13.2 STC); Integral 1536 to 768; Stockfish 3072 to 1024 (5 to 15% slower) | Fork's threat nets kept 512 and added the inputs on top | Fork is already at the width the others cut down to; it has no width to trade |
| A12 | **King buckets' cost** | Incipit 4 buckets 0.93 to 0.95 nps, 16 buckets 8.6% slower than 4; Lizard about 13% slower | H-512 lost (STC −24.36); H512+PP is in training (round 3) | S5's cache; the survey's bucket layouts are in matrix.md §3 |

## 4. What the engines report about hardware

These bear on the EPYC column.

- **Many engines at once, or many threads, change the answer.** Triumviratus could not see
  its own net's gain with 75 games on 40 cores (+0.8) and saw +23.4 with 38. Stockfish's
  shared weights gain most "with many cores and a large L3". The Torch write-up shows total
  nps *falling* past 50% machine load when weights are not shared. Minke's and Renegade's
  huge-page gains grow with threads. PlentyChess says its newest net "depends greatly on
  hardware (and especially cache sizes)".
- **Prefetch and layout gains concentrate on memory-bound hosts** (Coda: one host that is
  "not cache-bound" lost 1.5 Elo on a change that gained 6.1 and 10.9 on two others).
  Triumviratus, on a Xeon: "only removing work pays, while prefetching and reordering loads
  do not".
- **AVX-512 is not uniformly better.** Stockfish (register spills under gcc; one change
  failed only on AVX-512), PlentyChess and Raphael (AVX2 faster on some systems), Caissa
  (its AVX-512 and VNNI gain was +10.8 on AVX-512 workers and about +1 elsewhere), rofChade
  (+19% Intel, +10% Zen 4).
- **Fork's own evidence points the same way.** int8 rows added 11.6% instructions and still
  lost only 0.9% nps on a CPU with 96 MB of L3, and the perf-log already marks TCEC's EPYCs
  as the place to re-measure them.

## 5. The untried techniques, ranked by expected nps gain per engineering day

Only rows that apply to the present network and were never measured in the form that
matters. "Day" counts the build and the measurement. All gains are estimates (§1).

| Rank | Item | Work | Expected gain | Gain per day | The decision it can change |
|---|---|---|---|---|---|
| 1 | **S10: time the TCEC build targets** (v3 against v4, with gcc 11.4, g++-12, clang 16 and 19, through update.sh) and read the update kernel's code for register spills | 0.5 day; needs no new code. Zen 4 here stands in for Zen 4c | 0 to +5% on the TCEC binary, likely near 0; a spill or a rolled loop would be worth 10% or more | 0 to 10% | `FORK_ARCH` and the compiler for TCEC (decision 9 of 2026-11-07 assumes v4) |
| 2 | **S11: huge pages at a TCEC-sized hash** | 0.5 day on a runner at 4 GB (the candidate exists: archive/speed4-r19-hugepages; the driver in the hardware test plan does not) plus the driver, about 1 day | +1 to +4% at TCEC; 0 here | 1 to 3% | Adopt R19 or close it |
| 3 | **S6 under cache pressure**: int8 rows re-timed with every core loaded (the branch exists: speed3/nnue-i4) | 0.5 to 1 day: a many-engines-at-once A/B on this PC is a rough stand-in for 16 threads per 16 MB | 0 to +3% at TCEC; 0 here | 0 to 4% | Whether int8 rows are a TCEC-only build option |
| 4 | **S12: the net as shared constant data** | about 1 day (the net file laid out so it needs no parsing, with the loader's bounds checked at build time) | 0 at TCEC; +3 to +10% total throughput for fleets of engines (SPRT stages, gauntlets) | 0 at TCEC; 3 to 10% of test throughput | Test cost, not strength |
| 5 | **S13: NUMA placement** (threads pinned, each thread's tables first touched on its own node; a weight copy per node last) | 1 to 2 days, in Phase 6, and only measurable on a two-socket machine | unknown: 0 to +2% from the weight copies, possibly +3 to +15% from pinning and placement (the peers' figures on 192-thread machines are far larger, with far larger nets) | unknown; could be the largest item on this list | Phase 6 design; a line in the TCEC hardware test plan |
| 6 | **S15: speculative parent updates**; **S4: one pass for both perspectives, again** | 0.5 day each | 0 to +1% each | 0 to 2% | None likely |
| 7 | **S14: an evaluation cache** | 1 day | 0 or below | none | None; the engines that had one removed it |

NUMA placement stands fifth only because it can be neither built before Phase 6's threads
exist nor measured before a two-socket machine is available. Its size is the largest unknown
in the table.

**Reading.** For the single-layer net, the engines' list is nearly used up: of the 18 rows in
§2 Fork has 7, has measured and rejected 6 on this PC, has partly measured 1 (S10) and has
never tried 4 (S12 to S15),
of which only NUMA placement (S13) could matter at TCEC, and it cannot be measured here.
The three items that can be measured now are all "the same code on other hardware or
another compiler" (ranks 1 to 3), and none needs new engine code. The large speed items in
the survey (§3) are not optimisations of a network like Fork's. They are what makes a
different network affordable.

## 6. UNVERIFIED in this file

- Every expected gain (my estimates).
- Today's share of cycles spent in the network (not profiled since the fused update).
- The EPYC 9754's and the 7600X3D's cache sizes against AMD's own pages (Wikipedia only);
  AVX-512 VNNI on the EPYC 9754; its L2 TLB size.
- The size of a searcher's tables other than the pair tables (not read).
- Whether TCEC's four compilers generate the v4 update kernel as clang 21 does here.
- Peers' figures are as the group records cite them; I did not reopen their pages.
