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
# stops it, unmerged. Since 2026-11-07 (design R, owner, DESIGN.md §6
# decision 2): the kinds search, network and fixed with their bounds,
# alpha/beta, caps and the futility stop after 2 stages; the declared
# design cannot change on a restart; the two-try limit per idea and time
# control class. Since 2026-11-08: a transient gh failure (injected) of the
# commit check, the conclusion or the download is retried, its message
# logged; a lasting one still stops it. Since 2026-11-10 (owner: a scheduled
# nightly no longer holds a stage back): a stage goes out beside other
# workflows' runs when the jobs they still hold leave room for its shards and
# build within FORK_GH_JOBS (20); a run whose jobs are not listed yet counts
# as full; another sprt run still blocks. Uses python3 (or $PYTHON) for the merge and the ledger.
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

cp "$here/fake_gh.sh" "$tmp/gh"  # the fake gh (state in files; see its header)
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
    FORK_JOBS=${JOBS:-$tmp/$label/jobs} SPRT_UNSUPERVISED=${UNSUPERVISED-1} GH_TRIES=3 GH_RETRY_WAIT=0 \
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

# The capacity check (owner, 2026-11-10): a nightly holding one job does not
# hold a stage back; a run holding 18 of the 20 jobs does until it drops to 17
# (20 - 17 = 3 = 2 shards + the build); a run whose jobs are not listed yet
# counts as full. FORK_GH_JOBS is 20 by default; a hang is cut at 30 s.
drive_t() {  # label args... (as drive, with a time limit)
  local label=$1
  shift
  FAKE_GH=$tmp/$label GH=$tmp/gh POLL=0 SHARDS=2 REPO=owner/fork REF=test SPRT_DATA=$tmp/$label/data     FORK_JOBS=$tmp/$label/jobs SPRT_UNSUPERVISED=1 GH_TRIES=3 GH_RETRY_WAIT=0     timeout 30 bash "$here/sprt_run.sh" "$label" "$@" >"$tmp/$label/out" 2>&1
  echo $? >"$tmp/$label/rc"
}
setup nightly 0 "$strong"
echo "900 nightly 1" >"$tmp/nightly/active"
drive_t nightly "$sha" "$sha" 0 5
check "a nightly holding one job does not hold the stage back" [ "$(rc nightly)" = 0 ]
check "dispatched beside the nightly" grep -q "^501 busy=0 jobs=1 " "$tmp/nightly/dispatches"
setup full 0 "$strong"
echo "901 ci 18" >"$tmp/full/active"
: >"$tmp/full/drain"
drive_t full "$sha" "$sha" 0 5
check "a run holding 18 of 20 jobs waits, then the stage goes" [ "$(rc full)" = 0 ]
# The fake lowers a run's count after each query: the query that saw 17 (3 free) leaves 16 at the dispatch; a
# dispatch on the query that saw 18 would show 17.
check "dispatched only when 3 jobs were free" grep -q "^501 busy=0 jobs=16 " "$tmp/full/dispatches"
setup unlisted 0 "$strong"
echo "902 ci 0" >"$tmp/unlisted/active"
drive_t unlisted "$sha" "$sha" 0 5
check "a run with no jobs listed yet counts as full: no dispatch" [ "$(dispatches unlisted)" = 0 ]

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

# Design R (owner, DESIGN.md §6 2026-11-07 decision 2): kind search is [0, 6] nElo, alpha 0.05, beta
# 0.20, a cap of 8 stages (6 at LTC by default, 4-6 allowed), one futility look after 2 stages; kind
# network keeps [0, 5] at alpha = beta = 0.05; kind fixed plays exactly --cap stages. Every kind but the
# positional (custom) one needs an idea id. A refusal: exit 1, no new dispatch, the reason named.
futile='[6, 11, 20, 9, 4]'  # per stage nElo -27.08, LLR -0.30 on [0, 6]: -0.60 after 2 stages
verdict() { cat "$tmp/$1/data/$1/verdict" 2>/dev/null; }
stages() { grep -o 'stage=[0-9]*' "$tmp/$1/dispatches" | tr '\n' ' '; }
check "the futile counts stay inside design R's LLR bounds after 2 stages (a futility stop is not an H0)" \
  "$PYTHON" -I -c "
import sys; sys.path.insert(0, sys.argv[1]); import sprt_merge as sm
p = [4 * x for x in [6, 11, 20, 9, 4]]; lo, hi = sm.bounds(0.05, 0.20)
sys.exit(not (lo < sm.llr(p, 0, 6) < hi and sm.nelo(p) < 0))" "$here/../cloud"

setup r-h1 0 "$strong"
drive r-h1 --kind search --idea t1 "$sha" "$sha"
check "design R: H1 exits 0 after one dispatch" [ "$(rc r-h1):$(dispatches r-h1)" = 0:1 ]
check "design R: the LLR bounds are alpha 0.05, beta 0.20's" grep -q "LLR: .* (-1.56, 2.77) \[0.00, 6.00\] nElo: H1 accepted" "$tmp/r-h1/out"
check "design R: bounds, alpha and beta dispatched" grep -q "bounds=0 6 0.05 0.20" "$tmp/r-h1/dispatches"
check "design R: the verdict file says H1" [ "$(verdict r-h1)" = "H1 accepted" ]
check "design R: the header names the design and the try" grep -q "bounds \[0, 6\], stages 0 to 7, ref test, kind search, stc, alpha 0.05, beta 0.20, cap 8, futility after 2 stages, idea t1 (try 1 of 2)" "$tmp/r-h1/out"

setup r-futility 0 "$futile"
drive r-futility --kind search --idea t2 "$sha" "$sha"
check "futility: exits 0 (decided) after exactly 2 dispatches" [ "$(rc r-futility):$(dispatches r-futility)" = 0:2 ]
check "futility: the stop and its estimate are logged" grep -q "decided after stage 1: futility stop (nElo -27.08 < 0 after 2 stages), rejected" "$tmp/r-futility/data/r-futility/driver.log"
check "futility: the verdict file says so" [ "$(verdict r-futility)" = "futility stop" ]

setup r-stage-cap 0 "$even"
drive r-stage-cap --kind search --idea t3 "$sha" "$sha"
check "cap: undecided exits 2 after exactly 8 stages, 0 to 7" [ "$(rc r-stage-cap):$(stages r-stage-cap)" = "2:stage=0 stage=1 stage=2 stage=3 stage=4 stage=5 stage=6 stage=7 " ]
check "cap: logged as capped" grep -q "undecided after stage 7: capped (8 of 8 stages, undecided), not passed" "$tmp/r-stage-cap/out"
check "cap: the verdict file says capped" [ "$(verdict r-stage-cap)" = capped ]

setup r-origin 0 "$futile"
drive r-origin --kind search --idea t4 --origin 3 "$sha" "$sha"
check "origin 3: stages 3 and 4 only, then the futility stop" [ "$(rc r-origin):$(stages r-origin)" = "0:stage=3 stage=4 " ]

setup r-ltc 0 "$even"
TC=40+0.4 drive r-ltc --kind search --idea t5 --cap 7 "$sha" "$sha"
check "LTC: a cap of 7 is refused before any dispatch" eval '[ "$(rc r-ltc)" = 1 ] && [ "$(dispatches r-ltc)" = 0 ] && grep -qF -- "kind search at LTC takes --cap 4, 5 or 6" "$tmp/r-ltc/out"'
TC=40+0.4 drive r-ltc --kind search --idea t5 --cap 4 "$sha" "$sha"
check "LTC: --cap 4 plays 4 stages" [ "$(rc r-ltc):$(dispatches r-ltc)" = 2:4 ]
check "LTC: 1,664 games and 64 MB per stage" grep -q "tc=40+0.4 -f hash=64 -f games=1664" "$tmp/r-ltc/dispatches"
setup r-ltc6 0 "$even"
TC=40+0.4 drive r-ltc6 --kind search --idea t5b "$sha" "$sha"
check "LTC: the default cap is 6 stages" [ "$(rc r-ltc6):$(dispatches r-ltc6)" = 2:6 ]
setup r-stc-cap 0 "$even"
drive r-stc-cap --kind search --idea t6 --cap 6 "$sha" "$sha"
check "STC: design R's cap of 8 cannot be changed" eval '[ "$(rc r-stc-cap)" = 1 ] && [ "$(dispatches r-stc-cap)" = 0 ] && grep -qF -- "kind search at STC has design R'\''s cap of 8 stages" "$tmp/r-stc-cap/out"'
setup r-oddtc 0 "$even"
TC=120+1.2 drive r-oddtc --kind search --idea t6b "$sha" "$sha"
check "another time control is refused for kind search" eval '[ "$(rc r-oddtc)" = 1 ] && [ "$(dispatches r-oddtc)" = 0 ] && grep -qF -- "kind search runs at TC 8+0.08 (STC) or 40+0.4 (LTC)" "$tmp/r-oddtc/out"'

setup r-network 0 "$futile"
drive r-network --kind network --idea n1 "$sha" "$sha"
check "network: [0, 5] at alpha = beta = 0.05 dispatched" grep -q "bounds=0 5 0.05 0.05" "$tmp/r-network/dispatches"
check "network: no futility stop (more than 2 stages, none logged)" bash -c "[ \$(wc -l <'$tmp/r-network/dispatches') -gt 2 ] && grep -q 'no futility stop' '$tmp/r-network/out' && ! grep -q 'futility stop (nElo' '$tmp/r-network/out'"

setup r-fixed 0 "$strong"
drive r-fixed --kind fixed --idea f1 --cap 2 "$sha" "$sha"
check "fixed: an H1 does not stop it; exactly 2 stages, exit 0" [ "$(rc r-fixed):$(dispatches r-fixed)" = 0:2 ]
check "fixed: the verdict file says complete" [ "$(verdict r-fixed)" = complete ]

drive r-stage-cap --kind network --idea t3 "$sha" "$sha"
check "redesign: a restart with another design is refused" eval '[ "$(rc r-stage-cap)" = 1 ] && [ "$(dispatches r-stage-cap)" = 8 ] && grep -qF -- "differs from the declared design" "$tmp/r-stage-cap/out"'

setup r-missing-stage 0 "$even"
drive r-missing-stage --kind search --idea t7 --first 1 "$sha" "$sha"
check "resume past a stage with no results exits 1 before any dispatch" eval '[ "$(rc r-missing-stage)" = 1 ] && [ "$(dispatches r-missing-stage)" = 0 ] && grep -qF -- "resuming at stage 1: stage 0 has no recorded results" "$tmp/r-missing-stage/out"'

setup r-noidea 0 "$strong"
drive r-noidea --kind search "$sha" "$sha"
check "kind search without --idea is refused" eval '[ "$(rc r-noidea)" = 1 ] && [ "$(dispatches r-noidea)" = 0 ] && grep -qF -- "kind search needs --idea" "$tmp/r-noidea/out"'
drive r-noidea --kind network "$sha" "$sha"
check "kind network without --idea is refused" eval '[ "$(rc r-noidea)" = 1 ] && [ "$(dispatches r-noidea)" = 0 ] && grep -qF -- "kind network needs --idea" "$tmp/r-noidea/out"'
drive r-noidea --kind search --idea t8 "$sha" "$sha" 0 6
check "kind search with positional bounds is refused" eval '[ "$(rc r-noidea)" = 1 ] && [ "$(dispatches r-noidea)" = 0 ] && grep -qF -- "kind search takes its bounds from its design" "$tmp/r-noidea/out"'

# The two-try limit, per idea and time control class, in one jobs folder (run ids kept apart).
tries=$tmp/tries-jobs
n=600
for t in r-tries-a r-tries-b r-tries-c r-tries-d; do setup $t 0 "$strong"; echo $n >"$tmp/$t/latest"; n=$((n + 100)); done
JOBS=$tries drive r-tries-a --kind search --idea t9 "$sha" "$sha"
JOBS=$tries drive r-tries-b --kind search --idea t9 "$sha" "$sha"
check "tries: the first two run" [ "$(rc r-tries-a):$(rc r-tries-b)" = 0:0 ]
JOBS=$tries drive r-tries-c --kind search --idea t9 "$sha" "$sha"
check "tries: a third is refused before any dispatch" eval '[ "$(rc r-tries-c)" = 1 ] && [ "$(dispatches r-tries-c)" = 0 ] && grep -qF -- "another needs --owner-override" "$tmp/r-tries-c/out"'
check "tries: the refusal names the earlier tries" grep -q "already has 2 stc tries (r-tries-a, r-tries-b)" "$tmp/r-tries-c/out"
JOBS=$tries drive r-tries-a --kind search --idea t9 "$sha" "$sha"
check "tries: a restart of a recorded try is not a new try" [ "$(rc r-tries-a)" = 0 ]
JOBS=$tries drive r-tries-c --kind search --idea t9 --owner-override "owner test: third try" "$sha" "$sha"
check "tries: with an owner override the third runs" [ "$(rc r-tries-c):$(dispatches r-tries-c)" = 0:1 ]
check "tries: the override is recorded verbatim" grep -q '"override": "owner test: third try"' "$tries/tries.jsonl"
check "tries: and named in the header" grep -q "idea t9 (try 3, owner override: owner test: third try)" "$tmp/r-tries-c/out"
check "tries: three records" [ "$(wc -l <"$tries/tries.jsonl" | tr -d ' ')" = 3 ]
TC=40+0.4 JOBS=$tries drive r-tries-d --kind search --idea t9 --cap 4 "$sha" "$sha"
check "tries: an LTC test of the same idea is counted apart" [ "$(rc r-tries-d)" = 0 ]

# 26-29: transient gh failures (2026-11-08: a download and a commit check failed within a minute while
# GitHub was healthy) are retried: two injected failures each of the commit check, the conclusion and the
# download, with three tries allowed, still decide the SPRT, and gh's message is in the driver's log.
setup flaky 0 "$strong"
for k in api conclusion download; do echo 2 >"$tmp/flaky/flaky.$k"; done
drive flaky "$sha" "$sha" 0 5
check "transient gh failures are retried: H1 exits 0" [ "$(rc flaky)" = 0 ]
check "still one dispatch" [ "$(dispatches flaky)" = 1 ]
check "gh's message is logged" grep -q "attempt 1 of 3 failed: fake gh: download: connection reset (injected)" "$tmp/flaky/data/flaky/driver.log"
# 30-31: a lasting failure still stops it, unmerged.
setup flakyall 0 "$strong"
echo 9 >"$tmp/flakyall/flaky.download"
drive flakyall "$sha" "$sha" 0 5
check "a lasting download failure exits 1" [ "$(rc flakyall)" = 1 ]
check "it is named, nothing merged" bash -c "grep -q \"run 501's download failed\" '$tmp/flakyall/out' && ! grep -q LLR '$tmp/flakyall/out'"

if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed"
  for d in "$tmp"/*/; do [ -f "$d/out" ] && { echo "--- $d"; tail -5 "$d/out"; }; done
  exit 1
fi
echo "all checks passed"
