#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# The staleness audit's heavy re-runs on the cloud worker (coordinator's order of 2026-11-12): one declared
# quality-per-node measurement again, on the current default net and search, by its own tool and rule.
#
#   vm_rerun.sh COMMIT nomove     tools/no_move_measure.py (NoMoveReduceMinDepth): labels with the reduction
#                                 off, then its sweep and report
#   vm_rerun.sh COMMIT build      the tuning build alone
#   vm_rerun.sh COMMIT probcut    tools/tier2_measure.py with spec capture_probe (ProbCut's three constants):
#                                 labels by the default engine, then the sweep and report
#
# Idempotent and resumable: the tuning build is made once per commit (bench parity checked), the labels save
# every answer as it finishes, and each sweep cell is written whole. Ends with "rerun ok KIND" and the report
# in $W/out/stale-KIND/report.txt.
set -euo pipefail
commit=${1:?usage: vm_rerun.sh COMMIT nomove|probcut}
kind=${2:?usage: vm_rerun.sh COMMIT nomove|probcut}
W=${FORK_WORKER_ROOT:-/opt/fork}
S=$W/work/staleness
T=$S/tools                      # the audit's tools (rsynced from the PC's branch tools/staleness-audit)
PY=$W/venv/bin/python
jobs=${STALE_JOBS:-8}
say() { echo "$(TZ=EST5 date '+%Y-%m-%d %I:%M:%S %p EST') vm_rerun: $*"; }

src=$S/src-${commit:0:12}
bin=$S/build-${commit:0:12}/fork
if [ ! -x "$bin" ] || [ ! -f "$S/build-${commit:0:12}/parity.txt" ]; then
  if [ ! -d "$src/.git" ]; then
    git -C "$W/src" fetch -q origin
    git clone -q --no-checkout "$W/src" "$src"
  fi
  git -C "$src" checkout -q --detach "$commit"
  [ "$(git -C "$src" rev-parse HEAD)" = "$commit" ] || { echo "vm_rerun: checkout is not $commit" >&2; exit 1; }
  # The measurement build only: ProbCut's tuning ranges back to the ones its grid was declared under (d5a6eb6:
  # minimum depth from 2, margin to 640), since set_param clamps to the range and today's (4-18, 40-160) would
  # fold the grid's 3 and its 200-500 margins onto the bounds. Defaults unchanged, so bench parity still holds.
  p=$src/src/tune/params.hpp
  sed -i -e 's/X(CaptureProbeMinDepth, 9, 4, 18, 1) /X(CaptureProbeMinDepth, 9, 2, 18, 1) /' \
    -e 's/X(CaptureProbeMargin, 80, 40, 160, 6) /X(CaptureProbeMargin, 80, 40, 640, 6) /' "$p"
  grep -q 'X(CaptureProbeMinDepth, 9, 2, 18, 1)' "$p" && grep -q 'X(CaptureProbeMargin, 80, 40, 640, 6)' "$p" ||
    { echo "vm_rerun: the range patch did not apply" >&2; exit 1; }
  git -C "$src" diff --stat
  say "tuning build of ${commit:0:12}"
  cmake -S "$src" -B "$S/cmake-${commit:0:12}" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++ \
    -DFORK_TUNE=ON -DFORK_ARCH=x86-64-v3 >"$S/build-${commit:0:12}.log" 2>&1
  cmake --build "$S/cmake-${commit:0:12}" --target fork >>"$S/build-${commit:0:12}.log" 2>&1
  mkdir -p "$(dirname "$bin")"
  cp "$S/cmake-${commit:0:12}/fork" "$bin"
  "$bin" version >"$(dirname "$bin")/version.txt"
  # The tuning build compiles the same defaults, so bench equals the release reference.
  bash "$src/.github/ci/bench-parity.sh" "$bin" >"$(dirname "$bin")/parity.txt"
fi
cat "$(dirname "$bin")/version.txt" "$(dirname "$bin")/parity.txt"
[ "$kind" = build ] && { say "build ok"; exit 0; }

out=$W/out/stale-$kind
mkdir -p "$out"
case $kind in
  nomove)
    labels=$out/labels-iir-off.jsonl
    [ -f "$labels" ] || "$PY" -I -u "$T/tools/staleness/label_with.py" "$bin" "$labels" --jobs "$jobs" \
      --option UseNoMoveReduction=false
    "$PY" -I -u "$T/tools/no_move_measure.py" sweep "$bin" "$labels" "$out/sweep" --jobs "$jobs"
    "$PY" -I -u "$T/tools/no_move_measure.py" report "$labels" "$out/sweep" >"$out/report.txt.part"
    ;;
  probcut)
    labels=$out/labels-default.jsonl
    [ -f "$labels" ] || "$PY" -I -u "$T/tools/staleness/label_with.py" "$bin" "$labels" --jobs "$jobs"
    spec=$T/tools/tier2_measure/capture_probe.json
    "$PY" -I -u "$T/tools/tier2_measure.py" sweep "$spec" "$bin" "$labels" "$out/sweep" --jobs "$jobs"
    "$PY" -I -u "$T/tools/tier2_measure.py" report "$spec" "$labels" "$out/sweep" >"$out/report.txt.part"
    ;;
  *) echo "vm_rerun: unknown kind $kind" >&2; exit 2 ;;
esac
mv "$out/report.txt.part" "$out/report.txt"
cat "$out/report.txt"
echo "{\"kind\": \"$kind\", \"commit\": \"$commit\", \"at\": \"$(TZ=EST5 date '+%Y-%m-%d %I:%M:%S %p EST')\"}" >"$out/done.json"
say "rerun ok $kind"
