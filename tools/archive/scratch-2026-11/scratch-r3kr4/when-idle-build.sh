#!/usr/bin/env bash
# Waits for WSL to be free of builds and speed measurements for 3 checks in a
# row, 15 s apart, then runs this folder's nps builds (run-nps-build.sh).
WIN_HOME=${WIN_HOME:?set WIN_HOME to the Windows home folder as WSL sees it, /mnt/c/Users/<user>}  # archive: was a literal path
S=$WIN_HOME/fork-runners/scratch-r3kr4
n=0
while [ $n -lt 3 ]; do
  c=$(( $(pgrep -c -x ninja) + $(pgrep -c -f '[a]b_search') + $(pgrep -c -f '[f]ork bench') + $(pgrep -c -f '[c]lang\+\+') ))
  if [ "$c" = 0 ]; then n=$((n + 1)); else n=0; fi
  sleep 15
done
echo "idle at $(date)"
bash "$S/run-nps-build.sh" "$1"
echo "built at $(date)"
