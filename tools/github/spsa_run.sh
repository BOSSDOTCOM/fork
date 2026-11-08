#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# One SPSA on the GitHub shards (.github/workflows/spsa.yml; DESIGN.md §5.2, "SPSA on GitHub"), one run per
# iteration until the spec's last, from a clone where gh is logged in. The arithmetic, the spec and the
# state are tools/github/spsa.py's; initialise first:
#
#   python -I tools/github/spsa.py init NAME --spec tools/github/spsa-r14.json --commit SHA
#   python -I tools/jobs/jobctl.py start github NAME -- bash tools/github/spsa_run.sh NAME
#
# Each iteration: spsa.py dispatch plans the run (and records it in $SPSA_DATA/NAME/i<stage>/dispatch.json
# before anything is dispatched); the run is dispatched, found by its title, recorded in the ledger, waited
# for and downloaded; spsa.py step verifies every shard result against the dispatch (meta, openings, each
# draw's signs and values against its seed) and applies the update. A restart resumes: a stage with a
# recorded run waits for that run; a stage planned but without a recorded run (a stop between the dispatch
# and the ledger) adopts the one run titled for it that the ledger does not know, or dispatches it if
# there is none.
#
# Rules, as tools/github/sprt_run.sh's (2026-11-02 and 2026-11-05):
# - it runs only under the job supervisor (tools/jobs/jobctl.py start github NAME -- ...), type github, so
#   never beside an SPRT driver; started any other way it refuses;
# - the commit must be on GitHub before the first dispatch;
# - one run at a time: a run is dispatched only when no run of any workflow is queued or in progress;
# - it finds its run by the title spsa.yml builds from the inputs ("spsa NAME COMMIT stage D"), among runs
#   newer than the dispatch and not in the ledger, never as "the newest run"; D (the dispatch index) is
#   never reused, so the title is unique;
# - every run goes into the run-ID ledger (tools/jobs/ledger.py add NAME D RUN --base COMMIT --test
#   COMMIT --note "spsa iteration K params sha256 H");
# - it stops at the first run that does not succeed, and at any result spsa.py refuses, with nothing
#   applied; `spsa.py rewind NAME --to K` (K the last applied iteration) abandons that stage, and the restart
#   plays the iteration again with a new stage index, new seeds and new openings.
#
# Environment: SPSA_DATA (default ~/fork-spsa/github), SPSA_STOP_AFTER (stop cleanly once that iteration
# is applied: the dry run is SPSA_STOP_AFTER=0), REF (the branch whose spsa.yml runs; default the current
# branch), REPO (owner/name; default origin's), GH (the gh command; default gh), PYTHON (default the
# repository's .venv, else python3), POLL (seconds between status checks, default 120), FORK_JOBS (the
# supervisor's and the ledger's folder, default ~/fork-jobs), SPSA_UNSUPERVISED=1 (tests only).
#
# Exit status: 0 finished (or stopped after SPSA_STOP_AFTER), 1 stopped by a rule above or an error.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.."
if [ $# -ne 1 ]; then
  sed -n '7,8p' "$here/spsa_run.sh" >&2
  exit 1
fi
name=$1
GH=${GH:-gh}
POLL=${POLL:-120}
data=${SPSA_DATA:-$HOME/fork-spsa/github}/$name
mkdir -p "$data"
say() { echo "$(date -u '+%Y-%m-%d %H:%M UTC') $name: $*" | tee -a "$data/driver.log"; }
stop() { say "$*; stopping"; exit 1; }

py=${PYTHON:-}
if [ -z "$py" ]; then
  for c in .venv/Scripts/python.exe .venv/bin/python python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c pass >/dev/null 2>&1; then py=$c; break; fi
  done
fi
[ -n "$py" ] || stop "no Python"
[ -n "${FORK_JOB:-}" ] || [ "${SPSA_UNSUPERVISED:-}" = 1 ] ||
  stop "not started by the job supervisor (tools/jobs/jobctl.py start github $name -- $0 $name)"
[ -f "$data/spec.json" ] || stop "no spec: run tools/github/spsa.py init $name first"
ledger() { "$py" -I tools/jobs/ledger.py "$@"; }
spsa() { SPSA_DATA=$(dirname "$data") "$py" -I tools/github/spsa.py "$@"; }
field() { "$py" -I -c 'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$1" "$2" | tr -d '\r'; }
command -v "$GH" >/dev/null 2>&1 || stop "no gh command '$GH' (set GH to its path)"
commit=$(field "$data/spec.json" commit)
REF=${REF:-$(git rev-parse --abbrev-ref HEAD)}
REPO=${REPO:-$(git remote get-url origin | sed -E 's#^(https://github\.com/|git@github\.com:)##; s#\.git$##')}
"$GH" api "repos/$REPO/commits/$commit" --jq .sha >/dev/null 2>&1 || stop "commit $commit is not on GitHub ($REPO)"

# Prints the number of runs not completed; anything but "0" (gh failing included) counts as busy.
busy() { "$GH" run list -R "$REPO" -L 50 --json status --jq '[.[] | select(.status != "completed")] | length' 2>/dev/null; }
# The newest spsa runs, "ID TITLE" per line.
runs() { "$GH" run list -R "$REPO" -w spsa.yml -L 30 --json databaseId,displayTitle \
  --jq '.[] | "\(.databaseId) \(.displayTitle)"' 2>/dev/null | tr -d '\r'; }
# The runs titled $1, newer than $2, that the ledger does not know.
titled() { runs | while read -r rid rtitle; do
  [ "$rid" -gt "$2" ] && [ "$rtitle" = "$1" ] && ! ledger known "$rid" && echo "$rid"
done; }

say "commit $commit, ref $REF"
while :; do
  if [ "$(field "$data/state.json" done)" = True ]; then
    say "finished"
    spsa report "$name" | tee -a "$data/driver.log"
    exit 0
  fi
  plan=$(spsa dispatch "$name" 2>&1) || stop "the next run could not be planned: $plan"
  get() { sed -n "s/^$1=//p" <<<"$plan" | tr -d '\r'; }
  stage=$(get stage) iteration=$(get iteration) sum=$(get params_sha256)
  folder=$data/i$stage
  title="spsa $name $commit stage $stage"
  if [ -f "$folder/run_id" ]; then
    id=$(cat "$folder/run_id")
    ledger check "$name" "$stage" "$id" "$commit" "$commit" ||
      stop "stage $stage: run $id is not in the ledger as this SPSA's stage $stage"
    say "iteration $iteration, stage $stage: waiting for run $id (in the ledger)"
  else
    mine=$(titled "$title" 0)
    if [ -n "$mine" ]; then
      [ "$(echo "$mine" | wc -l)" -eq 1 ] || stop "stage $stage: more than one unrecorded run titled '$title': $(echo $mine)"
      id=$mine
      ledger add "$name" "$stage" "$id" --base "$commit" --test "$commit" --source import \
        --note "spsa iteration $iteration params sha256 $sum; adopted by its title after a restart" ||
        stop "stage $stage: run $id: ledger refused it"
      say "iteration $iteration, stage $stage: run $id adopted by its title (ledger, import)"
    else
      while [ "$(busy)" != 0 ]; do sleep "$POLL"; done
      before=$(runs | awk 'NR == 1 {print $1}')
      before=${before:-0}
      "$GH" workflow run spsa.yml -R "$REPO" --ref "$REF" -f commit="$commit" -f label="$name" -f stage="$stage" \
        -f params="$(get params)" -f games="$(get games)" -f shards="$(get shards)" -f tc="$(get tc)" \
        -f hash="$(get hash)" -f openings="$(get openings)" -f draw_pairs="$(get draw_pairs)" >/dev/null 2>&1 ||
        stop "stage $stage: dispatch failed"
      mine=
      for _ in $(seq 30); do
        sleep $((POLL < 10 ? POLL : 10))
        mine=$(titled "$title" "$before")
        [ -n "$mine" ] && break
      done
      [ -n "$mine" ] || stop "stage $stage: no new run titled '$title' after the dispatch"
      [ "$(echo "$mine" | wc -l)" -eq 1 ] || stop "stage $stage: more than one new run titled '$title': $(echo $mine)"
      id=$mine
      ledger add "$name" "$stage" "$id" --base "$commit" --test "$commit" \
        --note "spsa iteration $iteration params sha256 $sum" || stop "stage $stage: run $id: ledger refused it"
      say "iteration $iteration, stage $stage: run $id dispatched (ledger)"
    fi
    echo "$id" >"$folder/run_id"
  fi
  while [ "$("$GH" run view "$id" -R "$REPO" --json status --jq .status 2>/dev/null | tr -d '\r')" != completed ]; do
    sleep "$POLL"
  done
  concl=$("$GH" run view "$id" -R "$REPO" --json conclusion --jq .conclusion 2>/dev/null | tr -d '\r')
  [ "$concl" = success ] ||
    stop "stage $stage: run $id ended '$concl' (spsa.py rewind $name --to $((iteration - 1)) abandons the stage)"
  find "$folder" -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} +
  "$GH" run download "$id" -R "$REPO" -p "spsa-$stage-*" -D "$folder" >/dev/null 2>&1 ||
    stop "stage $stage: run $id's download failed"
  wall=$("$GH" run view "$id" -R "$REPO" --json createdAt,updatedAt --jq '"\(.createdAt) \(.updatedAt)"' 2>/dev/null |
    "$py" -I -c 'import sys, datetime as d
t = [d.datetime.fromisoformat(x.replace("Z", "+00:00")) for x in sys.stdin.read().split()]
print(round((t[1] - t[0]).total_seconds() / 60, 2) if len(t) == 2 else 0)' | tr -d '\r')
  out=$(spsa step "$name" --stage "$stage" --meta "wall_minutes=${wall:-0}" 2>&1) ||
    stop "stage $stage: run $id's results refused, nothing applied: $out (spsa.py rewind $name --to $((iteration - 1)) abandons the stage)"
  say "iteration $iteration, stage $stage: run $id applied (${wall:-?} min)"
  echo "$out" | sed 's/^/    /' | tee -a "$data/driver.log"
  if [ -n "${SPSA_STOP_AFTER:-}" ] && [ "$iteration" -ge "$SPSA_STOP_AFTER" ] &&
    [ "$(field "$data/state.json" done)" != True ]; then
    say "stopped after iteration $iteration (SPSA_STOP_AFTER)"
    exit 0
  fi
done
