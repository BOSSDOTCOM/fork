# Fork

Fork is a UCI chess engine in C++20, written to compete in TCEC (the Top
Chess Engine Championship). Phase 1 (board representation, legal move
generation, perft) and Phase 2 (the UCI protocol) are complete; Phase 3
(search) is in progress, with a deliberately simple bootstrap evaluation
until Phase 4 replaces it (docs/DESIGN.md).

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

## Building

Requirements: Linux x86-64, CMake 3.22 or newer, Ninja or make, and
gcc 11+ or clang 16+ (C++20).

```bash
git clone https://github.com/BOSSDOTCOM/fork.git fork
cd fork
./update.sh                       # builds build/tcec/fork and prints its path
build/tcec/fork bench             # search bench: nodes and a signature (tests/bench.ref)
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
main and every pull request (except docs-only changes) from a clean clone
on TCEC's toolchain (an Ubuntu 22.04 container: gcc 11.4,
g++-12, clang 16 and 19, CMake 3.22) and on current Ubuntu, and runs the
fast tests and bench parity.

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
