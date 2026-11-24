#!/usr/bin/env bash
# Waits for the smoke kernel to end (status every 2 minutes), then downloads its output into this folder's
# smoke-out (created here). Prints one line per status change.
K=~/fork/.venv/Scripts/kaggle.exe
KID=bossdotcom/fork-bakeoff-r3-smoke
OUT=$(cygpath -w ~/fork-runners/scratch-r3kr4/smoke-out)
last=
while true; do
  st=$("$K" kernels status "$KID" 2>&1 | tail -1)
  [ "$st" != "$last" ] && echo "$(date '+%I:%M %p') $st" && last=$st
  echo "$st" | grep -qi 'COMPLETE\|ERROR\|CANCEL' && break
  sleep 120
done
mkdir -p ~/fork-runners/scratch-r3kr4/smoke-out
for i in 1 2 3; do
  timeout 1800 "$K" kernels output "$KID" -p "$OUT" > ~/fork-runners/scratch-r3kr4/work/smoke-output.log 2>&1 && break
  sleep 60
done
echo "output downloaded: $(ls ~/fork-runners/scratch-r3kr4/smoke-out | tr '\n' ' ')"
