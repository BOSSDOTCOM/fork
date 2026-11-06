#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
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
# "option.UsePvs=false"), CONCURRENCY (default 10, owner 2026-10-25,
# raised from 5: 1,478 games per hour at STC with 0 time losses over 505
# games, against about 790 at 5; drop to 8 if time losses appear),
# ADJUDICATE (default 1: resign and draw adjudication, see below; 0 plays
# every game out), FORK_SPRT_DIR (default ~/fork-sprt),
# TUNE=1 to build tuning binaries (FORK_TUNE: every search switch is a UCI
# check option, so one commit can be tested with a technique on and off),
# MAX_GAMES to change the cap below, CXX (default: update.sh's choice, the
# first found of clang++-19, clang++-16, clang++, g++-12, g++), SRAND (the
# opening order's seed; default: the run's UTC stamp as a number),
# TABLES (default 1: both engines get the Syzygy 3-4-5 tables; 0: neither
# does, and BASE_OPTS / TEST_OPTS may then give them to one side),
# SYZYGY_PATH (default: config/local-test.json's syzygy.path).
#
# Tables (DESIGN.md §5.2; owner, audit-1 Phase C): both engines get
# option.SyzygyPath, the 3-4-5 set (145 .rtbw + 145 .rtbz, checked here);
# the log entry says whether tables were on.
#
# Cap (owner, 2026-10-25): an SPRT that has not decided after MAX_GAMES games
# (default 20,000 at STC, 10,000 at any other time control) stops and is
# logged as INCONCLUSIVE instead of running indefinitely.
#
# Each commit is exported with `git archive` from this repository and built
# with update.sh (the TCEC build, x86-64-v3), or with the same flags plus
# -DFORK_TUNE=ON when TUNE=1, both sides with the same compiler (CXX, passed
# explicitly in both modes), into
# $FORK_SPRT_DIR/build-<sha>-<compiler key>[-tune]; builds are reused only
# for the same compiler. Before the games, both binaries' `fork version` and
# `fork bench` are run: each bench must equal its commit's tests/bench.ref
# and both must name the same compiler, or the run stops (the identity
# check); both are logged. Openings: UHO_Lichess_4852_v1.epd, test openings
# only (KB data-policy.md decision 6), checked against its SHA-256 before
# every run, in a random order fixed by -srand (logged, so a run's openings
# can be replayed). Game pairs with colours reversed, pentanomial report,
# alpha = beta = 0.05. The full fastchess output goes to
# $FORK_SPRT_DIR/logs/; the summary lines are appended to
# docs/history/phase-3/sprt-log.md.
#
# Exit status: 0 after a run that ended normally (decided or at the cap); 1
# when nothing was played (a build, identity or fastchess failure before the
# first finished game: no log entry); 3 when fastchess stopped early (by
# hand, or an error) after some games: their partial result is logged, with
# fastchess's exit status.
set -euo pipefail

[ $# -ge 6 ] || { awk 'NR > 2 && /^set -euo/ { exit } NR > 2' "$0"; exit 2; }
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

each_tb=() tables_note="no tables"
case ${TABLES:-1} in
  1)
    case "${BASE_OPTS:-} ${TEST_OPTS:-}" in
      *SyzygyPath*) echo "sprt.sh: BASE_OPTS/TEST_OPTS set SyzygyPath, but TABLES=1 already gives both sides the tables; set TABLES=0 to choose per side" >&2; exit 2 ;;
    esac
    tb=${SYZYGY_PATH:-$(sed -n '/"syzygy"/,/}/ s/^[[:space:]]*"path":[[:space:]]*"\([^"]*\)".*/\1/p' "$repo/config/local-test.json" | head -n 1)}
    tb=${tb/#\~/$HOME}
    w=$(find "$tb" -maxdepth 1 -name '*.rtbw' 2>/dev/null | wc -l) z=$(find "$tb" -maxdepth 1 -name '*.rtbz' 2>/dev/null | wc -l)
    [ -n "$tb" ] && [ "$w" = 145 ] && [ "$z" = 145 ] ||
      { echo "sprt.sh: '$tb' does not hold the Syzygy 3-4-5 set (145 + 145 files, found $w + $z); set SYZYGY_PATH, or TABLES=0 to play without tables" >&2; exit 1; }
    each_tb=(option.SyzygyPath="$tb")
    tables_note="Syzygy 3-4-5 for both sides (${tb//$HOME/\~})"
    ;;
  0) ;;
  *) echo "sprt.sh: TABLES must be 1 or 0" >&2; exit 2 ;;
esac

# One compiler for both sides and both build modes (update.sh's order when
# CXX is unset); its --version line keys the build cache, so a build made
# by another compiler (one installed later, say) is never reused.
if [ -z "${CXX:-}" ]; then
  for c in clang++-19 clang++-16 clang++ g++-12 g++; do
    if command -v "$c" >/dev/null; then CXX=$c; break; fi
  done
fi
[ -n "${CXX:-}" ] && command -v "$CXX" >/dev/null || { echo "sprt.sh: no C++ compiler found (set CXX)" >&2; exit 1; }
cxx=$CXX
cxx_id=$("$cxx" --version 2>/dev/null | head -n 1)
[ -n "$cxx_id" ] || { echo "sprt.sh: $cxx --version printed nothing" >&2; exit 1; }
cxx_key=$(basename "$cxx" | tr -c 'A-Za-z0-9.+\n' '_')-$(printf '%s' "$cxx_id" | sha256sum | cut -c1-12)

build() {  # commit -> path of its engine
  local sha out src
  sha=$(git -C "$repo" rev-parse --verify "$1^{commit}")
  out=$dir/build-$sha-$cxx_key${TUNE:+-tune}
  if [ ! -x "$out/fork" ]; then
    src=$out/src
    rm -rf "$out" && mkdir -p "$src"
    git -C "$repo" archive "$sha" | tar -x -C "$src"
    if [ -n "${TUNE:-}" ]; then
      (cmake -S "$src" -B "$src/build/tcec" -DCMAKE_CXX_COMPILER="$cxx" -DCMAKE_BUILD_TYPE=Release \
        -DFORK_BUILD_TESTS=OFF -DFORK_ARCH=x86-64-v3 -DFORK_TUNE=ON &&
        cmake --build "$src/build/tcec" --target fork) >"$out/build.log" 2>&1
    else
      (cd "$src" && CXX=$cxx ./update.sh >"$out/build.log" 2>&1)
    fi || { echo "sprt.sh: build of $1 failed, see $out/build.log" >&2; exit 1; }
    cp "$src/build/tcec/fork" "$out/fork"
    rm -rf "$src"
  fi
  echo "$out/fork"
}

identity() {  # commit, engine -> "Fork <version>, <compiler>, bench <nodes> <signature>"
  # Fails when the bench differs from the commit's own tests/bench.ref
  # (non-negotiable 3 keeps bench.ref in step with every commit).
  local version compiler bench ref net reffile parity
  version=$("$2" version | sed -n '1p')
  compiler=$("$2" version | sed -n 's/^compiler //p')
  # An nnue build: its bench reference is tests/bench-<net>.ref, and it plays
  # only if its embedded network matches tests/nnue/<net>.parity exactly
  # (the game gate, DESIGN.md §5.3, deliverable 6).
  net=$("$2" version | tr -d '\r' | sed -n 's/^net //p')
  reffile=tests/bench.ref
  if [ -n "$net" ]; then
    reffile=tests/bench-$net.ref
    parity=$(mktemp)
    git -C "$repo" show "$1:tests/nnue/$net.parity" >"$parity" 2>/dev/null ||
      { echo "sprt.sh: $1: network $net has no tests/nnue/$net.parity" >&2; rm -f "$parity"; return 1; }
    "$2" netcheck "$parity" >&2 || { echo "sprt.sh: $1: network $net fails its parity file" >&2; rm -f "$parity"; return 1; }
    rm -f "$parity"
  fi
  bench=$("$2" bench | sed -n '1,2p' | awk '{ printf "%s%s", (NR > 1 ? " " : ""), $2 }')
  ref=$(git -C "$repo" show "$1:$reffile" 2>/dev/null | sed -n '1,2p' | awk '{ printf "%s%s", (NR > 1 ? " " : ""), $2 }')
  if [ -z "$bench" ] || { [ -n "$ref" ] && [ "$bench" != "$ref" ]; }; then
    echo "sprt.sh: $1: bench '$bench' is not its tests/bench.ref '$ref' (wrong or stale build in $2?)" >&2
    return 1
  fi
  echo "$version, $compiler, bench $bench${ref:+ (= bench.ref)}"
}

base_exe=$(build "$base")
test_exe=$(build "$test")
base_id=$(identity "$base" "$base_exe")
test_id=$(identity "$test" "$test_exe")
[ "$(echo "$base_id" | cut -d, -f2)" = "$(echo "$test_id" | cut -d, -f2)" ] ||
  { echo "sprt.sh: the two builds name different compilers: base $base_id; test $test_id" >&2; exit 1; }
echo "sprt.sh: base $base_id"
echo "sprt.sh: test $test_id"
if [ -z "${MAX_GAMES:-}" ]; then
  if [ "$tc" = 8+0.08 ]; then MAX_GAMES=20000; else MAX_GAMES=10000; fi
fi
# Adjudication (owner, 2026-10-25), the same for both engines: a game is
# resigned once both engines have reported a score of at least 1000 cp for
# one side for 5 consecutive moves, and drawn from move 40 on once both have
# reported |score| <= 10 cp for 10 consecutive moves. ADJUDICATE=0 plays every
# game to its end, as before.
if [ "${ADJUDICATE:-1}" = 1 ]; then
  adjudication="-resign movecount=5 score=1000 twosided=true -draw movenumber=40 movecount=10 score=10"
  adjudication_note="adjudication resign 1000 cp x 5 moves (two-sided), draw |10| cp x 10 moves from move 40"
else
  adjudication=""
  adjudication_note="no adjudication"
fi
stamp=$(date -u +%Y%m%dT%H%M%SZ)
seed=${SRAND:-${stamp//[!0-9]/}}
case $seed in '' | *[!0-9]*) echo "sprt.sh: SRAND must be a number" >&2; exit 2 ;; esac
out=$dir/logs/$stamp-$name.txt
echo "sprt.sh: $name: $base vs $test${TUNE:+ (tuning builds)}, [$elo0, $elo1], $tc, Hash $hash, concurrency ${CONCURRENCY:-10}, cap $MAX_GAMES games, $adjudication_note, $tables_note, openings seed $seed; log $out"

# From the log directory: fastchess writes its config.json autosave into the
# working directory, which must not be the repository.
cd "$dir/logs"
fc_status=0
# shellcheck disable=SC2086
"$fastchess" \
  -engine cmd="$test_exe" name=test ${TEST_OPTS:-} \
  -engine cmd="$base_exe" name=base ${BASE_OPTS:-} \
  -each tc="$tc" option.Hash="$hash" option.Threads=1 "${each_tb[@]}" \
  -openings file="$book" format=epd order=random -srand "$seed" \
  -repeat -rounds $((MAX_GAMES / 2)) -concurrency "${CONCURRENCY:-10}" \
  -sprt elo0="$elo0" elo1="$elo1" alpha=0.05 beta=0.05 model=normalized \
  ${adjudication} \
  -report penta=true -ratinginterval 100 -recover \
  -pgnout file="$dir/logs/$stamp-$name.pgn" | tee "$out" || fc_status=${PIPESTATUS[0]}

# A run that never got going (an unknown option, an engine that does not
# start) has nothing to report: no log entry.
games=$(grep -c '^Finished game' "$out" || true)
if [ "$games" = 0 ]; then
  echo "sprt.sh: no game finished (fastchess exit status $fc_status); nothing logged, see $out" >&2
  exit 1
fi
[ "$fc_status" = 0 ] ||
  echo "sprt.sh: fastchess ended early (exit status $fc_status, stopped?) after $games games; logging what it reported" >&2

# The last report block only: from the last "Elo:" line on (a test stopped by
# hand has no final report, so this is its last periodic one).
summary=$(awk '/^Elo:/ { block = "" } /^(Elo|LLR|Games|Ptnml|SPRT)/ { block = block $0 "\n" } END { printf "%s", block }' "$out")
if grep -q "H[01] was accepted" "$out"; then
  verdict=$(grep -o "H[01] was accepted" "$out" | tail -n 1)
elif [ "$fc_status" != 0 ]; then
  verdict="INCONCLUSIVE: stopped early after $games games (fastchess exit status $fc_status)"
else
  verdict="INCONCLUSIVE: no decision after the $MAX_GAMES-game cap"
fi
{
  echo
  echo "### $stamp $name"
  echo
  # Options may hold paths under the home folder: the log is public, so it
  # names them from ~ (no user name in the repository, 2026-10-24 rule).
  # Either may be unset (set -u): a plain commit-against-commit test has none.
  BASE_OPTS=${BASE_OPTS:-} TEST_OPTS=${TEST_OPTS:-}
  BASE_OPTS=${BASE_OPTS//$HOME/\~}
  TEST_OPTS=${TEST_OPTS//$HOME/\~}
  echo "- base \`$(git -C "$repo" rev-parse --short "$base^{commit}")\` ($base), test \`$(git -C "$repo" rev-parse --short "$test^{commit}")\` ($test), bounds [$elo0, $elo1] nElo, $tc, Hash $hash MB, 1 thread, concurrency ${CONCURRENCY:-10}, $adjudication_note, $tables_note${TUNE:+, tuning builds}${BASE_OPTS:+, base opts $BASE_OPTS}${TEST_OPTS:+, test opts $TEST_OPTS}"
  echo "- Builds: base $base_id; test $test_id. Openings in random order, -srand $seed."
  echo "- Verdict: **$verdict**; cap $MAX_GAMES games."
  echo '```'
  echo "$summary"
  echo '```'
} >>"$log_md"
echo "sprt.sh: summary appended to $log_md"
[ "$fc_status" = 0 ] || exit 3
