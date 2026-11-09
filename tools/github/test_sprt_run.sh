#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Dry runs of tools/github/sprt_run.sh against a fake gh: a shell script that
# keeps GitHub's state in files (runs not completed, the newest sprt run,
# each dispatched run's inputs, which runs fail or carry another test's
# results) and writes shard result.json files on "run download". Checks:
# no dispatch while any run is busy; an H1 verdict ends the SPRT after one
# stage; an undecided SPRT runs every stage, in order, then exits 2; a
# failed run stops it; results naming another commit stop it, unmerged; a
# commit not on GitHub stops it before any dispatch, and a missing gh is
# named as such; RUN_ID waits for that run without dispatching. Since
# 2026-11-05 (the job supervisor and the run-ID ledger): started outside the
# supervisor it refuses; it takes its own run by title even when another
# run was dispatched just after it; every dispatched run is in the ledger;
# RUN_ID needs a ledger record; a stage folder the ledger does not record
# stops it, unmerged. Uses python3 (or $PYTHON) for the merge and the
# ledger.
#
#   bash tools/github/test_sprt_run.sh
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
export PYTHON=${PYTHON:-python3}
sha=$(git -C "$here" rev-parse HEAD)
other=ffffffffffffffffffffffffffffffffffffffff

cat >"$tmp/gh" <<'EOF'
#!/usr/bin/env bash
# The fake gh. State in $FAKE_GH: busy (runs still to report busy), latest
# (the newest sprt run id), titles (each run's "ID TITLE", newest first),
# intruder (if present, another run is dispatched right after each of
# ours), commits (shas on GitHub), run.<id> (its inputs), fail.<id>,
# foreign.<id>, ptnml (each shard's pentanomial counts).
st=$FAKE_GH
echo "$*" >>"$st/calls"
case "$1 $2" in
  "api "*)
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
      if [ -f "$st/fail.$3" ]; then echo failure; else echo success; fi
    else
      echo completed
    fi ;;
  "run download")
    id=$3
    dir=${!#}  # the last argument, -D's
    . "$st/run.$id"
    [ -f "$st/foreign.$id" ] && test=ffffffffffffffffffffffffffffffffffffffff
    for k in $(seq 0 $((SHARDS - 1))); do
      mkdir -p "$dir/shard-$stage-$k"
      start=$(((stage * SHARDS + k) * 50 + 1))
      cat >"$dir/shard-$stage-$k/result.json" <<JSON
{"ptnml": $(cat "$st/ptnml"), "pairs": 50, "finished_games": 100, "time_losses": 0, "abnormal": 0, "status": "done",
 "meta": {"base": "$base", "test": "$test", "stage": "$stage", "shard": "$k", "shards": "$SHARDS", "tc": "8+0.08",
          "hash": "16", "base_opts": "", "test_opts": "", "tables": "3-4-5", "book_sha": "x",
          "opening_start": "$start", "rounds": "50"}}
JSON
    done ;;
  *) echo "fake gh: unexpected $*" >&2; exit 1 ;;
esac
EOF
chmod +x "$tmp/gh"

# One scenario: a fresh state, then the driver (args...); its exit status
# goes to $tmp/<label>/rc and its output to $tmp/<label>/out.
setup() {  # label busy ptnml
  st=$tmp/$1
  mkdir -p "$st"
  echo "$2" >"$st/busy"
  echo 500 >"$st/latest"
  echo "$sha" >"$st/commits"
  echo "$3" >"$st/ptnml"
  : >"$st/dispatches"
}
drive() {  # label args...
  local label=$1
  shift
  FAKE_GH=$tmp/$label GH=$tmp/gh POLL=0 SHARDS=2 REPO=owner/fork REF=test SPRT_DATA=$tmp/$label/data \
    FORK_JOBS=$tmp/$label/jobs SPRT_UNSUPERVISED=${UNSUPERVISED-1} \
    bash "$here/sprt_run.sh" "$label" "$@" >"$tmp/$label/out" 2>&1
  echo $? >"$tmp/$label/rc"
}
ledger() {  # label args...
  local label=$1
  shift
  FORK_JOBS=$tmp/$label/jobs "$PYTHON" -I "$here/../jobs/ledger.py" "$@"
}
rc() { cat "$tmp/$1/rc"; }
dispatches() { wc -l <"$tmp/$1/dispatches" | tr -d ' '; }

strong='[0, 0, 5, 20, 25]'  # H1 after one stage of two shards
even='[5, 10, 20, 10, 5]'   # Elo 0: undecided

# 1-3: waits while runs are busy; H1 ends it after one stage.
setup h1 3 "$strong"
drive h1 "$sha" "$sha" 0 5
check "H1 after one stage exits 0" [ "$(rc h1)" = 0 ]
check "one dispatch" [ "$(dispatches h1)" = 1 ]
check "dispatched only after the busy runs finished" grep -q "^501 busy=0 " "$tmp/h1/dispatches"
check "the merged verdict is logged" grep -q "H1 accepted" "$tmp/h1/data/h1/driver.log"
check "the games and time losses are logged" grep -q "Shards: 2 (done); pairs 100, games 200 (200 finished, time losses 0" "$tmp/h1/data/h1/driver.log"

# 4-6: undecided runs every stage in order, then exits 2.
setup undecided 0 "$even"
drive undecided "$sha" "$sha" 0 5 0 2
check "undecided exits 2" [ "$(rc undecided)" = 2 ]
check "three stages dispatched" [ "$(dispatches undecided)" = 3 ]
check "stages 0, 1, 2 in order" [ "$(grep -o 'stage=[0-9]*' "$tmp/undecided/dispatches" | tr '\n' ' ')" = "stage=0 stage=1 stage=2 " ]
check "bounds passed as given" grep -q "bounds=0 5" "$tmp/undecided/dispatches"

# 7-8: a failed run stops it.
setup failed 0 "$even"
touch "$tmp/failed/fail.502"
drive failed "$sha" "$sha" 0 5 0 4
check "a failed run exits 1" [ "$(rc failed)" = 1 ]
check "no stage after the failed one" [ "$(dispatches failed)" = 2 ]
check "the failure is named" grep -q "run 502 ended 'failure'" "$tmp/failed/out"

# 9-11: results naming another test commit stop it, unmerged.
setup foreign 0 "$strong"
touch "$tmp/foreign/foreign.501"
drive foreign "$sha" "$sha" 0 5
check "another SPRT's results exit 1" [ "$(rc foreign)" = 1 ]
check "the mismatch is named" grep -q "not this SPRT's" "$tmp/foreign/out"
check "nothing merged" bash -c "! grep -q 'LLR' '$tmp/foreign/out'"

# 12-13: a commit not on GitHub stops it before any dispatch.
setup missing 0 "$strong"
drive missing "$sha" "$sha" 0 5
echo "$other" >"$tmp/missing/commits"
drive missing "$sha" "$sha" 0 5
check "a commit not on GitHub exits 1" [ "$(rc missing)" = 1 ]
check "no dispatch for it" [ "$(dispatches missing)" = 1 ]

# 14: no gh at all is reported as such, not as a missing commit.
setup nogh 0 "$strong"
SPRT_UNSUPERVISED=1 FAKE_GH=$tmp/nogh GH=$tmp/no-such-gh POLL=0 SHARDS=2 REPO=owner/fork REF=test SPRT_DATA=$tmp/nogh/data \
  bash "$here/sprt_run.sh" nogh "$sha" "$sha" 0 5 >"$tmp/nogh/out" 2>&1
check "a missing gh is named" grep -q "no gh command" "$tmp/nogh/out"

# 15-16: RUN_ID waits for a dispatched run without dispatching it again.
setup adopt 0 "$strong"
printf 'base=%s\ntest=%s\nstage=0\n' "$sha" "$sha" >"$tmp/adopt/run.77"
ledger adopt add adopt 0 77 --base "$sha" --test "$sha" --source import --note test
RUN_ID=77 drive adopt "$sha" "$sha" 0 5
check "RUN_ID's run decides it" [ "$(rc adopt)" = 0 ]
check "RUN_ID dispatches nothing" [ "$(dispatches adopt)" = 0 ]

# 17-18: RUN_ID without a ledger record stops it before anything is merged.
setup unrecorded 0 "$strong"
printf 'base=%s\ntest=%s\nstage=0\n' "$sha" "$sha" >"$tmp/unrecorded/run.78"
RUN_ID=78 drive unrecorded "$sha" "$sha" 0 5
check "an unrecorded RUN_ID exits 1" [ "$(rc unrecorded)" = 1 ]
check "the missing record is named" grep -q "RUN_ID 78 is not in the ledger" "$tmp/unrecorded/out"

# 19-20: outside the supervisor it refuses, before any dispatch.
setup unsupervised 0 "$strong"
UNSUPERVISED= drive unsupervised "$sha" "$sha" 0 5
check "started outside the supervisor exits 1" [ "$(rc unsupervised)" = 1 ]
check "and dispatches nothing" [ "$(dispatches unsupervised)" = 0 ]

# 21-23: another run dispatched right after ours is newer; the driver still takes its own by title.
setup intruder 0 "$strong"
touch "$tmp/intruder/intruder"
drive intruder "$sha" "$sha" 0 5
check "with an intruding run, H1 exits 0" [ "$(rc intruder)" = 0 ]
check "it took its own run, 501, not the newer 502" grep -q "stage 0: run 501 dispatched" "$tmp/intruder/out"
check "the ledger records stage 0 as run 501" [ "$(ledger intruder runs intruder)" = "0 501 $sha $sha" ]

# 24-25: a stage folder the ledger does not record (results from elsewhere) stops it, unmerged.
setup stray 0 "$even"
mkdir -p "$tmp/stray/data/stray/s0/shard-0-0"
echo 400 >"$tmp/stray/data/stray/s0/run_id"
cp "$tmp/undecided/data/undecided/s0/shard-0-0/result.json" "$tmp/stray/data/stray/s0/shard-0-0/"
drive stray "$sha" "$sha" 0 5 1 1
check "an unrecorded stage folder exits 1" [ "$(rc stray)" = 1 ]
check "the stray stage is named, nothing merged" bash -c "grep -q \"stage 0's results (run 400) are not in the ledger\" '$tmp/stray/out' && ! grep -q LLR '$tmp/stray/out'"

if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed"
  for d in "$tmp"/*/; do [ -f "$d/out" ] && { echo "--- $d"; tail -5 "$d/out"; }; done
  exit 1
fi
echo "all checks passed"
