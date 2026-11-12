#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# E2's long-search check on the cloud worker (docs/gcp-worker.md; a class b queue item). Resumable: game_replay.py
# skips every game whose file exists, so a restarted run continues at the next unfinished game.
#
#   bash e2_run.sh ROOT FORK_SHA256 NODES
#
# ROOT holds src/ (the repository at the engine's commit), build-stats/fork (its clang-stats build), e2/games.jsonl
# (game_replay.py games output) and tools/measure/{e2_tm_replay.py,node_share_fit.py}. Writes /opt/fork/out/e2-ltc/:
# replay/ (one file per game), analysis.json, bench-before.txt, bench-after.txt and done.json last.
set -euo pipefail
root=${1:?usage: e2_run.sh ROOT FORK_SHA256 NODES}
pin=${2:?}
nodes=${3:?}
out=/opt/fork/out/e2-ltc
py=/opt/fork/venv/bin/python
fork=$root/build-stats/fork
mkdir -p "$out"
say() { echo "$(TZ=EST5 date '+%Y-%m-%d %I:%M:%S %p EST') e2: $*"; }
echo "$pin  $fork" | sha256sum -c --quiet
bench() { "$fork" bench 2>&1 | grep -E '^(nodes|signature) '; }
want=$(grep -E '^(nodes|signature) ' "$root/src/tests/bench-r8brft1.ref")
got=$(bench)
[ "$got" = "$want" ] || { say "bench before: $got, want $want"; exit 1; }
echo "$got" >"$out/bench-before.txt"
say "replay: nodes $nodes, 8 games at once, hash 256, 30 positions per game"
"$py" -I "$root/src/tools/measure/game_replay.py" run "$fork" "$root/e2/games.jsonl" "$out/replay" --nodes "$nodes" \
  --jobs 8 --max-positions 30 --syzygy /opt/fork/syzygy --report iterations --hash 256
n=$(ls "$out/replay"/game-*.jsonl | wc -l)
[ "$n" -eq "$(wc -l <"$root/e2/games.jsonl")" ] || { say "only $n game files"; exit 1; }
got=$(bench)
[ "$got" = "$want" ] || { say "bench after: $got, want $want"; exit 1; }
echo "$got" >"$out/bench-after.txt"
"$py" -I "$root/tools/measure/e2_tm_replay.py" --self-test
"$py" -I "$root/tools/measure/e2_tm_replay.py" "$out/replay" --json "$out/analysis.json" >/dev/null
"$py" -I -c 'import json, sys; d = json.load(open(sys.argv[1])); assert d["searches"] > 0; json.dump({"searches": d["searches"], "games": d["games"]}, open(sys.argv[2], "w"))' \
  "$out/analysis.json" "$out/done.json"
say "done"
