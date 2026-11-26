# Zugzwang-guard positions

`find_guard_positions.py` finds king-and-pawn positions for the search test
of the null move's zugzwang guard (no null move for a side with only pawns,
`src/search/searcher.cpp`). Audit-1's mutant M18b removes the guard; the
patch `tests/mutants/m18b-null-zugzwang-guard.patch` makes that mutant and is
applied only on demand: no build uses it.

The script draws random positions from a fixed seed (default 20261125),
keeps those whose saving moves the local Syzygy tables single out, drops
those the mutant still solves with the base configuration, and checks the
rest with the three configurations on both engines. See the script's
docstring for the exact rules. Every position it evaluates is logged with its
random index, so a run can be replayed and audited.

## Rerun

From Git Bash at the repository root, with the toolchain on PATH
(`. scripts/env.sh`):

```bash
# The guarded engine (a FORK_TUNE build: every parameter is a UCI option).
cmake --preset clang-release -B build/guard-intact -DFORK_TUNE=ON
cmake --build build/guard-intact --target fork

# The mutant: apply the patch, build, and revert the source at once.
git apply tests/mutants/m18b-null-zugzwang-guard.patch
cmake --preset clang-release -B build/guard-m18b -DFORK_TUNE=ON
cmake --build build/guard-m18b --target fork
git apply -R tests/mutants/m18b-null-zugzwang-guard.patch
git diff --exit-code src/        # nothing left of the mutant

# The search (Windows paths shown; on Linux give the tables' own folder).
.venv/Scripts/python.exe -I tools/guard_positions/find_guard_positions.py \
  --tables '\\wsl.localhost\<distro>\home\<user>\fork-tools\syzygy\3-4-5' \
  --intact build/guard-intact/fork.exe --mutant build/guard-m18b/fork.exe \
  --out guard-positions.jsonl --seed 20261125 --want 6 --max-minutes 120
```

`--nodes-bar` (owner, 2026-11-25) also holds each hard failure to a node
budget B, twice the guarded engine's worst found-and-kept nodes over the
three configurations, rounded up to 1,000: the guarded engine's bestmove at
`go nodes B` must be a saving move in every configuration, and the mutant's
at `go nodes 4B` in none (its moves at B and 2B are logged). The second
search used `--seed 20261126 --nodes-bar --want 1 --max-minutes 60`.

The test's positions (tests/test_search.cpp): P1 from the first search, with
its budget set by hand to 25,000 nodes (2.3x the worst guarded need; the
mutant still errs at 100,000 but finds the move at 120,000 with the base
configuration), and P7 from the second, budget 155,000 (the bar's B).

Requirements: python-chess (the repository's `.venv`), the Syzygy 3-4-5 WDL
tables, and `git` (the configurations' parameters are read from their
commits' `src/tune/params.hpp`). At most `--jobs` (default 3) engine
processes run at once.

To recheck chosen positions without a search, give each with `--check FEN`
(repeatable; `--out` still names the log): the script prints the tables'
saving moves and all twelve runs (both engines, the three configurations,
UseImprovingLmp on and off), one engine process at a time, and exits
non-zero unless the guarded engine finds and keeps a saving move with
UseImprovingLmp on in every configuration.
