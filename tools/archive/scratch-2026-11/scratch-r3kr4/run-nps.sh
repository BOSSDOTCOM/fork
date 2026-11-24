#!/usr/bin/env bash
# Bake-off round 3 option (a): the nps check (WSL), at the first idle moment:
# A/A, then A (phase-4 37b5d30, r8brft1) against B (nets/r3-kr4, r8brft1kr4,
# architecture 9; bench identical), then A/A again; 20 interleaved rounds each,
# core 4, through bench/ab_search.py's Side (scratch wrapper ab_search_paired.py).
WIN_HOME=${WIN_HOME:?set WIN_HOME to the Windows home folder as WSL sees it, /mnt/c/Users/<user>}  # archive: was a literal path
S=$WIN_HOME/fork-runners/scratch-r3kr4
N=$S/nps
B_COMMIT=${1:?B commit}
n=0
while [ $n -lt 3 ]; do
  c=$(( $(pgrep -c -x ninja) + $(pgrep -c -f '[a]b_search') + $(pgrep -c -f '[f]ork bench') + $(pgrep -c -f '[c]lang\+\+') ))
  if [ "$c" = 0 ]; then n=$((n + 1)); else n=0; fi
  sleep 15
done
cp "$N/A/build/fork" "$N/A-copy-fork"
run() { echo "== $1 $(date) load $(cut -d' ' -f1-3 /proc/loadavg)"; shift; python3 -I "$S/ab_search_paired.py" "$N/A" "$@"; }
run "A/A start" "$N/A/build/fork" "$N/A-copy-fork" 37b5d30 37b5d30 20 4 --allow-identical
run "A/B" "$N/A/build/fork" "$N/B/build/fork" 37b5d30 "$B_COMMIT" 20 4
run "A/A end" "$N/A/build/fork" "$N/A-copy-fork" 37b5d30 37b5d30 20 4 --allow-identical
echo "done $(date) load $(cut -d' ' -f1-3 /proc/loadavg)"
