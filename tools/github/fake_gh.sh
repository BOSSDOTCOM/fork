#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# The fake gh of the GitHub driver tests (tools/github/test_sprt_run.sh, test_h2h_run.sh): a shell script
# that keeps GitHub's state in files under $FAKE_GH and writes shard result.json files on "run download".
# State: busy (runs still to report busy), latest (the newest sprt run id), titles (each run's "ID TITLE",
# newest first), intruder (if present, another run is dispatched right after each of ours), commits (shas
# on GitHub), run.<id> (its inputs), fail.<id>, foreign.<id>, ptnml (each shard's pentanomial counts), and
# ptnml.<base>.<test> (the counts for runs of that pair, when present; head-to-head pairings).
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
    flake api
    grep -qx "${2##*/}" "$st/commits" ;;
  "run list")
    if [[ "$*" == *displayTitle* ]]; then
      cat "$st/titles" 2>/dev/null
    else
      n=$(cat "$st/busy")
      if [ "$n" -gt 0 ]; then echo $((n - 1)) >"$st/busy"; echo 1; else echo 0; fi
    fi ;;
  "workflow run")
    id=$(($(cat "$st/latest") + 1))
    echo "$id busy=$(cat "$st/busy") $*" >>"$st/dispatches"
    for a in "$@"; do case $a in base=* | test=* | stage=*) echo "$a" >>"$st/run.$id" ;; esac; done
    . "$st/run.$id"
    { echo "$id sprt $base $test stage $stage"; cat "$st/titles" 2>/dev/null; } >"$st/titles.new"
    mv "$st/titles.new" "$st/titles"
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
    for k in $(seq 0 $((SHARDS - 1))); do
      mkdir -p "$dir/shard-$stage-$k"
      start=$(((stage * SHARDS + k) * 50 + 1))
      cat >"$dir/shard-$stage-$k/result.json" <<JSON
{"ptnml": $(cat "$ptnml"), "pairs": 50, "finished_games": 100, "time_losses": 0, "abnormal": 0, "status": "done",
 "meta": {"base": "$base", "test": "$test", "stage": "$stage", "shard": "$k", "shards": "$SHARDS", "tc": "8+0.08",
          "hash": "16", "base_opts": "", "test_opts": "", "tables": "3-4-5", "book_sha": "x",
          "opening_start": "$start", "rounds": "50"}}
JSON
    done ;;
  *) echo "fake gh: unexpected $*" >&2; exit 1 ;;
esac
