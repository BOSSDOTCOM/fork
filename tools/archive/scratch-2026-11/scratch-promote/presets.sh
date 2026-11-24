#!/usr/bin/env bash
# Bench parity and netcheck of the embedded default net on each preset (promote/r8ceplo2 worktree).
set -u
wt=~/fork-runners/scratch-promote/wt
out=~/fork-runners/scratch-promote
cd "$wt" || exit 1
. scripts/env.sh >/dev/null 2>&1
export CMAKE_BUILD_PARALLEL_LEVEL=3 FORK_CHECK_JOBS=3
want=$(tr -d '\r' < tests/bench-r8ceplo2.ref | grep -E '^(nodes|signature) ')
for p in "$@"; do
  log=$out/preset-$p.log
  {
    echo "== $p $(date)"
    cmake --preset "$p" -DFORK_BUILD_TESTS=OFF > /dev/null && cmake --build "build/$p" --target fork > /dev/null || { echo "$p: BUILD FAILED"; continue; }
    bin=build/$p/fork.exe
    "$bin" version | tr -d '\r' | grep -E '^(net|variant|lto) '
    got=$("$bin" bench | tr -d '\r' | grep -E '^(nodes|signature|nps) ')
    echo "$got"
    if [ "$(grep -E '^(nodes|signature) ' <<<"$got")" = "$want" ]; then echo "$p: bench parity OK"; else echo "$p: BENCH MISMATCH"; fi
    pb=$("$bin" perftbench | tr -d '\r' | grep -E '^(nodes|signature) ')
    [ "$pb" = "$(tr -d '\r' < tests/perft_bench.ref | grep -E '^(nodes|signature) ')" ] && echo "$p: perftbench parity OK" || echo "$p: PERFTBENCH MISMATCH"
    "$bin" netcheck tests/nnue/r8ceplo2.parity
  } > "$log" 2>&1
  grep -E 'OK|MISMATCH|FAILED|netcheck' "$log"
done
