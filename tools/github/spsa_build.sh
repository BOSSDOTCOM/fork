#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Builds the engine of a GitHub SPSA run (.github/workflows/spsa.yml): one Fork commit as a tuning build
# (CMake FORK_TUNE, every FORK_SEARCH_PARAMS entry a UCI spin option; src/tune/params.hpp), from a clean
# export of the commit, with update.sh's configure line plus -DFORK_TUNE=ON (update.sh, TCEC's script, is
# not touched; tools/github/test_spsa.py checks the two lines stay equal). The caller pins the target in
# FORK_ARCH, as for an SPRT build (tools/cloud/build_pair.sh): x86-64-v3 on GitHub's runners.
#
#   FORK_ARCH=x86-64-v3 tools/github/spsa_build.sh REPO COMMIT OUTDIR   -> OUTDIR/fork, OUTDIR/meta.env
#
# Checks, each fatal: the binary reports FORK_ARCH; an nnue build's network passes its parity file (the
# game gate, as build_pair.sh); bench and perftbench match the commit's references for the network
# `fork version` names (.github/ci/bench-parity.sh of the commit: tests/bench-<net>.ref), so at the
# defaults the tuning build plays the shipped engine; and every FORK_SEARCH_PARAMS row of the commit is
# declared as a spin option with its default and range. Environment: CXX (default g++), FORK_JOBS
# (parallel build jobs, default nproc).
set -euo pipefail
repo=$1 commit=$2 out=$3
: "${FORK_ARCH:?spsa_build.sh: set FORK_ARCH (x86-64-v3 or x86-64-v4)}"
case $FORK_ARCH in x86-64-v3 | x86-64-v4) ;; *) echo "spsa_build.sh: FORK_ARCH must be x86-64-v3 or x86-64-v4" >&2; exit 2 ;; esac
mkdir -p "$out"
out=$(cd "$out" && pwd)
repo=$(cd "$repo" && pwd)
sha=$(git -C "$repo" rev-parse --verify "$commit^{commit}")
src=$(mktemp -d)
trap 'rm -rf "$src"' EXIT
git -C "$repo" archive "$sha" | tar -x -C "$src"
generator=()
command -v ninja >/dev/null && generator=(-G Ninja)
(cd "$src" &&
  cmake -S "$src" -B "$src/build/tune" "${generator[@]}" \
    -DCMAKE_CXX_COMPILER="${CXX:-g++}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DFORK_ARCH="$FORK_ARCH" \
    -DFORK_BUILD_TESTS=OFF \
    -DFORK_TUNE=ON &&
  cmake --build "$src/build/tune" --target fork -j "${FORK_JOBS:-$(nproc)}") >"$out/build.log" 2>&1 ||
  { tail -n 30 "$out/build.log" >&2; exit 1; }
cp "$src/build/tune/fork" "$out/fork"
fork=$out/fork
got=$("$fork" version | tr -d '\r' | sed -n 's/^arch //p')
[ "$got" = "$FORK_ARCH" ] || { echo "spsa_build.sh: the build reports arch '$got', not $FORK_ARCH" >&2; exit 1; }
net=$("$fork" version | tr -d '\r' | sed -n 's/^net //p')
if [ -n "$net" ]; then
  [ -f "$src/tests/nnue/$net.parity" ] || { echo "spsa_build.sh: network $net has no tests/nnue/$net.parity" >&2; exit 1; }
  "$fork" netcheck "$src/tests/nnue/$net.parity" >"$out/netcheck.log" 2>&1 ||
    { cat "$out/netcheck.log" >&2; echo "spsa_build.sh: network $net fails its parity file" >&2; exit 1; }
fi
bash "$src/.github/ci/bench-parity.sh" "$fork" >"$out/parity.log" 2>&1 ||
  { cat "$out/parity.log" >&2; echo "spsa_build.sh: the tuning build fails bench parity" >&2; exit 1; }
options=$(printf 'uci\nquit\n' | "$fork" | tr -d '\r')
rows=$(sed -n '/^#define FORK_SEARCH_PARAMS/,/^$/p' "$src/src/tune/params.hpp" | grep '^ *X(' |
  sed -E 's/^ *X\(([A-Za-z0-9_]+), *(-?[0-9]+), *(-?[0-9]+), *(-?[0-9]+), *(-?[0-9]+)\).*/\1 \2 \3 \4/')
[ -n "$rows" ] || { echo "spsa_build.sh: no FORK_SEARCH_PARAMS rows in the commit" >&2; exit 1; }
while read -r name dflt lo hi; do
  grep -qx "option name $name type spin default $dflt min $lo max $hi" <<<"$options" ||
    { echo "spsa_build.sh: the tuning build does not declare $name as spin $dflt [$lo, $hi]" >&2; exit 1; }
done <<<"$rows"
{
  echo "sha=$sha"
  echo "arch=$got"
  [ -z "$net" ] || echo "net=$net"
  echo "tune=on"
  echo "params=$(wc -l <<<"$rows" | tr -d ' ')"
  grep -E '^bench parity ok' "$out/parity.log" | sed -E 's/.*\): nodes ([0-9]+) signature ([0-9a-f]+).*/bench_nodes=\1\nbench_signature=\2/'
} >"$out/meta.env"
cat "$out/meta.env"
