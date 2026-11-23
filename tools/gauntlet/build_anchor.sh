#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Builds one gauntlet anchor (tools/gauntlet/anchors.tsv) from its official
# repository at the pinned commit, natively on this machine, and checks that it
# answers `uci` with `uciok`. The anchor's source is fetched into a temporary
# folder, built with the command the table gives, and deleted; only the binary
# is kept (opponents are binaries only: DESIGN.md §1). The binary is the
# largest executable file the build created. A make build may have several
# steps separated by "; ", run in order (Stockfish: make net, then make
# build). Every network file (*.nnue) in the source tree after the build is
# logged with its SHA-256, and so is each line of the build log that names
# one (whether a step fetched it).
#
#   tools/gauntlet/build_anchor.sh STEM OUTDIR     -> OUTDIR/STEM; exit 0, or 1 if it does not build
set -uo pipefail
stem=${1:?usage: build_anchor.sh STEM OUTDIR} out=${2:?usage: build_anchor.sh STEM OUTDIR}
table=$(cd "$(dirname "$0")" && pwd)/anchors.tsv
line=$(grep -v '^#' "$table" | awk -F'\t' -v s="$stem" '$2 == s' | head -n 1)
[ -n "$line" ] || { echo "build_anchor.sh: no anchor '$stem' in anchors.tsv" >&2; exit 2; }
IFS=$'\t' read -r name _ _ _ url commit sub build fallback _ <<<"$line"
mkdir -p "$out"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git -C "$tmp" init -q src
git -C "$tmp/src" fetch -q --depth 1 "$url" "$commit" && git -C "$tmp/src" checkout -q FETCH_HEAD ||
  { echo "$name: cannot fetch $commit from $url" >&2; exit 1; }
touch "$tmp/stamp"
run_build() {  # extra make arguments...
  case $build in
    cmake\ *)
      cmake -S "$tmp/src" -B "$tmp/build" -DCMAKE_BUILD_TYPE=Release >"$tmp/build.log" 2>&1 &&
        cmake --build "$tmp/build" --target "${build#cmake }" -j"$(nproc)" >>"$tmp/build.log" 2>&1 ;;
    make*)
      : >"$tmp/build.log"
      IFS=';' read -ra steps <<<"$build"
      for step in "${steps[@]}"; do
        step=${step# }
        echo "== $step $*" >>"$tmp/build.log"
        # shellcheck disable=SC2086
        (cd "$tmp/src/$sub" && make -j"$(nproc)" ${step#make} "$@" >>"$tmp/build.log" 2>&1) || return 1
      done ;;
    *) echo "$name: unknown build command '$build'" >&2; return 1 ;;
  esac
}
if ! run_build; then
  if [ "$fallback" != - ]; then
    echo "$name: build failed; retrying with $fallback"
    # shellcheck disable=SC2086
    run_build $fallback || { echo "$name: build failed:" >&2; tail -n 20 "$tmp/build.log" >&2; exit 1; }
  else
    echo "$name: build failed:" >&2; tail -n 20 "$tmp/build.log" >&2; exit 1
  fi
fi
bin=$(find "$tmp/src" "$tmp/build" -type f -perm -u+x -newer "$tmp/stamp" ! -name '*.sh' ! -name '*.o' \
  -printf '%s %p\n' 2>/dev/null | sort -rn | head -n 1 | cut -d' ' -f2-)
[ -n "$bin" ] || { echo "$name: no binary found" >&2; exit 1; }
grep -i -e '^== ' -e 'nnue' "$tmp/build.log" | sed "s/^/$name: build log: /"
(cd "$tmp/src" && find . -type f -name '*.nnue' -exec sha256sum {} +) | sed "s/^/$name: network /"
cp "$bin" "$out/$stem"
printf 'uci\nquit\n' | timeout 20 "$out/$stem" | grep -q uciok || { echo "$name: no uciok" >&2; rm -f "$out/$stem"; exit 1; }
echo "$name: built ($commit, $(sha256sum "$out/$stem" | cut -c1-16))"
