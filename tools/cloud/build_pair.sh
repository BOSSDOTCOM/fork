#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Builds the two engines of a cloud SPRT from one Fork repository, the way
# TCEC builds Fork (update.sh; on Ubuntu 22.04 with CXX=g++, gcc 11.4, and
# the default FORK_ARCH x86-64-v3, never native), each from a clean export
# of its commit.
#
#   tools/cloud/build_pair.sh REPO BASE TEST OUTDIR   -> OUTDIR/base/fork, OUTDIR/test/fork, OUTDIR/meta.env
set -euo pipefail
repo=$1 base=$2 test=$3 out=$4
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
  rm -rf "$src"
  echo "${side}_sha=$sha" >>"$out/meta.env"
  "$out/$side/fork" bench 2>/dev/null | head -n 2 | sed "s/^/${side}_/; s/ /=/" >>"$out/meta.env"
done
cat "$out/meta.env"
