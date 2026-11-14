#!/usr/bin/env bash
# The overnight GitHub queue (owner, 2026-11-08 night): one job of type github under tools/jobs/jobctl.py, so it
# survives the session. It runs the item scripts in ~/fork-jobs/night/items/ in name order, one step at a time, and
# re-reads the folder after every step, so an item added later (00-* for idea 59's screen) runs at the next stage
# boundary. Item exit codes: 0 done, 10 one step done (a stage boundary; more to do), 20 not ready (skipped for
# now), anything else a failure: the item waits 30 minutes and is retried, and after 3 failures it is skipped.
# Every event goes to ~/fork-jobs/night/chain.log and to the night log section of ~/fork/MORNING.md.
N=/c/Users/user/fork-jobs/night
I=$N/items-b
M=/c/Users/user/fork/MORNING.md
mkdir -p "$N/state"
say() {
  local line
  line="lane B: $(TZ=EST5 date '+%Y-%m-%d %I:%M %p EST') $*"
  echo "$line"
  echo "- $line" >>"$M"
}
say "night chain lane B started (pid $$)"
while :; do
  ran=0
  for item in $(ls "$I" 2>/dev/null | grep -E '\.sh$' | sort); do
    key=${item%.sh}
    [ -f "$N/state/$key.done" ] && continue
    [ -f "$N/state/$key.skipped" ] && continue
    if [ -f "$N/state/$key.retry_at" ] && [ "$(date +%s)" -lt "$(cat "$N/state/$key.retry_at")" ]; then continue; fi
    bash "$I/$item" >>"$N/$key.log" 2>&1
    rc=$?
    case $rc in
      0) touch "$N/state/$key.done"; say "$key: done"; ran=1 ;;
      10) ran=1 ;;
      20) continue ;;
      *)
        n=$(( $(cat "$N/state/$key.failures" 2>/dev/null || echo 0) + 1 ))
        echo "$n" >"$N/state/$key.failures"
        if [ "$n" -ge 3 ]; then
          touch "$N/state/$key.skipped"; say "$key: failed (exit $rc) for the 3rd time: skipped; see $N/$key.log"
        else
          echo $(( $(date +%s) + 1800 )) >"$N/state/$key.retry_at"
          say "$key: failed (exit $rc), attempt $n of 3: retry in 30 minutes; see $N/$key.log"
        fi
        ran=1 ;;
    esac
    break  # re-read the folder after every step: a new 00-* item goes first
  done
  [ "$ran" = 1 ] || sleep 300
done
