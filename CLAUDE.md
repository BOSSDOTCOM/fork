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
- GitHub: **public** repo https://github.com/BOSSDOTCOM/fork (made public by
  the owner on 2026-10-26 after a history audit; remote `origin`;
  push main, kb, tcec-cutechess and tags). CI in `.github/workflows/ci.yml`
  is the full check (owner, 2026-10-28), parallel jobs with bench parity in
  each: every Linux preset (ASan/UBSan, TSan), MSan with an instrumented
  libc++, the fuzz seeds, PGO, the tuning build (FORK_TUNE), the Windows toolchains (LLVM-MinGW, WinLibs,
  pinned in `.github/ci/win-tools.sh`) with the gcc-debug full suite and the
  GCC smoke loop, TCEC's four compilers (ubuntu:22.04), and the slow suites
  as their own jobs (perft_epd_full takes about 2 hours). AVX-512 binaries
  run under Intel SDE on runners without it. It runs on pushes to main and
  audit-1 (docs-only pushes skipped) and on every pull request; a newer push
  cancels the older run. Hosted runners are free for the public repo.
  Branch protection on main requires every job green. Never push the local
  backup bundles (`*.bundle`).
- TCEC toolchain: WSL distro `Ubuntu-22.04` (gcc 11.4, g++-12, clang 16/19,
  CMake 3.22), set up by `scripts/tcec-toolchain-setup.sh`; runs as root.
  CMake must stay at a 3.22 floor and the code within libstdc++ 11's C++20.

## Commands (Git Bash; source the env in every shell)

```bash
. scripts/env.sh                              # toolchain on PATH (Windows) / compilers (Linux)
scripts/build.sh                              # all presets + PGO, summary table
scripts/build.sh clang-release gcc-debug      # chosen presets
scripts/check.sh quick                        # clang-release build + fast tests (the pre-commit hook, on the staged tree)
scripts/check.sh stop                         # Stop hook: clang-release, all non-slow tests; skipped if code unchanged
scripts/check.sh full                         # on demand (CI runs the full matrix): Windows presets + UCI smoke loop of every MinGW GCC preset,
                                              # then the same + gcc-debug on Linux (WSL),
                                              # then update.sh + bench with TCEC's 4 compilers (WSL Ubuntu-22.04)
scripts/uci-smoke.sh build/gcc-debug/fork.exe 50   # 50 starts of uci/isready/quit, all must exit 0
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

Presets: `{clang,gcc}-{debug,release,v3,avx512,nopext}`, `clang-fuzz`,
`{clang,gcc}-tsan` (Linux only); PGO
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
3. **Every functional change:** the full check passes (the CI matrix on the
   pushed commit, or `scripts/check.sh full` locally),
   bench parity is checked, and the commit message states the bench node
   count (and the new signature if bench intentionally changed, with
   `tests/bench.ref` updated in the same commit).
4. **Say "unverified" when unsure** rather than guessing. Mark it in docs as
   UNVERIFIED.
5. **Read the relevant code and DESIGN.md section before editing.**
6. **Originality:** other engines' code, nets and engine-generated data are
   off-limits. Study ideas only, write Fork's own code, and log every
   reference in ORIGINALITY.md. Don't mirror Stockfish's file, class or
   function names: before introducing a new name, have it checked against
   Stockfish's, Ethereal's, Berserk's and Weiss's source (exact and case-
   and separator-insensitive) and flag any non-generic match to the owner
   first (DESIGN.md section 8). The implementing session never runs that
   check itself: a separate research subagent shallow-clones the engines
   into a temporary folder, reports only "match / no match" per name
   (never code lines), and deletes the clones immediately. No engine
   source, copied file or identifier dump is kept on this machine.
   **Every search constant needs a recorded justification** (reasoning,
   quick sweep or measurement, in the phase spec's "Search constants"
   table), and the originality-checker screens new or changed constants
   against known engines before the commit: model memory can reproduce
   famous values without any source being opened (owner, 2026-10-25).
7. **Performance claims** need the A/B harness (`bench/ab.py`), with bench
   unchanged (DESIGN.md section 7). Report any optimization that makes the code
   meaningfully harder to maintain before adopting it.
8. **The repo is public (since 2026-10-26), and TCEC builds Fork from
   source** (Category 4 entry via the Cat 3+4 playoff; docs/kb/competition.md
   on branch kb). Every push is published at once, history included, so
   **nothing personal, nothing secret and no other engine's code may ever be
   committed** (owner, 2026-10-27; a post-publication audit of every branch,
   tag and commit found none):
   - never commit secrets, credentials, tokens, personal data or private
     files (HANDOFF.md and other session notes stay untracked);
   - no user-name paths in files, logs or messages: write `~/`,
     `/mnt/c/Users/<user>/` or paths relative to the repository (a tool
     that copies an option or path into a committed file must write `~`
     for the home folder, as `tools/sprt.sh` does);
   - no other engine's source, snippets, nets or engine-generated data
     (non-negotiable 6), except vendored libraries the owner approved
     (Fathom), with their licence and lineage in ORIGINALITY.md;
   - before the first push of a branch, scan what it adds for the user
     name, home paths, the personal email and secrets;
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
  when the owner asks, so CI runs on meaningful checkpoints (the full
  matrix takes about 2 hours of wall time and shares runners with the SPRT
  shards). Push `kb` with the same milestones; it never triggers CI.

### Phase-end checklist

Run at the end of every phase, after the owner's sign-off and before the
next phase begins. Report each item's result.

1. **All checks pass on both platforms and the TCEC toolchain:**
   `scripts/check.sh full`, `scripts/build.sh` (all presets + PGO) on
   Windows and in `~/fork` (a clean clone), the slow suites, and the Ubuntu
   22.04 build with TCEC's compilers (gcc 11.4, g++-12, clang 16/19; see
   DESIGN.md §5.1). Plus the **full gcc-debug suite on Windows**
   (`scripts/build.sh gcc-debug`, every non-slow test; owner, 2026-10-24:
   `check.sh full` only smoke-starts the Windows GCC engines, and a Windows
   gcc-debug crash once went unseen for a whole phase). Plus **fuzz each
   target whose exercised code changed since its last clean run, with the
   coverage-plateau rule** (owner, 2026-10-24; check with `git diff` from
   that run's commit over the target's source and the code it calls, e.g.
   `src/core` for `fuzz_fen` and `fuzz_moves`, `src/uci` and `src/search`
   too for `fuzz_uci`): up to 1 hour each, one after the other, stopping
   early once coverage has not grown for 20 minutes
   (`tools/fuzz/run_fuzz.py --max-seconds 3600 --plateau-seconds 1200`), on
   a fresh `clang-fuzz` build. Report which targets ran or were skipped and
   why, with runs, coverage and whether each plateaued. Then minimize
   **all** corpora and promote them to `seed-*` files (see "Fuzz corpus"
   below). Add a fuzz target for any new parser under the same rule.
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
   marked UNVERIFIED and resolve or keep it with a reason. Then **merge
   `main` into `kb`** (in `../fork-kb`; on a conflict in `docs/DESIGN.md`
   take main's: kb's copy is an old one, not maintained there) and push both branches, so
   the KB never drifts from the code it describes.
7. **Memory notes:** review the saved memory files
   (Claude Code's memory directory for this project, under `~/.claude/projects/`) and update or delete
   anything outdated.
8. **Re-validation** (owner, 2026-10-25; DESIGN.md §5.2, Quality
   control 6), at the phase ends that call for it, before the summary:
   - **end of Phase 3:** one removal round: each search feature switched
     off in turn and SPRTed on non-regression bounds [-3, 0]; a feature
     whose removal costs nothing is simplified away; every result goes in
     the SPRT log;
   - **end of Phase 4 (after the network):** the full re-validation of
     every search feature, plus a retune of every eval-dependent margin;
   - search features keep their switches in the code until the Phase 4
     re-validation is done. No removal tests at individual milestones.
9. **Phase summary:** one page in `docs/history/phase-N/summary.md`: what
   was built, what was learned, what carries forward.
10. **Start the next phase in a fresh Claude Code session**, beginning from
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
