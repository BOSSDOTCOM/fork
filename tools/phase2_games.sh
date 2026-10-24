#!/usr/bin/env bash
# Phase 2 acceptance games (DESIGN.md §5.1, test 7): Fork against itself under
# standard cutechess-cli and under fastchess, with concurrency, from seeded
# random openings (tools/make_openings.py; each opening played with both
# colours). Linux (WSL), runners from config/local-test.json.
#
#   tools/phase2_games.sh <fork binary> <openings.epd> <output dir>
#
# Runs, per runner: 200 games at a fast increment (10+0.1), 50 at a fixed
# movetime (st=0.05) and 50 at a fixed depth (depth=3). Then 200 more
# cutechess-cli games at 2+0.02 while every CPU is kept busy by a spin loop
# (the owner's "never lose on time, including under heavy system load").
# No -recover: a crash ends a match and shows in its summary. Each match
# writes <name>.pgn and <name>.log; tools/pgn_summary.py tallies results and
# terminations. Environment: FORK_TOOLS_BIN (default ~/fork-tools/bin),
# CONCURRENCY (default 4).
set -uo pipefail
[ $# -eq 3 ] || { echo "usage: $0 <fork> <openings.epd> <outdir>" >&2; exit 2; }
fork=$(realpath "$1")
book=$(realpath "$2")
out=$3
bin=${FORK_TOOLS_BIN:-$HOME/fork-tools/bin}
conc=${CONCURRENCY:-4}
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$out"
out=$(realpath "$out")

cutechess() {  # name, -each options...
  local name=$1
  shift
  "$bin/cutechess-cli" -engine name=fork-a cmd="$fork" -engine name=fork-b cmd="$fork" \
    -each proto=uci "$@" -openings file="$book" format=epd order=random -srand 20261024 -repeat \
    -concurrency "$conc" -pgnout "$out/$name.pgn" >"$out/$name.log" 2>&1
  echo "$name: cutechess-cli exit $?"
}

fastchess() {  # name, -each options...
  local name=$1
  shift
  "$bin/fastchess" -engine name=fork-a cmd="$fork" -engine name=fork-b cmd="$fork" \
    -each "$@" -openings file="$book" format=epd order=random -srand 20261024 -repeat \
    -concurrency "$conc" -pgnout file="$out/$name.pgn" >"$out/$name.log" 2>&1
  echo "$name: fastchess exit $?"
}

cutechess cutechess-tc tc=10+0.1 -games 2 -rounds 100
cutechess cutechess-st st=0.05 -games 2 -rounds 25
cutechess cutechess-depth tc=inf depth=3 -games 2 -rounds 25
fastchess fastchess-tc tc=10+0.1 -rounds 100
fastchess fastchess-st st=0.05 -rounds 25
fastchess fastchess-depth tc=inf depth=3 -rounds 25

# Under load: one spin loop per CPU, at normal priority, for the whole match.
spinners=()
for _ in $(seq "$(nproc)"); do
  (while :; do :; done) &
  spinners+=($!)
done
cutechess cutechess-load tc=2+0.02 -games 2 -rounds 100
kill "${spinners[@]}" 2>/dev/null
wait "${spinners[@]}" 2>/dev/null

python3 "$here/pgn_summary.py" "$out"/*.pgn
