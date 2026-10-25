#!/usr/bin/env bash
# One SPRT between two commits (DESIGN.md §5.2, "Testing setup"), run in WSL.
#
#   tools/sprt.sh NAME BASE TEST ELO0 ELO1 TC [HASH_MB]
#
#   NAME      short label for the log (e.g. d3-tt)
#   BASE      base commit (or tag); TEST: the commit under test
#   ELO0/1    normalized-Elo bounds (owner, 2026-10-24: 0 5 until Milestone B,
#             0 3 for tier 2, -3 0 for non-regression)
#   TC        fastchess time control: 8+0.08 (STC) or 40+0.4 (LTC)
#   HASH_MB   default 16 (STC); use 64 for LTC
#
# Environment: BASE_OPTS / TEST_OPTS extra -engine options (e.g.
# "option.UsePvs=false"), CONCURRENCY (default 5: the 7600X3D's 6 cores
# minus one, the machine is shared), FORK_SPRT_DIR (default ~/fork-sprt),
# TUNE=1 to build tuning binaries (FORK_TUNE: every search switch is a UCI
# check option, so one commit can be tested with a technique on and off).
#
# Each commit is exported with `git archive` from this repository and built
# with update.sh (the TCEC build, x86-64-v3), or with the same flags plus
# -DFORK_TUNE=ON when TUNE=1, into $FORK_SPRT_DIR/build-<sha>[-tune]; builds
# are reused. Openings: UHO_Lichess_4852_v1.epd, test openings only
# (KB data-policy.md decision 6), checked against its SHA-256 before every
# run. Game pairs with colours reversed, pentanomial report, alpha = beta =
# 0.05. The full fastchess output goes to $FORK_SPRT_DIR/logs/; the summary
# lines are appended to docs/history/phase-3/sprt-log.md.
set -euo pipefail

[ $# -ge 6 ] || { sed -n '2,25p' "$0"; exit 2; }
name=$1 base=$2 test=$3 elo0=$4 elo1=$5 tc=$6 hash=${7:-16}
repo=$(cd "$(dirname "$0")/.." && pwd)
dir=${FORK_SPRT_DIR:-$HOME/fork-sprt}
fastchess=$HOME/fork-tools/bin/fastchess
book=$HOME/fork-tools/books/UHO_Lichess_4852_v1.epd
book_sha=7a7f6470615a69c6cf23d565417701d38732876f480af90d67b42abade35644a
log_md=$repo/docs/history/phase-3/sprt-log.md
mkdir -p "$dir/logs"

[ -x "$fastchess" ] || { echo "sprt.sh: no fastchess at $fastchess" >&2; exit 1; }
[ -f "$book" ] && [ "$(sha256sum "$book" | cut -d' ' -f1)" = "$book_sha" ] ||
  { echo "sprt.sh: $book missing or not the pinned UHO_Lichess_4852_v1.epd (tools/get_books.sh)" >&2; exit 1; }

build() {  # commit -> path of its engine
  local sha out src
  sha=$(git -C "$repo" rev-parse --verify "$1^{commit}")
  out=$dir/build-$sha${TUNE:+-tune}
  if [ ! -x "$out/fork" ]; then
    src=$out/src
    rm -rf "$out" && mkdir -p "$src"
    git -C "$repo" archive "$sha" | tar -x -C "$src"
    if [ -n "${TUNE:-}" ]; then
      (cmake -S "$src" -B "$src/build/tcec" -DCMAKE_BUILD_TYPE=Release -DFORK_BUILD_TESTS=OFF \
        -DFORK_ARCH=x86-64-v3 -DFORK_TUNE=ON && cmake --build "$src/build/tcec" --target fork) >"$out/build.log" 2>&1
    else
      (cd "$src" && ./update.sh >"$out/build.log" 2>&1)
    fi || { echo "sprt.sh: build of $1 failed, see $out/build.log" >&2; exit 1; }
    cp "$src/build/tcec/fork" "$out/fork"
    rm -rf "$src"
  fi
  echo "$out/fork"
}

base_exe=$(build "$base")
test_exe=$(build "$test")
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out=$dir/logs/$stamp-$name.txt
echo "sprt.sh: $name: $base vs $test${TUNE:+ (tuning builds)}, [$elo0, $elo1], $tc, Hash $hash, concurrency ${CONCURRENCY:-5}; log $out"

# shellcheck disable=SC2086
"$fastchess" \
  -engine cmd="$test_exe" name=test ${TEST_OPTS:-} \
  -engine cmd="$base_exe" name=base ${BASE_OPTS:-} \
  -each tc="$tc" option.Hash="$hash" option.Threads=1 \
  -openings file="$book" format=epd order=random \
  -repeat -rounds 100000 -concurrency "${CONCURRENCY:-5}" \
  -sprt elo0="$elo0" elo1="$elo1" alpha=0.05 beta=0.05 model=normalized \
  -report penta=true -ratinginterval 100 -recover \
  -pgnout file="$dir/logs/$stamp-$name.pgn" | tee "$out"

summary=$(grep -E "^(Elo|LLR|Games|Ptnml|SPRT|H[01] was)" "$out" | tail -n 8 || true)
{
  echo
  echo "### $stamp $name"
  echo
  echo "- base \`$(git -C "$repo" rev-parse --short "$base")\` ($base), test \`$(git -C "$repo" rev-parse --short "$test")\` ($test), bounds [$elo0, $elo1] nElo, $tc, Hash $hash MB, 1 thread, concurrency ${CONCURRENCY:-5}${TUNE:+, tuning builds}${BASE_OPTS:+, base opts $BASE_OPTS}${TEST_OPTS:+, test opts $TEST_OPTS}"
  echo '```'
  echo "$summary"
  echo '```'
} >>"$log_md"
echo "sprt.sh: summary appended to $log_md"
