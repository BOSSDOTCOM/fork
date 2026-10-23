#!/usr/bin/env bash
# Fork's single source of truth for "is the tree healthy?", shared by the
# Claude Code hooks (.claude/settings.json) and the git pre-commit hook
# (scripts/hooks/pre-commit).
#
#   scripts/check.sh quick   clang-release build + fast tests (post-edit hook)
#   scripts/check.sh full    clang-release, clang-debug (ASan+UBSan) and
#                            gcc-release: build + every non-slow test,
#                            including bench parity (Stop hook, pre-commit)
#
# A passing `full` run is remembered by a fingerprint of all code (tracked
# changes and untracked files under the code directories), so repeating it on
# an unchanged tree is instant. Exit status is non-zero on any failure; the
# failure output goes to stderr.
set -uo pipefail
cd "$(dirname "$0")/.."
. scripts/env.sh

mode=${1:-quick}
code_paths=(src tests bench fuzz tools/magic_seeds.cpp cmake CMakeLists.txt CMakePresets.json)
log=$(mktemp)
trap 'rm -f "$log"' EXIT

fail() {
  {
    echo "FORK CHECK FAILED ($mode): $1"
    tail -n 60 "$log"
  } >&2
  exit 1
}

fingerprint() {
  {
    git rev-parse HEAD 2>/dev/null
    git diff HEAD -- "${code_paths[@]}" 2>/dev/null
    git ls-files --others --exclude-standard -- "${code_paths[@]}" 2>/dev/null |
      while read -r f; do echo "$f"; cat "$f"; done
  } | sha1sum | cut -d' ' -f1
}

build_and_test() {  # preset, ctest filter args...
  local preset=$1
  shift
  if [ ! -f "build/$preset/build.ninja" ]; then
    cmake --preset "$preset" >>"$log" 2>&1 || fail "configure $preset"
  fi
  cmake --build "build/$preset" >>"$log" 2>&1 || fail "build $preset"
  ctest --test-dir "build/$preset" --output-on-failure "$@" >>"$log" 2>&1 || fail "tests $preset"
}

case "$mode" in
  quick)
    build_and_test clang-release -R '^(magics|fen|zobrist_ep|perft_edge|pseudo_legal|no_alloc|bench_parity)$'
    echo "fork check quick: ok"
    ;;
  full)
    mkdir -p build
    stamp=build/.check-full-pass
    fp=$(fingerprint)
    if [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$fp" ]; then
      echo "fork check full: ok (unchanged since last pass)"
      exit 0
    fi
    for preset in clang-release clang-debug gcc-release; do
      build_and_test "$preset" -LE slow
    done
    echo "$fp" >"$stamp"
    echo "fork check full: ok (clang-release, clang-debug, gcc-release; bench parity included)"
    ;;
  *)
    echo "usage: scripts/check.sh quick|full" >&2
    exit 2
    ;;
esac
