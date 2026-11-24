#!/usr/bin/env bash
# Waits until WSL has no build (ninja, clang++), no ab_search.py and no
# `fork bench` for 4 checks in a row, 30 s apart (the bracketed patterns do
# not match this script's own command line).
n=0
while [ $n -lt 4 ]; do
  c=$(( $(pgrep -c -x ninja) + $(pgrep -c -f '[a]b_search') + $(pgrep -c -f '[f]ork bench') + $(pgrep -c -f '[c]lang\+\+') ))
  if [ "$c" = 0 ]; then n=$((n + 1)); else n=0; fi
  sleep 30
done
date
uptime
