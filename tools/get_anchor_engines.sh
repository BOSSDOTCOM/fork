#!/usr/bin/env bash
# Builds the Elo-baseline anchor engines (KB competition.md §5, "Elo-baseline
# anchors (weak engines)", branch kb) as opponent binaries, in WSL.
#
#   tools/get_anchor_engines.sh
#
# Each engine is cloned at its pinned commit into a fresh temporary folder,
# built with the command its README or makefile gives, and only the binary is
# kept, in ~/fork-tools/engines/<name>, with its SHA-256 in MANIFEST. The
# source is deleted at once and is never opened (DESIGN.md §1: other
# engines' code is off-limits; opponents are binaries only).
set -euo pipefail

dest=$HOME/fork-tools/engines
mkdir -p "$dest"

build_one() {  # name, repo URL, commit, subdirectory to build in, make arguments...
  local name=$1 url=$2 commit=$3 sub=$4
  shift 4
  if [ -x "$dest/$name" ]; then
    echo "$name: already built"
    return
  fi
  local tmp
  tmp=$(mktemp -d)
  git -C "$tmp" init -q src
  git -C "$tmp/src" fetch -q --depth 1 "$url" "$commit"
  git -C "$tmp/src" checkout -q FETCH_HEAD
  touch "$tmp/stamp"
  (cd "$tmp/src/$sub" && make -j"$(nproc)" "$@" >"$tmp/build.log" 2>&1) || {
    echo "$name: build failed:" >&2
    tail -n 20 "$tmp/build.log" >&2
    rm -rf "$tmp"
    return 1
  }
  # The binary: the largest executable file the build created.
  local bin
  bin=$(find "$tmp/src" -type f -perm -u+x -newer "$tmp/stamp" ! -name '*.sh' ! -name '*.o' -printf '%s %p\n' |
        sort -rn | head -n 1 | cut -d' ' -f2-)
  [ -n "$bin" ] || { echo "$name: no binary found" >&2; rm -rf "$tmp"; return 1; }
  cp "$bin" "$dest/$name"
  rm -rf "$tmp"
  printf 'uci\nquit\n' | timeout 10 "$dest/$name" | grep -q uciok || { echo "$name: no uciok" >&2; return 1; }
  echo "$name $commit $url $(sha256sum "$dest/$name" | cut -d' ' -f1)" >>"$dest/MANIFEST"
  echo "$name: built"
}

# Pinned tags and commits from the KB (CCRL Blitz ratings there). A failed
# build is reported and the others still run. Shallow Blue 2.0.0 predates
# gcc versions that no longer include <string> indirectly, so its compiler
# command forces that header in (a make override; its source is untouched).
failed=0
build() { build_one "$@" || failed=$((failed + 1)); }
build shallowblue-2.0.0 https://github.com/GunshipPenguin/shallow-blue a04fbd9861770c897eb566d83b0d2e3b17aa9fc0 .   "CXX=g++ -include string"
build stash-12.0 https://github.com/mhouppin/stash-bot c59e2739e3d33eef9b177f2063187dbe2795233c .
# BBC 1.1 (KB) is left out: at its pinned commit the makefile in src/ does
# not find its source file (2026-10-25), and its licence at that tag is
# unclear (KB). Five anchors still span CCRL Blitz 1578 to 2896.
build stash-15.3 https://github.com/mhouppin/stash-bot 7d17ff80eb53b9d4808fd285c7439e641f1c5a3b src
build stash-19.0 https://github.com/mhouppin/stash-bot de408a3e8d8ffbd41f4b1608b19f18c69eac2512 src
build weiss-1.0 https://github.com/TerjeKir/weiss f44a4c654c67139ecbd5f3afd9da1ebe41241464 src
cat "$dest/MANIFEST"
[ "$failed" = 0 ] || { echo "$failed engine(s) failed to build" >&2; exit 1; }
