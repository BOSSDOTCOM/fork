# Fork

Fork is a UCI chess engine in C++20, written to compete in TCEC (the Top
Chess Engine Championship). Phase 1 (board representation, legal move
generation, perft) is complete; the UCI protocol, search and evaluation are
the next phases (docs/DESIGN.md).

## AI-assisted development

Fork is written by an AI coding agent, Claude Code (model: Claude Opus 5.5),
under the direction of its owner, BOSSDOTCOM, since 2026-10-23. All parts of
the code and documentation are AI-written or AI-assisted; every commit
carries `Co-Authored-By` and `Claude-Session` trailers, so the git log is
the record. In TCEC terms Fork is a Category 4 engine.

Fork is original work: it contains no source code, network files or
engine-generated training data from other engines. Every reference,
library and data source is logged in [docs/ORIGINALITY.md](docs/ORIGINALITY.md),
including resemblances to other code found in review and the clean-room
rewrites that removed them.

## Building

Requirements: Linux x86-64, CMake 3.22 or newer, Ninja or make, and
gcc 11+ or clang 16+ (C++20).

```bash
git clone <repository URL> fork
cd fork
./update.sh                       # builds build/tcec/fork and prints its path
build/tcec/fork bench             # nodes 26401709, signature f298a22041a6270a
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

Other commands: `fork perft <depth> [fen]`, `fork divide <depth> [fen]`,
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
