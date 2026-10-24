<!--
Archived 2026-10-24 (phase-end checklist): the code-free specification the
"dirty" research agent wrote for the clean-room rewrites of review findings
H2, H3, M3 and M4 (docs/ORIGINALITY.md, "Resemblances found in review").
Kept verbatim as a record of the process. It contains no code from Fork or
any other engine. Fork commit hashes in it predate the history rewrites of
2026-10-24: dfa4feb is now 501882d and b990883 is now 203558c.
effdc3fd is a Stockfish commit; the 7-digit numbers in DOIs are not commits.
-->

# Clean-room rewrite spec: H2, H3, M3, M4

Written 2026-10-24 by the "dirty" session (read both codebases). For the
implementing session, which must never see Stockfish's code or a paraphrase
of it. This file has no code from either engine, no pseudo-code, and no
step-by-step account of how Stockfish does anything. Where it says what Fork
does today, it does so only to name what must change.

## 0. Ground rules for the implementer

- **Baseline.** Fork `main` at dfa4feb (src/ last changed at b990883).
  Stockfish was compared at **effdc3fd3f6de6e75fe1374a51a7a7eed66f880b**
  (2026-10-17, official-stockfish/Stockfish master as cloned on 2026-10-24).
  That is the same commit the Phase 1 review used (effdc3f): master has not
  moved since, so the review's line references still apply.
- **Do not read**, in Fork:
  - the bodies of the flagged routines: `src/core/bitboard.cpp` from the
    xorshift `Rng` struct to the end of `build_bitboard_tables()` (the
    seeds, the slider-square builder, `search_magic`, `init_slider` and the
    between/line loop). `ray_walk`, the leaper tables and the seed arrays
    are not flagged, but they sit in the same region, so stay out of it;
  - the body of `Position::update_check_info` (position.cpp lines 111-137);
  - the "Evidence" paragraphs of H2, H3 and M3 in `REVIEW-phase1.md`. They
    paraphrase Stockfish at the level of individual expressions.
  You may read headers, tests, call sites, DESIGN.md, ORIGINALITY.md, the
  rest of position.cpp and movegen.cpp, and the sources in each section
  below.
- **Name checks (DESIGN.md §8)** need a Stockfish grep. Use only
  file-list or count output (`grep -rlw`, `grep -rcw`), never line output,
  so that no Stockfish code reaches your screen. Section 4.4 lists names
  that have already been checked and have zero hits.
- **Results must be identical.** The attack sets, masks, between/line sets,
  checkers, blockers and pinners all stay the same, and the `fork bench`
  node count and signature stay unchanged. `tests/bench.ref` is
  `nodes 26401709`, `signature f298a22041a6270a`; `build/clang-release/fork
  bench` reproduced both on 2026-10-24. The magic numbers themselves may
  change: callers and bench never see them.

## 1. H2: magic search and slider table initialisation (src/core/bitboard.cpp)

### 1.1 Functional contract

**Public surface** (bitboard.hpp). Keep it, or change it together with
every caller.
- `init_bitboards()`: builds every table exactly once, thread-safe. It is
  called by `forkeng::init()` (position.cpp) and by tests.
  `build_bitboard_tables()` rebuilds unconditionally; only
  `bench/micro.cpp` ("init_tables" timing) uses it.
- `rook_attacks(s, occ)`, `bishop_attacks(s, occ)`, `queen_attacks`, and
  `attacks(type, s, occ)` must return exactly the ray-walk result for
  **every** 64-bit occupancy, not just occupancies inside the mask. Squares
  outside the relevant mask, and the slider's own square, must not affect
  the result.
- `rook_attacks_slow` / `bishop_attacks_slow`: the reference ray walk.
  Attacks run in each of the four directions up to and including the first
  occupied square, or to the board edge. Tests use these as the oracle, so
  they must stay independent of the fast path.
- `tables::rook[64]` and `tables::bishop[64]`: `tests/test_magics.cpp`
  reads only the per-square `.mask` field. If you rename the struct or its
  members, update that test.
- `magic_search_attempts(rook, s, seed, limit)` is used only by
  `tools/magic_seeds.cpp` (target `fork_magic_seeds`), the offline tool
  that picks the per-square seeds. You may redesign or rename the search
  API, as long as the tool keeps working, or is replaced, and the seed
  tables are regenerated with it.

**Relevant-occupancy mask** (must stay bit-identical). For each square and
each slider kind, the mask is the set of squares the slider attacks on an
empty board, minus the last square of each ray (the square on the board
edge). On 2026-10-24 I checked that this definition reproduces Fork's 128
masks exactly. As a result, the per-square table sizes, two to the power of
the mask's bit count, sum to **102400** entries for rooks and **5248** for
bishops.

**Index width and table footprint.** Each square uses exactly as many
index bits as its mask has. In the magic build that means a right shift by
64 minus that bit count. In the PEXT build the index is the PEXT of the
occupancy by the mask. Each square owns a contiguous slice of one shared
table, so the total stays 107648 entries (about 841 KiB). DESIGN.md §4.3
describes this layout, and it should not grow.

**Build variants.** `FORK_USE_PEXT` (BMI2 and not `FORK_NO_PEXT`): no
search runs, and every subset is written at its PEXT index. Otherwise a
deterministic magic search runs at startup from fixed seeds. Any nonzero
seed must eventually succeed, so a stale seed table may only cost startup
time. The search must be deterministic, with no unseeded randomness
(`.claude/rules/cpp-style.md`). Startup currently takes milliseconds;
measure it with `fork_micro` "init_tables" before and after, using
`bench/ab.py` (the shared machine is noisy).

**Golden fingerprints** (taken 2026-10-24 from the current code; magic and
PEXT builds gave identical hashes). Write your own dumper with the byte
layout below and compare before you delete anything. Every value is a
uint64 written as 8 little-endian bytes.

| File | Content and order | Bytes | SHA-256 |
|---|---|---|---|
| between.bin | `between(a, b)` for a = 0..63 (outer), b = 0..63 (inner) | 32768 | b3072c4a83038e89aabb3f1c7a25d29239f098ed60734c79e7ddd0205cf5e690 |
| line.bin | `line(a, b)`, same order | 32768 | 59a183d3cab802369b846baffcf8c4574cfde79fac3e79f4a7c1fd7015b21ecf |
| masks.bin | rook mask for s = 0..63, then bishop mask for s = 0..63 | 1024 | c2c42e2a05ffab2e9f8fbe3e984ce8dd0b1a4640f253393647c4bc5d85e90111 |
| rook_attacks.bin | for s = 0..63: `rook_attacks(s, occ)` for every subset occ of the rook mask, in ascending numeric order of occ | 819200 | 8d14bf4b71c683ad5ec04290b41b46ec32b6265a11b9c49502f2db928b4ec70d |
| bishop_attacks.bin | the same for bishops | 41984 | 8d47a340cbb61d8e6c3c4b159d4667549bfe5c4de134a5c42a8f6abe33485ed6 |

**Tests that pin H2.** `magics`: every subset of every mask, plus random
noise outside the mask, against the slow ray walk, for both kinds. Then
`perft_suite`, `perft_mirror`, `perft_epd` (and `perft_epd_deep` /
`perft_epd_full`, label `slow`), `consistency`, and `bench_parity`. Run
these in both the PEXT presets (`*-release`, `*-v3`, `*-avx512` on BMI2
hosts) and the magic presets (`*-nopext`). Only the nopext presets exercise
the search.

### 1.2 Resemblances to avoid (what in Fork's current code must change)

1. **A stamp table driven by an attempt counter.** A per-index array of
   stamps is compared with a counter that goes up once per candidate, so the
   scratch table never has to be cleared. The local names `epoch` and
   `used_epoch` add to the match. Do not use any per-candidate
   generation-stamp scheme. The review's suggestion is to clear the
   square's own slice, or a scratch buffer, before each candidate. With
   tuned seeds there are about 1.5 candidates per square, so clearing is
   cheap.
2. **Storing while checking, in one pass.** Each subset's attack set is
   written into the final table as the candidate is checked, and a
   collision is detected by comparing against what that same pass already
   wrote. Structure your own check differently. For example, validate into
   a scratch area and fill the real table in a separate pass, or check for
   collisions in a way of your own design.
3. **The candidate generator, as a package.** Fork has a small
   generator object whose "next" step is Vigna's xorshift64* with shift
   triple (12, 25, 27) and multiplier M32, plus a "sparse" method that ANDs
   three draws. Each part is published: Vigna's paper for the generator,
   and CPW "Looking for Magics" for the three-way AND. Together, in this
   shape and with these method names, they read as a copy. Choose and cite
   your own generator. One option is Fork's own splitmix64 stream, the
   generator `src/core/zobrist.cpp` already uses (Vigna, public domain). If
   you keep xorshift64*, cite Vigna and structure the code your own way.
4. **The pre-filter on the candidate.** Fork rejects a candidate when
   fewer than 6 bits are set in the top byte of the mask times the
   candidate. CPW shows this heuristic too, but within this combination it
   is part of the recognisable pattern. Drop it, or use a filter of your
   own design. It only affects speed, and the seeds get retuned anyway.
5. **The mask as one edge-exclusion expression.** Fork builds the mask in
   one expression: the edge ranks and files, minus the slider's own rank and
   file, removed from the empty-board attacks. Build the mask by walking
   rays and stopping one square before the edge, which is the definition in
   1.1. The review asks for exactly this.
6. **Subset enumeration that fills two parallel lists in one do-while.**
   Fork enumerates the subsets with the carry-rippler step and pushes each
   occupancy and its reference attack set into two parallel lists in the
   same loop. The carry-rippler itself is generic (CPW "Traversing Subsets
   of a Set"), but this loop shape is part of the match. Use a different
   structure, for example mapping an index to a subset by depositing its
   bits into the mask, or computing reference attacks on demand.
7. **Per-square record names.** `SliderEntry` has members `mask`,
   `magic`, `attacks` and `shift`, and a method named `index`. A
   four-field record is CPW-generic (CPW "Magic Bitboards", Fancy section),
   but the member name `attacks` and the method name `index` match
   Stockfish. Rename both; zero-hit candidates are in 4.4.
8. **The overall order:** mask, then the subset and reference lists, then
   the candidate loop with stamp-checked stores, then a per-square table
   pointer advanced as a running offset. Each step is textbook, but this
   order, combined with points 1 to 6, is what the review called
   recognisable. Once points 1 to 6 are fixed it will differ anyway; do not
   recreate it.

The per-square seed tables and the "retry until found" outer loop are
Fork's own, and the review did not flag them. Regenerate the seed values
with the tool after you change the generator or the filter.

### 1.3 Independent sources (all opened 2026-10-24)

- CPW "Looking for Magics": https://www.chessprogramming.org/Looking_for_Magics
  covers trial and error with sparse random candidates, and includes
  Romstad's sample program: relevant masks, a 4096-entry used table cleared
  per candidate, and the top-byte heuristic. Read it for ideas only and do
  not transcribe the code; the page states no licence for that code beyond
  the wiki's CC BY-SA 3.0.
- CPW "Magic Bitboards": https://www.chessprogramming.org/Magic_Bitboards
  describes Fancy versus Plain, the per-square record, the individual shift,
  and constructive collisions.
- CPW "Traversing Subsets of a Set": https://www.chessprogramming.org/Traversing_Subsets_of_a_Set
  covers the carry-rippler (credited to Marcel van Kervinck and Steffan
  Westcott).
- CPW "On an empty Board": https://www.chessprogramming.org/On_an_empty_Board
  covers ray and line masks, both by lookup and by calculation.
- CPW "Square Mapping Considerations": https://www.chessprogramming.org/Square_Mapping_Considerations
  covers little-endian rank-file numbering and file and rank indices.
- Vigna, "An experimental exploration of Marsaglia's xorshift generators,
  scrambled", arXiv:1402.6246 (v5, 2016-10-13; the extended version of the
  ACM TOMS paper): https://arxiv.org/abs/1402.6246. Table IV gives M32 =
  2685821657736338717, which is 0x2545F4914F6CDD1D (converted by me), and
  section 9 recommends xorshift64* A1(12, 25, 27) with M32.
- Vigna, splitmix64.c (public-domain dedication, 2015):
  https://prng.di.unimi.it/splitmix64.c. The overview page is
  https://prng.di.unimi.it/.
- Vigna, "Further scramblings of Marsaglia's xorshift generators",
  arXiv:1404.0390: https://arxiv.org/abs/1404.0390 (abstract page opened;
  optional).

## 2. H3: check and pin information, and the State layout (src/core/position.{hpp,cpp})

### 2.1 Functional contract

`update_check_info(State&)` runs at the end of `make()` (after the side
to move flips, before the ep-legality step), in `make_null()`, and in
`compute_state()` (which `finish_setup()`, `set_fen` and `mirrored()` use).
It must produce, for the position **after** the side-to-move flip:

- **checkers**: every enemy piece that attacks the king of the side to
  move, with the full current occupancy. The test oracle is
  `attackers_to(own king, all pieces)` intersected with the enemy's pieces.
- **blockers[c]**, for each colour c: pieces of **either** colour such
  that removing that one piece would let some enemy (non-c) bishop, rook or
  queen newly attack c's king. Equivalently: there is an enemy slider on a
  common rank, file or diagonal with c's king, able to move along that line
  (rook or queen on ranks and files, bishop or queen on diagonals), and
  exactly one occupied square lies strictly between them. That square is a
  blocker. Enemy sliders standing in front of other enemy sliders count as
  blockers too. The oracle removes each piece in turn and has no special
  cases (`tests/test_consistency.cpp`, `check_blockers`).
- **pinners[c]**: the enemy sliders whose newly exposed attack on c's king
  comes from removing one of **c's own** pieces. Equivalently: the slider at
  the far end of a single-blocker line whose blocker belongs to c. Same
  oracle.
- **checking_squares[t]**, for t = Pawn..King: the squares from which a
  piece of type t belonging to the side to move would attack the enemy king,
  given the current occupancy. For pawns this means pawn-capture geometry
  for the side to move. Queen is the union of the bishop and rook sets.
  King is always empty: the test asserts it is 0, and `gives_check` reads
  it when the king moves. The oracle checks every square for every type.

`compute_state()` must equal the incrementally maintained State
**field for field**: `operator==` is defaulted, and `consistency` checks
`s == fresh` at every node. `same_state()` also compares `state()`. Any
field you add, remove or reorder is covered automatically, but whatever
you keep must be deterministic and fully initialised.

**What Fork's consumers actually read** (grep of src/, tests/, bench/,
tools/ on 2026-10-24):

| State field / accessor | Consumers outside tests | Test consumers |
|---|---|---|
| `key` | `key()`, repetition, bench signature, FEN round-trip checks, `predicted_key` | consistency |
| `pawn_key`, `pawn_key()` | **none** (maintained in `toggle_keys`, recomputed in `compute_state`) | consistency only |
| `material_key`, `material_key()` | **none** (maintained in `make`, recomputed in `compute_state`; it is the only user of `zobrist::material`) | consistency only |
| `non_pawn_key[2]`, `non_pawn_key(c)` | **none** (maintained in `toggle_keys`) | consistency only |
| `checkers`, `checkers()`, `in_check()` | movegen (double-check early exit, the evasion target), `is_legal` (double check, evasion target), `is_pseudo_legal` (castling while in check), `make_null` assert, main.cpp `print_ply`, alloc_test, micro.cpp | consistency |
| `blockers[c]` via `pinned(c)` (blockers of c that are c's own pieces) | movegen (pin restriction along `line(king, piece)`, pinned knights skipped, pinned pawns), `is_legal` | consistency |
| `blockers[them]` via `blockers(them)` (our pieces that block our own sliders from the enemy king) | `gives_check` (discovered check) | consistency |
| `pinners[2]`, `pinners(c)` | **none** | consistency only |
| `checking_squares[6]` | `gives_check` (direct check by the moving piece type; the King entry is read when the king moves) | consistency |
| `castling`, `ep`, `halfmove` | many (FEN, make, legality, keys, repetition window) | several |
| `captured` | `unmake` | via same_state |

So the information Fork needs today is: the checkers of the side to move;
the side to move's own pinned pieces (for movegen and `is_legal`); its
discovered-check candidates, i.e. its own pieces that are the only blocker
between one of its own sliders and the enemy king (for `gives_check`); and
a direct-check test for a piece type landing on a square. Anything beyond
that, namely pinners, the three secondary keys, and eager check squares,
exists today only because tests read it.

**What may change without touching the bench.** The bench only folds
`key()` and counts nodes. Removing `pawn_key`, `material_key` and
`non_pawn_key` does not change `key`. `zobrist::material` is the **last**
table filled in `zobrist::init()`, so removing it leaves every earlier key,
and the bench signature, unchanged. (Removing or reordering any earlier
table would change every key; see the zobrist.hpp invariant.) Computing
check squares lazily inside `gives_check` does not change perft or bench
counts, because bench never calls `gives_check`. `consistency` does,
checking it against `in_check()` after `make` for every legal move at every
node. If you remove State fields or accessors, update `test_consistency.cpp`
to keep an equivalent oracle for whatever remains, using its independent
oracles (remove-a-piece for blockers; brute-force attack checks for direct
checks). **Owner decision needed:** the review recommends removing the
unused keys "until a Fork-designed consumer exists", while the review's own
Phase 3 notes mention possible uses (a non-pawn-material test for null
move). Removing pinners was not explicitly recommended, though it has no
consumer either.

**Performance.** These are review and ideas.md figures, not re-measured
by me: the review says `update_check_info` is about 19% of bench time.
ideas.md idea 9 records make/unmake becoming about 60% slower when eager
check info was added, and that a 5-entry check-square array (King masked)
made `gives_check` 4 to 11% slower than the 6-entry one. Any layout or
lazy-evaluation change needs `bench/ab.py` evidence (DESIGN.md §7).

**Tests that pin H3.** `consistency` (all fields at every node, plus
`gives_check` and `is_legal` against the generator and random moves), the
perft suites and `perft_epd*`, `zobrist_ep`, `fen`, `no_alloc` (make and
unmake must not allocate), and `bench_parity`.

### 2.2 Resemblances to avoid

1. **One routine, in a fixed order**: blockers and pinners for both
   colours, then checkers, then the check squares, all written into the
   State at the end of every make. Re-architect this. The review suggests
   x-ray pin detection (CPW) and computing the direct-check squares lazily
   in `gives_check` (ideas.md idea 9's lazy variant).
2. **The pin scan itself.** Fork collects candidate enemy sliders by
   intersecting the king's empty-board rook and bishop rays with the enemy's
   rook-or-queen and bishop-or-queen sets (local name `snipers`). It then
   visits each candidate, intersects the between-set with the occupancy, and
   when exactly one piece is found adds it to the blockers, also adding the
   slider to the pinners if the piece is the king's own. Do not reproduce
   this candidate-then-single-occupant loop, the name `snipers`, or the
   paired update of the two sets in one conditional. Build it from CPW's
   x-ray formulation ("X-ray Attacks (Bitboards)", "Checks and Pinned Pieces
   (Bitboards)"). Note that CPW's sample finds only the king side's own
   pinned pieces. Fork also needs the other half, the discovered-check
   candidates, and CPW "Discovered Check" observes that both come out of the
   same computation as one union, which can be split by colour afterwards.
3. **The check-squares block**: a six-entry per-piece-type array filled
   in the order pawn, knight, bishop, rook, queen (as the union of bishop
   and rook), with King set to zero last. If you keep an eager table, design
   it differently. Better, drop it and answer direct-check queries on demand
   in `gives_check`.
4. **State field set and grouping.** Today the order is: main key, pawn
   key, material key, per-colour non-pawn keys, then checkers, per-colour
   blockers, per-colour pinners and the six check squares as one contiguous
   run, then castling, ep, halfmove, and the captured piece last. The set of
   fields (the key trio, then checkers / blockers / pinners / check squares)
   and that grouping match. Design the per-ply record from Fork's consumer
   list in 2.1 and nothing more. Order it by Fork's own criteria, for
   example what `make()` copies versus what it recomputes, or cache-line
   use per ideas.md idea 9, and document that rationale in the header
   comment.
5. **The accessor family on Position**: `checkers()`, `blockers(c)`,
   `pinners(c)`, `pinned(c)`, `checking_squares(t)`, `pawn_key()`,
   `material_key()`, `non_pawn_key(c)` (see 4.2). Keep only what has a
   consumer, and name it by what Fork's callers ask for, for example "own
   pinned pieces" and "discovered-check candidates". See 4.4 for checked
   names.
6. **The material key scheme**: one Zobrist key per (piece, count index)
   pair, XORed per piece present. It has no consumer, so remove it with
   `material_key`, unless the owner wants it kept.
7. **Comments.** Rewrite the State and accessor comments in your own words
   when the fields change. No wording match with Stockfish comments was
   found (see 4.5), but the comments describe the old field set.

### 2.3 Independent sources (all opened 2026-10-24)

- CPW "Checks and Pinned Pieces (Bitboards)": https://www.chessprogramming.org/Checks_and_Pinned_Pieces_(Bitboards)
  covers checks on the fly, direct and discovered checks, absolute pins via
  x-ray plus an in-between lookup, and the opposite-ray-direction idea.
- CPW "X-ray Attacks (Bitboards)": https://www.chessprogramming.org/X-ray_Attacks_(Bitboards)
  covers x-ray attacks by modifying the occupancy (removing the first
  blockers and comparing attack sets), and x-rays with one lookup.
- CPW "Pin": https://www.chessprogramming.org/Pin covers absolute, partial,
  relative and cross pins, and what legal movegen needs.
- CPW "Discovered Check": https://www.chessprogramming.org/Discovered_Check
  says discovered-check candidates come from the same computation as
  pinned pieces, as a union separated by colour.
- CPW "Check": https://www.chessprogramming.org/Check (the general page).
- CPW "Square Attacked By": https://www.chessprogramming.org/Square_Attacked_By
  covers attacks to a square by all pieces (the super-piece idea), any
  attack by a side, the legality test, and in-between lookups.
- CPW "Attack and Defend Maps": https://www.chessprogramming.org/Attack_and_Defend_Maps
  (background; only fetched and skimmed).
- **Failed:** CPW "Pinned_Pieces" returned HTTP 404, so there is no page by
  that title. The review's citation of CPW "Pinned Pieces" should point to
  "Pin" and "Checks and Pinned Pieces (Bitboards)" instead.

## 3. M3: between/line table construction (src/core/bitboard.cpp)

### 3.1 Functional contract

The tables are `tables::between[64][64]` and `tables::line[64][64]`,
read through `between(a, b)` and `line(a, b)`. I checked these properties
against the current tables on 2026-10-24:
- Both are **symmetric** in (a, b), and both are **0 when a == b**.
- `line(a, b)` is nonzero **exactly** when a and b differ and share a rank,
  file, diagonal or anti-diagonal (1456 ordered pairs). It is then the
  **whole** line through them, edge to edge, including a and b. For
  example, `line(a1, h1)` is all of rank 1, and `line(a1, h8)` has 8
  squares.
- `between(a, b)` is the set of squares strictly between a and b on that
  line, excluding **both** endpoints. It is 0 when a and b are not aligned
  or are adjacent (1036 ordered pairs are nonzero). It is always a subset of
  `line(a, b)`, minus a and b.
- The golden hashes are in 1.1 (between.bin, line.bin).
- Today both are built inside `build_bitboard_tables()`, after the slider
  tables. Any order is fine, provided they are ready before
  `init_bitboards()` returns.

Consumers: movegen (evasion target, pin restriction along `line`,
castling path and emptiness), `is_pseudo_legal` (castling path empty),
`is_legal` (castling path, evasion target, pin line), `gives_check`
(discovered check stays on the line), and the pin computation in H3. Tests:
`magics` (spot checks only: a1-h8 counts, a1-b3 zero, a1-h1 equals rank 1),
plus everything downstream, meaning the perft suites, `consistency` and
`bench_parity`. Consider adding an exhaustive test against an **independent**
oracle, for example coordinate arithmetic on file and rank differences, or
the golden hashes above. It must not reuse the construction under test
(`.claude/rules/testing.md`: oracles must be independent).

### 3.2 Resemblances to avoid

1. **Deriving both tables from intersections of attack sets taken from
   the two endpoints.** Today, for each aligned pair, `line` comes from
   intersecting the two squares' empty-board attack sets of the matching
   slider kind and adding both endpoints. `between` comes from intersecting
   each square's attacks with the other square placed as the only blocker.
   Alignment is detected by membership in an empty-board attack set, kind
   by kind. These are the matched expressions. Do not build either table
   from slider attack sets at all.
2. **The loop shape**: one nested loop over all ordered pairs, zeroing
   both entries, skipping a == b, then a rook-kind branch and a
   bishop-kind branch, each assigning both tables. Build it differently.
   The review suggests filling both by walking rays: from each square, step
   in each of the 8 directions, accumulating the squares passed (which are
   the between-set for the next square reached), and set the line from the
   full ray pair through the square. Any structure of your own that meets
   3.1 is fine.

### 3.3 Independent sources (opened 2026-10-24)

- CPW "Square Attacked By", section "In Between" (rectangular and
  triangular lookup, 0x88 difference, pure calculation):
  https://www.chessprogramming.org/Square_Attacked_By
- CPW "On an empty Board" (rays and lines by lookup and by
  initialisation loops): https://www.chessprogramming.org/On_an_empty_Board
- CPW "Square Mapping Considerations" (direction offsets, file and rank
  indices): https://www.chessprogramming.org/Square_Mapping_Considerations

## 4. M4: Fork identifiers that also occur in Stockfish's src/

### 4.1 Method

I tokenised every identifier in `src/core/*.{hpp,cpp}` and `src/main.cpp`
(982 distinct tokens), kept the ones Fork declares (types, enumerators,
functions, members, notable locals, file names), and ran `grep -rw` for each
over Stockfish `src/` (`*.cpp`, `*.h`) at effdc3fd. Hits that occur only in
comments or strings, or as a different construct (for example `forward` as
`std::forward`), are marked as such.

### 4.2 Matches

Status key: **G** = generic. The concept or term appears in CPW (page
cited) or is standard C++ or chess vocabulary, and the spelling is
unremarkable. **D** = distinctive: the exact spelling is Stockfish's and
CPW uses other words. **K** = already kept by the owner (DESIGN.md §8,
2026-10-23). A suggestion is given only for D items; every suggested name
had 0 hits in Stockfish src/ (`grep -rlw`, 2026-10-24). Before adopting
any of them, run the DESIGN.md §8 system-header collision check.

| Fork identifier | Fork location | Stockfish use | Status | Suggested neutral name |
|---|---|---|---|---|
| `piece_on(s)` | position.hpp:61 | same Position accessor | D. CPW has "piece on" only as a phrase. | `piece_at(s)` |
| `side_to_move()` | position.hpp:60 | same accessor | G/D: CPW has a page "Side to move" (the term), but the snake_case accessor is Stockfish's | `to_move()` has 4 Stockfish hits, so avoid it. Use `mover()`, or keep it (owner) |
| `ep_square()` | position.hpp:74 | same accessor | D. CPW "En passant" says "en passant target square". | `ep_target()` |
| `pawn_key` (field and accessor) | position.hpp:34, :78 | same accessor | D. CPW "Pawn Hash Table" says "pawn hash key" (forum title). No Fork consumer. | remove (H3), or `pawn_hash()` |
| `material_key` (field and accessor) | position.hpp:35, :79 | same accessor (also in the syzygy code) | D. CPW "Material Hash Table" says "material signature". No consumer. | remove (H3), or `material_hash()` |
| `non_pawn_key` (field and accessor) | position.hpp:36, :80 | same accessor | D. No consumer. | remove (H3), or `piece_hash(c)` |
| `relative_rank(c, s)` | types.hpp:39 | same free function, same argument order | D (no CPW use found) | `rank_from(c, s)` / `rank_for(c, s)` |
| `make_piece(c, t)` | types.hpp:47 | same free function, same argument order | D. CPW "Pieces" says "piece code". | `piece_of(c, t)` |
| `file_of(s)` | types.hpp:29 | same | G per the review. CPW "Square Mapping Considerations" uses "FileIndex". | optional: `file_index(s)` |
| `rank_of(s)` | types.hpp:30 | same | G per the review. CPW says "RankIndex". | optional: `rank_index(s)` |
| `make_square(f, r)` | types.hpp:31 | same (file, rank) | G per the review. CPW says "squareIndex". | optional: `square_at(f, r)` |
| `color_of(p)` | types.hpp:48 | same | D (not in the review's list) | `side_of(p)` |
| `type_of(p)` | types.hpp:49 | same (also a Move method there) | D (not in the review's list) | `kind_of(p)` |
| `promotion_type()` (Move) | types.hpp:93 | same Move method | D | `promo_type()` |
| `raw()` (Move) | types.hpp:86 | same Move method | G (common word) | owner |
| `MoveList` (`contains`, `size`, `begin`, `end`) | types.hpp:103-120 | same class name, and `contains` | K (MoveList kept); `contains` is G | none |
| `generate<GenMode>` | movegen.hpp:23 | same function name, templated on the generation kind | G (CPW "Move Generation" vocabulary). The template-on-kind shape matches. | owner |
| `generate_moves<...>` | movegen.cpp:43 (internal) | same function name in movegen | D (internal helper) | `fill_moves` / any |
| `Captures` (GenMode enumerator, and a template parameter in movegen.cpp:10) | movegen.hpp:18 | an enumerator `Captures` in history code (different meaning) | G | none |
| `pieces()` overload set: (), (c), (t), (c, t), (c, t1, t2) | position.hpp:62-68 | same name and the same overload shapes | G name (CPW calls them piece bitboards); the overload family matches | owner. Optional: split into distinct names such as `occupied()`, `side_bb(c)` |
| `count(c, t)` | position.hpp:69 | `count` (a template there) | G | none |
| `key()` | position.hpp:77 | same accessor | G (CPW "Zobrist Hashing": hash key) | none |
| `fen()` | position.hpp:58 | same accessor | G | none |
| `checkers()` / `State::checkers` | position.hpp:37, :83 | same accessor name | G/D: CPW uses "discovered checkers" as a phrase (X-ray page) | owner. If kept, fine. `checkers_bb()` has 0 hits. |
| `pinners(c)` / `State::pinners` | position.hpp:39, :86 | same accessor and field name | K (DESIGN §8 kept `blockers`/`pinners`). No consumer (H3). | remove, or keep per K |
| `pinned(c)` | position.hpp:87 | a local variable named `pinned` in movegen/position | G (CPW "Pin": pinned piece) | none |
| `attackers_to(s, occ)` | position.hpp:90 | same, with the same signature | K | none |
| `gives_check(m)` | position.hpp:95 | same | K | none |
| `popcount`, `lsb`, `pop_lsb` | bitboard.hpp:32-41 | same | K (pop_lsb kept). `popcount` is also `std::popcount`. CPW "BitScan" uses LS1B/bitScanForward. | none |
| `SliderEntry::attacks`, `SliderEntry::index` | bitboard.hpp:54, :57 | the same member and method names in the per-square magic record | D in combination (H2 item 7) | `table`, `slot()` |
| `SliderEntry::mask`, `::magic`, `::shift` | bitboard.hpp:52-55 | same | G (CPW "Magic Bitboards" Fancy record uses mask/magic/shift) | none |
| `epoch`, `used_epoch` (locals) | bitboard.cpp (search_magic) | the same local name in the magic init | D (H2 item 1) | disappears with H2 |
| `snipers`, `sniper` (locals) | position.cpp:115-121 | the same local name in the pin routine | D (H3 item 2) | disappears with H3 |
| `st()` (private accessor) | position.hpp:127 | `st` is that engine's State-pointer member name | minor (two letters) | `cur()` / `top()` (owner) |
| `capsq`, `kto`, `rto`, `ksq`, `occ`, `us`, `them`, `target` (locals) | movegen.cpp, position.cpp | the same local names | minor. `ksq`, `occ`, `us`, `them` are common. `capsq`/`kto`/`rto` are Stockfish-style abbreviations | optional: `cap_sq`, `king_to`, `rook_to` (0 hits) |
| `init()` | position.hpp:27, zobrist.hpp:23 | `init` in several namespaces | G | none |
| `Key` (type alias) | types.hpp:23 | same alias for a 64-bit hash | G (CPW "Zobrist Hashing") | none |
| `Bitboard`, `Square`, `Color`, `Piece`, `PieceType`, `Move`, `Position` | types.hpp, position.hpp | same type names | G (CPW vocabulary; Position is K) | none |
| `perft`, `bench`, `divide`, `nodes` | perft.hpp | same words | K/G (CPW "Perft" covers perft and divide) | none |
| `bb(s)`, `mask`, `magic`, `shift`, `attacks(...)`, `line`, `between`, `rook`, `bishop`, `next`, `state`, `clear`, `remove`, `add`, `size`, `begin`, `end`, `index`, `bits`, `side`, `material`, `castling`, `captured`, `moves`, `run`, `seconds`, `sparse` | various | the same words as locals, members or comments | G (ordinary words; `between`/`line` appear there only in comments, with different function names) | none, except H2 item 7 and `Rng::sparse` (H2 item 3) |

**File names.** Fork's `types.hpp`, `bitboard.{hpp,cpp}`,
`position.{hpp,cpp}`, `movegen.{hpp,cpp}`, `perft.hpp` and `main.cpp`
correspond to Stockfish's `types.h`, `bitboard.{h,cpp}`, `position.{h,cpp}`,
`movegen.{h,cpp}`, `perft.h` and `main.cpp`. The owner kept `types`,
`bitboard`, `position` and `movegen` (DESIGN.md §8). `perft` is CPW
vocabulary. `bench.cpp` (Stockfish has `benchmark.cpp`), `zobrist.{hpp,cpp}`
(no such file in Stockfish; it uses a capitalised `Zobrist` namespace,
while Fork's namespace is lowercase `zobrist`), `perft.cpp` and
`movegen.cpp` raise no new issues.

**No hits** for these Fork names, among others: `king_square`,
`in_check`, `is_legal`, `is_pseudo_legal`, `blockers`, `has_multiple`,
`checking_squares`, `predicted_key`, `castling_rights`, `halfmove_clock`,
`State`, `GenMode`, `NoSquare`, `NoPiece`, `FileA`, `Rank1`,
`shift_north`, `ray_walk`, `pawn_attacks`, `knight_attacks`,
`king_attacks`, `rook_attacks`, `bishop_attacks`, `queen_attacks`,
`zobrist` (lowercase), `piece_square`, `ep_file`, `compute_state`,
`toggle_keys`, `same_state`, `mirrored`, `repetition_count`,
`insufficient_material`, `move_to_uci`, `parse_uci`, `StartFen`, `set_fen`
(Stockfish uses another name), `from()`/`to()` (Stockfish uses other
names).

### 4.3 Design-level matches (not names)

- **Piece encoding**, colour times 8 plus type, documented in DESIGN.md
  §4.1. Stockfish also packs colour into bit 3, but its type numbering
  differs (Fork's Pawn is 0 and its NoPiece is 15). This is generic.
  UNVERIFIED as a CPW citation: CPW "Pieces" discusses piece codes, but I
  did not find this exact layout on the pages I opened.
- **Castling encoded internally as king-origin to rook-square**
  (types.hpp:55, DESIGN.md §4.1). Stockfish uses the same internal
  convention. CPW "Encoding Moves" (opened) does not describe it; it uses
  king-castle and queen-castle flags instead. UNVERIFIED whether the UCI
  protocol's Chess960 convention is a citable independent source; I did not
  open the UCI specification.
- **Move flag nibble** (quiet, double push, castle, capture, ep, promotions
  8-15): this follows the CPW "Encoding Moves" table (opened). Generic.

### 4.4 Pre-checked zero-hit names, for the implementer's renames

Each name below had 0 files in `grep -rlw` over Stockfish src/ at
effdc3fd (2026-10-24): `piece_at`, `mover`, `ep_target`,
`en_passant_target`, `pawn_hash`, `material_hash`, `piece_hash`,
`rank_from`, `rank_for`, `colored_piece`, `piece_of`, `file_index`,
`rank_index`, `square_at`, `square_index`, `side_of`, `kind_of`,
`promo_type`, `promoted_type`, `piece_set`, `count_of`, `checkers_mask`,
`checkers_bb`, `checking_pieces`, `king_xray`, `table_base`,
`occupied_mask`, `attack_slot`, `used_stamp`, `stamp`, `pinned_mask`,
`discoverers`, `pin_mask`, `lowest_bit`, `pop_lowest`, `bit_count`,
`xray`, `epsq`, `cap_sq`, `rook_to`, `king_to`, `attackers_of`, `hash_key`,
`zobrist_key`.

Names with hits (avoid them): `to_move` (4 files), `turn` (1), `slot` (3),
`lookup` (6), `generation` (7), `hash` (16), `has` (15), `pinning` (1).

### 4.5 Comments that echo Stockfish comments

I compared every Fork `//` comment in src/ against all Stockfish
comments using shared 4-word sequences. The only overlaps were "the side to
move" (position.hpp:37, :40, :133), "positions since the last"
(position.cpp:561), "pawn is the one" (position.cpp:539), and "castling is
encoded as" (types.hpp:55). These are common phrases; none reproduces a
Stockfish sentence. Two of them touch the topics above:
- types.hpp:55 ("Castling is encoded as king origin -> castling rook
  square."): the wording differs from Stockfish's, but the concept is the
  same (see 4.3).
- position.hpp:38-39, the comments on blockers and pinners: different
  wording, but the same concept as Stockfish's description of its
  blockers and pinners. Rewrite them along with the H3 fields.

## 5. What ORIGINALITY.md and DESIGN.md say today (text to replace)

`docs/ORIGINALITY.md`, quoted:

- Line 15 (a rule that stays true after H2): "Lookup constants (magic
  numbers, Zobrist keys) are generated by Fork's own code from fixed seeds.
  They are never copied from published tables."
- Line 27: "| 2026-10-23 | Chess Programming Wiki: Encoding Moves, Magic
  Bitboards, Zobrist Hashing, Square Mapping Considerations | General
  techniques for Phase 1 data structures (design in docs/DESIGN.md §4). |".
  It needs CPW "Looking for Magics" and "Traversing Subsets of a Set" for
  H2, the H3 pages from 2.3, and the M3 pages from 3.3. Vigna's xorshift64*
  paper and splitmix64 are also missing (review M5).
- **Line 33 (the H3 entry, to be rewritten):** "| 2026-10-23 | Stockfish
  design (recalled from prior study, source not opened this session):
  per-ply state record holding checkers, blockers/pinners per king and
  check squares; `gives_check` via check squares plus discovered-check
  blockers; a key-after-move helper (Stockfish: `key_after`) for TT
  prefetch | Ideas only, for Position::State, gives_check and predicted_key
  (renamed from key_after on 2026-10-23, see below). Fork's code is written
  from DESIGN.md; its blocker definition differs deliberately (removal
  semantics, no sniper exclusion). |"
- Lines 36-51, "Identifier renames": a table of four renames (`GenType`
  to `GenMode`, `more_than_one` to `has_multiple`, `check_squares` to
  `checking_squares`, `key_after` to `predicted_key`). The M4 decisions
  should be added here.
- There is **no entry** for the magic search (H2) or the between/line
  construction (M3) naming any source other than CPW "Magic Bitboards" in
  line 27. The review notes that ORIGINALITY.md does not list Stockfish for
  them.

`docs/DESIGN.md`:
- §4.2: "`between(a, b)` holds the squares strictly between two aligned
  squares, and `line(a, b)` holds the full line through them." This stays
  true.
- §4.3: "Magic numbers are found at startup by Fork's own search, using
  sparse random candidates from a fixed-seed xorshift generator." Update it
  if the generator changes. The Fancy and PEXT bullets stay true.
- §4.5 still describes an `Undo` vector (review L2). Update it with the
  new State.
- §8 "Kept" list: `pop_lsb`, `attackers_to`, `blockers`/`pinners`,
  `MoveList`, `gives_check`, `is_pseudo_legal`. Revisit it if pinners is
  removed or renamed.

## 6. Verification checklist for the rewrite

Run these on both platforms, per CLAUDE.md and review "Deferred tests"
item 7:
- `scripts/check.sh full`, `ctest -L slow`, and `scripts/build.sh` (all
  presets plus PGO);
- bench unchanged on every preset (26401709 / f298a22041a6270a);
- the golden SHA-256s from 1.1 reproduced in a nopext build **and** a
  PEXT build;
- startup ("init_tables") and make/unmake timing compared with
  `bench/ab.py`, with a note if anything gets slower;
- ORIGINALITY.md entries rewritten (section 5), with M4 decisions
  recorded per name after the owner decides.

Owner consideration (outside this spec's scope): the current paraphrased
versions remain in git history, which becomes public. Whether that matters
for the Category 4 application is UNVERIFIED and is the owner's call.

## 7. Sources (opened by the dirty session; dates are 2026-10-24)

| URL / object | What it is | Result | Used for |
|---|---|---|---|
| https://github.com/official-stockfish/Stockfish (shallow clone into a session scratch dir, outside the Fork repo) | Stockfish source, GPL-3.0 (Copying.txt) | HEAD effdc3fd3f6de6e75fe1374a51a7a7eed66f880b, 2026-10-17 | Comparing resemblances (H2, H3, M3); M4 name greps |
| https://www.chessprogramming.org/Looking_for_Magics | CPW | 200, read | H2 sources |
| https://www.chessprogramming.org/Magic_Bitboards | CPW | 200, read (Fancy section) | H2 sources, M4 (record field names) |
| https://www.chessprogramming.org/Traversing_Subsets_of_a_Set | CPW | 200, read (Carry-Rippler) | H2 |
| https://www.chessprogramming.org/On_an_empty_Board | CPW | 200, read | H2 mask, M3 |
| https://www.chessprogramming.org/Square_Attacked_By | CPW | 200, read (In Between, Attacks to a Square) | H3, M3 |
| https://www.chessprogramming.org/Checks_and_Pinned_Pieces_(Bitboards) | CPW | 200, read | H3 |
| https://www.chessprogramming.org/X-ray_Attacks_(Bitboards) | CPW | 200, read | H3 |
| https://www.chessprogramming.org/Pin | CPW | 200, read (intro) | H3, M4 |
| https://www.chessprogramming.org/Discovered_Check | CPW | 200, read | H3 |
| https://www.chessprogramming.org/Check | CPW | 200, skimmed | H3 |
| https://www.chessprogramming.org/Pinned_Pieces | CPW | **404, failed** | (no page by this title) |
| https://www.chessprogramming.org/Square_Mapping_Considerations | CPW | 200, read (index formulas) | M3, M4 (FileIndex/RankIndex/squareIndex) |
| https://www.chessprogramming.org/Encoding_Moves | CPW | 200, read (flag table, castling text) | M4 / 4.3 |
| https://www.chessprogramming.org/Zobrist_Hashing | CPW | 200, grepped | M4 (Key) |
| https://www.chessprogramming.org/Pawn_Hash_Table | CPW | 200, read (intro) | M4 (pawn_key) |
| https://www.chessprogramming.org/Material_Hash_Table | CPW | 200, read (intro) | M4 (material_key) |
| https://www.chessprogramming.org/Side_to_move | CPW | 200, read | M4 (side_to_move) |
| https://www.chessprogramming.org/En_passant | CPW | 200, grepped | M4 (ep_square) |
| https://www.chessprogramming.org/Pieces | CPW | 200, grepped | M4 (make_piece), 4.3 |
| https://www.chessprogramming.org/Squares | CPW | 200, grepped | M4 |
| https://www.chessprogramming.org/Ranks , /Files , /Color , /Castling | CPW | 200 each, grepped only | M4 term search (no relevant hits) |
| https://www.chessprogramming.org/Perft | CPW | 200, grepped | M4 (perft, divide) |
| https://www.chessprogramming.org/BitScan , /Population_Count , /General_Setwise_Operations , /Bitboard_Serialization | CPW | 200 each, grepped | M4 (lsb/pop_lsb/popcount terms) |
| https://www.chessprogramming.org/Move_Generation , /Attack_and_Defend_Maps , /Kogge-Stone_Algorithm , /Dumb7Fill | CPW | 200 each, skimmed | background only |
| https://www.chessprogramming.org/Pseudorandom_Number_Generator | CPW | 200, grepped (no Vigna/xorshift* content) | H2 (not useful) |
| https://www.chessprogramming.org/Xorshift | CPW | **404, failed** | (no page by this title) |
| https://arxiv.org/abs/1402.6246 and https://arxiv.org/pdf/1402.6246 (v5) | Vigna, xorshift* paper | 200, abstract and PDF read (Table IV, section 9) | H2 generator citation |
| https://arxiv.org/abs/1404.0390 | Vigna, "Further scramblings..." | 200, abstract only | H2 (optional) |
| https://prng.di.unimi.it/ | Vigna's PRNG page | 200, fetched | H2 |
| https://prng.di.unimi.it/splitmix64.c | splitmix64 reference, public domain | 200, read (header) | H2 alternative generator |
| https://doi.org/10.1145/2845077 | ACM TOMS DOI for the xorshift* paper | **403, failed** (publisher blocks the fetch) | citation not verified via the publisher |
| https://doi.org/10.1145/2660193.2660195 | DOI for Steele/Lea/Flood, SplittableRandom | **403, failed** | not used |

Every CPW page fetched on 2026-10-24 carried a banner saying the wiki is
a "temporary, read-only recovery" while a longer-term plan is worked out.
The content was available; future URLs may change.

Fork files read: CLAUDE.md, docs/DESIGN.md (§4, §6, §8), docs/ORIGINALITY.md,
docs/ideas.md (idea 9), REVIEW-phase1.md (H2, H3, M3, M4, Phase 3 notes,
deferred tests), src/core/* (all), src/main.cpp (declarations),
tests/test_consistency.cpp, tests/test_magics.cpp, tests/bench.ref,
CMakeLists.txt (test list), tools/magic_seeds.cpp, bench/micro.cpp
(init_tables).
