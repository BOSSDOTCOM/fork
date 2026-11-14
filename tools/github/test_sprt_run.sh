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
# build within FORK_GH_JOBS (40 by default since 2026-11-11, 20 before); a run whose jobs are not listed yet counts
# as full. Since 2026-11-10 9:30 PM (owner, GitHub Pro): another sprt run counts its jobs like any
# other run instead of blocking (two SPRT lanes); FORK_SPRT_SERIAL=1 restores the block. Since 2026-11-12 (the
# owner's rule of 2026-11-11: TT-policy tests at a pressure-matched Hash): --hash MB sets both engines' Hash for every
# kind and is part of the declared design (a restart with another Hash is refused); a bad value or a differing HASH
# is refused before any dispatch; without it the default (16; 64 at LTC) is unchanged. Since 2026-11-12 the custom
# (positional) form writes the verdict file too: H1 accepted, H0 accepted, or capped at its last stage. Since 2026-11-13 (owner:
# CalibratedScore off in every harness, branch workflows included): a REF older than c7a61ea (no
# tools/check_score_display_off.py) is refused before any dispatch when an engine has the option, and allowed when
# neither has it (the option was removed the same day; c7a61ea's engine stands in for one that has it). Uses python3 (or $PYTHON) for
# the merge and the ledger.
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
  echo "$sha" >"$st/ref.test"  # REF (test) points to this repository's HEAD, which forces CalibratedScore off
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
. "$here/../jobs/paths.sh" || exit 1
ledger() {  # label args...; the paths in the form $PYTHON takes (DESIGN.md section 1)
  local label=$1
  shift
  FORK_JOBS=$(fork_path_for "$PYTHON" "$tmp/$label/jobs") \
    "$PYTHON" -I "$(fork_path_for "$PYTHON" "$here/../jobs/ledger.py")" "$@"
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
# hold a stage back; a run holding 38 of the 40 jobs does until it drops to 37
# (40 - 37 = 3 = 2 shards + the build); a run whose jobs are not listed yet
# counts as full. FORK_GH_JOBS is 40 by default (owner, 2026-11-11; 20 before);
# a hang is cut at 30 s.
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
echo "901 ci 38" >"$tmp/full/active"
: >"$tmp/full/drain"
drive_t full "$sha" "$sha" 0 5
check "a run holding 38 of 40 jobs waits, then the stage goes" [ "$(rc full)" = 0 ]
# The fake lowers a run's count after each query: the query that saw 37 (3 free) leaves 36 at the dispatch; a
# dispatch on the query that saw 38 would show 37.
check "dispatched only when 3 jobs were free" grep -q "^501 busy=0 jobs=36 " "$tmp/full/dispatches"
setup was20 0 "$strong"
echo "906 ci 18" >"$tmp/was20/active"
drive_t was20 "$sha" "$sha" 0 5
check "the default is 40: a run holding 18 jobs (full under the old 20) does not hold the stage back" grep -q "^501 busy=0 jobs=18 " "$tmp/was20/dispatches"
setup unlisted 0 "$strong"
echo "902 ci 0" >"$tmp/unlisted/active"
drive_t unlisted "$sha" "$sha" 0 5
check "a run with no jobs listed yet counts as full: no dispatch" [ "$(dispatches unlisted)" = 0 ]
setup ghost 0 "$strong"
echo "907 gauntlet 0 2026-01-01T00:00:00Z" >"$tmp/ghost/active"
drive_t ghost "$sha" "$sha" 0 5
check "a run listing no jobs long after its creation is a ghost: the stage goes" [ "$(rc ghost)" = 0 ]
check "the ghost is named in the log" grep -q "ignored as a ghost" "$tmp/ghost/out"
setup fresh0 0 "$strong"
echo "908 ci 0 $(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$tmp/fresh0/active"
drive_t fresh0 "$sha" "$sha" 0 5
check "a fresh run listing no jobs yet still counts as full: no dispatch" [ "$(dispatches fresh0)" = 0 ]
setup lane2 0 "$strong"
echo "903 sprt 1" >"$tmp/lane2/active"
drive_t lane2 "$sha" "$sha" 0 5
check "another SPRT holding one job does not block: the stage goes beside it" [ "$(rc lane2)" = 0 ]
check "dispatched beside the other SPRT" grep -q "^501 busy=0 jobs=1 " "$tmp/lane2/dispatches"
setup lane2full 0 "$strong"
echo "904 sprt 38" >"$tmp/lane2full/active"
: >"$tmp/lane2full/drain"
drive_t lane2full "$sha" "$sha" 0 5
check "another SPRT holding 38 of 40 jobs: waits for room, then goes" [ "$(rc lane2full)" = 0 ]
check "dispatched beside it only when 3 jobs were free" grep -q "^501 busy=0 jobs=36 " "$tmp/lane2full/dispatches"
setup serial 0 "$strong"
echo "905 sprt 1" >"$tmp/serial/active"
FORK_SPRT_SERIAL=1 drive_t serial "$sha" "$sha" 0 5
check "FORK_SPRT_SERIAL=1: another SPRT pending blocks the dispatch" [ "$(dispatches serial)" = 0 ]

# 4-6: undecided runs every stage in order, then exits 2.
setup undecided 0 "$even"
drive undecided "$sha" "$sha" 0 5 0 2
check "undecided exits 2" [ "$(rc undecided)" = 2 ]
check "three stages dispatched" [ "$(dispatches undecided)" = 3 ]
check "stages 0, 1, 2 in order" [ "$(grep -o 'stage=[0-9]*' "$tmp/undecided/dispatches" | tr '\n' ' ')" = "stage=0 stage=1 stage=2 " ]
check "bounds passed as given" grep -q "bounds=0 5" "$tmp/undecided/dispatches"
check "custom, undecided at the last stage: the verdict file says capped" \
  [ "$(cat "$tmp/undecided/data/undecided/verdict" 2>/dev/null)" = capped ]

# The custom form writes the verdict file like the kinds (2026-11-12): H1 and H0 from the merge's LLR line.
check "custom H1: the verdict file says H1 accepted" [ "$(cat "$tmp/h1/data/h1/verdict" 2>/dev/null)" = "H1 accepted" ]
setup c-h0 0 '[25, 20, 5, 0, 0]'
drive c-h0 "$sha" "$sha" -3 0
check "custom H0 (LLR -5.14 on [-3, 0]) after two stages exits 0" eval '[ "$(rc c-h0)" = 0 ] && [ "$(dispatches c-h0)" = 2 ]'
check "custom H0: the verdict file says H0 accepted" [ "$(cat "$tmp/c-h0/data/c-h0/verdict" 2>/dev/null)" = "H0 accepted" ]

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

# Bug review 2026-11-11, T3 (owner, the same day): only complete shards are merged. A shard left "running" (its
# final snapshot never written) or one pair short of its planned rounds in a green run stops the SPRT at that
# stage, unmerged and undecided, before the next dispatch.
setup partial 0 "$even"
touch "$tmp/partial/partial.502"
drive partial --kind search --idea p1 "$sha" "$sha"
check "a partial shard: exit 1 after stage 1, no stage 2" [ "$(rc partial):$(dispatches partial)" = 1:2 ]
check "a partial shard: the refusal names it" grep -q "stage 1: run 502's results were not merged: sprt_merge.py: merge refused: 1 of 4 shards incomplete: stage 1 shard 0 has status 'running', not 'done' (50 pairs)" "$tmp/partial/out"
check "a partial shard: no verdict file, stage 1 unmerged" bash -c "[ ! -f '$tmp/partial/data/partial/verdict' ] && [ \$(grep -c 'merged$' '$tmp/partial/out') = 1 ]"
setup short 0 "$strong"
touch "$tmp/short/short.501"
drive short "$sha" "$sha" 0 5
check "a shard short of its pairs (custom kind): exit 1, nothing merged" bash -c "[ \$(cat '$tmp/short/rc') = 1 ] && ! grep -q LLR '$tmp/short/out'"
check "a short shard is named" grep -q "stage 0 shard 0 has 50 pairs of 51 planned" "$tmp/short/out"

# Bug review 2026-11-11, T6: the SPRT's name is in the run's title when REF's sprt.yml takes it, so another lane's
# run of the same commits and stage, dispatched right after ours, is never taken.
setup lanes 0 "$strong"
touch "$tmp/lanes/twin"
drive lanes "$sha" "$sha" 0 5
check "two lanes, one commit pair: H1 exits 0" [ "$(rc lanes)" = 0 ]
check "the name is dispatched" grep -q -- "-f name=lanes" "$tmp/lanes/dispatches"
check "it took its own run 501 (titled with its name), not the other lane's 502" grep -q "stage 0: run 501 dispatched" "$tmp/lanes/out"
check "the ledger records stage 0 as run 501" [ "$(ledger lanes runs lanes)" = "0 501 $sha $sha" ]
# A ref whose sprt.yml predates the input: no name sent, the title as before (a driver from before the change
# finds its runs the same way).
setup noname 0 "$strong"
touch "$tmp/noname/noname"
drive noname "$sha" "$sha" 0 5
check "an older sprt.yml: no name sent, H1 exits 0" bash -c "[ \$(cat '$tmp/noname/rc') = 0 ] && ! grep -q -- 'name=' '$tmp/noname/dispatches'"
check "an older sprt.yml: the title without the name" grep -qx "501 sprt $sha $sha stage 0" "$tmp/noname/titles"
# Without names, two lanes' runs look alike: the driver stops rather than guess (the hazard the name removes).
setup twins 0 "$strong"
touch "$tmp/twins/noname" "$tmp/twins/twin"
drive twins "$sha" "$sha" 0 5
check "an older sprt.yml and a twin run: stopped, not adopted" bash -c "[ \$(cat '$tmp/twins/rc') = 1 ] && grep -q 'more than one new run titled' '$tmp/twins/out'"

# The pressure-matched Hash (owner's rule, 2026-11-11: TT-policy tests run with a Hash matching TCEC's nodes per
# move over TT entries): --hash MB sets both engines' Hash for every kind and is part of the declared design;
# without it nothing changes.
check "without --hash the STC default is unchanged: Hash 16" grep -q -- "-f hash=16 -f games=1600" "$tmp/r-h1/dispatches"
check "without --hash the header does not name a Hash" bash -c "! grep -q -- '(--hash)' '$tmp/r-h1/out'"
setup r-hash 0 "$strong"
drive r-hash --kind search --idea h1 --hash 5 "$sha" "$sha"
check "--hash 5: H1 exits 0 after one dispatch" [ "$(rc r-hash):$(dispatches r-hash)" = 0:1 ]
check "--hash 5: dispatched as both engines' Hash" grep -q -- "-f hash=5 -f games=1600" "$tmp/r-hash/dispatches"
check "--hash 5: recorded in design.json" grep -q '"hash": "5"' "$tmp/r-hash/data/r-hash/design.json"
check "--hash 5: named in the header" grep -q "ref test, hash 5 MB (--hash), kind search, stc" "$tmp/r-hash/out"
drive r-hash --kind search --idea h1 --hash 6 "$sha" "$sha"
check "a restart with another --hash is refused before any dispatch" eval '[ "$(rc r-hash)" = 1 ] && [ "$(dispatches r-hash)" = 1 ] && grep -qF -- "hash '\''6'\'' differs from the declared design'\''s '\''5'\''" "$tmp/r-hash/out"'
drive r-hash --kind search --idea h1 "$sha" "$sha"
check "a restart without --hash (the default 16) is refused too" eval '[ "$(rc r-hash)" = 1 ] && [ "$(dispatches r-hash)" = 1 ] && grep -qF -- "hash '\''16'\'' differs from the declared design'\''s '\''5'\''" "$tmp/r-hash/out"'
setup r-hash-ltc 0 "$strong"
TC=40+0.4 drive r-hash-ltc --kind search --idea h2 --cap 4 --hash 22 "$sha" "$sha"
check "LTC --hash 22: 1,664 games at Hash 22" eval '[ "$(rc r-hash-ltc)" = 0 ] && grep -q -- "tc=40+0.4 -f hash=22 -f games=1664" "$tmp/r-hash-ltc/dispatches" && grep -q "\"hash\": \"22\"" "$tmp/r-hash-ltc/data/r-hash-ltc/design.json"'
setup r-hash-custom 0 "$strong"
drive r-hash-custom --hash 9 "$sha" "$sha" 0 5
check "custom kind --hash 9: dispatched as the Hash" eval '[ "$(rc r-hash-custom)" = 0 ] && grep -q -- "-f hash=9 -f games=1600" "$tmp/r-hash-custom/dispatches"'
setup r-hash-env 0 "$strong"
HASH=8 drive r-hash-env --kind search --idea h3 --hash 7 "$sha" "$sha"
check "--hash 7 with HASH=8 is refused before any dispatch" eval '[ "$(rc r-hash-env)" = 1 ] && [ "$(dispatches r-hash-env)" = 0 ] && grep -qF -- "--hash 7 and HASH=8 differ" "$tmp/r-hash-env/out"'
HASH=7 drive r-hash-env --kind search --idea h3 --hash 7 "$sha" "$sha"
check "--hash 7 with HASH=7 runs at Hash 7" eval '[ "$(rc r-hash-env)" = 0 ] && grep -q -- "-f hash=7 -f games" "$tmp/r-hash-env/dispatches"'
setup r-hash-bad 0 "$strong"
for v in 0 08 12x -4 4194305 ''; do
  drive r-hash-bad --kind search --idea h4 --hash "$v" "$sha" "$sha"
  check "--hash '$v' is refused before any dispatch" eval '[ "$(rc r-hash-bad)" = 1 ] && [ "$(dispatches r-hash-bad)" = 0 ] && grep -qF -- "is not a whole number of MB from 1 to 4194304" "$tmp/r-hash-bad/out"'
done
drive r-hash-bad --kind search --idea h4 "$sha" "$sha" --hash
check "--hash with no value is refused" eval '[ "$(rc r-hash-bad)" = 1 ] && [ "$(dispatches r-hash-bad)" = 0 ] && grep -qF -- "--hash needs a value" "$tmp/r-hash-bad/out"'

# CalibratedScore (owner, 2026-11-13): sprt.yml and its tools come from REF, the engines from BASE and TEST. REF at
# c7a61ea's parent has no tools/check_score_display_off.py, so it would play c7a61ea's engine (which has the option,
# default on) with the option on: refused before any dispatch. With both engines from before c7a61ea it is allowed.
# The option was removed the same day (owner, about 7:10 PM EST), so HEAD's engine no longer has it: the engine with
# the option is c7a61ea itself, not HEAD. Needs c7a61ea in this clone (a shallow clone skips these checks).
adopted=c7a61ea987595b7de3b105098b27e7360a73763f
pre=$(git -C "$here" rev-parse --verify --quiet $adopted^)
if [ -n "$pre" ]; then
  setup oldref 0 "$strong"
  echo "$pre" >"$tmp/oldref/ref.test"
  echo "$adopted" >>"$tmp/oldref/commits"
  drive oldref "$adopted" "$adopted" 0 5
  check "a REF older than CalibratedScore with an engine that has it: refused before any dispatch" eval     '[ "$(rc oldref)" = 1 ] && [ "$(dispatches oldref)" = 0 ] && grep -q "REF test ($pre): score_display_guard: refused" "$tmp/oldref/out"'
  setup oldboth 0 "$strong"
  echo "$pre" >"$tmp/oldboth/ref.test"
  echo "$pre" >>"$tmp/oldboth/commits"
  drive oldboth "$pre" "$pre" 0 5
  check "the same REF with both engines older than the option: allowed (H1 after one stage)" eval     '[ "$(rc oldboth)" = 0 ] && [ "$(dispatches oldboth)" = 1 ] && grep -q "no engine has CalibratedScore" "$tmp/oldboth/out"'
  setup oldtest 0 "$strong"
  echo "$pre" >"$tmp/oldtest/ref.test"
  printf '%s
' "$pre" "$adopted" >>"$tmp/oldtest/commits"
  drive oldtest "$pre" "$adopted" 0 5
  check "the same REF with only the test engine having the option: refused" eval '[ "$(rc oldtest)" = 1 ] && [ "$(dispatches oldtest)" = 0 ]'
  setup newref 0 "$strong"
  echo "$adopted" >>"$tmp/newref/commits"
  drive newref "$adopted" "$adopted" 0 5
  check "a REF that forces it off (HEAD) is checked and named in the log" eval     '[ "$(rc newref)" = 0 ] && grep -q "REF test ($sha): score_display_guard: allowed: harness" "$tmp/newref/out"'
else
  echo "SKIP  CalibratedScore REF checks: c7a61ea's parent is not in this clone"
fi

if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed"
  for d in "$tmp"/*/; do [ -f "$d/out" ] && { echo "--- $d"; tail -5 "$d/out"; }; done
  exit 1
fi
echo "all checks passed"
