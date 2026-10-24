# Phase 2 summary: UCI (2026-10-24)

## What was built

- **UCI front end** (`src/uci/`, about 1,300 lines): `UciSession` reads stdin
  on the input thread (LF, CRLF and lone CR; binary stdin on Windows) and
  runs each `go` on its own search thread with its own copy of the position.
  `isready`, `stop`, `ponderhit` and `quit` are answered during a search;
  every `go` prints exactly one `bestmove` after a scored `info` line;
  `go infinite` and `go ponder` wait for `stop` (or `ponderhit`). One output
  path (`OutputChannel`) writes whole flushed lines under a mutex, sanitizes
  echoed input, and keeps the optional `LogFile`. Commands: every UCI
  command, all `go` arguments (64-bit, negative and huge values clamp), and
  the extensions `d`, `bench`, `go perft`, which print only `info string`.
- **Options**: `Hash` (16 MB, 1 to 4194304), `Clear Hash`, `Threads` (1 to
  4096), `Move Overhead` (100 ms, 0 to 10000), `SyzygyPath` (counts table
  files), `LogFile`. Hash is allocated at the next `isready`/`ucinewgame`/
  `go`, after every option is set, as one OS block (`mmap` 2 MiB aligned +
  `MADV_HUGEPAGE`, `VirtualAlloc`) checked first against available memory,
  and first-touch cleared by `max(Threads, hardware threads)` workers (at
  least 2 MiB each); a refused size falls back with `info string`.
- **Placeholder chooser** (deleted in Phase 3): mate in one, else best
  MVV-LVA capture, else the first legal move.
- **Out-of-memory safety**: a failed allocation during a `go` still yields
  one real `bestmove`, from fixed buffers.
- **Tests and tools**: pipe-driven `uci_protocol`, `uci_options`,
  `uci_placeholder`, `uci_timing` suites (a cross-platform child-process
  driver), `uci_oom` (fails each allocation of a `go` in turn), `fuzz_uci`
  (the parsers with no threads, every output line validated, per-command
  seeds), TSan presets, `scripts/uci-smoke.sh` (50 UCI starts of every
  Windows GCC preset in every `check.sh full`), `tools/placeholder_check.py`
  (python-chess oracle), `tools/phase2_games.sh` + `pgn_summary.py`,
  `tools/hash_timing.cpp`, `tools/make_openings.py`.

## Results (final tree)

| Check | Result |
|---|---|
| UCI suites | protocol 14, options 14, placeholder 1, timing 1, plus `uci_oom`; every preset, both platforms |
| Timing (clang-release, Windows) | uci->uciok 3.1 ms (33 ms cold), first isready->readyok 1.3 ms with 16 MB Hash, stop->bestmove 0.09 ms |
| Hash clear, 12 workers | 1 GiB: 44 ms Windows, 96 ms WSL; 4 GiB: 377 ms WSL; 16 GiB refused cleanly (6.7 GB available) |
| Placeholder vs python-chess | 54,198 positions, 0 failures |
| Sanitizers | ASan/UBSan (both platforms), TSan (clang, gcc), MSan with instrumented libc++: clean |
| `fastchess --compliance` | 40/40 steps, release and ASan builds |
| Games | 800 (cutechess-cli + fastchess: 10+0.1, st, depth, and 2+0.02 with every CPU busy): all ended by the rules, no forfeits, illegal moves, crashes or warnings |
| Builds | all 10 presets + 2 PGO on Windows and the Linux clean clone; `update.sh` with gcc 11.4, g++-12, clang 16, clang 19, bench parity |
| Slow suites (Linux clean clone) | perft_epd_deep 53 s, perft_epd_full 1653 s, pass |
| Fuzzing | fuzz_uci on the final parser code (11852b0; no source change since): 747,315 runs in 1210 s with 6 jobs, coverage 1505 edges from 4 s on, plateaued under the 20-minute rule, 0 crashes. fuzz_fen and fuzz_moves skipped at phase end (owner, 2026-10-24): nothing they exercise changed since phase-1 (three comment lines in position.hpp). Corpora minimized: fen +1 input (seed-min), moves +0, uci +1118 (about 0.95 MB, 188 edges beyond the hand-written seeds) |
| Bench | unchanged: 26401709 nodes, signature f298a22041a6270a |

## What was learned

- **Run every preset before declaring done.** The Windows gcc-debug engine
  crashed in about half of all starts (MinGW GCC emits aligned AVX stores to
  16-byte-aligned stack slots), and no commit check started that build. Fix:
  `-Wa,-muse-unaligned-vector-move` for MinGW GCC; prevention: the UCI smoke
  loop in `check.sh full` and the gcc-debug suite at every phase end.
- **An independent review finds what the author's tests encode away.** The
  reviewer's allocation-failure test and the fallback-workers test were bugs
  my suite could not see; the originality checker found the option limits
  equal to Stockfish's, which the owner then replaced with Fork's own.
- **Spec clauses need a second look against the platform.** The approved
  chunked Hash fallback would have defeated Linux's per-request overcommit
  check; the owner replaced it with one block plus an available-memory check.
- **Facts written from memory were checked**: the OS memory claims went
  through primary sources (KB `os-memory.md`), which corrected two comments.
- **Check that a checker can fail**: every important test was fault-injected
  once (missing bestmove, Threads-before-Hash ordering, MVV-LVA tie-break,
  a data race for TSan, output validation and unknown-command silence for
  the fuzzer, the smoke loop against the pre-fix binary).

## What carries forward

- **Phase 3 (search)** replaces `src/uci/placeholder.*`; `GoLimits` is the
  input for time management (Phase 5); `HashMemory` is the TT's memory, and
  the TT index must use 64-bit arithmetic for the 4 TiB maximum (DESIGN.md
  §5.1 notes). Phase 3 starts in a fresh session after the idea mining and
  the clean-room descriptions.
- **Phase 4**: copy the owner's training-data decisions from branch kb into
  the Phase 4 spec (DESIGN.md §5 outline).
- **Open with TCEC** (KB competition.md, Discord questions): questionnaire
  address, minimum strength, licence, match runner, recommended Move
  Overhead, and (new) the servers' kernel version and overcommit setting.
- **UNVERIFIED**: GCC bug 54412 as the name of the MinGW problem and the
  binutils version of the assembler option; cloning with `FORK_REPO` until
  the repository is public; the KB's open UCI points (bare `go`, promotion
  letter case).
