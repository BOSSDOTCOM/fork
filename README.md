# Fork

Fork is a UCI chess engine in C++20, written to compete in TCEC (the Top
Chess Engine Championship). Phase 1 (board representation, legal move
generation, perft), Phase 2 (the UCI protocol) and Phase 3 (search) are
complete. Phase 4 (the evaluation network) is in progress: Fork evaluates
with its own NNUE network, r8btd90 (`nets/r8btd90.fnet`, built into the
binary), trained on Fork's own self-play games and a small share of
endgame positions labelled by the Syzygy tablebases (docs/DESIGN.md).

Phase 4's second milestone (2026-11-08) brings the S512+PP architecture
(the S-512 network plus 608 pawn-link inputs, kept incrementally), and
S512ppr3, its second retrain, as the default network (STC +7.12 ± 4.53 Elo against S512ppr2, its predecessor
as default). It adds time management (b): the soft time limit scaled by
best-move stability and the best move's share of the nodes, with
constants fitted on Fork's own search data (STC +18.69 ± 7.18 Elo, LTC
+10.23 ± 5.14 Elo, against off). On the tooling side: a faster CI (a gate
job classifies each change, documentation-only changes skip the build
matrix, and one "CI result" job sums up the run), the design R test
method for search changes (a futility stop, stage caps, a two-try limit
per time control, and head-to-head selection of constants), and Phase 4 step
1's measurement instrumentation (search counters, an iteration trace and
a decision ledger for pruning, compiled only into the `clang-stats` build, with their
analyses in `tools/measure/`).

## Strength

Fork's latest gauntlet (2026-11-08) rates it **3488.2 ± 20.4** (Ordo, on
the CCRL Blitz scale). This is a rating on the CCRL Blitz scale from games
on GitHub's runners, not a CCRL rating. How it was measured
(`.github/workflows/gauntlet.yml`, run 42538371594):

- Fork at commit 32c5517 (the S512ppr3 network, time management (b) and
  every search feature adopted so far; bench signature 1cb0717f040c294d,
  checked on the runner), built by `update.sh` with gcc 11.4 for
  x86-64-v3;
- 1,400 games, 200 against each of seven anchors built from their
  official sources at pinned commits (`tools/gauntlet/anchors.tsv`):
  Clover 6.1, Altair 7.0.0, Marvin 6.3.0, Laser 1.7, Winter 0.9,
  Monolith 2.01 and Weiss 1.0;
- 10 seconds plus 0.1 seconds per move, one thread, Fork's hash 16 MB,
  200 random 8-ply openings each played with both colours;
- shards of 100 games on 4-core runners, 3 games at a time; no time
  forfeits;
- Ordo 1.2.6 with the anchors fixed at their CCRL Blitz ratings.

Fork scored 931.5 of 1,400 (67%). The same run played 400 games against
Stockfish 19 as a reference, kept out of the Ordo fit: Fork scored 87 of
400, a gap of **−222 Elo (95% interval −251 to −196)**. The per-anchor
scores and the full record are in docs/DESIGN.md (decisions log,
2026-11-08).

## AI-assisted development

Fork is written by an AI coding agent, Claude Code (model: Claude Opus 5.5),
under the direction of its owner, BOSSDOTCOM, since 2026-10-23. All parts of
the code and documentation are AI-written or AI-assisted. The commits carry
a `Co-Authored-By` trailer and nearly all a `Claude-Session` trailer (13
commits of 2026-10-23 and 2026-10-24 lack the second; merge commits may
carry neither), so the git log is the record. The experimental heuristic-discovery tools in
`tools/evolve/` run further Claude agents (model: Claude Sonnet); no code of
theirs is in the engine. In TCEC terms Fork is a Category 4 engine.

Fork's own code is original work. The one exception is the vendored Fathom
library (below), Syzygy tablebase probing code from other authors. Fork
contains no other engine's source code, network files or engine-generated
training data. Every reference, library and data source is logged in
[docs/ORIGINALITY.md](docs/ORIGINALITY.md), including resemblances to other
code found in review and the clean-room rewrites that removed them.

## Third-party code and credits

- **Fathom** (`third_party/fathom/`, vendored unchanged from
  jdart1/Fathom at c9c6fef0; MIT licence in `third_party/fathom/LICENSE`):
  Syzygy tablebase probing. Its probing code is Ronald de Man's, written
  for Stockfish and taken from Cfish's `tbprobe.c` (a Stockfish
  derivative), released by its author for unrestricted use; the board and
  move-generation support is Basil Falcinelli's original Fathom; it is
  maintained by Jon Dart (Fathom's README and file headers). Fork calls
  only its public header.
- **Time budget**: the shape of Fork's first time allocation (the clock
  over 30 moves plus an increment term, a hard limit of four shares capped
  at 0.9 of the clock) is near Berserk 4.5.0-8's, which is credited in
  `src/search/time_budget.cpp` and docs/ORIGINALITY.md.
- **Data and references**: the Syzygy tablebases (Ronald de Man); the
  CC0 Lichess game export behind 40 of the 46 search-bench positions; the
  splitmix64 generator (Sebastiano Vigna, public domain); Daniel Lemire's
  range reduction for the TT index; Shannon's material values; the Chess
  Programming Wiki's technique descriptions. The details and the test-only
  tools are in docs/ORIGINALITY.md.
- **The network**: trained with **bullet** (jw1912/bullet, MIT), used as
  a tool at a pinned commit (`tools/train`); no bullet code is in the
  engine. Its training data are Fork's own self-play games, labelled by
  Fork's own search, written in the **viriformat** file layout (Fork's own
  reader and writer, from the format's README). The games start from
  positions of the CC0 Lichess game export. Since S512ppr2 the data also
  hold a small fixed share of random endgame positions of at most five
  pieces, labelled by their Syzygy WDL (`tools/datagen/endgame_slice.py`).

## Building

Requirements: Linux x86-64, CMake 3.22 or newer, Ninja or make, and
gcc 11+ or clang 16+ (C++20).

```bash
git clone https://github.com/BOSSDOTCOM/fork.git fork
cd fork
./update.sh                       # builds build/tcec/fork and prints its path
build/tcec/fork bench             # search bench: nodes and a signature (tests/bench-r8btd90.ref)
```

`update.sh` builds the engine only (Release, `-O3 -g`, no tests, no
downloads) for `FORK_ARCH=x86-64-v3` by default; set `FORK_ARCH=x86-64-v4`
for AVX-512 or `CXX` to choose the compiler. It never uses `-march=native`.

Development builds and tests use the CMake presets (CMake 3.25+), after
sourcing the toolchain environment:

```bash
. scripts/env.sh
cmake --preset clang-release && cmake --build build/clang-release
ctest --test-dir build/clang-release -LE slow --output-on-failure
```

Continuous integration (`.github/workflows/ci.yml`) builds every push to
main and every pull request from a clean clone on TCEC's toolchain (an
Ubuntu 22.04 container: gcc 11.4, g++-12, clang 16 and 19, CMake 3.22), on
current Ubuntu and on Windows. It runs every test suite, the sanitizers and
bench parity; documentation-only changes skip the build jobs, and the
longest suites (the full perft and TSan runs) run when the files they test
change and nightly on main. One job, "CI result", passes only when every
other job passed or was skipped by its own rule.

Other commands: `fork perft <depth> [fen]`, `fork divide <depth> [fen]`,
`fork perftbench` (the move-generation workload, tests/perft_bench.ref),
`fork version`. See CLAUDE.md and docs/DESIGN.md for the full workflow.

## License

Copyright (C) 2026 BOSSDOTCOM.

Fork is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version (GPL-3.0-or-later).
It is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See [LICENSE](LICENSE) for the full text.
