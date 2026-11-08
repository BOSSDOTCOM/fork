#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Dry runs of tools/github/spsa_run.sh against a fake gh: a shell script that keeps GitHub's state in files
# (runs not completed, each run's title and inputs, which runs fail or carry other results) and, on "run
# download", writes the run's shard results with tools/github/fake_spsa_shard.py (each draw's signs and
# values from its seed, games played on a synthetic quadratic landscape). Checks: no dispatch while any
# run is busy; a whole SPSA runs every iteration in order, each run in the ledger with its params sha, and
# moves theta toward the landscape's optimum; its own run is taken by title with another run dispatched
# just after; a failed run stops it, and after a rewind the iteration is played again under a new stage
# index; results naming another commit, or with a tampered draw, stop it with nothing applied; a commit
# not on GitHub stops it before any dispatch; outside the supervisor it refuses; SPSA_STOP_AFTER then a
# restart ends exactly as an uninterrupted run; a stage dispatched but not recorded (a stop between the
# dispatch and the ledger) is adopted by its title, not dispatched again. Uses python (or $PYTHON).
#
#   bash tools/github/test_spsa_run.sh
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
py=${PYTHON:-}
if [ -z "$py" ]; then
  for c in python3 python; do
    if command -v "$c" >/dev/null && "$c" -c 'pass' 2>/dev/null; then py=$(command -v "$c"); break; fi
  done
fi
[ -n "$py" ] || { echo "test_spsa_run.sh: no python found" >&2; exit 1; }
export PYTHON=$py
sha=$(git -C "$here" rev-parse HEAD)

cat >"$tmp/gh" <<'EOF'
#!/usr/bin/env bash
# The fake gh. State in $FAKE_GH: busy (runs still to report busy), latest (the newest run id), titles
# (each run's "ID TITLE", newest first), intruder (if present, another run is dispatched right after each
# of ours), commits (shas on GitHub), run.<id>.json (its inputs), fail.<id>, foreign.<id>, tamper.<id>,
# landscape.json (the synthetic optimum).
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
    shift 2
    args=()
    while [ $# -gt 0 ]; do [ "$1" = -f ] && args+=("$2"); shift; done
    "$PYTHON" -I -c 'import json, sys; print(json.dumps(dict(a.split("=", 1) for a in sys.argv[2:])))' x "${args[@]}" \
      >"$st/run.$id.json"
    title=$("$PYTHON" -I -c 'import json, sys; d = json.load(open(sys.argv[1])); print("spsa", d["label"], d["commit"], "stage", d["stage"])' "$st/run.$id.json" | tr -d '\r')
    { echo "$id $title"; cat "$st/titles" 2>/dev/null; } >"$st/titles.new"
    mv "$st/titles.new" "$st/titles"
    if [ -f "$st/intruder" ]; then  # someone else's run, newer than ours
      id=$((id + 1))
      { echo "$id spsa spsa-other $title"; cat "$st/titles"; } >"$st/titles.new"
      mv "$st/titles.new" "$st/titles"
    fi
    echo $id >"$st/latest" ;;
  "run view")
    if [[ "$*" == *conclusion* ]]; then
      if [ -f "$st/fail.$3" ]; then echo failure; else echo success; fi
    elif [[ "$*" == *createdAt* ]]; then
      echo "2026-11-08T01:00:00Z 2026-11-08T01:15:00Z"
    else
      echo completed
    fi ;;
  "run download")
    id=$3
    dir=${!#}  # the last argument, -D's
    "$PYTHON" -I "$FAKE_SHARD" "$st/run.$id.json" "$dir" "$st/landscape.json"
    if [ -f "$st/foreign.$id" ] || [ -f "$st/tamper.$id" ]; then
      "$PYTHON" -I - "$dir" "$st/foreign.$id" <<'PY'
import json, os, sys
from pathlib import Path
f = sorted(Path(sys.argv[1]).rglob('result.json'))[0]
r = json.load(open(f))
if os.path.exists(sys.argv[2]):
    r['meta']['commit'] = 'f' * 40
else:
    r['records'][0]['minus'][0] += 1
json.dump(r, open(f, 'w'))
PY
    fi ;;
  *) echo "fake gh: unexpected $*" >&2; exit 1 ;;
esac
EOF
chmod +x "$tmp/gh"

# The SPSA under test: two of R14's margins, the optimum 2 c below RfpMargin's start and 1.5 c above
# FutilityOffset's.
cat >"$tmp/spec.json" <<'EOF'
{"params": [{"name": "RfpMargin", "c": 6}, {"name": "FutilityOffset", "c": 8}], "fixed": {}, "iterations": 6,
 "games": 1600, "shards": 2, "draw_pairs": 1, "tc": "8+0.08", "hash": 16, "loss_budget": 0.5, "pair_sd": 0.21,
 "gain_exponent": 0.602, "stability_offset": 480, "clamp_c": 0.5, "c_decay": 0.0, "average_tail": 0.3,
 "opening_reserve": 2000001}
EOF
echo '{"RfpMargin": [68, 6, 1], "FutilityOffset": [112, 8, 1]}' >"$tmp/landscape.json"

setup() {  # label busy
  st=$tmp/$1
  mkdir -p "$st/data"
  echo "$2" >"$st/busy"
  echo 500 >"$st/latest"
  echo "$sha" >"$st/commits"
  cp "$tmp/landscape.json" "$st/"
  : >"$st/dispatches"
  SPSA_DATA=$st/data "$py" -I "$here/spsa.py" init spsa-t --spec "$tmp/spec.json" --commit "$sha" >"$st/init" 2>&1
}
drive() {  # label [env assignments...]
  local label=$1
  shift
  env FAKE_GH="$tmp/$label" FAKE_SHARD="$here/fake_spsa_shard.py" GH="$tmp/gh" POLL=0 REPO=owner/fork REF=test \
    SPSA_DATA="$tmp/$label/data" FORK_JOBS="$tmp/$label/jobs" SPSA_UNSUPERVISED="${UNSUPERVISED-1}" "$@" \
    bash "$here/spsa_run.sh" spsa-t >"$tmp/$label/out" 2>&1
  echo $? >"$tmp/$label/rc"
}
rc() { cat "$tmp/$1/rc"; }
dispatches() { wc -l <"$tmp/$1/dispatches" | tr -d ' '; }
state() {  # label, python expression on the state s
  "$py" -I -c "import json, sys; s = json.load(open(sys.argv[1])); print($2)" "$tmp/$1/data/spsa-t/state.json" | tr -d '\r'
}
ledger() {  # label args...
  local label=$1
  shift
  FORK_JOBS=$tmp/$label/jobs "$py" -I "$here/../jobs/ledger.py" "$@" | tr -d '\r'
}

# 1-7: a whole SPSA, after waiting for the busy runs.
setup full 3
drive full
check "a whole SPSA exits 0" [ "$(rc full)" = 0 ]
check "six dispatches, stages 0-5 in order" [ "$(grep -o 'stage=[0-9]*' "$tmp/full/dispatches" | tr '\n' ' ')" = "stage=0 stage=1 stage=2 stage=3 stage=4 stage=5 " ]
check "the first dispatch only after the busy runs finished" grep -q "^501 busy=0 " "$tmp/full/dispatches"
check "every run in the ledger, each stage once" [ "$(ledger full runs spsa-t | awk '{print $1, $2}' | tr '\n' ' ')" = "0 501 1 502 2 503 3 504 4 505 5 506 " ]
check "the ledger notes each run's params sha" bash -c "grep -c 'spsa iteration [0-9] params sha256 [0-9a-f]\{64\}' '$tmp/full/jobs/ledger.jsonl' | grep -qx 6"
check "theta moved toward the optimum (RfpMargin down, FutilityOffset up)" [ "$(state full "s['theta']['RfpMargin'] < 80 < 100 < s['theta']['FutilityOffset'], s['done']")" = "True True" ]
check "the report and final.json" bash -c "grep -q '| RfpMargin | 80 |' '$tmp/full/out' && [ -f '$tmp/full/data/spsa-t/final.json' ]"

# 8-9: another run dispatched right after ours is newer; the driver still takes its own by title.
setup intruder 0
touch "$tmp/intruder/intruder"
drive intruder SPSA_STOP_AFTER=0
check "with an intruding run, the iteration completes" [ "$(rc intruder)-$(state intruder "s['iteration']")" = "0-1" ]
check "it took its own run, 501, not the newer 502" [ "$(ledger intruder runs spsa-t | awk '{print $1, $2}')" = "0 501" ]

# 10-14: a failed run stops it; after a rewind the iteration is played again under a new stage index.
setup failed 0
touch "$tmp/failed/fail.502"
drive failed
check "a failed run exits 1, after one applied iteration" [ "$(rc failed)-$(state failed "s['iteration']")" = "1-1" ]
check "the failure is named, with the rewind" grep -q "run 502 ended 'failure' (spsa.py rewind spsa-t --to 0" "$tmp/failed/out"
drive failed
check "restarted without a rewind it stops again, dispatching nothing" [ "$(rc failed)-$(dispatches failed)" = "1-2" ]
SPSA_DATA=$tmp/failed/data "$py" -I "$here/spsa.py" rewind spsa-t --to 0 >/dev/null
drive failed SPSA_STOP_AFTER=1
check "after the rewind, iteration 1 is played as stage 2" [ "$(rc failed)-$(state failed "s['iteration'], s['burned']")" = "0-2 [1]" ]
check "stage 2 dispatched with iteration 1's theta" bash -c "grep -q 'stage=2' '$tmp/failed/dispatches'"

# 15-17: results naming another commit, or a tampered draw, stop it with nothing applied.
setup foreign 0
touch "$tmp/foreign/foreign.501"
drive foreign
check "another commit's results exit 1, nothing applied" [ "$(rc foreign)-$(state foreign "s['iteration']")" = "1-0" ]
check "the refusal is named" grep -q "results refused, nothing applied" "$tmp/foreign/out"
setup tamper 0
touch "$tmp/tamper/tamper.501"
drive tamper
check "a tampered draw exits 1, nothing applied" bash -c "[ '$(rc tamper)-$(state tamper "s['iteration']")' = 1-0 ] && grep -q 'differ from its seed' '$tmp/tamper/out'"

# 18-19: a commit not on GitHub; outside the supervisor.
setup missing 0
echo ffffffffffffffffffffffffffffffffffffffff >"$tmp/missing/commits"
drive missing
check "a commit not on GitHub exits 1 before any dispatch" [ "$(rc missing)-$(dispatches missing)" = "1-0" ]
setup unsupervised 0
UNSUPERVISED= drive unsupervised
check "started outside the supervisor exits 1, dispatching nothing" [ "$(rc unsupervised)-$(dispatches unsupervised)" = "1-0" ]

# 20-21: SPSA_STOP_AFTER then a restart ends exactly as the uninterrupted run (test 1).
setup resume 0
drive resume SPSA_STOP_AFTER=1
check "SPSA_STOP_AFTER=1 stops after iteration 1" [ "$(rc resume)-$(state resume "s['iteration']")" = "0-2" ]
drive resume
check "the restart finishes with the uninterrupted run's state" cmp -s "$tmp/resume/data/spsa-t/state.json" "$tmp/full/data/spsa-t/state.json"

# 22-23: stopped between the dispatch and the ledger: the run is adopted by its title, not dispatched again.
setup adopt 0
SPSA_DATA=$tmp/adopt/data "$py" -I "$here/spsa.py" dispatch spsa-t >"$tmp/adopt/plan"
FAKE_GH=$tmp/adopt PYTHON=$py "$tmp/gh" workflow run spsa.yml -R owner/fork --ref test \
  $(sed -n 's/^\(commit\|label\|stage\|params\|games\|shards\|tc\|hash\|openings\|draw_pairs\)=\(.*\)$/-f \1=\2/p' "$tmp/adopt/plan" | tr -d '\r')
drive adopt SPSA_STOP_AFTER=0
check "the planned stage's run is adopted (one dispatch in all)" [ "$(rc adopt)-$(dispatches adopt)-$(state adopt "s['iteration']")" = "0-1-1" ]
check "the ledger records it as an import" grep -q '"source": "import"' "$tmp/adopt/jobs/ledger.jsonl"

if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed"
  for d in "$tmp"/*/; do [ -f "$d/out" ] && { echo "--- $d"; tail -5 "$d/out"; }; done
  exit 1
fi
echo "all checks passed"
