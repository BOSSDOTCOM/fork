#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# CI: tests .github/ci/changed-areas.sh, which decides which of ci.yml's
# jobs run. Builds a throwaway git repository with one commit per case
# (documentation only, typical code, a TSan path, a threaded new file,
# move generation, renames and deletions, a pull request's merge ref, the
# unlistable cases, manual runs) and checks the code/tsan/movegen answers.
# Run by ci.yml's `changes` job before the classification; locally:
#
#   bash .github/ci/changed-areas-test.sh [path/to/changed-areas.sh]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
script=$(cd "$(dirname "${1:-$here/changed-areas.sh}")" && pwd)/$(basename "${1:-changed-areas.sh}")
[ -f "$script" ] || { echo "no script at $script" >&2; exit 2; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
repo=$tmp/repo
mkdir -p "$repo"
cd "$repo"
git init -q -b main .
git config user.name ci
git config user.email ci@invalid
git config core.hooksPath /dev/null
git config core.autocrlf false
failures=0 cases=0

# commit_paths MESSAGE PATH=CONTENT... (an empty CONTENT deletes PATH);
# prints the new commit.
commit_paths() {
  local msg=$1; shift
  local spec path content
  for spec in "$@"; do
    path=${spec%%=*} content=${spec#*=}
    if [ -z "$content" ]; then git rm -q "$path"; else
      mkdir -p "$(dirname "$path")"; printf '%s\n' "$content" > "$path"; git add "$path"
    fi
  done
  git commit -q --allow-empty -m "$msg"
  git rev-parse HEAD
}

# run_case NAME EXPECTED ENV...: EXPECTED is "code tsan movegen", e.g.
# "true false false"; ENV are VAR=value pairs for the script.
run_case() {
  local name=$1 want=$2; shift 2
  local out got
  cases=$((cases + 1))
  out=$tmp/out
  : > "$out"
  if ! env -i PATH="$PATH" HOME="$HOME" GITHUB_OUTPUT="$out" "$@" bash "$script" > "$tmp/log" 2>&1; then
    echo "FAIL $name: the script failed"; sed 's/^/  /' "$tmp/log"; failures=$((failures + 1)); return
  fi
  got="$(sed -n 's/^code=//p' "$out") $(sed -n 's/^tsan=//p' "$out") $(sed -n 's/^movegen=//p' "$out")"
  if [ "$got" = "$want" ]; then echo "ok   $name ($got)"; else
    echo "FAIL $name: got '$got', expected '$want' (code tsan movegen)"; sed 's/^/  /' "$tmp/log"
    failures=$((failures + 1))
  fi
}

# A small tree shaped like Fork's.
base=$(commit_paths "base" \
  "README.md=Fork" "docs/DESIGN.md=design" "LICENSE=GPL" \
  "CMakeLists.txt=project(fork)" "src/core/movegen.cpp=// moves" \
  "src/eval/eval.cpp=// eval" "src/eval/old.cpp=// old" \
  "src/search/searcher.cpp=std::atomic<bool>* stop_;" "src/search/trans_table.cpp=// tt" \
  "src/uci/session.cpp=std::thread search_thread_;" "tests/test_search.cpp=std::atomic<bool> stop{false};" \
  "tools/datagen/run.py=# tool")

c=$(commit_paths "docs" "docs/DESIGN.md=design 2" "README.md=Fork 2" "docs/x/notes.md=n" "LICENSE=GPL 2")
run_case "documentation only" "false false false" EVENT=push BEFORE="$base"
p=$c; c=$(commit_paths "eval" "src/eval/eval.cpp=// eval 2")
run_case "typical code (src/eval)" "true false false" EVENT=push BEFORE="$p"
p=$c; c=$(commit_paths "tool" "tools/datagen/run.py=# tool 2")
run_case "a tool, not built" "true false false" EVENT=push BEFORE="$p"
p=$c; c=$(commit_paths "docs and code" "docs/DESIGN.md=design 3" "src/eval/eval.cpp=// eval 3")
run_case "documentation and code" "true false false" EVENT=push BEFORE="$p"
p=$c; c=$(commit_paths "searcher" "src/search/searcher.cpp=std::atomic<bool>* stop_; // 2")
run_case "searcher.* (atomics, exempt)" "true false false" EVENT=push BEFORE="$p"
p=$c; c=$(commit_paths "tt" "src/search/trans_table.cpp=// tt 2")
run_case "TSan path: the TT" "true true false" EVENT=push BEFORE="$p"
p=$c; c=$(commit_paths "uci" "src/uci/session.cpp=std::thread search_thread_; // 2")
run_case "TSan path: the UCI layer" "true true false" EVENT=push BEFORE="$p"
p=$c; c=$(commit_paths "smp" "src/search/smp.cpp=#include <thread>")
run_case "a new threaded source file" "true true false" EVENT=push BEFORE="$p"
p=$c; c=$(commit_paths "eval mutex" "src/eval/eval.cpp=std::mutex m;")
run_case "a threading token outside the list" "true true false" EVENT=push BEFORE="$p"
p=$c; c=$(commit_paths "test" "tests/test_search.cpp=std::atomic<bool> stop{true};")
run_case "a test with a local stop flag" "true false false" EVENT=push BEFORE="$p"
p=$c; c=$(commit_paths "movegen" "src/core/movegen.cpp=// moves 2")
run_case "move generation" "true false true" EVENT=push BEFORE="$p"
p=$c; c=$(commit_paths "cmake" "CMakeLists.txt=project(fork) # 2")
run_case "the build definition" "true true true" EVENT=push BEFORE="$p"
p=$c; c=$(commit_paths "ci" ".github/workflows/ci.yml=on: push")
run_case "the CI workflow" "true true false" EVENT=push BEFORE="$p"
p=$c; git mv src/uci/session.cpp docs/session.md; git commit -q -m rename; c=$(git rev-parse HEAD)
run_case "a rename out of src/uci into docs" "true true false" EVENT=push BEFORE="$p"
p=$c; c=$(commit_paths "delete" "src/eval/old.cpp=")
run_case "a deleted source file" "true false false" EVENT=push BEFORE="$p"
run_case "no change" "true false false" EVENT=push BEFORE="$c"
run_case "push of a new branch" "true true true" EVENT=push BEFORE=0000000000000000000000000000000000000000
run_case "push after a rewrite (before unknown)" "true true true" EVENT=push BEFORE=1234567890abcdef1234567890abcdef12345678
run_case "push without before" "true true true" EVENT=push

# A pull request: the base gains code, the branch only documentation; the
# merge ref's HEAD^1..HEAD is the branch's net change.
fork_point=$c
git checkout -q -b topic
head=$(commit_paths "pr docs" "docs/DESIGN.md=design pr")
git checkout -q main
base_tip=$(commit_paths "main code" "src/uci/session.cpp=std::thread t;")
git merge -q --no-ff --no-edit topic
run_case "pull request, documentation only" "false false false" \
  EVENT=pull_request HEAD_SHA="$head" BASE_SHA="$fork_point"
run_case "pull request, not the merge ref: base used" "true true false" \
  EVENT=pull_request HEAD_SHA=0000000000000000000000000000000000000001 BASE_SHA="$fork_point"
run_case "pull request, nothing listable" "true true true" EVENT=pull_request HEAD_SHA=0000000000000000000000000000000000000001
run_case "pull request, base not in the clone" "true true true" \
  EVENT=pull_request BASE_SHA=1234567890abcdef1234567890abcdef12345678

# Manual runs.
run_case "manual run" "true false true" EVENT=workflow_dispatch
run_case "manual run, force-tsan" "true true true" EVENT=workflow_dispatch FORCE_TSAN=true
run_case "manual run, diff-base (documentation only)" "false false false" EVENT=workflow_dispatch DIFF_BASE="$base_tip"
run_case "manual run, diff-base, force-tsan" "false true false" EVENT=workflow_dispatch DIFF_BASE="$base_tip" FORCE_TSAN=true
run_case "manual run, diff-base (code)" "true true false" EVENT=workflow_dispatch DIFF_BASE="$fork_point"
run_case "manual run, unknown diff-base" "true true true" EVENT=workflow_dispatch DIFF_BASE=no-such-ref

echo "$cases cases, $failures failures"
[ "$failures" -eq 0 ]
