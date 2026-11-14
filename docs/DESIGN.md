# Fork: Design

Fork is an original UCI chess engine in C++20, built to compete in TCEC.
Every decision optimizes engine-vs-engine play under TCEC conditions,
correctness first, then speed. This file records the architecture and every
decision that affects play. Phase 7 evaluation adjustments must be documented
here; no logic may alter reported scores to trigger or avoid adjudication.

Status: **Phase 3 (search) closed 2026-10-28 (tag `phase-3`; summary: docs/history/phase-3/summary.md)**: Milestones A, B and C, the parameter table (8b), the heuristic-discovery harness and its validation run (8c), and the full engine audit (branch `audit-1`, merged through PR #5). By the owner's decision, tier 2 (deliverable 9) and the removal round move into Phase 4. **Phase 4 (evaluation) started 2026-10-28: step 0's spec (§5.3) approved and steps 1-3 of the multi-agent plan reviewed the same day; step 0 is being built.** Phase 2 (UCI) signed off 2026-10-24 (tag `phase-2`); Phase 1 signed off 2026-10-24 (tag `phase-1`).

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
- **Test as efficiently as possible, not as little as possible** (owner,
  2026-11-10; a standing principle). Every reliability check stays, but:
  - each test must be able to change a decision: if no outcome would change
    what is done next, it is not run;
  - use the cheapest test that can decide (an offline gate, a fixed-node
    screen, a short SPRT) before a dearer one;
  - stop early when the result is decided (SPRT bounds, futility stops,
    declared kill rules);
  - reuse controls (one control arm or seed for several candidates) and
    bundle CI (one full run covering several merged changes);
  - keep GitHub, the CPU and the GPU each busy with the next useful job,
    never idle while one is queued;
  - do not re-test what another planned test already covers (for example
    the factorial removal round instead of a separate LTC confirmation).
  **When proposing a test, state the decision it can change and its cost**
  (CPU-h, GPU-h, GitHub stages or hours).
- **Paths across Git Bash, PowerShell, Windows Python and WSL** (owner,
  2026-11-10; a standing rule, after retrain 8b's chain handed a Windows
  Python a `/c/...` path and silently wrote no ready file). One shared helper
  converts paths between the four environments, and every job and chain
  script uses it; a check fails if a script passes a Git Bash `/c/...` path to
  a Windows program. Jobs are launched from PowerShell, never from Git Bash.
  The helper is `tools/jobs/paths.sh` (`fork_path`, `fork_path_for`, `fork_wsl`; its twin `paths.py`), the
  check `tools/jobs/check_paths.py` (in the tool tests and the pre-commit hook; its header lists the rules
  and the `# fork-paths: ok REASON` exception marker).
- **No silent "done"** (owner, 2026-11-10; same incident). Every chain
  verifies that its own final outputs exist and are valid (for example
  `r8b-ready.json` present and parseable) before it reports done; otherwise
  it reports failed and names the missing or invalid output. The shared check is
  `fork_require_outputs` / `fork_chain_done` in `tools/jobs/paths.sh` (`json:FILE` also parses it).

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
  Detailed spec: §5.2. **Closed 2026-10-28** (owner; tag `phase-3`)
  without tier 2: deliverable 9 and the end-of-Phase-3 removal round move
  into Phase 4 (below).
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
  until it is done. **Tier 2 moves here** (owner, 2026-10-28): deliverable
  9's refinements (§5.2) are built and SPRTed one at a time on the GitHub
  shards, in parallel with the local self-play data generation (the shards
  use no local CPU). **The removal round folds into the search
  re-validation after the first network**: one round over every search
  feature, tier 2's included, instead of one at the end of Phase 3 and
  another after the network. **Phase 4 backlog** (owner, 2026-10-28): a
  manually triggered GitHub workflow that runs each fuzz target with the
  plateau rule, so phase-end fuzzing no longer uses the local machine
  (ideas.md idea 38). **Late Phase 4, if the owner said go after the Phase 3
  pilot (deliverable 8c):** the first real campaigns of the
  heuristic-discovery loop (ideas.md idea 23), after the first strong
  network and that re-validation; afterwards a standing tool in the
  improvement pass (below).

  **Phase 4 multi-agent plan** (owner, 2026-10-28; started 2026-10-28:
  step 0's spec is §5.3, steps 1-3 run on branch kb).
  - **Principle:** agents propose, build and review; training and SPRT
    decide. No architecture is chosen by argument alone.
  - **Focus** (owner, 2026-11-07): prefer ideas that make Fork more
    selective, spending computation and network capacity where decisions
    actually flip (near-window evaluations, reductions and prunes that go
    wrong), grounded in evidence from Fork's own search data. When choosing
    what to try next, favor ideas of this kind.
  - **Step 0, a baseline network first** (owner, 2026-10-28): a simple,
    proven network shape, chosen in the Phase 4 spec, gets the whole
    pipeline working end to end (data generation, training, inference,
    testing). Self-play data generation starts with it as early as
    possible, while the design work of steps 1-3 continues in parallel.
  - **Step 0 requirement: the trainer-engine parity test** (owner,
    2026-10-28). For a fixed set of positions, the trainer's own model
    and Fork's inference code (the scalar path and every SIMD path) must
    produce matching evaluations: exactly where both compute the same
    integer arithmetic, and within the quantization's documented
    tolerance where the trainer computes in floating point. It must pass
    **before any network is tested in games**, and it runs in CI for
    **every network change and every inference change**. Spec: §5.3,
    deliverable 6. It applies to every later architecture too: step 4's
    bake-off candidates and step 5's implementation each pass it before
    their first game.
  - **Step 1, research** (branch kb, ideas only): clean-room descriptions
    of modern NNUE design (input features including threat-aware inputs,
    king buckets and mirroring as concepts, output buckets, activations,
    quantization and quantization-aware training, training practices),
    plus the queued pipeline-streamlining research
    (`docs/kb/phase4-pipeline.md`; queued, not yet on branch kb as of
    2026-10-28). Never another engine's code or exact constants.
  - **Step 2, competing designs:** two or three independent designer
    agents each propose a full architecture for Fork, with reasoning,
    expected inference speed on x86-64-v3 and v4, Kaggle training cost,
    and risks. Their briefs differ on purpose (owner, 2026-10-28), so the
    proposals actually diverge: one speed-first, one accuracy-first, one
    novelty-first.
  - **Step 3, judge:** one agent compares the proposals and recommends 2-3
    candidates. **It may also propose one hybrid** (owner, 2026-10-28):
    a design combining components from different proposals, listing
    each component's source proposal and why the components should work
    together. The hybrid enters the bake-off as an extra candidate
    beside the originals and is never chosen without testing. The judge
    also records which components could later be tested individually by
    swapping them into the winner (each such swap is its own SPRT).
  - **Step 4, bake-off:** small versions of each candidate trained on the
    same data, compared by SPRT. The winner is confirmed at a larger size
    before Fork commits to it (owner, 2026-10-28); then it becomes Fork's
    first architecture. **Settled at the step 0-3 review** (owner,
    2026-10-28; §5.3 "Owner's answers"): the judge's four entries (S-512,
    the hybrid H-512, AF-S, and XGR-512 if its pre-test passes), all at
    width 512, on a shared kernel framework, trained on generation 1
    data, every candidate on the same data (owner, 2026-10-29; first
    generation 0); STC narrows the field and LTC decides between the finalists;
    Fork's Elo per speed doubling is measured by 2:1 time-odds games at
    STC only; the design-level originality screen comes first for X, G,
    R, the fitted king regions and AF's threat encoding. One net until
    the pipeline is proven; threat inputs come later as an add-on to the
    winner.
  - **Step 5, implementation:** one implementer session writes the
    inference code; independent reviewers check correctness, SIMD
    equivalence with the scalar reference, performance, and originality.
  - **Step 6, data:** a data-policy auditor enforces strategy A+ (own
    self-play labels, Lichess CC0 positions with evals stripped, Syzygy
    labels, nothing from off-limits sources).
  - **Step 7, training:** an analyst agent reviews each network
    generation's results and recommends the next change.
  - **Originality:** distinctive architecture choices (input features,
    bucketing, layer shapes, activations, quantization scheme) go through
    the originality screen, match / no match only (§8), before they are
    built.
  - **Compute:** heavy steps (data generation, training, bake-off SPRTs)
    run one at a time on the local machine, or on GitHub or AWS.
    **AWS is unavailable until further notice** (owner, 2026-11-05: the
    account is suspended; decisions log).
  - **Timing:** steps 1-3 may run in parallel with tier 2 once audit-1 is
    merged, since they need little CPU; steps 4-7 run in Phase 4. Each
    step stops for the owner's review before the next; reviews are
    batched where possible (owner, 2026-10-28): results that do not depend
    on each other's outcome go to the owner together, to reduce waiting.
- **Phase 5: Time management.** Soft and hard limits tuned for long
  increment games without ponder, and a stress test under artificial system
  load. Before this phase starts: research the current TCEC season's full
  rules and fill in `config/tcec.json`. **Carried over from Phase 3**
  (owner, 2026-10-27): deliverable 8's final form was checked at 40+0.4
  only briefly, stopped inconclusive (-14.8 ± 20.9 at fastchess's 400-game
  report, -4.7 ± 18.0 over all 590 games; sprt-log.md d8-ltc). Phase 5
  revisits it at long time controls, **the iteration rule first** (the
  danger-zone reserve should almost never bind at 40+0.4).
  **Also to settle** (owner, 2026-10-28; audit-1 R-4's remainder): a `go`
  with a clock only for the opponent (e.g. `go btime 1000 binc 10` with
  White to move) gives Fork no time limit today, so it searches until
  `stop` (checked: depth 20 after 3 s). Decide between that and a fallback
  budget, with a test.
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
  **Memory per thread** (owner, 2026-10-28): the 16,384-ply State reserve
  (audit-1 R-3) belongs to the UCI session's root position and its spare
  only; a search thread's copy reserves its own plies plus `StateReserve`
  (1,024), about 57 KB at a game's start. `no_alloc` checks the copy's
  allocation; keep it that way when threads multiply the copies (F-24's
  memory numbers).
- **Phase 7: Tournament-aware play.** Contempt/style options, TB-aware
  eval, keeping tension. Each item is documented here as genuine evaluation.
- **Phase 8: TCEC-conditions testing** from `tcec.json`: paired openings,
  adjudication, gauntlet against pinned engines, SPRT, stress testing.
  **TCEC-readiness checks** (audit-1's unmeasured suspicions; owner,
  2026-10-28), each measured before anything changes:
  - **Hash at TCEC sizes and under cgroups**: a refused 256 GiB request
    falls back to the previous size (16 MB at an event's start), not the
    largest size that fits, and a cgroup memory limit is invisible to
    `MemAvailable`. Settle with a `systemd-run -p MemoryMax=...` run, then
    decide on a halving fallback (A3 suspicions 3, 4).
  - **Fathom's `exit()` paths**: a failed `mmap` in mid-game ends the
    process, and a truncated table file with a valid magic is read out of
    bounds. Settle with a crafted file or a FIFO swap (A3 suspicions 1, 2).
  - **No BMI2**: a default x86-64-v3 binary on a CPU without BMI2 dies with
    SIGILL (47 `pext` instructions, no CPU check). TCEC's EPYCs have BMI2.
    Settle under Intel SDE `-nhm` (A4 suspicion 1).
  - **TT prefetch at 4 GB Hash**: the 16 MB bench table fits the 96 MB L3,
    so prefetch and TT changes are under-measured. A/B at 4 GB Hash with
    prefetch on and off (A2 S-c).
  - **Ponder timing**: the limits count from `go ponder`, so a long ponder
    leaves an instant move after `ponderhit`, and `bestmove` carries no
    ponder move. TCEC does not ponder (A1 suspicion 7).
  - **7-piece cold-cache cost**: probe rate and movetime with the 7-man set
    on disk and a cold page cache (`TableProbeMinDepth` 1, Fathom's lazy
    first-probe `mmap`, the root DTZ probe before the first hard-limit
    poll; A2 S-d, A3 suspicion 5).
  - **Fathom's lineage at TCEC** (audit-1 suspicion 12a): whether TCEC
    treats Fathom's Cfish-derived code as another engine's code
    (UNVERIFIED in ORIGINALITY.md). Settle by asking TCEC before the
    submission.
  - **The public KB's technique prose** (suspicion 12b): it was written by
    a research agent that had read engine code. Settle with an originality
    review of the KB pages the submission depends on.
  - **A load and stress run with B-1's forced-move stop** (audit-1 proof
    not run): games at 2+0.02 under artificial system load, checking that
    the shortened forced moves never lose on time.
  - **Reported-score calibration** (owner, 2026-11-13, when CalibratedScore was
    removed: "Record on the TCEC hazards list: reported-score calibration is open
    again (CalibratedScore removed at my call); before any TCEC entry, re-check
    whether Fork's raw scores could trigger TCEC's eval-based adjudication early
    (using the UHO/SF19 benchmark's numbers for the default net at that time),
    and decide then."). Fork reports the search's own score, not calibrated
    to win probability (engineering review 2026-11-11, W7). Settle with
    tools/nnue/uho_diag.py on the then-default net (advantaged-start and
    level-queenless medians against SF19) read against TCEC's adjudication
    rules (docs/kb/competition.md on branch kb: the draw rule, eval within
    +-0.25 for 8 consecutive plies with 6 or fewer pieces; whether it needs
    both engines' evals is UNVERIFIED in the KB; the outage rules +-10 and
    +-0.15), then decide.
  **Near term, before tier 2** (not Phase 8): the TT ignores the halfmove
  clock, so a table result stored at a zero clock can cut at a later visit
  with a non-zero clock, where the position may be a fifty-move draw (A1
  suspicion 4, A8 S-A8-1; B-2's storing of table results at full depth,
  reverted 2026-10-28, would widen it). Settle with a constructed 5-man two-path test: the same
  position reached once right after a capture and once 90 plies later.
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
| `position startpos\|fen <FEN> [moves ...]` | Builds the position and the repetition history from the move list. An invalid FEN or an illegal move keeps the position reached so far and prints `info string`; it never crashes. Move lists of several thousand plies are fine (no fixed-size history). **Out of memory** (audit-1 R-3; owner, 2026-10-28): the session reserves room for 16,384 plies in two positions at startup, so a long game's move list never allocates; a `position` that still runs out of memory (tokenizing the line, parsing the FEN) is tried once more, and if that fails too the position is unknown: every `go` answers `info string error: ...` and `bestmove 0000` without searching, until a `position` succeeds. |
| `go [...]` | Parses every argument: `searchmoves`, `ponder`, `wtime`, `btime`, `winc`, `binc`, `movestogo`, `depth`, `nodes`, `mate`, `movetime`, `infinite`. Times are 64-bit and may be zero or negative (a GUI can send a negative remaining time). Limits combine (both runners can send `depth` or `nodes` together with clock arguments); the first one reached ends the search. `wtime`/`btime` without `movestogo` means sudden death. `mate N` stops at a mate in N or less, and searches at most the 2N - 1 plies a mate in N needs (1 for N <= 0), then plays its best move, so a mate that does not exist still gets an answer (audit-1 R-4; owner, 2026-10-28). `go infinite` and `go ponder` never end by themselves: `bestmove` comes only after `stop` (or, for ponder, after `ponderhit` and the normal limits). A bare `go` is treated as "no limit" (an inference from the spec, UNVERIFIED in the KB); the Phase 2 placeholder answers it at once. |
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
| ~~`CalibratedScore`~~ | **Removed 2026-11-13** (owner, about 7:10 PM EST: "get rid of the cosmetic eval thing that was added, it may cause confusion in the future no need for it"); it was a check, default `true`, adopted the same morning (c7a61ea) | Was display only: every `info ... score cp N` showed N x 88 / 67 (r8brft1's S over the fitted logistic scale k = 67 cp). Since the removal Fork prints the search's own score again, as before c7a61ea (test: uci_options "info score cp is the search's own score, not rescaled"). Builds from c7a61ea up to the removal commit still carry the option, so the harnesses still set `option.CalibratedScore=false` (a no-op warning for a build without it: fastchess 1.8.2-alpha plays on) and the guard (tools/check_score_display_off.py, tools/jobs/score_display_guard.py, .github/ci/score-display-check.sh) stays; removing those is a follow-up once no such build is played. TCEC: the reported score is uncalibrated again, an open hazard (decisions log, 2026-11-13, the removal). The calibration study's findings stay (decisions log, 2026-11-13; ideas.md 172). |

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

**Its weights** (`bootstrap_eval.cpp`; audit-1 T-5, recorded 2026-10-28)
were chosen by reasoning, not measured or tuned: Phase 3 settles structure,
and Phase 4's network replaces this evaluation. The constant screen of
2026-10-27 found no match among them (ORIGINALITY.md). The rule throughout:
every placement term stays well below a pawn, so material always decides
first, and the terms only order otherwise equal positions.

| Weight | Value | Reasoning |
|---|---|---|
| Ring (`centre_distance`) | 0 on d4/e4/d5/e5 ... 3 on the edge | The Chebyshev distance to the four centre squares: one formula for every piece, no tables. |
| `KnightCentre` | 8 cp per ring | A knight's reach grows from 2 squares in a corner to 8 in the centre, so it gains most from centralization: at most 24 cp, a quarter of a pawn. |
| `BishopCentre` | 4 cp per ring | A bishop keeps long diagonals from the edge, so it loses less there: half the knight's weight. |
| `PawnAdvanceMg` | 2 cp per rank | In the middlegame an advanced pawn is also a weakness, so advancing earns little (10 cp on the 7th rank). |
| `PawnAdvanceEg` | 10 cp per rank | In a pawn ending advancing wins races: half a pawn on the 7th rank, still below promotion's value. Blended with the middlegame weight by the game phase. |
| `KingShelterMg` | 6 cp per ring from the centre | The middlegame king is safer away from the centre: at most 18 cp. |
| `KingCentreEg` | 10 cp per ring towards the centre | The endgame king is a fighting piece: at most 30 cp, blended by phase. |
| `MopUpLead` | 400 cp | The lead (no pawns left) at which the mop-up term starts: a rook (500) or more qualifies, a lone minor piece (300), which cannot force mate, does not. |
| `MopUpEdge` | 20 cp per ring | Driving the losing king to the edge is what mates: at most 60 cp. |
| `MopUpApproach` | 6 cp per square the kings are closer | Bringing the winning king is needed too, but matters less than the edge: at most 30 cp (kings never stand next to each other, so they are at least two squares apart). Together with `MopUpEdge`, under a pawn. |

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
SPRT-tested on its own, reported in batches, not individually. **Moved
into Phase 4** (owner, 2026-10-28): built there, its SPRTs on the GitHub
shards beside the local self-play data generation. The order follows the KB's build order (steps 5 and 7-10),
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

**Untested changes never ship** (owner, 2026-10-28). A change ships only
after the test its kind requires has given its verdict: an SPRT for a
behaviour change (passed, or ACCEPTED by the non-regression rule above),
the A/B harness for a speed claim, the full check for every change. A
change whose test is skipped, or stopped before a verdict, is **shelved**:
it is reverted (or left off behind its switch), the baseline stays, and
ideas.md logs it as untested with whatever partial data exist, to be
tested later. No decision accepts a change in place of its test. The
case that set the rule: RfpMargin 40, adopted without an SPRT, scored
22.5 points below Milestone C on the same 357 gauntlet games and was
reverted to 80 (ideas.md idea 34). **The one exception** (owner-approved,
2026-10-28): the TT-refined pruning eval (`UseTtEvalRefine`) stays on by
default. Its SPRT on [0, 3] was stopped undecided at +17.0 ± 19.9 Elo
after 800 games (Quality control 6), and it has been on through two
stable gauntlets: Milestone C (2402.5 ± 23.3) and audit-1 (2411.5 ±
22.5). The end-of-Phase-3 removal round still tests it.

**Build target per machine** (owner, 2026-10-28). Both engines of an SPRT
always share one target, so the target sets only speed, never a bias, and
bench is identical across targets (`bench_parity`). Every SPRT build is
update.sh's TCEC build (Ubuntu 22.04, g++ 11.4); `native` is never used,
because update.sh refuses it.
- **GitHub-hosted runners** (`.github/workflows/sprt.yml`): **x86-64-v3**,
  pinned as `FORK_ARCH` in the workflow's build step rather than taken from
  update.sh's default, since hosted runners may lack AVX-512 (CI run
  40717379840: AVX-512 binaries died with an illegal instruction on such
  runners). `tools/cloud/build_pair.sh` has no default target: it needs
  `FORK_ARCH`, accepts only x86-64-v3 or x86-64-v4, refuses x86-64-v4 on a
  CPU without its five AVX-512 features, and fails unless each binary's
  `fork version` reports the pinned target. Every shard result records it
  (`arch`). `tools/github/sprt_run.sh` drives one SPRT there, a stage of
  1,600 games at a time until the merged result decides: it dispatches only
  when no run of any workflow is queued or running, refuses commits not on
  GitHub, stops at the first run that does not succeed, and merges only
  shard results whose meta names its own base, test and stage
  (2026-11-02, after a cancelled SPRT's local driver kept dispatching
  stages; `tools/github/test_sprt_run.sh` checks each rule with a fake gh).
  Since 2026-11-08 its commit check, conclusion read and results download
  retry a transient gh failure (`GH_TRIES`, default 5, `GH_RETRY_WAIT`
  seconds apart, default 30; each failure's message in the driver's log)
  and stop only on a lasting one: twice in one night a healthy run's
  download, and once a commit check, failed and ended a screen, with gh's
  message discarded. **Since 2026-11-05 (owner) it runs only under the job supervisor**
  (`tools/jobs/jobctl.py start github NAME -- bash tools/github/sprt_run.sh
  ...`: one job of type `github` at a time; `jobctl.py stop NAME` ends the
  driver's whole process tree and verifies none is left before it releases
  the lock), finds the run it dispatched by the run's title (sprt.yml's
  `run-name`, "sprt BASE TEST stage N") among runs newer than the dispatch
  and not yet recorded, records each run in the run-ID ledger
  (`tools/jobs/ledger.py`, ~/fork-jobs/ledger.jsonl) with its inputs, and
  merges a stage only if the ledger records that stage's run with this
  SPRT's commits (`tools/jobs/test_jobctl.py` and the driver's test check
  each rule; a planted root-only kill and a planted "newest run" rule both
  fail them).
  **Which test a candidate gets (owner, 2026-11-09; the transfer-testing
  report, docs/research/transfer-testing/report.md §6):** integrity checks
  block (parity, quantization limits, bench, tests, and the
  **integrity/recall gate**: at most 15 of the 900 positions of
  tools/nnue/endgame_check.py misjudged, which catches missing or corrupted
  slice data; owner, 2026-11-12, about 5:00 PM EST; enforced by
  tools/nnue/gates.sh's exit status for a net trained with the endgame
  slice, reported only for any other, as the training chain states in the
  required `SLICE_TRAINED`, about 5:50 PM EST); offline metrics
  (validation loss, label error) are diagnostics only, reported and never a
  gate. **The held-out endgame checks** (4-5 pieces,
  tools/nnue/endgame_heldout.py; 6-7 pieces, tools/nnue/heldout_67.py; 8-12
  pieces, tools/nnue/heldout_deep.py) are reported for every net and
  flagged for the owner's review when the count is more than 15% worse
  than the **current default net's** (the net a promotion would replace),
  with each count's change against the run's warm-start net also reported
  for diagnosis; they are never a gate on screening or promotion, and every
  arm that passes the integrity gates gets its fixed-node screen (owner,
  2026-11-12, about 4:40 PM and 5:00 PM EST; they guard play without
  tablebases); a network or evaluation-side
  candidate whose speed differs from the default's plays a fixed-node
  screen first, adjusted for speed as FN_adj = FN + 118 log2(r) (r the two
  engines' speed ratio read from the screen's own games; 118 Elo per
  doubling = 1.72 Elo per 1% nps), and goes on to its STC SPRT [0, 5] only
  if FN_adj > 0 (a screen-out counts as a try of the idea, not the SPRT
  try); a prototype goes on to engineering only if FN + 118 log2(target r)
  > 0; a single same-architecture retrain goes straight to its STC SPRT,
  and competing candidates are all screened first; search features stay on
  design R.
  **Since 2026-11-07 (owner; the think tank's decisions 2 and 3) it has
  kinds**, each fixed in `design.json` before the first dispatch (a
  restart with another design is refused): `--kind search` is design R,
  [0, 6] nElo, alpha 0.05, beta 0.20, a cap of 8 stages at STC and 6 at
  LTC (`--cap 4-6`; 40+0.4, 1,664 games and 64 MB per stage), and one
  futility look after 2 stages: stop and reject if the nElo estimate of
  the 2 stages' summed pentanomial (sprt_merge.py's `nelo`, the "nElo:"
  figure) is below 0; `--kind network` keeps [0, 5] at alpha = beta = 0.05
  with 13 STC or 6 LTC stages; `--kind fixed --cap N` plays exactly N
  stages (head-to-head pairings). Every kind needs `--idea ID` (each
  retrain is its own idea), and a search or network SPRT is a try of its
  idea: at most two per idea and time control class (an LTC confirmation
  of an STC pass is not a retry), a third only with `--owner-override
  TEXT`, recorded verbatim (`ledger.py try` / `tries`,
  ~/fork-jobs/tries.jsonl). `--origin N` starts on fresh openings,
  `--first N` resumes. The outcome goes to the driver log and to a
  `verdict` file: H1 accepted, H0 accepted, futility stop (a rejection),
  capped (undecided at the cap: not passed) or complete. The positional
  form (`NAME BASE TEST ELO0 ELO1 [FIRST [LAST]]`, e.g. non-regression
  [-3, 0]) is unchanged, byte for byte. **Constants by head-to-head
  selection**: `tools/github/h2h_run.sh` plays 2-4 candidate values (one
  commit each; four since 2026-11-11, owner: six pairings) against each
  other on the same openings, one pairing or a
  round robin of `--stages L` each, and `tools/cloud/h2h_pick.py` picks
  the value (least-squares strengths; the declared `--prefer` value is
  kept unless beaten by more than 0.5 e) and writes the constants table's
  row, "head-to-head, N games, delta ± e", as Fork's own measurement; the
  winner then gets its design R SPRT on fresh openings (`--origin O+L`).
  Tests: `tools/github/test_sprt_run.sh` (66 checks), `test_h2h_run.sh`,
  `tools/cloud/test_sprt_merge.py`, `test_h2h_pick.py`,
  `tools/jobs/test_jobctl.py`.
- **AWS EC2 c7a/c8a** (**unavailable until further notice**: owner,
  2026-11-05, the account is suspended; decisions log)
  (`tools/cloud/aws_spot_sprt.sh`): the `--arch`
  option, **x86-64-v3 by default, and AWS SPRTs stay on x86-64-v3 until
  Phase 4** (owner, 2026-10-28; the SPRT log records no AWS run yet);
  `--arch x86-64-v4` gives an AVX-512 build, which C7a supports (its
  product page, KB tools.md §11). C8a's AVX-512 is UNVERIFIED in the KB;
  build_pair.sh's CPU check refuses x86-64-v4 there if the CPU lacks it.
  The shard results record the target.
- **Local** (WSL on the 7600X3D, `tools/sprt.sh`): update.sh's default,
  x86-64-v3.

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
acceptable for Milestone A (owner, 2026-10-25). **Non-regression early
acceptance** (owner, 2026-10-28): a non-regression SPRT ([-3, 0]) on a
change with a clear rationale stops once at least 10,000 games are in and
the 95% interval's lower bound is above -3, and is logged **ACCEPTED (by
rule)** with that interval. **The interval is read on the bounds' own
scale, normalized Elo** (owner, 2026-10-28): the SPRT bounds are nElo
(fastchess `model=normalized` in `tools/sprt.sh`; the same model in
`tools/cloud/sprt_merge.py`), so the rule reads the "nElo: x +/- e" line
(e = 1.96 × 800 / (ln 10 × √2) / √pairs), not the logistic "Elo: x +/- e"
line. The rule first read the logistic interval, as the owner had applied
it to B-1 ([-2.58, +4.50]); on the nElo scale B-1's interval is +1.24 ±
4.55, [-3.31, +5.79], which does not clear -3. On this scale the rule can
fire only on a clearly positive measurement: nElo above about +3.8 at
10,000 games, above about +1.8 at the 20,000-game cap. **Gainer-bound tests never stop early this way**: they pass
or reach their cap. The cloud SPRT driver checks the rule after every
stage; a local fastchess SPRT is checked at its rating reports.
**Concurrency 10**
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
tests skip while games run (`build/.games-running`, `FORK_GAMES_RUNNING`)
and, since 2026-11-12 (owner), while data generation runs on this machine:
`scripts/check.sh` then exports `FORK_LOW_PRIORITY=1` for its tests and
says so in one line (CI keeps them);
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
- **Everything else**: STC only (owner, 2026-11-06: LTC confirmations
  only for the list above). The STC verdict decides: a pass is adopted, a
  failure rejected, with no LTC confirmation or retest. Until 2026-11-06 a
  change to pruning, reductions or extensions was also confirmed at LTC
  and an STC failure was retested at LTC before rejection (one recorded
  exception, owner, 2026-10-27: rv-failhigh, the root fail-high fix, was
  rejected on STC alone; its question is reopened by ideas.md idea 29).
- Every result, including rejections, goes in the SPRT log.

**The streamlined standard (owner, 2026-11-06; for batch 4 and everything
after it).**
- **A search constant is chosen by a short SPRT ladder**, not by a
  label-and-sweep measurement: 2-3 sensible values (each with its
  reasoning recorded in the constants table; the placeholder may be one),
  each a quick STC test of the feature at that value against the default
  with the feature off (an SPRT on [0, 3] capped at 2 stages, 3,200 games;
  one that reaches H0 sooner drops out); the value with the best Elo point
  estimate is kept (within half the estimates' error bars of each other,
  the more cautious one), then the feature's normal STC SPRT runs with it
  on fresh openings. The ladder counts as Fork's own measurement for the
  originality rule (non-negotiable 6; the constant screen still runs
  before the commit that sets the value, matches recorded and credited as
  before); final values are refined later by the SPSA retune. The
  fifty-move scaling's label-and-sweep measurement, already running, is
  finished; batch 4's other declared measurement specs are not run.
- **No seed-noise matches**: the noise level is known (a net's seeds
  differ by about 4e-5 in validation loss, docs/history/phase-4).
- **The re-validation queue runs only as idle filler**: when GitHub would
  otherwise sit idle, never ahead of new work.
- **Kept as they are**: SPRTs; the parity chain and netcheck; the endgame
  acceptance test (since 2026-11-12 the integrity/recall gate, at most 15
  of 900); data verification before a part is sealed; the full CI
  before any merge to main; the fixed-node screen for new networks.

**Offline re-measurement rules set retune ranges only (owner, 2026-11-12;
the staleness audit, docs/research/staleness-audit-2026-11-12.md §4.2).**
A declared offline measurement rule (a label-and-sweep grid's quality per
node, a flag precision, a cutoff-share bound, a bench percentile, an
ordering index), re-run on a new network or search, only sets or widens
its constant's final-retune range so that the range covers the new
reading; it never gates a test and never picks a value by itself: games
(an SPRT, a head-to-head or the SPSA) decide. The evidence: in every case
where games or the SPSA checked a rule's pick, the pick lost or the tuner
moved away from it; `SingularMarginPerPly` 22, T27's rule re-run on
r8brft1, lost to 6 by 26.76 ± 9.93 Elo (design R STC, H0), and the
quality-per-node rules ranked "off" above every setting for IIR and
ProbCut, which then passed in games (IIR +21.45 STC and +26.25 LTC,
ProbCut +9.40 LTC). Area rule: .claude/rules/testing.md.

**A gauntlet's report step (owner, 2026-11-09).** When a run of
`.github/workflows/gauntlet.yml` (a gauntlet or an anchor check) ends, the
session that reports it first archives it: `tools/gauntlet/archive.sh
RUN_ID` downloads every artifact into `~/fork-data/gauntlet/run-RUN_ID/`
(the result at the top, each shard in a folder of its own), checks each
zip against GitHub's digest, and writes and verifies `SHA256SUMS` and
`meta.txt` (called again, it only re-verifies; a mismatch is an error,
never an overwrite), so nothing depends on GitHub's 90-day expiry. The
decisions-log row is written from that copy. If the ordo job could not
download an earlier run, level 0 is rerun from the archive, before
`transfer.json`'s `previous` moves on to the new run: `python -I
tools/gauntlet/report.py --archive ~/fork-data/gauntlet --adopted
tools/gauntlet/transfer.json --level0 ~/fork-data/gauntlet/run-RUN_ID
tools/gauntlet/anchors.tsv`. Every report section that gives an Elo
names its model: the Ordo fit (`-W -D`, anchored to CCRL Blitz) or the
plain logistic fit (no white advantage or draw model; the SPRTs' scale).

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

   Tier 2 refinements are reported in batches (in Phase 4 since
   2026-10-28), not individually. The performance gate still runs after every deliverable,
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
   **The SPRT checklist** (owner, 2026-11-05), every item before a
   feature's SPRT is dispatched:
   - each new or changed constant is a measured value (no placeholder ships
     unmeasured: a rule declared before the data, a wide grid not centered
     on the placeholder), and **the constant screen ran before the commit
     that set it** (the originality-checker; matches recorded beside the
     constant, non-generic ones to the owner);
   - **the test branch's full non-slow suite passes** on its test commit
     (`ctest -LE slow` on a fresh clang-release build), not only the quick
     pre-commit check, which leaves out the search suites (the LMR history
     term's SPRT ran with a pruning test that failed at its measured
     divisor; found and fixed on 2026-11-05);
   - the test commit's bench is recorded in its message, and its source
     diff against the base is the feature alone;
   - the new names were screened;
   - **the personal-data scan passes as its own step before the branch is
     pushed** (`scripts/scan-push.sh REF`; a hit blocks the push, and the
     pre-push hook runs the same scan as a backstop,
     `scripts/test_scan_push.sh` shows a planted hit stops it);
   - `tools/github/sprt_run.sh`'s own rules (one run at a time, both commits
     on GitHub, results matched to their stage), started through the job
     supervisor, every run of it in the run-ID ledger (owner, 2026-11-05).
   **The adoption checklist** (owner, 2026-11-09), every item in the
   adopting commit or the same day, so the records never trail an
   adoption:
   - the SPRT log row (docs/history/phase-4/sprt-log.md) and the
     decisions-log row, with the result as measured (Elo ± error, games,
     runs);
   - the constants table and ideas.md's status;
   - the bench references changed by the adoption, in the adopting commit
     (tests/bench-<net>.ref, tests/bench.ref);
   - **tools/gauntlet/transfer.json**: one `adopted` entry per adopted
     change (`change`, `elo`, `ci95` (the 95% half-width), `test`), so the
     gauntlet report's running transfer ratio counts every adoption since
     its baseline;
   - the labeller policy's part switch (a fresh PGO build for the next data
     generation part; at most one switch per day, think tank decision 24).
6. **Re-validation** (owner, 2026-10-25). Features interact: one that
   passed early can become redundant once later ones are in. So:
   - **No removal tests at the individual milestones** A, B and C.
   - **Folded into Phase 4's re-validation** (owner, 2026-10-28): Phase 3
     closed before tier 2, so the round below runs once, after the first
     network, and the items flagged here for "the end-of-Phase-3 removal
     round" are tested there. As first planned, **one removal round at
     the end of Phase 3**, after the tier 2 refinements: every search feature is switched off in turn (a tuning
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
     removal round tests it at STC and also at LTC 40+0.4. It is the
     owner-approved exception to "untested changes never ship" (Testing
     setup; 2026-10-28): on through the Milestone C and audit-1 gauntlets.
   - **Also flagged** (owner's cap, 2026-10-26): keeping exact TT entries
     (`UseTtKeepExact`, the second review's claim (e)), off by default: its
     SPRT on [-3, 0] ended INCONCLUSIVE at the cap, -0.6 ± 7.5 Elo after
     4,800 games (LLR 0.09 of 2.94).
7. **Next phase-end audit** (audit-1's open items; owner, 2026-10-28):
   checked at the end of Phase 4 with the phase-end checklist (Phase 3
   closed the same day without them), each
   settled by a test, a measurement or a recorded reason:
   - a one-sided table bound clamped inside the window is stored as Exact
     at PV nodes (audit-1 suspicion 1b; A1 s2);
   - mate distances beyond MaxPly overstated through the TT (suspicion 9;
     theoretical, A1 s3);
   - idea 23's proxies may favour the baseline's own LMR shape and barely
     see root fail highs (10a, 10b; A6 S-4, A8 S-A8-2, S-A8-3); undefined
     behaviour in a candidate body passes the gate, which builds Release
     without sanitizers (10c; A6 S-5); the evolve loop's originality
     screen is a manual step (10h; A4 s2). All before idea 23 resumes;
   - spot-interruption pair bias in the AWS shards (10f; A6 S-2), before
     the first AWS SPRT;
   - the "just above available memory" test can race other processes
     (11b; A5 S-1);
   - the post-edit hook's clang-format version against the one the audit
     used (13; A9 U-2);
   - proofs not run: fuzz_uci's coverage of the search on a `go depth 5`
     seed (with the checklist's fuzz step); the book-slice match (the
     cloud shards' shuffled book removes the bias it would measure, so it
     may be dropped with that reason); `test_hooks.sh` with its two build
     cases; `uci_timing` on an idle machine; the local Windows rebuild of
     the v3, AVX-512, no-PEXT and PGO presets (checklist item 1 covers it).

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
  move (review finding). The search's result then takes that iteration's
  depth with its move and score, so the result (the web page's depth) and
  the last `info` line describe the same search; the last finished
  iteration stays in the time-management signals (2026-11-10).
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
  rounded, at least 1. **Exception (owner, 2026-11-09):** eleven bounds
  widened past the rule for the final retune, steps kept (§5.6 step 19).
  Tests (`params` suite): every default in its range,
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
| `StopCheckInterval` | 1024 nodes | At about 10M nps that is a poll every 0.1 ms: far finer than the 1 ms clock, at a negligible cost per node. |
| `fail_report_ms` (a `Searcher` member, tests set 0) | 1000 ms | UCI GUIs need no fail-high/low lines for searches shorter than a second; it keeps fast games' output small. |
| `RfpMaxDepth` | 6 | At depth 6 the margin reaches 480 cp, a knight plus nearly two pawns; beyond that a static eval no longer bounds what the search can find (reasoning). |
| `RfpMargin` | 55 cp per ply (was 80) | **SPSA-tuned and adopted (owner, 2026-11-09; r14-spsa: spsa-r14-m2, 13 iterations, 10,400 pairs at 8+0.08, then STC design R +37.93 ± 10.03 Elo, H1; the set adopted as a whole, an owner exception to the LTC rule; docs/history/phase-4/sprt-log.md):** 80 -> 55 (pinned at the SPSA floor 40 + c, its gradient still pushing down; the final retune widens the lower bound to about 30). **Measured** (audit-1, 2026-10-27; owner: a justification from Fork's own data). With RFP off, at every node where RFP's other conditions hold and the pruning eval is at least beta, the share of the nodes a margin M·d would prune whose full search then fails low: on the bench (3.4 M such nodes) and on 300 evolve positions at depth 12 (15.7 M) it stays at most 0.37% for every M from 40 to 160 at every depth 1-6; at 80 it is 0.31% at depth 1 down to 0.03% at depth 6, within the pre-declared 1% criterion (LMP's) at every depth. The data bound the margin from below (40 is the smallest M that meets it) without picking a value. **40 was tried and reverted** (owner, 2026-10-28): adopted without an SPRT, it scored 22.5 points below Milestone C on the same 357 gauntlet games before that gauntlet was stopped, while 80 matched Milestone C over all 1,200 (Fork 2411.5 ± 22.5 against 2402.5 ± 23.3; history/phase-3/audit-1.md; ideas.md idea 34). Originally four fifths of a pawn per ply (reasoning); the value matches Berserk 4.5.0's margin (ORIGINALITY.md, 2026-10-27), kept with this measurement as Fork's own justification (owner, 2026-10-28). Range 40-160, step 6. |
| `NullMinDepth` | 3 | Below depth 3 the null search would be at least as costly as the node it replaces. |
| Null-search depth | d/2 − 1 − surplus plies | Fork's form: the null search only has to show that passing still fails high, so it gets half the remaining depth, one ply less for the pass; at depth 3 that is the quiescence search. |
| `NullSurplusPerPly` | 301 cp (was 300) | **SPSA-tuned and adopted (owner, 2026-11-09; r14-spsa: spsa-r14-m2, 13 iterations, 10,400 pairs at 8+0.08, then STC design R +37.93 ± 10.03 Elo, H1; the set adopted as a whole, an owner exception to the LTC rule; docs/history/phase-4/sprt-log.md):** 300 -> 301. One extra ply of reduction per knight of static surplus over beta (the bootstrap knight value): with a whole piece in hand, a shallower search still finds any refutation that matters. |
| `NullSurplusPliesMax` | 2 | Two pieces of surplus is already decisive; more reduction would leave too little depth to see threats. |
| `DisplayFittedScale` (display only, `src/uci/score_display.hpp`; adopted 2026-11-13, **removed with CalibratedScore the same day**: no longer in the code; the measurement stays as a record) | 67 cp | **Measured** (2026-11-12, ~/fork-data/calib-1112, method declared before the fits): the logistic scale k of E[score] = 1 / (1 + exp(-(s + b) / k)) fitted by maximum likelihood to Fork's own search scores against game results, positions past the first 6 engine plies, mates and tablebase scores excluded, |s| <= 10 pawns, CIs by an opening-clustered bootstrap. Population: probcut-ltc2's 4,992 UHO games at 40+0.4 between two r8brft1 builds (67.0, 95% 63.9-69.5): near-equal opponents, the longest TC and a biased book, the closest of the measured sets to TCEC conditions (longer TC; TCEC's books: the Cup's rise in bias, the Swiss's bias UNVERIFIED, docs/kb/competition.md). Other sets: UHO STC self-play 65.1, decision-audit UHO 69.4, random 8-ply book 56.4, gauntlet 60.2; queens on about 0.75 of queens off. Not a search constant: the search never reads it. Screen: no match (2026-11-12). |
| `DisplayTargetScale` (display only; adopted 2026-11-13, **removed with CalibratedScore the same day**: no longer in the code; the measurement stays as a record) | 88 cp | r8brft1's own output scale S (docs/nets.md), the scale its training targets and Fork's web eval bar use: the shown score means what the network's scale says. Screen: no match (2026-11-12). |
| `LmrMinDepth` | 3 | From depth 3 a reduced search still has at least one ply left (reductions are clamped to [1, d − 1]). |
| `LmrMinMove` | 4 | The first three moves (the TT move and the best captures, usually) take almost all cutoffs: 87.8% on the first move, mean cutoff index 0.27 (bench, FORK_SEARCH_STATS). |
| LMR divisor | 4.5 (log2 · log2) | Fork's choice of anchors: one ply at depth 3 from the third move, 2 plies at (8, 10), 3 at (12, 20), 5 at (20, 30), 8 at (63, 63); the reductions grow slowly enough to stay below a third of the depth. |
| `LmrCheckRelief` (tier 2 step 0) | 1 ply | **The minimal reduction unit, not a tuned constant** (owner, 2026-10-29): a late quiet move that gives check is reduced one whole ply less, the smallest step there is in Fork's LMR, whose reductions are whole plies. Its STC SPRT passed: +11.26 +/- 5.54 Elo after 9,600 games ([0, 3]). The constant screen found the same one-ply relief for checking moves in Berserk, a coincidence noted in ORIGINALITY.md, kept by the owner. |
| `SingularMarginPerPly` (tier 2, T27) | 6 cp per ply | **Measured** (2026-10-31, `tools/singular_measure.py`, S-512): 2,700 nodes where a singular test could run, 300 per depth 4-12, sampled from depth-13 searches of 80 evolve positions, each searched again from scratch with `searchmoves` (the TT move alone and the other moves, at half and at full depth). A margin flags the TT move when the other moves' half-depth score is below the TT score minus M·d; the pre-declared rule takes the smallest M at which, at every depth 6-12, at least 90% of flagged moves are still strictly best at full depth (cells with fewer than 20 flagged samples count as unknown). At 6 that is 0.91 at depth 6 rising to 0.97-0.98 at 7-12 (31-72 flagged per depth); at 4, depth 6 gives 0.89. Unflagged, the TT move is strictly best at full depth in 61% of the samples. **Re-measured 2026-11-12 on r8brft1** (builder 3's C6 run, tier2/c6-singular-measure b71199d; the staleness audit, docs/research/staleness-audit-2026-11-12.md): the same rule now picks 22; **22 against 6, design R at STC: H0 after stage 0, −26.76 ± 9.93 Elo**, so 6 stays. **Final-retune range 2-16** (the owner's decision, 2026-11-12, about 2:10 PM EST; was 2-12; default and step 1 unchanged; replaces the 2-44 planned before the SPRT's result; final-retune.md §3.2, a class (b) dimension). |
| `SingularMinDepth` (tier 2, T27) | 6 | **Measured**, same data and rule: at 6 cp per ply depth 5 gives 0.86 and depth 4 0.92, so 6 is the smallest depth from which every depth to 12 passes. |
| `SingularEntrySlack` (tier 2, T27) | 3 plies | **Measured**, same data and rule: the TT entry may be up to 3 plies shallower than the node. By deficit (depths 6-12, margin 6): 0 plies 0.94 (31 flagged), 1 0.98 (256), 2 1.00 (37), 3 0.92 (26); 4 plies has 13 flagged samples, too few to count. |
| `NoMoveReduceMinDepth` (tier 2, T26) | 8 | **Measured** (2026-11-01, `tools/no_move_measure.py`, S-512, in a separate worktree; owner: option B, a quality-per-node sweep with the rule fixed before the runs): the 4,794 evolve positions relabeled by the current engine at 25 M nodes with the reduction off (4,740 kept: no mate, \|score\| ≤ 1500 cp), then searched at 250,000 and 2,500,000 nodes from a fresh state with the reduction off and at minimum depths 2-8; per position, 1 for the label's move less the capped score error / 1000 (the evolve proxies), averaged over both budgets. Fitness: off 0.7273, 2 0.7113, 3 0.7090, 4 0.7203, 5 0.7179, 6 0.7149, 7 0.7206, **8 0.7204**; 7, 8 and 4 lie within the rule's 0.001 tie margin and the tie goes to the largest depth. **No depth beat "off"**: the paired 95% intervals of the gain over off are all below zero or reach it at most (8: −0.0068 [−0.0131, −0.0004]). The loss is in agreement at 2.5 M nodes (off 0.827, 7-8 0.807-0.808); the score error is lower with the reduction (23.9 cp against 25.7) and agreement at 250,000 nodes is level (0.698-0.702). The labels come from "off", which favours it on move agreement; the reduction also reaches depth 14 in fewer nodes (geometric mean, 4,636 positions: off 625,906, 8 495,872, 2 273,371). The rule sends 8 to the SPRT, which decides: **passed** (+21.45 ± 5.98 Elo after 4,800 games, [0, 3], on S512r2; 2026-11-02), the switch is on. The constant screen found 8 with a 1-ply reduction on a missing TT move in Stockfish 15 and in current Weiss, both at cut nodes only (Weiss before reverse futility and null-move pruning); Fork reduces at every node type, after them. Kept by the owner with credit (2026-11-01; ORIGINALITY.md). The tied 7 was screened too and matched Ethereal and Stockfish 17.1 in the same role. |
| `CutNodeLmrPlies` (tier 2, T17, node types; switch `UseCutNodeLmr`, on) | 1 ply | **Head-to-head, then design R SPRTs at STC and LTC; adopted 2026-11-11 (pre-approved by the owner).** Candidates declared before any game (2026-11-09; design R with constants by head-to-head selection, think tank decisions 2 and 3): 1 ply, the smallest unit of Fork's whole-ply LMR, and 2 plies (an expected cut node needs only its refutation, so its late quiets can bear the next unit; the base reduction at LMR's depths is 1.59 plies on average on the bench, FORK_SEARCH_STATS), 1 preferred on a tie (the more cautious). **Head-to-head** b4-cut-node-h2h (3,200 games on the same openings, runs 42883612798 and 42886734291): 2 − 1 = −5.33 ± 12.04 nElo, so 1 kept. **SPRTs** against off (tier2/b4-r14 ff0c088, S512ppr3 on both sides; test 6b4e407): STC b4-cut-node-stc **+6.02 ± 3.67 Elo** (nElo +10.55 ± 6.43), H1 after 11,200 games; LTC b4-cut-node-ltc (40+0.4) **+9.75 ± 5.14 Elo** (nElo +18.28 ± 9.64), H1 after 4,992 games (sprt-log). At an expected cut node (PlyFrame::expected_cut: the root's and a PV node's later children and an all node's children are expected cut nodes, a cut node's children expected all nodes, as in a minimal tree; the null move's child is the opposite of its parent), not a PV node, late quiet moves are reduced this much more, inside LMR's clamp. **Constant screens:** 2026-11-09, 1 ply matches Stockfish sf_4-sf_5 and Berserk 8 (near matches in later releases); 2026-11-11, on the four engines' current default branches, Berserk matches (a 1-ply cut-node increase), Stockfish, Ethereal and Weiss do not. One whole ply is the smallest unit of this form (generic); the idea is credited in ORIGINALITY.md. The switch stays until the Phase 4 re-validation; the final retune and fractional depth (idea 43) may refine the amount. |
| `ThreatBuckets` (tier 2, T56, threat-aware quiet ordering; switch `UseThreatBuckets`, on) | 4 | **A definition, not a tuned constant**: the butterfly history's bucket is two yes/no facts about the position before the quiet move, whether an enemy piece attacks its from-square and whether one attacks its to-square, so there are four. The layout is credited in ORIGINALITY.md (2026-11-10). **Design R SPRTs at STC and LTC; adopted 2026-11-11 (pre-approved by the owner):** STC +7.49 ± 4.89 Elo (6,400 games), LTC +8.07 ± 5.15 Elo (4,992 games); sprt-log. |
| `DriftWeightCap`, `DriftWeightTotal`, `DriftLimit`, `DriftSlotBits`, `DriftGrain` (tier 2, the drift tables: think tank R34, engine survey E4; branch tier2/corr-tables, every switch off) | 4, 256, 300 cp, 15 (2^15 slots per side to move, 256 KB a table), 128 | **Reused from the pawn drift table's measurement** (T32, branch tier2/drift, 2026-11-02, S512r2; the owner's instruction of 2026-11-11 to reuse the existing correction infrastructure: update rule, weights, clamping): an update moves an entry min(depth, 4) / 256 of the way to the error clamped at 300 cp (the 99th percentile of the exact results' raw error there, rounded up), 2^15 slots (the smallest count under a 2% collision share for the pawn key), entries in 1/128 cp. Measured for the pawn key, not for these keys: **UNVERIFIED that they suit them** (a later learning-rate test, E5, may refine them). The total 256 was found in the same role in Berserk 13 and Viridithas in 2026-11-02's screen and credited (kept by the owner); the screen of 2026-11-11 on the four engines' current default branches found no value match. **Shipped with the minor table, adopted 2026-11-12** (the `MinorDriftShare` row): these values are the ones its SPRT played. **`DriftLimit` 300 joins the final retune's SPSA as a class (a) dimension** with the share (final-retune.md §3.1; range 150-600, step 23, the parameter table's): the offline diagnosis of 2026-11-12 found the limit alone does not stop the share-64 runaway (minor 64 with limit 150 still +8.3 cp worse against deep labels), so it is tuned with the share rather than before it. `DriftWeightCap` and `DriftWeightTotal` (the learning rate) are left to E5 and not added; `DriftSlotBits` and `DriftGrain` are table layout, not tuned. |
| `PieceDriftShare`, `MinorDriftShare`, `MajorDriftShare`, `ThreatDriftShare` (switches `UsePieceDrift`, `UseMinorDrift`, `UseMajorDrift`, `UseThreatDrift`; `UseMinorDrift` on since 2026-11-12, the others off) | 64 (in 1/64: the whole learned drift), the natural value; **`MinorDriftShare` 32 (half the drift; adopted 2026-11-12)** | **The natural value, no head-to-head** (owner, 2026-11-11 7:45 PM EST: a constant the final retune's SPSA will tune gets its SPRT at the natural value): 64, the whole learned drift, as the pawn drift table applied it, in each table's design R STC SPRT against off; a pass is adopted (pre-approved) and the share joins the final retune's SPSA dimensions; a failure gets one retry at 32 (half the drift; try 2, night items 19-corr-*-retry). Passive reading (report only): every table erred more at half its term than at the whole term (summed fitness 0.84-0.89 against 0.73-0.80, the 200,000-node run). Ranges 32-128 step 5 (the rule); `MinorDriftShare` 16-64 since its adoption (the owner's decision, 2026-11-12: half to twice of 32). The screen of 2026-11-11 found no match for 64/64 or 32/64. **Results (2026-11-12; design R STC SPRTs against off tier2/corr-tables-e1 dd5db13, sprt-log):** threat 64 H0 (−10.53 ± 6.95 Elo, 3,200 games), threat 32 H0 (−7.38 ± 7.01, 3,200; the threat table's two tries used), minor 64 H0 (−18.26 ± 9.95, 1,600), **minor 32 H1 (+5.57 ± 4.01 Elo, nElo +9.66 ± 6.95, 9,600 games), adopted** (the owner's overnight pre-approval). The offline diagnosis of 2026-11-12 (40 games replayed at 200,000 nodes against 1,000,000-node labels) explains the split: at share 64 one table's term feeds on itself (the applied term enters the subtree results the table then learns from) and runs to the 300 cp limit (minor 64: mean term 44.9 cp, 3.0% of node visits at the limit, search error +23.7 cp [+14.5, +34.2] against the labels); at 32 it stays bounded (mean term 17.5 cp, 0.016% at the limit) and the search error improves, −2.5 cp [−4.5, −0.8]. **`MinorDriftShare` 32 joins the final retune's SPSA as a class (a) dimension** (final-retune.md §3.1: the term acts through the shallow pruning evals and the stand-pat), with its range 16-64, the adopted 32 centred (the owner's decision, 2026-11-12; 32 had been the floor of the range declared for 64). The piece and major shares stay 64 until their own tests; the diagnosis recommends a depth-scaled term before them (not decided here; the owner's). |
| `DriftShareUnit` | 64 | **A unit**, not a tuned value: shares in 1/64 move in steps of about 1.6% of the drift. |
| The piece term (`UsePieceDrift`) | the mean of the two colours' tables | **A definition:** each colour's table learns the whole error, so their mean is one estimate of it (their sum would apply it twice). The per-colour, king-inclusive key is R34's; the screen found the concept in Stockfish, Berserk and Weiss (credited in ORIGINALITY.md). |
| The threat key (`UseThreatDrift`) | three square sets hashed with splitmix's output function | **A definition, Fork's own:** the side to move's pieces other than pawns and kings that the opponent attacks, the opponent's that it attacks, and those of either colour an enemy pawn attacks (the cheapest attacker). Pawns are left out (one is attacked in most positions), kings too (check is never evaluated). No threat-keyed table in the four engines screened. |
| `DriftTailError` (stats builds only) | 100 cp | **A measurement setting:** the think tank's tail bins (I5, \|r\| > 100 cp), for the passive ranking's tail fitness. |
| `CaptureProbeMinDepth` (tier 2, T31, ProbCut; switch `UseCaptureProbe`, on) | 9 | **Measured** (2026-11-06, `tools/tier2_measure.py`, spec `capture_probe`, the rule and the grid committed before any run: d5a6eb6): the 4,758 positions of the LMR measurement's 25 M-node labels by the default engine (S512r2, IIR on); minimum depths 3, 4, 5, 7, 9 x reductions 2-5 x margins 50, 80, 130, 200, 320, 500 cp (120 settings, the placeholders 6, 3 and 240 not the grids' centres), each screened at 250,000 nodes, the best 6 then searched with "off" at 250,000 and 2,500,000 nodes; per position, 1 for the label's move less the capped score error / 1000, averaged over both budgets. Fitness: off 0.7539, **d9-r5-m80 0.7490**, d9-r5-m130 0.7476, d9-r4-m130 0.7467, d9-r4-m80 0.7456, d9-r2-m500 0.7451, d9-r3-m130 0.7448; the rule sends d9-r5-m80 to the SPRT. **No setting beat "off"** (d9-r5-m80: −0.0049 [−0.0101, +0.0006]); the depth and the reduction sit at the top of their grids, and the owner chose no extension (2026-11-06): the SPRT decides, as with IIR, whose measurement was also below "off" before it passed at STC and LTC. Time to depth 15 (geometric mean over 4,459 positions): off 705,129, d9-r5-m80 675,514. The constant screen (2026-11-06) found no match in this role. The placeholder's reasoning, kept for the record: the probe's verification search runs `CaptureProbeReduction` plies below a normal child, so from a few plies deep it is a real search rather than a quiescence search. Range 4-18, step 1 (the ranges rule). Ported unchanged onto the tuned search (branch tier2/probcut-r3 on phase-4 d1fe24b, T56 on; 2026-11-11) after the STC SPRT on S512r2 ended H0 (−5.29 ± 3.58 Elo after 12,800 games; sprt-log "probcut-d9r5m80-vs-base"); one LTC-only design R test decides it (owner, 2026-11-11). **That test passed and ProbCut was adopted 2026-11-11 (pre-approved by the owner):** probcut-ltc2 (40+0.4, Hash 64, design R [0, 6]; test 6d7ffb1 against off d47e479, r8brft1 on both sides) **+9.40 ± 5.03 Elo** (nElo +18.03 ± 9.64), H1 after 4,992 games (sprt-log). The three values are kept as measured (9 / 5 / 80) and, as LTC-only constants of a technique that acts only at depth 9 and beyond, join the final retune's SPSA as class (b) dimensions (docs/research/phase4-designs/final-retune.md §3.2). **Set on S512r2 (2026-11-06), not re-measured on r8brft1, by the owner's decision (2026-11-12, about 2:10 PM EST: "ProbCut's constants stay unmeasured until the final retune (LTC class)"):** the staleness audit's re-run of this measurement was withdrawn before it started (docs/research/staleness-audit-2026-11-12.md §3), so the final retune's LTC pass is the three values' first measurement on the current net. The switch stays until the Phase 4 re-validation. |
| `CaptureProbeReduction` (tier 2, T31) | 5 plies | **Measured** with `CaptureProbeMinDepth` (its row: one measurement of the three). The verification search runs depth − 1 − 5 plies. The constant screen (2026-11-06) found the literal 5 as the ProbCut reduction in Halogen, Clover and one branch of Stockfish's verification depth, where the verification child is searched 5 plies below the node; Fork's is 6 plies below (one deeper than a normal child's depth − 1), so the effective reduction differs (recorded in ORIGINALITY.md). Range 2-10, step 1 (the ranges rule). Set on S512r2 (2026-11-06), not re-measured on r8brft1, by the owner's decision (2026-11-12): LTC class of the final retune (the `CaptureProbeMinDepth` row). |
| `CaptureProbeMargin` (tier 2, T31) | 80 cp | **Measured** with `CaptureProbeMinDepth` (its row). The bar a capture must hold is beta + 80; only captures and queen promotions whose SEE could lift the pruning eval to the bar are tried, first with a zero-window quiescence search at the bar, then the reduced search; a capture that holds returns its score and stores a lower bound at the probe's depth; skipped when a TT entry at least that deep proves the node below the bar. The constant screen (2026-11-06) found 80 an exact same-role match: Ethereal 12.50, 12.75 and 13.00's ProbCut margin, and Xiphos's; **kept by the owner with credit (2026-11-06; ORIGINALITY.md)**, a value of Fork's own pre-declared geometric grid chosen by its rule. Tied to the evaluation's scale, like every margin, so it is retuned with them. Range 40-160, step 6 (the ranges rule). Set on S512r2 (2026-11-06), not re-measured on r8brft1, by the owner's decision (2026-11-12): LTC class of the final retune (the `CaptureProbeMinDepth` row). |
| `QuiesceMoveCap` (the engine survey's B16, move-count pruning in the quiescence search; switch `UseQuiesceMoveCap`, on since 2026-11-13; ideas.md idea 120) | **2 moves** (adopted 2026-11-13, the retry value; the natural value 3 stopped for futility) | With the switch on, a quiescence node out of check searches at most this many moves (captures and queen promotions in the selector's order: the TT move, then by victim and take history) and prunes the rest; in check every evasion is still searched. **Reasoning:** the main search treats its first three moves as early (`LmrMinMove` 4: the first three are never reduced), and the quiescence search has no reduction to fall back on, so its cap starts where the main search starts doubting a move: 3, the natural value, tested first. **Retry value** 2 (only if the first SPRT was not H1): a node keeps only its two best-ordered captures. **Screen (2026-11-12; Stockfish def601c and sf_6 to sf_17, Ethereal 0e47e9b, Berserk d7e1f05, Weiss c735b8f):** names no match; 3 no match; **2 matches Stockfish (sf_12 and later, master)**, a natural value kept as the retry and credited in ORIGINALITY.md (owner's rule of 2026-11-11); the idea is prior art in Stockfish (sf_10 and later, narrower scope), credited. Decided by design R at STC against off (ledger idea `b16-qs-move-cap`; night items 60a and 60b): the first try at the natural value 3, b16-qs-move-cap-stc (test sprt/b16-qs-lmp a03b0db, bench 9,773,608 / 77d045463a0c9b36; from stage 0), stopped for futility after stage 1: −0.22 ± 6.92 Elo (nElo −0.38 ± 12.04), Ptnml [38, 376, 775, 372, 39], LLR −0.54, 3,200 games, no time losses (runs 43441749955 and 43444719077; 9:57 AM EST 2026-11-13); **the retry passed and B16 was adopted at 2 on 2026-11-13** (pre-approved by the owner's rule of 2026-11-11: one SPRT at the natural value, one retry at a second value): b16-qs-move-cap-retry (STC 8+0.08, Hash 16, design R [0, 6], beta 0.20, cap 8, futility look after 2 stages, on fresh openings from stage 2): **+8.90 ± 5.56 Elo** (nElo +15.75 ± 9.83), Ptnml [35, 547, 1135, 626, 57], **H1** (LLR 3.04, bounds −1.56, 2.77) after stages 2-4, 4,800 games, no time losses (runs 43447742059, 43450913249, 43454049003; 10:53 AM EST 2026-11-13); sprt-log. Range 1-6, step 1; a class (a) dimension of the final retune (final-retune.md §3.1). |
| Root reductions (bug review 2026-11-11 §3; switch `UseRootLmr`, on since 2026-11-13; ideas.md idea 124) | the LMR table, no new constant | **A definition, not a tuned constant.** With the switch on (and LMR and PVS on), a late quiet root move (its index + 1 at least `LmrMinMove`, the iteration at least `LmrMinDepth` deep) gets the LMR table's reduction for that depth and move number, less `LmrCheckRelief` if it gives check, on a zero window first; if it beats alpha it is searched again at full depth, then on the full window as before. No context correction, cut-node or not-improving plies and no R20 history term (the whole-ply table entry only, as tested). **Reasoning:** the bug review found later root moves never reduced, though the same move at ply 1 would be; the root's move order is the best Fork has (the previous iteration's best first), so its late quiets are as unlikely as anywhere. **Screen (2026-11-12; Stockfish def601c and sf_13 to sf_17.1, Ethereal 0e47e9b, Berserk d7e1f05, Weiss c735b8f):** names no match; root reductions are shared practice in all four, credited in ORIGINALITY.md. **Adopted 2026-11-13 (pre-approved by the owner) on its STC and LTC passes** (design R [0, 6] against off; ledger idea `root-lmr`; night items 64a and 64c): root-lmr-stc +17.71 ± 6.74 Elo (nElo +31.68 ± 12.04), H1 after 3,200 games; root-lmr-ltc (40+0.4) +14.94 ± 6.24 Elo (nElo +28.29 ± 11.80), H1 after 3,328 games (sprt-log). No final-retune dimension (no constant of its own: it reads `LmrMinMove`, `LmrMinDepth`, the table and `LmrCheckRelief`, already tuned with LMR). The switch stays until the Phase 4 re-validation. |
| `HistorySkipMaxDepth` (tier 2, T24, quiet history pruning, the engine survey's B13; switch `UseHistorySkip`, on since 2026-11-12) | 3 | **Placeholder, kept from Fork's first build of the skip** (tier2/b4 d2b086d, 2026-11-05) and not varied in the head-to-head, which chooses the threshold only (owner, 2026-11-11: "a threshold chosen to actually fire"). Reasoning: the skip acts where a quiet move's history is a cheap stand-in for its search, the last plies before the horizon; 3 keeps it below late move pruning's depth limit (`LmpMaxDepth` 4), so both prune the same shallow region, LMP by move count and the skip by history. The deepest node where a quiet move can be skipped; later moves only (a move already searched, past LMP), non-PV, not in check. **Constant screen (2026-11-11; Stockfish def601c, Ethereal 0e47e9b, Berserk d7e1f05, Weiss c735b8f):** matches Ethereal (the non-improving depth limit of its history pruning), a near match in Weiss (3 as a strict bound on the reduced depth); no match in Stockfish or Berserk. A small whole-ply limit, credited in ORIGINALITY.md. **Adopted 2026-11-12 with the skip** (the `HistorySkipPerPly` row). It was never measured as a value of its own, so it joins the final retune's SPSA with the threshold as a class (a) dimension (final-retune.md §3.1; the efficiency rule), where it is measured. |
| `HistorySkipPerPly` (tier 2, T24) | **700 per ply** (adopted 2026-11-12; the head-to-head's pick of 2000, 1300 and 700) | The threshold is minus this times the depth, on the quiet ordering score's scale (`quiet_order_score`: the butterfly history in the move's threat bucket plus the weighted reply and follow tables), and a quiet move at or below it is skipped. **Candidates by a firing-rate measurement** (tools/tier2_measure/history_skip.json, its rule declared before its run): 48 games of the r8b-rft-stc SPRT replayed with history carried (tools/measure/game_replay.py, 200,000 nodes per search, a stats build counting each eligible quiet move's score by depth, bins of 100), the switch off, on phase-4 b2e083e (T56's threat buckets on); the values predicted to skip 5%, 10% and 20% of the eligible quiet moves at depths 1-3: **2000 (5.19%), 1300 (10.48%), 700 (20.12%)**. With the switch on the same replay skips **13.92%, 26.19% and 44.13%** (more than predicted: the skip changes the histories it reads, UNVERIFIED as the mechanism); bench 11,081,805 (+9.01%), 10,008,258 (−1.55%) and 9,886,698 (−2.75%) against 10,166,167. On the bench alone (history cleared per position) the shares are 2.86%, 3.15% and 11.01%, which is why the first build (bench-tested only) seemed not to fire. (The same measurement on phase-4 4470f24, before T56, gave 2300, 1600 and 900; those commits were superseded before any game.) **Chosen by a head-to-head** (qhp-h2h, a round robin of 2 stages of 1,600 games per pairing at STC; 2000 kept on a tie, the most cautious), then design R at STC against off (qhp-stc). **Constant screens (2026-11-11, same clones):** 700, 1300 and 2000 match none of the four (Ethereal's threshold has a different form, not scaled by depth). **Head-to-head qhp-h2h** (2026-11-11, test commits c06d62b, f6397e0 and 13d4d05 on b2e083e's engine; 9,600 games, runs 43113474240 to 43125463839): 1300 − 2000 +9.42 ± 9.83 nElo, 700 − 2000 +9.62 ± 9.83 nElo (least squares over the three pairings), so **700 picked** (the tie rule, 2000 unless beaten by more than 0.5 e, not applied). **qhp-stc** (STC 8+0.08, Hash 16, design R [0, 6], fresh openings from stage 2; test sprt/qhp-t56-700-e1 4701319 against off tier2/qhp-t56-e1 4cae4f4, both on adopt/e1 25623ab, r8brft1): **+6.04 ± 4.37 Elo** (nElo +10.52 ± 7.61), Ptnml [83, 899, 1917, 998, 103], **H1** (LLR 2.99) after stages 2-6, 8,000 games (runs 43182618097 to 43193266205; 4:57 AM EST 2026-11-12; sprt-log). **Adopted 2026-11-12** (the owner's overnight pre-approval). As a shallow ordering margin (depths 1-3) it joins the final retune's SPSA as a class (a) dimension (final-retune.md §3.1; the efficiency rule: not tuned again before it). Range 350-4000, step 183, as declared for the candidates; 350 is the ranges rule's half of 700, the ceiling is beyond its twice (1400), left for step 19's range check. |
| Pair-table update base (the engine survey's D8; switch `UsePairSumUpdate`, on since 2026-11-12) | the summed entries, no constant | **A definition, not a tuned constant.** With the switch on, a cutoff's bonus and maluses move each pair-table entry (reply and follow) by the same self-limiting rule as before, v + b − S·\|b\| / HistoryMax, but with S the move's reply and follow entries summed (both read before either is updated) instead of the entry alone, so the two tables approach the limit together; the result is clamped to ±`HistoryMax` (one entry can sit far from the sum). A table the node does not read (no arrival, or its switch off) is neither summed nor updated, so with one table the update is the usual one. The sum is unweighted (the ordering weights `ReplyWeight` and `FollowWeight` stay where they are read; the final retune, §5.6 step 19, tunes them with the rule in place). **Screen (2026-11-11; Stockfish def601c and releases sf_6 to sf_18, Ethereal 0e47e9b, Berserk d7e1f05, Weiss c735b8f):** no match (none of the four uses the summed base, and none uses 10,000 as the divisor or limit of a continuation update). **Design R at STC passed and D8 was adopted 2026-11-12** (pre-approved by the owner): survey-d8-stc (STC 8+0.08, Hash 16, design R [0, 6], cap 8, futility look after 2 stages, from stage 0): test sprt/d8-pair-sum-e1 dd132c9 against off tier2/d8-pair-sum-e1 aa8dd0d, both on adopt/e1 25623ab (phase-4 784b1b0's engine with E1; no ProbCut, no history skip, no drift table), r8brft1 on both sides, **+4.29 ± 3.46 Elo** (nElo +7.47 ± 6.02), Ptnml [136, 1483, 3011, 1627, 143], **H1** (LLR 2.84) after stages 0-7, 12,800 games (runs 43196026493 to 43216014186; 7:32 AM EST 2026-11-12; sprt-log). No constant, so no SPSA dimension of its own (final-retune.md §3.1). The switch stays until the Phase 4 re-validation. |
| `DirectCheckBonus` (the engine survey's D13, the direct-check ordering bonus; switch `UseCheckOrderBonus`, on since 2026-11-12) | **5000** (adopted 2026-11-12, the natural value) | In the main search out of check, a quiet move (not castling) whose piece attacks the enemy king from its destination adds this to its ordering score (the butterfly history in its threat bucket plus the weighted reply and follow tables, then clamped to int16 again); evasions, the root's initial order and the quiescence search are unchanged. A direct check only: the squares from which each piece type would attack the king are computed once per node on the board before the move (`direct_check_targets`), exact for a quiet move because a piece whose origin was the only blocker between its destination and the king would already be giving check. **The natural value:** half of one history table's range (±`HistoryMax`, 10,000; the quiet scores at LMR sites lie mostly within a few thousand of zero, X2), so a checking quiet passes quiets of similar or somewhat better history but not one the tables rate near their limit. **No head-to-head** (owner, 2026-11-11 about 7:45 PM EST: a constant the final retune will tune gets none; the candidates 2500, 5000 and 10000 declared before then were not played against each other; 2500 was the retry's value, unused). **Screen (2026-11-11; Stockfish def601c and releases sf_6 to sf_18, Ethereal 0e47e9b, Berserk d7e1f05, Weiss c735b8f):** no match for 2500, 5000 or 10000 (Stockfish has a quiet-check ordering bonus of another value; Ethereal, Berserk and Weiss have none). **Design R at STC passed and D13 was adopted 2026-11-12** (pre-approved by the owner): survey-d13-stc (STC 8+0.08, Hash 16, design R [0, 6], cap 8, futility look after 2 stages, from stage 0): test sprt/d13-check-order-5000-e1 cc7b3bc against off tier2/d13-check-order-e1 35209f0, both on adopt/e1 25623ab (phase-4 784b1b0's engine with E1; no ProbCut, no history skip, no drift table, no D8), r8brft1 on both sides, **+5.50 ± 3.93 Elo** (nElo +9.73 ± 6.95), Ptnml [93, 1082, 2306, 1218, 101], **H1** (LLR 3.21) after stages 0-5, 9,600 games (runs 43229400100 to 43247622236; 10:44 AM EST 2026-11-12; sprt-log). As an ordering weight it joins the final retune's SPSA as a class (a) dimension (final-retune.md §3.1; the efficiency rule: not tuned again before it). **Range 2500-10000, step 375** (owner, 2026-11-12 about 12:50 PM EST: "DirectCheckBonus final-retune range 2500-10000"): the ranges rule's half to twice of 5000 with the rule's step (a twentieth of the range), replacing 0-20000, step 1000, as declared in the parameter table at the re-plan of 2026-11-11 (floor 0, the off-equivalent). The history skip (B13) reads `quiet_order_score` without the bonus (the tested D13 had no skip, the tested skip no bonus, so the port keeps each as tested): a quiet check whose history is at or below the skip's threshold can still be skipped at depths 1-3 although the selector now tries it early. Whether the skip should see the bonus is not measured (UNVERIFIED; a follow-up for the owner). **Follow-up (2026-11-12):** the skip now exempts quiet direct checks instead (`UseSkipCheckExempt`, the row below; adopted on its non-regression pass). The switch stays until the Phase 4 re-validation. |
| History skip's exemption for checking quiets (B13 with D13; switch `UseSkipCheckExempt`, on since 2026-11-12) | a condition, no constant | **A definition, not a tuned constant.** With the switch on, the history skip (`UseHistorySkip`) never skips a quiet move that gives direct check (`gives_direct_check`, D13's test: not castling, the moved piece attacks the enemy king from its destination, on the board before the move). The skip's ordering score has no D13 bonus, so without the exemption a check the selector put early could be skipped on bad history. Tested last in the skip's condition, so only a move the skip would take pays for it. **Adopted 2026-11-12 on its non-regression pass** (owner, about 4:50 PM EST: "run one non-regression SPRT [-3, 0] ... adopt on a pass (pre-approved), drop if it fails"): skip-check-exempt-stc (STC 8+0.08, Hash 16, design R [0, 6], cap 8, futility look after 2 stages, from stage 0): **capped undecided at +2.80 ± 3.43 Elo** (nElo +4.90 ± 6.02), Ptnml [136, 1494, 3030, 1611, 129], LLR 1.21 (bounds −1.56, 2.77) after stages 0-7, 12,800 games (runs 43285168897 to 43307235492; 4:27 PM EST); skip-check-exempt-nonreg ([−3, 0] nElo, alpha = beta = 0.05, the same pair, fresh openings, stages 8-20): **H1, +2.86 ± 2.77 Elo** (nElo +5.08 ± 4.91), Ptnml [167, 2274, 4587, 2378, 194], LLR 3.14 (bounds ±2.94) after stage 19, 19,200 games (runs 43330489013 to 43356312529; 10:21 PM EST); sprt-log. `HistorySkipPerPly` and `HistorySkipMaxDepth` are tuned with the exemption in place (final-retune.md §3.1). The switch stays until the Phase 4 re-validation. |
| `HistoryKeepQuarters` (the engine survey's D17, think tank R16, history ageing between searches; switch `UseHistoryAgeing`, on since 2026-11-12) | **2 quarters (a half)** (adopted 2026-11-12, the natural value) | At the start of each search (each `go`) every history entry (butterfly in every threat bucket, reply, follow, take) keeps this many quarters of its value, rounded toward zero (`Searcher::age_histories`). **Reasoning:** the gravity update is an average with a time constant of about 830 updates at depth 1 and 8 at depth 10 or more (R16, from S8), so entries learned only at shallow depths persist from move to move unchanged, although each move's search sees a position two plies on. A half is the natural first step of a fade: what a search learned counts for half by the next search and a quarter by the one after, so the last few moves' searches dominate; R16's own candidates were 3/4 and 1/2. **The natural value, no head-to-head** (owner, 2026-11-11 7:45 PM EST: a constant the final retune's SPSA will tune gets its SPRT at the natural value; the retry at 3 quarters, night item 52b, was not needed). Bench does not see it (each bench position starts from cleared histories), so the switch-on bench equals the switch-off one; the tests check a second search changes. **Screens (2026-11-11; Stockfish def601c and sf_7 to sf_17, Ethereal 0e47e9b, Berserk d7e1f05, Weiss c735b8f):** names no match; the idea is a near match to Stockfish's current head; 2 quarters matches none; the unused retry value 3 quarters is a near match to Stockfish's current head (credited in ORIGINALITY.md). **Design R at STC passed and D17 was adopted 2026-11-12** (pre-approved by the owner's rule of 2026-11-11): survey-d17-stc (STC 8+0.08, Hash 16, design R [0, 6], cap 8, futility look after 2 stages, from stage 0): test sprt/d17-history-ageing-2 ee3a6c7 (the switch on, `HistoryKeepQuarters` 2) against off tier2/d17-history-ageing 94999a9 (phase-4 a95e269's engine with the ageing built in, off; no ProbCut, E1, history skip, drift table, D8, D13 or exemption), bench 10,166,167 / d874b380155a2e8c on both (bench cannot see the ageing), r8brft1 on both sides, **+5.71 ± 3.77 Elo** (nElo +9.74 ± 6.43), Ptnml [132, 1278, 2626, 1402, 162], **H1** (LLR 3.75, bounds −1.56, 2.77) after stages 0-6, 11,200 games, no time losses (runs 43350847538 to 43363398879; 11:25 PM EST 2026-11-12; sprt-log). As a history weight it joins the final retune's SPSA as a class (a) dimension (final-retune.md §3.1; range 0-4, step 1: 0 clears the tables at every search, 4 is no ageing; a finer grid would need a new unit). Cost: one pass over the tables (about 2.4 MB, nearly all the two pair tables) per search; bench/ab_search.py (clang-release, Windows, not pinned, the shared machine busy; A = phase-4 1b5a482, B = the port's build of this commit's engine code from the uncommitted tree on 1b5a482, r8brft1; identity checked on all 24 runs, `--same-nodes`): 12 interleaved rounds, median nps +0.9%, best +2.5%, under the 3.0% noise threshold: no significant difference. The bench pays one ageing pass per position (each position is its own search, on cleared tables), so the pass's price is inside that measurement; the bench's nodes are unchanged. The switch stays until the Phase 4 re-validation. |
| The improving flag (the engine survey's B9, think tank R17; switches `UseImprovingLmp` and `UseImprovingLmr`, both on since 2026-11-13) | the pruning eval above the same side's two plies up | **A definition:** compared on `prune_eval`, the TT-refined static estimate that RFP uses (R17: rising RFP compared raw evals; since the minor drift table's adoption the estimate includes its term), with the same side's node two plies up, or four plies up when that node was in check; not improving in check or when neither is known (near the root). **Screens (2026-11-11; Stockfish def601c and sf_7 to sf_17, Ethereal 0e47e9b, Berserk d7e1f05, Weiss c735b8f):** the definition matches Stockfish sf_12 to sf_16 (near match sf_11); kept and credited in ORIGINALITY.md. |
| `LmpImprovingEighths` (B9, R17; switch `UseImprovingLmp`, on since 2026-11-13) | **1 eighth** (adopted 2026-11-13, the natural value) | Late move pruning's quiet allowance (`LmpQuietAllowance` + d) is scaled by (8 + 1) / 8 at an improving node and (8 − 1) / 8 at one that is not, in whole quiets (rounded down): 9 + d becomes 10 or 7 at d = 1, 12 becomes 13 or 10 at d = 4. **Reasoning:** R17's prediction is that the non-improving class's 1% cutoff index is at most 0.75 times the improving one; scaling both sides by one eighth gives a ratio of 7/9 ≈ 0.78, and keeps the mean allowance where the SPSA tuned it when the two classes are about equally common (mean-preserving, as R17 asks). One eighth is the smallest step that moves the allowance by a whole quiet at every LMP depth. Range 0-4 step 1 (0 is off). UNVERIFIED: R17's stats-bench histogram split was not run (the build list's shape is R-STC). **Screens (2026-11-11; Stockfish def601c and sf_7 to sf_17, Ethereal 0e47e9b, Berserk d7e1f05, Weiss c735b8f):** 9/8 and 7/8 match none. **Design R at STC passed and the LMP use was adopted 2026-11-13** (pre-approved by the owner's rule: a search item passing its design R SPRT is adopted): survey-b9-lmp-stc (STC 8+0.08, Hash 16, design R [0, 6], beta 0.20, cap 8, futility look after 2 stages, from stage 0): test sprt/b9-improving-lmp 3273148 (`UseImprovingLmp` on, `LmpImprovingEighths` 1; bench 9,874,402 / 7065feb1fafd4e5f) against off tier2/b9-improving 74e485a (phase-4 a95e269's engine with both uses built in, off; no ProbCut, E1, history skip, drift table, D8, D13, exemption or D17; bench 10,166,167 / d874b380155a2e8c), r8brft1 on both sides, **+6.82 ± 4.37 Elo** (nElo +11.87 ± 7.61), Ptnml [85, 890, 1907, 1019, 99], **H1** (LLR 3.53, bounds −1.56, 2.77) after stages 0-4, 8,000 games, no time losses (runs 43365482176 to 43373575905; 12:59 AM EST 2026-11-13; sprt-log). It joins the final retune's SPSA as a class (a) dimension (final-retune.md §3.1). Speed: bench/ab_search.py (clang-release, Windows, 12 interleaved rounds, not pinned, identity checked on all 24 runs), A = 254841c, B = the port: median nps -2.1%, best -1.7%, under the 3.0% noise threshold, so no significant difference. The switch stays until the Phase 4 re-validation. |
| `LmrNotImprovingPlies` (B9, R17; switch `UseImprovingLmr`, on since 2026-11-13) | **1 ply** (adopted 2026-11-13, the natural value) | At a node that is not improving (never in check), late quiets are reduced this much more, inside LMR's clamp. **Reasoning:** the smallest unit of Fork's whole-ply LMR (as `CutNodeLmrPlies`): a node whose eval is falling is less likely to need a late quiet, so it can bear the next unit. Range 0-3 step 1 (0 is off). In the parameter table since the LMP use's adoption (2026-11-13). **Design R at STC passed and the LMR use was adopted 2026-11-13** (pre-approved by the owner's rule: a search item passing its design R SPRT is adopted; night item 53d, after the LMP use, R17's order): survey-b9-lmr-stc (STC 8+0.08, Hash 16, design R [0, 6], beta 0.20, cap 8, futility look after 2 stages, from stage 0): test sprt/b9-improving-lmr d3b3930 (`UseImprovingLmr` on, `LmrNotImprovingPlies` 1, the LMP use off; bench 7,186,034 / debc7162447eb810) against off tier2/b9-improving 74e485a (phase-4 a95e269's engine with both uses built in, off; no ProbCut, E1, history skip, drift table, D8, D13, exemption or D17; bench 10,166,167 / d874b380155a2e8c), r8brft1 on both sides, **+12.71 ± 7.00 Elo** (nElo +21.88 ± 12.04), Ptnml [35, 336, 750, 435, 44], **H1** (LLR 3.00, bounds −1.56, 2.77) after stages 0-1, 3,200 games, no time losses (runs 43375821546 and 43377962512; 1:38 AM EST 2026-11-13; sprt-log). Tested with the LMP use off on both sides and adopted on top of it (one at a time); the stacking check that follows covers the interaction. It joins the final retune's SPSA as a class (a) dimension (final-retune.md §3.1). Speed: bench/ab_search.py (clang-release, Windows, 12 interleaved rounds, not pinned, identity checked on all 24 runs), A = 17717a8, B = the port: median nps +0.5%, best +0.3%, under the 3.0% noise threshold, so no significant difference. The switch stays until the Phase 4 re-validation. **Screens (2026-11-11; Stockfish def601c and sf_7 to sf_17, Ethereal 0e47e9b, Berserk d7e1f05, Weiss c735b8f):** one more ply when not improving matches Ethereal and Berserk, near matches Weiss and Stockfish sf_11 to sf_16: the smallest unit, kept and credited in ORIGINALITY.md (owner's rule, 2026-11-11). |
| `LmrHistoryPerPly` (think tank R20, round-once LMR with a centred history term; the engine survey's C10 in its centred form; switch `UseCentredLmrHistory`, on since 2026-11-13) | **10,000 history units per ply** (adopted 2026-11-13, the natural value) | With the switch on, a late quiet's reduction is summed in 64ths of a ply and rounded once, and its history term is −c / `LmrHistoryPerPly` plies, where c is the move's butterfly entry less its running centre plus its reply and follow entries less theirs, weighted as the move ordering weights them (`ReplyWeight` / 4, `FollowWeight` / 4). **Reasoning:** one ply per `HistoryMax` (10,000) of centred, ordering-weighted history: a move whose tables sit a full table's range above their usual level is searched a ply deeper, the smallest whole unit of the old reduction; X2's in-game magnitudes (DESIGN §5.7, 95th percentile of the butterfly entry at LMR sites 1,875 to 5,625 through a game) put the term within about half a ply at most sites, a nudge rather than a second reduction. The failed term (sprt/lmr-history, −10.81 Elo) divided the summed score by 24,000 with integer division, so it acted at under 0.2% of sites and almost only to reduce less (X2); this one acts at every site, both ways, with mean about zero. **Retry value** 5,000 (two plies per range), only if the first SPRT is not H1: X2 found the in-game magnitudes small, so the natural scale may be too faint to matter. Decided by design R at STC, then LTC (a depth change), against off (ledger idea `r20-centred-lmr`): **both passed** (STC +8.04 ± 4.04 Elo, 9,600 games; LTC 40+0.4 +6.21 ± 4.35 Elo, 6,656 games; sprt-log), so 5,000 was not tried. **Constant screen** (2026-11-13): a near match to Stockfish's current master in effective ratio only, credited (natural value; ORIGINALITY.md). With B9's not-improving plies (adopted after R20's base) the whole-ply terms enter the 64ths sum as whole multiples of 64, so B9 moves the rounded reduction by exactly its ply. Range 5,000-20,000, step 750; a class (a) dimension of the final retune. |
| `HistoryCentre::Shift` (R20's running centres) | 10 (an average over about 1,024 LMR sites) | **Reasoning:** the term is centred on the population of LMR sites (think tank R20: "centre the history term on the LMR-candidate population ... so the mean reduction over LMR sites is unchanged"), and X2 shows that population drifting through a game (the butterfly's 95th percentile at LMR sites rises 2-3x from moves 1-15 to 61+), so a fixed centre measured once would be wrong for most of a game. An exponential average over 2^10 sites spans several nodes' late quiets (one node has up to a few dozen), so one node's moves move it little, and follows the drift within a few thousand sites, a small part of one search. Cleared with the histories (ucinewgame, each bench position). Not tuned (structural). |
| LMR's sub-ply unit (R20; `LmrFineUnit`) | 64ths of a ply | **A definition, not a tuned constant**, idea 43's unit (`OnePly = 64`): a power of two, so the one rounding is a shift. Each 64ths entry is the whole-ply entry times 64 plus the fixed-point value's own fraction kept within [−32, 31], so rounding once gives the whole-ply table back for any whole number of plies added (every entry tested): with no sub-ply term the search is unchanged. |
| `LinearBonusPerPly` (think tank R15, the engine survey's D11, the linear history bonus; switch `UseLinearBonus`, on since 2026-11-13) | **125 per ply** (adopted 2026-11-13, the natural value) | With the switch on, a cutoff's history bonus (and malus) is `LinearBonusPerPly` × depth, capped at `HistoryBonusCap` (1,250), instead of `HistoryBonusFactor` / 2 × depth² (`linear_bonus_for_depth`, `Searcher::cutoff_bonus`). **Reasoning:** the same cap reached at the same depth as the quadratic bonus (1,250 at depth 10, `HistoryBonusCap` / 10), so the two shapes differ only in how they weight shallow against deep cutoffs (depth 2: 250 against 50; depth 5: 625 against 312): the test is of the shape, not of the scale. **Retry value** 250 (the cap reached at depth 5), only if the first SPRT was not H1: not needed. **The natural value, no head-to-head** (owner, 2026-11-11 7:45 PM EST). The amount feeds every table `record_cutoff` updates (take, butterfly, and the pair tables through D8's summed update); R20's running centres read the tables it fills. With the switch on `HistoryBonusFactor` is unused. **Screen (2026-11-11; Stockfish def601c and sf_8 to sf_17.1, Ethereal 0e47e9b, Berserk d7e1f05, Weiss c735b8f):** min(125·d, 1,250) and min(250·d, 1,250) no match; the slope 125 is a near match to Stockfish and 250 to Weiss, kept and credited in ORIGINALITY.md (natural values). **Design R at STC passed and D11 was adopted 2026-11-13** (pre-approved by the owner, 2026-11-11: one SPRT at the natural value): d11-linear-bonus-stc (STC 8+0.08, Hash 16, design R [0, 6], beta 0.20, cap 8, futility look after 2 stages, from stage 0): **+8.98 ± 5.70 Elo** (nElo +15.50 ± 9.83), Ptnml [52, 527, 1129, 629, 63], **H1** (LLR 2.98, bounds −1.56, 2.77) after stages 0-2, 4,800 games, no time losses (runs 43445560313, 43448609701, 43451798490; 10:40 AM EST 2026-11-13); sprt-log. Range 63-250, step 9; a class (a) dimension of the final retune (final-retune.md §3.1). |
| Singular test depth | d / 2 | Fork's form, measured with it: the test only has to show that no other move comes near the TT score, so half the remaining depth (rounded down) is enough, as for the null move's question; the measurement above used exactly this depth. |
| Singular extension | 1 ply | The minimal unit, not a tuned constant (as `LmrCheckRelief`): Fork's depths are whole plies. With SE on the bench's nodes at fixed depth rise from 15,249,025 to 19,910,368, and 22.0% of the singular tests find the TT move singular (FORK_SEARCH_STATS). |
| Multi-cut (tier 2, T28) | returns the bar when the bar ≥ beta | **A definition, not a tuned constant:** the withheld-move search reaching a bar at or above beta shows a second move that beats beta, so the node is taken to fail high, with the bar as the proven lower bound (a half-depth score above it is not trusted further). Non-PV nodes only (a PV node needs an exact score) and never with a mate or tablebase bar (KB §3.21's pitfall, Halogen #637). On the bench with SE on it ends 11,700 of 48,568 tests (24%; FORK_SEARCH_STATS). |
| Negative extension (tier 2, T30) | −1 ply | **The minimal unit**, as the singular extension's +1: when the test finds other moves reaching the bar and the entry's score is already at or above beta, the TT move is searched one ply shallower. Non-PV nodes only, Fork's choice (KB: the gating is decided by experiment; its SPRT decides). With SE and multi-cut on, 9,326 such moves on the bench, whose nodes at fixed depth fall from 19,841,861 to 14,233,520. |
| `LmpMaxDepth` | 4 | The cutoff-index measurement (next row) has the same shape to depth 6, but from depth 5 on LMR already reduces late quiets by 2 plies or more (`reduction_for(5, 13)` = 2), so LMP adds little there. |
| `LmpQuietAllowance` | 8 (count 8 + d; was 12) | **SPSA-tuned and adopted (owner, 2026-11-09; r14-spsa: spsa-r14-m2, 13 iterations, 10,400 pairs at 8+0.08, then STC design R +37.93 ± 10.03 Elo, H1; the set adopted as a whole, an owner exception to the LTC rule; docs/history/phase-4/sprt-log.md):** 12 -> 8 (pinned at the SPSA floor 6 + c). **Measured** on the bench (LMP off, FORK_SEARCH_STATS histogram of the cutting quiet's index): fewer than 1% of quiet cutoffs come after the 13th, 13th, 14th and 11th quiet at depths 1-4. 12 + d keeps that 1% bound at depths 1-3 and prunes later at depth 4, where a missed cutoff costs a bigger subtree. |
| `FutilityMaxDepth` | 6 | As for RFP: at depth 6 the margin is 520 cp, past which a static eval says little. |
| `FutilityOffset`, `FutilityGrowth` | 86 + 50·d cp (was 100 + 70·d) | **SPSA-tuned and adopted (owner, 2026-11-09; r14-spsa: spsa-r14-m2, 13 iterations, 10,400 pairs at 8+0.08, then STC design R +37.93 ± 10.03 Elo, H1; the set adopted as a whole, an owner exception to the LTC rule; docs/history/phase-4/sprt-log.md):** 100 -> 86 and 70 -> 50. A quiet move rarely gains a pawn of static eval by itself (the offset), and each further ply allows 70 cp more swing, a little less than RFP's 80 because a futile node is already below alpha (reasoning). |
| `SeePruneMaxDepth` | 6 | The same horizon as the other shallow-depth pruning. |
| `QuietSeeFloor` | 60 cp per ply | A quiet move may hang a pawn's worth by depth 2 and a minor piece by depth 5: deeper searches can justify bigger sacrifices. |
| `CaptureSeeFloor` | 118 cp per ply (was 100) | **SPSA-tuned and adopted (owner, 2026-11-09; r14-spsa: spsa-r14-m2, 13 iterations, 10,400 pairs at 8+0.08, then STC design R +37.93 ± 10.03 Elo, H1; the set adopted as a whole, an owner exception to the LTC rule; docs/history/phase-4/sprt-log.md):** 100 -> 118. Captures that lose material are more often tactical (they open lines), so they get a pawn per ply. |
| `HistoryMax` | 10000 | The scale is free (ordering compares values within one table); 10000 is a round value well inside int16, so up to three tables summed in tier 2 (T10, T11) still fit in an int16 range. |
| `HistoryBonusCap` | HistoryMax / 8 = 1250 | No single cutoff moves a value by more than an eighth of the range, so about eight agreeing cutoffs are needed to approach the limit. |
| History bonus | 12.5·d², capped | Grows with depth because deeper cutoffs refute bigger subtrees; quadratic so the rarer deep cutoffs outweigh the many shallow ones; reaches the cap at depth 10. **Since 2026-11-13 the search uses the linear bonus** (D11, `LinearBonusPerPly` × d with the same cap; its row above) while `UseLinearBonus` is on; this form and `HistoryBonusFactor` act only with it off. |
| `ReplyWeight` (tier 2, T10) | 6 (quarters: the reply table weighs 1.5 times the butterfly history in a quiet's score) | **Measured** on the bench (2026-10-31, FORK_SEARCH_STATS, S-512): the mean index of the cutting quiet among the quiets searched, over the quiet cutoffs at depths 1-6 (non-PV, out of check), lower being better ordering, with the rule fixed before the runs (the lowest mean; ties to the smaller tree): table off 0.6500, weight 1 0.6554, 2 0.6380, 4 0.6217, **6 0.6142**, 8 0.6293 (each 586,000 to 638,000 quiet cutoffs). Scores stay within int16: 10,000 + 1.5 · 10,000. |
| `FollowWeight` (tier 2, T10) | 4 (quarters: the follow table weighs as much as the butterfly history) | **Measured** like `ReplyWeight`, in a separate worktree, with the reply table on at 6 (the follow table is tested on top of it): mean index of the cutting quiet, follow table off 0.6142, weight 1 0.6101, 2 0.6084, **4 0.5786**, 6 0.5841, 8 0.5980 (581,000 to 665,000 quiet cutoffs each). With both tables a quiet's score can pass int16 at the extremes (10,000 + 1.5 · 10,000 + 10,000), so the sum is clamped to the int16 range. |
| Pair-history slots | piece (colour and type) × destination, 768 | Fork's index for both moves of a pair (KB §3.10: a move is identified by its piece and destination); the table, 768 × 768 int16, is about 1.2 MB per searcher. The reply table takes the butterfly history's bonus and malus and its bounds (the same update), and is not read for evasions, whose captures must stay above every quiet (`EvasionCaptureBase`). A node reached by a null move, and the root, have no arrival: no read, no update (KB: Fork's choice between a neutral slot and none). The follow table (2-ply) reads the arrival of the ply above, the side's own previous move. Both tables live in one array, so the move selector holds one pointer and two int16 arrivals and the search stack's frame stays at 2,688 bytes, within its guard. |
| `TakeWeight` (tier 2, T11) | 4 (32nds: a take history entry at its limit adds 1,250 to a capture's score, whose victim counts 8 per centipawn) | **Measured** on the bench (2026-10-31, FORK_SEARCH_STATS, S-512, in a separate worktree), with the rule fixed before the runs (the lowest mean cutoff index over all cutoffs; ties to the smaller tree): take history off (MVV-LVA) 0.3499, weight 1 0.3430, 2 0.3407, **4 0.3331**, 8 0.3350, 16 0.3416. At 4, two entries at opposite limits differ by 2,500, so the history can reorder captures whose victims are less than about 3.1 pawns apart (a pawn is 800 here): a pawn capture can come before a minor-piece capture, never before a rook capture (tests/test_ordering.cpp). This row first said 1.6 pawns, counting one side of the history's range only; the tier-2 review of 2026-10-31 showed it with a failing test. Whether that reach is too far for KB §3.11's pitfall (history overriding real material) is what the SPRT measures. The table (moving piece and colour × destination × captured type, 4,608 int16) takes the history bonus on a capture cutoff and the malus for every capture tried before any cutoff; evasions keep MVV-LVA (`EvasionCaptureBase`). Its pointer grows the search stack's frame to 2,696 bytes, a recorded decision in the size guard (tests/test_search.cpp). |
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
| `ScoreTrendLimit` (score-trend clamp) | ±1000 cp | The LMR context's root score trend is clamped to ten pawns: beyond that a change only says "decisive", and the clamp keeps any rule's integer arithmetic far from overflow (deliverable 8c). |
| `TimeScaleMinDepth` (switches `UseStabilityTime`, `UseShareTime`, both on since 2026-11-08: variant b) | 8 | §5.6 step 10 (R8), a **placeholder from Fork's own fit** (X6, §5.7 on measure/step1: 18,782 iterations at depth >= 8 of 2,086 searches at 2M nodes in 60 of Fork's STC games; derived by tools/measure/tm_curve.py there). X6's declared primary depth: the fit has no rows below it, so the soft limit is not scaled there. The constant screen passed (ORIGINALITY.md, 2026-11-07). The rows below are adopted as one set with variant (b), whose SPRTs against off passed at STC (+18.69 ± 7.18 Elo) and LTC (+10.23 ± 5.14 Elo; 2026-11-08, SPRT log); no value was tuned on its own. |
| `TimeScaleMaxDepth` | 19 | Placeholder, X6: the last depth holding at least 1% of the fit's rows (290 of 18,782; depth 20 has 171). Deeper iterations are scaled as depth 19. |
| `TimeScaleStabilityCap` | 72 iterations | Placeholder, **derived by the owner's rule declared before it was computed** (2026-11-07): the 99th percentile of the stability count (iterations the best move stayed unchanged, X6's definition) over X6's 18,782 rows at depth >= 8, the smallest integer whose cumulative share reaches 99% (tm_curve.py prints it). It replaced X6's first cap of 10, which the constant screen found equal in role to other engines' stability caps and which had no data-based justification. Above about 15 iterations the floor binds anyway, so the cap mainly shapes the fit and keeps the fixed point in range. |
| `TimeScaleShareMin`, `TimeScaleShareMax` | 5, 995 per mille | Placeholder, X6's declared share clip (keeps the logit finite). |
| `StabilityFit` (variant a) | logit 0.534912 − 0.207666·stability − 0.096556·depth (Q16 35056, −13610, −6328) | Placeholder, X6 rows: logistic fit of "the best move changes within the next two iterations" on stability (capped at 72) and depth (AUC 0.765, out of sample 0.763). |
| `ShareFit` (variant b) | logit 0.474586 − 0.177596·stability − 0.185073·logit(share_all) − 0.103338·depth (Q16 31102, −11639, −12129, −6772) | Placeholder, X6 rows, the same label on stability (capped at 72), the every-pass share's logit and depth (AUC 0.771, out of sample 0.770; the last-pass share predicts less, §5.7). |
| `DepthFit` (normaliser) | logit 0.567490 − 0.211730·depth (Q16 37191, −13876) | Placeholder, X6 rows, the same label on depth alone. The scale is σ(fit)/σ(DepthFit): the iteration's change chance over the typical one at its depth. Depth normalises and is no signal of its own (owner, 2026-11-07): with the literal fits on stability (and share) alone, the balance needed to keep the mean spend drifts from 1.04 to 1.58 (a) and 1.01 to 1.46 (b) between 100k and 500k-node soft budgets, so an STC calibration would spend less at LTC; normalised, it stays at 0.99-1.08 (a) and 0.95-1.04 (b). Fallback (literal fits, kept documented; stability capped at 72): (a) σ(−0.455439 − 0.224471·s) / 0.1294, balance 1.216; (b) σ(−0.569350 − 0.199212·s − 0.173797·L) / 0.1294, balance 1.167 (both at 250k nodes; tm_curve.py prints all three budgets). |
| `TimeScaleBalanceStability`, `TimeScaleBalanceShare` | 1030, 996 per mille | Placeholders: the factor that keeps the mean spend equal to the plain soft limit's when X6's 2,086 searches are replayed with nodes as the clock (soft budget B, hard 4B, the engine's stop rules: the hard stop, the soft check, the forced-move stop, the iteration rule), the scale as the engine applies it (stability and depth caps, floor), the mean of the balances at B = 100k, 250k and 500k nodes (a: 1.018, 0.988, 1.083; b: 0.996, 0.954, 1.038). At equal mean spend the move at the stop matched the 2M-node final move more often (250k: 0.854 plain, 0.873 a, 0.874 b; in sample, not Elo). Nodes as time is UNVERIFIED: the head-to-head's clocks confirm the spend. |
| `TimeScaleFloor` | 360 per mille | Placeholder: at most two iterations short of the soft limit at Fork's iteration growth 5/3 (row "Iteration growth"): (3/5)² = 0.36. It binds at about a quarter of X6's rows (23% in a, 24% in b: the long-stable ones), and the balance is computed with it. No upper bound: the hard limit caps the scaled soft limit, and the iteration rule already ends an extended search near 2.4 soft limits. |

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

### 5.3 Phase 4 spec, step 0: the baseline network and the pipeline (approved by the owner 2026-10-28)

**Goal.** One simple, proven network shape carried through the whole
pipeline end to end, so every later architecture (steps 1-4 of the
multi-agent plan) plugs into machinery that already works and is already
tested: self-play data generation, upload, training on Kaggle with
bullet, Fork's own inference (scalar and SIMD), the trainer-engine parity
test, and the SPRT that decides. **Step 0 settles the pipeline, not the
architecture**: the baseline only has to beat the bootstrap evaluation
and to exercise every stage. Its second job is to start the data: the
first generation is labelled by the bootstrap evaluation's search and
can start as soon as deliverables 1-2 exist, before any network does.

**Out of scope for step 0.** King buckets, mirroring, output buckets,
threat inputs, deeper bodies, SCReLU and other activations, int8 hidden
layers, refresh caches (all candidates for steps 2-4); the search
re-validation and margin retune (after the first strong network, §5.2
Quality control 6); tier 2 (built and SPRTed beside this on the GitHub
shards, on bootstrap builds until the baseline network is adopted, then
rebased onto it); multithreaded search (Phase 6).

**Sources.** Concepts only, from the KB on branch kb: techniques.md §4-5,
research.md §6, tools.md §7-8, training-data.md, data-policy.md, and the
step 1 files `nnue-design.md` and `phase4-pipeline.md` (2026-10-28). No
engine's source code is opened by the implementing session or any
helper; bullet (MIT, a tool, KB tag USE) is read for its documented
interfaces and file layouts only, and Fork's training configuration is
Fork's own code. New references go into ORIGINALITY.md when first used.

**Build status (2026-10-28, branch `phase-4`).**
- Deliverable 0: Kaggle session 1 done (results under deliverable 0);
  K16 verified (owner, 2026-10-29); session 2 runs through the Kaggle CLI.
- Deliverable 1: done (32a2298, 1561c13); 591,871 openings from 2016-09;
  2026-09 streaming for generation 1.
- Deliverable 2: done (4e81783 and later); generation 0 running in WSL
  (10 workers, 20,000 nodes, target 200 M positions).
- Deliverable 3: sealing done (cb97e9b); upload and confirmation after
  session 2's CLI checks.
- Deliverable 4: training program done and checked on the CPU (5644fcf):
  bullet-trainer only, no bullet_lib (owner, 2026-10-28; KB
  bullet-internals.md §12-13); viriformat's own reader decodes Fork's
  shards exactly as python-chess replays them (45,626 positions), and its
  "tactical" filter is "a capture or promotion was played" (measured).
  Training needs CUDA (session 2).
- Deliverables 5-6: inference library, kernels, presets, net file,
  converter, reference and `fork netcheck` done (e2a5fa3); against files
  bullet itself wrote, the quantization leg and netcheck pass exactly.
  Still to do: the search integration (FORK_EVALUATOR=nnue, FeatureStack
  hooks in the Searcher), embedding the net, the gate in `tools/sprt.sh`,
  `build_pair.sh`, `elo_gauntlet.sh` and `fork_datagen`, and T from bullet
  on a GPU.
- Deliverable 7 (2026-10-29): B0 trained on the generation-0 snapshot
  g0s1 (9.5 M positions), passed the full parity test (trainer leg 0.00012
  cp, quantization leg exact, netcheck exact on 446 positions; loss max
  11.1 / p99 8.8 cp) and its SPRT against the bootstrap evaluation (+486.85
  +/- 32.07 Elo, H1 at [0, 5]; docs/nets.md, history/phase-4/sprt-log.md).
  **B0 is the default evaluator since 2026-10-29** (owner). With B0 the
  search suite's TT-at-exact-depth = minimax tests failed on a KRK
  position at depth 6 (554 vs 558; without the TT they agreed): graph-
  history interaction (verified: with repetition draws off in both the
  search and the reference, they pass), so the TT reuses a score a
  repetition draw shaped on another path; the bootstrap evaluation never
  hit it there. The hookup was verified exact (the refresh check on at
  every evaluation). By the owner's decision the tests were fixed, not the
  engine: the exact TT tests run where a full-width walk finds no
  repetition in reach (depth 3), a separate case documents the KRK case as
  tolerated, and checks tied to the bootstrap evaluation (score near
  material, the UCI mate-in-2 report) are bootstrap-only. The checks now
  follow the default evaluator (check.sh, build.sh, the PGO script and
  CI's bench parity pick bench-<net>.ref for a network).
- Deliverable 7, first retrain (B0r1, 2026-10-29): warm-started from B0 on
  the snapshot g0s2 (82.9 M positions; data/manifests/g0s2.json), same
  architecture and settings; the warm start reproduced B0's validation
  loss exactly before training (0.02482651); best superbatch 19 of 27,
  validation loss 0.02298 (B0: 0.02483). Parity: trainer leg 0.00012 cp,
  quantization leg exact, netcheck exact on 446; loss max 8.6 / p99 7.9 cp.
  SPRT against B0: +200.24 +/- 16.05 Elo, H1 at [0, 5] after 1,600 games.
  It is the default network (nets/b0r1.fnet, tests/bench-b0r1.ref:
  15,453,694 nodes) and the network for generation 1. Three search tests
  were fixed for it, as was done for B0:
  - determinism clears the history as well as the TT (the history persists
    between searches by design);
  - the fail-high stop test scans every bench position until three
    qualifying stops;
  - in the exchange test, a network may play any move that keeps the
    Syzygy result (owner), checked on K+R+P v K+R, where 4 of the 16 moves
    keep the win (fault-injected).

  B0r1's Rb2 in the two-rook position keeps the win, like every legal
  move there, so it is not recorded as a weakness (docs/nets.md).
- Names as built (four throwaway-clone screens, 2026-10-28, all no match
  or generic): the third screen's three case-insensitive matches were
  renamed before commit (`refresh_accumulator` -> `accumulate_board`,
  `apply_delta` -> `advance_accumulator`, `Columns` -> `DeltaColumns`).

#### Training-data decisions (copied from KB data-policy.md, "Owner decisions", 2026-10-24)

Copied as the Phase 4 outline requires; the KB keeps the evidence
(training-data.md) and the per-source statuses (data-policy.md).

1. **Strategy A+.** Labels come from Fork's own self-play only. Datagen
   openings are Lichess CC0 game positions, with `[%eval]` comments
   stripped and BOT games dropped. Positions with 7 pieces or fewer are
   labelled and adjudicated with Syzygy WDL (3-4-5 locally, so 5 pieces
   or fewer in practice). Fork rescores old data with newer Fork nets.
   No Lc0 data. **ChessTB tablebase results (owner, 2026-11-09)** are
   allowed beside Syzygy as exact retrograde labels (CC0 1.0 data; KB
   chesstb.md): WDL (and DTZ, read by ChessTB's own convention) for
   positions of up to 7 pieces and 8-piece positions with one opposing
   pawn pair, never in the engine; labels only (no engine evaluation or
   move from any source comes with them; the score field derives from the
   WDL class alone); provenance recorded per file (mirror, form, size,
   Xet hash, a local SHA-256, the prober at its pinned commit) in the
   slice manifest and ORIGINALITY.md; verified before use (agreement with
   Syzygy where both exist, spot checks at 6-7 pieces); downloaded only,
   never committed, deleted after the slice is sealed; the online
   explorer for spot checks only, within its limits, never for labelling.
   **Games against other engines are not Fork-pure data (owner,
   2026-11-10):** in a game against another engine (for example
   Stockfish), half the moves and the result come from the opponent, so
   such positions and results are never part of Fork's training data; at
   most a separate, labelled lineage, never mixed in silently, and only by
   an owner decision. (Ethereal's adversarial data, kb survey 2026-11, is
   the example.)
2. **Compute split.** Datagen on the owner's CPU (12 threads); training
   on Kaggle (free CUDA) first, rented CUDA only if Kaggle falls short.
   Colab is dropped (its FAQ bans chess training on free runtimes). The
   local Radeon RX 580 is not supported. **A dedicated netcup server is
   pinned as an option for later** (owner, 2026-11-06): recorded only;
   nothing is rented or running. AWS is unavailable (account suspended,
   2026-11-05).
3. **Disk and storage.** A compact data format (a few bytes per position)
   regardless of disk. Kaggle Datasets holds the only copy of the
   training data; local shards are deleted once the Kaggle hash check
   passes; each net and its data manifests go to GitHub Releases. Accepted
   risk: lost data means regeneration.
4. **Lichess puzzles**: a diagnostic report only; never a tuning target,
   an acceptance or SPRT gate, or a training input.
5. **Review gate for Lc0 data**: revisited (an owner decision on measured
   numbers, never an automatic switch) when two consecutive generations
   each gain less than about 10 Elo by SPRT against the previous one, or
   after 4 generations, or 2 billion own positions, whichever comes first.
6. **UHO_Lichess_4852_v1.epd**: test openings only, never training data,
   datagen openings, labelled positions or a tuning set; positions from
   test-match games are never kept for training.
7. **matetrack**: a diagnostic test input only, download-only, never
   training data or a tuning target.

Every net chains back to the bootstrap evaluation (KB originality.md §4):
generation 0 is labelled by the bootstrap evaluation's search, generation
n by net n-1's.

#### The baseline network, B0

| Part | Choice | Reasoning |
|---|---|---|
| Inputs | 768 piece-square features per perspective (2 colours × 6 piece types × 64 squares), seen from each side: the side's own pieces as "ours", the board flipped vertically for Black | The simplest input set that bullet's documentation starts from; no king dependence, so no refresh is ever needed after the root and the accumulator logic stays minimal while the pipeline is proven. |
| Body | one hidden layer of H = 256 per perspective; the two halves concatenated side to move first; one output | The smallest shape the KB lists as proven, and cheap at every stage: 256 int16 values are 512 bytes (8 cache lines) per perspective, a quiet move updates 2 × 2 columns, and training on generation-0 volumes takes little Kaggle time (measured in deliverable 4). Width is the first lever steps 2-4 pull, not step 0's. |
| Activation | clipped ReLU, clipped to [0, 1] in float, [0, QA] in integers | Exact and overflow-free in integers with plain int16/int32 arithmetic; squared variants need the overflow care the KB describes and belong to the designs. |
| Quantization | accumulator weights and biases int16, scaled by QA = 255; output weights int16, scaled by QB = 64; output bias int32, scaled by QA × QB | QA = 255 is the largest activation that fits an unsigned byte, which keeps an int8 path open for later designs. QB = 64 leaves output weights up to about ±511 in float before int16 overflows, far beyond trained values. Worst-case output sum: 2 × 256 × 255 × 32767 ≈ 4.3 × 10^9 would overflow int32 only at saturated weights; with |w| ≤ 2 in float (128 quantized) it is about 1.7 × 10^7, so the loader rejects any net whose quantized output weights exceed a bound that keeps the sum inside int32 (checked, not assumed). The int16 accumulator gets the same treatment: at most 32 features are active, so the loader also rejects a net where any hidden unit's |bias| plus 32 times its largest |feature weight| exceeds 32767. **Owner's decision (2026-10-28):** 255 and 64 are kept as bullet's standard quantization convention, a trainer-interface convention credited to bullet in ORIGINALITY.md, not a tuned constant; the constant screen does not apply to them. |
| Output scale | eval (cp) = output × S / (QA × QB), S fitted to Fork's own data | S maps the network's win-probability space to centipawns. It is **fitted, not chosen**: a logistic fit of game result against search score over generation-0 data (the Texel method's K fit, KB techniques.md §4), so a centipawn keeps roughly the meaning the search's margins were built on until their retune. |
| Clamp | the result clamped to ±(EvalLimit - 1) | `EvalLimit` (eval_scale.hpp) is the contract every evaluator keeps. |

Expected cost: per evaluation one 512-value dot product (16 AVX2 or 8
AVX-512 multiply-adds per perspective) plus incremental updates; the
measured nps goes into perf-log.md at deliverable 5 (not estimated here).

#### Deliverables in build order

Each deliverable is one or more commits with its tests. The full check
(the CI matrix) passes on each pushed milestone; bench changes only at
deliverable 7 (the evaluator switch), with tests/bench.ref in the same
commit. **The review stop**: this spec (with steps 1-3's results), then
the Kaggle test session's results (deliverable 0), then B0's SPRT
(deliverable 7). Nothing else stops unless something fails.

**0. Kaggle test session** (with the owner, who holds the account). One
real session, run from a private notebook, settles the facts the KB marks
UNVERIFIED before anything depends on them. Results go into the KB
(training-data.md §2.1) and the decisions log. Checklist, each with its
acceptable result:

| # | Check | How | Acceptable |
|---|---|---|---|
| K1 | Account can use GPUs and internet | Settings page; phone verification if asked | GPU T4 x2 selectable (P100 appears to be gone since September 2026, phase4-pipeline.md; UNVERIFIED for free accounts); internet toggle on |
| K2 | Internet inside a GPU session | `curl -sI https://static.rust-lang.org` in a GPU notebook | HTTP 200; otherwise the fallback below |
| K3 | CUDA toolkit and driver | `nvidia-smi`; the CUDA libraries bullet links (cuda, cudart, nvrtc, cublas) present and linkable; `nvcc` is not needed (bullet compiles its kernels at run time) | CUDA 12.4 or newer for driver and toolkit (phase4-pipeline.md's inference from bullet's driver calls; UNVERIFIED until this check). The version goes into every run record, since Kaggle's image follows Colab's runtime and its CUDA major version can change |
| K4 | Rust and bullet build | Rust is not preinstalled: rustup (bullet needs Rust 1.87 or newer), then `cargo build --release` of `tools/train` at the pinned bullet commit; time it | Builds in under 30 min. **Fallback**: build once, attach the binary as a private dataset, and check that it runs in a fresh session (glibc and CUDA match) |
| K5 | Toy training run | 1-2 superbatches of B0 on a 10 M-position sample dataset | Loss falls; positions per second recorded (sets deliverable 4's budget) |
| K6 | Checkpoint and resume | stop after N superbatches, save to `/kaggle/working`, resume in a **second** session that attaches the first's output as input, with the start superbatch set to the saved one plus one (bullet does not store it) | The weights and optimizer state loaded equal the saved ones (hash), and the loss continues from the saved level. Not a bit-identical continuation: bullet's data loader shuffles with a clock-seeded generator (phase4-pipeline.md), so training runs are not bit-reproducible, and the run record says so |
| K7 | Headless runs | `kaggle kernels push` of the notebook from WSL, `kaggle kernels status` polling, `kaggle kernels output` download | A full "Save & Run All" run completes without a browser open; outputs download |
| K8 | Datasets | `kaggle datasets create` of a 1-2 GB test shard from WSL; interrupt and re-run once; `kaggle datasets files` | Upload resumes; sizes match; mounted read-only at `/kaggle/input/...` |
| K9 | Mounted-data hash check | a CPU-only session hashes the mounted shard | SHA-256 equals the local manifest; CPU session uses no GPU quota |
| K10 | Read speed | time a full read of the mounted shard in a GPU session | Fast enough that data loading does not bound training (compared with K5's rate) |
| K11 | Scratch disk and limits | `df -h` in the session; largest single file uploaded | Recorded; the shard size (deliverable 2) is set below the limits found |
| K12 | Idle timeout and session length | note the interactive idle cutoff; commit runs are expected to ignore it | Recorded; training runs only as commit runs |
| K13 | Weekly quota | the quota display before and after | Recorded; deliverable 4's schedule fits the measured hours |
| K14 | Secrets | a Kaggle Secret read from the notebook (no token in the notebook text) | Works; nothing secret in any committed or uploaded file |
| K15 | The trainer's evaluation of fixed positions | bullet's own evaluation of FENs with the trained float model (its value trainer's eval call, GPU only; phase4-pipeline.md) on the parity positions | Prints a score per position, written to the run's outputs |
| K17 | Data loading on 4 CPU cores | time bullet's game-format loader alone against K5's training rate (a GPU session has only 4 CPU cores) | Loading keeps up; otherwise convert batches to bullet's fixed-size format (about 8 times larger) before training |
| K18 | Both T4s | one training run per GPU at once | Recorded; two bake-off candidates can then train side by side |
| K16 | Terms | re-read Kaggle's terms and AUP pages as of the session | Still personal, non-commercial ML use; datagen stays local |

**Session 1 results (2026-10-28)**, from `tools/train/kaggle/session_check.py`
run by the owner in a private GPU notebook (internet on); the JSON is
quoted in KB phase4-pipeline.md §8.1:

| Item | Result | Status |
|---|---|---|
| K1 GPUs | Two Tesla T4, 15,360 MiB each, driver 580.178.04. The accelerator menu offers "GPU T4 x2" and "TPU v5e-8" only (owner): no P100 for this account | verified |
| K2 internet | github.com answered 200; the rustup distribution root and crates.io answered HTTP 404, so both servers were reached (DNS, TLS and HTTP work from a GPU session). A real download (rustup, the crates index) is session 2's test | reachability verified; downloads open |
| K3 CUDA | Toolkit **12.8** (nvcc 12.8.93; cudart 12.8.90, NVRTC 12.8.93, cuBLAS 12.8.4.1 in `/usr/local/cuda/lib64`); the driver reports CUDA **13.0**. Both are above the 12.4 minimum inferred from bullet's code, and the driver is newer than NVRTC, as bullet needs (KB bullet-internals.md §8). `libcuda.so` is only in `/usr/local/nvidia/lib64` (on `LD_LIBRARY_PATH`, not in the loader cache); `CUDA_HOME=/usr/local/cuda`, `CUDA_PATH` unset | versions verified; that bullet builds and runs on them is K4/K5 (session 2) |
| K4 Rust | Not preinstalled (`rustc` absent). Plan: session 2 installs it with rustup and builds `tools/train` there (the image's glibc is 2.39); the binary is kept in `/kaggle/working` and attached as an input to later sessions, rebuilt when the image or CUDA version changes. If linking `cuda` fails, set `CUDA_PATH=/usr/local/cuda` and add `-L /usr/local/nvidia/lib64` to the linker flags | open |
| K11 disk | `/kaggle/working` 19.5 GB free (the documented 20 GB); `/tmp` and `/` 1,048.8 GB free (session scratch, lost at session end; how much of it is usable in practice: UNVERIFIED). Per-file upload limit: **none stated in the Datasets docs** (owner: only 200 GB per dataset, 200 GB of private datasets in total, at most 50 top-level files; archives are unpacked); confirmed by a real 1-2 GB shard upload in session 2 (K8) | partly verified |
| K12 idle timeout | No idle-timeout warning during session 1 (owner); a short interactive session, so the cutoff itself is still unmeasured; training runs are commit runs anyway | noted |
| K13 quota | Weekly GPU hours before and after were not noted (owner) | open: note them in session 2 |
| K16 terms | The current Terms and AUP (effective 2025-06-22, no newer version) still say personal, non-commercial use; no clause covers chess, self-play or publishing a model trained on Kaggle; outputs stay the user's; one account only; automation through the API is allowed (KB training-data.md §2.1, "Kaggle terms re-checked", 2026-10-28). The owner's earlier "no" was a mistake (owner, 2026-10-29) | **verified** |
| K17 cores | 4 CPUs, 31.3 GB RAM; Linux 6.18.55, glibc 2.39, Python 3.13.15 | verified |

**Session 2 (2026-10-29)**, run headless with the Kaggle CLI (kernel
`fork-session-2`, version 2; dataset `fork-s2-test`: two generation-0
shard snapshots of 637,006 and 643,039 positions):
- **K2, K4**: rustup installed Rust 1.99.1 in 13 s; `tools/train` at
  7c84ae7 built with `--locked --features cuda` in 36 s (CUDA_PATH set,
  `-L /usr/local/nvidia/lib64`); `check` wrote 394,816 bytes.
- **K5**: B0 trains at 1,236,220-1,302,414 positions per second on one T4
  (512 batches of 16,384 per superbatch, 6.4-6.8 s each).
- **K6**: resume from a checkpoint (start superbatch 3) works; the loss
  continues.
- **K15**: the trainer's own evaluation of the 46 test positions works.
- **K17**: one thread decodes and filters 1,366,487 positions per second
  (433,777 kept of 637,006), just above the training rate.
- **K18**: both T4s train at once (one run each, 14 s per superbatch).
- **Validation and early stopping** work; on this tiny set the loss rose
  after superbatch 1 (0.0302, 0.0319, 0.0328: overfitting, as expected).
- Run 1 found one bug of Fork's: bullet's evaluator runs at batch size 1,
  so validation evaluates one position at a time (7c84ae7).
- Still open: K7's headless output download (`kernels output` also fetches
  the cloned repository: scripts now delete it), K8/K9 at shard scale (a
  1-2 GB upload and the CPU-session hash check), K10, K13.

The Kaggle API token lives in `~/.kaggle/kaggle.json` in WSL (mode 600)
and in Kaggle Secrets; it is never committed, logged or uploaded.

**1. Datagen openings** (`tools/datagen/`, Python in `.venv`, run with
`-I`). From one pinned Lichess CC0 monthly file (its published SHA-256
checked before use; first 2016-09, about 1.2 GB and 6.8 M games, after
Lichess's documented self-play and castling issues, per
phase4-pipeline.md; recent months are about 30 GB each),
streamed and never stored whole:
- keep rated standard games with both players rated at least a
  threshold, drop any game with a BOT title, ignore `[%eval]` and every
  other comment (only moves and headers are read);
- take the position after a random ply in a fixed range, then play a
  few uniformly random legal plies (seeded) for diversity;
- drop positions that are already decided (game over, or a short
  bootstrap search scores beyond a bound), and duplicates;
- write an EPD with a manifest (source file and its SHA-256, filters,
  seed, count, output SHA-256). The EPD is not committed (size); it is
  regenerable from the manifest, which is.

**The 2016-09 run** (2026-10-28, `datagen_openings.py` with the default
settings, seed 20261028; manifest `data/manifests/openings-lichess-2016-09.json`):
6,813,113 games read in 31 minutes; 6,216,013 below the rating floor,
597,100 with both players at 2000 or more (8.8%), no BOT titles (as
expected before the Bot API), 4,308 too short, 76 ending during the random
plies, 845 duplicates; **591,871 openings** (EPD SHA-256 0ae298e1...831b).

**Why 2016-09** (recorded at the owner's request, 2026-10-28; facts from
KB phase4-pipeline.md, which read Lichess's database page):
- It is the **first month after both of Lichess's known data issues that
  matter here**: before March 2016 some players played themselves in
  rated games (fake games, worthless as "human play"), and up to August
  2016 a few games contain illegal castling moves. Lichess's other listed
  issues (evaluation problems in December 2016 and July-August 2020;
  wrong results on 12 March 2021) do not affect openings, since Fork
  reads neither evaluations nor results here.
- It is **small**: 1.2 GB compressed and 6.8 M games, against about
  30 GB and about 90 M games for a 2026 month. The first run of the tool
  is then minutes of download and streaming, and a mistake costs little.
- **Is a larger or more recent month worth it?** Not for generation 0,
  probably yes later. Generation 0 (about 200 M positions, roughly a
  million games at the expected game lengths; *estimate*) needs about a
  million openings, and 2016-09 can supply that only if enough of its
  games have both players at 2000 or more. That count is UNVERIFIED and
  is the first number the tool reports; if it falls short, 2016-10 or
  2016-12 (1.35 and 1.7 GB, same clean window) come next. Later
  generations need tens of millions of games, and then a recent month
  adds what matters: about 13 times as many games, so many more distinct
  2000+ positions and today's opening repertoire rather than 2016's. It
  also filters bots better: the BOT title exists only since Lichess's Bot
  API, so engine accounts in 2016 months are not tagged (UNVERIFIED when
  the API began), while a recent month's bots are dropped by the title
  filter. The cost is a 30 GB download, streamed through `zstdcat`
  without storing the file. So the plan is: 2016-09 for generation 0; a
  recent month (or several old ones) added to the pool before generation
  1, with each month in the manifest. Whether the extra variety helps is
  measured, not assumed: the tool reports distinct positions after the
  filters and the spread over opening codes (the PGN `ECO` header), and
  the analyst (step 7) can test a net trained on the wider pool by SPRT.
Thresholds (rating, ply range, random plies, the decided bound) are in
the constants table below. Test: the tool reproduces its own output
byte for byte from the same manifest; a fixture PGN with a BOT game, an
`[%eval]` comment and a low-rated game shows each filtered.

**2. Self-play data generation** (`fork_datagen`, a separate CMake
target linking the engine library, never part of the TCEC binary).
- **Games**: N worker threads (default 10, leaving 2 for other work),
  each playing whole games one after another with its own `Searcher`
  and its own small transposition table, cleared before each game.
  Every move is a fixed node-count search (`go nodes`, exact since
  audit-1), so a game is a pure function of (commit, evaluator and net,
  opening, seed): any shard can be regenerated. Where the node limit runs
  out before depth 1 finishes (long capture chains), that move is searched
  to depth 1 without a node limit instead, so no label is ever a depth-0
  score. **Per-game random plies** (owner, 2026-10-28): each game first
  plays 2 to 4 uniformly random legal plies (the range already screened
  for the openings tool) from a stream seeded by (seed, game index), so an
  opening used more than once still starts different games: generation 0
  needs about 2.2 M games and 2016-09 gave 591,871 openings.
- **Game end**: the rules only (mate, stalemate, threefold, fifty-move,
  insufficient material), plus two exact adjudications: Syzygy WDL once
  5 pieces or fewer remain (both sides' probes through
  `endgame_tables.*`; Fathom's README states WDL probes are thread-safe
  unless built with `TB_NO_THREADS`, provided the tables are loaded once
  before the workers start and never freed while they run; the probe
  comes right after the capture that enters the tables, when the
  fifty-move clock is zero, phase4-pipeline.md; concurrent probing is
  tested, not assumed), and a search-reported
  mate score, which ends the game with that result. **No eval-based win
  or draw adjudication in generation 0**: the bootstrap evaluation is
  weak, so a score threshold would write wrong results into the labels;
  the time saved is measured later and revisited per generation.
  **Score adjudication (2026-10-30, off by default)**: `fork_datagen
  --adjudicate-cp CP --adjudicate-plies N` ends a game as a win once N
  recorded scores in a row are at least CP for the same side (a score
  inside the band or for the other side restarts the count; a mate score
  still ends the game first). It is adopted per labelling network only by
  measurement: the rule's misjudgment rate on that network's own data must
  be essentially zero, and an adopted rule starts a new part. The run
  manifest records both values (0 when off) and the `score_adjudicated`
  end count; `verify_games.py --adjudicate CP N` checks it independently.
  No draw adjudication: in the generation-1 study the settings that
  misjudged no game saved under 0.2% of positions.
- **Split search (ideas.md idea 13; 2026-10-30, off by default)**:
  `--save-percent P --unsaved-nodes N` saves each position not in check
  with probability P% (searched with `--nodes`) and searches the others
  with N nodes; `--check-nodes C` searches positions in check with C nodes
  (the trainer drops them anyway). A viriformat record cannot skip a ply,
  so an unsaved position keeps its move and records the score 32767
  (`UnsavedScore`, above every search score), which the trainer's existing
  |score| > 20000 filter drops; a mate score is always written, and the
  score adjudication skips unsaved positions. Save decisions come from a
  stream of their own per (seed, game), so with the split off the shards
  are byte-identical to before. The manifest records the three settings,
  `positions_unsaved` and `nodes_spent` (every search's nodes, for the
  compute comparison); `verify_games.py` checks the unsaved count against
  it. **Standing data-generation setting since 2026-10-31 (owner; idea
  13 adopted, +65.5 ± 12.9 Elo):** `--save-percent 50 --unsaved-nodes
  4000 --check-nodes 2000`, with the other settings unchanged (20,000
  nodes, the score adjudication at 700 cp for 8 plies). It starts a new
  part: locally g2d was stopped and sealed and g2e continues with it; in
  the cloud the running 12-hour instances finish with the old settings
  and every relaunch uses it (`tools/cloud/aws_spot_datagen.sh` and
  `cloud_datagen.sh` pass the three options through). Each part's
  manifest records the settings.
- **What is recorded**: every position, its search score from White's
  view (or the convention the format fixes), the move played, and the
  game result. Filtering (in check, best move a capture or promotion,
  mate or tablebase scores) happens at training time, not here, so the
  data stays complete for later rescoring and filter changes.
- **Format**: viriformat (MIT; a game-based compact format with one
  32-byte packed board per game, then a 16-bit move and a 16-bit score
  per position: about 4 bytes per position), written by Fork's own C++
  code from the format's README specification (phase4-pipeline.md
  pins it). It is the format bullet documents for self-generated data,
  and bullet's loader reads the game files directly and shuffles in
  memory, so no converter or shuffle step stands between datagen and
  training. Two traps from the research: piece nibbles are low nibble
  first (an older README example had them reversed), and bullet pins an
  older format version without the extension record, so Fork never
  writes extension records. The conventions the README leaves open (the
  en passant square, whether a score belongs to the position before its
  move; UNVERIFIED) are settled by a test, not by assumption: bullet's
  own loader, run on the CPU with its mock device, decodes a Fork shard,
  and every decoded position, score and result must equal python-chess's
  replay of the same games. A data format is
  an interface, like UCI, not engine code; recorded in ORIGINALITY.md.
- **Shards** of a fixed size (constants table) in a staging directory
  (`FORK_DATA_DIR`, outside the repository), each with a manifest line:
  SHA-256, games, positions, generator commit, evaluator and net hash,
  node limit, openings manifest hash, seed range, start and end time.
  Manifests are committed under `data/manifests/` (no paths beyond `~`,
  no personal data).
- **Labeller policy (standing; owner, 2026-10-30, extended 2026-11-05).**
  Data generation always uses the current default **engine**: the default
  network and every adopted search change (until 2026-11-05 the policy
  named only the network). Whenever a new network is promoted to the
  default (for example the bake-off's winner beating B0r2) or a search
  change is adopted into phase-4, the running generation is stopped at a
  game boundary, the part generated so far is sealed from its complete
  games as its own manifest, and the generation continues as a new part
  from a PGO build of the new default (bench-checked against its
  reference), with a new seed and the rest of the generation's target.
  **One naming scheme** (owner, 2026-10-30): a part ends for any reason
  (a new labelling network, a new default engine, new openings, or the
  target reached), and the next
  part takes the next letter (g2, g2b, g2c, ...). Every part's manifest
  records its labelling network (`"evaluator": "nnue (<net>)"`, which
  fork_datagen writes itself since 3978e91), its openings file, and why
  the part ended (`"part_end"`; `upload_batch.py seal` refuses to seal
  without it, or with a network run that does not name its net). Parts
  are never merged into one manifest, so training can always tell which
  network labelled which positions. Generation 1 is the first instance:
  g1 (B0r1, ended by B0r2's promotion) and g1b (B0r2).
- **Disk margin (standing; owner, 2026-11-06).** A part starts only when
  the disk has room for it: its remaining target at the measured bytes
  per recorded position (4.6, above g3d's measured 4.38), once on
  WSL's disk and twice on C: (WSL's virtual disk grows on C:, and the
  sealed complete-games copy goes there too), plus a 20 GB reserve on
  each. The Fork Control Center (`tools/control_center/`, the only
  place that starts or stops a part from a button) refuses a start below
  it; the values are `bytes_per_position` and `disk_reserve_gb` in its
  `config.py`. The same 20 GB is its low-disk warning.
- **Tests**: a reader for the format (C++, used by the tests, the
  rescoring tool later, and a new fuzz target `fuzz_selfplay_record`
  under the phase-end fuzz rule) round-trips every written game; every
  stored move is legal in its position when replayed by python-chess
  (an independent oracle, `tools/datagen/verify.py`); the stored result
  matches the game's end by the rules or the tablebase; two runs with
  the same seed give byte-identical shards; the `no_alloc` style check
  that a worker allocates nothing per move after warm-up.
- **Throughput** is measured (positions per second per thread), not
  estimated, and recorded in perf-log.md before the first long run.

**3. Upload and confirmation** (`tools/datagen/upload.sh`), following the
KB's storage design (training-data.md §2.2): one immutable private
Kaggle dataset per batch (never versioned), at most 50 shards as plain
files at the dataset's top level (the CLI skips subfolders by default,
phase4-pipeline.md; that caps a batch at about 50 GB), the kaggle CLI
re-run on interruption, with its resume state kept outside `/tmp`; then a CPU-only Kaggle
session hashes the mounted shards; only a full SHA-256 match against the
manifests deletes the local shards. It is network-bound and runs beside
datagen (not a second heavy job; checked not to disturb a benchmark).
Test: a dry-run mode against a fake CLI covers the mismatch and resume
paths.

**4. Training** (`tools/train/`): a Cargo project depending on bullet at a
pinned commit (Cargo.lock committed), with Fork's own training program
for B0, and a Kaggle notebook driver pushed with `kaggle kernels push`.
- Inputs: the batch datasets (mounted), the previous run's output (for
  resume). Outputs: the float checkpoint, bullet's quantized file, the
  training log, and the trainer's evaluation of the parity positions
  (deliverable 6) when bullet can produce it.
- Target: a blend of the search score (through the sigmoid with the
  fitted scale S) and the game result, weight λ on the score; loss and
  schedule as in the constants table. Position filters as in
  deliverable 2. In bullet's terms (KB bullet-internals.md §5): its WDL
  setting is the weight on the game result, so Fork passes 1 - λ; its
  eval scale is S; its optimizer defaults (AdamW, weight clip ±1.98) are
  recorded in the run record; and B0's training program saves the
  tensors in a fixed order (`l0b`, `l0w`, `l1b`, `l1w` in the float file)
  that the converter's description file names.
- Runs are commit runs of at most 12 hours that checkpoint and resume
  (K6), inside the measured weekly quota (K13).
- Every run writes a run record: bullet commit, Fork commit of
  `tools/train`, dataset names and their manifest hashes, settings,
  final loss, output hashes. The record goes into the net registry
  (deliverable 7) and the net's GitHub Release.

**5. Inference** (`src/eval/nnue/`; FORK_EVALUATOR gains `nnue`):
- **Fork's own net file format**: a header (magic, format version,
  architecture id, dimensions, QA, QB, S, the payload's SHA-256), then
  the tensors in the order and layout Fork's kernels read. A converter
  (`tools/nnue/convert.py`) turns bullet's quantized file into it, so
  Fork's format never depends on the trainer's layout; the parity test
  checks the converter end to end. bullet's quantized file has no
  header, names or shapes: the tensors follow the order the training
  program saves them, little-endian, column-major unless transposed,
  padded to a multiple of 64 bytes (phase4-pipeline.md). So the
  converter takes the tensor order and shapes from one description file
  shared with Fork's training program, never by guessing. bullet
  truncates when quantizing unless rounding is asked for, so Fork's
  training program asks for rounding, and the parity bound assumes it. The loader validates everything
  (sizes, version, the output-weight bound of B0's table, the hash) and
  is a new parser, so it gets a fuzz target (`fuzz_net_file`).
- **Embedding**: the net Fork plays with is compiled in, from
  `nets/<sha-prefix>.fnet` in the repository (B0 is about 400 KB),
  checked against its SHA-256 at configure time, so TCEC's build from a
  clean clone needs nothing else. Larger nets later move to a GitHub
  Release fetched by CMake with a pinned SHA-256 (the clean-clone rule
  allows both). No runtime net option in step 0.
- **Accumulator**: two int16 vectors per position (one per perspective),
  kept in a per-ply stack owned by the `Searcher` beside the `PlyFrame`
  array, not in `Position` (audit-1 F-21: perft and movegen stay free
  of it). Updated incrementally from the parent's on make (added and
  removed features of the move, both perspectives; castling, en passant
  and promotion included); null move copies; unmake just pops. Lazy:
  computed when `static_eval` needs it, from the nearest computed
  ancestor. Root and new-game positions are computed from scratch.
  Debug builds check incremental against from-scratch at every
  evaluation.
- **Kernels**: scalar reference always compiled; AVX2 (x86-64-v3),
  AVX-512 (x86-64-v4) and AVX-512 VNNI where it helps (for B0, the
  int16 output dot product), selected at compile time (`.claude/rules/
  simd.md`). New presets: `{clang,gcc}-scalar` (baseline x86-64, no
  SIMD paths) and `{clang,gcc}-vnni` (x86-64-v4 plus VNNI; run under
  Intel SDE in CI on runners without it), each with bench parity.
  `update.sh`'s default target is revisited once SIMD code exists
  (decisions log, 2026-10-24).
- **Bootstrap evaluation stays** as `FORK_EVALUATOR=bootstrap`: it labels
  generation 0 and anchors the provenance chain. The default switches to
  `nnue` only after B0 passes deliverable 7.
- **Tests**: SIMD against scalar, bit-identical, randomized and edge
  inputs (saturation at 0 and QA, extreme weights, all-features-active
  positions); incremental against from-scratch along random game lines
  with null moves, castling, en passant, promotions and captures of
  every kind; colour-flip symmetry (a position and its mirror give the
  same score from the side to move's view, exactly); `no_alloc` over a
  search with the network; bench parity across every preset. Speed:
  `fork bench` nps before and after, recorded in perf-log.md.

**6. The trainer-engine parity test** (the owner's step 0 requirement).
- **Positions**: a committed EPD, `tests/nnue/parity.epd`, of a few
  hundred positions: hand-made edge cases (every one of the 768 features
  active somewhere in the set; promotion-heavy positions such as several
  queens per side; both kings in every region; positions in check;
  positions scoring at the clamp), the bench positions, and positions
  drawn with a fixed seed from Fork's own generation-0 data. Sources are
  cited in the file, as for every test input.
- **Three evaluators of the same positions**:
  1. **T, the trainer's model**: bullet's own forward pass with the float
     weights, run on Kaggle at the end of training (K15), written as
     `parity-trainer.txt` with the run's outputs.
  2. **R, Fork's independent reference** (`tools/nnue/reference.py`,
     numpy): written from this spec, not from Fork's C++ or from
     `convert.py`. It reads bullet's float weights file and computes the
     float forward pass (R-float); it **quantizes those float weights
     itself** (R-quant, exactly as bullet does at the pinned commit, KB
     bullet-internals.md §1: each f32 weight widened to f64 and multiplied
     by the factor in f64, rounded half away from zero, cast with
     saturation, and the whole file refused if any value leaves its type's
     range; never an f32 multiply, which disagrees with bullet on some
     weights, and never numpy's round-half-to-even); and it
     emulates Fork's integer arithmetic exactly on Fork's net file
     (R-int).
  3. **F, Fork's inference**: the scalar path and every SIMD path, through
     `static_eval` on each position set up from its FEN, and again after
     reaching each position incrementally from a parent.
- **What must match** (revised 2026-10-28 after the step 3 judge
  showed that the first draft's worst-case bound could never fail: for
  B0 it comes to the order of 1,000 cp, so a converter error smaller than
  that would pass; KB phase4-designs/judgement.md §6.6):
  - **Quantization leg, exact.** R-quant's integers equal bullet's
    quantized file and the tensors of Fork's net file, integer for
    integer. Three implementations (bullet's quantizer, `convert.py`,
    R-quant) check each other, so a layout, transposition, rounding or
    converter error fails here exactly, however small its effect on the
    score.
  - **F equals R-int exactly**: every path (scalar and every SIMD path),
    both routes (from the FEN and incrementally), every position.
  - **R-float equals T within floating-point noise**: |R-float - T| ≤
    0.01 cp (GPU summation order differs; revisited if K15's data show
    it is too tight, never loosened silently). This proves Fork's reading
    of the trainer's float model is right.
  - **The documented quantization tolerance**: the quantization loss
    |R-int - R-float| is computed exactly on every position (no bound).
    Its maximum and 99th percentile must stay under per-architecture
    thresholds, set at the architecture's first net from its measured
    loss, recorded in the net registry, and approved by the owner; they
    change only with the owner's approval. Since R-float equals T within
    0.01 cp, this bounds |R-int - T|, and so |F - T|, by the threshold
    plus 0.01 cp. For B0 the thresholds are proposed from its first
    trained net, with its numbers, at the deliverable 7 review, before
    any game.
  - **Feature leg** (for B0 a simple check; essential for every later
    design with king regions, mirroring, buckets or computed features):
    the active feature indices from Fork's C++ and from `reference.py`
    (python-chess for the board) are identical on the parity positions
    and on 1 M positions sampled from Fork's data; later designs add the
    trainer's own input code (a CPU-only test build) as a third party.
  - **The checker is shown able to fail**, each mutation tied to the leg
    that must catch it: a corrupted weight, a transposed tensor and a
    missing rounding step (quantization leg); a wrong perspective flip in
    the C++ (F = R-int or the feature leg); a too-coarse QB in a test
    copy (the loss threshold).
- **T needs a GPU**: bullet evaluates FENs with the float model on its
  GPU backend only, and has no evaluation of its quantized file
  (phase4-pipeline.md). So T is produced once per net on Kaggle and
  committed; CI and local runs compare against the committed T values
  and never run bullet. R-float reads bullet's self-describing float
  weights file (names, counts, f32 values) from the checkpoint.
- **Where it runs**: R-int against F as a ctest (`nnue_parity`) on every
  preset, so CI runs it on every push and pull request (scalar, v3, v4
  and VNNI under SDE, TCEC's four compilers); the Python legs (the
  quantization leg, R-float against T, the loss thresholds, the feature
  leg on the parity positions) as a CI job whenever `src/eval/**`,
  `nets/**`, `tests/nnue/**` or `tools/nnue/**` change; the 1 M-position
  feature leg nightly and on such changes. The expected values (T's,
  R-int's, the loss statistics and thresholds) are committed per net in
  `tests/nnue/<net>.parity`.
- **The game gate**: `fork netcheck FILE` (a hidden command, like
  `bench`) evaluates the parity positions and compares them with the
  committed R-int values, and refuses a net whose recorded loss exceeds
  its architecture's thresholds. `tools/sprt.sh`, the cloud shards'
  `build_pair.sh`, `tools/elo_gauntlet.sh` and `fork_datagen` run it on
  the exact binary before their first game and refuse to start on a
  mismatch, and refuse a net with no parity record at all.

**7. B0, generation 0 and the first SPRT.**
- Generation 0: `fork_datagen` with the bootstrap evaluation on the
  openings of deliverable 1, size in the constants table; uploaded and
  confirmed (deliverable 3).
- Fit S on generation-0 data; train B0 (deliverable 4); convert, run the
  parity test (deliverable 6); only then games.
- SPRT: B0 (`FORK_EVALUATOR=nnue`) against the bootstrap evaluation at
  STC on gainer bounds [0, 5] (gains this large end it quickly; the
  bounds policy of §5.2), on the GitHub shards. A pass switches the
  default evaluator, with the new bench in tests/bench.ref and the
  commit message; a fail goes back to deliverable 4 (more data, λ) with
  its result in the SPRT log.
- **Net registry** (`docs/nets.md`): one row per net (name, SHA-256,
  architecture, data manifests, training run record, parity bound and
  observed maximum, SPRT result), mirrored in ORIGINALITY.md's
  "Training data provenance" and published as a GitHub Release with the
  net file, the run record and the manifests.
- Generation 1 data starts with B0 at once (the Phase 4 outline:
  datagen keeps the local CPU busy while the designs proceed).

#### Constants (the owner's rule: every value justified and screened)

Initial values with their reasoning; each is screened by the
originality-checker (match / no match only) before its commit, and any
match goes to the owner first.

| Constant | Value | Reasoning |
|---|---|---|
| H (hidden width) | 256, kept by the owner (2026-10-28, question 7) | Above (B0 table). B0 is the generic minimal baseline shape (768 = 12 piece kinds × 64 squares; 256 a common round size) and exists to prove the pipeline, not as a distinctive design. The constant screen found the same shape in Berserk's 2021 release (a coincidence, recorded in ORIGINALITY.md) and 256 as a first-layer width in Stockfish 12-13 (near match, different inputs and body). |
| QA, QB | 255, 64 | bullet's standard quantization convention, kept by the owner (2026-10-28) as a trainer-interface convention credited to bullet (ORIGINALITY.md), not a tuned constant; the arithmetic above shows it is safe. Not screened. |
| S (output scale) | fitted | Logistic fit of result against score on generation-0 data. |
| Datagen nodes per move | 20,000 (screen: match; kept by the owner, question 10) | The count where the bootstrap search reaches depth 8 to 9 in a typical position. Measured 2026-10-28 with `tools/datagen/measure_nodes.py` (clang-release, Windows, a cleared 1 MB table per position) over the 46 bench positions: median last finished depth 3 at 1,000 nodes, 4 at 2,000, 5 at 5,000, 7 at 10,000, **8.5 at 20,000** (range 5-11), 10 at 50,000. Within a game the table carries entries from earlier moves, so the effective depth is a little higher. |
| Datagen TT size per worker | 1 MB (screen: no match) | The smallest power of two that holds one move's search: in the same measurement, one 20,000-node search from an empty 1 MB table filled 12% of it (median hashfull 120 per mille, largest 203), so replacement inside a 5-entry bucket is rare. Ten workers' tables (10 MB) also fit the 96 MB L3 cache. |
| Datagen game cap | 500 plies (screen: role not present) | Longer games are discarded. bullet's game reader at the pin stops at 512 records per game and would fail a loader thread beyond it (KB bullet-internals.md, UNVERIFIED whether records or plies; 500 keeps a margin either way). The throughput run below discarded none. |
| Datagen throughput | measured: 2,546 positions per second on 10 threads | `fork_datagen` on Windows (clang-release, bootstrap evaluation), 20,000 nodes, 1 MB tables, 3-4-5 tables partly present, the 46 bench positions as openings: 150,427 positions in 59.1 s (1,642 games, about 92 positions per game), about 220 M positions per day. Every game passed `verify_games.py`. Measured again on the real openings before generation 0. |
| Workers | 10 of 12 threads | Leaves two threads for development and CI-adjacent work; the one-heavy-job rule still applies (datagen is the heavy job while it runs). |
| Opening rating floor | 2000 (both players) | The KB's A+ description (training-data.md §3.4): positions from competent play, without engine choice. |
| Opening ply range, random plies | a random ply in 8-16, then 2-4 random plies | The KB's A+ description gives 8-16; a few random plies multiply the distinct positions without leaving plausible play. |
| Decided-opening bound | the bootstrap search at the datagen node count beyond ±400 cp | Four pawns: openings that lopsided teach little and end fast. |
| Shard size | 1 GB, or less if K11 shows a lower file limit | The KB storage design's 1-2 GB, at its low end so one failed upload costs little. |
| Generation 0 size | about 200 M positions, at least; more if the bake-off needs it | Within the KB's 100-200 M per first generation; refined by K5's training throughput and the measured datagen rate. The bake-off also runs on generation 0 (owner, 2026-10-28), and the judge sized its entries at about 0.7 B positions, so generation 0 may be extended before the bake-off; decided with the measured rate. **Outcome (owner, 2026-10-29):** generation 0 was stopped at 130,615,808 positions (1,366,657 complete games; data/manifests/g0.json) once B0r1 passed its SPRT. Generation 1 (B0r1, the same settings, seed 20261030) followed at once, and the bake-off trains on generation 1 data. |
| λ (score weight) | 0.5 for B0 | Generation-0 scores come from a weak evaluation and game results are noisy, so neither is trusted over the other; the analyst (step 7) tunes it per generation from measured results. |
| Loss, schedule, batch | from bullet's documented defaults for a single-layer net, recorded in the run record | Step 0 proves the pipeline; schedule tuning is step 7's. Each value used is written into this table at deliverable 4 with its source. |

#### Names (to be checked before use, §8 procedure)

Screened 2026-10-28 by a throwaway subagent (Stockfish ff7cee42,
Ethereal 0e47e9b6, Berserk 32628515, Weiss c735b8f3; match / no match
only):
- **No match:** `fork_datagen`, `SelfPlayGame`, `SelfPlayConfig`,
  `GameWriter`, `GameReader`, `CompactBoard`, `encode_move`,
  `decode_move`, `NetFile`, `NetHeader`, `FeatureSums`, `FeatureStack`,
  `output_layer`, `feature_index`, `netcheck`, `run_self_play`,
  `self_play`, `game_record`, `fuzz_game_record`, `net_file`,
  `fuzz_net_file`, `nnue_parity`, `net_format`, `feature_sums`,
  `datagen_openings`, `verify_games`, `upload_batch`, and the paths
  `tools/datagen`, `tools/nnue`, `tools/train`, `data/manifests`.
- **Accumulator** (type and file): matches in three engines, as the
  field's term (CPW's NNUE page has an Accumulator section): kept as
  domain vocabulary, as the owner allowed.
- **datagen** (the directory `src/datagen/`): one engine has a source
  file pair of that name in the same role; the word is the community's
  general term (OpenBench's workload type is called DATAGEN), so it is
  kept as domain vocabulary, flagged to the owner (question 8).
- **Renamed before use:** `AccumulatorStack` (an exact compound type name
  in one engine; the per-ply stack becomes `FeatureStack`, no match) and
  `clipped_relu` (an exact file and identifier in one engine; becomes
  `crelu`, no match).
- **Second screen** (same commits, 2026-10-28): the 37 further
  identifiers deliverable 2 introduced (its types, enumerators, helpers,
  `test_datagen`, `datagen_verify`, `datagen_main`, `measure_nodes`,
  `forkdatagen`): no match in any of the four.
- **Labeller policy** (2026-10-30, Stockfish ff7cee4, Ethereal 0e47e9b,
  Berserk 3262851, Weiss c735b8f): `part_end` (seal's parameter,
  `--part-end` and the manifest key): no match in any of the four.

#### Owner's answers (2026-10-28)

The review of this spec and of steps 1-3 (KB phase4-designs/, with the
judge's questions) was one batched stop; the answers, which the
deliverables above follow:

1. **No external SSD.** The staging directory is on C: (36 GB free on
   2026-10-28). Generation 0 (about 1 GB) fits easily; local shards are
   deleted after the Kaggle hash check (deliverable 3), so staging never
   holds more than the batches in flight. Disk is rechecked before each
   long datagen run.
2. **Kaggle**: the account exists; the test session (deliverable 0) runs
   with the owner.
3. **Datagen takes 10 of the 12 threads**; CI is the full check while it
   runs.
4. **B0's net is committed** to the repository (`nets/`), since TCEC
   builds offline from the source; every other net is published as a
   GitHub Release.
5. **"Accumulator" stays** (domain vocabulary, §8) if the name screen
   agrees; otherwise a Fork name.
6. QA and QB stay 255 and 64, bullet's standard quantization convention,
   recorded in ORIGINALITY.md as a trainer-interface convention credited
   to bullet, not a tuned constant (answered earlier the same day).
7. **Bake-off (plan step 4)**: every entry at accumulator width 512;
   the four candidates are built on **a shared kernel framework** (one
   accumulator, SIMD and parity framework that every candidate plugs
   into, not four separate implementations); **STC narrows the field,
   LTC decides between the finalists**; the bake-off runs on
   **generation 0 data** (not waiting for generation 1), and the winner
   is confirmed at full size later. **Changed 2026-10-29 (owner):** the
   bake-off trains on generation 1 data (B0r1's self-play), and every
   candidate trains on the same data.
8. **Speed price**: the 2:1 time-odds games are approved at **STC only**.
9. **Design-level originality screen** for XGR's exposure plane (X),
   phase gate (G) and revision head (R), AF's fitted king regions and
   AF's threat encoding, before any of them is built.
10. **bullet's code** (MIT, a tool) may be read by a subagent at the
    pinned commit, to settle the trainer features the KB marks
    UNVERIFIED (rounding rule, custom buckets, pairwise products, custom
    inputs, graph operations).
11. **Quantization-loss thresholds**: the implementer proposes each
    architecture's thresholds from its first net, for the owner's
    approval.
12. **One net** until the pipeline is proven; a separate datagen net is
    a later question.
13. **Threat inputs are in scope** for Phase 4, as a later add-on to the
    bake-off's winner.
14. **VNNI on TCEC's EPYCs stays UNVERIFIED** and is on the TCEC question
    list (KB competition.md, question 8). Nothing may depend on it.
15. **The older KB pages are scrubbed** of other engines' constants
    (techniques.md §4-5, research.md §6), keeping the ideas and sources.

#### Open questions (2026-10-28, raised while building step 0)

7. *Answered (owner, 2026-10-28)*: B0 stays 768 -> 256 -> 1, recorded in
   ORIGINALITY.md as the generic minimal baseline shape (768 = 12 pieces ×
   64 squares; 256 a common round size), noting the coincidence with
   Berserk's 2021 release; B0 exists to prove the pipeline, not as a
   distinctive design.
8. *Answered (owner, 2026-10-28)*: `src/datagen/` stays, as community
   vocabulary (OpenBench's DATAGEN).
9. **bullet's GPL and AGPL dependencies**: building bullet always pulls the
   Stockfish binpack reader (sfbinpack, GPL-3.0) and Monty's format crate
   (montyformat, AGPL-3.0, chess code from the Monty engine) into Cargo's
   cache (KB bullet-internals.md §9). Fork never uses them, but a local
   build would leave another engine's code on this machine. Options:
   (a) build bullet only on Kaggle, where the planned local check that
   bullet's loader decodes Fork's shards also runs (on a CPU session);
   (b) local builds with a throwaway `CARGO_HOME` in the scratchpad,
   deleted after each run, as the name-check clones are; (c) accept the
   cache. *Answered (owner, 2026-10-28)*: local bullet builds use a
   throwaway Cargo folder, deleted after each run; training builds run
   only on Kaggle; Fork never vendors or links those crates. Preferred if
   possible: bullet's Cargo features exclude the Stockfish binpack reader
   and the Monty crate entirely (checked by a research subagent; KB
   bullet-internals.md §12).
10. **Datagen nodes per move**: the second constant screen found 20,000 in
    Berserk's current documentation as the node limit of its OpenBench
    datagen preset (same role). Fork's 20,000 comes from its own
    measurement (median depth 8.5 on the bench positions, the spec's
    depth 8-9 target). *Answered (owner, 2026-10-28)*: keep 20,000, with
    the coincidence noted in ORIGINALITY.md.

**Design-screen credits** (the design-level screen of 2026-10-28, for the
bake-off; KB phase4-designs/judgement.md): XGR's linear output lanes
follow Stockfish's former PSQT accumulator (credit it; size the lanes by
XGR's own reasoning or to the three used); the purpose of XGR's revision
head (scaling pruning by how unreliable the evaluation is) is published
in Stockfish and Alexandria by other mechanisms (credit both); the
exposure plane, the learned phase gate, AF's fitted king regions and AF's
compact threat encoding have no precedent found; the hybrid H-512 is an
assembly of common concepts, with its counts (8 buckets, at most 4
regions) still to be screened as constants.

### 5.4 Phase 4 step 4: the bake-off (owner's instructions, 2026-10-30)

**Instructions.** (a) Training configurations for S-512, H-512, AF-S,
XGR-512 and the B0 control in the training program, each one's feature
handling checked against its parity reference. (b) A dry run of each on
Kaggle on a small data slice: it trains, saves, quantizes and passes the
parity chain. (c) At about 150 M generation-1 positions, a snapshot with a
held-out validation shard; all five trained on exactly that snapshot, same
steps, same tuning budget, two seeds each. (d) Parity and netcheck per net,
SPRTs one at a time on the GitHub shards against the B0 control (fixed
time, plus the fixed-node check), decided by the pre-registered rule
(judgement.md §6.3: complex against simpler on [0, 5], STC narrows, LTC
decides, an inconclusive pairing keeps the simpler design); LTC for the
finalists. Nothing is promoted before the owner's review.

**The entries as built** (`tools/train --arch`, descriptions in
`tools/nnue/<arch>.json`, independent reference `tools/nnue/models.py`):

| Entry (id) | Inputs per perspective | Body and output | Clips | Saved file |
|---|---|---|---|---|
| B0 control (1) | 768 | 256 CReLU -> 1 | bullet's ±1.98 | 394,756 B |
| S-512 (2) | 768, mirrored | 512 SCReLU -> 8, picked by phase | ±1.98 | 803,872 B |
| H-512 (3) | 768 × 4 fitted regions, mirrored, + 768 factoriser | 512 SCReLU -> 8, picked by phase | first layer and factoriser ±0.99 each, biases ±0.99 | 3,163,168 B |
| AF-S (4) | as H-512 | 512 clipped, halves multiplied -> 512 -> 16 -> 32 -> 1, SCReLU between, 8 phase stacks per layer | as H-512 | 3,222,560 B |
| XGR-512 (5) | 768 × 4 fixed regions (e1; f1-h1; rank 2; ranks 3-8), mirrored, + 768 factoriser, + 640 exposure + 10 factoriser | 512 SCReLU and 3 side values; two outputs blended by the gate | first layer, side layer and their factorisers ±0.99 | 3,828,494 B |

- **Features** (the same in Rust, Python and later C++): a perspective
  sees the board from its side (vertical flip for Black, its own pieces
  first: 384 × [enemy] + 64 × type + square); mirrored left-right (square
  XOR 7) when its own king stands on files a-d; the region of its mirrored
  king square (cell rank × 4 + file - 4) offsets the index by 768 per
  region; the factoriser input repeats the 768 index after the regions.
  XGR's exposure rule: a non-king piece is exposed when an enemy piece of
  a lower class attacks it (pawn < knight = bishop < rook < queen < king)
  or an enemy attacks it and no own piece defends it (pseudo-attacks on the
  real occupancy); its inputs are 320 × [enemy] + 64 × type + square, then
  5 × [enemy] + type for the factoriser. The phase selector is Fork's
  `game_phase` (knights and bishops 1, rooks 2, queens 4, capped at 24)
  through a 25-entry table.
- **S-512's selector** (owner, 2026-10-30): H-512's phase octiles instead
  of S's piece-count buckets (a near match to Stockfish's layer-stack
  selection), so S and H differ only in the king regions.
- **AF-S's body** (owner, 2026-10-30): kept as designed (16, 32, 8 stacks,
  int8 L1 at 64), although the constant screen found the same widths and
  stack count in Stockfish 14-18; recorded in ORIGINALITY.md.
- **XGR's side lanes**: 3 in the net file (the lanes used; the design
  screen's credit note), not the design's 8.
- **Maps, fitted on the training data** (`fork-train stats`, then
  `tools/nnue/fit_maps.py`): H-512's and AF-S's regions by AF's rule with
  the judge's θ = 10% and at most 4 regions; the phase octiles of all three
  selectors. The dry run fits them on its slice; the bake-off refits them
  on its snapshot before training.
- **Net file, version 2** (layout in `tools/nnue/models.py`): B0's 64-byte
  header with the bucket count, a 128-byte map block (regions, phase
  table), then each entry's tensors. AF-S's biases and output multiplier
  are quantized by the converter (their scales are not integers: L1 sums
  at 64 × 65,025 / 512 per unit, and so on, as exact rationals).
- **Integer arithmetic** as the designs specify it (design-speed.md §5,
  design-accuracy.md §5.3-5.4, design-novelty.md §5.1), emulated in
  `models.py` (R-int); the engine's inference follows the same spec.
- **Training** (`tools/train/kaggle/bakeoff.py`): every entry with the
  same settings and schedule, S fitted once on the training data, two at
  a time on the two T4s, the checkpoint with the lowest validation loss
  kept, the trainer's own evaluation of the parity positions (T) per run.

**Checked so far (2026-10-30, CPU, throwaway Cargo home).** Every graph
builds and its quantized file has the size above (bullet's own `check`).
**Feature leg**: the trainer's active inputs and bucket equal the
reference's (python-chess attack sets for XGR's exposure) on the 446
parity positions and on 200,000 generation-0 positions, for all five
(0 differences); planted faults are caught (exposure rule ≤ for <: 49,468
positions differ; mirror on the wrong side: all 200,000; a shifted region
map: 74,376; a queen phase weight of 3: 60,341). **Quantization leg**
against bullet's files of the initial weights: exact for all five,
factoriser merges and transposes included. Unit tests
(`tools/nnue/test_bakeoff.py`): legs pass on synthetic nets; a corrupted
weight, a missing factoriser merge, a transposed output layer and
truncation instead of rounding each fail.

**Dry run (2026-10-30, Kaggle kernel fork-bake-dry, 65a4c27, dataset
fork-g1s0)**: each entry trained 3 superbatches of 100 batches on g1s0
(S = 107, one seed), saved, quantized and evaluated the parity positions.
The parity chain on those nets: quantization leg exact for all five;
R-float against T at most 0.00018 cp (so `select` keeps one contiguous
block of rows per bucket, and the slices, gate, pairwise product and
factorisers are read as bullet computes them); quantization loss max / p99:
B0 11.1 / 7.1, S-512 13.0 / 11.2, H-512 18.1 / 11.9, AF-S 23.6 / 20.9,
XGR-512 9.8 / 8.7 cp. Training rates with two runs sharing the session's
4 cores: about 2 M positions/s for S-512, 1 M/s for H-512, AF-S and XGR-512.

**The engine's inference for every entry** (2026-10-30): one shared
framework in `src/eval/nnue/`, the architecture fixed at build time from
the embedded net's header (CMake reads its id into `FORK_NET_ARCH`;
`net_shape.hpp` holds each shape's constants). A perspective's frame (its
file flip and region rows) changes only when its own king crosses the d/e
line or a region boundary; that perspective is then recomputed from the
board at once, every other update stays incremental and lazy. XGR's
exposure rows are added at each evaluation (no incremental state). Every
output has a scalar reference and an AVX2 kernel (S/H/XGR: v * (v * w)
through 16-bit multiply and multiply-add; AF-S: the pairwise product as a
rounding high multiply, L1 as unsigned-by-signed byte multiply-adds); the
first-layer updates use B0's AVX2 and AVX-512 kernels. On each dry-run
net, for clang native, x86-64-v3 and scalar builds: the NNUE suite passes
(incremental against refresh along random games with king moves across
the mirror line and regions, every move kind's delta, SIMD against scalar,
colour symmetry, left-right symmetry for the mirrored entries, XGR's
exposure rule) and **netcheck gives the reference's R-int on all 446
parity positions** (F = R-int, every path); bench node counts agree across
the three builds of each entry. Local bench nps beside datagen (not an A/B
measurement): B0 2.96 M, S-512 2.31 M, H-512 2.21 M, AF-S 1.66 M, XGR-512
1.43 M (0.78, 0.75, 0.56, 0.48 of B0; the judge's model said 0.74, 0.73,
0.58-0.62, 0.51 of the bootstrap). Without a refresh cache: a frame change
recomputes the perspective from the board (judgement.md's cache is a speed
item for the winner). B0 is unchanged: bench 15,453,694, and its search
speed within noise of the previous build (`bench/ab_search.py`, 8 rounds,
-1.5% median, threshold 3%).

**XGR's entry condition** (judgement.md §3): the exposure pre-test on 10 M
g1s1 positions with B0r1 (`exposure_pretest.py`, now streaming in chunks):
mean k 0.50, k = 0 in 63.3%; the static evaluation's residual against the
search score is 75.2 cp (median 30) at k = 0 and 112.4 cp (median 53) at
k >= 1: X has something to fix, so XGR-512 enters the games.

**The bake-off snapshot g1s1** (2026-10-30, 10:32 AM EST): generation 1's
complete games at that moment, 1,505,322 games and 150,117,509 positions
(data/manifests/g1s1.json, worker 9 held out); 93,502,604 positions pass
the training filter in the training shards. Maps fitted on it: regions
{e1-e4, f4, g4} 31.5%, {f1-f3, g3} 20.9%, {g1} 22.7%, the rest 24.8% of
own-king samples; phase stacks 9-16% each. S = 105 (fit_scale.py, 2 M
positions). Training (`bakeoff.py`): every entry with seeds 1 and 2, 80
superbatches of 5 M positions (400 M seen, about 4.3 passes), LR 0.001
dropped tenfold after 40, λ 0.5, the checkpoint with the lowest
validation loss (20,000 held-out positions) kept; no per-entry tuning.

**Training results** (kernel fork-bake at d4ccadb, 2026-10-30; ten runs of
18-28 minutes on a T4). Validation loss at the kept checkpoint, seed 1 /
seed 2: B0 control 0.021679 / 0.021805; S-512 0.020974 / 0.021176; H-512
0.022349 / 0.022425; AF-S 0.021829 / 0.021631; XGR-512 0.021375 /
0.021201. Chosen (plan 1): B0 s1, S-512 s1, H-512 s1, AF-S s2, XGR-512
s2. The parity chain passes on all ten (R-float against the trainer
within 0.0002 cp). Matched scales (plan 2; the first 10,000 filtered
positions of g1s1-w09-val, the control's mean |eval| 281.9 cp): S-512
101 (both seeds), H-512 100, AF-S 111, XGR-512 96; parity and netcheck
redone on the rescaled files (0 mismatches). Candidate branches:
bake/g1b0, bake/g1s512, bake/g1h512, bake/g1afs, bake/g1xgr and
bake/g1s512b (S-512's seed 2, for plan 5).

**S-512 was still improving when training stopped**: its validation loss
over superbatches 71-80 is below that over 41-50 by 0.00018 (s1) and
0.00015 (s2), and its kept checkpoints are 68 and 71 of 80. The shared
budget ends before S converges.

**H-512's gap, diagnosed** (owner, 2026-10-30: no retraining, the plan
unchanged, H plays its games as is): **overfitting**. H has about 2.0 M
first-layer weights (four region copies of 768 × 512, the factoriser
merged in) against S's 0.39 M, on 93.5 M positions seen about 4.3 times.
Over superbatches 71-80 its training loss is the lowest of the entries
(0.01784 against S's 0.01958) and its validation loss the highest
(0.02269 against 0.02113): a gap of 0.0049 against S's 0.0016, and seed
1's validation loss rises after superbatch 52. On the held-out positions
it is worse than S-512 s1 **in every one of its regions** (the trainer's
loss recomputed per side-to-move region, reproducing the trainer's
totals exactly): +0.0010, +0.0017, +0.0019 and +0.0011 for regions 0-3
(seed 2: +0.0002, +0.0016, +0.0028, +0.0016), worst in {g1}, the largest
single-square region, so no starved or mixed region explains it; on
20,000 of its training positions both seeds beat S-512 in every region
(by 0.0013-0.0026). XGR-512 (the same four-copy input with a factoriser)
is about level with S-512 region by region on the held-out positions. Setup checked: trainer, reference and engine agree
(parity, netcheck); the committed map is what fit_maps.py's rule gives on
the stored histogram; the trainer's region lookup matches the histogram's
cells; the ±0.99 first-layer clip barely binds (no weight beyond 0.990,
under 0.001% at 0.98 or more). The data volume is the likely cause: θ =
10% with four regions was sized for 0.7 B positions (design-accuracy.md
§2.1's data-per-weight anchor, about 12.8 M touches per row), and g1s1's
93.5 M give about 1.7 M. The fitted map's shape also differs from the
design's expectation: g1 stands alone while h1, g2 and h2 share a region
with every rank 5-8 square, and e1 shares one with e4, f4 and g4. **King
regions join the component list** (judgement.md §5, row 5): retested
with much more data during the winner's full-size confirmation,
including a hand-drawn region map with the castled squares together.

**Games: the pre-registered plan** (written 2026-10-30, before any
bake-off game; judgement.md §6.2-6.3, the owner's (d)):
0. **First in the queue (owner, 2026-10-30): the B0 control against
   B0r1**, the default network, at STC on [0, 5]. If it passes it is
   promoted as **B0r2**: the default network (with its bench reference and
   parity file, as for B0r1), generation 1's labeller from then on, and an
   entry in docs/nets.md. The bake-off entries still play against the same
   B0 control.
1. **One net per entry**: of its two seeds, the one with the lower
   validation loss at its kept checkpoint. The other seed stays for the
   noise check (5).
2. **Eval-scale normalization** (§6.2): each entry's S in its net file is
   rescaled so that its mean |eval| over 10,000 positions of g1s1's
   held-out shard equals the B0 control's; the parity file and netcheck are
   redone with the rescaled file.
3. **Stage A, sanity**: each entry against the B0 control at STC (8+0.08,
   16 MB, Syzygy 3-4-5, the UHO book) on gainer bounds [0, 5], one SPRT at
   a time on the GitHub shards, never beside CI. A fail sends the entry
   back to training, not out of the bake-off.
4. **Stage B, fixed nodes** (diagnostic, no SPRT): each entry against the
   B0 control at a fixed node count per move, 1,600 games, for the accuracy
   term without the speed price.
5. **Training noise**: the two seeds of S-512 against each other, 1,600
   games at STC; if they differ by more than about 10 Elo, margins below
   that mean nothing and the top two get repeated trainings.
6. **Stage C, decisive pairings** in the judge's order, the more complex
   design against the simpler on [0, 5]: H-512 against S-512 (regions);
   AF-S against the better of S and H (the body); XGR-512 against H-512
   (X and G). STC narrows, **LTC decides** (40+0.4); an inconclusive
   pairing keeps the simpler design; caps 20,000 games at STC, 10,000 at
   LTC. The finalists play LTC.
7. Nothing is promoted (no default network change) before the owner's
   review of the results.

**Amendments after stage A (owner, 2026-10-31; decided after seeing stage
A's results**, sprt-log.md: S-512 H1, H-512, AF-S and XGR-512 H0 against
the B0 control, **and before any stage B or noise game**):
- **Item 3's retraining rule is replaced**: no entry is retrained alone.
  A stage A fail no longer sends the entry back to training by itself.
- **Item 4 decides who stays**: an entry that shows no accuracy advantage
  over the B0 control in stage B is dropped from the bake-off, not
  retrained. **The rule (owner, 2026-10-31, 12:04 AM EST, decided before
  any stage B result; the first run was still playing):** an entry has an
  accuracy advantage, and stays for round 2, if its stage B Elo point
  estimate against the B0 control is above 0. Why the point estimate and
  not an interval: keeping an entry costs only one more training run,
  while dropping one could discard a design expected to benefit most from
  more data; round 2's STC SPRTs remain the real filter.
  Stage B's conditions: 800,000 nodes per move for both engines (fastchess
  `nodes=`), under a 600+6 clock that never binds, otherwise as stage A
  (16 MB, Syzygy 3-4-5, the UHO book, stage 0's openings), 1,600 games,
  no SPRT (the run's LLR is ignored). The node count is a measurement:
  B0's first-move depth at STC in S-512's stage A games (50 opening
  positions, fresh hash) has mean 14.40 at 0.42 s per move; the B0
  control reaches mean 14.44 at 1.6 M nodes on the same positions, so the
  runners search about 3.8 M nodes/s (an estimate), and an average STC
  move (0.208 s) is worth about 800,000 nodes. **The estimate was high**:
  in the stage B games B0's median move took 0.33 s for 800,000 nodes
  (about 2.4 M nodes/s), so stage B searches deeper than STC (median depth
  17 against 15); the games themselves are unaffected (sprt-log.md).
- **Round 2 of the bake-off**: once about 500 M positions exist
  (generation 2 and the cloud data so far), every entry still in the
  bake-off, S-512 and the B0 control included, is retrained on the same
  larger snapshot with identical settings (one schedule and tuning budget
  for all, set before training), then the parity chain, scale matching
  and the games plan as for round 1.
- **XGR's three parts become add-ons to S-512**: the exposure plane (X),
  the phase gate (G) and the revision head (R), each its own experiment
  on top of S-512, planned after round 2. (2026-11-02, owner: on top of
  S512r2, the exposure plane first, after the current tier-2 queue;
  decisions log.)

**Engineering task before round 2 (owner, 2026-10-31; not a change to
round 2's rules):** XGR-512 placed second at fixed nodes (+52.07) but lost
at STC (-38.15), mainly on speed (0.48 of B0's nps). Its exposure rows are
recomputed from the board and added at every evaluation (no incremental
state). Investigate a cheaper computation, incremental or partial updates
in place of the full recompute, measure the speed gain with the A/B
harness with the output unchanged (netcheck's R-int on the parity
positions, bench identical), and report to the owner before round 2.
**Result (2026-10-31, branch `xgr-speed`, 49c421c on bake/g1xgr; adopted
into phase-4 for round 2 by the owner, identical evaluations being the
condition: inference speed is not a training change, so round 2's rules
are unaffected):** the exposure rule computed set-wise
(each side's attacked squares accumulated by attacker class, every piece's
lowest enemy attacker class read off the sets, in place of attackers_to
square by square) and no accumulator copy when nothing is exposed. Output
unchanged: bench 15,540,185 / 9564dc8f27cd9708 on both sides, netcheck 446
positions with 0 mismatches; a test checks the rule against the
square-by-square reference at every ply of random games (fault-injected).
Every XGR-512 net, old build against new: netcheck 446 positions with 0
mismatches for the entry (seed 2 scale-matched, g1xgr) and the raw seeds 1
and 2, and `fork evalfens` byte-identical on 500,005 positions of run g2's
held-out shard for each of the three (48.8% of them with an exposed piece,
so both paths ran).
Speed (bench/ab_search.py, WSL clang-release, core 4, g2c paused, the
openings stream running; an A/A run beside it moved -0.4% / +0.9%):
+15.5% median nps (2.42 to 2.80 M), +15.1% best, 10 rounds. Against the
B0 control's bench nps XGR goes from 0.44 to 0.50. Exposure switched off
entirely (a timing build only, its output differs) runs about 13% faster
than the new version, the most an incremental exposure could still gain;
most of the remaining gap to B0 lies outside the exposure (the profile:
evaluate_position 30% of the run, advance_perspective 19%).

**Round 2 amendment (owner, 2026-11-01; decided before any round-2 game
result).** Round 2's S-512 was promoted as S512r2 (+151.35 Elo against
round 1's S-512, docs/nets.md) before the other round-2 nets were ready.
Each remaining entry, H-512, AF-S and XGR-512 (each the round-2 seed with
the lower validation loss, item 1), first plays a **fixed-node match
against S512r2** at the same node budget for both engines, 1,600 games;
**only an entry that scores above S512r2 there** (its Elo point estimate
above 0, as in round 1's stage B rule) proceeds to an **STC promotion
SPRT against S512r2 on [0, 5]**; the others leave the bake-off.
**Reasoning:** every remaining entry is slower than S512r2 (round 1's
bench nps relative to B0: S-512 0.78, H-512 0.75, AF-S 0.56, XGR-512
0.48, about 0.50 after the exposure speed-up), so at equal time it searches fewer nodes than at equal nodes; an
entry that fails at equal nodes cannot win at equal time, and the match
costs no SPRT slot. For these entries this replaces stages A to C (items
3, 4 and 6); items 1 and 7 still apply (one seed per entry, nothing
promoted before the owner's review). The match's conditions are round 1's
stage B: 800,000 nodes per move for both engines (fastchess `nodes=`)
under a 600+6 clock that never binds, Hash 16 MB, Syzygy 3-4-5, the UHO
book, no SPRT (the run's LLR is ignored). Scale matching (item 2) uses
S512r2, the opponent in every remaining pairing, as the reference, as for
S512r2's own SPRT, whose matching was to its opponent.

**Retest and LTC candidates (owner, 2026-11-02; decided after the
fixed-node results and before any round-2 STC result).** Two outcomes
keep an entry on record instead of ending it:
- **Retest candidate:** an entry whose fixed-node Elo interval (the run's
  95% error bar) includes 0, or whose STC result against S512r2 is within
  its error margin of S512r2 (its Elo interval includes 0), is kept as a
  retest candidate for after the post-network search retune (the
  re-validation and margin retune, §5.2 Quality control 6). The fixed-node
  results (history/phase-4/sprt-log.md): H-512's interval, −22.75 to
  −1.59, excludes 0, so its loss is clean and it is not a candidate;
  AF-S's, −0.07 to +20.79, includes 0, but AF-S passed the screen on its
  point estimate; XGR-512's, +20.33 to +41.07, is wholly above 0.
- **LTC candidate:** an entry that beats S512r2 at fixed nodes (its point
  estimate above 0, as AF-S and XGR-512 did) but fails its STC SPRT is
  recorded as an LTC / TCEC-conditions candidate, tested later at a long
  time control with an x86-64-v4 build on AWS (AWS is unavailable until
  further notice: owner, 2026-11-05, decisions log).

An entry can be both. Neither kind is promoted without that later test and
the owner's review (item 7).

**An STC SPRT undecided at its cap (owner, 2026-11-02; decided after
AF-S's STC result and before XGR-512's).** An STC SPRT still undecided at
its 20,000-game cap counts as **not passed**: no promotion. The entry
qualifies as both an LTC candidate (if it beat S512r2 at fixed nodes) and
a retest candidate (an undecided result is within the error margin).

**The speed gate for new input types (owner, 2026-11-05).** A network design that adds an input type (threat or contact inputs, pawn pairs, an exposure plane, any new feature set) must keep the engine at **0.90 or more of the current default's nodes per second** before training it is worth a Kaggle session (S512+PP, owner, 2026-11-06: trained at 0.90 or more, with 0.95 as the goal reported beside it; the gate is revisited after the speed-to-Elo measurement, idea 46, and final adoption is by SPRT as always). The measurement: a quiet machine (every other CPU job suspended), release builds of the same source tree differing only in the network, interleaved, the median ratio reported. **The identical-tree method is preferred whenever the tree can be held identical** (owner, 2026-11-06): the new layout's net built from the default's weights with every new-input weight zero, so it searches the default's tree exactly (bench nodes and signature equal), and plain interleaved bench rounds measure the cost alone. Otherwise (a synthetic net, whose weights change the tree) runs at a fixed time per position, not a bench time, since a synthetic net can explode the fixed-depth tree. Below 0.90 the design is optimized first: incremental updates on make and unmake instead of recomputing per evaluation, 8-bit weights where the trained weights' range allows, fewer redundant features. The reason: S512+X, 2.2% lower in validation loss and +25.67 ± 10.26 at fixed nodes, lost −30.04 ± 10.82 at STC at 0.818 of S512r2's speed (history/phase-4/sprt-log.md); XGR-512 before it, +30.70 at fixed nodes, failed at STC and LTC.

**Not in this bake-off**: AF's small-layer activation sweep and XGR's two
ablation nets (no X; buckets instead of G); judgement.md lists them as
optional, the owner's five entries leave them out. XGR enters only if its
exposure pre-test passes with the current net on generation-1 data
(judgement.md §3).

#### S512cl: S-512 with Fork's contact and pawn-link inputs (ideas.md 41; owner, 2026-11-05)

Replaces the S512+X plan; **no exposure plane** (owner, 2026-11-05). Fork's
own encoding, designed from the concepts in KB nnue-inputs.md §1-2 (no
engine's indexing, layout or constants); branch nets/s512cl, built on
nets/s512x's infrastructure (the trainer's add-on inputs, the warm start
with new inputs at zero, the 32-bit row sums, the parity legs).
Architecture id 7, name `s512cl`.
- **Frame:** every square in a perspective's frame, the piece inputs' frame
  (vertically flipped for Black, mirrored left-right when that side's king
  is on files a-d), so every family mirrors alike (KB §2.6's pitfall).
  Sides are relative (own, enemy); a class is side x 5 + kind (pawn,
  knight, bishop, rook, queen). Kings take part in no contact or link.
- **Contacts** (the threat inputs): one input per (attacker class, attacker
  square, target square, victim class) for a piece that attacks another on
  the current board (sliders stop at the first piece, pawns diagonally
  forward), neither a king, not both pawns (the links take pawn contact).
  **Fork's redundancy rule:** when two pieces attack each other one input
  implies the other, and Fork keeps **the one whose attacker is the cheaper
  piece** (pawn < knight = bishop < rook < queen), between pieces of one
  kind the one whose attacker stands on the lower frame square. (The KB
  reports one engine keeping the more valuable attacker; Fork's choice
  keeps the "threatened by a lesser piece" direction, the one T56's cheaper
  set uses too.) Mutual pairs arise only for one kind, a queen with a rook
  on a line or a bishop on a diagonal, and a bishop or queen with a pawn
  that attacks it back; so those combinations are left out of the index
  space statically, with the others no position can activate (pawns on the
  first or last rank).
- **Links** (the pawn-pair inputs): one input per unordered pair of pawns,
  of either side, on the same or adjacent files (KB §2.2's observation).
- **Index space**, enumerated once in a fixed order that the engine, the
  trainer and the Python reference each build themselves: contacts by
  attacker class, attacker square, target square (ascending, over the
  squares the attacker's kind reaches on an empty board) and victim class,
  possible combinations only (**50,416**); links by the pair of pawn slots
  (side x 48 + frame square - 8), the lower first (**1,488**). Inputs: the
  768 piece rows, then the contacts, then the links: **52,672**.
- **Net file:** version 2, as S-512's (feature weights i16 [inputs][512],
  biases, output weights and biases; S-512's 8 phase-picked outputs), so
  about 54 MB of feature weights. Storing the contact and link rows as int8
  (KB §1.4 item 6) is a later option, with a training clip; **the file's size
  in the public repository is a question for the owner before a trained
  S512cl is committed**.
- **Inference, first version:** the piece accumulator stays incremental; the
  contact and link rows are found from the position and summed at
  evaluation, in 32 bits from the piece accumulator, then held to int16
  (exact: the activation clips to [0, QA]), as S512+X's exposure rows are.
  The row-sum kernel has a scalar reference and AVX2 and AVX-512 paths with
  an equivalence test (.claude/rules/simd.md). Incremental contact updates
  (KB §1.5) and a cache of the links by pawn key are later speed steps,
  each with bench unchanged.
- **Parity:** the three implementations' feature lists are compared (the
  trainer's `fork-train features` and the engine's against the reference),
  on the parity positions and on data positions, then the network's
  netcheck as for every architecture; planted faults must fail them.
- **Training:** a warm start from S512r2's float weights with the 51,904 new
  inputs appended as zero columns (so it starts at S512r2's exact output),
  S512r3's settings and data (g2s1 + g3s1, 360 superbatches, S = 92, two
  seeds), at most 392 active inputs per perspective (32 pieces, 240
  contacts: at most eight per piece, 120 links).
- **Tests** as the bake-off's entries: a fixed-node screen, then an STC SPRT
  against the default network.

### 5.5 The public web page: Fork in the browser (owner, 2026-10-31; plan, not built)

The owner's request: a public GitHub Pages site where anyone can play Fork
and watch it learn. **Timing:** building starts after round 2 of the
bake-off starts, on spare CPU only: Emscripten builds and Node test runs at
idle priority (`nice -n 19`), never beside a timing measurement, a local
SPRT, a verification run or another heavy job (the background datagen goes
on as it does beside every other job). **Order:** the five parts below, in
order; the WASM parity results go to the owner before anything is
published. Facts below were checked on 2026-10-31 from the sources named
(kb-researcher; to be logged in docs/kb/sources.md on branch kb when the
build starts); anything not checked is marked UNVERIFIED.

**Where things live.** The engine-side additions (a `wasm` build
configuration, the web entry points, their tests) are ordinary commits on
the development branch, with CI and bench parity like any other change.
The site itself lives on a dedicated orphan branch `site`: the page source
(plain HTML, CSS and JavaScript modules, no framework, no build step beyond
copying), the build script that compiles the engine modules at a named,
pushed engine commit, and the published output in `/docs`. GitHub Pages
can deploy from any branch, folder `/` or `/docs`, with a `.nojekyll` file
to skip Jekyll (docs.github.com, "Configuring a publishing source"). Pages
limits: published site at most 1 GB, soft bandwidth 100 GB a month, files
over 100 MiB blocked by GitHub (docs.github.com, "GitHub Pages limits",
"About large files"). `.wasm` is served as `application/wasm` (checked
with `curl -I` on two github.io sites). Enabling Pages on the repository
is a settings change: done with the owner's go-ahead at the first publish.

**1. The engine in WebAssembly.**
- Toolchain: Emscripten 6.0.13 (released 2026-10-19; MIT or NCSA), built
  with `emcmake cmake` (its toolchain file accepts C++20 under CMake 3.12+,
  so Fork's 3.22 floor is fine; emscripten.org "Building projects",
  cmake/Modules/Platform/Emscripten.cmake). A `wasm` preset: no `-march`,
  the no-PEXT magics (BMI2/PEXT is not among Emscripten's emulated
  intrinsics), no Syzygy (Fathom maps table files with `mmap`, and the
  tables are gigabytes), a fixed small hash. Whether Fork compiles
  unchanged under Emscripten is UNVERIFIED until the first build.
- Single-threaded. Emscripten's threads need SharedArrayBuffer, which
  browsers allow only on pages served with COOP/COEP headers, and GitHub
  Pages cannot set response headers (emscripten.org "Pthreads"; Pages
  limits; community discussion 13309, open). The only workaround, a
  service worker that adds the headers (coi-serviceworker, MIT), reloads
  the page on first visit and is untested here, so it is not used. The UCI
  session runs each search on its own thread, so the web build gets a
  small synchronous entry module (new names, screened before use): set a
  position, list legal moves, search to a node or time limit (the search
  already polls its hard time limit) while passing each iteration's
  depth, score and principal variation to JavaScript, return the best
  move; and the static evaluation of a position. The engine runs in a Web
  Worker, so the page never freezes; a search cannot be interrupted, so
  "stop" ends the worker and starts a fresh one.
- One module per network. A build compiles the inference for its embedded
  network's architecture (FORK_NET_ARCH comes from the net file), so each
  promoted network is its own module, `fork-<net>.wasm` with its JavaScript
  loader, downloaded only when chosen; the bootstrap evaluation is a module
  built with FORK_EVALUATOR=bootstrap. Network sizes: B0, B0r1, B0r2 about
  0.4 MB, S-512 0.8 MB (plus the engine code, to be measured). No
  run-time network loading is added to the engine.
- Inference: first the existing scalar paths (`*_scalar`, the parity
  references). Then, only if speed calls for it, WASM SIMD (128-bit; Chrome
  91+, Firefox 89+, Safari 16.4+ including iOS 16.4+, Node 16.4+;
  webassembly.org features.json, v8.dev, webkit.org): Emscripten compiles
  SSE to AVX2 intrinsics with `-msimd128`, most 256-bit operations as two
  128-bit ones and some scalarized (emscripten.org "Porting SIMD code"), so
  the first try is Fork's AVX2 kernels unchanged, measured against scalar;
  a `wasm_simd128.h` path is written only if that is slow. Every inference
  path is checked as below.
- **Verification (reported to the owner before publishing):** each
  module run under Node.js (`node fork-<net>.js netcheck ...`, real file
  access with `-sNODERAWFS=1`) must give 0 mismatches on its network's
  parity file (tests/nnue/<net>.parity, 446 positions), for the scalar and
  for any SIMD build; and its `bench` must give the native build's node
  count and signature (tests/bench-<net>.ref): the search is deterministic,
  so equal evaluations and move ordering must give an equal bench, and a
  difference (for example from wasm32's 32-bit pointers in the hash) is
  investigated, not accepted. Speed is reported as bench nodes per second
  in Node and in a desktop and a phone browser.

**2. Play tab.**
- Board: chessground 10.5.0 (lichess-org, GPL-3.0-or-later, so compatible
  with Fork's licence; no dependencies; touch drag and drop; npm
  `@lichess-org/chessground`), vendored into the site branch with its
  licence and credited on the page and in ORIGINALITY.md. Fallback:
  cm-chessboard (MIT, no dependencies, touch). Legal moves come from
  Fork's own move generator through the entry module, so no second rules
  library is needed; move notation (SAN) is written for the page from the
  legal-move list.
- Choices: colour (or random), time per move, and a strength level. Levels
  are node limits per move (no engine change); their Elo is not claimed
  unless measured.
- Evaluation bar from the search score (the side-to-move score turned to
  White's view; the bar shows the network's own win probability,
  sigmoid(score / S) with that network's output scale S from docs/nets.md)
  and the principal variation in SAN, updated each iteration.

**3. "Watch it learn" tab.**
- A network manifest (`nets.json`): each promoted network's name,
  architecture, module file, size and SHA-256, promotion date, its SPRT
  result against the network it replaced (Elo, interval, games, run), the
  data it was trained on and its validation loss. The first entries:
  bootstrap, B0, B0r1, B0r2, S-512; later networks are added by the
  promotion step.
- Generation against generation: pick two networks; they play live in the
  browser, two workers, at a fixed node count per move, from openings in
  Fork's own openings set (Lichess human games).
- A fixed set of positions with each network's evaluation side by side.
  The positions are taken only from sources fetched and checked character
  by character (non-negotiable 1): the CPW perft positions already in
  tests/suite.hpp first, others with their source named on the page.
- Progress timeline: Elo (the chain of promotion SPRT results; self-play
  Elo, labelled as such), training data (positions per generation, from
  data/manifests) and validation loss, read from `progress.json`, which a
  tool (`tools/site/`, names screened) regenerates from committed records;
  the promotion checklist gains a step that rebuilds it and the network
  modules on the site branch.

**4. Phones, themes, size.** One layout from phone to desktop (board first,
controls below on narrow screens); light and dark following the system
setting, with a toggle; network modules loaded on demand, nothing larger
than the page and the first module loaded up front; no web fonts, no
external requests at run time (the board library is vendored).

**5. Privacy.** Static files only: no analytics, no cookies, no third-party
requests. Before every push of the site branch a scan of everything it
adds (as for the repository: the user name, home paths, the personal
email, account ids, bucket and profile names, secrets) must come back
empty; networks and modules are built only from pushed public commits.

**The bare-bones version first (owner, 2026-10-31).** Built now, ahead
of the rest, which stays pinned as planned above:
- `.github/workflows/web.yml`, started by hand, on GitHub's runners only
  (no local CPU, no `site` branch): by a push to the trigger branch
  `web-build` (checks only) or `web-deploy` (checks, then deploy), since
  GitHub dispatches a workflow by hand only once its file is on the
  default branch; by manual dispatch once it reaches main. The deploy
  needs the `github-pages` environment to allow `web-deploy`: Emscripten 6.0.13 builds Fork with its
  default network (S-512), scalar inference, single-threaded, with a 16 MB
  hash on the page; `fork.js` runs under Node.js for the parity checks
  (netcheck on the network's parity file, 0 mismatches required; bench
  parity against tests/bench-<net>.ref and tests/perft_bench.ref, through
  .github/ci/bench-parity.sh unchanged); only if they pass is the page
  assembled, scanned for personal data (paths, addresses, keys, tokens;
  the WebAssembly through `strings`) and, when the run's `deploy` input is
  set, deployed with GitHub Pages' Actions deployment (configure in the
  repository settings: Pages source "GitHub Actions").
- The page (`web/`): the chessground board (credited, with its licence),
  a choice of colour, Fork answering at 200,000 nodes per move (a page
  setting chosen to keep a phone's move near a second; measured once the
  module runs), new game, game-over messages (checkmate, stalemate, the
  fifty-move rule, threefold repetition, insufficient material), phones
  first, light and dark. Fork is the only rules source: legal moves,
  positions and the game's end come from the engine through
  `src/web/web_engine.hpp`.
- The engine side: `src/web/web_engine.*` (the synchronous entry points,
  tested natively in fork_tests' `web` suite), the `fork_web` target and
  `fork.js` link options under Emscripten, no `-march` and no `-g` there,
  and no thread library (Emscripten's threads need shared memory).
- After the first good run, the WebAssembly parity checks join CI as a job.

**v2 (owner, 2026-11-02: strength levels, the evaluation bar and a network
selector for "Watch it learn"; code written on branch `web/v2`, deployed
only when GitHub's queue is free).** Unverified in WebAssembly until its
first `web` run: the native and Node.js tests below ran, the Emscripten
build did not (it runs on GitHub's runners only).
- Engine side (`src/web/web_engine.*`, native tests in the `web` suite, each
  fault-injected): each finished iteration is reported during
  `fork_web_search` (depth, score, nodes, line), to the page through an
  `EM_JS` call of the module's `onIteration` and natively to a hook set by
  `fork_web_set_iteration_hook`; `fork_web_san` writes a line in standard
  algebraic notation from the legal-move list on a position of its own (so
  it may run during a search), the engine staying the page's only rules
  source; `fork_web_evaluate` gives the static evaluation. The expected SAN
  in the tests is python-chess 1.11.2's for the same moves.
- One module per evaluator: `web.yml` builds the bootstrap evaluation and
  every promoted network (B0, B0r1, B0r2, S512, S512r2) as
  `engines/<id>/fork_web.{js,wasm}`, one job each, each with netcheck (0
  mismatches; none for the bootstrap) and bench parity under Node.js; a
  worker loads only the module its `net` parameter names, when it starts.
  `web/nets.json` is the network manifest (values copied from docs/nets.md
  and the Phase 4 SPRT log, checked against both by `web/test/page.test.js`);
  the build adds each module's path, size and SHA-256 (`web/fill_nets.py`).
  The promotion step adds a network to nets.json and to the matrix.
- Play tab: five strength levels (1,000, 10,000, 50,000, 200,000 and
  1,000,000 nodes per move; no rating claimed), the evaluation bar
  (sigmoid(score / S) from White's view with the playing network's S, mates
  at the ends), the principal variation and the game in SAN, updated each
  iteration.
- "Watch it learn" tab: two chosen evaluators play each other live, two
  workers, at 10,000, 50,000 or 200,000 nodes per move, from the start
  position or a random position of Fork's committed test set
  (tests/datagen_openings.epd, the bench positions: CPW perft and Lichess
  CC0 games); the networks' record (promotion date, SPRT, the running total
  of the promotion SPRTs labelled as self-play Elo, data, validation loss,
  module size); and every evaluator's static evaluation of the CPW perft
  positions of tests/suite.hpp side by side.
- Tests: `node --test web/test/page.test.js` (the score, bar and notation
  helpers; the fixed positions against tests/suite.hpp; nets.json against
  the docs and the files each network needs), run locally with Node.js 24
  and by the workflow before the page is assembled.

**Tests.** The entry module's functions get native unit tests (they compile
outside Emscripten too); the Node runs above are the WASM tests. Whether
CI gains an Emscripten job (cached SDK) is decided with the owner once the
build exists.

### 5.6 The Phase 4 checklist and its order (owner, 2026-11-06; the order approved the same day, item 7 changed; the order replaced on 2026-11-07 after the Phase 4 think tank)

Everything Phase 4 still owes, nothing cut, each item with its status, kept
current as items move (the decisions log records each owner decision once;
this section is the running list). Estimates are rough wall-clock times
(UNVERIFIED until run): GitHub's shards run one SPRT at a time (an STC SPRT
up to 12 stages of about 18 minutes, so up to about 3.6 hours; an LTC SPRT
up to 6 stages of 1,664 games at 40+0.4); Kaggle sessions run beside them;
local CPU jobs run one heavy job at a time beside data generation.

**The re-validation queue** (owner, 2026-11-06; recorded, not started):
GitHub filler after the current SPRT queue (the threat set, ProbCut, the
speed-to-Elo measurement), each STC on [0, 3] with S512r2 as the default,
logged in the SPRT log as **network-era retests of bootstrap-era
results**:
1. B-4, the TT-refined quiescence stand-pat (reverted in 1e16853 after H0
   at STC with the bootstrap evaluator, −4.11 ± 3.93 Elo; its code comes
   back from 6c797e1 behind a switch).
2. Keeping exact TT entries (`UseTtKeepExact`, off; inconclusive at its
   cap, −0.6 ± 7.5 at 4,800 games, on [−3, 0]).
3. B-3, the shallower fail-high re-search (b001d1e; reverted, inconclusive
   at its cap on [0, 3]), retested alongside idea 29's measurement (how
   often unconfirmed root fail highs hold; the owner confirmed this
   reading, 2026-11-06).
4. The root fail-high fix (f0a9caf; rejected at STC, −14.6 ± 10.8, reverted
   in 1fb18f4; idea 29 reopens it).
RfpMargin 40 (rejected in favour of 80 by its gauntlet data, idea 34) and
every Phase 3 margin go to the SPSA retune instead of SPRTs.
**Shrunk** (owner, 2026-11-07, think-tank decision 20): items 3 (B-3) and 4
(the root fail-high fix) are dropped (a timed search reaches the soft
check only after a completed iteration, so no root fail high is pending
there); item 1 returns only as the stand-pat refined by main-search TT
entries (R13, order step 12); item 2 only at a hash scaled to TCEC's
pressure (X23), otherwise dropped. Idea 34 is retired as a standalone
test (one point on the early SPSA's axis).

**Network**

| item | status (2026-11-06) |
|---|---|
| More data generations | g3 (500 M), g3b, g3c, g3d sealed; g3e sealed at S512+PP's promotion (517,947 games, 48,577,036 positions, S512r2's labels); g3f (S512+PP's labels, from 4:58 PM EST) stopped at a game boundary at S512ppr2's promotion (11:50 PM EST) and sealed as its part (data/manifests/g3f.json); **g3g labelled by S512ppr2** from a fresh PGO build of the promotion commit (the labeller policy). The snapshot g3s2 was built and item 7's retrain ran on it (below) **2026-11-07 (owner, think tank; DESIGN §6):** **g3g stopped at a game boundary at 12:16 PM EST on 2026-11-07 (owner: data generation cut from 10 to 6 threads), at 111,190,930 positions (50,692,451 unsaved) in 1,191,355 games of its 366,424,464 target, and sealed (seal-g3g); the generation continues as g3h on 6 threads** (seed 20261113, the same default engine, started by the chain g3h-chain once the seal succeeds), still from lichess-2016-09.epd: the switch to lichess-2026-09.epd (decision 12) waits for its duplicate count and an openings manifest, and comes at the next part boundary; search adoptions are bundled into at most one part switch per day (decision 24). |
| Endgame slice and the standing acceptance test, now the integrity/recall gate (idea 45) | **in g3s2** (10 files of 2,600,000 one-move games, about 2.1% of its positions); the retrained default S512ppr2 misjudges 8 of the 900 positions, against S512+PP's 351 (**a recall figure** (2026-11-11, bug review T1): 898 of the check's 900 positions are in the slice's files verbatim, so the drop shows that the slice's positions were learned, not that endings were understood; on the held-out check (tools/nnue/endgame_heldout.py: 3,800 positions in 19 material classes the slice cannot generate, zero overlap) S512+PP misjudges 945, S512ppr2 454, S512ppr3 514, r8btd90 526, r8brft1 612). Recorded from the start (owner, 2026-11-06; lifted from its hold): the Syzygy-labelled slice of at most 5 pieces goes into g3s2, and the 900-position check (tools/nnue/endgame_check.py) becomes the standing acceptance test for the retrained default (targets to be set); the KRK conversion test found 3 of 20 drawn by the fifty-move rule **2026-11-07 (owner, think tank; DESIGN §6):** the acceptance target is **at most 15 of 900 misjudged** (decision 10); idea 45 part 3 (conversion without tables) dropped; the check extended to 4-5-man classes (X19, report-only); the endgame-start slice (R32) deferred until item 8a's result (decision 17). **2026-11-12 (owner, about 4:40 PM and 5:00 PM EST):** the 900-position check **stays a gate**, named the **integrity/recall gate** (at most 15 of 900 misjudged; it catches missing or corrupted slice data, not understanding of endings; enforced by gates.sh for slice-trained nets, `SLICE_TRAINED=1`, reported only otherwise, about 5:50 PM EST); the held-out checks (4-5, 6-7 and 8-12 pieces) are reported and flagged for the owner's review when more than 15% worse than the current default net (the net a promotion would replace), with the change against each run's warm start reported for diagnosis, never a gate on screening or promotion. |
| S512+PP evidence (idea 40's L1 first step) | R = 1 (608 links), trained as the owner's recorded exception to the speed gate at 0.895: fixed-node screen against S512r2 **+46.09 ± 10.37** (run 42284077960), then the STC SPRT [0, 5] **H1 accepted, +32.67 ± 10.48** after 1,600 games (run 42294907752, 2026-11-06; sprt-log). **Item 7's retrain therefore uses the S512+PP architecture** (the owner's gate). **Promoted to the default network** (owner, 2026-11-06): bench 13,909,380 / 831e5c9295839f87; the speed exception (0.895) and the endgame check (351 of 900 misjudged against S512r2's 249) recorded in docs/nets.md. Replaced the same evening by item 7's retrain, S512ppr2 (below) |
| Item 7's retrain (S512ppr2) | **Done; promoted to the default network** (owner, 2026-11-06). The S512+PP architecture on g3s2, two recipes with two seeds each (Kaggle fork-retrain-g3s2 v1): the warm start (from S512+PP's float weights, LR 0.0001, tenfold drop after superbatch 180) mean best loss 0.01909453 on g3s2-val, from scratch (0.001, the same drop) 0.01951758. **The recipe result: the warm start is better by 0.00042, about ten times the 4e-5 seed spread, so resolved; it is now the standard retrain recipe** (owner, 2026-11-06). The candidate, warm seed 1 (0.01908862) at the matched S = 89 with 2 of 311,296 link weights clamped: parity within S-512's limits (max 7.9 cp, p99 6.1 cp), the endgame check 8 of 900 misjudged (S512+PP 351), the STC SPRT [0, 5] against S512+PP **H1 accepted, +20.11 ± 7.22** after 3,200 games (runs 42335141916, 42336446490; sprt-log). Bench 14,626,377 / 9e43990217b0886d (docs/nets.md) |
| Item 8, the retrain loop (8a, 8b, ...) | **Idea 70's result fine-tune of r8btd90: r8brft1 promoted to the default network** (owner, 2026-11-11): r8btd90's window average fine-tuned at result weight 1.0, LR 1e-5 constant, 60 superbatches on g4s1, the mean of superbatches 46-60 (docs/research/retrain-8b/rft-plan.md); fixed-node screens against r8btd90: seed 1 **+7.17 ± 9.93** (run 42962187538), seed 2 +6.73 ± 9.44; seed 1's STC SPRT [0, 5] **H1 accepted, +5.74 ± 3.81** (nElo +9.69 ± 6.43) after 11,200 games (runs 42974677403 to 42988446282; sprt-log); the endgame check 7 of 900; bench 10,708,227 / c5dfc0ec1923d3b0 (docs/nets.md). 8b's keep rules (2026-11-11): TD(0.9) labels stay in the standard recipe; idea 69 (cw) dropped; every future retrain arm runs 2 seeds. **8b done; r8btd90 (the TD(0.9) arm) promoted to the default network** (owner, 2026-11-10): five arms from S512ppr3 on g4s1 (docs/research/retrain-8b/plan.md); fixed-node screens against S512ppr3: c +13.03, i52 +5.86, td80 −1.09, **td90 +17.39 ± 9.71** (run 42910703028); td90's STC SPRT [0, 5] **H1 accepted, +12.17 ± 5.71** (nElo +20.96 ± 9.83) after 4,800 games (runs 42917050282 to 42922442883; sprt-log); the endgame check 7 of 900; bench 9,594,307 / 4eb36793548711d4 (docs/nets.md). The head-to-heads against the control (ideas 51 and 52's keep rules) are still pending. **8a done; S512ppr3 promoted to the default network** (owner, 2026-11-07): R1-avg (the standard recipe from S512ppr2, seed 1, the mean of superbatches 331-360; full g3s3-val loss 0.01966655 against S512ppr2's 0.01968472), S = 89, qloss 9.4 / 7.5 cp, the endgame check 8 of 900; the fixed-node tie-break **+15.65 ± 9.26** (run 42426868742), then the STC SPRT [0, 5] against S512ppr2 **H1 accepted, +7.12 ± 4.53** (nElo +11.98 ± 7.61) after 8,000 games (runs 42429984619 to 42435511074; sprt-log); bench 14,149,617 / 1cb0717f040c294d (docs/nets.md). The cooldown branch and the anneal-only arm did not beat R1-avg. Planned: **8a**: the retrain on g3s3 (g3s2 + g3f + g3g) as soon as g3g's seal, manifest and Kaggle upload are done (g3g sealed early on 2026-11-07, so 8a runs about a day sooner than planned, with about 0.4 of the planned g3g data: its prediction shrinks accordingly, UNVERIFIED), with the standard recipe as the control and the arms of docs/research/phase4-think-tank/phase-c-synthesis.md §5 (decision 10; order step 8); 8b, 8c each when about 150 M new kept positions from a promoted labeller exist (step 13). Idea 42 is no longer item 8 (decision 11). **From 8b** (owner, 2026-11-07): one idea-52 arm (the top-disagreement positions of an independent pair, deep-labelled and oversampled, at equal data), and every retrain keeps one from-scratch run as the independent committee member. **Candidate gate (owner, 2026-11-07):** a retrain's candidate goes to its STC SPRT on a fixed-node screen against the default (the same architecture, so no speed adjustment), not on an offline validation-loss margin |
| Threat inputs (S512cl, idea 41) | **held by the speed gate** (0.195 of S512r2's nps, recomputed per evaluation); speed work in order: incremental updates, 8-bit rows with clipping-aware training, fewer features; its own update cost measured when its turn comes **2026-11-07 (owner, think tank; DESIGN §6):** **S512cl's speed work dropped** (decision 20: full-width contact rows cannot reach 0.90x by arithmetic, and its table would be DRAM-bound at TCEC); threat inputs parked. |
| Idea 40's structure system | L1 (a pawn-and-king network cached by structure key): after S512+PP's evidence. L2 (tables): the pawn drift table's LTC was undecided (not adopted; the owner decides whether the further tables go ahead); the pawn-structure history is built in batch 4. L3 (root planner), L4 (teaching targets), L5 (proof set): planned; the two gates (near-tie frequency at the root, L1's signal against results) are measured first **2026-11-07 (owner, think tank; DESIGN §6):** **L1 and L2 dropped; L3 parked** (kept in ideas.md); L4 handled by the decisive-share pilot and the result-weight arm; L5 becomes the blind-spot suite (decision 20). |
| QAT (idea 44) | `--qat` built; its validation plan written; not yet run (with the next training session) **2026-11-07 (owner, think tank; DESIGN §6):** the validation session is **retired** (decision 20); `--qat` stays for int8 designs; adaptive rounding of the output layer (R25) instead. |
| Idea 46 (threat knowledge at low speed cost) | approved as ranked: the speed-to-Elo measurement first (after ProbCut), then the attack-map pricing and the residual study (cheap kill tests), then distillation from S512+X with auxiliary threat targets (one Kaggle session; a fixed-node screen, then STC), threat-class output heads, the gated evaluation's oracle, the danger vector, column-restricted exposure rows, the structure-keyed delta cache, threat-keyed correction tables, the stand-pat check **2026-11-07 (owner, think tank; DESIGN §6):** **distillation from S512+X dropped** (refuted) and the threat-keyed correction table dropped; threat inputs (ranks 3-5) parked; the residual study is redone against deep labels (X7); attack-map pricing folded into the zero-row build (X12); the speed-to-Elo measurement redesigned (decision 7). |
| S512+X | an LTC candidate at low priority (+25.67 fixed nodes, H0 at STC at 0.818 nps) **2026-11-07 (owner, think tank; DESIGN §6):** **dropped as an LTC candidate**, AF-S likewise (decision 20: the speed price barely falls from STC to LTC). |

**Search**

| item | status (2026-11-06) |
|---|---|
| Tier 2, batch 3 | rising RFP: H0 (off). Threat-aware ordering (cheaper-attacker): **H0 (off)**, −6.08 ± 3.59 after 12,800 games (sprt-log). **2026-11-10 (owner):** the any-attack set (never SPRTed; it lost only offline) gets its first game test on r8btd90, queued after root-gap (tier2/threat-any, switch off; night item 63). **2026-11-11: H1 at STC (+7.49 ± 4.89, 6,400 games) and LTC (+8.07 ± 5.15, 4,992 games): adopted** on phase-4 (adopt/t56-any, `UseThreatBuckets` on; decisions log). ProbCut (9 / 5 / 80): **H0 (off)**, −5.29 ± 3.58 after 12,800 games on S512r2 (sprt-log); no retest (the owner's rule after S512+PP's promotion) **2026-11-07 (owner, think tank; DESIGN §6):** ProbCut keeps its rule: no retest, at LTC either (decision 25). **2026-11-11 (owner, 3:10 PM EST):** that rule lifted for one LTC-only design R test on the tuned search (try 1 of 2): **H1, +9.40 ± 5.03 Elo after 4,992 games: adopted** on phase-4 (`UseCaptureProbe` on; decisions log). |
| Tier 2, batch 4 | built behind switches with placeholders (tier2/batch4, bench unchanged): razoring, quiet history pruning, bad-capture futility, fifty-move eval scaling (a placeholder, ClockDampingSpan 200, its formula an exact Berserk match: measured first on a wide pre-declared grid not centred on the current values, the measured result kept and any remaining match credited; owner, 2026-11-06), the history malus balance, double extensions, node types with their LMR uses, the pawn-structure history, upcoming-repetition detection; each gets its constants from a short SPRT ladder, then its constant screen and STC SPRT (the streamlined standard, owner, 2026-11-06). **The fifty-move scaling's measurement is done (2026-11-06, on S512r2): every span lost to "off"** (best, ClockDampingSpan 800, gain −0.199 [−0.219, −0.179]; the loss shrinks toward "off" as the span grows), by about five times the interval's width, so the bias rule's SPRT of the best non-off setting does not apply: **it stays off, with no retest** (owner, 2026-11-06) **2026-11-07 (owner, think tank; DESIGN §6):** **redesigned** (decisions 2, 3, 20): design R SPRTs with head-to-head constants and at most two tries per idea, in order step 12's order; razoring and bad-capture futility demoted to SPSA dimensions or filler; the history malus balance becomes an SPSA parameter. **2026-11-11 (owner):** the structure history at weight 5 (R21) **capped undecided at STC, +2.93 ± 3.46** after 8 stages (12,800 games, LLR 1.33): not passed, **no retry**; cut-node (R4, CutNodeLmrPlies 1) **H1 at STC, +6.02 ± 3.67** (11,200 games, LLR 4.20), its LTC confirmation b4-cut-node-ltc running, **pre-approved for adoption if it passes**. **2026-11-11: cut-node's LTC H1, +9.75 ± 5.14** (4,992 games, LLR 3.79, 7:59 AM EST): **adopted** on phase-4 (adopt/cut-node, `UseCutNodeLmr` on, CutNodeLmrPlies 1). Batch 4 is closed: cut-node adopted, structure not passed, history-skip dropped, razoring and bad-capture futility as final-retune SPSA dimensions, PV-trace deferred to the re-validation, fifty-move scaling off (measured), the malus balance an SPSA parameter; double extensions and upcoming-repetition detection stay on tier2/b4 behind their switches, not ported. |
| Further correction tables | non-pawn per side, minor, continuation, threat, material: **deferred to the gated items, after the SPSA retune** (owner, 2026-11-06); the pawn drift table stays off (undecided at LTC) **2026-11-07 (owner, think tank; DESIGN §6):** the material, major and threat tables are **dropped** (decision 20); non-pawn (king-inclusive) and continuation keys get a passive ranking, then the best key at LTC (step 16). |
| Continuation histories in LMR (idea 42) | planned (KB T58); measured and SPRTed like the LMR history term **2026-11-07 (owner, think tank; DESIGN §6):** **folded into the round-once LMR step** (R20) as its variant, run only if the centred history term passes (decision 11). |
| Fractional depth (idea 43) | designed (plan only); a search refactor before the SPSA retune **2026-11-07 (owner, think tank; DESIGN §6):** **shrunk** to round-once LMR arithmetic (R20); the full refactor is out of Phase 4 and no longer precedes the SPSA retune (decision 20). |
| The re-validation queue | recorded above; idle filler only, never ahead of new work (owner, 2026-11-06) **2026-11-07 (owner, think tank; DESIGN §6):** shrunk (above). |
| The full re-validation (§5.2, Quality control 6) | owed at Phase 4's end: every search feature switched off in turn, SPRT [−3, 0]; switches folded into plain code only after it **2026-11-07 (owner, think tank; DESIGN §6):** **replaced by a factorial removal round** (R30, with the skeptic's four fixes; decision 6), order step 18; accepted: about a 23% chance of removing a +3 nElo feature. |
| SPSA retune | owed: every eval-dependent margin and the Phase 3 margins (RfpMargin 40 among the candidates), at STC, then at LTC; after the search changes settle **2026-11-07 (owner, think tank; DESIGN §6):** **split** (decision 4): an early pass on the eight eval-dependent margins at STC (step 11) and a final retune by scaling class plus a VLTC spot check (step 19); time-management parameters and the eval scale never in SPSA. |
| Time management: node share + best-move stability | **moved from Phase 5 into Phase 4** (owner, 2026-11-07, decision 1), order step 10, on the LTC list; base allocation, the time curve and a TCEC-ratio control stay in Phase 5 |
| Cut-node negative extension (R40) | counts as a **new idea**, not a retest of the rejected negative extension (decision 26); at LTC in step 12; `use_negative_extension` stays until it is tested |

**Speed**

| item | status (2026-11-06) |
|---|---|
| The default engine's speed sprint | round 1: +4.0% (C4, committed 5ba7d0d); C1 parked for TCEC's x86-64-v4 builds; C2, C3 not kept. Round 2 (a refresh cache for mirror-frame changes −5.3%, a SIMD `select_best` +1.0%, both perspectives in one pass −0.6%, the last two together −0.2%): nothing kept (archive/sprint-candidates-2). Cumulative: +4.0% **2026-11-07 (owner, think tank; DESIGN §6):** C1 un-parked for the TCEC build and the native data-generation build (decision 9); speed sprint 3 at quiet windows under a 1% cycles-per-node rule, and a change slower locally is adopted if it is faster on the runners and in the TCEC build (decision 8); BOLT (idea 21) dropped, idea 36 closed (decision 20). **Sprint 3 (2026-11-12):** the accumulator update in register tiles (nnue-fused, b3b1f5c), +14.7% nps on x86-64-v3 and +5.4% on the native AVX-512 build, bench identical (docs/history/phase-4/perf-log.md); +9.0% on GCC 11.4 through update.sh. Window 2 kept nothing else: int8 feature-transformer rows (I4) -0.9% (no SPRT, below the 3% bar), the AVX-512 output layer +2.1% and the snapshot refresh +1.1%, both within the noise; x86-64-v3 is at least as fast as native for PGO builds (native -1.5%, within the noise; ideas.md 167-169). The search core (profile: move selection 13.2%, TT 7.4%, move generation 7.3%, SEE 4.8%, make/unmake 3.7%, gives_check 0.7%): captures generation that visits only the king squares and pawns able to add a move, adopted under the 1% cycles-per-node rule (+2.9% cycles per node on x86-64-v3, +2.4% on x86-64-v4; nps +2.7% / +2.5%, under the nps rule's 3% floor); SEE with an incrementally kept attacker set dropped (nothing on top of it); TT layout and digest notes left to step 17a (ideas.md 171). |
| The speed-to-Elo measurement | a throttled 0.5x test-only build, 2 STC stages plus 1 LTC stage, speed ratios measured in situ on the runners (decision 7), order step 9; the gate priced at 1.5 Elo per 1% nps until then (decision 8); **since 2026-11-09 priced at 1.72 Elo per 1% nps (1.56-1.88)**, the in-situ refit of the transfer-testing report (§6.2) |
| The TCEC build | x86-64-v4 with C1's AVX-512BW output layer behind a startup CPU check, PGO by default with a fallback, the compiler by measurement; VNNI out until TCEC answers; to ask TCEC: a launcher, and VNNI on both servers (decision 9); the build matrix runs at g3g's seal (step 7) |

**Idea 23**: the harness is built (tools/evolve/); the long run on the label-and-sweep
proxy is replaced by a capped pilot with a game-based fitness (R38; owner, 2026-11-07, decision 19), order step 20.

**Final steps**

| item | status |
|---|---|
| LTC confirmations owed | **2026-11-08 (owner): three owed, queued after the SPSA early pass, one at a time: singular extension (T27, STC +14.12 ± 6.55), multi-cut (T28, STC +9.19 ± 4.62) and the take history (T11, STC +4.53 ± 2.99), each adopted on STC alone although on the straight-to-LTC list; each on against off at 40+0.4, non-regression bounds [−3, 0] (IIR's form). No LTC retest for the ungated negative extension (T30, H0 at STC); R40's gated form stays the planned new idea. Idea 59's screens take priority over the SPSA and these LTCs at stage boundaries.** Before 2026-11-08 this row read: none outstanding today (IIR confirmed); LTC confirmations only for the LTC-sensitive list (Testing setup; owner, 2026-11-06), so of the queued items only batch 4's double extensions and its TT-PV use go to LTC; the pawn drift table stays off (undecided at LTC; owner, 2026-11-06) **2026-11-07 (owner, think tank; DESIGN §6):** plus a VLTC spot check of the final retune's output (decision 21). |
| Final gauntlet | after the last adoption (GitHub's gauntlet workflow, as milestone 1's) **2026-11-07 (owner, think tank; DESIGN §6):** plays the TCEC build (decision 9). S512ppr2's gauntlet: **3488.2 ± 22.2** (2026-11-07, run 42392526865; S512r2's was 3445.8 ± 21.6). |
| Audit-2 and its fixes | not started (an audit in audit-1's form after the last search and network change) |
| Phase-end checklist (CLAUDE.md), merge to main, tag `phase-4`, summary | at the end |

**The order** (owner, 2026-11-07: replaces the 2026-11-06 order, whose
items 1-3 and 7 were done; from the Phase 4 think tank,
docs/research/phase4-think-tank/phase-c-synthesis.md §6, where the R and X
identifiers are defined; estimates UNVERIFIED). Lanes: **G** GitHub (one
run at a time), **K** Kaggle, **L** local CPU (shared with data generation,
one heavy job at a time), **E** engineering. Stage = one STC stage of 1,600
games; an LTC stage counts as 4.

| # | step | lane | when / depends on | estimate |
|---|---|---|---|---|
| done | S512ppr2's gauntlet (3488.2 ± 22.2, run 42392526865) | G | 2026-11-07 | done |
| 1 | Cheap measurements: search counters (X1), in-game history magnitudes and the LMR-history branch's nps (X2), the node-share fit (X6), the decision ledger's RFP and futility rows (X10); the 2026-09 book's duplicate count | L | now, on the threads freed by data generation's cut to 6 (owner, 2026-11-07), one at a time | 6-10 CPU-h |
| 2 | Design R tooling (two tries per idea, head-to-head constants; X5) | E | now | 0.5 day |
| 3 | The anneal attribution and the two-seed weight average (X4) | K, G | now | 0.5 GPU-h, 1 stage |
| 4 | The tier-2 block check (X9), as filler | G | while GitHub is idle | 2 stages |
| 5 | The deep relabel (X7), then the decisive-share pilot (X11) | L | after step 1 | about 3 h on 2 threads |
| 6 | The throttle and zero-row build (X12); the runner speed A/B job (X3) | E, G | now | 1.5-2.5 days |
| 7 | **g3g's seal**: done early (stopped 12:16 PM EST 2026-11-07; owner); g3h follows on 6 threads. The quiet-window work (the TCEC build matrix R11, C1 for data generation, the zero-row timings) moves to the next planned pause of data generation; the 2026-09 book at the next part boundary | L | a planned pause | 2-4 quiet hours |
| 8 | **Item 8a** (the integrity/recall gate, at most 15 of 900 misjudged: its positions are slice positions, bug review T1, so it catches missing or corrupted slice data; named so 2026-11-12), then the STC SPRT [0, 5]; the optional high-WDL branch. **Done** (2026-11-07): S512ppr3 (R1-avg) passed the fixed-node tie-break (+15.65 ± 9.26) and the STC SPRT (+7.12 ± 4.53, H1 after 8,000 games) and was promoted (owner); the high-WDL branch not run | K, G | after g3g's seal, manifest and upload: the evening of 2026-11-07 or 2026-11-08 | 5-7 GPU-h, 1-3 stages |
| 9 | The throttled speed-to-Elo measurement (X8: 2 STC + 1 LTC stages) | G | after step 6 | about 6 stage-equivalents |
| 10 | **Node-share time management + best-move stability** (R8). **Done** (2026-11-08): variant (b) beat (a) head to head (+22.75 ± 12.04 nElo) and passed design R against off at STC (+18.69 ± 7.18 Elo) and LTC (+10.23 ± 5.14 Elo); adopted into phase-4 (owner) | E, G | after the node-share fit (AUC at least 0.70) | 2 days, about 22 stage-equivalents |
| 11 | The SPSA driver (X18), then the **early SPSA** of the eight margins (R14) | E, G | after the decision ledger's ranges | 2-3 days, about 29 stage-equivalents |
| 12 | Search features under design R, adoptions bundled into one part switch per day: R7 → R20 → R4 → R6 → R12 → R16 → R15 → R17 → R10 → R18 → R13 → R29 → R21 → R22; at LTC: R41, R40 (a new idea), R28 | E, G | interleaved with steps 10-11 | about 40 GitHub-hours |
| 13 | Retrains 8b and 8c by the cadence rule; **decide the endgame-start slice (R32) after 8a's result** | K, G | at least 150 M new kept positions | about 5 GPU-h each |
| 14 | The network screen (searched loss X15, the output-expert probe R26, the family screen R36), then at most one input family | L, K, G | after steps 5-7 | 3-10 days |
| 15 | Speed sprint 3 at quiet windows (R9, R19, R23; R31 on runner evidence) | E, L | after X1, X3, X13 | 4-6 days |
| 16 | Correction tables: passive ranking, then the best key at LTC (R34). **2026-11-11 (owner, 3:10 PM EST: "Build R34's non-pawn correction tables plus E4's minor/major/threat tables, then the planned passive ranking and SPRTs of the best")**: built as the drift tables on tier2/corr-tables (every switch off, bench unchanged); passive ranking (tools/measure/drift_rank.py, declared in tier2/corr-tables 201277c before the run): 120 of r8b-rft-stc's games (seed 20261111, 7,943 test-engine positions) replayed at 200,000 nodes by a stats build with every table learning and none applied, X10's ledger at 1 in 512 (818,437 RFP and 228,064 futility rows, 58,297,740 learning nodes). Decision-accuracy gain G (right minus wrong flipped prune decisions per 1,000 ledger rows; 95% bootstrap over games): **threat +17.95 [+16.11, +19.54], minor +14.44 [+12.56, +16.23], major +9.82 [+8.47, +11.07], pieces +7.51 [+6.60, +8.43]**; every neighbouring pair separated (paired 95% intervals above 0), so no tail-fitness swap. Tail fitness (raw error over 100 cp): threat 0.711, minor 0.707, major 0.753, pieces 0.769. Every table's gain is at RFP (+10.3 to +24.5); at futility rows every table loses (−2.6 to −5.5 per 1,000 futility rows). Report-only LTC proxy (the first 60 games at 1,000,000 nodes): the same order, threat +21.67, minor +18.52, major +13.81, pieces +11.40. The summed fitness (0.73-0.80) is not comparable with the pawn drift's 0.919: here the learning nodes are chosen by the raw eval's error direction, there by the drifted estimate's. **Test order (owner, 2026-11-11: the ranking orders the tests only, it drops no table): threat, minor, major, pieces**, each a design R STC SPRT against off (tier2/corr-tables 2992817) at its share's natural value 64 (the whole learned drift), and only if that fails a retry at 32 (half; try 2), with no head-to-head (owner, 7:45 PM EST: the shares are final-retune SPSA dimensions; a pass is adopted, pre-approved, and its share joins the final retune), night queue lane A items 19-corr-a to 19-corr-h, gated on state/gate-e1.done (owner, 6:40 PM EST: after E1's fix has had its SPRT; the commits may need rebasing onto the then phase-4 head). **2026-11-12: threat H0 at 64 and at 32 (both tries); minor H0 at 64, then H1 at 32 (+5.57 ± 4.01 Elo, 9,600 games): the minor table adopted at `MinorDriftShare` 32** (decisions log, 2026-11-12). The owner's table rule: if several tables pass alone, only the best is adopted and the next-best is tested on top of it; major and pieces remain | L, G | after the early SPSA | about 24 stage-equivalents |
| 17 | The structure-class calibration scale (R33: fitted on SPRT games, adopted on fresh games) | L, G | after 8a | 4-8 stages |
| 17a | **Minimal Lazy SMP** (owner, 2026-11-11, after the engineering review; docs/research/engineering-review-2026-11-11.md W1): the next major engineering item after the current queue, **ahead of the removal round (18) and the final retune (19)**, so both are decided on the search that will play. Tests per the review: bench parity at Threads=1, the TSan suites, a scaling curve (nps and time-to-depth against threads), 2-vs-1 and 8-vs-4 thread matches. **Revisit here the pair tables' colour fold** (archive/speed4-pair-fold, owner 2026-11-13: keep the tag, measure memory and nps at TCEC thread counts; docs/research/tcec-hardware-test-plan.md entry 2) | E, G | after the current queue | not costed |
| 18 | The factorial removal round (R30; design docs/research/phase4-designs/factorial-removal-round.md). **Owner, 2026-11-09:** a switch is removed if its estimate is at or below 0 nElo ("estimate <= 0", subject to the combined guard); the tooling (per-shard rows, the factorial and guard kinds, the fit) is built when this step comes up | G | after step 12 | 22-32 stages |
| 19 | The final retune by scaling class (R24) + a VLTC spot check (design docs/research/phase4-designs/final-retune.md). **Ranges widened (owner, 2026-11-09; applied in src/tune/params.hpp, defaults unchanged):** RfpMargin lowest 30 (was 40), LmpQuietAllowance 3 (6), FutilityOffset 30 (50), FutilityGrowth 25 (35), SingularMarginPerPly 2 (3), SingularMinDepth 3 (4), LmrMinMove 1 (2), LmpMaxDepth 1 (2); NoMoveReduceMinDepth highest 16 (10), ReplyWeight 12 (8; its int16 headroom checked), NullSurplusPliesMax 6 (4). Why: the SPSA keeps theta at least c inside its range, so its floor is `lowest + c`; in spsa-r14-m2 RfpMargin sat at that floor (55) from iteration 4 and LmpQuietAllowance (7.7) for the last 6 updates, gradients still pushing down. `spsa.py report` now flags a parameter pinned at a bound. The VLTC check passes by a non-regression rule: the 2-stage nElo estimate at or above −3 | G | after step 18 | about 25 h |
| 20 | Idea 23's capped pilot with a game-based fitness (R38) | L, G | after steps 12 and 19 | about 25 h local, 10-15 stages |
| 21 | The close: the final gauntlet on the TCEC build, the deep-search sanitizer audit (X20), the extended endgame test (X19), audit-2 and its fixes, the phase-end checklist, merge to main, tag, summary; a note that every Phase 4 Elo figure is 1-thread | all | the end | 3-4 days |

Parked: idea 40's L3 root planner. ProbCut: no retest, except one LTC-only
design R test on the tuned search (owner, 2026-11-11; idea 73). Totals (UNVERIFIED):
about 350 STC-equivalent GitHub stages and about 3-4 weeks; engineering
days are the binding resource. The 2026-11-06 order is in git history
(a24d41f).

**Step 10, built behind switches (2026-11-07, branch tm/node-share; owner).**
After each finished iteration of a timed search the soft check compares
against `scaled_soft_ms(soft, hard, soft_scale_permille(...))`
(src/search/time_budget.*): the soft limit times Fork's fitted chance that
the best move changes within the next two iterations, over the typical
chance at that depth, times a mean-spend balance, at least 360 per mille,
never above the hard limit. Variant (a), `UseStabilityTime`: stability
alone (finished iterations in a row with the same best move). Variant (b),
`UseStabilityTime` and `UseShareTime`: stability and the best move's share
of every aspiration pass's root nodes (`RootEntry::nodes_all_passes`; the
LMR context's last-pass share is untouched). `UseShareTime` alone does
nothing. Not scaled: below depth 8, mate and tablebase scores, `go
movetime` (soft equal to hard), pondering, and every search without a soft
limit (bench, data generation). Integer fixed point only. Both switches
are off: bench is unchanged, and the switch-off identity was checked on
timed searches with the node clock (`FORK_NODE_CLOCK`, a test-only CMake
option: elapsed time = nodes / 1000 ms): the 46 bench positions under
five conditions (8+0.08 and 60+0.6 clocks, movestogo 5, a 300 ms clock,
movetime 200), 230 searches, gave output identical to the seam-only commit
with the switches off and with `UseShareTime` alone (the two new option
lines of the tuning build's `uci` reply aside); with (a) on, 122 of the 230
searches changed, with (b) 129, and no movetime search. Constants:
"Search constants" (all placeholders from X6, awaiting the constant
screen). Prediction, recorded before any game: Spearman ρ² of the scale
against the label 0.069 (a) and 0.074 (b), about +3 to +4 Elo at STC by
§5.7's reading of M5's table (UNVERIFIED); R8's 0.5-2x method check
applies. Next: the head-to-head of (a) against (b) (branches tm/a and
tm/b; the declared value is (a)), then the winner under design R at STC
and at LTC. Limit: at TCEC depths the normaliser holds at depth 19 (Phase 5
owns the TCEC curve). The constant screen passed every fitted value; the
first stability cap (10) matched other engines' caps in role and was
replaced by the cap derived from X6 by the owner's declared rule (72),
with every coefficient and balance refitted.

**Step 10, adopted (2026-11-08; owner).** The head-to-head picked (b)
(+22.75 ± 12.04 nElo over (a), 3,200 games), and (b) against off passed
design R at STC (+18.69 ± 7.18 Elo, 3,200 games) and at LTC 40+0.4 (+10.23
± 5.14 Elo, 4,992 games, no time losses); Phase 4 SPRT log. By the owner's
rule (adopt into phase-4 only after LTC passes) tm/b was merged:
`UseStabilityTime` and `UseShareTime` now default to on, and both stay
switches until the Phase 4 re-validation. Bench is unchanged (bench has no
soft limit), and data generation is node-limited, so the labeller is
untouched.

### 5.7 Phase 4 step 1: measurement instrumentation (owner-approved 2026-11-07)

Decision (owner-approved 2026-11-07; recorded here rather than in §6 so the
section merges cleanly): X1, X2, X6 and X10 built behind FORK_SEARCH_STATS,
the `clang-stats` preset in CMakePresets.json only, drivers and analyses in
`tools/measure/`; every new name screened against the four engines before
use (three generic matches: Keep, evaluations, measure); X2 and X10 on
disjoint games, with the Syzygy 3-4-5 tables; X10 at 1 in 512 (accepted by
the orchestrator, 2026-11-07, see the settings table).

The think tank's cheapest measurements (research/phase4-think-tank,
phase-c-synthesis.md §2.2 and §2.4: X1, X2, X6, X10), built as
measurement-only code. **Normal builds are unchanged:** every engine line is
inside `#ifdef FORK_SEARCH_STATS` (or an always-compiled helper that no
normal build calls), so each commit keeps bench (14,626,377 /
9e43990217b0886d) on every preset, and the release presets' `.text` is
compared before and after. The stats build itself must search the same
tree: the preset `clang-stats` (CMakePresets.json only; not in build.sh or
CI, orchestrator's ruling 2026-11-07) runs bench_parity and the
`search_stats` suite (tests/test_search_stats.cpp, compiled only there).
The engine reads its report switches from environment variables once, at
start-up: `FORK_STATS_REPORT` (a cumulative counter dump after each search),
`FORK_ITERATION_TRACE` (one line per finished iteration), `FORK_PRUNE_LEDGER`
(the decision ledger's sampling rate). Line formats:
`tools/measure/engine_lines.py`. No allocation or exceptions in the
recursion, even in stats builds; the dump's lines are integers only.

**X1, search and accumulator counters.** `SearchCounters` became one
X-macro list, `FORK_SEARCH_COUNTERS`, so the dump cannot miss a counter
(the earlier `stats:` lines of `fork bench` keep their text; the summary
moved to `src/search/stats_report.cpp`). New: root and main-search nodes
(with the quiescence nodes they sum to the node count), static evaluations
computed, taken from the TT entry, or not needed (in check), in the main
and quiescence searches and at the ply limit, and pawn moves among the
moves made. The feature stack keeps a `FeatureStackTally` (stats builds
only; `forknnue` gets the define too, so every user of accumulator.hpp sees
one layout): evaluations, pushes, perspective updates, rows per update
(`delta_row_count`, the same columns the update uses), link updates, frame
and root refreshes, and the plies an evaluation walks. Report:
`tools/measure/search_counters_report.py x1` on a stats bench's stderr
(`FORK_STATS_REPORT=1 fork bench`) or on a replay folder (§X2).

**X2, in-game history magnitudes.** History and the TT persist across a
game's moves, while bench clears them per position, so the measurement
replays Fork's own games: `tools/measure/game_replay.py` starts one engine
per game, sends `ucinewgame` once, and searches every position where the
SPRT PGN's "test" engine was to move, in order, with `go nodes N`
(tools/drift_measure.py's method, rewritten). At each LMR site the stats
build histograms the move's ordering score (`quiet_order_score`, the
selector's formula as a function, the definition of branch
sprt/lmr-history; a test on every preset checks it orders quiets as the
selector does) and the raw butterfly, reply and follow entries; at late
captures (every LMR gate but "quiet": R18's sites) the take entry. It
counts where the LMR history term of sprt/lmr-history (the base reduction
less the ordering score / 24,000) would act, on which side, and where it
would change the reduction. Report: `search_counters_report.py x2` per
game-move band against the stats bench, with the declared readings in its
docstring.

**X6, the node-share fit.** With `FORK_ITERATION_TRACE` the stats build
prints one `iteration_trace` row per finished iteration: the best move, its
per mille of the last aspiration pass's root nodes (the share the engine
already computes) and of every pass's (`RootEntry::nodes_all_passes`), the
largest other share, the nodes, the score, the passes, the root moves and
the deepest ply. `tools/measure/node_share_fit.py` fits "the best move
changes within the next two iterations" by logistic regression on the
share's logit, stability, the score change and the depth, and reports AUC,
the partial R² of the share and Spearman's rho², with the declared
readings in its docstring.

**X10, the decision ledger (RFP and futility rows).** With
`FORK_PRUNE_LEDGER=N` the stats build samples 1 in N of the candidates of
RFP and of futility (every condition but the margin) by the position's
key (`key % N`, the key's low bits; the TT indexes by its high bits), and
searches the sampled node again with that technique switched at that node
only (`LedgerForce`, read through `FORK_STAT_GATE`, which is empty in
normal builds): RFP off (wrong if that search fails low), futility on and
off (wrong if on fails low and off fails high). The side search
(`ledger_side_search`) is invisible to the real search: the node count, the
limits (a static unlimited quota; the stop flag still ends it), the TT
(`TransTable::set_hold_writes`), the histories (`record_cutoff` returns),
the counters and the feature-stack tally are all restored, and bench with
the ledger on equals bench.ref (tests; removing any one of the three
guards fails them). Rows: `prune_ledger` lines; analysis:
`tools/measure/prune_ledger_fit.py` (I1's probit with a tail floor, by
depth, with the declared reading in its docstring).

**Idea 59 step 1, evaluations near the window** (owner's request,
2026-11-07, for the Boundary Refiner's gate). At each static evaluation the
stats build records the gap between the evaluation and the nearest finite
bound of the node's window (`window_gap`; a bound in the mate or tablebase
band does not count, and a site with no finite bound is counted apart),
separately for main-search and quiescence evaluations, for computed ones
(the network runs) and ones reused from the TT entry, and for the main
search by depth band. `search_counters_report.py gap` gives the share of
evaluations within 10, 25, 50 and 100 cp and the call rate per node.

**Crucial-point ground truth** (owner's request, 2026-11-07, the gate for
ideas 59 and 60). With `FORK_EVAL_SITES=N,M` the stats build prints every
Nth main-search and every Mth quiescence evaluation site (computed or
reused from the TT; counter-based, deterministic) with its FEN, window,
static and TT-refined evaluation, depth, ply, the parent's evaluation, the
TT entry and the last move's capture flag (`print_eval_site`; the FEN is a
string, built only at sampled sites, as FORK_SINGULAR_PROBE does).
`tools/measure/crucial_points.py` deep-searches every site with a finite
bound with the default engine, evaluates it with other networks (R-int),
labels it crucial when the static evaluation and the deep value fall on
opposite sides of the nearest finite bound, and scores detectors by recall
against the call rate per node, main search and quiescence apart.

**Measurement settings** (they change no play; each is recorded here and
in its code comment, as the orchestrator asked on 2026-11-07):

| Setting | Value | Reason |
|---|---|---|
| Counter dump | cumulative, per search | bench sums 46 positions in one searcher; a cumulative dump needs no reset, and the reader takes differences |
| Table-value bins | 250, sign-magnitude, 82 bins | a fortieth of HistoryMax per side resolves the quantiles; sign-magnitude edges make shares at multiples of the width exact |
| Ordering-score bins | 500, sign-magnitude, 132 bins | 24,000 (the term's divisor) is the 48th edge, so the share where the term acts is exact |
| `LmrHistoryProbeDivisor` | 24,000 | the value sprt/lmr-history tested (7d94d93), the thing measured; the search never reads it |
| X2 games | 100 from `~/fork-data/sprt/s512ppr2-stc` (seed 20261107), "test" engine's positions | the current default network's own STC games; 100 games give a game-level bootstrap |
| X2 node budgets | 200,000 and 1,000,000 per move | 200k is the drift measurement's and the ledger proposal's STC proxy; 1M shows the drift toward LTC, where more nodes per move age history further |
| Replay engine options | Hash 16, Threads 1, Syzygy 3-4-5 | as the replayed SPRT games were played (sprt.yml's default Hash, run_shard.sh's tables) |
| X6 positions | 60 games (seed 20261108, disjoint from X2's), at most 35 test-engine positions each, about 2,100 | the think tank's 2,000 positions; consecutive positions of a game keep the in-game TT and history R8 would act in |
| X6 node budget | 2,000,000 per move | the think tank's choice: deep enough (depth 18-22) that the depth >= 8 rows span the iterations where STC and LTC soft-limit decisions are taken |
| X6 fit | depth >= 8 primary; share clipped to [0.005, 0.995]; stability capped at 10; score change clipped at 500 cp; ridge 1e-6 | the soft limit is never checked before depth 8 at STC; the clips keep the logit and log finite and stop rare extremes dominating; the ridge only guards a singular system |
| X6 bootstrap | 300 rounds over games, seed 20261108 | each round refits the model twice per share definition in pure Python; 300 keeps that to minutes while the interval ends move by well under their width |
| X10 sampling | 1 in 512 candidates (`FORK_PRUNE_LEDGER=512`) | the design's 1 in 32 (I1) was tried on bench first: 1 in 8 gave 578,079 rows and made bench 17x slower, so 1 in 32 would give about 10 M rows over the X10 games, far beyond I1's need of about 60,000 sampled nodes near the margin per depth; 1 in 512 gives enough (893,987 rows in the run). Correction after the run: the side searches cost only 0.8% extra nodes (about 14 per sampled candidate); the slowdown was the rows' unbuffered output, so the rate is set by the row count, not by the side searches (changed before any run, accepted by the orchestrator 2026-11-07; uniform sampling keeps every row's weight exact) |
| X10 games and budget | 120 games (seed 20261109, disjoint from X2's and X6's), every test-engine position, 200,000 nodes | I1's cheapest first experiment (120 STC games at 200k) |
| X10 gap bins | 20 cp for rates, 10 cp for the fit | 20 cp resolves the margin's neighbourhood (RFP's margin grows 80 cp per ply); the finer fit bins lose little to binning |
| X10 bootstrap | 200 rounds for the margin rate, 50 for the fitted sigma, seed 20261109 | the sigma rounds each refit by Nelder-Mead in pure Python |
| X10 arm score clamp | +-2,000 cp, mate and tablebase arms flagged | only the side of beta matters; the clamp keeps the rows integer and short |
| Idea 59 gap bins | 1 cp to 255, 64 cp to 4,095, one overflow bin (317) | every margin up to 255 cp counts exactly (the owner's 10, 25, 50, 100 among them); the coarse bins keep the tail's shape |
| Idea 59 window | the node's alpha and beta at the evaluation (main search: after mate distance pruning) | the window a gate would compare against at that moment; mate and tablebase bounds give no gate |
| Idea 59 depth bands | 1, 2, 3-4, 5-7, 8+ | the pruning depths (1-6) apart from the deep nodes, each band with enough sites |
| Idea 59 games and budgets | 100 games (seed 20261110, disjoint from X2's, X6's and X10's), the test engine's positions (at most 80 per game), 200,000 and 1,000,000 nodes | as X2's arms, so the call rates are comparable with X1's in-game evaluations per node |
| Crucial-point sampling | every 140,000th main-search and every 170,000th quiescence site, 100 games (seed 20261111, disjoint from X2's, X6's, X10's and idea 59's), 200,000 nodes, at most 80 positions per game | about 3,000 sites per stratum; the smoke run's crucial rate of about 10% gives about 300 crucial sites each, enough for the ROC points at 2-10% of nodes |
| Crucial-point deep value | 1,000,000 nodes, one thread, Hash 16, `ucinewgame` per site, the default engine (bench checked) | the owner's budget; a fresh hash per site keeps sites independent |
| Seed networks | scratch seeds 1 and 2 and warm seed 2 of item 7's retrain, converted at S = 89, through R-int | the owner's choice; R-int gives the engine's values (checked: 50 of 50 equal for scratch seed 1), and the warm seed fails the engine's int16 load check |
| Detector folds | two halves by a CRC-32 of the game id; logistic ridge 1e-3 on standardised features | each half is scored by the model fitted on the other; the ridge keeps rare features from separating |
| Replay processes | at most 2, below-normal priority, through jobctl (kind `measure`) | the machine is shared with data generation (orchestrator, 2026-11-07); node limits make results independent of load |

**Results, X1** (2026-11-07; stats build 68c00b8, S512ppr2; bench in the
cleared state, and in game from X2's replays of 100 games, 6,172 searches).

| Number | Bench (46 positions) | In game, 200k nodes | In game, 1M nodes |
|---|---|---|---|
| Nodes | 14,626,377 | 1,230,631,040 | 6,149,834,610 |
| Evaluations per node | 0.657 | 0.538 | 0.543 |
| ... main / quiescence | 0.181 / 0.476 | 0.151 / 0.387 | 0.172 / 0.371 |
| Quiescence share of nodes / of evaluations | 61.1% / 72.4% | 55.9% / 72.0% | 53.7% / 68.3% |
| TT-eval hit rate, main / quiescence | 43.9% / 2.0% | 52.1% / 3.6% | 47.5% / 3.7% |
| Pawn moves among moves made | 24.2% | 16.1% | 16.1% |
| Rows per network update | 3.10 | 2.82 | 2.79 |
| Refreshes per 1,000 updates (almost all king frame changes) | 11.2 | 16.2 | 16.6 |
| Plies walked per evaluation | 1.17 | 1.21 | 1.20 |
| Link-update share (S512+PP's pawn links) | 33.6% | 26.9% | 26.6% |
| Pushes ever evaluated | 66.0% | 54.1% | 54.7% |

Readings against the declared ones: evaluations per node 0.54-0.66, under
the predicted 0.75-0.85 and under the 0.6 refutation line in game, so the
prediction is refuted and evaluation skipping has a lower ceiling than
assumed; quiescence evaluations are 68-72% of all evaluations, far above
the 30% line, so the quiescence eval-avoidance ideas stay open.

**Results, X2** (2026-11-07; stats build 68c00b8; 100 games of
`s512ppr2-stc`, seed 20261107, 6,172 test-engine searches per arm, Hash 16,
Syzygy 3-4-5; median PGN depth of the replayed moves 15; the replays'
own depths were not recorded in this run). Share of LMR sites where the
LMR history term of sprt/lmr-history would act (|ordering score| >=
24,000), with 95% intervals over games:

| Game moves | 200k nodes | 1M nodes |
|---|---|---|
| 1-15 | 0.0015% [0.0010, 0.0020] | 0.0074% [0.0059, 0.0090] |
| 16-29 | 0.0016% [0.0010, 0.0025] | 0.0065% [0.0053, 0.0078] |
| 30-60 | 0.039% [0.006, 0.105] | 0.086% [0.021, 0.211] |
| 61+ | 0.064% [0.014, 0.157] | 0.154% [0.066, 0.304] |
| all | 0.032% [0.008, 0.069] | 0.075% [0.030, 0.140] |
| bench (cleared per position) | 0.0019% | 0.0019% |

- In game at moves 30-60 the share is 20.8x the bench's at 200k and 45.5x
  at 1M: over the declared 5x line, so **history persistence is
  confirmed** (R16's per-go scaling comes before R20 and R29). History
  grows through a game: the butterfly entry's 95th percentile at LMR sites
  rises from 1,875 (moves 1-15) to 4,375 (61+) at 200k and to 5,625 at 1M
  (bench: 875); the take history at late captures sits near saturation in
  game (median 6,875-8,375 of 10,000 at moves 30+; bench 375).
- **B14's prediction is refuted:** it expected at least 85% of the term's
  firings on the reduce-more side; essentially all are on the reduce-less
  side (200k: 0 of the firings reduce more; 1M: 0.1%). Ordering scores
  reach +24,000 (good moves with all three tables high) but almost never
  -24,000.
- The term acts at well under 0.2% of LMR sites in every band and changes
  the reduction at about the same rate, so its firing alone is unlikely to
  explain the -10.8 Elo (UNVERIFIED); the declared alternative, its cost
  (the ordering score computed at every LMR site), is the next thing to
  measure (its nps, not part of this step).

**Results, X6** (2026-11-07; stats build 9e01f26; 60 games of
`s512ppr2-stc`, seed 20261108, disjoint from X2's; 2,086 test-engine
searches at 2M nodes, TT and history carried; 18,782 rows at depth >= 8,
33,384 at every depth; 95% intervals over games, 300 rounds).

| Depth >= 8 (primary) | `share` (last pass) | `share_all` (every pass) |
|---|---|---|
| AUC of the full model | 0.768 [0.748, 0.786] | 0.772 [0.753, 0.789] |
| Out-of-sample AUC (2 folds by game) | 0.767 | 0.771 |
| AUC of the share alone | 0.643 | 0.667 |
| McFadden pseudo-R² | 0.138 | 0.142 |
| Partial R² of the share | 0.0031 [0.0006, 0.0071] | 0.0077 [0.0040, 0.0130] |
| Partial R² of stability / of the score change | 0.062 / 0.001 | 0.054 / 0.001 |
| Spearman rho² of the share | 0.028 [0.019, 0.038] | 0.038 [0.028, 0.048] |

- Base rate: the best move changes within two iterations at 12.9% of
  depth >= 8 iterations (21.0% at every depth).
- P(change) by `share_all` decile (depth >= 8), from the lowest share to
  the highest: 0.229, 0.223, 0.192, 0.162, 0.130, 0.105, 0.088, 0.075,
  0.057, 0.034 (shares below 22%: 0.229; above 95.5%: 0.034). By stability
  quintile: 0.308 (1-2 iterations unchanged), 0.170, 0.098, 0.050, 0.021
  (13 or more).
- Declared reading: the primary definition is `share_all` (the higher
  AUC); its rho² is 0.038, above the 0.03 kill line, so R8's share term
  goes ahead to its SPRT, though narrowly (the interval reaches 0.028, and
  the engine's existing last-pass `share` gives 0.028, under the line; R8
  should use the every-pass share). M5's table puts rho²·CV² of about
  0.04 near +3 Elo (interpolated, UNVERIFIED). Stability carries several
  times the share's information (partial R² 0.054 against 0.008), so the
  stability signal, which S1 held in reserve, deserves its own term; the
  score change adds almost nothing at depth >= 8.

**X6's time-management curve** (2026-11-07; `tools/measure/tm_curve.py`
on X6's runs; §5.6 step 10, R8, built behind switches on tm/node-share).
The owner's two variants, (a) stability alone and (b) stability with the
every-pass share, each as Fork's own logistic fit with depth added and
divided by the depth-only fit (depth normalises, no signal of its own:
owner, 2026-11-07), scaled by a mean-spend balance, floor 360 per mille.
**The stability cap** follows the owner's rule, declared before it was
computed (2026-11-07): the 99th percentile of the stability count over
the rows at depth >= 8, the smallest integer whose cumulative share
reaches 99%: **72** (X6's first cap of 10 matched other engines' caps in
role at the constant screen and was replaced; every fit below uses 72).

| Fit (depth >= 8, 18,782 rows) | Coefficients (logit) | AUC / out of sample |
|---|---|---|
| (a) stability + depth | 0.534912, −0.207666, −0.096556 | 0.765 / 0.763 |
| (b) stability + share_all logit + depth | 0.474586, −0.177596, −0.185073, −0.103338 | 0.771 / 0.770 |
| depth alone (the normaliser) | 0.567490, −0.211730 | 0.665 / 0.665 |
| literal (a): stability alone | −0.455439, −0.224471 | 0.757 / 0.756 |
| literal (b): stability + share_all logit | −0.569350, −0.199212, −0.173797 | 0.764 / 0.763 |

- Depth cap 19 (the last depth with at least 1% of the rows).
- Mean-spend balance (X6's 2,086 searches replayed with nodes as the clock
  under the engine's stop rules, bisected so the mean spend equals the plain
  soft limit's) at 100k / 250k / 500k-node soft budgets: (a) 1.018 / 0.988
  / 1.083, mean **1.030**; (b) 0.996 / 0.954 / 1.038, mean **0.996**. The
  literal fits drift with the budget: 1.036 / 1.216 / 1.580 (a) and 1.013 /
  1.167 / 1.463 (b), which is why depth normalises. The floor binds at
  about a quarter of the rows (23% a, 24% b).
- At that balance the move at the stop equals the 2M-node final move more
  often: at 250k, 0.854 plain, 0.873 (a), 0.874 (b) (in sample, not Elo; at
  500k the variants reach the data's 2M-node end more often, which flatters
  them).
- Spearman ρ² of the scale against the label: 0.069 (a), 0.074 (b); by the
  reading above (M5's table, interpolated, UNVERIFIED) about +3 to +4 Elo
  at STC for either, declared before any game.

**Results, X10** (2026-11-07; stats build 9e01f26; 120 games of
`s512ppr2-stc`, seed 20261109, disjoint from X2's and X6's; 7,876
test-engine searches at 200k nodes; 1 in 512 candidates sampled: 893,987
rows; the side searches took 0.8% extra nodes, about 14 per sampled
candidate). Wrong rate = share of decisions where the prune is wrong (RFP:
the node fails low with RFP off there; futility: the on arm fails low and
the off arm fails high). "At the margin" = the 20 cp gap bin holding the
current margin, with its wrong events / rows and a 95% interval over games.

| Technique, depth | Margin | Prunes taken: wrong | Candidates not taken: wrong | At the margin |
|---|---|---|---|---|
| RFP 1 | 80 | 0.24% (609 / 255,215) | 5.5% | 0.49% (166 / 33,795) [0.37, 0.61] |
| RFP 2 | 160 | 0.38% (232 / 61,457) | 5.0% | 0.72% (35 / 4,869) [0.41, 1.07] |
| RFP 3 | 240 | 0.16% (49 / 30,745) | 3.7% | 0.12% (3 / 2,578) |
| RFP 4 | 320 | 0.17% (25 / 14,690) | 3.2% | 0.09% (1 / 1,079) |
| RFP 5 | 400 | 0.24% (15 / 6,371) | 2.8% | 0.24% (1 / 416) |
| RFP 6 | 480 | 0.06% (2 / 3,488) | 3.4% | 0.60% (1 / 166) |
| Futility 1 | 170 | 0.010% (3 / 29,460) | 5.7% | 0 / 2,797 |
| Futility 2 | 240 | 0.024% (2 / 8,446) | 6.3% | 1 / 774 |
| Futility 3 | 310 | 0.029% (1 / 3,443) | 3.3% | 0 / 354 |
| Futility 4 | 380 | 0 / 2,048 | 3.4% | 0 / 166 |
| Futility 5 | 450 | 0.17% (1 / 601) | 3.7% | 0 / 35 |
| Futility 6 | 520 | 0 / 484 | 2.1% | 0 / 27 |

- Declared reading (I1): the marginal RFP wrong rate falls at least 3x
  from depth 1 to depth 5. Measured 2.0x (0.49% to 0.24%), but the depth-5
  cell rests on one wrong event and every cell from depth 3 on has at
  most three, so the prediction is **neither confirmed nor refuted**
  (thin; I1 asked about 1,200 wrong events per depth, and only depth 1
  has more than 100 at the margin). A run with more games, or one that
  samples only near the margins, would settle it.
- Futility's margins look conservative: the prunes it takes are wrong at
  0.01-0.03% at depths 1-4, against 0.16-0.38% for RFP's, and no
  margin-bin cell has more than one wrong event. That is evidence for
  R14's ranges (room to lower futility's margins), not for any level.
- I1's probit-with-floor model is poorly identified on these data: its
  sigma is pinned only at RFP depth 1 (83 cp [75, 90]) and futility depths
  1, 3 and 4 (247, 155, 105 cp); elsewhere the intervals span orders of
  magnitude. The binned rates above (and the CSV of all rows, outside the
  repository) are the result to use; the fitted curves are not.

**Results, idea 59 step 1** (2026-11-07; stats build d7de27b; 100 games
of `s512ppr2-stc`, seed 20261110, disjoint from X2's, X6's and X10's;
6,523 test-engine positions, at most 80 per game; 200k and 1M nodes).
Computed evaluations within the margin of the nearest finite window bound:
the share of that kind's evaluations, then the call rate per node.

| Margin | Main, 200k | Quiescence, 200k | Main + quiescence per node, 200k | Main, 1M | Quiescence, 1M | Per node, 1M |
|---|---|---|---|---|---|---|
| 10 cp | 4.2% / 0.62% | 6.1% / 2.30% | 2.9% | 3.7% / 0.64% | 5.6% / 2.02% | 2.7% |
| 25 cp | 10.1% / 1.48% | 14.8% / 5.58% | 7.1% | 8.9% / 1.52% | 13.6% / 4.90% | 6.4% |
| 50 cp | 19.4% / 2.87% | 29.4% / 11.06% | 13.9% | 17.5% / 2.98% | 27.1% / 9.79% | 12.8% |
| 100 cp | 34.8% / 5.14% | 51.9% / 19.54% | 24.7% | 32.4% / 5.52% | 49.2% / 17.79% | 23.3% |

- Evaluations per node: 0.524 at 200k (main 0.147, quiescence 0.377) and
  0.533 at 1M (0.171, 0.362), as X1 found. Median gap: main 172 cp (181 at
  1M), quiescence 94 cp (100).
- No finite bound at the site: main 0.9% (1.2% at 1M), quiescence 1.3%
  (2.0%); one finite bound only: about 0% (the windows are zero-width
  almost everywhere, or both mate-bounded).
- Main search by depth (200k; within 25 cp; share of the band / call rate
  per node): depth 1, 11.9% / 1.17%; depth 2, 8.5% / 0.21%; 3-4, 4.9% /
  0.09%; 5-7, 2.4% / 0.01%; 8+, 0.9% / 0.00%. Depth 1 holds two thirds of
  the main search's computed evaluations; deeper nodes sit far from their
  windows (median gap 129 cp at depth 1, 544 cp at depth 8+).
- Evaluations reused from the TT entry (not counted above) lie closer to
  the window: main 20.9%, quiescence 48.6% within 25 cp at 200k, at 0.169
  and 0.015 per node. A gate that also refines reused evaluations would
  add up to 3.5% + 0.7% of nodes at 25 cp.
- Against the idea's cost model (a 2-5% call rate of evaluations costs
  under 5% of nps): only margins near 10 cp give 2-5% of evaluations
  overall (main 4.2%, quiescence 6.1%); 25 cp already reaches 10-15%.
  Two margins, as the owner asked, read off the table: e.g. m_main = 25 cp
  with m_qs = 10 cp gives about 1.5% + 2.3% = 3.8% of nodes.

**Results, crucial-point ground truth** (2026-11-07; stats build 63a7275
for the sites, the normal build for the deep values; 100 games of
`s512ppr2-stc`, seed 20261111, disjoint from X2's, X6's, X10's and idea
59's; 5,433 sites (2,673 main search, 2,760 quiescence; 5,368 with a
finite bound), each searched to 1,000,000 nodes). **18.6% of sites are
crucial** in both strata (498 main, 514 quiescence): the static evaluation
and the deep value fall on opposite sides of the nearest finite bound.
Sites per node: main 0.317, quiescence 0.397 (computed and reused). Recall
of crucial sites at a call rate of 2 / 4 / 7 / 10% of nodes (a detector
calling at random gets the call rate over the sites per node: 6 / 13 / 22
/ 32% in the main search, 5 / 10 / 18 / 25% in quiescence); the logistic
models are scored on the half of the games they were not fitted on.

| Detector | Main search: recall at 2 / 4 / 7 / 10% (AUC) | Quiescence: recall at 2 / 4 / 7 / 10% (AUC) |
|---|---|---|
| Logistic: gap + all features + seeds | 0.20 / 0.34 / 0.51 / 0.62 (0.756) | 0.15 / 0.26 / 0.41 / 0.50 (0.723) |
| Logistic: gap + features, no seeds | 0.20 / 0.34 / 0.50 / 0.60 (0.744) | 0.15 / 0.26 / 0.40 / 0.49 (0.715) |
| Window gap alone | 0.17 / 0.30 / 0.45 / 0.52 (0.674) | 0.14 / 0.25 / 0.37 / 0.45 (0.663) |
| Seed disagreement minus gap | 0.16 / 0.30 / 0.45 / 0.55 (0.686) | 0.12 / 0.22 / 0.37 / 0.47 (0.668) |
| TT refinement \|refined - static\| | 0.19 / 0.34 / 0.44 / 0.50 (0.648) | (none in quiescence) |
| Seed disagreement, scratch seeds | 0.11 / 0.16 / 0.28 / 0.37 (0.544) | 0.07 / 0.12 / 0.20 / 0.28 (0.521) |
| Seed disagreement, default vs warm seed | 0.06 / 0.13 / 0.22 / 0.30 (0.484) | 0.05 / 0.11 / 0.18 / 0.25 (0.497) |
| Hanging pieces | 0.05 / 0.11 / 0.21 / 0.30 (0.481) | 0.08 / 0.13 / 0.23 / 0.33 (0.568) |
| Last move a capture | 0.09 / 0.19 / 0.29 / 0.38 (0.546) | 0.06 / 0.12 / 0.22 / 0.31 (0.552) |
| Swing from the parent's evaluation | 0.12 / 0.19 / 0.26 / 0.35 (0.491) | 0.07 / 0.14 / 0.26 / 0.35 (0.534) |
| Checking moves available | 0.06 / 0.09 / 0.18 / 0.26 (0.447) | 0.06 / 0.11 / 0.20 / 0.27 (0.509) |

- Best detector in both strata: the logistic model on the window gap and
  the simple features (with or without the seed disagreement, which adds
  0.01-0.02 at most). It catches about 3.2x random at 2% of nodes in the
  main search and 3.0x in quiescence, and about 1.9-2.0x at 10%.
- The window gap alone is the best single signal (2.7-2.9x random at 2%).
  In the main search the TT refinement (the TT score moving the static
  evaluation) is as strong at 2-4% of nodes.
- Seed disagreement alone is barely better than random (AUC 0.48-0.54):
  two networks' disagreement does not locate the positions where the
  default network is wrong about the bound.
- For ideas 59 and 60 the gate is therefore the logistic model on the gap
  and features, with its own threshold per stratum; even so, at 4% of
  nodes per stratum it reaches only 34% (main) and 26% (quiescence) of the
  crucial sites.

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
| 2026-10-28 | **Audit-1 Phase C decisions (owner).** B-1 (forced-move stop) ACCEPTED at its cap; B-3 (shallower fail-high re-search) reverted (inconclusive at the cap on [0, 3]); B-2 (table results stored at full depth) reverted (inconclusive at the cap on [-3, 0], its interval never above -3); B-5 (keep-deeper TT rule) stopped, off by default, deferred to Phase 6 (ideas.md idea 30); non-regression SPRTs stop once past 10,000 games with the 95% interval above -3 (Testing setup); perft_epd_full gates CI only when move generation's files change, plus nightly on main. R-3: two positions with room for 16,384 plies reserved at startup, a failed `position` retried once, else no search of the unknown position (`bestmove 0000`). R-4: `go mate N` searches at most 2N - 1 plies. T-6: the TT digest mixed by splitmix64's output function, no SPRT (ORIGINALITY.md). T-13: an SPDX line in every source file. A1 suspicion 8: node limits kept exactly. **F-9 skipped**: merging the two move printers and the two bench reports would touch only cold code (UCI output, `fork bench`), each merge needs new names and their screens, and both printers are now checked by the UCI transcript replay (audit-1 Q-2); revisit when either printer changes. **D-20**: the tag `d8/final` (8b8e34c) is annotated "Deliverable 8 split, variant (c): the iteration rule alone", but the commit holds B2 (the danger-zone reserve) plus (c) (the iteration rule): the variant SPRTed as d8-final and merged as deliverable 8 (sprt-log.md). The pushed tag is not rewritten (owner: no force push); this row is the correct record. |
| 2026-10-28 | **B-4 and RfpMargin (owner).** B-4 (the quiescence stand-pat refined by the TT score) reverted: its STC SPRT accepted H0 (19,200 games, Elo -4.11 +/- 3.93). RfpMargin 40 (was 80) **accepted without an SPRT**, by the owner's decision: its STC run was restarted on a pair without B-4 (8550a78 vs 306bd9a), then stopped in stage 0, and the LTC follow-up was dropped. Its only game data is the superseded run's 3,200 games (with B-4 in both engines: +3.47 +/- 9.61, undecided), so its strength effect is UNVERIFIED; the measured fail-low shares justify the value (Search constants). |
| 2026-10-28 | **Audit-1 Phase D (owner).** Performance gate against main: +2.9% nps at the audit head of the time (not significant; different trees), +3.3% on the same tree (8550a78, significant at the 3.0% threshold), so no slowdown (perf-log.md). Gauntlet against the Milestone C anchors, Milestone C's openings and settings: with RfpMargin 40 stopped after 357 games, 22.5 points below Milestone C on the same games; with RfpMargin 80 (8550a78), all 1,200 games, **Fork 2411.5 ± 22.5** on the Milestone B anchors against 2402.5 ± 23.3 (2416.0 ± 22.2 with Weiss). **RfpMargin reverted to 80** (fd7d4b5; bench 17309921, as main's); 40 logged as untested (ideas.md idea 34). New policy: **untested changes never ship**; a skipped or unfinished test shelves the change and keeps the baseline (Testing setup). Report: history/phase-3/audit-1.md. |
| 2026-10-28 | **Phase 3 closed (owner).** Audit-1 merged into main (PR #5, 80f725e) after its full CI matrix passed (run 40773853691, perft_epd_full included). No new SPRTs. The roadmap changes: tier 2 (deliverable 9) moves into Phase 4, its SPRTs on the GitHub shards beside the local self-play data generation; the end-of-Phase-3 removal round folds into Phase 4's search re-validation after the first network; idea 23's long run stays in late Phase 4. `UseTtEvalRefine` stays on as the owner-approved exception to "untested changes never ship". Summary: history/phase-3/summary.md; tag `phase-3`. Phase 4 starts in a fresh session. |
| 2026-10-28 | **Step 0 screens answered (owner).** B0 stays 768 -> 256 -> 1 as the generic minimal baseline shape (the coincidence with Berserk 6 noted in ORIGINALITY.md); `src/datagen/` kept as community vocabulary; datagen at 20,000 nodes per move, Fork's own measurement (the coincidence with Berserk's OpenBench preset noted); local bullet builds only with a throwaway Cargo folder, training builds only on Kaggle, Fork never vendors or links bullet's GPL/AGPL dependencies (excluding them by Cargo features preferred). Quantization reference corrected to bullet's f64 rule; datagen game cap 500 plies (bullet's 512-record reader limit). |
| 2026-10-28 | **Step 0 spec approved; steps 1-3 reviewed (owner).** §5.3 approved with the answers in its "Owner's answers": no SSD (staging on C:), Kaggle account ready, datagen on 10 of 12 threads, B0's net committed (other nets as Releases), "accumulator" kept if the name screen agrees. Bake-off: the judge's four entries at width 512 on a shared kernel framework, on generation 0 data, STC narrows and LTC decides, time-odds games at STC only, a design-level originality screen for X, G, R, the fitted king regions and AF's threat encoding, a subagent may read bullet's code at the pin, loss thresholds proposed for approval, one net until the pipeline is proven, threat inputs later as an add-on. VNNI on TCEC stays UNVERIFIED (TCEC question list); older KB pages scrubbed of other engines' constants. |
| 2026-10-28 | **QA/QB and the openings month (owner, answering §5.3 question 6).** QA = 255 and QB = 64 stay as bullet's standard quantization convention, recorded in ORIGINALITY.md as a trainer-interface convention credited to bullet, not a tuned constant (so outside the constant screen). The choice of Lichess 2016-09 for datagen openings and the case for a larger or more recent month later are recorded in §5.3, deliverable 1. |
| 2026-10-28 | **Phase 4 started (owner).** The multi-agent plan gains a step 0 requirement: the trainer-engine parity test (the trainer's model against Fork's scalar and every SIMD path, exactly or within the quantization's documented tolerance), passing before any network plays a game and run in CI on every network and inference change. Step 0's spec (§5.3, the baseline network B0 and the whole pipeline, with the Kaggle test session checklist) is written as a draft for review, together with steps 1-3 (research, three designs with divergent briefs, a judge) on branch kb; one batched review stop. The training-data decisions of 2026-10-24 are copied from the KB into §5.3. |
| 2026-10-29 | **B0 adopted; its failing tests fixed, not the engine (owner).** B0 passed its SPRT against the bootstrap evaluation (+486.85 +/- 32.07 Elo, H1 at [0, 5], STC) and is the default evaluator. The TT-equals-minimax tests run their endgames at depth 3, where a full-width walk (repetition_in_tree) finds no repetition in reach; the known path-dependent repetition/TT case (KRK, depth 6) has its own test as tolerated; checks tied to the bootstrap evaluation are made bootstrap-only. Bench re-pinned (tests/bench-b0.ref). |
| 2026-10-29 | **Check relief kept at 1 ply and merged (owner).** LmrCheckRelief is recorded as the minimal reduction unit in Fork's whole-ply LMR, not a tuned constant; the coincidence with Berserk's one-ply relief is noted in ORIGINALITY.md. Its STC SPRT passed (+11.26 +/- 5.54 Elo, [0, 3]). The in-check LMR term (late quiet evasions reduced normally; no constant) passed its own STC SPRT (+4.21 +/- 2.89 Elo, 35,200 games) and is merged too. Both were tested against the bootstrap evaluation, separately. |
| 2026-10-29 | **Quantization-loss thresholds approved for B0-class nets (owner): max 15 cp, p99 12 cp**, revisited for each new architecture (§5.3, answer 11). B0 (11.1 / 8.8) and B0r1 (8.6 / 7.9) pass (`reference.py legs --max-loss 15 --p99-loss 12`). |
| 2026-10-29 | **Delta pruning's margin (owner).** QuiesceGainSlack's 150 cp (branch exp/qs-delta) was chosen after seeing the data (the marginal curve read off the bench measurement; the pre-declared 1% criterion only bounds it from below at 80); recorded as such, and its SPRT decides. |
| 2026-10-29 | **No script prints credentials (owner).** Audit of every committed script and workflow: no secrets in the workflows; the Kaggle kernels read none, and session_check.py reports only three named CUDA variables; the AWS script uses its instance-metadata token only inside a request header; the Kaggle CLI is used only through its own token file and prints only URLs and status. The local session scripts likewise read and print no token. |
| 2026-10-29 | **B0's retrain queued (owner): B0r1.** On all generation-0 data so far (g0s2, worker 9 held out), same architecture, warm-started from B0's weights, early stopping within Kaggle's limit; then the parity chain, netcheck and an STC SPRT against B0 at [0, 5] on the GitHub shards (never beside CI); if it passes it becomes the default and the network for the next data generation. |
| 2026-10-29 | **B0r1 adopted; tablebase result, not material, for a network's quiet choice (owner).** B0r1 passed its SPRT against B0 (+200.24 +/- 16.05 Elo, H1 at [0, 5], STC) and is the default network. Three search tests were fixed for it: determinism clears the history too; the fail-high stop test scans every bench position; in the exchange test a network's move is checked against Syzygy where the material-best move is not forced. Owner's rule: in Syzygy range, accept any move that keeps the tablebase result; otherwise compare the moves with a deep search, and record a real loss as a known weakness of the net, not a test change. The check must be able to fail: K+R+P v K+R with 4 winning and 12 non-winning moves, fault-injected. |
| 2026-10-29 | **Generation 0 stopped, generation 1 started with B0r1; the bake-off trains on generation 1 (owner).** Generation 0 was stopped at 1:42 PM EST and sealed from its complete games: 1,366,657 games, 130,615,808 positions (data/manifests/g0.json, worker 9 held out; g0s1 and g0s2 are byte prefixes of its shards). Generation 1 has the same settings (10 threads, 20,000 nodes, 2-4 random plies per game, 400 cp decided bound, Syzygy 3-4-5, 1 MB hash, Lichess 2016-09 openings) with a new seed (20261030) and fork_datagen from phase-4 bb4f75a (B0r1). The Lichess 2026-09 openings are added when their stream finishes. All bake-off candidates train on the same generation-1 data. |
| 2026-10-30 | **Delta pruning inconclusive, kept off (owner).** Its STC SPRT against B0r1 was stopped undecided after 27,200 games: -0.40 +/- 2.93 Elo, nElo -0.56 +/- 4.13, LLR -1.39 on [0, 3] (history/phase-4/sprt-log.md). Not merged; exp/qs-delta keeps it for the post-network re-validation, with its margin retuned (ideas.md 39). |
| 2026-10-30 | **Openings tool resumable and small (owner).** The 2026-09 stream was stopped for low memory after 6.4 hours (its python held 1.17 GB). `datagen_openings.py` now writes positions straight to a state folder, finds duplicates through 64-bit digests in one table capped at 256 MB, and checkpoints every 2 minutes; the same command resumes (the stream is re-read from its start and the finished games skipped; the re-read prefix must hash as recorded). Lichess 2016-09, killed after 600 s and resumed, reproduced its committed manifest byte for byte at a peak of 57 MB. |
| 2026-10-30 | **Bake-off constants (owner).** AF-S keeps its body (16, 32, 8 stacks, int8 L1 at 64) though the screen found it in Stockfish 14-18; S-512 takes H-512's phase octiles instead of piece-count buckets; XGR stores 3 side lanes (§5.4; ORIGINALITY.md). |
| 2026-10-30 | **B0r2 is the default network (owner's standing instruction, §5.4 games plan item 0).** The bake-off's B0 control (B0's shape on g1s1) beat B0r1 at STC on [0, 5]: +235.45 +/- 16.04 Elo, H1 after 1,600 games. It becomes `nets/b0r2.fnet` with its parity file and bench reference (14,589,665 / 9dba694dd1ee4c41) and generation 1's labeller from then on (docs/nets.md); one search test made evaluator-independent. **H-512 plays as trained (owner)**: its gap is overfitting (§5.4), the pre-registered plan is unchanged, and king regions are retested with much more data in the winner's full-size confirmation, a hand-drawn map with the castled squares together included (judgement.md §5, row 5). |
| 2026-10-30 | **Generation 1 switched to B0r2 (owner's standing instruction).** The B0r1 run was stopped at 1:45 PM EST and sealed from its complete games: 1,717,530 games, 171,297,909 positions (data/manifests/g1.json, worker 9 held out; g1s1's shards are byte prefixes of its shards, checked). The rest of the 200 M target, 28,702,091 positions, comes from run g1b: fork_datagen from phase-4 ac2ce91 (B0r2, bench checked), generation 1's settings with a new seed (20261031), started at 1:46 PM EST. The Lichess 2026-09 openings are still added when their stream finishes. |
| 2026-10-30 | **Each labelling net's data stays apart (owner).** Generation 1's two parts keep separate manifests: g1.json (B0r1) and g1b.json (B0r2, sealed when g1b finishes), never merged, so training can tell them apart. fork_datagen's run manifest now names the network (`"evaluator": "nnue (b0r2)"`; before, only "nnue"), checked by datagen_verify; g1b's binary predates this, so its seal sets the field. **check.sh full's TCEC leg** compared each TCEC binary's bench with tests/bench.ref (the bootstrap evaluation's) and so failed whenever a network is the default; it now calls .github/ci/bench-parity.sh as CI does (the net's reference and perft bench), and passed with gcc 11.4, g++-12, clang 16 and clang 19. |
| 2026-10-30 | **Generation 2 and the standing labeller policy (owner).** After generation 1 (g1 + g1b) and the WSL restart that applies `.wslconfig` (6 GB cap, gradual memory reclaim), generation 2 starts as run g2: labelled by B0r2, generation 1's settings, seed 20261101, target 500 M positions; the Lichess 2026-09 openings are added when their stream finishes. **Labeller policy** (§5.3, deliverable 2): whenever a new network is promoted, the running generation stops at a game boundary, the part so far is sealed with its labelling network recorded, and the generation continues as a new part (g2b, ...) labelled by the new default; parts are never merged. **One naming scheme (owner)**: a part ends for any reason (a new labelling net or new openings), the next part takes the next letter, and each manifest records its labelling network, openings file and why the part ended (`part_end`, required by `upload_batch.py seal`, which also refuses a network run that does not name its net; name screened, no match). g1.json gains its reason: B0r2's promotion. |
| 2026-10-30 | **AWS connected; cloud data generation built, not launched (owner).** The owner set up the account (root MFA, a $20 budget alert, a 30-day lifecycle rule, IAM Identity Center with PowerUserAccess for 12 h, an instance role with s3:PutObject on results/ and datagen/ only); AWS CLI v2 is installed in WSL user space (signature checked against the AWS CLI Team key's documented fingerprint) with an SSO profile; account names live only in local untracked settings. Applied spot quota (L-34B43A08, Standard families): 8 vCPU in us-east-2, so everything is sized to one c7a.2xlarge (8 cores, 1 thread per core, 3.7 GHz; spot $0.116-0.133 per hour over three days, about $3 a day). New safeguards in tools/cloud/: `spot_quota.sh` (every launch and dry run checks the applied quota and refuses an excess), `spot_watch.sh` (the spot interruption watcher, now shared; a simulated interruption against a fake IMDSv2 service, fault-injected once), `aws_cleanup.sh` (terminates tagged instances past `fork-expires`), and fork-run / fork-expires tags on instances, volumes and spot requests; aws_spot_sprt.sh uses them and defaults to c7a.2xlarge. Cloud data generation: `aws_spot_datagen.sh` (launcher: one spot instance, x86-64-v4, the commit's default net checked by bench, openings regenerated and checked byte for byte, seeds from 10^12 apart from every local run, a max-hours shutdown), `cloud_datagen.sh` (on the instance: chunks of 1 M positions, each verified, sealed with its labelling net, openings and reason, uploaded to datagen/), `pull_datagen.sh` (at home: download, SHA-256 and game checks, then a private Kaggle dataset); end to end without AWS in `test_cloud_datagen.sh` (CTest `cloud_datagen`, Linux). Names screened, no match. No real launch until the owner says go. |
| 2026-10-30 | **Cloud data generation on any of seven 8-vCPU types (owner).** The first real launch (one c7a.2xlarge spot instance, us-east-2, approved by the owner) found no spot capacity (InsufficientInstanceCapacity; spot placement score 1 of 10 in every zone for c7a.2xlarge and c8a.2xlarge); nothing was created. Data generation is node-limited, so the machine type does not change the data (the one-type rule stays for SPRTs): `aws_spot_datagen.sh` now asks for one spot instance through an instant EC2 Fleet, capacity-optimized-prioritized over c7a, c8a, m7a, c7i, m7i, c6a and c6i (.2xlarge, 8 vCPU; in that order) in every zone, each capped at $0.25 an hour, and checks every type against the spot quota first. The instance picks its build from its CPU flags (x86-64-v4 with AVX-512 F, BW, CD, DQ and VL, else x86-64-v3; no AVX2, BMI2 and FMA: it stops), and `fork version` must report that target; each chunk's sealed manifest records the instance type and CPU model (`machine`), the generator's `arch` being the build. No capacity exits 4, and a local loop retries every 30 minutes for up to 12 hours, stopping at the first launch. Stub test `tools/cloud/test_aws_spot_datagen.sh` (check.sh's tool tests; fault-injected once: a flat priority fails it); the instance-type record is in `test_cloud_datagen.sh`. Both requests this script builds (the launch template and the fleet) were sent to EC2 with `--dry-run`, and EC2 answered that each would have succeeded. Names screened (fleet_config, check_quota, instance_type, max_price, test_aws_spot_datagen): no match; machine and types only as plain words. |
| 2026-10-30 | **S-512 is the default network, provisionally (owner).** In bake-off stage A it beat the B0 control (B0r2) at STC on [0, 5]: +43.66 +/- 12.02 Elo (nElo +62.52 +/- 17.02), H1 after 1,600 games (run 41125906800). It becomes `nets/s512.fnet` (byte-identical to bake/g1s512's net) with its parity record and bench reference (15,249,025 / 13001f412d6e8d7e); one search test made evaluator-independent (docs/nets.md). The bake-off continues unchanged and a later entry that beats it is promoted then. S-512 labels generation 2 from its start (g2 had not begun; its first 6 hours stay arm A of the idea-13 experiment, and arm B uses the same labeller) and the cloud data generation. Its architecture's quantization-loss thresholds are not yet approved: its loss is max 15.6 cp, p99 12.1 cp (proposed: max 21, p99 16). |
| 2026-10-30 | **The datagen options reach the cloud runs.** `cloud_datagen.sh` and `aws_spot_datagen.sh` take `--adjudicate-cp` and `--adjudicate-plies` and hand them to fork_datagen, so a cloud part can use the same score adjudication as the local one; `verify_games.py` reads the adjudication from the run manifest's settings when `--adjudicate` is not given, and `pull_datagen.sh` passes the sealed settings on, so both the instance and the home check verify adjudicated games (a manifest that misstates the rule fails at home: `test_cloud_datagen.sh`). `upload_batch.py seal` carries `positions_unsaved` and `nodes_spent` when a run has them. The manifest key and accessor `nodes_searched` became `nodes_spent` before the first commit: the name screen found the former as an identifier in Stockfish (generic words, but renaming cost nothing; `nodes_spent` and the other option names: no match). |
| 2026-10-30 | **Quantization-loss limits for S-512's architecture (owner): max 21 cp, p99 16 cp.** Set from its first net (S512: 15.6 / 12.1 cp). The rule: limits per architecture leave headroom above the first healthy net's loss, to catch broken conversions, not to rank nets (docs/nets.md, "Quantization-loss limits", which lists every architecture's limits). They are applied with `reference.py legs` when a net is added; no CI job applies them automatically. |
| 2026-10-30 | **The idea-13 experiment, as run (owner).** Both arms are labelled by S-512, use the score adjudication (700 cp for 8 plies) and the same fork_datagen build (chosen at the break); the split search is the only difference. Arm A: generation 2's first 6 hours (normal settings). Arm B: 6 hours as its own part with its own seed, in check 2,000 nodes, other positions saved with probability 0.5 at 20,000 nodes, otherwise 4,000 nodes and not saved. CPU load is logged for both arms. Then nets of B0's shape, two seeds per arm with identical training, the usual parity chain and scale matching, and arm B's best net against arm A's at STC on [0, 5], capped at 20,000 games, after a seed-against-seed match per arm; if it is inconclusive the simpler setting (no split) stays (ideas.md 13). |
| 2026-10-30 | **Generation 1 complete; the score adjudication adopted for generation 2 (owner's rule).** Run g1b (B0r2) reached its target at 5:59 PM EST and is sealed as data/manifests/g1b.json: 286,781 games, 28,702,555 positions in 15,168.5 s (1,892 positions/s), worker 9 held out; part_end "target reached: generation 1's 200 M positions (g1 + g1b)". On all of g1b's games, a win adjudicated once one side scores at least 700 cp for 8 plies in a row ends 65.7% of the games early, 28 of them wrongly (0.015%: 27 were draws, 1 a loss) and saves 9.3% of the positions (on g1's B0r1 data: 20 wrong of about 104,000, 0.02%). The owner's condition was a rate near zero, so generation 2 (local and cloud) runs with `--adjudicate-cp 700 --adjudicate-plies 8`, recorded in every manifest's settings; no draw rule (the measured draw rules misjudge 1-10% of games where they save anything). |
| 2026-10-30 | **Cloud data generation in three regions (owner).** `aws_spot_datagen.sh --region` takes us-east-2, us-east-1 or us-west-2, one 8-vCPU instance per region within that region's own spot quota, and every instance uploads to the bucket in `--bucket-region` (us-east-2; the instance sets AWS_DEFAULT_REGION to it). Applied Standard spot quota (L-34B43A08) before any launch there: 8 vCPU in each of the three (default 5; us-east-2 also has an increase to 32 requested, case open). Dry runs of run-instances with the instance profile and of create-launch-template succeed in all three regions, so the SSO permission set and its iam:PassRole policy already cover them; the bucket has no bucket policy. The instance role's own policy cannot be read with PowerUserAccess (no IAM reads); that it has no region condition was confirmed when the first cross-region chunk (us-west-2, run g2-aws-us-west-2-20261030T233227Z) uploaded to the us-east-2 bucket. Seeds: 10^12 + (4 x launch time + region slot) x 1000 + chunk, the slot 0 / 1 / 2 for us-east-2 / us-east-1 / us-west-2, and cloud_datagen.sh stops a run at 1,000 chunks, so no two runs share a seed even when launched in the same second; the run name carries the region. Tests: the stub test checks each region's slot, name and upload region (fault-injected: a shared slot fails it); three older checks in test_cloud_datagen.sh that tested only their first condition now test both. |
| 2026-10-30 | **Cloud spending guards (owner): a $10 daily cap and a $25 credit floor.** `tools/cloud/cost_guard.sh`, run by `aws_spot_datagen.sh` before anything is created: every launch is recorded in a local ledger (outside the repository) at its worst case, --max-hours at the --max-price cap (12 h at $0.25 = $3), and a launch is refused (exit 5) when the last 24 hours' worst cases plus its own exceed FORK_DAILY_CAP ($10); it is refused (exit 6) when the remaining credits, the balance the owner read on a date (FORK_CREDITS_START, FORK_CREDITS_SINCE) minus the credits Cost Explorer shows applied since, fall below FORK_CREDIT_FLOOR ($25). Running instances always finish. Without a starting balance the credits are reported as unknown and do not block; no API giving the remaining credit balance directly is known here (UNVERIFIED). `cost_guard.sh report` lists the window's launches and the credits, run daily. Stub test `test_cost_guard.sh` (fault-injected: ignoring the new launch's own cost fails it); the launcher's stub test checks the ledger record and a refusal over the cap with nothing created. |
| 2026-10-30 | **Cloud launch rule: expected cost per million positions (owner).** The first measured rates (S-512, 20,000 nodes, adjudication 700/8, x86-64-v4 on 8 vCPU): c8a.2xlarge 2,075 positions/s (median of 18 chunks, 2,046-2,188), c7a.2xlarge 1,640 (2 chunks), so at the spot prices seen c8a costs about $0.015 per million positions and us-west-2's c7a at $0.227/h about $0.038. Rule: each spot pool (a type in a zone) is judged by its current spot price over its type's measured rate (`tools/cloud/datagen-rates.tsv`, keyed by net, nodes and adjudication); `aws_spot_datagen.sh` leaves out pools above `--max-cost-per-m` (default $0.03), above the $0.25/h cap or of a type with no measured rate, and gives the fleet the rest cheapest first (ties in --types order, c8a first by default), each capped at the price where it reaches the limit, so an instance whose price climbs past it is interrupted. No qualifying pool exits 7 with nothing created or recorded. The daily cap and its worst-case booking are unchanged ($0.25/h x 12 h). The five types without a measured rate (m7a, c7i, m7i, c6a, c6i) cannot launch until a rate is recorded for them. Ranking in `tools/cloud/spot_pools.py` (unit tests `test_spot_pools.py`; fault-injected: ranking by hourly price, and no limit check, each fail them), the fleet request and the refusal in the launcher's stub test; dry runs against the live price history in all three regions. Names screened (spot_pools, datagen-rates, load_rates, latest_prices, choose_pools, max-cost-per-m, per_m, refused): no match. |
| 2026-10-31 | **Bake-off amended after stage A (owner; decided after seeing stage A's results, before any stage B game).** Stage A: S-512 H1; H-512, AF-S and XGR-512 H0 against the B0 control. No entry is retrained alone; stage B (fixed nodes, 800,000 per move) decides who stays: an entry stays if its stage B Elo point estimate against the control is above 0 (rule set before any stage B result), otherwise it is dropped, not retrained. Round 2: every remaining entry, S-512 and the B0 control included, retrained on one snapshot of about 500 M positions (generation 2 and the cloud data) with identical settings. XGR's exposure plane, phase gate and revision head become separate add-on experiments to S-512 after round 2 (§5.4, "Amendments after stage A"). |
| 2026-10-31 | **The daily cap counts ended instances at their cost (owner).** A launch stays booked at its worst case ($0.25/h x 12 h) while its instance runs; once the instance has ended (finished, interrupted or terminated), `cost_guard.sh` replaces the booking with its cost: hours run times the spot price paid, each stretch of the run at the price then in effect (`tools/cloud/spot_cost.py`), from the instance's spot request (start, end, type, zone) and the zone's spot price history. `check` and `report` settle first; the launcher records each launch's region and instance. AWS lists closed spot requests only for some hours, so an instance it no longer lists keeps its worst case until `settle RUN COST` sets it by hand. The three launches of 2026-10-30 were settled by hand: us-east-2's c8a $0.73 (6.1 h, from AWS's record), us-west-2's c7a $0.57 (2.5 h, end from its boot log), us-east-1's c7a $0.26 (an upper bound: reclaimed before its first chunk, zone and end unknown, so 1.1 h at the dearest zone's price). Tests: `test_spot_cost.py` and `test_cost_guard.sh` (fault-injected: check without settling, a running instance counted as ended, price changes ignored, and a hand-settled row losing its state on a rewrite each fail them). Names screened (spot_cost, cost_between, settle, booked, paid): no match. |
| 2026-10-31 | **XGR's set-wise exposure adopted for round 2 (owner).** Condition: evaluations exactly identical and faster (§5.4, the engineering task's result). Old build against new, every XGR-512 net (the entry and the raw seeds 1 and 2): netcheck 446 positions, 0 mismatches each; `fork evalfens` byte-identical on 500,005 game positions each; bench 15,540,185 / 9564dc8f27cd9708 on both. Speed: +15.5% median nps (bench/ab_search.py, 10 rounds, datagen paused, the openings stream running at low priority; an A/A run beside it moved -0.4% / +0.9%). Inference only, so round 2's training rules are unaffected. |
| 2026-10-31 | **AWS used as much as needed (owner).** The owner has a budget set and accepts paying it daily, so cloud data generation is no longer held back by cost: the launch rule allows any pool at up to $1 per million positions and a spot price of $0.40/h (was $0.03 and $0.25), the credit floor is 0 (was $25), and the daily cap is raised from $10 to $100 at worst-case booking, kept only as a backstop against a runaway relaunch loop. Each instance still shuts itself down after 12 hours. The binding limit is the applied spot quota, 8 vCPU (one 8-vCPU instance) per region in us-east-2, us-east-1 and us-west-2; increases to 32 were requested for us-east-1 and us-west-2 (us-east-2's has been open since 2026-10-30), and the relaunch watcher fills each region up to its applied quota. The on-demand quota is also 8 vCPU per region (the launcher uses spot only). |
| 2026-10-31 | **A public web page for Fork, planned (owner).** GitHub Pages from a dedicated `site` branch: Fork compiled to WebAssembly (Emscripten, single-threaded, scalar then WASM SIMD, in a Web Worker), checked by netcheck and bench parity under Node before anything is published; a Play tab (chessground, GPL-3.0-or-later), a "Watch it learn" tab (any promoted network, live generation-against-generation games, fixed positions, a progress timeline from a summary JSON the promotion step updates); phones, light and dark, networks loaded on demand, no personal data. Built after round 2 starts, on spare CPU only (§5.5). |
| 2026-10-31 | **The gauntlet moves to GitHub's runners, with stronger anchors (owner).** `.github/workflows/gauntlet.yml` (started by a push to `gauntlet-run`, one run at a time in the GitHub queue): Fork (update.sh, gcc 11.4, x86-64-v3) against the continuity anchors Weiss 1.0 (CCRL Blitz 2896), Stash 19.0 (2473), WyldChess 1.51 (2603) and the new Monolith 2.01 (3061), Winter 0.9 (3168), Laser 1.7 (3292), each built from its official source at a pinned commit (tools/gauntlet/anchors.tsv); Topple 0.8.1 (3036) and Seawall 20250322 (2978) replace a new anchor that does not build. 200 games per anchor at 10+0.1, one thread, Fork's Hash 16 MB, the earlier gauntlets' 200 random 8-ply openings (tools/make_openings.py, seed 20261025, sha256-checked on the runner), each with both colours; 12 shards on ubuntu-latest, each recording its CPU model; Ordo 1.2.6 anchored to CCRL Blitz (list of 2026-10-31). A stronger anchor is added only if Fork scores over about 70% against Laser 1.7 (owner, 2026-10-31): Marvin 6.3.0 (CCRL Blitz 3458, GPL-3.0, tag v6.3.0; its network built in; its book never placed beside the binary), or Arcanum 2.8 (3460, GPL-3.0) if Marvin does not build, in a run started from `gauntlet-strong-run`, which replays the whole gauntlet with it. Every anchor's options come from its own `uci` output: listed options only if it has them, any thread option at 1, any book switch off. |
| 2026-10-31 | **First gauntlet on GitHub's runners: Fork 3325.9 ± 27.4 (Ordo, CCRL Blitz scale).** Run 41232350699, Fork at a38a37d (update.sh, gcc 11.4, x86-64-v3, the default network), 1,200 games at 10+0.1, all 12 shards complete, every game ended normally (no time losses or abnormal endings). Fork scored 965.0/1200 (80%): against Laser 1.7 109.0/200 (54.5%), Winter 0.9 155.0 (77.5%), Monolith 2.01 160.0 (80.0%), Weiss 1.0 168.5 (84.3%), WyldChess 1.51 184.0 (92.0%), Stash 19.0 188.5 (94.3%). Ordo: white advantage 118.0 ± 14.0, draw rate between equal opponents 19.2% ± 1.8. Every primary anchor built; no alternate was used. The shards ran on AMD EPYC 7763 (9 shards), EPYC 9V45, EPYC 9V74 and Xeon Platinum 8573C (one each), 4 cores, 3 games at a time. The rating is on the anchors' CCRL Blitz scale (2'+1" on CCRL's hardware) from 10+0.1 games on these runners, so it is an estimate in that scale, not a CCRL rating. **The strong anchor does not play:** Fork scored 54.5% against Laser 1.7, below the owner's threshold of about 70%. **A second run** (41238458381, at 62ce047: docs only after a38a37d, so the same engine), started at 3:20 PM EST by a queue script left running after it was meant to be stopped (it waited for an idle queue, so nothing overlapped): Fork 3305.3 ± 27.9, 948.5/1200, 56.5% against Laser 1.7, every game normal. Both runs together (Ordo 1.2.6, same settings, 2,400 games): **Fork 3315.6 ± 19.6**, 55.5% against Laser 1.7; both runs played the same 200 openings, so that error bar understates the uncertainty somewhat. |
| 2026-10-31 | **Idea 13 adopted: the split search is the standing data-generation setting (owner).** i13b1 (arm B) beat i13a2 (arm A) by +65.47 ± 12.90 Elo (nElo +88.52 ± 17.02), H1 on [0, 5] after 1,600 games (run 41236941019; seed noise +3.3 ± 12.6 and -14.8 ± 12.4; ideas.md 13). Every new part uses `--save-percent 50 --unsaved-nodes 4000 --check-nodes 2000` with the other settings unchanged. Locally, run g2d was stopped at 3:30:05 PM EST after 19,859 s and sealed (data/manifests/g2d.json: 337,222 games, 30,755,288 positions, every shard passing verify_games.py), and g2e (seed 20261105) started at 3:30:11 PM EST with the split search. In the cloud, the running instances finish their 12-hour runs as launched, and every relaunch passes the three options (`aws_spot_datagen.sh` to `cloud_datagen.sh` to fork_datagen; tests in `test_aws_spot_datagen.sh` and `test_cloud_datagen.sh`). The launcher's cost rule is unchanged: at the same rate of saved positions (arm B 1,641 a second against arm A's 1,637, measured locally), the rates file's positions per second still give the cost per million saved positions (UNVERIFIED on the cloud types until their first split chunks report). |
| 2026-10-31 | **Tier 2 resumes (deliverable 9; owner), in a new order.** One technique at a time, each behind its switch and SPRTed on the GitHub shards with S-512 as the default network, sharing the GitHub queue with round 2 (round 2's games first when they are ready): singular extensions (then multi-cut and negative extensions), continuation histories, capture history, internal iterative reduction, correction history, then razoring, futility pruning of bad captures, upcoming-repetition detection and fifty-move eval scaling. Gainer bounds by expected gain ([0, 5] where a large gain is expected, [0, 3] otherwise). Every constant is justified from Fork's own measurements, with the name and constant screens as usual. Check relief and in-check reductions, SPRTed on the bootstrap evaluation, are tested again with S-512 in the re-validation round. **Singular extension first:** built behind `use_singular_extension`, its SPRT passed (+14.12 ± 6.55 Elo after 4,800 games, [0, 5]; Phase 4 SPRT log) and the switch is on; multi-cut then passed on top of it (+9.19 ± 4.62 Elo after 9,600 games, [0, 3]) and is on (owner: adopted on passing, with the credit note for its textbook form); the negative extension was rejected (−8.73 ± 4.98 Elo after 8,000 games, H0) and stays off; its constants measured (Search constants: 6 cp per ply, minimum depth 6, entry slack 3, test at d / 2, 1-ply extension); the constant screen found the combination close to Stockfish 11's test, kept by the owner with credit (ORIGINALITY.md) and a correction to the margin and depth added as a candidate region for idea 23 (ideas.md). Then T10's reply table (the 1-ply continuation history, `ReplyWeight` 6 quarters, measured) passed on top of both (+11.46 ± 5.57 Elo after 6,400 games, [0, 5]; 2026-11-01) and is on, then the follow table (the 2-ply table, `FollowWeight` 4 quarters, measured) on top of it (+7.22 ± 3.92 Elo after 12,800 games, [0, 3]; 2026-11-01), on too; then T11's take history (capture history, `TakeWeight` 4 thirty-seconds, measured) on top of both (+4.53 ± 2.99 Elo after 22,400 games, [0, 3]; stages 0-12 ended without a verdict and the test ran on to stage 13), on too. |
| 2026-11-01 | **Round 2 of the bake-off set up (owner: the schedule, before training).** Generation 2 ended at 614.8 M saved positions: local parts g2-g2e (g2e, the split search, stopped 9:17 AM EST and sealed) and 8 cloud runs (507 chunks). The snapshot g2s1 (`data/manifests/g2s1.json`): 9,176,386 games, 614,769,222 saved positions for training (415,949,440 kept by the training filter); validation 780 games, the first 60 of a designated shard from each of the 13 sources, interleaved. Refitted on g2s1 by the round-1 rules: S = 92 (fit_scale.py's fit on 2 M positions drawn from every source in proportion to its saved positions; round 1's 105 came from generation 1's data), and the maps (`fit_maps.py`: H-512's and AF-S's king regions, the phase octiles). **Schedule (owner, 2026-11-01, set before any training): round 1's exposure, about 4.3 passes**: 360 superbatches of 5 M positions (1.8 B seen per run), the learning rate dropped tenfold at 180, every other setting as round 1; the five entries (B0 control, S-512, H-512, AF-S, XGR-512), seeds 1 and 2, in two Kaggle sessions (`tools/train/kaggle/bakeoff.py`). |
| 2026-11-01 | **S512r2 promoted; generation 3 begins (owner).** Round 2's S-512 (seed 2, the lower validation loss) was tested before the other round-2 nets were ready (owner): parity chain passed, S = 92 (matched to S512, the opponent; 89 against round 2's B0 control, untested), SPRT against S512 +151.35 +/- 12.50 Elo, H1 at [0, 5] after 1,600 games (run 41349145950). Promoted after the owner's review with exactly the tested scale (docs/nets.md; the other scale would need its own SPRT). Bench 17,904,298 (signature 698205c2870d96a4); one test whose "exact" search still pruned with multi-cut fixed (nets.md). **Labeller policy:** generation 2 had already ended (g2e sealed at 9:17 AM EST, past 500 M), so no local part was running; generation 3 starts as part g3, labelled by S512r2, with g2e's settings (the split search, the Lichess 2016-09 openings) and a new seed, target 500 M; cloud launches label with S512r2 from now on as runs g3-aws-* (each instance builds the pushed phase-4 with its default network). Their launch rule needs a measured rate for the net: S512r2 has S-512's architecture, so its rows in `tools/cloud/datagen-rates.tsv` carry S512's measured rates, marked provisional until its own chunks are measured (the $1 per million cost limit is about 50 times the expected cost). IIR's SPRT, started on S512, was stopped at its first stage and restarts on top of this commit. A gauntlet measures the new strength after round 2. |
| 2026-11-01 | **Round 2 amended (owner; decided before any round-2 game result).** H-512, AF-S and XGR-512 (round-2 seeds by validation loss) each first play a fixed-node match against S512r2, 1,600 games at round 1's stage B conditions (800,000 nodes per move for both); only an entry scoring above S512r2 there (Elo point estimate above 0) proceeds to the STC promotion SPRT against S512r2 on [0, 5]. Reasoning: every entry is slower than S512r2, so failing at equal nodes rules out winning at equal time. Replaces stages A to C for these entries; scale matching to S512r2 (§5.4, "Round 2 amendment"). |
| 2026-11-02 | **Round 2's retest and LTC candidates (owner; decided after the fixed-node results, before any round-2 STC result).** An entry whose fixed-node Elo interval includes 0, or whose STC result is within its error margin of S512r2, is kept as a retest candidate for after the post-network search retune; an entry that beats S512r2 at fixed nodes but fails its STC SPRT is recorded as an LTC / TCEC-conditions candidate, tested later at long time control with an x86-64-v4 build on AWS (§5.4, "Retest and LTC candidates"). Fixed-node results against S512r2: H-512 −12.17 ± 10.58 (interval excludes 0: out, not a candidate), AF-S +10.43 ± 10.36 and XGR-512 +30.70 ± 10.37 (both proceed to STC). |
| 2026-11-02 | **Round 2: an STC SPRT undecided at its cap (owner; decided after AF-S's STC result, before XGR-512's).** An STC SPRT still undecided at its 20,000-game cap counts as not passed (no promotion); the entry qualifies as both an LTC candidate (if it beat S512r2 at fixed nodes) and a retest candidate (an undecided result is within the error margin). AF-S's STC SPRT had already ended in H0 (−55.85 ± 11.42, history/phase-4/sprt-log.md): LTC and retest candidate under the earlier rules (§5.4, "Retest and LTC candidates"). |
| 2026-11-02 | **Internal iterative reduction on (tier 2, T26).** Its STC SPRT on S512r2 passed: +21.45 ± 5.98 Elo (nElo +35.35 ± 9.83) after 4,800 games, H1 on [0, 3] (Phase 4 SPRT log), and `use_no_move_reduction` is on (NoMoveReduceMinDepth 8, measured; kept by the owner with credit). Every bench reference recomputed; S512r2's bench is 14,180,299 (signature 4cf778ff753861f7). Engines built from phase-4 from now on, the cloud's g3-aws data runs among them, search with it; local part g3 keeps its PGO build from 387f338 (each run records its commit). |
| 2026-11-02 | **Gauntlet with the new anchor set: Fork 3445.8 ± 21.6 (Ordo, CCRL Blitz scale; owner).** Run 41465146207, Fork at 3902d00 (S512r2 and every tier-2 feature adopted so far, IIR included; update.sh, gcc 11.4, x86-64-v3), 1,200 games at 10+0.1, the earlier gauntlets' 200 openings, all 12 shards complete, every game ended normally. Anchors (owner, 2026-11-02): Weiss 1.0, Monolith 2.01, Winter 0.9, Laser 1.7, Marvin 6.3.0 (now standing) and, on trial, Altair 7.0.0 (CCRL Blitz 3579, MIT; proposed by the research agent, alternate Clover 6.1); Stash 19.0 and WyldChess 1.51 dropped. Every anchor built, Altair and Marvin included; no alternate was used. Fork scored 823.0/1200 (69%): Altair 64.0/200 (32.0%), Marvin 103.0 (51.5%), Laser 140.0 (70.0%), Winter 164.0 (82.0%), Monolith 177.5 (88.8%), Weiss 174.5 (87.2%). Ordo: white advantage 123.9 ± 10.8, draw rate between equal opponents 25.4% ± 1.8. Shards on AMD EPYC 7763 (5), EPYC 9V74 (4), Xeon 6973P-C (2) and EPYC 9V45 (1), 4 cores, 3 games at a time. The first GitHub gauntlet (a38a37d, 2026-10-31) gave 3315.6 ± 19.6 over two runs, before the singular extension, multi-cut, the reply, follow and take histories, IIR and S512r2; its anchor set differed (Stash and WyldChess in, Marvin and Altair out), so the 130-point difference is the change on two different scales, not a measured gain. As before, a rating in the CCRL Blitz scale from 10+0.1 games on these runners, not a CCRL rating. Results in ~/fork-data/gauntlet/run-41465146207. |
| 2026-11-02 | **The LTC queue and the rest of tier 2 (owner).** LTC tests on GitHub's shards at 40+0.4, Hash 64 MB, x86-64-v3, 1,664-game stages to 9,984 games (the owner's 10,000 cap in whole stages without reusing an opening), in this order: XGR-512 against S512r2 (failed: H0, −30.56 ± 9.96 Elo after 1,664 games; SPRT log), the pawn drift table's SPRT on [0, 3] (T32's first table; straight to LTC per Testing setup), IIR on against off on non-regression bounds [−3, 0] (its LTC confirmation: a reduction adopted on an STC pass; base branch ltc/iir-off), then AF-S against S512r2. The x86-64-v4 half of the TCEC-conditions check waits for the 32-vCPU AWS quota. A passing entry is reported before anything else. **The pawn drift table:** the measurement's first choice sat at its grid's edge, so the owner had the grid extended toward slower learning (declared before its runs, same rule): 256/4 won and was kept with credit (Search constants; ORIGINALITY.md). **LMR history term (T16):** in the base reduction (the table's less the move's ordering history score / LmrHistoryDivisor), not in idea 23's evolvable slot, which stays at 0 so the long run evolves a residual on the improved formula; measured (tools/lmr_history_measure.py, declared before its runs) and SPRTed as usual. **The order after it** (owner's adoption of the inventory of 2026-11-02, each with its own measurement and SPRT): the improving flag one use at a time (RFP, LMP, LMR, the NMP gate); the further correction tables (non-pawn per side, minor, continuation) after the pawn table's LTC result; ProbCut; quiet history pruning; node types, then TT-PV uses; threat-aware move ordering (KB T56, written 2026-11-02); double extensions; fifty-move scaling; pawn-structure history; upcoming repetition; bad-capture futility; the malus balance; razoring; the threat and material correction tables. |
| 2026-11-02 | **AF-S's LTC test dropped; XGR's parts become add-ons to S512r2; the Structure System planned (owner).** AF-S is **shelved, not tested at LTC**: it trailed XGR-512 at fixed nodes (+10.43 against +30.70) and at STC (−55.85 against −34.42), and XGR-512 failed at LTC (−30.56 ± 9.96, H0 after 1,664 games, run 41469160529; SPRT log), so the LTC queue after the pawn drift table is IIR on against off. AF-S stays a retest candidate after the post-network search retune (§5.4). **XGR's parts** (the exposure plane X, the phase gate G, the revision head R) are planned as add-ons to S512r2 (was S-512, 2026-10-31): the exposure plane first, after the current tier-2 queue, with its AVX-512 (x86-64-v4) LTC check when the 32-vCPU AWS quota allows. **The Structure System** (ideas.md idea 40): five layers (a pawns-and-kings network, the pawn correction table and pawn-structure history, a root-only structure planner, training targets, a strategic test set), plan only, built after the current tier-2 queue, behind two measurement gates. |
| 2026-11-02 | **Generation 3's first snapshot g3s1; S512r3 and S512+X trained on Kaggle (owner).** Taken while every generator kept running (Kaggle and light local CPU only; the GitHub slot stays with the LTC queue): the local part g3 as a byte prefix of its running shards (2,299,291 games; each file checked with verify_games, two at a time, beside training: a failure discards the runs before any result is used) and every sealed cloud chunk of the 11 g3-aws runs (471 chunks, each checked against its manifest, verify_games-checked on its instance): 7,321,720 games, 373,842,515 saved positions, all labelled by S512r2 (data/manifests/g3s1.json); trained on together with g2s1 (988,611,737 saved positions). Validation g3s1-val.vf: 60 held-out games from each of the 12 generation-3 sources interleaved with g2s1-val.vf's 13 sources (1,500 games). **S512r3:** S-512's architecture warm-started from S512r2's float weights (a warm start keeps its net's S = 92 and S512r2's phase table), S512r2's settings otherwise (360 superbatches, the drop at 180, the lowest validation loss kept), seeds 1 and 2 (`tools/train/kaggle/retrain.py`). **S512+X** (XGR's exposure plane as an add-on, 2026-11-02 above): architecture 6, S-512 plus the 640 exposure rows and their 10-input factoriser, warm-started from S512r2's weights with the exposure inputs appended as zeros (so it starts at S512r2's exact output), the same settings and seeds; S-512's training rule (no first-layer clip: 608 of S512r2's first-layer weights exceed 0.99, so a clip would move the warm start), with Fork summing the exposure rows in 32 bits so their size needs no bound. Before training, each warm start must reproduce S512r2's validation loss on g2s1-val (0.01945765) and S512+X must pass `fork-train check` and the feature legs against the reference. The first session (2026-11-02) passed all of these (both warm starts at 0.01945765, 0 feature-leg differences on 446 and on 5,000 positions, 27 of 27 shard hashes) and then ended in an error before recording any run: most likely (UNVERIFIED: its logs could not be downloaded) the checkpoint pruning, which counted superbatch 0 and so could delete the best trained checkpoint; fixed, and the session rerun on 2026-11-05. Then the parity chain and scale matching (to S512r2); S512r3's SPRT against S512r2 queues for GitHub; S512+X is tested against whichever of S512r2 and S512r3 is the default then. |
| 2026-11-02 | **The new nets' test order; the new search constants are placeholders (owner).** Each test takes the GitHub slot when it is free: (1) S512r3 against S512r2, STC SPRT on [0, 5], promoted if it passes; (2) S512+X against S512r3 (the same snapshot, warm start and settings, so the exposure plane is the only difference), a fixed-node screen first (the round-2 amendment's: 800,000 nodes per move for both, 1,600 games, an Elo point estimate above 0 proceeds), then an STC SPRT on [0, 5]; if it passes it becomes the default candidate, reviewed by the owner before any promotion. Web v2's build and deploy run only after these and the queued LTC tests leave a free slot. **Constants:** the values written with ProbCut, the improving flag's RFP use and threat-aware ordering (tier2/batch3) are placeholders only, the switches off: they likely come from memory of other engines (the constant screen found ProbCut's depth and reduction matching Berserk and Stockfish in the same role, its margin near Stockfish 18-19's, the relief near Igel's). Before any SPRT each is chosen by a measurement with a rule declared before its runs, on a grid spanning a wide range, not centered on the current value; the measured value is adopted and any remaining coincidence credited in ORIGINALITY.md, as with the singular extension. A placeholder is never shipped unmeasured. |
| 2026-11-05 | **AWS unavailable until further notice: the account is suspended (owner).** The owner reported the AWS account suspended. The same day every AWS process was stopped and the cloud runner disabled: the relaunch watcher (running since 2026-11-01) was stopped, the local cloud settings file every launcher, watcher and report reads was renamed so none can start, a guard was added to the session's AWS scripts, and the daily credit report was cancelled; no AWS login or API call is made until the owner says otherwise. The relaunch log's last readable state (2026-11-02, 2:25 PM EST) showed no fork instance running in us-east-2, us-east-1 or us-west-2, each region's spot quota reading as allowing none from 11:31 AM that day; the login expired on 2026-11-03 at 9:31 AM EST, and from 2026-11-05 a new login was refused (AccessDenied on starting a device authorization), so whether any instance still runs is UNVERIFIED. **Data:** every uploaded chunk of the 19 cloud runs downloaded so far is held locally (each run's uploaded count in its boot log matches its local chunk manifests): generation 2, 8 runs, 507 chunks, 5,528,986 games and 507,219,344 positions, all in g2s1; generation 3, 11 runs, 471 chunks, 5,023,149 games and 471,203,685 positions, all in g3s1; both snapshots are also Kaggle datasets. Held only in S3, so lost while it is unreachable: seven generation-2 runs launched on 2026-11-01 between 9:24 AM and 3:24 PM EST, after the last generation-2 download ($4.29 of instance time; their chunk counts were never recorded, so their size is estimated from the downloaded runs' positions per dollar at about 180 to 270 million positions, 2.0 to 3.0 million games, UNVERIFIED). The other four launches with no local copy (two of generation 2, two of generation 3) wrote nothing to S3: each had ended before a download that copied every run of its generation there. Unaffected: the local generation-3 part g3, which finished at its 500 M target (5,334,231 games, 500,000,697 positions) on 2026-11-03 and was never uploaded, and the Kaggle training (its data are Kaggle datasets and its code comes from GitHub). Data generation continues on the local machine only; the plans that used AWS (x86-64-v4 LTC candidates, AWS SPRT shards) wait. |
| 2026-11-05 | **The labeller policy covers the whole engine (owner).** Data generation always uses the current default engine, its network and every adopted search change, not only the default network (Labeller policy, §5.3 deliverable 2): a promoted network or an adopted search change ends the running part at a game boundary, the part is sealed, and the next part starts from a PGO build of the new default, bench-checked. **Generation 3's parts so far:** g3 (387f338: S512r2, IIR off) reached its 500 M target on 2026-11-03 and now has two verified copies besides WSL's (all of it on C:, and on Kaggle as fork-g3s1's prefix plus fork-g3rest, the games after it, each file checked to rebuild the original byte for byte). g3b started on 2026-11-05 at 3:48:50 PM EST with g3's own binary and settings (seed 20261107) and was stopped at 3:59:54 PM EST under this rule (16,265 games, 1,523,579 positions), since IIR, adopted on 2026-11-02 and confirmed at LTC on 2026-11-03, was missing from it. g3c started at 4:01:03 PM EST from a PGO build of phase-4 at 684bac6 (S512r2, IIR on; bench 14,180,299, signature 4cf778ff753861f7, as tests/bench-s512r2.ref), with g3's settings, seed 20261108 and the rest of the part's 500 M target, 498,476,421 positions; it was stopped at 4:20:49 PM EST (32,585 games, 3,060,039 positions) when the owner cut local data generation to 6 threads while the tier-2 measurements run (next row), and g3d continues with g3c's binary on 6 threads from 4:21:49 PM EST (seed 20261109, target 495,416,382), back to 10 threads as a new part once the measurement queue is empty. |
| 2026-11-05 | **Tier 2 first; the measurement queue; the next batch; the network and search plans (owner).** Tier 2 has priority (the TCEC message and release drafts are skipped for now). **CPU:** local data generation runs on 6 threads while the measurements run (their searches are node-limited, so the load does not bias them), 10 again when the queue is empty, each change a new part under the labeller policy. **Measurement queue**, each with its rule declared before its data on a wide grid not centered on the placeholder, reusing the 25 M-node labels of the LMR measurement: (a) the LMR history term (measured: 24000 chosen, no divisor above "off"; its STC SPRT failed, H0 −10.81 ± 5.01 Elo, not adopted); (b) the improving flag's RFP use; (c) ProbCut's three constants; (d) threat-aware ordering's set, any attack against a cheaper attacker (tools/tier2_measure.py and its specs, tier2/batch3, committed before any run). **SPRTs** on GitHub one at a time as each measurement finishes, the network tests (S512r3) first when ready; when GitHub would sit idle, the re-validation's removal SPRTs as filler (LMR check relief, LMR on late quiet evasions; branches reval/no-check-relief, reval/no-lmr-in-check). **The next batch, built behind switches with placeholders** (tier2/batch4, bench unchanged, each with a test that fails when it is disabled and its names screened): quiet history pruning, node types with a TT-PV use, double extensions, fifty-move scaling, the pawn-structure history, upcoming-repetition detection, bad-capture futility, razoring and the malus balance; each gets its own measurement before any SPRT. **Plans** (kb-researcher's clean-room entries first, every source idea credited in ORIGINALITY.md): a new network architecture, S-512 with Fork's own threat inputs and pawn-pair inputs, **replacing the S512+X plan** (the S512+X runs already in the Kaggle session are kept as records but not tested), trained and tested like the bake-off entries (ideas.md 41; pawn-pair inputs as idea 40's first L1 step); continuation histories as the LMR history term's inputs (idea 42); fractional depth as a search refactor before the SPSA retune (idea 43); QAT in the training pipeline (idea 44). Batch 4's `pawn_key` overlaps tier2/drift's pawn structure key; whichever merges first keeps one key. |
| 2026-11-05 | **The push gate, the SPRT checklist, S512+X as evidence (owner).** **Push gate:** the personal-data scan (`scripts/scan-push.sh`: every added line of every commit the remote lacks, for this machine's user name and home paths read at run time, a private patterns file outside the repository with the email and the cloud identifiers, and credential shapes) runs and passes as its own step before any push, and a hit blocks it; the pre-push hook runs the same scan as a backstop, and `scripts/test_scan_push.sh` (in the quick check) shows a planted hit of each kind stops both. It follows a slip: a scan and its push ran in one command, so the scan did not gate the push (its one hit was a bench signature's digits, nothing personal). **SPRT checklist** (Quality control 5): the test branch's full non-slow suite and the constant screen before committing constants, with the measured-constant, bench, name-screen and scan items. **S512+X:** when GitHub would otherwise sit idle, one fixed-node match of S512+X against S512r2 (800,000 nodes per move, 1,600 games), as evidence for the threat-input plan (ideas.md 41) only; S512+X is not a promotion candidate. **LMR history:** idea 42 (continuation histories in the term) is its follow-up, measured the same way. |
| 2026-11-05 | **S512r3 is not tested; S512+X trains well (owner's rule for the decision).** Kaggle fork-retrain3 version 2 (commit ddd9c57, the checkpoint fix) completed all four runs on g2s1 + g3s1 (360 superbatches, warm-started from S512r2, S = 92). Validation loss on g3s1-val (its first 20,000 kept positions, the trainer's own measure, the same set for every net; the warm-start check's 0.01945765 was on g2s1-val): S512r2 0.01930359; **S512r3** seed 1 0.019348 (superbatch 302), seed 2 0.01933709 (284), both worse (the loss rose to 0.0211 at the first superbatch and never came back below the start); **S512+X** seed 1 0.01891247 (302), seed 2 0.01887023 (303), 2.0-2.2% lower. S512r3 seed 2 went through the chain (S = 90 matched to S512r2 on 4,000 g3s1-val positions; parity legs: trainer leg max 0.00015 cp, quantization loss mean 2.24 cp, max 10.55; netcheck 0 mismatches; bench 14,207,568), but two network-dependent tests failed on its candidate branch (at depth 1 in 4k3/1P6/8/8/8/8/8/4K3 w it plays e1f2, +177, instead of the promotion; the web test's eval threshold), so the SPRT checklist stopped it. **Endgame check** (tools/nnue/endgame_check.py, thresholds declared before the run: a won position misjudged below +100 cp, a lost one above -100, a drawn one beyond +-200; 900 quiet random KPK, KQK and KRK positions, verified with the Syzygy tables): S512r2 misjudges 249 (27.7%), S512r3 329 (36.6%); KQK S512r2 0 of 300, S512r3 41 (14.7% won, 12.7% lost); KRK both badly (S512r2 73-76%, S512r3 87-89%: the data adjudicates such endings by the tables, so the nets hardly see them; the tables cover them in play); KPK level. **The owner's rule** (worse on the like-for-like loss and clearly worse at endgames: skip it and record why) applies: S512r3 is not SPRTed and not promoted; S512r2 stays the default. The warm start at S512r2's learning rate is to be reconsidered before another retrain of the same architecture. S512+X runs its fixed-node evidence match when GitHub is idle (not a promotion candidate). |
| 2026-11-05 | **S512+X: not promoted, an LTC candidate at low priority; the speed gate for new inputs (owner).** S512+X (seed 2, S = 89; bake/s512x c62bb3b) scored +25.67 ± 10.26 at fixed nodes (run 42142711426) and −30.04 ± 10.82 at STC (run 42149140337, H0 after stage 0) against S512r2, at 0.818 of its nps (a quiet 12-round A/B). By §5.4's rule (it beat S512r2 at fixed nodes and failed at STC) it is recorded as an **LTC / TCEC-conditions candidate**, at low priority: XGR-512, the same pattern with a larger fixed-node gain (+30.70), failed at LTC too (−30.56 ± 9.96, H0). S512r2 stays the default. New rule in §5.4: a new input type must keep 0.90 of the default's nps in a quiet fixed-time A/B before it trains; below that it is optimized first. Applied first to S512cl, measured before any Kaggle training. |
| 2026-11-05 | **The job supervisor and the run-ID ledger (owner).** Two SPRT drivers believed stopped (their tool tasks were stopped, which ended only a wrapper shell) kept running: the check-relief filler dispatched stages 7-9 while the rising-RFP driver, waiting for an idle GitHub, never dispatched, and its stage 0 was reported from the filler's run. No result was merged into the wrong SPRT (the driver's meta check), but attribution and process control failed. Built before any SPRT resumes: `tools/jobs/jobctl.py` (one lock per job type; the whole process tree contained, in a Windows Job Object the command joins before it runs, or a POSIX session plus an environment marker; `stop` ends the tree, gently first, and verifies none is left before releasing the lock; the keeper lives until the whole tree has ended, so a descendant outliving its command is still stopped); `tools/jobs/ledger.py` (every dispatched run with its inputs; an after-the-fact attribution goes in as an import with its evidence); `sprt_run.sh` runs only under the supervisor, takes its run by sprt.yml's new run title, records it, and merges only ledger-recorded stages. Tests: tools/jobs/test_jobctl.py (7, Windows and WSL) and tools/github/test_sprt_run.sh (29 checks); planted faults (a root-only kill, the old newest-run rule) fail them. |
| 2026-11-06 | **The reconciliation of two chats' instructions (owner).** Each decision recorded once, here. (1) **S512+PP's speed gate:** trained at 0.90 or more of the default's nps by the identical-tree method, 0.95 the goal reported beside it; revisited after the speed-to-Elo measurement (idea 46); final adoption by SPRT (§5.4). (2) **The speed gate's method:** the identical-tree method (bench rounds, every new-input weight zero) whenever the tree can be held identical; fixed time per position otherwise, e.g. synthetic nets (§5.4). (3) **The SPRT queue:** the threat set (running), then ProbCut (d9-r5-m80, STC [0, 3]; the margin 80 kept with credit, ORIGINALITY.md; the switch stays off until its SPRT passes), then the speed-to-Elo measurement. (4) **Docs-only pull requests** with green CI may be merged without asking (standing rule); PR #8's merge (0e7247b) ratified. (5) **Data generation:** g3e starts on 10 threads as soon as the quiet session of 2026-11-06 ends (the current default engine, the standing settings, a new seed), the measurement queue being empty. (6) **Idea 46's training experiment** (distillation and auxiliary targets): a fixed-node screen first, then STC, as for every new network (its rule 5 amended). (7) **Idea 46's order:** the speed-to-Elo measurement is first among its experiments, after the current SPRT queue. (8) **Performance-only settings** (S512+PP's cache size, prefetch depth): the higher median nps ratio wins, the smaller setting if the difference is within the 3% noise rule; declared before Part A's results were seen. Also: the AVX-512/VNNI output layer (speed sprint C1) is parked, not dropped (the SPRT shards build x86-64-v3 only), to be revisited for TCEC's x86-64-v4 builds; check relief stays on and the filler is closed (undecided at its cap: not passed, so the removal is not accepted). |
| 2026-11-06 | **The re-validation queue and the Phase 4 checklist (owner).** Four network-era retests of bootstrap-era results, recorded as GitHub filler after the current SPRT queue, each STC [0, 3] with S512r2 as the default: B-4 (the TT-refined stand-pat), keeping exact TT entries, B-3 with idea 29, and the root fail-high fix; RfpMargin 40 and every Phase 3 margin go to the SPSA retune. The full Phase 4 checklist, each item's status and a proposed order are in §5.6 (the order awaits the owner's review). |
| 2026-11-06 | **§5.6's order approved, with changes (owner).** Item 7: S512r3's non-improvement is diagnosed first on a shared validation set (warm start against from scratch; the current schedule against a longer one with a lower final LR), then the default is retrained with the winning recipe on the next snapshot, which includes the Syzygy endgame slice (idea 45, lifted from its hold), with the endgame acceptance test. The fifty-move scaling's formula, a placeholder, is measured on a wide grid not centred on it before its SPRT, the result kept and any remaining match credited. The further correction tables are deferred to the gated items, after the SPSA retune; the pawn drift table stays off. B-3 is retested alongside idea 29's measurement. |
| 2026-11-06 | **Item 7 becomes the retrain itself (owner).** The separate S512r3 diagnosis is dropped (archived unrun). The default is retrained on g3s2 with the endgame slice, in the S512+PP architecture only if S512+PP passes an STC SPRT against S512r2, which runs only if its fixed-node screen exceeds about +30 Elo (a screen above zero but below +30: evidence for idea 40 and an LTC candidate, the retrain in plain S-512; clarified by the owner the same day), else plain S-512, never launched before that result; two recipes side by side, two seeds each: a warm start at 0.0001 then the usual drop, and from scratch on the current schedule, scored by the mean best loss on a shared validation set; the better recipe's best seed goes through parity, the endgame acceptance test and its SPRT against S512r2; the recipe result is recorded (§5.6, item 7). |
| 2026-11-06 | **The Fork Control Center, and its decisions (owner).** A Windows desktop window (`tools/control_center/`, tkinter, no other dependencies; launched from a desktop shortcut) over the job supervisors, the SPRTs and GitHub runs, Kaggle training, the networks and gauntlets, the sealed data, the machine and §5.6; everything read-only except data generation: Start (the next part by the labeller policy, through the WSL supervisor), Stop & seal (`jobctl.py stop`, then a seal job that copies the complete games, runs `verify_games.py` and `upload_batch.py seal`, and keeps every file if verification fails), an optional auto-stop, and Windows kept awake while a part runs. Decided: (1) **the disk margin is policy** (§5.3 deliverable 2, "Disk margin"); (2) **the next part (after g3e) starts from a fresh PGO build of phase-4 including 5ba7d0d** (select_best's register change, +4.0% nps, bench identical), as the labeller policy requires for any adopted change, rather than g3e's 684bac6 binary; (3) its test suite joins `scripts/check.sh`'s tool tests (the Python suite in every mode, `test_start_part.sh` on Linux in "all"). A rehearsal re-sealed g3b from WSL into scratch folders with the real verify_games.py: every data field equal to data/manifests/g3b.json. Names screened (ORIGINALITY.md). |
| 2026-11-06 | **Testing streamlined (owner; the new standard, Testing setup).** Search constants for batch 4 and everything after it are chosen by a short SPRT ladder (2-3 sensible values, quick STC tests capped at 2 stages, the best kept), then the feature's normal SPRT; the ladder counts as Fork's own measurement for the originality rule, SPSA refines later; the running fifty-move measurement is finished, batch 4's other declared measurement specs are not run. Seed-noise matches are dropped. The re-validation queue runs only as idle filler. LTC confirmations only for the LTC-sensitive list (Testing setup, "Straight to LTC"); for everything else the STC verdict decides. Kept: SPRTs, parity and netcheck, the endgame acceptance test, data verification before sealing, CI before merges to main, the fixed-node screen for new networks. |
| 2026-11-06 | **S512+PP promoted to the default network (owner).** S512+PP R = 1 (bake/s512pp 412b13f, S = 90) beat S512r2 at STC, +32.67 ± 10.48 Elo, H1 after 1,600 games (run 42294907752), after +46.09 ± 10.37 at fixed nodes (run 42284077960). Promoted the same evening with its recorded exceptions: speed 0.895 of S512r2's nps (below the 0.90 gate) and the endgame check, 351 of 900 misjudged against 249 (KQK 59 of 300), which the Syzygy slice in g3s2 is meant to fix (docs/nets.md). Its two network-dependent search checks were rewritten to hold for any evaluator (the promotion rule). nets/s512pp merged into phase-4 with its inference code (architectures 6-8) and trainer; S512r2 stays buildable and joins CI's `nets` job. Bench 13,909,380 / 831e5c9295839f87. **The labeller policy:** g3e stopped at a game boundary (4:38:18 PM EST, 48,577,036 positions) and sealed as its part; the generation continues as g3f, labelled by S512+PP from a fresh PGO build. **Item 7's** candidate must beat S512+PP. The web page still runs S512r2 until it is redeployed. Tests and measurements based on S512r2 (ProbCut's SPRT, batch 4's fifty-move measurement) keep their S512r2 base; whether to re-run any on S512+PP is the owner's call |
| 2026-11-06 | **S512ppr2 promoted to the default network; the warm start becomes the standard retrain recipe (owner).** Item 7's retrain (S512+PP's architecture on g3s2 with the Syzygy endgame slice): the warm start from S512+PP at LR 0.0001 (mean best loss 0.01909453 on g3s2-val over 2 seeds) beat training from scratch (0.01951758) by about ten times the 4e-5 seed spread, so future retrains warm-start at LR 0.0001 with the usual tenfold drop. Its best seed, S512ppr2 (bake/s512ppr2 d56c2cf, S = 89, 2 of 311,296 link weights clamped), beat S512+PP at STC [0, 5], +20.11 ± 7.22 Elo (nElo +33.60 ± 12.04), H1 after 3,200 games (runs 42335141916, 42336446490), and misjudges 8 of the endgame check's 900 positions against S512+PP's 351 (a recall figure: the check's positions are slice positions; bug review T1, 2026-11-11). Promoted the same evening; S512+PP stays buildable and joins CI's `nets` job; the web page adds S512ppr2 as its default when it is next redeployed. Bench 14,626,377 / 9e43990217b0886d. **The labeller policy:** g3f stopped at a game boundary (11:50 PM EST) and sealed as its part; the generation continues as g3g, labelled by S512ppr2 from a fresh PGO build |
| 2026-11-07 | **The Phase 4 think tank's decisions (owner; docs/research/phase4-think-tank/, numbered as its synthesis §7).** (1) **Time management moves into Phase 4**, limited to node share plus best-move stability (R8), on the LTC list; base allocation, the time curve and a TCEC-ratio control stay in Phase 5; the resolution-aware soft stop is dropped (a timed search reaches the soft check only after a completed iteration). (2) **SPRT design R is the standard for search features**: [0, 6] nElo, alpha 0.05, beta 0.20, a cap of 8 stages, a futility stop after stage 2 (the same design at LTC, capped at 4-6 LTC stages); networks keep [0, 5]. Accepted risk: about 2% of truly null features adopted and about a third of +3 nElo features lost early, for about 60% fewer stages per test. **At most two tries per idea.** (3) **Constants by head-to-head selection** (value against value on the same games) instead of each-against-off ladders; the constants table records "head-to-head, N games, delta ± e" as Fork's own measurement; mini-SPSA once the driver exists. (4) **The SPSA retune is split**: an early pass on the eight eval-dependent margins at STC (R14), and a final retune by scaling class at the end (R24: shallow margins at STC, depth-scaling constants at LTC); time-management parameters never in an STC/LTC SPSA, the eval scale never in SPSA. (5) **Workflow changes approved**: the GitHub SPSA driver (a FORK_TUNE build input, per-pair options), per-shard options for the factorial screen, and a runner A/B speed job. (6) **The removal round becomes a factorial screen** (R30, with the skeptic's four fixes), replacing Quality control 6's per-feature [−3, 0] SPRTs; accepted: about a 23% chance of removing a +3 nElo feature, for a decision on every switch. (7) **The speed-to-Elo measurement** (§5.6 item 4) is a throttled 0.5x test-only build, 2 STC stages plus 1 LTC stage, with the speed ratio measured in situ on the runners, replacing the 0.85x time-odds design. (8) **The speed gate**: its ratio is measured in the shard build on the runners and priced at 1.5 Elo per 1% nps (1.26-1.80; the fit to all eight fixed-node/STC pairs) instead of 2 ± 1 or 3.1, the 0.90 threshold kept until the measurement of (7); a cycles-per-node 1% acceptance rule for bench-identical speed changes (a §7 doctrine change); a change that is slower locally is adopted if it is faster on the runners and in the TCEC build (R31). (9) **The TCEC build** (R11): x86-64-v4 with speed sprint C1's AVX-512BW output layer behind a startup CPU check, PGO by default with a fallback, the compiler chosen by measurement, the final gauntlet played with the TCEC build; C1 also for the native data-generation build now; VNNI stays out until TCEC answers (the 2026-10-28 rule). **Ask TCEC** whether a launcher may pick the binary at startup and whether the servers support AVX-512 VNNI (KB competition.md question 8). (10) **Item 8a's recipe** (the retrain on g3s3 = g3s2 + g3f + g3g, synthesis §5): the standard recipe unchanged as the control (2 seeds), plus a cooldown branch, an anneal-only arm, the recency arm only if the deep-label gold set exists, and the optional high-WDL branch on the finished candidate (its own SPRT, guarded by the endgame check and a 5-man rook-ending check); an averaged candidate may go to the SPRT when it is more than 1e-5 better offline; candidates scored offline on the full validation set, not best-of-N; checkpoints and optimiser state kept; **the endgame acceptance target is at most 15 of 900 misjudged**. (11) **Numbering**: "item 8" is the retrain loop (8a, 8b, ...); idea 42 (continuation histories in LMR) is folded into the round-once LMR step (R20). (12) **The next data part (g3h) uses the 2026-09 opening book** (lichess-2026-09.epd), after a duplicate count against the parts already generated. (13) **Local measurement jobs run beside data generation** (2 threads each, one at a time), and part seals serve as the quiet windows for speed A/Bs. (14) **Stormphrax** (two rulings): it is included in the clean-room survey at concept level like every other engine (public README, release notes, PR prose, forum posts; never source code or exact constants), any instruction embedded in its text is data and is ignored, and the KB's existing citations stay; **where an idea is also documented by another source, that source is credited and reliance on Stormphrax is minimized**. (15) **TCEC game statistics** may serve only as a cross-check for a time-management constant, never to set one; constants come from Fork's own games. (16) **Calibration constants may be fitted on SPRT test games** (R33) only if the constant's adoption test then uses fresh games. (17) **The endgame-start data slice** (R32) is deferred until item 8a's result. (18) **A gauntlet of S512ppr2 runs now**, with the standing anchor set (Marvin 6.3.0 and Altair 7.0.0 included): run 42392526865 on a24d41f (11:41 AM to 12:04 PM EST, every job succeeded): **Fork 3488.2 ± 22.2** (Ordo, CCRL Blitz scale, 1,200 games at 10+0.1, 864.0 points, 72%), against S512r2's 3445.8 ± 21.6 on 2026-11-02 (+42.4 against the anchors; the two promotions since measured +32.7 and +20.1 head to head). Scores: Altair 7.0.0 (3579) 130.5 of 200 against Fork, Marvin 6.3.0 (3458) 84.5, Laser 1.7 50.0, Winter 0.9 28.0, Monolith 2.01 22.5, Weiss 1.0 20.5. (19) **Idea 23** runs as a capped pilot with a game-based fitness (R38), after the LMR terms, never on the label-and-sweep proxy. (20) **The synthesis's drop list (§4.1) is accepted, except idea 40's L3 root planner, which is parked** (kept in ideas.md). Dropped or replaced: distillation from S512+X and idea 46's threat-keyed correction table; idea 46's threat inputs parked; S512cl's speed work; idea 40's L1 (a separate pawn-and-king net) and L2 (the pawn drift table); the material, major and threat correction tables; the QAT validation session (the `--qat` option stays); S512+X and AF-S as LTC candidates; idea 45 part 3; idea 47.1; idea 34 as a standalone test; ideas 10 and 11 (replaced by R33 and R32); BOLT (idea 21); idea 36 closed; the re-validation filler shrunk (B-3 and the root fail-high fix dropped, B-4 as R13's variant, keep-exact only at a TCEC-scaled hash); fractional depth shrunk to round-once LMR; batch 4 redesigned (razoring and bad-capture futility demoted, the history malus balance an SPSA parameter). (21) **A VLTC spot check** (120+1.2, 2 stages) of the final retune's output. (22) **Phase 6 guardrails as a standing rule** (H9): no new per-thread table above about 256 KB without a TCEC-footprint note, weight tables at most about 4 MB, new search state per-thread or explicitly shareable. (23) **TT-policy tests run at a hash scaled to TCEC's entries-per-node pressure.** (24) **Search adoptions are bundled into at most one data-generation part switch per day** (a labeller-policy refinement). (25) **ProbCut keeps its rule: no retest**, at LTC either. (26) **A negative extension gated to cut nodes, in sub-ply form (R40), counts as a new idea**, not a retest of the rejected ungated one; `use_negative_extension` stays until it is tested. The updated Phase 4 order was approved by the owner the same day and replaces §5.6's order table; §5.6 and ideas.md mark the dropped items. |
| 2026-11-07 | **Data generation cut to 6 threads (owner).** g3g stopped at a game boundary at 12:16 PM EST (111,190,930 positions, 50,692,451 of them unsaved, in 1,191,355 games, of its 366,424,464 target) and sealed through the Control Center (cc_stop.py; seal job seal-g3g); the generation continues as g3h on 6 threads from the same default engine (a24d41f, S512ppr2, bench 14,626,377; seed 20261113), started by the queue job g3h-chain once the seal succeeds. The freed threads run the think tank's step 1 measurements. Item 8a moves forward to follow g3g's seal (§5.6 order step 8), with less new data than planned. g3h keeps lichess-2016-09.epd: decision 12's switch to the 2026-09 book needs its duplicate count and an openings manifest first, so it comes at the next part boundary. |
| 2026-11-07 | **g3g sealed; the 2026-09 book at the next natural part boundary (owner).** g3g's seal verified every game (1,191,355 games, 111,190,930 positions, 50,692,451 unsaved) at 1:53 PM EST; its manifest is data/manifests/g3g.json; g3h started at 1:57 PM EST on 6 threads (a24d41f, S512ppr2, seed 20261113, lichess-2016-09.epd). The think tank's R1 duplicate count refuted its premise: at ply 20 or less, 0.0034% of kept positions are duplicates (19 of 555,082 over one shard each of g2e, g3, g3e and g3f), because every game starts from a distinct book position plus 2-4 random plies (the book is played as a seeded permutation). The owner keeps decision 12's switch to lichess-2026-09.epd for breadth, **only at the next natural part boundary, with no special stop**; its openings manifest (data/manifests/openings-lichess-2026-09.json, SHA-256 dab45c9f...) is committed and both copies (Windows and WSL) match it; the Control Center gains a setting for the next part's book before that boundary. |
| 2026-11-07 | **Ideas 48-60 recorded, plan only (owner).** A "novel NNUE ideas" group (48 decision-focused loss, 49 a pairwise ranking loss on sibling positions, 50 conformal pruning margins, 51 TD(lambda) targets, 52 ensemble-disagreement active learning, 53 pawn-structure-class output experts), scheduled after item 8a, first experiments in the order 51 and 52, then 53, then 50, each at equal data with a small net first; a "paradigm candidates" group (54 a shared-accumulator policy head, the first to prototype, after item 8a; 55 a learned reduction and pruning function; 56 probabilistic search with neural uncertainty; 57 in-game adaptation; 58 giant-teacher distillation), after the current order; and 59, the Boundary Refiner (a rich evaluation consulted only near the alpha-beta window; its refiner shares the base accumulator), after item 8a; and 60, a near-window extension at depth-1 frontier nodes (after item 8a, before idea 59's step 3). Each entry states its mechanism, its mathematical or literature basis, its first experiment and its kill criterion. |
| 2026-11-07 | **Testing speed: the design R tooling's settings (owner).** Design R and the head-to-head selection (decisions 2 and 3) are built before other work, so every later search test uses them. Settings: the default LTC cap for search features is 6 LTC stages (a run may set 4-6); the two-try limit counts per time control (an LTC confirmation of an STC pass is not a retry); every SPRT carries an idea id, network tests included, and each retrain is its own idea (8a, 8b, ...: each trains on new data), so the limit applies to retesting the same network, never to the retrain loop; in a head-to-head selection the declared value wins unless another beats it by more than 0.5 e. **CI:** a gate job classifies each change; docs-only changes skip the build matrix (about 1 minute instead of about 154); the full TSan suites move to the nightly run and an opt-in dispatch input, and run on pull requests and pushes only when files touching threads, the TT or the UCI layer change (the searcher does not count); a small "TSan, threaded suites" job (the UCI, TT, datagen and web suites under TSan) stays required on every code change; one aggregate "CI result" job passes only when every job passed or was skipped by its own rule, and branch protection on main is switched to require it alone before the first pull request to main that runs the new workflow (phase-4 itself is not protected). A typical code PR's expected CI time falls from about 154 to about 50 minutes (the design's medians over ten runs; UNVERIFIED until measured). |
| 2026-11-07 | **CI testing speed (owner).** ci.yml's new `changes` job (`.github/ci/changed-areas.sh`, tested by `.github/ci/changed-areas-test.sh`) lists the changed files once and decides what runs: documentation alone (docs/, any `*.md`, LICENSE) skips every build job on pull requests too (pushes keep their paths-ignore); the full TSan suites (`clang-tsan`, `gcc-tsan`, now the reusable `.github/workflows/tsan.yml`) run only when threads, the TT or the UCI layer change (src/uci/, src/main.cpp, src/datagen/, trans_table.\*, hash_memory.\*, their tests, the build files, the CI files, or any other source file using a threading primitive; not `searcher.*`), nightly on main beside perft_epd_full, and on demand (dispatch tsan.yml, or ci.yml with `force-tsan`; a manual run never runs them otherwise); a new job, **TSan, threaded suites**, runs uci_protocol, uci_options, uci_timing, tt, datagen and web under both TSan presets on every code change (no bench parity there: the full run has it). One job, **CI result**, needs every other job and passes only if each passed or was skipped by its own rule; main's branch protection will require it alone (switched by the owner before the first pull request to main that runs the new workflow). Expected wall time for a typical code PR: about 50 min instead of about 154 (gcc-tsan's median); docs-only about 1 min. |
| 2026-11-07 | **Idea 52: the independent committee (owner).** The seed-disagreement check (docs/research/idea52/report.md): item 7's warm seeds, in effect one net, fail the 1.5 line (eval-matched error ratios 1.24-1.37); its scratch seeds, independently initialised, pass it (1.69-1.76 on three detectors, 1.49-1.50 on the fourth, unchanged with deep-search mates excluded), and the default net errs 1.6-1.7 times more on the positions they pick. Decided: (1) an independent pair's disagreement is a detector in the crucial-point measurement (the gate comparison for ideas 59 and 60); (2) **retrain 8b gets an idea-52 arm**: the top-disagreement positions from an independent pair, deep-labelled by the default engine and oversampled, against the standard arm at equal data (the same number of positions seen); (3) **every retrain from 8b on keeps one from-scratch run as the independent committee member** (about 2.2 T4 GPU-hours at the standard 360 superbatches). A cheap check first: whether a warm-against-scratch pair (the default against the scratch run) carries the same signal, since every retrain will have that pair. **Keep-or-drop rule, decided before 8b's result:** if 8b's disagreement arm does not beat the standard arm by a meaningful margin (a fixed-node screen of +5 Elo or more, or a passing SPRT if it is screened), idea 52 is retired and the scratch-run rule dropped (saving its 2-4 hours per retrain); the result stays in the record either way. |
| 2026-11-07 | **Retrain candidates are gated by a fixed-node screen, not by validation loss (owner).** Item 8a's declared rule required the candidate's full validation-set loss to beat S512ppr2's by 2e-5; R1-avg (the average of R1's superbatches 331-360; every gate passed: S = 89, qloss 9.4 / 7.5 cp, the endgame check 8 of 900, netcheck 0 of 446) beat it by 1.82e-5, short by 1.8e-6 (the validation set, mostly g3s2-val, favours the baseline it selected). Declared before any result: a tie-break with one 1,600-game fixed-node screen of R1-avg against S512ppr2 (800,000 nodes per move each); the STC SPRT [0, 5] follows only at +5 Elo or more, otherwise 8a is recorded as below threshold and the next retrain is 8b. **From now on** a retrain's candidate is gated by that fixed-node screen (the same architecture, so no speed adjustment) instead of the offline validation-loss margin, since loss has proven an unreliable predictor (S512+PP gained +32.7 at STC with a flat loss). Also from 8a's arms: the cooldown branch did not beat R1's own average (4.8e-5 worse on the prefix window), and the anneal-only arm was worse than R1-avg on the full set. |
| 2026-11-07 | **S512ppr3 promoted to the default network (owner, about 9:05 PM EST).** Item 8a's retrain (S512+PP's architecture on g3s3 = g3s2 + g3f + g3g, Kaggle fork-retrain-g3s3 v1 at 6053b51, every arm warm from S512ppr2's float weights, S = 92 in training): R1 and R2, the standard recipe (seeds 1, 2); CD, a cooldown branch from R1's superbatch 180 (1e-5, 3e-6, 1e-6 for 20/15/15 superbatches, the last 15 averaged); D1, anneal only (1e-5 for 60 superbatches). Full g3s3-val losses: S512ppr2 0.01968472, R1-best 0.01965562, R2-best 0.01972978, R1-avg 0.01966655, CD-avg 0.01977483, D1-final 0.01975487, D1-avg 0.01971097: **the cooldown branch and the anneal-only arm did not beat R1-avg**. By the declared rule R1-avg was the candidate (more than 1e-5 below R-best, R2's best checkpoint), 1.82e-5 below S512ppr2, short of the 2e-5 margin; the owner's tie-break, one fixed-node screen, **now replaces the loss margin** as the gate for retrain candidates (the row above). S512ppr3 (bake/s512ppr3 720fe7b: R1-avg at the matched S = 89, 1 of 311,296 link weights clamped; quantization loss max 9.4 cp, p99 7.5 cp; netcheck exact on 446; the endgame check 8 of 900, as S512ppr2) scored **+15.65 ± 9.26 Elo** (nElo +28.80 ± 17.02, ptnml [7, 161, 406, 205, 21]) at 800,000 nodes per move (run 42426868742), above the declared +5, then beat S512ppr2 at STC [0, 5], **+7.12 ± 4.53 Elo (nElo +11.98 ± 7.61), H1 accepted** after 5 stages, 8,000 games, LLR 3.14, ptnml [100, 908, 1848, 1016, 128] (runs 42429984619, 42431412304, 42432793282, 42434196075, 42435511074; the driver stopped in the machine's crash at about 8:07 PM EST after dispatching stage 2 and was resumed with RUN_ID for that stage; sprt-log). Promoted; S512ppr2 stays buildable and joins CI's `nets` job; the web page adds S512ppr3 as its default when it is next redeployed. Bench 14,149,617 / 1cb0717f040c294d. **The labeller policy:** g3i (started after the crash, labelled by S512ppr2) ends at a game boundary and is sealed as its part, and the generation continues as g3j, labelled by S512ppr3 from a fresh PGO build. The owner: switching g3i -> g3j today is an explicit exception to decision 24 (one part switch per day), because g3i's start was forced by the crash and the labeller policy calls for an immediate switch on a network promotion |
| 2026-11-07 | **Crucial-point ground truth; the window gap gates ideas 59 and 60 (owner).** On measure/step1 (daca926, its §5.7): 5,433 sampled evaluation sites from 100 of Fork's games, deep-searched at 1 M nodes; 18.6% are crucial (the static evaluation and the deep value on opposite sides of the nearest finite bound) in both strata. Recall at 4% of the nodes: a logistic model (the gap plus features) 0.34 in the main search and 0.26 in quiescence; the window gap alone 0.30 / 0.25; random 0.13 / 0.10; the seeds' disagreement is near random as a gate (AUC 0.52-0.54). The owner: idea 59's oracle screens and idea 60 use the window gap now; the logistic gate comes in only in idea 59's step 3 and idea 60's tuning, if their screens pass |
| 2026-11-08 | **Idea 59's step 2 passed; the control split confirms the mechanism (owner).** Fixed-node screens (1,600 games, 800,000 nodes per move) against S512r2 alone: setting (a), window gate 25 / 10 cp with S512+X refining, +29.82 +/- 9.78 (3.81% of nodes consulted); setting (b), 25 / 25 cp, +41.01 +/- 9.97; a random gate at (a)'s call rate +7.60 +/- 9.93; bias only ((a)'s gate adding its mean refinement, S512+X never consulted) −14.56 +/- 9.96. The gain comes from where the refiner is consulted, not from a shift or from refining any 4% of nodes (ideas.md idea 59 has the runs). Next: step 3's design (a refiner sharing S512ppr3's accumulator, on-demand exposure features, trained on near-window positions from Fork's own search with deep labels from a pinned binary) for the owner's review before building, and a prior-art search before any public claim. Fixed-node gains do not charge the second network's cost; the nps claim waits for step 3's build, measured on a quiet machine. |
| 2026-11-08 | **TCEC's hardware supports VNNI (owner).** The answer to KB competition.md question 8 (decision 9 of 2026-11-07 kept VNNI out until TCEC answered): the owner reports that TCEC's hardware supports AVX-512 VNNI (the primary source is to be cited in the KB when available). VNNI paths may now be built for the TCEC build, each with its scalar reference and an exactness test (§7); SPRTs on the GitHub shards still run x86-64-v3, so a VNNI speed gain is judged separately from the AVX2 path that the SPRTs charge (idea 59 step 3, owner 2026-11-08). Still open: the `-march` for TCEC's build and the launcher question. |
| 2026-11-08 | **Time management variant (b) adopted (owner; §5.6 step 10, R8).** The soft limit scaled by best-move stability and the best move's every-pass node share (`UseStabilityTime` and `UseShareTime` on; constants from Fork's X6 fit, stability cap 72; Search constants) passed design R [0, 6] against off at STC (+18.69 ± 7.18 Elo, 3,200 games, H1) and at LTC 40+0.4, Hash 64 (+10.23 ± 5.14 Elo, nElo +19.22 ± 9.64, 4,992 games, H1 after stage 6, job tm-r8-ltc), and was merged into phase-4 by the owner's rule of the same day (adopt only after LTC passes). Variant (a) (tm/a, stability alone) lost the head-to-head and is not adopted. Both switches stay until the Phase 4 re-validation. Bench unchanged (14,149,617 / 1cb0717f040c294d); data generation is node-limited and unaffected. |
| 2026-11-08 | **The gauntlet's set of 2026-11-08: every anchor standing, and a gap to Stockfish (owner).** tools/gauntlet/anchors.tsv: Clover 6.1 (CCRL Blitz 3639, rechecked on the list of 2026-11-07) a standing anchor with the role `new` and no alternate (it built in the anchor job of runs 41465146207 and 42392526865 as Altair's alternate but never played, so not `continuity`); Marvin 6.3.0 and Altair 7.0.0 `continuity` (both built and played in those two runs), and Arcanum 2.8, Marvin's alternate, removed (its build failed in both): a failed build of any anchor now stops the run before any game. **Stockfish 19** (tag sf_19, edb0d9d, GPL-3.0), role `reference`: 400 games (all 200 openings, both colours, 4 shards), Threads 1 and Hash 16 MB as Fork's, built with `make net` then `make build ARCH=x86-64-avx2` (the network's file name and SHA-256 logged; whether `make build` alone fetches it is UNVERIFIED until the first run's log), **kept out of the Ordo fit** and reported apart as the gap to Stockfish: Fork's score, the implied Elo difference and its pentanomial 95% interval (tools/gauntlet/report.py, which now merges the shards and runs Ordo; its CCRL Blitz 3792 shown for context only); a failed build stops the run. A run plays 1,800 games: 1,400 in the fit (7 anchors x 200), 400 against Stockfish. Opponent binaries only (ORIGINALITY.md; KB competition.md §5). |
| 2026-11-08 | **Gauntlet of the new default (S512ppr3 + time management (b)): Fork 3488.2 ± 20.4; gap to Stockfish 19 −222.4 (owner).** Run 42538371594 on phase-4 32c5517 (update.sh, gcc 11.4, x86-64-v3; bench signature 1cb0717f040c294d checked on the runner), 7:06-7:45 PM EST, every shard 100 of 100, no time forfeits; 200 random 8-ply openings, 10+0.1. Ordo, CCRL Blitz scale, 1,400 games against the seven standing anchors (931.5 points, 67%). Opponents' scores against Fork: Clover 6.1 (3639) 147.0 of 200, Altair 7.0.0 (3579) 121.5, Marvin 6.3.0 (3458) 86.0, Laser 1.7 (3292) 49.0, Winter 0.9 (3168) 30.0, Monolith 2.01 (3061) 19.0, Weiss 1.0 (2896) 16.0. The rating equals S512ppr2's 3488.2 of 2026-11-07 to the decimal by coincidence: on the six anchors both runs share, Fork scored 878.5 of 1,200 (73.2%) against 864.0 (72.0%), about +10 Elo by the logistic slope, within either run's error, while Clover, new to the fit, scored 74% against Fork (about 3460 implied from that pairing alone). **Gap to Stockfish 19** (sf_19, edb0d9db, net nn-1a298aa575a0 fetched by its make net; outside the fit): Fork 87 of 400 (21.8%), +49 =76 −275, **Elo −222.4, 95% interval −251.2 to −196.1** (pentanomial, 200 pairs, [75, 76, 49, 0, 0]: each of Fork's 49 wins is paired with a loss of the colour-reversed game); for comparison, Fork's fitted 3488 against Stockfish's CCRL 3792 is −304 on the list's conditions. Result: ~/fork-data/gauntlet/run-42538371594. |
| 2026-11-09 | **Idea 59 step 3 closes; step 3b parked (owner).** Fixed-node screens (1,600 games, 800,000 nodes per move, against S512ppr3 alone, gate main 25 / quiescence 10 cp) replaced the net-flip yardstick as the deciding test (owner, 2026-11-08). The shared-accumulator refiner (kernel v2) hurt: both gates −19.78 ± 9.67 (run 42574807031), quiescence only −11.73 ± 9.63 (42589690181); both at or below 0, so the refiner line ends with no SPRT. An independent net (s512pp-scratch-s1) consulted at the gate: blend +9.56 ± 9.45 (42594402144), replace +3.47 ± 9.34 (42600420297), the pattern the independence hypothesis predicted, but below the +10 bar declared before the result. No step 3b plan is written; step 3b (a small independent near-window net, widths 64 / 128, blended with a tuned weight) is parked as a hypothesis to revisit when compute allows. ideas.md idea 59. |
| 2026-11-09 | **The full TSan suites on a push or pull request leave out `search` and `pruning`; nightly runs them all (owner).** Milestone 2's CI run 42611572178 lost gcc-tsan to its 240-minute limit: `search` alone took 10,296 s under gcc-tsan, `pruning` 1,266 s, and every test that finished passed. ci.yml now calls tsan.yml with `skip: '^(search\|pruning)$'`; nightly.yml and a dispatch run every fast suite, and the job's limit is 360 minutes. Both suites are single-search tests; the threaded suites still run under TSan on every code change (tsan-threaded). |
| 2026-11-09 | **Big-picture follow-ups: three decisions (owner).** (1) **Ensemble teacher (ideas.md 63): step 0 runs now** (E3 = S512ppr3 and item 7's two scratch seeds; about 1.25-1.5 h on 2 workers beside g4, one measure job), declared before any label in docs/research/labels-teacher/step0-declaration.md (dc90302, branch research/labels-teacher); reported before any small net, with the TD pre-test's measured same-network bias. (2) **Label depth (ideas.md 62) approved**: it starts after retrain 8b launches, a 30-minute rate probe first, then the 20k / 50k / 100k arms as designed (docs/research/labels-teacher/report.md §1) under the declared rule (+5 Elo with the interval above 0, then an STC network SPRT). (3) **Score-fall time (ideas.md 64) parked**: design and screened names kept (docs/research/eval-trend-tm/design.md); queued only if GitHub is idle. |
| 2026-11-09 | **Testing policy from the transfer-testing report (owner; docs/research/transfer-testing/report.md).** The report: since S512r2 the adopted changes summed to +84.6 ± 15.3 Elo in self-play against +55.4 (paired SD 12.2) on the six shared gauntlet anchors, a transfer ratio of 0.65 (95% 0.36-0.99); the SPRTs' conditions (unbalanced openings, tablebases, adjudication) resemble TCEC's more closely than the gauntlet's (balanced openings, no tables). Decided: (1) **the 2e-5 validation-loss margin is dropped**; validation loss is a diagnostic. (2) **The endgame acceptance target (at most 15 of 900, think tank decision 10) is non-blocking**: the check is reported for every net and a large regression against the default is flagged to the owner (it guards play without tablebases). (3) **The testing rule** (Testing setup): integrity checks block; a candidate whose speed differs from the default's plays a speed-adjusted fixed-node screen first (FN + 118 log2(r) > 0, r read from the screen's own games), then its STC SPRT [0, 5]; a single same-architecture retrain goes straight to its STC SPRT (replacing the 2026-11-07 fixed-node gate for retrains), competing candidates all screened first; search features stay on design R. (4) **The speed price is 1.72 Elo per 1% nps** (1.56-1.88; 118 ± 5.6 Elo per doubling from in-situ ratios, 9 of 9 leave-one-out verdicts), replacing decision 8's 1.5. (5) **The anchor check, both levels built as designed:** level 0, every gauntlet report shows the paired-by-opening gain over the previous gauntlet on the shared anchors and the running transfer ratio (tools/gauntlet/report.py); level 1, for major adoptions only (a claimed STC gain of +30 Elo or more, a new architecture, a time-management change, or unconfirmed adoptions summing to +40 or more), a paired match of the old and new Fork, each against Clover 6.1 and Altair 7.0.0 on the same 200 openings, 1,600 games at 10+0.1, a fixed sample (about one STC stage of runner time), outcome confirmed / consistent / flagged for the owner, never a revert, at the next idle slot after adoption (a two-engine mode in .github/workflows/gauntlet.yml). Corrected: each anchor plays openings 1-100 with both colours; only the Stockfish reference plays all 200. |
| 2026-11-09 | **Gauntlet upkeep made permanent (owner).** (1) **The adoption checklist** (Quality control 5, after the SPRT checklist) records every adopted change in tools/gauntlet/transfer.json at adoption time, beside the SPRT log, decisions log, constants table, ideas.md, bench references and the labeller policy's part switch. No change was adopted after 32c5517 (the engine source since then adds only the measurement presets' counters, bench unchanged), so transfer.json's list is current. (2) **Every gauntlet's stored results are downloaded into ~/fork-data/gauntlet/ with SHA-256 checksums** as part of its report step, and now for every past run, so nothing depends on GitHub's artifact expiry (the baseline run's on 2027-01-31); level 0 reads the local copy when the remote one is gone (tooling on branch gauntlet/archive). (3) **Every report names its rating model**: the Ordo fit (white advantage and draw rate, anchored to CCRL Blitz) or the plain logistic fit (anchors fixed, the SPRTs' logistic Elo scale); the transfer report's 0.65 is on Ordo's gains, the gauntlet report's running ratio (0.61, 0.32-0.95, on the same data) on the plain logistic. **Idea 52's full 8b check** (the owner's rule of e3b933b): 1.42 matched [1.26, 1.62] on all 202,000 labels; the interval straddles 1.5, so the arm stays in 8b (81a66ec, idea52/8b-sites). |
| 2026-11-09 | **RfpMargin's follow-up moves to the final retune (owner).** The queued head-to-head of 55 against 45 within the tuned set (night queue item 35, conditional on the tuned-values SPRT) is cancelled before it ran. Instead step 19 widens RfpMargin's lower bound to about 30 so the SPSA can move it below 55 (§5.6 order, step 19). Kept on file: the 45 build (tune/spsa-r14-m2-rfp45 0c09b93, bench 8,587,476 / 2342ba5c42adb014) and its credit decision (ORIGINALITY.md: a near match with current Stockfish, kept by the owner). |
| 2026-11-09 | **The R14 SPSA's tuned values adopted on phase-4 (owner; an explicit exception to the LTC-sensitive rule).** spsa-r14-m2 (13 iterations, 10,400 pairs at 8+0.08 on 32c5517) tuned RfpMargin 80 -> 55, FutilityOffset 100 -> 86, FutilityGrowth 70 -> 50, CaptureSeeFloor 100 -> 118, LmpQuietAllowance 12 -> 8, NullSurplusPerPly 300 -> 301 (AspirationHalfWidth stays 12); the set's STC design R SPRT against 32c5517 (spsa-r14-m2-stc, run 42726060415, 1,600 games): **+37.93 ± 10.03 Elo, nElo +64.91 ± 17.02, H1** (LLR 4.92). Adopted on that STC result alone, as the owner's exception: its LTC design R SPRT still runs afterwards as a **non-blocking confirmation** (night queue item 21), with the level 1 anchor check (item 22, claim +38, Clover and Altair); a failure of either is reported to the owner, never reverted automatically. Bench 10,374,064 / 677c436fa145e07f (every network's reference and the bootstrap's re-pinned in the adopting commit). Recorded per the adoption checklist: the SPRT log, the constants table, ideas.md, tools/gauntlet/transfer.json. Labeller policy (decision 24): data generation switches at g4's seal, so g4b is a fresh PGO build of the tuned engine; the play build rebuilt. |
| 2026-11-09 | **The Phase 4 design documents merged; the owner's decisions 2-5 on them (owner, about 8 PM EST).** The four designs (docs/research/phase4-designs/: idea 53's structure experts, the factorial removal round, the structure-class calibration, the final retune) are merged into phase-4, each amended with the decisions below. (2) **Final retune:** all ten widenings the design proposed plus RfpMargin's are applied to src/tune/params.hpp's ranges (lowest: RfpMargin 30, LmpQuietAllowance 3, FutilityOffset 30, FutilityGrowth 25, SingularMarginPerPly 2, SingularMinDepth 3, LmrMinMove 1, LmpMaxDepth 1; highest: NoMoveReduceMinDepth 16, ReplyWeight 12, NullSurplusPliesMax 6), defaults and steps unchanged, bench unchanged; ReplyWeight's int16 headroom at 12 checked (no overflow: the quiet score sums in int, at most 60,000, and clamps to int16; tests/test_ordering.cpp); LmrMinMove 1 searches exactly as 2 (the first move never takes the LMR path). `spsa.py report` flags a parameter pinned at a bound (theta at `lowest + c` or `highest − c`, within c / 100, in at least a third of the updates or at the last; branch tune/spsa-pinned): on spsa-r14-m2 it flags RfpMargin and LmpQuietAllowance. (3) **Factorial removal threshold: "estimate <= 0"** (rule A, the risk decision 6 accepted). (4) **Idea 53's 2e-5 probe stop-loss and the calibration's 30% offline kill become diagnostics only**: reported, never a gate (the probe still ranks the maps and picks the one trained). (5) **The calibration's SPRTs use design R; the final retune's VLTC check uses a non-regression rule** (pass if the 2-stage nElo estimate is at or above −3, the edge of the non-regression bounds [−3, 0]; a fail goes to the owner: revert the LTC pass's values or extend by 2 stages once; final-retune.md §5); **the factorial tooling is built when step 18 comes up.** |
| 2026-11-09 | **ChessTB and endgame slice v2 (owner; KB chesstb.md, kb 2e46665; docs/research/endgame-slice-v2/design.md).** (a) **The data-policy line is adopted** (training-data decision 1: ChessTB WDL/DTZ labels beside Syzygy, labels only, provenance and hashes recorded, never committed, the explorer for spot checks only). (b) **Budget R** (about 97 GiB downloaded, 34.5 GiB peak disk, one table file at a time). (c) **v2 replaces half of v1**: the slice stays 2% of a retrain's positions, half the current 3-5-piece Syzygy slice and half v2. (d) **The arm goes into retrain 8c** (8b keeps the current slice in every arm). (e) **The pure-Python prober first** (python-chess fork, pinned commit), its rate measured; ChessTB's C++ library only if labelling would exceed about a day. (f) **Tables stored in WSL.** (g) **Declared now, before any data: v2 is kept if its arm's fixed-node screen interval is not entirely below 0 AND the held-out 6-7-piece misjudgment falls by at least 25% against the control arm.** (h) **The class shares, the one-wing bias and the C2/C3 sub-types wait for the final conversion-and-defense numbers.** |
| 2026-11-09 | **Idea 23's restart target recorded (owner; plan only, idea 23 stays parked).** First target: the quiet move-ordering score (how the history tables combine), fitness = nodes to a fixed depth on a large position set (deterministic), a held-out set for confirmation, a guard that search results stay equivalent (the same best move, and the score within a tolerance, on a check set), then a design R SPRT of the winner. Runner-up: the time-management formula with a game-based fitness (ideas.md 23). |
| 2026-11-10 | **The conversion-and-defense analysis's data fixes (owner; docs/research/conversion-defense/report.md on research/conversion-defense, be86410).** (a) **Fixes 1 and 2 approved as one generation run** (ideas.md 66): a positional-advantage slice and a defense-start slice from Fork's own datagen positions (queens on, equal pieces), played out with raised adjudication. **A pilot first** (about 16 CPU-h); the slices are generated only if the pilot's rates and label checks look right; they are tested as arms in retrain 8c. (b) **Fix 4, a class-weighted sampler in the trainer** (ideas.md 69): a design review first, then an 8c arm. (c) **Fix 3** (R32's endgame-start slice, widened to rook against minors, queen imbalances and a piece against pawns) **waits for fix 1's result**. (d) **Endgame slice v2's class shares** (design decision (h), 2026-11-09) **are set from the analysis's numbers**. (e) **Idea 23's pilot**: its final result and replay check are reported when generation 5 ends; **no further run without the owner**. |
| 2026-11-10 | **Idea 69, class-weighted training: the design review's recommendations 1-9 approved as written (owner; docs/research/class-sampler/design.md, research/class-sampler f235d27), with one change.** Approved: per-position loss weights (rejection sampling as the fallback if an all-ones table does not reproduce the control); board-only weights; the material class alone; all 7,378 deciding positions as the target; cells with fewer than 50 deciding positions at weight 1; ideas 66 and 68 as separate 8c arms against one control; a second control seed if 8c's quota allows; the report's validation-loss kill rule dropped (validation loss a diagnostic only); **the keep rule, declared now: +5 Elo head to head against the control, or a passing STC SPRT**. **The change: the classes the conversion-and-defense report flagged for conversion failures (rook against minor pieces, queen imbalances, a piece against pawns, and one-wing structures as classified there) are floored at weight 1.0 instead of 0.5**, and the scale is re-solved so the mean weight stays 1. Next: the pre-arm checks; the arm runs in retrain 8c. |
| 2026-11-10 | **Idea 23's ordering pilot: a null result; idea 23 parked (owner).** The capped pilot on the quiet move-ordering score (docs/research/idea23-pilot/results.md, evolve/ordering-pilot 52a0fd6; 5 generations x 8, 40 proposals scored, 543,832 tokens of the 10,000,000 cap, 0 gate failures, 0 guard refusals) found **no candidate beyond noise: the ordering formula is near-optimal for this fitness**. Best by the declared rule, #35: +0.39% nodes saved [-0.39, +1.19] on the 4,794-position set, +1.43% [-0.33, +3.18] held out, 85.6% equivalent; nothing goes to an SPRT. The full replay of the run from its log was stopped before it finished by the owner's decision (about 9:00 AM EST, to free its CPU for the label-depth arms and the fix 1+2 pilot); the pre-pilot tiny live run's full replay (2026-11-09) had reproduced every candidate exactly. **Idea 23 is parked; the time-management formula stays noted as the next possible target, no run planned.** |
| 2026-11-10 | **Idea 69 after the pre-arm checks (owner; research/class-sampler 4372a3e, research/class-sampler-checks bcd48dc).** (A) **"A piece against pawns" stays as implemented** (the report's minor-EG with a minor up). (B) **The floor is narrowed to the conversion-failure material classes** (rook against minor pieces, queen imbalances, a piece against pawns); **one-wing structures are removed from the floored list**; the table is re-solved (mean weight 1). (C) **The 3% CPU speed limit is replaced by "trained positions per second within 1% of the control's", measured on Kaggle.** Then the remaining steps before the arm: the class recount on 8c's training files and the fixed table, the Kaggle preflight (all-ones equals the control, CUDA determinism, the speed rule), the arm in 8c's kernel, and the per-class validation scoring. **The trainer change's merge to phase-4 waits for the owner's OK.** |
| 2026-11-10 | **Idea 69's arm runs now as an extra retrain 8b arm ("cw"), not in 8c (owner).** The classes are recounted on 8b's training data (arm c's files, the slice exempt) and the table finalised with the narrowed floor; as soon as 8b's Kaggle session ends, a preflight (an all-ones table reproduces the control; trained positions/s within 1% of the control's), then the arm with the 8b control's exact data, recipe and seed, in its own kernel. It is compared against the 8b control by the declared keep rule (**+5 Elo head to head, or a passing STC SPRT**); its screen joins 8b's night-queue items. GPU quota checked first (9:20 AM EST: 24.35 h of 30 left, about 20 h after 8b's session). |
| 2026-11-10 | **Fixes 1 and 2 after the pilot's gold half (owner; research/defense-slices 5e42e4a).** Measured rate 9.6 CPU-h per million positions (the report's 4 was 2.6x optimistic). (1) **The positional slice is sized at 12.5 M positions (about 120 CPU-h)**, not 30 M (it passed every declared check on the gold runs; the offline gate +0.030 [+0.021, +0.040]). (2) **The defense slice is dropped for 8c, with no redesign now**: it failed its declared check 3 (defenders hold 6.4% at 80k nodes against the 10% minimum); its ~60 CPU-h stay unspent; a near-level band is revisited only if 8c's positional arm shows defense still lacking. (3) **The positional main pilot run (840,000 positions, the real start pool) runs now at 2 workers, lowest priority; the full slice starts only if it passes, and after the label-depth arms end.** Endgame slice v2's shares were set by the design's declared rule (research/endgame-slice-v2-shares 8e15f23: C1 30.4%, C2 17.3%, C3 29.3%, C4 23.0%, no one-wing bias). |
| 2026-11-10 | **Order after the label-depth arms (owner).** When the arms end and are sealed: **the full 12.5 M positional slice first** (only if its main pilot run passes), **then regular data generation (g4c) resumes** toward retrain 8c's threshold. The unattended chain is revised accordingly; a failed or unapproved slice does not block g4c. |
| 2026-11-10 | **Batch 4 trimmed; item 32 dropped (owner).** Batch 4's branches (base tier2/b4 1d1e313) and idea 61's were built before R14's adoption (85253a2), so they would test the untuned search. (1) **Kept: cut-node (CutNodeLmrPlies head-to-head of 1 against 2, then design R at STC) and the structure history at weight 5** (design R at STC), both **rebased onto phase-4's head with their benches re-checked** (new branches, the old ones kept). (2) **History-skip dropped** (at 5000 per ply it changed 30 bench nodes of 14 M; the think tank's estimate +0.3, conditional on X2). (3) **Horizon-drop (razoring) and bad-capture-stop dropped as standalone tests and added as dimensions in the final retune's SPSA** (step 19; the think tank's demotion, synthesis §5 table), which needs their constants in the tuning table (code and names screened then). (4) **PV-trace (PvTraceLmrPlies 1) deferred to the end-of-phase re-validation.** (5) **Item 32, take history's LTC confirmation, dropped: the factorial removal round covers that switch.** Item 31 (multi-cut's LTC confirmation) finishes. Idea 61's root-gap branches are rebased the same way before their queue items run (coordinator's choice, to avoid testing a stale search). |
| 2026-11-10 | **A stop that plays the unfinished iteration's move reports that iteration's depth in the result (owner: decide and fix).** The last `info` line already gave that move's PV at the unfinished depth with its exact score (§5.2 deliverable 2), and `SearchResult.score` was already that score, but `SearchResult.depth` kept the last finished iteration, so the web result read "depth 7" beside depth 8's score and line (startpos 1. e4 at 21,000 nodes; the `web` test failed 8 vs 7 on the R14 batch-4 branches). Chosen: the result takes the unfinished iteration's depth (option b). Rejected: marking that line as a bound (the score is exact for the move played, a bound line must not be the last one, and the web page drops bound lines), and reporting it under the finished depth (it would label depth 8's score as depth 7). Bench is unchanged (depth-limited searches never stop); datagen and UCI read the depth only as "0: nothing finished", which still holds; the tests that need the finished depth read `time_signals().depth`. Branch fix/partial-iteration-report. |
| 2026-11-10 | **Standing principle: test as efficiently as possible, not as little as possible (owner; §1 Ground rules).** Every reliability check stays; each test must be able to change a decision; the cheapest test that can decide comes first; tests stop early when decided; controls are reused and CI is bundled; GitHub, the CPU and the GPU are each kept busy with the next useful job; nothing is re-tested that another planned test already covers. **Every test proposal states the decision it can change and its cost.** |
| 2026-11-10 | **Idea 69's cw arm launched on an owner exception to its declared speed check (owner).** Preflight v2 under the revised rule declared first (retrain/8b-cw 0499006, design.md 14.8; record 299cf32): **the correctness checks passed**: the new trainer with no table and with an all-ones table stayed within the GPU noise of three runs of the old trainer against each of them (max 0.003071, RMS 7.00e-5), and the cw table changes training (RMS 2.42e-3, about 35 times the noise). **The declared speed check failed** (the cw table run at 0.9892 of the old runs' mean trained positions per second, against 0.99; the three identical old runs spread 2.9%). **Owner exception: the speed check affects only training cost, not the result's validity** (the arms are compared at equal positions seen), so cw and c2 are launched. |
| 2026-11-10 | **Two standing tooling rules (owner; §1 Ground rules), after retrain 8b's chain reported done with no ready file** (a Windows Python given a Git Bash `/c/...` path; the endgame check also crashed). (1) **One shared path helper** for Git Bash, PowerShell, Windows Python and WSL, used by every job and chain script, with a check that fails if a script passes a `/c/...` path to a Windows program; jobs are launched from PowerShell, never Git Bash. (2) **No silent done**: every chain verifies its final outputs exist and are valid before reporting done, else it reports failed naming the missing output. |
| 2026-11-10 | **After the engine survey's first results (owner).** (1) **A "result fine-tune" experiment is queued right after 8b's SPRT decides the base net**: the winner (td90 or the control) fine-tuned with a 100% game-result target at a low learning rate (Ethereal's form, concept level; kb survey 2026-11), on existing 8b data, two seeds; then the usual gates, a fixed-node screen against the base and an SPRT; the Kaggle hours are reported to the owner before the launch (ideas.md 70). (2) **Feature-transformer weight decay is a candidate arm for retrain 8c** (Stockfish's recent trainer change, concept level; ideas.md 71). (3) **Games against other engines are not Fork-pure data** (training-data decision 1): half the moves and the result come from the opponent; at most a separate, labelled lineage. |
| 2026-11-10 | **r8btd90 (retrain 8b's TD(0.9) arm) promoted to the default network (owner, about 6:45 PM EST).** Retrain 8b (docs/research/retrain-8b/plan.md and its manifests, retrain/8b-prep 320c0be; Kaggle fork-retrain-8b at 320c0be): five arms from S512ppr3's float weights on g4s1 (g3s3 plus g3h, g3i, g3j and g4), seed 1, 360 superbatches, each candidate its window average (superbatches 331-360): c, the control (result weight 0.5); i52, idea 52's arm; td80 and td90, idea 51's TD(0.8) and TD(0.9) labels on g3j and g4 at result weight 0 (every older file at the control's target); scr, the from-scratch committee member (not a candidate). Every candidate passed the gates at S = 89 (netcheck exact on 446; r8btd90's quantization loss max 10.6 cp, p99 9.1 cp, 1 of 311,296 link weights clamped); the endgame check 7 of 900 for each candidate (S512ppr3 8). Fixed-node screens against S512ppr3 (base c67fd26; 800,000 nodes per move, 1,600 games each): c +13.03 ± 9.37 (run 42889810114), i52 +5.86 ± 9.13 (42896624050), td80 −1.09 ± 9.30 (42903541854), **td90 +17.39 ± 9.71** (42910703028), so td90 (bake/r8btd90 115daad) went to the STC SPRT [0, 5] against S512ppr3 (r8b-stc-1): **+12.17 ± 5.71 Elo (nElo +20.96 ± 9.83), H1 accepted** after 3 stages, 4,800 games, LLR 3.67, ptnml [61, 483, 1147, 645, 64] (runs 42917050282, 42919747964, 42922442883; sprt-log). Promoted under its bake name; S512ppr3 stays buildable and joins CI's `nets` job; the web page adds r8btd90 as its default at its next redeploy. Bench 9,594,307 / 4eb36793548711d4 (the bootstrap's 11,537,913 / 90153d2b0f5a37f1 unchanged). **The labeller policy (owner):** the running label-depth arms stay on S512ppr3 until they end, because switching would confound that experiment; the positional slice and g4c use td90 (r8btd90), each from a fresh build of the promoting commit, bench-checked against tests/bench-r8btd90.ref. Not decided by this promotion: ideas 51's and 52's keep rules (the head-to-heads of td80, td90 and i52 against c, plan §3 items 6 and 7; r8b-h2h-i52 running, the TD arms' queued); idea 70's result fine-tune now starts from r8btd90. |
| 2026-11-10 | **T56 any-attack's first game test; batch 4 keeps its S512ppr3 bases (owner, about 7:15 PM EST).** (1) **T56's "any enemy attack" threat buckets get their first game test**, queued after root-gap (night queue item 63, t56-any-stc, after items 60-62): only the cheaper-attacker set was SPRTed (H0, −6.08 ± 3.59, 2026-11-06); the any-attack set lost only in the offline measurement (threat_set.json), which Fork no longer treats as decisive, so this is **its first game test, not a retest** (ledger idea `t56-any`, try 1). The any-attack set is ported onto phase-4 b787fba behind `use_threat_buckets`, off (branch tier2/threat-any, dc341d5; bench unchanged, 9,594,307 / 4eb36793548711d4); the test side is sprt/threat-any bfbc1c8 (switch on; bench 9,236,850 / 0f723ee4c163a419); design R STC ([0, 6] nElo, beta 0.20, cap 8, futility look after 2 stages), fresh openings from stage 3. The cheaper-attacker set is not ported. Like batch 4's and root-gap's switches, the port stays on its branch until its SPRT decides. (2) **Batch 4's items keep their S512ppr3 bases**: both sides of each test use the same net, so the default's change to r8btd90 does not require rebasing them. |
| 2026-11-11 | **r8brft1 (idea 70's result fine-tune of r8btd90) promoted to the default network (owner, about 6:35 AM EST: "Promote r8brft1 per the adoption checklist").** Kaggle fork-retrain-8b-rft v1 at 43f6ecc (docs/research/retrain-8b/rft-plan.md, branch retrain/8b-rft, declared before any run): warm from r8btd90's window average (its float weights), result weight 1.0 (the game result as the whole target), LR 1e-5 constant, 60 superbatches on g4s1 (arm c's 129 files), two seeds; each candidate the mean of superbatches 46-60. Both seeds passed the gates at S = 88 (matched to the base net's mean \|eval\|; netcheck exact on 446; r8brft1's quantization loss max 10.7 cp, p99 8.4 cp, 1 of 311,296 link weights clamped); the endgame check 7 of 900 for each (r8btd90 7). Fixed-node screens against r8btd90 (800,000 nodes per move, 1,600 games each): **rft1 +7.17 ± 9.93** (run 42962187538), rft2 +6.73 ± 9.44 (42966665389); rft1 (bake/r8brft1 4da54db) went to the STC SPRT [0, 5] against r8btd90 (r8b-rft-stc): **+5.74 ± 3.81 Elo (nElo +9.69 ± 6.43), H1 accepted** after 7 stages, 11,200 games, LLR 3.34, ptnml [131, 1331, 2511, 1476, 151] (runs 42974677403, 42976787971, 42979050772, 42981298644, 42983543508, 42985980827, 42988446282; H1 at 3:55 AM EST; sprt-log). Promoted under its bake name; r8btd90 and S512ppr3 stay buildable (r8btd90 joins CI's `nets` job); the web page adds r8brft1 as its default at its next redeploy; tools/gauntlet/transfer.json gains its `adopted` entry (+5.74, ci95 3.81). Bench 10,708,227 / c5dfc0ec1923d3b0, the bake branch's own (the bootstrap's 11,537,913 / 90153d2b0f5a37f1 unchanged). **The labeller policy (owner):** the label-depth arms stay on S512ppr3 and the cloud slice on r8btd90 until each finishes; g4c and later parts use r8brft1, each from a fresh build of the promoting commit, bench-checked against tests/bench-r8brft1.ref. |
| 2026-11-11 | **Retrain 8b's keep rules decided; idea 69 dropped; seed noise measured (owner, about 6:35 AM EST).** Head-to-heads against the control r8bc (bake/r8bc 33da6a5; 800,000 nodes per move, 1,600 games each; plan §3 items 6 and 7; sprt-log): td90 **+4.13 ± 9.47** (run 42935666743), td80 −0.87 ± 9.13 (42930415181), i52 −4.13 ± 9.60 (42925024784). (1) **TD(0.9) labels stay in the standard retrain recipe** (idea 51: td90 above the plan's +4 keep line, its endgame check 7 of 900 as the control's); td80 and i52 not kept. (2) **Idea 69 (class-weighted sampling, the cw arm) dropped**: its STC SPRT r8b-stc-cw [0, 5] against r8bc **H0 accepted, −7.60 ± 4.91 Elo** (nElo −13.18 ± 8.51) after 4 stages, 6,400 games, LLR −4.16 (runs 42949849410 to 42955981034), after a fixed-node screen of +3.04 ± 9.74 against S512ppr3 (42940727058) and a head-to-head of +3.04 ± 9.25 against the control (42945518194). (3) **Seed noise measured**: c2, the control re-run with another seed (bake/r8bc2 38155d9), against r8bc **−6.08 ± 9.42** (1,600 games at 800,000 nodes, run 42958000486), so one seed's head-to-head can move by about 6 Elo on the seed alone: **every future retrain arm runs 2 seeds**. |
| 2026-11-11 | **Batch 4: structure not passed, no retry; cut-node pre-approved on its LTC (owner, about 6:35 AM EST).** Both design R STC SPRTs ([0, 6] nElo, beta 0.20, cap 8, futility look after 2 stages) against tier2/b4-r14 ff0c088 (batch 4 on phase-4 after R14, every switch off; S512ppr3 base): (1) **the structure history at weight 5 (R21; tier2/b4-structure-r14 ec00954) capped undecided, +2.93 ± 3.46 Elo** (nElo +5.10 ± 6.02) after 8 stages, 12,800 games, LLR 1.33 (b4-structure-stc, runs 42964043071 to 42979311765): not passed; **"No retry of structure"** (owner), so its switch stays off. (2) **Cut-node (R4, CutNodeLmrPlies 1, the head-to-head's pick over 2; tier2/b4-cut-node-r14 6b4e407) H1, +6.02 ± 3.67 Elo** (nElo +10.55 ± 6.43) after 7 stages on fresh openings from stage 2, 11,200 games, LLR 4.20 (b4-cut-node-stc, runs 42948984895 to 42961813575). Its LTC confirmation b4-cut-node-ltc (40+0.4, design R) is running; **pre-approved: adopt cut-node (1 ply) if its LTC confirmation passes; report if it fails** (owner). |
| 2026-11-11 | **Cut-node (1 ply) adopted on its LTC pass, pre-approved by the owner 2026-11-11.** b4-cut-node-ltc (40+0.4, Hash 64, design R [0, 6], cap 6, fresh openings from stage 2; test 6b4e407 against off ff0c088, S512ppr3 on both sides): **+9.75 ± 5.14 Elo** (nElo +18.28 ± 9.64), Ptnml [23, 537, 1250, 649, 37], **H1** (LLR 3.79) after stages 2-4, 4,992 games (runs 42991551149, 43002660790, 43013618465; H1 at 7:59 AM EST), after the STC's +6.02 ± 3.67 (11,200 games). Ported onto phase-4 b5f11ae alone, on branch adopt/cut-node: the switch `UseCutNodeLmr` (on), PlyFrame::expected_cut and its three assignments (root, moves loop, null move), the LMR term and CutNodeLmrPlies 1 in the parameter table, the same code and value as tested; no other batch-4 code. Bench 9,942,973 / accfb975ccd6ccf5 with r8brft1 (10,708,227 / c5dfc0ec1923d3b0 with the switch off, phase-4 b5f11ae's); with S512ppr3 10,280,126 / 7db684469b226aa7, the tested commit 6b4e407's own tests/bench-s512ppr3.ref, which shows the port equals the tested code. Every network's reference and the bootstrap's (13,042,891 / c6cc076a5ba69b09) re-pinned in the adopting commit. Recorded: the SPRT log, the constants table, ideas.md (idea 43), tools/gauntlet/transfer.json (the adopted entry: the STC result +6.02, ci95 3.67, with the LTC as its `ltc` field). Name screen of expected_cut, use_cut_node_lmr, UseCutNodeLmr, CutNodeLmrPlies and cut_extra: no match in Stockfish, Ethereal, Berserk or Weiss; the constant matches Berserk's current branch (credited, ORIGINALITY.md). The switch stays until the Phase 4 re-validation. Labeller policy (decision 24): the next part switch takes a fresh PGO build of this commit (at most one switch per day); the play build is rebuilt. |
| 2026-11-11 | **Root-gap time management (idea 61, part 6) dropped (owner, about 3:30 PM EST).** Its constants by head-to-head (round robins, STC, 9,600 games each): RootGapBand **b7** over the placeholder b14 (+16.20 ± 9.83 nElo; b28 −5.03 ± 9.83; job i61-rg-band), then RootGapExtra **x333** over the placeholder x667 at b7 (+7.41 ± 9.83 nElo; x1000 −5.68 ± 9.83; job i61-rg-extra). The design R STC SPRT i61-rg-stc ([0, 6] nElo, beta 0.20; 00d6e61 against off 320e2f2, fresh openings from stage 4): **H0 accepted, −4.89 ± 7.03 Elo** (nElo −8.36 ± 12.04), LLR −1.81 after 2 stages, 3,200 games (runs 43012786722, 43015340549; try 1 of 2; sprt-log). The owner chose to drop it rather than use the second try: the switch stays off on its branch and nothing reaches phase-4. |
| 2026-11-11 | **Idea 52 (ensemble-disagreement active learning) retired under its keep rule (owner, about 3:30 PM EST).** The i52 arm's head-to-head against retrain 8b's control r8bc was −4.13 ± 9.60 (run 42925024784, 1,600 games at 800,000 nodes), below the declared +5 keep line, so idea 52 is retired and the scratch-run rule (one from-scratch run per retrain as the committee member) is dropped. This confirms the consequence the keep-rules row above (and ideas.md 52) left UNVERIFIED; the mark is removed. |
| 2026-11-11 | **T56 any-attack adopted on its LTC pass, pre-approved by the owner 2026-11-11** (8:35 AM EST: "T56 any-attack: pre-approved for adoption if its LTC confirmation (item 64) passes"). Test sprt/threat-any bfbc1c8 against off tier2/threat-any dc341d5 (r8btd90 on both sides), design R [0, 6]: STC t56-any-stc **+7.49 ± 4.89 Elo** (nElo +13.04 ± 8.51), **H1** (LLR 3.19) after stages 3-6, 6,400 games (runs 43017939593, 43020606092, 43023298002, 43025985854; 8:23 AM EST); LTC t56-any-ltc (40+0.4, Hash 64, 1,664 games a stage, cap 6) **+8.07 ± 5.15 Elo** (nElo +15.12 ± 9.64), Ptnml [20, 563, 1227, 653, 33], **H1** (LLR 3.01) after stages 3-5, 4,992 games (runs 43029851342, 43068666654, 43081871545; 3:13 PM EST; stage 4's runs 43042667430, 43048079900 and 43050144902 failed in the build job's toolchain step before any game, an Ubuntu-archive DNS outage, and were rerun; sprt-log). Ported onto phase-4 4470f24 alone, on branch adopt/t56-any: the four-bucket butterfly history (`ThreatBuckets` 4, `threat_bucket`), `Position::attacked_squares`, the selector's lazy threat set and the bucket reads and updates in the selector, record_cutoff and the LMR context, the same code as tested, with `UseThreatBuckets` on. Bench 10,166,167 / d874b380155a2e8c with r8brft1 (9,942,973 / accfb975ccd6ccf5 with the switch off, phase-4 4470f24's); with r8btd90 and cut-node off 9,236,850 / 0f723ee4c163a419, the tested commit bfbc1c8's own tests/bench-r8btd90.ref, which shows the port equals the tested code. Every network's reference and the bootstrap's (12,001,180 / e03ee8c75aa45fbe) re-pinned in the adopting commit. Recorded: the SPRT log, the constants table (ThreatBuckets), ideas.md (idea 72), tools/gauntlet/transfer.json (the adopted entry: the STC result +7.49, ci95 4.89, with the LTC as its `ltc` field). No new names (T56's screens of 2026-11-02 and 2026-11-10, ORIGINALITY.md). Speed not measured (UNVERIFIED). The switch stays until the Phase 4 re-validation. Labeller policy (decision 24): the next part switch takes a fresh PGO build of this commit (at most one switch per day); the play build is rebuilt. |
| 2026-11-11 | **ProbCut gets one LTC-only design R test on the tuned search (owner, 3:10 PM EST: "ProbCut: I lift the no-retest rule for ONE LTC-only design R test on the current default (tuned search); record it as LTC try 1 of 2. Start it now in the free lane.")** The no-retest rule after its STC H0 (probcut-d9r5m80-vs-base on S512r2, −5.29 ± 3.58 Elo after 12,800 games, 2026-11-06) is lifted for this one test only. ProbCut (T31, d9-r5-m80: CaptureProbeMinDepth 9, CaptureProbeReduction 5, CaptureProbeMargin 80, the measured values) is ported onto phase-4 4470f24 (r8brft1, R14, cut-node on) behind `use_capture_probe`, off: tier2/probcut-r2 a40b1ff (bench 9,942,973 / accfb975ccd6ccf5, phase-4's), test sprt/probcut-r2 d145d40 (bench 9,903,350 / 95f7f190cf02d64e). Design R at LTC only (40+0.4, Hash 64, 1,664 games a stage, cap 6, [0, 6] nElo, beta 0.20, futility look after 2 stages), ledger idea `t31-probcut`, **LTC try 1 of 2** (the STC SPRT predates the try ledger; no override is needed for a first try), fresh openings from stage 8 (past ProbCut's STC stages 0-7), night queue lane A item 18 (probcut-ltc). Both sides are the default at the owner's instruction (4470f24): T56 any-attack, adopted at 3:43 PM EST (db0bb31), is in neither; the driver started at 3:55 PM EST. No STC retest. An H1 goes to the owner; nothing is adopted before then. |
| 2026-11-11 | **ProbCut's LTC test runs on db0bb31's engine (T56 on): probcut-ltc2.** The one LTC-only design R test now runs on phase-4's current engine, db0bb31 (r8brft1, R14, cut-node and T56 any-attack on): the coordinator moved it (about 4:00 PM EST) because T56 any-attack was adopted at 3:43 PM EST (db0bb31), so "the current default" of the owner's exception includes T56; the first version (probcut-ltc, base a40b1ff / test d145d40 on 4470f24) was stopped before any stage was dispatched, so no try was spent. Base tier2/probcut-r3 d47e479 (bench 10,166,167 / d874b380155a2e8c, phase-4's), test sprt/probcut-r3 6d7ffb1 (bench 9,639,207 / 07f7ae19b9250f38); a new SPRT name, probcut-ltc2 (probcut-ltc's design file holds no runs); the same ledger idea t31-probcut, still LTC try 1 of 2; the same fresh openings from stage 8; night queue lane A item 18. tier2/probcut-r2 and sprt/probcut-r2 stay as they are, unused. |
| 2026-11-11 | **Gauntlet of phase-4's head (r8brft1 + the R14 tuned search + cut-node + T56 any-attack): Fork 3510.5 ± 20.5; paired gain +19.4 over 3488.2; gap to Stockfish 19 −201.4; transfer ratio of the window 0.28 (owner, about 3:30 PM EST).** Run **43103327654** on phase-4 db0bb31 (update.sh, gcc 11.4, x86-64-v3; bench 10,166,167 / signature d874b380155a2e8c and network r8brft1's parity checked on the runner, as tests/bench-r8brft1.ref), 4:28-4:52 PM EST, every shard 100 of 100, all 1,800 games ended normally (no time forfeits); no SPRT ran beside it. The first dispatch, run 43098344274 (a push of db0bb31 to gauntlet-run at 3:50 PM EST), was created during GitHub's Actions major outage and never got a job (an outage casualty: it still lists as queued with no jobs and cannot be cancelled); the coordinator dispatched 43103327654 by hand on gauntlet-run (workflow_dispatch, no old/new inputs, so the gauntlet). 200 random 8-ply openings, 10+0.1. Ordo, CCRL Blitz scale, 1,400 games against the seven standing anchors (956.0 points, 68%; white advantage 125.1 ± 10.1, draw rate 24.9% ± 1.6). Opponents' scores against Fork: Clover 6.1 (3639) 144.5 of 200, Altair 7.0.0 (3579) 110.0, Marvin 6.3.0 (3458) 82.0, Laser 1.7 (3292) 39.5, Winter 0.9 (3168) 29.0, Monolith 2.01 (3061) 23.0, Weiss 1.0 (2896) 16.0. **Paired gain over the 3488.2 gauntlet** (run 42538371594, 32c5517; report.py's level 0, plain logistic, paired by opening, all seven anchors shared this time): **+19.4 Elo, bootstrap SD 9.2, 95% interval +1.2 to +37.3** (1,400 games each); per anchor Altair +41.0, Clover +11.0, Laser +48.0, Marvin +14.3, Monolith −37.1, Weiss 0.0, Winter +6.9 (SDs 17-37). Ordo's published ratings differ by +22.3. **Gap to Stockfish 19** (sf_19, outside the fit): Fork 95.5 of 400 (23.9%), +59 =73 −268, **Elo −201.4, 95% interval −228.9 to −176.0** (pentanomial, 200 pairs, [68, 73, 59, 0, 0]), against −222.4 on 2026-11-08; Fork's fitted 3510.5 against Stockfish's CCRL 3792 is −282 on the list's conditions. **Transfer ratios** (plain logistic; interval: each bootstrap draw of the gain over a normal draw of the SPRT sum, SE from the entries' ci95): (a) **this window**, the five changes adopted since 32c5517 (transfer.json entries R14 SPSA tuned margins +37.93, r8btd90 +12.17, r8brft1 +5.74, cut-node +6.02 STC, T56 any-attack +7.49 STC; sum +69.35 ± 13.6): gain +19.4 / 69.35 = **0.28, 95% interval 0.02 to 0.56** (gap −49.9 ± 11.5 Elo, 1 SE); (b) **report.py's running ratio** since its baseline gauntlet (run 41465146207, 3902d00; all ten transfer.json entries: those five plus S512+PP, select_best 5ba7d0d, S512ppr2, S512ppr3, time management (b); sum +153.9 ± 20.5): anchor gain +73.6 (SD 11.8, +51.3 to +97.4) on the six anchors the baseline shares (Clover not in it), ratio **0.48, 95% interval 0.33 to 0.66** (0.61 on 2026-11-09). The window's LTC results (cut-node +9.75, T56 +8.07) are not in either sum, which uses each change's STC figure as transfer.json records it. tools/gauntlet/transfer.json's "previous" moves to this run. Result: ~/fork-data/gauntlet/run-43103327654 (79 files, SHA-256 manifest verified). |
| 2026-11-11 | **Quiet history pruning (B13) rebuilt with a threshold that fires, then design R at STC (owner, 3:10 PM EST: "Build quiet history pruning (B13) with a threshold chosen to actually fire (quick measurement first), then design R at STC").** Fork's earlier form and names (tier2/b4 d2b086d, dropped 2026-11-10 when it changed 30 bench nodes) on phase-4 b2e083e (T56 on), behind `use_history_skip`, off: tier2/qhp-t56 c84722b, bench unchanged (10,166,167 / d874b380155a2e8c). The quick measurement (tools/tier2_measure/history_skip.json, rule declared before its run): on the bench, which clears history per position, the eligible quiet moves' scores sit within a few hundred of zero; in 48 replayed SPRT games with history carried, the values predicted to skip 5%, 10% and 20% are **2000, 1300 and 700 per ply**, which with the switch on skip 13.9%, 26.2% and 44.1% (bench 11,081,805, 10,008,258, 9,886,698). `HistorySkipMaxDepth` stays 3 (the earlier placeholder; matches Ethereal, nearly Weiss: credited). Chosen by the head-to-head (lane B item 66, qhp-h2h: round robin, 2 stages of 1,600 games a pairing at STC, 2000 kept on a tie), then design R at STC against off (item 67, qhp-stc, fresh openings from stage 2; ledger idea `qhp`, try 1). Test commits sprt/qhp-t56-2000 c06d62b, sprt/qhp-t56-1300 f6397e0, sprt/qhp-t56-700 13d4d05; a first build on 4470f24 (tier2/qhp, candidates 2300, 1600, 900) was superseded before any game when T56 changed the history it reads. Nothing merged into phase-4 before the verdict. ideas.md idea 74. |
| 2026-11-11 | **Transfer diagnostic: the anchor check on the SPRTs' unbalanced book gives +45.5 (95% +21.7 to +70.1) for db0bb31 over 32c5517, against +27.1 on the same two anchors in the balanced gauntlets; the difference is not resolved, so self-play inflation is the next thing to examine (owner, about 5:15 PM EST: "Transfer diagnostic (one run, before any further conclusion) ... If it's much closer to the SPRT sum than the balanced gauntlet's +19.4, record that Fork's adopted gains transfer mainly in unbalanced (TCEC-like) positions; if not, look into self-play inflation next").** The anchor check gained an optional input book (commit 2a23bc4, workflow only): empty keeps the balanced 8-ply openings; uho plays the SPRTs' book as their shards get it (tools/cloud/fetch_tools.sh: UHO_Lichess_4852_v1, its seed-20261027 shuffled copy, both SHA-256-pinned), its first 200 lines in the shuffled order, each with both colours; TC, games, anchors and the paired report unchanged; the gauntlet path is untouched (diff read; the run's title showed the run-name expression works; no gauntlet has run on the new file yet). Run **43109946231** (phase-4 2a23bc4, 5:13-5:37 PM EST): OLD 32c5517 (s512ppr3, bench 14,149,617 / 1cb0717f040c294d) and NEW db0bb31 (r8brft1, 10,166,167 / d874b380155a2e8c), each against Clover 6.1 and Altair 7.0.0 at 10+0.1, Hash 16, 1,600 games, all 16 shards 50 of 50 per version, every game terminated normally, 200 distinct openings. report.py --check (plain logistic, paired by opening, 4,000 bootstrap resamples, seed 20261109): **pooled +45.5 Elo, SD 12.2, 95% +21.7 to +70.1**, outcome confirmed (claim +69.35: gain over the claim 0.66); Clover +53.4 (SD 16.4, +20.7 to +85.4; OLD 77.5/400, NEW 98.5/400), Altair +42.5 (SD 16.5, +10.0 to +75.0; OLD 149/400, NEW 172.5/400). **Comparison** (the same paired method on the balanced gauntlets 42538371594 and 43103327654, restricted to Clover and Altair, 100 openings, 400 games each): pooled +27.1 (SD 12.5, +2.9 to +51.9); Clover +11.0, Altair +41.0. Transfer ratios over the SPRT sum +69.35 ± 13.6: UHO 0.66 (95% 0.31 to 1.05), balanced two-anchor 0.39 (0.04 to 0.78), balanced seven-anchor 0.28 (0.02 to 0.56). Gap to the sum: UHO −23.9 (95% −51.3 to +3.6, so consistent with full transfer), balanced seven-anchor −49.9 (−72.4 to −27.4). **Judgment, by the intervals: not "much closer".** The point estimate moved toward the sum (the gap halved), but the like-for-like difference, UHO minus balanced on the same two anchors, is +18.4 (SE 17.4, 95% −15.7 to +52.6), and against the seven-anchor +19.4 it is +26.1 (95% −3.9 to +56.1): neither excludes zero, so this run does not show that the adopted gains transfer mainly in unbalanced positions. Recorded: **self-play inflation is the next thing to examine**; the book effect is not ruled out (UHO's interval reaches the sum, the balanced one does not). Caveat: the check's openings 1-200 of the shuffled book are the first ones every SPRT's stage 0 plays (its first shards), so the adoptions were partly measured on them. Result: ~/fork-data/gauntlet/run-43109946231 (107 files, SHA-256 manifest verified). |
| 2026-11-11 | **The engineering review (docs/research/engineering-review-2026-11-11.md, a read-only review of d1fe24b) and the owner's decisions on it (owner, about 6 PM EST; no runs now, the current queue continues).** (1) **Re-sequence:** minimal Lazy SMP becomes the next major engineering item after the current queue, ahead of the removal round (§5.6 step 18) and the final retune (step 19); new step 17a. (2) **Testing policy, adopted now:** (a) **pressure-matched hash** for TT-policy tests (Hash chosen so nodes per move over TT entries matches TCEC's, about 1); (b) the **regime-change retest rule**: after a change worth more than 20 Elo (a retune or a net), every rejected consensus idea (four or more engines report a gain) gets one new try, outside the two-tries count; (c) **the gauntlet is the truth** and self-play the screen, with an **anchor check every 2-3 adoptions**. (3) **Plan:** step 9's speed-price measurement at STC, LTC and VLTC, plus a first EPYC reading on the cloud VM; a long from-scratch training run (20-40 B samples) on a rented GPU, **costed for the owner's decision**; king-relative inputs (buckets, or the review's offset form) in bake-off round 3. (4) **TCEC hazards, scheduled before any entry:** a halfmove-clock guard on TT cutoffs; Syzygy probe-depth and probe-limit options for 7-man tables; a CPU-feature check at startup; score calibration; null-move verification at high depth; the TCEC build with PGO. (5) **The review's flagged facts and decisive file:line claims verified** (the review's appended verification section): the TT-PV flag is stored and never read; TT cutoffs ignore the halfmove clock; Syzygy probes from depth 1 (only at a zero halfmove clock); a run is 1.80 B samples (305 batches of 16,384, 360 superbatches; the trainer default is 6,104); EPYC 9754 L3 is 2 MB per core (secondary source; AMD's page timed out). None was wrong. |
| 2026-11-11 | **The bug review (docs/research/bug-review-2026-11-11.md, read-only, engine db0bb31) and the owner's decisions on it (owner, about 6:20 PM EST).** The review found no correctness bug in the engine (7,000 positions with legal moves and PVs, mate and tablebase claims, determinism and eval symmetry checked against python-chess). (1) **E1** (a search stopped mid-iteration plays the previous best move unless the new exact best beats the previous iteration's score): fix it so that, once the previous best has been re-searched in the unfinished pass, that pass's best exact move is accepted; then design R at STC, then LTC; no special instrumented build. (2) **E2** joins the TCEC hazards list: the time manager's depth-19 clamp (a stable best move gets the 0.36 floor beyond depth 19) is to be redesigned for deep searches and tested at VLTC. (3) **Now, without bench changes:** E3 (a bound on the output layer's 32-bit sum in the loader, or a 64-bit reduction); E4 (a UCI info line saying Threads is ignored by the search, and the hash clear respecting Threads); E5 (one TT age advance per datagen move); T2 (gate the shipped, clamped net and move the clamp script into the repo); T3 (merge only finished, complete shards); T6 (unique SPRT run titles per lane); the trainer's `--keep-all` flag bug (T9); jobctl's PID-reuse staleness (T8). (4) **T1:** a held-out endgame check with zero overlap with any slice data is built, and the current default and S512+PP are re-measured on it; the old endgame figure ("351 → 8") is a **recall** figure, not evidence of understanding: 509 of the 900 check positions appear verbatim in a slice file. (5) **T4:** the transfer ratio is corrected for the SPRT stopping bias in its denominator, or reported with that known upward bias (so the 0.28 of 2026-11-11 understates transfer by an unknown amount). (6) **T5:** check whether scale matching is dominated by large evals, and report. |
| 2026-11-11 | **Gating of the review work (owner, about 6:40 PM EST; applied to the night queue the same evening).** **Blocking, before new additions start** (tests already running may finish): T3 (merge only finished, complete shards) and T6 (unique run titles per lane) first; then E1's fix with its SPRT, so later tests use the corrected engine. **Before the next network decision (8c):** T2 (gate the shipped, clamped net; the clamp script in the repo), T1 (the held-out endgame check), the T5 check, and the training-data audit's validation/training overlap check. **Before the next gauntlet reading:** T4 (the transfer ratio's stopping bias). **In parallel, non-blocking:** E3, E4, E5, the trainer's --keep-all bug (T9), jobctl's PID-reuse staleness (T8); a read-only concurrency design review; the E2 long-TC check on the cloud VM; the decision audit as filler. **Before any TT-policy test:** the pressure-matched hash. **End of Phase 4 / pre-TCEC:** mutation testing round 2, the TCEC hazards (E2's fix included), the full TCEC dry run after SMP, release reproducibility, the Fathom review. **In the queue:** gate files in ~/fork-jobs/night/state: gate-t3-t6.done (written by the coordinator once T3 and T6 are committed and installed in the runner worktrees; E1's SPRT items wait for it) and gate-e1.done (written once E1's SPRT has decided; every new test item waits for it: B13's SPRT item 67, the correction-table and D8/D9/D13 items, and the label-depth items through ld.sh). |
| 2026-11-11 | **The engine survey's history-and-ordering group, D8, D9 and D13, built behind switches (off) and queued for design R at STC, gated behind E1 (owner, 3:10 PM EST: "the survey's top cheap techniques: D8 (summed continuation update), D9 (failed-child prior-move bonus), D13 (direct-check ordering bonus), each design R at STC"; gate, about 6:40 PM EST: new tests start only after E1's fix has had its SPRT).** Each on its own branch from phase-4 784b1b0 (r8brft1, R14, cut-node and T56 on; bench 10,166,167 / d874b380155a2e8c, unchanged with each switch off): **D8** tier2/d8-pair-sum 55bb786 (`use_pair_sum_update`: each pair-table entry's self-limiting term reads the reply and follow entries summed; no constant), test sprt/d8-pair-sum 8ffc602 (bench 10,236,778); **D9** tier2/d9-prior-credit ef30f4f (`use_prior_move_credit`: a fail-low node credits the parent's quiet move with `PriorCreditQuarters`/4 of the cutoff bonus at its depth), candidates 1, 3 and 6 quarters (sprt/d9-prior-credit-1 37f8a43, -3 39074b1, -6 bb59b7f; bench 9,560,037, 10,516,912, 10,270,243); **D13** tier2/d13-check-order ceb984a (`use_check_order_bonus`: a quiet giving direct check adds `DirectCheckBonus` to its ordering score), candidates 2500, 5000 and 10000 (sprt/d13-check-order-2500 006ae9c, -5000 5a99405, -10000 90338de; bench 10,246,388, 10,253,460 and 9,776,602). **Screens** (ORIGINALITY.md): every new name no match; D8's form and D13's candidates no match; D9's first candidates 1× and 2× the cutoff bonus **matched Stockfish 7-15.1** and were replaced before any game by 0.25×, 0.75× and 1.5× (1.5× a near match to one case of Stockfish 16.1, credited). **Queue, lane B after B13's items 66 and 67:** item 68 survey-d8-stc (design R against off from stage 0; ledger idea `d8-pair-sum`, try 1); 69a survey-d9-h2h (round robin, 2 stages a pairing at STC, 1 kept on a tie) and 69b survey-d9-stc (the winner against off from stage 2; `d9-prior-credit`, try 1); 70a survey-d13-h2h (2500 kept on a tie) and 70b survey-d13-stc (`d13-check-order`, try 1). Each item exits 20 until state/gate-e1.done exists; if E1 is adopted first, the OFF and test commits are rebased onto the new head before they run. A new runner script, ~/fork-jobs/night/survey-hist.sh (qhp.sh's pattern plus a direct mode for a switch with no constant). Dry runs (SURVEY_DRY, against the agent's worktree as the runner): each item prints its h2h_run.sh or sprt_run.sh command, and the SPRT modes report "try 1 of 2" from the ledger. Nothing merged into phase-4 before the verdicts (phase-4 has since moved to d570322 with tools and docs only, so the engine is the same). ideas.md 75-77. Before these, phase-4 784b1b0 fixed the stats preset's failing search_stats case: since cut-node's adoption the X2 probe compared a reduction without CutNodeLmrPlies against the real one with it (220,179 counted changes for 40 firings); the probe now keeps the term (29 changes), verified on clang-stats, which CI does not build. |
| 2026-11-11 | **The drift tables built, ranked passively, and queued in the ranking's order (owner, 3:10 PM EST: "Build R34's non-pawn correction tables plus E4's minor/major/threat tables, then the planned passive ranking and SPRTs of the best"; 5:20 PM EST: "use the passive ranking only to order the tests; no table is dropped on the offline ranking alone. If the first picks fail their SPRTs, test the next ones too"; 6:40 PM EST: new tests wait for E1's fix and its SPRT).** On tier2/corr-tables (from phase-4 54046a7): four eval correction terms on the pawn drift table's design (its update rule, weights, limit, grain and slot count, measured in T32), each keyed by its own Zobrist-based hash and behind its own switch, all off: per-colour pieces with the king (R34; the term is the two tables' mean), minor (knights and bishops), major (rooks and queens), and Fork's threat configuration (E4). A switched-on term times its share is added to the eval that pruning and the quiescence stand-pat estimate with; the TT keeps the raw eval; the material keys are kept by play() in a per-ply array beside the frames (PlyFrame's size guard) only while a table is in use. Commits 201277c (the tables and the declared ranking tool) and 2992817 (test), bench unchanged 10,166,167 / d874b380155a2e8c. The passive ranking (tools/measure/drift_rank.py, declared in tier2/corr-tables 201277c before the run): 120 of r8b-rft-stc's games (seed 20261111, 7,943 test-engine positions) replayed at 200,000 nodes by a stats build with every table learning and none applied, X10's ledger at 1 in 512 (818,437 RFP and 228,064 futility rows, 58,297,740 learning nodes). Decision-accuracy gain G (right minus wrong flipped prune decisions per 1,000 ledger rows; 95% bootstrap over games): **threat +17.95 [+16.11, +19.54], minor +14.44 [+12.56, +16.23], major +9.82 [+8.47, +11.07], pieces +7.51 [+6.60, +8.43]**; every neighbouring pair separated (paired 95% intervals above 0), so no tail-fitness swap. Tail fitness (raw error over 100 cp): threat 0.711, minor 0.707, major 0.753, pieces 0.769. Every table's gain is at RFP (+10.3 to +24.5); at futility rows every table loses (−2.6 to −5.5 per 1,000 futility rows). Report-only LTC proxy (the first 60 games at 1,000,000 nodes): the same order, threat +21.67, minor +18.52, major +13.81, pieces +11.40. The summed fitness (0.73-0.80) is not comparable with the pawn drift's 0.919: here the learning nodes are chosen by the raw eval's error direction, there by the drifted estimate's. **Test order (owner, 2026-11-11: the ranking orders the tests only, it drops no table): threat, minor, major, pieces**, each a design R STC SPRT against off (tier2/corr-tables 2992817) at its share's natural value 64 (the whole learned drift), and only if that fails a retry at 32 (half; try 2), with no head-to-head (owner, 7:45 PM EST: the shares are final-retune SPSA dimensions; a pass is adopted, pre-approved, and its share joins the final retune), night queue lane A items 19-corr-a to 19-corr-h, gated on state/gate-e1.done (owner, 6:40 PM EST: after E1's fix has had its SPRT; the commits may need rebasing onto the then phase-4 head). SPRT test builds (each the base plus one switch on; bench with r8brft1): threat 32 cf2b1a6 9,333,289 / 64 b45805b 10,031,831; minor 32 69d8715 9,633,320 / 64 2863375 9,450,299; major 32 4670eae 10,491,831 / 64 f971027 9,921,799; pieces 32 7b2387b 10,633,651 / 64 b9e40cb 9,811,399. Try-ledger ideas r34-piece-drift, e4-minor-drift, e4-major-drift, e4-threat-drift. Names and constants screened (no name or value match; concept near matches credited, ORIGINALITY.md). Nothing is adopted before its SPRT; speed not measured (UNVERIFIED). |
| 2026-11-11 | **The bug review's T1, T4 and T5, done (docs/research/bug-review-followup-2026-11-11.md; tools and documents only, bench unchanged).** **T1, the held-out endgame check** (tools/nnue/endgame_heldout.py, positions committed as tools/nnue/endgame_heldout.tsv): 3,800 positions, 200 in each of 16 four-piece classes and 3 five-piece ones (queen against two minor pieces) that the slice cannot generate (its signatures are KPvK/KQvK/KRvK and 103 five-piece classes; no four-piece class), with endgame_check.py's rules and thresholds unchanged; **zero overlap** by an exact board-and-side match against all 28,599,940 records of the eleven slice files (the same match finds **898 of the old check's 900**, 509 in slice1-01 alone, the review's count), so the old figure is recall. Misjudged of 3,800: **r8brft1 612, S512+PP 945**, S512ppr3 514, r8btd90 526, S512ppr2 454, S512r2 658 (four-piece: r8brft1 423, S512+PP 830; five-piece: 189 and 115). The slice generalised to the four-piece endings but queen against two minors got worse (S512r2 27 of 600), and the held-out count has risen since S512ppr2 while the old check stayed at 7-8. The records now call the old figure recall; the ≤ 15 of 900 gate stays as a recall gate (named the integrity/recall gate since 2026-11-12, owner). **T5, scale matching:** on the gates' own inputs 45-48% of the control's Σ|eval| comes from positions above 400 cp (not 56%); median, ≤ 400 cp means and slopes move S by at most 1-2 units, only on S512+PP (90 → 91 by two of five) and S512ppr2 (89 → 90-91), within the 4,000 positions' own noise (92-96 games); no bug, no shipped S to change; if the gate is revised, the mean over |control| ≤ 400 cp from more games. **T4, the stopping bias** (tools/gauntlet/stopbias.py, exact under the SPRTs' normal model; report.py prints both corrections; transfer.json records each SPRT's design, stages and nElo): **window since 32c5517 0.28 recorded, 0.29 median-unbiased at each stop stage, 0.31 with the selection bias also removed by plug-in; running ratio 0.48, 0.49, 0.51.** The median-unbiased estimate removes only the stopping rule's part (a passed design-R test still overstates a true 6 nElo by +4.4, raw +5.1); the plug-in is a sensitivity, not a bound; the selection part needs a prior over tested ideas' effects (empirical Bayes over every SPRT), not done. The stopping bias explains a few Elo of the window's −50 gap, not the gap. |
| 2026-11-11 | **Two standing rules for constants, and D9 and D13 re-planned under them (owner, about 7:35 and 7:45 PM EST).** (1) **Natural values are not replaced just because they match another engine; they are credited instead** (ORIGINALITY.md): D9's 1× the cutoff bonus (4 quarters), found in Stockfish 7-15.1 by the screen, comes back as a candidate and is credited; 1.5× stays credited (unused); 2× stays out. (2) **A constant that the final retune's SPSA will tune gets no head-to-head before it**: one design R SPRT at STC at its natural value against off, adopted if it passes (pre-approved by the owner) and then a dimension of the final retune (docs/research/phase4-designs/final-retune.md §3.1); if it fails, one retry at a second value, within the two-try limit. Head-to-heads stay only where a constant will not be retuned later, or where the values differ in kind. Applied: **D9** natural value 4 quarters (sprt/d9-prior-credit-4 83fb64b, bench 9,946,948 / 9feddb70e3ad7ea6), item 69a survey-d9-stc (try 1), retry 3 quarters (sprt/d9-prior-credit-3 39074b1), item 69b survey-d9-retry (try 2; not ready until 69a's verdict, done with a note if 69a passed); **D13** natural value 5000, half a history table's range (sprt/d13-check-order-5000 5a99405), item 70a survey-d13-stc (try 1), retry 2500 (006ae9c), item 70b survey-d13-retry (try 2). The 1- and 6-quarter and 10000 commits stay on GitHub, unused. D8 unchanged (item 68). Every item keeps the E1 gate first; survey-hist.sh gained a retry mode (fresh openings from the stage after the first try's last). h2h_run.sh had already been extended to four values (a round robin of six pairings, tests pass: test_h2h_run.sh 24 checks, test_h2h_pick.py 7 tests) before the second decision; it stays on phase-4 as a tested tool, not installed in any runner. The constants-table rows on tier2/d9-prior-credit and tier2/d13-check-order still describe the head-to-heads; they are rewritten with the SPRT results at adoption. |
| 2026-11-11 | **Fable's novel ideas recorded as candidates (owner, about 8:30 PM EST; docs/research/novel-ideas-2026-11-11.md; ideas.md 79-86; novelty UNVERIFIED until a prior-art check).** No runs until the current queue clears its gates; offline probes use the cloud VM or idle CPU. Plan: idea 2 (label the unsaved split-search half, ideas.md 80) is an arm in retrain 8c (owner's definition: the same self-play games and the same number of training steps as the control; the arm samples from saved plus unsaved TD-labelled positions, the control from saved positions only; two seeds each); ideas 4 and 5 (82, 83) get their offline probes on the existing gold labels; idea 7 (85) its offline check; idea 1 (79) its fixed-node oracle, measuring accuracy and speed; idea 6 (84) after minimal Lazy SMP exists; ideas 3 (81, biases game results) and 8 (86, for bake-off round 3) are parked. |
| 2026-11-11 | **The targeted-data cap (owner, about 8:50 PM EST).** All targeted slices together (the Syzygy/ChessTB endgame slices, the positional slice and any later selected-start or selected-position data) make up **at most 5% of a training snapshot**. Newer slices of a kind **replace** older ones of the same kind rather than adding to them. Each slice must **win its arm test** (its retrain arm against the control, two seeds) to stay in the standard snapshot. Applies from retrain 8c on. |
| 2026-11-11 | **The ChessTB prober installed and the held-out 6-7-piece check built (owner's order, evening: "Create a program to read the chesstb tablebases or install the best available option").** The designed option: the python-chess fork's `chess.chesstb` at 38c108e with python-lz4, in its own venv in WSL (`~/fork-tools/chesstb-venv`), never in the engine or Fork's .venv (ORIGINALITY.md). Verified before use: 100,000 random 3-5-piece positions, every WDL class equal to Syzygy 3-4-5 (slice v2 design §5.1, check 1); every downloaded file's SHA-256 recomputed, equal to the manifest. **tools/nnue/heldout_67.py / .tsv:** 5,600 positions, 200 per budget-R material (23 six-piece, 5 seven-piece), the 4-5-piece set's placement plus slice v2's no-promotion rule, ChessTB WDL labels (300 spot-checked against the Lichess API, all equal), zero overlap with slice v1 and the 62 g4 and label-depth files; slice v2 must leave its positions out. Misjudged of 5,600: r8brft1 770, r8btd90 732, S512ppr3 723, S512ppr2 731, S512+PP 828, S512r2 809: the result fine-tune's step (r8btd90 to r8brft1) recurs at 6-7 pieces, significantly (58 to 20 discordant), mostly queen against rook and minor; the earlier steps do not (S512ppr2 against r8btd90 53 to 54). Reported by tools/nnue/gates.sh beside the 4-5-piece check, never a gate (docs/research/bug-review-followup-2026-11-11.md, T1 extension). |
| 2026-11-11 | **Retrain 8c after the held-out 6-7-piece check (owner, about 10:50 PM EST).** (1) **8c gets a slice-preserving result fine-tune arm**: the endgame slice kept at its normal weight during the fine-tune (the result fine-tune r8brft1 raised the held-out misjudgments at 4-5 pieces, 526 to 612, and at 6-7, 732 to 770), **plus a lower-LR variant if the Kaggle quota allows** (ideas.md 70). (2) **Endgame slice v2's materials include queen against rook and minor endings** (KQvKRBP among them), **the held-out 6-7-piece set's positions excluded** (ideas.md 68; docs/research/endgame-slice-v2/design.md). (3) **Every 8c arm reports both held-out checks** (4-5 pieces, tools/nnue/endgame_heldout.py; 6-7 pieces, tools/nnue/heldout_67.py). (4) **The 6-7-piece check's three choices are kept:** the 1.15 flag ratio (report only; since 2026-11-12, owner: flagged when more than 15% worse than the current default net, with the change against each run's warm start also reported), cursed wins and blessed losses counted as drawn, 200 positions per material. |
| 2026-11-11 | **ProbCut adopted on its LTC pass, pre-approved by the owner (overnight order of 2026-11-11: search items that pass their SPRT, and their LTC where required, are adopted one at a time onto phase-4's head).** probcut-ltc2 (40+0.4, Hash 64, 1,664 games a stage, design R [0, 6], cap 6; LTC try 1 of 2 under the owner's one-time exception; fresh openings from stage 8): test sprt/probcut-r3 6d7ffb1 against off tier2/probcut-r3 d47e479 (r8brft1 on both sides) **+9.40 ± 5.03 Elo** (nElo +18.03 ± 9.64), Ptnml [24, 516, 1283, 647, 26], **H1** (LLR 3.73) after stages 8-10, 4,992 games (runs 43109070620, 43120086216, 43129867831; 9:08 PM EST; sprt-log). Ported onto phase-4 a95e269 alone, on branch adopt/probcut (the same code lines as d47e479), with `UseCaptureProbe` on. Bench equivalence: with the switch off 10,166,167 / d874b380155a2e8c (phase-4's); with it on 9,639,207 / 07f7ae19b9250f38 with r8brft1, byte for byte 6d7ffb1's tests/bench-r8brft1.ref (the tested net), so the port equals the tested code. Every network's reference and the bootstrap's re-pinned in the adopting commit: r8btd90 9,091,714 / 57e94112c304cf12, s512ppr3 9,333,183 / 5ab710110234a9e9, s512ppr2 10,023,900 / cfb36dd211556b98, s512pp 9,219,152 / 9bae442f2b52447a, s512r2 10,193,933 / f3f673e4dc5527fd, s512 10,309,655 / d34eef88ec700f3e, b0r2 10,697,112 / 4f942d2ed6637187, b0r1 11,453,302 / de5d88741b784504, b0 12,088,187 / ff41af04aecf8515, g1h512 10,847,162 / abd5be1619dcfe46, g1afs 16,047,781 / 000ea9ca46c571a5, g1xgr 10,645,291 / 84514b3679f6fb6c, bootstrap 11,132,058 / fde2337e54e9aed7. Recorded: the SPRT log, the constants table (CaptureProbeMinDepth 9, CaptureProbeReduction 5, CaptureProbeMargin 80, kept as measured; they join the final retune's SPSA as class (b) dimensions, final-retune.md §3.2), batch 3's status row, ideas.md (idea 73), tools/gauntlet/transfer.json (adopted: +9.40, ci95 5.03, an LTC measurement, design search-ltc). No new names (ProbCut's screens of 2026-11-02 and 2026-11-06 and their credits, ORIGINALITY.md). Commit e005049 (rebased onto d33a4db, no engine change since a95e269). Speed (clang-release, Windows, the shared machine busy; A = phase-4 a95e269, B = the adopting commit e005049, r8brft1): bench/ab_search.py, 10 interleaved rounds, not pinned: median nps 2,043,662 against 2,034,450 (-0.5%), best 2,075,512 against 2,061,329 (-0.7%), under its 3.1% noise threshold, no significant difference; 12 further paired ABBA rounds: B/A nps 0.999, 95% interval 0.989 to 1.009 (t, 11 df). So no measurable nps price; the bench itself finishes in about 5% less time because it searches 5% fewer nodes. The switch stays until the Phase 4 re-validation. Labeller policy (decision 24): the next part switch takes a fresh PGO build of this commit (at most one switch per day); the play build is rebuilt. |
| 2026-11-11 | **The training-data audit's validation/training overlap check, and the held-out sets cleaned (owner's gating, before 8c; coordinator's decision under the owner's authorization, about 11:30 PM EST; docs/research/overlap-audit-2026-11-11.md, tools/overlap).** **Definition:** a position (every record of a game, saved or not) overlaps when its placement, side to move, castling rights and legal en passant square (the first four FEN fields; counters ignored) occur in any training file; a game overlaps when its start board and move codes are identical; every hash hit confirmed exactly. Training files: 8b arm c's 129 (also r8brft1's), g4b, and, provisionally, the label-depth arms and the positional slice's first segment (2.62 billion records, SHA-256 against the manifests). **Results:** validation positions in training 1.97% (item 7, g3s2-val), 2.00% (8a), **1.94% (8b, 3,739 of 193,039; kept positions 2.30%; the 20,000-position monitoring prefix 1.72%)**, 1.96% (8c's sealed inputs); recurring late-ending positions (3,463 of 8b's at ply 80 or later, 3,097 with 6-7 pieces), **no leaked game** (the 14 identical games are one-move games: 13 endgame-slice placements, 1 self-play game that ended after one move). Past validation losses were not materially contaminated; **8c is not blocked**. Held-out sets: endgame_heldout.tsv 0 of 3,800; H 54 of 5,000 and H2 237 of 20,000 (held out by game, as declared); i52-held and i52-controls are training positions by construction (labels held out only). **The zero-overlap rule failed for 7 positions**: 6 of heldout_deep.tsv's 1,499 and 1 of heldout_67.tsv's 5,600, all in g3s2's parts. **Fixed:** they are excluded (heldout_deep_excluded.txt; new heldout_67_excluded.txt with `generate --exclude`), leaving 1,493 and 5,599 positions; both tools' `overlap` takes `--train-list` so the check covers every training file (fork_overlap_audit, placement and side to move). Re-run for the six nets: no net misjudged any excluded position, so every misjudged count and paired figure is unchanged (6-7 pieces: r8brft1 770, r8btd90 732, S512ppr3 723, S512ppr2 731, S512+PP 828, S512r2 809 of 5,599; 8-12 pieces: 80, 76, 77, 73, 81, 82 of 1,337 classed, mean differences 0.7-0.8 cp lower). **Recommended for 8c (optional):** drop from the validation file the positions found in training (the tool lists them). Tools and documents only; bench unchanged (9,639,207 / 07f7ae19b9250f38). |
| 2026-11-11 | **The novel ideas' offline probes and the owner's decisions on them (owner, about 10:25 PM EST; probe tools on branch tools/probes-1111 b5143af; ideas.md 79, 82, 83, 85).** (1) **Idea 85 (class-matched TD horizon): the probe passed** (best lambda against the 1M golds: queens-on middlegames 0.35, endgames 0.65; kill line 0.05) and **gets an arm in retrain 8c**: lambda about 0.35 for queens-on middlegames, about 0.65 for endgames, 0.9 for every other record, two seeds, beside the plain TD(0.9) control. (2) **Idea 83 (label super-resolution): killed** (error reduction 3.7% [1.7, 6.1] against the 10% line; the slope on search minus static not clear of zero). (3) **Idea 82 (multi-fidelity heads):** the gold half was flat (no refit beyond the seed spread); **its fixed-node screen runs, and the idea is dropped if that is flat too.** (4) **Idea 79 (nested-width evaluation):** the narrow readout's |narrow - full| is above 100 cp for 5.6% of positions; **its fixed-node screen is built as planned** (the engine work behind a switch, screened before any push). Any GitHub fixed-node run goes through a lane B queue item gated on gate-e1.done. |
| 2026-11-12 | **The pressure-matched Hash measured, and `--hash MB` in the SPRT driver (the owner's rule of 2026-11-11, the engineering review's decision 2a: TT-policy tests run with a Hash chosen so that nodes per move over TT entries matches TCEC's; coordinator's build order, about 1 AM EST).** **Fork's TT:** 64-byte buckets of five 12-byte entries (`src/search/trans_table.hpp`) and Hash in MB of 2^20 bytes (`src/search/hash_memory.hpp`), so 2^20 / 64 × 5 = **81,920 entries per MB**: 1,310,720 at Hash 16, 5,242,880 at 64, 21,474,836,480 at TCEC's Hash 262,144 (config/tcec.json, from TCEC's live.json). **TCEC's nodes per move, measured from TCEC's own PGNs:** 105 games of Swiss 10 (tcec-chess.com/archive/json/TCEC_Season_30_-_Swiss_10_N.pgn, N = 1 and every sixth from 6 to 624, fetched 2026-11-12), the `n=` field of every searched move; the 29 engines run there at Threads 512 and Hash 262144 averaged **6.80 × 10^9 nodes per move** pooled over their 10,170 moves (the median engine's mean 6.79 × 10^9; engine means 0.52 to 14.8 × 10^9; pooled median 3.41 × 10^9). TCEC's ratio for Fork's table: 6.80 × 10^9 / 2.147 × 10^10 = **0.317** (median basis 0.159; 0.094 to 0.687 across the field's engines). **The runners' nodes per move, measured from the SPRT shards:** the shard PGNs record each move's time, not its nodes. Mean time per move **0.1870 s at STC** (t56-any-stc, i61-rg-stc and stop-rule-stc, 2,991,063 moves; median 0.107-0.109 s) and **0.9033 s at LTC** (t56-any-ltc, probcut-ltc2 and b4-cut-node-ltc, 2,083,057 moves; median 0.490-0.494 s). The runners' speed under the same load (3 games at once, x86-64-v3, Hash 16) from the fixed-node screens r8b-rft-fn-rft1 and -rft2 (800,000 nodes per move): 800,000 × 439,412 moves / 174,033.3 s = **2.02 M nps**. So **0.378 M nodes per move at STC and 1.82 M at LTC** (median basis about 0.22 M and 0.99 M). **Ratios today:** STC 0.378 M / 1.31 M = **0.288**, LTC 1.82 M / 5.24 M = **0.348**, against TCEC's 0.317. **Matched Hash** = nodes per move / (0.317 × 81,920): **STC 14.6, so 15 MB; LTC 70.3, so 70 MB** (median basis about 17 and 76). Fork's Hash option takes any whole MB from 1 to 4,194,304 (`src/uci/session.hpp`), so no power-of-two rounding. **Finding: today's Hash 16 (STC) and 64 (LTC) are already pressure-matched** within the measurement's own spread (STC 9% less pressure than TCEC's mean, LTC 10% more). The review's figures were estimates and do not hold as measured: 0.38 M nodes per move at STC, not 0.7 M; 6.8 × 10^9 at TCEC, not "on the order of 10^10"; a ratio of 0.32, not about 1; Hash 70 MB at LTC, not 8-16. A ratio of 1 would instead mean Hash 4.6 (STC) and 22.3 MB (LTC). **UNVERIFIED assumption:** Fork with Lazy SMP at TCEC will search about as many nodes per move as the field's median engine (Fork has no parallel search yet and its EPYC speed is unmeasured; over the field's range of ratios, 0.094 to 0.687, the matched Hash would be 7 to 49 MB at STC and 32 to 238 MB at LTC). The runners' speed comes from the fixed-node games of an earlier engine (base 115daad) and is applied to later ones; a fixed-node move that stops early (if any) makes it slightly low. **Driver:** `tools/github/sprt_run.sh --hash MB` (opt-in, every kind): both engines' Hash, a whole number from 1 to 4194304, recorded in design.json's `hash` like the default (a restart with another Hash is refused), a differing HASH refused, named in the log's header; without it nothing changes. sprt.yml already sends its `hash` input to both engines (tools/cloud/run_shard.sh `option.Hash`) and is read from REF on GitHub at each dispatch, so it is unchanged. tools/github/test_sprt_run.sh: all 116 checks pass, 19 of them new (the default unchanged, --hash at STC, LTC and custom, the restart refusals, the bad values). |
| 2026-11-12 | **E1, the pass-best stop rule, adopted on its non-regression pass under the owner's rule** (2026-11-11, about 10:08 PM EST, as relayed by the coordinator: an H0 or undecided result with a non-negative estimate gets one non-regression test, adopted if it passes). Test sprt/stop-rule d97e358 against off tier2/stop-rule 959cc32 (phase-4 e63101a's engine, r8brft1 on both sides), STC 8+0.08: the design R SPRT stop-rule-stc ([0, 6] nElo, cap 8, stages 0-7) **capped undecided at +3.26 ± 3.35 Elo** (nElo +5.86 ± 6.02, 12,800 games, LLR 1.82; runs 43128978493 to 43145414123; 10:20 PM EST); the non-regression SPRT stop-rule-nonreg ([−3, 0] nElo, alpha = beta = 0.05, fresh openings, stages 8-20) **H1, +2.41 ± 2.69 Elo** (nElo +4.22 ± 4.72), Ptnml [215, 2413, 5033, 2491, 248], LLR 2.96 after 20,800 games (runs 43147600231 to 43173009038; 2:26 AM EST 2026-11-12; sprt-log; the legacy custom-bounds mode wrote no verdict file, a tooling gap). Ported onto phase-4 fa2ad80 alone (prepared on adopt/e1 25623ab from phase-4 26323e1): `prior_best_` and `prior_best_searched_` in the searcher, the per-pass reset of the iteration's best, and the stop rule's new branch (once the unfinished pass has searched the last finished iteration's best move again, that pass's best exact move is played whatever its score; an unresolved root fail high is still never played), with `UsePassBestStop` on; the same code as tested apart from clang-format line breaks. Commit e5a073f. Bench unchanged, 9,639,207 / 07f7ae19b9250f38 with r8brft1 (bench's searches finish every iteration); no reference changes (checked: the bootstrap 11,132,058 / fde2337e54e9aed7 and s512ppr3 9,333,183 / 5ab710110234a9e9 equal their references). Names screened at 959cc32 (no match in Stockfish, Ethereal, Berserk or Weiss); no constants. Speed not measured (UNVERIFIED). Recorded: the SPRT log, ideas.md (idea 130), tools/gauntlet/transfer.json (the adopted entry: the STC estimate +3.26, ci95 3.35, with the non-regression result as its basis; no stopping-bias record, as the STC was capped, not passed). The switch stays until the Phase 4 re-validation. The rule changes every node-limited search, so data generation too. Labeller policy (decision 24): the next part switch takes a fresh PGO build of this commit (at most one switch per day); the play build is rebuilt. The gated tests (gate-e1) run on commits rebased onto the rule (branches with the suffix -e1; each off benches 10,166,167 / d874b380155a2e8c, the engine of 26323e1 with E1, each test its original bench). |
| 2026-11-12 | **jobctl: the nested-stop test's race, and the Windows record-file race fixed (coordinator's request; tools/jobs only, bench unchanged).** (1) **Test race, not a stop bug.** `test_a_job_started_inside_another_stops_with_its_whole_tree` failed three times under load with "Lists differ: [pid] != []", at its check that the outer job is untouched. A process in the outer job's snapshot had ended by itself: the outer job's own `jobctl start` call (Git Bash's fork stub, the venv launcher, Python) could still be alive when the inner job ran. `start_nested_upload` now waits for the outer's long-lived waiter, which starts only after the call returns. A new test adds a 3-second tail after the call: it failed 3 of 3 with the old helper and passes with the new. The stop was already verified over the Job Object's process list and the recorded keeper and command, nested jobs included. (2) **Windows record-file race (a real bug).** On Windows a rename over a file, or its removal, fails while another process has it open, and every read holds it open for a moment; a read fails while a rename over it is under way. Under load, one keeper died on its first record write (its job ran unrecorded), and one record read failed. `read_json` would have taken such a record as missing, which lets `take_lock` reclaim a live job's lock and `other_jobs_pids` skip a nested job. **Fix:** `when_unblocked` retries a blocked read, rename or lock removal for up to `FILE_PATIENCE` (10 s). `write_json`'s temporary file is per process. A new test holds the file open and fails separately against the old read, write and release. The tools/jobs suite passed 20 of 20 runs on Windows, and the affected tests passed 4 of 4 under CPU load. **Open item (UNVERIFIED, not reproduced):** `take_lock` creates the lock file and then writes it, so a second `start` of the same type in that instant could read it empty and reclaim it, leaving both jobs holding the type. |
| 2026-11-12 | **The pre-commit check runs the search suites (owner, 6:15 AM EST: "add a fast search-suite subset (< ~2 min) to the pre-commit check; full suites stay in CI").** Switch-on test commits had failed search and pruning cases (root LMR's stop-rule coverage sample, C17's exact no-pruning reference) that `scripts/check.sh quick` never ran. **Measured** in clang-release on this machine under the builders' load (`ctest -L quick-search`, serial): search 70.3 s, pruning 18.9 s, ordering 0.8 s, see 0.2 s, draws 0.1 s, time_budget 0.1 s, tt and params 0.01 s each, **90.5 s together** (an earlier run of the same suites, 85 s). search's cost is its exactness and stop-rule cases (3 to 13 s each: root minimax, zero-window reference, tiny TT, the five stop cases, the node limit, the forced move), the ones such commits break, so the subset is the **whole suites**, not a case-level cut (the harness has no case filter). **Implemented:** the ctest label `quick-search` on those eight existing tests (CMakeLists.txt; no new test, so CI's `-LE slow` runs exactly what it did); `check.sh quick` runs it after the core suites (`run_ctest`, with `--no-tests=error`); `FORK_QUICK_SEARCH=0` skips it, and the after-edit hook sets that, so a per-edit rebuild stays inside its 280 s limit; the pre-commit hook runs it. **Hook time on a warm build:** 118 s before, 232 s after (same tree, back to back; the old check's own time is mostly the tooling's Python tests). **Fault injection:** `UsePassBestStop`'s default turned off (bench unchanged, 9,639,207 / 07f7ae19b9250f38): the old check passed (132 s), the new one failed at search/"the pass-best stop rule plays the pass's better exact move over the previous best" (test_search.cpp:1248); reverted. Names screened (coordinator): no match. Tooling only; bench unchanged. |
| 2026-11-12 | **Quiet history pruning (B13, the history skip) adopted on its STC pass at 700 per ply, pre-approved by the owner (overnight order of 2026-11-11: search items that pass their SPRT are adopted one at a time onto phase-4's head; held locally until the debug-job CI failure of run 43181932552 was fixed, the owner's rule "fix before anything is adopted"; fixed by 139cf3d, its CI run 43203416117 green in all four debug jobs).** The head-to-head qhp-h2h (9,600 games at STC, runs 43113474240 to 43125463839) picked **700** of 2000, 1300 and 700 (1300 − 2000 +9.42 ± 9.83 nElo, 700 − 2000 +9.62 ± 9.83 nElo, least squares; the tie rule not applied). qhp-stc (STC 8+0.08, Hash 16, design R [0, 6], cap 8, fresh openings from stage 2): test sprt/qhp-t56-700-e1 4701319 against off tier2/qhp-t56-e1 4cae4f4, both on adopt/e1 25623ab (phase-4 26323e1 with E1, no ProbCut), r8brft1 on both sides, **+6.04 ± 4.37 Elo** (nElo +10.52 ± 7.61), Ptnml [83, 899, 1917, 998, 103], **H1** (LLR 2.99) after stages 2-6, 8,000 games (runs 43182618097 to 43193266205; 4:57 AM EST; sprt-log). The tested commit 4701319 itself passes every non-slow test (clang-release, Windows: 32 of 32, eval skipped as usual), checked before the port. Ported onto phase-4 e79cbf7 alone, on branch adopt/qhp: the skip in the search, `UseHistorySkip` (now on), `HistorySkipMaxDepth` 3 and `HistorySkipPerPly` 700 in the parameter table (after ProbCut's rows; clang-format realigned the table), its stats counters and measurement bins, its tests, and tools/tier2_measure/history_skip.json and history_skip_rates.py; the code lines equal 4701319's diff against 25623ab apart from that realignment and merged comments. Tests: the history-skip case checks the default is on; test_pruning_review's exact search (`no_pruning`) now switches the skip off too (it prunes moves) and the tier-2 all-switches case lists it. Bench equivalence (clang-release, Windows, r8brft1): with the skip off 9,639,207 / 07f7ae19b9250f38 (phase-4's); with the skip on and ProbCut off 9,886,698 / 8e7db959846159f4, byte for byte 4701319's tests/bench-r8brft1.ref, so the port equals the tested code (a byte-equal bench with ProbCut on is not expected: the tested base had no ProbCut). New bench 9,263,568 / 881c326307a2ba8a with r8brft1. Every network's reference and the bootstrap's re-pinned from its own build: r8btd90 8,459,468 / 173ddab97c624226, s512ppr3 8,984,249 / 1705f049341caea1, s512ppr2 9,676,244 / cce7d1f4fe57a959, s512pp 9,339,795 / 88ec84da2c727210, s512r2 9,691,048 / ef3cd41f2b62ae43, s512 10,587,211 / b128f83e6a445ea9, b0r2 10,000,485 / 95f92932c956f2a5, b0r1 11,693,634 / 368a739f9c91f574, b0 12,595,919 / 2d8aa9d4e5e81f9d, g1h512 10,687,261 / de59d67dd0343e10, g1afs 14,767,049 / 81ff906352a4bef0, g1xgr 10,218,899 / 7bef3aa640b7a0a2, bootstrap 10,817,491 / 0119425c42894d16. Recorded: the SPRT log (qhp-h2h and qhp-stc), the constants table (700 adopted; `HistorySkipMaxDepth` 3, its Ethereal match and Weiss near match credited), ideas.md (idea 74), the final retune's SPSA (both constants join class (a), final-retune.md §3.1, the efficiency rule), tools/gauntlet/transfer.json (adopted: +6.04, ci95 4.37, design search-stc, 5 stages, nElo 10.52), ORIGINALITY.md (the 2026-11-11 screens' credit stands; no new names or constants). Speed, measured after the adopting commit 9d574d9 (built as 22ab719, before its rebases onto 32384e1 and 8cb60b8, which changed no engine code) with bench/ab_search.py (clang-release, Windows, not pinned, the shared machine busy; A = phase-4 e79cbf7, B = the adopting commit 9d574d9 (built as 22ab719, before its rebases onto 32384e1 and 8cb60b8, which changed no engine code), r8brft1): 12 interleaved rounds, median nps 3,163,250 against 3,083,790 (-2.5%), best 3,213,989 against 3,175,134 (-1.2%), under the 3.7% noise threshold; 16 more rounds, median 2,900,246 against 2,815,540 (-2.9%), best 2,983,721 against 2,991,063 (+0.2%), under the 6.3% threshold. No significant difference in either; both medians lean 2.5-3% slower, so a small nps price (the ordering score computed for each eligible quiet move at depths 1-3) is possible but not resolved at this noise (UNVERIFIED). The bench searches 3.9% fewer nodes (9,263,568 against 9,639,207). The switch stays until the Phase 4 re-validation. Labeller policy (decision 24): the next part switch takes a fresh PGO build of this commit (at most one switch per day); the play build is rebuilt. |
| 2026-11-12 | **The minor drift table (E4) adopted on its STC pass at `MinorDriftShare` 32/64, pre-approved by the owner (overnight order of 2026-11-11: search items that pass their SPRT are adopted one at a time onto phase-4's head; the owner's table rule: if several tables pass alone, only the best is adopted and the next-best is tested on top of it; minor at 32 is the first to pass).** The drift tables' SPRTs in the passive ranking's order (design R at STC 8+0.08, Hash 16, against off tier2/corr-tables-e1 dd5db13, every table off on adopt/e1 25623ab; r8brft1 on both sides; sprt-log): threat 64 H0 (−10.53 ± 6.95 Elo, 3,200 games), threat 32 H0 (−7.38 ± 7.01, 3,200; both tries used), minor 64 H0 (−18.26 ± 9.95, 1,600), **minor 32 (sprt/corr-minor-32-e1 62b911f) H1, +5.57 ± 4.01 Elo** (nElo +9.66 ± 6.95), Ptnml [105, 1081, 2295, 1193, 126], LLR 3.18 after stages 8-13, 9,600 games (runs 43197094411 to 43211912908; 7:04 AM EST). **The offline diagnosis** (2026-11-12, 6:20-7:05 AM EST; 40 of r8b-rft-stc's games replayed at 200,000 nodes against 1,000,000-node labels; a scratch stats build, not committed): at share 64 one table's term feeds on itself (the applied term enters the subtree results the table learns from) and runs to the 300 cp limit late in games (minor 64: mean term 44.9 cp, 3.0% of node visits at the limit, search error +23.7 cp [+14.5, +34.2] against the labels; threat 64 +17.8 cp), which matches both H0s at 64; at 32 it stays bounded (minor 32: mean term 17.5 cp, 0.016% at the limit) and the search error improves, −2.5 cp [−4.5, −0.8]; a lower `DriftLimit` alone (150) does not stop the runaway. Threat 32's H0 is not explained by accuracy (−1.4 cp [−3.3, +0.4]); the threat key's two attack maps per node are its likely cost (UNVERIFIED, not measured). The diagnosis recommends a depth-scaled term before the remaining major and piece tests (not decided here; the owner's). **The tested commit 62b911f itself** (clang-release, Windows, every non-slow test, checked before the port): 32 of 33 pass (eval skipped as usual; eval_drift passes); search fails its 4 exact-minimax cases (root score equals plain minimax; TT cutoffs at exact depth on small endgames; the repetition-in-reach known case; the zero-window reference), as the table adds its learned term to the quiescence stand-pat (e.g. 127 against 128 cp, 23 against 14 cp): a test-reference issue, so `exact_switches()` in tests/test_search.cpp now switches the drift tables off, as it does pruning. **Ported onto phase-4 75d53f0 alone** (branch adopt/corr-minor): src/search/eval_drift.hpp, the tables in the searcher, the four switches (`UseMinorDrift` now on; `UsePieceDrift`, `UseMajorDrift`, `UseThreatDrift` present and off, still under test), the seven parameters (`MinorDriftShare` 32), the stats counters and FORK_DRIFT_REPORT, tests/test_eval_drift.cpp, tools/measure/drift_rank.py and the engine_lines.py and game_replay.py parsing; the code lines equal 62b911f's diff against 25623ab apart from the parameter table's and the switch list's realignment beside ProbCut's and the history skip's rows and merged comments. PlyFrame unchanged (the keys sit beside the frames; the 2,704-byte guard holds). Tests added: the defaults (minor on, the others off), and every drift switch in the two tier-2 all-switches cases. Bench equivalence (clang-release, Windows, r8brft1): every table off 9,263,568 / 881c326307a2ba8a (phase-4's); the minor table on with ProbCut and the history skip off (the tested base had neither) 9,633,320 / 2467c017a6bb6ec4, byte for byte 62b911f's tests/bench-r8brft1.ref, so the port equals the tested code. New bench 9,366,920 / 6d72bf03d34c65ec with r8brft1. Every network's reference and the bootstrap's re-pinned from its own build: r8btd90 9,775,184 / 225454ca546913fe, s512ppr3 8,792,209 / 6ec2952061ff93a6, s512ppr2 9,145,319 / fc30f3292e0816e2, s512pp 9,426,347 / 16fa7fb6a5dabb47, s512r2 9,683,476 / 05b1ab23e820c2f3, s512 10,577,753 / 66776004fb20318b, b0r2 10,405,625 / 48db617801140e83, b0r1 11,901,807 / 203accdfd9e172bd, b0 11,974,437 / 829ce0ca30cbba11, g1h512 10,951,836 / 6611fcf61f6abaa3, g1afs 15,977,186 / 6103604a65734c7c, g1xgr 9,907,155 / 45956ab6a47711b1, bootstrap 12,502,060 / 44d782d7d272c23b. clang-release: every non-slow test passes (33 of 33, eval skipped as usual, bench_parity included). clang-debug: eval_drift (7 cases) and pruning (28 cases) pass; the debug search suite was stopped unfinished after 18 minutes, as it held the shared compile lock with four builds waiting, so it is left to CI's debug jobs (UNVERIFIED here). Recorded: the SPRT log (the four drift-table SPRTs), the constants table (`MinorDriftShare` 32 adopted; it and `DriftLimit` 300 join the final retune's SPSA as class (a) dimensions, final-retune.md §3.1, the share flagged at its range's floor), ideas.md (idea 78), tools/gauntlet/transfer.json (adopted: +5.57, ci95 4.01, design search-stc, 6 stages, nElo 9.66), ORIGINALITY.md (the 2026-11-11 screen's credits stand; no new names or constants). Speed: measured before the commit with bench/ab_search.py (clang-release, Windows, not pinned, the shared machine busy; A = phase-4 75d53f0, B = the port's build of this commit's engine code from the uncommitted tree on 75d53f0, r8brft1; identity checked on all 24 runs): 12 interleaved rounds, median nps -2.0%, best -3.4%, under the 4.9% noise threshold: no significant difference; a small price (the material keys kept at each make, the table read at each estimate) is possible but not resolved at this noise (UNVERIFIED). The bench searches 1.1% more nodes (9,366,920 against 9,263,568). The switches stay until the Phase 4 re-validation. Labeller policy (decision 24): the next part switch takes a fresh PGO build of this commit (at most one switch per day); the play build is rebuilt. |
| 2026-11-12 | **The summed pair-table update (the engine survey's D8) adopted on its STC pass, pre-approved by the owner (overnight order of 2026-11-11: search items that pass their SPRT, here an STC-only item, are adopted one at a time onto phase-4's head).** survey-d8-stc (STC 8+0.08, Hash 16, design R [0, 6], cap 8, futility look after 2 stages, from stage 0): test sprt/d8-pair-sum-e1 dd132c9 against off tier2/d8-pair-sum-e1 aa8dd0d, both on adopt/e1 25623ab (phase-4 784b1b0's engine with E1; no ProbCut, no history skip, no drift table), r8brft1 on both sides, **+4.29 ± 3.46 Elo** (nElo +7.47 ± 6.02), Ptnml [136, 1483, 3011, 1627, 143], **H1** (LLR 2.84) after stages 0-7, 12,800 games (runs 43196026493 to 43216014186; 7:32 AM EST 2026-11-12; sprt-log). No constant (DESIGN.md "Search constants", the pair-table update base). **Port:** aa8dd0d's change (relative to 25623ab) with dd132c9's switch-on onto phase-4 2c294d3 alone (branch adopt/d8; the code lines equal the tested diff apart from the switch list's and the comments' merge beside ProbCut's, the history skip's and the drift tables' entries; the test case moved beside the history skip's; test_pruning_review's all-switches case lists it too). `UsePairSumUpdate` on, the switch kept until the Phase 4 re-validation. **Bench equivalence** (clang-release, Windows, r8brft1): with D8 off 9,366,920 / 6d72bf03d34c65ec, phase-4's; with D8 on and ProbCut, the history skip and the minor drift table off (the tested base had none of them) 10,236,778 / 6338c0c3a941915a, byte for byte dd132c9's tests/bench-r8brft1.ref, so the port equals the tested code. Bench 8,773,005 / 413d5ae2f1af08de (r8brft1), every reference re-pinned from its own build. Tests: clang-release (Windows): every non-slow test passes (33 of 33, eval skipped as usual, bench_parity included). clang-debug: ordering (14 cases) and pruning (29 cases) pass; the debug search suite, still running when this was committed (started 8:44 AM EST), passed at 9:04 AM EST (27 cases, 0 failures). Speed: bench/ab_search.py (clang-release, Windows, not pinned, the shared machine busy; A = phase-4 2c294d3, B = the port's build of this commit's engine code from the uncommitted tree on 2c294d3 plus the zugzwang tools, r8brft1; identity checked on all 24 runs): 12 interleaved rounds, median nps -0.5%, best -0.4%, under the 3.0% noise threshold: no significant difference (a price of that size is inside the noise, UNVERIFIED). The bench searches 6.3% fewer nodes (8,773,005 against 9,366,920). Records: SPRT log, ideas.md (idea 75), final-retune.md (no new dimension), tools/gauntlet/transfer.json, ORIGINALITY.md (the 2026-11-11 screen stands; no new names or constants). |
| 2026-11-12 | **Final-retune ranges set by the owner (range only: every default and step unchanged, bench unchanged).** (1) About 8:45 AM EST: `MinorDriftShare` 16-64 (was 32-128, the range declared for the natural 64, at whose floor the adopted 32 sat): half to twice of 32, centred. (2) About 8:50 AM EST, the staleness audit: `AspirationHalfWidth` 8-40 (was 6-24); the default stays 12 with no SPRT (R14's SPSA kept 12 within a range topped at 24, and game evidence outranks the audit's offline re-measure of 29). The history weights' ranges must hold the audit's re-measured values strictly inside (defaults unchanged): `FollowWeight` 0-16 (was 0-8; the re-measured 8 was its ceiling, 16 the ranges rule's twice of 8); `ReplyWeight` 0-12 kept (the re-measured 8 lies 4 steps inside; a higher ceiling would break the checked property that one reply entry alone fits int16 unclamped); `TakeWeight` 0-16 kept (the re-measured 2 lies 2 steps above the natural floor 0). The int16 headroom holds: HistoryMax × (4 + 12 + 16) / 4 = 80,000, exact in int, clamped before the store. Time-management constants unchanged. src/tune/params.hpp, final-retune.md §3.1 and §3.3; the tuning build's bounds case (tests/test_search.cpp) searches the three new bounds. |
| 2026-11-12 | **Stacking checks compare like with like (owner, 10:45 AM EST).** Stacking check 1 (ProbCut + E1 + B13, 75d53f0 against d33a4db, design R STC): H1, +6.30 ± 4.40 over 8,000 games, against a raw sum of +18.70. ProbCut's +9.40 was measured at LTC (it lost at STC originally), so an STC check undercounts it; without it the STC sum is about +9.3 and the ratio about 0.68, within the decision audit's 0.62-0.80: no follow-up. Rule: a stacking check compares against the sum of each item's gain at the check's own time control; a batch with LTC-only items runs its check at LTC or leaves those items out of the comparison. SPRT log: docs/history/phase-4/sprt-log.md. |
| 2026-11-12 | **The direct-check ordering bonus (the engine survey's D13) adopted on its STC pass at `DirectCheckBonus` 5000, pre-approved by the owner (overnight order of 2026-11-11: search items that pass their SPRT, here an STC-only item, are adopted one at a time onto phase-4's head).** survey-d13-stc (STC 8+0.08, Hash 16, design R [0, 6], cap 8, futility look after 2 stages, from stage 0): test sprt/d13-check-order-5000-e1 cc7b3bc against off tier2/d13-check-order-e1 35209f0, both on adopt/e1 25623ab (phase-4 784b1b0's engine with E1; no ProbCut, no history skip, no drift table, no D8), r8brft1 on both sides, **+5.50 ± 3.93 Elo** (nElo +9.73 ± 6.95), Ptnml [93, 1082, 2306, 1218, 101], **H1** (LLR 3.21) after stages 0-5, 9,600 games (runs 43229400100 to 43247622236; 10:44 AM EST 2026-11-12; sprt-log). **Port:** 35209f0's change (relative to 25623ab) with cc7b3bc's switch-on onto phase-4 85672d8 alone (branch adopt/d13): `direct_check_targets` and the bonus in `MoveSelector::score_quiets` and `quiet_order_score`, the switch `UseCheckOrderBonus` (now on), `DirectCheckBonus` 5000 in the parameter table (after `TakeWeight`, range 0-20000, step 1000) and the tests; the code lines equal cc7b3bc's diff against 25623ab apart from the parameter table's and the switch list's merge beside ProbCut's, the history skip's, the drift tables' and D8's entries and the comments (the test case moved beside D8's; test_pruning_review's all-switches case lists it too). The history skip (B13) reads `quiet_order_score` without the bonus (the tested D13 had no skip, the tested skip no bonus, so the port keeps each as tested): a quiet check whose history is at or below the skip's threshold can still be skipped at depths 1-3 although the selector now tries it early. Whether the skip should see the bonus is not measured (UNVERIFIED; a follow-up for the owner). **Bench equivalence** (clang-release, Windows, r8brft1): with D13 off 8,773,005 / 413d5ae2f1af08de, phase-4's; with D13 on and ProbCut, the history skip, the minor drift table and D8 off (the tested base had none of them) 10,253,460 / 8f28bb6e1d52fa6e, byte for byte cc7b3bc's tests/bench-r8brft1.ref, so the port equals the tested code. Bench 9,118,607 / 208629aa15e140a9 (r8brft1), every reference re-pinned from its own build. Tests: clang-release (Windows): every non-slow test passes (33 of 33, eval skipped as usual, bench_parity included). clang-debug: ordering (16 cases) and pruning (30 cases) pass; the search suite (27 cases) passes too (11:33 AM EST). Speed: bench/ab_search.py (clang-release, Windows, not pinned, the shared machine busy; A = phase-4 85672d8, B = the port's build of this commit's engine code from the uncommitted tree on 85672d8, r8brft1; identity checked on all 24 runs): 12 interleaved rounds, median nps +1.2%, best -2.9%, under the 6.0% noise threshold: no significant difference (a price of that size is inside the noise, UNVERIFIED). The bench searches 3.9% more nodes (9,118,607 against 8,773,005). Records: SPRT log, the constants table (`DirectCheckBonus` adopted), ideas.md (idea 77), final-retune.md (one class (a) dimension), tools/gauntlet/transfer.json, ORIGINALITY.md (the 2026-11-11 screen stands; no new names or constants). |
| 2026-11-12 | **`DirectCheckBonus`'s final-retune range set by the owner (about 12:50 PM EST: "DirectCheckBonus final-retune range 2500-10000"; range and step only, the default 5000 unchanged, bench unchanged).** 2500-10000 (was 0-20000, step 1000, declared at D13's re-plan of 2026-11-11, its floor 0 the off-equivalent): the ranges rule's half to twice of the adopted 5000, so the rule's step applies too, a twentieth of the range, 375 (6.7 steps below the default, 13.3 above). Within the rule, so not one of the rule's exceptions (final-retune.md §3.3). src/tune/params.hpp, final-retune.md §3.1 (its row and the two notes that cite the range), the parameter's Search-constants row; the tuning build's bounds case (tests/test_search.cpp) searches 2500 and 10000. |
| 2026-11-12 | **The local checks skip the timing tests while data generation runs (owner, about 12:50 PM EST: "Set FORK_LOW_PRIORITY=1 for local timing tests while data generation runs (CI keeps them)").** Beside a running `fork_datagen` the timing cases (uci_timing) measure the machine's load, not Fork. `scripts/check.sh` (every mode: `quick`, the pre-commit and after-edit hooks', runs no timing case today; `stop` and `full` run uci_timing) detects data generation once, before its first test: on Windows a `fork_datagen.exe` process (`ps -W`, which also shows one started from Git Bash by its MSYS path) or a `fork_datagen` process in the WSL distro `FORK_WSL_DISTRO` (default Ubuntu; asked only while that distro runs, so the check never starts it); on Linux, the full check's WSL leg included, `pgrep -x fork_datagen`. It then exports `FORK_LOW_PRIORITY=1` (only the variable: env.sh's priority drop and job cap are not applied, as env.sh was sourced before) and prints "data generation running: timing tests skipped (FORK_LOW_PRIORITY=1)". Never on CI (`CI` or `GITHUB_ACTIONS` set); `FORK_DATAGEN_RUNNING=1` or `0` replaces the detection. About 0.6 s on Windows with the distro running, 0.05 s with the override. A `stop` or `full` pass with the timing cases skipped is still recorded (CI runs them on every code push). |
| 2026-11-12 | **The split search's settings are tuned values, re-checked as the data grows (owner, about 1:30 PM EST).** The save share (now 50%) and the saved and unsaved node budgets (20,000 and 4,000; idea 13, adopted 2026-10-31) are re-checked whenever the data volume grows substantially, like other tuned values. The label-depth experiment's result (idea 62) and idea 80's 8c arm (labelling the unsaved half) together decide the next settings, for example deeper saved labels and/or a higher save share if deeper labels win at equal CPU. Until then data generation keeps the current settings. |
| 2026-11-12 | **Correction tables: the offline gate is a safety check, the SPRT decides (owner, about 2:05 PM EST).** Pieces@64 on top of the adopted minor@32 failed the offline gate (runaway: error +12.74 cp against the head, 1.23% of visits at the limit; pieces@32 on top +2.99 cp, 0.24%). No standalone stacking SPRT now: the stack folds into idea 59's follow-up redesign, where the depth-scaled (and window-gated) variant of minor@32 + pieces@32 (shares sum to 64) is tested against the minor@32 head when slots open. Rule: the offline gate only blocks runaway (worse error or more than 0.1% of visits at the limit); a stack that passes it goes to a design R SPRT, which decides adoption (ideas.md 78, 59). |
| 2026-11-12 | **`SingularMarginPerPly`'s final-retune range 2-16 (owner, about 2:10 PM EST: "SingularMarginPerPly final-retune range 2-16."; range only, bench unchanged).** Was 2-12; default 6 and step 1 unchanged. T27's rule 1 re-run on r8brft1 picked 22, and 22 lost its design R STC SPRT against 6 (H0 after stage 0, −26.76 ± 9.93 Elo; the staleness audit, docs/research/staleness-audit-2026-11-12.md), so the 2-44 planned that morning (the ranges rule's twice of 22) is replaced. src/tune/params.hpp, final-retune.md §3.2 and §3.3, the constants table; the tuning build's bounds case (tests/test_search.cpp) searches 16. |
| 2026-11-12 | **Offline re-measurement rules set retune ranges only; they never gate or pick values by themselves (owner, about 2:10 PM EST; Testing setup).** The staleness audit (docs/research/staleness-audit-2026-11-12.md, on phase-4 75d53f0 and r8brft1) re-ran every declared measurement rule and compared each pick that games or the SPSA had checked: none won. `SingularMarginPerPly` 22 (T27's rule 1 re-run) lost to 6, H0 after stage 0, −26.76 ± 9.93 Elo; the quality-per-node rules ranked "off" first for IIR (+21.45 STC, +26.25 LTC in games) and ProbCut (STC H0 −5.29 on S512r2, LTC +9.40), and their picks for the LMR history term, rising RFP and the threat set lost (5 of 5 wrong in sign or order); the 1% cutoff bounds (LMP allowance, RFP margin) were moved by the SPSA or lost in games; aspiration's p90 rule now says 29 where the SPSA kept 12. So a re-run reading justifies a range that covers it; it is neither a gate nor a pick. The area rule is in .claude/rules/testing.md (1f38e18). |
| 2026-11-12 | **Planning factor for stacked search adoptions (owner, about 2:55 PM EST).** Stacking check 2 (the minor drift table, D8 and D13 at STC, 96ebfec against ec4a4be): H1, +7.86 ± 4.33 over 8,000 games, against an STC sum of +15.36 (ratio 0.51); accepted, no follow-up; the overlap between D8 and D13 (both move ordering) is left to the factorial removal round, which tests every switch on the full head. For overlapping small search adoptions, estimate the combined gain at about 0.5-0.6 times the sum of the separate SPRT claims (stacking check 1: 0.68 like for like). SPRT log: docs/history/phase-4/sprt-log.md. |
| 2026-11-12 | **Speed sprint 3: the accumulator update in register tiles, adopted (owner's speed-only rule; adopted on the pass, about 4:10 PM EST).** `advance_values` loads each tile of the parent's sums once (8 AVX2 vectors, up to 16 AVX-512 ones), applies every removed and added row with one pass per row and stores it once, instead of one row loop per vector. instructions:u per bench 42,841,608,071 -> 29,390,085,210 (-31.4%); nps (bench/ab_search.py, 24 interleaved rounds, quiet window 4:02-4:07 PM EST): WSL x86-64-v3 +14.7% median, +15.5% best (threshold 4.5%), Windows native (AVX-512) +5.4% / +5.9% (threshold 3.2%). Bench identical, 9,118,607 / 208629aa15e140a9. Maintenance cost small (tile sizes tied to the register files, guarded by a static_assert); GCC's speed UNVERIFIED. Record: docs/history/phase-4/perf-log.md, speed sprint 3. |
| 2026-11-12 | **Endgame checks: one integrity/recall gate, the held-out sets reported and flagged (owner, about 4:40 PM, 5:00 PM and 5:50 PM EST).** Base rule (4:40 PM), verbatim: "held-out endgame counts are reported and flagged for my review (>15% worse than the base), never a gate on screening or promotion; every arm that passes the integrity gates gets its fixed-node screen." Then (about 5:00 PM), verbatim: (1) "the 900-position check stays a gate, relabeled an integrity/recall check (catches missing or corrupted slice data)"; (2) "gates.sh flags against the current default net (what a promotion would replace), and also reports the change vs each run's warm start for diagnosis"; (3) "slice v2 keeps its declared Nov 9 keep rule (screen interval not entirely below 0 AND held-out 6-7 misjudgments down >= 25% vs the control)." Then (about 5:50 PM, on the coordinator's open points): 8c's fresh endgame slice **keeps** the 900 check's positions, so the check stays a recall/integrity gate; gates.sh **enforces** at most 15 of 900 in its exit status **only for nets trained with the endgame slice**, report-only otherwise, both paths tested. So: **the integrity/recall gate** is tools/nnue/endgame_check.py's 900 positions, at most 15 misjudged (898 of them are slice positions, bug review T1; `endgame_check.py gate`, `RECALL_LIMIT`), enforced by gates.sh when the required `SLICE_TRAINED` is 1 and reported only when it is 0 (no default: whether a net was trained with the slice is a fact of its training run, which the calling chain knows and the net file does not record; an unset or other value stops gates.sh before any work); **the held-out checks** (4-5 pieces endgame_heldout.py, 6-7 heldout_67.py, 8-12 heldout_deep.py) are reported for every candidate and flagged when the count is more than 15% worse than the **current default's** (the "base" of the 4:40 PM rule; `ratio > 1.15` in endgame_heldout.FLAG_RATIO), never a gate on screening or promotion; gates.sh also prints each held-out count's change against the run's warm-start net (`HELDOUT_WARM`, passed to both reports as `--warm-start`; unset, the line says the change was not reported); **slice v2's keep rule** stays as declared on 2026-11-09 (the fixed-node screen's interval not entirely below 0 AND the held-out 6-7-piece misjudgments down at least 25% against the control arm): the one place a held-out count is a condition, an arm's own keep rule, not a screening or promotion gate. Updated: Testing setup ("Which test a candidate gets"), the endgame-slice row and item 8a above, ideas.md (45, 68, 70), nets.md, docs/research/endgame-slice-v2/design.md, tools/nnue/gates.sh and the two report tools with their tests. |
| 2026-11-12 | **The startup CPU check, adopted on its own (owner, about 5:50 PM EST).** src/core/cpu_gate.cpp, a constructor of priority 101 compiled for baseline x86-64 without LTO, stops with a message (exit 1) a CPU that lacks the instruction sets FORK_ARCH (x86-64-v3, x86-64-v4) and FORK_VNNI compiled the rest for, instead of an illegal instruction later; a native build checks nothing. A refusal, never a dispatch (.claude/rules/simd.md); the TCEC build row's "startup CPU check". FORK_CPU_GATE_TEST=fail forces the refusal (ctest cpu_gate_refusal). Taken from archive/speed3-nnue-avx512 without its AVX-512 output layer (not adopted: within the noise). Bench unchanged, 9,118,607 / 208629aa15e140a9. |
| 2026-11-12 | **Speed sprint 3, the search core: captures generation visits only the king squares and pawns that can add a move, adopted under the 1% cycles-per-node rule (owner, about 5:50 PM EST; decision 8 of 2026-11-07, the think tank's X13).** In the captures-only mode `fill_moves` masks the king's squares to the generated kind and visits only pawns on the seventh rank, pawns attacking a capture target and pawns beside the en passant square; the skipped ones added no move, so every list is unchanged, move for move and in order. Quiet window 5:29-5:39 PM EST, 20 interleaved rounds per pair, core 4, every bench under perf stat, identity checked on every run: cycles per node +2.91% median / +3.00% best on x86-64-v3 (threshold 1.59%) and +2.40% / +2.30% on x86-64-v4 (threshold 1.54%), faster by the cycles rule; nps +2.70% / +3.09% and +2.47% / +2.06%, under the nps rule's 3% floor; instructions:u per bench -1.73%. The SEE candidate (one `attackers_to`, then only the last capturer's line looked up again) added nothing on top (-0.09% / +0.05%) and is dropped (archive/speed3-see-xray, archive/speed3-see-capgen). Bench identical, 9,118,607 / 208629aa15e140a9, and on every network's reference and the bootstrap's. Maintenance cost small (about 15 lines with comments in `fill_moves`). Record: docs/history/phase-4/perf-log.md, speed sprint 3, the search core. |
| 2026-11-12 | **The history skip's exemption for checking quiets (B13 with D13; night queue item 71b) adopted on its non-regression pass, pre-approved by the owner** (about 12:50 PM EST: "exempt quiet checking moves from B13's history skip; test as one small design R SPRT, pre-approved on pass"; about 4:50 PM EST, after the design R capped: "run one non-regression SPRT [-3, 0] ... adopt on a pass (pre-approved), drop if it fails"). test sprt/skip-check-exempt cb66f9b (the switch on; bench 9,443,408 / 6d421599a985f97c) against off tier2/skip-check-exempt 5cd267c (phase-4 96ebfec's engine with the exemption built in, off; 9,118,607 / 208629aa15e140a9), r8brft1 on both sides, STC 8+0.08: skip-check-exempt-stc (STC 8+0.08, Hash 16, design R [0, 6], cap 8, futility look after 2 stages, from stage 0): **capped undecided at +2.80 ± 3.43 Elo** (nElo +4.90 ± 6.02), Ptnml [136, 1494, 3030, 1611, 129], LLR 1.21 (bounds −1.56, 2.77) after stages 0-7, 12,800 games (runs 43285168897 to 43307235492; 4:27 PM EST); skip-check-exempt-nonreg ([−3, 0] nElo, alpha = beta = 0.05, the same pair, fresh openings, stages 8-20): **H1, +2.86 ± 2.77 Elo** (nElo +5.08 ± 4.91), Ptnml [167, 2274, 4587, 2378, 194], LLR 3.14 (bounds ±2.94) after stage 19, 19,200 games (runs 43330489013 to 43356312529; 10:21 PM EST); sprt-log. Ledger idea `skip-check-exempt`. **Port:** 5cd267c's change (relative to 96ebfec) with cb66f9b's switch-on onto phase-4 016d952 alone (branch adopt/skip-check-exempt; 46f2b1e, 6c5eaf4 and 016d952 changed no search code and no bench): `gives_direct_check` (D13's test as one helper, also called by `quiet_order_score`, no behaviour change), the skip's new condition, the switch `UseSkipCheckExempt` (now on), the tests-only accessor `Searcher::butterfly_edit` and the tests; the code lines equal cb66f9b's diff against 96ebfec apart from the switch's comment and the default check's comment. **Bench equivalence** (clang-release, Windows, r8brft1): with the exemption off 9,118,607 / 208629aa15e140a9, phase-4's; with it on 9,443,408 / 6d421599a985f97c, byte for byte cb66f9b's tests/bench-r8brft1.ref, so the port equals the tested code. Bench 9,443,408 / 6d421599a985f97c (r8brft1), every reference re-pinned from its own build. Tests: clang-release (Windows): every non-slow test passes (34 of 34, eval skipped as usual, bench_parity included). clang-debug: pruning (31 cases), ordering (16 cases) and search (27 cases) pass; clang-stats: search_stats (11 cases) passes. Speed: bench/ab_search.py (clang-release, Windows, not pinned; A = phase-4 016d952, B = the port's build of this commit's engine code from the uncommitted tree on 016d952, r8brft1; identity checked on all 24 runs): 12 interleaved rounds, median nps -0.1%, best +0.2%, under the 3.0% noise threshold: no significant difference. The bench searches 3.6% more nodes (9,443,408 against 9,118,607). No constant; names screened at 5cd267c (no match in Stockfish, Ethereal, Berserk or Weiss; ORIGINALITY.md). Records: SPRT log, the constants table (the exemption's row, a definition), ideas.md (idea 74), final-retune.md (p unchanged), tools/gauntlet/transfer.json (the adopted entry at the STC estimate +2.80, ci95 3.43, with the non-regression result as its basis; no stopping-bias record, as the STC was capped, not passed, as for E1). The switch stays until the Phase 4 re-validation. |
| 2026-11-12 | **History ageing between searches (the engine survey's D17, think tank R16; night queue item 52a) adopted on its STC pass at `HistoryKeepQuarters` 2, pre-approved by the owner** (the owner's rule of 2026-11-11: one design R SPRT at the natural value, adopted if it passes; the coordinator's overnight build list of 2026-11-11, item 3: "D17 / R16 - history ageing between searches. nat/retry"). survey-d17-stc (STC 8+0.08, Hash 16, design R [0, 6], cap 8, futility look after 2 stages, from stage 0): test sprt/d17-history-ageing-2 ee3a6c7 (the switch on, `HistoryKeepQuarters` 2) against off tier2/d17-history-ageing 94999a9 (phase-4 a95e269's engine with the ageing built in, off; no ProbCut, E1, history skip, drift table, D8, D13 or exemption), bench 10,166,167 / d874b380155a2e8c on both (bench cannot see the ageing), r8brft1 on both sides, **+5.71 ± 3.77 Elo** (nElo +9.74 ± 6.43), Ptnml [132, 1278, 2626, 1402, 162], **H1** (LLR 3.75, bounds −1.56, 2.77) after stages 0-6, 11,200 games, no time losses (runs 43350847538 to 43363398879; 11:25 PM EST 2026-11-12; sprt-log). Ledger idea `d17-history-ageing`, try 1 (the retry at 3 quarters, item 52b, not needed). **Port:** 94999a9's change (relative to a95e269) with ee3a6c7's switch-on onto phase-4 1b5a482 alone (branch adopt/d17): the tables' `age` (QuietHistory, PairHistory, TakeHistory), `Searcher::age_histories` and its call at each search's start in `deliberate` (after the TT's age advance), the switch `UseHistoryAgeing` (now on), `HistoryKeepQuarters` 2 in the parameter table (after `HistoryBonusCap`, range 0-4, step 1) and the tests; the code lines equal ee3a6c7's diff against a95e269 apart from the switch list's and the parameter table's merge beside the entries adopted since (ProbCut, E1, the history skip, the drift tables, D8, D13, the exemption; ee3a6c7's switch entry, which sat on `UseThreatBuckets`' line, has its own line) and the comments (the switch's comment, the default checks' comments); both tier-2 all-switches cases (test_pruning, test_pruning_review) list it. The same tables are aged as tested: the butterfly history (every threat bucket), reply, follow and take. The drift tables (eval_drift.hpp, added since the tested base) are not aged; whether they should be is not measured (UNVERIFIED; a follow-up for the owner). **Bench equivalence** (clang-release, Windows, r8brft1): with the ageing on, 9,443,408 / 6d421599a985f97c, phase-4 1b5a482's; with it off (a build with the switch's default flipped), the same 9,443,408 / 6d421599a985f97c. Each bench position starts from cleared histories, so ageing them changes nothing, as on the tested pair (both 10,166,167 / d874b380155a2e8c); the port's tests check that it changes a second search and that a first search after `clear_history()` equals the switch-off one. No bench reference changes. Bench 9,443,408 / 6d421599a985f97c (r8brft1), unchanged. Tests: clang-release (Windows): every non-slow test passes (34 of 34, eval skipped as usual, bench_parity included). clang-debug (Windows): the ordering, pruning and search suites pass (3 of 3). Speed: bench/ab_search.py (clang-release, Windows, not pinned, the shared machine busy; A = phase-4 1b5a482, B = the port's build of this commit's engine code from the uncommitted tree on 1b5a482, r8brft1; identity checked on all 24 runs, `--same-nodes`): 12 interleaved rounds, median nps +0.9%, best +2.5%, under the 3.0% noise threshold: no significant difference. The bench pays one ageing pass per position (each position is its own search, on cleared tables), so the pass's price is inside that measurement; the bench's nodes are unchanged. Names and the constant screened on 2026-11-11 (no name match; 2 quarters matches none; the idea a near match to Stockfish's current head, credited; ORIGINALITY.md). Records: SPRT log, the constants table (`HistoryKeepQuarters` adopted), ideas.md (idea 89), final-retune.md (one class (a) dimension), tools/gauntlet/transfer.json, ORIGINALITY.md (the screen's row, with the adoption). The switch stays until the Phase 4 re-validation. |
| 2026-11-13 | **The improving flag in late move pruning (the engine survey's B9, think tank R17; idea 90; night queue item 53a) adopted on its STC pass at `LmpImprovingEighths` 1, pre-approved by the owner** (the owner's rule: a search item that passes its design R SPRT is adopted, one at a time, with bench-equivalence checks; the coordinator's overnight build list of 2026-11-11, item 4: "B9 / R17 - improving flag as a measured mean shift in LMP, then LMR. R-STC"). survey-b9-lmp-stc (STC 8+0.08, Hash 16, design R [0, 6], beta 0.20, cap 8, futility look after 2 stages, from stage 0): test sprt/b9-improving-lmp 3273148 (`UseImprovingLmp` on, `LmpImprovingEighths` 1; bench 9,874,402 / 7065feb1fafd4e5f) against off tier2/b9-improving 74e485a (phase-4 a95e269's engine with both uses built in, off; no ProbCut, E1, history skip, drift table, D8, D13, exemption or D17; bench 10,166,167 / d874b380155a2e8c), r8brft1 on both sides, **+6.82 ± 4.37 Elo** (nElo +11.87 ± 7.61), Ptnml [85, 890, 1907, 1019, 99], **H1** (LLR 3.53, bounds −1.56, 2.77) after stages 0-4, 8,000 games, no time losses (runs 43365482176 to 43373575905; 12:59 AM EST 2026-11-13; sprt-log). Ledger idea `b9-improving-lmp`, try 1. **Port:** 74e485a's change (relative to a95e269) with 3273148's switch-on onto phase-4 254841c alone (branch adopt/b9-lmp): `PlyFrame::pruning_eval` (16 bits in the frame's padding; the 2,704-byte guard holds), the flag in `negamax` and the root frame's reset in `deliberate`, both uses (`UseImprovingLmp`, now on; `UseImprovingLmr`, off: its own SPRT, survey-b9-lmr-stc, night item 53d, runs against the same off 74e485a), `LmpImprovingEighths` 1 (after `LmpQuietAllowance`, range 0-4, step 1) and `LmrNotImprovingPlies` 1 (after `CutNodeLmrPlies`, range 0-3, step 1; unused while its switch is off) in the parameter table, and the tests. The code lines equal 3273148's diff against a95e269 apart from the switch list's and the parameter table's merge beside the entries adopted since (74e485a's two switch entries, which sat on `UseThreatBuckets`' line, have their own lines), the root reset's place beside the drift keys' set-up, and the comments; both tier-2 all-switches cases (test_pruning, test_pruning_review) list both uses, and the B9 case's switch-off side sets both uses off explicitly (the LMP use is on by default). The flag compares `prune_eval`, the variable RFP uses, as tested; since the minor drift table's adoption (2026-11-12) it includes that table's term, which the tested base did not have. R17's kill rule (two H0s among the LMP and LMR uses drop the flag) no longer applies to the LMP use. **Bench equivalence** (clang-release, Windows, r8brft1): with the LMP use off, 9,443,408 / 6d421599a985f97c, phase-4 254841c's; with it on and ProbCut, E1, the history skip, the minor drift table, D8, D13, the exemption and D17 off (the tested base had none of them), 9,874,402 / 7065feb1fafd4e5f, byte for byte 3273148's tests/bench-r8brft1.ref, so the port equals the tested code. **Bench changes (intended):** 9,430,886 / 647c5ee9a57cae18 with r8brft1 (0.1% fewer nodes than 9,443,408); every other reference re-pinned from its own build. Tests: clang-release (Windows): every non-slow test passes (34 of 34, eval and uci_timing skipped as usual, bench_parity included); clang-debug: ordering (17 cases), pruning (33) and search pass; clang-stats: search_stats passes (11 cases). Two cases pin the LMP use off, each set on trees built before it existed: test_search's null-move zugzwang-guard case (with the use on, its first pawn ending's depth-9 search plays g5f4 instead of b7b5; a UCI check finds b7b5 at depths 10 to 12) and search_stats X2's zero-band carry-over comparison (with the use on, carried 2829/8144 against cleared 2872/8737; the head passes it). Both flagged for the owner's review. Speed: bench/ab_search.py (clang-release, Windows, 12 interleaved rounds, not pinned, identity checked on all 24 runs), A = 254841c, B = the port: median nps -2.1%, best -1.7%, under the 3.0% noise threshold, so no significant difference. Names and constants screened on 2026-11-11 (no non-generic name match; 9/8 and 7/8 match none; the definition matches Stockfish sf_12 to sf_16, credited; ORIGINALITY.md). Records: SPRT log, the constants table (the flag's definition row, `LmpImprovingEighths` adopted, `LmrNotImprovingPlies` still a candidate), ideas.md (idea 90), final-retune.md (one class (a) dimension), tools/gauntlet/transfer.json, ORIGINALITY.md (the 2026-11-11 screen's row, with the adoption). The switches stay until the Phase 4 re-validation. |
| 2026-11-13 | **The improving flag in LMR (the engine survey's B9, think tank R17; idea 90; night queue item 53d) adopted on its STC pass at `LmrNotImprovingPlies` 1, pre-approved by the owner** (the owner's rule: a search item that passes its design R SPRT is adopted, one at a time, with bench-equivalence checks; the coordinator's overnight build list of 2026-11-11, item 4: "B9 / R17 - improving flag as a measured mean shift in LMP, then LMR. R-STC"). survey-b9-lmr-stc (STC 8+0.08, Hash 16, design R [0, 6], beta 0.20, cap 8, futility look after 2 stages, from stage 0): test sprt/b9-improving-lmr d3b3930 (`UseImprovingLmr` on, `LmrNotImprovingPlies` 1, the LMP use off; bench 7,186,034 / debc7162447eb810) against off tier2/b9-improving 74e485a (phase-4 a95e269's engine with both uses built in, off; no ProbCut, E1, history skip, drift table, D8, D13, exemption or D17; bench 10,166,167 / d874b380155a2e8c), r8brft1 on both sides, **+12.71 ± 7.00 Elo** (nElo +21.88 ± 12.04), Ptnml [35, 336, 750, 435, 44], **H1** (LLR 3.00, bounds −1.56, 2.77) after stages 0-1, 3,200 games, no time losses (runs 43375821546 and 43377962512; 1:38 AM EST 2026-11-13; sprt-log). Ledger idea `b9-improving-lmr`, try 1. **Port:** phase-4 17717a8 already carried both uses (B9's LMP adoption ported 74e485a's change, the LMR use off, `LmrNotImprovingPlies` 1 in the parameter table); this adoption (branch adopt/b9-lmr) only turns `UseImprovingLmr` on, the same one-line switch-on as d3b3930's against 74e485a, and updates test_pruning's B9 default checks (both uses on). Stats builds only: X2's LMR history probe now keeps B9's not-improving plies in its counterfactual reduction, as its comment says it keeps every other term of the real one (search_stats X2's check that the probe's changes need a firing failed without it with the use on; d3b3930 had the same omission; no release-build change). Tested without the LMP use (off on both sides), it is adopted on top of it under the one-at-a-time rule; the stacking check that follows covers the interaction. R17's kill rule (two H0s among the LMP and LMR uses drop the flag) no longer applies. **Bench equivalence** (clang-release, Windows, r8brft1): with the LMR use off, 9,430,886 / 647c5ee9a57cae18, phase-4 17717a8's; with it on and the LMP use, ProbCut, E1, the history skip, the minor drift table, D8, D13, the exemption and D17 off (the tested base had none of them), 7,186,034 / debc7162447eb810, byte for byte d3b3930's tests/bench-r8brft1.ref, so the port equals the tested code. **Bench changes (intended):** 6,238,381 / 8d4a17943d604c99 with r8brft1 (33.9% fewer nodes than 9,430,886); every other reference re-pinned from its own build. Tests: clang-release (Windows): every non-slow test passes (34 of 34, eval and uci_timing skipped as usual, bench_parity included; the search suite re-run after the stats probe's fix, 27 of 27); clang-debug: ordering (17 cases), pruning (33) and search (27) pass; clang-stats: search_stats passes (11 cases) with the probe's fix (X2 failed without it, the check that the probe's changes need a firing). No new pin: the two cases that pin the LMP use off (test_search's null-move zugzwang-guard case and search_stats X2's zero-band carry-over comparison) pass with the LMR use on, so neither pins it. Speed: bench/ab_search.py (clang-release, Windows, 12 interleaved rounds, not pinned, identity checked on all 24 runs), A = 17717a8, B = the port: median nps +0.5%, best +0.3%, under the 3.0% noise threshold, so no significant difference. Names and constants screened on 2026-11-11 (no non-generic name match; `LmrNotImprovingPlies` 1 matches Ethereal and Berserk, near matches Weiss and Stockfish sf_11 to sf_16, the smallest unit, credited; ORIGINALITY.md); no new name or constant since. Records: SPRT log, the constants table (the flag's definition row, `LmrNotImprovingPlies` adopted), ideas.md (idea 90), final-retune.md (one class (a) dimension), tools/gauntlet/transfer.json, ORIGINALITY.md (the 2026-11-11 screen's row, with the adoption). The switches stay until the Phase 4 re-validation. |
| 2026-11-13 | **Round-once LMR with a centred history term (think tank R20, the engine survey's C10 in its centred form; ideas 43 and 42; night queue items 80a and 80c) adopted on its STC and LTC passes at `LmrHistoryPerPly` 10,000, pre-approved by the owner** (2026-11-11: "R-STC, then LTC"; a search item that passes its SPRTs is adopted, one at a time, with bench-equivalence checks). test sprt/r20-centred-lmr ea2075e (`UseCentredLmrHistory` on, `LmrHistoryPerPly` 10,000; bench 11,073,869 / b5af8584ce121128) against off tier2/r20-centred-lmr 0f48efb (phase-4 26323e1's engine with the term built in, off; no ProbCut, E1, history skip, drift table, D8, D13, exemption, D17 or B9; bench 10,166,167 / d874b380155a2e8c), r8brft1 on both sides. STC: r20-centred-lmr-stc (STC 8+0.08, Hash 16, design R [0, 6], beta 0.20, cap 8, futility look after 2 stages, from stage 0): **+8.04 ± 4.04 Elo** (nElo +13.84 ± 6.95), Ptnml [103, 1073, 2252, 1243, 129], **H1** (LLR 5.17, bounds −1.56, 2.77) after stages 0-5, 9,600 games, no time losses (runs 43313118399 to 43327533834; 6:35 PM EST 2026-11-12); a first stage-0 dispatch, run 43253236046, ended in failure (one shard's tools step) and is not a result. LTC: r20-centred-lmr-ltc (LTC 40+0.4, design R [0, 6], cap 6): **+6.21 ± 4.35 Elo** (nElo +11.94 ± 8.35), Ptnml [35, 706, 1725, 829, 33], **H1** (LLR 2.96) after stages 0-3, 6,656 games, no time losses (runs 43358461914, 43367513386, 43377038348, 43386556188; 3:54 AM EST 2026-11-13); sprt-log. Ledger idea `r20-centred-lmr`, try 1. **Port** (branch adopt/r20-lmr): 0f48efb's change (relative to 26323e1) onto phase-4 1449010, `UseCentredLmrHistory` on (ea2075e's switch-on), `LmrHistoryPerPly` after `LmrNotImprovingPlies` in the parameter table, the centres cleared with the histories beside the drift tables, test_pruning's two R20 cases (the default check now on) and the tier-2 all-switches line. **How it combines with B9's LMR use** (adopted after R20's base, 1449010): the whole-ply sum is the table plus the correction, less check relief, plus the cut-node and B9's not-improving plies; with R20 on the same whole-ply terms (B9's among them) enter the 64ths sum as whole multiples of 64 beside the 64ths table and the centred history term, and the sum is rounded once. A whole number of plies added before the rounding moves the result by exactly that many plies, so each feature acts as it was tested: B9 adds its ply to R20's rounded reduction, R20 rounds its table and term with every other term in place. With every history table at zero the tree equals the switch-off tree (test_pruning, with B9 on). D17's ageing leaves R20's running centres as they are (the centres are cleared only with the histories, as tested); they follow the aged tables within a few thousand LMR sites (an untested interaction, as is B9 with R20; the stacking check that follows covers them). Stats builds only: X2's LMR history probe (FORK_SEARCH_STATS) now takes its shift from the real reduction's sum (R20's rounded one when on), so it keeps R20's term and rounding as it keeps every other term; ea2075e's probe recomputed the whole-ply sum (no release-build change). **Bench equivalence** (clang-release, Windows, r8brft1): with R20 off, 6,238,381 / 8d4a17943d604c99, phase-4 1449010's; with it on and ProbCut, E1, the history skip, the minor drift table, D8, D13, the exemption, D17 and B9's LMP and LMR uses off (the tested base had none of them), 11,073,869 / b5af8584ce121128, byte for byte ea2075e's tests/bench-r8brft1.ref, so the port equals the tested code. **Bench changes (intended):** 6,426,679 / 4c4375887f835cc7 with r8brft1 (3.0% more nodes than 6,238,381); every other reference re-pinned from its own build. Tests: clang-release (Windows): every non-slow test passes (34 of 34, eval and uci_timing skipped as usual, bench_parity included); clang-debug: ordering (17 cases), pruning (35, R20's two new) and search (27) pass; clang-stats: search_stats passes (11 cases). **One case flipped with R20 on and is pinned:** search_stats X2's zero-band carry-over comparison (carried 1948/7260 against cleared 1988/8936 with R20 on), the tree-shape comparison B9's LMP use already pins off; it tests the history carry-over between searches, not strength, so R20 is pinned off on both of its searchers with a comment in the B9 pin's style. Because that pin takes R20 out of the case's probe check, the case now also runs the probe check on a default-switches search (R20 and B9 on): fault check, with ea2075e's whole-ply probe that check fails, with the port's it passes. No other case flipped (test_search's null-move zugzwang-guard case, which pins the LMP use off, passes). Speed: bench/ab_search.py (clang-release, Windows, 12 interleaved rounds, not pinned, identity checked), A = 1449010, B = the port: median nps +0.9%, best +0.5%, under the 3.0% noise threshold, so no significant difference (identity checked on all 24 runs). Names and constants screened 2026-11-13 (originality-checker; Stockfish def601cc15, Ethereal 0e47e9b67f, Berserk d7e1f05045, Weiss c735b8f3d2): no name matches; `LmrHistoryPerPly` 10,000 is a near match to Stockfish's current master (its LMR history term, in effective ratio only, not in form), a natural value (one ply per `HistoryMax`), credited under the owner's rule of 2026-11-11; the 64ths unit and the centre's shift 10 match none (ORIGINALITY.md). Records: SPRT log, the constants table (three R20 rows, `LmrHistoryPerPly` adopted), ideas.md (ideas 43 and 42), final-retune.md (one class (a) dimension), tools/gauntlet/transfer.json (the LTC result as R20's basis), ORIGINALITY.md. The switch stays until the Phase 4 re-validation. |
| 2026-11-13 | **CalibratedScore adopted (owner, about 6:15 AM EST: "adopt CalibratedScore (display-only; off in all harnesses, datagen and labeling tools, never used inside search)").** The owner's order of 2026-11-12 (about 10:45 PM EST) measured Fork's eval against game results, balanced and UHO starts, search and static, by band, with declared rules (~/fork-data/calib-1112, method.md first, results.md): every set's search scores convert more surely than r8brft1's own scale says (logistic scale k 56-69 cp against S = 88; UHO decision audit 69.4, 95% 65.1-74.0), not more so on UHO starts (k(balanced)/k(UHO) 0.81, 0.75-0.88), no band misjudged beyond 0.03, and queens on much steeper than off (UHO 58.5 against 87.1, mostly in the search score): branch (c), the display calibration built and the data arms designed (arm Q, the queens-on unequal-material slice, prepared and gate-passed; ~/fork-data/calib-1112/design-b.md). **What it is:** the UCI option `CalibratedScore` (check, default on for GUIs and TCEC): `score cp N` shows N x 88 / 67 (`DisplayTargetScale`, r8brft1's S; `DisplayFittedScale`, the 40+0.4 UHO self-play fit, 67.0 cp, 95% 63.9-69.5); mate and tablebase scores, bounds, pv and bestmove unchanged; monotonic, odd, below the tablebase band (Options; Search constants). **Never inside the search:** only the session's two info-line printers call it, and the option is read once at go on the session's thread; the CTest `score_display_boundary` fails if any other source names it; fork_datagen's shards are byte-identical to the head's build. **Off in every harness and tool:** fastchess games (tools/sprt.sh, tools/cloud/run_shard.sh: SPRT, head-to-head, fixed-node and cloud shards; gauntlet.yml: anchors, the anchor check, decision audits; elo_gauntlet.sh; evolve/match.py) set `option.CalibratedScore=false` on both sides (fastchess 1.8.2 only warns on an older build), and every tool that reads Fork's scores over UCI sets it false; `tools/check_score_display_off.py` (scripts/check.sh) fails on a launcher that does not. **TCEC effect:** TCEC has no eval-based win adjudication now; its draw rule (eval within +-0.25 for 8 plies with at most 6 pieces) and its outage rule (+-10; +-0.15 past move 35) read the shown score, so with the option on they correspond to internal +-0.19, +-7.6 and +-0.11 (docs/kb/competition.md; whether both engines' evals must meet the draw rule is UNVERIFIED there). Refit `DisplayFittedScale` for each new default network. Bench 6,426,679 / 4c4375887f835cc7 unchanged (r8brft1). Screens: no match (ORIGINALITY.md). |
| 2026-11-13 | **The linear history bonus (think tank R15, the engine survey's D11; idea 173; night queue item 82d) adopted on its STC pass at `LinearBonusPerPly` 125, pre-approved by the owner** (2026-11-11: one SPRT at the natural value, adopted on a pass, one at a time). test sprt/d11-linear-bonus f289442 (`UseLinearBonus` on, `LinearBonusPerPly` 125; bench 10,094,473 / ef51ee8677008fc9) against off tier2/d10-d11-history-bonus 23e579e (phase-4 26323e1's engine with D10 and D11 built in, both off; no ProbCut, E1, history skip, drift table, D8, D13, exemption, D17, B9 or R20; bench 10,166,167 / d874b380155a2e8c), r8brft1 on both sides. d11-linear-bonus-stc (STC 8+0.08, Hash 16, design R [0, 6], beta 0.20, cap 8, futility look after 2 stages, from stage 0): **+8.98 ± 5.70 Elo** (nElo +15.50 ± 9.83), Ptnml [52, 527, 1129, 629, 63], **H1** (LLR 2.98, bounds −1.56, 2.77) after stages 0-2, 4,800 games, no time losses (runs 43445560313, 43448609701, 43451798490; 10:40 AM EST 2026-11-13); sprt-log. Ledger idea `d11-linear-bonus`, try 1 (the retry at 250, item 82e, not needed). **Port** (branch adopt/d11-linear-bonus): 23e579e's D11 change (relative to a95e269, phase-4 26323e1's engine) with f289442's switch-on onto phase-4 49494bb: `linear_bonus_for_depth` (quiet_history.hpp), `Searcher::cutoff_bonus`, `record_cutoff`'s bonus taken from it, the switch `UseLinearBonus` (now on), `LinearBonusPerPly` 125 in the parameter table (after `HistoryBonusCap`, range 63-250, step 9), test_ordering's linear-bonus checks, test_pruning's D11 case (the default check now on) and both tier-2 all-switches cases (test_pruning, test_pruning_review; the review case also lists R20, on by default, which its adoption had not added). D10, the TT-cutoff credit built on the same branch, was rejected by its own SPRT (d10-tt-cut-credit-stc, design R [0, 6] at STC: a futility stop after stage 1, −2.93 ± 6.97 Elo, nElo −5.06 ± 12.04, 3,200 games, runs 43438699344 and 43442565958; 9:43 AM EST 2026-11-13), and its code (`credit_tt_move`, `UseTtCutCredit`, the hook at negamax's TT cutoff, its test case) is left out of the port: it is separable (D11 needs only `cutoff_bonus` and `linear_bonus_for_depth`). **Where it sits:** the amount is chosen once per cutoff, at the top of `record_cutoff` (`cutoff_bonus`), upstream of every update there, as tested: the take history's bonus and maluses, the butterfly history's (in each move's threat bucket), and the reply and follow tables' through D8's summed update (`apply_from_sum`, adopted after D11's base), which takes the same amount and changes only how the self-limiting term is read; with D8 off the per-table update takes it as tested. D17's ageing (between searches) and R20's running centres (read at LMR sites) act on the tables after the fact: the larger shallow bonuses change the values R20's centres average (expected: the centres track the tables, so they follow the new level), and D17 ages whatever the tables hold. With the switch on, `HistoryBonusFactor` is unused (the quadratic form acts only with it off). D11 with D8, D17 and R20 are untested interactions; the stacking check that follows covers them. **Bench equivalence** (clang-release, Windows, r8brft1): with D11 off, 6,426,679 / 4c4375887f835cc7, phase-4 49494bb's; with it on and ProbCut, E1, the history skip, the minor drift table, D8, D13, the exemption, D17, B9's LMP and LMR uses and R20 off (the tested base had none of them), 10,094,473 / ef51ee8677008fc9, byte for byte f289442's tests/bench-r8brft1.ref, so the port equals the tested code. **Bench changes (intended):** 6,624,814 / 8aa09aa2e1ed5ede with r8brft1 (3.1% more nodes than 6,426,679); every other reference re-pinned from its own build. Tests: clang-release (Windows): every non-slow test passes (35 of 35 with -j1, eval and uci_timing skipped as usual, bench_parity included); clang-debug: ordering (17 cases), pruning (36, D11's new case) and search (27) pass; clang-stats: search_stats passes (11 cases). No case flipped with D11 on, so no new pin (the existing B9 and R20 pins, test_search's null-move zugzwang-guard case and search_stats X2's zero-band carry-over comparison, pass unchanged). Speed: bench/ab_search.py (clang-release, Windows, 12 interleaved rounds, not pinned, the shared machine busy; identity checked on all 24 runs), A = 49494bb, B = the port: median nps -2.9%, best -2.6%, under the run's 8.9% noise threshold, so no significant difference (the two search different trees: 6,426,679 against 6,624,814 bench nodes; the code change itself is one multiply in place of a square per cutoff). Names and the constant screened 2026-11-11 (a separate agent; no name match; the slope 125 a near match to Stockfish, credited under the owner's rule; ORIGINALITY.md); no new name since. Records: SPRT log, the constants table (`LinearBonusPerPly` adopted; the history bonus row), ideas.md (idea 173), final-retune.md (one class (a) dimension; `HistoryBonusFactor` inert while the switch is on), tools/gauntlet/transfer.json, ORIGINALITY.md (the screen's row, with the adoption). The switch stays until the Phase 4 re-validation. |
| 2026-11-13 | **The quiescence move cap (the engine survey's B16; idea 120; night queue items 60a and 60b) adopted on its retry's STC pass at `QuiesceMoveCap` 2, pre-approved by the owner's rule** (2026-11-11: one SPRT at the natural value, one retry at a second value if it fails, adopted on a pass, one at a time). test sprt/b16-qs-lmp-2 73dd82f (`UseQuiesceMoveCap` on, `QuiesceMoveCap` 2; bench 9,592,817 / 13fdc241be4650b2) against off tier2/b16-qs-lmp af8f35c (phase-4 ab70fa5's engine with the cap built in, off; ProbCut in; no E1, history skip, drift table, D8, D13, exemption, D17, B9, R20 or D11; bench 9,639,207 / 07f7ae19b9250f38), r8brft1 on both sides. First, the first try at the natural value 3, b16-qs-move-cap-stc (test sprt/b16-qs-lmp a03b0db, bench 9,773,608 / 77d045463a0c9b36; from stage 0), stopped for futility after stage 1: −0.22 ± 6.92 Elo (nElo −0.38 ± 12.04), Ptnml [38, 376, 775, 372, 39], LLR −0.54, 3,200 games, no time losses (runs 43441749955 and 43444719077; 9:57 AM EST 2026-11-13). Then b16-qs-move-cap-retry (STC 8+0.08, Hash 16, design R [0, 6], beta 0.20, cap 8, futility look after 2 stages, on fresh openings from stage 2): **+8.90 ± 5.56 Elo** (nElo +15.75 ± 9.83), Ptnml [35, 547, 1135, 626, 57], **H1** (LLR 3.04, bounds −1.56, 2.77) after stages 2-4, 4,800 games, no time losses (runs 43447742059, 43450913249, 43454049003; 10:53 AM EST 2026-11-13); sprt-log. Ledger idea `b16-qs-move-cap`, tries 1 and 2. **Port** (branch adopt/b16-qs-cap): af8f35c's change (relative to ab70fa5) with 73dd82f's switch-on and value onto phase-4 929f114: the cap in `quiesce`, the switch `UseQuiesceMoveCap` (now on), `QuiesceMoveCap` 2 in the parameter table (after ProbCut's rows, range 1-6, step 1), test_pruning's B16 case (the default check now on), both tier-2 all-switches cases (test_pruning, test_pruning_review), and the exact searches without it (test_search's `exact_switches`, as tested; test_pruning_review's `no_pruning`, as the history skip's adoption did, since it prunes moves). **Where it sits:** one test at the top of the quiescence search's move loop, out of check only, as tested: a node keeps the first `QuiesceMoveCap` moves the selector gives (the TT move, then captures and queen promotions by victim and take history, SEE-losing captures already dropped), and its result is the best of the stand pat and those moves; in check every evasion is searched. Every quiescence search takes it, ProbCut's zero-window quiescence probe included (ProbCut was in the tested base). The features adopted after B16's base change what it caps, not the cap: the minor drift table moves the stand pat (`drift_estimate`), and D11's linear bonus and D17's ageing change the take history that orders the captures, so which two are kept; E1, the history skip, D8, D13, B9 and R20 act in the main search only. B16 with them are untested interactions; the stacking check that follows covers them. **Bench equivalence** (clang-release, Windows, r8brft1): with B16 off, 6,624,814 / 8aa09aa2e1ed5ede, phase-4 929f114's; with it on and E1, the history skip, the minor drift table, D8, D13, the exemption, D17, B9's LMP and LMR uses, R20 and D11 off (the tested base had none of them), 9,592,817 / 13fdc241be4650b2, byte for byte 73dd82f's tests/bench-r8brft1.ref, so the port equals the tested code. **Bench changes (intended):** 6,064,962 / ad41c57a026bb021 with r8brft1 (8.5% fewer nodes than 6,624,814); every other reference re-pinned from its own build. Tests: clang-release (Windows): every non-slow test passes (35 of 35 with -j1, eval skipped as usual, uci_timing run and passed this time, bench_parity included); clang-debug: ordering (17 cases), pruning (37, B16's new case) and search (27) pass; clang-stats: search_stats passes (11 cases). No case flipped with B16 on, so no new pin (the existing B9 and R20 pins, test_search's null-move zugzwang-guard case and search_stats X2's zero-band carry-over comparison, pass unchanged); the two exact searches switch the cap off by definition (test_search's exact_switches as in the tested commit, test_pruning_review's no_pruning as the history skip's adoption did). Speed: bench/ab_search.py (clang-release, Windows, 12 interleaved rounds, not pinned, the shared machine busy; identity checked on all 24 runs), A = 929f114, B = the port: median nps +5.1%, best -1.5%, under the run's 15.8% noise threshold, so no significant difference (the two search different trees: 6,624,814 against 6,064,962 bench nodes; the code change itself is one comparison per quiescence move). Names and constants screened 2026-11-12 (the coordinator's separate agent; no name match; 3 no match; 2 matches Stockfish sf_12 and later, a natural value credited under the owner's rule; the idea is prior art in Stockfish, credited; ORIGINALITY.md); no new name since. Records: SPRT log (both tries), the constants table (`QuiesceMoveCap` adopted), ideas.md (idea 120), final-retune.md (one class (a) dimension), tools/gauntlet/transfer.json, ORIGINALITY.md (the screen's row, with the adoption). The switch stays until the Phase 4 re-validation. |
| 2026-11-13 | **Over-pruning check, tactical part: no broad over-pruning; ProbCut kept, its margin range widened, a priority switch in the removal round (owner, about 2:00 PM EST).** Phase-4 929f114 against d33a4db (the head before ProbCut) on Arasan's wacnew (WAC, 300) and ecmgcp (ECM, 183), MIT, test data only (ORIGINALITY.md): solved 335/412/385/434 vs 334/409/386/441 at 100k nodes, 1M nodes, 250 ms and 2 s (none significant; the head 1-2 plies deeper). With `UseCaptureProbe` off the head solves 350/429/399/456 (p 0.0026, 0.0033, 0.099, 0.0002), although ProbCut passed its LTC games (+9.40 ± 5.03). Decisions: keep ProbCut; `CaptureProbeMargin`'s final-retune range 60-200 (was 40-160; src/tune/params.hpp, tune builds only, release bench unchanged); ProbCut is a priority switch in the factorial removal round, its removal tested at LTC (docs/research/phase4-designs/factorial-removal-round.md §5.3). The LTC part of the check (the head against d33a4db at 40+0.4) is running. |
| 2026-11-13 | **Tuning-build LMR tables fixed for LLVM-MinGW clang (bug found by the tactics agent).** With LTO, LLVM-MinGW clang ran the inline variables' dynamic initialisers in reverse order (reproduced with a three-file program: without LTO, and with GCC, the order is right; ELF builds are unaffected, so CI's Linux tuning-build parity and the GitHub SPRT/SPSA builds never saw it), so `LmrFine` was built from a still-zero `LmrPlies`: every 64ths entry 31, round-once LMR never reduced, and a Windows clang FORK_TUNE bench of 14,927,773 for 6,064,962 until a setoption rebuilt the tables. Fix: each tuning-build initialiser reads only the (constant-initialised) parameters, never the other table; release builds unchanged (constexpr, bench 6,064,962). Guards: a pruning test that the startup tables equal freshly built ones, and a Windows clang FORK_TUNE step in CI (bench parity, the pruning and params suites). No other table is built from the parameters at static initialisation. Affected: Windows clang LTO tuning builds from 0f48efb (tier2/r20-centred-lmr, only with `UseCentredLmrHistory` on) and from 4c864c3 on phase-4 (on by default) up to this fix, in `fork bench` and UCI `go` alike, unless a numeric parameter's setoption was sent (a `Use*` switch, Hash or Threads does not rebuild the tables). |
| 2026-11-13 | **Leading explanation for the UHO conversion failures: a two-sided misjudgment, queens-on edges underrated and level queenless positions overrated (owner, about 4:20 PM EST; the UHO/SF19 analysis of 2026-11-13); the `uho_diag` benchmark measures it per net.** Against Stockfish 19 (gauntlet runs 43492072142 and 43492038248, no adjudication) Fork won none of its 200 advantaged UHO starts: SF19 put them at +0.98 (median) and Fork's own raw score at +0.50; the edge was lost in 198 of 200, mostly with queens on and material level; in level positions Fork stayed more optimistic than SF (SF 0.00, Fork +0.20 median); every loss began queens-on. `tools/nnue/uho_diag.py` (report only, never a gate) measures a net on three fixed sets drawn from those games by declared rules (seed 20261113; test data only, outside the repository, ORIGINALITY.md): adv (200 advantaged book positions; SF19 median +97.5 cp), levelql (272 level-material queenless positions where SF19 said within 10 cp of 0, scored from Fork's side), qtrade (528 positions with one queen each where the side to move is +30 to +100 cp by SF19 and a queen capture, offer or game-line trade is available). It reports the static evaluation (R-int, equal to the binary's on every position) and a 100k-node search (Threads 1, Hash 16, CalibratedScore off), and on qtrade whether the search line trades queens. Baselines (raw cp, medians, static / search; the sets as regenerated after the game-id fix below): r8brft1 adv +40 / +50 (0.42 / 0.51 of SF19's), levelql +24 / +17.5; r8btd90, r8bep1, r8bep2 and the 8c-early r8ec1 and r8ei801 within 4 cp of it; older nets underrate adv more (s512 static +33.5, b0r2 +33). Queen trades when slightly ahead: the nets trade in 0.08-0.09 of SF-to-move positions (SF19 0.05) and 0.11-0.14 of Fork-to-move ones (Fork's games 0.12), so no clear excess trade preference: the explanation lies in the evaluation's level on both sides. The search repeats exactly (r8brft1 run twice, identical). Retrain 8c runs it per passing arm (post_a1.sh uhodiag, report only), and arm Q and the per-class lambda arm (A2) are to be read on it. Caveat: levelql positions arise from Fork's own choices, so part of its optimism there may be selection (positions Fork steered into because it liked them). **Piece trades (owner, about 4:47 PM EST):** a fourth set, ptrade (931 positions: the side to move +20 to +100 cp by SF19, a rook, knight, bishop or bishop-for-knight trade available by capture, offer or the game line; queenless and queens-on apart), gives per-class trade rates of the search against SF19's own choice (SF to move) and Fork's in-game choice (Fork to move). Baselines (any class): queenless SF-to-move 0.08-0.14 against SF19's 0.07 (110 positions; the excess mostly bishop for knight), queens-on 0.07-0.09 against 0.10 (300); the Fork-to-move groups match Fork's games (0.14-0.17 against 0.16-0.17). On the same positions the nets' searches trade about as often as SF19 did, apart from that small queenless excess near the noise; the per-trade judging is the separate trade analysis's. **Game-id fix (evening, found by the trade analysis):** fastchess repeats a pair's Round number, so the tool's game ids (built from the Round) collided between a pair's two games and shared a per-game seed; the id now carries Fork's colour and the game's number, the four sets were regenerated (counts unchanged; new SHA-256s in ORIGINALITY.md) and every baseline re-run; the resample alone moved r8brft1's levelql static median by 4 cp (+28 to +24), the scale of noise between nets. |
| 2026-11-13 | **CalibratedScore forced off by every harness, branch workflows included (owner, about 4:10 PM EST: "Then make every harness force the option off by default, including branch workflows, with a test").** c7a61ea set the option off in every launcher of the tree (tools/check_score_display_off.py), but a workflow dispatched with an older --ref builds the engines from its inputs and runs the older ref's tools, so a pre-c7a61ea harness could play a post-c7a61ea engine with the option on. Two layers: (1) the dispatch-side guard `tools/jobs/score_display_guard.py` (ENGINE commits; `--ref REV` or `--tree DIR` for the harness): if any engine descends from c7a61ea or its src/ names CalibratedScore, the harness must hold tools/check_score_display_off.py and its own copy must pass on its tree (REV's tree is read in a throwaway repository that borrows this one's objects); called by tools/github/sprt_run.sh before every dispatch on REF's commit as GitHub reports it (so tools/github/h2h_run.sh too), tools/sprt.sh and tools/cloud/aws_spot_sprt.sh on their own checkout or tools commit, the cloud worker (tools/gcp/worker.py, an item running a $W/builds build is failed before it starts) and tools/gcp/vm_install_worker.sh (an older tools commit is refused while a build with the option is installed); (2) the workflow belt `.github/ci/score-display-check.sh`, run in sprt.yml's and gauntlet.yml's build jobs after the build: if a built engine advertises the option, the run's own harness must pass the checker, or the run stops before any game. The checker now also fails on a workflow that plays games (fastchess, cutechess, run_shard.sh, elo_gauntlet.sh, tools/sprt.sh) without that step. A branch older than this cannot check itself, which is why layer 1 exists. Callers outside the repository that run `gh workflow run gauntlet.yml` directly (night queue items) are not covered until they call the guard. Tests (scripts/check.sh quick): tools/jobs/test_score_display_guard.py, tools/test_check_score_display_off.py, tools/gcp/test_worker.py ScoreDisplayTest; with "all", REF scenarios in tools/github/test_sprt_run.sh and a refusal in tools/test_sprt.sh. |
| 2026-11-13 | **CalibratedScore removed (owner, about 7:10 PM EST: "get rid of the cosmetic eval thing that was added, it may cause confusion in the future no need for it").** Reason: a second, rescaled score beside the search's own invites confusion (which number a harness, a log or a reader sees) and nothing needs it. Removed from the engine: the UCI option, src/uci/score_display.hpp (the mapping, `DisplayFittedScale` 67, `DisplayTargetScale` 88), its use in session.cpp's two info-line printers, its tests in uci_options (the mapping case, the on/off identical-trees case with the sanitizer and bound-line fixes 85f590d and 49494bb) and the CTest `score_display_boundary` (cmake/score_display_boundary.cmake); the engine files are back to c7a61ea's parent's. Fork prints the search's own `score cp` again: a new uci_options case checks that a fresh engine's `go depth 6` on Kiwipete reports the score and nodes of the same search run directly (it failed with the option still in: -163 shown against -124 searched, 124 x 88 / 67 = 163). Bench unchanged (display only). **Kept, deliberately, for now:** the `option.CalibratedScore=false` flags in every launcher, tools/check_score_display_off.py, tools/jobs/score_display_guard.py and .github/ci/score-display-check.sh, because builds from c7a61ea up to the removal commit (e.g. the bake/r8ec1 and bake/r8ei801 builds queued for screens) still carry the option and stay in play. For a build without it the flag is a no-op: the pinned fastchess (1.8.2-alpha, f618e345) only warns ("doesn't have option CalibratedScore") and plays (two games to mate at 2+0.02, 2026-11-13). The guard now decides "has the option" by src/ naming CalibratedScore alone (descent from c7a61ea no longer implies it); its tests, test_sprt_run.sh and the worker's ScoreDisplayTest use c7a61ea's engine, not HEAD's, as the one with the option, and a new case builds a real descendant of c7a61ea without the option (refused under the old detection). **Follow-up, not now:** remove the flags, the checker, the guard and the workflow step once no build between c7a61ea and the removal commit is played any more. **TCEC hazard reopened:** the engineering review's "score calibration" hazard (2026-11-11 row, item (4); docs/research/engineering-review-2026-11-11.md W7) is **open** again. The owner's instruction: "Record on the TCEC hazards list: reported-score calibration is open again (CalibratedScore removed at my call); before any TCEC entry, re-check whether Fork's raw scores could trigger TCEC's eval-based adjudication early (using the UHO/SF19 benchmark's numbers for the default net at that time), and decide then." The re-check uses tools/nnue/uho_diag.py's numbers for the then-default net (the advantaged-start and level-queenless medians against SF19) with TCEC's adjudication rules from the KB (docs/kb/competition.md: the draw rule, eval within +-0.25 for 8 consecutive plies with 6 or fewer pieces, whether both engines' evals must be in the band is UNVERIFIED in the KB; the outage rules +-10 and +-0.15; no win adjudication now), and the decision is taken then; listed under Phase 8's TCEC-readiness checks. The calibration study's findings stay as recorded (the k values, 56-69 cp against S = 88; the two-sided misjudgment); only the display feature goes. |
| 2026-11-13 | **Root reductions (bug review 2026-11-11 §3; idea 124; night queue items 64a and 64c) adopted on their STC and LTC passes, pre-approved by the owner** (2026-11-13: "pre-approved adoptions as before (incl. root LMR on an LTC pass)"; the coordinator's overnight build list of 2026-11-12: "Root reductions. R-STC + LTC (depth)"). No new constant. test sprt/root-lmr b56adb9 (`UseRootLmr` on; bench 8,027,262 / 64ebc879047d0f81) against off tier2/root-lmr 350ea3a (phase-4 ab70fa5's engine with root reductions built in, off; ProbCut in; no E1, history skip, drift table, D8, D13, exemption, D17, B9, R20, D11 or B16; bench 9,639,207 / 07f7ae19b9250f38), r8brft1 on both sides, design R [0, 6] nElo, beta 0.20, futility look after 2 stages, from stage 0; ledger idea `root-lmr`, try 1 (the LTC its own class). root-lmr-stc (8+0.08, Hash 16, cap 8): **+17.71 ± 6.74 Elo** (nElo +31.68 ± 12.04), Ptnml [16, 335, 762, 444, 43], **H1** (LLR 4.56) after stages 0-1, 3,200 games, no time losses (runs 43515413836, 43518644286; 5:40 PM EST 2026-11-13). root-lmr-ltc (40+0.4, Hash 64, cap 6): **+14.94 ± 6.24 Elo** (nElo +28.29 ± 11.80), Ptnml [12, 343, 818, 472, 19], **H1** (LLR 4.18, bounds −1.56, 2.77) after stages 0-1, 3,328 games, no time losses (runs 43521188039, 43531310147; 8:20 PM EST 2026-11-13); sprt-log. **Port** (branch adopt/root-lmr): 350ea3a's change (relative to ab70fa5) with b56adb9's switch-on onto phase-4 bbc19c5: the reduction in `search_root`, the switch `UseRootLmr` (now on), test_pruning's root-reductions case (the default check now on), both tier-2 all-switches cases (test_pruning, test_pruning_review), and the exact searches without it (test_search's `exact_switches`, as tested; test_pruning_review's `no_pruning`, explicit beside B16's line, though its LMR off already disables it). **Where it sits:** at the root only, as tested: a root move after the first, quiet (no capture, no promotion), with its index + 1 at least `LmrMinMove` and the iteration at least `LmrMinDepth` deep, is searched first on the zero window at depth − 1 − (`reduction_for`(depth, index + 1) − the check relief), clamped to [1, depth − 1]; if it beats alpha, again at depth − 1, then on the full window as before. It reads the whole-ply LMR table only, as tested: no context correction, no cut-node or B9 not-improving plies, no R20 term (R20's 64ths sum and B9's trend act at negamax's LMR sites, unchanged), and the stats builds' X2 LMR probe counts negamax's sites only, so it is unchanged and consistent. The features adopted after the tested base act below the root as before; E1's stop rule reads the prior best, which starts each iteration at the front of the root list (index 0, never reduced; each fail high by another move in the iteration moves it one place down, so it can be reduced only after three). Root reductions with E1, the history skip, the drift table, D8, D13, the exemption, D17, B9, R20, D11 and B16 are untested interactions; the stacking check that follows covers them. **Bench equivalence** (clang-release, Windows, r8brft1): with root reductions off, 6,064,962 / ad41c57a026bb021, phase-4 bbc19c5's; with them on and E1, the history skip, the minor drift table, D8, D13, the exemption, D17, B9's LMP and LMR uses, R20, D11 and B16 off (the tested base had none of them), 8,027,262 / 64ebc879047d0f81, byte for byte b56adb9's tests/bench-r8brft1.ref, so the port equals the tested code. **Bench changes (intended):** 5,386,021 / 5ecd49d976e215e1 with r8brft1 (11.2% fewer nodes than 6,064,962); every other reference re-pinned from its own build. Tests: clang-release (Windows): every non-slow test passes (34 of 34 with -j1, eval skipped as usual, uci_timing and bench_parity included), and the pruning suite again after the pins (39 cases); clang-debug: ordering (17 cases), pruning (39, the root-reductions case new) and search (27) pass; clang-stats: search_stats passes (11 cases). **Two cases flipped with root reductions on, both debug-only tree checks, and are pinned:** test_pruning's no-move reduction case (its three depth-9 debug trees came out the same with IIR on and off) and R20's centred-history case (its three depth-7 debug trees the same with the term on and off); both are fault checks that a technique changes the search, not strength checks, and the release build's deeper trees (depths 12 and 10) still differ with root reductions on. Root reductions are pinned off on both sides of each comparison, with a comment in the B9 pin's style; with the pins the debug pruning suite passes (39 cases, 0 failures). No other case flipped (the existing B9 and R20 pins pass unchanged; test_search's stop-rule case, for which b56adb9 added a second pass with root reductions off, passes here without it, so that change is not ported). Speed: bench/ab_search.py (clang-release, Windows, 12 interleaved rounds, not pinned; identity checked on all 24 runs), A = bbc19c5, B = the port: median nps -1.5%, best -2.0%, under the run's 3.0% noise threshold, so no significant difference (the two search different trees: 6,064,962 against 5,386,021 bench nodes; the code change itself is a few comparisons per root move). Names screened 2026-11-12 (the coordinator's separate agent; no match; root reductions are shared practice in all four, credited; ORIGINALITY.md); no new name since, no constant. Records: SPRT log (STC and LTC), the constants table (the root reductions row, adopted), ideas.md (idea 124), tools/gauntlet/transfer.json (the LTC result as the basis, the STC beside it), ORIGINALITY.md (the screen's row, with the adoption); no final-retune dimension. The switch stays until the Phase 4 re-validation. |
| 2026-11-14 | **Retrain 8c's early test decided; the TPU path's first run changed (owner, about 6:20 AM EST).** Early test (8b's snapshot plus g4b and the ld arms, warm start r8btd90; fixed-node screens, 800,000 nodes per move, 1,600 games each): idea 80 (TD-labelled unsaved records) vs the control, seed 1 −1.74 ± 9.19, seed 2 +5.65 ± 9.10, pooled about +2: neither killed nor adopted by its declared rule, so retrain 8c's A1 i80 arm decides; 2.5x training vs the standard length −0.43 ± 9.44 at 2.4x the GPU time: no gain at about 1.8B samples. **Longer-training runs are deferred until the data volume grows substantially.** The TPU path (Kaggle's TPU quota; own JAX trainer reproducing the bullet recipe, clean-room) keeps its steps (research, trainer, report after each step), but its **first run is a parity reproduction of 8c's standard control arm** (same data, recipe and warm start, a third seed), compared with the GPU-trained r8cc1 and r8cc2 by loss curves and a fixed-node screen: it validates the path and adds a seed. After parity, TPU time goes to additional arms and seeds in parallel with GPU sessions. Plan only: it starts after the 8c promotion decision. |
| 2026-11-14 | **Bake-off round 3: the king-input designs measured and decided (owner, about 8:15 AM EST).** Design report docs/research/bakeoff-r3/king-inputs-design.md (branch proto/r3-king-a; prototypes proto/r3-king-a/b/c, each loading r8brft1 with zero new rows, bench identical to phase-4: 5,386,021 / 5ecd49d976e215e1; nps by bench/ab_search.py against phase-4 1a5aba4, x86-64-v3). (a) king buckets with a refresh cache: 4 buckets (M4: the mirrored own-king cell on e1; f1-h1; rank 2; ranks 3-8) 0.944 (0.939-0.949), 8 buckets 0.924, without the cache 0.885 / 0.839. (b) king-relative offset inputs (idea 157): 0.782 (own king, incremental) to 0.534. (c) the exposure plane on S512+PP: 0.864 recomputed per evaluation, 0.824 incremental (finding the exposed set dominates). **Decisions:** (1) train option (a) only for now; (2) M4 with the refresh cache; (3) option (b) parked; (4) option (c): a cheaper exposure finder prototyped first, no training until its nps ratio is re-measured and reported; (5) (a) is screened against a same-recipe control trained alongside it, plus the speed-adjusted fixed-node screen against the current default, then its STC SPRT, plus the UHO/SF19 diagnostic; (6) warm start from 8c's winner once promoted (r8brft1 if 8c is not promoted); (7) the trainer's input-index collision (the pawn-link block starting where a factoriser or exposure block starts) fixed now, as a standalone fix with a failing-first test. (a)'s names and constants pass the originality check before anything reaches phase-4. |
| 2026-11-14 | **Bake-off round 3: the follow-up prototypes measured and decided (owner, about 10:30-10:40 AM EST).** Measured (zero new weights, bench identical, bench/ab_search.py against phase-4): the exact exposure plane cannot reach 0.90 (fastest variant 0.877-0.882; finding the exposed set is only about 6%, applying its rows the rest); x_lower (the exposure rule's lower-class-attacker half only, a changed feature) 0.932 / 0.934; option (b)'s king windows (5x5) 0.784; (b2) a king-zone vector of 32 counts into the output layer 0.914 / 0.919; option (d)'s context vector 0.845 in full, its cut d_lite (fifty-move counter, castling rights, opposite-coloured bishops, pieces attacked by pawns, bishop pair, progress potential, symmetry, shelter; 34 values) 0.923. Reports on branches proto/r3-king-c, proto/r3-king-b1 and proto/r3-king-d. Option (a) (architecture 9, H512+PP) merged into phase-4 at a33a1e6 after its name screen: 0.941 (0.936-0.947). **Decisions:** (1) x_lower is a second arm in (a)'s training session: (a), x_lower and a same-recipe control, same data, recipe and warm start (8c's winner), with the session's quota estimate reported first; (2) d_lite and (b2) are held in reserve, trained separately later if (a) or x_lower shows promise; only candidates that pass alone are stacked, after their combined nps is measured; (3) **no data format change** for the halfmove clock and castling rights (the viriformat start board already stores both and every reader replays the moves): the trainer's decoder carries them into the packed board's spare bytes, with a test that they match a replay of the game, which works for every existing part; done only when d_lite or another feature needing them is scheduled for training. |
| 2026-11-14 | **Fable's network ideas recorded and sequenced (owner, about 11:30 AM EST).** Proposal docs/research/network-novelty-2026-11-14.md (read-only; estimates unmeasured; novelty UNVERIFIED), recorded as ideas.md 175-184. **Plan, after 8c's promotion decision and around round 3's training:** (1) idea 180 (the proposal's 6) step 2 first, no training: r8brft1's output heads rescaled by queen state (and phase) from Fork's own calibration fit; a fixed-node screen against r8brft1 and the UHO/SF19 diagnostic; reported before any label work. (2) Idea 175 (1): the residual study (ranking only) and a zero-delta speed prototype, killed below 0.95; idea 176's (2) column-utilisation count folded into the same data pass; idea 175 and option (a) are alternatives on one body. (3) Idea 182 (8): build, bench parity and A/B on this PC and on the GitHub runners (cache-size caution for TCEC), adopted under the speed rules. (4) Idea 178 (4): its share measurement and speed prototype after x_lower's result. Ideas 177, 179 and 181 (3, 5, 7) parked; 183 and 184 (9, 10) kept as later refinements. |
| 2026-11-14 | **Idea 23's revamp recorded; placed as a final pre-TCEC polish step (owner, about 12:15 PM EST).** Plan docs/research/idea23-revamp-2026-11-14.md (read-only; estimates unmeasured; prior art UNVERIFIED). **Placement:** after Lazy SMP, the removal round, the final retune and the TCEC fixes; its traces are recorded from the final engine under TCEC-like conditions (many threads, long time control; ideally during the rented-hardware dry run). **No engineering until then** (the owner chose this over starting the simulator after 8c's promotion). **Decisions:** (1) target order: time management first, row-choice states second, the calibration layer only if idea 180 gains; (2) coefficient fitting on the simulator approved for the time-management target only (fitted values are candidates; games decide); (3) the 12-arm batch of one-stage screens with three predicted-loser arms approved; E2's clamp fix goes into the simulator once its LTC decides; the stage-0 simulator validation is reported before tokens or GitHub time are spent. |
| 2026-11-14 | **Retrain decisions sped up (owner, about 12:20 PM EST).** (1) Network screens and promotion SPRTs take priority over search items and may use both GitHub lanes in parallel (applied at once to retrain 8c's final screens and its STC SPRT). (2) Future retrains plan only the control plus one fine-tune variant (currently the control against the control plus rft-ep-lo), dropping idea 80 and the fine-tune comparisons that were within noise in 8b and 8c. |
| 2026-11-14 | **The plan trimmed (owner, about 12:30 PM EST).** (1) Retrain 8c's A2: its positional-slice arm and arm Q's two arms (natural share, oversampled) are replaced by ONE combined queens-on arm (the positional slice plus arm Q's data, slice-pos-x-r8, oversampled within the 5% cap), two seeds; the per-class lambda arm stays. Reason: one arm testing the queens-on data idea once, with seed replication, instead of three single-seed arms splitting it. (2) Search queue: the fixed-node screens of ideas 79 (nested width) and 82 (multi-fidelity heads) and C16 (cheap refutation) are dropped, and the retries of R41, R40 and C4 are dropped (their first tries stay); B6 and its non-regression fallback stay. Reason: GitHub time goes first to network decisions (network screens and promotion SPRTs now take priority, same day); the dropped items are low-priority probes, and a retry only re-reads a first try that ended inside noise. Lane items marked skipped in state/ (reversible). |

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
- The accumulator is updated incrementally, in register tiles: each tile of
  the parent's sums is loaded once, every changed row applied, and stored
  once (speed sprint 3, 2026-11-12; decisions log).
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
- For a bench-identical change, a saving of at least 1% cycles per bench node
  (`perf stat -e cycles:u` over interleaved bench runs, beyond twice the
  round-to-round spread) also counts as a measured gain (decisions log,
  2026-11-07, decision 8; first applied in speed sprint 3, 2026-11-12).
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
