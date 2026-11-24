#!/usr/bin/env bash
# Bake-off round 3 option (a): the nps check's builds (WSL Ubuntu, clang,
# Release, LTO, x86-64-v3, no tests), as the design report's speed sessions:
#   A = phase-4 37b5d30 with r8brft1 (the default), B = nets/r3-kr4 COMMIT with
#   nets/r8brft1kr4.fnet (architecture 9, every region r8brft1's rows).
#   run-nps-build.sh B_COMMIT
set -eu
WIN_HOME=${WIN_HOME:?set WIN_HOME to the Windows home folder as WSL sees it, /mnt/c/Users/<user>}  # archive: was a literal path
S=$WIN_HOME/fork-runners/scratch-r3kr4
N=$S/nps
REPO=$WIN_HOME/fork
B_COMMIT=${1:?B commit}
mkdir -p "$N"
build() {  # dir commit net
  local d=$N/$1 c=$2 net=$3
  if [ ! -d "$d/src" ]; then git clone -q --no-checkout "$REPO" "$d"; fi
  git -C "$d" fetch -q "$REPO" "$c" 2>/dev/null || true
  git -C "$d" checkout -q --detach "$c"
  cmake -S "$d" -B "$d/build" -G Ninja -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_BUILD_TYPE=Release \
    -DFORK_ARCH=x86-64-v3 -DFORK_BUILD_TESTS=OFF -DFORK_NET="$d/nets/$net.fnet" >/dev/null
  CMAKE_BUILD_PARALLEL_LEVEL=3 nice cmake --build "$d/build" --target fork | tail -1
  "$d/build/fork" version | head -3
  "$d/build/fork" bench 2>&1 | grep -E '^(nodes|signature)' | tr '\n' ' '; echo
}
build A 37b5d30 r8brft1
build B "$B_COMMIT" r8brft1kr4
