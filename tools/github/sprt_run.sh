#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# One SPRT on the GitHub shards (.github/workflows/sprt.yml), dispatched a
# stage at a time until the merged result (tools/cloud/sprt_merge.py) is no
# longer "continue". Run it from a clone where gh is logged in.
#
#   tools/github/sprt_run.sh NAME BASE TEST ELO0 ELO1 [FIRST [LAST]]
#
#   NAME         label: stage results go to $SPRT_DATA/NAME/s<stage>/, the
#                driver's log to $SPRT_DATA/NAME/driver.log
#   BASE, TEST   commits (anything git rev-parse resolves here); both must
#                also be on GitHub
#   ELO0, ELO1   nElo bounds (0 5 for nets, 0 3 for tier 2, -3 0 for
#                non-regression)
#   FIRST, LAST  the stages to run, default 0 and 12 (13 stages of 1,600
#                games cover the 20,000-game STC cap, DESIGN.md §5.2)
#
# Rules (2026-11-02; an earlier driver, left running after its SPRT was
# cancelled, kept dispatching stages against a test commit that was no
# longer on GitHub, beside other runs):
# - both commits must be on GitHub before the first dispatch;
# - one run at a time: a stage is dispatched only when no run of any
#   workflow in the repository is queued or in progress;
# - it stops at the first stage whose run does not succeed;
# - every shard result merged must name this SPRT's base and test commits
#   and its own stage (result.json's meta), and the stage must have SHARDS
#   of them, so a run picked up by mistake is never merged.
#
# Environment: TC (default 8+0.08), HASH (16), GAMES (1600 per stage),
# SHARDS (16), TABLES (on), BASE_OPTS and TEST_OPTS (fastchess engine
# options, default none), REF (the branch whose sprt.yml runs; default the
# current branch), REPO (owner/name; default origin's), GH (the gh command;
# default gh), PYTHON (default the repository's .venv, else python3),
# SPRT_DATA (default ~/fork-sprt/github), POLL (seconds between status
# checks, default 120), RUN_ID (FIRST's run was already dispatched, e.g. by
# a driver that was stopped: wait for that run instead of dispatching).
#
# Exit status: 0 decided (H0 or H1 accepted), 2 undecided after LAST, 1
# stopped by a rule above or an error.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.."
if [ $# -lt 5 ]; then
  sed -n '7,16p' "$here/sprt_run.sh" >&2
  exit 1
fi
name=$1 elo0=$4 elo1=$5 first=${6:-0} last=${7:-12}
GH=${GH:-gh}
POLL=${POLL:-120}
SHARDS=${SHARDS:-16}
data=${SPRT_DATA:-$HOME/fork-sprt/github}/$name
mkdir -p "$data"
say() { echo "$(date -u '+%Y-%m-%d %H:%M UTC') $name: $*" | tee -a "$data/driver.log"; }
stop() { say "$*; stopping"; exit 1; }

py=${PYTHON:-}
if [ -z "$py" ]; then
  for c in .venv/Scripts/python.exe .venv/bin/python python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c pass >/dev/null 2>&1; then py=$c; break; fi
  done
fi
[ -n "$py" ] || stop "no Python for the merge"
command -v "$GH" >/dev/null 2>&1 || stop "no gh command '$GH' (set GH to its path)"
base=$(git rev-parse --verify --quiet "$2^{commit}") || stop "base $2 is not a commit in this clone"
test=$(git rev-parse --verify --quiet "$3^{commit}") || stop "test $3 is not a commit in this clone"
REF=${REF:-$(git rev-parse --abbrev-ref HEAD)}
REPO=${REPO:-$(git remote get-url origin | sed -E 's#^(https://github\.com/|git@github\.com:)##; s#\.git$##')}
for c in "$base" "$test"; do
  "$GH" api "repos/$REPO/commits/$c" --jq .sha >/dev/null 2>&1 || stop "commit $c is not on GitHub ($REPO)"
done

# Prints the number of runs not completed; anything but "0" (gh failing
# included) counts as busy.
busy() { "$GH" run list -R "$REPO" -L 50 --json status --jq '[.[] | select(.status != "completed")] | length' 2>/dev/null; }
latest() { "$GH" run list -R "$REPO" -w sprt.yml -L 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null; }

say "base $base, test $test, bounds [$elo0, $elo1], stages $first to $last, ref $REF"
for stage in $(seq "$first" "$last"); do
  if [ "$stage" = "$first" ] && [ -n "${RUN_ID:-}" ]; then
    id=$RUN_ID
    say "stage $stage: waiting for run $id (RUN_ID)"
  else
    while [ "$(busy)" != 0 ]; do sleep "$POLL"; done
    before=$(latest)
    "$GH" workflow run sprt.yml -R "$REPO" --ref "$REF" -f base="$base" -f test="$test" -f bounds="$elo0 $elo1" \
      -f tc="${TC:-8+0.08}" -f hash="${HASH:-16}" -f games="${GAMES:-1600}" -f shards="$SHARDS" -f stage="$stage" \
      -f tables="${TABLES:-on}" -f test_opts="${TEST_OPTS:-}" -f base_opts="${BASE_OPTS:-}" >/dev/null 2>&1 ||
      stop "stage $stage: dispatch failed"
    id=$before
    for _ in $(seq 30); do
      sleep $((POLL < 10 ? POLL : 10))
      id=$(latest)
      [ -n "$id" ] && [ "$id" != "$before" ] && break
    done
    [ -n "$id" ] && [ "$id" != "$before" ] || stop "stage $stage: no new sprt run after the dispatch"
    say "stage $stage: run $id dispatched"
  fi
  while [ "$("$GH" run view "$id" -R "$REPO" --json status --jq .status 2>/dev/null)" != completed ]; do sleep "$POLL"; done
  concl=$("$GH" run view "$id" -R "$REPO" --json conclusion --jq .conclusion 2>/dev/null)
  [ "$concl" = success ] || stop "stage $stage: run $id ended '$concl'"
  rm -rf "$data/s$stage"
  mkdir -p "$data/s$stage"
  "$GH" run download "$id" -R "$REPO" -D "$data/s$stage" >/dev/null 2>&1 || stop "stage $stage: run $id's download failed"
  # The shard results of stages FIRST..this one (earlier stages too when
  # resuming), each checked against this SPRT's commits and its stage.
  files=()
  for s in $(seq 0 "$stage"); do
    [ -d "$data/s$s" ] || continue
    while IFS= read -r f; do files+=("$f"); done < <(find "$data/s$s" -name result.json | sort)
  done
  wrong=$("$py" -I - "$base" "$test" "$data" "${files[@]}" <<'EOF'
import json, os, sys
base, test, data = sys.argv[1:4]
for f in sys.argv[4:]:
    meta = json.load(open(f)).get('meta', {})
    stage = os.path.relpath(f, data).replace(os.sep, '/').split('/')[0][1:]
    if (meta.get('base'), meta.get('test'), str(meta.get('stage'))) != (base, test, stage):
        print(os.path.relpath(f, data))
EOF
  ) || stop "stage $stage: the shard results could not be read"
  [ -z "$wrong" ] || stop "stage $stage: run $id's results are not this SPRT's (first: $(echo "$wrong" | head -1))"
  got=$(find "$data/s$stage" -name result.json | wc -l)
  [ "$got" -eq "$SHARDS" ] || stop "stage $stage: run $id gave $got shard results, not $SHARDS"
  merged=$("$py" -I tools/cloud/sprt_merge.py merge --elo0 "$elo0" --elo1 "$elo1" "${files[@]}" 2>&1 | tail -5)
  say "stage $stage: run $id merged"
  echo "$merged" | sed 's/^/    /' | tee -a "$data/driver.log"
  case $(echo "$merged" | grep -E '^LLR:' | tail -1) in
    *continue*) ;;
    *accepted*) say "decided after stage $stage"; exit 0 ;;
    *) stop "stage $stage: no LLR line in the merge" ;;
  esac
done
say "undecided after stage $last"
exit 2
