# Phase 1 summary: board, move generation, perft (2026-10-23 to 2026-10-24)

## What was built

- **Core** (`src/core/`, about 1,900 lines): 16-bit moves, bitboards,
  leaper and between/line tables, slider attacks by fancy magics (Fork's own
  seeded search) or BMI2 PEXT, splitmix64 Zobrist keys, a Position with a
  56-byte per-ply State stack, fully legal move generation with Legal /
  Captures / Quiets modes, `is_pseudo_legal` / `is_legal` / `gives_check` /
  `predicted_key`, FEN with strict validation, draw rules, perft, divide and
  a perft-based bench (26401709 nodes, signature f298a22041a6270a).
- **Tests** (14 CTest entries): CPW perft suite and mirrors, the Roce and
  perft-random EPD suites (to depth 6: 4,185,882,506,133 nodes, 0
  mismatches), per-node consistency against independent oracles, exhaustive
  magic and between/line checks, FEN edge cases, draws, a counting-allocator
  `no_alloc` test, bench parity on every build. Differential testing against
  python-chess, Syzygy WDL checks of the material-draw rule, two libFuzzer
  targets with committed minimized corpora.
- **Builds**: 10 presets (clang/gcc x debug/release/v3/avx512/nopext) plus
  PGO on Windows and Linux, ASan/UBSan, TSan, MSan with an instrumented
  libc++, valgrind. `update.sh` builds the TCEC binary on TCEC's own
  toolchain (Ubuntu 22.04: gcc 11.4, g++-12, clang 16, clang 19).
  `scripts/check.sh full` runs Windows, Linux and the TCEC toolchain on
  every commit.
- **Licence and record**: GPL-3.0 (LICENSE, README.md with the AI
  disclosure), docs/ORIGINALITY.md with every source, tool and finding.

## What was learned

- **Originality needs process, not intent.** A design studied from
  Stockfish earlier produced code the review judged too close to it, and a
  function written to match python-chess's rules became a translation of
  it. Both were fixed by clean-room rewrites: a research agent writes a
  code-free spec with golden fingerprints; the implementer never opens the
  other code; an independent checker reviews the result. The method and its
  two small lapses are documented in ORIGINALITY.md, and the spec is
  archived here (`cleanroom-spec.md`).
- **Build where the judge builds.** The TCEC servers' Ubuntu 22.04
  toolchain rejected Fork (CMake 3.25 floor, `<format>`) while every local
  compiler accepted it; only a real 22.04 environment showed it.
- **Prove bounds instead of searching for counterexamples.** The MoveList
  question was settled by rejecting impossible material in `set_fen` and
  deriving a hard limit (323 moves), not by searching for many-move FENs.
- **Measure, then decide.** The eager check squares cost every make; the
  lazy version makes make/unmake 16-19% faster and `gives_check` 70-80%
  slower (bench/ab.py). The fixed-array State stack was measured slower and
  dropped.
- **Facts from sources.** Perft position 6 was once typed from memory
  wrong; since then every FEN, count and constant is checked against its
  primary source.

## What carries forward

- **Phase 2 (UCI)**: spec approved (DESIGN.md §5.1): `Move Overhead`
  (100 ms), `LogFile`, deterministic placeholder mover, version
  `Fork <semver>-dev+<commit>`, `id author BOSSDOTCOM`, parallel hash
  clearing, fastchess compliance and cutechess-cli game runs.
- **Phase 3**: count `gives_check` calls per make and test the lazy per-ply
  check squares if the ratio nears 2 (ideas.md idea 9); design the State
  fields search needs (non-pawn material for null move, NNUE deltas);
  Fathom 7-piece support UNVERIFIED (idea 12); a capture list without quiet
  underpromotions for qsearch changes bench.
- **Open with TCEC (Discord list, docs/kb/competition.md)**: questionnaire
  address, minimum strength, licence requirement, match runner, recommended
  Move Overhead.
- **Not yet public**: the GitHub repository does not exist yet; once it
  does, README.md and the TCEC submission get its URL (`update.sh` clones
  from `FORK_REPO` when run outside a checkout).
