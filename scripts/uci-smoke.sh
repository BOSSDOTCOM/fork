#!/usr/bin/env bash
# UCI start-up smoke loop: starts the engine RUNS times (default 50), each
# time sending "uci", "isready", "quit", and fails unless every run exits 0
# and prints uciok and readyok.
#
#   scripts/uci-smoke.sh <fork binary> [RUNS]
#
# Why (owner, 2026-10-24): the Windows gcc-debug engine once crashed in about
# half of all starts (MinGW GCC aligned AVX stack moves, CMakeLists.txt), and
# no commit check started a Windows GCC engine in UCI mode. check.sh full runs
# this for every Windows GCC preset. A fault that hits one start in two is
# missed by 50 runs with probability 2^-50.
set -uo pipefail
fork=${1:?usage: scripts/uci-smoke.sh <fork binary> [RUNS]}
runs=${2:-50}
[ -x "$fork" ] || { echo "uci-smoke: $fork is not executable" >&2; exit 2; }
failed=0
for i in $(seq "$runs"); do
  out=$(printf 'uci\nisready\nquit\n' | "$fork" 2>&1)
  status=$?
  if [ $status -ne 0 ] || ! grep -qx 'uciok' <<<"${out//$'\r'/}" || ! grep -qx 'readyok' <<<"${out//$'\r'/}"; then
    failed=$((failed + 1))
    [ $failed -le 3 ] && echo "uci-smoke: run $i of $fork: exit $status, output: $(head -c 300 <<<"$out")" >&2
  fi
done
if [ $failed -ne 0 ]; then
  echo "uci-smoke: $failed of $runs runs failed ($fork)" >&2
  exit 1
fi
echo "uci-smoke: $runs of $runs runs ok ($fork)"
