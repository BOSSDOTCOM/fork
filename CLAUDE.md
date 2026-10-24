# Fork

Fork is an **original** UCI chess engine in C++20, built to compete in TCEC
(primary target: the TCEC Swiss). It is a TCEC "Category 4" engine (written
with major AI help), so its code must stay public, buildable from source,
and demonstrably original.

This file is context. Enforcement lives in hooks (`.claude/settings.json`,
`scripts/hooks/pre-commit`) and `scripts/check.sh`.

## Where things are

- `docs/DESIGN.md`: architecture, phase specs, module layout, naming,
  performance doctrine, decisions log. Read the relevant section before
  editing.
- `docs/ORIGINALITY.md`: every reference, library and data source. Update it
  when you consult something.
- `docs/ideas.md`: idea log (type ELO or TOOLING, phase, metric, status).
- `docs/kb/` (branch `kb`, worktree `../fork-kb` beside this repo): tools,
  techniques, research, TCEC rules, originality precedents, sources.
- `config/tcec.json`: tournament conditions. Only test scripts read it; the
  engine never does.
- `config/local-test.json`: local test environment from the kb branch's
  `tools/install.sh` (WSL): Syzygy 3-4-5 at
  `~/fork-tools/syzygy/3-4-5`, runners in `~/fork-tools/bin`
  (fastchess, cutechess-cli, ordo). Test scripts only.
- `.claude/rules/`: area rules (C++ style, testing, SIMD).
- GitHub: private repo https://github.com/BOSSDOTCOM/fork (remote `origin`;
  push main, kb, tcec-cutechess and tags). CI in `.github/workflows/ci.yml`:
  TCEC toolchain (ubuntu:22.04 container, update.sh with 4 compilers, bench
  parity, gcc 11.4 fast tests) and current Ubuntu presets. It runs only on
  pushes to main and pull requests, skips docs-only changes, cancels
  superseded runs (Actions minutes are limited: about 10 billed minutes per
  run). Never push the local backup bundles (`*.bundle`).
- TCEC toolchain: WSL distro `Ubuntu-22.04` (gcc 11.4, g++-12, clang 16/19,
  CMake 3.22), set up by `scripts/tcec-toolchain-setup.sh`; runs as root.
  CMake must stay at a 3.22 floor and the code within libstdc++ 11's C++20.

## Commands (Git Bash; source the env in every shell)

```bash
. scripts/env.sh                              # toolchain on PATH (Windows) / compilers (Linux)
scripts/build.sh                              # all presets + PGO, summary table
scripts/build.sh clang-release gcc-debug      # chosen presets
scripts/check.sh quick                        # clang-release build + fast tests
scripts/check.sh stop                         # Stop hook: clang-release, all non-slow tests; skipped if code unchanged
scripts/check.sh full                         # Windows presets, then the same + gcc-debug on Linux (WSL),
                                              # then update.sh + bench with TCEC's 4 compilers (WSL Ubuntu-22.04)
./update.sh                                   # TCEC build: build/tcec/fork (CXX, FORK_ARCH; never native)
cmake --preset clang-release && cmake --build build/clang-release
ctest --test-dir build/clang-release -LE slow --output-on-failure
ctest --test-dir build/clang-release -L slow  # deep perft suites (minutes)
build/clang-release/fork bench                # prints nodes, signature, nps
build/clang-release/fork perft 5 [fen]        # also: divide, version, difftest
build/clang-release/fork_micro --compare bench/baselines/<file>
python -I bench/ab.py A/fork_micro B/fork_micro --a-variant baseline --a-commit <hash> \
  --b-variant NAME --b-commit <hash>[-dirty]  # interleaved A/B (use .venv python); identity-checked
bash bench/experiment.sh clang NAME           # build FORK_EXPERIMENT=NAME and compare
python -I tools/difftest/difftest.py --fork build/clang-release/fork   # vs python-chess
python -I tools/fuzz/run_fuzz.py --target build/clang-fuzz/fuzz_fen --corpus fuzz/corpus/fen
```

Presets: `{clang,gcc}-{debug,release,v3,avx512,nopext}`, `clang-fuzz`; PGO
runs via `scripts/build.sh clang-pgo gcc-pgo`. Primary platform is x86-64
Linux (WSL2 working copy `~/fork`); Windows is the second platform.

## Non-negotiables

1. **Never write constants, test data, perft counts, FENs or rules from
   memory.** Fetch the primary source, check it character by character, and
   cite it (in the test or in ORIGINALITY.md). Phase 1's perft position 6
   was typed from memory without its black bishop on g4; only the test
   caught it.
2. **Never claim something works without running it.** Report numbers from
   actual runs, and say when something was not run.
3. **Every functional change:** the full check passes (`scripts/check.sh full`),
   bench parity is checked, and the commit message states the bench node
   count (and the new signature if bench intentionally changed, with
   `tests/bench.ref` updated in the same commit).
4. **Say "unverified" when unsure** rather than guessing. Mark it in docs as
   UNVERIFIED.
5. **Read the relevant code and DESIGN.md section before editing.**
6. **Originality:** other engines' code, nets and engine-generated data are
   off-limits. Study ideas only, write Fork's own code, and log every
   reference in ORIGINALITY.md. Don't mirror Stockfish's file, class or
   function names: before introducing a new name, grep a shallow clone of
   Stockfish's source and flag any non-generic match to the owner first
   (DESIGN.md section 8).
7. **Performance claims** need the A/B harness (`bench/ab.py`), with bench
   unchanged (DESIGN.md section 7). Report any optimization that makes the code
   meaningfully harder to maintain before adopting it.
8. **The repo will be public, and TCEC builds Fork from source** (Category 4
   entry via the Cat 3+4 playoff; docs/kb/competition.md on branch kb). The
   whole history becomes public before the application, so:
   - never commit secrets, credentials, tokens, personal data or private
     files (HANDOFF.md and other session notes stay untracked);
   - keep the Linux build working from a clean clone: everything the build
     needs is committed or fetched by CMake with a pinned SHA-256, with no
     dependence on untracked files or local paths. `scripts/check.sh full`
     builds a copy of the working tree, untracked files included, so phase
     sign-offs also build a fresh `git clone` on Linux (`~/fork`, via
     `scripts/linux-setup.sh`).

## Workflow

- Each phase: spec in DESIGN.md, stop for the owner's approval, build, run
  every preset on Windows and Linux, commit per finished piece, summarize
  with exact results, stop.
- One heavy job at a time (perft_epd_full, difftest, fuzzing, matches); the
  machine is shared.
- Git: work on `main`; the KB lives on `kb`. Commit messages end with the
  attribution lines the session provides.
- Push policy (owner, 2026-10-24): commit locally as often as needed, but
  push to GitHub only at milestones, meaning each completed deliverable or
  when the owner asks, so CI (and its limited minutes) runs on meaningful
  checkpoints. Push `kb` with the same milestones; it never triggers CI.

### Phase-end checklist

Run at the end of every phase, after the owner's sign-off and before the
next phase begins. Report each item's result.

1. **All checks pass on both platforms and the TCEC toolchain:**
   `scripts/check.sh full`, `scripts/build.sh` (all presets + PGO) on
   Windows and in `~/fork` (a clean clone), the slow suites, and the Ubuntu
   22.04 build with TCEC's compilers (gcc 11.4, g++-12, clang 16/19; see
   DESIGN.md §5.1). Plus **fuzzing until coverage plateaus** (owner,
   2026-10-24): every fuzz target (`fuzz_fen`, `fuzz_moves`) for up to 1
   hour each, one after the other, stopping early once coverage has not
   grown for 20 minutes (`tools/fuzz/run_fuzz.py --max-seconds 3600
   --plateau-seconds 1200`), on a fresh `clang-fuzz` build. Report runs, coverage and whether each plateaued; then minimize
   the corpora and promote them to `seed-*` files (see "Fuzz corpus"
   below). Add a fuzz target for any new parser (e.g. `fuzz_uci`, Phase 2)
   under the same rule.
2. **Tag the release** as a known-good baseline: `git tag -a phase-N` on
   `main`, with the bench node count and signature in the tag message.
3. **Untracked reports** (`REVIEW-*.md`, `HANDOFF.md`, `MORNING.md` and
   the like): move anything worth keeping into `docs/history/phase-N/`
   (committed, so it becomes public: no personal data or secrets), and
   delete the rest.
4. **Branches and worktrees:** delete merged or abandoned ones
   (`git branch`, `git worktree list`); archive experiments worth keeping
   as tags first (e.g. `git tag archive/layout-exp layout-exp`).
5. **Stale build directories and caches:** remove experiment and one-off
   build dirs (`build/ab-*`, `build/overnight/`, sanitizer trial dirs, the
   same under `~/fork` and `~/fork-check` in WSL); keep `.cache/` test
   downloads and `~/fork-tools`.
6. **Docs:** update DESIGN.md (decisions log, phase status), ideas.md
   statuses, ORIGINALITY.md and the KB (branch `kb`); re-check every item
   marked UNVERIFIED and resolve or keep it with a reason.
7. **Memory notes:** review the saved memory files
   (Claude Code's memory directory for this project, under `~/.claude/projects/`) and update or delete
   anything outdated.
8. **Phase summary:** one page in `docs/history/phase-N/summary.md`: what
   was built, what was learned, what carries forward.
9. **Start the next phase in a fresh Claude Code session**, beginning from
   the summary and DESIGN.md.

**Fuzz corpus.** Only `fuzz/corpus/<target>/seed-*` files are committed; a
fuzz run's new inputs are git-ignored. After a long run, minimize with
libFuzzer into a directory that already holds the committed seeds
(`<target> -merge=1 <dir with seeds> <corpus dir>`): the hand-written seeds
(start position, ep and promotion cases, Kiwipete, a castling line) are
kept, and only inputs that add coverage are added. Commit those as
`seed-min-<hash>` files, so the committed seeds keep the coverage the run
reached.

## Gotchas

- LLVM-MinGW ships its own `g++.exe` (really clang): never pick compilers by
  bare name; the presets use `FORK_CLANG_CXX` / `FORK_GCC_CXX` from env.sh.
- MinGW GCC has no sanitizer runtimes; GCC sanitizers run on Linux only.
- Bash heredocs mangle `\n` in C++ string literals: use the Edit tool or a
  script file written with the Write tool.
- Microbenchmarks on this shared machine are intermittently noisy: never
  trust a single run; use `bench/ab.py`.
