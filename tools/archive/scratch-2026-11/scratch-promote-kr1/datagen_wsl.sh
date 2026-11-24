#!/usr/bin/env bash
# WSL Ubuntu-22.04: the labeller's build path (tools/control_center/start_part.sh's MODE=build: a clang PGO build
# for x86-64-v3 of fork and fork_datagen) on the clean clone, then fork's bench against tests/bench-r3kr1.ref and a
# short fork_datagen run checked by tools/datagen/verify_games.py.
set -u
WIN_HOME=${WIN_HOME:?set WIN_HOME to the Windows home folder as WSL sees it, /mnt/c/Users/<user>}  # archive: was a literal path
s=$WIN_HOME/fork-runners/scratch-promote-kr1
cd ~/scratch-promote-kr1/fork || exit 1
export CMAKE_BUILD_PARALLEL_LEVEL=3
cxx=/usr/lib/llvm-19/bin/clang++
nice -n 10 cmake -DSOURCE_DIR="$PWD" -DCXX="$cxx" -DCOMPILER_ID=Clang -DARCH=x86-64-v3 -P cmake/pgo.cmake > "$s/datagen-pgo.log" 2>&1 || { echo "PGO BUILD FAILED"; tail -5 "$s/datagen-pgo.log"; exit 1; }
nice -n 10 cmake --build build/clang-pgo --target fork fork_datagen >> "$s/datagen-pgo.log" 2>&1 || { echo "DATAGEN BUILD FAILED"; exit 1; }
b=build/clang-pgo
"$b/fork" version | grep -E '^(Fork|compiler|arch|net) '
got=$("$b/fork" bench | grep -E '^(nodes|signature) ' | tr '\n' ' ')
want=$(grep -E '^(nodes|signature) ' tests/bench-r3kr1.ref | tr '\n' ' ')
echo "bench: $got"
[ "$got" = "$want" ] && echo "datagen build: bench parity OK" || echo "datagen build: BENCH MISMATCH (want $want)"
out=~/scratch-promote-kr1/datagen-smoke
rm -rf "$out"; mkdir -p "$out"
"$b/fork_datagen" --openings tests/datagen_openings.epd --out "$out" --positions 4000 --nodes 5000 --threads 2 \
  --seed 3 --run smoke-r3kr1-pgo 2>&1 | tail -1
grep -o '"evaluator": "[^"]*"' "$out"/smoke-r3kr1-pgo.json
python3 -I tools/datagen/verify_games.py "$out"/*.vf 2>&1 | tail -1
