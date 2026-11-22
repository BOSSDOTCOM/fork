#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# The 30-minute sweep (Git Bash on the Windows host): one screen of every job, lane, GitHub run, the cloud VM,
# Kaggle and RAM. Started 2026-11-10 as an untracked script under ~/fork-jobs/night/; committed here on the
# owner's order of 2026-11-22.
#
# It acts in two ways only:
#   - ~/fork-jobs/night/stale.py --kill, which ends assured-stale processes only (owner, 2026-11-11);
#   - tools/gcp/gcp.py sweep, which restarts the VM only while ~/fork-jobs/gcp/wanted.json says "running"
#     (a preemption). The untracked copy also restarted a stopped VM through gcloud whatever wanted.json said,
#     which would undo `gcp.py stop`; that restart is gone (owner, 2026-11-22: never restart a VM that is
#     wanted stopped). tools/jobs/test_sweep.py checks both.
#
#   bash tools/jobs/sweep.sh
set -u
H=$(cygpath -m "$HOME")                     # Windows form, for the Windows programs below
F="$H/fork"
PY="$F/.venv/Scripts/python.exe"
N="$HOME/fork-jobs/night"; J="$HOME/fork-jobs/jobs"; SP="$HOME/fork-data/sprt"   # Git Bash forms (find, stat, ls)
export PATH="$PATH:$HOME/AppData/Local/Microsoft/WinGet/Links"
age() { echo $(( ($(date +%s) - $(stat -c %Y "$1" 2>/dev/null || echo 0)) / 60 ))m; }
pending() {  # LANE_FOLDER: every item without a .done marker, SKIPPED ones marked
  local k f
  for f in "$1"/*.sh; do
    [ -e "$f" ] || continue
    k=$(basename "$f" .sh)
    [ -f "$N/state/$k.done" ] && continue
    printf '%s %s%s | ' "$([ -f "$N/state/$k.skipped" ] && echo SKIPPED || echo P)" "$k" \
      "$([ -f "$N/state/$k.failures" ] && echo " failures=$(cat "$N/state/$k.failures")")"
  done
  echo
}

echo "== $(TZ=EST5 date '+%I:%M %p EST')  free RAM $(powershell.exe -NoProfile -Command '[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,2)' | tr -d '\r') GB, C: free $(df -B1 /c | awk 'NR==2{printf "%.1f", $4/1e9}') GB"
echo "== jobctl (live)"; "$PY" -I "$F/tools/jobs/jobctl.py" status 2>&1 | grep -vE "ended|stopped" | cut -c1-140
echo "== jobs ended in the last 2 h"
for f in $(find "$J" -name '*.json' -mmin -120 2>/dev/null); do
  "$PY" -I -c "import json,sys;d=json.load(open(sys.argv[1]));print(' ',d.get('name'),d.get('state'),d.get('exit_code'))" "$(cygpath -m "$f")" 2>/dev/null
done | grep -v running
echo "== lane A pending"; pending "$N/items"
echo "   lane A log: $(tail -1 "$J/night-queue.log" 2>/dev/null | cut -c1-110) (log age $(age "$J/night-queue.log"))"
echo "== lane B pending"; pending "$N/items-b"
echo "   lane B log: $(tail -1 "$J/night-queue-b.log" 2>/dev/null | cut -c1-110) (log age $(age "$J/night-queue-b.log"))"
echo "   gates: $(ls "$N/state" 2>/dev/null | grep -E '^gate-' | tr '\n' ' ')"
echo "== SPRT/h2h drivers active in the last 3 h"
for d in $(find "$SP" -maxdepth 2 -name driver.log -mmin -180 2>/dev/null); do
  n=$(basename "$(dirname "$d")")
  echo "  $n [$(age "$d")]: $(grep -E '^ *Elo:' "$d" | tail -1 | sed 's/^ *//' | cut -c1-40) | $(grep -E 'dispatched|merged|decided|undecided|accepted|STOP' "$d" | tail -1 | cut -c1-90)"
done
echo "== GitHub runs in progress or queued"
gh run list -R BOSSDOTCOM/fork --limit 30 --json databaseId,workflowName,status,createdAt,displayTitle \
  --jq '.[]|select(.status!="completed")|"  \(.databaseId) \(.workflowName) \(.status) \(.createdAt) \(.displayTitle[0:60])"' 2>&1 | head -12
echo "== memwatch: $(tail -1 "$J/memwatch3.log" 2>/dev/null | cut -c1-140)"
echo "== state/ready files changed in the last 2 h"
find "$N/state" -maxdepth 1 -type f -mmin -120 -printf '  %f\n' 2>/dev/null | head -15
echo "== stale processes (assured-stale kills only; see stale.py)"
if [ -f "$N/stale.py" ]; then
  "$PY" -I "$H/fork-jobs/night/stale.py" --kill 2>&1 | sed 's/^/  /'
else
  echo "  stale.py not found: not checked"
fi
echo "== GCP (gcp.py sweep: restarts the VM only while wanted.json says running)"
"$PY" -I "$F/tools/gcp/gcp.py" sweep 2>&1 | sed 's/^/  /' | head -16; echo "  gcp sweep exit ${PIPESTATUS[0]}"
echo "== Kaggle"; "$F/.venv/Scripts/kaggle.exe" kernels list --mine --sort-by dateRun --page-size 3 2>&1 | tail -3 | cut -c1-140
