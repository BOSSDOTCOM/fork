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
#       [--checkpoint "COMMAND"] [--syzygy DIR] [--meta KEY=VALUE ...]
#
# --syzygy DIR gives both engines the Syzygy 3-4-5 tables in DIR
# (option.SyzygyPath; tools/cloud/fetch_tables.sh, 145 + 145 files); the
# shard meta records tables=3-4-5, or tables=off without it.
#
# Openings: shard I of stage S plays rounds G/2 openings starting at
# 1 + (S * N + I) * G/2 in the order of the book it is given, so no two
# shards or stages share an opening (the book has 2,632,036). The cloud
# gives it fetch_tools.sh's fixed-seed permutation of the book, whose name
# carries the seed (*.shuffled-SEED.epd); the meta records the book's name,
# seed and SHA-256. SIGTERM or SIGINT stops fastchess and records the counts
# with status "interrupted".
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
hash=16 stage=0 conc=$(( $(nproc) > 1 ? $(nproc) - 1 : 1 )) base_opts="" test_opts="" checkpoint="" syzygy="" meta=()
while [ $# -gt 0 ]; do
  case $1 in
    --base) base=$2 ;; --test) test=$2 ;; --fastchess) fastchess=$2 ;; --book) book=$2 ;;
    --shard) shard=$2 ;; --shards) shards=$2 ;; --games) games=$2 ;; --tc) tc=$2 ;; --out) out=$2 ;;
    --stage) stage=$2 ;; --hash) hash=$2 ;; --concurrency) conc=$2 ;; --base-opts) base_opts=$2 ;;
    --test-opts) test_opts=$2 ;; --checkpoint) checkpoint=$2 ;; --meta) meta+=(--meta "$2") ;;
    --syzygy) syzygy=$2 ;;
    *) echo "run_shard.sh: unknown option $1" >&2; exit 2 ;;
  esac
  shift 2
done
for v in base test fastchess book shard shards games tc out; do
  [ -n "${!v:-}" ] || { echo "run_shard.sh: --$v is required" >&2; exit 2; }
done
# Absolute paths: fastchess runs inside the output folder.
for v in base test fastchess book; do
  [ -e "${!v}" ] || { echo "run_shard.sh: --$v ${!v} does not exist" >&2; exit 2; }
  printf -v "$v" '%s' "$(cd "$(dirname "${!v}")" && pwd)/$(basename "${!v}")"
done
tables=off each_tb=()
if [ -n "$syzygy" ]; then
  syzygy=$(cd "$syzygy" && pwd) || { echo "run_shard.sh: --syzygy $syzygy is not a folder" >&2; exit 2; }
  w=$(find "$syzygy" -maxdepth 1 -name '*.rtbw' | wc -l) z=$(find "$syzygy" -maxdepth 1 -name '*.rtbz' | wc -l)
  [ "$w" = 145 ] && [ "$z" = 145 ] ||
    { echo "run_shard.sh: --syzygy $syzygy holds $w .rtbw + $z .rtbz, not the 3-4-5 set (145 + 145)" >&2; exit 2; }
  tables=3-4-5 each_tb=(option.SyzygyPath="$syzygy")
fi
rounds=$(( (games + 1) / 2 ))
start=$(( 1 + (stage * shards + shard) * rounds ))
mkdir -p "$out"
out=$(cd "$out" && pwd)
log=$out/fastchess.log
book_seed=$(basename "$book" | sed -n 's/.*\.shuffled-\([0-9]*\)\.epd$/\1/p')
meta+=(--meta "base_build=$(sha256sum "$base" | cut -c1-16)" --meta "test_build=$(sha256sum "$test" | cut -c1-16)"
       --meta "tc=$tc" --meta "hash=$hash" --meta "base_opts=$base_opts" --meta "test_opts=$test_opts"
       --meta "shard=$shard" --meta "shards=$shards" --meta "stage=$stage" --meta "opening_start=$start"
       --meta "rounds=$rounds" --meta "concurrency=$conc" --meta "tables=$tables"
       --meta "book=$(basename "$book")" --meta "book_seed=${book_seed:-none}"
       --meta "book_sha=$(sha256sum "$book" | cut -d' ' -f1)")

snap() {  # status
  python3 "$here/sprt_merge.py" snapshot "$log" "$out/result.json" --status "$1" "${meta[@]}" || true
  if [ -n "$checkpoint" ]; then bash -c "$checkpoint" || echo "run_shard.sh: checkpoint command failed" >&2; fi
}

cd "$out" || exit 1  # fastchess writes its config.json autosave here
# shellcheck disable=SC2086
"$fastchess" -engine cmd="$test" name=test $test_opts -engine cmd="$base" name=base $base_opts \
  -each tc="$tc" option.Hash="$hash" option.Threads=1 "${each_tb[@]}" \
  -openings file="$book" format=epd order=sequential start="$start" \
  -repeat -rounds "$rounds" -concurrency "$conc" \
  -resign movecount=5 score=1000 twosided=true -draw movenumber=40 movecount=10 score=10 \
  -report penta=true -ratinginterval 50 -recover -pgnout file="$out/games.pgn" >"$log" 2>&1 &
fc=$!
stopped=0
trap 'stopped=1; kill -INT "$fc" 2>/dev/null' TERM INT
while kill -0 "$fc" 2>/dev/null; do
  sleep "${FORK_SHARD_INTERVAL:-60}" &  # seconds between snapshots (tests use 1)
  wait $! 2>/dev/null
  kill -0 "$fc" 2>/dev/null && snap running
done
wait "$fc" 2>/dev/null
if [ "$stopped" = 1 ]; then snap interrupted; else snap done; fi
python3 -c "import json,sys; r=json.load(open(sys.argv[1])); print('shard', r['meta']['shard'], r['status'], 'ptnml', r['ptnml'], 'time losses', r['time_losses'])" "$out/result.json"
# A shard that played nothing, or whose fastchess stopped on a fatal error,
# fails (so its job is red, not a silent empty success).
if grep -q '^Fatal' "$log"; then grep '^Fatal' "$log" >&2; exit 1; fi
if [ "$stopped" = 0 ] && ! grep -q '^Finished game' "$log"; then
  echo "run_shard.sh: no game finished" >&2
  tail -n 5 "$log" >&2
  exit 1
fi
