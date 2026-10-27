#!/usr/bin/env bash
# One shard of a sharded SPRT (docs/kb/tools.md "Cloud SPRT"): a fixed number
# of games between two Fork builds on the shard's own slice of the openings,
# with the same conditions as tools/sprt.sh (Hash, one thread, adjudication,
# each opening played with both colours). Every minute, and when it ends or
# is told to stop, it writes OUT/result.json (the pentanomial counts so far,
# with the test's identity) and runs the checkpoint command, if any, so a
# shard that is stopped (a spot interruption) keeps its finished pairs.
#
#   tools/cloud/run_shard.sh --base EXE --test EXE --fastchess BIN --book EPD \
#       --shard I --shards N --games G --tc TC --out DIR [--stage S] [--hash MB] \
#       [--concurrency C] [--base-opts "option.X=1 ..."] [--test-opts "..."] \
#       [--checkpoint "COMMAND"] [--meta KEY=VALUE ...]
#
# Openings: shard I of stage S plays rounds G/2 openings starting at
# 1 + (S * N + I) * G/2 in the book's order, so no two shards or stages share
# an opening (the book has 2,632,036). SIGTERM or SIGINT stops fastchess and
# records the counts with status "interrupted".
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
hash=16 stage=0 conc=$(( $(nproc) > 1 ? $(nproc) - 1 : 1 )) base_opts="" test_opts="" checkpoint="" meta=()
while [ $# -gt 0 ]; do
  case $1 in
    --base) base=$2 ;; --test) test=$2 ;; --fastchess) fastchess=$2 ;; --book) book=$2 ;;
    --shard) shard=$2 ;; --shards) shards=$2 ;; --games) games=$2 ;; --tc) tc=$2 ;; --out) out=$2 ;;
    --stage) stage=$2 ;; --hash) hash=$2 ;; --concurrency) conc=$2 ;; --base-opts) base_opts=$2 ;;
    --test-opts) test_opts=$2 ;; --checkpoint) checkpoint=$2 ;; --meta) meta+=(--meta "$2") ;;
    *) echo "run_shard.sh: unknown option $1" >&2; exit 2 ;;
  esac
  shift 2
done
for v in base test fastchess book shard shards games tc out; do
  [ -n "${!v:-}" ] || { echo "run_shard.sh: --$v is required" >&2; exit 2; }
done
rounds=$(( (games + 1) / 2 ))
start=$(( 1 + (stage * shards + shard) * rounds ))
mkdir -p "$out"
out=$(cd "$out" && pwd)
log=$out/fastchess.log
meta+=(--meta "base_build=$(sha256sum "$base" | cut -c1-16)" --meta "test_build=$(sha256sum "$test" | cut -c1-16)"
       --meta "tc=$tc" --meta "hash=$hash" --meta "base_opts=$base_opts" --meta "test_opts=$test_opts"
       --meta "shard=$shard" --meta "shards=$shards" --meta "stage=$stage" --meta "opening_start=$start"
       --meta "rounds=$rounds" --meta "concurrency=$conc")

snap() {  # status
  python3 "$here/sprt_merge.py" snapshot "$log" "$out/result.json" --status "$1" "${meta[@]}" || true
  if [ -n "$checkpoint" ]; then bash -c "$checkpoint" || echo "run_shard.sh: checkpoint command failed" >&2; fi
}

cd "$out" || exit 1  # fastchess writes its config.json autosave here
# shellcheck disable=SC2086
"$fastchess" -engine cmd="$test" name=test $test_opts -engine cmd="$base" name=base $base_opts \
  -each tc="$tc" option.Hash="$hash" option.Threads=1 \
  -openings file="$book" format=epd order=sequential start="$start" \
  -repeat -rounds "$rounds" -concurrency "$conc" \
  -resign movecount=5 score=1000 twosided=true -draw movenumber=40 movecount=10 score=10 \
  -report penta=true -ratinginterval 50 -recover -pgnout file="$out/games.pgn" >"$log" 2>&1 &
fc=$!
stopped=0
trap 'stopped=1; kill -INT "$fc" 2>/dev/null' TERM INT
while kill -0 "$fc" 2>/dev/null; do
  sleep 60 &
  wait $! 2>/dev/null
  kill -0 "$fc" 2>/dev/null && snap running
done
wait "$fc" 2>/dev/null
if [ "$stopped" = 1 ]; then snap interrupted; else snap done; fi
python3 -c "import json,sys; r=json.load(open(sys.argv[1])); print('shard', r['meta']['shard'], r['status'], 'ptnml', r['ptnml'], 'time losses', r['time_losses'])" "$out/result.json"
