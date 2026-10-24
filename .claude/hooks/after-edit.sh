#!/usr/bin/env bash
# PostToolUse hook (Edit|Write): after any edit to src/ or tests/, format the
# file with clang-format, then run the quick check (clang-release build +
# fast tests). Exit 2 reports a failure to Claude (the edit itself stands).
set -uo pipefail
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$root"

input=$(cat)
if ! path=$(printf '%s' "$input" | python -I -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))'); then
  # Never pass silently on input we cannot read.
  echo "after-edit hook: could not parse hook input; checks were NOT run. Run scripts/check.sh quick manually." >&2
  exit 2
fi
[ -n "$path" ] || exit 0
command -v cygpath >/dev/null && path=$(cygpath -u "$path")
rootu=$root
command -v cygpath >/dev/null && rootu=$(cygpath -u "$root")
rel=${path#"$rootu"/}
case "$rel" in
  src/*|tests/*) ;;
  *) exit 0 ;;
esac

. scripts/env.sh
case "$rel" in
  *.cpp|*.hpp) clang-format -i "$rel" ;;
esac

if ! out=$(scripts/check.sh quick 2>&1); then
  echo "$out" | tail -n 40 >&2
  echo "after-edit hook: quick check failed after editing $rel. Fix it before continuing." >&2
  exit 2
fi
exit 0
