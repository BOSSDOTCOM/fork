#!/usr/bin/env bash
# Builds `fork` at a commit for the performance gate (DESIGN.md §5.2, Quality
# control 2), in WSL: clang, Release, -march=native, no tests, into
# ~/fork-perf/<short commit>/fork (reused if present).
# Usage: tools/perf_build.sh COMMIT -> prints the binary path.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
d=$HOME/fork-perf
c=$(git -C "$repo" rev-parse --short=7 "$1")
mkdir -p "$d"
if [ ! -x "$d/$c/fork" ]; then
  rm -rf "$d/src-$c"
  git clone -q "$repo" "$d/src-$c"
  git -C "$d/src-$c" checkout -q "$c"
  cmake -S "$d/src-$c" -B "$d/src-$c/build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DFORK_BUILD_TESTS=OFF \
    -DCMAKE_CXX_COMPILER=clang++ >/dev/null
  cmake --build "$d/src-$c/build" --target fork >/dev/null
  mkdir -p "$d/$c"
  cp "$d/src-$c/build/fork" "$d/$c/fork"
  rm -rf "$d/src-$c"
fi
echo "$d/$c/fork"
