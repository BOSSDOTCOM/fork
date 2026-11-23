#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Dry-run test of tools/cloud/run_shard.sh with a fake fastchess (no engine
# runs, no game is played): what it passes to fastchess, what it records in
# result.json, and its exit status. Uses python3, or $PYTHON if set.
#
#   bash tools/cloud/test_run_shard.sh
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
failures=0
check() {  # description, command...
  local what=$1
  shift
  if "$@"; then echo "PASS  $what"; else echo "FAIL  $what"; failures=$((failures + 1)); fi
}

# python3 for run_shard.sh: $PYTHON, else the first python that runs.
mkdir -p "$tmp/bin"
py=${PYTHON:-}
if [ -z "$py" ]; then
  for c in python3 python; do
    if command -v "$c" >/dev/null && "$c" -c 'pass' 2>/dev/null; then py=$(command -v "$c"); break; fi
  done
fi
[ -n "$py" ] || { echo "test_run_shard.sh: no python found" >&2; exit 1; }
printf '#!/bin/sh\nexec "%s" -B "$@"\n' "$py" >"$tmp/bin/python3"
chmod +x "$tmp/bin/python3"
export PATH="$tmp/bin:$PATH"

# Fake fastchess: FAKE_FC=full (every pair asked for), crash (2 pairs, then
# SIGSEGV), fail (2 pairs, then exit 1), short (2 pairs, exit 0) or slow (every
# pair, then 3 seconds before exit 0, so a "running" snapshot is written).
# Arguments go to $tmp/args.
cat >"$tmp/fastchess" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$FAKE_ARGS"
rounds=0
while [ $# -gt 0 ]; do [ "$1" = -rounds ] && rounds=$2; shift; done
n=$rounds
[ "${FAKE_FC:-full}" = full ] || n=2
for k in $(seq 1 "$n"); do
  echo "Finished game $((2 * k - 1)) (test vs base): 1-0 {White mates}"
  echo "Finished game $((2 * k)) (base vs test): 1/2-1/2 {Draw by 3-fold repetition}"
done
case ${FAKE_FC:-full} in
  slow) sleep 3 ;;
  crash) kill -SEGV $$ ;;
  fail) exit 1 ;;
esac
exit 0
EOF
chmod +x "$tmp/fastchess"
printf '#!/bin/sh\n' >"$tmp/base" && printf '#!/bin/sh\n' >"$tmp/test" && chmod +x "$tmp/base" "$tmp/test"
echo 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -' >"$tmp/book.epd"
mkdir -p "$tmp/tb" "$tmp/tb-short"
for i in $(seq 1 145); do : >"$tmp/tb/T$i.rtbw"; : >"$tmp/tb/T$i.rtbz"; done
: >"$tmp/tb-short/KPvK.rtbw"

shard() {  # out dir, extra run_shard.sh arguments... ; status in $status
  local out=$1
  shift
  FAKE_ARGS="$tmp/args" FORK_SHARD_INTERVAL=1 bash "$here/run_shard.sh" --base "$tmp/base" --test "$tmp/test" \
    --fastchess "$tmp/fastchess" --book "$tmp/book.epd" --shard 1 --shards 4 --games 10 --tc 8+0.08 \
    --out "$tmp/$out" --concurrency 2 "$@" >"$tmp/$out.txt" 2>&1
  status=$?
}
meta() {  # out dir, key -> value
  "$py" -c 'import json, sys; print(json.load(open(sys.argv[1]))["meta"].get(sys.argv[2], ""))' "$tmp/$1/result.json" "$2"
}
arg() { grep -qx -- "$1" "$tmp/args"; }

# D-2: tables for both engines when --syzygy is given, recorded in the meta.
shard tables --syzygy "$tmp/tb"
check "tables: exit 0" test "$status" = 0
check "tables: SyzygyPath for both engines (-each)" arg "option.SyzygyPath=$(cd "$tmp/tb" && pwd)"
check "tables: meta tables=3-4-5" test "$(meta tables tables)" = 3-4-5
shard notables
check "no tables: exit 0" test "$status" = 0
check "no tables: no SyzygyPath" bash -c "! grep -q SyzygyPath '$tmp/args'"
check "no tables: meta tables=off" test "$(meta notables tables)" = off
shard badtables --syzygy "$tmp/tb-short"
check "an incomplete set is refused" test "$status" = 2

# U-3: the book's name, permutation seed and SHA-256 are in the meta.
check "book: name" test "$(meta notables book)" = book.epd
check "book: no seed for a book in file order" test "$(meta notables book_seed)" = none
check "book: SHA-256" test "$(meta notables book_sha)" = "$(sha256sum "$tmp/book.epd" | cut -d' ' -f1)"
cp "$tmp/book.epd" "$tmp/UHO.shuffled-42.epd"
shard seeded --book "$tmp/UHO.shuffled-42.epd"
check "book: seed from a shuffled book's name" test "$(meta seeded book_seed)" = 42

# U-4: the opening range is recorded at both ends (shard 1 of 4, 5 rounds).
check "openings 6-10" test "$(meta notables opening_start)-$(meta notables opening_end)" = 6-10

# U-9: fastchess's exit status decides; fewer pairs than planned is short.
status_of() {  # out dir -> result.json status
  "$py" -c 'import json, sys; print(json.load(open(sys.argv[1]))["status"])' "$tmp/$1/result.json"
}
check "all pairs: done" test "$(status_of notables)" = done
check "all pairs: fastchess exit 0 recorded" test "$(meta notables fastchess_exit)" = 0
FAKE_FC=crash shard crash
check "crash: exit 1" test "$status" = 1
check "crash: status failed" test "$(status_of crash)" = failed
check "crash: fastchess exit 139 (SIGSEGV) recorded" test "$(meta crash fastchess_exit)" = 139
FAKE_FC=fail shard fail
check "fastchess error: exit 1, failed" test "$status-$(status_of fail)" = 1-failed
FAKE_FC=short shard short
check "too few pairs: exit 1, short" test "$status-$(status_of short)" = 1-short

# Bug review 2026-11-11, T3: a final snapshot that fails (here the python3 that would write "done") leaves the
# last "running" one; the shard exits 1 instead of passing as green with a partial result.
mkdir -p "$tmp/bin-nofinal"
printf '#!/bin/sh\ncase "$*" in *"--status done"*) exit 1 ;; esac\nexec "%s" -B "$@"\n' "$py" >"$tmp/bin-nofinal/python3"
chmod +x "$tmp/bin-nofinal/python3"
PATH="$tmp/bin-nofinal:$PATH" FAKE_FC=slow shard nofinal
check "a failed final snapshot: exit 1, result still running" test "$status-$(status_of nofinal)" = 1-running
check "a failed final snapshot is named" grep -q "the final snapshot was not written (result.json status 'running')" "$tmp/nofinal.txt"

# Lazy SMP (owner, 2026-11-15): each engine's own Threads, never an -each Threads; the games at once
# never put more search threads than CPUs on the machine.
cpus=$(nproc)
shard onethread
check "one thread: Threads=1 on each engine, none in -each" \
  bash -c "[ \$(grep -cx 'option.Threads=1' '$tmp/args') = 2 ] && ! grep -q '^tc=.*Threads' '$tmp/args'"
check "one thread: the meta's thread counts" test "$(meta onethread base_threads)-$(meta onethread test_threads)" = 1-1
check "one thread: the meta's options as given" test "$(meta onethread base_opts)|$(meta onethread test_opts)" = "|"
if [ "$cpus" -ge 2 ]; then
  FAKE_ARGS="$tmp/args" FORK_SHARD_INTERVAL=1 bash "$here/run_shard.sh" --base "$tmp/base" --test "$tmp/test" \
    --fastchess "$tmp/fastchess" --book "$tmp/book.epd" --shard 1 --shards 4 --games 10 --tc 8+0.08 \
    --out "$tmp/twothreads" --test-opts "option.Threads=2" >"$tmp/twothreads.txt" 2>&1
  check "two threads: exit 0" test $? = 0
  check "two threads: the test engine's Threads=2, the base's 1" \
    bash -c "grep -qx 'option.Threads=2' '$tmp/args' && [ \$(grep -cx 'option.Threads=1' '$tmp/args') = 1 ]"
  check "two threads: concurrency nproc / 2" test "$(meta twothreads concurrency)" = $((cpus / 2))
  check "two threads: the meta's thread counts" test "$(meta twothreads base_threads)-$(meta twothreads test_threads)" = 1-2
  check "two threads: the meta's options as given" test "$(meta twothreads base_opts)|$(meta twothreads test_opts)" = "|option.Threads=2"
  shard toomany --test-opts "option.Threads=2" --concurrency "$cpus"
  check "two threads: a concurrency over the CPUs is refused" test "$status" = 2
fi
shard overcpus --test-opts "option.Threads=$((cpus + 1))"
check "more threads than CPUs: refused" test "$status" = 2

# The factorial round's per-shard rows (DESIGN.md §5.6 step 18; design §3.1, §3.3): --rows FILE gives shard I
# entry I's options for its test engine alone, recorded with the row and the design's digest; a table of the
# wrong length, a malformed option, a missing table, or --rows beside --test-opts is refused before fastchess
# starts.
d=$(printf '0%.0s' $(seq 64))
rows_table() {  # file, entries...
  local f=$1 sep="" e
  shift
  { printf '{"design": "%s", "shard_rows": [' "$d"
    for e in "$@"; do printf '%s%s' "$sep" "$e"; sep=", "; done
    printf ']}\n'; } >"$f"
}
refused_early() {  # out dir, run_shard.sh arguments...: exit 2 and fastchess never started
  rm -f "$tmp/args"
  shard "$@"
  [ "$status" = 2 ] && [ ! -f "$tmp/args" ]
}
rows_table "$tmp/rows4.json" '{"row": 3, "opts": "option.UseLmp=false"}' \
  '{"row": 0, "opts": "option.UseAspiration=false option.UseLmrInCheck=false"}' \
  '{"row": 2, "opts": "option.UseLmp=false option.UseMateDistance=false"}' '{"row": 1, "opts": "option.UseSeeQuiesce=false"}'
shard rows --rows "$tmp/rows4.json"
check "rows: exit 0" test "$status" = 0
check "rows: shard 1 plays entry 1's options on the test engine, before its Threads" \
  test "$(awk '$0 == "name=test" {on = 1; next} $0 == "-engine" {on = 0} on' "$tmp/args" | tr '\n' ' ')" = \
  "option.UseAspiration=false option.UseLmrInCheck=false option.Threads=1 "
check "rows: the base engine gets none of them" \
  bash -c "! tr '\n' ' ' <'$tmp/args' | sed 's/.*name=base //' | grep -q 'UseAspiration'"
check "rows: the meta's row, design and test options" \
  test "$(meta rows row)|$(meta rows design)|$(meta rows test_opts)" = "0|$d|option.UseAspiration=false option.UseLmrInCheck=false"
check "rows: the shard is done" test "$(status_of rows)" = done
check "without --rows: no row or design in the meta" test "$(meta notables row)|$(meta notables design)" = "|"
check "rows: with --test-opts refused before fastchess" refused_early rowsopts --rows "$tmp/rows4.json" --test-opts "option.UseLmp=false"
rows_table "$tmp/rows3.json" '{"row": 0, "opts": "option.UseLmp=false"}' '{"row": 1, "opts": "option.UseLmp=false"}' \
  '{"row": 2, "opts": "option.UseLmp=false"}'
check "rows: 3 entries for 4 shards refused before fastchess" refused_early rowsshort --rows "$tmp/rows3.json"
check "rows: the length is named" grep -q "3 entries for 4 shards" "$tmp/rowsshort.txt"
rows_table "$tmp/rowsbad.json" '{"row": 0, "opts": "option.UseLmp=false"}' '{"row": 1, "opts": "option.UseLmp=false;rm"}' \
  '{"row": 2, "opts": "option.UseLmp=false"}' '{"row": 3, "opts": "option.UseLmp=false"}'
check "rows: a malformed option refused before fastchess" refused_early rowsbad --rows "$tmp/rowsbad.json"
check "rows: a missing table refused before fastchess" refused_early rowsnone --rows "$tmp/no-such-rows.json"

# Per-engine time controls (idea 212's time odds; owner, 2026-11-22): a tc=T among an engine's options is its own
# clock, -each then has no tc, the other engine plays --tc, and the meta records both. Without one the command line
# is exactly the one before the change: the list below was taken from run_shard.sh at 8d186ea8 with the same
# arguments (per-side nodes, as idea 212's node-odds match passed them).
engine_of() {  # side -> that engine's arguments after its name, one line
  case $1 in
    test) awk '$0 == "name=test" {on = 1; next} $0 == "-engine" {on = 0} on' "$tmp/args" | tr '\n' ' ' ;;
    base) awk '$0 == "name=base" {on = 1; next} $0 == "-each" {on = 0} on' "$tmp/args" | tr '\n' ' ' ;;
  esac
}
each_of() { awk '$0 == "-each" {on = 1; next} $0 == "-openings" {on = 0} on' "$tmp/args" | tr '\n' ' '; }
shard sametc --base-opts "nodes=400000" --test-opts "option.Threads=1 nodes=800000"
printf '%s\n' -engine "cmd=$tmp/test" name=test option.Threads=1 nodes=800000 -engine "cmd=$tmp/base" name=base \
  nodes=400000 option.Threads=1 -each tc=8+0.08 option.Hash=16 option.CalibratedScore=false -openings \
  "file=$tmp/book.epd" format=epd order=sequential start=6 -repeat -rounds 5 -concurrency 2 -resign movecount=5 \
  score=1000 twosided=true -draw movenumber=40 movecount=10 score=10 -report penta=true -ratinginterval 50 -recover \
  -pgnout "file=$tmp/sametc/games.pgn" >"$tmp/args.before"
check "one tc: exit 0" test "$status" = 0
check "one tc: the fastchess command line is byte for byte the one before per-engine tc" cmp -s "$tmp/args" "$tmp/args.before"
check "one tc: no base_tc or test_tc in the meta" test "$(meta sametc base_tc)|$(meta sametc test_tc)" = "|"
shard halftc --base-opts "tc=4+0.04"
check "base tc=4+0.04: exit 0, done" test "$status-$(status_of halftc)" = 0-done
check "base tc=4+0.04: the base engine plays it" test "$(engine_of base)" = "tc=4+0.04 option.Threads=1 "
check "base tc=4+0.04: the test engine plays --tc" test "$(engine_of test)" = "option.Threads=1 tc=8+0.08 "
check "base tc=4+0.04: -each has no tc" test "$(each_of)" = "option.Hash=16 option.CalibratedScore=false "
check "base tc=4+0.04: the meta's clocks and options" \
  test "$(meta halftc base_tc)|$(meta halftc test_tc)|$(meta halftc tc)|$(meta halftc base_opts)" = "4+0.04|8+0.08|8+0.08|tc=4+0.04"
shard bothtc --base-opts "tc=20+0.2" --test-opts "nodes=5000 tc=40+0.4" --syzygy "$tmp/tb"
check "both sides' tc: each engine its own, none in -each" test "$(engine_of base)#$(engine_of test)#$(each_of)" = \
  "tc=20+0.2 option.Threads=1 #nodes=5000 tc=40+0.4 option.Threads=1 #option.Hash=16 option.CalibratedScore=false option.SyzygyPath=$(cd "$tmp/tb" && pwd) "
check "both sides' tc: the meta's clocks" test "$(meta bothtc base_tc)|$(meta bothtc test_tc)" = "20+0.2|40+0.4"
check "two tc= on one engine refused before fastchess" refused_early twotc --test-opts "tc=4+0.04 tc=8+0.08"
check "the refusal is named" grep -q "at most one tc=SECONDS+INCREMENT" "$tmp/twotc.txt"
for bad in "tc=4" "tc=40/60+0.6" "tc=4+0.04;x" "tc=" "tc=+0.04"; do
  check "a malformed '$bad' refused before fastchess" refused_early badtc --base-opts "$bad"
done

echo "${failures} failure(s)"
exit $((failures > 0))
