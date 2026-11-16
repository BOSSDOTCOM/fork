#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# fork-paths: ok-file runs only on the Google Cloud VM (Linux)
# L1's long-search and time-loss check (the time-management audit of 2026-11-16; switch UseTimeGuards; DESIGN.md
# §5.2 "Search constants", TimeScaleValidatedDepth and TimeGuardPermille). Runs on the cloud worker beside the
# filler, never through the worker's queue (a class b item would stop the filler: production, never stopped):
# started with jobctl as its own job of type measure, its engines at niceness 0, JOBS replay engines and two
# clock games at a time, so it takes about JOBS + 2 of the 8 vCPUs and the filler keeps running (slower) the
# whole time. Resumable: game_replay.py and clock_games.py both skip what is already done.
#
#   bash l1_check.sh ROOT STATS_SHA256 RELEASE_SHA256 [NODES] [JOBS]
#
# ROOT holds src/ (the repository at this branch's switch-on commit), build-stats/fork (its clang-stats build,
# x86-64-v3), build-v3/fork (its clang-v3 build) and l1/games.jsonl (game_replay.py games output). Writes
# /opt/fork/out/l1-check/: clock.jsonl and clock.summary.json (the time-loss check), replay/ (one file per game),
# analysis.json (e2_tm_replay.py --l1), bench-before.txt, bench-after.txt and done.json last.
#
# 1. The time-loss check: 80 clock games (40 openings x both colours) of UseTimeGuards on against off at 60+0.1,
#    TCEC's 600:1 ratio of base to increment (1800+3), Move Overhead 100, Hash 64, Syzygy 3-4-5: the games fall
#    into the low-clock phase where the guard binds; contention with the filler adds latency, as a stress.
# 2. The long searches: 16 games x 8 positions (every 4th of the engine's own, so into the endgames) searched to
#    NODES (default 384M, four times E2's 96M, about three plies deeper: E2's final depth 29.9 on average) with
#    iteration traces, then replayed with nodes as the clock at B = NODES/32 ... NODES/4 under the plain rule,
#    the switch off (the clamp at 60) and on (27), and on with the guard at 4.25 and 2.5 soft budgets (TCEC's
#    1800+3 at 22.5 s and 10 s available): spend over the plain soft limit and over the hard limit, stops at the
#    hard limit, and both by the stop's depth band (30-34, 35-39, 40+). go nodes reads neither guard, so one
#    replay serves both settings.
set -euo pipefail
root=${1:?usage: l1_check.sh ROOT STATS_SHA256 RELEASE_SHA256 [NODES] [JOBS]}
pin_stats=${2:?}
pin_release=${3:?}
nodes=${4:-384000000}
jobs=${5:-2}
out=/opt/fork/out/l1-check
py=/opt/fork/venv/bin/python
stats=$root/build-stats/fork
release=$root/build-v3/fork
mkdir -p "$out"
say() { echo "$(TZ=EST5 date '+%Y-%m-%d %I:%M:%S %p EST') l1: $*"; }
echo "$pin_stats  $stats" | sha256sum -c --quiet
echo "$pin_release  $release" | sha256sum -c --quiet
net=$("$release" version | sed -n 's/^net //p')
want=$(grep -E '^(nodes|signature) ' "$root/src/tests/bench-${net:?}.ref")
for b in "$stats" "$release"; do
  got=$("$b" bench 2>&1 | grep -E '^(nodes|signature) ')
  [ "$got" = "$want" ] || { say "bench before ($b): $got, want $want"; exit 1; }
done
echo "$want" >"$out/bench-before.txt"
say "time-loss check: 80 games at 60+0.1, UseTimeGuards on (a) against off (b), 2 at a time"
"$py" -I "$root/src/tools/measure/clock_games.py" "$release" /opt/fork/inputs/lichess-2026-09.epd "$out/clock" \
  --games 80 --base-ms 60000 --inc-ms 100 --overhead-ms 100 --concurrency 2 --nice 0 --seed 20261116 --hash 64 \
  --syzygy /opt/fork/syzygy --option-a UseTimeGuards=true --option-b UseTimeGuards=false >/dev/null
say "replay: nodes $nodes, $jobs games at once, hash 256, every 4th position, 8 per game"
"$py" -I "$root/src/tools/measure/game_replay.py" run "$stats" "$root/l1/games.jsonl" "$out/replay" --nodes "$nodes" \
  --jobs "$jobs" --nice 0 --stride 4 --max-positions 8 --syzygy /opt/fork/syzygy --report iterations --hash 256
n=$(ls "$out/replay"/game-*.jsonl | wc -l)
[ "$n" -eq "$(wc -l <"$root/l1/games.jsonl")" ] || { say "only $n game files"; exit 1; }
for b in "$stats" "$release"; do
  got=$("$b" bench 2>&1 | grep -E '^(nodes|signature) ')
  [ "$got" = "$want" ] || { say "bench after ($b): $got, want $want"; exit 1; }
done
echo "$want" >"$out/bench-after.txt"
"$py" -I "$root/src/tools/measure/e2_tm_replay.py" --self-test
"$py" -I "$root/src/tools/measure/e2_tm_replay.py" "$out/replay" --l1 --guards 4.25,2.5 --json "$out/analysis.json" \
  >/dev/null
"$py" -I -c 'import json, sys
d = json.load(open(sys.argv[1])); c = json.load(open(sys.argv[2]))
assert d["searches"] > 0 and c["games"] == 80
json.dump({"searches": d["searches"], "games": d["games"], "clock_games": c["games"],
           "time_losses": {k: c[k]["time_losses"] for k in ("a", "b")}}, open(sys.argv[3], "w"))' \
  "$out/analysis.json" "$out/clock.summary.json" "$out/done.json"
say "done"
