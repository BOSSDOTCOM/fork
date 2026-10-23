---
paths:
  - "src/**/*.{cpp,hpp}"
  - "tests/**/*.{cpp,hpp}"
  - "bench/**/*.cpp"
  - "fuzz/**/*.cpp"
  - "tools/**/*.cpp"
---
# C++ style for Fork

- Formatting is `.clang-format` (Google-based, 110 columns). The post-edit
  hook applies it; don't fight it by hand.
- Naming (DESIGN.md "Naming conventions"):
  - types `PascalCase`; functions, variables and files `snake_case`;
  - private members end in `_`;
  - constants and enumerators `PascalCase`;
  - macros `FORK_UPPER_CASE`;
  - everything lives in `namespace forkeng` (tests in `forkeng::test`).
- Every module header starts with a comment giving its purpose and its
  invariants. Keep it true when you change behaviour.
- Hot paths (movegen, make/unmake, search, eval):
  - no heap allocation (enforced by `fork_alloc_test`);
  - no exceptions thrown;
  - no virtual dispatch per node;
  - no `std::function`.
- Prefer `constexpr`, fixed-size arrays and bitboards over containers in
  engine state. Hot structures are cache-aligned (DESIGN.md section 7).
- Determinism:
  - no unseeded randomness;
  - no iteration over unordered containers that affects search or bench;
  - no floating point in search decisions unless it's proven identical across
    builds.
- Warnings are errors on clang and gcc (`-Wall -Wextra -Wpedantic -Wshadow
  -Werror`). clang-tidy runs with the repo's `.clang-tidy` and must stay
  clean. A disabled check needs a written reason in that file.
- Don't copy or closely paraphrase code from other engines.
- Before introducing any new type, function, member or file name, grep
  Stockfish's current source (a shallow clone). If it matches and isn't
  generic CPW vocabulary, flag it to the owner before using it (DESIGN.md
  section 8).
