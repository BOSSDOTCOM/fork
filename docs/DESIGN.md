# Fork: Design

Fork is an original UCI chess engine in C++20, built to compete in TCEC.
Every decision optimizes engine-vs-engine play under TCEC conditions,
correctness first, then speed. This file records the architecture and every
decision that affects play. Phase 7 evaluation adjustments must be documented
here; no logic may alter reported scores to trigger or avoid adjudication.

Status: **Phase 1 built; all presets green on Windows; Linux (WSL2) run pending.**

---

## 1. Ground rules

- **Originality.** Stockfish and the Chess Programming Wiki (CPW) are used as
  technique references only. No engine's source, network files, or
  engine-generated training data enter the repo. Every reference consulted
  and every library used is logged in `docs/ORIGINALITY.md` as it happens.
- **Tournament settings live in `config/tcec.json` only.** The engine binary
  never reads that file: it has generic defaults and receives tournament
  settings as UCI options. The test scripts (Phase 8) and time-management
  tests (Phase 5) read `tcec.json` and pass the values in. So a new season
  means editing one JSON file, never code. Every value in it is unverified
  until the current season's full rules are researched (before Phase 5).
- **Tunable parameters** (search and evaluation) will live in one table,
  `src/tune/params.*`, from Phase 3 on. Each entry has a name, default,
  min, max and SPSA step, and is exposed as a UCI option in tuning builds.
- **No phase starts with a failing test.** Each phase ends with a commit, a
  summary, and a stop for go-ahead. A phase is signed off only when every
  build preset passes on **both Linux and Windows**.

## 2. Platform and toolchain

| Item | Decision |
|---|---|
| Primary target | x86-64 Linux (TCEC's platform). The Linux working copy lives in the WSL2 filesystem at `~/fork`, never under `/mnt/c`. |
| Second platform | Windows 11 (development host): LLVM-MinGW (UCRT) clang and WinLibs GCC, via winget. |
| Compilers | Clang (primary) and GCC (secondary). Both must build with zero warnings under `-Wall -Wextra -Wpedantic -Wshadow -Werror`. |
| Build | CMake (≥ 3.25) + Ninja, driven by `CMakePresets.json`. |
| Language | C++20, standard library only, plus documented permissive libraries (e.g. Fathom in Phase 3). |
| Line endings | LF everywhere (`.gitattributes`). |

LLVM-MinGW also ships a `g++.exe` that is really clang, so compilers are
never picked by bare name. The presets read `FORK_CLANG_CXX` and `FORK_GCC_CXX`,
which `scripts/env.ps1` and `scripts/env.sh` set: to absolute winget paths on
Windows, and to `clang++`/`g++` on Linux. `scripts/build.ps1` and
`scripts/build.sh` source the env script and then configure, build and test
any list of presets (`all` by default).

### Build presets

| Preset | Arch flags | Slider lookup | Notes |
|---|---|---|---|
| `clang-debug`, `gcc-debug` | `-march=native` | PEXT if BMI2 | `-O1 -g`, asserts, ASan + UBSan. MinGW GCC has no sanitizer runtimes, so on Windows `gcc-debug` builds without them; on Linux both compilers sanitize. |
| `clang-release`, `gcc-release` | `-march=native` | PEXT if BMI2 | `-O3`, LTO. |
| `clang-v3`, `gcc-v3` | `-march=x86-64-v3` (AVX2, BMI2) | PEXT | Portable modern build. |
| `clang-avx512`, `gcc-avx512` | `-march=x86-64-v4` (AVX-512 F/BW/CD/DQ/VL) | PEXT | |
| `clang-nopext`, `gcc-nopext` | `-march=x86-64-v3` | magics (`FORK_NO_PEXT`) | For CPUs with slow PEXT (AMD Zen 1/2). |

**PGO.** `cmake --build <dir> --target pgo` (or `scripts/pgo.sh` / `.ps1`) builds
an instrumented release binary in `build/<compiler>-pgo`, runs `fork bench`,
merges the profile (`llvm-profdata` for clang, `.gcda` files for GCC), and
rebuilds in the same directory with the profile. It then checks bench parity.

**Bench parity (automated).** `tests/bench.ref` holds the expected `fork bench`
node count and signature. Every preset's CTest run has a `bench_parity` test
that runs the real `fork` binary and compares its output with that file, and
the PGO script checks the PGO build the same way. Because every build matches
one committed reference, node counts are identical across all architectures,
lookup variants, both compilers and both operating systems; any drift fails
a test. The reference changes only when a commit intends to change bench
(from Phase 3 on, any search change), and that commit updates `bench.ref`
alongside the change.

`fork bench` (until Phase 3 provides a search bench) is a fixed perft workload
over the six suite positions. It prints `nodes`, `nps`, and a 64-bit
`signature`: a fold of the Zobrist key at every interior node in visit
order. The signature catches differences in hashing or generation order that a
bare node count would miss.

## 3. Repository layout

```
CMakeLists.txt  CMakePresets.json  .gitattributes
cmake/                    bench check, PGO driver
config/tcec.json          tournament conditions (data only)
docs/DESIGN.md            this file
docs/ORIGINALITY.md       references, libraries, data provenance
src/core/                 types, bitboards, attacks, zobrist, position, movegen, perft   (Phase 1)
src/uci/                  protocol, options                                              (Phase 2)
src/search/               search, TT, ordering, time management, threads                 (Phases 3,5,6)
src/eval/                 eval interface, PST eval, NNUE                                 (Phase 4)
src/tb/                   Syzygy bridge (Fathom)                                         (Phase 3)
src/tune/                 parameter table                                                (Phase 3)
src/main.cpp              CLI entry: perft, divide, bench (UCI loop from Phase 2)
tests/                    unit + perft tests (CTest), bench.ref
scripts/                  env setup, build-all, PGO
tools/                    training pipeline, match scripts (Phases 4, 8)
```

## 4. Phase 1 spec: board and move generation

### 4.1 Core types

- **Squares**: `a1 = 0, b1 = 1, …, h8 = 63` (little-endian rank-file).
  Square `s` is bit `s` of a `uint64_t` bitboard.
- **Colors** are `White = 0, Black = 1`. **Piece types** are
  `Pawn, Knight, Bishop, Rook, Queen, King` = 0..5. **Pieces** are
  `color * 8 + type`, with `NoPiece = 15`, so the color is `p >> 3` and the type
  is `p & 7`.
- **Move** (16 bits) = `from` (bits 0-5) | `to` (bits 6-11) | `flag` (bits
  12-15). This is the from-to-flags scheme described on CPW "Encoding
  Moves". The flags are quiet, double push, castle, capture, en passant, four
  promotions and four promotion-captures. Move 0 means "none".
- **Castling encoding.** Internally, a castling move is *king origin → castling
  rook square* ("king takes own rook"). At the UCI boundary it is converted to
  the standard `e1g1` form. Only standard castling (KQkq, king on e1/e8,
  rooks in the corners) is supported; see §6 for the deferred Chess960
  decision.
- `MoveList` is a fixed array of 256 moves with a size, stack allocated.

### 4.2 Bitboard utilities

`popcount`, `lsb`, and `pop_lsb` use `<bit>` (C++20), which compiles to
`POPCNT`/`TZCNT`. Shift helpers handle the a/h-file masks. Precomputed tables
are built at startup:
`between(a, b)` holds the squares strictly between two aligned squares, and
`line(a, b)` holds the full line through them. Both are used for pins and
check blocking. There are also pawn, knight and king attack tables.

### 4.3 Slider attacks: magic bitboards

- Rook and bishop masks, relevant occupancy subsets, and attack sets are
  computed by ray-walking.
- **Magic numbers are found at startup by Fork's own search**, using
  sparse random candidates from a fixed-seed xorshift generator. No published
  magic tables are copied. The search is deterministic and takes milliseconds.
- **Fancy magics.** Each square gets its own shift and its own offset into
  one shared attack table, about 800 KB for rooks and bishops together.
- **PEXT variant.** In builds with BMI2 (unless `FORK_NO_PEXT`), the index is
  `_pext_u64(occ, mask)` into the same table layout, and no magic search
  runs. Both variants are verified against the ray-walk reference for every
  square and occupancy subset, and bench parity ties them together.

### 4.4 Zobrist hashing

There are 64-bit keys for each piece-square pair, side to move, each of the
16 castling-rights states, and the en passant file. They come from a
fixed-seed splitmix64 stream generated by Fork, so keys and therefore bench
signatures are reproducible.

**The en passant square is stored only when a legal en passant capture
exists.** So it is hashed, and printed in FEN, only in that case. Two
positions that differ only by an unusable ep square get the same key, which
repetition detection (Phase 3) and the TT need, and `key(parse(fen(p))) ==
key(p)`.

### 4.5 Position

- State: `byType[6]`, `byColor[2]` bitboards, `board[64]` mailbox, side to
  move, castling rights (4 bits), ep square, halfmove clock, fullmove number,
  Zobrist key, and the checkers bitboard (computed in make).
- **Make/unmake.** An undo stack (`std::vector<Undo>`, reserved up front)
  holds the key, checkers, captured piece, castling rights, ep square and
  halfmove clock. `unmake` restores the state exactly; tests compare full
  snapshots.
- A null move (make/unmake) shares the undo path.
- **FEN** parse and serialize. Parsing validates the input and returns an
  error string instead of asserting, because FENs come from untrusted GUI
  input. It rejects: bad syntax or rank lengths, a count other than one king
  per side, more than 8 pawns or 16 pieces per side, pawns on the first or
  last rank, the side not to move being in check, castling rights without the
  king and rook on their home squares, and implausible ep squares (wrong
  rank, occupied, or no pawn that could have just double-pushed). The
  halfmove and fullmove fields may be omitted (they default to `0 1`).

### 4.6 Legal move generation

The generator is fully legal, with no make-and-test:

1. If the side to move is in **double check**, only king moves are generated.
2. **Single check**: a `target` mask = the checker plus the squares between it
   and the king. Non-king moves must land in `target`.
3. **Pins**: each pinned piece may only move along `line(king, piece)`.
4. **King moves** are tested against enemy attacks computed with the king
   removed from occupancy, so the king can't step back along a checking
   ray.
5. **En passant** is checked by simulating the occupancy change (removing
   the capturing and captured pawns, adding the destination) and testing
   whether any enemy piece other than the captured pawn attacks the king.
   This one test covers check evasion, pins, and the rank-discovery case.
6. **Castling**: the right must still be held, the squares between the king
   and rook must be empty, no square the king crosses may be attacked, and
   the king may not start in check.

There are three generation modes: `Legal` (all moves), `Captures` (captures plus
all promotions, for qsearch) and `Quiets` (everything else, including castling).
`Captures ∪ Quiets == Legal` and the two are disjoint; this is checked at every
node in the consistency test. Staged generation for move ordering comes in
Phase 3, on top of these modes.

`is_pseudo_legal(move)` and `is_legal(move)` validate TT and killer moves
later; they are tested against the generator at every node. Also provided:
`attackers_to(sq, occ)`.

### 4.7 Perft and CLI

- `fork perft <depth> [fen]` prints the node count and nps;
  `fork divide <depth> [fen]` prints per-move counts for debugging. Bulk
  counting is used at depth 1. Phase 2 adds the same through UCI `go perft`.
- `fork bench` runs the fixed workload (§2); `fork version` prints the
  compiler, arch and lookup variant.

### 4.8 Tests (CTest, no third-party framework)

Fork has a small in-house test harness (`tests/harness.hpp`, assertions plus
named cases) to avoid a dependency.

| Test | What it checks |
|---|---|
| `perft_suite` | The CPW perft positions: startpos, Kiwipete, positions 3, 4, 5, 6, with the published CPW counts as oracles. **Release depths**: startpos 6, Kiwipete 5, pos3 7, pos4 5, pos5 5, pos6 5 (all ≥ 5). **Debug (sanitizer) builds** run every position to depth 5 except startpos and Kiwipete at 4. The full release depths stay available in debug builds as `perft_full` (`ctest -L slow`). |
| `perft_mirror` | Each suite position color-flipped gives identical counts. This catches color-asymmetry bugs that the fixed suite misses. |
| `consistency` | Walks the perft tree of every suite position and at **every node** checks: incremental key == key recomputed from scratch; unmake restores an identical snapshot; FEN round-trip; `Captures`/`Quiets` partition `Legal`; `is_legal`/`is_pseudo_legal` agree with the generator for every generated move, every move generated at the parent, and a sample of random 16-bit moves; checkers == `attackers_to(king)`. Null moves are covered too. |
| `magics` | For every square and every occupancy subset of the mask, the build's lookup == the ray-walk reference. |
| `fen` | Round-trips of the suite plus edge cases. Malformed FENs are rejected with an error, not a crash. |
| `zobrist_ep` | An ep square without a legal ep capture does not change the key; a usable one does; a pinned ep capturer counts as unusable. |
| `bench_parity` | `fork bench` output matches `tests/bench.ref` (§2). |

**Pass criteria for Phase 1**: all tests green with zero warnings on every
preset in §2 (10 presets plus PGO for each compiler), on both Linux (WSL2,
`~/fork`) and Windows. Perft nps is reported, but there is no speed gate yet.

### 4.9 Phase 1 deliverables

1. CMake + presets + env/build scripts, with an empty `fork` that builds on
   both compilers.
2. Core types, bitboards, attack tables, magics (+ `magics` test).
3. Zobrist, Position, FEN, make/unmake (+ `fen`, `zobrist_ep`).
4. Legal movegen, perft/divide/bench CLI (+ `perft_suite`, `perft_mirror`,
   `consistency`, `bench_parity`).
5. PGO target, the Linux run in WSL2, DESIGN/ORIGINALITY updates, commit,
   summary, stop.

## 5. Later phases (outline; each gets its own spec before building)

- **Phase 2: UCI.** Full protocol. Hash in MB via `size_t` math with no
  32-bit overflow (64 GB+), allocated in chunks and first-touch
  initialized in parallel. Threads up to 1024 (Windows processor groups are
  handled for local testing). `Move Overhead`, `SyzygyPath`. Stability is
  tested under cutechess-cli and fastchess.
- **Phase 3: Search.** PVS + ID + aspiration, qsearch with SEE, TT,
  ordering, pruning and extensions as listed in the brief, Syzygy
  (Fathom), deterministic `bench` (fixed positions, fixed depth, 1 thread).
- **Phase 4: Evaluation.** A swappable `Evaluator` interface; tapered
  PST first, then NNUE (HalfKA-style, incremental accumulator, AVX2/AVX-512 plus
  scalar) trained only on Fork self-play data, with provenance logged.
- **Phase 5: Time management.** Soft and hard limits tuned for long
  increment games without ponder, and a stress test under artificial system
  load. Before this phase starts: research the current TCEC season's full
  rules and fill in `config/tcec.json`.
- **Phase 6: SMP.** Lazy SMP, NUMA-aware thread/memory placement, no large
  page dependence, scaling benchmark.
- **Phase 7: Tournament-aware play.** Contempt/style options, TB-aware
  eval, keeping tension. Each item is documented here as genuine evaluation.
- **Phase 8: TCEC-conditions testing** from `tcec.json`: paired openings,
  adjudication, gauntlet against pinned engines, SPRT, stress testing.

## 6. Decisions log

| Date | Decision |
|---|---|
| 2026-10-23 | **Linux**: the owner installs WSL2. The Linux working copy is `~/fork` inside WSL; Phase 1 sign-off requires every preset passing on Linux, including GCC with sanitizers. |
| 2026-10-23 | **Chess960 / Double FRC: deferred, out of scope.** No X-FEN/Shredder-FEN parsing, no `UCI_Chess960` option, no 960 perft suite. Standard KQkq castling only. The internal "king takes own rook" castling encoding stays (it costs nothing), but no 960-specific logic is written. If FRC is taken up later, the CPW "Chess960 Perft Results" page (960 positions with depth 1-6 counts) is the planned test oracle; no published Double FRC perft suite was found on 2026-10-23. |
| 2026-10-23 | **tcec.json**: every value, including the adjudication thresholds (from an older season's rules), is marked unverified. Full current-season rules are researched before Phase 5. |
| 2026-10-23 | **Release targets**: `-march=native`, x86-64-v3, x86-64-v4 (AVX-512), and a no-PEXT magics build, for each compiler; bench must match across all of them (automated `bench_parity`). |

## 7. Performance doctrine (governs every phase)

Added 2026-10-23 at the owner's request. These rules apply to all phases,
and later specs must cite them where relevant.

**SIMD**
- Use compiler intrinsics (`<immintrin.h>`), never hand-written assembly.
- Every SIMD path has a scalar reference implementation, and a test proves
  the two give identical results. For integer kernels the results must be
  bit-identical, over randomized and edge-case inputs.
- Targets are AVX2, AVX-512 (VNNI where available) and a scalar fallback,
  each selected by build preset. Phase 1 has the AVX2 (x86-64-v3) and
  AVX-512 (x86-64-v4) presets. Phase 4 adds an AVX-512 VNNI preset and a
  scalar preset (baseline x86-64, no SIMD paths), each with bench parity.

**NNUE (Phase 4)**
- The accumulator is updated incrementally.
- Weights are quantized to int8/int16.
- Buffers are cache-line aligned (64 bytes).
- Every layer has a SIMD implementation alongside its scalar reference.

**Memory**
- Hot structures are cache-line aligned and sized with the cache in mind.
- The TT entry is prefetched using `Position::key_after(move)` before
  `make`.
- No heap allocation in the search path, enforced by the counting-allocator
  test (`no_alloc`), which is extended to cover search in Phase 3.

**Measurement**
- Every optimization is profiled before and after.
- It must keep bench identical (`bench_parity`).
- It's accepted only with a measured gain, using the interleaved A/B harness
  (`bench/ab.py`, `bench/experiment.sh`) and the noise rules in
  `bench/micro.cpp`.
- Speed claims are recorded per function in the decisions log, with the
  harness output that supports them.
- An optimization that makes the code meaningfully harder to maintain is
  reported to the owner before it's adopted.

**Layout review (Phase 1 Part C)**
Position, move lists and the per-ply state are reviewed for cache efficiency
and SIMD-friendly access now, so that Phases 3 and 4 don't need a
restructure. The results are recorded in the decisions log.
