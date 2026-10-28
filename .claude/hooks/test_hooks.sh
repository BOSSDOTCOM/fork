#!/usr/bin/env bash
# Self-test for the enforcement hooks: feeds them the JSON Claude Code sends
# and checks the exit status. Run on a clean tree: scripts must pass there and
# fail on the breakages that test_hooks.sh introduces and then reverts.
#   bash .claude/hooks/test_hooks.sh             every case (builds clang-release)
#   bash .claude/hooks/test_hooks.sh --no-build  only the cases that build nothing
# The failure paths run the hooks against a throwaway project folder whose
# scripts/check.sh is a stand-in that fails, warns or hangs.
set -uo pipefail
cd "$(dirname "$0")/../.."
root=$(pwd -W 2>/dev/null || pwd)
hooks=$(pwd)/.claude/hooks
export CLAUDE_PROJECT_DIR=$root
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

edit_json() {  # project root, path relative to it -> PostToolUse JSON (Windows-style absolute path)
  python -I -c 'import json,sys,os; print(json.dumps({"tool_name":"Edit","tool_input":{"file_path":os.path.join(sys.argv[1],sys.argv[2]).replace("/","\\")}}))' "$1" "$2"
}
expect() {  # description, expected exit, command...
  local what=$1 want=$2
  shift 2
  "$@" >"$tmp/out" 2>&1
  local got=$?
  if [ "$got" = "$want" ]; then
    echo "PASS  $what (exit $got)"
  else
    echo "FAIL  $what (exit $got, expected $want)"
    tail -5 "$tmp/out"
    failures=$((failures + 1))
  fi
}
says() {  # description, pattern: the last case's output must match
  if grep -qE -- "$2" "$tmp/out"; then echo "PASS  $1"; else echo "FAIL  $1"; tail -5 "$tmp/out"; failures=$((failures + 1)); fi
}
failures=0
after_edit() { edit_json "$root" "$1" | bash "$hooks/after-edit.sh"; }
stop_check() { echo '{"stop_hook_active":false}' | bash "$hooks/stop-check.sh"; }

expect "after-edit: unreadable input is reported" 2 bash -c 'echo "{not json" | bash .claude/hooks/after-edit.sh'
expect "after-edit: docs edit is ignored" 0 after_edit docs/DESIGN.md

# Failure paths (audit-1 U-12, U-15, S-3): a stand-in project whose check
# fails, passes with the lock-skip warning, or outlives the hook's limit.
fake=$tmp/project
mkdir -p "$fake/scripts" "$fake/src"
: >"$fake/scripts/env.sh"
echo x >"$fake/src/x.txt"
fakeroot=$(cd "$fake" && (pwd -W 2>/dev/null || pwd))
stand_in() {  # body of the stand-in scripts/check.sh
  printf '#!/usr/bin/env bash\n%s\n' "$1" >"$fake/scripts/check.sh"
  chmod +x "$fake/scripts/check.sh"
}
fake_edit() { edit_json "$fakeroot" src/x.txt | CLAUDE_PROJECT_DIR=$fakeroot bash "$hooks/after-edit.sh"; }
fake_stop() { echo '{"stop_hook_active":false}' | CLAUDE_PROJECT_DIR=$fakeroot bash "$hooks/stop-check.sh"; }

stand_in 'echo "FORK CHECK FAILED ($1): tests clang-release" >&2; exit 1'
expect "stop: a failing check blocks" 2 fake_stop
says "stop: the failure is shown" 'FORK CHECK FAILED \(stop\)'
expect "after-edit: a failing check is reported" 2 fake_edit
says "after-edit: the failure is shown" 'FORK CHECK FAILED \(quick\)'

stand_in 'echo "fork check $1: skipped, another check (PID 1) still running after 600 s; no pass recorded" >&2; exit 0'
expect "stop: a skipped check passes" 0 fake_stop
says "stop: ...with the warning as a systemMessage" '^\{"systemMessage": "Stop hook .*skipped, another check'
expect "after-edit: a skipped check passes" 0 fake_edit
says "after-edit: ...with the warning for the user and for Claude" '"systemMessage": .*"additionalContext": "after-edit hook .*skipped, another check'

stand_in 'sleep 30'
expect "stop: a check past the hook's limit blocks" 2 env FORK_HOOK_TIMEOUT=2 bash -c 'echo "{}" | CLAUDE_PROJECT_DIR='"'$fakeroot'"' bash "'"$hooks"'/stop-check.sh"'
says "stop: ...and says so" 'did not finish within 2 s'
expect "after-edit: a check past the hook's limit is reported" 2 env FORK_HOOK_TIMEOUT=2 bash -c "$(declare -f edit_json fake_edit); hooks='$hooks' fakeroot='$fakeroot' fake_edit"
says "after-edit: ...and says so" 'did not finish within 2 s'

stand_in 'echo "fork check $1: ok"'
expect "stop: a clean check is silent" 0 fake_stop
if [ -s "$tmp/out" ]; then echo "FAIL  stop: ...no output"; failures=$((failures + 1)); else echo "PASS  stop: ...no output"; fi

if [ "${1:-}" != --no-build ]; then
  expect "after-edit: clean src edit passes" 0 after_edit src/core/perft.cpp
  expect "stop: clean tree passes" 0 stop_check
fi

echo "${failures} failure(s)"
exit $((failures > 0))
