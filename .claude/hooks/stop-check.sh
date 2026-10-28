#!/usr/bin/env bash
# Stop hook: before Claude finishes, run the fast check (scripts/check.sh
# stop): clang-release build, every non-slow test, bench parity and no_alloc,
# on this platform only. It is skipped, instantly, when no source, test or
# build file changed since the last passing stop or full check (content
# hash), so docs-only work and long background jobs (MSan, perft, fuzzing)
# never trigger a rebuild. The other presets, Linux, the sanitizers and TCEC's
# compilers run in GitHub CI on every push (and in `check.sh full` on demand).
# On failure, exit 2 blocks completion and feeds the failure back to Claude.
# Claude Code caps consecutive blocks, so an unfixable failure cannot loop
# forever; it must then be reported to the owner.
# Never silent (audit-1 U-12, S-3):
# - a check that did not finish within the hook's limit fails like a broken
#   check (Claude Code cancels a hook at its timeout and discards its
#   output, which would let the session end unchecked), so the check runs
#   under `timeout`, FORK_HOOK_TIMEOUT seconds (default 870, inside the 900
#   s of .claude/settings.json);
# - a check that passed with a warning (skipped because another check held
#   the lock, a WARNING, skipped or retried test cases) exits 0 with the
#   warning as a JSON systemMessage, which Claude Code shows to the user.
set -uo pipefail
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$root"
cat >/dev/null  # hook input (stop_hook_active etc.) is not needed
limit=${FORK_HOOK_TIMEOUT:-870}

out=$(timeout "$limit" scripts/check.sh stop 2>&1)
status=$?
if [ $status = 124 ]; then
  echo "$out" | tail -n 20 >&2
  echo "stop hook: scripts/check.sh stop did not finish within $limit s (the hook's limit); the tree is NOT checked. Run it by hand, or tell the owner." >&2
  exit 2
fi
if [ $status != 0 ]; then
  echo "$out" | tail -n 60 >&2
  echo "stop hook: the check failed (scripts/check.sh stop). Fix it, or if it cannot be fixed now, tell the owner exactly what fails." >&2
  exit 2
fi
warn=$(echo "$out" | grep -E 'skipped, another check|WARNING|\): (SKIP|NOTE) ' | head -n 20)
if [ -n "$warn" ]; then
  python -I -c 'import json, sys; print(json.dumps({"systemMessage": "Stop hook (scripts/check.sh stop) passed with warnings:\n" + sys.argv[1]}))' "$warn" ||
    { echo "stop hook: warnings: $warn" >&2; exit 2; }
fi
exit 0
