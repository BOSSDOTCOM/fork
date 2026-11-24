#!/usr/bin/env bash
# Bench parity, perftbench parity, netcheck of the embedded default net (r3kr1)
# and the nnue suite on each preset (promote/r3kr1 worktree).
#   presets.sh PRESET...   (one after the other; logs beside this script)
set -u
wt=~/fork-runners/scratch-promote-kr1/wt
out=~/fork-runners/scratch-promote-kr1
cd "$wt" || exit 1
. scripts/env.sh >/dev/null 2>&1
export CMAKE_BUILD_PARALLEL_LEVEL=3 FORK_CHECK_JOBS=3
want=$(tr -d '\r' < tests/bench-r3kr1.ref | grep -E '^(nodes|signature) ')
pwant=$(tr -d '\r' < tests/perft_bench.ref | grep -E '^(nodes|signature) ')
for p in "$@"; do
  log=$out/preset-$p.log
  {
    echo "== $p $(date)"
    if ! { cmake --preset "$p" > "$out/cfg-$p.log" 2>&1 && cmake --build "build/$p" --target fork fork_tests > "$out/build-$p.log" 2>&1; }; then
      echo "$p: BUILD FAILED"; continue
    fi
    bin=build/$p/fork.exe
    "$bin" version | tr -d '\r' | grep -E '^(net|variant|lto|arch|cpu) '
    got=$("$bin" bench | tr -d '\r' | grep -E '^(nodes|signature|nps) ')
    echo "$got"
    if [ "$(grep -E '^(nodes|signature) ' <<<"$got")" = "$want" ]; then echo "$p: bench parity OK"; else echo "$p: BENCH MISMATCH"; fi
    pb=$("$bin" perftbench | tr -d '\r' | grep -E '^(nodes|signature) ')
    [ "$pb" = "$pwant" ] && echo "$p: perftbench parity OK" || echo "$p: PERFTBENCH MISMATCH"
    "$bin" netcheck tests/nnue/r3kr1.parity | tr -d '\r'
    if build/$p/fork_tests.exe nnue > "$out/nnue-$p.log" 2>&1; then
      echo "$p: nnue suite OK: $(tr -d '\r' < "$out/nnue-$p.log" | tail -n 3 | tr '\n' ' ')"
    else
      echo "$p: NNUE SUITE FAILED (see nnue-$p.log)"
    fi
  } > "$log" 2>&1
  grep -E 'OK|MISMATCH|FAILED|netcheck|^net ' "$log"
done
