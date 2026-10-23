# Fork: Design

Fork is an original UCI chess engine in C++20, built to compete in TCEC.
Every decision optimizes engine-vs-engine play under TCEC conditions,
correctness first, then speed. This file records the architecture and every
decision that affects play. Phase 7 evaluation adjustments must be documented
here; no logic may alter reported scores to trigger or avoid adjudication.

Status: **Phase 1 spec, awaiting approval.** Nothing below is implemented yet.

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
  means editing one JSON file, never code.
- **Tunable parameters** (search and evaluation) will live in one table,
  `src/tune/params.*`, from Phase 3 on. Each entry has a name, default,
  min, max and SPSA step, and is exposed as a UCI option in tuning builds.
- **No phase starts with a failing test.** Each phase ends with a commit, a
  summary, and a stop for go-ahead.

## 2. Platform and toolchain

| Item | Decision |
|---|---|
| Primary target | x86-64 Linux (TCEC's platform). |
| Development host | Windows 11; LLVM-MinGW (UCRT) clang and WinLibs GCC, via winget. |
| Compilers | Clang (primary, currently 23.1) and GCC (secondary, currently 16.2). Both must build with zero warnings under `-Wall -Wextra -Wpedantic -Wshadow -Werror`. |
| Build | CMake (≥ 3.25) + Ninja, driven by `CMakePresets.json`. |
| Language | C++20, no exceptions in hot paths, no RTTI dependence. Standard library only, plus documented permissive libraries (e.g. Fathom in Phase 3). |
| CPU | This machine has AVX2, BMI2 and AVX-512, so every SIMD path can be tested locally. |

### Build presets

| Preset | Compiler | Flags | Purpose |
|---|---|---|---|
| `clang-debug` | clang | `-O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined`, `FORK_DEBUG` asserts | Day-to-day testing. |
| `clang-release` | clang | `-O3 -march=native -DNDEBUG` (+ LTO) | Fast local build, full-depth perft. |
| `gcc-debug` | gcc | `-O1 -g`, asserts; ASan/UBSan on Linux (MinGW GCC ships no sanitizer runtimes) | Second-compiler check. |
| `gcc-release` | gcc | `-O3 -march=native -DNDEBUG` | Second-compiler check. |
| `clang-pgo` / `gcc-pgo` | either | A `pgo` target builds an instrumented binary, runs `fork bench`, merges the profile (`llvm-profdata` or `.gcda`), then rebuilds with the profile. | Tournament binaries. |

Besides `-march=native` there are named architecture builds
(`-DFORK_ARCH=x86-64-v3` for AVX2 and `x86-64-v4` for AVX-512), so a binary
built here can be sent to a different machine. `FORK_PEXT=ON|OFF` picks PEXT
or classic magic lookups (see §4.3). It defaults to ON when BMI2 is present.

Until Phase 3 provides a search bench, `fork bench` is a fixed perft workload
(the six suite positions at fixed depths). It prints total nodes and nps, and
the node count is deterministic.

`scripts/env.ps1` and `scripts/env.sh` put the winget-installed toolchain on
PATH, so that a shell opened before the install still finds it.

## 3. Repository layout

```
CMakeLists.txt  CMakePresets.json
config/tcec.json          tournament conditions (data only)
docs/DESIGN.md            this file
docs/ORIGINALITY.md       references, libraries, data provenance
src/core/                 types, bitboards, attacks, zobrist, position, movegen   (Phase 1)
src/uci/                  protocol, options                                       (Phase 2)
src/search/               search, TT, ordering, time management, threads          (Phases 3,5,6)
src/eval/                 eval interface, PST eval, NNUE                          (Phase 4)
src/tb/                   Syzygy bridge (Fathom)                                  (Phase 3)
src/tune/                 parameter table                                         (Phase 3)
src/main.cpp              CLI entry: uci loop, bench, perft
tests/                    unit + perft tests (CTest)
tools/                    training pipeline, match scripts (Phases 4, 8)
scripts/                  env setup, PGO helpers
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
  Moves". The flags are quiet, double push, castle, capture, en passant,
  four promotions and four promotion-captures. Move 0 means "none".
- **Castling encoding.** Internally, a castling move is *king origin → castling
  rook square* ("king takes own rook"). At the UCI boundary it is converted
  to the standard `e1g1` form. This costs nothing now and makes Chess960
  (TCEC runs FRC events) a parsing change later rather than a movegen
  rewrite. The castling rights record the rook squares, not just KQkq bits.
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
  sparse random candidates from a fixed-seed xorshift64* generator. No
  published magic tables are copied. The search is deterministic and takes
  milliseconds. A test pins the result for each square: every subset maps to
  the correct attack set.
- **Fancy magics.** Each square gets its own shift and its own offset into
  one shared attack table, about 800 KB for rooks and bishops together.
- **PEXT variant.** With `FORK_PEXT` on, the index is
  `_pext_u64(occ, mask)` into the same table layout. Zen 1/2 microcode PEXT is
  slow, so it stays a build switch. The two variants are cross-checked in
  tests.

### 4.4 Zobrist hashing

There are 64-bit keys for each piece-square pair, side to move, each of the
16 castling-rights states, and the en passant file. They come from a
fixed-seed splitmix64 stream generated by Fork, so keys and therefore bench
node counts are reproducible.

**En passant is hashed only when a legal en passant capture exists.** This
way two positions that differ only by an unusable ep square get the same key,
which repetition detection (Phase 3) and the TT need. The same rule controls
whether FEN output prints the ep square, so `key(parse(fen(p))) == key(p)`.

### 4.5 Position

- State: `byType[6]`, `byColor[2]` bitboards, `board[64]` mailbox, side to
  move, castling rights and their rook squares, ep square, halfmove clock,
  fullmove number, and Zobrist key.
- **Computed in make, stored per ply**: the checkers bitboard. Pins are
  computed in movegen from the king outward (one slider pass per side).
- **Make/unmake.** An undo stack (`std::vector<Undo>`, reserved up front)
  holds the captured piece, the previous castling rights, ep square, halfmove
  clock, key and checkers. `unmake` restores the state exactly; tests compare
  full snapshots.
- A null move (make/unmake) is added now, because the search needs it and it
  shares the undo path.
- **FEN** parse and serialize. Parsing validates the input (piece counts,
  one king each, side not-to-move not in check, castling rights consistent
  with the king and rook squares, ep square plausible) and returns an error
  string instead of asserting, because FENs come from untrusted GUI input. X-FEN
  and Shredder-FEN castling letters are parsed too, in preparation for 960.

### 4.6 Legal move generation

The generator is fully legal, with no make-and-test:

1. If the side to move is in **double check**, only king moves are generated.
2. **Single check**: a `target` mask = the checker plus the squares between it
   and the king. Non-king moves must land in `target` (or capture the
   checking pawn en passant).
3. **Pins**: each pinned piece may only move along `line(king, piece)`.
4. **King moves** are tested against enemy attacks computed with the king
   removed from occupancy, so the king can't step back along a checking
   ray.
5. **En passant**: after the pin/check filters, the one rank case that
   filters miss (both pawns leaving the king's rank to reveal a rook or
   queen) is checked by removing both pawns and testing slider attacks on
   the king.
6. **Castling**: the right must still be held, the squares between the king
   and rook and the king's path must be empty (apart from those two pieces),
   no square the king crosses may be attacked, and the king may not start in
   check.

There are four generation modes: `Legal` (all moves), `Captures` (captures plus
all promotions, for qsearch), `Quiets` (everything else), and `Evasions` (used
by `Legal` when in check). `Captures ∪ Quiets == Legal` and the two are disjoint;
this is checked at every node in the consistency test. Staged generation for
move ordering comes in Phase 3, on top of these modes.

Also in Phase 1: `is_pseudo_legal(move)` and `is_legal(move)` for validating TT
and killer moves later (tested against the generator at every node), and
`attackers_to(sq, occ)`.

### 4.7 Perft and CLI

- `fork perft <depth> [fen]` prints the node count and nps;
  `fork divide <depth> [fen]` prints per-move counts for debugging. Bulk
  counting is used at depth 1. Phase 2 adds the same through UCI `go perft`.
- `fork bench` runs the fixed perft workload (§2).

### 4.8 Tests (CTest, no third-party framework)

Fork has a small in-house test harness (`tests/harness.hpp`, assertions plus
named cases) to avoid a dependency.

| Test | What it checks |
|---|---|
| `perft_suite` | The CPW perft positions: startpos, Kiwipete, positions 3, 4, 5, 6. Expected counts are the published CPW values. **Release depths**: startpos 6, Kiwipete 5, pos3 7, pos4 5, pos5 5, pos6 5 (all ≥ 5). **Sanitizer builds** run every position to depth 5 except startpos and Kiwipete at 4, labelled so a full-depth sanitizer run is still available (`ctest -L slow`). |
| `perft_mirror` | Each suite position color-flipped gives identical counts. This catches color-asymmetry bugs that the fixed suite misses. |
| `consistency` | Walks the perft tree of every suite position (depth 3-4) and at **every node** checks: incremental key == key recomputed from scratch; unmake restores a byte-identical snapshot; FEN round-trip; `Captures`/`Quiets` partition `Legal`; `is_legal`/`is_pseudo_legal` agree with the generator for every move in the list and reject a sample of random 16-bit moves; checkers == `attackers_to(king)`. |
| `magics` | For every square and every occupancy subset of the mask, magic (and PEXT) lookup == ray-walk reference. |
| `fen` | Round-trips of the suite plus edge cases. Malformed FENs (bad counts, two kings, side not to move in check, impossible ep, bad castling) are rejected with an error, not a crash. |
| `zobrist_ep` | An ep square without a legal ep capture does not change the key. |

**Pass criteria for Phase 1**: all tests green on `clang-debug` (ASan +
UBSan), `clang-release`, `gcc-debug` and `gcc-release`, with zero warnings
on both compilers. The `pgo` target builds and runs. Perft nps is reported,
but there is no speed gate yet.

### 4.9 Phase 1 deliverables

1. CMake + presets + env scripts, with an empty `fork` that builds on both
   compilers.
2. Core types, bitboards, attack tables, magics (+ `magics` test).
3. Zobrist, Position, FEN, make/unmake (+ `fen`, `zobrist_ep`).
4. Legal movegen, perft/divide/bench CLI (+ `perft_suite`, `perft_mirror`,
   `consistency`).
5. PGO target, DESIGN/ORIGINALITY updates, commit, summary, stop.

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
  load.
- **Phase 6: SMP.** Lazy SMP, NUMA-aware thread/memory placement, no large
  page dependence, scaling benchmark.
- **Phase 7: Tournament-aware play.** Contempt/style options, TB-aware
  eval, keeping tension. Each item is documented here as genuine evaluation.
- **Phase 8: TCEC-conditions testing** from `tcec.json`: paired openings,
  adjudication, gauntlet against pinned engines, SPRT, stress testing.

## 6. Open questions for the owner

1. **Linux.** There is no Linux environment here (WSL isn't installed). The
   primary target needs a real Linux build and test run, and that's also the
   only place GCC sanitizers work. Recommendation: install WSL2 + Ubuntu
   (needs admin, may need a reboot) before Phase 1 is signed off. Windows
   builds stay as the second platform.
2. **Chess960.** Phase 1 makes 960 cheap (§4.1) but doesn't test it. Should
   FRC (TCEC runs FRC events) be a goal, with a 960 perft suite added in
   Phase 1 or Phase 2?
3. **`tcec.json` values.** I could not confirm the current season's time
   controls, hardware, or hash limit from an authoritative source. Unknown
   fields are left `null` with `"verified": false`, and the Phase 8 scripts
   will refuse to run on nulls. Please supply the season's rules page, or
   I'll research it before Phase 5.
