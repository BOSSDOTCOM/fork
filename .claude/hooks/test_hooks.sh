#!/usr/bin/env bash
# Self-test for the enforcement hooks: feeds them the JSON Claude Code sends
# and checks the exit status. Run on a clean tree: scripts must pass there and
# fail on the breakages that test_hooks.sh introduces and then reverts.
#   bash .claude/hooks/test_hooks.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
root=$(pwd -W 2>/dev/null || pwd)
export CLAUDE_PROJECT_DIR=$root

edit_json() {  # path relative to root -> PostToolUse JSON (Windows-style absolute path)
  python -I -c 'import json,sys,os; print(json.dumps({"tool_name":"Edit","tool_input":{"file_path":os.path.join(sys.argv[1],sys.argv[2]).replace("/","\\")}}))' "$root" "$1"
}
expect() {  # description, expected exit, command...
  local what=$1 want=$2
  shift 2
  "$@" >/tmp/hooktest.out 2>&1
  local got=$?
  if [ "$got" = "$want" ]; then
    echo "PASS  $what (exit $got)"
  else
    echo "FAIL  $what (exit $got, expected $want)"
    tail -5 /tmp/hooktest.out
    failures=$((failures + 1))
  fi
}
failures=0
after_edit() { edit_json "$1" | bash .claude/hooks/after-edit.sh; }
stop_check() { echo '{"stop_hook_active":false}' | bash .claude/hooks/stop-check.sh; }

expect "after-edit: unreadable input is reported" 2 bash -c 'echo "{not json" | bash .claude/hooks/after-edit.sh'
expect "after-edit: docs edit is ignored" 0 after_edit docs/DESIGN.md
expect "after-edit: clean src edit passes" 0 after_edit src/core/perft.cpp
expect "stop: clean tree passes" 0 stop_check

echo "${failures} failure(s)"
exit $((failures > 0))
