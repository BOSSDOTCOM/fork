#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
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
#       [--checkpoint "COMMAND"] [--syzygy DIR] [--meta KEY=VALUE ...] [--rows FILE]
#
# Per-shard rows (the factorial removal round, DESIGN.md §5.6 step 18; design
# docs/research/phase4-designs/factorial-removal-round.md §3.1, §3.3): with
# --rows FILE (a stage's rows table, JSON {"design": SHA-256, "shard_rows":
# [{"row": R, "opts": "option.X=false ..."}, ...]} in shard order, as
# tools/github/factorial_fit.py rows writes it) this shard's test engine
# plays entry I's options (--test-opts must then be empty), and the meta
# records row=R and design=SHA-256 beside test_opts (the merge checks all
# three against the recomputed permutation). The table must have exactly N
# entries. Without --rows nothing changes.
#
# Search threads (Lazy SMP, DESIGN.md §5.6 step 17a; owner, 2026-11-15): an
# engine plays with option.Threads=N when its --base-opts or --test-opts say
# so, else 1, each set on that engine alone. With more than one thread on
# either side the games at once never put more search threads on the machine
# than it has CPUs (nproc): --concurrency defaults to nproc / the larger
# thread count (at least 1; ponder is off, so one engine of a game searches
# at a time), and a --concurrency or a thread count that would exceed nproc
# is refused. One-thread games keep the default of nproc - 1. The meta
# records base_threads and test_threads.
#
# Per-engine time controls (idea 212's time odds; owner, 2026-11-22): a
# tc=SECONDS+INCREMENT among an engine's --base-opts or --test-opts is that
# engine's own clock. Then -each carries no tc (fastchess's -each tc would
# override it), the engine without one plays --tc, and the meta records
# base_tc and test_tc. At most one tc= per engine, of that form, else refused.
# Without any, the fastchess command line is exactly as before (-each tc=TC).
# The line below is the capability the GitHub driver looks for in REF's copy
# of this file before it dispatches a per-side tc (tools/github/sprt_run.sh).
# capability: per-engine-tc
#
# --syzygy DIR gives both engines the Syzygy 3-4-5 tables in DIR
# (option.SyzygyPath; tools/cloud/fetch_tables.sh, 145 + 145 files); the
# shard meta records tables=3-4-5, or tables=off without it.
#
# Openings: shard I of stage S plays rounds G/2 openings starting at
# 1 + (S * N + I) * G/2 in the order of the book it is given, so no two
# shards or stages run with the same G and N share an opening (the book has
# 2,632,036); the meta records the range (opening_start, opening_end), and
# sprt_merge.py refuses shards whose ranges intersect. The cloud
# gives it fetch_tools.sh's fixed-seed permutation of the book, whose name
# carries the seed (*.shuffled-SEED.epd); the meta records the book's name,
# seed and SHA-256. SIGTERM or SIGINT stops fastchess and records the counts
# with status "interrupted".
#
# Final status (result.json, with fastchess's exit status as
# meta.fastchess_exit): "done" when every planned pair finished; "short"
# when fastchess ended normally with fewer pairs; "failed" when fastchess
# exited non-zero (a crash) or reported a fatal error; "interrupted" when
# stopped. The script exits non-zero for "short" and "failed" (so the job is
# red), 0 for "done" and "interrupted" (the merge counts finished pairs).
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
hash=16 stage=0 conc="" base_opts="" test_opts="" checkpoint="" syzygy="" rows="" meta=()
while [ $# -gt 0 ]; do
  case $1 in
    --base) base=$2 ;; --test) test=$2 ;; --fastchess) fastchess=$2 ;; --book) book=$2 ;;
    --shard) shard=$2 ;; --shards) shards=$2 ;; --games) games=$2 ;; --tc) tc=$2 ;; --out) out=$2 ;;
    --stage) stage=$2 ;; --hash) hash=$2 ;; --concurrency) conc=$2 ;; --base-opts) base_opts=$2 ;;
    --test-opts) test_opts=$2 ;; --checkpoint) checkpoint=$2 ;; --meta) meta+=(--meta "$2") ;;
    --syzygy) syzygy=$2 ;; --rows) rows=$2 ;;
    *) echo "run_shard.sh: unknown option $1" >&2; exit 2 ;;
  esac
  shift 2
done
for v in base test fastchess book shard shards games tc out; do
  [ -n "${!v:-}" ] || { echo "run_shard.sh: --$v is required" >&2; exit 2; }
done
# --rows: this shard's row of the stage's table (its test options), checked before anything runs.
if [ -n "$rows" ]; then
  [ -z "$test_opts" ] ||
    { echo "run_shard.sh: --rows gives the test engine's options; --test-opts must be empty" >&2; exit 2; }
  picked=$(python3 - "$rows" "$shard" "$shards" <<'PY'
import json, re, sys
path, shard, shards = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
try:
    table = json.load(open(path, encoding='utf-8'))
    entries, design = table['shard_rows'], table['design']
    assert isinstance(entries, list) and len(entries) == shards, f'{len(entries)} entries for {shards} shards'
    assert 0 <= shard < shards, f'shard {shard} of {shards}'
    assert isinstance(design, str) and re.fullmatch(r'[0-9a-f]{64}', design), f'design {design!r} is not a SHA-256'
    row, opts = entries[shard]['row'], entries[shard]['opts']
    assert isinstance(row, int) and not isinstance(row, bool) and row >= 0, f'row {row!r}'
    assert isinstance(opts, str) and opts.split() and all(
        re.fullmatch(r'option\.[A-Za-z][A-Za-z0-9_]*=[A-Za-z0-9.+-]+', o) for o in opts.split()), f'options {opts!r}'
except Exception as e:  # noqa: BLE001 (any malformed table is refused alike)
    sys.exit(f'run_shard.sh: --rows {path}: {e}')
print(row)
print(design)
print(' '.join(opts.split()))
PY
  ) || exit 2
  row=$(sed -n 1p <<<"$picked") design=$(sed -n 2p <<<"$picked") test_opts=$(sed -n 3p <<<"$picked")
  meta+=(--meta "row=$row" --meta "design=$design")
fi
# Each engine's search threads: the last option.Threads=N in its options, else 1.
threads_in() {  # options -> N
  local t
  t=$(printf '%s\n' $1 | sed -n 's/^option\.Threads=\([0-9][0-9]*\)$/\1/p' | tail -1)
  echo "${t:-1}"
}
base_threads=$(threads_in "$base_opts") test_threads=$(threads_in "$test_opts")
threads=$(( base_threads > test_threads ? base_threads : test_threads ))
cpus=$(nproc)
if [ "$threads" -gt 1 ]; then
  [ "$threads" -le "$cpus" ] ||
    { echo "run_shard.sh: $threads search threads per engine on $cpus CPUs" >&2; exit 2; }
  [ -n "$conc" ] || conc=$(( cpus / threads ))
  [ $(( conc * threads )) -le "$cpus" ] ||
    { echo "run_shard.sh: --concurrency $conc x $threads search threads exceeds the $cpus CPUs" >&2; exit 2; }
fi
[ -n "$conc" ] || conc=$(( cpus > 1 ? cpus - 1 : 1 ))
# Threads on each engine alone (an -each Threads would set the other's too);
# the meta keeps the options as given (sprt_merge.py compares them).
base_engine_opts=$base_opts test_engine_opts=$test_opts
case " $base_opts " in *" option.Threads="*) ;; *) base_engine_opts="${base_opts:+$base_opts }option.Threads=1" ;; esac
case " $test_opts " in *" option.Threads="*) ;; *) test_engine_opts="${test_opts:+$test_opts }option.Threads=1" ;; esac
# Per-engine time controls (the header): each engine's tc=T, if any.
own_tc() {  # options -> the value of its one tc=T, or nothing; status 1 for two of them or a malformed one
  local o t= n=0
  for o in $1; do
    case $o in tc=*) n=$((n + 1)) t=${o#tc=} ;; esac
  done
  [ "$n" -le 1 ] || return 1
  [ "$n" = 0 ] || [[ $t =~ ^[0-9]+(\.[0-9]+)?\+[0-9]+(\.[0-9]+)?$ ]] || return 1
  printf '%s' "$t"
}
base_tc=$(own_tc "$base_opts") && test_tc=$(own_tc "$test_opts") ||
  { echo "run_shard.sh: an engine's options take at most one tc=SECONDS+INCREMENT (e.g. tc=4+0.04)" >&2; exit 2; }
each_tc=(tc="$tc")
if [ -n "$base_tc$test_tc" ]; then
  each_tc=()
  [ -n "$base_tc" ] || { base_tc=$tc; base_engine_opts="$base_engine_opts tc=$tc"; }
  [ -n "$test_tc" ] || { test_tc=$tc; test_engine_opts="$test_engine_opts tc=$tc"; }
  meta+=(--meta "base_tc=$base_tc" --meta "test_tc=$test_tc")
fi
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
       --meta "shard=$shard" --meta "shards=$shards" --meta "stage=$stage" --meta "opening_start=$start" --meta "opening_end=$((start + rounds - 1))"
       --meta "rounds=$rounds" --meta "concurrency=$conc" --meta "tables=$tables"
       --meta "base_threads=$base_threads" --meta "test_threads=$test_threads"
       --meta "book=$(basename "$book")" --meta "book_seed=${book_seed:-none}"
       --meta "book_sha=$(sha256sum "$book" | cut -d' ' -f1)")

snap() {  # status
  python3 "$here/sprt_merge.py" snapshot "$log" "$out/result.json" --status "$1" "${meta[@]}" || true
  if [ -n "$checkpoint" ]; then bash -c "$checkpoint" || echo "run_shard.sh: checkpoint command failed" >&2; fi
}

cd "$out" || exit 1  # fastchess writes its config.json autosave here
# shellcheck disable=SC2086
"$fastchess" -engine cmd="$test" name=test $test_engine_opts -engine cmd="$base" name=base $base_engine_opts \
  -each "${each_tc[@]}" option.Hash="$hash" option.CalibratedScore=false "${each_tb[@]}" \
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
fc_status=$?
meta+=(--meta "fastchess_exit=$fc_status")
if [ "$stopped" = 1 ]; then
  snap interrupted
elif [ "$fc_status" != 0 ] || grep -q '^Fatal' "$log"; then
  snap failed
else
  snap done  # becomes "short" if fewer pairs than planned finished
fi
status=$(python3 -c "import json,sys; r=json.load(open(sys.argv[1])); print(r['status'])" "$out/result.json")
python3 -c "import json,sys; r=json.load(open(sys.argv[1])); print('shard', r['meta']['shard'], r['status'], 'pairs', r['pairs'], 'of', r['meta']['rounds'], 'ptnml', r['ptnml'], 'time losses', r['time_losses'], 'fastchess exit', r['meta']['fastchess_exit'])" "$out/result.json"
# A shard that crashed, played nothing or fell short fails (so its job is
# red, not a silent partial success).
case $status in
  failed | short)
    grep '^Fatal' "$log" >&2
    grep -q '^Finished game' "$log" || echo "run_shard.sh: no game finished" >&2
    echo "run_shard.sh: shard $status (fastchess exit status $fc_status)" >&2
    tail -n 5 "$log" >&2
    exit 1
    ;;
  done | interrupted) ;;
  *)  # bug review 2026-11-11, T3: the final snapshot failed, leaving the last "running" one (or none)
    echo "run_shard.sh: the final snapshot was not written (result.json status '${status:-none}')" >&2
    exit 1
    ;;
esac
