#!/usr/bin/env bash
# Bake-off round 3 option (a): architecture 9's nnue suite and bench on each
# named preset (Git Bash, Windows toolchain), with nets/r8brft1kr4.fnet built in.
#   run-presets.sh PRESET...
set -u
S=$(cygpath -m ~/fork-runners/scratch-r3kr4)  # archive: was a literal /c/ path
cd "$S/wt" || exit 1
. scripts/env.sh
export CMAKE_BUILD_PARALLEL_LEVEL=3
for p in "$@"; do
  b=build/kr4-$p
  echo "== $p"
  cmake --preset "$p" -B "$b" -DFORK_NET="$S/wt/nets/r8brft1kr4.fnet" >"$S/work/cfg-$p.log" 2>&1 || { echo "configure failed"; continue; }
  cmake --build "$b" --target fork fork_tests >"$S/work/build-$p.log" 2>&1 || { echo "build failed"; tail -5 "$S/work/build-$p.log"; continue; }
  "$b/fork_tests" nnue >"$S/work/nnue-$p.log" 2>&1
  echo "nnue exit $? : $(tail -1 "$S/work/nnue-$p.log")"
  "$b/fork" bench 2>&1 | grep -E '^(nodes|signature)' | tr '\n' ' '
  echo
  "$b/fork" netcheck tests/nnue/r8brft1kr4.parity
done
