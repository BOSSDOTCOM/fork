#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# CI: which areas did this push, pull request or manual run change? One
# listing of the changed files decides which of ci.yml's jobs run (its
# `changes` job; owner, 2026-11-07), printed to $GITHUB_OUTPUT:
#
#   code=true|false     false only when every changed file is documentation
#                       (docs/, any *.md, LICENSE; the same set as ci.yml's
#                       push paths-ignore): every build job is skipped
#   tsan=true|false     a file the full TSan suites bind to changed: threads,
#                       the TT, the UCI layer, the TSan build, this
#                       classification (the full suites run nightly on main
#                       otherwise, .github/workflows/tsan.yml)
#   movegen=true|false  a file move generation's results depend on changed
#                       (perft_epd_full; nightly on main otherwise)
#
# When the changed files cannot be listed (a new branch, a rewritten
# history, a missing base), every answer is true. A manual run
# (workflow_dispatch) without DIFF_BASE runs code and movegen, and TSan only
# when FORCE_TSAN=true (opt-in, owner 2026-11-07).
#
#   EVENT=... BASE_SHA=... HEAD_SHA=... BEFORE=... DIFF_BASE=... FORCE_TSAN=... \
#     .github/ci/changed-areas.sh
#
# Tested by .github/ci/changed-areas-test.sh (run by the same job first).
set -euo pipefail

# Documentation: keep in step with ci.yml's push paths-ignore.
docs_re='^docs/|\.md$|^LICENSE$'
movegen_re='^(src/core/|tests/(test_epd\.cpp|harness\.hpp|main\.cpp)$|CMakeLists\.txt$|CMakePresets\.json$|cmake/)'
# Threads, the TT and the UCI layer by path, plus what builds and runs the
# TSan jobs. tests/main.cpp and tests/harness.hpp run every suite. Not
# listed: uci_oom_test.cpp, uci_hash_oom_test.cpp and alloc_test.cpp (not
# built under TSan), and src/search/searcher.* (owner, 2026-11-07: it only
# reads the stop and ponder flags; the threaded suites job covers it).
tsan_re='^(src/main\.cpp$|src/uci/|src/datagen/|src/search/(trans_table|hash_memory)\.(cpp|hpp)$'
tsan_re+='|tests/(test_uci\.cpp|test_options\.cpp|test_tt\.cpp|test_datagen\.cpp|engine_process\.(cpp|hpp)|uci_message\.hpp|main\.cpp|harness\.hpp)$'
tsan_re+='|CMakeLists\.txt$|CMakePresets\.json$|cmake/'
tsan_re+='|\.github/workflows/(ci|tsan|nightly)\.yml$|\.github/ci/(changed-areas|run-tests)\.sh$)'
# Any other changed source file that uses threads or cross-thread state
# (whole file, as changed): a new file that starts a thread is caught
# without a list update. Test files are not scanned (most hold a local stop
# flag to call the search), nor searcher.* (above).
thread_re='std::(thread|jthread|async|atomic|atomic_ref|mutex|shared_mutex|recursive_mutex|timed_mutex|condition_variable|latch|barrier|counting_semaphore|binary_semaphore|stop_token|stop_source|call_once)\b'
thread_re+='|#include <(thread|atomic|mutex|shared_mutex|condition_variable|future|latch|barrier|semaphore|stop_token)>'
thread_re+='|\bpthread_|\bthread_local\b|memory_order'
source_re='^(src|third_party)/.*\.(cpp|hpp|h|c)$'

emit() { echo "$1=$2"; echo "$1=$2" >> "${GITHUB_OUTPUT:-/dev/null}"; }
everything() {
  echo "Changed files unknown ($1): running everything"
  emit code true; emit tsan "${2:-true}"; emit movegen true
  exit 0
}

zero=0000000000000000000000000000000000000000
from=""
case "${EVENT:-}" in
  pull_request)
    # actions/checkout checks out the merge ref: HEAD's first parent is the
    # base tip GitHub merged onto, so HEAD^1..HEAD is exactly the pull
    # request's net change, whatever its own history (force-pushes
    # included). Checked: HEAD's second parent must be the pull request's
    # head; else (not the merge ref) the event's base is used.
    if [ -n "${HEAD_SHA:-}" ] && [ "$(git rev-parse -q --verify 'HEAD^2' || true)" = "$HEAD_SHA" ]; then
      from=$(git rev-parse 'HEAD^1')
    else
      from=${BASE_SHA:-}
    fi ;;
  push) from=${BEFORE:-} ;;
  workflow_dispatch)
    [ -n "${DIFF_BASE:-}" ] || everything "manual run without diff-base" "${FORCE_TSAN:-false}"
    from=$(git rev-parse -q --verify "${DIFF_BASE}^{commit}" || true) ;;
esac
if [ -z "$from" ] || [ "$from" = "$zero" ] || ! git cat-file -e "$from^{commit}" 2>/dev/null; then
  everything "event ${EVENT:-none}, from '${from}'"
fi

# --no-renames: a rename lists both paths, so moving a file out of src/
# still counts as a change to src/.
changed=$(git diff --no-renames --name-only "$from" HEAD)
echo "Changed files since ${from:0:12}:"
if [ -n "$changed" ]; then echo "$changed" | sed 's/^/  /'; else echo "  (none)"; fi

code=false; tsan=false; movegen=false
# An empty list counts as code (its one empty line is not documentation).
if grep -Evq "$docs_re" <<<"$changed"; then code=true; fi
if grep -Eq "$movegen_re" <<<"$changed"; then movegen=true; fi
if grep -Eq "$tsan_re" <<<"$changed"; then tsan=true; fi
if [ "$tsan" = false ]; then
  while IFS= read -r f; do
    [ -n "$f" ] && [ -f "$f" ] || continue  # a deleted file has no content
    grep -Eq "$source_re" <<<"$f" || continue
    case $f in src/search/searcher.cpp|src/search/searcher.hpp) continue ;; esac
    if grep -Eq "$thread_re" "$f"; then echo "tsan: $f uses threads"; tsan=true; break; fi
  done <<<"$changed"
fi
# Documentation alone never needs TSan or perft (no pattern above matches
# it today; this keeps the three answers consistent).
if [ "$code" = false ]; then tsan=false; movegen=false; fi
# force-tsan wins: a manual run asked for it.
if [ "${FORCE_TSAN:-false}" = true ]; then tsan=true; fi
emit code "$code"; emit tsan "$tsan"; emit movegen "$movegen"
