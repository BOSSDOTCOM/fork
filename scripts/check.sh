#!/usr/bin/env bash
# Fork's single source of truth for "is the tree healthy?", shared by the
# Claude Code hooks (.claude/settings.json) and the git pre-commit hook
# (scripts/hooks/pre-commit).
#
#   scripts/check.sh quick   clang-release build + fast tests (post-edit hook)
#   scripts/check.sh stop    clang-release build + every non-slow test,
#                            including bench parity and no_alloc; this
#                            platform only (Stop hook). Skipped when the code
#                            is unchanged since a passing stop or full run.
#   scripts/check.sh full    clang-release, clang-debug (ASan+UBSan) and
#                            gcc-release: build + every non-slow test,
#                            including bench parity (pre-commit, sign-offs).
#                            On Linux also gcc-debug (GCC ASan+UBSan). On
#                            Windows it then runs the Linux check too (below).
#
# Both platforms on every full check: on Windows, `full` copies the working
# tree exactly as it is (tracked and untracked, non-ignored files) into
# ~/fork-check inside WSL (distro FORK_WSL_DISTRO, default Ubuntu; the
# owner's ~/fork copy is never touched) and runs the native Linux check there.
# A Linux failure, or WSL being unavailable, fails the whole check.
# FORK_SKIP_LINUX=1 skips the Linux part with a warning and records no pass.
#
# Passing `stop` and `full` runs are remembered by a fingerprint of the
# content of every source, test and build file plus the check scripts
# (tracked and untracked, non-ignored), not of the commit: docs-only commits
# and doc edits never trigger a rerun, and a long background job (MSan,
# perft, fuzzing) is never competed with unless code actually changed.
# Exit status is non-zero on any failure; the failure output goes to stderr.
set -uo pipefail
cd "$(dirname "$0")/.."
. scripts/env.sh

mode=${1:-quick}
code_paths=(src tests bench fuzz tools/magic_seeds.cpp cmake CMakeLists.txt CMakePresets.json
            scripts/check.sh scripts/env.sh)
log=$(mktemp)
trap 'rm -f "$log"' EXIT

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
build_and_test() {  # preset, ctest filter args...
  local preset=$1 out
  shift
  if [ ! -f "build/$preset/build.ninja" ]; then
    cmake --preset "$preset" >>"$log" 2>&1 || fail "configure $preset"
  fi
  cmake --build "build/$preset" >>"$log" 2>&1 || fail "build $preset"
  out=$(ctest --test-dir "build/$preset" --output-on-failure "$@" 2>&1)
  local status=$?
  echo "$out" >>"$log"
  [ $status -eq 0 ] || fail "tests $preset"
  echo "$out" | grep -qE 'Test +#[0-9]+: no_alloc \.+ +Passed' || fail "no_alloc did not run in $preset"
}

native_full() {
  local presets=(clang-release clang-debug gcc-release)
  [ "$(uname -s)" = Linux ] && presets+=(gcc-debug)
  for preset in "${presets[@]}"; do
    build_and_test "$preset" -LE slow
  done
  echo "${presets[*]}"
}

# Windows side: copy the working tree into WSL and run the Linux check there.
linux_leg() {
  local distro=${FORK_WSL_DISTRO:-Ubuntu} list=build/.linux-check-files src
  command -v wsl.exe >/dev/null || fail "wsl.exe not found (set FORK_SKIP_LINUX=1 to skip the Linux check)"
  git ls-files -co --exclude-standard >"$list" || fail "listing the working tree for Linux"
  src=$(MSYS_NO_PATHCONV=1 wsl.exe -d "$distro" -e wslpath -a "$(pwd -W)" 2>>"$log" | tr -d '\r') ||
    fail "WSL distro $distro unavailable (set FORK_SKIP_LINUX=1 to skip the Linux check)"
  [ -n "$src" ] || fail "WSL distro $distro unavailable (set FORK_SKIP_LINUX=1 to skip the Linux check)"
  MSYS_NO_PATHCONV=1 wsl.exe -d "$distro" -e bash "$src/scripts/check.sh" linux-sync "$src" >>"$log" 2>&1 ||
    fail "Linux check in WSL ($distro, ~/fork-check)"
}

case "$mode" in
  linux-sync)  # internal, run inside WSL by linux_leg: $2 = Windows tree as a /mnt path
    src=$2 dst=$HOME/fork-check
    mkdir -p "$dst"
    # Fresh source tree each time, so deleted files disappear; build/ and the
    # downloaded test data in .cache/ persist, and tar keeps the mtimes, so
    # only changed files recompile.
    find "$dst" -mindepth 1 -maxdepth 1 ! -name build ! -name .cache -exec rm -rf {} +
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
    echo "fork check quick: ok"
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
    if [ "$(uname -s)" != Linux ]; then
      if [ "${FORK_SKIP_LINUX:-0}" = 1 ]; then
        echo "fork check full: WARNING: Linux check SKIPPED (FORK_SKIP_LINUX=1); no pass recorded" >&2
        echo "fork check full: ok on $platforms only; Linux SKIPPED"
        exit 0
      fi
      linux_leg
      platforms="$platforms; Linux (WSL): clang-release clang-debug gcc-release gcc-debug"
    fi
    echo "$fp" >"$stamp"
    echo "fork check full: ok ($platforms; bench parity included)"
    ;;
  *)
    echo "usage: scripts/check.sh quick|stop|full" >&2
    exit 2
    ;;
esac
