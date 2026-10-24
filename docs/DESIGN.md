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
`tests/bench.ref`. The repository URL for `FORK_REPO` is not decided yet
(the GitHub repository does not exist): UNVERIFIED until it does.

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
  per side, more than 8 pawns or 16 pieces per side, pawns on the first or
  last rank, the side not to move being in check, castling rights without the
  king and rook on their home squares, and implausible ep squares (wrong
  rank, occupied, or no pawn that could have just double-pushed). The
  halfmove and fullmove fields may be omitted (they default to `0 1`);
  when present they are capped at 10000 and 100000, so `make` can never
  overflow them (review L1).
- **Draw rules** (the same definitions as python-chess, which difftest
  compares against): `fifty_move_reached()` is a halfmove clock of 100 or
  more (search must check mate first); `insufficient_material()` holds
  when neither side can ever deliver mate on material alone (a lone knight
  against only king and queens, or bishops all on one square colour with no
  pawns or knights on the board; python-chess's per-side rule applied to
  both sides); `repetition_count()` counts earlier occurrences of the
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
| `Hash` | spin, MB, default 16, min 1, max 33554432 (32 TiB) | TCEC sets `Hash=262144` (256 GiB) and caps hash at 32 or 64 GiB unless initialization is multithreaded. Size math in `std::size_t` bytes, no 32-bit overflow. `setoption` only records the size; the table is allocated and cleared at the next `isready`, `ucinewgame` or `go`, after every option has been applied, because a GUI may send `Hash` before `Threads` and a clear started on `setoption Hash` would run on one thread (review M5, 2026-10-23). Allocated as one aligned block (or in chunks if allocation fails), first-touch cleared **in parallel** with `max(Threads, hardware threads)` workers, before `readyok`. Allocation failure keeps the old table and reports `info string`, never aborts. `madvise(MADV_HUGEPAGE)` where available, but no dependence on large pages (TCEC enables them automatically). Phase 2 allocates and clears the table; Phase 3 uses it. |
| `Clear Hash` | button | Clears the table (also in parallel). |
| `Threads` | spin, default 1, min 1, max 1024 | TCEC sets 512 (two sockets). Phase 2 stores it and uses it for hash clearing; Phase 6 uses it for search, NUMA-aware. |
| `Move Overhead` | spin, ms, default 100, min 0, max 5000 | Time reserved per move for GUI and system latency; TCEC leaves options at default unless the author asks, so the default must already be safe at 30'+3". Name with a space (owner, 2026-10-24: the conventional spelling across engines); TCEC's recommended value is a Discord question (docs/kb/competition.md). Used by Phase 5. |
| `SyzygyPath` | string, default `<empty>` | TCEC sets `SyzygyPath=/home/syzygy7` in every division. Paths separated by `:` on Linux and `;` on Windows. Phase 2 stores it and reports how many table files it finds (`info string`); a missing directory is not an error. Probing (7-piece, ideas.md idea 12) is Phase 3. |
| `LogFile` | string, default `<empty>` | Optional log of all UCI input and output with timestamps, for diagnosing a TCEC game afterwards. Off by default. |

Not declared in Phase 2: `Ponder` (TCEC ponder off), `OwnBook` (engine
books are forbidden at TCEC; Fork has none), `MultiPV` (Phase 3),
`UCI_Chess960` (out of scope, §6), `UCI_Opponent` (Phase 7, idea 8).

Option names were grepped against Stockfish's source as required by §8
before use: **to do at implementation** (`SyzygyPath` and `Hash` are the
de-facto standard names TCEC sets and must stay).

#### TCEC requirements and how Phase 2 meets them

| Requirement (KB) | Phase 2 answer |
|---|---|
| UCI or XBoard protocol | UCI, tested with fastchess and cutechess-cli. |
| Threads up to 512, Hash up to 256 GiB with multithreaded init, 320 GiB RAM cap | `Threads` max 1024; parallel hash clearing; no other large allocations. Tested locally at the largest size this machine allows, and the size arithmetic tested at 262144 MB without allocating. |
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
3. **fuzz_uci**: a libFuzzer target over the command parser (no output
   checks, only no crash, no hang, no sanitizer report).
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
| `src/search/` | searcher, transposition table, move ordering, time control, thread pool | 3, 5, 6 |
| `src/eval/` | evaluator interface, tapered PST, NNUE (`eval/nnue/`) | 4 |
| `src/tb/` | Syzygy bridge (wraps Fathom) | 3 |
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

- **Rule:** before introducing a new type, function, file or member name,
  check it against Stockfish's current source (a shallow clone,
  `grep -rw`). If it matches and isn't generic CPW vocabulary, flag it to the
  owner before using it.
