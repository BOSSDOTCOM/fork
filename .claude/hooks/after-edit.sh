#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# PostToolUse hook (Edit|Write): after any edit to src/ or tests/, format the
# file with clang-format, then run the quick check (clang-release build +
# fast tests). Exit 2 reports a failure to Claude (the edit itself stands).
# Never silent (audit-1 U-12, S-3): the check runs under `timeout`
# (FORK_HOOK_TIMEOUT seconds, default 280, inside the 300 s of
# .claude/settings.json; at its own timeout Claude Code would discard the
# hook's output), and a timeout is reported like a failure; a check that
# passed with a warning (skipped because another check held the lock, a
# WARNING, skipped or retried test cases) exits 0 with JSON that shows the
# warning to the user (systemMessage) and to Claude (additionalContext).
set -uo pipefail
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$root"
limit=${FORK_HOOK_TIMEOUT:-280}

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

out=$(timeout "$limit" scripts/check.sh quick 2>&1)
status=$?
if [ $status = 124 ]; then
  echo "$out" | tail -n 20 >&2
  echo "after-edit hook: scripts/check.sh quick did not finish within $limit s after editing $rel; the edit is NOT checked. Run it by hand." >&2
  exit 2
fi
if [ $status != 0 ]; then
  echo "$out" | tail -n 40 >&2
  echo "after-edit hook: quick check failed after editing $rel. Fix it before continuing." >&2
  exit 2
fi
warn=$(echo "$out" | grep -E 'skipped, another check|WARNING|\): (SKIP|NOTE) ' | head -n 20)
if [ -n "$warn" ]; then
  python -I -c 'import json, sys
msg = "after-edit hook (scripts/check.sh quick, after editing " + sys.argv[2] + ") passed with warnings:\n" + sys.argv[1]
print(json.dumps({"systemMessage": msg,
                  "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))' "$warn" "$rel" ||
    { echo "after-edit hook: warnings after editing $rel: $warn" >&2; exit 2; }
fi
exit 0
