<!--
Archived 2026-10-24 (phase-end checklist) from the untracked REVIEW-phase1.md.
Every finding was resolved on 2026-10-24: docs/DESIGN.md decisions log and
docs/ORIGINALITY.md. The H2, H3 and M3 evidence paragraphs describe the
pre-rewrite code. User-name paths were replaced and commit hashes updated
to the rewritten history; line numbers refer to the code as it was then.
-->

# Phase 1 full review (2026-10-23, main @ 0f00021)

Two independent read-only reviews, reconciled: a **TCEC judge** (originality,
rules, Category 4, anything that could disqualify Fork, crash it or forfeit
games) and a **top engine developer** (correctness, performance, Phase 3
readiness). Nothing was built or run during the review (overnight queue
active); proofs are code readings, side-by-side comparisons and primary
sources, and every runnable proof is listed under "Deferred tests". Untracked
file, not committed.

"Checked" = I re-read the cited code or source myself while reconciling.

## Findings by severity

### Critical

**C1. Fork does not build on TCEC's toolchain.** (judge; checked)
- **Where:** `CMakeLists.txt:1` (`cmake_minimum_required(VERSION 3.25)`),
  `CMakePresets.json:2-3` (preset schema v6, needs 3.25), `src/main.cpp:6`
  (`#include <format>`) and `:134` (`std::format`).
- **Evidence:** TCEC's CPU server runs Ubuntu 22.04 with gcc 11.4, g++-12
  12.3, clang 16 and 19 (KB `competition.md`, "What this means for Fork"
  under "Swiss categories in full"; the judge re-read the wiki's "Further
  information" page on 2026-10-23). Ubuntu 22.04's cmake is 3.22.1
  (Launchpad); libstdc++ gained `<format>` in GCC 13.1 (gcc.gnu.org status
  table). Every build so far used clang 21-23 / gcc 15-16. The judge did not
  run a 22.04 build (deferred test b).
- **Why it matters:** Category 4 means TCEC builds Fork from the repository
  (`competition.md` "Builds and submission"). If it does not build, Fork
  does not play.
- **Fix:** replace the one `std::format` with `snprintf("%016llx")`; lower
  the CMake floor to 3.22 (keep presets as a developer convenience) or ship
  an `update.sh` that brings its own CMake; add an Ubuntu 22.04 build with
  all four compilers to the sign-off checks. **Effort:** S (code) + M
  (22.04 environment).

### High

**H1. No LICENSE and no README.** (judge; checked: neither file exists)
- **Why it matters:** without a licence the code is all rights reserved,
  not open source; Category 4 needs public, buildable source, the
  questionnaire asks for licences, and KB `originality.md` §4 item 1 says to
  state it in `LICENSE`.
- **Fix:** owner picks an OSI licence; README with clean-clone build
  commands and the AI-assistance disclosure (`originality.md` §4 item 2).
  Note the interaction with H2/H3: fix those first, or choose GPL-3.0.
  **Effort:** S.

**H2. The magic search mirrors Stockfish's `init_magics`.** (judge; checked
side by side)
- **Where:** `src/core/bitboard.cpp:42-51` (xorshift64*, sparse = and of
  three), `:89-91` (edge-mask expression), `:93-98` (carry-rippler filling
  occupancy and reference together), `:106-127` (`epoch`-stamped collision
  check, candidate rejected when `popcount((mask*magic)>>56) < 6`) against
  Stockfish `src/attacks.cpp` (effdc3f) L116-153.
- **Evidence:** the collision loop has the same structure and the same
  variable name `epoch` (`used_epoch[idx] != epoch` then store, else
  compare and reject). Each piece is textbook (CPW "Looking for Magics");
  the combination in the same order is recognisably Stockfish's.
- **Why it matters:** the first file a reviewer comparing against Stockfish
  opens; ORIGINALITY.md does not list Stockfish for it; DESIGN.md §8 and
  `.claude/rules/cpp-style.md` forbid close paraphrase.
- **Fix:** drop the epoch scheme (clear the per-square slice per candidate,
  about 1.5 candidates per square with the tuned seeds), write the mask as a
  ray walk, cite CPW and Vigna for the generator. Tables and bench stay
  identical. **Effort:** S.

**H3. `update_check_info` and the State layout paraphrase Stockfish.**
(judge; checked side by side)
- **Where:** `src/core/position.cpp:111-137` against Stockfish
  `update_slider_blockers` (position.cpp L628-652) and `set_check_info`
  (L473-481); `src/core/position.hpp:32-47` against `StateInfo`.
- **Evidence:** snipers from empty-board attacks, `between(ksq, sniper) &
  occ`, `if (b && !has_multiple(b))`, blockers and pinners updated the same
  way (Fork's one deliberate difference: no sniper exclusion from the
  occupancy); check squares assigned in the same order ending with
  `[King] = 0`; State fields pawn/material/non-pawn keys per colour,
  checkers, blockers, pinners, check squares, captured. `material_key` and
  `non_pawn_key` have no consumer outside tests.
- **Why it matters:** ORIGINALITY.md line 33 says the source was not opened
  and the code was written from DESIGN.md; the result still reads as a
  paraphrase.
- **Fix:** x-ray pin computation (CPW "Pinned Pieces"); compute checking
  squares lazily in `gives_check` (this is also ideas.md idea 9's lazy
  variant: `update_check_info` is 19% of bench time); remove the unused keys
  until a Fork-designed consumer exists; rewrite the ORIGINALITY.md entry.
  Bench unchanged. **Effort:** M.

### Medium

**M1. A copied `Position` allocates on its first moves, and a reallocation
invalidates `State&` references.** (developer; checked)
- **Where:** `src/core/position.cpp:303` and `:398` (`reserve(capacity*2)`
  when full), `:69` (`reserve(StateReserve)` only in `clear()`); no
  user-defined copy constructor; `position.hpp:12-13` promises no allocation
  within the reserve and per-thread copies.
- **Evidence:** `Position copy = root;` copies the vector with capacity equal
  to its size, so the first `make()` calls reserve 2, 4, 8 ...; `no_alloc`
  never copies a Position. Test: `build/overnight/review/review-tests/alloc_copy_test.cpp`
  (deferred).
- **Why it matters:** Lazy SMP copies the root per thread per `go` (up to
  512 threads at TCEC); any search code holding `const State&` across a
  growing `make()` gets a dangling reference (rare crash).
- **Fix:** copy constructor/assignment that reserve `max(StateReserve,
  size + MaxPly)`; extend `no_alloc` with the copy case. **Effort:** S.

**M2. `repetition_count()` looks back across null moves.** (both; checked)
- **Where:** `src/core/position.cpp:560-570` (window = `min(halfmove,
  n-1)`), `:402` (`make_null` increments `halfmove`).
- **Evidence:** startpos, null, g8f6 b1c3 f6g8 c3b1 gives count 2 (a
  "repetition" of a position that exists only because White passed). Test
  R3 in `build/overnight/review/review-tests/test_review.cpp` (deferred).
- **Why it matters:** false repetition draws inside null-move subtrees in
  Phase 3. **Fix:** `plies_from_null` in State, window bounded by it; a
  search-facing `is_draw(ply)`. **Effort:** S.

**M3. `between`/`line` table formulas are Stockfish's expressions.** (judge;
checked) `src/core/bitboard.cpp:205-209` vs Stockfish `attacks.cpp`
L182-184, identical apart from names. **Fix:** fill both by ray walk.
Bench unchanged. **Effort:** S.

**M4. Stockfish API names not logged or decided.** (judge) `piece_on`,
`side_to_move`, `ep_square`, `pawn_key`, `material_key`, `non_pawn_key`,
`relative_rank`, `make_piece` (generic: `file_of`, `rank_of`,
`make_square`). DESIGN.md §8 requires flagging non-generic matches to the
owner. **Fix:** owner decision per name, recorded in ORIGINALITY.md.
**Effort:** S-M.

**M5. ORIGINALITY.md is incomplete.** (judge) Missing: Vigna's splitmix64
(`zobrist.cpp:14-20`) and xorshift64* (`bitboard.cpp:42-49`); CPW "Looking
for Magics"; the Linux toolchain and analysis tools (clang 21, gcc 15,
clang-tidy, cppcheck, valgrind, TSan); fastchess, cutechess-cli, ordo,
Syzygy 3-4-5 from tablebase.lichess.ovh, the Python version; sources of the
non-CPW FENs in `tests/suite.hpp` and `tools/difftest/difftest.py`
(CLAUDE.md non-negotiable 1). **Effort:** S.

**M6. ideas.md idea 7 plans TCEC book positions as NNUE data-generation
starts**, which KB `originality.md` §3 lists as off-limits (books built from
other engines' evaluations). Nothing has been used yet. **Fix:** restrict
idea 7 to testing, or record an owner decision before Phase 4. **Effort:** S.

**M7. The default build downloads test data from archive.org at configure
time with no timeout.** (judge; checked: `CMakeLists.txt:187`
`file(DOWNLOAD ... STATUS st)`, no `TIMEOUT`; `FORK_BUILD_TESTS` defaults
ON) A stalled download hangs an admin's plain `cmake -B build`. **Fix:**
`TIMEOUT`/`INACTIVITY_TIMEOUT`, and tests off on the TCEC build path
(`update.sh`). **Effort:** S.

**M8 (Phase 2 spec). Hash allocation order and the TCEC build path.**
(judge) Both are now in DESIGN.md §5.1 (commit f7f74e0): allocation after
all options, and the TCEC-toolchain/`update.sh`/explicit `-march` items.

### Low

**L1. Signed overflow from FEN move counters at INT_MAX.** (both; checked)
`position.cpp:257-262` accepts any non-negative int; `:311` `++s.halfmove`,
`:364` `++fullmove_`, also in `make_null`. `set_fen("4k3/8/8/8/8/8/8/4K2R w
K - 2147483647 1")` then a move is UB (UBSan abort in clang-debug; in
release the FEN round trip breaks). Not a realistic TCEC input, but UB on
the GUI-input path. **Fix:** reject halfmove > 10000 and fullmove > 100000.
**Effort:** S.

**L2. Doc drift.** (developer) DESIGN.md §4.5 still describes an `Undo`
vector; `position.hpp:96` points to draw rules in §4.5 that are not there;
§7 says layout results are in the decisions log (they are in ideas.md).

**L3. `config/tcec.json` on main is stale** (old adjudication values, TB
adjudication, `large_pages: false`). (judge) **Fix:** merge the kb copy.

**L4. Personal identifiers in history.** (judge) The commit author email
(personal Gmail) is in every commit; user-name paths in CLAUDE.md,
`config/local-test.json`, `scripts/linux-setup.sh`,
`.claude/agents/kb-researcher.md`. No secrets, tokens or large blobs found
in the whole history. **Fix (owner decision, before the repo is public):**
GitHub noreply address (history rewrite is cheap now), generic paths,
`.gitignore` for session notes.

## Phase 3 readiness notes (developer; design, not defects)

1. Scored move list (score array beside the moves). KB `techniques.md` "Move
   ordering".
2. SEE and `see_ge` missing; `attackers_to(sq, occ)` exists. KB
   `techniques.md` "Quiescence search + SEE".
3. `GenMode::Captures` includes quiet underpromotions; qsearch usually
   wants captures plus queen promotions. Changing generation order changes
   bench.
4. Staged generation fits Captures then Quiets; missing `moved_piece`,
   `captured_piece` (ep aware), a non-pawn-material test for null-move
   conditions (`non_pawn_key` includes the king).
5. A null-move `predicted_key` variant for TT prefetch.
6. `fifty_move_reached()` ignores mate: search must check mate first.
7. Syzygy: the needed state is exposed; square numbering vs Fathom
   UNVERIFIED until its header is read; Fathom 7-man support UNVERIFIED
   (ideas.md idea 12).
8. `build_bitboard_tables()` is public and rewrites shared tables; zobrist
   arrays are mutable globals. Make the rebuild test-only before threads.
9. Phase 4: NNUE incremental updates need moved/captured/promoted pieces
   (and the castling rook) per ply; plan the State layout now.
10. Hot-path candidates for A/B only (no gain claimed): State about 144
    bytes copied per make, redundant `checking_squares[King]`/`[Queen]`,
    unused `pinners`, PEXT `SliderEntry` carries dead fields, no
    `alignas(64)` on `slider_table`/`State`; re-profile in search first.

## Suspicions (unproven)

1. **MoveList capacity.** `set_fen` accepts unreachable positions (up to 15
   queens); the judge's search found 240 legal moves (`Q4Qbk/3Q2pp/1Q4Q1/
   4Q3/2Q4Q/Q6Q/3Q1Q2/KQ1Q3Q w - - 0 1`), under the 256 capacity but with no
   proof of a bound; only an `assert` guards overflow (`types.hpp:108`).
   Cheap fix either way: reject impossible promoted material in `set_fen`.
2. Presets without `env.sh` (`$env{FORK_CLANG_CXX}` empty): fails or falls
   back? 
3. Clang LTO on Ubuntu 22.04 without LLVMgold/lld; `-Werror` with gcc 11.4
   and g++-12 at -O3 + LTO.
4. `-march=native` built on one TCEC server and run on the other (Zen 5 vs
   Zen 4): possible SIGILL. Avoided by the explicit `-march` in the spec.
5. Dangling `State&` once search holds references (M1).
6. `has_insufficient_material` for lone knight vs queens, same-colour
   bishops vs rooks: mirrors python-chess, so difftest cannot catch it;
   check with Syzygy WDL before search scores it as a draw.
7. `push_back` bookkeeping in make/unmake vs a fixed array: A/B.
8. Originality comparison covered only Stockfish (not Ethereal, Berserk,
   Obsidian, Reckless, Caissa, Viridithas).

## Deferred tests (after the overnight queue)

1. `build/overnight/review/review-tests/test_review.cpp` (R1, R2 counter overflow; R3 repetition
   across null): add to `fork_tests`, run in clang-debug (UBSan abort
   expected on R1) and clang-release (R1-R3 fail).
2. `build/overnight/review/review-tests/alloc_copy_test.cpp`: expected "make() on a copied
   Position allocated N times".
3. Counter-overflow reproduction from the CLI: `build/clang-debug/fork
   perft 2 "4k3/8/8/8/8/8/8/4K2R w K - 2147483647 1"`.
4. TCEC-toolchain build in an Ubuntu 22.04 environment (cmake 3.22; gcc
   11.4, g++-12, clang 16, clang 19): expected to fail on CMake 3.25, then
   on `<format>`.
5. `env -u FORK_CLANG_CXX -u FORK_GCC_CXX cmake --preset clang-release`.
6. MoveList bound: longer search with the judge's scripts
   (`build/overnight/review/movelist-search/`), then `fork perft 1` on the best FEN in
   a debug build.
7. After any H2/H3/M3 rewrite: `scripts/check.sh full`, `ctest -L slow`,
   bench unchanged.
