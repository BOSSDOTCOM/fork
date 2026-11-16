#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# The fake gh of the GitHub driver tests (tools/github/test_sprt_run.sh, test_h2h_run.sh): a shell script
# that keeps GitHub's state in files under $FAKE_GH and writes shard result.json files on "run download".
# State: busy (runs still to report busy), latest (the newest sprt run id), titles (each run's "ID TITLE",
# newest first), intruder (if present, another run is dispatched right after each of ours), commits (shas
# on GitHub), run.<id> (its inputs), fail.<id>, foreign.<id>, ptnml (each shard's pentanomial counts), and
# ptnml.<base>.<test> (the counts for runs of that pair, when present; head-to-head pairings). Since 2026-11-10
# (the driver's capacity check): busy runs are sprt runs; active holds other workflows' runs not completed, one
# "ID WORKFLOW JOBS [CREATED]" per line (JOBS: their jobs not completed; CREATED an ISO time, for the
# ghost-run rule of 2026-11-11); with drain present each jobs query of a run
# lowers its count by one afterwards.
# Since 2026-11-11 (bug review T3, T6): the fake sprt.yml takes the input name, and a run dispatched with it is
# titled "sprt BASE TEST stage N (NAME)", unless noname is present (a ref whose sprt.yml predates the input:
# "workflow view" shows no name input, and a dispatch with it is refused as GitHub does); twin (if present:
# another lane's run of the same commits and stage, named other-lane, is dispatched right after each of ours);
# partial.<id> (that run's shard 0 is left "running") and short.<id> (its shard 0 has one pair fewer than its
# planned rounds). Since 2026-11-13 (CalibratedScore off in every harness): ref.<name> holds the commit the
# ref <name> points to (the driver checks REF's commit before each dispatch). Since 2026-11-15 (--concurrency):
# the fake sprt.yml takes the input concurrency, unless noconcurrency is present (a ref whose sprt.yml predates
# it: "workflow view" shows no such input, and a dispatch with it is refused as GitHub does). Since 2026-11-15 (the
# factorial removal round): the inputs tune and rows likewise (notune, norows); a run dispatched with rows keeps
# them in run.<id>.rows, and its download gives each shard its entry's row, options and design digest in the meta,
# with swaprows.<id> (that run's shards 0 and 1 swap rows: a permutation not followed) and effects (lines
# "OPTION SHIFT": a shard's pentanomial moves SHIFT pairs per switch its row turns off, from the 1/2 bucket to 3/4
# when positive, to 1/4 when negative; tests of the fit through the driver).
st=$FAKE_GH
echo "$*" >>"$st/calls"
# flaky.<kind>: that many failures still to inject for api, conclusion or download (2026-11-08).
flake() {
  local f=$st/flaky.$1 n
  [ -f "$f" ] || return 0
  n=$(cat "$f")
  [ "$n" -gt 0 ] || return 0
  echo $((n - 1)) >"$f"
  echo "fake gh: $1: connection reset (injected)" >&2
  exit 1
}
case "$1 $2" in
  "api "*)
    case $2 in
      */actions/runs/*/jobs*)  # a run's jobs not completed (the driver's capacity check)
        rid=${2#*/actions/runs/}
        rid=${rid%%/*}
        n=$(awk -v r="$rid" '$1 == r {print $3}' "$st/active" 2>/dev/null)
        if [ -f "$st/drain" ] && [ "${n:-0}" -gt 0 ]; then
          awk -v r="$rid" '$1 == r {$3 = $3 - 1} {print}' "$st/active" >"$st/active.new"
          mv "$st/active.new" "$st/active"
        fi
        echo "${n:-0}" ;;
      *)
        flake api
        # ref.<name>: the commit a ref (the driver's REF) points to, printed as gh --jq .sha prints it.
        if [ -f "$st/ref.${2##*/}" ]; then cat "$st/ref.${2##*/}"; else grep -qx "${2##*/}" "$st/commits"; fi ;;
    esac ;;
  "run list")
    if [[ "$*" == *displayTitle* ]]; then
      cat "$st/titles" 2>/dev/null
    else  # the runs not completed, "ID WORKFLOW"
      n=$(cat "$st/busy")
      if [ "$n" -gt 0 ]; then echo $((n - 1)) >"$st/busy"; echo "900 sprt"; fi
      [ -f "$st/active" ] && awk '{print $1, $2, $4}' "$st/active"
      true
    fi ;;
  "workflow view")  # the fake sprt.yml's inputs (the driver looks for the name input)
    printf 'name: sprt\non:\n  workflow_dispatch:\n    inputs:\n      base: {description: "Base", required: true}\n'
    [ -f "$st/noname" ] || printf '      name: {description: "The SPRT name", required: false, default: ""}\n'
    [ -f "$st/noconcurrency" ] ||
      printf '      concurrency: {description: "Games at once per shard", required: false, default: ""}\n'
    [ -f "$st/notune" ] || printf '      tune: {description: "on: both sides one tuning build", required: false, default: ""}\n'
    [ -f "$st/norows" ] || printf '      rows: {description: "Per-shard test options", required: false, default: ""}\n'
    printf 'concurrency:\n  group: sprt\n' ;;  # the workflow's own concurrency group, not an input
  "workflow run")
    for input in tune rows; do
      if [ -f "$st/no$input" ] && [[ " $* " == *" $input="* ]]; then
        echo "could not create workflow dispatch event: HTTP 422: Unexpected inputs provided: [\"$input\"]" >&2
        exit 1
      fi
    done
    if [ -f "$st/noname" ] && [[ " $* " == *" name="* ]]; then
      echo "could not create workflow dispatch event: HTTP 422: Unexpected inputs provided: [\"name\"]" >&2
      exit 1
    fi
    if [ -f "$st/noconcurrency" ] && [[ " $* " == *" concurrency="* ]]; then
      echo "could not create workflow dispatch event: HTTP 422: Unexpected inputs provided: [\"concurrency\"]" >&2
      exit 1
    fi
    id=$(($(cat "$st/latest") + 1))
    held=$(awk '{s += $3} END {print s + 0}' "$st/active" 2>/dev/null)
    echo "$id busy=$(cat "$st/busy") jobs=${held:-0} $*" >>"$st/dispatches"
    for a in "$@"; do
      case $a in
        base=* | test=* | stage=* | name=*) echo "$a" >>"$st/run.$id" ;;
        rows=?*) printf '%s' "${a#rows=}" >"$st/run.$id.rows" ;;
      esac
    done
    name=
    . "$st/run.$id"
    { echo "$id sprt $base $test stage $stage${name:+ ($name)}"; cat "$st/titles" 2>/dev/null; } >"$st/titles.new"
    mv "$st/titles.new" "$st/titles"
    if [ -f "$st/twin" ]; then  # another lane's run of the same commits and stage
      id=$((id + 1))
      twin=
      [ -f "$st/noname" ] || twin=other-lane
      printf 'base=%s\ntest=%s\nstage=%s\n' "$base" "$test" "$stage" >"$st/run.$id"
      { echo "$id sprt $base $test stage $stage${twin:+ ($twin)}"; cat "$st/titles"; } >"$st/titles.new"
      mv "$st/titles.new" "$st/titles"
    fi
    if [ -f "$st/intruder" ]; then  # someone else's run, newer than ours
      id=$((id + 1))
      printf 'base=%s\ntest=%s\nstage=0\n' "$base" ffffffffffffffffffffffffffffffffffffffff >"$st/run.$id"
      { echo "$id sprt $base ffffffffffffffffffffffffffffffffffffffff stage 0"; cat "$st/titles"; } >"$st/titles.new"
      mv "$st/titles.new" "$st/titles"
    fi
    echo $id >"$st/latest" ;;
  "run view")
    if [[ "$*" == *conclusion* ]]; then
      flake conclusion
      if [ -f "$st/fail.$3" ]; then echo failure; else echo success; fi
    else
      echo completed
    fi ;;
  "run download")
    flake download
    id=$3
    dir=${!#}  # the last argument, -D's
    . "$st/run.$id"
    ptnml=$st/ptnml
    [ -f "$st/ptnml.$base.$test" ] && ptnml=$st/ptnml.$base.$test
    [ -f "$st/foreign.$id" ] && test=ffffffffffffffffffffffffffffffffffffffff
    # The rows (a factorial stage): "ROW|OPTS|DESIGN|PTNML" per shard, from the dispatched table (on stdin, so no
    # path conversion) and the effects file.
    shard_rows=()
    if [ -f "$st/run.$id.rows" ]; then
      mapfile -t shard_rows < <("$PYTHON" -I -c '
import json, sys
table, base = json.load(sys.stdin), json.loads(sys.argv[1])
effects = dict((name, int(shift)) for name, shift in (line.split() for line in sys.argv[2].splitlines() if line.strip()))
entries = table["shard_rows"]
if sys.argv[3] == "1":
    entries[0], entries[1] = entries[1], entries[0]
for e in entries:
    shift = sum(effects.get(o.split("=")[0][len("option."):], 0) for o in e["opts"].split())
    p = list(base)
    if shift > 0:
        p[2] -= shift; p[3] += shift
    else:
        p[2] += shift; p[1] -= shift
    print("%d|%s|%s|%s" % (e["row"], e["opts"], table["design"], json.dumps(p)))
' "$(cat "$ptnml")" "$(cat "$st/effects" 2>/dev/null)" "$([ -f "$st/swaprows.$id" ] && echo 1 || echo 0)" \
        <"$st/run.$id.rows" | tr -d '\r')
    fi
    for k in $(seq 0 $((SHARDS - 1))); do
      mkdir -p "$dir/shard-$stage-$k"
      start=$(((stage * SHARDS + k) * 50 + 1))
      status=done rounds=50
      [ "$k" = 0 ] && [ -f "$st/partial.$id" ] && status=running
      [ "$k" = 0 ] && [ -f "$st/short.$id" ] && rounds=51
      counts=$(cat "$ptnml") test_opts= row_meta=
      if [ "${#shard_rows[@]}" -gt 0 ]; then
        IFS='|' read -r r test_opts digest counts <<<"${shard_rows[$k]}"
        row_meta=", \"row\": \"$r\", \"design\": \"$digest\""
      fi
      cat >"$dir/shard-$stage-$k/result.json" <<JSON
{"ptnml": $counts, "pairs": 50, "finished_games": 100, "time_losses": 0, "abnormal": 0, "status": "$status",
 "meta": {"base": "$base", "test": "$test", "stage": "$stage", "shard": "$k", "shards": "$SHARDS", "tc": "8+0.08",
          "hash": "16", "base_opts": "", "test_opts": "$test_opts", "tables": "3-4-5", "book_sha": "x",
          "opening_start": "$start", "opening_end": "$((start + 49))", "rounds": "$rounds"$row_meta}}
JSON
      # progress (if present): the shard's progress artifact too (tools/cloud/shard_progress.py; 2026-11-14), as
      # a real run's download holds it beside shard-*; the file progress.name, if present, names its file (fault injection; default progress.json).
      if [ -f "$st/progress" ]; then
        mkdir -p "$dir/progress-$stage-$k"
        cat >"$dir/progress-$stage-$k/$(cat "$st/progress.name" 2>/dev/null || echo progress.json)" <<JSON
{"format": "fork-shard-progress/1", "state": "final", "shard_status": "$status", "upload_seq": 3,
 "run_id": $id, "stage": $stage, "shard": $k, "shards": $SHARDS, "base": "$base", "test": "$test",
 "games_planned": 100, "pairs_planned": 50, "games_finished": 100, "pairs_finished": 50, "ptnml": $(cat "$ptnml"),
 "wdl": {"wins": 0, "draws": 0, "losses": 0}, "time_losses": 0, "abnormal": 0}
JSON
      fi
    done ;;
  *) echo "fake gh: unexpected $*" >&2; exit 1 ;;
esac
