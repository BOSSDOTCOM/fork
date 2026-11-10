#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# The label-depth experiment's generation (docs/research/label-depth/; design: report.md section 1 on branch
# research/labels-teacher, approved by the owner on 2026-11-09): the three arms D20, D50 and D100 at the same
# time, 3 threads each (layout A), from one PGO build of phase-4's head, with g4b's standing settings except
# --nodes and --hash-mb, and the same seed in every arm. Runs in WSL under the job supervisor:
#
#   jobctl.py start datagen NAME -- wsl.exe -d Ubuntu -- bash ld_arms.sh PREFIX OUT SEED SECONDS POS20 POS50 POS100
#
# PREFIX names the runs (PREFIX-d20, PREFIX-d50, PREFIX-d100; shards PREFIX-dNN-wWW-KKKK.vf), OUT holds one folder
# per arm, SECONDS stops every arm at once after that wall time (0: none), POSnn are fork_datagen's --positions
# targets (an arm that reaches its target ends by itself and writes its run json). A stop of the job (SIGTERM, a
# hangup, or the Windows side's wsl.exe ending, seen as a failed write of the heartbeat) stops all three arms
# together, so they always share the same wall time.
set -euo pipefail
PREFIX=$1 OUT=$2 SEED=$3 LIMIT=$4
shift 4
POS=("$@")
[ ${#POS[@]} -eq 3 ] || { echo "three --positions targets needed"; exit 2; }
BIN=$HOME/fork-data/ld-builds/pgo
# lichess-2026-09.epd's openings for this seed's first 2.5 M games, in the order that gives each of those games
# the full book's opening (ld_book.py; byte-identical shards checked by ld_book_check.sh), because each process
# keeps its whole book in memory and three copies of the full book (1.4 GB each) do not fit WSL's 5.9 GB.
# One file per seed: segment 1 used 2026110900; the resume after memwatch's stop (2026-11-10) uses 2026110901.
OPENINGS=$HOME/fork-data/openings/lichess-2026-09-s$SEED-k2500000.epd
case $SEED in
  2026110900) OPENINGS_SHA256=f705366e5a3f4b803ce392f2b9da2f474e181bbcefecef0e0170e569ccdae736 ;;
  2026110901) OPENINGS_SHA256=da1c2dd85186c7e291cb73fb1c405b1fac4c329d96d75298ded57ae9ed090374 ;;
  *) echo "no openings file is built for seed $SEED"; exit 2 ;;
esac
TABLES=$HOME/fork-tools/syzygy/3-4-5
ENGINE_COMMIT=a4ee6740026118674d757b77a960e2d8b2c54abe
NET=s512ppr3
WANT="nodes 10374064 signature 677c436fa145e07f "
ARMS=(d20 d50 d100)
NODES=(20000 50000 100000)
HASH=(1 3 5)
THREADS=3
say() { echo "$(TZ=EST5 date '+%Y-%m-%d %I:%M:%S %p EST') $PREFIX: $*"; }

mkdir -p "$OUT"
for a in "${ARMS[@]}"; do
  d=$OUT/$PREFIX-$a
  mkdir -p "$d"
  [ -z "$(ls -A "$d" 2>/dev/null)" ] || { say "$d is not empty"; exit 1; }
done
# Other jobs' fork_datagen (a pilot's own build) may run; only this experiment's runs must not.
if pgrep -f -- "--run $PREFIX-d" >/dev/null; then say "a $PREFIX arm is already running"; exit 1; fi
ver=$("$BIN/fork" version)
echo "$ver" | grep -qx "net $NET" || { say "the binary's network is not $NET"; exit 1; }
echo "$ver" | grep -E '^Fork ' | grep -q "+${ENGINE_COMMIT:0:7}" || { say "the binary is not from $ENGINE_COMMIT"; exit 1; }
got=$("$BIN/fork" bench 2>&1 | grep -E '^(nodes|signature) ' | tr '\n' ' ')
[ "$got" = "$WANT" ] || { say "BENCH MISMATCH ($got, want $WANT)"; exit 1; }
say "bench ok: $got"
echo "$OPENINGS_SHA256  $OPENINGS" | sha256sum -c
sha256sum "$BIN/fork_datagen" "$BIN/fork" | sed "s#$HOME#~#g"

pids=()
stop_all() {
  trap - PIPE HUP TERM INT
  exec >>"$OUT/$PREFIX-runner.log" 2>&1
  say "stopping every arm ($1)"
  for p in "${pids[@]}"; do kill -TERM "$p" 2>/dev/null || true; done
  for p in "${pids[@]}"; do wait "$p" 2>/dev/null || true; done
  echo "stopped $(date +%s)" >>"$OUT/$PREFIX-times.txt"
  say "stopped"
  exit 0
}
trap 'stop_all "a hangup or a closed output (the job was stopped)"' PIPE HUP
trap 'stop_all "SIGTERM or SIGINT (the job was stopped)"' TERM INT

start=$(date +%s)
echo "started $start" >"$OUT/$PREFIX-times.txt"
for i in 0 1 2; do
  a=${ARMS[$i]}
  d=$OUT/$PREFIX-$a
  cp "$BIN/fork" "$BIN/fork_datagen" "$d/"
  (cd "$d" && exec ./fork_datagen --openings "$OPENINGS" --out "$d" \
     --run "$PREFIX-$a" --positions "${POS[$i]}" --nodes "${NODES[$i]}" --threads "$THREADS" --seed "$SEED" \
     --hash-mb "${HASH[$i]}" --shard-mb 1024 --tables "$TABLES" \
     --adjudicate-cp 700 --adjudicate-plies 8 \
     --save-percent 50 --unsaved-nodes 4000 --check-nodes 2000 \
     >"$d/$PREFIX-$a.log" 2>&1 </dev/null) &
  pids+=($!)
  say "$PREFIX-$a: --nodes ${NODES[$i]} --hash-mb ${HASH[$i]} --positions ${POS[$i]} --threads $THREADS --seed $SEED (pid $!)"
done
PREFIX=$PREFIX bash -c '
  prev=($(head -1 /proc/stat))
  while sleep 60 && pgrep -f -- "--run $PREFIX-d" >/dev/null; do
    cur=($(head -1 /proc/stat))
    idle=$(( ${cur[4]} + ${cur[5]} - ${prev[4]} - ${prev[5]} ))
    total=0; for i in 1 2 3 4 5 6 7 8; do total=$(( total + ${cur[$i]} - ${prev[$i]} )); done
    echo "$(TZ=EST5 date "+%Y-%m-%d %I:%M %p") load1 $(cut -d" " -f1 /proc/loadavg) busy $(( 100 * (total - idle) / total ))%"
    prev=("${cur[@]}")
  done' >"$OUT/$PREFIX-cpu-load.log" 2>&1 </dev/null &

beat=0
while :; do
  sleep 15
  live=0
  for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null && live=$((live + 1)); done
  if [ "$live" -eq 0 ]; then
    for p in "${pids[@]}"; do wait "$p" 2>/dev/null || true; done
    echo "finished $(date +%s)" >>"$OUT/$PREFIX-times.txt"
    say "every arm finished at its target"
    exit 0
  fi
  now=$(date +%s)
  if [ "$LIMIT" -gt 0 ] && [ $((now - start)) -ge "$LIMIT" ]; then
    stop_all "the wall-time limit of $LIMIT s"
  fi
  beat=$((beat + 1))
  if [ $((beat % 4)) -eq 0 ]; then  # once a minute: a closed pipe (wsl.exe gone) raises SIGPIPE here
    line=""
    for a in "${ARMS[@]}"; do line+="$a $(tail -1 "$OUT/$PREFIX-$a/$PREFIX-$a.log" 2>/dev/null | cut -d: -f2 | cut -d, -f2); "; done
    say "$((now - start)) s, $live live: $line" || stop_all "a failed heartbeat write"
  fi
done
