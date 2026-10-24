#!/usr/bin/env bash
# Stop hook: before Claude finishes, run the fast check (scripts/check.sh
# stop): clang-release build, every non-slow test, bench parity and no_alloc,
# on this platform only. It is skipped, instantly, when no source, test or
# build file changed since the last passing stop or full check (content
# hash), so docs-only work and long background jobs (MSan, perft, fuzzing)
# never trigger a rebuild. The Linux leg stays in `check.sh full` (pre-commit
# hook, sign-offs).
# On failure, exit 2 blocks completion and feeds the failure back to Claude.
# Claude Code caps consecutive blocks, so an unfixable failure cannot loop
# forever; it must then be reported to the owner.
set -uo pipefail
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$root"
cat >/dev/null  # hook input (stop_hook_active etc.) is not needed

if ! out=$(scripts/check.sh stop 2>&1); then
  echo "$out" | tail -n 60 >&2
  echo "stop hook: the check failed (scripts/check.sh stop). Fix it, or if it cannot be fixed now, tell the owner exactly what fails." >&2
  exit 2
fi
exit 0
