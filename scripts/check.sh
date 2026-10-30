#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Fork's single source of truth for "is the tree healthy?", shared by the
# Claude Code hooks (.claude/settings.json) and the git pre-commit hook
# (scripts/hooks/pre-commit).
#
#   scripts/check.sh quick   clang-release build + fast tests (post-edit hook),
#                            plus the tooling's Python unit tests
#   scripts/check.sh stop    clang-release build + every non-slow test,
#                            including bench parity and no_alloc; this
#                            platform only (Stop hook). Skipped when the code
#                            is unchanged since a passing stop or full run.
#   scripts/check.sh full    clang-release, clang-debug (ASan+UBSan) and
#                            gcc-release: build + every non-slow test,
#                            including bench parity (pre-commit, sign-offs),
#                            plus the tooling's tests (the Python suites and
#                            the dry runs of tools/sprt.sh and run_shard.sh).
#                            On Linux also gcc-debug (GCC ASan+UBSan). On
#                            Windows also a UCI start-up smoke loop (50 runs)
#                            of every MinGW GCC preset's engine, then the
#                            Linux check (below).
#
# Both platforms on every full check: on Windows, `full` copies the working
# tree exactly as it is (tracked and untracked, non-ignored files) into
# ~/fork-check inside WSL (distro FORK_WSL_DISTRO, default Ubuntu; the
# owner's ~/fork copy is never touched) and runs the native Linux check there.
# A Linux failure, or WSL being unavailable, fails the whole check.
# FORK_SKIP_LINUX=1 skips the Linux part with a warning and records no pass.
#
# TCEC toolchain leg (also part of every full check on Windows): the same
# tree is copied into a second WSL distro running Ubuntu 22.04 with TCEC's
# compilers (FORK_TCEC_DISTRO, default Ubuntu-22.04; set up once with
# scripts/tcec-toolchain-setup.sh), built there with update.sh using gcc 11.4,
# g++-12, clang 16 and clang 19 in turn, and each binary's bench and perft
# bench must match the evaluator's references (.github/ci/bench-parity.sh, as
# CI: tests/bench-<net>.ref for a network). FORK_SKIP_TCEC=1 skips it with a warning and records
# no pass. Run directly on Linux, `full` cannot reach the TCEC distro and
# records no pass either.
#
# Passing `stop` and `full` runs are remembered by a fingerprint of the
# content of every source, test and build file plus the check scripts
# (tracked and untracked, non-ignored; the paths in scripts/code-paths.txt,
# which the pre-commit hook's filter reads too), not of the commit:
# docs-only commits and doc edits never trigger a rerun, and a long
# background job (MSan, perft, fuzzing) is never competed with unless code
# actually changed.
#
# FORK_CHECK_LOCK (default build/.check.lock) and FORK_CHECK_DIR_NAME (the
# WSL folder of the Linux leg, default fork-check) let the pre-commit hook
# run the check on its own copy of the commit while sharing the lock.
# Exit status is non-zero on any failure; the failure output goes to stderr.
set -uo pipefail
cd "$(dirname "$0")/.."
. scripts/env.sh

mode=${1:-quick}
mapfile -t code_paths < <(sed -e 's/#.*//' -e 's/[[:space:]]*$//' scripts/code-paths.txt | grep .)
[ "${#code_paths[@]}" -gt 0 ] || { echo "fork check: scripts/code-paths.txt lists no paths" >&2; exit 1; }
log=$(mktemp)

# One check at a time (owner, 2026-10-26): a check run beside another one
# (the Stop hook during a pre-commit full check, say) competes for CPU and
# memory, and the timing and Hash tests then fail for the wrong reason. The
# lock is a directory holding the owner's PID, cleared when that process is
# gone. `full` waits for it; the hook modes wait within their hooks' time
# limits (stop 10 min, quick 4 min), then skip with a warning and record no
# pass. The internal modes (the WSL legs and full-native) run under the
# lock of the full check that started them and take none: inside WSL the
# Windows holder's PID does not exist, so they would take it for a stale
# lock and remove it while the full check still runs.
lock=${FORK_CHECK_LOCK:-build/.check.lock}
case "$mode" in
  full) wait_s=-1 ;;
  stop) wait_s=600 ;;
  linux-sync | tcec-sync | full-native) wait_s=none ;;
  *) wait_s=240 ;;
esac
mkdir -p build "$(dirname "$lock")"
if [ "$wait_s" = none ]; then
  trap 'rm -f "$log"' EXIT
else
  waited=0
  until mkdir "$lock" 2>/dev/null; do
    holder=$(cat "$lock/pid" 2>/dev/null)
    if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then
      rm -rf "$lock"  # the holder is gone: a stale lock
      continue
    fi
    if [ "$wait_s" -ge 0 ] && [ "$waited" -ge "$wait_s" ]; then
      echo "fork check $mode: skipped, another check (PID ${holder:-unknown}) still running after ${waited} s; no pass recorded" >&2
      rm -f "$log"
      exit 0
    fi
    sleep 5
    waited=$((waited + 5))
  done
  echo $$ >"$lock/pid"
  trap 'rm -f "$log"; rm -rf "$lock"' EXIT
fi
# A signal (a hook's `timeout`, Ctrl-C) exits through the EXIT trap, so the
# lock is released at once (bash skips the EXIT trap on an untrapped
# SIGTERM: checked with Git Bash, 2026-10-27).
trap 'exit 143' TERM
trap 'exit 130' INT

fail() {
  {
    echo "FORK CHECK FAILED ($mode): $1"
    tail -n 60 "$log"
  } >&2
  exit 1
}

# Content hash of the code: path and blob hash of every existing file under
# code_paths (a deleted file drops out of the list, which changes the hash).
fingerprint() {
  git ls-files -co --exclude-standard -- "${code_paths[@]}" | sort -u |
    while read -r f; do [ -f "$f" ] && echo "$f"; done >"$log.paths"
  git hash-object --stdin-paths <"$log.paths" >"$log.blobs"
  paste "$log.paths" "$log.blobs" | sha1sum | cut -d' ' -f1
  rm -f "$log.paths" "$log.blobs"
}

stamp_matches() {  # fingerprint, stamp files...
  local fp=$1 s
  shift
  for s in "$@"; do
    [ -f "$s" ] && [ "$(cat "$s")" = "$fp" ] && return 0
  done
  return 1
}

# no_alloc (the counting-allocator test, fork_alloc_test) must run and pass in
# every preset checked here; build_and_test fails if its "Passed" line is
# missing, so it can never be skipped silently. Its only sanctioned exclusions
# are TSan, MSan and valgrind runs (Linux sign-off, not part of this script):
# its replacement global operator new/delete collides with those tools' own
# (a link error under TSan/MSan; under valgrind the test's self-check reports
# that the counter is not in effect). ASan/UBSan builds run it. See
# .claude/rules/testing.md.
# Build parallelism is capped so a full check fits in this machine's 15 GB
# beside other work (2026-10-28: an uncapped check, about 14 compile jobs
# and 12 LTO jobs in the 7.5 GB WSL VM, ran the machine out of memory):
# 6 jobs on Windows, 4 inside WSL (its VM gets half the RAM). FORK_CHECK_JOBS
# overrides both. The legs (this platform's presets, then the Linux leg, then
# the TCEC leg) run one after another, never at once, and the lock keeps a
# second check from starting beside them.
check_jobs() {
  if [ -n "${FORK_CHECK_JOBS:-}" ]; then echo "$FORK_CHECK_JOBS"
  elif [ "$(uname -s)" = Linux ]; then echo 4
  else echo 6
  fi
}

# Every check configures with the tree's default evaluator and network:
# without -U a cached FORK_EVALUATOR or FORK_NET outlives a change of the
# default (B0 became the default on 2026-10-29, and the local check builds
# went on testing the bootstrap evaluation). A reconfigure that changes
# nothing rebuilds nothing.
build_and_test() {  # preset, ctest filter args...
  local preset=$1 out
  shift
  cmake --preset "$preset" -U FORK_EVALUATOR -U FORK_NET >>"$log" 2>&1 || fail "configure $preset"
  cmake --build "build/$preset" -j "$(check_jobs)" >>"$log" 2>&1 || fail "build $preset"
  out=$(ctest --test-dir "build/$preset" --output-on-failure "$@" 2>&1)
  local status=$?
  echo "$out" >>"$log"
  [ $status -eq 0 ] || fail "tests $preset"
  # Skipped cases and notes (retried timing attempts) are not failures, but
  # they stay visible (owner, 2026-10-26): CTest hides a passing test's output.
  local last="build/$preset/Testing/Temporary/LastTest.log"
  if [ -f "$last" ] && grep -qE '^(SKIP|NOTE) ' "$last"; then
    grep -E '^(SKIP|NOTE) ' "$last" | sed "s/^/fork check $mode ($preset): /" >&2
  fi
  echo "$out" | grep -qE 'Test +#[0-9]+: no_alloc \.+ +Passed' || fail "no_alloc did not run in $preset"
}

# The tooling's own tests (audit-1 U-15): standard-library Python suites
# (sprt_merge and the book permutation, the evolve harness, pgn_summary),
# plus the datagen openings tool where python-chess is installed, about 5 s; with "all", also the dry runs of tools/sprt.sh and
# tools/cloud/run_shard.sh with fake fastchess binaries (about 30 s).
tool_tests() {  # python | all
  local py="" c
  for c in .venv/Scripts/python.exe .venv/bin/python python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c pass >/dev/null 2>&1; then py=$c; break; fi
  done
  [ -n "$py" ] || fail "no Python for the tool tests"
  "$py" -I -B -m unittest discover -s tools/cloud -p 'test_*.py' >>"$log" 2>&1 || fail "tool tests: tools/cloud"
  "$py" -I -B -m unittest discover -s tools/evolve -p 'test_*.py' >>"$log" 2>&1 || fail "tool tests: tools/evolve"
  "$py" -I -B -m unittest discover -s tools -p 'test_pgn_summary.py' >>"$log" 2>&1 || fail "tool tests: tools/pgn_summary.py"
  # tools/datagen and tools/nnue need python-chess and zstandard (the
  # repository's .venv); the log says when they are missing and the suites are skipped.
  if "$py" -I -c 'import chess, zstandard' >/dev/null 2>&1; then
    "$py" -I -B -m unittest discover -s tools/datagen -p 'test_*.py' >>"$log" 2>&1 || fail "tool tests: tools/datagen"
    "$py" -I -B -m unittest discover -s tools/nnue -p 'test_*.py' >>"$log" 2>&1 || fail "tool tests: tools/nnue"
  else
    echo "tool tests: tools/datagen skipped (no python-chess or zstandard in $py)" >>"$log"
  fi
  bash scripts/update-test.sh >>"$log" 2>&1 || fail "tool tests: scripts/update-test.sh (update.sh clone mode)"
  [ "$1" = all ] || return 0
  bash tools/test_sprt.sh >>"$log" 2>&1 || fail "tool tests: tools/test_sprt.sh"
  case $py in */*) py=$(cd "$(dirname "$py")" && pwd)/$(basename "$py") ;; *) py=$(command -v "$py") ;; esac
  PYTHON=$py bash tools/cloud/test_run_shard.sh >>"$log" 2>&1 || fail "tool tests: tools/cloud/test_run_shard.sh"
  # The cloud safeguards (owner, 2026-10-30): the spot quota check, the
  # cleanup of instances past their limit, a simulated spot interruption,
  # the data-generation fleet request.
  local t
  for t in test_spot_quota test_aws_cleanup test_spot_watch test_aws_spot_datagen test_cost_guard; do
    PYTHON=$py bash "tools/cloud/$t.sh" >>"$log" 2>&1 || fail "tool tests: tools/cloud/$t.sh"
  done
}

native_full() {
  local presets=(clang-release clang-debug gcc-release)
  [ "$(uname -s)" = Linux ] && presets+=(gcc-debug)
  for preset in "${presets[@]}"; do
    build_and_test "$preset" -LE slow
  done
  [ "$(uname -s)" = Linux ] || windows_gcc_smoke
  tool_tests all
  echo "${presets[*]}"
}

# Windows only (owner, 2026-10-24): every MinGW GCC preset's engine must
# start cleanly in UCI mode, 50 times (scripts/uci-smoke.sh). Builds only the
# fork target of each; the full gcc-debug suite runs at each phase end.
windows_gcc_smoke() {
  local preset
  for preset in gcc-debug gcc-release gcc-v3 gcc-avx512 gcc-nopext; do
    cmake --preset "$preset" -U FORK_EVALUATOR -U FORK_NET >>"$log" 2>&1 || fail "configure $preset"
    cmake --build "build/$preset" --target fork -j "$(check_jobs)" >>"$log" 2>&1 || fail "build $preset (fork)"
    scripts/uci-smoke.sh "build/$preset/fork.exe" 50 >>"$log" 2>&1 || fail "UCI start-up smoke loop, $preset"
  done
}

# Windows side: copy the working tree into WSL and run the Linux check there.
linux_leg() {
  local distro=${FORK_WSL_DISTRO:-Ubuntu} list=build/.linux-check-files src name=${FORK_CHECK_DIR_NAME:-fork-check}
  case $name in '' | *[!A-Za-z0-9._-]*) fail "FORK_CHECK_DIR_NAME must be a plain folder name" ;; esac
  command -v wsl.exe >/dev/null || fail "wsl.exe not found (set FORK_SKIP_LINUX=1 to skip the Linux check)"
  git ls-files -co --exclude-standard >"$list" || fail "listing the working tree for Linux"
  src=$(MSYS_NO_PATHCONV=1 wsl.exe -d "$distro" -e wslpath -a "$(pwd -W)" 2>>"$log" | tr -d '\r') ||
    fail "WSL distro $distro unavailable (set FORK_SKIP_LINUX=1 to skip the Linux check)"
  [ -n "$src" ] || fail "WSL distro $distro unavailable (set FORK_SKIP_LINUX=1 to skip the Linux check)"
  MSYS_NO_PATHCONV=1 wsl.exe -d "$distro" -e bash "$src/scripts/check.sh" linux-sync "$src" "$name" >>"$log" 2>&1 ||
    fail "Linux check in WSL ($distro, ~/$name)"
}

# Windows side: copy the working tree into the Ubuntu 22.04 distro and build
# it there with TCEC's compilers.
tcec_leg() {
  local distro=${FORK_TCEC_DISTRO:-Ubuntu-22.04} list=build/.linux-check-files src
  git ls-files -co --exclude-standard >"$list" || fail "listing the working tree for the TCEC build"
  src=$(MSYS_NO_PATHCONV=1 wsl.exe -d "$distro" -u root -e wslpath -a "$(pwd -W)" 2>>"$log" | tr -d '\r') ||
    fail "WSL distro $distro unavailable (see scripts/tcec-toolchain-setup.sh; FORK_SKIP_TCEC=1 to skip)"
  [ -n "$src" ] || fail "WSL distro $distro unavailable (see scripts/tcec-toolchain-setup.sh; FORK_SKIP_TCEC=1 to skip)"
  MSYS_NO_PATHCONV=1 wsl.exe -d "$distro" -u root -e bash "$src/scripts/check.sh" tcec-sync "$src" >>"$log" 2>&1 ||
    fail "TCEC toolchain build in WSL ($distro, ~/fork-tcec)"
}

case "$mode" in
  tcec-sync)  # internal, run inside the Ubuntu 22.04 distro by tcec_leg: $2 = Windows tree as a /mnt path
    src=$2 dst=$HOME/fork-tcec
    rm -rf "$dst" && mkdir -p "$dst"
    (cd "$src" && tar -cf - -T build/.linux-check-files) | (cd "$dst" && tar -xf -) ||
      { echo "copying the tree to $dst failed" >&2; exit 1; }
    cd "$dst"
    # compiler, and the version its `fork version` line must report
    for pair in "g++:gcc 11.4." "g++-12:gcc 12." "clang++-16:clang 16." "clang++-19:clang 19."; do
      cxx=${pair%%:*} want=${pair#*:}
      echo "== TCEC build with $cxx"
      out=$(CXX=$cxx FORK_JOBS=$(check_jobs) bash ./update.sh 2>&1) || { echo "$out"; echo "update.sh failed with $cxx" >&2; exit 1; }
      bin=$(echo "$out" | tail -n 1)
      echo "$out" | grep -q "^compiler $want" ||
        { echo "$out"; echo "$cxx is not the expected $want" >&2; exit 1; }
      echo "$out" | grep -q -i 'LTO not supported' && echo "note: $cxx built without LTO"
      # The evaluator's own reference, as CI's TCEC job checks it (bench.ref
      # for bootstrap, bench-<net>.ref for a network; perft bench too).
      bash .github/ci/bench-parity.sh "$bin" || { echo "bench parity failed with $cxx" >&2; exit 1; }
      echo "bench parity ok with $cxx"
    done
    ;;
  linux-sync)  # internal, run inside WSL by linux_leg: $2 = Windows tree as a /mnt path, $3 = folder name
    src=$2 dst=$HOME/${3:-fork-check}
    mkdir -p "$dst"
    # Fresh source tree each time, so deleted files disappear; build/ and the
    # downloaded test data in .cache/ persist, and tar keeps the mtimes, so
    # only changed files recompile.
    find "$dst" -mindepth 1 -maxdepth 1 ! -name build ! -name .cache -exec rm -rf {} +
    # The kept builds are only valid for the tree they were built from: two
    # trees (a git worktree beside the main one) differ in file times, so a
    # file older in the new tree would not be recompiled and the check would
    # test a stale object (it did, 2026-10-27). A new source tree starts the
    # builds afresh.
    if [ "$(cat "$dst/build/.source-tree" 2>/dev/null)" != "$src" ]; then
      rm -rf "$dst/build"
      mkdir -p "$dst/build"
      echo "$src" >"$dst/build/.source-tree"
    fi
    (cd "$src" && tar -cf - -T build/.linux-check-files) | (cd "$dst" && tar -xf -) ||
      { echo "copying the tree to $dst failed" >&2; exit 1; }
    exec bash "$dst/scripts/check.sh" full-native
    ;;
  full-native)  # internal: this platform's presets only, no stamp
    presets=$(native_full) || exit 1
    echo "fork check full-native ($(uname -s)): ok ($presets)"
    ;;
  quick)
    build_and_test clang-release -R '^(magics|fen|zobrist_ep|perft_edge|pseudo_legal|no_alloc|bench_parity)$'
    tool_tests python
    echo "fork check quick: ok (with the tooling's Python tests)"
    ;;
  stop)
    mkdir -p build
    fp=$(fingerprint)
    if stamp_matches "$fp" build/.check-stop-pass build/.check-full-pass; then
      echo "fork check stop: skipped (code unchanged since last pass)"
      exit 0
    fi
    build_and_test clang-release -LE slow
    echo "$fp" >build/.check-stop-pass
    echo "fork check stop: ok (clang-release, all non-slow tests, bench parity, no_alloc)"
    ;;
  full)
    mkdir -p build
    stamp=build/.check-full-pass
    fp=$(fingerprint)
    if stamp_matches "$fp" "$stamp"; then
      echo "fork check full: ok (unchanged since last pass)"
      exit 0
    fi
    presets=$(native_full) || exit 1
    platforms="$(uname -s): $presets"
    [ "$(uname -s)" = Linux ] || platforms="$platforms, UCI smoke x50 for gcc-{debug,release,v3,avx512,nopext}"
    if [ "$(uname -s)" != Linux ]; then
      if [ "${FORK_SKIP_LINUX:-0}" = 1 ]; then
        echo "fork check full: WARNING: Linux check SKIPPED (FORK_SKIP_LINUX=1); no pass recorded" >&2
        echo "fork check full: ok on $platforms only; Linux SKIPPED"
        exit 0
      fi
      linux_leg
      platforms="$platforms; Linux (WSL): clang-release clang-debug gcc-release gcc-debug"
      if [ "${FORK_SKIP_TCEC:-0}" = 1 ]; then
        echo "fork check full: WARNING: TCEC toolchain build SKIPPED (FORK_SKIP_TCEC=1); no pass recorded" >&2
        echo "fork check full: ok on $platforms; TCEC toolchain SKIPPED"
        exit 0
      fi
      tcec_leg
      platforms="$platforms; TCEC toolchain (Ubuntu 22.04): gcc 11.4, g++-12, clang 16, clang 19"
    else
      echo "fork check full: WARNING: TCEC toolchain build runs from Windows only; no pass recorded" >&2
      echo "fork check full: ok on $platforms; TCEC toolchain not run"
      exit 0
    fi
    echo "$fp" >"$stamp"
    echo "fork check full: ok ($platforms; bench parity and the tooling's tests included)"
    ;;
  *)
    echo "usage: scripts/check.sh quick|stop|full" >&2
    exit 2
    ;;
esac
