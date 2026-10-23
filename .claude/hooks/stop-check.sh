#!/usr/bin/env bash
# Stop hook: before Claude finishes, run the full check (clang-release,
# clang-debug with sanitizers, gcc-release; every non-slow test including
# bench parity). It is instant when no code changed since the last pass.
# On failure, exit 2 blocks completion and feeds the failure back to Claude.
# Claude Code caps consecutive blocks, so an unfixable failure cannot loop
# forever; it must then be reported to the owner.
set -uo pipefail
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$root"
cat >/dev/null  # hook input (stop_hook_active etc.) is not needed

if ! out=$(scripts/check.sh full 2>&1); then
  echo "$out" | tail -n 60 >&2
  echo "stop hook: the full check failed (scripts/check.sh full). Fix it, or if it cannot be fixed now, tell the owner exactly what fails." >&2
  exit 2
fi
exit 0
