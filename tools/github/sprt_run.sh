#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# One SPRT on the GitHub shards (.github/workflows/sprt.yml), dispatched a
# stage at a time until the merged result (tools/cloud/sprt_merge.py) decides.
# Run it from a clone where gh is logged in.
#
#   tools/github/sprt_run.sh --kind search|network|fixed --idea ID [OPTIONS] NAME BASE TEST
#   tools/github/sprt_run.sh NAME BASE TEST ELO0 ELO1 [FIRST [LAST]]   (custom: as before 2026-11-07)
#
#   NAME         label: stage results go to $SPRT_DATA/NAME/s<stage>/, the
#                driver's log to $SPRT_DATA/NAME/driver.log
#   BASE, TEST   commits (anything git rev-parse resolves here); both must also be on GitHub
#   --kind       search: design R; network: [0, 5]; fixed: exactly --cap stages, never decided (below)
#   --idea ID    the idea under test ([a-z0-9][a-z0-9.-]*), required for every kind; the two-try limit
#   --owner-override TEXT   the owner's decision allowing a third try of the idea (recorded verbatim)
#   --cap N      LTC search: 4-6 stages (default 6); fixed: the stages to play
#   --origin N   the first stage index (default 0); later indices are new openings
#   --first N    resume at stage N (default the origin)
#   ELO0, ELO1   custom nElo bounds (e.g. -3 0 for non-regression); FIRST, LAST
#                the stages to run, default 0 and 12 (13 stages of 1,600 games)
#
# Kinds (owner, DESIGN.md §6 2026-11-07 decision 2 and the owner's answers
# the same day), each fixed before the first dispatch:
# - search (design R): [0, 6] nElo, alpha 0.05, beta 0.20; a cap of 8 stages
#   at STC (TC 8+0.08, 1,600 games, Hash 16) and 6 at LTC (TC 40+0.4, 1,664
#   games, Hash 64; --cap 4-6); one futility look after 2 stages: stop and
#   reject if the nElo estimate of the 2 stages' summed pentanomial is below 0;
# - network: [0, 5] nElo, alpha = beta = 0.05, 13 stages at STC, 6 at LTC, no
#   futility stop;
# - fixed: plays exactly --cap stages and reports "complete" (head-to-head
#   pairings, tools/github/h2h_run.sh); not a try;
# - custom (the positional bounds): alpha = beta = 0.05, stages FIRST to LAST,
#   byte for byte the driver before 2026-11-07, so an SPRT started with it
#   resumes unchanged.
# A search or network SPRT is a try of its idea: at most two per idea and
# time control class (tools/jobs/ledger.py try), a third only with
# --owner-override. The design goes to $SPRT_DATA/NAME/design.json before the
# first dispatch; a restart with any other design is refused. The verdict
# goes to $SPRT_DATA/NAME/verdict: H1 accepted, H0 accepted, futility stop,
# capped (undecided at the cap: not passed) or complete.
#
# Rules (2026-11-02; an earlier driver, left running after its SPRT was
# cancelled, kept dispatching stages against a test commit that was no
# longer on GitHub, beside other runs):
# - both commits must be on GitHub before the first dispatch;
# - one SPRT stage at a time, within the runner capacity (owner, 2026-11-10,
#   replacing "no run of any workflow in progress": a scheduled nightly's
#   four-hour TSan job held every stage back): a stage is dispatched only
#   when no other sprt run is queued or in progress and the jobs the other
#   workflows' runs still hold leave room for its SHARDS shard jobs plus its
#   build job within FORK_GH_JOBS concurrent jobs (20, the Free plan's limit
#   for standard GitHub-hosted runners; docs.github.com, Actions limits); a
#   run whose jobs are not listed yet counts as holding them all;
# - it stops at the first stage whose run does not succeed;
# - every shard result merged must name this SPRT's base and test commits
#   and its own stage (result.json's meta), and the stage must have SHARDS
#   of them, so a run picked up by mistake is never merged.
# Rules (owner, 2026-11-05; two drivers believed stopped kept dispatching,
# and one waited on the other's run):
# - it runs only under the job supervisor (tools/jobs/jobctl.py start github
#   NAME -- ...), which allows one job of type github at a time and stops a
#   job's whole process tree; started any other way it refuses;
# - it finds the run it dispatched by the run's title, which sprt.yml builds
#   from its inputs ("sprt BASE TEST stage N"), among runs newer than the
#   dispatch and not yet in the ledger, never as "the newest sprt run";
# - every dispatched run goes into the run-ID ledger (tools/jobs/ledger.py)
#   with its inputs, and a stage's results are merged only if the ledger
#   records that stage's run, with this SPRT's commits, and the stage's
#   folder holds that run's download (s<stage>/run_id); RUN_ID is accepted
#   only for a run the ledger already records for that stage (a run
#   attributed after the fact goes in with ledger.py add --source import).
#
# Environment: TC (default 8+0.08), HASH (16; 64 at LTC for the kinds),
# GAMES (1600 per stage; 1664 at LTC for the kinds), SHARDS (16), TABLES (on),
# BASE_OPTS and TEST_OPTS (fastchess engine options, default none), REF (the
# branch whose sprt.yml runs; default the current branch), REPO (owner/name;
# default origin's), GH (the gh command; default gh), PYTHON (default the
# repository's .venv, else python3), SPRT_DATA (default ~/fork-sprt/github),
# POLL (seconds between status checks, default 120), RUN_ID (the first
# stage's run was already dispatched, e.g. by a driver that was stopped: wait
# for that run instead of dispatching; the ledger must record it), FORK_JOBS
# (the supervisor's and the ledger's folder, default ~/fork-jobs),
# SPRT_UNSUPERVISED=1 (tests only: run without the supervisor).
#
# Exit status: 0 decided (H1, H0 or a futility stop) or a fixed run complete,
# 2 undecided at the cap, 1 stopped by a rule above or an error.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.."
kind=custom idea= override= have_override=0 opt_cap= origin=0 opt_first=
pos=()
while [ $# -gt 0 ]; do
  case $1 in
    --kind | --idea | --owner-override | --cap | --origin | --first)
      [ $# -ge 2 ] || { echo "sprt_run.sh: $1 needs a value" >&2; exit 1; }
      case $1 in
        --kind) kind=$2 ;;
        --idea) idea=$2 ;;
        --owner-override) override=$2 have_override=1 ;;
        --cap) opt_cap=$2 ;;
        --origin) origin=$2 ;;
        --first) opt_first=$2 ;;
      esac
      shift 2 ;;
    --*) echo "sprt_run.sh: unknown option $1" >&2; exit 1 ;;
    *) pos+=("$1"); shift ;;
  esac
done
set -- "${pos[@]}"
if { [ "$kind" = custom ] && [ $# -lt 5 ]; } || [ $# -lt 3 ]; then
  sed -n '7,20p' "$here/sprt_run.sh" >&2
  exit 1
fi
if [ "$kind" = custom ]; then
  name=$1 elo0=$4 elo1=$5 first=${6:-0} last=${7:-12}
else
  name=$1 first=
fi
GH=${GH:-gh}
POLL=${POLL:-120}
GH_JOBS=${FORK_GH_JOBS:-20}
SHARDS=${SHARDS:-16}
data=${SPRT_DATA:-$HOME/fork-sprt/github}/$name
mkdir -p "$data"
say() { echo "$(date -u '+%Y-%m-%d %H:%M UTC') $name: $*" | tee -a "$data/driver.log"; }
stop() { say "$*; stopping"; exit 1; }
# A gh call a transient network or GitHub error must not end (2026-11-08: a results download and a commit
# check failed within a minute while GitHub was healthy, and gh's message was discarded): up to GH_TRIES
# attempts, GH_RETRY_WAIT seconds apart, each failure's last line of output in the log (on stderr, so a
# caller's $(...) captures only gh's answer).
GH_TRIES=${GH_TRIES:-5}
GH_RETRY_WAIT=${GH_RETRY_WAIT:-30}
gh_retry() {  # what, command...
  local what=$1 n out
  shift
  for n in $(seq "$GH_TRIES"); do
    out=$("$@" 2>&1) && { printf '%s\n' "$out"; return 0; }
    say "$what: attempt $n of $GH_TRIES failed: $(printf '%s\n' "$out" | tail -1)" >&2
    [ "$n" -lt "$GH_TRIES" ] && sleep "$GH_RETRY_WAIT"
  done
  return 1
}

py=${PYTHON:-}
if [ -z "$py" ]; then
  for c in .venv/Scripts/python.exe .venv/bin/python python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c pass >/dev/null 2>&1; then py=$c; break; fi
  done
fi
[ -n "$py" ] || stop "no Python for the merge"
[ -n "${FORK_JOB:-}" ] || [ "${SPRT_UNSUPERVISED:-}" = 1 ] ||
  stop "not started by the job supervisor (tools/jobs/jobctl.py start github $name -- $0 ...)"
ledger() { "$py" -I tools/jobs/ledger.py "$@"; }

# The design of a kind (the table in the header); refuses what the owner's decisions do not allow.
design_defaults() {
  local n
  case $kind in search | network | fixed) ;; *) stop "unknown --kind '$kind' (search, network or fixed)" ;; esac
  [ $# -eq 3 ] || stop "kind $kind takes its bounds from its design, not positional ELO0 ELO1"
  [ -n "$idea" ] || stop "kind $kind needs --idea ID (the idea under test; each retrain is its own idea)"
  [[ $idea =~ ^[a-z0-9][a-z0-9.-]{0,47}$ ]] || stop "--idea '$idea' is not [a-z0-9][a-z0-9.-]*"
  [ "$have_override" = 0 ] || [ -n "${override//[[:space:]]/}" ] || stop "--owner-override needs the owner's decision"
  for n in "$origin" "$opt_first" "$opt_cap"; do
    case $n in *[!0-9]*) stop "--origin, --first and --cap take whole numbers" ;; esac
  done
  TC=${TC:-8+0.08}
  case $TC in
    8+0.08) tc_class=stc ;;
    40+0.4) tc_class=ltc ;;
    *) stop "kind $kind runs at TC 8+0.08 (STC) or 40+0.4 (LTC); use the positional (custom) form for others" ;;
  esac
  if [ "$tc_class" = stc ]; then GAMES=${GAMES:-1600} HASH=${HASH:-16}; else GAMES=${GAMES:-1664} HASH=${HASH:-64}; fi
  case $kind in
    search)
      elo0=0 elo1=6 alpha=0.05 beta=0.20 futility_after=2
      if [ "$tc_class" = stc ]; then
        [ -z "$opt_cap" ] || [ "$opt_cap" = 8 ] || stop "kind search at STC has design R's cap of 8 stages"
        cap=8
      else
        cap=${opt_cap:-6}
        case $cap in 4 | 5 | 6) ;; *) stop "kind search at LTC takes --cap 4, 5 or 6 (default 6)" ;; esac
      fi ;;
    network)
      elo0=0 elo1=5 alpha=0.05 beta=0.05 futility_after=0
      [ -z "$opt_cap" ] || stop "kind network keeps its caps (13 stages at STC, 6 at LTC)"
      if [ "$tc_class" = stc ]; then cap=13; else cap=6; fi ;;
    fixed)
      elo0=0 elo1=6 alpha=0.05 beta=0.20 futility_after=0
      [ -n "$opt_cap" ] && [ "$opt_cap" -ge 1 ] || stop "kind fixed needs --cap N (the stages to play)"
      cap=$opt_cap ;;
  esac
  first=${opt_first:-$origin}
  last=$((origin + cap - 1))
  [ "$first" -ge "$origin" ] && [ "$first" -le "$last" ] || stop "--first $first is outside stages $origin to $last"
}

# Writes $data/design.json, or compares the requested design with it (a restart may not change it).
declare_design() {
  "$py" -I - "$data/design.json" kind="$kind" tc_class="$tc_class" tc="$TC" hash="$HASH" games="$GAMES" \
    shards="$SHARDS" tables="${TABLES:-on}" base_opts="${BASE_OPTS:-}" test_opts="${TEST_OPTS:-}" elo0="$elo0" \
    elo1="$elo1" alpha="$alpha" beta="$beta" cap="$cap" futility_after="$futility_after" origin="$origin" \
    idea="$idea" base="$base" test="$test" <<'EOF'
import json, sys, time
path, want = sys.argv[1], dict(kv.split('=', 1) for kv in sys.argv[2:])
try:
    have = json.load(open(path, encoding='utf-8'))
except FileNotFoundError:
    json.dump(dict(want, declared_at=time.strftime('%Y-%m-%dT%H:%M:%S%z')), open(path, 'w', encoding='utf-8'),
              indent=1, sort_keys=True)
    sys.exit(0)
for k in sorted(set(want) | set(have) - {'declared_at'}):
    if want.get(k) != have.get(k):
        print(f'{k} {want.get(k)!r} differs from the declared design\'s {have.get(k)!r} ({path})')
        sys.exit(1)
EOF
}

[ "$kind" = custom ] || design_defaults "$@"
command -v "$GH" >/dev/null 2>&1 || stop "no gh command '$GH' (set GH to its path)"
base=$(git rev-parse --verify --quiet "$2^{commit}") || stop "base $2 is not a commit in this clone"
test=$(git rev-parse --verify --quiet "$3^{commit}") || stop "test $3 is not a commit in this clone"
REF=${REF:-$(git rev-parse --abbrev-ref HEAD)}
REPO=${REPO:-$(git remote get-url origin | sed -E 's#^(https://github\.com/|git@github\.com:)##; s#\.git$##')}
for c in "$base" "$test"; do
  gh_retry "commit check $c" "$GH" api "repos/$REPO/commits/$c" --jq .sha >/dev/null ||
    stop "commit $c is not on GitHub ($REPO)"
done

header="base $base, test $test, bounds [$elo0, $elo1], stages $first to $last, ref $REF"
bounds="$elo0 $elo1"
if [ "$kind" != custom ]; then
  try_args=()
  if [ "$kind" != fixed ]; then
    try_args=(try "$idea" "$name" --kind "$kind" --tc-class "$tc_class" --base "$base" --test "$test")
    [ "$have_override" = 0 ] || try_args+=(--owner-override "$override")
    trymsg=$(ledger "${try_args[@]}" --check 2>&1) || stop "$trymsg"
  else
    trymsg="head-to-head pairing, not a try"
  fi
  why=$(declare_design) || stop "the requested design: $why"
  for s in $(seq "$origin" $((first - 1))); do
    rid=$(cat "$data/s$s/run_id" 2>/dev/null)
    [ -n "$rid" ] && ledger check "$name" "$s" "$rid" "$base" "$test" ||
      stop "resuming at stage $first: stage $s has no recorded results"
  done
  bounds="$elo0 $elo1 $alpha $beta"
  case $futility_after in 0) fut="no futility stop" ;; *) fut="futility after $futility_after stages" ;; esac
  [ "$kind" != fixed ] || fut="fixed length"
  header="$header, kind $kind, $tc_class, alpha $alpha, beta $beta, cap $cap, $fut, idea $idea ($trymsg)"
fi

# Prints the number of runs not completed; anything but "0" (gh failing
# included) counts as busy.
# The runs not completed, "ID WORKFLOW" per line.
pending() { "$GH" run list -R "$REPO" -L 50 --json databaseId,status,workflowName   --jq '.[] | select(.status != "completed") | "\(.databaseId) \(.workflowName)"' 2>/dev/null; }
# Exit 0 when a stage can go now: no other sprt run pending, and room for SHARDS + 1 jobs beside what the other
# runs still hold (their jobs not completed; a run with none listed yet counts as holding all GH_JOBS). Any gh
# failure means "not now".
room() {
  local list rid wf n held=0
  list=$(pending) || return 1
  while read -r rid wf; do
    [ -n "$rid" ] || continue
    [ "$wf" = sprt ] && return 1
    n=$("$GH" api "repos/$REPO/actions/runs/$rid/jobs?per_page=100"       --jq '[.jobs[] | select(.status != "completed")] | length' 2>/dev/null) || return 1
    case $n in '' | *[!0-9]*) return 1 ;; esac
    [ "$n" -gt 0 ] || n=$GH_JOBS
    held=$((held + n))
  done <<<"$list"
  [ $((GH_JOBS - held)) -ge $((SHARDS + 1)) ]
}
# The newest sprt runs, "ID TITLE" per line.
runs() { "$GH" run list -R "$REPO" -w sprt.yml -L 30 --json databaseId,displayTitle \
  --jq '.[] | "\(.databaseId) \(.displayTitle)"' 2>/dev/null; }

say "$header"
for stage in $(seq "$first" "$last"); do
  title="sprt $base $test stage $stage"
  if [ "$stage" = "$first" ] && [ -n "${RUN_ID:-}" ]; then
    id=$RUN_ID
    ledger check "$name" "$stage" "$id" "$base" "$test" ||
      stop "stage $stage: RUN_ID $id is not in the ledger as this SPRT's stage $stage (ledger.py add --source import)"
    say "stage $stage: waiting for run $id (RUN_ID, in the ledger)"
  else
    until room; do sleep "$POLL"; done
    before=$(runs | awk 'NR == 1 {print $1}')
    before=${before:-0}
    "$GH" workflow run sprt.yml -R "$REPO" --ref "$REF" -f base="$base" -f test="$test" -f bounds="$bounds" \
      -f tc="${TC:-8+0.08}" -f hash="${HASH:-16}" -f games="${GAMES:-1600}" -f shards="$SHARDS" -f stage="$stage" \
      -f tables="${TABLES:-on}" -f test_opts="${TEST_OPTS:-}" -f base_opts="${BASE_OPTS:-}" >/dev/null 2>&1 ||
      stop "stage $stage: dispatch failed"
    id=
    for _ in $(seq 30); do
      sleep $((POLL < 10 ? POLL : 10))
      mine=$(runs | while read -r rid rtitle; do
        [ "$rid" -gt "$before" ] && [ "$rtitle" = "$title" ] && ! ledger known "$rid" && echo "$rid"
      done)
      [ -n "$mine" ] && break
    done
    [ -n "$mine" ] || stop "stage $stage: no new run titled '$title' after the dispatch"
    [ "$(echo "$mine" | wc -l)" -eq 1 ] || stop "stage $stage: more than one new run titled '$title': $(echo $mine)"
    id=$mine
    ledger add "$name" "$stage" "$id" --base "$base" --test "$test" || stop "stage $stage: run $id: ledger refused it"
    say "stage $stage: run $id dispatched (ledger)"
    # The try counts from its first dispatched run (a resume is not a new try).
    if [ "$kind" = search ] || [ "$kind" = network ]; then
      ledger "${try_args[@]}" >/dev/null 2>&1 || stop "stage $stage: the ledger refused the try record"
    fi
  fi
  while [ "$("$GH" run view "$id" -R "$REPO" --json status --jq .status 2>/dev/null)" != completed ]; do sleep "$POLL"; done
  concl=$(gh_retry "stage $stage: run $id's conclusion" "$GH" run view "$id" -R "$REPO" --json conclusion --jq .conclusion)
  [ "$concl" = success ] || stop "stage $stage: run $id ended '$concl'"
  # A failed attempt may leave part of the download, so each attempt starts from an empty folder.
  gh_retry "stage $stage: run $id's download" bash -c 'rm -rf "$1" && mkdir -p "$1" && "$0" run download "$2" -R "$3" -D "$1"' \
    "$GH" "$data/s$stage" "$id" "$REPO" >/dev/null || stop "stage $stage: run $id's download failed"
  echo "$id" >"$data/s$stage/run_id"
  # The shard results of this SPRT's stages up to this one (earlier stages too
  # when resuming), each checked against this SPRT's commits and its stage.
  # Only stages the ledger records for this SPRT, each folder holding its recorded run's download.
  # The kinds need every stage from the origin (the stages played count); custom skips missing ones.
  files=()
  if [ "$kind" = custom ]; then from=0; else from=$origin; fi
  for s in $(seq "$from" "$stage"); do
    if [ ! -d "$data/s$s" ]; then
      [ "$kind" = custom ] && continue
      stop "stage $stage: stage $s has no results"
    fi
    rid=$(cat "$data/s$s/run_id" 2>/dev/null)
    [ -n "$rid" ] && ledger check "$name" "$s" "$rid" "$base" "$test" ||
      stop "stage $stage: stage $s's results (run ${rid:-unknown}) are not in the ledger as this SPRT's stage $s"
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
  if [ "$kind" = custom ]; then
    merged=$("$py" -I tools/cloud/sprt_merge.py merge --elo0 "$elo0" --elo1 "$elo1" "${files[@]}" 2>&1 | tail -5)
  else
    staged=(--alpha "$alpha" --beta "$beta" --played $((stage - origin + 1)) --cap "$cap" --futility-after "$futility_after")
    [ "$kind" != fixed ] || staged+=(--fixed)
    merged=$("$py" -I tools/cloud/sprt_merge.py merge --elo0 "$elo0" --elo1 "$elo1" "${staged[@]}" "${files[@]}" 2>&1 | tail -6)
  fi
  say "stage $stage: run $id merged"
  echo "$merged" | sed 's/^/    /' | tee -a "$data/driver.log"
  if [ "$kind" = custom ]; then
    case $(echo "$merged" | grep -E '^LLR:' | tail -1) in
      *continue*) ;;
      *accepted*) say "decided after stage $stage"; exit 0 ;;
      *) stop "stage $stage: no LLR line in the merge" ;;
    esac
    continue
  fi
  v=$(echo "$merged" | sed -n 's/^Verdict: //p' | tail -1)
  case $v in
    continue) ;;
    "H1 accepted" | "H0 accepted") echo "$v" >"$data/verdict"; say "decided after stage $stage: $v"; exit 0 ;;
    "futility stop"*) echo "futility stop" >"$data/verdict"; say "decided after stage $stage: $v, rejected"; exit 0 ;;
    capped*) echo capped >"$data/verdict"; say "undecided after stage $stage: $v, not passed"; exit 2 ;;
    complete*) echo complete >"$data/verdict"; say "complete after stage $stage: $v"; exit 0 ;;
    *) stop "stage $stage: no Verdict line in the merge" ;;
  esac
done
say "undecided after stage $last"
exit 2
