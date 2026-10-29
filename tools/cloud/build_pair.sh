#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Builds the two engines of a cloud SPRT from one Fork repository, the way
# TCEC builds Fork (update.sh; on Ubuntu 22.04 with CXX=g++, gcc 11.4, never
# native), each from a clean export of its commit. The caller pins the
# target in FORK_ARCH (no default here, so a change to update.sh's default
# can never reach a cloud SPRT): x86-64-v3 on GitHub's runners, which may
# lack AVX-512. Each binary's `fork version` must report that target.
#
#   FORK_ARCH=x86-64-v3 tools/cloud/build_pair.sh REPO BASE TEST OUTDIR
#       -> OUTDIR/base/fork, OUTDIR/test/fork, OUTDIR/meta.env
set -euo pipefail
repo=$1 base=$2 test=$3 out=$4
: "${FORK_ARCH:?build_pair.sh: set FORK_ARCH (x86-64-v3 or x86-64-v4)}"
case $FORK_ARCH in x86-64-v3 | x86-64-v4) ;; *) echo "build_pair.sh: FORK_ARCH must be x86-64-v3 or x86-64-v4" >&2; exit 2 ;; esac
export FORK_ARCH
# The binaries run here (version, bench) and on machines like this one, so
# an AVX-512 build needs AVX-512 here: the five features x86-64-v4 adds to
# x86-64-v3 (gcc 11.4's predefined macros, -march=x86-64-v4 vs v3).
if [ "$FORK_ARCH" = x86-64-v4 ]; then
  for f in avx512f avx512bw avx512cd avx512dq avx512vl; do
    grep -qw "$f" /proc/cpuinfo || { echo "build_pair.sh: x86-64-v4 needs $f, which this CPU lacks" >&2; exit 2; }
  done
fi
# Absolute paths: each build runs in its own export folder.
mkdir -p "$out"
out=$(cd "$out" && pwd)
repo=$(cd "$repo" && pwd)
for side in base test; do
  ref=${!side}
  sha=$(git -C "$repo" rev-parse --verify "$ref^{commit}")
  src=$(mktemp -d)
  git -C "$repo" archive "$sha" | tar -x -C "$src"
  (cd "$src" && CXX=${CXX:-g++} ./update.sh >"$out/$side-build.log" 2>&1) ||
    { tail -n 30 "$out/$side-build.log" >&2; exit 1; }
  mkdir -p "$out/$side"
  cp "$src/build/tcec/fork" "$out/$side/fork"
  got=$("$out/$side/fork" version | tr -d '\r' | sed -n 's/^arch //p')
  [ "$got" = "$FORK_ARCH" ] || { echo "build_pair.sh: $side reports arch '$got', not $FORK_ARCH" >&2; exit 1; }
  # The game gate (DESIGN.md §5.3, deliverable 6): an nnue build plays only
  # if its embedded network matches its parity file exactly, and a network
  # without a parity file never plays.
  net=$("$out/$side/fork" version | tr -d '\r' | sed -n 's/^net //p')
  if [ -n "$net" ]; then
    [ -f "$src/tests/nnue/$net.parity" ] || { echo "build_pair.sh: $side's network $net has no tests/nnue/$net.parity" >&2; exit 1; }
    "$out/$side/fork" netcheck "$src/tests/nnue/$net.parity" >"$out/$side-netcheck.log" 2>&1 ||
      { cat "$out/$side-netcheck.log" >&2; echo "build_pair.sh: $side's network fails its parity file" >&2; exit 1; }
    echo "${side}_net=$net" >>"$out/meta.env"
  fi
  rm -rf "$src"
  echo "${side}_sha=$sha" >>"$out/meta.env"
  echo "${side}_arch=$got" >>"$out/meta.env"
  "$out/$side/fork" bench 2>/dev/null | head -n 2 | sed "s/^/${side}_/; s/ /=/" >>"$out/meta.env"
done
cat "$out/meta.env"
