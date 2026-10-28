# Fork: Design

Fork is an original UCI chess engine in C++20, built to compete in TCEC.
Every decision optimizes engine-vs-engine play under TCEC conditions,
correctness first, then speed. This file records the architecture and every
decision that affects play. Phase 7 evaluation adjustments must be documented
here; no logic may alter reported scores to trigger or avoid adjudication.

Status: **Phase 2 (UCI) signed off 2026-10-24 (tag `phase-2`); Phase 1 signed off 2026-10-24 (tag `phase-1`). Every preset green on Windows, Linux and the TCEC toolchain. Phase 3 (search) spec approved 2026-10-24 (§5.2): Milestones A, B and C done (C merged 2026-10-27), the parameter table (8b) done, the heuristic-discovery pilot (8c) on hold for the full engine audit (branch `audit-1`, 2026-10-27); tier 2 (deliverable 9) next.**

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
| Build | CMake + Ninja. The floor is CMake 3.22 (Ubuntu 22.04, TCEC's servers); `CMakePresets.json` (needs 3.25) is a developer convenience. The TCEC build is `update.sh` (plain `cmake -B`, no presets). |
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
| `clang-release`, `gcc-release` | `-march=native` | PEXT if BMI2 | `-O3 -g`, LTO (where the toolchain can link it; probed with `CheckIPOSupported`). |
| `clang-v3`, `gcc-v3` | `-march=x86-64-v3` (AVX2, BMI2) | PEXT | Portable modern build. |
| `clang-avx512`, `gcc-avx512` | `-march=x86-64-v4` (AVX-512 F/BW/CD/DQ/VL) | PEXT | |
| `clang-nopext`, `gcc-nopext` | `-march=x86-64-v3` | magics (`FORK_NO_PEXT`) | For CPUs with slow PEXT (AMD Zen 1/2). |

**TCEC build (`update.sh`).** Builds the engine only (no tests, so no
configure-time downloads), Release `-O3 -g`, with an explicit
`FORK_ARCH` (default `x86-64-v3`; `native` is refused, because TCEC may
build on one server and run on another CPU generation) and the first
compiler found of `clang++-19`, `clang++-16`, `clang++`, `g++-12`, `g++`
(or `CXX`). Inside a checkout it builds that tree; elsewhere it clones
`FORK_REPO`. `scripts/check.sh full` builds it on TCEC's toolchain on every
full check: a WSL distro with Ubuntu 22.04, gcc 11.4, g++-12, clang 16.0.6
and 19.1.7 (from apt.llvm.org) and CMake 3.22.1, provisioned by
`scripts/tcec-toolchain-setup.sh`; each compiler's binary must match
`tests/bench.ref`. `FORK_REPO` is https://github.com/BOSSDOTCOM/fork
(created 2026-10-24, public since 2026-10-26). An anonymous clone from
that URL through `update.sh` was verified on 2026-10-27 (Ubuntu 22.04
toolchain, clang 19: bench 17309921 / 372dc2e2d8a88e4b). In clone mode
every run checks out the remote's current state, also after a rewritten
history (audit-1, T-1; tested by `scripts/update-test.sh`).

**PGO.** `scripts/build.sh clang-pgo gcc-pgo` (which runs `cmake -P cmake/pgo.cmake`) builds
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

`fork bench` is the search bench since Phase 3 (§5.2, "Search bench"); the
Phase 1 perft workload over the six suite positions is `fork perftbench`
(`tests/perft_bench.ref`). Each prints `nodes`, `nps`, and a 64-bit
`signature`: for the perft workload, a fold of the Zobrist key at every
interior node in visit order. The signature catches differences in hashing or generation order that a
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
src/search/               search, TT, ordering, time management, Syzygy bridge, threads  (Phases 3,5,6)
src/eval/                 eval interface, PST eval, NNUE                                 (Phase 4)
src/tune/                 parameter table                                                (Phase 3)
src/main.cpp              CLI entry: perft, divide, bench (UCI loop from Phase 2)
tests/                    unit + perft tests (CTest), bench.ref
scripts/                  env setup, build-all, PGO
tools/                    training pipeline, match scripts (Phases 4, 8)
bench/, fuzz/             microbenchmarks and A/B harness; libFuzzer targets and seed corpora
third_party/fathom/       Fathom, vendored (Syzygy probing; MIT)
.github/workflows/        CI and the cloud SPRT shards
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
- `MoveList` is a fixed array of 323 moves with a size, stack allocated: the
  most pseudo-legal moves any position can have once `set_fen` rejects
  promoted material without missing pawns (derivation in `types.hpp`).

### 4.2 Bitboard utilities

`popcount`, `lsb`, and `pop_lsb` use `<bit>` (C++20), which compiles to
`POPCNT`/`TZCNT`. Shift helpers handle the a/h-file masks. Precomputed tables
are built at startup:
`between(a, b)` holds the squares strictly between two aligned squares, and
`line(a, b)` holds the full line through them. Both are filled by walking
the eight directions from every square. Both are used for pins and
check blocking. There are also pawn, knight and king attack tables.

### 4.3 Slider attacks: magic bitboards

- Rook and bishop masks (each ray stopping one square before the edge),
  relevant occupancy subsets (an index's bits deposited into the mask) and
  attack sets are computed by walking rays on (file, rank) coordinates.
- **Magic numbers are found at startup by Fork's own search**, using
  sparse candidates (the AND of three words) from the fixed-seed splitmix64
  stream (`splitmix.hpp`), each checked in a scratch table. Per-square seeds
  from `tools/magic_seeds.cpp` make the first or second candidate succeed.
  No published magic tables are copied. The search is deterministic and
  takes about 1.4 ms (no-PEXT builds only).
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

- Board: `by_type_[6]` and `by_color_[2]` bitboards, a `board_[64]` mailbox
  (one byte per square), side to move and fullmove number.
- **Per-ply State stack** (`std::vector<State>`, reserved up front): `make`
  pushes a copy of the current State and updates it, `unmake` pops it, so
  restoring is exact and earlier keys stay available for repetition
  detection. A State holds only what Fork's code reads (56 bytes), ordered
  by how `make` treats it: carried forward and updated in place (Zobrist
  key, castling rights, ep square, halfmove clock), recomputed from the
  board after every move (checkers, pinned pieces and discovered-check
  candidates of the side to move), and the captured piece.
- **Check information** (CPW "Checks and Pinned Pieces (Bitboards)",
  "X-ray Attacks (Bitboards)", "Discovered Check"): one x-ray computation,
  seen from each king, finds the pieces of the side to move that are the
  only piece between a king and a slider: towards its own king they are
  pinned, towards the enemy king they can discover check. Direct checks are
  answered on demand in `gives_check`. The review fix of 2026-10-24 (H3)
  replaced eager per-type check squares and unused pawn, material and
  non-pawn keys.
- A null move (make/unmake) shares the State path.
- **FEN** parse and serialize. Parsing validates the input and returns an
  error string instead of asserting, because FENs come from untrusted GUI
  input. It rejects: bad syntax or rank lengths, a count other than one king
  per side, more than 8 pawns or 16 pieces per side, more pieces beyond the
  starting set than missing pawns (promotions), pawns on the first or
  last rank, the side not to move being in check, castling rights without the
  king and rook on their home squares, and implausible ep squares (wrong
  rank, occupied, or no pawn that could have just double-pushed). The
  halfmove and fullmove fields may be omitted (they default to `0 1`);
  when present they are capped at 10000 and 100000, so `make` can never
  overflow them (review L1).
- **Draw rules** (the same definitions as python-chess, which difftest
  compares against): `fifty_move_reached()` is a halfmove clock of 100 or
  more (search must check mate first); `insufficient_material()` holds
  when neither side can mate on material alone. A side cannot mate when it
  has only its king; or only its king and one knight while the enemy has
  nothing but its king and queens; or only bishops besides its king, with
  every bishop on the board on one square colour and no pawn or knight on
  the board. This gives the same verdicts as python-chess (difftest), and
  Syzygy WDL confirms a side the rule rejects never wins
  (`tools/syzygy_insufficient.py`). Implemented as `cannot_mate(Color)`,
  written clean-room from this statement on 2026-10-24; `repetition_count()` counts earlier occurrences of the
  current key with the same side to move, looking back no further than the
  halfmove clock and the last null move: positions before a null move, and
  the position the null move creates, are not part of the game (review M2).
- **Copies.** A copied Position reserves room for 1024 more plies, so
  `make` on a search thread's copy never allocates or moves the State stack
  (review M1; `no_alloc` covers copy construction and assignment).

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
- `fork perftbench` runs the fixed perft workload (§2; `fork bench` was it
  until Phase 3 made `fork bench` the search bench); `fork version`
  prints the compiler, arch and lookup variant.

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
  tested under cutechess-cli and fastchess. **Acceptance (owner,
  2026-10-23):** `fastchess --compliance` passes, and games run cleanly
  under standard cutechess-cli (paths in `config/local-test.json`). TCEC's
  own cutechess fork is deferred until TCEC confirms which runner its
  servers use (Discord question, docs/kb/competition.md); its install step
  waits on branch `tcec-cutechess`.
  Detailed spec: §5.1.
- **Phase 3: Search.** PVS + ID + aspiration, qsearch with SEE, TT,
  ordering, pruning and extensions as listed in the brief, Syzygy
  (Fathom), deterministic `bench` (fixed positions, fixed depth, 1 thread).
  Detailed spec: §5.2.
- **Phase 4: Evaluation.** A swappable `Evaluator` interface; tapered
  PST first, then NNUE (HalfKA-style, incremental accumulator, AVX2/AVX-512 plus
  scalar) trained only on Fork self-play data, with provenance logged.
  **Before the Phase 4 spec is approved**, copy the owner's training-data
  decisions of 2026-10-24 from branch kb into it (`docs/kb/data-policy.md`,
  "Owner decisions", and `docs/kb/training-data.md`: strategy A+, own
  self-play labels only, Lichess CC0 positions as openings, Syzygy WDL
  labels, no Lc0 data, Kaggle storage and training, the Lc0 review gate).
  They were made in a KB session while main was off-limits and are not yet
  in this file. **After the network arrives**: the full re-validation of
  every search feature and the retune of eval-dependent margins (§5.2,
  Quality control 6, owner 2026-10-25); search switches stay in the code
  until it is done. **Late Phase 4, if the owner said go after the Phase 3
  pilot (deliverable 8c):** the first real campaigns of the
  heuristic-discovery loop (ideas.md idea 23), after the first strong
  network and that re-validation; afterwards a standing tool in the
  improvement pass (below).
- **Phase 5: Time management.** Soft and hard limits tuned for long
  increment games without ponder, and a stress test under artificial system
  load. Before this phase starts: research the current TCEC season's full
  rules and fill in `config/tcec.json`. **Carried over from Phase 3**
  (owner, 2026-10-27): deliverable 8's final form was checked at 40+0.4
  only briefly, stopped inconclusive (-14.8 ± 20.9 at fastchess's 400-game
  report, -4.7 ± 18.0 over all 590 games; sprt-log.md d8-ltc). Phase 5
  revisits it at long time controls, **the iteration rule first** (the
  danger-zone reserve should almost never bind at 40+0.4).
- **Phase 6: SMP.** Lazy SMP, NUMA-aware thread/memory placement, no large
  page dependence, scaling benchmark. **Shared-TT test plan** (owner,
  2026-10-24): TT entries are self-verifying (§5.2 deliverable 3), so a torn
  write reads as a miss; Phase 6 makes the entry accesses relaxed atomics
  (or equivalent) so concurrent access is not undefined behaviour, and adds
  a stress test, run under TSan, where many threads write and read the same
  buckets with random entries and every hit a reader accepts must be one
  writer's complete entry. **The spec must also settle** (owner, 2026-10-26,
  second external review): how the threads agree on the move played (the
  main thread's result, or a choice among threads by depth and score, or a
  vote), and how the threads' searches are kept diverse (different depths,
  move orders or other per-thread variation), each from the
  kb-researcher's clean-room description and measured by a scaling test.
- **Phase 7: Tournament-aware play.** Contempt/style options, TB-aware
  eval, keeping tension. Each item is documented here as genuine evaluation.
- **Phase 8: TCEC-conditions testing** from `tcec.json`: paired openings,
  adjudication, gauntlet against pinned engines, SPRT, stress testing.
- **Improvement pass** (after Phase 8; owner, 2026-10-26). The layers again,
  in dependency order: network, search, time management, threads,
  tournament behavior, TCEC-conditions validation. It repeats in rounds,
  and each round targets the layer with the best expected Elo per unit of
  effort, judged from the last round's measurements. Standing tools: SPSA
  tuning (on the parameter table, deliverable 8b) and idea 23's
  heuristic-discovery loop, if the Phase 3 pilot (deliverable 8c) was a go.
  Every change follows the same rules as in the phases (SPRT, the LTC rule,
  the originality screens, recorded justifications). **Bugs are never
  deferred to the pass:** a bug found at any time is fixed immediately,
  with its failing test first.

### 5.1 Phase 2 spec: UCI (approved by the owner 2026-10-24)

**Goal.** A UCI engine that TCEC can run for a whole event without a crash,
a hang, an illegal move or a protocol error, with every option TCEC sets.
There is still no search: `go` uses a placeholder move chooser (below) that
Phase 3 replaces. Protocol facts are from the UCI specification as
summarized in the KB (`docs/kb/uci.md` on branch kb); TCEC facts from
`docs/kb/competition.md` (sections "Engine settings", "Tablebases
available to engines", "Builds and submission", Swiss rules table).

**Module.** `src/uci/` (§8): the protocol loop, the option registry and
info output. `src/main.cpp` enters the UCI loop when started without
arguments; the existing CLI subcommands (`perft`, `divide`, `bench`,
`version`, `difftest`) stay.

#### Threads of control

- The **input thread** reads stdin line by line and is never blocked by a
  search: `isready`, `stop`, `quit` and `ponderhit` are handled while a
  search runs.
- `go` starts the search on a separate **search thread** (Phase 2: the
  placeholder; Phase 3: the search and, in Phase 6, its helper threads).
  Exactly one `bestmove` is printed per `go`, after the search has ended.
- **Output** goes through one function that writes a whole line, a
  newline and a flush under a mutex, so lines from the two threads never
  interleave and nothing sits in a pipe buffer.
- `quit` (or EOF on stdin) stops any search, joins all threads and exits
  with status 0.

#### Commands

| Command | Behaviour |
|---|---|
| `uci` | `id name Fork <version>` (version format below), `id author BOSSDOTCOM`, one `option` line per option, `uciok`. |
| `isready` | `readyok` at once, even during a search and without interrupting it; outside a search, only after pending work (Hash allocation and clearing) has finished. |
| `setoption name <N> [value <V>]` | Names may contain spaces and match case-insensitively (the spec says names should not be case-sensitive), but Fork declares each name in exactly the case TCEC types it, because fastchess matches names exactly and does not send unknown names or out-of-range spin values (docs/kb/uci.md §7). An unknown name or bad value prints `info string` and changes nothing. |
| `ucinewgame` | Clears search state (the TT from Phase 3). |
| `position startpos\|fen <FEN> [moves ...]` | Builds the position and the repetition history from the move list. An invalid FEN or an illegal move keeps the position reached so far and prints `info string`; it never crashes. Move lists of several thousand plies are fine (no fixed-size history). |
| `go [...]` | Parses every argument: `searchmoves`, `ponder`, `wtime`, `btime`, `winc`, `binc`, `movestogo`, `depth`, `nodes`, `mate`, `movetime`, `infinite`. Times are 64-bit and may be zero or negative (a GUI can send a negative remaining time). Limits combine (both runners can send `depth` or `nodes` together with clock arguments); the first one reached ends the search. `wtime`/`btime` without `movestogo` means sudden death. `go infinite` and `go ponder` never end by themselves: `bestmove` comes only after `stop` (or, for ponder, after `ponderhit` and the normal limits). A bare `go` is treated as "no limit" (an inference from the spec, UNVERIFIED in the KB); the Phase 2 placeholder answers it at once. |
| `stop` | Ends the search; `bestmove` follows promptly. Harmless when nothing runs. |
| `ponderhit` | Turns a ponder search into a normal one. Fork declares no `Ponder` option (TCEC plays with pondering off), so this only has to be harmless. |
| `quit` | As above. |
| `debug`, `register` | Accepted and ignored. |
| unknown or empty lines | Ignored (with `info string` in debug builds). |
| Fork extensions | `go perft <depth>` (§4.7), `bench`, `d` (print the board and FEN). |

Input handling: tokens are split on any whitespace; `\r` is stripped
(Windows GUIs send CRLF); a line may be very long (no fixed buffer).
Moves are long algebraic (`e2e4`, castling as the king move `e1g1`,
promotion `e7e8q`); Fork prints promotion letters in lower case and accepts
either case on input (lower case is the convention; the spec shows only
`q`).

#### Placeholder move chooser (Phase 2 only)

Picks a legal move deterministically (owner, 2026-10-24): a move that
mates in one if there is one, else the best capture by MVV-LVA (most
valuable victim first, then least valuable attacker), else the first legal
move; ties go to the first in generation order. It prints one
`info depth 1 seldepth 1 score cp 0 nodes <n> nps <n> time <ms> pv <move>`
line and `bestmove <move>`. With no legal move (mate or stalemate) it
prints `bestmove (none)`: the spec says nothing about this case and defines
`0000` only as a null move, fastchess never sends `go` in a finished
position, and python-chess reads `(none)` as "no move" (docs/kb/uci.md §7).
Its only job is to make the protocol testable; it is deleted in Phase 3.

#### Options

| Option | Type, default, range | TCEC relevance |
|---|---|---|
| `Hash` | spin, MB, default 16, min 1, max 4194304 (4 TiB; owner, 2026-10-24: 16 times TCEC's 256 GiB and above any server's RAM, chosen for Fork rather than the 33554432 first specified, which equals another engine's limit) | TCEC sets `Hash=262144` (256 GiB) and caps hash at 32 or 64 GiB unless initialization is multithreaded. Size math in `std::size_t` bytes, no 32-bit overflow. `setoption` only records the size; the table is allocated and cleared at the next `isready`, `ucinewgame` or `go`, after every option has been applied, because a GUI may send `Hash` before `Threads` and a clear started on `setoption Hash` would run on one thread (review M8, 2026-10-23). Allocated as **one block straight from the OS** (`mmap`, 2 MiB aligned, on Linux; `VirtualAlloc` on Windows), first-touch cleared **in parallel** with `max(Threads, hardware threads)` workers (but at least 2 MiB per worker, counted on the size actually allocated: review, 2026-10-24), before `readyok`. **No chunked fallback** (owner, 2026-10-24, amending the approved spec): Linux's default overcommit checks each `mmap` on its own (against RAM + swap since Linux 5.2, against free memory + swap before; never the running total), so chunks would slip past that check and the clear would then bring in the OOM killer; Windows' commit limit (RAM plus page files) is system-wide, so chunks gain nothing there either (sources: docs/kb/os-memory.md on branch kb, verified 2026-10-24). **Before allocating, the request is compared with the physical memory available now** (`MemAvailable` from `/proc/meminfo`; `ullAvailPhys` from `GlobalMemoryStatusEx`) plus the current table, which is freed first when both do not fit; a request that does not fit is never tried. If the size cannot be had, the table falls back to its previous size (else 1 MB) and `info string` says so; never an abort. `madvise(MADV_HUGEPAGE)` on Linux, but no dependence on large pages (TCEC enables them automatically). Tests: a 1 TB request and one just above available memory both fall back cleanly on Windows and Linux. Phase 2 allocates and clears the table; Phase 3 uses it. |
| `Clear Hash` | button | Clears the table (also in parallel). |
| `Threads` | spin, default 1, min 1, max 4096 (owner, 2026-10-24: 8 times TCEC's 512; nothing is sized for a fixed thread count, and a 4096-worker clear is tested) | TCEC sets 512 (two sockets). Phase 2 stores it and uses it for hash clearing; Phase 6 uses it for search, NUMA-aware. |
| `Move Overhead` | spin, ms, default 100, min 0, max 10000 (owner, 2026-10-24) | Time reserved per move for GUI and system latency; TCEC leaves options at default unless the author asks, so the default must already be safe at 30'+3". Name with a space (owner, 2026-10-24: the conventional spelling across engines); TCEC's recommended value is a Discord question (docs/kb/competition.md). Used by Phase 5. |
| `SyzygyPath` | string, default `<empty>` | TCEC sets `SyzygyPath=/home/syzygy7` in every division. Paths separated by `:` on Linux and `;` on Windows. Phase 2 stores it and reports how many table files it finds (`info string`); a missing directory is not an error. Probing (7-piece, ideas.md idea 12) is Phase 3. |
| `LogFile` | string, default `<empty>` | Optional log of all UCI input and output with timestamps, for diagnosing a TCEC game afterwards. Off by default. |

Not declared in Phase 2: `Ponder` (TCEC ponder off), `OwnBook` (engine
books are forbidden at TCEC; Fork has none), `MultiPV` (Phase 3),
`UCI_Chess960` (out of scope, §6), `UCI_Opponent` (Phase 7, idea 8).

Option names were checked against Stockfish's source as §8 requires
(2026-10-24, count-only `grep -rlw` over a shallow clone at effdc3f):
`Hash`, `Clear Hash`, `Threads`, `Move Overhead` and `SyzygyPath` match,
as expected, and are kept on purpose: they are the cross-engine
conventions TCEC and the runners type (docs/kb/uci.md §5). `LogFile` is
Fork's own spelling. Every new identifier in the code (about 60) had zero
distinctive matches; the hits were protocol or plain English words. The
option limits were first specified equal to Stockfish's; the owner chose
Fork's own (rows above). Boundary tests: the minimum and maximum of each
spin option are accepted, one past either end is rejected with an
`info string`, and the 4 TiB Hash falls back cleanly.

#### TCEC requirements and how Phase 2 meets them

| Requirement (KB) | Phase 2 answer |
|---|---|
| UCI or XBoard protocol | UCI, tested with fastchess and cutechess-cli. |
| Threads up to 512, Hash up to 256 GiB with multithreaded init, 320 GiB RAM cap | `Threads` max 4096; parallel hash clearing; no other large allocations. Tested locally at the largest size this machine allows, and the size arithmetic tested at 262144 MB without allocating. |
| 7-man Syzygy through `SyzygyPath=/home/syzygy7` | Option accepted and stored; probing in Phase 3. |
| Pondering off, engine books forbidden | No `Ponder`, no `OwnBook`, no book code. |
| Options default unless the author asks | Defaults are tournament-safe (`Move Overhead`, `Hash` sized by TCEC anyway). |
| A crash is a loss, no fixes once an event starts, time losses stand | Robust input handling, no exception escapes, stop and isready answered during search, fuzzed parser, sanitizer and TSan runs of the UCI tests. |
| Category 4: public source, TCEC builds the binary from the repository | Builds from a clean clone on **TCEC's toolchain**, not only on current compilers: Ubuntu 22.04 with gcc 11.4, g++-12, clang 16 and 19 (competition.md "What this means for Fork"; wiki Further information page per the 2026-10-23 review). That means CMake 3.22 or a documented way around it, no C++20 library features missing from libstdc++ 11/12 (`<format>` today, review C1), and a minimum-toolchain build in the sign-off checks. An `update.sh` that clones and builds the TCEC binary (the Further information page allows one) with an explicit `-march` instead of `native` (the CPU and GPU servers are different Zen generations), tests off, no configure-time downloads, debug info kept. `id name` carries the version (from `git describe` at configure time, with a fallback when built from a tarball). |
| TCEC recommends keeping debug info in the optimized binary | `update.sh` builds with `-g`, and so do the release presets (owner, 2026-10-24; debug info only, no other flag change; bench nps checked with `bench/ab.py`). |

#### Tests and acceptance checks

1. **`uci` test suite (ctest)** that drives `fork` through pipes: each
   command and argument above; `setoption` with spaces, odd case, unknown
   names and bad values; `isready` during `go infinite`, then `stop`; `stop`
   and `ponderhit` with no search; `go` twice in a row; `quit` during a
   search; EOF on stdin; CRLF input; a `position` with a several-thousand-ply
   move list; an illegal move and a malformed FEN; `Hash` 1 MB and large;
   `Threads` 1024; exactly one `bestmove` per `go`; `bestmove (none)` on
   mate and stalemate positions; a final `info` line before every
   `bestmove`.
2. **Timing checks:** `uci` to `uciok` and `isready` to `readyok` under
   50 ms at default settings; `stop` to `bestmove` under 10 ms; hash clear
   time at 1, 4 and 16 GiB recorded per thread count.
3. **fuzz_uci**: a libFuzzer target over the command parser. Refined by the
   owner (2026-10-24): the parsers in isolation, with no search threads
   (`SessionConfig::use_threads` off: go is answered on the calling thread,
   the Hash cleared there); every command covered, including position with
   long move lists, setoption with multi-word names, all go arguments and
   unknown or malformed input; hand-written seeds, one per command
   (`fuzz/corpus/uci/seed-cmd-*`); the coverage-plateau rule. Besides no
   crash, hang or sanitizer report, it checks that every printed line is a
   valid UCI engine message and that a line without a command prints
   nothing (debug builds: only `info string unknown command: ...`).
4. **Sanitizers:** the `uci` suite under ASan/UBSan (both platforms) and
   TSan (Linux); no_alloc keeps covering the core.
5. **TCEC-toolchain build:** `update.sh` builds and `fork bench` matches
   `tests/bench.ref` in an Ubuntu 22.04 environment with gcc 11.4,
   g++-12, clang 16 and clang 19.
6. **`fastchess --compliance ./fork`** passes on Linux (release and the
   ASan debug build). Note that it does not check `setoption`, `go
   depth/nodes/movetime/infinite`, `stop`, ponder, `quit` or MultiPV
   (docs/kb/tools.md, fastchess), which is why test 1 exists.
7. **Clean games under standard cutechess-cli** (and the same under
   fastchess): Fork against itself, at least 200 games at a fast increment
   time control plus 50 games each with `movetime` and `depth` limits, with
   concurrency: zero crashes, disconnects, illegal moves or time forfeits,
   and every game ending by the rules.
8. All presets on Windows and Linux, `scripts/check.sh full`, bench
   unchanged (bench stays the perft workload until Phase 3).

#### Deliverables (one commit each)

0. TCEC-toolchain build: `update.sh` and the Ubuntu 22.04 compiler check.
   Done as Phase 1 review fix C1 (2026-10-24, §2 "TCEC build").
1. `src/uci/`: input loop, output function, threads of control, commands.
2. Option registry and options, including hash allocation and parallel
   clearing.
3. Placeholder move chooser and `info` output.
4. `uci` ctest suite, timing checks, `fuzz_uci`.
5. fastchess compliance and the cutechess-cli/fastchess game runs
   (results recorded), sanitizers, all presets on both platforms, summary,
   stop.

#### Implementation notes (2026-10-24)

Choices made while building, where the spec leaves a gap:

- **Files.** `src/uci/session.*` (loop, commands, search thread),
  `options.*` (option table), `go_limits.*` (`go` parser), `output.*`
  (the one output path and the LogFile), `tokens.hpp`, `placeholder.*`
  (deleted in Phase 3), `version.cpp`; `src/search/hash_memory.*` holds the
  table memory that Phase 3's TT will use.
- **A command that arrives during a search** and changes what the search
  depends on (`position`, `ucinewgame`, `setoption`, `go`, `bench`,
  `go perft`) first stops and joins the search, as if `stop` had come
  first; its `bestmove` is printed before the command takes effect. GUIs
  never do this (the spec says `setoption` only comes while idle), but it
  keeps "one `bestmove` per `go`" and stops the state from changing under
  a search. `isready`, `stop`, `ponderhit`, `quit` and `d` do not stop it.
- **`isready` while idle** first joins a finished search thread and does
  the pending Hash work, so `readyok` means that work is done.
- **Fork extensions print only `info string` lines**, so every line on
  stdout in UCI mode is a valid engine-to-GUI message (the tests check
  each line).
- **`searchmoves` with no legal move in it** (python-chess sends
  `searchmoves 0000` for an empty list) searches every move, with an
  `info string`, rather than returning no move.
- **The Hash allocation is reported** as `info string Hash <N> MB
  allocated and cleared in <ms> ms by <W> threads` when it happens (first
  `isready`/`ucinewgame`/`go`, and after a Hash change); clears report
  nothing.
- **Unknown leading tokens are skipped** (`xyzzy isready` answers
  `readyok`), as the spec's `debug on` example describes.
- **Out of memory never costs a `bestmove`** (review, 2026-10-24): if an
  allocation fails while a `go` is being handled (tokenizing, the search
  thread's copy of the position, starting the thread) or while the search
  thread formats its output, the go is answered from fixed buffers with a
  scored `info` line and a real `bestmove` (the move found, or the first
  legal move), never with nothing and never with `(none)` while legal moves
  exist. A `go infinite` that cannot start its thread is answered at once.
  Tested by `uci_oom`, which fails each allocation of a `go` in turn.
- **Hash clear workers** are counted from the table actually allocated, so a
  refused Hash that falls back to 16 MB is cleared by at most 8 threads
  (review, 2026-10-24; it was 1024 with `Threads` 1024).
- **Phase 3 note on the 4 TiB maximum:** the TT index must be computed in
  64-bit arithmetic over an entry count of up to 2^42 / entry size (more
  than 2^32 entries), with a test at the maximum entry count.

#### Owner's answers (2026-10-24)

1. Option names: `Move Overhead` (with a space, conventional across
   engines) and `LogFile`.
2. `Move Overhead` default 100 ms; TCEC's recommended value is added to
   the Discord questions.
3. Placeholder: mate in one, else best MVV-LVA capture, else the first
   legal move (deterministic).
4. Version string: `Fork <semver>-dev+<short commit>` (e.g.
   `Fork 0.2.0-dev+abc1234`), from git at configure time, with a fallback
   when built without git.
5. `-g` in release builds: yes (debug info only).
6. `id author BOSSDOTCOM`.

Before Phase 2 starts, the Phase 1 review fixes come first (owner,
2026-10-24): the TCEC toolchain build (deliverable 0 above), the
clean-room originality rewrites, the medium and low findings, the
deferred tests and suspicions, and ORIGINALITY.md.

### 5.2 Phase 3 spec: search (approved by the owner 2026-10-24)

**Goal.** Replace the Phase 2 placeholder with a real alpha-beta search:
the tier 1 core first, then the tier 2 refinements one at a time. Every
technique stays only if it passes SPRT. **Phase 3 settles structure, not
final tuning**: each technique gets its shape, gating, flag, tests and a
reasonable default chosen by Fork, and the tuning campaigns come after
Phase 4. Phase 4 replaces the evaluation and changes its scale, so every
eval-tied margin (RFP, futility, NMP gate, ProbCut, SEE thresholds) will
need retuning then anyway.

**Sources.** Technique descriptions come only from the clean-room file
`docs/kb/search-techniques.md` (branch kb, 2026-10-24; IDs T1-T49 below are
its IDs) and the primary papers it cites. **No engine's source code is
opened in Phase 3**, by the implementing session or any helper, except the
throwaway name-check clone of §8. The identifiers that file lists as
off-limits are never used, in any case or spelling: `statScore`, `ttPv`,
`cutNode`, `Stack` (as the search stack type), `nmpMinPly`,
`singularBeta`, `opponentWorsening`, `hindsight`, `doDeeperSearch`,
`doShallowerSearch`, `BadNoisy`. Every new reference consulted goes into
ORIGINALITY.md when it is first used.

**Out of scope.** Tier 3 techniques (T34-T49), except mate distance pruning
(T33), which the KB says to add with the core because it is cheap. Killers
(T45) and countermoves (T46) are not built; they come back only if the
histories turn out weak, as their own SPRT. SMP is Phase 6: Phase 3 searches
on one thread and ignores `Threads` (Phase 2 uses it only for Hash
clearing), but it keeps all search state in a per-thread object, so Phase 6
adds threads without restructuring. Full time management is Phase 5:
Phase 3 builds only the basic budget (deliverable 8). Final parameter
tuning comes after Phase 4.

#### Module layout and names

| File | Contents |
|---|---|
| `src/eval/bootstrap_eval.*` | the bootstrap evaluation (deliverable 1) |
| `src/eval/eval_scale.hpp` | `EvalLimit`, the range every evaluator stays within (audit-1 F-12) |
| `src/core/material.hpp` | `MaterialCp`, `piece_value`, `game_phase`: the material scale SEE, move ordering, the LMR context and the bootstrap evaluation share, kept outside the evaluator (audit-1 F-12) |
| `src/search/searcher.*` | `Searcher` (per-thread search state and the recursion), `SearchQuota`, `SearchResult`, `PlyFrame` (one search-stack entry per ply), `RootEntry`; the node type is the template parameter `OnPv` (the `NodeKind` planned here was not needed) |
| `src/search/trans_table.*` | `TransTable`, `TtEntry`, `TtBucket`, `TtBound`, `score_to_tt` / `score_from_tt` |
| `src/search/see.*` | `see_at_least(pos, move, threshold)` |
| `src/search/move_selector.*` | `MoveSelector`, `SelectorStage` (the staged picker) |
| `src/search/quiet_history.hpp` | `QuietHistory` (deliverable 5); `CaptureHistory` and `ContHistory` come with tier 2 |
| `src/search/time_budget.*` | `TimeBudget` (soft and hard limits) |
| `src/search/endgame_tables.*` | `load_endgame_tables`, `probe_table_wdl`, `rank_root_by_tables`: the only code that calls Fathom |
| `src/tune/params.*` | `ParamTable`, `TuneParam` (DESIGN.md §1) |
| `third_party/fathom/` | Fathom, vendored at a pinned commit with its LICENSE (deliverable 7) |

The names above were checked against Stockfish dbe600b on 2026-10-24 by a
throwaway research subagent (§8 procedure; clone deleted before it
reported). All of them had no match. These candidates matched and are
**not used**: `RootMove`, `MovePicker`, `see_ge`, `ContinuationHistory`,
`CorrectionHistory`, `probe_wdl`, `Reductions`, `value_to_tt`,
`value_from_tt`, `mate_in`, `mated_in`, `evaluate`, `improving` (as an
identifier; the concept is fine), and the file basenames `search`, `tt`,
`history`, `timeman`. Any name added while building goes through the same
check first.

#### Deliverables in build order

Each deliverable is one or more commits, behind flags where it adds a
technique, with its tests, its SPRT results and its performance gate
(Quality control below). Milestones A, B and C are the only planned stops
for the owner's review.

**1. Bootstrap evaluation.** A deliberately simple, deterministic
evaluation, from the side to move's view, good enough to make the search's
results meaningful until Phase 4:
- material on a 100/300/300/500/900 centipawn scale (Fork's choice; the
  conventional 1/3/3/5/9 ratios, to be cited from a primary source when
  written, non-negotiable 1);
- a small centralization term for knights, bishops and the king in the
  endgame, computed from a distance formula, not from tables;
- with no pawns on the board and a clear material lead, a term that drives
  the losing king to the edge and the winning king toward it, so the
  search can play out mates such as KRK without tablebases;
- insufficient material scores as a draw (`cannot_mate`, Phase 1).

It is called directly, a plain function with no virtual dispatch (hot-path
rule 3). **The evaluator is selected at build time, with no indirect call**
(owner, 2026-10-24): Phase 4's "swappable Evaluator" is a build option, not
a runtime interface. Test: symmetry, the
colour-flipped position gives the negated score on every perft-suite node.

**2. Core search** (T1, T2, T5, T6, T33).
- **Negamax, fail-soft** alpha-beta, an explicit PV/non-PV flag passed down
  (T5 conditions), **PVS**, **iterative deepening** and **aspiration
  windows** (narrow window around the previous score; only the failing side
  widens, geometrically; decisive scores open the window fully).
- **Scores** in a 16-bit-safe range of Fork's own choosing: a mate at ply n
  scores `MateScore - n`, tablebase wins sit in a band below the mate band,
  and draws score 0. Mate distance pruning (T33) clamps the window to the
  mate bounds at each ply.
- **Draws in the tree**: insufficient material; the 50-move rule (mate is
  checked first, as Phase 1 requires); and a repetition, meaning any
  earlier occurrence of the position within `repetition_count()`'s range,
  scores as a draw at non-root nodes. Fork's choice: one repetition is
  enough inside the search, and the game itself still needs three.
- **Search stack**: a fixed array of `PlyFrame`, one per ply up to a fixed
  maximum ply that the max-ply stress test checks. Each frame holds the
  static eval (absent in check), the move played, the moved piece and its
  destination (for continuation history later), the excluded move (T27
  later) and node flags. The PV is collected from exact results only.
- **Root**: the root move list honours `searchmoves`. The best move from
  an unfinished iteration is used only if it came with an exact score
  above the previous iteration's best; otherwise the last finished
  iteration's best move stands. The flow of `go depth/nodes/mate/movetime/
  infinite` and `stop` is Phase 2's, now driving the real search.
- **UCI output**: one `info` line per finished iteration (`depth seldepth
  score cp|mate [lowerbound|upperbound] nodes nps time hashfull tbhits
  pv`), with aspiration fails printed only once the search has run for a
  while (Fork's choice: 1 s), then `bestmove`. MultiPV is deferred to
  Phase 7 (owner, 2026-10-24).
- **Search bench** (replaces the perft bench; Testing setup below).
- **Tooling**: `fork` reports its build identity (variant, commit) the way
  `fork_micro` does, so `bench/ab.py` (or a sibling script with the same
  identity checks) can compare search nps from interleaved `fork bench`
  runs.
- Deletes `src/uci/placeholder.*`, its test and `tools/placeholder_check.py`.

**3. Transposition table** (T4), on Phase 2's `HashMemory`.
- **Layout (Fork's own)**: one 64-byte bucket per cache line, holding 5
  entries of 12 bytes plus 4 spare bytes. Each entry holds a 32-bit word of
  24 key-check bits and the 8-bit age of the search that wrote it, a 16-bit
  move, a 16-bit score, a 16-bit static eval (unused until a later
  deliverable needs it; it is there so Phase 4 does not need a new layout),
  an 8-bit depth, and 8 bits of flags: the bound (2) and the TT-PV flag (1,
  T19). The entry size is an A/B experiment, not a fixed belief.
  *Amended 2026-10-24 after the Milestone A originality check* (the first
  layout's packed bound/PV/5-bit-age byte matched other engines'): 24
  check bits instead of 32 and a whole age byte (wrapping at 256 searches,
  not 32). **Self-verifying entries** (owner, 2026-10-24, for Phase 6): the
  stored check is the key's 24 bits XORed with a 24-bit digest of the
  entry's other fields, so a torn write (words from two writes) fails the
  check and reads as a miss; a 12-byte entry cannot be stored atomically
  on x86-64. Tested by splicing two writes at every 4-byte boundary.
- **Index**: the bucket comes from the 64-bit key by a multiply-high range
  reduction (Lemire's method, to be cited from its primary source), in
  64-bit arithmetic, so the 4 TiB maximum (more than 2^32 buckets) works.
  This is tested arithmetically at the maximum bucket count, without
  allocating (§5.1 note).
- **Probe and store**: a cutoff only at non-PV nodes, with sufficient
  depth and a bound that points the right way; mate and TB scores
  converted by ply on store and on probe; the TT move validated with
  `is_pseudo_legal` and `is_legal` before use. Replacement (redesigned
  2026-10-24 from the KB's description: "prefer deeper and current-age
  entries, replace stale ones"): the position's own entry is overwritten
  unless it is from this search, deeper, and the new result inexact (it
  keeps its move if the new search found none); otherwise an empty slot,
  else the least valuable slot, where every entry of an earlier search
  ranks below every entry of this one and, within each group, shallower
  ranks lower.
  Qsearch entries are stored with the lowest depth. An entry is always
  written whole, which Phase 6 needs for lockless access.
- **Prefetch** of the child's bucket via `predicted_key(move)` before
  `make` (§7 Memory).
- `ucinewgame` and `Clear Hash` keep clearing it in parallel (Phase 2);
  each `go` advances the age.

**4. Quiescence search and SEE** (T3, T7, and qsearch SEE pruning from T23).
- **SEE**, threshold form `see_at_least`, written by Fork from the T7
  description: least valuable attacker first, x-rays rejoin, the king
  captures only onto undefended squares, and either side may stop. Fork's
  documented promotion rule: the move being judged counts its promotion
  gain, and later recaptures do not promote. Pin-awareness is an
  experiment (KB §6 item 10): built off first, then measured.
- **Qsearch**: stand-pat (off in check), captures and queen promotions
  ordered by MVV-LVA, all evasions in check (mate detected when there are
  none), TT probe and cutoffs at non-PV nodes, captures that lose by SEE
  skipped. No checks in qsearch (the KB notes they were removed elsewhere
  at no cost; an experiment flag only).
- Tests: SEE on constructed positions with hand-derived results, and
  randomized differential testing against a slow reference (a full
  capture-only minimax on one square, written by Fork with the same rules);
  the threshold property (the sign agrees at every threshold); qsearch
  values on constructed exchange positions checked with python-chess.

> **Milestone A** (stop for the owner's review): deliverables 1-4 done;
> Fork plays real chess. Report: SPRT of the search against the placeholder
> (a sanity check, expected to be a huge gain), each deliverable's
> performance gate, the correctness suite, and games under fastchess and
> cutechess-cli with no crashes or time losses.

**5. Move ordering** (T8, T9). No killers, no countermoves.
- **Staged `MoveSelector`**: the TT move, then good captures (SEE at or
  above zero, by MVV-LVA; capture history replaces the LVA part in tier 2,
  T11), then quiets by butterfly history, then bad captures and
  under-promotions. In check: evasions, captures first, then quiets by
  history. Picking is a partial selection sort, and the TT move is never
  produced twice. Generation reuses Phase 1's `Captures` and `Quiets`
  modes, so only the stages that are reached get generated.
- **Butterfly history** (T9) by side, from-square and to-square: a bonus
  for the quiet move that cuts, growing with depth and capped; a malus for
  the quiets tried before it; a self-limiting gravity update, so values
  stay bounded. Integer widths are chosen so that summed tables cannot
  overflow. Whether histories are kept, aged or cleared between moves is
  Fork's choice, tested.
- Tests: an exhaustive picker test over the perft suites, where the picker
  yields exactly the legal moves, each once, in every stage combination,
  with a valid, an illegal and a bogus TT move. Update-rule unit tests
  (bounded for any sequence, monotone). Counters: the share of cutoffs on
  the first move, and the average index of the cutoff move.

**6. Tier 1 pruning and reductions**, one SPRT per technique, in this
order (KB build-order steps 4-6, minus the tier 2 items):
- **RFP** (T20): non-PV, not in check, shallow depth, a margin that grows
  with depth; never returns a mate score.
- **Null move pruning** (T13): non-PV, not in check, not after a null
  move, not in an excluded search, non-pawn material for the side to move,
  static eval at or above beta, beta not a mate score, a reduction that
  grows with depth and with the eval surplus, unproven mates not returned.
  The high-depth verification (T14) follows in tier 2.
- **LMR, base form** (T15): reduction from a precomputed table shaped as
  the product of two logarithms of depth and move number, clamped to at
  least one ply and below the full depth; re-search at full depth with the
  zero window, then at PV nodes with the full window.
  **Determinism rule:** the table must come out identical on every
  compiler, libm and architecture, or bench parity breaks. So it is built
  either with integer arithmetic only, or from `std::log` with a test that
  pins its checksum on every preset. No floating point anywhere else in a
  search decision.
- **Late move pruning** (T21): shallow depth, quiets only, a count that
  grows with depth. The legal-move count is kept apart from the
  searched-move count, so pruning never fakes a stalemate.
- **Futility pruning** (T22): shallow depth, quiet, non-checking moves,
  eval plus a margin at or below alpha, the best score raised to the
  futility value when pruning.
- **SEE pruning in the main search** (T23): shallow depth, separate
  thresholds for quiets and captures, growing with depth, after at least
  one move has been searched.
- Tests: the false-stalemate unit test (a position with only quiet legal
  moves at low depth); the tactical and mate suites at fixed nodes after
  each technique (Testing setup); prune and re-search counters.

> **Milestone B** (stop): deliverables 5-6 done. Report: each technique's
> SPRT (STC and LTC where the rule below applies), node counts and nps,
> tactical solve rates, and the queued experiments, run here because the
> hot path is now representative.

**7. Syzygy probing, designed for 7 pieces** (ideas.md idea 12).
- **Library**: Fathom, jdart1/Fathom at commit c9c6fef0 (KB tools.md §6,
  MIT), **vendored** in `third_party/fathom/`, because `update.sh` allows no
  configure-time downloads. It is built as a separate target, with its
  warnings handled there, so Fork's own `-Werror` stays. Its lineage
  (probing code from Ronald de Man's `tbprobe.c` via Cfish, a Stockfish
  derivative; board code from Basil's original Fathom) goes into
  ORIGINALITY.md under Third-party libraries (owner, 2026-10-24).
- **To settle before coding** (kb-researcher, primary sources only): that
  this Fathom commit probes 7-piece tables, and how its largest piece count
  is reported; whether its file mapping can take `madvise(MADV_RANDOM)` on
  Linux (TCEC asks this of 7-man users) and what change, if any, that needs
  in the vendored code, recorded as a diff; and its Windows mapping path,
  for the second platform.
- **Init** once per `SyzygyPath` change, outside any search. The piece
  limit comes from the tables actually found (3-7), never hard-coded, and a
  missing file is "no result", never an error.
- **In search**: WDL probes at non-root nodes within the piece limit, with
  zero castling rights and a zero halfmove clock (Fathom's conditions, KB
  techniques.md), above a minimum depth (a tunable parameter, not a UCI
  option). Wins and losses map to the TB band, cursed wins and blessed
  losses to scores just off zero, and the TT stores the result as a bound.
  `tbhits` is counted.
- **At the root**: when the root is in the tables, the DTZ root probe
  (once per search, on the search thread; it is not thread-safe) keeps
  only the moves that preserve the best WDL result under the 50-move rule
  and ranks them, then the search runs on those moves. The fallback when
  DTZ is missing is a WDL ranking. TCEC plays the 50-move rule, so the rule
  is always on; no Syzygy UCI options beyond `SyzygyPath` (owner,
  2026-10-24).
- **Thread safety for 512 threads** is a Phase 6 test, but nothing here
  may assume one thread: no shared mutable state outside Fathom's
  thread-safe WDL path.
- Tests: Fork's probes against the `fathom` command-line tool on the
  locally installed 3-4-5 tables, over many positions; 7-piece positions
  against the lichess tablebase API, with answers fetched once, cited and
  cached; one small 7-man table pair (KPPPPPvK: 3,721,360 and 1,652,304 bytes,
  pinned in CMakeLists.txt; ORIGINALITY.md); a missing file, an empty path
  and a path with only some files; the won-ending conversion suite (TB-won
  positions near the 50-move limit, played out against a TB-perfect
  defender, share converted); all presets on both platforms.

**8. Basic time management.** `TimeBudget` turns `wtime/btime/winc/binc/
movestogo/movetime` and `Move Overhead` into a soft limit (checked between
iterations: don't start an iteration that probably won't finish) and a hard
limit (polled in the search every fixed number of nodes). These are
conservative fixed formulas; nothing is tuned (that is Phase 5). Tests:
games at very short time controls and under full CPU load (Phase 2's
2+0.02 setup) with zero time losses; `movetime` overrun stays within a
stated bound; `stop` to `bestmove` latency under 10 ms with the real search
(the Phase 2 timing test).
- **Confirmed defect to fix here** (external review claim (b), 2026-10-26,
  reproduced by calling `plan_time`): the increment term divides before it
  multiplies (`increment / 4 * 3`), so an increment of 1-3 ms adds nothing
  to the soft budget and others lose up to 3 ms (7 ms adds 3, not 5.25;
  10 ms adds 6, not 7.5). The fix comes with a test of exact small
  increments.
- **Baselines** (owner's queue, 2026-10-26): 2,000 games at 2+0.02 with
  every CPU busy, 0 time losses (Milestone A: 1 in 200); LTC 40+0.4: 0 time
  losses in 1,867 SPRT games.

> **Milestone C** (stop): deliverables 7-8 done; the core of Phase 3 is
> complete. Report as for Milestone B, plus the TB tests, the conversion
> suite and time-loss counts.

**8b. Parameter table** (owner, 2026-10-25), after Milestone C and before
any tier 2 refinement or SPSA tuning: `src/tune/params.*` (DESIGN.md §1),
one table of every numeric search parameter (name, default, min, max, SPSA
step). Release and TCEC builds compile the defaults in as constants; tuning
builds (`FORK_TUNE`) declare each as a UCI spin option, beside the switches.
Moving a parameter into the table must not change bench. No SPSA run may
start before the table exists.

**8c. Pilot of the heuristic-discovery loop** (ideas.md idea 23, the
consolidated spec of 2026-10-26; owner).
- **Slot:** after Milestone C and the parameter table (8b), before tier 2
  (deliverable 9). Time box about two weeks. **Target:** the LMR formula
  only, as the one evolvable region; a candidate touching code outside it
  is rejected before building.
- **Prerequisites:** 8b done; the kb-researcher has verified the
  AlphaEvolve, FunSearch and MAP-Elites papers (primary sources, cited in
  the KB and ORIGINALITY.md); run when weekly Claude capacity is fresh.
- **Method** (idea 23): residual mode by default (final = base + correction,
  with its own strength coefficient for SPSA; a zero correction reproduces
  the baseline exactly), about 1 in 5 candidates full replacements; an
  island/MAP-Elites population; two proposers with distinct perspectives
  (optionally a third from Fork's search statistics), an explorer with its
  own protected island, a critic before every build, an analyst every N
  generations, the originality-checker on promoted survivors, and a
  deterministic orchestrator script; all agents clean-room. The evaluator
  funnel: the gate (build, perft, the minimax oracle with pruning off,
  determinism, the hot-path rules); proxies (best-move agreement and score
  error against Fork's much deeper search at equal node budgets, on a
  held-out self-play set labeled by Fork's own search; nodes to depth only
  as a secondary signal; WAC and matetrack excluded); a short fast-game
  match; the full SPRT on gainer bounds, STC then LTC.
- **Metrics:** whether proxy rankings predict SPRT outcomes; the cost per
  accepted change (compute, games, tokens, session time); the gate-failure
  rate with and without the critic; the improvement rate against a
  single-proposer baseline; the explorer's survival rate and SPRT wins;
  residual against full-replacement results.
- **Ends with a go/no-go decision by the owner** (stop).
- **If go:** real campaigns in late Phase 4, after the first strong network
  and the search re-validation; then a standing tool in the improvement
  pass (roadmap, §5), with candidate targets such as pruning margins,
  history updates, move ordering and time management. **If no-go:** the
  loop is archived, and its log and findings go into ideas.md.

**9. Tier 2 refinements**, built one at a time, each behind a flag and
SPRT-tested on its own, **reported in batches at the end of Phase 3**, not
individually. The order follows the KB's build order (steps 5 and 7-10),
with the owner's changes of 2026-10-26 (second external review): Fork has
neither singular extensions nor check-aware reductions yet, so checks come
first, and the quiescence delta pruning moves up. Every new technique gets
the kb-researcher's clean-room description (KB search-techniques.md) before
it is built.
0. **Checks first:** check-aware late move reductions (checking moves and
   in-check nodes reduced less) or a check extension, whichever the
   description and a first SPRT favour, then the other on its own SPRT; then
   quiescence delta pruning (moved up from step 5's qsearch futility).
1. T18 improving (per use: RFP, LMP, LMR, NMP gate), T26 IIR.
2. T10 continuation history (1-ply, then 2-ply, then deeper, each its own
   SPRT, watching nps), T11 capture history, T24 quiet history pruning.
3. T17 node-type tracking, T19 TT-PV flag, then the T16 LMR adjustments
   one at a time (history, improving, expected cut node, PV/TT-PV, TT move
   is a capture, captures, gives check, deeper/shallower re-search).
4. T27 singular extensions (with the excluded-move search, which neither
   probes as nor overwrites the real entry), then T28 multi-cut, T29 double
   and triple extensions with a per-line cap, T30 negative extensions.
5. T31 ProbCut, T32 correction history (one table at a time: pawn,
   non-pawn per side, minor, continuation), T25 qsearch futility, T14 NMP
   verification at high depth (zugzwang insurance for TCEC endgames, on
   non-regression bounds, tested on cited zugzwang positions). New
   candidates (owner, 2026-10-26): razoring, and futility pruning of losing
   captures in the main search.
6. T12 pawn-structure history, last, because it needs a pawn key.

**The pawn key** (for T12 and T32) and the non-pawn keys (for T32) are a
`src/core` change: Phase 1's H3 rewrite removed them because nothing used
them. They are re-added only with a consumer, designed by Fork from
Fork's own Zobrist keys, measured for make/unmake cost with `bench/ab.py`,
and they trigger the fuzz rule for `fuzz_fen` and `fuzz_moves`. A
correction-table bound and clamp keep the corrected eval out of the mate
and TB ranges; the raw eval is kept for anything that might later feed
training (Phase 4 data policy).

#### Testing setup

**SPRT.** fastchess (`~/fork-tools/bin`, config/local-test.json) on Linux
(WSL), game pairs with colours reversed, pentanomial statistics
(`-report penta=true`), normalized Elo (fastchess's default model),
alpha = beta = 0.05. Bounds (owner, 2026-10-24), in normalized Elo:
- gainers until Milestone B: [0, 5], since gains are large early;
- tier 2 gainers: [0, 3];
- simplifications and safety features (T14, removals): non-regression
  [-3, 0].

**Bounds policy (owner, 2026-10-26):** the kind of change decides the
bounds. **Bug fixes, speed-only changes, simplifications and safety
guards** use non-regression bounds [-3, 0]: they must not lose, and need
not prove a gain. **New features and techniques** use gainer bounds, [0, 3]
(or [0, 5] where gains are large, as before Milestone B). Applied first to
the external reviews' queue: the root fail-high fix and the futile-node
filter [-3, 0], the TT-refined pruning eval [0, 3], keeping exact TT entries
(a safety guard) [-3, 0].

Conditions: **STC** 8+0.08 s, Hash 16 MB; **LTC** 40+0.4 s,
Hash 64 MB; one thread per engine, 3-4-5 Syzygy for both sides (owner,
audit-1 Phase C: `tools/sprt.sh` passes `option.SyzygyPath` from
config/local-test.json to both engines, `TABLES=0` opts out; the cloud
shards get the set from the Actions cache or the lichess mirror, checked
against `tools/cloud/syzygy-345.sha256`; the SPRT log entry and the shard
results record whether tables were on. The SPRTs between deliverable 7 and
this fix ran without tables, except mc-tables' test side); concurrency 5 (the 7600X3D's 6 physical cores minus
one, since the machine is shared). Openings: UHO_Lichess_4852_v1.epd (KB
tools.md), **test openings only, never training data** (owner,
2026-10-24; KB data-policy.md decision 6), with its SHA-256 and source in ORIGINALITY.md
under Test-only tools, like idea 7's rule for engine-evaluated books.
`tools/make_openings.py` is the fallback. A script (`tools/sprt.sh`) builds both commits with the TCEC build, checks the
identities, runs fastchess from a JSON config and appends one line per
test to `docs/history/phase-3/sprt-log.md` (change, commits, bounds, TC,
games, pentanomial counts, Elo with error, LLR, verdict). Throughput was
measured on the first SPRTs (below). An
LTC SPRT can take a day or more, and only one heavy job runs at a time.
**Cap** (owner, 2026-10-25): an SPRT that has not decided after 20,000
games at STC (10,000 at any other time control; `MAX_GAMES` overrides)
stops and is logged as **inconclusive**, for the owner to decide on. For
techniques expected to be near zero in Elo (mate distance pruning,
possibly aspiration windows), an inconclusive result at the cap is
acceptable for Milestone A (owner, 2026-10-25). **Concurrency 10**
(owner, 2026-10-25, raised from 5 for the remaining Milestone A SPRTs; 8
if time losses ever appear): measured on the first 505 games of the PVS
SPRT at STC, 1,478 games per hour (about 790 at concurrency 5) with 0 time
losses and no illegal moves, crashes or disconnects; still 0 time losses
over all 943 concurrency-10 games by 2026-10-25 (634 PVS, 309 aspiration;
checked in both the fastchess logs and the PGN terminations). The external
reviews' queue runs at concurrency 8 (owner, 2026-10-26), so development
can run beside it; once that queue is empty, SPRTs return to 10
(`tools/sprt.sh`'s default). **Development beside test games** (owner,
2026-10-26): builds, tests and checks keep normal priority; the timing
tests skip while games run (`build/.games-running`, `FORK_GAMES_RUNNING`);
after any time loss, development drops to low priority
(`build/.low-priority`, `scripts/env.sh`) until those games end. Speed
measurements wait until no SPRT is running.
**Adjudication** (owner, 2026-10-25), in `tools/sprt.sh`, the same for
both engines (`ADJUDICATE=0` turns it off): resign once both engines report
at least 1000 cp for one side for 5 consecutive moves; draw from move 40 on
once both report |score| <= 10 cp for 10 consecutive moves. Validated by
re-running the PVS SPRT (bea68ed, STC): H1 again, +106.9 ± 22.8 Elo over
640 games, against +109.8 ± 24.0 over 634 without adjudication. **The gain
is nil at these thresholds**: 58% of games ended by adjudication, but those
games still averaged 104 plies (107-109 otherwise), mean game time 23.6 s
against 23.7 s, and throughput stayed at 1,478 games per hour. With the
bootstrap evaluation a two-sided 1000 cp score usually means mate is a few
moves away, and late moves use little more than the increment. Kept on (it
costs nothing and will matter more with a stronger evaluation); looser
thresholds would need their own validation.

**Long time controls.** No search change is rejected on short time
control results alone.
- **Straight to LTC** (the research flags these as long-time-control
  sensitive, KB §1 lesson 3 and the entries): correction history (T32),
  all extensions (T27-T30, and T38-T41 if ever tried), IIR (T26), TT-PV
  uses in pruning and reductions (T19, T16's TT-PV adjustment), and capture
  history (T11; Weiss #428 failed STC and passed LTC).
- **Everything else**: STC first. An STC pass is accepted for changes that
  don't alter tree shape (ordering scores, speed, eval); a change to
  pruning, reductions or extensions is also confirmed at LTC (KB tests
  rule). **An STC failure gets an LTC retest before it is rejected**, and
  the LTC result decides. One recorded exception (owner, 2026-10-27):
  rv-failhigh (the root fail-high fix) was rejected on STC alone; its
  question is reopened by the measurement plan of ideas.md idea 29.
- Every result, including rejections, goes in the SPRT log.

**Search bench** (replaces the perft bench as `fork bench` and in
`tests/bench.ref`). It searches a fixed set of positions to a fixed depth,
on one thread, with 16 MB of Hash, and clears the TT and histories before
each position. It prints `nodes`, `nps` and a 64-bit `signature`, a fold
over each position's node count, best move, score and depth, and runs in a
few seconds in release builds. The positions are the six perft-suite
positions plus about 40 positions from the Lichess CC0 game database
(moves only: `[%eval]` comments ignored, no BOT games; KB data-policy.md), sampled by a committed script with a fixed seed and
checked with python-chess (owner, 2026-10-24). **The set must cover
openings, middlegames, endgames and positions with the side to move in
check**; the sampling script selects by phase and check status and prints
the coverage. The perft workload stays as
its own parity test (`fork perftbench`), so
move-generation parity across architectures stays guarded. Every search
change updates `bench.ref` in the same commit, and the commit message
states nodes and signature (non-negotiable 3). Bench parity across all
presets, both compilers, both platforms and the 4 TCEC compilers still
holds, which is why search decisions use no floating point (deliverable 6).

**Correctness tests** (ctest, beside the existing ones):
- at small depths with pruning off, alpha-beta, PVS, aspiration and
  TT-on all give the same root score as a plain minimax reference, on
  random positions;
- mate-in-N positions and draw detection (repetition, the 50-move rule
  with mate first, insufficient material);
- the max-ply stress test on forcing positions (no overflow, ply bounded);
- a tiny-hash stress test (replacement and collisions);
- `go depth/nodes/mate/movetime` honoured; the existing UCI suites with
  the real search; `uci_oom` still yields a real `bestmove`;
- **tactical and mate suites** at fixed nodes, as a regression guard after
  every pruning change (they never replace SPRT). The suite is chosen and
  fetched by the kb-researcher from a primary source, cited and
  SHA-pinned, and downloaded at configure time if its licence forbids
  committing it (Win at Chess, chosen and pinned; its licence stays
  UNVERIFIED, so it is never committed; ORIGINALITY.md);
- debug-build search counters (`FORK_SEARCH_STATS`, compiled out of
  release builds): cutoff rates, prune, re-search and extension counts,
  and the TT hit rate;
- `fuzz_uci` reaches the search only up to its first stop poll (it runs
  without threads, so the stop flag is set before the search starts;
  audit-1, D-16); the
  phase-end fuzz rule applies to it, and to `fuzz_fen` and `fuzz_moves` if
  `src/core` changes.

#### Queued experiments (run at Milestone B; results in ideas.md)

1. **Legal vs pseudo-legal generation in search.** Fork generates fully
   legal moves. The alternative is pseudo-legal generation with
   `is_legal` before `make`, for the stages that are reached. With the
   same move order, bench nodes are identical, so this is an nps-only A/B.
2. **Idea 9, the gives_check ratio.** Count `gives_check` calls per
   `make` in real search. If the ratio approaches 2 or more, test the lazy
   per-ply check squares (computed on the first call in a ply and reused).
3. **Layout variants (idea 9).** Re-derive Position and State layout
   candidates for the 56-byte State (`archive/layout-exp` v5 no longer
   applies), plus TT entry and bucket sizes and history table widths, all
   measured by search nps with the A/B harness, bench unchanged.

**Results (2026-10-26; details in ideas.md idea 9).**
1. **Legal generation stays.** Bench cannot stay identical as the spec
   assumed, because the selection sort's swaps make the order of tied
   moves depend on the list's contents. So both variants used a tie-break
   by the move's encoding, which makes the order independent of extra
   entries, and their benches matched each other (17,047,993 nodes,
   signature add623af41d76213). Pseudo-legal captures and quiets out of
   check, with `is_legal` only on yielded moves: median -2.3%, best -1.7%,
   noise threshold 3.0%, no significant difference (one earlier run was
   too noisy to count: threshold 21.7%). The selector tests pass on the
   variant.
2. **gives_check ratio 0.646 per make**: the lazy check-squares variant is
   not warranted.
3. **Layout: no change.** State at 48 bytes +0.4%, State aligned to 64
   bytes -2.5%, int32 history -1.5%, 16-byte TT entries -0.3% (median nps;
   all within noise).

#### Quality control

1. **Pace.** One deliverable at a time, but stops for the owner's review
   only at the three milestones:
   - **Milestone A**: bootstrap eval, core search, TT and quiescence search
     done (Fork plays real chess).
   - **Milestone B**: move ordering and all tier 1 pruning and reductions
     done.
   - **Milestone C**: Syzygy probing and basic time management done (the
     core of Phase 3 complete).

   Tier 2 refinements are reported in batches at the end of Phase 3, not
   individually. The performance gate still runs after every deliverable,
   automatically: its results are recorded in
   `docs/history/phase-3/perf-log.md`, and work stops early only for an
   unexplained slowdown beyond the noise floor or a reviewer finding that
   needs the owner's decision.
2. **Performance gate per deliverable.**
   - Search nps and the search-bench node count, compared with the
     previous deliverable using the A/B harness. The noise floor is
     measured once by an A/A run of the search bench at deliverable 2 and
     recorded, then rechecked if the machine's load changes.
   - One `perf record` profile (WSL; perf 6.18 is installed) of `fork
     bench`, listing the top functions by self time, with any hotspot that
     doesn't belong flagged.
   - A slowdown beyond the noise floor needs a stated reason (a deliberate
     trade for better search, shown by its SPRT) or a fix.
3. **Hot-path rules for all search code.**
   - No heap allocation: the `no_alloc` test is extended to run full
     searches (bench positions, after setup) under the counting allocator
     and require zero allocations. Per-thread tables are allocated when
     the search object is created, never during a `go`, and `info` lines
     are formatted into a fixed buffer.
   - No exceptions, virtual calls or `std::function` in the search loop.
   - No unnecessary Position copies (one per search thread per `go`; the
     search itself uses make/unmake).
   - Compact TT entries (deliverable 3).

   The reviewer subagent checks these once per deliverable, not per
   commit. The originality-checker also runs at each milestone and at phase
   end, since search code is where resemblance risk is highest; it also
   compares Fork's constants (score range, margins) with other engines',
   as it did for the option limits.
4. **No premature micro-optimization.** Tweaks smaller than the noise floor
   aren't worth code complexity. Structure and correctness first; a speed
   change must show a measured gain (§7).
5. **Strength.** Every technique and refinement must pass SPRT before it
   stays. One that fails (after its LTC retest where the rule applies)
   stays off behind its flag or is removed, and the result is logged.
6. **Re-validation** (owner, 2026-10-25). Features interact: one that
   passed early can become redundant once later ones are in. So:
   - **No removal tests at the individual milestones** A, B and C.
   - **One removal round at the end of Phase 3**, after the tier 2
     refinements: every search feature is switched off in turn (a tuning
     build, `TUNE=1`) and SPRTed against the full search on
     non-regression bounds [-3, 0], with the feature off as the test side.
     If removing it costs nothing (H1 accepted), the feature is simplified
     away; every result, kept or removed, goes in the SPRT log. The rules
     above apply: a feature the research flags as long-time-control
     sensitive is removal-tested at LTC.
   - **Full re-validation after Phase 4's network arrives**: the same
     removal round over every search feature, and a retune of every
     eval-dependent margin (RFP, futility, the NMP gate, razoring,
     ProbCut, SEE thresholds, aspiration window and the like), since the
     evaluation they were set against will have changed.
   - **Every feature keeps its `SearchSwitches` flag in the code until
     that Phase 4 re-validation is done**; only then may switches of kept
     features be folded into plain code.
   - **Flagged for the end-of-Phase-3 removal round** (owner, 2026-10-25):
     SEE pruning in the quiescence search (`UseSeeQuiesce`), whose
     Milestone A SPRT was stopped as inconclusive at +9.5 ± 7.3 Elo after
     about 5,800 games (95% interval above zero); aspiration windows
     (`UseAspiration`), stopped as inconclusive at +3.9 ± 7.6 Elo after
     about 3,200 games (interval includes zero); and mate distance pruning
     (`UseMateDistance`), not SPRTed at Milestone A. All three kept on.
   - **Flagged for the end-of-Phase-3 removal round, NEEDS VERIFICATION**
     (owner, 2026-10-26): the TT-refined pruning eval (`UseTtEvalRefine`,
     the second review's claim (d)), **on by default provisionally**. Its
     SPRT on gainer bounds [0, 3] was stopped undecided by the owner (at
     +17.0 ± 19.9 Elo after 800 games; the last report, 1,000 games:
     +14.6 ± 17.8, LLR 0.40 of 2.94), so it was never accepted. The
     removal round tests it at STC and also at LTC 40+0.4.
   - **Also flagged** (owner's cap, 2026-10-26): keeping exact TT entries
     (`UseTtKeepExact`, the second review's claim (e)), off by default: its
     SPRT on [-3, 0] ended INCONCLUSIVE at the cap, -0.6 ± 7.5 Elo after
     4,800 games (LLR 0.09 of 2.94).

#### Implementation notes (2026-10-24)

Choices made while building, where the spec leaves a gap:

- **Deliverable 1.** `static_eval()` (`src/eval/eval.hpp`) is selected by the
  `FORK_EVALUATOR` CMake option (only `bootstrap` in Phase 3). Material uses
  Shannon's 9/5/3/3/1 scale (ORIGINALITY.md); the other terms and weights
  are Fork's own.
- **Deliverable 2, search.** The ply limit is `MaxPly` = 250; the score
  scale is in `src/search/score_bounds.hpp` (mates from 30000 down,
  tablebase wins from 29500 down, evaluations within 20000, infinity
  31000). Until deliverable 4 a leaf returns the static evaluation, so a
  mate is recognized one ply later than it will be with the quiescence
  search. Root moves are ordered once by the capture order, then after each
  root search by move-to-front: the move that last raised alpha goes first
  and the others keep their order (Fork's rule, adopted after the Milestone
  A originality check found the first rule, scores with minus infinity for
  moves that did not raise alpha plus a stable sort, equal to Stockfish's;
  owner, 2026-10-24). When an unfinished iteration supplies the move played, its PV
  is reported in a last `info` line, so the GUI's final line names that
  move (review finding).
- **Time.** All limits count from the moment `go` arrived, so Hash work
  done at `go` uses the move's own time (review finding). `go movetime N`
  plans N minus Move Overhead, but never less than N/2 and at least 1 ms
  (owner, 2026-10-25: subtracting the full 100 ms default made every
  movetime of 100 ms or less play at 1 ms, which silently weakened the
  short-movetime test games; clocked play keeps its full overhead). Deliverable 2 already has a
  first `TimeBudget`: a share of the clock (remaining / moves to go, or
  /30 in sudden death, plus 3/4 of the increment), a hard limit of four
  shares, never more than 90% of the clock after the overhead; every input
  is clamped to ±2^40 ms first, so INT64_MIN and INT64_MAX clocks cannot
  overflow (review finding). Deliverable 8 refines and tests it.
- **Bare `go`** and a `go ponder` without clock arguments that gets a
  `ponderhit` have no limit, so they search until `stop` (the Phase 2
  placeholder answered at once; the UCI tests now send `stop`).
- **Output.** Info lines are formatted in a fixed buffer. `send_line`
  returns each line's sequence number; if any other line (`readyok`, say)
  followed the last `info` line, that line is sent again right before
  `bestmove`, so a scored `info` line always precedes it.
- **Bench.** `fork bench` is the search bench: 46 positions at depth 6
  (24,919,232 nodes, about 2.5 s on the 7600X3D in deliverable 2); the
  depth may change as the search changes, always with `bench.ref`. The
  Phase 1 perft workload is `fork perftbench`, guarded by
  `perft_bench_parity` against `tests/perft_bench.ref`. `fork version`
  prints the build identity (`variant ... | commit ... |`) for
  `bench/ab_search.py`, the interleaved A/B harness for search nps.
- **Version** 0.3.0 for Phase 3 (the 0.<phase>.0 scheme).
- **Deliverable 3, TT.** 5 x 12-byte entries per 64-byte bucket, with the
  layout, replacement and self-verifying check of the deliverable as
  amended after the Milestone A originality check (above). The TT move is checked with `is_pseudo_legal` and
  `is_legal` before it orders anything. Mate and tablebase scores read too
  far below the node to fit within MaxPly stay at the bottom of their band
  (review). The age wraps every 256 searches (accepted, documented in
  `trans_table.hpp`). The session's `TransTable` is unbound before every
  Hash resize and rebound on every way out, as a throwing resize once left
  it on freed memory (review, test `uci_hash_oom`). The bench uses its own
  16 MB table, cleared before each position, refuses a smaller fallback, and
  times only the searches.
- **Deliverable 4, quiescence and SEE.** SEE is the exact swap-list value
  (CPW "SEE - The Swap Algorithm", via the KB's T7 description);
  `see_at_least` compares it with a threshold. The quiescence search
  searches captures and queen promotions (under-promotions are dropped), all
  evasions in check, and stores its results at depth 0, which a real-depth
  probe never accepts. The minimax oracle in `tests/test_search.cpp` is a
  textbook fail-hard alpha-beta with its own quiescence search (plain
  minimax over capture sequences was too slow); with the full window it
  returns the exact root value.
- **Tuning builds.** `-DFORK_TUNE=ON` declares every `SearchSwitches` flag
  as a UCI check option (`UseTT`, `UsePvs`, `UseAspiration`,
  `UseMateDistance`, `UseQuiesce`, `UseSeeQuiesce`, `UseHistory`,
  `UseHistoryMalus`, `UseRfp`, `UseNmp`, `UseLmr`, `UseLmp`,
  `UseFutility`, `UseSeePrune`, and since 2026-10-26/27 `UseTtAgeBlend`,
  `UseTtKeepExact`, `UseTtEvalRefine` and `UseTables`), so an SPRT compares a
  technique on and off in one binary (`tools/sprt.sh` with `TUNE=1`).
  Release and TCEC builds declare none. Since deliverable 8b, tuning builds
  also declare every numeric search parameter as a spin option (the
  parameter table, below).
- **Deliverable 5, move ordering** (2026-10-25). `MoveSelector`
  (`src/search/move_selector.*`) yields the TT move (validated), good
  captures and queen promotions by MVV-LVA with SEE computed only for the
  captures reached (losing ones deferred with the under-promotions), quiets
  by history, then the deferred moves; in check every evasion, captures
  first. `select_best` is a swap-based partial selection sort: the lowest
  index wins ties, but the swaps mean equal scores do not keep generation
  order (review: the first comment claimed they did). `QuietHistory`
  (`quiet_history.hpp`) is int16 by side, from and to; the bonus is
  min(12.5·d², 1250) with the standard gravity update toward ±10000
  (values replaced by the owner's decision of 2026-10-25, see "Search
  constants"), and the malus applies to the quiets searched before a
  cutoff (`failed_quiets`). The history persists between searches and
  is cleared by `ucinewgame`, Clear Hash (review finding: before that,
  Clear Hash did not reproduce a search) and each bench position, so a
  search is a function of position, limits, switches, TT and history.
- **Deliverable 6, tier 1 pruning** (2026-10-25). In `negamax`, non-PV and
  not in check: RFP (depth ≤ 6, eval − 80·d ≥ beta, returns the eval); the
  null move (depth ≥ 3, eval ≥ beta, the side has a piece besides pawns,
  not straight after a null move; null-search depth d/2 − 1 − min((eval −
  beta)/300, 2), 0 or less meaning the quiescence search; a mate score
  returned as beta); in the move loop, only once a move has been searched
  and while the best score is not a forced loss: LMP (depth ≤ 4, after 12
  + d quiets, via `stop_quiets`), futility (depth ≤ 6, eval + 100 + 70·d ≤
  alpha, quiet non-checking moves; the best score is raised to the
  futility value, the usual fail-soft convention) and SEE pruning (depth
  ≤ 6, thresholds −60·d for quiets and −100·d for captures). LMR applies
  to quiet moves from the fourth on at depth ≥ 3 and not in check, reduced
  by `reduction_for(d, m)` ≈ round(log2 d · log2 m / 4.5), using integer
  fixed-point logarithms (`lmr_table.hpp`, a compile-time table whose
  checksum is pinned; the truncating logarithms leave 18 of the 3,969
  entries one ply below the rounded value, review), clamped to [1, d − 1];
  then a full-depth zero-window re-search, then the full window at PV
  nodes. `moves_seen` (legal moves yielded) decides mate or stalemate; a
  node with moves but none searched returns its bound. Bench depth is 13.
  The minimax oracle tests switch the pruning off (it is not exact).
  `Searcher::probe_zero_window` is a tests-only seam that searches one
  non-PV node.
  - **Owner's decisions on the originality check (2026-10-25).** The first
    LMP count (3 + d²) was Stockfish's move-count formula and the first
    null-move reduction (3 + d/4 + min((eval − beta)/200, 3)) the Stockfish
    5/6 form; both were replaced by Fork's own (below), as were the history
    scale and bonus. The names `skip_quiets`, `quiets_tried`,
    `SeeQuietMargin`, `FutilityBase` and `FutilityPerDepth` (matching
    Ethereal or Stockfish in another case style) became `stop_quiets`,
    `failed_quiets`, `QuietSeeFloor`, `FutilityOffset` and
    `FutilityGrowth`.
  - **Guards.** `tools/solve_suite.py` at 200,000 nodes per position. WAC
    (verified by the kb-researcher, KB tools.md §4; download-only, licence
    UNVERIFIED), first values: 250/300 with all six on, 209 with all off;
    one at a time off: RFP 249, NMP 246, LMR 236, LMP 245, futility 245,
    SEE pruning 254. With Fork's own pruning values: 253/300; with the
    measured aspiration window as well: 247 (aspiration off: 245). These
    counts move by 3-6 under small trajectory changes alone (the same
    build: 245 at 150,000 nodes, 248 at 250,000), so they guard against
    collapses, not small differences. Mate suite (matetrack mates in 1-5,
    297 positions; a diagnostic only, owner 2026-10-25, KB data-policy.md
    decision 7): 136/297 with all six on and 126 with all off (first
    aspiration values); 132 with the measured window (aspiration off: 128). Review: no correctness defect; the pruning can delay a
    mate (ideas.md idea 22).
  - **Counters** (FORK_SEARCH_STATS bench, Fork's own values): RFP 2.09M
    and null-move 0.44M cuts; LMP 0.41M, futility 10.63M and SEE 2.90M
    prunes; 2.38M reduced searches, 0.5% re-searched at full depth.
- **Deliverable 7, Syzygy probing** (2026-10-26). Fathom at the pin is
  vendored unchanged in `third_party/fathom` (its own CMake target,
  `tbprobe.c` built as C++ so its `MADV_RANDOM` advice is compiled in, its
  warnings kept to itself); `src/search/endgame_tables.*` wraps it.
  `SyzygyPath` loads the tables at the next `isready`, `ucinewgame` or `go`,
  never during a search, and reports their largest piece count (from the
  files, 3-7). In `negamax`, at non-root nodes from depth 1 with no castling
  rights and a zero halfmove clock, a win/draw/loss probe returns at once
  when its bound settles the node (a win is a lower bound at the TB band, a
  loss an upper bound, a draw exact, cursed wins and blessed losses ±1, stored
  in the TT as that bound), and otherwise keeps the searched result within
  the bound. At the root the distance-to-zero ranking (the win/draw/loss
  ranking if the DTZ files are missing) keeps the moves of the best rank,
  which are all moves preserving the best result under the fifty-move rule
  (Fathom ranks every safe win equally), within any `searchmoves`. Info
  lines carry `tbhits`; switch `UseTables`. Tests (`tables` suite): no
  tables, a missing or empty directory, the 7-man pair (largest count 7,
  win and loss, no answer with a running halfmove clock or too many
  pieces), the root ranking (13 winning moves kept), a path with only the
  WDL file, the search's TB scores and probe count, and on Linux the
  `MADV_RANDOM` flag on the mapped table (`/proc/self/smaps`).
  `tools/check_syzygy.py`: 3,000 random positions on the 3-4-5 tables
  against python-chess's prober, 0 disagreements. Fathom's own output:
  an incomplete table file is reported on stderr and as an `info string`
  line on stdout (through C stdio, during loading only, so never beside
  search output); a mapping failure or running out of memory makes it call
  `exit()` (KB tools.md §6). Idea 22's KQR v K mate
  (re-checked with the 3-4-5 tables): the first mate appears at depth 9
  with tables and at depth 8 without, mate in 3 by depth 14 in both: the
  tables give no distance to mate, and probes need a zero halfmove clock
  (ideas.md idea 22). The won-ending conversion suite
  (`tools/conversion_suite.py`, 2026-10-26): 100 random TB-won 4-5 piece
  positions (seed 20261026), each with its halfmove clock set 4 plies
  short of what the win allows, played out by Fork (`go nodes 50000` per
  move, the tables loaded) against a defender that keeps its best table
  result, longest from zeroing: **100 of 100 converted**. The suite sends
  the whole game (`position fen ... moves ...`) and a `ucinewgame` before
  each one: with a bare FEN Fork cannot see repetitions, and 5 of 100 were
  drawn by repetition in the first runs, a harness fault, not Fork's.
- **Deliverable 8, basic time management** (2026-10-26). `plan_time`: the
  increment adds three quarters of itself, multiplied before dividing (the
  first external review's claim (b): 1-3 ms increments added nothing); the
  reserve is a tenth of the clock, and one more Move Overhead only in the
  danger zone, when less than `DangerZoneOverheads` (2) overheads plus an
  increment is available (the final form, B2, below; at first it was two
  overheads at every clock). Between
  iterations, besides the soft limit, no iteration starts that would
  probably not finish before the hard limit (the measured growth, 5/3):
  this binds for `go movetime` and for a low clock whose reserve caps the
  hard limit. Tests: exact small increments; the reserve inside and
  outside the danger zone; a simulated low-clock game survives a stall;
  the iteration rule stops a search whose listener pauses (fault-injected:
  each test fails without its change).
  **The owner's split (2026-10-27).** The first form's SPRT against its
  parent leaned to about -10 Elo midway and ended at -4.9 ± 7.1 at the
  5,000-game cap: the fixed two-overhead floor binds where 8+0.08 games
  settle (about 0.4-0.6 s left). Split into (a) the increment fix, (b) the
  reserve, redesigned adaptive as B1 (max(clock/10, overhead - increment))
  or B2 (the danger zone above), and (c) the iteration rule. Stress tests
  (2,000 games at 2+0.02, every CPU busy): (a) alone 3 time forfeits, (c)
  alone 1, B1 0, B2 0, the first form 0. The owner chose B2 without a
  separate SPRT (it acts only at a low clock; B1 reserves time on every
  move whose increment is below the overhead). The combination (a) + B2 +
  (c) against (a): +1.9 ± 10.6 Elo after 2,200 games on [-3, 0], accepted
  by the owner (sprt-log.md d8-final). Timing tests on an idle machine:
  pass on Windows and Linux (stop to bestmove 0.28-0.55 ms); `go movetime`
  never overran (30 searches each at 50, 200 and 1,000 ms ended at most
  25.2, 100.2 and 884.9 ms after go). The 40+0.4 check follows the
  Milestone C gauntlet.
  **The budget formula's credit** (owner, 2026-10-26): the constant screen
  found its shape (from deliverable 2: the clock over 30 moves plus an
  increment term, hard = min(4 × share, 0.9 × clock)) near Berserk
  4.5.0-8's time allocation. The owner kept it, with an explanation and a
  credit in `time_budget.cpp` and ORIGINALITY.md; Fork's own parts are the
  three-quarter increment, the soft limit at one share and the reserve's
  floor.
- **Deliverable 8b, the parameter table** (2026-10-26). `src/tune/params.hpp`
  lists every tunable numeric search parameter once, in an X-macro
  (`FORK_SEARCH_PARAMS`: name, default, lowest, highest, SPSA step): 28
  parameters (aspiration, the iteration rule, reverse futility, the null
  move, the table probe depth, LMR, LMP, futility, SEE pruning, the history
  bonus, the TT victim policy's stale depth, the time budget). Release and
  TCEC builds declare each as `inline constexpr int`, the same code as the
  constants they replace (bench unchanged: 17309921 / 372dc2e2d8a88e4b,
  also from a tuning build at the defaults). Tuning builds (`FORK_TUNE`,
  now public on `forksearch`) declare them as variables, offered as UCI
  spin options beside the switches; `set_param` clamps to the range and
  rebuilds the LMR table. Two formulas became integer parameters with
  identical arithmetic: the LMR divisor 4.5 is `LmrDivisorTenths` = 45 (the
  table is (10 L + 32768 t) / (65536 t), exactly the earlier
  (L + 147456) / 294912 at t = 45, checked entry by entry), and the
  iteration growth 5/3 is `IterationGrowthThirds` = 5; the history bonus
  12.5 d² is `HistoryBonusFactor` = 25 (halves). Not in the table, each with
  its reason: the stop-poll interval and fail-report delay (not strength
  parameters), the near-draw table score (must stay just off zero), the
  history scale (the int16 headroom depends on it), the move-ordering
  scores (derived structure) and the movetime floor (an owner's rule).
  **Ranges and steps** (Fork's rule, bounds for a tuner, never played as
  such): about half to twice the default, depths in whole plies (at least
  1, counts at least 0), and an SPSA step of a twentieth of the range,
  rounded, at least 1. Tests (`params` suite): every default in its range,
  steps fitting, unique names, the bonus cap's range within the history
  scale; the LMR table equal to the earlier formula (fault-injected: a
  rounding change and an out-of-range default each fail); in a tuning
  build, `set_param` changes, clamps, rebuilds and restores. Checked by
  hand on a tuning build: 31 spin options, and LmrDivisorTenths 30 changes
  a depth-12 search from 168,013 to 159,853 nodes. Name check 25: no match
  but the plain words `lowest`, `highest` and `default_value` (kept).
- **Deliverable 8c preparation: the heuristic-discovery harness**
  (2026-10-26; ideas.md idea 23; the loop itself not started, owner).
  `tools/evolve/`, standard-library Python, run in WSL:
  - **Region and guard** (`regions.py`): `// FORK-EVOLVE-BEGIN lmr` /
    `END lmr` mark the body of `lmr_correction(const LmrContext&)` in
    `src/search/lmr_table.hpp`. The search reduces by
    `base + lmr_correction(c) * LmrCorrectionStrength / 64` (the strength a
    new parameter-table entry, 64, for SPSA); the committed body returns 0,
    so bench is unchanged. A full replacement returns `R - c.base`, so one
    region serves both modes. The guard rejects a candidate that differs
    from the baseline outside the body, moves a marker or touches another
    file, before any build.
  - **Gate** (`gate.py`): hot-path rules on the body (no allocation,
    exceptions, dynamic dispatch, floating point, randomness, static state,
    threads, preprocessor, assembly, I/O, containers, markers), the guard,
    a Release build of the baseline commit with the body, perft equal to
    the baseline's, the `search` (minimax oracle), `pruning`, `params`,
    `tt`, `ordering` and `no_alloc` suites, and two identical benches.
  - **Proxies** (`proxies.py`): best-move agreement and mean score error
    (capped at 400 cp) against labels from Fork's much deeper search, at
    the baseline's node budget (20,000), from a fresh state per position;
    the mean depth reached is reported, never used alone. The position set
    (`positions.py`, `positions.jsonl`): Fork's own self-play from random
    8-ply openings, labeled at depth 18, one in six positions held out for
    survivors' final check. Behaviour descriptors from a
    `FORK_SEARCH_STATS` bench: the mean reduction (a new counter) and the
    re-search share.
  - **Population** (`population.py`): SQLite; islands, a MAP-Elites grid
    per island (one elite per cell of mean reduction by 0.25 ply and
    re-search share by 2 points), seeded parent choice, FunSearch-style
    reseeding of the weakest island, an event log.
  - **Agents** (`agents.py`, `prompts/`): two proposers (aggressive,
    cautious) and an optional third from the statistics, the explorer (the
    full-replacement share, about 1 in 5, on an island protected for 3
    generations), the critic before every build (a quarter of its
    rejections are still gated, to measure the critic), the analyst every
    3 generations; all under the clean-room rules in the shared context.
    `StubAgent` for tests and the dry run; `CliAgent` (`claude -p`) for a
    live loop (its JSON fields were confirmed by the validation run of
    2026-10-27: 18 live proposals, none malformed).
  - **Orchestrator** (`orchestrator.py`, `config.json`): deterministic and
    seeded; stops at the generation limit, a budget (3M tokens, 150
    candidates, 48 hours by default), 6 generations without improvement, or
    a gate-failure rate above 80%; a live loop needs `--live`. Promotion: a
    proxy fitness 0.005 above the baseline goes to a 400-game match at
    4+0.04 against it, then to the SPRT hand-off (`match.py`: the patch
    and the `tools/sprt.sh` commands, gainer bounds, STC then LTC, after
    the originality-checker's screen).
  - **Tests** (`test_evolve.py`, 23): regions and the guard, the static
    rules, the gate's order with a fake runner, the proxy metrics, the
    grid, parsing and budgets, the match parser, and one orchestrated
    generation with stub agents; fault-injected (a guard that accepts
    everything and a gate without its determinism check each fail).
    Name check 26: no match, except the plain words `Loop`, `Population`,
    `Budget` and `Span` as Python class names (kept).
  - **Dry run** (2026-10-26, one generation, stub agents, real builds,
    gates and proxies on all 1,170 evolve positions, in WSL at nice 19
    beside an SPRT; about 10 minutes): the baseline passed its gate with
    bench equal to the committed one (the zero correction is exact), fitness
    0.4462 (agreement 48.3%, score error 36.7 cp, depth 7.43), descriptors
    1.726 plies mean reduction and 0.54% re-searched. The scripted
    proposals each took their intended path: one ply more at depth 8 and
    beyond passed the gate (bench 17100087) with proxies identical to the
    baseline's; one ply less on PV nodes and strong-history moves passed
    with fitness 0.4441 (not an elite: same cell, less fit); a body that
    does not compile stopped at the build; a floating-point rule was
    rejected by the critic and, audited, stopped at the static rules. The
    first dry run had found a harness bug (the gate compared perft's
    varying nps line instead of its count; fixed, with a test).
    **Finding for the pilot:** at 20,000 nodes the proxies search to about
    depth 7.4, so a change that acts from depth 8 is invisible to them; the
    pilot's node budget must reach the depths a region acts at.
  - **Proxy node budget** (owner, 2026-10-27: depth about 10-12 before the
    pilot). Measured on 200 seeded evolve positions, each from a fresh
    state (depth median, p10-p90, interquartile; agreement with the depth-18
    labels): 20,000 nodes 7, 6-9, 7-8, 46.5%; 100,000 10, 9-12, 9-11, 58.0%;
    **200,000 11, 10-14, 11-13, 61.5%**; 400,000 13, 11-16, 12-14, 66.0%;
    800,000 14, 12-18, 13-16, 72.5%. **Chosen: 200,000** (`config.json`).
    Time per position at that budget, measured on a quiet machine
    (2026-10-27; the depths equal the first, loaded measurement's, as a node
    budget makes them): **31 ms** (100,000: 15 ms; 400,000: 61 ms; 800,000:
    126 ms; the first measurement, 249 ms, was taken at nice 19 beside a
    stress test that kept every CPU busy), so the full 1,170 evolve
    positions take about 36 seconds per candidate; the set is kept whole, since agreement near 60% over 1,170
    positions has a standard error of about 1.4 points, the size of the
    differences worth detecting.
  - **History input fix** (2026-10-27, b89185f): `LmrContext::history`
    was read after the move was made, so it held the opponent's score for
    the move's squares. Found when the pilot's first history-based
    candidate left bench unchanged. Now the mover's; with that candidate's
    rule bench changes (16,945,722 nodes). The pilot was restarted.
  - **Novelty push** (owner, 2026-10-27, for the validation restart):
    - **New context inputs** (`LmrContext`, documented in the prompt):
      the moved piece's type, whether its square was attacked before the
      move (an escape), whether it now attacks an enemy knight, bishop,
      rook or queen (`lmr_move_facts`, searcher.hpp), the node's quiet-move
      count (the selector's stage size), the game phase (the evaluation's
      own, moved inline into `bootstrap_eval.hpp` unchanged), the node's TT
      bound and depth, the root score's change between the last two
      finished iterations (clamped to ±1000 cp, a sanity bound on an input
      only), and the per-mille share of the last finished iteration's
      nodes spent under the line's root move. Per-move subtree counts exist
      only at the root, so interior nodes see their root move's share. The
      committed correction is 0: bench unchanged (17309921 /
      372dc2e2d8a88e4b). The move facts are checked against python-chess
      on six constructed positions, and the phase on three (`pruning`
      suite). Cost, `bench/ab_search.py` in WSL, 8 rounds, same nodes:
      −1.1% nps with the zero rule (noise threshold 3.3%) and −1.0% with a
      rule that reads every new input but never fires (threshold 3.0%).
      Neither is significant. No allocation (stack values; `no_alloc` in
      the gate). Name checks 31-32: no match for the new names; `tt_bound`
      and `tt_depth` matched other engines once normalized, so they became
      `entry_bound` and `entry_depth`. `piece`, `attacks`, `phase` and
      `threatened` are plain words (kept).
    - **Inputs used as a grid axis** (`population.inputs_used`): a cell is
      now mean reduction × re-search share × the set of information inputs
      the body reads (everything but depth, move number and base). A rule
      built on new information gets its own niche instead of competing
      with refinements of the table.
    - **Explorer**: a third of the candidates (`full_share` 0.3333, 2 of 6
      per generation), protected for 6 generations (was 3).
    - **Generic description only**: the shared context explains LMR in
      general terms and names no engine's rule; the table it describes is
      Fork's own.
  - **Noise estimate and trigger rate** (owner, 2026-10-27, before any
    promotion): fitness is the mean of a per-position score, kept per
    position. Each candidate's gain over the baseline gets a paired
    percentile bootstrap interval over the positions (2,000 rounds, 95%,
    seeded; `proxies.paired_interval`). The stats build counts the LMR
    sites where the rule ran, fired (non-zero) and changed the reduction
    after scaling and clamping (`lmr_rule_*`). The trigger rate is the
    changed share. Promotion now needs the margin, the interval's low end
    above zero and a non-zero trigger rate; otherwise the candidate is
    logged `not_promoted`. Both values are shown on the dashboard.
    **Measured on the first live candidate** (the stopped run's #2: no
    extra reduction on PV nodes, threat escapes, attacking moves or
    positive history; one more ply from move 8 with at least 10 quiets;
    two with history below −4000 from depth 5): fitness 0.6085 against
    0.5987, gain **+0.0098, interval [−0.0137, +0.0332]** (three seeds
    agree to 0.0007). It changes the result at 738 of the 1,170 positions
    (398 better, 340 worse). It fired at 53% of LMR sites and changed the
    reduction at **30.0%**. So the gain is within noise: the position set
    resolves gains of about ±0.023, and the 0.005 margin alone was far
    below that.
  - **Castling fix** (CI on be70f48, clang-debug): `lmr_move_facts`
    read a castling move's target, the rook's square, which can be empty
    afterwards (an assertion in debug, a junk piece in release). A castling
    move now reports the king, not threatened (castling is legal only out
    of check), attacking from its landing square. python-chess case added,
    which failed first.
  - **Validation run** (2026-10-27, 3dfbe91, 3 generations of 6, live
    agents, 32 minutes, 315,167 tokens): 18 proposals, 0 malformed. 16 were
    scored, the critic rejected 2 (both explorer proposals labelled full
    that were residual corrections), 1 failed the gate and 0 were
    promoted. Every gain interval spans zero: the best was #2,
    +0.0114 [−0.0101, +0.0332]. Five candidates passed the old 0.005
    margin and were blocked as within noise. Trigger rates ranged from 0.2%
    to 44.9%. The exact-input-set axis gave 12 elites from 16 scored
    candidates. The analyst's notes were sound; it read the grid's
    unlabelled numbers as best it could.
  - **Node limit after a stop** (found by that run's gate): an explorer
    rule that reduces hard made a 5,000-node search report 5,002 nodes.
    After a stop, a reduced search returns 0, which can beat alpha, and
    the full-depth and PV re-searches were still entered, each counting a
    node. Both re-searches now require `!stopped_`; the rule passes the
    `search` suite with the fix. Bench unchanged (depth-limited, it never
    stops).
  - **Before the long run** (owner, 2026-10-27):
    - Input groups as the third axis: move facts (history, piece,
      threatened, attacks), node facts (quiet moves, phase, TT bound and
      depth) and iteration facts (score trend, branch share).
    - The stop rule counts an improvement only beyond the interval: a
      candidate whose paired interval against the best so far lies above
      zero becomes the new best. Six generations without one stop the run.
    - Proxies are split across `proxy_jobs` engine processes (8). Checked
      against a single process on the validation run's baseline, #2 and
      #17: every per-position score is identical, and so is the fitness
      (0.598715, 0.610082, 0.608664). 7 s against 34-36 s.
    - Each agent gets only what it uses. The critic and the analyst get the
      rules and the region, without the measurements, history or reply
      format. Proposers get the last 8 candidates in compact form, parents
      with their gain intervals, and only the LMR-related baseline
      statistics. The analyst gets one summary line per candidate: no
      per-position lists, which made its call 105,369 tokens. Every call's
      tokens are logged (`agent_call`). Measured with real calls on the
      validation run's state, before → after: proposer 7,436 → 6,913,
      critic 5,120 → 5,015, so 12,556 → 11,928 per candidate (−5%; most
      of what remains is the shared rules and region, plus about 1,500 of
      the CLI's own); analyst 105,369 → 8,056.
    - Limits: 40 generations, 3,000,000 tokens (binding; the candidate cap
      is raised to 1,000 so it never binds), 9 hours. Projection: about
      74,300 tokens per generation (6 × 11,928, plus the analyst's 8,056
      every 3), so **about 40 generations at 3M**. The count includes cache
      reads.
    - **The 4× position set** (the noise fix): ten more batches of Fork
      self-play (`positions.py`, seeds 20261101-20261110, 46 games each,
      20,000 nodes per move, labels at depth 18 by Fork at 65f9b63, ids
      `b01p…`-`b10p…`, run from the Windows `.venv`, python-chess 1.11.2).
      They add 4,314 positions with no duplicates of the first set: 5,734
      in total, **4,794 evolve** (4.1×) and 940 holdout. Measured on HEAD
      builds of the baseline and the validation run's four best candidates
      (8 engine processes):

      | Candidate | Old set (1,170): gain [95% interval], width | New set (4,794): gain [95% interval], width |
      |---|---|---|
      | #2 | +0.0114 [−0.0093, +0.0341], 0.0434 | −0.0069 [−0.0178, +0.0045], 0.0223 |
      | #14 | +0.0054 [−0.0029, +0.0136], 0.0165 | −0.0006 [−0.0047, +0.0034], 0.0081 |
      | #17 | +0.0099 [−0.0031, +0.0243], 0.0273 | −0.0005 [−0.0076, +0.0063], 0.0139 |
      | #19 | +0.0104 [−0.0094, +0.0313], 0.0406 | −0.0047 [−0.0152, +0.0063], 0.0215 |

      The intervals halve (1/√4.1 ≈ 0.49). The four best of the validation
      run gain nothing on the larger set: their positive gains on the old
      set came from being selected on those same positions (winner's
      curse), and those 1,170 positions are part of the new set. Baseline
      fitness on the new set: 0.6009. Proxy time per candidate: 30-33 s
      (36 s on the old set single-process), so a generation stays at about
      9.5-11 minutes (the validation run's took 9.0, 9.9 and 11.5, the
      last with the analyst): 40 generations in about 6.5 hours.
    - **Held-out confirmation** (owner, 2026-10-27): every scored
      candidate is also measured on the 940 held-out positions (about 6 s
      with 8 processes). A candidate is promoted only if its paired interval
      against the baseline lies above zero on both sets; otherwise it is
      logged "not confirmed on the held-out set". The dashboard shows each
      candidate's held-out fitness and gain. The held-out results never
      reach an agent and are never used to pick parents or elites, so the
      split stays independent of the search. Its only use is this final
      check. Tests: both outcomes; fault-injected (with the check removed,
      the candidate is promoted and the test fails).
    - **On hold** (owner, 2026-10-27): the long run waits for the full
      engine audit (branch audit-1), which comes before idea 23 and tier 2.
- **Performance gate.** `tools/perf_gate.sh` (A/B with `bench/ab_search.py`
  and a `perf` profile, in WSL; `tools/perf_symbols.py` names the addresses,
  as WSL's perf has no libelf); results in `docs/history/phase-3/perf-log.md`.

#### External reviews (2026-10-26)

Two external reviews raised suspected issues. The owner's rule: each is a
claim, reproduced with a failing test or a measurement before anything is
fixed, then fixed from Fork's own reasoning; pure speed fixes keep bench
identical, behaviour changes get SPRTs. Measurements are from the
FORK_SEARCH_STATS bench unless stated.

**First review.**

| Claim | Outcome |
|---|---|
| (a) A root move failing high above the aspiration window is dropped when time expires during its re-search. | **Confirmed**: a sweep of node-limited searches (bench positions and WAC) found 626 of 34,254 playing another move (perft position 6 at 4,991 nodes: g5f6 failed high, c3d5 played). Fixed in f0a9caf (the pending fail high played, reported as a lower bound), then **rejected by its SPRT** (rv-failhigh: -14.6 ± 10.8 Elo, stopped by the owner at STC; the owner's exception to the LTC-retest rule, 2026-10-27) and **reverted** (1fb18f4): the previous iteration's move is kept, the bookkeeping stays, and ideas.md idea 29 measures how often an unconfirmed fail high holds. |
| (b) The increment scaling divides before it multiplies. | **Confirmed** by calling `plan_time`: 1-3 ms increments add nothing, 7 ms adds 3 (not 5.25). **Folded into deliverable 8** (owner). |
| (c) SEE recomputed for proven-good captures; bad captures tested twice; bad captures searched after LMP stops quiets. | **Confirmed and fixed** for good captures (443,516 tests that always passed; skipped, 6ae4128, bench identical). Bad captures' second test (944,986) stays: it tests another threshold. Bad captures after LMP (502,947, 73% then SEE-pruned): **design, not a defect** (LMP is quiet-only by spec). |
| (d) At futile nodes all quiets are generated, scored and sorted though only checking quiets can be searched. | **Confirmed**: 10.4M quiets handed out at 425,623 futile nodes, 200,876 searched. **Fixed** (3a8a1b6): once the futility conditions hold, the selector keeps only checking quiets (317,326 handed out); the same moves are searched (identical benches with a position-independent tie-break), only the order of tied checking quiets differs. Search nps +12.7%. SPRT on non-regression bounds. |
| (e) PlyFrame about 4 KB per ply. | **Confirmed**: 3,968 bytes, Searcher 1.14 MB. **Shrunk** (6ae4128): 2,664 bytes, Searcher 816 KB (the per-frame scratch list went; int16 selector scores). Bench identical, speed within noise. |
| (f) PV quiescence nodes may explode on tactical positions. | **Not confirmed**: 0.2% of quiescence nodes on the bench, 0.46% on WAC (300 positions, 200,000 nodes each); worst single position 2,983 PV quiescence nodes (23% of its quiescence work). |

**Second review.**

| Claim | Outcome |
|---|---|
| (a) `see_at_least` computes the full exchange. | **Confirmed** (it was `see_value >= threshold`). **Fixed** (1efade9): it stops once the answer is settled (the side to choose can always stop); tested equal to `see_value >= threshold` at 14 thresholds over the SEE trees. Bench identical. |
| (b) The TT's stored static eval is recomputed on a hit. | **Confirmed. Fixed** (1efade9): reused in the main and quiescence searches. Bench identical. |
| (c) No TT prefetch before the null move. | **Confirmed. Fixed** (1efade9): `Position::predicted_null_key()`, tested against `make_null`. Bench identical. The three together: nps +2.9% (just under the 3% noise rule). |
| (d) Refine the static eval with the TT score before pruning. | Built behind `UseTtEvalRefine` (738daff) from KB T50: WAC 259/300 vs 248, mate suite 139/297 vs 132. SPRT [0, 3] **stopped undecided by the owner** (+14.6 ± 17.8 Elo at 1,000 games): **PROVISIONAL, on by default** since 2026-10-26, NEEDS VERIFICATION in the end-of-Phase-3 removal round (STC and LTC 40+0.4). |
| (e) A same-depth fail-low replaces an exact entry of the same search. | **Confirmed** by a unit test. Switch `UseTtKeepExact` (738daff, off by default); rare in search (3 of 46 bench searches change). SPRT [-3, 0] (a safety guard, the owner's bounds policy), on top of the TT-refined eval's new default. Cap (owner): about 5,000 games or 4 hours; if still undecided then, INCONCLUSIVE, off by default, and into the end-of-Phase-3 removal round. **Result: INCONCLUSIVE at the cap**, -0.6 ± 7.5 Elo at 4,800 games: off by default, in the removal round. |
| (f) Tier 2 order, razoring, losing-capture futility. | Plan changed (deliverable 9). |
| (g) Upcoming repetitions, fifty-move eval scaling, history malus balance. | ideas.md ideas 26-28. |
| (h) Phase 6: thread agreement and diversity. | Added to the Phase 6 roadmap entry. |

#### Search constants (owner's rule, 2026-10-25)

Every search constant has a recorded justification (DESIGN.md §8). They
are starting points: deliverable 8b moves the tunable ones into the
parameter table, and the margins are retuned after Phase 4's network,
because they are in the bootstrap evaluation's centipawns (pawn 100, knight
and bishop 300, rook 500, queen 900: Shannon's scale, `bootstrap_eval.cpp`).
Screened by the originality-checker against Stockfish, Ethereal, Berserk
and Weiss (results in ORIGINALITY.md).

| Constant | Value | Justification |
|---|---|---|
| `AspirationMinDepth` | 5 | **Measured** on the bench (46 positions to depth 14, aspiration off): the iteration-to-iteration score change has p90 16 cp at depths 2-4 and settles at 9-13 cp from depth 5; earlier iterations are cheap, so they keep the full window. |
| `AspirationHalfWidth` | 12 cp | **Measured**, as above: 90% of the score changes from depth 5 on are at most 12 cp, so nine iterations in ten need no re-search. Replaced the first scheme (25 cp from depth 4, doubling), which the constant screen found identical to Berserk 1.0.0's. |
| Aspiration widening | delta += abs(score − previous) | Fork's rule: on a fail, the half-width grows by how far the fail-soft score already is from the previous iteration's score. That is at least the old half-width (the score fell outside the window), so the window at least doubles, and more after a big jump; only the failing bound moves. |
| `FailHighDepthCut` | 1 ply (switch `UseShallowFailHigh`) | Audit-1, B-3 (KB T6): after a root aspiration fail high the re-search only places a score already shown to be at least beta, so it searches one ply less (the smallest whole step), once per iteration, not cumulatively; a fail low gets the full depth back. **Measured**: bench nodes -1.0 / -6.7 / -7.9 / -2.6% at depths 11-14; the proxies neutral (-0.0007 [-0.0049, +0.0035]). Constant screen (2026-10-27): near match in all four screened engines (the published technique's own one-ply step). Range 0-2, step 1. |
| `StopCheckInterval` | 1024 nodes | At about 10M nps that is a poll every 0.1 ms: far finer than the 1 ms clock, at a negligible cost per node. |
| `fail_report_ms` (a `Searcher` member, tests set 0) | 1000 ms | UCI GUIs need no fail-high/low lines for searches shorter than a second; it keeps fast games' output small. |
| `RfpMaxDepth` | 6 | At depth 6 the margin reaches 480 cp, a knight plus nearly two pawns; beyond that a static eval no longer bounds what the search can find (reasoning). |
| `RfpMargin` | 40 cp per ply | **Measured** (audit-1, 2026-10-27; owner: a justification from Fork's own data, as for LMP, adjusted if the data point elsewhere). With RFP off, at every node where RFP's other conditions hold and the pruning eval is at least beta, the share of the nodes a margin M·d would prune whose full search then fails low: on the bench (3.4 M such nodes) and on 300 evolve positions at depth 12 (15.7 M) it stays at most 0.37% for every M from 40 to 160 at every depth 1-6 (at the former 80: 0.31% at depth 1 down to 0.03% at depth 6). The pre-declared criterion, LMP's (the smallest M in 5 cp steps with at most 1% at every depth), gives 40, the bottom of the range: the data bound the margin from below without picking it, so 40 replaced 80 only through its SPRT (sprt-log). The former 80 (four fifths of a pawn per ply, reasoning) matched Berserk 4.5.0's margin (ORIGINALITY.md, 2026-10-27); 40 has no match. Range 20-80, step 3. |
| `NullMinDepth` | 3 | Below depth 3 the null search would be at least as costly as the node it replaces. |
| Null-search depth | d/2 − 1 − surplus plies | Fork's form: the null search only has to show that passing still fails high, so it gets half the remaining depth, one ply less for the pass; at depth 3 that is the quiescence search. |
| `NullSurplusPerPly` | 300 cp | One extra ply of reduction per knight of static surplus over beta (the bootstrap knight value): with a whole piece in hand, a shallower search still finds any refutation that matters. |
| `NullSurplusPliesMax` | 2 | Two pieces of surplus is already decisive; more reduction would leave too little depth to see threats. |
| `LmrMinDepth` | 3 | From depth 3 a reduced search still has at least one ply left (reductions are clamped to [1, d − 1]). |
| `LmrMinMove` | 4 | The first three moves (the TT move and the best captures, usually) take almost all cutoffs: 87.8% on the first move, mean cutoff index 0.27 (bench, FORK_SEARCH_STATS). |
| LMR divisor | 4.5 (log2 · log2) | Fork's choice of anchors: one ply at depth 3 from the third move, 2 plies at (8, 10), 3 at (12, 20), 5 at (20, 30), 8 at (63, 63); the reductions grow slowly enough to stay below a third of the depth. |
| `LmpMaxDepth` | 4 | The cutoff-index measurement (next row) has the same shape to depth 6, but from depth 5 on LMR already reduces late quiets by 2 plies or more (`reduction_for(5, 13)` = 2), so LMP adds little there. |
| `LmpQuietAllowance` | 12 (count 12 + d) | **Measured** on the bench (LMP off, FORK_SEARCH_STATS histogram of the cutting quiet's index): fewer than 1% of quiet cutoffs come after the 13th, 13th, 14th and 11th quiet at depths 1-4. 12 + d keeps that 1% bound at depths 1-3 and prunes later at depth 4, where a missed cutoff costs a bigger subtree. |
| `FutilityMaxDepth` | 6 | As for RFP: at depth 6 the margin is 520 cp, past which a static eval says little. |
| `FutilityOffset`, `FutilityGrowth` | 100 + 70·d cp | A quiet move rarely gains a pawn of static eval by itself (the offset), and each further ply allows 70 cp more swing, a little less than RFP's 80 because a futile node is already below alpha (reasoning). |
| `SeePruneMaxDepth` | 6 | The same horizon as the other shallow-depth pruning. |
| `QuietSeeFloor` | 60 cp per ply | A quiet move may hang a pawn's worth by depth 2 and a minor piece by depth 5: deeper searches can justify bigger sacrifices. |
| `CaptureSeeFloor` | 100 cp per ply | Captures that lose material are more often tactical (they open lines), so they get a pawn per ply. |
| `HistoryMax` | 10000 | The scale is free (ordering compares values within one table); 10000 is a round value well inside int16, so up to three tables summed in tier 2 (T10, T11) still fit in an int16 range. |
| `HistoryBonusCap` | HistoryMax / 8 = 1250 | No single cutoff moves a value by more than an eighth of the range, so about eight agreeing cutoffs are needed to approach the limit. |
| History bonus | 12.5·d², capped | Grows with depth because deeper cutoffs refute bigger subtrees; quadratic so the rarer deep cutoffs outweigh the many shallow ones; reaches the cap at depth 10. |
| `StaleDepthPerSearch` | 2 plies (TT victim policy, experimental switch `UseTtAgeBlend`, off by default) | Between two of Fork's searches in a game two plies are played, so a stored position is two plies nearer the new root, and the new search asks it for two plies more depth than the search that wrote it. The shape depth − k·age is the common one (Stockfish, Ethereal, Berserk and Weiss); their rates are 4-16 plies per search (constant screen, 2026-10-26). |
| `EvasionCaptureBase` | HistoryMax + 1 | Above any history value (|h| ≤ 10000), so evasion captures always come before quiet evasions; with the largest victim-attacker score (14,400) every score fits the int16 score array (6ae4128; it was 2^20 with an int array). |
| `TableProbeMinDepth` | 1 | Endgame tables are probed at every main-search node that meets the conditions: a fifty-move-safe probe needs a zero halfmove clock, so probes come only right after captures and pawn moves anyway. A higher minimum pays only with slow table storage (TCEC's 7-man set is on disk); tuned in Phase 8 on TCEC-like storage. |
| `TableNearDrawScore` | 1 cp | Cursed wins and blessed losses (the fifty-move rule turns them into draws) score just off zero: a real draw is never preferred to a cursed win, and no real advantage is given up for one. |
| MVV-LVA score | (victim value + promotion value)·8 − attacker type | The victim's value dominates (distinct values differ by at least 100, so ·8 leaves room far above the attacker's type index, at most 5), and the attacker breaks ties: standard MVV-LVA ordering (CPW). |
| `AssumedMovesLeft` | 30 | Without `movestogo` the clock must last the rest of the game, and the budget is recomputed every move: spreading it over 30 moves spends a little more while the position is richest, and the remaining clock only shrinks geometrically (by about 1/30 a move before increments), so it never runs out. Reasoning (owner, 2026-10-27: measured in Phase 5); the shape is credited to Berserk 4.5.0-8 (ORIGINALITY.md). |
| `MaxMovesToGo` | 40 | A larger `movestogo` (a long first control) is read as 40, so one move never gets less than a fortieth of the clock: 40 moves is the classic length of a first time control. Reasoning; measured in Phase 5. |
| `HardOverSoft` | 4 | The hard limit is four shares. An iteration that starts near the soft limit can run on: the measured iteration growth has p90 2.38 (row "Iteration growth"), and a fail low or an aspiration re-search adds more; four shares cover that, while one move still takes at most about 4/30 of the clock. Reasoning; measured in Phase 5. |
| `ReserveDivisor` | 10 (hard limit at most 0.9 of the clock) | No single move may plan on the last tenth of the clock: that tenth is the reserve for latency and the moves after it. Reasoning; measured in Phase 5. |
| Increment share | 3/4 | An increment arrives only after the move; spending all of it every move leaves nothing for the variance of move times, so a quarter of each increment is kept back and accumulates as a reserve when the clock runs low. Reasoning (Fork's own; constant screen 2026-10-26: no match); measured in Phase 5. |
| `MovetimeFloorDivisor` | 2 | `go movetime` keeps at least half its time, whatever the Move Overhead (decisions log, 2026-10-25). |
| `ForcedMoveFraction` | 8 (switch `UseForcedMoveStop`) | Audit-1, B-1: with one root move nothing the search finds changes the move, so a timed search stops once 1/8 of its soft limit has passed. **From Fork's measured iteration growth** (row "Iteration growth": median 1.66 per iteration): 1.66^4 ≈ 7.6, so the reported score stays about four iterations short of a normal move's depth while 7/8 of the planned time is saved. Measured on a forced move at 60+0.6: 3,973 ms to depth 22 without the rule, 313 ms to depth 18 with it, the same score. Range 4-16, step 1. |
| `DangerZoneOverheads` | 2 | Deliverable 8, variant B2 (the owner's choice, 2026-10-27): one more Move Overhead of reserve only when the time available (the clock less one overhead) is below two overheads plus an increment, i.e. a clock below three overheads plus an increment. Fork's reasoning: in that zone one slow move (Milestone A's flag came from a stall longer than the overhead) plus the next move's normal latency could use up what is left before the increment, which arrives only after the move: one overhead for each. Stress test 0 time forfeits in 2,000 games (the tenth alone: 3). It replaced `ReserveOverheads` (2 overheads at every clock), which cost about 5-10 Elo at 8+0.08. |
| Iteration growth | 5/3 | **Measured** on the bench (46 positions to depth 14, cumulative nodes): the work grows by a median factor of 1.66 per iteration at depths 8-14 (p75 1.96, p90 2.38). An iteration started at elapsed time t probably finishes near t · 5/3, so none starts when that passes the hard limit. |
| `LmrCorrectionStrength` | 64 (of 64) | The evolvable LMR correction's scale in 1/64 steps: 64 applies a rule's correction as written, 0 switches it off, and the range 0-128 lets SPSA weaken or double it. A unit, not a tuned value; with the committed rule (0) it has no effect (deliverable 8c). |
| Score-trend clamp | ±1000 cp | The LMR context's root score trend is clamped to ten pawns: beyond that a change only says "decisive", and the clamp keeps any rule's integer arithmetic far from overflow (deliverable 8c). |

#### Owner's answers (2026-10-24)

1. SPRT bounds [0, 5] until Milestone B, [0, 3] for tier 2, [-3, 0] for
   non-regression; concurrency 5; UHO_Lichess for test openings only, never
   as training data (recorded in KB data-policy.md).
2. Fathom: vendor jdart1/Fathom c9c6fef0, lineage documented in
   ORIGINALITY.md; no Syzygy options beyond `SyzygyPath`.
3. Bench: the six perft-suite positions plus about 40 Lichess CC0 positions
   with a fixed seed, covering openings, middlegames, endgames and positions
   with checks.
4. MultiPV deferred to Phase 7.
5. The evaluator is selected at build time, with no indirect call.

## 6. Decisions log

| Date | Decision |
|---|---|
| 2026-10-23 | **Linux**: the owner installs WSL2. The Linux working copy is `~/fork` inside WSL; Phase 1 sign-off requires every preset passing on Linux, including GCC with sanitizers. |
| 2026-10-23 | **Chess960 / Double FRC: deferred, out of scope.** No X-FEN/Shredder-FEN parsing, no `UCI_Chess960` option, no 960 perft suite. Standard KQkq castling only. The internal "king takes own rook" castling encoding stays (it costs nothing), but no 960-specific logic is written. If FRC is taken up later, the CPW "Chess960 Perft Results" page (960 positions with depth 1-6 counts) is the planned test oracle; no published Double FRC perft suite was found on 2026-10-23. |
| 2026-10-23 | **tcec.json**: every value, including the adjudication thresholds (from an older season's rules), is marked unverified. Full current-season rules are researched before Phase 5. |
| 2026-10-23 | **Release targets**: `-march=native`, x86-64-v3, x86-64-v4 (AVX-512), and a no-PEXT magics build, for each compiler; bench must match across all of them (automated `bench_parity`). |
| 2026-10-23 | **Namespace `fork` renamed to `forkeng`** (owner): `fork` collided with POSIX `fork()` on Linux (section 8, naming conventions). Checked first: no match in Stockfish (shallow clone at effdc3f, 2026-10-17), the MinGW toolchains, glibc/libstdc++/clang headers, or exported libc/libstdc++/libm symbols. **`scripts/check.sh full` covers both platforms**: on Windows it also runs the Linux check in WSL on a copy of the working tree. |
| 2026-10-24 | **Phase 2 spec approved** with the answers in §5.1; the Phase 1 review fixes come before Phase 2. **History rewritten** (owner): every commit's author and committer email replaced with the GitHub noreply address before the repo goes public (review L4); trees unchanged, all hashes changed. |
| 2026-10-24 | **TCEC toolchain (review C1).** CMake floor 3.22, `std::format` replaced by `snprintf` (libstdc++ has `<format>` only from GCC 13), LTO probed with `CheckIPOSupported`, download timeouts (review M7), `update.sh`, and a required Ubuntu 22.04 leg in `scripts/check.sh full` (gcc 11.4, g++-12, clang 16, clang 19; bench parity with each). Before the fix the 22.04 build failed on the CMake floor and then on `<format>` with all four compilers; after it all four build with LTO and match bench. **`-g` in release builds** (owner): disassembly with and without `-g` is identical for clang (Windows, LTO) and identical in every shared function for gcc (MinGW static links three extra libgcc unwind helpers), so no speed effect is possible and no A/B was needed. `update.sh` defaults to `-march=x86-64-v3` until Phase 4 has SIMD code that benefits from x86-64-v4 (both TCEC servers are AVX-512 capable per the KB; revisit then). |
| 2026-10-24 | **Clean-room rewrites (review H2, M3, H3).** Magic search, masks, leaper and between/line tables rewritten by walking rays (no slider attack sets for between/line); candidates from the shared splitmix64 stream. State reduced to the fields Fork reads (key, castling, ep, halfmove, checkers, pinned, discoverers, captured: 56 bytes, was about 144); pins and discovered-check candidates by one x-ray computation per king; direct checks computed on demand in `gives_check`; pawn, material and non-pawn keys, `pinners` and the per-type check squares removed (no consumer; Phase 3 adds what search needs, designed then). bench/ab.py, 6 rounds, clang / gcc: make/unmake -16% / -16%, perft bench -7% / -5%, gives_check +76% / +76% (2.96 -> 5.21 ns clang); no-PEXT startup 1.02 -> 1.37 ms. Bench unchanged. Details: docs/ORIGINALITY.md. |
| 2026-10-24 | **Phase 1 review: deferred tests and suspicions resolved.** Deferred tests 1-2 (counter overflow, null-move repetition, copy allocation) were added with their fixes, each shown failing first (L1, M2, M1); test 3 (INT_MAX FEN from the CLI) is now rejected in clang-debug; test 4 (Ubuntu 22.04 build) failed as predicted, then passes (C1); test 5 (presets without env.sh) failed loudly with a generic message, now with a clear one; test 6 (MoveList bound) is replaced by a proof: promoted material needs missing pawns, so no position exceeds 323 pseudo-legal moves, and MoveList holds 323; test 7 (after the rewrites): check.sh full on every commit, slow suites and all presets at the end. Suspicions: 1 fixed as test 6; 2 as test 5; 3 resolved, gcc 11.4, g++-12, clang 16 and 19 all build with LTO and -Werror; 4 resolved, update.sh refuses -march=native; 5 resolved by M1 (copies reserve 1024 plies); 6 resolved, Syzygy WDL agrees on 434,763 positions (WDL cannot judge helpmates); 7 resolved against change, a fixed array instead of the vector measured make/unmake +2% (n.s.) and null move +11% slower (bench/ab.py, clang), and made Position about 128 KB, which overflowed the stack in a test; 8 resolved, six more engines compared (docs/ORIGINALITY.md), one high finding (insufficient material, from python-chess) rewritten clean-room. |
| 2026-10-24 | **Licence: GPL-3.0 (owner)**, stated in README.md as GPL-3.0-or-later (owner, 2026-10-24; first written as GPL-3.0-only), with the full text from gnu.org in LICENSE (review H1). The full history is kept, so the earlier Stockfish-like code and the python-chess-derived function (both from GPL-3.0 sources) stay licence-compatible. **History rewritten a second time** (owner): user-name paths in file contents and messages became `C:\Users\<user>\`, `/mnt/c/Users/<user>/` and `~/`; the tip trees of main and kb were unchanged, every hash changed. README.md covers the clean-clone build and the AI-assistance disclosure. `update.sh` also builds with make when Ninja is missing (tested in the Ubuntu 22.04 distro). |
| 2026-10-24 | **Phase 2 (UCI) signed off by the owner; tag `phase-2`.** Summary and results: docs/history/phase-2/summary.md. Phase-end changes (owner): `check.sh full` adds a 50-start UCI smoke loop for every Windows GCC preset; the checklist adds the full Windows gcc-debug suite, fuzzing only targets whose exercised code changed since their last clean run, and merging main into kb. MSan (instrumented libc++) also run: clean. |
| 2026-10-24 | **MinGW GCC: aligned AVX stack moves fault on Windows.** The sign-off run of all presets found the Windows gcc-debug engine crashing in about half of all starts (access violation at a `vmovdqa ymm` store to a 16-byte-aligned stack slot in `uci_main`; Windows x64 promises only 16-byte stack alignment). Every MinGW GCC build now assembles with `-Wa,-muse-unaligned-vector-move`: 0 aligned vector moves left, 0 of 50 starts crash, all 12 Windows builds pass, bench unchanged. Windows gcc-debug is not in `check.sh full`, which is why no commit check saw it (gcc-release has the same moves, 205 of them, without a crash seen). Linux and the TCEC builds are unaffected. GCC bug number and option history UNVERIFIED (CMakeLists.txt). |
| 2026-10-24 | **Option limits are Fork's own (owner, after the Phase 2 originality check found the specified limits equal to Stockfish's):** Hash max 4194304 MB (4 TiB), Threads max 4096, Move Overhead max 10000 ms; defaults unchanged. Boundary tests for every spin option. **Review fixes:** out-of-memory answers with a real bestmove from fixed buffers; Hash clear workers counted from the size allocated. |
| 2026-10-24 | **Hash memory: one block, checked against available memory (owner, amending §5.1).** The chunked fallback was dropped: Linux overcommit checks each mmap alone, so chunks would pass where the whole table is refused and the parallel clear would then trigger the OOM killer. Requests are compared with the physical memory available (plus the current table) before allocating; a refusal falls back to the previous size, else 1 MB, with `info string`. Transparent huge pages requested with `madvise`. Tested with a 1 TB request and one just above available memory, on Windows and Linux. |
| 2026-10-24 | **Phase 3 spec approved** (§5.2) with the owner's answers listed there: SPRT bounds and conditions, Fathom vendored, the search bench positions, MultiPV deferred to Phase 7, the evaluator chosen at build time. UHO_Lichess is a test-opening book only (KB data-policy.md decision 6). Build order: deliverables 1-8 with stops at Milestones A, B and C. |
| 2026-10-24 | **Milestone A originality fixes (owner).** `PvNode` renamed `OnPv` (bench identical). TT store redesigned from the KB description (stale entries below current ones, then shallower below deeper; a whole age byte with a 24-bit check) and made self-verifying for Phase 6 (the check XORs a digest of the entry's data, so torn writes read as misses); root moves ordered by move-to-front. Both change behaviour: bench 7533640 / 2711c23a13969520, the Milestone A SPRTs rerun on the new commit. SEE kept as the standard CPW swap algorithm, cited in ORIGINALITY.md. Root ordering by node counts logged as ideas.md idea 18. |
| 2026-10-25 | **Re-validation plan (owner).** No removal tests at Phase 3's milestones; one removal round (each feature off, SPRT [-3, 0], simplified away if removal costs nothing) at the end of Phase 3; the full re-validation of every search feature and a retune of eval-dependent margins after Phase 4's network; every search switch stays in the code until then. Added to §5.2 Quality control 6, the Phase 4 outline and CLAUDE.md's phase-end checklist (item 8). Also: SPRT cap of 20,000 games at STC (inconclusive acceptable at Milestone A for near-zero features) and concurrency raised from 5 to 10 for the remaining Milestone A SPRTs, pending a time-loss check. |
| 2026-10-25 | **`go movetime` keeps at least half its time (owner).** The budget is max(movetime - Move Overhead, movetime / 2, 1 ms); before, any movetime of 100 ms or less played at 1 ms with the default overhead. Clock games unchanged. Bench unchanged (no time limit in it). The Milestone A 50 ms/move games are re-run with the fix. |
| 2026-10-26 | **TT-refined pruning eval on by default, provisionally (owner).** Its SPRT ([0, 3], 8+0.08) was stopped undecided: +17.0 ± 19.9 Elo at 800 games when the owner decided (the last report, 1,000 games: +14.6 ± 17.8). `UseTtEvalRefine` keeps its switch and is flagged for the end-of-Phase-3 removal round at STC and LTC 40+0.4 (§5.2, Quality control 6); NEEDS VERIFICATION until then. Bench 17309921 / 372dc2e2d8a88e4b. The keep-exact SPRT runs on top of it. |
| 2026-10-27 | **Syzygy probing accepted (owner).** Its SPRT (tables on vs off, gainer bounds [0, 3], 8+0.08) reached the 5,000-game cap at +17.5 ± 7.2 Elo, LLR 2.72 of 2.94, the 95% interval entirely above zero: logged as ACCEPTED by the owner's decision; probing stays on. |
| 2026-10-26 | **External reviews' outcomes (owner).** Root fail-high fix: REJECTED at STC (-14.6 ± 10.8) and reverted (1fb18f4), an exception to the LTC-retest rule recorded on 2026-10-27 (idea 29 reopens the question). Futile-node quiet filter: ACCEPTED on the owner's stop ([-3, 0], +11.5 ± 11.9). TT victim blend: INCONCLUSIVE at LTC, off (idea 24). Keeping exact TT entries: INCONCLUSIVE at the cap, off, into the removal round. |
| 2026-10-27 | **Deliverable 8 split and merged (owner).** mc-time was inconclusive; variant B2 (the danger-zone reserve) with the iteration rule was chosen and ACCEPTED on the owner's stop (d8-final, +1.9 ± 10.6 on [-3, 0]); d8-ltc stopped INCONCLUSIVE and flagged to Phase 5 (the iteration rule first). The parameter table (8b) and the heuristic-discovery harness (8c) were built; the pilot's long run is on hold. |
| 2026-10-27 | **Full engine audit (owner), branch `audit-1`** before idea 23 and tier 2: ten parallel auditors, then the owner's decisions on the reconciled list: SPRTs give both sides the 3-4-5 tables; the 15 borderline names are kept as domain vocabulary (§8); `RfpMargin` gets a measured justification; Move Overhead's 100 / 0 / 10000 kept as Fork's protocol defaults; time-budget reasoning now, measurement in Phase 5; PVS and LMR switches decoupled; the forced-move stop SPRTed on [-3, 0]; the rv-failhigh exception recorded; constant screens report match / no match only. |

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
- The TT entry is prefetched using `Position::predicted_key(move)` before
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
restructure. The results are recorded in docs/ideas.md (idea 9).

## 8. Module layout and naming conventions

**Layout.** Fork follows the module split common to strong open-source
engines (rules core, search, evaluation, tablebases, protocol, tuning), with
its own names. Each module has a header comment giving its purpose and its
invariants.

| Directory | Responsibility | Phase |
|---|---|---|
| `src/core/` | chess rules: value types, bitboards and attack tables, hashing keys, board state, move generation, perft/bench | 1 |
| `src/uci/` | protocol loop, option registry, info output | 2 |
| `src/search/` | searcher, transposition table, move ordering, time control, thread pool; the Syzygy bridge (`endgame_tables.*`, the only code that calls Fathom in `third_party/fathom/`) | 3, 5, 6 |
| `src/eval/` | evaluator interface, tapered PST, NNUE (`eval/nnue/`) | 4 |
| `src/tune/` | the single tunable-parameter table | 3 |
| `tests/`, `bench/`, `fuzz/`, `tools/` | tests, microbenchmarks, fuzz targets, offline tools | all |

**Naming conventions** (enforced in review; `.clang-format` handles layout):
- types, classes and enums: `PascalCase` (`MoveList`, `GenMode`);
- functions, variables and files: `snake_case` (`make_null`, `predicted_key`,
  `test_epd.cpp`);
- private data members end in `_` (`states_`);
- constants and enumerators: `PascalCase` (`NoSquare`, `WhiteOO`);
- macros: `FORK_UPPER_CASE`;
- everything lives in `namespace forkeng` (tests: `forkeng::test`);
- headers `.hpp`, sources `.cpp`, one module per header/source pair.
- **No collisions with POSIX or C library names.** No identifier at
  namespace scope (namespaces included), and no macro, may reuse a name that
  the C library, POSIX, Windows/MinGW headers or the C++ standard library
  declare. Standard headers include system headers transitively and differ
  by platform, so a clash can be invisible on one platform and fatal on the
  other. Before introducing such a name, grep the system headers of both
  toolchains (MinGW on Windows; glibc, libstdc++ and clang on Linux).
  Example: the namespace was first called `fork`, which collides with POSIX
  `fork()` from `<unistd.h>`; libstdc++ 15 includes that header from
  `<atomic>`, so the tests failed to compile on Linux only. Renamed to
  `forkeng` on 2026-10-23. `scripts/check.sh full` builds on both platforms
  to catch this class of bug.

**Names and Stockfish (owner decision, 2026-10-23).**
- **Kept:** names that are common across engines and the Chess Programming
  Wiki: the files `types`, `bitboard`, `position`, `movegen`; the class
  `Position`; `pop_lsb`, `attackers_to`; and generic
  vocabulary (`perft`, `bench`, `make`/`unmake`, `MoveList`, `gives_check`,
  `is_pseudo_legal`).
- **Renamed** (Stockfish-distinctive), with the mapping kept in
  docs/ORIGINALITY.md:

| Old | Fork name | Meaning |
|---|---|---|
| `GenType` | `GenMode` | which moves `generate<>` produces (Legal, Captures, Quiets) |
| `more_than_one` | `has_multiple` | bitboard has two or more bits set |
| `check_squares` | `checking_squares` | squares from which a piece type would give check |
| `key_after` | `predicted_key` | exact Zobrist key after a move, without making it (TT prefetch) |

- **Domain vocabulary is kept deliberately (owner, 2026-10-25).** Standard
  chess-programming and textbook terms are the field's shared language, as
  CPW uses them, and stay even when another engine uses the same word
  (name check 13 found these matching Stockfish, Ethereal, Berserk or
  Weiss, mostly after case and underscores are ignored): `negamax`,
  `quiesce`, `gives_check`, `static_eval`, `mate_score`, `update_pv`,
  `see_value`, `score_to_tt` / `score_from_tt`, the TT names `TtHit`,
  `TtBound` and `TtBucket`, `LmrTable`, `moves_seen`, `quiets_searched`,
  `futility_value`, and the file name `see`; and the UCI option's own name,
  `SyzygyPath` (as `syzygy_path_`, name check 22). Kept the same way after
  the audit-1 screen (owner, 2026-10-27; ORIGINALITY.md row of that date):
  the castling-right names `WhiteOO`, `WhiteOOO`, `BlackOO`, `BlackOOO`,
  `parse_go`, the selector stages `GoodCaptures` and `BadCaptures`,
  `DarkSquares`, `NoPieceType`, `TbWinScore`, `rule50` and `max_hash_mb`
  (plus `score_to_tt` / `score_from_tt`, already listed). Exact matches of compound
  names that are not such terms are renamed: `SearchLimits` became
  `SearchQuota`, `AspirationWindow` became `AspirationHalfWidth`, and
  `Searcher::explore` became `Searcher::deliberate` (name check 14: no
  match in the four engines).
- **Rule:** before introducing a new type, function, file or member name,
  check it against Stockfish's current source. If it matches and isn't
  generic CPW vocabulary, flag it to the owner before using it.
- **Name-check procedure (owner, 2026-10-24).** The implementing session
  never runs the check itself and never has engine source on disk:
  1. The implementing session lists its candidate names and hands them to a
     separate research subagent.
  2. The subagent shallow-clones Stockfish, Ethereal, Berserk and Weiss
     (owner, 2026-10-25: the Stockfish-only check missed names matching
     Ethereal in another case style) into one fresh temporary folder,
     checks each name with a whole-word search (`grep -rlw`, file counts
     only) and also case- and separator-insensitively (identifiers
     lowercased with underscores removed, the comparison set kept only in
     the temporary folder), and records the commits it checked.
  3. It reports only **match / no match** per name (with the file count and
     the commit), never code lines, surrounding context or other
     identifiers.
  4. It deletes the clone immediately, before reporting, and confirms the
     deletion.

  **Constant screens report the same way (owner, 2026-10-27).** For each
  constant or formula: match, near match or no match, naming the engine and
  release for a match and its role in one phrase, and nothing else: no
  values, formulas, code or descriptions of what any engine does where it
  does *not* match, and no notes of that kind kept anywhere (the audit-1
  screen wrote such notes; they were deleted on 2026-10-27).

  No engine clone, copied file or identifier dump stays on the machine
  between checks (on 2026-10-24 all earlier clones in session scratchpads
  were deleted for this reason). Matches are flagged to the owner as above.
- **Search constants (owner, 2026-10-25).** Every search constant (margins,
  depth limits, reductions, counts, history scales, time-management
  factors) has a recorded justification in its phase spec's "Search
  constants" table: a reasoning, a quick sweep or a measurement on Fork's
  own data. The originality-checker screens every new or changed constant
  against known engines (Stockfish current and historical, Ethereal,
  Berserk, Weiss) before the commit, because model memory can reproduce a
  famous value without any source being opened. A match is replaced, or
  kept only with the owner's approval and a citation in ORIGINALITY.md.
